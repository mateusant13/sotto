# SHADOWPLAY PARITY — what NVIDIA actually ships, and what Sotto actually has

**Lane:** `ParityV2` · **date:** 2026-10-07 · **anchor:** `7744def` (branch `docs/parity-1`, worktree `H:\sotto-wt\parity`)
**Scope:** `_main/SHADOWPLAY-PARITY.md` + `_main/parity/`. No `src/` touched.

This is the parity research the project goal asked for ("research online before
designing") and which had never been done. It is a **read-only comparison**: the
left column is what NVIDIA documents, the middle is what the Sotto repo actually
claims, and the right column is the gap. Nothing here was inferred from the
product name — Sotto is described in its own files as a *replay + memory* app, and
that framing is load-bearing for most of the verdicts below.

**Tagging rule.** Every capability carries a source URL. Anything I could not
attach a URL to is written **UNSOURCED** rather than filled in from memory.
NVIDIA's own pages are marked `[N]`; secondary sources are marked `[S]`.

---

## 0. HOW TO READ THIS

The status vocabulary is deliberately blunt:

- **DONE** — implemented *and* measured on this box, with the receipt named.
- **PARTIAL** — a real part exists; the parity-relevant part does not.
- **NOT STARTED** — zero code, zero spec, zero mention. **This is most rows.**
- **SPEC-ONLY** — written down in a spec, no implementation.

A row marked NOT STARTED is not a criticism of the engineering. The engineering
that exists (NVENC sessions, the ring, the cut) is real and measured. The finding
is narrower and more useful: **Sotto is not currently a ShadowPlay clone, and its
own docs do not claim to be one.** Most of the gap is a *scope* gap, not a
*quality* gap.

### Sources actually fetched vs. cited-but-not-fetched

Fetched and read in full this lane:

| id | URL | how |
|---|---|---|
| N1 | https://www.nvidia.com/en-us/software/nvidia-app/ | `.md` alternate, full text |
| N2 | https://www.nvidia.com/en-us/geforce/broadcasting/broadcast-app/ | `.md` alternate, full text |

Cited from NVIDIA but **body not fetched** (page is JS-only or `.md` is not
published for that path; content below is from the search index and is marked
**VERIFY** at each use):

| id | URL | why not fetched |
|---|---|---|
| N3 | https://www.nvidia.com/en-us/geforce/guides/gfecnt/geforce-experience-shadowplay-is-now-share/ | `.md` alternate returns NVIDIA 404 |
| N4 | https://www.nvidia.com/en-us/geforce/news/geforce-experience-brodcasting-tutorial/ | not fetched; index snippet only |
| N5 | https://www.nvidia.com/en-us/geforce/forums/instant-replay-recording/15/556998/instant-replay-maximum-length-is-too-short/ | NVIDIA forum, index snippet only |

Secondary sources, read this lane:

| id | URL |
|---|---|
| S1 | https://gamerhardware.org/nvidia-shadowplay-recording-guide/ |
| S2 | https://grokipedia.com/page/Nvidia_ShadowPlay |
| S3 | https://insights.gg/blog/what-is-instant-replay-gaming |
| S4 | https://recorder.easeus.com/screen-recording-resource/how-to-use-nvidia-shadowplay.html |
| S5 | https://www.reddit.com/r/nvidia/comments/v4v8gw/why_in_the_world_doesnt_shadowplay_have_multiple/ |
| S6 | https://www.reddit.com/r/nvidia/comments/1bb1jfd/instant_replay_users_how_much_recorded_time_do/ |

`nvidia.custhelp.com` (a.k.a. the NVIDIA knowledge base, where the overlay
manual and the shortcuts list normally live) was **DOWN** for the whole lane —
it returned an Oracle "Technical Difficulties" incident page on every attempt.
That is the single biggest hole in this document and it is the reason the
hotkey row is PARTIAL rather than DONE. See §6.

---

## 1. THE PARITY TABLE

`ShadowPlay` column = the real number where NVIDIA states one.
`Sotto` column = what the repo claims. Evidence column = the Sotto file that
proves the status, so every verdict is re-checkable.

| # | Capability | ShadowPlay (real number) | Sotto status | Evidence | Gap |
|---|---|---|---|---|---|
| 1 | **Instant replay rolling buffer** | Default **30 s** saved on hotkey [N1]. Configurable **30 s → 20 min** [S1][S2][S3]; NVIDIA's own guide says "the last **20 minutes**" [N3, **VERIFY**]. The 20-min cap was bypassable in GeForce Experience via a registry edit and that route is gone in NVIDIA App [N5, **VERIFY**]. | **DONE (and exceeds)** | `_moved/aireplay/specs/01-capture-modes-and-scheduling.md` §1, §2 — GAMING **120 s**, DESKTOP **600 s** default; `specs/03-capture-encode.md` §2.6 | **None — Sotto's default memory is 4–20× longer than ShadowPlay's.** This is the one row where Sotto is ahead. It costs RAM: 675 MB @1080p60 gaming, measured peak RSS = 48 MB + ≈1.02 × ring capacity (`specs/03` §2.6 RESOLVED). |
| 2 | **Save-last-N-seconds hotkey** | `Alt+F10` saves the buffer; `Alt+Shift+F10` toggles replay on/off [S1][S4] | **NOT STARTED** | `_moved/aireplay/ROADMAP.md` §0c — "**No hotkey exists.**" `Select-String` for `RegisterHotKey\|GetAsyncKeyState\|WM_HOTKEY\|SetWindowsHookEx\|GetKeyState\|VK_` across **ALL** of `src/capture/*.cpp\|*.h` → **0 hits** | **The product's whole promise.** Sotto's cut is *time-triggered* (`cfg.cut_at_s`). The named seam is `{"cmd":"cut"}` on stdin; acceptance = clip on disk in < 1 s with zero `ring_dropped`. Until this lands, Sotto has a ring but no *instant replay*. |
| 3 | **Manual record (start/stop)** | `Alt+F9` [S1][S4]; **8K HDR @30 fps** or **4K HDR @120 fps** [N1]; **AV1** on RTX 40-series [N1]; older guide cites 60 fps up to 4K, full-screen and windowed [N3, **VERIFY**] | **NOT STARTED** | No manual-record mode in any spec. `specs/03` §2.4 ships the H.264 NVENC arm only; §6 names "no HEVC/AV1/AMF/QSV arm" | Sotto's capture is **continuous ring only**. It has no notion of "record on demand until stopped", and cannot reach 4K60 or any AV1. Bitrate ceiling today is **45 Mbps @1080p60** (`specs/01` §1). |
| 4 | **Full-screen capture** | Yes — NVIDIA's guide states recording "for both full screen and windowed modes" [N3, **VERIFY**] | **PARTIAL** | `specs/03-capture-encode.md` §2.1 — WGC capture item built via `CreateForWindow`/`CreateForMonitor`, **no picker, no consent dialog** | Mechanically the harder case (fullscreen/exclusive) is explicitly **UNKNOWN** and *not measured*: `specs/03` §4 "WGC on protected content / exclusive fullscreen", §6. DRM/exclusive-fullscreen behaviour is named as a gap, not a capability. |
| 5 | **Window capture** | Yes [N3, **VERIFY**] | **PARTIAL** | `specs/03` §2.1 `WgcCapture::startForWindow(hwnd)`; §6 "**`--monitor` … was never run**" | The window path is written. The monitor/full-desktop path is **implemented but never executed** (`--monitor` never run). Also: the **yellow WGC border stays** — `specs/03` §4 and §6 both say the prototype accepts it and that a borderless recorder needs a packaged app with a manifest capability. |
| 6 | **Game filters (Freestyle) and their real-time cost** | Freestyle with **AI filters**: RTX Dynamic Vibrance and RTX HDR; driver-level; **supports over 1200 games** [N1] | **NOT STARTED** | Zero occurrences of `freestyle` or `camera` in **every** `.md` in the repo (population: all `.md` under `H:\sotto-wt\parity`, window: whole tree) | No filter pipeline, no per-game post-process pass, **and no cost budget for one**. Note the counter-intuitive result for Sotto: a filter is GPU work on the same NVENC/D3D11 device that law 1 makes sacrosanct. Any Freestyle-class feature needs a measured cost before it is promised. |
| 7 | **Webcam + mic overlay** | Camera overlay exists in the overlay; Broadcast app is a separate product doing webcam AI [N1][N2]. **UNSOURCED**: the specific NVIDIA page stating the ShadowPlay camera-overlay feature and its limits — `custhelp` was down. | **NOT STARTED** | Zero occurrences of `webcam`/`camera` as a feature. The single `webcam` hit is `CABLE Output \| VoiceMeeter Output \| webcam mic (C920)` in `_main/receipt-20261007-audible-stimulus.md:31` — an **audio test device**, not a feature. | No second video source, no compositing, no camera placement/permission model. |
| 8 | **Broadcast to streaming destinations** | Broadcast brings **Facebook Live, YouTube Live, Twitch** under one UI [N4, **VERIFY**]; secondary names Twitch/YouTube/Facebook [S4]. **UNSOURCED**: whether NVIDIA supports *simultaneous multi-destination* — `custhelp` down. | **NOT STARTED** | Zero occurrences of `rtmp`/`twitch` as a feature. The one `rtmp` hit and two `twitch` hits are incidental (a PT-BR audit line about the panel text, `docs/audit/painel-texto.md:96`). | No streaming path at all. Law 3 (local-first, no cloud) arguably argues against it — **this is a genuine product decision, not a bug**, and it should be made explicitly rather than left unstated. |
| 9 | **AI noise removal in voice chat** | Broadcast: **Noise Removal** + **Room Echo Removal**, AI, one button [N2] | **NOT STARTED** | Zero occurrences of `noise removal`, `noise suppress`, or `voice chat` (population: all `.md`, window: whole tree) | Sotto has an **ASR** path (which denoises for *transcription*) but no **denoise-for-broadcast** path. These are different problems and only the first is even partly built. |
| 10 | **Highlights / automatic moment capture** | **NVIDIA Highlights**: "automatically captures key moments, clutch kills, and match-winning plays, ensuring that your best gaming moments are automatically saved" [N1]. | **NOT STARTED** | `highlight` appears **2×** in the whole tree, both incidental: `docs/audit/panel-gap.md:148` (`highlight()` inserting `<mark>`) and a panel hit rate. Zero product mentions. | This is the most interesting *strategic* gap, because Sotto is building something that could beat Highlights rather than copy it — a semantic index over what was said and shown on screen (`specs/04-index-search.md`, RRF over speech/OCR/visual). **That is never connected to auto-capture.** The capability exists as an index and does not exist as a feature. |
| 11 | **Performance overlay (FPS, GPU/CPU, memory, frametime)** | Real-time FPS + "GPU and CPU utilization, **FPS 1% Low**, and PC and system latency with integrated **NVIDIA Reflex Analyzer** support" [N1] | **NOT STARTED** | Zero occurrences of `fps counter` or `frametime`. `app/src-tauri/memory.rs` is **not** an overlay — `ROADMAP.md` §0c: "`memory.rs` is not a memory index — it is a `GetProcessMemoryInfo` working-set probe, and `commands.rs` returns a hardcoded `active:false, source:"m0-no-capture"`. The Tauri shell is an M0 mock." | No on-screen HUD at all. The one related component is explicitly a mock. `Alt+F12`/`Alt+R` FPS counter exists in ShadowPlay [S1][S4]; Sotto has no equivalent. |
| 12 | **Mobile pairing / second-screen control** | NVIDIA's Share overlay offered remote streaming to a **friend's browser via email invite** [N3, **VERIFY**]. That Chrome-app co-play path is legacy GeForce Experience. **UNSOURCED**: the current NVIDIA App mobile story — `custhelp` down. | **NOT STARTED** | `mobile` appears **2×**, both in `docs/harness-title-practice.md` as **prompt examples** (`"Fix login button on mobile"`, `"does not respond on mobile devices"`). `android` **1×** — `docs/accuracy-int4-vs-fp16-20261006.md:221`, incidental. | Nothing. The only `mobile` mentions are LLM test fixtures. |
| 13 | **In-app overlay launcher itself** | `Alt+Z` opens the overlay; all bindings remappable under Settings → Keyboard Shortcuts [S1][S4] | **NOT STARTED** | `overlay` appears 18× but as `GraphicsCapture`/capture-surface discussion and `_moved/aireplay/_main/pv-*.html` design prototypes — **never as a shipped in-game HUD** | Sotto has no overlay surface that can be summoned *over a running game*. The panel (`app/panel`, 5 themes) is a standalone WebView2 window, not an overlay. This is a structural prerequisite for rows 2, 7 and 11. |

**Row counts (population = 13 rows in §1, window = this document):**
NOT STARTED **9** · PARTIAL **2** · DONE **1** · SPEC-ONLY **0**.

---

## 2. WHAT SOTTO ACTUALLY CLAIMS — the honest summary

From `_moved/aireplay/ROADMAP.md` §1 and `specs/01`/`specs/03`, the measured
state on this box:

| subsystem | what the repo claims | measured where |
|---|---|---|
| Capture | WGC → BGRA→NV12 on GPU → NVENC H.264 → RAM ring. **IMPLEMENTED AND MEASURED.** NVENC API 13.1, 10 sessions held, #11 refused status **21** (`NV_ENC_ERR_INCOMPATIBLE_CLIENT_KEY`, *not* the documented `OUT_OF_MEMORY`). | `specs/03` §1; `docs/research/03-nvenc-sessions.md` |
| The cut | Remux, never re-encode. Forced IDR every 2 s (gaming) / 10 s (desktop); the IDR flag is read back from `NV_ENC_LOCK_BITSTREAM::pictureType`, not from what was requested. | `specs/03` §2.5, §2.7 |
| Clip latency | S1 cut+write **< 1 s** (must not touch the AI process); S2 thumbnail + SQLite row **< 300 ms**. | `specs/01` §4 |
| ASR | Parakeet int8 ONNX, EN 130/130 + PT 159/159 byte-identical to oracle. A later audit found the shipped decode carries `h`/`c` re-priming at every 560 ms chunk → WER **0.6105**, and arm 3 (carry + seed) reaches **0.1536** on a 25:08 reference. | `receipts/receipt-02-asr-impl.md`; `docs/audit/sotto-vs-referencia.md` |
| Index | Design measured, **no code** — `src/index/` empty, no SQLite anywhere in `src/`. | `ROADMAP.md` §0c |
| Hotkey | **Does not exist.** 0 hits across all of `src/capture/*.cpp\|*.h`. | `ROADMAP.md` §0c |
| Audio in clips | **Does not exist** in capture. `ffprobe -select_streams a` on **8** clips (3.0 s–30.0 s, largest 165 MB) → **8/8 `AUDIO=NONE`**. | `ROADMAP.md` §0c; `receipt-13` |

The two sentences that matter most for parity are, verbatim from `ROADMAP.md` §0c:

> "**No hotkey exists.** … The cut is *time-triggered* (`cfg.cut_at_s`). **The
> 'instant replay' trigger — the product's whole promise — does not exist.**"

> "**No audio exists.** … *Nothing is ever spoken into the index.*"

Both are already written down by the project. This table adds the third:

> **No broadcast surface exists.** There is no overlay, no HUD, no second video
> source, no filter pass, and no streaming path. Nine of thirteen parity
> capabilities have no code and no spec.

---

## 3. THE NEGATIVE ARM — capabilities the market expects that Sotto's plan never mentions

Method: `Select-String` with `-SimpleMatch` for each term across **every `.md`
file** under `H:\sotto-wt\parity`, excluding `node_modules`. **Population: all
markdown files in the worktree (whole tree, no date window).** Every non-zero hit
was then read in context to decide whether it was a product claim or incidental.

I found **five**, not the three required. I am reporting all five rather than
picking the three that flatter the story.

**A. In-game overlay / HUD surface — 0 as a feature.**
`overlay` = 18 hits, window: whole tree. Every one is either graphics-capture
surface discussion (`GraphicsCapture`, WGC overlay) or a design prototype under
`_moved/aireplay/_main/pv-*.html`. **Not one** describes an overlay Sotto draws
over a running game. This is a *prerequisite* for the hotkey UX, the FPS counter
and the webcam overlay — three parity rows collapse into it.

**B. Screenshots / still capture — 0 as a feature.**
`screenshot` = 9 hits, window: whole tree. ShadowPlay's `Alt+F1` still capture
[S1] is one of its most-used features and costs Sotto almost nothing (one decoded
frame — which `specs/01` §4 **already does** for the gallery thumbnail in the
S2 step). Not a single parity row mentions it, because the whole plan is framed
around video clips. **The cheapest missing parity win in this document.**

**C. Clip sharing / export / cloud round-trip — no mention.**
Sotto's index is `content_key`-addressed and local-first (law 3). There is no
export, no share sheet, no "open in editor / upload" path anywhere in the plan.
The market expects a recorded moment to **leave the machine**. Note the tension:
law 3 forbids content telemetry, which does **not** forbid a user-initiated
export. The plan conflates the two by never mentioning either.

**D. Recording *sources* beyond the game window — no mention.**
Sotto's capture item is chosen programmatically, never picked (`specs/03` §2.1:
"No `GraphicsCapturePicker`, therefore no dialog"). That is a deliberate,
defensible design choice — but it means there is **no user-facing concept of
"which app am I recording"**. Desktop mode exists as a *mode*, not as a
*source picker*. Every competing recorder treats source selection as table stakes.

