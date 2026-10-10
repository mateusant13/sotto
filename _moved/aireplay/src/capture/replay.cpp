#include "replay.h"

#include "selftest.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <ctime>

// The ASR contract: 16 kHz MONO PCM16.  This file converts from it; it never negotiates it.
#include "audio_contract.h"

// Windows Media Foundation — the AAC route.  AacEncoder (below) carries the measured recipe and
// the three details that are easy to get wrong; these headers are all it needs.
#include <mfapi.h>
#include <mferror.h>
#include <mfidl.h>
#include <mftransform.h>

namespace aireplay {

// ------------------------------------------------------------------ epoch / clip identity
//
// A QPC reading is not a time of day and never will be.  The offset between the two is SAMPLED
// once per process — one (FILETIME, QPC) pair, read together — and exposed so the receipt can
// quote what was actually read on this host rather than a claim about how Windows works.
//
// TWO CONSTANTS THIS FUNCTION GOT WRONG THE FIRST TIME, recorded because both produced a
// plausible-looking number rather than an obviously broken one:
//   1. FILETIME counts 100 ns intervals from 1601-01-01, NOT from 1970.  Comparing it with QPC
//      and calling the difference "epoch" yields year 23951 — which is what the first build of
//      this function produced (`clip_id=23951008T005111Z-000`).
//   2. QPC ticks are not nanoseconds, and `q.QuadPart * 1'000'000'000` OVERFLOWS uint64 after
//      ~6 days of uptime.  The multiply is done in 128 bits for that reason.
//
// 11644473600 s is the measured-by-definition gap between the FILETIME epoch and the Unix epoch
// (the number of seconds in the 369 years between them), so it is a CONSTANT here, not a guess.
static const uint64_t kFileTimeEpochOffsetNs = 11644473600ull * 1000000000ull;

uint64_t qpc_epoch_offset_ns()
{
    static uint64_t cached = 0;
    static bool     have   = false;
    if (!have) {
        LARGE_INTEGER freq, q;
        FILETIME ft;
        QueryPerformanceFrequency(&freq);
        QueryPerformanceCounter(&q);
        GetSystemTimeAsFileTime(&ft);
        const uint64_t ft_ns = (((uint64_t)ft.dwHighDateTime << 32) | ft.dwLowDateTime) * 100ull;
        const uint64_t q_ns  = (freq.QuadPart > 0)
                                 ? (uint64_t)((unsigned __int128)q.QuadPart * 1000000000ull
                                              / (unsigned __int128)freq.QuadPart)
                                 : 0;
        const uint64_t wall_ns = ft_ns > kFileTimeEpochOffsetNs
                                   ? ft_ns - kFileTimeEpochOffsetNs : 0;   // Unix epoch ns
        cached = wall_ns > q_ns ? wall_ns - q_ns : 0;
        have = true;
    }
    return cached;
}

double qpc_to_epoch_seconds(uint64_t qpc_ns)
{
    return (double)(qpc_ns + qpc_epoch_offset_ns()) / 1e9;
}

// The clip id, minted to the contract src\storage\layout.py already imposes — NOT to a second
// format invented here.  Two things that file fixes and that a naive mint gets wrong, both of
// which this lane's own gate caught on its first run (the ids it printed were `-000` and stamped
// with the CUT time, and `parse_clip_id` rejects the first and mis-files the second):
//   * CLIP_ID_RE is ^(\d{8})T(\d{6})Z-(\d{4,})$ — the sequence is FOUR digits minimum.
//   * make_clip_id(started_at_s, seq) stamps the WINDOW START.  parse_clip_id() gives that start
//     back out of the id, so a cut-time stamp would make the round-trip lie by the length of the
//     clip.  The caller passes the base frame's epoch for exactly that reason.
std::string mint_clip_id(double started_at_s, uint64_t seq)
{
    time_t t = (time_t)(started_at_s > 0 ? (int64_t)started_at_s : 0);
    struct tm g;
    gmtime_s(&g, &t);
    char buf[32];
    snprintf(buf, sizeof(buf), "%04d%02d%02dT%02d%02d%02dZ", g.tm_year + 1900, g.tm_mon + 1,
             g.tm_mday, g.tm_hour, g.tm_min, g.tm_sec);
    char seqbuf[24];
    snprintf(seqbuf, sizeof(seqbuf), "%04llu", (unsigned long long)seq);   // 4 digits minimum
    return std::string(buf) + "-" + seqbuf;
}

// ------------------------------------------------------------------ THE RETROACTIVE WINDOW
//
// [T-N, T].  Three failures are named rather than absorbed, because each of them is the one that
// makes an instant-replay product feel broken: no frames at all, no keyframe to start from, and —
// the one this lane exists for — a ring that holds LESS than N seconds.  The third sets
// `truncated` and fills `note`; the caller cannot miss it unless it chooses not to look.
bool plan_retroactive_window(const RingBuffer& ring, uint64_t t_cut_ns, double requested_s,
                             WindowPlan* out)
{
    WindowPlan p;
    p.cut_qpc_ns  = t_cut_ns;
    p.requested_s = requested_s > 0 ? requested_s : 0.0;

    const size_t n = ring.count();
    if (n == 0) {
        p.ring_empty = true;
        p.note = "the ring holds NO frames: there is nothing to cut";
        if (out) *out = p;
        return false;
    }

    RingEntry newest, oldest;
    if (!ring.entry_at(n - 1, &newest)) {
        p.note = "the ring would not name its newest entry";
        if (out) *out = p;
        return false;
    }
    if (!ring.entry_at(0, &oldest)) oldest = newest;
    p.base_abs = oldest.abs_off;
    p.end_abs  = newest.abs_off + newest.size;

    // MEASURED, and measured to the CUT, not to "now": a ring whose newest frame is older than
    // the press is a lagging capture, and comparing the window against the wall clock would
    // report a 30 s window as satisfied when the ring only ever held 2 s of it.
    const double oldest_s = (double)oldest.qpc_ns / 1e9;
    const double t_cut_s  = (double)t_cut_ns  / 1e9;
    p.ring_span_s = (t_cut_s > oldest_s) ? (t_cut_s - oldest_s) : 0.0;
    if (p.requested_s > 0.0 && p.requested_s > p.ring_span_s) {
        p.truncated  = true;
        p.shortfall_s = p.requested_s - p.ring_span_s;
    }

    size_t idx = 0;
    const uint64_t window_ns = (uint64_t)(p.requested_s * 1e9);
    if (p.requested_s > 0.0 && ring.find_cut_base(t_cut_ns, window_ns, &idx)) {
        // The requested window is fully inside the ring: the first IDR at or after (T-N).
    } else if (!ring.find_oldest_idr(&idx)) {
        p.no_idr = true;
        p.note = "NO IDR IN THE RING - refusing to write a clip a decoder cannot start";
        if (out) *out = p;
        return false;
    }

    // THE TRUNCATION REPORT — stated HERE, unconditionally, and that placement is the fix for a
    // defect this lane's own gate caught on its first run: the note used to be written only on the
    // `find_cut_base`-failed branch, so a 330 s window over a 30 s ring FOUND an IDR, returned
    // ok, and said NOTHING (`delivered=29983ms`, note empty).  A caller reading only the note got
    // a silent short clip — the exact failure the arm exists to forbid.  The measured numbers go
    // in whenever the ring cannot cover the request, whichever base was chosen.
    if (p.truncated) {
        p.note = "TRUNCATED: asked for " +
                 std::to_string((long long)(p.requested_s * 1000.0)) +
                 " ms, the ring holds only " +
                 std::to_string((long long)(p.ring_span_s * 1000.0)) +
                 " ms, so the clip starts " +
                 std::to_string((long long)(p.shortfall_s * 1000.0)) +
                 " ms late (at the oldest keyframe it still has)";
    }

    RingEntry base;
    if (!ring.entry_at(idx, &base)) {
        p.note = "the ring lost the cut base between the search and the read";
        if (out) *out = p;
        return false;
    }
    p.base_index  = idx;
    p.base_abs    = base.abs_off;
    p.base_qpc_ns = base.qpc_ns;
    // WHAT THE CLIP WILL CONTAIN, not (cut - base).  A press whose timestamp is later than the
    // ring's newest frame — a lagging capture, or a hotkey fired against an offline-seeded ring —
    // would otherwise "deliver" a window longer than any frame the muxer can write.
    p.delivered_s = (newest.qpc_ns > base.qpc_ns)
                      ? (double)(newest.qpc_ns - base.qpc_ns) / 1e9
                      : 0.0;
    p.ok = true;
    if (out) *out = p;
    return true;
}

// ------------------------------------------------------------------ offline ring seeding
//
// Factored out of cut_from_h264 so the gate seeds the ring through the SAME loader the offline
// cut uses.  A gate that seeds the ring by another route is testing a ring nobody ships.
size_t ring_seed_from_h264(RingBuffer* ring, const std::string& h264_path, uint32_t fps,
                           std::vector<bool>* au_idr_out, std::string* err)
{
    std::string e;
    FILE* f = nullptr;
    if (fopen_s(&f, h264_path.c_str(), "rb") != 0 || !f) {
        if (err) *err = "cannot open " + h264_path;
        return 0;
    }
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    std::vector<uint8_t> raw((size_t)(n > 0 ? n : 0));
    size_t got = raw.empty() ? 0 : fread(raw.data(), 1, raw.size(), f);
    fclose(f);
    raw.resize(got);
    if (raw.empty()) { if (err) *err = "empty elementary stream"; return 0; }

    std::vector<NalSpan> nals;
    annexb_split(raw.data(), raw.size(), nals);
    if (nals.empty()) { if (err) *err = "no NAL units found"; return 0; }

    // Group NALs into access units.  A VCL NAL (type 1 or 5) starts a new AU, and a parameter set
    // / AUD that arrives AFTER a VCL NAL starts one too.  Non-VCL NALs otherwise attach to the AU
    // they precede, which is what a decoder expects.
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
    if (aus.size() < 2) { if (err) *err = "the stream has fewer than two access units"; return 0; }

    const uint64_t step_ns = 1000000000ull / (fps ? fps : 60);
    uint64_t t = 0;
    size_t appended = 0;
    for (size_t i = 0; i < aus.size(); ++i) {
        if (!ring->append(aus[i].data(), aus[i].size(), au_idr[i], au_idr[i] ? 1 : 0, t, i)) {
            if (err) *err = "the ring could not hold the whole stream (appended " +
                            std::to_string(appended) + " of " + std::to_string(aus.size()) + " AUs)";
            if (au_idr_out) *au_idr_out = au_idr;
            return appended;
        }
        t += step_ns;
        ++appended;
    }
    if (au_idr_out) *au_idr_out = au_idr;
    (void)e;
    return appended;
}

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

