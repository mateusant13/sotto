# SPEC 07 — HIGHLIGHTS: THE NOTION OF A MOMENT, AND WHY THIS BOX HAS NONE

**This spec is mostly about what automatic highlighting cannot yet do.** Every number below is
either `MEASURED` on this box by the lane that wrote this file, or tagged `READ` with a
`path:line`, or tagged `UNKNOWN`. A constant without provenance is a bug in this spec — the
same rule `specs/02-asr.md` sets.

`MEASURED` = a command on this box produced it, with the command named ·
`READ` = source read, line given · `UNKNOWN` = nobody has shown it · `SYNTHETIC` = a corpus this
lane generated, which is real audio but **not** capture-derived and is never counted as product
evidence.

Provenance for the measurements in this file: `_main/_hl07-audio-census.txt` (the clip
population), `_main/_hl07-speech-probe.log` (real speech),
`_main/_hl07-scoring-probe.log` (the only clip with audio),
`_main/oracle-07-highlights.py` + `.log` (the gate, both colours).

---

## 0. THE DECISION, IN ONE PARAGRAPH

**Highlights ship as a DISABLED-BY-DEFAULT, AUDIO-ONLY v1 whose false-positive rate is 15.00 per
10 minutes of continuous speech, and the spec says so on the panel.** The alternative —
shipping a "smart highlights" toggle that fires on every phrase of ordinary talk — is the exact
defect this repo forbids: a plausible sentence filling a measurement gap. The gates that make
the feature *safe* (0 highlights from 180 s of a walk in the park, measured) are not the same
thing as the gates that would make it *useful*, and this spec refuses to conflate them. The
useful version needs a signal this project does not have; §1.4 names which one and why it is a
dependency, not a task.

---

## 1. WHAT THE PROJECT ACTUALLY HAS TO SCORE

### 1.1 There is no audio. Re-measured here, on a wider population than the inherited claim.

The brief carries `8/8 clips have no audio stream`. That is `UPHELD` and it is **understated**.
This lane re-ran `ffprobe -print_format json -show_streams` over **every** `.mp4/.mkv/.mov`
larger than 1 MB under `_moved/aireplay/_main/`:

| measure | value |
|---|---|
| **POPULATION** | **28 clips** (all `*.mp4`/`*.mkv` > 1 MB under `_moved/aireplay/_main/`) |
| **WINDOW** | all 28 on disk at the time of writing; no sampling |
| clips with `codec_type=audio` | **1** — `_main/_import-bench/synth-180s-1080p30.mp4`, 282 MB, 180.0 s, **AAC** |
| clips without an audio stream | **27** |
| of those 27, produced by our own capture path | **27 of 27** (every `_off-*`, `_remux-*`, `clip-*`, `offline-*`, `pass1147-*`) |

**The single clip with audio is an ffmpeg-generated synthetic from the import benchmark, not a
capture output.** So the honest sentence is stronger than the inherited one and has no escape
hatch in it:

> **Every clip this project has ever produced is video-only. N = 27 of 27 capture outputs.**
> The only audio on this box belongs to a file `ffmpeg` made to test an importer.

`MEASURED`, `_main/_hl07-audio-census.txt` + `_hl07-audio-census-verdict.txt`
(`POPULATION=28 WITH_AUDIO=1 WITHOUT_AUDIO=27`).

### 1.2 And the ASR that would consume it is file-fed, by contract.

`src/asr/transcribe.py:47` — `p.add_argument("--wav", required=True, ...)`. There is **no live
input path**: the engine is a batch job over a WAV file, with a per-clip model load of
**1.96–4.13 s** at 4 threads (`specs/02-asr.md` §5) and a peak RSS set by segment length
(**0.88 GB at 10 s**, `05-onnx-asr.md:67`). Any real-time use of the transcript is a
**background** capability under `specs/01` §5 tier 3 — "heaviest work happens when the user is
NOT playing" (`AGENTS.md` law 5).

### 1.3 The scoring primitives that DO exist today — as code, without any input

Both of the primitives this spec scores on are **model-free and deterministic**, which is why
this gate costs no inference:

| primitive | what it is | file | has data today? |
|---|---|---|---|
| **speech segments** | silence-aligned segmentation; deterministic; a byte-level regression target | `src/asr/segment.py:39` | **no** — needs audio |
| **10 Hz level** | windowed per-100 ms peak / RMS / smoothed envelope | `src/asr/level.py:45` | **no** — needs audio |

