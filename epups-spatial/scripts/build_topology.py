"""
Create the ePUPS topology in the production SpatialData dataset, then validate it.

Rules:
- ePup_Spatial must be covered by Ref_Protected_Lands (permits sit inside protected land)
- ePup_Spatial must be covered by Ref_BC_Boundary (permits sit inside the province)

There is deliberately no overlap rule: permits may overlap each other.

Run fetch_reference_data.py first, so the reference layers exist.
Existing topology is left in place, and its rules are only added if missing.

Run on the VDI from X:\\epups-spatial:
    propy.bat scripts\\build_topology.py
"""

import sys
from pathlib import Path

# Make the epups package importable when run from any folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import arcpy  # noqa: E402

from epups import builder, config, schema  # noqa: E402

TOPOLOGY_NAME = "ePUPS_Topology"
COVERED_BY = "Must Be Covered By Feature Class Of (Area-Area)"
PROTECTED_LANDS = "Ref_Protected_Lands"
BC_BOUNDARY = "Ref_BC_Boundary"


def main():
    gdb_path = config.PRODUCTION_PATH
    paths = builder.object_paths(gdb_path)
    dataset = paths["dataset"]
    topology = dataset / TOPOLOGY_NAME

    print("=" * 60)
    print(f"Building topology in: {dataset}")
    print("=" * 60)

    for name in (schema.SPATIAL_FC_NAME, PROTECTED_LANDS, BC_BOUNDARY):
        if not arcpy.Exists(str(dataset / name)):
            raise FileNotFoundError(
                f"{name} not found in SpatialData. Run fetch_reference_data.py first."
            )

    if arcpy.Exists(str(topology)):
        print(f"Topology already exists: {topology}")
    else:
        arcpy.management.CreateTopology(str(dataset), TOPOLOGY_NAME)
        print(f"Created topology: {topology}")

    for name in (schema.SPATIAL_FC_NAME, PROTECTED_LANDS, BC_BOUNDARY):
        try:
            arcpy.management.AddFeatureClassToTopology(
                str(topology), str(dataset / name), 1, 1
            )
            print(f"  Added to topology: {name}")
        except arcpy.ExecuteError as error:
            print(f"  Already in topology or failed: {name}\n    {error}")

    for reference in (PROTECTED_LANDS, BC_BOUNDARY):
        try:
            arcpy.management.AddRuleToTopology(
                str(topology),
                COVERED_BY,
                str(dataset / schema.SPATIAL_FC_NAME),
                "",
                str(dataset / reference),
            )
            print(f"  Added rule: {schema.SPATIAL_FC_NAME} {COVERED_BY} {reference}")
        except arcpy.ExecuteError as error:
            print(f"  Rule not added (may already exist): {reference}\n    {error}")

    print("\nValidating topology...")
    arcpy.management.ValidateTopology(str(topology))
    print("Validation finished. Open the topology in ArcGIS Pro's Error Inspector to see errors.")
    print("=" * 60)


if __name__ == "__main__":
    main()
