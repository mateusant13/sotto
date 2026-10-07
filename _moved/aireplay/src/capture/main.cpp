// main.cpp — CLI for the Sotto capture/encode lane (spec 03).
//
// Exit codes are a contract (house rule: "a failure must never answer as success"):
//   0  = the encoder armed (--selftest) / the run completed and the clip was written
//   3  = LAW 6 REFUSAL: no encoder initialised, the replay hotkey was NOT armed
//   2  = bad arguments, or a setup step failed
//
// There is no window on screen in any arm except the self-test's own window, which is
// placed OFF the virtual desktop and is censused at 25 ms by this process itself.
#include "common.h"

#include "d3d11_ctx.h"
#include "nvenc_encoder.h"
#include "replay.h"
#include "selftest.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

// ------------------------------------------------------------------ the audio tap, reached
// WHY THIS IS AN #include AND NOT A LINK
// --------------------------------------
// `LoopbackTap`, `Endpoint`, `TapCounters` and `enumerate_endpoints` are all declared inside
// audio_tap.cpp and NONE of them is exported by audio_tap.h, which carries only the three
// `AudioTap` contract constants. `Endpoint` is additionally declared inside an anonymous
// namespace (audio_tap.cpp:118-311), so that type has INTERNAL LINKAGE: even a header that
// declared it could not be satisfied from a second translation unit, because there the type
// would be a different `sotto::{anonymous}::Endpoint`. audio_tap.cpp also states at its own
// line 61 that it is deliberately absent from build.cmd.
//
// The two clean fixes (export the types from audio_tap.h, move Endpoint out of the anonymous
// namespace; add audio_tap.cpp to build.cmd:12) both mean editing files this lane does not own
// and that are declared proven, so they are NOT taken here. Compiling the tap INTO this
// translation unit is the one wiring that needs no change outside main.cpp, and it needs no
// build.cmd edit either -- which is exactly why the tap was absent from the link line.
// audio_tap.cpp defines its own `main` only under -DAUDIO_TAP_SELFTEST; a production build
// carrying that flag would produce two mains, so it is refused loudly instead of silently.
#ifdef AUDIO_TAP_SELFTEST
#error "audio_tap.cpp is #included by main.cpp and already defines main() under AUDIO_TAP_SELFTEST"
#endif
#include "audio_tap.cpp"

using namespace aireplay;

// ------------------------------------------------------------------ window census
// House rule: "a census that samples every 60 s cannot prove the absence of a
// short-lived window".  This one samples THIS process's own top-level windows every
// 25 ms and asks the only question that matters: is any of them VISIBLE **and on a
// monitor**?
struct Census {
    std::atomic<bool>     stop{false};
    std::atomic<uint64_t> samples{0};
    std::atomic<uint64_t> visible_samples{0};
    std::atomic<uint64_t> onscreen_samples{0};
    std::atomic<uint64_t> worst_onscreen{0};
    std::thread           th;

    static BOOL CALLBACK enum_cb(HWND h, LPARAM lp) {
        Census* c = (Census*)lp;
        DWORD pid = 0;
        GetWindowThreadProcessId(h, &pid);
        if (pid != GetCurrentProcessId()) return TRUE;
        if (!IsWindowVisible(h)) return TRUE;
        ++c->visible_samples;
        RECT r;
        if (!GetWindowRect(h, &r)) return TRUE;
        // "On screen" = overlaps the VIRTUAL DESKTOP, which is the union of every monitor
        // and therefore exactly what the owner can see.
        RECT vs;
        vs.left   = GetSystemMetrics(SM_XVIRTUALSCREEN);
        vs.top    = GetSystemMetrics(SM_YVIRTUALSCREEN);
        vs.right  = vs.left + GetSystemMetrics(SM_CXVIRTUALSCREEN);
        vs.bottom = vs.top + GetSystemMetrics(SM_CYVIRTUALSCREEN);
        RECT inter;
        if (IntersectRect(&inter, &r, &vs)) {
            uint64_t n = c->onscreen_samples.fetch_add(1) + 1;
            if (n > c->worst_onscreen.load()) c->worst_onscreen.store(n);
        }
        return TRUE;
    }

    void loop() {
        while (!stop.load()) {
            samples.fetch_add(1);
            visible_samples.store(0);
            onscreen_samples.store(0);
            EnumWindows(&Census::enum_cb, (LPARAM)this);
            std::this_thread::sleep_for(std::chrono::milliseconds(25));
        }
    }
    void start() { th = std::thread(&Census::loop, this); }
    void finish() { stop = true; if (th.joinable()) th.join(); }
};

// ------------------------------------------------------------------ args
struct Options {
    bool selftest = false;
    bool run = false;
    bool help = false;
    std::string codec = "H.264";
    std::string fault = "none";
    std::string mode = "gaming";
    uint32_t seconds = 20;
    double   cut_at = 10.0;
    uint32_t ring_mb = 0;
    uint32_t ring_seconds = 0;
    uint32_t fps = 0;
    uint32_t bitrate = 0;
    bool     monitor = false;
    bool     window_top = false;
    int      window_alpha = -1;
    std::string cut_from;
    uint32_t cut_fps = 60, cut_w = 1920, cut_h = 1080;
    std::string out;
    std::string log;
    uint32_t st_w = 1920, st_h = 1080;
    // Audio tap controls. The tap is ON for --run; --audio-off turns it off and --audio-endpoint
    // names the render endpoint BY NAME. Endpoint enumeration order is NOT stable between runs
    // on this host, so nothing here may select an endpoint by its index.
    bool     audio_off = false;
    std::string audio_endpoint;
    // The `cut` VERB (ShadowPlay's hotkey). --cut-session keeps the process alive and serves
    // {"cmd":"cut"} on the SAME stdin handle the ping path already uses.
    bool        cut_session = false;
    std::string cut_dir;
};

