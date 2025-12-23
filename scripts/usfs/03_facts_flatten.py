"""
---------------------------------------------------------------------------
Title: FACTS Duplicate Shape Identification and Dissolve Script

Purpose:
    This script identifies and resolves duplicate treatment
    features within the U.S. Forest Service FACTS dataset prior to Forest Tracker
    integration. It detects shape duplicates, groups them logically, dissolves
    redundant geometries, and outputs a flattened, cleaned feature class.

Major Steps:
    1. Create a working copy of the FACTS reclassified perimeters.
    2. Identify shape duplicates using a defined XY tolerance (e.g., 25 meters).
    3. Assign a unique Duplicate Group ID (DuplID) to all identical shapes.
    4. Create dissolve groups for duplicate features based on activity type and
       completion date.
    5. Dissolve grouped duplicates while preserving key attribute information
       (e.g., NEPA_DOC_NAME, TREATMENT_NAME, NBR_UNITS_ACCOMPLISHED).
    6. Rename fields to remove ArcGIS dissolve prefixes and restore clean names.
    7. Merge dissolved and non-duplicate features into a single flattened layer.

Inputs:
    FACTS_reclass  – Perimeter feature class with reclassified FACTS treatments.

Outputs:
    perim_flatten  – Flattened feature class containing both dissolved duplicates
                     and unique features, ready for attribute standardization.
---------------------------------------------------------------------------
"""

# Import Libraries
import os
import arcpy
import pandas as pd
from datetime import datetime

# --- CONFIG ---
arcpy.env.overwriteOutput = True
dt = datetime.now()
datetime_str = dt.strftime("%Y-%m-%d")

# Base workspace
base_fldr = r"E:\CFRI\FOREST_TRACKER\FEDERAL_DATA_CROSSWALK\USFS_FACTS"
arcpy.env.workspace = base_fldr

# Directories and files
data_dir = os.path.join(base_fldr, "OUTPUT")
FACTS_reclass = os.path.join(data_dir, 'raw_data_copy.gdb/perimeter_FACTS_reclassified')

# Scratch and output locations
scratchFolder = os.path.join(base_fldr, "SCRATCH")
scratch_gdb = os.path.join(scratchFolder, "scratch.gdb")

find_identical = os.path.join(scratch_gdb, "find_identical")
dupes_layer = os.path.join(scratch_gdb, "dupes_layer")
nondupes_layer = os.path.join(scratch_gdb, "nondupes_layer")
perim_dupes_dissolved = os.path.join(scratch_gdb, "perim_dupes_dissolved")
perim_flatten_output = os.path.join(scratch_gdb, "perim_flatten")

# Create working copy
arcpy.CopyFeatures_management(FACTS_reclass, find_identical)

# Check for identical shape duplicates
xy_tolerance = "25 Meters"
find_identical_table = os.path.join(scratch_gdb, "Find_Identical_output")
sum_stats_table = os.path.join(scratch_gdb, "Find_Identical_output_SumStats")

print("...Start duplicate issues resolve...")
print(f"Looking for identical shapes with XY tolerance of {xy_tolerance}...")

# Find identical shapes
arcpy.management.FindIdentical(
    in_dataset=find_identical,
    out_dataset=find_identical_table,
    fields=["Shape"],
    xy_tolerance=xy_tolerance,
    output_record_option="ONLY_DUPLICATES"
)

dup_count = int(arcpy.management.GetCount(find_identical_table)[0])
if dup_count == 0:
    print("No duplicate shapes found.")
else:
    print(f"Found {dup_count} duplicate records. Performing statistics...")

    arcpy.analysis.Statistics(
        in_table=find_identical_table,
        out_table=sum_stats_table,
        statistics_fields=[["FEAT_SEQ", "COUNT"]],
        case_field="FEAT_SEQ"
    )

    arcpy.management.JoinField(
        in_data=find_identical_table,
        in_field="FEAT_SEQ",
        join_table=sum_stats_table,
        join_field="FEAT_SEQ",
        fields=["COUNT"]
    )

    arcpy.management.JoinField(
        in_data=find_identical,
        in_field="OBJECTID",
        join_table=find_identical_table,
        join_field="IN_FID",
        fields=["FEAT_SEQ", "COUNT"]
    )

    arcpy.AlterField_management(
        in_table=find_identical,
        field="FEAT_SEQ",
        new_field_name="DuplID",
        new_field_alias="Duplicate Group ID",
        field_type="LONG"
    )

