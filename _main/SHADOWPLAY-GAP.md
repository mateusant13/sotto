# SHADOWPLAY-GAP

Feature-gap table: **NVIDIA ShadowPlay / NVIDIA app overlay** vs **Sotto** (`H:\sotto`), measured 2026-10-07.

**Method.** The ShadowPlay column was read from NVIDIA's own pages *before* any Sotto code was opened
(§ Sources). The Sotto column was taken from the code, not from this repo's documents — an
exhaustive grep of `app/` and `worker/` for `screen_capture|record|ffmpeg|nvenc|camera|webcam|mp4|
frame` returns **only** `docs/`, the research scratch file `pesquisarsobre.txt`, and a prototype
under `_moved/aireplay/`. None of those are the product. The live app has no video path at all.

`worker/README.md:36-38` warns that its own line numbers drift; the line numbers below were re-grepped
against the current file, not copied from the README.

## Feature-gap table

| Feature | ShadowPlay has | Sotto has | Evidence (file:line) | Gap size | Blocking dependency |
|---|---|---|---|---|---|
| Instant Replay (rolling buffer) | Rolling DVR-style buffer, length configurable via Settings cog (30 s default), `Alt+Shift+F10` saves the last moments | **ABSENT** — no video capture exists | `worker/sotto_worker.py:11-14` (capture is an *audio* `InputStream`); `worker/sotto_worker.py:1` ("system audio in, streamed captions out") | **L** | Windows.Graphics.Capture / DXGI desktop duplication + a video encoder |
| Manual Record (start/stop) | `Alt+F9` start/stop; up to 8K HDR 30 fps, 4K HDR 120 fps | **ABSENT** | same as above | **L** | same as above |
| Full-screen / display capture | Yes, game/app/desktop | **ABSENT** | `worker/sotto_worker.py:11-14` | **L** | WGC; multi-monitor + HDR path |
| Region capture | Yes, configurable capture rectangle | **ABSENT** | `worker/sotto_worker.py:11-14` | **M** | Crop step on top of full capture; DPI/`ContentScaling` handling |
| Multi-capture (simultaneous regions) | Yes, multiple simultaneous captures | **ABSENT** | `worker/sotto_worker.py:11-14` | **L** | N concurrent WGC items + N encoder sessions + compositor |
| Webcam overlay (picture-in-picture) | Yes, camera feed composited into the capture | **ABSENT** | grep over `app/` + `worker/`: no `camera`/`webcam` symbol in live code | **M** | Second capture source (Media Foundation / DirectShow) + alpha compositing |
| Broadcast video effects (background removal/blur, virtual key light, eye contact, auto-frame) | Yes, all AI-accelerated | **ABSENT** | `worker/models/` holds 9 **ASR/LLM** dirs only, no vision/effect model (see dir list below) | **L** | NVIDIA Maxine SDK + RTX GPU; a full vision pipeline Sotto does not have |
| Broadcast audio effects (noise / echo removal, Studio Voice) | Yes, one toggle | **PARTIAL** — a causal streaming spectral gate exists, but it is a floor attenuator, not a separator, and is **off by default** | `worker/denoise.py:1-28`; `worker/denoise.py:29` ("WHAT THIS DOES NOT DO"); `worker/config.json:2` (`use_denoise` false by default; measured −0.21 dB) | **S** | Nothing structural — a real separator (RNNoise/DeepFilterNet) for the M→S step |
| Performance overlay (FPS, FPS 1 % Low, GPU/CPU util, VRAM, temps, PC/system latency) | Yes — the Statistics screen is fully position/colour/size configurable | **ABSENT** — the panel's stats channel is explicitly *not wired* | `app/panel/panel.js:2050-2052` ("NOT wired to anything today: the shell exposes neither `onStats` nor `getStats`"); `app/panel/panel.js:2088-2089` | **M** | A sensor source (PDH / NVML / D3DKMT) + an always-on-top transparent overlay window |
| Game Filters / RTX HDR / RTX Dynamic Vibrance | Yes, real-time post-process, 1 200+ titles | **ABSENT** | `app/` + `worker/` grep: no filter/shader/HDR path | **L** | A DXGI post-process hook (or ReShade-style proxy) — an entire rendering-injection layer |
| Highlights (auto-capture of key moments) | Yes, automatic in supported games | **ABSENT** for video; nearest analog is a **caption** history | `app/panel/history-store.js` (text lines, not frames) | **M** | Needs the capture pipeline first, then a per-title trigger |
| Save + clip trim on a timeline | Yes, trim the saved clip before it lands | **ABSENT** — there is no media to trim | `worker/sotto_worker.py:2498` writes `.wav` only as a **temp** batch artefact (`tempfile.mkdtemp`); `soundfile` is otherwise **read-only** (`sotto_worker.py:1624`, `:2642`) | **M** | Needs a real recording on disk, then a trim UI over a muxer |
| Gallery (sort/view past captures) | Yes, per-game, stills vs video | **PARTIAL** — history is text, not media | `app/panel/history-store.js:108`; `worker/qwen_summary.py:1417-1434` (names/summarises **recordings**, i.e. caption runs) | **M** | Same as above |
| Streaming (RTMP / Broadcast as virtual device) | Yes | **ABSENT** | grep for `rtmp|obs\b` over live code: no hits | **L** | A muxing/publishing stack + Broadcast-style virtual device registration |
| Desktop (system) audio capture | Yes, system audio is the default source | **PRESENT** — driver-free WASAPI loopback, no virtual cable needed | `worker/wasapi_loopback.py:30-31`; `worker/sotto_worker.py:11-14`; `worker/config.json:6` | **S** | — |
| Microphone capture | Yes, mic toggle + push-to-talk + mic boost | **ABSENT by design** — the device ladder explicitly skips microphone endpoints | `worker/sotto_worker.py:1082` (`if "micro" in low or "mic" in low: continue`); `:1086` (tail is "remaining **non-microphone** input") | **S** | Nothing structural — it is a deliberate filter, not a missing capability |
| Per-source audio mixing / volume | Yes, multi-track audio, mic on a separate track | **ABSENT** | no mix/gain-bus code in `worker/`; `worker/sotto_worker.py:1120-1128` applies a single auto-gain target, not per-source volume | **S** | A mixer stage (two taps → two gains → one bus) |
| Hotkeys | Yes — `Alt+Z` overlay, `Alt+F9` record, `Alt+Shift+F10` replay, `Alt+F1` screenshot, `Alt+F2` photo mode, all rebindable | **PARTIAL** — exactly one global hotkey with a fallback chain | `app/webview/sotto_webview.py:1202-1203` (`RegisterHotKey` + `MOD_NOREPEAT`); `:1259` (`HOTKEY_FALLBACKS`); `:1220` (`WM_HOTKEY` pump) | **S** | Nothing structural — the mechanism is proven, the set is just small |
| Desktop app shell (the app itself) | Yes — NVIDIA App: drivers, Graphics, System, Redeem, Discover | **PRESENT** — pywebview/WebView2 shell, tray, no native build step | `app/webview/sotto_webview.py:3034-3035` (`self.hotkey`, `self.tray`); `app/webview/run.cmd:74` | **S** | — |
| Local-first / no content telemetry | Opt-in telemetry only (config/usage + crash data) | **AHEAD** — fully local models, no content egress | `worker/models/` (9 local dirs, list below); `worker/README.md:117-130` | — | — |