Their measured behaviour on the two corpora that exist on this box, `MEASURED`
(`_main/_hl07-speech-probe.log`, `_main/_hl07-scoring-probe.log`):

| measure | real speech `[900,1020)` s | the only clip with audio (180 s tone) |
|---|---|---|
| **segments** | **11** (median **6.98 s**, max **13.82 s**) | **0** |
| speech coverage | **72.3 %** | 0 % |
| level events | 1 200 @ **10.00 Hz** | 1 801 @ **10.00 Hz** |
| peak p50 | 0.0292 | 0.1252 |
| peak p95 | 0.4994 | — |
| peak max | 0.7231 | 0.1526 |
| **dynamic range `p99/p50`** | **19.90–24.76×** | **1.22×** |
| segments found | 11 | **0** |

**Two facts here are load-bearing, and both are surprises worth stating plainly.**

1. **The dynamic range separates speech from garbage by more than an order of magnitude**
   (19.90× vs 1.22×). That is the whole basis of the `degenerate-signal` gate in §6.
2. **The splitter finds ZERO segments in 180 s of a continuous tone, and that is correct
   behaviour, not a bug.** `thr = max(4 × p10(rms), 0.005)` (`segment.py:64`, constants
   `SILENCE_THRESHOLD_MULT=4.0`); a steady tone has `p10 ≈ median`, so the threshold lands
   **above the signal itself**, every frame reads as silent, every resulting segment is
   silence-only, and `segment.py:102-103` drops them. **The relative threshold makes a
   continuous non-speech signal indistinguishable from silence.** Any score built on
   "did the splitter find a segment" inherits that blindness.

### 1.4 The signal that would actually carry a "moment" does not exist here

`MEASURED` by reading, not by running:

| candidate signal | available today? | evidence |
|---|---|---|
| speech segment membership | code yes, **data no** | §1.1 — 27/27 clips silent |
| 10 Hz envelope excursion | code yes, **data no** | §1.3 |
| ASR text / rare token | code yes, **file-fed only** | `transcribe.py:47` |
| **GPU 3D utilisation** | **named in spec 01 §6, never implemented** | no `QueryAdapter`/util read anywhere in `src/capture` |
| **foreground window identity** | **not implemented** | `specs/01` §7 says the capture path "already knows the window"; no getter exists in `src/capture` |
| **user input activity** | **named in spec 01 §6, never implemented** | no `GetLastInputInfo` in `src/capture` |
| **frame-difference / scene change** | **no** | zero hits for scene/motion/diff outside `third_party/nvEncodeAPI.h` |

**The honest dependency statement:** the audio primitives exist as code but have no input; the
inputs that would discriminate a *moment* from *ordinary talk* — an opt-in UI event, an in-game
event feed, a kill/death feed, a chat spike — **are all game-title-specific and none is on
disk.** That is a dependency, and a dependency is the useful output here, not a failure.

---

## 2. CANDIDATE SIGNAL SOURCES — cost, what each misses, and is it here

| # | signal | cost | what it MISSES | here today? |
|---|---|---|---|---|
| **S1** | **speech-segment membership** (`A(t) ∈ {0,1}`) | ~0.1 % CPU (numpy, 20 ms frames, `segment.py`) | misses every moment that is not speech — a silent ace, a goal with the mic muted, a reaction with nobody talking | **code yes / data NO** |
| **S2** | **envelope excursion** `E(t) = env(t) / p99(env)` | ~0.01 % CPU at 10 Hz | loud is not important; misses quiet decisive moments; a door slam scores as high as a callout | **code yes / data NO** |
| **S3** | **ASR text** — rare token, proper noun, callout | **the whole 0.88 GB model**, 1.96–4.13 s load per clip, background only | cannot run in real time; transcription error is scored as signal | **file-fed only** |
| **S4** | **in-game event layer** (kill / objective / chat) | per-title SDK work, untitled | exactly the thing that would work | **does not exist** |
| **S5** | **GPU 3D load / window identity / input idle** | ~free (DXGI adapter + `GetLastInputInfo`) | measures *session* phase, not *moments* — good for "don't run heavy work now" (`specs/01` §6), useless for "this second matters" | **named, not implemented** |

