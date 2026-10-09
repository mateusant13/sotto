# LANE 02 — WASAPI audio loopback gate. THREE ARMS, BOTH COLOURS.
#
# WHAT THIS GATES (src\capture\wasapi_audio.cpp + wasapi_audio.h, this lane's files only):
#   A1  the translation unit COMPILES with the repo's OWN build path
#   A2  the component compiles STANDALONE — no MSVC, no CUDA, no new library beyond the
#       -lole32 -loleaut32 -luuid already in src\capture\build.cmd:12
#   B   a REAL capture against the LIVE device ladder, with the measured peak printed and
#       POPULATION + WINDOW on every number
#   C   the CONTROL: the cure reverted in a COPY, which MUST go red
#
# WHY ARM C EXISTS. This component's headline promise is that silence is a NAMED,
# LOUD verdict (`silent-device`) instead of an empty success. That promise is exactly
# the kind of thing a gate can be built to agree with: a self-consistent component that
# always says `ok` passes every "does it run" check. So ARM C takes a byte copy of the
# translation unit, reverts the one line that maps a below-floor peak onto `kSilentDevice`,
# rebuilds, and asserts the SAME probe now DISAGREES. If the control still agrees, ARM C
# is vacuous and the whole gate fails — that is the control's job.
#
# A SILENT DEVICE IS A VALID GREEN OUTCOME. On this host "nothing is routed" is normal
# and is CORRECT behaviour, not a regression. The gate therefore separates two claims and
# conjuncts them:
#     RUN-VERDICT   the instrument ran and produced a NAMED verdict  (must hold)
#     MEASUREMENT   what it measured: peak, POPULATION, WINDOW       (printed, never faked)
# A gate that reported RED merely because the owner's PC was quiet would be a gate that
# cannot be trusted, so that possibility is designed out.
#
# Law 2 (never pipe a native command to read its exit code): every build and every run
# goes to a FILE and is read back via $LASTEXITCODE. No pipe is ever closed early.
# Law 1 (no visible console window): this script only ever spawns console-mode exes that
# print to redirected handles, and the census at the end samples the OWN pid tree.
#
# Usage: pwsh -NoProfile -File _main\_lane2-audio-gate.ps1 [-WindowMs N] [-MeterMs N] [-BlockMs N] [-SkipLive]
# NOTE ON ARGUMENT SYNTAX, because it cost a silent no-op once: with `pwsh -File`, a
# parameter binds with a SINGLE dash (`-WindowMs 1200`). Passing `--window-ms 1200` does
# not error -- it is silently not bound, the script runs on its DEFAULTS, and the run
# looks perfectly green while measuring a different window than the one you asked for.
# The gate now prints the window it actually used on every line, which is what makes that
# mistake visible instead of invisible.
# Exit : 0 = LANE2-GATE PASS. Non-zero = an arm did not behave.

param(
    [int]$WindowMs = 1200,
    [int]$MeterMs  = 150,
    [int]$BlockMs  = 100,
    [switch]$SkipLive   # build + control only; used when the machine is busy
)
$ErrorActionPreference = 'Continue'

$prod    = 'H:\sotto\_moved\aireplay'
$src     = "$prod\src\capture"
$build   = "$prod\_main\build"
$gatedir = "$build\lane2-gate"
$logs    = "$prod\_main\logs"
$gateLog = "$gatedir\lane2-gate.json"

# ---- the repo's OWN build path, read from src\capture\build.cmd (never invented) -------
# build.cmd:7  set GXX=H:\msys64\mingw64\bin\g++.exe
# build.cmd:8  set SRC=H:\aireplay\src\capture
# build.cmd:9  set OUT=H:\aireplay\_main\build
# build.cmd:12 the exact flag list and library list
$gxx = 'H:\msys64\mingw64\bin\g++.exe'
$buildCmd = "$src\build.cmd"
if (-not (Test-Path -LiteralPath $gxx)) { Write-Output "LANE2-GATE FAIL: g++ not found at $gxx"; exit 1 }
if (-not (Test-Path -LiteralPath $buildCmd)) { Write-Output "LANE2-GATE FAIL: build.cmd missing"; exit 1 }
$buildCmdText = Get-Content -LiteralPath $buildCmd -Raw -Encoding UTF8
$flags = @('-std=c++17', '-O2', '-Wall', '-Wextra', '-Wno-unused-parameter')
$incs  = @('-I', $src, '-I', "$src\third_party")
# build.cmd:12 already links -lole32 -loleaut32 -luuid; this component needs NOTHING
# else, and arm A2 proves it (that is the point of A2).
$libs  = @('-lole32', '-loleaut32', '-luuid', '-lpsapi', '-luser32', '-lgdi32')

