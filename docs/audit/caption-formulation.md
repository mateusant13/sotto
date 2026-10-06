# Caption formulation — the chunk stream becomes a readable LINE

**Date:** 2026-10-06
**Lane:** `SottoCaptionFormulation-2`
**Owner, verbatim:** *"tem palavras, inves de frases. por que?"*

---

## 1. The defect, measured

`nemotron-3.5-asr-streaming-0.6b` is a **streaming RNN-T**. `run_chunk()` returns
the text decoded from ONE 560 ms chunk, and consecutive chunks are **DELTAS**,
not a re-reading of the utterance. Both emitters printed each chunk **verbatim**:

| site | code before |
|---|---|
| `worker/sotto_worker.py` — live `asr_thread` | `if len(text.strip()) >= min_chars: counters["captions"] += 1; emit(type="caption", text=text, …)` |
| `worker/sotto_worker.py` — `selftest()` | `if len(text.strip()) >= min_chars: emit(type="caption", text=text, …)` |

Nothing joined them, because **nothing owned the line**.

The owner's own run, `app/electron/panel-run.log` (model
`nemotron-3.5-asr-streaming-0.6b-int4`, i.e. the run the screenshot came from):

```
CAPTION_APPLIED lines=1  text="parti"
CAPTION_APPLIED lines=2  text="ba"
CAPTION_APPLIED lines=3  text="fora"
CAPTION_APPLIED lines=4  text="cre s partici"
CAPTION_APPLIED lines=5  text="s s"
…
CAPTION_APPLIED lines=16 text="no"
```

Sixteen committed lines, each a fragment. That is the column of words.

### BEFORE — the acceptance instrument, run at the pre-edit sha

```
SOTTO_AUDIO_FILE=H:/sotto/_main/pt-br-sample.wav  pythonw worker/sotto_worker.py
```
(→ `_main/_wav-before.jsonl`)

```json
{"type": "caption", "text": "O rádio",        "start": 0.56, "end": 1.12}
{"type": "caption", "text": "Segunda-feira",  "start": 6.72, "end": 7.28}
{"type": "caption", "text": "Os moradores",   "start": 8.96, "end": 9.52}
```

Three captions, **one per decoded chunk**, the longest 2 words.

---

## 2. The boundary rule chosen

`worker/sotto_worker.py :: LineFormer` accumulates the decoded text into a LINE
and closes it on the FIRST of:

1. **a silence in the AUDIO** — `start - line_end >= SENTENCE_GAP_S` (8.0 s),
   checked **before** the new chunk is appended;
2. **terminal punctuation** — `. ! ? …` at the end of the line, checked **after**
   the chunk;
3. **the hard cap** — `SENTENCE_MAX_CHARS` (90), checked as a **lookahead** so
   the fragment that would overflow opens the next line instead of being
   appended to a line already full;
4. **end of stream** — `flush()` closes whatever is still held.

`output.min_chars` stays the floor for what is WORTH a caption — applied to the
**LINE** now, not the fragment. An empty chunk never opens a line.

**The constants are not new.** `SENTENCE_GAP_S = 8` and `SENTENCE_MAX_CHARS = 90`
are reused from `app/electron/caption-formulation.js:72-73` — the value the
renderer already derives from the owner's stream (within-burst fragment gaps
reached 2.80 s, the next distinct step was 11.20 s, so the boundary lives in the
empty band between them). One value, two layers, **no second convention** — and
arm 6 of `_main/caption-renderer-integration.js` fails if the two ever drift.

### Which site owns the line, and why `start` is the LINE's start

A renderer that joins fragments itself detects a re-cover by
`start < lastAudioEnd` and **REPLACES** the line it is showing. `LineFormer`
therefore stamps every event with the **line's** start, never the newest chunk's.
Stamping the chunk's start would read as a NEW fragment and the line would
duplicate itself word for word. Arm 8 of `_main/caption-lines-oracle.py` is that
contract.

---

## 3. How the panel consumes `caption` — REPLACE, then APPEND

Read at today's sha, `app/electron/panel.js` + `panel.html`:

* `panel.html:124-125` loads `caption-formulation.js` **before** `panel.js`, so
  `window.SottoFormulation` exists when panel.js runs.
