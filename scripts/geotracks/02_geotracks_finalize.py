'''Series of update cursors to finalize FACTS'''

import arcpy
import datetime

# Import utils
from scripts.utils.date_tools import get_comp_year

arcpy.env.overwriteOutput = True
dt = datetime.datetime.now()
datetime_str = dt.strftime("%m/%d/%Y")

input_fc = r"E:\CFRI\FOREST_TRACKER\LOCAL_DATA\CFTv2_Data_Handoff\scratch.gdb\perim_flatten"
output_fc = r"E:\CFRI\FOREST_TRACKER\LOCAL_DATA\CFTv2_Data_Handoff\CFTv2_Data_Handoff.gdb\CFTv2_CSFS_GeoTracks_classified_v2"


def remove_duplicate_list(value):
    """Remove duplicate and 'None' entries from a semicolon-separated strings."""
    if not value:
        return None

    vals = [v.strip() for v in str(value).split("; ") if v.strip()]
    seen = set()
    deduped = []
    for v in vals:
        if v not in seen and v.lower() != "none":
            seen.add(v)
            deduped.append(v)

    return ', '.join(deduped) if deduped else None


tracker_fields = {
    "PRJ_NAME": "TEXT", "AGENCY": "TEXT", "AGENCY_C": "TEXT",
    "FUNDING": "TEXT", "LANDOWNER": "TEXT", "MGT_TYPE": "TEXT",
    "FIRE_MGT": "TEXT", "CANOPY_MGT": "TEXT", "SURF_MGT": "TEXT",
    "REFOREST": "TEXT", "TREE_COUNT": "LONG", "SPECIES": "TEXT",
    "PRJ_OBJECT": "TEXT", "YEAR_COMP": "LONG", "ACRES_GIS":"DOUBLE",
    "ACRES_MGT": "DOUBLE", "NOTES": "TEXT", "ORGFILE": "TEXT",
    "UPDATED": "DATE", "MODIFY_BY": "TEXT", "SourceOID": "LONG"
}

# Create copy to final
arcpy.CopyFeatures_management(input_fc, output_fc)

# Add all forest tracker final fields
print("Adding Forest Tracker Fields...")
existing_fields = [f.name for f in arcpy.ListFields(output_fc)]
for field_name, field_type in tracker_fields.items():
    if field_name not in existing_fields:
        arcpy.AddField_management(output_fc, field_name, field_type)

# Add source OID to link input and output feature class
with arcpy.da.UpdateCursor(output_fc, ["SourceOID", "OBJECTID"]) as cursor:
    for row in cursor:
        row[0] = row[1]
        cursor.updateRow(row)

# Update CALCULATE FIELDS
print("Updating static fields...")
constant_fields = {
    "AGENCY": "'Colorado State Forest Service'",
    "AGENCY_C": "'CSFS'",
    "MODIFY_BY": "'S E MUELLER'",
    "UPDATED": f"datetime.datetime.strptime('{datetime_str}', '%m/%d/%Y')"
}
for field, expression in constant_fields.items():
    arcpy.CalculateField_management(output_fc, field, expression, "PYTHON_9.3")

# Update PRJ_NAME
arcpy.CalculateField_management(output_fc, "PRJ_NAME", "!NAME_REDACT!", "PYTHON3")

# Update PRJ_OBJECT
max_len = [f.length for f in arcpy.ListFields(output_fc, "PRJ_OBJECT")][0]
with arcpy.da.UpdateCursor(output_fc, ["DESCRIPTION_REDACT", "COMMENT_REDACT", "PRJ_OBJECT"]) as cursor:
    for row in cursor:
        desc = row[0] or ""
        comm = row[1] or ""
        combined = f"{desc}; {comm}".strip("; ").strip()

        new_val = remove_duplicate_list(combined)
        if new_val:
            # truncate to field length
            row[2] = new_val[:max_len]
        else:
            row[2] = None
        cursor.updateRow(row)

# Update FUNDING
with arcpy.da.UpdateCursor(output_fc, ["FUNDING_SO", "FUNDING"]) as cursor:
    for row in cursor:
        val = row[0]
        new_val = remove_duplicate_list(val)
        row[1] = new_val
        cursor.updateRow(row)

# Update ACRES_GIS
print("Calculating acres...")
arcpy.CalculateField_management(output_fc, "ACRES_GIS", "!shape.area@acres!", "PYTHON_9.3", "")

# Update ACRES_MGT
with arcpy.da.UpdateCursor(output_fc, ["UNIT_OF_ME", "COMPLETED_", "ACRES_GIS", "ACRES_MGT"]) as cursor:
    for row in cursor:
        units, acre, gis, _ = row
        if units and units.lower() == "acres" and acre not in (None, 0):
            if acre <= gis:
                row[3] = acre
            else:
                row[3] = gis
        else:
            row[3] = gis
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

with arcpy.da.UpdateCursor(output_fc, ["ActClass", "RXFIRE_MGT", "CANOPY_MGT", "SURF_MGT", "REFOREST", "MGT_TYPE"]
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
            else:
                print(f"Unrecognized activity: {act_norm}")

# Update YEAR_COMP
print("Updating completion year...")
with arcpy.da.UpdateCursor(output_fc, ["COMPLETED1", "YEAR_COMP", "ORGFILE"]) as cursor:
    for row in cursor:
        row[1] = get_comp_year(row[0])
        row[2] = f"GEOTRACKS_{row[1]}_Completed_ForestManagementTreatment"
        cursor.updateRow(row)

# Clean up
print("Deleting unnecessary fields...")
keep_fields = list(tracker_fields.keys())
db_fields = {"OBJECTID", "Shape", "Shape_Length", "Shape_Area"}
for fld in arcpy.ListFields(output_fc):
    if fld.name not in keep_fields and fld.name not in db_fields:
        try:
            arcpy.DeleteField_management(output_fc, fld.name)
        except Exception as e:
            print(f"{fld.name} not deleted.")

print(f"✅ GEOTRACKS data compiled into Forest Tracker format!")
