#if EDITOR

#include "EditorUIHookManager.h"
#include "Log.h"

#include "imgui.h"

#include <algorithm>

EditorUIHookManager* EditorUIHookManager::sInstance = nullptr;

// ===== Helper Functions Used by InitializeHooks =====

static void Hook_OpenWindow(const char* windowId)
{
    EditorUIHookManager* mgr = EditorUIHookManager::Get();
    if (mgr) mgr->OpenWindow(windowId ? windowId : "");
}

static void Hook_CloseWindow(const char* windowId)
{
    EditorUIHookManager* mgr = EditorUIHookManager::Get();
    if (mgr) mgr->CloseWindow(windowId ? windowId : "");
}

static bool Hook_IsWindowOpen(const char* windowId)
{
    EditorUIHookManager* mgr = EditorUIHookManager::Get();
    return mgr ? mgr->IsWindowOpen(windowId ? windowId : "") : false;
}

static void Hook_RemoveAllHooks(HookId hookId)
{
    EditorUIHookManager* mgr = EditorUIHookManager::Get();
    if (mgr) mgr->RemoveAllHooks(hookId);
}

// ===== EditorUIHookManager Implementation =====

void EditorUIHookManager::Create()
{
    if (sInstance == nullptr)
    {
        sInstance = new EditorUIHookManager();
    }
}

void EditorUIHookManager::Destroy()
{
    if (sInstance != nullptr)
    {
        delete sInstance;
        sInstance = nullptr;
    }
}

EditorUIHookManager* EditorUIHookManager::Get()
{
    return sInstance;
}

EditorUIHookManager::EditorUIHookManager()
{
    InitializeHooks();
}

EditorUIHookManager::~EditorUIHookManager()
{
}

