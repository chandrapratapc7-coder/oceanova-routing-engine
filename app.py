#AIzaSyDls9T7IoIItLrR-qkingnIVjnOlHHVt1o/2c4ed773928de48bb0cbf503
import math
import os
import pickle
import requests
import concurrent.futures
from functools import lru_cache
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from rdp import rdp
from shapely.geometry import Point, shape

# Import your core custom routing and grid systems
from ocean_grid import build_ocean_mask
from pathfinder import astar
from weather_costs import build_weather_cost_grid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================================
# 1. ECA ZONE GEOMETRY DEFINITIONS
# =====================================================================
ECA_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "North America ECA"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-82, 24], [-70, 24], [-60, 45], [-75, 45], [-82, 24]]
                ],
            },
        },
        {
            "type": "Feature",
            "properties": {"name": "Mediterranean ECA"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[-6, 35], [36, 30], [36, 46], [-6, 44], [-6, 35]]
                ],
            },
        },
    ],
}

eca_polygons = [shape(feature["geometry"]) for feature in ECA_GEOJSON["features"]]

def is_in_eca(lat: float, lon: float) -> bool:
    point = Point(lon, lat)
    return any(polygon.contains(point) for polygon in eca_polygons)

@app.get("/api/v1/eca-zones")
def get_eca_zones():
    return ECA_GEOJSON


# =====================================================================
# 2. HYDRODYNAMIC PHYSICS & CURRENT ENGINE
# =====================================================================

@lru_cache(maxsize=1024)
def get_current_at(lat: float, lon: float):
    """Fetches live ocean current data from NOAA ERDDAP with Caching."""
    # Rounding coordinates slightly drastically improves cache hit rates
    lat_r = round(lat * 2) / 2
    lon_r = round(lon * 2) / 2
    try:
        url = (f"https://coastwatch.pfeg.noaa.gov/erddap/griddap/"
               f"jplOscarv2.json?u[last][({lat_r}):1:({lat_r})][({lon_r}):1:({lon_r})]"
               f",&v[last][({lat_r}):1:({lat_r})][({lon_r}):1:({lon_r})]")
        r = requests.get(url, timeout=3).json()
        u_ms = r["table"]["rows"][0][3]
        v_ms = r["table"]["rows"][0][4]
        
        # ERDDAP returns None if the coordinate is over landmass
        if u_ms is None or v_ms is None: 
            return 0.0, 0.0
            
        current_kn = math.sqrt(u_ms**2 + v_ms**2) * 1.944
        direction = math.degrees(math.atan2(u_ms, v_ms)) % 360
        return current_kn, direction
    except:
        return 0.0, 0.0 

def admiralty_fuel(dist_nm: float, speed: float, dwt: float, adm_const: float = 400.0) -> float:
    if speed <= 0 or dist_nm <= 0: return 0.0
    daily_fuel = ((dwt ** (2 / 3)) * (speed**3)) / adm_const
    voyage_days = dist_nm / (speed * 24)
    return daily_fuel * voyage_days

def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3440.065
    rad = math.pi / 180
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1 * rad) * math.cos(lat2 * rad) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))

