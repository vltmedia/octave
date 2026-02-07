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

## Per-Object Properties

Select any object and open **Properties > Object > Octave Data** to configure:

### Mesh Type

Dropdown controlling how the object is imported into the Octave Editor:

| Value | Description |
|-------|-------------|
| **Node3D** | Plain transform node — no mesh is assigned |
| **StaticMesh** | Standard mesh node (default) — creates a `StaticMesh3D` |
| **InstancedMesh** | GPU-instanced mesh node — creates an `InstancedMesh3D` |

### Octave Asset

Search field to link an existing project asset by its project-relative path (e.g., `Assets/Meshes/SM_Cube.oct`). When set, the Editor resolves the asset by UUID first, then by name, falling back to the embedded glTF mesh.

### Script

Search field to attach a Lua script to the node. Scripts are shown as project-relative paths (e.g., `Scripts/Player.lua`). The `Scripts/` prefix is stripped on export since the engine prepends it automatically.

## Exporting

1. Go to **File > Export > Export for Octave (.gltf)**
2. Choose the output path and click **Export**

The addon syncs all Octave properties to Blender custom properties before invoking the glTF exporter with `export_extras=True`, embedding the metadata into each node's `extras` block.

## glTF Extras Format

Each node in the exported glTF/GLB file may contain an `extras` object:

```json
{
  "mesh_type": "StaticMesh",
  "octave_asset": "Assets/Meshes/SM_Cube.oct",
  "octave_asset_uuid": "12345678",
  "octave_script": "Player.lua"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `mesh_type` | string | `"Node3D"`, `"StaticMesh"`, or `"InstancedMesh"` |
| `octave_asset` | string | Project-relative path to the `.oct` asset |
| `octave_asset_uuid` | string | 64-bit UUID string for rename-safe asset resolution |
| `octave_script` | string | Script filename relative to the `Scripts/` directory |

## Editor Import

The Octave Editor reads these extras during **Import Scene** (when the "Apply glTF Extras" checkbox is enabled) and:

- Creates the appropriate node type (`Node3D`, `StaticMesh3D`, or `InstancedMesh3D`)
- Links the referenced project asset (by UUID or name)
- Attaches the specified Lua script

If no extras are present, nodes default to `StaticMesh3D` (matching pre-extras behavior).

## Compatibility

- **Minimum Blender version:** 3.0
- **Backward compatibility:** Old exports using `instance_mesh` (bool) and `static_mesh` (bool) extras are still recognized by the Editor. `instance_mesh=true` maps to `InstancedMesh`, otherwise `StaticMesh`.
