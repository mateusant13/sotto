# SPEC 01 — CAPTURE MODES, THE RING, AND THE PROCESSING QUEUE

Owner's brief (2026-10-08, verbatim intent): *gaming mode captures 60 fps at ~40–50 Mbps; desktop
mode 30 or 24 fps at a lower bitrate — you choose the numbers. Clips must appear very fast in the
embedded gallery, so the processing happens AFTER the whole clip exists. **If another clip arrives,
the processing must not interfere with creating the new clip.** And processing should probably wait
until the game ends or the machine is idle — a login screen or a lobby.*

Status: **SPEC — nothing here is measured on this box yet.** Numbers marked ⚙ are engineering
decisions with the reasoning shown; numbers marked **UNKNOWN** need a measurement before shipping.

---

## 1. TWO MODES, AND THE NUMBERS I CHOSE

| | **GAMING** | **DESKTOP** | why |
|---|---|---|---|
| fps | **60** | **30** | 30, not 24: desktop content is not static — video in a window, animated UI, cursor smoothness. 24 judders on anything moving and buys only ~20% ring RAM, which §2 shows we can get back better |
| bitrate (1080p) | **45 Mbps** ⚙ | **8 Mbps** ⚙ | middle of the owner's 40–50 for gaming; desktop content is mostly static with large flat regions, so the encoder is cheap on bits — 8 Mbps is generous for H.264 High at 1080p30 |
| codec | HEVC or AV1 if the GPU offers it, else H.264 | H.264 (maximum compatibility for a clip the user may send someone) | at 45 Mbps the codec difference is small; at 8 Mbps on static content it is irrelevant |
| GOP / IDR grid | forced IDR every **2 s** | forced IDR every **10 s** | the cut point (see §3) is found by forced IDRs; static content needs far fewer |
| ring length | **120 s** default | **600 s** default ⚙ | see §2 — desktop's lower bitrate buys a much longer memory for the same RAM |

**Bitrate scales with pixels, not with a fixed number.** The 45/8 Mbps figures are for 1080p. The
shipping rule is **bits per pixel per second** (bpp), which is resolution-independent:

- GAMING: **≈0.036 bpp** → 1080p60 = 45 Mbps · 1440p60 = 80 Mbps · 4K60 = 180 Mbps
- DESKTOP: **≈0.013 bpp** → 1080p30 = 8 Mbps · 1440p30 = 14 Mbps · 4K30 = 32 Mbps

If a fixed cap is ever needed (weak hardware, encoder session pressure), cap the **ring**, never the
bitrate first: a bitrate-starved clip is a permanently damaged recording, a shorter ring is a
recoverable choice. **UNKNOWN: whether 0.036 bpp is the right knee for fast-motion game content on
HEVC/AV1 — needs a measured VMAF/SSIM sweep on three real clips before shipping.**

## 2. THE RING IS SIZED IN BYTES, AND DESKTOP GETS A LONGER MEMORY

Ring RAM = bitrate ÷ 8 × seconds. At the defaults above:

| mode | 1080p | 1440p | 4K |
|---|---|---|---|
| GAMING 120 s | **675 MB** | 1 200 MB | 2 700 MB |
| DESKTOP 600 s | **600 MB** | 1 050 MB | 2 400 MB |

So the two modes cost about the same RAM while the desktop one remembers **five times longer** —
which is exactly the desktop use case ("I want that thing from eight minutes ago"). The ring is the
memory hog of this product (§ law 7 in `AGENTS.md`), so the budget rule is:

> **Fix the ring's RAM budget from the detected GPU/VRAM class first, then derive seconds from the
> mode's bitrate.** Never fix seconds. The product must state what it chose and why.

**UNKNOWN: the actual ring overhead** (encoder reference frames, the NV12 staging texture, queue
depth) — the table is payload only.

## 3. THE CUT POINT — FORCED, NOT SEARCHED

