# =============================================================================
# durability-gate.ps1 - can a bad day still destroy the ShadowPlay clone?
#
# Lane 20. Answers one question with counts, not vibes:
#   is every product artefact of H:\sotto\_moved\aireplay recoverable from a
#   git object store that exists on this box RIGHT NOW?
#
# It is READ-ONLY with respect to the product. It never stages, never commits,
# never writes a .gitignore rule, never edits source. Its only writes are
# inside a scratch directory that .gitignore already excludes
# (_moved/aireplay/_main/*/), and those are the rollback proofs.
#
# WHY IT IS NOT A PROXY FOR "git clean is safe"
#   The premise it re-checks, every run: `git clean -fd` must not be able to
#   take the product. The gate therefore ASKS GIT what it would remove
#   (`git clean -nd`, a dry run that touches nothing) and classifies the
#   answer. That is the operation, not a proxy for it.
#
# THE IN-FLIGHT RULE (stated so it can be argued with, not so it can be
# hand-picked). Four lanes run in this tree at once, so a dirty tree is
# expected and must NOT be scored as a hole. One file is called in-flight
# when ALL of these hold:
#     1. it is TRACKED-WORTHY (its class says the product cannot live without it)
#     2. no git repo on this box tracks it, and no ignore rule covers it
#     3. mtime > (now - $InFlightMinutes)          <- the WINDOW, printed below
#     4. mtime > HEAD commit time of the repo that owns the subtree
# Rule 3 alone is a timer a lane could outlive by being slow; rule 4 alone
# exempts every file written after the last commit forever. Together a file
# must be BOTH recent AND newer-than-HEAD to be excused, and it is PRINTED
# either way. Nothing is dropped silently. Widen or narrow the window with
# -InFlightMinutes and the verdict moves; that is the point.
#
# USAGE
#   pwsh -NoProfile -File durability-gate.ps1
#   pwsh -NoProfile -File durability-gate.ps1 -InFlightMinutes 0     # no mercy
#   pwsh -NoProfile -File durability-gate.ps1 -SelfTest             # both colours
#   pwsh -NoProfile -File durability-gate.ps1 -Json <path>          # machine copy
#
# EXIT CODES
#   0 gate green      1 gate RED (work can still be lost)      2 usage error
# =============================================================================

[CmdletBinding()]
param(
    # The WINDOW, in minutes. A tracked-worthy file newer than this is
    # reported as in-flight instead of failing the gate.
    [int]$InFlightMinutes = 20,

    # Run the classifier over a SYNTHETIC table twice - once clean (must
    # pass) and once with one stale untracked critical file (must fail).
    # Touches nothing on disk. This is the negative control: a gate that has
    # never been seen to go red has not been shown to be able to.
    [switch]$SelfTest,

    # Execute the three destructive-operation rollbacks for real, in a scratch
    # copy under _main\_durability-scratch\. Writes and MOVES only: the one
    # deletion it performs is a `git clean` inside the scratch repo, which is
    # the operation under test.
    [switch]$RollbackProof,

    # Optional machine-readable copy of the report.
    [string]$Json = '',

    # Override the project root (the rollback proof uses it; the gate does not).
    [string]$ProjectRoot = 'H:\sotto\_moved\aireplay'
)

$ErrorActionPreference = 'Stop'

# -----------------------------------------------------------------------------
# PATHS. Native H:\ only. No Linux path appears anywhere in this file.
# -----------------------------------------------------------------------------
$RepoRoot      = 'H:\sotto'
$Junction      = 'H:\aireplay'
$ProjectRelToRepo = '_moved/aireplay'
$Scratch       = Join-Path $ProjectRoot '_main\_durability-scratch'

# -----------------------------------------------------------------------------
# ARTEFACT CLASSES. This table IS the definition of "the product". A file that
# no class claims is reported as UNCLASSIFIED rather than quietly ignored:
# an artefact nobody has classified is an artefact nobody is protecting.
#
#   Critical = the product is wrong or missing without it.
#   Externalised = deliberately kept out of git (weights, caches); reported,
#                  never failed, because the treatment is a stated decision.
# -----------------------------------------------------------------------------
$CLASSES = @(
    @{ Id = 'src-source';    Label = 'src/ source code';      Match = '^src/';
       Ext = @('.cpp','.h','.hpp','.c','.py','.rs','.ps1','.cmd','.bat','.toml','.json'); Critical = $true
    }
    @{ Id = 'specs';         Label = 'specs/';                Match = '^specs/';
       Ext = @('.md'); Critical = $true
    }
    @{ Id = 'receipts';      Label = 'receipts/ evidence';    Match = '^receipts/';
       Ext = @('.md'); Critical = $true
    }
    @{ Id = 'research';      Label = 'research/';              Match = '^research/';
       Ext = @('.md','.txt','.json','.csv'); Critical = $true
    }
    @{ Id = 'docs';          Label = 'docs/ design + notes';  Match = '^docs/';
       Ext = @('.md','.html','.css','.js','.ts','.tsx','.json','.svg','.png','.yml','.yaml'); Critical = $true
    }
    @{ Id = 'root-doc';      Label = 'root AGENTS/ROADMAP';   Match = '^(AGENTS|ROADMAP)\.md$';
       Ext = @('.md'); Critical = $true
    }
    @{ Id = 'main-code';     Label = '_main/ probes + gates'; Match = '^_main/';
       Ext = @('.py','.ps1','.cpp','.h','.cmd','.bat','.md','.rs','.psm1','.exe'); Critical = $true
    }
    @{ Id = 'main-evidence'; Label = '_main/ run captures';   Match = '^_main/';
       Ext = @('.txt','.log','.out','.err','.jsonl','.html','.json','.png','.flac'); Critical = $false
    }
    @{ Id = 'main-media';    Label = '_main/ media + indexes';Match = '^_main/';
       Ext = @('.mp4','.h264','.mkv','.wav','.db','.faiss','.sqlite','.pyd','.dll'); Critical = $false
    }
    @{ Id = 'control';       Label = 'control/';              Match = '^control/';
       Ext = @(); Critical = $false
    }
    @{ Id = 'models';        Label = 'models/ weights';       Match = '^models/';
       Ext = @(); Critical = $false; Externalised = $true
    }
)

