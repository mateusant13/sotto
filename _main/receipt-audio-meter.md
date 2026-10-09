# RECEIPT — the panel's WAVE: a per-window audio level, DEFAULT OFF (task 2)

**Lane:** SottoWordSplit (task 2, after the word split was fixed and reported).
**File changed:** `worker/sotto_worker.py` only — final revision **237 024 B**, sha256
`CEFD18689BD54F681E7F5666437DCECA28E9E61B3F3C41666697E4FD3829BAF1`.
**Not touched:** `app/panel/`, `app/webview/sotto_webview.py` (another lane owns it), the
owner's shell (pid 28428) or worker (pid 29008). **No audio device was opened.**

---

## 0. THE DEFAULT IS OFF — and that is the owner's decision, not a leftover

**An event with no consumer must not be on by default.** The consumer (the `getStats`/`onStats`
member on the shell's bridge) is **another lane's task**; the panel side is already built
(`app/panel/panel.js:1709` → `pushLevel(fields.peak, fields.blocks)`). Until that member exists,
every `meter` event would cost an unthrottled `BRIDGE_UNKNOWN` line in the owner's log — measured by
reading the shell's own code, not by running it:

- `app/webview/sotto_webview.py`, revision 286 151 B, mtime 10:35:58, sha256
  `A7B378F1BFF31A6DAE3C76C69A49FEDBE6A811868A832BB786BD9F246A17855D`:
  `_consume`'s `else` branch at **`:5135-5137`** does `self.malformed += 1` and
  `self.log(f'BRIDGE_UNKNOWN type={kind!r}')`, and `log()` (`:427-438`) **writes and flushes every
  line with no rate limit**. `grep` for `kind == 'meter'`, `getStats`, `onStats` in that file →
  **0 matches**.
- At 10 Hz that is ~10 lines/s ≈ **0.5 KB/s of unbounded growth** in `_main/webview-run.log`
  (already 3.4 MB) plus an ever-climbing `malformed` counter (reported at `:4991`) — for a wave
  nobody can see. That is a leak pretending to be a feature.
- **Turning it on is one flag**, and nothing else has to change:
  `--meter-hz 10` or `SOTTO_METER_HZ=10`.

`METER_HZ = 10.0` (the rate WHEN ASKED FOR) and `METER_HZ_DEFAULT = 0.0` (what ships) are separate
constants, and the oracle reads the shipped default **out of the source**, so a `default=10` slipped
back into argparse is caught by a test rather than by the owner's log.

## 1. What was wrong with the level that existed

| fact | value | source |
|---|---|---|
| the published field | `counters['peak']` = **maximum of the RUN**, only ever rises | contract lane, measured: 3 consecutive ticks printed the same `peak=0.554093` while `rms` drifted 0.06100197 → 0.06181468 |
| the published cadence | **1 point / 10 s** (`--stats-interval 10.0`) | `worker/sotto_worker.py` |
| the tap's own block rate | **10 Hz** (`audio.block_ms: 100`) | `worker/config.json` |
| why not lower the tick | that line is ~600 B → 10 Hz would be **~6000 B/s on the channel that also carries the captions** | the brief |

## 2. The feature — the level of ONE WINDOW, at the tap's own rate

| # | site (final revision) | change |
|---|---|---|
| 1 | `:1309-1332` | the rationale + `METER_HZ = 10.0` / `METER_HZ_DEFAULT = 0.0` |
| 2 | `:1335-1386` | `class AudioMeter` — **pure**: no clock, no I/O, no device. `reset()` clears the window; `tick(block_peak, now)` returns the payload when the window closes |
| 3 | `:2981-2991` | `--meter-hz`, default `METER_HZ_DEFAULT` (0 = off), overridable by `SOTTO_METER_HZ` |
| 4 | `:3554-3583` | construction (`block_s` from `audio.block_ms`) + a one-line announcement on **stderr** (not a new stdout `status`: a new lifecycle token would be painted by the panel as a state it does not name) |
| 5 | `:3585-3588` | `on_block`: the per-block peak `p` is already computed; the meter refuses to let it accumulate and emits `{"type": "meter", "peak": …, "blocks": …}` |

**The window closes on the FIRST of "enough time" and "enough blocks".** That second condition is
not decoration — it is a MEASURED cure:

> **The real live loop, fed from a file (100 ms blocks, 10 Hz time window): 80 blocks produced only
> 48 events over 8 s of audio = 6.0 points/s.** A block landing just before the time boundary makes
> the window swallow two, and the wave silently loses 40 % of its points. With
> `blocks_per_window = round(interval / block_s) = 1`, the same run gives **81 blocks → 81 events =
> 10.0 points/s** (blocks/event 1.00).

**The field is `peak`, not `peak_window`** — a deliberate deviation from the brief's example:
`app/panel/panel.js:1709` does `pushLevel(fields.peak, fields.blocks)`, and its own comment says the
code is built against "`stats.peak` = the level OF ONE WINDOW, plus `stats.blocks`". In a `meter`
event `peak` IS the window level; the RUN maximum keeps its name inside `WORKER_STATS`. A
differently named field would arrive and be ignored. **RAW, not smoothed** — instant attack /
~200 ms release is the panel's job.

## 3. The confirmation the decision asked for — on the REAL live loop, with the new default

`SOTTO_FILE_TAP=_main/pt-br-sample.wav`, `--max-seconds 8 --stats-interval 2`, `block_ms 100`,
**device = `file:pt-br-sample.wav` (no audio device opened)**. Four separate processes:

| arm | `meter` events | stdout bytes | captions | stdout line types |
|---|---|---|---|---|
| **DEFAULT (no flag, no env)** | **0** | 5 071 | 13 | `caption`, `status` |
| `--meter-hz 0` (run #1) | **0** | 5 090 | 13 | `caption`, `status` |
| `--meter-hz 0` (run #2, control) | **0** | 5 091 | 13 | `caption`, `status` |
| `--meter-hz 10` | **81 (10.0/s)** | 8 954 | 13 | `caption`, `status`, **`meter`** |

- **DEFAULT vs `--meter-hz 0`:** 22 stdout lines each, **0 differing payloads** (volatile timing
  fields excluded), captions **byte-identical** (text AND meta), the `meter:` stderr line identical,
  and the same line-type census — **no new type ever reaches the shell**.
- The stdout byte delta is **run-to-run noise, not the meter**: DEFAULT vs OFF#1 = 19 B, and
  **OFF#1 vs OFF#2 = 1 B** — two runs of the *same* arm differ too, in `rss_mb` / `load_s` /
  `infer_wall_s` inside `status` lines that exist in both. **Zero payloads differ in either pair.**
- `--meter-hz 10` still turns it on: 81 events, and its captions are identical to the DEFAULT run's.

## 4. Measured cost WHEN IT IS ON (the brief asked for exactly this)

- **Event size, measured: 47.0 B** (`{"type": "meter", "peak": 0.4213, "blocks": 1}`) → **470 B/s**
  at 10 Hz, against the **~6000 B/s** the 600 B WORKER_STATS line would cost at the same cadence.
  The brief's "≈15 B / 150 B/s" is not reachable with the two named keys the panel reads;
  `emit()`'s default JSON spacing accounts for 6 B of the 47.
- **In the live run:** +3 883 B over 8.1 s = **479 B/s**, 81 events, 75 distinct levels spanning
  0.0 … 0.552 (they rise AND fall — a run maximum cannot).
- **CPU, measured over 100 000 events (≤2 threads, no model, no device):**
  `emit()` format-only **1.90 µs/event → 0.0019 % of one core** at 10 Hz;
  format + write + flush **3.15 µs/event → 0.0032 %**;
  `AudioMeter.tick` **0.08 µs/event → 0.0001 %**.

## 5. The oracle — FOUR colours (one per claim)

`_main/audio-meter-oracle.py` drives the REAL `AudioMeter` (never a copy), counts the bytes that
reach stdout, and reads the shipped `--meter-hz` default **out of the source**. No model, no device,
no window.

```
py -3 _main/audio-meter-oracle.py                 -> 11 PASS / 0 FAIL (11 arms)  VERDICT: PASS  rc 0
py -3 _main/audio-meter-oracle.py --neg-default   -> NEG (default): 2 arm(s) RED as required,
                                                     0 stayed green, 0 control arm(s) broke  PASS
py -3 _main/audio-meter-oracle.py --neg-arm       -> NEG (window):  3 arm(s) RED as required,
                                                     0 stayed green, 0 control arm(s) broke  PASS
py -3 _main/audio-meter-oracle.py --neg-cadence   -> NEG (cadence): 2 arm(s) RED as required,
                                                     0 stayed green, 0 control arm(s) broke  PASS
```

Each claim has its own falsifier, and each goes RED on its own:
- `--neg-default` — the shipped default flipped back to ON. RED: *the shipped `--meter-hz` default
  is 0 (OFF)*; *a run at the SHIPPED DEFAULT emits nothing (0 events, 0 bytes)*.
- `--neg-arm` — the shipped defect (`AudioMeter.reset` no longer clears the peak = a run maximum).
  RED: *the level falls when the audio falls*; *each event reports the peak and count of the blocks
  IT covered*; *a late tick reports its own blocks with no catch-up burst*.
- `--neg-cadence` — the block-count rule removed (a pure time window, the 6 Hz beat). RED: *100
  blocks of 100 ms produce 100 events*; *a tap paced at 99 ms still yields one point per block*.
- Controls green in every colour: `--meter-hz 0` emits nothing at all (0 events, 0 bytes); the
  payload carries exactly `type`/`peak`/`blocks`; the event is compact; the cost is under budget.

## 6. Regressions re-checked on the FINAL revision (237 024 B / `CEFD1868…`)

| instrument | result |
|---|---|
| `_main/word-split-oracle.py` (task 1) | **12 PASS / 0 FAIL**, `--neg-arm` **PASS** (7 RED) |
| `_main/caption-lines-oracle.py` | **12 PASS / 0 FAIL**, rc 0 |
| `_main/verdict-gate.py` (battery step) | **GREEN 14/14**, rc 0 |
| `_main/_audit-fresh-processor-probe.py` (battery step) | **VERDICT: GREEN** |
| `py_compile worker/sotto_worker.py` | rc 0 |
| word-split evidence (`word-split-trace.json`) | re-captured on this revision (`worker_sha256: CEFD1868…`), same chunks, same split |

## 7. What I did NOT prove

1. **The real DEVICE path was not run.** The live loop was exercised through `SOTTO_FILE_TAP`, the
   same `on_block` → `asr_thread` → stats path with the tap replaced by a file — but a real
   endpoint's block cadence and jitter are its own. `blocks_per_window` is recomputed from
   `audio.block_ms`, the same value the tap is built with; that is an argument, not a measurement.
2. **The shell hazard in §0 was read, not run** (single-instance lock; it is the owner's live app).
3. **No long run.** 8 s only; the log-growth figure is linear arithmetic from the measured event
   rate.
4. **Smoothing is absent by design** — the panel owns it. If the panel lane expected a smoothed
   level from the worker, the wave will look spiky.