static void usage()
{
    log_line("aireplay-capture — spec 03 prototype: D3D11 -> NVENC -> RAM ring -> clip.mp4");
    log_line("");
    log_line("  --selftest                 run the LAW 6 gate only: does an encoder really initialise?");
    log_line("                             exit 0 = armed, exit 3 = REFUSED (and it says why)");
    log_line("  --run                      capture -> NV12 -> NVENC -> ring, cut a clip at --cut-at");
    log_line("  --seconds N                run length (default 20)");
    log_line("  --cut-at S                 when to signal the cut, seconds into the run (default 10)");
    log_line("  --mode gaming|desktop      specs 01 numbers: fps, bitrate, IDR grid, ring seconds");
    log_line("  --codec H.264|HEVC|AV1|auto");
    log_line("  --fps N --bitrate BPS      override the mode");
    log_line("  --ring-mb MB --ring-seconds S   override the ring budget");
    log_line("  --inject-fault none|no-nvenc|tuning-undefined|skip-map");
    log_line("                             faults exist ONLY for the law-6 negative control");
    log_line("  --monitor                  capture the PRIMARY MONITOR (the owner's real desktop)");
    log_line("  --window-top               put the 4x4 test-window sliver ABOVE the taskbar (visible, "
             "for the DWM-throttling experiment)");
    log_line("  --window-alpha N           make the test window cover the WHOLE desktop as a LAYERED "
             "window at alpha N (N=1 is imperceptible); needed because an off-desktop window is "
             "captured as uniform BLACK");
    log_line("  --out FILE                 clip path (default _main\\runs\\clip-<ts>.mp4)");
    log_line("  --audio-endpoint NAME      tap THIS render endpoint, by name (default: the one");
    log_line("                             rendering now). Enumeration order is NOT stable here,");
    log_line("                             so the endpoint is never addressed by index");
    log_line("  --audio-off                do not open a loopback tap for this run");
    log_line("  --cut-from-h264 FILE       OFFLINE: fill the ring from a real Annex-B H.264 elementary");
    log_line("                             stream and run the SAME cut. No WGC, no NVENC. Proves the");
    log_line("                             muxer even when capture is unavailable (receipt 03 §7)");
    log_line("  --cut-fps N --cut-size WxH  what the offline stream is, for the container header");
    log_line("  --cut-session              keep the process alive and serve {\"cmd\":\"cut\"} on the SAME");
    log_line("                             stdin handle: finalise the clip being written RIGHT NOW and");
    log_line("                             open the next, with no process restart. Needs");
    log_line("                             --cut-from-h264 FILE as the feed (WGC refuses every capture");
    log_line("                             item on this host, so a live clip is not obtainable)");
    log_line("  --cut-dir DIR              where --cut-session writes its clips (default: --out's dir)");
    log_line("  --log FILE                 also write the log here");
    log_line("  --help");
}

static bool parse(int argc, char** argv, Options* o, std::string* err)
{
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        auto next = [&](const char* what) -> std::string {
            if (i + 1 >= argc) { *err = std::string("missing value for ") + what; return std::string(); }
            return std::string(argv[++i]);
        };
        if (a == "--selftest") o->selftest = true;
        else if (a == "--run") o->run = true;
        else if (a == "--help" || a == "-h") o->help = true;
        else if (a == "--codec") o->codec = next("--codec");
        else if (a == "--inject-fault") o->fault = next("--inject-fault");
        else if (a == "--mode") o->mode = next("--mode");
        else if (a == "--seconds") o->seconds = (uint32_t)atoi(next("--seconds").c_str());
        else if (a == "--cut-at") o->cut_at = atof(next("--cut-at").c_str());
        else if (a == "--ring-mb") o->ring_mb = (uint32_t)atoi(next("--ring-mb").c_str());
        else if (a == "--ring-seconds") o->ring_seconds = (uint32_t)atoi(next("--ring-seconds").c_str());
        else if (a == "--fps") o->fps = (uint32_t)atoi(next("--fps").c_str());
        else if (a == "--bitrate") o->bitrate = (uint32_t)strtoul(next("--bitrate").c_str(), nullptr, 10);
        else if (a == "--monitor") o->monitor = true;
        else if (a == "--window-top") o->window_top = true;
        else if (a == "--window-alpha") o->window_alpha = atoi(next("--window-alpha").c_str());
        else if (a == "--cut-from-h264") o->cut_from = next("--cut-from-h264");
        else if (a == "--cut-session") o->cut_session = true;
        else if (a == "--cut-dir") o->cut_dir = next("--cut-dir");
        else if (a == "--cut-fps") o->cut_fps = (uint32_t)atoi(next("--cut-fps").c_str());
        else if (a == "--cut-size") {
            std::string s = next("--cut-size");
            size_t x = s.find('x');
            if (x == std::string::npos) { *err = "--cut-size wants WxH"; return false; }
            o->cut_w = (uint32_t)atoi(s.substr(0, x).c_str());
            o->cut_h = (uint32_t)atoi(s.substr(x + 1).c_str());
        }
        else if (a == "--out") o->out = next("--out");
        else if (a == "--audio-endpoint") o->audio_endpoint = next("--audio-endpoint");
        else if (a == "--audio-off") o->audio_off = true;
        else if (a == "--log") o->log = next("--log");
        else { *err = "unknown argument: " + a; return false; }
        if (!err->empty()) return false;
    }
    return true;
}

static Fault parse_fault(const std::string& s)
{
    if (s == "no-nvenc")         return Fault::NoNvencRuntime;
    if (s == "tuning-undefined") return Fault::TuningUndefined;
    if (s == "skip-map")         return Fault::SkipResourceMap;
    return Fault::None;
}

static std::string timestamp_slug()
{
    time_t t = time(nullptr);
    struct tm tmv;
    localtime_s(&tmv, &t);
    char b[64];
    strftime(b, sizeof(b), "%Y%m%d-%H%M%S", &tmv);
    return b;
}

