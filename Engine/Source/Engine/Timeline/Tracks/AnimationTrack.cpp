#include "Timeline/Tracks/AnimationTrack.h"
#include "Timeline/Tracks/AnimationClip.h"
#include "Timeline/TimelineInstance.h"
#include "Nodes/3D/SkeletalMesh3d.h"
#include "Utilities.h"

FORCE_LINK_DEF(AnimationTrack);
DEFINE_TRACK(AnimationTrack);

AnimationTrack::AnimationTrack()
{
}

AnimationTrack::~AnimationTrack()
{
}

void AnimationTrack::Evaluate(float time, Node* target, TimelineInstance* inst)
{
    if (target == nullptr)
        return;

    SkeletalMesh3D* skelMesh = target->As<SkeletalMesh3D>();
    if (skelMesh == nullptr)
        return;

    for (uint32_t i = 0; i < mClips.size(); ++i)
    {
        if (mClips[i]->GetType() != AnimationClip::GetStaticType())
            continue;

        AnimationClip* clip = static_cast<AnimationClip*>(mClips[i]);

        if (clip->ContainsTime(time))
        {
            const std::string& animName = clip->GetAnimationName();
            if (animName.empty())
                continue;

            float speed = clip->GetSpeed();
            float weight = clip->GetWeight();

            skelMesh->PlayAnimation(animName.c_str(), false, speed, weight);
        }
    }
}

void AnimationTrack::Reset(Node* target, TimelineInstance* inst)
{
    if (target == nullptr)
        return;

    SkeletalMesh3D* skelMesh = target->As<SkeletalMesh3D>();
    if (skelMesh != nullptr)
    {
        skelMesh->StopAllAnimations();
    }
}

glm::vec4 AnimationTrack::GetTrackColor() const
{
    return glm::vec4(0.3f, 0.4f, 0.9f, 1.0f);
}

TypeId AnimationTrack::GetDefaultClipType() const
{
    return AnimationClip::GetStaticType();
}
