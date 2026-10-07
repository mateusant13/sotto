# SPEC 03 — D3D11 → NVENC → REPLAY RING → `clip.mp4`

**Status: IMPLEMENTED AND MEASURED on this box 2026-10-08** — see
`receipts/receipt-03-capture-impl.md` for the numbers this spec's decisions produced.
This is the component `AGENTS.md` names as **the one thing to prototype first**
(*"D3D11 → NVENC → replay buffer → clip, with no frame loss"*).

**One environmental limit belongs in the status line, not in a footnote:** the live WGC capture arm
became unrunnable between **11:24:37 and 11:26:32** on this box (`CreateForWindow` → `E_ACCESSDENIED`
for *every* window and for the monitor, while `GraphicsCaptureSession::IsSupported` still returns true
and the OS consent store still says `Allow`). The measurements in the receipt were taken before that,
and the **cut path was re-proven afterwards without WGC** (`--cut-from-h264`, receipt §5c) precisely
so that one broken component cannot take the whole proof with it. **The documented recovery,
`GraphicsCaptureAccess::RequestAccessAsync(Programmatic)`, was called and does NOT restore access** —
so the block is not a per-app consent denial. Details, the refuted TDR hypothesis, and the two-line
human action: receipt §7.

`MEASURED` = a command on this box produced it · `READ` = vendor/other doc, URL given · `UNKNOWN` = nobody
has shown it. Host: Win11 26200 · i5-13600K (14C/20T) · RTX 5080 `0x2C02` · Intel UHD 770 `0x8086` ·
driver 617.14 / `nvEncodeAPI64.dll` 32.0.16.1714.

---

## 1. THE MEASURED FACTS THIS SPEC IS BUILT ON (not re-litigated here)

All from `docs/research/03-nvenc-sessions.md` (C++ probe, real SDK headers) and
`docs/research/01-capture-encode.md`, plus `_main/nvenc-probe-out.txt` verbatim:

| fact | value | consequence in this spec |
|---|---|---|
| `NvEncodeAPIGetMaxSupportedVersion` | `0xD1` (13.1), status 0 | compile against `nv-codec-headers` 13.1 |
| `NvEncOpenEncodeSessionEx` CUDA / DIRECTX | **status 0** both | the "status 5" story was a probe defect; **this box never refused NVENC** |
| `NV_ENC_CAPS_NUM_ENCODER_ENGINES` | **2** (H.264, HEVC, AV1) | never hard-code an engine count |
| H.264 max / HEVC-AV1 max | **4096×4096** / **8192×8192** | H.264 is enough for 1080p and 1440p; 4K on H.264 is at the wall |
| 1920×1080 NV12 D3D11 texture | **registers AND maps** (`NvEncRegisterResource`→0, `NvEncMapInputResource`→0) | the **zero-copy input path is the shipping path** |
| concurrent sessions | **10 held, #11 refused with status 21** (`NV_ENC_ERR_INCOMPATIBLE_CLIENT_KEY`), not the documented `OUT_OF_MEMORY`; 1 session already live (another app) | classify refusal by **21**, never by the documented code; hold exactly **one** long-lived session |
| `tuningInfo = 0` (`UNDEFINED`) | **status 12** | always `NV_ENC_TUNING_INFO_LOW_LATENCY` (or HIGH_QUALITY); never a `memset(0)` value |
| a hand-built `NV_ENC_CONFIG` (even `version` only) | **status 8** + misleading `"Unsupported color format."` | **always** start from `nvEncGetEncodePresetConfigEx(P3, LOW_LATENCY)` and override |
| `NvEncGetEncodeCaps` on an opened-but-**un**initialised session | **SEGFAULT `0xC0000005`**, no error status | caps are only queried **after** `NvEncInitializeEncoder` succeeded |
| `NvEncRegisterResource` on an uninitialised session | status **5** (`DEVICE_NOT_EXIST`) | a bare status 5 is ambiguous unless session state is printed |
| default `D3D11CreateDevice(NULL, HARDWARE)` | **is** the RTX 5080 (`0x10DE`) on this run | vendor matching stays correct practice, it is not a trap here |
| toolchain | mingw-w64 **g++ 15.2.0**; **no MSVC, no CUDA toolkit** | `d3dcompiler_47.dll`, `nvEncodeAPI64.dll`, `nvcuda.dll` are bound at **run time** |

