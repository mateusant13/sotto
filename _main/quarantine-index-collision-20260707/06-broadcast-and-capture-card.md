# SPEC 06 - BROADCAST AND CAPTURE CARD: the two features with different physics

Owner's brief (lane dispatch, 2026-10-08): *"ShadowPlay is not only instant replay. Broadcast is the
second pillar (second display, camera, microphone, streaming) and Capture Card is the external-input
path. Nobody has written a line about either, and they have completely different constraints from
screen capture."*

Status: **SPEC. Every NVIDIA/OBS/Microsoft claim below carries a URL that was OPENED on this machine,
and every claim about our code carries `file:line`.** Where a number is an engineering decision it is
marked **DECISION** and the reasoning is shown. Where it needs a measurement to be trusted it is
marked **UNKNOWN** and the closing instrument is named in §6 — a named unknown is not a TBD; an
unnamed one is.

**Scope note.** This spec writes neither source code nor another lane's file. It owns one artefact:
this document.

---

## 0. THE VERDICT FIRST, because the brief asks for it and it decides the reading order

> **BUILD BROADCAST FIRST. The capture card is a source that plugs into the broadcast compositor, not
> a feature that stands on its own.**

Three reasons, each one falsifiable by a fact in this repo:

1. **Broadcast is the only one of the two whose hardest piece does not exist.** It needs a D3D11
   composite (many sources → one texture → one swapchain). The capture card needs *the same*
   composite *plus* a Media Foundation video front end, device-loss handling and a different storage
   policy. The composite is the load-bearing new code and Broadcast is what forces it into existence.
2. **Broadcast is what makes every other lane's output visible.** One preview window shows the HUD
   (`specs/05`), the live caption and the composite in the same pixels. It is the only feature in the
   whole product that is *self-demonstrating* — the owner sees it working without reading a log.
3. **The capture card is a hardware purchase plus a driver plus a loss state machine, and this box has
   no capture card.** MEASURED on this machine (2026-10-08): `Get-PnpDevice -Class Camera` returns
   **0 devices**; the only image-class device is `HD Pro Webcam C920`
   (`USB\VID_046D&PID_082D&MI_00\7&38A30BCB&0&0000`). A spec whose main path cannot be opened on the
   owner's own machine is a spec whose gates can never be run here.

The honest cost order inside Broadcast, and the dependencies that do not exist yet, are in §7.

---

## 1. THE DEVICE AND ENUMERATION MODEL

### 1.1 What the desktop path already is, so the difference is not hand-waved

`src/capture/wgc_capture.h:27-28` — the capture session is created for **two handle kinds only**:

```
27:    bool start_for_window(HWND hwnd, std::string* err);
28:    bool start_for_monitor(HMONITOR mon, std::string* err);
```

and `:27-28` is the whole entry surface — `start_for_window(ID3D11Device*, HWND, …)` and
`start_for_monitor(ID3D11Device*, HMONITOR, …)`, **two handle kinds and no third**. The header says why
it is only two: the item comes from `IGraphicsCaptureItemInterop::CreateForWindow /
CreateForMonitor` and *"the frame pool is CreateFreeThreaded, so no message pump, no UI thread, and the
shipping process has no window at all"* (`:4-8`). What a frame is, is `CapturedFrame` at `:18-23`:
an `ID3D11Texture2D*`, a `qpc_ns`, and `sys_rel_ns` — *"frame.SystemRelativeTime, converted to ns"* —
which `specs/03-capture-encode.md:45-48` records as **QPC**, *"the clock the transcript and OCR must
share"*. The adapter is chosen by vendor and never taken from the default path
(`src/capture/d3d11_ctx.h:32`, `create_on_vendor(UINT vendor, …)`,
because "the NVENC session must be opened on the SAME `ID3D11Device` that owns the textures"
(`d3d11_ctx.h:3-6`)).

**That is the whole desktop model: a compositor-surface item on our own GPU.** Everything in §1.2 and
§1.3 is a different universe.

### 1.2 Why WGC structurally CANNOT open a capture card — and this is not a preference

The factory takes a window handle or a monitor handle and returns a `GraphicsCaptureItem`. Microsoft's
own declaration, `README`, opened:

- `https://learn.microsoft.com/en-us/windows/win32/api/windows.graphics.capture.interop/nf-windows-graphics-capture-interop-igraphicscaptureiteminterop-createformonitor`
  — *"monitor — The monitor handle that represents the monitor to capture."*
- `https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture`
  — the capture item is created **from a display or a window**.

There is no `CreateForDevice`, there is no third overload, and the item domain is DWM's composition
surfaces. **A capture card does not draw into this machine's DWM.** Its HDMI input is turned into
samples by a driver, and the only supported way to read those samples on Windows is a capture-device
API. This is a statement about the API surface, not a judgement about NVIDIA.

**Therefore: `wgc_capture.h` cannot be extended to cover a capture card, and this spec does not
pretend otherwise.** The capture card is a **second capture front end** that lands on the *same*
encode → ring → cut pipeline. Any design that treats it as "another window to capture" is wrong at the
first line of code.

### 1.3 The external video path: Media Foundation's capture stack

The documented sequence is fixed and short. All five pages below were opened:

