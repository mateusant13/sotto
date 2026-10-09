# RECEIPT — the live word split (PART A) and the panel's wave (PART B)

**Lane:** SottoWordSplit · **Date:** 2026-10-08
**Worker:** `worker/sotto_worker.py` — final revision **237 489 B**, sha256
`29E4CBFA71C1AC6DE5FA1C051C0FFFD63B1BC28E6AE214D52FC27AAE56380EA9`.

**PART A (the word split on the live path) wrote NO production code**, because measurement showed
there was nothing to write: the live emitters already carry `chunk_is_continuation`/`join_fragments`.
See §5 for why that is a finding and not an omission. **PART B (the wave) changed exactly one
constant** — `METER_HZ_DEFAULT`, `0.0` → `10.0` — and is §8 onwards.

---

## 0. THE ANSWER, IN THE TWO LINES THAT WERE ASKED FOR

**The live path DOES pass `continues=True`** — measured on the real live loop, 11 of 47 pushes, and
all 11 seams glue correctly. The hypothesis that the live path never passes it is **refuted by
measurement, not by reading**.

**The owner is still running PRE-FIX code.** His worker, pid 29008, was spawned at log line 26978
(08:01:56) and has never been restarted; the captions he pasted are at log lines 33465-33473 of the
SAME log. A Python process reads its source once, at import. **The shell detected my edits 20 times
and held every one of them** (`HOT_RELOAD_WORKER_DEFERRED … reason=capturing -- applies at the next
boundary`, 20 queued / 20 deferred / **0 applied** / 0 respawns since that pid started).

## 1. The instrument that does not need the audio device

`_main/live-seam-probe.py` runs the **real live loop** — `main()` → `asr_thread` → `drain` →
`finalise` → `rerun` — with `SOTTO_FILE_TAP` swapping the device ladder for a file
(`file_tap_candidate`, `sotto_worker.py:3331-3341`). The tap delivers blocks on a wall-clock
schedule exactly as a device callback does. It spies on `LineFormer.push` and on `emit`, and records
for every fragment: the text, the `continues` verdict, the line before, the line after.

**The owner's pid 29008 holds the endpoint, so no device was opened.** What is missing versus a
device arm is the endpoint's own block cadence and jitter — not the live code path, which is the same
code.

## 2. The live path passes `continues=True` (the question, answered by counting)

```
GREEN (shipped join_fragments)   continues=True seen: 11 of 47 pushes
RED   (pre-fix body, --neg-arm)  continues=True seen:  9 of 47 pushes
```

Every one of the 11 was checked individually: `line_after == line_before + text`, **0 of 11 spaced**.
The verdicts are real and they are spent:
`an`+`ced`, `Mon`+`e`, `Resident`+`s`, `Alterna`+`tive`, `Clo`+`sed`, `Clo`+`sed`, `Radio`+`an`… —
each a word the pre-fix code would have cut in half.

The count differs between the colours (11 vs 9) for a reason worth knowing: the `max_chars` cap
lookahead calls `join_fragments`, so changing the join changes when a line closes, which changes when
`_words` is empty, which changes `cont = bool(continues) and bool(self._words)`. The two colours are
not the same run with one function swapped — they are two different line histories. That is the
correct behaviour of the fix, not noise.

## 3. The TWO COLOURS on the LIVE path — same clip, same loop, same 14 s

`_main/en-us-sample.wav`, `_main/live-seam-two-colours.py`:

| | closed line |
|---|---|
| **GREEN** (shipped) | `'The Radio anced that the bridge over the river will be closed next Mone.  Residents need'` |
| **RED** (pre-fix body) | `'The Radio an ced that the bridge over the river will be closed next Mon e .  Resident'` |
| **GREEN** | `'Alternative route to get to work the radio announced that the bridge over the river'` |
| **RED** | `'an alternative route to get to work .  The Radio announced that the bridge over'` |

The RED line contains **exactly the owner's pattern**: `an ced`, `Mon e`, `.  Resident` cut. **39
fragments differ between the two colours**, every one of them in the direction of GREEN gluing.

## 4. The owner's own strings, through the REAL `LineFormer` + `join_fragments`

