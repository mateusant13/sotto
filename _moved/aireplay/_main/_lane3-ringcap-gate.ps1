# _lane3-ringcap-gate.ps1 — LANE 3 GATE: the ring cap is priced against the wrong resource.
#
# THE DEFECT: src/capture/d3d11_ctx.cpp:66-75 derives the ring budget from DXGI
# DedicatedVideoMemory (`cap = vram/16, clamp 256 MiB..2048 MiB`), but the arena it bounds is
# a std::vector<uint8_t> in SYSTEM RAM (ring_buffer.cpp init()).  The budget prices bytes
# from a pool the ring never draws from.
#
# THE FIX (ring_buffer.h + ring_buffer.cpp + the one call site, replay.cpp:130):
#   cap = min(4 GiB, 25% of TotalPhysicalMemory, 50% of AvailPhysicalMemory), floored at
#   256 MiB, MiB-aligned down, queryable at runtime (query_ring_budget) and LOGGED by init().
#   TOTAL carries the proportional rule; AVAILABILITY carries the guard, because availability
#   is what actually decides whether the commit succeeds (reviewer's F2).
#
# ARMS:
#   A  NEW policy, MEASURED by compiling ring_buffer.cpp and calling it, and recomputed here
#      INDEPENDENTLY in PowerShell (including the availability term).
#   B  OLD policy, MEASURED — and PARSED OUT OF THE SHIPPED SOURCE rather than re-implemented
#      in the probe.  Before: the probe carried its own copy of d3d11_ctx.cpp:70's formula, so
#      an edit to that line left this arm green forever.  Now the divisor and both clamps are
#      read from d3d11_ctx.cpp itself.
#   C  DERIVED seconds-of-ring at 1080p60 and 4K60 under both caps.  ARITHMETIC, not
#      measurement.  REASON FOR THE ABSENCE OF A 4K RUN (corrected 2026-10-07): this host's
#      ONLY monitor is 1920x1080 and WGC refuses every capture item with E_ACCESSDENIED
#      (receipt-18 §2), so no capture above 1080p can exist here.  It is NOT because a literal
#      1920x1080 clamp pins the window: lane 7 lifted that at 12:26 and replay.cpp:38-42
#      documents the lift (negotiate_capture_window).
#   D  CONTROL.  The PRE-CHANGE ring_buffer.{h,cpp}, restored in a COPY, must FAIL to link
#      against a caller of the budget API — that failure is the proof the old ring had no
#      system-RAM budget.  Same file, same compiler, opposite result: a gate that passes both
#      sides would prove nothing.
#   E  LIVE PATH: what the OLD cap would have given vs what the RAM budget gives, plus the
#      source-level state of the hookup (which side of the line the tree is on).
#   F  SYNTHETIC MACHINES.  ring_budget_from() is pure, so the terms that CANNOT bind on this
#      host are tested on machines that are not this one: 64/16/8/2/1 GiB, 512 MiB, a
#      low-availability 47 GiB, and a failed query.  On 47.74 GiB of RAM, min(4 GiB, 25%) is
#      4 GiB for any f >= 8.38%, so ARM A can only ever see the ceiling — without this arm
#      two of the three policy terms are untested code.
#   G  SOURCE-LEVEL REGRESSIONS: replay.cpp must read the RAM budget and not the VRAM cap, the
#      CHOSE log must print the committed size, the discarded seconds must be gone, and the
#      arena allocation must be inside a catch.
#
# POPULATION / FLAKINESS: every PASS in this gate is N=1 — one compile, one execution, on one
# host, at one moment.  NO FLAKINESS CLAIM IS MADE FOR ANY ARM, INCLUDING THE ONES THAT HAVE
# BEEN GREEN REPEATEDLY.  Two arms carry a live race against the machine's free memory (the
# availability term) and they handle it by REFUSING with exit 2 and a stated reason rather
# than by reporting a phantom defect; see ARM A.
#
# Exit: 0 only when all arms behave. Non-zero = the GATE is broken, not the tree.
#
# House rules honoured: no piped native command (every call is `> file 2>&1` then
# $LASTEXITCODE), native H:\ paths only, no visible console window.

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'

$Prod     = 'H:\sotto\_moved\aireplay'
$Src      = Join-Path $Prod 'src\capture'
$Main     = Join-Path $Prod '_main'
$Logs     = Join-Path $Main 'logs'
$Build    = Join-Path $Main 'build'
$Ctl      = Join-Path $Main '_lane3-ringcap-control'
$GXX      = 'H:\msys64\mingw64\bin\g++.exe'
$Libs     = @('-ld3d11','-ldxgi','-luuid','-lole32','-loleaut32','-lruntimeobject',
              '-lwindowsapp','-lpsapi','-lgdi32','-luser32')

foreach ($d in @($Logs, $Build, $Ctl)) { if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null } }

# ---------------------------------------------------------------- helpers
function Invoke-Native {
    # Rule 2: never pipe a native command for its exit code.  Redirect to a file, then read
    # $LASTEXITCODE.  A closed pipe hides the real status.
    param([string]$Exe, [string[]]$Argv, [string]$LogName)
    $log = Join-Path $Logs $LogName
    & $Exe @Argv > $log 2>&1
    $rc = $LASTEXITCODE
    return [ordered]@{ rc = $rc; log = $log; out = (Get-Content -LiteralPath $log -Raw -ErrorAction SilentlyContinue) }
}

