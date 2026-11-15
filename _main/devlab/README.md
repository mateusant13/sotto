# The Sotto dev lab -- a repeatable way to exercise the real pipeline

Owner order, verbatim: *"make a very easy way to test sotto"*, *"design a repeatable, stepped,
complex-but-real scenario sotto must handle greatly"*, *"never on the owner's screen, never focus,
never audible"*, *"content-keyed cache so nothing cold-repeats"*.

Entry point: **`Sotto.cmd dev`**. Everything below is measured in this tree, on this box.

## 1. Why the audio does not come from a browser

Four arms measured 2026-11-15, all on `https://youtu.be/rS4VMlwf2qM`:

| arm | play | seek to 60 | recovered |
|---|---|---|---|
| headless, plain | yes | parks `readyState=1 networkState=2` | **no** |
| headless, anti-throttling flags | yes | parks | **no** |
| headless, wait-then-play | yes | parks | **no** |
| headed, offscreen | yes | works | yes -- but **steals focus** |

Focus is forbidden, so playback from a browser is out for audio. The consequence is the whole
design: **the audio comes from the video's own stream**, downloaded once and cut locally.

That is strictly better than playback for a lab anyway:

* exact, byte-identical windows (`ffmpeg -ss`), not an estimate of what the player buffered;
* cacheable by content, so a re-run costs nothing;
* **inaudible by construction** -- the samples are read from a file, so there is nothing to render
  and no endpoint is ever opened.

The browser is still the right tool for the *caption* path, which needs the page and not the
speakers -- see §5.

## 2. The three cost facts the lab must not re-pay

Measured, and each one changed the code:

1. **`--max-seconds` counts from PROCESS START, but capture begins AFTER the model loads.**
   A run measured `load_s=24.59` (`private_mb=1734.4` at `model-loaded`). Launched at
   `--max-seconds 26`, only ~1.4 s of a 20 s window was ever drained. Coverage swung
   0.34 / 0.58 / 0.68 / 0.71 across identical runs -- the lab measured its own budget.
   Now `run_budget()` = `load_estimate() + window + 12 s`, and `load_estimate()` reads the
   `load_s` a previous run already published. Nothing is guessed when a measurement exists.
2. **The worker's `FileTap` loops the file.** That is correct for a live stream and wrong for a
   finite window: with a generous budget it replays the window while the model is still loading,
   and the HYP text repeats whole phrases. `SOTTO_FILE_TAP_ONCE=1` now ends the stream at EOF
   (`file-tap-eof`), which the lab sets by default. The loop stays the default for real runs.
3. **The download cache keyed on the wrong extension.** `source_file()` tested for `<id>.m4a`
   while yt-dlp wrote `<id>.webm`, so 53.5 MB was re-downloaded on every run. It now keys on the
   path the marker recorded and prints `CACHE HIT source ... (53.5 MB)`.

## 3. Commands

```text
Sotto.cmd dev                       # reuse cache, else build 60:20, then score
Sotto.cmd dev 60:20                 # explicit window (start:seconds)
Sotto.cmd dev 300:20,600:15         # several windows, one process
Sotto.cmd dev --video <id> ...      # another video
Sotto.cmd dev --strips              # ablate the pipeline on the same audio
Sotto.cmd dev --selftest            # judge the audibility gate itself
Sotto.cmd dev --status              # what is cached
python _main/devlab/lab.py mix --video <id> --window 60 20 --mix 6   # S1b: speech + bed
python _main/devlab/lab.py concurrent --video <id> --window 60 20 --second-start 100  # S4
python _main/devlab/lab.py captions        # S2: the real extractor over a fixture player
python _main/devlab/lab.py captions-neg    # S2 control: every mutant must break its named check
```

Under it: `_main/devlab/lab.py`, whose whole command set is `harvest`, `window`, `feed`, `score`,
`strips`, `mix`, `captions`, `captions-neg`, `concurrent`, `status`, `selftest`. Nothing is
advertised here that the file does not implement -- `python _main/devlab/lab.py <cmd> --help` is the
authority.

## 4. The scoring contract

* **Ground truth is the video's own captions** (`yt-dlp --write-auto-subs --sub-format json3`),
  sliced to the window by **event midpoint, strict interior**. Including events that merely
  overlap the window put words spoken before it into the reference and turned a coverage problem
  into a 0.779 WER that measured the slicer.
* **Only closed lines count.** A real feed produced 23 `final:false` partials against 3 finals, and
  every partial is a prefix of the next -- counting them inflates the transcript.
* **Coverage is reported beside WER**, because a low WER over a third of the window is not a good
  score. `SCORE population: finals=.. ref_events=.. dropped=.. ref_words=.. hyp_words=..
  coverage=..` is the line that makes a WER readable.