    // THE HOTKEY, only when the run asked for it.  Registered AFTER the ring and the cut thread
    // exist, because a press that arrives before either is a press with nowhere to go.
    if (cfg_.hotkey) {
        std::string kerr;
        if (!arm_hotkey({}, cfg_.hotkey_window_s, &kerr))
            log_line("  WARN the instant-replay hotkey did NOT arm (%s); the timer cut still runs",
                     kerr.c_str());
    }

    cut_thread_ = std::thread(&Replay::cut_thread_main, this);
    return true;
}

// ------------------------------------------------------------------ cut
//
// The TIMER cut, kept exactly as it was: one cut at cfg_.cut_at_s over the whole ring.  The
// hotkey does NOT come through here — it goes through request_cut(), which is the same code with
// a window the key chose.
void Replay::issue_cut(uint64_t t_cut_ns)
{
    request_cut(t_cut_ns, (double)cfg_.ring_seconds, "timer");
}

// The retroactive cut itself.  `requested_window_s` is what the key asked for; the ring decides
// what it can give, and the difference is carried out in the result rather than swallowed here.
bool Replay::plan_job(uint64_t t_cut_ns, double requested_window_s, const std::string& origin,
                      CutResult& job, WindowPlan& plan)
{
    job.origin = origin;
    if (!(requested_window_s > 0)) requested_window_s = (double)cfg_.ring_seconds;

    if (!plan_retroactive_window(ring_, t_cut_ns, requested_window_s, &plan)) {
        job.ok = false;
        job.state = "refused";
        job.note = plan.note;
        job.cut_qpc_ns = t_cut_ns;
        job.requested_window_s = requested_window_s;
        job.delivered_window_s = 0;
        job.window_truncated = plan.truncated;
        job.shortfall_s = plan.shortfall_s;
        stats_.cuts_refused++;
        {
            std::lock_guard<std::mutex> lk(cut_mu_);
            last_cut_ = job;
        }
        log_line("  CUT REFUSED (%s): %s", origin.c_str(), job.note.c_str());
        return false;
    }

    // IDENTITY.  Minted HERE, on the capture side, because the index store refuses to invent one
    // ("clip payload has no clip_id; refusing to invent one") — receipts\receipt-34 §IDENTITY
    // carries the field-by-field mapping and the consumer lines.
    const double base_epoch = qpc_to_epoch_seconds(plan.base_qpc_ns);
    job.clip_id      = mint_clip_id(base_epoch, clip_seq_++);   // stamped with the WINDOW START
    job.started_at_s = base_epoch;          // the WINDOW START, which is what a time filter wants
    job.state        = "cutting";
    job.cut_qpc_ns   = t_cut_ns;
    job.base_qpc_ns  = plan.base_qpc_ns;
    job.base_abs     = plan.base_abs;
    job.end_abs      = plan.end_abs;
    job.requested_window_s = plan.requested_s;
    job.delivered_window_s = plan.delivered_s;
    job.window_truncated   = plan.truncated;
    job.shortfall_s        = plan.shortfall_s;
    job.note               = plan.note;
    job.ring_dropped_at_cut = ring_.dropped();

    // ONE FILE PER CLIP when a directory was configured.  Two presses writing cfg_.out_path means
    // the second hotkey overwrites the clip the owner just saved, which is not instant replay,
    // it is instant replacement.  The shape is <out_dir>/<clip_id>/clip.mp4 — the INNER shape of
    // storage.layout.clip_dir(), with MEDIA_NAME as the file name, so the store adds only the
    // dated prefix.  Deliberately NOT a second naming scheme of our own.
    if (!cfg_.out_dir.empty()) {
        const std::string dir = cfg_.out_dir + "\\" + job.clip_id;
        CreateDirectoryA(dir.c_str(), nullptr);        // no-op when it already exists
        job.path = dir + "\\clip.mp4";
    }

    log_line("  CUT REQUESTED (%s) clip_id=%s window asked=%.3f s ring holds=%.3f s delivered=%.3f s%s",
             origin.c_str(), job.clip_id.c_str(), job.requested_window_s, plan.ring_span_s,
             job.delivered_window_s, plan.truncated ? "  [TRUNCATED]" : "");
    if (plan.truncated)
        log_line("    %s", plan.note.c_str());

    return true;
}

