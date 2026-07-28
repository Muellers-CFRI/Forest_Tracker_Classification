"""
---------------------------------------------------------------------------
Title: USFS FACTS Data Schema Finalization

Purpose:
    Executes the final data-cleaning phase for the USFS pipeline. It enforces
    the master tracker database schema, translates raw completion timestamps
    into clean reporting calendar years, and applies a strict acreage-clamping
    safeguard to eliminate phantom accomplishments caused by overlapping spatial records.

Major Steps:
    1. Import the spatially flattened dataset and initialize the universal
       master tracker schema fields (`TRACKER_FIELDS`).
    2. Filter out records falling outside the official temporal project bounds
       (`START_YEAR` to `END_YEAR`) using strict UpdateCursor row deletion.
    3. Calculate permanent tracking variables, generating stable, non-shifting
       record identifiers (`SourceOID`) and standardized calendar year strings.
    4. Execute a critical geographic reality check on reported accomplishments:
        - Read the raw spatial geometry arrays (`SHAPE@AREA`) to calculate
          exact geographic acreage.
        - Evaluate reported treatment totals against physical dimensions.
        - Programmatically clamp the final recorded acreage (`ACRES_MGT`) to the
          smaller of the two values, preventing overlapping poly double-counting.
    5. Cleanse the attribute table by deleting all temporary processing
       and scaffolding columns, leaving a pristine master database output.

Inputs:
    usfs_flatten   – Footprint-flattened spatial feature class from Stage 3.
    TRACKER_FIELDS – Central master dictionary holding the required output schema.

Outputs:
    usfs_final     – Fully verified, schema-conformed, and footprint-clamped
                     feature class optimized for target dashboard visualization.
---------------------------------------------------------------------------
"""

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
