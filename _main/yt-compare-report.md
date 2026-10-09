# yt-compare report — video 1XQ-_28efrE vs Sotto history vs redux vs nemotron

Date: 2026-10-08. Workdir H:\sotto. Shipped code untouched (read-only); new files only under `_main/`.

## 0. HEADLINE: the video ID does not match the owner's description

`py -3 -m yt_dlp --print "%(title)s | %(duration)s | %(upload_date)s | %(channel)s" "https://youtu.be/1XQ-_28efrE"` returns:

> OBRIGADO RIOT! O VOLIBEAR AD NUNCA FOI TÃO FORTE | 933 | 20261007 | Mylon

That is a League of Legends / Volibear gameplay video (channel Mylon, uploaded 20261007,
duration 15:16), NOT the Anthropic Claude Haiku 5.5 video the owner described (benchmarks,
Minecraft clone, Gamut sponsorship — the sample text in `_main/ab-input.txt`).
So **there is no overlapping span to compare**: the YouTube captions, the Sotto history, and
`_main/ab-input.txt` describe two different videos. Everything below is exact, nothing invented.

## 1. Captions download (STEP 1)

- yt-dlp installed: version `2026.08.19` (`py -3 -m yt_dlp --version`).
- Manual subs first:
  `py -3 -m yt_dlp --skip-download --write-sub --sub-lang en --sub-format vtt --output "_main/yt-1XQ-_28efrE.%(ext)s" "https://youtu.be/1XQ-_28efrE"`
  → `[info] There are no subtitles for the requested languages`. **No manual subs exist.**
- Fallback auto-subs:
  `py -3 -m yt_dlp --skip-download --write-auto-sub --sub-lang "en.*" --sub-format vtt --output "_main/yt-1XQ-_28efrE-auto.%(ext)s" "https://youtu.be/1XQ-_28efrE"`
  → wrote `_main/yt-1XQ-_28efrE-auto.en-orig.vtt` (**133 787 B**, **675 cues**,
  span **00:00:00.100 → 00:15:16.546**). A second request (`en` lang) hit HTTP 429; the file
  on disk is complete (ends with a proper closing cue + trailing newline).
- **Kind obtained: AUTO-SUBS (ASR), English.** No manual captions.
- Topic check on the plain text of the VTT: `Volibear` ×18; `Haiku`/`haiku` ×0,
  `Gamut`/`gamut` ×0, `Anthropic`/`anthropic` ×0, `Minecraft`/`minecraft` ×0, `sponsor` ×0.
  First cue: "We've got a killer top lane matchup." — LoL content start to finish.

## 2. Local sources (STEP 2)

- `I:\!produtos202608\BrandOps` — **EXISTS**, but is a code checkout (brands, dashboard, docs,
  estudio, inbox, repos, runs, scripts …). Top-level listing shows no video/audio file.
- `C:\Users\Administrador\Desktop\Nova pasta (3)\TESTE\VOD.RIP` — **EXISTS**, also a code
  checkout (backend, dist, e2e, installer, src, test-results …). No video/audio at top level.
- `_main/` clips: `en-us-sample.wav` (8.5 s), `live-sample-cable-input-90s.wav` (90 s),
  `live-sample-cable-input.wav`, `denoise-90s-on.wav`, `agc_drone_floor.wav`,
  `_redux-long/gap-120s.wav`. None is the YouTube video's audio.
- Per instructions the YouTube video itself was NOT downloaded. **No matching local audio
  exists**, so STEP 4 ran as a calibration pair (see §4), not a video comparison.

## 3. Sotto transcription in history/ (STEP 3)

Needles from `_main/ab-input.txt` (`Haiku`, `Gamut`, `sneven`, `bull run`, `Tropic`, `IPO`,
`Minecraft clone`, `cave system`, `water physics`, `cloudcode`, `subag`, `Openai`) plus
video-topic words (`Volibear`, `Riot`, `Mylon`, `top lane`, `League`, `patch`, `benchmark`,
`Gamut`, `sponsor`, `Anthropic`, `Opus`, `GPT`) were grepped over `history/`:

- **Zero matches** for every owner-video needle (Haiku/Gamut/sneven/bull run/Tropic/IPO/
  Minecraft clone/cave system/water physics/cloudcode). The `GPT`/`benchmark` hits in
  `history/2026-10-06/19.md` and `11.md` are other videos (Hark/GPT-Live dev content, GPT Next news).
