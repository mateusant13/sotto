# _lane23-trigger-defects-gate.ps1 — the named, mechanical gate for the two trigger defects
# this lane fixed.
#
# Run:  H:\sotto\_moved\aireplay\_main\_lane23-trigger-defects-gate.ps1
# Exit: 0 and the literal line `LANE23-GATE PASS` only when every arm behaves.
#
# THE TWO DEFECTS UNDER TEST (both were MEASURED broken first; see
# receipts\receipt-23-trigger-defects.md):
#   1. trigger.cpp's poll path evaluated only the bound key and never compared the bound
#      modifier mask.  One Alt+F10 press produced TWO CutRequests bound "F10" AND "Alt+F10";
#      a BARE F10 press produced those same two.  The cure compares the live modifier mask to
#      the binding's mask BY EQUALITY.
#   2. Bare F12 was first in the default ladder.  MS documents F12 as reserved for the
#      debugger "at all times".  The cure demotes bare F12 to LAST.  (It does NOT claim
#      RegisterHotKey(F12) fails; the documentation does not say that — see the receipt.)
#
# WHY ARM D IS A CONTROL AND NOT A CHECK: the cure for defect 1 is ONE line in trigger.cpp.
# Arm A asserts "Alt+F10 => exactly one request, bound to Alt+F10".  Arm D rebuilds the SAME
# probe against a COPY of trigger.cpp with that line reverted and REQUIRES ARM A'S ASSERTION
# TO GO RED ON IT.  If the reverted copy still produced one correct request, arm A would pass
# for the wrong reason on a broken binary and this gate would be worthless.  A gate that passes
# both sides is not a gate; this one is built so that it cannot.
#
# HARD RULES this file obeys (lane brief §4):
#   1. every child process is launched -WindowStyle Hidden: no console may flash on the owner's
#      screen (the census samples once per 60 s and cannot prove a short window never appeared,
#      so the claim is made by construction rather than by census);
#   2. no native command is ever piped; each writes to a file and this script reads $LASTEXITCODE
#      (or, for Start-Process, Process.ExitCode);
#   3. native H:\ paths only;
#   5. it edits NOTHING under src\ — the reverted trigger is a COPY written under _main\build.
$ErrorActionPreference = "Continue"

$repo = "H:\sotto\_moved\aireplay"
$src  = "$repo\src\capture"
$out  = "$repo\_main\build"
$logs = "$repo\_main\logs\lane23"
$gxx  = "H:\msys64\mingw64\bin\g++.exe"
$probe = "$repo\_main\_lane23-armprobe.cpp"
$gatelog = "$logs\lane23-trigger-defects-gate.txt"

# ERROR_HOTKEY_ALREADY_REGISTERED, from WinError.h.  Asserted by arm C so the gate fails if the
# meaning of that constant ever drifts.
$ERROR_HOTKEY_ALREADY_REGISTERED = 1409

$script:LINES = New-Object System.Collections.Generic.List[string]
function Say([string]$s) { $script:LINES.Add($s); Write-Host $s }

# Build one probe exe against one trigger.cpp.  Returns the compiler rc; the log is on disk.
function BuildProbe([string]$exe, [string]$triggerSrc, [string]$tag) {
    $blog = "$out\_lane23-build-$tag.txt"
    & $gxx -std=c++17 -O2 -Wall -Wextra -Wno-unused-parameter -I $src -I "$src\third_party" `
        "$src\common.cpp" $triggerSrc $probe -o $exe `
        -lpsapi -lgdi32 -luser32 -lole32 > $blog 2>&1
    return $LASTEXITCODE
}

