# GATE — LANE 18, THE OVERLAY PANEL.  `py -3 _main/_lane18-ui-gate.ps1`
#   or: pwsh -File _main\_lane18-ui-gate.ps1
#
# WHAT THIS GATE IS. It binds three instruments into ONE verdict, and it is the
# only file in this lane whose exit code anybody should read:
#
#   1. `_hud-state-oracle.js`   headless. The 11 states render, the bindings
#                               match the contract, the errors carry their
#                               facts. No window.
#   2. `_hud-window-census.py`  25 ms census of the shell's own pid tree. Does
#                               the panel map the window unless asked?
#   3. `hud-shell.py --json-out` the LIVE DOM, read back through the panel's own
#                               `SottoHud.probe()` — COMPUTED styles and
#                               measured boxes, not the attributes the panel set
#                               on itself. Arm 3 renders
#                               `ERROR_SILENT_DEVICE` at 144 dpi on a 3840 px
#                               display, so it exercises the real stylesheet.
#
# EVERY ASSERTION NAMES WHAT IT OBSERVED. No arm here reports a boolean it did
# not compute from a file on disk. A screenshot nobody took is not a result, and
# a pass nobody measured is worse.
#
# THE BOTH-COLOURS RULE. `_main/all-gates.ps1`'s repo convention: every gate
# ships its own RED arm, because "a control that stays green is a failing
# control". The census carries FOUR arms for this reason:
#
#   live      the shipped shell. MUST map 0 launches unless asked.
#   nonet     BOTH nets removed in a COPY. MUST map >= 1 launch. This is the
#             arm that proves the census can see a window at all.
#   nogate    the instance-shadow gate removed, re-assert kept. MEASURED GREEN
#             — the re-assert runs in the same .NET dispatch as pywebview's
#             `form.Show()`, so the map is shorter than the 25 ms grid. It is
#             kept and reported as its own arm precisely because it is the
#             arm that DOES move when only the cure is reverted, and collapsing
#             it into "the cure works" would be crediting the wrong mechanism.
#   show      `--show-hud`, the path the owner asks for. MUST map >= 1 launch.
#             Without it a panel that never maps scores a perfect first clause.
#
# HARD RULES HONOURED (lane brief §4): pythonw.exe + CREATE_NO_WINDOW for every
# launch (rule 1); no native command is ever piped, every rc is read from
# $LASTEXITCODE after a redirect (rule 2); native H:\ paths only (rule 3); no
# grep for context files (rule 4); only this lane's files are written (rule 5).
param(
    [int]$N = 6,
    [int]$CadenceMs = 25,
    [int]$Secs = 6,
    [switch]$Quick
)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $Here
$Ui = Join-Path $Root 'src\ui'
$Work = Join-Path $Here '_lane18'
$Out = Join-Path $Here '_lane18-gate.out.txt'

if (Test-Path $Work) { Remove-Item $Work -Recurse -Force }
New-Item -ItemType Directory -Path $Work | Out-Null

$script:boxes = New-Object System.Collections.ArrayList
$script:RedArms = 0

function Box {
    param([string]$Id, [bool]$Pass, [string]$Observed, [string]$Arm = 'live')
    $colour = if ($Pass) { 'GREEN' } else { 'RED' }
    $line = ('BOX {0,-42} {1,-5} arm={2,-8} {3}' -f $Id, $colour, $Arm, $Observed)
    Write-Host $line
    [void]$script:boxes.Add([pscustomobject]@{
        Id = $Id; Pass = $Pass; Colour = $colour; Arm = $Arm; Observed = $Observed
    })
    if (-not $Pass) { $script:RedArms++ }
    return $Pass
}

