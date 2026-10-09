#Requires -Version 7
<#
.SYNOPSIS
    LANE22 GATE -- the rolling clip store: layout, retention, disk-full behaviour, recovery.

.DESCRIPTION
    One named arm per acceptance criterion, each a SEPARATE OS process so a crash in one arm
    cannot take the gate with it.  Every arm runs against a REAL directory tree on H: --
    real files, real byte counts, a real `shutil.disk_usage` on the real volume.  Nothing here
    is mocked, because a retention policy tested against a mock is a policy that has never
    been tested.

      ARM 0  the LAYOUT contract: clip ids are pure, paths derive from the id and parse back
             to it, the commit is atomic, an unknown layout_version is REFUSED, and the whole
             index-key population is rebuildable from disk alone (no db, no in-memory state)
      ARM A  THE HEADLINE -- eviction against a real tree, with the BYTES FREED stated by two
             independent measures (the sum of the unlinks and a re-walk of the store), the
             store's POPULATION, and the WINDOW it acted on
      ARM B  DISK FULL -- eviction cannot free enough: the write is REFUSED, the refusal is
             LOUD on stdout, the store does not grow, the library survives, and the
             rate-limited alarm's SUPPRESSIONS are counted rather than hidden
      ARM C  RECONCILIATION -- every crash state (partial-committed, partial-uncommitted,
             orphan, key-without-media) becomes committed or ceases to exist, and the index
             never claims a file that is not there
      ARM E  the budget IN FORCE and where it came from: explicit > env > default, with a
             refusal (never a clamp) for any unusable value, and the byte budget translated
             into minutes of capture at the MEASURED rate of this box
      ARM D  THE CONTROL -- the same package copied to disk with ONE guarantee reverted per
             mutant.  ARM D0 is the un-mutated copy and MUST BE GREEN, so the only difference
             between green and red in D1..D4 is the reverted guard.

    ARM D0 is what makes ARM D a control rather than a demonstration: a mutated run that goes
    red because the copy is in a different directory, or because the mutant broke an import,
    would be indistinguishable from a run that went red for the intended reason.

    House rules obeyed here:
      rule 1 -- every python process is created with CreateNoWindow + WindowStyle Hidden, so
                running this gate never puts a console on the owner's screen
      rule 2 -- no native command is ever PIPED for its exit code.  Each arm runs through
                System.Diagnostics.Process and its REAL .ExitCode is read.
      rule 3 -- native H:\ paths only

.EXAMPLE
    pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane22-storage-gate.ps1
#>
[CmdletBinding()]
param(
    [string] $Python = "",                 # full path to python.exe; default: the `py` launcher
    [string] $Work = "",                   # scratch dir; default: _main\_lane22-run
    [int]    $TimeoutSec = 900
)

$ErrorActionPreference = 'Stop'
$Repo    = Split-Path -Parent $PSScriptRoot
$Src     = Join-Path $Repo 'src'
$Pkg     = Join-Path $Src 'storage'
if (-not $Work) { $Work = Join-Path $Repo '_main\_lane22-run' }
$Env:PYTHONIOENCODING       = 'utf-8'      # or the Portuguese dies on cp1252
$Env:PYTHONDONTWRITEBYTECODE = '1'         # and no lane leaves a __pycache__ behind

if ($Python) { $Exe = $Python; $Prefix = @() }
else         { $Exe = 'py';      $Prefix = @('-3') }

foreach ($f in @('layout.py', 'retention.py', '__init__.py')) {
    if (-not (Test-Path (Join-Path $Pkg $f))) { Write-Error "lane22 gate: missing storage\$f"; exit 2 }
}
New-Item -ItemType Directory -Force -Path $Work | Out-Null