`worker/models/` (measured, 9 dirs, all ASR/LLM — no vision or effect model):
`nemotron-3.5-asr-streaming-0.6b-{fp16,fp32,int4,int8}`, `parakeet-redux-{onnx-int4,reference,ternary}`,
`qwen3-0.6b-arm-int4`, `qwen3.5-0.8b-ortgenai-cpu`.

### Source confidence

Region capture, multi-capture and the webcam pip are configured in the NVIDIA app's overlay Settings
cog, which NVIDIA describes collectively ("numerous options to customize these features") rather than
in a per-feature page I could fetch. They are real product features, but the citation below is for the
overlay as a whole, not a per-feature spec.

## The three largest gaps

**1. There is no video capture pipeline at all — L.**
Everything else is downstream of it: Record, Instant Replay, region, multi-capture, webcam pip,
Highlights, trim, Gallery and streaming all need frames to exist first. Sotto's worker is
audio-in/captions-out by construction (`worker/sotto_worker.py:11-14`), and the only encoder work in
the repo is a `_moved/` prototype (`_moved/aireplay`, which cut an offline H.264→mp4 clip *without*
WGC or NVENC).
**First deliverable:** one WGC desktop-capture session that writes a 10-second H.264 `.mp4` to disk,
with the wall-clock encode time and the frame count printed — the same "offline cut" receipt the moved
prototype already produces, but with live frames.