* **Cost is reported with every run**: `SCORE cost: wall=..s peak_private=..MiB threads=2`.

## 5. The stepped scenarios

Each step states what it proves and what a failure looks like. A step that cannot be measured says
`CANNOT-MEASURE` and why -- never a green.

### S1 -- single source, single window
One cached window through the live loop, scored against captions. **Proves**: model quality on real
audio. Fails as: coverage < 0.9 with the budget derived (the window was truncated), or WER rising on
an unchanged input (non-determinism).

### S2 -- seek, subtitles on and off
`lab.py captions`. **Why this is not the live YouTube page** (measured 2026-11-15, five arms):
real headless YouTube refuses to serve captions -- `is_servable: false` on every track, an empty
`.ytp-caption-window-container` through 16 s of playback, and the track's own `baseUrl&fmt=json3`
returning a **0-byte** body from inside the page. So the browser arm cannot be a YouTube arm, and a
green there would prove nothing. What is proven instead is the part that is ours: a headless Chrome
is served a loopback page at a real `/watch?v=<id>` URL, so the **shipped** target picker
(`list_targets`/`pick_target`) sees it exactly as it sees a YouTube tab, and the **shipped** extractor
(`EXTRACT_JS`) plus `parse_snapshot` read its DOM.

The player is cue-driven: which caption is on screen is a function of the page's clock, so a seek
changes the line without the lab touching a caption element. Captions are toggled through the SAME
two doors a person uses -- the `c` key (`Input.dispatchKeyEvent` into the page's own handler) and the
CC button's own click handler (`Input.dispatchMouseEvent`) -- and the lab never writes a caption line.

23 checks: the fixture page is confirmed ready (a reused port serving a
stale browser's page is refused, not measured); before anyone enables subtitles there are zero rows and `why` is `no-painted-caption`;
after the `c` key the player's line appears, segments carry geometry and `why` says `painted`; a seek
replaces the old cue with the new one and carries the new `t`; a two-line cue keeps both and the
`>>` speaker marker is stripped; pressing `c` again clears the rows and names the state
`no-painted-caption` (not `painted`, not `no-window`); seeking with subtitles off brings back no
line; the CC button's handler turns them back on; the `paused` flag surfaces and `player_stopped`
agrees, and a cleared flag is not a pause; a box holding only the player's own notice (an
`svg`/`button` in the line) is dropped **and** named `no-painted-caption`, because `painted` beside
zero lines is the log line that sends the next measurement looking at the wrong thing; the shipped
picker sees and names the tab; and the foreground window is unchanged before and after.

`captions-neg` is the control: three mutants of the shipped module, each paired with the one check it
must break (chrome filter removed, marker not stripped, empty box still called painted). Measured
`S2 NEG-ARM: PASS -- 3/3 mutants caught`, each by its named check. A mutant whose anchor vanished
reports `ANCHOR-GONE` rather than counting as caught -- a control that was never planted proves
nothing.

### S1b -- the same speech against a real bed, at a declared SNR
`lab.py mix --mix <DB>` builds a second window from the clean one by adding the **owner's own**
captured audio (`_main/live-sample-cable-input-90s.wav`, 50.0-88.0 s -- non-speech by two independent
instruments: the Redux ASR finds no words and the pyannote segmenter finds no speech there, while
both find speech at 29.5-49.4 s of the same file). SNR is `20*log10(rms(target)/rms(bed))` measured on
the written file and stored beside it, never the requested number.

Cross-checked against an independent recomputation: `bed_gain=6.1181` from the lab, `6.1181` from a
separate script that re-derives it from the two files. The peak scale preserves SNR because it scales
both terms.

Measured 2026-11-15, window `60:20` of `rS4VMlwf2qM`:

| audio | coverage | WER | wall |
|---|---|---|---|
| clean | 0.81-0.92 | 0.32-0.37 | 81-92 s |
| + bed @ 6 dB | **0.66** | **0.559** | 89 s |

That gap is the point: every score this lab produced before today came from clean audio, and a clean
window cannot show the failure class that ate 72 % of a real broadcast.

### S3 -- pipeline strips (ablation)
`strips` runs the same audio with ONE stage removed per row. **Proves**: which stage actually buys
quality and which only buys latency. Fails as: a strip that changes nothing (dead code) or a strip
that improves WER (a stage is hurting).

Each name states the knob that really removes that stage. Two entries were **lies** until
2026-11-15 and both were caught by measuring: `no-denoise` set `SOTTO_GATE=0`, the SPEECH GATE, so
the row named a stage it never touched; and `single-thread` set `SOTTO_WORKER_THREADS`, a variable
that exists nowhere in the product (`grep -rn SOTTO_WORKER_THREADS` returned that line only) -- the
worker's real knob is `--threads`, and `effective_threads()` reads the flag BEFORE the environment, so
no env var could ever have won. A strip whose knob does not exist is not a cheap strip; it is the same
run counted twice under a confident name.

**The instrument has a measured noise floor, and the verdict respects it.** Two identical runs:

| strip | run 1 | run 2 | spread |
|---|---|---|---|
| live-only | 0.3220 | 0.3729 | 0.051 |
| batch-on | 0.3559 | 0.3220 | 0.034 |
| single-thread | 0.3898 | 0.3898 | 0.000 |

So a single run cannot order two strips that differ by less than ~0.05 -- and the first version of this
table reported `batch-on` as worse than `live-only` while the next run reported the reverse. `--repeats
N` measures the spread and the verdict prints `STRIPS-best ... CLEARS it` only when the gap exceeds
it, otherwise `UNDECIDED` with the instruction to repeat. `selftest` judges that judge with both arms
(a noise-sized gap, and a real one).

**Measured with `--repeats 3`** (2026-11-15, caged `--cpu 40 --io very-low`, 4 strips x 3 runs,
1 083 s; `STRIPS-best batch-on wer=0.3051 by 0.0678 (noise=0.0339, CLEARS it)`):

| strip | WER | spread | coverage | wall | peak private |
|---|---|---|---|---|---|
| **batch-on** | **0.3051** | 0.0169 | 0.88 | 87.1 s | 3 177 MiB |
| live-only (default) | 0.3898 | 0.0339 | 0.73 | 93.5 s | 3 312 MiB |
| single-thread | 0.3729 | 0.0339 | 0.75 | 90.0 s | 3 277 MiB |
| gate-on | 0.7119 | 0.0170 | **0.34** | 90.3 s | 3 312 MiB |

Three findings, each one an order that now has a number behind it:

1. **The Redux batch pass is worth 0.085 WER and 0.15 coverage**, and it costs nothing measured (it is
   also *faster* and holds *less* memory here). `SOTTO_REDUX_WHEN_HIDDEN=1` is the knob. The product
   only arms it when the panel is hidden, so this is the number for the "listening in the background"
   case the owner actually uses.
2. **The speech gate destroys the transcript on real speech**: coverage 0.34, WER 0.71. That is the
   same defect measured on the owner's own log on 2026-11-15 (`music_gated_chunks=19`, captions frozen
   at 8.4 s while the reference continues to 67.1 s). It is why the product's default is OFF.
