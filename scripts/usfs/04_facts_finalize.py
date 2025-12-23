'''Series of update cursors to finalize FACTS'''

import arcpy
import datetime

arcpy.env.overwriteOutput = True
dt = datetime.datetime.now()
datetime_str = dt.strftime("%m/%d/%Y")

input_fc = r"E:\CFRI\FOREST_TRACKER\FEDERAL_DATA_CROSSWALK\USFS_FACTS\SCRATCH\scratch.gdb\perim_flatten"
output_fc = r"E:\CFRI\FOREST_TRACKER\FEDERAL_DATA_CROSSWALK\USFS_FACTS\OUTPUT\Output.gdb\FACTS_final_2025"


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
    "FUND_SOURCE": "TEXT", "FUND_TYPE": "TEXT", "LANDOWNER": "TEXT",
    "MGT_TYPE": "TEXT", "RXFIRE_MGT": "TEXT", "CANOPY_MGT": "TEXT", "SURF_MGT": "TEXT",
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
    "AGENCY": "'US Forest Service'",
    "AGENCY_C": "'USFS'",
    "FUND_TYPE": "'Federal'",
    "MODIFY_BY": "'S E MUELLER'",
    "UPDATED": f"datetime.datetime.strptime('{datetime_str}', '%m/%d/%Y')"
}
for field, expression in constant_fields.items():
    arcpy.CalculateField_management(output_fc, field, expression, "PYTHON_9.3")

arcpy.CalculateField_management(output_fc, "ORGFILE", "!fileNmDate!", "PYTHON3")

# Update PRJ_NAME
with arcpy.da.UpdateCursor(output_fc, ["TREATMENT_NAME", "PRJ_NAME"]) as cursor:
    for row in cursor:
        treatment = row[0]
        if treatment and treatment.lower() != "none":
            new_val = remove_duplicate_list(treatment)
            row[1] = new_val
        else:
            row[1] = "None"
        cursor.updateRow(row)

# Update PRJ_OBJECT
with arcpy.da.UpdateCursor(output_fc, ["ACTIVITY", "PRJ_OBJECT"]) as cursor:
    for row in cursor:
        val = row[0]
        new_val = remove_duplicate_list(val)
        row[1] = new_val
        cursor.updateRow(row)

# Update FUNDING
with arcpy.da.UpdateCursor(output_fc, ["funding_update", "FUND_SOURCE"]) as cursor:
    for row in cursor:
        val = row[0]
        new_val = remove_duplicate_list(val)
        row[1] = new_val
        cursor.updateRow(row)

# Update ACRES_GIS
print("Calculating acres...")
arcpy.CalculateField_management(output_fc, "ACRES_GIS", "!shape.area@acres!", "PYTHON_9.3", "")

# Update ACRES_MGT
with arcpy.da.UpdateCursor(output_fc, ["NBR_UNITS_ACCOMPLISHED", "ACRES_GIS", "ACRES_MGT"]) as cursor:
    for row in cursor:
        units, gis, _ = row
        if units is None or units == 0:  # if NBR units equals 0, use GIS acres
            row[2] = gis
        elif units < gis:                # if NBR units not 0 and less than GIS acres, use NBR Units
            row[2] = units
        else:                            # else (if NBR units greater than managed acres), use GIS acres
            row[2] = gis
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

with arcpy.da.UpdateCursor(output_fc, ["activity_reclass", "FIRE_MGT", "CANOPY_MGT", "SURF_MGT", "REFOREST", "MGT_TYPE"]
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
with arcpy.da.UpdateCursor(output_fc, ["DATE_COMPLETED", "YEAR_COMP"]) as cursor:
    for row in cursor:
        dt = row[0]
        if hasattr(dt, "year") and dt.year >= 2000:
            row[1] = dt.year
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

print(f"✅ USFS FACTS data compiled into Forest Tracker format! Runtime: {datetime.datetime.now() - dt}")
