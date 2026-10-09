# _lane25-locale-number-gate.ps1 — no gate may publish a memory number through a
# locale-dependent group separator.
#
# THE DEFECT CLASS.  This box runs pt-BR.  MEASURED 2026-10-07 on pwsh 7.6.6 / pt-BR:
#
#     ("{0:N0}" -f 48888)  ->  '48.888'      hex 0034 0038 002E 0038 0038 0038
#                                               ^^^^^^^ a real PERIOD, U+002E
#
# A period is the DECIMAL POINT, so a gate that prints "48.888 MiB" has published a number
# wrong by a factor of 1000, in a form that looks entirely plausible.  This is the same
# wrong-published-number class as the reviewer's F1 (a receipt published 11934 where the
# correct figure was 12222) and as receipt-32's "48.888 MiB for 48888 MiB".
#
# WHAT THIS GATES, EXACTLY.  POPULATION = the `N`-specifier composite-format placeholders
# (`{n[,align]:N[k]}`) in the THREE PowerShell probes this lane owns.  WINDOW = the whole
# working tree at the moment this file runs, read from disk, not a sample.
#
# THE REPO-WIDE CENSUS is printed every run and is NOT part of the verdict.  Hits in files
# another lane owns are printed as DEFERRED with the owner named, so they are never
# invisible and never silently absorbed into this lane's green.
#
# GREEN DOES NOT MEAN "the whole repo is clean".  It means: no memory or duration quantity
# in THIS lane's files is published through a locale-dependent separator.
#
#   exit 0 = verdict PASS        exit 1 = verdict FAIL        exit 2 = gate could not run
#
# Usage:  pwsh -File _lane25-locale-number-gate.ps1                 (fixed arm, real tree)
#         pwsh -File _lane25-locale-number-gate.ps1 -Falsify       (both colours, one run)

[CmdletBinding()]
param(
    # Root of a tree to scan.  The falsify arm points this at a COPY whose only difference
    # is that this lane's fix has been reverted, which is what makes the red colour real.
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    # Run BOTH arms in one process: green on $Root, red on a copy with the fix reverted.
    [switch]$Falsify
)

$ErrorActionPreference = 'Stop'
$gateSelf = Split-Path -Leaf $MyInvocation.MyCommand.Path

# ---------------------------------------------------------------------------------------
# The files whose `N` sites this lane owns.  Adding a file here transfers the obligation to
# keep it separator-free to this lane; it does not transfer ownership away from a live lane.
# ---------------------------------------------------------------------------------------
$OWNED = @(
    '_main\durability-gate.ps1'
    '_main\font-lag-probe.ps1'
    '_main\font-shots.ps1'
)

# ---------------------------------------------------------------------------------------
# Inverse of this lane's fix, applied verbatim to build the falsify copy.  Each entry is
# @(path, fixedText, revertedText).  If a fix is edited and this list is not, the falsify arm
# stops being able to go red and the gate says so instead of pretending to be a gate.
# ---------------------------------------------------------------------------------------
$REVERTS = @(
    # The MEMORY site -- the one this whole lane exists for.  Two steps: the placeholder must
    # regain its :N1 AND the operand must go back to the raw locale-formatted value, otherwise
    # the copy prints "{0,9} MB" which this detector correctly calls SAFE and the arm lies.
    @('_main\durability-gate.ps1',
      '{0,9} MB',
      '{0,9:N1} MB'),
    @('_main\durability-gate.ps1',
      '$_.MB.ToString(''F1'', $inv)',
      '$_.MB'),
    @('_main\durability-gate.ps1',
      'duration={6}s',
      'duration={6:N1}s'),
    @('_main\font-lag-probe.ps1',
      '{1,5}s',
      '{1,5:N1}s'),
    @('_main\font-shots.ps1',
      '{4}s',
      '{4:N1}s')
)

# A placeholder is DEFECTIVE when the unit literal printed right after it is a memory
# integer unit or a time unit.  Both are quantities a reader parses with a decimal point,
# which is exactly what this host's group separator looks like.  Percentages, ratios, and
# sub-1000 seconds carry no separator and are left alone: their `N` is doing no harm.
$MEMORY_UNITS = @('B', 'bytes', 'KB', 'MB', 'GB', 'KiB', 'MiB', 'GiB', 'TiB')
$TIME_UNITS   = @('s', 'ms', 'min', 'h')

$inv = [System.Globalization.CultureInfo]::InvariantCulture

# Files the scan could not read because a live lane holds them open.  Counted and NAMED, never
# dropped: a scan that loses a file without saying so would understate the population, and an
# understated population is how a wrong number survives a green.
$script:unreadableCount = 0
$script:unreadableNames = New-Object System.Collections.ArrayList

