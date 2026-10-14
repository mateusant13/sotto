# RECEIPT — TRADE-OFF AUDIT · AREA: PANELCSS

**Lane:** audit trade-offs (subagent) · **date:** 2026-10-13 · measurements taken 14:56–16:08 -03:00
**Subject:** `app/panel/panel.css` **and the sheets it has to live with** — the file cannot be judged
alone, because three other sheets override it (see §4/§5).
**Product root measured: `H:\sotto`.** The owner's app was NOT launched, and no shell, worker or
WebView2 probe was run: everything below is static (bytes, parse, cascade arithmetic, corpus greps).
The single renderer-dependent check is listed in §6 and marked **UNMEASURED**.

## 0. Pin (AGENTS.md rule 2)

| what | value |
|---|---|
| file | `app/panel/panel.css` |
| bytes | **119 959** |
| lines | **3 142** (CRLF 3 141 / bare LF **0**) |
| sha256 | `c6c33850902226a13d89de153b9c55adb243d13e16f240118309428dc61896da` |
| mtime | 2026-10-13T13:08:14.936Z |
| rule blocks | **312** (comments stripped); **3** `@media` blocks |
| heads scoped `body[data-surface="strip"]` | **59** |
| `!important` **declarations** | **3** — `:1472`, `:1699`, `:2600` (the other 4 `!important` hits are inside comments: 1467, 2594, 2595, 2911) |

**Why the product root and not a worktree (measured).** `H:\sotto-wt\ArbV8\app\panel\panel.css` is
**77 751 B / 2 339 lines / sha `6250884b…`**, and `ArbV8\app\panel\caption-float.css` and
`…\zip-overlay.css` **do not exist** (ENOENT). The worktree is therefore not the document the shell
loads. **Every line number below is valid only against the 119 959 B / `c6c33850…` revision — re-grep
before acting on one.**

**Instrument.** `node` over the bytes; rule split by comment-stripping + brace matching;
specificity by the standard (a,b,c) algorithm; the "does this selector match anything" corpus is
`panel.html` plus the 16 modules `panel.html` loads; sibling-sheet load order read from the
`<link>` tags plus the JS that injects sheets (`themes/panel-designs.js` → `panel-designs.css`,
`skin-host.js` → `skin-layout.css` + `skins/skin-shim.css`, `caption-float.js` →
`caption-float.css` idempotently).

## 1. Verdicts at a glance

| # | site | claim it defends | verdict |
|---|---|---|---|
| T1 | `:2890-2906` `.strip-button--pause` | Pause is filled / is the row's verb | **REMOVER** — dead selector |
| T2 | `:2603-2610` `.status .chrome` on strip | specificity stops a theme leaking chrome | **REMOVER** — unreachable, and the number is wrong |
| T3 | `:1502-1510` `.captions__bar` / `.captions__body` on strip | strip caption-box sizing | **REMOVER** — dead (ancestor hidden) |
| T4 | `:1495-1500` strip `.status` padding/align | strip readout layout | **REMOVER** — dead (ancestor hidden) |
| T5 | `:1475-1477` vs `:2915-2917` | the bar shows on strip | **REMOVER** one — exact duplicate |
| T6 | `:2560-2577` `.strip-button--theme` / `.strip-theme__swatch` | the strip's theme key | **REMOVER** — dead selector (pill removed 2026-10-12) |
| T7 | `:1863-1865`, `:1956-1963` `.strip-button--chevron` | the strip chevron's tight box | **REMOVER** — dead selector (never assigned) |
| T8 | `:1929-1931` `#strip-theme-chevron` hide | 2nd layer against a re-created node | **MANTER** (belt; comment is now the whole story) |
| T9 | `:2518-2520` `.caption__ch{display:inline}` | floor for the type reveal | **MELHORAR** — no-op declaration |
| T10 | `:1996-1999` `font-size:0` not `display:none` | a11y tree + a read-back probe | **MELHORAR** — the cited instrument cannot tell the two apart |
| T11 | `:1300-1312` + `:1583-1587` `prefers-reduced-motion` | motion a11y | **MANTER** + comment fix (asymmetry with `:2533-2558`) |
| T12 | `:3015-3028`, `:3086-3111` `.caption-float*` | the overlay's 4px bar, no-paint meter | **MELHORAR** — decided in two other files |
| T13 | `:2919-2932` triplicated header | — | **MELHORAR** — dedupe |
| T14 | `:1802-1814` "THE TWO EXCEPTIONS" | two labels stay on the bar | **MELHORAR** — one of the two is gone |
| T15 | `:1470-1472` + `:2599-2601` | no body-appended popup on the strip | **MELHORAR** (optional) — 3 hides, 2 rules |
| T16 | the 10 `*[hidden]{display:none}` backstops | `hidden` survives an author `display` | **MANTER** — 1 of 10 is provably load-bearing, the rest are cheap |
| T17 | `:345-347` neutral base tokens | a theme may restyle without moving the list | **MANTER** — verified, no conflict |
| T18 | `:610-611` CSS-only collapsed hide | read-back probes still count rows | **MANTER** — verified in markup |
| T19 | `:2512-2531` fail-VISIBLE type reveal | a suppressed animation must not blank the word | **MANTER** — construction verified correct |

