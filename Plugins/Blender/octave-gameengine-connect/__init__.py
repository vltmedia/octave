bl_info = {
    "name": "Octave Game Engine Connector",
    "author": "Octave Engine",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "Properties > Object > Octave Data, File > Export, 3D Viewport > Sidebar > OctaveEngine",
    "description": "Set Octave-specific metadata per object and export .gltf with extras",
    "category": "Import-Export",
}

import json
import os
import re
import struct

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    StringProperty,
    PointerProperty,
)
from bpy.types import PropertyGroup, Panel, Operator
from bpy_extras.io_utils import ExportHelper


# ---------------------------------------------------------------------------
# OctHashString – replicates Engine/Source/Engine/Utilities.cpp:377-398
# ---------------------------------------------------------------------------

def oct_hash_string(key):
    h = 0
    for ch in key:
        ki = ord(ch)
        high_order = h & 0xF8000000
        h = ((h << 5) & 0xFFFFFFFF) ^ ((high_order >> 27) & 0x1F) ^ ki
    return h


KNOWN_ASSET_TYPES = [
    "Font",
    "Material",
    "MaterialBase",
    "MaterialLite",
    "MaterialInstance",
    "ParticleSystem",
    "ParticleSystemInstance",
    "Scene",
    "SkeletalMesh",
    "SoundWave",
    "StaticMesh",
    "Texture",
]

TYPE_ID_TO_NAME = {oct_hash_string(n): n for n in KNOWN_ASSET_TYPES}

OCT_MAGIC = 0x4F435421

# DatumType enum values (mirrors Engine DatumType)
DATUM_TYPE_NAMES = {
    "Integer": 0, "Float": 1, "Bool": 2, "String": 3,
    "Vector2D": 4, "Vector": 5, "Color": 6, "Asset": 7,
    "Byte": 8, "Short": 11,
}
EDITABLE_TYPES = {0, 1, 2, 3, 4, 5, 6, 7, 8, 11}

# Module-level cache: { (scene_id, script_rel_path): [prop_dicts] }
_script_prop_cache = {}

# Flag to suppress the project-dir update callback during file load.
_loading_file = False


# ---------------------------------------------------------------------------
# .oct file scanner
# ---------------------------------------------------------------------------

def scan_oct_header(filepath):
    """Read an .oct file header and return (type_id, uuid) or None on failure."""
    try:
        with open(filepath, "rb") as f:
            data = f.read(21)
            if len(data) < 12:
                return None
            magic, version, type_id = struct.unpack_from("<III", data, 0)
            if magic != OCT_MAGIC:
                return None
            uuid = 0
            if version >= 12 and len(data) >= 21:
                # offset 12: 1 byte embedded flag, then 8 byte uuid
                uuid = struct.unpack_from("<Q", data, 13)[0]
            return (type_id, uuid)
    except (OSError, struct.error):
        return None


def scan_project_assets(project_dir, progress_fn=None):
    """Walk Assets/ and Packages/ for .oct files. Returns list of dicts.
    progress_fn(current, total) is called per file if provided."""
    search_roots = []
    assets_dir = os.path.join(project_dir, "Assets")
    packages_dir = os.path.join(project_dir, "Packages")
    if os.path.isdir(assets_dir):
        search_roots.append(assets_dir)
    if os.path.isdir(packages_dir):
        search_roots.append(packages_dir)

    # Collect all .oct paths first (fast), then read headers with progress.
    oct_files = []
    for root_dir in search_roots:
        for dirpath, _dirnames, filenames in os.walk(root_dir):
            for fname in filenames:
                if fname.lower().endswith(".oct"):
                    oct_files.append(os.path.join(dirpath, fname))

    total = len(oct_files)
    results = []
    for i, full_path in enumerate(oct_files):
        if progress_fn:
            progress_fn(i, total)
        header = scan_oct_header(full_path)
        if header is None:
            continue
        type_id, uuid = header
        type_name = TYPE_ID_TO_NAME.get(type_id, "Unknown")
        asset_name = os.path.splitext(os.path.basename(full_path))[0]
        rel_path = os.path.relpath(full_path, project_dir).replace("\\", "/")
        results.append({
            "name": asset_name,
            "type_name": type_name,
            "uuid": uuid,
            "relative_path": rel_path,
        })
    return results


