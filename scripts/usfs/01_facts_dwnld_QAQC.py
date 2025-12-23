# Import libraries
import os
import arcpy
import urllib.request
from datetime import datetime
from zipfile import ZipFile

# ----- CONFIG -----
arcpy.env.overwriteOutput = True

# base workspace
base_fldr = 'E:/CFRI/FOREST_TRACKER/FEDERAL_DATA_CROSSWALK/USFS_FACTS'
arcpy.env.workspace = base_fldr

# PC Directory
out_fldr = os.path.join(base_fldr, "OUTPUT")
scratchFolder = os.path.join(base_fldr, "SCRATCH")
scratch_gdb = os.path.join(scratchFolder, "scratch.gdb")
final_fc = os.path.join(out_fldr, "raw_data_copy.gdb/perimeter_FACTS")

# date filtering
dt = datetime.now()
datetime_str = dt.strftime("%Y-%m-%d")
dt_start = '2000-01-01'  # START DATE for filter
dt_end = '2024-12-31'  # END DATE for filter

# FACTS source URLs
URLS = {
    "HazFuelTrt": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_HazFuelTrt_PL.gdb.zip",
    "SilvReforestation": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_SilvReforest.gdb.zip",
    "BrushDisposal": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_BrushDisposal.gdb.zip",
    "CFLRP": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_CFLRP_PL.gdb.zip",
    "IRR": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_IRR_PL.gdb.zip",
    "KnutsonVandenberg": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_KnutsonVandenberg.gdb.zip",
    "SilvTSI": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_SilvTSI.gdb.zip",
    "StwrdshpCntrctng": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_StwrdshpCntrctng_PL.gdb.zip",
    "TimberHarvest": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_TimberHarvest.gdb.zip",
    "WBBS": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_WBBS_PL.gdb.zip",
}

# fields to keep at the end
keep_fields = [
    "NEPA_DOC_NAME",
    "TREATMENT_NAME",
    "ACTIVITY",
    "METHOD",
    "EQUIPMENT",
    "DATE_COMPLETED",
    "FUND_CODE",
    "NBR_UNITS_ACCOMPLISHED",
    "fileNmDate",
]


def download_zip(url_addr, zip_path):
    """Download zip file from a url"""
    try:
        print(f"Downloading file from: {url_addr}")
        urllib.request.urlretrieve(url_addr, zip_path)
        return True
    except Exception as e:
        print(f"Could not retrieve file from: {url_addr}\n{e}")
        return False


def unzip_extract_fgdb(zip_path, scratch_folder, scratch_gdb):
    """unzip file, extract FGDB + feature class, return path"""
    try:
        print(f"...UnZipping file:      {os.path.basename(zip_path)}")
        with ZipFile(zip_path) as zip_ref:
            file_list = zip_ref.namelist()
            zip_ref.extractall(scratch_folder)

        fgdb_path = os.path.join(scratchFolder, os.path.dirname(file_list[0]))
        print(f"Extracted geodatabase {fgdb_path}")

        arcpy.env.workspace = fgdb_path
        fc_list = arcpy.ListFeatureClasses()
        if not fc_list:
            raise ValueError(f"No feature classes found in {fgdb_path}")
        fc_path = os.path.join(fgdb_path, fc_list[0])
        facts_fc = arcpy.FeatureClassToFeatureClass_conversion(fc_path, scratch_gdb, "tmp_perim")
        print(f"Using feature class: {fc_path}")
        return facts_fc

    except Exception as e:
        print(f"Could not unzip or extract feature class: {e}")
        return None, None


def clip_to_colorado(facts_fc, output_fc):
    """Clip data to Colorado extent and copy to final output"""
    try:
        print("...Clipping to Colorado extent.")
        arcpy.MakeFeatureLayer_management(facts_fc, "facts_fc_lyr", "STATE_ABBR = 'CO'")
        arcpy.CopyFeatures_management("facts_fc_lyr", output_fc)
        return True
    except:
        print(f"No Colorado data found or clipping failed.\n{e}")
        return False


def standardize_fields(facts_fc, url, datetime_str):
    rename_map = {
        "AU_NAME": "TREATMENT_NAME",
        "ACTIVITY_NAME": "ACTIVITY",
        "FUND_CODES": "FUND_CODE",
        "METHOD_DESC": "METHOD",
        "EQUIPMENT_DESC": "EQUIPMENT"
    }

    # Rename fields if they exist
    for old, new in rename_map.items():
        try:
            arcpy.AlterField_management(facts_fc, old, new, new)
            print(f"Renamed {old} -> {new}")
        except:
            pass

    # Add file/date field
    arcpy.AddField_management(facts_fc, "fileNmDate", "TEXT", 50)
    arcpy.CalculateField_management(
        facts_fc,
        "fileNmDate",
        f'"{os.path.basename(url)[:-4]} {datetime_str}"',
        "PYTHON_9.3"
    )