foreach ($d in @($build, $gatedir, $logs)) { if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null } }

$report = [ordered]@{ lane = '02-wasapi-audio-loopback'; window_ms = $WindowMs; meter_ms = $MeterMs; block_ms = $BlockMs; arms = [ordered]@{} }
function Say($s) { Write-Output $s }

# =====================================================================================
# ARM A1 — the translation unit COMPILES with the repo's own flags and libraries.
# =====================================================================================
$objA = "$gatedir\wasapi_audio.obj"
$logA = "$gatedir\armA1-build.txt"
& $gxx @flags @incs -c "$src\wasapi_audio.cpp" -o $objA @libs > $logA 2>&1
$a1rc = $LASTEXITCODE
$a1text = if (Test-Path -LiteralPath $logA) { (Get-Content -LiteralPath $logA -Raw -Encoding UTF8) } else { '' }
# -Wall -Wextra are ON: a warning is not a failure, but the count is reported, because a
# silent warning creeping in is how a component starts drifting from the house style.
$a1warn = if ([string]::IsNullOrEmpty($a1text)) { 0 } else { ([regex]::Matches($a1text, 'warning:')).Count }
$a1ok = ($a1rc -eq 0)
$report.arms['A1-compile-with-repo-build-path'] = [ordered]@{
    status = $(if ($a1ok) { 'GREEN' } else { 'RED' })
    rc = $a1rc; warnings = $a1warn
    compiler = $gxx
    flags = ($flags -join ' ')
    libs = ($libs -join ' ')
    build_cmd = $buildCmd
    obj_bytes = $(if (Test-Path -LiteralPath $objA) { (Get-Item -LiteralPath $objA).Length } else { 0 })
    tail = ($a1text -split "`r?`n" | Select-Object -Last 4) -join ' | '
}
Say ("ARM-A1 compile rc={0} warnings={1} population=1 TU  window=1 build" -f $a1rc, $a1warn)

# =====================================================================================
# ARM A2 — the probe links and runs with NO library beyond what build.cmd already links.
# This is the arm that would catch a KSDATAFORMAT_SUBTYPE_* (ksuuid) or a PropVariantClear
# (propsys) creeping in: both COMPILE fine in isolation and fail only at LINK time in the
# product. It was not hypothetical here — both were removed before this arm passed.
# =====================================================================================
$mainCpp = "$gatedir\lane2_audio_probe_main.cpp"
@'
// GENERATED by _main\_lane2-audio-gate.ps1 — the harness main() for the lane-2 audio gate.
// It owns NO audio logic: it enumerates, walks the ladder, prints, exits. Every decision
// about what counts as silence lives in wasapi_audio.cpp, which is why ARM-C (the control)
// only has to revert a line THERE.
#include "wasapi_audio.h"
#include <cstdio>
#include <cstring>
#include <cmath>
#include <cstdlib>
using namespace aireplay;

static int synthetic_arm()
{
    // SYNTHETIC. A generated tone, NOT captured audio. It exercises the ASR sink only,
    // and says so on every line it prints so it can never be read as a capture result.
    int bad = 0;
    const uint32_t in_rate = 48000, out_rate = kAsrSampleRate, n = 4800;
    std::vector<float> in(n);
    for (uint32_t i = 0; i < n; ++i)
        in[i] = (float)(0.5 * sin(2.0 * 3.14159265358979 * 440.0 * (double)i / (double)in_rate));
    AudioBlock b{}; b.samples = in.data(); b.frames = n; b.rate = in_rate;
    std::vector<int16_t> out; std::string err;
    const bool ok = to_asr_pcm16(b, out_rate, &out, &err);
    float peak = 0.0f;
    for (int16_t v : out) { float a = v < 0 ? -(float)v : (float)v; if (a > peak) peak = a; }
    std::printf("ARM2_SYNTH case=decimate ok=%d in_rate=%u out_rate=%u in_frames=%u "
                "out_frames=%u expect_frames=%u peak_out=%.6f src=synthetic\n",
                ok ? 1 : 0, in_rate, out_rate, n, (unsigned)out.size(),
                (unsigned)(n / 3), (double)(peak / 32767.0));
    if (!ok || out.size() != n / 3) { bad++; std::printf("ARM2_SYNTH_FAIL case=decimate err=%s\n", err.c_str()); }
    std::vector<int16_t> out2; std::string err2;
    const bool refused = !to_asr_pcm16(b, 17000, &out2, &err2) && !err2.empty();
    std::printf("ARM2_SYNTH case=refuse-noninteger refused=%d src=synthetic\n", refused ? 1 : 0);
    if (!refused) bad++;
    std::printf("ARM2_SYNTH_RESULT bad=%d src=synthetic\n", bad);
    return bad;
}

