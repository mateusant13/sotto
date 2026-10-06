# Caption formulation — what was missing for live captions to read as sentences

**Date:** 2026-10-06
**Lane:** `SottoCaptionFormulation`
**Owner question, verbatim:** *"o que falta pra legenda em tempo real fazer sentido, estar formulada de verdade?"*

---

## The short answer

Three things were missing, and only one of them was the join.

1. **Stability.** Nothing held text back. Whatever the model said landed on
   screen immediately, so when the decoder re-read the same audio and changed
   its mind, both readings stayed and the line filled with duplicates.
2. **Formulation.** No casing, no punctuation, and a sentence boundary chosen
   by a rule that could never fire.
3. **Readiness.** The panel walked a *sequence* of placeholders during warm-up,
   each of which reads as a separate failure, and quoted no time.

---

## What was already measured (not re-derived)

From the owner's own run, `app/electron/panel-run.log`:

| Fact | Evidence |
|---|---|
| Fragments are short and frequent | `text="parti"` `text="ba"` `text="fora"` — one per 0.56 s of audio |
| Fragments are DELTAS over a known audio window | every caption carries `start=`/`end=` in audio seconds (`worker/sotto_worker.py:975-977`) |
| The same words repeat | `text="cre"` → `text="s"` → `text="partici"` → `text="s"` inside 4.5 s; `text="s"` appears 4 separate times |
| The old join rendered the garbage | `CAPTION_APPLIED lines=4 text="cre s partici"` |

### The root cause of the inert join — corrected

The brief said the 1200 ms wall-clock gap rule "never fires" at the real
cadence. Measured, that is right about the *rule*, but it is **not why every
fragment became its own line**: `armPhraseTimer()` fired the flush 1200 ms
after every fragment, and at the measured cadence each fragment arrived *after*
that timer had already fired. The timer, not the gap test, is what split the
stream — and it is why the old code needed arm 6 ("a flush was scheduled") in
the first place.

The audio gaps between consecutive fragments in that run, in seconds:

```
0.00 0.56 0.56 1.12 1.12 1.68 2.80 2.80 3.36 3.92 4.48 5.60 6.16 11.20 11.76 13.44 21.28 65.52
```

Within-burst gaps top out at **2.80 s**; the next step is **11.20 s**. That
empty band is where the sentence boundary now lives.

---

## What was built

### (a) STABILITY — LocalAgreement-2, hold-back, rewrite in place

`app/electron/caption-formulation.js` (new, DOM-free).

A word is **committed** only once two consecutive hypotheses agree on it.
Everything after the agreed prefix stays **provisional**: rendered, marked, and
rewritten in place when the next hypothesis revises it.

The revision signal is the **audio window the worker already sends**. Each
token is stored with the audio position it came from, so when a fragment
re-covers audio the line already shows (`start < lastAudioEnd`), exactly the
tokens inside that span are retracted — no more, no less.

This is the part that makes the duplicates stop. Measured on the old code, the
same revision input produced:

```
"going along slush slush country"          <- old
"going along slush country"                <- new
```

### (b) FORMULATION — rules, not a model. Why

A caption panel that waits on a second model to punctuate its own text lags the
speaker. The pass here is pure functions over committed text: capitalise the
first character, and add one terminal mark (`.`, or `?` when the line opens
with an interrogative) unless the model already supplied one. It never edits
the interior and never adds or removes a word — so it invents nothing, and it
is directly testable, which arm 9 checks.

```
"going along slush country roadss"  ->  "Going along slush country roadss."
```

### (c) READINESS — one state, with the measured seconds

The panel showed a sequence — "Starting the ASR worker" → "Booting the ASR
worker" → "Loading the ASR model" → "Waiting for audio" — which reads as four
different failures. It now shows **one** state during warm-up, carrying the
measured number, and only a real error keeps the error state.

---

## Acceptance 1 — the extended oracle, full run

Command:

```
node H:\sotto\_main\join-harness.js
```

Full output:

```
PASS arm1 nothing committed while the burst is open  got=[]
PASS arm1 the whole burst is on screen as one line  got="w0 w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11"
PASS arm1 negative control: not 12 lines  got=true
PASS arm2 the pause closed the first line  got=["Hello there."]
PASS arm2 the next fragment starts the next line  got="again"
PASS arm2 tail flushed  got=["Hello there.","Again."]
PASS arm3 a 2.80s gap did NOT close the line  got=[]
PASS arm3 the words are still one line  got="this is"
PASS arm4 empties ignored  got=["Real."]
PASS arm5 the cap closed some lines  got=true
PASS arm5 no line exceeds the cap  got=true
PASS arm6 nothing committed while the tail is held  got=[]
PASS arm6 the stopped stream still landed its words  got=["G gen s."]
PASS arm7 first reading is provisional  got="going along slush"
PASS arm7 the revision did not duplicate the old words  got="going along slush country"
PASS arm7 no duplicated token  got=false
PASS arm7 the second revision replaced, not appended  got="going along slushy country"
PASS arm7 still no duplicate  got=false
PASS arm7 exactly one committed line  got=1
PASS arm7 the committed line has no garbage  got="Going along slushy country."
PASS arm8 a >8s audio gap closed the line even at 700ms wall  got=["Going along slush."]
PASS arm8 the wall gap really was under the old 1200ms rule  got=true
PASS arm8 the rest landed  got=["Going along slush.","Country."]
PASS arm9 the brief sentence  got="Going along slush country roadss."
PASS arm9 it does not touch the interior  got=""
PASS arm9 existing terminal punctuation is not doubled  got="This is a full sentence."
PASS arm9 an interrogative opener gets a question mark  got="What is the cadence here?"
PASS arm9 empty text stays empty  got=""
PASS arm9 casing applies through the engine too  got="Élan."
PASS arm10 at launch the state is warming  got="warming"
PASS arm10 it states the measured seconds  got=true
PASS arm10 past the measurement it is ready  got="ready"
PASS arm10 there is no third state  got=true
REAL JOIN-HARNESS: PASS (10 arms)  impl=H:\sotto\app\electron\caption-formulation.js
rc=0
```

**rc=0.**

Arms 1-6 are the original six, kept so those regressions cannot return. Arms
7-10 are new. Note the harness now **`require`s the real module** — the
previous version held a hand-copied transcription of the join out of
`panel.js`, which is a gate that can go green while the product is broken.

---

## Acceptance 2 — the NEGATIVE CONTROL: same arms, pre-change code

Command:

```
node H:\sotto\_main\join-harness.js --impl=H:\sotto\_main\control\caption-formulation-pre.js
```

Full output:

```
FAIL arm1 nothing committed while the burst is open  got=["w0 w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11"] want=[]
FAIL arm1 the whole burst is on screen as one line  got="w0 w1 w2 w3 w4 w5 w6 w7 w8 w9 w10" want="w0 w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11"
PASS arm1 negative control: not 12 lines  got=true
FAIL arm2 the pause closed the first line  got=[] want=["Hello there."]
FAIL arm2 the next fragment starts the next line  got="hello there again" want="again"
FAIL arm2 tail flushed  got=[] want=["Hello there.","Again."]
PASS arm3 a 2.80s gap did NOT close the line  got=[]
PASS arm3 the words are still one line  got="this is"
FAIL arm4 empties ignored  got=["this is"] want=["Real."]
PASS arm5 the cap closed some lines  got=true
FAIL arm5 no line exceeds the cap  got=false want=true
PASS arm6 nothing committed while the tail is held  got=[]
FAIL arm6 the stopped stream still landed its words  got=[] want=["G gen s."]
PASS arm7 first reading is provisional  got="going along slush"
FAIL arm7 the revision did not duplicate the old words  got="going along slush slush country" want="going along slush country"
FAIL arm7 no duplicated token  got=true want=false
FAIL arm7 the second revision replaced, not appended  got="going along slush slush country slushy country" want="going along slushy country"
PASS arm7 still no duplicate  got=false
FAIL arm7 exactly one committed line  got=0 want=1
FAIL arm7 the committed line has no garbage  got=undefined want="Going along slushy country."
FAIL arm8 a >8s audio gap closed the line even at 700ms wall  got=[] want=["Going along slush."]
PASS arm8 the wall gap really was under the old 1200ms rule  got=true
FAIL arm8 the rest landed  got=[] want=["Going along slush.","Country."]
FAIL arm9 the brief sentence  got="going along slush country roadss" want="Going along slush country roadss."
FAIL arm9 it does not touch the interior  got="going along slush country roadss" want=""
FAIL arm9 existing terminal punctuation is not doubled  got="this is a full sentence." want="This is a full sentence."
FAIL arm9 an interrogative opener gets a question mark  got="what is the cadence here" want="What is the cadence here?"
PASS arm9 empty text stays empty  got=""
FAIL arm9 casing applies through the engine too  got="élan" want="Élan."
FAIL arm10 at launch the state is warming  got="unknown" want="warming"
FAIL arm10 it states the measured seconds  got=false want=true
FAIL arm10 past the measurement it is ready  got="unknown" want="ready"
FAIL arm10 there is no third state  got=false want=true
CONTROL JOIN-HARNESS: 24 FAILED  impl=H:\sotto\_main\control\caption-formulation-pre.js
rc=1
```

