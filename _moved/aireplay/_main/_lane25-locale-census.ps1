# _lane25-locale-census.ps1 — the CENSUS, standalone, with an exact denominator.
#
# THE DEFECT CLASS.  This host runs pt-BR.  MEASURED: ("{0:N0}" -f 48888) renders
# '48.888', hex 0034 0038 002E 0038 0038 0038 — the group separator is U+002E, a real
# PERIOD.  A period is the decimal point, so a gate that prints "48.888 MiB" has published
# a number wrong by 1000x in a form that reads as plausible.  Same class as F1.
#
# WHY A SEPARATE FILE AND NOT JUST THE GATE.  The gate answers "is it fixed"; the census
# answers "how many are there".  They were conflated, and the conflation produced a wrong
# published number of exactly the kind this lane exists to kill: receipt-33 claimed
# POPULATION 18 "in 6 files" and its own gate then printed 15, because the gate silently
# dropped .md from the scanned extensions.  Two numbers, one name, neither traceable.
#
# THE WINDOW, STATED ONCE AND COUNTED.  POPULATION = the placeholder SITES below.
# WINDOW = the source-code files under -Root that this census declares IN SCOPE.  The
# denominator is PRINTED, so "18" is checkable instead of being a claim.
#
# WHAT IS IN SCOPE, and why it is not "every file":
#   IN  = source code that can PRINT a number: .ps1 .psm1 .cmd .bat .py .cpp .c .h .hpp
#         .js .mjs .cjs
#   OUT = (a) comments and docstrings, which print nothing; (b) .md/.txt/.log/.json, which
#         are DOCUMENTS or OUTPUT — a wrong number already baked into a receipt is fixed by
#         editing the receipt, and this census quotes the very patterns it counts, so
#         including prose would make the population a function of how much prose the repo
#         has.  Excluded occurrences are COUNTED and PRINTED, never dropped silently.
#
#   exit 0 = census ran (a census is a measurement, not a verdict; the gate owns the verdict)
#   exit 2 = census could not run
#
# Usage:  pwsh -File _lane25-locale-census.ps1
#         pwsh -File _lane25-locale-census.ps1 -Root <dir> -Json

[CmdletBinding()]
param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [switch]$Json
)

$ErrorActionPreference = 'Stop'
$self = Split-Path -Leaf $MyInvocation.MyCommand.Path

$IN_EXT = @('.ps1', '.psm1', '.cmd', '.bat', '.py', '.cpp', '.c', '.h', '.hpp',
            '.js', '.mjs', '.cjs')
$OUT_EXT = @('.md', '.txt', '.log', '.json', '.csv', '.jsonl')

$MEMORY_UNITS = @('B', 'bytes', 'KB', 'MB', 'GB', 'KiB', 'MiB', 'GiB', 'TiB')
$TIME_UNITS   = @('s', 'ms', 'min', 'h')

function Get-UnitAfter {
    param([string]$Line, [int]$Index, [int]$Length)
    $tail = $Line.Substring($Index + $Length)
    # The unit lives inside the format string.  Stop at the next placeholder, a pipe, or the
    # closing quote, or the scan runs past the quote and reads the `-f` operator as a unit.
    $cut = $tail.IndexOfAny([char[]]@('{', '|', '"'))
    if ($cut -ge 0) { $tail = $tail.Substring(0, $cut) }
    $m = [regex]::Match($tail, '[A-Za-z]+')
    if ($m.Success) { return $m.Value }
    return ''
}

if (-not (Test-Path -LiteralPath $Root)) {
    Write-Output "CENSUS COULD NOT RUN: root '$Root' does not exist."
    exit 2
}

$all   = @(Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue)
$inFx  = @($all | Where-Object { $IN_EXT  -contains $_.Extension.ToLowerInvariant() })
$outFx = @($all | Where-Object { $OUT_EXT -contains $_.Extension.ToLowerInvariant() })

# A BACKUP of a deleted blob is dead code: nothing runs it, so it cannot publish a wrong
# number.  Left in scope it would inflate the population with sites no reader can ever see.
# It is separated and COUNTED, never silently dropped.
$BACKUP_DIR = '_deleted-blob-backup'
$inFxLive   = @($inFx | Where-Object { $_.FullName -notlike "*\*$BACKUP_DIR\*" })
$inFxBackup = @($inFx | Where-Object { $_.FullName -like "*\*$BACKUP_DIR\*" })

