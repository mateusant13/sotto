# ALL-GATES - the aggregate gate for the aireplay project. BOTH COLOURS BY CONSTRUCTION.
#
# WHY THIS FILE EXISTS: every lane writes its own `_lane*-gate.ps1`, and there was no
# way to answer "is the project green?" in one command. A project with no aggregate
# gate reports green BY DEFAULT, and that is the most expensive kind of wrong: it is
# indistinguishable from a project that is actually green.
#
# THE THREE LAWS THIS FILE ENFORCES:
#   1. DISCOVERY IS A GLOB, NEVER A LIST. `_lane*-gate.ps1` is resolved fresh on
#      every run. A hardcoded list rots the moment a lane lands, and a rotted list
#      silently stops checking the new lane - the same defect as a missing gate.
#      POPULATION and WINDOW (the glob instant) are printed every run, per hard rule 6.
#   2. A MISSING CHECK IS A FAIL, NOT A SKIP. Zero discovered gates => FAIL. A named
#      gate from -Expect that is not in the population => FAIL. An include that does
#      not exist => FAIL. Nothing is ever skipped, because "skipped" and "passed" are
#      the same word to every consumer that only reads the exit code.
#   3. THE REAL EXIT CODE, READ FROM THE PROCESS OBJECT. Not $LASTEXITCODE (which is
#      stale if the gate never invoked a native command) and NEVER a pipe (hard rule 2;
#      this repo already paid for a gate that reported green over a hidden exit 2).
#
# A HANG IS A FAIL AND IT SAYS WHICH GATE HUNG. WaitForExit(timeout) returning false
# kills the whole process tree (Kill(true) - killing only the root is what left the
# orphan writers documented in receipt-15 §0) and names the gate on stdout.
#
# WINDOWS: children run with CreateNoWindow=true + UseShellExecute=false, i.e. the
# CREATE_NO_WINDOW (0x08000000) path. Hard rule 1. No console window is ever opened,
# including for the hanging-gate arm of the self-test.
#
# OUTPUT DISCIPLINE: every human-readable line goes to [Console]::Out directly, never
# through Write-Output. The functions here RETURN data (a gate result, an exit code);
# if they also wrote to the PowerShell success stream, `exit (Invoke-Aggregate ...)`
# would receive its own printed lines as an array instead of 0/1.
#
# Usage:
#   pwsh -File _main\all-gates.ps1                        # the real aggregate
#   pwsh -File _main\all-gates.ps1 -TimeoutSec 600        # patient run
#   pwsh -File _main\all-gates.ps1 -Expect _lane01-x-gate  # demand a gate EXISTS
#   pwsh -File _main\all-gates.ps1 -SelfTest              # prove it can go RED
#
# Exit: 0 = ALL-GATES PASS. Non-zero = ALL-GATES FAIL.
#
# HONEST LIMITS (read before trusting this):
#   - The EXIT CODE is authoritative. A gate that prints `GATE-VERDICT FAIL` while
#     exiting 0 is contradicting itself and is scored FAIL - the declaration wins.
#     `-NoVerdictLine` waives even that and trusts the exit code alone; self-test ARM-G
#     exists to keep that hole visible and re-runnable.
#   - A gate that prints NO `GATE-VERDICT` line at all is NOT automatically a failure:
#     its exit code decides. That is deliberate and MEASURED. Making the line mandatory
#     by default was tried first and, on the first real run (8 gates, 2026-10-07), 6 of
#     8 lanes were reported FAIL/NO-VERDICT purely because none had adopted the line -
#     burying the one real failure. Pass -RequireVerdictLine to also demand the line.
#     THE CONSEQUENCE, STATED PLAINLY: a gate that fails every check, prints no verdict
#     line and exits 0 scores PASS. No aggregate can see inside a gate.
#   - A gate that tests nothing and exits 0 is indistinguishable from a working gate.
#     Only the gate's own author can close that. Nothing here can.
#   - Discovery is NON-recursive. A gate in a subdirectory is not in the population,
#     which is why the self-test arms live in `_selftest-gates\arm*\` and can never be
#     picked up by a real run of the `_main` population.
#   - Gates run SEQUENTIALLY, not in parallel. A hung lane holding an audio device or
#     a model load would otherwise make two lanes fail for one fault. This is a
#     correctness choice, and it is the reason a full run costs the SUM of the budgets.