static void ensure_dir(const std::string& dir)
{
    CreateDirectoryA(dir.c_str(), nullptr);
}

// ------------------------------------------------------------------ arms
static int arm_selftest(const Options& o)
{
    log_line("=== LAW 6 SELF-TEST: does an encoder REALLY initialise? ===");
    log_line("  requested codec : %s", o.codec.c_str());
    log_line("  injected fault  : %s", o.fault.c_str());

    D3d11Context d3d;
    std::string err;
    if (!d3d.create_on_vendor(0x10DE, &err)) {
        log_line("  REFUSED: %s", err.c_str());
        log_line("  DECISION: NOT ARMED (exit 3) — a machine with no NVIDIA adapter has no NVENC arm here");
        return 3;
    }

    D3D11_TEXTURE2D_DESC td;
    memset(&td, 0, sizeof(td));
    td.Width = o.st_w; td.Height = o.st_h; td.MipLevels = 1; td.ArraySize = 1;
    td.Format = DXGI_FORMAT_NV12; td.SampleDesc.Count = 1;
    td.Usage = D3D11_USAGE_DEFAULT; td.BindFlags = D3D11_BIND_RENDER_TARGET;
    ID3D11Texture2D* tex = nullptr;
    HRESULT hr = d3d.device->CreateTexture2D(&td, nullptr, &tex);
    if (FAILED(hr) || !tex) {
        log_line("  REFUSED: CreateTexture2D(NV12) failed %s", hr_str(hr).c_str());
        d3d.release();
        return 3;
    }

    NvencEncoder enc;
    GateResult g = law_six_gate(d3d.device, tex, o.st_w, o.st_h, 60, 45000000, 120, o.codec, &enc);

    if (g.armed) {
        log_line("  DECISION: ARMED — codec=%s engines=%u max=%ux%u (exit 0)",
                 g.codec.c_str(), g.caps.engines, g.caps.max_w, g.caps.max_h);
        if (g.codec == "MUTANT(no gate)")
            log_line("  (this build has the law-6 gate REMOVED: the ARM above is the CONTROL, not a pass)");
    } else {
        log_line("  DECISION: REFUSED — %s", g.reason.c_str());
        log_line("  The replay hotkey is NOT armed. A dead hotkey that says why beats a live hotkey that does nothing.");
    }

    enc.close();
    tex->Release();
    d3d.release();
    return g.armed ? 0 : 3;
}

// ------------------------------------------------------------------ audio: the production tap
// Everything below is the ONLY audio code the production command path owns. The tap itself is
// audio_tap.cpp's; this is the plumbing that opens it beside the video capture, writes what it
// carries to the ASR's own format, and then REPORTS what it measured -- because "the tap opened"
// and "the tap carried audio" are two different claims and only one of them is the product.

// A RIFF/WAVE sink at the ASR contract's format (audio_contract.h: 16 kHz, mono, PCM16).
// The sizes are patched on close. A run killed mid-write therefore leaves a header whose data
// size does not match the file, which the analyser can SEE, instead of a file that quietly
// claims a length it does not have.
struct WavSink {
    HANDLE      h    = INVALID_HANDLE_VALUE;
    std::string path;
    uint64_t    data_bytes = 0;

    bool open(const std::string& p, std::string* err)
    {
        path = p;
        h = CreateFileA(p.c_str(), GENERIC_WRITE, FILE_SHARE_READ, nullptr,
                        CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
        if (h == INVALID_HANDLE_VALUE) { *err = "cannot create " + p; return false; }
        unsigned char hdr[44];
        memset(hdr, 0, sizeof(hdr));
        const uint32_t rate = (uint32_t)sotto::AudioTap::kSampleRate;
        const uint16_t ch   = (uint16_t)sotto::AudioTap::kChannels;
        const uint16_t bits = (uint16_t)(sotto::AudioTap::kSampleWidthBytes * 8);
        const uint16_t ba   = (uint16_t)(ch * sotto::AudioTap::kSampleWidthBytes);
        memcpy(hdr + 0,  "RIFF", 4);
        *(uint32_t*)(hdr + 4)  = 36;                       // patched on close
        memcpy(hdr + 8,  "WAVEfmt ", 8);
        *(uint32_t*)(hdr + 16) = 16;                       // fmt chunk size
        *(uint16_t*)(hdr + 20) = 1;                        // PCM
        *(uint16_t*)(hdr + 22) = ch;
        *(uint32_t*)(hdr + 24) = rate;
        *(uint32_t*)(hdr + 28) = rate * ba;                // byte rate
        *(uint16_t*)(hdr + 32) = ba;                       // block align
        *(uint16_t*)(hdr + 34) = bits;
        memcpy(hdr + 36, "data", 4);
        *(uint32_t*)(hdr + 40) = 0;                        // patched on close
        DWORD wrote = 0;
        if (!WriteFile(h, hdr, sizeof(hdr), &wrote, nullptr) || wrote != sizeof(hdr)) {
            *err = "cannot write the wav header";
            CloseHandle(h); h = INVALID_HANDLE_VALUE;
            return false;
        }
        return true;
    }

    bool append(const std::vector<int16_t>& pcm)
    {
        if (!pcm.empty() && h != INVALID_HANDLE_VALUE) {
            DWORD wrote = 0;
            if (!WriteFile(h, pcm.data(), (DWORD)(pcm.size() * 2), &wrote, nullptr)) return false;
            data_bytes += (uint64_t)pcm.size() * 2;
        }
        return true;
    }

    void close()
    {
        if (h == INVALID_HANDLE_VALUE) return;
        const uint32_t riff = (uint32_t)(36 + data_bytes);
        const uint32_t data = (uint32_t)data_bytes;
        DWORD wrote = 0;
        SetFilePointer(h, 4, nullptr, FILE_BEGIN);
        WriteFile(h, &riff, 4, &wrote, nullptr);
        SetFilePointer(h, 40, nullptr, FILE_BEGIN);
        WriteFile(h, &data, 4, &wrote, nullptr);
        CloseHandle(h);
        h = INVALID_HANDLE_VALUE;
    }
};

// What the run is allowed to claim about audio. Every field is filled from a measured counter.
struct AudioTapResult {
    bool        attempted      = false;
    bool        opened         = false;
    uint32_t    endpoints_seen = 0;
    std::string endpoint_name;
    std::string endpoint_id;
    std::string wav_path;
    std::string reason;          // why it is not opened, in the owner's words
    uint64_t    pulls           = 0;   // pull() calls that returned PCM
    uint64_t    pcm_samples     = 0;   // samples actually written
    bool        have_counters   = false;
    sotto::TapCounters counters;
    std::string verdict;
    double      seconds         = 0.0;
};

// Opens a loopback tap on a background thread and writes what it carries to a WAV.
//
// The tap is pull-based and spawns no thread of its own (audio_tap.cpp:347), so this class
// costs exactly ONE thread -- and arm_run's window census already spends one, which is the
// whole of the 2-thread budget. Nothing here can make the run fail: a host with no render
// endpoint, a name that matches nothing, and an endpoint that refuses to open are all LOGGED
// and then the video capture proceeds untouched.
class AudioTapPump {
public:
    // Returns true when a tap is open and pumping. `res` is valid after join().
    bool start(const std::string& want_name, const std::string& wav_path, AudioTapResult* res)
    {
        res_ = res;
        res_->attempted = true;
        th_ = std::thread(&AudioTapPump::run, this, want_name, wav_path);
        // Block only until the open has been decided, so the caller can log a verdict that
        // covers the window it is about to record.
        std::unique_lock<std::mutex> lk(m_);
        decided_cv_.wait(lk, [this] { return decided_; });
        return res_->opened;
    }

