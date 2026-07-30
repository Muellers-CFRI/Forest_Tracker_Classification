"""
---------------------------------------------------------------------------
Title: USFS FACTS Data Automated Ingestion and Multi-Source Downloader

Purpose:
    Automates the sequential fetching, extraction, and standardization of
    multiple public USFS FACTS file geodatabase endpoints. Standardizes core
    spatial fields, clips to regional boundaries, dynamically cleans
    unreliable temporal values, and aggregates layers into a unified footprint.

Major Steps:
    1. Iterate through public zip-compressed agency download URLs in sequence.
    2. Extract zipped file geodatabases to disk, isolate the target feature classes,
       and stage records in the fast `memory\\` workspace.
    3. Filter out records outside the Colorado boundary (`STATE_ABBR = 'CO'`)
       early to shrink subsequent geographic processing volume by over 90%.
    4. Harmonize native agency attribute naming anomalies across distinct datasets
       into standard processing fields (`facts_processing_fields`).
    5. Compile isolated layers into a single merged dataset and enforce temporal
       boundary constraints (`START_YEAR` to `END_YEAR`).
    6. Ensure date consistency by programmatically populating empty execution
       dates (`DATE_COMPLETED`) with valid planning dates (`DATE_AWARDED`).
    7. Standardize spatial projections to EPSG:26913 (NAD83 UTM Zone 13N).
    8. Sanitize text fields containing invalid default values (e.g., placeholder
       NEPA labels), drop extraneous attribute metadata columns, and explode
       complex multi-part geometry combinations into distinct single-part records.

Inputs:
    FACTS_URLS              – Configuration dictionary holding specific remote zip endpoints.
    facts_processing_fields – Central metadata schema used to preserve core tracking variables.

Outputs:
    usfs_perimeter_dwnld    – Multi-source aggregated and geographically standardized feature
                              class saved to the intermediate staging database.
---------------------------------------------------------------------------
"""

# Import libraries
import os
import arcpy
import urllib.request
from datetime import datetime
from zipfile import ZipFile
from scripts.utils.paths import get_gdb_path, RAW_GDB, SCRATCH_DIR
from config.config import START_YEAR, END_YEAR, FACTS_URLS, facts_processing_fields

arcpy.env.overwriteOutput = True
dt = datetime.now()
datetime_str = dt.strftime("%Y-%m-%d")

# PATHS
staged_gdb = get_gdb_path("usfs", stage="staged", gdb_name="usfs")
final_fc = os.path.join(staged_gdb, "usfs_perimeter_dwnld")


def download_zip(url_addr, zip_path):
    """Download zip file from a url"""
    try:
        print(f"Downloading file from: {url_addr}")
        urllib.request.urlretrieve(url_addr, zip_path)
        return True
    except Exception as e:
        print(f"Could not retrieve file from: {url_addr}\n{e}")
        return False


def unzip_extract_fgdb(zip_path, scratch_folder, unique_name):
    """unzip file, extract FGDB + feature class, return path"""
    try:
        print(f"...UnZipping file:      {os.path.basename(zip_path)}")
        with ZipFile(zip_path) as zip_ref:
            file_list = zip_ref.namelist()
            zip_ref.extractall(scratch_folder)

        fgdb_path = os.path.join(scratch_folder, os.path.dirname(file_list[0]))
        print(f"Extracted geodatabase {fgdb_path}")

        arcpy.env.workspace = fgdb_path
        fc_list = arcpy.ListFeatureClasses()
        if not fc_list:
            raise ValueError(f"No feature classes found in {fgdb_path}")

        fc_path = os.path.join(fgdb_path, fc_list[0])
        memory_fc = f"memory\\{unique_name}_extracted"
        arcpy.conversion.FeatureClassToFeatureClass(fc_path, "memory", f"{unique_name}_extracted")

        return memory_fc

    except Exception as e:
        print(f"Could not unzip or extract feature class: {e}")
        return None


def clip_to_colorado(facts_fc, unique_name):
    """Clip data to Colorado extent and copy to final output"""
    try:
        print("...Clipping to Colorado extent.")
        memory_clip = f"memory\\{unique_name}_CO"

        arcpy.management.MakeFeatureLayer(facts_fc, "facts_fc_lyr", "STATE_ABBR = 'CO'")
        arcpy.management.CopyFeatures("facts_fc_lyr", memory_clip)
        arcpy.management.Delete("facts_fc_lyr")
        return memory_clip

    except:
        print(f"No Colorado data found or clipping failed.")
        return None


def standardize_fields(facts_fc, url, datetime_str):
    rename_map = {
        "AU_NAME": "TREATMENT_NAME",
        "SUBUNIT_NAME": "TREATMENT_NAME",
        "ACTIVITY_NAME": "ACTIVITY",
        "FUND_CODES": "FUND_CODE",
        "METHOD_DESC": "METHOD",
        "EQUIPMENT_DESC": "EQUIPMENT"
    }

    # Rename fields if they exist
    for old, new in rename_map.items():
        try:
            arcpy.management.AlterField(facts_fc, old, new, new)
            print(f"Renamed {old} -> {new}")
        except:
            pass

    # Add file/date field
    arcpy.management.AddField(facts_fc, "fileNmDate", "TEXT", field_length=50)
    val = f"{os.path.basename(url)[:-4]} {datetime_str}"
    arcpy.management.CalculateField(facts_fc, "fileNmDate", f"'{val}'", "PYTHON3")


# ----- START SCRIPT -----
merge_list = []