# ---------------------------------------------------------------------------
# .lua script scanner
# ---------------------------------------------------------------------------

def scan_project_scripts(project_dir):
    """Walk Scripts/ and Packages/*/Scripts/ for .lua files.
    Returns list of (display_name, relative_path)."""
    results = []
    scripts_dir = os.path.join(project_dir, "Scripts")
    if os.path.isdir(scripts_dir):
        for dirpath, _dirnames, filenames in os.walk(scripts_dir):
            for fname in filenames:
                if not fname.lower().endswith(".lua"):
                    continue
                full_path = os.path.join(dirpath, fname)
                rel = os.path.relpath(full_path, project_dir).replace("\\", "/")
                results.append(rel)

    packages_dir = os.path.join(project_dir, "Packages")
    if os.path.isdir(packages_dir):
        for pkg_name in os.listdir(packages_dir):
            pkg_scripts = os.path.join(packages_dir, pkg_name, "Scripts")
            if not os.path.isdir(pkg_scripts):
                continue
            for dirpath, _dirnames, filenames in os.walk(pkg_scripts):
                for fname in filenames:
                    if not fname.lower().endswith(".lua"):
                        continue
                    full_path = os.path.join(dirpath, fname)
                    rel = os.path.relpath(full_path, project_dir).replace("\\", "/")
                    results.append(rel)
    return results


# ---------------------------------------------------------------------------
# Lua script property parser
# ---------------------------------------------------------------------------

