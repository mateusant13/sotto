# collect-dirt.ps1 - READ-ONLY against H:\sotto. Never writes into the product tree.
# Emits machine-readable JSON for the manifest + backup steps.
$ErrorActionPreference = 'Stop'
$repo = 'H:\sotto'
$out  = 'I:\cc-tmp\dirtrescue'
New-Item -ItemType Directory -Force -Path $out | Out-Null

# --- exact path lists (-z => NUL separated, no quoting, spaces safe) ---
$raw = git -C $repo -c core.quotepath=false status --porcelain -uall -z
$entries = New-Object System.Collections.Generic.List[object]
$codes = $raw -split "`0"
for ($i = 0; $i -lt $codes.Count; $i++) {
    $e = $codes[$i]
    if ([string]::IsNullOrEmpty($e)) { continue }
    $code = $e.Substring(0, 2)
    $path = $e.Substring(3)
    if ($code -match 'R|C') { $i++ }   # rename/copy: skip the dest path
    $entries.Add([pscustomobject]@{ code = $code; path = $path })
}

# --- diff size per tracked-modified file ---
$numstat = @{}
foreach ($ln in (git -C $repo diff --numstat)) {
    if ($ln -notmatch '^(\d+|-)\t(\d+|-)\t(.+)$') { continue }
    $numstat[$Matches[3]] = [pscustomobject]@{ add = $Matches[1]; del = $Matches[2] }
}

$root = (Resolve-Path $repo).Path.TrimEnd('\')
$rows = New-Object System.Collections.Generic.List[object]
$missing = 0
foreach ($e in $entries) {
    $full = Join-Path $root ($e.path -replace '/', '\')
    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { $missing++; continue }
    $fi = Get-Item -LiteralPath $full -Force
    $isMod = $e.code -match 'M'
    $add = $null; $del = $null
    if ($isMod -and $numstat.ContainsKey($e.path)) {
        $a = $numstat[$e.path].add; $d = $numstat[$e.path].del
        $add = $(if ($a -eq '-') { 'bin' } else { [int]$a })
        $del = $(if ($d -eq '-') { 'bin' } else { [int]$d })
    }
    $rows.Add([pscustomobject]@{
        code   = $e.code
        kind   = $(if ($isMod) { 'tracked-modified' } else { 'untracked' })
        path   = $e.path
        bytes  = [int64]$fi.Length
        mtime  = $fi.LastWriteTimeUtc.ToString('yyyy-MM-dd HH:mm:ss')
        add    = $add
        del    = $del
    })
}

$summary = [pscustomobject]@{
    repo            = $repo
    branch          = (git -C $repo rev-parse --abbrev-ref HEAD)
    head            = (git -C $repo rev-parse HEAD)
    porcelainDefault= ((git -C $repo status --porcelain | Measure-Object -Line).Lines)
    porcelainUall   = ($entries.Count)
    trackedModified = @($rows | Where-Object { $_.kind -eq 'tracked-modified' }).Count
    untrackedFiles  = @($rows | Where-Object { $_.kind -eq 'untracked' }).Count
    totalFiles      = $rows.Count
    totalBytes      = [int64](($rows | Measure-Object -Property bytes -Sum).Sum)
    missingOnDisk   = $missing
}
$summary | ConvertTo-Json | Set-Content "$out\summary.json" -Encoding utf8
$rows | ConvertTo-Json -Depth 4 | Set-Content "$out\files.json" -Encoding utf8
$rows | Export-Csv "$out\files.csv" -NoTypeInformation -Encoding utf8
$summary | Format-List | Out-String | Write-Output