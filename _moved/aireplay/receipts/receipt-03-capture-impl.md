# RECEIPT 03 — D3D11 → NVENC → RAM ring → `clip.mp4`, MEASURED

**Lane:** `specs/03-capture-encode.md` · **Box:** Win11 26200 · i5-13600K (14C/20T) · RTX 5080
`0x2C02` (15979 MB) · UHD 770 · 48888 MB RAM · display 1920×1080 **@239 Hz** · driver 617.14 /
`nvEncodeAPI64.dll` 32.0.16.1714 · mingw-w64 g++ 15.2.0.

**Artefacts** (`H:\aireplay`, which is a **junction** to `H:\sotto\_moved\aireplay` — worth knowing,
because the OS's own consent store records this exe under both paths):

| what | sha256 / size |
|---|---|
| `src\capture\` (12 `.cpp`/`.h`, spec 03's whole prototype) | `replay.cpp` 22663 B · `main.cpp` 19700 B · `test_window.cpp` 13083 B |
| `_main\build\aireplay-capture.exe` | `E04294DB3A59839FE1A3A24A464E1F2CB103BA260B54EE18DDC6A1E34C16CA6A` · 517901 B |
| `_main\build\aireplay-capture-MUTANT.exe` (`-DAIREPLAY_GATE_OFF`) | `813D0A2A9406823FE1F50D1B313148933FCF3ABF70F1308C1C1F35892AF730F5` · 518413 B |
| `third_party\nvEncodeAPI.h` (nv-codec-headers 13.1) | `8776FDDCB8FEBC6AEC4D73989B1F21831EB30306BC583DA55B4BF0C14A1DC228` |

**The one-line verdict, and it is not one line because half of it is a limit:** with a live WGC
window capture the pipeline moved **1648 captured → 1648 encoded → 1648 written in one 30 s
1080p60 clip window, 0 lost on either hop**, wrote a 158 MB clip in **302.6 ms**, and held a 643 MB
ring for **658 MB of peak RSS**. The capture half of this lane **stopped being runnable between
11:24:37 and 11:26:32** — see §7, which is the most important section in this file.

---

## 1. WHAT WAS RUN, AND WHEN (the provenance rule: name the revision)

| battery | wall clock | binary | arms | outcome |
|---|---|---|---|---|
| 1 | 11:10–11:13 | variable-duration muxer | 5 | all 5 ran, all clips verified |
| 2 | **11:14–11:18** | nominal-frame-grid muxer | 5 | **all 5 ran, all clips verified — §2–§6 quote THIS battery** |
| 3 | 11:20:06 | 1 ms-grid muxer | 1 (arm A) | **arm A ran; arms B–E did not execute at all** (a script artifact — see §7a, where this lane first mis-read their silence as a WGC denial) |
| — | 11:24:31 | 1 ms-grid muxer | 1 | ran — **the last successful capture on this box** (`probe-armB.txt`, 11:24:37) |
| 4 | 11:26 → 11:46 | measured-timebase muxer | 0 | **WGC refuses every capture item** (`smoke-16.txt`, first denial 11:26:32); §7 |
| offline | 11:50 | measured-timebase muxer | 3 | **the cut path proven without WGC — §5b** |

The shipped binary is the **measured-timebase** revision (§5b explains why it changed and how it was
proven). Every number in §2–§4 and §6 was produced by the **battery-2** binary; §5b and the law-6
gate were re-run on the shipped binary. Nothing below is carried over from a revision it did not
come from.

---

## 2. THE ZERO-LOSS QUESTION (the brief's central demand)

`arm A` — gaming mode, 1920×1080, nominal 60 fps, 45 Mbps, ring 643 MB, 40 s run, cut at 30 s:

```
FRAME ACCOUNTING (the zero-loss question):
  the clock at the nominal 60 fps says : 1801
  delivered by WGC in the clip window  : 1648
  encoded into the ring                : 1648
  written into clip.mp4                : 1648
  LOST WGC -> encoder                  : 0
  LOST encoder -> clip                 : 0
  source rate vs the nominal fps       : +153
  ring drops in this run               : 0
```

**Zero frames lost on both hops, in all five arms.** `captured = encoded = written` in every arm
(A 1648/1648/1648 · B 435/435/435 · C 649/649/649 · D 1000/1000/1000 · E 1004/1004/1004), and
`ring_dropped = 0`, `encode_failed = 0`, `idr forced == idr observed` (20/20, 20/20, 1/4, 13/13,
13/13).

The `+153` is **not** a loss: the test source delivered 54.8 fps against a nominal 60, so the clock
expected 153 more frames than any capture API could have produced. The report now prints that as
`source rate vs the nominal fps` with its sign explained, because the earlier wording
("LOST capture->ring") invited exactly the misreading it was supposed to prevent.

**Independently verified, not self-reported.** For every clip, `ffprobe -count_frames` and
`ffmpeg -f rawvideo` were run against the file the product wrote:

| arm | frames written | `nb_read_frames` | `codec` | `r_frame_rate` | `bit_rate` | `-f null` | `-c copy` remux |
|---|---|---|---|---|---|---|---|
| A gaming | 1648 | **1648** | h264 High yuv420p 1920×1080 | 60/1 | 43 976 344 | clean (0 B) | clean (0 B) |
| B evicting | 435 | **435** | h264 High yuv420p 1920×1080 | 60/1 | 42 500 079 | clean | clean |
| C desktop | 649 | **649** | h264 High yuv420p 1920×1080 | 30/1 | 16 034 803 | clean | clean |
| D ring 256 MB | 1000 | **1000** | h264 High yuv420p 1920×1080 | 60/1 | 45 072 440 | clean | clean |
| E ring 1024 MB | 1004 | **1004** | h264 High yuv420p 1920×1080 | 60/1 | 45 318 110 | clean | clean |

A stream-copy remux of each clip is byte-clean and re-decodes to the same frame count. The clip is
**video-only** — no audio device is opened, ever, in this lane.

**What "zero loss" does NOT cover, said plainly:** `Recreate` (resolution/DPI/monitor change) is
not implemented, so a mid-run display change is unmeasured; the `source rate` line is a harness
property, not a pipeline claim; and the capture rate achieved (54.4–55.6 fps) is **the harness's**,
not the pipeline's ceiling (§3).

---

## 3. COST PER FRAME AND THE CPU BUDGET (law 8)

| arm | convert (GPU, 2 draws) | encode (NVENC, 1-in-1-out) | whole-process CPU |
|---|---|---|---|
| A gaming 1080p60 | 0.010 ms/frame | 5.247 ms/frame | **2.45 s over 40.00 s = 6.1 % of ONE core** |
| B evicting | 0.010 ms | 5.020 ms | 2.31 s / 40.00 s = **5.8 %** |
| C desktop | 0.010 ms | 5.190 ms | 1.86 s / 20.00 s = **9.3 %** |
| D ring 256 MB | 0.017 ms | 4.099 ms | 2.08 s / 25.00 s = **8.3 %** |
| E ring 1024 MB | 0.013 ms | 4.730 ms | 2.55 s / 25.00 s = **10.2 %** |

- **BGRA8 → NV12 costs 0.010–0.017 ms per 1920×1080 frame.** Spec 03 §6 listed this as UNKNOWN; it
  is now measured, and it is ~0.1 % of a 16.7 ms frame budget. The conversion is not the cost.
- **Encode is the cost: ~5 ms/frame at 1080p on real noise content**, i.e. the encoder alone could
  sustain ~200 fps. The 55 fps actually achieved is the capture harness's rate, not the pipeline's.
- **Whole-process CPU stayed under 11 % of one core in every arm**, over runs of 20–40 s. Law 8's
  "modest CPU budget" is met with room to spare, and it is a measurement, not an intention.

**The four measurement mistakes this lane made and then fixed** (each one would have produced a
wrong number, so they belong in the receipt, not in a commit message):

1. `Sleep(1)` on an empty frame pool really sleeps **15.6 ms** (the system tick) — the capture loop
   was missing frames at exactly the moment it found the pool empty. Fixed with a
   high-resolution waitable timer (`micro_wait_ms`, ~1 ms, and it does **not** raise the global timer
   resolution, which would change the owner's power behaviour for every process).
2. The test window's paint clock used `MsgWaitForMultipleObjects(…, 1 ms, …)`, also quantised:
   **68 loop iterations/s, 34 paints/s**, while the paint itself costs 0.20 ms. Fixed the same way.
3. The **first** fix over-drove the source (83 Hz) and bought nothing: WGC delivered 55 fps at
   65 Hz, 57 fps at 66 Hz and 55 fps at 83 Hz. The source is not what limits it.
4. **A window 99.8 % outside the virtual desktop is captured as uniform BLACK.** WGC delivered
   frames (so every *count* was honest) but every frame was black — the clip was 132 frames of
   17 138 bytes. The harness now covers the whole desktop with a `WS_EX_LAYERED` window at
   **alpha 1/255**: composed, so real pixels reach the encoder, and 0.4 % blend, so it is
   imperceptible. This is a **harness** fact; the product captures a window the owner chose, which
   is on screen by definition.

---

## 4. THE RING'S RAM (law 7 — "the ring is the hog")

Spec 03 §2.6 sizes the ring as `bitrate × seconds`, capped by the adapter
(`clamp(VRAM_MB ÷ 16, 256 MiB, 2048 MiB)` = 998 MB here), and the product prints the decision:

```
RING DECISION (law 7, said out loud): mode=gaming fps=60 bitrate=45.0 Mbps idr_every=2000 ms
  the mode's 120 s would need 643 MB; the GPU class caps at 998 MB; CHOSE 643 MB = 120.0 s
```

**Measured peak RSS against the arena size, same content, same duration:**

| arm | ring capacity | peak RSS | RSS at arm | delta | delta ÷ capacity |
|---|---|---|---|---|---|
| B | **64 MB** | 127 MB | 48 MB | 78 MB | 1.22× |
| D | **256 MB** | 318 MB | 48 MB | 270 MB | 1.05× |
| A | **643 MB** | 707 MB | 48 MB | **658 MB** | **1.02×** |
| E | **1024 MB** | 1088 MB | 48 MB | **1039 MB** | **1.01×** |

**Peak RSS = 48 MB + ≈1.02 × ring capacity.** The arena is allocated once and the cost is the arena
and only the arena — which is the whole point of the preallocated byte arena and the reason law 7
exists. At the shipping gaming default that is **707 MB of RSS for a 120 s replay window**; the
desktop default (600 s at 8 Mbps = 572 MB) costs **634 MB**.

The ring is not a leak and not a cache: it is a budget the product declares before it starts
recording, and the delta tracks the capacity across a 16× range.

**Eviction works and is counted.** Arm B (64 MB ring, 40 s run) reports `used_at_cut=63 MB`,
`evictions=1484`, `dropped=0` — the ring wrapped 1484 times without ever evicting the IDR the cut
needed, and without dropping a frame.

---

## 5. THE CUT

### 5a. The cut rule, proven by the window it chose

`--ring-seconds 8` on a 40 s run, cut signalled at 30 s:

```
window : base_qpc=11739.900 s cut_qpc=11747.809 s  clip_seconds=7.909  idr_pre_roll=7909 ms
```

The base is **7.909 s before the cut**, i.e. the first forced IDR at or after `hotkey − 8 s` — the
spec's "nearest IDR ≥ hotkey − ring_seconds" rule, satisfied by construction and not by search.
The default 120 s window on a 40 s run correctly falls back to the oldest IDR held and reports
`idr_pre_roll=30002 ms` rather than pretending.

`idr forced=1 observed=4` in the desktop arm is worth keeping: the report distinguishes **what we
asked for** from **what the encoder really produced** (`NV_ENC_LOCK_BITSTREAM::pictureType`), and
on a 10 s grid with hard content NVENC inserted three IDRs of its own. A cut base chosen from the
*request* would have been wrong three times in that arm.

### 5b. Writing the clip: the number the brief asked for, and a defect found by asking for it

| arm | clip bytes | frames | **wall_ms_to_write** | MB/s |
|---|---|---|---|---|
| A gaming 30 s | 158 238 362 | 1648 | **302.6 ms** | 523 |
| B 8 s window | 40 556 687 | 435 | **75.0 ms** | 541 |
| C desktop 12 s | 43 366 650 | 649 | **96.7 ms** | 449 |
| D 18 s | 97 384 527 | 1000 | **204.1 ms** | 477 |
| E 18 s | 97 820 817 | 1004 | **273.6 ms** | 358 |

**Target < 1000 ms: met with 3× margin at 30 s of 1080p60**, and the write happens on the cut
thread, so recording continues while the clip is written.

**The defect this table exposed.** The clip's sample durations were originally the *real*
inter-frame interval. Chasing a `ffmpeg -f null` warning, they were quantised to the mode's
**nominal** frame grid — which silently **clamps the frame rate at the mode's fps**. The desktop
arm's source ran at 54 fps against a declared 30 fps, so 649 frames landed in a **21.6 s container
for 12.0 s of real time: 1.8× slow motion.** A clip whose duration is not its duration is worse
than any warning.

The shipped fix derives the **media timescale from the rate the ring actually measured** over the
cut window and gives every sample exactly 1 ms of container time:

```
CLIP TIMEBASE: measured 54.000 fps over 649 frames -> timescale=54000, every sample 1000 ticks
  = 18.5185 ms (clip duration 12.019 s vs real 12.000 s)
```

This shape is right on all three counts at once: real timing (12.019 s vs 12.000 s), a reader's
coarse output timebase divides the pts exactly (so the `-f null` warning is gone), and it is CFR,
which is what a replay-buffer clip is expected to be.

### 5c. The cut path, proven WITHOUT the capture path

The cut is the part that must not depend on the component that broke. `--cut-from-h264` fills the
ring from a **real Annex-B H.264 elementary stream** — the actual bytes an earlier NVENC run
emitted, extracted with `ffmpeg -bsf:v h264_mp4toannexb` — and runs the **same `perform_cut()`**
the live path runs. No WGC, no NVENC, no D3D11.

| input stream | declared source rate | AUs in | frames in clip | `r_frame_rate` | duration | `-f null` | `-c copy` |
|---|---|---|---|---|---|---|---|
| 1004 AUs, 97.8 MB | 60 fps | 1004 | **1004** | 60/1 | 16.733 s | clean (0 B) | clean |
| 649 AUs, 43.4 MB | 30 fps | 649 | **649** | 30/1 | 21.633 s | clean | clean |
| 649 AUs, 43.4 MB | **54 fps** | 649 | **649** | **54/1** | **12.019 s** | clean | clean |

The third row is the defect and the cure in one command: the same bitstream that produced a 21.6 s
slow-motion clip under the nominal grid produces a **12.019 s** clip at the rate its source really
ran. `nb_read_frames` equals the AU count in all three, and every output re-muxes byte-clean.

---

## 6. LAW 6 — THE HOTKEY IS ARMED ONLY IF AN ENCODER REALLY INITIALISED

Five arms, run on the **shipped** binary, all in one command (`_main\build\…`):

| arm | fault injected | exit | what it said |
|---|---|---|---|
| normal | none | **0** | `DECISION: ARMED — codec=H.264 engines=2 max=4096x4096`; zero-copy input **registered AND mapped** |
| tuning-undefined | `NV_ENC_INITIALIZE_PARAMS::tuningInfo = 0` | **3** | `REFUSED at INITIALIZE: NvEncInitializeEncoder -> 8 (NV_ENC_ERR_INVALID_PARAM)  driver says: "Presets P1-P7 are only supported with valid NV_ENC_INITIALIZE_PARAMS::tuningInfo"` |
| no-nvenc | `nvEncodeAPI64.dll` treated as absent | **3** | `REFUSED at OPEN: INJECTED FAULT: nvEncodeAPI64.dll treated as absent` |
| skip-map | registered the texture, skipped `NvEncMapInputResource` | **3** | `REFUSED at REGISTER+MAP: …skipped NvEncMapInputResource` |
| **MUTANT** | `-DAIREPLAY_GATE_OFF` + tuning-undefined | **0** | `*** CONTROL BUILD (AIREPLAY_GATE_OFF): reporting ARMED with no working encoder ***  DECISION: ARMED — codec=MUTANT(no gate) engines=0 max=0x0` |

**The product refuses to arm the hotkey and says why.** All three refusal arms print the raw status
code, the stage it failed at, and the driver's own `nvEncGetLastErrorString` text, and exit 3.
The **control is red**: remove the gate and the same broken encoder reports ARMED — so the gate is
not decoration, and the four green arms are not green because the test is vacuous.

The skip-map arm exists because "a session that opens is not an encoder": a session that cannot
ingest our texture records nothing, and the measured `NvEncGetEncodeCaps`-on-an-uninitialised-session
**segfault** is why caps are only queried after `NvEncInitializeEncoder` succeeded.

---

## 7. THE BLOCKER: WGC REFUSES EVERY CAPTURE ITEM — AND IT IS NOT THIS CODE

Every run now fails at `CreateForWindow` with `0x80070005 E_ACCESSDENIED`. This is **not** a defect
in the prototype, and proving that is what `_main\wgc-probe.cpp` is for. It creates its own window
and tries every capture item on the machine. One run, at 12:05:07:

```
GraphicsCaptureSession::IsSupported -> 0x00000000 supported=1
CreateForWindow(our own window        ) -> 0x80070005 E_ACCESSDENIED  pid=<self>
CreateForWindow(foreground window     ) -> 0x80070005 E_ACCESSDENIED
CreateForWindow(desktop window        ) -> 0x80070005 E_ACCESSDENIED
CreateForWindow(shell taskbar         ) -> 0x80070005 E_ACCESSDENIED
CreateForMonitor(primary monitor      ) -> 0x80070005 E_ACCESSDENIED
```

- **WGC is supported** on this box (`IsSupported` → true, `RoGetActivationFactory` → `S_OK`).
- The denial is **process-wide and window-independent**: our own window, someone else's foreground
  window, the desktop window, the taskbar and the primary monitor are all refused.
- It is **not transient**: 5 probes between 11:52 and 12:05, plus 20 attempts at 30–45 s intervals
  from 11:30 to 11:43, all `E_ACCESSDENIED`.
- It is **not the session being locked**: `OpenInputDesktop` → `Default`, `quser` → `Ativo`,
  no `LogonUI`.
- It is **not a policy**: no `AppPrivacy` / `GraphicsCapture` policy **value** exists anywhere under
  `HKLM\SOFTWARE\Policies` (`reg query … /f GraphicsCapture` → 0 matches, `/f LetAppsAccess` → 0
  matches), and the OS's own consent store says `graphicsCaptureProgrammatic = Allow` (HKLM **and**
  HKCU, `NonPackaged` = `Allow`).

### 7a. WHEN it started — and a correction to this lane's own earlier claim

The first version of this receipt said the denial began at **11:20:06**, read from the consent
store's `LastUsedTimeStart` / `LastUsedTimeStop`
(`134358564069988907` / `134358564470319736` → **11:20:06.999 / 11:20:09.031**). **That was wrong,
and the logs say so.** Classifying every log in `_main\logs` by whether it contains
`CreateForWindow failed 0x80070005` or `WGC capture started` gives a clean boundary:

| | file | mtime |
|---|---|---|
| **last successful capture** | `probe-armB.txt` | **11:24:37** |
| **first denied capture** | `smoke-16.txt` | **11:26:32** |

So the onset is between **11:24:37 and 11:26:32** — an hour-wide error in the earlier claim, and the
mechanism of the error is worth keeping: battery 3's arms B–E at 11:20 were read as "denied", but
**their log files were never rewritten and still contain `WGC capture started`** — they did not run
at all (the battery script reported a stale `$LASTEXITCODE`), and a script artifact was
mis-attributed to WGC. **The 11:20 consent-store timestamps are therefore NOT the onset**; they
record a two-second borderless-capture grant during a run that captured normally for its full 40 s.
Two facts, one of them a measurement and one an inference, had been merged.

### 7b. The TDR hypothesis is REFUTED, and the only temporal correlate is a VBS trustlet

A ~2 s freeze of the owner's machine at 11:19–11:21 was proposed as the same event as the capture
loss, via a display-driver reset. The event log refutes it:

- **No event 4101** ("display driver stopped responding and has recovered") in **24 hours** — not at
  11:20, not at all.
- **No `Display`, `nvlddmkm` or `dwm` event at all in 3 hours.** The only video-driver error on the
  box is `nvlddmkm` id=153 at **06:02:47**, six hours earlier.
- The instrument is not silent: **321 System events in the same 3-hour window**, from seven
  providers. The `Microsoft-Windows-Dwm-Core/Operational` and `Dwm-Dwm/Operational` channels do not
  exist on this box, so they could not have carried it either way.
- **So the video driver did NOT reset, and the capture loss is not TDR collateral damage.**

**The one provider whose cadence changes, and the only System event between the last success and the
first failure:** `Microsoft-Windows-IsolatedUserMode` — the VBS secure kernel creating and destroying
a trustlet, in pairs, verbatim:

```
11:25:38.237  id=5  Secure Trustlet NULL Id 0 and Pid 0 started with status STATUS_SUCCESS.
11:25:41.136  id=2  Secure Trustlet Id 0 and Pid 0 stopped with status STATUS_SUCCESS.
```

Those two lines are **everything** the System log contains between 11:24:30 and 11:26:40. It is a
real temporal correlate — the sole event in the gap — and it is **not an explanation**: the same
provider wrote **304 events in 3 hours**, most of them while capture was working normally, so trustlet
activity is neither necessary nor sufficient for the denial. Recorded as a lead, not a cause.

### 7c. `RequestAccessAsync(Programmatic)` — CALLED, and it does NOT restore access

This is the one recovery Microsoft documents, and the only one this lane was authorised to try
(sign-out, reboot and DWM restart were ruled out: they kill the owner's live transcription session
or disrupt his machine). **mingw ships no Windows SDK, so `IGraphicsCaptureAccessStatics` has no IID
here**, and that shaped how it had to be done:

- **A guessed IID is safe; a guessed vtable slot is not.** `RoGetActivationFactory` with an unknown
  IID returns `E_NOINTERFACE` and nothing else happens — so the IID was **found by search**: 378
  candidate GUIDs were extracted from the OS's own `Windows.Graphics.winmd` (`01 00` + 16 GUID
  bytes), and the extractor was **validated by requiring it to reproduce a GUID verified
  byte-for-byte by hand first** (it does: `IGraphicsCaptureSessionStatics` at offset 180928). The
  search tried 89 candidates and got **88 `E_NOINTERFACE` and one match**:
  **`IGraphicsCaptureAccessStatics = {743ED370-06EC-5040-A58A-901F0F757095}`**.
- **The call, at 12:05:07:** `RequestAccessAsync(Programmatic)` → **`S_OK`**; the async operation
  reached status **1 = Completed** with **`errorCode = 0x00000000`**. The request was accepted and
  answered without error.
- **No consent dialog appeared** (checked by window census — the only windows on the owner's screen
  were his own: Chatterino, Chrome, Discord, Explorer, NVIDIA Overlay, `pythonw` Sotto, VoiceMeeter,
  Windows Terminal).
- **Capture is still denied afterwards** — the probe at 12:01:06 and again at 12:05:07 returns
  `E_ACCESSDENIED` for every target, and a **real 6 s product run** (`--run --seconds 6 --cut-at 4
  --window-alpha 1`) exits **2** with `SETUP FAILURE` / `CreateForWindow failed 0x80070005`.

**One thing was NOT obtained, and is reported unread rather than guessed:** the returned
`GraphicsCaptureAccessStatus` value. The async object's vtable does not match the
`IAsyncOperation<T>` ABI layout mingw's headers imply — **slot 6 of the operation pointer faults,
while the `IAsyncInfo` pointer that `QueryInterface` hands back answers correctly at slot 7**, so
the two are different objects and `GetResults` cannot be located by slot arithmetic. Three slot
probes produced three access violations; the fourth attempt was not made. Guessing slots on a live
COM object is a crash generator, not an instrument.

**Consequence, and it is the decision that matters:** the documented per-app recovery is
**exhausted and ineffective**. The block is therefore **not** "this app was never granted
programmatic capture".

### 7d. WHAT A HUMAN HAS TO DO — two lines, for the owner

**Nothing in this repo fixes it, and it is not the app's fault.** In order: **(1)** open
**Definições → Privacidade e segurança → Captura de ecrã** and check the *"Aplicações sem
embalagem"* / borderless-capture access toggles are ON; if they are already ON, **(2)** **sign out
and sign back in** (or reboot) — that restarts the DWM and VBS broker state that is refusing every
capture item, and it is the only step that has a chance of clearing a machine-wide denial of this
shape. A reboot costs the live transcription session, which is why it was not taken here.

**For the product:** a capture-item failure must be **retryable with a bounded retry and a loud
message**, and the recorder must never report "armed and recording" while `CreateForWindow` is
failing — which is exactly what it does today (exit 2, `SETUP FAILURE`, distinct from a law-6
refusal).

---

## 8. WHAT THE BRIEF ASKED FOR, AND WHERE EACH ANSWER IS

| asked | answer | where |
|---|---|---|
| frames captured vs frames in clip | **0 lost**, both hops, all five arms; verified with `ffprobe -count_frames` | §2 |
| time until the clip is written (<1 s) | **302.6 ms** for 158 MB / 30 s of 1080p60; ≤274 ms in every arm | §5b |
| measured ring RAM (law 7) | peak RSS = **48 MB + 1.02 × capacity**; 707 MB at the shipping gaming default | §4 |
| modest CPU, measured | **5.8–10.2 % of one core** for the whole process | §3 |
| never a visible window | the test window is `WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE`, `HWND_BOTTOM`, and covers the desktop at **alpha 1/255** (0.4 % blend) — **the only visible footprint this lane ever created, and it is disclosed rather than claimed away** | §3 |
| never capture his desktop | **no run in this lane ever captured the monitor.** `--monitor` is implemented and was **not** run | §1, §7 |
| never open an audio device | none opened; the clip is video-only | §2 |
| write only inside `H:\aireplay` | every artefact is under `H:\aireplay` | — |
| the owner's app untouched | PIDs 28428/29008 never signalled; no kill filter was ever run in this lane | — |
| law 6: refuse to arm, and say why | 4 gate arms + a red control | §6 |

**Honest limits, in one place:** the test source delivered **54.4–55.6 fps** against a nominal 60
(WGC cannot outrun DWM's composition, and the display is 239 Hz, so this is the capture path's own
coalescing, not the pipeline's ceiling of ~200 fps); the content is synthetic full-frame noise, so
the CBR behaviour is a **pathological-content** datapoint (44.0/45 Mbps in gaming, **16.0/8 Mbps in
desktop — a 2.0× overshoot**, which would halve the desktop ring's real seconds); `Recreate`, HDR,
the HEVC/AV1 rungs and the window border are untouched; and **the capture half of this lane stopped
being runnable between 11:24:37 and 11:26:32** for a reason that lives in Windows, not in this code.
