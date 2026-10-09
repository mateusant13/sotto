#Requires -Version 7
<#
.SYNOPSIS
    LANE4 GATE -- the searchable clip index (H:\sotto\_moved\aireplay\src\index).

.DESCRIPTION
    One named arm per acceptance criterion, each a SEPARATE OS process so a crash in one arm
    cannot take the gate with it:

      ARM 0  the fixture drift lock -- the transcript text this gate searches is still the
             MEASURED text in _main/runs/threads11/silence-t4-p1.json (814 chars, 11 segments)
      ARM A  a FRESH db: 6 clips / 9 segments written from a real ASR `done` payload, then
             named queries with their POPULATION and WINDOW
      ARM B  a SECOND run on the SAME db: idempotent replay, and an OLD-SHAPE v0 db migrated
             additively (row kept, columns added, transcript backfilled into the FTS table)
      ARM C  THE CONTROL -- arm A's assertions, unchanged, against a COPY of the package with
             one guarantee reverted. Both mutants must go RED.
      ARM D  two OS processes writing one file: they must OVERLAP, lose no row, duplicate none,
             and never see "database is locked"

    Prints `LANE4-GATE PASS` and exits 0 ONLY when every arm met its expectation; otherwise
    `LANE4-GATE RED` and exit 1.

    House rules obeyed here:
      rule 2 -- no native command is ever PIPED for its exit code. Every python invocation goes
               through System.Diagnostics.Process and its real ExitCode is read.
      rule 1 -- every python process is created with CreateNoWindow + WindowStyle Hidden, so
               running this gate never puts a console on the owner's screen.

.EXAMPLE
    pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane4-index-gate.ps1
#>
[CmdletBinding()]
param(
    [string] $Python = "",                 # full path to python.exe; default: the `py` launcher
    [string] $Work = ""                    # scratch dir; default: _main\_lane4-run
)

$ErrorActionPreference = 'Stop'
$Repo    = Split-Path -Parent $PSScriptRoot
$Src     = Join-Path $Repo 'src'
$Gate    = Join-Path $Repo 'src\index\selftest.py'
if (-not $Work) { $Work = Join-Path $Repo '_main\_lane4-run' }
$Db      = Join-Path $Work 'gate.db'
$Env:PYTHONIOENCODING = 'utf-8'            # or the accented Portuguese dies on cp1252
$Env:PYTHONDONTWRITEBYTECODE = '1'

if ($Python) { $Exe = $Python; $Prefix = @() }
else         { $Exe = 'py';              $Prefix = @('-3') }

if (-not (Test-Path $Gate)) { Write-Error "index gate: missing $Gate"; exit 2 }
New-Item -ItemType Directory -Force -Path $Work | Out-Null
foreach ($stale in @($Db, "$Db-wal", "$Db-shm")) { if (Test-Path $stale) { Remove-Item $stale -Force } }

function Invoke-Py {
    param([string[]] $PyArgs, [string] $LogName)
    $log = Join-Path $Work $LogName
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName               = $Exe
    foreach ($a in ($Prefix + $PyArgs)) { [void] $psi.ArgumentList.Add($a) }
    $psi.WorkingDirectory       = $Src
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
    $proc.WaitForExit()
    $out = $so.Result
    $err = $se.Result
    Set-Content -Path $log -Value ($out + "`n--- STDERR ---`n" + $err) -Encoding UTF8
    [pscustomobject]@{ Rc = $proc.ExitCode; Log = $log; Out = $out; Err = $err }
}

function Read-Report {
    param([string] $Path)
    if (-not (Test-Path $Path)) { return $null }
    try { return (Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json) }
    catch { return $null }
}

$summary = [System.Collections.Generic.List[object]]::new()
$failed  = 0

function Add-Arm {
    param([string] $Name, [bool] $Ok, [string] $Detail, $Report)
    if (-not $Ok) { $script:failed++ }
    $n = if ($Report -and $Report.PSObject.Properties.Name -contains 'n_checks') { $Report.n_checks } else { $null }
    $f = if ($Report -and $Report.PSObject.Properties.Name -contains 'n_failed') { $Report.n_failed } else { $null }
    $script:summary.Add([pscustomobject]@{
        Arm = $Name; Ok = $Ok; Checks = $n; Failed = $f; Population = $Detail
    })
    $mark = if ($Ok) { 'PASS' } else { 'RED ' }
    $chk  = if ($null -ne $n) { "$f/$n check(s) failed" } else { 'no report' }
    Write-Host ("  ARM {0,-4} {1}  {2,-52} {3}" -f $Name, $mark, $Detail, $chk)
}

Write-Host "LANE4 GATE -- the clip index"
Write-Host "  repo   : $Repo"
Write-Host "  python : $Exe $($Prefix -join ' ')"
Write-Host "  work   : $Work"
Write-Host "  sqlite : $(& $Exe @($Prefix + @('-c','import sqlite3;print(sqlite3.sqlite_version)')) 2>$null)"

