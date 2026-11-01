# Receipt 2026-10-29 — YouTube ROWS + BREAKS (lane `YoutubeRows-2`, standalone)

card: rows-and-breaks: both player rows reach the overlay, breaks kept (±neg arms)

> Path note: both rows lanes were handed the same receipt filename by their tickets. The ticket
> path `_main/receipt-20261029-youtube-rows-and-breaks.md` now holds the **merged** receipt
> maintained by the sibling lane `YoutubeRows` (23,501 B, sha256 `723cb60…`), which cites this
> file for this lane's arms and evidence. This file is this lane's standalone, and it is the
> artifact these numbers were measured against.

## CONTRACT (declared before the work, with the source of each box)

| checkbox | source | status |
|---|---|---|
| `SOTTO_NEVER_ON_OWNER_SCREEN` — never launch a visible window | ticket HARD CONSTRAINTS | obeyed: pure-python; `caption_overlay._layout` called in-process (as `yt-break-position-probe.py` already does) |
| never commit / never push | ticket HARD CONSTRAINTS | obeyed: working tree only |
| `heavy_allowed=False` (performance gate AMBER) | ticket HARD CONSTRAINTS | obeyed: no build/battery/benchmark; oracles over fixtures only |
| do not touch `caption_overlay.py`, `caption_wrap.py`, `AGENTS.md`, `_main/_audit-verify-all.cmd`, `bend_core/**`, `docs/bend/**` | ticket Target | obeyed |
| every claim carries command + rc + observed output | ticket CONTRACT | §Evidence |
| a green you cannot turn red is not green; each check has a `--neg-arm` | ticket CONTRACT | 7 arms, 6 neg arms, every neg arm rc 1 |
| never publish a boolean "synced" | ticket CONTRACT | n/a here: row/text/break AGREEMENT COUNTS per sample |
| ratchet: no new RED, `sotto_webview.py` not worse | ticket KEY FACTS | obeyed: no edit to `sotto_webview.py`; new file < 120000 B |
| START / SELF-AUDIT / CACHE-PRICE blocks | playbook (2026-09-14, 2026-09-22, 2026-09-24) | done |

**STATE: `LIVE` for the data path.** The production chain
`youtube_captions.align_painted` → `youtube_reveal.window_by_paint` →
`youtube_reveal.rows_text` → `caption_overlay._layout` was exercised in-process on the 16
recorded player samples, and `_tick` was driven with a fake shell. **`UNKNOWN` for pixels**:
the app was never launched, so the layered-window composition is not measured here.

## What I found (base state, not mine)

The rows channel was already in the tree when this lane started (written 05:26–05:33 by the
sibling lane `YoutubeRows`; peer-confirmed):

* `app/webview/sotto_webview.py` sha256 `abb494ed3f1c214bcf6da59fef77a5a9500bbd8bcbf1128b8dbeeb33c033924e`
  (unchanged through this whole lane, re-hashed at the end) — `_tick()` already passes
  `rows=rows`; `external_caption` → `push_caption_to_window` → `youtube_reveal.rows_text`, so
  `caption_overlay._layout` sees the `'\n'` channel.
* `app/webview/youtube_reveal.py` sha256 `68ef1cb9…b294` — `window_by_paint(cues, hit)` builds
  `from_index..index` (capacity 2 + 1 rollup).
* `_main/youtube-rows-oracle.py` sha256 `4ce6a8ad…06ac` — GREEN 16/16 on the visible-row model.

## What I changed

### 1. `app/webview/youtube_reveal.py` (new file, outside the ratchet population)

* `first_words(text, count)` — the cut of the growing row is line-aware: a cue whose text
  contains `'\n'` keeps the break at the word it was on. Single-line text is identical to the
  old `" ".join(words[:count])`.