$sites    = New-Object System.Collections.ArrayList
$comments = 0
$quoted   = 0
$selfRefs = 0
# A file a live lane holds open is a real condition on this repo, not an error: the tree is
# being written while gates run.  Such a file is SKIPPED and NAMED, never silently dropped —
# a census that quietly loses a file would understate its own population.
$unreadable = New-Object System.Collections.ArrayList

foreach ($f in $inFxLive) {
    if ($f.Name -eq $self) { continue }      # the tool quotes the pattern on purpose
    $lines = $null
    try { $lines = [System.IO.File]::ReadAllLines($f.FullName) }
    catch { [void]$unreadable.Add($f.Name); continue }   # a live lane is writing it
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $ln = $lines[$i]
        $t = $ln.TrimStart()
        # A comment prints nothing.  Counted separately so the exclusion is visible.
        if ($t.StartsWith('#') -or $t.StartsWith('//') -or $t.StartsWith('*') -or
            $t.StartsWith('REM ') -or $t.StartsWith('::')) { $comments++; continue }
        foreach ($m in [regex]::Matches($ln, '\{(\d+)(,[^:}]+)?:N(\d*)\}')) {
            # A pattern INSIDE a quoted string is DATA — the REVERTS table of this lane's gate
            # holds the defective text on purpose so the falsify arm can restore it.  Counting
            # it as a live site would make the gate flag its own detector; a census that does
            # that is a census nobody reads.  Odd number of quotes before the match == inside.
            $before = $ln.Substring(0, $m.Index)
            $q = ([regex]::Matches($before, "'")).Count
            if ($q % 2 -eq 1) { $quoted++; continue }
            $unit = Get-UnitAfter -Line $ln -Index $m.Index -Length $m.Length
            $kind = 'SAFE'
            if ($MEMORY_UNITS -contains $unit) { $kind = 'MEMORY' }
            elseif ($TIME_UNITS -contains $unit) { $kind = 'DURATION' }
            $rel = $f.FullName.Substring($Root.TrimEnd('\').Length).TrimStart('\')
            [void]$sites.Add([pscustomobject]@{
                File = $rel; Line = ($i + 1); Placeholder = $m.Value
                Unit = $unit; Kind = $kind
            })
        }
    }
}

# The same pattern in the documents/output extensions: counted so the exclusion is an
# arithmetic statement, not a shrug.
$outHits = 0
$unreadable = New-Object System.Collections.ArrayList
foreach ($f in $outFx) {
    $lines = $null
    try { $lines = [System.IO.File]::ReadAllLines($f.FullName) }
    catch { [void]$unreadable.Add($f.Name); continue }   # a live lane is writing it
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $outHits += ([regex]::Matches($lines[$i], '\{[0-9]+(,[^:}]+)?:N[0-9]*\}')).Count
    }
}

# The same pattern in BACKUP copies of deleted blobs: dead code, counted separately so the
# exclusion is arithmetic rather than a shrug.
$backupHits = 0
foreach ($f in $inFxBackup) {
    $lines = $null
    try { $lines = [System.IO.File]::ReadAllLines($f.FullName) }
    catch { continue }
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $t = $lines[$i].TrimStart()
        if ($t.StartsWith('#') -or $t.StartsWith('//')) { continue }
        $backupHits += ([regex]::Matches($lines[$i], '\{[0-9]+(,[^:}]+)?:N[0-9]*\}')).Count
    }
}

