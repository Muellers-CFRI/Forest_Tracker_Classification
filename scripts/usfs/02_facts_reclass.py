# Import libraries
import os
import arcpy
import pandas as pd
from datetime import datetime
from scripts.utils.gis_tools import classify_from_csv
from scripts.utils.paths import (get_gdb_path, SCRATCH_DIR,
                                 FS_ACTIVITY_CSV,
                                 FS_METHOD_CSV,
                                 FS_EQUIP_CSV,
                                 FS_FUND_CSV)

# --- CONFIG ---
arcpy.env.overwriteOutput = True
dt = datetime.now()

# Base workspace
staged_gdb = get_gdb_path("usfs", stage="staged", gdb_name="usfs")
input_fc = os.path.join(staged_gdb, "usfs_perimeter_dwnld")
final_fc = os.path.join(staged_gdb, "usfs_reclass")

# Load funding reclass table
funding_df = pd.read_csv(FS_FUND_CSV, encoding="utf-8-sig")

funding_dict = pd.Series(funding_df.fund_source.values,
                         index=funding_df.fund_code).to_dict()

# QA/QC csv outputs
csv_final_reclass = os.path.join(SCRATCH_DIR, "post_mechanical_reclass.csv")
csv_majority = os.path.join(SCRATCH_DIR, "majority_reclass.csv")

# Create copy in RAM
print("Creating a temporary working copy....")
working_copy = arcpy.management.CopyFeatures(input_fc, "memory\\working_copy")


def replace_fund_codes(fund_code_str, fund_dict):
    """Define a lookup + replacement function
    This version:
        handles multiple codes separated by commas or pipes
        trims spaces
        skips blanks and <Null>
        returns the comma-separated names (no "Multiple")
        """
    if not fund_code_str or pd.isna(fund_code_str):
        return fund_dict.get("<NULL>", "No Funding Code")

    parts = [p.strip() for p in str(fund_code_str).replace("|", ",").split(",") if p.strip()]
    replacements = []
    for p in parts:
        if p in fund_dict:
            replacements.append(fund_dict[p])
        else:
            replacements.append("Other")

    return ", ".join(replacements)


# Update funding codes to readable
print("Updating funding codes...")
arcpy.management.AddField(working_copy, "funding_update", "TEXT")
arcpy.management.AddField(working_copy, "funding_type", "TEXT")

with arcpy.da.UpdateCursor(working_copy, ["FUND_CODE", "funding_update", "funding_type"]) as cursor:
    for row in cursor:
        fund_code = row[0]
        new_val = replace_fund_codes(fund_code, funding_dict)

        # Split, strip, remove duplicates (preserve order)
        items = [x.strip() for x in new_val.split(",") if x.strip()]
        unique_items = list(dict.fromkeys(items))

        # If "Other" appears with something else, remove it
        if "Other" in unique_items and len(unique_items) > 1:
            unique_items = [x for x in unique_items if x != "Other"]

        row[1] = ", ".join(unique_items)
        row[2] = "Federal"
        cursor.updateRow(row)

# Reclassify FACTS ACTIVITY attribute field
print("Reclassify by Activity...")
arcpy.management.AddField(working_copy, "activity_reclass", "TEXT")

classify_from_csv(
    csv_path=FS_ACTIVITY_CSV,
    fc=working_copy,
    source_fields=["ACTIVITY"],
    field_map={"reclass": "activity_reclass"}
)

# Reclassify METHOD attribute field
print("Reclassify by Method...")
classify_from_csv(
    csv_path=FS_METHOD_CSV,
    fc=working_copy,
    source_fields=["METHOD"],
    field_map={"reclass": "activity_reclass"},
    where_clause="activity_reclass = 'SKIP'"
)

# Reclassify EQUIPMENT attribute field
print("Reclassify by Equipment...")
classify_from_csv(
    csv_path=FS_EQUIP_CSV,
    fc=working_copy,
    source_fields=["EQUIPMENT"],
    field_map={"reclass": "activity_reclass"},
    where_clause="activity_reclass = 'SKIP'"
)

# --- Post sweep cleanup and reclassification
print("Running post-sweep mechanical and removal cleanups...")
q1 = "activity_reclass = 'SKIP' AND METHOD IS NOT NULL"
with arcpy.da.UpdateCursor(working_copy, ["METHOD", "activity_reclass"], q1) as cursor:
    for method, act_reclass in cursor:
        if method in ("Mechanical", "Removal"):
            cursor.updateRow((method, method))
    del cursor

fields = [f.name for f in arcpy.ListFields(working_copy)]
data = [row for row in arcpy.da.SearchCursor(working_copy, fields)]
pd.DataFrame(data, columns=fields).to_csv(os.path.join(SCRATCH_DIR, "post_mechanical_reclass.csv"), index=False)

# Start pandas code
print("Classifying remaining 'SKIPPED' activites by Activity majority classification")
df = pd.read_csv(csv_final_reclass, low_memory=False)
df = df[df['activity_reclass'] != 'SKIP']

# Compute the most common reclass per Activity
major_activity = (
    df.groupby("ACTIVITY")["activity_reclass"]
      .agg(lambda x: x.value_counts().index[0] if not x.value_counts().empty else None)  # most frequent label
      .reset_index()
)
major_activity.to_csv(csv_majority, index=False)

# Reclassify by majority activity
majorityDict = pd.Series(
    major_activity.activity_reclass.values,
    index=major_activity.ACTIVITY
).to_dict()

print("Applying majority-based reclassification")
q2 = "activity_reclass = 'SKIP'"
with arcpy.da.UpdateCursor(working_copy, ["ACTIVITY", "activity_reclass"], q2) as cursor:
    for row in cursor:
        if row[0] in majorityDict:
            row[1] = majorityDict[row[0]]
            cursor.updateRow(row)

# Delete EXCLUDE rows in one pass using a feature layer
print("Deleting excluded or empty rows...")
sql_query = "activity_reclass = 'EXCLUDE' OR activity_reclass IS NULL"
arcpy.management.MakeFeatureLayer(working_copy, "to_delete", sql_query)
arcpy.management.DeleteRows("to_delete")
arcpy.management.Delete("to_delete")

print("Finalizing reclassified feature class...")
arcpy.management.RepairGeometry(working_copy)
arcpy.management.CopyFeatures(working_copy, final_fc)

arcpy.management.Delete("memory\\working_copy")

print("Completed! Run Time: %s\n\n" % (datetime.now() - dt))
