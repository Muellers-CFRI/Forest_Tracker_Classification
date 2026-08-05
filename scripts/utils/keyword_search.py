import arcpy
import os
import re
import csv

from config.config import keyword_classification_fields, keyword_activity_fields
from scripts.utils.gis_tools import add_fields_from_schema


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = s.lower()                            # normalize case
    s = re.sub(r"[^\w\s]", " ", s)           # replace punctuation with space
    s = re.sub(r"[_]", " ", s)               # turn underscores into spaces
    s = re.sub(r"[\\/]", " ", s)             # turn slashes into spaces
    s = re.sub(r"\s+", " ", s)               # collapse multiple spaces
    return s.strip()


def classify_by_keyword(fc, activity_csv, class_field):
    """Classify text in 'class_field' using regex rules from csv."""
    rules = []
    with open(activity_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            regex_str = row["regex"].strip()
            try:
                compiled = re.compile(regex_str, re.IGNORECASE)
                rules.append({
                    "regex": compiled,
                    "activity": row["activity"].strip()
                })
            except re.error as e:
                print(f"Bad regex '{regex_str}' : {e}")

    activity_fieldnames = [f for f in keyword_classification_fields.keys() if f != "Class_Combine"]

    print(f"FC: {fc}")
    print(f"Class Field: {class_field}")
    print(f"Activity Names: {activity_fieldnames}")

    with arcpy.da.UpdateCursor(fc, [class_field] + activity_fieldnames) as cursor:
        for row in cursor:
            text = clean_text(row[0])

            matches, used_spans = [], []

            for rule in rules:
                for m in rule["regex"].finditer(text):
                    span = m.span()
                    if any(start <= span[0] < end or start < span[1] <= end for start, end in used_spans):
                        continue
                    matches.append({"activity": rule["activity"], "regex": rule["regex"].pattern})
                    used_spans.append(span)

            unique_matches = []
            seen_activities = set()
            for m in matches:
                if m["activity"] not in seen_activities:
                    unique_matches.append(m)
                    seen_activities.add(m["activity"])

            row[1:] = [None] * (len(row) - 1)

            # Fill ActClass_1/Keyword_1 … ActClass_3/Keyword_3
            for idx, match in enumerate(unique_matches[:3]):
                row[1 + idx * 2] = match["activity"]  # ActClass_#
                row[2 + idx * 2] = match["regex"]     # Keyword_#

            cursor.updateRow(row)


def classify_treatments(input_fc, fields_to_classify, activity_csv, output_fc):
    """Classify treatments by regex keywords."""
    print("Classifying treatments by keyword")

    temp_fc = arcpy.management.CopyFeatures(input_fc, arcpy.env.scratchGDB + "/fc")

    add_fields_from_schema(temp_fc, keyword_classification_fields)
    add_fields_from_schema(temp_fc, keyword_activity_fields)

    cursor_fields = fields_to_classify + ["Class_Combine"]
    combine_idx = len(fields_to_classify)

    with arcpy.da.UpdateCursor(temp_fc, cursor_fields) as cursor:
        for row in cursor:
            text_values = [str(row[i]) for i in range(len(fields_to_classify)) if row[i]]
            combined_text = " ".join(text_values)

            row[combine_idx] = combined_text[0:5000] if combined_text.strip() else None
            cursor.updateRow(row)

    classify_by_keyword(temp_fc, activity_csv, "Class_Combine")

    with arcpy.da.UpdateCursor(temp_fc, ["ActClass_1"]) as cursor:
        for row in cursor:
            if row[0] is None or str(row[0]).strip() == "":
                row[0] = "UNCLASSIFIED"
            cursor.updateRow(row)

    arcpy.management.RepairGeometry(temp_fc)
    arcpy.management.CopyFeatures(temp_fc, output_fc)
    arcpy.management.Delete(temp_fc)
    return output_fc


def explode_activity(fc, class_fields, out_fc):
    """
    Explodes matched keyword activities into separate rows.
    """
    sr = arcpy.Describe(fc).spatialReference
    if arcpy.Exists(out_fc):
        arcpy.management.Delete(out_fc)

    arcpy.management.CreateFeatureclass(
        out_path=os.path.dirname(out_fc),
        out_name=os.path.basename(out_fc),
        geometry_type=arcpy.Describe(fc).shapeType,
        spatial_reference=sr
    )

    keep_fields = [f for f in arcpy.ListFields(fc) if f.type not in ("OID", "Geometry")]
    for f in keep_fields:
        arcpy.management.AddField(out_fc, f.name, f.type, f.precision, f.scale, f.length)

    # Guarantee output schema fields exist
    existing_out_flds = [f.name for f in arcpy.ListFields(out_fc)]
    for target_fld in ["activity_reclass", "Keyword"]:
        if target_fld not in existing_out_flds:
            arcpy.management.AddField(out_fc, target_fld, "TEXT", field_length=100)

    # Fetch updated schema list
    updated_keep_fields = [f for f in arcpy.ListFields(out_fc) if f.type not in ("OID", "Geometry")]
    all_fields = [f.name for f in updated_keep_fields] + ["SHAPE@"]

    # --- FIX: Explicitly match ActClass_# with Keyword_# ---
    activities = list(class_fields.keys())
    act_flds = [f for f in activities if f.startswith("ActClass_")]
    key_flds = [f for f in activities if f.startswith("Keyword_")]

    with arcpy.da.SearchCursor(fc, [f.name for f in keep_fields] + ["SHAPE@"]) as cursor_in, \
            arcpy.da.InsertCursor(out_fc, all_fields) as cursor_out:

        for row in cursor_in:
            row_dict = dict(zip([f.name for f in keep_fields] + ["SHAPE@"], row))
            shape = row_dict.pop("SHAPE@")

            # Gather matched activities safely
            pairs = [(row_dict.get(a), row_dict.get(k)) for a, k in zip(act_flds, key_flds) if row_dict.get(a)]

            # Fallback if no activity matches were captured
            if not pairs:
                pairs = [("UNCLASSIFIED", "None")]

            seen = set()
            for activity, keyword in pairs:
                if activity not in seen:
                    out_dict = row_dict.copy()
                    out_dict["activity_reclass"] = activity
                    out_dict["Keyword"] = keyword

                    out_row = tuple(out_dict.get(f) for f in all_fields[:-1]) + (shape,)
                    cursor_out.insertRow(out_row)
                    seen.add(activity)

    arcpy.management.RepairGeometry(out_fc)


def split_outputs(exploded_fc, delete_out, unclass_out, class_out):
    """
    Splits features from exploded_fc into final output feature classes
    and cleans up temporary classification fields.
    """
    existing_fields = [f.name for f in arcpy.ListFields(exploded_fc)]
    optional_flds = ["ActClass_1", "ActClass_2", "ActClass_3", "ACT_CSV"]
    active_optionals = [f for f in optional_flds if f in existing_fields]

    # Clean up duplicate 'DELETE' rows when other valid treatments exist
    with arcpy.da.UpdateCursor(exploded_fc, ["activity_reclass"] + active_optionals) as cursor:
        for row in cursor:
            final_activity = row[0]
            reclass_activities = row[1:]

            if final_activity == "DELETE":
                if any(a and str(a).strip() not in ("", "None", "DELETE", "UNCLASSIFIED", "Null") for a in reclass_activities):
                    cursor.deleteRow()

    conditions = {
        delete_out:  "activity_reclass = 'DELETE'",
        unclass_out: "activity_reclass IN ('UNCLASSIFIED', 'TREE CHECK', 'PLANT CHECK')",
        class_out:   "activity_reclass IS NOT NULL AND activity_reclass NOT IN ('DELETE', 'UNCLASSIFIED', 'TREE CHECK', 'PLANT CHECK')"
    }

    cleanup_flds = ["ActClass_1", "Keyword_1", "ActClass_2", "Keyword_2", "ActClass_3", "Keyword_3", "STATUS"]

    arcpy.management.MakeFeatureLayer(exploded_fc, "out_layer")

    for out_path, sql in conditions.items():
        arcpy.management.SelectLayerByAttribute("out_layer", "NEW_SELECTION", sql)
        arcpy.management.CopyFeatures("out_layer", out_path)

        existing_out_flds = [f.name for f in arcpy.ListFields(out_path)]
        flds_to_delete = [f for f in cleanup_flds if f in existing_out_flds]
        if flds_to_delete:
            arcpy.management.DeleteField(out_path, flds_to_delete)

        count = int(arcpy.management.GetCount(out_path).getOutput(0))
        print(f"{os.path.basename(out_path)}: {count} features written")

    arcpy.management.Delete("out_layer")


def finalize_and_split(combined_fc, delete_out, unclass_out, class_out):
    """
    Wrapper to handle explode and split logic.
    """
    exploded_fc = combined_fc + "_vertical"

    explode_activity(combined_fc, keyword_classification_fields, exploded_fc)
    split_outputs(exploded_fc, delete_out, unclass_out, class_out)

    if arcpy.Exists(exploded_fc):
        arcpy.management.Delete(exploded_fc)
