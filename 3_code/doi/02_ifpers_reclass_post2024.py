import os
import arcpy
from datetime import datetime
from utils.paths import get_gdb_path, IFPERS_TYPE_CSV, KEYWORD_CSV
from utils.gis_tools import classify_from_csv
from utils.keyword_search import classify_treatments, finalize_and_split

arcpy.env.overwriteOutput = True
dt = datetime.now()

staged_gdb = get_gdb_path("doi", "staged", "doi")
raw_input = os.path.join(staged_gdb, "ifpers_perimeter_dwnld")

prepped_fc = os.path.join(staged_gdb, "ifpers_prepped")
filtered_fc = os.path.join(staged_gdb, "ifpers_filtered")
combined_out = os.path.join(staged_gdb, "ifpers_combined_staged")
class_out = os.path.join(staged_gdb, "ifpers_classified_temp")
unclass_out = os.path.join(staged_gdb, "ifpers_unclassified_staged_review")
delete_out = os.path.join(staged_gdb, "ifpers_deleted")

# ----- START SCRIPT -----
print("--- IFPERS STAGE 1: Keyword Classification ---")

print("Copying raw data to processing environment...")
arcpy.management.CopyFeatures(raw_input, prepped_fc)

arcpy.management.AddField(prepped_fc, "ACT_CSV", "TEXT")
classify_from_csv(
    csv_path=IFPERS_TYPE_CSV,
    fc=prepped_fc,
    source_fields=["Type", "Category", "SubType"],
    field_map={"reclass": "ACT_CSV"}
)

print("Running text-mining keyword search classification engine...")
classify_treatments(
    input_fc=prepped_fc,
    fields_to_classify=["Name", "Notes", "ACT_CSV"],
    activity_csv=str(KEYWORD_CSV),
    output_fc=combined_out
)

print("Splitting features into classified and QA/QC review layers...")
finalize_and_split(combined_out, delete_out, unclass_out, class_out)

# Cleanup working datasets
arcpy.Delete_management(combined_out)
arcpy.Delete_management(prepped_fc)
arcpy.management.Delete(filtered_fc)

print("\n=== IFPERS STAGE 1 COMPLETE ===")
print(f"👉 Please review QA/QC layer: {unclass_out}")
print(f"👉 Move reconciled rows to:  {class_out} before running Stage 2.")
print("Completed! Run Time: %s\n\n" % (datetime.now() - dt))
