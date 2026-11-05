# Punctuation from prosody — measurement, normaliser, oracle

Lane `PunctFromProsody` · 2026-11-05 · worktree `H:\sotto` (no commit, no push)

**State: `UNWIRED`.** `worker/punctuation_prosody.py` exists and is exercised by the oracle
(`LIVE`), but nothing calls it: `worker/sotto_worker.py` was off-limits for this lane, so the
wiring into `join_fragments` (`sotto_worker.py:4276`) is main's step. Nothing was run against
the app, the model, or an audio device.

The owner's idea, verbatim: *"por que a gente nao normaliza as frases ou usa pontuacao de forma
inteligente? se tu notar a diferenca de timing de cada palavra ou token sei la, da pra presumir
pontuacoes. se tu notar um aumento de frequencia da voz ou volume ou qualquer coisa assim parecida,
pelas ondas sonoras ou sei la, da pra entender se é uma nova frase."*

Short answer: **timing works, pitch does not.** Silence length separates clause from sentence
boundaries cleanly on every clean fixture; the pre-gap pitch slope is a coin flip and must not be
used. Details and counts below.

---

## 1. Phase 1 — what the audio actually says

Reproduce with `python _main/punct-prosody-oracle.py --measure` (pure numpy, fixture WAVs only).

Method: linear resample to the worker clock (16 kHz), windows 25 ms, hop 20 ms, per-frame RMS and
zero-crossing rate, F0 by normalised autocorrelation peak (60–400 Hz, periodicity ≥ 0.30, parabolic
refinement). Gate = `max(noise_floor*3, 0.02*peak)` with `noise_floor` = median of the quietest 10 %
of frames. A pause is a below-gate run ≥ 80 ms. Slopes are fitted over the 150 ms before the gap,
**excluding frames already below the gate** (including them made every slope a measurement of the
silence ramp — first pass produced "f0 = 1022 dB/s" nonsense that this filter removed).

### 1.1 Per-file inventory

```
file                        dur_s   gate     n speech   lead   tail gaps_ms
pt-br-sample.wav            15.00  0.020    14  0.68    120    815 140 140 120 80 120 80 100 140 160 1100 100 160 80 80
ptbr-tts-01.wav              8.83  0.020     8  0.67    100    867 100 80 80 100 180 360 80 120
ptbr-tts-02.wav             13.60  0.020    10  0.68    100    871 120 80 100 80 240 100 100 80 100 80
ptbr-tts-03.wav              6.54  0.020     8  0.53    180    878 160 180 120 80 400 100 280 100
enus-tts-01.wav              6.96  0.020     4  0.63    120    773 80 420 80 100
enus-tts-02.wav              5.49  0.020     3  0.59    120    783 440 80 100
live-sample-cable-input.wav  30.10  0.078    44  0.17    180     15 200 140 600 460 80 180 2640 100 1080 800 100 100 80 120 700 140 180 120 80 100 80 100 240 220 220 100 260 960 260 80 100 80 180 280 120 260 80 160 140 120 180 180 100 180
```

Sources: `_main/pt-br-sample.wav` (= `fixtures/stack-compare/ptbr-radio-14s.wav`, owner's own radio
audio) and `_main/fixtures/stack-compare/unified-tts/*.wav`, whose `reference.json` carries
**authored** text with punctuation — hand-written, not another engine's output, so it is usable as
ground truth for *where the marks are* (not for whether the TTS paused there, which is what we are
measuring).

### 1.2 Gap histogram (91 inner gaps, 7 fixtures)

```
    80- 120 ms : 42 ##########################################
   120- 160 ms : 15 ###############
   160- 200 ms : 12 ############
   200- 250 ms :  5 #####
   250- 300 ms :  5 #####
   300- 400 ms :  1 #
   400- 500 ms :  4 ####
   500- 600 ms :  0
   600- 800 ms :  2 ##
   800-1000 ms :  2 ##
  1000-1500 ms :  2 ##
  1500-3000 ms :  1 #
  total inner gaps: 91
```

The 6 clean fixtures contribute 47: **41 below 250 ms, 5 in 250–600, 1 at 1100 ms.** The remaining
44 are the noisy cable capture (see §1.5).

