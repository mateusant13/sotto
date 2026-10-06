# Verdict-order fix — `worker/sotto_worker.py` (lane SottoVerdictShadow)

**Defect (localised by Main, confirmed by me on disk).** The top-level `done` verdict
tested the device-SELECTION outcome FIRST:

```python
if outcome in ("all-flat", "open-failed"):     # <- this branch won
    verdict = "all-candidate-taps-flat"
elif ran_but_silent:
    verdict = "silent-device"
```

`ran_but_silent = bool(silent_rows) and not proved_alive["any"]`, and the exit code is
`return 3 if ran_but_silent else 0`. When BOTH hold in one run, the run emitted
`state="silent-device"` (the loud status), returned **exit 3**, and its own `done` said
`all-candidate-taps-flat`. Word and code disagreed inside ONE run.

**Which word is TRUE when both hold (one sentence).** When both hold, at least one candidate
was *measured* opening and running a full window below the peak floor — the
device-attributable fact the exit code and the SILENT-DEVICE status already assert — whereas
`all-candidate-taps-flat` is only the weaker statement that no candidate settled; the specific
and code-consistent word is `silent-device`.

**Fix = the ORDER, no vocabulary renamed** (`worker/sotto_worker.py:1605-1608`):

```python
if ran_but_silent:
    verdict = "silent-device"
elif outcome in ("all-flat", "open-failed"):
    verdict = "all-candidate-taps-flat"
```

`ran_but_silent` is the exact predicate the exit code is built from, so
`done.verdict == "silent-device"` iff `exit == 3`, by construction.

## Pre-fix run on disk (both conditions, the contradiction)

`worker/runs/exit3-armB-worker.jsonl` (measured before the fix, rc 3):

```
{"type": "status", "state": "silent-device", "verdict": "silent-device", "device": "Mapeador de som da Microsoft - Input", "api": "MME", "peak": 0.000122, "peak_floor": 0.002, "blocks": 34, ...}
{"type": "status", "state": "done", "verdict": "all-candidate-taps-flat", ..., "device_outcome": "all-flat", ...}
```

## Oracle — `_main/verdict-order-oracle.py` (one command, `python -m`; workers `CREATE_NO_WINDOW`)

`py -3 _main/verdict-order-oracle.py`  ->  rc 0, wall 34.3 s, VERDICT **PASS**, `failures: []`.

Three arms, and the two word-arms cannot both pass by accident:

* **GREEN** (real worker): `rc=3  done_verdict=silent-device  device_outcome=all-flat
  blocks=45  both_conditions_hold=true  word_matches_code=true`.
* **RED** (a COPY with the pre-fix order restored): `rc=3  done_verdict=all-candidate-taps-flat
  silent_status_verdict=silent-device  device_outcome=all-flat  contradiction_reproduced=true`.
  The oracle builds the mutant TEXTUALLY and FAILS if it cannot find the branch, so the red
  arm can never pass vacuously.
* **BLUE** (no-data control, `--max-chunks 1`, blocks=15 < TAP_SILENT_BLOCKS=20):
  `rc=0  done_verdict=all-candidate-taps-flat  silent_status_present=false` — proves the fix
  reordered the branch rather than renaming a word out of existence.

The run reproduces BOTH conditions in one run: `--device <silent endpoint>` makes the first
candidate rung C, and `--max-chunks N` stops the run MID-WINDOW so `outcome` keeps its initial
`"all-flat"` (the rotation loop breaks on `stop.is_set()` before it can set `"explicit-flat"`),
while the candidate has already delivered blocks below the floor.

### The two lines, both arms (verbatim, from the oracle stdout)

