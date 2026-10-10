# AUDIT-FINDINGS - Sotto (ShadowPlay clone)

Orchestrator-authored accumulator, written WHILE the six lanes are still running, so nothing
measured here is lost by a later context reset. It carries FACTS and the instrument that
produced them. It is NOT the verdict: the owner-ordered full audit runs after the lanes are
merged, committed and pushed.

Repo of record: H:/sotto, branch feat/build-verify-1 @ 399bc85.
Product tree:  H:/sotto/_moved/aireplay (nested repo, remote aireplay.git).
Written 2026-10-09 ~20:50Z, read-only measurements from the orchestrator session.

Rule applied below: MEASURED with a named command, or UNKNOWN said plainly. No number is
estimated. Where a claim circulating in this session was WRONG it is retracted by name
rather than quietly replaced.

## A. FOUR CLAIMS IN CIRCULATION THAT WERE MEASURED THIS SESSION

### A1. 10 of 16 lanes never got a reviewer row -- FALSE. The real gap is 11 lanes, and the count came from a bad string match.
MEASURED: receipts/ has 71 files; 22 are review-Ln rows, for lanes 1-10 and 12-23 (10419-37114 B
each, all dated 2026-10-07). ABSENT review rows: L11, L24, L25, and every number 26-36.
Receipts EXIST for each of those (receipt-11-onnx-threads.md, receipt-24-clip-to-asr-chain.md,
receipt-24-wake-defects-fixed.md, receipt-25-overlay-panel.md, receipt-26..36). So the
ledger rule (a lane that lands needs a reviewer row) is unmet by 11 historical lanes.
The wrong 10-of-16 figure came from matching review-L1 against the gate prefix _lane01:
a string comparison without normalising the leading zero. Rule: name the instrument.

### A2. receipt-24 delivered the clip->ASR chain module -- FALSE as stated, and the receipt itself is honest.
MEASURED: receipt-24-clip-to-asr-chain.md (25590 B / 371 lines) delivers FOUR files and all
four are on disk at the exact byte counts it prints: src/pipeline/__init__.py 1000,
contracts.py 30015, chain.py 49948, _main/_lane17-chain-gate.ps1 26616.
chain.py is a 1062-line ONE-SHOT RUNNER (12 top-level defs; StageReport, CutResultMeta,
Doubles, ChainRunner, ChainReport) - an instrument, not a library function.
A file named clip_to_asr.py exists on this box ONLY inside the lane-B worktree
(H:/sotto-wt/clipasr/_moved/aireplay/src/pipeline/clip_to_asr.py), untracked, written this
session. It is in neither repo index and in neither git history (git log --all --
src/pipeline/clip_to_asr.py returns EMPTY in BOTH repos).
So: the chain was never shipped as a module; lane B is building the missing module now.
Not a lost artifact. But note for the audit: chain.py and the new clip_to_asr.py are two
entry points into the same clip->audio->transcript->index flow. Whoever wires the Engine
must pick one and say so, or the clone will have two paths with different provenance rules.

### A3. _main/_lane34/build-probe.txt (0 B) means the linkage is UNKNOWN -- FALSE. It linked cleanly.
MEASURED mtimes in _main/_lane34: clip_probe.cpp 07:11:43.074Z -> build-probe.txt 07:54
(0 B) -> clip-probe-live.exe 07:55:33.146Z (666205 B) -> _lane34-run/live.mp4 07:55:53.998Z
(146621246 B). The binary was written 20 s before a real 146 MB recording, so the probe
linked AND ran. An empty build log is what a CLEAN g++ link looks like. Reading the 0 B file
as a failure was a wrong inference from absence - the instrument for it exists and says the
opposite. Residual truth: _main/_lane34-run/run-live.txt still DOES NOT EXIST, so the run has
no log, only its output file.

### A4. _main/review-synthesis.ps1 crashes on a None msg_content -- CONFIRMED, cause and fix named.
review-synthesis.ps1:39 returns j.get(msg_content) if isinstance(j, dict) else (nothing),
so a JSON null or a non-string msg_content yields None or a list, and line 53 calls
content(d).strip() on it -> AttributeError. Fix, one line, same semantics:
  def content(d):
      try: j = json.loads(d)
      except Exception: return the empty string
      v = j.get(msg_content) if isinstance(j, dict) else None
      return v if isinstance(v, str) else the empty string

## B. THE DEFECT LEDGER (each with its evidence; nothing here is a verdict)

### B1. GATE POPULATION AND THE TWO STALE PASS ROWS - HIGH
The only aggregate verdict on record is _main/_all-gates-real.txt, MEASURED
2026-10-07T13:00:19-03:00, population 8 gates, 7 PASS / 1 FAIL (the FAIL was
_lane16-wake-gate, which is out of clone scope). The gate population on disk is now 15 files
matching _lane*-gate.ps1. Two gates have changed size since the aggregate run, so their PASS
rows cite a DIFFERENT revision than the one on disk:
  _lane16-wake-gate.ps1    30116 B then  ->  69294 B now  (+39178)
  _lane3-ringcap-gate.ps1  20673 B then  ->  36787 B now  (+16114)
Those two rows are not evidence about today code. Seven gates have NO aggregate verdict at
all: _lane17-chain, _lane18-ui, _lane19-receipt-audit, _lane21-agents-truth,
_lane22-storage, _lane24-wake-defects, _lane25-locale-number.
Required after landing: all-gates.ps1 -TimeoutSec 1800, then -SelfTest, both quoted.

### B2. THE GREEN-BUT-EMPTY-GATE CLASS - HIGH
_lane2-audio-gate.ps1 PASSES (43.5 s, rc 0) while the product binary muxes NO audio: both of
its arms are COMPILE checks (the repo own build path, and a standalone compile). all-gates.ps1
says it itself: a gate that tests nothing and exits 0 is indistinguishable from a working
gate. Mechanism (chain.py:472-487): ffmpeg was judged REAL while the AAC trak the product
would need is unwritten, so an external binary stood in for a producer that never existed.
This is the class the audit must sweep for by asking, gate by gate: what would FAIL if the
product were broken?

### B3. RING CAP - the catch path was never provoked - MEDIUM
receipt-32-ring-defects-closed.md (15635 B) is honest about this: F4 DELIVERED (the live path
now reads the SYSTEM-RAM budget), F6 EXECUTED AND IT DID LIE at N=1 (before the fix the
binary printed GPU class caps at 998 MB; CHOSE 8192 MB while the arena committed 4096 MiB).
NOT verified, by name: a real std::bad_alloc has never been provoked (4 GiB arena would eat
host RAM); no soak past 40 s; the 4K60 row is DERIVED (this box is 1920x1080 and WGC refuses
0x80070005); the unclamped --ring-mb at main.cpp:247 / replay.cpp:133-135; and
(void)seconds_kept; at replay.cpp:149. Lane 3 made NO commit.
Policy of record: cap = min(4 GiB, 25 pct TotalPhys, 50 pct AvailPhys), floor 256 MiB,
MiB-aligned down.

### B4. src/asr/constants.py:58 hard-codes a machine path, against its own file philosophy - LOW but real
constants.py:49-52 carries the rule in a comment: the repo root is derived from __file__ so
the tree can move; a hard-coded root would break silently. Line 58 then hard-codes
H:/sotto. Blast radius is small (only the parity oracle reads it), but it is a portability
trap for any other user and it contradicts the file own stated rule.

### B5. The nested repo drift - 292 tracked files deleted on disk - MEDIUM, needs a receipt
H:/sotto/_moved/aireplay git status --porcelain is ~764 lines: 45 modified, 292 tracked
DELETED on disk, ~425 untracked. The 292 are exactly _main/logs (167), _main/runs (96),
_main/_lane24-gate (15), _main/_import-bench (9), _main/_lane4-run (3), and two directories
whose names now appear as files. Overlap with the 867 files the PARENT tracks under
_moved/aireplay is ZERO, so the parent repo is unaffected. Five prune receipts exist on
disk (backup-20261007-121455 .. backup-20261008-035507). _main/_lane24-gate and
_main/_import-bench are GONE ENTIRELY - the _lane24-wake-defects gate has no instrument.
Nested repo also has 7 local-only commits ahead of its origin/main (1b6f56e).
Junction H:/aireplay -> H:/sotto/_moved/aireplay must NEVER be deleted.

### B6. A retraction file whose NAME is misspelled - LOW, but it hides a retraction
receipts/ contains BOTH receipt-36-RETRACT-wake-latency-artifact.md (4421 B) and
receipt-36-RETRAIT-wake-latency-artifact.md (4276 B). RETRAIT is a misspelling of RETRACT.
A file that exists to announce a withdrawal must not itself be findable under two names.

### B7. Two entries into the same clip->ASR->index flow - see A2

## C. DECISIONS THE OWNER MUST MAKE (a lane may not invent these)

C1. Spec 06 (broadcast-and-capture-card.md, 60775 B / 680 lines) is WRITTEN but has no
implementer, no lane and no investor. Broadcast is the gateable half here (composite +
encode); a capture card cannot even be measured on this box - Get-PnpDevice -Class Camera
returns 0 devices and the only imaging device is an HD Pro Webcam C920.
C2. Which remote wins: the parent sotto.git, or the nested aireplay.git.
C3. Embeddings are BLOCKED ON THE OWNER (no model chosen, no money decision).
C4. Owner-machine trade: 25 pct TotalPhys / 50 pct AvailPhys ring budget against a 47.74 GiB
box with 25.96 GiB free (measured in the 10-09 battery).

## D. NOT MEASURED, SAID PLAINLY

- Press-to-clip latency p95 (build-order step 2) - no run yet.
- Any gate verdict for the 15-gate population on today revisions.
- The 10-09 battery: LINKED (build.cmd direct run, rc 0, 783865 B, 6 warnings, all in
  audio_tap.cpp) but the battery run itself failed at rule 1. BUILD because
  run_battery.ps1 kept its own stale source list without trigger.cpp. LANE F is fixing
  the instrument in the SHARED tree and will run the full battery (-Reps 3 -Census).
- ASR in a worktree: only engproc and clipasr have the models junction. Do NOT run ASR in
  audioclip, wgcunb or specs57.

## E. HOW THIS FILE IS MAINTAINED

Append-only. A claim that is disproven gets a RETRACTED line, never a silent edit. Every
number names its instrument. This file is untracked until the orchestrator commits it by
explicit path.
## F. LANE F - BATTERY INSTRUMENT REPAIR AND THE 10-09 BASELINE (landed as 431b423)

### F1. The battery now runs to completion. MEASURED 2026-10-09, command on record.
LANE F repaired the one stale line in src/capture/run_battery.ps1 (its own source list
lacked trigger.cpp) and ran the whole battery in the SHARED tree. Report:
  H:\sotto\_moved\aireplay\_main\logs\cap-battery-20261009-175104.txt
  149 lines / 14036 bytes, read in full and quoted row by row below.