- **Zero matches** for the actual video's topic either (Volibear/Riot/Mylon/top lane/League) —
  the owner never transcribed this Volibear video with Sotto either.
- Newest history file overall: `history/2026-10-06/19.md` (mtime 2026-10-06 19:58).
  `history/2026-10-07/14.md` contains only the en-us-sample selftest lines.
- **Conclusion: the owner's ~7 min Sotto transcription of the Haiku video is NOT in
  `history/`.** Either it was never recorded (Sotto not running / panel closed with no
  batch pass), or it lives outside `history/`. `_main/ab-input.txt` (32 lines, the owner's
  pasted sample) is the ONLY local copy of that transcription found.

## 4. Engine runs (STEP 4) — calibration pair on `_main/en-us-sample.wav`

Same audio for both engines. Commands verbatim:

- `py -3 worker/redux_batch.py --wav _main/en-us-sample.wav --json` → stdout saved to
  `_main/yt-compare-redux.txt` (stderr → `_main/yt-compare-redux.stderr`).
- `py -3 worker/sotto_worker.py --selftest --audio _main/en-us-sample.wav` → stdout saved to
  `_main/yt-compare-nemotron.txt` (stderr → `_main/yt-compare-nemotron.stderr`).

Reference text (the bundled sample): "The radio announced that the bridge over the river
will be closed next Monday. Residents need an alternative route to get to work." (21 words)

| engine | result text | WER (word-level, case/punct-insensitive) |
|---|---|---|
| redux (parakeet ternary, `worker/redux_batch.py`) | byte-identical to reference, 2 segments, duration 8.543 s, compute 1.723 s, RTF 4.96 | **0/21 = 0%** |
| nemotron streaming (`worker/sotto_worker.py --selftest`) | "The Radio **anoud** that the bridge over the river will be closed next **Mone.** Residents need an alternative route to get to work" (final:true lines; selftest-done: 59 tokens, blank_frac 0.6402, infer 3.507 s, RTF 0.417, peak RSS 2409.2 MB) | **2 subs / 21 = 9.5%** (0 drops, 0 inserts) |

Census detail (nemotron vs reference): subs = {announced→anoud, Monday→Mone}; capitalization
diff = "Radio" mid-sentence cap; punctuation = sentence-1 period present, otherwise same.
No word-split seams, no hallucinations on this clip. Redux: no diffs of any kind.

## 5. Three-way comparison over the overlapping span (STEP 5)

**There is no overlapping span.** YouTube captions = Volibear gameplay EN auto-subs;
Sotto history = no lines from either this video or the Haiku video; `ab-input.txt` = Haiku
video (different video); engines ran on the bundled calibration sample. A word-level
YouTube-vs-Sotto-vs-engine census cannot be constructed without inventing data, so none is.

## 6. Top 3 improvement candidates (from the calibration pair — the only measured evidence)

1. **nemotron `announced → anoud`** — mid-word vowel/consonant-cluster collapse on a common
   word redux gets right. Candidate: check RNNT greedy vs beam on -ounced rimes.
2. **nemotron `Monday → Mone`** — word-final truncation (`day` → `e`); same family as the
   chunk-seam splits fixed 2026-10-08, but here on a short clean clip. Candidate: look at
   end-of-word token starvation in the streaming decoder.
3. **nemotron spurious mid-sentence capitalization (`Radio`)** — truecasing noise redux does
   not produce. Candidate: post-decode truecaser or capitalized-vocabulary bias.

## 7. Files produced

- `_main/yt-1XQ-_28efrE-auto.en-orig.vtt` — raw YouTube AUTO captions (en).
- `_main/yt-compare-redux.txt` / `_main/yt-compare-redux.stderr` — redux calibration output.
- `_main/yt-compare-nemotron.txt` / `_main/yt-compare-nemotron.stderr` — nemotron calibration output.
- `_main/yt-compare-report.md` — this file.

## 8. Open question for the owner

The video ID `1XQ-_28efrE` resolves to a Mylon Volibear video, not the Haiku 5.5 video.
To do the real comparison we need the correct Haiku-video URL (or the local audio file),
plus where the ~7 min Sotto transcription was saved if not in `history/`.
