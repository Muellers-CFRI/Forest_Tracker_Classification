import arcpy
import os

from scripts.utils.paths import ensure_directories
from scripts.blm.blm_finalize import run_blm_pipeline


def main():
    # 1. SETUP: Create folders if they don't exist
    ensure_directories()

    print("--- Colorado Forest Tracker Classification ---")
