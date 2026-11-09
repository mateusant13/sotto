# RECEIPT — code-health closure (2026-11-09)

**status: BLOCKED** — no GREEN-by-reduction exists inside this lane's writable scope.
The exact authorization needed is in §8. No baseline refresh was performed.

**scope:** item 4 of `TODO-omp-handoff-20261109.md`. Read-only on product files.
No app launch, no synthetic input, no battery, no baseline write.

**snapshot:** 2026-11-09 13:56 -03:00. Two files moved during the audit:
`app/panel/history-context-store.js` at **13:48:58** and
`app/webview/sotto_webview.py` at **13:53:56** (+85 lines, the history-session fix).
The numbers below are the 13:56 state; the metric *set* stayed the same (8) while the
webview values moved.

---

## 1. Oracle run — current baseline (verbatim)

Command: `python _main/code-health-oracle.py` (13:56 -03, exit 2)

```
RED  app/panel/history-context-store.js: bytes piorou de 8605 para 12980
RED  app/panel/history-context-store.js: lines piorou de 217 para 300
RED  app/webview/sotto_webview.py: bytes piorou de 1244408 para 1249560
RED  app/webview/sotto_webview.py: lines piorou de 23544 para 23634
RED  worker/sotto_worker.py: bytes piorou de 468615 para 473754
RED  worker/sotto_worker.py: lines piorou de 8882 para 8990
RED  worker/sotto_worker.py: defs piorou de 89 para 92
RED  worker/sotto_worker.py: except_pass piorou de 20 para 21
piorem: 8 metrica(s)
CODE-HEALTH VERDICT FAIL
```

The same command at 13:44 printed **6** metrics. The two `history-context-store.js`
lines appeared at 13:48:58 (8605 → 12980 B, 217 → 300 lines); the webview numbers
moved at 13:53:56 (1244761 → 1249560 B, 23549 → 23634 lines). The count is a moving
target while other lanes write: after this snapshot the same file was written again at
**13:57:53** (1249897 B / 23640 lines). The metric *set* stayed 8; only the webview
values drift, and the attribution (the uncommitted history-session fix) is unchanged.

The comparator is not mute — `python _main/code-health-oracle.py --neg-arm` (exit 1 by
design):

```
NEG-ARM M1 um ficheiro cresce 1 byte           RED as expected (bytes)
NEG-ARM M2 a funcao mais longa cresce          RED as expected (bytes)
NEG-ARM M3 aparece um except-pass novo         RED as expected (bytes)
POS-ARM o comparador diz VERDE no baseline     PASS as expected
POS-ARM e diz VERMELHO a +1 byte               PASS as expected
INFO    estado medido                          8 metrica(s) acima do baseline (divida ja publicada pelo passo `code-health`)
NEG-ARM 3 of 3 mutant(s) caught
NEG-ARM PASS
```

---

## 2. The "7 red metrics" the handoff named — verbatim, with the 7th explained

The handoff says *"7 red metrics across app/webview/sotto_webview.py and
worker/sotto_worker.py"*. That is the count against the **pre-refresh** baseline
(`b633097^`), not against today's baseline. Reproduced with the oracle's own
`census()` + `compare()` against `git show b633097^:_main/code-health-baseline.json`
(exit 2):

```
RED  app/panel/history-context-store.js: bytes piorou de 8605 para 12980
RED  app/panel/history-context-store.js: lines piorou de 217 para 300
RED  app/webview/sotto_webview.py: bytes piorou de 1243732 para 1249560
RED  app/webview/sotto_webview.py: lines piorou de 23534 para 23634
RED  worker/sotto_worker.py: bytes piorou de 466772 para 473754
RED  worker/sotto_worker.py: lines piorou de 8848 para 8990
RED  worker/sotto_worker.py: defs piorou de 89 para 92
RED  worker/sotto_worker.py: max_func piorou de 2682 para 2702
RED  worker/sotto_worker.py: except_pass piorou de 20 para 21
piorem: 9 metrica(s)  [against b633097^ baseline]
```

The **7** named by the handoff, isolated verbatim (the same run, the two product files):

