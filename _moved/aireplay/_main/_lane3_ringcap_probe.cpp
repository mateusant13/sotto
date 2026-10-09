// _lane3_ringcap_probe.cpp — the measurement instrument for lane 3 (ring cap VRAM vs RAM).
//
// It links ring_buffer.cpp + common.cpp and prints, machine-readable, BOTH policies:
//   * OLD  = clamp(DedicatedVideoMemory/16, 256 MiB, 2048 MiB)   — d3d11_ctx.cpp:70, the code
//            as it stood; the VRAM probe is read here so the OLD arm needs no D3D device.
//   * NEW  = min(4 GiB, 25% of TotalPhysicalMemory, 50% of AvailPhysicalMemory), floored at
//            256 MiB and MiB-aligned down — ring_buffer.cpp's shipped query_ring_budget().
//            CORRECTED 2026-10-07: this header previously printed the SUPERSEDED formula
//            ("min(4 GiB, 25% of TotalPhysicalMemory), floored"), which omits the
//            availability term and the named floor — the two arms that the gate's ARM E
//            falsifies.  The law quoted here is the one the gate itself parses out of the
//            shipped source (_lane3-ringcap-gate.ps1:9-10, :167-168).
//
// Plus the derived seconds-of-ring at a given bitrate/resolution.  DERIVED is arithmetic at
// the code's own bitrate law; it is NOT a measurement of a 4K run — N=0 runs exist above
// 1080p, but NOT because a clamp pinned the window: lane 7 lifted that clamp at 12:26
// (replay.cpp:38-42, negotiate_capture_window), and WGC refuses every capture item on this
// host anyway (receipt-18 §2).  The reference to a removed "replay.cpp:57" pin that stood
// here is what made this header claim a hardware reason for a measurement that does not
// exist; it is corrected, not merely re-cited.
//
// Prints one line per fact, exits 0.
#include "ring_buffer.h"

#include <cstdio>
#include <cstdlib>

using namespace aireplay;

// The OLD policy, reproduced verbatim from d3d11_ctx.cpp:66-75.  It is reproduced here (not
// called) because that file needs a live DXGI device to fill info.dedicated_vram, and the
// gate must run without opening an adapter.
static uint64_t old_policy_cap(uint64_t dedicated_vram)
{
    uint64_t cap = dedicated_vram / 16;
    const uint64_t lo = 256ull << 20, hi = 2048ull << 20;
    if (cap < lo) cap = lo;
    if (cap > hi) cap = hi;
    return cap;
}

// Dedicated video memory, read from DXGI without creating a device.
static uint64_t probe_vram()
{
    IDXGIFactory1* f = nullptr;
    uint64_t best = 0;
    if (FAILED(CreateDXGIFactory1(__uuidof(IDXGIFactory1), (void**)&f)) || !f) return 0;
    for (UINT i = 0; i < 16; ++i) {
        IDXGIAdapter1* a = nullptr;
        if (f->EnumAdapters1(i, &a) == DXGI_ERROR_NOT_FOUND) break;
        DXGI_ADAPTER_DESC1 d;
        memset(&d, 0, sizeof(d));
        a->GetDesc1(&d);
        if (d.VendorId == 0x10DE && (uint64_t)d.DedicatedVideoMemory > best)
            best = (uint64_t)d.DedicatedVideoMemory;   // the NVIDIA one: the vendor the app targets
        a->Release();
    }
    f->Release();
    return best;
}

