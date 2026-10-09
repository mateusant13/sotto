# Receipt — the `cinematic` template set, and the two-click contract

Date: 2026-10-08. Lane: the owner's request, verbatim:

> *"gostei de alguns designs que botei ai no workspace. sao .zip novos. eu gostei de
> todas as fontes, entao inclua toda as fontes. ja os designs, inclua aqueles que nao
> sao 'agressivos demais'. e eu nao quero só a paleta de cores. eu quero uma mudança
> mesmo, a cada tema/template. super parecida com o que ta no zip, ou igual"*

> *"e outra coisa: quero SUPER parecido, a parte da legenda ao vivo que fica no meio da
> tela, dos que estao no zip. tambem permita testing, troca de template/tema, etc. e
> pros que sao bem parecidos, faça outra alternativa, a b c testing. e clique esquerdo
> avança, direito retrocede nos temas"*

## 1. What shipped, in one line each

| piece | where | what it does |
|---|---|---|
| the font bundle | `app/panel/themes/fonts.css` + `app/panel/fonts/*.woff2` | **all sixteen** families the three zips name, 66 faces, 1227.4 KB, latin only |
| the theme generator | `_main/_design-lane/gen_cinematic.py` | reads the design source, emits the CSS + the manifest + the backdrops, self-checks, refuses to write a broken set |
| the theme set | `app/panel/themes/cinematic.css` | **22 themes** — every non-aggressive design of all THREE zips (7 + 9 + 6), scope `:root[data-theme='cine-…']`, 253 256 B, generated |
| the backdrops | `app/panel/themes/backdrops/*.jpg` | the 22 wallpapers the zips themselves name, downloaded and bundled, plus `LICENCES.md` |
| the manifest | `app/panel/themes/themes.js` | regenerated: the 5 original directions **verbatim** + the 22, in 10 A/B/C groups |
| the manifest | `app/panel/themes/themes.js` | regenerated: the 5 original directions **verbatim** + the set, with `group`/`variant`/`groupLabel` |
| the two clicks | `app/panel/theme-switcher.js` | left = next, right = previous, both wrap; the picker moved to the keyboard |
| the picker | `app/panel/panel.css` + `theme-switcher.js` | one shared token-driven base, group headings, A/B/C badges, scroll cap |
| the font selector | `app/panel/theme-tune.js` | offers all 16 bundled faces + the 2 system stacks, matched by primary family |

## 2. The mechanism, and the ONE thing to understand about it

A theme is not a palette here. Every theme block declares **all 59 tokens** of the
contract in `themes/theme-1.css:43-125` *and* its own structural rules, so a theme that
forgot a token fails the build instead of silently inheriting another design's colour.

**The caption is the centrepiece, and it is the same idea in every theme of the set:**
no box, no pane, no border — type over the design's own photograph, behind the design's
own scrim, with one word (or one character) arriving at a time. That is what the zip
does and it is what the owner asked to be *"super parecido"*.

**The caret is load-bearing.** In five of the six caption treatments of the zips the
forming text is styled IDENTICALLY to the settled text, so the blinking caret is the
only thing on screen that says a word is not final. It is also the only honest marker
our panel can produce, because the worker sends the words it has and not the ones it
hasn't. The shared block is scoped `[data-theme^='cine-']`, never to the document: the
five original directions inherit nothing from it.

The four reveals are the zip's own: `fade` and `rise` animate the WORD (and switch the
per-character reveal OFF, because two animations on one character's opacity multiply);
`blur` animates the CHARACTER through the existing `--c-i * --type-step` machinery; and
`type` needs no rule at all — it *is* the character reveal `panel.css` already declares.

## 3. What is PROVEN, by instrument

**`node _main/theme-tune-oracle.js --neg-arm` → ARMS: 66, PASS: 66, FAIL: 0, VERDICT PASS.**
Includes the liveness gate: every token the editor offers must appear as `var(--token)` in
the real stylesheets, and the four tokens that are declared-but-read-by-nothing must NOT
be offered. `--neg-arm` proves the gate rejects `--slab-opacity` and accepts `--size-caption`.

**The render instrument, over ALL 12 themes in a real Chromium** (`_main/theme-tune-render-test/`,
`electron exit=0`, `VERDICT: PASS`):

