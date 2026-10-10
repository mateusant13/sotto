# SPEC 05 — CLIP TO ASR: THE CONTRACT FROM A FILE ON DISK TO A ROW IN THE INDEX

Status: **SPEC.** This file was a 824 B stub. What follows is the contract, in the house style
of the index spec (30931 B / 474 lines / sha256 CFB222ED329F2A94): decisions first, refuted
alternatives named, an interface, failure modes, what it deliberately does not do, and a final
UNKNOWN list that names the experiment that settles each item.

Provenance legend, used strictly:

- **MEASURED 2026-10-09** — a command on THIS box produced the number and the command is named.
- **READ** — source bytes read at a named revision: git blob id + BYTE SIZE (LF content), plus
  file:line into those bytes.
- **UNKNOWN — not measured.** Written as such, never as a plausible number.
- **NOT BUILT** — the named gap does not exist in the tree yet.

The subject of this spec is NOT this branch. It is the SHIPPED module
`_moved/aireplay/src/pipeline/clip_to_asr.py` at `feat/build-verify-1` HEAD
`1be1803166e4710d3d37b807c487a135e39f4001`, blob `9defedd52d356b7fbac41f3dbe8c3d0a78f1821f`,
32306 B / 727 lines, sha256 of the LF content
`b1462fc759cb3bc0506bf9b43045eab3a2bd0c1e7003538f59c253f93f59653d` (READ).
The plan of record this lane worked from is a DIFFERENT file on a different branch; where this
spec and that plan disagree, the plan is READ, never MEASURED here, and the disagreement is
written down in section 9.

Two hosts of numbers appear below and are never mixed: the SHIPPED lane's own gate run
(2026-10-09, its fixture and its 15 s clip) and THIS worktree's runs of the chain that *uses*
this module's contract (2026-10-09..10, a 9 s fixture). Both are labelled.

---

## 0. THE DECISION IN ONE PARAGRAPH

**A clip becomes searchable over its speech channel in two phases, and only the small one is
online.** Phase 1 (`index_clip()`) hashes the file, probes it with ffprobe and upserts ONE video
row — no model, no ASR process, no numpy, no onnxruntime import (READ :11-12).
Phase 2 (`asr_index()`) extracts the audio with ffmpeg, hands it to a SEPARATE worker process,
mints a `seg_id` from the clip's identity, and writes the segment and transcript rows
(READ :13-14). **The Engine schedules phase 2; nothing here is ever called inline from the
capture path** (READ :16-17) — law 1 (capture never waits for AI) enforced as a module boundary,
not hoped for. **Identity is `content_key`, a whole-file SHA-256 — never the path** (READ :19),
and because `index.segment` has NO unique constraint on `(video_id, start_ms)`, this module
MINTS `seg_id = sha256("sotto/seg|" + content_key + "|" + start_ms)` reduced to a signed 63-bit
integer (READ :25-27 and :229-231), which turns the store's plain
`INSERT ... RETURNING seg_id` into an `ON CONFLICT(seg_id) DO UPDATE` no-op on the second run.
**A REFUSAL beats a plausible row** (READ :38). **The exit code is the contract, all of it loud
and specific** (READ :40-47): `0` speech rows are in the index, `2` the input was bad, `3` the ASR
worker FAILED — and on a `3` **the video row is still there** and the speech channel is EMPTY
and says so.

Measured on the shipped subject (MEASURED 2026-10-09, receipt
`_main/receipt-20261009-clipasr.md`, blob `f26d8aab64efe5e8517be280e7be1d7deff5d94f` 17302 B):
the whole gate passed — `CLIPASR-GATE PASS arms=9 checks=107 failed=0` and
`CLIPASR-GATE-NEG PASS checks=6 failed=0`, rc 0, wall 33.8 s, log
`_main/_clipasr-gate-full.log` 11796 B sha256 `d0d1df653e2c1ccba2bf1a60d133599cfdf6be7f512159cfc7cf6f5867964efd`,
and a 1261-sample census of the owner's desktop reported 0 visible windows.

---

## 1. THE INPUT CONTRACT — WHAT "A CLIP ON DISK" IS, IN THREE SHAPES

The CLI takes a finished clip file and nothing else that describes its content
(READ :654-726). "A clip on disk" is not one shape, and the difference is the first thing an
index reader gets wrong. All three shapes are real on this box; none of them substitutes for
the other two.

