// audio_contract.h — THE one place the audio format is written down, lane B (feat/audio-mux).
//
// WHY THIS FILE EXISTS
// --------------------
// MEASURED on this box (lane B, 2026-10-07): `ffprobe -select_streams a` on 8 captured
// clips (3.0 s - 30.0 s, largest 165 MB) returned AUDIO=NONE on 8/8 -- every clip is
// h264 VIDEO-ONLY. The ASR half of the product consumes WAV (`asr/transcribe.py --wav`,
// required) and REFUSES anything that is not the format below. So searchable memory has
// no input at all. This header is the C++ side of that gap.
//
// THE FORMAT, taken from the ASR side and not guessed:
//   sample rate   16000 Hz          src/asr/constants.py:91  (SAMPLE_RATE = 16_000)
//   channels      1 (mono)         src/asr/audio.py:57-58   (else WavFormatError)
//   sample width  2 bytes, PCM16   src/asr/audio.py:54-55   (else WavFormatError)
//   container     RIFF/WAVE        src/asr/audio.py:1,49-50 (`wave.open`)
//   value range   signed int16, read as <i2 / 32768.0 into float32 in [-1,1]
//                                     src/asr/audio.py:75
//   naming        NONE required by the reader (any .wav is accepted); the worker's own
//                 convention is the sibling name, but that is a convention, not a contract.
//
// The values below are CHECKED against those literals at runtime by
// audio_wav.cpp: `kAsrSampleRate != 16000` refuses to build a clip rather than emitting a
// file the ASR would reject. A silent format mismatch is how a language gets destroyed
// (src/asr/audio.py:3-4).
#pragma once

#include <cstdint>

namespace aireplay {
namespace audio {

// The ASR input contract, with the ASR file:line that fixes each value.
constexpr uint32_t kAsrSampleRate = 16000;   // src/asr/constants.py:91
constexpr uint16_t kAsrChannels   = 1;      // src/asr/audio.py:57
constexpr uint16_t kAsrSampleWidth = 2;     // bytes per sample, PCM16 -- src/asr/audio.py:54

// Bytes per audio frame (one channel) in the ASR contract: 2.
constexpr uint32_t kAsrBytesPerFrame = kAsrChannels * kAsrSampleWidth;  // 2

}  // namespace audio
}  // namespace aireplay