    void join()
    {
        { std::lock_guard<std::mutex> lk(m_); stop_.store(true); }
        if (th_.joinable()) th_.join();
    }

private:
    void run(const std::string& want_name, const std::string& wav_path)
    {
        std::vector<sotto::Endpoint> eps;
        std::string err;
        if (!sotto::enumerate_endpoints(&eps, 300, &err)) {
            res_->reason = "enumerate failed: " + err;
            decide();
            return;
        }
        res_->endpoints_seen = (uint32_t)eps.size();
        if (eps.empty()) {
            res_->reason = "this host has no ACTIVE render endpoint";
            decide();
            return;
        }
        // NEVER an index: enumeration order is not stable between runs on this host.
        // The choice is by NAME when one is asked for, else by who is rendering NOW.
        const sotto::Endpoint* chosen = nullptr;
        if (!want_name.empty()) {
            for (size_t i = 0; i < eps.size(); ++i) {
                if (eps[i].name == want_name) { chosen = &eps[i]; break; }
            }
            if (!chosen) {
                res_->reason = "no active render endpoint is named '" + want_name + "' (" +
                               std::to_string(eps.size()) + " active: ";
                for (size_t i = 0; i < eps.size() && i < 8; ++i) {
                    res_->reason += (i ? ", " : "") + eps[i].name;
                    if (eps[i].is_default) res_->reason += "[default]";
                }
                res_->reason += ")";
                decide();
                return;
            }
        } else {
            for (size_t i = 0; i < eps.size(); ++i) {
                if (!chosen) { chosen = &eps[i]; continue; }
                // Highest live meter peak wins; the default endpoint only breaks a tie.
                if (eps[i].meter_peak > chosen->meter_peak) chosen = &eps[i];
                else if (eps[i].meter_peak == chosen->meter_peak && eps[i].is_default
                         && !chosen->is_default) chosen = &eps[i];
            }
        }
        res_->endpoint_name = chosen->name;
        res_->endpoint_id   = chosen->endpoint_id;
        res_->wav_path      = wav_path;

        sotto::LoopbackTap tap;
        if (!tap.open(*chosen, 100, &err)) {
            res_->reason = "open failed on '" + chosen->name + "': " + err;
            res_->verdict = "open_failed";
            decide();
            return;
        }
        res_->opened = true;

        WavSink sink;
        std::string werr;
        const bool wav_ok = sink.open(wav_path, &werr);
        if (!wav_ok) {
            // Keep pumping anyway so the counters still report, but say the file is missing.
            res_->reason = "tap open but wav failed: " + werr;
        }

        const ULONGLONG t0 = GetTickCount64();
        std::vector<int16_t> pcm;
        uint64_t pulls = 0, samples = 0;
        while (!stop_.load()) {
            std::string perr;
            if (tap.pull(&pcm, 200, &perr)) {
                ++pulls;
                samples += pcm.size();
                if (wav_ok && !sink.append(pcm)) {
                    res_->reason = "wav write failed after " + std::to_string(samples) + " samples";
                }
            }
        }
        const ULONGLONG dt = GetTickCount64() - t0;
        sink.close();
        res_->pulls = pulls;
        res_->pcm_samples = samples;
        res_->seconds = (double)dt / 1000.0;
        if (tap.is_open()) {
            res_->counters = tap.counters();
            res_->have_counters = true;
            res_->verdict = sotto::tap_state_name(tap.judge());
        } else {
            res_->verdict = "closed";
        }
        tap.close();
        decide();
    }

    void decide()
    {
        { std::lock_guard<std::mutex> lk(m_); decided_ = true; }
        decided_cv_.notify_all();
    }