# ----- START SCRIPT -----
merge_list = []

for name, url in URLS.items():
    print(f" Processing FACTS data: {name}")
    zip_temp = os.path.join(scratchFolder, "TEMP_ZIP.zip")
    output_fc = os.path.join(scratch_gdb, f"FACTSperimters_{name}")

    # Download + unzip
    if not download_zip(url, zip_temp):
        continue

    facts_fc = unzip_extract_fgdb(zip_temp, scratchFolder, scratch_gdb)
    if not facts_fc:
        continue

    # Clip, repair, and clean fields
    clip_to_colorado(facts_fc, output_fc)
    arcpy.RepairGeometry_management(output_fc, "DELETE_NULL")
    standardize_fields(output_fc, url, datetime_str=datetime_str)
    merge_list.append(output_fc)

merged_fc = arcpy.Merge_management(merge_list, os.path.join(scratch_gdb, "merged_perimeters"))

# Preprocess merged perimters
print("Preprocessing FACTS Perimeter Feature Class")
print("Subsetting perimeters based on user selected time frame")

where_clause = (
    f"DATE_COMPLETED >= timestamp '{dt_start} 00:00:00' " 
    f"AND DATE_COMPLETED <= timestamp '{dt_end} 00:00:00'"
)

arcpy.MakeFeatureLayer_management(merged_fc, "date_subset_lyr", where_clause )
tmp_copy = arcpy.CopyFeatures_management("date_subset_lyr", os.path.join(scratch_gdb, "tmp_copy_date"))

# Project to NAD 1983 UTM Zone 13 if needed
desc = arcpy.Describe(tmp_copy)
spatialRef = desc.spatialReference
if spatialRef.Name == "NAD 1983":
    print("Spatial reference is already NAD 1983 — skipping reprojection.")
    arcpy.CopyFeatures_management(tmp_copy, final_fc)
else:
    print("Reprojecting to NAD83 UTM Zone 13N...")
    coordSystemNAD = (
        "PROJCS['NAD_1983_UTM_Zone_13N',"
        "GEOGCS['GCS_North_American_1983',"
        "DATUM['D_North_American_1983',"
        "SPHEROID['GRS_1980',6378137.0,298.257222101]],"
        "PRIMEM['Greenwich',0.0],"
        "UNIT['Degree',0.0174532925199433]],"
        "PROJECTION['Transverse_Mercator'],"
        "PARAMETER['false_easting',500000.0],"
        "PARAMETER['false_northing',0.0],"
        "PARAMETER['central_meridian',-111.0],"
        "PARAMETER['scale_factor',0.9996],"
        "PARAMETER['latitude_of_origin',0.0],"
        "UNIT['Meter',1.0]]"
    )
    arcpy.Project_management(tmp_copy, final_fc, coordSystemNAD)

# Clean up NEPA_DOC_NAME attribute
print("Rename projects without NEPA_DOC_NAME to 'None'")
with arcpy.da.UpdateCursor(final_fc, ["NEPA_DOC_NAME"]) as cursor:
    for row in cursor:
        if (
            row[0] in [
                "DEFAULT FOR NOT REQUIRED",
                "CE without DM",
                "DECISION NOTICE AND FINDING OF NO SIGNIFICANT IMPACT",
                "NEPA Pending",
                None
            ]
        ):
            row[0] = None

        else:
            if str(row[0]).startswith("(PALS)"):
                row[0] = str(row[0]).replace("(PALS)", "").strip()

        cursor.updateRow(row)

# Cleanup
print("Delete unnecessary fields")
db_fields = {"OBJECTID", "Shape", "Shape_Length", "Shape_Area"}
for fld in arcpy.ListFields(final_fc):
    if fld.name not in set(keep_fields) and fld.name not in db_fields:
        try:
            arcpy.DeleteField_management(final_fc, fld.name)
        except Exception as e:
            print(f"{fld.name} not deleted.")
            
print("\n=== Cleaning up temporary data ===")
try:
    if os.path.exists(zip_temp):
        os.remove(zip_temp)
    if 'fgdb_name' in locals() and fgdb_name:
        fgdb_path = os.path.join(scratchFolder, fgdb_name)
        if arcpy.Exists(fgdb_path):
            arcpy.Delete_management(fgdb_path)
    if 'facts_fc' in locals() and arcpy.Exists(facts_fc):
        arcpy.Delete_management(facts_fc)
    print("✅ Cleanup complete.")
except Exception as e:
    print(f"⚠️ Some interim data was not deleted.\n{e}")
print("Deleting unnecessary fields")

arcpy.management.Delete(merged_fc)
arcpy.management.Delete(tmp_copy)

print("Completed! Run Time: %s\n\n" %(datetime.now() - dt))
