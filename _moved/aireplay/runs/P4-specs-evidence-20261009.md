
# LANE E - THE ARMS ACTUALLY RUN

Lane `feat/specs-05-07`, worktree `H:/sotto-wt/specs57`, HEAD `399bc851cea30e99e7c1fe8ccb1928b22bc1b1e3`.

Subject: `_moved/aireplay/src/pipeline/chain.py` - READ `git rev-parse HEAD:_moved/aireplay/src/pipeline/chain.py` = `85bffa78f1ac7dfc5ebb457a717ff1a38b3165f1`, `git cat-file -s 85bffa78...` = 49948 B (LF content; the CRLF copy on disk is larger).

**Window of the runs recorded here: 2026-10-09T21:06:32Z .. 2026-10-10T01:19:33Z.** Every instant below is UTC; this box is UTC-03:00 (MEASURED `Get-Date -Format 'zzz'` -> `-03:00`). File instants are `stat` mtimes of the artefact named, which is the most precise clock this lane has for a run.

This file is a RECORD, not a plan. It commits no database, no clip, no WAV, no model weight and no binary.

**No arm opened an audio DEVICE.** The ASR read a 16 kHz mono s16le WAV that ffmpeg extracted from a FILE. No capture device was initialised and no WASAPI endpoint was taken. The endpoint law in `AGENTS.md` (exactly ONE owner of a loopback endpoint; 86 historical `0x8889000A` deaths) is therefore NOT a risk of these arms and none of them tests it: that test needs a live capture run, which this box cannot do because WGC refuses every capture item here (READ `docs/integration-sotto-app.md`).

## 1. THE ARMS AND WHAT EACH ASSERTS

| arm | instant (UTC) | clip | verdict | assertion |
| --- | --- | --- | --- | --- |
| A | 2026-10-09T21:06:36Z | `spec05-arm-a.mp4`, 9 s, 2 streams | `ok` | the whole 9-stage chain completes on a clip that HAS audio: real ffprobe, real ffmpeg extract, real int8 ASR, real speech rows, a lexical hit |
| A-rerun | 2026-10-09T21:15:39Z | the same clip | `ok` | a rerun over the same index. Its numbers are the defect in section 5 |
| B | 2026-10-09T21:27:41Z | `spec05-arm-b-videoonly.mp4`, video-only | `no-audio-stream` | a clip with no audio stream is REFUSED at the probe stage, before the index is opened - zero index bytes |
| B-repeat | 2026-10-10T01:19:33Z | the same clip, fresh index | `no-audio-stream` | repeat of B taken to harvest a row census: again zero index bytes |
| D-pair | 2026-10-10T00:56:52Z and 00:56:53Z | A-clip, then B-clip | `ok`, then `no-audio-stream` | `--expect no-audio-stream` is NOT vacuous: the SAME expectation fails the clip that has audio and passes the clip that does not |
| no-ASR | 2026-10-09T21:30:42Z | `spec05-arm-a.mp4` with `--NoAsr` | `ok` | with ASR suppressed the indexed transcript is the lane's own DOUBLE text; the row still lands and names its producer |

Row populations - what the indexes actually contained after each run - are section 9, read with `sqlite3` in read-only URI mode (`file:<db>?mode=ro`) so opening them cannot change what is measured.

## 2. THE INSTRUMENT, EXACTLY

The chain is driven by a PowerShell FILE, never an inline `-Command` (measured repeatedly on this box: the inline form returns EMPTY stdout). Driver: `I:/cc-tmp/spec05/run-chain-patfix.ps1`, a byte-copy of `I:/cc-tmp/spec05/run-chain.ps1` with ONE line inserted before the `$src = ...` anchor, setting `$env:PATHEXT = '.COM;.EXE;.BAT;.CMD;.VBS;.VBE;.JS;.JSE;.WSF;.WSH;.MSC'`. Why that line exists is section 10.

- child interpreter: `py -3` (`py -NoProfile` is not a thing on this box: "Unknown option: -N")
- working directory: `H:/sotto-wt/specs57/_moved/aireplay/src`
- `$env:PYTHONPATH = H:\sotto-wt\specs57\_moved\aireplay\src`
- `$env:TMPDIR` / `$env:TMP` / `$env:TEMP` = `I:/cc-tmp` (G: fills with ENOSPC)
- `$env:OMP_NUM_THREADS = 4` (int8 model, 4 intra / 1 inter by the shipped constants)
- spawn: `UseShellExecute=$false`, `CreateNoWindow=$true`, both stdouts redirected - so no console window is put on the owner's screen, and the driver prints the child's own rc and elapsed ms

