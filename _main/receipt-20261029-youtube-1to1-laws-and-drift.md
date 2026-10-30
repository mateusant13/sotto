# receipt 20261029 — YouTube 1:1: as LEIS (Bend 2), o falsificador do DRIFT, e os mirrors do caminho vivo

Lane: `herdr-lane` (H:/sotto). Owner order 2026-10-29, verbatim:
*"le a bend/README.md primeiro -- LAWS.bend e PROOF.bend para as decisoes puras, mais um falsificador
medido para o orcamento de tempo (a latencia/sync nunca e uma lei -- precisa de um falsificador
medido, e `drift_ms` medido, nunca um booleano 'synced')"*.

**Scope of this receipt.** The four owner-named elements of the 1:1 path (words, line breaks, timing,
word-by-word reveal), each measured against the artefact that records what YouTube's OWN player did.
This receipt covers the parts this lane owns: the Bend law bundle and its gate, the drift falsifier,
the reveal mirror, and the battery wiring. The rows/breaks production fix and its oracle were
authored by sibling lanes and are cited here as measured facts, with their own receipts.

**No window was opened, no app was launched.** Every command below is a pure-python process or the
`bend` CLI inside the WSL distro `ubuntu-bend`. The owner order `SOTTO_NEVER_ON_OWNER_SCREEN` is
obeyed literally: there is not one screenshot and not one app launch in this lane.

---

## 1. THE STATE BEFORE THIS LANE (re-measured, not quoted)

The receipt `_main/receipt-20261026-youtube-1to1-check.md` closed with one RED (`word-reveal-1to1`).
Re-measured 2026-10-29, the static oracle is GREEN on all seven elements — but that oracle compares
the PAYLOAD against the SERVED CUES. It cannot see the live path, and the live path was broken:

```
python _main/youtube-1to1-oracle.py
YOUTUBE-1TO1 VERDICT GREEN     (7 elementos, 0 vermelhos)
```

**The defect the static oracle could not see** (measured, in `app/webview/sotto_webview.py`, the
`painted` branch of `_youtube()`): the window was built with the cue's **start**, not the player's
clock:

```python
lines = self._yt_lines(track, float(hit.get('cue', {}).get('start') or 0.0) + 0.001)
```

`revealed_lines(cues, t)` cuts each line by the words' `tOffsetMs`, so with `t = cue.start + 0.001`
only the **first** word passed and the line **never grew on screen**. Measured directly:
`revealed_lines(cues, cue0.start+0.001) -> ['Have']` against
`revealed_lines(cues, cue0.start+1.000) -> ['Have you ever had to kill']`.

Why the static oracle was blind: its `reveal-wired` arm checks that `revealed_lines` is **called**.
It is. The clock passed to it was wrong. "The call exists" is not "the behaviour is right".

---

## 2. THE FIX, AND THE MIRROR THAT PROVES IT

### 2.1 Production

`app/webview/youtube_reveal.py` (NEW file, 294 linhas) holds the window rule, and
`app/webview/sotto_webview.py`'s `painted` branch calls it:

```python
lines = youtube_reveal.window_by_paint(track.get('cues') or (), hit)
```

The rule in one line: **the number of words revealed comes from what the player already painted**,
not from an estimated clock. `align_painted` returns `from_index` (the first cue of the matched
run), `index` (the cue being painted) and `painted_from` (the word offset inside it); those three
numbers ARE what the player has on screen.

**This is 1:1 by construction** — there is no guessed delay and no estimated timestamp in the
branch. The chosen clock (painted words rather than the video clock) is deliberate and measured: the
player's clock can be **frozen** (measured 2026-10-20: +0.00 s in 8.35 s of wall clock), and the
`painted` branch was drawn not to depend on it.

### 2.2 The mirror — `_main/youtube-reveal-oracle.py`

The mirror calls the **production functions** (`youtube_captions.align_painted` and
`youtube_reveal.window_by_paint`), not a reimplementation, and compares the window against the rows
YouTube's own player painted, recorded in
`_main/fixtures/yt-WdaHAGRBB6s.break-position-20261026.json`.

```
python _main/youtube-reveal-oracle.py
EXIT=0
```

```
elemento                       veredicto  medicao
reveal-matches-the-player      GREEN      linhas iguais: 15/15
cobertura                       PARCIAL    15/16 amostras medidas (0 sem cues vivos, 1 sem alinhamento de 3 palavras)
the-old-clock-was-broken       GREEN      a janela antiga tambem batia: 2/15
wiring-is-live                 GREEN      a janela pelas palavras pintadas esta ligada
```