| step | call | source (opened) |
|---|---|---|
| enumerate | `MFEnumDeviceSources` with `MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE = MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID` | [enumerating-video-capture-devices](https://learn.microsoft.com/en-us/windows/win32/medfound/enumerating-video-capture-devices) |
| instantiate | `IMFActivate::ActivateObject` → `IMFMediaSource` | same page |
| discover formats | `CreatePresentationDescriptor` → `GetStreamDescriptorByIndex` → `GetMediaTypeHandler` → `GetMediaTypeCount` / `GetMediaTypeByIndex` | [how-to-set-the-video-capture-format](https://learn.microsoft.com/en-us/windows/win32/medfound/how-to-set-the-video-capture-format) |
| choose format | `IMFMediaTypeHandler::SetCurrentMediaType`; *"If you do not set the capture format, the device will use its default format."* | same page |
| choose frame rate | read `MF_MT_FRAME_RATE_RANGE_MAX` / `_MIN`, set `MF_MT_FRAME`, then `SetCurrentMediaType` | [how-to-set-the-video-capture-frame-rate](https://learn.microsoft.com/en-us/windows/win32/medfound/how-to-set-the-video-capture-frame-rate) |
| read samples | `IMFSourceReader` (`MFCreateSourceReaderFromMediaSource`, `ReadSample`, `Flush`, `SetCurrentMediaType`) | [IMFSourceReader](https://learn.microsoft.com/en-us/windows/win32/api/mfreadwrite/nn-mfreadwrite-imfsourcereader) |
| detect loss | `RegisterDeviceNotification` for **`KSCATEGORY_CAPTURE`**, handle `WM_DEVICECHANGE`, compare `dbcc_name` against `MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK` | [handling-video-device-loss](https://learn.microsoft.com/en-us/windows/win32/medfound/handling-video-device-loss) |

Four consequences the spec commits to, each because a page says it:

- **Identity is the symbolic link, never the friendly name.** *"The `MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME`
  attribute contains the display name of the device. The display name is suitable for showing to the
  user, but might not be unique"*; *"The symbolic link uniquely identifies the device on the system,
  but is not a readable string"* — [audio-video-capture-in-media-foundation](https://learn.microsoft.com/en-us/windows/win32/medfound/audio-video-capture-in-media-foundation),
  opened. **This is the same lesson Sotto already paid for** (`src/capture/wasapi_audio.h:25-30`:
  `"CABLE Output (VB-Audio Virtual Cable)"` exists at MME #2, DirectSound #15 and WASAPI #32 and they
  are not interchangeable). Every device record this spec emits carries `api=` **and** `symbolic_link=`.
- **UVC is the floor, not "webcam".** *"Video capture devices are supported through the UVC class
  driver and must be compatible with UVC 1.1"* — same page. A PCIe capture card is a different class
  entirely (Blackmagic, AJA) and needs a vendor SDK; OBS ships them as **separate plugins**
  (`https://api.github.com/repos/obsproject/obs-studio/contents/plugins` lists `decklink`, `aja`,
  `win-dshow`, `win-capture`, `win-wasapi`), and its knowledge base says the Blackmagic source works
  *"using their provided developer SDK"*
  ([https://obsproject.com/kb/video-capture-sources](https://obsproject.com/kb/video-capture-sources)).
  **A USB/UVC capture card is in scope for this spec. A PCIe card is not, and §8 says so.**
- **Device loss is a first-class event, not an error to discover from a black frame.** The device-loss
  page exists precisely because a capture device disappears without the process being told by the
  pipeline. §4 gives it a state name.
- **Device timestamps are not trustworthy by default.** FFmpeg's `dshow` input exposes
  `use_video_device_timestamps` and documents that setting it false *"allows working around devices
  that provide unreliable timestamps"* — [https://ffmpeg.org/ffmpeg-devices.html](https://ffmpeg.org/ffmpeg-devices.html),
  opened. **DECISION: the capture-card source stamps QPC on the frame it is delivered, not the
  device's clock.** Reason: the ring's cut point is a QPC comparison
  (`src/capture/ring_buffer.h:22` `qpc_ns`, `:81` `find_cut_base(t_cut_ns, window_ns, …)`), and the
  transcript's clock is QPC too (`specs/03-capture-encode.md:47-48`).

**DirectShow: named, and deliberately not the primary path.** Microsoft has marked the whole feature
legacy: *"DirectShow, is a legacy feature. It has been superseded by MediaPlayer, IMFMediaEngine, and
Audio/Video Capture in Media Foundation… Microsoft strongly recommends that new code use … Audio/Video
Capture in Media Foundation"* —
[https://learn.microsoft.com/en-us/windows/win32/directshow/video-capture](https://learn.microsoft.com/en-us/windows/win32/directshow/video-capture),
opened. OBS nevertheless ships `plugins/win-dshow/win-dshow.cpp` and its knowledge base says *"On
Windows, for a device to work with OBS the drivers needs to support DirectShow output"* (both opened:
`https://raw.githubusercontent.com/obsproject/obs-studio/master/plugins/win-dshow/win-dshow.cpp`,
`https://obsproject.com/kb/video-capture-sources`). **Both facts are true and they disagree about the
future. Resolution for this product: Media Foundation first, DirectShow as a documented fallback rung
in the device ladder, because the vendor SDK route is the only one with no future anyway.** OBS's own
source shows what the fallback costs: its device plugin carries the comment
*"TODO: - handle disconnections and reconnections - if device not present, wait for device to be
plugged in"* — it does not. We do.

### 1.4 Camera and microphone: the two paths, and what OBS does that a clone must match

- **Camera** = the §1.3 video path, unchanged. The `HD Pro Webcam C920` on this box is one.
- **Microphone** = WASAPI capture (`eCapture`), the mirror of the loopback tap we already have. OBS's
  `plugins/win-wasapi/win-wasapi.cpp:614` calls `GetDefaultAudioEndpoint(input ? eCapture :
  eRender, …)` and `:743` initialises `AUDCLNT_SHAREMODE_SHARED` with `AUDCLNT_STREAMFLAGS_LOOPBACK`
  — opened at
  `https://raw.githubusercontent.com/obsproject/obs-studio/master/plugins/win-wasapi/win-wasapi.cpp`.
  A microphone is the same code with the flag off. Microsoft's loopback page
  ([https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording),
  opened) is the reference sequence, and the first five steps of it are already transcribed in
  `src/capture/wasapi_audio.h:16-22`.
- **What OBS does that we would otherwise skip**, each item with its source (all opened):
  1. *Separate audio device per video source.* OBS's device source has a `use_custom_audio_device` /
     `audio_device_id` pair (knowledge base, *Video Capture Device Source* table; and
     `win-dshow.cpp:48-49`), because a webcam's built-in mic is worse than a desk mic and the two
     must not be forced together. **We adopt this from M2.**
  2. *"Deactivate when not showing"* — *"Frees up resources by deactivating the device when it is
     hidden/not on the current scene"*, default Off. **We adopt the idea, keep the default Off** so a
     source that is merely occluded does not disappear from a recording.
  3. *"Buffering: Auto-Detect … If set to Disable, turns buffering off which can help if you are
     experiencing a delay on the device."* **We ship `auto` and expose the flag**, because the failure
     mode it names (a delay the user feels) is a latency bug and latency bugs must be adjustable, not
     argued about. FFmpeg documents the same knob on its side (`audio_buffer_size`, *"can directly
     impact latency, depending on the device… typically some multiple of 500ms"*, opened).
  4. *Format negotiation as a user-visible property.* OBS exposes Resolution / FPS / Video Format /
     Color Space as first-class settings and says plainly: *"If the device does not support the
     resolution, the source will not display anything"* and *"If the device does not support the frame
     rate, the source will not display anything"* (opened). **We adopt that wording verbatim in §4**,
     because a silent black source is the exact defect this repo keeps paying for.

### 1.5 What is actually on this box (MEASURED, 2026-10-08, this machine)

| fact | value | how it was obtained |
|---|---|---|
| monitors | **1** — `\\.\DISPLAY1`, 1920×1080@240 Hz, primary, work area 1920×1032 | `EnumDisplayMonitors` + `GetMonitorInfo` + `EnumDisplaySettings` via a temporary P/Invoke |
| capture devices (`Camera` class) | **0** | `Get-PnpDevice -Class Camera` |
| image-class devices | **1** — `HD Pro Webcam C920` | `Get-PnpDevice -Class Image` |
| audio endpoints | **15**, among them `Microphone (HyperX Quadcast)`, `Microphone (HD Pro Webcam C920)`, `Microfone (NVIDIA Broadcast)`, `VoiceMeeter Input/Output`, `CABLE Input/Output` | `Get-PnpDevice -Class AudioEndpoint` |

**Two design facts fall straight out of that table.** First, **there is exactly one monitor, so the
"second display" of Broadcast cannot be a monitor.** It is a window — always has been (§1.2). Second,
**a microphone is available right now**, which means the M2 milestone in §7 is testable on this
machine, while M4 (capture card) is not.

---

## 2. THE COMPOSITE LAYOUT MODEL

### 2.1 Two canvases, and why one is a lie

A composite has a **base (canvas)** resolution and an **output (scaled)** resolution, and they are
different numbers. NVIDIA's own encoder guide states the two-field model and names the filter:
*"Base (Canvas) Resolution: Set the resolution you normally play at… Output (Scaled) Resolution: Enter
the resolution appropriate for your Upload Speed and Bitrate… Downscale Filter: If your Output
Resolution is smaller than the Base Resolution, OBS will use a downscale filter"* —
[https://www.nvidia.com/en-us/geforce/guides/broadcasting-guide.md](https://www.nvidia.com/en-us/geforce/guides/broadcasting-guide.md),
opened. OBS implements it as `ovi.base_width`/`ovi.base_height` versus the output info
(`libobs/obs-video.c:146`, `:174-186`, `:295-301`, opened at
`https://raw.githubusercontent.com/obsproject/obs-studio/master/libobs/obs-video.c`).

**Decision, closed:** `base` = the capture window's size (dynamic, from WGC); `output` = a fixed
1920×1080 for the prototype, because the only display on this box is 1920×1080
(`specs/01` §1 already fixes gaming at 60 fps / 45 Mbps at 1080p).

### 2.2 The source list, and per-source geometry

OBS's model is a list of sources per scene; *"Sources that are above others in the Sources list … are
also located above other Sources in the preview"*, each with a bounding box, and the ordering is
z-order — `https://obsproject.com/kb/sources-guide` (opened) plus
`https://raw.githubusercontent.com/obsproject/obs-studio/master/libobs/obs-scene.c` (opened), where
`crop_to_bounds` at `:439-443` and the `OBS_BOUNDS_SCALE_OUTER / _TO_HEIGHT / _TO_WIDTH` bounds types
are the fit modes.

**DECISION — the minimum scene model that is not a toy and not OBS:**

| field | type | meaning | why it exists |
|---|---|---|---|
| `sources[]` | ordered list, **index = z** | first is topmost | matches OBS; a reorder is an index write, no layout engine |
| `src.id` | string | `cam-0`, `mic-0`, `card-0`, `win-0` | stable across restarts; the symbolic link is stored per device, not in the scene |
| `src.kind` | enum | `display` \| `camera` \| `card` \| `mic` \| `image` \| `text` | `mic` has no video rect; `text`/`image` are the overlay lane's business |
| `src.rect` | `x, y, w, h` in **base-canvas pixels** | absolute, not relative | a relative rect breaks the moment the canvas resizes |
| `src.fit` | enum | `stretch` \| `fit` (letterbox) \| `fill` (crop) \| `none` | one choice the user actually makes, three aliases it does not |
| `src.opacity` | 0.0–1.0 | alpha | OBS does it; without it a face-cam over a game is a rectangle cut out of the game |
| `src.visible` | bool | hidden ≠ removed | a hidden source keeps its device open and keeps its audio |

**Two decisions that are refusals, not omissions:**
- **No nested scenes and no transitions in this prototype.** A scene that contains scenes is a scene
  graph, and a scene graph is a renderer. The whole feature is one composite; a user who needs two
  layouts switches the layout.
- **No filters.** OBS's filter chain (gain, compressor, noise gate, chroma key) is
  `https://obsproject.com/kb/filters-guide` (opened) and is a separate spec's worth of work. The one
  exception is audio gain/mute, which is a mixer parameter (§2.3), not a filter.

### 2.3 Audio mixing

Three buses, in this order, and they are not the same thing:

| bus | what | why separate |
|---|---|---|
| **program** | what goes into the composite and into the recording | law 2 (`AGENTS.md:283-284`): the clip must already exist without the AI |
| **monitor** | what the owner hears | **default is OFF and it is never opened implicitly** — `AGENTS.md:341-342` requires saying so out loud before opening an audio device, and OBS makes the same choice a user setting (*"Audio Output Mode: You can set to Capture Only (meaning you will not hear, without Audio Monitoring), or Output desktop audio"*, `https://obsproject.com/kb/video-capture-sources`, opened). That page lists **no default** for it, so OBS's shipped default is **UNVERIFIED here** and must be read from the build, not inferred from the page |
| **chat/voice** | *not in this spec* | a third input path with its own device ladder; it arrives with the streaming milestone and not before |

Per source: `gain` (dB, −∞…+12), `mute`, `pan` is **not** shipped (one program bus, no stereo image to
place). The mix is computed in float32 at the **mix rate**, downsampled by summing with a documented
rule (mean of channels, so a stereo game and a mono mic do not differ by 6 dB), then handed to the
compositor. The ASR sink contract is unchanged and is quoted from the other side of the boundary:
`src/capture/wasapi_audio.h:70-72` (`kAsrSampleRate = 16000`, mono, PCM16) and
`src/asr/constants.py`. **A mic source is 16 kHz mono PCM16 to the ASR and float32 mix to the
compositor — the same two-step the loopback already documents** (`wasapi_audio.h:126-133`: a WASAPI
stream has no format negotiation, so the downmix-then-resample order is forced, "*The conversion
therefore happens HERE, in software, in two documented steps*").

### 2.4 Where the composite sits relative to the existing encode path

```
WGC frame ─┐
camera ────┼─► [ per-source: fit/crop/alpha ] ─► ONE BGRA texture (base canvas)
card ──────┤
image ─────┘                                        │
                                                    ├─► NV12 convert (existing, specs/03 §2.3)
                                                    ├─► audio mix (float32) ─► AAC
                                                    └─► BGRA copy ─► preview swapchain (M1)
                                                             │
                                                     NVENC ─┴─► ring (existing, specs/03 §2.6)
                                                                   └─► cut ─► mp4 (existing §2.7)
```

**One composite, one encoder, one ring.** The composite is *upstream* of NVENC, never a second
encoder. Reason: law 6 (`AGENTS.md:293-299`) makes the encoder the thing that must be proven at
start-up, and two encoders means two chances to fail that proof with one bit of UI. **The stream-out
encode is the only exception and it is M3, because a stream needs a different rate control (§5) —
and that is a measured cost, not a free one (§5.3).**

---

## 3. THE RING FOR AN EXTERNAL FEED — and a refutation

The dispatch brief said: *"a live feed has no 'instant replay' — state what the honest feature is."*
**The first half of that is false for this codebase, and the spec says so rather than building on
it.**

- The ring stores **encoded bitstream entries**, not frames:
  `src/capture/ring_buffer.h:20-25` (`seq`, `size`, `qpc_ns`, `is_idr`), `:81`
  `find_cut_base(t_cut_ns, window_ns, index)`, and `:63-64` `append(data, size, is_idr, …)`.
- **Nothing in it knows where the bytes came from.** A capture-card source produces the same
  `{ptr, size, is_idr, qpc_ns}` tuple that NVENC produced a frame ago. The cut is a pointer flip plus
  a copy (`specs/03-capture-encode.md:146-151`).
- The trigger is **local** for a capture card — the whole point of the box is that the owner is at
  it — so the argument "nobody is at the keyboard to press the key" does not apply here.

**So the honest feature of the capture-card path is:**

1. **Instant replay that works**, on a source that does not come from this machine's compositor.
2. **A latency floor we do not own and must not claim.** The card's HDMI→samples path, its driver and
   its USB/PCIe transport are somebody else's milliseconds. Our contribution is measurable
   (delivery → composite → encode). **The product reports OUR number and never quotes a
   glass-to-glass figure it did not measure.**
3. **Continuous capture, and the honest difference from desktop capture.** For a card the useful
   artefact is usually *the whole session*, not *the last 120 seconds* — the moment happened on
   another machine and, unlike a desktop mistake, **it cannot be repeated**. Therefore the card
   profile's default is a **disk-backed rolling segment writer** (60 s segments, a bounded tail
   arena in RAM for the cut), not a 120 s RAM ring. **DECISION, and it is reversible**: the same
   `RingBuffer` code, with the sink changed from RAM to disk and the budget from law 7's VRAM-derived
   cap to free disk space. The cut semantics are byte-for-byte the existing ones.
4. **The failure that must be loud, and is not a bug:** a capture card with nothing plugged into its
   HDMI input delivers a **valid stream of a constant frame** (black, or the device's no-signal
   colour). That is §4's `no-signal-at-source`, and it is a *warning with a real cause*, not an
   error. See §4.

**What is genuinely different about a card, stated so nobody re-derives it:** it can vanish mid-run
(§1.3 device loss), its clock is not ours (§1.3), and its memory is disk (§5.4). It is **not**
different in geometry, colour space handling, encode settings, or the cut.

---

## 4. THE FAILURE VOCABULARY

**The rule this spec inherits and does not restate:** the state name in the log, the state name on
the HUD and the enum name are the same string (`specs/05-overlay-hud.md:325-330`, and the
`exit3-armB-worker.jsonl` defect it cites), and errors are sticky, never timed out
(`specs/05-overlay-hud.md:403-412`).

### 4.1 The states

| state | meaning | severity | the one datum the message MUST carry |
|---|---|---|---|
| `composite-no-sources` | the scene has zero visible video sources | **refusal** | the count (`0 visible of 3 configured`) |
| `source-missing` | a source in the scene has no bound device | error | the source id and the device state below |
| `device-not-present` | enumeration returned nothing for the requested source type | error | devices found (0) and the API (`MF VIDCAP` / `WASAPI eCapture`) |
| `device-privacy-denied` | Windows camera privacy is off for this app | error | the Settings path — Microsoft: *"Windows allows users to grant or deny access to the device's camera in Windows Settings, under Privacy & Security -> Camera"* (opened, enumerating-video-capture-devices) |
| `device-format-refused` | `SetCurrentMediaType` failed for the type we asked for | error | requested `WxH@fps` and the device's advertised type count |
| `device-open-failed` | an HRESULT failed (activate / reader / start) | error | the raw HRESULT in hex |
| `device-lost` | `WM_DEVICECHANGE` matched our symbolic link | error, sticky | the symbolic link, and `since=` |
| `no-signal-at-source` | frames arriving, format valid, **content constant** | **warning** | the constant-run duration and the frozen frame's hash |
| `source-silent-audio` | audio delivered, peak ≤ `kAudioSilencePeakFloor` | **warning** | the measured peak and the floor, reusing the existing verdict word |
| `encoder-not-armed` | no encoder initialised ⇒ the hotkey is not armed (law 6) | error | the encoder status string |
| `stream-not-connected` | the RTMP session is not up | error, sticky | the connect failure string and the endpoint host |
| `stream-dropping` | frames dropped to hold the bitrate | warning | dropped count / window and the measured send rate |
| `stream-over-budget` | sustained send above the declared ceiling | error | target vs measured kbps |

### 4.2 The wording rule, and the sentence that must exist in the binary

**A device that is silent and that is real must never be reported as a failure to open, and never as
success.** Three sentences, one per case, each produced verbatim by the product:

- nothing is routed in → `silent-device` (this is the **existing** Sotto word and state —
  `src/capture/wasapi_audio.h:79-88` already defines `kSilentDevice`, `kNoSignal`, `kOpenFailed`,
  `kNoEndpoint`, `kDeviceExhausted`, precisely so a silent tap is a *name* and not an empty success;
  and its header states the law at `:36-41`: *"SILENCE IS USUALLY CORRECT BEHAVIOUR … a tap that opens
  and reads silence has NOT failed to open"*). **Broadcast reuses these five words unchanged.** A
  report from either implementation is then comparable with no translation table.
- the card's HDMI input is empty → `no-signal-at-source`, with the duration and the frame hash. The
  remedy is in the message ("plug the source in"), not in a log level.
- the requested format is not supported → `device-format-refused`, quoting OBS's own warning
  (*"If the device does not support the resolution, the source will not display anything"*,
  https://obsproject.com/kb/video-capture-sources, opened), because a user who has seen that failure
  in another tool must not have to learn it twice.

**And the three words that are forbidden in this spec: "no signal", "connection lost", "error".**
Each names no cause and carries no datum. `AGENTS.md:335-336`: *"A failure must never answer as
success"* — and the mirror, which this project has also paid for: **a success must never answer as a
failure**, or the owner learns to ignore red.

### 4.3 Composite-specific, because a composite can lie

A composite can produce a perfectly valid stream of nothing. Therefore:

- **`composite-no-sources` is a REFUSAL, not a warning.** Going live with an empty scene is the
  composite's version of a recording that claims to be armed while it records nothing — the exact
  failure law 6 exists to prevent. The product refuses and says why.
- **A hidden source keeps its audio** unless explicitly muted. OBS's model hides video only; so does
  ours, deliberately, because the failure of "I muted the camera and my microphone went with it" is
  worse than a rectangle on screen.

---

## 5. PARAMETERS — every number, its unit, and why it is that number

### 5.1 Video

| parameter | value | unit | reason |
|---|---|---|---|
| `composite.base` | the capture window's size | px | one number fewer to get wrong; follows `specs/03` §2.1 |
| `composite.output` | **1920×1080** | px | the only display on this box is 1920×1080 (`§1.5`); and `specs/01` §1 sizes every bitrate at 1080p |
| `composite.fps` | **60** gaming / **30** desktop | Hz | `specs/01` §1, already decided and owned by that spec |
| `preview.present_mode` | **waitable object, no vsync wait** | — | a preview that waits for vsync adds a frame of latency to a thing whose entire purpose is latency |
| `preview.scale_filter` | **bilinear** | — | OBS recommends Lanczos-36 for *stream* quality (`broadcasting-guide.md`, opened) and that is the **output** filter, not the on-screen preview. Lanczos-36 on a preview the user reads at arm's length is a cost with no beneficiary |
| `preview.dpi` | `round(24 × dpi/96)` inset | px | the HUD already fixed this rule (`specs/05` §5); a second rule would be a second number to drift |

### 5.2 Capture card

| parameter | value | unit | reason |
|---|---|---|---|
| `card.preferred_format` | the **highest** `MF_MT_FRAME` whose width ≤ 1920 | — | MS: the frame-rate range *"can vary depending on the capture format. For example, at larger frame sizes, the maximum frame rate might be reduced"* (opened, how-to-set-the-video-capture-frame-rate). Choosing the biggest frame first silently drops the frame rate |
| `card.frame_rate` | `MF_MT_FRAME_RATE_RANGE_MAX`, **clamped to 60** | Hz | the profile has no use above 60 and the clamp is what makes the bitrate table below mean something |
| `card.bitrate` | **45 Mbps** at 1080p60 | bits/s | `specs/01` §1 GAMING. Same encode, same ring arithmetic — the card is a source, not a profile |
| `card.segment_seconds` | **60** | s | one segment is the granularity of loss: unplug the card and at most one segment is malformed, not the whole recording |
| `card.tail_arena_seconds` | **10** | s | RAM for the cut only. A cut must be a pointer flip (law 2), so the *cut* memory is RAM even when the *history* is disk. 10 s covers the hotkey latency a human actually has |
| `card.ring_min_idr` | **2** | entries | already the invariant: `idr_count_at_least_two_locked` (`src/capture/ring_buffer.h:97`) and the eviction rule (*"eviction NEVER removes the last IDR still held"*, `:9-10`) |
| `card.no_signal_window` | **2.0** | s | a constant-frame run longer than this is `no-signal-at-source`. Shorter and a legitimately static scene (a paused game) trips it |
| `card.no_signal_variance` | **0** | LSB per channel, max over the window | "constant" is exactly this, not a threshold. A frozen JPEG-compressed frame is not bit-identical, so the check is on the **decoded luma plane**, after the format's own compression — the one place where "constant" is a real, testable predicate |

### 5.3 Encode and stream

| parameter | value | unit | reason |
|---|---|---|---|
| `stream.codec` | **H.264 High**, NVENC | — | NVIDIA's platform table lists H.264 support for every destination including Twitch; AV1 is YouTube/Discord only
([broadcasting-guide.md](https://www.nvidia.com/en-us/geforce/guides/broadcasting-guide.md), opened) |
| `stream.rate_control` | **CBR** | — | same page: *"Rate Control: Select CBR"* |
| `stream.keyframe_interval` | **2** | s | same page: *"Keyframe Interval: Set to 2. Streaming platforms may limit what you can select here, and most require a setting of 2."* It also matches our forced-IDR grid (`specs/03` §2.4), so the stream's GOP and the recording's cut grid are the **same** numbers |
| `stream.preset` | **P6** | — | same page: *"Most users should use P6: Slower (Better Quality)"* |
| `stream.bitrate` | **~0.036 bpp** (`specs/01` §1), clamped to **6 000 kbps** | bits/s | the bpp rule is the owner's own number; the clamp is Twitch's current cap, named on the same page |
| `stream.bitrate_vs_upload` | **75 % of measured stable upload** | — | stated twice, by NVIDIA (*"We want to use around 75% of your upload speed"*) and by OBS (*"A good starting point is to set your bitrate to 75% of your total upload speed"*, `https://obsproject.com/kb/stream-connection-troubleshooting`, opened) |
| `stream.transport` | **RTMP out** (`rtmp://` / `rtmps://`) | — | OBS's implementation is `plugins/obs-outputs/rtmp-stream.c` + `flv-mux.c` + `flv-output.c`, and its services file carries `Server.AutoRTMPS = "Auto (RTMPS, Recommended)"` (all opened: `https://raw.githubusercontent.com/obsproject/obs-studio/master/plugins/obs-outputs/rtmp-stream.c`, `.../flv-mux.c`, `.../data/locale/en-US.ini`). **RTMPS by default**, because the stream key is a bearer credential and OBS's own page warns *"Be careful with your stream key! Anyone with it can take over your stream"* (NVIDIA guide, opened) |
| `stream.connections` | **2** | concurrent sessions | **the price of streaming is stated, not hidden:** OBS separates record and stream outputs, and this box's measured NVENC ceiling is 10 held sessions with the 11th refused (`docs/research/03-nvenc-sessions.md:52-62`). 2 is 20 % of a measured wall, and the start-up check classifies the refusal by **status 21** — which that receipt measured, against the documented code |
| `stream.split_encode` | **off** | — | OBS 31 exposes it and says it *"Requires NVIDIA Ada Generation GPU with two or more NVENC engines"* and *"at low bitrates there may be a visible seam between the two frame halves"* (`https://obsproject.com/kb/advanced-nvenc-options`, opened). This box has **2 engines** (`specs/03-capture-encode.md:33`), so the option is *available* — and a visible seam down the middle of a broadcast composite is exactly the defect a viewer notices, so the prototype does not turn it on. Revisit only with a seam-measuring instrument |

### 5.4 Latency budget — stated as a budget, with the parts we do not own marked as such

| stage | budget | owner | status |
|---|---|---|---|
| card HDMI → driver samples | **UNKNOWN** | the device | not measurable by us; **the product must not print a number here** |
| driver → `IMFSourceReader::ReadSample` | **UNKNOWN**, vendor- and driver-dependent | the driver | FFmpeg exposes `audio_buffer_size` for the audio half precisely because it *"can directly impact latency"* (opened) |
| delivery → composite present | **≤ 1 frame** (16.7 ms @60, 33.3 ms @30) | us | by construction: composite the newest frame of each source, present, drop the old |
| composite → NVENC accept | **≤ 1 frame** | us | measured cost at 1080p is *convert 0.010 ms + encode ~5 ms* (`specs/03-capture-encode.md:310-311`), which leaves room for ~200 fps |
| stream end-to-end (glass to viewer) | **UNKNOWN** | the internet + the platform | the only honest thing to print is the **measured send rate and drop count**, which is §4's `stream-dropping` |

**The rule: every latency number the UI prints is one we measured ourselves, with the stage named.
A number from any other stage is printed as `not measured`.**

---

## 6. PASS CONDITIONS — one per milestone, observable, each with a RED arm

House rule: *"Every gate ships BOTH colours: the pass, and a deliberately-broken copy that must go
RED. A control that stays green is a failing control"* (`AGENTS.md:332-334`).

| # | milestone | PASS condition (observable) | instrument | the RED arm |
|---|---|---|---|---|
| **P0** | composite core | with two synthetic colour sources in known positions, the output texture has the expected pixels at both positions and z-order is honoured | `_06-composite-oracle.py` | swap index for z-index → overlap assertion fails |
| **P0b** | audio mix | a −6 dBFS 1 kHz tone on source A and silence on B reads **−6 dB ± 0.5** at the mix bus | `_06-audiomix-oracle.py` | sum instead of mean → −3 dB, fails |
| **P1** | preview window | the window is mapped and its pixels change within **≤ 1 frame** of a source change, measured as the presented frame's own `SystemRelativeTime` | `_06-preview-latency-probe.py` | present the previous frame → 2 frames, fails |
| **P1b** | second-monitor placement | with `EnumDisplayMonitors` returning ≥2 monitors, the preview lands on the non-primary one; **with 1 monitor (this box, MEASURED) it lands on the primary and says so** | `_06-display-probe.py` | always-on-primary → fails on the 2-monitor arm only |
| **P2** | mic capture | the `HyperX Quadcast` endpoint enumerates, a clap reaches the program bus above the silence floor, and **a silent tap reports `source-silent-audio` with the peak and the floor — never `ok`** | `_06-mic-oracle.py` | return the empty success → the silence arm goes RED |
| **P3** | stream out | an RTMP **listener under our control** receives the stream; a deliberately late keyframe or a 2× bitrate produces `stream-dropping` with a count | `_06-rtmp-sink.py` | drop the reconnect → `stream-not-connected` never fires, fails |
| **P3b** | ring-vs-stream independence | cutting during a live stream produces a byte-identical clip whether the stream is on or off (same encode inputs) | `_06-cut-determinism.py` | encode the preview texture instead of the composite → hashes differ |
| **P4** | capture card | MF enumeration of the `HD Pro Webcam C920` yields exactly 1 device with a **non-empty symbolic link**, and the same device re-opens after `ActivateObject` release + re-acquire | `_06-mf-enum-oracle.py` (the webcam is a UVC capture device and stands in for a UVC capture card; **it is not a capture card and does not close the PCIe question**) | key the config on friendly name → the two-C920 case cannot be told apart, fails |
| **P4b** | device loss | a synthetic `WM_DEVICECHANGE` whose `dbcc_name` matches the stored symbolic link drives `device-lost` in ≤ 1 s; a `WM_DEVICECHANGE` for a **different** link changes nothing | `_06-device-loss-oracle.py` | compare on friendly name → the control arm fires, fails |
| **P4c** | no-signal | 2.0 s of a constant decoded luma plane reports `no-signal-at-source` with the hash; **1.9 s does not** | `_06-nosignal-oracle.py` | window at 1.0 s → the negative arm false-positives, fails |

**UNKNOWNS this spec refuses to close without a measurement, with the instrument named:** end-to-end
card latency (needs the device); NVENC throughput at 4K60 (needs `nvenc-probe` at 3840×2160, which
was never run); whether a PCIe card enumerates through MF at all (**UNMEASURED — no such device on this
box**, see §8).

---

## 7. ORDERING — cheapest and most valuable first, and what depends on what does not exist

**The dependency graph, honestly: none of the composite exists yet.** MEASURED 2026-10-08 by listing
`src/capture/`: there is **no** `composite.*`, **no** preview window, **no** MF video source and
**no** RTMP/socket file — the directory holds `common, d3d11_ctx, main, mp4_writer, nvenc_encoder,
nv12_convert, replay, ring_buffer, trigger, wasapi_audio, wgc_capture` plus tests. Broadcast's M0–M1 are new code; M2–M3 are new code on
top of an existing audio tap; M4 is new code on top of an existing frame pipeline.

| order | milestone | cost | depends on | value | why here |
|---|---|---|---|---|---|
| **1** | **M0 — composite core + preview window** (P0, P1) | one new D3D11 pass, one window | `D3d11Context` (`d3d11_ctx.h:21-37`) only | **highest** | it is the piece Broadcast *is*, and it is the piece the capture card later plugs into. Doing it first means M4 is a source, not a feature |
| **2** | **M1b — audio mix + mic** (P0b, P2) | small | the existing WASAPI tap (`wasapi_audio.h:91-103`, `audio_state_for`) | high | the composite without audio is a screencast; the Sotto caption also arrives on this bus, so the audio lane's output becomes *visible* for the first time |
| **3** | **M2 — RTMP out** (P3, P3b) | medium: a mux and a socket | M0's encoder output | high, but not first | it is the only milestone with a **second NVENC session** and the only one that touches the network; both are places where a first version goes wrong in ways the other milestones do not |
| **4** | **M3 — camera as a source** (P4's enumeration half) | medium | M0's slot + the MF path | medium | it is the **same code** as the capture card; it is built early **only because the hardware is on this box** and the capture card is not. This is the one place where the ordering follows the bench, not the market |
| **5** | **M4 — capture card proper + disk segments** (P4, P4b, P4c) | largest | M0, M3, and **hardware the owner must buy** | medium-high for the right user, zero for the owner today | §3's `card.*` parameters; cannot be gated on this box |

**What depends on parts that do not exist yet, stated plainly:** M0 depends on a composite that is
this spec's own deliverable; M2's stream and the recording are two encoder sessions because their rate
control differs (§5.3) — **that is the only place this design spends a second NVENC session, and it is
paying for a decision, not for a feature**; M4's disk-backed segments depend on `mp4_writer`
(`src/capture/mp4_writer.h`) being able to write into a segment and be closed at a keyframe, which it
is designed for (`specs/03` §2.7 remux-only) but has never been asked to do.

---

## 8. WHAT THIS SPEC DELIBERATELY DOES NOT DO

- **It does not promise glass-to-glass latency.** §5.4, and the rule that we print only what we measured.
- **It does not build a PCIe/vendor-SDK capture path.** OBS needs the Blackmagic SDK
  (https://obsproject.com/kb/video-capture-sources, opened) and ships `decklink`/`aja` as separate
  plugins. A UVC capture card is in scope; a PCIe card is a named exclusion with the reason.
- **It does not do scenes-as-containers, transitions, filters or audio plugins.** §2.2. The feature is
  one composite; a filter chain is a different spec.
- **It does not do chat, alerts or platform logins.** The stream takes a URL and a key. OBS ships
  **66** locale files for platform services (`plugins/rtmp-services/data/locale`, MEASURED by
  directory listing 2026-10-08) — that is a
  product decision about third-party accounts, and `AGENTS.md:285-286` (law 3, local-first, no cloud)
  argues against embedding them here.
- **It does not open a playback device by itself.** The monitor bus exists, defaults to OFF, and says
  so when turned on (`AGENTS.md:341-342`).
- **It does not re-open instant replay's storage model for desktop.** Only the card profile moves to
  disk segments (§3).

---

## APPENDIX A — every external source, opened on this machine

| # | URL | what it is cited for |
|---|---|---|
| 1 | https://learn.microsoft.com/en-us/windows/apps/develop/media-authoring-processing/screen-capture | a capture item comes from a display or a window |
| 2 | https://learn.microsoft.com/en-us/windows/win32/api/windows.graphics.capture.interop/nf-windows-graphics-capture-interop-igraphicscaptureiteminterop-createformonitor | `CreateForMonitor(HMONITOR,…)`; no device overload exists |
| 3 | https://learn.microsoft.com/en-us/windows/win32/medfound/audio-video-capture-in-media-foundation | UVC 1.1 floor; friendly name "might not be unique"; symbolic link "uniquely identifies the device" |
| 4 | https://learn.microsoft.com/en-us/windows/win32/medfound/enumerating-video-capture-devices | `MFEnumDeviceSources` + `VIDCAP_GUID` + `ActivateObject`; the camera privacy setting |
| 5 | https://learn.microsoft.com/en-us/windows/win32/medfound/how-to-set-the-video-capture-format | format enumeration and `SetCurrentMediaType`; device default when unset |
| 6 | https://learn.microsoft.com/en-us/windows/win32/medfound/how-to-set-the-video-capture-frame-rate | `MF_MT_FRAME_RATE_RANGE_MAX/MIN`, `MF_MT_FRAME`; rate falls with frame size |
| 7 | https://learn.microsoft.com/en-us/windows/win32/medfound/handling-video-device-loss | `RegisterDeviceNotification`/`KSCATEGORY_CAPTURE`, `WM_DEVICECHANGE`, symbolic-link compare |
| 8 | https://learn.microsoft.com/en-us/windows/win32/api/mfreadwrite/nn-mfreadwrite-imfsourcereader | `IMFSourceReader`, `ReadSample`, `MFCreateSourceReaderFromMediaSource` |
| 9 | https://learn.microsoft.com/en-us/windows/win32/directshow/video-capture | DirectShow is legacy; Media Foundation supersedes it |
| 10 | https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording | the WASAPI sequence; the microphone is the same minus the loopback flag |
| 11 | https://ffmpeg.org/ffmpeg-devices.html | `dshow` options: `list_options`, `audio_buffer_size` ("can directly impact latency"), `use_video_device_timestamps` ("unreliable timestamps"), `show_video_device_dialog` |
| 12 | https://www.nvidia.com/en-us/geforce/guides/broadcasting-guide.md | base vs output canvas; 75 % of upload; codec-per-platform table; CBR, keyframe 2, P6, High Quality; Twitch 6 000 kbps cap; the stream-key warning |
| 13 | https://www.nvidia.com/en-us/geforce/broadcasting/broadcast-app/faq.md | NVIDIA Broadcast presents itself as **a virtual camera/microphone/speaker device**, so it is a *source in our model*, not a feature we reimplement |
| 14 | https://www.nvidia.com/en-us/geforce/guides/broadcast-app-setup-guide.md | Broadcast's virtual-device model; "leave settings as default, or match"; GPU-utilisation meter |
| 15 | https://www.nvidia.com/en-us/software/nvidia-app.md | ShadowPlay "DVR-style Instant Replay, enabling users to instantly save the last 30 seconds" — the number our ring already exceeds |
| 16 | https://www.nvidia.com/en-us/geforce/broadcasting.md | NVENC is *"an independent section of your GeForce GPU used to encode video"*; the "Go Live … Broadcast on the most popular livestreaming platforms" framing, i.e. NVIDIA sells streaming as **an output**, not as a device mode |
| 17 | https://obsproject.com/kb/video-capture-sources | DirectShow on Windows; "the source will not display anything" for an unsupported resolution/fps; Audio Output Mode; custom audio device; buffering; Blackmagic needs the vendor SDK |
| 18 | https://obsproject.com/kb/sources-guide | source list = z-order; positioning and sizing |
| 19 | https://obsproject.com/kb/stream-connection-troubleshooting | 75 % bitrate rule; dropped frames are the program shedding frames, not the server |
| 20 | https://obsproject.com/kb/advanced-nvenc-options | OBS 31's NVENC surface (split encode, CBR/tune/preset) |
| 21 | https://raw.githubusercontent.com/obsproject/obs-studio/master/plugins/win-dshow/win-dshow.cpp | the device-source implementation, `RES_TYPE`/`FPS_HIGHEST`, and its own *"TODO: handle disconnections"* |
| 22 | https://raw.githubusercontent.com/obsproject/obs-studio/master/plugins/win-wasapi/win-wasapi.cpp | `eCapture` vs `eRender`, shared mode, the loopback flag |
| 23 | https://raw.githubusercontent.com/obsproject/obs-studio/master/libobs/obs-scene.c | `crop_to_bounds`, `OBS_BOUNDS_SCALE_*` — the geometry model we copy |
| 24 | https://raw.githubusercontent.com/obsproject/obs-studio/master/libobs/obs-video.c | base canvas vs output canvas |
| 25 | https://raw.githubusercontent.com/obsproject/obs-studio/master/plugins/obs-outputs/rtmp-stream.c | OBS's RTMP client |
| 26 | https://raw.githubusercontent.com/obsproject/obs-studio/master/plugins/obs-outputs/flv-mux.c | the FLV muxer, hard-coded H.264 + AAC |
| 27 | https://raw.githubusercontent.com/obsproject/obs-studio/master/plugins/rtmp-services/data/locale/en-US.ini | `Auto (RTMPS, Recommended)`; the stream key is a credential |
| 28 | https://api.github.com/repos/obsproject/obs-studio/contents/plugins | `decklink`, `aja`, `win-dshow`, `win-capture`, `win-wasapi` are **separate plugins** |
| 29 | https://www.elgato.com/us/en/p/game-capture-4k60-pro | a real card's shape: capture table (1080p30…240, 1440p, 4K30/60 with HDR variants), HDMI 2.1 in / 2.0 out, PCIe 2.0 ×4 **or** USB-C 3.2 Gen1 5 Gbps, and the footnote that *"HDR cannot be captured at all resolution and frame rate combinations"* — i.e. **the card advertises its own format list, exactly like a UVC device** |
| 30 | https://www.elgato.com/us/en/p/game-capture-hd60mk2 | (attempted; 404 on this host — **not cited for anything**) |

**Two NVIDIA claims this spec makes that are NVIDIA's own and are cited as such:** the streaming
platform codec table and the 6 000 kbps Twitch cap (source 12) are *NVIDIA's* statements about *their
recommendations*, not platform specifications. Where a platform number is load-bearing (the 6 000 kbps
clamp) it is re-checked against the platform before shipping, and until then the clamp is a
**DECISION**, marked as one in §5.3.

---

## APPENDIX B — the reviewer's verdict

*(filled in by the dispatched verifier; see the lane report for the verbatim verdict.)*