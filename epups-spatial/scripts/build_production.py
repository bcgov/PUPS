"""
Build (or complete) the ePUPS spatial production database.

Creates the geodatabase if it is missing, then adds any missing
objects, fields and domains. Existing data is left unchanged, so it is
safe to rerun after schema.py gains new fields.

Production is currently the development file geodatabase in
epups/config.py, until the production server is chosen.
"""

import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arcpy  # noqa: E402

from epups import builder, config, schema  # noqa: E402


def main():
    print("=" * 60)
    print("ePUPS Spatial - Build Production Database")
    print("=" * 60)
    print(f"ArcGIS Pro version: {arcpy.GetInstallInfo()['Version']}")
    print(f"Schema version: {schema.SCHEMA_VERSION}")
    print(f"Production: {config.PRODUCTION_PATH}")

    if arcpy.Exists(str(config.PRODUCTION_PATH)):
        print("Geodatabase already exists; adding anything missing.")
    else:
        builder.create_file_gdb(config.PRODUCTION_FOLDER, config.PRODUCTION_GDB_NAME)

    paths = builder.build_schema(config.PRODUCTION_PATH)

    spatial = arcpy.Describe(str(paths["spatial"]))
    print("\nVerification")
    print("-" * 60)
    print(f"Feature class: {spatial.catalogPath}")
    print(f"Geometry: {spatial.shapeType}")
    print(f"Coordinate system: {spatial.spatialReference.name}")
    print(f"WKID: {spatial.spatialReference.factoryCode}")

    print("\nSUCCESS: Production schema is complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