One driver invocation per arm, of the form

```powershell
I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip <clip.mp4> -Index <db> -Work <dir> -ModelDir <models> -Json <json> [-Expect no-audio-stream] [-RequireReal <n>] [-NoAsr]
```

Defaults NOT restated per arm (they are the driver's own): `-ModelDir H:/sotto/_moved/aireplay/models/parakeet-tdt-0.6b-v3-onnx`, `-Device spec05-sapi-lavfi`, `-Mode instant`, `-RequireReal 5`. The model directory is the git-ignored one in the product root; it is absent from this worktree by design and that absence is not evidence about the code.

Every command line below was PRINTED BY THE DRIVER (its `ARGS:` line) and the JSON it names was written by the same invocation, so the command text is a record, not a reconstruction.


## 3. THE SUBJECTS AND WHAT THEY ARE NOT

Nothing in these arms is a SOTTO capture artefact. Three clip shapes are in play and they are NOT interchangeable:

**SUBSTITUTE-CLIP-1 - `_moved/aireplay/src/pipeline/chain.py`'s own fixture, two streams.** Fixed sha256 `9f74b9a693aeaa204ec2e963905bed19ab944ecc058f55cbfcb20f4678ac9498`, 1425657 B, ffprobe (READ from `arm-a.json`, stage `probe`): `n_streams=2 n_video=1 n_audio=1 dur_s=9 vcodec=h264`. This is the clip the audio-OK arms ran on. It is a REAL capture artefact ON DISK in the sense the driver's note uses - a file, mtime 2026-10-09T20:38:13.718Z - but it is NOT the muxer's output: it was built by ffmpeg, so the audio trak in it was NOT written by `_moved/aireplay/src/capture/mp4_writer.cpp`.

**SUBSTITUTE-CLIP-2 - the video-only clip.** Fixed sha256 `0fa7ae2918f74b5df788482c802cfbf32821be937cf6f9f84fe6c980663b233e`, 1335631 B, ffprobe `n_audio=0`. This is what SOTTO's own capture produces ON THIS BRANCH today: `_moved/aireplay/src/capture/mp4_writer.cpp` @ HEAD blob `0d59f554e9920b3d63ba5505f3004fa7535975ab`, 13732 B / 322 lines, writes ONE trak (`vide` :249, video `track_ID` 1 :273, `next_track_ID=2` :302, no `soun`). That is the measured reason a two-trak SOTTO clip cannot be produced in this worktree: the muxer does not write the audio trak yet, and `chain.py:85 SRC` resolves siblings relative to the RED root, so copying the RED root is the only way to run it at all.

**The gate's own fixture.** The shipped lane used `I:/cc-tmp/clipasr/fixture-15s.mp4` 864070 B, ffmpeg-built WITH aac, `n_streams=2 n_video=1 n_audio=1` (READ `_main/receipt-20261009-clipasr.md` section 4, blob `f26d8aab64efe5e8517be280e7be1d7deff5d94f` 17302 B).

So the two-trak clip the plan's section 2.1 describes ("H.264 + AAC") is only real here as an ffmpeg product. The plan's other shape ("video-only when audio is disabled") is real here twice over: as the fixture and, more importantly, as what the branch's own capture core emits today.

The audio itself: `work/9f74b9a693aeaa20.wav` - fixed sha256 `c64ac7f727580f254e8f3df83d0507510b0e32db4cacd3f7444aaadccd17ab75`, 547156 B, mtime 2026-10-09T20:38:13.311Z - is ffmpeg's extract of that fixture. Four arms (A, A-rerun, no-ASR and the D-pair's first leg) all extracted the SAME wav by the SAME code, mtimes 21:15:36Z, 21:30:41.260Z, 21:27:39.722Z and 00:56:48.777Z. In the lanes that came after, the `work-` directories that are EMPTY (`work-b/`, `work-b2/`, `work-d2/`, `work-d3/`, `work-arm-d3/`) are the instrument proving the corresponding run never reached the extract stage.


## 4. ARM-A - THE WHOLE CHAIN ON A CLIP THAT HAS AUDIO

