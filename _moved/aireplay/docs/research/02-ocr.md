# 02 — OCR stack for Shadow Memory (on-screen text as a searchable channel)

Question (one): **which OCR stack do we ship so that game HUD / subtitles / chat / dialogue /
error messages become a searchable channel — cheap enough to run alongside a game?**
Every claim is tagged **MEASURED** (a command here produced it), **READ** (a source says it),
or **UNKNOWN**. Instruments: `_main/ocr_frames.py`, `_main/ocr-bench-02.py`,
`_main/_winocr-probe.ps1`, `_main/_ocr-trigger-probe.py`, `_main/ocr-score-02.py`. Raw:
`_main/ocr-bench-02.json`, `_main/ocr-winocr-raw.txt`, `_main/ocr-trigger-02c.json`,
`_main/ocr-score-02.json`.

## 0. What was run on this box, and one warning about the numbers

- **MEASURED** — the box is an `i5-13600K` (14C/20T) with an `RTX 5080 16 GB`, driver 617.14
  (`Get-CimInstance Win32_Processor`, `nvidia-smi`). torch sees CUDA; **ORT's
  `CUDAExecutionProvider` is requested but not loadable on this box** (Sotto's `AGENTS.md`,
  inherited law) — so the RapidOCR numbers below are **CPU** numbers.
- **MEASURED** — the frames are **synthetic game-like frames I generated** (1920×1080: gradient +
  noise + 14 polygons + 600 bright rectangles as clutter, then HUD in four corners, chat lines,
  an error toast and a centred subtitle on a translucent bar). **No screen was captured.**
  Arms: clean / low-contrast chat / 0.7× text / 2 px blur / 4 px blur / 50 % frame dim / CJK
  subtitle / Cyrillic subtitle.
- **WARNING, read before quoting any latency below.** The owner's box was running many other
  Python processes and TreeSizeFree during this work, and commit charge fell to **0.63 GB free of
  67.8 GB limit** (`Win32_OperatingSystem`), which made ONNX Runtime raise
  `bad allocation` twice and made timings swing wildly (the same 1080p frame measured 2.4 s, 5.8 s,
  7.5 s, 10.9 s and 24.6 s across runs). **The latency figures are a recorded range, not a
  benchmark.** The accuracy figures are unaffected by load (deterministic output) and are what I
  would trust.
- **MEASURED** — I tried to extract real game frames from the owner's own
  `I:\importantes\Videos\Fortnite\Fortnite 2024.01.03 - 20.57.10.07.DVR.mp4` (ffprobe: h264,
  1920×1080, 60 fps, 15.33 s). `ffmpeg -vf fps=1` produced **0 files in >10 minutes** — that
  drive reads are too slow for this lane. So **the accuracy numbers are on synthetic frames**,
  and real-footage accuracy is **UNKNOWN**.

## 1. Which engine

| engine | on this box | PT-BR + EN | licence | install weight | 1080p CPU cost |
|---|---|---|---|---|---|
| **RapidOCR 3.9.2 + PP-OCRv6-small** | **installed, models on disk** | one Latin model covers both | Apache-2.0 | wheel 26.1 MB **including all 3 ONNX models** (31.7 MB: det 9.93 + rec 21.23 + cls 0.59 MB) | **2.4 – 41 s/frame MEASURED** |
| **Windows.Media.Ocr** | installed, **pt-BR only** | **EN not installed → NULL engine** | part of Windows, not redistributable | 0 (present) | **21 – 119 ms MEASURED** |
| Tesseract 5 | **not on disk** (`tesseract` not on PATH, no `C:\Program Files\Tesseract-OCR`) | needs `por`+`eng` traineddata | Apache-2.0 | UNKNOWN | UNKNOWN (untestable here: no downloads allowed) |
| PaddleOCR (upstream) | not installed; RapidOCR *is* its ONNX export | same models | Apache-2.0 | ~ same as RapidOCR + Paddle | ≈ RapidOCR |
| EasyOCR | not installed (weights are a download) | 80+ langs | Apache-2.0 | ≈2 GB PyTorch, **~1 GB peak RSS CPU** (READ) | UNKNOWN here |
| VLM / vision model | not installed | multilingual in principle | model-dependent | large | UNKNOWN |

