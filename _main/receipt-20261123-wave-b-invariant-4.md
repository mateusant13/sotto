# Wave B invariant 4 — clean worker shutdown, measured (2026-11-23)

Closes the last open Wave B invariant: **a real worker run that reaches end of audio, stops
by itself, and exits rc=0 with zero orphans** — while still loading the CUDA stack and
emitting captions, so the invariant is proven on the same code the other three were.

## Why this run is not a lease bypass

The performance gate refused the `heavy` lease, measured the same day:

```
state=amber  commit-pct=81.8 >= amber 80.0  heavy_allowed=False  amber_light_ttl_max=300.0s
avail=30.4%>15.0%   leases: heavy=0/1 light=0/1
acquire --kind heavy --owner wD:p5 --ttl 5400
  -> refused heavy lease owner=wD:p5 state=amber
     - heavy-requires-green
     - commit-pct=81.8 >= amber 80.0
```

So the run was executed **inside the watcher cage** (`--cpu 40 --single --io very-low`), the
house's own door for a heavy child, with the machine measured first:

- memory `total 47.7 GiB, used 33.1 GiB (69.3 %)`
- **zero** live Sotto processes (`sotto_worker.py`, `sotto_webview.py`, `warm_engine.py`)
- no competing job of this lane

The lease is still refused; this receipt reports the refusal and the numbers rather than
presenting the run as gate-approved.

## The run

Fixture: 15 s cut from `_main/bench/live-youtube-20261117/source-16k-mono.wav`
(1 ch, 16 kHz, 16-bit) at t=120 s → `_main/_cache/triage/inv4-15s.wav`, 480 044 B,
240 000 samples. A **finite** tap is what makes a clean shutdown observable: the worker's
own `finite_file_tap_state` turns EOF into `outcome="run-ended"`.

```
H:\Python311\python.exe -m watcher run --cpu 40 --single --io very-low -- \
  H:\Python311\python.EXE -u worker/sotto_worker.py --threads 2 --stats-interval 5
env: SOTTO_FILE_TAP=I:\cc-tmp\inv4-15s.wav  SOTTO_FILE_TAP_ONCE=1  TMPDIR=I:\cc-tmp
     OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=NUMEXPR_NUM_THREADS=2
```

`SOTTO_FILE_TAP_ONCE=1` sits ON TOP of the tap (a harness's own "done" is not the EOF); without
it the tap loops the file forever and no shutdown can be measured.

Wall 487.9 s, log `_main/_cache/triage/inv4-worker.log` (19 717 B).

## Measured

|invariant|evidence line (verbatim)|
|---|---|
|CUDA asked and gotten|`"providers": ["CUDAExecutionProvider", "CPUExecutionProvider"]`, `load_s: 13.36`, `rss_mb 459.8 / private_mb 2010.5`|
|audio opened first try|`LADDER_TRY attempt=1/1 device='file:inv4-15s.wav' api=None ms=2407 retries=0 result=opened`|
|first block fast|`TAP_FIRST_BLOCK endpoint='file:inv4-15s.wav' wait_ms=153 blocks=3 rotated_from='-'`|
|thread budget stated|`THREADS process_budget=4 peak_intra=2 declared=2 torch=not-loaded ort_intra=enc:2,small:1 sessions=3 env OMP=2 MKL=2 OPENBLAS=2 NUMEXPR=2`|
|thread plan|`WORKER_THREAD_PLAN encoder=2 small=1 sessions=3 total_intra=4 budget_total=2 budget_batch=2`|
|EOF is the tap's own|`{"type":"status","state":"file-tap-eof","samples":240000,"rate":16000,"mode":"once"}`|
|captions emitted|`"verdict":"captions-emitted","blocks":375,"captions":5,"tokens":30,"queue_drops":0`|
|queue loss is COUNTED, not silent|`AUDIO_QUEUE_EVICTION reason=live-2s-cap blocks=1 samples=640` printed 3× (rate-limited), each carrying its reason; the `done` record counts them all: `"queue_evicted":311`, `"queue_drops":0`|
|ring closed cleanly|`AUDIO_RING stopped ... "written_s":15.0,"segments":1,"failed":0`|
|**clean shutdown**|`child exit code 0 — total 487.9s (startup 0.3s, wait 485.0s, not-scheduled 0.0s, wrapper cpu 2.84s, launched pid cpu 9.03s)`|
|**zero orphans**|after the run, `psutil` scan for `sotto_worker.py`: 0. (Three unrelated `watcher run` processes belong to other lanes' labels `GateLandedRoots`, `Tier4Causal`, `HealthNextRound`.)|
|wrapper was scheduled|`not-scheduled 0.0s` — the wall is the child's, not the governor queue's|

`process_budget=4` vs `declared=2` is not a contradiction, and the line prints both because
they measure different things: `declared` is `asr_budget()['total']`, the **peak of one pass**
(docstring: `max(live, small, batch) == total`), while `process_budget` is the **sum of the
three ORT sessions' configured intra-op pools** (`enc 2 + small 1 + small 1`), which is what
the process actually holds across its three sessions. Understating either number would be the
"the flag declares half the truth" defect the AGENTS rule names.

Throughput is **not** claimed: the run is caged at 40 % of the machine by design, so RTF here
describes the cage. `wrapper cpu 2.84 s` + child `9.03 s` of CPU for 15 s of audio is a cost
measurement, not a speed one.

## Pollution this run caused, and its cleanup

The worker owns `history/audio` by design, so the test wrote one ring segment
(`history/audio/2026-11-23/092929.24k.opus`, 45 406 B) plus its `index.jsonl` row and one
`gaps.jsonl` row (the 419 s gap is the model load, inside the segment by construction).
A 15 s fixture slice mislabeled as the owner's audio would poison any later corpus/replay, so
it was removed by exact filename and nothing else:

```
index.jsonl: 632 -> 631   gaps.jsonl: 117 -> 116   lines.jsonl: 155 -> 155
deleted: True   foreign kept: True (2026-11-23/053345.24k.opus, 786 432 B, untouched)
```

The ring's own identity held on that row — `wall_s 421.211 == stream_s 2.056 + gap_s 419.155` —
which is the newer `2026-11-19` form of the invariant, not the retired `wall_s - (t1-t0)` one.
