import numpy as np
import pickle, os

GRID_RES = 1.0 # degrees
LAT_RANGE = np.arange(-80, 81, GRID_RES)
LON_RANGE = np.arange(-180, 181, GRID_RES)
N_LAT = len(LAT_RANGE)
N_LON = len(LON_RANGE)

def build_ocean_mask() -> np.ndarray:
    """Returns bool 2D array: True = navigable ocean (Loaded from pre-baked file)"""
    # This points directly to the file you generated with your bake script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cache = os.path.join(current_dir, "ocean_grid_data.pkl") 
    
    if not os.path.exists(cache):
        raise FileNotFoundError(f"CRASH: Cannot find {cache}. Did you force push the .pkl file to GitHub?")

    print("Loading lightweight pre-baked ocean mask...")
    with open(cache, "rb") as f: 
        return pickle.load(f)

# Helper converters used by A*
def latlon_to_ij(lat, lon):
    i = int(round((lat - LAT_RANGE[0]) / GRID_RES))
    j = int(round((lon - LON_RANGE[0]) / GRID_RES))
    return max(0, min(i, N_LAT-1)), j % N_LON

def ij_to_latlon(i, j):
    return float(LAT_RANGE[i]), float(LON_RANGE[j % N_LON])