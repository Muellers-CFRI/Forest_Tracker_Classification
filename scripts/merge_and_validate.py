import os
import re
import arcpy
import pandas as pd

# Environmental settings
arcpy.env.overwriteOutput = True
arcpy.env.qualifiedFieldNames = False

compile_folder = r'E:\CFRI\FOREST_TRACKER\ALL_DATA_COMPILE'
compile_gdb = os.path.join(compile_folder, 'DATA_to_COMPILE.gdb')
out_gdb = os.path.join(compile_folder, "CFTv2.gdb")
arcpy.env.workspace = compile_gdb

# Input data
coMap = os.path.join(compile_folder, "LANDOWNER_MAJORITY", "INPUT", "COMaP-v8_final_public", "COMaP-v8_final_public.shp")
funding_csv = os.path.join(compile_folder, 'funding_update.csv')
funding_df = pd.read_csv(funding_csv, encoding="latin1")

# Outputs
out_merge = os.path.join(out_gdb, 'CFTv2_merge')
out_final = os.path.join(out_gdb, 'CFTv2_all_data_compile')

# Final Fields
tracker_fields = {
    "PRJ_NAME": "TEXT", "AGENCY": "TEXT", "AGENCY_C": "TEXT",
    "FUND_SOURCE": "TEXT", "FUND_TYPE": "TEXT", "PARTNERS": "TEXT",
    "LANDOWNER": "TEXT", "MGT_TYPE": "TEXT", "ACTIVITY": "TEXT",
    "TREE_COUNT": "LONG", "SPECIES": "TEXT", "PRJ_OBJECT": "TEXT",
    "YEAR_COMP": "LONG", "ACRES_GIS": "DOUBLE", "ACRES_MGT": "DOUBLE",
    "NOTES": "TEXT", "ORGFILE": "TEXT", "UPDATED": "DATE", "MODIFY_BY": "TEXT"
}

# Final activities
activities = [
    "Broadcast Burn", "Pile Burn",
    "Manual", "Mechanical", "Mastication", "Chemical",
    "Removal", "Lop and Scatter", "Pile Fuels", "Mulching",
    "Plant Trees", "Seed"]


def standardize_fields(fc):
    rename_map = {
        "FIRE_MGT": "RXFIRE_MGT",
        "REFOREST": "REFOR_MGT",
    }

    # Rename fields if they exist
    for old, new in rename_map.items():
        try:
            arcpy.AlterField_management(fc, old, new, new)
            print(f"Renamed {old} -> {new}")
        except:
            pass


print("-------------------------------------------------------")
print("  Forest Tracker Compilation - Majority Landowner Pass")
print("-------------------------------------------------------\n")

# ---------------------------------------------------------------------------
# MERGE ALL INPUT LAYERS
# ---------------------------------------------------------------------------
print("Merging all feature classes in the compile GDB...")
data_list = arcpy.ListFeatureClasses()
for lyr in data_list:
    full_fc = os.path.join(arcpy.env.workspace, lyr)
    standardize_fields(full_fc)
out_merge = os.path.join(out_gdb, 'CFTv2_merge')
compiled_data = arcpy.Merge_management(data_list, out_merge)

arcpy.RepairGeometry_management(compiled_data)

# ---------------------------------------------------------------------------
# Update LANDOWNER field
# ---------------------------------------------------------------------------

# Add and calculate an original ID field if not already present and error flag field
print("Calculating an original ID field")
existing_fields = [f.name for f in arcpy.ListFields(compiled_data)]
error_flag = "ERROR_FLAG"

if "ORGID" not in existing_fields:
    arcpy.AddField_management(compiled_data, "ORGID", "LONG")
    arcpy.CalculateField_management(compiled_data, "ORGID", "!OBJECTID! + 1", "PYTHON_9.3", )

if error_flag not in existing_fields:
    arcpy.AddField_management(compiled_data, error_flag, "TEXT")