Launcher: I:/cc-tmp/lanef_battery_run.cmd ->
  pwsh -NoProfile -File H:\sotto\_moved\aireplay\src\capture\run_battery.ps1
    -Root H:\sotto\_moved\aireplay -Reps 3 -Census < NUL > I:/cc-tmp\lanef-battery.txt 2>&1
Rowed tally printed by the battery itself: MEASURED=15  DERIVED=0  NOT_MEASURED=3
untagged=0. Exit code 0 means the battery RAN; it does not mean every row passed.
No rule was skipped (no CK FAILED / NO VERDICT / ERROR line in the 149 lines).

### F2. The baseline rows (each quoted from that report)
MACHINE  RTX 5080 driver 32.0.16.1714; i5-13600K 14C/20T; RAM 47.74 GiB / 25.96 free;
         nvidia-smi rc=0; DISPLAY1 1920x1080.
BUILD    rc=0, warnings=6 (all in audio_tap.cpp), exe 783865 B, sha256 6CADE9A3C1D46...
         and the gated mutant build also rc=0 (mission critical: a gate that cannot go red
         is not a gate - this one can).
NVENC    5 arms, all as designed: normal rc=0 ARMED codec=H.264 engines=2 max=4096x4096;
         tuning refused rc=3 (NvEncInitializeEncoder -> 8); no-nvenc rc=3; skip-map rc=3;
         MUTANT-control rc=0 codec=MUTANT engines=0 max=0x0.
WGC      5/5 refused with 0x80070005 while IsSupported reports supported=1: own window,
         foreground window, desktop shell, taskbar, and CreateForMonitor.
MUXER    rc=0 at 1080p (aus=1800, 146621246 B, wall med 479.6003 ms) and at 4K
         (aus=1800, 149735942 B, wall med 466.5204 ms), ffprobe re-counting 1800 frames
         each, null-decode stderr 0 B. Both RED arms rc=2 as intended.
TIMING   3 rows: the two NOT MEASURED capture rows (POPULATION=0 because WGC refuses) and
         two EXTERNAL-tool encoder rows - ffmpeg h264_nvenc 300 frames: med 1013.2 ms
         (3.377 ms/frame) at 1080p and 3224.1 ms (10.747 ms/frame) at 4K, POPULATION=3.
AUDIO    8 Win32_SoundDevice rows, all state=OK status=3, listed BY NAME ONLY.
         NOT ENUMERATED: per-API indices (MME / DirectSound / WASAPI), POPULATION=0.

### F3. NEW DEFECTS, all MEASURED by the same run, NONE FIXED YET
F3a mux-4k-LIED - the product writes a file that decodes at one size and is declared at
    another. The battery fed a wrong --cut-size on purpose: rc=0, aus=1800,
    real SPS = 3840x2160 while the container tkhd/avc1 says 1920x1080. ffprobe CANNOT
    see it because ffprobe reads the SPS; a player sizes the track from tkhd/avc1.
    Cause: mp4_writer.cpp writes cfg_.width/height into BOTH the avc1 sample entry and
    the tkhd track header, and replay.cpp cut_from_h264 assigns w_/h_ from --cut-size
    rather than from the stream, while avcC carries the stream REAL SPS.
F3b The ring-floor message blames the wrong thing. rc=2 with OFFLINE CUT FAILED: ring
    capacity below 16 MiB - that cannot hold a cuttable window. The actual cause is the
    fixed arena guard capacity_bytes < (16u << 20) in ring_buffer.cpp. Same text is
    printed for a NON-H.264 input, where 16 MiB has nothing to do with the refusal.
F3c run_battery.ps1 RunNative cannot serve a stdin-driven exe (instrument defect, no
    product defect): Start-Process -RedirectStandardOutput/-RedirectStandardError does
    NOT propagate an inherited stdin handle, so a blocking ReadFile on STD_INPUT_HANDLE
    never returns. A/B measured 3 modes: MODE 0 stalled; MODE 2 (cmd /c ... < NUL) rc=0
    with STDIN CONTROL: stdin closed (0 commands served) and a full DECISION line.
    Also RunNative $TimeoutSec is declared and NEVER USED - the battery has no timeout.
F3d The -Census flag produced NO census/window rows in the report (no WINDOW=, no
    census line). So the battery cannot currently prove no visible console window.
F3e Nested-vs-parent tracked-revision divergence: src/capture/audio_tap.h and
    src/capture/d3d11_ctx.cpp are MODIFIED in the nested repo but CLEAN in the parent,
    and audio_tap.cpp is UNTRACKED in the nested repo while the parent tracks it.

