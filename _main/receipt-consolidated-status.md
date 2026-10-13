# RECEIPT — CONSOLIDATED GATE STATUS, 2026-10-13

Every gate this session touched or that a lane produced, run on the committed bytes.
**All green, and every one carries a control arm that can say NO.**

| gate | control | negative arm |
|---|---|---|
| `instruments-battery.mjs` (house) | **79/79 rc=0, failed=0, launches=0** | — |
| `strip-geometry-oracle.py` | PASS, 15 checks | PASS, 21 checks, **6/6 mutants RED** |
| `base-themes-oracle.py` | PASS | **CONTROL VERDICT PASS** |
| `cine-themes-oracle.py` | PASS | 8 mutants, **0 inert** |
| `cinematic-designs-oracle.py` | PASS | 6 mutants, **0 inert** |
| `zipc-designs-oracle.py` | PASS | 6 mutants, **0 inert** |
| `three-overlays-oracle.js` | PASS | 8/8 RED (incl. the N8 this session added) |
| `theme-preview-oracle.js` | PASS | 6/6 RED (incl. ARM14.1b) |
| `scope-leak-oracle.js` | PASS, 9 sheets, 0 leaks | 4 mutants RED |
| `fonts-fidelity-oracle.mjs` | PASS (A/B/C/D) | 2 RED |
| `caption-independent-oracle.js` | PASS, 46 checks | 6/6 RED |
| `botoes-lane-oracle.js` | PASS, 33 checks | 7/7 RED |
| `_panel2-dom-probe.js` | **GREEN, 83/83 arms** | carries its own copy control |

## The owner list, and where each item stands

| # | item | state |
|---|---|---|
| 1 | bottom panel minimal AND movable | minimal **verified live** (380x40); movable: implemented, **not verified** |
| 2 | caption independent, no background | decoupled, measured; shell transparency A/B measured |
| 3 | the solid-colour div | **closed, verified live** — the window IS the pill |
| 4 | the zips original fonts | closed (weight 300 was the gap, not family) |
| 5 | live button, clear state; right-panel caption button removed | closed |
| 6 | X moved to the right | closed |
| 7 | Alt+C twice opens the right panel | **closed, verified live** |
| 8 | theme change must not scroll to top | closed, gated |
| 9 | bugged designs | closed in code and by parse; **all 45 themes paint and all differ** |
| 10 | each zip design equal to the zip, a real revamp | zip-C: min structural difference 0 -> 63; 0 recolours measured |

## What is NOT closed, named plainly

1. **The drag moving the window** — implemented (page, bridge, shell), never verified. Three
   probe approaches were exhausted: a direct bridge call cannot reach the shell from the
   context the shell own `exec_js` runs in; an unknown-kind dispatch cannot either; synthetic
   pointer events do not fire the panel handler. **The owner hand on the mouse is the
   instrument left.**
2. **`--size-meta`** — ten declarations, zero readers. A design decision, written up in
   `receipt-size-meta-decision.md` with the two options.
3. **Fidelity to the zip mockups** — never measured. "Different" is not "equal to the design".
4. **The 4 `UNSETTLED`/no-window leftovers of the first census** were resolved; `Feed` keeps
   `UNSETTLED` correctly (animated sheen bar) and its 1618 colours are an observation.
