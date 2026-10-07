// nvenc_encoder.h — the NVENC session, built the ONLY way this box accepts one.
//
// Spec 03 §2.4 + §5.  The three measured traps this file encodes as rules:
//   * `tuningInfo = 0` (UNDEFINED) is INVALID -> status 12.  Never a memset(0) value.
//   * a HAND-BUILT NV_ENC_CONFIG is refused with status 8 and a MISLEADING
//     "Unsupported color format."  Always start from nvEncGetEncodePresetConfigEx.
//   * NvEncGetEncodeCaps on an OPENED-but-UNINITIALISED session SEGFAULTS (0xC0000005)
//     with no error status.  Caps are only ever queried after a successful init.
//
// Law 6 lives here too: an encoder that opens but does not initialise, or that cannot
// ingest our texture, is NOT an encoder, and the caller must refuse to arm.
#pragma once
#include "common.h"

#include "nvEncodeAPI.h"

namespace aireplay {

// Fault injection exists ONLY for the law-6 negative control.  Each value reproduces a
// failure this box really produces (or a real absence), so the gate can be shown to say
// NO for a true reason rather than by a mock.
enum class Fault {
    None = 0,
    NoNvencRuntime,    // nvEncodeAPI64.dll "missing" (the non-NVIDIA user's case)
    TuningUndefined,   // the measured status-12 trap
    SkipResourceMap,   // session opens and initialises, but the input never maps
};

struct EncoderCaps {
    uint32_t engines = 0;
    uint32_t max_w = 0;
    uint32_t max_h = 0;
    bool queried = false;
};

struct CodecArm {
    const GUID* guid;
    const char* name;
};

// The ladder's SHAPE (research 01 §3): NVENC H.264 -> HEVC -> AV1, then the non-NVIDIA
// arms.  Only the three NVENC rungs exist today; AMF/QSV/x264 are named, not implemented.
const CodecArm* codec_ladder(size_t* count);

class NvencEncoder {
public:
    static void set_fault(Fault f);
    static Fault fault();
    static bool runtime_available(std::string* why_not);
    static const char* status_name(NVENCSTATUS s);

    // --- the arm/refuse decision, step by step -------------------------------------
    bool open(ID3D11Device* dev, const char* codec_name, const GUID& codec, std::string* err);
    bool initialize(uint32_t w, uint32_t h, uint32_t fps_num, uint32_t fps_den,
                    uint32_t bitrate_bps, uint32_t gop_len, std::string* err);
    bool query_caps(std::string* err);
    bool register_and_map(ID3D11Texture2D* nv12, std::string* err);

    // --- steady state ---------------------------------------------------------------
    bool encode(bool force_idr, uint64_t pts, std::string* err);
    bool sequence_params(std::vector<uint8_t>* out, std::string* err);

    void close();

    bool ready() const { return ready_; }
    const std::vector<uint8_t>& bitstream() const { return out_; }
    bool last_was_idr() const { return last_idr_; }
    int  last_picture_type() const { return last_pt_; }
    const EncoderCaps& caps() const { return caps_; }
    const char* codec_name() const { return codec_name_; }
    uint32_t width() const { return w_; }
    uint32_t height() const { return h_; }
    uint32_t bitrate() const { return bitrate_; }
    uint32_t gop_len() const { return gop_len_; }
    const GUID& codec_guid() const { return codec_; }
    const std::string& last_error_string() const { return last_err_str_; }
    uint64_t frames_encoded() const { return frames_; }

private:
    void note_last_error(const char* tag);
    void release_handles();

    NV_ENCODE_API_FUNCTION_LIST L_;
    bool     api_ok_ = false;
    void*    enc_ = nullptr;
    NV_ENC_REGISTERED_PTR reg_ = nullptr;
    NV_ENC_INPUT_PTR      mapped_ = nullptr;
    NV_ENC_OUTPUT_PTR     bs_ = nullptr;

    GUID        codec_ = {};
    const char* codec_name_ = "?";
    uint32_t    w_ = 0, h_ = 0;
    uint32_t    fps_num_ = 60, fps_den_ = 1;
    uint32_t    bitrate_ = 0;
    uint32_t    gop_len_ = 0;
    uint64_t    frames_ = 0;
    uint32_t    frame_idx_ = 0;

    bool        ready_ = false;
    bool        mapped_ok_ = false;
    bool        last_idr_ = false;
    int         last_pt_ = -1;
    EncoderCaps caps_;
    std::vector<uint8_t> out_;
    std::string last_err_str_;
};

} // namespace aireplay