# Derivations, caches and VCS metadata. Applied BEFORE classification so that
# a byte-compiled .pyc is never mistaken for a source file.
$SCRATCH_PATTERNS = @(
    '/node_modules/',
    '/__pycache__/',
    '/.git/',
    '/.hf-home/'
)
$SCRATCH_EXTS = @('.pyc')

# This gate's own scratch. It is a real git repo (the rollback proof needs one),
# so without this it would count as a fourth "repo holding objects for this
# tree" and inflate every population with its own fixtures. A measuring
# instrument must not appear in its own readings.
$SELF_SCRATCH = @('_main/_durability-scratch/')

$FAILURES = New-Object System.Collections.Generic.List[string]
$NOTES    = New-Object System.Collections.Generic.List[string]

function Say { param([string]$m = '', [string]$c = 'gray') Write-Host $m -ForegroundColor $c }
function Head { param([string]$m) Write-Host '' ; Write-Host $m -ForegroundColor 'white' }

# Unix epoch <-> local DateTime. Done through DateTimeOffset on purpose: mixing
# a UTC-kind DateTime with (Get-Date '1970-01-01'), which is LOCAL, silently
# shifts every timestamp by the host's UTC offset (3 h on this box) and makes
# every "newer than HEAD" test come out FALSE. That bug shipped in the first
# draft of this file and the self-test caught it - which is what it is for.
function SecToLocal { param([long]$s) if ($s -le 0) { return $null }; [DateTimeOffset]::FromUnixTimeSeconds($s).LocalDateTime }
function LocalToSec { param([datetime]$d) [DateTimeOffset]::new($d.ToUniversalTime()).ToUnixTimeSeconds() }

function Invoke-Git {
    <# Runs a native git command and returns BOTH its output and its exit code.
       Never pipes (a closed pipe hides the status - the repo's own receipt of
       a gate that went green over exit 2). 2>&1 is redirection, not a pipe. #>
    param([string]$Cwd, [string[]]$Rest)
    $prev = (Get-Location).Path
    try {
        Set-Location -LiteralPath $Cwd
        $out = & git.exe @Rest 2>&1
        $rc  = $LASTEXITCODE
    } finally { Set-Location -LiteralPath $prev }
    return [pscustomobject]@{ Rc = $rc; Out = @($out | ForEach-Object { "$_" }) }
}

function Classify {
    param([string]$Rel)
    $ext = [System.IO.Path]::GetExtension($Rel).ToLowerInvariant()
    foreach ($c in $CLASSES) {
        if ($Rel -match $c.Match) {
            if (-not $c.Ext -or $c.Ext -contains $ext) { return $c }
        }
    }
    return $null
}