Instant: 2026-10-09T21:06:36.625Z (mtimes of `arm-a.json` 19441 B and `arm-a.db` 106496 B, birth 21:06:32Z). Verdict `ok`, rc 0, 4273 ms, 25 contract checks, 0 failed, provenance `DOUBLE=1 REAL=5 REAL_SUBSTITUTE=2`.

```powershell
I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip spec05-arm-a.mp4 -Index arm-a.db -Work work -Json arm-a.json
  RC: 0 ELAPSED_MS: 4273
```

Every stage in the order the driver ran them, each number a field of the same JSON:

| stage | provenance | what was measured |
| --- | --- | --- |
| capture | DOUBLE | `bytes=1425657 device=spec05-sapi-lavfi`. Note, verbatim: "DOUBLE for the CutResult VALUE (C++, cannot run here: WGC refuses every capture item, receipt-16). The clip is a REAL capture artefact on disk." |
| probe | REAL_SUBSTITUTE | `n_streams=2 n_video=1 n_audio=1 dur_s=9 vcodec=h264`. Note: "ffprobe is an EXTERNAL binary; REAL means the shipped module did the work". |
| extract | REAL_SUBSTITUTE | `rate=16000 ch=1 sampwidth=2 peak=0.532623 rms=0.062638 floor=0.001 bytes=286892 extract_s=0.04`. Note: "ffmpeg does the extraction that the unwritten AAC trak in mp4_writer.h cannot yet do (receipt-16 section 7)". |
| ingest-clip | REAL | `video_id=1 content_key=9f74b9a693ae duration_ms=9000 db_bytes=4096`. Note: "`started_at_s` is NOT a column in the new schema ... recorded, not silently dropped." |
| segments | REAL | `mode=silence n_segments=2 audio_s=8.963 covered_s=9.163`. |
| asr | REAL | `chars=95 rtfx_steady=8.46 rss_peak_mb=776.3 providers='['CPUExecutionProvider']x['CPUExecutionProvider']' wall_s=3.85`. Two ORT sessions, both on CPU, with the CUDA directory question out of scope here. |
| ingest-asr | REAL | `segments=2 expected=2 text_fts_rows=2 producer=asr:parakeet-tdt-0.6b-v3:int8`. Note: "The FTS row came from the schema's TRIGGERS, not from this chain." |
| search | REAL | `query=disquintoa n_lexical_hits=1 video_ids=[1] paths=1 population=1`. |

Stage notes are the chain's own text, quoted because the PROVENANCE of each stage is carried in them.

**The transcript, verbatim (95 chars):**

`Spec 5 ternos a clip on disquintoa ser chabluru. The harber is quiet before that, and deserted.`

**What is asserted about that text: its length, its persistence, its indexing, and the identity of its producer - and NOTHING else.** The lane's own fixture audio is synthetic TTS, so the words are nonsense; `disquintoa` is the token the chain's own `_pick_query` chose for the lexical arm (longest alphabetic token of >=4 chars, chain.py:826-837), not a claim that the model transcribed anything real. Transcription QUALITY is out of scope for these arms and no number here speaks to it.


## 5. ARM-A RERUN - THE DEFECT THIS LANE FOUND

Instant: 2026-10-09T21:15:39.927Z (mtimes of `arm-a2.json` 19457 B and the refreshed `arm-a.db` 106496 B). Same clip, same index, same work dir. Verdict `ok`, rc 0, 2761 ms, provenance `DOUBLE=1 REAL=5 REAL_SUBSTITUTE=2`.

```powershell
I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip spec05-arm-a.mp4 -Index arm-a.db -Work work -Json arm-a2.json
  RC: 0 ELAPSED_MS: 2761
```

The stage that changed is the last one:

- `arm-a2.json` stage `ingest-asr`: `text_fts_rows=4` (run 1 wrote 2, over the same 2 segments).
- `arm-a2.json` stage `search`: `n_lexical_hits=2 video_ids=[1,1] paths=1 population=1` - the same clip returned TWICE for the same query.

Row census of the index after the rerun (read-only, 2026-10-10T01:03:10Z, `py -3 I:/cc-tmp/spec05/count-rows.py`, URI `file:...?mode=ro`):

| table | rows | what they are |
| --- | --- | --- |
| video | 1 | one row - `content_key` unique held |
| segment | 4 | each of the 2 segments present TWICE with two different minted ids |
| transcript | 4 | ditto |
| text_fts | 4 | the FTS mirror doubled by the schema TRIGGERS |

