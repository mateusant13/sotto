# Receipt — the five themes became TEMPLATES, editable from the panel

Owner's request, verbatim (2026-10-08), and it is the whole scope of this lane:

> *"beleza. entao mantemos assim. tenha certeza que o modelo de agora, pro ao vivo, é o
> nemotron. e quero que os temas sejam templates. e quero modificar coisas de cada
> templete de um jeito facil, pelo painel. tipo trocar a fonte, entre outras coisas q tu
> achar bom tambem"*

Three claims, three receipts, below. The third one grew a fourth: a live bug the
census exposed while confirming the first, and it was the owner's own report.

---

## 1. Ao vivo é o Nemotron — CONFIRMED

`worker/config.json` selects `models/nemotron-3.5-asr-streaming-0.6b-int8`, and the
worker's own command line carries **no** `--model` flag, so the config file is what
it loads (`_main/_tune-census.ps1`). The Parakeet Redux runners name their own
defaults and are not on this path (`worker/redux_batch.py`,
`worker/qwen_summary.py`). `output.partial: true`, `use_denoise: false`,
`lang_id: auto`.

## 2. The themes are templates — WHAT SHIPPED

**New:** `app/panel/theme-tune.js` — the whole layer, DOM-free core + DOM layer.
**Edited:** `app/panel/panel.html` (one `<script>`), `app/panel/panel.css` (the
dialog's styling). **NOT touched:** `themes/theme-{1..5}.css` and
`themes/fonts.css` — both are owned by generators (`_main/_design-lane/gen_themes.py`,
`build_fonts.py`) and stay regenerable. mtimes confirm it: the theme files are
`07/10 23:45`, from an earlier lane.

### The mechanism

An edit is `document.documentElement.style.setProperty('--size-caption', '34px')`,
undone with `removeProperty`. Two reasons this is inline and not a generated
`<style>` element:

* **precedence** — the theme files scope everything to
  `:root[data-theme='theme-N']`, and an inline custom property on `<html>` outranks
  every author rule regardless of specificity, so this layer never argues with a theme;
* **CSP** — `style-src 'self'` governs markup and stylesheet loads, while
  `setProperty` is a CSSOM mutation. The mechanism does not depend on how that CSP
  treats a script-created `<style>`.

**The baseline is READ, never copied.** "Restore this theme" removes the inline
property and reads what the theme's own stylesheet resolves to — so no second copy
of `30px` or `#F2E9D8` exists in this repo, and a regenerated theme moves every
untouched knob automatically.

**A theme switch is followed through a `MutationObserver` on `<html data-theme>`**,
so `theme-tune.js` and `theme-switcher.js` never call each other.

### The knobs (17), and why those

Font family · live caption size · live leading · live weight · live letter-spacing ·
uppercase · closed-line size · closed-line leading · closed-line weight · accent ·
confirmed-text colour · provisional-text colour · panel background (2) · radius ·
transition duration · typing speed (`--type-step`, 0 = off).

**FOUR TOKENS THE THEMES DECLARE ARE DELIBERATELY NOT OFFERED**, because a control
nothing reads is a control that lies — the defect class this repo already paid for
(`docs/audit/config-inert-fixed.md`):

| token | why it is refused |
|---|---|
| `--slab-opacity` | declared 0.96–0.99 by all five themes, read by nothing — the slab bakes the percentage into `color-mix(... 97% ...)` at generation time |
| `--text-confirmed` | declared by all five, consumed by no rule (a confirmed line paints with `--text-secondary`, `theme-1.css:226-231`) |
| `--font-caption`, `--font-closed` | declared as `var(--font-sans)`, consumed by no rule; `--font-sans` is the knob that actually moves both tiers |

`_main/theme-tune-oracle.js` ARM 7 gates this against the shipped CSS **from disk**:
every offered token must appear as `var(--token)` somewhere, and the four above must
NOT be offered while still being declared.

### An accent edit moves THREE tokens, not one

`--accent` alone is not enough: `--theme-swatch` (the picker's own dot) and
`--accent-soft`/`--line`/`--line-strong` are **literal colours** in the theme files.
Changing the accent without them would leave the button advertising the previous
accent — the exact drift `themes/themes.js:27-33` says must never happen. The
alpha of each is **read from the theme** (`alphaOfComputed`), so the designer's own
opacity survives an accent change.

### How the owner uses it

A gear (`#tune-button`) in the header's control cluster, **inserted before the pause
button** so HIDE STAYS LAST/RIGHTMOST (the owner's 2026-10-08 ruling, which
`panel.html:265-288` makes load-bearing). It opens a dialog that reuses
`.pause-dialog`/`.dialog-button` for its shell — two modals in one 380 px window that
look different is a defect — with one row per knob, each row showing `do tema` when it
is untouched and a per-row ↺ plus a "Restaurar este tema" button. Edits are per theme
and persist through the same defensive `localStorage` pattern the switcher uses
(memory fallback when `file://` refuses storage).

## 3. The live bug the census found, and the cure

Confirming the model meant reading the running app, and `panel-state.json` said:

```
"noAudio": true, "noAudioEvidence": "device-rotated reason=flat peak=0.0 floor=0.002"
"captions": 21295, "state": "capture-started", "namedState": "no-audio"
```

21 295 captions with the shell's own name for the panel state being `no-audio`. That
is the owner's report, verbatim: *"nao ta ao vivo. algo ta bugado."*

**Cause.** `no_audio` was set by `_no_audio_evidence` (`:6871`) and cleared **only in
`_spawn`** (`:6666`). A caption lifted `pending_error` but not this flag, so ONE flat
window latched it for the life of the child. Two consequences:

* **the watchdog went blind** — `_on_silence` returns early whenever `no_audio` is
  true, so after one flat window every later quiet was BENIGN forever, and a worker
  that wedged afterwards could never be caught (the opposite of what that branch was
  written for);
* **the panel was told "No audio to transcribe" over a working transcript.**

**Cure.** In the `type == 'caption'` branch of `_consume`, a caption now lifts the
verdict with the same force it already lifted a death, and says so:
`BRIDGE_NO_AUDIO_LIFTED reason=caption captions=N because=<old evidence>`. The
evidence itself is why it must not latch: `device-rotated reason=flat` is the
worker's row for *"THIS CANDIDATE carried nothing I could transcribe, moving on"*
(`_no_audio_evidence`'s own docstring) and the ladder moves AWAY from that candidate —
the sentence is about an endpoint the tap is no longer on.

### The gates

* `py -3 _main/no-audio-latch-oracle.py` → **VERDICT: PASS**, 4 arms, with a CONTROL
  built from today's shell with only the lift deleted: the control goes RED on
  `ARM 2` (the latch survives, the evidence survives, no lift logged, the panel still
  named `no-audio`, and the watchdog still benign), while ARM 1 and the benign half of
  ARM 4 stay green — so the arm is not vacuous and the revert touched only the cure.
* `node _main/theme-tune-oracle.js` → **VERDICT: PASS, 64 arms**, and
  `--neg-arm` → **66 arms**, with the liveness gate REJECTING the declared-but-unread
  `--slab-opacity` and ACCEPTING a consumed token (so the gate is neither vacuous nor
  always-false).

### Live proof, on the owner's box

The shell was restarted through the documented path (`app/webview/run.cmd`, hidden —
`PANEL_VISIBILITY_AT_STARTUP visible=false`, no window on his screen), and the running
shell publishes `BRIDGE_NO_AUDIO_LIFTED`, **a string the pre-fix shell cannot print**.
The state sequence from `_main/panel-state.json` on the new shell:

```
device-rotated   noAudio=True                  <- the verdict raised (detection still works)
silent-device    noAudio=True
boot             noAudio=False                 <- a new child declares nothing yet
capture-started  noAudio=True                  <- raised again by a flat rotation
capture-started  noAudio=False  captions=8     <- LIFTED BY A CAPTION
namedState       capture-started               <- was 'no-audio'
```

## 4. The template layer, measured in a real renderer

`node` cannot answer "does the edit change what is painted", so
`_main/theme-tune-render-test/` loads the **real** `panel.css`, the **real** five
themes and the **real** `theme-tune.js` into a real Chromium (the Electron binary
that was already in `app/node_modules`) in a hidden window:

```
H:/sotto/app/node_modules/electron/dist/electron.exe _main/theme-tune-render-test/main.js
```

Receipt `_main/theme-tune-render-test/receipt.txt` → `"ok": true`, `"failed": []`,
`"errors": []`. Every check is **relational** (no design number is hard-coded, so a
regenerated theme cannot make the instrument lie): the edit adds `--size-caption: 41px`
on `<html>` AND the caption element's own computed `font-size` becomes `41px`
(**cascade**); `theme-2` then reports its OWN value with nothing inline on `<html>`
(**isolation**); coming back restores `41px` (**memory**); "restore" returns exactly
the value read before the edit (**baseline is read**); an accent edit moves
`--accent`, `--theme-swatch` and `--accent-soft` together keeping the theme's alpha;
`--type-step: 0ms` reaches the sheet; the gear is inside `.panel__controls` before the
pause button with hide still last, and the dialog is outside `.panel`; no page error.

## 5. What is NOT proven — stated plainly

* The **WebView2** shell has not been photographed showing the gear. What is proven
  there: the panel assets hot reload, and `PAGE_ERROR` is **0** in the new session, so
  the module loaded and booted in that renderer without throwing. The gate on the
  mechanism itself is the Chromium test above.
* The two new oracles are **not yet steps in `_main\_audit-verify-all.cmd`**. That
  file is CRLF-by-byte-offset fragile and is edited by other lanes; adding steps
  changes its documented `steps : 29` receipt, so it was left alone on purpose. The
  two commands to aggregate them:
  `node _main/theme-tune-oracle.js --neg-arm` and
  `py -3 _main/no-audio-latch-oracle.py`.
* The typing-speed knob moves the reveal's documented switch, and the reveal's cost
  was already instrumented (`_main/_panel-anim-cost.js`); no NEW animation cost
  measurement was taken for it, because the knob only changes an existing delay.
