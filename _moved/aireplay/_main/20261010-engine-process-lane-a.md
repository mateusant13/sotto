# LANE A - THE ENGINE PROCESS - dual-colour receipt

Everything below is MEASURED unless it is marked UNKNOWN. Every claim names the arm it came from.
Where a number is a label rather than a measurement, that is said plainly instead of being glossed.

## 0. Identification

| field | value |
|---|---|
| lane | A - THE ENGINE PROCESS (roadmap P0) |
| subject | H:\sotto-wt\engproc\_moved/aireplay/src/engine (worktree H:/sotto-wt/engproc, branch feat/engine-process) |
| plan of record | H:/sotto/_moved/aireplay/runs/P4-aireplay-engine-process.md - product root only, the worktree has no runs/ dir |
| lane commit, this run | faffdd6 |
| lane commit, initial implementation | 0e1b7f5b2806a48a92dcfbe3841cd01f812652c6 |
| receipt written against | faffdd6 - the files this proof ran against are engine.py 60743 B sha256 1dcb9aeca04ef86b, test_engine.py 52459 B sha256 3edff3c8d71153b5, ui_child.py 11840 B sha256 208ca9bcec165603 |

## 1. BOTH COLOURS, ONE COMMAND

```
$env:TMPDIR="I:/cc-tmp"; Set-Location H:/sotto-wt/engproc/_moved/aireplay/src/engine;
& "C:/Program Files/Python311/python.exe" ..\..\_main\_engine-audit-battery-v2.py
```

The battery (_main/_engine-audit-battery-v2.py) is the aggregator; the dual-colour instrument is
src/engine/test_engine.py --mutants --keep. The battery launches every gate process with
creationflags=CREATE_NO_WINDOW (0x08000000), so no console lands on the owner screen, and its
census names the full artifact path.

Verbatim, from the committed logs: _main/_engine-audit-battery-v2-run.txt is the battery stdout,
_main/_engine-audit-battery-v2.txt is the gate log it tees in (I:/cc-tmp/battery-engine-v2.txt).

