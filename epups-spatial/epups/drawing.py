"""
Map layers the toolbox adds to the open ArcGIS Pro project.

Used by the toolbox inside ArcGIS Pro (it needs the open project).

- "Drawing:" layer. Start or Resume Permit adds a second layer of the
  workspace's ePup_Spatial at the top of the map, named for the permit, for
  example "Drawing: authorization 7000002 (version 1)". It shows only that
  version's polygons, outlined in bright blue, and has its own template in
  Create Features with the same name. Drawing with that template (or the
  ePup_Spatial one) adds polygons to the permit; the attribute rules link
  them to it. Finish or Save Draft removes the layer.
- "QA:" layer. Check Workspace adds a layer of the polygons that failed QA,
  outlined in thick red, and selects them, so they can be found on the map
  and in the attribute table.
"""

from pathlib import Path

import arcpy

from epups import builder, versioning

PREFIX = "Drawing: "
QA_PREFIX = "QA: "

BRIGHT_BLUE = {"RGB": [0, 170, 255, 100]}
PALE_BLUE = {"RGB": [0, 170, 255, 25]}
BRIGHT_RED = {"RGB": [255, 0, 0, 100]}
PALE_RED = {"RGB": [255, 0, 0, 30]}


def layer_name(version):
    return f"{PREFIX}authorization {version.authorization_id} (version {version.number})"


def show_permit(spatial_path, version):
    """Add the drawing layer for version to the map showing spatial_path. Returns the layer name, or None."""
    map_ = _workspace_map(spatial_path)
    if map_ is None:
        return None
    _remove_drawing_layers(map_)

    layer = map_.addDataFromPath(str(spatial_path))
    layer.name = layer_name(version)
    layer.definitionQuery = f"VERSION_ID = {int(version.version_id)}"
    _symbolize(layer, PALE_BLUE, BRIGHT_BLUE)
    _name_templates(layer, version)
    return layer.name


def show_qa_failures(spatial_path, object_ids):
    """
    Show the polygons that failed QA: a "QA:" layer of just those polygons,
    outlined in red, and selected on the workspace's ePup_Spatial layer.
    Removes the layer if nothing failed. Returns the layer name, or None.
    """
    map_ = _workspace_map(spatial_path)
    if map_ is None:
        return None
    _remove_layers(map_, QA_PREFIX)
    object_ids = sorted(object_ids)
    for layer in _source_layers(map_, spatial_path):
        layer.setSelectionSet(object_ids, "NEW")
    if not object_ids:
        return None

    layer = map_.addDataFromPath(str(spatial_path))
    layer.name = f"{QA_PREFIX}failing polygons ({len(object_ids)})"
    oid_field = arcpy.Describe(str(spatial_path)).OIDFieldName
    layer.definitionQuery = f"{oid_field} IN ({', '.join(str(oid) for oid in object_ids)})"
    _symbolize(layer, PALE_RED, BRIGHT_RED, width=4)
    _remove_templates(layer)
    return layer.name


def selected_authorizations(gdb_path):
    """AUTHORIZATIONIDs of the polygons selected on the map, from any layer of the workspace's polygons."""
    paths = builder.object_paths(gdb_path)
    map_ = _workspace_map(paths["spatial"])
    if map_ is None:
        return []
    object_ids = set()
    for layer in _source_layers(map_, paths["spatial"]):
        object_ids.update(layer.getSelectionSet() or [])
    if not object_ids:
        return []

    versions = versioning.read_versions(paths["version"])
    with arcpy.da.SearchCursor(str(paths["spatial"]), ["OID@", "VERSION_ID"]) as cursor:
        version_ids = {version_id for oid, version_id in cursor if oid in object_ids}
    return sorted({versions[v].authorization_id for v in version_ids if v in versions})


def clear():
    """Remove every drawing layer from the open project's maps."""
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
    except (OSError, RuntimeError, ValueError):
        return
    for map_ in aprx.listMaps():
        _remove_drawing_layers(map_)


def _workspace_map(spatial_path):
    """The open project's map that shows spatial_path, else the active map."""
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
    except (OSError, RuntimeError, ValueError):
        return None
    target = _normalise(spatial_path)
    for map_ in aprx.listMaps():
        for layer in map_.listLayers():
            if layer.supports("DATASOURCE") and _normalise(layer.dataSource) == target:
                return map_
    return aprx.activeMap


def _source_layers(map_, spatial_path):
    """Layers in map_ that draw spatial_path, apart from the QA layer."""
    target = _normalise(spatial_path)
    return [
        layer for layer in map_.listLayers()
        if layer.supports("DATASOURCE") and _normalise(layer.dataSource) == target
        and not layer.name.startswith(QA_PREFIX)
    ]


def _remove_drawing_layers(map_):
    _remove_layers(map_, PREFIX)


def _remove_layers(map_, prefix):
    for layer in map_.listLayers():
        if layer.name.startswith(prefix):
            map_.removeLayer(layer)


def _symbolize(layer, fill, outline, width=3):
    symbology = layer.symbology
    if hasattr(symbology, "renderer"):
        if symbology.renderer.type != "SimpleRenderer":
            symbology.updateRenderer("SimpleRenderer")
        symbol = symbology.renderer.symbol
        symbol.color = fill
        symbol.outlineColor = outline
        symbol.outlineWidth = width
        layer.symbology = symbology


def _remove_templates(layer):
    """The QA layer is for looking at, not drawing into."""
    try:
        definition = layer.getDefinition("V3")
        definition.featureTemplates = []
        definition.autoGenerateFeatureTemplates = False
        layer.setDefinition(definition)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass


def _name_templates(layer, version):
    """
    Name the layer's editing template after the permit and default its
    VERSION_ID, so Create Features shows which permit it adds to. If Pro
    hasn't made the template yet it makes one when editing starts, named
    after the layer, which says the same thing.
    """
    try:
        definition = layer.getDefinition("V3")
        definition.autoGenerateFeatureTemplates = True
        for template in definition.featureTemplates or []:
            template.name = layer.name
            values = dict(template.defaultValues or {})
            values["VERSION_ID"] = int(version.version_id)
            template.defaultValues = values
        layer.setDefinition(definition)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass  # the layer name still shows the permit


def _normalise(path):
    return str(Path(str(path))).lower().rstrip("\\")