function Get-ProbeField {
    # Matches "<key>=<number>" ANYWHERE on a line, as the LAST token or followed by a space.
    # It must NOT require a literal "PROBE " prefix: the probe prints several key=value pairs
    # per line and only the first is prefixed.  Anchoring on the prefix silently returned $null
    # for every other field — the first run of this gate proved that by failing for a reason
    # that had nothing to do with the ring.  Exactly ONE capture group, so $Matches[1] is the
    # number; a second group would have made this return null again, silently.
    param([string]$Text, [string]$Key)
    $re = '(?:^|\s)' + [regex]::Escape($Key) + '=(-?[0-9.]+)(?:\s|$)'
    foreach ($line in ($Text -split "`r?`n")) {
        if ($line -match $re) { return $Matches[1] }
    }
    return $null
}

function Get-IntField {
    param($Row, [string]$Key)
    if ($null -eq $Row) { return $null }
    if (-not $Row.Contains($Key)) { return $null }
    return [int]$Row[$Key]
}

$arms = [ordered]@{}
$notes = New-Object System.Collections.Generic.List[string]

# ---------------------------------------------------------------- arm A + B + C: the probe
# One instrument answers all three: it compiles the CURRENT ring_buffer.cpp and prints both
# policies, so OLD and NEW come from one machine, one moment, one binary.
if (-not (Test-Path -LiteralPath $GXX)) {
    Write-Output "LANE3-GATE FAIL: g++ not found at $GXX (the gate cannot measure anything)"
    exit 2
}

$probeExe = Join-Path $Build 'lane3-ringcap-probe.exe'
$probeArgv = @(
    '-std=c++17','-O2','-Wall','-Wextra','-Wno-unused-parameter','-I',$Src,
    (Join-Path $Main '_lane3_ringcap_probe.cpp'),
    (Join-Path $Src 'ring_buffer.cpp'), (Join-Path $Src 'common.cpp'),
    '-o', $probeExe
) + $Libs
$b = Invoke-Native -Exe $GXX -LogName 'lane3-gate-probe-build.log' -Argv $probeArgv

if ($b.rc -ne 0) {
    Write-Output "LANE3-GATE FAIL: probe build rc=$($b.rc) — see $($b.log)"
    exit 2
}
$r = Invoke-Native -Exe $probeExe -LogName 'lane3-gate-probe-run.log' -Argv @()
$probeText = [string]$r.out
$notes.Add("probe built and run rc=$($r.rc); log=$($r.log)")

$totalPhys  = Get-ProbeField $probeText 'total_physical_bytes'
$totalMiB   = Get-ProbeField $probeText 'total_physical_mib'
$queryOk    = Get-ProbeField $probeText 'query_ok'
$quarterMiB = Get-ProbeField $probeText 'quarter_mib'
$ceilingB   = Get-ProbeField $probeText 'ceiling_binds'
$floorAp    = Get-ProbeField $probeText 'floor_applied'
$vramMiB    = Get-ProbeField $probeText 'dedicated_vram_mib'
$vramBytes  = Get-ProbeField $probeText 'dedicated_vram_bytes'
$oldCap     = Get-ProbeField $probeText 'old_cap_mib'
$newCap     = Get-ProbeField $probeText 'new_cap_mib'
$oldPct     = Get-ProbeField $probeText 'old_pct_of_ram'
$newPct     = Get-ProbeField $probeText 'new_pct_of_ram'
$clampUnder = Get-ProbeField $probeText 'clamp_probe_under'
$clampOver  = Get-ProbeField $probeText 'clamp_probe_over'

# A field the parser could not read is NOT a value.  Without this guard a $null compares as
# "0" or "not equal" and the gate reports a defect that is actually a blind spot.
$required = [ordered]@{
    total_physical_bytes=$totalPhys; total_physical_mib=$totalMiB; query_ok=$queryOk
    quarter_mib=$quarterMiB; ceiling_binds=$ceilingB; floor_applied=$floorAp
    dedicated_vram_mib=$vramMiB; dedicated_vram_bytes=$vramBytes; old_cap_mib=$oldCap; new_cap_mib=$newCap
    old_pct_of_ram=$oldPct; new_pct_of_ram=$newPct
    clamp_probe_under=$clampUnder; clamp_probe_over=$clampOver
}
$unparsed = @($required.Keys | Where-Object { $null -eq $required[$_] })
if ($unparsed.Count -gt 0) {
    Write-Output '=========================================================================='
    Write-Output ' LANE 3 GATE - ring cap: VRAM-priced vs system-RAM-priced'
    Write-Output '=========================================================================='
    Write-Output ("LANE3-GATE FAIL: the probe output did not carry these fields: {0}" -f ($unparsed -join ', '))
    Write-Output ("  raw probe output follows; the PARSER is what is broken, not the ring:")
    Write-Output $probeText
    exit 2
}

# --- ARM A: the new policy is what the code computes on THIS machine --------------------
# Expected cap recomputed HERE, independently of the C++, from an INDEPENDENT read of RAM
# (Win32_ComputerSystem.TotalPhysicalMemory) and of AVAILABILITY (Win32_OperatingSystem.
# FreePhysicalMemory, KiB).  Three terms: 4 GiB ceiling, 25% of total, 50% of available,
# then the 256 MiB floor.
$cimRam = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
$cimOs  = Get-CimInstance Win32_OperatingSystem
$availBytes = [uint64]$cimOs.FreePhysicalMemory * 1024      # CIM reports KiB
# Integers, not :N0/:N2.  This host's locale renders the GROUP separator as "." — "48.888 MiB"
# then reads as forty-eight point eight, which is the same class of wrong number the reviewer's
# F1 was about.  Plain integers are unambiguous in any locale.
$cimRamMiB   = [int64][math]::Floor($cimRam / 1MB)
$cimRamGiB   = [double]$cimRam / 1GB
$availMiB    = [int64][math]::Floor($availBytes / 1MB)
$availGiB    = [double]$availBytes / 1GB
$notes.Add(("independent availability read: {0} MiB free (CIM) vs the probe's own read at its own moment" -f $availMiB))

