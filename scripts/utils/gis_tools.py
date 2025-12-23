import arcpy
from config.config import TRACKER_FIELDS


def add_tracker_fields(input_fc):
    """Adds all fields defined in the master TRACKER_FIELDS config."""
    existing_fields = [f.name.uupper() for f in arcpy.ListFields(input_fc)]

    for field_name, field_type in TRACKER_FIELDS.items():
        if field_name.upper() not in existing_fields:
            print(f"Adding field: {field_name} ({field_type})")
            arcpy.AddField_management(input_fc, field_name, field_type)
        else:
            print(f"Field {field_name} already exists.")


def delete_unnecessary_fields(input_fc):
    """Clean up unnecessary and extraneous fields from output"""
    # System fields that cannot be deleted
    db_fields = {"OBJECTID", "Shape", "Shape_Length", "Shape_Area", "FID", "GEOMETRY"}

    keep_set = {f.upper() for f in TRACKER_FIELDS.keys()} | db_fields

    all_fields = arcpy.ListFields(input_fc)
    to_delete = [f.name for f in all_fields if f.name.upper() not in keep_set]

    if to_delete:
        arcpy.DeleteField_management(input_fc, to_delete)