| check | result |
|---|---|
| `every_theme_declares_every_token` | true — `missingByTheme: {}` for all 12 |
| `swatch_matches_accent` | true — `swatchMismatch: []` |
| `caption_size_is_sane` | true — `sizeBad: []` |
| `themes_are_not_all_the_same` | true — **12 distinct `--bg-slab` values for 12 themes** |
| `left_click_advances` | true — through the real listener, `theme-1` → `theme-2` |
| `right_click_goes_back` | true — `theme-2` → `theme-1` |
| `right_click_wraps_to_the_last` | true |
| `picker_lists_every_theme` | true — 12 options |
| `picker_shows_every_variant_badge` | true — 2 badges for 2 variants (`> 0` is part of the check) |
| `picker_shows_every_group_heading` | true — 1 heading for 1 group |
| `picker_is_scroll_capped` | true — `max-height: 517.7px`, `overflow-y: auto` |
| the 26 tuner arms (cascade, isolation, memory, colour, off-switch) | all true |

`themes_are_not_all_the_same` is the one that catches a bundle that failed to load: with
no stylesheet every theme falls back to `panel.css`'s `:root` and all twelve report ONE
value. It cannot pass by accident.

**The STRUCTURE, in a real Chromium, over all 16 themes** — `_main/theme-caption-render-test/`, a second
instrument whose page carries the caption markup copied from the panel's own builder
(`panel.js:595-645`), because the first instrument's page has a two-element stand-in and
a theme whose structural rules matched NOTHING would have passed it. `electron exit=0`,
`VERDICT: PASS`:

| check | result |
|---|---|
| `every_theme_sizes_the_caption_from_its_token` | true — the computed `font-size` IS `--size-caption`, string for string |
| `every_theme_applies_a_backdrop` | true — a real image layer on `.panel` |
| `a_marker_says_the_text_is_still_forming` | true — a caret, OR the accent on the newest word, OR a reveal animation; never none |
| `every_theme_holds_the_type_off_the_photo` | true — a text shadow on every theme |
| `older_lines_recede` | true — older lines strictly smaller, checked as a RELATION |
| `control_no_caret_on_the_original` | true — `theme-1` has no caret: the shared block is scoped to the set |
| `control_the_original_keeps_its_own_face` | true — `theme-1` still paints Barlow Condensed |

**THREE OF THOSE CHECKS WERE WRONG FIRST, AND THE CORRECTION IS THE POINT.** They began
as set-wide demands that no theme paint a caption box, that every theme show the caret, and
that every theme accent its newest word. All three are true of the FIRST zip and false of
the SECOND, whose panels are card layouts and whose `wide` variant has no caret by design.
The instrument was encoding one zip's convention as a rule for the other — and the failure
list it printed was the evidence (five themes "painting a box", four with `caret: none`,
nine without the accent). The corrected checks keep only what is universal: a backdrop, the
caption sized from its own token, older lines receding, the type held off the photograph,
and **at least one** forming marker. See §5.