void Replay::request_cut(uint64_t t_cut_ns, double requested_window_s, const std::string& origin)
{
    CutResult job;
    job.path = cfg_.out_path;
    WindowPlan plan;
    if (!plan_job(t_cut_ns, requested_window_s, origin, job, plan)) return;

    // The capture-side counts are computed HERE, on the thread that owns capture_qpc_, so the cut
    // thread never races the run loop for them.
    uint64_t captured = 0;
    for (uint64_t t : capture_qpc_) if (t >= job.base_qpc_ns && t <= t_cut_ns) ++captured;
    job.captured_in_window = captured;
    job.expected_in_window = (uint64_t)llround((double)(t_cut_ns - job.base_qpc_ns) * 1e-9
                                               * cfg_.fps) + 1;
    job.idr_pre_roll_ms = (double)(t_cut_ns - job.base_qpc_ns) / 1e6;
    job.bytes = 0;

    ring_.pin(job.base_abs);
    {
        std::lock_guard<std::mutex> lk(cut_mu_);
        // A press that arrives while another clip is being written is REFUSED and COUNTED, never
        // queued silently: the owner's second hotkey has to be visible as something.
        if (cut_busy_) {
            ++hotkey_dropped_;
            log_line("  CUT REFUSED (%s): a clip is already being written; this press is DROPPED "
                     "and counted (hotkey_dropped=%llu)", origin.c_str(),
                     (unsigned long long)hotkey_dropped_);
            return;
        }
        cut_job_     = job;
        cut_plan_    = plan;
        cut_has_job_ = true;
        cut_busy_    = true;
    }
    cut_cv_.notify_one();
}

// ------------------------------------------------------------------ the hotkey
bool Replay::arm_hotkey(const std::vector<HotkeyBinding>& bindings, double window_s,
                        std::string* err)
{
    std::string e;
    trigger_.reset(new Trigger());
    trigger_->set_ring_probe(this);          // the trigger ASKS the ring how much history it holds
    const bool ok = trigger_->arm(bindings.empty() ? default_binding_ladder() : bindings,
                                  window_s, &e);
    if (!ok) {
        if (err) *err = e;
        trigger_.reset();
        return false;
    }
    log_line("  %s", trigger_->arm_summary().c_str());
    return true;
}

void Replay::disarm_hotkey()
{
    if (!trigger_) return;
    trigger_->set_ring_probe(nullptr);       // the probe is `this`; do not outlive the pointer
    trigger_->disarm();
    trigger_.reset();
}

uint64_t Replay::hotkey_requests_dropped() const { return hotkey_dropped_; }

double Replay::span_seconds()
{
    const size_t n = ring_.count();
    if (n == 0) return 0.0;
    RingEntry a, b;
    if (!ring_.entry_at(0, &a) || !ring_.entry_at(n - 1, &b)) return -1.0;
    if (b.qpc_ns <= a.qpc_ns) return 0.0;
    return (double)(b.qpc_ns - a.qpc_ns) / 1e9;
}

void Replay::drain_hotkey()
{
    if (!trigger_) return;
    CutRequest req;
    while (trigger_->take(&req, 0)) {
        const uint64_t t = req.t_cut_ns ? req.t_cut_ns : qpc_now_ns();
        request_cut(t, req.requested_window_s,
                    std::string("hotkey:") + (req.binding.name ? req.binding.name : "?"));
        ++hotkey_cuts_;
    }
}
bool Replay::wait_cut_done(uint32_t timeout_ms)
{
    std::unique_lock<std::mutex> lk(cut_mu_);
    return cut_done_cv_.wait_for(lk, std::chrono::milliseconds(timeout_ms), [&] { return !cut_busy_; });
}

bool Replay::perform_cut(CutResult& r, const WindowPlan* plan)
{
    const bool ok = perform_cut_body(r, plan);
    r.ok = ok;
    r.state = ok ? "recorded" : "failed";
    if (clip_sink_) clip_sink_->on_clip_done(r);
    return ok;
}

// THE 'cutting' ANCHOR — the only producer of the literal the §2.5 ladder scans for.  Fired from
// inside perform_cut_body() IMMEDIATELY BEFORE Mp4Writer::open(), i.e. while the output file does
// not exist yet: a row written here precedes the bytes, so a crash can orphan a ROW (which the
// ladder finds and repairs) and never a FILE (which nothing would ever find).
void Replay::fire_anchor(const CutResult& r, const WindowPlan& p, double fps_measured)
{
    if (!clip_sink_) return;
    ClipAnchor a;
    a.clip_id = r.clip_id;
    a.path = r.path;
    a.state = "cutting";
    a.started_at_s = r.started_at_s;
    a.requested_window_s = r.requested_window_s;
    a.delivered_window_s = r.delivered_window_s;
    a.window_truncated = r.window_truncated;
    a.shortfall_s = r.shortfall_s;
    a.base_abs = r.base_abs;
    a.end_abs = r.end_abs;
    a.base_qpc_ns = r.base_qpc_ns;
    a.cut_qpc_ns = r.cut_qpc_ns;
    a.width = w_;
    a.height = h_;
    a.fps_measured = fps_measured;
    (void)p;
    clip_sink_->on_clip_anchor(a);
}

