import os
import arcpy
from datetime import datetime
from utils.paths import get_gdb_path
from config.config import TRACKER_FIELDS
from utils.gis_tools import (finalize_tracker_data, delete_unnecessary_fields)

arcpy.env.overwriteOutput = True
dt = datetime.now()

# PATHS
staged_gdb = get_gdb_path("doi", "staged", "doi")
input_fc = os.path.join(staged_gdb, "ifpers_classified_temp")
output_fc = os.path.join(staged_gdb, "ifpers_final")

# ----- START SCRIPT -----
print("--- IFPERS STAGE 2: Finalizing Reviewed Data ---")
arcpy.management.CopyFeatures(input_fc, output_fc)

print("Calculating master tracking fields and mapping regional agency key...")
finalize_tracker_data(
    output_fc,
    agency_key="ifpers"
)

# Clean up
delete_unnecessary_fields(output_fc, TRACKER_FIELDS)

print("\n=== IFPERS STAGE 2 COMPLETE ===")
print(f"✅ Production dataset built: {output_fc}")
print("Data is verified and ready for the final cross-agency merge.")
print("Completed! Run Time: %s\n\n" % (datetime.now() - dt))
