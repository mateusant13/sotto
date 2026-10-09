# receipt-24 — the CHAIN, end to end: clip → audio → transcript → index row → search

Lane 17 · 2026-10-07 · scope `src/pipeline/` + `_main/_lane17-chain-gate.ps1`

> **REVISION 2 (post-verifier).** An independent verifier returned `VERDICT: FAIL` with three
> reproducible defects. All three were real, all three are fixed, and the receipt now carries
> the corrected numbers. §10 quotes the verifier verbatim. One number changed materially:
> **5** stages ran REAL, not 6 — `probe` was mislabelled, and `--require-real-stages` had been
> set to the inflated value. A second measurement this lane did not have before: the chain is
> **NOT idempotent** past the video row (§7.1), which is a finding for the index lane.

## 0. The headline, first, because it is the whole lane

**5 of 8 stages ran against the REAL shipped module. 2 ran against external binaries standing
in for producers this repo has never had. 1 is a double, and says so.**

```
  stage              provenance        what actually ran                            numbers
  ------------ ----  ----------------- -------------------------------------------- --------
  capture      ok    DOUBLE            CutResultMeta (this lane) + real clip on disk bytes=98099914 device=CABLE Input (VB-Audio Virtual Cable) via MME render / DirectSound capture
  probe        ok    REAL_SUBSTITUTE   ffprobe (external binary)                    n_streams=2 n_video=1 n_audio=1 dur_s=16.733 vcodec=h264
  extract      ok    REAL_SUBSTITUTE   ...\WinGet\Links\ffmpeg.EXE                 dur_s=16.725 rate=16000 ch=1 sampwidth=2 peak=0.304382 rms=0.028366 floor=0.001
  ingest-clip  ok    REAL              store.upsert_video                           video_id=1 content_key=c6e345b1fb9f duration_ms=16733 db_bytes=4096
  segments     ok    REAL              asr.segment.segments_for_mode                mode=silence n_segments=5 audio_s=16.725 covered_s=17.005
  asr          ok    REAL              asr.runner.transcribe                        n_segments=5 chars=50 rtfx_steady=5.55 rss_peak_mb=815.4 providers=['CPUExecutionProvider']x2
  ingest-asr   ok    REAL              store.upsert_segment + store.upsert_transcript segments=5 expected=5 text_fts_rows=5
  search       ok    REAL              search.SearchIndex.search_text               query=fazer n_lexical_hits=1 video_ids=[1] population=1
  contracts: 25 check(s), 0 failed
  SCAFFOLD: False   VERDICT: ok
  transcript (50 chars): She know that she's a fake. Bora fazer um plan de.
```

**The last link is the one that matters and it is REAL:** the search token `fazer` is not a
fixture. It is a token picked out of the transcript the model produced in that same run
(`chain.py:_pick_query`), so the clip can only come back if the model, the writer and the
FTS5 read side all agree on the same text. `population=1` is the denominator: one clip in
the index, one hit, and it is the clip this run wrote.

**WHAT THIS IS NOT.** The audio in that fixture is real capture audio, but it did not come
out of a clip *this repo produced*: see §3. The `capture` stage is a DOUBLE, because
`Replay::perform_cut()` cannot run on this host at all. A chain that claims to be end-to-end
and hides that is worse than no chain, which is why provenance is a column and not a footnote.

**`REAL` means the shipped module of this repo did the work.** ffprobe is an external binary
and is therefore `REAL_SUBSTITUTE`, not `REAL`. Revision 1 of this receipt called it `REAL`
while calling ffmpeg a substitute — the same class of external tool judged two ways, which
inflated the headline by one stage and was the only reason `--require-real-stages 6` passed.
Caught by the verifier (§10, finding 1); the threshold is now **5**, and it is asserted at 5.

## 1. What was delivered — four files, all new, none owned by another lane

| file | bytes | sha256 (first 16) |
|---|---|---|
| `src/pipeline/__init__.py` | 1000 | `C9608FC9DA3D5277` |
| `src/pipeline/contracts.py` | 30015 | `5C207ADCA906E2AB` |
| `src/pipeline/chain.py` | 49948 | `3BD5F54D58B720DA` |
| `_main/_lane17-chain-gate.ps1` | 26616 | `0146D9A51F4E161E` |
| `receipts/receipt-24-clip-to-asr-chain.md` | 25366 | `B6413E3D4DF9B3C1` |