// ------------------------------------------------------------------ AAC, route 1
//
// WHY AN ENCODER LIVES IN THIS TRANSLATION UNIT
// -----------------------------------------------
// audio_tap.cpp is #included by main.cpp, so its symbols exist in NO other translation unit, and
// this file is compiled on its own.  An encoder defined in audio_tap.cpp could not be called from
// the cut thread, which is the only thread that needs it.  It therefore lives HERE, beside its one
// caller: no new production file, and no new source in build.cmd.
//
// THE RECIPE IS PORTED, NOT INVENTED.  It is the winning arm (A1) of the measured probe
// _main/_audio-mft-probe.cpp, which printed
//     BATTERY: WINNING ARM A1 with 683 bytes
//     VERDICT: GREEN - a real AAC encoder exists on this box and produced bytes from a 440 Hz tone.
// Three details in that recipe are why it works, and each was paid for inside that same battery:
//   1. SetOutputType BEFORE SetInputType;
//   2. a FRESH IMFSample + IMFMediaBuffer for EVERY ProcessOutput -- the first run of the battery
//      returned E_INVALIDARG from all eight arms while a single buffer was reused;
//   3. the output bytes are read out of od.pSample BEFORE the caller sample is released and
//      od.pEvents is then released -- releasing the events first was a 0xC0000005 crash there.
//
// THE RATE CONVERSION IS EXACT, NOT A RESAMPLE.  The ring carries the contract of 16 kHz MONO
// PCM16 (audio_contract.h) and the encoder is handed 48 kHz STEREO, because the AAC MFT REFUSES
// 16 kHz mono at SetInputType (measured in that probe: hr=0xC00D36B4 MF_E_INVALIDMEDIATYPE, and
// the winning input type ri is 48 k / 2 ch / 16-bit).  48 kHz is exactly 3 x 16 kHz, so each mono
// frame becomes THREE stereo frames, every one of them carrying that value on both channels.  No
// interpolation, no filter, no resampler error, and NO change of speed or pitch: the repetition
// count is the entire conversion, and it is what makes the trak as long as the picture.  Written
// down so nobody has to take it on faith, and so the next reader can re-check the 3 against the
// constants.
//
// THE OUTPUT IS RAW AAC WITH NO ADTS SYNC, which is what an mp4 trak wants: the ASC rides in the
// esds box the muxer already builds.  A frame that arrived WITH a sync word would put garbage in
// the clip, so that case is counted and reported, not ignored.
class AacEncoder {
public:
    // 48 kHz in AAC frames is the encoder domain; 16 kHz mono frames is the contract domain.
    static const UINT32 kRate48      = 48000;
    static const UINT32 kBlock       = 1024;    // AAC frames per block
    static const UINT32 kOutBufBytes = 16000;   // arm A1 measured 683 bytes per block

    // AAC AudioSpecificConfig for AOT=2 (LC), 48000 Hz, stereo: samplingFrequencyIndex 3
    // (96000) in the top 4 bits, channelConfiguration 2 in the bottom 4, one pad bit.
    static void audio_specific_config(std::vector<uint8_t>* asc)
    {
        asc->clear();
        asc->push_back(0x11);
        asc->push_back(0x90);
    }

    AacEncoder() {}

    ~AacEncoder() { close(); }

    bool is_open() const { return mft_ != nullptr; }

    // NUMBERS, not adjectives: contract frames in, the exact number of them that were silence
    // padding the final block, raw AAC frames out, the rare ADTS case, the byte total, and the
    // one-line reason this route did or did not ship.  The receipt quotes all of them.
    uint32_t mono_frames_in() const { return mono_frames_in_; }
    uint32_t mono_pad_frames() const { return mono_pad_frames_; }
    uint32_t aac_frames() const { return aac_frames_; }
    uint32_t adts_frames() const { return adts_frames_; }
    uint64_t out_bytes() const { return out_bytes_; }
    const std::string& last_error() const { return last_err_; }

    // WHY NOT AAC, in one line, for the run log and the receipt.  Empty on success.
    bool open(std::string* why_not)
    {
        if (mft_) return true;
        auto rel = [](IUnknown* p) { if (p) p->Release(); };
        auto hx  = [](HRESULT hr) { char b[24];
                                      snprintf(b, sizeof(b), "0x%08lX", (unsigned long)hr);
                                      return std::string(b); };
        HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
        com_ours_ = (hr == S_OK || hr == S_FALSE);
        if (FAILED(hr) && hr != RPC_E_CHANGED_MODE) {
            *why_not = "CoInitializeEx failed " + hx(hr);
            return false;
        }
        hr = MFStartup(MF_VERSION, MFSTARTUP_FULL);
        if (FAILED(hr)) { *why_not = "MFStartup failed " + hx(hr); return false; }
        mf_ours_ = true;

        IMFMediaType* tin = nullptr;
        if (FAILED(MFCreateMediaType(&tin)) || !tin) {
            *why_not = "MFCreateMediaType (input) failed " + hx(hr);
            return false;
        }
        tin->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Audio);
        tin->SetGUID(MF_MT_SUBTYPE, MFAudioFormat_PCM);
        tin->SetUINT32(MF_MT_AUDIO_BITS_PER_SAMPLE, 16);
        tin->SetUINT32(MF_MT_AUDIO_SAMPLES_PER_SECOND, kRate48);
        tin->SetUINT32(MF_MT_AUDIO_NUM_CHANNELS, 2);
        tin->SetUINT32(MF_MT_AUDIO_BLOCK_ALIGNMENT, 4);
        tin->SetUINT32(MF_MT_AUDIO_AVG_BYTES_PER_SECOND, kRate48 * 4);