# Delete any version of 'ACTIVITY' in merged data
activity_fld = "ACTIVITY"
activity_actual = None
for f in arcpy.ListFields(compiled_data):
    if f.name.lower() == activity_fld.lower():
        activity_actual = f.name
        print(activity_actual)
        break
if activity_actual:
    arcpy.DeleteField_management(compiled_data, activity_fld)

# Intersect and dissolve management data with coMap
print("Intersecting with COMaP to determine majority landowner...")
lo_intersect = "in_memory/intersect"
arcpy.Intersect_analysis([compiled_data, coMap], lo_intersect)

# Add and calculate acreage field
owner_fld = "FT_LABEL"
arcpy.AddField_management(lo_intersect, "NEWACRES", "DOUBLE")
arcpy.CalculateField_management(lo_intersect, "NEWACRES", "!shape.area@acres!", "PYTHON_9.3")

stats_table = "in_memory/stats"
arcpy.Statistics_analysis(lo_intersect,
                          stats_table,
                          [["NEWACRES", "SUM"]],
                          ["ORGID", owner_fld])

# Convert to Pandas DataFrame and process majority landowner
print("Computing majority landowner using Pandas...")
table_data = arcpy.da.TableToNumPyArray(stats_table, ("ORGID", owner_fld, "SUM_NEWACRES"))
df = pd.DataFrame(table_data)

majority_landowners = df.loc[df.groupby("ORGID")["SUM_NEWACRES"].idxmax()]
landownerDict = dict(zip(majority_landowners["ORGID"], majority_landowners[owner_fld]))

# Update LANDOWNER field
if "LANDOWNER" not in existing_fields:
    arcpy.AddField_management(compiled_data, "LANDOWNER", "TEXT", field_length=100)

with arcpy.da.UpdateCursor(compiled_data, ["ORGID", "LANDOWNER"]) as cursor:
    for orgid, _ in cursor:
        if orgid in landownerDict:
            cursor.updateRow((orgid, landownerDict[orgid]))

# Clean up
print("Cleaning up temporary files...")
arcpy.DeleteField_management(compiled_data, "ORGID")

# ---------------------------------------------------------------------------
# Update MANAGEMENT fields
# ---------------------------------------------------------------------------
print("-------------------------------------------------------")
print("  Forest Tracker Compilation - Management Fields")
print("-------------------------------------------------------\n")

with arcpy.da.UpdateCursor(compiled_data, ["MGT_TYPE", error_flag]) as cursor:
    for row in cursor:
        if not row[0]:
            row[1] = "NO MGT_TYPE"

        val = row[0].lower().replace(" ", "")

        if "canopy" in val:
            row[0] = "Mechanical and Hand Equipment"
        elif "surface" in val:
            row[0] = "Mechanical and Hand Equipment"
        elif "reforest" in val:
            row[0] = "Reforestation"
        elif "rxfire" in val or "prescribed" in val or 'fire' in val:
            row[0] = "Prescribed Fire"
        cursor.updateRow(row)

# Update new ACTIVITY field
arcpy.AddField_management(compiled_data, "ACTIVITY", "TEXT")
fields = ["CANOPY_MGT", "SURF_MGT", "RXFIRE_MGT", "REFOR_MGT", "ACTIVITY", error_flag]
with arcpy.da.UpdateCursor(compiled_data, fields) as cursor:
    for row in cursor:
        canopy, surf, rxfire, reforest, activity, error = row
        # Clean them and get list of non-empty values
        vals_raw = [canopy, surf, rxfire, reforest]
        vals_clean = [v.strip() for v in vals_raw if v not in (None, "", " ")]

        if len(vals_clean) == 0:
            row[4] = ""
            row[5] = "ACTIVITY ERROR"
        elif len(vals_clean) > 1:
            row[4] = ""
            row[5] = "ACTIVITY ERROR"
        else:
            single = vals_clean[0]
            if single not in activities:
                row[4] = vals_clean[0]
                row[5] = "ACTIVITY ERROR"
            else:
                row[4] = vals_clean[0]

        cursor.updateRow(row)

