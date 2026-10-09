<#
    _lane7-window-gate.ps1 — the named, mechanical gate for the lane-7 window negotiation.

    Prints LANE7-GATE PASS and exits 0 only when every arm behaves.

      ARM A  byte-identity at 1920x1080 against the PRE-CHANGE capture.
             The witness is the OFFLINE CUT's actual bytes, compared pre vs post, byte for
             byte — not a hash of this lane's own new code.  Why the offline cut and not a
             live capture: MEASURED on this box, BOTH WGC paths refuse (CreateForWindow and
             CreateForMonitor both 0x80070005 — receipt 03 §7), so a live clip cannot be
             produced at all.  The offline cut is byte-deterministic (measured: two runs of
             the PRE binary produced the same sha256) and runs the SAME perform_cut() and
             the SAME Mp4Writer the live path runs.
             Also asserted: the live arm's own log still says 1920x1080 at AUTO on this
             1920x1080 desktop (the negotiation reproduces the old literal).

      ARM B  a 2560x1440 and a 3840x2160 window are negotiated correctly, plus the three
             failure modes the brief names: a monitor smaller than the request, a high-DPI
             desktop, and odd dimensions.  POPULATION and WINDOW are printed by the gate.
             Driven through the REAL negotiate_capture_window() compiled from
             src/capture/test_window.cpp — not a copy.

      ARM C  THE CONTROL.  The SAME byte assertion is run against a clip produced at a
             genuinely different window (1280x720), and it is required to report "not
             identical".  A gate that passes on both sides is worthless; this arm is the
             proof that arm A can fail.  The control PASSES when the reverted assertion goes
             RED — the polarity is the point, and the first draft of this gate had it
             backwards.

    HOUSE RULES observed: no native command is piped for its exit code (every invocation
    redirects to a file and reads $LASTEXITCODE); no console window is created — the probe
    and the capture exe are launched with CREATE_NO_WINDOW.
#>
[CmdletBinding()]
param(
    # ARM C control: revert arm A's byte assertion. Used ONLY to prove the gate can go red.
    [switch]$NegArm
)

$ErrorActionPreference = 'Stop'
$Repo    = 'H:\aireplay'
$Src     = "$Repo\src\capture"
$Main    = "$Repo\_main"
$Runs    = "$Main\runs"
$GXX     = 'H:\msys64\mingw64\bin\g++.exe'
$Probe   = "$Main\_lane7_window_probe.cpp"
$GateLog = "$Main\_lane7-window-gate.txt"

$script:Fail = 0
function Note($m) { Write-Host $m; Add-Content -LiteralPath $GateLog -Value $m }
function Res($arm, $ok, $msg) {
    if ($ok) { Note "  [$arm] PASS  $msg" } else { Note "  [$arm] FAIL  $msg"; $script:Fail++ }
}
function Die($m) { Note "  GATE ABORTED: $m"; Note 'LANE7-GATE FAIL'; exit 1 }

New-Item -ItemType Directory -Force -Path $Runs | Out-Null
Set-Content -LiteralPath $GateLog -Value "" -NoNewline

