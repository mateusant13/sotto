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
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

#include "d3d11_ctx.h"
#include "mp4_writer.h"
#include "nv12_convert.h"
#include "nvenc_encoder.h"
#include "ring_buffer.h"
#include "test_window.h"
#include "trigger.h"
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
    // THE HOTKEY, and it is OFF by default on purpose.  arm_hotkey() registers GLOBAL keys on
    // the owner's desktop (F10/F11/F9/F12/PrintScreen by default) and wakes a thread every 8 ms.
    // A measurement run must never take that decision for the owner, and the CLI flag that turns
    // it on lives in main.cpp, which is ANOTHER LANE's file — receipts\receipt-34 names the exact
    // line to add.  Until that flag exists the hotkey is reachable from arm_hotkey() and from the
    // gate, and NOT from a bare `aireplay-capture` run.
    bool        hotkey = false;
    double      hotkey_window_s = 0;       // 0 => the trigger's own default (30 s)
    // Non-empty => ONE FILE PER CLIP, named <clip_id>.mp4.  Without it every press writes
    // cfg_.out_path and the second hotkey overwrites the first clip the owner just saved.
    std::string out_dir;
};

struct CutResult {
    bool        ok = false;
    std::string path;
    std::string note;
    // --- IDENTITY AND THE TWO FIELDS AN INDEX CONSUMER WAS REFUSED (§S5 of review-L4) -----------
    // Minted HERE, by the capture side, because the index store REFUSES to invent one
    // (store.py: "clip payload has no clip_id; refusing to invent one").  Format matches the clip
    // directories already on disk: 20261007T130417Z-0013 — compact UTC to the second, then the
    // per-run sequence, so the name is sortable and unique inside one run.
    std::string clip_id;
    // EPOCH seconds of the clip window START (the base frame), NOT the cut time: that is the axis
    // a library-wide `since_s/until_s` filter runs on, and it is the field that was NULL for every
    // clip so far.  0.0 => unknown (the base frame's QPC could not be converted).
    double      started_at_s = 0;
    // "cutting" while the muxer runs, then "recorded" or "failed".  See ClipAnchor below.
    std::string state;
    std::string origin;                   // "hotkey:F10", "timer", "offline-cut" — who asked
    // --- THE RETROACTIVE WINDOW, as requested and as delivered ---------------------------------
    double      requested_window_s = 0;   // what the hotkey asked for
    double      delivered_window_s = 0;   // what the ring could actually give
    double      shortfall_s        = 0;   // requested - delivered, > 0 only when truncated
    bool        window_truncated   = false;
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

// ------------------------------------------------------------------ THE RETROACTIVE WINDOW
//
// The product in one PURE function.  A hotkey at wall time T must yield the clip [T-N, T] out of
// a ring that has been recording all along — there is no "recording started now", and that is the
// whole difference between this and a screen recorder.  A ring plus two numbers in, a plan out:
// no WGC, no NVENC, no D3D11, no thread.  That purity is not tidiness.  WGC refuses every item on
// this host (CreateForWindow failed 0x80070005), so the live path is unprovable here, and the case
// that must NEVER be silent — asking for more than the ring holds — is only reachable through a
// seam that runs without a capture device.
struct WindowPlan {
    bool        ok          = false;   // a base IDR exists => a clip is possible at all
    size_t      base_index  = 0;
    uint64_t    base_abs    = 0;
    uint64_t    end_abs     = 0;       // one past the newest byte AT PLAN TIME
    uint64_t    base_qpc_ns = 0;
    uint64_t    cut_qpc_ns  = 0;
    double      requested_s = 0;
    double      ring_span_s = 0;       // MEASURED: oldest frame still held -> the cut
    double      delivered_s = 0;       // what this plan can actually give
    double      shortfall_s = 0;
    bool        truncated   = false;   // requested_s > ring_span_s.  SAID, never silent.
    bool        ring_empty  = false;
    bool        no_idr      = false;   // nothing decodable is held: refuse rather than write
    std::string note;
};

// requested_s <= 0 means "the whole ring", which is what the offline cut and the timer cut use.
bool plan_retroactive_window(const RingBuffer& ring, uint64_t t_cut_ns, double requested_s,
                             WindowPlan* out);

// QPC -> epoch seconds.  MEASURED, never assumed: one (FILETIME, QPC) pair is sampled per call,
// because no QPC value on Windows is an epoch value until it is offset by something.
double      qpc_to_epoch_seconds(uint64_t qpc_ns);
uint64_t    qpc_epoch_offset_ns();      // the sampled offset itself, so a receipt can quote it
std::string mint_clip_id(double epoch_s, uint64_t seq);

// Fill `ring` from an Annex-B H.264 elementary stream (the offline path's loader, factored out so
// the gate and cut_from_h264() seed the ring the SAME way).  `au_idr_out`, when non-null, receives
// one flag per access unit.  Returns the number of access units appended, or 0 with *err set.
size_t ring_seed_from_h264(RingBuffer* ring, const std::string& h264_path, uint32_t fps,
                           std::vector<bool>* au_idr_out, std::string* err);

// ------------------------------------------------------------------ THE 'cutting' ANCHOR
//
// Spec §2.1 T0 and the §2.5 repair ladder, from the capture side.  The reviewer's S4 (HIGH) is
// that `state='cutting'` has ZERO producers in this repo, so the ladder that scans for it has
// nothing to scan — and the fix is a call site, not a rename.  perform_cut() fires
// on_clip_anchor() immediately BEFORE Mp4Writer::open(), i.e. before the first byte of the clip
// exists on disk, and on_clip_done() after the muxer closed.  src/index/** is ANOTHER LANE's;
// receipts\receipt-34-retroactive-clip.md §ANCHOR names the exact call site it should wire, and
// this file's line numbers are printed here so the two edits can be made in one pass.
struct ClipAnchor {
    std::string clip_id;
    std::string path;
    const char* state = "cutting";     // the literal the §2.5 ladder scans for
    double      started_at_s = 0;
    double      requested_window_s = 0;
    double      delivered_window_s = 0;
    bool        window_truncated = false;
    double      shortfall_s = 0;
    uint64_t    base_abs = 0, end_abs = 0;
    uint64_t    base_qpc_ns = 0, cut_qpc_ns = 0;
    uint32_t    width = 0, height = 0;
    double      fps_measured = 0;
};

class ClipAnchorSink {
public:
    virtual ~ClipAnchorSink() {}
    // BEFORE the file exists.  An index consumer writes its row here (state='cutting'), so a file
    // can never exist without a row and the ladder can always find the orphans.
    virtual void on_clip_anchor(const ClipAnchor& a) = 0;
    // AFTER the muxer closed; r.state is final ("recorded" / "failed").
    virtual void on_clip_done(const CutResult& r) = 0;
};

class Replay : public RingSpanProbe {
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
    // The ring itself, read-only.  Exposed so a gate can plan a window against the ring the
    // SHIPPED code filled, instead of seeding a second one behind the product's back.
    const RingBuffer& ring() const { return ring_; }

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

