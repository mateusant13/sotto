# receipt-30 — the rolling clip store: layout, retention, disk-full, recovery

**Lane:** 22 · **Date:** 2026-10-07 · **Gate:** `_main\_lane22-storage-gate.ps1` → `LANE22-GATE PASS` (rc=0)

Files (all new, all owned by this lane):

| path | what |
|---|---|
| `src\storage\__init__.py` | package contract + the measured capture rate that reframes the whole design |
| `src\storage\layout.py` | the on-disk layout, the clip-id algebra, the version read-rules, the reconciliation vocabulary |
| `src\storage\retention.py` | the policy, eviction, the disk-full decision, reconciliation, and arms A/B/C/E |
| `_main\_lane22-storage-gate.ps1` | 11 named arms, one of them a control with 4 reverted guarantees |
| `receipts\receipt-30-clip-storage-retention.md` | this file |

**No other lane's file was touched.** The hookups other lanes need are in §7.

---

## 1. THE MEASUREMENT THAT DECIDED THE DESIGN

Before choosing a default budget I measured what one clip costs on this box:

```
file      H:\sotto\_moved\aireplay\_main\_lane17-run\clip-speech.mp4
size      98 099 914 B
duration  16.733333 s        (ffprobe -show_entries format=duration,bit_rate,size, rc=0)
bit_rate  46 900 358 bit/s
=>        5 862 545 B/s  =  19.65 GiB PER HOUR
```

**A byte budget on this machine is not a duration, and reading it as one is the bug.**
4 GiB — a number that reads as "four hours" in every settings screen ever written — is
**12.2 minutes** of capture at this rate. So:

- **`max_age_s` is the primary retention key.** It states what the owner keeps, in the unit
  they think in.
- **`max_bytes` is the backstop.** It bounds the failure, not the product.
- Every policy line logs the translation (`capture_minutes_at_measured_rate=12.210`), because
  a budget printed without it is a number nobody can act on.

This is not a generic worry: the brief's premise ("the app got slow for no reason") is what
19.65 GiB/h unbounded looks like on a box whose volume had **42.72 GiB free** when measured
(`Win32_LogicalDisk` H:, 517.00 GiB total; the gate's own ARM B measured `free_bytes=40151216128`
= 37.40 GiB during the run — other lanes are writing to this volume, so treat the figure as a
moment, not a constant).

## 2. Layout — deterministic, re-derivable, versioned

```
<root>/
  layout.json                    store version marker (written once, refuses a foreign one)
  clips/2026/10/07/20261007T130648Z-0001/
      .partial                   PRESENT iff NOT committed -- the only crash marker
      clip.mp4                   the muxed artefact
      transcript.json            sidecar
      thumb.jpg                  sidecar
      key.json                   THE COMMIT MARKER, the index key, written LAST
```

Four properties, each with a check that can say no:

1. **A path is a pure function of a `clip_id`**, and a `clip_id` is a pure function of
   (UTC instant, seq). `clip_dir()` and `parse_clip_dir()` are computed by *different code*,
   so their disagreement is detectable rather than invisible (ARM 0 `A2`).
2. **UTC always.** `2026-10-07T02:00:00Z` is filed under `2026/10/07`; this host's local date
   for that instant is `2026-10-06` (offset **−180 min**, measured and printed). A
   local-date layout would have filed it two days wrong for four hours a day. ARM 0 `A3`
   prints the host offset and marks itself **VACUOUS** if that offset is ever 0.
3. **The commit is one atomic step**: `key.json.tmp` → `os.replace` → `key.json`, *then* the
   marker is unlinked. Before it, nothing claims the clip exists; after it, it does.
4. **Versioned reads.** `READ_RULES = {1: _read_v1}`. A key stamped `layout_version=99`
   is **REFUSED**, not read as v1 (ARM 0 `C1`). This is the whole answer to "can the code
   that reads recover the layout after a version bump": the rule table is explicit, and its
   absence is a refusal.

**The index is reconstructible from disk alone.** `walk_keys(root)` returns the whole index-key
population with no db and no in-memory state, because every key is self-describing
(`content_key`, `size_bytes`, `mtime_ns`, `duration_ms`, `layout_version`). Lose `store.db`
and the library is still describable. ARM 0 `B3`/`B4`: 6/6 keys rebuilt, 6/6 naming media
that exists.

## 3. Retention — three rules, unioned, oldest first

