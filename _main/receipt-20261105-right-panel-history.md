- card: [RightPanelHistory] diagnose right-panel history loss, land receipt only

# Right panel loses history — diagnosis (2026-11-05), and the cure that followed

Owner report: *"e alias, o painel da direita fica perdendo historico. nao sei se é culpa sua."*

**This ticket opened read-only.** §0-§6 are that diagnosis, measured without editing anything
(`_main/webview-run.log`, `_main/panel-state.json`, the `history/` tree; nothing launched). The
orchestrator then directed the cure of the SECOND cause found in §3, and §7-§10 are that cure:
sources edited (`app/panel/history-source.js`, `app/panel/panel.js`,
`app/webview/sotto_webview.py`, `app/panel/history-store.js`), one oracle added, two battery
steps added, still nothing launched and nothing committed by this lane.

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

## 7. The second cause: the transcript had ZERO writers, and the refusal was mute

§3 said "the store has never held them". The orchestrator asked for the class, not the symptom.
Traced to one door:

| file | what it did |
|---|---|
| `app/panel/history-source.js:51` | `isCanonicalLine(meta)` = `producerOf(meta) === 'redux'` — the ONLY producer it admits |
| `app/panel/panel.js:2145-2162` (pre-cure) | `const route = …transcriptRoute(meta); if (!route) return;` then a SECOND gate `if (!isCanonical || !isCanonical(meta)) return;` — a bare `return`, no line anywhere |
| `worker/redux_batch.py` | the only engine that stamps `producer:'redux'`, and the batch pass is OFF by default (`--redux-when-hidden`) |

So on this box the transcript had **no writer at all** — and the panel could not say so. The
measurement, on the owner's own log (the whole 22 MB file, not a window):

```
$ grep '2026-11-05' _main/webview-run.log | grep -c CAPTION_APPLIED   # the panel painted
3853
$ grep -c HISTORY_APPEND _main/webview-run.log                        # the store wrote (all runs)
851
$ grep '2026-11-05' _main/webview-run.log | grep -c HISTORY_APPEND    # ...today
0
$ grep '2026-11-05' _main/webview-run.log | grep -c 'HISTORY_'        # ...any history event today
0
$ grep "HISTORY_APPEND" _main/webview-run.log | tail -1               # the last write ever
2026-11-04 12:16:09.887 sotto: HISTORY_APPEND path="H:\\sotto\\history\\2026-11-04\\12.md" ...
$ grep -c HISTORY_REFUSED _main/webview-run.log                       # and the refusal said
0                                                                    # nothing at all
$ ls -d history/2026-11-05
history/2026-11-05 ABSENT
```

**CAUSE (2): `app/panel/panel.js:2162` (pre-cure) — `if (!isCanonical || !isCanonical(meta)) return;`
drops every line whose meta carries no `producer:'redux'`, which is every line this box
produces (the batch pass is off by default), and it drops it with a bare `return`, so the
empty transcript and the 3853 captions it refused today are indistinguishable in the log.**

The executed proof, before any edit, on the REAL module:

```
$ node -e "const m=require('./app/panel/history-source.js'); …"
live closed line (device)  route= null  producer= null  canonical= false
youtube closed cue         route= null  producer= null  canonical= false
batch redux line           route= "batch"  producer= "redux"  canonical= true
```

