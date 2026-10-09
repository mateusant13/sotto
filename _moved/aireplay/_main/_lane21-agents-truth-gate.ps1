# LANE21-AGENTS-TRUTH-GATE -- the mechanical gate for lane 21
# ("this repo's own AGENTS.md must not lie to the next agent").
#
# WHY THIS EXISTS.  AGENTS.md is auto-loaded into the context of EVERY agent that touches this
# repo.  A false sentence in it is not an inconvenience, it is a standing instruction to build the
# wrong thing, and two such sentences had already cost real work by 2026-10-07.  This gate is the
# thing that stops the third one from costing anything.
#
# It checks FOUR things about H:\sotto\_moved\aireplay\AGENTS.md:
#
#   ARM-1  the two KNOWN-FALSE claims are ABSENT
#          1a  the ring budget must not be sized for a 16 GB machine (this box has 47.74 GiB)
#          1b  "no hotkey exists in src/capture" must not be asserted (src/capture/trigger.cpp
#              appeared at 12:12 on 2026-10-07)
#
#   ARM-2  the CORRECTED truths are PRESENT -- absence alone is not a cure, a file can simply
#          delete a claim.  This arm is what stops a gutted AGENTS.md from passing ARM-1.
#
#   ARM-3  EVERY line asserting a measurement carries an ISO date on that SAME line.  A claim
#          without a date rots, and today's largest wastes were all stale claims read as current.
#
#   ARM-4  no measurement line carries a FUTURE date.  Before 2026-10-07 every claim in the file
#          was stamped 2026-10-08 -- one day ahead of the machine -- and a future date can never
#          be detected as stale, because it prices as negative age.  (The correction note that
#          NAMES the bad stamp lives on lines that do not assert a measurement, so it does not
#          trip this arm; see --show-exclusions.)
#
#   ARM-C  THE CONTROL.  A COPY of AGENTS.md with the cure reverted -- the false claims restored
#          and the date stamps stripped -- MUST GO RED.  An instrument that cannot say NO is
#          worthless, and a control that stays green is a failing control.
#
# Prints LANE21-AGENTS-TRUTH-GATE PASS and exits 0 only when every arm behaves as declared.
#
# RULES HONOURED HERE (LANE-BRIEF.md section 4):
#   rule 1  no visible console window: this script only reads text and writes to _main\.  It
#           spawns NOTHING except `pwsh` for nothing at all -- there is no child process, so
#           there is no window to leave.  Run it as
#               pwsh -NoProfile -WindowStyle Hidden -File _main\_lane21-agents-truth-gate.ps1
#           if you are launching it from a console that could reach the owner's desktop.
#   rule 2  the exit code is the script's own, never a pipe's.  Nothing here is piped to
#           Select-Object -First N; every count comes from a full enumeration.
#   rule 3  native H:\ paths only.
#   rule 7  every count carries POPULATION and WINDOW -- each arm prints the line numbers it
#           examined and how many lines the file has.
#
# Usage:  pwsh -File _main\_lane21-agents-truth-gate.ps1
#         pwsh -File _main\_lane21-agents-truth-gate.ps1 -NegArm      # control only
#         pwsh -File _main\_lane21-agents-truth-gate.ps1 -ShowExclusions
param(
    [switch]$NegArm,
    [switch]$ShowExclusions
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Repo    = 'H:\sotto\_moved\aireplay'
$Out     = Join-Path $Repo '_main'
$Target  = Join-Path $Repo 'AGENTS.md'
$Log     = Join-Path $Out 'lane21-agents-truth-gate.log'

# The claims that MUST NOT be asserted, and the truth that MUST be.  Kept as data so ARM-C can
# revert the cure in a COPY without touching the real file.
$FalseClaims = @(
    @{ id = '1a ring budget sized for a 16 GB machine'; needle = '16 GB box' }
    @{ id = '1a (alt form)';                            needle = 'breaks a 16 GB' }
    @{ id = '1b no hotkey in src/capture';               needle = '0 hits for a hotkey' }
    @{ id = '1b (alt form)';                            needle = 'Nao existe hotkey' }
    @{ id = '1b (alt form, accents)';                   needle = 'Não existe hotkey' }
)
$TrueClaims = @(
    @{ id = '2a this host really has 47.74 GiB';  needle = '47.74 GiB' }
    @{ id = '2b the trigger files are named';     needle = 'trigger.cpp' }
    @{ id = '2c the build gap is named';          needle = 'NOT on the' }
    @{ id = '2d receipt-29 is cited';             needle = 'receipt-29' }
)

function Get-GateState {
    param([string]$Path)

    if (-not (Test-Path $Path)) { throw "AGENTS.md missing: $Path" }
    # Read as UTF-8 explicitly.  Get-Content without -Encoding UTF8 re-decodes the em-dashes and
    # the arrows, and a gate that reads a different file than the editor shows is a lie.
    $lines = [IO.File]::ReadAllLines($Path, [Text.Encoding]::UTF8)
    $text  = [IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8)

    $falseHits  = @()
    foreach ($c in $FalseClaims) {
        $n = ([regex]::Matches($text, [regex]::Escape($c.needle))).Count
        if ($n -gt 0) { $falseHits += "$($c.id)  x$n  '$($c.needle)'" }
    }
    $trueMissing = @()
    foreach ($c in $TrueClaims) {
        if ($text.IndexOf($c.needle, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
            $trueMissing += "$($c.id)  '$($c.needle)'"
        }
    }

    # ARM-3: any line asserting a measurement must carry an ISO date ON THAT LINE.
    # A date on the wrapped NEXT line does not count -- this is what the cure had to fix, and a
    # looser rule would have let all three of those through.
    $undated = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '(?i)\bmeasured\b' -and $lines[$i] -notmatch '\d{4}-\d{2}-\d{2}') {
            $undated += "    line {0,4}: {1}" -f ($i + 1), $lines[$i].Trim()
        }
    }

    # ARM-4: a measurement line may not carry a date in the future.  Today is the reference; the
    # point is not "which day" but "no stamp later than the day the file was last edited".
    $future = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -notmatch '(?i)\bmeasured\b') { continue }
        foreach ($m in [regex]::Matches($lines[$i], '\d{4}-\d{2}-\d{2}')) {
            $d = [datetime]::MinValue
            if ([datetime]::TryParseExact($m.Value, 'yyyy-MM-dd', $null, [Globalization.DateTimeStyles]::None, [ref]$d)) {
                if ($d -gt (Get-Date).Date) { $future += "    line {0,4}: {1}" -f ($i + 1), $m.Value }
            }
        }
    }

    [pscustomobject]@{
        Path         = $Path
        LineCount    = $lines.Count
        ByteCount    = $text.Length
        FalseHits    = $falseHits
        TrueMissing  = $trueMissing
        Undated      = $undated
        Future       = $future
    }
}

