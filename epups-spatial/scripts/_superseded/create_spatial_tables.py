
"""
Create the initial ePUPS spatial database objects.

Creates:
- ePup_Spatial_Version: nonspatial table at the geodatabase root
- ePup_Spatial: polygon feature class inside SpatialData
- ePup_Spatial_Status: coded value domain for SPATIAL_STATUS

Field definitions come from schema/schema.py.
Existing objects and fields are left unchanged.
"""

import sys
from pathlib import Path

import arcpy

# Make the schema package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from schema.schema import (  # noqa: E402
    SPATIAL_FIELDS,
    SPATIAL_STATUS_DOMAIN,
    SPATIAL_STATUS_VALUES,
    VERSION_TABLE_FIELDS,
)

# --------------------------------------------------
# Configuration
# --------------------------------------------------

DATA_ROOT = Path(
    r"\\spatialfiles.bcgov\Work\srm\gss\projects\gr_2026_472_park_use_permits\source_data"
)

GDB_PATH = DATA_ROOT / "epups_spatial_dev" / "epups_spatial_dev.gdb"
FEATURE_DATASET = GDB_PATH / "SpatialData"

VERSION_TABLE = GDB_PATH / "ePup_Spatial_Version"
SPATIAL_FEATURE_CLASS = FEATURE_DATASET / "ePup_Spatial"


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def add_missing_fields(table_path, field_defs):
    existing = {field.name.upper() for field in arcpy.ListFields(str(table_path))}

    for field in field_defs:
        name = field["name"]

        if name.upper() in existing:
            print(f"  Field already exists; leaving unchanged: {name}")
            continue

        kwargs = {
            "field_alias": field["alias"],
            "field_is_nullable": "NULLABLE" if field["nullable"] else "NON_NULLABLE",
        }
        if "length" in field:
            kwargs["field_length"] = field["length"]

        arcpy.management.AddField(
            str(table_path), name, field["type"], **kwargs
        )
        print(f"  Added field: {name}")


def ensure_status_domain():
    domains = {domain.name for domain in arcpy.da.ListDomains(str(GDB_PATH))}

    if SPATIAL_STATUS_DOMAIN in domains:
        print(f"  Domain already exists; leaving unchanged: {SPATIAL_STATUS_DOMAIN}")
    else:
        arcpy.management.CreateDomain(
            str(GDB_PATH),
            SPATIAL_STATUS_DOMAIN,
            "ePUPS spatial workflow status",
            "TEXT",
            "CODED",
        )
        for value in SPATIAL_STATUS_VALUES:
            arcpy.management.AddCodedValueToDomain(
                str(GDB_PATH), SPATIAL_STATUS_DOMAIN, value, value
            )
        print(f"  Created domain: {SPATIAL_STATUS_DOMAIN}")

    for field in arcpy.ListFields(str(SPATIAL_FEATURE_CLASS), "SPATIAL_STATUS"):
        if field.domain == SPATIAL_STATUS_DOMAIN:
            print("  Domain already assigned to SPATIAL_STATUS")
            return

    arcpy.management.AssignDomainToField(
        str(SPATIAL_FEATURE_CLASS), "SPATIAL_STATUS", SPATIAL_STATUS_DOMAIN
    )
    print("  Assigned domain to SPATIAL_STATUS")


def verify(paths):
    print("\nVerification")
    print("-" * 60)

    for path in paths:
        if not arcpy.Exists(str(path)):
            raise RuntimeError(f"Verification failed: {path}")

        description = arcpy.Describe(str(path))
        print(f"Name: {description.name}")
        print(f"Path: {description.catalogPath}")
        print(f"Data type: {description.dataType}")

        if path == SPATIAL_FEATURE_CLASS:
            print(f"Geometry: {description.shapeType}")
            print(
                "Coordinate system: "
                f"{description.spatialReference.name}"
            )
            print(
                "WKID: "
                f"{description.spatialReference.factoryCode}"
            )

        print()


# --------------------------------------------------
# Main
# --------------------------------------------------

def main():
    arcpy.env.overwriteOutput = False

    print("=" * 60)
    print("Creating ePUPS spatial database objects")
    print("=" * 60)

    if not arcpy.Exists(str(GDB_PATH)):
        raise RuntimeError(f"Geodatabase not found: {GDB_PATH}")

    if not arcpy.Exists(str(FEATURE_DATASET)):
        raise RuntimeError(f"Feature dataset not found: {FEATURE_DATASET}")

    # Version table at the geodatabase root.
    print("\nVersion table")
    if arcpy.Exists(str(VERSION_TABLE)):
        print(f"Already exists; leaving unchanged: {VERSION_TABLE}")
    else:
        arcpy.management.CreateTable(str(GDB_PATH), "ePup_Spatial_Version")
        print(f"Created version table: {VERSION_TABLE}")
    add_missing_fields(VERSION_TABLE, VERSION_TABLE_FIELDS)

    # Polygon feature class inside SpatialData.
    print("\nPolygon feature class")
    if arcpy.Exists(str(SPATIAL_FEATURE_CLASS)):
        print(f"Already exists; leaving unchanged: {SPATIAL_FEATURE_CLASS}")
    else:
        arcpy.management.CreateFeatureclass(
            str(FEATURE_DATASET),
            "ePup_Spatial",
            "POLYGON",
            spatial_reference=arcpy.SpatialReference(3005),
        )
        print(f"Created polygon feature class: {SPATIAL_FEATURE_CLASS}")
    add_missing_fields(SPATIAL_FEATURE_CLASS, SPATIAL_FIELDS)

    # Coded domain for SPATIAL_STATUS.
    print("\nStatus domain")
    ensure_status_domain()

    verify((VERSION_TABLE, SPATIAL_FEATURE_CLASS))

    print("SUCCESS: Database objects and fields are present.")


if __name__ == "__main__":
    main()
