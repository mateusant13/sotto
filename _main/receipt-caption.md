# receipt — LANE CAPTION: the legend is INDEPENDENT, paints nothing, and the transcript never scrolls to the top

**Date:** 2026-10-13 ~00:0x–00:3x -03:00 · **Lane:** caption (caption-float.js / panel.js / caption-float.css)
**Owner's order, verbatim:** *"a porra da legenda, e pra ser independente do painel, nao acoplado."* ·
*"e eu to vendo div com cor solida inves de invisivel."* · *"e nao e pra mudanca de design/tema/template ficar
scrollando pra cima. e sempre mostrando o bottom do historico de transcript."*

**NO APP, SHELL, WORKER, WEBVIEW2 OR BROWSER WAS LAUNCHED.** Every number below comes from files on disk and
from jsdom (the harness `_main/_s2-bar-dom-oracle.js` already uses). No window appeared; nothing was spawned.

---

## 0. VERDICT (commands and numbers, all re-run on the frozen bytes)

```
node _main/caption-independent-oracle.js             -> 46 check(s), 0 failed   VERDICT: PASS   rc=0
node _main/caption-independent-oracle.js --neg-arm   -> 6 of 6 mutants RED      NEG-ARM VERDICT: PASS   rc=0
node _main/strip-float-oracle.js                     -> 47 check(s), 0 failed   VERDICT: PASS   (its S19 pins a literal getElementById('caption-float'): it went RED on my first rewrite and is green again with the literal restored)
node _main/_s2-bar-dom-oracle.js                     -> 23 check(s), 0 failed   VERDICT: PASS
```

The control arm is the point: **six defects injected one at a time into a COPY of `app/panel`, and every one
goes RED.** One of them (N5) is the owner's coupling restored — the overlay can no longer build itself — i.e.
the shipped behaviour this lane replaced. A mutant that stays green is a missing control, not a pass.

| mutant (a COPY of `app/panel`) | file | went | failing checks |
|---|---|---|---|
| N1 the theme/skin guard is never armed | panel.js | **RED** | C3 C4 C5 C6 C9 |
| N2 the pin writes the TOP instead of the bottom | panel.js | **RED** | C3 C4 C5 |
| N3 the page paints its solid slab behind the caption | caption-float.css | **RED** | B2 B3 B3b |
| N4 the meter plate comes back | caption-float.css | **RED** | B1 B2 B4 B5 |
| N5 the overlay can no longer build itself (the shipped coupling) | caption-float.js | **RED** | A7 A8 A10 A11 A12 |
| N6 the shell cannot see the float state on `<html>` | caption-float.js | **RED** | A11 A14 B3 |

### Files written (pins, 2026-10-13 00:3x -03:00, CRLF preserved, 0 bare LF in all four)

| file | bytes | lines | sha256 |
|---|---|---|---|
| `app/panel/caption-float.js` (rewritten) | 16 614 | 393 | `17AB849D337C4277B7E69E20F248456F3D811E2DCAE34EDD772A96A65A64E3A3` |
| `app/panel/caption-float.css` (**NEW**) | 6 756 | 137 | `E67E0AD00961F85027BBEBF2923A4B404A6BECFA280D7466B503745700890AED` |
| `app/panel/panel.js` (4 targeted edits) | 153 765 | 3 156 | `CBDCB50FEF6A8B953381661D60916476DBE98F5015F843411662019EF9BAA794` |
| `_main/caption-independent-oracle.js` (**NEW**) | 33 321 | 676 | `73FD046D9090190C9EDCBD03928B1247CCB5331545EAC3FBC1CBF93366EE890D` |

`panel.js` was 147 793 B / 3 033 lines / `D18DD4A8…` before this lane (`git status` clean, i.e. the HEAD
revision). `panel.css` and `panel.html` were **NOT touched by this lane** — measured, their pins are unchanged
by me: `panel.css` 110 852 B / `4E368392DBAD39DB1B7E08D10A06133DE683A13392F615CCBAF86C6F3E4DD7C7`,
`panel.html` 63 627 B / `ADE14C7E920F00142E90ED3C839DB34F02E7B98072F81C5A4324976F8E106A4E`.

**`panel.html` ALREADY LINKS `caption-float.css`** — another hand added it at 00:18:41Z, minutes before this
receipt (`panel.html:50-54`, after `panel.css`). Measured with `grep -n 'link rel="stylesheet"'` and with the
oracle's A1 (exactly ONE link in the document). **So the Lead has nothing to wire for this file.** The module
also links it itself when a document does not (A6b/A6c), which is what makes the overlay independent of the
panel's markup.

