import heapq, math
import pickle
from ocean_grid import latlon_to_ij, ij_to_latlon, N_LAT, N_LON

# Load the cached land mask generated in Step 1
with open("ocean_mask.pkl", "rb") as f:
    OCEAN_MASK = pickle.load(f)

# 8 directions: N S E W + 4 diagonals
DIRS = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]

def haversine_nm(lat1, lon1, lat2, lon2) -> float:
    """Calculates nautical miles between two points."""
    R = 3440.065
    p = math.pi / 180
    a = (0.5 - math.cos((lat2-lat1)*p)/2
         + math.cos(lat1*p)*math.cos(lat2*p)*(1-math.cos((lon2-lon1)*p))/2)
    return R * 2 * math.asin(math.sqrt(a))

def get_neighbours(i, j):
    """Yields valid adjacent ocean nodes, wrapping around the globe."""
    for di, dj in DIRS:
        ni, nj = i + di, (j + dj) % N_LON # wrap longitude ±180
        if 0 <= ni < N_LAT and OCEAN_MASK[ni, nj]:
            yield ni, nj

def astar(start_ll, goal_ll, weather_costs=None) -> list[tuple]:
    if weather_costs is None:
        weather_costs = {}

    si, sj = latlon_to_ij(*start_ll)
    gi, gj = latlon_to_ij(*goal_ll)
    g_lat, g_lon = ij_to_latlon(gi, gj)

    open_q = []
    heapq.heappush(open_q, (0.0, (si, sj)))
    came_from = {}
    g = {(si, sj): 0.0}
    
    # NEW: Visited set to prevent duplicate processing (Gotcha 4)
    visited = set()

    while open_q:
        _, cur = heapq.heappop(open_q)
        
        # NEW: Skip if we've already processed this exact node optimally
        if cur in visited: continue
        visited.add(cur)
        
        ci, cj = cur

        if ci == gi and cj == gj:
            return _reconstruct(came_from, cur)

        c_lat, c_lon = ij_to_latlon(ci, cj)

        for ni, nj in get_neighbours(ci, cj):
            n_lat, n_lon = ij_to_latlon(ni, nj)

            dist = haversine_nm(c_lat, c_lon, n_lat, n_lon)
            w_pen = weather_costs.get((ni, nj), 0.0)
            new_g = g[cur] + dist + w_pen

            if new_g < g.get((ni, nj), float('inf')):
                came_from[(ni, nj)] = cur
                g[(ni, nj)] = new_g
                h = haversine_nm(n_lat, n_lon, g_lat, g_lon)
                heapq.heappush(open_q, (new_g + h, (ni, nj)))

    print("WARNING: No path found. Target might be inland.")
    return []

def _reconstruct(came_from, current):
    """Rebuilds the path from the end node back to the start, then reverses it."""
    path_ij = [current]
    while current in came_from:
        current = came_from[current]
        path_ij.append(current)
    
    path_ij.reverse() # Flip it so it goes Start -> Goal
    
    # Convert matrix coordinates back to GPS Lat/Lon for Google Maps
    return [ij_to_latlon(i, j) for i, j in path_ij]