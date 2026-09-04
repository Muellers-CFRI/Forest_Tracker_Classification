"""
---------------------------------------------------------------------------
Title: Master USFS FACTS Pipeline Sequencing Orchestrator

Purpose:
    Acts as the central execution engine for the USFS data pipeline. This
    script automates the end-to-end processing sequence—from remote ingestion
    to final schema deployment—by executing each standalone stage as an
    isolated native subprocess.

Major Steps:
    1. Initialize environment configurations and reset global scratch workspaces.
    2. Execute `01_facts_download_QAQC.py` to harvest and clip regional data.
    3. Execute `02_facts_reclass.py` to map raw activities via crosswalk tables.
    4. Execute `03_facts_flatten.py` to dissolve spatial duplicate footprints.
    5. Execute `04_facts_finalize.py` to clamp final acreages and apply the
       master tracker dashboard schema.
    6. Monitor exit codes for each stage to ensure error-free completion
       before proceeding to the next downstream script.

Inputs:
    Downstream pipeline python scripts (Stages 01 through 04).

Outputs:
    A fully processed, schema-conformed, production-ready `usfs_final`
    feature class, built seamlessly in a single manual click.
---------------------------------------------------------------------------
"""

import subprocess

scripts = [
    "01_facts_dwnld_QAQC.py",
    "02_facts_reclass.py",
    "03_facts_flatten.py",
    "04_facts_finalize.py"
]

print ("Starting Automated USFS Pipeline...")
for script in scripts:
    print(f"\n================= Running: {script}")
    subprocess.run(["python", script], check=True)

print("\n USFS Pipeline Complete!!!")
