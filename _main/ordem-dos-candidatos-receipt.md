# Receipt — lane SottoOrdemCandidatos (ordem dos candidatos WASAPI)

status: done
deliverable: `H:/sotto/docs/audit/ordem-dos-candidatos.md` · `H:/sotto/worker/wasapi_loopback.py`
· `H:/sotto/worker/sotto_worker.py`

## What landed

* **Diagnosis:** (a) is true; (b) and (c) are false, both with numbers (§1 of the doc).
* **Cure:** `prefer_rendering_now()` (sotto_worker.py) + `live_render_peaks()` (wasapi_loopback.py)
  — the meter is re-read at the moment the choice is made, so the endpoint rendering NOW is the
  one the tap opens. Measured RED/GREEN on the live machine: without the cure attempt 1 opens
  `VoiceMeeter Input` (meter 0.000000) while `CABLE Input` measures 0.386425; with the cure it
  opens `CABLE Input`. Re-read cost 0.749 s against the 6.0 s window it saves.
* **Collateral, measured and fixed:** `_friendly_name()` returned None for all six active render
  endpoints (`Activate(IPropertyStore)` → E_NOINTERFACE 0x80004002; PROPVARIANT union read at
  offset 0 instead of 8 — access violation rc=5; vt tested against 0x001B instead of
  VT_LPWSTR 0x001F). All three fixed; device names are readable now.
* `python -m py_compile worker/wasapi_loopback.py worker/sotto_worker.py` → rc=0.

## Not verified / blockers

* The running app cannot run its worker: `BRIDGE_EXIT rc=1 ... ModuleNotFoundError: No module
  named 'onnxruntime'`, because it spawns `I:\!manager\.venv\Scripts\python.EXE`, which has no
  onnxruntime while `C:\Program Files\Python311\python.exe` has 1.30.0. So the acceptance's
  "AFTER, no log da app viva" could not be produced. Ticket `4508645cd7c0f5b0940d51b0` filed;
  the owner is the lane that launches the app (`default_python()`,
  app/webview/sotto_webview.py:3059).
* The owner's audio is rendering on CABLE Input throughout (0.13–0.39), so the silence→audio
  transition the defect needs was reproduced only in the silence arm, not live.
* The rotation in the live conditions with signal present (`reason=flat` with peak 0.1–0.38) is
  the `_on_silence`/`BRIDGE_SILENT_BENIGN` behaviour the brief says is already cured; it was NOT
  touched and is unchanged.

## SELF-AUDIT

- **protocolos em falta** — I did not run a preflight that cites the paths a lane will touch
  *before* editing. I began editing after reading, which happened to be right, but I had no
  preflight for two sibling-owned surfaces I ended up needing (`_main/_ordem-before/`
  scaffolding, and `app/webview/sotto_webview.py`, which I correctly left alone). Differently: I
  would have run `git status --porcelain` BEFORE editing, so the BEFORE arm could have been the
  real pre-edit working tree — HEAD turned out to carry sibling lanes' uncommitted work, so a
  HEAD-based BEFORE was invalid and had to be rebuilt by reverting my own hunks.
- **verificacao adicional** — a second RED/GREEN oracle run at a moment when the owner's audio is
  *silent*, to show RED still opens the default while GREEN skips to whichever endpoint my own
  stimulus lights. Cost: one 40 s arm; it needs the owner quiet for ~15 s. Cheap one I DID run
  instead: the oracle twice, GREEN rc=0 and RED rc=3.
- **checkboxes novas** — before touching a worker file, run `git status --porcelain <dir>`; if it
  is dirty, snapshot the WORKING TREE, never HEAD, as the BEFORE arm (`cp worker/*.py <before>/`).
  The command that would have left me RED: `diff <(git show HEAD:worker/sotto_worker.py)
  worker/sotto_worker.py` → non-empty because of a sibling lane, which invalidates a HEAD-based
  BEFORE.
- **review por outro subagente** — sim-com-escopo: re-run `_main/_ordem-cura-oracle.py` against
  both `worker/` (expect rc=0) and `_main/_ordem-before/` (expect rc=3), and check that
  `live_render_peaks()` cannot reorder a list when every endpoint reads 0.0.