---

## 1. THE COUPLING, MEASURED, AND WHAT REPLACES IT

Pre-lane `caption-float.js` = 4 965 B / 119 lines / sha `602288DAE3946524241EC0C23C032E3E37093EEFB026871612BA34073BF273D7`.
Every line below is the revision I read before editing (re-measured in this session, not quoted from a doc).

| # | coupling (file:line, pre-lane) | what it made the overlay depend on | what replaces it (now) |
|---|---|---|---|
| 1 | `caption-float.js:36` `document.getElementById('caption-float')` | the panel's markup; without it `nodes()` returns false and **nothing** works | `mount()` (caption-float.js:152) **creates** the host + its five nodes when the document has none; `build()` at :113 |
| 2 | `caption-float.js:38-44` the five id lookups + `.caption-float__led`/`.caption-float__col` | the panel's DOM contract, resolved once and cached | `resolve()` at :138, re-resolved after any re-mount; same ids/classes, so no second contract |
| 3 | `caption-float.js:45` `return !!(line && prev && meter && meterFill && credits)` | a missing node silently disabled `push`/`setMeter`/`setListening` | `nodes()` at :167 mounts on demand; `push` at :216 still no-ops without a document, never throws |
| 4 | `caption-float.js:105` `on: document.body.getAttribute('data-float') === 'on'` | **the panel owned the overlay's state** | the host carries `data-float`; `on` is the module's own (`:58`, `setFloat` at :199); `body[data-float]` is still READ (an older panel.js) and never depended on (`watch()` at :305) |
| 5 | `caption-float.js:112-117` the API (push/setMeter/setListening/state) | no way to show the overlay except through the panel's attribute | `show/hide/toggle/setFloat/isOn/mount/own` added at :365-378; the four old names are unchanged, so panel.js and every probe keep working |
| 6 | `panel.css:2789` `body[data-surface="strip"][data-float="on"] .caption-float { display: block }` | **the strip surface had to be on** — the overlay was invisible on the full panel, on a standalone page, everywhere else | `caption-float.css` `#caption-float[data-float="on"] { display: block }` **plus** an inline `display` the module owns (caption-float.js:194), so it is correct even before the sheet lands |
| 7 | `panel.css:2815` `body[data-surface="strip"][data-float="on"] .caption-float { top: 34px }` | its geometry was the panel bar's height | `caption-float.css` rule 3: with no bar the overlay hugs the BOTTOM (`top:auto; bottom:0; height:auto`); with the bar the panel.css placement is restated for the strip case only |
| 8 | `panel.js:1042` (commit) and `panel.js:865` (forming) are the ONLY pushes | with no panel, nothing could ever feed the caption | `selfFeed()` at caption-float.js:277 subscribes to `window.sotto.onCaption` (the shell's own bridge, sotto_webview.py:2924) **only when no panel is mounted**; with a panel the feed stays `panel` (A16) so one caption can never paint twice |
| 9 | `panel.js:2268` `document.body.setAttribute('data-float', want)` | the panel was the only writer of the float state | panel.js `applyFloat` now also calls the module (`syncCaptionFloat` at panel.js:2254, call sites :2265/:2271); the module is the ONE writer of `documentElement[data-float]` |
| 10 | `panel.js:2276` `bridge.setPanelSurface('strip', …)` | the overlay's visibility depended on the panel's window call | the call still resizes the window (it is the shell's job) but the overlay no longer waits for it: it paints from its own attribute |
| 11 | `sotto_webview.py:6620` and `:6668` — the shell reads `documentElement[data-float]` | **the shell never saw the float**: the panel wrote the attribute on `<body>`, the shell read it on `<html>` | the module mirrors its state onto `documentElement` (caption-float.js:203-206). MEASURED on the HEAD bytes: `body[data-float]="on"` while `documentElement[data-float]=null` -> the shell's own expression `=== 'on'` was **false**; now A14/A11 assert it is `'on'` |

Consequence of #11, named for the Lead because it is the shell's half: while the caption is floated the shell
sized the strip window by the strip's rules — `strip_width_from_dom` returns `None` only when
`documentElement[data-float] === 'on'` (sotto_webview.py:6668), so with the old write it measured the ~pill's
width and the caption got that window; and `strip_height_from_css` (sotto_webview.py:6620) chose
`--strip-height` instead of `--float-height`. Both reads now answer correctly. **This is a code-level fix, not
an observed one: no WebView2 was launched, so the window's real size was NOT measured.**

---

## 2. "SEM FUNDO NENHUM" — the solid div was FOUND, and it was a rule

**The defect, measured:** `panel.css:105-134`, rule `html, body { background: rgba(11, 15, 20, 0.98) }`
(the file calls it THE RENDER PROTECTION) paints a 98%-opaque slab over the WHOLE window on every surface.
The overlay's own pixels are transparent, so what the owner saw behind a loose caption was that slab — the
"div com cor solida". Second painter, also measured: `panel.css:2911` gave `.caption-float__meter` a
translucent white plate (`rgba(255, 255, 255, 0.16)`) and `:2926` gave its fill `var(--accent-gradient)` —
two DESCENDANTS of the overlay painting colour, which the owner's "apenas uma barra a esquerda" forbids.

**Before/after, same probe, HEAD bytes vs shipped bytes:**

```
BEFORE (HEAD app/panel, 4 files)                     AFTER (shipped)
body[data-float]            = "on"                   body[data-float]            = "on"
documentElement[data-float] = null                   documentElement[data-float] = "on"      (oracle A14)
shell expression === 'on'   = false                  shell expression === 'on'   = true
body computed background    = rgba(11, 15, 20, 0.98) body/html computed background = rgba(0, 0, 0, 0)  (oracle B3)
```

**The fix is `caption-float.css`** (panel.css may not be edited by this lane): `html[data-float="on"], body[data-float="on"] { background: transparent }`,
the overlay and every descendant except the left bar forced to `background: none / background-color: transparent / background-image: none / box-shadow: none / border: 0 / outline: 0 / backdrop-filter: none`,
and the meter plate switched off (`height: 0; margin: 0`). The ONE body is `.caption-float__led` (the zip's
4px breathing bar), restated with a fallback gradient so a theme without `--accent-gradient` cannot leave the
overlay bodiless.

**How it is gated (three instruments, one claim):**
* `B1` — jsdom walks every element of the overlay subtree and reads the COMPUTED background: **0 painters**
  (real cascade, resolved colours; this is what catches a literal plate like `rgba(255,255,255,0.16)`).
* `B2/B2c` — a CSS declaration scan over **the sheets the document actually loads** (panel.html's links + the
  lazy manifest in `lazy-assets.js` + caption-float.css): every rule that paints on the overlay or a descendant
  must be neutralised by a caption-float.css rule on the same element with a non-painting value and >=
  specificity. It reports the **4 neutralised rules** it found (html, body, meter, meter-fill) and **0 offenders**.
  This is the instrument that covers `var()`-valued paint, which jsdom does not resolve.
* `B3b` — nothing in that sheet population may paint `<html>`/`<body>` with a specificity that beats the
  transparency rule (future themes included).
* `B4/B5` — the meter and its fill compute transparent and the meter is 0px tall.

**Not covered:** jsdom has no paint engine. These are computed-style and cascade facts, not pixels. Nothing
here was verified on a real WebView2.

---

## 3. THE SCROLL — the mechanisms, and the one rule

**What moves the transcript when a theme changes (measured in the bytes, anchors re-grepped this session):**
1. A theme write is `data-theme` on `<html>`, and the document carries THREE observers on it —
   `theme-tune.js:986`, `lazy-assets.js:266`, `skin-host.js:555`. The last two **inject stylesheets into the
   live document**; a sheet that lands after the write reflows the list — the scroll POSITION is kept, the
   CONTENT height is not, so the newest line leaves the view.
2. A template/skin switch **hides the container**: `skin-layout.css:66-68`
   `body[data-skin][data-surface="panel"] .history { display: none !important }`, and `data-skin` is written on
   `<body>` (`skin-host.js:304`). A scroll container that is not rendered has no position to come back to.
   The strip surface hides `.history` the same way (`panel.css:1456`).
3. The panel's OWN re-render did it: `renderFeed` ended with `dom.historyList.scrollTop = 0` (was panel.js:1642)
   — a re-render of a bucket jumped the feed to its first line.

**The fix, in `panel.js`, one rule and one place:**
* `pinHistoryToBottom()` (panel.js:1108) — `scrollTop = scrollHeight`, always. `pinLiveTranscriptToBottom()`
  (:1122) — the live box too, but only while `stickToNewest` (the owner's own scroll keeps its older right to
  stop the follow). `pinTranscriptsToBottom()` (:1130) is both.
* `repinTranscriptsAfterLayoutChange()` (:1141) — pins NOW, on the next frame, and twice on a short timer
  (a stylesheet that lands late reflows again).
* `wireThemeScrollGuard()` (:1151) — observes `data-theme` on `<html>` and `data-skin`, `data-skin-theme`,
  `data-surface`, `data-float` on `<body>`, plus every stylesheet `load` (capture phase: `load` does not
  bubble). Armed from the init block at **panel.js:610**, bridge or not.
* `renderFeed` now calls `pinHistoryToBottom()` (panel.js:1748) instead of writing 0.

**Gated by:** C3 (theme write), C4 (skin write), C5 (stylesheet load), C6 (the live box), C7/C8 (the real
`renderFeed` source, extracted by brace matching: it contains the pin and no `scrollTop = 0`), C9/C10 (the
guard is armed and observes the right attributes). Mutants N1/N2 are the controls and both go RED.

**Deliberately NOT changed:** `renderSearchResults` still writes `historyList.scrollTop = 0` (panel.js:2623).
Search results are newest-first, so their first line IS the newest — and if the owner changes the theme while
search results are open, the guard still pins the list to the bottom, which is his rule.

---

## 4. WHAT I COULD NOT CLOSE (and why)

1. **NOTHING WAS LAUNCHED.** No WebView2, no shell, no window, no pixels. Everything is jsdom + bytes. The
   owner's three complaints are answered at the level of code, cascade and state — not at the level of what the
   compositor paints.
2. **The window's own opacity while floated is NOT solved by CSS alone, and it is the shell's.** With the page
   now transparent, what shows behind the caption is the shell's form: `sotto_webview.py:3977`
   `form.BackColor = #0B0F14` (the shell's deliberate failure-mode colour) and the transparency path
   (`SottoShell._transparency`, :3644 → `set_transparency`, :5623) which is driven by the panel's
   `setTransparency` message — and the panel's transparency button was REMOVED as the earlier bug. **Exact rule
   the Lead must decide:** while `documentElement[data-float] === 'on'` (now true for the first time), the shell
   should either keep the window transparent so the desktop shows through, or accept the #0B0F14 slab as the
   caption's backdrop. File: `app/webview/sotto_webview.py` (out of this lane's scope — not touched).
3. **The scroll reset itself was not observed in a browser.** I proved the rule, the guard, and the three code
   paths that move or hide the container; the browser's own "a display:none container loses its scroll position"
   behaviour is named as the mechanism, not measured here.
4. **`documentElement[data-float]` has ONE writer (the module) and the page's transparency CSS keys on it** —
   mutant N6 shows that if the mirror is removed the page paints the slab again (B3 goes RED with it). That is a
   deliberate dependency, stated so the next reader does not remove the mirror as "redundant".
5. **`three-overlays-oracle.js` (D1, D6) and `theme-preview-oracle.js` (ARM14.1) are RED and it is NOT this
   lane.** Measured: the working-tree `panel.html` no longer ships `strip-theme-button`,
   `strip-font-smaller-button`, `strip-font-larger-button` inside `.stripbar` (HEAD's `.stripbar` had 13 ids,
   the working tree has 10) and no longer has `data-theme-button`; those two oracles assert exactly those
   anchors. Another lane removed them at 00:18:41Z while this lane ran. My files are not read by those checks.
6. **`history-route-oracle.js` is RED on live data**, not on code: it reads the owner's own
   `history-verify/2026-10-12/21.md` and finds 2 of 3 entries failing its "closed line, marked, >3 words"
   rule. Not this lane's file.

## 5. REPRODUCE

```
cd H:/sotto
node _main/caption-independent-oracle.js              # 46 checks, VERDICT: PASS, rc 0
node _main/caption-independent-oracle.js --neg-arm    # 6/6 mutants RED, NEG-ARM VERDICT: PASS, rc 0
node _main/strip-float-oracle.js                      # 47/47 PASS
node _main/_s2-bar-dom-oracle.js                      # 23/23 PASS
```
(`TMPDIR` is `I:/cc-tmp`; the oracle uses it for the mutant scratch copies and removes them.)

**What I ask the Lead to run, if a launch is wanted** (this lane may not): the only unmeasured half is what the
real WebView2 paints and how big the window is while floated. A single launch with the float on, plus
`grep STRIP_RECT_ _main/webview-run.log`, would answer both: with `documentElement[data-float]="on"` the shell
should log `STRIP_WIDTH … source=content` only when NOT floated, and dock `--float-height` (220) while floated.
