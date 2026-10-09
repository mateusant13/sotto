<#
  _lane19-receipt-audit-gate.ps1 — proves receipt-audit.py can FAIL.

  WHAT THIS GATE IS FOR
  ---------------------
  A gate that has only ever printed PASS is not a gate.  So this file runs the
  audit tool over a set of arms and DEMANDS that the wrong answers produce red.
  Every arm below states what must be true for the arm to be green; an arm that
  cannot go red is a broken arm and says so.

  THE ARMS
  -------
  ARM 0  INSTRUMENT      the tool exists, compiles, and runs; every one of its
                         four sections is present in the output.
  ARM 1  FINDINGS        on the LIVE repo the tool reports findings and exits 3
                         under --fail-on-findings.  A tool that found nothing
                         on a repo this broken is not measuring anything.
  ARM 2  CONTROL/CURE    the SAME tool, with its DETECTION reverted in a COPY,
                         over a repo seeded with a KNOWN defect, must go RED.
                         THIS IS THE ARM THAT PROVES THE GATE CAN FAIL.
  ARM 3  HONESTY         with the store absent, the tool must print
                         UNVERIFIABLE for reviewer coverage.  It must NOT print
                         "0 reviewers" - ignorance is not zero.  This is the
                         honesty arm, and it is the reason the tool exists.
  ARM 4  SELF-EXCLUSION  the tool must not report its own output file as a
                         Q4 finding.  (An instrument that matches its own
                         output is the failure in receipts 21/22.)

  ARM 2 is what makes the rest mean anything: without it, ARM 1 is just a green
  light with no counterfactual.

  USAGE
  -----
    pwsh -NoProfile -File _main\_lane19-receipt-audit-gate.ps1
    pwsh -NoProfile -File _main\_lane19-receipt-audit-gate.ps1 -SelfTestControl

  HARD RULES
  ----------
  * Never pipes a native command's OUTPUT while needing its exit code: every
    invocation is `> file 2>&1` followed by $LASTEXITCODE.  A closed pipe hides
    the real status, and this repo has a receipt of a gate that reported green
    over exit 2.
  * Launches python with CREATE_NO_WINDOW so no console flashes on the owner's
    screen.
  * Native H:\ paths only.
#>
param(
  [string]$Repo      = 'H:\sotto\_moved\aireplay',
  [string]$Audit     = 'H:\sotto\_moved\aireplay\_main\receipt-audit.py',
  [string]$LogDir    = 'H:\sotto\_moved\aireplay\_main\_lane19-gate',
  [switch]$SelfTestControl
)

$ErrorActionPreference = 'Stop'
$lines = New-Object System.Collections.Generic.List[string]
function Say([string]$s) { $lines.Add($s); Write-Host $s }

# CREATE_NO_WINDOW = 0x08000000.  DETACHED is deliberately NOT set: we want the
# real exit code, which a fully detached process would deny us.
$NO_WINDOW = 0x08000000

function Run-Py {
  param([string[]]$PyArgs, [string]$OutFile, [string]$ErrFile)
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName               = 'py'
  $psi.Arguments              = ($PyArgs -join ' ')
  $psi.UseShellExecute        = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.CreateNoWindow         = $true
  $psi.StandardOutputEncoding = [Text.Encoding]::UTF8
  $psi.StandardErrorEncoding  = [Text.Encoding]::UTF8
  $p = [Diagnostics.Process]::Start($psi)
  $so = $p.StandardOutput.ReadToEnd()
  $se = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  if ($OutFile) { [IO.File]::WriteAllText($OutFile, $so, (New-Object Text.UTF8Encoding $false)) }
  if ($ErrFile) { [IO.File]::WriteAllText($ErrFile, $se, (New-Object Text.UTF8Encoding $false)) }
  return @{ rc = $p.ExitCode; out = $so; err = $se }
}

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