**WGC (Windows Graphics Capture) — MEASURED elsewhere in `01-capture-encode.md` §1:**
`IsSupported()` → True; `TryCreateFromDisplayId` / `TryCreateFromWindowId` exist, so a capture item is
built **programmatically, with no picker and no consent dialog**; `frame.Surface` is an
`ID3D11Texture2D` and `frame.SystemRelativeTime` is **QPC** — the clock the transcript and OCR must
share.

**Ring RAM arithmetic (law 7), `bytes = Mbps × 10⁶ × s ÷ 8`:** 1080p60 @45 Mbps × 120 s = **675 MB**;
@40 Mbps × 120 s = 572 MiB; 4K60 @200 Mbps × 120 s = 2 861 MiB. **The ring, not the AI, is the hog.**

---

## 2. DECISIONS

### 2.1 Capture: **WGC**, and the item is chosen, never picked

- The capture item is created with `IGraphicsCaptureItemInterop::CreateForWindow(hwnd, …)` (or
  `CreateForMonitor`), reached from the activation factory of
  `Windows.Graphics.Capture.GraphicsCaptureItem` via `RoGetActivationFactory`. **No
  `GraphicsCapturePicker`, therefore no dialog and no window on screen.**
- The frame pool is `IDirect3D11CaptureFramePoolStatics2::CreateFreeThreaded` — the capture callbacks
  never run on a UI thread, and the process has **no window at all** in the shipping path.
- Format requested: `B8G8R8A8UIntNormalized`. HDR/FP16 (`R16G16B16A16_FLOAT`) is **out of scope for
  the prototype** and is a named UNKNOWN in §6.
- On `Recreate` (resolution/DPI/monitor change) the design in `01-capture-encode.md` §4(b) applies:
  force an IDR, start a **new ring segment**, count and report the ≤2 frames lost. **The prototype
  does not yet implement `Recreate`** — see §6.

### 2.2 Device: **enumerate DXGI, match `VendorId == 0x10DE`, create on that adapter**

`D3D11CreateDevice(adapter, D3D_DRIVER_TYPE_UNKNOWN, …)`. The default-adapter path is *not* used even
though it happens to be NVIDIA here: on a hybrid/docked machine it is the wrong adapter, and the
NVENC session must be opened on the **same** `ID3D11Device` that owns the textures.

### 2.3 BGRA8 → NV12: **on the GPU, and it is the only pixel cost we own**

`01-capture-encode.md` §1 names three transfers; desktop→pool is DWM's (already paid), pool→NVENC is
zero-copy, and **the conversion is ours**. It is done with a full-screen-triangle pixel shader
compiled **at run time** from `d3dcompiler_47.dll` (`D3DCompile` — there is no `fxc` without MSVC), in
**two passes** into the two planes of a single `DXGI_FORMAT_NV12` texture:

- pass 1 → RTV `DXGI_FORMAT_R8_UNORM` (plane 0, luma);
- pass 2 → RTV `DXGI_FORMAT_R8G8_UNORM` (plane 1, interleaved Cb/Cr at half resolution).

Two passes and not MRT, because **D3D11 requires every RTV in an MRT set to have identical
dimensions** and the chroma plane is half-size. Colours: BT.709 limited range (studio swing), which is
what H.264 in an MP4 is expected to carry and what a decoder assumes by default.

The NV12 texture is created `D3D11_USAGE_DEFAULT`, `D3D11_BIND_RENDER_TARGET`, and is **registered
with NVENC once** (`NvEncRegisterResource`) and **mapped per frame** (`NvEncMapInputResource`), so the
encoded input never round-trips through system memory.

### 2.4 Encoder: **NVENC, H.264, preset P3, `LOW_LATENCY`, CBR**

