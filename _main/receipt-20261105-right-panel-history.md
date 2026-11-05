- card: [RightPanelHistory] diagnose right-panel history loss, land receipt only

# Right panel loses history — diagnosis (2026-11-05)

Owner report: *"e alias, o painel da direita fica perdendo historico. nao sei se é culpa sua."*

Read-only task: **no source was edited, nothing was launched, nothing committed.** The live
instance (pid 54040) was only *observed*: `_main/webview-run.log`, `_main/panel-state.json`
(the app's own 2 s dump) and the `history/` tree.

---

## 0. Which list the owner is looking at

The right panel (`panel.html`, surface `panel`) has **two** lists, and only one of them is on
screen:

| list | element | fed by | state today |
|---|---|---|---|
| live transcript | `#caption-list` (`panel.html:487` region is `.history`; the live box is in `.captions`) | `panel.js addCaption` | **visible**, growing |
| canonical transcript | `#history-body` inside `.history` (`panel.html:487`) | `panel.js loadHistory` → `historyApi.tail()` → the `history/` files | **collapsed, empty** |

The second one is collapsed **by construction** in this shell: `applyTranscriptMode()`
(`app/panel/panel.js:1946`) only expands the drawer when `canonicalProducer` is truthy, and
`SottoShell.history_root()` returns `{'root': HISTORY_ROOT, 'canonicalProducer': None}`
(`app/webview/sotto_webview.py:12846`). So the "history" the owner watches in the right panel
is `#caption-list` — the live box, capped at 200 rows.

This matters because it rules the whole `history-store` question out: `recordHistory`
(`panel.js:2055`) refuses every live line (canonical-producer guard in
`app/panel/history-source.js`), so the file store and the panel list are **not** the same data.

---

## 1. Hypothesis (one, falsifiable)

**H.** The panel never deletes a row except at the cap: `addCaption` appends one `<li>` per
commit and trims the oldest while `#caption-list.childElementCount > MAX_CAPTIONS` (200).
Because *every* commit of the live path produces a row (including a **duplicate** of a line the
list already holds), the list reaches 200 in ~8 minutes of speech and from then on **deletes one
real line per append**. That rolling window — not a reload, not a surface switch, not a store
read — is the "losing history".

**Observation that would refute it:** the list pinning at a number other than 200, or the same
oldest row staying on screen while new rows arrive, or the count resetting to 0 (a reload), or
rows disappearing from the middle (a delete path other than the trim).

---

## 2. The falsifying check, run against the live panel

Sampler: `_main/panel-state.json` polled every 5 s (the app's own `PANEL_STATE_PROBE`,
`sotto_webview.py:9346`, which reports `#caption-list.childElementCount`);

```
python - <<'PY'   # read-only poll of _main/panel-state.json
... rows=[l['text'] for l in d['panel']['live']['lines']] ...
    print(f'{ts} rows={len(rows)} rewritten={rew} oldest_dropped={prev[0] not in rows} first={rows[0][:40]!r}')
PY
```

Verbatim output (excerpt; full run 16:28:41 → 16:32:06):

```
16:28:41 baseline rows=129 first='Three of these items too constantly be a'
16:29:41 rows=151 rewritten=0 oldest_dropped=False first='Three of these items too constantly be a'
16:30:41 rows=180 rewritten=1 oldest_dropped=False first='Three of these items too constantly be a'
16:31:21 rows=199 rewritten=1 oldest_dropped=False first='Three of these items too constantly be a'
16:31:25 rows=200 rewritten=0 oldest_dropped=False first='Three of these items too constantly be a'
16:31:31 rows=200 rewritten=200 oldest_dropped=True first='Cooldowns with every tick combine this w'
16:31:42 rows=200 rewritten=199 oldest_dropped=True first="Enemies will run and dash slower they'll"
16:31:52 rows=200 rewritten=200 oldest_dropped=True first='Sitting there.'
16:31:56 rows=200 rewritten=200 oldest_dropped=True first='Deali ng up to six hundred damage in a c'
16:32:02 rows=200 rewritten=200 oldest_dropped=True first='Ulti ma ability and scrap armor that ref'
16:32:06 rows=200 rewritten=149 oldest_dropped=True first='Surface with them let.'
```

**Result: the hypothesis survives.** `rows` climbs 129 → 200 and pins at exactly
`MAX_CAPTIONS`; from 16:31:31 on, the entire 200-row list shifts every sample and
`oldest_dropped=True` — the panel is now evicting continuously. No reset, no mid-list
disappearance.

Retention, measured: the oldest row in the 200-row list at `16:32:36` is
`'The, rat how hard it to kill an art student.'`, first painted at **16:24:59.898** per
`CAPTION_APPLIED`. The panel therefore holds **7 min 37 s** of transcript and everything
earlier in the session is already gone.

**Alternatives this same run refutes:**

* *"the list is reloaded from an empty/stale source"* — no. `loadHistory()` has exactly one
  caller (`wireHistory`, `panel.js:1848` → `1924`) reached once from the init block
  (`panel.js:956`); `shell.reloadCount = 0` in `panel-state.json`; no `PANEL_NAV*` after
  10:42 today; 18 `PANEL_SURFACE` switches today and none of them touched the list
  (`applySurface`, `panel.js:2600`, is paint-only).
* *"the store lost the lines"* — no. Today's store is **empty**: see §3.
* *"a delete path other than the trim"* — no. `#caption-list` has exactly four mutators
  (`panel.js`: `dom.list.append` ×2 at 1376/1626, `removeChild` at 1460 for the *provisional*
  row, `removeChild(first)` at 1648 for the cap). Sampling caught no other deletion.

---

## 3. Numbers: store vs panel

```
$ ls -d history/2026-11-05
ls: cannot access 'history/2026-11-05': No such file or directory
$ grep "2026-11-05" _main/webview-run.log | grep -c "HISTORY_"
0
$ grep "HISTORY_" _main/webview-run.log | tail -2
120577:2026-11-04 11:54:10.540 sotto: HISTORY_APPEND path="H:\\sotto\\history\\2026-11-04\\11.md" time=11:54:10 bytes=48
124093:2026-11-04 12:16:09.887 sotto: HISTORY_APPEND path="H:\\sotto\\history\\2026-11-04\\12.md" time=12:16:09 bytes=77
```

| moment | rows in the store (`history/`) | rows in `#caption-list` | evictions since the last sample |
|---|---|---|---|
| 16:19:xx (app start) | 0 lines today | 0 | 0 |
| 16:28:41 | 0 | 129 | 0 |
| 16:31:25 | 0 | 200 (= cap) | 0 |
| 16:31:31 → 16:32:06 | 0 | 200 | ~3 rows per 5 s sample |

So the panel is not "losing" lines the store still has — the store **has never held them**. The
live nvidia/punctuation path is refused by `history-source.js` by design, and the canonical
batch pass has written nothing since 2026-11-04 12:16. `#caption-list` is the only copy of what
was said.

---

## 4. Why it fills (and therefore loses) twice as fast: the duplicate append

`writtenAt 16:32:24, count 200` — **51 of the 200 rows (25.5 %) are exact duplicates of the
row two positions back** (A, B, A):

```
rows 0/2:   "A glorified salesman why isn't that skeleton staying dead fair f"   between: 'The.'
rows 7/9:   'Obscurity where it belongs the chest pla is making his move befo'   between: 'Want.'
rows 10/12: "Want Solomon's mangled orps rotting incent fork."                  between: 'Sho.'
rows 23/25: "Nobody has their own side anymore, that's too bad for twenty six"   between: 'Years when you.'
rows 60/62: 'Lo level engineers with one giant scre no sunt and sufficient vi'   between: 'Compete. The.'
... (51 pairs; the census script is quoted in §2's provenance)
```

The mechanism, traced end to end in the log (`_main/webview-run.log`, 16:23:02 → 16:23:06):

```
16:23:02.429 CAPTION_IN start=None end=12.88 final=false  text="cooldowns with"          <- line S begins (no start)
16:23:02.429 CAPTION_IN start=7.28  end=12.32 final=true  text="three of these items ..."  <- line L closes
16:23:02.434 CAPTION_APPLIED text="Cooldowns with."                    kind=final
16:23:02.442 CAPTION_APPLIED text="Three of these items too constantly ... their." kind=final
16:23:02.948 CAPTION_APPLIED text="Cooldowns with every."             kind=partial
...
16:23:06.388 CAPTION_APPLIED text="Continue."                          kind=final
16:23:06.391 CAPTION_APPLIED text="Cooldowns with every tick ... just." kind=final  <- S's final, AFTER the next line's commit
```

`S`'s partials merged into one row by the prefix rule; when S's own `final` finally lands, the
last row of the source is no longer S's row (the next sentence's first commit took that slot),
so `isPrefixExtension(rowText(lastOfSource), text)` is false and `addCaption` **appends a second
row with text the list already holds** (`panel.js:1570-1572` → `1626`).

