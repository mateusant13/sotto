You are a VERIFIER. Your seat is READ-ONLY: **edit NOTHING, write NOTHING, create no files.** Report findings as text only.

# The artifact under review
`H:\sotto\_moved\aireplay\specs\04-index-search.md`  (60 KB, sha256 prefix `3fc85e391b5e8dfe`)

It is a SPECIFICATION for a subsystem that does not exist yet. Another lane (L4) is
implementing the code from this spec **in parallel**, right now. So the only question that
matters is:

> **Would an implementer who follows this spec EXACTLY produce something INCOMPATIBLE with
> the real ASR output, or incompatible with the L1 (instant cut) / L2 (audio) interfaces?**

That is the single failure mode you are hunting. Everything else is secondary.

# The ground truth you must check against (read these yourself; do not trust the spec's quotes)

- `H:\sotto\_moved\aireplay\src\asr\segment.py` — the silence splitter
- `H:\sotto\_moved\aireplay\src\asr\transcribe.py` — the CLI, the stdout NDJSON contract
- `H:\sotto\_moved\aireplay\src\asr\runner.py` — the loop that builds the `done` object
- `H:\sotto\_moved\aireplay\src\asr\audio.py` — the 16 kHz mono PCM16 refusal
- `H:\sotto\_moved\aireplay\src\asr\engine.py` — what `verify_model_dir` actually verifies
- `H:\sotto\_moved\aireplay\src\asr\level.py`, `constants.py`
- `H:\sotto\_moved\aireplay\src\capture\replay.h` — L1's cut-side struct (`CutResult`)
- `H:\sotto\_moved\aireplay\src\capture\common.h`
- `H:\sotto\_moved\aireplay\receipts\receipt-07-index-search.md` and
  `H:\sotto\_moved\aireplay\docs\research\07-index-search.md` — the measured design it derives from
- **The real captured output**: `H:\sotto\_moved\aireplay\_main\lane-spec04-asr-emit.json`
  (an actual `done` object the spec's author produced by running the ASR). Read the raw bytes;
  it is UTF-8 with non-ASCII.

# What to check, in priority order

1. **Field/type mismatches.** Does every field the spec says the ASR emits actually exist in
   `runner.py`/`transcribe.py`? Does the spec name a field that does not exist, misspell a key,
   or get a unit wrong (ms vs s, relative vs absolute)? Is `segments[]`'s key list exactly right?
2. **The offset trap.** `runner.py` computes `start = offset_s + a`. The spec makes a big deal
   of absolute-vs-relative and gives a conversion formula in §1.3. **Check that formula against
   the code.** Would an implementer applying it land timestamps in the right place? Is
   `video.audio_offset_ms` given a consistent meaning?
3. **The overlap trap.** Segments overlap (`PAD_S`). Does the spec's schema survive overlapping
   segments — in particular, does `UNIQUE(video_id, start_ms)` hold for the real data, and can
   two segments ever share a start?
4. **Empty text.** `text or ""` can be empty. Does the spec keep `''` and NULL distinct, and is
   `text NOT NULL` actually satisfiable?
5. **Synthesised fields.** The spec insists `producer` and `model_sha256` are NOT emitted and
   must be synthesised. Verify that against `runner.py` and `engine.py`. If either IS emitted,
   the spec is wrong.
6. **The FTS5 rules.** §1.5 says an unquoted hyphenated MATCH RAISES. Verify against the
   evidence in `_main\lane-spec04-fts5-realtext.log` and, if you wish, against
   `_main\lane-spec04-fts5-avail.log` / `_lane-spec04-fts5-tok.log`. Are the tokenizer claims
   right (`ascii`+`remove_diacritics` really failing)? Is the quoting rule implementable as
   written, or does it have a hole?
7. **L1 interface.** Does the NDJSON event in §4.1 map 1:1 onto `CutResult` in `replay.h`? Name
   any field that does not exist or is renamed.
8. **L2 interface.** Does the 16 kHz/mono/PCM16 contract match `audio.py`'s actual refusal
   condition? Does `resample_to_16k` do what the spec claims?
9. **SQL correctness.** Can the DDL in §1 actually be executed as written? Are the FTS5
   triggers, `content_rowid='rowid'` on a composite-PK table, and the `ON CONFLICT ... RETURNING`
   upsert valid on SQLite 3.43.1? Can you find a way to run it?
10. **Self-contradiction.** Any statement in the spec that contradicts another, or contradicts
    `receipt-07` / `specs/01` / `specs/02` / `specs/03`.

# How to verify
You may READ anything. You may RUN read-only commands (`py -3 -c ...`, `Select-String`,
`sqlite3`/`py -3` in-memory experiments) **as long as you write no file into the repo** — if you
need scratch space, use `%TEMP%` only. Do NOT open any audio device. Do NOT launch a GUI or a
visible console window. Do NOT edit any file in `H:\sotto\_moved\aireplay`.

Prefer running something over believing the spec. If the spec asserts a number, check it.

# Output format
Start with exactly one line:

    VERDICT: PASS
  or
    VERDICT: FAIL

Then, for every finding:

- **severity**: BLOCKER (an implementer following the spec produces incompatible/wrong
  behaviour) · MAJOR (a real gap an implementer must guess at) · MINOR (wording/nit)
- **spec location**: the section number and the exact quoted line
- **what is wrong**, stated concretely
- **the evidence**: `file:line` from the source you read, or the command you ran and its output
- **the fix**: the exact replacement text or the exact hookup to write

If you find nothing wrong, say so plainly and list what you actively checked and found sound.
A PASS with nothing checked is worthless. Do not invent findings to look thorough; but do not
soften a real one. An empty "minor nits" section is a legitimate result.

Report your confidence in the VERDICT and name anything you could not check.