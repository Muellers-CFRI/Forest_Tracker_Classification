import arcpy
import os
import re
import csv

from config.config import keyword_classification_fields, keyword_activity_fields
from scripts.utils.gis_tools import add_fields_from_schema


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower()                                        # normalize case
    s = re.sub(r"[^\w\s]", " ", s)           # replace punctuation with space
    s = re.sub(r"[_]", " ", s)               # turn underscores into spaces
    s = re.sub(r"[\\/]", " ", s)             # turn slashes into spaces
    s = re.sub(r"\s+", " ", s)               # collapse multiple spaces
    return s.strip()


def classify_by_keyword(fc, activity_csv, class_field):
    """Classify text in 'class_field' using regex rules from csv."""

    # Build keyword dictionary and sort once by priority
    rules = []
    with open(activity_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            regex_str = row["regex"].strip()
            try:
                # Compile regex once, case-insensitive
                compiled = re.compile(regex_str, re.IGNORECASE)
                rules.append({
                    "regex": compiled,
                    "activity": row["activity"].strip()
                })
            except re.error as e:
                print(f"Bad regex '{regex_str}' : {e}")

    activity_fieldnames = [f for f in keyword_classification_fields.keys() if f != "Original_ID" and f != "Class_Combine"]

    print(f"FC: {fc}")
    print(f"Class Field: {class_field}")
    print(f"Activity Names: {activity_fieldnames}")

    with arcpy.da.UpdateCursor(fc, [class_field] + activity_fieldnames) as cursor:
        for row in cursor:
            text = row[0]
            text = clean_text(text)

            # Find all regex matches
            matches, used_spans = [], []

            for rule in rules:
                for m in rule["regex"].finditer(text):
                    span = m.span()
                    # Skip if span overlaps a previously claimed match
                    if any(start <= span[0] < end or start < span[1] <= end for start, end in used_spans):
                        continue
                    matches.append({"activity": rule["activity"], "regex": rule["regex"].pattern})
                    used_spans.append(span)

                #print(f"TEXT: {text} -  matches: {matches}")

            unique_matches = []
            seen_activities = set()
            for m in matches:
                if m["activity"] not in seen_activities:
                    unique_matches.append(m)
                    seen_activities.add(m["activity"])

            row[1:] = [None] * (len(row) - 1)

            # fill ActClass_1/Keyword_1 … ActClass_3/Keyword_3
            for idx, match in enumerate(unique_matches[:3]):
                row[1 + idx * 2] = match["activity"]  # Activity_#
                row[2 + idx * 2] = match["regex"]  # Keyword_#

            cursor.updateRow(row)


def classify_treatments(input_fc, fields_to_classify, activity_csv, output_fc):
    """Classify treatments by regex keywords and date filter."""
    print("Classifying treatments by keyword")

    # Copy input to preserve source
    temp_fc = arcpy.CopyFeatures_management(input_fc, arcpy.env.scratchGDB + "/fc")

    add_fields_from_schema(temp_fc, keyword_classification_fields)
    add_fields_from_schema(temp_fc, keyword_activity_fields)

    # Build cursor field list: input text fields + Class_Combine + date + YEAR_COMP
    cursor_fields = fields_to_classify + ["Class_Combine"]
    combine_idx = len(fields_to_classify)

    with arcpy.da.UpdateCursor(temp_fc, cursor_fields) as cursor:
        for row in cursor:
            # Combine selected text fields, ignoring None values
            text_values = [str(row[i]) for i in range(len(fields_to_classify)) if row[i]]
            combined_text = " ".join(text_values)

            row[combine_idx] = combined_text[0:254] if combined_text.strip() else None
            cursor.updateRow(row)

    # Add activity fields and classify by regex
    classify_by_keyword(temp_fc, activity_csv, "Class_Combine")

    with arcpy.da.UpdateCursor(temp_fc, ["ActClass_1"]) as cursor:
        for row in cursor:
            if row[0] is None or str(row[0]).strip() == "":
                row[0] = "UNCLASSIFIED"
            cursor.updateRow(row)

    # Cleanup
    arcpy.RepairGeometry_management(temp_fc)
    arcpy.CopyFeatures_management(temp_fc, output_fc)
    arcpy.Delete_management(temp_fc)
    return output_fc


def explode_activity(fc, class_fields, out_fc):
    # Create output feature class
    sr = arcpy.Describe(fc).spatialReference
    if arcpy.Exists(out_fc):
        arcpy.Delete_management(out_fc)
    arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(out_fc),
        out_name=os.path.basename(out_fc),
        geometry_type=arcpy.Describe(fc).shapeType,
        spatial_reference=sr
    )

    # Copy all non-system fields (exclude OID and Geometry)
    keep_fields = [f for f in arcpy.ListFields(fc) if f.type not in ("OID", "Geometry")]
    for f in keep_fields:
        arcpy.AddField_management(out_fc, f.name, f.type, f.precision, f.scale, f.length)

    # --- Build field list for cursors ---
    all_fields = [f.name for f in keep_fields] + ["SHAPE@"]
    existing_fields = [f.name for f in arcpy.ListFields(fc)]
    has_csv_field = "ACT_CSV" in existing_fields

    # --- Process rows ---
    with arcpy.da.SearchCursor(fc, all_fields) as cursor_in, \
            arcpy.da.InsertCursor(out_fc, all_fields) as cursor_out:

        for row in cursor_in:
            row_dict = dict(zip(all_fields, row))
            shape = row_dict.pop("SHAPE@")

            # pull paired activity/keyword values
            activities = list(class_fields.keys())
            act_values = [row_dict.get(f) for f in activities[2::2]]
            key_values = [row_dict.get(f) for f in activities[3::2]]

            explosion_list = list(zip(act_values, key_values))

            if has_csv_field and row_dict.get("ACT_CSV"):
                explosion_list.append((row_dict.get("ACT_CSV"), "Official Agency Reclass"))

            seen_activities = set()

            for activity, keyword in explosion_list:
                if activity and activity not in seen_activities:  # only explode non-empty
                    # create a copy of row_dict and update Activity/Keyword
                    out_row_dict = row_dict.copy()
                    if "activity_reclass" in out_row_dict:
                        out_row_dict["activity_reclass"] = activity
                    if "Keyword" in out_row_dict:
                        out_row_dict["Keyword"] = keyword

                    # maintain field order for insert
                    out_row = tuple(out_row_dict[f] for f in all_fields[:-1]) + (shape,)
                    cursor_out.insertRow(out_row)
                    seen_activities.add(activity)

    arcpy.RepairGeometry_management(out_fc)
    print(f"Exploded activities written to: {out_fc}")


