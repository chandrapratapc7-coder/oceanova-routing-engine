import numpy as np
import pickle, os
from global_land_mask import globe 

GRID_RES = 1.0 # degrees — change to 0.5 later for better accuracy
LAT_RANGE = np.arange(-80, 81, GRID_RES)
LON_RANGE = np.arange(-180, 181, GRID_RES)
N_LAT = len(LAT_RANGE)
N_LON = len(LON_RANGE)

# Key straits to FORCE open — 1° grid sometimes misses narrow passages
# Key straits to FORCE open — 1° grid sometimes misses narrow passages
# Key straits to FORCE open — 1° grid sometimes misses narrow passages
FORCED_OCEAN = [
    # --- NORTH AMERICA (NEW) ---
    (25, -79), (26, -79), (25, -80), # Miami / Florida Straits
    (40, -73), (40, -74), (39, -74), # New York Approach

    # --- EUROPE & MEDITERRANEAN ---
    (53, 3), (53, 4), (52, 3), (52, 4), # Rotterdam approach
    (51, 2), (51, 1), (50, 0),          # English Channel
    (36, -6), (36, -5),                 # Gibraltar
    (37, 11), (37, 10),                 # Strait of Sicily (The Med Wall)

    # --- SUEZ & RED SEA ---
    (31, 32), (30, 32), (29, 33), (28, 34), # Suez Canal
    (13, 43), (12, 43), (11, 44),           # Bab-el-Mandeb (Red Sea exit)

    # --- ASIA & MALACCA ---
    (1, 103), (1, 104),                     # Singapore Port
    (2, 102), (3, 100), (4, 99), (5, 98)    # Malacca Strait
]

def build_ocean_mask() -> np.ndarray:
    """Returns bool 2D array: True = navigable ocean"""
    cache = "ocean_mask.pkl"
    if os.path.exists(cache):
        print("Loading cached ocean mask...")
        with open(cache, "rb") as f: 
            return pickle.load(f)

    print("Building ocean mask for the first time. This takes a few seconds...")
    mask = np.zeros((N_LAT, N_LON), dtype=bool)
    for i, lat in enumerate(LAT_RANGE):
        for j, lon in enumerate(LON_RANGE):
            mask[i, j] = globe.is_ocean(lat, lon)

    # Force straits and canals open
    for lat, lon in FORCED_OCEAN:
        i = round((lat - LAT_RANGE[0]) / GRID_RES)
        j = round((lon - LON_RANGE[0]) / GRID_RES)
        if 0 <= i < N_LAT and 0 <= j < N_LON:
            mask[i, j] = True # override land — canal is passable

    with open(cache, "wb") as f: 
        pickle.dump(mask, f)
    print(f"Ocean mask built: {mask.sum()} navigable cells")
    return mask

# Helper converters used by A*
def latlon_to_ij(lat, lon):
    i = int(round((lat - LAT_RANGE[0]) / GRID_RES))
    j = int(round((lon - LON_RANGE[0]) / GRID_RES))
    return max(0, min(i, N_LAT-1)), j % N_LON

def ij_to_latlon(i, j):
    return float(LAT_RANGE[i]), float(LON_RANGE[j % N_LON])

# This runs only when you execute this file directly
if __name__ == "__main__":
    build_ocean_mask()