$expQuarter = [math]::Floor(($cimRam / 4) / 1MB) * 1MB
$expHalfAvail = [math]::Floor(($availBytes / 2) / 1MB) * 1MB
$expCap = $expQuarter
$expCeilingBinds = 0
$expAvailBinds   = 0
if ($expCap -gt 4GB) { $expCap = 4GB; $expCeilingBinds = 1 }
if ($expHalfAvail -lt $expCap) { $expCap = $expHalfAvail; $expAvailBinds = 1 }
$expFloorAp = 0
if ($expCap -lt 256MB) { $expCap = 256MB; $expFloorAp = 1 }

# RACE GUARD, stated as a precondition rather than tolerated as noise.  The probe reads
# availability at ITS moment and the recompute above reads it at OURS; between them the owner
# can start something.  If the guard fails, the two numbers are not comparable and reporting a
# FAIL would be a phantom defect — so the gate refuses with exit 2 and says why.  On 47.74 GiB
# of RAM the term needs >= 8 GiB free; measured free is ~24 GiB (POPULATION: several reads).
if ($expHalfAvail -lt 4GB) {
    Write-Output '=========================================================================='
    Write-Output ' LANE 3 GATE - ring cap: VRAM-priced vs system-RAM-priced'
    Write-Output '=========================================================================='
    Write-Output ("LANE3-GATE REFUSED: only {0} MiB of RAM is free, so the 50%-of-available term can bind and the probe's reading" -f $availMiB)
    Write-Output ("  and this independent recompute are no longer comparable.  Free at least 8 GiB and re-run.  (The ring is not implicated.)")
    exit 2
}

$aChecks = [ordered]@{}
$aChecks['probe_reported_a_budget']    = ($newCap -ne $null)
$aChecks['ram_query_succeeded']        = ($queryOk -eq '1')
# UNITS: the probe prints MiB; the independent recompute below is in BYTES.  Compare like
# with like, in bytes.
$aChecks['matches_independent_recompute'] = ([double]$newCap * 1MB -eq [double]$expCap)
$aChecks['ceiling_flag_agrees']        = ([int]$ceilingB -eq $expCeilingBinds)
$aChecks['floor_flag_agrees']          = ([int]$floorAp -eq $expFloorAp)
$aChecks['cap_is_nontrivial']          = ([double]$newCap -ge 256)   # MiB
$aChecks['availability_term_free_on_this_host'] = ($expAvailBinds -eq 0)
# the clamp: under the cap untouched, over the cap clamped to it
$aChecks['clamp_leaves_small_request'] = ([double]$clampUnder -eq 512MB)
$aChecks['clamp_caps_huge_request']    = ([double]$clampOver -eq [double]$newCap * 1MB)
$arms['A'] = [ordered]@{ status = 'GREEN'; what = 'NEW cap measured from the compiled ring_buffer.cpp (ceiling + 25% of total + 50% of available, floored)'; checks = $aChecks }

# --- ARM B: the OLD cap, parsed OUT OF THE SHIPPED SOURCE, and matched to the run log -----
# FINDING CLOSED (2026-10-07): the probe used to carry its OWN copy of the old formula.  An
# edit to d3d11_ctx.cpp:70 therefore left this arm green forever — it measured the probe, not
# the code.  The divisor and both clamps are now READ from d3d11_ctx.cpp and the expected cap
# is recomputed from the PARSED values, so changing that line turns this arm RED.
$d3dPath = Join-Path $Src 'd3d11_ctx.cpp'
$d3dText = Get-Content -LiteralPath $d3dPath -Raw
$d3dFn   = [regex]::Match($d3dText, 'uint64_t\s+D3d11Context::ring_cap_bytes\(\)\s*const(?<body>[\s\S]*?\n\})')
$divRe   = [regex]::Match($(if ($d3dFn.Success) { $d3dFn.Groups['body'].Value } else { '' }), 'dedicated_vram\s*/\s*(\d+)')
$loRe    = [regex]::Match($(if ($d3dFn.Success) { $d3dFn.Groups['body'].Value } else { '' }), 'lo\s*=\s*(\d+)ull\s*<<\s*20')
$hiRe    = [regex]::Match($(if ($d3dFn.Success) { $d3dFn.Groups['body'].Value } else { '' }), 'hi\s*=\s*(\d+)ull\s*<<\s*20')