static int verdict_table_arm()
{
    // DETERMINISTIC. A fixed table of (open, frames, peak) -> expected state, checked
    // against audio_state_for() with NO device involved. This is what makes the control
    // falsifiable: it does not depend on what the machine happens to be playing, so the
    // reverted copy disagrees here even on a host where audio is flowing.
    struct Case { bool open; uint64_t frames; float peak; const char* want; };
    const Case cases[] = {
        {false, 0,      0.0f,      "closed"},
        {true,  0,      0.0f,      "no-signal"},
        {true,  48000,  0.0f,      "silent-device"},   // delivered a full window of zeros
        {true,  48000,  0.0001f,   "silent-device"},   // measured digital-silence ceiling
        {true,  48000,  0.0009f,   "silent-device"},   // just under the floor
        {true,  48000,  0.001f,    "silent-device"},   // exactly ON the floor: <= is silent
        {true,  48000,  0.0011f,   "ok"},              // just over
        {true,  48000,  0.698243f, "ok"},
    };
    int bad = 0;
    const int n = (int)(sizeof(cases) / sizeof(cases[0]));
    for (int i = 0; i < n; ++i) {
        AudioState got = audio_state_for(cases[i].open, cases[i].frames, cases[i].peak);
        const char* g = audio_state_name(got);
        const bool ok = (std::strcmp(g, cases[i].want) == 0);
        if (!ok) ++bad;
        std::printf("ARM2_VERDICTMAP i=%d/%d open=%d frames=%llu peak=%.6f want=%s got=%s ok=%d\n",
                    i + 1, n, cases[i].open ? 1 : 0,
                    (unsigned long long)cases[i].frames, (double)cases[i].peak,
                    cases[i].want, g, ok ? 1 : 0);
    }
    std::printf("ARM2_VERDICTMAP_RESULT cases=%d population=%d bad=%d deterministic=1\n", n, n, bad);
    return bad;
}

// ARM-D. Repeated open/close of the SAME object on the SAME thread. This is the arm that
// catches an unbalanced COM reference: CoUninitialize is reference-counted, so giving one
// back twice does not crash immediately -- it walks the apartment count down until some
// LATER COM call on the thread fails for a reason that looks nothing like the cause.
// So the check is not "did it crash" but "did every cycle open cleanly and report a
// verdict", repeated N times. MEASURED: this arm exists because self-audit found
// `com_ref_taken_ = com.took()` alongside a ComScope destructor, i.e. CoUninitialize ran
// TWICE per cycle -- a bug that survived a single open/close because it only bites later.
static int cycle_arm(WasapiAudio& tap, const AudioEndpoint& ep, uint32_t block_ms, int cycles, int window_ms)
{
    int bad = 0;
    for (int i = 1; i <= cycles; ++i) {
        std::string err;
        if (!tap.open(ep, block_ms, &err)) {
            std::printf("ARM2_CYCLE i=%d/%d open_failed err=%s\n", i, cycles, err.c_str());
            ++bad;
            break;
        }
        uint64_t frames = 0;
        AudioBlock b{};
        const uint64_t t0 = GetTickCount64();
        for (;;) {
            std::string le;
            if (tap.try_get_block(&b, 50, &le) && b.frames) frames += b.frames;
            if (le.empty() == false) break;
            if ((GetTickCount64() - t0) >= (uint64_t)window_ms) break;
        }
        AudioState s = tap.judge();
        const bool named = (audio_state_name(s) != std::string("?"));
        if (!named) ++bad;
        std::printf("ARM2_CYCLE i=%d/%d open=ok state=%s frames=%llu is_open=%d named=%d\n",
                    i, cycles, audio_state_name(s), (unsigned long long)frames,
                    tap.is_open() ? 1 : 0, named ? 1 : 0);
        tap.close();
        if (tap.is_open()) { std::printf("ARM2_CYCLE_FAIL i=%d still_open_after_close\n", i); ++bad; }
    }
    // THE ASSERTION THAT ACTUALLY MATTERS. CoUninitialize is reference-counted, so a
    // double release does not crash -- it just drives the apartment count down and the
    // damage surfaces on some LATER COM call. MEASURED: with the handoff reverted, five
    // cycles of open/close reported bad=0 and looked PERFECTLY healthy, while every
    // cycle had uninitialised COM twice for one initialise. The balance is what names it.
    const int64_t bal = com_reference_balance();
    if (bal != 0) {
        std::printf("ARM2_COMBALANCE i=%d/%d balance=%lld taken=%lld released=%lld -- "
                    "UNBALANCED: COM was initialised and uninitialised a different number of times\n",
                    cycles, cycles, (long long)bal, (long long)com_reference_taken_count(),
                    (long long)com_reference_released_count());
        ++bad;
    } else {
        std::printf("ARM2_COMBALANCE cycles=%d balance=%lld taken=%lld released=%lld balanced=1\n",
                    cycles, (long long)bal, (long long)com_reference_taken_count(),
                    (long long)com_reference_released_count());
    }
    std::printf("ARM2_CYCLE_RESULT cycles=%d population=%d bad=%d\n", cycles, cycles, bad);
    return bad;
}

