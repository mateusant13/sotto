<#
.SYNOPSIS
    Permanent regression battery for the `--audio` production fix (lane audiofix).

.DESCRIPTION
    The bug this pins: `--audio FILE` WITHOUT `--selftest` used to be DISCARDED
    (`args.audio if args.selftest else None`), so the run fell through to the LIVE
    capture branch — the room, not the file, rc=3, 0 captions, devices spinning,
    no error anywhere. One manual run per arm is not a battery. This runs every
    arm as a SUBPROCESS and asserts on the exit code AND on the JSONL contract.

    Two rules make the output worth something:

      1. ASSERT ON CONTENT, NOT JUST rc. A green exit code was the original
         symptom. Every arm checks the `mode` field of the boot line, the caption
         count, and (where it applies) that the reported path is in the output.

      2. THE GATE MUST BE ABLE TO SAY NO. `-SelftestExpectedMode live` deliberately
         arms a WRONG expectation for every arm that asserts a mode, so the whole
         table goes red on demand. A battery that cannot fail is decoration.

    NOT MUTATED: this script only READS the worker it is pointed at. Pass
    `-Worker H:\sotto\worker\sotto_worker.py` to test the pre-fix code (branch
    feat/build-verify-1), or the main-branch path to test the shipped fix.

.PARAMETER Worker
    Path to sotto_worker.py under test. Read-only.

.PARAMETER SelftestExpectedMode
    'file' (the real contract), 'live' (DELIBERATELY WRONG — proves the gate is
    live), or '' to use each arm's own expectation.

.PARAMETER RedArmProof
    yes|no, printed in the final verdict line. 'yes' only after a wrong-armed run
    has actually been captured.

.EXAMPLE
    pwsh -File audio_battery.ps1 -Label green-main
    pwsh -File audio_battery.ps1 -SelftestExpectedMode live -Label red-wrong-armed -RedArmProof yes
#>
[CmdletBinding()]
param(
    [string]$Worker = 'H:\sotto-wt\ArbV8\worker\sotto_worker.py',
    [string]$Python = 'python',
    [string]$Model  = 'H:\sotto\worker\models\nemotron-3.5-asr-streaming-0.6b-int8',
    [string]$Sample = 'H:\sotto\worker\assets\sample1.flac',
    [int]   $ArmTimeoutS = 180,
    # Injected into EVERY arm. File mode ignores it; a run that wrongly falls
    # through to LIVE capture stops itself instead of spinning the devices until
    # the harness kills it.
    [int]   $MaxSeconds = 15,
    [string]$SelftestExpectedMode = '',
    [string]$RedArmProof = 'no',
    [string]$OutDir = '',
    [string]$Label  = 'run'
)

$ErrorActionPreference = 'Stop'
# Command 1 of this lane's brief, kept alive for every run made by this script.
$env:TMPDIR = 'I:\cc-tmp'

if (-not (Test-Path $Worker))  { throw "worker not found: $Worker" }
if (-not (Test-Path $Model))   { throw "model dir not found: $Model" }
if (-not (Test-Path $Sample))  { throw "sample not found: $Sample" }
$pythonExe = (Get-Command $Python -ErrorAction Stop).Source

$stamp    = Get-Date -Format 'yyyyMMdd-HHmmss'
$runDir   = if ($OutDir) { $OutDir } else { Join-Path $PSScriptRoot "runs\$Label-$stamp" }
New-Item -ItemType Directory -Force -Path $runDir | Out-Null

$missing  = 'H:\sotto\worker\assets\nope-does-not-exist.flac'
$missingSp = 'H:\sotto\worker\assets\my missing clip.wav'
$adir     = Split-Path $Sample -Parent

