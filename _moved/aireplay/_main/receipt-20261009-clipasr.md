# receipt-20261009 — CLIP-TO-ASR: a saved clip becomes searchable, idempotently, off the capture path

Lane **clip-to-asr** (branch `feat/clip-to-asr`, worktree `H:/sotto-wt/clipasr`) · 2026-10-09 ·
build-order step 5, indexing half · owner persona **Johannes Maier (maierjo)**

> **This lane is the indexing half only.** It makes a clip that already exists on disk
> searchable through the speech channel. It does not capture, it does not mux audio into the
> clip, and it does not run on the capture thread — see §8 for what a *changed* transcript
> does, which is the one behaviour this lane could not make work on this host.

## 0. The verdict, verbatim

Full run, 2026-10-09, rc **0**, wall **33.8 s**, log 11 059 B
(archived at `_main/_clipasr-gate-full.log`, 11 796 B, sha256 `d0d1df653e2c1ccba…`):

```
CLIPASR-GATE PASS arms=9 checks=107 failed=0
CLIPASR-GATE-NEG PASS checks=6 failed=0
CLIPASR-FINAL PASS
```

Companion lines from the same run, verbatim:

```
CLIPASR-REPORT census {"distinct_pids": [], "samples": 1261, "visible_hits": 0}
PASS W no visible console window in 1261 samples at 25 ms hits=0
CLIPASR-REPORT asr {"asr_rss_peak_mb_max": 797.7, "clip_seconds": 15.0, "db_file_bytes": 139264,
  "db_file_mib": 0.1328125, "db_mib_per_clip_minute": 0.53125, "db_page_size": 4096,
  "speech_row_bytes_per_clip_minute": 4712.0, "speech_rows": 2, "speech_rows_fingerprint_bytes": 1178}
```

Per arm: `ARM-SHAPE GREEN checks=5`, `ARM-A GREEN checks=25`, `ARM-C GREEN checks=26`,
`ARM-C2 GREEN checks=9`, `ARM-D1 GREEN checks=11`, `ARM-D2 GREEN checks=14`,
`ARM-V GREEN checks=11`, `ARM-X GREEN checks=5`.

## 1. The exact command (reproduce it in one shot, both colours)

```powershell
$env:TMPDIR='I:/cc-tmp'; $env:TMP='I:/cc-tmp'; $env:TEMP='I:/cc-tmp'
C:\Program Files\Python311\python.exe `
  H:\sotto-wt\clipasr\_moved\aireplay\src\pipeline\test_clip_to_asr.py