### 1.3 The decisive table — each authored mark vs the gap at its position

Position proxy: gap start mapped linearly into the speech span (first to last above-gate frame),
compared with the mark's letter position in the authored text. Tolerance ±0.10 of the clip; the
worst observed residual among hits is 0.069, so the proxy is not the limiting factor.

```
  file             mark   expect band-gap ms    delta  nearest-any  verdict
  pt-br-sample.wav .       0.534        1100   -0.021         1100  hit
  ptbr-tts-01.wav  ,       0.455         360   -0.007          360  hit
  ptbr-tts-02.wav  ,       0.529        none        -          240  MISS
  ptbr-tts-03.wav  ,       0.417         400   -0.041          400  hit
  ptbr-tts-03.wav  ,       0.583         280   -0.004          280  hit
  enus-tts-01.wav  ,       0.593         420   -0.069          420  hit
  enus-tts-02.wav  ,       0.681         440   -0.057           80  hit
  -> commas with a 250-600 ms gap at their position: 5/6 ; periods with a >=600 ms gap: 1/1
```

Two-way contingency, same gaps and same marks:

```
  band        n  at-comma-pos  at-period-pos  no mark near
  short      41            6              1            34
  clause      5            5              0             0
  sentence    1            0              1             0

  COMMA RECALL: 5 of 6 (ptbr-tts-01 1/1, ptbr-tts-02 0/1, ptbr-tts-03 2/2,
                          enus-tts-01 1/1, enus-tts-02 1/1)
  CLAUSE PRECISION: 5 of 5 clause-band gaps sit at a comma position
  SENTENCE PRECISION: 1 of 1 sentence-band gaps sit at a period position
```

The 6 "short gaps near a comma position" are the ±0.10 proxy admitting neighbours, not commas: of
the 6 authored commas the *lowest* pause behind any of them is **240 ms** (ptbr-tts-02, the one
MISS), and no authored comma has less. The single sentence-band inner gap (1100 ms, pt-br-sample)
lands at 0.513 against an expected 0.534 — that is the boundary the model itself heard as
"…segunda-feira. Os moradores…" (`_main/ASR-TRUTH.md` §C), so it is an independently corroborated
sentence break, not a coincidence of the proxy.

Sentence-final pauses (trailing silence, measured on the same gate):

```
  pt-br-sample.wav   815 ms      ptbr-tts-01  867 ms      ptbr-tts-02  871 ms
  ptbr-tts-03.wav    878 ms      enus-tts-01  773 ms      enus-tts-02  783 ms
```

**6 of 6 sentence ends are ≥ 773 ms; no gap in the 6 clean fixtures falls between 441 and 772 ms.**

### 1.4 The falsifiable claim

> On clean speech, an inner silence of **250–600 ms marks a clause boundary** and an inner silence
> of **≥ 600 ms marks a sentence boundary**; silences **< 250 ms carry no punctuation information.**

Verdict with the counts:

* clause half — **5/6 commas have a 250–600 ms gap at their position, and 5/5 gaps in that band sit
  at a comma.** One comma (ptbr-tts-02) pauses only 240 ms, i.e. the claim is 5/6 recall, 5/5
  precision. **Supported.**
* sentence half — **1/1 inner sentence boundaries and 6/6 trailing sentence ends are ≥ 600 ms, and 0
  of the 47 clean inner gaps in 441–772 ms exist** to contradict it. **Supported, but on n = 1
  internal boundary** (only one fixture has a sentence break inside the clip); the trailing-silence
  row is the bulk of the evidence and it is a weaker test, since the end of a file is a sentence end
  by construction of the recording.
* the 200 ms floor — no authored comma sits below 240 ms, so a floor of 200 ms costs **zero**
  measured commas while still deleting commas with nothing behind them. **Supported.**

Honest scorecard: the timing signal is real and well separated (the smallest pause measured behind
any authored comma is 240 ms, and every clause-band gap is a comma), but the sentence claim rests on
one internal example plus six recording ends. Treat "≥ 600 ms = period" as plausible-strong, not
proven at clause-level strength.

### 1.5 What did not work