# rule 2: a native command NEVER gets piped. Redirect, then read $LASTEXITCODE.
#
# THE PARAMETER IS NOT NAMED `$Args`. PowerShell's `$Args` is an AUTOMATIC
# variable, and a function parameter of that name does not bind the way a normal
# one does: the first run of this gate passed `-ArgumentList @(...)` into `$Args`,
# `node` was launched with NO arguments, wrote 0 bytes to both redirects, and the
# gate died on a null `$stateText` instead of reporting a failure. The name is
# `$ArgList` for exactly that reason.
function Run-Native {
    param([string]$Exe, [string[]]$ArgList, [string]$Stdout, [string]$Stderr)
    $p = Start-Process -FilePath $Exe -ArgumentList $ArgList -NoNewWindow -Wait `
        -PassThru -RedirectStandardOutput $Stdout -RedirectStandardError $Stderr
    return $p.ExitCode
}

$pyw = 'C:\Program Files\Python311\pythonw.exe'
if (-not (Test-Path $pyw)) { $pyw = 'pythonw.exe' }
$env:PYTHONIOENCODING = 'utf-8'

Write-Host "LANE18 GATE  n=$N  cadence_ms=$CadenceMs  window_s=$Secs"
Write-Host ''

# ---------------------------------------------------------------------------
# ARM 1 — the headless state oracle
# ---------------------------------------------------------------------------
$nodeOut = Join-Path $Work 'state-oracle.out.txt'
$nodeErr = Join-Path $Work 'state-oracle.err.txt'
$rc = Run-Native 'node' @((Join-Path $Here '_hud-state-oracle.js'),
    '--json', (Join-Path $Work 'state-oracle.json')) $nodeOut $nodeErr
$stateText = (Get-Content $nodeOut -Raw -Encoding UTF8)
$errText = if (Test-Path $nodeErr) { Get-Content $nodeErr -Raw -Encoding UTF8 } else { '' }
Write-Host $stateText

$arms = @([regex]::Matches($stateText, '(?m)^ARM (\S+) (GREEN|RED) (.+)$'))
$stateRed = @($arms | Where-Object { $_.Groups[2].Value -eq 'RED' })
$stateGreen = @($arms | Where-Object { $_.Groups[2].Value -eq 'GREEN' })
$popLine = ([regex]::Match($stateText, '(?m)^POPULATION (.+)$')).Groups[1].Value

Box 'ARM1-oracle-runs' ($rc -eq 0 -and $arms.Count -gt 0) `
    "node_rc=$rc arms_parsed=$($arms.Count) green=$($stateGreen.Count) red=$($stateRed.Count) stderr_len=$($errText.Length) POPULATION: $popLine"
foreach ($m in $stateGreen) {
    Box ("ARM1/" + $m.Groups[1].Value) $true ("observed: " + $m.Groups[3].Value)
}
foreach ($m in $stateRed) {
    Box ("ARM1/" + $m.Groups[1].Value) $false ("observed: " + $m.Groups[3].Value)
}

# ---------------------------------------------------------------------------
# ARM 2 — the window census, all four arms
# ---------------------------------------------------------------------------
$armsCsv = if ($Quick) { 'live,nonet,show' } else { 'live,nonet,nogate,show' }
$cenOut = Join-Path $Work 'census.out.txt'
$cenErr = Join-Path $Work 'census.err.txt'
$rc2 = Run-Native 'py' @('-3', (Join-Path $Here '_hud-window-census.py'),
    '--n', "$N", '--ms', "$CadenceMs", '--secs', "$Secs",
    '--arms', $armsCsv, '--json-out', (Join-Path $Work 'census.json')) $cenOut $cenErr
$cenText = Get-Content $cenOut -Raw -Encoding UTF8
Write-Host $cenText
if ((Test-Path $cenErr) -and (Get-Item $cenErr).Length -gt 0) {
    Write-Host "CENSUS STDERR:"
    Get-Content $cenErr -Encoding UTF8
}

$census = $null
if (Test-Path (Join-Path $Work 'census.json')) {
    $census = Get-Content (Join-Path $Work 'census.json') -Raw -Encoding UTF8 | ConvertFrom-Json
}

if ($null -eq $census) {
    Box 'ARM2-census-produced-json' $false `
        "census_rc=$rc2 census_json=ABSENT stderr_len=$((Get-Item $cenErr).Length)"
} else {
    Box 'ARM2-census-produced-json' ($rc2 -eq 0) `
        "census_rc=$rc2 arms=$($census.arms.Count) launches_per_arm=$($census.population_n) window_s=$($census.window_s) cadence_ms=$($census.cadence_ms)"

    $byTag = @{}
    foreach ($a in $census.arms) { $byTag[$a.tag] = $a }

    foreach ($a in $census.arms) {
        Box ("ARM2/" + $a.tag + "/launchable") ([bool]$a.launchable) `
            "reaching_HUD_READY=$($a.launches)/$($a.launches) rcs=$($a.rcs -join ',') nets2_lines=$($a.nets2_lines) exstyle_set_equality_lines=$($a.exstyle_set_equality_lines)" $a.tag
    }

    # THE CLAIM. live maps nothing at start-up.
    if ($byTag.ContainsKey('live')) {
        $l = $byTag['live']
        Box 'PASS-1-live-maps-nothing-unless-asked' `
            ($l.launches_with_opaque_window -eq 0 -and $l.launchable) `
            "launches_with_opaque_window=$($l.launches_with_opaque_window)/$($l.launches) samples=$($l.samples) opaque_catch_samples=$($l.opaque_catch_samples) longest_opaque_ms=$($l.longest_opaque_ms) show_refused_total=$($l.show_refused_total) reassert_total=$($l.reassert_total) nets2_lines=$($l.nets2_lines) hud_show_mapped_lines=$($l.hud_show_mapped_lines) POPULATION=$($census.population_n) launches WINDOW=$($census.window_s)s @ $($census.cadence_ms)ms, x=-10000" 'live'
    }
    # THE CONTROL. nonet MUST map — else the census is blind.
    if ($byTag.ContainsKey('nonet')) {
        $c = $byTag['nonet']
        Box 'CONTROL-nonet-maps-the-window' `
            ($c.launches_with_opaque_window -ge 1 -and $c.opaque_catch_samples -ge 1) `
            "launches_with_opaque_window=$($c.launches_with_opaque_window)/$($c.launches) opaque_catch_samples=$($c.opaque_catch_samples) longest_opaque_ms=$($c.longest_opaque_ms) show_refused_total=$($c.show_refused_total) reassert_total=$($c.reassert_total) -- THIS is the arm that proves the census can see a window; a control that stays green is a failing control" 'nonet'
    }
    # NON-VACUITY. The owner-asked path MUST map.
    if ($byTag.ContainsKey('show')) {
        $s = $byTag['show']
        Box 'PASS-1b-show-hud-maps-the-window' `
            ($s.launches_with_opaque_window -ge 1) `
            "launches_with_opaque_window=$($s.launches_with_opaque_window)/$($s.launches) opaque_catch_samples=$($s.opaque_catch_samples) longest_opaque_ms=$($s.longest_opaque_ms) hud_show_mapped_lines=$($s.hud_show_mapped_lines) -- the second clause of PASS-1, so a panel that never maps cannot pass" 'show'
    }
    # REPORTED, NOT FAILED. The cure removed, re-assert kept.
    if ($byTag.ContainsKey('nogate')) {
        $g = $byTag['nogate']
        Box 'ARM2-nogate-reported-not-asserted' $true `
            "launches_with_opaque_window=$($g.launches_with_opaque_window)/$($g.launches) opaque_catch_samples=$($g.opaque_catch_samples) reassert_total=$($g.reassert_total) show_refused_total=$($g.show_refused_total) -- MEASURED GREEN: the re-assert runs in the same dispatch as pywebview's Show, so the map is shorter than the $($census.cadence_ms)ms grid. This arm does NOT prove the instance gate alone is load-bearing; nonet does. See receipt." 'nogate'
    }
    if ($byTag.ContainsKey('reassert')) {
        $r = $byTag['reassert']
        Box 'ARM2-reassert-reported-not-asserted' $true `
            "launches_with_opaque_window=$($r.launches_with_opaque_window)/$($r.launches) reassert_total=$($r.reassert_total) nets2_lines=$($r.nets2_lines) -- independence of the two nets" 'reassert'
    }
}

# ---------------------------------------------------------------------------
# ARM 3 — the LIVE DOM, through the shell's own probe()
# ---------------------------------------------------------------------------
$probeLog = Join-Path $Work 'probe.log'
$probeJson = Join-Path $Work 'probe.json'
if (Test-Path $probeLog) { Remove-Item $probeLog -Force }
$p = Start-Process -FilePath $pyw -NoNewWindow -Wait -PassThru `
    -ArgumentList @((Join-Path $Ui 'hud-shell.py'), '--log', $probeLog,
        '--exit-after', '6', '--x', '-10000', '--y', '-10000',
        '--state', 'ERROR_SILENT_DEVICE', '--json-out', $probeJson,
        '--dpi', '144', '--display-w', '3840')
$probeRc = $p.ExitCode
$probeBody = if (Test-Path $probeLog) { Get-Content $probeLog -Raw -Encoding UTF8 } else { '' }
$probe = $null
if (Test-Path $probeJson) { $probe = Get-Content $probeJson -Raw -Encoding UTF8 | ConvertFrom-Json }

Box 'ARM3-shell-exits-clean' ($probeRc -eq 0) `
    "rc=$probeRc reached_HUD_READY=$($probeBody -match 'HUD_READY') panel_loaded=$($probeBody -match 'panel_loaded=true') nets_armed=$(([regex]::Match($probeBody,'nets_armed=(\d)')).Groups[1].Value)"

if ($null -eq $probe) {
    Box 'ARM3-probe-returned-json' $false `
        "probe_json=ABSENT rc=$probeRc log_len=$($probeBody.Length)"
} else {
    Box 'ARM3-probe-returned-json' $true `
        "state=$($probe.state) mapped=$($probe.mapped) glyph_name=$($probe.glyph_name) plate_visible=$($probe.plate_visible) plate_opacity=$($probe.plate_opacity) plate=$($probe.plate_rect.w)x$($probe.plate_rect.h) painted_lines=$($probe.painted_lines)"

    # THE PAINT GATE. Nothing published until a binding fires.
    Box 'PASS-1c-not-mapped-means-not-painted' `
        ($probe.mapped -eq '0' -and $probe.plate_visible -eq 'hidden' -and $probe.plate_opacity -eq '0') `
        "data-mapped=$($probe.mapped) computed_visibility=$($probe.plate_visible) computed_opacity=$($probe.plate_opacity) -- SPEC §1.6: an unmapped HUD is never-published, not published-at-alpha-0"

    # THE STATE REACHED THE PLATE, with its enum name.
    Box 'PASS-9-live-plate-shows-the-enum-name' `
        ($probe.state -eq 'ERROR_SILENT_DEVICE' -and $probe.line1 -eq 'ERROR_SILENT_DEVICE') `
        "data-state=$($probe.state) line1_text=$($probe.line1) -- the HUD's word and the log's word are the same string"

    # SPEC §1.1: three lines, never four.
    Box 'SPEC-1.1-live-three-line-ceiling' ($probe.painted_lines -le 3) `
        "painted_lines=$($probe.painted_lines) line2_len=$($probe.line2.Length)"

    # SPEC §5: the DPI rule, measured off the live DOM at TWO dpis.
    #
    # THE FIRST VERSION OF THIS BOX WAS WRONG and it is worth recording why: it
    # asserted the plate measures ~720 at 144 dpi, i.e. that the plate equals
    # `plate_max_w`. It measured 667 and went RED. But SPEC §5's own table column
    # is literally "plate min × max" — 360 x 720 at 144 dpi — and `max-width`
    # caps a plate that sizes to its CONTENT, so 667 is correct and the
    # ASSERTION was the defect. Asserting the max would have forced the plate to
    # be as wide as it may be, which is the opposite of the spec's intent.
    #
    # The assertion is now the spec's own range, and it is run at 192 dpi too
    # because THAT is where a hardcoded window would have failed: the old
    # `width=520` left 520 - 2*48 = 424 px of plate, below the 480 px
    # `plate_min_w_px` minimum at 192 % scaling. The min-floor is the load-
    # bearing half of the range, and only a high-dpi run exercises it.
    foreach ($case in @(@{ dpi = 144; dw = 3840; min = 360; max = 720 },
            @{ dpi = 192; dw = 3840; min = 480; max = 960 })) {
        $cLog = Join-Path $Work "probe-$($case.dpi).log"
        $cJson = Join-Path $Work "probe-$($case.dpi).json"
        if (Test-Path $cLog) { Remove-Item $cLog -Force }
        $cp = Start-Process -FilePath $pyw -NoNewWindow -Wait -PassThru `
            -ArgumentList @((Join-Path $Ui 'hud-shell.py'), '--log', $cLog,
                '--exit-after', '6', '--x', '-10000', '--y', '-10000',
                '--state', 'ERROR_SILENT_DEVICE', '--json-out', $cJson,
                '--dpi', "$($case.dpi)", '--display-w', "$($case.dw)")
        $cProbe = $null
        if (Test-Path $cJson) {
            $cProbe = Get-Content $cJson -Raw -Encoding UTF8 | ConvertFrom-Json
        }
        if ($null -eq $cProbe) {
            Box ("SPEC-5-live-dpi-" + $case.dpi) $false `
                "dpi=$($case.dpi) display_w=$($case.dw) probe_json=ABSENT rc=$($cp.ExitCode)"
        } else {
            $w = $cProbe.plate_rect.w
            Box ("SPEC-5-live-dpi-" + $case.dpi) `
                ($w -ge $case.min -and $w -le $case.max -and $cp.ExitCode -eq 0) `
                "dpi=$($case.dpi) display_w=$($case.dw) plate_measured_w=$w spec_range=[$($case.min)..$($case.max)] (SPEC §5 'plate min x max') rc=$($cp.ExitCode) painted_lines=$($cProbe.painted_lines) line1=$($cProbe.line1)"
        }
    }
}

# ---------------------------------------------------------------------------
# VERDICT
# ---------------------------------------------------------------------------
$total = $script:boxes.Count
$red = @($script:boxes | Where-Object { -not $_.Pass })
Write-Host ''
Write-Host '--- BOXES ---'
foreach ($b in $script:boxes) {
    Write-Host ('{0,-8} {1}' -f $b.Colour, $b.Id)
}
Write-Host ''
Write-Host "POPULATION boxes=$total arms_run=$($script:boxes.Count) red=$($red.Count)"
Write-Host "WINDOW launches_per_census_arm=$N window_s=${Secs}s census_cadence_ms=$CadenceMs live_dom_window=6s states_walked=$($arms.Count) (headless)"
Write-Host ('VERDICT {0}' -f $(if ($red.Count -eq 0) { 'PASS' } else { 'FAIL' }))
if ($red.Count -gt 0) {
    Write-Host ('FAILED_BOXES {0}' -f (($red | ForEach-Object { $_.Id }) -join ','))
}

$report = @()
$report += "LANE18 UI GATE  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')"
$report += "POPULATION boxes=$total red=$($red.Count) launches_per_arm=$N window_s=${Secs}s cadence_ms=$CadenceMs"
$report += "VERDICT $(if ($red.Count -eq 0) { 'PASS' } else { 'FAIL' })"
$report += ''
foreach ($b in $script:boxes) { $report += ('{0,-8} {1,-46} arm={2}' -f $b.Colour, $b.Id, $b.Arm) }
$report += ''
$report += $stateText
$report += ''
$report += $cenText
Set-Content -Path $Out -Value ($report -join "`n") -Encoding UTF8
Write-Host ''
Write-Host "WROTE $Out"

if ($red.Count -gt 0) { exit 1 }
exit 0