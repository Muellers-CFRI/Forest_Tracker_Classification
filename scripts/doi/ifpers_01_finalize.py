import arcpy
from datetime import datetime
from scripts.utils.paths import get_gdb_path, RAW_GDB, IFPERS_TYPE_CSV, KEYWORD_CSV
from config.config import START_YEAR, TRACKER_FIELDS
from scripts.utils.date_tools import prep_date_fields, filter_by_year
from scripts.utils.gis_tools import (add_fields_from_schema, classify_from_csv,
                                     finalize_tracker_data, delete_unnecessary_fields)
from scripts.utils.keyword_search import classify_treatments, finalize_and_split

arcpy.env.overwriteOutput = True
dt = datetime.now()


def run_ifpers_stage_1():
    """
    STAGE 1:
    """
    print("--- IFPERS STAGE 1: Reclassify ---")

    staged_gdb = get_gdb_path("ifpers", stage="staged", gdb_name="ifpers")
    raw_input = f"{RAW_GDB}\\ifpers"

    prepped_fc = f"{staged_gdb}\\ifpers_prepped"
    filtered_fc = f"{staged_gdb}\\ifpers_filtered"
    combined_out = f"{staged_gdb}\\ifpers_combined_staged"

    class_out = f"{staged_gdb}\\ifpers_classified_temp"
    unclass_out = f"{staged_gdb}\\ifpers_unclassified_staged_review"
    delete_out = f"{staged_gdb}\\ifpers_deleted"

    print("Copying raw data to processing environment...")
    where_clause = "State = 'Colorado' AND Class = 'Actual Treatment'"
    arcpy.MakeFeatureLayer_management(raw_input, "actual_trt", where_clause)
    arcpy.CopyFeatures_management("actual_trt", prepped_fc)

    add_fields_from_schema(prepped_fc, TRACKER_FIELDS)

    print("Stamping SourceOID and calculating completion years...")
    prep_date_fields(prepped_fc,
                     date_fields=["CompletionDate", "InitiationDate"],
                     min_year=START_YEAR)

    filter_by_year(prepped_fc, filtered_fc, year_field="YEAR_COMP")

    arcpy.AddField_management(prepped_fc, "ACT_CSV", "TEXT")
    classify_from_csv(
        csv_path=IFPERS_TYPE_CSV,
        fc=prepped_fc,
        source_fields=["Type", "Category", "SubType"],
        field_map={
            "reclass": "ACT_CSV"}
    )

    classify_treatments(
        input_fc=prepped_fc,
        fields_to_classify=["NAME", "Notes"],
        activity_csv=str(KEYWORD_CSV),
        output_fc=combined_out
    )

    finalize_and_split(combined_out, delete_out, unclass_out, class_out)

    arcpy.Delete_management(prepped_fc)
    arcpy.Delete_management(filtered_fc)

    print(f"\nSTAGE 1 COMPLETE.")
    print(f"Please review {combined_out} and compare ACTIVITY classification to keyword values")


def run_ifpers_stage_2():
    """STAGE 2: Finalize the data after manual review."""
    print("--- IFPERS STAGE 2: Finalizing Reviewed Data")

    staged_gdb = get_gdb_path("ifpers", stage="staged", gdb_name="ifpers")
    input_fc = f"{staged_gdb}\\ifpers_classified_temp"
    output_fc = f"{staged_gdb}\\ifpers_classified"

    arcpy.CopyFeatures_management(input_fc, output_fc)

    finalize_tracker_data(output_fc, agency_key="ifpers")

    delete_unnecessary_fields(output_fc, TRACKER_FIELDS)

    print("IFPERS STAGE 2 COMPLETE. Data is ready for final merge.")


run_ifpers_stage_1()