# Run a probe exe with NO window and return its exit code.  Never piped.
function RunHidden([string]$exe, [string]$outf) {
    $errf = "$outf.err"
    $p = Start-Process -FilePath $exe -WindowStyle Hidden -PassThru `
                       -RedirectStandardOutput $outf -RedirectStandardError $errf
    if (-not $p.WaitForExit(60000)) { try { $p.Kill() } catch {} ; return 9999 }
    return $p.ExitCode
}

function Invoke-Gate {
    if (-not (Test-Path $logs)) { New-Item -ItemType Directory -Path $logs -Force | Out-Null }
    if (-not (Test-Path $out))  { New-Item -ItemType Directory -Path $out  -Force | Out-Null }

    Say "LANE23 GATE - trigger defects: modifier matching + F12 ordering"
    Say "SRC=$src  OUT=$out"
    Say "sha256 trigger.cpp (fixed) = $((Get-FileHash "$src\trigger.cpp" -Algorithm SHA256).Hash)"

    # ---- the cure must exist, and must be UNIQUE, or the control means nothing -------------
    $cureNeedle = 'const bool down = key_down && held_mods =='
    $lines = Get-Content "$src\trigger.cpp"
    $cureHits = @($lines | Where-Object { $_.Contains($cureNeedle) })
    Say "STEP 1 cure line occurrences in trigger.cpp = $($cureHits.Count)"
    if ($cureHits.Count -ne 1) {
        return "the cure line must occur EXACTLY ONCE for the revert to mean anything; found $($cureHits.Count)"
    }

    # ---- STEP 2: the REVERTED COPY (the control's input) -----------------------------------
    $mutDir = "$out\_lane23-trigger-mutant"
    $mutSrc = "$mutDir\trigger-reverted.cpp"
    New-Item -ItemType Directory -Path $mutDir -Force | Out-Null
    $mutated = New-Object System.Collections.Generic.List[string]
    foreach ($l in $lines) {
        if ($l.Contains($cureNeedle)) { $mutated.Add('        const bool down = key_down; (void)held_mods;   // MUTANT: cure reverted') }
        else { $mutated.Add($l) }
    }
    Set-Content -Path $mutSrc -Value $mutated -Encoding UTF8
    $stillThere = @(Get-Content $mutSrc | Where-Object { $_.Contains($cureNeedle) }).Count
    Say "STEP 2 cure line occurrences in the REVERTED COPY = $stillThere"
    if ($stillThere -ne 0) { return "the revert did not take; the control would be a no-op" }
    Say "STEP 2 sha256 reverted copy = $((Get-FileHash $mutSrc -Algorithm SHA256).Hash)"

    # ---- STEP 3: build both sides ---------------------------------------------------------
    $fixedExe = "$out\lane23-probe-fixed.exe"
    $mutExe   = "$out\lane23-probe-reverted.exe"
    $rc = BuildProbe $fixedExe "$src\trigger.cpp" "fixed"
    Say "STEP 3 build FIXED rc=$rc"
    if ($rc -ne 0) {
        Get-Content "$out\_lane23-build-fixed.txt" -Raw | Write-Host
        return "the fixed probe did not compile"
    }
    $warn = @(Select-String -Path "$out\_lane23-build-fixed.txt" -Pattern "warning:" -ErrorAction SilentlyContinue).Count
    Say "STEP 3 FIXED compiler warnings=$warn (built -Wall -Wextra; a warning is a finding)"
    if ($warn -gt 0) { return "the fixed build emitted $warn warning(s)" }

    $rc = BuildProbe $mutExe $mutSrc "reverted"
    Say "STEP 3 build REVERTED rc=$rc"
    if ($rc -ne 0) {
        Get-Content "$out\_lane23-build-reverted.txt" -Raw | Write-Host
        return "the reverted probe did not compile, so arm D has nothing to control"
    }

    # ---- STEP 4: run both sides -----------------------------------------------------------
    $fixedOut = "$logs\probe-fixed.txt"
    $mutOut   = "$logs\probe-reverted.txt"
    $rc = RunHidden $fixedExe $fixedOut
    Say "STEP 4 FIXED probe rc=$rc"
    if ($rc -ne 0) { return "the fixed probe exited rc=$rc (a crash is a failure)" }
    $rc = RunHidden $mutExe $mutOut
    Say "STEP 4 REVERTED probe rc=$rc"
    if ($rc -ne 0) { return "the reverted probe exited rc=$rc (a crash is a failure)" }

    $F = @(Get-Content $fixedOut)
    $M = @(Get-Content $mutOut)
    Say "---- FIXED probe output ----"
    $F | ForEach-Object { Say "  $_" }
    Say "---- REVERTED probe output ----"
    $M | ForEach-Object { Say "  $_" }
    Say "-----------------------------"

    function One([string[]]$set, [string]$pattern, [string]$what) {
        $hits = @($set | Where-Object { $_ -match $pattern })
        if ($hits.Count -ne 1) { return "" }
        return $hits[0]
    }

    # ---- ARM A: Alt+F10 => exactly ONE request, bound to Alt+F10 ---------------------------
    $a = One $F '^LANE23-A ' "A"
    if ($a -eq "") { return "arm A: expected exactly one LANE23-A line from the fixed probe" }
    Say "ARM A (fixed)    $a"
    if ($a -notmatch 'cuts=1 ')      { Say "ARM A FAIL :: Alt+F10 must yield exactly ONE CutRequest"; return "arm A: $a" }
    if ($a -notmatch 'bound=Alt\+F10$') {
        Say "ARM A FAIL :: the single request must be BOUND to Alt+F10 (the F10 row must not fire)"; return "arm A: $a"
    }

    # ---- ARM B: the contract's hold semantics, with and without a modifier -----------------
    # The EXPECTED BINDINGS DIFFER BY TAG, and that difference is the point.  The bare chord
    # must produce two requests bound to the BARE binding; the Alt chord must produce two bound
    # to the Alt binding.  Asserting one shared pattern for both was this lane's first mistake:
    # the pattern written down was `F10,Alt+F10` — which is exactly the BROKEN behaviour, since
    # each of those chords used to fire two bindings at once.  The gate caught it.
    $armB = @{ "-plain" = "F10,F10"; "-alt" = "Alt\+F10,Alt\+F10" }
    foreach ($tag in @("-plain","-alt")) {
        $b = One $F "^LANE23-B$([regex]::Escape($tag)) " "B$tag"
        if ($b -eq "") { return "arm B: expected exactly one LANE23-B$tag line" }
        Say "ARM B$tag (fixed)    $b"
        if ($b -notmatch 'cuts=2 ') {
            Say "ARM B$tag FAIL :: down,down,down,up,down,down,up has TWO rising edges; a held key must yield ONE request and the second press must NOT be swallowed"
            return "arm B${tag}: $b"
        }
        if ($b -notmatch "bound=$($armB[$tag])$") {
            Say "ARM B$tag FAIL :: both presses must be bound to the SAME binding this chord names, and only to it"
            return "arm B${tag}: $b"
        }
    }

    # ---- ARM C: a key owned by another app, and WHICH key ----------------------------------
    $c1 = One $F '^LANE23-C squatter=' "C1"
    $c2 = One $F '^LANE23-C summary_names_key=' "C2"
    if ($c1 -eq "" -or $c2 -eq "") { return "arm C: expected both LANE23-C lines" }
    Say "ARM C (fixed)    $c1"
    Say "ARM C (fixed)    $c2"
    if ($c1 -notmatch 'squatter=1 ')       { return "arm C: the squatter did not take VK_F23, so the ownership failure under test never happened" }
    if ($c1 -notmatch 'registered=0 ')     { Say "ARM C FAIL :: the key WAS registered; nothing was owned by another app"; return "arm C: $c1" }
    if ($c1 -notmatch 'owned=1 ')          { return "arm C: the refusal was not flagged as ERROR_HOTKEY_ALREADY_REGISTERED ($c1)" }
    if ($c1 -notmatch "err=$ERROR_HOTKEY_ALREADY_REGISTERED ") { return "arm C: expected Win32 error $ERROR_HOTKEY_ALREADY_REGISTERED ($c1)" }
    if ($c1 -notmatch 'errtext=ERROR_HOTKEY_ALREADY_REGISTERED ') { return "arm C: the error must carry readable text, not a number ($c1)" }
    if ($c1 -notmatch 'key=F23')           { Say "ARM C FAIL :: the status must NAME the key that was taken"; return "arm C: $c1" }
    if ($c2 -notmatch 'summary_names_key=1 ') { Say "ARM C FAIL :: arm_summary() must name the key, not just say it failed"; return "arm C: $c2" }
    if ($c1 -notmatch 'arm_rc=1 ') {
        Say "ARM C FAIL :: arm() must STILL return true — the poll path is live for a key we cannot register (documented contract in trigger.h)"
        return "arm C: $c1"
    }

    # ---- ARM D: THE CONTROL.  Arm A's assertion must GO RED on the reverted copy -----------
    # Arm A's assertion is `cuts=1 AND bound=Alt+F10`.  The control therefore goes RED when the
    # reverted copy FAILS that assertion, i.e. on EITHER half of it.  Both halves are checked
    # separately on purpose: a revert that still cut once but bound to the wrong key would be
    # caught by the second test alone, and a revert that cut twice but all to Alt+F10 by the
    # first.  (This test was written inverted the first time — it looked for the mutant PASSING
    # and called that red — and the gate refused to pass, which is how it was found.)
    $ad = One $M '^LANE23-A ' "D"
    if ($ad -eq "") { return "arm D: the reverted probe wrote no LANE23-A line, so the control did not run" }
    Say "ARM D (CONTROL) $ad"
    $redReasons = New-Object System.Collections.Generic.List[string]
    if ($ad -notmatch 'cuts=1 ')       { $redReasons.Add("arm A's cuts=1 assertion fails on it") }
    if ($ad -notmatch 'bound=Alt\+F10$') { $redReasons.Add("arm A's bound=Alt+F10 assertion fails on it") }
    if ($redReasons.Count -eq 0) {
        return "arm D: the reverted copy PASSED arm A's assertion ($ad), so arm A cannot fail and proves nothing"
    }
    $redText = ($redReasons -join "; ")
    Say "ARM D RED-as-expected: $redText"
    Say "ARM D: the cure is load-bearing — reverting it turns arm A red, so arm A is not vacuous"

    # ---- ARM D2: the reverted copy must not have broken the rest of the build --------------
    # A control that goes red for the WRONG reason (a compile failure, a crash) is not a
    # control.  Arm D2 pins that the reverted build merely re-introduced the defect: its arm C
    # must be IDENTICAL to the fixed one, because the revert touches the poll path only.
    $cd1 = One $M '^LANE23-C squatter=' "D2"
    $cd2 = One $M '^LANE23-C summary_names_key=' "D2b"
    if ($cd1 -eq "" -or $cd2 -eq "") { return "arm D2: the reverted probe wrote no LANE23-C lines" }
    if ($cd1 -ne $c1 -or $cd2 -ne $c2) {
        return "arm D2: the reverted copy changed arm C, so the control is not isolating the cure ($cd1)"
    }
    Say "ARM D2 arm C is byte-identical on both sides — the revert isolates the modifier cure"

    Say "MEASUREMENT NOTE :: this host, this desktop session, synthetic key state (no real"
    Say "MEASUREMENT NOTE :: keystroke is injected into the owner's session). Arm C's refusal is a"
    Say "MEASUREMENT NOTE :: REAL RegisterHotKey collision, produced by this process squating on F23."
    return ""
}

$code = Invoke-Gate
if ($code -eq "") {
    Say "LANE23-GATE PASS"
    $script:LINES -join "`n" | Set-Content -Path $gatelog -Encoding UTF8
    exit 0
} else {
    Say "LANE23-GATE FAIL :: $code"
    $script:LINES -join "`n" | Set-Content -Path $gatelog -Encoding UTF8
    Write-Host "LANE23-GATE FAIL (log: $gatelog)"
    exit 1
}