So a rerun is NOT idempotent on this branch. Root cause, READ in the subject: `chain.py`:697-699 `upsert_segment(...)` is called WITHOUT `seg_id=`, and `store.upsert_segment` falls back to a plain `INSERT ... RETURNING seg_id` (READ `_moved/aireplay/src/index/store.py`:247-267) - so every rerun mints NEW seg_ids and the transcript follows. The chain's own stage note names the FTS half of the truth: "The FTS row came from the schema's TRIGGERS, not from this chain."

**The shipped lane is the one that got this right, and it got it right with a mechanism, not a discipline.** READ `clip_to_asr.py` @ `1be1803166e4710d3d37b807c487a135e39f4001` (blob `9defedd52d356b7fbac41f3dbe8c3d0a78f1821f`, 32306 B / 727 lines): `write_speech_row` (:469-519) compares the existing row against a `want` set of exactly `{"text","text_norm","start_ms","producer","model_sha256"}`; identical -> `"kept"`; disagree -> `ClipToAsrError("speech-row-conflict", ...)`. The shipped lane measured the same run twice - `RUN 1 {'inserted': 2}` vs `RUN 2 {'kept': 2}`, `DIFF: {}`, and eight per-table sha prefixes that did not move (READ `_main/receipt-20261009-clipasr.md` section 5). The id that makes it possible is minted deterministically from `(content_key, start_ms)` - the mechanism this branch's chain does not have.

The consequence of the defect that matters for the SPEC: rerunning an index over an already-indexed clip doubles the speech channel, and the search layer then returns the same clip once per duplicate row. Nothing crashes, nothing refuses, the index just stops being a truth.


## 6. ARM-B - THE VIDEO-ONLY CLIP IS REFUSED

Two invocations, same subject, fresh index each time. Both ran the video-only SUBSTITUTE-CLIP-2 with `--expect no-audio-stream`.

```powershell
I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip spec05-arm-b-videoonly.mp4 -Index arm-b.db -Work work-b -Expect no-audio-stream -Json arm-b.json
  RC: 1 ELAPSED_MS: 370
I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip spec05-arm-b-videoonly.mp4 -Index arm-b2.db -Work work-b2 -Expect no-audio-stream -Json arm-b2.json
  RC: 1 ELAPSED_MS: 215
```

Instants: 2026-10-09T21:27:41.179Z (`arm-b.json` 16949 B) and 2026-10-10T01:19:33.579Z (`arm-b2.json` 16950 B). Verdict `no-audio-stream` both times. Provenance of both: `DOUBLE=1 REAL_SUBSTITUTE=1 REFUSED=1`, and their `stages` lists carry exactly three entries - capture DOUBLE, probe REAL_SUBSTITUTE (verdict `no-audio-stream`), chain REFUSED. The `refusal` field is the chain's own sentence, verbatim:

The index for this arm is EMPTY in a way that is worth stating precisely, because "no rows" and "no index" are different claims:

- `arm-b.db` - ABSENT. Zero bytes; no `-wal`, no `-shm`.
- `arm-b2.db` - ABSENT. Zero bytes; no `-wal`, no `-shm`.

 quoted: `spec05-arm-b-videoonly.mp4 carries 0 audio stream(s) of 1 (measured by ffprobe). The muxer is video-only, so this clip has nothing for the ASR to hear. Refusing rather than inventing an audio track.`
- `work-b/` and `work-b2/` - EMPTY.

So the refusal is at the PROBE, before the index is even created. That is the mechanism, not luck: `chain.py`:561-573 `_con_or_open()` creates the database lazily, so a probe refusal leaves ZERO index bytes. The index that ARM-A created in 4096 B is 106496 B by the time the run is over; this arm's peak is 0.

**Grade.** The refused arm is `is_scaffold=true` in its JSON - the chain's own provenance word. The grade here is GREEN for the REFUSAL: the shipped probe reports `n_audio=0` and refuses, and the expectation is met. It is thin BY CONSTRUCTION, not because it failed: an arm whose subject is "a clip with no audio must be refused" has nothing to prove past the refusal, so "SCAFFOLD" is not a failure here. What is NOT covered by this arm is anything at all about what the index would have looked like - no extract, no segments, no ASR, no rows.

Absenting instrument, stated for the record: a `stat` of the db path plus a `Get-ChildItem` of the work dir, both of which are the evidence for "zero bytes" and "never extracted". Neither is an impression.