[CmdletBinding()]
param(
    # Directory to glob. Default = the directory this script lives in (_main).
    [string]   $Dir,

    # Extra gate paths, appended to the discovered population.
    # A path that does not exist is a FAIL row, never a silent skip.
    [string[]] $Include = @(),

    # Gate names that MUST be present. Missing => FAIL row. Caller-supplied on purpose,
    # so the expectation list cannot rot inside this file.
    [string[]] $Expect = @(),

    # Per-gate wall-clock budget. Exceeding it is a FAIL named on stdout.
    [int]      $TimeoutSec = 300,

    # Require every gate to print a GATE-VERDICT line; absence is then a FAIL.
    # OFF BY DEFAULT, and the reason is MEASURED, not stylistic.
    #
    # On the first real run over the live population (2026-10-07, 8 gates, rc=1,
    # 568.5 s, `_all-gates-real.txt`) this was ON, and 6 of 8 gates were reported
    # FAIL/NO-VERDICT - not because they were broken, but because no lane adopted the
    # line. That buried the ONE real signal (_lane2-audio-gate, FAIL/EXIT1) under six
    # adoption failures, which is how a real failure gets missed.
    #
    # So the default is: the exit code is authoritative, AND a self-declared
    # GATE-VERDICT FAIL always wins over exit 0. That catches a gate lying about its
    # own failure (self-test ARM-D) at zero adoption cost. Turn this ON to also demand
    # the line from every gate - stricter, and noisy until the lanes adopt it.
    [switch]   $RequireVerdictLine,

    # Waive even the self-declared-FAIL rule, falling back to the exit code alone.
    # A documented hole; self-test ARM-G keeps it re-runnable.
    [switch]   $NoVerdictLine,

    # Where full per-gate stdout/stderr is written. Default _main\_all-gates-logs.
    [string]   $LogDir,

    # Run the built-in both-colour self-test and exit. Never touches real lanes.
    [switch]   $SelfTest
)

$ErrorActionPreference = 'Continue'

# The self-declared-FAIL rule is always on unless explicitly waived. Requiring the
# LINE from every gate is opt-in (see the -RequireVerdictLine note in the header).
$VerdictLineOn = (-not $NoVerdictLine)

# ------------------------------------------------------------------ constants
$SelfDir    = Join-Path $PSScriptRoot '_selftest-gates'
$PwshExe    = Join-Path $PSHOME 'pwsh.exe'
if (-not (Test-Path -LiteralPath $PwshExe)) { $PwshExe = (Get-Process -Id $PID).Path }
# House glob. Kept in ONE place so the self-test and the real run cannot diverge.
$GateFilter = '_lane*-gate.ps1'
# A gate may declare its own verdict with a line like `GATE-VERDICT PASS`.
$VerdictRe  = '(?im)^\s*GATE-VERDICT\s+(PASS|FAIL)\b'

function Say {
    param([string]$Text = '')
    [Console]::Out.WriteLine($Text)
}

# ------------------------------------------------------------------ discovery