function Show-State {
    param($S, [string]$Label)
    Write-Output ""
    Write-Output "  [$Label]  $($S.Path)"
    Write-Output "    POPULATION = $($S.LineCount) lines / $($S.ByteCount) B"
    Write-Output "    ARM-1 false claims asserted : $($S.FalseHits.Count)"
    if ($S.FalseHits.Count) { $S.FalseHits   | ForEach-Object { Write-Output "      RED  $_" } }
    Write-Output "    ARM-2 corrected truths missing : $($S.TrueMissing.Count)"
    if ($S.TrueMissing.Count) { $S.TrueMissing | ForEach-Object { Write-Output "      RED  $_" } }
    Write-Output "    ARM-3 undated measurement lines : $($S.Undated.Count)"
    if ($S.Undated.Count) { $S.Undated | ForEach-Object { Write-Output "      RED  $_" } }
    Write-Output "    ARM-4 future-dated measurement lines : $($S.Future.Count)"
    if ($S.Future.Count) { $S.Future | ForEach-Object { Write-Output "      RED  $_" } }
}

if ($ShowExclusions) {
    Write-Output "EXCLUSIONS FROM ARM-3 (printed so they cannot hide):"
    Write-Output "  ARM-3 is LINE-scoped by design: a line containing the word 'measured' must carry"
    Write-Output "  an ISO date on that same line.  There is NO allowlist of exempted lines -- a"
    Write-Output "  blanket exemption is how a 'measured with no date' claim would survive.  Lines"
    Write-Output "  that merely NAME the bad 2026-10-08 stamp (the correction note at the top of the"
    Write-Output "  file) contain no word 'measured', so ARM-3/ARM-4 never see them."
    Write-Output ""
    Write-Output "  ARM-4 exempts nothing either: it only fires on lines that also assert a measurement."
    exit 0
}

Write-Output "LANE21-AGENTS-TRUTH-GATE  repo=$Repo"
Write-Output "  target: $Target"
Write-Output "  control: a COPY with the cure reverted MUST go RED (ARM-C)"

$live = Get-GateState -Path $Target
Show-State -S $live -Label 'LIVE'

if ($NegArm) {
    # The control arm, on the LIVE file, is not a thing this gate can fake: -NegArm runs ARM-C
    # only, and it still builds the reverted copy so you can inspect it.
    Write-Output ""
}

