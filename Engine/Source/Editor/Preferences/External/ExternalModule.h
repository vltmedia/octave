#pragma once

#if EDITOR

#include "../PreferencesModule.h"

/**
 * @brief Parent preferences module for external tools configuration.
 *
 * This module serves as a container for external tool settings such as
 * emulator paths and launcher configurations.
 */
class ExternalModule : public PreferencesModule
{
public:
    DECLARE_PREFERENCES_MODULE(ExternalModule)

    ExternalModule();
    virtual ~ExternalModule();

    virtual const char* GetName() const override { return GetStaticName(); }
    virtual const char* GetParentPath() const override { return GetStaticParentPath(); }
    virtual void Render() override;
    virtual void LoadSettings(const rapidjson::Document& doc) override;
    virtual void SaveSettings(rapidjson::Document& doc) override;
};

#endif
