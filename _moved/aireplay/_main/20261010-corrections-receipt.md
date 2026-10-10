# 20261010-CORRECTIONS - the landing procedure, the index incident, and every claim this commit corrects

Landed on top of `bf845e30` (branch `feat/build-verify-1`, product root `H:/sotto`), 2026-10-10.
Three paths, all explicit, no `git add -A`, nothing pushed.

| path | kind | holds |
|---|---|---|
| `_moved/aireplay/_main/DEBT-LEDGER.md` | M | append-only corrections (a), (b), (c), (k) |
| `_moved/aireplay/_main/AUDIT-FINDINGS.md` | M | append-only corrections (d), (e), (f), (g), (h), (i), (j) |
| `_moved/aireplay/_main/20261010-corrections-receipt.md` | A | this file |

The two `.md` corrections are APPENDS. No paragraph above is rewritten: this file's value is that
the order in which things were learned stays legible, exactly as the wave-2 count blocks keep all
five of their earlier counts (DEBT-LEDGER 144-181).

## 0. Why this commit exists: one landing that landed the wrong bytes

The LANE A landing (`53c7e122a122a63fd0415feeef8b2758c21ad8f2`, 5 paths, 605 insertions, 1 deletion)
was committed ONCE WRONGLY and then rewound.

PA: `git hash-object` over the raw worktree bytes of the 5 paths in `H:/sotto-wt/engproc`.
POP: 5 paths. WINDOW: 2026-10-10, before the repair.

The first attempt hashed the worktree FILES. Three of the five are CRLF text
(`_engine-ui-census-armb.txt`, `_engine-ui-census.ps1`, `_engine-ui-census.txt`) and
`core.autocrlf=true` on this box (measured: `git config core.autocrlf` -> `true`), so the
parent worktree's bytes are NOT the lane's committed bytes - git already normalised the CRs when
the lane committed. The cross-check that compared "lane sha == local sha" printed `3 MISMATCH`
and the program KEPT GOING, committing `f38ded6dd50ea958c13423da947eef0e2707471e`.

Two rules, now hard, both bought by one mistake:

1. **A staleness guard must ABORT the program, not count.** A mismatch that only gets printed is a
   log line, not a guard.
2. **The authoritative sha for a landing is `git ls-tree <lanetip> -- <path>`, never a hash of a
   worktree file.** For a CRLF file under autocrlf these are two different objects holding the
   same text, and the wrong one is silently accepted by every git command downstream.

REPAIR, in order: `git update-ref HEAD 3e7357f1 <f38ded6d>` (CAS rewind, rc 0 - if HEAD had moved
it would have failed loudly), `git reset -q HEAD -- <the 5 paths>` (index back to HEAD), then
re-staging from the LANE'S OWN blob shas out of `git ls-tree 53c7e122`, each one verified present
in the parent's shared object store with `cat-file --batch-check` before it was used. Final commit
`bf845e30`, tree `851fbf2df1b147ffa2af2326772d98aa49e616b4`, `diff-tree -r --name-status
3e7357f..bf845e30` = exactly 5 rows.

PA: `git diff --name-status 3e7357f bf845e30` and `git ls-tree -r bf845e30 -- <5 paths>` against
`git ls-tree -r 53c7e122 -- <5 paths>`. POP: the 5 landed paths. RESULT: 5/5 byte-identical.
Parent-state invariant for every future landing, measured again in this commit's own run:
`git diff --cached --name-only` is EMPTY after the pathspec reset, i.e. index == HEAD.

## (a) L5 and L6 cite shas that DO NOT EXIST

PA: `git rev-parse --verify <sha>^{commit}` in `H:/sotto`. POP: the reviewer cells of the wave-2
table (DEBT-LEDGER 128-142). WINDOW: 2026-10-10, HEAD `bf845e30`.

- `47ed989e` -> rc 128, `fatal: Needed a single revision`. L5's cell (line 137) says
  "`47ed989e` (lane working)". No such commit exists anywhere in the object store.
- `6b3ddb1c` -> rc 128, same fatal. L6's cell (line 138) says "`6b3ddb1c` (lane working)".
  Also nonexistent.
