import datetime
import arcpy
import os
import pandas as pd
import re


def add_fields_from_schema(fc, schema_dict):
    """Generic worker to add fields to any feature class with optional field length support."""
    existing = [f.name.upper() for f in arcpy.ListFields(fc)]
    for field_name, field_def in schema_dict.items():
        if field_name.upper() not in existing:
            if isinstance(field_def, dict):
                f_type = field_def.get("type")
                f_length = field_def.get("length")
                arcpy.management.AddField(fc, field_name, f_type, field_length=f_length)
            else:
                # Fallback for simple string definitions like "TEXT" or "LONG"
                arcpy.management.AddField(fc, field_name, field_def)


def delete_unnecessary_fields(input_fc, schema_dict):
    """Clean up unnecessary and extraneous fields from output"""
    # System fields that cannot be deleted
    protected_types = ["OID", "Geometry"]
    protected_names = {"SHAPE", "SHAPE_LENGTH", "SHAPE_AREA", "FID", "GEOMETRY"}

    keep_set = {f.upper() for f in schema_dict.keys()} | protected_names

    all_fields = arcpy.ListFields(input_fc)
    to_delete = []
    for f in all_fields:
        name_upper = f.name.upper()
        if f.type not in protected_types and name_upper not in keep_set:
            if not name_upper.startswith("SHAPE"):
                to_delete.append(f.name)

    if to_delete:
        arcpy.management.DeleteField(input_fc, to_delete)


def ensure_nad83_utm13(input_fc, output_fc, target_wkid=26913):
    """
        Ensures input feature class is projected to NAD83 / UTM Zone 13N (WKID 26913).
        If it's already in 26913, it copies directly. Otherwise, it projects it.
    """
    target_sr = arcpy.SpatialReference(target_wkid)
    input_sr = arcpy.Describe(input_fc)

    if getattr(input_sr, "factoryCode", None) == target_wkid:
        print("Spatial reference is already NAD 1983 — copying directly to final staged feature class.")
        arcpy.management.CopyFeatures(input_fc, output_fc)
    else:
        print(f"Reprojecting from '{input_sr.name}' to NAD83 UTM Zone 13N via Environment Settings...")
        with arcpy.EnvManager(outputCoordinateSystem=target_sr):
            arcpy.management.CopyFeatures(input_fc, output_fc)
    return output_fc


def classify_from_csv(csv_path, fc, source_fields, field_map, where_clause=None):
    """Update fields based on csv"""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    df = pd.read_csv(csv_path, encoding="utf-8-sig", keep_default_na=False)
    print("Reclassifying from CSV file")
    print(f"DEBUG: CSV Columns found: {list(df.columns)}")
    print(f"DEBUG: Looking for keys: {list(field_map.keys())}")

    mapping_dict = {}
    csv_out_cols = list(field_map.keys())

    for _, row in df.iterrows():
        key_parts = []
        for col in source_fields:
            v = str(row[col]).strip()
            if v.lower() in ["nan", "none", "null"]:
                v = " "
            key_parts.append(v)

        key = "|".join(key_parts)
        mapping_dict[key] = tuple(row[col] for col in csv_out_cols)

    fc_target_fields = list(field_map.values())
    cursor_fields = source_fields + fc_target_fields
    target_start_index = len(source_fields)
    with arcpy.da.UpdateCursor(fc, cursor_fields, where_clause=where_clause) as cursor:
        for row in cursor:
            key_vals = []
            for val in row[:target_start_index]:
                v = str(val).strip() if val is not None else ""
                if v.lower() in ["none", "nan", "null"]:
                    v = ""
                key_vals.append(v)

            row_key = "|".join(key_vals)
            new_vals = mapping_dict.get(row_key)

            if new_vals:
                row[target_start_index:] = new_vals
                cursor.updateRow(row)
            else:
                has_content = row_key.replace("|", "").strip()
                if has_content:
                    print(f"{cursor_fields[0]} not found in dictionary: {row_key}")

    print("Update complete!")