- Session: `NV_ENC_DEVICE_TYPE_DIRECTX` + the `ID3D11Device` of §2.2.
- Config: **`nvEncGetEncodePresetConfigEx(H.264, P3, LOW_LATENCY)` first**, then override
  `gopLength`, `frameIntervalP = 1` (P-only, no B-frames ⇒ 1-in-1-out, bounded latency), and
  `rcParams` (CBR, `averageBitRate = maxBitRate = vbvBufferSize = vbvInitialDelay = bitrate`).
  **Never a hand-built config** — measured status 8.
- `frameRateNum/Den` from the active mode; `enablePTD = 1`; `enableEncodeAsync = 0` (the encoder runs
  on its own dedicated thread; an async queue would add a second, unaccounted buffer).
- Codec ladder for the shipping product is H.264 → HEVC → AV1 and then AMF/QSV/x264
  (`01-capture-encode.md` §3). **The prototype ships the H.264 NVENC arm only**, and the ladder's
  *shape* (probe, then fall through, then refuse) is what §5 implements.

### 2.5 Forced IDR every 2 s — the cut point is **forced, never searched**

`NV_ENC_PIC_PARAMS::encodePicFlags |= NV_ENC_PIC_FLAG_FORCEIDR` on every frame whose index is a
multiple of `fps × 2`. SPS/PPS ride every IDR by default, so a forced IDR is a self-describing decoder
start point. `NV_ENC_LOCK_BITSTREAM::pictureType` is read back and the IDR flag is taken from **what
the encoder really produced**, not from what we asked for.

`gopLength` is set to the same 2 s cadence so the encoder's own GOP grid coincides with the forced one.

**Honest cost:** frequent IDRs spend bitrate. At 2 s the pre-roll is ≤2 s; if the measured average
bitrate runs high, lengthen the cadence — the index shape does not change. Desktop mode uses 10 s per
`specs/01-capture-modes-and-scheduling.md` §1.

### 2.6 The ring: **encoded frames in RAM, byte-budgeted, keyframe-bookmarked**

- **RAM, not disk.** The hotkey must be a pointer flip, not a seek plus concat, and must not depend on
  a filesystem a game or an AV scanner can stall (`01-capture-encode.md` §2; OBS's replay buffer is
  RAM-only too).
- The ring is a **preallocated byte arena**. Each frame is appended at a monotonic offset with wrap;
  a parallel index holds `(seq, isIDR, qpc_ns, offset, size, pictureType)`. Nothing is `malloc`'d per
  frame, so the RAM cost is the arena and only the arena — which is what law 7 says to measure.
- **Eviction never takes the last IDR still held.** If evicting the oldest entry would leave the ring
  without an IDR, an IDR is forced immediately and the frames until it arrives are counted as dropped
  (they are the only frames this design can lose, and the counter says so).
- **Sizing (law 7 — "budgeted by measured hardware, not by taste"):** the mode's bitrate fixes the
  bytes-per-second; the mode fixes the nominal seconds; and a **cap derived from the adapter's
  `DedicatedVideoMemory`** (`clamp(VRAM_MB ÷ 16, 256 MiB, 2048 MiB)`) can shorten the seconds. The
  product **prints what it chose and why** on every start.

| mode | fps | bitrate @1080p | IDR grid | ring seconds | ring RAM @1080p |
|---|---|---|---|---|---|
| GAMING | 60 | 45 Mbps | 2 s | 120 | **675 MB** |
| DESKTOP | 30 | 8 Mbps | 10 s | 600 | **600 MB** |

Bitrate scales with pixels, not with a fixed number: GAMING ≈ **0.036 bpp**, DESKTOP ≈ **0.013 bpp**
(`specs/01` §1). **UNKNOWN: whether 0.036 bpp is the right knee for fast-motion content** — needs a
VMAF/SSIM sweep, not an impression.

### 2.7 The cut: **remux, never re-encode**

On the signal (hotkey), with `t_cut` = the QPC timestamp of the newest frame in the ring:

1. pick `i` = the **first entry with `isIDR` whose `qpc_ns ≥ t_cut − ring_seconds`** (i.e. the nearest
   forced IDR at or after the window's start — the spec's "nearest IDR ≥ hotkey − 120 s"); if no IDR
   satisfies it, the **oldest IDR held** is used and the shortfall is reported;