3. **Halving the threads costs 0.017 WER** (inside the noise) and buys ~1 CPU core. The thread budget
   of 2 is not paying quality; a 1-thread budget is a legitimate future knob for a weaker box.

### S4 -- two workers at once: what must NOT be shared
`concurrent` launches **two real workers on two different cuts of the same track**, both alive at the
same moment, both under the same declared 2-thread ceiling, and judges what isolation means here.

**The claim is scoped to what the product has.** The shell constructs exactly ONE `WorkerBridge(` and
the worker opens ONE tap, so "two programmes at once" is not a topology this product runs. Pretending
to feed two programmes to one worker would measure a design that does not exist. What IS load-bearing
and was never measured is that two worker processes on one box do not collide:

| row | what a collision would look like |
|---|---|
| both produced text | one starved and returned an empty transcript |
| the transcripts are NOT the same text | a shared state file or chunk trace collapsing them |
| each wrote its OWN stdout file | a shared path, one run overwriting the other |
| the two ran CONCURRENTLY (wall < 0.9x the sum) | a shared lock serializing them |
| no worker process was left running | a leak holding ~1.8 GiB of commit |

The judge is a **pure function** (`_concurrent_judge`) so its control can exist: `selftest` feeds it a
pair with a shared artifact (one stdout path, one text) and requires the four isolation rows to go
red, then a clean pair (green), then a clean pair plus a live pid and requires the leak row alone to
fail. A judge only exercisable by launching two workers costs ~3 min per arm, and nobody would ever
run its negative arm -- that is how a control becomes decorative.

Class `heavy`: it pays the model load twice. It runs in the battery as `concurrent-workers` and only
with `SOTTO_BATTERY_HEAVY=1`.