def remove_duplicate_list(value):
    """Remove duplicate and 'None' entries from a semicolon-separated strings."""
    if not value or str(value).strip().lower() in ("none", "", "unknown"):
        return []

    raw_vals = re.split(r'[;,]', str(value))
    vals = []
    for v in raw_vals:
        clean_v = v.strip()
        clean_v_upper = clean_v.upper()

        if not clean_v or clean_v_upper in ("NONE", "", "UNKNOWN"):
            continue

        if clean_v and clean_v not in vals:
            vals.append(clean_v)

    if not vals:
        return []

    # Fuzzy deduplication
    vals.sort(key=len, reverse=True)
    deduped = []
    for v in vals:
        v_upper = v.upper()
        is_redundant = False
        for kept_v in deduped:
            if v_upper in kept_v.upper():
                is_redundant = True
                break

        if not is_redundant:
            deduped.append(v)

    return deduped if deduped else None


def remove_spatial_slivers(feature_class, min_acres=0.05):
    """
        Evaluates features within a feature class and deletes geometric artifacts
        (slivers) using a combination of size, shape compactness, and naming indicators.

        Parameters:
            feature_class (str): Path to the target feature class.
            min_acres (float): The acreage threshold below which a polygon is scrutinized.
            area_unit (str): The linear unit of the dataset's projection ("FEET" or "METERS").

        Returns:
            int: Number of sliver records deleted.
        """
    # Conversion factors to acres
    ABSOLUTE_ACRES_FLOOR = 0.01
    fields = ["ACRES_GIS", "SHAPE@"]
    deleted_count = 0

    with arcpy.da.UpdateCursor(feature_class, fields) as cursor:
        for row in cursor:
            acres_val = row[0]
            geom = row[1]

            if acres_val is None or geom is None:
                cursor.deleteRow()
                deleted_count += 1
                continue

            if acres_val <= ABSOLUTE_ACRES_FLOOR:
                cursor.deleteRow()
                deleted_count += 1
                continue

            if acres_val < min_acres:
                if geom.length > 0:
                    compactness = geom.area / (geom.length ** 2)

                    if compactness < 0.025:
                        cursor.deleteRow()
                        deleted_count += 1
                        continue

    return deleted_count


def finalize_tracker_data(fc, agency_key, mgt_acre_field=None):
    """Standardize finalizer for agency datasets"""
    from config.config import AGENCY_CONSTANTS, AGENCY_FIELD_MAPS, activity_map

    print(f"Applying constants for {agency_key}")
    constants = AGENCY_CONSTANTS[agency_key]
    constants["MODIFY_BY"] = "'Stephanie Mueller'"
    constants["UPDATES"] = f"'{datetime.datetime.now().strftime('%m/%d/Y')}'"

    for field, val in constants.items():
        syntax = "PYTHON3" if "!" in str(val) else "PYTHON_9.3"
        arcpy.management.CalculateField(fc, field, val, syntax)

    print(f"Mapping source fields...")
    field_map = AGENCY_FIELD_MAPS[agency_key]
    for target, source in field_map.items():
        with arcpy.da.UpdateCursor(fc, [source, target]) as cursor:
            for row in cursor:
                raw_val = str(row[0]) if row[0] is not None else ""
                cleaned_val = remove_duplicate_list(raw_val)
                row[1] = "; ".join(cleaned_val)[0:254]
                cursor.updateRow(row)

    print("Calculating GIS Acres...")
    if mgt_acre_field:
        expression = f"!{mgt_acre_field}! if !{mgt_acre_field}! is not None else !ACRES_GIS!"
        arcpy.management.CalculateField(fc, "ACRES_MGT", expression, "PYTHON3")
    else:
        arcpy.management.CalculateField(fc, "ACRES_GIS", "!shape.area@acres!", "PYTHON_9.3", "")

    # Update Management
    print("Classifying management types...")

    with arcpy.da.UpdateCursor(fc, ["activity_reclass", "ACTIVITY", "MGT_TYPE"]) as cursor:
        for row in cursor:
            act = row[0]
            if act:
                act_norm = act.strip()
                if act_norm in activity_map:
                    clean_activity, mgt_type = activity_map[act_norm]

                    row[1] = clean_activity
                    row[2] = mgt_type
                    cursor.updateRow(row)
