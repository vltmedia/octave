#pragma once

#include "Factory.h"
#include "Object.h"
#include "Property.h"
#include "Stream.h"
#include "Timeline/TimelineTypes.h"

#include <string>
#include <vector>

class Node;

#define DECLARE_CLIP(Class, Parent) \
    DECLARE_FACTORY(Class, TimelineClip); \
    DECLARE_OBJECT(Class, Parent); \
    typedef Parent Super;

#define DEFINE_CLIP(Class) \
    DEFINE_FACTORY(Class, TimelineClip); \
    DEFINE_OBJECT(Class);

class TimelineClip : public Object
{
public:

    DECLARE_FACTORY_MANAGER(TimelineClip);
    DECLARE_FACTORY(TimelineClip, TimelineClip);
    DECLARE_OBJECT(TimelineClip, Object);

    TimelineClip();
    virtual ~TimelineClip();

    virtual void SaveStream(Stream& stream);
    virtual void LoadStream(Stream& stream, uint32_t version);

    virtual void GatherProperties(std::vector<Property>& outProps) override;

    float GetStartTime() const { return mStartTime; }
    void SetStartTime(float time) { mStartTime = time; }

    float GetDuration() const { return mDuration; }
    void SetDuration(float duration) { mDuration = duration; }

    float GetEndTime() const { return mStartTime + mDuration; }

    float GetClipInTime() const { return mClipInTime; }
    void SetClipInTime(float time) { mClipInTime = time; }

    float GetClipOutTime() const { return mClipOutTime; }
    void SetClipOutTime(float time) { mClipOutTime = time; }

    float GetSpeed() const { return mSpeed; }
    void SetSpeed(float speed) { mSpeed = speed; }

    bool ContainsTime(float globalTime) const;
    float GetLocalTime(float globalTime) const;
    bool OverlapsWith(const TimelineClip* other) const;

    virtual bool SupportsKeyframes() const { return false; }
    virtual uint32_t GetNumKeyframes() const { return 0; }
    virtual void AddKeyframeAtTime(float localTime, Node* targetNode) {}
    virtual void RemoveKeyframe(uint32_t index) {}

protected:

    float mStartTime = 0.0f;
    float mDuration = 1.0f;
    float mClipInTime = 0.0f;
    float mClipOutTime = 0.0f;
    float mSpeed = 1.0f;
};