# Things that LOOK like a gate to a human but that the strict glob will not match.
# Each one is a check that would otherwise never run, silently.
function Get-NearMissGates {
    param([Parameter(Mandatory)][string] $SearchDir)

    $out = New-Object System.Collections.Generic.List[object]
    # (a) DIRECTORIES named like a gate. A lane that did `mkdir _lane99-x-gate.ps1`
    #     instead of writing a file gets silence; this gets a FAIL row.
    foreach ($d in (Get-ChildItem -LiteralPath $SearchDir -Filter '_lane*gate*.ps1' -Directory -ErrorAction SilentlyContinue |
                    Sort-Object Name)) {
        $out.Add([pscustomobject]@{ Name=$d.Name; Path=$d.FullName; Bytes=0
                                    MtimeUtc=$d.LastWriteTimeUtc.ToString('o'); Why='a DIRECTORY named like a gate' })
    }
    # (b) MISSPELLED / misnamed FILES: `_lane*gate*.ps1` that the strict
    #     `_lane*-gate.ps1` glob skips - `gates.ps1`, `gate_x.ps1`, `gate.ps1.bak`.
    foreach ($f in (Get-ChildItem -LiteralPath $SearchDir -Filter '_lane*gate*.ps1' -File -ErrorAction SilentlyContinue |
                    Sort-Object Name)) {
        if ($f.Name -like $script:GateFilter) { continue }   # the real thing, already in
        $out.Add([pscustomobject]@{ Name=$f.Name; Path=$f.FullName; Bytes=$f.Length
                                    MtimeUtc=$f.LastWriteTimeUtc.ToString('o')
                                    Why=('does not match the glob ' + $script:GateFilter) })
    }
    return ,$out.ToArray()
}

# Population + WINDOW, resolved fresh on every run. No list is hardcoded anywhere.
function Get-GatePopulation {
    param([Parameter(Mandatory)][string] $SearchDir)

    $rows = New-Object System.Collections.Generic.List[object]
    if (Test-Path -LiteralPath $SearchDir) {
        # -File, NON-recursive.
        foreach ($f in (Get-ChildItem -LiteralPath $SearchDir -Filter $script:GateFilter -File |
                        Sort-Object Name)) {
            $rows.Add([pscustomobject]@{
                Name = $f.Name; Path = $f.FullName; Bytes = $f.Length
                MtimeUtc = $f.LastWriteTimeUtc.ToString('o')
                Source = 'glob'; Missing = $false; Why = ''
            })
        }
        # NEAR-MISS SCAN - a missing check must never be a SILENT skip.
        #
        # HOLE 3, found by the reviewer on 2026-10-07 and CONFIRMED: the `-File` glob
        # cannot see (a) a gate that is a DIRECTORY, (b) a gate whose name is
        # misspelled, e.g. `_lane12-typo-gates.ps1`, or (c) a stray `.bak`. Every one of
        # those is simply ABSENT from the population and from the printed table, which
        # is the same "absent check silently passing" defect this file exists to kill -
        # LAW 2 guarded `-Expect` and the zero-gate case but not UNDER-discovery.
        # Each near-miss becomes a FAIL row naming what was found and what was expected.
        foreach ($n in (Get-NearMissGates -SearchDir $SearchDir)) {
            $rows.Add([pscustomobject]@{
                Name = $n.Name; Path = $n.Path; Bytes = $n.Bytes
                MtimeUtc = $n.MtimeUtc; Source = 'near-miss'; Missing = $true; Why = $n.Why
            })
        }
    }
    foreach ($inc in $script:Include) {
        # An explicit include is a CLAIM that this gate exists. If it does not, that is
        # a FAIL row - the caller asked for a check and silently not running it is the
        # exact defect class this file exists to kill.
        $full = $inc
        if (-not [System.IO.Path]::IsPathRooted($full)) { $full = Join-Path $SearchDir $inc }
        $exists = Test-Path -LiteralPath $full -PathType Leaf
        $rows.Add([pscustomobject]@{
            Name = [System.IO.Path]::GetFileName($full); Path = $full
            Bytes = $(if ($exists) { (Get-Item -LiteralPath $full).Length } else { 0 })
            MtimeUtc = $(if ($exists) { (Get-Item -LiteralPath $full).LastWriteTimeUtc.ToString('o') } else { '' })
            Source = 'include'; Missing = (-not $exists); Why = 'included explicitly but the file does not exist'
        })
    }
    # Dedupe by path so one gate cannot be counted - or paid for - twice.
    $seen = @{}
    $out = New-Object System.Collections.Generic.List[object]
    foreach ($r in $rows) {
        $k = $r.Path.ToLowerInvariant()
        if ($seen.ContainsKey($k)) { continue }
        $seen[$k] = $true
        $out.Add($r)
    }
    return ,$out.ToArray()
}

