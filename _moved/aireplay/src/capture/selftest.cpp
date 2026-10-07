#include "selftest.h"

namespace aireplay {

GateResult law_six_gate(ID3D11Device* dev, ID3D11Texture2D* nv12,
                        uint32_t w, uint32_t h,
                        uint32_t fps, uint32_t bitrate, uint32_t gop,
                        const std::string& codec_pref,
                        NvencEncoder* enc)
{
    GateResult r;
    size_t n = 0;
    const CodecArm* arms = codec_ladder(&n);
    const bool want_auto = (codec_pref.empty() || codec_pref == "auto");
    std::string tried;

    for (size_t i = 0; i < n; ++i) {
        if (!want_auto && codec_pref != arms[i].name) continue;
        ++r.arms_tried;
        log_line("  ARM %s: open -> initialise (P3 + LOW_LATENCY) -> caps -> register+map a real NV12 texture",
                 arms[i].name);
        std::string e;
        if (!enc->open(dev, arms[i].name, *arms[i].guid, &e)) {
            log_line("    REFUSED at OPEN         : %s", e.c_str());
            tried += std::string(arms[i].name) + ":open(" + e + ") ";
            enc->close();
            continue;
        }
        if (!enc->initialize(w, h, fps, 1, bitrate, gop, &e)) {
            log_line("    REFUSED at INITIALIZE   : %s", e.c_str());
            tried += std::string(arms[i].name) + ":init(" + e + ") ";
            enc->close();
            continue;
        }
        if (!enc->query_caps(&e)) {
            log_line("    REFUSED at CAPS         : %s", e.c_str());
            tried += std::string(arms[i].name) + ":caps(" + e + ") ";
            enc->close();
            continue;
        }
        if (!nv12) {
            log_line("    REFUSED at REGISTER+MAP : no NV12 texture to prove the zero-copy path with");
            tried += std::string(arms[i].name) + ":map(no texture) ";
            enc->close();
            continue;
        }
        if (!enc->register_and_map(nv12, &e)) {
            log_line("    REFUSED at REGISTER+MAP : %s", e.c_str());
            log_line("    (a session that cannot ingest OUR texture records nothing, so it is NOT an encoder)");
            tried += std::string(arms[i].name) + ":map(" + e + ") ";
            enc->close();
            continue;
        }

        r.armed = true;
        r.codec = arms[i].name;
        r.caps = enc->caps();
        log_line("    OK: %s initialised; engines=%u max=%ux%u; zero-copy input registered AND mapped",
                 arms[i].name, r.caps.engines, r.caps.max_w, r.caps.max_h);
        return r;
    }

    r.reason = "NO ENCODER INITIALISED - the replay hotkey is NOT armed. Attempted: " +
               (tried.empty() ? std::string("(no arm matched the requested codec)") : tried);

#ifdef AIREPLAY_GATE_OFF
    // ------------------------------------------------------------------------------
    // THE CONTROL, and the only reason this branch exists: a build with the law-6 gate
    // DELETED.  With a broken encoder this build must report ARMED — if it does not, the
    // gate is not what is refusing, and every "refused" result above is worthless.
    // ------------------------------------------------------------------------------
    r.armed = true;
    r.codec = "MUTANT(no gate)";
    r.caps = enc->caps();
    r.reason = "GATE REMOVED (control build): armed=true even though no encoder initialised";
    log_line("    *** CONTROL BUILD (AIREPLAY_GATE_OFF): reporting ARMED with no working encoder ***");
#endif
    return r;
}

} // namespace aireplay