### S5 -- chaos
`chaos` drives the transitions a person actually makes while speech is on screen: a seek that lands in
a **gap** between cues, six seeks in a burst, captions toggled **mid-line** (both the `c` key and the
CC button's own handler), a **track swapped** under the same URL, a finished video, mute, a pause
mid-line, and a playback-rate change. **Proves**: the surface always describes the current state --
never a stale line, never a blank that fails to come back, never two lines where the cue has one.
Fails as: a stuck line, a duplicated line, or a blank surface that never recovers.

`chaos` runs **24 checks** over **9 transitions** (2026-11-15, 2.0 s, cache-warm) and `chaos-neg`
runs four mutants, each tied to the ONE check it must break:

| mutant | must break |
|---|---|
| `ended` ignored, so a finished video keeps its last line | T5 reads an ended video as stopped |
| a pause that names no reason is read as stopped | T7 a payload with no pause field is not a stop |
| an empty box is still reported as painted | T8b a `painted` claim with zero rows is renamed |
| the chrome-window notice reaches the screen as a line | T8b the player's notice window is not read as a line |

**The drill found a product defect on its first run.** `EXTRACT_JS` published `t`, `paused`, `rs` and
`rate` -- and never published `ended`. The shell computes `yt_cdp_ended = bool(snap.get('ended'))`, so
that read was `False` for the whole life of the code: a finished video never read as finished. The
shipped CDP oracle passed anyway because it handed `player_stopped` a hand-built dict; the arm measured
the *decision*, never asked whether the field could *arrive*. Fixed in both halves -- the extractor
publishes `ended`, and `parse_snapshot` passes it through with absence staying `None` (a stale payload
must not assert that the video ended) -- and the oracle gained three arms that close the chain:
`js_ended` (the JS publishes it), `parse` (it survives parsing), `absent_none` (a payload without it
yields `None`, not `False`). Measured after: `VERDICT: PASS (26/26)` with
`js_ended=True parse=True absent_none=True`.

### S6 -- two DIFFERENT cuts at once: which reference does each text match?
`crosstalk` launches two real workers on **two different windows of the same track** -- different
audio, different captions, so the two references cannot coincide -- and asks the one question a
mixed transcript cannot pass: for each worker, does its own text score better against its OWN
captions than against its sibling's?

| row | what a leak looks like |
|---|---|
| `concurrent-a matches its OWN reference better` | both scores tie (shared audio) or invert (it heard the sibling) |
| `concurrent-b matches its OWN reference better` | same, from the other side |

The assertion is a **comparison, never an absolute WER**: an absolute threshold would need a WER
budget nobody has measured on this box, and a comparison is a property of isolation that costs
nothing to state. Three refusals are named rather than implied -- a `None` WER (a cut with no
reference) is `CANNOT-MEASURE` and fails; two identical references make the comparison vacuous and
fail; and a **tie** fails, because a tie is precisely the leakage the arm exists to catch.

**Measured 2026-11-15** (caged `--cpu 40 --io very-low`, two workers, pair wall 93.3 s, peak
private 3 327 + 3 329 MiB; `S6 CROSSTALK: PASS (2/2)`):

| worker | WER vs own captions | WER vs sibling | margin |
|---|---|---|---|
| concurrent-a | 0.4237 | 0.9683 | +0.5445 |
| concurrent-b | 0.4444 | 0.9661 | +0.5217 |

The two references are genuinely different (`a` 17 events / 60 words, `b` 21 / 65, `identical=False`),
so the margin is not an artefact of two similar cuts. The absolute WER is high because these are 20 s
windows of accented broadcast speech, not the point of the arm: the point is that each text describes
**its own** audio by half a WER unit.

Class `heavy` (the model loads twice). Battery step: `devlab-crosstalk`, `SOTTO_BATTERY_HEAVY=1`.

## 6. What this lab does NOT prove

`verified` still requires the owner running the real app. The lab never opens an audio device, never
registers the hotkey, and never shows a window: `selftest` is the gate that proves the silence
claim itself (21/21 arms: the audibility meter's four, the planted-peak control, the capture
protocol's three, and eleven that judge the S3, S4 and S6 judges in both directions).

**Per-programme taps are not exercised here, and `crosstalk` does not claim to.** The product grows
them with `--target-name`, and a file tap deliberately bypasses the whole device/tap layer. What
`crosstalk` (S6) pins is the claim that has to survive the day a second tap lands, so that day
already has a judge waiting: two DIFFERENT cuts through two workers at the same moment, then, for
each worker, `wer(own_text, own_ref) < wer(own_text, sibling_ref)`. A leaking worker scores the same
against both and fails; a worker that heard its sibling scores *better* against the sibling and
fails harder. The judge is pure (`_crosstalk_judge`) and its negative arms are in `selftest` --
a leak (a tie), an inversion, a `None` WER, and an empty population.

Class `heavy`: it pays the model load twice. It runs in the battery as `devlab-crosstalk` and only
with `SOTTO_BATTERY_HEAVY=1`.
