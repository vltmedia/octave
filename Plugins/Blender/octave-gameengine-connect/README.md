# Octave Game Engine Connector — Blender Addon

Bridge between Blender and the Octave Engine for scene export with per-object metadata.

## Installation

1. Open Blender (3.0+)
2. Go to **Edit > Preferences > Add-ons > Install**
3. Navigate to this folder (or a zip of it) and install
4. Enable **"Octave Game Engine Connector"** in the add-ons list

## Setup

1. Open the **N-panel** in the 3D Viewport (press `N`)
2. Select the **OctaveEngine** tab
3. Set the **Project Dir** to the root of your Octave project (the folder containing `Assets/` and `Scripts/`)
4. Click **Refresh** to scan for assets and scripts
5. The status line shows `Assets: N | Scripts: N` confirming the scan

The scanner looks for `.oct` files in both `Assets/` and `Packages/` directories, and `.lua` scripts in both `Scripts/` and `Packages/*/Scripts/`.

## Per-Object Properties

Select any object and open **Properties > Object > Octave Data** to configure:

### Mesh Type

Dropdown controlling how the object is imported into the Octave Editor (meshes only):

| Value | Description |
|-------|-------------|
| **Node3D** | Plain transform node — no mesh is assigned |
| **StaticMesh** | Standard mesh node (default) — creates a `StaticMesh3D` |
| **InstancedMesh** | GPU-instanced mesh node — creates an `InstancedMesh3D` |

### Octave Asset

Search field to link an existing project asset by its project-relative path (e.g., `Assets/Meshes/SM_Cube`). When set, the Editor resolves the asset by UUID first, then by name, falling back to the embedded glTF mesh.

A magnifying-glass button next to the field auto-matches the asset based on the object name (see [Match Asset](#match-asset) below).

### Script

Search field to attach a Lua script to the node. Scripts are shown as project-relative paths (e.g., `Scripts/Player.lua`). The `Scripts/` prefix is stripped on export since the engine prepends it automatically. Package scripts (`Packages/Addon/Scripts/AI/Enemy.lua`) are remapped to `Packages/Addon/AI/Enemy.lua`.

### Main Camera (cameras only)

Boolean toggle shown when a Camera object is selected. When enabled, the exported camera node is flagged so the Editor sets it as the active camera on import.

## Match Asset

The addon can automatically match Octave assets to Blender objects based on their names.

### Single Object

In **Properties > Object > Octave Data**, click the magnifying-glass icon next to the **Octave Asset** field. The addon matches the active object's name against the asset catalog and fills in the field.

### Bulk Match

In the **3D Viewport > Sidebar > OctaveEngine** tab, click **Match Assets** to auto-match all selected objects at once. Camera objects are skipped. A report shows how many objects were matched.

### Matching Algorithm

Blender duplicate suffixes (`.001`, `.002`, etc.) are stripped before matching. The matcher compares the object name against the leaf name of each catalog entry (e.g., `SM_Cube` from `Assets/Models/SM_Cube`) with the following priority:

1. **Exact match** — `SM_Cube` == `SM_Cube`
2. **Case-insensitive exact** — `sm_cube` == `SM_Cube`
3. **Object name is substring of asset** — `Cube` found in `SM_Cube`
4. **Asset name is substring of object** — `SM` found in `SM_Cube_Large`

The first exact match wins immediately; otherwise the best fuzzy match is used.

## Exporting

1. Go to **File > Export > Octave Engine Scene (.glb)**
2. Choose the output path and click **Export**

The addon syncs all Octave properties to Blender custom properties before invoking the glTF exporter with `export_extras=True`, embedding the metadata into each node's `extras` block. The scene is exported as a single `.glb` binary file.

## GLB Extras Format

Each node in the exported GLB file may contain an `extras` object:

```json
{
  "mesh_type": "StaticMesh",
  "octave_asset": "Assets/Meshes/SM_Cube",
  "octave_asset_uuid": "12345678",
  "octave_script": "Player.lua"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `mesh_type` | string | `"Node3D"`, `"StaticMesh"`, or `"InstancedMesh"` |
| `octave_asset` | string | Project-relative path to the asset (without `.oct` extension) |
| `octave_asset_uuid` | string | 64-bit UUID string for rename-safe asset resolution |
| `octave_script` | string | Script filename relative to the `Scripts/` directory |
| `octave_main_camera` | bool | `true` if this camera should be the active camera on import |

## Editor Import

The Octave Editor reads these extras during **Import Scene** (when the "Apply glTF Extras" checkbox is enabled) and:

- Creates the appropriate node type (`Node3D`, `StaticMesh3D`, or `InstancedMesh3D`)
- Links the referenced project asset (by UUID, then path, then name)
- Attaches the specified Lua script
- Sets the main camera if flagged
- Skips creating redundant mesh/material/texture assets for nodes that reference existing project assets

If no extras are present, nodes default to `StaticMesh3D` (matching pre-extras behavior).

## Compatibility

- **Minimum Blender version:** 3.0
- **Backward compatibility:** Old exports using `instance_mesh` (bool) and `static_mesh` (bool) extras are still recognized by the Editor. `instance_mesh=true` maps to `InstancedMesh`, otherwise `StaticMesh`.
