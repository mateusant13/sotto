// replay.h — the whole path: WGC -> NV12 -> NVENC -> RAM ring -> clip.mp4.
//
// Spec 03.  Two threads, and no more: the run loop owns capture+convert+encode+append,
// and a cut thread writes the clip so that RECORDING CONTINUES while the clip is written
// (law 1 + spec 01 §5: the clip is on the critical path, but it must not stop capture).
//
// The cut PINS the ring range it needs, so appending during the write cannot overwrite
// the bytes being muxed.
#pragma once
#include "common.h"

#include <condition_variable>
#include <mutex>
#include <thread>

#include "d3d11_ctx.h"
#include "mp4_writer.h"
#include "nv12_convert.h"
#include "nvenc_encoder.h"
#include "ring_buffer.h"
#include "test_window.h"
#include "wgc_capture.h"

namespace aireplay {

struct ModeNumbers {
    const char* name;
    uint32_t    fps;
    uint32_t    anchor_bitrate;   // at 1920x1080 and `fps`
    uint32_t    idr_ms;
    uint32_t    ring_seconds;
};

// Specs 01 §1.  NOTE: specs/01's "bpp" figures (0.036 gaming / 0.013 desktop) are a
// FACTOR OF TEN off its own table — 45 Mbps at 1080p60 is 0.362 bits/pixel, not 0.036.
// This lane uses the table's anchor bitrates and scales by pixels, which reproduces the
// table exactly, and records the discrepancy rather than propagating it.
const ModeNumbers* mode_numbers(const std::string& name);

struct RunConfig {
    std::string mode = "gaming";
    std::string codec = "H.264";
    uint32_t    fps = 0;             // 0 => from the mode
    uint32_t    bitrate = 0;         // 0 => from the mode and the pixel count
    uint32_t    idr_ms = 0;          // 0 => from the mode
    uint32_t    ring_seconds = 0;    // 0 => from the mode
    uint64_t    ring_bytes = 0;      // 0 => derived (law 7)
    uint32_t    run_seconds = 20;
    double      cut_at_s = 10.0;
    bool        use_monitor = false;
    bool        use_test_window = true;
    // The capture window as a REQUEST.  0 (or one side 0) => AUTO: follow the measured output
    // desktop.  A non-zero pair is honoured when the display can carry it and CLAMPED when it
    // cannot, with the clamp said out loud.  Before lane 7 this was the literal 1920x1080 at
    // replay.cpp:57, which is why every 1440p/4K figure in this repo was arithmetic.
    uint32_t    capture_w = 0;
    uint32_t    capture_h = 0;
    int         test_window_x = INT_MIN;   // INT_MIN => the 4x4 on-desktop sliver
    int         test_window_y = INT_MIN;
    bool        test_window_top = false;   // true => the sliver is NOT occluded by the taskbar
    int         test_window_alpha = -1;    // >=0 => full-desktop LAYERED window at this alpha
    std::string out_path;
};

struct CutResult {
    bool        ok = false;
    std::string path;
    std::string note;
    uint64_t    frames_in_clip = 0;
    uint64_t    encoded_in_window = 0;
    uint64_t    captured_in_window = 0;
    uint64_t    expected_in_window = 0;
    uint64_t    ring_dropped_at_cut = 0;
    uint64_t    bytes = 0;
    uint64_t    base_qpc_ns = 0;
    uint64_t    cut_qpc_ns = 0;
    uint64_t    base_abs = 0;      // ring offsets the cut pinned
    uint64_t    end_abs = 0;
    double      clip_seconds = 0;
    double      idr_pre_roll_ms = 0;
    double      wall_ms = 0;
};

class Replay {
public:
    Replay();
    ~Replay();

    // LAW 6 GATE + full initialisation.  Returns false when NO encoder really
    // initialised — in which case nothing is armed and *err says why, in the driver's
    // own words plus the raw status code.
    bool arm(const RunConfig& cfg, std::string* err);

