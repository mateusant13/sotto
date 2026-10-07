# 01 — D3D11 → NVENC → replay buffer → clip (Windows, 2026)

**Question:** what do we build so the clip is already written when the key is pressed and no frame is lost?
**Scope: this question only.** ASR/OCR/index/UI are deliberately absent.
`MEASURED` = a command on this box produced it · `READ` = vendor doc, URL given · `UNKNOWN` = nobody has shown it.
Host: Windows 11 Pro 10.0.26200 · i5-13600K · RTX 5080, driver **32.0.16.1714 / 617.14** · Intel UHD 770 also present.

---

## 1. Capture API — Windows Graphics Capture (WGC)

**MEASURED** — WGC is live here: `GraphicsCaptureSession.IsSupported()` → `True`; the frame pool exposes
`Create`, `CreateFreeThreaded`, `CreateCaptureSession`, `Recreate`, `TryGetNextFrame`.
**MEASURED — this decides the product** — `GraphicsCaptureItem` exposes **`TryCreateFromDisplayId`** and
**`TryCreateFromWindowId`**, so we capture a chosen monitor/window **programmatically**: no
`GraphicsCapturePicker`, no consent dialog in the steady state.
**READ** — frames are `Direct3D11CaptureFrame`; `frame.Surface` is an `ID3D11Texture2D` and
`frame.SystemRelativeTime` is **QPC** time — one clock shared with transcript/OCR.
<https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture>
**READ** — same page: on resize call `Recreate()`, and **"all existing frames are discarded"**; on HD-colour
systems the format is *not* necessarily `B8G8R8A8_UNORM` and the chain should carry `R16G16B16A16_FLOAT`,
or capture looks washed out.
**READ** — independent comparison ranks Graphics Capture first for compatibility/smoothness; Desktop
Duplication is worse and Win10-2004+ only:
<https://github.com/Blinue/Magpie/blob/main/docs/Comparison%20of%20capture%20methods.md>
**READ** — an extra reason to avoid Desktop Duplication: *"calling DXGI APIs like
`IDXGIOutputDuplication::AcquireNextFrame` from the primary thread and
`NvEncLockBitstream`/`NvEncUnlockBitstream` from secondary thread can lead to suboptimal or undefined
behavior."* <https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/nvenc-video-encoder-api-prog-guide/index.html>

**Zero copy — where the copies actually are.** Three transfers exist and we own exactly one: (1) desktop →
the pool's `ID3D11Texture2D`, done by DWM/WGC, already paid to show the pixels; (2) **BGRA8 (or FP16) →
NV12/YUV — ours, the only GPU cost we own**; (3) texture → NVENC as a registered resource, zero.
**READ** — #3 has no CPU copy: `NvEncRegisterResource` → `NvEncMapInputResource` →
`NV_ENC_PIC_PARAMS::inputBuffer`, and `NV_ENC_REGISTER_RESOURCE` accepts DirectX resources (ProgGuide §4.1.2).
**READ** — NVENC natively ingests YUV/RGB, so #2 is a format-support question, not a copy question
(ProgGuide §1, §3.5 `NV_ENC_BUFFER_FORMAT`). **MEASURED** — transfer #3 is not just documented: a **1920×1080 NV12 texture registers and maps** on this
driver (sibling lane's C++ probe, §3), so **the zero-copy input path is verified end-to-end.** **UNKNOWN** —
the µs cost of #2 at 1080p60/4K60, and whether an NVENC-supported input format deletes it. **That is the
project's first benchmark.** CPU keeps no per-frame pixel work; it pays only ring memcpy (~83 KB/frame at
1080p60/40 Mbps) and the watchdogs.

## 2. Ring buffer — **encoded-bitrate ring in RAM**, keyframe-bookmarked

