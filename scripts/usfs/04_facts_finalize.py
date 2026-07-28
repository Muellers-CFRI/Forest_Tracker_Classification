import arcpy
import os
from datetime import datetime
from scripts.utils.paths import get_gdb_path
from config.config import START_YEAR, END_YEAR, TRACKER_FIELDS
from scripts.utils.date_tools import get_comp_year
from scripts.utils.gis_tools import (add_fields_from_schema,
                                     delete_unnecessary_fields,
                                     finalize_tracker_data)

arcpy.env.overwriteOutput = True
dt = datetime.now()
datetime_str = dt.strftime("%Y-%m-%d")


def run_facts():
    """Run FACTS finalize script"""
    print("--- FACTS Finalize Data ---")

    staged_gdb = get_gdb_path(agency="usfs", stage="staged", gdb_name="usfs")
    input_fc = os.path.join(staged_gdb, "usfs_flatten")
    output_fc = os.path.join(staged_gdb, "usfs_final")

    print("Copying raw data to processing environment...")
    arcpy.management.CopyFeatures(input_fc, output_fc)

    add_fields_from_schema(output_fc, TRACKER_FIELDS)

    print(f"Applying temporal filter from config: {START_YEAR} to {END_YEAR}")
    print("Stamping SourceOID and calculating completion years, and filtering dates...")
    with (arcpy.da.UpdateCursor(output_fc, ["DATE_COMPLETED"]) as cursor):
        for row in cursor:
            comp_year = get_comp_year(row[0], min_year=START_YEAR)
            if comp_year is None or comp_year < START_YEAR or comp_year > END_YEAR:
                cursor.deleteRow()

    print("Stamping permanent SourceOIDs and calculating completion tracker dates...")
    with arcpy.da.UpdateCursor(output_fc, ["SourceOID", "OBJECTID", "DATE_COMPLETED", "YEAR_COMP", "DATE_COMP"]) as cursor:
        for row in cursor:
            row[0] = row[1]
            row[3] = get_comp_year(row[2], min_year=START_YEAR)
            row[4] = row[2]
            cursor.updateRow(row)

    finalize_tracker_data(output_fc, agency_key="usfs")

    # Calculate management acres separately
    with arcpy.da.UpdateCursor(output_fc, ["NBR_UNITS_ACCOMPLISHED", "SHAPE@AREA", "ACRES_MGT"]) as cursor:
        for row in cursor:
            units, sq_meters, _ = row
            gis_acres = (sq_meters or 0) * 0.000247105
            if units is None or units == 0:  # if NBR units equals 0, use GIS acres
                row[2] = gis_acres
            elif units < gis_acres:          # if NBR units not 0 and less than GIS acres, use NBR Units
                row[2] = units
            else:                            # else (if NBR units greater than managed acres), use GIS acres
                row[2] = gis_acres
            cursor.updateRow(row)

    # Updated Date
    with arcpy.da.UpdateCursor(output_fc, ["UPDATED"]) as cursor:
        for row in cursor:
            row[0] = datetime_str
            cursor.updateRow(row)

    delete_unnecessary_fields(output_fc, TRACKER_FIELDS)

    print("USFS COMPLETE. Data is ready for final merge.")


run_facts()