void EditorUIHookManager::InitializeHooks()
{
    // Set up the hooks struct with function pointers
    // These need to call back into this manager

    // For AddMenuItem, we need a static function that can access the manager
    mHooks.AddMenuItem = [](HookId hookId, const char* menuPath, const char* itemPath,
                            MenuCallback callback, void* userData, const char* shortcut) {
        EditorUIHookManager* mgr = EditorUIHookManager::Get();
        if (mgr == nullptr) return;

        RegisteredMenuItem item;
        item.mHookId = hookId;
        item.mMenuPath = menuPath ? menuPath : "";
        item.mItemPath = itemPath ? itemPath : "";
        item.mCallback = callback;
        item.mUserData = userData;
        item.mShortcut = shortcut ? shortcut : "";
        item.mIsSeparator = false;

        mgr->mMenuItems[item.mMenuPath].push_back(item);
    };

    mHooks.AddMenuSeparator = [](HookId hookId, const char* menuPath) {
        EditorUIHookManager* mgr = EditorUIHookManager::Get();
        if (mgr == nullptr) return;

        RegisteredMenuItem item;
        item.mHookId = hookId;
        item.mMenuPath = menuPath ? menuPath : "";
        item.mIsSeparator = true;

        mgr->mMenuItems[item.mMenuPath].push_back(item);
    };

    mHooks.RemoveMenuItem = [](HookId hookId, const char* menuPath, const char* itemPath) {
        EditorUIHookManager* mgr = EditorUIHookManager::Get();
        if (mgr == nullptr) return;

        std::string menu = menuPath ? menuPath : "";
        std::string path = itemPath ? itemPath : "";

        auto it = mgr->mMenuItems.find(menu);
        if (it != mgr->mMenuItems.end())
        {
            auto& items = it->second;
            items.erase(std::remove_if(items.begin(), items.end(),
                [hookId, &path](const RegisteredMenuItem& item) {
                    return item.mHookId == hookId && item.mItemPath == path;
                }), items.end());
        }
    };

    mHooks.RegisterWindow = [](HookId hookId, const char* windowName, const char* windowId,
                               WindowDrawCallback drawFunc, void* userData) {
        EditorUIHookManager* mgr = EditorUIHookManager::Get();
        if (mgr == nullptr) return;

        RegisteredWindow win;
        win.mHookId = hookId;
        win.mWindowName = windowName ? windowName : "";
        win.mWindowId = windowId ? windowId : "";
        win.mDrawFunc = drawFunc;
        win.mUserData = userData;
        win.mIsOpen = false;

        mgr->mWindows.push_back(win);
    };

    mHooks.UnregisterWindow = [](HookId hookId, const char* windowId) {
        EditorUIHookManager* mgr = EditorUIHookManager::Get();
        if (mgr == nullptr) return;

        std::string id = windowId ? windowId : "";
        mgr->mWindows.erase(std::remove_if(mgr->mWindows.begin(), mgr->mWindows.end(),
            [hookId, &id](const RegisteredWindow& win) {
                return win.mHookId == hookId && win.mWindowId == id;
            }), mgr->mWindows.end());
    };

    mHooks.OpenWindow = Hook_OpenWindow;
    mHooks.CloseWindow = Hook_CloseWindow;
    mHooks.IsWindowOpen = Hook_IsWindowOpen;

    mHooks.RegisterInspector = [](HookId hookId, const char* nodeTypeName,
                                  InspectorDrawCallback drawFunc, void* userData) {
        EditorUIHookManager* mgr = EditorUIHookManager::Get();
        if (mgr == nullptr) return;

        RegisteredInspector insp;
        insp.mHookId = hookId;
        insp.mNodeTypeName = nodeTypeName ? nodeTypeName : "";
        insp.mDrawFunc = drawFunc;
        insp.mUserData = userData;

        mgr->mInspectors.push_back(insp);
    };

    mHooks.UnregisterInspector = [](HookId hookId, const char* nodeTypeName) {
        EditorUIHookManager* mgr = EditorUIHookManager::Get();
        if (mgr == nullptr) return;

        std::string typeName = nodeTypeName ? nodeTypeName : "";
        mgr->mInspectors.erase(std::remove_if(mgr->mInspectors.begin(), mgr->mInspectors.end(),
            [hookId, &typeName](const RegisteredInspector& insp) {
                return insp.mHookId == hookId && insp.mNodeTypeName == typeName;
            }), mgr->mInspectors.end());
    };

    mHooks.AddNodeContextItem = [](HookId hookId, const char* itemPath,
                                   MenuCallback callback, void* userData) {
        EditorUIHookManager* mgr = EditorUIHookManager::Get();
        if (mgr == nullptr) return;

        RegisteredContextItem ctx;
        ctx.mHookId = hookId;
        ctx.mItemPath = itemPath ? itemPath : "";
        ctx.mCallback = callback;
        ctx.mUserData = userData;
        ctx.mIsNodeContext = true;

        mgr->mContextItems.push_back(ctx);
    };

    mHooks.AddAssetContextItem = [](HookId hookId, const char* itemPath,
                                    const char* assetTypeFilter,
                                    MenuCallback callback, void* userData) {
        EditorUIHookManager* mgr = EditorUIHookManager::Get();
        if (mgr == nullptr) return;

        RegisteredContextItem ctx;
        ctx.mHookId = hookId;
        ctx.mItemPath = itemPath ? itemPath : "";
        ctx.mAssetTypeFilter = assetTypeFilter ? assetTypeFilter : "*";
        ctx.mCallback = callback;
        ctx.mUserData = userData;
        ctx.mIsNodeContext = false;

        mgr->mContextItems.push_back(ctx);
    };

    mHooks.RemoveAllHooks = Hook_RemoveAllHooks;
}

const std::vector<RegisteredMenuItem>& EditorUIHookManager::GetMenuItems(const std::string& menuPath) const
{
    auto it = mMenuItems.find(menuPath);
    if (it != mMenuItems.end())
    {
        return it->second;
    }
    return mEmptyMenuItems;
}

void EditorUIHookManager::DrawMenuItems(const std::string& menuPath)
{
    auto it = mMenuItems.find(menuPath);
    if (it == mMenuItems.end() || it->second.empty())
    {
        return;
    }

    for (const RegisteredMenuItem& item : it->second)
    {
        if (item.mIsSeparator)
        {
            ImGui::Separator();
        }
        else
        {
            const char* shortcut = item.mShortcut.empty() ? nullptr : item.mShortcut.c_str();
            if (ImGui::MenuItem(item.mItemPath.c_str(), shortcut))
            {
                if (item.mCallback)
                {
                    item.mCallback(item.mUserData);
                }
            }
        }
    }
}