2. copy entries `i … last` straight out of the arena into `clip.mp4`, **without touching the encoder**;
3. report `frames_in_clip`, `clip_bytes`, `clip_seconds`, `idr_pre_roll_ms`, `wall_ms_to_write`.

**Container.** The ring holds what NVENC emitted, which is **Annex-B** (start codes). MP4 requires
**length-prefixed (AVCC)** NAL units plus an `avcC` record carrying SPS/PPS, so the cut performs a
start-code scan and a rewrite — a byte transform, **not** a decode. The muxer is a minimal streaming
ISO-BMFF writer (`ftyp` → streaming `mdat` → `moov` on close, with `avc1`/`avcC`, `stts`, `stss`,
`stsc`, `stsz`, `stco`/`co64`).

**Sample durations are the REAL inter-frame interval, quantised to a 1 ms grid that divides the media
timescale exactly** (`timescale/900` = 100 ticks at 90 000). Two measured reasons, and they point the
same way:

- Quantising to the **nominal** frame grid instead (an integer number of `1/fps`) **clamps the frame
  rate at the mode's fps**: the desktop arm's source ran at 54 fps against a declared 30 fps and the
  clip came out **1.8× slow motion** (649 frames in a 21.6 s container for 12.0 s of real time). A clip
  whose duration is not its duration is worse than a warning.
- A **common** grid that divides the timescale stops a reader which derives a coarse output timebase
  from the frame durations (ffmpeg's `-f null` does exactly that) from rounding two adjacent frames onto
  the same tick. Measured without it: 5 `non monotonically increasing dts` lines on a clip whose
  packets were monotonic and whose `-f rawvideo` decode and `-c copy` remux were both clean.

**A clip is written only if the ring actually contains an IDR.** A file that a decoder cannot start is
worse than an error: with no IDR the cut **refuses** and says so.

### 2.8 Priority (law 1 — capture never waits for AI)

The capture→convert→encode path is one dedicated thread plus a bounded staging queue. **Nothing on it
is allowed to block on the AI, on the disk, or on the UI.** The cut is the only disk I/O on the
critical path, it is bounded by the ring's byte budget, and it happens on the cut thread, not the
encoder thread, so the recording continues while the clip is written (`specs/01` §5).

**The prototype has no AI and no audio at all, deliberately.** No audio device is opened, ever
(`AGENTS.md` house rule) — the audio path belongs to `AudioManager`, not to this lane.

### 2.9 CPU budget — a design constraint with a number attached (law 8)

Law 8 exists because *our* probes stuttered the owner's machine. Therefore:

- **No per-frame CPU pixel work.** The BGRA→NV12 conversion is a GPU draw; the CPU never maps a pixel
  buffer on the hot path. (The measured alternative — CPU conversion of 1080p BGRA at 60 fps — is
  8.3 MB/frame ≈ 500 MB/s of memcpy plus arithmetic, and is rejected for that reason.)
- One encoder thread, one capture thread, no thread pools, no spinning. The staging queue is a
  **condition variable**, not a poll loop.
- The lane's own measurement runs hold **≤2 threads' worth of CPU** and last tens of seconds, per
  `AGENTS.md` law 8. The receipt states the CPU% the run actually used.

---

## 3. THE INTERFACE (what the code in `src/capture/` exposes)

```
d3d11_ctx.h    D3d11Context::createOnVendor(0x10DE)      -> device + adapter + VRAM class
wgc_capture.h  WgcCapture::startForWindow(hwnd)          -> frames on a free-threaded pool
               WgcCapture::startForMonitor(hmonitor)
nv12_convert.h Nv12Converter::convert(bgraTex, nv12Tex)  -> 2 draws, BT.709 limited
nvenc_encoder.h NvencEncoder::selftest()                 -> law 6: did an encoder really initialise?
                NvencEncoder::init(mode, device, nv12Tex) -> preset P3 + LOW_LATENCY, forced IDR grid
                NvencEncoder::encode(...)                 -> Annex-B access unit + pictureType
ring_buffer.h  RingBuffer(capacityBytes)                 -> append / findCutBase / forEachFrom
mp4_writer.h   Mp4Writer::open/write_sample/close        -> streaming ISO-BMFF, AVCC in
replay.h       Replay::arm() / Replay::cut(path)         -> the whole path above, with counters
selftest.h     runLawSixSelftest()                       -> the arm/refuse decision + its reason
```

**Every counter the proof needs lives in one struct** (`Stats`): `frames_captured`,
`frames_converted`, `frames_encoded`, `frames_dropped_*`, `frames_in_ring`, `bytes_in_ring`,
`ring_capacity_bytes`, `peak_rss_bytes`, `cpu_*`. A clip that cannot say how many frames it is missing
is not shippable (`01-capture-encode.md` §4(a)).

---

## 4. THE FAILURE MODES THAT LOSE FRAMES, AND WHAT THIS DESIGN DOES

| mode | survival |
|---|---|
| encoder session limit | exactly **one** long-lived session; refusal classified by **status 21**; loud start-up failure instead of an armed hotkey |
| `Recreate` (resolution/DPI/monitor change) | force IDR + new segment; **≤2 frames lost, counted, never claimed as zero** — *not implemented in the prototype, named in §6* |
| protected content / DRM / exclusive fullscreen | **frame-liveness watchdog** (not a frame *count*: a paused game legitimately sends nothing) → fall back window item → monitor item → **stop claiming to record** |
| HDR / FP16 surfaces | out of scope for the prototype; feeding FP16 into a BGRA pipeline is the "washed out" failure MS names |
| the yellow border | borderless needs a packaged app + `graphicsCaptureWithoutBorder` capability + a one-time prompt; a plain Win32 exe cannot be borderless. **The prototype accepts the border** and does not pretend otherwise. MEASURED: `IGraphicsCaptureSession3::put_IsBorderRequired(0)` returns `S_OK` and reads back `0`, but whether the border is actually suppressed was **not** observable in this lane's runs (the test window's on-screen footprint was 4×4 px, then a full-desktop window at alpha 1/255). So the *call* succeeds; the *effect* stays UNKNOWN |
| a WGC frame arriving while the encoder is busy | bounded staging queue; overflow is **dropped with a counter**, never a silent stall (law 1) |

