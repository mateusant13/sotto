# Receipt 2026-11-27 — the pause oracle judged the wrong thing, and the arch slider has a floor

## 1. `_main/yt-pause-disagreement-oracle.py --log` was a broken instrument

**What it judged.** The old `--log` rule paired a `YOUTUBE_PAUSE_DISAGREED` with a
`YOUTUBE_PAUSE_PROVEN` inside ±5 lines, same `vid`, `|Δt| ≤ 0.05`. The shell writes a
`DISAGREED` the moment the two witnesses disagree and a `PROVEN` one or two ticks later
**when they converge** — so the rule measured *convergence*, not harm. Measured on the
full `_main/webview-run.log` (284 010 lines): `episodes=32`, `contradicted=9` in the
owner's last session — while that session carried exactly **one**
`CAPTION_WINDOW_BLANKED reason=youtube-paused`, armed by a `PROVEN held_s=0.5 t=2.85`
that came back with `RESUMED 13 lines later. Zero harm, nine accusations.

**Why `t` cannot be the witness.** A player position is *invariant while paused*, so
`|Δt| ≤ 0.05` cannot distinguish "the same measurement" from "a measurement that converged
one tick later". A gate that accuses the code that is right loses its authority.

**The corrected rule.** Harm = a `CAPTION_WINDOW_BLANKED reason=youtube-paused*` armed by a
`PROVEN` whose own episode also logged a `DISAGREED` at the same `t` (`T_MATCH_S = 0.05`,
same `vid`, within 8 lines). That is the shape of the 2026-11-26 02:38:01 defect: an
episode that measured `clock_rate=0.58` and still blanked the screen.

**Measured, both directions, same tree:**

| arm | command | result |
|---|---|---|
| positive | `python _main/yt-pause-disagreement-oracle.py` | `VERDICT: GREEN (5 arms)` rc 0 |
| negative | `... --neg-arm` | `NEG-ARM VERDICT: PASS`, 9/9 mutants caught, rc 1 |
| owner's last session | `... --log _main/webview-run.log` | `episodes=27 contradicted=0 settled=9` `VERDICT: CLEAN` rc 0 |
| pre-fix window | `... --since '2026-11-26 02:37:5'` | `episodes=46 contradicted=2`, rc 1 |

The two new classifier mutants are `e-volta-a-regra-antiga` (blind to the blank) and
`e-cego-ao-carimbo` (`T_MATCH_S = 1e9`); either one silently disables the whole judgement,
so both must go red.

## 2. The architecture slider has an arithmetic floor, measured

`exocortex/revival_engine.py:436-447`:

```
arch_score = 100 - min(40, int(mono_pct * 4.5 + min(mono_cnt, 10) * 1.5))
```

With 13 monoliths of 162 files: `int(8.02 * 4.5 + 10 * 1.5) = int(51.1) = 51`, clamped to
**40**, so the score is exactly **60**. `surface.arch_doc` (−8) and the feature map are
already satisfied, so `docs/ARCHITECTURE.md` and the S1 display-geometry extraction moved
this number by **zero** — that is the formula talking, not the work.

| monoliths | penalty | score |
|---:|---:|---:|
| 13 (today) | 40.0 | 60.0 |
| 5 | 16.2 | 83.8 |
| 2 (target 90) | 8.6 | 91.4 |
| 1 | 4.3 | 95.7 |

Reaching 90 needs `monolith_count ≤ 2`: **11 files must shrink below 20 000 chars**, the
next being `worker/sotto_worker.py` (10 230 lines). Recorded in the slider's own
`why_not_100` rather than re-drawn.

## 3. `benchmarks/sliders.json` — foreign product stages purged

A pasted `--levels-json` had written another product's stages into 7 of 8 rubrics
(`capture start`, `clip export`, `replay`, `panel verification`, `recording handoff`).
Rewritten against Sotto's real surfaces: YouTube CDP caption read, cue-to-paint, Alt+C
gesture, shared audio capture, history merge, worker ASR + diarizer.

Only evidence prose moved. Verified `current`, `target`, `baseline`, `proof_cmd` and
`evidence` are byte-identical to HEAD for all 8 sliders; `slider_scorecard.py report
--strict-evidence --require-rubric` now reports `missing_rubric_sliders: []`,
`missing_why_not_100: []`, `duplicate_evidence: []`. The remaining `FAIL` is three score
gaps (60→90, 88→90, 94→95), not a structural defect.

## 4. Final verification, after the last edit

```
multi-monitor-oracle.py            PASS 6 arms / 30 checks, --neg-arm 11/11 red, rc 1
undefined-names-oracle.py          {"files": 20, "undefined": 0, "verdict": "GREEN"}
yt-pause-disagreement-oracle.py    GREEN (5 arms) rc 0 / neg 9/9 caught rc 1
yt-diag-truth-oracle.py            GREEN (4/4) rc 0
unreferenced-oracle-census.py      rc 0 / --neg-arm both mutants CAUGHT rc 1
artifact-manifest-oracle.py        5/5 arms rc 0
dead-unwired-oracle.py             PASS (arms=4 fail=0)
claims-date-oracle.py              PASS checks=4 fail=0
battery-launch.py --verify         pins/wiring/pairing/class/undefined-names all PASS
_gitattributes-verify.py           PASS, 0 divergent
py_compile shell + display_geometry COMPILE_OK
```

## 5. What is NOT verified

The S1 split and the two product fixes (`02793b2` budgeted CDP read, `1d2649d` CDP retry
cooldown) are `fixed, NOT verified` at runtime: `_main/live-code-freshness-oracle.py`
still names the last `SHELL_STARTUP_STAGE` pid 53752 @ 2026-11-26 11:45:10, so the
instance the owner loads is older than this tree. A lane does not put the app on his
screen; the runtime verdict is his restart away.