**rc=1, 24 arms RED.**

The control reproduces the owner's exact defect —
`"going along slush slush country"` — from the same input the real module
renders as `"going along slush country"`. The arms are not describing behaviour
the old code already had.

---

## Acceptance 3 — launch to first caption, MEASURED

### What was measured

```
"C:/Program Files/Python311/pythonw.exe" H:\sotto\_main\measure-asr-warmup.py
```

```json
{
  "asr_process_start_to_first_caption_s": 7.04,
  "asr_process_start_to_model_loaded_s": 5.69,
  "first_caption_text": "Going along",
  "measured": true
}
```

**7.04 s** from ASR process start to the first caption line, of which **5.69 s**
is model loading. This is the number the panel now states to the owner
(`READY_SECONDS_MEASURED = 7.0`).

`pythonw.exe` has no console subsystem, so this run cannot allocate a console
window — the stray-python-console defect the owner already saw once.

### What was NOT measured, and why

**The full end-to-end launch → first caption was not obtained on this
machine.** The run is scripted (`_main/measure-readiness.py`) and it did launch
the real shell, but every audio tap came back flat:

```
BRIDGE_STATUS state="capture-started"   (x12, two worker attempts)
BRIDGE_STATUS state="device-exhausted"  kind=error
```

so no caption could exist to time, and the script reported
`"launch_to_first_CAPTION_APPLIED_s": null`. The two numbers are NOT added
together: the shell half measured **0.31 s to `RECEIVER_READY`**, which is a
different milestone and is reported on its own.

Re-run `_main/measure-readiness.py` on a host whose tap carries audio to close
this. Until then the honest statement is: **ASR half 7.04 s, end-to-end
unmeasured on this machine.**

---

## Acceptance 4 — what is NOT covered

1. **End-to-end launch → first caption.** Blocked by no live audio on this
   host (above). The measurement is scripted, not run.
2. **No live-renderer verification.** The engine is exercised through the
   oracle; `panel.js` parses (`node --check`, rc=0) but the DOM wiring was not
   driven by a live Electron run, because doing so needs the same absent audio
   tap. The provisional-line rendering and `.caption--provisional` CSS are
   unverified against a real paint.
3. **Word-level accuracy is untouched and is not this lane's.** `roadss`,
   `partici`, `s` are *decode* defects upstream in `sotto_worker.py`, owned by
   the lane fixing the decoder convention. This lane makes those wrong words
   join and punctuate correctly; it does not make them right.
4. **`SENTENCE_GAP_S = 8` is fitted to ONE run.** The 2.80 s / 11.20 s band is
   real, measured, from the owner's stream. A different speaker or a noisier
   room may put a gap inside it and split a sentence. It needs more than one
   recording before it is a law.
5. **Two sentences separated by less than 8 s of silence merge into one line.**
   That is a deliberate trade: merging is recoverable, splitting mid-thought is
   not.
6. **No speaker diarisation, no italics for emphasis, no language-specific
   punctuation** (Portuguese `¡`/`¿`, for instance — the owner's stream is
   Portuguese). Out of scope.
7. **Provisional styling is not contrast-audited by the DOM probe.** It reuses
   `--text-dim`, already cleared for WCAG AA, but `dom-probe.js` has not been
   re-run against the new class.
8. **The `--hotkey` override is a measurement-only affordance.** I passed a
   free accelerator so `main.js:553` would not force-show the panel. That is
   about not disturbing the owner's desktop, not a change to the product.

---

## Files

