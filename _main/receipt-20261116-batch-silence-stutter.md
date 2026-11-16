# RECEIPT — stutter episode of pid 25972: the batch ASR decodes DIGITAL SILENCE, window by window

Measured 2026-11-16 between 19:0x and 19:15 on this box. Every number below has the command
that produced it next to it; nothing is copied from an older log except the two historical
`REDUX_ENGINE_DONE` samples, which are labelled with their date.

## 1. Attribution (the work is this tree)

| what | evidence |
|---|---|
| shell | `pythonw.exe(25972)` started `2026-11-16 16:47:55.087`, argv `… sotto_webview.py --log H:\sotto\_main\webview-run.log --no-self-relaunch --ready-file …` |
| worker | `python.exe(20584)`, `BRIDGE_SPAWNED pid=20584 argv=["H:\\Python311\\python.EXE","-u","H:\\sotto\\worker\\sotto_worker.py","--threads","2"]` at `16:47:55.218` |
| thread plan it declares | `WORKER WORKER_THREADS threads=2 source=flag` |
| DM | watcher, `cpu 17.7% of machine over 12 proc(s)` at the episode (18 % of machine ≈ 3.5 cores of 20) |

## 2. Freshness (step 0 of the bug-hunt)

`python _main/live-code-freshness-oracle.py` at 19:15:19:

```
LIVE_CODE STALE log=H:\sotto\_main\webview-run.log
  pid=25972 started=2026-11-16 16:47:55.087
  prova A : hash diferente
  prova B : 12 ficheiro(s) com mtime depois do arranque
```
The 12 changed files are shell/panel assets (`sotto_webview.py`, `caption_overlay.py`,
`capture_exclusion.py`, `youtube_monotonic.py`, `panel.html`, `panel.js`, the six theme
sheets). **The batch path judged below is not among them**: `worker/engine_policy.py`
(2026-11-15 01:57), `worker/engine_switch.py` (2026-11-12 00:42), `worker/redux_live.py`
(2026-10-17) all predate the 16:47:55 spawn, i.e. the worker is running the code on disk.
The shell half of this receipt is a measurement of older shell code and is marked as such.

## 3. Cost, by thread, with names

`python _main/shell-thread-cpu.py 20584 --burst --seconds 40 --above 20`

```
BURST t=+1.0s fios=309.4%  session-16-intra-op-3:73.4%  session-16-intra-op-2:73.4%
                           session-16-intra-op-1:71.9%  session-16-intra-op-0:71.9%
BURST-END segundos_acima_de_20%=5 pico_fios=309.4% processo_total=31.9% na janela
```

`python _main/shell-thread-cpu.py 25972 --burst --seconds 20 --above 20` (the shell):

```
processo_total=8.7%  pico=sotto-batch-executor:28.4%
```

So the holder is the **worker**, in bursts of 309 % of one core, and the shell is not it.
One ORT session named `session-16` runs **FOUR** intra-op threads against a declared plan
of 2 (`REDUX_LIVE_THREADS = 2`, `worker/engine_switch.py:279`). That discrepancy is an
open question handed to the fix lane, not resolved here.

## 4. What the batch was decoding, and why it was silent

From `_main/webview-run.log`, same minutes:

```
19:07:18.580 WORKER REDUX_ENGINE_LOAD engine=onnx model=parakeet-redux-onnx-int4 load_s=2.17 rss_mb=543.8 loads=1
19:07:2x    REDUX_BATCH_KICK reason=interval engine=parakeet audio_s=30.0 kicks=2  held_in=119717 … asr_expired=3
19:07:xx    STATUS_APPLIED text="redux-batch-empty" (repetidas_silenciadas=N)
…           REDUX_BATCH_KICK reason=interval engine=parakeet audio_s=30.0 kicks=10 held_in=120633
BRIDGE_METER count=59963 in_window_s=30.0 sample={"peak":0.0,"blocks":2.0,"childPid":20584}
NO_AUDIO_CLEARED reason=caption evidence="tap-silent-desktop window_s=4.0 endpoints=6 peak=1.0"
```

