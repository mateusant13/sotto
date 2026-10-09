# RECEIPT — LANE SPEC-04 · `specs/04-index-search.md`

**Artifact:** `H:\sotto\_moved\aireplay\specs\04-index-search.md`
**Final:** 71 334 B · 1009 lines · **bare LF** (matches all three sibling specs, verified
0 CRLF in each of `01`, `02`, `03`) · sha256 `27303fe2f26d2301…`
**Scope:** this file only. No source code, no `specs/01–03`, no `src/index/**` (L4's) was
touched. Everything written under `_main/` is new and named `*spec04*`.

## WHY THIS RECEIPT IS LONGER THAN A LIST OF NUMBERS

The spec's own acceptance criterion is that an implementer could build L4's task from it
alone. That criterion is only checkable by **executing** the spec and by **letting something
else try to break it**. Both happened. **Two BLOCKER defects survived my own reading and were
found only by running the spec's SQL and by an independent reviewer** — one of them would have
shipped a permanently-wrong search index.

## 1. THE CROSS-CHECK THE BRIEF ASKED FOR — and it changed the spec

The brief required checking the interfaces against what `src/asr/segment.py` and
`transcribe.py` **really emit**. Reading is not enough, so I ran the ASR:

```
py -3 -m asr.transcribe --wav H:\sotto\_main\_redux-long\plain-3600s.wav \
      --offset-s 900 --max-s 120 --threads 2 --level off --json
RESULT … silence 11 segs (med 6.98s max 13.82s) audio 120.0s load 8.141s infer 21.393s
       rtfx(infer/steady/slice)=4.06/4.08/5.61 threads(intra=2,inter=1)
       cpu(infer med/max)=217.2/238.4% rss(load/peak/peak_wset)=736.4/911.4/923.9MB chars=814
exit=0
```

It reproduced `specs/02 §6`'s regression lock exactly (**11 segments, 814 chars, median
6.98 s, max 13.82 s**), which is itself evidence the capture of ground truth was faithful. The
event file is 4 811 B, sha256 `f895749477532574…`, **valid UTF-8 with non-ASCII**
(`_main/lane-spec04-asr-emit.json`).

Six facts came out of it, and **three of them are now load-bearing rules in the spec**:

| # | MEASURED | became |
|---|---|---|
| 1 | `segments[]` has exactly 7 keys: `i, start, end, audio_s, wall_s, chars, text` | §4.3's whole input surface |
| 2 | `start` is **ABSOLUTE in the wav** — `offset_s=900` ⇒ `segments[0].start = 914.32` | §1.3's conversion formula + the warning that `done.offset_s` is **not** subtracted again |
| 3 | adjacent segments **overlap by exactly 0.20 s**; `i=3`→`i=4` has a **10.26 s gap** | no non-overlap invariant; the `UNIQUE(video_id, start_ms)` justification |
| 4 | `sum(chars) = 804` but `len(done.text) = 814` (the 10 join spaces) | do not assume the concatenation is reversible |
| 5 | `wav_format.duration_s = 3600.0` vs `audio_s = 120.0` | `video.duration_ms` is the **clip's**, never the wav file's |
| 6 | no `producer`, no `model_sha256`, no confidence, no language, no word timings | §4.3's "the index MUST NOT require" list |

## 2. THE FTS5 DECISION, MEASURED NOT ASSUMED

The brief demanded a **decision** on FTS5-vs-fallback with a reason. It is **FTS5, external
content, `unicode61 remove_diacritics 2`**, and every part of that was measured:

| question | answer | log |
|---|---|---|
| available? | SQLite **3.43.1**, `ENABLE_FTS5` true, `fts5` in `pragma_module_list()` | `lane-spec04-fts5-avail.log` |
| which tokenizers construct? | `unicode61` ± `remove_diacritics 0/1/2` ✅ · `porter unicode61 remove_diacritics 2` ✅ · `trigram` ✅ · **`ascii` + `remove_diacritics` ❌ `error in tokenizer constructor`** | `lane-spec04-fts5-tok.log` |
| diacritic folding | `acesso` matches `ACESSO NEGADO`, `acesso negado` **and** `Acesso à Negado` | same |
| cost | **+3.75 MiB** on 28.32 MiB (**+13.2 %**); light commit **1.02× median / 1.87× p95** | `lane-spec04-index-cost.log` |

**The finding that decided §1.5** — and it is the strongest single result in this lane:

```
'segunda-feira'   -> RAISED  OperationalError: no such column: feira
'"segunda-feira"' -> OK  3 rows
'r-adio'          -> RAISED  OperationalError: no such column: adio
```

