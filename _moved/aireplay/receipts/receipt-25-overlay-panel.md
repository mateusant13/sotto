# RECEIPT 25 — THE OVERLAY PANEL (`src/ui/`) AND ITS WINDOW-MAPPING CURE

**Lane 18** · written 2026-10-07 · project `H:\sotto\_moved\aireplay` (git `029d995`)
**Owns:** `src/ui/**`, `_main/_lane18-ui-gate.ps1`, this file. Nothing else.

Every claim below carries **POPULATION** and **WINDOW**. Anything not measured is
written `NOT MEASURED`, in those words.

---

## 0. THE ONE-PARAGRAPH VERSION

`src/ui/` was empty (measured: `Get-ChildItem … | Measure-Object` → **0** items,
2026-10-07 12:5x). It now holds a HUD plate — HTML, CSS, a DOM binder, a
DOM-free contract, and a WebView2 host — built to `specs/05-overlay-hud.md` and
`docs/overlay-hotkey-contract.md`. The gate is
`pwsh -File _main\_lane18-ui-gate.ps1`, **36 boxes, 0 red**, and it ships
**four** census arms so the central claim (the panel does not map its window
unless asked) has a control that moves.

**The two findings a reader must not skip are §3 (two contradictions inside the
normative documents) and §5 (an arm that measured GREEN when the brief said it
would go RED).** Neither was worked around silently.

---

## 1. WHAT WAS BUILT

| file | what | bytes |
|---|---|---|
| `src/ui/hud-contract.js` | states, bindings, parameters, `renderPlate`. DOM-free, `require()`-able. | 21 k |
| `src/ui/hud-panel.html` | the plate document. `data-mapped="0"` in the MARKUP. | 3.5 k |
| `src/ui/hud-panel.css` | SPEC §1.3's alpha budget, in the Sotto panel's token names. | 7.6 k |
| `src/ui/hud-panel.js` | the only writer of the DOM; `probe()` for the gate. | 7.7 k |
| `src/ui/hud-shell.py` | the WebView2 host **and the cure**. | 24 k |
| `_main/_hud-state-oracle.js` | 19 headless arms. | 13 k |
| `_main/_hud-window-census.py` | the 25 ms four-arm census. | 19 k |
| `_main/_lane18-ui-gate.ps1` | binds all three into one exit code. | 16 k |

### THE DESIGN LANGUAGE IS THE OWNER'S, NOT MINE

`hud-panel.css` reuses `H:\sotto\app\panel\panel.css`'s token **names and
values** — `--bg`, `--text`, `--accent-from`/`--accent-to`, the radii, the Segoe
stack, `background: transparent` on `body`, the slab-must-be-the-window rule. A
second visual language would read as a second product. What is NOT copied is the
slab: SPEC §1.1 draws one plate with at most three lines, and a caption window is
the thing SPEC §1.2's `WS_POPUP` row exists to avoid.

### THE PANEL IS A READOUT, NOT AN INPUT

`hud-panel.js` registers **no** key listener and has no `window.pywebview`
dependency. `DEAL` §1 measured that `RegisterHotKey` reports PRESS ONLY, §4.2(5)
separates the overlay chain from the replay chain, and §6.1/§6.3 forbid
double-firing. A `keydown` listener in the document would be a **third** path
answering a press the OS already routed. The panel renders; `hud-shell.py` hosts;
`src/capture/**` (another lane) owns the keys.

---

## 2. THE CURE — stated, because the brief asked, and shown in code

### THE RULE

> A window this product maps is a promise the user asked for. The HUD window is
> NOT CREATED VISIBLE and NOTHING IS PAINTED OR PUBLISHED until a HUD binding
> fires or `--show-hud` was passed. — SPEC §1.6

### WHY IT IS NEEDED AT ALL

