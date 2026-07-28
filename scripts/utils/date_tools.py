import arcpy
from config.config import START_YEAR, END_YEAR


def get_comp_year(*dates, min_year=START_YEAR):
    """
    Takes any number of date objects and returns the year of the first
    valid one found.

    Usage: get_priority_year(end_date, actual_date, planned_date)
    """
    for d in dates:
        if d is not None and hasattr(d, "year"):
            if d.year >= min_year:
                return d.year

    return None


def prep_date_fields(fc, date_fields, min_year):
    cursor_fields = ["OBJECTID", "SourceOID", "DATE_COMP", "YEAR_COMP"] + date_fields

    print(f"Stamping OIDs and calculating years using {date_fields}")
    with arcpy.da.UpdateCursor(fc, cursor_fields) as cursor:
        for row in cursor:
            row[1] = row[0]
            primary_date = row[4]
            secondary_date = row[5] if len(date_fields) > 1 else None

            row[2] = primary_date if primary_date is not None else secondary_date
            row[3] = get_comp_year(primary_date, secondary_date, min_year=min_year)
            cursor.updateRow(row)


def filter_by_year(input_fc, output_fc, year_field, start=START_YEAR, end=END_YEAR):
    """Filters data to a specific year range based on a dynamic field name."""
    filter_years_clause = f"{year_field} >= {start} AND {year_field} <= {end}"
    print(f"Filtering {year_field} between {start} and {end}...")

    try:
        arcpy.analysis.Select(input_fc, output_fc, filter_years_clause)
        count = int(arcpy.GetCount_management(output_fc)[0])
        print(f"Filter complete. {count} records kept.")
    except Exception as e:
        print(f"Error filtering {year_field}: {e}")

