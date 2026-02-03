#if EDITOR

#include "ExternalModule.h"
#include "../JsonSettings.h"

#include "document.h"
#include "imgui.h"

DEFINE_PREFERENCES_MODULE(ExternalModule, "External", "")

ExternalModule::ExternalModule()
{
}

ExternalModule::~ExternalModule()
{
}

void ExternalModule::Render()
{
    ImGui::TextDisabled("Select a subcategory from the left panel to configure external tools.");
}

void ExternalModule::LoadSettings(const rapidjson::Document& doc)
{
    // Parent module has no settings of its own
}

void ExternalModule::SaveSettings(rapidjson::Document& doc)
{
    // Parent module has no settings of its own
}

#endif