---

## 5. LAW 6 — THE HOTKEY IS ARMED ONLY IF AN ENCODER REALLY INITIALISED

**The worst failure this product can have is a recorder that says it is armed and records nothing** —
the owner only finds out when the moment is gone. So `arm()` is not a flag; it is the *output* of a
self-test that must succeed:

1. enumerate the codec ladder (H.264 → HEVC → AV1 → the non-NVIDIA arms);
2. for each: open a session **and** `NvEncInitializeEncoder`; a session that opens but does not
   initialise is **NOT** an encoder (measured: `NvEncGetEncodeCaps` on exactly that state segfaults);
3. register **and map** one real NV12 texture — the zero-copy path is part of "an encoder really
   initialised", because a session that cannot ingest our texture records nothing;
4. on the first full success: **arm**, and log codec, engine count, resolution, bitrate, IDR grid and
   ring bytes;
5. on total failure: **do not arm**, print one line per attempted arm with its **raw status code and
   `nvEncGetLastErrorString`**, and return a non-zero exit code. **A dead hotkey that says why beats
   a live hotkey that does nothing.**

The gate ships both colours: the pass (encoder present ⇒ armed) **and** a control in which the encoder
is made to fail on purpose (⇒ refused, with the reason printed). A control that stays green is a
failing control.

---

## 6. WHAT THIS SPEC DELIBERATELY DOES NOT DO / WHAT STAYS UNKNOWN

- **No audio.** Never opened, never captured, never muxed. A clip from this lane is **video-only**, and
  that is stated in the receipt rather than discovered by the owner.
- **No `Recreate` handling, no HDR/FP16, no HEVC/AV1/AMF/QSV arm.** The ladder's *shape* is
  implemented and exercised; only the NVENC-H.264 rung is real today.