**S4 is the honest answer to "what is a highlight", and this project cannot write it without a
game title.** Everything below is therefore scoped as **v1 = S1 + S2 only**, with S3 pinned to
zero weight and S4/S5 named as the route to v2.

---

## 3. THE SCORING RULE — the exact formula and its parameters

For each candidate time `t`, over a window of PCM at 16 kHz mono:

```
score(t) = w_A · A(t)  +  w_E · E(t)  +  w_K · K(t)

  A(t) ∈ {0,1}   1 if t lies inside a speech segment from segment.py:39, else 0
  E(t) ∈ [0,1]   envelope excursion = env(t) / p99(env over the trailing PEAK_REFERENCE_S)
  K(t) ∈ [0,1]   ASR rare-token / callout hit rate for t  -- PINNED 0.00 in v1 (S3 not live)

  w_A = 0.60    w_E = 0.40    w_K = 0.00        (spec section 7)
  THRESHOLD = 0.75

EMIT a highlight at t  iff  score(t) >= 0.75  AND  (t - t_last_emit) >= MIN_GAP_S = 20.0
```

And **before any of that**, two gates:

```
GATE 0  degenerate-signal:  p99(peak) / p50(peak) < MIN_DYNAMIC_RANGE (3.0)
        -> state "degenerate-signal", REFUSE.   [anchors: 1.22x tone, 19.90x speech]
GATE 1  no-speech:  segments_silence() returns 0 segments
        -> state "no-speech", REFUSE.
```

**Candidate generation is the part that matters, and it is not in the formula.** v1 scores
**one candidate per speech segment** — the peak of the envelope inside that segment — *not* one
per time window. Scoring every window is what the naive rule in §5 does, and it is why the
naive rule emits highlights from a walk.

**Why these weights.** `w_A + w_E = 1.0` and `THRESHOLD = 0.75` are chosen so that the
conjunct is **load-bearing rather than decorative**: with `A = 1` the rule needs `E ≥ 0.375`;
with `A = 0` the maximum reachable score is `0.40 < 0.75`, so a highlight **cannot** be emitted
outside speech even if `E = 1.0`. This is not a stylistic claim — `MIN_GAP_S` is not what
produces that, and removing the conjunct without also changing the threshold produces a rule
that is unfalsifiable (the oracle found this in itself; §5).

**`MIN_GAP_S = 20.0 s`** is chosen from the measured segment statistics: median segment
**6.98 s**, max **13.82 s** (`_main/_hl07-speech-probe.log`; these reproduce the ASR spec's own
registered numbers, `specs/02-asr.md` §3 — 11 segments, median 6.98, max 13.82). 20 s exceeds
the longest measured segment plus the clip tail, so two highlights cannot overlap in time.

**All four weights and both thresholds are `CHOICE`, not measurement.** They are bounded by
[A1] below and must be re-derived against a real labelled corpus before v2. They are stated
here as *starting values that the gate enforces*, not as findings.

---

## 4. THE SEGMENT WINDOW POLICY — and what the ring actually gives us

```
HIGHLIGHT clip window  =  [ t_peak - PRE_ROLL_S , t_peak + POST_ROLL_S ]

  PRE_ROLL_S   = 6.0 s     (CHOICE, band 3-10)
  POST_ROLL_S  = 8.0 s     (CHOICE, band 5-15)
  nominal clip length = 14.0 s
```

**Then the window is snapped BACK to a decode start**, because a clip must begin at an IDR:
the start becomes the nearest forced IDR at or before `t_peak - PRE_ROLL_S`. The forced-IDR
grid is already a contract in `specs/03-capture-encode.md` §2.5 (`NV_ENC_PIC_FLAG_FORCEIDR`
every `fps × 2` in GAMING, every 10 s in DESKTOP). So:

| mode | nominal | IDR grid | **worst-case actual clip** | ring seconds held (`specs/03` §2.6) |
|---|---|---|---|---|
| GAMING 1080p60 | 14.0 s | **2 s** | **≤ 16.0 s** | 120 s |
| DESKTOP 30 | 14.0 s | **10 s** | **≤ 24.0 s** | 600 s |