# ── the arms ──────────────────────────────────────────────────────────────────
# ExpMode ''   = do not assert a mode (the arm is about something else)
# ForbidMode   = the arm's whole point is "must not fall back to live capture"
# ArgvMustNot  = the BOOT line's own argv, i.e. what the worker was actually given
$arms = @(
    [pscustomobject]@{ Name='a-audio-good';        Desc='--audio FILE alone must be FILE mode (the fixed bug)'
        Args=@('--audio', $Sample); Env=@{}; ExpRc=0; ExpMode='file'; ForbidMode='live'
        MinCapt=1; MaxCapt=0; MustMention=''; MustNot=''; ArgvMustNot=@() }

    [pscustomobject]@{ Name='b-audio-missing';     Desc='--audio MISSING must refuse, not fall through to live'
        Args=@('--audio', $missing); Env=@{}; ExpRc=2; ExpMode=''; ForbidMode='live'
        MinCapt=0; MaxCapt=0; MustMention='nope-does-not-exist'; MustNot=''; ArgvMustNot=@() }

    [pscustomobject]@{ Name='c-selftest-bare';     Desc='--selftest alone, argv must carry no --audio'
        Args=@('--selftest'); Env=@{}; ExpRc=0; ExpMode='file'; ForbidMode='live'
        MinCapt=1; MaxCapt=0; MustMention=''; MustNot=''; ArgvMustNot=@('--audio') }

    [pscustomobject]@{ Name='d-selftest-plus-audio'; Desc='--selftest --audio FILE stays file mode'
        Args=@('--selftest', '--audio', $Sample); Env=@{}; ExpRc=0; ExpMode='file'; ForbidMode='live'
        MinCapt=1; MaxCapt=0; MustMention=''; MustNot=''; ArgvMustNot=@() }

    [pscustomobject]@{ Name='e-env-audio';         Desc='SOTTO_AUDIO_FILE with no flags is file mode'
        Args=@(); Env=@{ SOTTO_AUDIO_FILE=$Sample }; ExpRc=0; ExpMode='file'; ForbidMode='live'
        MinCapt=1; MaxCapt=0; MustMention=''; MustNot=''; ArgvMustNot=@('--audio') }

    [pscustomobject]@{ Name='f-audio-empty';       Desc='--audio "" is a VALUE: must be refused, never live'
        Args=@('--audio', ''); Env=@{}; ExpRc=2; ExpMode=''; ForbidMode='live'
        MinCapt=0; MaxCapt=0; MustMention=''; MustNot='Traceback \(most recent call last\)'; ArgvMustNot=@() }

    [pscustomobject]@{ Name='g-audio-directory';   Desc='--audio <dir> must refuse cleanly, not raise a traceback'
        Args=@('--audio', $adir); Env=@{}; ExpRc=2; ExpMode=''; ForbidMode='live'
        MinCapt=0; MaxCapt=0; MustMention=''; MustNot='Traceback \(most recent call last\)'; ArgvMustNot=@() }

    [pscustomobject]@{ Name='h-audio-missing-spaces'; Desc='missing path WITH SPACES must refuse, not go live'
        Args=@('--audio', $missingSp); Env=@{}; ExpRc=2; ExpMode=''; ForbidMode='live'
        MinCapt=0; MaxCapt=0; MustMention='my missing clip.wav'; MustNot=''; ArgvMustNot=@() }

    [pscustomobject]@{ Name='i-env-missing';       Desc='SOTTO_AUDIO_FILE pointing at nothing must refuse'
        Args=@(); Env=@{ SOTTO_AUDIO_FILE=$missing }; ExpRc=2; ExpMode=''; ForbidMode='live'
        MinCapt=0; MaxCapt=0; MustMention='nope-does-not-exist'; MustNot=''; ArgvMustNot=@() }

    [pscustomobject]@{ Name='j-env-beats-flag';    Desc='documented precedence: SOTTO_AUDIO_FILE wins over --audio'
        Args=@('--audio', $Sample); Env=@{ SOTTO_AUDIO_FILE=$missing }; ExpRc=2; ExpMode=''; ForbidMode='live'
        MinCapt=0; MaxCapt=0; MustMention='nope-does-not-exist'; MustNot=''; ArgvMustNot=@() }
)