`meta.start` is what would have made this a replace instead of an append, and the live worker
omits it most of the time:

```
$ grep "2026-11-05" _main/webview-run.log | grep -c "CAPTION_IN start=None"
2371
$ grep "2026-11-05" _main/webview-run.log | grep -cE "CAPTION_IN start=[0-9]"
950
```

2371 / 3321 = **71 %** of today's `CAPTION_IN` carry no `start`; for those lines the only
identity the panel has is "does the text continue the LAST row of the source" — and a row that
is no longer last is invisible to that test.

The same fallback also *overwrites*: at 16:26:58 a row was rewritten `'… do you see.'` →
`'… do you.'` (a re-read that cut the line), and at 16:26:46→16:26:50 row 54 went
`'Stop and.'` → `'Shared.'` → `'S super I like the olders …'`. Both are the same
`existing` branch (`panel.js:1587-1625`), both destroy text the owner had already read.

---

## 5. Offending path

| file:line | what it does |
|---|---|
| `app/panel/panel.js:41-42` | `MAX_CAPTIONS = 200` — the only bound on the visible transcript |
| `app/panel/panel.js:1636-1648` | `while (childElementCount > MAX_CAPTIONS) removeChild(first)` — deletes the oldest real line on every append once the list is full |
| `app/panel/panel.js:1555-1557` | row lookup is `committedByStart.get((source,start))`; **null whenever the worker omits `start`** (71 % of today) |
| `app/panel/panel.js:1570-1573` | the only fallback: prefix test against `lastRowForSource(source)` — a *positional* test that cannot find a row that is not last |
| `app/panel/panel.js:1626` | the append that creates the duplicate |
| `app/webview/sotto_webview.py:9346` (`PANEL_STATE_PROBE`) | the only instrument, and it reports `#caption-list` only — no field counts `#history-list` |