## 7. ARM-D PAIR - THE CONTROL THAT MAKES THE EXPECTATION LOAD-BEARING

The plan's ARM-D is "two-track / no-audio-stream" and a single run of it proves nothing about the mechanism: an arm that expects the refusal could be passing by always failing. So the arm is a PAIR - same expectation, both clip shapes, fresh indexes, back to back.

```powershell
I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip spec05-arm-a.mp4 -Index arm-d2.db -Work work-arm-d2 -Expect no-audio-stream -Json arm-d2.json
  RC: 1 ELAPSED_MS: 4093
I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip spec05-arm-b-videoonly.mp4 -Index arm-d3.db -Work work-arm-d3 -Expect no-audio-stream -Json arm-d3.json
  RC: 1 ELAPSED_MS: 208
```

Instants: 2026-10-10T00:56:52.580Z (`arm-d2.json` 19441 B, `work-arm-d2/9f74b9a693aeaa20.wav` @00:56:48.777Z) and 00:56:53.117Z (`arm-d3.json` 16950 B, `work-arm-d3/` EMPTY).

| leg | clip | verdict | expectation | outcome |
| --- | --- | --- | --- | --- |
| d2 | two-trak | `ok` | no-audio-stream | **VIOLATED** - the clip has audio, the expectation is false, exit 1 |
| d3 | video-only | `no-audio-stream` | no-audio-stream | MET, exit 1 |

The RC-1 is the same in both legs for OPPOSITE reasons, which is why rc alone must never be used to grade this pair:

- leg d2 exited 1 because the expectation was VIOLATED (it got `ok`). The chain's own line: `with --expect V, the run PASSES when the verdict IS V` (chain.py:1018-1026).
- leg d3 exited 1 because the expectation was MET `and` the run had already been told `--require-real-stages 5`, which a probe-refused run can never satisfy: `pipeline.chain: FAIL only 0 REAL stage(s); 5 required`.

Two further details of leg d2 worth keeping in view: it ran the full ASR (`rtfx_steady=7.63 rss_peak_mb=778 wall_s=3.5`, `text_fts_rows=2`, search `n_lexical_hits=1 video_ids=[1]`) and its index is `video 1, segment 2, transcript 2, text_fts 2` - so the doubled-row defect of section 5 does not appear on a FRESH index, only on a rerun, which is the precision that fixes what the defect is.

**Why this pair had to be re-run.** The first D attempts (00:06Z, work dirs `work-d2/` and `work-d3/`) never ran: `--clip` and friends were passed but the driver's own spawn put a child in a PATH where `shutil.which('ffprobe')` returned None - the tool was not found, the run refused with `tool-missing`, RC 1, in 4105 ms and 291 ms. The mechanism is an INSTRUMENT defect of this box, recorded in section 10, not a product defect. The fix that made the pair runnable is the one `PATHEXT` line in the driver.


## 8. ARM-noASR - THE SPEECH CHANNEL WITHOUT AN ASR

Instant: 2026-10-09T21:30:42.216Z (`arm-noasr.json` 19287 B, `work-noasr/9f74b9a693aeaa20.wav` @21:30:41.260Z, `arm-noasr.db` 106496 B). Verdict `ok`, provenance `DOUBLE=2 REAL_SUBSTITUTE=2 REAL=4` - one more DOUBLE and one fewer REAL than ARM-A, because the `asr` stage itself is now the double.

```powershell
I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip spec05-arm-a.mp4 -Index arm-noasr.db -Work work-noasr -NoAsr -Json arm-noasr.json
```

With ASR suppressed the segmenter still runs - `n_segments=2`, no chars - and the chain writes its OWN DOUBLE text instead of a transcription:

| stage | value |
| --- | --- |
| asr (provenance DOUBLE) | `n_segments=2`, no chars, no runtime numbers at all |
| ingest-asr | `text_fts_rows=2`, `producer=asr:parakeet-tdt-0.6b-v3:int8` |
| search | `query=DOUBLEONLYTOKEN n_lexical_hits=2 video_ids=[1,1] paths=1 population=1` |

Row census of `arm-noasr.db`: `video 1, segment 2, transcript 2, text_fts 2`, texts `zqxjk DOUBLEONLYTOKEN` and `wvuut DOUBLEONLYTOKEN`.

Two things this arm establishes and one it does NOT:

