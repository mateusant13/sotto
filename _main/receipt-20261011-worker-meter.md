# Receipt — the owner's panel gets its live level meter ("the wave")

Lane: worker meter (one producer, one consumer contract). Date 2026-10-11 (America/Sao_Paulo).
Owner order in force: **Sotto was NOT launched** — no shell, no worker, no probe, no
`_main\_audit-verify-all.cmd`. Every number below comes from bytes, from an in-process import, or
from an oracle that spawns a child Python. No visible console was opened (every child was spawned
with Node `spawnSync` + `windowsHide: true`, `TMPDIR=I:\cc-tmp`).

---

## 1. What was broken, and what now ships

The worker is the only producer of a level stream, and it never emitted one: the panel's bars were
drawn from the `WORKER_STATS` line on stderr, whose `peak` is the **running maximum of the whole
run** — a staircase that only rises and then flattens. That is the defect the owner reported, and it
is named in the shell's own docstring (`_meter`, below).

Three files, exactly as the write scope allowed:

| file | role |
|---|---|
| `worker/sotto_worker.py` | the meter is now INSTANTIATED on the live audio path and emitted once per window |
| `_main/meter-chain-oracle.py` | NEW — gates the producer, the shape, and both consumers; `--neg-arm` runs two mutants |
| `_main/receipt-20261011-worker-meter.md` | this file |

---

## 2. Pins (bytes, sha256, mtime — measured, not remembered)

Instrument: Node `fs.readFileSync` + `crypto.createHash("sha256")` over the same bytes.

**Touched by this lane:**

| file | bytes | sha256 | mtime (UTC) |
|---|---|---|---|
| `worker/sotto_worker.py` (SHIPPED) | 304762 | `771ACA94AB3E3B3AD37498CA28881E96B27C4045E3046B386E1781DBF45CEB7A` | 2026-10-11T23:09:27.486Z |
| `_main/meter-chain-oracle.py` (NEW) | 38941 | `163410F7D21D65116E74AD4A5A3D61943E442F6EA78BDF4B9DFB0A0ED840928A` | 2026-10-11T23:17:19.411Z |

`worker/sotto_worker.py` line endings: **5832 CRLF / 0 bare LF** (`node` census on the bytes), and
the diff against HEAD proves the property line by line: `git diff -- worker/sotto_worker.py` returns
**148 added / 9 removed** lines, and **all 148 added lines are found in the file followed by CRLF**
(0 missing, 0 bare LF). The file is 8895 B larger than the 295867 B baseline measured when this lane
opened it (that revision already carried other lanes' work — the worker has moved 291873 → 295867 →
304762 B across lanes today; AGENTS.md rule 2).

**Read but NOT modified by this lane** (pins taken from the same bytes the oracles read):

| file | bytes | sha256 | mtime (UTC) |
|---|---|---|---|
| `app/webview/sotto_webview.py` | 440186 | `4295AEABED6727721A125C2CE2E9F87658C6107BC756309D1BF9FE40E2320822` | 2026-10-11T22:42:49.555Z |
| `app/panel/panel.js` | 138379 | `A14C0A96E69F759E2584BA0DB1B781B36E3F97DE00AA7989E3B9F8804ABCFC7F` | 2026-10-11T22:53:57.474Z |
| `_main/audio-meter-oracle.py` (pre-existing gate) | 18330 | `72942D49D7F241377915389BE1A2AD7C3272E8F110FD8CBD98EE5EACD011644A` | 2026-10-11T22:15:13Z |

