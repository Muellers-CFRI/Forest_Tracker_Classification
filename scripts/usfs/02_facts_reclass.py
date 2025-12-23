# Import libraries
import os
import arcpy
import pandas as pd
from datetime import datetime

# --- CONFIG ---
arcpy.env.overwriteOutput = True
dt = datetime.now()

# Base workspace
base_fldr = r"E:\CFRI\FOREST_TRACKER\FEDERAL_DATA_CROSSWALK\USFS_FACTS"
arcpy.env.workspace = base_fldr

# Input directories and files
input_dir = os.path.join(base_fldr, "INPUT", "reclass_csv")
activity_csv  = os.path.join(input_dir, "ACTIVITY_reclass.csv")
method_csv    = os.path.join(input_dir, "METHOD_reclass.csv")
equipment_csv = os.path.join(input_dir, "EQUIPMENT_reclass.csv")
funding_csv = os.path.join(input_dir, "FUNDING_reclass.csv")

# Scratch and output locations
scratch_dir = os.path.join(base_fldr, "SCRATCH")
output_dir  = os.path.join(base_fldr, "OUTPUT", "raw_data_copy.gdb")

outtables             = os.path.join(scratch_dir, "tables")
perim_FACTS           = os.path.join(output_dir, "perimeter_FACTS")
perim_temp_output     = os.path.join(scratch_dir, "scratch.gdb", "perim_FACTS_reclass")
perim_reclass_output  = os.path.join(output_dir, "perimeter_FACTS_reclassified")


# Create copy of perimeter_FACTS
print("Creating a temporary working copy....")
perim_test = arcpy.CopyFeatures_management(perim_FACTS, perim_temp_output)

# --- Load Reclass Tables ---
activity_df = pd.read_csv(activity_csv, encoding="utf-8-sig")
method_df = pd.read_csv(method_csv, encoding="utf-8-sig")
equipment_df = pd.read_csv(equipment_csv, encoding="utf-8-sig")
funding_df = pd.read_csv(funding_csv, encoding="utf-8-sig")

activity_dict = pd.Series(activity_df.activity_reclass.values,
                          index=activity_df.activity).to_dict()
method_dict = pd.Series(method_df.method_reclass.values,
                        index=method_df.method).to_dict()
equipment_dict = pd.Series(equipment_df.equip_reclass.values,
                           index=equipment_df.equipment).to_dict()
funding_dict = pd.Series(funding_df.fund_source.values,
                         index=funding_df.fund_code).to_dict()


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
print("Update funding codes...")
arcpy.AddField_management(perim_test, "funding_update", "TEXT")
arcpy.AddField_management(perim_test, "funding_type", "TEXT")

with arcpy.da.UpdateCursor(perim_test, ["FUND_CODE", "funding_update", "funding_type"]) as cursor:
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
arcpy.AddField_management(perim_test, "activity_reclass", "TEXT")

with arcpy.da.UpdateCursor(perim_test, ["ACTIVITY", "activity_reclass"]) as cursor:
    for row in cursor:
        act = row[0]
        if act is None:
            continue
        new_val = activity_dict.get(act)
        if new_val:
            row[1] = new_val
            cursor.updateRow(row)
        else:
            print(f"Activity not found in dictionary: {act}")

# Delete EXCLUDE rows in one pass using a feature layer
print("Deleting excluded rows...")
arcpy.MakeFeatureLayer_management(perim_test, "to_delete", "activity_reclass = 'EXCLUDE'")
arcpy.DeleteRows_management("to_delete")
arcpy.Delete_management("to_delete")

# Export check table for review
arcpy.TableToTable_conversion(perim_test, outtables, "activities_reclass.csv")

# Reclassify METHOD attribute field
print("Reclassify by Method...")
with arcpy.da.UpdateCursor(perim_test, ["METHOD", "activity_reclass"], "activity_reclass = 'SKIP'") as cursor:
    for row in cursor:
        mthd = row[0]
        if mthd is None:
            continue
        new_val = method_dict.get(mthd)
        if new_val:
            row[1] = new_val
            cursor.updateRow(row)
        else:
            print(f"Activity not found in dictionary: {mthd}")

# Create a csv file of method classified activites and remaining 'SKIP' activities
arcpy.TableToTable_conversion(perim_test, outtables, "method_reclass.csv")

# Reclassify EQUIPMENT attribute field
print("Reclassify by Equipment...")
with arcpy.da.UpdateCursor(perim_test, ["EQUIPMENT", "activity_reclass"], "activity_reclass = 'SKIP'") as cursor:
    for row in cursor:
        equip = row[0]
        if equip is None:
            continue
        new_val = equipment_dict.get(equip)
        if new_val:
            row[1] = new_val
            cursor.updateRow(row)
        else:
            print(f"Activity not found in dictionary: {equip}")

# Create a csv file of method classified activites and remaining 'SKIP' activities
arcpy.TableToTable_conversion(perim_test, outtables, "equipment_reclass.csv")

print("Mechanical and Removal method cleanup reclassification")

# --- Post sweep cleanup and reclassification

# Only target features that are currently 'SKIP' and have METHOD filled
q1 = "activity_reclass = 'SKIP' AND METHOD IS NOT NULL"
with arcpy.da.UpdateCursor(perim_test, ["METHOD", "activity_reclass"], q1) as cursor:
    for method, act_reclass in cursor:
        if method in ("Mechanical", "Removal"):
            cursor.updateRow((method, method))
    del cursor

# Export for QC
final_reclass = os.path.join(outtables, "post_mechanical_reclass.csv")
arcpy.TableToTable_conversion(perim_test, outtables, "post_mechanical_reclass.csv")

# Start pandas code
print("Classifying remaining 'SKIPPED' activites by Activity majority classification")
df = pd.read_csv(final_reclass)
df = df[df['activity_reclass'] != 'SKIP']

# Compute the most common reclass per Activity
major_activity = (
    df.groupby("ACTIVITY")["activity_reclass"]
      .agg(lambda x: x.value_counts().index[0] if not x.value_counts().empty else None)  # most frequent label
      .reset_index()
)

majority_csv = os.path.join(outtables, "majority_reclass.csv")
major_activity.to_csv(majority_csv, index=False)

# Reclassify by majority activity
print("Applying majority-based reclassification")
majorityDict = {
    row[0]: row[1]
    for row in arcpy.da.SearchCursor(majority_csv, ["ACTIVITY", "activity_reclass"])
}

q2 = "activity_reclass = 'SKIP'"
with arcpy.da.UpdateCursor(perim_test, ["ACTIVITY", "activity_reclass"], q2) as cursor:
    for act, act_reclass in cursor:
        if act in majorityDict:
            cursor.updateRow((act, majorityDict[act]))
        # Skips None safely — no else needed
    del cursor

print("Create copy of classified FACTS perimeters")
arcpy.RepairGeometry_management(perim_test)
arcpy.CopyFeatures_management(perim_test, perim_reclass_output)

print("Completed! Run Time: %s\n\n" % (datetime.now() - dt))