def parse_lua_script_properties(filepath):
    """Parse a Lua script's GatherProperties() and Create() to extract
    editable property definitions and their default values.

    Returns list of {"name": str, "type": int, "default": value}.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            source = f.read()
    except OSError:
        return []

    # Find GatherProperties body
    gp_match = re.search(
        r'function\s+\w+:GatherProperties\s*\(\s*\)(.*?)^end',
        source, re.MULTILINE | re.DOTALL,
    )
    if not gp_match:
        return []

    gp_body = gp_match.group(1)

    # Extract property entries: { name = "xxx", type = DatumType.Yyy }
    prop_entries = re.findall(
        r'\{\s*name\s*=\s*"(\w+)"\s*,\s*type\s*=\s*DatumType\.(\w+)',
        gp_body,
    )

    if not prop_entries:
        return []

    # Build property list filtered to editable types
    props = []
    for prop_name, type_name in prop_entries:
        type_int = DATUM_TYPE_NAMES.get(type_name)
        if type_int is None or type_int not in EDITABLE_TYPES:
            continue
        props.append({"name": prop_name, "type": type_int, "default": None})

    if not props:
        return []

    # Find Create body for defaults
    create_match = re.search(
        r'function\s+\w+:Create\s*\(\s*\)(.*?)^end',
        source, re.MULTILINE | re.DOTALL,
    )
    if create_match:
        create_body = create_match.group(1)
        # Extract self.xxx = value assignments
        defaults = re.findall(r'self\.(\w+)\s*=\s*(.+?)$', create_body, re.MULTILINE)
        default_map = {name: val.strip() for name, val in defaults}

        for prop in props:
            raw = default_map.get(prop["name"])
            if raw is None:
                continue
            prop["default"] = _parse_lua_literal(raw, prop["type"])

    return props


def _parse_lua_literal(raw, prop_type):
    """Convert a Lua literal string to a Python value appropriate for prop_type."""
    # Strip trailing comments
    raw = re.sub(r'--.*$', '', raw).strip().rstrip(',')

    if raw == "nil":
        return None

    # Bool
    if prop_type == 2:  # Bool
        if raw == "true":
            return True
        if raw == "false":
            return False
        return None

    # Integer, Byte, Short
    if prop_type in (0, 8, 11):
        try:
            return int(float(raw))
        except (ValueError, OverflowError):
            return None

    # Float
    if prop_type == 1:
        try:
            return float(raw)
        except ValueError:
            return None

    # String
    if prop_type == 3:
        m = re.match(r'^["\'](.*)["\']\s*$', raw)
        return m.group(1) if m else None

    # Vector2D: Vec(x, y) or Vector.New(x, y)
    if prop_type == 4:
        m = re.match(r'(?:Vec|Vector\.New)\s*\(\s*([^,]+),\s*([^)]+)\)', raw)
        if m:
            try:
                return [float(m.group(1)), float(m.group(2))]
            except ValueError:
                pass
        return None

    # Vector: Vec(x, y, z) or Vector.New(x, y, z)
    if prop_type == 5:
        m = re.match(r'(?:Vec|Vector\.New)\s*\(\s*([^,]+),\s*([^,]+),\s*([^)]+)\)', raw)
        if m:
            try:
                return [float(m.group(1)), float(m.group(2)), float(m.group(3))]
            except ValueError:
                pass
        return None

    # Color: Vec(r, g, b, a) or Vector.New(r, g, b, a)
    if prop_type == 6:
        m = re.match(
            r'(?:Vec|Vector\.New)\s*\(\s*([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)',
            raw,
        )
        if m:
            try:
                return [float(m.group(1)), float(m.group(2)),
                        float(m.group(3)), float(m.group(4))]
            except ValueError:
                pass
        return None

    # Asset: string path
    if prop_type == 7:
        m = re.match(r'^["\'](.*)["\']\s*$', raw)
        return m.group(1) if m else None

    return None


def _get_or_parse(scene, script_path):
    """Get cached parse result or parse the Lua script and cache it."""
    global _script_prop_cache
    cache_key = (id(scene), script_path)
    if cache_key in _script_prop_cache:
        return _script_prop_cache[cache_key]

    raw_dir = scene.octave_project_dir
    if not raw_dir:
        return []

    project_dir = bpy.path.abspath(raw_dir)
    full_path = os.path.join(project_dir, script_path)
    if not os.path.isfile(full_path):
        return []

    result = parse_lua_script_properties(full_path)
    _script_prop_cache[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# PropertyGroups
# ---------------------------------------------------------------------------

class OctaveScannedAsset(PropertyGroup):
    name: StringProperty()
    type_name: StringProperty()
    uuid_str: StringProperty()
    relative_path: StringProperty()


class OctaveScannedScript(PropertyGroup):
    name: StringProperty()


class OctaveScriptPropValue(PropertyGroup):
    name: StringProperty()
    prop_type: IntProperty()  # DatumType int
    value_float: FloatProperty()
    value_int: IntProperty()
    value_bool: BoolProperty()
    value_string: StringProperty()
    value_vec2: FloatVectorProperty(size=2)
    value_vec3: FloatVectorProperty(size=3)
    value_color: FloatVectorProperty(size=4, subtype='COLOR', min=0.0, max=1.0)
    value_byte: IntProperty(min=0, max=255)
    value_short: IntProperty(min=-32768, max=32767)
    value_asset: StringProperty()


# ---------------------------------------------------------------------------
# Script property rebuild logic
# ---------------------------------------------------------------------------

def _rebuild_script_props(obj, scene):
    """Parse script and rebuild the object's octave_script_props collection."""
    props = obj.octave_props
    script_path = props.script_file
    if not script_path:
        obj.octave_script_props.clear()
        return

    parsed = _get_or_parse(scene, script_path)
    if not parsed:
        obj.octave_script_props.clear()
        return

    # Snapshot existing values by (name, type)
    old_values = {}
    for item in obj.octave_script_props:
        old_values[(item.name, item.prop_type)] = _read_prop_value(item)

    obj.octave_script_props.clear()

    for pdef in parsed:
        item = obj.octave_script_props.add()
        item.name = pdef["name"]
        item.prop_type = pdef["type"]

        # Restore old value if the same name+type existed, otherwise use parsed default
        key = (pdef["name"], pdef["type"])
        if key in old_values and old_values[key] is not None:
            _write_prop_value(item, old_values[key])
        elif pdef["default"] is not None:
            _write_prop_value(item, pdef["default"])