`git status --porcelain` at the end of the lane: ` M worker/sotto_worker.py`, `M app/panel/panel.js`
(another lane's edit, not mine — I never wrote that file), `?? _main/meter-chain-oracle.py`.

---

## 3. The chain, with the anchors as measured on the pins above

**Producer (mine).** `worker/sotto_worker.py`

* `:4146-4161` — the rate rung: `--meter-hz` (recorded by `MeterHzFlag`, `:1341-1356`, see §4) > `SOTTO_METER_HZ` >
  `METER_HZ`, with a negative rate refused loudly and read as **OFF**.
* `:1359-1390` — `class AudioMeter` (declared at line 1359); `def __init__(self, hz=METER_HZ, now=0.0, block_s=0.0)` at 1367;
  `blocks_per_window = max(1, int(round(interval/block_s)))` when a block period is supplied.
* `:1396-1438` — `tick()`: closes a window on **ENOUGH TIME _or_ ENOUGH BLOCKS** (the predicate is at
  1424-1425), emits `peak` + `blocks` (1427), and steps `next` FORWARD from `now` (1435-1437 — no
  catch-up burst).
* `:4663` — `meter = AudioMeter(meter_hz, now=time.time(), block_s=block_ms / 1000.0)`, the ONE
  construction site in the file (AST count = 1), on the live audio path.
* `:4705-4747` — in `on_block` (declared at 4705), the per-block peak `p` the tap ALREADY computes
  (line 4709, no second audio read) feeds `meter.tick(p, time.time())` (4745), and a closed window is
  published with `emit(type="meter", **level)` (4747), behind `if meter.enabled:` (4744).

**Consumer A — the shell (`app/webview/sotto_webview.py`, not mine):**

| anchor | line | text |
|---|---|---|
| dispatch | 7475 | `elif kind == 'meter':` |
| forward | 7476 | `self._meter(message, child)` |
| handler | 7395 | `def _meter(self, message, child=None):` |
| fields it copies | 7419 | `for key in ('peak', 'blocks'):` |
| freshness gate | 672 | `METER_FRESH_S = 2.0` |
| preference over the run maximum | 5863-5872 | the meter sample wins while fresh, else the stats line |

**Consumer B — the panel (`app/panel/panel.js`, not mine):** `function pushLevel(peak, blocks)` `:2564`,
called as `pushLevel(fields.peak, fields.blocks)` `:2647` inside `wireLevel()` `:2633`.

**The contract, as read out of BOTH consumers' own bytes:** `{"type":"meter","peak":<float>,
"blocks":<int>}` — nothing else. My oracle asserts the union across producer/shell/panel, and that the
producer's key set is exactly the fields both consumers name (`peak`, `blocks`).

---

## 4. The rate: `--meter-hz` > `SOTTO_METER_HZ` > default 10.0, and 0 = OFF

WHY AN ARGPARSE ACTION AND NOT A SENTINEL. `--meter-hz` must keep the literal `default=METER_HZ` in
`add_argument` — the pre-existing gate `_main/audio-meter-oracle.py` reads the default OUT OF THESE
BYTES with a regex (`shipped_default_hz`, arm 1) — so the parsed value cannot tell "the operator asked
for 10" from "nobody asked". `class MeterHzFlag(argparse.Action)` sets `meter_hz_given` beside the
value, and the rung decides on THAT. Consequence, measured: an explicit `--meter-hz 10` beats
`SOTTO_METER_HZ=4`, which a value-based rung (`if args.meter_hz != METER_HZ`) would silently lose.

**Evidence — real argparse, real rung, in process (`py -3 -c`, spawned from Node):**

```
===== IN-PROCESS IMPORT + RATE RESOLUTION (via Node spawnSync)  rc=0
import sotto_worker: OK H:\sotto/worker\sotto_worker.py
METER_HZ = 10.0
default (no flag, no env)       -> (10.0, 'default')
env SOTTO_METER_HZ=4            -> (4.0, 'env')
flag --meter-hz 5, env 4        -> (5.0, 'flag')
flag --meter-hz 0 (OFF)         -> (0.0, 'flag')
flag --meter-hz 0, env 4        -> (0.0, 'flag')
flag --meter-hz 2.5             -> (2.5, 'flag')
flag --meter-hz -3 (refused)    -> (0.0, 'flag')
AudioMeter signature: (self, hz=10.0, now=0.0, block_s=0.0)
--meter-hz 0 meter enabled = False tick = None
```

The same nine cases are gated inside `_main/meter-chain-oracle.py` arm 1 (11 checks), including the
`--meter-hz 10` case above.

---

## 5. One event per window, in the shape the consumer reads (criterion 2 and 3)

The meter closes a window on `now >= next` and emits exactly what `_meter` copies. Arm 5 drives the
REAL class out of the shipped bytes and captures the REAL `emit` payloads:

```
[PASS] check: every emitted line carries exactly type/peak/blocks (no third field)
       keysets=[('blocks', 'peak', 'type')]