    bool run(std::string* err);

    void shutdown();

    const Stats& stats() const { return stats_; }
    const CutResult& last_cut() const { return last_cut_; }
    const RunConfig& cfg() const { return cfg_; }
    uint64_t ring_capacity() const { return ring_cap_; }
    const EncoderCaps& caps() const { return caps_; }
    const char* armed_codec() const { return armed_codec_; }
    // True once the LAW 6 gate passed.  main() uses this to tell a law-6 REFUSAL apart
    // from "the encoder armed and a later setup step failed" — two different failures
    // that must never wear the same word.
    bool encoder_armed() const { return gate_passed_; }
    uint32_t width() const { return w_; }
    uint32_t height() const { return h_; }
    // How the capture window was decided, and why.  main() and the receipts quote this; the
    // gate asserts on it.  `valid()` is false for an OFFLINE cut, which has no desktop.
    const WindowDecision& window_decision() const { return window_decision_; }
    // Measured count of output-desktop changes seen by the test window DURING the run.
    uint32_t display_changes() const { return display_changes_; }
    const char* cap_kind() const { return cap_.item_kind(); }
    uint64_t ring_used() const { return ring_.bytes_used(); }
    uint64_t ring_evictions() const { return ring_.evictions(); }

    // OFFLINE VALIDATION OF THE CUT PATH — no WGC, no NVENC, no D3D11.  Fills the ring from
    // a real Annex-B H.264 elementary stream (`ffmpeg -bsf:v h264_mp4toannexb`) and runs the
    // SAME perform_cut() the live path runs.  This exists because WGC began refusing every
    // capture item on this box (E_ACCESSDENIED, receipt §7), and a muxer that can only be
    // exercised through the one component that broke is not provable.
    bool cut_from_h264(const std::string& h264_path, const std::string& out_path,
                       uint32_t fps, uint32_t w, uint32_t h, std::string* err);

    // Where the test window actually landed — the receipt quotes this.
    RECT test_window_rect() const { return tw_rect_; }
    uint64_t test_window_paints() const { return tw_.paint_count(); }
    uint64_t test_window_paint_ns() const { return tw_.paint_ns(); }
    uint64_t test_window_loop_iters() const { return tw_.loop_iters(); }
    uint64_t test_window_update_ns() const { return tw_.update_ns(); }

private:
    bool build_target(uint32_t* w, uint32_t* h, std::string* err);
    bool do_gate(std::string* err);
    void cut_thread_main();
    bool perform_cut(CutResult& r);

    RunConfig    cfg_;
    D3d11Context d3d_;
    Nv12Converter conv_;
    NvencEncoder enc_;
    WgcCapture   cap_;
    RingBuffer   ring_;
    TestWindow   tw_;
    RECT         tw_rect_ = { 0, 0, 0, 0 };

    ID3D11Texture2D* nv12_ = nullptr;
    uint32_t w_ = 0, h_ = 0;
    WindowDecision window_decision_;
    uint32_t display_changes_ = 0;
    uint32_t idr_ms_ = 2000;
    uint64_t ring_cap_ = 0;
    EncoderCaps caps_;
    const char* armed_codec_ = "none";
    bool        gate_passed_ = false;
    Stats stats_;

    std::vector<uint64_t> capture_qpc_;

    // cut plumbing
    std::thread             cut_thread_;
    std::mutex              cut_mu_;
    std::condition_variable cut_cv_;
    std::condition_variable cut_done_cv_;
    bool                    cut_quit_ = false;
    bool                    cut_has_job_ = false;
    bool                    cut_busy_ = false;
    CutResult               cut_job_;
    CutResult               last_cut_;
    uint64_t                seq_ = 0;
    uint64_t                next_idr_ns_ = 0;

    void issue_cut(uint64_t t_cut_ns);
    bool wait_cut_done(uint32_t timeout_ms);
};

} // namespace aireplay
