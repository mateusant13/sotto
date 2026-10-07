#pragma once
#include <cstdint>
namespace sotto {
struct AudioTap {
    static constexpr int kSampleRate = 16000;
    static constexpr int kChannels = 1;
    static constexpr int kSampleWidthBytes = 2;
};
}  // namespace sotto