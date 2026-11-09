# OMP subtitle overlay design and dragging

Status: dispatched directly through OpenCode Go 2 / DeepSeek V4.1 Flash with the active H:\env config.

## Required start

- Read this editable TODO first.
- Read the following skills before source edits: C:/Users/Administrador/.agents/skills/task-resolver/SKILL.md; H:/sotto/.opencode/skills/bug-hunt-sotto/SKILL.md; C:/Users/Administrador/.agents/skills/design-taste-frontend/SKILL.md.
- Use the project’s active bug-hunt procedure for the reported defect. Treat the current live process as STALE and do not claim runtime behavior verified.
- Do not delegate to Luna or relay through another agent. This is a direct OMP lane.

## Owned paths

- app/webview/caption_overlay.py
- app/webview/caption_drag.py
- _main/caption-overlay-theme-oracle.py
- _main/caption-drag-oracle.py

## Acceptance
- MECHANICAL: every theme payload gives its on-screen subtitle a designed background/face that matches the theme demo identity; no portrait/demo circles; overlay can be dragged with a bounded frame/update rate up to 240 Hz; hidden/idle display does not stop model or history.
- JUDGMENT: inspect offscreen renders at representative and edge themes for readable contrast, line fit, spacing, and a deliberate visual hierarchy; keep captions visually designed for all 59 payloads rather than one default bed.

## Existing gates
- Existing caption-overlay-theme-oracle.py and --neg-arm (all 59 payloads)
- Existing caption-drag-oracle.py and --neg-arm
- Existing caption-kept-on-hide-oracle.py, only if its owned path is not changed

## Shared constraints

- Read AGENTS.md and this TODO before editing; follow the task-resolver and bug-hunt-sotto procedures. Current process freshness is STALE (pid 50452, 13 source files changed after start). No runtime symptom may be called verified.
- Do not launch, restart, show, or synthesize input to the Sotto app. Preserve every existing dirty change; never reset, restore, or rewrite unrelated files.
- No full battery, build, model benchmark, or mutation campaign without a current exclusive heavy lease and the project artifact preflight. Keep work source-focused; if a focused gate is light, use its existing positive and negative arms.
- Keep all subprocesses hidden through the repo launcher / hidden execution method. No visible terminal, popup, browser, or owner-screen activity.
- Acceptance includes the mechanical checks and the judgment-based rendered/interaction quality described below. Record the evidence, changed paths, and remaining runtime limits in this TODO.
- Do not add Bend laws for latency or budgets. If touching any load-bearing Bend claim/proof, read docs/bend/README.md, then docs/bend/BEND_PROOFS_REFERENCE.md, then docs/bend/BEND_LAW_GUIDE.md.

## Scope boundary

Own only the listed paths. Do not edit panel HTML/CSS/JS, subtitle source/startup files, history, worker/model, battery wiring, AGENTS.md, or _audit-verify-all.cmd. Report any integration seam outside this set.

## Lane result

- Source findings: the working tree already carried the design/drag implementation in the four owned paths when this lane started (dirty files dated 2026-11-09 07:24–08:54; the two app modules are 07:24 `caption_drag.py` and 08:02 `caption_overlay.py`, both before the 08:14:03 app start, while the two oracles are 08:11 and 08:54 and are not loaded by the app). This lane made **no additional product/source edits** and preserved those dirty changes byte-for-byte. What the code does today:
  - `caption_overlay.py` separates the content deadline (`_content_due_at`) from the poll pace, so the drag poll runs at `caption_drag.DRAG_FRAME_S` (1/240) without paying a paint per tick; a paint frame still passes through `_limit_by_paint` (40% of one core). It measures and logs `CAPTION_DRAG_RATE ticks= moves= paints= seconds= hz= target_hz=240 paint_ms=`.
  - `caption_drag.py` raises the drag ceiling from 60 Hz to `DRAG_FRAME_HZ = 240` (`DRAG_FRAME_S = 1/240`), while the pulse stays at 30 Hz and the idle poll at its slow pace.
  - `caption-overlay-theme-oracle.py` keeps the house hidden-launch helper for the payload refresh (no console window on the owner screen).
  - Theme identity reaches the native overlay through `_brand_tokens` → `overlay_paint._normalise_theme` → `_premultiplied_bitmap`: plate colour/alpha/radius from each payload (`rowBg`/`rowBgAlpha`/`rowRadius`, alpha floor 140), rule, padding, and player face (Arial 38, leading 1.35, stroke 5). `overlay_paint.py` is clean and was not edited (outside the owned set).
  - No payload produces an LED/avatar ellipse: all 59 normalised themes report `led=false`, so no portrait/demo circle is painted on the overlay.