And the reveal engine, read off the paint for the seven themes of the first zip (4 move the
WORD, 2 move the CHARACTER, 1 uses the panel's own character reveal):

| theme | reveal | newest word in the accent | character animation |
|---|---|---|---|
| `cine-midnight-rain` | fade | yes | none (off by design) |
| `cine-warm-hour` | fade, italic | yes | none |
| `cine-velvet-dusk` | rise | yes | none |
| `cine-quiet-streets` | fade, 0.09em | yes | none |
| `cine-tideline-body` | blur | yes | `cine-blur` |
| `cine-north-fog` | blur | yes | `cine-blur` |
| `cine-study-light` | type | **no — by design** | `sotto-type-in` |

**The real shell (WebView2, not a stand-in):** `py -3 app/webview/sotto_webview.py
--dump-dom --no-hotkey --no-hot-reload --log _main/_dom-cinematic.log` →
`sheets: 8` (panel.css + fonts.css + the five directions + `cinematic.css`),
`BRIDGE_GATE=GREEN`, `url=file:///H:/sotto/app/panel/panel.html`, `SHELL_EXIT rc=0`, and
**zero `PAGE_ERROR`**. The computed colours it reports (`#A9B7C6` for `.status`, `#F2E9D8`
for `.wordmark__name`) are theme-1's own tokens, so the contract resolves in the real engine.

**And a theme OF THE SET, painted by that same real engine.** There is no CLI flag for the
theme, so the measurement was taken by pointing the manifest's `fallback` at
`cine-velvet-dusk` for one `--dump-dom` run and restoring it immediately afterwards; the
manifest's sha256 was identical before and after, and `node --check` was green on both
sides. Measured: `.status` = `rgb(132, 100, 121)` = `#846479` = **velvet-dusk's own
`--text-muted`**, `.wordmark__name` = `rgb(209, 140, 178)` = `#d18cb2` = **velvet-dusk's own
accent** (the wordmark paints with the accent, which is why theme-1 reported its
`--text-primary` — in that theme the two are the same value), `sheets: 8`, `#panel rect
[0,0,380,900]`. So the tokens of the set reach the real engine's paint, not only the
instrument's.

**The app the owner will find is running the new panel.** The shell that was up had
started at 03:41, before the bundle existed, and had logged no hot reload — so its panel
did not contain the new `<link>`. It was stopped **by artefact name** (`sotto_webview\.py`,
`sotto_worker\.py`), the table was waited on until empty, and the documented entry
(`cmd.exe /c app\webview\run.cmd`, hidden) was started: now shell **33140** + worker
**32444**, `SINGLE_INSTANCE already_running=false`, `HOTKEY_REGISTERED accelerator=Alt+C`,
`WORKER_AUTOSTART=started reason=default`, `PANEL_VISIBILITY_ON_SCREEN visible=false`
(off screen, as the house rule requires), `SHOW_REFUSED count=2` (the map gate working),
`PAGE_ERROR count: 0`. The no-audio latch cure from the previous lane is also alive in
this run: `BRIDGE_NO_AUDIO_LIFTED reason=caption captions=23`.

## 4. The decisions that are MINE, not the zip's

1. **`--size-caption` takes the MAX of the source's `clamp(floor, vw, max)`.** The `vw`
   term is a stage unit: at our 380 px column the zip's own CSS would resolve to its
   FLOOR (20 px) and the caption would look nothing like the design at full size.
2. **Lines older than the newest get `0.72` of the caption size and `--text-secondary`.**
   The zips only ever show ONE live line, so they state no treatment for the ones our
   panel keeps; 0.72 is the smallest value that recedes without becoming unreadable.
3. **The state colours are the product's, not the design's.** The zip declares no
   `--ok`/`--error`; those carry meaning in this app (the tap is delivering / it is not),
   so they are the same two literals the five directions already use, and `--busy`/`--idle`
   follow the palette.
4. **`--line-strong` is the zip's ONE line colour at alpha 0.34.** The panel has two
   weights of a line; a second colour would be a colour the design never states.
5. **The caption's colours go on the tokens the panel AND the editor read**
   (`--text-confirmed`, `--text-provisional`, and `--accent` for the newest word, which is
   the zip's `--caption-accent` role). This is deliberate: it keeps every colour of the
   set editable from the panel's own template editor.
6. **`--panel` → `--bg-slab`.** The zip's panel colour is the slab.
7. **The backdrop is bundled, not linked.** The zips name Pexels photographs. They are
   downloaded and shipped locally because the panel's CSP is `img-src 'self' data:` — a
   remote URL would be a silently missing backdrop forever.

## 5. Defects found and fixed on the way (each is a lesson, not a footnote)

| defect | symptom | fix |
|---|---|---|
| the generator wrote LF into a CRLF family | `themes.js` was 88 B larger in HEAD than in the tree: 88 lines × 1 byte | write `newline='\r\n'`, matching the measured 88/0 and 646/0 of its siblings |
| `with open(path,'w')` truncates before the text is built | the manifest raised mid-build and left a **0-byte** `themes.js` | build both documents first, open the files second; restored from git |
| the manifest spliced entries with no comma | `node --check` RED (`} {`); in the panel this is SILENT — `SottoThemeManifest` stays undefined and the whole set is invisible | join entries with `,`; **and the generator now runs `node --check` on its own output** |
| the self-check read only the first token block | 11 "missing token" failures per theme — the aliases live in a second block | read every block of that theme (fail-closed: no file was written) |
| a group's members were not adjacent | the picker drew the group heading TWICE | group members are emitted consecutively — which is also what makes the two mouse buttons flip between the alternatives |
| Python's TLS cannot verify Pexels | all ten wallpapers `CERTIFICATE_VERIFY_FAILED: certificate has expired` | download with `curl.exe` (Windows certificate store): exit 0, valid JPEG magic |
| two backticks inside a driver template literal | `SyntaxError: Unexpected number` / `Unexpected identifier`; electron then HUNG on the broken file | no backticks in those comments; `node --check` runs BEFORE electron now |
| a stale electron held the Chromium profile | the render instrument produced 0 bytes and never exited | census and kill by the **artefact path**; the same rule the repo already has for `sotto_*.py` |
| the manifest writer was **not idempotent, twice** | run N+1 inserted the header paragraph again (the anchor it looked for survives the insertion), then, after that was fixed, still grew 4 bytes per run from an orphaned ` *` line — a header bloated to 9 499 B inside a COMMENT, so `node --check` stayed green and only the byte count exposed it | strip by a marker that includes the paragraph's opening line, reinsert it, and verify **both** artifacts with three consecutive runs: both byte-identical |
| a driver inside a template literal | two backticks in a comment closed it | the second instrument keeps its driver in `driver.js`, read with `fs.readFileSync`, so `node --check driver.js` checks exactly what runs |
| **controls and checks that could not say no** | `control_the_set_did_not_repainted_the_originals` compared the WRONG element (theme-1's `.captions__list` is transparent too); the type shadow turned out to exist on the originals as well; and THREE set-wide structural checks (no caption box, the caret, the accent on the newest word) encoded the FIRST zip's conventions as rules for the second, so 9 correct themes were reported as failures | the two dead controls were replaced by ones that discriminate (the caret's absence on `theme-1`, and its still painting its OWN face); the three over-strong checks were reduced to the one universal claim — a theme must show AT LEAST ONE forming marker — with the box kept only as an observation |

## 6. What is NOT proven, and what is not done

- **All 22 are shipped.** Every design the plan selected from all three zips is in the
  panel: the 5 original directions plus 22 of the set, **27 themes** in the manifest, in
  **10 A/B/C groups**. The generator is idempotent over both artifacts (verified across
  consecutive runs, byte-identical each time), and both render instruments pass over the
  full set: the structure instrument across all 22 (`badMarker`, `badSize`, `badPhoto`,
  `badShadow`, `oldNotSmaller` all empty), the token instrument across all 27
  (`missingByTheme {}`, `swatchMismatch []`, `sizeBad []`, **27 distinct backgrounds for
  27 themes**, 16/16 variant badges, 10/10 group headings).
- **The two sets size their captions differently, on purpose and inconsistently.** The
  `cinematic` themes take the MAX of the source's `clamp(...)` (24–33 px, the size the
  design was drawn for); the `cinematic-1` themes take its FLOOR (17 px, which is what the
  design's own `1.72vw` term resolves to in a 380 px column — the choice the plan
  recommended). Both are defensible and they do not match each other. The knob is the
  panel's own template editor, per theme ("tamanho da legenda"), so changing it is two
  clicks and no code.
- **The nine excluded designs are excluded, not hidden**: `motel-glow` (glow),
  `paper-moon` (all-caps + light panel), `last-reel` (a one-step grade), and the ones
  §4 of the plan lists from the other zips. The owner's filter was *"nao agressivos
  demais"* and each exclusion names a concrete feature, not a taste.
- **`karaoke` is not implemented.** Both of its designs are in the LOUD bucket, so its
  spec in the plan is documentation. It also needs text our DOM does not have (the words
  not yet spoken).
- **The photographs are Pexels stock, bundled.** Licence: free to use, attribution
  appreciated, recorded in `app/panel/themes/backdrops/LICENCES.md`. They are the exact
  images the zip names, and they are the reason the set reads as the zip does.
- **No human has looked at any of it.** Every claim above is a machine check or a
  computed value. Whether the set is BEAUTIFUL at 380×900 is the owner's call, and it is
  the one question no instrument here can answer.
- Not touched, deliberately: `themes/theme-1..5.css` (owned by `gen_themes.py`),
  `_main/_audit-verify-all.cmd` (CRLF, other lanes edit it), and the two new oracles are
  documented here instead of being added to that battery.

## 7. How to re-run everything

```powershell
py -3 _main/_design-lane/build_fonts.py            # fonts: 66 faces, refuses on a missing file
py -3 _main/_design-lane/gen_cinematic.py          # themes + manifest + backdrops, self-checks
node _main/theme-tune-oracle.js --neg-arm          # 66 arms
py -3 _main/no-audio-latch-oracle.py               # the latch cure, control RED as expected
node --check app/panel/themes/themes.js            # the manifest parses
H:/sotto/app/node_modules/electron/dist/electron.exe _main/theme-tune-render-test/main.js --no-sandbox
py -3 app/webview/sotto_webview.py --dump-dom --no-hotkey --log _main/_dom-cinematic.log
```