**Cross-reference, not contradiction — the ring-sizing lane does not bind this window.**
`receipts/receipt-14-ring-cap-vram-vs-ram.md` prices the ring from VRAM (`d3d11_ctx.cpp:70`,
`dedicated_vram / 16` = 998.69 MiB on this box) and shows the worst case today is **4K60
keeping only 46.5 s**. **46.5 s > 24.0 s**, so even the clipped ring satisfies the worst-case
desktop highlight window today. If that lane's RAM-based cap (4 GiB) is adopted, 120 s is
restored at 1440p/4K and the window gets *more* slack, not less. **This spec therefore places no
requirement on the ring-sizing decision**, and asks only that the sizing lane keep reporting
`seconds_kept` — note that today it is computed and then discarded at `replay.cpp:125`
(`(void)seconds_kept;`, receipt-14), so the number a highlight would need is **thrown away
before it is printed**. That single line is the one real coupling between this spec and that
lane, and it is a one-line fix owned by them.

**The ring is asked, never assumed.** `src/capture/trigger.h:99-103` already declares
`RingSpanProbe::span_seconds()` — one method, explicitly so a lane that does not own the ring
can ask how much history exists. **Highlights use that same probe** (`CutRequest::ring_span_s`
is the existing carrier of the same answer for the hotkey). If `span_seconds() < PRE_ROLL_S +
POST_ROLL_S` at emit time, the clip is **shortened at the front and the shortfall is reported**
— never silently clamped, per `trigger.h:47-53` — or **refused** if the user asked for the full
window. `state = ring-too-short`, and the log carries `requested_s`, `ring_span_s`, `written_s`.

**Clip merging.** Candidates whose windows overlap are ONE highlight, not two. With
`MERGE_GAP_S = 1.0 s` this merges 80 % of adjacent segments — `MEASURED`: 10 inter-segment gaps
in the 120 s slice, 80 % ≤ 1.0 s, and the median gap is **−0.20 s**, i.e. segments *overlap*
because `PAD_S = 0.10 s` is applied on both sides (`segment.py:97,104`). Without merging, every
`PAD_S` overlap would manufacture a duplicate highlight at the same instant.

---

## 5. THE FALSE-POSITIVE BUDGET — two numbers, because one honest number is not useful

### 5.1 What the oracle measured

`_main/oracle-07-highlights.py`, all four arms, one command, `MEASURED`
(`_main/oracle-07-highlights.log`, **exit 0**, `VERDICT PASS`):

| arm | corpus | result |
|---|---|---|
| **A0 positive** | real speech `plain-3600s.wav [900,1020)` | `scored` — 11 segments, **3 emits**, **0 outside a speech segment**, **dr 19.897** |
| **A1 dead tone** | `synth-180s-1080p30.mp4`, 180 s — the only clip on this box with audio | **`degenerate-signal`, 0 emits** |
| **A2 walk** | 180 s `SYNTHETIC` pink-noise bed with slow amplitude wander | **`degenerate-signal`, 0 emits** |
| **A3 control** | A1 and A2 under the **naive rule** (§5.3) | **9 emits from a tone · 8 emits from a walk** |

### 5.2 The two budgets

| budget | value | status |
|---|---|---|
| **α — v1 ceiling, continuous speech** | **≤ 20 highlights / 10 min** | **`MEASURED` 15.00 / 10 min on A0 — passes.** This is the number the gate enforces. |
| **β — product target** | **≤ 1 highlight / 10 min** | **`MEASURED` 15.00 / 10 min — **FAILS BY 15×**. Declared NOT REACHABLE with audio alone.** |
| **false negatives** | **not claimed** | **`NOT MEASURED`. No labelled corpus exists on this box. There is no recall number in this spec and there must not be one until a human labels real gameplay.** |

**α is a terrible product number and the spec says so on the panel.** 15 highlights per 10
minutes of continuous speech is not a highlight reel; it is "every other sentence". The
reason is structural, not a tuning failure: **continuous speech is 72.3 % segment coverage with
a median segment of 6.98 s**, so "a phrase happened" carries almost no information about "a
moment happened". Tuning `THRESHOLD` upward does not fix this — it only moves which sentences
survive, because A0's emits are spread across segments, not concentrated in a few.

**β is reachable only by adding a non-audio signal** (§1.4: S4, or S3 with a per-title event
vocabulary). That is the honest statement of what highlights needs next, and it is a dependency
on someone choosing a game title.

