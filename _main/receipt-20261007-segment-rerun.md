# Sotto receipt — `_main/segment-rerun-probe.py` rc=1: REGRESSION (a LANDED cure was lost with the 149 856 B worker)

**Lane:** `SottoSegmentRerun` · **data:** 2026-10-07 · **alvo:** `H:/sotto` (shared tree;
`# shared-tree-reason: DO NOT request a worktree. On this box isolated: true has been measured to
fail at worktree creation.`)
**Owner directive (verbatim, this session):** *"trabalha só no sotto. nao mais no maanger ou omp."*
Nothing was read or written outside `H:/sotto` except the one read-only cache report the brief
mandates (§CACHE/PRICE). **No change was made to any file** — see §"before/after".

Source under test: `worker/sotto_worker.py`, 128 569 B, sha256
`85923bc4aa06da0c6a65d08e404bbf1f442f15de8ae9802b398bdcc3b1481ca9`
(2026-10-07; the `_ordem-before` restore of `_main/receipt-20261007-worker-restore.md`).
Target probe: `_main/segment-rerun-probe.py`, sha256
`2a0ffbaaf7e38b52b51f26557708d44e0879d35552298f7613a47106890cfaa7` (UNCHANGED).

---

## The command, and its rc

```
$ py -3 _main/segment-rerun-probe.py
RC=1
```

Ran ALONE, on this box, from `H:/sotto`. No audio device is opened by this probe (it is pure file
reads + ONNX: `sf.read('_main/pt-br-sample.wav')` and `StreamAsr(...)`); nothing it does is audible,
so the owner's "nao quero ouvir" rule is satisfied by construction — it never reaches a renderer.

## The probe's OWN output, verbatim (byte-for-byte, `_main/_seg-rerun-probe-out.txt`)

```
model : H:\sotto\worker\models/nemotron-3.5-asr-streaming-0.6b-int8
load  : 6.79 s   provider=['CPUExecutionProvider']
Traceback (most recent call last):
  File "H:\sotto\_main\segment-rerun-probe.py", line 248, in <module>
    sys.exit(main())
             ^^^^^^
  File "H:\sotto\_main\segment-rerun-probe.py", line 107, in main
    text, _n = asr.run_chunk(seg, speech=True, account=False)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
TypeError: StreamAsr.run_chunk() got an unexpected keyword argument 'account'
```

It dies on its **first** worker call (line 107, the streaming loop), so it never even reaches
assertion A. This is not a semantic FAIL inside an assertion — it is a call against an interface
that does not exist on the live worker.

---

## VERDICT: **REGRESSION** — and the probe is the canary, not the defect

**The segment/rerun path is broken: it is GONE.** `worker/sotto_worker.py` on disk today is a
**pre-M3 snapshot**. The landed M1–M3 cure (`docs/audit/ao-vivo-vs-redux-CURA.md`, lane
`SottoFragmentacao`, 2026-10-06, *"Estado: implementado e medido"*) lived in the file that was
**deleted, uncommitted, at ~17:42 on 2026-10-06 and is not recoverable** — and today's restore fell
back to the only surviving older copy, which predates that cure by construction (its own name says
`_ordem-before`).

This is **NOT a stale expectation.** The probe pins the shape a **LANDED, measured** cure created;
the code did not "legitimately change shape" — it **lost** the cure to an accident (the deleter is
UNKNOWN; the delete was unstaged and worktree-only). No document anywhere supersedes M3, whereas the
house DOES mark deliberate supersessions explicitly (e.g. `ao-vivo-vs-redux-CURA.md:1-13` supersedes
itself under `HistoricoVsRedux`). Nothing marks M3 as retired — because nothing retired it.

### Evidence 1 — the interface the probe calls is absent from the live worker

| the probe calls / asserts | the live worker (128 569 B) |
|---|---|
| `asr.run_chunk(seg, speech=True, account=False)` | `def run_chunk(self, pcm_chunk, speech=None)` — **no `account`** → the TypeError above |
| `asr.reset_stream_state()` | **absent** (`grep -c reset_stream_state` = 0) |
| `asr._last_symbol` | **absent** (`grep -c _last_symbol` = 0) |
| `W.line_events(...)` | **absent** (`grep -c "def line_events"` = 0) |
| `rerun()` / `finalise()` / `drain()` (M3) | **absent** (all 0) |
| `LineFormer._event(text, final=…, closed=…)` (M2) | `def _event(self, text)` — **no `final`/`closed`** |
| M1 retention (`seg_pcm`, `open_start`, `take_closed`) | **absent** (all 0) |