| rule | default | meaning |
|---|---|---|
| `max_age_s` | `86400` (24 h) | the window the owner is promised |
| `max_clips` | `500` | roughly a day at one clip per ~3 min of play |
| `max_bytes` | `4 GiB` | the backstop — 12.2 min at the measured rate |
| `reserve_bytes` | `1 GiB` | free space the store refuses to consume |

Precedence is `explicit` > `env` > `default`, **field by field**, and every field records
where it came from (`budget_source=env:SOTTO_CLIP_MAX_BYTES` is in every log line). An
unusable value in **any** tier is a `PolicyError` — `0`, `-5`, `abc` and `""` are all refused,
never clamped (ARM E `E4`). An env var that is *present but empty* is refused too:
`SOTTO_CLIP_MAX_BYTES=` silently buying the 4 GiB default is exactly the silent substitution
this lane exists to prevent.

The three rules are computed **independently and unioned**, so a 25-hour-old clip is evicted
even when the disk has room — it is outside the promised window regardless of free space.
Victim order is `(started_at_s, clip_id)`: a total order, so the plan is reproducible.

**The budget is compared against the whole store footprint**, not the sum of clip directories.
This is a bug my own gate caught: comparing the payload sum to a budget and then *reporting*
the tree size left the store "120 B over budget" while every printed number was individually
true (`A3` now states the 226 B of non-clip overhead explicitly).

## 4. DISK FULL — the decision, and what it costs

**Decision: keep the library, refuse the next clip, and say so.**

The order in `admit_write()` is not negotiable: measure → evict down to the **configured**
budget (never below it) → measure **free space on the volume** (not `max_bytes - used`, which
knows nothing about what else on the machine is consuming the disk) → refuse if
`free < incoming + reserve`.

The two rejected alternatives, and why:

- **(a) keep writing and fill the disk.** The failure surfaces on the owner's box as "the app
  got slow for no reason" days later, and the clip that filled the disk is never the one that
  was wanted.
- **(b) evict everything until the write fits.** A recorder whose library disappears because
  something *else* ate the disk is worse than one that misses a clip, and it is
  indistinguishable from data loss the moment the pressure comes from a neighbour.

The configured budget is the floor of what this store promises to keep. `DEFAULT_ON_DISK_FULL`
is the one named place that would change it.

**Loud, rate-limited, and auditable.** One `CLIP_STORE_ALARM reason=disk-full` per
`alarm_interval_s` (60 s), carrying `free_bytes`, `need_bytes`, `reserve_bytes`,
`budget_bytes`, `budget_source`, what was evicted, and what happens next. Rate limiting that
cannot be audited is indistinguishable from having gone quiet, so the **suppressed count is
reported** (ARM B `B6`: 2nd refusal 1 s later → `emitted=1, suppressed=1`; `B7`: after the
interval it speaks again, `emitted=2`). The gate asserts loudness **on the child's real
stdout**, not on an internal counter — an alarm nobody can see in the process output is not a
loud alarm.

`admitted=False` is a normal product state, not an exception. Callers that raise on it will
crash the recorder instead of the library.

## 5. Reconciliation — finished or discarded, never "corrupt but claimed"

| on-disk state | verdict | action | why |
|---|---|---|---|
| key + media, no marker | `committed` | keep | |
| marker **+** key | `partial-committed` | **finish** (drop the marker) | crash between commit and marker removal; the clip was never lost |
| marker, no key | `partial-uncommitted` | **discard** | the mp4 has no finished `moov`; it will not play |
| no marker, no key | `orphan-key` | discard | a directory, not a clip |
| key, no media | `missing-media` | discard | the claim goes with the file |
| no marker, key unparseable | `partial-uncommitted`→`ACTION_KEEP` | **keep, report loudly** | the media may be a good clip; deleting it destroys bytes on a guess. It stays **out** of the index, so the hole is visible |

That last row exists because my control caught the alternative: I had first written the
partial branch as `if guard: DISCARD else: DISCARD` — a guard between two branches returning
the same value, i.e. decoration. Making the two branches genuinely different decisions made
the guard load-bearing, and it is now covered by `C9`.

**The invariant:** *nothing the index claims exists is missing or unusable.* `walk_keys()`
sees only committed directories, so a `.partial` directory is invisible to the index by
construction; reconciliation is what stops it staying on disk forever.

## 6. THE GATE — `_lane22-storage-gate.ps1`