### 5.3 The gate, and the two controls the oracle had to be rewritten for

`_main/oracle-07-highlights.py` enforces, and goes RED when any of these fail:

1. **A0 emits ≥ 1** on real speech (an instrument that cannot see a positive is broken);
2. **A0 containment: 0 emits outside a speech segment** — this is the FP claim;
3. **A0 rate ≤ α (20 / 10 min)**;
4. **A1 and A2 emit exactly 0** — a walk is not a highlight;
5. **A3 emits > 0** on both garbage corpora — otherwise 1 and 2 prove nothing.

**Both control arms in this gate were wrong on their first two runs, and the oracle reported
RED both times rather than being weakened.** This is recorded because it is the transferable
part:

- **Defect 1 — the control could not fail.** Removing only the speech conjunct still emitted 0,
  because `GATE 0` short-circuits before scoring runs. A1/A2 were green because of the
  dynamic-range gate, and **nothing in the instrument proved the conjunct did any work** — the
  conjunct was VACUOUS.
- **Defect 2 — removing both gates still could not fire.** With `THRESHOLD = 0.75` and `A = 0`
  the maximum score is `0.40`, so a gate-removed copy of the same rule is **unfalsifiable by
  construction**. Lowering the threshold to make it fire would have destroyed the control's
  meaning.
- **The cure:** A3 is the naive rule *as a different rule* — `w_A = 0`, `w_E = 1.0`, its own
  threshold 0.60, no gates, and **every 1 s window a candidate instead of one per segment**.
  Same refractory, so the single variable is the gating. It emits 9 and 8. That is the RED
  colour, and it is a rule, not a mutilated copy.

**A third defect was in this lane's own probe, caught by the oracle printing its duration:**
`read_wav_slice(path, start_s, dur_s)` was called with `dur_s = 1020.0` (the slice's *end*
offset) instead of `120.0`, so the "120 s slice" ran to the end of the file and reported
**24 emits over 1020 s**. The number was wrong by 3.5× and would have been quoted as the
false-positive rate.

---

## 6. THE FAILURE VOCABULARY — silence and refusal must be loud

Every state below is a **reported** state with a reason, never a fallback that looks like
success. The panel shows the current one; the log carries all of them.

| state | when | what the user sees | what it must never do |
|---|---|---|---|
| `no-audio-stream` | the capture carries no audio — **today's state, 27/27 clips** | "Highlights unavailable: this recording has no audio" + the reason | silently produce zero highlights and call it "no highlights found" |
| `no-tap` | the loopback endpoint is not armed, or routed nothing | the device ladder's own reason | treat digital silence as a quiet recording |
| `degenerate-signal` | `GATE 0` fires — **MEASURED 1.22× on the tone** | "Audio present but not speech (flat dynamic range 1.22×)" | report "no highlights" as if the audio were evaluated |
| `no-speech` | `GATE 1` fires — **MEASURED 0 segments on the tone** | "No speech in this window" | fall back to peak scoring |
| `scored-no-candidate` | scoring ran, nothing crossed threshold | "Scored N windows, 0 above threshold" | claim the feature is broken, or retry silently |
| `ring-too-short` | `span_seconds() < PRE_ROLL + POST_ROLL` | "Ring held 12.4 s, clip needs 24.0 s — shortened" with all three numbers | write a 4-second clip and say nothing (`trigger.h:47-53`) |
| `asr-absent` | `w_K` is pinned 0.00 | "Text signal not yet in the score" | imply the text channel is contributing |
| `scoring-deferred` | machine is in a match (`specs/01` §5 tier 3) | "Highlighting paused while you play" | run anyway and take cores from capture (law 1) |

**The rule underneath all eight:** *no state may resolve to "success with no output" unless it
names which of these it was.* A highlights system that produces nothing and says nothing is
indistinguishable from a broken one, which is the failure mode `AGENTS.md` law 6 already names
for the encoder ("no encoder → no armed key, and a loud reason") and this spec adopts verbatim.

---

## 7. PARAMETERS — value, unit, and why this value

