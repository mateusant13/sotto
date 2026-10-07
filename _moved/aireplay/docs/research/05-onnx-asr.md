# 05 — Does the int8 ONNX export replace the 3.90 GB ternary runner?

**Question (ONE):** the ternary/TDT Redux runner peaks at **3.90 GB RSS** (`receipt-redux-ternary.md` §2.3). Does the
istupakov int8 ONNX export — already on disk, 670.6 MB — land at **~700–900 MB**, measured through `onnx-asr`?
**Scope: nothing else.** `MEASURED` = a command on this box produced it, file named · `READ` = source read, file+line
given · `UNKNOWN` = nobody has shown it. Host: Windows 11 · i5-13600K (6 P + 8 E) · RTX 5080 · CPU only.
**Budget this lane was ordered to run under** (owner reported stutter): audio slice **≤120 s, in series**,
`OMP_NUM_THREADS=2`, `OPENBLAS_NUM_THREADS=2`, ORT `intra_op=2`, `inter_op=1`. **Every number below is at 2 threads
unless the row says otherwise** — that is the number the product gets.

## 0. Answer in one line

**The RAM hope HOLDS and the speed hope does NOT.** With ~10 s silence-aligned segments the int8 export peaks at
**798–923 MB** (flat over 20 min of audio: no leak) — **4.2–4.9× less** than the 3.90 GB ternary runner — but it
transcribes at **6.06× real time on 2 threads**: comparable to slightly *slower* than the ternary runner's own 5–14×
on this box, and nowhere near the **31.4× int8** this repo quotes (`READ`, istupakov benchmark, `04-asr.md:42`).

## 1. Verified before anything ran — 5/5 sha256 MATCH, nothing downloaded

**MEASURED** (`Get-FileHash -Algorithm SHA256` here vs `https://huggingface.co/api/models/istupakov/parakeet-tdt-0.6b-v3-onnx?blobs=true`,
revision `8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce` — the revision the local `.cache/huggingface/download/*.metadata`
names): `encoder-model.int8.onnx` **652 183 999 B** `6139D2FA…5AFF09` · `decoder_joint-model.int8.onnx`
**18 202 004 B** `EEA7483E…667A70` · `nemo128.onnx` **139 764 B** `A9FDE148…019E9F` — all three MATCH the API's
`lfs.sha256`; `vocab.txt` **93 939 B** and `config.json` **97 B** MATCH by git blobId (= the local `.cache` etags).
**Total 670 589 803 B = 670.6 MB (639.5 MiB).** The fp32 sidecar `encoder-model.onnx.data` (2 435 420 160 B) is **not** on this disk. **No byte was downloaded:** `onnx-asr` 0.12.0 was *already installed* (onnxruntime 1.30.0, numpy 1.26.4,
psutil 5.9.8) and `load_model(path=<local dir>)` sets `offline=True` (`resolver.py:69-72`) — no HF call at load.
**The lane that died in the reboot DID run `onnx-asr` before dying** (`_main/onnx_asr_probe.py` + `onnx-asr-*.json`,
06:49–07:03 today), so `AGENTS.md:117` "Nobody here has run onnx-asr yet" is stale. It agrees with me where we overlap:
RSS after load **742–751 MB**, the *same* parity text (`práxima segunda feira`), 30 s passes peaking **1174 MB**; its
RTFx is **0.4–1.8×** at ORT default threads on a loaded machine (its 25 ms census degraded to 170–205 ms effective).
Its graph census explains the slow encoder: **IR 8 / opset `ai.onnx` 17 / 5654 nodes, `DynamicQuantizeLinear` ×223,
`MatMulInteger` ×217, `ConvInteger` ×77** — *dynamically* quantized, activations quantized at runtime, not QDQ.

## 2. How it was run

`onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", path="H:\aireplay\models\parakeet-tdt-0.6b-v3-onnx",
quantization="int8", providers=["CPUExecutionProvider"], sess_options=<intra_op=2, inter_op=1>)` — the `int8` suffix
is a **glob** (`encoder-model?int8.onnx`, `nemo.py:84-89`). Both sessions report `['CPUExecutionProvider']`.
**GPU: NOT used** — `CUDAExecutionProvider` *is* available in this ORT build, but the owner's GPU had 3.8/16.3 GB in
use by his software and the product must work CPU-only (law 5). **MEASURED** off the loaded object: `vocab_size 8193`,
`blank_idx 8192`, `max_tokens_per_step 10`, `subsampling 8`, `features 128` — the Redux fichas again; the preprocessor
is `NemoPreprocessorNumpy` (NumPy mel on the CPU provider, `loader.py:203-204`), so the model dir's `nemo128.onnx` is
**verified but not loaded**. **No audio device opened** (wav files only). **No visible window:** my census
(`_main/window-census.ps1`, `MainWindowHandle`, its own cadence) — budgeted phase **145 samples at 1000 ms,
`visible_hits=0`, `distinct_pids=0`**; the earlier 500 ms census (08:14→08:27) named only the owner's own Sotto panel
(pid 28428) — **never a pid of mine**.

## 3. RSS — the number that decides

| what | peak RSS (1 Hz poll) | OS `peak_wset` |
|---|---|---|
| before imports / after imports / **after load** | 35.6 / 56.2 / **735–748 MB** | — |
| `src-en-8s` (8.5 s, one call) · `src-pt-15s` (15 s) | 798.2 · 843.6 | 798.6 · 844.0 |
| **120 s slice, 10 s chunks** | **873.7** | **881.4** |
| **20 min of audio (120 s slice × 10, 10 s chunks)** | **874.6** | **882.0** |
| 120 s slice, silence-aligned (median 7.0 s, max 13.8 s) | 909.1 | 923.1 |
| 120 s slice, 30 s chunks | 1144.1 | 1172.4 |
| 120 s slice, **one** 120 s encoder pass | 1773.1 | 1773.1 |

**Curve over 20 min of continuous audio** (same 120 s slice repeated 10× in series — the budget's substitute for a
long file; `runs/b-curve-120s-x10.json`, **216 points at 1 Hz**, each stamped with wall seconds AND audio seconds).
RSS at each minute of audio processed: **56.2** (before load) · minutes 1–12: **873.5, 873.8, 871.7, 872.3, 873.9,
873.9, 873.9, 873.9, 873.9, 873.9, 873.8, 873.8** · minutes 13–20: **854.4, 836.5, 836.5, 836.6, 836.1, 834.1,
834.1, 831.1** MB. Whole-curve min/max/mean 56.2 / **874.7** / 855.9 MB; last 10 min range 831.0–874.0 MB.
**Flat, then ~43 MB handed back at ~13 min — no leak, no growth in 1200 s** (the pre-budget 20-min curve,
`runs/curve-1200s-chunk10.json`, agrees at ORT default threads: flat 885.5, peak 892.7 / `peak_wset` 895.5).
**The peak is set by SEGMENT LENGTH, not by time:** 10 s → 0.88 GB, 30 s → 1.17 GB, one 120 s pass → 1.77 GB.

## 4. RTFx — the hope this measurement kills

| arm (2 threads, CPU) | audio | infer s | **RTFx** | cpu median |
|---|---|---|---|---|
| clips, one call each (`src-en-8s` 8.5 s · `src-pt-15s` 15 s) | 8.5 · 15 s | 0.64 · 1.42 | **13.3 · 10.6** (first-call) | 189 · 200 % |
| 120 s slice, 10 s / 30 s chunks | 120 s | 19.81 / 21.09 | **6.06** / 5.69 | 203 / 200 % |
| 120 s slice, one 120 s pass | 120 s | 30.59 | 3.92 | 200 % |
| 120 s slice, silence-aligned | 86.8 s processed | 13.82 | 6.28 on processed audio | n/m |
| **20 min of audio (curve)** | 1200 s | 216.22 | **5.55** | 218 % |

