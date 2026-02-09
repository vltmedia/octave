#pragma once

#include "Timeline/TimelineClip.h"

#include <string>

class AnimationClip : public TimelineClip
{
public:

    DECLARE_CLIP(AnimationClip, TimelineClip);

    AnimationClip();
    virtual ~AnimationClip();

    virtual void SaveStream(Stream& stream) override;
    virtual void LoadStream(Stream& stream, uint32_t version) override;
    virtual void GatherProperties(std::vector<Property>& outProps) override;

#if EDITOR
    virtual bool DrawCustomProperty(Property& prop) override;
#endif

    const std::string& GetAnimationName() const { return mAnimationName; }
    void SetAnimationName(const std::string& name) { mAnimationName = name; }
    float GetBlendIn() const { return mBlendIn; }
    float GetBlendOut() const { return mBlendOut; }
    float GetWeight() const { return mWeight; }

protected:

    std::string mAnimationName;
    float mBlendIn = 0.0f;
    float mBlendOut = 0.0f;
    float mWeight = 1.0f;
};
