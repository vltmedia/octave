# Example: Rotator3D

A native addon that creates a Rotator3D component to continuously rotate Node3D objects with configurable speed and axis. The rotation logic runs entirely in C++ with no Lua overhead per frame.

---

## Overview

This example demonstrates:
- Using the plugin `Tick` callback for frame updates entirely in C++
- Storing Node3D references in native addon components
- Using OctaveEngineAPI to directly manipulate Node3D transforms
- Exposing configurable properties to Lua scripts
- Managing multiple Rotator3D instances from native code

---

## Files

### package.json

```json
{
    "name": "Rotator3D",
    "author": "Octave Examples",
    "description": "Continuously rotates objects with configurable speed and axis.",
    "version": "1.0.0",
    "tags": ["gameplay", "utility"],
    "native": {
        "target": "engine",
        "sourceDir": "Source",
        "binaryName": "Rotator3D",
        "apiVersion": 2
    }
}
```

### Source/Rotator3D.cpp

```cpp
/**
 * @file Rotator3D.cpp
 * @brief Native addon that provides rotation functionality for Node3D objects.
 *
 * This addon demonstrates using the plugin Tick callback to update all
 * Rotator3D instances each frame entirely in C++. Lua only needs to create
 * and configure Rotator3Ds - no Lua Tick function required.
 */

#include "Plugins/OctavePluginAPI.h"
#include "Plugins/OctaveEngineAPI.h"

// Include Lua headers for type definitions only (lua_State, luaL_Reg)
// DO NOT call lua_* functions directly - use sEngineAPI->Lua_* instead!
extern "C" {
#include "lua.h"
#include "lauxlib.h"
}

#include <vector>
#include <algorithm>

static OctaveEngineAPI* sEngineAPI = nullptr;

//=============================================================================
// Rotator3D Data Structure
//=============================================================================

struct Rotator3DData
{
    Node3D* targetNode = nullptr;  // The node to rotate
    float speedX = 0.0f;           // Degrees per second on X axis
    float speedY = 45.0f;          // Degrees per second on Y axis (default)
    float speedZ = 0.0f;           // Degrees per second on Z axis
    bool enabled = true;
};

// Global list of all active Rotator3Ds (managed by the plugin)
static std::vector<Rotator3DData*> sActiveRotator3Ds;

//=============================================================================
// Plugin Tick - Called every frame by the engine
//=============================================================================

static void PluginTick(float deltaTime)
{
    // Update all active Rotator3Ds
    for (Rotator3DData* data : sActiveRotator3Ds)
    {
        if (data == nullptr || !data->enabled || data->targetNode == nullptr)
        {
            continue;
        }

        // Calculate rotation delta
        float deltaX = data->speedX * deltaTime;
        float deltaY = data->speedY * deltaTime;
        float deltaZ = data->speedZ * deltaTime;

        // Apply rotation directly to the Node3D using the engine API
        sEngineAPI->Node3D_AddRotation(data->targetNode, deltaX, deltaY, deltaZ);
    }
}

//=============================================================================
// Lua Bindings - Use sEngineAPI->Lua_* wrappers!
//=============================================================================

// Rotator3D.Create(node) - Creates a new Rotator3D attached to a Node3D
static int Lua_Rotator3D_Create(lua_State* L)
{
    // First argument should be a Node3D userdata
    if (!sEngineAPI->Lua_isuserdata(L, 1))
    {
        sEngineAPI->LogError("Rotator3D.Create: expected Node3D as first argument");
        sEngineAPI->Lua_pushnil(L);
        return 1;
    }

    // Get the Node3D pointer from the Lua userdata
    Node3D* node = *(Node3D**)sEngineAPI->Lua_touserdata(L, 1);
    if (node == nullptr)
    {
        sEngineAPI->LogError("Rotator3D.Create: Node3D is null");
        sEngineAPI->Lua_pushnil(L);
        return 1;
    }

    // Create our Rotator3DData userdata
    Rotator3DData* data = (Rotator3DData*)sEngineAPI->Lua_newuserdata(L, sizeof(Rotator3DData));
    new (data) Rotator3DData();  // Placement new to initialize
    data->targetNode = node;

    // Add to active Rotator3Ds list
    sActiveRotator3Ds.push_back(data);

    sEngineAPI->LuaL_getmetatable(L, "Rotator3D");
    sEngineAPI->Lua_setmetatable(L, -2);

    return 1;
}

// Rotator3D:SetSpeed(x, y, z) - Set rotation speed for each axis
static int Lua_Rotator3D_SetSpeed(lua_State* L)
{
    Rotator3DData* data = (Rotator3DData*)sEngineAPI->LuaL_checkudata(L, 1, "Rotator3D");
    data->speedX = (float)sEngineAPI->LuaL_checknumber(L, 2);
    data->speedY = (float)sEngineAPI->LuaL_checknumber(L, 3);
    data->speedZ = (float)sEngineAPI->LuaL_checknumber(L, 4);
    return 0;
}

// Rotator3D:SetSpeedX(speed)
static int Lua_Rotator3D_SetSpeedX(lua_State* L)
{
    Rotator3DData* data = (Rotator3DData*)sEngineAPI->LuaL_checkudata(L, 1, "Rotator3D");
    data->speedX = (float)sEngineAPI->LuaL_checknumber(L, 2);
    return 0;
}

// Rotator3D:SetSpeedY(speed)
static int Lua_Rotator3D_SetSpeedY(lua_State* L)
{
    Rotator3DData* data = (Rotator3DData*)sEngineAPI->LuaL_checkudata(L, 1, "Rotator3D");
    data->speedY = (float)sEngineAPI->LuaL_checknumber(L, 2);
    return 0;
}

// Rotator3D:SetSpeedZ(speed)
static int Lua_Rotator3D_SetSpeedZ(lua_State* L)
{
    Rotator3DData* data = (Rotator3DData*)sEngineAPI->LuaL_checkudata(L, 1, "Rotator3D");
    data->speedZ = (float)sEngineAPI->LuaL_checknumber(L, 2);
    return 0;
}

// Rotator3D:GetSpeed() - Returns x, y, z rotation speeds
static int Lua_Rotator3D_GetSpeed(lua_State* L)
{
    Rotator3DData* data = (Rotator3DData*)sEngineAPI->LuaL_checkudata(L, 1, "Rotator3D");
    sEngineAPI->Lua_pushnumber(L, data->speedX);
    sEngineAPI->Lua_pushnumber(L, data->speedY);
    sEngineAPI->Lua_pushnumber(L, data->speedZ);
    return 3;
}

// Rotator3D:SetEnabled(enabled)
static int Lua_Rotator3D_SetEnabled(lua_State* L)
{
    Rotator3DData* data = (Rotator3DData*)sEngineAPI->LuaL_checkudata(L, 1, "Rotator3D");
    data->enabled = sEngineAPI->Lua_toboolean(L, 2);
    return 0;
}

// Rotator3D:IsEnabled()
static int Lua_Rotator3D_IsEnabled(lua_State* L)
{
    Rotator3DData* data = (Rotator3DData*)sEngineAPI->LuaL_checkudata(L, 1, "Rotator3D");
    sEngineAPI->Lua_pushboolean(L, data->enabled);
    return 1;
}

// Rotator3D:Destroy() - Remove from active list
static int Lua_Rotator3D_Destroy(lua_State* L)
{
    Rotator3DData* data = (Rotator3DData*)sEngineAPI->LuaL_checkudata(L, 1, "Rotator3D");

    // Remove from active list
    auto it = std::find(sActiveRotator3Ds.begin(), sActiveRotator3Ds.end(), data);
    if (it != sActiveRotator3Ds.end())
    {
        sActiveRotator3Ds.erase(it);
    }

    // Clear the target to prevent updates
    data->targetNode = nullptr;
    data->enabled = false;

    return 0;
}

// Garbage collection - ensure cleanup
static int Lua_Rotator3D_GC(lua_State* L)
{
    Rotator3DData* data = (Rotator3DData*)sEngineAPI->Lua_touserdata(L, 1);
    if (data != nullptr)
    {
        // Remove from active list if still there
        auto it = std::find(sActiveRotator3Ds.begin(), sActiveRotator3Ds.end(), data);
        if (it != sActiveRotator3Ds.end())
        {
            sActiveRotator3Ds.erase(it);
        }
    }
    return 0;
}

// Metatable methods
static const luaL_Reg sRotator3DMethods[] = {
    {"SetSpeed", Lua_Rotator3D_SetSpeed},
    {"SetSpeedX", Lua_Rotator3D_SetSpeedX},
    {"SetSpeedY", Lua_Rotator3D_SetSpeedY},
    {"SetSpeedZ", Lua_Rotator3D_SetSpeedZ},
    {"GetSpeed", Lua_Rotator3D_GetSpeed},
    {"SetEnabled", Lua_Rotator3D_SetEnabled},
    {"IsEnabled", Lua_Rotator3D_IsEnabled},
    {"Destroy", Lua_Rotator3D_Destroy},
    {"__gc", Lua_Rotator3D_GC},
    {nullptr, nullptr}
};

// Module functions
static const luaL_Reg sRotator3DFuncs[] = {
    {"Create", Lua_Rotator3D_Create},
    {nullptr, nullptr}
};

//=============================================================================
// Plugin Callbacks
//=============================================================================

static int OnLoad(OctaveEngineAPI* api)
{
    sEngineAPI = api;
    sActiveRotator3Ds.clear();
    api->LogDebug("Rotator3D addon loaded!");
    return 0;
}

static void OnUnload()
{
    if (sEngineAPI)
    {
        sEngineAPI->LogDebug("Rotator3D addon unloaded.");
    }
    sActiveRotator3Ds.clear();
    sEngineAPI = nullptr;
}

static void RegisterScriptFuncs(lua_State* L)
{
    // Create the Rotator3D metatable
    sEngineAPI->LuaL_newmetatable(L, "Rotator3D");

    // Set __index to itself for method lookup
    sEngineAPI->Lua_pushvalue(L, -1);
    sEngineAPI->Lua_setfield(L, -2, "__index");

    // Register methods (including __gc for cleanup)
    sEngineAPI->LuaL_setfuncs(L, sRotator3DMethods, 0);
    sEngineAPI->Lua_pop(L, 1);

    // Create the Rotator3D table and register module functions
    sEngineAPI->Lua_createtable(L, 0, 1);
    sEngineAPI->LuaL_setfuncs(L, sRotator3DFuncs, 0);
    sEngineAPI->Lua_setglobal(L, "Rotator3D");
}

//=============================================================================
// Plugin Entry Point
//=============================================================================

extern "C" OCTAVE_PLUGIN_API int OctavePlugin_GetDesc(OctavePluginDesc* desc)
{
    desc->apiVersion = OCTAVE_PLUGIN_API_VERSION;
    desc->pluginName = "Rotator3D";
    desc->pluginVersion = "1.0.0";
    desc->OnLoad = OnLoad;
    desc->OnUnload = OnUnload;
    desc->Tick = PluginTick;       // Gameplay tick (PIE or built game only)
    desc->TickEditor = nullptr;    // Editor tick (nullptr = don't tick in edit mode)
    desc->RegisterTypes = nullptr;
    desc->RegisterScriptFuncs = RegisterScriptFuncs;
    desc->RegisterEditorUI = nullptr;
    return 0;
}

// For compiled-in builds ONLY (when addon source is included in game executable)
// This is NOT used when building as a DLL for the editor
#if !defined(OCTAVE_PLUGIN_EXPORT)
#include "Plugins/RuntimePluginManager.h"
OCTAVE_REGISTER_PLUGIN(Rotator3D, OctavePlugin_GetDesc)
#endif
```