# ---------------------------------------------------------------------------
# Clean up Funding
# ---------------------------------------------------------------------------
print("-------------------------------------------------------")
print("  Forest Tracker Compilation - Funding Update")
print("-------------------------------------------------------\n")

# Build dictionary: fund_code → (fund_source, fund_type)
funding_df = funding_df.fillna("Unknown")
funding_dict = {
    code: (source, ftype)
    for code, source, ftype in zip(
        funding_df.fund_code,
        funding_df.fund_source,
        funding_df.type
    )
}

with arcpy.da.UpdateCursor(compiled_data, ["FUNDING", "FUND_SOURCE", "FUND_TYPE", error_flag]) as cursor:

    for row in cursor:
        raw = row[0]   # FUNDING text

        # -------------------------
        # Case 1: FUNDING is blank
        # -------------------------
        if not raw or raw.strip() == "":
            row[1] = "Unknown"    # FUND_SOURCE
            row[2] = "Unknown"    # FUND_TYPE
            cursor.updateRow(row)
            continue

        # -------------------------
        # Split on comma or slash
        # -------------------------
        items = [x.strip() for x in re.split(r"[,/]", raw) if x.strip()]

        sources = []
        types = []

        # -------------------------
        # Look up codes in dict
        # -------------------------
        for item in items:
            if item in funding_dict:
                src, typ = funding_dict[item]
            else:
                src, typ = "Unknown", "Unknown"
                row[3] = "FUND_FLAG"   # Set error flag

            sources.append(src)
            types.append(typ)

        # -------------------------
        # Remove duplicates (ordered)
        # -------------------------
        row[1] = ", ".join(dict.fromkeys(sources))  # FUND_SOURCE
        row[2] = ", ".join(dict.fromkeys(types))    # FUND_TYPE

        if "Unknown" in row[1] or "Unknown" in row[2]:
            row[3] = "FUND_FLAG"

        cursor.updateRow(row)

# ---------------------------------------------------------------------------
# Clean up fields and final
# ---------------------------------------------------------------------------
print("-------------------------------------------------------")
print("  Forest Tracker Compilation - Final Cleanup")
print("-------------------------------------------------------\n")

text_fields = [f.name for f in arcpy.ListFields(compiled_data)
               if f.type == "String" and f.editable]

# Replace NULL with empty string in all text fields
with arcpy.da.UpdateCursor(compiled_data, text_fields) as cursor:
    for row in cursor:
        updated = False
        for i, val in enumerate(row):
            if val is None:          # NULL detected
                row[i] = ""          # replace with empty string
                updated = True
        if updated:
            cursor.updateRow(row)

# Check that data falls between 2000 and 2024
with arcpy.da.UpdateCursor(compiled_data, ["YEAR_COMP", error_flag]) as cursor:
    for row in cursor:
        if row[0] < 2000 or row[0] > 2024:
            row[1] = "YEAR FLAG"

# Rerun ACRES_GIS
print("Calculating acres...")
arcpy.CalculateField_management(compiled_data, "ACRES_GIS", "!shape.area@acres!", "PYTHON_9.3", "")

# ---------------------------------------------------------------------------
# Create a final copy with fields in correct order
# ---------------------------------------------------------------------------
print("Create Final Copy with field order")
desc = arcpy.Describe(compiled_data)
geom_type = desc.shapeType
spatial_ref = desc.spatialReference

arcpy.CreateFeatureclass_management(
    out_path=os.path.dirname(out_final),
    out_name=os.path.basename(out_final),
    geometry_type=geom_type,
    spatial_reference=spatial_ref
)

for field_name, field_type in tracker_fields.items():
    arcpy.AddField_management(out_final, field_name, field_type)

src_fields = ["SHAPE@"] + list(tracker_fields.keys())
dst_fields = src_fields[:]

with arcpy.da.SearchCursor(compiled_data, src_fields) as src_cursor, \
        arcpy.da.InsertCursor(out_final, dst_fields) as dst_cursor:

    for row in src_cursor:
        dst_cursor.insertRow(row)

print("Process completed successfully. Final output saved at: ", out_final)