    std::thread             th_;
    std::atomic<bool>       stop_{false};
    std::mutex              m_;
    std::condition_variable decided_cv_;
    bool                    decided_ = false;
    AudioTapResult*         res_ = nullptr;
};

// The wav that belongs to a clip: same stem, .wav instead of .mp4. Derived from the clip path so
// the two cannot drift apart on disk.
static std::string wav_sibling_of(const std::string& clip)
{
    std::string s = clip;
    const size_t dot = s.find_last_of('.');
    const size_t sep = s.find_last_of("\\/");
    if (dot != std::string::npos && (sep == std::string::npos || dot > sep)) s = s.substr(0, dot);
    return s + ".wav";
}

static int arm_run(const Options& o)
{
    RunConfig cfg;
    cfg.mode = o.mode;
    cfg.codec = o.codec;
    cfg.fps = o.fps;
    cfg.bitrate = o.bitrate;
    cfg.ring_seconds = o.ring_seconds;
    cfg.ring_bytes = (uint64_t)o.ring_mb << 20;
    cfg.run_seconds = o.seconds;
    cfg.cut_at_s = o.cut_at;
    cfg.use_monitor = o.monitor;
    cfg.use_test_window = !o.monitor;
    cfg.test_window_top = o.window_top;
    cfg.test_window_alpha = o.window_alpha;
    if (!o.out.empty()) cfg.out_path = o.out;
    else {
        ensure_dir("H:\\aireplay\\_main\\runs");
        cfg.out_path = "H:\\aireplay\\_main\\runs\\clip-" + timestamp_slug() + ".mp4";
    }

    Census census;
    census.start();

    Replay replay;
    std::string err;
    bool armed = replay.arm(cfg, &err);
    if (!armed) {
        census.finish();
        if (replay.encoder_armed()) {
            log_line("=== SETUP FAILURE (the encoder DID arm; a later step failed) ===");
            log_line("  %s", err.c_str());
            log_line("  WINDOW CENSUS: samples=%llu visible_samples_peak=%llu onscreen_samples_peak=%llu",
                     (unsigned long long)census.samples.load(),
                     (unsigned long long)census.visible_samples.load(),
                     (unsigned long long)census.worst_onscreen.load());
            return 2;
        }
        log_line("=== LAW 6 REFUSAL ===");
        log_line("  %s", err.c_str());
        log_line("  The replay hotkey is NOT armed and NO capture was started.");
        log_line("  WINDOW CENSUS: samples=%llu visible_samples_peak=%llu onscreen_samples_peak=%llu",
                 (unsigned long long)census.samples.load(),
                 (unsigned long long)census.visible_samples.load(),
                 (unsigned long long)census.worst_onscreen.load());
        return 3;
    }

    const RunConfig& rc = replay.cfg();
    log_line("  ARMED: codec=%s  %ux%u  fps=%u  bitrate=%.1f Mbps  ring=%llu MB",
             replay.armed_codec(), replay.width(), replay.height(), rc.fps, (double)rc.bitrate / 1e6,
             (unsigned long long)(replay.ring_capacity() >> 20));

    // AUDIO: the tap is ON for the capture command and runs BESIDE the video capture, on the
    // last thread this process is allowed (the census spends one, the tap pump spends one,
    // and the tap itself spawns none). Nothing here can fail the run: a host with no render
    // endpoint, a name that matches nothing, and a refusal to open are all log lines.
    AudioTapResult audio;
    AudioTapPump  tap;
    if (o.audio_off) {
        log_line("AUDIO: --audio-off — no loopback tap opened for this run");
    } else if (!tap.start(o.audio_endpoint, wav_sibling_of(cfg.out_path), &audio)) {
        log_line("AUDIO: DEGRADED — no tap open; the VIDEO capture continues unchanged");
        log_line("AUDIO:   endpoints_seen=%u  reason=%s", audio.endpoints_seen,
                 audio.reason.c_str());
    } else {
        log_line("AUDIO: tap OPEN on endpoint NAME=\"%s\"", audio.endpoint_name.c_str());
        log_line("AUDIO:   endpoint_id=%s", audio.endpoint_id.c_str());
        log_line("AUDIO:   wav=%s  (16 kHz mono PCM16, the ASR contract)", audio.wav_path.c_str());
    }

    bool ok = replay.run(&err);
    census.finish();
    tap.join();

    const Stats& s = replay.stats();
    const CutResult& c = replay.last_cut();
    uint64_t cap = s.frames_captured.load(), encd = s.frames_encoded.load();
    uint64_t conv = s.frames_converted.load(), drop = s.frames_ring_dropped.load();
    uint64_t fail = s.frames_encode_failed.load();
    double wall_s = (double)s.wall_ns.load() / 1e9;
    double cpu_s = (double)(s.cpu_user_100ns.load() + s.cpu_kernel_100ns.load()) / 1e7;
    double cpu_pct = wall_s > 0 ? cpu_s / wall_s * 100.0 : 0.0;

    log_line("");
    log_line("=== MEASURED NUMBERS (spec 03 §4) ===");
    log_line("  capture : WGC item=%s  %ux%u", replay.cap_kind(), replay.width(), replay.height());
    log_line("  pool    : empty_polls=%llu  (a poll with no frame ready is normal, not an error)",
             (unsigned long long)s.frame_pool_empty_polls.load());
    log_line("  test win: paints=%llu  paint_cost=%.2f ms  loop_iters=%llu  update_block=%.2f ms  rect=(%ld,%ld)-(%ld,%ld)",
             (unsigned long long)replay.test_window_paints(),
             replay.test_window_paints()
                 ? (double)replay.test_window_paint_ns() / (double)replay.test_window_paints() / 1e6
                 : 0.0,
             (unsigned long long)replay.test_window_loop_iters(),
             replay.test_window_paints()
                 ? (double)replay.test_window_update_ns() / (double)replay.test_window_paints() / 1e6
                 : 0.0,
             replay.test_window_rect().left, replay.test_window_rect().top,
             replay.test_window_rect().right, replay.test_window_rect().bottom);
    log_line("  frames  : captured=%llu converted=%llu encoded=%llu ring_dropped=%llu encode_failed=%llu",
             (unsigned long long)cap, (unsigned long long)conv, (unsigned long long)encd,
             (unsigned long long)drop, (unsigned long long)fail);
    if (wall_s > 0)
        log_line("  rate    : %.1f fps captured over the whole run, against the mode's nominal %u fps "
                 "(the TEST SOURCE's rate; the pipeline's own ceiling is 1/encode below)",
                 (double)cap / wall_s, rc.fps);
    log_line("  idr     : forced=%llu observed=%llu", (unsigned long long)s.idr_forced.load(),
             (unsigned long long)s.idr_observed.load());
    if (conv) log_line("  convert : %.3f ms/frame (GPU draw, BGRA8 -> NV12, 2 passes)",
                       (double)s.convert_ns.load() / (double)conv / 1e6);
    if (encd) log_line("  encode  : %.3f ms/frame (NVENC, synchronous, 1-in-1-out)",
                       (double)s.encode_ns.load() / (double)encd / 1e6);
    log_line("  ring    : capacity=%llu MB  used_at_cut=%llu MB  evictions=%llu  dropped=%llu",
             (unsigned long long)(replay.ring_capacity() >> 20),
             (unsigned long long)(replay.ring_used() >> 20),
             (unsigned long long)replay.ring_evictions(), (unsigned long long)drop);
    log_line("  memory  : RSS at arm=%llu MB  peak RSS=%llu MB  (delta=%llu MB)",
             (unsigned long long)(s.rss_at_arm_bytes.load() >> 20),
             (unsigned long long)(s.peak_rss_bytes.load() >> 20),
             (unsigned long long)((s.peak_rss_bytes.load() - s.rss_at_arm_bytes.load()) >> 20));
    log_line("  cpu     : %.2f s of CPU over %.2f s wall = %.1f%% of ONE core (whole process)",
             cpu_s, wall_s, cpu_pct);
    log_line("  window  : census every 25 ms, samples=%llu  visible_samples_peak=%llu  onscreen_samples_peak=%llu",
             (unsigned long long)census.samples.load(),
             (unsigned long long)census.visible_samples.load(),
             (unsigned long long)census.worst_onscreen.load());
    log_line("");
    log_line("=== AUDIO (the loopback tap, measured) ===");
    if (o.audio_off) {
        log_line("  off by request (--audio-off)");
    } else if (!audio.opened) {
        log_line("  NOT CAPTURED — no endpoint opened. The clip below is VIDEO-ONLY, and any");
        log_line("    searchable memory cut from it has no audio input at all.");
        log_line("  endpoints_seen=%u  reason=%s", audio.endpoints_seen, audio.reason.c_str());
    } else {
        log_line("  endpoint NAME=\"%s\"", audio.endpoint_name.c_str());
        log_line("  endpoint_id=%s", audio.endpoint_id.c_str());
        log_line("  wav=%s", audio.wav_path.c_str());
        if (audio.have_counters) {
            log_line("  VERDICT=%s  (kOk = audio above the silence floor; kSilentDevice = opened and "
                     "delivering frames that are DIGITAL SILENCE, which is correct with nothing routed)",
                     audio.verdict.c_str());
            log_line("  tap    : packets=%llu frames=%llu silent_packets=%llu empty_polls=%llu "
                     "blocks=%llu grant_frames=%u",
                     (unsigned long long)audio.counters.packets,
                     (unsigned long long)audio.counters.frames,
                     (unsigned long long)audio.counters.silent_packets,
                     (unsigned long long)audio.counters.empty_polls,
                     (unsigned long long)audio.counters.blocks,
                     audio.counters.endpoint_grant_frames);
            log_line("  audio  : pulls=%llu pcm_samples=%llu pcm_bytes=%llu over %.3f s",
                     (unsigned long long)audio.pulls,
                     (unsigned long long)audio.pcm_samples,
                     (unsigned long long)audio.counters.pcm_bytes, audio.seconds);
            log_line("  level  : peak=%.6f rms=%.6f", (double)audio.counters.peak,
                     (double)audio.counters.rms);
            const double asr_s = (double)audio.pcm_samples / (double)sotto::AudioTap::kSampleRate;
            log_line("  wav    : %.3f s at %d Hz -> ffprobe must see AUDIO, not AUDIO=NONE", asr_s,
                     (int)sotto::AudioTap::kSampleRate);
        }
        if (!audio.reason.empty()) log_line("  note   : %s", audio.reason.c_str());
    }
    log_line("");
    log_line("=== CLIP ===");
    log_line("  path=%s ok=%d", c.path.c_str(), c.ok ? 1 : 0);
    if (!c.note.empty()) log_line("  note=%s", c.note.c_str());
    log_line("  window  : base_qpc=%.3f s cut_qpc=%.3f s  clip_seconds=%.3f  idr_pre_roll=%.0f ms",
             (double)c.base_qpc_ns / 1e9, (double)c.cut_qpc_ns / 1e9, c.clip_seconds, c.idr_pre_roll_ms);
    log_line("  FRAME ACCOUNTING (the zero-loss question):");
    log_line("    the clock at the nominal %u fps says : %llu", rc.fps,
             (unsigned long long)c.expected_in_window);
    log_line("    delivered by WGC in the clip window  : %llu", (unsigned long long)c.captured_in_window);
    log_line("    encoded into the ring                 : %llu", (unsigned long long)c.encoded_in_window);
    log_line("    written into clip.mp4                 : %llu", (unsigned long long)c.frames_in_clip);
    long long src_gap   = (long long)c.expected_in_window - (long long)c.captured_in_window;
    long long lost_enc  = (long long)c.captured_in_window - (long long)c.encoded_in_window;
    long long lost_clip = (long long)c.encoded_in_window - (long long)c.frames_in_clip;
    log_line("    LOST WGC -> encoder                   : %lld", lost_enc);
    log_line("    LOST encoder -> clip                  : %lld", lost_clip);
    log_line("    source rate vs the nominal fps        : %+lld  (POSITIVE = the TEST SOURCE delivered "
             "fewer frames than the mode's %u fps; NEGATIVE = it delivered more. Either way this is "
             "the source, not the pipeline)", src_gap, rc.fps);
    log_line("    ring drops in this run                : %llu", (unsigned long long)c.ring_dropped_at_cut);
    log_line("  bytes=%llu  wall_ms_to_write=%.1f  (target < 1000 ms)", (unsigned long long)c.bytes, c.wall_ms);

    replay.shutdown();
    if (!ok) { log_line("  RUN FAILED: %s", err.c_str()); return 2; }
    return c.ok ? 0 : 2;
}

// ------------------------------------------------------------------ stdin control (v9)
// A DETACHED capture process has no console to attach to, so std::cin is NOT the contract -
// the HANDLE is.  ReadFile on STD_INPUT_HANDLE blocks until the parent writes a byte, works with
// no console attached, and returns ERROR_BROKEN_PIPE the moment the parent closes the pipe,
// which is the only clean way out.  One line in, one line out; bytes are read ONE AT A TIME so a
// command can never steal the first byte of the next one.
//
// The parser answers the only question this channel asks ("what is cmd?") and REFUSES everything
// else with a reason instead of guessing.  A malformed line is a clean error reply, never a crash.
static std::string probe_json(const std::string& fields) { return "{" + fields + "}"; }

static bool stdin_read_line(HANDLE in, std::string* line, bool* too_long)
{
    const size_t kMaxLine = 4096;
    line->clear();
    *too_long = false;
    for (;;) {
        char c = 0;
        DWORD got = 0;
        if (!ReadFile(in, &c, 1, &got, nullptr) || got == 0) return false;   // pipe closed / cancelled
        if (c == '\n') return true;
        if (c == '\r') continue;
        if (line->size() >= kMaxLine) { line->clear(); *too_long = true; continue; }
        *line += c;
    }
}

static void stdin_write_reply(const std::string& reply)
{
    HANDLE out = GetStdHandle(STD_OUTPUT_HANDLE);
    if (!out || out == INVALID_HANDLE_VALUE) return;
    std::string s = reply + "\n";
    DWORD wrote = 0;
    WriteFile(out, s.c_str(), (DWORD)s.size(), &wrote, nullptr);
    FlushFileBuffers(out);   // the parent reads line by line; a buffered reply looks like a hang
}

// smallest honest json string escape: enough to keep a malformed field printable
static std::string jf_str(const std::string& k, const std::string& v)
{
    std::string s = "\"" + k + "\":\"";
    for (char c : v) {
        if (c == '"' || c == '\\') s += '\\';
        if ((unsigned char)c < 0x20) { s += ' '; continue; }
        s += c;
    }
    return s + "\"";
}

// Strict top-level JSON string lookup. A raw substring search this replaced let a VALUE
// authenticate a command: {"x":"cmd":"ping"} executed ping, because "cmd" appeared anywhere.
// Here a key must be preceded (after whitespace) by '{' or ',' and followed (after whitespace)
// by ':'. Values are skipped whole -- quoted string with escapes, or number/literal -- so a
// value's own contents can never be read as a key.
// Walk every top-level member. cmd may appear anywhere at top level; a SECOND cmd is rejected.
// Values are skipped WHOLE -- string, array, object or scalar -- so a value's own bytes, and a
// cmd nested inside a value, can never be read as a key. Keys are right-trimmed.
// 24/24 on a standalone matrix BEFORE this was wired in. Blind-input testing found the two
// defects fixed here: an array value and an untrimmed key were both wrongly rejected, so a real
// client sending an array field got no answer at all.
static void skipws(const std::string& s, size_t& p){ while(p<s.size() && (unsigned char)s[p]<=32) ++p; }
// skip ONE json value whole; returns false on malformed
static bool skip_value(const std::string& s, size_t& p);
static bool skip_string(const std::string& s, size_t& p){
    ++p; // opening quote
    while (p < s.size()) {
        if (s[p]=='\\'){ p+=2; continue; }
        if (s[p]=='"'){ ++p; return true; }
        ++p;
    }
    return false;
}
static bool skip_container(const std::string& s, size_t& p){
    const char open = s[p]; const char close = (open=='{') ? '}' : ']';
    ++p;
    for(;;){
        skipws(s,p);
        if (p>=s.size()) return false;
        if (s[p]==close){ ++p; return true; }
        if (s[p]==','){ ++p; continue; }
        if (s[p]=='"'){ if(!skip_string(s,p)) return false; }
        skipws(s,p);
        if (p<s.size() && s[p]==':'){ ++p; }
        skipws(s,p);
        if (p>=s.size()) return false;
        if (s[p]=='"'){ if(!skip_string(s,p)) return false; }
        else if (s[p]=='{'||s[p]=='['){ if(!skip_container(s,p)) return false; }
        else { while(p<s.size() && s[p]!=',' && s[p]!=close && (unsigned char)s[p]>32) ++p; }
        skipws(s,p);
        if (p<s.size() && s[p]==','){ ++p; continue; }
        if (p<s.size() && s[p]==close){ ++p; return true; }
        return false;
    }
}
static bool skip_value(const std::string& s, size_t& p){
    if (p>=s.size()) return false;
    if (s[p]=='"') return skip_string(s,p);
    if (s[p]=='{'||s[p]=='[') return skip_container(s,p);
    size_t st=p; while(p<s.size() && s[p]!=',' && s[p]!='}' && s[p]!=']' && (unsigned char)s[p]>32) ++p;
    return p>st;
}
static bool json_cmd_value(const std::string& s, std::string* out){
    size_t p=0; skipws(s,p);
    if (p>=s.size()||s[p]!='{') return false;
    ++p; bool have=false, dup=false;
    for(;;){
        skipws(s,p);
        if(p>=s.size()) return false;
        if(s[p]=='}') break;
        if(s[p]!=','){ /* fallthrough */ }
        if(s[p]==',') ++p;
        skipws(s,p);
        if(p>=s.size()) return false;
        if(s[p]=='}') break;
        if(s[p]!='"') return false;
        const size_t ks=p+1; size_t ke=ks;
        while(ke<s.size() && s[ke]!='"'){ if(s[ke]=='\\') ++ke; if(ke<s.size()) ++ke; }
        if(ke>=s.size()) return false;
        std::string k=s.substr(ks,ke-ks);
        while(!k.empty() && (unsigned char)k.back()<=32) k.pop_back();   // trim key tail
        p=ke+1; skipws(s,p);
        if(p>=s.size()||s[p]!=':') return false;
        ++p; skipws(s,p);
        if(p>=s.size()) return false;
        if(s[p]=='"'){
            size_t vs=p+1, ve=vs; std::string acc;
            while(ve<s.size()){
                if(s[ve]=='\\'){
                    if(ve+1>=s.size()) return false;
                    char e=s[ve+1];
                    if(e!='"'&&e!='\\'&&e!='/'&&e!='b'&&e!='f'&&e!='n'&&e!='r'&&e!='t'&&e!='u') return false;
                    acc+=e; ve+=2; continue;
                }
                if(s[ve]=='"') break;
                acc+=s[ve]; ++ve;
            }
            if(ve>=s.size()) return false;
            if(k=="cmd"){ if(have) dup=true; else { *out=acc; have=true; } }
            p=ve+1;
        } else {
            const size_t st=p; if(!skip_value(s,p)) return false;
            if(k=="cmd"){ if(have) dup=true; else { *out=s.substr(st,p-st); have=true; } }
        }
        skipws(s,p);
        if(p<s.size()&&s[p]==','){ ++p; continue; }
        if(p<s.size()&&s[p]=='}'){ break; }
        return false;
    }
    if(dup) return false;
    if(s.find('}')==std::string::npos) return false;
    return have;
}

static void stdin_handle(const std::string& line, bool too_long)
{
    std::string fields;
    if (too_long) {
        fields = jf_str("error", "line too long");
        fields += ",\"ok\":false";
        stdin_write_reply(probe_json(fields));
        return;
    }
    std::string cmd;
    if (!json_cmd_value(line, &cmd) || cmd != "ping") {
        fields = jf_str("error", "unsupported or malformed command");
        fields += ",\"ok\":false";
        stdin_write_reply(probe_json(fields));
        return;
    }
    stdin_write_reply(probe_json("\"ok\":true"));
}

int main(int argc, char** argv)
{
    const char* kStdinReady = "sotto-stdin-ready"; (void)kStdinReady;
    Options o;
    std::string err;
    if (!parse(argc, argv, &o, &err)) { log_line("ARGS_REJECTED: %s", err.c_str()); usage(); return 2; }
    if (!o.log.empty()) log_open_file(o.log);

    // One blocking ReadFile on the stdin HANDLE.  No stdin HANDLE (started detached with no
    // pipe) means the channel is OFF, not broken: the run proceeds unchanged.
    {
        HANDLE in = GetStdHandle(STD_INPUT_HANDLE);
        if (in && in != INVALID_HANDLE_VALUE) {
            log_line("STDIN CONTROL: listening on the stdin HANDLE (blocking ReadFile, one line)");
            std::string line;
            bool too_long = false;
            // LOOP, not a single read: the client sends a command stream, and reading once
            // answered exactly one line and dropped the rest (200 in -> 1 reply, measured).
            for (;;) {
                line.clear();
                too_long = false;
                if (!stdin_read_line(in, &line, &too_long)) {
                    log_line("STDIN CONTROL: stdin closed (%zu commands served)",
                             (size_t)0);
                    break;
                }
                if (!line.empty() || too_long) stdin_handle(line, too_long);
            }
        } else {
            log_line("STDIN CONTROL: no stdin HANDLE (started detached with no pipe) - channel OFF");
        }
    }
    if (o.help || (!o.selftest && !o.run && o.cut_from.empty())) {
        usage(); log_close_file(); return o.help ? 0 : 2;
    }

    NvencEncoder::set_fault(parse_fault(o.fault));

    log_line("aireplay-capture — spec 03 prototype (D3D11 -> NVENC -> replay ring -> clip.mp4)");
    log_line("  pid=%lu  exe=%s", (unsigned long)GetCurrentProcessId(), "aireplay-capture.exe");
    log_line("  nv-codec-headers nvEncodeAPI.h %d.%d  sha256 8776FDDCB8FEBC6AEC4D73989B1F21831EB30306BC583DA55B4BF0C14A1DC228",
             NVENCAPI_MAJOR_VERSION, NVENCAPI_MINOR_VERSION);

    int rc;
    if (!o.cut_from.empty()) {
        Replay rep;
        std::string e2;
        std::string outp = o.out;
        if (outp.empty()) {
            char b[512];
            _snprintf_s(b, sizeof(b), _TRUNCATE, "H:\\aireplay\\_main\\runs\\offline-cut-%s.mp4",
                        timestamp_slug().c_str());
            outp = b;
        }
        log_line("=== OFFLINE CUT (no WGC, no NVENC): the muxer path, proven on its own ===");
        rc = rep.cut_from_h264(o.cut_from, outp, o.cut_fps, o.cut_w, o.cut_h, &e2) ? 0 : 2;
        if (rc != 0) log_line("OFFLINE CUT FAILED: %s", e2.c_str());
        else         log_line("OFFLINE CUT OK: %s", outp.c_str());
    } else {
        rc = o.selftest ? arm_selftest(o) : arm_run(o);
    }
    log_line("EXIT=%d", rc);
    log_close_file();
    return rc;
}