---

## Usage in Lua Scripts

### Basic Usage

```lua
-- RotatingCube.lua
-- Attach this script to any Node3D

RotatingCube = {}

local Rotator3D = nil

function RotatingCube:Create()
    -- Create a Rotator3D attached to this node
    -- Default: rotates at 45 degrees/sec on Y axis
    -- No Tick function needed - C++ handles everything!
    Rotator3D = Rotator3D.Create(self)
end

function RotatingCube:Destroy()
    -- Clean up when node is destroyed
    if Rotator3D then
        Rotator3D:Destroy()
        Rotator3D = nil
    end
end
```

### Advanced Usage

```lua
-- SpinningPlatform.lua
-- A platform that spins on multiple axes with exposed properties

SpinningPlatform = {}

local Rotator3D = nil

-- Exposed properties (editable in inspector)
SpeedX = 0.0
SpeedY = 90.0
SpeedZ = 0.0
StartEnabled = true

function SpinningPlatform:Create()
    Rotator3D = Rotator3D.Create(self)
    Rotator3D:SetSpeed(SpeedX, SpeedY, SpeedZ)
    Rotator3D:SetEnabled(StartEnabled)
end

function SpinningPlatform:Destroy()
    if Rotator3D then
        Rotator3D:Destroy()
        Rotator3D = nil
    end
end

-- Called from other scripts or events
function SpinningPlatform:SetRotationEnabled(enabled)
    if Rotator3D then
        Rotator3D:SetEnabled(enabled)
    end
end

function SpinningPlatform:SetRotationSpeed(x, y, z)
    if Rotator3D then
        Rotator3D:SetSpeed(x, y, z)
    end
end
```