---

## 6. Verdict

**CAUSE: `app/panel/panel.js:1636-1648` — `#caption-list` is a rolling 200-row window: once it fills (measured at 16:31:25, 7 min 37 s of transcript), every commit deletes the oldest visible line, and because `meta.start` is absent on 71 % of live commits the row lookup at `panel.js:1555-1557` falls back to a prefix test against the LAST row only (`panel.js:1570-1572`), so a line's late `final` re-appends text the panel already holds (measured: 51 of 200 rows are exact A,B,A duplicates) and the window is pushed to eviction twice as fast.**

Not a store bug, not a reload, not a surface switch: the canonical transcript is empty today
(0 `HISTORY_` lines, no `history/2026-11-05`) and the drawer that would show it is collapsed by
design (`sotto_webview.py:12846` → `canonicalProducer: None`).

Residual honestly stated: the 200-row cap is a *declared* design choice ("matching
`MAX_CAPTIONS` in the shell"), so whether it is "too small" is the owner's call. What is not a
design choice is the duplicate append — that one has a single separating measurement, already
run: **51 A,B,A pairs of 200** at 16:32:24. If those were merged, the same window would hold
~13 minutes of speech instead of 7.6.

---

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: RightPanelHistory
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RightPanelHistory']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RightPanelHistory']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-05T19:33:25.194670+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RightPanelHistory']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RightPanelHistory']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

