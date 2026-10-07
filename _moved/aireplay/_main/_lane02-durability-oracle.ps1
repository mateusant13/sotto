# LANE 02 - durability + worktree feasibility oracle. BOTH COLOURS.
#
# WHY: two facts decide how this project can be worked on at all, and both were
# UNKNOWN until measured:
#   (a) the product tree lives at H:\sotto\_moved\aireplay and is UNTRACKED in the
#       H:\sotto repo, so `git clean -fd` can delete the product, and so the 7
#       existing worktrees cannot see the product AT ALL;
#   (b) the owner directed "worktrees by default", which is only satisfiable once
#       (a) is fixed.
#
# This oracle NEVER mutates the repo. It only reads. It never runs git clean, never
# adds, never checks out, never resets. Its RED arm is a deliberately wrong path, so
# the instrument can say NO.
#
# Law 8: no drive walk, no model load, single pass, milliseconds.
# Usage: pwsh -File _main\_lane02-durability-oracle.ps1
# Exit : 0 = both arms behaved. Non-zero = the ORACLE is broken (not the tree).

$ErrorActionPreference = 'Continue'
$root = 'H:\sotto'
$prod = 'H:\sotto\_moved\aireplay'
$outFile = 'H:\sotto\_moved\aireplay\_main\lane02-durability.json'

function Measure-Tree {
    param([string]$Path, [string]$Label)
    # BUG FOUND IN THIS ORACLE'S OWN AUTHOR, 2026-10-07, by its own RED arm:
    # Test-Path on a RELATIVE path resolves against the PROCESS CWD, not the
    # repo root passed to git -C. So ARM-0 reported RED on a tree that is plainly
    # there. Every path is now joined onto $root before it is tested. This is the
    # "a control that can say NO is worth more than the numbers it guards" lesson,
    # applied to the guard itself.
    $abs = Join-Path $root $Path
    # ARM-A path is deliberately wrong: this must FAIL loudly, never pass quietly.
    if (-not (Test-Path -LiteralPath $abs)) {
        return [ordered]@{
            label    = $Label
            path     = $abs
            status   = 'RED'
            problem  = 'path does not exist - the oracle cannot measure a tree that is not there'
        }
    }
    $rel = $Path.Replace('\','/')
    $tracked = @(git -C $root ls-files -- $rel | Where-Object { $_ -and $_.Trim() })
    $untracked = @(git -C $root ls-files --others --exclude-standard -- $rel | Where-Object { $_ -and $_.Trim() })
    return [ordered]@{
        label             = $Label
        path              = $abs
        status            = 'GREEN'
        tracked_files     = $tracked.Count
        untracked_files   = $untracked.Count
    }
}

# What `git clean -fd` would actually delete. DRY RUN ONLY (-n). We never run -fd.
$cleanDry = @(git -C $root clean -nd -- _moved 2>$null)

$wts = @(git -C $root worktree list --porcelain 2>$null |
    Select-String -Pattern '^worktree ' | ForEach-Object { $_.Line -replace '^worktree ','' })
$wtProbe = @()
foreach ($w in $wts) {
    if ($w -eq $root) { continue }
    $probe = Join-Path $w.Replace('/','\') '_moved\aireplay\AGENTS.md'
    $wtProbe += [ordered]@{
        worktree        = $w
        sees_product    = (Test-Path -LiteralPath $probe)
    }
}

$arm0 = Measure-Tree -Path '_moved/aireplay' -Label 'ARM-0-real product tree'
$armA = Measure-Tree -Path '_moved/aireplay-THIS-PATH-DOES-NOT-EXIST' -Label 'ARM-A-corrupt (must be RED)'

$oracle_ok = ($arm0.status -eq 'GREEN') -and ($armA.status -eq 'RED')
$verdict = if ($oracle_ok) { 'GREEN' } else { 'RED' }

$report = [ordered]@{
    lane              = '02-durability-oracle'
    repo_root         = $root
    product_root      = $prod
    arms              = [ordered]@{ 'ARM-0-real' = $arm0; 'ARM-A-corrupt' = $armA }
    clean_dryrun_paths_under_moved = $cleanDry.Count
    worktrees         = $wtProbe
    worktrees_that_see_product = @($wtProbe | Where-Object { $_.sees_product }).Count
    oracle_verdict    = $verdict
    note              = 'DRY RUN ONLY. This oracle never runs git clean, never add/checkout/reset.'
}
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $outFile -Encoding UTF8

Write-Output "lane=02-durability-oracle"
Write-Output ("  ARM-0-real    : {0}  tracked={1}  untracked={2}" -f $arm0.status, $arm0.tracked_files, $arm0.untracked_files)
Write-Output ("  ARM-A-corrupt : {0}  {1}" -f $armA.status, $armA.problem)
Write-Output ("  git clean -nd _moved would remove : {0} paths" -f $cleanDry.Count)
Write-Output ("  worktrees total={0}  seeing the product={1}" -f $wtProbe.Count, $report.worktrees_that_see_product)
foreach ($w in $wtProbe) { Write-Output ("    {0}  sees_product={1}" -f $w.worktree, $w.sees_product) }
Write-Output ("  ORACLE: {0}  -> {1}" -f $verdict, $outFile)

if (-not $oracle_ok) { Write-Output 'ORACLE BROKEN: arms did not separate.'; exit 1 }
exit 0