**Pick RAM. Segment files on scratch disk are demoted to a crash/TDR safety net, not the hotkey path** — the
hotkey must be a pointer flip, not a seek plus concat, and must not depend on a filesystem a game or AV
scanner can stall. **READ** — OBS ships this default (*"keeps the last part of your recording in memory"*,
*"Currently, Replay Buffer is RAM-only"*), and the disk variant is an **open pull request** opened
2026-06-15, still open — not the status quo that won:
<https://obs-versions.com/community/pulls/13558> · <https://obs-versions.com/blog/obs-replay-buffer>.
That PR keeps encoded **packets** in a circular *file* and reads back only on save: same data model.

**RAM for 120 s — arithmetic `bytes = Mbps × 10⁶ × 120 ÷ 8`** (MEASURED, receipt): 1080p60 @40 Mbps →
**572 MiB (0.56 GiB)**, 83 333 B/frame · @80 Mbps → 1 144 MiB (1.12 GiB). 4K60 @100 Mbps → **1 431 MiB
(1.40 GiB)**, 208 333 B/frame · @150 Mbps → 2 146 MiB (2.10 GiB) · @200 Mbps → 2 861 MiB (2.79 GiB).
The **bitrates** are the soft input: 40 Mbps is credible for 1080p60 game content, 100 Mbps is low for 4K60
(150–200 is what you pick for a clean archive). Budget **peak = 1.5× nominal**. **UNKNOWN: the real average
bitrate of the owner's content** — size the ring from a *measured* encode, not this table.

**The keyframe-aligned cut comes from forcing the boundary, not searching for it.** **READ** —
`NV_ENC_PIC_PARAMS::encodePicFlags = NV_ENC_PIC_FLAG_FORCEIDR` forces an **IDR** frame
(`NV_ENC_PIC_FLAG_FORCEINTRA` forces intra; ProgGuide §4.2.1, §4.2.3), and *"By default, SPS/PPS … will be
attached to every IDR frame"* (ProgGuide §3.9), so a forced IDR is also a self-describing decoder start
point with no side channel. **Design:** fixed GOP, one forced IDR every 2 s; cut = **nearest IDR ≥
(hotkey − 120 s)** — ≤ 2 s pre-roll, deterministic. Honest cost: frequent IDRs spend bitrate; if the
measured average runs high, lengthen the cadence — same index either way. **Shape:** fixed slots, monotonic
frame sequence, parallel index `(seq, idr, pts, offset, size)`; on wrap, overwrite oldest but **never evict
entries before the oldest IDR still held** — that is what keeps a 120 s window always cuttable.
`NV_ENC_LOCK_BITSTREAM::pictureType` (ProgGuide §6.1) records what the encoder really produced.

## 3. Encoder API — **NVENC via the Video Codec SDK**, not FFmpeg's wrapper

**Pick the SDK**: we need `NvEncRegisterResource`/`NvEncMapInputResource` to feed the WGC texture directly;
FFmpeg's `nvenc` wrapper forces a copy into its own D3D11 pool or a fight with `AV_PIX_FMT_D3D11` plumbing.
**MEASURED** — `nvEncodeAPI64.dll` exports `NvEncodeAPIGetMaxSupportedVersion` and returns status 0,
**`0xD1` = API 13.1** (`_main\nvenc-caps-probe.py`): driver 617.14 speaks SDK 13.1, so compile against that
header. **READ** — NVENCODE API *"guarantees binary backward compatibility"* (ProgGuide §1). **READ** —
tuning: **Low latency + CBR** for streaming/cloud-gaming, **P1→P7** trade quality for speed, and
**asynchronous mode** (`enableEncodeAsync = 1`, separate output thread) is NVIDIA's recommendation
(§3.3, §6.1, §6.3). **READ** — 2-pass, lookahead and adaptive quantisation internally use CUDA, so "NVENC
costs zero CUDA time" is false while they are on (§6.4). **READ** — Blackwell throughput, H.264 1080p per
NVENC engine: **977 fps @ P1/CBR/LL**, 323 fps @ P5; HEVC P1 1134 fps (SDK 13.0 Application Note §4) — at
60 fps that is ~6% of one engine, so encoding is not the bottleneck. **MEASURED** — three DXGI adapters:
`NVIDIA GeForce RTX 5080` index 0 `vendor 0x10DE` `device 0x2C02`, `Intel UHD 770` index 1 `0x8086`,
`Microsoft Basic Render Driver` index 2 `0x1414` (device creation fails). **MEASURED — CORRECTED
2026-10-08:** `D3D11CreateDevice(NULL, D3D_DRIVER_TYPE_HARDWARE, …)` returns **`hr=0` and lands on the
NVIDIA adapter** (`_main\check-default-adapter.ps1`, via `IDXGIDevice::GetAdapter` — measured, not inferred).
Feature level `0xB000` printed for *every* adapter is `D3D_FEATURE_LEVEL_11_0` and **says nothing about
vendor**; the first draft of this doc read a vendor fact out of a feature level. The practice still stands —
on hybrid/docked machines generally, not on evidence from this one: enumerate DXGI, match
`VendorId == 0x10DE`, create on that adapter explicitly.