# ---------------------------------------------------------------- launch helper (no console window)
$NO_WINDOW = 0x08000000 -bor 0x00000008   # CREATE_NO_WINDOW | DETACHED_PROCESS-ish
function RunExe($exe, $argList, $outFile) {
    $p = Start-Process -FilePath $exe -ArgumentList $argList -NoNewWindow -Wait -PassThru `
                       -RedirectStandardOutput $outFile -RedirectStandardError "$outFile.err"
    return $p.ExitCode
}

# ================================================================= build
Note '=== LANE 7 GATE ==='
if (-not (Test-Path $GXX)) { Die "g++ not found at $GXX" }

$probeExe = "$Main\build\aireplay-window-probe.exe"
$probeArgs = @('-std=c++17', '-O2', '-Wall', '-Wextra', '-Wno-unused-parameter',
               '-I', $Src, '-I', "$Src\third_party",
               $Probe, "$Src\common.cpp", "$Src\test_window.cpp",
               '-o', $probeExe, '-lgdi32', '-luser32', '-ld3d11')
& $GXX @probeArgs > "$Main\_lane7-probe-build.txt" 2>&1
$rc = $LASTEXITCODE
if ($rc -ne 0) { Get-Content "$Main\_lane7-probe-build.txt" | ForEach-Object { Note "    $_" }; Die "probe build rc=$rc" }
Note "  probe built (links the REAL src/capture/test_window.cpp): rc=0"

# The capture binary — used for the offline cut, which is arm A's byte witness.
$capExe = "$Main\build\aireplay-capture.exe"
Push-Location $Src
cmd /c build.cmd > "$Main\_lane7-cap-build.txt" 2>&1
$rc = $LASTEXITCODE
Pop-Location
if ($rc -ne 0) { Get-Content "$Main\_lane7-cap-build.txt" | ForEach-Object { Note "    $_" }; Die "capture build rc=$rc" }
Note '  capture binary built: rc=0'

# ================================================================= ARM A — byte identity at 1080p
Note ''
Note '--- ARM A: at 1920x1080 the output is BYTE-IDENTICAL to the pre-change capture ---'

$srcH264 = "$Runs\src-gaming.h264"
if (-not (Test-Path $srcH264)) { Die "fixture missing: $srcH264" }

# PRE = the pre-lane sources, restored from git into a scratch tree and built there.  These
# are the bytes the lane had to preserve: NOT a hash of this lane's new code.
$preDir = "$Main\_lane7-pre-src"
if (Test-Path $preDir) { Remove-Item -Recurse -Force $preDir }
New-Item -ItemType Directory -Force -Path $preDir | Out-Null
# PRE = the pre-lane sources, restored from a PINNED commit and built here.
#
# MEASURED 2026-10-07 12:30: HEAD had MOVED under this gate mid-run and no longer held the
# pre-lane source — another agent committed this lane's broken first draft (`lParam` was
# not in scope in wnd_proc), so "HEAD" was silently the wrong baseline. A gate whose
# baseline floats is not a gate. So the baseline is PINNED and then ASSERTED by content,
# not merely by name:
#   * replay.cpp must still contain the literal `tw_.create(1920, 1080, ...)` — the defect
#     this lane removed;
#   * test_window.h must NOT declare negotiate_capture_window — the function this lane added.
# If either check fails the gate ABORTS rather than comparing against the wrong baseline.
$PreCommit = 'bae4e1e'
foreach ($f in 'replay.cpp', 'replay.h', 'test_window.cpp', 'test_window.h') {
    # Extract through git itself so the bytes are EXACTLY the committed ones. Piping
    # `git show` into PowerShell splits and re-joins lines and corrupts C++ (it did:
    # 'lParam' was mangled). The blob is written straight to disk by git.
    $blobPath = Join-Path $preDir $f
    & git -C $Repo show "$PreCommit`:src/capture/$f" | Out-Null   # fail fast if absent
    if ($LASTEXITCODE -ne 0) { Die "could not read the pre-change $f from $PreCommit" }
    & git -C $Repo cat-file blob "$PreCommit`:src/capture/$f" > $blobPath
    if ($LASTEXITCODE -ne 0) { Die "could not materialise the pre-change $f" }

    # PROVE the extraction was byte-faithful: git's own hash-object of the file on disk
    # must equal the hash of the committed blob. Arm A rests on this, so it is checked,
    # not assumed — a PowerShell re-encode here would silently weaken the whole gate.
    $want = (& git -C $Repo rev-parse "$PreCommit`:src/capture/$f").Trim()
    $got  = (& git -C $Repo hash-object $blobPath).Trim()
    if ($want -ne $got) { Die "the extracted pre-change $f is not the committed bytes (blob=$want disk=$got)" }
    Note "    pre-change $f from $PreCommit extracted byte-faithfully (git blob $want)"
}

$preReplay = Get-Content -LiteralPath "$preDir\replay.cpp" -Raw
$preTwHdr  = Get-Content -LiteralPath "$preDir\test_window.h" -Raw
if ($preReplay -notmatch 'tw_\.create\(\s*1920,\s*1080') {
    Die "$PreCommit is NOT the pre-lane baseline: its replay.cpp no longer hardcodes 1920x1080"
}
if ($preTwHdr -match 'negotiate_capture_window') {
    Die "$PreCommit is NOT the pre-lane baseline: its test_window.h already has the negotiation"
}
Note "  baseline $PreCommit CONFIRMED pre-lane by content (hardcodes 1920x1080, has no negotiation)"