$histLog = Join-Path $Logs 'arm-A-gaming-default-ring.txt'
$histCap = $null
if (Test-Path -LiteralPath $histLog) {
    $m = Select-String -Path $histLog -Pattern 'the GPU class caps at (\d+) MB' | Select-Object -First 1
    if ($m) { $histCap = [double]$m.Matches[0].Groups[1].Value }
}
# UNITS: bytes in, MiB out.  The OLD policy divides VRAM in BYTES and clamps in bytes, so the
# recompute must do the same and only then convert.  And the conversion must TRUNCATE the same
# way the C++ does: the probe prints `cap >> 20`, and vram/16 here is 998.6875 MiB, so the
# honest expected value is 998, not 998.6875.  Comparing the un-truncated figure failed this
# check once, which is why it is stated rather than assumed.
$bChecks = [ordered]@{}
$bChecks['shipped_old_policy_source_found'] = $d3dFn.Success
$bChecks['shipped_old_policy_divisor_parsed'] = $divRe.Success
$bChecks['shipped_old_policy_lo_parsed'] = $loRe.Success
$bChecks['shipped_old_policy_hi_parsed'] = $hiRe.Success
if ($d3dFn.Success -and $divRe.Success -and $loRe.Success -and $hiRe.Success) {
    $expDivisor = [double]$divRe.Groups[1].Value
    $expLo = [uint64]$loRe.Groups[1].Value * 1MB
    $expHi = [uint64]$hiRe.Groups[1].Value * 1MB
    $expOldCapB = [math]::Floor([double]$vramBytes / $expDivisor)
    if ($expOldCapB -lt $expLo) { $expOldCapB = $expLo }
    if ($expOldCapB -gt $expHi) { $expOldCapB = $expHi }
    $expOldCapMiB = [math]::Floor($expOldCapB / 1MB)
    $notes.Add(("OLD policy PARSED from d3d11_ctx.cpp: divisor={0} lo={1}MiB hi={2}MiB -> {3}MiB" -f $expDivisor, ($expLo/1MB), ($expHi/1MB), $expOldCapMiB))
    # The gate now asserts against the SHIPPED SOURCE'S OWN numbers.  Change /16 to /8 in
    # d3d11_ctx.cpp and this check goes RED, which is the whole point of the finding.
    $bChecks['old_cap_reproduced_from_the_shipped_source'] = ([double]$oldCap -eq $expOldCapMiB)
}
$bChecks['old_cap_matches_2026-10-07 run log'] = ($histCap -ne $null -and [double]$oldCap -eq $histCap)
$bChecks['old_cap_below_new_cap']   = ([double]$oldCap -lt [double]$newCap)
$bChecks['old_cap_is_tiny_share_of_ram'] = ([double]$oldPct -lt 5.0)
$arms['B'] = [ordered]@{ status = 'GREEN'; what = 'OLD cap PARSED from d3d11_ctx.cpp (not re-implemented here) and matched to the shipped run log'; checks = $bChecks }

# --- ARM C: seconds of ring, DERIVED -----------------------------------------------------
# ARITHMETIC at the code's own law (replay.cpp:98-102).  WHY NO 4K RUN EXISTS (corrected
# 2026-10-07 — this used to cite a literal clamp that lane 7 removed at 12:26): this host's
# only monitor is 1920x1080 and WGC refuses every capture item, so no capture above 1080p can
# happen on this machine at all (receipt-18 §2).  Labelled DERIVED below.
$cases = @{}
foreach ($line in ($probeText -split "`r?`n")) {
    if ($line -match '^PROBE case=(\S+) bitrate_mbps=(\S+) want_mib=(\S+) old_kept_s=(\S+) new_kept_s=(\S+) old_clipped=(\d) new_clipped=(\d)') {
        $cases[$Matches[1]] = [ordered]@{
            bitrate_mbps = [double]$Matches[2]; want_mib = [double]$Matches[3]
            old_kept_s = [double]$Matches[4];   new_kept_s = [double]$Matches[5]
            old_clipped = [int]$Matches[6];     new_clipped = [int]$Matches[7]
        }
    }
}
$cChecks = [ordered]@{}
$cChecks['both_cases_derived']      = ($cases.ContainsKey('1080p60') -and $cases.ContainsKey('4K60'))
$hd = $cases['1080p60']; $uhd = $cases['4K60']
# 1080p60 is corroborated by a REAL run (arm-A log: "CHOSE 643 MB = 120.0 s"), so its want is
# a measured number; the seconds under a cap are still derived.
$cChecks['1080p60_want_matches_measured_run'] = ([math]::Abs($hd.want_mib - 643) -le 2)
$cChecks['1080p60_unaffected_by_both_caps']   = ($hd.old_clipped -eq 0 -and $hd.new_clipped -eq 0)
# 4K60: the defect.  Old cap clips to ~46.5 s; the new cap restores the promised 120 s.
$cChecks['4K60_old_cap_clipping_to_under_120s'] = ($uhd.old_kept_s -lt 120 -and $uhd.old_kept_s -gt 40)
$cChecks['4K60_old_clipped_flag']              = ($uhd.old_clipped -eq 1)
$cChecks['4K60_new_cap_restores_120s']         = ($uhd.new_kept_s -ge 120 -and $uhd.new_clipped -eq 0)
$cChecks['new_cap_buys_more_4K60_than_old']    = ($uhd.new_kept_s -gt $uhd.old_kept_s)
$arms['C'] = [ordered]@{ status = 'GREEN'; what = 'DERIVED seconds-of-ring at 1080p60 and 4K60 under both caps (no 4K run possible on this host: 1080p-only monitor + WGC refuses every item)'; checks = $cChecks }

# ---------------------------------------------------------------- ARM D: THE CONTROL
# The pre-change ring_buffer.{h,cpp} restored in a COPY.  The SAME control source that links
# against the current code MUST fail to link against this copy — because the old ring had no
# budget API at all.  If the control arm ever links, the control is not controlling anything.
$dChecks = [ordered]@{}
$oldDir = Join-Path $Ctl 'old'
foreach ($d in @($oldDir)) { if (-not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null } }
Copy-Item -LiteralPath (Join-Path $Ctl 'ring_buffer.h.prefix')   -Destination (Join-Path $oldDir 'ring_buffer.h')   -Force
Copy-Item -LiteralPath (Join-Path $Ctl 'ring_buffer.cpp.prefix') -Destination (Join-Path $oldDir 'ring_buffer.cpp') -Force

