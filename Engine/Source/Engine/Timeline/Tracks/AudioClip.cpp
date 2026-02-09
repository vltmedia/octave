#include "Timeline/Tracks/AudioClip.h"
#include "Assets/SoundWave.h"
#include "Utilities.h"

FORCE_LINK_DEF(AudioClip);
DEFINE_CLIP(AudioClip);

AudioClip::AudioClip()
{
}

AudioClip::~AudioClip()
{
}

void AudioClip::SaveStream(Stream& stream)
{
    TimelineClip::SaveStream(stream);

    stream.WriteAsset(mSoundWave);
    stream.WriteFloat(mVolume);
    stream.WriteFloat(mPitch);
    stream.WriteFloat(mFadeInDuration);
    stream.WriteFloat(mFadeOutDuration);
}

void AudioClip::LoadStream(Stream& stream, uint32_t version)
{
    TimelineClip::LoadStream(stream, version);

    stream.ReadAsset(mSoundWave);
    mVolume = stream.ReadFloat();
    mPitch = stream.ReadFloat();
    mFadeInDuration = stream.ReadFloat();
    mFadeOutDuration = stream.ReadFloat();
}

void AudioClip::GatherProperties(std::vector<Property>& outProps)
{
    TimelineClip::GatherProperties(outProps);

    SCOPED_CATEGORY("Audio");

    outProps.push_back(Property(DatumType::Asset, "Sound Wave", this, &mSoundWave, 1, nullptr, int32_t(SoundWave::GetStaticType())));
    outProps.push_back(Property(DatumType::Float, "Volume", this, &mVolume));
    outProps.push_back(Property(DatumType::Float, "Pitch", this, &mPitch));
    outProps.push_back(Property(DatumType::Float, "Fade In", this, &mFadeInDuration));
    outProps.push_back(Property(DatumType::Float, "Fade Out", this, &mFadeOutDuration));
}