```
RED  app/webview/sotto_webview.py: bytes piorou de 1243732 para 1249560
RED  app/webview/sotto_webview.py: lines piorou de 23534 para 23634
RED  worker/sotto_worker.py: bytes piorou de 466772 para 473754
RED  worker/sotto_worker.py: lines piorou de 8848 para 8990
RED  worker/sotto_worker.py: defs piorou de 89 para 92
RED  worker/sotto_worker.py: max_func piorou de 2682 para 2702
RED  worker/sotto_worker.py: except_pass piorou de 20 para 21
```

The other two lines in the run above are the live `history-context-store.js` edit
(first two rows of the table below).

### Per-metric attribution

| metric (verbatim) | caused by | delta | declared? |
|---|---|---|---|
| `history-context-store.js: bytes 8605 → 12980` | uncommitted edit, mtime **13:48:58**; file is untracked (`??`); history lane (named in handoff item 5) | +4375 B | no receipt, no commit |
| `history-context-store.js: lines 217 → 300` | same edit | +83 lines | no receipt, no commit |
| `sotto_webview.py: bytes 1244408 → 1244761` | **feee26d** `genai: as ~36 threads do stream nao tem botao` (13:44:11) | +353 B | work declared (receipt §7.5), code-health delta NOT declared |
| `sotto_webview.py: lines 23544 → 23549` | feee26d — 4-line comment + `'WORKER_GENAI_THREADS',` in `ENGINE_VISIBLE_TAGS` | +5 lines | same |
| `sotto_webview.py: bytes 1244761 → 1249560` | **uncommitted** edit, mtime **13:53:56**; the history-session identity fix (`_history_ctx_session_of`, `_history_ctx_observe_session`, `WorkerBridge.history_session`) — handoff item 2 | +4799 B | declared as work in the handoff, no commit/receipt |
| `sotto_webview.py: lines 23549 → 23634` | same uncommitted edit (`git diff --stat` = 85 insertions) | +85 lines | same |
| `sotto_worker.py: bytes 468615 → 473754` | feee26d | +5139 B | same |
| `sotto_worker.py: lines 8882 → 8990` | feee26d — `genai_thread_ids()`, `cpu_mask()`, `cap_genai_threads()` + the call after `og.Model` | +108 lines | same |
| `sotto_worker.py: defs 89 → 92` | feee26d — the three top-level functions | +3 | same |
| `sotto_worker.py: except_pass 20 → 21` | feee26d — `worker/sotto_worker.py:826-827`, `except Exception: pass` inside `cap_genai_threads` | +1 | same |
| `sotto_worker.py: max_func 2682 → 2702` | **b633097** (13:32:07); `main` grew by 20 lines with the `WORKER_COST` plumbing | +20 | **absorbed by b633097's own `--update`** |

`git show feee26d --stat` = `app/webview/sotto_webview.py | 5 +`,
`worker/sotto_worker.py | 108 +`. The numbers match the oracle exactly.

Note on the `except_pass` +1: `cap_genai_threads()` swallows every failure of the
census/pin loop (`except Exception: pass`, line 826). The exception-hygiene oracle does
**not** flag it, because its exemption window (`lines[lineno-3:lineno]`, 1-based
`lineno` used as a slice end) includes the `except` line itself, where the
`# noqa: BLE001` sits. Measured: the oracle's `offenders()` returns 8 for the current
worker and line 826 is **not** among them; stripping that inline comment makes it
count. Code-health counts it regardless — hence the RED. This is a silent fallback by
the house's own definition, not a cosmetic delta.

---

## 3. Baseline-diff forensics — five refreshes today, all authored by `mateusant13`

`git log --since=2026-11-09T00:00 -- _main/code-health-baseline.json`:

| commit | time | entries changed | declaration | verdict |
|---|---|---|---|---|
| `ac848d9` | 10:26:21 | 16 files, 51+/41- (panel, caption, history, performance, observability) | commit body EMPTY; declared in `receipt-20261109-reload-floor.md` §12-bis ("o diff inteiro sao as 16 linhas que este dia landou") | blanket re-pin, declared in a receipt; absorbed many lanes' work |
| `5986e78` | 12:23:33 | 8 entries, 46 lines: `history-context-store.js` (new, **untracked**), `history-store.js` −719 B, `panel-unified.css` −12 B, `history_context.py` −559 B, `sotto_webview.py` +20 lines, `youtube_cdp_source.py` +51 lines/defs+3/globals+3, `sotto_worker.py` +41 lines/defs+1/except_pass+1, `wasapi_loopback.py` 55288→58473 B / 1216→1244 lines / max_func 142→152 | **none** — empty body, no receipt section found | **illegitimate as a declared refresh**: it pinned a dirty worktree, including other lanes' uncommitted files and the still-uncommitted `wasapi_loopback.py` |
| `b5912be` | 13:17:45 | `sotto_webview.py` +112 lines, `sotto_worker.py` +75 lines, new `cost_watchdog.py` entry | commit body does not mention the baseline; receipt §6 says "as duas entradas re-medidas" (actually 3 entries) | undeclared in the commit, loosely declared in the receipt; same lane's own work |
| `32122b5` | 13:24:26 | `cost_watchdog.py` only, 5494→6057 B / 113→122 lines | body: "Nenhuma linha de comportamento mudou … o baseline de code-health re-medido" | scoped and declared — the correct shape |
| `b633097` | 13:32:07 | `sotto_webview.py` 1243732→1244408 B, 23534→23544 lines; `sotto_worker.py` 466772→468615 B, 8848→8882 lines, max_func 2682→2702 | body: "`code-health` re-pinado … crescimento declarado de 14 linhas na shell e 34 no worker e' desta mudanca" | see §4 |

**No scoped writer exists in the tree.** `grep -rn "code-health-baseline" _main/*.py`
returns only the oracle, and its `--update` rewrites the **whole** census
(`json.dump(... today ...)`). The 2026-10-30 receipt describes a key-by-key writer
("um `--update` inteiro regeneraria as 63 linhas do censo e apagaria o ratchet"), but
that writer is not present today. The repo precedent is explicit
(`receipt-20261024-lane-screen-gate.md`): `--update` is "só com o dono de acordo",
because it absorbs other lanes' growth.

---

## 4. Judgment on this lane's refresh (the one the assignment describes)

The assignment says the lane refreshed "via `--update` for +14 lines in
`sotto_webview.py` and +34 in `sotto_worker.py` (genai thread census)". Measured:

* The refresh with **+34 worker** is `b633097` (13:32:07), and its worker delta is
  **exactly +34** (8848 → 8882). That part is legitimate: it pins the lane's own
  declared `WORKER_COST` growth, and the commit body declares the re-pin.
* The shell delta is **+10 lines, not +14** (23534 → 23544, measured with the oracle's
  own `lines` formula at both revisions). The "+14" in the commit body is not
  reproducible from the baseline numbers; the +34 is.
* The same refresh **absorbed `max_func 2682 → 2702`** (+20 in `main`), i.e. it did not
  just pin size, it pinned the long-function regression of the same commit. That is a
  declared growth in the commit's own work, so it is defensible, but the receipt must
  say it.
* The genai census (`feee26d`, 13:44:11) did **not** refresh the baseline. It is the
  sole cause of today's 6 RED metrics in the two product files. So the assignment's
  attribution is off by one commit: the refresh was the cost-denominator commit, not
  the census.

**Verdict: keep `b633097`'s numbers, do not revert them; correct the receipt's "+14" to
"+10" and record the `max_func` absorption.** Reverting would turn a declared, already
measured growth back into RED without reducing a byte.

`5986e78` (12:23) is the one that should not have happened the way it did: it pinned
untracked files and the dirty `wasapi_loopback.py` from a tree that no commit
describes. Do not revert it unilaterally now — that would turn other lanes' in-flight
work RED — but it must not be repeated.

---

## 5. `worker/wasapi_loopback.py` — the undeclared change

`git diff -- worker/wasapi_loopback.py`: **31 insertions / 3 deletions**, +28 lines,
+3185 B (HEAD 55288 B → worktree 58473 B). Last commit touching the file is `0031526`
(2026-11-04), so this is uncommitted work.

What it does (from the diff, comments dated 2026-11-09):

1. `Initialize` now asks for `HNS_100MS` **first**; the zero-duration call becomes the
   fallback (`hr != 0`). Measured on this box: zero-duration is granted
   `GetBufferSize` = 1056 frames = 22 ms; `HNS_100MS` is granted 4800 frames = 100 ms.
2. `_open` records the **granted** ring (`GetBufferSize`, vtable slot 4) in
   `self._ring_frames`.
3. `_pump` derives `period = min(block_ms/2000, max(0.005, ring_s/4))` — 20 ms at a
   100 ms ring, 5.5 ms at the 22 ms fallback — instead of the fixed 5 ms. The comment
   cites pid 20676 at 6.0 % of a core, kernel-bound, as the reason.