[PASS] check: the event type is the literal string 'meter'
       types={'meter'}
[PASS] check: peak travels as a JSON FLOAT and blocks as a JSON INT
       first='{"type": "meter", "peak": 0.3, "blocks": 2}'
[PASS] check: one line per event, and every line is valid JSONL on its own
       lines=11 newline_terminated=True
```

---

## 6. Cadence: the off-by-one is fixed, and it is fixed ON THE LIVE SHAPE

### 6.1 What the defect was

The committed `AudioMeter` closed a window on TIME ALONE, so a tap paced at exactly the window period
lost one event per run (the boundary tick falls a hair early and is skipped): 100 blocks of 100 ms
produced **99** events — and at a 99 ms pace the same rule beat down to ~6 Hz. The class's own
committed revision in `_main/_redux-gate-mutants/env-optin.py` carries the cure (a block-count arm + a
`block_s` argument); the working tree had lost it.

### 6.2 The cure

`AudioMeter.__init__(..., block_s=0.0)` computes `blocks_per_window` from the tap's own period, `tick`
closes on **enough time OR enough blocks**, and `next` advances from `now` so a late tick cannot emit a
catch-up burst. The live call site passes the period it actually has:

```
meter = AudioMeter(meter_hz, now=time.time(), block_s=block_ms / 1000.0)
```

### 6.3 Measured

```
[PASS] check: 100 blocks of 100 ms produce 100 EVENTS on the live shape (not 99)
       events=100 (the pre-existing gate measures 99 here)
[PASS] check: ...and every one of those events covers exactly one block
       blocks=[1, 1, 1, 1, 1, 1]        (first six of 100; all 1)
[PASS] check: ...and every block lands in some event (none is lost)
       sum(blocks)=100 over 100 events
[PASS] check: a 99 ms pace still yields one point per block (no ~6 Hz beat)
       events=100 over 9.80 s = 10.20 Hz
[PASS] check: with NO tap period the meter is pure-time (so the rule is the fix)
       pure-time events=99, first window blocks=2: a driver that does not forward block_s
       measures 99, not the shipped 100
[PASS] check: at 5 Hz over 100 ms blocks the meter emits one event per 2 blocks
       events=10 blocks=[2, 2, 2, 2, 2, 2, 2, 2, 2, 2]
[PASS] check: a tick exactly ON the boundary closes the window (99 -> 100 fix)
       tick@0.10={'peak': 0.5, 'blocks': 3}
[PASS] check: a LATE tick reports its own blocks and emits NO catch-up burst
       tick@0.25={'peak': 0.4, 'blocks': 1} tick@0.26=None
