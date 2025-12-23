def get_comp_year(*dates, min_year=2000):
    """
    Takes any number of date objects and returns the year of the first
    valid one found.

    Usage: get_priority_year(end_date, actual_date, planned_date)
    """
    for d in dates:
        if hasattr(d, "year") and d.year >= min_year:
            return d.year

    return None