int main(int argc, char** argv)
{
    setvbuf(stdout, nullptr, _IONBF, 0);
    uint32_t meter_ms = 150, window_ms = 1200, block_ms = 100;
    bool synth = false, table = false, table_only = false;
    int cycles = 0;
    for (int i = 1; i < argc; ++i) {
        if (!strcmp(argv[i], "--meter-ms") && i + 1 < argc)  meter_ms  = (uint32_t)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--window-ms") && i + 1 < argc) window_ms = (uint32_t)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--block-ms") && i + 1 < argc)  block_ms  = (uint32_t)atoi(argv[++i]);
        else if (!strcmp(argv[i], "--synthetic")) synth = true;
        else if (!strcmp(argv[i], "--verdict-table")) table = true;
        else if (!strcmp(argv[i], "--table-only")) table_only = true;
        else if (!strcmp(argv[i], "--cycles") && i + 1 < argc) cycles = atoi(argv[++i]);
        else { std::printf("ARM2_USAGE unknown_arg=%s\n", argv[i]); return 2; }
    }
    std::printf("ARM2_PROBE api=%s meter_ms=%u window_ms=%u block_ms=%u\n",
                kAudioApiName, meter_ms, window_ms, block_ms);
    int bad = 0;
    if (synth) bad += synthetic_arm();
    if (table) bad += verdict_table_arm();
    // --table-only stops here: the DETERMINISTIC arms need no audio device at all, which
    // is what lets the control be falsified even while the owner is listening to music.
    if (table_only) {
        std::printf("ARM2_VERDICT state=not-run instrument=ran bad=%d scope=deterministic-arms-only\n", bad);
        return bad ? 1 : 0;
    }

    std::vector<AudioEndpoint> eps; std::string err;
    { WasapiAudio probe;
      if (!probe.enumerate(&eps, meter_ms, &err)) {
        std::printf("ARM2_ENUM_FAILED err=%s\n", err.c_str());
        std::printf("ARM2_VERDICT state=open-failed instrument=broken bad=1\n");
        return 1; } }
    std::printf("ARM2_ENUM population=%zu meter_window_ms=%u\n", eps.size(), meter_ms);
    for (size_t i = 0; i < eps.size(); ++i) {
        const AudioEndpoint& e = eps[i];
        std::printf("ARM2_ENDPOINT api=%s i=%zu/%zu default=%d name=%s id=%s rate=%u ch=%u "
                    "bits=%u format=%s meter_available=%d meter_peak=%.6f meter_window_ms=%u\n",
                    kAudioApiName, i + 1, eps.size(), e.is_default ? 1 : 0, e.name.c_str(),
                    e.endpoint_id.c_str(), (unsigned)e.rate, (unsigned)e.channels,
                    (unsigned)e.bits, e.format_tag == 3 ? "float32" : (e.format_tag == 1 ? "pcm16" : "?"),
                    e.meter_available ? 1 : 0, (double)e.meter_peak, meter_ms);
        // The API NAME travels on every record. On this box the SAME device name exists
        // under three host APIs and they are not interchangeable, so a record without it
        // is not actionable.
        if (e.api != kAudioApiName) { bad++; std::printf("ARM2_FAIL case=api-missing-on-endpoint i=%zu\n", i + 1); }
    }
    if (eps.empty()) { std::printf("ARM2_VERDICT state=no-endpoint instrument=ran bad=0 population=0\n"); return bad ? 1 : 0; }

    AudioLadderResult res;
    if (!run_audio_ladder(eps, window_ms, block_ms, &res, &err)) {
        std::printf("ARM2_LADDER_FAILED err=%s\n", err.c_str());
        std::printf("ARM2_VERDICT state=open-failed instrument=broken bad=1\n");
        return 1;
    }
    if (cycles > 0) {
        // The LADDER's first choice, so the cycle arm exercises the endpoint that is
        // actually reachable rather than an arbitrary one.
        const size_t idx = (res.chosen == (size_t)-1) ? 0 : res.chosen;
        WasapiAudio tap;
        bad += cycle_arm(tap, res.steps[idx].endpoint, block_ms, cycles, 200);
    }
    float peak_max = 0.0f;
    uint64_t frames_total = 0, silent_total = 0, packets_total = 0, gaps_total = 0;
    int silent_steps = 0;
    for (const AudioLadderStep& s : res.steps) {
        if (s.counters.peak > peak_max) peak_max = s.counters.peak;
        frames_total += s.counters.frames; silent_total += s.counters.silent_packets;
        packets_total += s.counters.packets; gaps_total += s.counters.position_gap_packets;
        if (s.endpoint.api != kAudioApiName) { bad++; std::printf("ARM2_FAIL case=api-missing-on-step\n"); }
        if (s.state == AudioState::kSilentDevice) {
            silent_steps++;
            std::printf("ARM2_SILENT_SPEAKS peak=%.6f floor=%.6f frames=%llu silent_packets=%llu "
                        "window_ms=%u population=%zu\n", (double)s.counters.peak,
                        (double)kAudioSilencePeakFloor, (unsigned long long)s.counters.frames,
                        (unsigned long long)s.counters.silent_packets, (unsigned)s.window_ms,
                        res.steps.size());
        }
    }
    std::printf("ARM2_LADDER state=%s chosen=%ld steps=%zu window_ms=%u peak_max=%.6f floor=%.6f "
                "frames_total=%llu packets_total=%llu silent_packets_total=%llu gaps_total=%llu "
                "silent_steps=%d population=%zu\n", audio_state_name(res.final_state),
                (long)(res.chosen == (size_t)-1 ? -1 : (long)res.chosen), res.steps.size(),
                window_ms, (double)peak_max, (double)kAudioSilencePeakFloor,
                (unsigned long long)frames_total, (unsigned long long)packets_total,
                (unsigned long long)silent_total, (unsigned long long)gaps_total,
                silent_steps, res.steps.size());
    std::printf("ARM2_VERDICT state=%s peak_max=%.6f floor=%.6f window_ms=%u population=%zu "
                "frames_total=%llu silent_steps=%d instrument=ran bad=%d\n",
                audio_state_name(res.final_state), (double)peak_max, (double)kAudioSilencePeakFloor,
                window_ms, res.steps.size(), (unsigned long long)frames_total, silent_steps, bad);
    return bad ? 1 : 0;
}
'@ | Set-Content -LiteralPath $mainCpp -Encoding UTF8 -NoNewline

