# ODS-1 ARM A -- the on-disk search run on a SYNTHETIC store

DUPLICATE ROOM POLICY: NONE WRITTEN IN THIS TREE.
Nothing under the root of this run was created, renamed, linked, copied or removed. Arm A
does not repair, does not dedupe, and does not take the `right` side of a
contradiction -- it prints the sides and ranks them. Every number below was measured at run
time; the synthetic fixture values are CHOSEN test inputs, never measurements.

| run | value |
|---|---|
| instrument | ods1.py, --layout H:/sotto/_moved/aireplay/src/storage/layout.py --root I:\cc-tmp\ods1-armA\store-mutant |
| store root | `I:\cc-tmp\ods1-armA\store-mutant` |
| index db | `I:\cc-tmp\ods1-armA\store-mutant\store.db` |
| run started | 2026-10-10T03:48:42.698850+00:00 |
| layout.py sha256 | fe02e34b9a6339c763e193323a6e9a8e970ca4f15fdf99127543a6b43830ebd6 |
| clips visited (layout.py's own walk) | 5 |
| foreign container files visited | 0 |
| rows emitted | 5 |
| db video rows | 5 |
| db duplicate content_keys | 0 |
| findings | 1 red, 30 informational |
| refusals to produce a duration | 0 |
| self-audit invariants | 7 green, 0 RED |
| exit code | 1 |

## HOW A SOURCE RANK WAS CHOSEN (the priority contract)

`clip-id(1) > key.json(2) > db(3) > container/moov(4) > mtime-derived(5)`

* start = the CLIP ID (rank 1), decoded by parse_clip_id (layout.py:139). Nothing outranks
  the clip id, and no other source can move a start.
* end = the highest-rank source that carries one: key ended_at_s (2) > db duration_ms added
  to that start (3) > container/moov (4) > mtime-derived (5).
* **An absent value prints UNKNOWN. It is never 0 and it is never a guess.**
* A REFUSED container has no duration: it prints UNKNOWN, never 0.

Tolerances (each with where it came from):

| tolerance | value | basis |
|---|---|---|
| interval overlap (C01) | 0.10 s | READ specs/02-asr.md:165 PAD_S 0.10 |
| duration agreement | 1 ms | chosen by this lane (a rounding allowance) |
| key start vs clip id (C09) | 0.000 s | READ layout.py:433 -- the key COPIES the clip id |
| mp4 epoch offset | -2082844800 s | COMPUTED here: datetime(1904,1,1,utc).timestamp() |

NOT MEASURED BY THIS INSTRUMENT: no pixel is read, no SPS/PPS is parsed, no audio or video
stream is decoded, no image is opened, no audio device is opened, nothing is written.

## THE SANITY TRAPS, RUN

1. **Every mvhd/tkhd/mdhd stamp on this writer is the literal 0** (mp4_writer.cpp:257, :272,
   :293). The instrument COUNTS those fields and prints the count; it never converts a 0
   into a date. Zero-epoch fields formatted as dates in this run: **0**.
   Field census over this store: mdhd:creation_time=5, mdhd:modification_time=5, mvhd:creation_time=5, mvhd:modification_time=5, tkhd:creation_time=5, tkhd:modification_time=5.
2. **Missing means UNKNOWN.** %d row(s) carry at least one absent value in this run; each
   prints the literal word UNKNOWN, and the invariant zero_is_never_an_absent_value stays
   green.

## THE TIMELINE (every row carries its evidence path and its ranks)

start is the rank-1 instant. end came from the highest rank that carried one. The last two
columns name WHICH source produced the end and WHAT rank it had.

| # | kind | verdict | start (UTC) | start rank | end (UTC) | end source | end rank | clip id / file | evidence path |
|---|---|---|---|---|---|---|---|---|---|
| 1 | clip | committed | 2026-10-09T12:00:00+00:00 | 1/clip-id | 2026-10-09T12:00:04+00:00 | key.json | 2/key.json | 20261009T120000Z-0001 | I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120000Z-0001 |
| 2 | clip | committed | 2026-10-09T12:00:04+00:00 | 1/clip-id | 2026-10-09T12:00:08+00:00 | key.json | 2/key.json | 20261009T120004Z-0002 | I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120004Z-0002 |
| 3 | clip | committed | 2026-10-09T12:00:08+00:00 | 1/clip-id | 2026-10-09T12:00:12+00:00 | key.json | 2/key.json | 20261009T120008Z-0003 | I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120008Z-0003 |
| 4 | clip | committed | 2026-10-09T12:00:12+00:00 | 1/clip-id | 2026-10-09T12:00:16+00:00 | key.json | 2/key.json | 20261009T120012Z-0004 | I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120012Z-0004 |
| 5 | clip | committed | 2026-10-09T12:00:15+00:00 | 1/clip-id | 2026-10-09T12:00:19+00:00 | key.json | 2/key.json | 20261009T120015Z-0900 | I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120015Z-0900 |

## THE CONTRADICTIONS FOUND, BY CLASS

### C01 -- INTERVAL OVERLAP (1)

* **20261009T120012Z-0004 vs 20261009T120015Z-0900** -- intervals overlap by 1.000 s, which is more than the PAD_S 0.10 s tolerance
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120012Z-0004, I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120015Z-0900 (ranks 2, 2)

### C04 -- ZERO-EPOCH FIELD (not a date) (30)

* **20261009T120000Z-0001** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120000Z-0001** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120000Z-0001** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120000Z-0001** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120000Z-0001** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120000Z-0001** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120004Z-0002** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120004Z-0002** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120004Z-0002** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120004Z-0002** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120004Z-0002** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120004Z-0002** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120008Z-0003** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120008Z-0003** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120008Z-0003** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120008Z-0003** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120008Z-0003** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120008Z-0003** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120012Z-0004** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120012Z-0004** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120012Z-0004** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120012Z-0004** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120012Z-0004** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120012Z-0004** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120015Z-0900** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120015Z-0900 (ranks 4)
* **20261009T120015Z-0900** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120015Z-0900 (ranks 4)
* **20261009T120015Z-0900** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120015Z-0900 (ranks 4)
* **20261009T120015Z-0900** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120015Z-0900 (ranks 4)
* **20261009T120015Z-0900** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120015Z-0900 (ranks 4)
* **20261009T120015Z-0900** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store-mutant\clips\2026\10\09\20261009T120015Z-0900 (ranks 4)

## ROWS THAT REFUSED TO GIVE A DURATION (a refusal is not a zero)

NONE. Every container in this store yielded a duration.

## THE DB, AS IT IS

* tables found: index_meta, video, segment, transcript, ocr, embedding, marker, text_fts, text_fts_data, text_fts_idx, text_fts_content, text_fts_docsize, text_fts_config
* video rows: 5
* duplicate content_key in the live db: **0** (schema.sql:44 declares it UNIQUE)
* rows whose declared path is absent from disk: 0

## SELF-AUDIT -- THIS INSTRUMENT'S OWN INVARIANTS

| invariant | state | detail |
|---|---|---|
| rows_emitted_equals_visited | GREEN | rows=5 clips_visited=5 foreign_visited=0 |
| no_duplicate_rows | GREEN | 5 rows, 5 distinct |
| zero_epoch_fields_formatted_as_dates | GREEN | 0 row(s) printed a DATE derived from an mp4 stamp; the writer of this tree writes the literal 0 (mp4_writer.cpp:257, :272, :293) |
| unknown_prints_as_the_literal_word | GREEN | 0 row(s) carry at least one absent value; each prints 'UNKNOWN', never 0 |
| zero_is_never_an_absent_value | GREEN | 0 row(s) use the number 0 as a value |
| clip_start_is_rank_1_when_present | GREEN | 5 of 5 clip rows started from the CLIP ID (rank 1), the only source that ranks above the key |
| every_identity_claim_was_recomputed | GREEN | identity claims found=5, recomputed against the bytes=5 |

## CENSUS

| bucket | count |
|---|---|
| verdict committed | 5 |
| non-clip-id directories skipped under clips/ | 0 |
| db rows | 5 |
| db duplicate content_keys | 0 |

## WHAT THIS RUN DID NOT VERIFY (say it, do not fill it in)

* The PAD_S 0.10 overlap tolerance is READ from specs/02-asr.md:165, where it is defined
  for ASR segment padding. The spec does not state a tolerance for two CLIP intervals;
  TO-BE-ANSWERED-BY-OWNER.md carries the question.
* No transcript, segment or subject rows exist in this arm, so C06 (a per-subject tiling
  gap) could not be exercised -- schema.sql:65-68 keeps the window in segment, not here.
* A foreign file's duration has no source besides the db and its own moov; no key.json sits
  next to an imported library file.
* Whether an imported moov carries a usable creation_time is UNKNOWN: the only files this
  product writes carry the literal 0, and no foreign file was measured on this box.

PROVENANCE: values under the synthetic store are CHOSEN test inputs; every other number was
measured by this run. The layout.py sha256 above names the exact revision every disk fact
was routed through.

## EXPECTED vs ACTUAL (this run against the fixture manifest)

| store | class | expected | actual | state |
|---|---|---|---|---|
| mutant | C01 | A900 | 1 C01 finding(s) | OK |
| mutant | C02 | NONE | 0 finding(s), 0 red | OK |
| mutant | C03 | NONE | 0 finding(s), 0 red | OK |
| mutant | C04 | NONE | 30 finding(s), 0 red | OK |
| mutant | C05 | NONE | 0 finding(s), 0 red | OK |
| mutant | C06 | NONE | 0 finding(s), 0 red | OK |
| mutant | C07 | NONE | 0 finding(s), 0 red | OK |
| mutant | C08 | NONE | 0 finding(s), 0 red | OK |
| mutant | C09 | NONE | 0 finding(s), 0 red | OK |
| mutant | C2TRAK | NONE | 0 finding(s), 0 red | OK |

10 expectation(s), 0 MISSING.  A MISSING line is a contradiction the
instrument did not catch, or a fixture expectation this run disagrees with --
either way it is a finding, and it is printed, never hidden.