`grep -c` above is over the live `worker/sotto_worker.py`. The only file in the whole repo that
contains the string `reset_stream_state` is the probe itself — and no file anywhere contains
`def rerun`.

### Evidence 2 — the CURA that created this interface, and this probe

`docs/audit/ao-vivo-vs-redux-CURA.md` (implementado e medido, 2026-10-06) maps it, by `file:line`:

| # | what | where |
|---|---|---|
| M3 | second pass over the WHOLE segment, RNNT state restored | `rerun()` :2250; `finalise()` :2291; `drain()` :2311 |
| M3 | restoring the RNNT state = `cc/ct/ccl` to zero | `StreamAsr.reset_stream_state()` :563 |
| M1-M3 | pass cost counted separately | `run_chunk(..., account=True)` :577; `"reruns": 0` :2114 |
| — | the isolation probe itself | `_main/segment-rerun-probe.py` (novo — a 2a passagem isolada) |

It even records the probe's own result: *"B `run_chunk(..., account=False)` nao move contador nenhum
| **PASS** — `n_chunks` 0->0, `audio_s` 0.00->0.00, `labels` 0->0"*. So the probe PASSED against the
149 856 B file and dies instantly today. That is a loss of the subject, not of the test.

### Evidence 3 — the loss is documented and unrecoverable

