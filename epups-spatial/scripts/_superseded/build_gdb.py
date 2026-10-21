

"""

Create the initial ePUPS spatial development file geodatabase.



This script creates an empty file geodatabase only.

It does not create tables or feature classes yet.

"""



from pathlib import Path

import arcpy





# Temporary development location.

# Update this value when the project gets a permanent data location.

DATA_ROOT = Path(

    r"\\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\source_data"

)



GDB_NAME = "epups_spatial_dev.gdb"

GDB_FOLDER = DATA_ROOT / "epups_spatial_dev"

GDB_PATH = GDB_FOLDER / GDB_NAME





def main():

    print("=" * 60)

    print("ePUPS Spatial - Development Geodatabase Setup")

    print("=" * 60)



    print(f"ArcGIS Pro version: {arcpy.GetInstallInfo()['Version']}")

    print(f"Output folder: {GDB_FOLDER}")

    print(f"Geodatabase: {GDB_PATH}")



    # Refuse to overwrite an existing geodatabase.

    if arcpy.Exists(str(GDB_PATH)):

        raise FileExistsError(

            f"Geodatabase already exists; nothing was overwritten:\n{GDB_PATH}"

        )



    # Ensure the parent directory exists.

    GDB_FOLDER.mkdir(parents=True, exist_ok=True)



    # Create the file geodatabase.

    arcpy.management.CreateFileGDB(

        out_folder_path=str(GDB_FOLDER),

        out_name=GDB_NAME

    )



    # Verify creation.

    if not arcpy.Exists(str(GDB_PATH)):

        raise RuntimeError(

            f"ArcPy did not report the geodatabase as existing:\n{GDB_PATH}"

        )



    description = arcpy.Describe(str(GDB_PATH))



    print("\nSUCCESS: Development geodatabase created.")

    print(f"Catalog path: {description.catalogPath}")

    print(f"Exists: {arcpy.Exists(str(GDB_PATH))}")

    print("=" * 60)





if __name__ == "__main__":

    main()

