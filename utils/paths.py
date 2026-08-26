import arcpy
from pathlib import Path

# ==============================================================================
# --- BASE DIRECTORIES ---
# ==============================================================================
ROOT_DIR = Path(r"C:\Users\semue\Documents\CFRI_PROJECTS\FOREST_TRACKER")
DATA_REPO = Path(r"C:\Users\semue\Documents\CFRI_PROJECTS\DATA_REPOSITORY")
BOX_DIR = Path(r"C:\Users\semue\Box\CFRI\Geodatabase\Colorado_Forest_Tracker")

# ==============================================================================
# --- PIPELINE ENGINE PATHS ---
# ==============================================================================
DATA_DIR         = ROOT_DIR / "2_data"
RAW_DIR          = DATA_DIR / "raw"
STAGING_DIR      = DATA_DIR / "staged"
PRODUCTION_DIR   = DATA_DIR / "production"
SCRATCH_DIR      = DATA_DIR / "scratch"

RAW_GDB = str(RAW_DIR / "raw.gdb")
SCRATCH_GDB = str(SCRATCH_DIR / "scratch.gdb")

# ==============================================================================
# --- CONFIGURATION LOOKUPS ---
# ==============================================================================
CODE_DIR    = ROOT_DIR / "3_code"
CONFIG_DIR  = ROOT_DIR / "config"

KEYWORD_CSV     = CONFIG_DIR / "keywords.csv"
FUNDING_CSV     = CONFIG_DIR / "funding_update.csv"
FS_ACTIVITY_CSV = CONFIG_DIR / "usfs_activity_reclass.csv"
FS_METHOD_CSV   = CONFIG_DIR / "usfs_method_reclass.csv"
FS_EQUIP_CSV    = CONFIG_DIR / "usfs_equip_reclass.csv"
FS_FUND_CSV     = CONFIG_DIR / "usfs_funding_reclass.csv"
IFPERS_TYPE_CSV = CONFIG_DIR / "ifpers_type_reclass.csv"

# ==============================================================================
# --- EXTERNAL ASSETS ---
# ==============================================================================
LANDOWNER_REF  = str(DATA_REPO / r"BASE_LAYER_DATA\LAND_OWNERSHIP\PAD_US_Landowner.gdb\Surface_Management_Agency")
VEGETATION_REF = str(DATA_REPO / r"BASE_LAYER_DATA\VEGETATION_ECOLOGY\LANDFIRE_EVT_Colorado.gdb\EVT_2026")

BOX_PRODUCTION_DEPLOY = BOX_DIR / "Final_Products"


# ==============================================================================
# --- PIPELINE HELPERS ---
# ==============================================================================
def ensure_directories():
    """Creates the data folder structure if it doesn't exist."""
    for folder in [RAW_DIR, STAGING_DIR, PRODUCTION_DIR, SCRATCH_DIR, CONFIG_DIR]:
        folder.mkdir(parents=True, exist_ok=True)


def get_gdb_path(agency, stage="staged", gdb_name=None):
    """
    Helper to return a string path for arcpy.
    Example: get_gdb_path("doi") -> .../data/staged/doi/classified.gdb
    """
    folder = DATA_DIR/ stage/ agency
    folder.mkdir(parents=True, exist_ok=True)

    gdb_path = folder / f"{gdb_name}.gdb"

    # Create the GDB if it's missing
    if not arcpy.Exists(str(gdb_path)):
        arcpy.CreateFileGDB_management(str(folder), f"{gdb_name}.gdb")

    return str(gdb_path)
