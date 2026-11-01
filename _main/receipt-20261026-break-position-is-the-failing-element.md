# Receipt — the element that fails is the LINE BREAK, and it is measurable

Lane `sotto-lane-task-resolver-continuation` · 2026-10-26 · route measured `providerID=opencode-go-3`
(instrument: `_main/receipt-20261026-receipt-provenance.md` §2) · **no commit, no push**.

The owner's own words set the question, and they are the question:

> *"tem que bater timing, linha/quebra de linha e etc, 1:1."*
> *"e pra surgir palavras, quebrar linhas, usar o timing de nova linha ou nao, igual o youtube."*

State: **measured by the author, not `verified`.** No app launch, no window, no pixel capture, no heavy lease.

## 1. Why every existing green could not see this

| gate | what it actually compares | can it see the break position? |
|---|---|---|
| `_main/youtube-1to1-oracle.py` · `linebreaks-1to1` | **number** of lines — *"amostras com numero de linhas diferente: 0/677"* | **No.** Two lines broken at different words have the same count. |
| `_main/yt-1to1-live-compare.py` · yesterday's `16/16 MATCH` | the player's `lines` field, which is the container's **`textContent` — one joined string** | **No.** All 16 samples have `len(lines) == 1`; the joined text matched, so the window scored `MATCH` with an empty `fails`. |
| `_main/yt-break-position-probe.py` (this receipt) | the player's **`segs`** — the segments the player paints, one per row — against `caption_overlay._layout`'s own output | **Yes.** |

So the earlier `MATCH 16/16` was true and useless for this element: it compared one concatenated string to
another. The artefact proves it — `len(lines) == 1` in 16/16, while `len(segs)` is 2 in nine samples and 3 in
four.

## 2. The measurement

`python _main\yt-break-position-probe.py` → **rc 1, `DIVERGE`**, `amostras=16 fronteira_diferente=12
texto_junto_diferente=1`. Video `WdaHAGRBB6s`, geometry `work_width=1920 scale=1.0`, measured with the
overlay's **own GDI+** `_layout`, not a re-implementation.

| t (s) | YouTube paints (`segs`) | the native overlay draws (`_layout`) | verdict |
|---|---|---|---|
| 2.059 | `['Have you ever had to kill a man?', '>> No.']` | `['Have you ever had to kill a man? >> No.']` | 2 rows → 1 |
| 4.681 | `['>> No.', '>> Then this sword is useless.', ">> Don't"]` | `['>> No. >> Then this', "sword is useless. >> Don't"]` | 3 → 2, break moved |
| 6.224 | `['>> Then this sword is useless.', ">> Don't worry about me, Yamato."]` | `['>> Then this sword is useless. >>', "Don't worry about me, Yamato."]` | break moved one word |
| 6.884 | `['>> Then this sword is useless.', ">> Don't worry about me, Yamato. I'll be", 'fine.']` | `[">> Don't worry about", "me, Yamato. I'll be fine."]` — `scrolled off: '>> Then this sword is useless.'` | **a row the player shows is absent from our screen** |
| 10.192 | `["After the ritual, I'd love to train with", 'you sometime.']` | `["After the ritual, I'd love to", 'train with you sometime.']` | break moved two words |

**Positive control inside the same run:** 4 of the 16 samples report `igual` (e.g. t=5.531,
`['>> Then this sword is useless.', ">> Don't worry about me,"]` on both sides). The instrument is not stuck
on `DIVERGE` — it discriminates.

**Not a width artefact.** `--work-width 1280 / 1920 / 2560` each give `fronteira_diferente=12`. Reason
measured, not assumed: `caption_wrap.budget_px(work_width, 34, measure)` returns **714.0 px at all three
widths** — the 42-character ceiling binds before the 68 %-of-work-area rule does.

## 3. The mechanism, with the line it happens on

- `app/webview/caption_overlay.py:661` — `cur_lines, scrolled = _cw.wrap_tail(text or '', cur_w, budget)`.
  The overlay receives **one** `text`; it does not receive the player's rows.