int main()
{
    RingBudget b = query_ring_budget();
    uint64_t vram = probe_vram();
    uint64_t old_cap = old_policy_cap(vram);
    uint64_t new_cap = ring_budget_cap_bytes();

    printf("PROBE total_physical_bytes=%llu total_physical_mib=%llu query_ok=%d\n",
           (unsigned long long)b.total_physical_bytes,
           (unsigned long long)(b.total_physical_bytes >> 20), b.query_ok ? 1 : 0);
    printf("PROBE quarter_mib=%llu ceiling_binds=%d floor_applied=%d\n",
           (unsigned long long)(b.quarter_bytes >> 20),
           b.ceiling_binds ? 1 : 0, b.floor_applied ? 1 : 0);
    printf("PROBE dedicated_vram_bytes=%llu dedicated_vram_mib=%llu\n",
           (unsigned long long)vram, (unsigned long long)(vram >> 20));
    printf("PROBE old_cap_bytes=%llu old_cap_mib=%llu\n",
           (unsigned long long)old_cap, (unsigned long long)(old_cap >> 20));
    printf("PROBE new_cap_bytes=%llu new_cap_mib=%llu\n",
           (unsigned long long)new_cap, (unsigned long long)(new_cap >> 20));

    // Ratio of each cap to the pool the arena is really allocated from (system RAM).
    if (b.total_physical_bytes)
        printf("PROBE old_pct_of_ram=%.4f new_pct_of_ram=%.4f\n",
               100.0 * (double)old_cap / (double)b.total_physical_bytes,
               100.0 * (double)new_cap / (double)b.total_physical_bytes);

    // The clamp, exercised as a PURE function so the test commits no gigabytes.
    printf("PROBE clamp_probe_under=%zu clamp_probe_over=%zu\n",
           ring_apply_budget(512ull << 20, b),
           ring_apply_budget(8ull << 30, b));

    // Seconds of ring the cap buys, at the code's own law: want = bitrate/8 * seconds, and
    // the kept window is cap*8/bitrate.  replay.cpp:98-102 scales the gaming anchor (45 Mbps
    // at 1920x1080p60) by pixel count.
    struct Case { const char* label; uint32_t w, h, fps; };
    const Case cases[] = {
        { "1080p60", 1920, 1080, 60 },
        { "4K60",    3840, 2160, 60 },
    };
    const uint32_t anchor_bps = 45000000u;   // replay.cpp:15, gaming mode
    const uint32_t window_s   = 120u;         // replay.cpp:15, gaming ring_seconds
    for (const Case& c : cases) {
        double px  = (double)c.w * (double)c.h * (double)c.fps;
        double ref = 1920.0 * 1080.0 * 60.0;
        double bps = (double)anchor_bps * px / ref;
        double want_mib  = bps / 8.0 * (double)window_s / 1048576.0;
        double old_keep  = (double)old_cap * 8.0 / bps;
        double new_keep  = (double)new_cap * 8.0 / bps;
        printf("PROBE case=%s bitrate_mbps=%.2f want_mib=%.2f old_kept_s=%.2f new_kept_s=%.2f "
               "old_clipped=%d new_clipped=%d basis=DERIVED\n",
               c.label, bps / 1e6, want_mib, old_keep, new_keep,
               old_keep < (double)window_s ? 1 : 0,
               new_keep < (double)window_s ? 1 : 0);

        // WHAT THE LIVE PATH ACTUALLY CHOOSES.  replay.cpp:130 still reads
        // d3d_.ring_cap_bytes() (the VRAM cap), so today chose = min(want, old_cap) and the
        // new RAM cap is only a CEILING the caller never reaches.  These two lines are the
        // measured difference between "the policy is fixed" and "the caller asks for it".
        double want_b = bps / 8.0 * (double)window_s;
        double live_today   = want_b < (double)old_cap ? want_b : (double)old_cap;
        double live_hooked  = want_b < (double)new_cap ? want_b : (double)new_cap;
        printf("PROBE livepath case=%s want_mib=%.2f chose_today_mib=%.2f chose_with_hookup_mib=%.2f "
               "hookup_needed=%d today_kept_s=%.2f hooked_kept_s=%.2f basis=DERIVED\n",
               c.label, want_mib / 1048576.0, live_today / 1048576.0, live_hooked / 1048576.0,
               (live_hooked > live_today) ? 1 : 0,
               live_today * 8.0 / bps, live_hooked * 8.0 / bps);
    }
    printf("PROBE done\n");
    return 0;
}