---

## API Reference

### Rotator3D.Create(node)
Creates a new Rotator3D instance attached to a Node3D.

**Parameters:**
- `node` (Node3D): The node to rotate (typically `self`)

**Returns:** Rotator3D userdata, or nil on error

---

### Rotator3D:SetSpeed(x, y, z)
Sets the rotation speed for all axes.

**Parameters:**
- `x` (number): Degrees per second on X axis
- `y` (number): Degrees per second on Y axis
- `z` (number): Degrees per second on Z axis

---

### Rotator3D:SetSpeedX(speed) / SetSpeedY(speed) / SetSpeedZ(speed)
Sets the rotation speed for a single axis.

**Parameters:**
- `speed` (number): Degrees per second

---

### Rotator3D:GetSpeed()
Gets the current rotation speeds.

**Returns:** x, y, z (numbers)

---

### Rotator3D:SetEnabled(enabled)
Enables or disables the rotation.

**Parameters:**
- `enabled` (boolean): Whether rotation is active

---

### Rotator3D:IsEnabled()
Checks if rotation is enabled.

**Returns:** boolean

---

### Rotator3D:Destroy()
Removes the Rotator3D from the update list. Call this in your Destroy callback.

---

## Tick Callbacks

Native addons have two tick callbacks:

| Callback | When Called | Use Case |
|----------|-------------|----------|
| `Tick` | During gameplay only (PIE or built game) | Gameplay logic like rotation, movement, AI |
| `TickEditor` | Every frame in editor (regardless of play state) | Editor tools, visualizations, gizmos |