Byte counts and hashes are **revision 2** (post-verifier fixes). The verifier confirmed
rev 1's four values **4/4 exact**; `chain.py` and the gate are the two files that changed after.

**NOT touched:** `src/capture/**`, `src/asr/**`, `src/index/**`, `src/ui/**`. MEASURED by
mtime census from 12:57 (this lane's start): every file changed under those four directories
belongs to another lane (capture `replay.cpp/h`, `ring_buffer.*`, `test_window.*`,
`audio_contract.h`; asr `runner.py`, `engine.py`, `gate.py`, `transcribe.py`; index the whole
rewrite; ui `hud-*`). This lane imported those modules and copied them into scratch to mutate;
it never wrote to them.

## 2. THE FINDING: the index lane's API was REPLACED underneath this chain, and the contract file caught it

This is the most valuable thing in the receipt, and it is a measured event, not a story.

At **13:10:26** the index lane rewrote `src/index` **while this lane was running**. Measured
before and after, same session:

| | before (read at the start of this lane) | after (13:10:26) |
|---|---|---|
| `__init__.py` | 2612 B, the package's declared API | **DELETED** |
| `schema.py` | 15748 B, `open_index()` / `SCHEMA_VERSION` | **renamed `schema.sql`**, 10570 B, no Python |
| `store.py` | 17284 B, `ingest_clip` / `ingest_asr_done` / `ClipRecord`, keyed on a TEXT `clip_id` | **14746 B**, `connect` / `upsert_video` / `upsert_segment` / `upsert_transcript`, keyword-only, keyed on `content_key` |
| `search.py` | 10883 B, module-level `search_text(con, query, filt)` | **9740 B**, a `SearchIndex` class; `import store` (bare, line 28) |

**What that would have cost without the contract file:** `ingest_clip` and `ingest_asr_done`
were deleted, so a chain written against them either fails to import (loud, fine) or — worse
— keeps a local reimplementation that agrees with a deleted API and writes rows nobody reads
(quiet, and that is the failure this repo keeps paying for). The contract file turned the
rewrite into **25 named checks that failed loudly at chain time**, with the drift named.

**Three integration obstacles the rewrite creates, all MEASURED, none of them mine to fix:**

1. **`import index.store` no longer works.** `src/index/__init__.py` is gone, so the package is
   a PEP-420 namespace and `search.py:28` does a bare `import store`.
   `ModuleNotFoundError: No module named 'store'` — verbatim, reproduced.
   *Fix for the index lane:* use `from . import store` (or restore `__init__.py`), so the
   package is importable the normal way. `chain.py:_con_or_open` works around it by putting
   `src/index` on `sys.path`, and says so.
2. **The FTS row is no longer the caller's job.** `schema.sql:173-186` carries triggers that
   mirror `transcript → text_fts`. Any chain still writing `text_fts` by hand now writes
   every row **twice**. `chain.py:stage_ingest_asr` writes only `transcript` and reports
   `text_fts_rows=5` read back from the table.
3. **The seconds→milliseconds boundary moved onto me.** The old store owned `_ms()`. The new
   writer takes `duration_ms` / `start_ms` in **milliseconds** and has no boundary of its own,
   while the ASR counts in 3-dp seconds. Writing seconds into a ms column puts every window
   at 1/1000 of its real position and every time filter misses **silently**. `chain.py:_ms()`
   is now the single boundary, and ARM H asserts `duration_ms=16733` for a 16.733 s clip.

## 3. The audio is real, but it did not come out of a clip this repo produced — stated plainly

The fixture the gate builds is: a **REAL capture artefact** (`_main/runs/cap-offline-gaming.mp4`,
16.733 s, h264 1920×1080, 97.8 MB, produced by this repo's muxer) + the **REAL WASAPI loopback
capture** (`H:\sotto\_main\live-sample-cable-input.wav`, float32 48 kHz mono, 30.1 s),
AAC-encoded and joined by ffmpeg.

**Why the join, and what it is not:** `mp4_writer` is video-only. The AAC `trak` is specified
as code to INSERT in receipt-16 §7 and was never inserted. Measured, re-confirmed here:
`_main/runs/clip-20261007-105609.mp4` carries `n_streams=1, n_video=1, n_audio=0`. So both
binary stages are **REAL_SUBSTITUTE**: `extract` stands in for a missing **writer** (the AAC
trak), `probe` for an mp4 **inspector** the product has never had. Neither is REAL, and
calling either REAL would be a lie in the chain.

**The audio content is not a tone and not noise.** `live-sample-cable-input.wav` is the
capture lane's own loopback recording, and the model transcribes it into words (§0).
`peak=0.304382` against the capture lane's `kAudioSilencePeakFloor=1e-3`
(`wasapi_audio.h:65`), so it is signal, not silence.

**The `capture` stage is a DOUBLE and cannot be anything else here:** `Replay::perform_cut()`
is C++, and `replay.h:120-123` records that WGC began refusing every capture item on this box
(E_ACCESSDENIED) — which is why the offline cut path exists at all. The `CutResult` VALUE is a
stand-in; the clip on disk is a real one.

## 4. Every stage either measures or refuses — there is no third outcome

| verdict | what it means | measured by |
|---|---|---|
| `ok` | the whole chain completed and search handed the clip back | ARM H |
| `no-audio-stream` | the clip has no audio. **The measured state of this product's capture path**, and the brief's premise | ARM N — `n_streams=1 n_video=1 n_audio=0`, ffprobe command attached, **and `video rows written=0` asserted** |
| `silent-device` | audio delivered, peak at/below the capture lane's floor. **CORRECT BEHAVIOUR on this box** | ARM S — `peak=0.0 floor=0.001` |
| `empty-transcript` | the model returned 0 characters | ARM E — `chars=0 n_segments=1` |
| `not-found` | everything completed and the clip did NOT come back | the chain's own failure mode |

**ARM E is the arm worth reading twice.** A 3.3 s slice of the real capture audio is above the
silence floor and segments into 1 window, and the model returns **0 characters**. The chain
refuses with `empty-transcript` and the gate then asks SQLite directly:
`transcript rows with invented text = 0`. The splitter drops silence-only and sub-0.6 s
segments (`segment.py:100-103`), so a silent clip must stay searchable-as-nothing. **Inventing
text here would be the worst bug in this repo**, and the gate measures its absence rather than
asserting it in prose.

**The silence floor is NOT this lane's number.** It is `kAudioSilencePeakFloor` from
`src/capture/wasapi_audio.h:65`, and `contracts._check_silence_floor` matches the literal in
that header at run time. If the capture lane retunes it, this chain follows instead of
carrying its own copy.

## 5. THE GATE — `pwsh -NoProfile -File _main\_lane17-chain-gate.ps1` → `LANE17-GATE PASS`, rc=0

**The gate now clears every stale `.db` under its work dir at start**, because the verifier
found all of its printed counts were cumulative across runs — which made the numbers
non-reproducible and hid §7.1. Every count below therefore belongs to ONE run.

```
Arm   Ok  Detail
0     True 25/25 contract check(s), 0 failed, live producers
H     True verdict=ok REAL=5 REAL_SUBSTITUTE=2 DOUBLE=1 scaffold=False transcript=50ch search_hits=1
N     True rc=0 verdict=no-audio-stream evidence=yes video rows written=0 (must be 0)
S     True rc=0 verdict=silent-device peak=0.0 floor=0.001 (a VALID green outcome on this box)
E     True rc=0 verdict=empty-transcript transcript rows with invented text=0
D     True rc=1 (expected non-zero) leak detected=yes
C1    True reverted refusal -> rc=1 red=True mutatedBytesRan=True contractsGreen=True namesTheCure(bad-wav)=True
C2    True reverted refusal -> rc=1 red=True mutatedBytesRan=True contractsGreen=True namesTheCure=True
```

The gate **builds its own fixtures** from artefacts already on this box and refuses to run if
one is missing, so it never depends on scratch this lane left behind. **POPULATION: 1 clip per
fixture, 1 run.** Elapsed ≈ 23–45 s depending on the machine's load.

**ARM 0 — the contracts, 25 checks against the LIVE producers.** 17 from the 8 Python
signatures (resolve + signature each) + 1 resolve-only module contract + 5 `CutResult` header
checks + 3 silence-floor checks. Re-verified independently at 13:2x against `src/index` @
13:10:26 and `src/asr` @13:09:59: **25/25, 0 failed.**

### 5.1 THE CONTROLS — four assertions each, and the control that was red for the wrong reason

Both controls copy `src/pipeline` byte-for-byte into scratch, revert ONE cure in the copy,
and run the **same assertions** against it. `New-MutatedCopy` **throws** if the mutation string
is not found, so a control whose mutation silently did nothing cannot pass.

- **ARM C1** — `if not info.get("n_audio"):` → `if False and not info.get("n_audio"):`
  (the `no-audio-stream` refusal). The copy proceeds into ffmpeg, which fails on a video-only
  clip: verdict **`bad-wav`**, rc=1.
- **ARM C2** — `silent = peak <= SILENCE_PEAK_FLOOR` → `silent = False` (the `silent-device`
  refusal). The copy then runs the REAL model over digital silence, which **MEASURED** returns
  0 characters, so the verdict becomes **`empty-transcript`** and the gate's
  `--expect silent-device` refuses: rc=1. (The first version predicted `ok` and failed; the
  assertion now states what actually happens.)

**Each control asserts FOUR things, not one** — the verifier's finding 3 was that `Rc -ne 0`
alone does not tie a red to the cure, because a copy that failed for an unrelated reason would
also satisfy it:

1. the run went **red** (rc ≠ 0), AND
2. the `loaded from:` line names the **COPY** (`chain.py` prints its own `__file__` on every
   run precisely so this is checkable), AND
3. the **contract block inside that same run is green** (25 checks, 0 failed) — which is what
   proves the red came from the reverted cure and not from a broken copy, AND
4. the red **names the failure the reverted cure opened up** (`bad-wav` for C1,
   `empty-transcript` for C2) — a red that merely *differs* is weaker than a red that differs
   **in the expected direction**.

**Each control's mutation string occurs exactly once in `chain.py`** (verifier-checked), so it
cannot no-op by hitting a second site.

**Two control-shaped lessons that were mine, both learned by shipping a bad control:**
- The first C1 went red and was **worthless**: the COPY could not find `src/capture/replay.h`,
  because the package computed the repo root as `parents[2]` and the copy sits in scratch. The
  cure under test was never exercised — exactly the failure receipt-16 §10 records in this
  repo. `contracts._find_repo_root()` now **walks up looking for `src/capture/replay.h` and
  `src/asr/runner.py`** instead of counting parents.
- The first attempt put the copy in a directory named `control-pipeline`, so `import pipeline`
  found the LIVE tree and the control passed **vacuously** while looking like a working red.
  The package directory must be named `pipeline`.

## 6. The contract declarations, and what each one prevents

`contracts.py` holds 9 contracts + 16 non-reflection checks = **25 live checks**. Seven are
Python signatures captured with `inspect.signature` and re-derived at run time; the C++
`CutResult` and the silence floor are matched textually. The ones with consequences:

| contract | the failure it prevents |
|---|---|
| `asr-transcribe` | the writer read EXACTLY the runner's `segments[]` keys. A renamed key is a transcript that indexes as nothing, with no error anywhere. |
| `asr-segment` | 0 segments is a MEASURED outcome, not an error (sub-0.6 s and silence-only segments are dropped). The chain reports a count BEFORE inference so the distinction is visible. |
| `asr-audio-read` | `_check` (`audio.py:53-61`) RAISES on anything but 16 kHz mono PCM16. That refusal is the last line of defence; the extractor must satisfy it or the chain dies there, which is the correct place to die. |
| `index-connect` | the `schema.open_index` → `store.connect` rename (§2). |
| `index-upsert-video` | identity is `content_key` (a 64-char SHA-256 the schema CHECKs), **not** a minted id and **not** the path. Keyword-only: a positional call raises `TypeError`. |
| `index-upsert-segment` | seconds in, ms stored, and the boundary is now MINE (§2.3). |
| `index-upsert-transcript` | `text_norm` is the caller's argument, and the FTS row is the schema's TRIGGER, not the caller's write (§2.2). |
| `index-search` | a malformed FTS5 expression returns `[]` instead of raising (`search.py:126-127`), so an empty result is **not** proof of a bad query. The chain asserts the clip came BACK, not that the call ran. |
| `index-import-shape` | `import index.store` no longer works (§2.1). |

## 7. Gaps declared, not papered over

### 7.1 The chain is NOT idempotent past the video row — MEASURED, and it is the index lane's to fix

Revision 1 of this receipt claimed re-running updates one row instead of duplicating. **That
was false**, and the verifier measured it (20 transcript rows after 4 runs). Measured here
directly on a **fresh** db, two passes of the same chain:

| after | `video` | `segment` | `transcript` | `text_fts` |
|---|---|---|---|---|
| pass 1 | 1 | 2 | 2 | 2 |
| pass 2 | 1 | **4** | **4** | **4** |

**Cause, read off the source:** `store.upsert_segment` (`src/index/store.py:140-160`) takes an
optional `seg_id`; when it is `None` it **always INSERTs** and returns a new `seg_id`. Its
`ON CONFLICT(seg_id)` branch is unreachable on that path, and `schema.sql` no longer carries
the `UNIQUE (video_id, start_ms)` constraint that the **previous** schema had (old
`schema.py:93`) — which was exactly what made the old `ingest_asr_done` idempotent.

**So:** the video row is idempotent on `content_key` (1 → 1 ✓). Everything below it
accumulates, so a retried ASR pass — which the product's own scheduling makes normal, since
the background pass is meant to be re-runnable — multiplies rows. `transcript`'s PK is
`seg_id`, so it cannot dedupe either.

**Hookup, not an edit** (the file belongs to another lane):
- **file** `src/index/schema.sql` · **anchor** the `segment` table (line 69) · **add**
  `UNIQUE (video_id, start_ms)` — restores the constraint the rewrite dropped.
- **file** `src/index/store.py:140` · **anchor** `upsert_segment`'s `seg_id is None` path ·
  **change** to `INSERT … ON CONFLICT(video_id, start_ms) DO UPDATE SET end_ms=excluded.end_ms, …`
  returning the existing `seg_id`.

### 7.2 The other declared gaps

1. **No AAC producer.** `aac_path` is NULL in every payload this chain writes; the audio path
   comes from somewhere else and the provenance table says so. *Owner: the mp4_writer/replay lane.*
2. **The epoch time axis the old index filtered on is GONE.** The rewritten `video` table has
   no epoch column — only `mtime_ns` — so the old store's `started_at_s` filter axis no longer
   exists. The chain records the loss on the stage (`started_at_s_source=NOT WRITABLE: ...`)
   rather than inventing a column. *Owner: whoever owns the QPC→epoch base.*
3. **The clip id is not the product's.** Identity here is the whole-file SHA-256 the schema
   mandates. *Owner: lane 15 (instant cut) for whatever the product's own id scheme is.*
4. **WGC refuses every capture item here**, so the `capture` stage cannot be real on this host.
   *Owner: the capture lane.*
5. **`started_at_s` has no home**, so the chain cannot demonstrate a time-window filter — only
   device/id filters survive the rewrite. `NOT MEASURED` on this box.

## 8. House rules

- **Rule 1, no visible console window:** every `ffmpeg`/`ffprobe`/`py` process is created
  through `System.Diagnostics.Process` with `CreateNoWindow=True` + `WindowStyle=Hidden`.
  MEASURED after a full run: a `Win32_Process` census for `python.exe`/`py.exe`/`ffmpeg.exe`
  returned 10 live processes, **none of them `pipeline.chain`** — they belong to the owner's
  Sotto worker (`sotto_worker.py`), BrandOps and other lanes.
- **Rule 2, never pipe for an exit code:** every native invocation redirects stdout and stderr
  to a file under `_main\_lane17-gate\evidence\` and reads the real `ExitCode`. No pipeline
  operator anywhere in the gate.
- **Rule 3, native `H:\` paths only.** **Rule 6:** every count carries its population and
  window; the ASR numbers are one 16.733 s clip, one run, and are **not** a performance claim
  (`rtfx_steady` ranged 0.6–5.55 across runs on a shared box).
- **Rule 7, git:** nothing committed. The gate is green; the commit is the orchestrator's call.
- **Repeatability:** the gate clears its indexes and was run twice from the fixed revision,
  both rc=0.

### 8.1 Two rules of the gate itself, added after the verifier

- **A `SCAFFOLD` verdict is only a failure for a run that was supposed to COMPLETE.** Relabelling
  `probe` left the two early-refusal arms with zero REAL stages, and they failed as "SCAFFOLD"
  while behaving exactly right — a false red. `chain.py:main` now refuses the scaffold verdict
  only when `verdict == "ok"`, and otherwise prints
  `note: this run refused at '<verdict>', so it is thin by construction, not a scaffold`.
- **An unreadable index must never read as "no leak".** `_db_contains` used to return 0 on
  `sqlite3.OperationalError`, which reports a broken detector as a clean one — ARM D would have
  passed for the wrong reason. It now raises, naming the db and the error.

## 9. What a reader should NOT take from this receipt

- **It is not an accuracy claim.** The transcript in §0 is agreement with the model, not WER
  against a human transcription; this box has no labelled corpus (receipt-17 §"WER").
- **It is not a performance claim.** One clip, one window.
- **It is not proof the product ships.** It proves four Python modules and one real model
  compose correctly over a real clip. `capture` is a double, both binary stages are
  substitutes, and §7 lists who owns each remaining gap — including **7.1**, which means the
  ASR pass is not safe to re-run today.
- **`src/index` may have changed again** since 13:10:26. ARM 0 is the arm that will catch it:
  if it goes red, the chain is built on sand and says so before any stage runs.

## 10. The verifier's verdict, quoted

An independent verifier was dispatched with a read-only audit brief
(`_main/_lane17-verifier-prompt.md`, 6 priority areas: control non-vacuity, provenance honesty,
contract/producer agreement, receipt numbers vs evidence, house rules, silent failure). It ran
the gate itself and reported:

> **VERDICT: FAIL** — Three reproducible defects: `chain.py:465` labels `probe` `REAL` for
> `ffprobe`, inflating the headline from 5 shipped modules to 6 and being the only reason ARM
> H's `--require-real-stages 6` passes; receipt §8's idempotence claim measured false against
> accumulating rows; controls assert `Rc -ne 0` without tying the red to the cure. House rules
> 1 and 2 hold (`:86-110`, `chain.py:423,501`); no green-on-failure path found.

It also recorded, as its own gate-doubt: *"because arms N/S/E expect refusals, a producer that
broke early enough to refuse would pass several arms."* That is a fair objection with a known
limit; §5.1's controls are the partial answer — they break the producer's own code on purpose
and check the refusal disappears — but no arm currently proves a refusal is *early* rather than
*correct*. Also fair, and it is why ARM N now asserts `video rows written = 0` instead of
relying on prose.

**Its three findings, and what was done:**

| # | finding | disposition |
|---|---|---|
| 1 | `probe` labelled `REAL`; headline inflated 5→6; `--require-real-stages 6` passed only because of it | **FIXED.** `probe` → `REAL_SUBSTITUTE`, threshold → 5, and the scaffold rule narrowed (§8.1) because the relabelling exposed a false red |
| 2 | idempotence claim measured false (20 rows vs 5) | **FIXED as a claim, and raised as a finding for the index lane** (§7.1), with the file, the line and the two-line fix. Not fixable here — the file is not mine |
| 3 | controls assert `Rc -ne 0` without tying the red to the cure | **FIXED.** Four assertions, the fourth being that the red names the expected downstream failure (`bad-wav` / `empty-transcript`) |

Its positive findings, kept here because they are the credit the work earned: signatures
**8/8** match against the post-rewrite `src/index` and never a stale revision; sha256 **4/4**
exact; each mutation string occurs **exactly once**; both control logs name the copy in
`loaded from:` with contracts green; the refusal DBs are **absent** (nothing written on
refusal); and **no green-on-failure path** was found anywhere in the gate.

### 10.1 Post-fix state

Gate re-run after all three fixes: **`LANE17-GATE PASS`, rc=0, 8/8 arms**, elapsed ≈ 23 s.
New sha256 for the two changed files: `chain.py` `3BD5F54D58B720DA`,
`_lane17-chain-gate.ps1` `0146D9A51F4E161E`. `contracts.py` and `__init__.py` are unchanged by
the fixes (`5C207ADCA906E2AB`, `C9608FC9DA3D5277`) — the verifier found no contract defect.

**Not done, and why:** no second independent verifier pass on the fixed revision (this lane's
budget); no test of the `CutResultMeta` → payload mapping against real C++ output
(structurally impossible here — `perform_cut()` cannot run); `replay.h` and `wasapi_audio.h`
were matched by the contract checks rather than read member-by-member by a second party.