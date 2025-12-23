# Import packages
import arcpy
from datetime import datetime
from scripts.utils.paths import get_gdb_path, KEYWORD_CSV
from scripts.utils.date_tools import get_comp_year
from scripts.utils.keyword_search import (
    classify_treatments,
    split_outputs,
    add_new_fields,
    tracker_fields
)

from scripts.utils.gis_tools import add_tracker_fields, delete_unnecessary_fields

arcpy.env.overwriteOutput = True
dt = datetime.now()


def run_blm_stage_1():
    """
    STAGE 1: Automate the keyword classification and split the data.
    This creates the files for you to review in ArcGIS Pro.
    """
    print("--- BLM STAGE 1: Keyword Classification ---")

    staged_gdb = get_gdb_path("blm", stage="staged", gdb_name="blm")
    input_fc = r'E:\CFRI\FOREST_TRACKER\FEDERAL_DATA_CROSSWALK\BLM\WORKING\REVIEW_2024_DATA_UPDATE\output.gdb\classified_output_manual'  ## Update to raw folder

    combined_out = f"{staged_gdb}\\blm_combined_staged"
    class_out = f"{staged_gdb}\\blm_classified_temp"
    unclass_out = f"{staged_gdb}\\blm_unclassified_REVIEW_ME"
    delete_out = f"{staged_gdb}\\blm_deleted"

    classify_treatments(
        input_fc=input_fc,
        fields_to_classify=["TRTMNT_NM", "TRTMNT_COMMENTS"],
        date_field="TRTMNT_END_DT",
        activity_csv=str(KEYWORD_CSV),
        output_fc=combined_out,
        start_year=2020,
        end_year=2025
    )

    split_outputs(combined_out, delete_out, unclass_out, class_out)

    add_tracker_fields(class_out)
    add_tracker_fields(unclass_out)

    print(f"\nSTATE 1 COMPLETE.")
    print(f"Please review {unclass_out} and move fixed rows to {class_out} before running Stage 2")


def run_blm_stage_2():
    """
    STAGE 2: Finalize the data after manual review.
    This runs the specific BLM logic (Mapping activities to MGT_TYPE, etc.)
    """
    print("--- BLM STAGE 2: Finalizing Reviewed Data ---")

    staged_gdb = get_gdb_path("blm", stage="staged", gdb_name="blm")
    input_fc = f"{staged_gdb}\\blm_classified_temp"
    output_fc = f"{staged_gdb}\\blm_classified"

    datetime_str = dt.strftime("%m/%d/%Y")
    print("Updating static fields...")

    # Add source OID to link input and output feature class
    if "SourceOID" not in [f.name for f in arcpy.ListFields(input_fc)]:
        arcpy.AddField_management(input_fc, "SourceOID", "LONG")
    with arcpy.da.UpdateCursor(input_fc, ["SourceOID", "OBJECTID"]) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)

    # Create copy to final
    arcpy.CopyFeatures_management(input_fc, output_fc)

    final_fields = ["PRJ_NAME",
                    "AGENCY",
                    "AGENCY_C",
                    "FUNDING",
                    "LANDOWNER",
                    "MGT_TYPE",
                    "RXFIRE_MGT",
                    "CANOPY_MGT",
                    "SURF_MGT",
                    "REFOREST",
                    "TREE_COUNT",
                    "SPECIES",
                    "PRJ_OBJECT",
                    "YEAR_COMP",
                    "ACRES_GIS",
                    "ACRES_MGT",
                    "NOTES",
                    "ORGFILE",
                    "UPDATED",
                    "MODIFY_BY",
                    "SourceOID"]

    # Update CALCULATE FIELDS
    print("Updating static fields...")
    constant_fields = {
        "AGENCY": "'Bureau of Land Management'",
        "AGENCY_C": "'BLM'",
        "ORGFILE": "'vtrt_cmplt_poly'",
        "MODIFY_BY": "'S E MUELLER'",
        "UPDATED": f"'{datetime_str}'"
    }
    for field, expression in constant_fields.items():
        arcpy.CalculateField_management(output_fc, field, expression, "PYTHON_9.3")

    # Update PRJ_NAME, OBJECTIVE
    print("Copying project names and comments...")
    with arcpy.da.UpdateCursor(output_fc, ["TRTMNT_NM", "PRJ_NAME"]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)

    with arcpy.da.UpdateCursor(output_fc, ["TRTMNT_COMMENTS", "PRJ_OBJECT"]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)

    # UPDATE ACRES
    print("Calculating acres...")
    arcpy.CalculateField_management(output_fc, "ACRES_GIS", "!shape.area@acres!", "PYTHON_9.3", "")
    with arcpy.da.UpdateCursor(output_fc, ["BLM_ACRES", "ACRES_MGT"]) as cursor:
        for row in cursor:
            row[1] = row[0]
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

    with arcpy.da.UpdateCursor(output_fc, ["Activity", "FIRE_MGT", "CANOPY_MGT", "SURF_MGT", "REFOREST", "MGT_TYPE"]
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

    # Update YEAR_COMP
    print("Updating completion year...")
    with arcpy.da.UpdateCursor(output_fc, ["TRTMNT_START_DT", "TRTMNT_END_DT", "YEAR_COMP"]) as cursor:
        for row in cursor:
            row[2] = get_comp_year(row[1], row[0])
            cursor.updateRow

    print("Delete unnecessary fields")
    delete_unnecessary_fields(output_fc)

    print("BLM STAGE 2 COMPLETE. Data is ready for final merge.")

if __name__ == "main":
    # For testing in PyCharm, you can choose which one to run here...
    run_blm_stage_1()
    # run_blm_stage_2()