# --------------------------------------------------------------------------------------------
# Invoke-Py -- one child process, hidden, exit code from the PROCESS OBJECT (house rule 2).
# $Cwd is the child's working directory, which is how the control arm makes `import storage`
# resolve to the mutated COPY rather than to the repository.
# --------------------------------------------------------------------------------------------
function Invoke-Py {
    param([string[]] $PyArgs, [string] $LogName, [string] $Cwd = $Src)
    $log  = Join-Path $Work $LogName
    $outF = "$log.stdout.txt"
    $errF = "$log.stderr.txt"
    $psi  = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName               = $Exe
    foreach ($a in ($Prefix + $PyArgs)) { [void] $psi.ArgumentList.Add($a) }
    $psi.WorkingDirectory       = $Cwd
    $psi.UseShellExecute        = $false
    $psi.CreateNoWindow         = $true      # house rule 1
    $psi.WindowStyle            = 'Hidden'   # house rule 1
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError  = $true
    $psi.Environment['PYTHONIOENCODING']     = 'utf-8'
    $psi.Environment['PYTHONDONTWRITEBYTECODE'] = '1'
    $proc = [System.Diagnostics.Process]::Start($psi)
    # Both streams drained concurrently: reading one to the end first can deadlock the child
    # when the OTHER pipe fills.
    $so = $proc.StandardOutput.ReadToEndAsync()
    $se = $proc.StandardError.ReadToEndAsync()
    if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
        try { $proc.Kill() } catch { }
        Write-Host "  (arm exceeded ${TimeoutSec}s and was killed)"
        return [pscustomobject]@{ Rc = 124; Log = $log; Out = ''; Err = "timeout"; Report = $null }
    }
    $out = $so.Result
    $err = $se.Result
    Set-Content -Path $outF -Value $out -Encoding UTF8
    Set-Content -Path $errF -Value $err -Encoding UTF8
    Set-Content -Path $log  -Value ($out + "`n--- STDERR ---`n" + $err) -Encoding UTF8
    $rep = $null
    $json = ($PyArgs | Where-Object { $_ -like '*.json' } | Select-Object -First 1)
    if ($json -and (Test-Path $json)) {
        try { $rep = Get-Content $json -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $rep = $null }
    }
    return [pscustomobject]@{ Rc = $proc.ExitCode; Log = $log; Out = $out; Err = $err; Report = $rep }
}

function Read-Report { param([string] $Path) if (Test-Path $Path) { try { Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $null } } else { $null } }

$summary = [System.Collections.Generic.List[object]]::new()
$failed  = 0
function Add-Arm {
    param([string] $Name, [bool] $Ok, [string] $Detail, $Report)
    if (-not $Ok) { $script:failed++ }
    $n = if ($Report -and $Report.PSObject.Properties.Name -contains 'n_checks') { $Report.n_checks } else { $null }
    $f = if ($Report -and $Report.PSObject.Properties.Name -contains 'n_failed') { $Report.n_failed } else { $null }
    $summary.Add([pscustomobject]@{ Arm = $Name; Ok = $Ok; Checks = $n; Failed = $f; Population = $Detail })
    $mark = if ($Ok) { 'PASS' } else { 'RED ' }
    $chk  = if ($null -ne $n) { "$f/$n check(s) failed" } else { 'no report' }
    Write-Host ("  ARM {0,-4} {1}  {2,-58} {3}" -f $Name, $mark, $Detail, $chk)
}

Write-Host "LANE22 GATE -- the rolling clip store (layout / retention / disk-full / recovery)"
Write-Host "  repo   : $Repo"
Write-Host "  python : $Exe $($Prefix -join ' ')"
Write-Host "  work   : $Work"

# --------------------------------------------------------------------------------------------
Write-Host "`n[ARM 0] the layout contract -- derivation, atomic commit, version refusal"
$j0 = Join-Path $Work 'arm0.json'
$r0 = Invoke-Py @('-m', 'storage.layout', '--selftest', '--work', (Join-Path $Work 'layout-selftest'), '--json', $j0) 'arm0-layout.log'
$rep0 = Read-Report $j0
$p0 = if ($rep0) { "$($rep0.population.clips_committed) clips, $([int]$rep0.population.bytes_measured) B, tz_offset=$($rep0.population.host_utc_offset_min)min" } else { 'population UNKNOWN' }
Add-Arm -Name '0' -Ok ($r0.Rc -eq 0 -and $rep0 -and $rep0.ok) -Detail $p0 -Report $rep0
if ($r0.Rc -ne 0 -or -not $rep0 -or -not $rep0.ok) { Write-Host $r0.Out; Write-Host $r0.Err }