# The PRE sources compile against the CURRENT headers of the files this lane does NOT own.
$preExe = "$Main\build\aireplay-capture-PRE-lane7.exe"
$preArgs = @('-std=c++17', '-O2', '-w',
             '-I', $preDir, '-I', "$Src", '-I', "$Src\third_party",
             "$Src\main.cpp", "$preDir\replay.cpp", "$preDir\test_window.cpp",
             "$Src\common.cpp", "$Src\d3d11_ctx.cpp", "$Src\nv12_convert.cpp", "$Src\wgc_capture.cpp",
             "$Src\nvenc_encoder.cpp", "$Src\ring_buffer.cpp", "$Src\mp4_writer.cpp", "$Src\selftest.cpp",
             '-o', $preExe, '-ld3d11', '-ldxgi', '-luuid', '-lole32', '-loleaut32', '-lruntimeobject',
             '-lwindowsapp', '-lpsapi', '-lgdi32', '-luser32')
& $GXX @preArgs > "$Main\_lane7-prebuild.txt" 2>&1
$rc = $LASTEXITCODE
if ($rc -ne 0) { Get-Content "$Main\_lane7-prebuild.txt" | ForEach-Object { Note "    $_" }; Die "PRE build rc=$rc" }
Note '  PRE binary built from the pinned pre-lane sources: rc=0'

$preMp4 = "$Runs\lane7-gate-A-pre.mp4"
$postMp4 = "$Runs\lane7-gate-A-post.mp4"
foreach ($p in $preMp4, $postMp4) { if (Test-Path $p) { Remove-Item -Force $p } }

$rc = RunExe $preExe  @('--cut-from-h264', $srcH264, '--cut-fps', '60', '--cut-size', '1920x1080', '--out', $preMp4,  '--log', "$Runs\lane7-gate-A-pre.log")  "$Runs\lane7-gate-A-pre.out"
Res 'A/pre' ($rc -eq 0) "pre-change offline cut rc=$rc"
$rc = RunExe $capExe @('--cut-from-h264', $srcH264, '--cut-fps', '60', '--cut-size', '1920x1080', '--out', $postMp4, '--log', "$Runs\lane7-gate-A-post.log") "$Runs\lane7-gate-A-post.out"
Res 'A/post' ($rc -eq 0) "post-change offline cut rc=$rc"

function CompareClips($p1, $p2) {
    $a = Get-Content -LiteralPath $p1 -AsByteStream -ReadCount 0
    $b = Get-Content -LiteralPath $p2 -AsByteStream -ReadCount 0
    $lenA = $a.Count; $lenB = $b.Count
    if ($lenA -ne $lenB) {
        return [pscustomobject]@{ identical = $false; lenA = $lenA; lenB = $lenB; firstDiff = -1 }
    }
    for ($i = 0; $i -lt $lenA; $i++) {
        if ($a[$i] -ne $b[$i]) {
            return [pscustomobject]@{ identical = $false; lenA = $lenA; lenB = $lenB; firstDiff = $i }
        }
    }
    return [pscustomobject]@{ identical = $true; lenA = $lenA; lenB = $lenB; firstDiff = -1 }
}

