# Master Schema
# If the required fields change next year, you only change them HERE.

# DATES INCLUSIVE
START_YEAR = 2024
END_YEAR = 2025
CURRENT_YEAR = 2026

# FACTS source URLs
FACTS_URLS = {
    "CommonAttributes": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/S_USA.Actv_CommonAttribute_PL.gdb.zip",
    "HazFuelTrt": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_HazFuelTrt_PL.gdb.zip",
    "SilvReforestation": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_SilvReforest.gdb.zip",
    "BrushDisposal": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_BrushDisposal.gdb.zip",
    "CFLRP": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_CFLRP_PL.gdb.zip",
    "IRR": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_IRR_PL.gdb.zip",
    "KnutsonVandenberg": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_KnutsonVandenberg.gdb.zip",
    "SilvTSI": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_SilvTSI.gdb.zip",
    "StwrdshpCntrctng": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_StwrdshpCntrctng_PL.gdb.zip",
    "TimberHarvest": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_TimberHarvest.gdb.zip",
    "WBBS": "https://data.fs.usda.gov/geodata/edw/edw_resources/fc/Actv_WBBS_PL.gdb.zip",
}

IFPERS_URL = "https://ifprs.firenet.gov/arcgis/rest/services/OpenData/IFPRS_Open_Data/FeatureServer/2"

# FIELDS LISTS
facts_processing_fields = [
    "NEPA_DOC_NAME",
    "TREATMENT_NAME",
    "ACTIVITY",
    "METHOD",
    "EQUIPMENT",
    "DATE_COMPLETED",
    "DATE_AWARDED",
    "FUND_CODE",
    "NBR_UNITS_ACCOMPLISHED",
    "fileNmDate",
]

ifpers_processing_fields = [
    "ID",
    "Name",
    "Type",
    "Category",
    "SubType",
    "Class",
    "Agency",
    "Department",
    "State",
    "CalculatedArea",
    "InitiationDate",
    "CompletionDate",
    "Notes",
    "Status",
    "FundingSource",
    "FundingSourceProgram",
    "FundingAgency"
]

keyword_classification_fields = {
    "Class_Combine": {"type": "TEXT", "length": 5000},
    "ActClass_1": {"type": "TEXT", "length": 100},
    "Keyword_1": {"type": "TEXT", "length": 100},
    "ActClass_2": {"type": "TEXT", "length": 100},
    "Keyword_2": {"type": "TEXT", "length": 100},
    "ActClass_3": {"type": "TEXT", "length": 100},
    "Keyword_3": {"type": "TEXT", "length": 100}
}

keyword_activity_fields = {
    "activity_reclass": "TEXT",
    "Keyword": "TEXT"
}

TRACKER_FIELDS = {
    "PRJ_NAME": "TEXT",
    "AGENCY": "TEXT",
    "AGENCY_C": "TEXT",
    "YEAR_COMP": "LONG",
    "DATE_COMP": "DATE", ## Add completion date when available - not in final
    "FUND_SOURCE": "TEXT",
    "FUND_TYPE": "TEXT",
    "PARTNERS": "TEXT",
    "LANDOWNER": "TEXT",
    "MGT_TYPE": "TEXT",
    "ACTIVITY": "TEXT",
    "TREE_COUNT": "LONG",
    "SPECIES": "TEXT",
    "PRJ_OBJECT": "TEXT",
    "ACRES_GIS": "DOUBLE",
    "ACRES_MGT": "DOUBLE",
    "NOTES": "TEXT",
    "ORGFILE": "TEXT",
    "UPDATED": "DATE",
    "MODIFY_BY": "TEXT",
    "SourceOID": "LONG"
}

activity_map = {
    "Broadcast Burn": ("Broadcast Burn", "Prescribed Fire"),
    "Pile Burn": ("Pile Burn", "Prescribed Fire"),
    "Manual": ("Manual", "Mechanical and Hand"),
    "Mechanical": ("Mechanical", "Mechanical and Hand"),
    "Mastication": ("Mastication", "Mechanical and Hand"),
    "Chemical": ("Chemical", "Mechanical and Hand"),
    "Removal": ("Removal", "Mechanical and Hand"),
    "Lop and Scatter": ("Lop and Scatter", "Mechanical and Hand"),
    "Pile Fuels": ("Pile Fuels", "Mechanical and Hand"),
    "Mulching": ("Mulching", "Mechanical and Hand"),
    "Plant Trees": ("Plant Trees", "Reforestation"),
    "Seed": ("Seed", "Reforestation")
}

# AGENCY CONSTANTS
AGENCY_CONSTANTS = {
    "blm": {
        "AGENCY": "'Bureau of Land Management'",
        "AGENCY_C": "'BLM'",
        "ORGFILE": "'vtrt_cmplt_poly'",
        "FUND_TYPE": "'Federal'"
    },
    "ifpers": {
        "AGENCY_C": "!FundingAgency!",
        "ORGFILE": "'IFPRS_Open_Data/Polygon Actions'",
        "FUND_TYPE": "'Federal'"
    },
    "usfs": {
        "AGENCY": "'US Forest Service'",
        "AGENCY_C": "'USFS'",
        "ORGFILE": "!fileNmDate!",
        "FUND_TYPE": "'Federal'"
    }
}

# Agency Field Mappings (Source Field -> Tracker Field)
AGENCY_FIELD_MAPS = {
    "blm": {
        "PRJ_NAME": "TRTMNT_NM",
        "PRJ_OBJECT": "TRTMNT_COMMENTS"
    },
    "usfs": {
        "PRJ_OBJECT": "ACTIVITY",
        "FUND_SOURCE": "funding_update"
    },
    "ifpers": {
        "PRJ_NAME": "Name",
        "PRJ_OBJECT": "Notes",
        "FUND_SOURCE": "FundingSource"
    }
}