```
BATTERY      : _engine-audit-battery-v2  subject=H:\sotto-wt\engproc\_moved\aireplay\src\engine
GATE         : H:\sotto-wt\engproc\_moved\aireplay\src\engine\test_engine.py
BATTERY CMD  : python src/engine/test_engine.py --keep
BATTERY LOG  : I:/cc-tmp\battery-engine-v2.txt
BATTERY START: 2026-10-10T01:42:59

GATE ROOT      : I:\cc-tmp\engine-gate-19796
ARMS           : A,B,C1,C2,D,E,F,G   skipped=-
RED CONTROLS   : stdout-leak,no-replay,capture-waits,preflight-ok,no-lock,commit-nokey,stale-lie,no-finalise

  PASS   ARM-A    green GREEN   5.3s  rc=0 cuts=4/4 ring=6 cuts_refused=0 rec=1 spine=5cmt,5key-ok,5sha-ok stop=cut-count-reached stdout=0B
  PASS   ARM-B    green GREEN   33.6s  rc=0/0 ui1=5ms ui2=2ms replayed=14(30..44) exact=True cursor=30 ids=71 gaps=[] dupes=0 engring=100/120 live=41 cuts_while_unattended=219 clips=221 files=221 rows=221 orphan=-
  PASS   ARM-C/stall green GREEN   34.2s  rc=0 asr={'submitted': 12, 'done': 0, 'dead': 4, 'failed': 0, 'dropped': 1} clips=12/12 maxcut=1982ms intervals=[139, 942, 986, 995, 1005, 1012, 1030, 1071, 1125, 1982] keys_ok=12/12 ui=0
  PASS   ARM-C/dead green GREEN   13.8s  rc=0 asr={'submitted': 12, 'done': 0, 'dead': 0, 'failed': 12, 'dropped': 0} clips=12/12 maxcut=1398ms intervals=[714, 822, 903, 1022, 1032, 1065, 1075, 1238, 1287, 1398] keys_ok=12/12 ui=0
  PASS   ARM-D    green GREEN   0.8s  rc=3 stdout=0B verdict="[engine 01:44:26] pre-flight rc=3 decision='DECISION: REFUSED ? NO ENCODER INITIALISED - the rep" locks=False spine=False
  PASS   ARM-E    green GREEN   15.3s  rc1=0 rc2=4 lock-file-seen=True refused_words=True lock_after=False
  PASS   ARM-F    green GREEN   6.2s  killed pid=34268 child=42708 committed=3 done=3 cutting=0 live_before_kill=3 keys_ok=3/3 files=3 integrity=ok committed_before_kill=True
  PASS   ARM-G    green GREEN   46.3s  cursor=1 evicted_before=149 maxring=100/100 orc=3 to=102 n=100 truncated=True ui=8ms files=249 rows=249 orphan=-
  REDok  ARM-A    red   rc=0 cuts=4/4 ring=6 cuts_refused=0 rec=1 spine=5cmt,5key-ok,5sha-ok stop=cut-count-reached stdout=2336B FAIL:stdout empty
  REDok  ARM-B    red   rc=0/0 ui1=5ms ui2=2ms replayed=0(24..33) exact=False cursor=24 ids=50 gaps=[{'prev': 24, 'next': 34}] dupes=0 engring=100/64 live=27 cuts_while_unattended=162 clips=163 files=163 rows=163 orphan=- FAIL:replay window is cursor-consistent,replay is the exact continuation,live ids continue exactly,ids gapless (no holes)
  REDok  ARM-C/stall red   clips=4/4 maxcut=3753ms intervals=[3734, 3753] keys_ok=4/4 ui=0 FAIL:cuts >= 8,capture never waited (max interval 3753 ms < 2500)
  REDok  ARM-D    red   rc=0 FAIL:rc==3,status exit_code 3
  REDok  ARM-E    red   rc1=0 rc2=0 lock-file-seen=False refused_words=False lock_after=False FAIL:second engine refused (rc 4),loud refusal words
  REDok  ARM-F    red   killed pid=46960 child=33468 committed=1 done=1 cutting=1 live_before_kill=1 keys_ok=0/1 files=1 integrity=ok committed_before_kill=True FAIL:engine published >=3 clips before the kill,spine still holds them all after the kill,>=3 clips committed by the kill,every key == file sha256
  REDok  ARM-G    red   cursor=1 evicted_before=141 maxring=100/100 orc=3 to=102 n=100 truncated=False ui=17ms files=240 rows=240 orphan=- FAIL:replay flags the loss (truncated)
  REDok  ARM-G    red   cursor=1 evicted_before=136 maxring=100/100 orc=3 to=103 n=100 truncated=True ui=50ms files=238 rows=237 orphan=['cut-0237.wav'] FAIL:every clip file on disk has a spine row

arms=8 (ARM-A,ARM-B,ARM-C/dead,ARM-C/stall,ARM-D,ARM-E,ARM-F,ARM-G) green=8/8 red-controls-red=8/8 silent-controls=0
CENSUS (own cadence, full artifact path): no gate process alive after the run
GATE-VERDICT: GREEN   total 400.9s
```
Battery verdict, verbatim:

```
BATTERY GATE EXIT=0  wall=401.0s
BATTERY RESULT
  PASS  gate exit code 0
  PASS  exactly one GATE-VERDICT line
  PASS  gate verdict is GREEN
  PASS  all 8 green arms ran and PASS
  PASS  all 8 red controls ran and went RED
  PASS  all 8 named mutants went RED
  PASS  gate summary says 8/8, 8/8, 0 silent
  PASS  stdout-leak control proves the stdout guard
  PASS  engine stdout empty on every green arm
  PASS  UI reconnect latency measured (ms)
  PASS  no arm threw an exception
  PASS  no silent control
  PASS  census: no gate process left alive
UI-RECONNECT LATENCY (attach -> first ui_ready health, ms): min=2 max=50 [2, 5, 8, 17, 50]
BATTERY-VERDICT: GREEN - 13 step(s) pass
exit-code: 0
```

Note on the BATTERY CMD line: at run time it printed --keep only, because the print sliced
argv[3:] and dropped the --mutants flag. The 8 REDok rows in the same log prove --mutants WAS
passed. The print is fixed to argv[2:] in faffdd6; re-printing the same argv construction now
yields: BATTERY CMD  : python src/engine/test_engine.py --mutants --keep

Note on the ARM-G label evicted_before: it is the MAXIMUM ring.dropped the UI sampled in any
engine health during that arm (run-wide), NOT the number evicted before the attach. The attach
window itself is orc=3 (oldest_retained) through to=102 (newest at attach), 100 events. The two
checks that bind that window to the engine own snapshot are "oldest_retained == engine snapshot"
and "to == engine snapshot newest" (test_engine.py:779-780). The label was kept rather than
renamed, so the lines quoted above stay byte-true of what this code prints.

## 2. The RED-lane mechanism (what makes a red control a control)

