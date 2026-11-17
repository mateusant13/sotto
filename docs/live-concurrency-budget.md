# Live concurrency budget — how many speaker streams fit on this machine

Measured 2026-11-17 on H:\sotto. One "stream" = one `worker/sotto_worker.py` process running the
shipped live engine (`nemotron-3.5-asr-ptbr-onnx-int4`, 8960-sample = 560 ms chunks) at the shipped
`--threads 2`, fed the same 300 s of real call audio. Everything below is a number this task
produced; the JSON receipts are under `_main/bench/concurrency/`.

## Answer

| question | measured answer |
|---|---|
| streams that fit with margin (every stream under 0.6 RTF) | **4** — worst stream RTF **0.591** (1.7× headroom), **5 523.3 MB** RSS, **26.9 %** of the 20-core box, at 48.1 % ambient CPU |
| streams that did NOT fit | **5** — worst stream RTF **1.033** (past real time) at 69.1 % ambient CPU |
| cost of one more stream | **~1.9 cores** (1.96 at N=1, 1.90 at N=2), **1.24–1.55 GB RSS**, **1.57 GB VRAM**, 4–13 s model load (38 s on a cold page cache) |
| what binds | **CPU-core availability under the box's other load** — not RAM, not VRAM, not the declared 40 % cap |

## What is being run (and what it is not)

`worker/sotto_worker.py --selftest --audio <wav> --threads 2` is the product's own no-device arm:
the same `StreamAsr.run_chunk()`, the same VAD/gate, the same `LineFormer`, the same JSONL contract,
over a file instead of a capture tap. The thread plan it printed on every stream is
`WORKER_THREAD_PLAN encoder=2 small=1 sessions=3 total_intra=4 budget_total=2 budget_batch=2`, i.e.
2 encoder threads + 1 thread each for decoder and joint, **4 intra-op threads per process**, with
54–55 OS threads alive per process.

The window is a slice of the frozen corpus, checksummed:

```
ffmpeg -v error -nostdin -ss 300 -t 300 -i _main/bench/discord-call-20261116/mix-16k.wav \
       -ac 1 -ar 16000 -c:a pcm_s16le -y _main/bench/concurrency/window-300s-16k.wav
# 4 800 000 frames / 16 000 Hz = 300.0 s, mono s16
# sha256 f351295b9770685c37cdddf29071937afe155b4e16f52f123d8f00084f3bab90
```

At t=300–600 s the corpus's own `speech-60s.csv` reports speech fraction 0.984 / 0.994 / 0.410 /
0.522 / 0.981 per minute — a speech-dense window, not a silent one. Every run decoded **1 927
tokens**, identical in all 15 completed streams: concurrency did not change what was recognised.

## The ladder