**E. Multi-slot instant replay — never discussed, and ShadowPlay lacks it too.**
There is a standing user complaint that ShadowPlay cannot hold more than one
instant-replay clip at a time, and that the workaround is third-party software
that reads ShadowPlay's registry and watches for saves [S5]. Sotto's plan
discusses ring sizing extensively and multi-clip *queueing* (persistent on-disk
queue, one heavy job at a time, `specs/01` §5) but **never** the two-second
question users actually ask: "can I press save twice and keep both?" The queue
implies the answer is yes; nothing states it.

*(Self-check on the arm: if I had to argue against myself, the strongest counter
is that (C) and (D) may be deliberate product decisions under law 3 rather than
oversights. I think that is half right — law 3 constrains telemetry, not export —
but I am flagging them as *undecided* rather than *missing*, which is the honest
label. (A), (B) and (E) are not defensible as deliberate; they are absences.)*

---

## 4. THE MVP — what Sotto cannot exist without, in order

Eight items. This is the boundary, not the wishlist: **drop any one of these and
the product is not a ShadowPlay-parity recorder at all.** Everything in rows 3–13
of §1 is explicitly *outside* this list.

1. **The cut hotkey.** `{"cmd":"cut"}` on the capture process's stdin. This is
   the entire product. Today the cut is time-triggered and *"the product's whole
   promise does not exist"* (`ROADMAP.md` §0c). **Gate: clip on disk < 1 s during
   a live 1080p60 encode, zero `ring_dropped`, `ffmpeg -f null -` clean.**
   *Why first:* it is the smallest change that converts an existing, measured
   subsystem into the product. Everything else is additive; this is definitional.