void EditorUIHookManager::DrawWindows()
{
    for (RegisteredWindow& win : mWindows)
    {
        if (win.mIsOpen)
        {
            if (ImGui::Begin(win.mWindowName.c_str(), &win.mIsOpen))
            {
                if (win.mDrawFunc)
                {
                    win.mDrawFunc(win.mUserData);
                }
            }
            ImGui::End();
        }
    }
}

void EditorUIHookManager::OpenWindow(const std::string& windowId)
{
    for (RegisteredWindow& win : mWindows)
    {
        if (win.mWindowId == windowId)
        {
            win.mIsOpen = true;
            return;
        }
    }
}

void EditorUIHookManager::CloseWindow(const std::string& windowId)
{
    for (RegisteredWindow& win : mWindows)
    {
        if (win.mWindowId == windowId)
        {
            win.mIsOpen = false;
            return;
        }
    }
}

bool EditorUIHookManager::IsWindowOpen(const std::string& windowId) const
{
    for (const RegisteredWindow& win : mWindows)
    {
        if (win.mWindowId == windowId)
        {
            return win.mIsOpen;
        }
    }
    return false;
}

const RegisteredInspector* EditorUIHookManager::GetInspector(const std::string& nodeTypeName) const
{
    for (const RegisteredInspector& insp : mInspectors)
    {
        if (insp.mNodeTypeName == nodeTypeName)
        {
            return &insp;
        }
    }
    return nullptr;
}

bool EditorUIHookManager::DrawInspector(const std::string& nodeTypeName, void* node)
{
    const RegisteredInspector* insp = GetInspector(nodeTypeName);
    if (insp && insp->mDrawFunc)
    {
        insp->mDrawFunc(node, insp->mUserData);
        return true;
    }
    return false;
}

void EditorUIHookManager::DrawNodeContextItems()
{
    for (const RegisteredContextItem& ctx : mContextItems)
    {
        if (ctx.mIsNodeContext)
        {
            if (ImGui::MenuItem(ctx.mItemPath.c_str()))
            {
                if (ctx.mCallback)
                {
                    ctx.mCallback(ctx.mUserData);
                }
            }
        }
    }
}

void EditorUIHookManager::DrawAssetContextItems(const std::string& assetType)
{
    for (const RegisteredContextItem& ctx : mContextItems)
    {
        if (!ctx.mIsNodeContext)
        {
            // Check if this item applies to this asset type
            if (ctx.mAssetTypeFilter == "*" || ctx.mAssetTypeFilter == assetType)
            {
                if (ImGui::MenuItem(ctx.mItemPath.c_str()))
                {
                    if (ctx.mCallback)
                    {
                        ctx.mCallback(ctx.mUserData);
                    }
                }
            }
        }
    }
}

void EditorUIHookManager::RemoveAllHooks(HookId hookId)
{
    // Remove menu items
    for (auto& pair : mMenuItems)
    {
        pair.second.erase(std::remove_if(pair.second.begin(), pair.second.end(),
            [hookId](const RegisteredMenuItem& item) {
                return item.mHookId == hookId;
            }), pair.second.end());
    }

    // Remove windows
    mWindows.erase(std::remove_if(mWindows.begin(), mWindows.end(),
        [hookId](const RegisteredWindow& win) {
            return win.mHookId == hookId;
        }), mWindows.end());

    // Remove inspectors
    mInspectors.erase(std::remove_if(mInspectors.begin(), mInspectors.end(),
        [hookId](const RegisteredInspector& insp) {
            return insp.mHookId == hookId;
        }), mInspectors.end());

    // Remove context items
    mContextItems.erase(std::remove_if(mContextItems.begin(), mContextItems.end(),
        [hookId](const RegisteredContextItem& ctx) {
            return ctx.mHookId == hookId;
        }), mContextItems.end());
}

HookId GenerateHookId(const char* identifier)
{
    if (identifier == nullptr)
    {
        return 0;
    }

    // Simple hash function
    uint64_t hash = 0;
    while (*identifier)
    {
        hash = hash * 31 + static_cast<uint64_t>(*identifier);
        ++identifier;
    }
    return hash;
}

#endif // EDITOR