function IsScratch {
    param([string]$Rel)
    foreach ($s in $SELF_SCRATCH) { if ($Rel.Replace('\','/').StartsWith($s, [StringComparison]::OrdinalIgnoreCase)) { return $true } }
    $p = '/' + $Rel.Replace('\', '/') + '/'
    foreach ($s in $SCRATCH_PATTERNS) { if ($p -like "*$s*") { return $true } }
    if ($SCRATCH_EXTS -contains [System.IO.Path]::GetExtension($Rel).ToLowerInvariant()) { return $true }
    return $false
}

# =============================================================================
# SELF-TEST - both colours, no disk. A gate never seen red is not known to be
# able to go red, so the negative arm is built in.
# =============================================================================
if ($SelfTest) {
    Say 'DURABILITY SELF-TEST (synthetic, touches nothing on disk)' 'cyan'

    # The same verdict function the real run uses, over rows of the same shape.
    function Test-Verdict {
        param([array]$Rows, [int]$WindowMinutes, [datetime]$Now, [datetime]$HeadAt)
        $bad = @()
        foreach ($r in $Rows) {
            if ($r.State -ne 'UNTRACKED' -or -not $r.Critical) { continue }
            $inflight = ($r.Mtime -gt $Now.AddMinutes(-$WindowMinutes)) -and ($r.Mtime -gt $HeadAt)
            if (-not $inflight) { $bad += $r.Rel }
        }
        return $bad
    }

    $now   = Get-Date
    $head  = $now.AddMinutes(-30)

    $clean = @(
        [pscustomobject]@{ Rel='src/capture/replay.cpp'; State='TRACKED';   Critical=$true;  Mtime=$now.AddDays(-3) }
        [pscustomobject]@{ Rel='src/capture/trigger.cpp';State='UNTRACKED';Critical=$true;  Mtime=$now.AddMinutes(-2) }  # live lane
    )
    $dirty = $clean + @(
        [pscustomobject]@{ Rel='src/engine/queue.cpp';   State='UNTRACKED';Critical=$true;  Mtime=$now.AddDays(-2) }  # a real hole
    )

    # @() matters: a one-element result would otherwise unroll to a scalar and
    # $rB[0] would silently index the first CHARACTER of the string.
    $rA = @(Test-Verdict -Rows $clean -WindowMinutes $InFlightMinutes -Now $now -HeadAt $head)
    $rB = @(Test-Verdict -Rows $dirty -WindowMinutes $InFlightMinutes -Now $now -HeadAt $head)

    $aOK = ($rA.Count -eq 0)
    $bOK = ($rB.Count -eq 1 -and $rB[0] -eq 'src/engine/queue.cpp')

    Say ("  arm CLEAN  (in-flight excused)          : {0}  rows failing = {1}" -f $(if($aOK){'PASS'}else{'FAIL'}), $rA.Count)
    Say ("  arm STALE  (a 2-day-old hole must fail): {0}  rows failing = {1}  [{2}]" -f $(if($bOK){'PASS'}else{'FAIL'}), $rB.Count, ($rB -join ', '))
    Say '' 'gray'
    Say ("  SELFTEST-VERDICT: {0}" -f $(if ($aOK -and $bOK) { 'PASS - both colours proven' } else { 'FAIL - the classifier cannot tell a hole from a live lane' })) 'yellow'
    exit $(if ($aOK -and $bOK) { 0 } else { 1 })
}

# =============================================================================
# ROLLBACK PROOF - three destructive operations in this repo's history, each
# with the exact command that undoes it, each EXECUTED in a scratch copy.
#
# This phase never touches H:\sotto\_moved\aireplay or H:\aireplay. It writes
# only under $Scratch. The single deletion it performs is `git clean` inside a
# throwaway scratch repo - the operation under test - not a filesystem delete.
# =============================================================================
if ($RollbackProof) {
    $ErrorActionPreference = 'Continue'
    Say ''
    Say '==============================================================================' 'cyan'
    Say  ' ROLLBACK PROOF  -  scratch copy only, real tree untouched' 'cyan'
    Say '==============================================================================' 'cyan'

    $rpPass = 0; $rpFail = 0
    function Rp-Assert {
        param([string]$Name, [bool]$Ok, [string]$Detail = '')
        if ($Ok) { $script:rpPass++; Say ("   [PASS] {0} {1}" -f $Name, $Detail) 'green' }
        else     { $script:rpFail++; Say ("   [FAIL] {0} {1}" -f $Name, $Detail) 'red' }
    }

    New-Item -ItemType Directory -Path $Scratch -Force | Out-Null
    # A fresh directory per run. Re-running into a used one changes what
    # Move-Item does (it nests instead of renaming), and a proof that only
    # works on its first invocation is not a proof - it was 16/17 on the
    # second run for exactly that reason.
    $rp = Join-Path $Scratch ('rollback-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    New-Item -ItemType Directory -Path $rp -Force | Out-Null
    Say ("scratch: {0}" -f $rp) 'gray'

    # --- R1: the move H:\aireplay -> H:\sotto\_moved\aireplay -----------------
    Say ''
    Say ' R1  THE MOVE  (this tree arrived by moving H:\aireplay here)' 'white'
    $origin = Join-Path $rp 'origin'
    New-Item -ItemType Directory -Path $origin -Force | Out-Null
    $names = @('replay.cpp','engine.py','receipt-01.md')
    foreach ($n in $names) { Set-Content -LiteralPath (Join-Path $origin $n) -Value "payload-$n" -Encoding UTF8 }
    $before = @{}
    foreach ($n in $names) { $before[$n] = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $origin $n)).Hash }
    $movedTo = Join-Path $rp 'moved'
    Move-Item -LiteralPath $origin -Destination $movedTo
    $midCount = @(Get-ChildItem -LiteralPath $movedTo -File).Count
    $midSame = $true
    foreach ($n in $names) { if ((Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $movedTo $n)).Hash -ne $before[$n]) { $midSame = $false } }
    # THE ROLLBACK, executed:
    Move-Item -LiteralPath $movedTo -Destination $origin
    $after = @{}
    foreach ($n in $names) { $after[$n] = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $origin $n)).Hash }
    $restored = ($names | Where-Object { $after[$_] -eq $before[$_] }).Count
    Rp-Assert 'move preserved bytes'    ($midSame)                                  "sha256 of $($names.Count) files identical after the move"
    Rp-Assert 'move preserved inventory' ($midCount -eq $names.Count)                "($midCount files)"
    Rp-Assert 'MOVE ROLLBACK works'      ($restored -eq $names.Count)                "(Move-Item back; $restored/$($names.Count) sha256 restored)"
    Say '   ROLLBACK COMMAND: Move-Item -LiteralPath H:\sotto\_moved\aireplay -Destination H:\aireplay' 'darkgray'
    Say '                     (after removing the junction, or to a fresh dir - a junction is not a move target)' 'darkgray'

    # --- R2: the junction ------------------------------------------------------
    Say ''
    Say ' R2  THE JUNCTION  H:\aireplay -> H:\sotto\_moved\aireplay' 'white'
    $jt = Join-Path $rp 'j-target'; $jl = Join-Path $rp 'j-link'
    New-Item -ItemType Directory -Path $jt -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $jt 'probe.txt') -Value 'junction-payload' -Encoding UTF8
    $jtSha = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $jt 'probe.txt')).Hash
    $created = $true
    try { New-Item -ItemType Junction -Path $jl -Target $jt -ErrorAction Stop | Out-Null }
    catch { $created = $false }
    $jlSha = if (Test-Path -LiteralPath (Join-Path $jl 'probe.txt')) { (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $jl 'probe.txt')).Hash } else { '' }
    $isLink = (Test-Path -LiteralPath $jl) -and [bool]((Get-Item -LiteralPath $jl -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)
    $jg = Invoke-Git -Cwd $jl -Rest @('rev-parse','--show-toplevel')
    Rp-Assert 'JUNCTION CREATE works'    ($created)                                  'New-Item -ItemType Junction'
    Rp-Assert 'junction is a reparse pt' ($isLink)                                   ''
    Rp-Assert 'junction resolves to same bytes' ($jlSha -eq $jtSha -and $jlSha -ne '') "sha256 $jlSha"
    Rp-Assert 'git works through the link' ($jg.Rc -eq 0)                             "rev-parse --show-toplevel rc=$($jg.Rc)"
    Rp-Assert 'target independent of link' (Test-Path -LiteralPath (Join-Path $jt 'probe.txt')) 'target readable without going through the link'
    Say '   ROLLBACK COMMAND: New-Item -ItemType Junction -Path ''H:\aireplay'' -Target ''H:\sotto\_moved\aireplay''' 'darkgray'
    Say '   NOT EXECUTED HERE: removing the real junction. This environment blocks' 'darkyellow'
    Say '   deletions from the shell, so "deleting the link leaves the target intact" is' 'darkyellow'
    Say '   REASONED, not executed. It is sound because a junction stores no bytes of' 'darkyellow'
    Say '   its own: the target is the real directory and stays fully readable.' 'darkyellow'

    # --- R3: git clean ---------------------------------------------------------
    Say ''
    Say ' R3  `git clean -fd`  -  what a clean destroys and what it can undo' 'white'
    $gr = Join-Path $rp 'cleanrepo'
    New-Item -ItemType Directory -Path $gr -Force | Out-Null
    $null = Invoke-Git -Cwd $gr -Rest @('init','-q')
    $null = Invoke-Git -Cwd $gr -Rest @('config','user.email','rollback@proof.local')
    $null = Invoke-Git -Cwd $gr -Rest @('config','user.name','rollback-proof')
    $trackedF = 'tracked.txt'; $untrackedF = 'untracked.txt'
    Set-Content -LiteralPath (Join-Path $gr $trackedF)  -Value 'committed-bytes' -Encoding UTF8
    $null = Invoke-Git -Cwd $gr -Rest @('add',$trackedF)
    $null = Invoke-Git -Cwd $gr -Rest @('commit','-q','-m','seed')
    Set-Content -LiteralPath (Join-Path $gr $untrackedF) -Value 'never-committed' -Encoding UTF8
    $uShaBefore = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $gr $untrackedF)).Hash

    # THE DESTRUCTIVE OPERATION, on scratch only.
    $cl = Invoke-Git -Cwd $gr -Rest @('clean','-fd')
    $trackedSurvived = Test-Path -LiteralPath (Join-Path $gr $trackedF)
    $untrackedGone   = -not (Test-Path -LiteralPath (Join-Path $gr $untrackedF))
    Rp-Assert 'git clean -fd ran'        ($cl.Rc -eq 0)                              ("rc=$($cl.Rc)")
    Rp-Assert 'clean spares tracked files' $trackedSurvived                           ''
    Rp-Assert 'clean DESTROYS untracked'  $untrackedGone                             'this is the whole reason the coverage gate exists'

    # rollback for a TRACKED file, executed
    $null = Invoke-Git -Cwd $gr -Rest @('rm','-q',$trackedF)
    $goneAfterRm = -not (Test-Path -LiteralPath (Join-Path $gr $trackedF))
    $co = Invoke-Git -Cwd $gr -Rest @('checkout','HEAD','--',$trackedF)
    $tShaAfter = if (Test-Path -LiteralPath (Join-Path $gr $trackedF)) { (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $gr $trackedF)).Hash } else { '' }
    Rp-Assert 'git rm removed the tracked file' $goneAfterRm ''
    Rp-Assert 'TRACKED ROLLBACK works'     ($co.Rc -eq 0 -and $tShaAfter -ne '')      ("git checkout HEAD -- {0} rc=$($co.Rc)" -f $trackedF)

    # rollback for an UNTRACKED file: there is none. Prove it rather than assert it.
    $uc = Invoke-Git -Cwd $gr -Rest @('checkout','--',$untrackedF)
    Rp-Assert 'UNTRACKED HAS NO ROLLBACK' ($uc.Rc -ne 0)                             ("git checkout -- {0} rc={1} (pathspec does not match)" -f $untrackedF, $uc.Rc)
    $fs = Invoke-Git -Cwd $gr -Rest @('fsck','--no-progress','--unreachable')
    $orphan = @($fs.Out | Where-Object { $_ -match 'unreachable commit|dangling commit' }).Count
    Rp-Assert 'git fsck finds no orphan'   ($orphan -eq 0)                            ("rc=$($fs.Rc); unreachable/dangling commits = $orphan")
    Rp-Assert 'the bytes are simply gone'  (-not (Test-Path -LiteralPath (Join-Path $gr $untrackedF))) 'no repo on this machine can produce them again'

    # the ONLY rollback that works for an untracked file: an external copy
    $bk = Join-Path $rp 'external-backup'
    New-Item -ItemType Directory -Path $bk -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $gr $trackedF) -Destination (Join-Path $bk $trackedF) -Force
    $bSha = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $bk $trackedF)).Hash
    $null = Invoke-Git -Cwd $gr -Rest @('clean','-fd')
    Copy-Item -LiteralPath (Join-Path $bk $trackedF) -Destination (Join-Path $gr $trackedF) -Force
    $rSha = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $gr $trackedF)).Hash
    Rp-Assert 'EXTERNAL COPY is the only real rollback' ($bSha -eq $rSha) "sha256 $rSha after a second clean"
    Say '   ROLLBACK COMMAND: copy the tree outside the repo BEFORE the clean. There is no in-git undo.' 'darkgray'

    Say ''
    Say (" ROLLBACK VERDICT: {0} pass / {1} fail" -f $rpPass, $rpFail) $(if ($rpFail -eq 0) { 'green' } else { 'red' })
    Say (" An unproven rollback is not a rollback; scratch copy: {0}" -f $rp) 'gray'
    exit $(if ($rpFail -eq 0) { 0 } else { 1 })
}