$dBuildArgv = @(
    '-std=c++17','-O2','-I',$oldDir,'-I',$Src,
    (Join-Path $Main '_lane3_ringcap_control_budget.cpp'),
    (Join-Path $oldDir 'ring_buffer.cpp'), (Join-Path $Src 'common.cpp'),
    '-o', (Join-Path $Build 'lane3-ringcap-control-old.exe')
) + $Libs
$dBuild = Invoke-Native -Exe $GXX -LogName 'lane3-gate-armD-old-build.log' -Argv $dBuildArgv
$dText = [string]$dBuild.out
$dChecks['old_copy_really_lacks_the_api'] = ($dBuild.rc -ne 0)
$dChecks['failure_is_the_missing_budget_api'] = ($dText -match 'query_ring_budget|ring_apply_budget')
# And the control source must still LINK against the CURRENT code — otherwise "it failed"
# could just mean the instrument is broken, which would make the control vacuous.
$newCtlArgv = @(
    '-std=c++17','-O2','-I',$Src,
    (Join-Path $Main '_lane3_ringcap_control_budget.cpp'),
    (Join-Path $Src 'ring_buffer.cpp'), (Join-Path $Src 'common.cpp'),
    '-o', (Join-Path $Build 'lane3-ringcap-control-new.exe')
) + $Libs
$newCtl = Invoke-Native -Exe $GXX -LogName 'lane3-gate-armD-new-build.log' -Argv $newCtlArgv
$dChecks['same_source_links_against_current_code'] = ($newCtl.rc -eq 0)
$newCtlRun = $null
if ($newCtl.rc -eq 0) {
    $newCtlRun = Invoke-Native -Exe (Join-Path $Build 'lane3-ringcap-control-new.exe') -LogName 'lane3-gate-armD-new-run.log' -Argv @()
    $dChecks['current_control_prints_the_cap'] = ([string]$newCtlRun.out -match 'budget_api=present cap_mib=(\d+)')
}
$arms['D'] = [ordered]@{ status = 'GREEN'; what = 'CONTROL: pre-change ring_buffer.cpp in a COPY must FAIL the same source that passes today'; checks = $dChecks }

# ---------------------------------------------------------------- ARM F: SYNTHETIC MACHINES
# GATE BLINDNESS CLOSED (2026-10-07).  On this host min(4 GiB, 25% of 47.74 GiB) = 4 GiB for
# any f >= 8.38%, and the floor binds only below 1 GiB of RAM — so ARM A can only ever observe
# the CEILING.  Two of the three policy terms were untested code.  ring_budget_from() is pure,
# so this arm runs the SAME code against machines that are not this one.
#
# The instrument is GENERATED into _main\build on every run rather than checked in, so the
# expectations below cannot drift from a stale copy and no other lane's probe file is edited.
$synthSrc = Join-Path $Build '_lane3_synth_probe.cpp'
$synthExe = Join-Path $Build 'lane3-ringcap-synth.exe'
$synthBody = @'
// GENERATED by _lane3-ringcap-gate.ps1 on every run — do not edit.
#include "ring_buffer.h"
#include <cstdio>
using namespace aireplay;

static void one(const char* label, uint64_t total, uint64_t avail, bool ok)
{
    RingBudget b = ring_budget_from(total, avail, ok);
    printf("SYNTH label=%s query_ok=%d total_mib=%llu avail_mib=%llu quarter_mib=%llu "
           "half_avail_mib=%llu cap_mib=%llu ceiling_binds=%d availability_binds=%d "
           "floor_applied=%d clamp_8gib_mib=%llu clamp_512mib_mib=%llu\n",
           label, ok ? 1 : 0,
           (unsigned long long)(total >> 20), (unsigned long long)(avail >> 20),
           (unsigned long long)(b.quarter_bytes >> 20),
           (unsigned long long)(b.half_avail_bytes >> 20),
           (unsigned long long)(b.cap_bytes >> 20),
           b.ceiling_binds ? 1 : 0, b.availability_binds ? 1 : 0, b.floor_applied ? 1 : 0,
           (unsigned long long)(ring_apply_budget(8ull << 30, b) >> 20),
           (unsigned long long)(ring_apply_budget(512ull << 20, b) >> 20));
}

int main()
{
    const uint64_t MiB = 1ull << 20;
    const uint64_t GiB = 1024ull << 20;
    one("total64gib",          64ull * GiB,  64ull * GiB, true);
    one("total16gib",          16ull * GiB,  16ull * GiB, true);
    one("total8gib",            8ull * GiB,   8ull * GiB, true);
    one("total2gib",            2ull * GiB,   2ull * GiB, true);
    one("total1gib",            1ull * GiB,   1ull * GiB, true);
    one("total512mib",        512ull * MiB, 512ull * MiB, true);
    one("host47gib_avail2gib", 48888ull * MiB, 2ull * GiB, true);
    one("query_failed",         0, 0, false);
    printf("SYNTH done\n");
    return 0;
}
'@
Set-Content -LiteralPath $synthSrc -Value $synthBody -Encoding UTF8