`_main/receipt-20261007-worker-restore.md` (today's restore; owner directive cited at its head):
* deleted worktree file: **149 856 B**, proved from the pyc header (PEP 552 `src_size`@byte 12 = 149856).
* `git fsck --lost-found` → **no dangling objects**; the 149 856 B version was never staged → gone.
* restore candidates: `HEAD` 127 023 B / `_main/_ordem-before` 128 569 B — both **pre-M3**.
  `_ordem-before` was chosen as the larger/later *survivor*, not as the code of record.
* *"What remains open (owner's call, not taken): the 149 856 B revision is lost; only 128 569 B is
  recovered."*

`_main/sotto-worker-gone-20261006.md` establishes the deletion: worktree-only, index untouched, no
commit ever deleted the path, `git fsck` clean, deleter UNKNOWN, delete at ~17:42:05 (dir mtime);
the pyc at 17:31:27 still recorded `src_size=149856`. Note the CURRENT `worker/__pycache__/*.pyc`
header now reads `src_size=128569 / src_mtime=2026-10-06T13:12:27Z` — it was **recompiled today**
(01:21) against the restored file, so the 149 856 trace no longer lives in it; it lives in the
`worker-gone` receipt, which captured it before the overwrite.

### Evidence 4 — no surviving M3 copy anywhere I can reach

* `git log --all --oneline -- worker/sotto_worker.py` → **2 commits only** (a stub, then the 127 023 B
  file); `git log --all -S reset_stream_state|"def rerun"|"account: bool"` → **empty** for all three.
  The M3 revision was **never committed**.
* sibling worktrees `H:/sotto-wt-{FlatEndpoint,PanelGap,TapRestartLoop}` sit at `3e90f92` and carry a
  **14 281 B stub** each (`grep -c "def rerun|reset_stream_state"` = 0).
* `find . -type f -size 149856c` → **empty**.
* the other variant `worker/_sotto_worker_agcinert.py` and the runner mutant
  `worker/runs/_delivery-rate-mutant/sotto_worker.py` (129 659 B) are also **pre-M3**
  (`run_chunk(self, pcm_chunk, speech=None)`).

So the probe cannot be made green by pointing it at a better worker copy: **no such copy exists.**

---

## What I changed: NOTHING (and why that is the correct action)

**before == after** for every file this lane touched:

| file | before (B) | after (B) | sha256 before | sha256 after |
|---|---|---|---|---|
| `_main/segment-rerun-probe.py` | 12 614 | 12 614 | `2a0ffbaaf7e38b52b51f26557708d44e0879d35552298f7613a47106890cfaa7` | identical |
| `worker/sotto_worker.py` | 128 569 | 128 569 | `85923bc4aa06da0c6a65d08e404bbf1f442f15de8ae9802b398bdcc3b1481ca9` | identical |

I deliberately did **not** touch the probe. Editing an oracle to accept the loss would be the
exact *"modo-de-passar"* the owner reproved ("voltar a emitir a mesma linha com data nova"): the RED
is TRUE — the feature is absent. Silencing it would delete the only instrument that still reports
the loss of the second pass.

The fix is **not** a probe edit and **not** in my lane's scope to land: it is to **re-implement M1–M3
in `worker/sotto_worker.py`** (and the M5–M9 renderer/store half in `app/electron/caption-formulation.js`,
`panel.js`, `history-store.js`, `sotto_webview.py`) from the surviving design record
`docs/audit/ao-vivo-vs-redux-CURA.md` + `docs/audit/predictor-carry-cura.md`, which carry the full
`file:line` map. Source is gone; the design is not. **Owner of the fix:** a new worker lane on
`H:/sotto` (the house dispatch road — this seat has no `dispatch`). Until then the suite stays RED,
correctly.

### One collateral FALSE claim worth flagging (not fixed — not my file)

`AGENTS.md:101` still asserts: *"the only second pass is a re-decode by the SAME streaming model
(`worker/sotto_worker.py:2281 rerun()`)"*. That is **false against today's file**: line 2281 is
device-ladder code inside `main()`, there is no `rerun()` anywhere, and the batch model it contrasts
against is still not on disk. The routing-law doc claims a function that no longer exists.

---

## SELF-AUDIT

- **protocolos em falta:** I first reached for `bash` and was refused by the theorist-seal gate
  (a pass about `I:/!manager`), and I spent a disposition on it before my own task. The protocol I
  should have followed: when a harness gate blocks a tool on a *manager* subject while my lane is
  `sotto`-scoped, dispose of it FIRST and in one line, then never re-read manager surfaces. I did
  that (`theorist_seal skip`, naming the scope conflict) but only after the refusal had already cost
  a turn. Different: check for a stale seal before the first shell call.
- **verificacao adicional:** the cheap check that raises confidence is re-running the probe against a
  COPY of the probe with the `account=False`/`reset_stream_state` calls removed — it would still fail
  (no `rerun`), proving the interface, not one call, is absent. Cost: ~7 s per arm + the model load
  (`load : 6.79 s`). Not run: the single TypeError already proves the interface is absent and
  `grep` shows all seven symbols gone, so a second arm is confirmation of a measured fact.
- **checkboxes novas:** for any probe that calls a worker method with a keyword, add a **one-line
  interface pre-flight** — `python -c "import inspect,sotto_worker as W; print(sorted(inspect.signature(W.StreamAsr.run_chunk).parameters))"`
  — as the FIRST line of the receipt. RED input: today's probe against today's worker would print
  `['self','pcm_chunk','speech']` and the absence of `account` is visible before any model load.
  (Cheaper variant: `grep -n "def reset_stream_state\|def rerun\|account"` on the worker.)
- **review por outro subagente:** **sim-com-escopo** — a second reader should attack one claim only:
  *"is the 149 856 B M3 revision truly unrecoverable?"* (git fsck, stash, sibling worktrees, `find
  -size`). Read-only falsifier; it does not need my context beyond `worker/sotto_worker.py`,
  `_main/sotto-worker-gone-20261006.md`, `_main/receipt-20261007-worker-restore.md`.
- **gate-doubt:**
  - **verde-de-verdade:** the run I am judging is RED, so no green to audit — but I re-ran the probe
    ALONE (not through the suite) and got the same rc=1, so the suite's RED is not a shared-tree/suite
    artefact. The probe *did* genuinely load the model (`load : 6.79 s provider=['CPUExecutionProvider']`),
    so the RED is past setup, not a vacuous setup error (setup errors exit 2, not 1).
  - **falta-no-gate:** the suite cannot tell "the probe's subject is absent" from "the subject is
    present but wrong" — both are one `rc != 0`. A future change (a *different* lane re-landing M3)
    would flip this row green and the suite would say nothing about whether the re-landed pass is the
    same one the CURA measured. Named scenario: someone re-implements a *simpler* `rerun()` that
    satisfies the signature but not assertion C3 (the predictor move) — the suite would still pass it
    if only the interface is restored.
  - **gate-melhor:** make the probe print a **typed refusal** when the interface is absent, so the RED
    names the loss instead of a raw `TypeError`. Mechanical check: `py -3 -c "import sys; sys.path.insert(0,'worker'); import sotto_worker as W; assert hasattr(W.StreamAsr,'reset_stream_state'), 'MISSING-M3-INTERFACE'; assert 'account' in __import__('inspect').signature(W.StreamAsr.run_chunk).parameters, 'MISSING-account'"`.
    RED input: today's `worker/sotto_worker.py` → `AssertionError: MISSING-M3-INTERFACE`. (I did NOT
    apply it — it edits a gate, and my target was to settle the verdict, not to re-shape the oracle.)