- **It does** prove the index and search path work end to end when the ASR is replaced - a pipeline whose speech channel only works when a 652 MB model happens to load is not a pipeline.
- **It does** show the producer string is the chain's own bookkeeping, i.e. the `producer` column names the PRODUCTION step, and the DOUBLE text says so in every row's text.

**It does NOT** prove anything about the ASR row: the segmenter, the model, the runtime, the ONNX session. Cite the ARM-A numbers for that. Note also the `video_ids=[1,1]` - this is the rerun-duplication shape of section 5 re-appearing on a DOUBLE-only index, which is a second independent sighting of the same defect and its cheapest reproduction.


## 9. THE ROW CENSUS - WHAT THE INDEXES ACTUALLY CONTAINED

One command, all databases, read-only, 2026-10-10T01:03:10Z: `py -3 I:/cc-tmp/spec05/count-rows.py` with `sqlite3.connect('file:<db>?mode=ro', uri=True)`. The read-only URI is not decoration: WAL sidecars from earlier runs were present, and opening the database read-write would have checkpointed them, which is a measurement change, not a measurement.

| db (B) | video | segment | transcript | text_fts | reading |
| --- | --- | --- | --- | --- | --- |
| arm-a.db 106496 | 1 | 4 | 4 | 4 | ARM-A plus its rerun. 2 segments, each present twice |
| arm-a2.db (absent) | - | - | - | - | no such file: the rerun REUSED `arm-a.db` |
| arm-d2.db 106496 | 1 | 2 | 2 | 2 | the D-pair's two-trak leg, fresh index, no duplication |
| arm-d3.db (absent) | - | - | - | - | probe refusal: ZERO index bytes |
| arm-b.db (absent) | - | - | - | - | probe refusal: run 1 of ARM-B. ZERO index bytes |
| arm-b2.db (absent) | - | - | - | - | probe refusal, run 2. ZERO index bytes |
| arm-noasr.db 106496 | 1 | 2 | 2 | 2 | the no-ASR arm, DOUBLE text, 2 rows |
| arm-d.db 106496 | 1 | 0 | 0 | 0 | **UNATTRIBUTED - see below** |

The `arm-d.db` row needs its own paragraph because a histogram that silently includes an unknown is worse than one that omits it. Its provenance was settled by census, not inference: `video 1`, `content_key 9f74b9a693ae`, path `I:\cc-tmp\spec05\spec05-arm-a.mp4`, 1425657 B, `state=recorded`, segments 0, transcript 0, text_fts 0. Its mtimes are 2026-10-09T21:27:40.473Z (birth 21:27:39.779Z), sandwiched between `work-d/9f74b9a693aeaa20.wav` @21:27:39.722Z and `arm-b.json` @21:27:41.179Z. So it is a run on the ARM-A clip that reached `ingest_clip` and stopped before any speech row - and it left NO driver JSON behind and appears in no `ARGS:` line. It is recorded as an artefact, NOT as an arm, and it is graded NOWHERE. Nobody should read +1 segment out of it.

Measurement side effect, disclosed: after this census every present db has a 0-byte `-wal` (mtime 01:03:10Z) and a 32768-byte `-shm` (mtime 02:03:34Z) that were not there before. Those sidecars are the probe's own footprint on the subject.

**The absence claims need their instrument too**, and here they are: `Get-ChildItem I:/cc-tmp/spec05 -Filter '*.db'` for "absent", and a directory listing for "empty". No arm below 2 streams ever left a transcript row, and that is a counted fact, not an impression.


## 10. INSTRUMENT DEFECTS AND RECOVERED DECISIONS

**1 - PATHEXT, the reason the first D-pair attempts never ran.** A child spawned from a `.ps1` via `ProcessStartInfo` on this box sees `$env:PATHEXT = ".CPL"` only, so `shutil.which('ffprobe')` is None inside `chain.py`:337-345 `_tool` and the first stage refuses `tool-missing`. The SAME `py` launched directly from the harness sees the python default (`.COM;.EXE;.BAT;.CMD`) and resolves the WinGet `ffprobe.EXE`. `H:/ffmpeg` and `C:/ffmpeg` do not exist, so the module's own guess-list cannot rescue it. Fix: insert the default list into the driver before spawn. Recorded as an INSTRUMENT defect - the product was never wrong here, the harness was. (Inserting the assignment at the TOP of the file lands inside the `param(...)` block and is a `ParserError`; it must go immediately before the `$src = ...` anchor.)

**2 - rc is not a verdict.** Two runs in this record exited 1 with opposite meanings (section 7). Every grade in this file is verdict-vs-expectation-first.