A CLOSED line (`route:'final'`, the worker's own second pass / the audio gap) was refused for
having no producer — the owner's caption, every time.

---

## 8. The cure (what each file now does)

| file:line | change |
|---|---|
| `app/panel/history-source.js:historyDecision` | ONE decision replaces the two questions: `route==='final'` → `final`; a canonical (batch) line with no route → `batch`; `provisional-draft` / unknown / nothing → `null`. The producer is no longer an admission gate. |
| `app/panel/history-source.js:historyRefusal` | why the decision said no (`reason`, `route`, `producer`, `src`) — `null` when it said yes |
| `app/panel/panel.js:2145-2171` | one guard, and a refusal is REPORTED (`reportHistoryRefusal`) instead of returned |
| `app/panel/panel.js:2225-2256` | the reporter: counts per signature, sends the 1st and every 50th; payload carries `where`, `reason`, `route`, `final`, `producer`, `src`, `n`, `total` |
| `app/panel/panel.js:2187-2194` | `options.producer` forwarded, so the line names its source |
| `app/webview/sotto_webview.py:9774-9776` | `history-refused` verb in the dispatch map |
| `app/webview/sotto_webview.py:10145` | `SottoHost._history_refused` → `HISTORY_REFUSED where=… reason=… route=… final=… producer=… src=… n=… total=…` |
| `app/webview/sotto_webview.py:806-814`+`12904` | `HISTORY_PRODUCERS = ('redux','live')`; `producer=` stamped on the line next to `route=` |
| `app/webview/sotto_webview.py:12999` | the store's own `provisional-draft` refusal now says `where=history_append` too |
| `app/webview/sotto_webview.py:history_root` | `canonicalProducer` no longer `None`: a writer EXISTS, so the drawer expands and the feed/search stop being decorative |
| `app/panel/history-store.js:60-66,98-102` | the Node twin writes `producer=` from the same vocabulary — both writers, one shape |

The owner's 2026-10-07 separation is NOT deleted, it is moved: the transcript now carries every
CLOSED line and each line says `producer=redux|live`, so a Parakeet line and a streaming line
stay tellable apart **in the file**, which is what that quote was reaching for. The
`provisional-draft` refusal (owner 2026-10-06, *"o historico simplesmente mostra a legenda ao
vivo"*) is untouched, at both the panel and the store.

---

## 9. Evidence: the oracle, the numbers, the pair

`_main/history-write-oracle.py` — four arms over the LIVE code, nothing re-implemented here:
(A) the decision table; (B) the REAL `recordHistory` and `reportHistoryRefusal`, lifted out of
`panel.js` by brace matching at run time; (C) the REAL `_history_provenance`, AST-extracted;
(D) the REAL `history_append` (+ `history_merge`, `_history_tail`) writing into a TEMP root.

```
$ python _main/history-write-oracle.py
  A historyDecision: 9/9
  B recordHistory (call site): 8/8
  C _history_provenance: 4/4
  D history_append -> disco: 6/6
VERDICT: PASS — a closed caption line (live or batch) reaches the
         transcript with its producer on the line; a provisional
         draft is refused AND says why.
LIVE rc=0

$ python _main/history-write-oracle.py --neg-arm
  FAIL live-closed / FAIL youtube-closed            (the old producer gate, in a COPY)
  FAIL panel:live-closed / panel:youtube-closed     (the call site, in a COPY)
  FAIL prov-live / FAIL prov-redux                  (no `producer=`, in a COPY)
NEG-ARM: PASS — the closed-line arms go RED under the old refusal
NEG rc=1   (EXPECTED for an expect-red step; log carries "NEG-ARM: PASS")
```

The same claim, measured end to end through the real engine and the real store
(`_main/live-vs-history-source-oracle.js`, 1226 recorded events, model
`nemotron-3.5-asr-streaming-0.6b-int8`):

| arm | commits handed to the panel | lines reaching the transcript |
|---|---|---|
| AS SHIPPED (the cure) | 1221 | **130** (`{"final":130}`, no `provisional-draft`) |
| AS SHIPPED, commits stamped `producer:'redux'` | 1221 | 130, `producers={"redux":130}` |
| BEFORE (the pre-cure permissive choke point) | 1221 | 1221 — the two fields were ONE (the control) |

`_main/live-vs-history-source-oracle.js` is GREEN 17/17 with the claim rewritten to this one;
`_main/_redux-transcript-path.py` 7/7 + 5/5 + 4/4 and its neg-arm PASS; the historical probe
`_main/historico-vs-redux-probe.js` GREEN (its two source-level guard arms now match what the
code DOES, not an old comment); `_main/history-merge-oracle.py` 22/22 + neg-arm PASS;
`_main/history-gallery-oracle.js` 6/6; `_main/agents-md-pins-oracle.py` PASS (2 pins, 0
failures) and its `--neg-arm` PASS.

Battery wiring (`_main\_audit-verify-all.cmd`, additive): `history-write` (expects rc 0) and
`red-as-expected-history-write` (expects rc 1 + `NEG-ARM: PASS`), right after the
`redux-transcript-path` pair. New pin, measured from the file, not copied:

```
_main\_audit-verify-all.cmd = 255029 B, 3136 CRLF / 0 bare LF
sha256 09F47639C6D101177A2D689DC2E1618025E1DD0EE5F353FB81605F7FF0A5655B
```
(the last 15 lines pinned are the `page-scan-browser` pair, two more steps this lane was asked
to add to the same file; the `history-write` pair is the earlier +13.)

**LIVE, measured on the owner's own instance** (the shell restarted at 16:51 with this tree;
this lane launched nothing) — the first store writes since 2026-11-04:

```
$ grep '2026-11-05' _main/webview-run.log | grep -E 'HISTORY_(APPEND|REFUSED)' | head -3
16:53:56.395 HISTORY_REFUSED where=panel/recordHistory reason=provisional-draft route=provisional-draft final=- producer=- src=device:WASAPI loopback: CABLE Input (VB-Audio Virtual Cable) n=1 total=1
16:53:56.426 HISTORY_APPEND path="H:\\sotto\\history\\2026-11-05\\16.md" time=16:53:56 bytes=85
16:53:59.880 HISTORY_APPEND path="H:\\sotto\\history\\2026-11-05\\16.md" time=16:53:59 bytes=84
...
16:54:35.163 HISTORY_REFUSED ... n=50 total=50        # the 50th repeat, exactly as designed

$ grep '2026-11-05' _main/webview-run.log | grep -c HISTORY_APPEND      -> 7
$ grep '2026-11-05' _main/webview-run.log | grep -c HISTORY_REFUSED     -> 2
$ wc -l history/2026-11-05/16.md                                        -> 7 (route=final lines)
$ head -1 history/2026-11-05/16.md
- [16:53:56] With one punch and also snowballing is being reduced ... <!-- route=final src=worker-stamped reason=stable -->
```

Both halves of the sensor are visible in the SAME window: the closed lines land (7), the draft
is refused and SAID (first at `n=1`, again at `n=50`) — before the cure this window produced
0 lines and 0 refusals. `final=-` is honest: the live worker stamps no `final` key, so the log
says "not declared" instead of inventing a vote.

Also fixed while measuring: `_main/live-vs-history-source-oracle.js` wrote its arms with
`fs.rmSync` into the repo, and one run **deleted tracked fixtures** of other probes
(`history-verify/plvh-*/2026-10-07/02.md`, 5 files — restored with `git checkout --`). Its arms
now write to `mkdtemp` in `$TMP`.

---

## 10. Verdict

**CAUSE: `app/panel/panel.js:1636-1648` — `#caption-list` is a rolling 200-row window: once it fills (measured at 16:31:25, 7 min 37 s of transcript), every commit deletes the oldest visible line, and because `meta.start` is absent on 71 % of live commits the row lookup at `panel.js:1555-1557` falls back to a prefix test against the LAST row only (`panel.js:1570-1572`), so a line's late `final` re-appends text the panel already holds (measured: 51 of 200 rows are exact A,B,A duplicates) and the window is pushed to eviction twice as fast.**

**CAUSE (2, the store half): `app/panel/panel.js:2162` (pre-cure) — the transcript's choke point dropped every line whose meta carried no `producer:'redux'`, which on this box is every line it produces (the batch pass is off by default), and dropped it with a bare `return`: 3853 `CAPTION_APPLIED` today, 0 `HISTORY_APPEND` today, `history/2026-11-05/` absent, 0 `HISTORY_REFUSED` in the log. Cured in §8; measured 0 → 130 closed lines of 1221 commits, refusal now named.**

Not a store bug, not a reload, not a surface switch: the canonical transcript is empty today
(0 `HISTORY_` lines, no `history/2026-11-05`) and the drawer that would show it is collapsed by
design (`sotto_webview.py:12846` → `canonicalProducer: None`) — both addressed in §8.

---

## CACHE/PRICE

```
- task/agent: RightPanelHistory
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RightPanelHistory']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['RightPanelHistory']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-05T19:53:32.073504+00:00
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
- **protocolos em falta** — (1) No `todo` card was declared at the start: this toolset has no
  `todo` tool, so per the START block the card line opens the result and the `done` closes it.
  (2) The diagnosis pass read `sotto_webview.py` line numbers while another lane was editing the
  file (`M`, `shell.stale: true`), so §0-§6 anchors are in the *current* file, not in the bytes
  the running process loaded. (3) The cure edited a shared file (`sotto_webview.py`) whose owner
  was the orchestrator: I reported the plan and the orchestrator confirmed ownership of the
  battery, but the shell edit itself went in without a per-edit handshake — the right move would
  have been one message naming the six exact hunks before writing them.
- **verificacao adicional** — For the cure, the check that would raise confidence most is a LIVE
  run: restart the shell with the panel visible and watch `history/2026-11-05/` fill and
  `HISTORY_REFUSED` appear with a count. Cheap substitute already used: the same claim executed
  through the real engine + real store over 1226 recorded events (130 closed lines, 0 drafts).
  Cost of the live check: it launches the app, which this lane is not allowed to do.
- **checkboxes novas** — (1) `grep -c HISTORY_REFUSED` in a live run must be > 0 whenever
  `#caption-list` grows and `history/<today>/` has 0 lines: "captions painted and no line
  written" is now a FAIL instead of a silence. (2) The dup census of the diagnosis pass
  (`sum(rows[i]==rows[i-2]) > 2` or `count == 200` twice) — still not a gate.
  (3) The `producer=` field must exist on every line whose writer declared one; arm C of
  `_main/history-write-oracle.py` is that assertion.
- **review por outro subagente** — `sim-com-escopo` the two halves: `history-source.js` +
  `panel.js recordHistory/reportHistoryRefusal` and the shell's `_history_provenance` /
  `_history_refused` / `history_root`.
- **gate-doubt** —
  (a) `verde-de-verdade:` three greens deserve the question. (i) The green handed to me — "a
    `panel-prefix-row` cure exists (commit 2026-11-05)" — is real for the arm it tests
    (`isPrefixExtension` merges a prefix when the row is LAST) and **vacuous for the live case**:
    `_main/panel-prefix-row-oracle.py` feeds the function directly and can never observe that the
    row it compares against is the wrong row. (ii) `_main/_redux-transcript-path.py` was GREEN
    while the transcript was empty: every arm it ran declared a `producer`, so the door it
    proved open was not the door the live path walks through — a green that measures the tree's
    own fixture, not the product. (iii) My new oracle's own green: arm D writes REAL lines into
    a temp root, but a temp root is not `history/`; the run that matters is the first live
    restart, which I did not perform. Named run: `python _main/history-write-oracle.py`, 27/27
    arms, 130 lines measured through the real engine.
  (b) `falta-no-gate:` NOTHING compares "captions applied" with "lines written". A future change
    can restore a silent refusal and every gate stays green — precisely today's state before the
    cure: 3853 `CAPTION_APPLIED`, 0 `HISTORY_`, 0 `HISTORY_REFUSED`, whole battery green. The
    scenario: someone adds a third `return` in `recordHistory` without the reporter; arms A/C/D
    stay green because they never run the panel's early exit, and arm B only checks the arms it
    declares.
  (c) `gate-melhor:` `python _main/history-live-gate.py` reading a live log window: FAIL when
    `count(CAPTION_APPLIED with kind=final) > 0` AND `count(HISTORY_APPEND) == 0` AND
    `count(HISTORY_REFUSED) == 0`. Input that must leave it red: today's log before the cure
    (3853 / 0 / 0). That gate does not exist; it is the hole, and the honest statement is that
    the cure makes the failure LOUD, not that it makes it IMPOSSIBLE.
- **confianca** — `alta`: the mechanism is executed (0 -> 130 closed lines of 1221 commits through
  the real engine and store) AND the live instance confirms it (7 `HISTORY_APPEND` + 2
  `HISTORY_REFUSED` in the same two minutes, `history/2026-11-05/16.md` created — the first store
  writes since 2026-11-04).
- **nao verificado** — (1) the panel's VISUAL state after the restart (the drawer now expands
  because `canonicalProducer` is non-null; I read the store and the log, not the screen);
  (2) the panel's visual state after a restart (the drawer now expands because
  `canonicalProducer` is non-null — the owner will see the history section for the first time);
  (3) `history-route-oracle.js` is RED on arms 1/4 and its redness predates this change: it
  drives `worker/sotto_worker.py` + `caption-formulation.js` + `history-store.js` and touches
  neither file I edited; the arms it fails are its own fixture's (`real=["final","provisional-draft"]`
  from the engine, and a `route` marker missing in its own hand-built line). Not mine, not fixed,
  flagged; (4) `_main/route-stamp-gate.js` exits 2 with "SETUP ERROR: mutant: the expression to
  replace is not in the engine" — same class: it mutates `caption-formulation.js`, which I did
  not touch.

---
