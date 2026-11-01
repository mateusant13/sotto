# Receipt — YouTube caption ROWS and their break position (2026-10-29)

status: done

Lane: `YoutubeRows` (owner: main), merged ticket receipt. `YoutubeRows-2`'s
standalone is `_main/receipt-20261029-youtube-rows-and-breaks-lane2.md`
(23,957 B, sha256 `d2d43eb4…`); it documents the receipt collision and the
additive arms. Target: the
native GDI+ overlay that the owner
actually sees must draw the player's caption rows, in the player's order, at the
player's break — not re-wrap one flattened string.

## 1. Protocol contract (what applies, and its source)

- No `todo` tool exists in this lane's toolset. Per the task-start block, the
  substitute is: the first line of the final result names the card and the last
  line is the `done` citing the artifact. (Source: task-start block v1.)
- `SELF-AUDIT` with `gate-doubt` — source: task-start block v2 /
  `I:/!manager/AGENTS.md` ("every agent closes with a SELF-AUDIT").
- `CACHE/PRICE` — source: CACHE-PRICE-BLOCK v1 in the lane instructions.
- Deliverables 1-3 (rows on production path, new oracle with `--neg-arm`,
  this receipt) — source: this ticket.
- Code-health ratchet (`_main/code-health-oracle.py` vs
  `_main/code-health-baseline.json`) — source: hard constraint of this ticket.
- No app launch / window / screenshot / commit / push — source: hard
  constraints of this ticket.

## 2. BEFORE (measured, not remembered)

The 2026-10-26 receipt (`_main/receipt-20261026-break-position-is-the-failing-element.md`)
reported **12 of 16** sampled instants breaking at a different word, and one
instant (t=6.884) missing a row the player shows.

Re-run today against the **HEAD** sources (a copy of `app/webview/caption_overlay.py`
and `caption_wrap.py` from `git show HEAD:...`, measured by the old instrument via
the new `SOTTO_PROBE_WEBVIEW` override so the current files are not involved):

```
SOTTO_PROBE_WEBVIEW=<G:/Temp/.../before/app/webview> python _main/yt-break-position-probe.py
rc=1
SUMMARY amostras=16 fronteira_diferente=12 texto_junto_diferente=1
BREAK-POSITION DIVERGE
```

Two examples from that run (the old instrument joins the recorded rows with a
space before calling `_layout`, so it measures the re-wrap — which is exactly the
defect):

```
t=6.884    DIFERE
   youtube (3): ['>> Then this sword is useless.', ">> Don't worry about me, Yamato. I'll be", 'fine.']
   overlay (2): [">> Don't worry about", "me, Yamato. I'll be fine."]
   scrolled off: '>> Then this sword is useless.'

t=10.192   texto-junto-igual
   youtube (2): ["After the ritual, I'd love to train with", 'you sometime.']
   overlay (2): ["After the ritual, I'd love to", 'train with you sometime.']
```

The second example is the proof that re-wrapping cannot be fixed by width: the
joined text is IDENTICAL and the break still falls at a different word. The old
instrument's `texto_junto_diferente=1` (one sample where even the joined text
differs) is the `>>`/normalisation artifact; it does not remove the break result.

## 3. What changed

Production (all measurable in pure Python; no window opened):

1. `app/webview/youtube_captions.py` — `align_painted` now returns
   `from_index`, the FIRST cue of the painted run (`_align_from` already knew
   it). The rest of the alignment logic is unchanged. This is what lets the
   window be the player's run instead of the last cue only.
