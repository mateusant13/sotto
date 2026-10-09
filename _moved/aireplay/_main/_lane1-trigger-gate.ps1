# _lane1-trigger-gate.ps1 — the named, mechanical gate for the instant-replay trigger lane.
#
# Run:  H:\sotto\_moved\aireplay\_main\_lane1-trigger-gate.ps1
# Exit: 0 and the literal line `LANE1-GATE PASS` only when every arm behaves.
#
# WHAT MAKES THIS GATE NON-VACUOUS — arm D is a CONTROL, not a check:
#   The cure for the instant-replay trigger is ONE line in trigger.cpp (the edge latch, marked
#   //CURE-EDGE-LATCH).  Without it a HELD key emits a cut request on every poll tick, i.e. one
#   clip per 8 ms.  Arm C asserts "one press = exactly one cut".  Arm D builds a MUTANT from a
#   COPY of trigger.cpp with that line deleted and REQUIRES THE MUTANT TO FAIL.  If the deletion
#   silently stopped matching, the mutant would equal the fixed build, arm C would go green for
#   the wrong reason, and this arm goes RED.
#
# LESSON BAKED IN (a bug this file already had once): the first version used `goto fail`, which
# PowerShell rejects at these positions — execution fell THROUGH to the `LANE1-GATE PASS` line
# and printed PASS over a self-test that had CRASHED (rc 0xC0000005).  There is now exactly one
# exit point, it is `exit $code`, and `$code` is only ever 0 when every check below ran and
# passed.  No control-flow keyword can skip a check.
#
# HARD RULES this file obeys (lane brief §4):
#   2. no native command is ever piped; every one is `> file 2>&1` then $LASTEXITCODE;
#   3. native H:\ paths only;
#   5. it edits NOTHING under src\ — the mutant is a COPY written under _main\build.
$ErrorActionPreference = "Continue"

$src  = "H:\aireplay\src\capture"        # the junction build.cmd itself uses
$out  = "H:\aireplay\_main\build"
# Lane-private log directory.  MEASURED reason: another lane's gate writing
# _main\logs\lane1-repobuild.txt at the same moment made this gate's own redirect fail with
# "The process cannot access the file ... because it is being used by another process", and the
# run then reported an EMPTY error it had never read.  Shared log paths are a race in a repo
# where several gates run at once.
$logs = "H:\aireplay\_main\logs\lane1"
$gxx  = "H:\msys64\mingw64\bin\g++.exe"
$gatelog = "$logs\lane1-trigger-gate.txt"

$libsrc = @("common.cpp","d3d11_ctx.cpp","nv12_convert.cpp","wgc_capture.cpp","nvenc_encoder.cpp",
            "ring_buffer.cpp","mp4_writer.cpp","selftest.cpp","test_window.cpp","replay.cpp")
# The REDUCED set still links real capture sources, just not the ones a neighbouring lane may
# be editing.  Used ONLY when the full set fails for a reason this lane cannot own; the run
# prints which mode it used, because a gate that silently degrades is a dishonest gate.
$libsrc_reduced = @("common.cpp","ring_buffer.cpp")
$libs = @("-ld3d11","-ldxgi","-luuid","-lole32","-loleaut32","-lruntimeobject","-lwindowsapp",
          "-lpsapi","-lgdi32","-luser32")
$myFiles = @("trigger.cpp","trigger.h","trigger_selftest.cpp","trigger_selftest.h")

$script:LINES = New-Object System.Collections.Generic.List[string]
function Say([string]$s) { $script:LINES.Add($s); Write-Host $s }

