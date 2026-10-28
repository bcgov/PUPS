"""
Create the ePUPS topology in the production SpatialData dataset, then validate it.

Rules:
- ePup_Spatial must be covered by Ref_Protected_Lands (permits sit inside protected land)
- ePup_Spatial must be covered by Ref_BC_Boundary (permits sit inside the province)

There is deliberately no overlap rule: permits may overlap each other.

Run fetch_reference_data.py first, so the reference layers exist.
Rules are only added when the topology is created. If it already exists, its
rules are left alone, so reruns do not duplicate them. To rebuild the rules,
delete the topology in ArcGIS Pro and run this again.

The validation errors are exported to logs\\topology_errors.gdb (not to
production), and the count is printed.

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
ERROR_GDB_NAME = "topology_errors.gdb"
ERROR_BASENAME = "topology_errors"

arcpy.env.overwriteOutput = True


def export_errors(topology):
    """Export the topology errors to a separate geodatabase. Returns the error count."""
    error_folder = PROJECT_ROOT / "logs"
    error_folder.mkdir(parents=True, exist_ok=True)
    error_gdb = error_folder / ERROR_GDB_NAME
    if not arcpy.Exists(str(error_gdb)):
        arcpy.management.CreateFileGDB(str(error_folder), ERROR_GDB_NAME)

    arcpy.management.ExportTopologyErrors(str(topology), str(error_gdb), ERROR_BASENAME)

    count = 0
    for suffix in ("point", "line", "poly"):
        error_class = error_gdb / f"{ERROR_BASENAME}_{suffix}"
        if arcpy.Exists(str(error_class)):
            count += int(arcpy.management.GetCount(str(error_class))[0])
    print(f"Errors exported to: {error_gdb}")
    return count


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
        print(f"Topology already exists, rules left as they are: {topology}")
        rules_needed = False
    else:
        arcpy.management.CreateTopology(str(dataset), TOPOLOGY_NAME)
        print(f"Created topology: {topology}")
        rules_needed = True

    for name in (schema.SPATIAL_FC_NAME, PROTECTED_LANDS, BC_BOUNDARY):
        try:
            arcpy.management.AddFeatureClassToTopology(
                str(topology), str(dataset / name), 1, 1
            )
            print(f"  Added to topology: {name}")
        except arcpy.ExecuteError as error:
            print(f"  Already in topology or failed: {name}\n    {error}")

    if rules_needed:
        for reference in (PROTECTED_LANDS, BC_BOUNDARY):
            arcpy.management.AddRuleToTopology(
                str(topology),
                COVERED_BY,
                str(dataset / schema.SPATIAL_FC_NAME),
                "",
                str(dataset / reference),
            )
            print(f"  Added rule: {schema.SPATIAL_FC_NAME} {COVERED_BY} {reference}")

    print("\nValidating topology...")
    arcpy.management.ValidateTopology(str(topology))
    error_count = export_errors(topology)

    print(f"\nRESULT: {error_count} topology error(s). Open the Error Inspector to see them.")
    print("=" * 60)


if __name__ == "__main__":
    main()