2. `app/webview/youtube_reveal.py` (the lead's new module, extended):
   - `window_by_paint` takes the new path when the hit has `from_index`:
     rows `from_index..index`, the middle rows whole, the last row cut to
     `aligned - painted_from` words; the window keeps `capacity + 1` rows
     (`ROLLUP_ROWS = 1`) because the browser's rollup keeps the outgoing row
     for a while (measured: 3 rows at t=6.884). A hit without `from_index`
     keeps the old `live_cues` path (the lead's oracle calls it that way).
   - `rows_text(rows)` joins rows with `"\n"` and appends a final `"\n"`. The
     trailing terminator is the channel marker: one row still carries `"\n"`,
     so `_layout` cannot mistake it for a normal one-line caption.
   - `painted_prefix_count` stays `aligned - painted_from` (the lead's rule).
   - `first_words(text, count)` and `row_text(text)` preserve an INTERNAL
     `"\n"` (a cue's own line break) instead of `split()` flattening it, and
     both `window_by_paint` branches call `row_text`; measured inert on this
     fixture (0 of the 19 caption events / 0 parsed cues contain `"\n"`), so
     the 16/16 below is a re-run after the change, not a carried number.
     Unit probe on the current tree: `window_by_paint` on cue `"a b\nc d"` with
     3 painted words returns `['a b\nc']`; `rows_text` -> `'a b\nc\n'`;
     `_layout` -> `['a b', 'c']`.
3. `app/webview/sotto_webview.py`:
   - `_youtube()` (painted branch) returns
     `[('external:youtube:track', youtube_reveal.window_by_paint(...))]`.
   - `_tick()` no longer takes `lines[-1]` for YouTube: it passes **all** rows
     to `external_caption(..., rows=rows)`; the comparison of the last tick
     includes `rows` so a row change is not mistaken for "same line". The final
     call on release also carries `rows`.
   - `external_caption(..., rows=None)` applies the production
     `clean_external_text` to EACH row (so `>>` is stripped per row, the same
     convention as the lead's `norm()` in `youtube-oracle.py`), and passes
     `rows=rows` to `push_caption_to_window`.
   - `push_caption_to_window(..., rows=None)` joins the rows with
     `youtube_reveal.rows_text(rows)` and forces `instant=True`: a rows window
     is already the player's painted frame and must never sprout again (without
     the force, `set_text(instant=False)` would flatten it to the first word and
     re-reveal with spaces, losing the `"\n"` markers).
   - `replay()` / release clear `last_rows` alongside `last_line`.
4. `app/webview/caption_overlay.py` (net **-9 bytes**, see §6):
   - `_display_text()` returns the whole multiline text when `_shown >= _n`;
     `push_caption_to_window` guarantees that for rows.
   - `_layout()` tests `'\n' in text`; if so, `cur_lines = text.splitlines()`
     and `scrolled = ''`, bypassing `caption_wrap.wrap_tail` entirely. A row is
     never re-broken at another word. If a row is wider than the drawable plate,
     GDI+ clips it; the code does not silently re-break it, and the new oracle
     reports `clipped=N` so this is visible. (`caption_wrap.py` untouched.)
5. `_main/yt-break-position-probe.py` — added an optional
   `SOTTO_PROBE_WEBVIEW` env override so the genuine HEAD measurement in §2 can
   be taken without reverting the working tree. Measurement only; no product
   behavior.
6. `_main/youtube-1to1-oracle.py` — one WIRING anchor updated from
   `push_caption_to_window(text, instant=instant)` to
   `push_caption_to_window(text, instant=instant, rows=rows)`. The call now
   carries rows; the invariant ("external_caption transports instant") is the
   same. This was a RED caused by the new call shape and is fixed; the oracle is
   green 7/7 (§5).

## 4. AFTER — the new oracle, and the old instrument

New oracle: `_main/youtube-rows-oracle.py`. It calls the PRODUCTION functions:

```
python _main/youtube-rows-oracle.py
rc=0
SUMMARY samples=16 rows_match=16/16 draw_match=16/16 rows_different=0 draw_different=0 clipped=0
BREAKS  samples=16 dom_match=16/16 dom_draw_match=16/16 text_match=16/16 breaks_match=16/16 older_row=4/4 shape=16/16 visible_box=15/16
WIRING ok: a janela, o _tick, o push e o layout estao ligados
TICK ok: o _tick entrega as DUAS linhas (novo e final)
YOUTUBE-ROWS GREEN
```

Per-sample evidence (the full table is printed by the command; two of the 16):

```
t=6.884    MATCH      hit=align        rows=3 draw=3
   youtube (3): ['Then this sword is useless.', "Don't worry about me, Yamato. I'll be", 'fine.']
   sotto   (3): ['Then this sword is useless.', "Don't worry about me, Yamato. I'll be", 'fine.']
t=10.192   MATCH      hit=align        rows=2 draw=2
   youtube (2): ["After the ritual, I'd love to train with", 'you sometime.']
   sotto   (2): ["After the ritual, I'd love to train with", 'you sometime.']
```

The older row is retained by the PLAYER's own painted words, not by a timer
(`YoutubeRows-2` evidence, re-checked on the current tree). On the four 3-row
samples, `align_painted`'s `from_index` reaches one cue before the live window,
and `window_by_paint` keeps it:

```
t=2.7148 dom=3 hit from_index=0 index=2 painted_from=10 aligned=12 rows=3  old row kept: True
t=4.6813 dom=3 hit from_index=1 index=3 painted_from=8  aligned=10 rows=3  old row kept: True
t=6.8838 dom=3 hit from_index=2 index=4 painted_from=14 aligned=15 rows=3  old row kept: True
t=8.2643 dom=3 hit from_index=3 index=5 painted_from=9  aligned=12 rows=3  old row kept: True
```

What the oracle does per sample:
- reads `samples[].segs` from
  `_main/fixtures/yt-WdaHAGRBB6s.live-compare-20261026.json`, keeps the rows the
  player PAINTS (opacity > 0.05, `v` not false, the `l` language filter when
  present), strips the `>>` marker on BOTH sides (`norm`), and lists the rows;
- builds the live `hit` with production `youtube_captions.align_painted(cues,
  painted_words)`, then calls production `youtube_reveal.window_by_paint`;
- calls production `sotto_webview.clean_external_text` per row,
  `youtube_reveal.rows_text`, the real `caption_overlay.NativeCaptionOverlay`
  `_display_text`/`_layout` (GDI+ measure), and compares the drawn row list to
  the player's rows;
- prints `rows_match`, `draw_match`, `clipped`, the wiring source anchors, and a
  `TICK` behavioral check of `ExternalCaptionWatcher._tick` (a plain fake shell,
  no process).
- the `dom` arm feeds production ALL DOM segments (what the live UIA
  `_painted_children` really reads: no `v`/opacity filter) and compares that
  input separately; `text` and `breaks` compare the joined words and
  `break_offsets(rows)` separately; `older_row` is scored only on the four
  samples whose DOM has 3 rows; `shape` checks that the `painted_words` input is
  a list of WORDS, not rows (a row list passed where words are expected is the
  silent failure this guards); `visible_box` is informational (15/16, the
  clipped rollup row at t=8.264) and is NOT part of the green condition.
- the added neg arms `drop-older`, `rewrap`, `text` and `shape` each neutralise
  one dimension; an arm that fails to break its own dimension exits **2**
  (blind), not 1, so "saw it" and "blind" cannot be confused.
- One sample (t=0.023, one painted word "Have") is marked
  `hit=reconstructed`: production `align_painted` intentionally requires 3 exact
  words (`_ALIGN_MIN_EXACT`), so that sample has no production hit; the
  reconstruction walks the same flattened cues to supply the run. The rows are
  still produced by production `window_by_paint`. This is the only sample not
  driven by a live `align_painted` hit, and it is named in the report.

Negative arms (each must go RED; all six do, by design):

```
python _main/youtube-rows-oracle.py --neg-arm              rc=1  rows-from-player broken 13/16
python _main/youtube-rows-oracle.py --neg-arm draw         rc=1  overlay-rows     broken 11/16
python _main/youtube-rows-oracle.py --neg-arm drop-older   rc=1  dom-oldest-row   broken 13/16  older_row 4/4 -> 0/4
python _main/youtube-rows-oracle.py --neg-arm rewrap       rc=1  breaks           broken 15/16  text_match=16/16
python _main/youtube-rows-oracle.py --neg-arm text         rc=1  text             broken 15/16
python _main/youtube-rows-oracle.py --neg-arm shape        rc=1  input-shape      broken 15/16  shape 16/16 -> 1/16
```

`rows` neutralises `window_by_paint` to "rows from the player"; `draw`
neutralises the overlay rows branch (joins the rows with a space before
`_layout`, i.e. the pre-fix re-wrap); `drop-older` injects `_tick`'s old
`lines[-1]` back; `rewrap` moves the break one word while the joined text stays
identical (16/16), which isolates the break from the text; `text` drops one
word; `shape` passes the player's ROW LIST where `painted_words`' word list is
expected. Each arm names the samples it breaks. These counts were independently
re-run by this lane on the current tree; the full outputs are in the
`YoutubeRows-2` standalone receipt (lane2 path).

Old instrument, after the change:

```
python _main/yt-break-position-probe.py
rc=1
SUMMARY amostras=16 fronteira_diferente=12 texto_junto_diferente=1
BREAK-POSITION DIVERGE
```

This is **identical** to the HEAD run in §2 (byte-for-byte output). It is not
worse, and it cannot get better: the old instrument joins the rows with a space
before calling `_layout`, so it always exercises the flattened contract. The
rows channel is measured by the new oracle above. At 1280 and 2560 it is also
12/16 (same instrument, same rule).

## 5. Other gates (regression check)

```
python _main/youtube-1to1-oracle.py       rc=0  YOUTUBE-1TO1 VERDICT GREEN (7/7)
python _main/yt-mirror-align-oracle.py    rc=0  VERDICT: PASS arms 13/13 mutants 5/5
python _main/youtube-window-oracle.py     rc=0  BATTERY-VERDICT PASS checks=12 fail=0
python _main/youtube-captions-oracle.py   rc=0  VERDICT: PASS arms 66/66 mutants 17/17
python _main/youtube-reveal-oracle.py     rc=1  (pre-existing; see below)
```

`youtube-1to1-oracle.py` was RED on `reveal-wired` for one anchor after the new
call shape; the anchor was updated (§3.6) and the oracle is green again. The
anchor's own mutant (`wiring_drop`) still proves it can fail.

`youtube-reveal-oracle.py` is RED at 8/10 with **both** the old and the new
`window_by_paint` (monkeypatched old implementation in the same process, same
fixture): the two differing samples are t=6.883805 and t=8.264271, both because
its input `sub` has only the cues alive at `t` and its fixture's `youtube` rows
include the outgoing/invisible row. It is a pre-existing RED of that oracle's
input contract, not caused by this change; its protected oracle path
(`--neg-arm`, capacity, wiring) is unchanged.

## 6. Code-health ratchet (before/after of the touched files)

`python _main/code-health-oracle.py` → **rc=2, 12 RED metrics, before and after**
(the same 12 metric pairs; no new metric type; the REDs in
`sotto_webview`/`youtube_captions`/`youtube_window`/worker are pre-existing).

| file | before | after | verdict |
|---|---|---|---|
| `app/webview/caption_overlay.py` | 51371 B, 1173 lines, max_func 132 | **51362 B (-9), 1167 lines (-6)**, max_func 132 | LESS — not RED |
| `app/webview/caption_wrap.py` | 20049 B, 418 lines | **20049 B (0), 418 lines** | SAME — untouched |
| `app/webview/youtube_captions.py` | 88879 B, 2110 lines, defs 60 | 89284 B, 2115 lines, defs 60 | already RED; +405 B from this lane |
| `app/webview/sotto_webview.py` | 770605 B, 14638 lines | 772492 B, 14668 lines | already RED; +1887 B / +30 lines from this lane |
| `app/webview/youtube_reveal.py` | 8688 B, 208 lines (NEW) | 12714 B, 294 lines (NEW) | < 120000 B, no RED |

The two zero-slack files are the ones the constraint names: `caption_overlay.py`
got **smaller** and `caption_wrap.py` did not change. The new logic is in
`youtube_reveal.py` (new module, 12.7 KB) and the oracle under `_main/`.

## 7. What is NOT proven

- **The owner's pixels.** `_layout` returns the rows and their geometry; the
  actual GDI+ `GraphicsPath.AddString` positions and the alpha blend were not
  captured. No window was opened, no screenshot was taken. The claim is about
  the row list the overlay is asked to draw, not the rendered glyphs.
- **The live player.** Every row compared here comes from the recorded
  2026-10-26 fixture. No live UIA read was taken in this lane.
- **A cue whose painted run starts mid-cue (`off0 > 0`).** `align_painted`
  supports it, but all 16 recorded samples start at a cue boundary; the window's
  last-row prefix is `aligned - painted_from`, which assumes the run starts at
  the last cue's first word. Not exercised.
- **The first 1-2 painted words.** Production `align_painted` requires 3 exact
  words; t=0.023 uses the reconstructed hit described in §4. A live first-word
  instant goes through the existing clock fallback, not through
  `window_by_paint`.
- **A row wider than the drawable plate.** The design is "clip, do not
  re-break"; `clipped=0` for all 16 samples, so the clipping path is untested.
- **Other videos/languages, >3-row rollup, and non-YouTube captions containing
  `"\n"`.** The `_layout` newline branch applies to any caption with a newline
  (intended: a newline is an explicit break), but only the YouTube fixture was
  measured.
- The panel/OSD (`meta["chunks"]`) still uses the last row only; that surface
  was not in scope.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: H:/pi-agent/sessions/--H--sotto--/2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987/YoutubeRows.jsonl
- source: H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows.jsonl
- cache: read=15933312 write=0 hit=95.5159% (cache-read / input+cache-read); universe: 143 usage rows from H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: commandcode-b/deepseek/deepseek-v4.1-flash: calls=143 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: commandcode-b/deepseek/deepseek-v4.1-flash $0.00000000 vs $0.00000000 over 143 of 143 matched usage rows
- when-failed: NOT A PREFIX VERDICT — cache-read census: 1 of 142 warm-eligible turns read 0 cache tokens (state=CACHE-MISS; population: 142 warm-eligible turns of 143 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-10-29T08:17:20.540Z..2026-10-29T08:49:29.716Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows.jsonl)
- where-failed: first miss at 2026-10-29T08:17:20.540Z: message_id=20c2a63d provider=commandcode-b model=deepseek/deepseek-v4.1-flash input=15310 (state=CACHE-MISS; population: 142 warm-eligible turns of 143 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-10-29T08:17:20.540Z..2026-10-29T08:49:29.716Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows.jsonl)
- report generated_at: 2026-10-29T08:49:31.408555+00:00
- usage rows: 143
- model + route: commandcode-b/deepseek/deepseek-v4.1-flash
- input tokens: 748004
- output tokens: 184537
- cache-read tokens: 15933312
- cache-write tokens: 0
- hit ratio: 95.5159% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: commandcode-b/deepseek/deepseek-v4.1-flash: calls=143 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: commandcode-b/deepseek/deepseek-v4.1-flash $0.00000000 vs $0.00000000 over 143 of 143 matched usage rows
- prefix breaks: NOT A PREFIX VERDICT — cache-read census: 1 of 142 warm-eligible turns read 0 cache tokens (state=CACHE-MISS; population: 142 warm-eligible turns of 143 assistant turns in this transcript; 0 carry no cacheRead field; window: 2026-10-29T08:17:20.540Z..2026-10-29T08:49:29.716Z; key: transcript path H:\pi-agent\sessions\--H--sotto--\2026-10-29T03-30-58-532Z_01a185b5-fb64-7711-9482-a93950f13987\YoutubeRows.jsonl)
- WHEN / WHERE failed:
1 of 142 warm-eligible turns read 0 cache tokens; first at 2026-10-29T08:17:20.540Z (message_id=20c2a63d, provider=commandcode-b, model=deepseek/deepseek-v4.1-flash, input=15310)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## 8. SELF-AUDIT

- **claimed-state**: LIVE for the production data path (the oracle calls the
  production `align_painted`, `window_by_paint`, `rows_text`,
  `clean_external_text`, `_display_text`, `_layout`; 16/16 rows and 16/16 drawn
  rows). DARK for the owner's pixels and the live player — not exercised.
- **what-changed**: the production files in §3 (two zero-slack files;
  `caption_overlay.py` net -9 B and `caption_wrap.py` untouched), the lead's
  `youtube_reveal.py` with the internal-`\n` extension now actually used by both
  `window_by_paint` branches, the new `_main/youtube-rows-oracle.py` (my arms
  plus `YoutubeRows-2`'s additive `dom`/`text`/`breaks`/`drop-older` arms), the
  probe env override, and the one 1:1 oracle anchor. No commit, no push, no
  window.
- **commands-run**: the exact commands and rc are in §2, §4, §5, §6. Summary:
  new oracle rc=0; all six neg arms rc=1 by design (rows 13/16, draw 11/16,
  drop-older 13/16 with older_row 0/4, rewrap 15/16 with text_match 16/16,
  text 15/16, shape 15/16 with shape 16/16 -> 1/16); old probe rc=1 (12/16,
  before and after); code-health rc=2
  (pre-existing 12); 1to1 rc=0 (7/7); mirror rc=0; window/captions oracles rc=0;
  py_compile OK.
- **what-I-did-not-do**: I did not launch the app, open a window, take a
  screenshot, commit, push, or edit `worker/**`, `app/panel/**`,
  `_main/_audit-verify-all.cmd`, `AGENTS.md`, or `_cache/**`. I did not change
  `caption_wrap.py`. I did not claim the pixels.
- **refuted-mine**: "re-wrapping can be fixed by choosing a better width" is
  refuted by t=10.192: same joined text, different break. "The old probe staying
  at 12/16 means the fix failed" is refuted by the old probe's own code: it
  joins the rows with a space and never exercises the rows channel; the new
  oracle does (16/16). "The 1to1 oracle's RED is a production regression" is
  refuted: it was one string anchor, fixed in §3.6, and the mutant still proves
  the anchor is discriminating.
- **red-I-did-not-cause**:
  - code-health's 12 RED metrics (`sotto_webview`, `youtube_captions`,
    `youtube_window`, `worker/sotto_worker`): present before this lane, same 12
    metric pairs after. The deltas of the two files I grew (+405 B, +1887 B) are
    on metrics that were already RED; `caption_overlay` improved.
  - `youtube-reveal-oracle.py` 8/10: proven identical with the old and new
    `window_by_paint` in one process (t=6.883805, t=8.264271), so not this
    change.
  - `yt-break-position-probe.py` 12/16: pre-existing; its output is identical
    before/after.
- **gate-doubt**:
  - **verde-de-verdade**: the green run is
    `python _main/youtube-rows-oracle.py` (rc=0), and it is not vacuous:
    `--neg-arm` turns the same comparison red on 13/16, `--neg-arm draw` on
    11/16, and the added `drop-older`/`rewrap`/`text`/`shape` arms go 13/16,
    15/16, 15/16 and 15/16 on the dimensions they neutralise (`rewrap` leaves
    `text_match=16/16` and only moves the break; `shape` guards the word-list
    input). The instrument calls the production functions,
    not copies; the GDI+ measurement is the overlay's own `_layout`. Two named
    boundaries: t=0.023's reconstructed hit (one word; production refuses it),
    and `visible_box=15/16` (the clipped rollup row at t=8.264) which is
    reported but deliberately NOT in the green condition. The old probe's
    12/16 red is real but measures the flattened path, not this fix.
  - **falta-no-gate**: the new oracle is NOT wired into
    `_main/_audit-verify-all.cmd` (that file is forbidden to this lane), so a
    future change that deletes `rows=rows` from `external_caption`, or the
    `'\n'` branch from `_layout`, still leaves the routine battery exactly as
    green as today (the old probe was already red). Code-health only counts
    bytes and would not see a behavioral regression.
  - **gate-melhor**: a mechanical addition by the battery's owner:
    `python _main/youtube-rows-oracle.py` (expect rc=0) plus
    `python _main/youtube-rows-oracle.py --neg-arm draw` (expect rc=1, named
    arm). The input that must leave the first RED: delete `rows=rows` from the
    `push_caption_to_window` call in `external_caption` (the `TICK`/wiring arm
    fails) or join rows with a space in `_layout` (`draw` arm drops to 11/16).
    Until that is wired, this receipt is the only gate for the rows channel.
- **review por outro subagente**: sim — review the oracle's `hit` construction
  and the claim that 16/16 compares the production hit, not a harness hit;
  also re-check the `off0 > 0` gap named in §7.
- **confianca**: alta for the data/rows/break path (16/16, both neg arms red);
  media for the live player and the owner's pixels (unmeasured, as stated).
- **nao verificado**: the pixels; the live player/UIA; `off0 > 0`; a row wider
  than the plate; other videos/languages; ASR/other-player captions containing
  `\n`; the panel/OSD; the app's startup wiring of `youtube_reveal` on a real
  launch.
