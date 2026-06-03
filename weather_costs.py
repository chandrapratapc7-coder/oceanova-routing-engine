import numpy as np
from ocean_grid import latlon_to_ij

# The Master Penalty Table (Beaufort -> Extra NM Penalty)
BF_PENALTY = {0:0, 1:0, 2:0, 3:0, 4:0,
              5:15, 6:50, 7:200, 8:600, 9:9999, 10:9999, 11:9999, 12:9999}

def build_weather_cost_grid(start_lat, start_lon, end_lat, end_lon) -> dict:
    costs = {}
    
    # ---------------------------------------------------------
    # PROTOTYPE MODE: SYNTHETIC HURRICANE
    # Instead of making 100 API calls that hang the server, 
    # we inject a massive storm directly in the Miami->Lisbon path.
    # ---------------------------------------------------------
    
    storm_lat = 32.0   # Mid-Atlantic Latitude
    storm_lon = -45.0  # Mid-Atlantic Longitude
    storm_radius = 8.0 # Degrees radius (massive storm)
    
    # Generate the weather grid around the storm center
    for lat in np.arange(storm_lat - storm_radius, storm_lat + storm_radius, 1.0):
        for lon in np.arange(storm_lon - storm_radius, storm_lon + storm_radius, 1.0):
            # Calculate distance from the eye of the storm
            dist = np.sqrt((lat - storm_lat)**2 + (lon - storm_lon)**2)
            
            if dist < 2.0: bf = 9    # Eye (Impassable - 9999nm penalty)
            elif dist < 4.5: bf = 7  # Near Gale (200nm penalty)
            elif dist < 7.0: bf = 6  # Strong breeze (50nm penalty)
            else: bf = 4             # Safe
            
            penalty = BF_PENALTY[bf]
            if penalty > 0:
                i, j = latlon_to_ij(lat, lon)
                # Keep the highest penalty if zones overlap
                costs[(i, j)] = max(costs.get((i, j), 0), penalty)
                
    print(f"Weather hazard grid generated: {len(costs)} high-risk nodes.")
    return costs

    """
    # FUTURE PRODUCTION CODE (Batch API fetching)
    # When you move to production, replace the synthetic storm with this logic,
    # but use a bulk-download tool like the Copernicus CDS API to get GRIB data 
    # instead of looping individual HTTP requests!
    """