    // --- THE HOTKEY -----------------------------------------------------------------------
    // Arms the trigger with `bindings` (empty => default_binding_ladder()) and installs the ring
    // probe, so a press can report how much history the ring actually holds.  Called by arm() when
    // cfg_.hotkey is set, and directly by the gate.  The window default is cfg_.hotkey_window_s.
    bool arm_hotkey(const std::vector<HotkeyBinding>& bindings, double window_s, std::string* err);
    void disarm_hotkey();
    bool hotkey_armed() const { return trigger_ && trigger_->armed(); }
    Trigger* hotkey() { return trigger_.get(); }              // the consumer side (take) is non-const
    const Trigger* hotkey() const { return trigger_.get(); }
    uint64_t hotkey_cuts() const { return hotkey_cuts_; }   // requests the run loop consumed
    uint64_t hotkey_requests_dropped() const;              // busy cut thread => press refused, NOT lost

    // --- THE RETROACTIVE CUT, as the hotkey drives it ----------------------------------------
    // [t_cut_ns - requested_window_s, t_cut_ns] out of the ring.  MUST be called from the capture
    // thread (the run loop): it reads capture_qpc_ to count what the window should have held.
    void request_cut(uint64_t t_cut_ns, double requested_window_s, const std::string& origin);

    // THE SOUND OF THE CLIP.  NULL (the default) means the cut writes VIDEO ONLY — the
    // unchanged pre-audio shape.  When a ring is attached the cut reads the SAME window
    // [base_qpc_ns, cut_qpc_ns] out of it, on the SAME qpc clock the video ring stamps
    // f.qpc_ns with, and writes the samples into the clip the video loop is already writing.
    void set_audio_ring(AudioRing* ring) { audio_ring_ = ring; }
    AudioRing* audio_ring() const { return audio_ring_; }