$synthArgv = @(
    '-std=c++17','-O2','-Wall','-Wextra','-Wno-unused-parameter','-I',$Src,
    $synthSrc, (Join-Path $Src 'ring_buffer.cpp'), (Join-Path $Src 'common.cpp'),
    '-o', $synthExe
) + $Libs
$synthBuild = Invoke-Native -Exe $GXX -LogName 'lane3-gate-armF-build.log' -Argv $synthArgv
$fChecks = [ordered]@{}
$fChecks['synthetic_probe_built'] = ($synthBuild.rc -eq 0)
$synthRun = $null
$synth = @{}
if ($synthBuild.rc -eq 0) {
    $synthRun = Invoke-Native -Exe $synthExe -LogName 'lane3-gate-armF-run.log' -Argv @()
    $fChecks['synthetic_probe_ran'] = ($synthRun.rc -eq 0)
    foreach ($line in ([string]$synthRun.out -split "`r?`n")) {
        if ($line -match '^SYNTH label=(\S+) query_ok=(\d) total_mib=(\d+) avail_mib=(\d+) quarter_mib=(\d+) half_avail_mib=(\d+) cap_mib=(\d+) ceiling_binds=(\d) availability_binds=(\d) floor_applied=(\d) clamp_8gib_mib=(\d+) clamp_512mib_mib=(\d+)') {
            $synth[$Matches[1]] = [ordered]@{
                query_ok = [int]$Matches[2]; total_mib = [double]$Matches[3]; avail_mib = [double]$Matches[4]
                quarter_mib = [double]$Matches[5]; half_avail_mib = [double]$Matches[6]; cap_mib = [double]$Matches[7]
                ceiling_binds = [int]$Matches[8]; availability_binds = [int]$Matches[9]; floor_applied = [int]$Matches[10]
                clamp_8gib_mib = [double]$Matches[11]; clamp_512mib_mib = [double]$Matches[12]
            }
        }
    }
}
$wantRows = @('total64gib','total16gib','total8gib','total2gib','total1gib','total512mib','host47gib_avail2gib','query_failed')
$missingRows = @($wantRows | Where-Object { -not $synth.ContainsKey($_) })
$fChecks['every_synthetic_machine_answered'] = ($missingRows.Count -eq 0)
if ($missingRows.Count -eq 0) {
    # 64 GiB: 25% would be 16 GiB, so the 4 GiB CEILING is the binding term.
    $fChecks['64gib_ceiling_binds']       = ($synth['total64gib'].cap_mib -eq 4096 -and $synth['total64gib'].ceiling_binds -eq 1)
    # 16 GiB: 25% lands EXACTLY on the ceiling, so the QUARTER produces the cap and the
    # ceiling flag must stay free.  This is the boundary the reviewer named.
    $fChecks['16gib_quarter_lands_on_ceiling'] = ($synth['total16gib'].cap_mib -eq 4096 -and $synth['total16gib'].ceiling_binds -eq 0)
    $fChecks['16gib_quarter_value_is_the_cap'] = ($synth['total16gib'].quarter_mib -eq 4096)
    # 8 GiB / 2 GiB / 1 GiB: the 25% term binds on its own, floor free (1 GiB lands on it).
    $fChecks['8gib_quarter_binds']         = ($synth['total8gib'].cap_mib -eq 2048 -and $synth['total8gib'].ceiling_binds -eq 0 -and $synth['total8gib'].floor_applied -eq 0)
    $fChecks['2gib_quarter_binds']         = ($synth['total2gib'].cap_mib -eq 512 -and $synth['total2gib'].floor_applied -eq 0)
    $fChecks['1gib_quarter_equals_floor']  = ($synth['total1gib'].cap_mib -eq 256 -and $synth['total1gib'].floor_applied -eq 0 -and $synth['total1gib'].ceiling_binds -eq 0)
    # Below 1 GiB the FLOOR binds — the term that can never bind on this host.
    $fChecks['floor_binds_below_1gib']     = ($synth['total512mib'].cap_mib -eq 256 -and $synth['total512mib'].floor_applied -eq 1 -and $synth['total512mib'].quarter_mib -eq 128)
    # The availability GUARD (F2): same 47.7 GiB machine as this host, but 2 GiB free -> the
    # cap must fall to 1 GiB instead of committing 4 GiB that cannot be committed.
    $fChecks['availability_guard_binds']   = ($synth['host47gib_avail2gib'].cap_mib -eq 1024 -and $synth['host47gib_avail2gib'].availability_binds -eq 1 -and $synth['host47gib_avail2gib'].ceiling_binds -eq 1)
    $fChecks['availability_guard_below_quarter'] = ($synth['host47gib_avail2gib'].cap_mib -lt $synth['host47gib_avail2gib'].quarter_mib)
    # A pool that cannot be read is reported, not guessed.
    $fChecks['failed_query_is_honest']     = ($synth['query_failed'].query_ok -eq 0 -and $synth['query_failed'].cap_mib -eq 256 -and $synth['query_failed'].floor_applied -eq 1)
    # The CLAMP on synthetic machines: over the cap -> the cap; under it -> untouched.
    $fChecks['clamp_clamps_on_an_8gib_machine'] = ($synth['total8gib'].clamp_8gib_mib -eq 2048 -and $synth['total8gib'].clamp_512mib_mib -eq 512)
    $fChecks['clamp_follows_the_guarded_cap']   = ($synth['host47gib_avail2gib'].clamp_8gib_mib -eq 1024)
}
$arms['F'] = [ordered]@{ status = 'GREEN'; what = 'SYNTHETIC MACHINES: the ceiling / 25% / availability / floor terms the real host cannot observe'; checks = $fChecks }