**Thread A/B, same 120 s slice, same chunks — the finding that matters for the product:**

| `intra_op` | infer s | RTFx | cpu median | peak `wset` |
|---|---|---|---|---|
| 1 | 36.31 | 3.30 | 97 % | 880.4 |
| **2 (the product's budget)** | **19.81** | **6.06** | **203 %** | 881.4 |
| 6 | 14.10 | 8.51 | 610 % | 886.1 |
| **ORT default (`intra_op=0`)** | **38.58** | **3.11** | **690 %** | 895.1 |

**ORT's default thread choice on this hybrid CPU burns 6.9 cores to deliver the throughput of ONE.** Pinning 2
threads is *both* the polite setting and **1.95× faster** than the default, so any RTFx measured at default threads on
this box (including this lane's own first series: 2.73–3.96×) is an artefact of that contention.
**Where the seconds go** (MEASURED, 10 s chunk, 2 threads, `probe-onnx-asr-phases.py`): preprocess **0.006–0.011 s**,
**encode 0.63–1.78 s**, decode **0.009–0.023 s** (126 encoder frames, 35–44 `decoder_joint` calls) — the encoder is
**≥95 %** of the time, so a better TDT loop buys almost nothing. **The first encode after load is 2.5× faster than
every later one** (0.625 s vs 1.25–1.8 s, same 126 frames), so the 13.3×/10.6× clip numbers are *first-call* numbers,
not the product's speed. **UNKNOWN: the mechanism.**

## 5. Parity — the same audio the sibling project already transcribed (read-only from `H:\sotto`)

| comparison | verdict |
|---|---|
| `src-en-8s.wav` vs `_main/redux-en.txt` | **EXACT**, 130/130 chars, ratio **1.000000**, 0 diff blocks |
| `src-pt-15s.wav` vs `_main/redux-ptbr.txt` | 159/159 chars, ratio **0.993711**, **one char**: `segunda-feira` → `segunda feira` |
| `plain-3600s.wav` **[900,1020)** silence-aligned vs the sibling's captions | **8/11 segments IDENTICAL**; 2 differ only `closed`→`clos`; 1 is my own cut at 1020 s (`Monday`→`year`) |
| `plain-3600s.wav` [900,1080) silence-aligned (pre-budget; text is thread-independent) | **13/16 IDENTICAL**; the rest differ **only** in the final `ed` of `closed` (3/3) |
| `plain-3600s.wav` [900,1020) on a **FIXED 10 s grid** | ratio **0.229** (648 vs 741 chars) — seams give `The radio announce. that…`, `anunció que la bridge`, `TECA. Video announced` |

**The fixed grid is the trap, not the model:** it cuts mid-word; cut on silence and the int8 export's text *is* the
Redux text. Control: the split probe's `--mode fixed` reproduced the main probe's transcript **byte for byte**
(648 chars), and both clips' text is **identical** at ORT's default threads and at 2 threads. (`redux-ptbr.txt` is
**cp1252, not UTF-8** — 0xE1 at offset 135; a UTF-8 reader crashes on it.)

## 6. Verdict, and what stays UNKNOWN

- **Memory: adopt it** (~0.88 GB peak at 10 s segments, 4.4× under the ternary runner, inside the 700–900 MB band);
  **speed: not a win** — 6.06× at 2 threads against the ternary's 5–14× here (a wash to a loss, not 31.4×).
- **Do not ship fixed-grid chunking**, and **cap the threads**: 2 threads is polite *and* the fast setting.
- **UNKNOWN:** why the READ benchmark says 31.4× int8 while this box measures 6.06× (a 5× gap this lane cannot
  attribute; the thread pathology is part of it, not all of it) · the first-call 2.5× speedup's mechanism · behaviour
  past 120 s of continuous audio *under the budget* · the CUDA path (never run) · onnx-asr's own silero VAD (not on
  disk, so my splitter is energy-only) · word timestamps (never exercised) · game audio, music, overlap.