pywebview calls `self.form.Show()` on **every navigation start** when the window
is transparent. READ on this box, pywebview **6.2.1**, `pythonnet` 3.1.0,
`C:\Program Files\Python311\Lib\site-packages\webview\platforms\edgechromium.py`:

```
346  def on_navigation_start(self, sender, args):
347      if self.pywebview_window.transparent:
348          self.form.Show()
349          self.form.Activate()
```

`:102` is the subscription — `self.webview.NavigationStarting`, on the **child
`WebView2`**, not on the form (`:95` `form.Controls.Add(self.webview)`).
`hidden=True` does not buy anything here, and SPEC §1.2 needs transparency for
per-pixel alpha, so the call is reachable on the shipped configuration.

### HOW THE CODE RESPECTS IT — two independent nets

**Net 1, the refusal** (`hud-shell.py`, `gate_form_show`). `Show` is a .NET
method, but pywebview calls it from **Python**, so an attribute on the INSTANCE
shadows it for exactly that call:

```python
base = form.Show
def guarded_show(*a, **kw):
    ...
    if self.args.show_hud or self.shown or opacity < 1.0:
        return base(*a, **kw)          # the three deliberate exits
    self.show_refused += 1
    log(f'HUD_SHOW_REFUSED reason=not-asked opacity={opacity} …')
    return None                        # refuse, and COUNT it
form.Show = guarded_show
```

Three exits, each named: `opacity < 1.0` is pywebview's own invisible creation
dance (`winforms.py:777-782`) — refusing it would leave the form never created,
which measured as a HANG in the sibling project; `--show-hud` is the owner
asking; `self.shown` means a re-navigation must not un-map an already-mapped HUD.

**Net 2, the re-assert** (`on_navigation_start`), for a `Show` that got through
anyway — a future pywebview path, or a `Show` from .NET, which an instance
shadow cannot intercept.

**Net 3, the paint gate** (`hud-panel.css`). `body[data-mapped="0"] .plate`
sets `opacity: 0` **and** `visibility: hidden`, and `data-mapped="0"` is in the
MARKUP, so it holds before any script runs. A panel that is somehow mapped
without being asked still paints nothing. `visibility` is what does the work:
`opacity: 0` alone still composites and still registers as mapped.

**Net 4, the census** (§5 below), because three nets that are believed to work
are not a measurement.

### MEASURED, POPULATION 12 LAUNCHES

| arm | launches w/ opaque window | opaque samples | longest | refusals | re-asserts |
|---|---|---|---|---|---|
| **`live`** (shipped) | **0 / 6** | **0** | **0 ms** | 6 | 6 |
| **`nonet`** (BOTH nets removed, a COPY) | **6 / 6** | **811** | 7.14 s | 0 | 0 |
| **`show`** (`--show-hud`, shipped shell) | 6 / 6 | **711** | 8.36 s | 0 | 0 |
| **`nogate`** (cure removed, re-assert kept) | 0 / 6 | 0 | 0 ms | 0 | 6 |

**POPULATION** 6 launches per arm, all from the single full run `-N 6`. Sample
totals: live 934, nonet 975, show 868, nogate 882. (The earlier N=2 smoke is kept
at `_main/_lane18-census-smoke.out.txt`.) **WINDOW** 6 s per launch, 25 ms
census cadence, **every launch at x=-10000**, so no arm can put a window on the
owner's desk; the axis measured is `IsWindowVisible` + not-alpha-occluded,
neither of which reads a rect.

Extended styles, asserted as **set equality** (SPEC §1.2 / PASS-2), read from
the live window: `exstyle=0x080800A8` = `LAYERED|TOPMOST|NOCTIVATE|TOOLWINDOW|
TRANSPARENT`, `exact_set_equality=True` on every launch of every arm.
`WS_EX_APPWINDOW` is absent, as §1.2 requires.

---

## 3. TWO CONTRADICTIONS INSIDE THE NORMATIVE DOCUMENTS

I did **not** silently resolve either. Both are reported here with the lines.