# ---------------------------------------------------------------- ARM G: SOURCE-LEVEL
# The three regressions that are cheap to reintroduce and expensive to notice in a log file.
# Each is a claim about the SHIPPED SOURCE, so it holds without running anything.
$replayText = Get-Content -LiteralPath (Join-Path $Src 'replay.cpp') -Raw
$ringText   = Get-Content -LiteralPath (Join-Path $Src 'ring_buffer.cpp') -Raw
$headerText = Get-Content -LiteralPath (Join-Path $Src 'ring_buffer.h') -Raw
$gChecks = [ordered]@{}
# NOTE the assignment form on purpose: replay.cpp MENTIONS d3d_.ring_cap_bytes() in a comment
# that explains why it is gone.  A bare -notmatch on the token would go red for that comment.
$gChecks['live_path_does_not_read_the_vram_cap'] = ($replayText -notmatch 'uint64_t\s+cap\s*=\s*d3d_\.ring_cap_bytes')
$gChecks['live_path_reads_the_ram_budget']        = ($replayText -match 'uint64_t\s+cap\s*=\s*ring_budget_cap_bytes\(\)')
$gChecks['log_prints_the_committed_size']         = ($replayText -match '\(unsigned long long\)\(ring_cap_ >> 20\)')
$gChecks['seconds_kept_is_no_longer_discarded']   = ($replayText -notmatch '\(void\)seconds_kept')
$gChecks['clamp_is_applied_before_the_log']       = ($replayText -match 'ring_cap_\s*=\s*ring_apply_budget\(')
$gChecks['arena_alloc_is_wrapped_in_catch']       = ($ringText  -match 'catch\s*\(\s*const std::bad_alloc')
$gChecks['init_commits_no_such_short_arena_only'] = ($ringText  -match 'the ring arena came back short')
$gChecks['init_logs_the_committed_capacity']      = ($ringText  -match 'RING ARENA COMMITTED')
$gChecks['policy_basis_is_stated_in_the_header']   = ($headerText -match 'ullAvailPhys' -and $headerText -match 'ullTotalPhys')
$gChecks['pure_policy_seam_exists']               = ($headerText -match 'ring_budget_from')
$arms['G'] = [ordered]@{ status = 'GREEN'; what = 'SOURCE-LEVEL: the hookup, the honest log, and the caught allocation are all still in the shipped files'; checks = $gChecks }

# ---------------------------------------------------------------- ARM E: the LIVE PATH
# WHAT THE LIVE PATH CHOOSES.  The hookup replay.cpp:130 -> ring_budget_cap_bytes() is now
# APPLIED (2026-10-07): the app asks init() for min(want, RAM budget), not min(want, VRAM cap).
# The probe's two numbers are therefore a COUNTERFACTUAL pair — what the VRAM cap WOULD have
# given against what the RAM budget gives — plus the source-level state of the call site.
$eChecks = [ordered]@{}
$live = @{}
foreach ($line in ($probeText -split "`r?`n")) {
    if ($line -match '^PROBE livepath case=(\S+) want_mib=(\S+) chose_today_mib=(\S+) chose_with_hookup_mib=(\S+) hookup_needed=(\d) today_kept_s=(\S+) hooked_kept_s=(\S+)') {
        $live[$Matches[1]] = [ordered]@{
            want_mib = [double]$Matches[2]; chose_today_mib = [double]$Matches[3]
            chose_with_hookup_mib = [double]$Matches[4]; hookup_needed = [int]$Matches[5]
            today_kept_s = [double]$Matches[6]; hooked_kept_s = [double]$Matches[7]
        }
    }
}
$eChecks['livepath_rows_parsed'] = ($live.ContainsKey('4K60'))
if ($live.ContainsKey('4K60')) {
    $l4k = $live['4K60']
    # Had the call site stayed on the VRAM cap, 4K60 would still be clipped...
    $eChecks['4K60_vram_cap_would_still_clip'] = ($l4k.today_kept_s -lt 120 -and $l4k.today_kept_s -gt 40)
    # ...and the RAM budget is what restores it.
    $eChecks['ram_budget_restores_the_window'] = ($l4k.hookup_needed -eq 1 -and $l4k.hooked_kept_s -ge 120)
    # The hookup is DELIVERED.  Asserting the gap PERSISTED was wrong (it punished the fix);
    # asserting the hookup is APPLIED punishes a revert, which is the correct direction now.
    $hookupApplied = -not ($replayText -match 'uint64_t\s+cap\s*=\s*d3d_\.ring_cap_bytes')
    $eChecks['hookup_is_applied_in_replay_cpp'] = $hookupApplied
    $script:hookupApplied = $hookupApplied
}
$arms['E'] = [ordered]@{ status = 'GREEN'; what = 'LIVE PATH: replay.cpp sources the cap from SYSTEM RAM; the VRAM cap is now a counterfactual'; checks = $eChecks }

# ---------------------------------------------------------------- verdict
$failed = New-Object System.Collections.Generic.List[string]
foreach ($name in $arms.Keys) {
    foreach ($ck in $arms[$name].checks.Keys) {
        if (-not $arms[$name].checks[$ck]) { $failed.Add("ARM-$name/$ck") }
    }
}