- **MEASURED (licences)** — `RapidOCR` is Apache-2.0 (fetched `raw.githubusercontent.com/RapidAI/RapidOCR/main/LICENSE`);
  Tesseract is Apache-2.0 (its `LICENSE`); EasyOCR is Apache-2.0 **READ**
  ([thunderbit benchmark](https://thunderbit.com/blog/easyocr-review)).
- **MEASURED (install weight)** — `pip download rapidocr==3.9.2 --no-deps` → 26.01 MB wheel;
  `onnxruntime-1.30.0-cp311-win_amd64.whl` = **13.6 MB**, `onnxruntime-gpu-1.30.0` = **153 MB**
  (PyPI JSON API). Per-run import cost is a different number from install weight.
- **MEASURED (Windows OCR language availability)** — `OcrEngine.AvailableRecognizerLanguages`
  returns **exactly one** language on this box: `pt-BR`. `TryCreateFromLanguage(new Language("en-US"))`
  → **NULL**. So on this machine Windows OCR **cannot read English at all**; on an en-US host it
  would not read Portuguese. `MaxImageDimension = 10000`.
- **MEASURED (Windows OCR quality, pt-BR engine)** — it read a Portuguese caption
  `ELE TÁ DE AWP, NÃO SOBE A RAMP` correctly (same as RapidOCR) but mangled
  `HP 87/100 AMMO 24/90` → `HP 87/400`, `OBJETIVO` → `OBJEflVO`, and dropped `[Maria] gg wp`.
  On the low-contrast arm it returned `Joao] eleáa de aw` and `SSO NEG`.
- **READ (Windows OCR performance claim)** — Microsoft's Windows App SDK text-recognition API runs
  "exclusively on devices with a neural processing unit (NPU)" and is "faster and more accurate
  than the legacy `Windows.Media.Ocr.OcrEngine`" ([Microsoft Learn](https://learn.microsoft.com/en-us/windows/ai/apis/text-recognition)).
  That is a **different API** from the one I measured, needs an NPU, and is **UNKNOWN here**.

### Recommendation — **RapidOCR, and only as a background pass**

1. **Ship RapidOCR (PP-OCRv6-small ONNX) as the OCR engine.** MEASURED reasons: the models are
   **already in the runtime on disk**, the licence permits commercial desktop use, one model reads
   both PT-BR and EN (accented characters included: `ELE TÁ DE AWP, NÃO SOBE A RAMP` came back
   byte-exact on the clean, low-contrast and fade arms), and it exposes **per-box boxes, per-box
   confidence and word boxes** which the schema in §3 needs.
2. **Do not ship Windows OCR as the only engine** — MEASURED: the engine is language-per-user, and
   an EN machine cannot read PT-BR text or vice versa. A product that silently returns nothing
   because a language pack is missing is the "bricked app that looks like a working one" failure
   this house already has a rule about.
3. **Correct the premise in the question**: on this box, **neither engine can be run per frame in
   real time.** RapidOCR measured **2.4–41 s for one 1920×1080 frame** (median ≈ 8–11 s), while the
   capture loop wants ~1 FPS. Windows OCR is 21–119 ms and is *fast enough*, but its accuracy is
   roughly half of RapidOCR's (see the table in §4) and it is PT-BR-only here.
   ⇒ **OCR is a batch channel over already-recorded frames, never a live one.** This is the same
   shape as the decided ASR law (streaming model live, batch model afterwards) and it belongs to
   the **AI Scheduler**, which already knows to do heavy work when the user is not playing.
4. **GPU is the lever that would change this and it is UNMEASURED here.** The `onnxruntime-gpu`
   wheel is present and the RTX 5080 answers, but RapidOCR's CUDA path could not be exercised in
   this lane (the `bad allocation` failures hit while the box was starved, and the documented
   override is a YAML file, not a kwarg). **UNKNOWN: RapidOCR-with-CUDA latency.** That one
   measurement decides whether OCR can ever be "1 FPS live" or stays "background".

## 2. When to run it

- **MEASURED — the cheapest trigger is essentially free.** On a **160×90 grayscale** thumbnail
  (and on a **40×23** one) an abs-diff mean costs **1.0 × 10⁻⁵ – 2.7 × 10⁻⁵ s per frame**, and a
  dHash bit-count on the 40×23 thumbnail costs **1.4 × 10⁻⁵ s**. At that price the trigger can run
  at 30 fps without appearing in any CPU budget (full rate: 0.0008 s/s of video).
- **MEASURED — the trigger fires on the frame the text appears.** Synthetic 30 fps/3 s clip: a
  moving HUD element plus a toast that is on screen for 0.8 s. For all three methods the **first
  frame whose delta exceeded every quiet frame's** was **exactly the onset frame**, with quiet
  `max` 7.54 (mean 0.21, σ 0.92) vs onset 30.64 for the 160×90 abs-diff. Nothing false-fired in
  87 quiet frames after the moving element was excluded — **the moving HUD element itself is the
  false positive**, which is why the trigger must run on a **mask that excludes the animated HUD
  regions**, not on the whole frame.
- **MEASURED — 1 FPS alone is not enough.** 1 frame per second on an 0.8 s toast has a **~20 %**
  chance of never sampling it (0.8 s window vs a 1.0 s grid). Two text events inside one 1 s bucket
  also collapse into one OCR call.
- **Therefore (derived, not measured): two-rate trigger.** (a) change detection on a
  160×90 masked thumbnail at **30 fps** — MEASURED cost 2.7 × 10⁻⁵ s/frame; (b) on a change, enqueue
  the frame and let the OCR worker consume the queue at whatever rate it manages. The queue's job is
  to make sure a 0.8 s toast is **already in the buffer** before OCR gets to it. Whether a real game
  changes the masked region every frame is **UNKNOWN** (my scene animates continuously); if it does,
  the change trigger degenerates into "every frame" and the correct knob becomes a **fixed lower
  rate** (e.g. 0.2–0.5 Hz) plus the trigger for bursts.

## 3. What to store, and how it enters the index

Per OCR observation, one row (names only — no schema file here, this is the lane's request list):

`t_ms` (frame timestamp), `t_end_ms` (last frame this text was still identical — needed for
"when was this on screen", not just "when first seen"), `text_raw`, `text_norm` (case/accent-folded,
for lexical match), `box` (x,y,w,h) **per line** and `word_boxes` when `return_word_box` is on,
`conf` (per box; RapidOCR returns floats, e.g. 0.978/0.973 on the clean arm), `engine` +
`model` + `model_sha256`, `frame_ref` (which buffer frame), `trigger` (change-delta value that
enqueued it), `lang_guess`, `region_id` (if the frame was OCR'd by band).

- **Store the region, not just the text.** **MEASURED**: the recognition stage accepts a cropped
  region directly (`engine.text_rec`), so a re-read of a known dialogue box and a full-frame search
  can share one model. The region is also what lets the UI draw the box on the thumbnail, and what
  lets a later pass re-OCR at higher scale.
- **How it enters the index — say it plainly:**
  - **Lexical (SQLite FTS) is the required baseline.** It covers what the owner actually searches
    for in game text: `ELIMINATED`, `GG`, item names, `0x80070005`, player names. **MEASURED**:
    exact tokens came back intact (`ERRO 0x80070005: ACESSO NEGADO` byte-exact on 3 of 6 arms),
    so lexical hits here are real hits, not fuzzy ones.
  - **Vectors: reuse the transcript's text embedding, do NOT build a second space.** The two
    channels are compared side by side in one result list, so a shared text-embedding space is what
    makes a text query rank OCR and speech hits on the same scale. **UNKNOWN which text-embedding
    model the transcript channel will use** — the brief's final turn only names an
    EmbeddingGemma-class *multimodal* image embedding for the ~1 FPS visual channel. **This lane
    does not choose it; it depends on the transcript lane's choice.** The one hard constraint it
    imposes on that choice: **the text embedder must be multilingual (PT-BR + EN at minimum)**,
    otherwise OCR text and transcript text land in different spaces and the fusion is decorative.
    Until that model exists, **lexical-only for OCR text** — and that is ship-able by itself.
  - **A cheap token side-channel is already in the tree**: Redux's `vocab.txt` (8 193 tokens,
  `H:\sotto\worker\models\...`) is a tokenizer on disk with no download. **READ** (its specs are in
  Sotto's model docs). Usable for token-exact lexical matching; **not** a semantic space.
- **Confidence is not a truth score — do not gate on it.** **MEASURED**: RapidOCR reported
  **0.989** for `[Maria]gg.wp` (ground truth `[Maria] gg wp`) and **0.995** for `MO2490` — the
  entire 4 px-blur arm collapsed to one box with confidence 0.995. Windows OCR likewise lost
  `[Maria] gg wp` entirely. Store the score for ranking, never as a "correct" flag. The published
  write-up reaches the same conclusion on Japanese text ([dev.to, PP-OCRv6 + RapidOCR](https://dev.to/kiarina/testing-japanese-and-english-ocr-with-pp-ocrv6-small-and-rapidocr-39pd)).

## 4. Failure modes and what accuracy to expect

**MEASURED on 7 ground-truth strings per arm, 1920×1080 (recall = recovered / 7; CER = character
error rate of the whole output block vs the whole ground truth; script `_main/ocr-score-02.py`):**

| arm | RapidOCR recall | RapidOCR CER | Windows OCR (pt-BR) recall | Windows OCR CER |
|---|---|---|---|---|
| clean HUD + subtitle | **1.00** | 0.367† | 0.57 | 0.483 |
| low-contrast chat | 0.71 | 0.358 | 0.29 | 0.642 |
| text at 0.7 × size | 0.43 | 0.367 | 0.29 | 0.725 |
| **motion blur 2 px** | 0.71 | 0.458 | 0.29 | 0.542 |
| **motion blur 4 px** | **0.14** | 0.950 | **0.00** | 0.892 |
| **subtitle faded to 50 % brightness** | **0.86** | 0.375 | 0.57 | 0.567 |

† The CER on the clean arm is not a misread: all 7 strings were recovered, but RapidOCR joins
tokens (`ERRO0x80070005:ACESSONEGADO`) and emits a stray `■` box, so the concatenated string
differs. **For search this is harmless; for display it is not.**

- **Motion blur is the killer, not darkness.** **MEASURED**: at 4 px blur RapidOCR returned
  **one** box for the whole 1080p frame; Windows OCR returned one. 2 px blur already cost
  `HP 87/100` → `HP 10 1 90`.
- **A 50 % fade costs much less than blur** — MEASURED accuracy dropped only one string (6/7). So
  the "subtitles that fade" worry is **second-order** compared with motion.
- **Low contrast loses tokens, not boxes.** MEASURED: `[Joao] ele ta de awp` → `éle ta de awp`,
  `[voce] recuando B` → `[voce] recando B•`.
- **Small text collapses at ~0.7×.** MEASURED: 5 boxes for 7 strings, `ELE TÁ DE AWP` → `AP`. A
  HUD at 1080p→720p downscale carries the same risk: the same models on a **960×540** downscale
  returned 7 boxes but I did not score that arm, so **UNKNOWN**.
- **Non-Latin script is the categorical failure.** MEASURED: the CJK subtitle `敵が丘の上にいる`
  was **not detected at all** by RapidOCR (the arm produced no output) nor by Windows OCR
  (`31100' AMMoi4190`, noise). The Cyrillic subtitle was **recognised as Cyrillic but garbage**
  (`ОН НА ХОЛМЕ, НЕ ПОДНИМАЙСЯ` → `OH Ha xonMe, He nOAHb4MahCB` with the pt-BR engine). The
  PP-OCRv6-small model shipped in this wheel is the Latin/Chinese-tier recognizer; other scripts
  need a different recognition model, which is a **download** and therefore UNKNOWN here.
- **No real-game accuracy number exists in this doc.** Synthetic frames were used because the
  video drive was too slow to sample. Numbers from other people's benchmarks are indicative only:
  **READ** — 12/14 strings exact on a 1448×1086 mixed JA/EN image, 839–920 ms on an M4 Max CPU
  ([dev.to](https://dev.to/kiarina/testing-japanese-and-english-ocr-with-pp-ocrv6-small-and-rapidocr-39pd));
  **READ** — EasyOCR ~1 GB peak RSS on CPU with a font-size cliff
  ([thunderbit](https://thunderbit.com/blog/easyocr-review)); **READ** — an academic comparison
  table of EasyOCR/DocTR/Tesseract/PaddleOCR per image is available but its columns are not
  screen text (Zenodo record, [PDF](https://www.zenodo.org/records/17336160/files/Automating%20Circularity%20-%20OCR-Enabled%20Robotics.pdf?download=1)).

## 5. What could not be verified (by name)

1. **RapidOCR with CUDA** — provider present, RTX 5080 present, measurement blocked by box-wide
   memory exhaustion (`bad allocation`). This is the single most decision-relevant unknown.
2. **Tesseract accuracy and cost** — no binary on disk and downloads are out of scope for this lane.
3. **EasyOCR accuracy and cost here** — weights are a download.
4. **Accuracy on real game footage** — the owner's clips are on a drive this lane could not read at
   speed; the one attempt wrote zero frames in ten minutes.
5. **The text-embedding model** the OCR channel should share with the transcript channel.
6. **The masked-region change rate in a real game** — whether the cheap trigger really skips frames.
7. **Windows OCR on an en-US host** — this box has only pt-BR, and language packs are per-user.