- Changed paths:
  - `app/webview/caption_overlay.py` (pre-existing dirty, untouched by this lane; sha256 `78A3421662489D8FAD9FFBC83D6E6747B2FC10ECBFA95D2B0E265026D48426BB`)
  - `app/webview/caption_drag.py` (pre-existing dirty, untouched; sha256 `553824B2242B3E87A19E1B77726C322B0734B3FF29D27057D3C1C53F0A81F124`)
  - `_main/caption-overlay-theme-oracle.py` (pre-existing dirty, untouched; sha256 `058A6D5799E806FD1FA76143551F70117125D3A0A074519FBDDA0AF431A0F64E`)
  - `_main/caption-drag-oracle.py` (pre-existing dirty, untouched; sha256 `2D61AFAECB0B6001B85494D20AF4BC7DB7F3161E24459A52B95C8CC0BFCC54F6`)
  - Aggregate diff vs HEAD for the four owned paths: 355 insertions, 17 deletions.
  - Lane-added evidence artifacts (cache/scratch, not product code): `_main/_cache/_theme_stills.py`, `_main/_cache/theme-stills/*.png`, `_main/_cache/theme-stills-summary.json`, this TODO.
- Focused evidence (all subprocesses hidden with `CreateNoWindow`/`Start-Process -WindowStyle Hidden`; no app launch, no synthetic input):
  - `python _main/caption-overlay-theme-oracle.py --json _main/_cache/_theme_oracle_result.json` → exit 0, `VERDICT: PASS (8/8)`: `designs=59 sem_placa=0`, `cor_errada=0`, `camas=56 piso=47 de 59`, `face_errada=0`, `raios=8 piso=5`, `renders=59 fora=0`, empty payload → `plate=None face=Arial`, `payloads=59`.
  - `python _main/caption-overlay-theme-oracle.py --neg-arm` → exit 1 with `CAUGHT M1 sem-placa`, `CAUGHT M2 placa-generica`, `CAUGHT M3 face-do-payload`, `NEG-ARM: PASS -- 3/3 mutants caught` (rc 1 is the house convention for “caught”).
  - `python _main/caption-drag-oracle.py` → exit 0, `VERDICT: PASS (14/14)`, including `P12 a arrastar: poll nao pinta, conteudo vencido pinta` and `P13 arrasto: 128 Hz entregues, 132 ticks, 0 pinturas` (P13 floor is 120 Hz, half the 240 Hz ceiling) and `P14 pulso do Ctrl dentro do orcamento de pintura (delay=50.0 ms)`.
  - `python _main/caption-drag-oracle.py --neg-arm` → exit 1, all plan mutants red (P1/P4/P5/P6/P7/P9) and `NEG-ARM poll-repinta-ao-mover CAUGHT`, `NEG-ARM limite-da-pintura-no-poll CAUGHT`, `NEG-ARM pulso-fora-do-orcamento CAUGHT`, `NEG-ARM VERDICT: PASS (plan=CAUGHT, poll=3/3)`.
  - `python _main/caption-kept-on-hide-oracle.py` → exit 0, `caption-kept-on-hide-oracle: PASS` (14 arms): hiding the panel keeps the live caption (`CAPTION_WINDOW_KEPT`), and A/B/C/D prove history still leaves when display is off; blanking still happens on pause/end/silence.
  - `python _main/live-code-freshness-oracle.py --strict` → exit 3 `LIVE_CODE STALE` (pid 50452 started 2026-11-09 08:14:03; 14 source files changed afterwards). Runtime behavior remains UNVERIFIED.
  - `python _main/_cache/_theme_stills.py _main/_cache/theme-stills` → 59 offscreen renders, `contrast_min=1.81`, `box_frac_max=0.334`, `boxes_over_68pct=[]`. Representative + edge stills inspected: `theme-1..5`, `cine-midnight-rain`, `cine-cafe`, `cine-tideline`, `pd-tele`, `pd-cine`, `pd-instr`, `GlassCards`, `Gutter`, `cine-adobe`, `cine-paper-rain`, `cine-snowline`, `cine-terrace`.
  - Judgment from the stills: plate identity is visible and distinct per design (charcoal, green-black, blue-black, brown, warm ink, paper-light, etc.); the face is the player’s Arial 38 with a 5 px black stroke in every theme; two lines fit inside 33.4% of a 1920 frame (the internal budget is 68%); the previous line sits above at the smaller `prevPx`, giving the intended echo/live hierarchy; radii range 0–29.6 px and follow the design. The two light-paper designs (`cine-paper-rain`, `cine-snowline`) measure 1.81/1.93 fill-vs-plate contrast, but the mandatory 5 px black stroke keeps them legible in the stills — changing that plate would discard the theme identity the acceptance asks to keep.
