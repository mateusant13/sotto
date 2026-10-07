# Receipt — the three red steps of `_main\_audit-verify-all.cmd`, made honest again

Lane: `receipt-battery-reds`. Date: 2026-10-08. Box: this host, owner's app LIVE
throughout (`pythonw.exe` pid 27492, `H:\sotto\app\webview\sotto_webview.py --log
H:\sotto\_main\webview-run.log --with-worker`, started 05:25:13; plus its worker).
**Nothing was killed, restarted, signalled, or shown on screen. No audio device was
opened. The owner's app was never touched.**

Files this lane owns and changed:

| file | why |
|---|---|
| `_main/verdict-gate.py` | red 1 — the arm table did not provide a counter the predicate reads |
| `_main/history-producer-gate.js` | red 2 — the assertion was unsatisfiable by construction |
| `_main/_audit-hotkey-delivery.py` | red 3 — the instrument could not tell the app's own key from a stranger's |
| `_main/receipt-battery-reds.md` | this file |

Not touched: `worker/**`, `app/**`, `_main/_audit-verify-all.cmd`. The three reds were
fixed in the INSTRUMENT, never by loosening a word the instrument measures.

---

## RED 1 — `python _main\verdict-gate.py` → rc=2

### Before
```
reads    : counters[...] = ['blocks', 'captions', 'chunks', 'music_gated_chunks', 'nonzero_blocks', 'redux_captions', 'resampled_samples', 'vad_gated_chunks']
SETUP ERROR: decide_verdict reads counters['redux_captions'], which this gate's arm table does not provide.
---rc=2
```

### Cause, read from the source (not assumed)
`worker/sotto_worker.py` `decide_verdict` sums the batch engine's counter into the shared
`emitted` (line 2672, current revision 4330 lines):

```python
emitted = counters.get("captions", 0) + counters.get("redux_captions", 0)
```

`redux_captions` is therefore **an input to three predicates**, not a new verdict word:

* `elif counters.get("chunks", 0) == 0 and emitted == 0:` → `buffer-never-reached-chunk-size`
* `elif counters.get("chunks", 0) > 0 and …music_gated… and emitted == 0:` → `captions-all-music-gated`
* `elif emitted == 0 and counters.get("vad_gated_chunks", 0) > 0:` → `captured-signal-has-no-speech`

### Semantics — the question the brief asked, answered explicitly
**`redux_captions` is COUNTED, not NAMED.** It must never influence a verdict word on its
own; there is no `redux-emitting`/`batch-emitted` word and none should be invented, because
"did this run emit captions?" is ONE question with ONE answer and the healthy word
(`captions-emitted`) is what the shells paint as a finish. It DOES change a word — by
stopping a FAILURE word from being emitted for a run that transcribed through the light
path — and that influence is what the new arms pin.

### The fix
1. `HEALTHY` now provides `redux_captions: 0` (the SHIPPED value: with the light path off
   it is always 0, so every pre-existing arm behaves byte-identically to before the key
   existed).
2. Three arms added for the influence itself, at the end of the table as `d1`–`d3`:
   * `d1` `redux_captions=4`, `chunks=0`, every other counter non-zero → **`captions-emitted`**
     (the light path: the app comes up HIDDEN, decodes no 560 ms chunk by design, and
     transcribes over the batch engine — **only the sum** keeps this off
     `buffer-never-reached-chunk-size`).
   * `d2` **`d1` with one counter moved** — `redux_captions` 4 → 0 → the word must go back to
     `buffer-never-reached-chunk-size`. This is the pair that makes the assertion
     non-vacuous: `d1` alone would only prove the sum is read.
   * `d3` `ran_but_silent=True` **while `redux_captions > 0`** → `silent-device`, because the
     MEASURED device fact is tested FIRST and the exit code is built from it
     (`return 3 if ran_but_silent else 0`), so a batch caption may not talk a run out of
     naming a silent device.
