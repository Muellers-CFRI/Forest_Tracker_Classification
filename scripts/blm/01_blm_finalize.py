''' Series of update cursors to finalize BLM Vegetation Treatment Polygon '''

import arcpy
from datetime import datetime

arcpy.env.overwriteOutput = True
dt = datetime.now()
datetime_str = dt.strftime("%m/%d/%Y")

input_fc = r'E:\CFRI\FOREST_TRACKER\FEDERAL_DATA_CROSSWALK\BLM\WORKING\REVIEW_2024_DATA_UPDATE\output.gdb\classified_output_manual'
output_fc = r'E:\CFRI\FOREST_TRACKER\FEDERAL_DATA_CROSSWALK\BLM\FINAL_DATA\UPDATE_YEAR_2025\UPDATE_YEAR_2025.gdb\blm_final_2025'

# Add source OID to link input and output feature class
if "SourceOID" not in [f.name for f in arcpy.ListFields(input_fc)]:
    arcpy.AddField_management(input_fc, "SourceOID", "LONG")
with arcpy.da.UpdateCursor(input_fc, ["SourceOID", "OBJECTID"]) as cursor:
    for row in cursor:
        row[0] = row[1]
        cursor.updateRow(row)

# Create copy to final
arcpy.CopyFeatures_management(input_fc, output_fc)

final_fields = ["PRJ_NAME",
                "AGENCY",
                "AGENCY_C",
                "FUNDING",
                "LANDOWNER",
                "MGT_TYPE",
                "RXFIRE_MGT",
                "CANOPY_MGT",
                "SURF_MGT",
                "REFOREST",
                "TREE_COUNT",
                "SPECIES",
                "PRJ_OBJECT",
                "YEAR_COMP",
                "ACRES_GIS",
                "ACRES_MGT",
                "NOTES",
                "ORGFILE",
                "UPDATED",
                "MODIFY_BY",
                "SourceOID"]

# Update CALCULATE FIELDS
print("Updating static fields...")
constant_fields = {
    "AGENCY": "'Bureau of Land Management'",
    "AGENCY_C": "'BLM'",
    "ORGFILE": "'vtrt_cmplt_poly'",
    "MODIFY_BY": "'S E MUELLER'",
    "UPDATED": f"'{datetime_str}'"
}
for field, expression in constant_fields.items():
    arcpy.CalculateField_management(output_fc, field, expression, "PYTHON_9.3")

# Update PRJ_NAME, OBJECTIVE
print("Copying project names and comments...")
with arcpy.da.UpdateCursor(output_fc, ["TRTMNT_NM", "PRJ_NAME"]) as cursor:
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)

with arcpy.da.UpdateCursor(output_fc, ["TRTMNT_COMMENTS", "PRJ_OBJECT"]) as cursor:
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)

# UPDATE ACRES
print("Calculating acres...")
arcpy.CalculateField_management(output_fc, "ACRES_GIS", "!shape.area@acres!", "PYTHON_9.3", "")
with arcpy.da.UpdateCursor(output_fc, ["BLM_ACRES", "ACRES_MGT"]) as cursor:
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)

# Update Management
print("Classifying management types...")
activity_map = {
    "Broadcast Burn": (1, "FIRE"),
    "Pile Burn": (1, "FIRE"),
    "Manual": (2, "CANOPY"),
    "Mechanical": (2, "CANOPY"),
    "Mastication": (2, "CANOPY"),
    "Chemical": (2, "CANOPY"),
    "Removal": (3, "SURFACE"),
    "Lop and Scatter": (3, "SURFACE"),
    "Pile Fuels": (3, "SURFACE"),
    "Mulching": (3, "SURFACE"),
    "Plant Trees": (4, "REFOREST"),
    "Seed": (4, "REFOREST")
}

with arcpy.da.UpdateCursor(output_fc, ["Activity", "FIRE_MGT", "CANOPY_MGT", "SURF_MGT", "REFOREST", "MGT_TYPE"]
                           ) as cursor:
    for row in cursor:
        act = row[0]
        if act:
            act_norm = act.strip()
            if act_norm in activity_map:
                target_index, mgt_type = activity_map[act_norm]
                row[1:5] = ["", "", "", ""]
                row[target_index] = act_norm
                row[5] = mgt_type
                cursor.updateRow(row)

# Update YEAR_COMP
print("Updating completion year...")
with arcpy.da.UpdateCursor(output_fc, ["TRTMNT_START_DT", "TRTMNT_END_DT", "YEAR_COMP"]) as cursor:
    for row in cursor:
        start, end = row[0], row[1]
        if hasattr(end, "year") and end.year >= 2000:
            row[2] = end.year
        elif hasattr(start, "year"):
            row[2] = start.year
        cursor.updateRow(row)

print("Delete unnecessary fields")
keep_fields = set(final_fields)
db_fields = {"OBJECTID", "Shape", "Shape_Length", "Shape_Area"}
for fld in arcpy.ListFields(output_fc):
    if fld.name not in keep_fields and fld.name not in db_fields:
        try:
            arcpy.DeleteField_management(output_fc, fld.name)
        except Exception as e:
            print(f"{fld.name} not deleted.")

print("Finalization complete!")