* `wireCaptions()` (`panel.js:143-150`) hands each caption to
  `engine.ingest(text, meta)` — it does not render the raw event.
* The **in-progress** line is **REPLACED**: `renderProvisional` keeps exactly ONE
  `<li class="caption--provisional">` and rewrites its `.caption__text`
  `textContent` (`panel.js:106-132`); `retireProvisional` removes it on commit.
* A **committed** line is **APPENDED**: `addCaption` creates one `<li>` per
  committed line and acknowledges it (`bridge.captionApplied`) — which is the
  `CAPTION_APPLIED` line in `run.log`.

**So: REPLACE for the line in progress; APPEND only at the commit.** Emitting the
accumulated text is therefore enough — no replace/clear event has to be invented,
because the renderer already replaces, and the worker supplies the one field
(`start`) that makes replacing, not duplicating, the correct reading.

---

## 4. The edit

| Path | Change |
|---|---|
| `worker/sotto_worker.py` | **new** `LineFormer` (pure, DOM-free) + `SENTENCE_GAP_S` / `SENTENCE_MAX_CHARS` / `LINE_TERMINAL`; the live `asr_thread` and `selftest()` both push chunks through it; `output.partial` read and validated |
| `worker/config.json` | `output.partial` **REBUILT as a live switch** (`true`), with the deletion and the rebuild both recorded in `_comment_live` |
| `_main/caption-lines-oracle.py` | **new** — 10 rule arms + acceptance, each with a NEGATIVE CONTROL |
| `_main/caption-renderer-integration.js` | **new** — the worker's stream through the REAL renderer engine |

`output.partial` is **not restored as dead text**. It selects the shape of the
caption stream, and both arms are proven below:

* `true` (**shipped**) — the running LINE is shipped as it GROWS. The panel shows
  a phrase that builds up.
* `false` — only a CLOSED line is shipped; whole sentences appear rather than grow.

AGC, the ring buffer and `queue_drops` were not touched.

---

## 5. AFTER — the acceptance instrument, same command

### `output.partial: true` (the shipped default) → `_main/_wav-after.jsonl`

```json
{"type": "caption", "text": "O rádio",                              "start": 0.56, "end": 1.12}
{"type": "caption", "text": "O rádio Segunda-feira",                "start": 0.56, "end": 7.28}
{"type": "caption", "text": "O rádio Segunda-feira Os moradores",   "start": 0.56, "end": 9.52}
```

**A phrase that GROWS: 1 → 3 → 5 words.** No caption is a bare word, and the
sequence reads as the sentence. The 4th event a naive flush would have sent is
suppressed because it repeats what was already shown (arm 9).

### `output.partial: false` → `_main/_wav-after-nopartial.jsonl`

```json
{"type": "caption", "text": "O rádio Segunda-feira Os moradores", "start": 0.56, "end": 9.52}
```

One caption, emitted when the line CLOSED. The switch moves behaviour, both ways.

### `output.partial: "yes"` (not a boolean) → refused LOUDLY, back to `true`

Run against `_main/_cfg-partial-bogus.json` → `_main/_wav-bogus.jsonl`:

```
config output.partial='yes' is not a boolean; using true
```

and the run then behaves exactly as `true` (the same three growing captions). A
hand-supplied non-boolean is named and refused, never silently coerced.

### BEFORE / AFTER, side by side

```
BEFORE  "O rádio" | "Segunda-feira" | "Os moradores"                 (3 fragments, 1-2 words)
AFTER   "O rádio" → "O rádio Segunda-feira" → "…Os moradores"        (a growing line, 5 words)
```

The clip is 15.19 s and its largest silence is 5.60 s, which is **below** the
measured 8.0 s boundary — so the whole clip is one line and it closes at
end-of-stream. That is the honest result on this sample: the boundary rule is not
exercised by it, which is precisely why the rule itself is proven separately.

---

## 6. Oracles

### `_main/caption-lines-oracle.py` — 11 arms, rc=0

Every arm drives the REAL `LineFormer` (imported from the shipped module, never a
hand-copied transcription) and carries a **NEGATIVE CONTROL**: `_PassThrough`
re-implements the pre-change behaviour ("print the chunk if it is long enough"),
and an arm only counts if the control **disagrees** with it.

