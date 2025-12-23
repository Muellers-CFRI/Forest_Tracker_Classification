
'''Series of update cursors to finalize FACTS'''

# Import packages
import arcpy
import datetime

# Import utilities
from scripts.utils.date_tools import get_comp_year
from scripts.utils.gis_tools import add_tracker_fields, delete_unnecessary_fields

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


# Create copy to final
arcpy.CopyFeatures_management(input_fc, output_fc)

# Add all forest tracker final fields
print("Adding Forest Tracker Fields...")
add_tracker_fields(output_fc)

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
        row[1] = get_comp_year(row[0])
        cursor.updateRow(row)

# Clean up
print("Deleting unnecessary fields...")
delete_unnecessary_fields(output_fc)

print(f"✅ USFS FACTS data compiled into Forest Tracker format! Runtime: {datetime.datetime.now() - dt}")