    // What the last cut did with audio.  Filled by perform_cut_body so a run log can state
    // the route that actually shipped (aac or pcm or none) and why, instead of the reader
    // having to infer it from the file.
    const std::string& audio_route() const { return audio_route_; }
    const std::string& audio_route_note() const { return audio_route_note_; }
    uint64_t audio_frames_in_clip() const { return audio_frames_; }
    double   audio_seconds_in_clip() const { return audio_seconds_; }
    double   audio_skew_ms() const { return audio_skew_ms_; }

    // NULL by default: no index, no row, no anchor — and no clip is written in this process.
    void set_clip_anchor_sink(ClipAnchorSink* s) { clip_sink_ = s; }
    ClipAnchorSink* clip_anchor_sink() const { return clip_sink_; }

    // RingSpanProbe: seconds of encoded history held RIGHT NOW, measured from the ring's own
    // oldest and newest entries.  0.0 when the ring is empty, -1 only if the ring cannot be read.
    double span_seconds() override;

private:
    bool build_target(uint32_t* w, uint32_t* h, std::string* err);
    bool do_gate(std::string* err);
    void cut_thread_main();
    bool perform_cut(CutResult& r, const WindowPlan* plan);
    bool perform_cut_body(CutResult& r, const WindowPlan* plan);
    // Turns a plan into a job: identity, epoch, truncation, state.  One function so the LIVE path,
    // the offline cut and the gate all mint clip_id and started_at_s by the same code.
    bool plan_job(uint64_t t_cut_ns, double requested_window_s, const std::string& origin,
                  CutResult& job, WindowPlan& plan);
    void fire_anchor(const CutResult& r, const WindowPlan& p, double fps_measured);

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
    WindowPlan              cut_plan_;
    CutResult               last_cut_;
    uint64_t                seq_ = 0;
    uint64_t                next_idr_ns_ = 0;
    uint64_t                clip_seq_ = 0;      // the NNNN half of clip_id

    std::unique_ptr<Trigger> trigger_;          // null unless arm_hotkey() ran
    ClipAnchorSink*          clip_sink_ = nullptr;   // BORROWED; cleared before destruction
    AudioRing*               audio_ring_ = nullptr;    // BORROWED; the tap owns the memory
    std::string              audio_route_ = "none";    // "aac" | "pcm" | "none"
                                                        // "none" = no audio ring was attached,
                                                        // so no trak was written -- never "" 
    std::string              audio_route_note_;        // WHY that route, in one line
    uint64_t                 audio_frames_ = 0;        // samples-frames written to the last clip
    double                   audio_seconds_ = 0.0;     // what the clip carries, measured
    double                   audio_skew_ms_ = 0.0;     // audio minus video duration, in ms
    uint64_t                 hotkey_cuts_ = 0;
    uint64_t                 hotkey_dropped_ = 0;

    void issue_cut(uint64_t t_cut_ns);          // the timer cut: the whole ring
    bool wait_cut_done(uint32_t timeout_ms);
    void drain_hotkey();                        // run-loop hook: requests -> request_cut()
};

} // namespace aireplay
