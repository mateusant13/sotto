# Per-speaker separation, OFFLINE, on this box — measured

**Question (owner's goal, restated):** separate the call audio so each speaker is
transcribed on his own stream; speaker names and "who spoke when" are NOT the
acceptance — separation for transcription is.
**Lane:** MEASURE (writes only `_main/bench/` + this receipt). **Date:** 2026-11-17,
additions 2026-11-19 (§0, §6.1, §6.3, §6.6a, §6.8, §7.1, §8.1, §8.2).
**Window:** 60.000 s of the frozen corpus, `_main/bench/discord-call-20261116/mix-16k.wav`
at t = 360.0 s → `_main/bench/windows/w60-t0360.wav`
(1 920 044 B, 960 000 samples @ 16 kHz, `sha256_int16 35e938c3f7bc22bb…`, peak 0.973, RMS −18.37 dBFS).

> **A frase final (PT-BR, para o dono):** a separação existe nesta caixa e funciona
> tecnicamente, mas custa **≈12× tempo real a 2 threads (RTF 11,9; até 22,6 com a caixa
> ocupada) e 1,3–2,4 GB de RAM** por passada — e o corpus é 3 h 7 min de áudio. Medido,
> não estimado. Os números que decidem estão na §6; o veredicto, na §8.

---

## 0. Ceiling, declared BEFORE the numbers

Every run that loads a model is launched as

```
python -m watcher run --cpu 40 --io very-low --cwd H:/sotto -- \
    python _main/bench/separate.py --engine <e> --threads 2 ...
```

The 2026-11-19 re-run of §6.6a uses the tighter, `--single` form
(`--cpu 10 --single --io very-low`), i.e. a hard cap of **2 of the box's 20 logical
cores**; both forms are the watcher Job Object, neither is a `--threads` flag.

| ceiling | value |
|---|---|
| model processes | **1 at a time** in this lane (`--single` is passed on every launch) |
| threads | **2 total** (`torch.set_num_threads(2)` inside the loader; `OMP/MKL/OPENBLAS=2`) — the two pools SUM to the budget, they do not each get it (§6.6a) |
| CPU | **40 %** of the box hard cap on the 2026-11-17 runs, **10 %** (= 2 cores) on the 2026-11-19 one; 2 threads is ~10 % |
| IO priority | **very-low** (inherited by the tree) |
| RSS target | declared ≤ 3000 MB, enforced at **3 072 MiB** inside the process; measured peaks in §6 |
| audio | **never rendered, no output device touched** — files and numpy only |

**`python -m watcher` DOES exist on this box**; what does not exist is importing it
from `H:\sotto`:

```
$ cd H:/sotto && python -m watcher --help
H:\Python311\python.exe: No module named watcher
$ cd I:/!watcher && python -m watcher --help
usage: watcher [-h] [--mode ...] {tui,serve,start,stop,...,run,...}
```

`_main/bench/cage.py` (written 2026-11-16 by an earlier pass) concluded from the first
command alone that "the watcher form was a cage nobody could enter". That conclusion is
**wrong**: the module lives in its own repo at `I:/!watcher` and is reachable with
`cwd=I:/!watcher` (or `--cwd H:/sotto` for the child). The real defect of `cage.py`
is worse than its docstring: **it discards the child's stdout and stderr** —

```
$ python _main/bench/cage.py --label t2 -- python -u -c "print('CHILD-STDOUT')"
CEILING: 1 job | threads 2 | ...
CEILING-CMD: python -u -c print('CHILD-STDOUT')
MEASURED: wall 0.46 s | peak tree CPU 0.0% of the box | peak tree RSS 0 MB | rc 0
```

— the child's line is missing, and `peak tree RSS 0 MB` is a second defect (measured
after the child exited). Two 3–5 minute caged runs died inside `separate.py` and **the
traceback was swallowed by that**, which is how a real bug (§3) survived a whole
previous pass. `cage.py` is not used for anything below except as the negative
control that established this. All runs use `watcher run`, which does forward the
child's output:

```
$ cd I:/!watcher && python -m watcher run --cpu 40 --io very-low --cwd H:/sotto -- python -u -c "print('CHILD-STDOUT-VISIBLE')"
launched pid=3368: python -u -c print('CHILD-STDOUT-VISIBLE')
job CPU hard cap 40%  (children inherit)
io priority VeryLow (readback=0)
CHILD-STDOUT-VISIBLE
child exit code 0 — total 1.8s (startup 1.7s, wait 0.1s, ...)
```

---

## 1. What is actually on disk — candidates, by name

Census queries (exact, re-runnable):

```
find . -iname "*demucs*" -o -iname "*sepformer*" -o -iname "*spleeter*" \
     -o -iname "*conv-tasnet*" -o -iname "*asteroid*"      # repo-wide, node_modules pruned
python -c "import importlib.util as u; [print(m, bool(u.find_spec(m))) for m in
          ['demucs','asteroid','speechbrain','pyannote','pyannote_audio','clearvoice','modelscope']]"
ls -d /i/*model* /i/*Model* /i/models                          # I: model stores
ls _main/diar-models worker/models
```