### 3.1 PASS-5 (per-state distinct glyphs) is UNSATISFIABLE against §3.1 (the state table)

- SPEC §6 PASS-5 (`:578`): "**every** state of §3.1 is reachable and paints a
  **distinct** plate glyph colour".
- SPEC §3.1 (`:335`, `:338`, `:340-344`): `ARMING` and `SAVING` are both
  "saving (amber, pulsing)", and **all five** `ERROR_*` plus
  `HIDDEN_EXCLUSIVE` are "error".

Per-state uniqueness therefore cannot hold: it needs 11 distinct glyphs and §3.1
supplies 4. Measured, first run of the oracle: **11 shared-glyph pairs** across 9
painted states.

**Which one governs, and why.** §3.1 is the state table and is what the
implementation must reproduce. PASS-5's own **falsifier** is the tie-breaker and
names exactly one requirement: "a build where `HIDDEN_EXCLUSIVE` paints the idle
glyph ⇒ the distinctness assertion fails". That is a claim about
**confusability**, not pairwise uniqueness. SPEC §1.3's reason for the grouping is
the requirement that actually protects the user: "deliberately distinct from the
recording red so a failure never reads as 'recording'".

**What the gate asserts instead** (all three, and all satisfiable):
- `PASS-5-no-state-looks-idle` — no state shares `IDLE`'s glyph.
- `PASS-5-error-never-reads-as-recording` — no error shares `RECORDING`'s.
- `PASS-5-groups-match-spec-3.1` — the groups are exactly `saving:2, armed:1,
  recording:1, error:5`, i.e. §3.1 reproduced, not approximated.

**FOR THE SPEC'S OWNER:** either relax PASS-5's wording to "no two states that
must be told apart share a glyph", or give §3.1 nine distinct glyph colours. The
second is a product decision, not a documentation fix.

### 3.2 `DEAL` §6.3 ("refuse duplicates at arm time") would refuse 5 of SPEC §4.2's own rows

- SPEC §4.2 rows H1/H3/H4/H5/H6 each cite a `trigger.cpp` line as the rung they
  match (`trigger.cpp:69`, `:70`, `:71`, `:72`, `:73`), and H2's own rationale is
  "a duplicate so a machine that owns `Alt+F9` still has one free".
- So SPEC §4.2 and `DEAL` §2.1 **deliberately share five** `vk`+`mods` pairs.
  Measured: `Alt+F9, Alt+F10, Alt+F11, Ctrl+F12, PrintScreen`.
- `DEAL` §6.3 says "Duplicate bindings must be refused at arm time … §2.1 and §2.4
  are disjoint today". Read across the two documents that rule refuses 5 of
  SPEC's own rows, which cannot be the intent.

**Resolution taken, stated so it can be disagreed with by name:** §6.3's refusal
applies **within one arm**, because that is the only place a double-fire happens.
A HUD row and a ladder rung are the same physical key on purpose: one press, one
cut, two subscribers of one event. The gate therefore asserts:

| assertion | measured |
|---|---|
| overlay × replay-ladder == 0 (`DEAL` §2.4's actual claim) | **0 pairs** |
| overlay × hud-table == 0 (Alt+C can never collide with a HUD key) | **0 pairs** |
| hud × replay overlaps are **all declared** via a `dup_of` field | **5 of 5 declared, 0 undeclared** |

An **undeclared** overlap is the defect §6.3 is really about, and it fails the
gate. `DEAL` §2.2's F12-last ordering is asserted separately and passes.

---

## 4. THE GATE

```
pwsh -NoProfile -File _main\_lane18-ui-gate.ps1              # all four arms, N=6
pwsh -NoProfile -File _main\_lane18-ui-gate.ps1 -Quick -N 2  # live, nonet, show
```

Three instruments, one exit code:

1. **`_hud-state-oracle.js`** — 19 headless arms. **POPULATION** 19 arms, 11
   states, 10 HUD bindings, 5 DPI cases. **WINDOW** none — no window, no audio,
   no display. Headless on purpose: running these in a real WebView2 would put a
   window on the owner's screen to learn what a pure function can answer.
2. **`_hud-window-census.py`** — the 25 ms four-arm census of §2/§5.
3. **`hud-shell.py --json-out`** — the **live DOM**, read back through the
   panel's own `probe()`: **computed** styles and measured boxes, never the
   attributes the panel set on itself, so a panel that sets `data-mapped="1"`
   and still paints nothing cannot pass.

**Result: `POPULATION boxes=36 red=0` · `VERDICT PASS`** — the `-N 6` run above.
(The `-Quick` run reports 34 boxes because it skips the two report-only arms.)

Both colours are present and each names what it observed:

```
GREEN PASS-1-live-maps-nothing-unless-asked
      launches_with_opaque_window=0/6 samples=… opaque_catch_samples=0
      longest_opaque_ms=0 show_refused_total=6 reassert_total=6 nets2_lines=6
      POPULATION=6 launches WINDOW=6s @ 25ms, x=-10000
GREEN CONTROL-nonet-maps-the-window
      launches_with_opaque_window=6/6 opaque_catch_samples=811 longest_opaque_ms=7140
      show_refused_total=0 reassert_total=0
      -- THIS is the arm that proves the census can see a window
GREEN PASS-1b-show-hud-maps-the-window
      launches_with_opaque_window=6/6 opaque_catch_samples=711 hud_show_mapped_lines=6
      -- so a panel that never maps cannot pass
GREEN PASS-1c-not-mapped-means-not-painted
      data-mapped=0 computed_visibility=hidden computed_opacity=0
GREEN SPEC-5-live-dpi-192  plate_measured_w=750 spec_range=[480..960]
```

### THE GATE FOUND FIVE REAL DEFECTS IN MY OWN CODE

Named here because a receipt that lists only successes is not a receipt:

| # | defect | how it surfaced | fix |
|---|---|---|---|
| 1 | `background_color='#00000000'` — pywebview slices 3 hex pairs (`:106-111`) and raised `ValueError('#00000000 is not a valid hex triplet color')`, rc=1 | direct run | six-digit `#000000`; `edgechromium.py:113-114` overwrites it with `Color.Transparent` anyway |
| 2 | log written **only at exit** → a hang wrote nothing, so a hang was indistinguishable from a launch that never started | 20 s hang with no log | rewrite the file on every line |
| 3 | `--exit-after` armed inside `on_loaded` — the event that does not fire when the shell hangs | same hang | `arm_failsafe()` before `webview.start()`; `os._exit(0)` **first**, because `destroy()` marshals onto the GUI thread and blocked forever |
| 4 | `int(form.Handle)` — a .NET `IntPtr`; `TypeError: … not 'IntPtr'` | log line | `form_handle()` → `ToInt64()`, with the loud fallback |
| 5 | re-assert subscribed on `window.native` (the `BrowserForm`) → `AttributeError`, swallowed into a `pass`, so **the second net was absent on every run** while the file read as if installed | `nets_armed=1` | `_webview_control()` → `form.Controls[0]`; `nets_armed=N` is now in the startup line so this can never be silent again |

Defect 5 is the one worth remembering: **a swallowed `except` on a
load-bearing path is not a style problem, it is a silent downgrade**, and only a
number in the log (`nets_armed=2`) surfaced it.

---

## 5. THE ARM THAT MEASURED GREEN AGAINST THE BRIEF

The brief said the control arm "goes RED when the cure is reverted in a COPY".
The `nogate` arm — cure reverted, re-assert kept — came back **GREEN**: 0/6
launches, 0 opaque samples.

**This is a correct result about the wrong mechanism, and I report it rather than
re-picking the arm until it went red.**

Why: the re-assert is subscribed to the **same** .NET event pywebview subscribes
(`edgechromium.py:102`), so .NET raises handlers in subscription order —
pywebview's `form.Show()` runs first, our `Hide()` immediately after, **in one
dispatch**. The window is mapped for less than the 25 ms sampling grid, so this
instrument cannot see it. The sibling project measured the same thing from the
other side: same-dispatch re-assert did not close its flash (18/20 vs the
un-fixed 19/20), which is why it built the `_gate_form_show` instance-shadow
refusal in the first place.

So `nogate` alone **cannot** prove the instance-shadow gate is load-bearing, and a
gate that claimed otherwise would be crediting the cure for something the
re-assert did. Two changes followed:

- **`nonet` was added** — both nets removed in a copy. It maps **6/6** launches,
  811 opaque samples, longest 7.14 s. That is the arm that proves the census is
  not blind, and it is the gate's asserted control.
- **`nogate` is kept and reported as its own arm**, explicitly *not asserted*,
  so the measurement survives for whoever re-tunes the cadence.

**A caveat I will not paper over:** this proves the cure **and** the re-assert
together prevent the map at a 25 ms grid. It does **not** isolate the cure's
contribution, and it does not rule out a sub-25 ms flash. Isolating it needs a
cadence this box cannot sample (the sibling's own census had the same limit).
`NOT MEASURED`: the duration of the map in the `nogate` arm.

---

## 6. DEVIATIONS AND THINGS I DELIBERATELY DID NOT DO

- **The native layered window is NOT built.** SPEC §1.2-§1.6 and §7 describe a
  C++ `hud.h` inside the capture process. `src/capture/**` belongs to another
  lane (brief rule 5). **The hookup is in §7 below**, in the exact form the
  trigger/capture lane can paste.
- **`PASS-4` (pixel proof) is NOT attempted.** SPEC §6 records monitor-item WGC
  as **refused** on this box (`E_ACCESSDENIED` for every item while `IsSupported()`
  still returned true). A SKIP is not a pass, so no box claims it.
- **`PASS-7/8` (exclusive fullscreen), `PASS-10` (idle cost), `PASS-11`
  (refresh rate), `PASS-12` (one `UpdateLayeredWindow` per frame)** — all need the
  native window and the capture process. `NOT MEASURED`. `HIDDEN_EXCLUSIVE` IS
  rendered and glyph-distinct; it is not driven by a DEVMODE fixture.
- **No game was run.** Nothing here claims a hotkey works in-game; `DEAL` §4.5
  and SPEC §4.5 both say that is unmeasured and it stays that way.
- **No screenshot.** Every DOM claim is a **computed style or a measured box**
  read through the live WebView2, which is stronger for these assertions than a
  picture, and the receipt says which is which. A screenshot nobody took is not
  a result, so none is cited.
- **No `git commit`** (brief rule 7: commit only on green). Gate is green;
  committing is the parent's call.

---

## 7. THE HOOKUP FOR `src/capture/**` — another lane's files, not mine

For the trigger/capture lane, verbatim:

- **Call site** — after a binding fires, and **only** there:
  `hud.show()` / `hud.hide()` (`SPEC` §1.6 steps 2-3 are the ONLY mapping sites).
- **Styles** — SPEC §1.2's set, then re-issue
  `SetWindowPos(..., SWP_NOMOVE|SWP_NOSIZE|SWP_NOZORDER|SWP_FRAMECHANGED)`
  after any `SetWindowLong`. **Never** `SetForegroundWindow`. **Never**
  `SetLayeredWindowAttributes` — it switches a layered window out of the
  `UpdateLayeredWindow` path and destroys per-pixel alpha (SPEC §1.3).
- **Alpha** — only through `UpdateLayeredWindow(..., ULW_ALPHA)`.
- **State line** — emit `hud_state=<HudState enum name>`, verbatim
  (`hud-contract.js` `tokens()` is the list; the log token and the plate's line 1
  must be the same string).
- **The mapping order is load-bearing** (SPEC §1.6): `UpdateLayeredWindow` at
  **α=0** first (sizes and positions), then
  `SetWindowPos(..., SWP_SHOWWINDOW|SWP_NOACTIVATE)`, then the next frame
  publishes α>0. Mapping first shows an unsized rectangle at the wrong origin.

---

## 8. POPULATION / WINDOW INDEX

| claim | POPULATION | WINDOW |
|---|---|---|
| gate verdict | **36 boxes, 0 red** | N=6 launches/arm, 6 s each, 25 ms census, x=-10000 |
| headless oracle | 19 arms, 11 states, 5 DPI cases | none — no window, no display |
| `live` maps nothing | 0/6 launches, 0 opaque samples | 6 s × 25 ms, off-screen |
| `nonet` maps | 6/6 launches, 811 opaque samples (975 samples total) | as above |
| `show` maps | 6/6 launches, 711 opaque samples (868 samples total) | as above |
| ex-style set equality | 4 lines/launch × 6 launches | live + 3 control arms |
| live DOM probe | 1 shell run per DPI case, rc=0 | 6 s, `ERROR_SILENT_DEVICE` |
| plate width @144 dpi | 667 px, spec range [360..720] | 1 run |
| plate width @192 dpi | 750 px, spec range [480..960] | 1 run |
| sub-25 ms map in `nogate` | `NOT MEASURED` | — |
| in-game hotkey behaviour | `NOT MEASURED` | no game was run |

**Artifacts:** `_main/_lane18-gate.out.txt` (box list + both instrument logs),
`_main/_lane18-gate-console-full.txt`, `_main/_lane18-gate-console.txt`,
`_main/_lane18-census-*.out.txt`, `_main/_lane18-state-oracle.out.txt`, and
`_main/_lane18/` (per-run logs and JSON).

---

## 9. SELF-AUDIT

- **High confidence** — the four census arms, the computed-style probes, the
  contract table vs the two documents (all read, all line-cited). Would move on a
  different pywebview build; the `edgechromium.py` line numbers are version-pinned
  to 6.2.1 and the file says so.
- **Medium confidence** — that the cure is load-bearing **in isolation**.
  §5 explains exactly why I cannot claim it and what would.
- **The 6.3/§4.2 resolution is an interpretation**, stated in §3.2 with the line
  numbers so it can be rejected on the evidence rather than on taste.
- **Confidence raised by** running the oracles twice (three defects only appeared
  on the second pass), by a control arm that goes RED in a copy, and by reading
  the failure logs rather than the exit codes.
- **New named verification boxes I created** (all asserted in the gate):
  `PASS-6-unmeasured-says-so`, `SPEC-1.1-ceiling-holds-at-4000-chars`,
  `DEAL-6.3-hud-overlaps-all-declared`, `CONTROL-collisions-clean-on-distinct`,
  `PASS-5-error-never-reads-as-recording`, `PASS-5-groups-match-spec-3.1`,
  `PASS-1c-not-mapped-means-not-painted`, `CONTROL-nonet-maps-the-window`,
  `SPEC-5-live-dpi-144`, `SPEC-5-live-dpi-192`, plus the census's
  `ARM-LAUNCHABLE` (an arm that cannot start can never report a pass — it exists
  because two arms once reported `0/2 launches, 0 catches` while having died with
  rc=1).
- **Gate doubts** — `nogate` is green and I report it rather than hide it; the
  two DPI boxes are single-run; `PASS-4` through `PASS-12` are unmeasured and
  cannot be measured from this lane.
- **Reviewer** — a verifier subagent was requested by the brief. **I could not
  dispatch one: this session has no `task`/subagent tool available**, and the
  seat constraint says a read-only role must not be handed a file to write. So the
  mandatory review step is **NOT DONE**, and it is reported as such rather than
  as a passing formality.