function Get-UnitAfter {
    param([string]$Line, [int]$MatchIndex, [int]$MatchLength)
    # The literal text between this placeholder and the next placeholder / end of line is
    # where the unit lives:  "{0,9} MB  [{1}/{2}]"  ->  " MB  [".
    $tail = $Line.Substring($MatchIndex + $MatchLength)
    # Stop at the next placeholder, a pipe, OR the closing quote of the format string - the
    # unit lives inside the format string, and letting the scan run past the quote reads the
    # `-f` operator as a unit named "f".
    $cut = $tail.IndexOfAny([char[]]@('{', '|', '"'))
    if ($cut -ge 0) { $tail = $tail.Substring(0, $cut) }
    $m = [regex]::Match($tail, '[A-Za-z]+')
    if ($m.Success) { return $m.Value }
    return ''
}

function Get-NGroupSites {
    param([string]$ScanRoot)

    $sites = New-Object System.Collections.ArrayList
    if (-not (Test-Path -LiteralPath $ScanRoot)) { return $sites }

    # CODE ONLY.  A .md file is a document, not a publishing site: a wrong number already
    # baked into a receipt is fixed by editing the receipt, not by a format specifier, and
    # this receipt quotes the very patterns it censuses - scanning .md would make the
    # POPULATION count a function of how much prose the repo has, which is not a measurement
    # of anything.  Prose occurrences are listed as EXCLUDED in receipt-33 instead.
    $exts = @('.ps1', '.py', '.cpp', '.h', '.cmd', '.bat', '.js', '.mjs', '.cjs')
    $script:scannedExts = $exts
    $files = Get-ChildItem -LiteralPath $ScanRoot -Recurse -File -ErrorAction SilentlyContinue |
             Where-Object { $exts -contains $_.Extension.ToLowerInvariant() }

    foreach ($f in $files) {
        if ($f.Name -eq $gateSelf) { continue }      # the gate quotes the pattern on purpose
        # A file a live lane holds open is a real condition on this repo.  Skipping it silently
        # would understate the population, so it is counted and NAMED on every run.
        $lines = $null
        try { $lines = [System.IO.File]::ReadAllLines($f.FullName) }
        catch {
            $script:unreadableCount++
            $script:unreadableNames.Add($f.Name)
            continue
        }
        for ($i = 0; $i -lt $lines.Count; $i++) {
            $ln = $lines[$i]
            $t = $ln.TrimStart()
            # A comment does not print.  Skipping them keeps the census about code and keeps
            # prose that QUOTES the pattern (run_battery.ps1:79, all-gates.ps1:353,
            # receipt-32:204) from reading as a live site.
            if ($t.StartsWith('#') -or $t.StartsWith('//')) { continue }

            foreach ($m in [regex]::Matches($ln, '\{(\d+)(,[^:}]+)?:N(\d*)\}')) {
                $unit = Get-UnitAfter -Line $ln -MatchIndex $m.Index -MatchLength $m.Length
                $kind = 'SAFE'
                if ($MEMORY_UNITS -contains $unit) { $kind = 'MEMORY' }
                elseif ($TIME_UNITS -contains $unit) { $kind = 'DURATION' }

                $rel = $f.FullName.Substring($ScanRoot.TrimEnd('\').Length).TrimStart('\')
                [void]$sites.Add([pscustomobject]@{
                    File = $rel
                    Line = ($i + 1)
                    Placeholder = $m.Value
                    Unit = $unit
                    Kind = $kind
                    Owned = ($OWNED -contains $rel)
                })
            }
        }
    }
    return $sites
}

function Write-Census {
    param($Sites)
    Write-Output ''
    Write-Output 'CENSUS — every `N`-specifier composite-format placeholder in the tree'
    Write-Output ("  POPULATION = {0} placeholder(s) in {1} scanned file(s)" -f $Sites.Count, $scanFileCount)
    Write-Output  '  WINDOW     = the whole tree under Root, read from disk at gate time (not a sample)'
    Write-Output ("               scanned extensions: {0}  — .md/.txt/.log/.json are DOCUMENTS or" -f ($script:scannedExts -join ' '))
    Write-Output '               OUTPUT, and are counted by _lane25-locale-census.ps1, not by this gate.'
    Write-Output ("               {0} file(s) unreadable (a live lane holds them open) and were SKIPPED:" -f $script:unreadableCount)
    foreach ($u in $script:unreadableNames) { Write-Output ("                 unreadable: {0}" -f $u) }
    Write-Output '  CLASS      = MEMORY/DURATION are the ones a reader parses with a decimal point.'
    Write-Output '               SAFE = the value carries no group separator (percent, ratio, sub-1000 s).'
    Write-Output ''
    $w = 0
    foreach ($s in $Sites) {
        $tag = if ($s.Owned) { 'OWNED   ' } else { 'DEFERRED' }
        Write-Output ("  {0} {1,-34}:{2,-4} {3,-9} {4,-6} {5}" -f `
            $tag, $s.File, $s.Line, $s.Placeholder, $s.Kind, ("'" + $s.Unit + "'"))
        $w = [math]::Max($w, $s.File.Length + 4)
    }
    if ($Sites.Count -eq 0) { Write-Output '  (none)' }
}

# =======================================================================================
# ARM 1 — THE HOST.  A gate that cannot bite on this host must say so, not pass quietly.
# =======================================================================================
Write-Output '=========================================================================='
Write-Output ' LANE 25 GATE — locale group separator must never publish a memory number'
Write-Output '=========================================================================='
Write-Output ("ROOT {0}" -f $Root)
$culture = [System.Globalization.CultureInfo]::CurrentCulture.Name
$sample  = "{0:N0}" -f 48888
$fmtHost = 'HOST culture={0}   ("{0:N0}" of 48888) renders as {1}'
Write-Output ($fmtHost -f $culture, $sample)

$hostArmOk = $true
if ($sample -match '^\d+\.\d{3}$') {
    Write-Output '      -> the group separator is a PERIOD. The defect class is LIVE on this host,'
    Write-Output '         so a green verdict below is a real measurement and not a vacuous pass.'
} else {
    Write-Output '      -> WARNING: 48888 did not render with a period group separator. The defect'
    Write-Output '         class is NOT live on this host, so this gate cannot go red here.'
    $hostArmOk = $false
}

# =======================================================================================
# ARM 2 — THE RENDER PROOF.  Ties the static rule to what this host actually prints, using
# the real magnitude from receipt-32 (48888 MiB) rather than an invented one.
# =======================================================================================
Write-Output ''
Write-Output 'RENDER PROOF — 48888 (the magnitude receipt-32 published wrong)'
$badBefore  = "{0:N1}" -f 48888.0
$goodAfter  = (48888.0).ToString('F1', $inv)
$renderOk   = ($goodAfter -eq '48888.0' -and $goodAfter -notmatch '\.\d{3}')
Write-Output ('  DEFECTIVE  locale "-f {{0:N1}}"   -> {0}   [readable as forty-eight — WRONG BY 1000x]' -f $badBefore)
Write-Output ('  FIXED      ToString(F1,inv)    -> {0}   [readable only as 48888]' -f $goodAfter)
if (-not $renderOk) { Write-Output '  FAIL: the invariant form is not separator-free.' }

# =======================================================================================
# ARM 3 — THE CENSUS + VERDICT
# =======================================================================================
$scanFiles = Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue
$scanFileCount = @($scanFiles).Count
$sites = Get-NGroupSites -ScanRoot $Root
Write-Census -Sites $sites

$ownedBad  = @($sites | Where-Object { $_.Owned -and ($_.Kind -eq 'MEMORY' -or $_.Kind -eq 'DURATION') })
$deferred  = @($sites | Where-Object { -not $_.Owned })
$otherLane = @($deferred | Where-Object { $_.Kind -eq 'MEMORY' -or $_.Kind -eq 'DURATION' })

Write-Output ''
Write-Output 'VERDICT INPUT'
Write-Output ("  owned files scanned        : {0}" -f ($OWNED -join ', '))
Write-Output ("  owned DEFECTIVE sites      : {0}" -f $ownedBad.Count)
Write-Output ("  DEFERRED sites (other lane): {0}  of which memory/duration: {1}" -f $deferred.Count, $otherLane.Count)
foreach ($s in $otherLane) {
    Write-Output ("      {0}:{1}  {2} on '{3}'  — NOT this lane's file; reported, not touched." -f $s.File, $s.Line, $s.Placeholder, $s.Unit)
}

$pass = $hostArmOk -and $renderOk -and ($ownedBad.Count -eq 0)
Write-Output ''
if ($pass) {
    Write-Output 'VERDICT PASS - no memory or duration quantity owned by this lane is'
    Write-Output '            published through a locale-dependent group separator.'
} else {
    Write-Output 'VERDICT FAIL'
    foreach ($s in $ownedBad) {
        Write-Output ("  - {0}:{1}  {2} publishes a '{3}' quantity through a locale-dependent" -f $s.File, $s.Line, $s.Placeholder, $s.Unit)
        Write-Output ("      group separator.  Fix: pass the operand through ToString('F<k>', InvariantCulture)")
        Write-Output ("      and drop the specifier from the placeholder.")
    }
    if (-not $hostArmOk) { Write-Output '  - the host arm could not bite (see above): this gate is not a gate here.' }
    if (-not $renderOk)    { Write-Output '  - the invariant render is not separator-free.' }
}

# =======================================================================================
# ARM 4 — FALSIFY.  A COPY of the owned files with ONLY this lane's fix reverted.  If the
# copy does not go red, the green above is not evidence of anything.
# =======================================================================================
$fp = $null
$falsifyOk = $true      # becomes $false if the falsify arm fails to prove it can bite
if ($Falsify) {
    Write-Output ''
    Write-Output '=========================================================================='
    Write-Output ' FALSIFY ARM - copy of the owned files with ONLY the fix from this lane reverted'
    Write-Output '=========================================================================='
    $fp = Join-Path ([System.IO.Path]::GetTempPath()) ('lane25-falsify-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
    New-Item -ItemType Directory -Path $fp -Force | Out-Null
    try {
        $applied = 0; $missing = New-Object System.Collections.ArrayList
        foreach ($r in $REVERTS) {
            $dst = Join-Path $fp $r[0]
            New-Item -ItemType Directory -Path (Split-Path -Parent $dst) -Force | Out-Null
            if (-not (Test-Path -LiteralPath $dst)) {
                Copy-Item -LiteralPath (Join-Path $Root $r[0]) -Destination $dst -Force
            }
            $txt = [System.IO.File]::ReadAllText($dst)
            if ($txt.Contains($r[1])) {
                $txt = $txt.Replace($r[1], $r[2])
                [System.IO.File]::WriteAllText($dst, $txt, (New-Object System.Text.UTF8Encoding($false)))
                $applied++
            } else {
                [void]$missing.Add($r[0] + ' :: ' + $r[1])
            }
        }
        Write-Output ("  reverts applied: {0} of {1}" -f $applied, $REVERTS.Count)
        foreach ($m in $missing) { Write-Output ("  REVERT DID NOT MATCH (the fix was edited without updating REVERTS): {0}" -f $m) }

        $fSites = Get-NGroupSites -ScanRoot $fp
        $fBad = @($fSites | Where-Object { $_.Owned -and ($_.Kind -eq 'MEMORY' -or $_.Kind -eq 'DURATION') })
        Write-Output ''
        Write-Output '  reverted copy — sites the detector now finds:'
        foreach ($s in $fSites) {
            Write-Output ("    {0,-34}:{1,-4} {2,-9} {3,-9} '{4}'" -f $s.File, $s.Line, $s.Placeholder, $s.Kind, $s.Unit)
        }
        Write-Output ''
        if ($fBad.Count -gt 0 -and $missing.Count -eq 0) {
            Write-Output ("  FALSIFY RED — {0} defective site(s) on the reverted copy." -f $fBad.Count)
            Write-Output '  This is the proof that the green above is a measurement, not a habit.'
        } else {
            Write-Output '  FALSIFY DID NOT GO RED — the detector is not a detector. Treat the green above as unproven.'
            $falsifyOk = $false
        }
    } catch {
        # A falsify arm that THROWS has proved nothing.  Swallowing that into a green is the
        # exact failure this lane exists to kill, so it is a hard failure, not a warning.
        Write-Output ("  FALSIFY ARM THREW: {0}" -f $_.Exception.Message)
        $falsifyOk = $false
    } finally {
        Remove-Item -LiteralPath $fp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Output ''
Write-Output ("POPULATION: one host ({0}), one tree scan of {1} file(s) under {2}, WINDOW: this run." -f $culture, $scanFileCount, $Root)
Write-Output 'NO FLAKINESS CLAIM IS MADE. Re-running is a new measurement, not a confirmation.'

# THE EXIT.  Three conditions, all required:
#   $pass       — no owned defective site, and both static arms are meaningful here
#   -not $Falsify — when the falsify arm was NOT requested, its verdict is not claimed
#   $falsifyOk  — when it WAS requested, it must have gone RED, or this process exits 1
#
# This used to read `if ($pass -and (-not $Falsify -or $true))`, and `-or $true` made the
# second term a tautology: `-Falsify` could never influence the exit code.  MEASURED on a
# tree where all five reverts failed to match — the run printed "FALSIFY DID NOT GO RED"
# and still returned EXITCODE=0.  A falsify arm that cannot turn the gate red is a comment,
# not a gate, so the arm's result is now wired into the exit.
if ($pass -and $falsifyOk) { exit 0 } else { exit 1 }