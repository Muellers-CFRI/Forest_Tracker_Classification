"""
---------------------------------------------------------------------------
Title: BLM Schema Finalization

Purpose:
    Picks up post-reviewed, fully-classified BLM data, maps native field metrics
    to the master regional tracker schema, and deploys the clean records to
    the production environment.

Major Steps:
    1. Load the manually reconciled and populated `blm_classified_temp` dataset.
    2. Generate universal tracker fields via `finalize_tracker_data`, setting
       the permanent owner index to 'doi' and assigning `BLM_ACRES`.
    3. Prune all temporary string scaffolding and keyword calculation columns.
    4. Export a pristine, fully verified feature class ready for multi-agency merging.

Inputs:
    blm_classified_temp – Staging layer populated by Stage 1 automation and manual edits.
    TRACKER_FIELDS      – Master target reporting schema configuration.

Outputs:
    blm_classified      – Clean, finalized, dashboard-ready production dataset.
---------------------------------------------------------------------------
"""

# Import libraries
import os
import arcpy
from datetime import datetime
from scripts.utils.paths import get_gdb_path
from config.config import TRACKER_FIELDS
from scripts.utils.gis_tools import delete_unnecessary_fields, finalize_tracker_data

arcpy.env.overwriteOutput = True
dt = datetime.now()

# PATHS
staged_gdb = get_gdb_path("blm", stage="staged", gdb_name="blm")
input_fc = os.path.join(staged_gdb, "blm_classified_temp")
output_fc = os.path.join(staged_gdb, "blm_classified")

# ----- START SCRIPT -----
print("--- BLM STAGE 2: Finalizing Reviewed Data ---")

arcpy.management.CopyFeatures(input_fc, output_fc)

print("Calculating master tracking fields and mapping regional agency key...")
finalize_tracker_data(
    output_fc,
    agency_key="doi",
    mgt_acre_field="BLM_ACRES"
)

# Clean up
delete_unnecessary_fields(output_fc, TRACKER_FIELDS)

print("\n=== BLM STAGE 2 COMPLETE ===")
print(f"✅ Production dataset built: {output_fc}")
print("Data is verified and ready for the final cross-agency merge.")
print("Completed! Run Time: %s\n\n" % (datetime.now() - dt))
