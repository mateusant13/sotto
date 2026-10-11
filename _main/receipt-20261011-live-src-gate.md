# Receipt — the LIVE `src=` gate, the redux arm's weights, and the audit map (2026-10-11)

**Lane:** Lead (verification + fix of the live writer), absorbing lane 4's redux-arm work and
lane T4's audit-map work. **No launch of any kind happened** — the owner's order stands
(*"para de abrir o sotto, ta travando meu pc quando ele abre"*). Every claim below comes from
bytes, parse, in-process imports, or a Node/jsdom run; none from a running shell or worker.

## Identity (measured this session, instrument: node reading bytes + crypto sha256)

| artefact | bytes | CRLF / bare LF | sha256 (first 16) | mtime (UTC) |
|---|---|---|---|---|
| `worker/sotto_worker.py` | 295 867 | 5 693 / 0 | `2C0AF4FB8B22D3D1` | 2026-10-11T22:24:41Z |
| `app/panel/history-store.js` | 9 766 | 0 / 256 | `0A81FD98378911FC` | 2026-10-11T22:25:13Z |
| `app/webview/sotto_webview.py` | 440 186 | 8 671 / 0 | `4295AEABED672772` | 2026-10-11T22:42:49Z |
| `app/panel/panel.html` | 56 537 | 1 020 / 0 | `EFD662DA8EB342DC` | 2026-10-11T21:20:27Z |
| `_main/canonical-producer-oracle.py` | 40 909 | 0 / 732 | `51CFD5B731DC661F` | 2026-10-11T22:49:12Z |
| `_main/redux-arm-weights-oracle.py` | 27 218 | 0 / 601 | `DA0F5FFCDCD74E7E` | 2026-10-11T22:36:30Z |
| `_main/receipt-20261011-redux-arm-weights.md` | 33 423 | 0 / 497 | `74B44AAAF5597F7E` | 2026-10-11T22:40:07Z |
| `docs/audit/00-MAPA-CONSOLIDADO.md` | 36 541 | 0 / 359 | `2D9C9F389A64CA22` | 2026-10-11T22:45:46Z |
| `_main/receipt-20261011-audit-map-t4.md` | 28 931 | 0 / 233 | `D7AD864BF4CDF125` | 2026-10-11T22:46:47Z |
| `AGENTS.md` | 87 544 | 0 / 920 | `EB1164EC69860625` | 2026-10-11T22:44:10Z |

The shell grew by **688 B** from its committed pin (`E5B4ADE7…`, 439 498 B) — that delta is a comment
block and one tuple member. CRLF preserved (8 671 / 0), which is the property every `.cmd`-adjacent
reader of this file relies on.

## Finding 1 — which of the two `src=` twins is LIVE (this REFUTES the Layout row in AGENTS.md)

Instrument: `node I:/cc-tmp/pin-src-gate.mjs`, reading `app/panel/panel.html` and regexing its
`<script src>` population.

- `panel.html` loads **11** scripts, in order: `caption-formulation.js`, `history-source.js`,
  `history-gallery.js`, `surface.js`, `themes/themes.js`, `themes/panel-designs.js`,
  `skins/skins.js`, `theme-switcher.js`, `theme-tune.js`, `skin-host.js`, `panel.js`.
- **`history-store.js` is not one of them**, and the string `history-store` does not occur in
  `panel.html` at all: **0 matches**.
