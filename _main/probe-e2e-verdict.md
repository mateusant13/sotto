# Verdict -- slice-e2e-probe.py first real execution

Measured 2026-10-07, Windows/pwsh, repo H:\sotto. Measurement only: the probe was
NOT edited and nothing was fixed. This file records what the probe actually did.

## Command run

```
python H:\sotto\_moved\aireplay\_main\slice-e2e-probe.py > H:\sotto\_main\probe-e2e-out.txt 2>&1
```

## Exit code

`RC = 0`  (read from `$LASTEXITCODE` after redirection, not from a pipe)

The probe's own final line: `VERDICT: GREEN -- all checks passed (chain ran end to end)`
`FAILURES` list is therefore empty (the probe returns 1 when it is non-empty).

## PASS/FAIL per stage the probe prints

| Stage | Printed check | Result |
|---|---|---|
| STEP 1  connect/executescript(schema.sql) | schema applied (13 tables) | PASS |
| STEP 2  upsert_video/segment/embeddings | one segment row -- COUNT=1 | PASS |
| STEP 2  upsert_video/segment/embeddings | three embedding rows -- COUNT=3 | PASS |
| STEP 3+4  SearchIndex.search (RRF, 3 ch) | query returns >=1 hit -- 1 hits | PASS |
| STEP 3+4  SearchIndex.search (RRF, 3 ch) | the inserted row is the hit -- got [1] | PASS |
| STEP 3+4  SearchIndex.search (RRF, 3 ch) | hit carries video_id + path | PASS |
| RED  re-upsert same content_key | video row count stays 1 | PASS |
| RED  re-upsert same content_key | segment row count stays 1 | PASS |
| RED  re-upsert same content_key | embedding row count stays 3 | PASS |
| RED  re-upsert same content_key | video_id is stable (rename = UPDATE) | PASS |
| RED  re-upsert same segment BY seg_id | seg_id is stable when passed | PASS |
| RED  re-upsert same content_key | the PATH was updated, the key was not | PASS |
| documented FINDING | finding cleaned up (COUNT back to 1) | PASS |
| CONTROL  different content_key | a different content_key DOES add a row -- COUNT=2 | PASS |

14 checks, 14 PASS, 0 FAIL. The one literal `[RED]` token in the output is the section
HEADER `[RED] re-upsert the SAME content_key...`, not a failed check.

## Most important thing that failed

Nothing in the probe FAILED. The one thing that matters, measured and NOT fixed, is a
real latent defect the probe prints as a finding rather than as a check:

`upsert_segment(seg_id=None)` ALWAYS inserts a new segment row (segment COUNT 1 -> 2),
because schema.sql declares `seg_id INTEGER PRIMARY KEY` with no
`UNIQUE(video_id, start_ms)`. The module docstring's claim that every write is
"a no-op rather than a duplicate" holds for video (content_key UNIQUE) and for
embedding (PRIMARY KEY (seg_id, channel)), but NOT for a segment re-emitted without its
seg_id. A pipeline re-run that omits seg_id silently duplicates segments and their
embeddings. The probe measures this, deletes the row it created to restore state, and
correctly leaves the fix to src/index.

Second caveat, narrower: the "16 ms/query target" is NOT exercised. Measured 0.244 ms at
n=3, and the probe itself says the target is at 211,200 vectors. This run proves the chain
works, not that it is fast.

## Reproducibility (2nd run)

Run twice back to back: `RC1 = 0`, `RC2 = 0`, identical VERDICT line both times.
Output files are not byte-identical (fresh tmpdir name + measured timings differ):

```
SHA256 probe-e2e-out.txt  = 0C7E826991C66D53963FA1388BF68ACB2607588063510C0436BF3F4D3A4E082E
SHA256 probe-e2e-out2.txt = E31EE69513D869F01381BCEA60957638254D7994CE4FAB4D309687829093E223
```

## Last 40 lines of output (of 46), verbatim from probe-e2e-out.txt

```
  page_size          = 4096
  cache_size         = -16000
  tables (13)        = embedding, index_meta, marker, ocr, segment, text_fts, text_fts_config, text_fts_content, text_fts_data, text_fts_docsize, text_fts_idx, transcript, video
  [GREEN] schema applied -- 13 tables

[STEP 2] upsert_video -> upsert_segment -> upsert_embeddings (fp32)
  content_key (sha256) = 3b2f8e02953e0c7563a45ec033c3571edda4e4dd65f1b9179aa99e36579bfc24
  video_id=1  seg_id=1
  embedded 3 channels @ 256-d fp32 (0.150 ms/row MEASURED)
  [GREEN] one segment row -- segment COUNT=1
  [GREEN] three embedding rows -- embedding COUNT=3

[STEP 3+4] SearchIndex.search(query) -- RRF over 3 channels
  index.n=3  index.dim=256  channels loaded=['ocr', 'speech', 'visual']
  query MEASURED 0.244 ms (n=3; the 16 ms/query target is at 211 200 vectors, this is 1)
  hits (1):
     1. seg_id=1 score=0.04426230 channels=['ocr', 'speech', 'visual'] path=SYNTHETIC-NOT-A-REAL-FILE.mp4
        at=G:\Temp\slice-v6-fa7qmv70\SYNTHETIC-NOT-A-REAL-FILE.mp4 @ 00:00.000  evidence={'speech': {'rank': 1, 'cosine': -0.047978}, 'ocr': {'rank': 1, 'cosine': -0.045627}, 'visual': {'rank': 1, 'cosine': 0.018008}}
  [GREEN] query returns >=1 hit -- 1 hits
  [GREEN] GREEN: the inserted row is the hit -- expected seg_id=1, got [1]
  [GREEN] hit carries video_id + path

[RED] re-upsert the SAME content_key, then the SAME segment BY seg_id
  after re-upsert: video=1 segment=1 embedding=3
  video_id stable? True   seg_id stable? True
  [GREEN] RED: video row count stays 1 -- COUNT=1
  [GREEN] RED: segment row count stays 1 -- COUNT=1
  [GREEN] RED: embedding row count stays 3 -- COUNT=3
  [GREEN] RED: video_id is stable (rename = UPDATE) -- 1 -> 1
  [GREEN] RED: seg_id is stable when passed -- 1 -> 1
  [GREEN] RED: the PATH was updated, the key was not -- RENAMED-STILL-SAME-CONTENT.mp4
  FINDING re-confirmed: upsert_segment(seg_id=None) -> new seg_id=2, segment COUNT 1 -> 2 (duplicates; schema has no UNIQUE(video_id,start_ms))
  [GREEN] finding cleaned up (segment COUNT back to 1) -- COUNT=1
  [GREEN] CONTROL: a different content_key DOES add a row -- COUNT=2

  on-disk: 0.133 MiB (page_size=4096, checkpoint=[<sqlite3.Row object at 0x000001F88C1F1A20>])
  total wall: 0.051 s

==============================================================
VERDICT: GREEN -- all checks passed (chain ran end to end)
```