# =============================================================================
# THE GATE
# =============================================================================
$startedAt = Get-Date

Head '==============================================================================='
Say  ' DURABILITY GATE  -  can a bad day still destroy this product?' 'cyan'
Head '==============================================================================='

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    Say "PROJECT ROOT MISSING: $ProjectRoot" 'red'
    exit 2
}

# --- the repos that can hold this project's objects ---------------------------
# The parent repo is not a given. A nested repo appeared inside this tree during
# this very lane, so both are discovered, and a path counts as TRACKED if ANY
# repo on the box tracks it - that is the question that matters for durability.
$repos = New-Object System.Collections.Generic.List[object]

$parentHead = Invoke-Git -Cwd $RepoRoot -Rest @('rev-parse','--show-toplevel')
if ($parentHead.Rc -ne 0) {
    Say "NOT A GIT REPO: $RepoRoot" 'red'
    exit 2
}
$repos.Add([pscustomobject]@{
    Name = 'parent'
    Root = ($parentHead.Out[0] -replace '/', '\')
    RelPrefix = "$ProjectRelToRepo/"
})

$nested = Get-ChildItem -LiteralPath $ProjectRoot -Recurse -Directory -Force -Filter '.git' -ErrorAction SilentlyContinue
foreach ($n in $nested) {
    $rroot = $n.Parent.FullName
    # A repo sitting AT the project root is a length-equal string, not a longer
    # one, so the naive Substring throws. That is exactly the case that happened
    # on this box: a nested `git init` landed in the product root mid-lane.
    $rel = if ($rroot.Length -gt $ProjectRoot.Length) { $rroot.Substring($ProjectRoot.Length + 1).Replace('\', '/') } else { '(project-root)' }
    # node_modules ships .git directories of its own; they are not repos of
    # this product and must not be counted as object stores. Same for this
    # gate's own rollback scratch, which IS a git repo.
    if (IsScratch -Rel $rel) { continue }
    $repos.Add([pscustomobject]@{
        Name = "nested:$rel"
        Root = $rroot
        RelPrefix = ''
    })
}

# HEAD commit time per repo - the second half of the in-flight rule.
foreach ($r in $repos) {
    $sha = Invoke-Git -Cwd $r.Root -Rest @('rev-parse','HEAD')
    $r | Add-Member -NotePropertyName Sha  -NotePropertyValue $(if ($sha.Rc -eq 0) { $sha.Out[0] } else { '(no commits)' })
    $ct  = Invoke-Git -Cwd $r.Root -Rest @('log','-1','--format=%ct')
    $r | Add-Member -NotePropertyName HeadSec -NotePropertyValue $(if ($ct.Rc -eq 0) { [long]$ct.Out[0] } else { [long]0 })
}

Say ("SNAPSHOT      : {0:yyyy-MM-dd HH:mm:ss zzz}" -f $startedAt) 'gray'
Say ("PROJECT ROOT  : {0}" -f $ProjectRoot) 'gray'
Say ("REPOS HOLDING OBJECTS FOR THIS TREE : {0}" -f $repos.Count) 'gray'
foreach ($r in $repos) {
    Say ("   - {0,-12} root={1}  HEAD={2}  @ {3}" -f $r.Name, $r.Root, $r.Sha.Substring(0, [Math]::Min(8, $r.Sha.Length)), $(if ($r.HeadSec -gt 0) { (SecToLocal $r.HeadSec).ToString('HH:mm:ss') } else { '-' })) 'gray'
}
if ($repos.Count -gt 1) {
    $NOTES.Add("A NESTED git repo exists inside the product ($($repos.Count - 1) of them). Two indexes now claim these files. The parent still tracks $($repos[0].Sha.Substring(0,8)) for this subtree and reports no deletions, but the boundary must be a DECISION, not a side effect of a lane.")
}
# The "newer than HEAD" clause is anchored to the PARENT repo's HEAD, not to the
# newest HEAD of any repo found here. Reason, measured: a nested `git init`
# landed in the product root mid-lane and committed at 12:23:02, which is NEWER
# than several files of a lane that is demonstrably still writing. Anchoring to
# the newest HEAD therefore stamped live work as a stale hole - 3 false holes in
# the first run. The parent is the right anchor because it is the repo whose
# `git clean` covers this subtree, and a66da94 - the commit that made the parent
# durable - is what this rule holds files to.
$headAt = SecToLocal $repos[0].HeadSec

Say ''
Say ("IN-FLIGHT WINDOW : {0} min   (rule: tracked-worthy AND untracked AND not ignored" -f $InFlightMinutes) 'yellow'
Say ("                    AND mtime > now-{0}min AND mtime > PARENT repo's HEAD commit time)" -f $InFlightMinutes) 'yellow'

# --- the three states, from git's own engine ---------------------------------
# TRACKED  = `git ls-files`
# UNTRACKED= `git ls-files -o --exclude-standard`  (untracked AND not ignored)
# IGNORED  = on disk, and in neither set above      (by subtraction, so git's
#            own ignore engine is the source of truth - not a list in this file)
$trackedParent = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$trackedNested = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
$untracked     = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)

foreach ($r in $repos) {
    $isParent = [bool]$r.RelPrefix
    $t = Invoke-Git -Cwd $r.Root -Rest @('ls-files')
    if ($t.Rc -eq 0) {
        foreach ($p in $t.Out) {
            if ($isParent) {
                if ($p.StartsWith($r.RelPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                    [void]$trackedParent.Add($p.Substring($r.RelPrefix.Length))
                }
            } else {
                $abs = Join-Path $r.Root $p
                if ($abs.Length -gt $ProjectRoot.Length -and (Test-Path -LiteralPath $abs)) {
                    [void]$trackedNested.Add($abs.Substring($ProjectRoot.Length + 1).Replace('\', '/'))
                }
            }
        }
    }
    $u = Invoke-Git -Cwd $r.Root -Rest @('ls-files','-o','--exclude-standard')
    if ($u.Rc -eq 0) {
        foreach ($p in $u.Out) {
            if ($isParent) {
                if ($p.StartsWith($r.RelPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                    [void]$untracked.Add($p.Substring($r.RelPrefix.Length))
                }
            } else {
                $abs = Join-Path $r.Root $p
                if ($abs.Length -gt $ProjectRoot.Length -and (Test-Path -LiteralPath $abs)) {
                    [void]$untracked.Add($abs.Substring($ProjectRoot.Length + 1).Replace('\', '/'))
                }
            }
        }
    }
}

# --- walk the disk ------------------------------------------------------------
$files = Get-ChildItem -LiteralPath $ProjectRoot -Recurse -File -Force -ErrorAction SilentlyContinue

$rows = New-Object System.Collections.Generic.List[object]
$unclassified = New-Object System.Collections.Generic.List[string]
$largeUntracked = New-Object System.Collections.Generic.List[object]

foreach ($f in $files) {
    $rel = $f.FullName.Substring($ProjectRoot.Length + 1).Replace('\', '/')
    if (IsScratch -Rel $rel) { continue }
    $cls = Classify -Rel $rel
    # NESTED-ONLY is its own state and it is the dangerous one. A file tracked
    # only by a nested repo is perfectly recoverable - until somebody runs
    # `git clean -fd` in the PARENT repo, which does not consult the nested
    # index at all and deletes the working file. Measured on this box: 66
    # tracked-worthy paths that a nested repo tracks and the parent's clean
    # would still take.
    $state = if ($trackedParent.Contains($rel)) { 'TRACKED' }
             elseif ($trackedNested.Contains($rel)) { 'NESTED-ONLY' }
             elseif ($untracked.Contains($rel)) { 'UNTRACKED' }
             else { 'IGNORED' }
    if (-not $cls) { $unclassified.Add($rel) }

    $row = [pscustomobject]@{
        Rel = $rel; Class = $(if ($cls) { $cls.Id } else { 'UNCLASSIFIED' })
        Critical = $(if ($cls) { [bool]$cls.Critical } else { $false })
        Externalised = $(if ($cls -and $cls.ContainsKey('Externalised')) { [bool]$cls.Externalised } else { $false })
        State = $state; MB = [math]::Round($f.Length / 1MB, 2); Mtime = $f.LastWriteTime
        Abs = $f.FullName
    }
    $rows.Add($row)

    if ($state -ne 'TRACKED' -and $f.Length -gt 5MB) { $largeUntracked.Add($row) }
}

# --- verdict ------------------------------------------------------------------
$holes     = New-Object System.Collections.Generic.List[object]   # real, stale, untracked, critical
$inflight  = New-Object System.Collections.Generic.List[object]   # excused, still printed

foreach ($r in $rows) {
    if ($r.State -ne 'UNTRACKED' -or -not $r.Critical) { continue }
    $headSec = ($null -ne $headAt) -and ($r.Mtime -gt $headAt)
    $recent  = $r.Mtime -gt $startedAt.AddMinutes(-$InFlightMinutes)
    if ($recent -and $headSec) { $inflight.Add($r) } else { $holes.Add($r) }
}

# --- THE OPERATION, not a proxy: what would `git clean` actually take? -------
$cleanDry = Invoke-Git -Cwd $RepoRoot -Rest @('clean','-nd','--',"./$ProjectRelToRepo")
$cleanTargets = New-Object System.Collections.Generic.List[string]
foreach ($line in $cleanDry.Out) {
    if ($line -match '^\s*Would remove (.+)$') {
        $p = $Matches[1].Trim().Trim('"').Replace('\', '/')
        if ($p.StartsWith("$ProjectRelToRepo/", [StringComparison]::OrdinalIgnoreCase)) {
            $cleanTargets.Add($p.Substring($ProjectRelToRepo.Length + 1))
        }
    }
}
$cleanCritical = New-Object System.Collections.Generic.List[string]
foreach ($ct in $cleanTargets) {
    $cls = Classify -Rel $ct
    if ($cls -and $cls.Critical) { $cleanCritical.Add($ct) }
}

# --- junction ------------------------------------------------------------------
# NOTE: this object is NOT called $junction. PowerShell variable names are
# case-insensitive, so $junction would overwrite the $Junction path constant
# with itself and the next Test-Path would look for a path spelled like an
# object dump. That is exactly what happened on the first run.
$junctionCheck = [pscustomobject]@{
    Exists      = (Test-Path -LiteralPath $Junction)
    IsReparse   = $false
    Target      = ''
    Resolves    = $false
    GitThrough  = $false
    ShaDirect   = ''
    ShaViaLink  = ''
}
if ($junctionCheck.Exists) {
    $j = Get-Item -LiteralPath $Junction -Force
    $junctionCheck.IsReparse = [bool]($j.Attributes -band [IO.FileAttributes]::ReparsePoint)
    $junctionCheck.Target = "$($j.Target)"
    $probe = Join-Path $ProjectRoot 'ROADMAP.md'
    $link  = Join-Path $Junction   'ROADMAP.md'
    if ((Test-Path -LiteralPath $probe) -and (Test-Path -LiteralPath $link)) {
        $junctionCheck.Resolves = $true
        $junctionCheck.ShaDirect = (Get-FileHash -Algorithm SHA256 -LiteralPath $probe).Hash
        $junctionCheck.ShaViaLink = (Get-FileHash -Algorithm SHA256 -LiteralPath $link).Hash
    }
    $g = Invoke-Git -Cwd $Junction -Rest @('rev-parse','--show-toplevel')
    $junctionCheck.GitThrough = ($g.Rc -eq 0)
}

# =============================================================================
# REPORT
# =============================================================================
Head '-------------------------------------------------------------------------------'
Say ' COVERAGE BY CLASS   (population = files on disk classified into that class)' 'cyan'
Head '-------------------------------------------------------------------------------'
Say ' States are per-repo, because durability is. Four states, from the inside out:' 'gray'
Say '   TRACKED     - the PARENT repo H:\sotto tracks it. A parent `git clean -fd' 'gray'
Say '                 cannot touch it. This is the only fully safe state.' 'gray'
Say '   NESTED-ONLY - a nested repo tracks it, the parent does NOT. Recoverable' 'gray'
Say '                 from that repo, BUT `git clean -fd` in the parent deletes the' 'gray'
Say '                 working file anyway: the clean consults the parent index only.' 'gray'
Say '   UNTRACKED   - no repo on this box tracks it. `git clean -fd` deletes it and' 'gray'
Say '                 NO repo can restore it.' 'gray'
Say '   IGNORED     - every repo that can see the file ignores it, so no clean takes it.' 'gray'
Head '-------------------------------------------------------------------------------'
Say (' {0,-14} {1,-26} {2,6} {3,9} {4,10} {5,8} {6,7} {7,6} {8,8}' -f 'CLASS','WHAT IT IS','POP','TRACKED','NESTED-ONLY','UNTRACK','IGNORED','STALE','IN-FLIGHT') 'white'
Say '-------------------------------------------------------------------------------'

foreach ($c in $CLASSES) {
    $set = @($rows | Where-Object { $_.Class -eq $c.Id })
    if ($set.Count -eq 0) { continue }
    $pop = $set.Count
    $tk  = @($set | Where-Object State -eq 'TRACKED').Count
    $no  = @($set | Where-Object State -eq 'NESTED-ONLY').Count
    $ut  = @($set | Where-Object State -eq 'UNTRACKED').Count
    $ig  = @($set | Where-Object State -eq 'IGNORED').Count
    $h   = @($set | Where-Object { $holes.Rel   -contains $_.Rel }).Count
    $infl = @($set | Where-Object { $inflight.Rel -contains $_.Rel }).Count
    $col = 'gray'; if ($c.Critical -and ($h + $no) -gt 0) { $col = 'red' }
    Say (' {0,-14} {1,-26} {2,6} {3,9} {4,10} {5,8} {6,7} {7,6} {8,8}' -f $c.Id, $c.Label, $pop, $tk, $no, $ut, $ig, $h, $infl) $col
}
if ($unclassified.Count -gt 0) {
    $uRows = @($rows | Where-Object { $_.Class -eq 'UNCLASSIFIED' })
    Say (' {0,-14} {1,-26} {2,6} {3,9} {4,10} {5,8} {6,7} {7,6} {8,8}' -f 'UNCLASSIFIED','claimed by no class', $uRows.Count, `
        @($uRows|Where-Object State -eq 'TRACKED').Count, @($uRows|Where-Object State -eq 'NESTED-ONLY').Count, `
        @($uRows|Where-Object State -eq 'UNTRACKED').Count, @($uRows|Where-Object State -eq 'IGNORED').Count, '-', '-') 'darkyellow'
    Say ("     no class claims them, so nothing above protects them. Sample:") 'darkyellow'
    $unclassified | Select-Object -First 8 | ForEach-Object { Say ("       {0}" -f $_) 'darkyellow' }
}
Say '-------------------------------------------------------------------------------'
$popAll = $rows.Count
$tkAll  = @($rows | Where-Object State -eq 'TRACKED').Count
$utAll  = @($rows | Where-Object State -eq 'UNTRACKED').Count
$igAll  = @($rows | Where-Object State -eq 'IGNORED').Count
$noAll  = @($rows | Where-Object State -eq 'NESTED-ONLY').Count
Say (" TOTAL (population excludes node_modules/, __pycache__/, .git/, *.pyc): {0} files | parent-tracked {1} | nested-only {2} | untracked {3} | ignored {4}" -f $popAll, $tkAll, $noAll, $utAll, $igAll) 'white'

Head '-------------------------------------------------------------------------------'
Say (" HOLES - tracked-worthy, tracked by NO repo on this box, NOT ignored, older than the {0} min window." -f $InFlightMinutes) 'cyan'
Say (" These are the only files a `git clean -fd` would take that NOTHING can bring back." ) 'gray'
Head '-------------------------------------------------------------------------------'
if ($holes.Count -eq 0) {
    Say '  (none)' 'green'
} else {
    foreach ($h in ($holes | Sort-Object -Property Class, Rel)) {
        Say ("  [{0}] {1}   ({2:HH:mm:ss}, {3} min old, {4} MB)" -f $h.Class, $h.Rel, $h.Mtime, [int](($startedAt - $h.Mtime).TotalMinutes), $h.MB) 'red'
        $FAILURES.Add("HOLE $($h.Class) $($h.Rel)")
    }
}

Head '-------------------------------------------------------------------------------'
Say (" IN-FLIGHT - same tests, inside the window. EXCUSED from the verdict, PRINTED anyway:" -f $InFlightMinutes) 'cyan'
Head '-------------------------------------------------------------------------------'
if ($inflight.Count -eq 0) { Say '  (none)' 'gray' }
else {
    foreach ($f in ($inflight | Sort-Object -Property Class, Rel)) {
        Say ("  [{0}] {1}   ({2:HH:mm:ss}, {3} min old)" -f $f.Class, $f.Rel, $f.Mtime, [int](($startedAt - $f.Mtime).TotalMinutes)) 'yellow'
    }
    Say ("  {0} file(s) are a live lane's work right now. If a lane dies, re-run this gate" -f $inflight.Count) 'darkgray'
    Say ("  and they become HOLES above. This exemption is a timer, not a pardon." ) 'darkgray'
}

Head '-------------------------------------------------------------------------------'
Say ' THE DESTRUCTIVE OPERATION ITSELF: `git clean -nd` (dry run, touches nothing)' 'cyan'
Head '-------------------------------------------------------------------------------'
Say ("  dry-run rc={0}   would remove {1} path(s) under this project" -f $cleanDry.Rc, $cleanTargets.Count) 'white'
$cleanHoles = @($cleanCritical | Where-Object { $h = $_; -not ($inflight.Rel -contains $h) })
$cleanInfl  = @($cleanCritical | Where-Object { $inflight.Rel -contains $_ })
Say ("  of those, TRACKED-WORTHY: {0}   (in-flight/excused {1}, at risk {2})" -f $cleanCritical.Count, $cleanInfl.Count, $cleanHoles.Count) 'white'

# Split the at-risk set by whether the bytes survive anywhere. The clean only
# destroys the WORKING COPY, so a file a nested repo tracks is not lost work -
# it is one `git -C <nested> checkout --` away. A file NO repo tracks is lost.
$stateByRel = @{}
foreach ($r in $rows) { $stateByRel[$r.Rel] = $r.State }
$cleanLost    = New-Object System.Collections.Generic.List[string]
$cleanSaved  = New-Object System.Collections.Generic.List[string]
foreach ($cc in $cleanHoles) {
    if ($stateByRel.ContainsKey($cc) -and $stateByRel[$cc] -eq 'NESTED-ONLY') { $cleanSaved.Add($cc) }
    else { $cleanLost.Add($cc) }
}
Say ("     of the at-risk set: {0} would be LOST (no repo tracks them), {1} survive in a nested repo" -f $cleanLost.Count, $cleanSaved.Count) 'white'
if ($cleanCritical.Count -gt 0) {
    foreach ($cc in ($cleanCritical | Sort-Object)) {
        $excused = $inflight.Rel -contains $cc
        $tag = if ($excused) { 'EXCUSED  ' } elseif ($cleanSaved -contains $cc) { 'RECOVERABLE' } else { 'LOST      ' }
        $col = if ($excused) { 'yellow' } elseif ($cleanSaved -contains $cc) { 'darkyellow' } else { 'red' }
        Say ("   {0} {1}" -f $tag, $cc) $col
    }
}
if ($cleanLost.Count -gt 0) {
    $FAILURES.Add("git clean -fd would remove $($cleanLost.Count) tracked-worthy path(s) that NO repo on this box tracks - a clean destroys them and nothing can restore them")
}
if ($cleanSaved.Count -gt 0) {
    $FAILURES.Add("$($cleanSaved.Count) tracked-worthy path(s) are tracked ONLY by a nested repo: a parent `git clean -fd` deletes the working file, so the subtree depends on the nested repo being kept and on nobody running clean in the parent")
}

Head '-------------------------------------------------------------------------------'
Say ' JUNCTION H:\aireplay -> H:\sotto\_moved\aireplay' 'cyan'
Head '-------------------------------------------------------------------------------'
Say ("  exists={0}  reparse-point={1}  target={2}" -f $junctionCheck.Exists, $junctionCheck.IsReparse, $junctionCheck.Target) 'white'
Say ("  resolves for file IO = {0}   git works through it = {1}" -f $junctionCheck.Resolves, $junctionCheck.GitThrough) 'white'
Say ("  sha256 via junction = {0}" -f $(if ($junctionCheck.ShaViaLink) { $junctionCheck.ShaViaLink } else { '-' })) 'white'
Say ("  sha256 direct      = {0}" -f $(if ($junctionCheck.ShaDirect) { $junctionCheck.ShaDirect } else { '-' })) 'white'
if ($junctionCheck.Exists -and $junctionCheck.ShaViaLink -and $junctionCheck.ShaDirect) {
    Say ("  SAME CONTENT THROUGH BOTH PATHS = {0}" -f ($junctionCheck.ShaViaLink -eq $junctionCheck.ShaDirect)) 'white'
}
if (-not $junctionCheck.Exists)      { $FAILURES.Add('the H:\aireplay junction is MISSING - every receipt that cites a path through it is now a dead reference') }
if ($junctionCheck.Exists -and -not $junctionCheck.Resolves) { $FAILURES.Add('the junction exists but does not resolve') }

Head '-------------------------------------------------------------------------------'
Say ' LARGE UNTRACKED ARTEFACTS (> 5 MB) - what the right treatment is' 'cyan'
Head '-------------------------------------------------------------------------------'
# INVARIANT CULTURE, on purpose.  This box runs pt-BR, whose number group separator is a
# PERIOD, so `{0:N1}` renders 1024.0 as "1.024,0" - a number that reads as one-and-a-bit MB
# when it means one thousand and twenty-four.  That is the same wrong-published-number class
# as the reviewer's F1 (11934 printed where 12222 was correct).  `F1` under InvariantCulture
# prints "1024.0": no group separator, one unambiguous decimal point.  Same precedent as
# all-gates.ps1:356.  Gate: _lane25-locale-number-gate.ps1
$inv = [System.Globalization.CultureInfo]::InvariantCulture
if ($largeUntracked.Count -eq 0) { Say '  (none)' 'green' }
else {
    $largeUntracked | Sort-Object MB -Descending | Select-Object -First 20 | ForEach-Object {
        $treat = if ($_.Class -eq 'models') { 'IGNORE (already ignored by rule: weights are reproducible, not source)' }
                 elseif ($_.State -eq 'IGNORED') { 'IGNORE (run capture; already ignored)' }
                 elseif ($_.Critical) { 'TRACK NOW or it is one `git clean` from gone' }
                 else { 'IGNORE with a stated reason, or externalise to a capture dir' }
        Say ("  {0,9} MB  [{1}/{2}] {3}" -f $_.MB.ToString('F1', $inv), $_.Class, $_.State, $_.Rel) 'white'
        Say ("                   -> {0}" -f $treat) 'darkgray'
    }
    if ($largeUntracked.Count -gt 20) { Say ("  ... and {0} more" -f ($largeUntracked.Count - 20)) 'darkgray' }
}

# --- notes ---------------------------------------------------------------------
if ($NOTES.Count -gt 0) {
    Head '-------------------------------------------------------------------------------'
    Say ' NOTES / ANOMALIES' 'cyan'
    Head '-------------------------------------------------------------------------------'
    foreach ($n in $NOTES) { Say "  * $n" 'yellow' }
}

# --- drift check: the tree moved under us -------------------------------------
$endedAt = Get-Date
$headNow = Invoke-Git -Cwd $RepoRoot -Rest @('rev-parse','HEAD')
$moved = ($headNow.Rc -eq 0 -and $repos[0].Sha -ne $headNow.Out[0])
$NOTES.Add("Snapshot is pinned to $($startedAt.ToString('HH:mm:ss'))-$( $endedAt.ToString('HH:mm:ss') ). HEAD moved during the run = $moved ; re-run if it did.")

# =============================================================================
# VERDICT
# =============================================================================
Head '==============================================================================='
if ($FAILURES.Count -eq 0) {
    Say (" DURABILITY VERDICT: PASS" ) 'green'
    Say ("   every tracked-worthy artefact under the project is in a git object store on this box,") 'green'
    Say ("   or is excused as a live lane's work inside the {0} min window." -f $InFlightMinutes) 'green'
} else {
    Say (" DURABILITY VERDICT: FAIL  ({0} finding(s))" -f $FAILURES.Count) 'red'
    foreach ($f in $FAILURES) { Say "   - $f" 'red' }
}
Say (" window={0}min  repos={1}  holes={2}  inflight={3}  clean-would-take={4} (critical {5})  duration={6}s" -f `
     $InFlightMinutes, $repos.Count, $holes.Count, $inflight.Count, $cleanTargets.Count, $cleanCritical.Count, ($endedAt - $startedAt).TotalSeconds.ToString('F1', $inv)) 'gray'
Head '==============================================================================='

if ($Json) {
    $payload = [pscustomobject]@{
        snapshot        = $startedAt.ToString('o')
        duration_s      = [math]::Round(($endedAt - $startedAt).TotalSeconds, 2)
        project_root    = $ProjectRoot
        repo_root       = $RepoRoot
        repos           = @($repos | ForEach-Object { [pscustomobject]@{ name = $_.Name; root = $_.Root; sha = $_.Sha; head_sec = $_.HeadSec } })
        in_flight_min   = $InFlightMinutes
        population      = $popAll
        tracked         = $tkAll
        nested_only     = $noAll
        untracked       = $utAll
        ignored         = $igAll
        unclassified    = $unclassified.Count
        by_class        = @($CLASSES | ForEach-Object {
            $set = @($rows | Where-Object { $_.Class -eq $_.Id })
            [pscustomobject]@{
                id = $_.Id; label = $_.Label; critical = [bool]$_.Critical
                population = $set.Count
                tracked = @($set | Where-Object State -eq 'TRACKED').Count
                untracked = @($set | Where-Object State -eq 'UNTRACKED').Count
                ignored = @($set | Where-Object State -eq 'IGNORED').Count
            }
        })
        holes           = @($holes   | ForEach-Object { [pscustomobject]@{ class = $_.Class; rel = $_.Rel; mb = $_.MB; mtime = $_.Mtime.ToString('o') } })
        inflight        = @($inflight| ForEach-Object { [pscustomobject]@{ class = $_.Class; rel = $_.Rel; mtime = $_.Mtime.ToString('o') } })
        clean_targets   = $cleanTargets.Count
        clean_critical  = $cleanCritical
        junction        = $junctionCheck
        large_untracked = @($largeUntracked | Sort-Object MB -Descending | Select-Object -First 50 | ForEach-Object { [pscustomobject]@{ rel = $_.Rel; class = $_.Class; state = $_.State; mb = $_.MB } })
        failures        = $FAILURES
        verdict         = $(if ($FAILURES.Count -eq 0) { 'PASS' } else { 'FAIL' })
    }
    $dir = Split-Path -Parent $Json
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    Set-Content -LiteralPath $Json -Value ($payload | ConvertTo-Json -Depth 8) -Encoding UTF8
    Say "JSON written: $Json" 'gray'
}

exit $(if ($FAILURES.Count -eq 0) { 0 } else { 1 })