A red control is not a hand-written expectation. test_engine.py make_mutant copies the whole engine
tree to a sibling directory, replaces ONE literal line, and runs the SAME arm against the copy.
A mutant that still PASSES is a SILENT CONTROL and is scored as a FAILURE, because it means the
arm cannot see the property it claims to check. Run #3 measured: red-controls-red=8/8
silent-controls=0, and the battery has a separate named check "no silent control".

| mutant | the one line it breaks | the RED row it produced |
|---|---|---|
| stdout-leak | emit() is made to write to sys.__stdout__ behind the guard | stdout=2336B FAIL:stdout empty |
| no-replay | the attach handler drops every retained ring event (evs = []) | replayed=0 exact=False gaps=[{prev:24,next:34}] FAIL:replay is the exact continuation,live ids continue exactly |
| capture-waits | the cut path is made to sleep 3.5 s after submitting to ASR | maxcut=3753ms intervals=[3734, 3753] FAIL:cuts >= 8,capture never waited |
| preflight-ok | the pre-flight refusal on rc=3 | rc=0 FAIL:rc==3,status exit_code 3 |
| no-lock | the exclusive ring lock acquisition | rc1=0 rc2=0 lock-file-seen=False FAIL:second engine refused (rc 4) |
| commit-nokey | content_key computed from the file bytes | keys_ok=0/1 FAIL:every key == file sha256 |
| stale-lie | truncated forced to False, so a stale cursor is never called stale | truncated=False FAIL:replay flags the loss (truncated) |
| no-finalise | the shutdown reconcile _reconcile_clip_dir() | files=238 rows=237 orphan=[cut-0237.wav] FAIL:every clip file on disk has a spine row |

## Appendix A1 - stderr carries diagnostics only (b-green)

engine-stderr.txt, 254 lines, 24733 B, head verbatim:

```
[engine 01:43:04] BOOT pid=42244 python=3.11.8 workdir=I:\cc-tmp\engine-gate-19796\b-green ring=100
[engine 01:43:04] pre-flight (LAW 6): C:\Program Files\Python311\python.exe H:\sotto-wt\engproc\_moved\aireplay\src\engine\stub_capture.py --selftest --session --out I:\cc-tmp\engine-gate-19796\b-green\clips --fps 30
[engine 01:43:04] pre-flight rc=0 decision='DECISION: ARMED - stub' wall=0.1s
[engine 01:43:05] ring lock acquired: I:\cc-tmp\engine-gate-19796\b-green\engine-ring.lock
[engine 01:43:05] spine open: I:\cc-tmp\engine-gate-19796\b-green\engine-spine.db
[engine 01:43:05] capture child pid=45744 argv=C:\Program Files\Python311\python.exe H:\sotto-wt\engproc\_moved\aireplay\src\engine\stub_capture.py --session --out I:\cc-tmp\engine-gate-19796\b-green\clips --fps 30
[engine 01:43:05] [capture-STUB] === CUT SESSION: feed=STUB aus=generated fps=30 dir=I:\cc-tmp\engine-gate-19796\b-green\clips ===
[engine 01:43:05] [capture-STUB] clip 0 open: I:\cc-tmp\engine-gate-19796\b-green\clips\cut-0000.wav
[engine 01:43:05] capture handshake ok=True reply={"ok": true}
[engine 01:43:05] ui door listening on 127.0.0.1:56857 (portfile=I:\cc-tmp\engine-gate-19796\b-green\engine-port.json)
[engine 01:43:05] ui 127.0.0.1:56858#1 WRITER-IDLE sent=0 q=0 alive=True attached=False
[engine 01:43:05] ui 127.0.0.1:56858#1 ATTACH since=0 replay=1 truncated=False
[engine 01:43:05] clip cut-000000 written: cut-0000.wav key=984a778ea941 bytes=5374 frames=2665
[engine 01:43:05] clip cut-000001 written: cut-0001.wav key=61b3eb35550f bytes=4308 frames=2132
```

engine-status.json, 55 lines, 1128 B, tail verbatim (arms record stdout_bytes and the ring state):

