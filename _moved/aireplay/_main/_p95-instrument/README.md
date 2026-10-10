# press-to-clip-probe -- README

Sotto (ShadowPlay clone, `_moved/aireplay`) press-to-clip latency instrument.
**This file measures the CUT half only.**  It prints that decomposition in its own
output on every run, before any number.

## 0. STATUS -- READ THIS FIRST

**Delivered, parse-checked, NEVER EXECUTED.**  Nothing in this directory has been run:
no probe run, no `aireplay-capture.exe`, no NVENC session, no WASAPI device, no WGC
capture, no ffmpeg.  That was the condition of the delivery.

Consequently: every exit code, every verdict word and the RED of the control arm are
**DESIGNED AND UNVERIFIED**.  They are what the code does when read, not what was
observed.  The first person to run these files is the first measurement; treat the
first run as a smoke test of the instrument, not as a latency result.

What IS verified, without executing anything: both .ps1 files parse clean under the
PowerShell 5.1 parser (`Parser::ParseFile`, 0 errors), the source lines quoted below
were read from disk, and the red arm differs from the green arm only at the named
mutation sites (line-level diff in `INSTRUMENT-CHECKLIST.md` section 4).

## 1. What "press-to-clip" decomposes into

    press-to-clip = [ A: keypress -> the cut decision is taken ]
                  + [ B: cut command -> clip finalised on disk, next clip open ]

`press-to-clip-probe.ps1` measures **B only**.  A is UNKNOWN here, and no number this
instrument prints may be quoted as press-to-clip latency.

## 2. Why A is UNKNOWN -- verified in the source, with line numbers

Read on `src/capture/main.cpp` (68613 B, mtime 2026-10-09T06:00:03Z):

* **Nothing in `main.cpp` constructs a `Trigger`.**  The only reference in the whole
  file is the observer `Trigger* trig = replay.hotkey();` at **main.cpp:627**; every
  other grep hit for `Trigger` is a comment (:566, :567, :569, :621, :622, :623).
* **The hotkey defaults OFF** -- main.cpp:645-647.
* `trigger.cpp` **IS** on the link line (**build.cmd:23**), so the capability is built.
  The note in `_moved/aireplay/AGENTS.md` claiming `trigger.cpp` is off the link line
  is **STALE**; the shipped binary carries the code and `main.cpp` never arms it.
* **There is no `--stdin` argument.**  `parse()` (main.cpp:192-237) has no such flag,
  and an unknown argument dies at :233-234 with `ARGS_REJECTED: unknown argument: --stdin`
  (exit 2, :1331).
* **stdin is automatic, and in `--run` mode it REFUSES cuts.**  `main()` runs a blocking
  `ReadFile` loop (:1346-1367) and routes each line to `stdin_handle` (:1362), but in
  `--run` mode the clip session is `nullptr`, so `{"cmd":"cut"}` returns
  `{"error":"no clip session is open","ok":false,"cut":false}` -- main.cpp:1109-1113.

**Therefore the invocation that was originally specified (`--run --stdin`) cannot exist.**
The device-free arm that does accept cut commands is:

    --cut-session ...      main.cpp:1336-1342  ->  arm_cut_session(), main.cpp:1235-1324

and that arm contains **zero** NVENC / WGC / D3D11 / AudioTap references (grep-verified
over 1235-1324), which is why this instrument can measure B without opening a device.
That absence is a **reading of the source, not a measurement** -- see section 10.

## 3. Files

| file | what |
|---|---|
| `press-to-clip-probe.ps1` | THE INSTRUMENT (green).  675 lines, 32935 B. |
| `press-to-clip-probe.red.ps1` | THE CONTROL (red).  Same file plus one injected mutation (two selectable) and the two self-checks that must catch it.  722 lines, 36142 B. |
| `README.md` | this file |
| `INSTRUMENT-CHECKLIST.md` | the claims it CAN and CANNOT make, each with its carrying output field |

## 4. Run preconditions (a refusal is a FAILURE, never a silent skip)

1. **No other lane gate may be running.**  NVENC allows at most 10 sessions, and there is
   exactly ONE WASAPI loopback owner, so two device gates must never be concurrent.
   The probe refuses (exit 2) and prints the offending pid + command line unless
   `-NoPreflight` is passed.  The census runs from THIS .ps1 FILE via
   `Get-CimInstance Win32_Process` -- the inline `-Command` form returns empty on this
   box and would silently report "nothing is running".  **An empty census is reported as
   `CENSUS-EMPTY` and treated as a failure**, never as "all clear".