| candidate | present? | bytes / evidence | what it IS |
|---|---|---|---|
| `mossformer2` (MossFormer2_SS_16K) | **PRESENT** | `_main/diar-models/mossformer2/last_best_checkpoint.pt` **670 353 271 B** + vendored architecture in `_main/bench/_vendor/mossformer2/` (8 files) | **real 2-talker speech separation**, 16 kHz, 55 735 410 params |
| `UVR_MDXNET_9482.onnx` | **PRESENT** | `_main/diar-models/UVR_MDXNET_9482.onnx` **29 704 738 B** | **music** vocal/instrumental split (UVR = Ultimate Vocal Remover) |
| sherpa-onnx diarization | **PRESENT** | seg `model.onnx` 5 992 913 B + emb `3dspeaker_eres2net_base_16k.onnx` 39 593 761 B (+ `nemo_en_titanet_small.onnx` 40 257 283 B) | **labels only** — no audio out |
| `demucs` | **ABSENT** | 0 hits in the repo; not on `I:`; `find_spec('demucs')` False | — |
| `sepformer` | **ABSENT** | 0 hits in the repo; not on `I:`; no module | — |
| `spleeter` | **ABSENT** | 0 hits; no module | — |
| `asteroid` / `speechbrain` | **ABSENT** | `find_spec` False | — |
| `pyannote.audio` | **ABSENT** | `find_spec('pyannote')` False — only the *sherpa-onnx export* of pyannote segmentation-3.0 exists | — |
| `clearvoice` / `modelscope` (MossFormer2's own package) | **ABSENT** | `find_spec` False | this is why the architecture is vendored (§3) |
| `torchaudio.pipelines.SourceSeparationBundle` | API present, **weights absent** | `torchaudio` 2.11.1 has the class; every bundle (`hdemucs_mph`, `conv_tasnet_base`) is a *download* | not measured: would need the network |

**Why vendoring was necessary** (`_main/bench/_vendor/mossformer2/`, 8 files, nothing
outside `_main/bench/`): the checkpoint is ClearerVoice-Studio's `MossFormer2_SS_16K`
weight file, and neither `clearvoice` nor `modelscope` is installed. The architecture
source (`mossformer2.py`, `mossformer2_block.py`, `conv_module.py`, `fsmn.py`,
`layer_norm.py`) plus `rotary_embedding_torch` are vendored so the `.pt` can be built
and loaded without installing a package into the owner's interpreter. Keys in the
checkpoint start at `enc.`/`mask_net.` (the inner `MossFormer`), not at `model.enc.`
(the `MossFormer2_SS_16K` wrapper) — measured: 1099 missing / 1099 unexpected when the
wrapper is instantiated. The loader therefore builds the inner module directly.

---

## 2. What the SHIPPING speaker code does (read, not assumed)

| file | what it produces | is it separation? |
|---|---|---|
| `worker/speaker_id.py` (357 ln) | **pure functions over time labels**: `speaker_for_window`, `stable_labels`, `attribute_lines`, `segments_from_payload`, `attribute_from_payload`, `summarize`. Header states "No model is loaded here either". | **No.** Nothing here touches audio samples; it maps caption lines to labels. |
| `worker/speaker_sidecar.py` (1 431 ln) | a **WRITER process**: `RingBuffer` → `tick()` (`:418`) → `_load_sherpa_diarizer()` (`:531`, pyannote seg + 3dspeaker emb + FastClustering, `threshold=0.9`) → `to_absolute()` (`:126`) → atomic write of **`_main/diar-live.json`**. `worker/speaker_bridge.py` reads that JSON. | **No.** It emits **labels with times**, never audio. Its own docstring: "Nothing in the ASR path imports this". |
| `_main/diar-models/…` | segmentation + speaker-embedding weights | **No.** Speaker *identity*, not signal separation. |

So "what ships" is **Arm A: diarize → label**, and the owner's objective
("each speaker transcribed separately") is **not served by it at all** — the ASR still
receives one mixed stream. That is why Arm B (`separate.py`) exists.

---

## 3. Defects found while measuring (all inside `_main/bench/`)

1. **`run_mossformer2` could never have produced a stream.** The crossfade window was
   built `fade` samples long (4 000) and multiplied by a whole `chunk` (160 000):
   `ValueError: operands could not be broadcast together with shapes (160000,) (4000,)`.
   The window belongs to the chunk with `fade`-sample ramps at its ends. Fixed; the
   `(2, 60000, 1)`-shaped `MOSSFORMER_CACHE` was empty beforehand for exactly this
   reason — no `mossformer2` entry had ever been written.
2. **`run_uvr` was not reconstructing audio at all**: after the inverse FFT it replaced
   the frame matrix with two concatenated `np.zeros` arrays and then indexed it per
   frame. Rewritten on librosa's `stft`/`istft` (one owner), fed the graph's declared
   `[batch,4,2048,256]` stereo-complex input.
3. **`cage.py` swallows the child's output** and prints `peak tree RSS 0 MB` (§0).
4. **The frozen corpus moved under the measurement.** `manifest.json` records
   `mix-16k.wav` as 432 534 444 B / `sha256 2a6503a9…` / 13 516.7 s; the file on disk
   (mtime 2026-11-16 22:24:32, i.e. *after* the manifest at 22:18:56) is
   **358 400 044 B = 179 200 000 frames = 11 200.0 s**, and `speech-60s.csv` is
   371 B / 10 rows where the manifest recorded 7 490 B. The CSV's silence pattern
   (−180 dBFS in bins 0,3,4,7) does **not** match the file now on disk (signal 0–10 min,
   silence 11–33 min, signal 34–49, silence 50–59), so the CSV is stale and was not
   used to pick the window. The 60 s window is therefore pinned as **its own file with
   its own hash**, not as "corpus offset N".

---

## 4. The entry point — `_main/bench/separate.py`

One file: mix → per-speaker WAVs, content-cached, plus `--score`.

```
key = sha256( engine_id | params_json | int16 PCM of the span )
```

`MISS <key>` is printed before the compute, `CACHE HIT <key>` when the bytes are
reused, `COST engine=… audio_s=… wall_s=… rtf=… rss_peak_mb=… threads=…` after it. The
same numbers are written into `<cache>/meta.json`, and `--cost-log FILE` appends one
JSON line per row — which is what makes a caged run's own numbers survive at all (§0).

Cache proof, 60 s window, zero model loaded (`passthrough`):

```
$ python _main/bench/separate.py --engine passthrough --wav _main/bench/windows/w60-t0360.wav --start 0 --span-s 60 --threads 2
MISS df5fd0161530343558b031cbc84fed4f17586d87509494579dea372eb2381943  (passthrough, 60.00 s of audio)
COST engine=passthrough audio_s=60.00 wall_s=0.014 rtf=0.0002 rss_peak_mb=49.1 threads=2
$ python _main/bench/separate.py --engine passthrough --wav _main/bench/windows/w60-t0360.wav --start 0 --span-s 60 --threads 2
CACHE HIT df5fd0161530343558b031cbc84fed4f17586d87509494579dea372eb2381943  (passthrough, 60.00 s of audio, streams=1, cached at 2026-11-17T00:27:14)
COST engine=passthrough audio_s=60.00 wall_s=0.000 rtf=0.0000 rss_mb=48.9 cached_rtf=0.00023 (CACHE HIT, no compute)
```

### `--score`: what it reports, and what it refuses to report

There is **no reference transcript** for this call, so **no WER is reported** — inventing
one would be the whole failure this receipt exists to avoid. Four numbers are measured
per stream, all with the **shipping** batch ASR (`worker/models/parakeet-redux-onnx-int4`,
imported by path, read-only):

| number | what it means |
|---|---|
| `words` / `wps` | how much text the ASR extracts from that stream, and per second of audio |
| `sp_s` / `sp_fr` | speech seconds the ASR's own VAD finds in that stream (so silence cannot win the average) |
| `wps_sp` | words per second **of speech**, the fair per-utterance rate |
| `peak_p` | mean posterior of the transducer at every **non-blank** token it emitted — the model's own confidence in the text, the intelligibility proxy. **Not a WER.** |
| `blank_frac` | blank steps / decode steps — rises when audio stops looking like speech |

**The decode loop was copied from the vendor and is pinned by a control.** The vendor's
`greedy()` discards its logits; the copy keeps them to read `peak_p`. `--verify-decode`
then runs the vendor's own `transcribe()` on the same PCM and compares the text:

```
$ python _main/bench/separate.py --engine passthrough --wav _main/bench/windows/w60-t0360.wav --start 0 --span-s 5 --threads 2 --score --verify-decode
            SCORE (shipping ASR parakeet-redux-onnx-int4, score wall 27.1s)
            strm  words    wps   sp_s  sp_fr  wps_sp  peak_p  verify
            mix      19   3.80    4.9   0.98    3.86   0.984  MATCH
```

`MATCH` = the copied loop and the shipping decoder produced the same text. A drift in
the vendor loop turns this into `DRIFT` instead of silently scoring a decode nobody ships.

## 5. The window, and the control arm (mix, one stream)

The 60 s window is **real, loud, continuous speech** — that is measured, not assumed:
the shipping ASR transcribes **211 words in 60 s**, its VAD calls **100 %** of the window
speech, and its mean token posterior is **0.978**.

| arm | stream | words | wps | vad speech s | speech frac | wps_speech | peak_p | ASR wall |
|---|---|---|---|---|---|---|---|---|
| control | **mix** (what the ASR sees today) | **211** | **3.52** | 59.9 | 1.00 | 3.52 | **0.978** | 102.1 s (1 pass, 2 threads, box at 63 %) |

Command:

```
cd I:/!watcher && python -m watcher run --cpu 40 --io very-low --cwd H:/sotto -- \
  python -u _main/bench/separate.py --engine passthrough \
    --wav _main/bench/windows/w60-t0360.wav --start 0 --span-s 60 --threads 2 --score \
    --cost-log _main/bench/logs/sep-20261117.jsonl
```

The ASR itself is not free either: **102.1 s of wall for 60 s of audio at 2 threads**
(85.6 s of child CPU on a box already at 63 %). That is the context every separation
number below has to fit next to.


### Box load while these numbers were taken (declared, because RTF is load-dependent)

The previous lane in `_main/receipt-diarization-decisive.md` §9.3 established that on
this box the SAME arm measured RTF 0.0798 and 0.2571 minutes apart — "an A/B between
executions measures the LOAD, not the variable". So the load is recorded with every
number here:

| when | host CPU | free RAM | what else was running |
|---|---|---|---|
| mix control (60 s ASR) | 63 % | 12.5 GB | another lane's 4-stream `concurrency_probe.py` + 3 × `sotto_worker.py --selftest` |
| MossFormer2 60 s run 1 | 80–82 % | 9.8–13.6 GB | the same, plus three `watcher run` jobs from other repos (`G:/superharness-rebase`, `codeintel index`) |

Consequence for reading the table in §6: **every RTF below is an upper bound taken on a
busy box, not a quiet-box best case.** A lower number would flatter the arm; it is not
reported as if it were the measured one.

## 7. Reproduction — every command, in order

```powershell
# 0. the window, pinned as a file (the corpus is being rebuilt by another lane, §3.4)
py -3 -c "import soundfile as sf, numpy as np; x,_=sf.read(r'_main/bench/discord-call-20261116/mix-16k.wav', start=int(360.0*16000), frames=960000, dtype='float32'); sf.write(r'_main/bench/windows/w60-t0360.wav', x, 16000, subtype='PCM_16')"

# 1. the cage that actually exists (module lives in its own repo)
cd I:/!watcher
python -m watcher run --cpu 40 --io very-low --cwd H:/sotto -- `
  python -u _main/bench/separate.py --engine passthrough --wav _main/bench/windows/w60-t0360.wav `
    --start 0 --span-s 60 --threads 2 --score --cost-log _main/bench/logs/sep-20261117.jsonl

# 2. the two MossFormer2 runs on the SAME window (run 1 caches + scores, run 2 recomputes)
python -m watcher run --cpu 40 --io very-low --cwd H:/sotto -- `
  python -u _main/bench/separate.py --engine mossformer2 --wav _main/bench/windows/w60-t0360.wav `
    --start 0 --span-s 60 --threads 2 --score --cost-log _main/bench/logs/sep-20261117.jsonl
python -m watcher run --cpu 40 --io very-low --cwd H:/sotto -- `
  python -u _main/bench/separate.py --engine mossformer2 --wav _main/bench/windows/w60-t0360.wav `
    --start 0 --span-s 60 --threads 2 --no-cache --cost-log _main/bench/logs/sep-20261117.jsonl

# 3. the UVR arm, same window, twice
python -m watcher run --cpu 40 --io very-low --cwd H:/sotto -- `
  python -u _main/bench/separate.py --engine uvr --wav _main/bench/windows/w60-t0360.wav `
    --start 0 --span-s 60 --threads 2 --score --cost-log _main/bench/logs/sep-20261117.jsonl
python -m watcher run --cpu 40 --io very-low --cwd H:/sotto -- `
  python -u _main/bench/separate.py --engine uvr --wav _main/bench/windows/w60-t0360.wav `
    --start 0 --span-s 60 --threads 2 --no-cache --cost-log _main/bench/logs/sep-20261117.jsonl

# 4. the shipping diarizer (sidecar's own two models) on the same window, twice
python -m watcher run --cpu 40 --io very-low --cwd H:/sotto -- `
  python _main/_diar-run.py --wav _main/bench/windows/w60-t0360.wav --threads 2 --threshold 0.9 `
    --tag sep-lane-w60 --out _main/bench/logs/diar-w60-1.json

# 5. the cache, proven instead of asserted (no model loaded)
python _main/bench/separate.py --engine passthrough --wav _main/bench/windows/w60-t0360.wav --start 0 --span-s 60
python _main/bench/separate.py --engine passthrough --wav _main/bench/windows/w60-t0360.wav --start 0 --span-s 60

# 6. the decode copy, pinned against the shipping decoder
python _main/bench/separate.py --engine passthrough --wav _main/bench/windows/w60-t0360.wav `
  --start 0 --span-s 5 --threads 2 --score --verify-decode

# 7. the census behind §1 (absence is a query, not an opinion)
find . -iname "*demucs*" -o -iname "*sepformer*" -o -iname "*spleeter*" -o -iname "*conv-tasnet*" -o -iname "*asteroid*"
python -c "import importlib.util as u; [print(m, bool(u.find_spec(m))) for m in ['demucs','asteroid','speechbrain','pyannote','clearvoice','modelscope','rotary_embedding_torch','mossformer2']]"
ls -d /i/*model* /i/*Model* /i/models
```

## 6. The measurement table

### 6.1 MossFormer2 — the only real separator on this box

Two independent 60 s passes on the SAME window, each under the declared ceiling
(`watcher run --cpu 40 --io very-low`, `--threads 2`, `chunk_s 10`):

| run | caged how | audio | wall | **RTF** | **peak RSS** | output |
|---|---|---|---|---|---|---|
| 1 (`scale=raw`) key `ccdc974b…` | `watcher run --cpu 40 --io very-low` | 60.000 s | **711.44 s** | **11.857** | **2 362.6 MB** | **two 60 s WAVs** (1 920 044 B each) — per-speaker audio, not labels |
| 2 (`scale=match`, key `4e6a2c28…`) | same | 60.000 s | **1 358.94 s** | **22.649** | **2 304.7 MB** | same shape |
| 3 (`scale=match`, `rev 2`, key `d1a43670…`) | same | 60.000 s | **1 335.11 s** | **22.252** | **2 238.8 MB** | same shape — this is the pass §6.3 reports |

**Second pass on the same window, five hours of other lanes later: `wall 1358.94 s`,
RTF 22.649, peak RSS 2304.7 MB.** The same arm, the same 60 s, the same command — **a
1.9× spread**. This is the prior lane's §9.3 finding reproduced on a different arm: an
RTF taken between executions on this box measures the load. The **intrinsic** cost is the
lower figure (11.857); the 22.649 is what the owner's box does to it while it is busy.

**The thread budget these numbers were taken under — and the defect in it.** Both RTF
figures were produced by a process that had **only torch loaded**, at
`torch.set_num_threads(2)`. But `--score` later loads ONNX Runtime **in the same
process**, and ORT's `intra_op_num_threads` is an independent pool: the process then
held **4 threads for a `--threads 2` flag**. Measured from outside, by `Main` with
`psutil` over 5 s: **pid 47520 → 250.9 % of one core, 30 OS threads, 2012 MB RSS**, and a
peer lane sampled the same job at **386.4 %**, while the owner's UI froze. The flag was
not ignored by either library — the process total was simply double what the flag
advertised, and nothing in the process said so. Fixed in §6.6a; the RTF above is still
valid (torch-only phase) but the *label* "2 threads" was wrong for any scored run.

`child cpu 1146.28 s` for 711.8 s of wall on run 1 — i.e. it held **~2 cores** for the
whole pass. The 40 % cap was never approached; the arm is thread-bound, not cap-bound.

**What that means at corpus scale** (arithmetic, on the measured RTF):

| scope | audio | wall at 2 threads |
|---|---|---|
| one 60 s window | 60.0 s | 711 s = **11.9 min** |
| one 20 s live sidecar window | 20.0 s | **237 s** — 12× slower than real time: **impossible in the live path** |
| the corpus **as it is on disk** | 11 200.0 s | **36.9 h** |
| the corpus **as the manifest describes it** | 13 516.7 s | **44.5 h** |

Disk: two PCM16 streams for the on-disk corpus = **716.8 MB** (2× the 358.4 MB mix);
for the manifest's length, **865.1 MB**. (FLAC would cut that ~2×, not measured here.)

### 6.2 The raw estimate must be rescaled or it is not a measurement

Before any ASR number could mean anything, the output had to be checked, and it failed
the check:

```
s0 rms −1.06 dB   s1 rms −15.14 dB   mix rms −18.37 dB
s0 peak 1.000     ->  690 600 of 960 000 samples at |x| >= 0.999   (72 % clipped)
corr(s0,s1) = 0.0808        corr(s0,mix) = 0.6902      corr(s1,mix) = 0.1252
residual (mix − s0 − s1) rms = −1.54 dB   (louder than the mix itself)
```

The stream was **+17.3 dB above the mixture and 72 % of its samples sat on the digital
rail** — a measurement of the clipping, not of the separator. A mask-based separator's
estimate lives on the *mixture's* scale; ClearerVoice's framework normalises it, and a
loader that skips that step produces the square wave above. `scale="match"` now applies
one joint factor per chunk (`input_rms / estimate_rms`, both streams) so the relative
balance is untouched; `scale="raw"` remains so the clipping stays reproducible.

**This is the second reason the arm had never been run**: run 1 *stored* its streams
and then died in `_stream_stats` on `NameError: name 'residual' is not defined`
(`resid` was assigned, `residual` read). The 2-stream branch had never executed,
because the control arm has one stream. Both bugs were found only because the child's
output is visible under `watcher run` and invisible under `cage.py` (§0).

### 6.3 What separation does to the transcription (the owner's actual question)

Filled from the `scale="match"` pass; the ASR is the shipping
`parakeet-redux-onnx-int4`, the same one that scored the control.
Source: `_main/bench/logs/sep-20261117.jsonl` row `key=d1a43670…` and the run's
own forwarded output in `_main/bench/logs/moss-after.log` (the pass with the
thread budget of §6.6a in force).

| phase (key `d1a43670…`, `rev 2`, `scale=match`, `--threads 2`, 60 s window) | wall | printed evidence |
|---|---|---|
| separation — 60 s in → two 60 s WAVs | **1 335.107 s** (RTF 22.252, peak RSS 2 238.8 MB) | `THREADS process_budget=2 torch=2 … stage=mossformer2-load` |
| ASR scoring — 3 × 60 s streams (mix, s0, s1) | **34.9 s** (ASR model load excluded) | `SCORE (shipping ASR parakeet-redux-onnx-int4, score wall 34.9s)` |
| watcher total | **1 372.6 s** (child cpu 1 232.20 s, startup 0.2 s) | `child exit code 0 — total 1372.6s` |

**A disagreement in the file's own walls, stated rather than smoothed:** §5 logs
**102.1 s** for one 60 s ASR pass; this pass logged **34.9 s** for three 60 s streams
(180 s of audio). Both are as recorded, and 9× is not explained by any number measured
here — the 102.1 s pass ran on a box at 63 % with other lanes' probes (§5), the 34.9 s
pass after the thread change, but neither fact accounts for a 9× spread. It is not used
for any verdict below; the transcription verdict uses word counts and `peak_p` only.

| stream | words | wps | vad speech s | speech frac | wps_speech | peak_p | rms |
|---|---|---|---|---|---|---|---|
| **mix** (control) | **211** | 3.52 | 59.9 | 1.00 | 3.52 | 0.978 | −18.4 dB |
| **s0** | **210** | 3.50 | 59.2 | 0.99 | 3.55 | 0.979 | −18.2 dB |
| **s1** | **2** | 0.03 | 50.7 | 0.85 | 0.04 | 0.874 | −36.5 dB |

The earlier `scale="match"` pass (key `4e6a2c28…`, same 60 s, same commands,
taken before the thread fix, so its three scores ran beside a torch pool that
was not yet halved) is the table in §6.4: 210 vs 210 words on s0, 2 vs 2 on s1,
s1 `peak_p` 0.858 vs 0.874. The two passes agree on everything the verdict in
§8.2 uses; the difference between them is the thread configuration, not the audio.


### 5.1 What the 60 s window actually CONTAINS — a monologue, and why that matters

The control transcript (shipping ASR, `--engine passthrough --score`) is one person
talking without interruption about League of Legends / Wild Rift champion design, in
2 ASR segments, `blank_frac 0.187`:

> "do Wild Rift não foi o caso. A Riot, dentro desse modelo do League of Legends, optou
> por uma escolha muito precisa quando se trata de design. … A Ash, por exemplo, não é
> perfeita, mas ela tenta conversar com que Steel Here criou. …"

**That is the wrong material to judge a separator on.** A 2-speaker separator fed one
speaker has nothing to separate: it either reproduces the voice twice or splits the
same voice's harmonics across streams, and either outcome says nothing about whether
two people's words survive. It is still the right material to judge **COST** on (a
fixed, real, loud 60 s of the frozen corpus — which is what the RTF and RSS columns are).

So the measurement is split in two, and the distinction is carried into every verdict:

| question | material | measured in |
|---|---|---|
| what does a pass COST | this monologue window (real, loud, 60 s) | §6.1 |
| does it IMPROVE transcription of two talkers | needs a window with ≥2 voices | §6.5 (selection below) |

Corpus material, measured so the window is not mistaken for the corpus:

```
$ python -c "…; print(nmins, len(active))"      # 60 s per-minute RMS over mix-16k.wav
minutes: 186   active (> -40 dBFS): 159
```

i.e. **3 h 06 min of the file has signal and 27 min is near-silent**. Nine windows spread
across the active minutes were extracted with their own hashes
(`_main/bench/windows/WINDOWS.json`, `w60-m000/032/054/081/102/121/141/161/183.wav`) to
find one with more than one voice — selected by measurement, not by ear (I cannot hear
audio; that is declared in §9).

## 8. Verdict

### 8.1 The cost answer (measured for the arms that ran)

| arm | present | RTF @2 threads | peak RSS | output shape | verdict |
|---|---|---|---|---|---|
| **MossFormer2_SS_16K** | yes (670 MB ckpt + vendored code) | **11.857** (711.4 s / 60.0 s) | **2 362.6 MB** | **two 60 s per-speaker WAVs** | **KEEP for offline batch, DISCARD for the live path** |
| UVR_MDXNET_9482 | yes (29.7 MB) | **NOT-MEASURED** — the arm was rewritten (§3, item 2) but never run: no `uvr` row in `_main/bench/logs/*.jsonl`, no `uvr` cache entry | **NOT-MEASURED** (same) | 2 stems, music semantics | **NOT-MEASURED** — music splitter, not a speech separator; no number exists to rank it |
| sherpa-onnx diarization (`speaker_sidecar`'s own models) | yes (45.6 MB) | **NOT-MEASURED** — `_main/_diar-run.py` (§7, step 4) was never executed in this lane: no `_main/bench/logs/diar-w60-1.json` | **NOT-MEASURED** (same) | **labels only — no audio** | not a separator: it cannot serve the owner's goal at all |
| demucs / sepformer / spleeter / asteroid | **no** | — | — | — | **absent by name** (§1) |
| torchaudio `SourceSeparationBundle` | API only, weights are a download | — | — | — | **not measured** — not on disk |

**The one number that decides the live path:** a 20 s sidecar window would need
`20 × 11.857 = 237 s` of compute on 2 threads — the separator is **12× slower than the
conversation**. Separation cannot sit in the live loop; the live loop keeps the engines it
has (`nemotron` streaming + `parakeet-redux` batch). This is arithmetic on a measured RTF,
not an opinion.

**The offline path is affordable but not cheap:** the corpus as it is on disk (11 200 s)
costs **36.9 h** at 2 threads and **716.8 MB** of output WAVs. Spread over this box's 20
cores it is ~3.7 h — i.e. an overnight batch, not an interactive feature.

### 8.2 The transcription answer

**On the only window that was separated and scored, separation neither helped
nor hurt transcription, and that is all the numbers say.** Stream 0 carries
**210** words at 3.50 words/s and mean posterior **0.979** against the mix's
**211** at 3.52 and **0.978**; stream 1 carries **2** words at 0.03 words/s,
`peak_p` **0.874**, at **−36.5 dB** RMS (§6.3; the earlier pass in §6.4 reads
the same shape: 2 words, `peak_p` 0.858, −33.7 dB). That window is a
monologue — the control transcript is one person, 2 ASR segments,
`blank_frac` 0.187 (§5.1) — so the result is a **positive control** on the
separator (one voice survives whole into one stream instead of being torn in
two), not an answer about two talkers.

**The two-talker answer is NOT-MEASURED.** §6.5 selected `w60-m054.wav`
(30 handover-shaped gaps, −30.1 dB mean) for that test, but no separation pass
was ever run on it: there is no cache entry and no `_main/bench/logs/*.jsonl`
row for `m054`. Until that pass exists, no sentence in this document claims
separation improves (or fails to improve) the transcription of two voices.


### 6.4 The transcription result on the monologue window (measured, and it explains itself)

`scale="match"`, same 60 s, shipping ASR on each stream:

| stream | words | wps | vad speech s | speech frac | wps_speech | peak_p | rms |
|---|---|---|---|---|---|---|---|
| **mix** (control) | **211** | 3.52 | 59.9 | 1.00 | 3.52 | 0.978 | −18.4 dB |
| **s0** (separator's stream 0) | **210** | 3.50 | 59.4 | 0.99 | 3.54 | 0.979 | −15.4 dB |
| **s1** (separator's stream 1) | **2** | 0.03 | 53.6 | 0.89 | 0.04 | 0.858 | −33.7 dB |

`corr(s0,s1) = 0.009`; residual `mix − s0 − s1` at −25.9 dB.

Read this correctly, because it is easy to read as success and it is not:

* The separator put **the whole monologue in stream 0** and left stream 1 at −33.7 dB
  with 2 words. Its output *reproduces the mix* (210 vs 211 words, `peak_p` 0.978 →
  0.979). Separation neither helped nor hurt **because there was nothing to separate**.
* That is a **positive control on the separator**: fed one voice, it does not shred it
  into two half-voices — which a broken mask would.
* It is **not** an answer to "does separation improve transcription of two talkers".
  That needs a window with two voices, and the selection of one is §6.5.

### 6.6a The thread budget: declared and enforced (the fix for the 4-thread process)

`separate.py` now: (a) reads `--threads` from the raw `argv` **before numpy/torch are
imported** and exports `OMP/MKL/OPENBLAS/NUMEXPR/VECLIB = <budget>`; (b) prints one
`THREADS` line **per stage** with the numbers the libraries actually hold; (c) gives the
ASR only the **remainder** of the budget (`torch` drops to 1 while the ASR runs at 1),
because the two pools SUM.

```
$ python -c "import sys; sys.argv=['separate.py','--threads','3']; sys.path.insert(0,'_main/bench'); import separate as S; S._declare_threads('selfcheck', torch_threads=1, ort_intra=1)"
PROCESS_BUDGET 3 OMP 3
THREADS process_budget=3 torch=1 ort_intra=1 env OMP=3 MKL=3 OPENBLAS=3 stage=selfcheck
```

The run that carries the claim, 10 s of the same window (ceiling declared before
launch, in numbers: **2 threads total**, watcher CPU hard cap **10 % of the box = 2 of
20 logical cores**, IO **very-low**, RSS ceiling **3 072 MiB** enforced inside the
process). 2026-11-19, full output in `_main/bench/logs/sep-threads-run.log` — **that path is
git-ignored** (`.gitignore:29` `*.log`, the corpus rule that keeps measurement output
out of the clone), so every line that carries this claim is pasted below and the run
regenerates with the command shown:

```
$ cd I:/!watcher && python -m watcher run --cpu 10 --single --io very-low --cwd H:/sotto -- \
    python -u _main/bench/separate.py --engine mossformer2 \
      --wav _main/bench/windows/w60-t0360.wav --start 0 --span-s 10 \
      --threads 2 --device cpu --hash-mib-s 0 --score \
      --cost-log _main/bench/logs/sep-20261117.jsonl
topology logical=20 hybrid=True p=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11] e=[12, 13, 14, 15, 16, 17, 18, 19]
launched pid=2764: python -u _main/bench/separate.py --engine mossformer2 ...
job CPU hard cap 10%  (children inherit)
io priority VeryLow (readback=0) — the tree loses the disk QUEUE, never the disk
THREADS process_budget=2 torch=2 ort_intra=n/a env OMP=2 MKL=2 OPENBLAS=2 stage=mossformer2-device-resolve
DEVICE {"requested": "cpu", "resolved": "cpu"}
...
MISS 761a78ab5b00f335953daa1855c39c565cfd7d1c1adc0c6ed41360fa51f389a4  (mossformer2, 10.00 s of audio)
THREADS process_budget=2 torch=2 ort_intra=n/a env OMP=2 MKL=2 OPENBLAS=2 stage=mossformer2-load
COST engine=mossformer2 audio_s=10.00 wall_s=222.289 rtf=22.2289 rss_peak_mb=2278.5 threads_budget=2 process_threads_peak=19 gpu_allocated_peak_mb=None gpu_reserved_peak_mb=None gpu_nvml_baseline_free_mib=None gpu_nvml_min_free_mib=None gpu_nvml_peak_used_mib=None (PROCESS total: torch+ort SUM to it, not each)
child exit code 1 — total 228.0s (startup 0.3s, wait 227.1s, not-scheduled 0.0s, wrapper cpu 1.42s, child cpu 277.14s)
```

What this run settles, and what it does not:

* **Settles the declaration.** The process printed the budget itself, twice
  (`stage=mossformer2-device-resolve` and `stage=mossformer2-load`), both
  `process_budget=2 torch=2` with `env OMP=2 MKL=2 OPENBLAS=2`. Before this fix the
  dedupe key was the string `"declared"`, so only the first stage ever printed and the
  second pool was invisible; the `stage=` field is what makes the stages separable.
* **Settles enforcement on the separation phase, sampled from OUTSIDE.** The sampler
  below found the model process (`pid 2764`, not its wrapper) and took 23 samples at
  5 s (`_main/bench/logs/sep-threads-samples-child.txt`): CPU **56.6–172.2 % of one
  core** (mean 109.9 %), OS threads **14–15**, RSS rising to **2 166 MB** and falling
  back to 941 MB. Two threads never reached the 200 % (2-core) hard cap.
  `process_threads_peak=19` in the `COST` line is OS threads, not compute threads.
  Per-phase wall for the whole run: hash of the 670 MB checkpoint **1.32 s**
  (`--hash-mib-s 0`), then separation **222.289 s** including model load, then the ASR
  attempt (died at once, below); watcher total **228.0 s**, child cpu **277.14 s**.
* **Does NOT settle the ASR half of the budget — NOT-MEASURED, with the reason.** The
  shipping ASR refused to load: `RuntimeError: Redux ONNX GPU-only policy requires
  exactly CUDAExecutionProvider; got []` (`worker/models/parakeet-redux-onnx-int4/transcribe.py:215-229`).
  So `stage=asr-load` printed nothing and "torch drops to 1, the ASR takes 1" could not
  be sampled on 2026-11-19. The code does implement it (`separate.py` `main()`:
  `torch.set_num_threads(1)`, then `asr_threads = PROCESS_BUDGET - 1`), and the
  2026-11-17 scored pass of §6.3 did load the ASR after torch and scored in 34.9 s, but
  that run predates the per-stage print, so it left no `asr-load` line either. The
  process exited `rc=1` on that refusal — the same GPU-only policy that keeps the live
  worker dead (outage note in §6.8).


### 6.8 What I could NOT measure (declared, so nothing above is over-read)

1. **WER.** There is no reference transcript for the frozen corpus, and I refuse to
   invent one. Every transcription number here is **words/s + a speech-region peak
   proxy** (§4), which detects *damage and empty streams* and cannot detect *substitutions*
   that preserve word counts. A 210-vs-211 result is "no damage", not "no errors".
2. **Listening.** I cannot hear. "Sounds good" appears nowhere in this document; every
   judgment is a number from `numpy`/`parakeet`/`psutil`.
3. **The GPU.** Every cost row above was taken with `--device cpu`. The interpreter used
   here is `torch 2.15.0+cu134` and `torch.cuda.is_available()` is **True** (1 device), so
   "CPU only" is not a property of this box; `--device cpu` was pinned to keep the rows
   comparable. GPU passes exist in the cache (`mossformer2` keys `3225fc8c…` and
   `fa48c43a…`, 10 s, `rtf 0.301` / `0.346`, `process_threads_peak` 15 / 14, written
   2026-11-17 10:16–10:28 by another lane running this same harness) but were not
   re-measured here, so no GPU-vs-CPU factor is claimed.
4. **The corpus at scale.** 60 s measured; 186 minutes would cost ~36.9 h at RTF 11.857
   and would produce 716.8 MB. That is arithmetic on one measured RTF, not a batch run.
   The measured 1.9× load sensitivity (§6.1) means the real batch could cost 2× that.
5. **Peak RSS at 186 minutes.** Measured at 60 s (2.3 GB) — the model is fixed-size, so the
   peak is not expected to grow with input, but that is an expectation, not a measurement.
6. **`sherpa-onnx` diarization inside the live worker** (`speaker_sidecar`) — read and its
   two models identified; whether the live path still calls it after D-33 is a question for
   the worker lane, not something a 60 s bench run answers.
7. **Re-scoring on 2026-11-19.** `--score` cannot run on this box today: the shipping ASR
   requires exactly `CUDAExecutionProvider` and ONNX Runtime registered none
   (`RuntimeError: Redux ONNX GPU-only policy requires exactly CUDAExecutionProvider;
   got []`, `worker/models/parakeet-redux-onnx-int4/transcribe.py:215-229`, reproduced in
   the same git-ignored run log cited above). The transcription numbers in §6.3 and §6.4
   are the 2026-11-17 measurements, reported as measured and **not re-verified today**.
### 6.5 Finding a window with TWO voices (selected by measurement, not by ear)

With no reference transcript and no ability to listen, the selector is a **turn-taking
proxy** computed with numpy only (20 ms frames, speech = within 25 dB of the window's
max): count **short gaps (150-900 ms) inside speech** — the fingerprint of two people
handing each other the floor — plus the fraction of speech frames in the quieter of two
energy clusters (two voices at two levels). This is a **selector**, not a verdict; the
claim "≥2 voices" is only made where the diarizer confirms it — and the diarizer arm
was never run (§8.1), so `m054` stays a **candidate**, not a confirmed two-voice window.

```
$ python - <<'PY'   # pure numpy over the 9 extracted windows, no model
… short_gaps = count of 0.15-0.9 s gaps inside speech; bim = quieter-cluster fraction …
PY
w60-m141.wav   short_gaps=31 bim=0.324 env_std= 5.9 mean=-40.5 dB
w60-m054.wav   short_gaps=30 bim=0.329 env_std= 6.0 mean=-30.1 dB
w60-t0060.wav  short_gaps=24 bim=0.320 env_std= 6.3 mean=-31.0 dB
w60-m102.wav   short_gaps=16 bim=0.317 env_std= 5.8 mean=-42.9 dB
…
w60-t0360.wav  short_gaps= 7 bim=0.331 env_std= 5.8 mean=-23.7 dB   <- the monologue of §5.1
w60-t0120.wav  short_gaps= 0 bim=0.076 env_std= 4.4 mean=-31.6 dB
```

The window I had measured cost on (`t0360`, 7 short gaps) sits where the transcript says it
should: one person, no handovers. **`w60-m054`** is the candidate for the two-talker test
(30 handover-shaped gaps, loud at −30 dB). `m000`/`m032` are near-silence (−117 dB mean) —
they are in the set only because the extraction was blind to level, which §3.4 already
records as a defect of that pass.
### 7.1 The thread-budget proof and the sampled cost run (exact commands)

```
# the budget scan, proven at import time (no model): 3 in -> 3 everywhere
$ python -c "import sys; sys.argv=['separate.py','--threads','3']; sys.path.insert(0,'_main/bench');
  import separate as S; S._declare_threads('selfcheck', torch_threads=1, ort_intra=1)"
PROCESS_BUDGET 3 OMP 3
THREADS process_budget=3 torch=1 ort_intra=1 env OMP=3 MKL=3 OPENBLAS=3 stage=selfcheck

# the run that carries the ceiling: --single refuses a duplicate with exit 75,
# --cpu 10 = a 2-thread process on a 20-core box
$ python -m watcher run --cpu 10 --single --io very-low --cwd H:/sotto -- \
    python -u _main/bench/separate.py --engine mossformer2 \
      --wav _main/bench/windows/w60-t0360.wav --start 0 --span-s 60 \
      --threads 2 --score --cost-log _main/bench/logs/sep-20261117.jsonl
```

That 60 s command is the 2026-11-17 one (no `--device`/`--hash-mib-s`, because that
`rev` did not have them); the 2026-11-19 run of §6.6a uses 10 s and pins
`--device cpu --hash-mib-s 0`, because `--score` no longer loads at all (§6.8.7).

The sampler that produces the per-pid CPU trace is a small inline `psutil` loop (kept
inline, not a file: it is instrumentation of one run, not a product). It has to find the
**model** process, and the obvious `cmdline` match finds the `watcher` wrapper instead —
the wrapper's own argv contains the child's command:

```python
import psutil, time
out = open("_main/bench/logs/sep-threads-samples-child.txt", "w", buffering=1)
def child():                      # "watcher" in cmdline == the wrapper, not the child
    best = None
    for p in psutil.process_iter(["pid", "cmdline", "create_time"]):
        j = " ".join(map(str, p.info["cmdline"] or []))
        if "separate.py" in j and "mossformer2" in j and "watcher" not in j:
            if best is None or p.info["create_time"] > best[1]:
                best = (p.info["pid"], p.info["create_time"])
    return best
while not child():
    time.sleep(0.5)
pid, created = child(); proc = psutil.Process(pid)
out.write("# pid %d create %s\n" % (pid, time.strftime("%H:%M:%S", time.localtime(created))))
while True:
    try:
        pct = proc.cpu_percent(interval=5.0); rss = proc.memory_info().rss
        n = proc.num_threads()
    except psutil.NoSuchProcess:
        break
    out.write("t=%s cpu_pct_of_one_core=%.1f threads=%d rss_mb=%.0f\n"
              % (time.strftime("%H:%M:%S"), pct, n, rss / 1048576.0))
```

**The trace an earlier pass left (`_main/bench/logs/moss-after-samples.txt`) is discarded,
and the reason is the defect above.** Its header records `pid 29144` while the run it is
meant to trace launched `pid 49036` (`moss-after.log`), and all **272** of its samples read
`cpu 0.0 % of one core, threads 3–8, rss 38–39 MB` — it sampled an idle wrapper, never the
model process. It is therefore **not** evidence for anything in §6.6a. The corrected
finder above is what produced `sep-threads-samples-child.txt`, the 5 s trace quoted there.

## Evidence that lives OUTSIDE the clone, and how to rebuild it

Three artefact classes this receipt rests on are git-ignored **by design** (`.gitignore:29`
`*.log`, `:57` `*.jsonl`, `:30` `*.wav`), so a clean checkout has the numbers in this file
and not the bytes. Each one reproduces with one command, and the manifests beside them pin
the sha256 that makes a rebuild comparable byte for byte:

| artefact | ignored by | rebuild |
|---|---|---|
| `_main/bench/logs/*.log`, `*.jsonl` (run output, cost log) | `.gitignore:29,57` | re-run the caged command quoted in the section that cites it |
| `_main/bench/windows/w60-*.wav`, `spans/*.wav` (the cut spans) | `.gitignore:30` `*.wav` | `_main/bench/windows/WINDOWS.json` names the corpus and, for every window, its offset and `sha256_int16`; `_main/bench/spans/SPANS.json` does the same for the span set |
| `_main/bench/discord-call-20261116/mix-16k.wav` (the corpus) | `*.wav` | `python _main/bench/discord-call-20261116/freeze-corpus.py` (its docstring carries the ffmpeg line and the sha in `manifest.json`) |

Only one trace lives in the index: `sep-threads-samples-child.txt`, the corrected 5 s trace
(§6.6a). `moss-after-samples.txt` is **not** committed — 272 samples of an idle wrapper measure
nothing, and a second copy of a non-measurement is the same poison as a compatibility shim. The
receipt keeps the defect on record; the bytes stay on the disk where they were produced.