```
   "cuts_requested": 220,
   "cuts_ok": 220,
   "cuts_refused": 0,
   "asr_dead": 0,
   "asr_failed": 0
  },
  "reconciled": 1,
  "clips": {},
  "asr": null,
  "child": {
   "alive": false,
   "pid": 45744,
   "diag_lines": 7,
   "exit_code": 0
  },
  "ui": {
   "connected": 0,
   "attached": 0
  },
  "stop_reason": "seconds-elapsed"
 },
 "spine": "I:\\cc-tmp\\engine-gate-19796\\b-green\\engine-spine.db",
 "portfile": "I:\\cc-tmp\\engine-gate-19796\\b-green\\engine-port.json",
 "lock": "I:\\cc-tmp\\engine-gate-19796\\b-green\\engine-ring.lock",
 "stdout_bytes": 0
}
```

## Appendix A2 - the UI attach/detach evidence (b-green ui.jsonl, 69 lines)

#0 (203 B) - first attach, since=0, replay carries exactly the one ring event:

```
{"v":1,"type":"hello","id":0,"ts":1791607385752,"payload":{"engine_version":1,"pid":42244,"ring":{"size":1,"capacity":100,"dropped":0,"oldest_id":1,"newest_id":1,"next_id":2},"since":0,"capture":"stub"}}
```

#1 (410 B) - the replay envelope for that first attach:

```
{"v":1,"type":"replay","id":0,"ts":1791607385752,"payload":{"events":[{"v":1,"type":"capture_started","id":1,"ts":1791607385663,"payload":{"capture":"stub","clip_dir":"I:\\cc-tmp\\engine-gate-19796\\b-green\\clips","child_pid":45744,"fps":30,"stub":true,"ring":{"size":0,"capacity":100,"dropped":0,"oldest_id":0,"newest_id":0,"next_id":1}}}],"from":0,"to":1,"oldest_retained":1,"truncated":false,"replayed":1}}
```

#35 (207 B) - second attach, hello carries the client since=30 rose to ring newest 44:

```
{"v":1,"type":"hello","id":0,"ts":1791607391786,"payload":{"engine_version":1,"pid":42244,"ring":{"size":44,"capacity":100,"dropped":0,"oldest_id":1,"newest_id":44,"next_id":45},"since":30,"capture":"stub"}}
```

#36 (5487 B) - the second replay envelope, from=30 to=44, replayed=14. First event id 31:

```
{"v":1,"type":"replay","id":0,"ts":1791607391786,"payload":{"events":[{"v":1,"type":"clip_written","id":31,"ts":1791607389859,"payload":{"clip_id":"cut-000029","path":"I:\\cc-tmp\\engine-gate-19796\\b-green\\clips\\cut-0029.wav","content_key":"2f7d5e58c5e4508d1e56ecdcc08959402b1008692f05852e4d9f3644
   ... 13 more events ...
```

The gate parses this file and asserts: replay window is cursor-consistent, replay is the exact
continuation (no hole, no repeat), live ids continue exactly, ids gapless (no holes).

## Appendix A3 - the 3 proof points in ONE stderr chain (ATTACH, DETACH, ENGINE-RECONCILE)

engine-stderr.txt, 253 non-empty lines, every one of them classified, UNCLASSIFIED = 0:
220 `clip cut-XXXXXX written`, 7 `[capture-STUB]` diagnostics, 7 WRITER-IDLE,
2 READER-EXIT, 1 `ui ... read failed`, 2 ATTACH, 1 DETACH, 1 `ui door listening`,
1 `RECONCILED at shutdown`, 4 engine capture lines (argv, `pid=`, `handshake ok=True`,
`exited rc=0`), 2 pre-flight, 1 BOOT, 1 `ring lock acquired`, 1 `spine open`,
1 `cannot write status file: PermissionError(13, 'Acesso negado')` and 1
`main loop stopped: seconds-elapsed`. There are ZERO lines starting `LIVE ` and ZERO
lines starting `SHUTDOWN ` in this file; the `168 LIVE / 11 SHUTDOWN` counts an earlier
draft of this receipt carried were false and are withdrawn here.
Head and tail:

```
[engine 01:43:04] BOOT pid=42244 python=3.11.8 workdir=I:\cc-tmp\engine-gate-19796\b-green ring=100
[engine 01:43:04] pre-flight (LAW 6): C:\Program Files\Python311\python.exe H:\sotto-wt\engproc\_moved\aireplay\src\engine\stub_capture.py --selftest --session --out I:\cc-tmp\engine-gate-19796\b-green\clips --fps 30
[engine 01:43:04] pre-flight rc=0 decision='DECISION: ARMED - stub' wall=0.1s
[engine 01:43:05] ring lock acquired: I:\cc-tmp\engine-gate-19796\b-green\engine-ring.lock
[engine 01:43:05] spine open: I:\cc-tmp\engine-gate-19796\b-green\engine-spine.db
[engine 01:43:05] capture child pid=45744 argv=C:\Program Files\Python311\python.exe H:\sotto-wt\engproc\_moved\aireplay\src\engine\stub_capture.py --session --out I:\cc-tmp\engine-gate-19796\b-green\clips --fps 30
[engine 01:43:05] [capture-STUB] === CUT SESSION: feed=STUB aus=generated fps=30 dir=I:\cc-tmp\engine-gate-19796\b-green\clips ===
[engine 01:43:05] [capture-STUB] clip 0 open: I:\cc-tmp\engine-gate-19796\b-green\clips\cut-0000.wav
   ...
[engine 01:43:37] [capture-STUB] EXIT=0
[engine 01:43:37] capture child exited rc=0
[engine 01:43:37] clip cut-0220 RECONCILED at shutdown: cut-0220.wav key=7d78e8f39503 bytes=2176 frames=1066

```

### A3b - a real 200 ms window census, measured for this receipt and committed

The census block that stood here was written from an artifact that is not in the
evidence root, so it is WITHDRAWN. I re-measured it at a 200 ms nominal cadence over a
fresh ARM-B run and committed the instrument, the log and the run record:

    _main/_engine-ui-census.ps1       the instrument (28 lines)
    _main/_engine-ui-census.txt       its log, 68 lines, 67 samples + CENSUS-END
    _main/_engine-ui-census-armb.txt  the run record: command, verdict row, pid sets

One command produced them, gate root I:\cc-tmp\engine-gate-40232, ARM-B only, kept:

    py -3.11 H:\sotto-wt\engproc\_moved\aireplay\src\engine\test_engine.py --only B --keep

with the census script running concurrently, spawned CREATE_NO_WINDOW like every other
process in this lane. Its measured verdict row, verbatim:

    PASS   ARM-B    green rc=0/0 ui1=5ms ui2=5ms replayed=11(28..39) exact=True cursor=28 ids=63 gaps=[] dupes=0 engring=100/66 live=35 cuts_while_unattended=165 clips=166 files=166 rows=166 orphan=-

The census samples at 200 ms and asks Win32_Process for every python whose command line
names this lane's artifacts, then reads each pid's MainWindowHandle. Measured log,
verbatim:

```
2026-10-10 02:53:10  sample=1 tracked=1 visible=0 :: python.exe:39256:h=0:t=
2026-10-10 02:53:12  sample=3 tracked=3 visible=0 :: python.exe:39256:h=0:t= python.exe:14120:h=0:t= python.exe:25212:h=0:t=
2026-10-10 02:53:21  sample=21 tracked=2 visible=0 :: python.exe:39256:h=0:t= python.exe:14120:h=0:t=
2026-10-10 02:53:44  sample=63 tracked=1 visible=0 :: python.exe:39256:h=0:t=
2026-10-10 02:53:44  sample=64 tracked=0 visible=0 ::
CENSUS-END samples=67
```

Measured totals: 67 samples over 36 s, 63 of them with at least one tracked process,
3 tracked processes at the maximum, and 0 samples with a visible window - every
MainWindowHandle 0, every MainWindowTitle empty. The three pids are named by the
engine's own stderr: 39256 the Engine (`BOOT pid=39256`), 14120 the capture child
(`capture child pid=14120 ... stub_capture.py --session --out ...`), and 25212 the
ui_child, present from sample 3 to sample 20 and gone by sample 21 - exactly the two
attach windows this arm drives (`ATTACH since=0`, `DETACH -- recording continues`,
`ATTACH since=28`, `READER-EXIT ... why=eof`). So the UI process exists only while a
UI is attached, and the Engine outlives its death.

Honest limits of the instrument: the loop sleeps 200 ms and then pays a Win32_Process
query, so the measured cadence is 67 samples / 36 s = 0.54 s per sample, and a window
shorter than that is outside it; ARM-B runs `--asr off`, so no asr_worker.py appears
in any sample. The claim is exactly "no window seen in 67 samples", never "no window
ever existed".

The engine-stderr.txt tail itself names the live traffic and the shutdown reconcile:

```
[engine 01:43:37] [capture-STUB] EXIT=0
[engine 01:43:37] capture child exited rc=0
[engine 01:43:37] clip cut-0220 RECONCILED at shutdown: cut-0220.wav key=7d78e8f39503 bytes=2176 frames=1066
```

## Appendix A4 - ARM-C witness: the cut clock while the AI is stalled or dead

