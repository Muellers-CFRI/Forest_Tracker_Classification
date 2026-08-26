"""
---------------------------------------------------------------------------
Title: BLM Treatment Ingestion and Keyword Search Classifier (Stage 1)

Purpose:
    Ingests raw BLM treatment footprints, standardizes time coordinates,
    and applies an automated text-mining keyword search against names
    and comments. Segregates unmapped rows into a QA/QC layer for human review.

Major Steps:
    1. Import raw regional BLM spatial datasets into the staged GDB workspace.
    2. Format primary temporal fields and filter records based on `START_YEAR`.
    3. Execute regex/keyword lookups across `TRTMNT_NM` and `TRTMNT_COMMENTS`.
    4. Isolate successful matches into a temporary staging layer.
    5. Route ambiguous or unmapped text rows into an explicit review layer
       (`blm_unclassified_staged_review`) to enforce a Human-in-the-Loop checkpoint.

Inputs:
    RAW_GDB/blm    – Unaltered raw Bureau of Land Management datasets.
    KEYWORD_CSV    – Regex pattern-matching library for text parsing.

Outputs:
    blm_unclassified_staged_review – A spatial QA/QC layer requiring manual crosswalk updates.
    blm_classified_temp            – Temporary holding layer for conformed records.
---------------------------------------------------------------------------
"""

# Import libraries
import os
import arcpy
from datetime import datetime
from scripts.utils.paths import get_gdb_path, RAW_GDB, KEYWORD_CSV
from config.config import START_YEAR, TRACKER_FIELDS
from scripts.utils.date_tools import prep_date_fields, filter_by_year
from scripts.utils.gis_tools import add_fields_from_schema
from scripts.utils.keyword_search import classify_treatments, finalize_and_split

arcpy.env.overwriteOutput = True
dt = datetime.now()

# PATHS
staged_gdb = get_gdb_path("blm", stage="staged", gdb_name="blm")
raw_input = os.path.join(RAW_GDB, "blm")

prepped_fc = os.path.join(staged_gdb, "blm_prepped")
filtered_fc = os.path.join(staged_gdb, "blm_filtered")
combined_out = os.path.join(staged_gdb, "blm_combined_staged")
class_out = os.path.join(staged_gdb, "blm_classified_temp")
unclass_out = os.path.join(staged_gdb, "blm_unclassified_staged_review")
delete_out = os.path.join(staged_gdb, "blm_deleted")

# ----- START SCRIPT -----
print("--- BLM STAGE 1: Keyword Classification ---")

print("Copying raw data to processing environment...")
arcpy.management.CopyFeatures(raw_input, prepped_fc)

add_fields_from_schema(prepped_fc, TRACKER_FIELDS)

print("Stamping SourceOID and calculating completion years...")
prep_date_fields(
    prepped_fc,
    date_fields=["TRTMNT_START_DT", "YEAR_COMP"],
    min_year=START_YEAR
)

print("Filtering records by year...")
filter_by_year(prepped_fc, filtered_fc, year_field="YEAR_COMP")

print("Running text-mining keyword search classification engine...")
classify_treatments(
    input_fc=filtered_fc,
    fields_to_classify=["TRTMNT_NM", "TRTMNT_COMMENTS"],
    activity_csv=str(KEYWORD_CSV),
    output_fc=combined_out
)

print("Splitting features into classified and QA/QC review layers...")
finalize_and_split(combined_out, delete_out, unclass_out, class_out)

# Cleanup working datasets
arcpy.management.Delete(prepped_fc)
arcpy.management.Delete(filtered_fc)

print("\n=== BLM STAGE 1 COMPLETE ===")
print(f"👉 Please review QA/QC layer: {unclass_out}")
print(f"👉 Move reconciled rows to:  {class_out} before running Stage 2.")
print("Completed! Run Time: %s\n\n" % (datetime.now() - dt))