Ceiling declared before every rung: **2 threads/session (4 intra-op per process), CPU hard cap 40 %
of 20 cores = 8 cores (enforced by the watcher job object), IO = one 9.6 MB wav read per stream plus
one 787 MB model read per stream if the page cache is cold, and RSS ≤ 1200 MB × N for the rungs below
— which the measurements exceeded, so the declaration is 1600 MB × N from here on (see "Declared vs
measured").** One rung of mine at a time. What else the box was running is not under my
control: it is recorded per rung as `ambient` (a 1 s `psutil.cpu_percent` sample taken immediately
before the rung), and a peer lane's `_main/bench/separate.py` probe was observed on the same box
around the n5 rung.

```
PYTHONPATH="I:/!watcher" python -m watcher run --cpu 40 --io very-low -- \
  python _main/bench/concurrency_probe.py --streams N \
    --wav _main/bench/concurrency/window-300s-16k.wav \
    --out _main/bench/concurrency/nN.json --label nN
```

| rung | streams | ambient CPU before | declared RSS MB | measured RSS total MB | wall s | RTF worst | RTF best | peak box % | VRAM peak MB | audio-s per wall-s |
|---|---|---|---|---|---|---|---|---|---|---|
| n1 | 1 | UNMEASURED | 1 200 | 1 306.1 (+8.8 %) | 93.51 | 0.185 | 0.185 | 19.4 | UNMEASURED | 3.20 |
| n2 | 2 | UNMEASURED | 2 400 | 2 926.3 (+21.9 %) | 75.77 | 0.186 | 0.177 | 22.1 | UNMEASURED | 7.91 |
| n3 | 3 | 52.1 % | 3 600 | 3 913.8 (+8.7 %) | 139.27 | 0.310 | 0.168 | 24.4 | 7 303.2 | 6.45 |
| n4 | 4 | 48.1 % | 4 800 | 5 523.3 (+15.1 %) | 244.07 | 0.591 | 0.232 | 26.9 | 8 876.3 | 4.91 |
| n5 | 5 | 69.1 % | 6 000 | 7 783.5 (+29.7 %) | 350.35 | 1.033 | 0.271 | 19.4 | 13 261.3 | 4.28 |

Produced by:

```
python _main/bench/concurrency_summary.py \
  _main/bench/concurrency/n{1,2,3,4,5}.json
```

Per-stream cores and CPU seconds, same files:

| rung | cores per stream | Σ cores (each child's CPU s ÷ its own infer wall) | total CPU s | core-s per audio-s | model load s (max) |
|---|---|---|---|---|---|
| n1 | 1.96 | 1.96 | 109.0 | 0.3637 | 37.95 (wall − infer; cold cache) |
| n2 | 1.90 | 3.80 | 206.6 | 0.3448 | 12.91 |
| n3 | 1.71 | 5.14 | 336.7 | 0.3746 | 48.96 |
| n4 | 1.02 | 4.08 | 459.3 | 0.3833 | 58.30 |
| n5 | 0.54 | 2.68 | 394.4 | 0.2633 | 9.83 |

**Rungs n1 and n2 carry no ambient reading** (the ambient field was added to the probe after they
ran), so their RTF is not comparable to n3–n5 as a controlled ladder: n2 finished the same audio in
75.77 s while n1 took 93.51 s, and n1 paid a cold-cache model load. The ambient-matched comparison
exists for **n3 (52.1 %) vs n4 (48.1 %)**: going from 3 to 4 streams raised the worst stream from 0.310 to
0.591 with ambient nearly unchanged. n5's ambient was 69.1 %, which is the rung's confound and is
stated as such, not corrected for.

**One rung-3 attempt is not in the table.** On the first N=3 launch one of three children stopped
advancing at audio t=50.4 s: age 584 s, 60.6 s CPU consumed, 0 % CPU at inspection, 5.9 MB resident
(working set trimmed). The tree was killed; the immediate rerun completed 3/3. That is one
unreproduced stall of the OpenMP/ORT class `limit_threads()` already documents; no number in this
document depends on it, and the probe now kills and reports such a child (`--stall-s 120`).

## Each extra stream costs

- **CPU:** ~1.9 cores of steady demand (1.96 measured at N=1, 1.90 at N=2), 0.34–0.38 core-seconds
  per second of audio. The cost is inside the encoder: at N=1, `stage_s` = pre 3.52 / **enc 41.29** /
  dec 8.86 s — 77 % of decode time; at N=5 the starved streams spent 176.7–207.8 s in `enc` alone.
- **RAM:** 1 236.4–1 548.3 MB per process (RSS sampled at 0.5 s), i.e. one 787 MB model per stream —
  the ASR sessions are per process, and there is no shared session.
- **VRAM:** +1.57 GB per stream, exactly: 2 590.7→8 876.3 MB for 4 streams (+6 285.6) and
  2 548.4→13 261.3 MB for 5 (+10 712.9). Per-process attribution is not available on this driver
  (`nvidia-smi --query-compute-apps=used_memory` returns `[N/A]`), so this is the box delta.
- **Load:** 3.9–12.9 s per stream with the model in the page cache, 58.3 s when the box is busy, and
  ≈38 s cold. This is paid per stream because each stream is a process.

## Where the limit binds

| candidate | number | verdict |
|---|---|---|
| declared 40 % CPU cap (8 cores) | peak tree CPU 19.4 / 22.1 / 24.4 / 26.9 / 19.4 % of the box | **never reached** — the cap did not bind any rung |
| per-session thread pools | 4 intra-op threads per process, 54–55 OS threads, 5 processes = ~275 threads | **not the limit** — the box never exceeded 26.9 % of its 20 cores |
| RAM | 51 229 MB total; 19 585.8 / 16 591.8 / 18 284.2 / 19 189.1 / 14 816.3 MB free after each rung; 1.24–1.55 GB per stream | **not the limit** — free RAM after n4 admits ~12 more streams |
| VRAM | 16 303 MiB total (17 095 MB); 13 261.3 MB peak at n5 (77.6 %), ~2.4–2.6 GB of it the desktop | **not the limit at 4** — ~8 streams would fit in VRAM |
| core availability under the box's other load | n4: ambient 48.1 % + Σ 4.08 cores = 69 % of the box, worst RTF 0.591. n5: ambient 69.1 % left ~6 cores, the five streams got 2.68 cores total, worst RTF 1.033 | **this is what binds** |

The 20 logical cores are hybrid — the watcher reported `topology logical=20 hybrid=True
p=[0..11] e=[12..19]` — so "11 of 20 cores" is not 11 equivalent cores: 12 P-cores and 8 E-cores,
and which pool an ORT thread lands on changes its throughput. That is why per-stream RTF degrades
non-linearly (0.185 → 0.31 → 0.59) while aggregate CPU stays under half the box.

Machine-wide upper bound, **not measured** (see below): 20 cores ÷ 1.9 cores/stream ≈ **10 streams**
would be the linear arithmetic, assuming the box is otherwise idle and RTF degrades linearly. The
measured points say it does not degrade linearly, so treat 10 as arithmetic, not as a capacity.

## What would have to change to exceed 4

1. **Cut the encoder's cost per stream.** 70–77 % of decode time is `enc`; ~1.9 cores per stream is
   the whole budget. The shipped config requests CUDA and the session reports
   `["CUDAExecutionProvider","CPUExecutionProvider"]`, yet one stream still spends 41.3 s of CPU-side
   wall in `enc` for 300 s of audio and burns 1.96 cores — and VRAM grew 1.57 GB per stream, so the
   EP is loading weights somewhere. `[INFERENCE]` which nodes actually execute on the GPU is not
   established here: the arithmetic that would settle it (the same rung with
   `--providers CPUExecutionProvider`) was not run, because the box was 88–97 % busy with other
   lanes' work whenever a free slot appeared. Either of two changes moves the curve — execute that
   graph on the GPU for real, or batch several streams' chunks through one encoder pass.
2. **Stop paying one model per stream.** Today each stream is a process: 787 MB of weights, 1.24–1.55 GB
   RSS and 4–13 s of load, per stream. A single process holding N streams (or a shared session) would
   cut the marginal RSS and load cost, though each additional ORT session still allocates its own
   weights.
3. **Buy back ambient headroom.** The same 4-stream shape passed at 48.1 % ambient and the 5-stream
   shape failed at 69.1 %. Any other heavy lane on this box is charged to the stream budget.
4. **Lower the per-stream thread budget** only with a measurement: 2 encoder threads is already the
   shipped floor, and the failure at n5 was too little CPU, not too many threads.

## Declared vs measured — a defect in the record

Rungs n1–n5 were declared at **1200 MB per stream**. The measured per-stream RSS is 1 236.4–1 548.3 MB,
so **every rung exceeded its own declared ceiling**: n1 +8.8 %, n2 +21.9 %, n3 +8.7 %, n4 +15.1 %,
n5 +29.7 % (7 783.5 MB against 6 000). The declaration, not the run, was wrong; the probe now declares
**1600 MB per stream** (`_main/bench/concurrency_probe.py`, the `CEILING:` line). No rung was refused
by RAM — the smallest free-RAM reading after any rung was 14 816.3 MB against 7 783.5 MB of total
tree RSS — but the *declared* ceiling was wrong and is recorded as wrong here rather than restated
after the fact.

## What this does NOT prove

- Every stream is fed the **same 300 s file**, so this measures the **cost per stream**, never
  separation: it says nothing about how well the engine handles N voices arriving simultaneously,
  overlapping, or with different levels.
- It runs `worker/sotto_worker.py --selftest --audio <wav>`, i.e. the shipped engine in **file mode**
  at the shipped `--threads 2` — not the live tap path (WASAPI capture, ring buffer, `LineFormer`
  deadlines, the speaker sidecar). A reader must not take this for a live-path proof.

## Could not be measured

- **Rungs ≥ 6.** The ladder stopped at n5 because the per-stream RTF crossed 1.0 there (1.033). That
  crossing happened at 69.1 % ambient CPU, so it is a statement about this box under that load, not
  about 20 idle cores.
- **Ambient-matched rungs 1 and 2.** No ambient reading was instrumented on those two runs; their
  RTF is therefore `UNMEASURED` for comparison purposes. n3/n4 (52.1 % vs 48.1 %) are the only
  ambient-matched pair.
- **Per-stream VRAM.** The driver reports `[N/A]` per process; only the box-wide delta is known.
- **Whether the CUDA EP executes the encoder.** The two arms that would settle it (the same rung with
  `--providers CPUExecutionProvider`, and GPU-utilisation sampling) were not run: no free slot came
  up, and the box sat at 82–97 % CPU with another lane's `_main/bench/separate.py` probe running.
  The ambient re-runs of rungs 1–2 are blocked by the same condition.
- **The live capture path and speaker separation.** No audio device, no capture tap, no diarizer, no
  live worker was started or touched by this task.