2. **Audio in the clip.** WASAPI loopback → muxed beside the video, 16 kHz mono.
   **Gate: one capture whose clip `ffprobe` reports `codec_type=audio`, with ASR
   text over that same audio.** *Why second:* the machinery **already exists and
   is proven in this repo** — `worker/wasapi_loopback.py`, the device ladder
   (`sotto_worker.py:942-1088`), `resample_to_16k` (`:1090`). `ROADMAP.md` says
   "Reuse it, do not rebuild it." 8/8 clips are currently `AUDIO=NONE`. A video
   recorder with no sound is not parity and not a product; and without audio the
   entire ASR half of Sotto is disconnected from the capture half.

3. **One Engine process that is the PARENT, UI a reconnectable child.** IPC =
   **JSON Lines over stdin/stdout** — already hardened in production here
   (`sotto_worker.py:374-377` `emit()` → `sotto_webview.py:5964-5975`, watchdog).
   *Why third:* this is the difference between "we measured four subsystems" and
   "there is a product". It is also what makes items 1 and 2 survive a UI crash.
   Note the dependency: the same stdin pipe as item 1 carries the control verb.

4. **One SQLite file — the durable spine.** Identity is `content_key`, which a
   message-passing engine cannot express (`ROADMAP.md` P0 item 4). Today
   `src/index/` is **empty** and there is **no SQLite anywhere** in `src/`.
   *Why fourth:* S2's "appears in the gallery in < 300 ms" has nowhere to write.
   This is the item that makes the gallery real rather than a temp directory.