**The negative arm** delays the paint by one word and MUST go RED:

```
python _main/youtube-reveal-oracle.py --neg-arm
EXIT=1
NEG-ARM PASS (a janela ja nao batia com o atraso)
```

### 2.3 A DEFECT FOUND IN THE INSTRUMENT ITSELF (measured 2026-10-29)

The reveal oracle was **RED** when this lane picked it up (`8/10`), and the RED was partly a defect
**in the instrument**, not only in the production. Two causes, both now fixed and both recorded
here because an instrument that lies is worse than no instrument:

1. **The oracle rebuilt the `hit` by hand.** Its `hit_from_player` produced a hit **without
   `from_index`**, and without `from_index` the production window can never reconstruct the row
   that is scrolling out — the third row the player still shows. The oracle therefore measured
   something the production does not do. It now calls the production `align_painted`.
2. **The oracle passed a cue SUBSET** (`sub = [cues[i] for i in indexes]`) to `window_by_paint`,
   while the production hit's `index`/`from_index` are indices into the **full** track. The two
   index spaces disagreed. The mirror now passes the full track, as production does.

The `>>` speaker marker is **kept on both sides** (the payload has `'>> No.'` and the player paints
`'>> No.'`); stripping it on one side only is what made an earlier variant of this analysis report
six phantom divergences. That was my measurement error, and it is recorded rather than quietly
dropped.

**Coverage is reported, not hidden.** 15 of 16 samples are measured. The one that is not is
`t=0.023 s`, where the player had painted a **single** word and the production alignment needs
`ALIGN_MIN_EXACT = 3` matched words — production has no alignment at that instant either. The
oracle counts and prints it (`cobertura ... 15/16`), because measuring a fraction and calling it a
measurement is the vacuity this repo keeps fighting.

---

## 3. THE LINES AND THE BREAKS (sibling lane; measured here, receipt cited)

The rows/breaks production fix and its oracle were authored by the `YoutubeRows` and `YoutubeRows-2`
lanes. Their receipt: `_main/receipt-20261029-youtube-rows-and-breaks.md` (and the lane-2 file
beside it). Re-measured **in this lane**, on the tree as it stands:

```
python _main/youtube-rows-oracle.py
EXIT=0
SUMMARY samples=16 rows_match=16/16 draw_match=16/16 rows_different=0 draw_different=0 clipped=0
BREAKS  dom_match=16/16 dom_draw_match=16/16 text_match=16/16 breaks_match=16/16 older_row=4/4 shape=16/16
YOUTUBE-ROWS GREEN
```

```
python _main/youtube-rows-oracle.py --neg-arm        EXIT=1
python _main/youtube-rows-oracle.py --neg-arm draw   EXIT=1
```

**What was broken** (measured 2026-10-26, receipt
`_main/receipt-20261026-break-position-is-the-failing-element.md`): the **position** of the line
break diverged in **12 of 16** samples. The cause: `caption_wrap.wrap` splits on whitespace, so a
`"\n"` inside the text is destroyed and the line is re-wrapped at a different word than YouTube's —
and our wrap width (`budget_px` = 714.0 px at 1280/1920/2560) is not YouTube's, so re-wrapping can
never agree. The fix carries the player's own rows, with their breaks, through the whole path
(`rows_text` -> `push_caption_to_window` -> the `"\n"` that `caption_overlay._layout` respects
without re-breaking).

**What is still not proven** (stated by the sibling lanes and repeated here so the next reader hits
it): the owner's actual pixels; the live player/UIA; a run starting mid-cue (`off0 > 0`); a row
wider than the plate (the clip path); other videos and languages; the clock branch (`_yt_lines`),
which has no rollup because there is no painted word to anchor it.

---

## 4. THE TIMING BUDGET — A MEASURED FALSIFIER, NOT A LAW

**A latency/sync budget is never a law.** A law proves an ORDERING; it cannot prove a millisecond.
The budget is measured by `_main/youtube-drift-oracle.py` (authored by the `YoutubeDrift` lane;
receipt `_main/receipt-20261029-youtube-drift.md`; re-measured here).

```
python _main/youtube-drift-oracle.py
EXIT=0
```

```
cue=1 row=Have drift_ms=+23 observed_ms=22.8 ref_ms=0.0
cue=1 row=Have you ever had drift_ms=+132 observed_ms=772.3 ref_ms=640.0
...
SUMMARY n=16 min_ms=+23 max_ms=+704 mean_ms=+172.5 median_ms=+107.2
payload nunca observado: 12/19 linhas (fora da janela das amostras): cues 8..19
CONVENCAO drift_ms negativo = player adiantado = a nossa revelacao TARDE
YOUTUBE-DRIFT VERDICT MEASURED (rc=0)
```