GREEN:
```
{"type": "status", "state": "silent-device", "verdict": "silent-device", "device": "Mapeador de som da Microsoft - Input", "api": "MME", "peak": 0.000122, "peak_floor": 0.002, "blocks": 45, "window_s": 60.0, "silent_min_blocks": 20, ...}
{"type": "status", "state": "done", "verdict": "silent-device", "blocks": 45, ..., "device_outcome": "all-flat", ..., "proved_alive": false, ...}
```
RED (same device, same args, pre-fix order):
```
{"type": "status", "state": "silent-device", "verdict": "silent-device", "device": "Mapeador de som da Microsoft - Input", "api": "MME", "peak": 9.2e-05, "peak_floor": 0.002, "blocks": 45, "window_s": 60.0, "silent_min_blocks": 20, ...}
{"type": "status", "state": "done", "verdict": "all-candidate-taps-flat", "blocks": 45, ..., "device_outcome": "all-flat", ..., "proved_alive": false, ...}
```

## Window census against my OWN pids

* **Child self-report** (the instrument AGENTS endorses: a process reporting its OWN console,
  no enumeration of others). The REAL worker, run through its own code path with the exact
  flags I used (`CREATE_NO_WINDOW|DETACHED_PROCESS` = `0x08000008`), printed:
  `WORKER_SELF pid=33048 GetConsoleWindow=0 visible=False`, and its own `done` line was
  `verdict=silent-device`, rc 3.
* **The governor's own census** ran at both ends of my runs and never named me:
  ```
  JANELAS ts=2026-10-06T07:07:22Z modo=medicao visiveis=12 alarmSet=0 reencontro=0 pidsConhecidos=140 alarmeHerdadoApagado=0
  JANELAS ts=2026-10-06T07:08:22Z modo=medicao visiveis=12 alarmSet=0 reencontro=0 pidsConhecidos=140 alarmeHerdadoApagado=0
  ```
  No `ALERTA-JANELA` for any of my pids.

## CONTRADICTION to report (brief: report every measurement that contradicts this brief)

AGENTS.md (~lines 96-100) states that a PowerShell filter reading a process list must run from a
`.ps1` FILE with `Get-CimInstance Win32_Process`, because "the inline `-Command` form returns
EMPTY stdout on this box while the file form returns every row". I measured that when
`powershell.exe` is launched from this context with `CREATE_NO_WINDOW|DETACHED_PROCESS`, **BOTH**
forms return empty stdout (`rc 0`, `stdout=''`) AND a `... | Out-File <path>` inside the same
command creates no file at all. So the "file form works" half of that sentence did not reproduce
here: from this launch context the whole PowerShell channel is dead, and an empty channel is not
a zero. I therefore measured the console with the child's own `GetConsoleWindow()` (above), which
does not go through PowerShell at all. This is an instrument-channel observation, not a claim
about the census script itself (the scheduled census writes to a log file and is unaffected).

## SELF-AUDIT

- **protocolos em falta** — I did not name my lane in `agents/SottoVerdictShadow.md` (that file
  does not exist), so the harness cannot read my `tools:` line and the selo does not know my
  capability. Different, small fix: the seat declaration is the standing contract that makes the
  next selo readable, and I would write it first. Not this ticket's scope (a repo-copy file, not
  the product repo).