5. **Ring budget from measured hardware (law 7).** Fix the RAM budget from the
   detected GPU/VRAM class, then *derive* seconds from the mode's bitrate — never
   fix seconds. Cap `clamp(VRAM_MB ÷ 16, 256 MiB, 2048 MiB)`; print what it chose
   and why on every start. **Gate: the printed seconds match the printed RAM
   arithmetic, and the 16 ms budget gate holds on a real 60 fps window** — the
   current gate already passes a 3.3× miss (`p50 52.94 ms`, `frac_under_16ms =
   0.000`; see `index: scale verdict`, commit `1327902`). *Why fifth:* the ring is
   the memory hog — measured 675 MB @1080p60 — and an unbounded ring is the
   fastest way to make the owner's machine unusable.

6. **No encoder → no armed key (law 6).** `arm()` is the *output* of a self-test
   that opened a session **and** initialised it **and** registered **and** mapped
   a real NV12 texture. On total failure: do not arm, print one line per attempted
   arm with its raw status and `nvEncGetLastErrorString`, exit non-zero. **Gate:
   both colours — encoder present ⇒ armed, and encoder failed on purpose ⇒
   refused with the reason printed.** *Why sixth:* "the worst failure this
   product can have is a recorder that says it is armed and records nothing."
   Pair it with item 1: **never arm the hotkey unless the encoder is real.**