# Find exact duplicates
print("Search for duplicates")
#group_fields = ["DuplID", "ACTIVITY", "DATE_COMPLETED"]
group_fields = ["DuplID", "activity_reclass", "DATE_COMPLETED"]
fields = group_fields + ["OBJECTID"]

df_table = arcpy.da.TableToNumPyArray(find_identical, fields, null_value=0)
df = pd.DataFrame(df_table)

# Split into SHAPE duplicates and non SHAPE duplicates
dupes_df = df[df["DuplID"] != 0].copy()
nondupes_df = df[df["DuplID"] == 0].copy()

# Assign dissolve groups only to true duplicates
if not dupes_df.empty:
    dupes_df["DISSOLVE_KEY"] = dupes_df[group_fields].astype(str).agg("|".join, axis=1)
    dupes_df["DISSOLVE_GRP"] = dupes_df["DISSOLVE_KEY"].astype("category").cat.codes + 1
    print(f"Created {dupes_df['DISSOLVE_GRP'].nunique()} dissolve groups for {len(dupes_df)} duplicate features.")
else:
    dupes_df["DISSOLVE_GRP"] = None
    print("No duplicate features found.")

# Merge data back together
df = pd.concat([dupes_df, nondupes_df], ignore_index=True)
df["DISSOLVE_GRP"] = df["DISSOLVE_GRP"].fillna("None")

# Write data back to feature class
arcpy.AddField_management(find_identical, "DISSOLVE_GRP", "TEXT", field_length=50)
value_map = dict(zip(df["OBJECTID"], df["DISSOLVE_GRP"].astype(str)))
with arcpy.da.UpdateCursor(find_identical, ["OBJECTID", "DISSOLVE_GRP"]) as cursor:
    for row in cursor:
        oid = row[0]
        if oid in value_map:
            row[1] = value_map[oid]
            cursor.updateRow(row)

# Save SHAPE duplicates and non-duplicates separately
arcpy.MakeFeatureLayer_management(find_identical, "find_identical_lyr")

arcpy.SelectLayerByAttribute_management("find_identical_lyr", "NEW_SELECTION",
                                        "DISSOLVE_GRP IS NOT NULL AND DISSOLVE_GRP <> 'None'")
arcpy.CopyFeatures_management("find_identical_lyr", dupes_layer)

arcpy.SelectLayerByAttribute_management("find_identical_lyr", "NEW_SELECTION",
                                        "DISSOLVE_GRP IS NULL OR DISSOLVE_GRP = 'None'")
arcpy.CopyFeatures_management("find_identical_lyr", nondupes_layer)

# Dissolve SHAPE duplicates while retaining important attribute information
print("Dissolve identical features")
dissolve_fields = group_fields + ["DISSOLVE_GRP"]
agg_fields = [
    ["NBR_UNITS_ACCOMPLISHED", "SUM"],
    ["NEPA_DOC_NAME", "CONCATENATE"],
    ["TREATMENT_NAME", "CONCATENATE"],
    ["fileNmDate", "FIRST"],
    ["FUND_CODE", "CONCATENATE"],
    ["funding_update", "CONCATENATE"],
    ["funding_type", "FIRST"],
    #["activity_reclass", "FIRST"]
    ["ACTIVITY", "CONCATENATE"]
]

arcpy.Dissolve_management(
    in_features=dupes_layer,
    out_feature_class=perim_dupes_dissolved,
    dissolve_field=dissolve_fields,
    statistics_fields=agg_fields,
    multi_part="",
    concatenation_separator="; "
)

fields = arcpy.ListFields(perim_dupes_dissolved)
for f in fields:
    for prefix in ("SUM_", "FIRST_", "CONCATENATE_"):
        if f.name.startswith(prefix):
            new_name = f.name.replace(prefix, "")
            arcpy.management.AlterField(perim_dupes_dissolved, f.name, new_name, new_name)

arcpy.Merge_management(
    inputs=[perim_dupes_dissolved, nondupes_layer],
    output=perim_flatten_output
)

print(f"Dissolve complete!\nOutput saved to: {perim_flatten_output}")