        IMFMediaType* tout = nullptr;
        if (FAILED(MFCreateMediaType(&tout)) || !tout) {
            rel(tin);
            *why_not = "MFCreateMediaType (aac) failed " + hx(hr);
            return false;
        }
        tout->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Audio);
        tout->SetGUID(MF_MT_SUBTYPE, MFAudioFormat_AAC);
        tout->SetUINT32(MF_MT_AUDIO_SAMPLES_PER_SECOND, kRate48);
        tout->SetUINT32(MF_MT_AUDIO_NUM_CHANNELS, 2);
        tout->SetUINT32(MF_MT_AUDIO_BITS_PER_SAMPLE, 16);
        tout->SetUINT32(MF_MT_AUDIO_BLOCK_ALIGNMENT, 1);
        tout->SetUINT32(MF_MT_AUDIO_AVG_BYTES_PER_SECOND, 16000);

        MFT_REGISTER_TYPE_INFO ri, ro;
        ZeroMemory(&ri, sizeof(ri));
        ZeroMemory(&ro, sizeof(ro));
        tin->GetGUID(MF_MT_MAJOR_TYPE, &ri.guidMajorType);
        tin->GetGUID(MF_MT_SUBTYPE, &ri.guidSubtype);
        tout->GetGUID(MF_MT_MAJOR_TYPE, &ro.guidMajorType);
        tout->GetGUID(MF_MT_SUBTYPE, &ro.guidSubtype);

        IMFActivate** acts = nullptr;
        UINT32 n = 0;
        hr = MFTEnumEx(MFT_CATEGORY_AUDIO_ENCODER, MFT_ENUM_FLAG_ALL, &ri, &ro, &acts, &n);
        rel(tin);
        rel(tout);
        if (FAILED(hr) || n == 0 || !acts) {
            *why_not = "no AAC encoder MFT is registered on this host (MFTEnumEx) " + hx(hr);
            return false;
        }
        IMFTransform* mft = nullptr;
        hr = acts[0]->ActivateObject(IID_IMFTransform, (void**)&mft);
        for (UINT32 i = 0; i < n; ++i) acts[i]->Release();
        CoTaskMemFree(acts);
        if (FAILED(hr) || !mft) {
            *why_not = "the AAC encoder MFT could not be activated " + hx(hr);
            return false;
        }

        // The measured ORDER of the type pair, and the measured field values.  The media types
        // are rebuilt here on purpose: ORDER is the detail that must not drift, and this call
        // pair is green on this box in the probe exactly as written.
        IMFMediaType* ti = nullptr;
        IMFMediaType* to = nullptr;
        MFCreateMediaType(&ti);
        MFCreateMediaType(&to);
        if (!ti || !to) {
            mft->Release();
            if (ti) ti->Release();
            if (to) to->Release();
            *why_not = "the type pair could not be built after the encoder was found";
            return false;
        }
        ti->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Audio);
        ti->SetGUID(MF_MT_SUBTYPE, MFAudioFormat_PCM);
        ti->SetUINT32(MF_MT_AUDIO_BITS_PER_SAMPLE, 16);
        ti->SetUINT32(MF_MT_AUDIO_SAMPLES_PER_SECOND, kRate48);
        ti->SetUINT32(MF_MT_AUDIO_NUM_CHANNELS, 2);
        ti->SetUINT32(MF_MT_AUDIO_BLOCK_ALIGNMENT, 4);
        ti->SetUINT32(MF_MT_AUDIO_AVG_BYTES_PER_SECOND, kRate48 * 4);
        to->SetGUID(MF_MT_MAJOR_TYPE, MFMediaType_Audio);
        to->SetGUID(MF_MT_SUBTYPE, MFAudioFormat_AAC);
        to->SetUINT32(MF_MT_AUDIO_SAMPLES_PER_SECOND, kRate48);
        to->SetUINT32(MF_MT_AUDIO_NUM_CHANNELS, 2);
        to->SetUINT32(MF_MT_AUDIO_BITS_PER_SAMPLE, 16);
        to->SetUINT32(MF_MT_AUDIO_BLOCK_ALIGNMENT, 1);
        to->SetUINT32(MF_MT_AUDIO_AVG_BYTES_PER_SECOND, 16000);
        HRESULT ho = mft->SetOutputType(0, to, 0);   // detail 1: OUTPUT first,
        HRESULT hi = mft->SetInputType(0, ti, 0);    //            INPUT second
        rel(ti);
        rel(to);
        if (FAILED(ho) || FAILED(hi)) {
            mft->Release();
            *why_not = "the encoder refused the type pair (48k stereo PCM -> AAC) " +
                       hx(ho) + " / " + hx(hi);
            return false;
        }
        hr = mft->ProcessMessage(MFT_MESSAGE_NOTIFY_BEGIN_STREAMING, 0);
        if (FAILED(hr)) {
            // Arm A5 produced bytes WITHOUT this message, so it is a warning and not a refusal:
            // a message the encoder does not want must not take the whole audio route down.
            log_line("  AUDIO ROUTE: NOTIFY_BEGIN_STREAMING was refused (%s); proceeding",
                     hx(hr).c_str());
        }
        mft_ = mft;
        log_line("  AUDIO ROUTE: aac -- windows media foundation AAC encoder, 48 kHz stereo, "
                 "%u-frame blocks, raw AAC with the ASC (11 90) in the esds box", kBlock);
        return true;
    }

    void close()
    {
        if (mft_) {
            mft_->ProcessMessage(MFT_MESSAGE_COMMAND_DRAIN, 0);
            mft_->Release();
            mft_ = nullptr;
        }
        if (mf_ours_) { MFShutdown(); mf_ours_ = false; }
        if (com_ours_) { CoUninitialize(); com_ours_ = false; }
    }

    // 16 kHz MONO PCM16 in, raw AAC frames appended in order.  A false return carries last_error().
    bool encode_all(const std::vector<int16_t>& mono,
                    std::vector<std::vector<uint8_t>>* frames)
    {
        last_err_.clear();
        if (!mft_) { last_err_ = "AAC route: the encoder is not open"; return false; }
        if (mono.empty()) return true;   // the caller supplies the silence if there is none

        // 16 kHz MONO in, 48 kHz STEREO out is EXACTLY THREE stereo frames per contract frame:
        // the value is written three times, left = right, with no interpolation and no filter, so
        // the only quality claim is that repetition count -- and it is what keeps the trak as long
        // as the picture.  A block is 1024 STEREO frames, so it carries 341 1/3 contract frames and
        // the trailing block is short by less than one of them.
        const size_t slots = (size_t)kBlock * 2u;   // 1024 frames x 2 channels, in int16
        std::vector<int16_t> blk(slots, 0);
        uint32_t blk_frames = 0;                    // STEREO frames filled in THIS block
        for (size_t i = 0; i < mono.size(); ++i) {
            const int16_t v = mono[i];
            for (int rep = 0; rep < 3; ++rep) {
                const size_t j = (size_t)blk_frames * 2u;
                blk[j]     = v;   // left  = the contract sample,
                blk[j + 1] = v;   // right = the SAME value, three times
                ++blk_frames;
                if (blk_frames == kBlock) {
                    if (!feed_block(blk.data(), frames)) return false;
                    blk_frames = 0;
                    std::fill(blk.begin(), blk.end(), 0);
                }
            }
        }
        if (blk_frames) {
            // The partial block is already zero past what was filled, so the encoder sees
            // (used frames + zeros) and the LENGTH of that padding is a counted number rather
            // than something the caller has to infer from the file.  It is rounded UP because a
            // whole contract frame is the unit the log promises, and 1024 is not a multiple of 3,
            // so a trailing block is short by at most one contract frame.
            mono_pad_frames_ += (kBlock - blk_frames + 2u) / 3u;
            if (!feed_block(blk.data(), frames)) return false;
        }
        // Everything fed is not yet in `frames`: the MFT answers some feeds with
        // NEED_MORE_INPUT and only produces on the drain.  Collect that before returning, or the
        // trak is silently short by a block or two (21.3 ms each) and the gate measures it.
        if (!drain_frames(frames)) return false;
        mono_frames_in_ += (uint32_t)mono.size();
        return true;
    }

