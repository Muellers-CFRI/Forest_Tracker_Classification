import arcpy
import os

from scripts.utils.keyword_search import (
    add_new_fields,
    split_outputs,
    classify_treatments,
    explode_activity,
    classification_fields,
    activity_fields,
    tracker_fields
)

arcpy.env.overwriteOutput = True

# ----------------------------------------------------
# ✳️ Data Configuration (EDIT FOR INPUT FEATURE CLASS)
# ----------------------------------------------------
date_field = 'COMPLETED1'                                  # Field with Date (MM/DD/YYYY) or (YYYY)
dt_start = 2000                                                 # START YEAR for filter
dt_end = 2024                                                   # END YEAR for filter
input_fc_name = "CFTv2_CSFS_GeoTracks"  # Name of input file to classify
fields_to_classify = ["TREATMENT_", "SLASH_TREA"]           # Fields to search in input_fc (i.e. comments/notes/name fields)
base_dir = r'C:\Users\semue\Documents\GITHUB\Forest_Tracker'    # path to your project (location of data folder)

# -------------------------------------------
# Configurable Base Directories
# -------------------------------------------
data_dir = os.path.join(base_dir, 'data', 'data.gdb')
output_dir = os.path.join(base_dir, 'data', 'output.gdb')
arcpy.env.workspace = data_dir

# --- Data ---
keyword_csv = os.path.join(base_dir, 'data', 'keywords.csv')    # keywords regex csv file
classify_fc = os.path.join(data_dir, input_fc_name)             # input feature class to classify

# --- Final Output for Combined Perimeters ---
temp_output_fc = arcpy.env.scratchGDB + "/output_fc"
split_output = os.path.join(output_dir, "split_output")
classified_output = os.path.join(output_dir, "classified_output")
unclassified_output = os.path.join(output_dir, "unclassified_output")
delete_output = os.path.join(output_dir, "delete_output")

# --- Run workflow ---
print("🔹 Adding new fields...")
add_new_fields(classify_fc, classification_fields)
add_new_fields(classify_fc, activity_fields)
add_new_fields(classify_fc, tracker_fields)

print("🔹 Classifying treatments...")
classify_treatments(
    input_fc=classify_fc,
    fields_to_classify=fields_to_classify,
    date_field=date_field,
    activity_csv=keyword_csv,
    output_fc=temp_output_fc,
    start_year=dt_start,
    end_year=dt_end
)

print("🔹 Exploding activities...")
explode_activity(temp_output_fc, classification_fields, split_output)

print("🔹 Splitting outputs...")
split_outputs(split_output, delete_output, unclassified_output, classified_output)

print("✅ Processing complete.")