Dead-rule footprint of T1–T7: **~1 309 B / ~45 lines of panel.css (1.09 %)** that no element in the
loaded document can ever match. With the comment prose that justifies them, ~2.6 KB (2.20 %).

## 2. The trade-offs, one by one

### T1 — `panel.css:2895-2906` (comment `:2890-2894`): the Pause rule paints nothing

**1. The exact line and what it claims.** Two rule blocks give
`body[data-surface="strip"] .strip-button--pause` a filled blue treatment plus a hover/focus pair.
The comment claims: *"THE ACTION AT THE END OF THE ROW keeps a voice of its own: Pause is the one that
costs a model load to resume, so it is filled rather than outlined and reads as the row's verb."*

**2. What it buys (as designed).** A distinct affordance for the most expensive action on the bar.

**3. What it costs — measured.** Nothing is bought, because nothing matches. `panel.html:837-843`
declares the button as

    <button type="button" class="strip-button" id="strip-pause-button" data-pause-trigger title="Pause">

— class list `strip-button`, **no `strip-button--pause`**. The token occurs in **0 of 11**
panel files (panel.html, panel.js, theme-switcher.js, theme-tune.js, surface.js, skins.js, skin-host.js,
caption-float.js, strip-drag.js, letter-swap.js, history-gallery.js), and it cannot be built dynamically:
a grep for `'…--' +` across the 6 modules that create nodes returns **0**, and the only factory that
takes a class as an argument — `theme-switcher.js:634 makeChevron(doc,id,className)` — is called
**exactly once**, with `'icon-button theme-chevron'` (`:671`). So the rule is unreachable:
2 blocks / 11 declarations / 17 lines = **780 B** of committed, reasoned design.

**4. VERDICT: REMOVER.** It is unreachable, and this file's own stated standard
(`:1884-1889`: *"an `order` on an id that does not exist is a rule about nothing, and this
file's own rule is that a dead declaration is removed rather than left looking live"*; `:1481-1490`)
says exactly this is the trap to avoid.

**5. Concrete change + proof.**
- **Option A (what the comment intends):** add `strip-button--pause` to `panel.html:839`. That is
  a product edit in another lane's file — the Lead owns it; I did not touch it.
- **Option B (what the evidence supports):** delete `:2890-2906`.
- **Proof it cannot break:** `grep -rn "strip-button--pause" app/panel` must be **0** after the edit
  (it is 3 today, all in panel.css). Renderer check (owed, §6): the computed
  `borderColor`/`backgroundColor`/`color` of `#strip-pause-button` must equal the values
  from `body[data-surface="strip"] .stripbar .strip-button` (`:1825-1831`) before **and** after —
  identical, because the removed selector never participated in any match.

### T2 — `panel.css:2608-2610` (comment `:2603-2607`): a specificity claim that is wrong twice, about an element that is never rendered

**1. The exact line and what it claims.**
`body[data-surface="strip"] .status .chrome { display: none; }` with the comment: *"The footer chrome
is a PANEL-surface thing: the strip keeps its dot and one word (the status block is the only footer it
has). Specificity is deliberate — `body[data-surface] .status .chrome` (0,3,2) outranks a theme's
`:root[data-theme] .chrome--x` (0,3,0), so no theme can leak a label into the strip's ~100 px."*

**2. What it buys (as designed).** A guarantee that no theme's chrome label paints on the 40 px strip.

**3. What it costs — measured, three separate ways.**
- **The number is wrong.** `body[data-surface="strip"] .status .chrome` = type **1** (`body`),
  class-level **3** (`[data-surface]`, `.status`, `.chrome`) → **(0,3,1)**, not (0,3,2).
  The conclusion still holds against the competitor the comment names, but the arithmetic in the comment
  is off by one type unit.
- **The competitor it names is not the real one.** Themes write
  `:root[data-theme='theme-N'] .chrome--tele[data-chrome="head"]` = **(0,4,0)**, which **beats**
  (0,3,1). Measured across 11 sheets: theme-1`:624`/`:659`, theme-2`:637/693`,
  theme-3`:638/661`, theme-4`:623/651`, theme-5`:637/697`, panel-designs (10 sites). So the
  rule **cannot** be what keeps chrome off the strip.
- **The rule is unreachable anyway.** `.status` is `<footer class="status" id="status">`
  (`panel.html:894`) and it is the parent of **every** `.chrome` span. `panel.css:2847-2849`
  sets `body[data-surface="strip"] .status { display: none; }`, and `:2859-2866` already measured
  that *"no theme or skin sets `display` on `.status` (0 of 15 stylesheets)"*. A descendant of a
  `display:none` box cannot paint. The declaration can never be the thing that hides anything.
- **The comment's other half is also false today:** *"the strip keeps its dot and one word (the status
  block is the only footer it has)"* contradicts `:2843-2846`, which says the strip's readout is
  `#strip-state` **inside the bar** and the `.status` row is `display:none` on that surface.