`audio_s=30.0` at every kick is `REDUX_BATCH_PASS_MAX_S` — the pass is always capped, i.e.
the pending queue never drains (`held_in` grows 119717 → 120633 in ~2 min) — and every pass
returns `redux-batch-empty`. The meter says `peak=0.0` throughout: the endpoint is silent
after the device rotation to `soundcore Space Q45`.

## 5. Root cause, localized

* `worker/engine_policy.py:363 run_engine_pass()` loops over the held audio in windows of
  `engine_window_s` (3 s) and calls `sw.engine.transcribe(chunk)` at `:399` **for every
  window, unconditionally**. There is no energy/VAD check anywhere in this path — the live
  path has one (`silent_desktop_hold`, the VAD gate), the batch path has none.
* `worker/engine_switch.py:1511-1539` kicks the pass on an interval whenever the pending
  audio is longer than `REDUX_MIN_AUDIO_S`, **without asking whether that pending audio is
  digital silence**.

Net effect: ten 3 s decodes of zeros every ~5-15 s, 2-4 cores, zero captions, backlog
growing. That is the 17.7 % of machine the DM ranked, and the DM's ranking is right.

## 6. What was dispatched

Lane `BatchSilenceGate` (worker subagent) with the measured brief, own files
`worker/engine_policy.py`, `worker/engine_switch.py`, a new oracle, the battery and the
`AGENTS.md` PIN. Two halves, both required:

1. energy gate at the source in `run_engine_pass` (silent window never reaches
   `transcribe()`; window counted and published once per pass; a quiet-but-real window must
   still decode);
2. the kick side, reusing whatever silence state already exists rather than adding a second
   detector — or a measured "leave it alone" if the gate makes the kick cost nothing.

Declared ceiling for that lane: `python -m watcher run --cpu 40 --io very-low -- …`, one heavy
job at a time; it must not kill or restart pid 25972 (a HIGH-integrity process on the owner's
desktop).

## 7. UNMEASURED

* The **after** number on the owner's live process: a lane may not restart his app, so the
  post-fix cost has to be proven in a controlled worker run over a synthetic silent WAV.
* Whether `session-16`'s four intra-op threads are a second budget or the same two counted
  twice: `redux_live.py:319` forwards `threads` to the export's constructor (`transcribe.py:208`
  sets `intra_op_num_threads` only `if threads`), which explains 2, not 4. Attribution is
  open and named in the lane's acceptance.
* Anything about the shell half of this tree: `LIVE_CODE STALE`, so its code is older than
  the disk by 12 files.

## 8. Retro (one durable change, proven on the failing case)

**Observed**: a decode loop burned 30,45 CPU-s over 30 s of digital silence because the
protection the LIVE path has (`silent_desktop_hold`, the VAD gate) exists in exactly one of
the two paths that decode audio. Cost: 17,7 % of the machine in the episode, the top ranking
in the watcher's DM, and a backlog that grew all afternoon.

**Durable change**: the oracle pair, not another paragraph —
`_main/batch-silence-gate-oracle.py` `VERDICT: PASS (11/11)` and
`--neg-arm: 2/2 mutants caught`, where **M1 is the pre-fix code itself** (call site removed)
and it goes RED on A5/A6/A7/A8. The failing case is the case the gate is proven on; nothing
here is verified by a different case.

**Wiring, checked the house way**: `grep -c 'batch-silence-gate-oracle' _main\_audit-verify-all.cmd`
is 2 (the `:step` and the `:expectred`), so the instrument is reachable from the runner and is
not an orphaned artifact.

**Not claimed**: this retro changes nothing about the second half of the same family — the live
`session-16` 4-thread pool. That one is named in §3/§7 as an open attribution, and it needs its
own lane because capping it touches the live caption path.