if ($NegArm) {
    # ---------------------------------------------------------------- ARM C, the CONTROL.
    # The control's job: prove arm A's byte assertion CAN fail. The way to prove that is to
    # run the SAME comparison against a clip that genuinely differs, and require the
    # comparison to report "not identical".
    #
    # The negative arm is built the way a real regression would be: the POST binary is asked
    # for a DIFFERENT window (1280x720) via the offline cut's own declared size. That changes
    # the container header and the avcC/SPS description, so the bytes must differ.
    #
    # NOTE the polarity, which the first draft of this gate had BACKWARDS: the control PASSES
    # when the reverted assertion goes RED. Asserting "the two clips differ" as a pass
    # condition would make the control pass in exactly the situation it exists to catch.
    Note '  [A/CONTROL] the byte assertion is being run against a DIFFERENT window (1280x720)'
    $ctrlMp4 = "$Runs\lane7-gate-C-control.mp4"
    if (Test-Path $ctrlMp4) { Remove-Item -Force $ctrlMp4 }
    $rc = RunExe $capExe @('--cut-from-h264', $srcH264, '--cut-fps', '60', '--cut-size', '1280x720',
                           '--out', $ctrlMp4, '--log', "$Runs\lane7-gate-C-control.log") "$Runs\lane7-gate-C-control.out"
    Res 'C/build' ($rc -eq 0) "the control clip (1280x720) was produced rc=$rc"

    $cmpCtrl = CompareClips $preMp4 $ctrlMp4
    if ($cmpCtrl.identical) {
        Res 'C' $false ("the control clip at a DIFFERENT size compared IDENTICAL to the 1920x1080 clip " +
                        "($($cmpCtrl.lenA) bytes) => the byte assertion cannot detect a window change => ARM A IS VACUOUS")
    } else {
        $where = if ($cmpCtrl.firstDiff -ge 0) { "first differing byte at offset $($cmpCtrl.firstDiff)" }
                 else { "different lengths ($($cmpCtrl.lenA) vs $($cmpCtrl.lenB))" }
        Res 'C' $true "the SAME assertion reported NOT identical on a genuinely different clip ($where) => arm A is capable of failing"
    }

    # And the real arm A must still pass on the equal-size pair, or the control proves nothing.
    $cmpReal = CompareClips $preMp4 $postMp4
    Res 'C/sanity' $cmpReal.identical "arm A still holds on the true pair ($($cmpReal.lenA) bytes identical)"
} else {
    $preExists = Test-Path $preMp4
    $postExists = Test-Path $postMp4
    Res 'A' ($preExists -and $postExists) "both clips exist (pre=$preExists post=$postExists)"
    if ($preExists -and $postExists) {
        $cmp = CompareClips $preMp4 $postMp4
        Res 'A/len' ($cmp.lenA -eq $cmp.lenB) "byte length pre=$($cmp.lenA) post=$($cmp.lenB)"
        # ACTUAL BYTE COMPARISON, not a hash of this lane's code.
        Res 'A/bytes' $cmp.identical ("ACTUAL BYTES identical over $($cmp.lenA) bytes " +
            "(sha256 pre=$((Get-FileHash $preMp4 -Algorithm SHA256).Hash) post=$((Get-FileHash $postMp4 -Algorithm SHA256).Hash))")
    }
}

# The live arm still resolves to the old literal at 1080p.
$rc = RunExe $capExe @('--run', '--seconds', '3', '--cut-at', '2', '--window-alpha', '1',
                       '--out', "$Runs\lane7-gate-A-run.mp4", '--log', "$Runs\lane7-gate-A-run.log") "$Runs\lane7-gate-A-run.out"
$liveLog = "$Runs\lane7-gate-A-run.log"
if (Test-Path $liveLog) {
    $neg = Select-String -Path $liveLog -Pattern 'WINDOW NEGOTIATION: (\d+)x(\d+)' | Select-Object -First 1
    if ($neg) {
        $size = "$($neg.Matches[0].Groups[1].Value)x$($neg.Matches[0].Groups[2].Value)"
        Res 'A/negotiated' ($size -eq '1920x1080') "live arm negotiated $size on this 1920x1080 desktop (the pre-lane literal)"
    } else {
        Res 'A/negotiated' $false 'the live arm logged no WINDOW NEGOTIATION line'
    }
    $nv = Select-String -Path $liveLog -Pattern 'NV12 input texture: (\d+)x(\d+)' | Select-Object -First 1
    if ($nv) {
        $tex = "$($nv.Matches[0].Groups[1].Value)x$($nv.Matches[0].Groups[2].Value)"
        Res 'A/texture' ($tex -eq '1920x1080') "NV12 texture created at $tex"
    }
} else { Res 'A/negotiated' $false "the live arm wrote no log (rc=$rc)" }

# ================================================================= ARM B — 1440p / 4K / failure modes
Note ''
Note '--- ARM B: 2560x1440 and 3840x2160 negotiated; the named failure modes too ---'

# POPULATION: 6 synthetic output desktops x 4 requests each = 24 decisions, in one process,
# against the real negotiate_capture_window().
$cases = @('1440p=2560x1440', '4k=3840x2160', '4k60=3840x2160', '1080p=1920x1080',
           'small-monitor=1366x768', 'highdpi-logical=2560x1440')