ARM-C is the eighth law, "capture never waits for AI". It was run in two shapes
against the same engine and the same stub capture child.

ARM-C/stall - the ASR child is alive and stuck (stub_asr.py --stall 25). Its final
counters were asr={'submitted': 12, 'done': 0, 'dead': 4, 'failed': 0,
'dropped': 1}: 12 jobs went in, ZERO came back, and the arm still ended with
clips=12/12 and keys_ok=12/12. The cut intervals in ms were
[139, 942, 986, 995, 1005, 1012, 1030, 1071, 1125, 1982] - one outlier, the rest
inside the stub's own ~1 s cadence. The stall lasted 25 s and the cut clock never
joined it.

ARM-C/dead - the ASR child died before finishing anything (--rc 2). Counters
asr={'submitted': 12, 'done': 0, 'dead': 0, 'failed': 12, 'dropped': 0}.
clips=12/12, keys_ok=12/12, intervals [714, 822, 903, 1022, 1032, 1065, 1075,
1238, 1287, 1398] ms. Recording is untouched by the death of the transcriber.

The falsifier for both is the capture-waits control, where the cut is made to wait
on the ASR queue: intervals collapse to [3734, 3753] ms and the arm answers its own
check with FAIL:cuts >= 8,capture never waited (max interval 3753 ms < 2500). A green
arm with a stalled AI plus a red arm that blocks the cut on AI is the pair that
proves the law; neither arm on its own says anything.
## Appendix A5 - ARM-F witness: content_key survives TerminateProcess

The arm starts the engine, waits until 3 clips are committed, then kills the ENGINE with
taskkill /F /PID (Runner.terminate in test_engine.py:213-218 -- TerminateProcess
semantics: no finally, no atexit, no flush, no chance to close the file), and only
afterwards opens the sidecar copy of the spine. The capture child is killed with a
second taskkill /F /PID afterwards (arm_f:958-964), so neither process got to run its
own shutdown path.

Green side, I:\cc-tmp\engine-gate-19796\f-green\engine-spine.db, measured after
the kill:

    integrity_check: ok
    counts: done 3   cutting 0

    cut-000000  state=done  content_key=2dbb7d8c39254117a06afd47a61dd2c3ef9e51518fd354de5a400694df04aea4
               size_bytes=33090  frames=16523  modes=engine-hotkey  committed_at=1791607485.4040122
    cut-000001  state=done  content_key=98ea4df964425b001334477e55906434ca121b5140d810fcd2b285bc5f625338
               size_bytes=30958  frames=15457  modes=engine-hotkey  committed_at=1791607486.421375
    cut-000002  state=done  content_key=634104f3ed21570ccda6fc841b0a1419b9470e2c22b5edc484fc2bd5a9c85220
               size_bytes=39486  frames=19721  modes=engine-hotkey  committed_at=1791607487.7077262

The point is not that rows exist, it is that each key IS the file. I recomputed the
whole-file SHA-256 from the retained clip directory, independently of the spine:

    cut-0000.wav  33090 B  sha256=2dbb7d8c39254117a06afd47a61dd2c3ef9e51518fd354de5a400694df04aea4  = content_key
    cut-0001.wav  30958 B  sha256=98ea4df964425b001334477e55906434ca121b5140d810fcd2b285bc5f625338  = content_key
    cut-0002.wav  39486 B  sha256=634104f3ed21570ccda6fc841b0a1419b9470e2c22b5edc484fc2bd5a9c85220  = content_key

Red side, I:\cc-tmp\engine-gate-19796\f-red\engine-spine.db, the commit-nokey
control, which strips the key computation from commit_clip():

    cut-000000  state=done  content_key=0000000000000000000000000000000000000000000000000000000000000000
    cut-000001  state=cutting  content_key=NULL  committed_at=NULL  size_bytes=0  frames=0

The very same directory re-measured: cut-0000.wav is still 33090 B with
sha256=2dbb7d8c39254117a06afd47a61dd2c3ef9e51518fd354de5a400694df04aea4, so the
control really did store 64 zeros where the file hash belongs - that is why the arm
fails on FAIL:every key == file sha256. And cut-0001 shows the two-step lifecycle
working as designed: a killed engine may leave a cutting row, and that row must have
content_key NULL and zero size, which is exactly what is on disk.
## Appendix A6 - what the gate does NOT cover (read before trusting section 1)