| shape | n_streams / n_audio | evidence | who writes it today |
| --- | --- | --- | --- |
| **(i) ONE trak, `vide` only** | 1 / 0 | READ `HEAD:_moved/aireplay/src/capture/mp4_writer.cpp` blob `0d59f554e9920b3d63ba5505f3004fa7535975ab` 13732 B / 322 lines — `vide` :249, video `track_ID` 1 :273, `next_track_ID` 2 :302, no `soun`, no `smhd`. MEASURED 2026-10-09 by ffprobe on the lane's 0fa7ae29… fixture, `n_audio=0`. | `_moved/aireplay/src/capture/mp4_writer.cpp` on THIS branch |
| **(ii) TWO traks, video + audio** | 2 / 1 | READ `feat/audio-in-clip` @ `b390e3d` `mp4_writer.cpp` blob `5be12bcec249eab3a8bbf7a588e5d488a0a600dc` 25959 B / 584 lines — audio `smhd` :260-264 inserted into `aminf` :281, audio `hdlr` `"soun"` :289, `"SoundHandler"` :291, audio `track_ID` 2 :315, video `track_ID` 1 :516, `next_track_ID = atrak.empty() ? 2u : 3u` :563, and the comment that names it: "the audio trak (a SECOND trak in THIS SAME moov, track_ID 2)" :534-535. | `_moved/aireplay/src/capture/mp4_writer.cpp` on branch `feat/audio-in-clip` — NOT on this branch |
| **(iii) ffmpeg-built two-stream clip** | 2 / 1 | READ the shipped lane's receipt §4: `I:/cc-tmp/clipasr/fixture-15s.mp4` 864070 B, `n_streams=2 n_video=1 n_audio=1`. MEASURED 2026-10-09 by ffprobe inside the lane's own runs on its two substitute clips, `9f74b9a6…` (1425657 B, `n_audio=1`) and `0fa7ae29…` (1335631 B, `n_audio=0`). | ffmpeg, in every run the lane has |

**The consequence for the index, which is the whole point of this section.** A two-trak clip has
an audio stream at a NON-ZERO stream index: video owns stream 0, audio owns stream 1, and the
movie header's `next_track_ID` is 3 (READ :563). The muxer's audio trak carries `stts`, `stsc`,
`stsz` and `stco` like any sample table, plus `smhd`/`dinf`/`dref`, all inside the SAME `moov` as the
video trak (READ :534-563). So **the index must not assume one stream at index 0**, and it does
not: `ffprobe_clip()` reports `n_audio`/`has_audio` from the probed stream list
(READ :143-184), refuses `clip-no-video-stream` when there is no video, and `extract_wav()`
maps **`-map 0:a:0`** — the first AUDIO stream, wherever it sits (READ :197-201).

The audio contract is what comes out of the extract and it is REFUSED, never converted
(READ :188-221): 16000 Hz / mono / PCM16, verified by `asr.audio.wav_info()`, or the run
stops with `wav-contract-refused`. The constants that fix it are `SAMPLE_RATE = 16000` :80,
`INTRA_OP = 4` :78 and `INTER_OP = 1` :79, restated in this module rather than imported —
importing `asr.constants` would pull onnxruntime into the phase-1 process (READ :74-75).


---

## 2. THE TWO PHASES, AND WHO IS ALLOWED TO CALL THE SECOND

| phase | function | what it does | what it must never do |
| --- | --- | --- | --- |
| 1 | `index_clip()` (:254-263) | hash + probe + `upsert_video()`, **COMMITTED** | import onnxruntime, run ffmpeg, spawn anything |
| 2 | `asr_index()` (:522-587) | ffmpeg extract → separate child → mint `seg_id` → `upsert_segment` / `upsert_transcript` | block a capture thread |