### F4. Landing facts (parent repo H:\sotto, branch feat/build-verify-1)
Landed as 431b423 - 1 file changed, 1 insertion, 1 deletion, that file only. Verified
with git show --stat. Two earlier accidental commits (e7b6cbd, 127655a) that had
swallowed the 5 pre-staged ORIGINAL app/* files were undone with git reset --soft
HEAD~1 BEFORE any push; the 5 files are staged and uncommitted today.
LESSON, now a harness rule: git commit -m '<multi-line message>' -- <path> under
cmd.exe SILENTLY DROPS the pathspec and commits the whole index. Always write the
message to a file and use git commit -F <file> -- <explicit paths>.

### F5. MEASURED LANE-STATE BASELINE, 2026-10-09T22:47Z (the audit's dated reference)
Every row below was produced by git in this run, not by a lane's self-report. Three
consecutive lanes (L-A, L-B, L-C) self-reported git state that measurement could not
find, so this table is the record the final audit compares against.

PARENT H:\sotto, branch feat/build-verify-1 @ 1be1803166e4710d3d37b807c487a135e39f4001
  staged (uncommitted) = exactly the 5 ORIGINAL app/* files, byte-identical to 431b423:
    app/panel/panel.css, app/panel/panel.html, app/panel/panel.js,
    app/panel/theme-switcher.js, app/webview/sotto_webview.py
  commits beyond 399bc85: 431b423, 1d96648, 1be1803. Nothing pushed yet.
  unstaged/untracked noise is the pre-existing panel skin/theme work - OUT OF SCOPE
    (this branch must carry only the ShadowPlay-clone work; the audit must decide
    what happens to the 5 staged originals and the 25 backdrops BEFORE any push).

LANES (all are worktrees of H:\sotto, all rooted at H:\sotto-wt/<lane>):
  engproc    feat/engine-process  @0e1b7f5 ahead=1  dirty=0   (10 files +3289, engine/)
  clipasr    feat/clip-to-asr     @1d96648 ahead=1  dirty=0   (LANDED as 1be1803)
  audioclip  feat/audio-in-clip   @f30dcca ahead=2  dirty=12  (first measured!)
  wgcunb     feat/wgc-unblock     @399bc85 ahead=0  dirty=3   (dirty size!)
  specs57    feat/specs-05-07     @399bc85 ahead=0  dirty=0   (corrective msg)

  MEASURED FIRST TIME THIS RUN (this checkpoint):
  1. audioclip's 2 commits exist and diff against 399bc85 as 4 files / +560 -1:
       mp4_writer.cpp +264, mp4_writer.h +48, ring_buffer.cpp +183, ring_buffer.h +66.
     The lane is STILL DIRTY in 3 files it has not committed: audio_tap.cpp (staged),
     replay.cpp and replay.h (unstaged). Nothing of its audio work is lost.
  2. wgcunb has NO commit beyond 399bc85 - its WGC unblock is entirely uncommitted.
     It reports a wrong-size/dirty worktree; the branch is the only lane that
     cannot currently be landed (LAND BEFORE GATE, harness rule 4).
  3. specs57 wrote its evidence OUTSIDE its owned paths (I:/cc-tmp/spec05, incl.
     mp4/wav/db artefacts) instead of into runs/ and specs/. Corrective message
     delivered 2026-10-09T22:47Z; it owes three commits.

AUDIT-DUE ITEM, CLOSED THE SAME SESSION (asked and answered, 2026-10-09T22:47Z):
  the binaries do NOT live in src\capture, they live in _main\build\. Re-measured now:
    H:\sotto-wt\audioclip\_moved\aireplay\_main\build\aireplay-capture.exe
      810718 B @ 2026-10-09T18:59:31  (the checkpoint recorded 804441 B - L-C rebuilt)
    H:\sotto-wt\audioclip\_main\build\_audio-tap-qpc-check.exe
      374433 B @ 2026-10-09T19:15:57   <- L-C task (1) has an artefact of its own
    H:\sotto-wt\audioclip\_main\build\_audio-mft-probe.exe
      420017 B @ 2026-10-09T17:29:34
  So the audit can find every L-C artefact by name; a claim about "the exe" must carry
  the SIZE and the MTIME of one of these three paths, not the word.

### F6. THE NESTED-TREE DRIFT, RE-MEASURED 2026-10-09T22:55Z (audit question #1)
Repo H:\sotto\_moved\aireplay\.git (remote aireplay.git), branch main @ 1b6f56e,
7 local-only commits ahead of origin/main. status --porcelain -uall = 1178 rows:
  53 modified, 287 tracked-DELETED, 838 untracked.
  The checkpoint's "~764 lines" is now STALE - it is 1178. The 287 deletions are the
  prune receipts landing as deletions of tracked files (logs/ 167, _main/runs/ 96,
  _lane24-gate/ 15, _import-bench/ 9, _lane4-run/ 3, plus two more). A "git add -A"
  in the nested tree would record all 287; the 838 untracked include MY OWN
  _main/AUDIT-FINDINGS.md, so that command would also stage the audit's evidence
  into a repo it does not belong to.
  Tracked-file comparison against the parent branch (ls-files, both sides):
  parent tracks 33 paths under _moved/aireplay/src/capture, nested tracks 32; the
  ONLY difference is src/capture/audio_tap.cpp (parent tracks it, nested does not).
  Nothing in src/capture diverges between the two repos TODAY except that one file.

### F7. LANDING VERIFICATION of 1be1803 - done, measured 2026-10-09T22:56Z, PASS
The blob side of the merge is byte-identical to what lane B reported it measured:
  _moved/aireplay/src/pipeline/clip_to_asr.py     blob 9defedd 32306 B  sha256 b1462fc7...
  _moved/aireplay/src/pipeline/test_clip_to_asr.py blob e5ea65b 45771 B  sha256 9d9e48ad...
  _moved/aireplay/_main/receipt-20261009-clipasr.md blob f26d8aa 17302 B
Both blob sha256 values match lane B's OWN reported sha256 for its LF sources, so the
merge introduced no re-encoding. HEAD parents = 431b4232... + 1d9664891... (second
parent is lane B's tip, as intended). The worktree copies are the CRLF conversions
(33032/46814/17578 B) - expected under core.autocrlf=true, do not cite them as the bytes.
This is the landing-check the audit will demand for every remaining lane: blob size +
git blob sha256 + second parent, never the worktree file.

### F8. HOST RAM, RE-MEASURED 2026-10-09T23:12:11Z (this closes the owed measurement)
Instrument: I:\cc-tmp\ram-probe.ps1 (pwsh -NoProfile -File; the inline -Command form has
returned EMPTY stdout on this box, which is why the .ps1 FILE form is mandatory). Output:
I:\cc-tmp\ram-20261009.txt.
  TotalVisibleMemorySize_KB  50061360   -> visible 48888 MB / 47.74 GiB
  TotalPhysicalMemory_BYTES  51262832640  (= the same 47.74 GiB; visible == physical)
  FreePhysicalMemory_KB      26566240   -> free 25572 MB / 53.07 % of visible
  PoolPagedBytes 3395702784 / PoolNonpagedBytes 1812647936
The 48888 MB visible figure matches the earlier number of record exactly, so the box has
not changed; what moved is FREE RAM: 23293 MB -> 25572 MB. THIS IS WHY ~6 GB was the
working constraint during the afternoon and why a heavy re-run may be cheaper now.
Effect on the owner decision C4 (ring budget): with cap = min(4 GiB, 25 % TotalPhys,
50 % AvailPhys) the 4 GiB term dominates at all three candidate values, so the ring cap
is 4 GiB and the 256 MiB floor is unreachable on this box. NOT A NEW DECISION - it is the
same rule evaluated on a fresh measurement. Recorded as the ring cap the code may assume
once replay.cpp actually budgets by RAM (d3d11_ctx.cpp:70 still clamps by VRAM/16).

### F9. THE LANE-COLLISION INCIDENT, 2026-10-09T23:07:48Z (an audit rule, not a lane fault)
I dispatched a second agent into H:\sotto-wt\audioclip while L-C was live in the same
worktree, on the same branch feat/audio-in-clip. I interrupted it at 23:07:48Z. Measured
state after the interrupt:
  tip b390e3d, 6 commits ahead of 399bc85 (L-C had reported 2), 9 porcelain rows,
  all untracked (_main/_audio-mft-probe.cpp, _main/_audio-tone-inject.py, the two
  _main/build/_audio-*.exe, _main/runs/live{2,3,4,5}/*). No modified rows left -
  whatever was dirty got committed by one of the two agents.
  Three new commits existed and I could NOT attribute them:
    b390e3d  capture: the cut writes an audio trak -- AAC first, raw PCM fallback (+513 replay.cpp)
    b549bb3  capture: link mfplat/mfuuid -- the AAC encoder needs Media Foundation (build.cmd)
    5976ba4  capture: the loopback tap stamps its buffers with qpc (+32/-3 audio_tap.cpp)
  Nothing was lost - worktrees share the object store, so committed work survives the
  interrupt - but ownership of those three commits is UNKNOWN until L-C reads them.
RULE FOR THE AUDIT, earned here: "the lane reported N commits" is not a landing
precondition. What is: the ORCHESTRATOR re-measures ahead-count, tip, porcelain and
attribution itself, and a commit nobody can attribute is repaired by its author, not by
reverting it. Two lanes never share a worktree path, even transiently.

### F10. THE PARENT WORKTREE H:/sotto IS NOT A CLEAN LANDING TARGET - measured 2026-10-09T23:13Z
The parent repo is the ORIGINAL product (app/panel, app/webview) with the aireplay tree parked
under _moved/aireplay. Measured now, branch feat/build-verify-1 @ 1be1803, 4 commits ahead of
origin (nothing pushed, as intended):
  porcelain rows = 10194  =  6 staged?  NO - measured exactly FIVE staged, all app/*:
     app/panel/panel.css, panel.html, panel.js, theme-switcher.js, app/webview/sotto_webview.py
     (git diff --cached --stat = +424 / -111 over those 5; gen_themes.py is worktree-only, NOT
     staged - my first reading said staged because of a leading-space parse bug, corrected here)
  18 tracked files modified in the WORKTREE and NOT staged (panel.css .html .js theme-switcher.js
     skin-layout.css, app/panel/themes/theme-1..5.css, _main/panel-visibility.json,
     _main/_tmp-panel-noreveal/themes/theme-*.css x5, _moved/aireplay/_main/wake-{counters.json,
     last-message.md}, _main/_design-lane/gen_themes.py). The worktree copies are LARGER than the
     staged blobs (panel.css 75413 staged vs 87673 on disk), so something edited them AFTER the
     index was built.
  10 173 untracked (ls-files --others --exclude-standard). Big populations, for the push/add -A
     hazard map: _main/_epvenvs 8834, _main/_venv-diar 779, _main/_libs 218, _main/_design-lane
     93, _main/_skin-lane 89, app/panel 44, _main/_skin-owner 28, _main/_tmp-panel-noreveal 24,
     _main/build 11, _main/diar-models 10, _moved/aireplay 7, plus a literal $null and a .txt
     entry. NOTHING under _moved/aireplay/**, so the aireplay side is clean of add -A junk.
  TWO LIVE WRITERS into this tree, both NOT mine:
   (a) a 3-minute wake loop (Windows scheduled task, EXEC-CHILD pid 38248, cadence 180 s) that
       rewrites _moved/aireplay/_main/wake-counters.json every pass - last write 2026-10-09T23:13:16Z.
       Its own log heartbeat.log (2.3 MB, 11 824 lines) ENDS at 20:13:02 with
       "WAKE rc=4 ... mcode exec failed: The Token Plan usage limit has been reached" - the
       executor it wakes is out of credits, so the wake goes nowhere but the counters still grow.
   (b) a design/skin lane in the ORIGINAL product: _main/_design-lane/shot.py 23:01:54Z,
       gen_themes.py 22:43:07Z, _geom.js 22:34:08Z, app/panel/themes/theme-1.css 22:46:13Z,
       app/panel/panel.css 22:49:17Z. That work is the product the owner told me NOT to continue,
       it is not one of my nine agents (descendant list checked), and it is what moved the
       panel.css worktree copy after the index snapshot.
CONSEQUENCE FOR THE LANDING/PUSH: a push moves commits only, so none of this dirt travels; but
ANY test that reads the parent worktree to prove a landed lane is measuring THAT. Landings must
keep proving the BLOB (git cat-file on the landing commit), which F7 already does, and the audit
must not treat "the file on disk" as the landed bytes.
### F11. L4 wgc-unblock LANDED-ELIGIBLE on first measure - commit 25b6b40b (2026-10-09T23:2xZ)
The lane rebuilt its OWN committed bytes into scratch exes and re-ran them, which is the standard
the receipt is held to (not the working copy). Verdicts as measured by it, each with the instrument
in the receipt `_moved/aireplay/_main/_wgc-receipt-20261009-wgc-unblock.md` (269 lines, TRACKED):
  H1 medium IL     UNTESTABLE on this box - not "green", not "red". Cause measured, not guessed:
                     EnableLUA REG_DWORD 0, ConsentPromptBehaviorAdmin 0, account RID 500 (not
                     1001+), seclogon STOPPED, and 0 medium-IL among 230 readable tokens. The arm
                     prints SKIP, never PASS - the correct shape for an untestable hypothesis.
  H2 session/station  GREEN (sessionid 1, active console session 1, WinSta0, Default desktop).
  H3 capture stack    GREEN (dwm present, item_factory/access_factory/session_factory all ok,
                     331 services enumerated).
  ARM-D               REJECTED with NO MEASURED EFFECT: CreateForWindow and CreateForMonitor
                     both return 0x00000000 S_OK with, without, and with an awaited
                     RequestAccessAsync. No E_ACCESSDENIED (0x80070005) was produced at all, so
                     the E_ACCESSDENIED prose in HANDOVER.md §3 / receipt-03 §7 / receipt-18:118
                     describes a 2026-10-07 state and is retired by this run.
  wgc_capture.cpp    UNMODIFIED: 14 470 B, 0 occurrences of RequestAccessAsync or E_ACCESSDENIED,
                     absent from porcelain. The lane correctly refused to edit it on a "might
                     help" basis - the brief allowed an edit only if the HRESULT demonstrably moved.
  build.cmd          append-only PROVEN by blob prefix (1907 -> 4244 B, startswith True); the one
                     deleted byte is the `\ No newline at end of file` marker. Both colours hold:
                     `build.cmd probe` still product-builds first and prints PROBE BUILD OK; a bare
                     `build.cmd` prints no probe output.
  no console         three instruments, the only visible window being the probe's own 32x32 tool
                     window (WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE), 0 of 56 samples of a console.
KNOWN, declared by the lane and not discoverable by the reader: the probe stops at CreateForWindow;
no D3D device, no frame pool, no session. It proves the call succeeds, NOT that the product reaches it.

### F12. Two FALSE ANCHORS in the wave-2 dispatch briefs, corrected (2026-10-09T23:3xZ)
The lease lane (Phase B) read its brief and found two paths that DO NOT EXIST:
  `_moved/aireplay/ACKNOWLEDGE_AGENT.md` - ABSENT. The real anchors are AGENTS.md /
    HANDOVER.md / ROADMAP.md, measured by that lane, not assumed.
  `src/index/video.py` - ABSENT. The index is defined in **src/index/schema.sql** (206 lines);
    the specs are docs/research/07-index-search.md and docs/research/08-import-library.md,
    row 14 of the latter carrying the stage list probe->thumb->audio->asr->frame->embed->ocr.
  Writing briefs from a remembered tree instead of a listed one costs a lane a whole turn. Every
  future brief gets its anchors from `ls`, and the lane is told the anchors may be wrong and to
  report rather than substitute.
The same lane also ran a census that answers two questions this audit had open:
  - **NO LEASE EXISTS IN CODE.** No job table and no `lease_expires_at` anywhere under src/
    (census 2026-10-09, word-boundary, every dir). The only executing lease on this machine is
    the AGENT RUNTIME's (local_runtime_queue_items.claim_lease_expires_at_ms, read by
    `_main/check-delivery.py:61-64`, `_main/watch-wake.py:109-111`, predicate at
    `_main/wake-fix.py:322-359`). A landing that claims the product enforces leases would be
    false - specs/04-index-search.md:163-164 says it in words, and 08:14 says the rule once,
    and no code implements either.
  - **THE MP4 CARRIES NO WALL CLOCK, AND THE NAÍVE READ IS A TRAP.** creation_time and
    modification_time are written as literal 0,0 (mp4_writer.cpp:257,272,293), so reading them
    yields 1970-01-01 - a value that looks measured and is not. key.json.started_at_s is a
    parse of the clip_id it lives under (layout.py:433), so it is NOT an independent witness.
    The only genuinely independent time left on disk is mtime_ns, last in the priority order
    by design. The instrument that measures this (ODS-1) is DESIGNED AND NOT RUN as of this
    finding; its own doc says so.


---

## F13 - GATE-AUDIT CORRECTIONS (read-only re-verification of _gate-audit/gate-verdict-matrix.md)

POPULATION: 5 claims inherited from `_gate-audit/gate-verdict-matrix.md` (landed by f4ca6691).
WINDOW: each re-read against the aggregate it cites, 2026-10-10. Four survive, one is CONTRADICTED,
one is ADDED. The gate audit's own split (6 current + 2 STALE + 7 UNKNOWN over 15 gate rows) is
unchanged by this finding.

**F13.1 CONFIRMED - the "two NOT MEASURED capture rows" count is THREE.** `AUDIT-FINDINGS.md:175`
says "TIMING 3 rows" verbatim and then enumerates only 2 NOMEASURED rows plus 2 external-ffmpeg
rows. The aggregate (`_main/logs/cap-battery-20261009-175104.txt`, 14 036 B, 150 lines) carries a
third NOT MEASURED row that is NOT a WGC consequence: the per-API audio-input index gap, whose only
evidence is the scalar `:53 items_tried=5 E_ACCESSDENIED=5`. It must be attributed to the audio
input path, not to the WGC refusal. Both counts are now on the record; a reader who takes "3" from
the sentence and 2 from the list will reconcile them wrongly.

**F13.2 CONTRADICTED - THE TWO WGC INSTRUMENTS DISAGREE ABOUT THE SAME API CALL, AND NEITHER
NUMBER CAN BE QUOTED AS "THE STATE OF THIS BOX" YET.** This is the most important open item in the
capture stack, so it is written in full.
- INSTRUMENT A: `_main/wgc-probe.exe`, 307 103 B, mtime 2026-10-07T13:09:59.0265941-03:00, built
  by another lane from `_main/wgc-probe.cpp` (345 lines). Run 2026-10-09T17:51 inside
  `src/capture/run_battery.ps1` section 3 (`RunNative $wgcExe`, `$wgcExe = _main\wgc-probe.exe`).
  Result: probe rc=0, `items_tried=5 E_ACCESSDENIED=5`, `IsSupported supported=1`, and
  `CreateForWindow(our own window) -> 0x80070005` plus foreground/desktop/taskbar and
  `CreateForMonitor(primary)`, all 0x80070005 (`cap-battery...:51,53-60`).
- INSTRUMENT B: `H:/sotto-wt/wgcunb/_moved/aireplay/src/capture/wgc_probe.cpp` (1 648 lines, lane
  feat/wgc-unblock, L-D). ARM-D RED ("CreateForWindow with NO RequestAccessAsync") measured
  **S_OK / 0x00000000**.
- The two are the SAME predicate, and that is what makes it a contradiction rather than a nuance:
  both create the probe window with `CreateWindowExW(WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, <cls>,
  ..., WS_POPUP | WS_VISIBLE, 0, 0, W, H, ...)` (A: 200x200 at `wgc-probe.cpp:329-330`; B: 32x32
  at `wgc_probe.cpp:794-795`), and both call `CreateForWindow` with no `RequestAccessAsync`
  before it. So the difference is NOT the window, NOT the call order, and NOT the API - it is
  build-time (manifest / integrity level) or run-time (session, input desktop, concurrent capture
  holder), and this audit has not measured which.
- CONSEQUENCE FOR LANDING: L-D's ARM-D GREEN ("RequestAccessAsync awaited, then CreateForWindow
  S_OK") and the battery's 5-of-5 E_ACCESSDENIED cannot both describe this box. Any lane, spec or
  gate that repeats either number as fact must say which instrument produced it.
- CONSEQUENCE FOR THE DECLARED UNKNOWN: ARM-D's "stops at CreateForWindow; programmatic access does
  not unblock" is NOT settled - instrument B contradicts its premise, instrument A supports its
  conclusion. UNRECONCILED. Recorded as a BLOCKER to the capture lane. Not guessed around, and not
  resolved by re-running the battery (which also drives NVENC and the fixture muxers).

**F13.3 CONFIRMED ABSENT - the "stale capture source list" defect is NOT open.** The compile sources
are listed inline in the same script at `src/capture/run_battery.ps1:128-129` (`$src\wgc_capture.cpp`,
`$src\nvenc_encoder.cpp`, `$src\ring_buffer.cpp`) and `trigger.cpp` IS present at
`run_battery.ps1:129`. A claim that the capture source list is stale is itself stale.

**F13.4 CONFIRMED PRESENT - the mux-4k-LIED container-vs-SPS defect**, and the instrument is a
BOX READ of the existing `_main/runs/cap-mux-4k-lied.mp4` (probe-cap-tkhd.ps1, no re-encode), NOT
a re-run of the battery. `run_battery.ps1:224` already states why: WGC is refused, so the muxer is
fed a fixture stream, and any capture number in that section is DERIVED, not measured.

## F14 - THE LANDING ENUMERATION HAZARD, CAUGHT BY A DRY RUN BEFORE IT LOST WORK

POPULATION: 1 dry run (feat/wgc-unblock -> feat/build-verify-1, GIT_INDEX_FILE in
`I:/cc-tmp/landing/idx-wgc`). WINDOW: 2026-10-10, nothing landed, no ref moved.

The enumeration that looks natural - `git diff --name-status <target-tip>..<lane>` - is WRONG, and it
does not fail loudly. Against the parent tip 1be1803 it lists THREE FILES OF ALREADY-LANDED WORK AS
DELETED (`_main/receipt-clipasr.md`, `src/pipeline/clip_to_asr.py`,
`src/pipeline/test_clip_to_asr.py`, all landed by 1d966489 via F7) and
`src/capture/run_battery.ps1` as modified - because those changes exist in the LANE's history too
(they are behind the merge base), so a two-way diff reads them as a difference to be applied. Landing
that tree would have reverted L2's clip-to-asr work while claiming to be a wgc-unblock landing.

THE RULE, measured (see LANDING-PROCEDURE.md): enumerate from the MERGE BASE, never from the target
tip. `git diff --name-status $(git merge-base <target> <lane>) <lane>` produces exactly 5 paths
for this lane (receipt A, build.cmd M, three wgc probes A), the intersection with the target-side
changes since that base is EMPTY, and `build.cmd` is byte-identical at base and target
(1 907 B, sha256 a9581698f3aa both) so the lane's append-only blob (4 243 B, 0ec52c0ed16a) is safe to
take wholesale. The dry run is the ONLY reason this was found; the same procedure run blind would
have shipped it.

## F15 - "THE HOTKEY IS UNBUILT" IS NOW HALF FALSE, AND THE REASON THE OLD SENTENCE GAVE FOR THE REST IS VOID

POPULATION: the 15 `.cpp` under `src/capture` (directory listing); the link line
`src/capture/build.cmd:23` (483 chars); `main.cpp` 1401 lines; `trigger.cpp` 567;
`trigger_selftest.cpp` 370; `wasapi_audio.cpp` 1059; `audio_tap.cpp` 1439; 73 references to the
two absent sources across `.cmd/.ps1/.py/.md`. WINDOW: worktree `H:/sotto/_moved/aireplay`
(nested repo `1b6f56e`), parent `H:/sotto` at `927e724`, `build.cmd` 1 932 B mtime
2026-10-09T05:56:59Z, measured 2026-10-10.

**F15.1 THE CLAIM THAT BROKE.** `_moved/aireplay/AGENTS.md:374-376` said "`trigger.cpp`,
`trigger_selftest.cpp` and `wasapi_audio.cpp` are NOT on the `src/capture/build.cmd` link line
(verified 2026-10-07: 10 of 13 `.cpp` are, those three are not; `build.cmd` mtime 10:41:10
predates all three files)". One of its three parts is false and the reason it gave for the other
two is void.

**F15.2 `trigger.cpp` IS ON THE LINK LINE.** `build.cmd:23` carries 12 `.cpp`: main, common,
d3d11_ctx, nv12_convert, wgc_capture, nvenc_encoder, ring_buffer, mp4_writer, selftest,
test_window, **trigger**, replay. The same 12 are `run_battery.ps1:127-129`. The fix
`receipt-29-agents-truth.md:63` prescribed ("append `%SRC%\trigger.cpp`") was applied by parent
`399bc85` / nested `1b6f56e` "capture: wire the (proven) Trigger into the product (link +
construct + gate)". The reason the old sentence gave is void: `build.cmd`'s mtime is now
2026-10-09T05:56:59Z, which POSTDATES all three sources it supposedly predated.

**F15.3 THE SECOND HALF OF THE CLAIM IS STILL TRUE, RE-MEASURED.** `main.cpp` never constructs a
Trigger: the only reference is the observer `main.cpp:627 Trigger* trig = replay.hotkey()`, the
rest are comments (`:566`, `:569`, `:621`) and reporting (`:638-646`). Construction belongs to
`Replay::arm()` (`main.cpp:566`) and the default is off (`:646`). So the truth is **built,
unwired, off by default** - not "unbuilt".

**F15.4 THE TWO SOURCES THAT ARE ABSENT ARE NOT THE TWO THE OLD SENTENCE NAMED, AND A THIRD IS
ABSENT THAT NEITHER SENTENCE NAMED.** 15/15 sources accounted for: 12 on the link line, 1 folded
into `main.cpp`'s OWN translation unit by `#include "audio_tap.cpp"` at `main.cpp:51`
(`audio_tap.cpp`, 1439 lines, and `main.cpp:48-50` refuses the double-main case on purpose), and
2 compiled by NOTHING - `trigger_selftest.cpp` (370 lines, its own `main()` at `:352`, so it
CANNOT be linked into the same exe) and `wasapi_audio.cpp` (1059 lines; the census of every
`.cmd/.ps1/.py/.md` reference to those two names returns 73 hits, ALL prose - AGENTS.md,
HANDOVER.md, receipts, research notes - no compile line, no `#include`). `wasapi_audio.cpp` is a
DEAD SOURCE: nothing builds it, nothing includes it.

**F15.5 ABSENCE OF A NAME IS NOT ABSENCE OF A TRANSLATION UNIT.** `audio_tap.cpp` is absent from
every compile line, and that is why the 6 warnings in `_main/_gate-audit/HONEST-BASELINE.md:48`
(read from `_main/logs/cap-build.txt.err`, binary 783865 B, mtime 2026-10-09T20:51:21Z) are
attributed to a file no compile line names. Counting it "not built" is a false negative of exactly
the shape rule 3 warns about; it is the LIVE audio path and it is compiled.

**F15.6 THE STALE CITATION IS NOT THE NESTED FILE'S ALONE.** The parent `H:/sotto/AGENTS.md:684`
cites "Its link line (`:19`)"; `build.cmd:19` today is `set SRC=%~dp0.` and the link line is
`:23`. Cause is measurable: `5f165fa fix(build): resolve build.cmd SRC/OUT from %~dp0 instead of
stale H:\aireplay junction` inserted that block and moved the link line down four lines.

**F16. `--cut-session` REFUSED EVERY FEED: A VCL GUARD HID THE SPS/PPS CAPTURE, AND A SECOND LOADER HID THE DEFECT**

Appended 2026-10-10, lane `fixcut`. Landed: lane commit `117600e` -> parent `cacc213` on
`feat/build-verify-1`. Every number below carries its population and window. No claim below
comes from reading the code where a refusal was measurable, and no cause is asserted where
only a symptom was seen.

**F16.1 THE DEFECT IS TWO UNREACHABLE LINES.** `SourceStream::load` (`main.cpp`) must hand the
muxer an `avcC` box, which needs an SPS and a PPS. At revision `92ebab41` (parent tip
`a12549d`, the lane's base; `main.cpp` 68 613 B / 1 401 lines) both captures sat INSIDE a
VCL-only guard:

    :994  const bool vcl = (ns.type == 1 || ns.type == 5);
    :999  if (vcl) {
    :1000     cur_has_vcl = true;
    :1001     if (ns.type == 5) cur_idr = true;
    :1002     if (ns.type == 7 && sps.empty()) sps.assign(...)   <-- DEAD
    :1003     if (ns.type == 8 && pps.empty()) pps.assign(...)   <-- DEAD
    :1004 }

SPS is NAL type 7 and PPS is type 8. `vcl` is true only for 1 and 5, so on every feed
`sps`/`pps` stayed empty and load() refused, text "no SPS/PPS: avcC cannot be built". Note the
trap: the predicate itself is correct in isolation - it is the guard it was nested in that
made it dead. Line numbers above are the pre-fix revision; in the landed revision (67 752 B /
1 407 lines) the guard is `:999-1002`, the two captures are `:1009-1010` under a six-line
comment, and the refusal is `:1014`.

**F16.2 THE PROOF IS A MEASURED REFUSAL, NOT AN INSPECTION.** Subject: the SHIPPED binary
`H:/sotto/_moved/aireplay/_main/build/aireplay-capture.exe`, 783 865 B, mtime
2026-10-09T20:51:21.144Z, sha256
`6CADE9A3C1D4623C6779EC4CCEA5C7CA67027FB1F2FF3AB55F3B8FA6E1A05296`. That binary was NOT
overwritten: the lane built into its own worktree. Feed `_main/src/cap-small.h264`, 746 792 B.
ARM: `--cut-session --cut-from-h264 <feed> --cut-dir <dir> --cut-fps 60
--cut-size 1920x1080`. POP: 10 cut commands written to the child's stdin pipe. WINDOW: 0.
RESULT: exit code 2, child log line "=== CUT SESSION REFUSED: no SPS/PPS: avcC cannot be
built ===", 0 clips opened, 0 cuts measured.

**F16.3 THE FEED WAS NEVER SHORT OF PARAMETER SETS.** Annex-B NAL census of
`cap-small.h264` by type: 1:298  5:2  6:1  7:2  8:2 - two SPS and two PPS are present, and
300 VCL access units. So the input was never the problem; the loader was.
CAVEAT, STATED, AND CORRECTED: this paragraph was first written the other way round - "the feed
POSTDATES the report of record" - and that is FALSE, so it is retracted here rather than left
to mislead. Measured instead: the aggregate of record starts at 17:51:04.695 -03:00
(`cap-battery-20261009-175104.txt:3`) and the feed was written at 20:52:57.985Z = 17:52:57
-03:00, i.e. 1 min 53 s INSIDE that run. The feed is that run's own fixture - generated by
`run_battery.ps1:329`, whose `$fixtures` is `_main\src` (`:41`) - so it is a SIBLING of the
instance the aggregate box-walked. Nothing here claims the two instances are byte-identical:
the battery stamps no fixture hash and neither does the report, so that cannot be proven and
is not asserted.

**F16.4 WHY THE BATTERY COULD NEVER SEE IT - TWO LOADERS, ONE FEED.** Census of
`run_battery.ps1` at the tip (blob `a84a9030`, 28 309 B / 436 lines, mtime
2026-10-09T19:51:44.179Z): the string `cut-session` occurs 0 times, `cut-from-h264` 3 times -
three mux arms at `:260` (the mux row), `:319` (junk feed) and `:334` (small feed), and not
one of them passes `--cut-session`. Every one takes the ONE-SHOT arm, dispatched at
`main.cpp:1340-1347` -> `:1397` `rep.cut_from_h264(...)`, and that path parses the feed with
`extract_sps_pps()` (`replay.cpp:248-257`), which performs the same two assignments with NO
vcl guard. One feed, two Annex-B loaders, and the battery only ever exercised the correct one.
`--cut-session` is the arm the press-to-clip instrument runs, so the three green mux arms said
nothing about the path that was broken.

**F16.5 A SECOND REFUSAL ON THE SAME FEED, WHICH IS NOT A NEW DEFECT.** The one-shot arm
cannot mux this feed at all. Replaying the battery's own arm shape from `:334` verbatim on the
shipped exe gives exit code 2 and "OFFLINE CUT FAILED: ring capacity below 16 MiB -- that
cannot hold a cuttable window" (the dash is an em dash in the source, written `--` here).
The guard is `ring_buffer.cpp:78` `if (capacity_bytes < (16u << 20))`, and
`run_battery.ps1:326-342` is a DELIBERATE refusal row for exactly this - its own note calls it
"the ring floor: a MEASURED refusal that explains itself". So on this feed the one-shot arm
refuses BY DESIGN and the session arm refused BY DEFECT: the only arm that could have shown
the SPS/PPS defect is the one nothing runs.

**F16.6 AFTER THE FIX, MEASURED.** Lane `fixcut` (branch `feat/cut-session-spspps`, base
`a12549d`) hoists the two captures out of the guard to loop-body level, keeping
`if (vcl) { cur_has_vcl = true; if (ns.type == 5) cur_idr = true; }` intact. Built with
`build.cmd`'s own 12-source link line, TMPDIR `I:/cc-tmp`, into the worktree's own
`_main\build`. SAME arm, SAME feed, child exit code 0:

    === CUT SESSION: feed=.../cap-small.h264 aus=300 sps=23B pps=4B fps=60 ===
    commands_served=10  cuts_sent=10  clips_opened=11  clips_closed=6
    cuts_refused=5  cuts_executed=5  frames_written=590  bytes_written=1456669
    largest_clip_bytes=354474

Before: 0 clips, exit 2, no parameter sets. After: 6 clips, 590 frames, 1 456 669 B, exit 0,
largest surviving clip 354 474 B - a real, sized file.

**F16.7 WHAT THE FIX DOES NOT BUY - RECORDED, CAUSES UNKNOWN.** The p95 instrument on the same
run still reports `VERDICT RED` with exit code 1, which IS its own contract (0 green, 1 red, 2
the instrument could not measure). Four facts, each with its window, none explained here:

  PA: 10 cuts requested in one run of the p95 probe (child stdout, cadence 150 ms).
  - 5 of 10 were REFUSED BY THE SESSION: `"cut":false,"ok":false,"closed_frames":0`. The odd
    cuts executed (19 / 84 / 99 / 114 / 129 frames closed) and the even ones were refused.
    n=1, so an alternating OBSERVATION, not a law, and not attributed here.
  - 5 clips did not pass the instrument's moov-last box walk inside its 5 000 ms window
    (last observed state `chain-ok-last-is-mdat`). "Every clip opened" is therefore FALSE.
  - `aus_waited_for_idr=1005` on a 300-AU feed: the session waited for an IDR more AUs than
    the feed contains, so it re-scanned. Mechanism UNKNOWN, not guessed.
  - `SUMMARY n=5 p50=1,249ms p95=28,542ms max=28,542ms floor=1,166ms pollHz=858,0` - the five
    executed cuts only. The p95 is 23x the p50, which the residual refusals do not explain.

**F16.8 ONE INSTRUMENT DEFECT, RECORDED BEFORE SOMEONE CITES IT AS PRODUCT BEHAVIOUR.** The
FIRST smoke run (the one that measured the refusal in F16.2) printed the word `VERDICT RED`
over exit code 2, although the probe's own contract names 2 as "could not measure a single
cut". The second run printed `VERDICT RED` over rc=1, which IS consistent. So the FAIL branch
lost its reason string in the first run and a subject that REFUSED was labelled red instead
of not-measured. The exit code is the verdict; the word is decoration. No owner question
opens on this: it is a defect in `press-to-clip-probe.ps1`, to repair or drop by its owner.

**F16.9 AN INHERITED CITATION WITH NO HOME - RETRACTED, NOT CARRIED FORWARD.** The note this
lane opened from asserted that the report of record cites `run_battery.ps1  78be872c  mtime:
2026-10-09T19:44:07-03:00`. That is a PRESENCE claim, and the instrument for a presence claim is
a grep, so it was run instead of repeated:

  PA: the string `78be872` over `_moved/aireplay`. PA: the string `19:44` over the same tree.
  WINDOW: one grep each, 2026-10-10.
    - `78be872` returns exactly ONE match - this paragraph. Nothing else in the tree has it.
    - `19:44` returns TWO matches: this one, and an unrelated `_lane16-census5.out.txt:96`
      cron line from 2026-10-05.
    - `run_battery\.ps1` followed by 7-40 hex chars over `_main` returns ZERO matches.
    - HONEST-BASELINE section 3 (lines 38-52, the BUILD RESULT) names `run_battery.ps1`
      exactly once, at `:18`, as the command that reproduces the aggregate - with no hash, no
      size and no mtime row for the SCRIPT anywhere in that file.

The report of record as it exists NOW: 13 066 B / 200 lines / mtime 2026-10-09T23:20:34.686Z,
and its aggregate header (`cap-battery-20261009-175104.txt:3-7`) stamps no script sha either.
So the inherited assertion was itself a claim without a home - rule 3 of AGENTS.md applied to
an audit note, not only to a product claim. What IS measured, for whoever needs it:
`run_battery.ps1` = 28 309 B / 436 lines / mtime 2026-10-09T19:51:44.179Z / blob `a84a9030`,
and the three mux arms with no `--cut-session` (F16.4) were re-measured this session and hold.


**F16.10 THE JUNK ARM'S RED REASON IS THE RING FLOOR, NOT THE JUNK.** PA: the RED arm at
`run_battery.ps1:316-324`. It writes `_main\src\cap-junk-not-h264.bin` - the literal 37
bytes x 64 = 2 368 B at `:317` - feeds it to `--cut-from-h264` with `--cut-size 1920x1080`, and
takes the `FAILED` line out of the child log. POP: 1 arm, 1 run. The run of record measured the
message: `_main/logs/cap-mux-small.txt:7` (the small arm) and the aggregate rows `:136` (junk)
and `:137` (small) all read "ring capacity below 16 MiB -- that cannot hold a cuttable window",
the two aggregate rows byte-identical apart from their labels. A 2 368 B feed cannot reach the
H.264 parser at all - the guard at `ring_buffer.cpp:78` fires first. So this arm returns the
rc it is expected to return (2) for a reason that never names the feed, and its own note, "a
refused input is what makes the green rows above worth anything" (`:324`), rests on an arm that
proves only "small things are refused". Recorded as a defect in the RED arm's generator, with
no owner question attached; the obvious repair is to size the junk fixture above the 16 MiB
floor, or to add an explicit ring-capacity override to the one-shot path (none exists today:
`main.cpp` parses no `--ring` flag).

**F17. THE F15 CENSUS IS REFUTED BY THE REPO'S OWN GATE SCRIPTS: THE F15 REVIEWER RETURNS "NO" ON `a12549d`**

POPULATION: the 15 `.cpp` under `src/capture`; every `.cmd` / `.ps1` / `.py` / `.md` under
`H:/sotto/_moved/aireplay`, recursive = 843 files (32 `.cmd`, 98 `.ps1`, 331 `.py`, 382 `.md`).
WINDOW: commit `a12549d` for the build-side facts (`build.cmd`, `main.cpp`); the WORKING TREE for
the `.ps1` and artefact facts, which the parent repo does not track and which are unchanged;
reviewer `d6853873-7aed-468d-8a5c-b89412188bb6`, READ-ONLY - no compiler invoked, no lane or probe
run, no file written under `H:/sotto` or `H:/sotto-wt`, no git write. Measured 2026-10-10.

**F17.1 THE VERDICT.** The F15 documents lane, parent commit `a12549d` (subject: "F15 - the Trigger
IS on the build link line; wasapi_audio.cpp is compiled by nothing"), was reviewed and returned
**VERDICT: NO**. Score 4 of 5 claims PASS. Claim 3 - the census and its "compiled by NOTHING" /
"DEAD SOURCE" wording - is NO, and it is the load-bearing claim: **the commit's own subject line
is one of the false sentences.** This section does not delete anything F15 asserted; it names the
five sentences that are FALSE and records what is measured instead.

**F17.2 WHAT SURVIVES THE REVIEW, AND IT IS MOST OF IT.** `build.cmd:23` is 483 characters / 483
UTF-8 bytes / ASCII-only and carries exactly 12 `.cpp` (main, common, d3d11_ctx, nv12_convert,
wgc_capture, nvenc_encoder, ring_buffer, mp4_writer, selftest, test_window, **trigger**, replay -
trigger is the 11th); the compiler is mingw-w64 g++ 15.2.0 (`build.cmd:3`, `GXX` at `:7`);
`main.cpp` never constructs a Trigger - zero `new Trigger` in the file, and the three code lines
that name the type are `:627` the declaration, `:629` the two static calls and `:633` the reporting;
`:627 Trigger* trig = replay.hotkey()` is exact and it is an OBSERVER, because `replay.hotkey()`
returns a pointer owned by the `Replay` instance; the sole construction anywhere in the tree is
`replay.cpp:558` `trigger_.reset(new Trigger())` inside `Replay::arm_hotkey()`, reached from `:433`
only after the law-6 gate at `:407-408` with `gate_passed_ = true` at `:412`; the default is off at
`main.cpp:140` and reported at `:646`. `audio_tap.cpp` (1 438 LF / 1 439 elements) is folded into
`main.cpp`'s OWN translation unit at `main.cpp:51`, with `main.cpp:48-49` refusing the double-main
case on purpose; `trigger_selftest.cpp` is 369 LF / 370 elements with its own `int main(argc, argv)`
at `:352`; `wasapi_audio.cpp` is 1 058 LF / 1 059 elements and contains no `int main`; 12 + 1 + 2 =
15. The engineering conclusion **built, unwired, off by default - not "unbuilt"** stands, and so
do the F15 law and both citations of Claim 5.

**F17.3 THE FIVE SENTENCES THAT ARE FALSE, AND WHAT IS MEASURED INSTEAD.**

  FALSE: "2 are compiled by NOTHING".
  FALSE: "the census of every `.cmd/.ps1/.py/.md` reference to those two names returns 73 hits, ALL
         prose - no compile line, no `#include`".
  FALSE: "`wasapi_audio.cpp` is a DEAD SOURCE: nothing builds it, nothing includes it."
  FALSE: "THE TWO SOURCES ABSENT FROM THE LINK LINE ARE NOT THE TWO THE OLD SENTENCE NAMED."
  FALSE: the commit subject, "`wasapi_audio.cpp` is compiled by nothing".

  WHAT IS TRUE INSTEAD:

  (1) `trigger_selftest.cpp` is COMPILED AND LINKED AND IT RAN. `_main/_lane1-trigger-gate.ps1`
      names it in `$myFiles` at `:45`, appends it to `$all` at `:54`, and invokes `$gxx` with it at
      `:58-59`; the `BuildSelftest` function is declared at `:50` and called from `:116`, `:128` and
      `:161`. It was executed, not merely compiled: `_main/build/aireplay-trigger-selftest.exe`
      846 850 B, mtime 2026-10-07T23:57:59Z, and `_main/build/lane1-trigger-selftest.log` 2 343 B,
      mtime 2026-10-09T06:18:20Z, whose head carries the selftest's own runtime output
      "TRIGGER key=F10 vk=0x79 ... registered=yes polled=true" and
      "TRIGGER arm: 9 key(s), 6 registered, 3 polled-only".

  (2) `wasapi_audio.cpp` is COMPILED TO AN OBJECT AND LINKED. `_main/_lane2-audio-gate.ps1` runs
      `& $gxx @flags @incs -c "$src\wasapi_audio.cpp" -o $objA @libs` at `:82` and
      `& $gxx @flags @incs "$src\wasapi_audio.cpp" "$src\common.cpp" $mainCpp -o $exeLive @libs`
      at `:335`. Artefacts on disk, read-only: `_main/build/wasapi_audio.obj` 117 935 B
      2026-10-07T15:20:51Z; `_main/build/lane2-gate/wasapi_audio.obj` 118 274 B
      2026-10-08T00:03:19Z; `_main/build/lane2-audio-probe.exe` 2 047 568 B 2026-10-07T15:39:56Z;
      `_main/build/lane2-gate/lane2-audio-probe.exe` and the control directory's
      `lane2-audio-probe-CONTROL.exe`; `_main/build/wasapi_audio.cpp.PRISTINE` 47 739 B. A
      `.PRISTINE` copy plus a `control\` directory is the shape of a lane that ran BOTH colours.
      It is not the shape of a dead file.

  (3) THE CENSUS, MEASURED INSTEAD OF ASSERTED. Pattern
      `wasapi_audio[.]cpp|trigger_selftest[.]cpp` over the 843-file population gives **59 lines /
      68 occurrences**. By extension: `.cmd` 0 / 0, `.ps1` 8 / 8, `.py` 2 / 2, `.md` 49 / 58. By
      subtree: `_main` 28 / 32, `receipts` 15 / 19, `research` 8 / 8, `runs` 2 / 2, root 6 / 7. The
      counts are identical with the control copies included and excluded. "73 hits" appears in no
      nearby window: the two names at any extension are 132 lines / 147 occurrences; adding
      `audio_tap.cpp` gives 77 / 87; adding `trigger.cpp` gives 285 / 327. And "none a build line"
      is FALSE - of the 8 `.ps1` lines, 4 are build machinery and 2 are the compiler command line
      itself (`:82` compiles, `:335` links). The 2 `.py` lines (`_main/_rv-absent.py:40`,
      `_main/_rv-cite.py:16`) are indeed prose, and there are 0 `.cmd` lines.

  (4) THREE names are absent from the link line, not two - `audio_tap.cpp` is the third, and it is
      folded, so the two NON-folded absent names (`trigger_selftest.cpp`, `wasapi_audio.cpp`) ARE
      the two the old sentence named. The genuinely new facts are that `trigger.cpp` is now ON the
      line and `audio_tap.cpp` is folded in.

  CORRECTED SENTENCE, offered as the replacement for the five above: *Of the 15 `.cpp`, 12 are on
  the link line, 1 is folded into `main.cpp`'s own translation unit, and 2 are not on the line -
  but both of those are compiled elsewhere, `trigger_selftest.cpp` by `_lane1-trigger-gate.ps1`
  and `wasapi_audio.cpp` by `_lane2-audio-gate.ps1` (compile `:82`, link `:335`). `wasapi_audio.cpp`
  is OFF THE PRODUCT LINK LINE, which is the defect `receipt-29-agents-truth.md:63` wanted fixed
  and did not: that receipt prescribed appending BOTH `%SRC%\trigger.cpp` AND
  `%SRC%\wasapi_audio.cpp`, and only the first landed (parent `399bc85`, nested `1b6f56e`).
  `wasapi_audio.cpp` is therefore UNWIRED, not dead - and it is no longer claimed to be either.*

**F17.4 TWO NUMBER DEFECTS, NEITHER FATAL TO THE CONCLUSION.** (a) `main.cpp` is asserted as
"1401 lines" in F15's population line and again in the claim text. Unreproducible in either
window: 1 400 elements / 1 399 LF with no trailing newline at the commit, 1 406 by
`Get-Content -Count` and by `System.IO.File.ReadAllLines().Count` in the tree today (the LF+1
convention gives 1 400, not 1 401). (b) "the only reference" at `:627` is loose - three code
lines name the type and none of them constructs or deletes an object. Every line number F15 cites
(`:566`, `:627`, `:646`) is still exact in the working tree.

**F17.5 THE TRANSFERABLE PART, AND THE IRONY IT COST.** F15.5 argues - correctly, and it passes -
that *absence of a NAME is not evidence of absence of a TRANSLATION UNIT*, citing the six warnings
in `_main/_gate-audit/HONEST-BASELINE.md:48` which are attributed to a file no compile line names.
F15.4, three paragraphs above it in the same landed section, commits exactly that error: the
census of names across `.cmd/.ps1/.py/.md` found no compile line, and a translation unit that
two `.ps1` gates compile, link, run and keep a control copy of - was pronounced dead. The
instrument was right about names and wrong about units. The lesson is not "grep harder"; it is
that a census whose population is the FILES you can name cannot answer for the files you cannot,
and an artefact on disk with a mtime inside the lane's own run window is louder evidence than any
absence. Note also that this error was found by a READ-ONLY reviewer that invoked no compiler:
the `.ps1` text and the build directory were enough, which means it could have been caught before
`a12549d` landed.

**F17.6 OPEN AFTER THIS REVIEW, AND NOT BY THIS SECTION.** `wasapi_audio.cpp` is still off the
product link line. This section refuses to decide whether it SHOULD be on it: that is
`receipt-29-agents-truth.md:63`'s prescription and it is recorded as UNVERIFIED here, not argued.
No owner question is opened by this section; it records a refuted claim, a corrected sentence and
an artefact census.
**F18. THE WGC CONTRADICTION IS RECONCILED - MEASURED 2026-10-10. THE BOX DOES NOT REFUSE CAPTURE:
EVERY EXECUTABLE IMAGE UNDER `H:\sotto` CARRIES THE S-1-16-4096 LOW MANDATORY LABEL, AND A
LOW-IL PROCESS CANNOT CREATE A CAPTURE ITEM.**

Receipt, the only artefact that decides this section:
`_main/receipts/receipt-29-review-wgc-instrument-contradiction.md` (59 465 B, sha256 `733E50C9...`,
measured 2026-10-10). It was produced by a read-only lane that honoured `DO-NOT-RUN.md`, invoked no
battery and no `run_battery.ps1`, created no capture session (`CreateForWindow` / `CreateForMonitor`
ONLY - zero `CreateCaptureSession` and zero `StartCapture` in either source), built nothing, wrote no
git ref, and confined its writes to `I:/cc-tmp` and `_main/receipts`. Its own window census, 81 samples
at a 100 ms cadence, saw 0 consoles.

**F18.1 THE ANSWER, IN THE FORM THE LEDGER ASKED FOR.** DEBT-LEDGER D-H1-MEDIUMIL asks "the cause of
the WGC refusal is therefore UNRECONCILED, not MEASURED-and-neutralised". It is now MEASURED, and the
measurement says: **this box does NOT refuse WGC capture.** Instrument B's number, `S_OK = 0x00000000`,
is the truth of this box.

**F18.2 THE MECHANISM.** Every image under `H:\sotto` carries the `S-1-16-4096` Low mandatory label,
explicit at the `H:\sotto` root and inherited by everything below it. An image so labelled is launched
as a **LOW-IL process**, and in a LOW-IL process Windows refuses WGC ITEM CREATION for every target
owned at MEDIUM/HIGH: `CreateForWindow` on all 4 windows the probe names, `CreateForMonitor`, and the
process's own window. That is instrument A's 5-of-5 `E_ACCESSDENIED 0x80070005` in full, with no
access-denied-on-the-display, no OS setting and no box change anywhere in it.

**F18.3 SAME BYTES, TWO POPULATIONS - AND THE LABEL FOLLOWS THE FILE OBJECT, NOT THE PATH.** A's own
image, byte-identical, run from outside `H:\sotto`: **5 of 5 `S_OK`** (`A_wgcunb` 2026-10-09T23:51:58Z,
and arms `E04` / `E05` / `E06` / `E18`). The identical image run from inside `H:\sotto`: **5 of 5
`0x80070005`** (`A_product`, arms `E01`-`E03`, `E09`, `E10`, `E13`, `E14`). The reverse direction was
measured on the reviewer's own scratch copies only: remove the label -> `S_OK` (`C2`); add it ->
`0x80070005` (`D2` / `D3`). The decisive single-binary test is `E15`: **B's OWN bytes, run at LOW IL,**
returned `0x80070005` on every ARM, in a run whose HIGH-IL predecessor on the same bytes returned
`S_OK`. B's numbers were true of the box, not of the binary; A's were true of the label, not of the
box. The `E13` junction earned its paragraph: A's own object launched through `I:\cc-tmp\f13-2\jprod`
- an `I:` path STRING, junctioned to `H:\sotto\_moved\aireplay\_main` - was still denied. The label
is carried by the FILE OBJECT the linker resolves, not by the text of the path.

**F18.4 RULED OUT BY MEASUREMENT, EACH ONE NAMED.** byte difference, run order, token elevation, the
embedded manifest, the PE subsystem, the session/desktop, `IsSupported`, and the path string. The
per-token and per-machine scope of the label was not measured, and neither was MEDIUM IL nor SYSTEM -
both are named as unknown rather than folded into the answer.

**F18.5 WHAT IS ASSERTED PLAINLY AS NOT KNOWN (this is the honest part of the section).**
`GraphicsCaptureAccessStatus` is **never read by either instrument** - B's GREEN arm resolved
`Completed` with `errorCode 0x0` and was THEN denied, so neither probe can report the consent state at
all. Whether a consent dialog ever appeared was not observed. Who set the label was not established.
And A's `RequestAccessAsync` claim is ATTRIBUTED to A's own comments; it is not a measurement.

**F18.6 WHAT THIS RETIRES, AND WHAT IT DOES NOT.** It retires D-H1-MEDIUMIL's closing task - "the task
before any H1 activation is now to reconcile the two WGC binaries under one set of conditions - not to
change the machine" - because that reconciliation is now done, and it retires the inference that a
genuine MEDIUM-IL capture process might be required: **a HIGH-IL process from an unlabelled image
measured `S_OK`**, so medium IL is not on the critical path on the strength of the same numbers that
convict the label. It does NOT retire the D-H1-MEDIUMIL RECOMMENDATION to leave the machine alone:
that recommendation now stands on exactly the ground it was already on when the reason fell away - a
re-logon would tear down every live lane of both waves, the 3-minute wake loop and the audit trail
mid-flight. Both halves stay in the ledger; neither is rewritten.

**F18.7 THE OPERATIVE CONSEQUENCE, FOR ANY LANE THAT WANTS TO MEASURE WGC.** Instrument A, as built
and as labelled, cannot measure WGC on this box - not because the box refuses, but because the
instrument refuses itself. Re-run it from an **unlabelled copy on `I:`** or from `H:\sotto-wt\...`,
and expect `S_OK`; expect `E_ACCESSDENIED` from anything under `H:\sotto`. This is also the first
trap in this file that a whole-class of future instruments would otherwise walk into.

**F18.8 AN HONEST BOUND RECEIPT-29 STATES AND THIS SECTION DID NOT: NO FRAME WAS EVER CAPTURED.**
F18.1 says "this box does NOT refuse WGC capture", and the measured predicate is narrower than that
sentence reads. Out of scope for the reconciler by its own design, and therefore UNMEASURED:
`CreateCaptureSession`, `StartCapture`, and anything that opens a GPU encoder, a camera or a microphone.
Every number in F18 is a number about ITEM CREATION. Receipt-29 sec.12 states it plainly - "whether
`S_OK` at `CreateForWindow` is sufficient for a working capture path is UNKNOWN from these measurements
alone" - and labels its own surrogate as a surrogate, not a proof: in every `0x00000000` case both
instruments print a non-null `item=` COM pointer, in every `0x80070005` case the pointer is exactly
zero (population: E18 and E07 non-null on all five targets; E01/E02/E03/E06/E09/E10 null). **So read F18
as "the box does not refuse WGC ITEM CREATION, and the refusal in circulation was the label". A working
capture path on this box is still UNKNOWN, and no artifact in this repo has yet produced a frame.**
Two further bounds from the same receipt, both load-bearing for whoever measures next: the label was
partly MOVED by the reviewer to prove causality - a constructed experiment, symmetrical in both
directions, mitigated by measuring the original untouched state first (F18.3 already says the reverse
direction was measured on scratch copies only); and the MEDIUM and SYSTEM IL neighbours were not
reached at all (no linked token), so every conclusion here is bounded to {LOW: `0x80070005`, HIGH:
`0x00000000`} on ONE host and ONE elevated admin account (`EnableLUA=0`).

**F19. THE F16 CODE REVIEWER RETURNS PASS-WITH-DEFECTS ON `cacc213` - AND FIVE OF ITS SIX DEFECTS ARE
THE AUDIT'S OWN NUMBERS, NOT THE SHIPPED CODE.**

Verdict written by the lane dispatched for L17, delivered 2026-10-10 to `I:/cc-tmp/review-f16-code/
` as `verdict.md` (15 943 B / 279 LF lines, pure ASCII) and `verdict-message.md` (16 747 B / 292 LF
lines, the delivery copy, which records that its own `send_message` to the parent was REJECTED -
`ToolCallError: subagent ... is unavailable` - twice, with `list_agents` returning empty for both
children and descendants. Delivery-by-file instead of delivery-by-message is recorded here as the
reason this verdict reached the ledger at all).

**F19.1 SUBJECT AND DIFF.** `cacc21338c520d5bba1b01bd73e2ef193dba6acf` = lane commit `117600e` = landing
`a172a95`. One file, `_moved/aireplay/src/capture/main.cpp`, **8 insertions / 2 deletions.** The hunk is
`@@ -999,9 +999,15 @@`; the only removals are the pre-fix `:1002-1003` captures, the only additions are a 6-line
comment and the same two statements at `:1009-1010`. Lines 1-998 are untouched.

**F19.2 THE DEFECT WAS REAL - PROVEN ON THE PRE-FIX BYTES, BY REBUILDING THEM.** The reviewer rebuilt
blob `92ebab41` (67 213 B / 1 400 LF lines) with g++ 15.2.0 mingw, rc=0, and ran
`--cut-session --cut-from-h264 cap-small.h264 --cut-fps 60 --cut-size 320x180` with 10 cuts paced
2 600 ms apart over a stdin PIPE: **exit 2**, stdout 63 B exactly
`=== CUT SESSION REFUSED: no SPS/PPS: avcC cannot be built ===`, stderr 0 B, **0 clip files.** So the
two assignments really were dead code, and the refusal message that only a fix could reach really was
unreachable before it. That is the strongest form this finding can take.

**F19.3 WHY THE BATTERY WAS BLIND - CONFIRMED.** `run_battery.ps1` blob `a84a9030`: `--cut-session` = 0,
`cut-session` = 0, `--cut-from-h264` = 3. `extract_sps_pts` (`replay.cpp:248-257`) has no vcl guard;
`ring_seed_from_h264` carries the idiom but captures nothing; the battery's only use of this feed is
the deliberate ring-floor row at `:327-343`. A 0-count is a claim with a shelf life, and the
shelf-life here is short.

**F19.4 THE FIX ITSELF, AND WHY IT IS EXACTLY A HOIST.** `ps` (`:995`) and the two-disjunct flush
(`:996`) are **byte-identical pre and post**, and the hunk starts at `:999` - so any framing that
presents them as new is false. The reviewer's control over all 305 NALs, on its own `annexb_split`
replica: with vs without the `ps` disjunct -> **identical** 300 AUs / 2 IDR AUs / sps 23 B / pps 4 B /
histogram `{1:298,3:1,4:1}`; the disjunct fires exactly once (a mid-stream SPS at NAL 253) and makes
AU[250] into `[7,8,5]`. AUD type 9 is **UNTESTABLE** on this feed (census of type 9 = 0), so the
`ps` list carrying it is unexercised rather than wrong. `cur_has_vcl` is still assigned only inside
`if (vcl)` (post `:1000`) and `cur_idr` at `:1001`; only `sps`/`pps` moved. Non-regression:
`replay.cpp` blob `88f023ca` is identical at all three revisions, and both binaries on the one-shot arm
-> exit 2, identical 522 B stdout, `OFFLINE CUT FAILED: ring capacity below 16 MiB`.

**F19.5 AFTER THE FIX, MEASURED BY THE REVIEWER.** Post build sha256-16 `9A4AB2D7F5DBD790`, same arm
and feed, 10 cuts 2 600 ms apart: **exit 0**, `aus=300 sps=23B pps=4B fps=60`, **6 clips MP4-OK**
(386 839 / 344 302 / 299 594 / 255 521 / 220 157 / 181 494 B), 5 refusals, and 5 ftyp-only 40 B stubs
(`bad box 'mdat' size=0 at 32`), with `frames_written=686 bytes_written=1687907 largest=386839
aus_waited_for_idr=1064`. The same binary at burst cadence (411 ms) gave 1 executed cut / 4 frames /
14 099 B. **So every total is cadence-set**: `session_feeder` loops 300 AUs at 16 ms and the cut
count is the clock, not the data.

**F19.6 THE SIX DEFECTS. NONE OF THEM IS IN THE SHIPPED BEHAVIOUR.**
1. **F16.1 (audit text, ALREADY RECORDED).** F16.1 quotes the pre-fix `main.cpp` as "68 613 B / 1 401
   lines" - that is the CRLF worktree render; blob `92ebab41` is **67 213 B / 1 400 LF lines**. The
   file **GROWS** 539 B / 6 lines, it does not shrink 861 B. This is the defect already recorded in
   ledger row L17 by an earlier measurement (`bad9fd9`); an independent rebuild confirms it.
   Appended, not rewritten - F16.1 stays as landed and this is its correction.
2. **F16.9 (audit text, NOT YET RECORDED).** F16.9 quotes `run_battery.ps1` as "28 309 B / 436 lines" -
   the same CRLF-vs-blob confusion applied to a second file. Blob `a84a9030` is **27 874 B / 435 LF
   lines.** The pattern, not the accident, is the finding: this file has now miscounted bytes the same
   way in two different sections, which means the "measure the blob, never the worktree" rule is not
   yet a habit here.
3. **THE FRAMING (audit text).** `ps` and the two-disjunct flush are presented as new. They are
   pre-identical at `:995`/`:996` and the hunk starts at `:999`. The fix IS the hoist - two statements -
   which is why it is safe, and which is why the 6-line comment that landed with it carries more of
   the value than the code does.
4. **A CLAIM THAT WAS NOT A FIXED MEASUREMENT.** "590 frames / 1 456 669 B / largest 354 474 B" belongs
   to the LANE'S 150 ms cadence. Burst gave 1 / 4 / 14 099; 2 600 ms gave 6 / 686 / 1 687 907. Recorded
   in L17 as UNRECONCILED, that UNRECONCILED label is now RETIRED in favour of the sharper sentence:
   **both sides were correct of different cadences, and the audit did not name a cadence.**
5. **A PRODUCT RESIDUAL, PRE-EXISTING, AND NEW TO THIS FILE.** A cut with no IDR in front of it leaves a
   40-byte ftyp-only stub (5 of 11 files), with `bad box 'mdat' size=0 at 32`. Cause UNKNOWN, and the
   lane says so itself. Not fixed, not argued, and not blame for the fix that exposed it.
6. **AN INSTRUMENT DEFECT, NAMED IN F16.8 AND NOW CONFIRMED.** `press-to-clip-probe.ps1` printed
   `VERDICT RED` over exit code 2 - its own contract's "could not measure a single cut". An instrument
   whose own failure is indistinguishable from its subject's failure.

**F19.7 THE TRANSFERABLE PART.** The instrument that decided this section was a REBUILD OF THE PRE-FIX
BLOB - available to anyone who could name the blob, before the audit section was written, exactly as the
read-only `.ps1` + build-directory review was available before `a12549d` landed (F17.5). Two of the last
three errors in this file were caught by an instrument that existed first and was run second. The rule
that follows is narrower than "measure more": **when a lane claims a defect, ask what the pre-fix bytes
did - if the answer is not a rebuild, the claim is a reading.**

**F19.8 RULE 4.** L17 now has its reviewer row: PASS-WITH-DEFECTS, on the landed code. The defects are
this file's, and they are recorded above rather than deleted from F16.


## CORRECTIONS 2026-10-10 - appended after bf845e30, append-only, nothing above rewritten

This section follows the file's own idiom: F19.6 items 1 and 2 correct F16.1 and F16.9 by
APPENDING, because an audit that edits its own record has no record. The cadence that F16.6/F16.7
never named is named here.

### (d) THE F16.6/F16.7 NUMBERS HAVE NO SURVIVING LOG

PA: `git grep` for `p50=1,249ms`, `p95=28,542ms`, `aus_waited_for_idr=1005` and the
"5 of 10" refusal count, plus F16.9's measurement of the report of record itself (13 066 B / 200
lines, mtime 2026-10-09T23:20:34.686Z, aggregate header `cap-battery-20261009-175104.txt:3-7`
stamping no script sha). POP: the four F16.7 facts. WINDOW: 2026-10-10, HEAD `bf845e30`.

RESULT: those numbers survive ONLY as the sentences at 624-633. No log behind them is in the tree.
They may be quoted as "what a run once reported", never as "the state of the instrument".

### (e) F16.8 IS CLOSED, NOT DROPPED - D0 WAS REPAIRED

The defect F16.8 named (the first smoke run printed `VERDICT RED` over exit code 2, the probe's own
contract's "could not measure a single cut", so an instrument's own failure looked like its
subject's failure) was repaired in `c72268cc`, which landed
`_main/_p95-instrument/press-to-clip-probe.ps1` and its `.red.ps1`. PA: the landed probe's bytes
at 584-589, which now print `VERDICT FAIL`, a `REASON: no cut produced a measurable delta` line,
a `HALF A (keypress -> cut decision) remains UNKNOWN` line and `exit 2`. The exit code is the
verdict, and the word now agrees with it. No owner question opens on this and none did then.

### (f) ON THE OLD WORDING - RECORDED WITHOUT A CADENCE

F16.6 (606-618) and F16.7 (620-633) make cadence-free claims: "6 clips, 590 frames, 1 456 669 B,
largest 354 474 B" and "p95 28 542 ms is 23x the p50". The reviewer's own re-measurement at other
cadences (F19.5, 917-921: 6 clips, 686 frames, 1 687 907 B, `aus_waited_for_idr=1064` at
2 600 ms; burst 411 ms giving 1 cut / 4 frames / 14 099 B) shows every total is cadence-set -
`session_feeder` loops 300 AUs at 16 ms and the cut count is the clock, not the data (line 922).
So those numbers are not wrong; they are UNNAMED. They cannot be compared to anything and must not
be quoted as product behaviour. The paragraphs above stay exactly as landed.

### (g) THE AUDIO PEAK/RMS ANOMALY - 3 OF 4 NON-SILENT ARMS, CAUSE UNKNOWN

PA: the L7 gate logs in `I:/cc-tmp/l7-gate/`. POP: every arm that reported a `level` pair.
WINDOW: the L7 four-colour arm gate, 2026-10-10.

| log | line | arm | peak | rms |
|---|---|---|---|---|
| `capture2.out.log` | 65 | GREEN1 | 0.837463 | 0.000000 |
| `g3-cap.log` | 66 | GREEN3 | 0.871136 | 0.000000 |
| `r6-cap.log` | 62 | RED6b | 0.000000 | 0.000000 |
| `r7-cap.log` | 58 | RED7 | 0.428103 | 0.000000 |

Three non-zero peaks against a zero RMS, and one arm where both are zero. A real signal cannot have
a peak without an RMS, and the pair is emitted by the same report in `audio_tap.cpp`. Mechanism
UNKNOWN, not guessed; carried as an open instrument defect.

### (h) F13.2 IS RESOLVED - THE CAUSE IS MANDATORY INTEGRITY LEVEL

F13.2 (427-446) recorded the alternative as open: "build-time (manifest / integrity level) or
run-time (session, input desktop, concurrent capture holder), and this audit has not measured
which".

PA: ONE merged binary, ONE argv, ONE box, TWO run locations, with `icacls` as the IL instrument -
`Get-Acl` / `File::GetAccessControl` return the DACL only and so report a false NO-LABEL (its
pt-BR output renders as mojibake, `Rotulo Obrigatorio\Nivel Obrigatorio Baixo:(I)(NW)`, so any IL
probe must also be validated against a known-LOW control). POP: the same executable run from
`H:/sotto` and from `H:/sotto-wt/audioclip/_merged-gate/`. WINDOW: 2026-10-10.

- under `H:/sotto` (LOW, `S-1-16-4096`): `CreateForWindow failed 0x80070005`, EXIT=2, 0 frames,
  wall 1 682 ms.
- under `H:/sotto-wt/audioclip/_merged-gate/` (NO label => MEDIUM): EXIT=0, full capture.

CONSEQUENCE FOR EVERY FUTURE CAPTURE GATE: run the binary from a MEDIUM-IL path, never from under
`H:/sotto`.

Any earlier sentence in this file type that said the low-IL premise "was refuted" was an artifact of
that broken DACL-only instrument: it could not see the mandatory label at all, so it reported
NO-LABEL for a path that is LOW. Carried with it, unchanged: the stale comment at
`src/capture/main.cpp:183-184` ("WGC refuses every capture item on this host") is false in the
merged binary at HEAD, and it is left to the lane that owns that file.

### (i) THE F13.2 CENSUS LINE NAMES A DEAD LANE TIP

Line 229 records `engproc  feat/engine-process  @0e1b7f5 ahead=1  dirty=0   (10 files +3289,
engine/)`. `0e1b7f5b2806a48a92dcfbe3841cd01f812652c6` exists (LANE A's first commit, parent
`399bc851`) but it is no longer the lane's tip. PA: `git diff --numstat 0e1b7f5 faffdd609`.
RESULT: `src/engine/engine.py` +340 -12, `src/engine/test_engine.py` +311 -30,
`src/engine/ui_child.py` +184 -77, and three `_engine-audit-battery-v2*` instruments +354. The
spec-07 text written against `0e1b7f5` describes an engine that has since grown by 340 added lines
of shipped behaviour.

### (j) ODS1 / ARM B - A CONTRADICTION CARRIED AS UNKNOWN, WITH ITS POPULATION

PA: `_main/_lease-audit/armA-report.md` and `armB-report.md`, both landed in ODS1 (tree
`7395ebae7f0e5f84ef3ca4c008a131f492f55b4d`). POP: `H:/sotto/_moved/aireplay/_main/_lane22-run`
(99 `clip.mp4`, 98 `key.json`, 0 `.db`). WINDOW: 2026-10-10, 10 runs - rc=1 in all of them,
which is the instrument's own contract.

The contradiction, stated without resolving it: Arm B counts 95/95 keys self-contradictory
(`usable_keys 95, violators 95, tolerance_ms 1`) and 99/99 clips carrying neither `ftyp` nor
`moov` (`.terminal R-NO-MOOV 98 / R-NO-FTYP 1`), so every clip has no duration. C01 overlaps 621
clips in one store; the duration histogram is
`{1000:7, 1001:1, 1002:1, 1003:1, 1004:1, 1005:1, 30000:83}`; per-store C01 spans 200.045 s to
82 800.275 s (`armB-report.md:53-64`); `armB-report.md:150` itself writes
`sobreposicoes de 3600 s a 82800 s em 9 de 10 stores: UNKNOWN`. Verdicts: `committed 95`,
`partial-uncommitted 4`, and the 4 clips without a usable key ARE exactly the 4 partial-uncommitted -
cause UNKNOWN. Controls outside the population refused 0.

It is UNKNOWN whether these are two correct instruments reading two different populations, or one
wrong predicate. No resolution is asserted here.