This Rotator3D uses `Tick` so objects only rotate during gameplay, not while editing.

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Zero Lua overhead** | No Tick function needed in Lua - C++ handles all updates |
| **Automatic cleanup** | `__gc` metamethod ensures cleanup when Lua garbage collects |
| **Direct Node3D access** | Uses `Node3D_AddRotation` for maximum performance |
| **Multiple instances** | Plugin manages all Rotator3Ds in a single tick loop |
| **Gameplay-only rotation** | Uses `Tick` callback so objects don't rotate while editing |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Engine Main Loop                      │
│                                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────┐ │
│  │   Update()  │───▶│PluginTick() │───▶│ Next Frame   │ │
│  └─────────────┘    └──────┬──────┘    └──────────────┘ │
│                            │                              │
│                            ▼                              │
│              ┌─────────────────────────┐                 │
│              │  For each Rotator3DData:  │                 │
│              │  - Calculate delta      │                 │
│              │  - Node3D_AddRotation() │                 │
│              └─────────────────────────┘                 │
└─────────────────────────────────────────────────────────┘
```

---

## Important Notes

**Lifecycle Management:** Always call `Rotator3D:Destroy()` in your Lua script's `Destroy()` callback, or the Rotator3D may continue trying to update a destroyed node.

**Garbage Collection:** The `__gc` metamethod provides automatic cleanup when Lua garbage collects the Rotator3D, but explicit `Destroy()` is recommended for deterministic cleanup.

**Node Validity:** The plugin stores a raw pointer to the Node3D. If the node is destroyed before the Rotator3D, ensure you call `Rotator3D:Destroy()` first.

---

## How It Works in Built Games

When you build your game, the native addon source files are compiled directly into the game executable (not as a DLL). The plugin uses the `OCTAVE_REGISTER_PLUGIN` macro for automatic registration:

```cpp
// At the end of the plugin source file (ONLY for compiled-in builds):
#if !defined(OCTAVE_PLUGIN_EXPORT)
#include "Plugins/RuntimePluginManager.h"
OCTAVE_REGISTER_PLUGIN(Rotator3D, OctavePlugin_GetDesc)
#endif
```

**Important:** The `#if !defined(OCTAVE_PLUGIN_EXPORT)` guard ensures this code is only compiled when building directly into the game. When building as a DLL for the editor (which defines `OCTAVE_PLUGIN_EXPORT`), the macro is skipped because the editor uses dynamic loading via `OctavePlugin_GetDesc` instead.

This macro creates a static initializer that registers the plugin with the `RuntimePluginManager` when the game starts. The registration flow is:

1. **Static initialization** - `OCTAVE_REGISTER_PLUGIN` queues the plugin descriptor
2. **Engine Initialize()** - `RuntimePluginManager::Create()` processes queued plugins
3. **RuntimePluginManager::Initialize()** - Calls `OnLoad` and `RegisterScriptFuncs` for each plugin
4. **Every frame** - `RuntimePluginManager::TickAllPlugins()` calls each plugin's `Tick` callback
5. **Shutdown** - `RuntimePluginManager::Destroy()` calls `OnUnload` for each plugin

Both the editor (via `NativeAddonManager`) and built games (via `RuntimePluginManager`) use the same plugin code, ensuring consistent behavior between development and release.