function Invoke-Arm {
    param($Arm, [int]$Index)

    $outFile = Join-Path $runDir ("{0:d2}-{1}.out" -f $Index, $Arm.Name)
    $errFile = Join-Path $runDir ("{0:d2}-{1}.err" -f $Index, $Arm.Name)

    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName               = $pythonExe
    $psi.WorkingDirectory       = (Split-Path -Parent (Resolve-Path $Worker))
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.UseShellExecute        = $false
    # ORDER MATTERS: the SCRIPT PATH comes first. `python --audio X worker.py`
    # is read by the interpreter's own parser ("unknown option", rc=2), which is
    # what this battery did on its first run — caught, because an arm that returns
    # rc=2 in 0 s cannot also produce captions.
    foreach ($a in (@($Worker) + $Arm.Args + @('--model', $Model, '--max-seconds', "$MaxSeconds"))) {
        [void]$psi.ArgumentList.Add([string]$a)
    }
    # An inherited SOTTO_AUDIO_FILE would silently make every "no flags" arm a
    # file run, so the environment each arm sees is stated, never inherited.
    [void]$psi.Environment.Remove('SOTTO_AUDIO_FILE')
    foreach ($k in $Arm.Env.Keys) { $psi.Environment[$k] = [string]$Arm.Env[$k] }

    $t0 = Get-Date
    $proc = [System.Diagnostics.Process]::new()
    $proc.StartInfo = $psi
    [void]$proc.Start()
    # Read both pipes concurrently: a worker whose stderr fills while we wait on
    # stdout would otherwise deadlock, and the symptom would look like a hang.
    $soTask = $proc.StandardOutput.ReadToEndAsync()
    $seTask = $proc.StandardError.ReadToEndAsync()
    $exited = $proc.WaitForExit($ArmTimeoutS * 1000)
    $timedOut = -not $exited
    if ($timedOut) {
        try { $proc.Kill($true) } catch { }
        [void]$proc.WaitForExit(5000)
    }
    $so = $soTask.GetAwaiter().GetResult()
    $se = $seTask.GetAwaiter().GetResult()
    $rc = if ($timedOut) { -999 } else { $proc.ExitCode }
    $t1 = Get-Date

    Set-Content -Path $outFile -Value $so -Encoding utf8NoBOM
    Set-Content -Path $errFile -Value $se -Encoding utf8NoBOM

    # The contract is JSON Lines: count the caption objects, do not grep for a
    # word that may legitimately appear inside a caption's own text.
    $captions = 0; $mode = 'none'; $argv = @()
    foreach ($line in ($so -split "`r?`n")) {
        if (-not $line.Trim()) { continue }
        try { $o = $line | ConvertFrom-Json -ErrorAction Stop } catch { continue }
        if ($o.type -eq 'caption') { $captions++ }
        if ($o.state -eq 'boot' -and $o.stage -eq 'start') { $mode = [string]$o.mode; $argv = @($o.argv) }
    }
    [pscustomobject]@{
        Rc=$rc; TimedOut=$timedOut; Captions=$captions; Mode=$mode; Argv=$argv
        Out=$so; Err=$se; Start=$t0; End=$t1; OutFile=$outFile; ErrFile=$errFile
    }
}

function Test-Arm {
    param($Arm, $Obs)

    $fail = [System.Collections.Generic.List[string]]::new()
    $combined = $Obs.Out + "`n" + $Obs.Err

    if ($Obs.TimedOut) { $fail.Add("timeout after ${ArmTimeoutS}s (a live branch that would not stop)") }

    $expRc = @($Arm.ExpRc)
    if ($expRc -notcontains $Obs.Rc) {
        $fail.Add("rc=$($Obs.Rc), expected $($expRc -join '|')")
    }

    # The deliberate-wrong-expectation switch. Applied to every arm that asserts a
    # mode, so arming it wrong takes the WHOLE table red, not one row.
    $expMode = $Arm.ExpMode
    if ($SelftestExpectedMode -and $Arm.ExpMode) { $expMode = $SelftestExpectedMode }
    if ($expMode -and $Obs.Mode -ne $expMode) {
        $fail.Add("mode='$($Obs.Mode)', expected '$expMode'")
    }
    if ($Arm.ForbidMode -and $Obs.Mode -eq $Arm.ForbidMode) {
        $fail.Add("FELL BACK TO $($Arm.ForbidMode) — the original defect")
    }
    # Independent of the boot line: a run that actually opened a device said so.
    if ($Arm.ForbidMode -and $combined -match '"state":\s*"capture-started"') {
        $fail.Add("emitted capture-started — live capture was entered")
    }

    if ($Obs.Captions -lt $Arm.MinCapt) {
        $fail.Add("captions=$($Obs.Captions), expected >= $($Arm.MinCapt)")
    }
    if ($Obs.MaxCapt -gt 0 -and $Obs.Captions -gt $Arm.MaxCapt) {
        $fail.Add("captions=$($Obs.Captions), expected <= $($Arm.MaxCapt)")
    }
    if ($Arm.MustMention -and -not $combined.ToLower().Contains($Arm.MustMention.ToLower())) {
        $fail.Add("output never names '$($Arm.MustMention)'")
    }
    if ($Arm.MustNot -and $combined -match $Arm.MustNot) {
        $fail.Add("output matches forbidden /$($Arm.MustNot)/")
    }
    foreach ($tok in $Arm.ArgvMustNot) {
        if ($Obs.Argv -contains $tok) { $fail.Add("argv contains '$tok'") }
    }

    [pscustomobject]@{
        Pass = ($fail.Count -eq 0)
        Why  = ($fail -join '; ')
    }
}

