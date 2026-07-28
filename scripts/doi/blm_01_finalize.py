# Import packages
import arcpy
from datetime import datetime
from scripts.utils.paths import get_gdb_path, RAW_GDB, KEYWORD_CSV
from config.config import START_YEAR, TRACKER_FIELDS
from scripts.utils.date_tools import prep_date_fields, filter_by_year
from scripts.utils.gis_tools import (add_fields_from_schema,
                                     delete_unnecessary_fields, finalize_tracker_data)
from scripts.utils.keyword_search import classify_treatments, finalize_and_split

arcpy.env.overwriteOutput = True
dt = datetime.now()


def run_blm_stage_1():
    """
    STAGE 1: Automate the keyword classification and split the data.
    This creates the files for you to review in ArcGIS Pro.
    """
    print("--- BLM STAGE 1: Keyword Classification ---")

    staged_gdb = get_gdb_path("blm", stage="staged", gdb_name="blm")
    raw_input = f"{RAW_GDB}\\blm"

    prepped_fc = f"{staged_gdb}\\blm_prepped"
    filtered_fc = f"{staged_gdb}\\blm_filtered"
    combined_out = f"{staged_gdb}\\blm_combined_staged"
    class_out = f"{staged_gdb}\\blm_classified_temp"
    unclass_out = f"{staged_gdb}\\blm_unclassified_staged_review"
    delete_out = f"{staged_gdb}\\blm_deleted"

    print("Copying raw data to processing environment...")
    arcpy.CopyFeatures_management(raw_input, prepped_fc)

    add_fields_from_schema(prepped_fc, TRACKER_FIELDS)

    print("Stamping SourceOID and calculating completion years...")
    prep_date_fields(prepped_fc,
                     date_fields=["TRTMNT_START_DT", "YEAR_COMP"],
                     min_year=START_YEAR)

    filter_by_year(prepped_fc, filtered_fc, year_field="YEAR_COMP")

    classify_treatments(
        input_fc=filtered_fc,
        fields_to_classify=["TRTMNT_NM", "TRTMNT_COMMENTS"],
        activity_csv=str(KEYWORD_CSV),
        output_fc=combined_out
    )

    finalize_and_split(combined_out, delete_out, unclass_out, class_out)

    arcpy.Delete_management(prepped_fc)
    arcpy.Delete_management(filtered_fc)

    print(f"\nSTATE 1 COMPLETE.")
    print(f"Please review {unclass_out} and move fixed rows to {class_out} before running Stage 2")


def run_blm_stage_2():
    """STAGE 2: Finalize the data after manual review."""
    print("--- BLM STAGE 2: Finalizing Reviewed Data ---")

    staged_gdb = get_gdb_path("blm", stage="staged", gdb_name="blm")
    input_fc = f"{staged_gdb}\\blm_classified_temp"
    output_fc = f"{staged_gdb}\\blm_classified"

    arcpy.CopyFeatures_management(input_fc, output_fc)

    finalize_tracker_data(output_fc, agency_key="doi", mgt_acre_field="BLM_ACRES")

    delete_unnecessary_fields(output_fc, TRACKER_FIELDS)

    print("BLM STAGE 2 COMPLETE. Data is ready for final merge.")