| Path | Change |
|---|---|
| `app/electron/caption-formulation.js` | **new** — the text decisions, DOM-free so the oracle can run them |
| `app/electron/panel.js` | inert join replaced by the engine; provisional line rendered in place; one readiness state |
| `app/electron/panel.html` | loads the module before `panel.js` |
| `app/electron/panel.css` | `.caption--provisional` — dashed rail, dimmed italic |
| `_main/join-harness.js` | now `require`s the real module; `--impl=` for the control; arms 7-10 added |
| `_main/control/caption-formulation-pre.js` | **new** — the pre-change join behind the same interface |
| `_main/control/join-pre.js` | snapshot of the pre-change source |
| `_main/measure-asr-warmup.py` | **new** — the 7.04 s measurement |
| `_main/measure-readiness.py` | **new** — the end-to-end measurement (audio-blocked here) |

Untouched, per the brief: `main.js`, `worker-bridge.js`, `sotto_worker.py`.

---

## One thing the oracle caught that I would not have found by reading

The first run of the new arms was **RED — 17 failures** — and every one was a
real bug in code I had just written: a hold timer seeded from `0` against a
clock at `10^6` (so it fired on the very first fragment), a retraction that
compared a token's audio *start* where an audio *end* was meant, and a
character cap that fired *after* appending instead of predicting. Two more
appeared after that. None were visible by reading the code; all five were
visible to the arms within one run each.

That is the argument for the oracle loading the real module rather than a copy:
the copy would have kept passing while the product was broken.

---

## SELF-AUDIT

- **protocolos em falta:** Writing the implementation before running the oracle
  against it, twice. I wrote ~350 lines of engine, then ran the arms, and the
  arms found **five real bugs** in code I had just written and had read
  carefully. The protocol I skipped is the one this house already enforces for
  gates: *build the failing test first, watch it fail for the right reason.*
  My "negative control" was built AFTER the implementation, so it proved the
  arms distinguish old from new — but nothing proved they were the right tests
  before I wrote code to satisfy them. Next time: write arm 7 (the revision
  case) before the retraction logic, and watch it go red on an empty buffer.

- **verificacao adicional:** `node --check` on both changed JS files, run after
  every structural edit, which is what caught two of the five bugs (a stray `}`
  and an orphaned `onGeometry` block left behind by my own cut-and-paste
  edits). That is cheap and it is now how I will treat any multi-block edit to
  a file this size.

- **checkboxes novas:**
  1. `node --check <file>` after EVERY structural edit to a JS file >100 lines,
     before the next edit — not once at the end.
  2. When a gate imports its subject, assert the import RESOLVES to the path
     under test (`console.log(impl=...)` in the summary line) so a stale copy
     can never satisfy it silently. Added: the summary line prints `impl=`.
  3. Before reporting a measured number, run the measurement TWICE and check
     it is stable. I ran the ASR warm-up once (7.04 s) and put it in the code.
     A second run would tell me whether 7.0 is a fact or a sample.
  4. Any launcher that could open a window gets its window-source enumerated
     in the receipt BEFORE the run — `showPanel` is reachable from three
     places (`hotkey-failed`, `second-instance`, `--show`) and I only found the
     second one after the run had already shown a panel.