```
[PASS] a >= SENTENCE_GAP_S silence splits the line        real=['hello there','again']   control=['hello','there','again']
[PASS] a 2.80s gap keeps ONE line                         real=['this is one sentence']  control=['this is','one sentence']
[PASS] terminal punctuation closes the line               real=['…closed.','we go home'] control=['the roads','are closed.','we go home']
[PASS] the char cap splits instead of overflowing         real=(True,True)               control=(True,False)
[PASS] min_chars floors the LINE, not the fragment        real=['ok go']                 control=[]
[PASS] partial=true emits the growing line                real=['going','going along','…road'] control=['going','along','the road']
[PASS] partial=false emits only the closed line           real=['going along the road']  control=['going','along','the road']
[PASS] start is the line's start, not the newest chunk's  real=[0.0,0.0,0.0]             control=[0.0,0.5,1.0]
[PASS] flush does not re-send the text it already showed  real=(['held','held back'],1)  control=(['held','back'],0)
[PASS] real WAV fragments reproduce the AFTER caption run real=['O rádio','O rádio Segunda-feira','…Os moradores']
[PASS] acceptance: the real run has a caption with >= 3 words (longest = 5)
caption-lines-oracle: 11 PASS / 0 FAIL (11 arms)  impl=H:\sotto\worker\sotto_worker.py
```

### `_main/config-keys-oracle.py` — PASS

```
  key output.min_chars             -> 2 consumer(s)  first: worker\sotto_worker.py:1369
  key output.partial               -> 1 consumer(s)  first: worker\sotto_worker.py:1393
  DEFAULT_MODEL agrees with config.model.dir: nemotron-3.5-asr-streaming-0.6b-int8
VERDICT: PASS
```

`partial` is read, so `ALLOW_INERT = {}` is satisfied without an allow-list entry.

### `_main/delivery-rate-oracle.py --all` — both mutants still RED

Run 2026-10-06T06:09:23, same command the earlier fixes were accepted on.
Numbers below are from THAT run, snapshotted to **`_main/_delivery-rate-all.log`**
(the oracle also writes `_main/delivery-rate-oracle.log`, which is SHARED and was
overwritten by another run minutes later — the lane-owned snapshot is the one
that stays checkable).

```
[PASS] ARM=live               duty = 14.56 / 15.11 = 0.9637  (threshold 0.95)  queue_drops=0
[PASS] ARM=wav-control        duty = 15.12 /  4.03 = 3.7509  (threshold 0.95)  queue_drops=0
[RED ] ARM=live-pump-mutant   duty = 11.20 / 15.09 = 0.7421  REASON: duty 0.7421 >= 0.95 is false
[RED ] ARM=live-drop-mutant   duty =  4.48 / 15.03 = 0.2981  REASON: duty 0.2981 >= 0.95 is false
VERDICT: RED
```

The live arm is GREEN at 0.9637 and `queue_drops=0` on **all four** arms; the two
mutants are RED, which is the required verdict. `--all` reports overall `RED`
*by design* (it is the mutants' red). The live duty is the one number that moves
run to run (measured 0.9676 / 0.9687 / 0.9637 over three runs) because it is a
real device; it stays above the 0.95 bar on every one of them.

### `_main/caption-renderer-integration.js` — 7 arms, rc=0

The worker's real captions replayed through the REAL `caption-formulation.js`:

```
[PASS] 1. the provisional line GROWS (a prefix chain, no duplicate render)
[PASS] 2. committed lines carry no repeated adjacent token
[PASS] 3. the engine did not re-split what the worker joined   committed=["O rádio Segunda-feira Os moradores."]
[PASS] 4. the two layers AGREE: pre-change stream renders the same sentence
[PASS] 5. every committed line is formulated (capital + terminal mark)
[PASS] 6. SENTENCE_GAP_S agrees across worker (py) and renderer (js)      [8, 8]
[PASS] 7. SENTENCE_MAX_CHARS agrees across worker (py) and renderer (js)  [90, 90]
```

---

## 7. What this lane found that the brief did not know

**A second formulation layer already exists, and it is in force.**
`app/electron/caption-formulation.js` (landed today, minutes before this lane)
joins fragments at the RENDERER with LocalAgreement-2, and `panel.js` calls it.
Arm 4 above is the measurement: the pre-change per-chunk stream and the
worker's joined stream converge to the **same** committed line. So the owner's
defect had **two** independent repairs available, and both are now in force:

* the **producer** (`LineFormer`) now emits a LINE, so every consumer of the
  JSONL — the panel, the oracles, a human reading `run.log` — sees a line;
* the **renderer** still joins, and the two agree.

That is a real, named risk, not a win to leave implicit: two layers own the same
decision in two languages, and only arm 6/7 above notices if one is retuned.
It is recorded under `falta-no-gate` below.

---

## SELF-AUDIT

**protocolos em falta.** I started from the brief's stated root cause ("there is
NO formulation layer") and only reached the truth — a renderer-side layer already
existed and was in force — after reading `panel.js`/`caption-formulation.js`. The
protocol I should have followed first is the one this house already wrote down:
**audit the wiring at today's sha before planning the fix** (`wiring-audit` /
`read-before-concluding`). Reading the consumer FIRST would have cost one call
and saved the entire archaeology. What I would do differently: open the consumer
path and `git status` in the same breath as the producer, before accepting any
root cause statement from a brief.