2. **`TMPDIR` must be `I:\cc-tmp`** -- the probe sets `$env:TMPDIR` and the child's own
   `TMPDIR` to `I:\cc-tmp`.  `G:` fills and kills lanes with ENOSPC.
3. **`-WorkDir` must resolve under `I:\cc-tmp`** unless `-ForceWorkDirAnywhere` is given.
   The exe's own default (`H:\aireplay\_main\runs`) is inside the protected tree and is
   ALWAYS overridden.
4. **The clip dir must be empty after the sweep.**  The probe deletes `cut-*.mp4` and
   refuses to measure if anything else remains -- it will not measure into a directory
   holding files it did not create.
5. **No visible console window.**  The child is started with `UseShellExecute=false` and
   `CreateNoWindow=true` (CREATE_NO_WINDOW); it never allocates its own console.
6. **The feed must be long enough for the plan.**  `PLAN` prints the arithmetic and the
   run exits 2 with the numbers if the feed is shorter.

## 5. How to run it

    pwsh -NoProfile -File I:\cc-tmp\p95-instrument\press-to-clip-probe.ps1

or, overriding the defaults (all paths native `H:\` form):

    pwsh -NoProfile -File I:\cc-tmp\p95-instrument\press-to-clip-probe.ps1 `
      -Exe  'H:\sotto\_moved\aireplay\_main\build\aireplay-capture.exe' `
      -Feed 'H:\sotto\_moved\aireplay\_main\src\cap-small.h264' `
      -Cuts 30 -CadenceMs 150 -Fps 60

Defaults: `Exe` = `H:\sotto\_moved\aireplay\_main\build\aireplay-capture.exe`,
`Feed` = `H:\sotto\_moved\aireplay\_main\src\cap-small.h264`, `Fps` 60,
`Size` 1920x1080, `Cuts` 30, `CadenceMs` 150, `WorkDir` `I:\cc-tmp\p95-instrument\run`,
`MinPollHz` 200, `PollHz` 500, `CutTimeoutMs` 5000, `WarmupMs` 300, `GoalP95Ms` 250.0.
Switches: `-KeepClips`, `-ForceWorkDirAnywhere`, `-NoPreflight`.  `-ResultJsonl <path>`
moves the JSONL; `-FirstCutIndex` only shifts the reported clip numbering.

The child command line it builds (one process, one stdin pipe):

    aireplay-capture.exe --cut-session --cut-from-h264 "<Feed>" --cut-dir "<run>\clips"         --cut-fps <Fps> --cut-size <Size> --log "<run>\exe.log"

Then, at `CadenceMs` intervals, the probe writes `{"cmd":"cut"}` + newline to that pipe.

## 6. What it prints and writes

Every run writes, under `-WorkDir`:

| output | content |
|---|---|
| `cuts.jsonl` | one `kind:run` record, one record per cut, one `kind:summary` record |
| `child-stdout.log` | the child's complete stdout, unmodified |
| `exe.log` | the child's own log, written by the child |
| `clips\cut-NNNN.mp4` | deleted as measured unless `-KeepClips` |

Per cut it prints one row: index, `t_cmd_ms`, `t_file_closed_ms`, `delta_ms`,
`reply_delta_ms`, frames, bytes, box count, status word.  Then:

* `SUMMARY n=... p50=... p95=... p99=... min=... max=... method=...` -- one line, with
  the percentile method spelled out inside it.
* `SUMMARY-REPLY ...` -- the child-internal half (cut command read -> reply written),
  reported separately and never mixed into the headline number.
* `POLL iterations = ... achieved = ... Hz` and `quantisation floor = ... ms`.
* `VERDICT GREEN` / `VERDICT RED`.

## 7. Exit codes (the exit code IS the verdict)

| code | meaning |
|---|---|
| 0 | GREEN -- n cuts finalised, box walk clean on every clip, reply/size consistency held, poll cadence contract met |
| 1 | RED -- at least one self-check failed (this is the code the control arm must return) |
| 2 | FAIL -- the measurement could not be taken; the reason is printed (refusal, timeout, insufficient population, precondition violation) |
| 3 | reserved for the control file; the green file never returns it |

## 8. The number: method and sampling error

* Clock: QPC via `[System.Diagnostics.Stopwatch]::GetTimestamp()` (a static read, safe
  from any thread) with `Frequency`; both the poll loop and the stdout reader runspace
  stamp on the same base.
* Percentiles: **nearest-rank** on the ascending-sorted deltas,
  `rank = ceil(p/100*n)`, 1-based.  At n=30 the p95 is the 29th smallest value.  The
  method string is printed in the summary line so no reader has to guess.
* **Sampling error is stated, not hidden.**  Every delta is quantised by the poll
  interval; the true latency lies in `[delta, delta + 1/pollHz_achieved]`.  The achieved
  rate and that floor are printed.  A run whose achieved rate is below `-MinPollHz` is RED.
* The poll is a **tight direct-file poll of the predicted path** `cut-%04d.mp4`
  (`ClipSession::path_for`, main.cpp:1030-1034, whose format is literally "cut-%04llu.mp4"
  at main.cpp:1032) via `FileStream` open + box walk.  NOT
  `FileSystemWatcher` (asynchronous, buffered delivery would add unmeasured jitter to
  `t_file_closed`) and NOT `Get-ChildItem` (a listing enumerates every entry every poll,
  so its cost grows with the clips kept).
* The completion test is **ffprobe-free**: a top-level ISO-BMFF box walk that must be well
  formed, end exactly at the file length, and finish on `moov` -- the box
  `Mp4Writer::close()` appends last (mp4_writer.cpp:305-311).  It is a completion test,
  not a decode validation.
* `-GoalP95Ms` is a target the **owner** picked, never a measurement; missing it prints a
  yellow line and does not by itself turn the run red.

## 9. The control arm

    pwsh -NoProfile -File I:\cc-tmp\p95-instrument\press-to-clip-probe.red.ps1

It must go **RED, name its mutation and exit 1**.  Two mutations, both selectable:

* `-Mutation zero-t-cmd` (**default, baked in**): the QPC stamp taken immediately before
  each cut command is replaced by the constant `0.0`, so every delta is the raw stopwatch
  epoch -- tens of thousands of ms.  The CONTROL-ARM SELF-CHECK must find a median above
  1000 ms, print `RED-MUTATION: zero-t-cmd` and `exit 1`.
* `-Mutation close-on-first-sight`: the completion test is replaced by "the file exists",
  so `t_file_closed` is stamped while the clip is still being written.  Caught because the
  size at that instant cannot equal the reply's `closed_bytes` and no box walk ends in
  `moov`.

The cadence anchor stays a REAL stamp in mutation A, so the mutation cannot also change the
cut spacing: one mutation, one consequence.  If the control ever ends GREEN, the control has
failed -- not the instrument -- and its own banner says so.

**Its RED has not been observed** (section 0).  Running it is the same act as running the
green file: it spawns `aireplay-capture.exe`.

## 10. What a run does NOT prove

* Nothing about **A** (keypress -> cut decision).  Not measured, not bounded, UNKNOWN.
* Nothing about a **physical disk flush**.  `t_file_closed` is the moment the finalised
  bytes are visible to another process through the OS file cache.
* Nothing about the **capture device, NVENC, the ring buffer, or frame age**.  The feed in
  `--cut-session` is a file; the clip's content is that file's access units, so no number
  here describes a live capture path.
* Nothing about **encoder packet latency** or audio.
* That `--cut-session` opens no device is a **reading of main.cpp:1235-1324**, not a
  measurement.  If you need that proven, gate it with the process/device census
  (`all-gates.ps1` style), not with this instrument.

## 11. When a run is DIRTY -- say so, do not present it

* the exe's `sha256` differs from the `kind:run` record (the binary moved under you);
* `CENSUS-EMPTY` or any preflight hit (`-NoPreflight` was used to get past it);
* the child exit code is not 0, or a cut timed out (`CutTimeoutMs`);
* the achieved poll rate is below `-MinPollHz`;
* fewer than 30 executed cuts (`-Cuts` defaults to 30 for exactly this reason);
* any clip failed the `chain-ok-moov-last` walk, or a reply was `ok:false`.

A dirty run is repeated, not explained away.  `SKIP IS FAIL`.

## 12. House rules this file obeys

* pure ASCII; no backticks anywhere in either .ps1
* PowerShell 5.1 compatible (no ternary, no `??`, no `Join-String`)
* process lists from a **.ps1 file** with `Get-CimInstance Win32_Process`
* native `H:\` paths; child `TMPDIR` forced to `I:\cc-tmp`
* `CREATE_NO_WINDOW` -- no visible console on the owner's screen
* both colours: the green instrument and its red control ship together