# ------------------------------------------------------------------ one gate

# Read a gate as a child process. Returns a result OBJECT (never text), so nothing
# the gate prints can be mistaken for the aggregate's own output.
function Invoke-Gate {
    param(
        [Parameter(Mandatory)][string] $Path,
        [Parameter(Mandatory)][int]    $TimeoutSec,
        [Parameter(Mandatory)][string] $LogPath
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName               = $script:PwshExe
    $psi.UseShellExecute        = $false
    $psi.CreateNoWindow         = $true          # == CREATE_NO_WINDOW, hard rule 1
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    # stdin is closed immediately below: a gate that calls Read-Host gets EOF and
    # keeps going, instead of burning the whole timeout on a prompt nobody will answer.
    $psi.RedirectStandardInput  = $true
    $psi.WorkingDirectory       = (Split-Path -Parent $Path)
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $psi.StandardErrorEncoding  = [System.Text.Encoding]::UTF8
    foreach ($a in @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$Path)) {
        [void]$psi.ArgumentList.Add($a)
    }
    # Belt and braces for gates that shell out to python (LANE-BRIEF §8: cp1252 kills
    # non-ASCII output with UnicodeEncodeError).
    $psi.Environment['PYTHONIOENCODING'] = 'utf-8'
    $psi.Environment['PYTHONUTF8']       = '1'

    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi

    $sw         = [System.Diagnostics.Stopwatch]::StartNew()
    $startError = $null
    $outTask    = $null
    $errTask    = $null
    $hung       = $false
    $exitCode   = $null
    try {
        [void]$proc.Start()
        $proc.StandardInput.Close()
    } catch {
        $startError = $_.Exception.Message
    }

    if (-not $startError) {
        # Async reads BEFORE the wait: a pipe that fills while we are blocked in
        # WaitForExit is the classic way to make a slow gate look hung.
        $outTask = $proc.StandardOutput.ReadToEndAsync()
        $errTask = $proc.StandardError.ReadToEndAsync()

        if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
            $hung = $true
            # The WHOLE TREE. Killing only the root is what left the orphan writers
            # documented in receipt-15 §0.
            try { $proc.Kill($true) } catch { }
            [void]$proc.WaitForExit(5000)
        } else {
            [void]$proc.WaitForExit()      # flush the async readers
        }
        try { $exitCode = $proc.ExitCode } catch { $exitCode = $null }
    }
    $sw.Stop()

    $stdout = ''
    $stderr = ''
    if ($outTask) { try { if ($outTask.Wait(5000)) { $stdout = [string]$outTask.Result } } catch { } }
    if ($errTask) { try { if ($errTask.Wait(5000)) { $stderr = [string]$errTask.Result } } catch { } }

    $log = ''
    if ($stdout) { $log += "--- STDOUT ---`r`n$stdout" }
    if ($stderr) { $log += "--- STDERR ---`r`n$stderr" }
    if ($startError) { $log += "--- START ERROR ---`r`n$startError`r`n" }
    if ($log) {
        [System.IO.File]::WriteAllText($LogPath, $log, (New-Object System.Text.UTF8Encoding($false)))
    } elseif (Test-Path -LiteralPath $LogPath) {
        Remove-Item -LiteralPath $LogPath -Force -ErrorAction SilentlyContinue
    }

    try { $proc.Dispose() } catch { }

    return [pscustomobject]@{
        Path       = $Path
        ExitCode   = $exitCode
        Hung       = $hung
        DurationMs = $sw.Elapsed.TotalMilliseconds
        Stdout     = $stdout
        Stderr     = $stderr
        StartError = $startError
        LogPath    = $LogPath
    }
}