# ── run every arm ─────────────────────────────────────────────────────────────
$windowStart = Get-Date
$results = @()
$i = 0
foreach ($arm in $arms) {
    $i++
    Write-Host ("[{0:d2}/{1}] {2} ..." -f $i, $arms.Count, $arm.Name)
    $obs = Invoke-Arm -Arm $arm -Index $i
    $verdict = Test-Arm -Arm $arm -Obs $obs
    $results += [pscustomobject]@{
        Name = $arm.Name; Desc = $arm.Desc
        ExpRc = $arm.ExpRc; ExpMode = $arm.ExpMode; Obs = $obs; Pass = $verdict.Pass; Why = $verdict.Why
    }
    Write-Host ("      {0}  rc={1} mode={2} captions={3} {4}s" -f `
        $(if ($verdict.Pass) { 'PASS' } else { 'FAIL' }), $obs.Rc, $obs.Mode, $obs.Captions, `
        [math]::Round(($obs.End - $obs.Start).TotalSeconds, 1))
    if (-not $verdict.Pass) { Write-Host "      why: $($verdict.Why)" }
}
$windowEnd = Get-Date

$pass = @($results | Where-Object Pass).Count
$fail = @($results | Where-Object { -not $_.Pass }).Count
$totalCaptions = ($results | ForEach-Object { $_.Obs.Captions } | Measure-Object -Sum).Sum

# ── report ────────────────────────────────────────────────────────────────────
$md = [System.Collections.Generic.List[string]]::new()
$md.Add("# audio_battery.ps1 — run '$Label'")
$md.Add("")
$md.Add("- worker: ``$Worker``")
$md.Add("- model: ``$Model``")
$md.Add("- expected-mode override: ``$(if ($SelftestExpectedMode) { $SelftestExpectedMode } else { '(none, per-arm contract)' })``")
$md.Add("- WINDOW: ``$($windowStart.ToString('yyyy-MM-dd HH:mm:ss'))`` → ``$($windowEnd.ToString('yyyy-MM-dd HH:mm:ss'))`` (host local)")
$md.Add("- POPULATION: **$($results.Count) arms, $pass pass, $fail fail, $totalCaptions captions total, 1 run per arm**")
$md.Add("- per-arm outputs: same directory, ``NN-<arm>.out`` / ``.err``")
$md.Add("")
$md.Add("| arm | expected rc | expected mode | observed rc | observed mode | captions | PASS/FAIL | POPULATION | WINDOW |")
$md.Add("|---|---|---|---|---|---|---|---|---|")
foreach ($r in $results) {
    $o = $r.Obs
    $md.Add("| $($r.Name) | $($r.ExpRc) | $(if ($r.ExpMode) { $r.ExpMode } else { '(not asserted)' }) | $($o.Rc) | $($o.Mode) | $($o.Captions) | $(if ($r.Pass) { 'PASS' } else { '**FAIL**' }) | $($o.Captions) captions / 1 run | $($o.Start.ToString('HH:mm:ss'))→$($o.End.ToString('HH:mm:ss')) |")
}
$md.Add("")
foreach ($r in $results) {
    $md.Add("### $($r.Name)")
    $md.Add("")
    $md.Add("$($r.Desc).")
    if ($r.Why) { $md.Add("") ; $md.Add("**FAILED**: $($r.Why)") }
    $md.Add("")
    $md.Add("argv as the worker saw it: ``$($r.Obs.Argv -join ' ')``")
    $md.Add("")
}
$verdictLine = "BATTERY VERDICT: $($results.Count) ARMS, $pass PASS, $fail FAIL (red-arm proof: $RedArmProof)"
$md.Add('```')
$md.Add($verdictLine)
$md.Add('```')

$mdPath = Join-Path $runDir 'REPORT.md'
Set-Content -Path $mdPath -Value ($md -join "`n") -Encoding utf8NoBOM
$results | Select-Object Name, @{n='rc';e={$_.Obs.Rc}}, @{n='mode';e={$_.Obs.Mode}},
    @{n='captions';e={$_.Obs.Captions}}, Pass, Why |
    ConvertTo-Json -Depth 4 | Set-Content -Path (Join-Path $runDir 'report.json') -Encoding utf8NoBOM

Write-Host ""
Write-Host "report: $mdPath"
Write-Host $verdictLine
exit ([int]($fail -gt 0))