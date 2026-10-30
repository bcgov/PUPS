"""
Create the ArcGIS Pro project that goes with an editor workspace.

The project is saved next to the workspace geodatabase with the same name
(for example ePUPS_Temp_Workspace.aprx). It has one map: the workspace's polygons
to edit, over the production protected lands and BC boundary layers, both
semi-transparent, over the Esri topographic basemap. The reference layers
have no editing templates, so editors only draw into the workspace. The
workspace is the project's default geodatabase, and the ePUPS toolbox is in
the project.

Inside ArcGIS Pro, set_up_current_project() instead turns the open project
into a workspace project, adding the same map to it.

ArcPy cannot create a project from nothing, so create_project() copies a blank one:
config.PROJECT_TEMPLATE if it exists, otherwise the blank project that
ships with ArcGIS Pro.

Use config.PROJECT_TEMPLATE. Pro reopens the map window saved in the
template at the view it was saved with, and ignores the map's default
camera. Pro's blank project was saved looking at Australia, so every
workspace opened there. A template saved in Pro, zoomed to BC, opens on BC.
"""

import os
import stat
from pathlib import Path

import arcpy

from epups import builder, config, schema

PROTECTED_LANDS = "Ref_Protected_Lands"
BC_BOUNDARY = "Ref_BC_Boundary"

# Percent transparency of the reference layers (0 is solid, 100 is invisible).
REFERENCE_TRANSPARENCY = 50

LIGHT_GREEN = {"RGB": [150, 210, 130, 100]}
DARK_GREEN = {"RGB": [60, 120, 50, 100]}
PALE_GREY = {"RGB": [235, 235, 235, 100]}
GREY = {"RGB": [110, 110, 110, 100]}
HOLLOW = {"RGB": [0, 0, 0, 0]}
RED = {"RGB": [200, 0, 0, 100]}

# The default basemap of a new ArcGIS Pro map. If it can't be added (for
# example, not signed in), the public topographic tile service is used.
BASEMAP = "Topographic"
BASEMAP_FALLBACK_URL = "https://services.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer"

# Roughly how wide the map view is on screen, in metres. Sets the start scale
# so all of BC fits.
START_VIEW_SCREEN_METRES = 0.18

# The ePUPS toolbox, added to every workspace project and the starter project.
# The shared path is preferred, so projects work for people without an X: drive.
_LOCAL_TOOLBOX = Path(__file__).resolve().parent.parent / "ePUPS.pyt"
TOOLBOX = config.SHARED_TOOLBOX if config.SHARED_TOOLBOX.exists() else _LOCAL_TOOLBOX

# Blank project shipped with ArcGIS Pro, relative to the install folder.
PRO_BLANK_PROJECT = Path("Resources/ArcToolBox/Services/routingservices/data/Blank.aprx")


def find_template():
    if config.PROJECT_TEMPLATE.exists():
        return config.PROJECT_TEMPLATE
    pro_blank = Path(arcpy.GetInstallInfo()["InstallDir"]) / PRO_BLANK_PROJECT
    if pro_blank.exists():
        print(f"  No template at {config.PROJECT_TEMPLATE}. Using Pro's blank project, "
              f"which may open away from BC (see Setup in the README).")
        return pro_blank
    raise FileNotFoundError(
        f"No blank project to copy. In ArcGIS Pro, create a new Map project, "
        f"save it as {config.PROJECT_TEMPLATE}, close Pro and run this again."
    )


def create_project(gdb_path, production_path=None):
    """
    Create the workspace's .aprx next to it and return its path.

    Run it outside ArcGIS Pro (a script, or the toolbox's separate process; see
    scripts/create_project.py). Inside Pro, Pro keeps the new file open, and the
    Pro window that then opens it opens it read-only.
    """
    gdb_path = Path(gdb_path)
    production_path = Path(production_path) if production_path else config.PRODUCTION_PATH
    aprx_path = gdb_path.with_suffix(".aprx")
    if aprx_path.exists():
        raise FileExistsError(f"Project already exists: {aprx_path}")

    template = find_template()
    print("\nArcGIS Pro project")
    print(f"  Template: {template}")
    template_project = arcpy.mp.ArcGISProject(str(template))
    template_project.saveACopy(str(aprx_path))
    del template_project

    aprx = arcpy.mp.ArcGISProject(str(aprx_path))
    aprx.homeFolder = str(gdb_path.parent)
    aprx.defaultGeodatabase = str(gdb_path)

    maps = aprx.listMaps()
    map_ = maps[0] if maps else aprx.createMap(gdb_path.stem, "MAP")
    map_.name = gdb_path.stem
    _build_map(map_, gdb_path, production_path)
    _add_toolbox(aprx)
    aprx.save()
    print(f"  Saved: {aprx_path}")
    return aprx_path