Run **against the product's own registered ASR output**, whose first segment is *"O rádio
anunciou que a ponte sobre o rio vai ser interditada na próxima **segunda-feira**."* An FTS5
`MATCH` string is not a string literal; an unquoted hyphen is parsed as *phrase minus column*
and **raises**. So an implementer who interpolates the user's query would **crash the search
box on ordinary Portuguese** — on an owner's-primary-language product. §1.5 now carries the
escaping rule as a table, with the prefix-operator hole (`acess*` inside quotes becomes a
literal phrase) called out separately.

## 3. THE WRITE PATH, AND THE FAILURE THE SPEC EXISTS FOR

`research 07` measured a light commit of **0.061 ms** on a schema with **no FTS5**. Quoting
that as the write budget would have been quoting a number for a schema that does not ship, so I
re-measured it on the shipping schema: **0.0458 ms median / 0.1670 ms p95** at 120 201
segments (`lane-spec04-index-cost.log`), plus reconciliation costs **8.667 ms** (state scan)
and **55.584 ms** (FTS-coverage scan).

The ordering decision is the substance: **T0 writes the `video` row BEFORE the file exists**,
because a row with no file is *recoverable* (§2.5 finds `state='cutting'` and repairs it) while
a file with no row is *invisible forever*. Those two failures are not symmetric, and only one
of them is detectable.

## 4. THE REVIEW — AND THE TWO BLOCKERS IT CAUGHT

A read-only verifier was dispatched with **no file to write** (seat constraint), briefed to hunt
exactly one failure: *would an implementer following this spec produce something incompatible
with the real ASR output or with L1/L2?* Verdict file:
`_main/lane-spec04-review-verdict.md`.

**Its first line was `VERDICT: FAIL`, with 3 BLOCKERs, 2 MAJORs, 3 MINORs.** All were triaged;
all 8 were fixed. The two that mattered:

### BLOCKER 1 — `INSERT OR REPLACE` would have shipped a permanently wrong index

My §2.4 mandated `INSERT OR REPLACE INTO transcript`. `REPLACE` is `DELETE` + `INSERT`, and
with `recursive_triggers` OFF — **SQLite's default** — the `AFTER DELETE` trigger does not fire,
so **the superseded text stays in `transcript_fts` forever while `fts_orphans` stays 0** and
§2.5's reconciliation cannot see it.

I did not take the reviewer's word for it. Reproduced here on the spec's own DDL, four arms
with a NEG arm (`_main/lane-spec04-replace-trigger-oracle.py`, `lane-spec04-replace-trigger.log`):

```
ARM  recursive  mode      old_before old_after new_after  STALE  integrity_check
     False     replace   1          1         1         True    ok
     True      replace   1          0         1         False   ok
     True      update    1          0         1         False   ok
VERDICT: GREEN
```

⚠ **`integrity_check = ok` on the broken arm.** The store is not corrupt, so no database check
will ever report it — which is precisely why this is silent recall loss rather than a crash.
Fixes are now in the spec: `PRAGMA recursive_triggers=ON` (§1.1) **and** `INSERT OR REPLACE`
forbidden on `transcript`/`ocr`, with UPDATE-when-exists (§2.4) **and** a `stale_fts_tokens`
counter (§6.3) that can actually see it.

### BLOCKER 2 — the schema's declared grain contradicted its own write path

§1.2 declared a **5 s window**; §4.3 writes **one row per ASR chunk**; the real chunks are
**3.96 / 5.08 / 6.96 / 6.98 / 8.06 / 8.08 / 13.76 / 13.82 s — none is 5.00 s and none is
grid-aligned.** An implementer must pick one and would pick silently. Decided, with reason:
**`segment` carries whatever the producer emits; there is no fixed grid in the schema** — the
ASR is silence-aligned (re-cutting to a 5 s grid collapses text to ratio **0.229** against the
oracle) and chunks overlap by 0.20 s, so a fixed grid cannot even be assigned without
duplicating or dropping ~4 % of every clip's speech. `window_ms` is now honestly a **planning
average for the embedding pass**, and §5's corpus arithmetic is **re-derived** at the measured
grain (11 chunks/120 s ⇒ **55 000** per 1000 × 10 min; `MAX_SEGMENT_S=15` ⇒ 40 000), replacing
`research 07`'s 120 000 which assumed the fictional grid.

### Also fixed

- **BLOCKER 3** — `clip_uuid` and `produced_by` **do not exist anywhere in `src/capture/`**
  (MEASURED) and `frames_in_clip` keeps its own name (I had renamed it `frames`). §4.1 now
  carries a **field-provenance table** separating "exists verbatim in `CutResult`" from "must
  be ADDED to lane 03's wire event", and names the fields deliberately dropped
  (`base_abs`, `end_abs`, `encoded_in_window`, `captured_in_window`, `expected_in_window`).