function BuildSelftest([string]$exe, [string]$triggerSrc, [string]$tag, $srcs) {
    $all = @()
    foreach ($f in $srcs) { $all += "$src\$f" }
    $all += $triggerSrc
    $all += "$src\trigger_selftest.cpp"
    # Build logs live in the LANE-PRIVATE log dir, never _main\build (contended by other lanes).
    $blog = "$logs\build-$tag.txt"
    Remove-Item $blog -ErrorAction SilentlyContinue
    & $gxx -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter -I $src -I "$src\third_party" `
        @all -o $exe @libs > $blog 2>&1
    $rc = $LASTEXITCODE
    # MEASURED, and it is the exact silent-skip this repo's rule 2 exists to prevent: when the
    # redirect target is locked by another lane, PowerShell SKIPS the command entirely and
    # $LASTEXITCODE keeps its PREVIOUS value (0).  The gate then read a STALE log, reported
    # "warnings=0", and ran a STALE .exe.  So the log's existence is part of the contract.
    if (-not (Test-Path $blog)) {
        Write-Host "BUILD-SKIPPED $tag :: the compiler never ran (redirect target could not be opened)"
        return 99
    }
    return $rc
}

# Does this build log blame a file this lane owns?  A shared repo has lanes editing test_window.cpp
# and replay.cpp RIGHT NOW, and a gate that dies on their half-finished edit reports nothing
# about the trigger.  This separates "my lane is broken" from "a neighbour is mid-edit".
function BlameMine([string]$logPath) {
    foreach ($f in $myFiles) {
        if (Select-String -Path $logPath -Pattern ([regex]::Escape($f)) -ErrorAction SilentlyContinue |
            Where-Object { $_.Line -match "error:" }) { return $f }
    }
    return ""
}

function Invoke-Gate {
    if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs -Force | Out-Null }
    if (-not (Test-Path $out))  { New-Item -ItemType Directory -Path $out  -Force | Out-Null }

    Say "LANE1 GATE - instant-replay trigger"
    Say "SRC=$src  OUT=$out"

    # ---- ARM 0: the repo's OWN build ------------------------------------------------------
    # Attribution, not blame: if build.cmd is red in a file another lane owns, that is a
    # REPORTED finding about this run, not a verdict on the trigger.
    if (-not (Test-Path "$src\build.cmd")) { return "src\build.cmd is gone; the repo build path moved" }
    cmd /c "`"$src\build.cmd`"" > "$logs\lane1-repobuild.txt" 2>&1
    $repoRc = $LASTEXITCODE
    Say "ARM 0 repo build.cmd rc=$repoRc  (log: $logs\lane1-repobuild.txt)"
    if ($repoRc -ne 0) {
        $mine = BlameMine "$logs\lane1-repobuild.txt"
        $first = @(Get-Content "$logs\lane1-repobuild.txt" | Where-Object { $_ -match "error:" } | Select-Object -First 1)
        if ($mine -ne "") { return "build.cmd fails in a file THIS LANE OWNS ($mine)" }
        # build.cmd writes to a FIXED output path with no lock, so two lanes building at once
        # collide at the link step.  MEASURED here: "cannot open output file ...
        # aireplay-capture.exe: Permission denied" while NO aireplay-capture.exe process was
        # running and the exe was rewritten seconds later by another lane.  That is an
        # environment race, not a broken source, and the two must not wear the same verdict.
        $locked = (Select-String -Path "$logs\lane1-repobuild.txt" -Pattern "cannot open output file" -ErrorAction SilentlyContinue | Measure-Object).Count
        $tag = if ($locked -gt 0) { "red because its link OUTPUT was locked by a concurrent build.cmd" } else { "red in a file this lane does NOT own" }
        Say "ARM 0 WARN :: build.cmd is $tag; first error:"
        Say "ARM 0 WARN ::   $($first)"
        Say "ARM 0 WARN ::   this lane's verdict below is therefore about the TRIGGER only."
    }

    # ---- STEP 1: the FIXED selftest ------------------------------------------------------
    $fixedExe = "$out\aireplay-trigger-selftest.exe"
    $buildMode = "FULL"
    $rc = BuildSelftest $fixedExe "$src\trigger.cpp" "fixed" $libsrc
    if ($rc -ne 0) {
        $mine = BlameMine "$logs\build-fixed.txt"
        if ($mine -ne "") {
            Get-Content "$logs\build-fixed.txt" -Raw | Write-Host
            return "the fixed build fails in a file THIS LANE OWNS ($mine)"
        }
        Say "STEP 1 build FULL rc=$rc - a neighbouring lane's file does not compile;"
        Say "STEP 1   first error: $((@(Get-Content "$logs\build-fixed.txt" | Where-Object { $_ -match 'error:' } | Select-Object -First 1)))"
        Say "STEP 1   RETRYING in REDUCED mode (common.cpp + ring_buffer.cpp + trigger.*),"
        Say "STEP 1   which still links real capture sources but not the ones being edited."
        $buildMode = "REDUCED"
        $rc = BuildSelftest $fixedExe "$src\trigger.cpp" "fixed-reduced" $libsrc_reduced
        if ($rc -ne 0) {
            Get-Content "$logs\build-fixed-reduced.txt" -Raw | Write-Host
            return "the fixed build failed even in REDUCED mode"
        }
    }
    Say "STEP 1 build $buildMode rc=$rc"
    $bkey = if ($buildMode -eq "FULL") { "fixed" } else { "fixed-reduced" }
    $warn = (Select-String -Path "$logs\build-$bkey.txt" -Pattern "warning:" -ErrorAction SilentlyContinue | Measure-Object).Count
    Say "STEP 1 compiler warnings=$warn (built -Wall -Wextra; a warning is a finding)"
    if ($warn -gt 0) { return "the fixed build emitted $warn warning(s)" }

    # ---- STEP 2: the MUTANT - a COPY of trigger.cpp with the cure line deleted -----------
    $mutDir  = "$out\_lane1-trigger-mutant"
    $mutSrc  = "$mutDir\trigger-mutant.cpp"
    $mutExe  = "$out\aireplay-trigger-mutant.exe"
    New-Item -ItemType Directory -Path $mutDir -Force | Out-Null

    $cure = 'held_\[i\] = down \? 1 : 0;'
    $lines = Get-Content "$src\trigger.cpp"
    $hitCount = ($lines | Select-String -Pattern $cure | Measure-Object).Count
    Say "STEP 2 cure line occurrences in trigger.cpp = $hitCount"
    if ($hitCount -ne 1) {
        return "the cure line must occur EXACTLY ONCE for the revert to mean anything; found $hitCount"
    }
    $mutated = @($lines | Where-Object { $_ -notmatch $cure })
    Set-Content -Path $mutSrc -Value $mutated -Encoding UTF8
    $stillThere = (Select-String -Path $mutSrc -Pattern $cure -ErrorAction SilentlyContinue | Measure-Object).Count
    Say "STEP 2 cure line occurrences in the MUTANT COPY = $stillThere"
    if ($stillThere -ne 0) { return "the revert did not take; the control would be a no-op" }
    Say "STEP 2 sha256 fixed  = $((Get-FileHash "$src\trigger.cpp" -Algorithm SHA256).Hash)"
    Say "STEP 2 sha256 mutant = $((Get-FileHash $mutSrc -Algorithm SHA256).Hash)"

    $rc = BuildSelftest $mutExe $mutSrc "mutant" $(if ($buildMode -eq "FULL") { $libsrc } else { $libsrc_reduced })
    Say "STEP 2 build MUTANT ($buildMode) rc=$rc"
    if ($rc -ne 0) {
        Get-Content "$logs\build-mutant.txt" -Raw | Write-Host
        return "the mutant did not compile, so arm D has nothing to control"
    }

    # ---- STEP 3: run the arms ------------------------------------------------------------
    $runLog = "$logs\lane1-trigger-selftest.txt"
    & $fixedExe --mutant $mutExe --work-dir $out > $runLog 2>&1
    $runRc = $LASTEXITCODE
    Say "STEP 3 selftest rc=$runRc  (log: $runLog)"
    Say "---- selftest output ----"
    Get-Content $runLog -Raw | Write-Host
    Say "------------------------"

    # A crash is a failure.  rc 0xC0000005 as a signed int is -1073741819.
    if ($runRc -ne 0) { return "the self-test exited rc=$runRc (a crash or a red arm); see $runLog" }

    $runContent = @(Get-Content $runLog)
    $armLines = @($runContent | Where-Object { $_ -match '^ARM ' })
    $summary  = @($runContent | Where-Object { $_ -match '^TRIGGER-SELFTEST' })
    if ($armLines.Count -ne 5) { return "expected exactly 5 ARM lines (A-E), found $($armLines.Count)" }
    if ($summary.Count -ne 1)   { return "expected exactly 1 TRIGGER-SELFTEST summary line, found $($summary.Count)" }

    foreach ($n in @("A","B","C","D","E")) {
        $l = @($armLines | Where-Object { $_ -match "^ARM $n " })
        if ($l.Count -ne 1) { return "expected exactly one result line for arm $n, found $($l.Count)" }
        Say $l[0]
        if ($l[0] -notmatch "^ARM $n PASS ") { return "arm $n did not PASS" }
    }
    Say $summary[0]
    if ($summary[0] -notmatch 'GREEN') { return "the self-test summary is not GREEN" }

    Say "MEASUREMENT NOTE :: arms A-E measure THIS host's desktop session. 1 host, 1 session."
    Say "MEASUREMENT NOTE :: WHICH PATH FIRES INSIDE A FULLSCREEN GAME = NOT MEASURED IN-GAME."
    Say "BUILD MODE :: $buildMode"
    return ""
}

$code = Invoke-Gate
if ($code -eq "") {
    Say "LANE1-GATE PASS"
    $script:LINES -join "`n" | Set-Content -Path $gatelog -Encoding UTF8
    exit 0
} else {
    Say "LANE1-GATE FAIL :: $code"
    $script:LINES -join "`n" | Set-Content -Path $gatelog -Encoding UTF8
    Write-Host "LANE1-GATE FAIL (log: $gatelog)"
    exit 1
}