private:
    bool feed_block(const int16_t* blk, std::vector<std::vector<uint8_t>>* frames)
    {
        auto hx = [](HRESULT hr) { char b[24];
                                      snprintf(b, sizeof(b), "0x%08lX", (unsigned long)hr);
                                      return std::string(b); };
        const DWORD bytes = (DWORD)(slots_kBlock() * sizeof(int16_t));
        IMFMediaBuffer* inbuf = nullptr;
        if (FAILED(MFCreateMemoryBuffer(bytes, &inbuf)) || !inbuf) {
            last_err_ = "AAC route: MFCreateMemoryBuffer (input) failed";
            return false;
        }
        BYTE* p = nullptr;
        DWORD dummy = 0;
        inbuf->Lock(&p, &dummy, &dummy);
        if (p) std::copy(blk, blk + (long)slots_kBlock(), (int16_t*)p);
        inbuf->Unlock();
        inbuf->SetCurrentLength(bytes);
        IMFSample* s = nullptr;
        if (FAILED(MFCreateSample(&s)) || !s) {
            inbuf->Release();
            last_err_ = "AAC route: MFCreateSample (input) failed";
            return false;
        }
        s->AddBuffer(inbuf);
        inbuf->Release();
        const LONGLONG dur = (LONGLONG)kBlock * 10000000LL / kRate48;   // 100 ns units
        s->SetSampleTime(next_time_100ns_);
        s->SetSampleDuration(dur);
        next_time_100ns_ += dur;
        HRESULT hr = mft_->ProcessInput(0, s, 0);
        s->Release();
        if (FAILED(hr)) {
            last_err_ = "AAC route: ProcessInput refused a block " + hx(hr);
            return false;
        }

        // The answer to that ProcessInput is decoded in ONE place, so the feed path and the
        // drain path below cannot disagree about what a ProcessOutput result means.
        return pump_output(frames);
    }

    // Pull whatever the encoder has: a FRESH sample and buffer for EVERY ProcessOutput (detail 2),
    // the bytes read out of od.pSample BEFORE the caller sample is released, and pEvents released
    // after (detail 3).  NEED_MORE_INPUT is a perfectly good answer: it just means there is
    // nothing to take yet, which is why it is true and not an error.
    bool pump_output(std::vector<std::vector<uint8_t>>* frames)
    {
        auto hx  = [](HRESULT hr) { char b[24];
                                      snprintf(b, sizeof(b), "0x%08lX", (unsigned long)hr);
                                      return std::string(b); };
        IMFSample* os = nullptr;
        IMFMediaBuffer* ob = nullptr;
        if (FAILED(MFCreateSample(&os)) || !os) {
            last_err_ = "AAC route: MFCreateSample (output) failed";
            return false;
        }
        if (FAILED(MFCreateMemoryBuffer(kOutBufBytes, &ob)) || !ob) {
            os->Release();
            last_err_ = "AAC route: MFCreateMemoryBuffer (output) failed";
            return false;
        }
        os->AddBuffer(ob);
        ob->Release();
        MFT_OUTPUT_DATA_BUFFER od;
        ZeroMemory(&od, sizeof(od));
        od.dwStreamID = 0;
        od.pSample   = os;
        DWORD status = 0;
        HRESULT h = mft_->ProcessOutput(0, 1, &od, &status);
        if (h == MF_E_TRANSFORM_NEED_MORE_INPUT) {
            os->Release();
            if (od.pEvents) od.pEvents->Release();
            return true;
        }
        if (h == MF_E_TRANSFORM_STREAM_CHANGE) {
            // No measured arm needed this; the encoder kept producing without it.  Carry on.
            log_line("  AUDIO ROUTE: the AAC encoder asked for MF_E_TRANSFORM_STREAM_CHANGE; "
                     "continuing");
            os->Release();
            if (od.pEvents) od.pEvents->Release();
            return true;
        }
        if (FAILED(h)) {
            os->Release();
            if (od.pEvents) { od.pEvents->Release(); od.pEvents = nullptr; }
            last_err_ = "AAC route: ProcessOutput refused the output sample " + hx(h);
            return false;
        }

        // Detail 3: READ pSample BEFORE releasing the sample, and release pEvents after.
        IMFSample* got_s = od.pSample;
        if (got_s) {
            IMFMediaBuffer* mb = nullptr;
            if (SUCCEEDED(got_s->GetBufferByIndex(0, &mb)) && mb) {
                BYTE* q = nullptr;
                DWORD maxl = 0, curl = 0;
                if (SUCCEEDED(mb->Lock(&q, &maxl, &curl)) && q && curl) {
                    if (curl >= 2 && q[0] == (BYTE)0xFF && (q[1] & (BYTE)0xF0) == (BYTE)0xF0)
                        ++adts_frames_;   // must be 0: a sync word in an mp4 trak is garbage
                    frames->push_back(std::vector<uint8_t>(q, q + curl));
                    out_bytes_ += curl;
                    ++aac_frames_;
                }
                mb->Unlock();
                mb->Release();
            }
        }
        os->Release();
        if (od.pEvents) od.pEvents->Release();
        return true;
    }

    // COMMAND_DRAIN, then keep pulling until the encoder has nothing left.  The MFT holds its last
    // one or two blocks back -- every feed that was answered NEED_MORE_INPUT is a block that will
    // only appear after the drain -- and a trak that stops one block early is 1024/48000 = 21.3 ms
    // short of the picture.  That is the exact skew the gate measures, on the side where the sound
    // stops BEFORE the picture does, which is the audible half.
    bool drain_frames(std::vector<std::vector<uint8_t>>* frames)
    {
        if (!mft_) { last_err_ = "AAC route: the encoder is not open"; return false; }
        HRESULT hr = mft_->ProcessMessage(MFT_MESSAGE_COMMAND_DRAIN, 0);
        if (FAILED(hr)) {
            // A drain the encoder refuses must not take the audio route down: the blocks already
            // collected are real audio, so this is counted and reported, and the run goes on with
            // a trak that is short by whatever was being held.
            log_line("  AUDIO ROUTE: the AAC encoder refused COMMAND_DRAIN (0x%08lX); the trak "
                     "is short by whatever it was holding back", (unsigned long)hr);
            return true;
        }
        for (int guard = 0; guard < 8; ++guard) {
            const uint32_t before = aac_frames_;
            if (!pump_output(frames)) return false;
            if (aac_frames_ == before) break;   // nothing came back: the encoder is empty
        }
        return true;
    }

    // One place for the block size in int16 slots: kBlock frames x 2 channels.
    static size_t slots_kBlock() { return (size_t)kBlock * 2u; }

    IMFTransform* mft_ = nullptr;
    bool           mf_ours_ = false;    // only the thing that started MF shuts it down
    bool           com_ours_ = false;
    uint32_t mono_frames_in_ = 0;
    uint32_t mono_pad_frames_ = 0;
    uint32_t aac_frames_ = 0;
    uint32_t adts_frames_ = 0;
    uint64_t out_bytes_ = 0;
    LONGLONG next_time_100ns_ = 0;
    std::string last_err_;
};