It comes with an updated `_main/wasapi-buffer-fallback-oracle.py` (also dirty, 74 lines
changed) that now requires HNS_100MS as the primary call and a ring-derived period.
That oracle passes on the current bytes:

```
python _main/wasapi-buffer-fallback-oracle.py
  the PRIMARY call carries HNS_100MS (=1_000_000), the guarded retry is the zero-duration fallback: true
  block_ms from config.json: 40.0
  period formula: min(self.block_ms / 2000.0, max(0.005, ring_s / 4.0))
    granted 100 ms ring -> 20.0 ms (ring/4 = 25.0 ms)
    22 ms fallback ring -> 5.5 ms
VERDICT: PASS -- the retry is CONDITIONAL ...
EXIT=0
```

Provenance: no receipt in `_main/receipt-20261109-*.md` mentions `HNS_100MS`,
`ring_frames`, `1056`, or the 6.0 % measurement. It is declared **in code and in the
oracle**, not in a receipt, and not committed. It is someone else's lane (capture/audio).

Code-health impact: **none added** — the baseline entry was already pinned to
`58473 B / 1244 lines / max_func 152` by `5986e78` (12:23), which is the dirty
worktree's size, not any committed revision's (HEAD's file is 55288 B / 1216 lines).
So the ratchet currently cannot see this change at all; the pin is only reproducible
from the dirty tree.

---

## 6. Exception baseline — the dirty 7 → 6

`git diff -- _main/exception-baseline.json`:

```diff
- "app/webview/sotto_webview.py": 7,
+ "app/webview/sotto_webview.py": 6,
```

Provenance: the source dropped from 7 to 6 offenders at **`8e40508`** (2026-11-09
10:06:59, the YouTube-health refactor: two `except: pass` removed, one added, net −1).
The baseline file's mtime is **08:57:23**, so the edit was made against the then-dirty
source, before the commit. The committed baseline (HEAD) still says 7; with 7, C2
fails (baseline sum 42 vs measured 41). The dirty edit is therefore **required** and is
a **tightening** (a paid debt recorded), not a hidden growth.

Oracle on the current tree:

```
GREEN C1 nenhum ficheiro passa da linha de base
GREEN C2 a linha de base e igual ao medido
GREEN C3 a isencao e o comentario, e so ele
EXCEPTION-HYGIENE VERDICT PASS -- a divida de `except Exception: pass` nao cresce (medida: 41)
EXIT=0
```

It is not declared in any receipt or commit body. It must be committed by the owner of
`8e40508`; leaving it uncommitted means any `git checkout` of that file silently makes
the gate RED.

---

## 7. What could be reduced, and why this lane cannot do it

All three RED files are outside this lane's writable scope:

* `app/webview/sotto_webview.py` — two other owners' work in the same file: feee26d's
  genai tag (cost lane) and the uncommitted history-session fix (history lane, handoff
  item 2). The assignment and the house rules forbid touching the cost/genai region.
* `worker/sotto_worker.py` — explicitly owned by another lane right now.
* `app/panel/history-context-store.js` — untracked, history lane's live file.

There is no honest reduction this lane can make: the deltas are the other lanes' new
functionality, not dead weight this lane introduced. Refreshing the baseline would be
the only way to turn it green from here, and the assignment forbids doing that without
authorization. Hence **BLOCKED**.

---

## 8. Exact authorization needed

Copy the option the owner chooses; nothing below has been executed.

**A — preferred (GREEN by reduction).** The genai/cost lane reduces `feee26d` so the
two product files fit the current baseline again:

* `app/webview/sotto_webview.py`: bytes ≤ 1244408 and lines ≤ 23544. Two owners must
  act: the cost lane reduces feee26d's 5 lines (4-line comment + `'WORKER_GENAI_THREADS',`;
  the tag line alone still leaves bytes above the pin), and the history lane commits or
  reduces the +85-line session fix. Only together can the file fit the pin.
* `worker/sotto_worker.py`: bytes ≤ 468615, lines ≤ 8882, defs ≤ 89, except_pass ≤ 20.
  `defs` can only go back to 89 by inlining/removing one of the three helpers;
  `except_pass` must go back to 20 by handling the failure at `:826` instead of
  `pass` (this also removes a silent fallback).