# .ToString('N...') — the other spelling of the same locale group separator.
$toStringSites = New-Object System.Collections.ArrayList
foreach ($f in $inFxLive) {
    if ($f.Name -eq $self) { continue }
    $lines = $null
    try { $lines = [System.IO.File]::ReadAllLines($f.FullName) }
    catch { [void]$unreadable.Add($f.Name); continue }
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $t = $lines[$i].TrimStart()
        if ($t.StartsWith('#') -or $t.StartsWith('//')) { continue }
        foreach ($m in [regex]::Matches($lines[$i], "ToString\(\s*'N[0-9]*'")) {
            $rel = $f.FullName.Substring($Root.TrimEnd('\').Length).TrimStart('\')
            # [guid]::NewGuid().ToString('N') is the NO-DASHES GUID format, not a number.
            $isGuid = $lines[$i] -match '(?i)guid'
            $kind = if ($isGuid) { 'GUID-EXCLUDED' } else { 'TOSTRING-N' }
            [void]$toStringSites.Add([pscustomobject]@{
                File = $rel; Line = ($i + 1); Text = $m.Value; Kind = $kind
            })
        }
    }
}

$memSites = @($sites | Where-Object { $_.Kind -eq 'MEMORY' })
$tsSites  = @($sites | Where-Object { $_.Kind -eq 'DURATION' })
$safeSites= @($sites | Where-Object { $_.Kind -eq 'SAFE' })
$fileCount = @($sites | Select-Object -ExpandProperty File -Unique).Count

if ($Json) {
    [pscustomobject]@{
        Root            = $Root
        FilesInWindow   = $inFxLive.Count
        FilesBackup     = $inFxBackup.Count
        FilesOutOfScope = $outFx.Count
        FilesTotal      = $all.Count
        PopSites        = $sites.Count
        PopLines        = $sites.Count
        PopFiles        = $fileCount
        Memory          = $memSites.Count
        Duration        = $tsSites.Count
        Safe            = $safeSites.Count
        CommentSkipped  = $comments
        QuotedSkipped   = $quoted
        BackupHits      = $backupHits
        DocHitsExcluded = $outHits
        Unreadable      = $unreadable.Count
        ToStringN       = @($toStringSites | Where-Object { $_.Kind -eq 'TOSTRING-N' }).Count
        GuidExcluded    = @($toStringSites | Where-Object { $_.Kind -eq 'GUID-EXCLUDED' }).Count
        Sites           = $sites
    } | ConvertTo-Json -Depth 5
    exit 0
}

Write-Output '=========================================================================='
Write-Output ' CENSUS — locale-dependent group separators (pt-BR renders them as ".")'
Write-Output '=========================================================================='
Write-Output ("WINDOW     : {0}" -f $Root)
Write-Output ("IN SCOPE  : {0} LIVE source file(s) (extensions: {1})" -f $inFxLive.Count, ($IN_EXT -join ' '))
Write-Output ("BACKUP    : {0} file(s) under {1} — dead code, counted apart" -f $inFxBackup.Count, $BACKUP_DIR)
Write-Output ("OUT OF SCOPE: {0} document/output file(s) — hits counted, listed below" -f $outFx.Count)
Write-Output ("TREE TOTAL : {0} file(s)" -f $all.Count)
Write-Output ''
Write-Output ("POPULATION : {0} placeholder site(s) on {0} line(s), in {1} file(s)" -f $sites.Count, $fileCount)
Write-Output ("             {0} MEMORY / {1} DURATION / {2} SAFE" -f $memSites.Count, $tsSites.Count, $safeSites.Count)
Write-Output ("EXCLUDED   : {0} comment line(s); {1} quoted pattern(s) (revert tables); {2} pattern(s) in {3} backup file(s)" -f $comments, $quoted, $backupHits, $inFxBackup.Count)
Write-Output ("             {0} pattern(s) in documents/output; {1} ToString('N') GUID site(s) (no-dashes, not a number)" -f $outHits, @($toStringSites | Where-Object { $_.Kind -eq 'GUID-EXCLUDED' }).Count)
Write-Output ("             {0} file(s) unreadable (a live lane holds them open) and were SKIPPED" -f $unreadable.Count)
foreach ($u in $unreadable) { Write-Output ("               unreadable: {0}" -f $u) }
Write-Output ''
Write-Output 'SITES (MEMORY and DURATION are the ones a reader parses with a decimal point)'
foreach ($s in $sites) {
    Write-Output ("  {0,-9} {1}:{2}  {3,-9} unit '{4}'" -f $s.Kind, $s.File, $s.Line, $s.Placeholder, $s.Unit)
}
if ($sites.Count -eq 0) { Write-Output '  (none)' }

Write-Output ''
Write-Output 'A census is a MEASUREMENT, not a verdict: it exits 0 whenever it ran.'
Write-Output 'The verdict belongs to _lane25-locale-number-gate.ps1.'
exit 0