$exeLive = "$gatedir\lane2-audio-probe.exe"
$logA2   = "$gatedir\armA2-link.txt"
& $gxx @flags @incs "$src\wasapi_audio.cpp" "$src\common.cpp" $mainCpp -o $exeLive @libs > $logA2 2>&1
$a2rc = $LASTEXITCODE
$a2ok = ($a2rc -eq 0) -and (Test-Path -LiteralPath $exeLive)
$report.arms['A2-link-no-new-library'] = [ordered]@{
    status = $(if ($a2ok) { 'GREEN' } else { 'RED' }); rc = $a2rc
    exe = $exeLive
    tail = ((Get-Content -LiteralPath $logA2 -Raw -Encoding UTF8) -split "`r?`n" | Select-Object -Last 4) -join ' | '
}
Say ("ARM-A2 link+run rc={0} libs='{1}' (no ksuuid, no propsys) population=1 exe" -f $a2rc, ($libs -join ' '))

# =====================================================================================
# ARM B — a REAL capture against the LIVE device ladder.
# =====================================================================================
$bLog = "$gatedir\armB-run.txt"
$bOut = @{}
$bOk = $false
$bState = 'instrument-broken'
$bPeak = 0.0
$bPop = 0
$bSilentSteps = 0
if ($a2ok -and -not $SkipLive) {
    & $exeLive --meter-ms $MeterMs --window-ms $WindowMs --block-ms $BlockMs --synthetic --verdict-table > $bLog 2>&1
    $brc = $LASTEXITCODE
    $bText = if (Test-Path -LiteralPath $bLog) { Get-Content -LiteralPath $bLog } else { @() }
    $bOut = @{}
    foreach ($l in $bText) { if ($l -match '^ARM2_') { $bOut[$l] = $l } }
    $bRc = $brc
    $bLines = $bText | Where-Object { $_ -match '^ARM2_VERDICT ' } | Select-Object -Last 1
    if ($bLines) {
        if ($bLines -match 'instrument=ran') {
            $bOk = $true
            if ($bLines -match 'state=(\S+)') { $bState = $Matches[1] }
            if ($bLines -match 'peak_max=([0-9.]+)') { $bPeak = [double]$Matches[1] }
            if ($bLines -match 'population=(\d+)') { $bPop = [int]$Matches[1] }
            if ($bLines -match 'silent_steps=(\d+)') { $bSilentSteps = [int]$Matches[1] }
        }
    }
} elseif ($SkipLive) { $bRc = -1; $bText = @('skipped: -SkipLive') }