**Pitch.** Pre-gap F0 direction, clean fixtures only:

```
  short    clean n=41 | f0 rising= 9 falling=18 flat= 7 unknown= 7 | rms rising=4 falling=37
  clause   clean n= 5 | f0 rising= 3 falling= 2 flat= 0 unknown= 0 | rms rising=0 falling= 5
  sentence clean n= 1 | f0 rising= 0 falling= 1 flat= 0 unknown= 0 | rms rising=0 falling= 1
```

The 5 clean clause gaps are 3 rising / 2 falling — a coin flip — and no fixture contains a question
(0 `?` in all 6 authored references). **The correlation the owner asked about ("aumento de
frequencia da voz … pra entender se é uma nova frase") is not there in this data**, so the module
does **not** convert a rising F0 into `?`: there is nothing to convert it *from* and no evidence
what a rising pre-gap slope means. `?` produced by the model is never touched. `f0_slope` is still
carried in the `pauses` contract (main will have it for free from the same features) but the module
ignores it — see the module docstring.

**Energy.** Falling RMS slope is present at 37 of 41 short gaps too, so it does not discriminate
either. The module does not use `rms_slope` for anything.

**The noisy live capture.** `live-sample-cable-input.wav` has RMS p50 = 0.077 against a gate of
0.078 and only 17 % voiced frames: `max(noise_floor*3, 0.02*peak)` puts the gate *at the median*, so
all 44 detected "gaps" are noise dips (600, 700, 800, 960, 1080, 2640 ms — five of them would be
called sentence ends). **This is the main wiring risk**: on a cable/AGC'd signal the gate must be
re-derived (or the features taken post-denoise) before `normalise` is fed real pauses, otherwise it
will insert periods into continuous speech.

---

## 2. Phase 2 — `worker/punctuation_prosody.py`

One entry point, `normalise(text, pauses)`; stdlib only (`re`), no I/O, no state, no numpy needed.
`pauses[i]` = silence in ms **after** the i-th whitespace token; entries may be numbers or dicts
(`{"ms": ..., "f0_slope": ..., "rms_slope": ...}`). `len(pauses) == tokens-1` covers the inner
boundaries; one extra entry is the trailing silence.

| rule | code | measured number behind it |
|---|---|---|
| drop a trailing `,` when the pause behind it is < 200 ms | `DROP_FLOOR_MS = 200.0` | lowest pause behind any authored comma = 240 ms; 41 of 47 clean gaps are < 250 ms and 34 of them are nowhere near a mark |
| append `,` when the pause is 250–599 ms | `CLAUSE_MIN_MS = 250.0` | 5/5 clause-band gaps sit at a comma, 5/6 commas have a clause-band gap |
| append `.` when the pause is ≥ 600 ms | `SENTENCE_MIN_MS = 600.0` | no clean gap lies in 441–772 ms; 600 ms is the midpoint of that empty region, and 599/600 is tested as a band edge |
| append `.` at the trailing boundary when the trailing silence is ≥ 600 ms and only if `pauses` supplies that entry | rule 3 | 6/6 trailing silences measured 773–878 ms |
| never drop `.` `?` `!` `;` `:` (only `,`) | `_DROPPABLE = ","` | the failure being fixed is comma spam; a wrong period did not appear in any live sample |
| never two marks in a row, never before an existing mark | `_TERMINALS` checks on both sides | prevents `,,` and `.,` at the seam between a model mark and an added one |
| marks land inside closing quotes/brackets | `_peel` | `"Sim," ele disse` must lose its comma, not become `"Sim", ...` |
| empty/unknown/short `pauses` → identity | early `return text` | this is the shipped default: wiring has not happened, `text in == text out` byte for byte |
| rising F0 → `?` | **not implemented** | no evidence (§1.5) |

Idempotent by construction (a comma the module adds sits behind a ≥ 250 ms pause, above the 200 ms
drop floor; added periods are never dropped), asserted as an arm.

---

## 3. Oracle — `_main/punct-prosody-oracle.py`

30 arms (29 on `normalise`, 1 drift guard on the measurement pipeline). Default mode exits 0;
`--neg-arm` exits 1 with `NEG-ARM: PASS`.

Both live strings are arms, with the junk pauses that produced them:

```
drop_junk_commas_live_a   "What's, crazy is, that Astro at the."       -> "What's crazy is that Astro at the."
drop_junk_commas_live_b   "What's, crazy is, that Astro at the highest thinking budget also."
                                                                       -> no commas left
```

Measured gaps are used verbatim as arm input: the real 360 ms gap of ptbr-tts-01 and the real
1100 ms gap of pt-br-sample are placed at their real word boundary:

```
add_comma_at_measured_360ms     "…para sexta feira porque o diretor"      -> "…sexta feira, porque…"
add_period_at_measured_1100ms   "…na proxima segunda feira os moradores"  -> "…segunda feira. os moradores…"
```

Full run:

```
identity_no_pauses_live                PASS
identity_none_pauses_live              PASS
identity_no_pauses_live_b              PASS
identity_empty_text                    PASS
identity_pauses_shorter_than_text      PASS
drop_junk_commas_live_a                PASS
drop_junk_commas_live_b                PASS
drop_floor_is_inclusive                PASS
keep_question_mark                     PASS
keep_period_drop_comma                 PASS
add_comma_at_measured_360ms            PASS
add_period_at_measured_1100ms          PASS
band_edges_249_250_599_600             PASS
no_add_below_clause_floor              PASS
no_double_marks                        PASS
no_mark_before_existing_mark           PASS
numeric_pause_entries                  PASS
unknown_pause_entry_is_identity        PASS
non_list_pauses_is_identity            PASS
mark_goes_inside_closing_quote         PASS
comma_dropped_inside_quote             PASS
trailing_period_from_silence           PASS
trailing_never_doubles                 PASS
trailing_needs_its_own_entry           PASS
f0_rising_does_not_make_question       PASS
idempotent                             PASS
whitespace_preserved                   PASS
whitespace_preserved_on_edit           PASS
standalone_mark_dropped_no_double_space PASS
measured_gaps_ptbr_tts_01              PASS

30 arms, 30 pass, 0 fail        (rc=0)
```

`measured_gaps_ptbr_tts_01` is the drift guard: it re-runs `frame_features`/`gaps_from` on
ptbr-tts-01 and demands the exact list `[100, 80, 80, 100, 180, 360, 80, 120]`. Without it, every
other arm would stay green while the extractor silently changed, because the arms use frozen
numbers.

Neg-arm: each mutation rewrites a **copy** in a temp dir, re-imports it by path, and the arm set
must go red. A mutation whose target string is missing, or whose mutant fails to import, is counted
as BROKEN — never as a passing mutation — so `NEG-ARM: PASS` cannot be produced by a no-op edit.

```
drop_floor_zero       (DROP_FLOOR_MS 200 -> 0)      RED as required  8/29 arms red
clause_floor_zero     (CLAUSE_MIN_MS 250 -> 0)      RED as required  17/29 arms red
sentence_floor_250    (SENTENCE_MIN_MS 600 -> 250)  RED as required  3/29 arms red

NEG-ARM: PASS        (rc=1)
```

`python -m py_compile worker/punctuation_prosody.py` → rc=0.

Constraints respected: `worker/sotto_worker.py` untouched, no model load, no app launch, no audio
played, no window opened, nothing committed.

---

## 4. What main still has to decide

1. **Where the pauses come from.** `normalise` needs a per-boundary silence list, and the worker
   currently joins fragments with no audio bookkeeping (`join_fragments`, `sotto_worker.py:4276`).
   The feature extractor in this oracle (`frame_features`, `gaps_from`) is the reference
   implementation — it is ~60 lines of numpy and could move into the worker or into a small
   streaming variant.
2. **The gate on real input.** §1.5: on a noisy/AGC'd capture the `noise_floor*3` gate sits at the
   median and the sentence rule will fire on noise. Wiring should either feed denoised audio or
   derive the floor from a rolling minimum, and re-run this oracle with real captured pauses.
3. **Asymmetry.** Dropping a comma is cheap; adding a period is expensive (it closes a caption
   line). If main wants extra safety, raise `SENTENCE_MIN_MS` only — every number in the module is
   a top-level constant for exactly this reason.

---

## 5. CACHE/PRICE
- task/agent: PunctFromProsody
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PunctFromProsody']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PunctFromProsody']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-05T19:26:00.122634+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PunctFromProsody']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['PunctFromProsody']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