def create_starter_project(production_path=None):
    """
    Make config.STARTER_PROJECT: a copy of the template with the ePUPS toolbox
    attached and one map of protected lands and the BC boundary, for context.
    Replaces an existing starter. Marks the file read-only, so Pro won't save
    over it. Returns its path.
    """
    production_path = Path(production_path) if production_path else config.PRODUCTION_PATH
    starter = config.STARTER_PROJECT
    if starter.exists():
        os.chmod(starter, stat.S_IWRITE)
        starter.unlink()
        print(f"  Replaced: {starter}")

    template = find_template()
    print("\nStarter project")
    print(f"  Template: {template}")
    arcpy.mp.ArcGISProject(str(template)).saveACopy(str(starter))

    aprx = arcpy.mp.ArcGISProject(str(starter))
    aprx.homeFolder = str(starter.parent)
    maps = aprx.listMaps()
    map_ = maps[0] if maps else aprx.createMap("ePUPS", "MAP")
    map_.name = "ePUPS - start here"
    map_.spatialReference = arcpy.SpatialReference(schema.SPATIAL_REFERENCE_WKID)

    reference = builder.object_paths(production_path)["dataset"]
    _add_basemap(map_)
    for name, fill, outline in (
        (BC_BOUNDARY, PALE_GREY, GREY),
        (PROTECTED_LANDS, LIGHT_GREEN, DARK_GREEN),
    ):
        layer = _add_layer(map_, reference / name, fill, outline, 0.5, REFERENCE_TRANSPARENCY)
        if layer:
            _remove_templates(layer)
    _set_start_view(map_, reference / BC_BOUNDARY)
    _add_toolbox(aprx)
    aprx.save()
    del aprx

    os.chmod(starter, stat.S_IREAD)
    print(f"  Saved (read-only): {starter}")
    return starter


def is_starter_project(aprx_path):
    try:
        return Path(aprx_path).resolve() == config.STARTER_PROJECT.resolve()
    except OSError:
        return False


def set_up_current_project(gdb_path, production_path=None):
    """
    Turn the project open in ArcGIS Pro into a workspace project, for the
    toolbox's Create Workspace tool: add a map named after the workspace with
    the same layers as create_project(), open it on BC, make the workspace the
    project's default geodatabase, and add the toolbox. Other maps in the
    project are left alone. The project isn't saved; the editor saves it.
    Returns the map's name.
    """
    gdb_path = Path(gdb_path)
    production_path = Path(production_path) if production_path else config.PRODUCTION_PATH
    aprx = arcpy.mp.ArcGISProject("CURRENT")

    print("\nThis project")
    aprx.defaultGeodatabase = str(gdb_path)
    print(f"  Default geodatabase: {gdb_path}")
    map_ = aprx.createMap(gdb_path.stem, "MAP")
    print(f"  Added map: {map_.name}")
    _build_map(map_, gdb_path, production_path)
    _add_toolbox(aprx)

    # A new map view opens at the map's default camera, set to BC by _build_map.
    try:
        map_.openView()
        bc_boundary = builder.object_paths(production_path)["dataset"] / BC_BOUNDARY
        if arcpy.Exists(str(bc_boundary)) and aprx.activeView is not None:
            aprx.activeView.camera.setExtent(arcpy.Describe(str(bc_boundary)).extent)
    except (AttributeError, RuntimeError, ValueError) as error:
        print(f"  Open the {map_.name} map from the Catalog pane (Maps): {error}")
    return map_.name


def _build_map(map_, gdb_path, production_path):
    """The workspace map's layers, symbols and start view."""
    # BC Albers, like the data. Otherwise the basemap sets the map to Web Mercator.
    map_.spatialReference = arcpy.SpatialReference(schema.SPATIAL_REFERENCE_WKID)

    workspace = builder.object_paths(gdb_path)
    reference = builder.object_paths(production_path)["dataset"]

    # Added bottom to top, so the polygons being edited draw over the reference layers.
    _add_basemap(map_)
    for name, fill, outline in (
        (BC_BOUNDARY, PALE_GREY, GREY),
        (PROTECTED_LANDS, LIGHT_GREEN, DARK_GREEN),
    ):
        layer = _add_layer(map_, reference / name, fill, outline, 0.5, REFERENCE_TRANSPARENCY)
        if layer:
            _remove_templates(layer)
    _add_layer(map_, workspace["spatial"], HOLLOW, RED, 2)
    map_.addTable(arcpy.mp.Table(str(workspace["version"])))
    print(f"  Added table: {workspace['version'].name}")

    _set_start_view(map_, reference / BC_BOUNDARY)