| parameter | value | unit | kind | reason |
|---|---|---|---|---|
| `W_A` | **0.60** | weight | CHOICE | makes the speech conjunct load-bearing: with `A=0` max score 0.40 < threshold |
| `W_E` | **0.40** | weight | CHOICE | the excursion cannot carry a highlight alone, by construction |
| `W_K` | **0.00** | weight | PINNED | no real-time ASR exists (`transcribe.py:47`) — pinned, not absent |
| `THRESHOLD` | **0.75** | score | CHOICE | ≥ 0.40 + 0.375·1.0; see §3 |
| `MIN_GAP_S` | **20.0** | s | CHOICE | > max measured segment **13.82 s** + tail, so highlights cannot overlap |
| `MIN_DYNAMIC_RANGE` | **3.0** | ratio `p99/p50` | CHOICE, band 2–5 | between the measured **1.22×** (tone) and **19.90×** (speech) |
| `PEAK_REFERENCE_S` | **300.0** | s | CHOICE | trailing normalisation window; ≥ the ring's 120 s GAMING memory |
| `PRE_ROLL_S` | **6.0** | s | CHOICE, band 3–10 | lead-in before the peak; must cover visual onset before audio |
| `POST_ROLL_S` | **8.0** | s | CHOICE, band 5–15 | the moment resolves after the peak |
| `MERGE_GAP_S` | **1.0** | s | **MEASURED** | 80 % of measured inter-segment gaps ≤ 1.0 s; median −0.20 s |
| `SAMPLE_RATE` | **16 000** | Hz | **MEASURED** `constants.py:91` | the ASR contract |
| `LEVEL_HZ` | **10** | Hz | **MEASURED** `constants.py:172` | the level event rate |
| `FRAME_MS` | **20** | ms | **MEASURED** `segment.py` const | the splitter's RMS frame |
| IDR grid GAMING | **2.0** | s | **MEASURED** `specs/03` §2.5 | bounds the snap-back error |
| IDR grid DESKTOP | **10.0** | s | **MEASURED** `specs/03` §2.5 | bounds the snap-back error |
| `FP_ALPHA_PER_10MIN` | **20.0** | per 10 min | **MEASURED 15.00** | the v1 ceiling the gate enforces |
| `FP_BETA_PER_10MIN` | **1.0** | per 10 min | **MEASURED FAIL (15.00)** | the product target; **unreachable with audio alone** |
| false negatives | — | — | **NOT MEASURED** | no labelled corpus exists; **no recall claim is made** |

---

## 8. MILESTONES — every pass condition is observable, and every one is currently RED

Each milestone names the command that decides it. **None of these has been run except M0.**