def _read_prop_value(item):
    """Read the appropriate value field from an OctaveScriptPropValue."""
    t = item.prop_type
    if t == 0:
        return item.value_int
    elif t == 1:
        return item.value_float
    elif t == 2:
        return item.value_bool
    elif t == 3:
        return item.value_string
    elif t == 4:
        return list(item.value_vec2)
    elif t == 5:
        return list(item.value_vec3)
    elif t == 6:
        return list(item.value_color)
    elif t == 7:
        return item.value_asset
    elif t == 8:
        return item.value_byte
    elif t == 11:
        return item.value_short
    return None


def _write_prop_value(item, value):
    """Write a value to the appropriate field of an OctaveScriptPropValue."""
    t = item.prop_type
    if t == 0:
        item.value_int = int(value)
    elif t == 1:
        item.value_float = float(value)
    elif t == 2:
        item.value_bool = bool(value)
    elif t == 3:
        item.value_string = str(value)
    elif t == 4:
        item.value_vec2 = (float(value[0]), float(value[1]))
    elif t == 5:
        item.value_vec3 = (float(value[0]), float(value[1]), float(value[2]))
    elif t == 6:
        item.value_color = (float(value[0]), float(value[1]),
                            float(value[2]), float(value[3]))
    elif t == 7:
        item.value_asset = str(value)
    elif t == 8:
        item.value_byte = int(value)
    elif t == 11:
        item.value_short = int(value)


def _on_script_file_changed(self, context):
    """Update callback for script_file property."""
    obj = context.object
    if obj is not None:
        _rebuild_script_props(obj, context.scene)


class OctaveObjectProperties(PropertyGroup):
    mesh_type: EnumProperty(
        name="Mesh Type",
        description="How this object should be imported into Octave",
        items=[
            ("NODE3D", "Node3D", "Import as plain Node3D (no mesh)"),
            ("STATIC_MESH", "StaticMesh", "Import as StaticMesh3D"),
            ("INSTANCED_MESH", "InstancedMesh", "Import as InstancedMesh3D"),
        ],
        default="STATIC_MESH",
    )
    octave_asset: StringProperty(
        name="Octave Asset",
        description="Asset name to link instead of the imported mesh",
        default="",
    )
    script_file: StringProperty(
        name="Script",
        description="Lua script to assign to this node on import (e.g. Goblin.lua)",
        default="",
        update=_on_script_file_changed,
    )
    material_type: EnumProperty(
        name="Material Type",
        description="Material shading type for imported meshes (only applies when no Octave Asset is set)",
        items=[
            ("DEFAULT", "Default", "Use scene import default"),
            ("UNLIT", "Unlit", "Unlit material (no lighting)"),
            ("LIT", "Lit", "Lit material (standard lighting)"),
            ("VERTEX_COLOR", "Vertex Color", "Use vertex colors"),
        ],
        default="DEFAULT",
    )
    main_camera: BoolProperty(
        name="Main Camera",
        description="Set this camera as the main camera on import",
        default=False,
    )


# ---------------------------------------------------------------------------
# Refresh script properties operator
# ---------------------------------------------------------------------------

class OCTAVE_OT_refresh_script_props(Operator):
    bl_idname = "octave.refresh_script_props"
    bl_label = "Refresh Script Properties"
    bl_description = "Re-parse the Lua script and refresh editable properties"

    def execute(self, context):
        obj = context.object
        if obj is None:
            self.report({"WARNING"}, "No active object")
            return {"CANCELLED"}

        props = obj.octave_props
        script_path = props.script_file
        if not script_path:
            self.report({"WARNING"}, "No script assigned")
            return {"CANCELLED"}

        # Clear cache entry so it re-parses
        global _script_prop_cache
        cache_key = (id(context.scene), script_path)
        _script_prop_cache.pop(cache_key, None)

        _rebuild_script_props(obj, context.scene)
        n = len(obj.octave_script_props)
        self.report({"INFO"}, f"Refreshed: {n} editable properties")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Asset matching helper