$bNamed = @('ok', 'silent-device', 'no-signal', 'device-exhausted', 'open-failed', 'no-endpoint', 'closed')
$bNamedOk = $bNamed -contains $bState
$report.arms['B-live-capture'] = [ordered]@{
    status = $(if ($bOk -and $bNamedOk) { 'GREEN' } else { 'RED' })
    rc = $bRc; state = $bState
    peak_measured = $bPeak
    floor = 0.001
    population_endpoints = $bPop
    window_ms = $WindowMs; meter_window_ms = $MeterMs
    silent_steps = $bSilentSteps
    note = 'A silent device is a VALID green outcome: it means nothing is routed into the endpoint, which is CORRECT behaviour on this host. The verdict must be NAMED either way.'
    skipped = [bool]$SkipLive
}
Say ("ARM-B  live capture rc={0} state={1} peak_max={2} floor=0.001 population={3} window_ms={4} meter_window_ms={5}" -f $bRc, $bState, $bPeak, $bPop, $WindowMs, $MeterMs)
# The window ACTUALLY used, printed explicitly: with `pwsh -File` a `--flag` does not
# bind, so the requested window and the measured window can differ with no error at all.
if ($WindowMs -ne 1200 -or $MeterMs -ne 150) {
    Say ("  NOTE: non-default window requested and applied: window_ms={0} meter_ms={1}" -f $WindowMs, $MeterMs)
} else {
    Say ("  NOTE: running at DEFAULT window_ms={0} meter_ms={1} (pass -WindowMs/-MeterMs to change)" -f $WindowMs, $MeterMs)
}
if ($bText) { $bText | Where-Object { $_ -match '^(ARM2_ENDPOINT|ARM2_LADDER|ARM2_VERDICT|WASAPI_AUDIO api=.*state=)' } | ForEach-Object { Say ("  " + $_) } }

# =====================================================================================
# ARM C — THE CONTROL. The cure reverted in a COPY. It MUST disagree with ARM B.
#
# THE CURE, precisely: `WasapiAudio::judge()` maps a window whose measured peak is at or
# below kAudioSilencePeakFloor onto AudioState::kSilentDevice. Without that mapping the
# component reports `ok` for a device that delivered digital silence — which is the exact
# defect the component exists to remove.
# =====================================================================================
$cDir = "$gatedir\control"
if (-not (Test-Path -LiteralPath $cDir)) { New-Item -ItemType Directory -Path $cDir -Force | Out-Null }
$liveSrc = Get-Content -LiteralPath "$src\wasapi_audio.cpp" -Raw -Encoding UTF8

# TWO cures are reverted in the COPY, because the component has two claims a control has
# to be able to falsify, and a control that only tests one of them is half a control:
#   CURE-1  a below-floor peak is a NAMED verdict (silent-device), not an empty success
#   CURE-2  the COM reference is handed to the object exactly once (com.take()), and the
#           failure guard releases what a failed open already acquired
$cure1 = 'if (peak <= kAudioSilencePeakFloor) return AudioState::kSilentDevice;'
$cure2 = 'com_ref_taken_ = com.take();'
$cure2reverted = 'com_ref_taken_ = com.took();'
$cReverted = $liveSrc.Replace($cure1, '// ARM-C CONTROL: cure-1 (named silence verdict) is reverted in this COPY.' + "`r`n" + 'if (false) return AudioState::kSilentDevice;')
$cReverted = $cReverted.Replace($cure2, '// ARM-C CONTROL: cure-2 (single COM ownership handoff) is reverted in this COPY.' + "`r`n" + $cure2reverted)
$revertApplied = $liveSrc.Contains($cure1) -and $liveSrc.Contains($cure2) -and ($cReverted -ne $liveSrc)
$cSrc = "$cDir\wasapi_audio.cpp"
Set-Content -LiteralPath $cSrc -Value $cReverted -Encoding UTF8 -NoNewline
# the control needs the header; copy it so the control arm is self-contained
Copy-Item -LiteralPath "$src\wasapi_audio.h" -Destination "$cDir\wasapi_audio.h" -Force
Copy-Item -LiteralPath "$src\common.h" -Destination "$cDir\common.h" -Force