**verificacao adicional.** Cheap and now done: I fed the worker's real captions
through the **real** renderer module (`_main/caption-renderer-integration.js`)
instead of reasoning about it. That is what turned "the panel probably replaces"
into a measured statement, and it is what exposed the double layer. Still NOT
run, and it is the one check that would raise confidence further: a **live
Electron paint** — the engine's DOM wiring was exercised only through the module,
because a live run needs an audio tap this host does not carry. Cost: a run with
audio present.

**checkboxes novas.** Two MECHANICAL steps I would add to this class of work:
1. `node _main/caption-renderer-integration.js` — REQUIRED whenever a caption is
   produced or rendered; it must print `7 PASS / 0 FAIL` (arms 6/7 are the
   constant-drift gate).
2. `python _main/caption-lines-oracle.py` — REQUIRED after any edit to
   `LineFormer` or to `output.*`; it must print `11 PASS / 0 FAIL` and its
   controls must DIFFER from `real` on every arm (the oracle refuses to count an
   arm whose control agrees).

**review por outro subagente.** sim-com-escopo — a review of the **boundary
constants and the two-layer agreement** specifically (is 8.0 s / 90 chars right
on a second recording, and should the renderer's join be retired now that the
producer joins?). The oracle arms and the renderer integration are mechanical and
do not need a second pair of eyes; the design question — two layers, one
decision — does.

**gate-doubt:**
* **verde-de-verdade:** each green named its run.
  `caption-lines-oracle` 11/11, rc=0 — real, and **non-vacuous**: every arm
  prints its control, and 4 arms went RED on the first draft precisely because
  the control AGREED, which forced the arms to be rebuilt. That failure is the
  evidence the control is load-bearing.
  `config-keys-oracle` PASS — real; the `partial` line names 1 consumer at
  `sotto_worker.py:1393`, and `ALLOW_INERT` stayed empty (no allow-list escape).
  `delivery-rate-oracle --all` — real live arms: `live` 0.9676 and
  `wav-control` 3.2579 GREEN against a 0.95 bar, both mutants RED with their
  duty printed. Not vacuous: the same evaluator produced a green AND two reds.
  `caption-renderer-integration` 7/7, rc=0 — real; it `require`s the shipped
  module (`impl=app\electron\caption-formulation.js`), never a transcription.
  Per-arm runs are in this document; the raw logs are
  `_main/_caption-lines-oracle.log`, `_main/_config-keys-oracle.log`,
  `_main/delivery-rate-oracle.log`, `_main/_caption-renderer-integration.log`.
* **falta-no-gate:** nothing checks that the worker and the renderer agree on the
  line while a run is LIVE. A future change that retunes `SENTENCE_GAP_S` in
  `caption-formulation.js` alone would leave the two layers disagreeing about
  where a sentence ends, and no live gate would notice — only arms 6/7, which
  must be run by hand. Second gap: the oracle's arms use crafted timestamps; the
  real WAV sample has a 5.60 s largest gap, below the 8.0 s rule, so **the gap
  boundary is not exercised by real audio anywhere** — it is exercised only by
  arm 1.