```

run with `cwd = H:\sotto-wt\clipasr\_moved\aireplay\src`, `windowsHide=true`, and the child env
`SystemRoot`/`SystemDrive`/`USERPROFILE`/`HOMEDRIVE`/`HOMEPATH`/`PYTHONIOENCODING=utf-8`/`PATH`
(with `C:\Windows\system32`). The work dir is wiped before the full run so no arm inherits
another arm's rows.

## 2. What was delivered — two files, both new, both owned by this lane

| file | bytes | sha256 | role |
|---|---|---|---|
| `src/pipeline/clip_to_asr.py` | 32 306 | `b1462fc759cb3bc0506bf9b43045eab3a2bd0c1e7003538f59c253f93f59653d` | **the deliverable** |
| `src/pipeline/test_clip_to_asr.py` | 45 771 | `9d9e48ad7e498bea9a0c5a1f85b426f9d2b588a9475a63079ea143905e7844be` | the gate |
| `_main/_clipasr-gate-full.log` | 11 796 | `d0d1df653e2c1ccba2bf1a60d133599cfdf6be7f512159cfc7cf6f5867964efd` | the archived green run |

> **The `.log` row is not part of the commit.** `_moved/aireplay/.gitignore:227` is `_main/*.log`,
> so `git status --porcelain -uall` never lists the archive; it is kept on disk at that exact path
> and size for anyone who wants to re-read the run, and it was **not** force-added past the
> repository's own ignore rule. Everything the log says is quoted in this receipt.

Nothing else was written. `src/index/*`, `src/asr/*`, `src/capture/*`, `src/engine/*`,
`src/storage/*`, `docs/*`, `specs/*`, `runs/*` are untouched (see §9).

## 3. The one-paragraph description of the shipped behaviour

`asr_index(conn, *, clip, ...)` runs, in order: `index_clip` → **commit** → `extract_wav` →
`run_asr` → one `mint_seg_id` + `store.upsert_segment` + `write_speech_row` per segment →
`conn.commit()`. The video row is committed **before** the ASR worker is spawned, so a worker
that stalls or dies leaves the clip discoverable in `video` and leaves the database free for
every other lane. Every speech row carries `producer='speech'`, so a result can always say
*which channel matched*. `seg_id` is minted from `(content_key, start_ms)`, so the same audio
in the same place always produces the same id — that is what makes the chain idempotent.

## 4. ASR measurements — MEASURED, CPU provider, 15.0 s fixture

Fixture: `I:/cc-tmp/clipasr/fixture-15s.mp4` (864 070 B, ffmpeg-built with an aac track —
ffprobe `n_streams=2 n_video=1 n_audio=1 codec=h264 w=1280 h=720 fps=30.0 duration_s=15.0
bitrate=460837`). **It stands in for the muxed clip lane C will produce; it is NOT a capture
clip** — `src/capture/mp4_writer.cpp` still writes video-only tracks today (MEASURED: exactly
one `Box trak("trak");`, `hdlr.b.insert(...,"vide",...)`, and the string `"soun"` appears
nowhere in that file).

Command: two CLI invocations against one fresh DB — `main(['index', …])` then
`main(['asr', …])` — with `store.store_bytes` read after each phase. The `asr` verdict JSON,
verbatim and abridged to the measurement keys:

| key | value | what it is |
|---|---|---|
| `rss_start_mb` | **23.3** | worker RSS before the model load |
| `rss_after_load_mb` | **739.0** | worker RSS after the int8 weights load |
| **`rss_peak_mb`** | **798.3** | **peak working set (MB) of the ASR run** |
| `rss_peak_wset_mb` | 804.5 | peak, whole process |
| `load_s` | 1.939 | weights load, seconds |
| `infer_s` | 1.126 | inference, seconds |
| `rtfx_steady` | **14.75**× | faster than realtime (gate run: 10.12×) |
| `n_segments` | 2 | `segment_mode=silence`, `seg_median_s=8.0`, `seg_max_s=8.0` |
| `cpu_median_pct` | 1176.6 | 12 logical cores busy |
| `quantization` | `int8` | from the model dir's own config |
| `session_providers` | `[["CPUExecutionProvider"], ["CPUExecutionProvider"]]` | no CUDA session, by choice |
| `video.index_ms` / `extract.seconds` | 56.7 / 0.035 | video row write / wav extract |
| `model_sha256` | `7db838b6f0e57b8f…` | identity of the weights actually loaded |

The gate's own `CLIPASR-REPORT asr` reports `asr_rss_peak_mb_max = 797.7` MB — the same
measurement taken at a slightly different sample point inside the run. Both are CPU-only, and
both are what this box pays per clip index on CPU.

### rows per minute, and DB bytes per minute

- **speech rows: 2 for 15.0 s of clip = 8 rows per clip-minute.** `db_file_mib_per_clip_minute`
  is 0.53125 MiB and `speech_row_bytes_per_clip_minute` is 4712 B; both are single-clip
  linear extrapolations from a **15 s** clip, so the DB number is an **upper bound** — at this
  size the file is dominated by the schema's own pages, not by the rows.
- **MEASURED before/after the ASR phase: 139 264 B → 139 264 B.** After the `index` phase the
  DB already holds `video:1, segment:0, transcript:0, text_fts:0` at 139 264 B; after the `asr`
  phase the row counts are `video:1, segment:2, transcript:2, text_fts:2` at **the same 139 264
  B** (4096-byte pages). The two segments, two transcripts and two FTS rows fit inside pages
  the schema already reserved: **at 15 s per clip the ASR phase costs zero additional file
  bytes.** The per-minute growth of a *large* index is UNKNOWN (§8).

## 5. Idempotence — the proof, not the promise

Two consecutive full runs of `C.asr_index` on the same clip, same DB:

| run | status | wall | rows | actions |
|---|---|---|---|---|
| RUN 1 | `ok` | 3.827 s | 2 | `{'inserted': 2}` |
| RUN 2 | `ok` | 3.520 s | 2 | `{'kept': 2}` |

`RUN1_after vs RUN2_after DIFF: {}` and every per-table hash is byte-identical:
`video 1075d931c9e4`, `segment 9eda31405d82`, `transcript f77a38e17533`,
`text_fts 416c118a90e6`, `ocr a89149d1aa95`, `embedding de37bdb34a8a`,
`marker 1d42ae6de1ef`, `index_meta 0897a3501b3b`. ARM-C2 adds the second half: the
**same clip under a different filename** produces the same `content_key` and therefore the
same `seg_id`s, so a re-capture of the same footage re-indexes to nothing new.
ARM-A reads the four tokens out of `text_fts` with `MATCH ?` — `ponte`, `interditada`,
`moradores`, `radio` get exactly 1 hit each, and the FTS rowid equals the `seg_id` the
pipeline minted (`7757643230769124496`, `2288948642603608206`).

**How idempotence is built:** `write_speech_row` reads the row first and only INSERTs when it
is absent. An identical row answers `"kept"`; a *disagreeing* row raises `speech-row-conflict`
(status 2). That preflight is why the second run never touches the FTS5 update triggers.

## 6. The control that makes the green worth something — ARM-NEG

`build_negation()` byte-copies the shipped module and does exactly **one** thing: it replaces
the `write_speech_row` preflight with a bare `store.upsert_transcript` (and emits
`action = 'inserted'` so the copy keeps the same control flow). The RED is therefore
indistinguishable from the GREEN control except for the missing preflight.

- **NEG control (first run of the copy): PASS.** A plain INSERT only fires
  `tr_transcript_fts_ai`, which works.
- **NEG negated (second run of the same copy): RED, as required.** The second run reaches the
  `ON CONFLICT DO UPDATE` arm, which fires `tr_transcript_fts_au`/`_ad`, and SQLite answers
  `sqlite3.OperationalError: SQL logic error` — FTS5 refuses the `'delete'` special-insert on
  an ordinary content-storing fts5 table **on this host**. NEG3 `OperationalError`, NEG4
  `'SQL logic error'`, and NEG6 the **real** shipped module succeeding on that very database
  (`{"kept": 2}`). `CLIPASR-GATE-NEG PASS checks=6 failed=0`.

Without this arm the 107 green checks above would only prove the module runs.

## 7. Failure arms — the capture path is never allowed to pay

| arm | what it injects | measured |
|---|---|---|
| ARM-D1 | an ASR worker that exits rc=7 | rc **3**, status `asr-worker-failed: … exited rc=7 and produced no transcript`, DB `{"video":1,"segment":0,"transcript":0,"text_fts":0}` |
| ARM-D2 | an ASR worker that sleeps forever | video row visible on a **second** connection at **t=0.263 s** while the worker is provably alive (`stalled_pid=35548`), driver exits **3** at the 4 s timeout, verdict `asr-worker-timeout`, same row counts as D1 |
| ARM-X | a *pre-existing, disagreeing* transcript row | status `speech-row-conflict`, rc **2**, seg_id named in the message, the stale text left **untouched**, row counts unchanged |
| ARM-V | a clip with no audio track at all | refused, loud, no ASR spawned |

The exit contract, MEASURED: `0` speech rows in index · `2` bad input / refuse · `3` ASR
worker failed or timed out (the video row still present).

## 8. What is UNKNOWN, and the one thing this lane could NOT make work

**DISCLOSURE — a *changed* transcript cannot be written.** On this host, re-indexing a clip
after its transcript text has *changed* for an existing `seg_id` raises
`speech-row-conflict`, status 2, because `store.upsert_transcript`'s UPDATE path hits the same
FTS5 `'delete'` trigger that ARM-NEG turns red (§6). The honest reading: **the index is
append-only per (content_key, start_ms) — a clip's transcript can be created once and kept
forever, but never rewritten in place.** Anyone who needs a re-transcribe-when-the-model-changes
job must change `src/index/*` (not this lane's) — either drop and rebuild the FTS5 triggers or
make the update path use `INSERT OR REPLACE` with a content-storing `'delete'` command SQLite
will accept on this host. This is **a recorded rejected alternative**, not a defect to paper
over: editing `schema.sql` was rejected here on ownership grounds (§10).

**DISCLOSURE — the dispatch-named run file does not exist.**
`_moved/aireplay/runs/P4-aireplay-clip-to-asr.md` **DOES NOT EXIST** — there is no `runs/`
directory at all under `_moved/aireplay/`. The plan of record is
`receipts/receipt-24-clip-to-asr-chain.md` (25 960 B), whose §7.1 states that the chain is
**not idempotent past the video row** — the defect this lane closes. `specs/05-clip-to-asr.md`
is a stub; it was read, and it was not edited.

Also UNKNOWN (not measured, do not quote as fact):

- behaviour on clips **longer than 15 s**: throughput, and whether `seg_max_s` stays at 8.0 s
  as the audio grows — every timing above is from a 15.0 s clip;
- CPU inference time / peak RSS on a longer clip (the 798 MB peak is the 15 s number);
- whether lane C's real muxed capture clip produces the same probe values as this
  ffmpeg-built fixture (the mux path is not built yet — see §4);
- DB growth per clip-minute at real scale — the 139 264 B figure is a 2-clip DB;
- multi-clip throughput, and what the index does when two clips carry the same audio.

## 9. Files touched, and files deliberately not touched

Written: `src/pipeline/clip_to_asr.py`, `src/pipeline/test_clip_to_asr.py`,
`_main/_clipasr-gate-full.log`, `_main/receipt-20261009-clipasr.md` (this file).
Committed: the three files above minus the `.log` (see the table in §2 — `_main/*.log` is
ignored at `.gitignore:227` in `_moved/aireplay`, by the repository's own rule).
That is a deliberate disclosure, not an omission: a force-add would have put a 11.8 kB build
artifact into git against the ignore rule.
Not touched: everything else. `git status --porcelain -uall` in the worktree immediately
before the commit lists exactly THREE untracked paths — the two deliverables and this receipt —
and nothing modified anywhere else in the tree.

## 10. Decisions of record, each with the rejected alternative

1. **Idempotence by minting `seg_id` from `(content_key, start_ms)`** — rejected: editing
   `src/index/schema.sql` to add `UNIQUE(video_id, start_ms)`, because `src/index/*` is not
   this lane's to change.
2. **Leave the FTS5 `'delete'` triggers alone** — same ownership reason; the preflight no-op
   write is the fix, and it is the fix ARM-NEG proves is load-bearing.
3. **CPU provider as the ASR default** — the RSS numbers in §4 are CPU measurements and say so.
4. **Quoting with double-quoted POSIX tokens** instead of rewriting `asr_cmdline` — the
   `--asr-cmd` CLI contract is shipped and the gate must exercise the real code path; on
   Windows, `shlex.split` mangles an interpreter path containing spaces
   (`C:/Program Files/Python311/python.exe`) unless it is one quoted token.
5. **The negation copy keeps `action = 'inserted'`** so its RED is comparable to the GREEN.
6. **`fresh_db()` before every arm** — a gate that reuses a crashed run's directory measures
   nothing: the arm must own its subject's starting state. This was a real defect caught by a
   crash-on-launch (`FOREIGN KEY constraint failed`) and fixed before the numbers above.
7. **`pythonw` rejected as the ASR-launch interpreter** — its stdout is `None`, so no
   transcript can come back. The worker is launched with
   `creationflags = 0x08000000|0x00000008` (CREATE_NO_WINDOW) instead, and the gate's own
   window census is the evidence for "no visible console window" (§11).

## 11. The window census is the instrument, not an impression

`CLIPASR-REPORT census {"distinct_pids": [], "samples": 1261, "visible_hits": 0}` — the gate
samples its own pid tree at **25 ms** across the whole 33.8 s run, 1261 samples, zero visible
console windows. A 60 s house census cannot prove the absence of a short-lived window; this one
samples at the lifetime of the thing it denies. All children (the ASR worker, the D2 stall
worker, the negation copy) inherit `CREATE_NO_WINDOW`.

## 12. Two gate defects found and fixed while getting to this green

Both are recorded because both are the kind that hides a real hang in production.

1. **`make_stall_helper(work)` returned `None`.** The ARM-D2 stall command became
   `"…python.exe" "None" <wav>` — python exited rc=2 in milliseconds, no pidfile ever
   appeared, and D2f measured `asr-worker-failed` instead of a stall. Fixed by returning the
   path; the same stall string then reproduced `asr-worker-timeout` out of band, with
   `wall_s=4.015`.
2. **`pid_alive` probed with STILL_ACTIVE 259 instead of WAIT_TIMEOUT 258.**
   `WaitForSingleObject(handle, 0)` returns **258** for a running process and **0** for one
   that exited; **259 is an exit-code value the wait API never returns**. The old constant
   reported every live process as dead — `pid_alive()` said `False` for the gate's own
   `os.getpid()` — which would have masked a real hang. Measured with the fix in place:
   `OpenProcess h=656 lasterr=0`, `WaitForSingleObject=258`, and a living child correctly
   reported alive.

Both fixes were proven by the runs that followed them (the isolated `--only d2` run:
`ARM-D2 GREEN checks=14 failed=0`).

## 13. Re-verification of the exact bytes that were committed

The two files above were hashed *before* this second run and the run was repeated on the very
bytes that were staged. rc **0**, wall **32.9 s**, `CLIPASR-GATE PASS arms=9 checks=107
failed=0`, `CLIPASR-GATE-NEG PASS checks=6 failed=0`, `CLIPASR-FINAL PASS`, census
`{"distinct_pids": [], "samples": 1228, "visible_hits": 0}`. `asr_rss_peak_mb_max` came back
**797.1 MB** on this run (797.7 and 798.3 on the two earlier ones) — same code path, same
fixture, same CPU provider; the spread is run-to-run noise, not a behavioural difference.
What changed after that run is THIS file only (a section-12 heading restored in the right place, and
the two additions below that carry the `.log` ignore rule and the corrected `git status` count).
The two source files were not touched again — their sha256 in §2 are the bytes that run above
executed, re-checked after the fact: `b1462fc7…` and `9d9e48ad…`, both unchanged.