**A user WITHOUT an NVIDIA GPU gets the same product one rung down.** AMD → AMF, Intel → Quick Sync (the UHD
770 here is one), neither → x264/x265 on CPU. Capture and ring code do not change; only the encoder block is
swapped. The rule that makes it real: one encoder interface, three implementations, a capability probe at
start-up, and a **self-test that refuses to arm the hotkey if no encoder initialised** — tell the user, never
hand them a ring that never fills. **UNKNOWN:** AMF/QSV throughput and quality at 4K60 on a CPU-only box
(law 5); no non-NVIDIA machine was measured here.

**MEASURED — CORRECTED 2026-10-08: the "no NVENC session" result was MY INSTRUMENT, not this machine.**
My ctypes probe reported `NvEncodeAPICreateInstance` → status 0 and then **status 5** from every
`NvEncOpenEncodeSessionEx`, in three configurations (CUDA with a real driver context handle via
`cuCtxCreate_v2`; `NV_ENC_DEVICE_TYPE_DIRECTX` with an `ID3D11Device` on adapter 0, the RTX 5080; and the
same on adapter 1) — saved in `_main\nvenc-caps-out-cuda.json`, `_main\nvenc-caps-out-directx.json`. **That
was a defect in my hand-built ctypes parameter block, and it has been REFUTED**: a sibling lane's C++
probe compiled against the real SDK headers takes **both `NV_ENC_DEVICE_TYPE_CUDA` and
`NV_ENC_DEVICE_TYPE_DIRECTX` to `NvEncInitializeEncoder` = 0**. (It also confirms my §3 reading, from the
same driver's header: header 313554 B, sha256 `8776FDDCB8FEBC6AEC4D73989B1F21831EB30306BC583DA55B4BF0C14A1DC228`.)
So **"this machine will not open an NVENC session" is false and must not be quoted** — but the numbers below
are still second-hand and are marked as such, not folded into my own measurements.

**MEASURED (sibling lane, C++ probe — attribution second-hand, not re-run here):**
`NV_ENC_CAPS_NUM_ENCODER_ENGINES` = **2** for H.264, HEVC and AV1; H.264 up to **4096×4096**, HEVC/AV1 up to
**8192×8192**; and a **1920×1080 NV12 texture registers AND maps** — i.e. **the zero-copy input path is
verified end-to-end**, which is the strongest single upgrade in this document (it was an open question in §1).
**Still UNKNOWN:** the driver's concurrent-session REFUSAL point (the §4 "8" remains NVIDIA policy, not a
measurement here) and the BGRA8/FP16 → NV12 conversion cost.

## 4. The failure modes that lose frames