---

---

## SELF-AUDIT
- **protocolos em falta** — I did not first declare a `todo` card: this toolset has no `todo`
  tool, so per the START block the card line opens this result and the `done` closes it. Also
  missing: I should have checked `git log` for the running shell's code identity *before*
  reading `sotto_webview.py`; the file is being edited right now (mtime 16:21, `M`) and
  `shell.stale: true` in `panel-state.json`, so every shell line number below is an anchor in
  the *current* file, not in the bytes the running process loaded. The panel half (`panel.js`,
  mtime 06:13, committed in `ebd578c`) *is* the running code — the diagnosis rests on that half.
- **verificacao adicional** — a DOM read of `#caption-list` row `data-start`/`dataset.revision`
  would have shown directly which rows were `revision=true`, confirming the append-vs-replace
  split per row. Cost: needs `exec_js` into the live WebView, which this task forbade. Cheap
  substitute used: `CAPTION_APPLIED` (one line per commit) + the state dump's row texts.
- **checkboxes novas** — (1) `python -c "json…; assert live['count'] <= 200"` in the panel
  state gate: a count that pins at the cap for two consecutive dumps is a FAIL, because it
  means the transcript is being evicted. (2) a duplicate census
  (`sum(rows[i]==rows[i-2])` over the dump) asserted `< 2 %` of rows — today it is 25.5 %.
- **review por outro subagente** — `sim-com-escopo` the panel half (`addCaption` identity
  fallback and the trim), since that is where the cure lands.
- **gate-doubt** —
  (a) `verde-de-verdade:` the green I was handed was "a `panel-prefix-row` cure exists (commit
    landed 2026-11-05)". That green is real *for the arm it tests* (`isPrefixExtension` merges a
    prefix when the row is last) but it is **vacuous for the live case**: the oracle
    (`_main/panel-prefix-row-oracle.py`) feeds the function directly, so it can never observe
    that the row it compares against is the wrong row. The commit message's own measurement
    ("nove `<li>` para a MESMA frase") is the wall; the panel today shows the same wall with
    **duplicates** instead of prefixes, and the oracle stays green.
  (b) `falta-no-gate:` nothing measures `#caption-list` against the commit stream. `PANEL_STATE_PROBE`
    (`sotto_webview.py:9346`) has no history field, and no gate compares
    `len(dump.live.lines)` with the number of distinct `CAPTION_APPLIED` texts. A future change
    that appends two rows per commit walks straight through every green.
  (c) `gate-melhor:` mechanical check —
    `python _main/panel-dup-gate.py` reading `_main/panel-state.json`: FAIL when
    `sum(rows[i]==rows[i-2] for i in range(2,len(rows))) > 2` or when `count == 200` in two
    consecutive dumps. Input that must leave it RED: today's snapshot (51 duplicates, count 200).
    Today it does not exist; that is the hole.
- **confianca** — `alta` for the mechanism (traced in the log and reproduced in the live
  dumps); `media` for the exact eviction rate (audio pauses make it non-linear). What would move
  it to `alta`: a DOM read of `data-start`/`dataset.revision` on the live list.
- **nao verificado** — (1) `history-store.js`/`history-gallery.js` runtime behaviour (Electron
  arm, not served here, and the drawer is collapsed anyway); (2) the bytes actually loaded by
  the running shell (`shell.stale: true`); (3) whether any *other* surface (strip) has a
  different cap — the strip shares the same `#caption-list`.

---