## 6. SELF-AUDIT

- **protocolos em falta** — I started writing `worker/punctuation_prosody.py` before reading any
  existing `_main/*-oracle.py` for house convention. I checked one afterwards
  (`_main/word-split-oracle.py`) and the shape agrees (`--neg-arm` → rc=1 BY DESIGN, prints
  `NEG-ARM: PASS`, a decorative mutant is refused by name). Next time: read one sibling oracle
  before writing the first one, not after.
- **verificacao adicional** — run, cheap: the drift guard `measured_gaps_ptbr_tts_01` (added after
  asking the gate-doubt question). What I could not cheaply run: `normalise` against a *real
  streaming* pause stream from the worker, because that requires the wiring this lane is forbidden
  to touch. Cost of closing it: one capture session with the worker running, feeding
  `join_fragments`' fragment boundaries into the same extractor.
- **checkboxes novas** — "every receipt that quotes a measured distribution ships an arm that
  recomputes at least one of those numbers from the artifact in the same run" (here:
  `measured_gaps_ptbr_tts_01`, must go RED if `frame_features` or `gaps_from` changes). The
  mechanical form is a `--measure --assert` mode whose quoted rows are compared to the receipt.
- **review por outro subagente** — `sim-com-escopo`: the three thresholds (200/250/600) and the
  decision not to implement the `?` rule are the parts worth a second pair of eyes; the arithmetic
  and the arms are self-checking.