11 named arms, each a separate OS process (`CreateNoWindow`, house rule 1; exit code read
from the **process object's** `.ExitCode`, never a pipe, house rule 2; native `H:\` only).

```
ARM 0   PASS  10/10   6 clips, 29 663 B, host UTC offset −180 min
ARM A   PASS   8/8    freed 542 141 B over 13/24 clips; 1 001 109 B -> 458 968 B;
                      budget 500 554 B; the two measures AGREE EXACTLY
ARM B   PASS   8/8    12/12 clips kept; free 40 151 216 128 B MEASURED;
                      3 CLIP_STORE_ALARM lines on the child's stdout
ARM C   PASS  10/10   7 staged -> kept 4, finished 1, discarded 3; 8 349 B reclaimed;
                      the index would see 3 clips, every one with media present
ARM E   PASS   6/6    policy line, precedence, 4 refusal arms
ARM D0  PASS   8/8    the UN-MUTATED COPY runs ARM A green
ARM D/RETENTION-BYTES    PASS   A went RED: A1, A3, A4
ARM D/WRITE-ADMISSION    PASS   B went RED: B1, B2, B5, B6, B7
ARM D/LOUD-ALARM         PASS   B went RED: B2, B5, B6, B7
ARM D/RECONCILE-PARTIAL  PASS   C went RED: C2, C6
=> control: 4/4 reverted guarantees went RED as required, D0 GREEN
LANE22-GATE PASS (rc=0)
```

### POPULATION and WINDOW for the headline (ARM A)

- **POPULATION:** 24 real committed clips written to a real tree on `H:`,
  **1 001 109 B** measured by a full recursive walk (not by summing what the writer intended);
  0 filesystem errors.
- **WINDOW:** oldest `20261006T162104Z-0000` → newest `20261007T152104Z-0023`, span
  **82 800 s** (24 clips over a 86 400 s window); age window in force `1e9 s`, count window
  `1e9` (both off, so the byte rule acted alone); budget in force 500 554 B from `explicit`.
- **BYTES FREED: 542 141 B**, by two independent measures that agree to the byte — the sum of
  the files whose own `unlink` succeeded, and the delta of a full re-walk of the store. A
  disagreement would mean something else wrote during the eviction; `A2` asserts they match.
- **WHO WENT:** 13 of 24, the oldest, contiguous from `…162104Z-0000` to `…042104Z-0012`.
  11 survivors, the newest. A second pass over the same tree selects **0** victims (`A5`).

### Why ARM D0 exists

Without an un-mutated copy, a mutant that goes red **because the copy is in another directory**
(or because the mutation broke an import) is indistinguishable from one that went red for the
intended reason. This is the "a gate that supplies the thing it then finds cannot say no"
failure: the mutation is applied by the **harness**, to a **package on disk**, and the mutated
module has no idea it was changed. Each mutant arm also asserts `facts.module_file` is inside
its own copy, so a run that accidentally imported the original cannot report a passing RED.

### Defects my own gate found while this lane was being written

Six, all fixed, all listed because a gate that has never caught anything is not evidence:

1. `parse_clip_dir` walked one level too few → refused every real clip dir.
2. A hand-copied epoch constant (`1792730408`) was not 2026-10-07T13:06:48Z. The instants are
   now built from their date components, so the assertion cannot drift from the code.
3. `parse_clip_id("20261307T…")` escaped as `ValueError`, not the documented `LayoutError` —
   two different callers, and a crash is not a refusal.
4. Budget measured against the clip-payload sum, reported against the tree: 120 B "over budget"
   while every printed number was true (§3).
5. `SOTTO_CLIP_MAX_BYTES=` (present, empty) silently fell back to the 4 GiB default (§3).
6. The reconcile guard was decorative: both branches returned `ACTION_DISCARD`, and ARM D's
   `RECONCILE-PARTIAL` mutant stayed GREEN — the control caught a guarantee that was not there.

Two harness bugs too: the negative copy was laid out flat (`ModuleNotFoundError: No module
named 'storage'`, correctly reported RED rather than passed), and the mutation path missed the
`storage\` prefix.

## 7. HOOKUPS FOR OTHER LANES — I did not edit these files

- **`src\capture\`** (the mux/`mp4_writer` owner): do not write clips directly. Call
  `storage.layout.ClipWriter(root, clip_id)` → `write_media(bytes)` →
  `write_transcript(obj)` / `write_thumb(bytes)` → `commit(duration_ms=…, mode=…)`.
  **Always** `commit()` or `abort()`; an open writer is the crash this layout survives. Use
  `make_clip_id(started_at_s, seq)` for the id — never a filename you invented. `commit()`
  returns the key dict, which already carries `content_key` (whole-file SHA-256) for the index.
- **`src\index\`** (the `video`/`segment` tables owner): the row's `path` is
  `clip_dir(root, clip_id)` and its `content_key` is `key["content_key"]` — identity is the
  content key, never the path, exactly as `schema.py:56` already says. After a crash, or after
  losing `store.db`, rebuild the video population with `walk_keys(root)`; it needs no db and
  skips `.partial` directories by construction. `reconcile(root)` should run at startup, before
  the first index scan, so the index never sees a half-finished clip.
- **Startup order (nobody owns this yet):** `ensure_root(root)` → `reconcile(root)` →
  `policy_from_env()` → log `policy.line(population, window)` → periodic
  `admit_write(root, policy, incoming_bytes, now, alarm)`. `admit_write` is also the natural
  place to drive the rolling evictions that keep the store inside its budget.

## 8. LIMITS — what this receipt does NOT claim

- **NOT MEASURED:** behaviour under real concurrent writers. `remove_clip_dir` and the marker
  protocol assume one writer per store, as the capture pipeline implies; nothing here tests
  two processes racing the same clip id.
- **NOT MEASURED:** eviction cost at scale. The headline ran 24 clips / ~1 MB. `tree_bytes`
  and `iter_clips` walk the whole store per pass, so at the default 500 clips every call is a
  full walk; for a hot loop this wants an incremental counter, and I did not build one.
- **NOT MEASURED:** the real muxer. The gate's media payloads are synthetic (`ftypmp42` + N
  bytes); the *decision* about an unfinished `moov` is sound, but no real partially-written
  NVENC file was fed to `reconcile()`.
- The 19.65 GiB/h rate is **this box's 1080p60 clip**. A different encoder or resolution moves
  it, and `capture_minutes_at_measured_rate` is meaningless once it does. The constant carries
  its provenance in `layout.py:MEASURED_BYTES_PER_SECOND` for exactly that reason.
- `DEFAULT_MAX_CLIPS = 500` is a product choice with no measurement behind it. It is the one
  default here I would expect the owner to overrule.

## 9. SELF-AUDIT

- **High confidence:** the layout algebra, the commit protocol, the eviction order, the
  disk-full refusal path, and the four mutants — all exercised against real files on a real
  volume, with every count carrying a POPULATION and a WINDOW, and the control arm running
  both colours.
- **Lower confidence:** the *default policy values*. The rate behind them is measured; the
  24 h / 500 clips / 4 GiB choices are judgement, and the byte budget deliberately trades
  retention for the owner's disk. What would move it: an owner's decision on how much library
  he expects to keep.
- **Gate doubts:** the synthetic media payloads (a real crash leaves a genuinely truncated
  mp4, and I have not fed one to `reconcile()`), and the single-writer assumption in §8.
- **Protocols missing:** no fuzzing of `parse_clip_id` beyond four hand-picked bad ids; no
  test of a store root that is a file, a symlink, or on a volume that reports 0 free bytes.
- **Extra verification run beyond the gate:** the gate was run **twice**, green both times,
  confirming re-runnability; and `PYTHONDONTWRITEBYTECODE=1` was verified to leave no
  `__pycache__` under `src\storage`.
- **WINDOW-CENSUS (house rule 1, measured not asserted):** the gate was run a third time
  while sampling `Get-Process` for `MainWindowHandle != 0` every **100 ms** — 35 samples over
  the run. **23 samples matched a visible window, and all of them were 2 distinct FOREIGN
  processes**: `pythonw` pids 38512 and 41188, both titled `Aireplay HUD` (other lanes'
  artifacts). **Zero** samples matched `python.exe`, `py`, `cmd` or `conhost` — this gate
  launches `py -3`, whose `python.exe` children are created with `CreateNoWindow`, so running
  this gate put no console on the owner's screen. Reported in full because the census is not
  clean, and the clean part is not the whole part.
- **Another subagent reviewed this:** **NO.** I have no dispatch tool in this session
  (see the handoff), so this receipt is unreviewed and the verifier dispatch is the open item.