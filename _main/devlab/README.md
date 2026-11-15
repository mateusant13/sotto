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
```

Under it: `_main/devlab/lab.py`, whose whole command set is `harvest`, `window`, `feed`, `score`,
`strips`, `status`, `selftest`. Nothing is advertised here that the file does not implement --
`python _main/devlab/lab.py <cmd> --help` is the authority.

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
Browser arm, captions toggled on the page (the `c` key and the button are different code paths).
**Proves**: the YouTube-caption source follows the page's track, and turning subtitles off is not
mistaken for "no captions exist". Fails as: Sotto shows the previous line after the track is off.

### S3 -- pipeline strips (ablation)
`--strips` runs the same audio with one stage removed at a time. **Proves**: which stage actually
buys quality and which only buys latency. Fails as: a strip that changes nothing (dead code) or a
strip that improves WER (a stage is hurting).

### S4 -- two concurrent sources
Two different programmes through per-process taps at once. **Proves**: per-program isolation and no
cross-talk. Fails as: one source's words in the other's transcript.

### S5 -- chaos
Seek during speech, mute/unmute, second audio starting mid-sentence, subtitles toggled mid-line.
**Proves**: the state machine survives transitions. Fails as: a stuck line, a duplicated line, or a
blank surface never recovering.

## 6. What this lab does NOT prove

`verified` still requires the owner running the real app. The lab never opens an audio device, never
registers the hotkey, and never shows a window: `--selftest` is the gate that proves the silence
claim itself (10/10 arms, including "planted peak -> AUDIBLE" as the control).