def split_outputs(combined_fc, delete_out, unclass_out, class_out):
    # First, delete "DELETE" rows that have other valid activities in Activity_#
    existing_fields = [f.name for f in arcpy.ListFields(combined_fc)]
    cursor_flds = ["activity_reclass"]
    optional_flds = ["ActClass_1", "ActClass_2", "ActClass_3", "ACT_CSV"]
    active_optionals = [f for f in optional_flds if f in existing_fields]

    with arcpy.da.UpdateCursor(combined_fc, cursor_flds + active_optionals) as cursor:
        for row in cursor:
            final_activity = row[0]
            reclass_activities = row[1:]

            if final_activity == "DELETE":
                # Check if ANY of the activity fields contain something other than DELETE/None
                if any(a not in (None, "DELETE", "UNCLASSIFIED") for a in reclass_activities):
                    cursor.deleteRow()

    conditions = {
        delete_out: "activity_reclass = 'DELETE'",
        unclass_out: "activity_reclass IN ('UNCLASSIFIED', 'TREE CHECK')",
        class_out: "activity_reclass IS NOT NULL AND activity_reclass NOT IN ('DELETE', 'UNCLASSIFIED', 'TREE CHECK')"
    }

    arcpy.MakeFeatureLayer_management(combined_fc, "out_layer")
    for out_fc_path, sql in conditions.items():
        arcpy.SelectLayerByAttribute_management("out_layer", "NEW_SELECTION", sql)
        arcpy.CopyFeatures_management("out_layer", out_fc_path)

        delete_flds = ["ActClass_1", "Keyword_1", "ActClass_2", "Keyword_2", "ActClass_3", "Keyword_3"]
        existing_fields = [f.name for f in arcpy.ListFields(out_fc_path)]
        for fld in delete_flds:
            if fld in existing_fields:
                arcpy.DeleteField_management(out_fc_path, fld)

        count = int(arcpy.GetCount_management("out_layer").getOutput(0))
        print(f"{out_fc_path}: {count} features selected")  # debug

    arcpy.Delete_management("out_layer")


def finalize_and_split(combined_fc, delete_out, unclass_out, class_out):
    """Wrapper to handle explode and split logic"""
    exploded_fc = combined_fc + "_vertical"

    explode_activity(combined_fc, keyword_classification_fields, exploded_fc)
    split_outputs(exploded_fc, delete_out, unclass_out, class_out)

    if arcpy.Exists(exploded_fc):
        arcpy.Delete_management(exploded_fc)