The clip begins at the **nearest forced IDR at or before (hotkey − ring_relevant_seconds)** and ends
at the next IDR **after** the hotkey plus the configured "after" tail. The encoder is told to force
that grid itself (`NV_ENC_PIC_FLAG_FORCEIDR`), so the cut never depends on hunting keyframes in a
bitstream, and SPS/PPS ride every IDR by default (measured in the capture lane's source reading).

## 4. THE CLIP APPEARS FAST — AND THAT IS A SEPARATE, CHEAP STEP

The owner's requirement is that the clip shows up in the gallery **immediately**. So the pipeline is
split by COST, not by feature:

| stage | what it does | budget |
|---|---|---|
| **S1 — cut and write** | remux the ring's frames into `clip.mp4` (no re-encode) | **the only stage on the critical path; target < 1 s, and it must not touch the AI process at all** |
| **S2 — make it visible** | one decoded frame at the cut point → thumbnail; duration, timestamp, mode, resolution, size → SQLite row; emit a UI event | **target < 300 ms; this is what "appears fast" means** |
| **S3 — transcribe** | ASR over the clip's audio (VAD-gated) | background, interruptible |
| **S4 — index** | visual + OCR + text embeddings, markers, reranker data | background, interruptible, slowest |

**The gallery shows S1+S2 results. A clip with no transcript yet must LOOK unfinished, not be
hidden** — an entry with a "transcribing…" state, so the user never loses track of a clip.

## 5. PRIORITY — THE RULE THE OWNER ASKED FOR, IN WRITING

Three tiers, strictly ordered. **A lower tier never delays a higher one.**

1. **CAPTURE + ENCODE** (continuous). Reserved GPU/CPU; never blocked, never throttled by anything
   below. If the machine cannot sustain both, S3/S4 pause — the recording is sacrosanct.
2. **CLIP SAVE (S1) + APPEARANCE (S2)**. Preempts the AI worker **immediately**: a new clip arriving
   is the owner pressing the key, and the seconds after that are the ones he is watching.
3. **HEAVY AI (S3, S4)**. Runs in a **separate process**, one job at a time, at background priority,
   and only inside the idle windows of §6.

Rules that make this real, not aspirational:
- **Separate process, not threads.** Measured in the sibling project: the Redux runner peaks at
  **3.90 GB RSS**. A heavy job must be killable and restartable without touching the capture
  process.
- **One heavy job at a time, ever.** Parallel model loads were the cause of a `bad allocation`
  failure in the sibling project.
- **A memory floor check before starting** a job; below it, defer and say so.
- **The queue is persistent on disk.** A deferred job survives a restart or a crash; the UI shows how
  many clips are waiting.
- **Preemption is cooperative and bounded**: the AI worker checks a stop flag between segments and
  yields within one segment, so a preempted job loses at most one segment of work.

## 6. WHEN THE HEAVY WORK RUNS — IDLE, NOT "WHEN IT FEELS FREE"

Signals, all cheap to sample on a timer:
- **no fullscreen/borderless 3D application on screen** (the capture path already knows the window);
- **GPU 3D utilisation below a threshold for N consecutive seconds** — the honest proxy for "not in a
  match";
- **desktop mode active** (if the user switched to desktop, he is not gaming);
- optionally **user input idle** (`GetLastInputInfo`) — but never as the only signal, because a
  lobby or login screen has no input and is exactly the window we want.

Policy: an **idle score** with hysteresis — start heavy work after the score has held for
**≥30 s**, stop it within **one segment** (a few seconds) when the score drops. **The UI must say
what it is doing** ("indexing 3 clips — paused while you play"), because a background job the user
cannot see is indistinguishable from a bug.

**UNKNOWN: the GPU-utilisation threshold and N.** Must be measured against real gaming sessions on
this box; a wrong threshold either spins the fans during play or never indexes anything.

## 7. MODE SELECTION — AUTO, WITH AN OVERRIDE, AND NEVER SILENT

- **auto**: fullscreen/borderless 3D window present **and** sustained GPU 3D load → GAMING; else
  DESKTOP;
- **manual override** always available (tray + panel); the active mode is **displayed**;
- **the switch between modes is a discontinuity** (fps, bitrate, GOP, ring seconds all change), so
  it must be **announced in the UI and in the log**, and the ring must be **re-armed**, not mixed:
  a clip whose first half is 24 fps and second half is 60 fps is a broken artefact. **UNKNOWN:
  whether the WGC session survives a format change or must be recreated — the capture lane already
  found that recreation discards pending frames.**

## 8. WHAT THIS SPEC DELIBERATELY DOES NOT DO

- It does not re-encode the clip to save space (quality loss, CPU cost, and a clip appears slower).
- It does not process during play "if there is spare capacity" — spare capacity is exactly what the
  game claims the moment the user does something violent on screen.
- It does not promise the transcript is ready when the clip appears. It promises **the clip** is.