1. **Capture arms run against a STUB, not the real C++ binary.** The real binary,
   H:\sotto-wt\engproc\_moved\aireplay\src\capture, carries the pre-flight and
   LAW-6 (exit 3, no encoder) arm only. It cannot feed an offline clip, so the ring,
   clip, UI and ASR arms use src\engine\stub_capture.py, declared stub arms in the
   receipt. Cause, measured read-only in src\capture\main.cpp:
   SourceStream::load captures SPS/PPS only inside `if (vcl)`, but SPS/PPS are NOT
   VCL NAL units, so src.sps/src.pps are always empty and every offline feed is
   refused with `no SPS/PPS: avcC cannot be built`. The one-line fix is not this
   lane to make - src/capture is not mine. Consequence: LAW-1..LAW-8 are proved
   against the Engine and the stub child, and ONLY the Engine-level behaviour of the
   real child (its EOF path, its JSON replies, its refusal) is exercised, via ARM-A
   and ARM-D.

2. **WGC is blocked in another lane.** The Engine links no d3d11/dxgi, opens no
   window, takes no audio device, and never requires WGC (design-notes/03-engine-ipc.md).
   Window-capture correctness is therefore out of scope here and unproven.

3. **Files the brief named that do not exist.** Reported, not substituted:
   - `_moved/aireplay/ACKNOWLEDGE_AGENT.md` - absent (product root and worktree).
   - `src/index/video.py` - absent. The index is `src/index/schema.sql`.
   - `src/engine/__init__.py` - absent in both trees; the engine modules are imported
     by path, so there is no package to break.
   - `_moved/aireplay/runs/` - absent in the worktree. The plan of record,
     `runs/P4-aireplay-engine-process.md`, was read from the product root H:\sotto.
   - `I:/cc-tmp/battery-engine-v2.txt` - absent at lane start. The file now there is
     THIS battery run 3 gate log, not the missing source. The battery script itself
     had to be rebuilt: `_main/_engine-audit-battery-v2.py`.

4. **A blob of what is measured is stub-internal.** ARM-C intervals, ARM-B clip counts
   and ARM-G eviction counts include the stub child's clip cadence, not NVENC
   encode timing. Nothing in the receipt should be read as a statement about the real
   encoder.

5. **One measured limitation of the box, not of the Engine:** os.kill(pid, 0) kills
   its subject under CPython 3.11.8 Windows, so the ring lock's liveness probe uses
   ctypes Win32 OpenProcess(SYNCHRONIZE) + WaitForSingleObject and fails closed.
   It is measured in ARM-E (refusal) but NOT in the pathological case of a PID reused
   by an unrelated process while our lock file survives - that case is UNKNOWN.
## 3. Decisions taken here, and the alternative each one refused

D1. Language: a **Python Engine** supervises the C++ capture child and the Python
    ASR worker, all over JSONL on pipes. Rejected alternative: writing the Engine in
    Rust and having it own the ring, the spine and the audio tap in-process from the
    start. Refused here because the Engine must land in this roadmap step, and the
    whole capture/ASR hull already exists in C++/Python; the Rust version stays the
    long-term core and is recorded as an accepted divergence (section 4).

D2. Shutdown close of the last clip is **reconciliation of the clip directory**, not a
    "cut then close stdin" sequence. Measured: the child writes NO JSON reply on its
    stdin channel after EOF, so awaiting one deadlocks; and a shutdown cut leaves a
    44-byte zero-frame WAV and inflates cuts_ok. The stub was deliberately left
    matching the real child. Reconciliation does NOT bump cuts_ok; it reports in
    `health.reconciled` (run 3 b-green shows `"reconciled": 1`).

D3. Second-instance refusal is an **exclusive lock file** whose owner PID is proved
    alive before a steal attempt. Rejected: PID-file-only (racy between check and
    open), a named mutex (per-session, would not survive a logoff, and cannot tell a
    stale holder from a live one), and unconditional theft (two engines would fight
    over one WASAPI loopback endpoint). The liveness probe cannot use os.kill(pid, 0),
    because on this box that call KILLS the subject; it uses ctypes
    OpenProcess(SYNCHRONIZE)+WaitForSingleObject and fails closed.

D4. stdout is sealed at boot by `_silence_stdout` and the status file carries
    `"stdout_bytes": 0` so the claim is measurable, not asserted. The stdout-leak
    red control removes the seal and the arm goes RED at 2336 B.

D5. Observer failures are named, never hidden: a sidecar the OS would not release is
    retried 20 x 0.25 s and then reported as the FAIL line
    `every spine sidecar copied (no OS lock)`. Rejected: swallowing the error (the arm
    would look green while reading zero rows) and letting it traceback (the run would
    die before the verdict).

