"""
Copy reference layers into the production SpatialData dataset.

Each layer is copied from its source URL, reprojected to EPSG:3005 if needed,
and written over the previous copy. Every run is logged to epups-spatial\\logs.

Run again to refresh the copies. Remove any topology that uses these layers
before refreshing, because the copies are replaced.

Run on the VDI from X:\\epups-spatial:
    propy.bat scripts\\fetch_reference_data.py
"""

import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import builder, config, schema  # noqa: E402

# Imported after arcpy and epups, matching scripts/qa_validate.py.
from datetime import datetime  # noqa: E402

LOG_FILE = PROJECT_ROOT / "logs" / "reference_refresh.log"

PROTECTED_LANDS_SOURCE = (
    "ArcGIS Online item bd852a2c42924732a69b37632c25c585 "
    "(British Columbia Provincial Parks, Eco Reserves and Protected Areas), "
    "from Tantalis"
)

BC_BOUNDARY_SOURCE = (
    "ArcGIS Online service BC_Boundary (item 0f9e79a9b613415f9192083fa20a3c96), "
    "layer BC_Boundary_Terrestrial_Singlepart, from GeoBC"
)

REFERENCE_LAYERS = [
    {
        "name": "Ref_Protected_Lands",
        "url": (
            "https://services6.arcgis.com/ubm4tcTYICKBpist/arcgis/rest/services/"
            "British_Columbia_Provincial_Parks_Eco_Reserves_and_Protected_Areas_-_View/"
            "FeatureServer/10"
        ),
        "source": PROTECTED_LANDS_SOURCE,
    },
    {
        "name": "Ref_BC_Boundary",
        "url": (
            "https://services.arcgis.com/wjcPoefzjpzCgffS/arcgis/rest/services/"
            "BC_Boundary/FeatureServer/3"
        ),
        "source": BC_BOUNDARY_SOURCE,
    },
]

TEMP_COPY = "in_memory\\epups_ref_copy"
TEMP_PROJECTED = "in_memory\\epups_ref_projected"


def copy_reference_layer(gdb_path, layer):
    """Copy one layer into SpatialData. Returns (feature count, source spatial reference name)."""
    target = builder.object_paths(gdb_path)["dataset"] / layer["name"]

    for temp in (TEMP_COPY, TEMP_PROJECTED):
        if arcpy.Exists(temp):
            arcpy.management.Delete(temp)

    arcpy.management.CopyFeatures(layer["url"], TEMP_COPY)

    source_sr = arcpy.Describe(TEMP_COPY).spatialReference
    if source_sr.factoryCode == schema.SPATIAL_REFERENCE_WKID:
        to_write = TEMP_COPY
    else:
        arcpy.management.Project(
            TEMP_COPY, TEMP_PROJECTED, arcpy.SpatialReference(schema.SPATIAL_REFERENCE_WKID)
        )
        to_write = TEMP_PROJECTED

    if arcpy.Exists(str(target)):
        arcpy.management.Delete(str(target))

    arcpy.management.CopyFeatures(to_write, str(target))
    count = int(arcpy.management.GetCount(str(target))[0])

    for temp in (TEMP_COPY, TEMP_PROJECTED):
        if arcpy.Exists(temp):
            arcpy.management.Delete(temp)

    return count, source_sr.name


def log(message):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")


def main():
    gdb_path = config.PRODUCTION_PATH

    if not arcpy.Exists(str(gdb_path)):
        raise FileNotFoundError(f"Production database not found: {gdb_path}")

    print("=" * 60)
    print(f"Refreshing reference layers in: {gdb_path}")
    print("=" * 60)

    for layer in REFERENCE_LAYERS:
        count, source_sr = copy_reference_layer(gdb_path, layer)
        message = (
            f"{layer['name']}: {count} features, source spatial reference "
            f"{source_sr}, from {layer['url']} (source: {layer['source']})"
        )
        print(f"  {message}")
        log(message)

    print("=" * 60)
    print(f"Done. Log: {LOG_FILE}")


if __name__ == "__main__":
    main()