- Independent review/evidence: none. These are self-run gates and self-inspected renders; `caption-overlay-theme-oracle.py` re-runs the real `_brand_tokens`/`_normalise_theme`/`_premultiplied_bitmap` path, and its negative arm mutates copies, so the verdict is not a text read — but there is no separate author/reviewer split.
- Gates re-run in this session (2026-11-09 12:0x, same bytes as above, all subprocesses hidden, no app launch, no synthetic input):
  - `python _main/caption-tick-thread-oracle.py` -> exit 0, `VERDICT: PASS (10/10)`: `A1 o relogio pinta (frames=170 em 1 s)`, `A2 zero threading.Timer (contados=0)`, `A3 um fio so' (cresceu 1)`, `A7 custo medido limita o pedido e loga`, `A10 laco real: fracao de nucleo 0.26 <= orcamento (22 Hz, 20 quadros)`.
  - `python _main/caption-tick-thread-oracle.py --neg-arm` -> exit 1, `NEG-ARM: PASS (A2 caiu=True, A3 caiu=True com o Timer por frame de volta)` and `NEG-ARM VERDICT: PASS (6/6)` (tecto de volta a 60 Hz, limite de volta ao custo, orcamento de volta a 1.0, relogio de grao grosso).
  - `python _main/caption-kept-on-hide-oracle.py` -> exit 0, `caption-kept-on-hide-oracle: PASS` (14 arms): `CAPTION_WINDOW_KEPT reason=panel-hidden wanted=true`, history still leaves with the display off (A/B/C/D), pause/end/silence still blank, `E pausa do YouTube nao cala o Stremio`.
  - `python _main/caption-kept-on-hide-oracle.py --neg-arm` -> exit 1, `NEG-ARM: PASS -- hide=CAUGHT pausa=CAUGHT deferred=CAUGHT display=CAUGHT pausa-pixels=CAUGHT release=CAUGHT escopo=CAUGHT retoma=CAUGHT` (the mutant restores the `_blank_caption_window('panel-hidden')` path and also plants a `NameError("name 'on' is not defined")`).
  - `python _main/caption-drag-oracle.py` -> exit 0, `VERDICT: PASS (14/14)`, `P13 arrasto: 196 Hz entregues, 197 ticks, 0 pinturas`.
  - `python _main/caption-drag-oracle.py --neg-arm` -> exit 1, `NEG-ARM: PASS (vermelhas=7/14: P1, P13, P4, P5, P6, P7, P9; exigidas=P4, P7, P9)` plus `poll-repinta-ao-mover CAUGHT`, `limite-da-pintura-no-poll CAUGHT`, `pulso-fora-do-orcamento CAUGHT`, `NEG-ARM VERDICT: PASS (plan=CAUGHT, poll=3/3)`.
  - Honest caveat on P13 (recorded, not hidden): the FIRST positive run of the pair delivered **27 Hz** and failed, in the same minutes the machine reported `LoadPercentage=82` with foreign CPU consumers (chatterino, MsMpEng, two `bun`, chrome) and concurrent lanes running pytest/watcher/codeintel work. The immediate re-run on the SAME bytes delivered 196 Hz. So the 240 Hz ceiling is real in the loop and the poll does not paint during a drag, but P13's 120 Hz floor is load-sensitive on this machine, and the drag rate of the live app (pid 50452) is still UNMEASURED.
