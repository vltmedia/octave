bl_info = {
    "name": "Octave Game Engine Connector",
    "author": "Octave Engine",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "Properties > Object > Octave Data, File > Export, 3D Viewport > Sidebar > OctaveEngine",
    "description": "Set Octave-specific metadata per object and export .gltf with extras",
    "category": "Import-Export",
}

import os
import re
import struct

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
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


def scan_project_assets(project_dir):
    """Walk Assets/ and Packages/ for .oct files. Returns list of dicts."""
    results = []
    search_roots = []
    assets_dir = os.path.join(project_dir, "Assets")
    packages_dir = os.path.join(project_dir, "Packages")
    if os.path.isdir(assets_dir):
        search_roots.append(assets_dir)
    if os.path.isdir(packages_dir):
        search_roots.append(packages_dir)

    for root_dir in search_roots:
        for dirpath, _dirnames, filenames in os.walk(root_dir):
            for fname in filenames:
                if not fname.lower().endswith(".oct"):
                    continue
                full_path = os.path.join(dirpath, fname)
                header = scan_oct_header(full_path)
                if header is None:
                    continue
                type_id, uuid = header
                type_name = TYPE_ID_TO_NAME.get(type_id, "Unknown")
                asset_name = os.path.splitext(fname)[0]
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
# PropertyGroups
# ---------------------------------------------------------------------------

class OctaveScannedAsset(PropertyGroup):
    name: StringProperty()
    type_name: StringProperty()
    uuid_str: StringProperty()
    relative_path: StringProperty()


class OctaveScannedScript(PropertyGroup):
    name: StringProperty()


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
    )
    main_camera: BoolProperty(
        name="Main Camera",
        description="Set this camera as the main camera on import",
        default=False,
    )


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
    raw = scene.octave_project_dir
    if not raw:
        return (0, 0)

    project_dir = bpy.path.abspath(raw)
    if not os.path.isdir(project_dir):
        return (0, 0)

    # Refresh asset catalog
    scene.octave_asset_catalog.clear()
    assets = scan_project_assets(project_dir)
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

    return (len(assets), len(scripts))


def _on_project_dir_changed(self, context):
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

        layout.prop_search(
            props, "script_file",
            context.scene, "octave_script_catalog",
            text="Script", icon="SCRIPT",
        )


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
# Registration
# ---------------------------------------------------------------------------

classes = (
    OctaveScannedAsset,
    OctaveScannedScript,
    OctaveObjectProperties,
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


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    del bpy.types.Scene.octave_script_catalog
    del bpy.types.Scene.octave_asset_catalog
    del bpy.types.Scene.octave_project_dir
    del bpy.types.Object.octave_props

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
