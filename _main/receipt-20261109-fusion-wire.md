# Receipt — FUSION WIRE (2026-11-09, `FusionWire`)

**Deliverable state: DARK** — the join is written and wired into the shipped
caption ingress, and both the join and the two surfaces it feeds are exercised
by an oracle that execs the REAL functions; the running app was NOT launched
(owner's window, H:/sotto rule), so the live seam is unproven in-process.

## 1. Starting state — `fusion` had no consumer

Command (run before any edit; the same proof against `HEAD` after the work):

```
grep -rn "import fusion\|from \.fusion\|from worker\.fusion\|fusion import" --include=*.py .
git grep -n -E "import fusion|from \.fusion|from worker\.fusion|fusion import" HEAD -- '*.py'
```

Output: **no matches** (`git grep` rc=1). The only other reader of the core is
`_main/fusion-oracle.py`, which loads it by PATH (`spec_from_file_location`),
not by import — so the shipped pipeline never called it.

## 2. The join, and why it lives where it does

`SottoShell.on_worker_caption` is the ONE place a worker caption passes
through, and both surfaces hang off it:

* **LIVE** — `push_caption_to_window(text)` → the slot → `_drain_caption_pending`
  → `caption_overlay.set_text` (and the panel row, via `emit_async('caption')`).
* **HISTORY** — the same `emit_async('caption', {'text': text, 'meta': meta})`
  feeds the panel, whose `caption-formulation.js` commit is what calls
  `history-append` → `SottoShell._history_append` (app/webview/sotto_webview.py:11485)
  → `SottoShell.history_append` (app/webview/sotto_webview.py:14624).

So one decision at ingress reaches both; patching the two surfaces separately
would be two rules for one line.

Roles kept apart by the method:

* a **partial** (`final` not true) is the STREAM hypothesis for its line
  identity `(historySession, start)` — remembered, bounded to 32 entries;
* a **`final:true`** caption is the FINISHER's hypothesis for the SAME identity
  (the M3 second pass, or the Redux overlay's line) — fed to
  `worker/fusion.py` with the remembered stream text, and the FUSED text is what
  ships.

The stream line is seeded with `feed(stream, '')` and then `reveal()`, which is
what arms `REVEALED_REPLACE_RULE` ("revealed word replaced only when the
finisher disagrees AND both models never confirmed it"). The seed is NOT
`feed(stream, stream)`: that would stamp `both_models=True` before the finisher
spoke, i.e. fake the very confirmation that blocks a correction.

`Fusion` state persists per `(session, start)` so a later finisher hypothesis is
judged against what is on screen, not against a fresh copy of the stream line.

Switch: `SOTTO_FUSION=1` (OFF by default); `FUSION_SWITCH_ENV` at
app/webview/sotto_webview.py:986. When it changes text, the log carries
`FUSION_EDIT op=… span=i:j was="…" now="…" stability=…`.

## 3. Exact edits (file:line — HEAD → working tree)

| # | Site | HEAD | Now | What |
|---|---|---|---:|---|
| 1 | `app/webview/sotto_webview.py`, module-level block after `history_merge` | — (insertion point 964) | **965-1060** | `FUSION_SWITCH_ENV` (:986), `fusion_enabled` (:995), `_fusion_module` (:1001, lazy `worker/fusion.py` import by directory, like `_speaker_bridge`), `fuse_caption` (:1022, seed+reveal+feed), `_fusion_key` (:1044, `(historySession, start)`) |
| 2 | `SottoShell._fusion_caption` | — (method did not exist) | **17508-17598** | the join: remember partial / fuse final, bound the registries, log `FUSION_EDIT`, return the target text |
| 3 | `SottoShell.on_worker_caption` — call site | — (no call; method at **17411**) | hunk **17611-17621** (code 17619-17621) | 8 comment lines + `_fuse = getattr(self, '_fusion_caption', None)` / `if _fuse is not None:` / `text = _fuse(text, meta)` — one variable, used by BOTH consumers |
| 4 | `on_worker_caption`, final-line context | **17446** `_url = self._viewing_url()` | **17651-17652** `_viewing_url = getattr(...)` / `_url = _viewing_url() if callable(...) else ''` | probe-safe (see §4); the call itself predates this work |
| 5 | `on_worker_caption`, final-line context | **17453** `self.note_history_context(meta)` | **17659-17661** `_note_ctx = getattr(...)` / `if _note_ctx is not None:` | same |
| 6 | `_main/fusion-wire-oracle.py` | — | new | 10 arms + `--pair` + `--neg-arm`; execs the REAL functions extracted by `ast` |
| 7 | `_main/_fusion-wire-two-arm.js` | — | new | two-arm measurement through the REAL `app/panel/caption-formulation.js` |

Edits 4/5 are a **pre-existing** probe-shell bug, not part of the fusion join:
`git show HEAD:app/webview/sotto_webview.py | grep -n "_viewing_url()"` →
`17446:            _url = self._viewing_url()`, and `_main/caption-lag-budget-oracle.py`
drove `on_worker_caption` with a `types.SimpleNamespace` that never had the
method. It is fixed here defensively (`getattr`, no silent `except`), matching
the `_observe_ctx` idiom already in the same method.

No edits in `worker/sotto_worker.py`, `worker/models/**`, or
`app/panel/caption-formulation.js`. Nothing was launched; no audio device was
touched.

## 4. Oracle runs (verbatim)

### `python _main/fusion-wire-oracle.py` → rc 0

```
GREEN call-site-present  on_worker_caption chama o join (getattr=True call=True)
GREEN switch-off  push='o sotto ta rodando' edits=0
GREEN stream-only  push='o chotto ta rodando' edits=0
GREEN agreement  push='o sotto ta rodando' ops=0 stability=confirmed
GREEN correction  push='o sotto ta rodando' ops=[{'op': 'replace', 'span': [1, 2], 'text': 'sotto'}] log='FUSION_EDIT op=replace span=1:2 was="chotto" now="sotto" stability=corrected'
GREEN overlay-gets-fused  push='o sotto ta rodando'
GREEN history-gets-fused  panel_text='o sotto ta rodando' (o commit do painel e o que history_append grava)
GREEN revealed-word-locked  push='o sotto ta rodando' edits=0
GREEN key-has-session  push='charlie delta' edits=0
GREEN same-text-both-surfaces  fusao='text' panel='text' overlay='text'

FUSION-WIRE GREEN -- arms=10 pass=10 fail=0 (rc=0)
```

### `python _main/fusion-wire-oracle.py --neg-arm` → rc 1

```
NEG-ARM: PASS caught=correction (sem o call site: push='o sotto ta rodando', FUSION_EDIT=0) -- o arm fica VERMELHO e o portao nomeia-o
```

The mutation removes the call-site block in a COPY of `sotto_webview.py`; the
copy is re-extracted and the correction arm re-run through the real
`on_worker_caption` of the copy. No `FUSION_EDIT` is logged, so the arm the gate
names is `correction`.

### `python _main/undefined-names-oracle.py` → rc 0

```
UNDEFINED-NAMES GREEN -- 19 ficheiros de producao, 0 nomes usados e nunca definidos
```

### `python _main/fusion-oracle.py` (the core's own gate, untouched) → rc 0

```
VERDICT: PASS (14/14)
```

### `python _main/caption-lag-budget-oracle.py` (the shell fix in §3) → rc 0

```
arrival-final-not-blamed     PASS CAPTION_IN=CAPTION_IN start=1.0 end=2.0 final=true stable=true tap_ms=... age_ms=3200 text="linha fechada, audi | BLOWN=nao
VERDICT: PASS (15/15 arms)
```

### `python -m py_compile app/webview/sotto_webview.py _main/fusion-wire-oracle.py` → rc 0

## 5. Two-arm number (LIVE surface vs HISTORY surface)

Command: `node _main/_fusion-wire-two-arm.js` → rc 0

```
pair stream="o chotto ta rodando agora"
     refined="o sotto ta rodando"
     fused="o sotto ta rodando agora" ops=[{"op":"replace","span":[1,2],"text":"sotto"}] stability=provisional

raw    live_partial="o chotto ta rodando agora"
       live_after_close="o sotto ta rodando"
       history="O sotto ta rodando." commits=1 routes=["final"] producers=["redux"]
       sha256=0ff07ed09c7f851935e4b0723baec7e7d32509dc0f0a1f33badafdb11e2f9af6
wired  live_partial="o chotto ta rodando agora"
       live_after_close="o sotto ta rodando agora"
       history="O sotto ta rodando agora." commits=1 routes=["final"] producers=["redux"]
       sha256=32866ae57c9348a3f4559be97bb71da54b19d880c31cdfe02fcb422639281fd9

TWO-ARM sha_equal=false live_changed=true history_changed=true stream_words_kept=true
```

Reading it, with the commands that back each half:

* **The LIVE row while the line is open is the STREAM engine's text in both
  arms** (`live_partial` identical), and the **HISTORY line is the finisher's**
  (`producer=redux`, `route=final`, `commits=1`): the separation Main asked for
  survives the wiring.
* **`raw` is the shipped behaviour before the join**: the closed line replaces
  the row and is what history takes (`0ff0…`, drops `agora`). It is also the
  behaviour with `SOTTO_FUSION` unset — proved by the oracle's `switch-off` arm,
  which asserts the shell's push is the refined text unchanged.
* **`wired`** is the same events through `fuse_caption` (real core). The
  finisher's correction (`chotto`→`sotto`) lands as ONE `replace [1:2]`, and the
  stream word `agora` — already on screen and never contradicted — is KEPT
  (`_diff_ops` never emits `delete`). Hash changes on BOTH surfaces for exactly
  that reason.
* **Route counts do not change**: 1 commit / `route=final` / `producer=redux`
  in both arms. Fusion changes TEXT, not routing.

## 6. What is NOT proven

* The app was not launched, so no live run decoded audio through the join. The
  seam **`WorkerBridge._consume → on_worker_caption` in the running process** is
  unproven: the oracle calls the extracted method directly, not via the bridge.
* The Redux overlay / M3 second pass were not run (both are opt-in and would
  load models); their event shape is what the arm `history-gets-fused` reproduces
  (`final:true`, same `start`, `producer=redux`).
* `_main/fusion-oracle.py`'s 14 arms are green, but this receipt does not add the
  wiring to `_main/_audit-verify-all.cmd` — that gate is the owner's battery and
  depends on the two new files being listed first.

## CACHE/PRICE

- task/agent: FusionWire
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FusionWire']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FusionWire']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-09T22:09:20.963758+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FusionWire']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['FusionWire']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

## SELF-AUDIT

* **protocolos em falta** — I edited `on_worker_caption` (a file whose oracles
  drive it with fake shells) before grepping which oracles bind that method; the
  lag oracle went red and Main caught it. What I would do differently: grep
  `_main` for the method being edited BEFORE the first edit, and run those
  oracles in the same turn.
* **verificacao adicional** — run the two-arm measurement through `_history_append`
  itself (not only the panel payload) to close the last seam between "the panel
  receives the fused text" and "the file carries it". Cost: a fake shell plus a
  temp `SOTTO_HISTORY_ROOT`; ~30 lines.
* **checkboxes novas** — a mechanical assertion that `on_worker_caption` feeds the
  SAME variable to `emit_async` and `push_caption_to_window` after the join
  (added as arm `same-text-both-surfaces`), plus the call-site AST arm the
  neg-arm mutates.
* **review por outro subagente** — `sim-com-escopo` — the shell diff (4 hunks)
  and the two new `_main` probes.
* **gate-doubt** —
  * `verde-de-verdade:` the FUSION-WIRE green is real: every semantic arm execs
    the functions extracted from `sotto_webview.py` (not a copy), and the
    neg-arm kills the call site in a COPY and re-runs the same predicate —
    `python _main/fusion-wire-oracle.py --neg-arm` rc 1. The lag oracle green is
    real (`VERDICT: PASS (15/15 arms)` on the imported module). Not vacuous:
    `switch-off` and `stream-only` are the negative controls that must NOT edit.
  * `falta-no-gate:` the gate does not prove the BRIDGE delivers the refined
    event after the stream partial in the live process, nor that
    `_history_append` writes the same text the panel committed. A future change
    where `panel.js` re-composes the history line from stored fragments (instead
    of the event text) would keep every arm green while history diverged.
  * `gate-melhor:` add a `--history-arm` to the oracle that binds the extracted
    `_history_append` to a fake shell with a temp `SOTTO_HISTORY_ROOT`, feeds the
    panel's commit payload, and asserts the file line contains the fused word;
    the input that must leave it RED is the raw refined text (`agora` absent).
* **confianca** — `media`: the join, the rule and both surfaces are executed;
  the live bridge seam and a real decode are not.
* **nao verificado** — app launch; live `WorkerBridge` path; Redux/M3 models;
  real transcript file; audio devices (untouched, by rule).