- `git grep 47ed989e|6b3ddb1c` over the whole repo returns exactly TWO matches: those two rows.
  The false shas have no other citation, which is what makes this a bounded repair.

What is TRUE instead, measured:

- **L5 engine-process** - the lane's real content is `faffdd609f9ce63439ced953af59f5711428022c`
  ("LANE A - THE ENGINE PROCESS: dual-colour gate GREEN, reconcile fix, sidecar hardening,
  battery", parent `0e1b7f5`, base of the wave) plus its receipt
  `53c7e122a122a63fd0415feeef8b2758c21ad8f2`. Both are LANDED at `bf845e30`.
- **L6 specs 05-07** - the lane's real tip is `40f2cba7301fdef7f4ddd6c17bc728c808e3e253`
  ("specs: write the 07-engine-process spec for the shipped Python Engine", 2026-10-10), which
  touches exactly one path, `_moved/aireplay/specs/07-engine-process.md`, +496 -16. It is landed
  at `1055e7ee`.

Both still have NO reviewer row, so rule 4 is NOT satisfied for either.

## (b) D-GATE-AUDIT: the "commit does not exist" half is now FALSE

The row opened at DEBT-LEDGER 187 says the three `_gate-audit` files are untracked/gitignored and
that "the commit that was said to hold them does not exist in either repo". Appended, not
rewritten: they are LANDED in this repo at `2f9071c`. The sentence above is the measurement it
was at the time it was written.

## (c) Rule 4 over wave 2 - the sixth count

PA: the wave-2 table plus `git log` of the landings. POP: 8 wave-2 rows + ODS1 + LANE A.
WINDOW: 2026-10-10, HEAD `bf845e30`.

VALUES: 5 verdicts READ (L2 PASS, L4 PASS-WITH-DEFECTS, L15 NO, L17 PASS-WITH-DEFECTS, L18
PASS-WITH-DEFECTS), 0 reviewers running, and with NO reviewer row at all: **L5, L6, L7, ODS1 and
LANE A**. Rule 4 is NOT satisfied for those five, however good the receipt is (rule 4, ledger 13
and 39). This supersedes the fifth count (176-181) for L5/L6/L7 only; L2/L4/L15/L17/L18 keep
their verdicts.

## (d)+(e)+(f) F16.6-F16.8: the numbers, the closure, and what must NOT be edited

**(d) The p95 numbers have no surviving log.** PA: `git grep` for the four values
(`p50=1,249ms`, `p95=28,542ms`, `5 of 10` refused, `aus_waited_for_idr=1005`) across the tree,
plus the F16.9 measurement of the report of record itself (13 066 B / 200 lines, mtime
2026-10-09T23:20:34.686Z, whose aggregate header `cap-battery-20261009-175104.txt:3-7` stamps no
script sha). RESULT: those four numbers survive ONLY as the sentences at AUDIT-FINDINGS 624-633;
no log behind them is in the tree. They may be quoted as "what a run reported once", never as
"the state of the instrument".

**(e) F16.8's instrument defect is CLOSED, not dropped.** The defect (lines 635-641: the first
smoke run printed `VERDICT RED` over exit code 2, its own contract's "could not measure a single
cut") was repaired in `c72268cc`, which landed
`_main/_p95-instrument/press-to-clip-probe.ps1` and its `.red.ps1`. PA: the landed probe's
bytes, lines 584-589, which now emit `VERDICT FAIL`, a `REASON: no cut produced a measurable
delta` line, a HALF-A-remains-UNKNOWN line and `exit 2`. So the exit code is the verdict and the
word is now the same verdict. No owner question opens on this and none did then.

**(f) Nothing above is rewritten.** Lines 620-621, 635-641 and 947-948 keep their text; they are
the record of what was believed and printed. The reviewer's own cadence-aware re-measurement
(F19.5, lines 917-923: `aus_waited_for_idr=1064`, 6 clips, 5 refusals, 5 ftyp-only stubs, at
2 600 ms cadence) is the reason F16.6/F16.7 cannot be quoted as a product number: the cadence is
not named there, and the totals are cadence-set (line 922).

## (g) The audio peak/rms anomaly - 3 of 4 non-silent arms, cause UNKNOWN

PA: the L7 gate logs in `I:/cc-tmp/l7-gate/`. POP: every arm that reported a `level` pair.
WINDOW: the L7 four-colour arm gate, 2026-10-10.

| log | line | peak | rms |
|---|---|---|---|
| `capture2.out.log` (GREEN1) | 65 | 0.837463 | 0.000000 |
| `g3-cap.log` (GREEN3) | 66 | 0.871136 | 0.000000 |
| `r6-cap.log` (RED6b) | 62 | 0.000000 | 0.000000 |
| `r7-cap.log` (RED7) | 58 | 0.428103 | 0.000000 |

Three non-zero peaks with a zero RMS, and one arm with both zero. The pair is computed by the
same `audio level` report in `audio_tap.cpp`; a real signal cannot have a peak without an RMS.
Mechanism UNKNOWN and not guessed here; it is carried as an open instrument defect.

## (h) F13.2 - the IL mechanism is CONFIRMED, and the older "refuted" sentence was an instrument artifact

F13.2 (AUDIT-FINDINGS 427-446) says the two WGC instruments disagree about the same
`CreateForWindow` call and that the cause is "build-time (manifest / integrity level) or run-time
(session, input desktop, concurrent capture holder)". That alternative is now RESOLVED.

PA: one merged binary, one argv, one box, two run locations; `icacls` on each location (the only
instrument that prints the SACL - `Get-Acl`/`File::GetAccessControl` return the DACL only and so
report a false NO-LABEL). POP: the same executable run from `H:/sotto` and from
`H:/sotto-wt/audioclip/_merged-gate/`. WINDOW: 2026-10-10.

- under `H:/sotto` (LOW, `S-1-16-4096`): `CreateForWindow failed 0x80070005`, EXIT=2, 0 frames,
  wall 1 682 ms.
- under `H:/sotto-wt/audioclip/_merged-gate/` (no label => MEDIUM): EXIT=0, full capture.

CONSEQUENCE FOR EVERY FUTURE CAPTURE GATE: the binary must run from a MEDIUM-IL path, never from
under `H:/sotto`.

The earlier sentence elsewhere in this file type that the low-IL premise "was refuted" was an
artifact of the broken DACL-only instrument: it could not see the mandatory label at all, so it
reported NO-LABEL for a LOW-IL path. Any IL probe must be validated against a known-LOW control.

Carried with it, unchanged: the stale comment at `src/capture/main.cpp:183-184` ("WGC refuses every
capture item on this host") is FALSE in the merged binary at HEAD and is left for the lane that
owns that file.

## (i) The F13.2 census line that names a dead lane tip

AUDIT-FINDINGS 229 records `engproc  feat/engine-process  @0e1b7f5 ahead=1  dirty=0   (10 files
+3289, engine/)`. `0e1b7f5b2806a48a92dcfbe3841cd01f812652c6` exists (LANE A's first commit,
parent `399bc851`, the wave base) but it is no longer the lane's tip. PA: `git diff --numstat
0e1b7f5 faffdd609`. POP: the whole lane delta. RESULT: `src/engine/engine.py` +340 -12,
`src/engine/test_engine.py` +311 -30, `src/engine/ui_child.py` +184 -77, and three
`_engine-audit-battery-v2*` instruments +354. So the spec-07 text written against `0e1b7f5`
describes an engine that has since grown by 340 added lines of shipped behaviour.

## (j) ODS1 / Arm B - a contradiction, carried as UNKNOWN with its population

Arm A and Arm B measured the same population of clips and disagreed about the same objects.

PA: `_moved/aireplay/_main/_lease-audit/armA-report.md` and `armB-report.md`, both landed in
ODS1 (tree `7395ebae7f0e5f84ef3ca4c008a131f492f55b4d`). POP: `H:/sotto/_moved/aireplay/_main/_lane22-run`
(99 `clip.mp4`, 98 `key.json`, 0 `.db`). WINDOW: 2026-10-10, 10 runs by design (rc=1 in all of
them, which is the instrument's contract).

The contradiction, stated without resolving it: Arm B counts 95/95 keys self-contradictory
(`usable_keys 95, violators 95, tolerance_ms 1`) and 99/99 clips with no `ftyp` or `moov`
(`.terminal R-NO-MOOV 98 / R-NO-FTYP 1`), while Arm A's own instrument reports 9% foreign clips
and 32 red rows over 23 db rows. C01 overlaps 621 clips in one store; the duration histogram is
`{1000:7, 1001:1, 1002:1, 1003:1, 1004:1, 1005:1, 30000:83}`; per-store C01 spans
200.045 s to 82 800.275 s (`armB-report.md:53-64`); `armB-report.md:150` already states
`sobreposicoes de 3600 s a 82800 s em 9 de 10 stores: UNKNOWN`.

Verdicts: `committed 95`, `partial-uncommitted 4`, and the 4 clips without a usable key ARE
exactly the 4 partial-uncommitted ones - cause UNKNOWN. Controls outside the population refused
0. It is UNKNOWN whether these are two correct instruments reading two different populations, or
one wrong predicate; no resolution is asserted here.

## (k) THE INDEX INCIDENT of 2026-10-10 05:50:23Z - recorded, with its recovery measurement

One of the day's landings (ODS1, tree `7395ebae`, 25 A-paths, all verified) used a scratch index
built with `GIT_INDEX_FILE` + `read-tree HEAD`. After it, the other owner's five staged rows read
`MM` -> ` M`: the LANDING was correct, the damage was confined to the index. Mechanism
UNVERIFIED - prime suspect that `read-tree` ran against the REAL index because the env var was
never genuinely in the spawned child's environment.

Recovery measurement, exhaustive. PA: loose objects under `.git/objects` in the staging windows
(`2026-10-09T22:10:50Z-22:11:30Z` and `2026-10-10T03:09:20-50Z`). POP: 68 loose objects. RESULT:

| worktree path (INTACT, never edited by the lane) | mtime | normalised content | status |
|---|---|---|---|
| `app/panel/panel.css` 87 673 B | 2026-10-09T22:49:17.128Z | `e5df2ef5d6be…` 85 161 B | **ABSENT from the object DB** |
| `app/panel/panel.html` 55 727 B | 22:11:18.417Z | `13f84250c48c61…` 54 716 B | unreachable loose object, recoverable |
| `app/panel/panel.js` 129 266 B | 22:11:18.418Z | `2a130324e995fa…` 126 551 B | unreachable loose object, recoverable |
| `app/panel/theme-switcher.js` 30 537 B | 22:11:18.419Z | `296e23d8ee84…` 29 782 B | REACHABLE history blob at the same path |
| `app/webview/sotto_webview.py` 326 796 B | 22:11:18.422Z | `926d33a7b2ae9…` 320 214 B | unreachable loose object, recoverable |

`panel.css` is absent for a reason that is measured, not assumed: it was re-edited at 22:49, i.e.
38 minutes AFTER the 22:11 staging batch, so no object ever held that content. The size gaps
(1 011 / 2 716 / 6 582 / 756 B) equal the line counts exactly, which is pure CRLF<->LF: the
objects ARE the same content, not an older revision. Nothing foreign entered the object DB from
any of the day's landings (same census, checked file by file).

DECISION RECORDED: the recovered blobs are NOT re-staged by this commit. Those five paths are the
OTHER OWNER's work - the worktree files are intact, their mtimes unchanged - and re-staging a blob
I did not see him stage would be this lane writing his index. The corruption is disclosed here,
the recovery path is named (3 unreachable blobs + 1 reachable history blob), and the index is
left to its owner.

## Still open after this commit (unchanged, none of it closed by writing about it)

1. Rule 4 for L5, L6, L7, ODS1 and LANE A: no reviewer row.
2. The p95 control RED arm was designed but never run; receipt-30 close-out item 2 (one smoke pass
   of BOTH arms) is STILL OPEN - that is what closes D1.
3. Q6: the ring cap is priced from dedicated VRAM while the arena is SYSTEM RAM
   (`d3d11_ctx.cpp:70`); the fix exists on `feat/ring-cap-ram-c` (`caf7a9a`) and is NOT merged.
4. The C++ capture child end-to-end: blocked by the read-only SPS/PPS defect in
   `src/capture/main.cpp SourceStream::load` (L17 fixed the FEED path; the product path is still open).
5. Nothing is pushed. `origin/feat/build-verify-1` is at `9ef1f03`; landing is not pushing.