- **verificacao adicional** — I added the BLUE no-data arm precisely because the first version of
  the oracle could only show GREEN (word==code) and RED (contradiction) and said nothing about
  whether `all-candidate-taps-flat` still exists. That extra check was cheap (~8 s) and is now
  run mechanically. I did NOT add a check that the *panel* still paints the new word as an error
  (that is the existing `_main/panel-exit3-oracle.py`'s job).
- **checkboxes novas** — a mechanical `word == code` assertion for EVERY terminal state word the
  worker emits, not just `silent-device`: one line per `done` verdict, `verdict_word == f(exit)`.
  Command: `py -3 _main/verdict-order-oracle.py` (must be GREEN on the word-match and RED on the
  mutant). It would have caught this defect at introduction.
- **review por outro subagente** — sim-com-escopo *the verdict branch and the oracle's three arms*
  — the branch is the sentence the panel and any caller now trust; the oracle is a new gate whose
  non-vacuity someone else should try to break (e.g. by pointing it at a run where nothing is
  silent).
- **gate-doubt:**
  - **verde-de-verdade:** GREEN word==code came from a run whose `device_outcome=all-flat` AND a
    `silent-device` status with `blocks=45 ≥ 20`, i.e. both conditions held by content, not by
    construction. The RED arm is the discriminating control: a textually-reverted COPY produced
    `rc=3` while its `done` said `all-candidate-taps-flat`, so the green cannot be a
    pass-by-construction. The one shared instrument is the silent device — it is real hardware
    ("Mapeador de som da Microsoft - Input", measured peak ≤ 0.000122 across every run today); if
    the owner ever routes audio into it the GREEN arm would stop reproducing both conditions and
    the oracle would FAIL LOUDLY with `both-hold precondition not met` (not pass green).
  - **falta-no-gate:** the oracle checks the WORKER's word vs its code; it does NOT check that the
    panel/shell renders the word. A future change could keep the worker honest and let the shell
    swallow the verdict. That hole is owned by `_main/panel-exit3-oracle.py`, which this lane did
    not run.
  - **gate-melhor:** extend `_main/verdict-order-oracle.py` with a fourth arm that consumes the
    GREEN run's `done` line through the WebView2 shell's own status mapper and asserts the painted
    `kind == 'error'`; RED input: a `done` whose verdict is a word the shell does not know.
- **confianca** — alta. The fix is a two-line reorder whose invariant (`verdict == silent-device`
  iff `exit == 3`) is one predicate shared by word and code, measured GREEN+R1ED+BLUE.
- **nao verificado** — (1) the panel's rendered state for the new word (see gate-doubt above);
  (2) the ARM2/routed path of `_main/device-silence-oracle.py` (no audio was routed during this
  lane's window); (3) the PowerShell channel under a non-DETACHED launch (not needed for this
  ticket, and deliberately not attempted — a control arm would risk a window on the owner's
  screen).

gate-change-request: n/a — this lane found no hole in a gate; it fixed a PRODUCT defect (the
worker's own verdict order) and added a product oracle (`_main/verdict-order-oracle.py`, a `.py`,
not a gate script). The instrument-channel observation above is reported, not turned into a
gate patch.

## CACHE/PRICE

stdout of `bash I:/!manager/scripts/cache-task-report.sh SottoVerdictShadow`, verbatim:

```
## CACHE/PRICE
- task/agent: SottoVerdictShadow
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoVerdictShadow.jsonl
- cache: read=5889797 write=0 hit=96.3620% (cache-read / input+cache-read); universe: 51 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoVerdictShadow.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=41 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=10 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 51 of 51 matched usage rows
- when-failed: break_items=19; WHEN=2026-10-06T07:01:55.273000+00:00 | break_items=2; WHEN=2026-10-06T07:03:42.279000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 112513 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoVerdictShadow']; window: 2026-10-06T07:01:55.273000+00:00..2026-10-06T07:03:42.279000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11004-7081-716d-b015-7255b3b4e621 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791270115273 | session_id=01a11004-7081-716d-b015-7255b3b4e621 provider=deepseek-flash model=deepseek-flash item_index=72; turn_id=1791270222279 (state=RESOLVED-BREAKS-OMP; population: 2 of 112513 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoVerdictShadow']; window: 2026-10-06T07:01:55.273000+00:00..2026-10-06T07:03:42.279000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T07:08:35.770854+00:00
- usage rows: 51
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 222360
- output tokens: 46432
- cache-read tokens: 5889797
- cache-write tokens: 0
- hit ratio: 96.3620% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 21 (state=RESOLVED-BREAKS-OMP; ...)
- WHEN / WHERE failed:
  - break_items=19; WHEN=2026-10-06T07:01:55.273000+00:00; WHERE session_id=01a11004-7081-716d-b015-7255b3b4e621 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791270115273
  - break_items=2; WHEN=2026-10-06T07:03:42.279000+00:00; WHERE session_id=01a11004-7081-716d-b015-7255b3b4e621 provider=deepseek-flash model=deepseek-flash item_index=72; turn_id=1791270222279
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```