# --------------------------------------------------------------------------------------------
Write-Host "`n[ARM A] THE HEADLINE -- eviction against a REAL tree: bytes freed, POPULATION, WINDOW"
$jA = Join-Path $Work 'armA.json'
$rA = Invoke-Py @('-m', 'storage.retention', '--arm', 'A', '--work', $Work, '--json', $jA) 'armA-evict.log'
$repA = Read-Report $jA
$pA = if ($repA) {
    $f = $repA.population
    "freed=$($f.bytes_freed)B (walk agrees: $($f.bytes_freed_by_walk)B) over $($f.clips_evicted)/$($f.clips_before) clips; $($f.bytes_before)B -> $($f.bytes_after)B; budget=$($f.budget_bytes)B"
} else { 'population UNKNOWN' }
Add-Arm -Name 'A' -Ok ($rA.Rc -eq 0 -and $repA -and $repA.ok) -Detail $pA -Report $repA
if ($rA.Rc -ne 0 -or -not $repA -or -not $repA.ok) { Write-Host $rA.Out }
if ($repA) {
    Write-Host ("    WINDOW   oldest={0} newest={1} span={2}s :: {3}" -f `
        $repA.window.oldest, $repA.window.newest, $repA.window.span_s, $repA.window.note)
    Write-Host ("    BUDGET   {0} B from {1} = {2} min of capture at the MEASURED rate" -f `
        $repA.population.budget_bytes, $repA.population.budget_source, $repA.population.capture_minutes_budget_at_measured_rate)
    ($repA.checks | ForEach-Object { Write-Host ("      [{0}] {1}" -f $(if ($_.ok) {'ok  '} else {'RED '}), $_.name) })
}

# --------------------------------------------------------------------------------------------
Write-Host "`n[ARM B] DISK FULL -- refuse the write, keep the library, be LOUD"
$jB = Join-Path $Work 'armB.json'
$rB = Invoke-Py @('-m', 'storage.retention', '--arm', 'B', '--work', $Work, '--json', $jB) 'armB-diskfull.log'
$repB = Read-Report $jB
# The loudness claim is asserted HERE, on the child's real stdout, not on an internal counter:
# an alarm nobody can see in the process output is not a loud alarm.
$alarmOnStdout = ($rB.Out -split "`n" | Where-Object { $_ -match 'CLIP_STORE_ALARM\s+reason=disk-full' }).Count
$pB = if ($repB) {
    "admitted=$($repB.population.clips_present_after)/$($repB.population.clips_written) clips kept; free=$($repB.population.volume_free_bytes_measured)B MEASURED; CLIP_STORE_ALARM lines on stdout=$alarmOnStdout"
} else { 'population UNKNOWN' }
$bOk = ($rB.Rc -eq 0 -and $repB -and $repB.ok -and $alarmOnStdout -ge 1)
Add-Arm -Name 'B' -Ok $bOk -Detail $pB -Report $repB
if (-not $bOk) { Write-Host $rB.Out; Write-Host $rB.Err }
if ($repB) { ($repB.checks | ForEach-Object { Write-Host ("      [{0}] {1}" -f $(if ($_.ok) {'ok  '} else {'RED '}), $_.name) }) }
if ($alarmOnStdout -lt 1) { Write-Host "  RED: no CLIP_STORE_ALARM reached this process's stdout." }

# --------------------------------------------------------------------------------------------
Write-Host "`n[ARM C] RECONCILIATION -- a crashed clip is finished or discarded, never left corrupt"
$jC = Join-Path $Work 'armC.json'
$rC = Invoke-Py @('-m', 'storage.retention', '--arm', 'C', '--work', $Work, '--json', $jC) 'armC-reconcile.log'
$repC = Read-Report $jC
$pC = if ($repC) {
    "staged=$($repC.population.dirs_staged) dirs -> kept=$($repC.population.kept) finished=$($repC.population.finished) discarded=$($repC.population.discarded); $([int]$repC.population.bytes_reclaimed)B reclaimed; index sees $($repC.population.keys_the_index_would_see) clips"
} else { 'population UNKNOWN' }
Add-Arm -Name 'C' -Ok ($rC.Rc -eq 0 -and $repC -and $repC.ok) -Detail $pC -Report $repC
if ($rC.Rc -ne 0 -or -not $repC -or -not $repC.ok) { Write-Host $rC.Out }
if ($repC) { ($repC.checks | ForEach-Object { Write-Host ("      [{0}] {1}" -f $(if ($_.ok) {'ok  '} else {'RED '}), $_.name) }) }

