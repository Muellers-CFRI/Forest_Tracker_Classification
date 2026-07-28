import arcpy
from pathlib import Path

# Get the absolute path of the directory where THIS file lives (scripts/utils)
# .parents[1] goes up two levels to the project root (forestry-data-integration/)
ROOT_DIR = Path(__file__).resolve().parents[2]

# Define Top-Level Folders
CONFIG_DIR  = ROOT_DIR / "config"
DATA_DIR    = ROOT_DIR / "data"
STAGED_DIR  = DATA_DIR / "staged"
RAW_DIR     = DATA_DIR / "raw"
FINAL_DIR   = DATA_DIR / "final"
SCRATCH_DIR = DATA_DIR / "scratch"

# Define geodatabases
RAW_GDB = str(RAW_DIR / "raw.gdb")
SCRATCH_GDB = str(SCRATCH_DIR / "scratch.gdb")

# Define Specific File Paths
KEYWORD_CSV = CONFIG_DIR/ "keywords.csv"
FUNDING_CSV = CONFIG_DIR/ "funding_update.csv"

FS_ACTIVITY_CSV = CONFIG_DIR/ "usfs_activity_reclass.csv"
FS_METHOD_CSV = CONFIG_DIR/ "usfs_method_reclass.csv"
FS_EQUIP_CSV = CONFIG_DIR/ "usfs_equip_reclass.csv"
FS_FUND_CSV = CONFIG_DIR/ "usfs_funding_reclass.csv"
IFPERS_TYPE_CSV = CONFIG_DIR/ "ifpers_type_reclass.csv"


def ensure_directories():
    """Creates the data folder structure if it doesn't exist."""
    for folder in [STAGED_DIR, RAW_DIR, FINAL_DIR, CONFIG_DIR]:
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
