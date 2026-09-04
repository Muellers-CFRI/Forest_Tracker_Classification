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


def prep_date_fields(fc, date_fields, min_year=START_YEAR):
    """
        Dynamically maps SourceOID, populates DATE_COMP from prioritized source fields,
        and calculates YEAR_COMP.
    """
    cursor_fields = ["DATE_COMP", "YEAR_COMP"] + date_fields

    print(f"Stamping OIDs and calculating years using {date_fields}")
    with arcpy.da.UpdateCursor(fc, cursor_fields) as cursor:
        for row in cursor:

            source_dates = [row[i] for i in range(2, len(cursor_fields))]
            primary_date = next((d for d in source_dates if d is not None), None)

            row[0] = primary_date
            row[1] = get_comp_year(*source_dates)
            cursor.updateRow(row)


def filter_by_year(input_fc, output_fc, year_field="YEAR_COMP", start=START_YEAR, end=END_YEAR):
    """Filters data to a specific year range and drops NULL/unmapped years."""
    # Strict SQL clause catching valid range and excluding NULLs
    filter_years_clause = f"{year_field} IS NOT NULL AND {year_field} >= {start} AND {year_field} <= {end}"
    print(f"Filtering {year_field} between {start} and {end}...")

    try:
        arcpy.analysis.Select(input_fc, output_fc, filter_years_clause)
        count = int(arcpy.management.GetCount(output_fc)[0])
        print(f"Filter complete. {count} records kept.")
    except Exception as e:
        print(f"Error filtering {year_field}: {e}")
        raise e