for name, url in FACTS_URLS.items():
    print(f" Processing FACTS data: {name}")
    zip_temp = os.path.join(SCRATCH_DIR, "TEMP_ZIP.zip")

    # Download + unzip
    if not download_zip(url, zip_temp):
        continue

    facts_fc = unzip_extract_fgdb(zip_temp, SCRATCH_DIR, unique_name=name)
    if not facts_fc:
        continue

    # Clip, repair, and clean fields
    colorado_fc = clip_to_colorado(facts_fc, unique_name=name)
    arcpy.management.Delete(facts_fc)
    if not colorado_fc or int(arcpy.management.GetCount(colorado_fc)[0]) == 0:
        print(f"No records found for {name} in Colorado. Skipping.")
        if colorado_fc:
            arcpy.management.Delete(colorado_fc)
        continue

    arcpy.management.RepairGeometry(colorado_fc, "DELETE_NULL")
    standardize_fields(colorado_fc, url, datetime_str=datetime_str)
    merge_list.append(colorado_fc)

    raw_archive_path = os.path.join(RAW_GDB, f"FACTS_{name}")
    print(f"Archiving raw national dataset to: {raw_archive_path}")
    arcpy.management.CopyFeatures(colorado_fc, raw_archive_path)

    if os.path.exists(zip_temp):
        os.remove(zip_temp)

print("\nMerging all processed perimeters...")
merged_fc = arcpy.management.Merge(merge_list, "memory\\merged_perimeters")

for mem_fc in merge_list:
    arcpy.management.Delete(mem_fc)

# Preprocess merged perimters
print("Preprocessing FACTS Perimeter Feature Class")
print("Subsetting perimeters based on user selected time frame")

dt_start = f"{START_YEAR}-01-01 00:00:00"
dt_end = f"{END_YEAR}-12-31 23:59:59"

where_clause = (
    f"(DATE_COMPLETED BETWEEN timestamp '{dt_start}' AND timestamp '{dt_end}') "
    f"OR "
    f"(DATE_AWARDED BETWEEN timestamp '{dt_start}' AND timestamp '{dt_end}')"
)

arcpy.management.MakeFeatureLayer(merged_fc, "date_subset_lyr", where_clause)
tmp_copy = arcpy.management.CopyFeatures("date_subset_lyr", "memory\\tmp_copy_date")
arcpy.management.Delete("date_subset_lyr")
arcpy.management.Delete(merged_fc)

# Update DATE_COMPLETED with DATE_AWARDED if empty
with arcpy.da.UpdateCursor(tmp_copy, ["DATE_COMPLETED", "DATE_AWARDED"]) as cursor:
    for row in cursor:
        if row[0] is None or str(row[0]).strip() == " ":
            row[0] = row[1]
            cursor.updateRow(row)

# Project to NAD 1983 UTM Zone 13 and save to on-disk STAGED geodatabase
desc = arcpy.Describe(tmp_copy)
spatialRef = desc.spatialReference

# Define the target UTM 13N Spatial Reference Object using its EPSG code (26913)
coordSystemNAD = arcpy.SpatialReference(26913)

if spatialRef.Name == "NAD 1983":
    print("Spatial reference is already NAD 1983 — copying directly to final staged feature class.")
    arcpy.management.CopyFeatures(tmp_copy, final_fc)
else:
    print("Reprojecting to NAD83 UTM Zone 13N via Environment Settings...")
    # Set the environment projection to UTM Zone 13N
    with arcpy.EnvManager(outputCoordinateSystem=coordSystemNAD):
        # CopyFeatures will automatically project the data on-the-fly!
        arcpy.management.CopyFeatures(tmp_copy, final_fc)

arcpy.management.Delete(tmp_copy)

# Clean up NEPA_DOC_NAME attribute
print("Cleaning NEPA_DOC_NAME values...")
invalid_nepa = {
    "DEFAULT FOR NOT REQUIRED",
    "CE without DM",
    "DECISION NOTICE AND FINDING OF NO SIGNIFICANT IMPACT",
    "NEPA Pending"
}
with arcpy.da.UpdateCursor(final_fc, ["NEPA_DOC_NAME"]) as cursor:
    for row in cursor:
        val = row[0]
        if val is None or str(val).strip() == "" or val in invalid_nepa:
            row[0] = None
        else:
            if str(val).startswith("(PALS)"):
                row[0] = str(val).replace("(PALS)", "").strip()
        cursor.updateRow(row)

# Cleanup
print("Removing unneeded attributes...")
db_fields = {"OBJECTID", "FID", "Shape", "Shape_Length", "Shape_Area", "GLOBALID"}
fields_to_delete = [
    fld.name for fld in arcpy.ListFields(final_fc)
    if fld.name not in facts_processing_fields and fld.name not in db_fields
]

if fields_to_delete:
    arcpy.management.DeleteField(final_fc, fields_to_delete)

print("Expliding multi-part geometries into distinct single-part records...")
temp_singlepart = "memory\\exploded_perimeters"
arcpy.management.MultipartToSinglepart(final_fc, temp_singlepart)
arcpy.management.RepairGeometry(temp_singlepart, "DELETE_NULL")

arcpy.management.Delete(final_fc)
arcpy.management.CopyFeatures(temp_singlepart, final_fc)

# Final complete RAM flush
print("\n=== Cleaning up in-memory workspace ===")
arcpy.management.Delete("memory")
print("✅ Complete! Run Time: %s" % (datetime.now() - dt))