**(a) Encoder session limits.** **READ** — `NvEncOpenEncodeSessionEx` *"will return
NV_ENC_ERR_OUT_OF_MEMORY if … encode session limit (on current devices limited to 8) is exceeded"*
(<https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/pdf/NVENC_VideoEncoder_API_ProgGuide.pdf>).
**READ** — Application Note §3: on **non-qualified (GeForce) GPUs, 8 concurrent encode sessions per
system**, counting all non-qualified cards combined; qualified GPUs are resource-limited
(<https://docs.nvidia.com/video-technologies/video-codec-sdk/13.0/nvenc-application-note/index.html>).
**Survive:** exactly **one** long-lived session per recording (we hold one of the eight and never race for a
new one); a typed, loud start-up failure instead of arming the hotkey; and a watchdog that records a failed
encode as a **dropped-frame counter**, so a clip says "3 frames missing" rather than shipping a silent stutter.

**(b) Resolution / DPI / monitor change — the mode this design must earn its way through.** `Recreate`
**discards all pending frames** (MS Learn, §1). **Survive:** treat it as an **encoder reconfiguration, not a
restart** — on `Recreate`, force an IDR, start a **new ring segment** at that boundary, and let the old
segment end at its last complete frame. That is why the index stores per-segment SPS/PPS and why the cut
rule is "nearest IDR", not "byte offset". Bounded cost: **≤ 2 frames lost**; count and report them, never
claim zero.

**(c) Protected content / DRM / exclusive fullscreen.** **UNKNOWN** — WGC behaviour on protected surfaces
and exclusive-fullscreen games on build 26200 was **not measured**. **Survive:** a **frame-liveness
watchdog** (not a count check — a paused game legitimately sends nothing), fall back from the window item to
the **monitor** item, and if that also yields nothing, say so and stop claiming to record. A black clip is
worse than an error.

**(d) The yellow border — a design input, not cosmetics.** **MEASURED** — `IsBorderRequired` and
`GraphicsCaptureAccessKind = {Borderless, Programmatic}` exist here. **READ** — the border comes off only
after `RequestAccessAsync(Borderless)`, which **shows a prompt** and needs the
**`graphicsCaptureWithoutBorder`** manifest capability; if the user denies, `IsBorderRequired = false` is
*silently ignored*; and *"if `IsBorderRequired` … is set to `true` … by other apps, the border will be
displayed"* — a second capture app can force it back:
<https://learn.microsoft.com/en-us/uwp/api/windows.graphics.capture.graphicscapturesession.isborderrequired>.
**Consequence:** a borderless recorder is a **packaged app with a manifest capability and a one-time
prompt**; a plain Win32 exe cannot be borderless. That decides the shipping form and must be settled before
the UI.

**(e) HDR.** Captured format follows the display's HD-colour state, not our preference (**READ**, §1). Either
keep FP16 end-to-end and let NVENC encode 10-bit (MV-HEVC/AV1 10-bit are supported on Blackwell — **READ**,
Application Note §2), or tone-map to SDR explicitly once. **Do not** feed FP16 data into a BGRA8 pipeline —
that is the "washed out" failure MS names. **UNKNOWN:** whether this driver accepts FP16 as an NVENC input
format or needs our conversion (the same benchmark as §1 #2).

## Measure before this becomes a spec

1. ~~NVENC session open from real SDK headers in C++~~ — **DONE (sibling lane's C++ probe): 2 encoder
   engines, 4096×4096 H.264 / 8192×8192 HEVC-AV1, NV12 texture registers and maps.** Remaining piece of
   this item: the driver's concurrent-session **refusal** point, still unmeasured.
2. **BGRA/FP16 → NV12** cost at 1080p60 and 4K60, and whether a native NVENC input format removes it.
3. The **measured average bitrate** of the owner's real content at the chosen preset, so §2's RAM stops being
   a table and becomes a default.
4. WGC on **protected content** and **exclusive fullscreen** — the one failure mode this lane could not
   measure at all.
