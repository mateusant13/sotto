# Review of LANE L4 — `src/index/` (ShadowPlay clone): schema, FTS5 store, writer, search

> **Provenance of this file.** Written by lane *Persist the L4 and L16 verdicts to disk*
> (`mvs_a29960b9f84d4c8eb9c83fe133df194d`) to satisfy `_main/REVIEW-MODEL.md:41` —
> control **CHK-REV-1**, *"every committed lane has receipts/review-<LANE>.md on disk"*.
> Recovered read-only from `C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite`
> (`file:…?mode=ro`), reviewer session **`mvs_9c1a6ee2dc9049d7af4d6342f8524e9d`**
> (*"L4 reviewer - index and search audit"*, agent `verifier`, `session_type=branch`).
> Source rows: **`local_runtime_message_rows.id = 230082`** (main report, `msg_content`
> 16 282 chars) and **`id = 230487`** (P0-restoration turn, `msg_content` 6 187 chars).
> Recounted live, not taken from a prior lane's census: the session holds **40 message
> rows / 38 assistant**, matching the recovery lane's snapshot.
> **This file is a transcription, not a review.** Nothing in it was re-measured by me except
> the four facts explicitly labelled *verified by the persisting lane*, below.

---

## ⚠ STANDING HAZARD — READ BEFORE ROUTING ANY `file:line` IN THIS FILE

Three of the five files this review cites are **DELETED in the working tree**, and two more
are modified. Every `file:line` below is exact against commit **`9cb9eb2`**, which is
**12 commits behind `HEAD` (`cdfffda5842743ba4753cf1088fa5b9eae3f16a9`)**.

*Verified by the persisting lane*, `git status --porcelain=v1 -- src/index` (rc=0):

```
 D src/index/__init__.py
 D src/index/schema.py
 M src/index/search.py
 D src/index/selftest.py
 M src/index/store.py
?? src/index/_index-green-probe.py
?? src/index/schema.sql
```

Consequences, stated plainly:

1. **`schema.py` and `selftest.py` no longer exist on disk.** Every citation into them
   (S1, S2, S3, S8) is a citation into a file that is gone. Do not open it; read it at `9cb9eb2`.
2. **A new `schema.sql` exists** and is **untracked**. The schema has moved from Python to SQL.
   Whether S1–S3, S7 or S8 survive that rewrite is **unknown and was not checked by anyone.**
3. **The reviewer's own reported HEAD did not match either sha.** He wrote *"`HEAD` moved under
   me (`f6d9fe3` → `d13d4239`)"*. `9cb9eb2` — the sha the recovery lane named as the citation
   base — is **not** the sha the reviewer recorded, and is not `HEAD` today.
   Both `f6d9fe3` and `d13d4239` **do** exist as commits. `9cb9eb2` **does** exist and **is** an
   ancestor of `HEAD` (`git merge-base --is-ancestor` rc=0). *Verified by the persisting lane.*
4. *Spot-check, verified by the persisting lane:* `git show 9cb9eb2:src/index/schema.py` is
   371 lines, and lines **298–302 are exactly the backfill block S1 cites**. So the citation
   base is the right one for S1 — but this is **one** spot-check, not a re-verification of
   all nine findings.

**Therefore: do not treat any line below as a live fix site.** Confirm the file exists and the
line still means the same thing before routing.

---

## Verdict

The reviewer's own final line, verbatim, from his **last** turn (`id 230487`):

> Does your implementation meet the spec? NO - criteria 1, 2, 3 and 6 are met and the gate is genuinely sound, but criterion 5 fails on the declared interface (L1 has no producer for `clip_id`/`started_at_s`, and `producer` is a forbidden literal), and three defects the gate cannot see remain open: `migrate()` is O(N²) on every open so the store cannot be opened twice at 20k rows, `offset_s` timestamps are stored unseekable, and the declared OCR search surface does not exist.

The **main report** turn (`id 230082`) ended with a near-identical variant, quoted here because
the difference is itself evidence — it names the arm-C attack, which the later turn compressed away:

> Does your implementation meet the spec? NO - criteria 1, 2, 3 and 6 are met and the gate is genuinely sound (arm C really goes red, as do four mutations of my own), but criterion 5 fails on the declared interface (L1 has no producer for `clip_id`/`started_at_s`, and `producer` is a forbidden literal), and three defects the gate cannot see remain open: `migrate()` is O(N²) on every open so the store cannot be opened twice at 20k rows, `offset_s` timestamps are stored unseekable, and the declared OCR search surface does not exist.

**Scorecard against the acceptance criteria** (reviewer's own, verbatim):

| # | Criterion | Result |
|---|---|---|
| 1 | Schema + FTS5 probe | **MET** (OCR channel missing, S3) |
| 2 | Writer upserts clip + transcript | **MET** |
| 3 | Text search + time/device/duration filters | **MET** (hand-recomputed) |
| 4 | Migration-safe | **MET at fixture scale; broken at scale** (S1) |
| 5 | **Declared interface** | **NOT MET** (S5 unproducible fields; S2 wrong timestamps; S6 false producer) |
| 6 | Gate A/B/C/D incl. real control | **MET, and stronger than claimed** |

**"The one thing that cannot work" — S1.** Reviewer's words: *"Not a performance nit: at
20 000 transcripts a single `open_index()` holds the write lock for 22.3 s executing a scan
that provably changes nothing, and the second process to open the file dies with `database is
locked`. The store is a single file that cannot be opened by two things at once at the corpus
size the spec sizes itself for. It is unfixable with an index (fts5 virtual tables may not be
indexed) and invisible to the gate, which only ever builds 9 segments."*

---

## POPULATION and WINDOW

**The reviewer DID state a POPULATION and a WINDOW for the review itself.** They are carried
over here intact — this is his own table, not a per-claim figure and not a reconstruction.

| done | POPULATION | WINDOW |
|---|---|---|
| Ran the gate, real exit code | **1** invocation, 5 arms, **106** named checks | 2026-10-07 **12:53:37–12:53:40** BRT, scratch forced to `G:\Temp\sotto-l4-verify` so the repo stayed clean |
| Attacked arm C | **2** lane mutants × 1 run; **4** unseen mutants of mine × 1 run | same session, 13:0x BRT — all 6 rc≠0 |
| Probed FTS5 independently of the lane | **1** interpreter (Py 3.11.8 / SQLite 3.43.1) | point query; **1 build only** |
| Recomputed searches by hand | **4** queries × (1 raw SQL + 1 `search_text`) | whole library, 6 clips / 9 segments; 3/4 agree exactly, the 4th diverges and my reading of it is interpretation |
| Measured `migrate()` scaling | **6** corpus sizes: 1k/2k/4k/8k/16k/40 009 transcripts | fresh db per point, FTS complete before timing; **n=1 per point, no variance** |
| Lock-conflict + race | **1** trial; then **2** processes, **1** trial | 20 000 transcripts; **n=1** |
| Checked the interface against real producers | **1** struct, **16** `CutResult` fields; `runner.py:259-306`, `runner.py:231-239` | `replay.h:65-82` |
| Diffed code against the parallel spec | **9** findings (2 blocker, 3 high, 3 medium, 1 low) over **6** criteria graded 6/6 | spec sha `27303FE2F26D2301`, **rewritten by L6 at 12:49:59 mid-review** |
| Proved the repo untouched | **12** files byte-compared (5 `.py`, 6 `.pyc`, 1 spec) | 12:48 → 13:02 |

**The reviewer's own caveat on this table, verbatim:**

> Every timing above is **n=1**. The O(N²) claim does not rest on them — it rests on the query plan (`SCAN t` + correlated subquery re-scanning the FTS virtual table per row) plus `virtual tables may not be indexed`, which are structural. The curve corroborates.

> **Correction to a claim in my dispatch brief:** the brief said *"the reviewer declined to run
> the gates."* **That is false, and I am not laundering it into this file.** The reviewer ran
> the gate and reported a real exit code: *"`LANE4-GATE PASS`, exit 0; A 62/0, B 23/0, C 8/0,
> D 13/0"* (62+23+8+13 = **106**, matching his own P0 table). What is true is narrower: he
> declined to run the **spec's own corpus size** (120 201 segments), and every timing he quotes
> is **n=1**. Those are different claims and only the second one is his.

---

## Findings

Nine findings: **2 blocker, 3 high, 3 medium, 1 low**, as the reviewer counted them.

| id | severity | file:line | what was claimed | what is actually there | the fix (reviewer's words) | owning lane |
|---|---|---|---|---|---|---|
| **S1** | BLOCKER | `schema.py:298-302` (backfill) called unconditionally from `schema.py:341` (`open_index` → `migrate`), inside `BEGIN IMMEDIATE` (`schema.py:270`) | `migrate()` is idempotent; arm D proves two writers never see a locked db | **O(N×M)**, runs on *every* open. Measured no-op re-run (`rows missing = 0` — it did *nothing*): 1 000→43.8 ms · 2 000→291.6 ms · 4 000→753.5 ms · 8 000→3 189.8 ms · 16 000→13 419.6 ms. ×4.2 per doubling = quadratic. `EXPLAIN QUERY PLAN`: `SCAN t` → `CORRELATED SCALAR SUBQUERY` → `SCAN f VIRTUAL TABLE INDEX 0:` per row. `CREATE INDEX … ON transcript_fts(seg_id)` → `virtual tables may not be indexed`, so **it cannot be fixed with an index**. At 20 000 transcripts one `open_index()` holds the write lock **22.3 s**; the second process dies `sqlite3.OperationalError: database is locked` (11.05 s, the 10 s busy_timeout). Spec sizes this store for 120 201 segments. | *"run the backfill only when the FTS table was just created in this call (it already tracks `created`; set a flag), and/or guard the whole migration on `PRAGMA user_version` actually changing. One line: `if created_fts_now: backfill`."* | L4 (`src/index/`) |
| **S2** | BLOCKER | `runner.py:233`; `store.py:304-305`; `selftest.py:140` | timestamps are clip-relative; the declared interface writes them correctly | `runner.py:233` emits `"start": round(cfg.offset_s + a, 3)` — **absolute within the wav** — and `store.py:304-305` stores it as clip-relative via `_ms()`. `grep audio_offset_ms src/index/` → **zero hits**; the column does not exist. Measured: `offset_s=900`, `segments[0].start=914.32` → stored `segment.start_ms = 914320`; `search_text` hands the UI `start_ms=914320` on a **120 s** clip → the hit is **unseekable**. The spec's own registered fixture is `plain-3600s.wav[900,1020)` — offset 900 (spec §1.3). Gate blind spot: `selftest.py:140` hardcodes `"offset_s": 0.0`, so all 62 arm-A checks pass with this live. | *"add `video.audio_offset_ms INTEGER NOT NULL DEFAULT 0`; store `start_ms = audio_offset_ms + round(start*1000)` per spec §1.3; set the arm-A fixture to `offset_s=900` and assert `914320 - audio_offset_ms`."* | L4 + L1 |
| **S3** | HIGH | `schema.py:110-112` (the claim); `schema.py:114-127` (the declared `ocr` table) | *"FTS5 over `ocr.text_norm` is the REQUIRED lexical baseline for game tokens like `ERRO 0x80070005: ACESSO NEGADO`."* | The OCR lexical channel **does not exist**. `grep ocr_fts src/index/` → zero. `search.py` joins `transcript_fts → transcript → segment → video` only. Reviewer inserted an `ocr` row with that exact text: `search_text(con,"negado")` → **0 hits**, `search_text(con,"erro")` → **0 hits**. The declared `ocr` table is write-only dead weight. | *"add `ocr_fts` + the reader join, or delete the claim at `schema.py:110-112`. One or the other — the comment as written is false today."* | L4 |
| **S4** | HIGH | code `store.py:12-13`, `schema.py:77` **vs** spec §2.1 T0 (normative) and §2.5 | spec: write `video(…, state='cutting', added_at)` in its **own commit BEFORE** the remux; *"a file with no row is invisible forever"*; §2.5's ladder scans `state='cutting'` | Code fires *"right after `perform_cut()` returns ok and `Mp4Writer::close()` has written the `moov`"* — **file first, row second**. `schema.py:77` defaults `state='recorded'`; **nothing ever writes `'cutting'`**, so **§2.5's repair ladder has no producer at all.** As written, the code loses clips in the one way its own spec calls unrecoverable. | *"the **spec wins** — this is a correctness invariant, not a naming preference, and it changes L1's call site. Add a T0 `ingest_clip_anchor()` before remux, then the existing call as T2."* | L4 + L1 |
| **S5** | HIGH | `store.py:21-22` (`clip_id`), `store.py:31-32` (`started_at_s`); consumer `search.py:66-71`; producer `replay.h:65-82` | `store.py:21-22` *"**`clip_id` TEXT REQUIRED** … stable identity, L1's to mint"*; `store.py:31-32` *"`started_at_s` … epoch seconds, the clip window START (not the cut time): this is the axis a library-wide time filter runs on."* | **The declared interface cannot be called by the real L1.** `CutResult` (`replay.h:65-82`) has **no** `clip_id` and **no** `started_at_s`; it carries `base_abs`, `end_abs`, `base_qpc_ns`, `cut_qpc_ns`, `path`, `clip_seconds`, `bytes`. `grep 'clip_id\|clip_uuid\|started_at_s'` across `src/capture/*.{cpp,h}` → **zero matches**. L1's first call raises `ValueError: index: clip payload has no clip_id; refusing to invent one`. Even with a minted id, `started_at_s` — the axis `search.py:66-71` filters on — is `NULL`, so `since_s`/`until_s` match nothing. | *"in the receipt, name who mints `clip_id` and from which `CutResult` field (e.g. `base_abs`/`cut_qpc_ns` → epoch), and give the exact L1 line that fills `started_at_s`."* | L1 (mint) + L4 (receipt) |
| **S6** | MEDIUM | `store.py:92`, `store.py:53-54`; real payload at `runner.py:264`, `runner.py:267-278`; ingest at `store.py:284-298` | `PRODUCER_ASR = "asr:parakeet-tdt-0.6b-v3:int8"` is the producer tag; `store.py:53-54` claims it reads "`segment_mode`, `quantization`, `model_dir` for the producer tag" | **`producer` is a hardcoded literal** — *"the precise thing spec §1.2 / #27 forbids by name"*, whose rule is *"**TEMPLATE**, not a literal … hard-coding would be a lie for any other run."* And `ingest_asr_done` **never reads those keys** (only `segments`, `n_segments`, `text`, `store.py:284-298`). The real `done` carries `quantization` (`runner.py:264`) and `threads.intra/inter/model_name/session_providers` (`runner.py:267-278`); all ignored. **An fp16 row would still claim `int8`.** | *"build the tag from `done` per spec #27; delete or fix `store.py:53-54`."* | L4 |
| **S7** | MEDIUM | `store.py:100-115` (`normalise_text`); assertion `selftest.py:259-261` | the LIKE fallback finds Portuguese | **it cannot.** `normalise_text` does NFKC + casefold but **keeps diacritics** (NFKC ≠ NFD; `'ã'.isalnum()` is True). Measured: FTS5 `proxima`/`próxima` → 2/2; **LIKE `proxima` → 0**, LIKE `próxima` → 2. `selftest.py:259-261` asserts this as expected (honest), but on any Python without FTS5 the pt-BR search box returns nothing for a keyboard-typable query — weaker on exactly this corpus. | *"in `normalise_text`, decompose (`NFKD`) and drop combining marks; both paths then fold, at zero cost."* | L4 |
| **S8** | MEDIUM | `schema.py:335-340` (pragmas); `store.py:339-346`; spec §1.1 | four spec-mandated pragmas are set | `cache_size=-65536` (the ARM C *"database disk image is malformed"* evidence), `recursive_triggers=ON` (the measured `INSERT OR REPLACE` blocker), `mmap_size=0`, `busy_timeout=5000` are all **absent**. `schema.py:335-340` sets only busy_timeout (10 000), WAL, `synchronous=NORMAL`, `foreign_keys`. `grep` finds `cache_size` only inside a docstring. | reviewer gave no one-line fix; he states the `recursive_triggers` half is *"defence by discipline, not by the pragma the spec calls the second line of defence; it goes live the moment anyone adds a `REPLACE`."* | L4 |
| **S9** | LOW | multiple — see note | spec/code parity | Remaining divergences: no `meta` table (spec: *"not optional"*; `search_mode`/`tokenizer`/`rrf_*` are not recorded on disk, so `index_info` re-derives them from code) · `video.id` `TEXT PRIMARY KEY` vs spec `INTEGER PRIMARY KEY` + `clip_uuid TEXT NOT NULL UNIQUE` · no `produced_by`, `audio_wav`, `codec` · one `source_device` vs spec's `src_device_id`+`src_device_name` · `state` default `'recorded'` vs `'cutting'` · `added_at_s REAL` vs `added_at INTEGER` · `transcript` lacks `n_chars`/`asr_wall_s`/`asr_rtfx` although the payload **has** `chars`/`wall_s` · `producer`/`model_sha256` nullable vs NOT NULL · `search_text` has no keyset cursor, no `order`, no 200 hard cap (spec #22), and **no RRF/vector fusion at all** (spec §0 headline). | *"the **code** wins on naming/columns (`src_device`, `h264_path`, `added_at_s`) … The **spec wins** on the four things that are correctness invariants, not taste: **S4**, **S2**, **S6**, and the `meta` table. Those need code changes; the rest need one reconciliation edit to the spec."* — **never half.** | L4 + owner |

---

## UNVERIFIABLE / do not route as fixes

Everything in this section is drawn **only** from the reviewer's own hedges. Each line is
either his verbatim text or a direct restatement of it. **Nothing here is a finding. Do not
open a lane on any of it.**

1. **`VBOX-9 CLIPID-NO-PRODUCER` is INVALID — the reviewer says so himself.** His named
   verification box reads *"`VBOX-9 CLIPID-NO-PRODUCER` **invalid, no denominator**"*, and in
   his own "what I did NOT do": *"**Did not give `VBOX-9` a denominator.** I grepped
   `src/capture/*.cpp`/`*.h` without recording how many files, so 'zero producers' is
   currently an unbounded negative. **That is my own gap, and it is the first item to close.**"*
   **S5's headline negative therefore rests on an unbounded grep.** He still rates S5
   *"pending `VBOX-9`'s denominator"* — i.e. he did not certify it.
2. **S8's `recursive_triggers` half is unrepresentable today.** His words: *"The
   `recursive_triggers` hole is genuinely unrepresentable **today** — `store.py:339-346` uses
   explicit `DELETE`+`INSERT`, never `REPLACE`."* An arm cannot fail on a defect that has no
   reachable path. It is a latent risk, not a reproducible defect.
3. **S8/S9 are rated as divergences, not defects.** His own confidence line: *"S8/S9 high as
   divergences, **low as defects**."* Do not promote a divergence into a blocking defect.
4. **The 4th hand-recomputed search is interpretation, not a defect.** *"3/4 agree. The 4th
   (`radio`: 5 vs 3) is **my** weaker LIKE baseline being outclassed by folding — **not** a
   defect; it is the folding working."*
5. **The spec citations are pinned to a sha that was rewritten mid-review.**
   *"L6 rewrote it during my review; my §1.1–§2.5 citations are pinned to one sha and may be
   stale."* Spec sha at read time: `27303FE2F26D2301`, rewritten **12:49:59** by L6. Every
   spec citation below is as-of that sha.
6. **He did not run at the spec's own corpus size.** *"My ceiling was 40 009, so **every
   latency I quote is a lower bound** on the real cost."* The 22.3 s figure is at 20 000
   transcripts; the spec sizes for 120 201 segments. **Do not read 22.3 s as the real cost.**
7. **He did not re-run the crash-during-write protocol** from `receipt-07` against this
   schema — *"the store inherits that claim on trust."*
8. **He did not grep for call sites** of `ingest_clip`/`ingest_asr_done` outside the gate.
   His words: *"Unchecked, and it should be checked before anyone rewrites the interface."*
9. **S2 and S6 rest on a payload he reconstructed from source**, not on real
   `runner.transcribe()` output — he never ran the ASR or opened an audio device.
10. **S4 and S5 are argued from `replay.h` and an absence, never from a live cut.** *"Did not
    invoke the L1 binary or perform a cut."* He states what would move S4: *"an L1 call site
    showing `ingest_clip` is the first write."*
11. **The vector/ANN half was never tested.** *"Did not test the vector/ANN half — L4 never
    wrote it and says so; **it is not this lane's deliverable**."* Its absence is not a defect.
12. **One repo artifact changed and he could not fully exonerate himself.**
    `__pycache__/store.cpython-311.pyc` 22 149 B/12:33:16 → 22 307 B/13:01:14. His words:
    *"**I did not cause it** … Residual uncertainty: **I cannot prove a negative about every
    syscall**; the evidence chain is circumstantial but consistent."* Treat the `.pyc` as
    unattributed, not as damage and not as his.
13. **Every timing in this review is n=1**, per his own table and caveat. Not one of them has a
    variance figure.

---

## The reviewer's own gate doubt

> **Gate-doubt:** sensitive but small — different properties. All six mutations went red, four of them mine, so the instrument can say no. But every one hit a path arm A already exercises. **All three blockers live where arm A never looks** — corpus scale, nonzero `offset_s` (fixture hardcodes `0.0`), and the OCR channel (no `ocr_fts` exists to break). The lane could fix all nine findings and this gate would print the same 106 passing checks with nothing moving. The fixture is also self-referential: arm 0 locks the text against the same artefact the assertions were built from, so a drift moves both sides together.

And, from the main report, his verdict on the gate itself — which cuts *against* his own
"gate is sound" claim and should travel with it:

> The gate is genuinely good and I could not break it: exit 0 on the exact hashed bytes; arm C builds real mutants in a COPY with a unique-anchor guard that fails loudly rather than faking a RED; **my four unseen mutations all went red**. … The migration is genuinely additive, the v0 row survives with its values, a newer version is refused loudly, and `INSERT OR REPLACE` is correctly avoided. Arm D's overlap is a real clock intersection, not back-to-back theatre. Docstrings state their own unknowns.

**Read the two together.** The gate is sound *as far as the gate looks* — and the reviewer's
own doubt is that all three blockers are outside its field of view. A green gate from this
lane is not evidence that S1–S3 are fixed.

---

## SELF-AUDIT

Carried over from the reviewer's own `## SELF-AUDIT` (turn `230487`), verbatim.

**Review by another subagent:** none. I am the first and only reviewer of L4; nothing has reviewed this report.

**Checkboxes (mechanical, re-runnable):** `VBOX-1 GATE-REPEATABLE` n=1, underpowered · `VBOX-2 MIGRATE-NOOP-COST` **fails** 22 268 ms · `VBOX-3 MIGRATE-QUADRATIC` **fails** 4.21/4.23 · `VBOX-4 FTS-PLAN-SHAPE` **fails** · `VBOX-5 FTS-NOT-INDEXABLE` **fails** · `VBOX-6 SECOND-WRITER-LOCKS` **fails at 20k**, passes at 9 · `VBOX-7 OCR-UNREACHABLE` **fails** · `VBOX-8 OFFSET-SEEK` **fails** · `VBOX-9 CLIPID-NO-PRODUCER` **invalid, no denominator** · `VBOX-10 INDEP-CONTROL` **passes 4/4** · `VBOX-11 FTS5-BUILD-PROBE` **passes, 1 build** · `VBOX-12 DIACRITIC-FOLD` **underpowered, n=1 word**. **Nine fail or are invalid.**

**Protocols missing:** the POPULATION+WINDOW law (violated in my first response, corrected here — folding rests on 1 word, not 6 probes); no second reviewer; no ASR/audio protocol; no crash protocol; no run at spec corpus size.

**Confidence and what moves it:** S1 high (structural) · S2 high, would downgrade if L2 guarantees `offset_s == 0` — I found no such guarantee · S3 high · S4 medium-high (argued from §2.5's ladder having no producer) · S5 medium-high, pending `VBOX-9`'s denominator · S6 high · S7 high on measurement, medium on severity · S8/S9 high as divergences, low as defects.

Additional self-audit text from the main report turn (`230082`), verbatim:

- **Confidence high** (direct measurement, reproducible): S1, S2, S3, S5, S6, S7 — each recomputed, not inferred.
- **Confidence high** that the gate is sound; I attacked it and failed to produce a false green.
- **Would move S4 from "contradiction" to "confirmed defect":** an L1 call site showing `ingest_clip` is the first write. I reasoned from the spec's own recovery ladder having no producer.
- **Named verification boxes I created:** *VERIFIER-HAND-SQL* (independent recount), *VERIFIER-INDEP-CONTROL* (4 unseen mutations), *VERIFIER-MIGRATE-SCALE*, *VERIFIER-LOCK-CONFLICT*, *VERIFIER-OCR-SEARCHABILITY*, *VERIFIER-PRODUCER-CONTRACT*.
- **Reviewer of this review:** none. I am the first reviewer of L4.
- **No stray window:** every process went through `py -3 -B` / `CREATE_NO_WINDOW`; I launched no `python.exe` from a visible shell.

**What the lane got right** (reviewer's own section, abridged only by dropping his MATCH-safety detail): the gate is genuinely good; FTS5 is probed not assumed and its claim checks out; the tokenizer is the correct one and demonstrably folds pt-BR accents both ways; MATCH quoting is genuinely injection-safe — 13 hostile queries including `segunda-feira`-shaped input and a bare `*` do not raise, because `fts5_match_expression` emits `"tok"*`.

---

## SELF-AUDIT of THIS persisting lane

Stated separately so it can never be confused with the reviewer's.

**Reviewer position.** Read-only. I opened the runtime store with `mode=ro` and wrote no
byte to it. I did **not** re-run the gate, re-measure `migrate()`, re-probe FTS5, or re-open a
single finding. I transcribed and I labelled.

**What I verified myself (4 facts, all measured, not assumed):**

| fact | command | rc | result |
|---|---|---|---|
| `review-L*.md` did not already exist | `Get-ChildItem receipts -Filter 'review-*.md'` | — | **NONE** — 37 receipts on disk, 0 review files. So no overwrite risk. |
| the three cited files are deleted | `git status --porcelain=v1 -- src/index` | 0 | `D schema.py`, `D selftest.py`, `D __init__.py`; `M store.py`, `M search.py`; `?? schema.sql`, `?? _index-green-probe.py` |
| `9cb9eb2` is an ancestor of HEAD, 12 commits back | `git merge-base --is-ancestor 9cb9eb2 HEAD` | 0 | confirmed; `HEAD` = `cdfffda5842743ba4753cf1088fa5b9eae3f16a9`; branch `main` |
| one citation resolves at `9cb9eb2` | `git show 9cb9eb2:src/index/schema.py` | 0 | 371 lines; **298–302 are exactly the S1 backfill block** |

**What I did NOT verify.**

- That **any** finding other than S1's citation still reads as claimed. One spot-check is not a
  re-verification of nine findings.
- Whether the findings **survive** the working tree's rewrite of the schema out of Python and
  into `schema.sql`. **Nobody has checked this**, including the reviewer. It is the single
  biggest open question about this file.
- The `9cb9eb2` sha came from a **dispatch brief**, not from the reviewer's own text. He
  recorded `f6d9fe3 → d13d4239` instead. I could not reconcile the two, so I disclosed both.
  All three shas exist as commits.
- Every figure in the Findings and UNVERIFIABLE sections is **the reviewer's**, at n=1, from
  2026-10-07 12:49–13:02 BRT, against a tree that has since moved 12 commits.
- I did not check whether `_index-green-probe.py` (untracked) is related to this lane.

**Per-claim confidence in MY OWN contribution:** high that the four facts in the table above are
true; high that the transcription is faithful to the store bytes; **zero** confidence that any
finding is still live — the citation base has moved and two of the five files no longer exist.