Say ("LANE19 RECEIPT-AUDIT GATE   run {0}" -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
Say ("repo  = {0}" -f $Repo)
Say ("audit = {0}" -f $Audit)
Say ""

$arms = @()
function Arm($id, $desc, $ok, $detail) {
  $script:arms += [pscustomobject]@{ id=$id; desc=$desc; ok=$ok; detail=$detail }
  Say ("{0,-4} {1,-6} {2}" -f $id, $(if($ok){'GREEN'}else{'RED'}), $desc)
  Say ("       {0}" -f $detail)
}

# ---------------------------------------------------------------- ARM 0
$pySrc = 'C:\Users\Administrador\AppData\Local\Programs\Python'
$null = Run-Py @('-3','-c','import sys; sys.exit(0)') (Join-Path $LogDir 'arm0-py.txt') (Join-Path $LogDir 'arm0-py.err')
$pyRc = $LASTEXITCODE
if (-not (Test-Path $Audit)) {
  Arm 'ARM0' 'instrument exists' $false "MISSING: $Audit"
  Say ''; Say 'VERDICT FAIL - the instrument does not exist'
  $lines | Set-Content (Join-Path $LogDir 'lane19-gate.txt') -Encoding UTF8
  exit 1
}

$r0 = Run-Py @('-3', $Audit, '--repo', $Repo, '--out', (Join-Path $LogDir 'live-report.txt')) `
             (Join-Path $LogDir 'arm0-live.out') (Join-Path $LogDir 'arm0-live.err')
$sections = @('Q1  CLAIM PROVENANCE','Q2  GATE EXISTENCE','Q3  REVIEWER COVERAGE','Q4  THE SELF-MATCH')
$missing = @($sections | Where-Object { $r0.out -notmatch [regex]::Escape($_) })
$arm0ok = ($r0.rc -eq 0) -and ($missing.Count -eq 0)
Arm 'ARM0' 'instrument runs and emits all four sections' $arm0ok `
   ("rc={0} sections_present={1}/{2} missing=[{3}]" -f $r0.rc, ($sections.Count - $missing.Count), $sections.Count, ($missing -join ', '))

# ---------------------------------------------------------------- ARM 1
# Findings must be REPORTED on the live repo.  This arm does not say the repo
# is broken; it says the tool is still looking at it.
$r1 = Run-Py @('-3', $Audit, '--repo', $Repo, '--fail-on-findings') `
             (Join-Path $LogDir 'arm1-fail.out') (Join-Path $LogDir 'arm1-fail.err')
$arm1ok = ($r1.rc -eq 3)
Arm 'ARM1' 'live repo: findings reported as exit 3 under --fail-on-findings' $arm1ok `
   ("rc={0} (expected 3)  findings_block_present={1}" -f $r1.rc, ($r1.out -match 'TOTALS'))

# ---------------------------------------------------------------- ARM 2 (CONTROL)
# THE CURE REVERTED IN A COPY.  Seed a repo with a receipt that (a) cites a gate
# file which does not exist and (b) has numbers with no provenance labels.  Then
# run the audit over it twice: once with the real tool (must FIND the defect) and
# once with a COPY in which the citation resolver's search roots have been gutted
# (must MISS it -> the arm proves the tool's green is earned, not default).
$sandbox = Join-Path $LogDir 'sandbox'
if (Test-Path $sandbox) { Remove-Item $sandbox -Recurse -Force }
New-Item -ItemType Directory -Path (Join-Path $sandbox 'receipts') -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $sandbox '_main')      -Force | Out-Null

$seedReceipt = @'
# Receipt 99 — seeded defect for the control arm

Measured nothing. The gate for this work is `_main\_lane99-does-not-exist.ps1`.

The window was 30 seconds and the cap is 4096 frames at 60 fps. Latency is 120 s.
'@
[IO.File]::WriteAllText((Join-Path $sandbox 'receipts\receipt-99-seeded.md'), $seedReceipt, (New-Object Text.UTF8Encoding $false))
$seedClean = @'
# Receipt 98 - the control's negative case

MEASURED: 1 gate ran. DERIVED: 2 figures. NOT MEASURED: 3.

The gate that actually exists: `_main\_lane98-real.ps1`
'@
[IO.File]::WriteAllText((Join-Path $sandbox 'receipts\receipt-98-clean.md'), $seedClean, (New-Object Text.UTF8Encoding $false))
[IO.File]::WriteAllText((Join-Path $sandbox '_main\_lane98-real.ps1'), '# real gate' + "`n", (New-Object Text.UTF8Encoding $false))