7. **Law 1 — capture never waits for AI.** One dedicated capture→convert→encode
   path, bounded staging queue, drop-with-a-counter, never block on the AI, the
   disk or the UI. Heavy AI in a separate process, one job at a time, at
   background priority, gated on an idle score that must hold ≥ 30 s and must
   stop within one segment. The queue is persistent on disk and the UI **says what
   it is doing**. **Gate: a clip arriving preempts a running S3/S4 job, and a
   preempted job loses at most one segment.** *Why seventh:* this is the
   difference between Sotto and a product that degrades the game it is recording.
   It is also the gate that keeps the AI work Sotto is uniquely good at from
   costing the user frames.

8. **Clips appear fast, and unfinished looks unfinished.** S1 (cut+write, < 1 s,
   never touches the AI) → S2 (one decoded frame → thumbnail, < 300 ms, plus a
   SQLite row and a UI event). The gallery shows S1+S2. A clip with no transcript
   yet is shown with a **"transcribing…" state — never hidden.** **Gate: pressing
   the key during a live encode yields a visible gallery entry in < 1 s with the
   transcript still pending.** *Why eighth:* it is the owner's stated requirement
   verbatim (`specs/01` §4) and the acceptance test that makes items 1–4 legible
   to a human.

**Explicitly deferred, and that is a decision not an oversight:** broadcast/streaming,
webcam and mic overlay, Freestyle-class filters, NVIDIA-Highlights-class automatic
moment capture, AI noise removal for voice chat, mobile pairing, manual
start/stop recording, the performance HUD, and any in-game overlay surface.