| fragment A | fragment B | `continues=True` | `continues=False` | the pre-fix body gives |
|---|---|---|---|---|
| `lan` | `e` | **`lane`** | `lan e` | `lan e` |
| `Tor` | `nado` | **`Tornado`** | `Tor nado` | `Tor nado` |
| `winn` | `able` | **`winnable`** | `winn able` | `winn able` |
| `tow` | `s` | **`tows`** | `tow s` | `tow s` |
| `he` | `'s` | **`he's`** | `he 's` | `he 's` |
| `an` | `other` | **`another`** | `an other` | `an other` |
| `damage he` | `'s gonna go for an` | **`damage he's gonna go for an`** | `damage he 's gonna go for an` | `damage he 's gonna go for an` |
| `gonna go for an` | `other golem` | **`gonna go for another golem`** | `gonna go for an other golem` | `gonna go for an other golem` |

**`he 's` is DECIDED by the vocabulary, and this is not a guess.** The whole 13 088-token vocabulary
contains **exactly one** token with an apostrophe — `'`, id **2775** — and there is **no `▁'` token at
all**. So a chunk that begins with `'` can never carry a word-start marker,
`chunk_is_continuation` always returns True, and the shipped code **always glues it** while the
pre-fix code **always spaced it**. `he 's` is a pre-fix seam, full stop.

**`an other` is NOT decided, and I will not pretend otherwise.** `▁other` (id 2979) exists alongside
`other` (id 2902), so the model may legitimately have chosen a word start; only the owner's audio can
settle it. Same for `e` (`▁e` = 1281 exists) and `s` (`▁s` = 260 exists) — the fragments in `lan e`
and `tow s` have marked forms, so **which** token the model picked decides it. The fragments that are
decided are `able` (no `▁able`), `lan` (no `▁lan`), `nado`/`winn`/`tow` (not single tokens at all):
a chunk starting there **must** glue.

## 5. THE REAL FINDING — why the fix has not reached the owner

Not the join. Not the plumbing. **The delivery.**

- The last `HOT_RELOAD_WORKER_APPLIED` for `sotto_worker.py` was at log line **25476**.
- The worker running now, **pid 29008**, was spawned at log line **26978** (`WORKER_AUTOSTART=started
  reason=default`), CreationDate **08:01:56**.
- **Since that spawn: 20 `HOT_RELOAD_WORKER_QUEUED`, 20 `HOT_RELOAD_WORKER_DEFERRED`, 0
  `APPLIED`, 0 respawns** — the first at line 31058. My edits are in that set.
- The deferral is verbatim: `reason=capturing -- applies at the next boundary`, and the condition is
  `WorkerReloadPolicy._fire` (`app/webview/sotto_webview.py:5711`) →
  `if br.is_capturing(): … return  # pending stays`, where
  `is_capturing()` is `bool(self.capturing) and self.child is not None` (`:4784-4792`).
  **While the owner's audio keeps playing, `capturing` is True and the boundary never comes.** The
  reload lands only on a NATURAL respawn (the `_fire` path at `:5719-5724` marks a request satisfied
  when a respawn happened after it was queued) — and his worker has not respawned once since 08:01:56.

**This is not my file and I did not touch it** (`app/webview/sotto_webview.py`, revision 286 151 B,
sha256 `A7B378F1BFF31A6DAE3C76C69A49FEDBE6A811868A832BB786BD9F246A17855D` at the time of reading; it
has moved since). It is a finding for the lane that owns the shell, and it is **not specific to my
fix**: every `sotto_worker.py` edit by every lane since 08:01:56 is queued and unapplied.

**The minimal delivery action, for whoever owns that decision:** the worker alone has to be restarted
— killing pid 29008 makes the shell respawn it 2 s later, and the new process reads the fixed file.
A full shell restart also works. **I did not do either**: the owner's app is not mine to restart, and
the house rule is that lanes do not touch it.

## 6. What was NOT proved

1. **No audio DEVICE was opened** — pid 29008 holds the endpoint. The live *loop* was exercised
   through `SOTTO_FILE_TAP`; the endpoint's own cadence and jitter are not in this measurement.
2. **The owner's exact audio was not re-run**, so `an other`, `lan e` and `tow s` cannot be assigned
   to "pre-fix seam" or "the model's own word start" from here. `he 's` CAN, from the vocabulary.