# ---------------------------------------------------------------------------

def _match_asset_for_object(obj, catalog):
    """Find best catalog match for obj.name. Returns item.name or ""."""
    raw_name = obj.name
    # Strip Blender duplicate suffix (.001, .002, etc.)
    base_name = re.sub(r'\.\d{3,}$', '', raw_name)

    best = ""
    best_score = 0
    for item in catalog:
        asset_leaf = item.name.rsplit("/", 1)[-1]

        if asset_leaf == base_name:
            return item.name
        elif asset_leaf.lower() == base_name.lower():
            if best_score < 3:
                best, best_score = item.name, 3
        elif base_name.lower() in asset_leaf.lower():
            if best_score < 2:
                best, best_score = item.name, 2
        elif asset_leaf.lower() in base_name.lower():
            if best_score < 1:
                best, best_score = item.name, 1

    return best


# ---------------------------------------------------------------------------
# Refresh logic (called from operator and update callback)
# ---------------------------------------------------------------------------

def _do_refresh(scene):
    """Scan project directory and repopulate catalogs."""
    global _script_prop_cache
    _script_prop_cache.clear()

    raw = scene.octave_project_dir
    if not raw:
        return (0, 0)

    project_dir = bpy.path.abspath(raw)
    if not os.path.isdir(project_dir):
        return (0, 0)

    wm = bpy.context.window_manager
    window = bpy.context.window

    # Show wait cursor, progress bar, and status text
    if window:
        window.cursor_set('WAIT')
    wm.progress_begin(0, 1000)
    bpy.context.workspace.status_text_set("Scanning Octave Project Directory...")

    def _on_progress(current, total):
        if total > 0:
            wm.progress_update(int(current / total * 1000))

    # Refresh asset catalog
    scene.octave_asset_catalog.clear()
    assets = scan_project_assets(project_dir, progress_fn=_on_progress)
    for a in assets:
        item = scene.octave_asset_catalog.add()
        # Strip .oct extension — engine paths are e.g. "Assets/Models/SM_Cube"
        rel_no_ext = a["relative_path"]
        if rel_no_ext.lower().endswith(".oct"):
            rel_no_ext = rel_no_ext[:-4]
        item.name = rel_no_ext
        item.type_name = a["type_name"]
        item.uuid_str = str(a["uuid"])
        item.relative_path = a["relative_path"]

    # Refresh script catalog
    scene.octave_script_catalog.clear()
    scripts = scan_project_scripts(project_dir)
    for s in scripts:
        item = scene.octave_script_catalog.add()
        item.name = s

    wm.progress_end()
    bpy.context.workspace.status_text_set(None)
    if window:
        window.cursor_set('DEFAULT')

    return (len(assets), len(scripts))


def _on_project_dir_changed(self, context):
    if not _loading_file:
        _do_refresh(self)


# ---------------------------------------------------------------------------
# Refresh Operator
# ---------------------------------------------------------------------------

class OCTAVE_OT_refresh_project(Operator):
    bl_idname = "octave.refresh_project"
    bl_label = "Refresh Octave Project"
    bl_description = "Rescan project directory for assets and scripts"

    def execute(self, context):
        scene = context.scene
        raw = scene.octave_project_dir
        if not raw:
            self.report({"WARNING"}, "No project directory set")
            return {"CANCELLED"}

        project_dir = bpy.path.abspath(raw)
        if not os.path.isdir(project_dir):
            self.report({"WARNING"}, f"Directory not found: {project_dir}")
            return {"CANCELLED"}

        has_assets = os.path.isdir(os.path.join(project_dir, "Assets"))
        has_scripts = os.path.isdir(os.path.join(project_dir, "Scripts"))
        if not has_assets and not has_scripts:
            self.report({"WARNING"}, "Directory has no Assets/ or Scripts/ subfolder")
            return {"CANCELLED"}

        num_assets, num_scripts = _do_refresh(scene)
        self.report({"INFO"}, f"Found {num_assets} assets, {num_scripts} scripts")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Match Asset Operators