- **gate-doubt**:
  - **verde-de-verdade:** the GREEN arm of the oracle is not a pass-by-construction — it asserts
    on the NAME of the endpoint attempt 1 opens against the endpoint the live meter says is
    loudest, and the RED arm (same box, same meter, same list, module without the cure) exits 3
    on the same assertion, so the instrument can fail. The quiet-but-vacuous risk I checked and
    rejected: `py_compile` rc=0 proves syntax only, never that the re-read runs — the timing gap
    between `device-rotated` and the next `capture-started` (0.755 / 0.748 s, matching 0.12 s x 6
    endpoints + COM) is what proves it executed, measured in `_main/_ordem-AFTER-live`.
  - **falta-no-gate:** neither the oracle nor the arms check that `live_render_peaks()` leaves COM
    balanced across a long run of rotations. A future change that drops the `_com_uninit()` on
    the `COM_REF_TAKEN` path walks through it: hundreds of re-reads in one process, each taking a
    COM reference it never gives back. What I tried to break and could not: a run with three
    consecutive rotations (`_main/_ordem-AFTER-live`) ended in
    `Initialize(SHARED|LOOPBACK) failed: 0x8889000A` — an endpoint-invalidation code, not an
    apartment error, so it is evidence AGAINST a COM leak but not proof.
  - **gate-melhor:** `bash -c 'for i in $(seq 1 10); do "C:/Program Files/Python311/python.exe" -c
    "import sys;sys.path.insert(0,r\"H:/sotto/worker\");import wasapi_loopback as w;
    p=w.live_render_peaks(); assert len(p)==6, p" || break; done; echo "$i"'` — 10 consecutive
    reads with no failure leaves it GREEN; if the fix ever leaks a reference the eleventh read is
    where it must turn RED, and the input that must leave it RED is the same loop with the
    `if com == COM_REF_TAKEN: _com_uninit()` line removed.
- **confianca** — alta for the diagnosis ((a)/(b)/(c): two arms of the same probe plus the arms'
  rotation counts) and for the cure's mechanism (RED/GREEN oracle on the live meter); media for
  the size of the win in the owner's real day, because the owner's audio was up throughout, so
  the live "one rotation instead of two" was never observed end to end.
- **nao verificado** — (1) the AFTER number on the live app log (blocked: onnxruntime);
  (2) an end-to-end run of the silence→audio transition with the cure (needs the owner quiet for
  ~15 s); (3) whether `_friendly_name` succeeds on endpoints on a machine OTHER than this one —
  only these six were measured; (4) that `PropVariantClear` frees exactly the string `GetValue`
  allocated (checked only that it does not crash and that the names come back).

## CACHE/PRICE

<!-- pasted verbatim from scripts/cache-task-report.sh SottoOrdemCandidatos
     (raw copy at G:/superharness/_scratch/_ordem-cache.txt); the two long lines
     that the reader truncated when first shown are reproduced here in full -->