**2. Instant Replay rolling buffer + save — L.**
A continuous ring buffer that survives "press one key, get the last 30 seconds", plus a save path that
muxes it. This is ShadowPlay's signature feature and Sotto has nothing comparable.
**First deliverable:** a fixed-length ring buffer holding N seconds of encoded frames in RAM, where one
hotkey flushes the previous N seconds to a file and does not interrupt the ongoing capture.

**3. Performance monitoring overlay — M.**
Independent of the video work (it needs no encoder, so it can run as a parallel track), and the panel
is already built to consume it — `app/panel/panel.js:2088-2089` mounts the level/stats meter but bails
out because the shell exposes no `onStats`/`getStats` (`panel.js:2050-2052`).
**First deliverable:** one always-on-top transparent overlay window showing FPS, GPU utilisation and
VRAM, fed by a single sampler thread, wired through the `onStats` bridge the panel already expects.

### Notes for whoever picks these up

- **Broadcast effects are the hardest dependency-bound item** and are deliberately not in the top three:
  they need the Maxine SDK plus an RTX GPU, and Sotto has no vision pipeline of any kind today.
- **Do not trust this repo's own docs on Sotto's capabilities.** `worker/README.md` is careful about its
  own line-number drift (`worker/README.md:36-38`) and is honest about past errors, which is why it was
  usable. The `docs/` tree and `pesquisarsobre.txt` describe an NVENC + WGC + circular-buffer
  architecture that does **not** exist in the product.
- Every ABSENT verdict above was produced by a grep over `app/` and `worker/` that surfaced only docs,
  scratch notes and `_moved/`.

## Sources

- NVIDIA app product page — Record (up to 8K HDR 30 fps / 4K HDR 120 fps), Instant Replay (30 s default,
  configurable), Highlights, AV1, statistics overlay, Freestyle filters:
  <https://www.nvidia.com/en-us/software/nvidia-app.md>
- NVIDIA app release highlights — AV1 for Record/Instant Replay/Highlights, 240 FPS ShadowPlay recording,
  default bitrate by resolution, microphone selection and boost, desktop capture via hotkeys, gallery,
  Highlights summary window, statistics overlay fixes:
  <https://www.nvidia.com/en-us/software/nvidia-app/release-highlights.md>
- NVIDIA app launch article — `Alt+Z` overlay, `Alt+F9` record, `Alt+Shift+F10` instant replay,
  `Alt+F1` screenshot, `Alt+F2` photo mode, microphone + push-to-talk, multi-track audio, gallery,
  1 200+ game filters, RTX HDR, RTX Dynamic Vibrance, Statistics screen, the app's own tabs:
  <https://www.nvidia.com/en-us/geforce/news/nvidia-app-download-and-features.md>
- NVIDIA Broadcast app — noise removal, room echo removal, Studio Voice, virtual background/replacement/
  blur, virtual key light, eye contact, video noise removal, auto frame:
  <https://www.nvidia.com/en-us/geforce/broadcasting/broadcast-app.md>

**Dead ends** (recorded so nobody re-fetches them): `https://www.nvidia.com/en-us/geforce/living/` and
`https://nvidia.custhelp.com/app/answers/detail/a_id/4655` both return not-found — NVIDIA retired the
old ShadowPlay pages. Use the four sources above.