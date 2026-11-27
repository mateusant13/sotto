# Receipt — the test-quality auditor graded 9 % of this repo's test surface

**Date:** 2026-11-27
**Instrument:** `C:/Users/Administrador/.agents/skills/project-revival/scripts/test_quality_audit.py`
(Project Revival v4.4.0, the Layer-5 mechanical test-hygiene gate)
**Verdict:** genuine Goodhart failure in the instrument; fixed; the honest baseline is
**score 75 / verdict PASS** over **325 files / 594 test functions**.

## 1. The measurement that opened it

```
python .../test_quality_audit.py scan --repo . --json
  test_files = 34      total_tests = 22      test_quality_score = 90   verdict = PASS
```

Against this repo's actual population:

| surface | count |
|---|---:|
| `_main/*oracle*.py` files | **328** |
| `call :step` in `_main/_audit-verify-all.cmd` | **621** |
| oracle files that emit a `VERDICT` | **302** |

The auditor's own docstring names this exact failure mode — *"a green score over 12 % of
the test surface is the Goodhart failure this file exists to catch"* — and its file docstring
records fixing the same class for `-test.cjs` in another repo. `_main/*-oracle.py` was the
same blind spot here: `_is_test_file` knew `test_*.py`, `*_test.py` and any path containing
`tests`, and an oracle matches none of them.

## 2. The fix — discovery only, and both halves required

An oracle is a test file when **it names itself one AND actually emits a verdict**:

```python
if PY_ORACLE_NAME_RE.search(name):        # 'oracle' in the basename
    ...
    return bool(PY_VERDICT_RE.search(head))   # '\bVERDICT\b' in the file
```

Both halves are load-bearing: the name alone would grade a helper, a bare verdict string
alone would grade product code that merely logs the word.

Arm functions are then **counted** (`def arm*` / `def check*`) as test functions, so the
denominator is honest.

## 3. The three false metrics I did NOT ship

Extending `zero_assert` to arms produced **490** findings, then **480**, then **441** as I
widened the assertion regex — and every one I sampled was a legitimate arm. This repo's arms
assert in three forms:

| form | example | regex-visible |
|---|---|---|
| (a) `arm.check(cond, msg)` | `obj.check(painted == want, "...")` | with a helper pattern |
| (b) `failures.append("...")` | `_main/agents-md-pins-oracle.py:114` | with a `fails?` pattern |
| (c) **verdict-as-data** | `return ok, 'trimmed=%d ...'` (`_main/audio-ring-journal-oracle.py:66`) | **no** |

Style (c) is a pure function returning its verdict tuple for `main()` to judge. **A gate that
accuses who is right has lost its authority**, so `zero_assert` is deliberately NOT applied to
arms. Style (c) is covered by the stronger instrument this repo already runs: the
feature × angle matrix, where *a row whose neg arm cannot go red is a HOLE, not a pass*.

## 4. The honest baseline, measured

| metric | before | after |
|---|---:|---:|
| test files | 34 | **325** |
| test functions | 22 | **594** |
| score | 90 | **75** |
| verdict | PASS | **PASS** (75 ≥ 70) |
| zero_assert | 0 | **0** |
| vacuous_assert | 0 | 0 |
| object_new_bypass | 0 | **29** |
| unexpiring_skips | 0 | 0 |
| raw_sleep_calls | 2 | **187** |
| mutation_refs | 145 | **2299** |

The score DROPPED from 90 to 75 while the verdict stayed PASS. That is the correct direction:
the number now describes 325 files instead of 34.

## 5. What the new numbers mean (for the fix swarm)

- **29 `object.__new__` bypasses** — all in `_main/caption-*-oracle.py`. Verified samples:
  `_main/caption-drag-oracle.py:281` builds `NativeCaptionOverlay` with
  `object.__new__` and then sets `_drag_armed`/`_drag_dragging`/`_drag_canvas` by hand;
  `_main/caption-rollup-oracle.py:120` does the same for `_cue`/`_live`. That is Layer-1
  mock theater *unless* the real constructor opens a window — which the helper's own
  docstring (`"Um overlay SEM janela"`) claims. **Per-file judgement required.**
- **187 raw `time.sleep(`** — Layer-4 bans polling sleeps in unit tests.
- **0 property tests** (`@given` / `hypothesis`) across 594 test functions — Layer 3 is
  wholly absent.
- **2299 mutation references** — the RED-arm culture is strong; that is the one metric
  already in good shape.

## 6. Self-test still passes

```
python .../test_quality_audit.py --selftest   ->  {"selftest": "PASS", ...}   rc 0
```