- **gate-doubt**
  - `verde-de-verdade:` the 30-arm green is not pass-by-construction — `--neg-arm` turns 3 of 3
    mutations red (8, 17 and 3 arms respectively) and refuses a mutation whose target string is
    missing, so the arm set demonstrably *can* fail. The measurement green is weaker in one place
    and I name it: the "6/6 trailing silence ≥ 600 ms" figure is partly tautological, because a
    recording ends after a sentence by construction, so it is not independent evidence for the
    sentence band — the only independent instance is the single 1100 ms inner gap at 0.513 vs an
    expected 0.534. The positional proxy is a second soft instrument: it assumes a uniform speaking
    rate, and the worst residual among hits (0.069 on enus-tts-01) is 70 % of the ±0.10 tolerance —
    which is why the headline is the per-mark table and not the ±0.10 contingency counts.
  - `falta-no-gate:` the gate does not check what happens when `pauses` and `text` come from
    *different* utterances (a desynchronised alignment): every arm supplies a list that is either
    the right length or shorter, and a length mismatch on the short side silently degrades to
    identity. A future change that reuses a stale `pauses` buffer across two fragments would pass
    every arm here and put commas in the wrong places.
  - `gate-melhor:` make the length relation explicit and mechanical:
    `normalise(text, pauses)` should refuse (raise or return text with a diagnostic) when
    `len(pauses) not in (0, n-1, n)`, and an arm `mismatched_pauses_rejected` would be the input
    that must leave it RED — today `len(pauses) == n-1` on a 7-word text fed a 3-word text's pauses
    is accepted silently.

  *Follow-up taken from this block:* the drift guard is now arm 30; the `len(pauses)` guard is
  **not** implemented, because the contract in the brief fixes the input shape and main wires it —
  recorded here as the first thing to add when the wiring lands.

- **confianca** — `alta` on "timing separates clause from sentence on clean audio" (5/5 clause
  precision, 5/6 comma recall, an empty 441–772 ms region across 6 clips) and `alta` on the
  module's rule behaviour (30 arms, 3 independent mutations red). `media` on the sentence band,
  for the tautology named above.
- **nao verificado** — (1) no real streaming pause stream was ever fed to `normalise`; (2) the
  noisy `live-sample-cable-input.wav` path is measured but the gate is known to be degenerate
  there, so no claim is made that the thresholds hold on live cable input; (3) only one internal
  sentence boundary exists in the whole fixture set; (4) `?`-related behaviour is untested by
  construction because no question exists in any fixture.