**4. VERDICT: REMOVER** the rule, and rewrite the comment (or delete it with the rule). The real defences,
enumerated, are: (a) `.chrome` base `display:none` at `:2399-2404`; (b) each theme's own
`:root[… ] body[data-surface="strip"] .chrome[data-chrome="head|foot"] { display:none }` at **(0,5,1)**
in the theme's own file (theme-1`:707-710`, theme-2`:739`, theme-3`:705`, theme-4`:699`,
theme-5`:769`, panel-designs 6 sites); and (c) `skin-layout.css:222`
`body[data-skin] .status .chrome { display:none !important }`. All three already exist.

**5. Concrete change + proof.** Delete `:2603-2610`. Proof: re-run the existing census (no stylesheet
sets `display` on `.status`) and add the corollary — for each of the 11 sheets, the only
`display` declarations matching `.chrome` on the strip are the base (0,1,0)=none and the theme's
(0,4,0) show / (0,5,1) hide pair. A (0,3,1) rule sitting strictly between them cannot change the winner in
any shipped theme. Renderer check (owed): on `#strip`, `#status` must report
`getClientRects().length === 0` before and after. **If the Lead prefers a real backstop for a future
theme that shows a non-`data-chrome` chrome**, the change is
`body[data-surface="strip"] .status .chrome { display: none !important }` — the same form
`skin-layout.css:222` already uses for the identical problem; panel.css has 3 such declarations
today, so it is not a new category. But it buys a guarantee the ancestor hide already gives.

### T3 — `panel.css:1502-1510`: the strip's caption-box rules are dead

**1.** `body[data-surface="strip"] .captions__bar { min-height: 12px }` and
`body[data-surface="strip"] .captions__body { border-radius: 8px }`, with comments describing "the live
box's own label row" and its radius on the strip.
**2. Buys:** a one-size-down label row and a rounded body for a strip caption box.
**3. Costs — measured:** `.captions__bar` and `.captions__body` are children of
`<section class="captions">` (`panel.html:562`) and `panel.css:2855-2857` sets
`body[data-surface="strip"] .captions { display: none }`. The file itself repeats that in `:2859-2866`
(*"NOTHING ELSE RENDERS ON THIS SURFACE"*). Two rules / 9 lines = **277 B**, unreachable.
**4. VERDICT: REMOVER.**
**5. Proof:** re-run the ancestor/descendant check — `grep` the markup chain and assert
`.captions` is `display:none` on strip (already recorded at `:2851-2857`); the only new fact is
that these two selectors' only matches live inside it. Renderer check: `#captions-body`
`getClientRects().length === 0` on `#strip` on both sides.

### T4 — `panel.css:1495-1500`: the strip `.status` properties are dead

**1.** `body[data-surface="strip"] .status` sets `padding-top:4px; align-items:center;
justify-content:flex-start; gap:6px`, with *"The status block is the one thing the strip keeps from the
footer"*.
**2. Buys (as designed):** the strip's status-row layout.
**3. Costs — measured:** the same ancestor rule at `:2847-2849` makes `.status` `display:none`
on the strip, so all 4 declarations are inert. 6 lines = **131 B**. Note the selector also appears at
`:2847` (the live hide) — a reader who greps for it finds two rules and the *first* one is the dead
one, which is exactly the "left looking live" trap the file warns about.
**4. VERDICT: REMOVER.**
**5. Proof:** same as T3 — assert the only rule that can make `.status` paint on strip is the
`display:none` at `:2847` (0 sheets set `display` on it, per `:2864`).

### T5 — `panel.css:1475-1477` vs `:2915-2917`: the same rule twice

**1.** `body[data-surface="strip"] .stripbar { display: flex; }` appears **verbatim at both sites**
(1 440 lines apart).
**2. Buys:** the strip's control row is shown on the strip surface.
**3. Costs — measured:** one of the two is redundant under every cascade rule (same selector, same
declaration, same origin, same value) — 3 lines / **61 B** of pure duplication. It is also the second of
**three** rule blocks for that head (the third, `:1687-1689`, sets `cursor:grab`).
**4. VERDICT: REMOVER one.** Keep `:2915-2917` (it sits next to the block that explains the strip
scoping) and delete `:1475-1477`, or vice versa — either is behaviour-neutral.
**5. Proof:** a parse check that the head occurs once after the edit; then the DOM check that
`#strip .stripbar` still computes `display:flex` (it must: identical declaration still present,
equal specificity, later or equal order).

### T6 — `panel.css:2560-2577`: the strip's theme pill is gone; its rules are not