- **MAJOR 1 — all five wrong line citations.** `runner.py:232`→**:233** (verified: line 232 is
  `"i": i`), `audio.py:53-62`→**:53-61**, `transcribe.py:105-107`→**:110-114** (`return 2` at
  :114), `engine.py:50-71`→**:90-111**. These were real errors: I cited a line number I had
  read in a *different revision*.
- **MAJOR 2** — `producer` hard-coded `intra=4,inter=1` while my own §7 evidence ran at
  `--threads 2` and reads `intra=2`. Now a TEMPLATE built from `done.threads`.
- **MINOR 1** — `ON CONFLICT` merges silently ⇒ new `segments_collided` counter (§6.3).
- **MINOR 2** — gap sign: `−10.26 s` → a **gap of 10.26 s** between `i=3` and `i=4`.
- **MINOR 3** — the escaper neutralised a trailing `*`; §1.5 now specifies the prefix operator
  goes **outside** the quotes.

## 5. A CONCURRENCY FACT L4 MUST KNOW

**`src/asr/` is being edited in parallel by another lane, right now.** During this session
`runner.py` and `transcribe.py` changed at **12:20** and `engine.py` at **12:34**, *after* my
citations were taken; a new `gate.py` appeared at 12:26 that was not in my first directory
listing. I re-read the current files: the **emitted shape did not change** — the 7 `segments[]`
keys, `text or ""` (`runner.py:230`), and the `done` construction (`:259+`) are byte-identical.
**But bare line numbers are not a durable citation against a moving target**, so §4.1 now
requires citing `path:line` **and** the symbol or the exact quoted token, and states which to
trust when they disagree.

## 6. THE SPEC IS EXECUTABLE — VERIFIED, NOT ASSUMED

`_main/lane-spec04-ddl-check.py` extracts **every SQL fence from the spec** and runs it on
SQLite 3.43.1:

```
sql fences found: 8 … ALL FENCES EXECUTED: True   (6 tables + meta + 2 FTS5 virtual + 6 triggers)
upsert ON CONFLICT … RETURNING  -> same seg_id on re-run, count stays 1
overlapping segment            -> ACCEPTED (correct: no non-overlap constraint)
text='' legal / text=NULL      -> accepted / refused by NOT NULL (IntegrityError)
channel/dtype CHECKs           -> 'nope' and 'bfloat16' refused
orphan transcript (FK ON)      -> refused (IntegrityError)
quoted MATCH through trigger   -> rowids [3]  (the trigger fires)
unquoted MATCH                 -> RAISED OperationalError no such column: feira (the trap)
'rebuild' repair               -> OK
```

⚠ **This gate caught a BLOCKER of my own making before any reviewer saw it.** In the first
draft the §1.4 block *described* the triggers in a SQL comment and **never wrote them**:
`trigger count = 0`, so the lexical surface would have been **permanently empty** while every
transcript sat in the table — the silent failure §6 forbids, shipped by omission. The six
triggers are now real DDL in the spec.

**Three of my own probes were also caught being wrong**, which is the point of both-colour
gates and worth recording rather than hiding:

| probe | what it claimed | truth |
|---|---|---|
| `_lane-spec04-ddl-check.py` | "rebuild FAILED: no such column: seg_id" | **the rebuild always worked**; my *verification* query asked a one-column FTS table for a `seg_id` column. Reproduced clean across three independent probes reading the spec verbatim |
| `_lane-spec04-rebuild4.py` | FK failure | **correct refusal** — my probe hardcoded `seg_id=3` in a DB where segments were numbered 1,2. The FK was right; I was wrong |
| `_lane-spec04-replace-trigger-oracle.py` | 4-arm run | my 4th "control" was a plain `INSERT` on an existing PK — an error, not a staleness test. Removed |

## 7. NUMBERS, AND WHAT IS NOT A NUMBER

The numbers table is **31 rows**, every one carrying its unit and its reason. Provenance tags
in the final file: **54 `MEASURED`**, 11 `UNKNOWN`, 35 `⚙` (decisions with reasons), and
**zero `TBD`/`TODO`/`FIXME`** (verified by script). Six decisions were genuinely open and are
**decided with rationale**, not deferred:

1. **FTS5, not LIKE** (§1.4) — available and measured; the `like` path is declared *and loud*.
2. **`lexical 1.0` RRF weight** — `research 07 §7.6` left it UNKNOWN. Decided level with the two
   text channels and above `visual 0.7`, because RRF consumes only **rank**, and lexical is the
   required exact baseline for OCR. Stored in `meta.rrf_weights`; the experiment that reopens it
   (A/B `w ∈ {0.5,1.0,2.0}` over 20 hand-labelled queries) is named.
