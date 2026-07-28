# Colorado Forest Tracker GIS Pipeline

An automated data engineering pipeline designed to harvest, clean, reclassify, and flatten public federal land management data for direct integration into the Forest Tracker dashboard. 

This repository standardizes and aggregates overlapping spatial accomplishment datasets from multiple federal agencies (starting with USFS FACTS) into a single, footprint-clamped, schema-conformed master database.

---

## 🏗️ System Architecture & Directory Layout

The codebase uses a strict separation of concerns. Core parameters live in a centralized configuration hub, utility tools handle dynamic environment calculations, and individual agency workflows are isolated into step-by-step sequential scripts.

```text
my_gis_pipeline/
├── README.md               <-- Main repository overview and setup guide
├── config/
│   ├── config.py           <-- Central brain (Years, Master Schema, URL registries)
│   ├── usfs_activity_reclass.csv   <-- Static Tier 1 Activity mapping tables
│   ├── usfs_method_reclass.csv     <-- Static Tier 2 Method mapping tables
│   ├── usfs_equip_reclass.csv      <-- Static Tier 3 Equipment mapping tables
│   └── usfs_fund_reclass.csv       <-- Static Funding source crosswalk lookups
│
└── scripts/
    ├── usfs/
    │   ├── 01_facts_download_QAQC.py
    │   ├── 02_facts_reclass.py
    │   ├── 03_facts_flatten.py
    │   └── 04_facts_finalize.py
    │   └──run_usfs_all.py <-- Master Orchestrator (Runs the entire USFS stack)
    │
    └── utils/
        ├── paths.py        <-- Dynamic workspace, scratch, and database path builder
        └── gis_tools.py    <-- Universal shared ArcPy processing operations

```

---

## ⚙️ USFS Data Pipeline Sequence

The pipeline executes in four distinct, defensive stages to protect data integrity and avoid "double-counting" overlapping management acreage:

```
[01 Ingestion]  ──►   [02 Reclass] ──► [03 Flatten] ──►    [04 Finalize]
   Download &         Hierarchical      100m Spatial       Acreage Clamp &
  Boundary Clip       CSV Crosswalk      Dissolve          Master Schema

```

1. **01_facts_download_QAQC.py (Ingestion):** Automatically harvests multiple compressed `.gdb.zip` endpoints directly from the USFS Enterprise Data Warehouse, clips them to the regional boundary (Colorado) to cut processing overhead by 90%, and explodes complex multipart features into distinct single-part geometries.
2. **02_facts_reclass.py (Normalization):** Runs a multi-tiered hierarchical lookup to resolve messy raw agency codes, methods, and compound funding strings. Any remaining unmapped categories are automatically assigned via an in-memory Pandas statistical majority-vote loop.
3. **03_facts_flatten.py (Spatial Consolidation):** Resolves spatial overlap inflation by executing a specialized `arcpy.management.Dissolve` utilizing an aggressive 100-meter clustering tolerance to compress field-GPS drift.
4. **04_facts_finalize.py (Enforcement):** Applies a rigorous mathematical reality check. It reads raw polygon geometry arrays (`SHAPE@AREA`) and clamps the final management acreage (`ACRES_MGT`) to the smaller of either the reported or physical values, wipes away intermediate scaffolding columns, and applies the production `TRACKER_FIELDS` schema.

---

## 🚀 Getting Started

### Prerequisites

* **ArcGIS Pro (v3.0+)** with the native `arcpy` library environment active.
* **Python 3.x** environment including `pandas`.

```

### Execution

To execute the entire end-to-end data processing stack for the U.S. Forest Service without manually stepping through individual files, run the sequence orchestrator from your terminal:

```bash
python scripts/run_usfs_all.py

```

```

```