def _add_basemap(map_):
    if any(layer.isBasemapLayer for layer in map_.listLayers()):
        print("  Basemap already in the template")
        return
    before = len(map_.listLayers())
    try:
        map_.addBasemap(BASEMAP)
    except (RuntimeError, ValueError) as error:
        print(f"  Basemap {BASEMAP} not available: {error}")
    if len(map_.listLayers()) > before:
        print(f"  Added basemap: {BASEMAP}")
        return
    try:
        map_.addDataFromPath(BASEMAP_FALLBACK_URL)
        print(f"  Added basemap: {BASEMAP_FALLBACK_URL}")
    except (RuntimeError, ValueError) as error:
        print(f"  Could not add a basemap (add one from Map > Basemap): {error}")


def _add_toolbox(aprx):
    """Add the ePUPS toolbox to the project, keeping the toolboxes already in it."""
    try:
        toolboxes = [
            toolbox for toolbox in (aprx.toolboxes or [])
            if Path(toolbox["toolboxPath"]).name.lower() != TOOLBOX.name.lower()
        ]
        toolboxes.append({"toolboxPath": str(TOOLBOX), "isDefaultToolbox": False})
        aprx.updateToolboxes(toolboxes)
        print(f"  Added toolbox: {TOOLBOX}")
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError) as error:
        print(f"  Could not add the toolbox (add {TOOLBOX} from Catalog > Toolboxes): {error}")


def _remove_templates(layer):
    """Clear the layer's editing templates, so it isn't offered in Create Features."""
    definition = layer.getDefinition("V3")
    definition.featureTemplates = []
    # Otherwise Pro makes new templates for a layer that has none when the project opens.
    definition.autoGenerateFeatureTemplates = False
    layer.setDefinition(definition)
    print(f"  Editing templates removed: {layer.name} (reference only)")


def _add_layer(map_, path, fill, outline, width, transparency=0):
    if not arcpy.Exists(str(path)):
        print(f"  Skipped, not found: {path}")
        return None
    layer = map_.addDataFromPath(str(path))
    symbology = layer.symbology
    if hasattr(symbology, "renderer"):
        if symbology.renderer.type != "SimpleRenderer":
            symbology.updateRenderer("SimpleRenderer")
        symbol = symbology.renderer.symbol
        symbol.color = fill
        symbol.outlineColor = outline
        symbol.outlineWidth = width
        layer.symbology = symbology
    layer.transparency = transparency
    print(f"  Added layer: {layer.name} ({transparency}% transparent)")
    return layer


def _set_start_view(map_, bc_boundary):
    """
    Open on the whole of BC. The camera is written into the map definition
    (CIM), because the map in Pro's blank project has an empty camera that
    map.defaultCamera can't set (it reads back as nan, and Pro then opened
    over Australia).
    """
    if not arcpy.Exists(str(bc_boundary)):
        return
    # Set again here, in case adding the basemap changed it.
    map_.spatialReference = arcpy.SpatialReference(schema.SPATIAL_REFERENCE_WKID)
    extent = arcpy.Describe(str(bc_boundary)).extent
    try:
        definition = map_.getDefinition("V3")
        camera = definition.defaultCamera
        if camera is None:
            camera = arcpy.cim.CreateCIMObjectFromClassName("CIMViewCamera", "V3")
        camera.x = (extent.XMin + extent.XMax) / 2
        camera.y = (extent.YMin + extent.YMax) / 2
        camera.z = 0
        camera.scale = max(extent.width, extent.height) / START_VIEW_SCREEN_METRES
        camera.pitch = -90
        camera.heading = 0
        camera.roll = 0
        definition.defaultCamera = camera
        map_.setDefinition(definition)

        saved = map_.getDefinition("V3").defaultCamera
        print(f"  Start view: x {saved.x:,.0f}, y {saved.y:,.0f}, scale 1:{saved.scale:,.0f}, "
              f"map coordinates {map_.spatialReference.name}")
    except (AttributeError, RuntimeError, ValueError) as error:
        print(f"  Could not set the start view (use Zoom To Layer on Ref_BC_Boundary): {error}")