Write-Output '=========================================================================='
Write-Output ' LANE 3 GATE — ring cap: VRAM-priced vs system-RAM-priced'
Write-Output '=========================================================================='
Write-Output ("HOST   total physical RAM = {0} B = {1} MiB = {2:N2} GiB   [POPULATION: 1 host, WINDOW: measured once at gate time]" -f $cimRam, $cimRamMiB, $cimRamGiB)
Write-Output ("       source: Win32_ComputerSystem.TotalPhysicalMemory + GlobalMemoryStatusEx in the probe (independent paths, agreed: {0})" -f ([double]$totalPhys -eq [double]$cimRam))
Write-Output ("FREE   available physical RAM = {0} MiB = {1:N2} GiB   [CIM, read by this gate; the probe reads its own]" -f $availMiB, $availGiB)
Write-Output ("GPU    dedicated VRAM (DXGI, NVIDIA) = {0} MiB  — the pool the OLD cap priced the RAM arena against" -f $vramMiB)
Write-Output ''
Write-Output ("OLD CAP  d3d11_ctx.cpp  clamp(vram/{0}, {1} MiB, {2} MiB) = {3} MiB = {4:N2}% of system RAM   [PARSED from the shipped source]" -f $(if ($divRe.Success) { $divRe.Groups[1].Value } else { '?' }), $(if ($loRe.Success) { [double]$loRe.Groups[1].Value } else { '?' }), $(if ($hiRe.Success) { [double]$hiRe.Groups[1].Value } else { '?' }), $oldCap, [double]$oldPct)
# A single %, not %%: PowerShell's -f operator formats with BRACES, so %% is not collapsed to
# % the way printf would — the earlier version of this line printed a literal "50%%" at the
# reader, on a line whose whole job is to publish the terms.
Write-Output ("NEW CAP  ring_buffer.cpp   min(4 GiB, 25% physical RAM, 50% AVAILABLE) = {0} MiB = {1:N2}% of system RAM   (25% = {2} MiB; 50% of free = {3} MiB; ceiling {4}, floor {5})" -f $newCap, [double]$newPct, $quarterMiB, [int64][math]::Floor(($availBytes/2)/1MB), $(if ($ceilingB -eq '1') {'BINDS'} else {'free'}), $(if ($floorAp -eq '1') {'APPLIED'} else {'free'}))
Write-Output ''
Write-Output 'SECONDS OF RING (want = bitrate/8 x 120 s, kept = cap x 8 / bitrate)'
Write-Output '  POPULATION: 1 compile + 1 execution of the probe; WINDOW: this run.'
Write-Output '  BASIS:      DERIVED — arithmetic at the code own law (replay.cpp:98-102).'
Write-Output "              NO 4K RUN EXISTS because this host's only monitor is 1920x1080 and WGC refuses every"
Write-Output '              capture item (receipt-18 §2) — NOT because a literal clamp pins the window: lane 7'
Write-Output '              lifted that clamp at 12:26 (replay.cpp:38-42, negotiate_capture_window).'
if ($hd) {
    Write-Output ("  1080p60  {0} Mbps  wants {1} MiB -> OLD {2:N2} s | NEW {3:N2} s   [both keep the full 120 s; want corroborated by a MEASURED run]" -f $hd.bitrate_mbps, $hd.want_mib, $hd.old_kept_s, $hd.new_kept_s)
}
if ($uhd) {
    Write-Output ("  4K60     {0} Mbps  wants {1} MiB -> OLD {2:N2} s (CLIPPED) | NEW {3:N2} s (120 s RESTORED)   [DERIVED — NOT MEASURED, N=0 runs above 1080p]" -f $uhd.bitrate_mbps, $uhd.want_mib, $uhd.old_kept_s, $uhd.new_kept_s)
}
Write-Output ''
Write-Output 'LIVE PATH (replay.cpp sources the cap from SYSTEM RAM; the VRAM numbers are counterfactual)'
if ($live.ContainsKey('4K60')) {
    $l4k = $live['4K60']
    Write-Output ("  4K60  HAD IT STAYED ON VRAM = {0:N2} MiB -> {1:N2} s (CLIPPED) | WITH THE RAM BUDGET = {2:N2} MiB -> {3:N2} s   [DERIVED]" -f $l4k.chose_today_mib, $l4k.today_kept_s, $l4k.chose_with_hookup_mib, $l4k.hooked_kept_s)
}
Write-Output ("  hookup state in replay.cpp: {0}" -f $(if ($script:hookupApplied) { 'APPLIED — the app now asks for the RAM cap' } else { 'NOT APPLIED — one line to change' }))
Write-Output ''
Write-Output 'SYNTHETIC MACHINES (the terms this host cannot observe; POPULATION: 1 compile + 1 execution)'
foreach ($k in $wantRows) {
    if ($synth.ContainsKey($k)) {
        $row = $synth[$k]
        Write-Output ("  {0,-20} total {1,8} MiB  avail {2,8} MiB  ->  cap {3,6} MiB  (ceiling {4} / availability {5} / floor {6})" -f $k, $row.total_mib, $row.avail_mib, $row.cap_mib, $row.ceiling_binds, $row.availability_binds, $row.floor_applied)
    }
}
Write-Output ''
Write-Output 'ARMS'
foreach ($name in $arms.Keys) {
    $a = $arms[$name]
    Write-Output ("  ARM-{0}  {1} — {2} checks" -f $name, $a.what, $a.checks.Count)
    foreach ($ck in $a.checks.Keys) {
        Write-Output ("      [{0}] {1}" -f $(if ($a.checks[$ck]) {'PASS'} else {'FAIL'}), $ck)
    }
}
Write-Output ''
Write-Output ("CLAMP   ring_apply_budget(512 MiB) = {0} MiB (untouched) | ring_apply_budget(8 GiB) = {1} MiB (clamped to cap)" -f ($clampUnder/1MB), ($clampOver/1MB))
Write-Output "POPULATION EVERY PASS in this gate is N=1 — one compile, one execution, one host, one moment."
Write-Output '          NO FLAKINESS CLAIM IS MADE FOR ANY ARM, INCLUDING REPEATEDLY GREEN ONES.'
foreach ($n in $notes) { Write-Output ("NOTE    {0}" -f $n) }

if ($failed.Count -eq 0) {
    Write-Output ''
    Write-Output 'LANE3-GATE PASS'
    exit 0
}
Write-Output ''
Write-Output ("LANE3-GATE FAIL  failed: {0}" -f ($failed -join ', '))
exit 1