3. **The batch/Redux caption emitter was not exercised.** `ReduxHiddenSwitch` is OFF by default
   (`switch = None`, `sotto_worker.py:3995`, opt-in via `--redux-when-hidden` /
   `SOTTO_REDUX_WHEN_HIDDEN=1`) and the owner's spawn line shows neither, so its `drain_captions()`
   path (`:3837-3840`) was inert. It emits caption payloads WITHOUT going through `LineFormer.push`,
   so it is a separate surface that this receipt does not cover.
4. **The model's decode quality is a separate defect.** The GREEN live line reads
   `The Radio anced that the bridge over the river … next Mone` — "announced" lost `noun` and
   "Monday" lost `day`. Those are not seams (the glue did its job: `an`+`ced`, `Mon`+`e`) and no
   seam fix can address them. The owner's `M in front` and `meet rage` may be the same class.
5. **Only one clip.** `_main/en-us-sample.wav`, 14 s, one language.

## 7. Files this task added (all under `_main/`)

| file | what |
|---|---|
| `live-seam-probe.py` | the live loop fed from a file + spies on `push`/`emit`; `--neg-arm` = the pre-fix body |
| `live-seam-two-colours.py` | the two colours side by side, the owner's strings, the vocabulary fact |
| `_live-seam-show.py` | prints the live captions and every seam decision |
| `_live-seam-probe.json`, `_live-seam-neg.json`, `_live-seam-{en,neg}.out/.err` | the evidence |

**Re-verified on the FINAL revision (237 489 B / `29E4CBFA…`):** the live seam probe re-run in both
colours gives the SAME numbers (`continues_true` 11 of 47 GREEN, 9 of 47 RED, 24 captions each), and
word-split-oracle 12/12 + `--neg-arm` PASS, caption-lines 12/12, verdict-gate GREEN, fresh-processor
GREEN, `py_compile` rc 0.

---

# PART B — the panel's WAVE: the meter is ON again, and the log is the shell's to limit

## 8. What was wrong, and it was NOT what it looked like

The coordinating agent's account was that turning `METER_HZ_DEFAULT` to `0.0` starved the panel's
wave. **The conclusion is right; the causal chain is not, and the difference decides who fixes what.**

| claim | measurement |
|---|---|
| "the worker stopped emitting `peak`" | The owner's worker **has no meter code at all**. `grep 'meter'` over `_main/webview-run.log` → **0** meter events, **0** `meter        :` announcements, ever. pid 29008 was spawned at 08:01:56; the meter was written at ~10:2x. **A default that changed at 10:2x cannot be the cause of a defect in a process started at 08:01:56.** |
| so what feeds the panel's wave today? | The shell's `stats()` (`sotto_webview.py:4796-4809`) returns `{peak, blocks}` read from `last_worker_stats`, which `_pump` fills **only** from the `WORKER_STATS` stderr line (`:6142-6147`). That line's `peak` is the **RUN MAXIMUM** and it arrives **once per 10 s**. |
| what does a wave drawn from that look like? | A staircase: it can only rise, then it flatlines. **Exactly "as ondas que crescem e diminuem não tá funcionando".** This is the ORIGINAL contract-lane defect, unchanged by anything I did. |
| and has the shell ever fed it? | `BRIDGE_STATS_REPLY` in the log → **0**. The stats channel has never answered a poll in this log's lifetime. |

So there are two separate blockers and **neither is the default**: the datum was a run maximum at
0.1 Hz, and the shell does not consume the `meter` event that carries a per-window level at 10 Hz.

## 9. The change: one constant, and the cadence is a measurement

```
METER_HZ        = 10.0     # the rate the meter runs at (unchanged)
METER_HZ_DEFAULT = 10.0    # was 0.0 — the wave's datum is ON again
```