| # | milestone | observable pass condition | how it goes RED | state |
|---|---|---|---|---|
| **M0** | **the scorer exists and is falsifiable** | `py -3 _main/oracle-07-highlights.py` → `VERDICT PASS`, **exit 0**, ≥1 emit on real speech, 0 on both garbage corpora, >0 on the naive control | any arm fails; **the oracle itself returning 2 is also RED** | ✅ **DONE — exit 0** (`oracle-07-highlights.log`) |
| **M1** | **the honest census** | a clip census over the whole library reports `audio_streams` per clip, and `no-audio-stream` is a distinct state from `scored-no-candidate` | the two states collapse into one | ✅ **DONE — 27/27** (`_hl07-audio-census.txt`) |
| **M2** | **audio exists end-to-end** | one capture whose clip `ffprobe` reports `codec_type=audio`, **and** the scorer runs on it without a `--wav` file argument | the clip is video-only (today's state) | ⛔ **BLOCKED — lane L2** |
| **M3** | **the ring can be asked** | `replay.cpp:125` stops discarding `seconds_kept`, `RingSpanProbe::span_seconds()` returns a real number during a live run, and highlights emit `ring_span_s` | `ring-too-short` never appears in the log, or the value is −1 | ⛔ **BLOCKED — ring lane** (the `(void)` is theirs to fix) |
| **M4** | **a labelled corpus exists** | ≥ 60 min of real gameplay, **human-labelled**, with the labels in a file the oracle reads | the oracle still measures rate, never recall | ⛔ **BLOCKED — needs the owner + a game** |
| **M5** | **β becomes reachable** | on the M4 corpus, the rate falls ≤ 1 / 10 min **with at least one non-audio signal enabled** | it stays at ~15 / 10 min, which is the measured ceiling of audio alone | ⛔ **BLOCKED on M4** |
| **M6** | **v2 ships, default OFF** | with `w_K` or an S4 feed live, the panel shows the score's composition per highlight | the panel shows a highlight with no provenance | ⛔ **blocked on M2–M5** |

**The dependency chain is M2 → M4 → M5, and not one link of it is a task this lane can pull.**
That is the real content of this spec.

---

## APPENDIX A — THE HONEST VERDICT: is automatic highlighting worth building before instant replay and audio exist?

**No. And the argument is not a preference — it is three measurements.**

**1. The signal does not exist, and its absence is not incremental.**
27 of 27 capture outputs have no audio stream (§1.1). Not "low coverage", not "noisy" —
**zero**. The ASR is file-fed by contract (`transcribe.py:47`). So every audio-based candidate
signal in §2 has **N = 0 in-product measurements**, and the entire scoring rule in §3 would ship
having been validated on a radio broadcast and a synthetic noise bed.

**2. The signal that exists is measurably the wrong signal.**
On real continuous speech the rule emits **15.00 highlights per 10 minutes** — because speech
covers 72.3 % of the audio with a median segment of 6.98 s, so "a phrase happened" carries
almost no information. β (≤ 1 / 10 min) fails by 15×, and no threshold tuning fixes a failure
whose cause is that the feature is measuring the wrong thing. **A highlights feature that fires
every 40 seconds is worse than no highlights feature**, because the user learns to ignore the
highlight surface, and that lesson does not unlearn.

**3. What exists today already does this job worse.**
There is no hotkey (`receipt-13`, 0 hits across `src/capture`). Instant replay is the product's
central promise and it does not exist. Highlights is a **second-order** feature whose input is
missing, being scoped ahead of a first-order feature whose input exists and whose trigger is
simply not wired. **`trigger.h` exists; a highlights scorer does not.** That ordering is the
whole verdict.

**The counter-argument I weighed, stated fairly.** Instant replay needs the ring to be sized
right (the VRAM/RAM defect, receipt-14) and needs a key that is **UNMEASURED inside a
fullscreen game** (`trigger.h:34-38`: "no game was run"). So there is a real argument that
instant replay also has an unmeasured hole, and that highlights could be specced in parallel
"while the ring work happens". That argument fails on scope: parallelising means two features
competing for the same unmeasured ring window, and highlights is the one whose *input* is
absent, not merely unmeasured. Parallel work is justified between "unmeasured" and "measured".

**What this spec is therefore FOR**, if not for shipping the feature:

- it **names the dependencies** (§1.4, §8) so they can be scheduled against something real;
- it **fixes the failure vocabulary** (§6) so that when audio does arrive, the absent-signal case
  is loud instead of looking like "no highlights found";
- it **establishes the FP budget and the falsifier** (§5) as a gate that is RED today and stays
  RED until the corpus exists — which is the correct state for an instrument, and the opposite
  of a plausible sentence filling a measurement gap;
- and it **records that audio-only scoring cannot reach β** (§5.2), so whoever picks the game
  title knows in advance that the event layer is not an optimisation, it is the feature.

---

## APPENDIX B — THE REVIEWER'S QUESTION, AND ITS VERDICT

The mandated reviewer question:

> **"would this heuristic call a random 30 seconds of a walk in the park a highlight?"**

**The independent subagent review was NOT dispatched — see the blocker in the lane report.** No
dispatch tool was available in this session's toolset, so the question was answered by running
it as a falsifier instead, with the answer in numbers:

| rule | highlights from 180 s of a walk |
|---|---|
| **the spec's rule (§3)** | **0** — state `degenerate-signal`, dynamic range **1.22×** vs the 3.0 gate |
| the naive rule the spec replaces (§5.3) | **8** |

**Verdict: NO — this heuristic does not call a walk a highlight, and the number that says so is
the 1.22× dynamic range against a 3.0 gate, not a judgement.** The caveat that must travel with
that answer: the walk corpus is `SYNTHETIC` (`oracle-07-highlights.py:synth_walk_bed`) because
no recording of a walk exists on this box, and the positive arm is a **radio broadcast**, not
gameplay. The claim proven is *"flat non-speech audio cannot fire this rule"* — a narrower claim
than *"this rule finds real highlights"*, which is **NOT MEASURED** and is not asserted anywhere
in this spec.