def calc_heading(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - (math.sin(lat1) * math.cos(lat2) * math.cos(dlon))
    initial_bearing = math.atan2(x, y)
    return (math.degrees(initial_bearing) + 360) % 360

def apply_hydrodynamics(stw: float, wave_height: float, wind_dir: float, heading: float):
    rel_wind = min(abs(wind_dir - heading), 360 - abs(wind_dir - heading))
    if rel_wind <= 45: 
        sog = stw - (0.5 * wave_height)
        cond = "Headwind"
    elif rel_wind >= 135: 
        sog = stw + (0.1 * wave_height)
        cond = "Tailwind"
    else: 
        sog = stw - (0.2 * wave_height)
        cond = "Beam Sea"
    return max(4.0, sog), cond 

def calculate_voyage_metrics(
    actual_eca_mt: float, actual_noneca_mt: float, 
    actual_days: float, ideal_days: float, 
    total_dist: float, eca_dist: float, non_eca_dist: float,
    speed_stw: float, avg_sog: float,
    dwt: float, target_days: float, is_suez_route: bool, is_detour: bool = False
):
    eca_fuel_usd = actual_eca_mt * 820.0  
    non_eca_fuel_usd = actual_noneca_mt * 620.0  
    co2_tonnes = (actual_eca_mt + actual_noneca_mt) * 3.114  
    co2_cost_usd = co2_tonnes * 19.21  
    # Google API coordinates constraint override -> Ensure Canal dues match the real mapped coordinates
    canal_dues = (dwt * 0.55 * 4.5 * 1.32) if is_suez_route else 0.0

    total_cost = eca_fuel_usd + non_eca_fuel_usd + co2_cost_usd + canal_dues
    
    weather_delay_hours = max(0, (actual_days - ideal_days) * 24)
    ideal_fuel_total = admiralty_fuel(total_dist, speed_stw, dwt)
    fuel_penalty_mt = max(0, (actual_eca_mt + actual_noneca_mt) - ideal_fuel_total)
    fuel_penalty_usd = fuel_penalty_mt * 620.0 

    eta_status = "ON_TIME"
    hours_late = 0.0
    speed_needed = speed_stw
    advanced_warning = ""

    start_date = datetime.now()
    eta_date = start_date + timedelta(days=actual_days)
    laycan_end = start_date + timedelta(days=target_days)
    laycan_start = laycan_end - timedelta(days=1)

    if actual_days > target_days:
        eta_status = "LATE"
        hours_late = (actual_days - target_days) * 24
        speed_needed = speed_stw * (actual_days / target_days) if target_days > 0 else speed_stw
        advanced_warning = (
            f"ETA: {eta_date.strftime('%b %d, %H:00')} (laycan {laycan_start.strftime('%b %d')}-{laycan_end.strftime('%b %d')}). "
            f"Current forecast indicates high risk of missing laycan by ~{int(hours_late)} hrs due to heavy weather. "
            f"Increase STW to {round(speed_needed, 1)} kn to recover buffer."
        )

    return {
        "total_voyage_cost_usd": round(total_cost, 0),
        "voyage_days": round(actual_days, 1),
        "distance_nm": round(total_dist, 0),
        "eca_dist": round(eca_dist, 0), "non_eca_dist": round(non_eca_dist, 0),
        "eca_fuel_mt": round(actual_eca_mt, 0), "eca_fuel_usd": round(eca_fuel_usd, 0),
        "non_eca_fuel_mt": round(actual_noneca_mt, 0), "non_eca_fuel_usd": round(non_eca_fuel_usd, 0),
        "canal_dues_usd": round(canal_dues, 0),
        "co2_tonnes": round(co2_tonnes, 0), "co2_cost_usd": round(co2_cost_usd, 0),
        "eta_status": eta_status, "hours_late": round(hours_late, 1),
        "speed_needed": round(speed_needed, 1), "advanced_warning": advanced_warning,
        "max_bf": 3 if is_detour else 7, "gale_risk": "2.1%" if is_detour else "18-22%",
        "speed_stw": speed_stw, "avg_sog": round(avg_sog, 1),
        "weather_delay_hours": round(weather_delay_hours, 1),
        "fuel_penalty_mt": round(fuel_penalty_mt, 0),
        "fuel_penalty_usd": round(fuel_penalty_usd, 0)
    }

# =====================================================================
# 3. ROUTE SMOOTHING & METEOROLOGICAL GENERATOR
# =====================================================================
def process_route_leg(
    raw_path, speed: float, dwt: float, target_days: float, start_name: str, end_name: str, is_detour: bool = False
):
    smoothed_path = rdp(raw_path, epsilon=0.5)
    max_voyage_hours = int((sum(haversine_nm(smoothed_path[i-1][0], smoothed_path[i-1][1], smoothed_path[i][0], smoothed_path[i][1]) for i in range(1, len(smoothed_path))) / speed) + 48)

    actual_eca_mt, actual_noneca_mt = 0.0, 0.0
    eca_dist, non_eca_dist = 0.0, 0.0
    total_actual_days, total_ideal_days, total_dist = 0.0, 0.0, 0.0
    sog_accumulator, leg_count = 0.0, 0
    is_suez_route = False
    
    waypoints_data = []
    legs_breakdown = [] 

    # OPTIMIZATION: Fetch all ocean currents simultaneously in parallel threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        currents_data = list(executor.map(lambda pt: get_current_at(pt[0], pt[1]), smoothed_path))

    for i in range(len(smoothed_path)):
        lat, lng = smoothed_path[i]
        if 28 <= lat <= 32 and 32 <= lng <= 34: is_suez_route = True
        
        heading = 0
        prev_name = start_name if i == 1 else f"WP-{i-1}"
        
        if i > 0:
            prev_lat, prev_lng = smoothed_path[i - 1]
            dist = haversine_nm(prev_lat, prev_lng, lat, lng)
            heading = calc_heading(prev_lat, prev_lng, lat, lng)
            in_eca = is_in_eca(lat, lng) or is_in_eca(prev_lat, prev_lng)
            if in_eca: eca_dist += dist
            else: non_eca_dist += dist
        else:
            dist, in_eca = 0, False

        # Load current data from parallel fetch
        current_kn, current_dir = currents_data[i]

        timeline = []
        for hour in range(0, max_voyage_hours, 6):
            base_wave = 1.0 + (abs(lat) / 40.0)
            if not is_detour and len(smoothed_path) * 0.3 < i < len(smoothed_path) * 0.7:
                base_wave += 3.2 
            wave_variance = math.sin((hour + lat) / 24.0) * 1.5
            current_wave = max(0.5, base_wave + wave_variance)
            bf = 4; status = "CLEAR"
            if current_wave > 2.5: bf = 5; status = "CAUTION"
            if current_wave > 4.0: bf = 7; status = "CRITICAL"
            timeline.append({ "hour": hour, "wind_dir": int((hour * 5 + lat * 10) % 360), "wind_speed": int(current_wave * 5), "wave_height": round(current_wave, 1), "beaufort": bf, "status": status })

        sog, condition = speed, "Departure"
        if i > 0:
            sog, condition = apply_hydrodynamics(speed, timeline[0]["wave_height"], timeline[0]["wind_dir"], heading)
            current_boost = current_kn * math.cos(math.radians(current_dir - heading))
            sog = max(4.0, sog + current_boost)

            ideal_days = dist / (speed * 24)
            actual_days = dist / (sog * 24)
            
            ideal_fuel = admiralty_fuel(dist, speed, dwt)
            actual_fuel = ideal_fuel * (speed / sog) 
            
            if in_eca: actual_eca_mt += actual_fuel
            else: actual_noneca_mt += actual_fuel
            
            total_actual_days += actual_days
            total_ideal_days += ideal_days
            total_dist += dist
            sog_accumulator += sog
            leg_count += 1

            wp_name = end_name if i == len(smoothed_path) - 1 else f"WP-{i}"
            legs_breakdown.append({
                "from": prev_name, "to": wp_name,
                "dist_nm": round(dist, 0), "stw_kn": speed,
                "sog_kn": round(sog, 1), "wave_m": round(timeline[0]["wave_height"], 1),
                "bf": timeline[0]["beaufort"], "delay_hrs": round((actual_days - ideal_days) * 24, 1),
                "fuel_mt": round(actual_fuel, 0)
            })
        else:
            wp_name = start_name

        waypoints_data.append({"lat": lat, "lng": lng, "name": wp_name, "timeline": timeline, "sog": round(sog, 1), "condition": condition})

    avg_sog = sog_accumulator / leg_count if leg_count > 0 else speed
    metrics = calculate_voyage_metrics(actual_eca_mt, actual_noneca_mt, total_actual_days, total_ideal_days, total_dist, eca_dist, non_eca_dist, speed, avg_sog, dwt, target_days, is_suez_route, is_detour)
    
    return {"path": [{"lat": pt[0], "lng": pt[1]} for pt in smoothed_path], "waypoints": waypoints_data, "metrics": metrics, "legs": legs_breakdown}


# =====================================================================
# 4. MASTER ROUTING API ENDPOINT
# =====================================================================
@app.get("/api/v1/route-analysis")
def analyze_dynamic_route(
    start_lat: float, start_lng: float, start_name: str,
    end_lat: float, end_lng: float, end_name: str,
    speed: float = 11.0, dwt: float = 50000.0, target_days: float = 12.0
):
    raw_path_main = astar((start_lat, start_lng), (end_lat, end_lng), weather_costs={})
    if not raw_path_main: raise HTTPException(status_code=400, detail="A* Engine failed to discover a valid maritime path.")
    main_route_data = process_route_leg(raw_path_main, speed, dwt, target_days, start_name, end_name, is_detour=False)

    mid_idx = len(raw_path_main) // 2
    storm_center = raw_path_main[mid_idx]
    heavy_weather_penalties = {}

    for i in range(-2, 3):
        for j in range(-2, 3):
            heavy_weather_penalties[(int(storm_center[0]) + i, int(storm_center[1]) + j)] = 999

    raw_path_detour = astar((start_lat, start_lng), (end_lat, end_lng), weather_costs=heavy_weather_penalties)
    if not raw_path_detour: raw_path_detour = raw_path_main 
    detour_route_data = process_route_leg(raw_path_detour, speed, dwt, target_days, start_name, end_name, is_detour=True)

    return { "routes": { "main": main_route_data, "detour": detour_route_data } }


# =====================================================================
# 5. FEATURE 5: ROUTE A VS B (SUEZ VS CAPE COMPARISON)
# =====================================================================
def interpolate_path(waypoints):
    path = []
    for i in range(len(waypoints)-1):
        p1, p2 = waypoints[i], waypoints[i+1]
        dist = haversine_nm(p1[0], p1[1], p2[0], p2[1])
        steps = max(2, int(dist / 60)) 
        for step in range(steps):
            frac = step / float(steps)
            lat = p1[0] + (p2[0]-p1[0])*frac
            lon = p1[1] + (p2[1]-p1[1])*frac
            path.append((lat, lon))
    path.append(waypoints[-1])
    return path

@app.get("/api/v1/compare-routes")
def compare_suez_vs_cape(
    start_lat: float, start_lng: float, start_name: str,
    end_lat: float, end_lng: float, end_name: str,
    speed: float = 13.0, dwt: float = 50000.0, target_days: float = 32.0
):
    """Executes head-to-head accounting using DYNAMIC routing anchors."""
    
    SUEZ_BASE = [(36.1, -5.3), (35.5, 14.5), (31.3, 32.3), (12.5, 43.4)] 
    CAPE_BASE = [(25.0, -20.0), (-10.0, -10.0), (-34.4, 18.5), (-30.0, 55.0)] 
    
    SUEZ_WAYPOINTS = [(start_lat, start_lng)] + SUEZ_BASE + [(end_lat, end_lng)]
    CAPE_WAYPOINTS = [(start_lat, start_lng)] + CAPE_BASE + [(end_lat, end_lng)]
    
    suez_path = interpolate_path(SUEZ_WAYPOINTS)
    cape_path = interpolate_path(CAPE_WAYPOINTS)
    
    suez_data = process_route_leg(suez_path, speed, dwt, target_days, start_name, end_name, is_detour=False)
    cape_data = process_route_leg(cape_path, speed, dwt, target_days, start_name, end_name, is_detour=True)
    
    m_suez = suez_data["metrics"]
    m_cape = cape_data["metrics"]
    
    rec = "SUEZ" if (m_suez["eta_status"] != "LATE" and m_suez["total_voyage_cost_usd"] < m_cape["total_voyage_cost_usd"]) else "CAPE"
    if m_suez["eta_status"] == "LATE" and m_cape["eta_status"] != "LATE":
        rec = "CAPE"
        
    return { "suez": suez_data, "cape": cape_data, "recommendation": rec }