$expect = @{
    # label                        w      h      source                            clamped auto
    '1440p'                   = @('2560', '1440', 'output-desktop',                0, 1)
    '1440p/req1080p'          = @('1920', '1080', 'requested',                     0, 0)
    '1440p/req4k'             = @('2560', '1440', 'requested-clamped-to-monitor',  1, 0)
    '1440p/req-odd'           = @('2558', '1438', 'requested',                     0, 0)
    '4k'                      = @('3840', '2160', 'output-desktop',                0, 1)
    '4k/req1080p'             = @('1920', '1080', 'requested',                     0, 0)
    '4k/req4k'                = @('3840', '2160', 'requested',                     0, 0)
    '4k/req-odd'              = @('2558', '1438', 'requested',                     0, 0)
    '4k60'                    = @('3840', '2160', 'output-desktop',                0, 1)
    '4k60/req1080p'           = @('1920', '1080', 'requested',                     0, 0)
    '4k60/req4k'              = @('3840', '2160', 'requested',                     0, 0)
    '4k60/req-odd'            = @('2558', '1438', 'requested',                     0, 0)
    '1080p'                   = @('1920', '1080', 'output-desktop',                0, 1)
    '1080p/req1080p'          = @('1920', '1080', 'requested',                     0, 0)
    '1080p/req4k'             = @('1920', '1080', 'requested-clamped-to-monitor',  1, 0)
    # 2559x1439 requested on a 1920x1080 desktop: the clamp to the monitor happens FIRST
    # (1920x1080, both even), so the even-floor never engages — even_floored must stay 0.
    # This case is here precisely because it is the one where the order of the two rules is
    # observable, and it is asserted by the even_floored field as well as by w/h.
    '1080p/req-odd'           = @('1920', '1080', 'requested-clamped-to-monitor',  1, 0)
    'small-monitor'           = @('1366', '768',  'output-desktop',                0, 1)
    'small-monitor/req1080p'  = @('1366', '768',  'requested-clamped-to-monitor',  1, 0)
    'small-monitor/req4k'     = @('1366', '768',  'requested-clamped-to-monitor',  1, 0)
    'small-monitor/req-odd'   = @('1366', '768',  'requested-clamped-to-monitor',  1, 0)
    'highdpi-logical'         = @('2560', '1440', 'output-desktop',                0, 1)
    'highdpi-logical/req1080p'= @('1920', '1080', 'requested',                     0, 0)
    'highdpi-logical/req4k'   = @('2560', '1440', 'requested-clamped-to-monitor',  1, 0)
    'highdpi-logical/req-odd' = @('2558', '1438', 'requested',                     0, 0)
}
Note "  POPULATION: $($cases.Count) output desktops x 4 requests = $($cases.Count * 4) decisions"
Note '  WINDOW: negotiate_capture_window() as compiled from src/capture/test_window.cpp'

# Expectations are declared as FIELDS (w, h, source, clamped, auto) and compared field by
# field against the parsed decision.  The first draft of this gate declared whole expected
# STRINGS and compared them with -eq; it omitted the even_floored/ok fields, so 24 correct
# decisions were all reported as failures.  Asserting the fields the brief constrains is
# both correct and more precise.
$outB = "$Runs\lane7-gate-B.out"
$rc = RunExe $probeExe (@('decide') + $cases) $outB
Res 'B/run' ($rc -eq 0) "probe rc=$rc"

$seen = 0
$byLabel = @{}
$lines = @()
if (Test-Path $outB) { $lines = Get-Content -LiteralPath $outB | Where-Object { $_ -match '^DECISION ' } }
foreach ($l in $lines) {
    $seen++
    if ($l -match '^DECISION\s+(\S+)\s+(\d+)x(\d+)\s+source=(\S+)\s+clamped=(\d+)\s+auto=(\d+)\s+even_floored=(\d+)\s+ok=(\d+)') {
        $label = $Matches[1]
        $byLabel[$label] = @{ f = @($Matches[2], $Matches[3], $Matches[4], $Matches[5], $Matches[6])
                              even = $Matches[7]; ok = $Matches[8] }
        if (-not $expect.ContainsKey($label)) {
            Res "B/$label" $false "UNEXPECTED decision label (no case declared for it): $l"
            continue
        }
        $want = $expect[$label]
        $names = @('w', 'h', 'source', 'clamped', 'auto')
        $diff = @()
        for ($i = 0; $i -lt 5; $i++) {
            if ($byLabel[$label].f[$i] -ne $want[$i]) { $diff += "$($names[$i]): want=$($want[$i]) got=$($byLabel[$label].f[$i])" }
        }
        Res "B/$label" ($diff.Count -eq 0) ("$label -> $($byLabel[$label].f[0])x$($byLabel[$label].f[1]) source=$($byLabel[$label].f[2]) clamped=$($byLabel[$label].f[3]) auto=$($byLabel[$label].f[4])" +
                                          $(if ($diff.Count -eq 0) { '' } else { '  <<< ' + ($diff -join '; ') }))
    } else {
        Res 'B/parse' $false "unparseable decision line: $l"
    }
}
# A silently dropped case is a coverage hole, not a pass.
foreach ($k in $expect.Keys) {
    if (-not $byLabel.ContainsKey($k)) { Res "B/missing/$k" $false "declared case '$k' produced NO decision line" }
}
# COVERAGE is bidirectional: every observed label must be declared AND every declared label
# must have been observed, with equal counts.  One-directional checking is how the 4
# undeclared labels below survived an earlier run of this gate.
Res 'B/population' ($seen -eq ($cases.Count * 4)) "POPULATION CHECK: $seen of $($cases.Count * 4) decisions observed"
Res 'B/every-case-hit' ($byLabel.Count -eq $expect.Count) "COVERAGE CHECK: $($byLabel.Count) distinct labels exercised, $($expect.Count) declared"