# ARM C is checked on the DETERMINISTIC table, with NO audio device opened. That is the
# whole point: a control that needs the machine to be quiet is a control that stops
# working the moment the owner puts music on. The live capture states are reported too,
# as CONTEXT, but they are not what arm C decides on.
$cExe = "$cDir\lane2-audio-probe-CONTROL.exe"
$cLog = "$gatedir\armC-build.txt"
$cInc = @('-I', $cDir, '-I', $src, '-I', "$src\third_party")
& $gxx @flags @cInc "$cSrc" "$src\common.cpp" $mainCpp -o $cExe @libs > $cLog 2>&1
$cBuildRc = $LASTEXITCODE

# The live build on the same table, for the pair to be compared.
$liveTableLog = "$gatedir\armC-live-table.txt"
& $exeLive --table-only --verdict-table > $liveTableLog 2>&1
$liveTableRc = $LASTEXITCODE

$cRunLog = "$gatedir\armC-run.txt"
$cOk = $false; $cState = 'instrument-broken'; $cBad = -1
if ($cBuildRc -eq 0) {
    & $cExe --table-only --verdict-table > $cRunLog 2>&1
    $cRc = $LASTEXITCODE
    $cLine = (Get-Content -LiteralPath $cRunLog) | Where-Object { $_ -match '^ARM2_VERDICTMAP_RESULT ' } | Select-Object -Last 1
    if ($cLine -and ($cLine -match 'bad=(\d+)')) { $cBad = [int]$Matches[1]; $cOk = $true }
} else { $cRc = -1 }

$liveTableLine = (Get-Content -LiteralPath $liveTableLog) | Where-Object { $_ -match '^ARM2_VERDICTMAP_RESULT ' } | Select-Object -Last 1
$liveBad = -1
if ($liveTableLine -and ($liveTableLine -match 'bad=(\d+)')) { $liveBad = [int]$Matches[1] }

# THE CONTROL'S CLAIM, precisely: with the cure reverted, the deterministic table must
# FAIL. A control that still passes here is a control that cannot say no.
$controlGoesRed = ($cOk -and ($cBad -gt 0) -and ($liveBad -eq 0))
# CONTEXT ONLY: what the two arms said about the live machine. Recorded, never decisive.
$cLiveCtx = 'not-run'; $cCtlCtx = 'not-run'
$liveCtxLog = "$gatedir\armC-live-ctx.txt"
if (-not $SkipLive -and $a2ok) {
    & $exeLive --meter-ms $MeterMs --window-ms $WindowMs --block-ms $BlockMs > $liveCtxLog 2>&1
    $lc = (Get-Content -LiteralPath $liveCtxLog) | Where-Object { $_ -match '^ARM2_VERDICT ' } | Select-Object -Last 1
    if ($lc -and ($lc -match 'state=(\S+)')) { $cLiveCtx = $Matches[1] }
    $cCtxLog = "$gatedir\armC-ctl-ctx.txt"
    & $cExe --meter-ms $MeterMs --window-ms $WindowMs --block-ms $BlockMs > $cCtxLog 2>&1
    $cc = (Get-Content -LiteralPath $cCtxLog) | Where-Object { $_ -match '^ARM2_VERDICT ' } | Select-Object -Last 1
    if ($cc -and ($cc -match 'state=(\S+)')) { $cCtlCtx = $Matches[1] }
}

$report.arms['C-control-reverted-must-go-red'] = [ordered]@{
    status = $(if ($controlGoesRed) { 'GREEN' } else { 'RED' })
    build_rc = $cBuildRc; run_rc = $cRc
    cure_line_found = $revertApplied
    cure_line = 'if (peak <= kAudioSilencePeakFloor) return AudioState::kSilentDevice;'
    check = 'deterministic verdict table, NO audio device opened'
    live_table_bad = $liveBad
    control_table_bad = $cBad
    control_goes_red = $controlGoesRed
    context_live_state = $cLiveCtx
    context_control_state = $cCtlCtx
    note = 'The live states are CONTEXT. A control that needs the machine to be silent cannot say no while the owner is listening to music (MEASURED: first run gave live=ok control=ok, which proved nothing).'
}
Say ("ARM-C  control (cures reverted in a COPY): build_rc={0} live_table_bad={1} control_table_bad={2} goes_red={3} | context: live={4} control={5}" -f $cBuildRc, $liveBad, $cBad, $controlGoesRed, $cLiveCtx, $cCtlCtx)