D6. ARM-G keeps the label `evicted_before` for the MAXIMUM `ring.dropped` sampled
    during the arm. The label is not exactly what it says; it is kept so every quoted
    gate line stays byte-true. Renaming it would have made the receipt prettier and the
    evidence unverifiable.

## 4. The accepted divergence, in one sentence

Python-vs-Rust divergence: this Engine is a Python supervisor speaking JSONL to a C++
capture child and a Python ASR worker, where the roadmap's long-term core is one Rust
process owning the ring, the spine and the audio tap in-process - that difference is
recorded here as ACCEPTED for this step, not as a defect to be closed inside it.

## 5. UNKNOWN (not measured here, do not read as working)

- The real C++ capture child driving the Engine end-to-end on a live window session.
  Blocked by the SPS/PPS defect in src/capture (A6.1) and by the WGC lane.
- Real NVENC encode timing, bitrate and quality through the Engine. ARM-D proves only
  that a missing encoder is detected and answered with exit 3.
- Two or more UI clients attached at the SAME time. Every arm attaches exactly one
  client (three UI_CHILD launches in test_engine.py, one per arm), so the hub holding
  several simultaneous connections is code-read only, not measured.
- A PID reused by an unrelated process while our ring lock file survives (A6.5).
- The real ASR model under Engine supervision. The ASR side ran stub_asr.py with
  `--stall 25` and `--rc 2`; a real model's latency, partial cadence and death
  behaviour are unmeasured.
- Anything the owner's screen must show. The gate ran headless by construction
  (CREATE_NO_WINDOW on every spawn, and the gate never requires the display).
- Long-horizon behaviour: the longest measured session here is ARM-G at 46.3 s.
## 6. Revisions this receipt speaks about

Code under lane ownership (H:\sotto-wt\engproc), measured on the branch
feat/engine-process at HEAD faffdd6:

    src/engine/engine.py        60743 B  sha256 1dcb9aeca04ef86b
    src/engine/protocol.py       5505 B  sha256 b2a3f63bf77f5cb6
    src/engine/store.py          7223 B  sha256 6a83ebf80e0fadf3
    src/engine/capture_child.py  7872 B  sha256 4fdb115d8d87229c
    src/engine/asr_worker.py     8793 B  sha256 f1dca398e13b8db1
    src/engine/ui_child.py      11840 B  sha256 208ca9bcec165603
    src/engine/stub_capture.py   9394 B  sha256 d038b7ef61bff0f0
    src/engine/stub_asr.py       2736 B  sha256 68baa9b24ec7071b
    src/engine/test_engine.py   52459 B  sha256 3edff3c8d71153b5

Evidence and instruments committed with this lane:

    _main/_engine-audit-battery-v2.py      9823 B  sha256 cd10f3070c3719a6  (argv[2:] fix)
    _main/_engine-audit-battery-v2.txt    10141 B  sha256 0650b62bc2378249  (run 3 gate log)
    _main/_engine-audit-battery-v2-run.txt 11179 B  sha256 fa288e0c207b4736  (run 3 battery log)
    _main/_engine-ui-census.ps1            1161 B  sha256 0b42a8b1e66629b7
    _main/_engine-ui-census.txt           7111 B  sha256 4b78218a7d4b7009
    _main/_engine-ui-census-armb.txt       1410 B  sha256 c2198a678d4d2e9f

## 7. Reproduce, both colours, ONE command

    set TMPDIR=I:\cc-tmp
    "C:\Program Files\Python311\python.exe" _main\_engine-audit-battery-v2.py

That invocation runs the 8 green arms and the 8 red controls in one process and
prints one verdict. A single control can be re-run against a tampered copy of the
subject with `--neg-arm <name>`, which must come back RED; a PASS there means the
control measures nothing. Negative-proof, on a tampered COPY of the live subject, not
on the live subject:

    "C:\Program Files\Python311\python.exe" _main\_engine-audit-battery-v2.py --log I:\cc-tmp\battery-engine-v2.txt

The battery aggregates 13 steps and exits with the verdict as its exit code
(`--log` mode re-scores a stored log and prints 12 of them; the run verdict is 13).

## 8. Measured UI-reconnect replay latency

    min=2 ms   max=50 ms   values [2, 5, 8, 17, 50]

Measured as attach -> first ui_ready health, on the ARM-B and ARM-G reconnects of run 3
(the same numbers as the two ui1/ui2 columns and the ui=8ms/ui=17ms cells in section 1).