3. A fail-closed guard so the answer above cannot rot: if `sotto_worker.py` ever assigns a
   verdict word from `redux_captions` alone (`verdict = …` on a line naming it, without
   `captions-emitted`), the gate raises a SETUP ERROR naming the line instead of silently
   missing a word it has no arm for.
4. A second fail-closed guard, independent of this red: **no arm input may be a key the
   predicate does not read.** An arm whose counter was renamed upstream would otherwise
   PASS while asserting a value it never set. This is checked against the keys the gate
   really extracts from the function.

### After
```
[PASS] d1 redux_captions > 0 alone, chunks == 0 (the light path)
       real = 'captions-emitted'
       want = 'captions-emitted'
[PASS] d2 chunks == 0 AND redux_captions == 0 (the same input, nothing emitted)
       real = 'buffer-never-reached-chunk-size'
       want = 'buffer-never-reached-chunk-size'
[PASS] d3 ran_but_silent=True while redux_captions > 0 (the device word is tested FIRST)
       real = 'silent-device'
       want = 'silent-device'
RESULT (worker/sotto_worker.py (as shipped)): GREEN - 14/14 arm(s)

RESULT: GREEN
---rc=0
```

### Stronger or weaker?
**STRONGER.** All 11 original arms still pass unchanged, three arms were added for the new
counter's influence (including the exact input that flips its outcome back, `d2`), and two
fail-closed checks were added.

### Found on the way: this gate's negative control was silently broken
`--control-unguard-captions-zero` printed `SETUP ERROR: the control arm needs the 'elif
counters.get("captions", 0) == 0: … verdict = "captions-zero"' block …; it is not there`
and exited 2: its regex anchored on a spelling the worker has left behind (the branch is
now `elif emitted <= 0:`). The battery never runs the control, so this had been invisible.
The control now **neutralises** the guard (`elif False:`) instead of deleting a regex-matched
block — deletion cannot be relied on to leave a file that parses, and it re-anchors on the
GUARD itself. Both halves in one command:

```
$ python _main\verdict-gate.py --control-unguard-captions-zero
RESULT (the unguarded COPY (control)): RED - 13/14 arm(s)
CONTROL PASS - arm (b) fails on the copy exactly as it should
RESULT: GREEN (control satisfied: gate RED on the unguarded copy, gate GREEN on the shipped worker)
---rc=0
```

---

## RED 2 — `node _main\history-producer-gate.js` → rc=1

### Before
```
--- the three facts ---
  P (engine hands a producer)      : false
  S (a live source stamps one)     : true   (7 hit(s))
  D (lines that reached the disk)  : 0

INCONSISTENT STATE — the tree and the transcript disagree:
  * a non-test source stamps a producer but the ENGINE meta carries none: … (worker/redux_batch.py:17,189,202; worker/sotto_worker.py:2375,2413)
RESULT: RED — PRODUCER-VERDICT: inconsistent
---rc=1
```

### Cause
The gate replayed **one** stream — the LIVE worker shape, which carries no producer — and
then compared `P = the meta carries a producer` against `S = a source stamps one`. Once the
worker started stamping `producer:"redux"` on its BATCH lines (and the live shape correctly
kept carrying none), that single stream could only ever read `P=false`: the gate was
comparing a fact about ONE shape against a fact about the whole TREE. It was unsatisfiable
**by construction**, and — worse — `D` (lines on disk) had always been 0 because the run it
measured never stamped anything. `verify`ing "the lines reach the transcript" was therefore
never actually measured.

### The fix — three invariants instead of one biconditional
The asymmetry is the owner's law (`_main/_redux-producer-path.js` proves both directions on
the real engine, and MUST stay green: REDUX accepted **1/1**, LIVE refused **0/1** —
re-verified after this change, rc=0). The gate now replays three streams through the REAL
engine → REAL predicate → REAL store, each into its **own** throwaway history root:

| arm | stream | assertion |
|---|---|---|
| **P1** | batch, every fragment `producer:'redux'` | every commit meta carries it, every commit ACCEPTED, and lines on disk `> 0` and `== accepted` |
| **P2** | live, no fragment carries one | no meta carries a producer, NOTHING accepted, disk `== 0` |
| **P3** | one line whose fragments disagree (`redux` vs `live`) | the engine forwards NOTHING (fail-closed), nothing accepted, disk `== 0` |

Verdict: **CONSISTENT iff P1 ∧ P2 ∧ P3.** The old `no-producer-in-tree` shape is GONE — a
gate that can only say yes is worse than none, and emptiness is now RED.

### After
```
  P1 the BATCH tag is forwarded, accepted and reaches the disk
       every commit carries producer="redux" : true
       every commit accepted by the predicate        : true  (1/1)
       disk lines > 0 and equal to the accepted      : true  (1 line(s))
     => P1 : true
  P2 the LIVE shape carries NO producer and cannot reach the disk
       NO commit carries a producer key              : true
       NOTHING accepted by the predicate             : true  (0/1)
       disk lines == 0                               : true  (0 line(s))
     => P2 : true
  P3 a CONFLICTED line is refused at the engine, not at the store
       … => P3 : true

PRODUCER-VERDICT: producer-wired-through
RESULT: GREEN — PRODUCER-VERDICT: producer-wired-through
---rc=0
```

### Stronger or weaker?
**STRONGER, in both directions.** The two regressions this law can suffer are now each
demonstrably caught:

* **DROP** — the engine stops forwarding the tag (the defect `_redux-producer-path.js` ARM B
  measured before the fix). One line of `caption-formulation.js` changed in a scratch copy,
  run through the new `--engine` override: `P1=false`, reasons name it, **rc=1**.
* **INVENT** — the engine mints a tag for a line that never declared one. Shipped as the
  gate's own control `--control-stamp-nvidia`, which had ALSO been broken (see below):
  now **rc=0 with `CONTROL PASS`**, going RED on P1, P2 *and* P3.

Also fixed on the way, because a control that cannot build its mutant reports nothing:

* `--control-stamp-nvidia` used to anchor on the literal `onCommit(line, reason, { … })`,
  which the engine no longer writes (it passes a TERNARY). It exited 2 with
  `SETUP ERROR: … the anchor … is not there`. It now overrides `committedProducer` (one
  function, exactly once in the file) so the mutant pins "the engine declares this producer
  whatever the fragments said" — a **real, placeable, non-canonical** tag.
* Two anchor bugs found and guarded by measurement, recorded in the file: a lazy
  `[\s\S]*?\n\}` stopped at the INNER closing brace of `if (…) return null;` and deleted
  the next **18 430 bytes** of the module (the mutant came out 17 157 B against a 35 525 B
  original and `require`d as an EMPTY namespace → `TypeError: … reading 'ingest'`); and
  every anchor used a bare `\n` while `app/panel/caption-formulation.js` is a **CRLF** file.
  A length-class backstop now refuses a mutant that is not a one-function change.
* A latent trap in the new replay: spreading `producer: undefined` is **not** the live shape
  — the engine reads any string in the field as "this fragment DECLARED a producer"
  (`rememberProducer` → `bufferSawProducer = true`). The key is therefore only set when the
  event names one, so ARM P2 measures the LIVE shape and not an empty string.

---

## RED 3 — `python _main\_audit-hotkey-delivery.py` → rc=1

### Before
```
sotto: HOTKEY_REGISTER_FAILED accelerator=Alt+C winerror=1409
Alt+C register: ready=True registered=False winerror=1409
FAIL Alt+C registers on this box
       real=False want=True
VERDICT: RED — Alt+C registers on this box
---rc=1
```

### Cause
The probe read `RegisterHotKey(Alt+C) → 1409` as a property of the BOX and reported it as a
defect — but the holder was **the owner's own app**: pid 27492 running
`sotto_webview.py --log H:\sotto\_main\webview-run.log --with-worker`, whose own log carried
`HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true thread=7308`. The app
holding the key the owner presses is the app **working**. The instrument could not tell
"taken by a STRANGER" from "taken by the very app we are measuring", which means it was
measuring the probe, not the app.

