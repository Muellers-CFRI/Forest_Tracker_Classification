import sys
import arcpy

from scripts.utils.paths import ensure_directories
from scripts.doi.blm_01_finalize import run_blm_stage_1, run_blm_stage_2


def main():
    # 1. SETUP: Create folders if they don't exist
    ensure_directories()

    print("--- Colorado Forest Tracker Classification ---")

    print("\nAvailable Steps:")
    print(" [1] Stage 1: Prep, Filter, and Keyword Classification")
    print(" [2] Stage 2: Finalize Reviewed Data (Calculate Acres/Mgt)")
    print(" [Q] Quit")

    choice = input("\nWhich stage would you like to run? (1/2/Q): ").strip().upper()

    if choice == "1":
        print("/nStarting Stage 1...")
        run_blm_stage_1()
        print("\nNEXT STEP: Open ArcGIS Pro, review the 'unclassified' file,")
        print("and move corrected records into 'classified_temp' before running Stage 2.")

    elif choice == "2":
        print("\nStarting Stage 2...")
        run_blm_stage_2()

    elif choice == "Q":
        print("Exiting...")
        sys.exit()

    else:
        print("Invalid choice. Please run the script again and select 1, 2, or Q.")


if __name__ == "__main__":
    main()