# ---------------------------------------------------------------------------

class OCTAVE_OT_match_asset(Operator):
    bl_idname = "octave.match_asset"
    bl_label = "Match Asset"
    bl_description = "Auto-match Octave Asset based on object name"

    def execute(self, context):
        obj = context.object
        if obj is None:
            self.report({"WARNING"}, "No active object")
            return {"CANCELLED"}
        catalog = context.scene.octave_asset_catalog
        if len(catalog) == 0:
            self.report({"WARNING"}, "Asset catalog is empty — refresh project first")
            return {"CANCELLED"}
        match = _match_asset_for_object(obj, catalog)
        if match:
            obj.octave_props.octave_asset = match
            self.report({"INFO"}, f"Matched '{obj.name}' -> '{match}'")
        else:
            self.report({"WARNING"}, f"No match found for '{obj.name}'")
        return {"FINISHED"}


class OCTAVE_OT_match_assets_selected(Operator):
    bl_idname = "octave.match_assets_selected"
    bl_label = "Match Assets"
    bl_description = "Auto-match Octave Asset for all selected objects"

    def execute(self, context):
        catalog = context.scene.octave_asset_catalog
        if len(catalog) == 0:
            self.report({"WARNING"}, "Asset catalog is empty — refresh project first")
            return {"CANCELLED"}
        matched = 0
        skipped = 0
        for obj in context.selected_objects:
            if obj.type == 'CAMERA':
                continue
            match = _match_asset_for_object(obj, catalog)
            if match:
                obj.octave_props.octave_asset = match
                matched += 1
            else:
                skipped += 1
        self.report({"INFO"}, f"Matched {matched} object(s), {skipped} unmatched")
        return {"FINISHED"}


# ---------------------------------------------------------------------------
# Sidebar Panel: Octave Project (3D Viewport N-Panel)
# ---------------------------------------------------------------------------

class OCTAVE_PT_scene_project(Panel):
    bl_label = "Octave Project"
    bl_idname = "OCTAVE_PT_scene_project"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OctaveEngine"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.prop(scene, "octave_project_dir", text="Project Dir")
        layout.operator("octave.refresh_project", text="Refresh", icon="FILE_REFRESH")

        num_assets = len(scene.octave_asset_catalog)
        num_scripts = len(scene.octave_script_catalog)
        layout.label(text=f"Assets: {num_assets}  |  Scripts: {num_scripts}")

        layout.operator("octave.match_assets_selected", text="Match Assets", icon="VIEWZOOM")


# ---------------------------------------------------------------------------
# Object Properties Panel
# ---------------------------------------------------------------------------