- Integration `code-health` (this lane's close attempt, measured now):
  - `python _main/code-health-oracle.py` -> exit 2, `CODE-HEALTH VERDICT FAIL`, **11 metric(s) / 4 files** RED, none of them this lane's: `app/panel/history-store.js` 25714 B (+5673) / 657 lines (+154); `app/panel/panel-unified.css` 29240 B (+3200) / 562 lines (+51); `app/webview/history_context.py` 15188 B (+2802) / 373 lines (+63), defs 11->12, max_func 35->44; `worker/wasapi_loopback.py` 58473 B (+3185) / 1244 lines (+28), max_func 142->152.
  - This lane's own files are `SAME`: `caption_overlay.py` 83880 B and `caption_drag.py` 12566 B sit exactly on their baseline rows. The caption growth described above is already inside `_main/code-health-baseline.json` (mtime 2026-11-09 10:25:22), so it is not part of the RED population.
  - The gate itself is healthy, not broken: `python _main/code-health-oracle.py --neg-arm` -> exit 1, `NEG-ARM 3 of 3 mutant(s) caught` (M1 +1 byte, M2 longer function, M3 new except-pass) with `POS-ARM o comparador diz VERDE no baseline PASS as expected` and `POS-ARM e diz VERMELHO a +1 byte PASS as expected`. The FAIL is the measured tree.
  - Attribution: `history-store.js` + `history_context.py` are the active history dedupe/recall lane (`.agent-work/TODO-omp-history-dedupe-recall-20261109.md` names both as changed paths, with retention/`RETENTION_H`/`prune()` and the codec-parity work); `panel-unified.css` is the panel/theme composition lane (`.agent-work/TODO-omp-panel-all-themes-20261109.md`, listed in `receipt-omp-themes.json`); `worker/wasapi_loopback.py` has **no declaration in `.agent-work` at all** - the nearest artifact is a dirty `_main/wasapi-buffer-fallback-oracle.py`, so that growth is undeclared drift from another active lane and is reported here, not absorbed.
  - Why it is NOT closed here: the oracle documents `--update` as owner-agreement-only, the integration task forbids blessing other lanes' uncommitted growth to manufacture green, and all four RED files are outside this lane's ownership and are being actively edited, so shrinking or reverting them would clobber another lane's work. There are exactly two admissible closes: (a) the owning lanes shrink their own growth so the ratchet goes green with no baseline change, or (b) the owner authorizes a baseline regeneration that records this measured population. Until one happens, `code-health` stays RED and this TODO records it as an integration blocker with the numbers above - not as passed. Provenance of that decision: this run was non-interactive and no owner authorization for a baseline refresh exists in it, so the default was the blocker record, and `_main/code-health-baseline.json` was left at its committed state (mtime 2026-11-09 10:25:22, untouched by this lane).
- Remaining uncertainty:
  - The live app is STALE; the measured drag rate is the oracle's real 240 Hz-cap loop on this machine (128-196 Hz delivered across runs, 27 Hz in one loaded run), not a measurement of pid 50452. No live window was dragged.
  - The 240 Hz figure is the ceiling; delivered rate depends on scheduler load. The 40% paint budget still bounds content repaint, so a content repaint during a drag can be slower than the poll.
  - No independent reviewer ran the gates; `fixed, NOT verified` is the ceiling for runtime behavior.
  - `overlay_paint.py` is the real painting seam and is outside the owned set; it was read and executed by the oracle but not edited.
