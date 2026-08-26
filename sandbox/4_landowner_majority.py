import os
import arcpy
import pandas as pd
from datetime import datetime

# Environmental settings
arcpy.env.overwriteOutput = True
arcpy.env.qualifiedFieldNames = False
fldr = r'E:\CFRI\FOREST_TRACKER\ALL_DATA_COMPILE\LANDOWNER_MAJORITY'
scratch_fldr = os.path.join(fldr, "SCRATCH")
scratch = os.path.join(scratch_fldr, "SCRATCH.gdb")

# Input data
coMap = os.path.join(fldr, "INPUT", "COMaP-v8_final_public", "COMaP-v8_final_public.shp")
landowner_update = os.path.join(fldr, "INPUT", "LANDOWNER.gdb", "ALL_DATA_COMPILE_20250128")

# Run Repair geometry to avoid potential topology issues
arcpy.RepairGeometry_management(landowner_update)

# Add and calculate an original ID field if not already present
owner_fld = "FT_LABEL"
print("Calculating an original ID field")
if "ORGID" not in [field.name for field in arcpy.ListFields(landowner_update)]:
    arcpy.AddField_management(landowner_update, "ORGID", "LONG", 10)
    arcpy.CalculateField_management(landowner_update, "ORGID", "!OBJECTID! + 1", "PYTHON_9.3", "")

# Intersect and dissolve management data with coMap
lo_intersect = arcpy.Intersect_analysis([landowner_update, coMap], scratch + "/lo_intersect")
lo_dissolve = arcpy.Dissolve_management(lo_intersect, scratch + "/lo_dissolve", ["ORGID", owner_fld])

# Add and calculate acreage field
arcpy.AddField_management(lo_dissolve, "NEWACRES", "DOUBLE")
arcpy.CalculateField_management(lo_dissolve, "NEWACRES", "!shape.area@acres!", "PYTHON_9.3", "")

# Convert to Pandas DataFrame and process majority landowner
print("Start majority landowner Pandas code")
table_data = arcpy.da.TableToNumPyArray(lo_dissolve, ("ORGID", owner_fld, "NEWACRES"))
df = pd.DataFrame(table_data)

# Group by the ORGID and grab the row with the maximum calculated acres
majority_landowners = df.loc[df.groupby("ORGID")["NEWACRES"].idxmax()]
output_csv = os.path.join(scratch_fldr, "landowner_majority_output.csv")
majority_landowners.to_csv(output_csv, index=False)

# Create a dictionary from the Pandas csv output and use update cursor to 'join' fields by ORGID
print("Update majority Landowner column")
landownerDict = dict(zip(majority_landowners["ORGID"], majority_landowners[owner_fld]))
with arcpy.da.UpdateCursor(landowner_update, ["ORGID", "LANDOWNER", "OBJECTID"]) as cursor:
    for row in cursor:
        org_id = row[0]
        if org_id in landownerDict:
            row[1] = landownerDict[org_id]
            cursor.updateRow(row)
        else:
            print("Unable to update ObjectID: '{}'".format(str(row[2])))

# Delete interim data
print("Delete interim data")
arcpy.DeleteField_management(landowner_update, "ORGID")
arcpy.Delete_management(output_csv)
arcpy.Delete_management(lo_intersect)
arcpy.Delete_management(lo_dissolve)

# Export final copy
print("Create Final Copy")
final_output = os.path.join(fldr, "OUTPUT", "OUTPUT.gdb", "ALL_DATA_COMPILE_" + datetime.now().strftime("%Y%m%d"))
arcpy.CopyFeatures_management(landowner_update, final_output)

print("Process completed successfully. Final output saved at: ", final_output)
