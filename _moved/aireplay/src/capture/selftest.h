// selftest.h — LAW 6, factored into ONE place so the run path and the standalone
// `--selftest` can never drift apart.
//
// AGENTS.md law 6: "THE HOTKEY IS ARMED ONLY IF AN ENCODER REALLY INITIALISED".  The
// worst failure this product can have is a recorder whose UI says it is armed while it
// records nothing — the owner only discovers it when the moment is gone.
//
// So "armed" is not a flag; it is the OUTPUT of this function.  Three steps must ALL
// succeed, and a session that opens but does not initialise is NOT an encoder (measured:
// NvEncGetEncodeCaps on exactly that state SEGFAULTS with no error status):
//   1. NvEncOpenEncodeSessionEx
//   2. NvEncInitializeEncoder  (P3 + LOW_LATENCY, config taken from the driver's preset)
//   3. NvEncRegisterResource + NvEncMapInputResource on a REAL NV12 texture
#pragma once
#include "common.h"

#include "d3d11_ctx.h"
#include "nvenc_encoder.h"

namespace aireplay {

struct GateResult {
    bool        armed = false;
    std::string codec;          // the arm that won, or "" 
    EncoderCaps caps;
    std::string reason;         // why NOT armed, in the driver's own words
    uint32_t    arms_tried = 0;
};

// On success, `out_encoder` holds the OPEN + INITIALISED + MAPPED session.
// On failure, `out_encoder` is closed and nothing is armed.
GateResult law_six_gate(ID3D11Device* dev, ID3D11Texture2D* nv12,
                        uint32_t w, uint32_t h,
                        uint32_t fps, uint32_t bitrate, uint32_t gop,
                        const std::string& codec_pref,
                        NvencEncoder* out_encoder);

} // namespace aireplay