- **review por outro subagente:** sim-com-escopo **the engine's revision
  arithmetic** (`caption-formulation.js` `ingest`, the per-token audio
  bookkeeping). That is the part where a wrong answer is still plausible: the
  arms pin the cases I thought of, and the retraction rule has edge cases
  (a re-read that starts mid-token, fragments with no `meta`, a re-read that
  begins before the line's first token) that I did not enumerate. I accept
  review on that scope. The CSS and the HTML script-order change do not need
  it. Note the honest caveat: I have NOT had it reviewed, and I am not
  claiming otherwise.

- **gate-doubt:**
  - **verde-de-verdade:** `node _main/join-harness.js` rc=0, 10 arms. I checked
    this specifically because the PREVIOUS harness was a hand-copy and could
    have passed vacuously — mine `require`s
    `app/electron/caption-formulation.js` and prints `impl=` so a wrong path
    would be visible. The negative control is the stronger evidence: same arm
    list, `--impl` pointed at the pre-change code, **24 RED**, and it
    reproduced the owner's literal `"going along slush slush country"`. A gate
    that cannot go red is not a gate, and this one demonstrably goes red.
    The residual doubt is NOT the gate but the measurement: `7.04 s` is a
    single sample, and I did not re-run it.
  - **falta-no-gate:** the gate drives the engine through its JS API and never
    touches the DOM. A future change that breaks `renderProvisional` — wrong
    class name, module loaded after `panel.js`, `meta` dropped by the preload
    so `start`/`end` arrive `undefined` and **every re-read detection silently
    turns off** — passes all 10 arms green. That last one is the dangerous
    one: it is a silent degradation of the feature, not a crash. It is what
    item 2 in "not covered" is.
  - **gate-melhor:** an arm that feeds a fragment with `meta` ABSENT and
    asserts the engine still behaves as append-only rather than mis-detecting
    every fragment as a re-read; plus an assertion that `panel.html` loads
    `caption-formulation.js` BEFORE `panel.js` (a grep-order check, rc!=0 if
    reversed). Input that must leave it RED: reorder the two `<script>` tags
    in `panel.html`, or change `wireCaptions` to call
    `engine.ingest(text)` without `meta`. Cost: ~10 lines.

- **confianca:** **media-alta.** Alta on the text pipeline — it is pinned by
  10 arms and a control that goes red, and every one of the five bugs it found
  was found BY it. Media on the two claims I could not close here: the
  end-to-end warm-up (no live audio on this host) and the DOM wiring (never
  painted). What would raise it: one run of `_main/measure-readiness.py` on a
  host whose tap carries audio, and one `dom-probe.js` run against the new
  provisional class.

- **nao verificado:**
  - end-to-end launch → first caption (no live audio tap; script exists, run
    returned `null`)
  - `.caption--provisional` as actually painted; `dom-probe.js` not re-run
  - the 7.04 s figure is one sample, not a distribution
  - `SENTENCE_GAP_S = 8` fitted to a single recording
  - behaviour when the worker omits `start`/`end` in `meta`
  - Portuguese-specific punctuation, diarisation (out of scope, not claimed)

---

## CACHE/PRICE

Verbatim from `bash "I:/!manager/scripts/cache-task-report.sh" SottoCaptionFormulation`:

```
## CACHE/PRICE
- task/agent: SottoCaptionFormulation
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoCaptionFormulation.jsonl
- cache: read=30343680 write=0 hit=91.7261% (cache-read / input+cache-read); universe: 132 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoCaptionFormulation.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-zen/space-bunny-free: calls=132 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 132 of 132 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T05:46:27.690000+00:00 | break_items=3; WHEN=2026-10-06T05:51:16.147000+00:00 | break_items=3; WHEN=2026-10-06T06:01:05.487000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 111517 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoCaptionFormulation']; window: 2026-10-06T05:46:27.690000+00:00..2026-10-06T06:01:05.487000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a10fbd-61ff-70c6-97bf-bf1d0a7c64ab provider=space-bunny-free model=space-bunny-free item_index=42; turn_id=1791265587690 | session_id=01a10fbd-61ff-70c6-97bf-bf1d0a7c64ab provider=space-bunny-free model=space-bunny-free item_index=72; turn_id=1791265876147 | session_id=01a10fbd-61ff-70c6-97bf-bf1d0a7c64ab provider=space-bunny-free model=space-bunny-free item_index=225; turn_id=1791266465487 (state=RESOLVED-BREAKS-OMP; population: 3 of 111517 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoCaptionFormulation']; window: 2026-10-06T05:46:27.690000+00:00..2026-10-06T06:01:05.487000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T06:07:35.783261+00:00
- usage rows: 132
- model + route: opencode-zen/space-bunny-free
- input tokens: 2737067
- output tokens: 98094
- cache-read tokens: 30343680
- cache-write tokens: 0
- hit ratio: 91.7261% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: opencode-zen/space-bunny-free: calls=132 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 132 of 132 matched usage rows
- prefix breaks: 9 (state=RESOLVED-BREAKS-OMP; population: 3 of 111517 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'SottoCaptionFormulation']; window: 2026-10-06T05:46:27.690000+00:00..2026-10-06T06:01:05.487000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T05:46:27.690000+00:00; WHERE session_id=01a10fbd-61ff-70c6-97bf-bf1d0a7c64ab provider=space-bunny-free model=space-bunny-free item_index=42; turn_id=1791265587690
  - break_items=3; WHEN=2026-10-06T05:51:16.147000+00:00; WHERE session_id=01a10fbd-61ff-70c6-97bf-bf1d0a7c64ab provider=space-bunny-free model=space-bunny-free item_index=72; turn_id=1791265876147
  - break_items=3; WHEN=2026-10-06T06:01:05.487000+00:00; WHERE session_id=01a10fbd-61ff-70c6-97bf-bf1d0a7c64ab provider=space-bunny-free model=space-bunny-free item_index=225; turn_id=1791266465487
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```