# ---------------------------------------------------------------------------------------------
Write-Host "`n[ARM 0] the fixture drift lock -- is the searched text still the MEASURED text?"
$r0 = Invoke-Py @('-m', 'index.selftest', '--verify-fixture') 'arm0-fixture.log'
$fixtureOk = $r0.Rc -eq 0
Add-Arm -Name '0' -Ok $fixtureOk -Detail 'fixture text == _main/runs/threads11/silence-t4-p1.json' -Report $null
if (-not $fixtureOk) { Write-Host $r0.Out }

# ---------------------------------------------------------------------------------------------
Write-Host "`n[ARM A] a FRESH db: write 6 clips / 9 segments, then search them"
$aJson = Join-Path $Work 'armA.json'
$rA = Invoke-Py @('-m', 'index.selftest', '--arm', 'A', '--db', $Db, '--work', $Work, '--json', $aJson) 'armA.log'
$repA = Read-Report $aJson
$popA = if ($repA) { "clips=$($repA.population.clips) segments=$($repA.population.segments) window=whole library" } else { 'population UNKNOWN' }
Add-Arm -Name 'A' -Ok ($rA.Rc -eq 0 -and $repA -and $repA.ok) -Detail $popA -Report $repA
if ($rA.Rc -ne 0 -or -not $repA -or -not $repA.ok) { Write-Host $rA.Out }

# ---------------------------------------------------------------------------------------------
Write-Host "`n[ARM B] a SECOND run on the SAME db + an OLD-SHAPE v0 db migrated additively"
$bJson = Join-Path $Work 'armB.json'
$rB = Invoke-Py @('-m', 'index.selftest', '--arm', 'B', '--db', $Db, '--work', $Work, '--json', $bJson) 'armB.log'
$repB = Read-Report $bJson
$popB = if ($repB) { "replay rows=$(($repB.rows_before.PSObject.Properties | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join ' ')" } else { 'rows UNKNOWN' }
Add-Arm -Name 'B' -Ok ($rB.Rc -eq 0 -and $repB -and $repB.ok) -Detail $popB -Report $repB
if ($rB.Rc -ne 0 -or -not $repB -or -not $repB.ok) { Write-Host $rB.Out }

# ---------------------------------------------------------------------------------------------
Write-Host "`n[ARM C] THE CONTROL -- arm A's assertions against a COPY with the guarantee reverted"
$cJson = Join-Path $Work 'armC.json'
$rC = Invoke-Py @('-m', 'index.selftest', '--arm', 'C', '--db', $Db, '--work', $Work, '--json', $cJson) 'armC.log'
$repC = Read-Report $cJson
$checksC = if ($repC) { @($repC.checks) } else { @() }
$mutations = @($checksC | Where-Object { $_.name -like '*.mutation' })
$redArms = @($checksC | Where-Object { $_.name -like '*.goes-RED' -and $_.ok }).Count
$cOk = ($rC.Rc -eq 0 -and $repC -and $repC.ok -and $mutations.Count -ge 2 -and $redArms -ge 2)
Add-Arm -Name 'C' -Ok $cOk -Detail "$redArms/$($mutations.Count) reverted guarantee(s) went RED as required" -Report $repC
if (-not $cOk) { Write-Host $rC.Out }

# ---------------------------------------------------------------------------------------------
Write-Host "`n[ARM D] two OS processes, one file -- they must overlap and lose nothing"
$dJson = Join-Path $Work 'armD.json'
$rD = Invoke-Py @('-m', 'index.selftest', '--arm', 'D', '--db', $Db, '--work', $Work, '--json', $dJson) 'armD.log'
$repD = Read-Report $dJson
$overlap = if ($repD) { @($repD.checks | Where-Object { $_.name -eq 'D.writers-overlapped' }) } else { @() }
$ovDetail = if ($overlap.Count) { $overlap[0].detail } else { 'overlap NOT MEASURED' }
Add-Arm -Name 'D' -Ok ($rD.Rc -eq 0 -and $repD -and $repD.ok) -Detail $ovDetail -Report $repD
if ($rD.Rc -ne 0 -or -not $repD -or -not $repD.ok) { Write-Host $rD.Out }

# ---------------------------------------------------------------------------------------------
Write-Host "`n  GATED SOURCE (sha256, first 16) -- the bytes these verdicts are about:"
Get-ChildItem (Join-Path $Repo 'src\index') -Filter *.py | Sort-Object Name | ForEach-Object {
    $h = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.Substring(0, 16)
    Write-Host ("    {0,-16} {1}" -f $_.Name, $h)
}

Write-Host ''
$summary | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
if ($failed -eq 0) {
    Write-Host 'LANE4-GATE PASS'
    exit 0
}
Write-Host "LANE4-GATE RED ($failed arm(s) failed) - logs in $Work"
exit 1