**There is no boolean "synced" anywhere in this lane's output.** The tool prints `drift_ms` per row,
signed, with its mean and median, and names its own limits.

**Two honesty notes, both kept visible:**

* **The sign convention is stated, not assumed.** `drift_ms = observado - referencia`; therefore a
  NEGATIVE drift means the player showed the row *before* its own payload says — our reveal is
  LATE. The lane that wrote the instrument flagged that a gloss in the brief had the sign inverted
  relative to the formula; the formula was kept and the derived convention printed.
* **The +704 ms maximum is sampling-limited, not a measured regression.** The sample grid runs
  637–849 ms and the capture covers only 0.02–10.19 s of a 33.84 s payload, so **12 of the 19
  payload cues were never observed**. The instrument prints that line. A regression in the second
  half of the video would pass this instrument untouched — that is the honest limit of the capture,
  and a fresh capture is the fix, not a different number.

**The falsifier must be able to say NO:**

```
python _main/youtube-drift-oracle.py --neg-arm
EXIT=1
```

It injects **+250 ms** into the payload reference; every one of the 16 drifts moves by exactly
−250 ms (mean +172.5 -> −77.5) and the arm names the offset. A detection miss would exit 3.

---

## 5. THE LAWS — `bend_core/LAWS.bend` + `bend_core/PROOF.bend`

### 5.1 What is proven and what is not

The laws cover the **pure decisions** of the 1:1 path, over a model of the same three decisions the
production makes:

| law | the decision it pins |
|---|---|
| `Nat.revealed_flag_is_zero_or_one` | the "the word has arrived" indicator is a BOOLEAN, not a duration |
| `Nat.of_bool_agrees_with_revealed_flag` | the two shapes of that indicator (`match` vs `Bool.pick`) compute the same thing |
| `Toks.count_due_counts_only_due_words` | the revealed count never exceeds the number of words |
| `Toks.count_due_of_an_empty_line_is_zero` | an empty line reveals nothing |
| `Toks.count_due_of_one_word_is_its_flag` | a one-word line's count IS that word's indicator |
| `Toks.count_due_is_monotone_in_time` | revealing later never reveals fewer |
| `Nat.live_flag_is_started_and_not_ended` | a line is alive iff it started and has not ended |
| `Nat.live_flag_is_false_before_the_line_starts` | a line that has not started is not alive |
| `Nat.window_rows_is_the_minimum` | the window is `min(capacity, live rows)` |
| `Nat.window_rows_never_exceeds_the_capacity` | the window never exceeds `rcRows` |
| `Nat.window_rows_never_exceeds_the_live_rows` | the window never invents rows |

**What these laws do NOT prove, and this receipt does not claim:**

1. **Not the timing budget.** A law proves an ORDER. The budget is §4, measured in `drift_ms`.
2. **Not the pixels on the owner's screen.** The laws prove the DATA. What is drawn is §2 and §3,
   measured by mirrors that call the production functions.
3. **Not the intent behind the claim.** A law certifies a statement over a model.

**The premise that is not proved here, stated where the next reader hits it:** the model's word list
is assumed to be in **increasing `at_ms` order**. That is a PREMISE supplied by the caller — the
`parse_json3` produces that order and `youtube_captions.py` checks it — and it is not proved here,
because proving the ordering of a list would need an ordered-list type the model does not carry. The
law is TRUE over ordered lists; its applicability to production is fixed by the MIRROR (§2), which
runs the production function over the real payload.

### 5.2 The gate

`_main/bend-laws-gate.py` is the gate the battery calls. It runs `bend PROOF.bend --verdict` inside
the WSL distro `ubuntu-bend` and enforces **six typed exit codes**, because a gate that answers 0 or
1 cannot tell "the law is false" from "the gate did not run":

| rc | meaning |
|---|---|
| 0 | every law checks AND every negative control fails naming the law it was written to falsify |
| 2 | a law did not check (the proof is wrong) |
| 3 | a negative control misbehaved (checked, or failed without naming its law) |
| 4 | INFRASTRUCTURE (WSL / bend / verdict / kernel unavailable) — **never** "the law is false" |
| 5 | the law inventory drifted from the pinned list |
| 6 | a tamper probe misbehaved (a gutted proof still checked) |

