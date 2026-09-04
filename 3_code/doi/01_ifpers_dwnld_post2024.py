# Import libraries
import os
import arcpy
from datetime import datetime
from arcgis.features import FeatureLayer

from utils.paths import get_gdb_path, RAW_GDB
from utils.gis_tools import add_fields_from_schema, ensure_nad83_utm13
from utils.date_tools import prep_date_fields, filter_by_year
from config.config import (IFPERS_URL, ifpers_processing_fields,
                           TRACKER_FIELDS, START_YEAR, END_YEAR)

arcpy.env.overwriteOutput = True
dt = datetime.now()
datetime_str = dt.strftime("%Y-%m-%d")

# Paths
staged_gdb = get_gdb_path("doi", "staged", "doi")
temp_download = os.path.join(RAW_GDB, "ifpers_temp_download")
final_fc = os.path.join(staged_gdb, "ifpers_perimeter_dwnld")

print("Downloading IFPERS Colorado actual treatments...")
layer = FeatureLayer(IFPERS_URL)
dwnld_clause = "State = 'Colorado' AND Class = 'Actual Treatment'"
sdf = layer.query(where=dwnld_clause, out_fields=ifpers_processing_fields).sdf

sdf.spatial.to_featureclass(
    location=temp_download,
    sanitize_columns=False,
    overwrite=True
)

# Add all target schema fields
add_fields_from_schema(temp_download, TRACKER_FIELDS)

# Carry through ID to SourceID
with arcpy.da.UpdateCursor(temp_download, ["ID", "SourceOID"]) as cursor:
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)

# Prep and Filter Dates
date_fields = ["CompletionDate", "InitiationDate"]
temp_date_filtered = "memory\\temp_filtered_ifpers"
prep_date_fields(temp_download, date_fields, min_year=START_YEAR)

filter_by_year(
    input_fc=temp_download,
    output_fc=temp_date_filtered,
    year_field="YEAR_COMP",
    start=START_YEAR,
    end=END_YEAR)

# Project to NAD 1983 UTM Zone 13 and save to on-disk STAGED geodatabase
ensure_nad83_utm13(temp_date_filtered, final_fc, target_wkid=26913)

# Clean up temp layers
print("Removing unneeded attributes...")
db_fields = {"OBJECTID", "FID", "Shape", "Shape_Length", "Shape_Area", "GLOBALID"}
fields_to_delete = [
    fld.name for fld in arcpy.ListFields(final_fc)
    if fld.name not in ifpers_processing_fields
    and fld.name not in db_fields
    and fld.name not in TRACKER_FIELDS
]

if fields_to_delete:
    arcpy.management.DeleteField(final_fc, fields_to_delete)

# Final complete RAM flush
print("\n=== Cleaning up in-memory workspace ===")
arcpy.management.Delete("memory")
print("✅ Complete! Run Time: %s" % (datetime.now() - dt))