### The fix — ask WHO holds it, and never pass silently
ARM 1 now asks the OS on **the shell's own hotkey id** (`sotto_webview._HOTKEY_ID` = `0xB0F0`):
`RegisterHotKey` on that id fails with 1409 who ever holds the key, but **nothing but a Sotto
shell ever registers that id**, so 1409 there is attributable. A SKIP requires **both**:

1. the key is HELD on that id, **and**
2. a live Sotto shell exists **and its own log claims THAT EXACT KEY**, written at or after
   that process started (log mtime ≥ process start — so a previous run of the same file
   cannot corroborate).

Otherwise the arm is RED **and names the holder**. A SKIP **never** becomes a pass: the
verdict line is `VERDICT: SKIPPED`, it says in the same breath that *"Alt+C reaches its
handler" is the one claim this run cannot make* and how to get it (close the shell and
re-run) — and if ANY other arm fails, the exit code is 1 regardless.

### After
```
ARM 1 ownership probe: Alt+C held=True winerror=1409 asked on id 0xb0f0
  live Sotto shell pid=27492 log=H:\sotto\_main\webview-run.log last_registered='Alt+C' log_fresh=True

SKIP the Alt+C delivery arm
       SKIP: held by the running Sotto shell pid=27492 — pid 27492 is running and its own log … carries HOTKEY_REGISTERED accelerator=Alt+C … "Alt+C works" is the one claim this run CANNOT make.
…
VERDICT: SKIPPED — every arm that could run held, but this run CANNOT claim "Alt+C reaches its handler"
         skipped: the Alt+C delivery arm
         the fallback chain, the single-instance lock and the toggle rule WERE really exercised above.
         to verify the skipped arm: close the Sotto shell and re-run this probe.
---rc=0
```

The required line is emitted verbatim: `SKIP: held by the running Sotto shell pid=27492`.

### The other arms really ran (they are the half the running app does not block)
`arm_hotkey` walked past the taken bait (`Alt+F9` → `HOTKEY_TRY_FAILED winerror=1409`) and
won with `Alt+Shift+C` (`WARN HOTKEY_FALLBACK requested=Alt+F9 using=Alt+Shift+C`), and the
mutex refused the second holder on a test-only name. All PASS, real values printed.

### Stronger or weaker? — STRONGER, and the SKIP was falsified six ways
This looks like a relaxation, so it was held to a higher bar rather than asserted:

| what was removed | what the probe answered | why that is right |
|---|---|---|
| nothing (real box) | `sotto_owns=True` → SKIP | the app holds Alt+C and says so in its own log |
| the process snapshot finds no shell | `held=True`, `sotto_owns=False` → **RED** | a stranger holding the key is never excused |
| the shell's log FILE is gone | `held=True`, `sotto_owns=False` → **RED** | corroboration is load-bearing |
| the shell's log claims a DIFFERENT key (`Alt+Shift+C`) | `held=True`, `sotto_owns=False` → **RED** | that is the stranger case, exactly |
| a FREE key (`Ctrl+Alt+L`, scratch copy of the audit) | `held=False` → no SKIP: registration + a real `WM_HOTKEY` + the handler toggling all PASS, `VERDICT: GREEN` | the normal path was not broken by the skip |
| the key-probe itself | `key_held('Alt+C')=True` (1409) vs `key_held('Ctrl+Shift+F12')=False` (0) | the probe can say both yes and no |

So the SKIP is conditioned on evidence, and a gate that can only say yes was not created.

---

## The full battery — `cmd /c "H:\sotto\_main\_audit-verify-all.cmd"`

Every step's rc, as the fixed reporter prints them. **All 22 steps rc=0.**