- **RESOLVED — the BGRA8 → NV12 cost at 1080p.** Measured **0.010–0.017 ms/frame** for the two GPU
  draws at 1920×1080 (receipt §3). That is ~0.1 % of a 16.7 ms frame budget; the encode, not the
  conversion, is the cost that matters.
- **RESOLVED — the ring's RAM is the ring and nothing else.** Measured on this box: peak RSS =
  **48 MB (at arm) + ≈1.02 × ring capacity**, across 64 MB / 256 MB / 643 MB / 1024 MB arenas
  (receipt §4). The arena is preallocated, so the RAM cost does not depend on how much the content
  actually produced.
- **NEW, and it changed the harness — an off-desktop window is captured as uniform BLACK.** WGC
  delivered frames (so the *counts* were always honest) but every frame was black, which made the
  encoded bitrate meaningless and the ring's eviction path unreachable. A window 99.8 % outside the
  virtual desktop has nothing for DWM to compose beyond the desktop bounds. The harness now covers the
  whole desktop with a `WS_EX_LAYERED` window at **alpha 1/255** — composed, so real pixels reach the
  encoder, and 0.4 % blend, so it is imperceptible. **This is a test-harness fact, not a product one:**
  the product captures a window the owner chose, which is on screen by definition.
- **UNKNOWN — CBR overshoot on pathological content.** Full-frame random noise at 1920×1080 hit
  **42.50–45.32 Mbps** against the 45 Mbps target in GAMING (≈0.94–1.01×) but **16.03 Mbps against the
  8 Mbps target in DESKTOP (2.00×)**. Both arms encoded the same synthetic content at the same
  `vbvBufferSize = bitrate`; the desktop arm simply has fewer bits to spend per pixel at 30 fps. If
  the owner's real desktop content is anywhere near this hard, §2.6's 600 s of desktop ring is 300 s.
  **The ring budget must be re-derived from real content, not from this synthetic source.**
- **NEW — WGC can stop granting capture items machine-wide, and it is not a code defect.**
  Measured: `IGraphicsCaptureItemInterop::CreateForWindow` and `CreateForMonitor` return
  `E_ACCESSDENIED` for our own window, another process's foreground window, the desktop window, the
  taskbar and the primary monitor — while `IsSupported` is true and the consent store says `Allow`.
  It began between 11:24:37 (last success) and 11:26:32 (first failure) and has held for 40 minutes.
  **`GraphicsCaptureAccess::RequestAccessAsync(Programmatic)` was called and does NOT restore it**
  (S_OK, async Completed, errorCode 0 — receipt §7c), so the block is not a per-app consent denial.
  A display-driver reset (TDR) is **refuted**: no event 4101 in 24 h and no Display/nvlddmkm/Dwm
  event in 3 h, against 321 System events in that window. Consequence for the product: **a
  capture-item failure must be retryable with a bounded retry and a loud message**, and the recorder
  must never claim to be recording while it is failing. The human action is a sign-out/reboot
  (receipt §7d).
- **UNKNOWN — the real average bitrate of the owner's content** at the chosen preset, so §2.6's RAM is
  a budget, not a measurement of *his* content.
- **UNKNOWN — WGC on protected content and exclusive fullscreen** (`01-` §4(c)) — not measured here.
- **UNKNOWN — sustained encode throughput over hours**, and the behaviour when a second Sotto instance
  and a game both hold NVENC sessions.
- **UNKNOWN — whether a monitor capture item behaves identically to a window item** under the same
  pool settings. `--monitor` is implemented and **was never run**: it captures the owner's real
  desktop, and this lane does not do that without being asked.
- **The window border stays.** A borderless recorder is a packaged app with a manifest capability;
  that decision belongs to the shipping form, not to this prototype.
- **The measured capture rate is the DISPLAY/HARNESS rate, not the pipeline's.** The test source
  painted at 62–66 Hz and WGC delivered **54.4–55.6 fps**; the pipeline's own cost (convert 0.010 ms +
  encode ~5 ms) leaves room for ~200 fps at 1080p. A 60 fps game on a real window is the untested case.