* `app/panel/history-context-store.js`: the history lane commits it and then a scoped
  pin (or a reduction) is chosen; target ≤ 8605 B / 217 lines only if the new
  functionality is not wanted.

**B — only if A is rejected (authorized re-pin).** The owner authorizes a re-pin of
**exactly these entries**, after their owners commit them, with the deltas written in
the receipt:

* `app/webview/sotto_webview.py`: +353 B/+5 lines (feee26d) **plus** +4799 B/+85 lines
  (uncommitted history-session fix) = **+5152 B/+90 lines** against the pin.
* `worker/sotto_worker.py`: +5139 B, +108 lines, defs 89→92, except_pass 20→21.
* `app/panel/history-context-store.js`: +4375 B, +83 lines.

The only writer in the tree is the blanket `--update`; it rewrites all 91 entries from
whatever is in the worktree at that moment. So option B must either (i) wait until the
tree is clean/committed, accepting a full re-pin, or (ii) add a scoped writer first
(the 2026-10-30 receipt describes one that no longer exists).

**C — exception baseline.** Authorize committing `_main/exception-baseline.json`
(7 → 6 for `sotto_webview.py`). It is a tightening that matches `8e40508`; without it
the gate is RED on C2. Do not revert this edit.

**D — wasapi.** The capture lane commits `worker/wasapi_loopback.py` and
`_main/wasapi-buffer-fallback-oracle.py` with a receipt. No code-health refresh is
needed for it (the baseline already pins the dirty size), but the commit is what makes
the pin reproducible.

---

## 9. Commands used

```
python _main/code-health-oracle.py                     # 8 RED, exit 2
python _main/code-health-oracle.py --neg-arm           # 3/3, exit 1 by design
python _main/exception-hygiene-oracle.py               # PASS, 41 measured
python _main/wasapi-buffer-fallback-oracle.py          # PASS, exit 0
git log --since=2026-11-09T00:00 -- _main/code-health-baseline.json
git show <rev>:<file> | python -c "<oracle line formula>"
git show <rev>:<file> | python -c "<oracle AST census>"
```

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: CodeHealthClosure
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CodeHealthClosure']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CodeHealthClosure']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-09T16:53:36.670736+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CodeHealthClosure']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['CodeHealthClosure']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## NAO VERIFICADO

* No baseline refresh was executed (forbidden without authorization).
* No battery run; no app launch; no runtime claim.
* `history-context-store.js` and `sotto_webview.py` may move again after 13:56; the
  report is a snapshot. The webview file gained 85 uncommitted lines at 13:53:56 and
  was written again at 13:57:53 while this audit was running.
* Whether the genai census code can be made size-neutral without changing behavior is
  the owning lane's call — not measured here.

## SELF-AUDIT

* **protocolos em falta** — the house requires a receipt per lane; the two refreshes
  that matter (`5986e78`, `b5912be`) landed without a receipt section, and I could not
  retroactively prove intent beyond their diffs. A protocol that should exist: a
  baseline commit must name the entries it changes, or it does not land.
* **verificacao adicional** — re-running the oracle after each refresh commit
  (`git stash`-free: checkout to a temp worktree) would prove the pin equals the commit
  rather than the dirty tree. Cost: a second checkout of a large repo, and it risks
  disturbing concurrent lanes, so I did not.
* **checkboxes novas** — add a mechanical check to `code-health-oracle.py --update`:
  refuse to write when the worktree is dirty (`git status --porcelain -- <product
  files>` non-empty) unless `--allow-dirty` is passed. Input that must leave it RED:
  the current tree (three dirty/untracked product files).
* **review por outro subagente** — `sim-com-escopo` (verify the per-metric attribution
  and the `max_func`/`except_pass` claims against the cited commits).
* **gate-doubt** — `verde-de-verdade:` the exception oracle's GREEN is real for the
  current bytes, but it is green **because of an uncommitted baseline edit**; the
  committed baseline would be RED on C2. The code-health neg-arm GREEN is real (3/3
  mutants, bidirectional control). `falta-no-gate:` `--update` has no dirty-tree guard,
  so a blanket re-pin can absorb other lanes' uncommitted work — exactly what
  `5986e78` did; a future change that edits a product file and runs `--update` in the
  same minute walks straight through it. `gate-melhor:` `git status --porcelain --
  app/webview worker app/panel` non-empty ⇒ `--update` exits 2 with
  `RED dirty worktree`; the current tree must leave it RED.
