# This is your "Master Schema"
# If the required fields change next year, you only change them HERE.
TRACKER_FIELDS = {
    "PRJ_NAME": "TEXT",
    "AGENCY": "TEXT",
    "AGENCY_C": "TEXT",
    "FUND_SOURCE": "TEXT",
    "FUND_TYPE": "TEXT",
    "LANDOWNER": "TEXT",
    "MGT_TYPE": "TEXT",
    "RXFIRE_MGT": "TEXT",
    "CANOPY_MGT": "TEXT",
    "SURF_MGT": "TEXT",
    "REFOREST": "TEXT",
    "TREE_COUNT": "LONG",
    "SPECIES": "TEXT",
    "PRJ_OBJECT": "TEXT",
    "YEAR_COMP": "LONG",
    "ACRES_GIS": "DOUBLE",
    "ACRES_MGT": "DOUBLE",
    "NOTES": "TEXT",
    "ORGFILE": "TEXT",
    "UPDATED": "DATE",
    "MODIFY_BY": "TEXT",
    "SourceOID": "LONG"
}

# You can also store other "Constants" here
CURRENT_YEAR = 2025