#include "replay.h"

#include "selftest.h"

#include <algorithm>
#include <chrono>
#include <cmath>

namespace aireplay {

// ------------------------------------------------------------------ modes (specs 01 §1)
const ModeNumbers* mode_numbers(const std::string& name)
{
    static const ModeNumbers modes[] = {
        { "gaming",  60, 45000000u,  2000u, 120u },
        { "desktop", 30,  8000000u, 10000u, 600u },
    };
    for (const ModeNumbers& m : modes) if (name == m.name) return &m;
    return nullptr;
}

static void extract_sps_pps(const uint8_t* data, size_t size,
                            std::vector<uint8_t>& sps, std::vector<uint8_t>& pps)
{
    std::vector<NalSpan> nals;
    annexb_split(data, size, nals);
    for (const NalSpan& n : nals) {
        if (n.type == 7 && sps.empty()) sps.assign(n.data, n.data + n.size);
        if (n.type == 8 && pps.empty()) pps.assign(n.data, n.data + n.size);
    }
}

Replay::Replay() {}
Replay::~Replay() { shutdown(); }

// ------------------------------------------------------------------ target
//
// The capture window is a RUNTIME value (lane 7).  It used to be the literal 1920x1080 at
// replay.cpp:57, which made every 1440p/4K number in this repo arithmetic rather than
// measurement.  It is now negotiated against the MEASURED output desktop by a pure function
// (test_window.cpp: negotiate_capture_window), so it is testable over synthetic desktops on
// a machine whose only monitor is 1080p.
bool Replay::build_target(uint32_t* w, uint32_t* h, std::string* err)
{
    const DesktopInfo desk = query_output_desktop();
    log_line("  OUTPUT DESKTOP: %s", desk.note.c_str());

    if (cfg_.use_monitor) {
        POINT pt;
        pt.x = 0; pt.y = 0;
        HMONITOR mon = MonitorFromPoint(pt, MONITOR_DEFAULTTOPRIMARY);
        MONITORINFO mi;
        memset(&mi, 0, sizeof(mi));
        mi.cbSize = sizeof(mi);
        if (!GetMonitorInfo(mon, &mi)) { *err = "GetMonitorInfo failed"; return false; }
        *w = (uint32_t)(mi.rcMonitor.right - mi.rcMonitor.left);
        *h = (uint32_t)(mi.rcMonitor.bottom - mi.rcMonitor.top);
        log_line("  TARGET: PRIMARY MONITOR %ux%u  *** this is the owner's REAL DESKTOP; the run says so ***",
                 *w, *h);
        window_decision_ = WindowDecision();
        window_decision_.w = *w;
        window_decision_.h = *h;
        window_decision_.source = WindowDecision::Source::Monitor;
        window_decision_.note = "--monitor: the owner's primary monitor, by request";
        return true;
    }

    // Our own window, sized by the negotiation.  cfg_.capture_w/h == 0 means AUTO (follow the
    // output desktop).  The DEFAULT stays 1920x1080-on-a-1920x1080-desktop, byte-identical to
    // the pre-lane literal.
    const WindowDecision dec = negotiate_capture_window(cfg_.capture_w, cfg_.capture_h, desk);
    log_line("  WINDOW NEGOTIATION: %ux%u source=%s clamped=%d auto=%d even_floored=%d",
             dec.w, dec.h, window_source_name(dec.source), dec.clamped ? 1 : 0,
             dec.requested_auto ? 1 : 0, dec.even_floored ? 1 : 0);
    log_line("    %s", dec.note.c_str());
    if (!dec.ok()) { *err = "window negotiation produced a degenerate size"; return false; }

    tw_.set_topmost(cfg_.test_window_top);
    tw_.set_alpha(cfg_.test_window_alpha);
    if (!tw_.create(dec.w, dec.h, cfg_.test_window_x, cfg_.test_window_y, err)) return false;
    RECT r;
    GetWindowRect(tw_.hwnd(), &r);
    tw_rect_ = r;
    window_decision_ = dec;
    *w = dec.w; *h = dec.h;
    return true;
}

// ------------------------------------------------------------------ LAW 6 GATE
bool Replay::do_gate(std::string* err)
{
    uint32_t gop = (uint32_t)((uint64_t)cfg_.fps * idr_ms_ / 1000);
    if (gop == 0) gop = cfg_.fps;
    GateResult g = law_six_gate(d3d_.device, nv12_, w_, h_, cfg_.fps, cfg_.bitrate, gop,
                                cfg_.codec, &enc_);
    if (!g.armed) { *err = g.reason; return false; }
    caps_ = g.caps;
    armed_codec_ = enc_.codec_name();
    return true;
}

// ------------------------------------------------------------------ arm
bool Replay::arm(const RunConfig& cfg, std::string* err)
{
    cfg_ = cfg;

    const ModeNumbers* m = mode_numbers(cfg_.mode);
    if (!m) { *err = "unknown mode '" + cfg_.mode + "' (gaming|desktop)"; return false; }
    if (cfg_.fps == 0)          cfg_.fps = m->fps;
    if (cfg_.idr_ms == 0)       cfg_.idr_ms = m->idr_ms;
    if (cfg_.ring_seconds == 0) cfg_.ring_seconds = m->ring_seconds;
    idr_ms_ = cfg_.idr_ms;

    uint32_t w = 0, h = 0;
    if (!build_target(&w, &h, err)) return false;
    w_ = w; h_ = h;

    if (!d3d_.create_on_vendor(0x10DE, err)) return false;

    // Bitrate scales with PIXELS, not with a fixed number (specs 01 §1).  Anchored on the
    // mode's own 1080p figure so the table is reproduced exactly at 1080p.
    if (cfg_.bitrate == 0) {
        double pixels = (double)w_ * (double)h_ * (double)cfg_.fps;
        double anchor = 1920.0 * 1080.0 * (double)m->fps;
        cfg_.bitrate = (uint32_t)((double)m->anchor_bitrate * pixels / anchor);
    }

    // --- ring budget (law 7): bytes from bitrate x seconds, CAPPED by the SYSTEM-RAM budget.
    uint64_t want = (uint64_t)((double)cfg_.bitrate / 8.0 * (double)cfg_.ring_seconds);
    // The cap is SYSTEM RAM (ring_buffer.h), not VRAM: the arena it bounds is a heap
    // vector, and d3d_.ring_cap_bytes() priced it from a pool the ring never draws from
    // — receipt-14 / receipt-16.
    uint64_t cap  = ring_budget_cap_bytes();
    uint64_t chose = want;
    uint32_t seconds_kept = cfg_.ring_seconds;
    if (cfg_.ring_bytes) {
        chose = cfg_.ring_bytes;
        seconds_kept = (uint32_t)((double)chose * 8.0 / (double)cfg_.bitrate);
    } else if (want > cap) {
        chose = cap;
        seconds_kept = (uint32_t)((double)cap * 8.0 / (double)cfg_.bitrate);
    }
    if (chose < (16u << 20)) chose = 16u << 20;

    // F6: the budget init() will APPLY is applied HERE, before anything is printed, so the
    // log cannot announce a size the arena does not hold.  --ring-mb 8192 used to print
    // "CHOSE 8192 MB" while init() clamped the arena to the cap and init()'s own log line
    // said a different number two lines later.  ring_cap_ is what init() receives, so the
    // clamp below is applied once, here, and init()'s internal clamp is the backstop.
    const uint64_t asked_bytes = chose;
    const RingBudget rbudget  = query_ring_budget();
    ring_cap_ = ring_apply_budget(chose, rbudget);
    seconds_kept = (uint32_t)((double)ring_cap_ * 8.0 / (double)cfg_.bitrate);

    log_line("  RING DECISION (law 7, said out loud): mode=%s fps=%u bitrate=%.1f Mbps idr_every=%u ms",
             cfg_.mode.c_str(), cfg_.fps, (double)cfg_.bitrate / 1e6, cfg_.idr_ms);
    log_line("    the mode's %u s would need %llu MB; the system-RAM budget caps at %llu MB; "
             "CHOSE %llu MB = %u s%s%s",
             cfg_.ring_seconds, (unsigned long long)(want >> 20), (unsigned long long)(cap >> 20),
             (unsigned long long)(ring_cap_ >> 20), seconds_kept,
             (asked_bytes > ring_cap_) ? "  [CLAMPED to the system-RAM budget]" : "",
             (want > cap && !cfg_.ring_bytes) ? "  [SHORTENED to fit the RAM budget]" : "");

    // --- the NV12 texture NVENC will ingest (created BEFORE the gate, because the gate
    //     must prove it registers AND maps).
    D3D11_TEXTURE2D_DESC td;
    memset(&td, 0, sizeof(td));
    td.Width = w_;
    td.Height = h_;
    td.MipLevels = 1;
    td.ArraySize = 1;
    td.Format = DXGI_FORMAT_NV12;
    td.SampleDesc.Count = 1;
    td.Usage = D3D11_USAGE_DEFAULT;
    td.BindFlags = D3D11_BIND_RENDER_TARGET;
    HRESULT hr = d3d_.device->CreateTexture2D(&td, nullptr, &nv12_);
    if (FAILED(hr) || !nv12_) { *err = "CreateTexture2D(NV12 " + std::to_string(w_) + "x" +
                                       std::to_string(h_) + ") failed " + hr_str(hr); return false; }
    log_line("  NV12 input texture: %ux%u DXGI_FORMAT_NV12, BIND_RENDER_TARGET (the zero-copy NVENC input)", w_, h_);

    // --- LAW 6 GATE.  Nothing below runs if this fails.
    if (!do_gate(err)) {
        stats_.rss_at_arm_bytes = process_rss_bytes();
        return false;
    }
    gate_passed_ = true;
    stats_.rss_at_arm_bytes = process_rss_bytes();

    if (!conv_.init(d3d_.device, err)) return false;
    if (!ring_.init((size_t)ring_cap_, err)) return false;

    if (cfg_.use_monitor) {
        POINT pt; pt.x = 0; pt.y = 0;
        HMONITOR mon = MonitorFromPoint(pt, MONITOR_DEFAULTTOPRIMARY);
        if (!cap_.start_for_monitor(d3d_.device, mon, err)) return false;
    } else {
        if (!cap_.start_for_window(d3d_.device, tw_.hwnd(), err)) return false;
    }

    capture_qpc_.reserve(1 << 18);
    next_idr_ns_ = 0;   // the very first frame is forced to be an IDR: the ring is cuttable from t=0

    cut_thread_ = std::thread(&Replay::cut_thread_main, this);
    return true;
}

// ------------------------------------------------------------------ cut
void Replay::issue_cut(uint64_t t_cut_ns)
{
    CutResult job;
    job.path = cfg_.out_path;
    job.cut_qpc_ns = t_cut_ns;

    size_t idx = 0;
    uint64_t window_ns = (uint64_t)cfg_.ring_seconds * 1000000000ull;
    if (!ring_.find_cut_base(t_cut_ns, window_ns, &idx)) {
        if (!ring_.find_oldest_idr(&idx)) {
            job.ok = false;
            job.note = "NO IDR IN THE RING - refusing to write a clip a decoder cannot start";
            stats_.cuts_refused++;
            std::lock_guard<std::mutex> lk(cut_mu_);
            last_cut_ = job;
            return;
        }
        job.note = "no IDR at or after (hotkey - ring_seconds): using the OLDEST IDR held "
                   "(the ring is shorter than the window; said, not hidden)";
    }

    RingEntry base;
    if (!ring_.entry_at(idx, &base)) {
        job.ok = false;
        job.note = "the ring lost the cut base between the search and the read";
        stats_.cuts_refused++;
        std::lock_guard<std::mutex> lk(cut_mu_);
        last_cut_ = job;
        return;
    }

    job.base_qpc_ns = base.qpc_ns;
    job.base_abs = base.abs_off;
    job.end_abs = ring_.newest_abs();
    job.bytes = 0;

    // The capture-side counts are computed HERE, on the thread that owns capture_qpc_,
    // so the cut thread never races the run loop for them.
    uint64_t captured = 0;
    for (uint64_t t : capture_qpc_) if (t >= base.qpc_ns && t <= t_cut_ns) ++captured;
    job.captured_in_window = captured;
    job.expected_in_window = (uint64_t)llround((double)(t_cut_ns - base.qpc_ns) * 1e-9 * cfg_.fps) + 1;
    job.idr_pre_roll_ms = (double)(t_cut_ns - base.qpc_ns) / 1e6;
    job.ring_dropped_at_cut = ring_.dropped();

    ring_.pin(base.abs_off);
    {
        std::lock_guard<std::mutex> lk(cut_mu_);
        cut_job_ = job;
        cut_job_.note = job.note;
        cut_has_job_ = true;
        cut_busy_ = true;
    }
    cut_cv_.notify_one();
}

bool Replay::wait_cut_done(uint32_t timeout_ms)
{
    std::unique_lock<std::mutex> lk(cut_mu_);
    return cut_done_cv_.wait_for(lk, std::chrono::milliseconds(timeout_ms), [&] { return !cut_busy_; });
}

bool Replay::perform_cut(CutResult& r)
{
    const uint64_t t0 = qpc_now_ns();

    RingEntry base;
    if (!ring_.entry_by_abs(r.base_abs, &base)) {
        r.note += " | the base IDR is no longer in the ring";
        return false;
    }

    // SPS/PPS come from the base IDR itself (repeatSPSPPS=1), so avcC describes exactly
    // the stream in the file.  The driver's sequence payload is the fallback.
    std::vector<uint8_t> au, sps, pps;
    if (!ring_.read_entry(base, au)) { r.note += " | could not read the base access unit"; return false; }
    extract_sps_pps(au.data(), au.size(), sps, pps);
    if (sps.empty() || pps.empty()) {
        std::vector<uint8_t> seq;
        std::string e;
        if (enc_.sequence_params(&seq, &e))
            extract_sps_pps(seq.data(), seq.size(), sps, pps);
    }
    if (sps.empty() || pps.empty()) {
        r.note += " | no SPS/PPS available: avcC cannot be built, refusing to write";
        return false;
    }

    Mp4Config mc;
    mc.width = w_;
    mc.height = h_;
    mc.sps = sps;
    mc.pps = pps;

    // ---- the clip's timebase is MEASURED, not declared --------------------------------
    // Every sample gets the same duration, and the media timescale is derived from the rate
    // the ring ACTUALLY ran at over this window.  Three measured reasons, and the third is
    // what makes this the only shape that is right on all three counts:
    //  1. A duration grid quantised to the mode's NOMINAL fps clamps the frame rate at that
    //     fps: the desktop arm's source ran at 54 fps against a declared 30 fps and the clip
    //     came out 1.8x SLOW MOTION (649 frames in a 21.6 s container for 12.0 s of real
    //     time).  A clip whose duration is not its duration is worse than a warning.
    //  2. A finer grid (1 ms) fixed the timing but reintroduced the reader problem below:
    //     MEASURED, `ffmpeg -v error -f null -` printed 2105 bytes of "non monotonically
    //     increasing dts" (first value 42 >= 42) while `-f rawvideo` and `-c copy` stayed
    //     clean — because a reader that derives a coarse output timebase from the frame
    //     durations (ffmpeg's null muxer does exactly that) rounded adjacent frames onto the
    //     same tick whenever the durations were not all multiples of their own minimum.
    //  3. Deriving the timescale from the measured rate makes every sample exactly 1 ms of
    //     container time (timescale/1000), so all pts are multiples of 1000 and the reader's
    //     timebase divides them exactly.  Total clip duration equals the real elapsed time to
    //     the millisecond, which is the property the other two shapes each lost.
    // CFR, not VFR, is also what a replay-buffer clip is expected to be (OBS, ShadowPlay).
    uint64_t span_ns = 0;
    uint64_t n_frames = 0;
    {
        RingEntry first, last;
        if (ring_.entry_by_abs(r.base_abs, &first)) {
            uint64_t a = r.base_abs;
            while (a < r.end_abs) {
                RingEntry e;
                if (!ring_.entry_by_abs(a, &e)) break;
                last = e;
                ++n_frames;
                a += e.size;
            }
            if (n_frames > 1 && last.qpc_ns > first.qpc_ns) span_ns = last.qpc_ns - first.qpc_ns;
        }
    }
    double fps_meas = (span_ns && n_frames > 1)
                          ? (double)(n_frames - 1) * 1e9 / (double)span_ns
                          : (double)cfg_.fps;
    uint32_t ts_meas = (uint32_t)(fps_meas * 1000.0 + 0.5);
    if (ts_meas < 1000)    ts_meas = 1000;         // 1 fps floor
    if (ts_meas > 1000000) ts_meas = 1000000;      // 1000 fps ceiling
    mc.timescale = ts_meas;
    mc.fps_num = ts_meas;
    mc.fps_den = 1000;
    const uint64_t dur = 1000;                     // 1 ms per sample, exactly
    log_line("  CLIP TIMEBASE: measured %.3f fps over %llu frames -> timescale=%u, every sample "
             "%llu ticks = %.4f ms (clip duration %.3f s vs real %.3f s)",
             fps_meas, (unsigned long long)n_frames, ts_meas, (unsigned long long)dur,
             (double)dur * 1000.0 / (double)ts_meas, (double)n_frames * (double)dur / (double)ts_meas,
             (double)span_ns / 1e9);

    // The muxer is opened AFTER the timebase is known (the header carries it).
    Mp4Writer mw;
    std::string err;
    if (!mw.open(r.path, mc, &err)) { r.note += " | mp4 open: " + err; return false; }

    uint64_t abs = r.base_abs;
    uint64_t samples = 0, encoded = 0;
    while (abs < r.end_abs) {
        RingEntry e;
        if (!ring_.entry_by_abs(abs, &e)) break;
        ++encoded;
        if (!ring_.read_entry(e, au)) break;
        std::vector<uint8_t> avcc;
        annexb_to_avcc(au.data(), au.size(), avcc);
        if (avcc.empty()) { r.note += " | an access unit had no NAL units"; break; }

        if (!mw.write_sample(avcc.data(), avcc.size(), e.is_idr, dur, &err)) {
            r.note += " | mp4 write_sample: " + err;
            break;
        }
        abs += e.size;
        ++samples;
    }

    if (!mw.close(&err)) { r.note += " | mp4 close: " + err; return false; }

    r.frames_in_clip = samples;
    r.encoded_in_window = encoded;
    r.bytes = mw.bytes_written();
    r.clip_seconds = (double)(r.cut_qpc_ns - r.base_qpc_ns) / 1e9;
    r.wall_ms = (double)(qpc_now_ns() - t0) / 1e6;
    r.ok = (samples > 0);
    return r.ok;
}

// ------------------------------------------------------------------ offline cut
bool Replay::cut_from_h264(const std::string& h264_path, const std::string& out_path,
                           uint32_t fps, uint32_t w, uint32_t h, std::string* err)
{
    FILE* f = nullptr;
    if (fopen_s(&f, h264_path.c_str(), "rb") != 0 || !f) { *err = "cannot open " + h264_path; return false; }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    std::vector<uint8_t> raw((size_t)(n > 0 ? n : 0));
    size_t got = raw.empty() ? 0 : fread(raw.data(), 1, raw.size(), f);
    fclose(f);
    raw.resize(got);
    if (raw.empty()) { *err = "empty elementary stream"; return false; }

    std::vector<NalSpan> nals;
    annexb_split(raw.data(), raw.size(), nals);
    if (nals.empty()) { *err = "no NAL units found"; return false; }

    // Group NALs into access units.  A VCL NAL (type 1 or 5) starts a new AU, and a
    // parameter set / AUD that arrives AFTER a VCL NAL starts one too.  Non-VCL NALs
    // otherwise attach to the AU they precede, which is what a decoder expects.
    std::vector<std::vector<uint8_t>> aus;
    std::vector<bool> au_idr;
    std::vector<uint8_t> cur;
    bool cur_has_vcl = false, cur_is_idr = false;
    auto flush = [&]() {
        if (!cur.empty()) { aus.push_back(cur); au_idr.push_back(cur_is_idr); }
        cur.clear();
        cur_has_vcl = false;
        cur_is_idr = false;
    };
    for (const NalSpan& ns : nals) {
        const bool vcl = (ns.type == 1 || ns.type == 5);
        const bool ps  = (ns.type == 7 || ns.type == 8 || ns.type == 9);
        if ((vcl && cur_has_vcl) || (ps && cur_has_vcl)) flush();
        static const uint8_t sc[4] = { 0, 0, 0, 1 };
        cur.insert(cur.end(), sc, sc + 4);
        cur.insert(cur.end(), ns.data, ns.data + ns.size);
        if (vcl) { cur_has_vcl = true; if (ns.type == 5) cur_is_idr = true; }
    }
    flush();
    if (aus.size() < 2) { *err = "the stream has fewer than two access units"; return false; }

    uint64_t need = 0;
    for (const std::vector<uint8_t>& a : aus) need += a.size() + 4096;
    if (!ring_.init((size_t)need, err)) return false;
    w_ = w;
    h_ = h;
    window_decision_ = WindowDecision();
    window_decision_.w = w;
    window_decision_.h = h;
    window_decision_.source = WindowDecision::Source::RequestedAsIs;
    window_decision_.note = "OFFLINE CUT: the size is DECLARED by --cut-size and describes the "
                            "elementary stream; no output desktop is involved";
    cfg_.fps = fps;

    const uint64_t step_ns = 1000000000ull / (fps ? fps : 60);
    uint64_t t = 0;
    for (size_t i = 0; i < aus.size(); ++i) {
        if (!ring_.append(aus[i].data(), aus[i].size(), au_idr[i], au_idr[i] ? 1 : 0, t, i)) {
            *err = "the ring could not hold the whole stream";
            return false;
        }
        t += step_ns;
    }

    // Base = the first IDR; end = one past the newest byte.  This is exactly the range a
    // live cut would pin, so perform_cut() runs unmodified.
    size_t first_idr = 0;
    if (!ring_.find_oldest_idr(&first_idr)) { *err = "no IDR in the stream"; return false; }
    RingEntry base_e, last_e;
    if (!ring_.entry_at(first_idr, &base_e)) { *err = "base entry missing"; return false; }
    if (!ring_.entry_at(ring_.count() - 1, &last_e)) { *err = "last entry missing"; return false; }

    CutResult r;
    r.path = out_path;
    r.base_abs = base_e.abs_off;
    r.end_abs = last_e.abs_off + last_e.size;
    r.base_qpc_ns = base_e.qpc_ns;
    r.cut_qpc_ns = last_e.qpc_ns;
    r.captured_in_window = aus.size();
    r.encoded_in_window = aus.size();
    ring_.pin(r.base_abs);
    const bool ok = perform_cut(r);
    ring_.unpin();
    last_cut_ = r;
    log_line("  OFFLINE CUT: %s -> %s  aus=%zu  idr=%s  frames_in_clip=%llu  bytes=%llu  wall_ms=%.1f  note=%s",
             h264_path.c_str(), out_path.c_str(), aus.size(), first_idr ? "not-first" : "first",
             (unsigned long long)r.frames_in_clip, (unsigned long long)r.bytes, r.wall_ms,
             r.note.empty() ? "(none)" : r.note.c_str());
    if (!ok) { *err = "perform_cut failed: " + r.note; return false; }
    return true;
}

void Replay::cut_thread_main(){
    for (;;) {
        CutResult job;
        {
            std::unique_lock<std::mutex> lk(cut_mu_);
            cut_cv_.wait(lk, [&] { return cut_quit_ || cut_has_job_; });
            if (cut_quit_ && !cut_has_job_) return;
            job = cut_job_;
            cut_has_job_ = false;
        }
        CutResult res = job;
        bool ok = perform_cut(res);
        res.ok = ok;
        ring_.unpin();
        if (ok) stats_.cuts_written.fetch_add(1);
        else    stats_.cuts_refused.fetch_add(1);
        {
            std::lock_guard<std::mutex> lk(cut_mu_);
            last_cut_ = res;
            cut_busy_ = false;
        }
        cut_done_cv_.notify_all();
    }
}

// ------------------------------------------------------------------ run
bool Replay::run(std::string* err)
{
    const uint64_t t_start = qpc_now_ns();
    const uint64_t run_ns = (uint64_t)cfg_.run_seconds * 1000000000ull;
    const uint64_t cut_ns = (uint64_t)(cfg_.cut_at_s * 1e9);
    bool cut_issued = false;
    uint64_t last_rss = 0;
    uint64_t encode_fail_logged = 0;

    log_line("  RUN: %u s of capture, cut signalled at %.2f s", cfg_.run_seconds, cfg_.cut_at_s);

    for (;;) {
        const uint64_t now = qpc_now_ns();
        const uint64_t elapsed = now - t_start;
        if (elapsed >= run_ns) break;

        // ---- a resolution change WHILE RUNNING ------------------------------------------------
        // The NVENC session, the NV12 texture and the ring are all sized at arm time, so a
        // desktop that changes size mid-run cannot be absorbed by copying frames of the new
        // size into a stream declared as the old one.  The honest handling is to stop and say
        // so, naming BOTH sizes — a clip whose container says 1920x1080 while the source is
        // 3840x2160 is a silent lie, and this repo's rule is that a failure must never answer
        // as success.
        if (tw_.display_changed()) {
            display_changes_ = tw_.display_changes();
            log_line("  STOP: the OUTPUT DESKTOP CHANGED mid-run (%ux%u -> %ux%u, %u change(s)); "
                     "the encoder was armed at %ux%u and cannot be re-sized in place. Refusing "
                     "rather than writing a clip whose header contradicts its pixels.",
                     window_decision_.w, window_decision_.h, tw_.desktop_w(), tw_.desktop_h(),
                     display_changes_, w_, h_);
            *err = "the output desktop resolution changed during the run (" +
                   std::to_string(window_decision_.w) + "x" + std::to_string(window_decision_.h) +
                   " -> " + std::to_string(tw_.desktop_w()) + "x" + std::to_string(tw_.desktop_h()) +
                   "); the armed encoder is sized for the old one";
            return false;
        }

        CapturedFrame f;
        std::string e2;
        if (!cap_.try_get_frame(&f, &e2)) {
            if (!e2.empty()) { *err = "capture failed: " + e2; return false; }
            stats_.frame_pool_empty_polls.fetch_add(1);
            micro_wait_ms(1);
            continue;
        }
        stats_.frames_captured.fetch_add(1);
        capture_qpc_.push_back(f.qpc_ns);

        const uint64_t c0 = qpc_now_ns();
        std::string ce;
        if (!conv_.convert(d3d_.device, d3d_.ctx, cap_.last_srv(), nv12_, w_, h_, &ce)) {
            f.texture->Release();
            *err = "BGRA->NV12 conversion failed: " + ce;
            return false;
        }
        stats_.convert_ns.fetch_add(qpc_now_ns() - c0);
        stats_.frames_converted.fetch_add(1);

        const bool force = (f.qpc_ns >= next_idr_ns_);
        const uint64_t e0 = qpc_now_ns();
        std::string ee;
        if (!enc_.encode(force, f.qpc_ns / 100, &ee)) {
            stats_.frames_encode_failed.fetch_add(1);
            if (encode_fail_logged < 3) {
                log_line("  WARN encode failed (frame %llu): %s",
                         (unsigned long long)stats_.frames_captured.load(), ee.c_str());
                ++encode_fail_logged;
            }
            f.texture->Release();
            continue;
        }
        stats_.encode_ns.fetch_add(qpc_now_ns() - e0);
        stats_.frames_encoded.fetch_add(1);
        if (force) stats_.idr_forced.fetch_add(1);
        if (enc_.last_was_idr()) {
            stats_.idr_observed.fetch_add(1);
            next_idr_ns_ = f.qpc_ns + (uint64_t)idr_ms_ * 1000000ull;
        }

        const std::vector<uint8_t>& bs = enc_.bitstream();
        if (!ring_.append(bs.data(), bs.size(), enc_.last_was_idr(), enc_.last_picture_type(),
                          f.qpc_ns, seq_++)) {
            stats_.frames_ring_dropped.fetch_add(1);
        }

        f.texture->Release();

        if (now - last_rss > 200000000ull) {
            uint64_t r = process_rss_bytes();
            uint64_t cur = stats_.peak_rss_bytes.load();
            if (r > cur) stats_.peak_rss_bytes.store(r);
            last_rss = now;
        }

        if (!cut_issued && elapsed >= cut_ns) {
            issue_cut(f.qpc_ns);
            cut_issued = true;
        }
    }

    stats_.wall_ns.store(qpc_now_ns() - t_start);
    {
        uint64_t r = process_rss_bytes();
        uint64_t cur = stats_.peak_rss_bytes.load();
        if (r > cur) stats_.peak_rss_bytes.store(r);
    }
    uint64_t u = 0, k = 0;
    process_cpu_100ns(&u, &k);
    stats_.cpu_user_100ns.store(u);
    stats_.cpu_kernel_100ns.store(k);

    if (cut_issued) {
        if (!wait_cut_done(20000)) log_line("  WARN the cut thread did not finish within 20 s");
    } else {
        log_line("  NOTE: no cut was signalled in this run");
    }
    return true;
}

void Replay::shutdown()
{
    {
        std::lock_guard<std::mutex> lk(cut_mu_);
        cut_quit_ = true;
    }
    cut_cv_.notify_all();
    if (cut_thread_.joinable()) cut_thread_.join();

    cap_.release();
    enc_.close();
    conv_.release();
    if (nv12_) { nv12_->Release(); nv12_ = nullptr; }
    tw_.stop();
    d3d_.release();
}

} // namespace aireplay