# --------------------------------------------------------------------------------------------
Write-Host "`n[ARM E] the budget IN FORCE, its source, and a refusal instead of a clamp"
$jE = Join-Path $Work 'armE.json'
$rE = Invoke-Py @('-m', 'storage.retention', '--arm', 'E', '--work', $Work, '--json', $jE) 'armE-policy.log'
$repE = Read-Report $jE
$pE = if ($repE) { "policy line + precedence + refusal arms" } else { 'report UNKNOWN' }
Add-Arm -Name 'E' -Ok ($rE.Rc -eq 0 -and $repE -and $repE.ok) -Detail $pE -Report $repE
if ($rE.Rc -ne 0 -or -not $repE -or -not $repE.ok) { Write-Host $rE.Out }
if ($repE) {
    ($repE.checks | Where-Object { $_.name -like 'E5*' } | ForEach-Object { Write-Host "      $($_.detail)" })
}

# --------------------------------------------------------------------------------------------
Write-Host "`n[ARM D] THE CONTROL -- one guarantee reverted per mutant, in a COPY on disk"
# Each guard is ONE line in retention.py ending in `# GUARD:<TOKEN>`.  The mutation is a
# whole-line rewrite, applied by this harness and not by the code under test: the mutated
# module has no idea it was changed, which is the point.
$Mutants = @(
    @{ Token = 'RETENTION-BYTES';    NewExpr = 'return False'; Arm = 'A'; Lost = 'the store is never over budget, so nothing is ever evicted' }
    @{ Token = 'WRITE-ADMISSION';   NewExpr = 'return True';  Arm = 'B'; Lost = 'the disk-full refusal' }
    @{ Token = 'LOUD-ALARM';        NewExpr = 'return False'; Arm = 'B'; Lost = 'the loudness of the refusal' }
    @{ Token = 'RECONCILE-PARTIAL'; NewExpr = 'return False'; Arm = 'C'; Lost = 'discarding a clip whose media was never finalised' }
)

# --- D0: the UN-MUTATED copy.  Green, or the whole control arm proves nothing. -----------
$ctl0 = Join-Path $Work 'negctl-D0'
if (Test-Path $ctl0) { Remove-Item $ctl0 -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Join-Path $ctl0 'storage') | Out-Null
Copy-Item (Join-Path $Pkg '*.py') (Join-Path $ctl0 'storage')
$jd0 = Join-Path $Work 'negctl-D0.json'
$rD0 = Invoke-Py @('-m', 'storage.retention', '--arm', 'A', '--work', (Join-Path $Work 'negctl-D0-work'), '--json', $jd0) 'negctl-D0.log' $ctl0
$repD0 = Read-Report $jd0
$importedCopy = $false
if ($repD0 -and $repD0.facts.PSObject.Properties.Name -contains 'module_file') {
    $importedCopy = ([string]$repD0.facts.module_file).StartsWith($ctl0, [System.StringComparison]::OrdinalIgnoreCase)
}
$d0Ok = ($rD0.Rc -eq 0 -and $repD0 -and $repD0.ok -and $importedCopy)
Add-Arm -Name 'D0' -Ok $d0Ok -Detail 'the un-mutated COPY runs arm A green (proves the copy is not the cause)' -Report $repD0
if (-not $d0Ok) { Write-Host $rD0.Out; Write-Host "  imported: $($repD0.facts.module_file)" }