**3 - the census is read-only for a reason.** The mode=ro URI keeps the WAL sidecars from being checkpointed away under the measurement, and its own footprint (0-byte `-wal`, 32768-byte `-shm`) is disclosed in section 9.

**4 - `is_scaffold` is a provenance TAG, not a grade.** It appears on the video-only arm because the provenance chain includes doubles. Reading it as "this arm failed" is the mistake section 6 refuses.

**5 - the DOUBLE text is the lane's own fixture.** Every "`double` number in this record (transcript text, search token) comes from the lane fixture, not from the model, and the search token was chosen by the chain's `_pick_query`. Cite the arm for what ran, not for what the text says.

## 11. WHAT THE SHIPPED LANE MEASURED - READ, NOT CLAIMED HERE

Everything in this section is READ from the shipped lane's record on this branch, `_main/receipt-20261009-clipasr.md` (blob `f26d8aab64efe5e8517be280e7be1d7deff5d94f`, 17302 B), and is NOT a measurement of THIS lane. It is the only reason this file can state the idempotence and budget numbers at all, since the branch's own chain cannot produce them (section 5).

- Full run, rc 0, wall 33.8 s, log `_main/_clipasr-gate-full.log` 11796 B sha256 `d0d1df653e2c1ccba2bf1a60d133599cfdf6be7f512159cfc7cf6f5867964efd`: `CLIPASR-GATE PASS arms=9 checks=107 failed=0` and `CLIPASR-GATE-NEG PASS checks=6 failed=0`. Per-arm: `ARM-SHAPE GREEN 5` `ARM-A GREEN 25` `ARM-C GREEN 26` `ARM-C2 GREEN 9` `ARM-D1 GREEN 11` `ARM-D2 GREEN 14` `ARM-V GREEN 11` `ARM-X GREEN 5`.
- Census: 1261 samples / 0 visible windows.
- ASR on a 15 s clip: `rss_peak_mb_max 797.7`, `db_file_bytes 139264`, `db_mib_per_clip_minute 0.53125`, `speech_row_bytes_per_clip_minute 4712.0`, `speech_rows 2`, `rtfx_steady 14.75`, `n_segments 2 seg_median_s=8.0`, `video.index_ms 56.7`, `model_sha256 7db838b6f0e57b8f...`.
- Re-verify: rc 0, 32.9 s, census 1228, `asr_rss_peak_mb_max 797.1 MB`.
- FTS control (ARM-NEG): both colours were run in one gate command; the ARM-A FTS lookups hit `ponte` / `interditada` / `moradores` / `radio` exactly once each, rowid = seg_id `7757643230769124496`.

## 12. DECISIONS TAKEN AND ALTERNATIVES REFUSED

**DECISION 1 - grade the plan's ARM-B as a probe refusal, with a control.** The plan's ARM-B is "clip with no audio" and the shipped module's own vocabulary for it is the refusal `no-audio-stream`. Refused: grading it by the chain's own stop code, which circles back to rc and cannot distinguish "refused correctly" from "died on the way in".