- `app/webview/caption_overlay.py:602` — `_layout` is documented as *"ONE layout for the caption, used by the
  measure AND by the draw"*, which is why the lines it returns are the lines painted, not a proxy.
- `app/webview/caption_wrap.py:55` — `MAX_LINES = 2`; the player paints 3 rows in 4 of these 16 instants.
- `caption_wrap.wrap_tail` treats the payload's newline as whitespace. Measured separately with a 10 px/char
  measure: `"After the ritual, I'd love to train with\nyou sometime."` and the same text joined by a space
  both come back as `["After the ritual, I'd love", 'to train with you sometime.']` at a 400 px budget, and
  as **one line** at 900 px. The newline is not read at all — so even handing the overlay YouTube's exact
  break could not survive.

Two independent proofs, then, and they agree: the input channel cannot carry the break (newline ignored), and
the layout's real GDI+ output puts the break elsewhere in 12 of 16 instants.

## 4. Commands and exit codes (from `H:\sotto`)

| # | command | rc | verdict |
|---|---|---|---|
| 1 | `python _main\yt-break-position-probe.py --json _main\fixtures\yt-WdaHAGRBB6s.break-position-20261026.json` | 1 | `DIVERGE`, `fronteira_diferente=12`, `texto_junto_diferente=1` |
| 2 | `… --work-width 1280` / `1920` / `2560` | 1 / 1 / 1 | `12` at every width — width-invariance, explained by `budget_px` |
| 3 | `python -c "… budget_px …"` | 0 | `[714.0, 714.0, 714.0]`, `MAX_LINES 2` |
| 4 | `python _main\youtube-1to1-oracle.py` (earlier this session) | 0 | `GREEN`, `linebreaks-1to1` counts lines only |
| 5 | `python _main\yt-1to1-live-compare.py --samples 16 --json …` (earlier) | 0 | `MATCH 16/16` over **joined** text |
| 6 | `python I:\!manager\tools\performance-gate.py status` (earlier) | 4 | `AMBER commit-pct=81.1 heavy_allowed=False` |

Artefact: `_main/fixtures/yt-WdaHAGRBB6s.break-position-20261026.json` — 4342 B, sha256
`DA48432FFE63A19722AF98E1BDFA6C6014EB35553F0AD111E05F044B1646DEE0`.

### 4-bis. The verdict path itself, both the arms

A probe that can only say `DIVERGE` proves nothing, so the green path is exercised too, with `--live` pointed at
a synthetic artefact whose `segs` **are** the overlay's own lines:

| input | output | rc |
|---|---|---|
| `--live I:\cc-tmp\yt-break-synthetic-match.json` (segs := `_layout`'s lines) | `fronteira_diferente=0`, `BREAK-POSITION MATCH` | **0** |
| the real 2026-10-26 artefact | `fronteira_diferente=12`, `BREAK-POSITION DIVERGE` | **1** |

So the instrument is discriminating at the **verdict** level, not only per row: same code, same geometry, the
only variable is the input. (`--live` exists because this arm needed it; it is the flag that would otherwise
have been used to "prove" the detector by pointing it at data built to pass.)

## 5. What this does NOT prove

- **Not the pixels.** This compares the layout's line model — the same model the draw consumes — not a capture
  of the native window's surface. A theme with a different face changes the measure; `theme=None` here.
- **16 instants of one 32 s video.** Not the 677 samples, not a long video, not a language other than English.
- **Words and timing are not re-judged here.** The payload half's `words 0/677`, `timing 0/18+0/18` stand as
  measured earlier today; this receipt says nothing about them.
- **`budget_px` was probed with a synthetic 17 px/char measure** (§4 row 3). The 714 figure is therefore
  representative, not the GDI+ number; the *break positions* in §2 are GDI+ and are the load-bearing evidence.
- **No negative arm on the pixels** and none on the reveal; only this element has a discriminating probe today.

## 6. The decision this hands to the owner (I did not touch the product)

Two rules are in conflict inside `_layout`, and only he can pick:

1. **Industry wrap** — break by width, cap at 2 lines, newest words survive (*"verificar online como quebrar
   de um jeito bom"*). That is what ships today.
2. **YouTube 1:1** — break exactly where the player breaks, and show the rows it shows (2 or 3). That is what
   he asked for four times, and what `AGENTS.md` records as the acceptance.

They cannot both hold. Making (2) true means `caption_overlay` must consume **rows** (from `live_lines`,
already one string per row) instead of one `text`, stop calling `wrap_tail` on the 1:1 path, and let
`MAX_LINES` follow the player's capacity (measured: 3, not 2). That is a product change to what appears on
his screen, so it waits for his word — `SOTTO_NEVER_ON_OWNER_SCREEN` applies to verifying it, and a change to
what he sees should not be invented by a lane.

## SELF-AUDIT

1. **claimed-state:** the failing element is **line-break position** (12/16, plus one instant where a row the
   player shows is absent), not words and not timing. `DIVERGE` is measured-by-author, not `verified`.
2. **what-changed:** new instrument `_main/yt-break-position-probe.py`; new artefact
   `_main/fixtures/yt-WdaHAGRBB6s.break-position-20261026.json`; this receipt; the W-16 row in
   `I:\!manager\state\herdr\TODO.md`. **No product file touched** — no edit in `app/` or `worker/`.
3. **commands-run:** §4, six rows with rc; every number quoted from an artefact on disk or from a command run
   in this session.
4. **what-I-did-not-do:** no commit, no push, no app launch, no panel, no Edge launch this turn, no synthetic
   input, no heavy lease, no change to `caption_overlay.py` or `caption_wrap.py`.
5. **refuted-mine:** yesterday's `16/16 MATCH` is **not refuted** — it is shown to be about joined text, which
   is a narrower claim than it looked. My first probe attempt returned `NO-VERDICT` because I read `lines`
   instead of `segs`; the instrument was wrong, not the world, and the fix is in the file.
6. **red-I-did-not-cause:** `performance-gate` AMBER `commit-pct=81.1`; `battery-wiring` `sem_passo=125` vs
   ceiling `124`; `code-health` red on three pre-existing dirty product files. None introduced here.
7. **gate-doubt:**
   - *verde-de-verdade:* the break table is per-instant, both sides printed in full, with 4 samples reporting
     `igual` in the same run — and §4-bis drives the whole verdict path to `MATCH` rc 0 on a clean input, so the
     instrument is not stuck on `DIVERGE`.
   - *falta-no-gate:* nothing yet **fails the battery** when the break drifts. `yt-break-position-probe.py` is
     an instrument, not a wired step; adding it needs a pin change and a decision on whether a red product
     defect should be pinned as `expect-red` — I did not do that in the same turn as finding it.
   - *gate-melhor:* wire `break-position-1to1` next to `linebreaks-1to1` and **replace** the count check with
     it (count is a weaker predicate that stays green while the owner's complaint is true).

## INTENT-PROGRESS

helps: the owner's intention is that what he sees matches YouTube *"1:1 — timing, linha/quebra de linha"*. He
has said the caption is wrong four times, and until today the lane answered with gates that were green
because they compared a **count** and a **joined string**. This turn names the failing element with his own
vocabulary — the **line break** — and shows it failing 12 times in 16 with the overlay's own measurement code,
including one instant where a row he would see on YouTube is not on his screen at all. That converts "it looks
wrong to him" into "this is the line of code, this is the budget, this is the number".

todo: W-16

next: **ask the owner to settle the conflict in §6, then wire the check.** Concretely: `break-position-1to1`
replaces `linebreaks-1to1` in `_main/youtube-1to1-oracle.py` (count → frontier), with a mutant that moves one
break one word and must go RED, because a gate that stays green while his complaint is true is worse than no
gate. And, on his word, `caption_overlay._layout` consumes `live_lines`' **rows** instead of one `text` and
lets capacity follow the player (measured 3, not 2) — that is the change that makes his screen match, and it
is his to authorise because it is his screen.
