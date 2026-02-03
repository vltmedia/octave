#pragma once

/**
 * @file EditorUIHookManager.h
 * @brief Manages registered UI hooks from plugins and Lua scripts.
 *
 * This entire file is wrapped in #if EDITOR to ensure editor code
 * does not leak into game builds.
 */

#if EDITOR

#include "Plugins/EditorUIHooks.h"

#include <string>
#include <vector>
#include <unordered_map>
#include <functional>

/**
 * @brief Registered menu item.
 */
struct RegisteredMenuItem
{
    HookId mHookId;
    std::string mMenuPath;
    std::string mItemPath;
    MenuCallback mCallback;
    void* mUserData;
    std::string mShortcut;
    bool mIsSeparator = false;
};

/**
 * @brief Registered custom window.
 */
struct RegisteredWindow
{
    HookId mHookId;
    std::string mWindowName;
    std::string mWindowId;
    WindowDrawCallback mDrawFunc;
    void* mUserData;
    bool mIsOpen = false;
};

/**
 * @brief Registered custom inspector.
 */
struct RegisteredInspector
{
    HookId mHookId;
    std::string mNodeTypeName;
    InspectorDrawCallback mDrawFunc;
    void* mUserData;
};

/**
 * @brief Registered context menu item.
 */
struct RegisteredContextItem
{
    HookId mHookId;
    std::string mItemPath;
    std::string mAssetTypeFilter;  // Empty for node context, or asset type for asset context
    MenuCallback mCallback;
    void* mUserData;
    bool mIsNodeContext;  // true for node context, false for asset context
};

/**
 * @brief Singleton manager for editor UI hooks.
 *
 * Stores all registered hooks and provides rendering helpers.
 */
class EditorUIHookManager
{
public:
    static void Create();
    static void Destroy();
    static EditorUIHookManager* Get();

    /**
     * @brief Get the EditorUIHooks struct for plugins.
     */
    EditorUIHooks* GetHooks() { return &mHooks; }

    // ===== Menu Items =====

    /**
     * @brief Get menu items for a specific menu path.
     */
    const std::vector<RegisteredMenuItem>& GetMenuItems(const std::string& menuPath) const;

    /**
     * @brief Draw plugin menu items for a menu.
     * Call this inside ImGui::BeginMenu/EndMenu.
     */
    void DrawMenuItems(const std::string& menuPath);

    // ===== Custom Windows =====

    /**
     * @brief Get all registered windows.
     */
    const std::vector<RegisteredWindow>& GetWindows() const { return mWindows; }

    /**
     * @brief Draw all open custom windows.
     */
    void DrawWindows();

    /**
     * @brief Open a window by ID.
     */
    void OpenWindow(const std::string& windowId);

    /**
     * @brief Close a window by ID.
     */
    void CloseWindow(const std::string& windowId);

    /**
     * @brief Check if a window is open.
     */
    bool IsWindowOpen(const std::string& windowId) const;

    // ===== Inspectors =====

    /**
     * @brief Get inspector for a node type.
     * @return Pointer to inspector, or nullptr if none registered.
     */
    const RegisteredInspector* GetInspector(const std::string& nodeTypeName) const;

    /**
     * @brief Draw custom inspector for a node.
     * @return true if a custom inspector was drawn.
     */
    bool DrawInspector(const std::string& nodeTypeName, void* node);

    // ===== Context Menus =====

    /**
     * @brief Draw node context menu items.
     */
    void DrawNodeContextItems();

    /**
     * @brief Draw asset context menu items.
     * @param assetType The type of asset being right-clicked
     */
    void DrawAssetContextItems(const std::string& assetType);

    // ===== Cleanup =====

    /**
     * @brief Remove all hooks registered by a specific hook ID.
     */
    void RemoveAllHooks(HookId hookId);

private:
    static EditorUIHookManager* sInstance;
    EditorUIHookManager();
    ~EditorUIHookManager();

    void InitializeHooks();

    // Hook storage
    std::unordered_map<std::string, std::vector<RegisteredMenuItem>> mMenuItems;
    std::vector<RegisteredWindow> mWindows;
    std::vector<RegisteredInspector> mInspectors;
    std::vector<RegisteredContextItem> mContextItems;

    // Empty vector for returning when menu not found
    std::vector<RegisteredMenuItem> mEmptyMenuItems;

    // Hooks struct passed to plugins
    EditorUIHooks mHooks;
};

/**
 * @brief Generate a HookId from a string identifier.
 */
HookId GenerateHookId(const char* identifier);

#endif // EDITOR