class OCTAVE_PT_object_data(Panel):
    bl_label = "Octave Data"
    bl_idname = "OCTAVE_PT_object_data"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.object is not None

    def draw(self, context):
        layout = self.layout
        obj = context.object
        props = obj.octave_props

        if obj.type == 'CAMERA':
            layout.prop(props, "main_camera")
        else:
            layout.prop(props, "mesh_type")
            row = layout.row(align=True)
            row.prop_search(
                props, "octave_asset",
                context.scene, "octave_asset_catalog",
                text="Octave Asset", icon="ASSET_MANAGER",
            )
            row.operator("octave.match_asset", text="", icon="VIEWZOOM")
            layout.prop(props, "material_type")

        layout.prop_search(
            props, "script_file",
            context.scene, "octave_script_catalog",
            text="Script", icon="SCRIPT",
        )

        # Script Properties section
        if props.script_file and len(obj.octave_script_props) > 0:
            box = layout.box()
            header_row = box.row()
            header_row.label(text="Script Properties", icon="PROPERTIES")
            header_row.operator("octave.refresh_script_props", text="", icon="FILE_REFRESH")

            for item in obj.octave_script_props:
                row = box.row()
                t = item.prop_type
                if t == 1:    # Float
                    row.prop(item, "value_float", text=item.name)
                elif t == 0:  # Integer
                    row.prop(item, "value_int", text=item.name)
                elif t == 2:  # Bool
                    row.prop(item, "value_bool", text=item.name)
                elif t == 3:  # String
                    row.prop(item, "value_string", text=item.name)
                elif t == 4:  # Vector2D
                    row.prop(item, "value_vec2", text=item.name)
                elif t == 5:  # Vector
                    row.prop(item, "value_vec3", text=item.name)
                elif t == 6:  # Color
                    row.prop(item, "value_color", text=item.name)
                elif t == 7:  # Asset
                    row.prop_search(
                        item, "value_asset",
                        context.scene, "octave_asset_catalog",
                        text=item.name, icon="ASSET_MANAGER",
                    )
                elif t == 8:  # Byte
                    row.prop(item, "value_byte", text=item.name)
                elif t == 11:  # Short
                    row.prop(item, "value_short", text=item.name)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def _sync_custom_properties(obj, scene):
    """Copy OctaveObjectProperties to Blender custom properties so
    the glTF exporter writes them into extras automatically."""
    props = obj.octave_props

    if obj.type == 'CAMERA':
        obj["octave_main_camera"] = props.main_camera
    else:
        mesh_type_map = {"NODE3D": "Node3D", "STATIC_MESH": "StaticMesh", "INSTANCED_MESH": "InstancedMesh"}
        obj["mesh_type"] = mesh_type_map.get(props.mesh_type, "StaticMesh")
        obj["octave_asset"] = props.octave_asset
        if props.material_type != "DEFAULT":
            obj["octave_material_type"] = props.material_type
        else:
            obj["octave_material_type"] = "LIT"

    # Convert catalog paths to engine-expected format:
    #   "Scripts/Goblin.lua"                      -> "Goblin.lua"
    #   "Packages/Addon/Scripts/AI/Enemy.lua"     -> "Packages/Addon/AI/Enemy.lua"
    script_path = props.script_file
    if script_path.startswith("Scripts/"):
        script_path = script_path[len("Scripts/"):]
    elif script_path.startswith("Packages/"):
        parts = script_path.split("/", 3)  # ["Packages", pkgName, "Scripts", rest]
        if len(parts) >= 4 and parts[2] == "Scripts":
            script_path = f"Packages/{parts[1]}/{parts[3]}"
    obj["octave_script"] = script_path

    # Serialize script property overrides
    if len(obj.octave_script_props) > 0:
        props_dict = {}
        types_dict = {}
        for item in obj.octave_script_props:
            types_dict[item.name] = item.prop_type
            val = _read_prop_value(item)
            props_dict[item.name] = val
        obj["octave_script_props"] = json.dumps(props_dict)
        obj["octave_script_props_types"] = json.dumps(types_dict)
    else:
        # Clean up stale keys if script was removed
        for key in ("octave_script_props", "octave_script_props_types"):
            if key in obj:
                del obj[key]

    # Look up UUID from catalog
    obj["octave_asset_uuid"] = "0"
    if props.octave_asset:
        for item in scene.octave_asset_catalog:
            if item.name == props.octave_asset:
                obj["octave_asset_uuid"] = item.uuid_str
                break


class OCTAVE_OT_export_for_octave(Operator, ExportHelper):
    bl_idname = "octave.export_for_octave"
    bl_label = "Octave Engine Scene (.glb)"
    bl_description = "Export scene as .glb with Octave extras"

    filename_ext = ".glb"
    filter_glob: StringProperty(default="*.glb", options={"HIDDEN"})

    export_selected: BoolProperty(
        name="Selected Only",
        description="Export only selected objects",
        default=False,
    )
    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers before exporting",
        default=True,
    )

    def execute(self, context):
        scene = context.scene

        objects = context.selected_objects if self.export_selected else bpy.data.objects
        for obj in objects:
            if hasattr(obj, "octave_props"):
                _sync_custom_properties(obj, scene)

        export_kwargs = dict(
            filepath=self.filepath,
            export_format="GLB",
            export_extras=True,
            export_yup=True,
            export_apply=self.apply_modifiers,
            export_texcoords=True,
            export_normals=True,
            export_cameras=True,
            export_lights=True,
            export_animations=True,
        )

        if self.export_selected:
            export_kwargs["use_selection"] = True

        bpy.ops.export_scene.gltf(**export_kwargs)

        self.report({"INFO"}, f"Exported Octave scene to {self.filepath}")
        return {"FINISHED"}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "export_selected")
        layout.prop(self, "apply_modifiers")