**The cadence, confirmed rather than assumed: 10 Hz IS the tap's own block rate.** `audio.block_ms:
100` ⇒ `AudioMeter.blocks_per_window = round(interval / block_s) = 1` ⇒ **exactly one point per
block**. Measured on the live loop fed from a file: **120 meter events in 12 s = 10.0 points/s**,
`blocks` per event = `[1]`. A faster window would have to invent points between blocks; a slower one
would throw away blocks the tap already measured.

**The reasoning that was reversed, kept because it is the transferable part:** the default went to 0
to stop the shell logging an unknown `type` once per sample. That is **switching the DATA off to fix
a LOG** — a feature disabled to keep a log quiet. The limit belongs where the flood is produced.

## 10. TWO COLOURS, and one without the other is not a pass

**(a) The datum exists and MOVES** — live loop, `SOTTO_FILE_TAP`, **no device**, shipped default, no
flag (`_main/meter-wave-two-colours.py`):

| | |
|---|---|
| meter events | **120** (10.0 Hz) |
| captions | 22 |
| distinct amplitudes | **70 of 120 samples** |
| **rises / falls / flat** | **49 / 55 / 15** |
| min / max | 0.0 / 0.6898 |
| first 14 samples | `[0.0, 0.4124, 0.4926, 0.6324, 0.4077, 0.4537, 0.5018, 0.4255, 0.5862, 0.5521, 0.2521, 0.0616, 0.383, 0.2276]` |

A wave whose amplitude never changes is a flat line; one that only rises is a staircase. **49 rises
and 55 falls across 120 samples** is a wave. The RED colour is the same run at `--meter-hz 0`: 0
events, 0 bytes (oracle arm 4, and it is the reason the oracle's `--neg-default` mode exists).

**(b) The log-side cost, as a NUMBER** — so the flood is a budget, not a scare:

| | |
|---|---|
| the shell's line | `sotto: BRIDGE_UNKNOWN type='meter'` = **35 B** (UTF-8 + newline) |
| at 10 Hz | **350 B/s = 21 000 B/min = 20.5 KB/min**, unbounded, plus `malformed` climbing |
| today (0.1 Hz) | 210 B/min |
| with the aggregation the shell ALREADY has for the sibling push | **~105 B/min** |

**The pattern to copy is in the shell's own file**: `_stats_log_maybe`
(`app/webview/sotto_webview.py:4847-4860`) logs the FIRST sample and then at most **one line per
`STATS_LOG_INTERVAL_S = 30.0`**, carrying the count of what it stands for. The unknown-type path
(`_consume`'s `else`, `:6274-6275`) still does `self.malformed += 1` +
`self.log(f'BRIDGE_UNKNOWN type={kind!r}')` with no limit.

**NOT RUN: I did not run the shell** — single-instance lock, and it is the owner's live app. That
20.5 KB/min is the file's own arithmetic on a measured line length, and I am labelling it as such.

## 11. THE HALF THAT IS NOT MINE — stated so it cannot be mistaken for done

1. **The wave will NOT move from my change alone.** The shell has **no `type:"meter"` branch**
   (`grep meter` in `app/webview/sotto_webview.py` → no `kind == 'meter'`). Until the shell routes
   the event into the payload `stats()` returns, the panel keeps receiving the WORKER_STATS run
   maximum once per 10 s. **This is the shell's half, and it is the half that makes the owner's
   animation work.**
2. **The log limit is the shell's half too** — same file, same lane, and the pattern is already
   written there.
3. **`app/webview/sotto_webview.py` was NOT edited by me** (347 988 B, mtime 11:48:43 at the time of
   writing; it moved twice while this receipt was being written). Handing this to the shell lane is
   the correct split, not a punt.
4. **Both processes are running pre-08:00 code.** The worker's fix needs a **worker** restart; the
   shell's needs a **shell** restart. **ORDER MATTERS:** if the worker restarts first, the shell
   still running its old code will log one `BRIDGE_UNKNOWN` per meter sample — **20.5 KB/min** —
   until the shell restarts. Restart the shell first (or both together).
5. **`--meter-hz 0` / `SOTTO_METER_HZ=0` remains the escape hatch**, and with it off not one byte
   reaches stdout (oracle arm 4, measured).

## 12. Files PART B added (all under `_main/`)

| file | what |
|---|---|
| `meter-wave-two-colours.py` | the datum's movement + the log-side arithmetic, both as numbers |
| `_meter-default-live.jsonl` / `.err` | the live default run (120 events, 3 WORKER_STATS lines) |
| `audio-meter-oracle.py` | **inverted**: the two `default` arms now assert `10` and that the level RISES and FALLS; `--neg-default` flips it back to 0 |
| `_wordsplit-meter*.out` | the four colours of that oracle |

**Oracle, four colours, on the final revision:**
`11 PASS / 0 FAIL` — `--neg-default` **2 RED**, `--neg-arm` **3 RED**, `--neg-cadence` **2 RED**,
0 stayed green, 0 controls broken in every mode.