- Therefore the AGENTS.md `Layout` row (`app/panel/` … "the modules the document loads
  (`caption-formulation.js`, `history-source.js`, `history-store.js`, `surface.js`,
  `theme-switcher.js`, `themes/`)"`) is **FALSE**: it lists a module the document does not load, and
  it misses six it does.
- The writer the owner's transcript actually passes through is the SHELL:
  `panel.js recordHistory` (`:1298`, gate `:1331 route !== 'final'`) → `historyApi.append` →
  shell `history-append` (`:3197`) → `history_append` (`:4630`) → `_history_provenance`
  (`:4610`), which consults `HISTORY_ROUTE_SOURCES` at **`:177`** — the Python twin of the Node
  `ROUTE_SOURCES`.
- `history-store.js` is read by **oracles only**: `_main/historico-vs-redux-probe.js`,
  `history-route-oracle.js`, `live-vs-history-source-oracle.js`, `history-producer-gate.js`,
  `_main/canonical-producer-oracle.py`.

A FIRST DRAFT of the AGENTS.md rule said "its only mention in that file is a comment at `:963`". The
count above (**0**) was taken while writing the rule and REFUTED the draft, so the shipped rule carries
the measurement and names the retraction. That is rule 1 of that file applied to itself.

## Finding 2 — BOTH twins were missing `'worker-stamped-producer'`

`caption-formulation.js routeSourceFor` returns `'worker-stamped-producer'` for a line that DECLARES a
producer while no worker `final` vote decided the route. Neither allow-list carried the token, so such a
line was written with **no `src=` marker at all** — provenance thinner than the decision that produced it.

- JS half: **LATENT.** The Node store is oracle-only (Finding 1) and `panel.js:1331` returns before any
  store for a non-`final` route.
- SHELL half: **LIVE.** `_history_provenance` is the writer of the owner's transcript.

Fixed in both; each tuple now equals the four declared tokens. The shell holds
`('worker-stamped', 'worker-stamped-producer', 'panel-deadline', 'fallback')`.

## Finding 3 — the redux arm armed on the RUNNER FILE and would have guaranteed a batch failure

Lane 4's finding, verified here by import and by the file's own anchors: `redux_batch.py` resolves its
checkpoint at `models/parakeet-redux-ternary` (runner dir + relpath), and on this box that directory is
**ABSENT** — `config.json`, `model.safetensors` and `ternary.json` all missing, while the runner file
itself exists. `ReduxHiddenSwitch.armed` was `enabled and runner_available` — i.e. it armed on the
`.py` alone. A user passing `--redux-when-hidden` would have had streaming CUT while the panel was
hidden and then every batch fail at load: the exact failure shape the repo's HARD RULE forbids.

Now `armed = enabled and runner_available and model_available`, with a loud
`REDUX_SWITCH_REFUSED armed=false reason=checkpoint-missing runner=… model_dir=… missing=config.json,model.safetensors,ternary.json`
line. Measured live, in process: `checkpoint= models\parakeet-redux-ternary missing= ['config.json', 'model.safetensors', 'ternary.json']`.

## The two oracle arms that pinned the defect — RE-BASELINED, deliberately

`_main/canonical-producer-oracle.py` went **rc=1, 43/45, VERDICT: FAIL** the moment the fixes landed,
because two of its checks were the defects written down as expected state:

1. arm B asserted `armed_switch.armed is True` *with no checkpoint on disk* — it required the bug.
2. arm C asserted the missing token was missing ("`'worker-stamped-producer'` in store_text" was checked
   in the NEGATIVE sense).

Both were re-baselined into REQUIREMENTS, and the shell's live tuple got a check of its own:

| arm | before | after |
|---|---|---|
| B | "the switch ARMS on the RUNNER FILE even when no checkpoint exists" (`armed is True`) | "the switch REFUSES to arm when the checkpoint it will LOAD is absent" (`armed is False and not model_available`), detail printing `runner_available`/`model_available`/`model_missing` |
| C (JS) | the token's absence | the token's PRESENCE in `history-store.js` |
| C (shell) | *(did not exist)* | NEW: `HISTORY_ROUTE_SOURCES` parsed out of the shell bytes equals the 4-token set |
| label | "worker arms on the RUNNER FILE only" | "worker's runner-FILE availability fact (gate 2, half one)" |
| ANSWER prose | "checks the RUNNER FILE, not the weights … then fails every batch" | "is now TWO facts … it REFUSES to arm … until 2026-10-11 the .py alone armed it" |

**A check that cannot say NO is not a check**, so the new shell arm got its own mutant: the RED arm now
reads a copy of the shell with `'worker-stamped-producer', ` dropped (delta **-27 B**, asserted unique),
and the arm goes RED on exactly the pre-fix tuple.

## Gate results (both colours, this revision)

```
py -3 _main/canonical-producer-oracle.py
  SUMMARY: 47/47 checks green; failed=[]          VERDICT: PASS          rc=0

py -3 _main/canonical-producer-oracle.py --red-arm
  RED-ARM SUMMARY: 10 of 39 checks FAILED against the mutant subject (this is the expected colour)
  VERDICT: FAIL
  FAIL [C] the SHELL's LIVE src= allow-list carries every token routeSourceFor declares
       -- HISTORY_ROUTE_SOURCES=('worker-stamped', 'panel-deadline', 'fallback')
```

The new arm is among the 10 and its failure text shows the 3-token pre-fix tuple: it can say NO.

```
py -3 -m py_compile app/webview/sotto_webview.py     rc=0
py -3 _main/per-app-source-plumbing-oracle.py        VERDICT: PASS
py -3 _main/app-target-oracle.py                     VERDICT: PASS  live=GREEN(9/9)  M1 RED  M2 RED
node _main/redux-live-contract-oracle.js              VERDICT PASS - 8/8 shipped-contract arm(s) held
node _main/panel-row-identity-oracle.js               VERDICT: PASS
py -3 _main/redux-arm-weights-oracle.py              GREEN 20/20 rc=0 ; --neg-arm PASS rc=0 (M1 W9/W10/W12,
                                                     M2 W10/W12, M3 J1/J2/J3, M4 nothing, unbuildable rc=2)
```

## The audit map (lane T4) — verified by me, not taken on report

I re-ran the gate myself: `bash I:/!manager/scripts/audit-map-gate.sh H:/sotto/docs/audit`

```
audit-map-gate: dir=H:/sotto/docs/audit map=00-MAPA-CONSOLIDADO.md docs=43
  findings_total=138 findings_distinct=138 count_rows=3 counts=applied:47/open:91/inflight:0
audit-map-gate: GREEN (rc=0) - map complete: 43/43 docs named, 138 distinct finding(s),
  every row stated, applied/open counted
GATE rc=0
```

Identical to the lane's report, stderr empty. The map was `rc=1 RED` before (34 NAMED-DOC-MISSING, 14
ROW-NO-STATE, 36 LABEL-UNMAPPED). Four states changed, each with a citable proof; **F2 stays OPEN with an
explicit NOT MEASURED** (the tree stamps `producer`, but no line has been shown to reach the
`meta.producer` the canonical gate reads).

## What this does NOT establish

- **No launch happened**, so no real line has travelled `panel.js recordHistory` → shell
  `history_append` end-to-end. The `src=` fix is proven by parse and in-process oracles, not by an
  observed file write on this revision.
- It is **not measured** that a real `worker-stamped-producer` line ever occurs in practice; the route
  needs a declared producer with no `final` vote, which is a rare combination. The fix closes the gap;
  whether the gap was being hit is unmeasured.
- The redux refusal is proven by import and by the oracle, not by a run: no run is permitted.
- T2 (startup flash) remains UNMEASURED on this revision by the owner's order; the two contradictory
  AGENTS.md numbers (0/20 at 25 ms vs 88/130 and 141/262) are still unreconciled.