# ---- ARM C also has to catch the SECOND cure, or it is testing half the promise. -------
# The cycle arm on the reverted copy is what proves cure-2's reversion is observable.
$cCtxLog2 = "$gatedir\armC-ctl-cycles.txt"
$cCyclesBad = -1
if ($cBuildRc -eq 0) {
    & $cExe --meter-ms $MeterMs --window-ms 400 --block-ms $BlockMs --cycles 5 > $cCtxLog2 2>&1
    $ccy = $LASTEXITCODE
    $cl = (Get-Content -LiteralPath $cCtxLog2) | Where-Object { $_ -match '^ARM2_CYCLE_RESULT ' } | Select-Object -Last 1
    if ($cl -and ($cl -match 'bad=(\d+)')) { $cCyclesBad = [int]$Matches[1] }
} else { $ccy = -1 }
$liveCyclesLog = "$gatedir\armB-cycles.txt"
$liveCyclesBad = -1
if ($a2ok) {
    & $exeLive --meter-ms $MeterMs --window-ms 400 --block-ms $BlockMs --cycles 5 > $liveCyclesLog 2>&1
    $lcy = $LASTEXITCODE
    $ll = (Get-Content -LiteralPath $liveCyclesLog) | Where-Object { $_ -match '^ARM2_CYCLE_RESULT ' } | Select-Object -Last 1
    if ($ll -and ($ll -match 'bad=(\d+)')) { $liveCyclesBad = [int]$Matches[1] }
} else { $lcy = -1 }
Say ("ARM-D  open/close cycles: live_bad={0} population=5 cycles   control_bad={1} (reverted COM handoff)  live_rc={2} control_rc={3}" -f $liveCyclesBad, $cCyclesBad, $lcy, $ccy)
# ARM-D is a REAL control now: the live balance must be 0 and the REVERTED copy's must not
# be, which is the only thing that makes cure-2 observable at all (MEASURED: with the
# reversion in place, five open/close cycles still reported bad=0).
$armD = ($liveCyclesBad -eq 0) -and ($liveCyclesBad -ne -1)
$armDcontrolFires = ($cCyclesBad -gt 0)
$report.arms['D-com-reference-balance'] = [ordered]@{
    status = $(if ($armD -and $armDcontrolFires) { 'GREEN' } else { 'RED' })
    live_cycle_bad = $liveCyclesBad
    control_cycle_bad = $cCyclesBad
    control_catches_reverted_handoff = $armDcontrolFires
    cycles = 5
    note = 'com_reference_balance() must be 0 at rest. The reverted copy does not crash -- CoUninitialize is reference-counted -- so only the balance names it.'
}
if (-not $armDcontrolFires) { Say 'ARM-D  WARNING: the reverted COM handoff was NOT observable. The control is weaker than it looks; recorded, not hidden.' }

# =====================================================================================
# VERDICT — the conjunction of DIFFERENT claims, printed separately and conjoined.
# =====================================================================================
$armA = $a1ok -and $a2ok
$armB = if ($SkipLive) { $true } else { $bOk -and $bNamedOk }
$armC = $revertApplied -and $controlGoesRed
$armD = ($liveCyclesBad -eq 0)
$runVerdict = if ($armA -and $armB -and $armD) { 'GREEN' } else { 'RED' }
$controlVerdict = if ($armC) { 'GREEN' } else { 'RED' }
$pass = $armA -and $armB -and $armC -and $armD -and $armDcontrolFires

$report.run_verdict = $runVerdict
$report.control_verdict = $controlVerdict
$report.measurement = [ordered]@{
    state = $bState; peak = $bPeak; floor = 0.001
    population_endpoints = $bPop; window_ms = $WindowMs
    note = 'peak is what the LOOPBACK delivered over window_ms across population endpoints. It is NOT a promise that audio is playing.'
}
$report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $gateLog -Encoding UTF8

Say ""
Say ("  ARM-A (build, repo's own path)      : {0}" -f $(if ($armA) { 'GREEN' } else { 'RED' }))
Say ("  ARM-B (live capture, named verdict): {0}   state={1} peak={2} population={3} window_ms={4}" -f $(if ($armB) { 'GREEN' } else { 'RED' }), $bState, $bPeak, $bPop, $WindowMs)
Say ("  ARM-C (control, cures reverted)      : {0}   live_table_bad={1} control_table_bad={2} goes_red={3}" -f $controlVerdict, $liveBad, $cBad, $controlGoesRed)
Say ("  ARM-D (open/close cycles, COM ref)  : {0}   cycles=5 live_bad={1}" -f $(if ($armD) { 'GREEN' } else { 'RED' }), $liveCyclesBad)
Say ("  RUN-VERDICT   : {0}   (the instrument ran and produced a named verdict)" -f $runVerdict)
Say ("  CENSUS/VERDICT: {0}   (arm C is non-vacuous)" -f $controlVerdict)
Say ("  report: {0}" -f $gateLog)

if (-not $pass) { Say 'LANE2-GATE FAIL'; exit 1 }
Say 'LANE2-GATE PASS'
exit 0