# ------------------------------------------------------------------ ARM-C : the control
# Build a COPY of AGENTS.md with the cure REVERTED and run every arm against it.  It must fail
# all four.  The copy is written to _main\ and is never the real file.
$copy = Join-Path $Out 'lane21-agents-truth-PRE-CURE-COPY.md'
$orig = [IO.File]::ReadAllText($Target, [Text.Encoding]::UTF8)

# Revert 1: put the false claims back, exactly as they read before this lane.
$reverted = $orig
$reverted = $reverted -replace '(?m)^.*CORRECTED 2026-10-07: this line used to size the.*$', ''
$reverted = $reverted -replace '(?m)^.*whole argument against a 16 GB machine.*$', '  breaks a 16 GB box -- consistent with law 7.'
$reverted = $reverted -replace '(?m)^.*there is no\s*$', '   There is no hotkey. 0 hits for a hotkey across src/capture.'
# Revert 2: strip the date stamps so ARM-3 has something to catch.
$reverted = [regex]::Replace($reverted, '(?i)(measured)(\s+(?:on this box\s+)?)(?:in force\s+)?\d{4}-\d{2}-\d{2}', '$1$2')
# Revert 3: re-stamp ONE line with a future date, which is exactly the pre-cure disease (every
#   claim stamped a day ahead of the machine).  This runs AFTER revert 2 on purpose: in the first
#   version of this gate the two ran in the other order, the strip consumed the stamp, ARM-4 saw
#   nothing, and the gate reported "THE CONTROL IS WORTHLESS" about its own control.  A control
#   arm that cannot detect the disease is not a control.
$reverted = $reverted -replace '(?i)(INITIALISED[^\r\n]*?measured)\s*\.', '$1 2026-10-08.'
# Revert 4: gut the corrected truths so ARM-2 has something to catch.
$reverted = $reverted -replace '47\.74 GiB', '16 GB'
$reverted = $reverted -replace 'trigger\.cpp', 'no-trigger'
$reverted = $reverted -replace 'NOT on the', 'deliberately absent from'
$reverted = $reverted -replace 'receipt-29', 'no-receipt'

[IO.File]::WriteAllText($copy, $reverted, (New-Object Text.UTF8Encoding($false)))
$ctrl = Get-GateState -Path $copy
Show-State -S $ctrl -Label 'ARM-C CONTROL (cure reverted in a COPY)'

# ARM-C is only a pass when the control REDS on every arm it is supposed to redden.
$armC_ok = ($ctrl.FalseHits.Count -ge 2) -and
           ($ctrl.TrueMissing.Count -ge 2) -and
           ($ctrl.Undated.Count   -ge 1) -and
           ($ctrl.Future.Count    -ge 1)

Write-Output ""
Write-Output "  ARM-C expected: false-claims>=2 ($($ctrl.FalseHits.Count)), truths-missing>=2 ($($ctrl.TrueMissing.Count)), undated>=1 ($($ctrl.Undated.Count)), future-dated>=1 ($($ctrl.Future.Count))"
Write-Output "  ARM-C verdict: $(if ($armC_ok) { 'RED as expected -- the control CAN say NO' } else { 'DID NOT GO RED -- THE CONTROL IS WORTHLESS' })"

$live_ok = ($live.FalseHits.Count   -eq 0) -and
           ($live.TrueMissing.Count -eq 0) -and
           ($live.Undated.Count     -eq 0) -and
           ($live.Future.Count      -eq 0)

Write-Output ""
Write-Output "  ARM-1..4 verdict on the LIVE file: $(if ($live_ok) { 'GREEN' } else { 'RED' })"
Write-Output "  copy written: $copy"

Add-Content -Path $Log -Encoding UTF8 -Value (
    "LANE21-AGENTS-TRUTH-GATE rc=$(if ($live_ok -and $armC_ok) { 0 } else { 1 }) " +
    "live=[false=$($live.FalseHits.Count) missing=$($live.TrueMissing.Count) undated=$($live.Undated.Count) future=$($live.Future.Count)] " +
    "control=[false=$($ctrl.FalseHits.Count) missing=$($ctrl.TrueMissing.Count) undated=$($ctrl.Undated.Count) future=$($ctrl.Future.Count)] " +
    "$(Get-Date -Format s)")

if ($NegArm) {
    if ($armC_ok) { Write-Output "LANE21-AGENTS-TRUTH-GATE CONTROL-ONLY PASS"; exit 0 }
    Write-Output "LANE21-AGENTS-TRUTH-GATE FAIL (the control did not go red -- the gate cannot be trusted)"
    exit 1
}

if ($live_ok -and $armC_ok) {
    Write-Output "LANE21-AGENTS-TRUTH-GATE PASS"
    exit 0
}
Write-Output "LANE21-AGENTS-TRUTH-GATE FAIL"
exit 1