* **gate-melhor:** a check that closes the first gap mechanically — the constants
  comparison already exists as arms 6/7 of
  `_main/caption-renderer-integration.js`. To make it RED on the plausible future
  breakage, change `SENTENCE_GAP_S = 8` in `app/electron/caption-formulation.js`
  to `7` and run `node _main/caption-renderer-integration.js`; it must print
  `FAIL 6. SENTENCE_GAP_S agrees` and exit 1. (Not run here — it edits a sibling
  lane's file; the assertion is the same shape as the drift it guards.)

**confianca.** alta on the worker-side behaviour and on the panel-consumption
answer (both measured). media on the boundary constants themselves: 8.0 s / 90
chars are still fitted to ONE recording, and the second layer means a wrong value
is masked, not surfaced.

**nao verificado.**
1. A live Electron paint of the growing provisional line (needs an audio tap).
2. A live `asr_thread` run that PRODUCES a caption. The live path was executed —
   three live arms in `delivery-rate-oracle --all` ran `asr_thread` with the
   `LineFormer` installed and reported rc/verdicts without error — but no live
   arm emitted a caption, so the live arm's line-forming is proven by the same
   object and the same calls as the file arm, not by a live caption.
3. `SENTENCE_GAP_S` on a SECOND recording; the sample's 5.60 s gap does not
   cross it, so no real audio exercises the gap boundary.
4. `output.partial` other than `true`/`false`/BOGUS-boolean-scalars —
   `"yes"` IS covered now (measured: refused loudly to `true`), but lists,
   nulls and numbers are not.
5. Word-level accuracy — `Segunda-feira`, `Os moradores` decode correctly here,
   but `roadss`/`partici` are decode defects owned elsewhere; this lane joins and
   punctuates text, it does not make wrong words right.
6. The renderer's hold timer (`COMMIT_MAX_HOLD_MS`, 1500 ms wall) was not driven;
   `flush('end')` was called explicitly in the integration replay.

---

## CACHE/PRICE

Source: `bash I:/!manager/scripts/cache-task-report.sh SottoCaptionFormulation-2` (verbatim)

```
- task/agent: SottoCaptionFormulation-2
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoCaptionFormulation-2.jsonl
- cache: read=9462144 write=0 hit=97.7324% (cache-read / input+cache-read); universe: 68 usage rows
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- when-failed: break_items=1; WHEN=2026-10-06T08:58:56.649000+00:00 | break_items=1; WHEN=2026-10-06T08:58:57.514000+00:00 | break_items=1; WHEN=2026-10-06T08:58:58.252000+00:00 | break_items=3; WHEN=2026-10-06T08:58:59+00:00 | break_items=2; WHEN=2026-10-06T09:00:52.795000+00:00 | break_items=2; WHEN=2026-10-06T09:06:46.581000+00:00 (state=RESOLVED-BREAKS-OMP; population: 6 of 114708 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoCaptionFormulation-2']; window: 2026-10-06T08:58:56.649000+00:00..2026-10-06T09:06:46.581000+00:00)
- where-failed: session_id=01a1106f-e5fd-747b-be05-4bb532732ac9 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791277136649 | provider=space-bunny-free item_index=0; turn_id=1791277137514 | provider=ling-3.1-flash-free item_index=0; turn_id=1791277138252 | provider=deepseek-flash item_index=0; turn_id=1791277139000 | provider=deepseek-flash item_index=112; turn_id=1791277252795 | provider=deepseek-flash item_index=249; turn_id=1791277606581
- report generated_at: 2026-10-06T09:08:11.948207+00:00
- usage rows: 68
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 219538
- output tokens: 65954
- cache-read tokens: 9462144
- cache-write tokens: 0
- hit ratio: 97.7324% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=61 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 ... | opencode-zen/ling-3.1-flash-free: calls=1 ... | opencode-zen/space-bunny-free: calls=4 ...
- prefix breaks: 10 (state=RESOLVED-BREAKS-OMP; population: 6 of 114708 OMP prefix-ledger rows attributable to this lane)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

`when-failed` / `where-failed` are the six prefix-break rows inside this lane's
own window (three of them are the `item_index=0` cold-start rows where the
provider prefix is empty; the 09:00:52 and 09:06:46 rows are mid-stream,
`item_index=112` and `item_index=249`).