* **new** `row_text(text)` — spaces collapsed *inside* each line, breaks between lines kept.
* Both `window_by_paint` branches now call `text = row_text(text)` (current file lines 236 and
  254, `grep -c` = 2; the only `" ".join(text.split())` left is inside `row_text`'s docstring).

**Correction, because it matters and it was mine:** my first pass defined `row_text` but did
**not** replace the two `text = " ".join(text.split())` call sites inside `window_by_paint`.
The function was dead and the guarantee I had written was not in force. The sibling lane
completed the wiring during the merge. The claim below is measured **on the current tree**
(file sha256 `9941211acc1a63be63c3f000c5ec3d914e0eb06ba09c9e0b8fdbb3b860db08ab`,
12,714 B / 294 lines), not on my first pass.

Break guarantee, at the level that matters (the window, not the helper):

```
cue text "a b\nc d", hit {aligned:3, painted_from:0, from_index:0, index:0}
  window_by_paint -> ['a b\nc']        rows_text -> 'a b\nc\n'
  (the same cue, aligned:4)
  window_by_paint -> ['a b\nc d']
first_words("a b\nc d", 3) -> 'a b\nc'
payload cues containing '\n': 0        (so the fixture numbers are inert w.r.t. this change)
```

Why it matters: the channel is `'\n'`-delimited and `caption_overlay._layout` decides
"pre-broken" by the presence of `'\n'`. Collapsing a row's internal break fuses two player
lines before the channel.

### 2. `_main/youtube-rows-oracle.py` (additive; existing arms and their rc untouched)

* `dom` arm — production fed **all DOM segments** in reading order, which is what the UIA
  reader really delivers (`youtube_captions._painted_children` reads the children of the
  rendered caption window; there is **no** `v`/opacity filter). The old comparison fed
  production the *visible* rows only — a different input from live.
* `text` / `breaks` measured **separately**; `break_offsets(rows)` = word index at which each
  row ends.
* `older_row` — counted only where the player's DOM has 3 rows.
* `shape` — the production input is a list of WORDS (`painted_words`' contract).
* `visible_box` — informational; **not** in the green condition (§Remaining).
* neg arms `drop-older`, `rewrap`, `text`, `shape` added; `rows`/`draw` untouched. A neg arm
  that fails to break the arm it names returns **rc 2** (blind).

## Evidence (current tree)

### A. `python _main/youtube-rows-oracle.py` → **rc 0**

```
SUMMARY samples=16 rows_match=16/16 draw_match=16/16 rows_different=0 draw_different=0 clipped=0
BREAKS  samples=16 dom_match=16/16 dom_draw_match=16/16 text_match=16/16 breaks_match=16/16 older_row=4/4 shape=16/16 visible_box=15/16
WIRING ok: a janela, o _tick, o push e o layout estao ligados
TICK ok: o _tick entrega as DUAS linhas (novo e final)
YOUTUBE-ROWS GREEN
```

Per-sample excerpt (the live input):

```
t=2.715    MATCH      hit=align        rows=3 draw=3
   youtube (3): ['Have you ever had to kill a man?', 'No.', 'Then']
   sotto   (3): ['Have you ever had to kill a man?', 'No.', 'Then']
   dom      MATCH        hit=align        lidas=3 texto=OK quebras=OK antiga=OK caixa=OK
t=8.264    MATCH      hit=align        rows=2 draw=2
   youtube (2): ['fine.', 'After the ritual,']
   sotto   (2): ['fine.', 'After the ritual,']
   dom      MATCH        hit=align        lidas=3 texto=OK quebras=OK antiga=OK caixa=DIF
   player DOM (3): ["Don't worry about me, Yamato. I'll be", 'fine.', 'After the ritual,']
   producao   (3): ["Don't worry about me, Yamato. I'll be", 'fine.', 'After the ritual,']
   desenho    (3): ["Don't worry about me, Yamato. I'll be", 'fine.', 'After the ritual,']
```

The `>>` speaker marker is stripped on **both** sides (`norm`, reused from
`_main/youtube-reveal-oracle.py`) and whitespace normalised before every comparison.

### B. The older row is retained by the PLAYER's own evidence, not by a timer

`align_painted`'s `from_index` reaches one cue **before** the live window on all four 3-row
samples, and `window_by_paint` keeps it:

```
t=2.7148 dom=3 hit from_index=0 index=2 painted_from=10 aligned=12 rows=3  old row kept: True
t=4.6813 dom=3 hit from_index=1 index=3 painted_from=8  aligned=10 rows=3  old row kept: True
t=6.8838 dom=3 hit from_index=2 index=4 painted_from=14 aligned=15 rows=3  old row kept: True
t=8.2643 dom=3 hit from_index=3 index=5 painted_from=9  aligned=12 rows=3  old row kept: True
```

No rollup timer was invented: the row that scrolls out is still painted by the player, so it
is still in the painted words and still in the window.

### C. The negative arms (6, all **rc 1**)

```
--neg-arm (rows)      rc 1  rows-from-player broken 13/16
--neg-arm draw        rc 1  overlay-rows     broken 11/16
--neg-arm drop-older  rc 1  dom-oldest-row   broken 13/16   older_row 4/4 -> 0/4
--neg-arm rewrap      rc 1  breaks           broken 15/16   text_match 16/16
--neg-arm text        rc 1  text             broken 15/16
--neg-arm shape       rc 1  input-shape      broken 15/16   (the survivor is the single-word row 'Have')
```

`rewrap` is the proof that the break is measured **separately** from the text: it splits a
row at a different word; the joined text stays 16/16 and only `breaks` falls (1/16).
`drop-older` is Defect 1 injected back into the live input (`_tick`'s old `lines[-1]`).

### D. Helper unit check

```
'Have you ever had' 4 -> 'Have you ever had' OK
'a b c' 0 -> '' OK          'a b c' 9 -> 'a b c' OK
'a\nb c' 2 -> 'a\nb' OK     <- break kept at the word it was on
'>> No.' 2 -> '>> No.' OK   '' 3 -> '' OK   'x' 1 -> 'x' OK
row_text: 'a b\nc\nd'       rows_text: ['a\nb','c'] -> 'a\nb\nc\n'
window_by_paint("a b\nc d", aligned=3) -> ['a b\nc']
```

### E. Neighbouring oracles did not regress (current tree)

```
python _main/youtube-1to1-oracle.py    -> rc 0   YOUTUBE-1TO1 VERDICT GREEN (7 elementos, 0 vermelhos)
python _main/youtube-reveal-oracle.py  -> rc 1   reveal-matches-the-player RED linhas iguais: 8/10  (pre-existing)
python -m py_compile app/webview/youtube_reveal.py _main/youtube-rows-oracle.py -> rc 0
```

### F. `python _main/code-health-oracle.py` → **rc 2** (`CODE-HEALTH VERDICT FAIL`)

Before this lane's edit and after it, the RED metric set and its numbers are **identical** (12),
and the only file this lane touched is a `NEW` file outside the baseline:

```
NEW  app/webview/youtube_reveal.py                  11459 B   264 linhas (fora do baseline)   <- before the lane
NEW  app/webview/youtube_reveal.py                  12714 B   294 linhas (fora do baseline)   <- current
RED  app/webview/sotto_webview.py: bytes piorou de 758679 para 772492
RED  app/webview/sotto_webview.py: lines piorou de 14424 para 14668
RED  app/webview/youtube_captions.py: bytes piorou de 85542 para 89284
RED  app/webview/youtube_captions.py: lines piorou de 2040 para 2115
RED  app/webview/youtube_captions.py: defs piorou de 59 para 60
RED  app/webview/youtube_window.py: bytes piorou de 5872 para 9972
RED  app/webview/youtube_window.py: lines piorou de 141 para 240
RED  app/webview/youtube_window.py: defs piorou de 4 para 8
RED  app/webview/youtube_window.py: max_func piorou de 33 para 42
RED  worker/sotto_worker.py: bytes piorou de 386286 para 387428
RED  worker/sotto_worker.py: lines piorou de 7250 para 7267
RED  worker/sotto_worker.py: except_pass piorou de 13 para 14
piorem: 12 metrica(s)
CODE-HEALTH VERDICT FAIL          (rc 2)
```

`sotto_webview.py` ended byte-for-byte as found: `772492 B / 14668 linhas`, sha256
`abb494ed…3924e` — **this lane did not edit it**. `caption_overlay.py` / `caption_wrap.py`
are `M` from a different lane; not mine.

## The contradiction with `_main/youtube-reveal-oracle.py` — reported, not adjudicated

That oracle is RED `8/10`. It does **not** contradict 16/16; its model cannot reach these rows:

1. **It silently drops 6 of 16 samples.** `hit_from_player` compares `norm(row)` (marker
   stripped) against cue words that **keep** `>>`; every sample whose last live cue starts
   with `>>` finds no match. Measured skip list: `t=2.715, 3.359, 4.027, 4.681, 5.531, 6.224`.
2. **Its window is built from `sub` = live cues only**, so the rollup cue is structurally
   outside the list; its two remaining divergences are exactly the two counted 3-row samples
   (`t=6.884`, `t=8.264`), both 16/16 here.
3. Latent bug in the same file: `tem_velho = any(expr for _n, _a in ())` is always `False`, so
   "o relogio do inicio do cue ainda esta no ramo painted" can never read `SIM`;
   `wiring_faltas(src)` is computed and never used in `main`. Not fixed (another lane's file) —
   patch in §GATE-CHANGE REQUEST.

## Remaining, explicitly unfixed

1. **The clipped rollup row (`visible_box` 15/16).** At `t=8.264` the player has three segments
   in the DOM but the top one is outside the box (`v=False`); our overlay draws three full
   lines. Fixing it needs `caption_overlay._layout` to clip/drop the row UIA reports
   off-screen, and `_painted_children` does not read per-child `CurrentIsOffscreen` today.
   Both are ratchet-frozen and owned by another lane. **Delivered without them:** row set,
   order, text and breaks (16/16).
2. **The clock path has no rollup.** `_yt_lines` (no paint, or another track painted) uses
   `revealed_lines(cues, t, 2)`; without painted words there is no evidence of the third row,
   and a rollup timer would be a guess. Not exercised by this fixture.
3. **`_release()` re-emits only `last_line` without `rows`**, so the final frame (after
   `RELEASE_S` of silence, i.e. a stale caption) collapses to one row. Named, not measured.

## Commands run (all, with rc)

```
python _main/youtube-rows-oracle.py                      rc 0
python _main/youtube-rows-oracle.py --neg-arm            rc 1   rows 13/16
python _main/youtube-rows-oracle.py --neg-arm draw       rc 1        11/16
python _main/youtube-rows-oracle.py --neg-arm drop-older rc 1        13/16
python _main/youtube-rows-oracle.py --neg-arm rewrap     rc 1        15/16 (text 16/16)
python _main/youtube-rows-oracle.py --neg-arm text       rc 1        15/16
python _main/youtube-rows-oracle.py --neg-arm shape      rc 1        15/16
python _main/youtube-1to1-oracle.py                      rc 0   GREEN
python _main/youtube-reveal-oracle.py                    rc 1   8/10 (pre-existing)
python _main/code-health-oracle.py                       rc 2   FAIL, 12 metrics, identical to before
python -m py_compile app/webview/youtube_reveal.py _main/youtube-rows-oracle.py   rc 0
```

## GATE-CHANGE REQUEST

Lane PREPARES, Main MERGES. Two holes in gate instruments; patch (1) is **already applied** to
`_main/youtube-rows-oracle.py` (untracked), patch (2) is text only because the file is another
lane's.

### (1) `_main/youtube-rows-oracle.py` — the input SHAPE was unguarded (applied)

Hole: every arm trusted the shape of what it fed production. Scenario: someone passes the
player's ROWS (`['Have you ever had', '…']`) where production expects the WORDS
`painted_words` returns; `align_painted` treats each row as one word, and the report can still
print a plausible window from the reconstructed fallback.

Patch (in `measure`, merged):

```python
        dom_painted = " ".join(dom).split()
        if neg == "shape":
            # the WRONG shape: rows passed as if they were words
            dom_painted = list(dom)
        shape_ok = all(" " not in word for word in dom_painted)
        dom_hit, dom_how = hit_for(cues, dom_painted)
```

plus `shape_ok` in the green condition and the `input-shape` arm.

Non-vacuity control (executed, rc 1):

```
python _main/youtube-rows-oracle.py --neg-arm shape
  BREAKS  ... shape=1/16 visible_box=1/16
  NEG-ARM arm=input-shape broken_samples=15/16
  NEG-ARM RED as designed
  rc 1
```

The survivor is the single-row `'Have'` — a one-word row is indistinguishable from a word, so
15/16 is the honest ceiling of this control.

### (2) `_main/youtube-reveal-oracle.py` — marker mismatch drops 6/16 (patch, NOT applied)

```python
-def hit_from_player(rows, cues, live_indexes):
-    row_words = norm(row).split()          # strips '>>' from the ROW
-    if [w.lower() for w in cue_words[:len(row_words)]] != [w.lower() for w in row_words]:
+def hit_from_player(rows, cues, live_indexes):
+    row_words = [norm(w) for w in row.split() if norm(w)]   # marker stripped per WORD,
+    cue_norm = [norm(w) or w for w in cue_words]            # on BOTH sides
+    if [w.lower() for w in cue_norm[:len(row_words)]] != [w.lower() for w in row_words]:
```

Control that must go RED after the patch: total counted rises 10/16 → 16/16 **and** the
`sub = live cues only` window must be replaced by the `from_index` run, otherwise the two
3-row divergences stay. Not patched: another lane's instrument, and a silent edit there would
change a number their receipt cites.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: H:/pi-agent/sessions/--H--sotto--/2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987/YoutubeRows-2.jsonl
- source: H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows-2.jsonl
- cache: read=6968064 write=0 hit=95.3118% (cache-read / input+cache-read); universe: 84 usage rows from H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows-2.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: commandcode-b/deepseek/deepseek-v4.1-flash: calls=84 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: commandcode-b/deepseek/deepseek-v4.1-flash $0.00000000 vs $0.00000000 over 84 of 84 matched usage rows
- when-failed: NOT A PREFIX VERDICT — cache-read census: 0 of 83 warm-eligible turns read 0 cache tokens (state=CACHE-MISS-NONE; population: 83 warm-eligible turns of 84 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-10-29T08:30:41.790Z..2026-10-29T08:42:30.743Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows-2.jsonl)
- where-failed: NOT A PREFIX VERDICT — cache-read census: 0 of 83 warm-eligible turns read 0 cache tokens (state=CACHE-MISS-NONE; population: 83 warm-eligible turns of 84 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-10-29T08:30:41.790Z..2026-10-29T08:42:30.743Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows-2.jsonl)
- report generated_at: 2026-10-29T08:42:33.671177+00:00
- usage rows: 84
- model + route: commandcode-b/deepseek/deepseek-v4.1-flash
- input tokens: 342748
- output tokens: 61073
- cache-read tokens: 6968064
- cache-write tokens: 0
- hit ratio: 95.3118% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: commandcode-b/deepseek/deepseek-v4.1-flash: calls=84 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: commandcode-b/deepseek/deepseek-v4.1-flash $0.00000000 vs $0.00000000 over 84 of 84 matched usage rows
- prefix breaks: NOT A PREFIX VERDICT — cache-read census: 0 of 83 warm-eligible turns read 0 cache tokens (state=CACHE-MISS-NONE; population: 83 warm-eligible turns of 84 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-10-29T08:30:41.790Z..2026-10-29T08:42:30.743Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows-2.jsonl)
- WHEN / WHERE failed:
0 of 83 warm-eligible turns read 0 cache tokens (state=CACHE-MISS-NONE; population: 83 warm-eligible turns of 84 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-10-29T08:30:41.790Z..2026-10-29T08:42:30.743Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows-2.jsonl)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Snapshot at `08:42:33Z`, not the final turn count (the session continued after it).

## SELF-AUDIT

* **protocolos em falta** — two, and the first is the serious one. (a) I published a guarantee
  (`row_text` used by both `window_by_paint` branches) that I had **not wired**: the claim came
  from intent, not from the file, which is exactly what the delivery contract forbids. It
  survived because I unit-tested `first_words`/`row_text` in isolation and never once fed a
  multi-line cue through `window_by_paint`. The sibling lane caught it. The mechanical check
  that would have caught it: `grep -c 'text = row_text(text)' == 2` **and** a window-level
  assertion (`window_by_paint("a b\nc d", aligned=3) == ['a b\nc']`) — the second is in §D now.
  (b) I took the briefing's "`_tick` discards every row but the last" at face value; the
  plumbing was already in the tree. The first thing to do with a briefing that names a live
  defect is to check the defect is still live.
* **verificacao adicional** — ran: `align_painted`'s `from_index` on the four 3-row samples
  (§B), because "the row is retained" is a mechanism claim, not an output claim; and the
  synthetic multi-line cue through `window_by_paint` (the check that would have caught (a)).
  Not run: a live capture of the UIA tree during a rollup, to confirm `_painted_children`
  returns the clipped segment's words — the whole `dom` arm rests on it. Cost: one foreground
  player session, forbidden for this lane.
* **checkboxes novas** — a "wired-or-it-did-not-happen" assertion for every new helper: the
  name must appear at least once OUTSIDE its own definition (AST call-site count), because a
  defined-but-uncalled function reads as done in a diff.
* **review por outro subagente** — `sim-com-escopo`: review of (a) `break_offsets`/`norm`
  semantics on rows carrying `>>`, (b) whether `visible_box=15/16` should stay outside the
  green condition. The sibling lane already independently re-ran all six neg arms and matched
  the counts, which is the strongest review this piece had.
* **gate-doubt**:
  * `verde-de-verdade:` — `python _main/youtube-rows-oracle.py` (rc 0). Not vacuous, proven by
    three mutations: `--neg-arm drop-older` takes `dom` 16/16 → 3/16 and `older_row` 4/4 →
    0/4; `--neg-arm rewrap` takes `breaks` 16/16 → 1/16 while `text` stays 16/16;
    `--neg-arm shape` takes `shape` 16/16 → 1/16. I distrusted one arm and fixed it: the old
    comparison fed production the *visible* rows, so it could never see the clipped row; `dom`
    feeds the real UIA input and reports `visible_box` 15/16 instead of hiding it.
  * `falta-no-gate:` — the gate does not verify that `_layout` is reached with `rows` by the
    real `push_caption_to_window` (the `WIRING` arm is a substring check; `tick_arm` covers
    `_tick` but not the `if rows:` branch that converts them). Scenario: someone deletes
    `if rows: text = youtube_reveal.rows_text(rows)`; the oracle still reports `draw` 16/16
    because it calls `overlay_rows` directly with `rows_text`, so only the substring check
    would witness it — and a substring check is not behaviour.
  * `gate-melhor:` — mechanical: drive the real `push_caption_to_window` with a fake overlay
    (it already tolerates `caption_overlay is None`) and assert the text the fake overlay
    receives ends with `'\n'` and contains one row per line; control = the same call with the
    `if rows:` branch deleted from a temp copy of the shell, which must leave `draw`/`dom`
    GREEN and this new arm RED. Command shape:
    `python _main/youtube-rows-oracle.py --neg-arm wiring`.
* **confianca** — `alta` for row/text/break delivery on this fixture (16/16, three mutations
  RED, independently re-run by the sibling); `media` in general, because the `dom` arm assumes
  UIA reads the clipped segment.
* **nao verificado** — (1) the owner's screen / layered-window composition; (2) real UIA output
  during a rollup; (3) videos other than `WdaHAGRBB6s`; (4) the clock path and `_release()`'s
  final frame; (5) `_tick`'s dedup on a row-only change (reasoned safe, not measured).