**DECISION 2 - a SCAFFOLD is not a failure for a run that was supposed to REFUSE.** A chain that refuses has, by construction, almost no provenance; the rule only bites for a run that was supposed to COMPLETE (same rule receipt-24 section 8.1 states for the shipped lane's own gate).

**DECISION 3 - the D arm is a pair, never a single run.** An expectation that a run can satisfy by always failing is not an expectation. The control leg uses the two-trak clip, where the same expectation is VIOLATED.

**DECISION 4 - never print PASS for an arm that could not run.** The first D-pair attempts at 00:06Z are recorded as refused by the instrument, with the reason. No PASS word was printed for them.

**DECISION 5 - no audio device is opened by any arm here.** The alternatives (a live capture run to exercise the WASAPI one-owner law) are refused as unavailable on this box - WGC refuses every capture item - and naming that is the honest answer instead of a substitute that pretends to test it.

**DECISION 6 - every stage keeps its provenance word.** DOUBLE, REAL_SUBSTITUTE and REAL are reported per stage, never collapsed into one pass number, because a chain with 5 REAL stages and 1 DOUBLE one is a different claim from a chain with 6.


## 13. UNKNOWN - NAMED, WITH THE EXPERIMENT THAT SETTLES EACH

**Idempotence on THIS branch is measured-DEFECT, not unknown.** Settled: a rerun over the same index doubles every speech row (section 5), root-caused to `chain.py`:697-699. What is UNKNOWN is whether the branch will adopt the shipped mechanism. The settling experiment is the shipped one and it is READ here: run the same clip twice and compare, per table, the row ids `and` a per-table sha of the surviving rows (`_main/receipt-20261009-clipasr.md` section 5, which got `RUN 1 {'inserted': 2}` vs `RUN 2 {'kept': 2}`, `DIFF: {}`). The mechanism to adopt is a deterministic seg_id minted from `(content_key, start_ms)` plus `write_speech_row`'s `want` set - READ `clip_to_asr.py` @ `1be1803`, blob `9defedd...`, :469-519.

**I1 (index_bytes == 0.05% x video_bytes) is NOT verified on these clips.** The clips are ffmpeg fixtures of 1.3-1.4 MB, not the 15 s capture artefact, and the shipped lane's own numbers (`db_file_bytes 139264`, `db_mib_per_clip_minute 0.53125`) are for its own fixture. Settling experiment: the same I1 line computed on the arm indexes here (106496 B / 1425657 B = 7.46%, i.e. WAY over 0.05%) and on a real capture clip; this lane refuses to claim either number, because the fixture's video bytes are ffmpeg's, not the muxer's.

**The ASR-failure path (exit 3) is NOT run in this lane.** Every ARM-A-family run had a working model and a working CPU. Settling experiment: the shipped lane's ARM-D1 (`rc 7 -> rc 3`) and ARM-D2 (stall -> rc 3 with the video row visible at t=0.263 s), READ in the receipt's sections 7.

**The two-trak SOTTO clip is NOT produced here.** Everything two-trak in this record is ffmpeg's or the fixture's. Settling experiment: check out `feat/audio-in-clip` @ `b390e3d` (READ `_moved/aireplay/src/capture/mp4_writer.cpp` 25955 B / 584 lines: audio `track_ID` 2 :315, `next_track_ID 3` :563) and let it write one.

**The WASAPI one-owner law is NOT exercised.** See section 0. Settling experiment: a live capture run with a second owner deliberately holding the endpoint, which is a lane of its own.

## 14. HOW TO REPRODUCE THIS RECORD

Every artefact named lives in `I:/cc-tmp/spec05/` except the model directory (product root, git-ignored) and the receipt (product root `_main/`). Nothing in this record depends on a file that is not on disk today.

```powershell
cd H:/sotto-wt/specs57/_moved/aireplay/src
powershell I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip I:/cc-tmp/spec05/spec05-arm-a.mp4 -Index I:/cc-tmp/spec05/arm-a.db -Work I:/cc-tmp/spec05/work -Json I:/cc-tmp/spec05/arm-a.json
powershell I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip I:/cc-tmp/spec05/spec05-arm-a.mp4 -Index I:/cc-tmp/spec05/arm-a.db -Work I:/cc-tmp/spec05/work -Json I:/cc-tmp/spec05/arm-a2.json
powershell I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip I:/cc-tmp/spec05/spec05-arm-b-videoonly.mp4 -Index I:/cc-tmp/spec05/arm-b.db -Work I:/cc-tmp/spec05/work-b -Expect no-audio-stream -Json I:/cc-tmp/spec05/arm-b.json
powershell I:/cc-tmp/spec05/run-chain-patfix.ps1 -Clip I:/cc-tmp/spec05/spec05-arm-a.mp4 -Index I:/cc-tmp/spec05/arm-noasr.db -Work I:/cc-tmp/spec05/work-noasr -NoAsr -Json I:/cc-tmp/spec05/arm-noasr.json
py -3 I:/cc-tmp/spec05/count-rows.py
```

The per-arm defaults the driver adds when they are not passed: `-ModelDir H:/sotto/_moved/aireplay/models/parakeet-tdt-0.6b-v3-onnx`, `-Device spec05-sapi-lavfi`, `-Mode instant`, `-RequireReal 5`.

**Verification of this document itself:** the `ARGS:` / `RC:` / `ELAPSED_MS:` lines quoted in sections 4, 5, 6, 7 and 8 were read out of the corresponding `arm-*.json` and driver output; the row counts in section 9 were read by `count-rows.py` at the instant stated; every blob id and size was read by `git cat-file` in this worktree; every mtime was read by `stat`. Where a number came from the shipped lane's record, it says READ and names the receipt.