One of those — **automatic moment capture** — deserves a note rather than a
bury. Sotto's ASR + OCR + visual index (`specs/04-index-search.md`, 3-channel
RRF) is a strictly better signal for "that was a good moment" than a game's
kill feed. Wiring the existing index to the existing ring is how Sotto beats
NVIDIA Highlights instead of trailing it. It is **not** in the MVP because the
MVP is the boundary, and it needs item 4 and item 7 working first.

---

## 5. WHAT SOTTO IS AHEAD ON

Recording this because a parity table that only lists gaps is a dishonest artefact.

1. **Replay memory.** 120 s (gaming) / 600 s (desktop) default vs ShadowPlay's
   30 s default and 20 min hard ceiling [N1][S1]. Sotto's *default* is 4–20×
   longer than ShadowPlay's.
2. **Speed to a saved, visible clip.** Sotto targets < 1 s to the file and < 300 ms
   to a gallery entry, with S1 explicitly forbidden from touching the AI process.
   ShadowPlay's instant replay is DVR-class; the "appears fast with a real
   transcript pending" loop is Sotto's design and I found **no** NVIDIA feature
   it maps to.
3. **Semantic recall over what was said.** Whisper-class in-process ASR plus a
   3-channel RRF index is not a ShadowPlay feature at all. It is the honest
   differentiator, and §3/E shows it is not yet connected to capture.

---

## 6. LIMITATIONS OF THIS DOCUMENT

- **`nvidia.custhelp.com` was down for the entire lane** (Oracle incident page,
  incident `0.4cc41002.1791398185.5263de87`). The overlay manual and the official
  shortcuts list live there. **Every hotkey in this document is secondary-sourced
  [S1][S4]** and should be re-verified against NVIDIA's own shortcuts page before
  any of it is treated as a spec input.
- **N3, N4, N5 are cited from the search index, not fetched.** Marked **VERIFY**
  inline. N3's page returns NVIDIA's own 404 for the `.md` alternate.
- **Game filter real-time cost — UNSOURCED.** NVIDIA publishes no per-filter
  performance figure, and Freestyle's cost is famously driver-version-dependent.
  Any Sotto filter decision needs its own measurement; do not carry a number over
  from this document.
- **Mobile pairing — UNSOURCED for the current NVIDIA App.** The only sourced
  evidence (N3) is the retired GeForce Experience Chrome co-play path.
- **Simultaneous multi-destination broadcast — UNSOURCED.** I could not confirm
  whether NVIDIA broadcasts to more than one destination at once. Row 8 does not
  claim it either way.
- I did not execute anything in `src/` and did not touch it. Every Sotto verdict
  is read from the repo's own docs and receipts, cross-checked where the repo
  contradicts itself.