bool Replay::perform_cut_body(CutResult& r, const WindowPlan* plan)
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


    // ---- THE SOUND OF THE CLIP ----------------------------------------------------
    // audio_ring_ == nullptr means THIS CUT IS THE PRE-AUDIO, VIDEO-ONLY SHAPE: nothing below
    // runs, no audio trak is written, and the file is the old clip exactly.  An attached ring
    // means the last N seconds of 16 kHz MONO PCM16 (the ASR contract) travel in, stamped with the
    // SAME QPC clock the video ring is stamped with, so the sound and the picture line up on one
    // clock instead of on hope.
    std::vector<int16_t> win;         // the window, 16 kHz mono, oldest first
    uint64_t win_first_qpc_ns = 0;    // the QPC of win[0]
    uint64_t win_silence_frames = 0;  // EXACT-ZERO samples in the window, not an energy guess
    bool     win_clamped = false;     // the ring was asked for time it no longer holds
    bool     audio_route_aac = false;
    std::string audio_why_not = "the AAC route was not attempted";   // why PCM, when it was
    AacEncoder aac;                    // only built when the route is wanted
    if (audio_ring_) {
        // The target is the clip's OWN container duration in nanoseconds: the sound must last
        // exactly as long as the picture, and the gate measures the two to within 50 ms.
        const double video_seconds_target = (double)n_frames * (double)dur / (double)ts_meas;
        const uint64_t a0 = base.qpc_ns;
        const uint64_t a1 = base.qpc_ns + (uint64_t)(video_seconds_target * 1e9);
        std::string aerr;
        if (!audio_ring_->copy_window(a0, a1, &win, &win_first_qpc_ns, &win_silence_frames,
                                      &win_clamped, &aerr)) {
            // LOUD: the tap is armed, the ring holds nothing for this window, and a trak of pure
            // silence would be a recording that lies.  Nothing is written yet, so the clip that
            // never appears is a better answer than the one it would tell.
            log_line("  AUDIO ROUTE: REFUSED - %s", aerr.c_str());
            r.note += " | audio window: " + aerr;
            return false;
        }
        const uint64_t want_frames = (uint64_t)(video_seconds_target * 16000.0 + 0.5);
        if (want_frames && win_silence_frames * 2 > want_frames) {
            // More than half digital silence in the window is a BROKEN RECORDING, not a clip.
            // On this host that is the normal answer when nothing is routed to the tap (see the
            // routing law: a loopback with nothing playing reads exact zeros, and that is CORRECT).
            char b[300];
            snprintf(b, sizeof(b),
                     "the window carries %llu of %llu frames of digital silence; a clip with a "
                     "silence trak would be a recording that lies",
                     (unsigned long long)win_silence_frames, (unsigned long long)want_frames);
            log_line("  AUDIO ROUTE: REFUSED - %s", b);
            r.note += std::string(" | audio window: ") + b;
            return false;
        }
        // Pad or trim to the picture, and say which one happened and by how much: 50 ms is the
        // tolerance the gate measures, so a short window is made whole with COUNTED silence at
        // the end rather than stretched from the middle.
        if (win.size() < want_frames) {
            const uint64_t pad = want_frames - (uint64_t)win.size();
            win.resize((size_t)want_frames, 0);
            log_line("  AUDIO WINDOW: padded %.1f ms of silence at the end (%llu contract frames)",
                     (double)pad * 1000.0 / 16000.0, (unsigned long long)pad);
        } else if (win.size() > want_frames) {
            win.resize((size_t)want_frames);
        }
        if (win_clamped)
            log_line("  AUDIO WINDOW: the ring was asked for time it no longer holds; clamped");
        log_line("  AUDIO WINDOW: %.3f s of 16 kHz mono PCM16, starting %.3f s before the cut, "
                 "first_qpc=%llu",
                 (double)win.size() / 16000.0,
                 (double)(base.qpc_ns - win_first_qpc_ns) / 1e9,
                 (unsigned long long)win_first_qpc_ns);

        // ROUTE 1, AAC.  The encoder is opened HERE, before one byte of the file exists, because
        // the route decides the esds the moov will carry (mp4a + ASC, or sowt) and a route
        // discovered mid-write produces a file that cannot be finished.
        if (aac.open(&audio_why_not)) {
            audio_route_aac = true;
            mc.audio.enabled = true;
            mc.audio.pcm = false;
            mc.audio.sample_rate = 48000;                   // the encoder's rate; the ASR
            mc.audio.channels = 2;                          // contract of 16 kHz mono lives
            mc.audio.sample_width = 2;                      // on the tap side of this cut
            mc.audio.frame_samples = AacEncoder::kBlock;
            mc.audio.bitrate = 128000;
            AacEncoder::audio_specific_config(&mc.audio.asc);
            audio_route_ = "aac";
            audio_route_note_ = "windows media foundation AAC encoder (48 kHz stereo, raw AAC, "
                                "ASC 11 90 in esds)";
        } else {
            // ROUTE 2, PCM.  The trak is a raw PCM trak and the reason the first route did not
            // ship is IN the run log and in the receipt, because "AAC failed quietly" is exactly
            // the kind of sentence this lane was opened to remove.
            mc.audio.enabled = true;
            mc.audio.pcm = true;
            mc.audio.sample_rate = aireplay::audio::kAsrSampleRate;   // 16000, unchanged
            mc.audio.channels = aireplay::audio::kAsrChannels;        // 1
            mc.audio.sample_width = aireplay::audio::kAsrSampleWidth; // 2
            mc.audio.frame_samples = 0;
            mc.audio.bitrate = 256000;
            mc.audio.asc.clear();
            audio_route_ = "pcm";
            audio_route_note_ = "the AAC route did not ship: " + audio_why_not +
                                "; the trak is raw 16 kHz mono PCM16 instead";
            log_line("  AUDIO ROUTE: %s", audio_route_note_.c_str());
        }
    }
    // THE ANCHOR, one line above the first byte of the clip.  Spec §2.1 T0: the row is written in
    // its own commit BEFORE the remux, because "a file with no row is invisible forever".  With no
    // sink installed this is a no-op and the cut proceeds exactly as before.
    if (plan) fire_anchor(r, *plan, fps_meas);

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


    // ---- write the sound, into the SAME muxer and the SAME moov --------------------
    if (audio_ring_) {
        // Re-trim to what the video loop ACTUALLY wrote, so a read that broke inside that loop
        // cannot leave a clip whose sound is longer than its picture.
        const double v_seconds = (double)samples * (double)dur / (double)ts_meas;
        const uint64_t want16 = (uint64_t)(v_seconds * 16000.0 + 0.5);
        if (win.size() > want16) win.resize((size_t)want16);
        if (audio_route_aac) {
            std::vector<std::vector<uint8_t>> frames;
            if (!aac.encode_all(win, &frames) || frames.empty()) {
                r.note += " | AAC route: " +
                          (aac.last_error().empty() ? "the encoder produced no frames"
                                                       : aac.last_error());
                return false;
            }
            for (size_t i = 0; i < frames.size(); ++i) {
                // 1024 samples per AAC frame, in the audio media timescale the muxer chose
                // (48000): duration_ticks is AUDIO ticks, never video ticks.
                if (!mw.write_audio_sample(frames[i].data(), frames[i].size(),
                                           AacEncoder::kBlock, &err)) {
                    r.note += " | mp4 write_audio_sample: " + err;
                    return false;
                }
            }
            audio_frames_ = aac.mono_frames_in();
            audio_seconds_ = (double)aac.aac_frames() * (double)AacEncoder::kBlock / 48000.0;
            if (aac.adts_frames())
                log_line("  AUDIO TRAK: %u AAC block(s) carried an ADTS sync word -- that is "
                         "garbage inside an mp4 trak and is being REPORTED, not hidden",
                         aac.adts_frames());
            log_line("  AUDIO TRAK: aac, %u frame(s), %llu byte(s), %u contract frame(s) in, "
                     "%u of them zero-padding the final block",
                     aac.aac_frames(), (unsigned long long)aac.out_bytes(),
                     aac.mono_frames_in(), aac.mono_pad_frames());
        } else {
            // PCM route: the contract shape itself, written in 20 ms chunks so a reader sees
            // short, evenly sized samples.  duration_ticks is left at 0 and DERIVED from the
            // length, so the chunk size and the chunk duration cannot disagree.
            const size_t chunk = (size_t)(aireplay::audio::kAsrSampleRate / 50);   // 20 ms
            uint64_t written = 0;
            for (size_t off = 0; off < win.size(); off += chunk) {
                const size_t n = (win.size() - off < chunk) ? (win.size() - off) : chunk;
                if (!mw.write_audio_sample((const uint8_t*)(win.data() + off), n * 2u, 0, &err)) {
                    r.note += " | mp4 write_audio_sample: " + err;
                    return false;
                }
                written += n;
            }
            audio_frames_ = written;
            audio_seconds_ = (double)written / 16000.0;
            log_line("  AUDIO TRAK: pcm, %llu chunk frame(s) of 16 kHz mono PCM16",
                     (unsigned long long)written);
        }
        audio_skew_ms_ = (audio_seconds_ - v_seconds) * 1000.0;
    }
    if (!mw.close(&err)) { r.note += " | mp4 close: " + err; return false; }

    r.frames_in_clip = samples;
    r.encoded_in_window = encoded;
    r.bytes = mw.bytes_written();
    r.clip_seconds = (double)(r.cut_qpc_ns - r.base_qpc_ns) / 1e9;
    r.wall_ms = (double)(qpc_now_ns() - t0) / 1e6;

    // ---- the sound's own numbers, next to the video's ------------------------------
    if (audio_ring_) {
        log_line("  CLIP SHAPE: %u video sample(s) + %s audio (%s), audio %.3f s, skew %+.1f ms",
                 (unsigned)samples, audio_route_.c_str(), audio_route_note_.c_str(),
                 audio_seconds_, audio_skew_ms_);
        if (audio_skew_ms_ > 50.0 || audio_skew_ms_ < -50.0)
            log_line("  AUDIO TRAK: WARNING - the audio and video container durations are more "
                     "than 50 ms apart; the gate measures this and it is outside the tolerance");
    }
    r.ok = (samples > 0);
    return r.ok;
}