`--check-only` is **never** used as a gate: it runs no proof and prints `ALL PROOFS CHECK` on a file
the kernel rejects (upstream #1897, #1896). The gate is `--verdict`, and it prints the `bend` and
`lean` versions because kernel acceptance widens between patch releases (#1892) — a log that says only
"green" cannot tell "the laws still hold" from "the kernel now accepts more".

**The negative controls.** Eleven files, `bend_core/NEGATIVE_*.bend`, one FALSE claim each (the
kernel stops at the FIRST failing law, so two false claims in one file would leave the second
unexercised). Each names the law it falsifies, and the gate requires the failure to carry that
exact name — a parse error is not a counterexample. **Measured 2026-10-29, all eleven:**

```
NEGATIVE_count_due_empty.bend        rc=1  Location: Toks.count_due_of_an_empty_line_is_zero
NEGATIVE_count_due_monotone.bend     rc=1  Location: Toks.count_due_is_monotone_in_time
NEGATIVE_count_due_one_word.bend     rc=1  Location: Toks.count_due_of_one_word_is_its_flag
NEGATIVE_count_due_only.bend         rc=1  Location: Toks.count_due_counts_only_due_words
NEGATIVE_live_flag.bend              rc=1  Location: Nat.live_flag_is_started_and_not_ended
NEGATIVE_live_flag_before.bend       rc=1  Location: Nat.live_flag_is_false_before_the_line_starts
NEGATIVE_of_bool_agrees.bend         rc=1  Location: Nat.of_bool_agrees_with_revealed_flag
NEGATIVE_revealed_flag.bend          rc=1  Location: Nat.revealed_flag_is_zero_or_one
NEGATIVE_window_rows_capacity.bend   rc=1  Location: Nat.window_rows_never_exceeds_the_capacity
NEGATIVE_window_rows_live.bend       rc=1  Location: Nat.window_rows_never_exceeds_the_live_rows
NEGATIVE_window_rows_min.bend        rc=1  Location: Nat.window_rows_is_the_minimum
```

**The tamper probes.** A green verdict on the file AS WRITTEN cannot see a proof **deleted** or a
proof body **emptied** (a proof of a weaker statement is still a proof). The gate builds two changed
copies and requires both to fail: one with a proof def deleted, one with a proof body replaced by
`{==}`.

### 5.2b The model in Python — `bend_core/model.py`

The same model, the same sample, in Python, for a host without the Bend toolchain, and so that a
reader can check the number a law constrains without installing anything.

```
python bend_core/model.py
EXIT=0
MODELO (model.py) -- a MESMA amostra, em Python
casos verificados: 1090
todas as leis da amostra respeitadas
NOTA: isto e uma AMOSTRA, nao uma prova. A prova e `bend PROOF.bend --verdict` (o kernel), e o portao e `_main/bend-laws-gate.py`.
YOUTUBE-LAWS-MODEL VERDICT GREEN (amostra)
```

```
python bend_core/model.py --neg-arm
EXIT=1
NEG-ARM PASS: o modelo quebrado viola 4 lei(s): Nat.live_flag_is_started_and_not_ended,
  Nat.of_bool_agrees_with_revealed_flag, Nat.revealed_flag_is_zero_or_one,
  Toks.count_due_counts_only_due_words
```

**This file is NOT the gate**, and its own output says so. A sample is not a proof: the kernel
proves over ALL inputs. It exists so the model is legible without the toolchain, and its neg-arm
exists so a reader can see that the checker can say NO.

### 5.3 The Bend semantics this bundle had to obey — all MEASURED, not assumed

`bend 2.0.39`, Lean 4.34.0, WSL distro `ubuntu-bend`. Each of these was seen as an error message
while writing the bundle:

1. **No `if`.** `match` on `True{}`/`False{}`, or `Bool.pick(Type, cond, a, b)` — which **does**
   accept a computed condition.
2. **No mutual recursion, and a def may only call a def defined EARLIER** (or itself).
   "expected : a filled definition" means the callee is later in the file. Helpers go BEFORE their
   callers; each recursion lives in one def.
3. **Affine:** a value may be used only once — "expected : b, observed : b (consumed more than
   once)". This applies to parameters AND to pattern-bound variables. The fix is the `+` (erased)
   marker, and the erasure **propagates from the law's binder to the proof def's parameter**.
4. **A `match` cannot scrutinize a COMPUTED value** ("give it its own def") — but it CAN scrutinize
   a parameter or a pattern-bound variable.
5. **A `match` cannot scrutinize a hypothesis**: `match h:` on `h : {X == True{} : Bool}` gives
   "expected : a datatype". The recipe is to match the underlying `Bool` and discharge the
   impossible arm with `Empty.elim(..., Bool.absurd_false_true(h))`.
6. **A def with no return type fills a law**; the law must be declared `law Laws.<name>:` for
   `def Laws.<name>(...)` to fill it. A helper needs an explicit return type and typed params.
7. **Recursion must be visibly decreasing** ("arguments are read left to right: each passed
   unchanged until one shrinks") — the hypothesis has to shrink too.
8. **Operators need annotation:** `(a + b : Nat)`.
9. **Base's `List<a>` needs a `Quant` kind argument**, unusable for a `Data` type — hence the
   model's own list type.
10. **The law's statement codomain must match:** `... == 0n : Nat` is a `Nat` equality, and
    `... == True{} : Bool` is a `Bool` equality. Mixing them is a type error, not a proof failure.

These are written into `bend_core/LAWS.bend`'s header, because the next person to write a law will
hit every one of them again.

### 5.4 The law gate — the final command

```
wsl -d ubuntu-bend -e bash -lc 'export PATH=/root/.bend/bin:$HOME/.elan/bin:$PATH; cd /mnt/h/sotto/bend_core && bend PROOF.bend --verdict'
ALL PROOFS CHECK
RC=0
```

```
python _main/bend-laws-gate.py
EXIT=0
== bend: bend 2.0.39 ==
PASS: every law in LAWS.bend checks (proofs in PROOF.bend).
PASS: law inventory matches the pinned 11 laws.
PASS: LAWS.bend alone reports its laws as open claims: Error: 11 TODOs found.
PASS: negative control NEGATIVE_revealed_flag.bend fails on Nat.revealed_flag_is_zero_or_one, as it must.
PASS: negative control NEGATIVE_of_bool_agrees.bend fails on Nat.of_bool_agrees_with_revealed_flag, as it must.
PASS: negative control NEGATIVE_live_flag.bend fails on Nat.live_flag_is_started_and_not_ended, as it must.
PASS: negative control NEGATIVE_live_flag_before.bend fails on Nat.live_flag_is_false_before_the_line_starts, as it must.
PASS: negative control NEGATIVE_window_rows_min.bend fails on Nat.window_rows_is_the_minimum, as it must.
PASS: negative control NEGATIVE_window_rows_capacity.bend fails on Nat.window_rows_never_exceeds_the_capacity, as it must.
PASS: negative control NEGATIVE_window_rows_live.bend fails on Nat.window_rows_never_exceeds_the_live_rows, as it must.
PASS: negative control NEGATIVE_count_due_only.bend fails on Toks.count_due_counts_only_due_words, as it must.
PASS: negative control NEGATIVE_count_due_monotone.bend fails on Toks.count_due_is_monotone_in_time, as it must.
PASS: negative control NEGATIVE_count_due_empty.bend fails on Toks.count_due_of_an_empty_line_is_zero, as it must.
PASS: negative control NEGATIVE_count_due_one_word.bend fails on Toks.count_due_of_one_word_is_its_flag, as it must.
PASS: tamper probe A (a deleted proof) is detected.
PASS: tamper probe B (an emptied proof) is detected.
== bend gate green ==
```

**The proofs are not vacuous.** All eleven proof bodies were checked against the trivial shape
(`{==}` alone, which would prove anything); **none** is trivial — every one is either a real
induction, a multi-arm case split, or a lemma chain. The four hardest (`count_due_counts_only_due_words`,
`count_due_of_one_word_is_its_flag`, `count_due_is_monotone_in_time`, `window_rows_is_the_minimum`)
are proved over a Nat toolkit that had to be built first:

* `le_0_l` — `0 <= b` for every `b`.
* `le_trans` — transitivity of `<=`, with the two impossible arms discharged through
  `Bool.absurd_false_true` and `Empty.elim` (the technique the whole file reuses).
* `le_1_r` — `a <= 1 + a`.
* `pick_succ` — `Bool.pick` commutes with a successor.
* `flag_mono` — **the indicator is monotone in the clock**: if `t1 <= t2`, a word's flag can only
  go 0 -> 1, never 1 -> 0. Eight arms, because `Nat.is_le` needs BOTH arguments known to compute.
* `flag_add_mono`, `flag_add_le` — sums of indicators, with the affine erasure (`+c2`, `+l`) that
  Bend demands when a value appears twice.
* `min_le_l`, `min_le_r` — `min(a, b) <= a` and `min(a, b) <= b`.

**The laws name what they REJECT**, and each `# REJECTS:` clause names a real implementation the
law excludes — an indicator returning the *difference* `t_ms - at_ms`, a liveness that ignores the
end of the line, a window that shows `capacity + 1`. The eleven negative controls are those
rejects, one false claim each.

**One premise is stated and NOT proved here:** the model's word list is assumed to be in
increasing `at_ms` order. That premise is supplied by the caller (`parse_json3` produces it, and
`youtube_captions.py` checks it); it is not proved in the bundle, because proving the ordering of
a list would need an ordered-list type the model does not carry. The law is TRUE over ordered
lists; its applicability to production is fixed by the MIRROR (§2), which runs the production
function over the real payload.

---

## 6. THE BATTERY

Four new steps in `_main/_audit-verify-all.cmd`, each with its RED control:

| step | what it proves | control |
|---|---|---|
| `youtube-reveal` | the live window equals the player's rows (15/15) | `red-as-expected-youtube-reveal` |
| `youtube-rows` | the rows and the BREAK POSITION (16/16, clipped=0) | `red-as-expected-youtube-rows` |
| `youtube-drift` | the timing, in `drift_ms` (never a boolean) | `red-as-expected-youtube-drift` |
| `bend-laws` | the laws check, the controls fail, the tamper probes fire | (the gate carries its own controls) |
| `bend-laws-model` | the model in Python respects the laws on the explicit sample | `red-as-expected-bend-laws-model` |

All five are `always` (never cached): they read the LIVE proof state and the live fixtures, and a
cached result would describe a state that no longer exists.

**The pin moved, and it moved for a reason.** `_main/_audit-verify-all.cmd` is now **132069 B,
1728 CRLF / 0 bare LF, sha256 `75C94485C242480988AD3C0DD7F3E84C00290FE2BB8AFB084AAAF654B9AA5916`**,
and `AGENTS.md` carries those numbers:

```
python _main/agents-md-pins-oracle.py
AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)
VERDICT: PASS
EXIT=0
```

```
python _main/agents-md-pins-oracle.py --neg-arm
AGENTS-PINS CONTROL PASS
EXIT=0
```

---

## 7. THE CODE-HEALTH RATCHET

`_main/code-health-oracle.py` was **already RED** before this lane (12 metrics), and it is RED
after, with the **same 12 metric pairs** — no new RED was introduced by this lane. The files this
lane touched:

* `app/webview/youtube_reveal.py` — **NEW** (no baseline entry, so no ratchet movement).
* `app/webview/sotto_webview.py` — already RED before (758679 -> 772492 B), edited by the rows lane.
* `app/webview/caption_overlay.py` — 51371 -> **51362 B** (the rows lane's `splitlines` change made
  it SMALLER; the file has zero slack in the ratchet, so a smaller file is not a regression).
* `app/webview/caption_wrap.py` — **untouched** (20049 B).

The pre-existing REDs belong to `sotto_webview.py`, `youtube_captions.py`, `youtube_window.py` and
`worker/sotto_worker.py` — the last one is another lane's file.

---

## 8. SELF-AUDIT

- **protocolos em falta:** none outstanding in this lane. The `bend-laws-gate.py` gate and the
  three oracles were all written and run in this lane; the rows/breaks production fix and its
  oracle came from sibling lanes and were **re-measured here** rather than quoted.
- **verificacao adicional:** every oracle was run in BOTH arms in this lane (positive and
  `--neg-arm`), and the drift oracle's numbers were recomputed from the fixtures rather than
  copied from the sibling's receipt. The reveal oracle's `>>`-marker handling was re-derived after
  my own measurement error, and the error is recorded in §2.3 rather than dropped.
- **checkboxes novas:** `python _main/youtube-reveal-oracle.py` (expect 0) and `--neg-arm` (expect 1);
  `python _main/youtube-rows-oracle.py` (expect 0) and `--neg-arm` (expect 1);
  `python _main/youtube-drift-oracle.py` (expect 0) and `--neg-arm` (expect 1);
  `python _main/bend-laws-gate.py` (expect 0). All four pairs are now wired into
  `_main/_audit-verify-all.cmd` as `always` steps with their RED controls.
- **review por outro subagente:** the `hit` construction in the reveal oracle and the `drift_ms`
  sign convention were both reviewed by sibling lanes; the reveal-oracle defect in §2.3 was found by
  cross-reading the two sibling receipts (the `YoutubeRows-2` lane reported the same contradiction
  from the other side) and adjudicated here.
- **gate-doubt:**
  - **verde-de-verdade:** every green in this receipt has a paired RED arm that fails for the
    stated reason (the law it names, the offset it injects, the word it delays). The bend gate's
    green additionally rests on eleven named controls and two tamper probes.
  - **falta-no-gate:** the drift instrument only covers 0.02–10.19 s of a 33.84 s payload (12 of 19
    cues unobserved) and its sample grid is 637–849 ms, so a regression in the second half of the
    video passes it untouched. Nothing here tests the owner's actual pixels, because the app was
    never launched (owner order).
  - **gate-melhor:** a capture that covers every cue (>=1 sample inside each) with a tighter grid
    would turn the drift instrument from "sampling-limited" into "covering"; until then the
    instrument must keep printing the uncovered-cue line, and it does.
- **confianca:** alta for the law bundle (kernel-checked, with named controls), alta for the reveal
  and rows mirrors (they call the production functions and the neg arms fire), media for the timing
  (the capture is coarse and partial), nenhuma for the pixels (never launched).
- **nao verificado:** the owner's screen; the live player and UIA; other videos and languages; the
  clock branch (`_yt_lines`), which has no rollup; a row wider than the plate; a run starting
  mid-cue; the non-YouTube caption path, whose `\n` now has a meaning in the overlay.

## CACHE/PRICE

`cache`/`price`/`when-failed`/`where-failed`: **UNKNOWN** for this lane's own turns — the ledger
(`I:\!manager\.agents\usage\`) has no usage row whose identity matches this lane's seat. The two
sibling lanes reported their own rows (both `$0.00000000`, one cache miss on `YoutubeRows-2` at
2026-10-29T08:17:20.540Z, message_id=20c2a63d). Nothing here is quoted from the ledger that was
not measured.

---

# ADDENDUM 2026-10-30 (a ordem seguinte, do mesmo dono)

O dono deu uma ordem NOVA no dia seguinte, e a 2026-10-30:

> *"faz sotto identificar palavras que ainda nao estao completas e nao dar
> display. nunca vai dar display por exemplo em 'so' sem esperar virar 'sou'. em
> qualquer lingua"*

**O recibo dessa ordem e o `_main/receipt-20261030-incomplete-word.md`** (e
deliberadamente um ficheiro separado: a ordem de 2026-10-29 foi sobre o
caminho 1:1 do YouTube, e esta e sobre a palavra que ainda nao esta
provada -- decisoes diferentes, com instrumentos diferentes).

O que muda em relacao a este recibo:

1. **O `_main/youtube-sotto-drift-oracle.py` foi CORRIGIDO e WIRADO.** O
   ficheiro ja existia, mas media uma tautologia (`drift_sotto_ms = +0.0 ms`
   SEMPRE, zero por construcao), lia o relogio do payload no campo errado
   (`tOffsetMs`/`w`, quando o `parse_json3` devolve `start`/`text`), e
   emparelhava por PALAVRA em vez de por OCORRENCIA (desvios de -26 s).
   Corrigido: `drift_sotto_ms` = -125.0 ms (mediana -74.0),
   `drift_player_ms` = +125.0 ms, e o `--neg-arm` rc=1 com o atraso injectado
   a aparecer. Ver o §8 do recibo de 2026-10-30.

2. **O `git stash` REVERTEU A ARVORE INTEIRA** e a recuperacao foi feita
   ficheiro a ficheiro com `git checkout stash@{N} -- <path>`. Os ficheiros
   que tinham de voltar do `stash@{0}`:
   `worker/sotto_worker.py`, `app/panel/panel.js`,
   `app/panel/caption-formulation.js`, `app/webview/sotto_webview.py`,
   `app/webview/youtube_captions.py`, `app/webview/caption_overlay.py`,
   `AGENTS.md`, `_main/_audit-verify-all.cmd`.
   **REGUA:** nao usar `git stash` / `git stash pop` neste repo.

3. **OS DOIS DEFECTOS DE INSTRUMENTO QUE ESTE RECIBO JA MENCIONAVA** (o
   gerador vazio `any([])` e o detector de codigo-vs-comentario) foram
   ambos resolvidos; o detector do relogio antigo passou a ser uma PASSAGEM
   DA AST (le o codigo, nao o comentario), e o oratorio da revelacao
   chama a `align_painted` de PRODUCAO com a lista COMPLETA de cues.

4. **O PIN do `.cmd` mudou** (a regra do repo: re-medir depois de cada
   edicao do `.cmd`). O valor actual esta no `AGENTS.md`:
   **135712 B, 1777 CRLF, sha256
   `F05027472377B036C1F7281216B38DC3589125E9CC653733DE5D32848D33289A`**.

### 5.2c The SAME gate, as a shell script — `tools/bend_verify.sh`

Ported from `I:/!manager`'s authoritative bundle + the consultgpt implementation on 2026-10-30,
because `_main/bend-laws-gate.py` is a PYTHON entry point and the fleet's mandated gate is the shell
one the other lanes run (`bend_verify.sh` + `bend_proof_ledger.py`, the pair whose watched-file list
makes a proof edit impossible to land unnoted). Both entry points run the SAME assertions; neither
replaces the other, and the ledger proves it by hash.

```
$ bash tools/bend_verify.sh
== bend laws gate (native: /usr/local/bin/bend) ==
ALL PROOFS CHECK
PASS: every law in LAWS.bend checks (proofs in PROOF.bend).
PASS: negative control NEGATIVE_count_due_empty.bend fails on Toks.count_due_of_an_empty_line_is_zero, as it must.
PASS: negative control NEGATIVE_count_due_monotone.bend fails on Toks.count_due_is_monotone_in_time, as it must.
PASS: negative control NEGATIVE_count_due_one_word.bend fails on Toks.count_due_of_one_word_is_its_flag, as it must.
PASS: negative control NEGATIVE_count_due_only.bend fails on Toks.count_due_counts_only_due_words, as it must.
PASS: negative control NEGATIVE_display_clean_before_new_source.bend fails on Cap.display_clean_before_new_source, as it must.
PASS: negative control NEGATIVE_epoch_monotonic.bend fails on Cap.epoch_monotonic, as it must.
PASS: negative control NEGATIVE_live_flag.bend fails on Nat.live_flag_is_started_and_not_ended, as it must.
PASS: negative control NEGATIVE_live_flag_before.bend fails on Nat.live_flag_is_false_before_the_line_starts, as it must.
PASS: negative control NEGATIVE_no_cross_source_paint.bend fails on Nat.no_cross_source_paint, as it must.
PASS: negative control NEGATIVE_of_bool_agrees.bend fails on Nat.of_bool_agrees_with_revealed_flag, as it must.
PASS: negative control NEGATIVE_revealed_flag.bend fails on Nat.revealed_flag_is_zero_or_one, as it must.
PASS: negative control NEGATIVE_window_rows_capacity.bend fails on Nat.window_rows_never_exceeds_the_capacity, as it must.
PASS: negative control NEGATIVE_window_rows_live.bend fails on Nat.window_rows_never_exceeds_the_live_rows, as it must.
PASS: negative control NEGATIVE_window_rows_min.bend fails on Nat.window_rows_is_the_minimum, as it must.
PASS: law inventory matches the pinned 14 laws.
PASS: LAWS.bend alone reports its laws as open claims: Error: 14 TODOs found.
PASS: tamper probe A is detected (proof state is checked, not assumed).
PASS: tamper probe B is detected (proof state is checked, not assumed).
== gate green ==

$ py -3 tools/bend_proof_ledger.py
ledger: green rc=0 judge=bend 2.0.39 laws=14 -> .bend-ledger\runs.jsonl
```

**Correction to §5.2 above:** the control set is **fourteen** files, not eleven — the two families
added after that paragraph was written (`Cap.epoch_monotonic`, `Cap.display_clean_before_new_source`,
`Nat.no_cross_source_paint`) brought three more, and every one is now pinned by name to the law it
falsifies in `tools/bend_verify.sh`, so a control deleted without touching the pin fails the gate
(exit 3) instead of silently removing a falsifier.

**Two adaptations the port needed, both measured here:**

1. **The tamper probes name THIS tree's proofs.** The upstream probe mutates
   `Laws.choose_the_candidate_that_exists`; sotto has no such law. Probe A now replaces the
   `{==}` of the `(True{}, True{})` arm of `Laws.Nat.live_flag_is_started_and_not_ended` with
   `False{}`, and probe B guts `Laws.Cap.epoch_monotonic`. Both are required to fail AT the law
   (`Location: Laws.<name>`), which is what makes them read proof state rather than "the file
   stopped parsing".
2. **`lean` on PATH.** The native branch now exports `$HOME/.elan/bin` and `/root/.elan/bin`:
   measured 2026-10-30, a gate run from inside the distro printed `lean: command not found` while
   `bend` was on PATH at `/usr/local/bin`. The gate still passed (bend carries its own kernel), but a
   toolchain warning inside a green run is a lie the next reader has to re-investigate.

**What is still NOT proved:** the same three things §5 already says — the timing budget (the
falsifier's, `_main/youtube-drift-oracle.py`), the pixels on the owner's screen (the oracles'), and
the intent behind each claim.
