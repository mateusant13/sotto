# receipt-05-onnx-asr — what was RUN, what was VERIFIED, what is UNKNOWN

**Question (ONE):** does the istupakov int8 ONNX export (`H:\aireplay\models\parakeet-tdt-0.6b-v3-onnx`, 670.6 MB)
replace the ternary Redux runner's **3.90 GB** peak RSS, landing at ~700–900 MB — measured through `onnx-asr`?
Answer: **RAM yes (798–923 MB peak at ~10 s segments, flat over 20 min), speed no (6.06× real time at 2 threads,
against the ternary's own 5–14× on this box).** Doc: `docs/research/05-onnx-asr.md`.

## 1. Verification before use — 5/5 sha256 MATCH, nothing downloaded

`Get-FileHash -Algorithm SHA256` on this box vs the live HF API
(`/api/models/istupakov/parakeet-tdt-0.6b-v3-onnx?blobs=true`, revision `8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce`,
the revision the local `.cache/huggingface/download/*.metadata` names): `encoder-model.int8.onnx`
**652 183 999 B** `6139D2FA…5AFF09` MATCH · `decoder_joint-model.int8.onnx` **18 202 004 B** `EEA7483E…667A70` MATCH ·
`nemo128.onnx` **139 764 B** `A9FDE148…019E9F` MATCH · `vocab.txt` **93 939 B** and `config.json` **97 B** MATCH by git
blobId (= the local `.cache` etags). **Total 670 589 803 B = 670.6 MB (639.5 MiB).** The fp32 sidecar
`encoder-model.onnx.data` (2 435 420 160 B) is **not** on this disk. **No download:** `onnx-asr` 0.12.0 was already
installed; `load_model(path=<local dir>)` sets `offline=True` (`resolver.py:69-72`) and never calls HF.

## 2. What was run

`onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", path=…, quantization="int8", providers=["CPUExecutionProvider"],
sess_options=<intra_op=2, inter_op=1>)`, `OMP_NUM_THREADS=2`, `OPENBLAS_NUM_THREADS=2`, `MKL_NUM_THREADS=2`.
**CPU only — the GPU was NOT used** (owner's GPU 3.8/16.3 GB busy; `CUDAExecutionProvider` is available here but was
never exercised). Both sessions report `['CPUExecutionProvider']`. Preprocessor is `NemoPreprocessorNumpy`, so the
model dir's `nemo128.onnx` is verified but **not loaded** on this path. Fichas read off the loaded object:
`vocab_size 8193`, `blank_idx 8192`, `max_tokens_per_step 10`, `subsampling 8`, `features 128`.
Instruments: `_main/probe-onnx-asr.py`, `probe-onnx-asr-split.py`, `probe-onnx-asr-phases.py`, `parity-onnx-asr.py`,
`parity-segments.py`, `window-census.ps1`; JSONs/transcripts in `_main/runs/`, logs in `_main/logs/`.
**No audio device was opened** (wav files only). **No visible window:** my census (`Get-Process … MainWindowHandle`,
its own cadence) — budgeted phase **145 samples at 1000 ms, `visible_hits=0`, `distinct_pids=0`**
(`_main/logs/window-census-budget.log`); the earlier 500 ms census (08:14→08:27, killed before its end line) named
only the owner's own Sotto panel (pid 28428) and **no pid of mine**. **Nothing in `H:\sotto` was written** — read-only.

## 3. The numbers (all 2 threads; full tables in the doc)

- **RSS:** after imports 56.2 MB → **after load 735–748 MB** → peak **798.2** (`src-en-8s`) / **843.6** (`src-pt-15s`) /
  **873.7** (120 s slice, 10 s chunks) / **874.6** (20 min of audio) / **909.1** (silence-aligned, max 13.8 s seg) MB;
  OS `peak_wset` 881.4 / 882.0 / 923.1. Bigger segments: 30 s → 1144.1; one 120 s pass → **1773.1**.
- **Curve over 20 min of audio** (120 s slice repeated 10× in series, 1 Hz, 220 points): flat 868.9→869.1 MB, a step
  down to ~831.8 at ~14 min, ending **826.3 MB**. **No leak; it gives ~45 MB back.** (Pre-budget 20-min curve at ORT
  default threads agrees: flat 885.5, peak 892.7 / `peak_wset` 895.5.)
- **RTFx:** 6.06 (120 s, 10 s chunks) · 5.69 (30 s chunks) · 3.92 (one 120 s pass) · **5.55 steady over 1200 s of
  audio** · 6.28 on processed audio for the silence-aligned arm · 13.3 / 10.6 on the 8.5 s / 15 s clips, which are
  **first-call** numbers.
- **Thread A/B (same 120 s slice):** 1 → 3.30× (97 % CPU) · **2 → 6.06× (203 %)** · 6 → 8.51× (610 %) ·
  **ORT default → 3.11× while burning 690 % CPU.** Pinning 2 threads is polite *and* 1.95× faster than the default.
- **Phases (10 s chunk, 2 threads):** preprocess 0.006–0.011 s · **encode 0.63–1.78 s** · decode 0.009–0.023 s
  (126 frames, 35–44 joint calls) → the encoder is ≥95 % of the time; the TDT loop is not the bottleneck. The **first**
  encode after load is 0.625 s and every later one 1.25–1.8 s for the same 126 frames.

## 4. Parity against the sibling project's own transcriptions (read-only)

`src-en-8s` vs `_main/redux-en.txt` → **EXACT** (130/130 chars, ratio 1.000000). `src-pt-15s` vs `_main/redux-ptbr.txt`
→ ratio 0.993711, **one char**: `segunda-feira` → `segunda feira`. `plain-3600s.wav` slice **900–1020 s**,
silence-aligned vs the sibling's captions → **8/11 segments IDENTICAL**, 2 differ only `closed`→`clos`, 1 is my own
cut at 1020 s. Pre-budget 900–1080 s window: **13/16 IDENTICAL**, the rest differing only in the final `ed` of
`closed`. The **fixed-10 s-grid** arm over the same 120 s scores **0.229** (648 vs 741 chars) with seam garbage
(`The radio announce. that…`, `anunció que la bridge`, `TECA. Video announced`) — that is the chunking policy, not the
model. Control: the split probe's `--mode fixed` reproduced the main probe's transcript **byte for byte** (648 chars);
clip text is identical at default threads and at 2 threads. `redux-ptbr.txt` is **cp1252, not UTF-8** (0xE1 at 135).

## 5. UNKNOWN, by name

(1) Why the READ benchmark (`04-asr.md` line 42) says **31.4× int8** while this box measures **6.06×** — a 5× gap this
lane cannot attribute; the ORT-default-thread pathology is part of it, not all of it. (2) The mechanism of the
first-call 2.5× speedup. (3) Behaviour past 120 s of continuous audio **under the budget** — the only 20-minute
evidence was taken pre-budget. (4) The CUDA path (never run). (5) `onnx-asr`'s own silero VAD (its model is not on
disk; my splitter is energy-only, so a model-based segmenter may score differently). (6) Word timestamps
(`with_timestamps()` never exercised). (7) Quality on game audio, music and overlap — untouched here.
**Budget note:** this lane's first series (a 1200 s slice curve, a 180 s split arm, a chunk sweep) ran at ORT's
default thread count (~640 % CPU) before the owner's stutter was reported; those runs are kept only as *structure*
(chunk-size vs RSS, seam behaviour) and are labelled as such in the doc. All headline numbers were re-measured at
2 threads on ≤120 s slices.

