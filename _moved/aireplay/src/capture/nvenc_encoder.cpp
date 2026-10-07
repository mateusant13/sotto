#include "nvenc_encoder.h"

namespace aireplay {

// ------------------------------------------------------------------ module state
static Fault                g_fault = Fault::None;
static HMODULE              g_dll = nullptr;
static bool                 g_dll_tried = false;
static NV_ENCODE_API_FUNCTION_LIST g_api;
static bool                 g_api_ok = false;
static std::string          g_api_why;

void NvencEncoder::set_fault(Fault f) { g_fault = f; }
Fault NvencEncoder::fault() { return g_fault; }

const char* NvencEncoder::status_name(NVENCSTATUS s)
{
    switch (s) {
    case NV_ENC_SUCCESS:                      return "NV_ENC_SUCCESS";
    case NV_ENC_ERR_NO_ENCODE_DEVICE:         return "NV_ENC_ERR_NO_ENCODE_DEVICE";
    case NV_ENC_ERR_UNSUPPORTED_DEVICE:       return "NV_ENC_ERR_UNSUPPORTED_DEVICE";
    case NV_ENC_ERR_INVALID_ENCODERDEVICE:    return "NV_ENC_ERR_INVALID_ENCODERDEVICE";
    case NV_ENC_ERR_INVALID_DEVICE:           return "NV_ENC_ERR_INVALID_DEVICE";
    case NV_ENC_ERR_DEVICE_NOT_EXIST:         return "NV_ENC_ERR_DEVICE_NOT_EXIST";
    case NV_ENC_ERR_INVALID_PTR:              return "NV_ENC_ERR_INVALID_PTR";
    case NV_ENC_ERR_INVALID_EVENT:            return "NV_ENC_ERR_INVALID_EVENT";
    case NV_ENC_ERR_INVALID_PARAM:            return "NV_ENC_ERR_INVALID_PARAM";
    case NV_ENC_ERR_INVALID_CALL:             return "NV_ENC_ERR_INVALID_CALL";
    case NV_ENC_ERR_OUT_OF_MEMORY:            return "NV_ENC_ERR_OUT_OF_MEMORY";
    case NV_ENC_ERR_ENCODER_NOT_INITIALIZED:  return "NV_ENC_ERR_ENCODER_NOT_INITIALIZED";
    case NV_ENC_ERR_UNSUPPORTED_PARAM:        return "NV_ENC_ERR_UNSUPPORTED_PARAM";
    case NV_ENC_ERR_LOCK_BUSY:                return "NV_ENC_ERR_LOCK_BUSY";
    case NV_ENC_ERR_NOT_ENOUGH_BUFFER:        return "NV_ENC_ERR_NOT_ENOUGH_BUFFER";
    case NV_ENC_ERR_INVALID_VERSION:          return "NV_ENC_ERR_INVALID_VERSION";
    case NV_ENC_ERR_MAP_FAILED:               return "NV_ENC_ERR_MAP_FAILED";
    case NV_ENC_ERR_NEED_MORE_INPUT:          return "NV_ENC_ERR_NEED_MORE_INPUT";
    case NV_ENC_ERR_ENCODER_BUSY:             return "NV_ENC_ERR_ENCODER_BUSY";
    case NV_ENC_ERR_EVENT_NOT_REGISTERD:      return "NV_ENC_ERR_EVENT_NOT_REGISTERD";
    case NV_ENC_ERR_GENERIC:                  return "NV_ENC_ERR_GENERIC";
    case NV_ENC_ERR_INCOMPATIBLE_CLIENT_KEY:  return "NV_ENC_ERR_INCOMPATIBLE_CLIENT_KEY";
    case NV_ENC_ERR_UNIMPLEMENTED:            return "NV_ENC_ERR_UNIMPLEMENTED";
    case NV_ENC_ERR_RESOURCE_REGISTER_FAILED: return "NV_ENC_ERR_RESOURCE_REGISTER_FAILED";
    case NV_ENC_ERR_RESOURCE_NOT_REGISTERED:  return "NV_ENC_ERR_RESOURCE_NOT_REGISTERED";
    case NV_ENC_ERR_RESOURCE_NOT_MAPPED:      return "NV_ENC_ERR_RESOURCE_NOT_MAPPED";
    default:                                  return "(unknown NVENCSTATUS)";
    }
}

bool NvencEncoder::runtime_available(std::string* why_not)
{
    if (g_fault == Fault::NoNvencRuntime) {
        *why_not = "INJECTED FAULT: nvEncodeAPI64.dll treated as absent";
        return false;
    }
    if (g_dll_tried) {
        if (!g_api_ok) *why_not = g_api_why;
        return g_api_ok;
    }
    g_dll_tried = true;

    g_dll = LoadLibraryW(L"nvEncodeAPI64.dll");
    if (!g_dll) {
        char b[128];
        snprintf(b, sizeof(b), "LoadLibrary(nvEncodeAPI64.dll) failed, GetLastError=%lu", GetLastError());
        g_api_why = b;
        return false;
    }
    typedef NVENCSTATUS (NVENCAPI *PFN_CreateInstance)(NV_ENCODE_API_FUNCTION_LIST*);
    PFN_CreateInstance ci = (PFN_CreateInstance)(void*)GetProcAddress(g_dll, "NvEncodeAPICreateInstance");
    if (!ci) { g_api_why = "nvEncodeAPI64.dll has no NvEncodeAPICreateInstance export"; return false; }

    memset(&g_api, 0, sizeof(g_api));
    g_api.version = NV_ENCODE_API_FUNCTION_LIST_VER;
    NVENCSTATUS s = ci(&g_api);
    if (s != NV_ENC_SUCCESS) {
        char b[160];
        snprintf(b, sizeof(b), "NvEncodeAPICreateInstance -> %d (%s)",
                 (int)s, NvencEncoder::status_name(s));
        g_api_why = b;
        return false;
    }
    if (!g_api.nvEncOpenEncodeSessionEx || !g_api.nvEncInitializeEncoder ||
        !g_api.nvEncDestroyEncoder || !g_api.nvEncEncodePicture) {
        g_api_why = "NvEncodeAPICreateInstance returned a table with essential slots NULL";
        return false;
    }
    g_api_ok = true;
    return true;
}

const CodecArm* codec_ladder(size_t* count)
{
    static const CodecArm arms[] = {
        { &NV_ENC_CODEC_H264_GUID, "H.264" },
        { &NV_ENC_CODEC_HEVC_GUID, "HEVC"  },
        { &NV_ENC_CODEC_AV1_GUID,  "AV1"   },
    };
    *count = sizeof(arms) / sizeof(arms[0]);
    return arms;
}

void NvencEncoder::note_last_error(const char* tag)
{
    last_err_str_.clear();
    if (!L_.nvEncGetLastErrorString || !enc_) return;
    const char* m = L_.nvEncGetLastErrorString(enc_);
    if (m && (unsigned char)m[0] >= 0x20 && (unsigned char)m[0] < 0x7F) last_err_str_ = m;
    (void)tag;
}

bool NvencEncoder::open(ID3D11Device* dev, const char* codec_name, const GUID& codec, std::string* err)
{
    std::string why;
    if (!runtime_available(&why)) { *err = why; return false; }
    L_ = g_api;
    api_ok_ = true;
    codec_ = codec;
    codec_name_ = codec_name;

    NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS p;
    memset(&p, 0, sizeof(p));
    p.version    = NV_ENC_OPEN_ENCODE_SESSION_EX_PARAMS_VER;
    p.deviceType = NV_ENC_DEVICE_TYPE_DIRECTX;
    p.device     = dev;
    p.apiVersion = NVENCAPI_VERSION;

    NVENCSTATUS s = L_.nvEncOpenEncodeSessionEx(&p, &enc_);
    if (s != NV_ENC_SUCCESS || !enc_) {
        char b[256];
        snprintf(b, sizeof(b), "NvEncOpenEncodeSessionEx -> %d (%s)", (int)s, status_name(s));
        *err = b;
        if (s == NV_ENC_ERR_INCOMPATIBLE_CLIENT_KEY)
            *err += "  [this is the MEASURED concurrent-session refusal on this driver, not OUT_OF_MEMORY]";
        return false;
    }
    return true;
}

bool NvencEncoder::initialize(uint32_t w, uint32_t h, uint32_t fps_num, uint32_t fps_den,
                              uint32_t bitrate_bps, uint32_t gop_len, std::string* err)
{
    if (!enc_) { *err = "initialize() called with no open session"; return false; }
    w_ = w; h_ = h; fps_num_ = fps_num; fps_den_ = fps_den;
    bitrate_ = bitrate_bps; gop_len_ = gop_len;

    // The driver's OWN preset config is the contract.  A hand-built one is refused with
    // status 8 and a misleading message (measured).
    NV_ENC_PRESET_CONFIG pc;
    memset(&pc, 0, sizeof(pc));
    pc.version           = NV_ENC_PRESET_CONFIG_VER;
    pc.presetCfg.version = NV_ENC_CONFIG_VER;

    NVENCSTATUS s = L_.nvEncGetEncodePresetConfigEx(enc_, codec_, NV_ENC_PRESET_P3_GUID,
                                                    NV_ENC_TUNING_INFO_LOW_LATENCY, &pc);
    if (s != NV_ENC_SUCCESS) {
        char b[256];
        snprintf(b, sizeof(b), "nvEncGetEncodePresetConfigEx(P3, LOW_LATENCY) -> %d (%s)", (int)s, status_name(s));
        *err = b;
        return false;
    }

    // --- overrides on top of the driver's config ------------------------------------
    pc.presetCfg.gopLength      = gop_len;   // the forced-IDR cadence (spec 03 §2.5)
    pc.presetCfg.frameIntervalP = 1;         // P-only: 1-in-1-out, bounded latency
    pc.presetCfg.rcParams.rateControlMode = NV_ENC_PARAMS_RC_CBR;
    pc.presetCfg.rcParams.averageBitRate  = bitrate_bps;
    pc.presetCfg.rcParams.maxBitRate      = bitrate_bps;
    pc.presetCfg.rcParams.vbvBufferSize   = bitrate_bps;   // in BITS: ~1 s of VBV
    pc.presetCfg.rcParams.vbvInitialDelay = bitrate_bps;
    pc.presetCfg.rcParams.enableLookahead = 0;             // lookahead costs CUDA time
    pc.presetCfg.rcParams.lookaheadDepth  = 0;
    pc.presetCfg.rcParams.zeroReorderDelay = 1;            // low latency: num_reorder_frames=0
    pc.presetCfg.rcParams.enableAQ        = 0;
    pc.presetCfg.rcParams.multiPass       = NV_ENC_MULTI_PASS_DISABLED;

    if (codec_ == NV_ENC_CODEC_H264_GUID) {
        pc.presetCfg.encodeCodecConfig.h264Config.idrPeriod    = gop_len;
        pc.presetCfg.encodeCodecConfig.h264Config.repeatSPSPPS = 1;  // SPS/PPS on every IDR
        pc.presetCfg.encodeCodecConfig.h264Config.outputAUD    = 0;
        pc.presetCfg.encodeCodecConfig.h264Config.disableSPSPPS = 0;
        pc.presetCfg.encodeCodecConfig.h264Config.enableIntraRefresh = 0;
        pc.presetCfg.encodeCodecConfig.h264Config.hierarchicalPFrames = 0;
        pc.presetCfg.encodeCodecConfig.h264Config.hierarchicalBFrames = 0;
        pc.presetCfg.encodeCodecConfig.h264Config.enableFillerDataInsertion = 0;
    } else if (codec_ == NV_ENC_CODEC_HEVC_GUID) {
        pc.presetCfg.encodeCodecConfig.hevcConfig.idrPeriod    = gop_len;
        pc.presetCfg.encodeCodecConfig.hevcConfig.repeatSPSPPS = 1;
        pc.presetCfg.encodeCodecConfig.hevcConfig.outputAUD    = 0;
    }

    NV_ENC_INITIALIZE_PARAMS ip;
    memset(&ip, 0, sizeof(ip));
    ip.version         = NV_ENC_INITIALIZE_PARAMS_VER;
    ip.encodeGUID      = codec_;
    ip.presetGUID      = NV_ENC_PRESET_P3_GUID;
    ip.encodeWidth     = w;
    ip.encodeHeight    = h;
    ip.darWidth        = w;
    ip.darHeight       = h;
    ip.frameRateNum    = fps_num;
    ip.frameRateDen    = fps_den;
    ip.enablePTD       = 1;
    ip.bufferFormat    = NV_ENC_BUFFER_FORMAT_NV12;
    ip.enableEncodeAsync = 0;    // the encoder has its own thread; no second hidden queue
    // tuningInfo = UNDEFINED (0) is INVALID and returns status 12 (measured).
    ip.tuningInfo = (g_fault == Fault::TuningUndefined)
                        ? NV_ENC_TUNING_INFO_UNDEFINED
                        : NV_ENC_TUNING_INFO_LOW_LATENCY;
    ip.encodeConfig = &pc.presetCfg;

    s = L_.nvEncInitializeEncoder(enc_, &ip);
    if (s != NV_ENC_SUCCESS) {
        note_last_error("initialize");
        char b[320];
        snprintf(b, sizeof(b), "NvEncInitializeEncoder -> %d (%s)", (int)s, status_name(s));
        *err = b;
        if (!last_err_str_.empty()) *err += "  driver says: \"" + last_err_str_ + "\"";
        return false;
    }

    // Bitstream buffer.  NV_ENC_CREATE_BITSTREAM_BUFFER::size is marked DEPRECATED in
    // this header, so it is left 0 and the driver sizes it.
    NV_ENC_CREATE_BITSTREAM_BUFFER cb;
    memset(&cb, 0, sizeof(cb));
    cb.version = NV_ENC_CREATE_BITSTREAM_BUFFER_VER;
    s = L_.nvEncCreateBitstreamBuffer(enc_, &cb);
    if (s != NV_ENC_SUCCESS) {
        char b[256];
        snprintf(b, sizeof(b), "nvEncCreateBitstreamBuffer -> %d (%s)", (int)s, status_name(s));
        *err = b;
        return false;
    }
    bs_ = cb.bitstreamBuffer;
    return true;
}

bool NvencEncoder::query_caps(std::string* err)
{
    // ONLY safe on an INITIALISED session: measured, this call on an opened-but-
    // uninitialised session SEGFAULTS with no error status.
    if (!enc_) { *err = "query_caps() called with no open session"; return false; }
    struct CapQ { NV_ENC_CAPS c; uint32_t* out; const char* name; };
    uint32_t engines = 0, wmax = 0, hmax = 0;
    CapQ qs[3] = {
        { NV_ENC_CAPS_NUM_ENCODER_ENGINES, &engines, "NUM_ENCODER_ENGINES" },
        { NV_ENC_CAPS_WIDTH_MAX,           &wmax,    "WIDTH_MAX" },
        { NV_ENC_CAPS_HEIGHT_MAX,          &hmax,    "HEIGHT_MAX" },
    };
    for (int i = 0; i < 3; ++i) {
        NV_ENC_CAPS_PARAM cp;
        memset(&cp, 0, sizeof(cp));
        cp.version     = NV_ENC_CAPS_PARAM_VER;
        cp.capsToQuery = qs[i].c;
        int val = -1;
        NVENCSTATUS s = L_.nvEncGetEncodeCaps(enc_, codec_, &cp, &val);
        if (s != NV_ENC_SUCCESS) {
            char b[256];
            snprintf(b, sizeof(b), "nvEncGetEncodeCaps(%s) -> %d (%s)", qs[i].name, (int)s, status_name(s));
            *err = b;
            return false;
        }
        *qs[i].out = (uint32_t)val;
    }
    caps_.engines = engines; caps_.max_w = wmax; caps_.max_h = hmax; caps_.queried = true;

    if (w_ > wmax || h_ > hmax) {
        char b[256];
        snprintf(b, sizeof(b), "%ux%u exceeds %s's measured maximum %ux%u on this driver",
                 w_, h_, codec_name_, wmax, hmax);
        *err = b;
        return false;
    }
    return true;
}

bool NvencEncoder::register_and_map(ID3D11Texture2D* nv12, std::string* err)
{
    if (!enc_) { *err = "register_and_map() called with no open session"; return false; }

    NV_ENC_REGISTER_RESOURCE rr;
    memset(&rr, 0, sizeof(rr));
    rr.version            = NV_ENC_REGISTER_RESOURCE_VER;
    rr.resourceType       = NV_ENC_INPUT_RESOURCE_TYPE_DIRECTX;
    rr.width              = w_;
    rr.height             = h_;
    rr.pitch              = 0;                       // required 0 for DIRECTX resources
    rr.subResourceIndex   = 0;
    rr.resourceToRegister = nv12;
    rr.bufferFormat       = NV_ENC_BUFFER_FORMAT_NV12;
    rr.bufferUsage        = NV_ENC_INPUT_IMAGE;

    NVENCSTATUS s = L_.nvEncRegisterResource(enc_, &rr);
    if (s != NV_ENC_SUCCESS || !rr.registeredResource) {
        char b[256];
        snprintf(b, sizeof(b), "NvEncRegisterResource -> %d (%s)", (int)s, status_name(s));
        *err = b;
        if (s == NV_ENC_ERR_DEVICE_NOT_EXIST)
            *err += "  [status 5 here means the session is not in the state it must be in,"
                    " not that the device is missing]";
        return false;
    }
    reg_ = rr.registeredResource;

    if (g_fault == Fault::SkipResourceMap) {
        *err = "INJECTED FAULT: registered the texture but skipped NvEncMapInputResource";
        return false;
    }

    NV_ENC_MAP_INPUT_RESOURCE mr;
    memset(&mr, 0, sizeof(mr));
    mr.version            = NV_ENC_MAP_INPUT_RESOURCE_VER;
    mr.registeredResource = reg_;
    s = L_.nvEncMapInputResource(enc_, &mr);
    if (s != NV_ENC_SUCCESS || !mr.mappedResource) {
        char b[256];
        snprintf(b, sizeof(b), "NvEncMapInputResource -> %d (%s)", (int)s, status_name(s));
        *err = b;
        return false;
    }
    mapped_ = mr.mappedResource;
    mapped_ok_ = true;
    return true;
}

bool NvencEncoder::encode(bool force_idr, uint64_t pts, std::string* err)
{
    if (!enc_ || !mapped_ok_ || !bs_) { *err = "encode() called before the session was fully armed"; return false; }

    NV_ENC_PIC_PARAMS pp;
    memset(&pp, 0, sizeof(pp));
    pp.version       = NV_ENC_PIC_PARAMS_VER;
    pp.inputWidth    = w_;
    pp.inputHeight   = h_;
    pp.inputPitch    = 0;
    pp.inputBuffer   = mapped_;
    pp.outputBitstream = bs_;
    pp.bufferFmt     = NV_ENC_BUFFER_FORMAT_NV12;
    pp.pictureStruct = NV_ENC_PIC_STRUCT_FRAME;
    pp.frameIdx      = frame_idx_++;
    pp.inputTimeStamp = pts;
    // pictureType is only required when enablePTD = 0; we run with enablePTD = 1.
    pp.encodePicFlags = force_idr ? (uint32_t)NV_ENC_PIC_FLAG_FORCEIDR : 0u;

    NVENCSTATUS s = L_.nvEncEncodePicture(enc_, &pp);
    if (s != NV_ENC_SUCCESS) {
        note_last_error("encode");
        char b[320];
        snprintf(b, sizeof(b), "NvEncEncodePicture%s -> %d (%s)",
                 force_idr ? "(FORCEIDR)" : "", (int)s, status_name(s));
        *err = b;
        if (!last_err_str_.empty()) *err += "  driver says: \"" + last_err_str_ + "\"";
        return false;
    }

    NV_ENC_LOCK_BITSTREAM lb;
    memset(&lb, 0, sizeof(lb));
    lb.version         = NV_ENC_LOCK_BITSTREAM_VER;
    lb.outputBitstream = bs_;
    lb.doNotWait       = 0;
    s = L_.nvEncLockBitstream(enc_, &lb);
    if (s != NV_ENC_SUCCESS) {
        note_last_error("lock");
        char b[320];
        snprintf(b, sizeof(b), "NvEncLockBitstream -> %d (%s)", (int)s, status_name(s));
        *err = b;
        return false;
    }

    out_.assign((const uint8_t*)lb.bitstreamBufferPtr,
                (const uint8_t*)lb.bitstreamBufferPtr + lb.bitstreamSizeInBytes);
    last_pt_  = (int)lb.pictureType;
    last_idr_ = (lb.pictureType == NV_ENC_PIC_TYPE_IDR);
    L_.nvEncUnlockBitstream(enc_, bs_);

    ++frames_;
    ready_ = true;
    return true;
}

bool NvencEncoder::sequence_params(std::vector<uint8_t>* out, std::string* err)
{
    out->clear();
    if (!enc_ || !L_.nvEncGetSequenceParams) { *err = "nvEncGetSequenceParams not available"; return false; }
    std::vector<uint8_t> buf(8192, 0);
    NV_ENC_SEQUENCE_PARAM_PAYLOAD sp;
    memset(&sp, 0, sizeof(sp));
    sp.version              = NV_ENC_SEQUENCE_PARAM_PAYLOAD_VER;
    sp.inBufferSize         = (uint32_t)buf.size();
    sp.spsppsBuffer         = buf.data();
    uint32_t outsize        = 0;
    sp.outSPSPPSPayloadSize = &outsize;
    NVENCSTATUS s = L_.nvEncGetSequenceParams(enc_, &sp);
    if (s != NV_ENC_SUCCESS) {
        char b[256];
        snprintf(b, sizeof(b), "nvEncGetSequenceParams -> %d (%s)", (int)s, status_name(s));
        *err = b;
        return false;
    }
    out->assign(buf.begin(), buf.begin() + outsize);
    return true;
}

void NvencEncoder::release_handles()
{
    if (!api_ok_) return;
    if (mapped_ && enc_ && L_.nvEncUnmapInputResource) {
        L_.nvEncUnmapInputResource(enc_, mapped_);
        mapped_ = nullptr; mapped_ok_ = false;
    }
    if (reg_ && enc_ && L_.nvEncUnregisterResource) {
        L_.nvEncUnregisterResource(enc_, reg_);
        reg_ = nullptr;
    }
    if (bs_ && enc_ && L_.nvEncDestroyBitstreamBuffer) {
        L_.nvEncDestroyBitstreamBuffer(enc_, bs_);
        bs_ = nullptr;
    }
}

void NvencEncoder::close()
{
    release_handles();
    if (enc_ && api_ok_ && L_.nvEncDestroyEncoder) {
        L_.nvEncDestroyEncoder(enc_);
        enc_ = nullptr;
    }
    ready_ = false;
}

} // namespace aireplay