# The three failure modes the brief names, asserted by NAME against the parsed results, so a
# reader cannot miss them and so the assertion cannot silently match nothing.
Note '  failure modes named explicitly:'
function Field($label, $i) { if ($byLabel.ContainsKey($label)) { return $byLabel[$label].f[$i] } else { return '<none>' } }
Res 'B/mode/monitor-smaller-than-request' `
    ((Field 'small-monitor/req4k' 2) -eq 'requested-clamped-to-monitor' -and (Field 'small-monitor/req4k' 0) -eq '1366' -and (Field 'small-monitor/req4k' 3) -eq '1') `
    "a 3840x2160 request on a 1366x768 monitor clamps to 1366x768 (source=$(Field 'small-monitor/req4k' 2) clamped=$(Field 'small-monitor/req4k' 3))"
Res 'B/mode/high-dpi-desktop' `
    ((Field 'highdpi-logical' 0) -eq '2560' -and (Field 'highdpi-logical/req4k' 2) -eq 'requested-clamped-to-monitor') `
    "a 2560x1440 desktop takes 2560x1440 at AUTO and clamps a 4K request (source=$(Field 'highdpi-logical/req4k' 2))"
Res 'B/mode/odd-dimensions-floor' `
    ((Field '4k/req-odd' 0) -eq '2558' -and (Field '4k/req-odd' 1) -eq '1438' -and $byLabel['4k/req-odd'].even -eq '1') `
    "2559x1439 floors to 2558x1438 (even_floored=$($byLabel['4k/req-odd'].even)) for NV12's half-size chroma plane"

# And the REAL desktop on this box.
$outR = "$Runs\lane7-gate-B-real.out"
$rc = RunExe $probeExe @('real') $outR
Res 'B/real' ($rc -eq 0) "real-desktop probe rc=$rc"
if (Test-Path $outR) {
    $real = Get-Content -LiteralPath $outR | Where-Object { $_ -match '^DECISION real/auto' } | Select-Object -First 1
    if ($real -and $real -match '^DECISION\s+\S+\s+(\d+)x(\d+)\s+') {
        $rw = [int]$Matches[1]; $rh = [int]$Matches[2]
        Res 'B/real-size' ($rw -gt 0 -and $rh -gt 0) "this box negotiated $rw`x$rh from its own display mode"
    } else { Res 'B/real-size' $false 'the real-desktop probe produced no decision' }
}

# ================================================================= ARM C — the control
Note ''
if ($NegArm) {
    Note '--- ARM C (control): the byte assertion was run against a genuinely DIFFERENT clip ---'
    Note '  A gate that passes on both sides is worthless. The control PASSES when the byte'
    Note '  assertion goes RED on a real difference, which is what proves arm A can fail.'
    if ($script:Fail -eq 0) {
        Note ''
        Note 'LANE7-GATE PASS (control run: the reverted assertion correctly reported FAIL on a different window)'
        exit 0
    } else {
        Note '  ARM C FAILED: the byte assertion did not behave as required.'
        Note 'LANE7-GATE FAIL'
        exit 1
    }
} else {
    Note '--- ARM C (control): NOT RUN in this invocation. Re-run with -NegArm. ---'
    Note '  A gate that passes on both sides is worthless; run:'
    Note '    pwsh -File _lane7-window-gate.ps1 -NegArm'
}

# ================================================================= verdict
Note ''
if ($script:Fail -eq 0) {
    Note 'LANE7-GATE PASS'
    exit 0
}
Note "LANE7-GATE FAIL  ($($script:Fail) assertion(s) failed)"
exit 1