// ------------------------------------------------------------------ offline cut
//
// Refactored onto plan_job() so the offline path mints clip_id, started_at_s and state through
// the SAME code as the live hotkey — and so the gate can drive the real cut without WGC or NVENC.
// The seed loader is ring_seed_from_h264(), shared with the gate on purpose.
bool Replay::cut_from_h264(const std::string& h264_path, const std::string& out_path,
                           uint32_t fps, uint32_t w, uint32_t h, std::string* err)
{
    // Size the ring from the stream itself.  The file is read twice (once to size, once to seed)
    // because RingBuffer::init() takes the byte count up front; that is cheaper than guessing.
    FILE* probe = nullptr;
    if (fopen_s(&probe, h264_path.c_str(), "rb") != 0 || !probe) {
        *err = "cannot open " + h264_path;
        return false;
    }
    fseek(probe, 0, SEEK_END);
    const long file_bytes = ftell(probe);
    fclose(probe);
    if (file_bytes <= 0) { *err = "empty elementary stream"; return false; }
    // +50% for Annex-B start codes and the muxer-side slack the old code allowed per AU.
    const uint64_t need = (uint64_t)file_bytes + (uint64_t)file_bytes / 2 + (1u << 20);
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

    std::vector<bool> au_idr;
    std::string seed_err;
    const size_t appended = ring_seed_from_h264(&ring_, h264_path, fps, &au_idr, &seed_err);
    if (appended < 2) { *err = "seeding the ring failed: " + seed_err; return false; }

    // The SAME planner the hotkey uses.  requested_s = 0 => the whole ring, which is what an
    // offline cut has always meant: base = the first IDR held, end = the newest byte.
    RingEntry last_e;
    if (!ring_.entry_at(ring_.count() - 1, &last_e)) { *err = "last entry missing"; return false; }

    CutResult r;
    r.path = out_path;
    WindowPlan plan;
    if (!plan_job(last_e.qpc_ns, 0.0, "offline-cut", r, plan)) {
        *err = "no cuttable window: " + r.note;
        return false;
    }
    r.captured_in_window = appended;
    r.encoded_in_window = appended;
    r.idr_pre_roll_ms = plan.delivered_s * 1000.0;
    r.expected_in_window = appended;

    ring_.pin(r.base_abs);
    const bool ok = perform_cut(r, &plan);
    ring_.unpin();
    last_cut_ = r;
    log_line("  OFFLINE CUT: %s -> %s  aus=%zu  clip_id=%s  started_at_s=%.3f  state=%s  "
             "frames_in_clip=%llu  bytes=%llu  wall_ms=%.1f  note=%s",
             h264_path.c_str(), out_path.c_str(), appended, r.clip_id.c_str(), r.started_at_s,
             r.state.c_str(), (unsigned long long)r.frames_in_clip, (unsigned long long)r.bytes,
             r.wall_ms, r.note.empty() ? "(none)" : r.note.c_str());
    if (!ok) { *err = "perform_cut failed: " + r.note; return false; }
    return true;
}
void Replay::cut_thread_main(){
    for (;;) {
        CutResult job;
        WindowPlan plan;
        {
            std::unique_lock<std::mutex> lk(cut_mu_);
            cut_cv_.wait(lk, [&] { return cut_quit_ || cut_has_job_; });
            if (cut_quit_ && !cut_has_job_) return;
            job = cut_job_;
            plan = cut_plan_;
            cut_has_job_ = false;
        }
        CutResult res = job;
        bool ok = perform_cut(res, &plan);
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

        // ---- THE HOTKEY, consumed here -----------------------------------------------------
        // Drained on the capture thread because request_cut() reads capture_qpc_.  Non-blocking:
        // `take(0)` returns at once, so a run with no hotkey armed pays one null check per frame.
        drain_hotkey();

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
        // A hotkey cut may still be in flight even when no timer cut was signalled — a press in
        // the last second of the run is exactly the case this product exists for, and returning
        // while its muxer is still open would leave the owner with no file and no error.
        bool busy = false;
        {
            std::lock_guard<std::mutex> lk(cut_mu_);
            busy = cut_busy_;
        }
        if (busy) {
            if (!wait_cut_done(20000)) log_line("  WARN the cut thread did not finish within 20 s");
        } else {
            log_line("  NOTE: no cut was signalled in this run");
        }
    }
    return true;
}

void Replay::shutdown()
{
    // The hotkey goes FIRST and unconditionally.  A global F10/F11/F9/F12/PrintScreen
    // registration that outlives the object would steal those keys from the owner's desktop for
    // the rest of the session, with nothing left to unregister it.
    disarm_hotkey();
    clip_sink_ = nullptr;

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