```

The pure-time contrast line is the proof that the block arm — not a tightened comparison — is what
moves 99 to 100: the SAME class, driven without a period, still measures 99.

### 6.4 The pre-existing gate `_main/audio-meter-oracle.py` — RED, and NOT edited (OPEN GAP)

Command and real output (rc=1):

```
py -3 _main/audio-meter-oracle.py
[FAIL] arm: 100 blocks of 100 ms produce 100 events (10 Hz, the tap's block rate)
       got  = (99, 9.9)
       want = (100, 10.0)
[FAIL] arm: a tap paced at 99 ms still yields one point per block (no 6 Hz beat)
       got  = (98, 9.9)
       want = (100, 10.1)
 meter-oracle: 9 PASS / 2 FAIL      (VERDICT: FAIL, rc=1)
```

**Why it is still red, measured rather than guessed.** Its driver `stream()`
(`_main/audio-meter-oracle.py:124`) constructs `W.AudioMeter(hz, now=0.0)` and **does not forward
`block_s`** — the comment at `:118-123` says so on purpose ("a driver that forwarded it would hide
the very defect this arm measures"). So its two cadence arms drive a PURE-TIME meter, while the live
call site is not pure-time. Its two arms are also mutually unreachable: arm 3 (`:241-247`) requires
`tick(p, 0.0)` to return **None** (the first tick must be silent) and arm 5 wants **100** emissions
from 100 ticks at t = 0.0…9.9 — 100 ticks give at most 99 emissions if the first is silent, and 100
requires emitting AT t=0.0, which arm 3 forbids. No per-tick-emitting meter can satisfy both, so this
gate cannot go green without editing it, and editing it is outside this lane's write scope
(three files, measured). **It was NOT weakened and NOT touched**: `git status` shows it unmodified,
and its own `--neg-cadence` mutant still runs.

```
py -3 _main/audio-meter-oracle.py --neg-cadence
NEG (cadence): 2 arm(s) of this claim went RED as required, 0 stayed green (must be 0),
               0 control arm(s) broke (must be 0)
VERDICT: PASS
```

(That PASS is partly tautological today — the 2 arms it demands RED are already RED in the base run.
It is reported for completeness, not as evidence of the fix.)

**What a next lane must do (exact fix, not done here):** in a copy of
`_main/audio-meter-oracle.py`, forward the tap period from `stream()` — `W.AudioMeter(hz, now=0.0,
block_s=dt)` — and re-baseline the two arms, accepting `blocks==1` per event at a 100 ms pace. Do not
touch it from this lane: `_main/meter-chain-oracle.py` already gates the same property on the LIVE
shape and its `--neg-arm` proves those arms can say NO.

---

## 7. `--meter-hz 0` DISABLES the stream (criterion 4) — and how byte-identity was verified

WHAT "BYTE-IDENTICAL" MEANS HERE. With the meter off, the worker must write the same bytes it wrote
before the feature existed: nothing read, nothing emitted, no extra line. Verified as a triple, all
measured:

1. **The switch is the only thing added to `on_block`, and it wraps everything that reads or writes.**
   AST over the shipped bytes: `on_block` has exactly ONE top-level `If` whose test mentions the meter,
   and its body contains both the `tick` and the `emit`:
   ```
   [PASS] guards=['p > counters["peak"]', 'p > device_peak["value"]', 'p > 1e-4', 'meter.enabled']
   [PASS] the guard wraps the tick AND the emit (nothing runs when OFF)
   [PASS] the meter adds exactly ONE top-level branch; the three peak branches on_block
          already had are untouched
          top-level on_block statements=['AugAssign', 'AugAssign', 'AugAssign', 'Assign',
                                         'If', 'If', 'If', 'AugAssign', 'Try', 'If']
   ```
   (the three pre-existing `If`s are the peak/device-peak updates; the last `If` is `meter.enabled`.)
2. **The switch is closed.** Rate 0 (and a negative rate, refused to 0) makes `AudioMeter.enabled`
   False and `tick` returns None:
   ```
   [PASS] rate 0 constructs a meter that is DISABLED (enabled is False)
          enabled=False interval=0.0 tick=None
   [PASS] a negative rate is disabled too (never a negative interval)
   ```
3. **Driving the REAL `on_block` with the meter OFF produces ZERO events, and the SAME harness with it
   ON does produce them** (so the zero is the guard, not a harness that cannot emit at all):
   ```
   [PASS] driving the REAL on_block with the meter OFF writes ZERO events      events=[]
   [PASS] ...and the meter it built is DISABLED (enabled is False, interval 0)
   [PASS] the SAME harness with the meter ON does emit (the control for the zero)
          events=[{'type': 'meter', 'peak': 0.0, 'blocks': 2},
                  {'type': 'meter', 'peak': 0.0, 'blocks': 1}]
   ```
   The harness is the real function: `on_block` is extracted from the live bytes, assembled with the
   real class and the real `emit`/`counters`/`audio_q`, and called with real float32 numpy blocks.

**What this does NOT prove — see §10.** It is not a byte-diff of two real worker runs (impossible
under the owner's no-launch order). The claim it supports is exactly: with the rate at 0 the meter
reads and writes nothing, and no other statement was moved or added.

---

## 8. No per-block log line (criterion 5)

```
[PASS] check: the meter branch writes ONE event per window and NO log line
       emit(=1 err(=0 print(=0 stderr=0
```

Read on the AST source segment of the guarded branch: one `emit(` call, zero `err(`, zero `print(` and
no `sys.stderr` write. The branch runs at most once per window (10 Hz by default), never per block and
never per sample; the event itself measures 47.0 B (`{\"type\": \"meter\", \"peak\": 0.4213, \"blocks\": 1}`
+ newline), ≈470 B/s at 10 Hz, against the 6000 B/s the WORKER_STATS tick would add at the same
cadence — both printed by the pre-existing gate's own budget arm.

---

## 9. The gate battery (every command actually run, real rc)

| command | result |
|---|---|
| `py -3 -m py_compile worker/sotto_worker.py` | **rc=0**, no output |
| `py -3 _main/meter-chain-oracle.py` | **rc=0** — `55 PASS / 0 FAIL (55 checks)`, `VERDICT: PASS` |
| `py -3 _main/meter-chain-oracle.py --neg-arm` | **rc=0** — `66 PASS / 0 FAIL`, two mutants RED, live control GREEN |
| `py -3 _main/audio-meter-oracle.py` | rc=1 — `9 PASS / 2 FAIL` (pre-existing; §6.4) |
| `py -3 _main/audio-meter-oracle.py --neg-arm` | **rc=0** — `NEG (window): 3 arm(s) … went RED as required … VERDICT: PASS` |
| `py -3 _main/audio-meter-oracle.py --neg-cadence` | **rc=0** — `VERDICT: PASS` (tautological today; §6.4) |
| `py -3 _main/per-app-source-plumbing-oracle.py` | **rc=0** — `VERDICT: PASS` |
| `py -3 _main/app-target-oracle.py` | **rc=0** — `VERDICT: PASS  live=GREEN(9/9)  M1 env line removed=RED-as-expected(['d'])  M2 tree-root rule removed=RED-as-expected(['b'])` |
| `py -3 _main/canonical-producer-oracle.py` | **rc=0** — `SUMMARY: 47/47 checks green; failed=[]`, `VERDICT: PASS` |
| `py -3 _main/redux-arm-weights-oracle.py` | **rc=0** — `GREEN ARM SUMMARY: 20/20 checks green; red=[]`, `VERDICT: PASS` |
| `py -3 _main/redux-arm-weights-oracle.py --neg-arm` | **rc=0** — `VERDICT: PASS` (4 mutant arms, control comment-only arm moves nothing) |

No oracle went RED because it pins the worker's byte count or sha256 — but note that THREE of them DO
pin the worker's bytes, and they were re-run AFTER the last edit to the worker:
`redux-arm-weights-oracle.py` prints `PIN worker/sotto_worker.py bytes=304762 sha256=771ACA94…`,
`canonical-producer-oracle.py` prints `PIN H:\sotto\worker\sotto_worker.py 304762 B sha256 771ACA94…`,
and my own oracle prints the same. All three are green on the same pin, so the pin is consistent at the
moment of writing.

### 9.1 The new gate, in full (green)

```
=== meter-chain-oracle (green) rc=0
== ARM 1: the RATE -- flag > env > default, and 0/negative = OFF ==
== ARM 2: the CADENCE -- one event per window, and no burst ==
== ARM 3: the WORKER wiring -- the meter is DRIVEN from the live path ==
== ARM 4: --meter-hz 0 is BYTE-IDENTICAL -- the emit is dead when OFF ==
== ARM 5: the SHAPE -- exactly the fields the CONSUMERS read ==
== ARM 6: the SHELL consumes kind 'meter' and reads peak/blocks ==
== ARM 7: the PANEL pushes the level and reads peak/blocks ==
== ARM 8: the TWO consumers agree on the field names ==
meter-chain-oracle: 55 PASS / 0 FAIL (55 checks)
VERDICT: PASS
```

(The full per-check output — 138 lines — was captured to `I:\cc-tmp\meter-chain-green.txt`; the
decisive lines are quoted throughout this receipt. Elided only there: the long `peaks=[…]`, `out=[…]`
and `tally=[…]` payload dumps of arm 2, which are verbatim identical to the payload lists printed by
the pre-existing gate.)

### 9.2 The `--neg-arm`: two mutants, both colours

```
py -3 _main/meter-chain-oracle.py --neg-arm         (rc=0, 70 s)
== NEG ARM: the same oracle against TWO mutated copies ==
-- CHILD (mutant=emit) rc=1
  child FAILED check names for emit (5): on_block drives exactly ONE meter tick; on_block emits
  exactly ONE event; the emit sits behind a meter.enabled guard (the --meter-hz 0 contract); the meter
  adds exactly ONE top-level branch; the three peak branches on_block already had are untouched; the
  SAME harness with the meter ON does emit (the control for the zero)
-- CHILD (mutant=cadence) rc=1
  child FAILED check names for cadence (4): 100 blocks of 100 ms produce 100 EVENTS on the live shape
  (not 99); ...and every one of those events covers exactly one block; a 99 ms pace still yields one
  point per block (no ~6 Hz beat); at 5 Hz over 100 ms blocks the meter emits one event per 2 blocks
-- CHILD (live bytes (control)) rc=0
meter-chain-oracle: 66 PASS / 0 FAIL (66 checks)
VERDICT: PASS
```

Mutant A (`emit`) replaces the guarded branch of `on_block` with `pass` IN A COPY built from the AST —
the producer is deadened. Mutant B (`cadence`) removes the block-count arm of `tick`'s predicate in a
copy — the cadence rule is removed while `blocks_per_window` is still computed and the live call site
still passes the period. Each mutant is compiled, imported and run as a child process; the child must
exit non-zero AND name the right checks, and the SAME child against the untouched bytes must be GREEN.
That last line is what makes the two reds attributable to the mutations and to nothing else.

---

## 10. NOT MEASURED (explicit gaps)

1. **No real worker run, and therefore no live wire.** The owner forbade launching Sotto; the meter's
   bytes were never observed arriving at a real shell over a real stdout pipe, and the panel never
   painted a wave from them. Everything above is static + in-process. What would measure it:
   `py -3 worker/sotto_worker.py --selftest --audio <file> --meter-hz 10` piped into the shell's
   `_consume` — both forbidden today.
2. **`--meter-hz 0` byte-identity is proven structurally and behaviourally, not by diffing two real
   runs.** See §7 for exactly what is proven.
3. **The real tap period was not measured.** `block_ms / 1000.0` is the period the config declares
   (`audio.block_ms`); whether the live tap actually delivers a block every `block_ms` on this host
   (stalls, WASAPI re-clocking, process-loopback jitter) was not measured, because that needs a live
   tap. If the tap delivers SLOWER than `block_ms`, the block-count arm cannot fire early and the meter
   falls back to the time rule — the pre-existing behaviour — which is the safe direction.
4. **The panel's drawing was not measured.** `pushLevel` was only read, never executed.
5. **The two arms of `_main/audio-meter-oracle.py` were left RED on purpose** (§6.4). Until a lane
   re-baselines that gate, `py -3 _main/audio-meter-oracle.py` exits 1. That is a REPORTED, EXPLAINED
   red — not a silent one.
6. **`SOTTO_METER_HZ` is read AFTER argparse, so a shell that passes `--meter-hz` on the command line
   still lands the flag before the script path** (the shell spawns `python [...extraArgs, script]`),
   which is exactly why the env rung exists. That the shell's own spawn line has not changed was NOT
   re-verified by me beyond reading `sotto_webview.py`'s spawn call; no launcher was run.

---

## 11. Reproduce

```
set TMPDIR=I:\cc-tmp
py -3 -m py_compile worker/sotto_worker.py
py -3 _main/meter-chain-oracle.py                 # 55 PASS / 0 FAIL, rc=0
py -3 _main/meter-chain-oracle.py --neg-arm       # 66 PASS / 0 FAIL, rc=0, 2 mutants RED
py -3 _main/audio-meter-oracle.py                 # 9 PASS / 2 FAIL, rc=1  (see `6.4)
py -3 _main/audio-meter-oracle.py --neg-arm       # VERDICT: PASS, rc=0
py -3 _main/per-app-source-plumbing-oracle.py     # VERDICT: PASS
py -3 _main/app-target-oracle.py                  # VERDICT: PASS
py -3 _main/canonical-producer-oracle.py          # 47/47, VERDICT: PASS
py -3 _main/redux-arm-weights-oracle.py           # 20/20, VERDICT: PASS
py -3 _main/redux-arm-weights-oracle.py --neg-arm # VERDICT: PASS
```

Every one of those was run from `H:\sotto` through Node `spawnSync('py', ['-3', …],
{cwd: 'H:/sotto', windowsHide: true, maxBuffer: 64 MiB, env: {TMPDIR: 'I:\\cc-tmp'}})`.


---

## ADDENDUM 2026-10-11 (Lead, after this receipt was written)

1. **The RED this receipt reported in section 6.4 is CLOSED, with the fix it prescribed.**
   `_main/audio-meter-oracle.py` now forwards the block period --
   `m = W.AudioMeter(hz, now=0.0, block_s=block_s)` -- and the comment above it, which said the
   shipped class had "no \`block_s\` parameter, no \`blocks_per_window\`", was replaced by the
   measurement that falsified it (`def __init__(self, hz=METER_HZ, now=0.0, block_s=0.0)` at
   `:1367`, `blocks_per_window` at `:1388-1389`, live call site `:4663`). Re-run by the Lead in
   three modes: default **11 PASS / 0 FAIL, VERDICT: PASS, rc=0** (it was 9 PASS / 2 FAIL rc=1);
   `--neg-arm` -> "3 arm(s) of this claim went RED as required", VERDICT: PASS, rc=0;
   `--neg-cadence` -> "2 arm(s) of this claim went RED as required", VERDICT: PASS, rc=0 -- and
   that last mode passed only TAUTOLOGICALLY before, exactly as this receipt said it did.
   The pure-time shape is still exercised deliberately: arm 3 builds the meter WITHOUT the block
   period, and `--neg-cadence` removes the rule and requires the cadence arms to fail.
2. **`app/panel/panel.js`'s comment was updated for the same reason.** It said the missing half
   was the producer; it now names the shipped producer (construction `:4663`, tick `:4745`,
   emit `:4747`, rate rung, `--meter-hz 0` inert) and repeats the honest half this receipt
   already carries: THE WIRE HAS NEVER BEEN EXERCISED end to end under the owner's stop order.

**NOT MEASURED, unchanged by this addendum:** nothing was launched; no real worker run, no real
wire, no painted bar. The `--meter-hz 0` byte-identity remains structural + behavioural, exactly
as this receipt states.


---

## NOTA TARDIA — 2026-10-11 (Lead): a revisao do worker andou DEPOIS deste recibo

O recibo acima fixa `worker/sotto_worker.py` em **304 762 B / sha256 `771ACA94…`** — a revisao que
a lane entregou e que este recibo mede. Desde entao o MESMO ficheiro mudou outra vez, e por trabalho
que tambem e medido:

* `c515cd7` (auditoria, linha #9B) — o tap passou a CONTAR `AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY`
  nos DOIS loops de pacotes (`wasapi_loopback.py` e o loop PLP dentro de `sotto_worker.py`), com
  `disco_packets=` na linha `TAP_STALLED`. O ramo do medidor deste recibo nao mudou: `AudioMeter`,
  a construcao em `:4663`, o `on_block`/emit continuam a ser o que aqui esta medido, apenas
  deslocados pelas linhas novas.
* O gate desta classe existe agora e corre sem lançar nada:
  `py -3 _main/stale-receipt-oracle.py` compara o relogio de cada artefacto com o das suas fontes e
  DECLARA o STALE em vez de o deixar ser lido como corrente. A primeira corrida dele marcou ESTE
  recibo como `STALE age_s=224.4` — 224 s mais velho que o worker que descreve — e esta nota e a
  correcao: a parte acima continua verdadeira para a revisao que mediu, e a revisao corrente e
  maior. **Nao re-medido aqui:** os numeros do medidor (55 checks, cadencia, `--meter-hz 0`) contra
  a revisao NOVA do worker; o que se afirma e a procedencia, nao uma re-medicao.
