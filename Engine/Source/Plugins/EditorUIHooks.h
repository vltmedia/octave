#pragma once

/**
 * @file EditorUIHooks.h
 * @brief Editor UI extension system for native addons.
 *
 * Provides hooks for plugins and Lua scripts to extend the editor UI
 * including menus, custom windows, inspectors, and context menus.
 *
 * This entire file is wrapped in #if EDITOR to ensure editor code
 * does not leak into game builds.
 */

#if EDITOR

#include <stdint.h>

// ===== Callback Types =====

/**
 * @brief Callback for menu item clicks.
 * @param userData User data passed during registration
 */
typedef void (*MenuCallback)(void* userData);

/**
 * @brief Callback for drawing custom window content.
 * @param userData User data passed during registration
 */
typedef void (*WindowDrawCallback)(void* userData);

/**
 * @brief Callback for drawing custom inspector content.
 * @param node Pointer to the node being inspected
 * @param userData User data passed during registration
 */
typedef void (*InspectorDrawCallback)(void* node, void* userData);

/**
 * @brief Unique identifier for tracking hooks.
 *
 * Use GenerateHookId() to create from addon ID or Lua script UUID.
 * This allows proper cleanup when plugins are unloaded.
 */
typedef uint64_t HookId;

/**
 * @brief Editor UI extension hooks.
 *
 * Provides functions for plugins to extend the editor UI.
 * All registration functions take a HookId for tracking and cleanup.
 */
struct EditorUIHooks
{
    // ===== Menu Extensions =====

    /**
     * @brief Add a menu item to an existing menu.
     *
     * @param hookId Unique identifier for this hook (for cleanup)
     * @param menuPath Top-level menu: "File", "Edit", "View", "Developer", "Help"
     * @param itemPath Item path within menu, e.g., "My Tool" or "Submenu/My Tool"
     * @param callback Function called when item is clicked
     * @param userData User data passed to callback
     * @param shortcut Optional keyboard shortcut, e.g., "Ctrl+Shift+M" (can be nullptr)
     */
    void (*AddMenuItem)(
        HookId hookId,
        const char* menuPath,
        const char* itemPath,
        MenuCallback callback,
        void* userData,
        const char* shortcut
    );

    /**
     * @brief Add a separator in a menu.
     *
     * @param hookId Unique identifier for this hook
     * @param menuPath Menu to add separator to
     */
    void (*AddMenuSeparator)(HookId hookId, const char* menuPath);

    /**
     * @brief Remove a previously added menu item.
     *
     * @param hookId Hook identifier used during registration
     * @param menuPath Menu containing the item
     * @param itemPath Path of item to remove
     */
    void (*RemoveMenuItem)(HookId hookId, const char* menuPath, const char* itemPath);

    // ===== Custom Windows =====

    /**
     * @brief Register a custom dockable window.
     *
     * @param hookId Unique identifier for this hook
     * @param windowName Display name shown in title bar
     * @param windowId Unique ID for docking persistence
     * @param drawFunc Function called to draw window content
     * @param userData User data passed to drawFunc
     */
    void (*RegisterWindow)(
        HookId hookId,
        const char* windowName,
        const char* windowId,
        WindowDrawCallback drawFunc,
        void* userData
    );

    /**
     * @brief Unregister a custom window.
     *
     * @param hookId Hook identifier used during registration
     * @param windowId Window ID to unregister
     */
    void (*UnregisterWindow)(HookId hookId, const char* windowId);

    /**
     * @brief Open a custom window by ID.
     * @param windowId Window ID to open
     */
    void (*OpenWindow)(const char* windowId);

    /**
     * @brief Close a custom window by ID.
     * @param windowId Window ID to close
     */
    void (*CloseWindow)(const char* windowId);

    /**
     * @brief Check if a custom window is currently open.
     * @param windowId Window ID to check
     * @return true if window is open
     */
    bool (*IsWindowOpen)(const char* windowId);

    // ===== Inspector Extensions =====

    /**
     * @brief Register a custom inspector for a node type.
     *
     * @param hookId Unique identifier for this hook
     * @param nodeTypeName Type name of node, e.g., "MyCustomNode"
     * @param drawFunc Function called to draw inspector content
     * @param userData User data passed to drawFunc
     */
    void (*RegisterInspector)(
        HookId hookId,
        const char* nodeTypeName,
        InspectorDrawCallback drawFunc,
        void* userData
    );

    /**
     * @brief Unregister a custom inspector.
     *
     * @param hookId Hook identifier used during registration
     * @param nodeTypeName Node type name to unregister
     */
    void (*UnregisterInspector)(HookId hookId, const char* nodeTypeName);

    // ===== Context Menu Extensions =====

    /**
     * @brief Add item to node context menu (right-click in hierarchy).
     *
     * @param hookId Unique identifier for this hook
     * @param itemPath Item path in context menu
     * @param callback Function called when item is clicked
     * @param userData User data passed to callback
     */
    void (*AddNodeContextItem)(
        HookId hookId,
        const char* itemPath,
        MenuCallback callback,
        void* userData
    );

    /**
     * @brief Add item to asset context menu (right-click in asset browser).
     *
     * @param hookId Unique identifier for this hook
     * @param itemPath Item path in context menu
     * @param assetTypeFilter Asset type to show for, e.g., "Texture", or "*" for all
     * @param callback Function called when item is clicked
     * @param userData User data passed to callback
     */
    void (*AddAssetContextItem)(
        HookId hookId,
        const char* itemPath,
        const char* assetTypeFilter,
        MenuCallback callback,
        void* userData
    );

    // ===== Cleanup =====

    /**
     * @brief Remove ALL hooks registered by this hookId.
     *
     * Call this in OnUnload to ensure proper cleanup.
     *
     * @param hookId Hook identifier to remove all hooks for
     */
    void (*RemoveAllHooks)(HookId hookId);
};

/**
 * @brief Generate a HookId from a string identifier.
 *
 * Use the addon ID or Lua script UUID as the identifier
 * to ensure hooks can be properly tracked and cleaned up.
 *
 * @param identifier Unique string identifier
 * @return HookId for use with hook functions
 */
HookId GenerateHookId(const char* identifier);

#endif // EDITOR
