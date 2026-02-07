#pragma once

#if EDITOR

#include "EngineTypes.h"

enum class OctaveMeshType { Node3D, StaticMesh, InstancedMesh };

struct OctaveNodeExtras
{
    OctaveMeshType mMeshType = OctaveMeshType::StaticMesh;
    std::string mAssetName;
    uint64_t mAssetUuid = 0;
    std::string mScriptPath;
    bool mMainCamera = false;
};

struct SceneImportOptions
{
    std::string mFilePath;
    std::string mSceneName;
    std::string mPrefix;
    bool mImportMeshes = true;
    bool mImportMaterials = true;
    bool mImportTextures = true;
    bool mImportLights = true;
    bool mImportCameras = true;
    bool mEnableCollision = true;
    bool mApplyGltfExtras = true;
    ShadingModel mDefaultShadingModel = ShadingModel::Lit;
    VertexColorMode mDefaultVertexColorMode = VertexColorMode::None;
};

struct CameraImportOptions
{
    std::string mFilePath;
    std::string mCameraName;
    bool mIsMainCamera = false;
    bool mOverrideCameraName = false;
};

#endif