3. **`recursive_triggers=ON`** (§1.1) — measured BLOCKER fix.
4. **`segment` grain = the producer's chunk** (§1.2) — BLOCKER fix, with the cost re-derived.
5. **`meta` table added** (7th table beyond `research 07`'s six) — because the acceptance
   criterion requires a later reader to check conformance, and parameters living only in code
   are not auditable.
6. **retention: none, ever** (§5 #28) — deletion is what makes "exists but unfindable" possible;
   `missing=1` is a state, not a delete.

**Three schema columns are additions to `research 07`, flagged as such in their own rows**:
`video.clip_uuid` (the recovery anchor — `content_key` is NULL until the hash pass, so a fresh
clip otherwise has no identity), `video.src_device_id/name` (**`research 07`'s schema has no
device column at all**, so the "filter by device" the brief required was unanswerable), and
`video.audio_offset_ms` (the wav's `t=0` inside the clip's timeline).

The `job` table is **referenced, not redefined** — it is lane 08's (`research 08`), and two job
tables is how a repo grows a bug.

**The 11 `UNKNOWN`s each name the experiment that would settle them**, including the one
**BLOCKED ON THE OWNER**: no embedding weights are on disk (B4), so 256d-vs-768d video recall
is unmeasured, and the ~1.5 GB download is his call.

## 8. L4 IS ALREADY WRITING AGAINST A SPEC THAT WAS STILL MOVING — AND HAS THE BLOCKER-1 DEFECT

⚠ **The single most actionable thing in this receipt.** `src/index/` did not exist when I
started; at **12:48** it holds five modules written **while I was still correcting this spec**:

```
__init__.py   2612 B  12:18:57     store.py    17284 B  12:34:52
schema.py    15748 B  12:24:21     search.py   10883 B  12:38:12
selftest.py  42745 B  12:30:48
```

**`schema.py` contains 23 FTS5 references and ZERO triggers** — `grep -i trigger` across
every `.py` in the package returns **no matches**, and `recursive_triggers` appears **nowhere**.
That is precisely the BLOCKER-class defect the reviewer found in my own draft and that my own
DDL gate caught before the reviewer saw it: **FTS5 tables with no triggers means the lexical
surface is permanently empty while every transcript sits in the table** — and because
`integrity_check` reads `ok`, nothing will ever report it.

⚠ **Stated honestly: this may be in-progress work, not a finished defect.** The files were
minutes old when I looked, and L4 may add the triggers next. **It is reported as a
check-now, not a verdict.** The check is one command and takes seconds:

```
grep -ci trigger H:\sotto\_moved\aireplay\src\index\*.py    # 0 => the surface is dead
```

Two other things L4 should re-check against the final spec, because both were **corrected
after 12:1x**: the `segment` **grain** (BLOCKER 2 — no fixed 5 s grid in the schema) and the
`producer` **template** (MAJOR 2 — never a literal `intra=4`).

A bulk snapshot commit `51f84cc` ("freeze: estado do clone … 12:2x") captured my spec
mid-draft. **Nothing of mine was overwritten** — `git show HEAD:specs/04-index-search.md` is my
own earlier draft at 60 247 B; the final 71 334 B is a strict superset.

## 9. WHAT THIS LANE DID NOT DO

- **Did not** edit L4's `src/index/**` even though I found the trigger defect there — it is
  L4's file and the brief forbade touching it. **Reported instead of fixed**, with the
  one-command check.
- **Did not** implement `src/index/**` — that is L4's.
- **Did not** edit `specs/01`, `02`, `03`, any source file, or `AGENTS.md`.
- **Did not** touch the `job` table's design or lane 08's asset identity rules.
- **Did not** resolve the 256d-vs-768d embedding question — **it is blocked on the owner's
  download decision**, and guessing it would be inventing a requirement.
- **Did not** re-litigate anything `receipt-07` settled (RRF k, WAL, fp16-on-disk, no
  reranker, no ANN).
- **Did not** open an audio device, launch a GUI, or leave a visible console window.

## 9. THE ONE THING THE OWNER SHOULD KNOW

The spec is a contract with a lane coding **in parallel**, and one of its two BLOCKERs would
have produced an index that *searches* perfectly and silently returns **stale text** forever
while every health counter reads healthy. That class of bug is invisible to `integrity_check`
— MEASURED `ok` — and invisible to `fts_orphans`. The spec now forbids `INSERT OR REPLACE` on
the text tables, sets `recursive_triggers=ON`, and defines `stale_fts_tokens` to catch it. **If
L4 reads only one section, read §2.4.**

Re-run the gates:

```
py -3 _main\_lane-spec04-ddl-check.py                 # every SQL fence executes; the behaviours hold
py -3 _main\_lane-spec04-replace-trigger-oracle.py    # the REPLACE/recurse bug, NEG arm included
py -3 _main\_lane-spec04-index-cost-probe.py          # the write/lexical/reconcile numbers
py -3 _main\_lane-spec04-doccheck.py                  # no TBD, provenance tags, measured facts present
```