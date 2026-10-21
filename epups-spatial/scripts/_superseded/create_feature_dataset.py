
"""Create the spatial feature dataset in the development geodatabase."""

from pathlib import Path
import arcpy

DATA_ROOT = Path(
    r"\\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\source_data"
)

GDB_PATH = DATA_ROOT / "epups_spatial_dev" / "epups_spatial_dev.gdb"
FEATURE_DATASET_NAME = "SpatialData"
FEATURE_DATASET_PATH = GDB_PATH / FEATURE_DATASET_NAME

def main():
    if not arcpy.Exists(str(GDB_PATH)):
        raise FileNotFoundError(f"Geodatabase not found: {GDB_PATH}")

    if arcpy.Exists(str(FEATURE_DATASET_PATH)):
        print(f"Feature dataset already exists: {FEATURE_DATASET_PATH}")
        return

    # EPSG:3005 - NAD 1983 BC Environment Albers
    spatial_reference = arcpy.SpatialReference(3005)

    arcpy.management.CreateFeatureDataset(
        out_dataset_path=str(GDB_PATH),
        out_name=FEATURE_DATASET_NAME,
        spatial_reference=spatial_reference
    )

    description = arcpy.Describe(str(FEATURE_DATASET_PATH))

    print("Feature dataset created successfully.")
    print(f"Path: {description.catalogPath}")
    print(f"Spatial reference: {description.spatialReference.name}")
    print(f"WKID: {description.spatialReference.factoryCode}")

if __name__ == "__main__":
    main()