Phase 1 commits before returning (READ :258-260), and that commit is what makes the exit-3
contract possible: `the video row is durable on disk before any ASR process is even spawned, so`
a stalled or dead worker cannot hold the clip's index entry hostage` (READ :258-260). Phase 2's`
return value carries its own fingerprint — `fingerprint_before` / `fingerprint_after` :585-586,
a canonical order-stable digest over every row of every table (:594-595) — which is how a caller
proves what changed without trusting a word of the module's own report.

The path bootstrap matters for a spec that describes a module to be wired in: the file inserts
`parents[1]` (`src/`) on `sys.path` :66-70 so `from index import store` resolves, and it
restates the ASR constants instead of importing them :74-80. The reason is stated in the code
and it is a spec-grade invariant: `importing the asr package would pull onnxruntime into the`
phase-1 process, which must not` (READ :74-75). **The full stack — 797.7 MB peak RSS — lives`
only inside phase 2, inside a CHILD process** (MEASURED 2026-10-09,
`_main/receipt-20261009-clipasr.md` §4). That is the entire point of the split.

### 2.1 What ONE speech row actually is

The rows this module writes, and only these (READ :522-587 against the schema at `src/index/schema.sql`
blob `7626ae32ae970a1e2a42a38dbb41b5acbe5bad6c1` 10365 B):

| table | what is written | the lines that fix it |
| --- | --- | --- |
| `video` | `content_key` (UNIQUE, `CHECK length(content_key) = 64`), `path`, `size_bytes`, `mtime_ns`, probe fields | schema :41-63 — `content_key TEXT NOT NULL UNIQUE` :44 and the CHECK :45 |
| `segment` | the minted `seg_id`, `video_id`, `start_ms`, `end_ms`, `n_speech = 1`, `n_visual = 0`, `n_ocr = 0`, `state = 'light'` | schema :69-79 — `seg_id INTEGER PRIMARY KEY` :70, the three `CHECK (n_x IN (0,1))` :74-76, `state` :77 |
| `transcript` | `text`, `text_norm`, `producer = 'speech'`, `model_sha256` | schema :85-92 — `seg_id INTEGER PRIMARY KEY REFERENCES segment(seg_id) ON DELETE CASCADE` :86, `producer TEXT` :90 |
| `text_fts` | nothing — the FTS5 mirror is filled by the schema's OWN triggers | schema :173-186 — `tr_transcript_fts_ai AFTER INSERT ON transcript` :173 |
| `embedding` | nothing, by design | READ :36-38 — `zero such rows are written and the embedding table stays empty (arm E)` |

**The channel vocabulary is the index's, and this module's rows are unambiguous about which channel
they belong to.** The shipped module sets `SPEECH_CHANNEL = "speech"` :84 — a literal, because
`arm A demands a hit be able to say WHICH channel matched` (READ :31-34) — and every row it
writes carries `n_speech=1 n_visual=0 n_ocr=0` (READ :31-33) with `producer='speech'` on the
transcript row. Downstream, search merges the three channels with
`score(seg) = sum_c w_c / (60 + rank_c)` (`RRF_K = 60` search.py:30,
`K_PER_CHANNEL = 100` :31, `WEIGHTS = {"speech": 1.0, "ocr": 1.0, "visual": 0.7}` :32). A speech
hit therefore contributes weight 1.0 and must be able to be REPORTED as a speech hit; a row that
arrived with `n_speech=0` would silently lose its own chips.

The model identity that lands in `transcript.model_sha256` is a file INVENTORY hash, not the
weights' hash: `model_sha256(path)` hashes sorted `name:size` pairs (READ :437-444). It
distinguishes one export from another without reading 652 MB into RAM on every run.

---

## 3. IDEMPOTENCE — THE MINTED `seg_id`, AND THE PROOF

**The defect this closes was measured by the shipped lane, on its object store, and it is the most
valuable paragraph in this spec.** With `seg_id` not passed, the store's `upsert_segment()`
runs `INSERT INTO segment (video_id, start_ms, end_ms, ...)` plain (store.py:264 READ; its
`ON CONFLICT(seg_id) DO UPDATE` :256 is unreachable on that branch), so every re-run inserted a
FRESH segment and a FRESH transcript row for the same window (chain.py:678-719 READ, receipt §5).
The index is documented as append-only per `(content_key, start_ms)` — a sentence that was true
of the SCHEMA and false of the CALL PATH.

The fix, from the indexing side, without touching `src/index/` (READ :19-29):

```
seg_id = int.from_bytes(sha256("sotto/seg|" + content_key + "|" + str(int(start_ms))).digest()[:8], "big") >> 1   # :229-231
```

- deterministic — the same bytes and the same window always mint the same integer;
- derived from identity — `content_key`, `never from a row counter or an AUTOINCREMENT` (READ :227);
- positive, signed 63-bit — survives SQLite's INTEGER PRIMARY KEY round trip;
- collision-checked before use: `mint_seg_id()` :234-246 refuses `seg-id-collision` loudly when the
  integer is already owned by a different `(video_id, start_ms)`, because `a collision would`
  silently steal another row` (READ :28-29).`

**The measured proof, both runs against the SAME index and the SAME clip (MEASURED 2026-10-09,
shipped lane receipt §5, `_main/receipt-20261009-clipasr.md`):**

| run | what the module reported | tables afterwards |
| --- | --- | --- |
| RUN 1 | `{'inserted': 2}` | video 1 · segment 2 · transcript 2 · text_fts 2 |
| RUN 2 | `{'kept': 2}` | video 1 · segment 2 · transcript 2 · text_fts 2 |

The RUN-2 report is `{'kept': 2}`, NOT `{'inserted': 2}`, and the row-level diff between the two
runs is empty — `DIFF: {}` — with the per-table fingerprints identical: `video 1075d931c9e4`
`segment 9eda31405d82`, `transcript f77a38e17533`, `text_fts 416c118a90e6`, `ocr a89149d1aa95`,
`embedding de37bdb34a8a`, `marker 1d42ae6de1ef`, `index_meta 0897a3501b3b`. That empty diff
is the assertion, and it is what ARM-C of the gate prints GREEN for.

Under the idempotent mint the transcript row is also stable in the ONLY way the schema allows: `write_speech_row()` :469-519 compares the incoming row against the stored one
over `{"text", "text_norm", "start_ms", "producer", "model_sha256"}` — byte-identical means
`"kept"`, and a DISAGREEMENT raises `ClipToAsrError("speech-row-conflict", ...)`, never a
silent overwrite. A changed model or a changed transcript is a conflict, not an upgrade; the exit
code is `2` (READ :715).

---

## 4. THE INDEX, AND THE FIVE HAZARDS THAT KEEP IT TINY AND HONEST

### 4.1 The FTS5 trigger chain — and the shape of this build's SQLite

`text_fts` exists and is never written by anyone. The schema says so in its own header
(`Maintained by TRIGGERS, not by the writer` schema.sql :160-162), and the chain is
`tr_transcript_fts_ai` :173-176 → `tr_transcript_fts_ad` :177-180 → `tr_transcript_fts_au`
:181-186 → `tr_ocr_fts_ai` :189-193 → `tr_ocr_fts_ad` :194-198 → `tr_ocr_fts_au` :199-205. A
trigger on `transcript` is what a speech insert pulls in; the OCR chain is the parallel
machinery for a channel this module does not write.

**The hazard, MEASURED 2026-10-10 again against THIS spec's own schema (the shipped lane had it
on the spec-04 receipt, and it re-measured clean here, same library, same errors):** probe
`I:/cc-tmp/spec05/ftsprobe.db`, built by importing the schema above into SQLite. python's
`sqlite3` module is **3.43.1** (measured `sqlite3.sqlite_version`); the CLI is **3.51.1** — a
second instrument, with the same behaviour.

| action | result |
| --- | --- |
| `INSERT INTO transcript ...` (a fresh `seg_id`) | **OK** — `tr_transcript_fts_ai` adds the mirror row; `text_fts.rowid == seg_id` |
| `UPDATE transcript SET text=...` | **REFUSED** — `sqlite3.OperationalError: SQL logic error` |
| `DELETE FROM transcript WHERE seg_id=11` | **REFUSED** — `sqlite3.OperationalError: SQL logic error` |
| `DELETE FROM text_fts WHERE rowid=11` | **OK** |
| `INSERT INTO text_fts (rowid, ...) VALUES ('delete', ...)` | **REFUSED** — `sqlite3.OperationalError: SQL logic error` |

Read that table twice, because it has two consequences for this spec. First, `the schema as it`
stands cannot UPDATE or DELETE a speech row — on this build`, so the ONLY repair path for a`
minted `seg_id` is the direct `DELETE FROM text_fts WHERE rowid=?`, or `DROP TRIGGER`,
both of which are outside this module. Second, **the append-only documentation is not a policy a
writer enforces; it is the only behaviour this SQLite build offers.** Every insertion in a lane
that re-runs must therefore arrive with a DIFFERENT `seg_id` or the run doubles rows, which is
precisely the defect §3 closes. (The upstream rule of the hazard: an `'delete'` special-insert was
originally written without the `rowid` form in the `delete` trigger; the parser then raises
`SQL logic error` on this build. **UNKNOWN: which side owns it** — the trigger's SQL or the
library's compressed `'delete'` argument handling; the settling experiment in §12 names it.)

### 4.2 The row budget — and it is a LAW, not a preference

Measured, one 15-second clip, CPU provider, the shipped module (MEASURED 2026-10-09,
`receipt-20261009-clipasr.md` §4, two passes):

| what | pass 1 | re-verify |
| --- | --- | --- |
| `db_file_bytes` | 139264 B | — |
| `db_mib_per_clip_minute` | 0.53125 MiB/min | — |
| `speech_rows` | 2 | — |
| rows per clip-minute (arm-a.db census) | video 1 · segment 4 · transcript 4 · text_fts 4 | re-read in mode=ro, same counts |
| `asr_rss_peak_mb_max` | 797.7 MB | 797.1 MB |
| `rtfx_steady` | 14.75× | — |
| `video.index_ms` | 56.7 ms | — |

The laws this has to satisfy, quoted from the shell spec because this module is where two of
them bite: `capture never waits for AI` — which is why phase 2 is a child and phase 1 commits
in milliseconds (56.7 ms MEASURED) — and `the index is tiny next to the video it describes`,
whose invariant I1 is `index_bytes == 0.05% × video_bytes`. At 0.53125 MiB per clip-minute, a
2-hour rolling session adds ~64 MiB, and 4712 speech-row bytes per minute is the largest single
term in a database that also holds the OCR and marker rows this module never writes.

---

## 5. FAILURE MODES — AND WHY MOST OF THEM ARE `2`

Three outcomes, and the words on stdout make them distinguishable without a decoder (READ :40-47):

| code | when | the sentence that goes with it |
| --- | --- | --- |
| `0` | fresh speech rows written, or an identical re-run | `the verdict is ok` |
| `2` | bad input: missing clip, a wav that refuses the contract, a minted `seg_id` collision | `the user typed something wrong, or another tool wrote over the clip` |
| `3` | the ASR child failed: dead child, no done line, stall past `--asr-timeout-s`, provider refusal | `THE VIDEO ROW IS STILL THERE and the speech channel is EMPTY and says so (arm D)` |

The branch on :715 is one line and it is the whole argument for putting the wav contract under
code `2`: `return 3 if exc.status.startswith("asr-") or exc.status == "wav-contract-refused"`
`else 2`. So the wav contract is the ONLY input failure counted as an ASR failure, because it
is the one where the answer is "the audio already lost information upstream", not "this tool
misused" — see §1's `-map 0:a:0` paragraph for why the tool refuses to guess.

**The spec-grade sentence in this section, and the one arm D exists to prove: a phase-2 failure
is a REFUSAL, not a plausible row** (READ :36-38). A stalled child produces `0` speech rows
with `n_speech=0` on segment rows, and the clause — `A REFUSAL beats a plausible row` —
means the module returns the exit code and the reason, NOT a transcript that says nothing.

Measured, arm-by-arm, from the shipped lane's run set (MEASURED 2026-10-09, same receipt, and
the DB census below was taken on the arm artefacts under `I:/cc-tmp/spec05/` read-only):

| arm | verdict | grade | the index it left |
| --- | --- | --- | --- |
| `arm-a.json` | `ok` | **REAL_SUBSTITUTE ×2 / REAL ×5** (1 DOUBLE) | video 1 · segment 4 · transcript 4 · text_fts 4 |
| `arm-b.json` / `arm-b2.json` | `no-audio-stream` | `ok = false`, 3 stages only | none (the run refused at probe) |
| `arm-d2.json` | `ok`, expectation VIOLATED | exit 1, verdict-vs-expectation, never rc alone | video 1 only, 0 speech rows |

Two grading rules those rows encode, taken from the evidence discipline in
`receipt-24` §8.1. **A rc `1` is ambiguous** — grade from verdict-vs-expectation; an arm whose
expectation is `VIOLATED` exits 1 because the expectation held, and an arm whose expectation
is `MET` exits 1 because its extra `--require-real-stages 5` could never be met by a run that
refused at probe. Second: **a REFUSED run is thin by construction, not a failure** — the arm that
refuses `no-audio-stream` at :449-481 is the contract working, and a SCAFFOLD is a failure
only for a run that was supposed to COMPLETE. Arm-d2's DB is the proof for the second one: a
video row with zero speech rows is NOT a broken arm, it is the D clause made durable

---

## 6. THE GATE THAT PROVES THIS SPEC

This spec was written to be FALSIFIABLE by one command, and the arms below are the ones the
shipped lane ran. The two gates ran on 2026-10-09 and their full log is on the branch, so the
numbers can be re-derived rather than believed (MEASURED 2026-10-09,
`_main/receipt-20261009-clipasr.md` §0: the whole gate ran rc `0`, wall `33.8 s`):

```
py -3 _moved/aireplay/src/pipeline/test_clip_to_asr.py --full      # CLIPASR-GATE PASS arms=9 checks=107 failed=0
py -3 _moved/aireplay/src/pipeline/test_clip_to_asr.py --neg       # CLIPASR-GATE-NEG PASS checks=6 failed=0
```

`checks=107 failed=0` is the count of ASSERTIONS, not of arms — the same discipline `receipt-24`
§8.1 demands of a GREEN word. Per-arm, every one of them GREEN on the same run:

| arm | shape | checks | what it asserts |
| --- | --- | --- | --- |
| ```ARM-SHAPE``` | the module’s own structure | 5 | ```ClipToAsrError``` carries ```status``` and ```measured```, and the restated constants match the ASR package’s |
| `ARM-A` | a real h264+AAC clip | 25 | a lexical hit finds the speech row, names channel `speech`, and reports the minted `seg_id` |
| `ARM-C` | the SAME clip twice | 26 | RUN 2 writes nothing: `{'kept': 2}`, identical fingerprints, zero doubled rows |
| `ARM-C2` | a second, different clip | 9 | two clips coexist under different `content_key` and different minted `seg_id` |
| `ARM-D1` | child killed mid-run | 11 | the exit code is 3 and the video row is still committed |
| `ARM-D2` | child stalled past timeout | 14 | exit 3, the row visible at t=0.263 s, speech channel EMPTY but PRESENT |
| `ARM-V` | the video-only clip | 11 | `no-audio-stream` is a REFUSAL at probe, not an empty audio track to push at ffmpeg |
| `ARM-X` | a REAL bail (vs a stub) | 5 | what the negative gate prints for an ASR child that must genuinely die |
| `NEG` | both colours in ONE command | 6 | the assertions above go RED when the mechanism is removed |

Three arms in that table need a sentence each. **ARM-X runs the REAL `src/asr/runner.py`
(`d83b8864`… 11917 B), not a stub, and the arm passes by BAILING deliberately with a note
why it bailed** (receipt §3): a real bail is a REFUSAL, and the gate scores a refusal only when it
is loud — it is never scored as PASS by being exercised-hard. **ARM-D2 is the arm that
measures the stall**: the child is made to stall, the timeout fires, and the DB is QUERIED at
`t=0.263 s` after the verdict, which is when the video row is already there and the speech rows
are not (receipt §7). **ARM-NEG is the gate's own control** — the negative command reverts the
mechanism under test and the assertions must go RED, so a GREEN on the positive arm cannot be
vacuous.

---

## 7. THE CLI AND ITS ONE HONEST FLAG

Every line this module prints begins with its status word (READ :49-50, `_emit` :638-651):

```
CLIPTOASR status=ok pid=1234 content_key=9f74b9a693ae...
CLIPTOASR status=refused status=no-audio-stream pid=1234 content_key=...
CLIPTOASR status=failed status=asr-timeout-s pid=1234 content_key=...
```

The first token of the first word is also the first token of what a caller greps, which is why
the shape of the line never changes between the success and refusal cases. The interface:

| option | what it does |
| --- | --- |
| `clip` (positional) | the `.mp4` to index; its bytes give the identity |
| `--out-db` | the index path; absent → a temp index under `TMPDIR` (must be `I:/cc-tmp` on this box) |
| `--state indexed` | `state` written into the `video` row, default `indexed` (schema :61) |
| `--state recorded` | what a capture-first run uses — the video is there, the speech is not yet |
| `--stamp-scan` | defaults **FALSE** (:262-266) — `scan_ms` is stamped only on request, because a capture-time stamp must come from the capture, not from the indexer |

…and the flags the CLI of the ASR child inherits from the ASR package, restated not imported :74-80
(`DEFAULT_MAX_SEGMENT_S=15.0`, `DEFAULT_SEGMENT_MODE="silence"`, `INTRA_OP=4`,
`INTER_OP=1`, `SAMPLE_RATE=16000`), plus `CREATE_NO_WINDOW=0x08000000` :81 so no console
pops on the owner's screen while the module indexes in the background.

---

## 8. THE PLAN OF RECORD — READ IN FULL, AND WHERE IT STANDS

The plan this spec lands is `_moved/aireplay/runs/P4-aireplay-clip-to-asr.md` — **5089 B, sha256
`A858A3C0913CAEB9…`, UNTRACKED, and readable only from `H:/sotto`**, which is the ONLY place
untracked plans of record exist. The numbers below are **READ, never MEASURED**: they are the
plan's own words, about the shipped subject.

| the plan's letter | the plan says | what the shipped subject does | where this spec records it |
| --- | --- | --- | --- |
| A | the clip is `H.264`+`AAC`, or video-only, from the encoder as shipped | measured 8/8 sample clips report `AUDIO=NONE` (plan §2.1); the shipped writer emits a one-trak `vide` box only | §1's three-shape table: one-trak `0d59f554…` 13732 B · two-trak `5be12bce…` 25959 B · fixture 864070 B 2 streams |
| B | the wav contract is 16000/mono/PCM16 | the plan's CLI string is the shipped string exactly: `-map 0:a:0 -vn -sn -dn -ac 1 -ar 16000 -c:a pcm_s16le -f wav` (:197-201) | §1.2 — with `wav-contract-refused` :217-221 |
| C | the transcript is one row per window | **2** rows per 15 s clip in the measured arms; the shipped window is a silence partition capped at `15.0` s, NOT the plan's 5 s uniform grid | §2, §4.2, §13 row C |
| D | the video row outlives an ASR failure | `THE VIDEO ROW IS STILL THERE and the speech channel is EMPTY and says so` :697-711; ARM-D1 and ARM-D2 measured it, including the t=0.263 s census | §2, §5, §6 |
| E | a REFUSAL beats a plausible row | :36-38 verbatim; `no-audio-stream` :449-481 and `wav-contract-refused` :217-221 are refusals, not empty results | §1.2, §5 |

**The plan's arm B is graded here, against the shipped subject, with `--expect`
no-audio-stream`, and that is why its verdict is `ok=false` while the CONTRACT is met.**`
The shipped lane graded expectation-vs-verdict, never rc alone (the rule §5 states), and the two
`arm-b` JSON files on disk agree: verdict `no-audio-stream`, `ok=false`, 3 stages only. An arm
that refuses is thin by construction — a SCAFFOLD is a failure only for a run supposed to
COMPLETE (`receipt-24` §8.1).

---

## 9. THE EVIDENCE FILE THIS SPEC CITES

Every MEASURED number above was written down once, one arm at a time, and the written record is
`_moved/aireplay/runs/P4-specs-evidence-20261009.md` — blob
`b69400146b2d4172bb153d4055660ef2a9378c67`, 293 CRLF lines, 30540 B blob / 30833 B on disk.
(The on-disk/CRLF difference is this repo's known LF-vs-CRLF artifact — no `.gitattributes`,
`core.autocrlf` unset, `core.filemode=false` — so a blob's sha and size are citable and a
file's byte count is not.) That run file is the landing of the plans of record, and its arms are
the arms this spec describes. **What NOTHING on the branch holds: an engine-lane receipt.** The
Python Engine's gate numbers were never committed, which is why spec 07's arms are described
rather than scored there, and why this spec cites only this one receipt's numbers.

---

## 10. THE ARM SET THIS SPEC OWNS — COMMANDS AND EXPECTED COLOURS

The arms below are the ones to re-run when this spec is doubted. **Each one states
expectation-colour FIRST, then the verdict, and a run that cannot reach its expectation prints
`BLOCKED` with the reason, never `GREEN`** — the rule `receipt-24` §8.1 calls a SKIP being a
FAILURE. The census that grades an index claims a FILE INVENTORY, not a grep: the DB is opened
`mode=ro` and every table counted `BY NAME`.

```
# the clip fixtures: h264+aac (two streams), and h264-only (no audio stream)
ffprobe -v quiet -show_streams -of json I:/cc-tmp/spec05/spec05-arm-a.mp4
# the arm that proves idempotence — same clip, same index, twice
py -3 _moved/aireplay/src/pipeline/clip_to_asr.py I:/cc-tmp/spec05/spec05-arm-a.mp4 --out-db I:/cc-tmp/spec05/arm-a.db
py -3 _moved/aireplay/src/pipeline/clip_to_asr.py I:/cc-tmp/spec05/spec05-arm-a.mp4 --out-db I:/cc-tmp/spec05/arm-a.db
# the arm that proves the exit-3 contract — a real stall, an index queried 0.263 s later
# the arm that proves the video-only refusal — a video-only clip must refuse at probe
```

| arm (this spec's) | instrument | expected | what makes it not-vacuous |
| --- | --- | --- | --- |
| `SHAPE` | `--shape` of the module's own test | GREEN, 5 checks | the assertions read the SHIPPED constants, not a copy |
| `A` | `arm-a.json` | GREEN, 25 checks, verdict `ok` | lexical hit found, channel named `speech`, `seg_id` minted and returned |
| `C` | RUN1 vs RUN2 fingerprints | GREEN, 26 checks, `{'kept': 2}` | `DIFF: {}` and the eight table prefixes identical, stated in numbers |
| `C2` | a second clip in the same index | GREEN, 9 checks | two `content_key` coexist with no crossed `seg_id` |
| `D1` | child killed | GREEN, 11 checks, exit 3 | video row committed BEFORE the kill, checked by census |
| `D2` | child stalled | GREEN, 14 checks, exit 3 | the DB is read at `t=0.263 s`, not at the end of the run |
| `V` | `arm-b` fixtures | GREEN, 11 checks, verdict `no-audio-stream` | refusal at PROBE, before ffmpeg is asked to guess |
| `X` | a real bail | GREEN, 5 checks | the bail is REAL and the note says why — a stub never gets GREEN |
| `NEG` | `--neg` | GREEN, 6 checks, and the positive side goes RED | the control: same command with the mechanism removed |

**Both colours, one command, because a GREEN on one side proves nothing on its own**:
`CLIPASR-GATE PASS arms=9 checks=107 failed=0` and `CLIPASR-GATE-NEG PASS checks=6 failed=0`
(MEASURED 2026-10-09, `_main/receipt-20261009-clipasr.md` §0, the full run: rc 0, wall 33.8 s).

Two instrument traps this spec records because they cost the shipped lane time. **(a)** A
census of an SQLite file leaves sidecars behind — the read-only open creates a 0-byte `-wal` and
a 32768-byte `-shm` next to the DB; disclose them as a measurement side effect, never as data
written by the arm. **(b)** An inline `child.spawn` under PowerShell's `-Command` form can
return an empty `PATHEXT`, which makes `shutil.which('ffprobe')` come back `None` on a box
where ffprobe is installed — the fix was inserted into the run script before the `$src =…`
anchor, and it is why every command above is run from a FILE, never inline.

---

## 11. THE CONSTANTS — the table to copy into code

| constant | value | where it comes from |
| --- | --- | --- |
| `SPEECH_CHANNEL` | `"speech"` | :84 — READ, verbatim |
| `DEFAULT_MAX_SEGMENT_S` | `15.0` | :74-80 restated from the ASR package |
| `DEFAULT_SEGMENT_MODE` | `"silence"` | :74-80, and `segments_fixed` is the forbidden grid |
| `INTRA_OP` / `INTER_OP` | `4` / `1` | :74-80 |
| `SAMPLE_RATE` | `16000` | :74-80; `kAsrSampleRate = 16000` also in `src/capture/audio_contract.h` :33 |
| `CREATE_NO_WINDOW` | `0x08000000` | :81 — no console on the owner's screen |
| `RRF_K` | `60` | `src/index/search.py` :30, and `score(seg) = sum_c w_c/(60+rank_c)` |
| `K_PER_CHANNEL` | `100` | `search.py` :31 |
| `WEIGHTS` | `{'speech': 1.0, 'ocr': 1.0, 'visual': 0.7}` | `search.py` :32 — speech is NOT down-weighted |
| the mint | `int.from_bytes(sha256("sotto/seg|"+content_key+"|"+start_ms)[:8], "big") >> 1` | :229-231 |
| the exit contract | `0` / `2` / `3` | :40-47 and the branch at :715 |

---

## 12. UNKNOWN — NAMED, WITH THE EXPERIMENT THAT SETTLES EACH

1. **Who owns the FTS5 `SQL logic error` — the trigger's SQL, or this build's SQLite?** The
   probe above installed the schema verbatim and got UPDATE, DELETE and the `'delete'`
   special-insert refused on python 3.43.1 and on the CLI at 3.51.1, so the behaviour is stable
   across two builds. **Settling experiment:** a two-table minimal repro — one
   `CREATE VIRTUAL TABLE`, one hand-written `AFTER DELETE` trigger using the documented
   special-insert WITH the `rowid` form, run against 3.43.1 and 3.51.1; if both still refuse,
   bisect the python wheel against a same-version CLI build. Until then, treat the schema as
   UPDATABLE-NOWHERE and never write an UPDATE path into `src/index/`.
2. **How the Engine will call this module.** `the Engine schedules phase 2; nothing here is`
   ever called inline from the capture path` (READ :16-17) is a CODE statement, not a measurement.`
   The Python Engine on `feat/engine-process` runs its own `asr_worker.py` child, and nothing
   in the object store runs `clip_to_asr.py` end-to-end behind a real capture. **Settling
   experiment:** run the Engine against a real `aireplay-capture.exe` clip, then read which pid
   owns the index write from the store's commit trace — if the winner is a capture thread, Law
   `capture never waits for AI` is already violated.
3. **The index budget at production scale.** 0.53125 MiB/clip-minute and `db_file_bytes 139264`
   are ONE 15 s CPU clip. Not measured: a 2-hour rolling session, a clip WITH audio, the visual
   channel's rows, or any of the other tables. **Settling experiment:** synthesise a library of
   clips with distinct `content_key` (distinct BYTES — a copy IS the same clip) totalling at least
   100 minutes, index them all, and read `index_bytes == 0.05 % x video_bytes` invariant I1.
4. **The 5-second grid.** The plan asks for `one row per 5 s window`; the shipped module
   partitions on silence with a 15.0 s cap. **Settling experiment:** index the same clip twice —
   shipped silence mode, then a forced 5 s grid — and compare `speech_rows`,
   `db_mib_per_clip_minute`, and a spot-check of five transcripts against the wav's known text.
   The owner decides; the numbers decide how much it costs.
5. **`model_sha256` is a file-INVENTORY hash, so two exports that differ in bytes but not in
   `name:size` collide.** One export round-trip was measured; the collision case was not.
   **Settling experiment:** point two runs at exports with identical sizes and check whether
   `model_sha256(path)` distinguishes them; if it does not, the transcript-row conflict detector
   at §3 is the only thing standing between a re-transcode and a silently stale model.
6. **`--stamp-scan` defaults to FALSE (:262-266), so no `scan_ms` is written on the default
   path.** Who is supposed to stamp it, and from what clock, is in neither the code nor the plan.
   **Settling experiment:** index one clip with and without the flag and census the `video`
   row's columns in `mode=ro` — the difference names the owner.

---

## 13. WHERE THE PLAN OF RECORD OVER-STATES — SAID OUT LOUD, NOT PAPERED OVER

| the plan says | the measured or READ fact | reading |
| --- | --- | --- |
| clips are `H.264`+`AAC` (§2.1) | 8/8 sample clips report `AUDIO=NONE` (READ); the shipped one-trak MP4 carries `"vide"` only | the plan describes an INTENDED shape, not the one that ships today |
| one row per `5 s` window (§2.3) | the shipped cap is `DEFAULT_MAX_SEGMENT_S = 15.0` on a silence partition with a `0.10` s pad, and 2 rows per 15 s clip is MEASURED | the plan and the code disagree on window length; this spec records the DEVIATION |
| the plan is a plan of record | `P4-aireplay-clip-to-asr.md` is UNTRACKED and lives only at `H:/sotto` | every claim above is READ from the untracked copy; it becomes citable only once this spec's evidence file lands it |

---

## 14. WHAT THIS SPEC DELIBERATELY DOES NOT DO

### 14.1 It does not transcribe in-process

No `onnxruntime` import on the phase-1 path (READ :11-12), and phase 2's ASR work runs in a
child whose stdout is the only channel back. A dead or stalled child cannot wedge the indexer: it
produces a REFUSAL and an exit code, and the parent has already committed the video row.

### 14.2 It does not guess at the audio stream

`-map 0:a:0` (READ :197-201) takes the FIRST audio stream or NOTHING, and anything that is not
exactly 16000/mono/PCM16 is refused with `wav-contract-refused` :217-221, whose comment is
`the contract is 16000/mono/PCM16 and nothing here converts`. The tool refuses rather than
resamples because a resample would silently change what the model hears.

### 14.3 It does not size its segments to please a plan

The shipped window is a silence partition with a `15.0` s cap and a `0.10` s pad, and the
uniform `segments_fixed` grid is what the ASR package itself calls forbidden. A plan asking
for `one row per 5 s window` would produce the grid the code refuses; the deviation is recorded
in §13 rather than implemented here.

### 14.4 It does not open the audio endpoint

Audio reaches this module through a FILE it extracts itself (:187-230), never through the
machine's capture endpoint. The one-owner WASAPI law — one process, one loopback endpoint — is
not this module's to satisfy, and a spec claiming otherwise would describe a different program.

### 14.5 It does not overwrite, ever

A minted `seg_id` collision is `seg-id-collision` :234-246; a disagreeing speech row is
`speech-row-conflict` :469-519. Both exit `2` (READ :715). Both are refusals.

### 14.6 It does not pretend a REFUSED arm is a measured one

Arm V's verdict `no-audio-stream` means the run refused at probe and produced no speech rows.
That is the contract working, and this spec records it as a refusal — never as a measured
transcript of a clip that had no audio.

---

## 15. WHERE TO STAND WHILE READING THE SUBJECT

The subject file is `_moved/aireplay/src/pipeline/clip_to_asr.py` at
`feat/build-verify-1` HEAD `1be1803`, blob `9defedd…`, 32306 B / 727 lines LF
(sha256 `b1462fc7…`); its companion test is `_moved/aireplay/src/pipeline/test_clip_to_asr.py`
blob `e5ea65be…`, 45771 B / 1044 lines, carrying the same 9 arms and 107 checks this spec
describes. The store and search it writes for are `store.py` blob `e8398e5c…` 21155 B / 447
lines and `search.py` blob `ab69eab4…` 10713 B / 223 lines at the worktree HEAD `399bc85`.
**Line numbers are hints; the sizes and shas are the identity.**