# The verdict law, in one readable place.
function Get-Verdict {
    param(
        [Parameter(Mandatory)][psobject] $R,
        [switch] $RequireLine,      # -RequireVerdictLine: absence of the line is a FAIL
        [switch] $TrustExitCodeOnly # -NoVerdictLine: ignore the declared verdict entirely
    )
    if ($R.StartError)        { return [pscustomobject]@{ Verdict='FAIL/START';     Detail=$R.StartError } }
    if ($R.Hung)              { return [pscustomobject]@{ Verdict='FAIL/TIMEOUT';   Detail='no exit within budget; process tree killed' } }
    if ($null -eq $R.ExitCode) { return [pscustomobject]@{ Verdict='FAIL/NOEXIT';   Detail='ended without a readable exit code' } }
    if ($R.ExitCode -ne 0)    { return [pscustomobject]@{ Verdict=('FAIL/EXIT{0}' -f $R.ExitCode); Detail='' } }

    # A gate that EXITS 0 while DECLARING A FAIL is contradicting itself, and the
    # declaration wins - unless -NoVerdictLine waives it, which is the one documented
    # hole and is exercised by self-test ARM-G so it can never quietly widen.
    #
    # EVERY verdict line is examined and ANY FAIL wins.
    # BUG FOUND 2026-10-07 by adversarial probe `_rev\dualverdict.txt`: this used
    # [regex]::Match, which returns the FIRST match, so a gate printing
    # `GATE-VERDICT PASS` then `GATE-VERDICT FAIL` scored PASS - the first line
    # talked the runner out of reading the second.
    if (-not $TrustExitCodeOnly) {
        $all = [regex]::Matches(($R.Stdout + "`n" + $R.Stderr), $script:VerdictRe)
        $anyFail = @($all | Where-Object { $_.Groups[1].Value -eq 'FAIL' })
        if ($anyFail.Count -gt 0) {
            $detail = 'exit 0 but the gate declared GATE-VERDICT FAIL'
            if ($all.Count -gt 1) {
                $detail = ('exit 0 but the gate declared FAIL on {0} of {1} GATE-VERDICT lines' -f `
                           $anyFail.Count, $all.Count)
            }
            return [pscustomobject]@{ Verdict='FAIL/VERDICT'; Detail=$detail }
        }
        if ($RequireLine -and $all.Count -eq 0) {
            return [pscustomobject]@{ Verdict='FAIL/NO-VERDICT'; Detail='exit 0 but no GATE-VERDICT line was printed' }
        }
    }
    return [pscustomobject]@{ Verdict='PASS'; Detail='' }
}

# ------------------------------------------------------------------ reporting

function Write-ResultTable {
    param([Parameter(Mandatory)][object[]] $Rows)
    $nameW = 4
    foreach ($r in $Rows) { if ($r.Name.Length -gt $nameW) { $nameW = $r.Name.Length } }
    $hdr = ('{0,-' + $nameW + '}  {1,-6}  {2,9}  {3}') -f 'GATE', 'EXIT', 'DURATION', 'VERDICT'
    Say $hdr
    Say ('-' * $hdr.Length)
    # The seconds column is formatted with the INVARIANT culture on purpose: this box
    # runs pt-BR, where `{2,8:N1}` renders 0.6 as "0,6" - a comma that reads like a
    # field separator and silently changes what the number says. Measured in the
    # self-test output on 2026-10-07.
    $inv = [System.Globalization.CultureInfo]::InvariantCulture
    foreach ($r in $Rows) {
        $ec = if ($null -eq $r.ExitCode) { 'n/a' } else { [string]$r.ExitCode }
        $secs = [double]$r.DurationMs / 1000.0
        Say (('{0,-' + $nameW + '}  {1,-6}  {2,8}s  {3}{4}') -f `
            $r.Name, $ec, $secs.ToString('F1', $inv), $r.Verdict,
            $(if ($r.Detail) { '  <- ' + $r.Detail } else { '' }))
    }
}

# ------------------------------------------------------------------ aggregate

function Invoke-Aggregate {
    param(
        [Parameter(Mandatory)][string] $SearchDir,
        [Parameter(Mandatory)][string] $Stamp,
        [Parameter(Mandatory)][int]    $PerGateTimeout
    )

    # THE WINDOW: one instant, taken once, before discovery. Every count below is
    # scoped to it. Hard rule 6.
    $window = (Get-Date).ToString('o')
    Say ("ALL-GATES window={0} dir={1} glob={2} timeout={3}s verdict-line={4}" -f `
        $window, $SearchDir, $GateFilter, $PerGateTimeout, `
        ('declare-FAIL-honoured={0}, line-required={1}' -f $script:VerdictLineOn, [bool]$RequireVerdictLine))
    Say ''

    $pop = Get-GatePopulation -SearchDir $SearchDir
    Say ("GATES POPULATION = {0}   (globbed + explicitly included, deduped by path)" -f $pop.Count)
    foreach ($g in $pop) {
        Say (("  [{0}] {1}  {2} B  mtime={3}  {4}") -f `
            $(if ($g.Missing) { 'MISSING' } else { 'ok' }), $g.Name, $g.Bytes, $g.MtimeUtc, $g.Source)
    }
    Say ''

    # LAW 2: no checks at all is a FAIL, never a vacuous PASS.
    if ($pop.Count -eq 0) {
        Say 'FAIL NO-GATES: the glob matched 0 gates. A project with no checks is not green, it is UNVERIFIED.'
        Say ''
        Say 'ALL-GATES FAIL'
        return 1
    }

    $logRoot = $LogDir
    if (-not $logRoot) { $logRoot = Join-Path $PSScriptRoot '_all-gates-logs' }
    $logRoot = Join-Path $logRoot $Stamp
    if (-not (Test-Path -LiteralPath $logRoot)) {
        [void](New-Item -ItemType Directory -Path $logRoot -Force)
    }

    $rows = New-Object System.Collections.Generic.List[object]
    foreach ($g in $pop) {
        if ($g.Missing) {
            $rows.Add([pscustomobject]@{
                Name=$g.Name; ExitCode=$null; DurationMs=0.0
                Verdict='FAIL/MISSING'; Detail=$(if ($g.Why) { $g.Why } else { 'registered but the file does not exist' })
            })
            continue
        }
        $raw = Invoke-Gate -Path $g.Path -TimeoutSec $PerGateTimeout `
                            -LogPath (Join-Path $logRoot ($g.Name + '.log'))
        $v = Get-Verdict -R $raw -RequireLine:([bool]$RequireVerdictLine) `
                            -TrustExitCodeOnly:(-not $script:VerdictLineOn)
        $rows.Add([pscustomobject]@{
            Name=$g.Name; ExitCode=$raw.ExitCode; DurationMs=$raw.DurationMs
            Verdict=$v.Verdict; Detail=$v.Detail
        })

        if ($raw.Hung) {
            # Requirement 4: name the hung gate, loudly, on its own line.
            Say ("HUNG GATE: {0}  exceeded {1}s with no exit; process tree killed; marked FAIL." -f `
                $g.Name, $PerGateTimeout)
        }
        # Only reachable when the requirement is waived (-NoVerdictLine): there the exit
        # code is the only signal, so any disagreement with the gate's own declared
        # verdict is named rather than buried.
        if (-not $script:VerdictLineOn) {
            $mm = [regex]::Matches(($raw.Stdout + "`n" + $raw.Stderr), $script:VerdictRe)
            if ($mm.Count -eq 0) {
                Say ("  ! {0} printed no GATE-VERDICT line - its exit code was the ONLY signal." -f $g.Name)
            } elseif (@($mm | Where-Object { $_.Groups[1].Value -eq 'FAIL' }).Count -gt 0) {
                Say ("  ! {0} printed GATE-VERDICT FAIL but exited {1}; the aggregate followed the EXIT CODE. Drop -NoVerdictLine to close this hole." -f `
                    $g.Name, $raw.ExitCode)
            }
        }
        if ($v.Verdict -like 'FAIL*' -and $raw.Stderr) {
            foreach ($l in @($raw.Stderr -split "`r?`n" | Where-Object { $_ -ne '' } | Select-Object -Last 5)) {
                Say ("    | {0}" -f $l)
            }
        }
    }

    # A named expectation that never appeared in the population is a FAIL row.
    foreach ($e in $Expect) {
        if (@($pop | Where-Object { $_.Name -eq $e -and -not $_.Missing }).Count -eq 0) {
            $rows.Add([pscustomobject]@{
                Name=$e; ExitCode=$null; DurationMs=0.0
                Verdict='FAIL/MISSING'; Detail='expected by -Expect but not in the population'
            })
        }
    }

    Say ''
    Say 'RESULT TABLE'
    Write-ResultTable -Rows $rows.ToArray()
    Say ''

    $failed = @($rows | Where-Object { $_.Verdict -ne 'PASS' })
    Say ("SUMMARY gates={0} passed={1} failed={2}  logs={3}" -f `
        $rows.Count, ($rows.Count - $failed.Count), $failed.Count, $logRoot)
    if ($failed.Count -gt 0) {
        foreach ($f in $failed) { Say ("  FAILED: {0}  {1}" -f $f.Name, $f.Verdict) }
        Say ''
        Say 'ALL-GATES FAIL'
        return 1
    }
    Say ''
    Say 'ALL-GATES PASS'
    return 0
}

# ------------------------------------------------------------------ self-test
# Proves the aggregate can say NO. A gate that has only ever printed PASS is not a
# gate. Every arm is a REAL child invocation of the SAME code path the real run
# uses - nothing here is a stub, a mock, or an assertion of my own arithmetic.
#
# Each arm gets its OWN directory so each glob sees exactly one population. Without
# that isolation ARM A would also pick up the broken and the hanging gate.
function Invoke-SelfTest {
    $fails = 0

    function Arm {
        param(
            [string]   $Label,
            [string]   $ExpectLine,
            [int]      $ExpectRc,
            [string]   $DirArg,
            [string[]] $ExtraArgs = @(),
            [switch]   $VerdictLine,
            [switch]   $NoVerdictLine,
            [string]   $ExpectContains = ''
        )
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName               = $script:PwshExe
        $psi.UseShellExecute        = $false
        $psi.CreateNoWindow         = $true
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError  = $true
        $psi.RedirectStandardInput  = $true
        $psi.WorkingDirectory       = $script:PSScriptRoot
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding  = [System.Text.Encoding]::UTF8
        $args = @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',
                  (Join-Path $script:PSScriptRoot 'all-gates.ps1'),'-Dir',$DirArg)
        $args += $ExtraArgs
        if ($VerdictLine) { $args += '-RequireVerdictLine' }
        if ($NoVerdictLine) { $args += '-NoVerdictLine' }
        foreach ($a in $args) { [void]$psi.ArgumentList.Add($a) }

        $p = New-Object System.Diagnostics.Process
        $p.StartInfo = $psi
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        [void]$p.Start()
        $p.StandardInput.Close()
        $ot = $p.StandardOutput.ReadToEndAsync()
        $et = $p.StandardError.ReadToEndAsync()
        [void]$p.WaitForExit(300000)
        $sw.Stop()
        $o = ''; $e = ''
        try { if ($ot.Wait(5000)) { $o = [string]$ot.Result } } catch { }
        try { if ($et.Wait(5000)) { $e = [string]$et.Result } } catch { }
        $rc = $p.ExitCode
        try { $p.Dispose() } catch { }

        $lines = @(($o + "`n" + $e) -split "`r?`n" | Where-Object { $_ -ne '' })
        $final = if ($lines.Count -gt 0) { $lines[-1].Trim() } else { '(no output)' }
        $okLine = ($final -eq $ExpectLine)
        $okRc   = if ($ExpectRc -eq 0) { ($rc -eq 0) } else { ($rc -ne 0) }
        $okTxt  = $true
        if ($ExpectContains) { $okTxt = (($o + "`n" + $e) -like ('*' + $ExpectContains + '*')) }
        $ok = $okLine -and $okRc -and $okTxt
        Say ("{0,-26} rc={1,-4} final='{2}'  expect='{3}' rcExpectNonZero={4}  => {5}" -f `
            $Label, $rc, $final, $ExpectLine, (-not $ExpectRc), $(if ($ok) { 'GREEN' } else { 'RED' }))
        foreach ($l in $lines) { Say ("    | {0}" -f $l) }
        Say ''
        if (-not $ok) { return 1 }
        return 0
    }

    Say '=== SELF-TEST: the aggregate gate, both colours ==='
    Say ("Self-test arms live in {0}\arm* and are NEVER in the real _main population (the glob is non-recursive)." -f $SelfDir)
    Say ''

    $fails += Arm -Label 'ARM-A green is PASS' -ExpectLine 'ALL-GATES PASS' -ExpectRc 0 `
        -DirArg (Join-Path $SelfDir 'armA_good')
    $fails += Arm -Label 'ARM-B broken is FAIL' -ExpectLine 'ALL-GATES FAIL' -ExpectRc 1 `
        -DirArg (Join-Path $SelfDir 'armB_broken')
    $fails += Arm -Label 'ARM-C no gates is FAIL' -ExpectLine 'ALL-GATES FAIL' -ExpectRc 1 `
        -DirArg (Join-Path $SelfDir 'armC_empty')
    # ARM-D with NO extra flag: a gate that exits 0 while declaring GATE-VERDICT FAIL.
    # The DEFAULT must catch it - the declaration wins over the exit code.
    $fails += Arm -Label 'ARM-D exit0 but FAIL' -ExpectLine 'ALL-GATES FAIL' -ExpectRc 1 `
        -DirArg (Join-Path $SelfDir 'armD_silentfail')
    # ARM-D2: a gate that prints NO GATE-VERDICT line passes on its exit code by
    # default, and is a FAIL/NO-VERDICT under -RequireVerdictLine. armA_good is NOT
    # usable here - it prints the line, so it passes either way. armI_launder's gate is
    # the right fixture: exit 0, no verdict line.
    $fails += Arm -Label 'ARM-D2 no line passes' -ExpectLine 'ALL-GATES PASS' -ExpectRc 0 `
        -DirArg (Join-Path $SelfDir 'armI_launder')
    $fails += Arm -Label 'ARM-D2b line required' -ExpectLine 'ALL-GATES FAIL' -ExpectRc 1 `
        -DirArg (Join-Path $SelfDir 'armI_launder') -VerdictLine
    $fails += Arm -Label 'ARM-E hang is FAIL' -ExpectLine 'ALL-GATES FAIL' -ExpectRc 1 `
        -DirArg (Join-Path $SelfDir 'armE_hang') -ExtraArgs @('-TimeoutSec','5') `
        -ExpectContains 'HUNG GATE:'
    $fails += Arm -Label 'ARM-F absent expect FAIL' -ExpectLine 'ALL-GATES FAIL' -ExpectRc 1 `
        -DirArg (Join-Path $SelfDir 'armA_good') -ExtraArgs @('-Expect','_lane99-nope-gate.ps1')
    # ARM-G: the documented opt-out. Same lying gate, -NoVerdictLine, and the
    # aggregate reports ALL-GATES PASS with rc=0. This arm exists so the LIMIT is
    # re-runnable evidence and not a claim in a comment: the hole is real, reachable
    # by one flag, and named every time it is taken.
    $fails += Arm -Label 'ARM-G opt-out hole' -ExpectLine 'ALL-GATES PASS' -ExpectRc 0 `
        -DirArg (Join-Path $SelfDir 'armD_silentfail') -NoVerdictLine

    Say ("SELFTEST arms={0} failed={1}   [expect 0]" -f 8, $fails)
    if ($fails -eq 0) { Say 'SELFTEST PASS' } else { Say 'SELFTEST FAIL' }
    return $fails
}

# ------------------------------------------------------------------ entry point
if ($SelfTest) { exit (Invoke-SelfTest) }

$searchDir = $Dir
if (-not $searchDir) { $searchDir = $PSScriptRoot }
$searchDir = [System.IO.Path]::GetFullPath($searchDir)
exit (Invoke-Aggregate -SearchDir $searchDir -Stamp (Get-Date).ToString('yyyyMMdd-HHmmss') -PerGateTimeout $TimeoutSec)