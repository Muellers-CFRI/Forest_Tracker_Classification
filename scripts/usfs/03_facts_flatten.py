"""
---------------------------------------------------------------------------
Title: USFS FACTS Spatial Flattening and Dissolve Pipeline

Purpose:
    Identifies and resolves overlapping or duplicate treatment features
    within the USFS FACTS dataset to eliminate spatial "double counting"
    before final data mapping.

Major Steps:
    1. Import data and generate stable tracking fields upstream.
    2. Group adjacent or near-duplicate shapes using an aggressive XY
       tolerance (100 meters) to account for field-GPS collection drift.
    3. Use fast Pandas in-memory dictionaries to map and assign unique
       dissolve group keys (`DISSOLVE_GRP`) based on activity type,
       spatial cluster, and completion timeframe.
    4. Execute an arcpy.management.Dissolve using customized aggregation rules
       to flatten geometries.
    5. Re-integrate unique (non-overlapping) features to output a complete,
       compressed feature class.

Inputs:
    usfs_reclass – Feature class with reclassified FACTS treatments.

Outputs:
    usfs_flatten – Spatial footprint-flattened feature class ready for
                   temporal filtering and schema mapping in the final script.
---------------------------------------------------------------------------
"""

# Import Libraries
import os
import arcpy
import pandas as pd
from datetime import datetime
from scripts.utils.paths import get_gdb_path, SCRATCH_GDB

arcpy.env.overwriteOutput = True
dt = datetime.now()
datetime_str = dt.strftime("%Y-%m-%d")

# PATHS
staged_gdb = get_gdb_path("usfs", stage="staged", gdb_name="usfs")
FACTS_reclass = os.path.join(staged_gdb, "usfs_reclass")
perim_flatten_output  = os.path.join(staged_gdb, "usfs_flatten")

# QA/QC Layers (Saved to SCRATCH_GDB for review)
find_identical        = os.path.join(SCRATCH_GDB, "find_identical")
perim_dupes_dissolved = os.path.join(SCRATCH_GDB, "perim_dupes_dissolved")

# Temporary files
find_identical_table = "memory\\Find_Identical_output"
dupes_layer          = "memory\\dupes_layer"
nondupes_layer       = "memory\\nondupes_layer"

# Create working copy
arcpy.management.CopyFeatures(FACTS_reclass, find_identical)

# Check for identical shape duplicates
xy_tolerance = "100 Meters"

print("...Start duplicate issues resolve...")
print(f"Looking for identical shapes with XY tolerance of {xy_tolerance}...")

# Find identical shapes
arcpy.management.AddField(find_identical, "DuplID", "LONG", field_alias="Duplicate Group ID")

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

    dup_array = arcpy.da.TableToNumPyArray(find_identical_table, ["IN_FID", "FEAT_SEQ"])
    df_dups = pd.DataFrame(dup_array)

    dup_dict = dict(zip(df_dups["IN_FID"], df_dups["FEAT_SEQ"]))

    print("Writing duplicate IDs to spatial data...")
    with arcpy.da.UpdateCursor(find_identical, ["OBJECTID", "DuplID"]) as cursor:
        for row in cursor:
            oid = row[0]
            row[1] = dup_dict.get(oid, 0)
            cursor.updateRow(row)


# Find exact duplicates
print("Extracting attributes for duplicate classification processing...")
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


def clean_group_id(val):
    if pd.isna(val) or val == "None" or val == 0:
        return "None"
    return str(int(float(val)))


df["DISSOLVE_GRP"] = df["DISSOLVE_GRP"].apply(clean_group_id)

# Write data back to feature class
arcpy.management.AddField(find_identical, "DISSOLVE_GRP", "TEXT", field_length=50)
value_map = dict(zip(df["OBJECTID"], df["DISSOLVE_GRP"].astype(str)))

with arcpy.da.UpdateCursor(find_identical, ["OBJECTID", "DISSOLVE_GRP"]) as cursor:
    for row in cursor:
        oid = row[0]
        if oid in value_map:
            row[1] = value_map[oid]
            cursor.updateRow(row)

# Save SHAPE duplicates and non-duplicates separately
arcpy.management.MakeFeatureLayer(find_identical, "find_identical_lyr")

arcpy.management.SelectLayerByAttribute("find_identical_lyr", "NEW_SELECTION",
                                        "DISSOLVE_GRP IS NOT NULL AND DISSOLVE_GRP <> 'None'")
arcpy.management.CopyFeatures("find_identical_lyr", dupes_layer)

arcpy.management.SelectLayerByAttribute("find_identical_lyr", "NEW_SELECTION",
                                        "DISSOLVE_GRP IS NULL OR DISSOLVE_GRP = 'None'")
arcpy.management.CopyFeatures("find_identical_lyr", nondupes_layer)

arcpy.management.Delete("find_identical_lyr")

# Dissolve SHAPE duplicates while retaining important attribute information
print("Dissolve identical features")
dissolve_fields = group_fields + ["DISSOLVE_GRP"]
agg_fields = [
    ["NBR_UNITS_ACCOMPLISHED", "MAX"],
    ["NEPA_DOC_NAME", "CONCATENATE"],
    ["TREATMENT_NAME", "CONCATENATE"],
    ["fileNmDate", "FIRST"],
    ["FUND_CODE", "CONCATENATE"],
    ["funding_update", "CONCATENATE"],
    ["funding_type", "FIRST"],
    ["ACTIVITY", "CONCATENATE"]
]

arcpy.management.Dissolve(
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

print("Merging structural components into final flattened perimeter...")
arcpy.Merge_management(
    inputs=[perim_dupes_dissolved, nondupes_layer],
    output=perim_flatten_output
)

arcpy.management.Delete("memory\\")

print(f"Dissolve complete!\nOutput saved to: {perim_flatten_output}")