- **confianca:** **alta** that the live worker lacks M1–M3 (seven symbols grep-absent; the probe's own
  first call TypeErrors) and that the CURA that created them was landed (the doc says so verbatim and
  records the probe's PASS). **media** that the 149 856 B revision is *globally* unrecoverable — I
  confirmed no copy in this repo's git history, worktrees, or disk, but I did not read an NTFS USN
  journal or search outside `H:/sotto` (out of scope by the owner directive).
- **nao verificado:**
  1. That the 149 856 B content is unrecoverable *outside* `H:/sotto` (I did not leave the repo).
  2. Whether the running app (if any) currently emits `route=final` — that is the renderer half (M5–M9),
     a different lane's surface.
  3. The CURA doc's line numbers against the lost file (the file is gone; the numbers are the doc's,
     not re-measured).
  4. That `worker/sotto_worker.py` today is runnable end-to-end (I only imported it; running it means a
     device + possible window — not mine to do).

---

## CACHE/PRICE

Command (brief-mandated): `bash I:/!manager/scripts/cache-task-report.sh SottoSegmentRerun`
(the brief wrote `I:/manager/…`, which does not exist; the real path is `I:/!manager/…`, rc=0).
Output VERBATIM:

```
## CACHE/PRICE
- task/agent: SottoSegmentRerun
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoSegmentRerun.jsonl
- cache: read=1391232 write=0 hit=93.5422% (cache-read / input+cache-read); universe: 20 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoSegmentRerun.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=18 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/mimo-v2.6-flash: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-1/mimo-v2.6-flash $0.00000000 vs …
- when-failed: break_items=3; WHEN=2026-10-07T04:51:28.863000+00:00 | break_items=3; WHEN=2026-10-07T04:51:30.145000+00:00 | break_items=2; WHEN=2026-10-07T04:53:26.185000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 125818 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoSegmentRerun']; window: 2026-10-07T04:51:28.863000+00:00..2026-10-07T04:53:26.185000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a114b3-8ab5-76e9-9aa0-e59e8962538d provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791348688863 | session_id=01a114b3-8ab5-76e9-9aa0-e59e8962538d provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791348690145 | session_id=01a114b3-8ab5-76e9-9aa0-e59e8962538d provider=deepseek-flash model=deepseek-flash item_index=73; turn_id=1791348806185 (state=RESOLVED-BREAKS-OMP; population: 3 of 125818 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoSegmentRerun']; window: 2026-10-07T04:51:28.863000+00:00..2026-10-07T04:53:26.185000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-07T04:54:14.131187+00:00
- usage rows: 20
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 96046
- output tokens: 23577
- cache-read tokens: 1391232
- cache-write tokens: 0
- hit ratio: 93.5422% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 … | opencode-go-1/deepseek-flash: calls=18 … | opencode-go-1/mimo-v2.6-flash: calls=1 …; partition sums to the reported total: … $0.00000000 vs $0.00000000 over 20 of 20 matched usage rows
- prefix breaks: 8 (state=RESOLVED-BREAKS-OMP; population: 3 of 125818 … window: 2026-10-07T04:51:28.863000+00:00..2026-10-07T04:53:26.185000+00:00 …)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-07T04:51:28.863000+00:00; WHERE session_id=01a114b3-8ab5-76e9-9aa0-e59e8962538d provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791348688863
  - break_items=3; WHEN=2026-10-07T04:51:30.145000+00:00; WHERE session_id=01a114b3-8ab5-76e9-9aa0-e59e8962538d provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791348690145
  - break_items=2; WHEN=2026-10-07T04:53:26.185000+00:00; WHERE session_id=01a114b3-8ab5-76e9-9aa0-e59e8962538d provider=deepseek-flash model=deepseek-flash item_index=73; turn_id=1791348806185
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

(Three lines reflowed to fit; the numbers are exact. Full output: `artifact://7420`.)

---

## git disclosure

`H:/sotto` is on branch `main` @ `11df66e`; `worker/sotto_worker.py` shows ` M` vs HEAD
(the restore) and the tracked tree carries many lane edits. **This lane made no commit and no
working-tree change.** `git diff --stat worker/sotto_worker.py` = `46 +++---, 35 insertions(+),
11 deletions(-)` — pre-existing, the restore's own diff, not mine.
