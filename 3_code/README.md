# Colorado Forest Tracker GIS Pipeline

An automated data pipeline designed to download, clean, reclassify, and flatten public federal land management data for direct integration into the Colorado Forest Tracker. 

This repository standardizes and aggregates overlapping spatial accomplishment datasets from multiple federal agencies into a single master database.

---

## System Architecture & Directory Layout

Core parameters live in a centralized configuration script (config.py), utility tools handle dynamic functions (gis_tools.py and date_tools.py), and individual agency workflows are isolated into step-by-step sequential scripts.

```text
FOREST_TRACKER/
├── README.md                           
├── .gitignore                          
└── 3_code/                             
    ├── config/
    │   ├── config.py                   <-- Central brain (Years, Master Schema, URL registries)
    │   ├── ifpers_type_reclass.csv     <-- Static Tier 1 Type mapping tables
    │   ├── keywords.csv                <-- Regex keyword dictionary
    │   ├── usfs_activity_reclass.csv   <-- Static Tier 1 Activity mapping tables
    │   ├── usfs_method_reclass.csv     <-- Static Tier 2 Method mapping tables
    │   ├── usfs_equip_reclass.csv      <-- Static Tier 3 Equipment mapping tables
    │   └── usfs_funding_reclass.csv    <-- Static USFS Funding source crosswalk lookups
    │
    ├── usfs/
    │   ├── 01_facts_download_QAQC.py
    │   ├── 02_facts_reclass.py
    │   ├── 03_facts_flatten.py
    │   ├── 04_facts_finalize.py
    │   └── run_usfs_all.py             <-- Master Orchestrator (Runs entire USFS stack)
    │
    ├── blm/
    │   ├── 01_blm_classify.py
    │   └── 02_blm_finalize.py
    │
    ├── doi/
    │   ├── 01_ifpers_dwnld_post2024.py
    │   ├── 02_ifpers_reclass_post2024.py
    │   └── 03_ifpers_finalize_post2024.py
    │
    └── utils/
        ├── PATHS.py                    <-- Dynamic workspace, scratch, and Box path builder
        ├── date_tools.py               <-- Date formatting and filtering utility functions
        ├── gis_tools.py                <-- Universal shared ArcPy processing operations
        └── keyword_search.py           <-- Text matching and regex classification tools

```
### 1. USFS Data Pipeline Sequence

The USFS pipeline executes in four distinct stages to protect data integrity and resolve potential spatial double-counting from overlapping management activities:


```

[01 Ingestion]  ──►    [02 Reclass]   ──►   [03 Flatten]   ──►    [04 Finalize]
Download &             Hierarchical         100m Spatial          Convert to
Boundary Clip          CSV Crosswalk        Dissolve              Master Schema

```

1. **`01_facts_download_QAQC.py` (Data Ingestion):** Automatically downloads multiple compressed `.gdb.zip` endpoints directly from the USFS Enterprise Data Warehouse, clips them to the Colorado state boundary, and explodes complex multipart features into distinct single-part geometries.
2. **`02_facts_reclass.py` (Classification):** Runs a multi-tiered hierarchical CSV lookup to resolve messy raw agency codes, methods, and compound funding strings. Any remaining unmapped categories are automatically assigned via a statistical majority-vote loop.
3. **`03_facts_flatten.py` (Spatial Consolidation):** Cleans up mapping artifacts and prevents double-counting. It snaps together overlapping boundary edges and fixes small GIS coordinate gaps (up to 100 meters apart) so that slightly misaligned maps of the exact same treatment are merged into one clean boundary.
4. **`04_facts_finalize.py` (Clean and Finalize):** Calculates the final management acreage (`ACRES_MGT`) to the smaller of either the reported or physical values, wipes away intermediate scaffolding columns, and applies the production `TRACKER_FIELDS` schema.

* **Master Orchestrator:** Run `run_usfs_all.py` to execute the full 4-stage USFS pipeline sequentially.

---

### 2. DOI / BLM Keyword Data Pipeline Sequence (Pre-2024 BLM data)

The BLM pipeline focuses on keyword (REGEX) classification to extract structured treatment types from raw attribute text:


```

[01 Classify]  ──►   Manual Review  ──►    [02 Finalize]
Text-Mining          of automated          Apply Master
Keyword Search       classification        TRACKER_FIELDS

```

1. **`01_blm_classify.py` (Classification):** Ingests raw BLM treatment footprints from the BLM Vegetation Treatment Polygon system and applies an automated text-mining keyword search against names and comments. Segregates unmapped rows into a QA/QC layer for manual review.
2. **`02_blm_finalize.py` (Clean and Finalize):** Picks up post-reviewed, fully-classified BLM data, wipes away intermediate scaffolding columns, and applies the production `TRACKER_FIELDS` schema.

---

### 3. DOI / IFPERS Data Pipeline Sequence (Post-2024 DOI data, including BLM)

The DOI pipeline processes post-2024 IFPERS treatment data, using regex keyword engines and hierarchical crosswalks to standardize multi-agency Department of the Interior records (NPS, BIA, FWS, BLM):


```

[01 Ingestion]  ──►    [02 Reclass]   ──►        Manual Review  ──►   [03 Finalize]
Download post-         Regex & CSV Crosswalk     of automated         Enforce Schema &
2024 IFPERS            Categorization Engine     classification       Schema Finalization

```

1. **`01_ifpers_dwnld_post2024.py` (Data Ingestion):** Pulls raw IFPERS fuel treatment data directly from the DOI data gateway, filters features to the project boundary, and explodes multipart geometries into single-part features for spatial integrity.
2. **`02_ifpers_reclass_post2024.py` (Classification & Reclass):** Applies a dual-layer classification approach—first executing `ifpers_type_reclass.csv` crosswalks on standard agency codes, then running a regex-driven keyword search (`keywords.csv` / `keyword_search.py`) on treatment notes and project titles to map ambiguous records into standardized treatment tiers.
3. **`03_ifpers_finalize_post2024.py` (Clean and Finalize):** Calculates acreage, removes intermediate Regex matching scaffolding, and maps all standardized attributes directly into the production `TRACKER_FIELDS` master schema.
```

```
## Getting Started

### Prerequisites

* **ArcGIS Pro (v3.0+)** with the native `arcpy` library environment active.
* **Python 3.x** environment including `pandas`.

```
