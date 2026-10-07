# Probe verdict — `slice_upsert.py` (content_key upsert / idempotency)

Date: 2026-10-07
Lane: execute-and-measure only. **The probe was NOT edited.**

## Commands run (verbatim)

```powershell
python H:\sotto\_moved\aireplay\_main\slice_upsert.py > H:\sotto\_main\probe-upsert-out.txt 2>&1
```

**EXIT CODE: 1** (measured as `$LASTEXITCODE` after the redirect — no pipe)

## Full probe output (`probe-upsert-out.txt`, 16 lines total — the "last 40 lines")

```
db              : G:\Temp\slice-upsert-5eyzkh45\scratch.sqlite
journal_mode    : wal
schema applied  : OK (store.connect runs schema.sql)
content_key     : 973965bdec94ec32... (64 hex chars)
upsert          : video_id=1 seg_id=1 (0.461 ms/row)

SearchIndex     : n=1 dim=256
ranked hits     : 1
Traceback (most recent call last):
  File "H:\sotto\_moved\aireplay\_main\slice_upsert.py", line 115, in <module>
    sys.exit(main())
             ^^^^^^
  File "H:\sotto\_moved\aireplay\_main\slice_upsert.py", line 81, in main
    print(f"  rank={h['rank']} seg_id={h['seg_id']} "
                    ~^^^^^^^^
KeyError: 'rank'
```

## What this means

The crash is at **line 81** — the *print* of the first search hit, not an assertion
failure. Everything up to and including the search itself worked: the schema applied,
the video/segment/embedding upsert landed, and `SearchIndex` returned **n=1, 1 hit**.

Consequence: **lines 86-107 — the entire idempotency block — never executed.**
The probe as committed therefore proves *nothing* about idempotency.

### Root cause (measured, not guessed)

`SearchIndex.search()` hits do **not** carry a top-level `rank` key. Measured keys:

```
['at', 'channels', 'end_ms', 'evidence', 'missing', 'path',
 'score', 'seg_id', 'start_ms', 'video_id']
has 'rank'? False
```

Rank is nested per channel: `hit['evidence']['visual']['rank']` -> `1`, with
`cosine: 1.0`. So `slice_upsert.py:81` (`h['rank']`) is a real bug in the merged
probe (commit `5a1c29a`, "feat(slice-v7): content_key upsert/query/idempotency probe").
One-character-class fix: `h['evidence'][CHANNEL]['rank']`. **Not applied here** — this
lane measures only.

## STEP 3 — the two row counts, and whether idempotency held

The probe itself produced **one** count (implicitly, via its scratch DB, which stopped
at `path=/synthetic/nonexistent-a.mp4`). To answer STEP 3 without editing the probe,
the same `store.*` calls were replayed independently against a fresh scratch DB
(same seed `20261007`, same 256-d vector, same `store.connect` path). Script kept
**outside** the repo at `G:\Temp\_idemp_measure.py`; output in
`probe-upsert-idem.txt`; exit code 0.

| moment | video | segment | embedding |
|---|---|---|---|
| **before** re-upsert (1st insert) | **1** | **1** | **1** |
| **after** re-upsert (same content_key, path changed `nonexistent-a` -> `renamed-b`) | **1** | **1** | **1** |

Also measured:
- `upsert_video` returned `video_id2 = 1`, identical to `video_id = 1` — no new id.
- `SELECT path ... WHERE content_key = ?` -> `/synthetic/renamed-b.mp4` — the row was
  **updated in place** on the renamed/moved file, which is the intended move-semantics.
- `before == after` -> `True`

**IDEMPOTENCY: HELD**, on the row counts, the returned id, and the path update.

### Honest scope of that verdict

- Idempotency is **measured and real** (`video` stays at exactly 1 row).
- It is **not** demonstrated *by the committed probe* — the probe dies before it gets
  there. The proof comes from the independent replay, which is the same code path
  against the same real schema, but is not the artifact under test.

## Reproduction / other evidence

Scratch DBs left by 5 runs today (`G:\Temp\slice-upsert-*`): 3 from 13:41:38-13:41:56
hold `path=/synthetic/renamed-b.mp4` and `video=1` — those earlier runs reached the
re-upsert and still ended with exactly one row. The 13:42:21 checkout rewrote
`slice_upsert.py` to the HEAD version (mtime 13:42:21; the file is clean vs `HEAD`,
`git status --porcelain` empty for that path), which is the version with the
`h['rank']` bug — and every run after it stops at line 81.

## Bottom line

| question | answer |
|---|---|
| probe exit code | **1** |
| row count, 1st insert | **video=1, segment=1, embedding=1** |
| row count, after duplicate content_key | **video=1, segment=1, embedding=1** |
| idempotency held? | **YES** (measured independently) |
| committed probe valid? | **NO** — crashes at `slice_upsert.py:81`, `KeyError: 'rank'`, before any assertion |