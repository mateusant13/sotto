# ODS-1 ARM A -- the on-disk search run on a SYNTHETIC store

DUPLICATE ROOM POLICY: NONE WRITTEN IN THIS TREE.
Nothing under the root of this run was created, renamed, linked, copied or removed. Arm A
does not repair, does not dedupe, and does not take the `right` side of a
contradiction -- it prints the sides and ranks them. Every number below was measured at run
time; the synthetic fixture values are CHOSEN test inputs, never measurements.

| run | value |
|---|---|
| instrument | ods1.py, --layout H:/sotto/_moved/aireplay/src/storage/layout.py --root I:\cc-tmp\ods1-armA\store |
| store root | `I:\cc-tmp\ods1-armA\store` |
| index db | `I:\cc-tmp\ods1-armA\store\store.db` |
| run started | 2026-10-10T03:48:42.832299+00:00 |
| layout.py sha256 | fe02e34b9a6339c763e193323a6e9a8e970ca4f15fdf99127543a6b43830ebd6 |
| clips visited (layout.py's own walk) | 17 |
| foreign container files visited | 9 |
| rows emitted | 26 |
| db video rows | 23 |
| db duplicate content_keys | 0 |
| findings | 32 red, 134 informational |
| refusals to produce a duration | 9 |
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
   Field census over this store: mdhd:creation_time=22, mdhd:modification_time=22, mvhd:creation_time=20, mvhd:modification_time=20, tkhd:creation_time=22, tkhd:modification_time=22.
2. **Missing means UNKNOWN.** %d row(s) carry at least one absent value in this run; each
   prints the literal word UNKNOWN, and the invariant zero_is_never_an_absent_value stays
   green.

## THE TIMELINE (every row carries its evidence path and its ranks)

start is the rank-1 instant. end came from the highest rank that carried one. The last two
columns name WHICH source produced the end and WHAT rank it had.

| # | kind | verdict | start (UTC) | start rank | end (UTC) | end source | end rank | clip id / file | evidence path |
|---|---|---|---|---|---|---|---|---|---|
| 1 | clip | committed | 2026-10-09T12:00:00+00:00 | 1/clip-id | 2026-10-09T12:00:04+00:00 | key.json | 2/key.json | 20261009T120000Z-0001 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120000Z-0001 |
| 2 | clip | committed | 2026-10-09T12:00:04+00:00 | 1/clip-id | 2026-10-09T12:00:08+00:00 | key.json | 2/key.json | 20261009T120004Z-0002 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120004Z-0002 |
| 3 | clip | committed | 2026-10-09T12:00:08+00:00 | 1/clip-id | 2026-10-09T12:00:12+00:00 | key.json | 2/key.json | 20261009T120008Z-0003 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120008Z-0003 |
| 4 | clip | committed | 2026-10-09T12:00:12+00:00 | 1/clip-id | 2026-10-09T12:00:16+00:00 | key.json | 2/key.json | 20261009T120012Z-0004 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120012Z-0004 |
| 5 | clip | committed | 2026-10-09T12:00:20+00:00 | 1/clip-id | 2026-10-09T12:00:23.500000+00:00 | key.json | 2/key.json | 20261009T120020Z-0005 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005 |
| 6 | clip | committed | 2026-10-09T12:00:40+00:00 | 1/clip-id | 2026-10-09T12:00:44+00:00 | key.json | 2/key.json | 20261009T120040Z-0006 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 |
| 7 | clip | committed | 2026-10-09T12:01:00+00:00 | 1/clip-id | 2026-10-09T12:00:58+00:00 | key.json | 2/key.json | 20261009T120100Z-0007 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120100Z-0007 |
| 8 | clip | committed | 2026-10-09T12:01:20+00:00 | 1/clip-id | 2026-10-09T12:01:24+00:00 | key.json | 2/key.json | 20261009T120120Z-0008 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120120Z-0008 |
| 9 | clip | committed | 2026-10-09T12:01:21+00:00 | 1/clip-id | 2026-10-09T12:01:25+00:00 | key.json | 2/key.json | 20261009T120121Z-0009 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009 |
| 10 | clip | committed | 2026-10-09T12:01:30+00:00 | 1/clip-id | 2026-10-09T12:01:33+00:00 | key.json | 2/key.json | 20261009T120130Z-0010 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010 |
| 11 | clip | partial-committed | 2026-10-09T12:01:34+00:00 | 1/clip-id | 2026-10-09T12:01:37+00:00 | key.json | 2/key.json | 20261009T120134Z-0011 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120134Z-0011 |
| 12 | clip | partial-uncommitted | 2026-10-09T12:01:38+00:00 | 1/clip-id | 2026-10-09T12:01:38+00:00 | db | 3/db | 20261009T120138Z-0012 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120138Z-0012 |
| 13 | clip | partial-uncommitted | 2026-10-09T12:01:50+00:00 | 1/clip-id | 2026-10-09T12:01:52.500000+00:00 | db | 3/db | 20261009T120150Z-0013 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013 |
| 14 | clip | orphan-key | 2026-10-09T12:01:54+00:00 | 1/clip-id | 2026-10-09T12:01:54+00:00 | db | 3/db | 20261009T120154Z-0014 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014 |
| 15 | clip | missing-media | 2026-10-09T12:01:58+00:00 | 1/clip-id | 2026-10-09T12:02:00+00:00 | key.json | 2/key.json | 20261009T120158Z-0015 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120158Z-0015 |
| 16 | clip | partial-uncommitted | 2026-10-09T12:02:05+00:00 | 1/clip-id | 2026-10-09T12:02:08+00:00 | key.json | 2/key.json | 20261009T120205Z-0016 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016 |
| 17 | clip | committed | 2026-10-09T12:02:20+00:00 | 1/clip-id | 2026-10-09T12:02:22+00:00 | key.json | 2/key.json | 20261009T120220Z-0017 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120220Z-0017 |
| 18 | foreign | None | 2026-10-10T02:10:32.753729+00:00 | 5/mtime | 2026-10-10T02:10:32.753729+00:00 | db | 3/db | clip.mp4 | I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4 |
| 19 | foreign | None | 2026-10-09T12:04:20+00:00 | 5/mtime | 2026-10-09T12:04:20+00:00 | db | 3/db | db-zero-duration.mp4 | I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 |
| 20 | foreign | None | 2026-10-09T12:00:05.500000+00:00 | 5/mtime | 2026-10-09T12:00:08+00:00 | db | 3/db | legacy-2026-09-01.mp4 | I:\cc-tmp\ods1-armA\store\imports\legacy-2026-09-01.mp4 |
| 21 | foreign | None | UNKNOWN | 5/mtime | UNKNOWN | UNKNOWN | -- | moov-no-duration.mp4 | I:\cc-tmp\ods1-armA\store\imports\moov-no-duration.mp4 |
| 22 | foreign | None | UNKNOWN | 5/mtime | UNKNOWN | UNKNOWN | -- | moov-no-timescale.mp4 | I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4 |
| 23 | foreign | None | UNKNOWN | 5/mtime | UNKNOWN | UNKNOWN | -- | moov-truncated.mp4 | I:\cc-tmp\ods1-armA\store\imports\moov-truncated.mp4 |
| 24 | foreign | None | UNKNOWN | 5/mtime | UNKNOWN | UNKNOWN | -- | mp4-unknown-box.mp4 | I:\cc-tmp\ods1-armA\store\imports\mp4-unknown-box.mp4 |
| 25 | foreign | None | UNKNOWN | 5/mtime | UNKNOWN | UNKNOWN | -- | mvhd-v1.mp4 | I:\cc-tmp\ods1-armA\store\imports\mvhd-v1.mp4 |
| 26 | foreign | None | UNKNOWN | 5/mtime | UNKNOWN | UNKNOWN | -- | not-really.mp4 | I:\cc-tmp\ods1-armA\store\imports\not-really.mp4 |

## THE CONTRADICTIONS FOUND, BY CLASS

### C01 -- INTERVAL OVERLAP (1)

* **20261009T120120Z-0008 vs 20261009T120121Z-0009** -- intervals overlap by 3.000 s, which is more than the PAD_S 0.10 s tolerance
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120120Z-0008, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009 (ranks 2, 2)

### C02 -- IDENTITY CLAIM LIES (3)

* **20261009T120220Z-0017** -- key.json claims content_key=34743952a84bfff10a838fc4120d54727b468f997e3e680d4f4713ea8be981be but the bytes hash to dbc16d9f72fc9ca7bf51119a511fde384c4a1c67fee8e7f16db9c3caa65546e2: identity by content is NOT what the row claims
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120220Z-0017\key.json, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120220Z-0017 (ranks 2, 1)
* **sha256=386b4226ee4f8d118f697887ecc0698f27d93f59589d147549c8fc9b539b07fb** -- 2 rows share one whole-file sha256; the index enforces UNIQUE(content_key) (schema.sql:44) so only ONE may be indexed -- the rest is DUPLICATE ROOM this tree does NOT write
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4, I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 (ranks 3, 3)
* **sha256=bc61af69259b9f5bf1850cfef1eb10200d67491270bc95de621d10c3305022db** -- 2 rows share one whole-file sha256; the index enforces UNIQUE(content_key) (schema.sql:44) so only ONE may be indexed -- the rest is DUPLICATE ROOM this tree does NOT write
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120120Z-0008, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009 (ranks 2, 2)

### C03 -- DB ROW ABSENT (4)

* **20261009T120121Z-0009** -- a committed clip is on disk with no video row naming it: the index never saw it
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009 (ranks 1)
* **20261009T120130Z-0010** -- a committed clip is on disk with no video row naming it: the index never saw it
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010 (ranks 1)
* **db path=I:\cc-tmp\ods1-armA\store\clips\2026\10\07\20261007T000000Z-0001\clip.mp4** -- the db row names a path that is not on disk; its content_key deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef is nowhere in this root
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\07\20261007T000000Z-0001\clip.mp4 (ranks 3)
* **db path=I:\cc-tmp\ods1-armA\store\clips\2026\10\08\20261008T110000Z-0099\clip.mp4** -- the db row's path is gone but its content_key is present at another path: identity survived, the path did not
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\08\20261008T110000Z-0099\clip.mp4, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010 (ranks 3, 1)

### C04 -- ZERO-EPOCH FIELD (not a date) (124)

* **20261009T120000Z-0001** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120000Z-0001** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120000Z-0001** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120000Z-0001** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120000Z-0001** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120000Z-0001** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120000Z-0001 (ranks 4)
* **20261009T120004Z-0002** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120004Z-0002** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120004Z-0002** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120004Z-0002** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120004Z-0002** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120004Z-0002** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120004Z-0002 (ranks 4)
* **20261009T120008Z-0003** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120008Z-0003** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120008Z-0003** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120008Z-0003** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120008Z-0003** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120008Z-0003** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120008Z-0003 (ranks 4)
* **20261009T120012Z-0004** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120012Z-0004** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120012Z-0004** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120012Z-0004** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120012Z-0004** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120012Z-0004** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120012Z-0004 (ranks 4)
* **20261009T120020Z-0005** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005 (ranks 4)
* **20261009T120020Z-0005** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005 (ranks 4)
* **20261009T120020Z-0005** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005 (ranks 4)
* **20261009T120020Z-0005** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005 (ranks 4)
* **20261009T120020Z-0005** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005 (ranks 4)
* **20261009T120020Z-0005** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005 (ranks 4)
* **20261009T120040Z-0006** -- mdhd:creation_time is literal 0 in 2 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 (ranks 4)
* **20261009T120040Z-0006** -- mdhd:modification_time is literal 0 in 2 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 (ranks 4)
* **20261009T120040Z-0006** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 (ranks 4)
* **20261009T120040Z-0006** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 (ranks 4)
* **20261009T120040Z-0006** -- tkhd:creation_time is literal 0 in 2 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 (ranks 4)
* **20261009T120040Z-0006** -- tkhd:modification_time is literal 0 in 2 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 (ranks 4)
* **20261009T120100Z-0007** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120100Z-0007 (ranks 4)
* **20261009T120100Z-0007** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120100Z-0007 (ranks 4)
* **20261009T120100Z-0007** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120100Z-0007 (ranks 4)
* **20261009T120100Z-0007** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120100Z-0007 (ranks 4)
* **20261009T120100Z-0007** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120100Z-0007 (ranks 4)
* **20261009T120100Z-0007** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120100Z-0007 (ranks 4)
* **20261009T120120Z-0008** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120120Z-0008 (ranks 4)
* **20261009T120120Z-0008** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120120Z-0008 (ranks 4)
* **20261009T120120Z-0008** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120120Z-0008 (ranks 4)
* **20261009T120120Z-0008** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120120Z-0008 (ranks 4)
* **20261009T120120Z-0008** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120120Z-0008 (ranks 4)
* **20261009T120120Z-0008** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120120Z-0008 (ranks 4)
* **20261009T120121Z-0009** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009 (ranks 4)
* **20261009T120121Z-0009** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009 (ranks 4)
* **20261009T120121Z-0009** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009 (ranks 4)
* **20261009T120121Z-0009** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009 (ranks 4)
* **20261009T120121Z-0009** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009 (ranks 4)
* **20261009T120121Z-0009** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009 (ranks 4)
* **20261009T120130Z-0010** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010 (ranks 4)
* **20261009T120130Z-0010** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010 (ranks 4)
* **20261009T120130Z-0010** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010 (ranks 4)
* **20261009T120130Z-0010** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010 (ranks 4)
* **20261009T120130Z-0010** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010 (ranks 4)
* **20261009T120130Z-0010** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010 (ranks 4)
* **20261009T120134Z-0011** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120134Z-0011 (ranks 4)
* **20261009T120134Z-0011** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120134Z-0011 (ranks 4)
* **20261009T120134Z-0011** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120134Z-0011 (ranks 4)
* **20261009T120134Z-0011** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120134Z-0011 (ranks 4)
* **20261009T120134Z-0011** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120134Z-0011 (ranks 4)
* **20261009T120134Z-0011** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120134Z-0011 (ranks 4)
* **20261009T120150Z-0013** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013 (ranks 4)
* **20261009T120150Z-0013** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013 (ranks 4)
* **20261009T120150Z-0013** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013 (ranks 4)
* **20261009T120150Z-0013** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013 (ranks 4)
* **20261009T120150Z-0013** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013 (ranks 4)
* **20261009T120150Z-0013** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013 (ranks 4)
* **20261009T120154Z-0014** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014 (ranks 4)
* **20261009T120154Z-0014** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014 (ranks 4)
* **20261009T120154Z-0014** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014 (ranks 4)
* **20261009T120154Z-0014** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014 (ranks 4)
* **20261009T120154Z-0014** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014 (ranks 4)
* **20261009T120154Z-0014** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014 (ranks 4)
* **20261009T120205Z-0016** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016 (ranks 4)
* **20261009T120205Z-0016** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016 (ranks 4)
* **20261009T120205Z-0016** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016 (ranks 4)
* **20261009T120205Z-0016** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016 (ranks 4)
* **20261009T120205Z-0016** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016 (ranks 4)
* **20261009T120205Z-0016** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016 (ranks 4)
* **20261009T120220Z-0017** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120220Z-0017 (ranks 4)
* **20261009T120220Z-0017** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120220Z-0017 (ranks 4)
* **20261009T120220Z-0017** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120220Z-0017 (ranks 4)
* **20261009T120220Z-0017** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120220Z-0017 (ranks 4)
* **20261009T120220Z-0017** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120220Z-0017 (ranks 4)
* **20261009T120220Z-0017** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120220Z-0017 (ranks 4)
* **clip.mp4** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4 (ranks 4)
* **clip.mp4** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4 (ranks 4)
* **clip.mp4** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4 (ranks 4)
* **clip.mp4** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4 (ranks 4)
* **clip.mp4** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4 (ranks 4)
* **clip.mp4** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4 (ranks 4)
* **db-zero-duration.mp4** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 (ranks 4)
* **db-zero-duration.mp4** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 (ranks 4)
* **db-zero-duration.mp4** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 (ranks 4)
* **db-zero-duration.mp4** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 (ranks 4)
* **db-zero-duration.mp4** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 (ranks 4)
* **db-zero-duration.mp4** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 (ranks 4)
* **legacy-2026-09-01.mp4** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\legacy-2026-09-01.mp4 (ranks 4)
* **legacy-2026-09-01.mp4** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\legacy-2026-09-01.mp4 (ranks 4)
* **legacy-2026-09-01.mp4** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\legacy-2026-09-01.mp4 (ranks 4)
* **legacy-2026-09-01.mp4** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\legacy-2026-09-01.mp4 (ranks 4)
* **legacy-2026-09-01.mp4** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\legacy-2026-09-01.mp4 (ranks 4)
* **legacy-2026-09-01.mp4** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\legacy-2026-09-01.mp4 (ranks 4)
* **moov-no-duration.mp4** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-duration.mp4 (ranks 4)
* **moov-no-duration.mp4** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-duration.mp4 (ranks 4)
* **moov-no-duration.mp4** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-duration.mp4 (ranks 4)
* **moov-no-duration.mp4** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-duration.mp4 (ranks 4)
* **moov-no-duration.mp4** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-duration.mp4 (ranks 4)
* **moov-no-duration.mp4** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-duration.mp4 (ranks 4)
* **moov-no-timescale.mp4** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4 (ranks 4)
* **moov-no-timescale.mp4** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4 (ranks 4)
* **moov-no-timescale.mp4** -- mvhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4 (ranks 4)
* **moov-no-timescale.mp4** -- mvhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4 (ranks 4)
* **moov-no-timescale.mp4** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4 (ranks 4)
* **moov-no-timescale.mp4** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4 (ranks 4)
* **mvhd-v1.mp4** -- mdhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\mvhd-v1.mp4 (ranks 4)
* **mvhd-v1.mp4** -- mdhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\mvhd-v1.mp4 (ranks 4)
* **mvhd-v1.mp4** -- tkhd:creation_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\mvhd-v1.mp4 (ranks 4)
* **mvhd-v1.mp4** -- tkhd:modification_time is literal 0 in 1 box(es).  A 0 in an MP4 time field means 1904-01-01 and the writer of this product WRITES the 0 (mp4_writer.cpp), so this tree CANNOT carry a wall clock.  The instrument prints the literal, not a date.
  * evidence: I:\cc-tmp\ods1-armA\store\imports\mvhd-v1.mp4 (ranks 4)

### C05 -- NEGATIVE OR ZERO INTERVAL (5)

* **20261009T120100Z-0007** -- the chosen end (1791547258.000000) does not come after the rank-1 start (1791547260.000000, source=clip-id): the row is not a time interval at all
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120100Z-0007 (ranks 2)
* **20261009T120138Z-0012** -- the chosen end (1791547298.000000) does not come after the rank-1 start (1791547298.000000, source=clip-id): the row is not a time interval at all
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120138Z-0012 (ranks 3)
* **20261009T120154Z-0014** -- the chosen end (1791547314.000000) does not come after the rank-1 start (1791547314.000000, source=clip-id): the row is not a time interval at all
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014 (ranks 3)
* **clip.mp4** -- the chosen end (1791598232.753729) does not come after the rank-5 start (1791598232.753729, source=mtime): the row is not a time interval at all
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4 (ranks 3)
* **db-zero-duration.mp4** -- the chosen end (1791547460.000000) does not come after the rank-5 start (1791547460.000000, source=mtime): the row is not a time interval at all
  * evidence: I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 (ranks 3)

### C07 -- DECLARED vs DECODED (1)

* **20261009T120040Z-0006** -- key.json duration_ms=4000 but the moov video trak decodes 5000 ms (1000 ms apart, tolerance 1 ms)
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006\key.json, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 (ranks 2, 4)

### C08 -- DURATION SOURCE MISMATCH (5)

* **20261009T120040Z-0006** -- db duration_ms=4000 but the moov video trak decodes 5000 ms (1000 ms apart, tolerance 1 ms)
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006\clip.mp4, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 (ranks 3, 4)
* **20261009T120154Z-0014** -- db duration_ms=0 but the moov video trak decodes 2000 ms (2000 ms apart, tolerance 1 ms)
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014\clip.mp4, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014 (ranks 3, 4)
* **clip.mp4** -- db duration_ms=0 but the moov video trak decodes 2000 ms (2000 ms apart, tolerance 1 ms)
  * evidence: I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4 (ranks 3, 4)
* **db-zero-duration.mp4** -- db duration_ms=0 but the moov video trak decodes 2000 ms (2000 ms apart, tolerance 1 ms)
  * evidence: I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4, I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 (ranks 3, 4)
* **legacy-2026-09-01.mp4** -- db duration_ms=2500 but the moov video trak decodes 3000 ms (500 ms apart, tolerance 1 ms)
  * evidence: I:\cc-tmp\ods1-armA\store\imports\legacy-2026-09-01.mp4, I:\cc-tmp\ods1-armA\store\imports\legacy-2026-09-01.mp4 (ranks 3, 4)

### C09 -- KEY START vs CLIP ID (1)

* **20261009T120020Z-0005** -- key started_at_s=1791547220.500000 but the directory's clip id decodes to 1791547220.000000 (0.500 s apart, tolerance 0.000 s -- layout.py:433 copies the clip-id start INTO the key, so any difference means one of the two is not the record this product wrote)
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005\key.json, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005 (ranks 2, 1)

### C2TRAK -- TRAK DURATIONS DISAGREE (1)

* **20261009T120040Z-0006** -- inside ONE container the traks disagree by 3.000 s (tolerance 1 ms): a reader that takes max, min or the first trak gets three different clip lengths
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 (ranks 4)

### R-DATA-QUALITY -- DB DURATION ZERO FOR A READABLE CLIP (3)

* **20261009T120154Z-0014** -- the db declares duration_ms=0 for a container that decodes 2000 ms: a 0 is a fact about the row, not about the clip
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120154Z-0014 (ranks 3, 4)
* **clip.mp4** -- the db declares duration_ms=0 for a container that decodes 2000 ms: a 0 is a fact about the row, not about the clip
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\not-a-clip-id\clip.mp4 (ranks 3, 4)
* **db-zero-duration.mp4** -- the db declares duration_ms=0 for a container that decodes 2000 ms: a 0 is a fact about the row, not about the clip
  * evidence: I:\cc-tmp\ods1-armA\store\imports\db-zero-duration.mp4 (ranks 3, 4)

### REFUSAL -- REFUSED TO PRODUCE A DURATION (9)

* **20261009T120138Z-0012** -- R-BOX-TRUNCATED: box '110|' at 40 in top-level declares size 1935764596 but only 16 bytes remain: it claims past EOF -> R-NO-MOOV: no moov box was reached, so there is no sample table to read a duration from
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120138Z-0012 (ranks 4)
* **20261009T120150Z-0013** -- R-VERSION: LayoutError: key I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013\key.json is layout_version=2; this build has NO read rule for it (known: [1]). Refusing beats reading a v2 as v1.
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013 (ranks 2)
* **20261009T120205Z-0016** -- R-WRONG-DIR: key.json claims clip_id=20261009T123319Z-9999 but this directory is 20261009T120205Z-0016, so layout.py refuses the key and the clip_id of the key does NOT override the directory (the directory stays rank 1)
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016\key.json, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016 (ranks 2, 1)
* **moov-no-duration.mp4** -- R-NO-DURATION: trak 'vide' has mdhd (timescale 1000) but no stts: the sample-to-duration table is absent, so its duration is UNKNOWN -> R-DURATION-UNKNOWN: the duration could not be produced from the bytes that were readable
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-duration.mp4 (ranks 4)
* **moov-no-timescale.mp4** -- R-NO-TIMESCALE: mdhd timescale == 0 in I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4: the duration ticks (2000) exist but there is no time base to divide by, so NO duration is produced (not 0) -> R-NO-DURATION: the box that would carry the duration is in a version this instrument does not parse, so its duration stays UNKNOWN, never 0
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4 (ranks 4)
* **moov-truncated.mp4** -- R-BOX-TRUNCATED: box 'moov' at 3240 in top-level declares size 2190 but only 12 bytes remain: it claims past EOF -> R-NO-MOOV: no moov box was reached, so there is no sample table to read a duration from
  * evidence: I:\cc-tmp\ods1-armA\store\imports\moov-truncated.mp4 (ranks 4)
* **mp4-unknown-box.mp4** -- R-BOX-UNKNOWN: box 'zzzz' at 32 in top-level is outside the implemented vocabulary -> R-NO-MOOV: no moov box was reached, so there is no sample table to read a duration from
  * evidence: I:\cc-tmp\ods1-armA\store\imports\mp4-unknown-box.mp4 (ranks 4)
* **mvhd-v1.mp4** -- R-BOX-VERSION: mvhd version 1: only v0 (32-bit fields) is implemented, so NO mvhd value is read -> R-NO-DURATION: the box that would carry the duration is in a version this instrument does not parse, so its duration stays UNKNOWN, never 0
  * evidence: I:\cc-tmp\ods1-armA\store\imports\mvhd-v1.mp4 (ranks 4)
* **not-really.mp4** -- R-BOX-TRUNCATED: box 'an m' at 0 in top-level declares size 1313821728 but only 61 bytes remain: it claims past EOF -> R-NO-FTYP: the walk never reached an ftyp box, so the container brand was never recognised
  * evidence: I:\cc-tmp\ods1-armA\store\imports\not-really.mp4 (ranks 4)

### INFO-GAP -- BETWEEN-CLIP GAP (informational) (9)

* **20261009T120012Z-0004 -> 20261009T120020Z-0005** -- 4.000 s with no clip.  A gap between two CLIPS is not a finding: schema.sql:65-68 keeps the 5 s ASR window in segment, so the spec never asks clips to tile a subject
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120012Z-0004, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005 (ranks 1, 1)
* **20261009T120020Z-0005 -> 20261009T120040Z-0006** -- 16.500 s with no clip.  A gap between two CLIPS is not a finding: schema.sql:65-68 keeps the 5 s ASR window in segment, so the spec never asks clips to tile a subject
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120020Z-0005, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006 (ranks 1, 1)
* **20261009T120040Z-0006 -> 20261009T120120Z-0008** -- 36.000 s with no clip.  A gap between two CLIPS is not a finding: schema.sql:65-68 keeps the 5 s ASR window in segment, so the spec never asks clips to tile a subject
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120040Z-0006, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120120Z-0008 (ranks 1, 1)
* **20261009T120121Z-0009 -> 20261009T120130Z-0010** -- 5.000 s with no clip.  A gap between two CLIPS is not a finding: schema.sql:65-68 keeps the 5 s ASR window in segment, so the spec never asks clips to tile a subject
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120121Z-0009, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010 (ranks 1, 1)
* **20261009T120130Z-0010 -> 20261009T120134Z-0011** -- 1.000 s with no clip.  A gap between two CLIPS is not a finding: schema.sql:65-68 keeps the 5 s ASR window in segment, so the spec never asks clips to tile a subject
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120130Z-0010, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120134Z-0011 (ranks 1, 1)
* **20261009T120134Z-0011 -> 20261009T120150Z-0013** -- 13.000 s with no clip.  A gap between two CLIPS is not a finding: schema.sql:65-68 keeps the 5 s ASR window in segment, so the spec never asks clips to tile a subject
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120134Z-0011, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013 (ranks 1, 1)
* **20261009T120150Z-0013 -> 20261009T120158Z-0015** -- 5.500 s with no clip.  A gap between two CLIPS is not a finding: schema.sql:65-68 keeps the 5 s ASR window in segment, so the spec never asks clips to tile a subject
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120158Z-0015 (ranks 1, 1)
* **20261009T120158Z-0015 -> 20261009T120205Z-0016** -- 5.000 s with no clip.  A gap between two CLIPS is not a finding: schema.sql:65-68 keeps the 5 s ASR window in segment, so the spec never asks clips to tile a subject
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120158Z-0015, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016 (ranks 1, 1)
* **20261009T120205Z-0016 -> 20261009T120220Z-0017** -- 12.000 s with no clip.  A gap between two CLIPS is not a finding: schema.sql:65-68 keeps the 5 s ASR window in segment, so the spec never asks clips to tile a subject
  * evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016, I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120220Z-0017 (ranks 1, 1)

## ROWS THAT REFUSED TO GIVE A DURATION (a refusal is not a zero)

* 20261009T120138Z-0012 -- R-BOX-TRUNCATED: box '110|' at 40 in top-level declares size 1935764596 but only 16 bytes remain: it claims past EOF -> R-NO-MOOV: no moov box was reached, so there is no sample table to read a duration from (evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120138Z-0012)
* 20261009T120150Z-0013 -- R-VERSION: LayoutError: key I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013\key.json is layout_version=2; this build has NO read rule for it (known: [1]). Refusing beats reading a v2 as v1. (evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120150Z-0013)
* moov-no-duration.mp4 -- R-NO-DURATION: trak 'vide' has mdhd (timescale 1000) but no stts: the sample-to-duration table is absent, so its duration is UNKNOWN -> R-DURATION-UNKNOWN: the duration could not be produced from the bytes that were readable (evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-duration.mp4)
* moov-no-timescale.mp4 -- R-NO-TIMESCALE: mdhd timescale == 0 in I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4: the duration ticks (2000) exist but there is no time base to divide by, so NO duration is produced (not 0) -> R-NO-DURATION: the box that would carry the duration is in a version this instrument does not parse, so its duration stays UNKNOWN, never 0 (evidence: I:\cc-tmp\ods1-armA\store\imports\moov-no-timescale.mp4)
* moov-truncated.mp4 -- R-BOX-TRUNCATED: box 'moov' at 3240 in top-level declares size 2190 but only 12 bytes remain: it claims past EOF -> R-NO-MOOV: no moov box was reached, so there is no sample table to read a duration from (evidence: I:\cc-tmp\ods1-armA\store\imports\moov-truncated.mp4)
* mp4-unknown-box.mp4 -- R-BOX-UNKNOWN: box 'zzzz' at 32 in top-level is outside the implemented vocabulary -> R-NO-MOOV: no moov box was reached, so there is no sample table to read a duration from (evidence: I:\cc-tmp\ods1-armA\store\imports\mp4-unknown-box.mp4)
* mvhd-v1.mp4 -- R-BOX-VERSION: mvhd version 1: only v0 (32-bit fields) is implemented, so NO mvhd value is read -> R-NO-DURATION: the box that would carry the duration is in a version this instrument does not parse, so its duration stays UNKNOWN, never 0 (evidence: I:\cc-tmp\ods1-armA\store\imports\mvhd-v1.mp4)
* not-really.mp4 -- R-BOX-TRUNCATED: box 'an m' at 0 in top-level declares size 1313821728 but only 61 bytes remain: it claims past EOF -> R-NO-FTYP: the walk never reached an ftyp box, so the container brand was never recognised (evidence: I:\cc-tmp\ods1-armA\store\imports\not-really.mp4)
* 20261009T120205Z-0016 -- R-WRONG-DIR: key.json claims clip_id=20261009T123319Z-9999 but this directory is 20261009T120205Z-0016, so layout.py refuses the key and the clip_id of the key does NOT override the directory (the directory stays rank 1) (evidence: I:\cc-tmp\ods1-armA\store\clips\2026\10\09\20261009T120205Z-0016\key.json)

## THE DB, AS IT IS

* tables found: index_meta, video, segment, transcript, ocr, embedding, marker, text_fts, text_fts_data, text_fts_idx, text_fts_content, text_fts_docsize, text_fts_config
* video rows: 23
* duplicate content_key in the live db: **0** (schema.sql:44 declares it UNIQUE)
* rows whose declared path is absent from disk: 2

## SELF-AUDIT -- THIS INSTRUMENT'S OWN INVARIANTS

| invariant | state | detail |
|---|---|---|
| rows_emitted_equals_visited | GREEN | rows=26 clips_visited=17 foreign_visited=9 |
| no_duplicate_rows | GREEN | 26 rows, 26 distinct |
| zero_epoch_fields_formatted_as_dates | GREEN | 0 row(s) printed a DATE derived from an mp4 stamp; the writer of this tree writes the literal 0 (mp4_writer.cpp:257, :272, :293) |
| unknown_prints_as_the_literal_word | GREEN | 6 row(s) carry at least one absent value; each prints 'UNKNOWN', never 0 |
| zero_is_never_an_absent_value | GREEN | 0 row(s) use the number 0 as a value |
| clip_start_is_rank_1_when_present | GREEN | 17 of 17 clip rows started from the CLIP ID (rank 1), the only source that ranks above the key |
| every_identity_claim_was_recomputed | GREEN | identity claims found=13, recomputed against the bytes=13 |

## CENSUS

| bucket | count |
|---|---|
| verdict None | 9 |
| verdict committed | 11 |
| verdict missing-media | 1 |
| verdict orphan-key | 1 |
| verdict partial-committed | 1 |
| verdict partial-uncommitted | 3 |
| non-clip-id directories skipped under clips/ | 1 |
| db rows | 23 |
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
| full | C01 | A008 | 1 C01 finding(s) | OK |
| full | C01 | A009 | 1 C01 finding(s) | OK |
| full | C02 | A008 | 3 C02 finding(s) | OK |
| full | C02 | A009 | 3 C02 finding(s) | OK |
| full | C02 | A017 | 3 C02 finding(s) | OK |
| full | C03 | A010 | 4 C03 finding(s) | OK |
| full | C04 | NONE | 124 finding(s), 0 red | OK |
| full | C05 | A007 | 5 C05 finding(s) | OK |
| full | C06 | NONE | 0 finding(s), 0 red | OK |
| full | C07 | A006 | 1 C07 finding(s) | OK |
| full | C08 | legacy-2026-09-01.mp4 | 5 C08 finding(s) | OK |
| full | C08 | db-zero-duration.mp4 | 5 C08 finding(s) | OK |
| full | C09 | A005 | 1 C09 finding(s) | OK |
| full | C2TRAK | A006 | 1 C2TRAK finding(s) | OK |
| full | REFUSAL | A012 | 9 REFUSAL finding(s) in this run | OK |
| full | REFUSAL | A013 | 9 REFUSAL finding(s) in this run | OK |
| full | REFUSAL | A016 | 9 REFUSAL finding(s) in this run | OK |
| full | REFUSAL | moov-no-duration.mp4 | 9 REFUSAL finding(s) in this run | OK |
| full | REFUSAL | not-really.mp4 | 9 REFUSAL finding(s) in this run | OK |
| full | REFUSAL | moov-truncated.mp4 | 9 REFUSAL finding(s) in this run | OK |
| full | REFUSAL | mp4-unknown-box.mp4 | 9 REFUSAL finding(s) in this run | OK |
| full | REFUSAL | moov-no-timescale.mp4 | 9 REFUSAL finding(s) in this run | OK |
| full | REFUSAL | mvhd-v1.mp4 | 9 REFUSAL finding(s) in this run | OK |
| full | FINISH | A011 | 0 row(s) carry that token | OK |
| full | DISCARD | A012 | 0 row(s) carry that token | OK |
| full | ORPHAN | A014 | 0 row(s) carry that token | OK |
| full | MISSING-MEDIA | A015 | 0 row(s) carry that token | OK |

27 expectation(s), 0 MISSING.  A MISSING line is a contradiction the
instrument did not catch, or a fixture expectation this run disagrees with --
either way it is a finding, and it is printed, never hidden.