$mutantResults = [System.Collections.Generic.List[object]]::new()
foreach ($m in $Mutants) {
    $dir = Join-Path $Work "negctl-$($m.Token)"
    if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
    # The copy must be a PACKAGE (a `storage` directory holding __init__.py), not a flat pile
    # of modules: `python -m storage.retention` resolves against the child's own sys.path.
    New-Item -ItemType Directory -Force -Path (Join-Path $dir 'storage') | Out-Null
    Copy-Item (Join-Path $Pkg '*.py') (Join-Path $dir 'storage')

    # Find the guard line: exactly one line must match, or this is not a control.
    $target = Join-Path $dir 'storage\retention.py'
    if (-not (Test-Path $target)) {
        Add-Arm -Name "D/$($m.Token)" -Ok $false -Detail "MUTATION HARNESS FAILED: no $target to mutate" -Report $null
        $mutantResults.Add([pscustomobject]@{ Token = $m.Token; Applied = $false; WentRed = $false; Arm = $m.Arm })
        continue
    }
    $lines = [System.IO.File]::ReadAllLines($target)
    $rx = [regex]("#\s*GUARD:$([regex]::Escape($m.Token))\s*$")
    $hits = @()
    for ($i = 0; $i -lt $lines.Count; $i++) { if ($rx.IsMatch($lines[$i])) { $hits += $i } }
    if ($hits.Count -ne 1) {
        Add-Arm -Name "D/$($m.Token)" -Ok $false -Detail "MUTATION DID NOT APPLY: $($hits.Count) line(s) carry # GUARD:$($m.Token)" -Report $null
        $mutantResults.Add([pscustomobject]@{ Token = $m.Token; Applied = $false; WentRed = $false; Arm = $m.Arm })
        continue
    }
    $idx = $hits[0]
    $indent = ([regex]::Match($lines[$idx], '^\s*')).Value
    $lines[$idx] = "$indent$($m.NewExpr)  # GUARD:$($m.Token)"
    [System.IO.File]::WriteAllLines($target, $lines, (New-Object System.Text.UTF8Encoding($false)))

    $jj = Join-Path $Work "negctl-$($m.Token).json"
    $r = Invoke-Py @('-m', 'storage.retention', '--arm', $m.Arm, '--work', (Join-Path $Work "negctl-$($m.Token)-work"), '--json', $jj) "negctl-$($m.Token).log" $dir
    $rep = Read-Report $jj
    $imported = $false
    if ($rep -and $rep.facts.PSObject.Properties.Name -contains 'module_file') {
        $imported = ([string]$rep.facts.module_file).StartsWith($dir, [System.StringComparison]::OrdinalIgnoreCase)
    }
    $wentRed = ($r.Rc -ne 0 -or ($rep -and -not $rep.ok))
    $redNames = @()
    if ($rep) { $redNames = @($rep.checks | Where-Object { -not $_.ok } | ForEach-Object { $_.name }) }
    $ok = $imported -and $wentRed
    Add-Arm -Name "D/$($m.Token)" -Ok $ok -Detail ("reverted {0} -> arm {1} went RED: {2}" -f $m.Lost, $m.Arm, ($(if ($redNames) { $redNames -join ',' } else { "rc=$($r.Rc)" }))) -Report $rep
    if (-not $imported) { Write-Host "  RED: the mutated module was NOT the one imported: $($rep.facts.module_file)" }
    $mutantResults.Add([pscustomobject]@{ Token = $m.Token; Applied = $true; WentRed = $wentRed; Imported = $imported; Arm = $m.Arm; RedChecks = $redNames })
}

Write-Host ("  control: {0}/{1} reverted guarantee(s) went RED as required (D0 un-mutated copy: {2})" -f `
    @($mutantResults | Where-Object { $_.WentRed }).Count, $Mutants.Count, $(if ($d0Ok) { 'GREEN' } else { 'RED' }))

# --------------------------------------------------------------------------------------------
Write-Host "`n  GATED SOURCE (sha256, first 16) -- the bytes these verdicts are about:"
Get-ChildItem $Pkg -Filter *.py | Sort-Object Name | ForEach-Object {
    $h = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.Substring(0, 16)
    Write-Host ("    {0,-16} {1}  {2} B" -f $_.Name, $h, $_.Length)
}

Write-Host ''
$summary | Format-Table -AutoSize | Out-String -Width 220 | Write-Host
if ($failed -eq 0) {
    Write-Host 'LANE22-GATE PASS'
    exit 0
}
Write-Host "LANE22-GATE RED ($failed arm(s) failed) - logs in $Work"
exit 1