**1.** *"the strip's theme key"*: `.strip-button--theme { padding-left: 6px }` (`:2567-2569`) and
`.strip-theme__swatch` (`:2571-2577`), with the claim that *"It is a `.strip-button` like its
three neighbours, with the theme's accent as its swatch."*
**2. Buys (as designed):** the strip's own theme control, so the owner can change theme from the key's surface.
**3. Costs — measured:** `#strip-theme-button` was removed from the markup on 2026-10-12 — the
`panel.html` comment at that site says so verbatim (*"WHAT STOOD HERE WAS `#strip-theme-button`, a
`.strip-button--theme` pill that cycled the template on click"*). The token `strip-button--theme`
occurs in **0 of 11** panel files except that comment; `strip-theme__swatch` likewise **0 of 11**. So
3 of the 4 declarations are on a class no element carries. 18 lines = **693 B**.
**4. VERDICT: REMOVER** `:2560-2577` (keep the *next* block, `:2579-2601`, which is live: it refuses
the dropdown on the strip by surface attribute — that one has a real job).
**5. Proof:** `grep -rn "strip-button--theme\|strip-theme__swatch" app/panel` → **0** after the edit
(today: 4 hits, all panel.css); plus the `#strip` DOM must be unchanged because no node carries either
class (assert `document.querySelectorAll('.strip-button--theme,.strip-theme__swatch').length === 0`).

### T7 — `panel.css:1863-1865` and `:1956-1963`: `.strip-button--chevron` is never assigned

**1.** Three blocks: `body[data-surface="strip"] .strip-button--chevron { justify-content: center }`,
`.strip-button--chevron { min-width: 26px; justify-content: center }`, and
`.strip-button--chevron svg { width: 13px; height: 13px }`, under the claim (comment `:1945-1955`)
that *"the cycle button and the list chevron keep the ONE shape the owner asked for"*.
**2. Buys (as designed):** the tightest box on the bar for the strip's list chevron.
**3. Costs — measured:** the strip chevron no longer exists in markup **and** the module no longer builds
it: `theme-switcher.js` `:680-689` documents the deleted builder block, `:663` still queries
`#strip-theme-chevron` and `:618 isPanelChevron` **refuses** a strip-bar chevron
(`:660-664`), and the single factory call (`:671`) passes `'icon-button theme-chevron'` — not
`strip-button--chevron`. The token occurs in **0 of 11** panel files. 3 blocks / 8 lines total =
**227 B**; with the `:1945-1955` prose, ~0.5 KB.
**4. VERDICT: REMOVER** both rule blocks and the `:1945-1955` comment.
**5. Proof:** `grep -rn "strip-button--chevron" app/panel` → **0** after the edit (today: 4 hits, all
panel.css); and assert `document.querySelectorAll('.strip-button--chevron').length === 0` in both
surfaces. Note the *adjacent* `#strip-theme-chevron` hide (T8) is a **different** selector and should
NOT be removed in the same pass.

### T8 — `panel.css:1929-1931`: `#strip-theme-chevron` hide — MANTER

**1.** `body[data-surface="strip"] #strip-theme-chevron { display: none }`; the comment
(`:1912-1928`) calls it "LAYER 2" and says it "STAYS".
**2. Buys:** if a future markup line re-ships the node, it is invisible, and `registerChevron` refuses
to wire it — so an idle node cannot open the list.
**3. Costs — measured:** 1 rule / 3 lines / **72 B**, and it matches nothing today (the id occurs in
`panel.html` only inside comments). Cost is negligible; the defensible part is that it is a
declaration about a *node the module may re-add*, not about a class the code never made (contrast T6/T7).
**4. VERDICT: MANTER.** Its comment is honest ("two layers, not one") and both layers are verifiable.
**5. No change.** If the Lead wants to tighten, the comment could name
`theme-switcher.js:634-678`/`:680-689` as the instrument that keeps the id absent — it already does,
by file, without line numbers.

### T9 — `panel.css:2518-2520`: `.caption__ch { display: inline }` is a no-op

**1.** The rule body is a single declaration, `display: inline`, under the 33-line type-reveal
comment block.
**2. Buys (as intended):** a floor so the reveal's holder is inline.
**3. Costs — measured:** `.caption__ch` is created as `document.createElement('span')`
(`panel.js`, `paintWords`) and **no** loaded stylesheet declares `display` on
`.caption__ch` (measured across 13 sheets; the cinematic/panel-designs overrides touch only
`animation`/`transition`). `display:inline` **is** the initial value for a span, so the
declaration changes nothing. It also cannot act as the floor the historical bug needed: an unscoped theme
rule `.caption__mark{display:none}` at (0,1,0) ties this rule and **wins on order** (panel.css loads
before the theme sheets) — that is precisely the leak recorded in AGENTS.md §10. 3 lines / **45 B**.
**4. VERDICT: MELHORAR** — delete the rule, keep the comment block (it is the valuable part: the
fail-VISIBLE argument).
**5. Concrete change + proof.** Remove `:2518-2520` (the `.caption__ch` rule only). Proof: assert
no loaded sheet sets `display` on `.caption__ch` (re-run that grep), and in the renderer read
`getComputedStyle(aCharSpan).display` — must remain `inline` on both sides. Same test, if
desired, for the two sibling no-ops `.caption__word` (`:2475-2477`) and `.caption__mark`
(`:2481-2483`) — **but keep those two**: `.caption__mark` *does* have live competitors
(theme-3 sets `display:inline-block`; cinematic and panel-designs set `display:none`), so its base
declaration is not provably vacuous, and removing it widens the blast radius for no gain.

### T10 — `panel.css:1996-1999`: the `font-size: 0` citation cannot prove what it is cited for

**1.** *"The DOM label is hidden with `font-size: 0`, NOT `display:none`, so its text stays in the
accessibility tree and a read-back probe still finds it (measured: `_main/_panel2-dom-probe.js` ARM T
reads that exact `textContent` and expects the word to still be there)."*
**2. Buys:** a real distinction — `display:none` removes a subtree from the a11y tree; `font-size:0`
does not.
**3. Costs — measured.** The cited instrument **cannot distinguish the two options**:
`_main/_panel2-dom-probe.js` ARM T runs `wiredT.id('strip-live-label').textContent` and expects
`'LIVE'` — `textContent` returns that same string under `display:none`. So the ARM T line is
true but does not support the "NOT `display:none`" claim. The claim is *also* partly redundant: the
button already carries `aria-label="live: off — …"` (`panel.html`), and an `aria-label` overrides
the subtree for accessible-name computation, so neither hide removes the control's name. The one honest,
unmeasured difference is the a11y-tree presence of the label text itself. Residual cost: the zero-width
label still consumes the `gap:5px` of `.strip-button`, so the LIVE pill is ~5 px wider than needed.
**4. VERDICT: MELHORAR** the comment, not the rule. Keep `font-size:0` (it is the more careful choice);
stop citing ARM T as the proof and state the real reason.
**5. Concrete change + proof.** Rewrite `:1996-1999` to: the label is hidden with `font-size:0` rather
than `display:none` so the word keeps a place in the DOM and in the a11y tree; the button's accessible
name comes from its `aria-label` either way; ARM T pins `textContent` and does not discriminate the two
techniques. Anything stronger is a renderer measurement (owed, §6) — I did not make it.

### T11 — `panel.css:1300-1312` + `:1583-1587`: two `prefers-reduced-motion` blocks survive the reasoning that removed the third

**1.** `:1300-1312` sets `animation:none` on `.listening span`, `.caption` and
`.status__dot[data-state="live"]::after` (`opacity:0.4`); `:1583-1587` does the same for
`body[data-surface="strip"] .listening span`.
**2. Buys:** a reader who asked for less motion gets static, non-pulsing indicators.
**3. Costs — measured / reasoned.** `:2533-2558` records the **measured** decision that the *third*
`prefers-reduced-motion` block (on the char spans) had to go: on this box
`SPI_GETCLIENTAREAANIMATION=0` maps onto `prefers-reduced-motion: reduce`, so that block silently
disabled the feature the owner asked for twice. **That same OS flag makes the two surviving blocks active
on the owner's own machine today**, and nothing in the file says so. The difference that justifies keeping
them: unlike the reveal, they degrade to a **static but visible** state (`.listening span` base is
`width:4px; height:10px; opacity:.5`; the halo keeps its ring and the file says so at `:1305-1307`),
so they blank nothing.
**4. VERDICT: MANTER** — but **MELHORAR the comment at `:1300`**, because the file's own standard is to
say what was measured. As shipped, a reader meets three `prefers-reduced-motion` blocks, one of which is
gone with a 26-line explanation, and the other two with no explanation at all — the natural inference
("those two must be safe") is an unmeasured inference.
**5. Concrete change + proof.** Add 3 lines at `:1300`: this query is ACTIVE on this box (measured OS
flag, cited at `:2538-2543`); these two animations intentionally fall back to a static, still-visible
state, unlike the char reveal whose base would have been invisible. The only missing fact is
`matchMedia('(prefers-reduced-motion: reduce)').matches` **read from the renderer** — which
`:2553-2558` itself says has never been done (`grep` finds no `matchMedia` call anywhere in the
shell). That is the one measurement I could not make (§6).

### T12 — `panel.css:3015-3028` and `:3086-3111`: the overlay's own design is decided in two other files

**1. The lines and what they claim.**
- `:3015-3019`: *"THE BAR THE TEXT LEANS ON. 4px, rounded, the panel's own accent gradient … the zip's
  `led-breathe` keyframe"*, with the owner's words *"tipo uma barra a esquerda dela, onde ela se apoia"*.
  Declaration at `:3020-3028`: `width:4px; border-radius:999px; background: var(--accent-gradient)`.
- `:3086-3088`: *"The listening meter: the zip's own three bars, collapsed to one fill … `panel.js`
  writes the level; CSS owns the shape."* Declarations at `:3089-3098` (`height:3px`…), `:3100-3102`
  (`.is-on{opacity:1}`), `:3104-3111` (`.caption-float__meter-fill`).
**2. What they buy:** the overlay's minimal 4 px body and a themed level meter — "ONE body, the bar", the
owner's own rule.
**3. What they cost — measured, and this is the sharpest cross-file finding in the area.**
- `caption-float.css:102-105` sets `#caption-float .caption-float__meter { height: 0; margin: 0 }`
  at **(1,1,0)**, which beats panel.css's `.caption-float__meter` at **(0,1,0)**. Its comment
  (`caption-float.css:96-101`) says the element *"and its id stay … the plate goes: zero height, zero
  margin, nothing painted"*. So **3 of panel.css's rules / 8 declarations are inert**: the meter is a
  zero-height, zero-margin box. The `transform:scaleX(0)` + `transition:opacity` animation can never be
  seen. The comment at `:3086-3088` claiming "CSS owns the shape" is false about the shipped cascade.
- `zip-overlay.css:321-328` sets `body[data-float="on"] .caption-float__stage { border … !important;
  border-radius:10px !important; background: rgba(5,7,10,0.86) !important; padding … !important; box-shadow
  … !important; max-width … !important }`. That **beats** `caption-float.css:59-93`'s explicit
  "NOTHING PAINTS … NOT THE OVERLAY, NOT A DESCENDANT" list (which names `.caption-float__stage`), and it
  beats panel.css's `:2923-2926` *"with NO BACKGROUND EVER"* and `:2950-2954` *"No plate, no box, no
  backdrop, no border — the bar IS the body."* `!important` wins over any non-important author rule,
  whatever its specificity, so **the only state in which the stage paints at all (`data-float="on"`) is the
  state in which the stage is a bordered filled card.** Two files assert opposite invariants about the same
  element; the `!important` one wins.
- `zip-overlay.css:249-255` sets `body[data-float="on"] .caption-float__led { width:6px !important;
  height:6px !important; border-radius:50% !important; background:#37d67a !important; box-shadow … }`,
  which beats panel.css's `width:4px; border-radius:999px; background: var(--accent-gradient)`. So the
  "4 px bar" is a 6 px round green dot in the only state it renders.
- `zip-overlay.css:151` sets `body[data-surface="strip"]:not([data-float="on"]) .stripbar * { color:
  #0b0f14 !important }`, which beats panel.css's ID-level LIVE colour pair at `:2022-2026` and
  `:2042-2049` — the very rules whose comment at `:2001-2003` promises *"no `:root[data-theme]
  .strip-button` rule (a=0) in any theme can put the old red back on the OFF state."* True of themes; false
  of the shipped sibling.
- `zip-overlay.css:177-181`'s five `body[data-surface="strip"] .captions__list > li:nth-*` opacity
  rules are inert because `panel.css:2855-2857` hides `.captions` on the strip — the file's own
  comment at `zip-overlay.css:183-186` admits *"STEP 3 ABOVE TARGETS THE WRONG ELEMENT. IT IS INERT."*

**4. VERDICT: MELHORAR** — do not delete on my word, but the *documentation* in panel.css is wrong and
should be corrected, and the two meter rules (and the dead `width`/`border-radius` on the bar) are
candidates for deletion once the owner confirms the card is the intended look.
**5. Concrete change + proof.** (a) Rewrite `:3086-3088` and `:3015-3019` to name the actual winner
(`caption-float.css:102-105` and `zip-overlay.css:249-255` / `:321-328`). (b) If deleting the meter
rules: the deletion is provably safe because the winner (`caption-float.css` `height:0`) does not
reference any of the removed declarations — a cascade resolver over the 13 sheets shows the winning
declaration for every removed property comes from a different file both before and after. The same
argument covers `width:4px`/`border-radius` on `.caption-float__led`. Renderer confirmation of the
visual (owed, §6): `#caption-float .caption-float__meter` `height` must read `0px`, and
`.caption-float__led` `width` `6px` / `border-radius` `50%`, on the current build.

### T13 — `panel.css:2919-2932`: the same header comment three times

**1.** The header *"── 3. THE FLOATED CAPTION (the zip's CaptionStage, translated) ────"* appears **three
times** (`:2919`, `:2921`, `:2927`) and the four-line paragraph *"Bottom-anchored, full width,
centred inside `max-w-5xl` …"* appears **twice** (`:2923-2926` and `:2929-2932`). Syntactically
harmless (the duplicate opens and closes a comment), but it is the same defect category the lane is
hunting: dead weight that a reader must re-read to discover it says nothing new.
**2. Buys:** nothing.
**3. Costs — measured:** 14 lines / **~0.5 KB** of duplicated prose at the head of the floated-caption
section.
**4. VERDICT: MELHORAR** — collapse to one header + one paragraph.
**5. Proof:** the file's own scope-leak / parse gates are unaffected (comment-only change); a byte diff must
show only comment lines removed, and `node _main/scope-leak-oracle.js` must stay GREEN.

### T14 — `panel.css:1802-1814`: "THE TWO EXCEPTIONS" names a control that no longer exists

**1.** *"THE TWO EXCEPTIONS, both deliberate: 1. `#strip-theme-button` keeps its label … 2.
`#strip-live-label` keeps the word LIVE."*
**2. Buys:** the rationale for why two labels survive the icon-glyph trim.
**3. Costs — measured:** exception 1 is gone — `#strip-theme-button` was removed from the strip markup on
2026-10-12 (see T6) and the class exists nowhere. Only exception 2 survives. A reader is told a second
control keeps a label, and then finds no such control.
**4. VERDICT: MELHORAR** — rewrite to *"THE ONE EXCEPTION (the theme pill was the other until 2026-10-12)"*.
**5. Proof:** comment-only; cross-check against the dead-token census in T6/T7 (0 matches).

### T15 — `panel.css:1470-1472` + `:2599-2601`: three popup hides, two rules

**1.** `body[data-surface="strip"] .theme-picker, body[data-surface="strip"] #tune-dialog { display:none
!important }` (`:1470-1472`) and `body[data-surface="strip"] .theme-dropdown { display:none !important }`
(`:2599-2601`). Three body-appended popups, one treatment.
**2. Buys:** no body-level popup can paint on the 100 px strip when the surface flips mid-preview (the
reason is spelled out at `:2586-2598`: the owner can switch surfaces with the dropdown still open).
**3. Costs — measured:** two rules instead of one, with two separate rationales. The specificity
difference between `#tune-dialog` (1,1,1) and `.theme-dropdown` (0,2,1) is irrelevant under
`!important`, so nothing but the comments keeps them apart. ~0 behavioural cost; a small
findability cost (a lane adding a fourth popup has two places to look).
**4. VERDICT: MELHORAR (optional / low priority)** — merge into one rule and one combined comment. If the
Lead prefers each rationale adjacent to its selector, **MANTER** is fine; this one is genuinely a wash.
**5. Concrete change + proof.** Merge both preludes and delete the duplicate declaration. Proof: the
cascade is unchanged for all three selectors because the declaration and its `!important` are identical;
assert with a parse that each of the three selectors still has exactly one matching `display:none
!important` rule, and that no other rule setting `display` on them exists outside the strip scope.

### T16 — the `*[hidden]` backstop pattern — MANTER

Measured: panel.css carries 10 `X[hidden]{display:none}` rules (`:362`, `:675`, `:845`,
`:865`, `:1067`, `:1142`, `:1238`, `:2165`, `:2649`). Exactly **one** is provably
load-bearing — `.captions__list[hidden]` (`:1142`), because `.captions__list` sets
`display:flex` (`:1130-1136`); the file measured that one and recorded it (`:1138-1141`). For the
other eight (including `.theme-dropdown[hidden]` at `:362` and `.theme-picker[hidden]` at
`:2649`) **no loaded sheet sets `display` on the base selector** (measured across 13 sheets), so
they are currently no-ops — but they are the only reason a future theme that sets `display` cannot defeat
`[hidden]`, at one declaration each. **VERDICT: MANTER.** One caveat for the comment at `:346`:
*"`[hidden]` wins over every display"* overstates — it wins only over an **unset** display; an author
`display` wins over the user-agent `[hidden]` rule, which is the whole reason these ten rules exist.
Rewrite that half-sentence.

## 3. The specificity ledger (what the comment claims vs what the cascade does)

Computed with the standard (a,b,c) algorithm; "winner" considers `!important` first, then specificity, then
source order (panel.html links panel.css, then caption-float.css, then theme-1..5, zipc-panels, zip-overlay;
panel-designs.css and skin-layout.css are injected afterwards).

| selector (site) | computed | strongest competitor | winner |
|---|---|---|---|
| `body[data-surface="strip"] .status .chrome` (`:2608`) | **(0,3,1)** — comment says (0,3,2) | `:root[data-theme='theme-N'] .chrome--tele[data-chrome="head"]` (0,4,0); `:root[… ] body[data-surface="strip"] .chrome[data-chrome="head"]` (0,5,1); `skin-layout.css:222` (0,3,1)**+important** | **never panel.css** |
| `body[data-surface="strip"] .stripbar .strip-button` (`:1792`) | (0,3,1) — comment says (0,3,1) ✓ | `:root[data-theme='theme-N'] .strip-button` (0,3,0) | **panel.css** — claim correct |
| `body[data-surface="strip"] #strip-live-button[aria-pressed="true"]` (`:2022`) | (1,2,1) | theme (0,3,0) → panel.css; `zip-overlay.css:151` (0,3,1)**+important** | **zip-overlay** (float off) |
| `body[data-surface="strip"] #strip-live-button .strip-button__label[::after]` (`:2008-2019`) | (1,2,1) | theme label rules (0,3,0) → panel.css; `zip-overlay.css:115/151` **+important** | **zip-overlay** (float off) |
| `caption-float__led` width/border-radius/background (`:3020-3028`) | (0,1,0) | `zip-overlay.css:249-255` (0,2,0)**+important** | **zip-overlay** |
| `caption-float__meter*` (`:3089-3111`) | (0,1,0) | `caption-float.css:102-105` (1,1,0) | **caption-float** |
| `caption-float__stage` no-paint (`:2926` / caption-float.css:84) | (0,1,0) / (1,1,0) | `zip-overlay.css:321-328` (0,2,0)**+important** | **zip-overlay** |
| `body[data-surface="strip"] .status .chrome` — the *ancestor* that settles it | `.status` display:none (`:2847`, (0,2,1)) | 0 sheets set display on `.status` (census `:2864`) | **panel.css** — the real hiding rule |

## 4. The "deliberate" markers the brief named — measured verdicts

| marker | what it claims | measured | verdict |
|---|---|---|---|
| `:345-347` neutral base tokens | themes may restyle below without moving the list | no loaded sheet overrides `.theme-dropdown` / `__list` / `__option` / `__swatch` (0 of 13) | **MANTER** |
| `:1802` "the two exceptions" | two labels survive the glyph trim | exception 1 (`#strip-theme-button`) removed 2026-10-12; class in **0 of 11** files | **MELHORAR** (T14) |
| `:610-611` collapsed is a CSS-only hide | rows stay in the DOM for read-back probes | verified in markup: `.hist` rows live in `.history__body`, the only node hidden | **MANTER** |
| `:2517` fail-BLANK is forbidden | base opacity is 1, fill is `both`, so a suppressed animation stays readable | verified: `.caption__ch` carries no `opacity` of its own; 15 of the 25 named cinematic themes ship `animation: none` on it and 2 replace it with their own `cine-*` keyframe — both paths resolve the char at its base `opacity:1`, i.e. readable, which is the fail-VISIBLE property exercised in production | **MANTER** — the construction is right; this is the file's best-argued rule |
| `:2604` specificity is deliberate | (0,3,2) beats a theme's (0,3,0) | (0,3,1), and the real competitor is (0,4,0) / (0,5,1) / important; the rule is also unreachable | **REMOVER** (T2) |
| `:2910` strip scoped on purpose | one sheet for every surface; a strip rule must never fire on the panel | **true** — and it is also the *only* mechanism here; but see §5: it does not defend against the sheets that actually win | **MANTER**, documented |
| `:2923/2950` "NO BACKGROUND EVER" / "the bar IS the body" | the overlay paints no plate | overridden by `zip-overlay.css:321-328 !important` in the only state the overlay paints | **MELHORAR** (T12) |

## 5. The pattern the Lead should act on

The `body[data-surface="strip"]` prefix (59 heads) and the ID-level `a=1` defences (`:1966-1971`,
`:2001-2003`, `:1868-1873`) are all built to beat **themes** — `:root[data-theme='theme-N']
.class` at (0,3,0). Against that specific competitor they are **correct** (T-objs verified arithmetically).
The document's actual overriders are different: `zip-overlay.css` (51 `!important`),
`caption-float.css` (2), `skin-layout.css` (10), `panel-designs.css` (10), each with
`!important` and each loaded after panel.css. **`!important` beats any non-important author rule
regardless of specificity, so none of the 59 scoped heads and none of the `a=1` claims can compete with
those files** — and, measured, several panel.css rules are already dead because of them (T12) or because an
ancestor in the same file hides the box (T2/T3/T4).

The transferable rule, in the house style: *a specificity defence is only as good as the set of competitors
it was priced against. Before adding an `a=1` or an `.stripbar` to win a race, enumerate the sheets in
`panel.html`'s load order and check them for `!important` — the race you can win is not always the race
being run.* Current `!important` census, for the next reader:
panel.css **3** · caption-float.css **2** · theme-1..5 **2 each** · zipc-panels **0** · zip-overlay **51** ·
panel-designs **10** · cinematic **0** · skin-layout **10** · skin-shim **5**.

## 6. UNMEASURED / owed (stated, not hidden)

I launched nothing, so none of the following was measured — each needs a running shell, which this lane
may not start:

1. `matchMedia('(prefers-reduced-motion: reduce)').matches` inside WebView2 on this box (T11). The OS
   flag was read by an earlier lane; the renderer read has never been made (`:2553-2558` says so).
2. Computed-style confirmation of every T1–T7 deletion proof (border/background/display identities) — the
   *static* proofs are complete, the renderer ones are owed.
3. `#caption-float .caption-float__meter` `height` = `0px`, `.caption-float__led` `width` = `6px`
   (T12) — asserted from the cascade, not observed.
4. Whether the LIVE pill actually reads ~5 px wide because of the zero-width label (T10).
5. Anything about paint, layout or a11y-tree contents. My corpus greps are strong against *static* absence
   (I checked for dynamic class construction explicitly), but a renderer can refute any of them.

## 7. What I touched

**Nothing in the product.** I read `app/panel/panel.css` and its siblings, `panel.html` and the panel
modules; I wrote only this receipt. No app, shell, worker or probe was launched.

**Edit budget if the Lead takes the REMOVEs:** T1 (780 B) + T3 (277 B) + T4 (131 B) + T5 (61 B) + T6
(693 B) + T7 (227 B) + T2 (404 B, includes its comment) ≈ **2.6 KB / ~70 lines**, i.e. **~2.2 %** of
panel.css, with **no computed-style change that any of the static proofs can detect**.