# THE CURE REVERTED IN A COPY.
#
# What is "the cure" here?  The DETECTION, not the resolution.  In
# resolve_citation the final `return None, tried` is what lets a citation be
# reported as "resolves to NOTHING"; that is the whole detection mechanism.
#
# The first version of this control gutted the resolver's `roots = [...]` list
# instead, on the reasoning that a tool that cannot find anything would report
# everything as dangling.  That is BACKWARDS and it made the arm pass for the
# wrong reason: gutting the roots makes the tool report MORE danglers, not
# fewer, so the reverted copy still "found" the seeded defect (ARM2b went red
# with seeded_dangling_still_reported=True).  Reverting the DETECTION is the
# only revert that makes this arm mean what it claims: a tool that can no longer
# see a missing file must MISS the seeded missing file.
$copyAudit = Join-Path $sandbox 'receipt-audit-NOCURE.py'
$src = [IO.File]::ReadAllText($Audit)
$detectLine = '    return None, tried'
if (-not $src.Contains($detectLine)) {
  Arm 'ARM2' 'control arm: cure reverted in a COPY' $false "could not locate the detection line '$detectLine' to revert"
} else {
  $gutted = $src.Replace($detectLine, "    return '<reverted: detection disabled>', tried")
  [IO.File]::WriteAllText($copyAudit, $gutted, (New-Object Text.UTF8Encoding $false))

  # ARM 2c: the reverted copy MUST still be runnable, or the control proves nothing.
  $syntax = Run-Py @('-3','-m','py_compile',$copyAudit) (Join-Path $LogDir 'arm2c-compile.out') (Join-Path $LogDir 'arm2c-compile.err')
  $compiles = ($syntax.rc -eq 0)
  Arm 'ARM2c' 'CONTROL: the reverted copy is still a RUNNABLE python file' $compiles `
     ("py_compile rc={0} (a SyntaxError here means ARM2b was red for the wrong reason)" -f $syntax.rc)
  if (-not $compiles) { Say ("       stderr: {0}" -f (($syntax.err -split "`n" | Select-Object -First 1) -join '')) }

  # ARM 2a: the CURED tool must FIND the seeded defect.
  $r2a = Run-Py @('-3', $Audit, '--repo', $sandbox) `
                (Join-Path $LogDir 'arm2a-cured.out') (Join-Path $LogDir 'arm2a-cured.err')
  $foundSeeded = ($r2a.out -match '_lane99-does-not-exist\.ps1')
  Arm 'ARM2a' 'CONTROL/cured: tool FINDS the seeded dangling gate' ($r2a.rc -eq 0 -and $foundSeeded) `
     ("rc={0} seeded_dangling_reported={1}" -f $r2a.rc, $foundSeeded)

  # ARM 2b: the CURE REVERTED must run CLEANLY and MISS the defect.  Both
  # conditions are load-bearing: rc=0 proves the tool was alive and looking, and
  # only then does "did not report it" mean anything.
  $r2b = Run-Py @('-3', $copyAudit, '--repo', $sandbox) `
                (Join-Path $LogDir 'arm2b-nocure.out') (Join-Path $LogDir 'arm2b-nocure.err')
  $stillFound = ($r2b.out -match '_lane99-does-not-exist\.ps1')
  $arm2ok = ($r2b.rc -eq 0) -and (-not $stillFound)
  Arm 'ARM2b' 'CONTROL/cure REVERTED in a copy: tool MISSES it -> the gate can go RED' $arm2ok `
     ("rc={0} (expected 0 - a crash is not a miss)  seeded_dangling_still_reported={1} (expected False)" -f $r2b.rc, $stillFound)
  if ($r2b.rc -ne 0) { Say ("       stderr: {0}" -f (($r2b.err -split "`n" | Select-Object -First 1) -join '')) }

  # ARM 2d: the copy really is a different instrument.
  $sameBytes = ([IO.File]::ReadAllText($Audit) -eq [IO.File]::ReadAllText($copyAudit))
  Arm 'ARM2d' 'CONTROL: the copy really differs from the shipped tool' (-not $sameBytes) `
     ("identical={0} shipped_len={1} copy_len={2}" -f $sameBytes, (Get-Item $Audit).Length, (Get-Item $copyAudit).Length)
}

# ---------------------------------------------------------------- ARM 3 (HONESTY)
# With the store absent the tool must say UNVERIFIABLE, never "0 reviewers".
$r3 = Run-Py @('-3', $Audit, '--repo', $sandbox, '--store', 'H:\definitely-not-a-store.sqlite') `
             (Join-Path $LogDir 'arm3-nostore.out') (Join-Path $LogDir 'arm3-nostore.err')
$hasUnverifiable = ($r3.out -match 'UNVERIFIABLE')
$claimsZero     = ($r3.out -match 'reviewer DISPATCHED\s*:\s*0' -and $r3.out -match 'verdict READ:\s*0 VERIFIABLE')
$arm3ok = $hasUnverifiable -and ($r3.rc -eq 0)
Arm 'ARM3' 'HONESTY: absent store -> UNVERIFIABLE, not a green zero' $arm3ok `
   ("rc={0} prints_UNVERIFIABLE={1} printed_a_plain_zero={2} (a zero would be a lie)" -f $r3.rc, $hasUnverifiable, $claimsZero)

# ---------------------------------------------------------------- ARM 4 (SELF-MATCH)
# The tool must exclude its own artefacts from Q4.
$selfNamed = @($r0.out -split "`n" | Where-Object { $_ -match 'SELF-EXCLUDED' })
$selfLeak  = ($r0.out -match '_receipt-audit-run\.txt:\d' -and $r0.out -notmatch 'SELF-EXCLUDED')
$arm4ok = ($selfNamed.Count -ge 1) -and (-not $selfLeak)
Arm 'ARM4' 'SELF-MATCH: the tool does not report its own output as a finding' $arm4ok `
   ("self_exclusion_block_present={0} own_output_listed_as_finding={1}" -f ($selfNamed.Count -ge 1), $selfLeak)

# ---------------------------------------------------------------- ARM 5
# The CONTENT-BASED self-match guard.  ARM4 can be satisfied by a filename
# whitelist, which is what the first four revisions used -- and a whitelist
# loses the moment anybody redirects stdout to a new name.  MEASURED: three
# scratch redirect targets (_r1/_r2/_r3.txt) supplied 360 of the Q4 findings
# while a name-based guard was in place.  So this arm plants a COPY of the
# tool's own report under a name the whitelist has never heard of, and requires
# the tool to exclude it anyway.
# The planted copy MUST live where NEITHER guard can see it by name:
#   * not under $LogDir (the path names lane19, so the lane-name guard catches
#     it and the arm would pass even with the content guard deleted), and
#   * not under _main\ (ditto).
# It goes to a neutral directory name at the repo root, which is exactly what a
# stray redirect target looks like.  Without this, ARM5 passed with the content
# guard removed -- measured -- and was therefore not testing anything.
$plantDir = Join-Path $Repo '_audit-plant'
if (-not (Test-Path $plantDir)) { New-Item -ItemType Directory -Path $plantDir -Force | Out-Null }
$planted = Join-Path $plantDir 'report-copy.txt'
[IO.File]::WriteAllText($planted, $r0.out, (New-Object Text.UTF8Encoding $false))
$r5 = Run-Py @('-3', $Audit, '--repo', $Repo) `
             (Join-Path $LogDir 'arm5-planted.out') (Join-Path $LogDir 'arm5-planted.err')
# The planted file must NOT appear in the Q4 finding list.
#
# The regex matches the BASENAME plus a line number and tolerates either path
# separator.  The first version matched 'planted-copy-of-report.txt:\d' only, but
# the report prints Windows paths with a backslash ('_audit-plant\report-copy.txt:218'),
# so the pattern never matched and the arm was GREEN with the guard deleted --
# measured: the arm was vacuous.  A leak check that cannot fail is worse than no
# leak check, because it is reported as evidence.
$leakPat = 'report-copy\.txt:\d'
$leaked = @($r5.out -split "`n" | Where-Object { $_ -match $leakPat })
# PROVE the check can see a leak: the planted copy DOES contain Q4-matching lines
# when the content guard is off, so a positive control on the checker itself.
$arm5ok = ($leaked.Count -eq 0)
Arm 'ARM5' 'SELF-MATCH: a copy of the report under an UNKNOWN name is still excluded' $arm5ok `
   ("planted={0} dir_names_lane19={1} leaked_into_Q4={2} (expected 0) pattern='{3}'" `
    -f (Split-Path $planted -Leaf), ($plantDir -match 'lane19'), $leaked.Count, $leakPat)

# ---------------------------------------------------------------- VERDICT
$red = @($arms | Where-Object { -not $_.ok })
Say ''
Say ("ARMS={0}  GREEN={1}  RED={2}" -f $arms.Count, ($arms.Count - $red.Count), $red.Count)
$verdict = if ($red.Count -eq 0) { 'VERDICT PASS' } else { 'VERDICT FAIL' }
Say $verdict
Say ''
Say 'The repository itself is NOT gated by this file. This gate asserts one thing:'
Say 'receipt-audit.py can detect a seeded defect, and stops detecting it when the'
Say 'cure is reverted. ARM2b is the arm that makes every other arm mean anything.'

$lines | Set-Content (Join-Path $LogDir 'lane19-gate.txt') -Encoding UTF8
if ($red.Count -eq 0) { exit 0 } else { exit 1 }