- task/agent: SottoOrdemCandidatos
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoOrdemCandidatos.jsonl
- cache: read=20596352 write=0 hit=98.7145% (cache-read / input+cache-read); universe: 100 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoOrdemCandidatos.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=94 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-zen/ling-3.1-flash-free $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 100 of 100 matched usage rows
- when-failed: break_items=1; WHEN=2026-10-06T13:02:28.990000+00:00 | break_items=1; WHEN=2026-10-06T13:02:29.564000+00:00 | break_items=3; WHEN=2026-10-06T13:02:30.189000+00:00 | break_items=2; WHEN=2026-10-06T13:04:25.745000+00:00 | break_items=2; WHEN=2026-10-06T13:09:36.683000+00:00 | break_items=1; WHEN=2026-10-06T13:20:05.638000+00:00 (state=RESOLVED-BREAKS-OMP; population: 6 of 118072 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoOrdemCandidatos']; window: 2026-10-06T13:02:28.990000+00:00..2026-10-06T13:20:05.638000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791291748990 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791291749564 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791291750189 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=83; turn_id=1791291865745 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=194; turn_id=1791292176683 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=246; turn_id=1791292805638 (state=RESOLVED-BREAKS-OMP; population: 6 of 118072 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoOrdemCandidatos']; window: 2026-10-06T13:02:28.990000+00:00..2026-10-06T13:20:05.638000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T13:29:01.512993+00:00
- usage rows: 100
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 268214
- output tokens: 107518
- cache-read tokens: 20596352
- cache-write tokens: 0
- hit ratio: 98.7145% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=94 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-zen/ling-3.1-flash-free $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 100 of 100 matched usage rows
- prefix breaks: 10 (state=RESOLVED-BREAKS-OMP; population: 6 of 118072 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoOrdemCandidatos']; window: 2026-10-06T13:02:28.990000+00:00..2026-10-06T13:20:05.638000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T13:02:28.990000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791291748990
  - break_items=1; WHEN=2026-10-06T13:02:29.564000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791291749564
  - break_items=3; WHEN=2026-10-06T13:02:30.189000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791291750189
  - break_items=2; WHEN=2026-10-06T13:04:25.745000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=83; turn_id=1791291865745
  - break_items=2; WHEN=2026-10-06T13:09:36.683000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=194; turn_id=1791292176683
  - break_items=1; WHEN=2026-10-06T13:20:05.638000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=246; turn_id=1791292805638
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

## CACHE/PRICE — re-run after the 17:37 restart (verbatim, same session file, 117 rows)

<!-- scripts/cache-task-report.sh SottoOrdemCandidatos ; raw copy G:/superharness/_scratch/_ordem-cache2.txt -->

## CACHE/PRICE
- task/agent: SottoOrdemCandidatos
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoOrdemCandidatos.jsonl
- cache: read=24178944 write=0 hit=95.5738% (cache-read / input+cache-read); universe: 117 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoOrdemCandidatos.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=104 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=11 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-zen/ling-3.1-flash-free $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 117 of 117 matched usage rows
- when-failed: break_items=1; WHEN=2026-10-06T13:02:28.990000+00:00 | break_items=1; WHEN=2026-10-06T13:02:29.564000+00:00 | break_items=3; WHEN=2026-10-06T13:02:30.189000+00:00 | break_items=2; WHEN=2026-10-06T13:04:25.745000+00:00 | break_items=2; WHEN=2026-10-06T13:09:36.683000+00:00 | break_items=1; WHEN=2026-10-06T13:20:05.638000+00:00 | break_items=276; WHEN=2026-10-06T17:41:52.949000+00:00 | break_items=224; WHEN=2026-10-06T17:42:04.342000+00:00 (state=RESOLVED-BREAKS-OMP; population: 8 of 120594 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoOrdemCandidatos']; window: 2026-10-06T13:02:28.990000+00:00..2026-10-06T17:42:04.342000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791291748990 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791291749564 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791291750189 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=83; turn_id=1791291865745 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=194; turn_id=1791292176683 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=246; turn_id=1791292805638 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791308512949 | session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=4; turn_id=1791308524342 (state=RESOLVED-BREAKS-OMP; population: 8 of 120594 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoOrdemCandidatos']; window: 2026-10-06T13:02:28.990000+00:00..2026-10-06T17:42:04.342000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T17:42:11.086529+00:00
- usage rows: 117
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 1119784
- output tokens: 120839
- cache-read tokens: 24178944
- cache-write tokens: 0
- hit ratio: 95.5738% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=104 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=11 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-zen/ling-3.1-flash-free $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 117 of 117 matched usage rows
- prefix breaks: 510 (state=RESOLVED-BREAKS-OMP; population: 8 of 120594 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoOrdemCandidatos']; window: 2026-10-06T13:02:28.990000+00:00..2026-10-06T17:42:04.342000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T13:02:28.990000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791291748990
  - break_items=1; WHEN=2026-10-06T13:02:29.564000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791291749564
  - break_items=3; WHEN=2026-10-06T13:02:30.189000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791291750189
  - break_items=2; WHEN=2026-10-06T13:04:25.745000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=83; turn_id=1791291865745
  - break_items=2; WHEN=2026-10-06T13:09:36.683000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=194; turn_id=1791292176683
  - break_items=1; WHEN=2026-10-06T13:20:05.638000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=246; turn_id=1791292805638
  - break_items=276; WHEN=2026-10-06T17:41:52.949000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791308512949
  - break_items=224; WHEN=2026-10-06T17:42:04.342000+00:00; WHERE session_id=01a1114e-d581-76a0-aa52-d524d24b3830 provider=deepseek-flash model=deepseek-flash item_index=4; turn_id=1791308524342
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

## Addendum after the 17:37 restart

- Deliverables re-censused post-restart: 7/7 PRESENT (doc 17981 B, receipt 12926 B before this append, both worker files, probe, oracle, seat file).
- The seal's two RED governors closed while this lane worked and are now EM DIA with a NEW signal: `theorist-always-on` idade=11 s (was 47.10 h) and `theorist-delta-guard` idade=3.2 min with `06/10/2026 14:34:01 RAN target=theorist-delta-guard-scheduled.cmd rc=0` — the task was Disabled when this lane measured it and is running now. Panel: 0 of 23 in VERMELHO.
- New ticket `29f9285c453daca4ec2ace95`: `write agent://Main` is refused at transport ("this build exposes no delegation seam"), so the blocker reached Main only through the terminal yield. Nothing was silently lost — the refusal says nothing was written.
- Two theorist passes (17-33Z, 16-55Z) were disposed as `skip` with reasons naming this seat's scope: their findings are about the observer/gate-trace, the solved-gate census, the owner-pendency registry and the INDEX writer, none of which this lane owns or can act on.