def menu_func_export(self, context):
    self.layout.operator(OCTAVE_OT_export_for_octave.bl_idname, text="Octave Engine Scene (.glb)")


# ---------------------------------------------------------------------------
# Scan prompt shown after opening a file with a project directory set
# ---------------------------------------------------------------------------

class OCTAVE_OT_scan_prompt(Operator):
    bl_idname = "octave.scan_prompt"
    bl_label = "Octave Game Engine Connect"
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.label(text="An Octave project directory is set for this file.")
        layout.label(text="The asset and script catalogs need to be scanned")
        layout.label(text="before you can use the connector.")
        layout.separator()
        layout.label(text="You can also do this later with the Refresh button")
        layout.label(text="in the OctaveEngine sidebar panel.")

    def execute(self, context):
        num_assets, num_scripts = _do_refresh(context.scene)
        self.report({"INFO"}, f"Scanned project: {num_assets} assets, {num_scripts} scripts")
        return {"FINISHED"}


def _deferred_scan_prompt():
    """Timer callback to show the scan prompt after file load."""
    try:
        if bpy.context.scene and bpy.context.scene.octave_project_dir:
            bpy.ops.octave.scan_prompt('INVOKE_DEFAULT')
    except RuntimeError:
        pass
    return None


@bpy.app.handlers.persistent
def _load_pre_handler(dummy):
    global _loading_file
    _loading_file = True


@bpy.app.handlers.persistent
def _load_post_handler(dummy):
    global _loading_file
    _loading_file = False

    scene = bpy.context.scene
    if scene and scene.octave_project_dir:
        # Clear stale catalog data baked into the .blend file
        scene.octave_asset_catalog.clear()
        scene.octave_script_catalog.clear()
        bpy.app.timers.register(_deferred_scan_prompt, first_interval=0.5)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

classes = (
    OctaveScannedAsset,
    OctaveScannedScript,
    OctaveScriptPropValue,
    OctaveObjectProperties,
    OCTAVE_OT_refresh_script_props,
    OCTAVE_OT_scan_prompt,
    OCTAVE_PT_scene_project,
    OCTAVE_PT_object_data,
    OCTAVE_OT_refresh_project,
    OCTAVE_OT_match_asset,
    OCTAVE_OT_match_assets_selected,
    OCTAVE_OT_export_for_octave,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Object.octave_props = PointerProperty(type=OctaveObjectProperties)
    bpy.types.Object.octave_script_props = CollectionProperty(type=OctaveScriptPropValue)

    bpy.types.Scene.octave_project_dir = StringProperty(
        name="Octave Project Directory",
        description="Root directory of the Octave project (contains Assets/, Scripts/)",
        subtype="DIR_PATH",
        default="",
        update=_on_project_dir_changed,
    )
    bpy.types.Scene.octave_asset_catalog = CollectionProperty(type=OctaveScannedAsset)
    bpy.types.Scene.octave_script_catalog = CollectionProperty(type=OctaveScannedScript)

    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)

    bpy.app.handlers.load_pre.append(_load_pre_handler)
    bpy.app.handlers.load_post.append(_load_post_handler)


def unregister():
    if _load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_load_post_handler)
    if _load_pre_handler in bpy.app.handlers.load_pre:
        bpy.app.handlers.load_pre.remove(_load_pre_handler)

    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    del bpy.types.Scene.octave_script_catalog
    del bpy.types.Scene.octave_asset_catalog
    del bpy.types.Scene.octave_project_dir
    del bpy.types.Object.octave_script_props
    del bpy.types.Object.octave_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