## 6. Reconciliation with the lane that died — its work IS on disk and it AGREES with mine

The brief said the previous lane died in a reboot after downloading the weights, and `AGENTS.md:117` still says
"Nobody here has run `onnx-asr` yet". **Both are stale.** `_main/onnx_asr_probe.py` (15 249 B, mtime 06:53:04) and a
full result set from **06:49–07:03 today** are in `_main/`: `onnx-asr-armA-default.json`, `onnx-asr-armB-cpuep.json`,
`onnx-asr-armC-cpu8.json`, `onnx-asr-parity.json`, `onnx-asr-curve.json` (+ `-timeline.jsonl`), `onnx-asr-profile.json`
(ORT node profile), `onnx-asr-graph-census.json`, `onnx-asr-diag.json`, seven `onnx-asr-census-*.txt` (its own 25 ms
window censuses) and external working-set CSVs. What it establishes, and where it meets my numbers:

| its measurement | its number | mine |
|---|---|---|
| RSS after load (3 arms) | **742.3 / 749.0 / 749.1 MB** | **735–748 MB** |
| parity text, `pt-br-sample.wav` | `… na práxima segunda feira. Os moradores …` | same text, same dropped hyphen |
| parity text, `en-us-sample.wav` | `The radio announced … closed next Monday. Residents …` | byte-identical to `redux-en.txt` |
| 30 s passes, 12-pass curve, `intra_op=0` | peak WS **1174 MB**, RTFx mean **0.808** (0.415–1.815) | 30 s chunks: peak **1172.4 MB** |
| ORT graph census | encoder **IR 8 / opset `ai.onnx` 17 / 5654 nodes**, `DynamicQuantizeLinear` ×223, `MatMulInteger` ×217, `ConvInteger` ×77 | same file, same conclusion: **dynamically** quantized, activations quantized at runtime |
| its own window censuses (25 ms, 6 arms) | `visible_samples=0` in every arm (up to 2282 samples) | my census: 145 samples at 1 s, 0 hits |

Its RTFx (0.4–1.8×) is *worse* than my default-thread runs (3.11×) and its own census cadence degraded from 25 ms to
170–205 ms effective — a loaded machine, measured. **What it did NOT have, and this lane adds:** the thread A/B
(1 / 2 / 6 / default), the phase attribution (encoder ≥95 %), the peak-RSS-vs-segment-length law, and the
fixed-grid-vs-silence-aligned chunking finding. Nothing of its was overwritten; its instrument and results stay as
they are.