| # | step | rc |
|---|---|---|
| 1 | py_compile sotto_webview.py | 0 |
| 2 | py_compile hot_reload+panel_state | 0 |
| 3 | py_compile sotto_worker.py | 0 |
| 4 | py_compile wasapi_loopback+lang_prompt | 0 |
| 5 | transcript-append-oracle | 0 |
| 6 | live-vs-history-source-oracle | 0 |
| 7 | historico-vs-redux-probe | 0 |
| 8 | **history-producer-gate** | **1 → 0** |
| 9 | panel-state-guard-gate | 0 |
| 10 | **verdict-gate** | **2 → 0** |
| 11 | lane2-reset-probe | 0 |
| 12 | lane3-verdict-probe | 0 |
| 13 | lane4-tap-stop-probe | 0 |
| 14 | audit-history-dead | 0 |
| 15 | worker-start-wiring | 0 |
| 16 | embedded-js-check | 0 |
| 17 | lane1-worker-default-arms | 0 |
| 18 | review-f1f3 | 0 |
| 19 | review-tapstop | 0 |
| 20 | hotkey-registration | 0 |
| 21 | **hotkey-delivery** | **1 → 0** |
| 22 | fresh-processor-probe | 0 |

Non-zero accounting: **there are none.** The three that were non-zero before this lane
(8, 10, 21) are the three fixed above, each with a receipt in its own section. The battery
returns 0 overall because the `.cmd` reports rather than aggregates — each step's rc is read
from the report, never from the batch's own exit code.

`node _main\_redux-producer-path.js` — the sibling the brief requires to STAY green —
re-verified after the changes: `PRODUCER-PATH-VERDICT: GREEN`, REDUX accepted **1/1**, LIVE
refused **0/1**, rc=0.

Compile/parse checks on everything touched: `python -m py_compile` rc=0 on
`_main/verdict-gate.py` and `_main/_audit-hotkey-delivery.py`; `node --check` rc=0 on
`_main/history-producer-gate.js`.

---

## What could NOT be verified

1. **The Alt+C delivery arm itself (registration → real `WM_HOTKEY` → handler → toggle).**
   The owner's app holds Alt+C for the whole session, and this lane may not close it. The
   arm is SKIPPED, not passed. Evidence that it is intact comes from a **scratch copy** of
   the audit pointed at a free key (`Ctrl+Alt+L`, the three registry edits announced in the
   command): `PASS a WM_HOTKEY posted to the hotkey thread is accepted`, `PASS the handler
   ran within 2 s`, `PASS the handler called toggle_panel(reason=hotkey)`,
   `VERDICT: GREEN`. That copy was deleted. **The delivered-on-Alt+C case is unverified until
   someone runs the audit with the app closed.**
2. **Both colours were not obtainable from a single run of red 3.** The RED of ARM 1 cannot
   be produced while the owner's app holds Alt+C, and the SKIP cannot be produced without it.
   The harness the brief points at (`app/webview/run.cmd --with-worker`) starts a second
   shell, which would have been refused the key by the single-instance lock anyway — so the
   RED was demonstrated on a free key and the discrimination was demonstrated by feeding the
   ownership probe its negative inputs. Neither is an end-to-end same-key RED/GREEN pair.
3. **`_main/_audit-verify-all.cmd` still does not aggregate its steps' rc** (it reports each
   one; the batch itself exits 0 even when a step is red — the pre-fix baseline run returned
   0 with three red steps inside). Its reporter fix is correct and landed; making the batch
   fail loudly on a red step is a separate change, and that file is not mine to edit.
4. **`worker/**` was not edited, as instructed.** The `d1`/`d3` semantic claims above are
   therefore asserted **through the gate's arms** (executing the real `decide_verdict`), not
   by an end-to-end run of the batch engine with `redux_captions` actually incrementing. A
   run of the live worker on the light path (`--redux-when-hidden`, app hidden) would close
   that, and it needs the model load and the owner's routing; it was not attempted here.
5. **Two controls were found stale and repaired, but only `--control-unguard-captions-zero`
   and `--control-stamp-nvidia` are exercised here.** Neither is run by the battery, which is
   why both had rotted unnoticed; a future lane should consider putting a control arm into the
   battery rather than leaving it to be run by hand.
