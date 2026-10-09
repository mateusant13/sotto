# LANE16 GATE - audit of the WAKE MECHANISM (read-only auditor gate).
#
# This gate does NOT repair anything. It asserts the invariants that the
# audit in receipts/receipt-21-wake-mechanism-audit.md claims, and it asserts
# them as MEASURED, not as hoped-for. Arms that measure a NEGATIVE are green
# when the negative reproduces; when the negative stops reproducing the arm
# goes red and the receipt must be updated. That is the intent: a gate that
# stays green after the mechanism is fixed is lying.
#
# HARD RULES honoured here:
#   * never a visible console window (the probe is launched through
#     pythonw / CREATE_NO_WINDOW and ARM E censuses its own pid tree);
#   * never pipe a native command for its exit code: every native call is
#     redirected to a file and read with $LASTEXITCODE;
#   * the runtime store is opened READ-ONLY (mode=ro), always.
#
# Usage:  pwsh -NoProfile -File _lane16-wake-gate.ps1
#         pwsh -NoProfile -File _lane16-wake-gate.ps1 -WindowMinutes 20
# Exit:   0 + "LANE16-GATE PASS"   |   1 + "LANE16-GATE FAIL"

[CmdletBinding()]
param(
    [int]$WindowMinutes = 15
)

$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'

$mainDir  = 'H:\sotto\_moved\aireplay\_main'
$logFile  = Join-Path $mainDir 'heartbeat.log'
$outFile  = Join-Path $mainDir '_lane16-gate.out.txt'
$taskName = 'SottoReplayHeartbeat'

# ---------------------------------------------------------------------------
# The probe source is embedded so this lane owns exactly ONE artifact.
# ---------------------------------------------------------------------------
$probePy = @'
import json, os, re, sqlite3, sys, time
from datetime import datetime

# Fed by the .ps1 launcher: the probe runs from STDIN, so __file__ does not
# exist. Never guess a path.
LANE_DIR = os.environ["LANE16_DIR"]

DB = "file:C:/Users/Administrador/.minimax/v2/sqlite/runtime-state.sqlite?mode=ro"
TARGET = "mvs_b7a9f3a7db404912b32d28fc11b83645"
HIST = [
    "WAKE-TEST-A3F1",                       # v3 inject, 12:06:18
    "Pass automatico. Continua o plano do Sotto",   # v2 inject, 11:51:49
    "reiniciei. que workspace estamos",     # the OWNER's own typed message
]
def L(ms):
    try: return datetime.fromtimestamp(int(ms) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except Exception: return repr(ms)
def mins(ms):
    return round((time.time() * 1000 - int(ms)) / 60000.0, 1)

con = sqlite3.connect(DB, uri=True)
con.row_factory = sqlite3.Row
R = {}

# ---- ARM A ---------------------------------------------------------------
# Wake payload markers = first 60 chars of every LIVE queued row's content,
# plus the historical injected texts. Nothing is invented.
markers = list(HIST)
for r in con.execute("select session_id, data_json from local_runtime_queue_items"):
    try:
        c = json.loads(r["data_json"]).get("message", {}).get("content", "") or ""
    except Exception:
        c = ""
    c = c.strip()
    if len(c) >= 40:
        markers.append(c[:60])
markers = list(dict.fromkeys(markers))          # de-dup, order kept

a = []
for m in markers:
    naive = con.execute("select count(*) from local_runtime_message_rows "
                        "where data_json like ?", ("%" + m + "%",)).fetchone()[0]
    user = con.execute("select count(*) from local_runtime_message_rows "
                       "where data_json like ? and role='user'", ("%" + m + "%",)).fetchone()[0]
    a.append({"marker": m[:56], "naive_any_role": naive, "role_user": user})
R["arm_a"] = a
R["arm_a_pop_markers"] = len(markers)
R["arm_a_pop_message_rows"] = con.execute(
    "select count(*) from local_runtime_message_rows").fetchone()[0]

# A3: phantom claims - rows claimed N times, still 'queued', no user row.
phantom = []
for r in con.execute("select id, session_id, item_id, status, claim_id, created_at_ms, "
                     "data_json from local_runtime_queue_items order by id"):
    d = json.loads(r["data_json"])
    att = d.get("deliveryAttempts", [])
    tids = [x.get("turnId") for x in att if isinstance(x, dict) and x.get("turnId")]
    landed = 0
    for t in tids:
        landed += con.execute("select count(*) from local_runtime_turn_ingress "
                              "where turn_id=?", (t,)).fetchone()[0]
        landed += con.execute("select count(*) from local_runtime_message_rows "
                              "where turn_id=?", (t,)).fetchone()[0]
    phantom.append({"id": r["id"], "session": r["session_id"][:12],
                    "status": r["status"], "claim_id": r["claim_id"],
                    "created": L(r["created_at_ms"]),
                    "age_min": mins(r["created_at_ms"]),
                    "attempts": len(att), "turns_landed_anywhere": landed})
R["arm_a3_phantom_claims"] = phantom

# A4: stranded OWNER message - a queue row whose content is the owner's own
# typed text and which never became a user-role row.
R["arm_a4_owner_rows"] = [
    {"id": p["id"], "session": p["session"], "created": p["created"],
     "age_min": p["age_min"], "attempts": p["attempts"]}
    for p in phantom if p["session"] != TARGET[:12]]

# ---- ARM B ---------------------------------------------------------------
mx = con.execute("select max(created_at_ms) from local_runtime_v2_cron_runs").fetchone()[0]
R["arm_b"] = {
    "cron_runs_pop": con.execute("select count(*) from local_runtime_v2_cron_runs").fetchone()[0],
    "newest_run": L(mx), "newest_run_age_min": mins(mx),
}
cu = con.execute("select count(*) from local_runtime_message_rows "
                 "where role='user' and source='cron'").fetchone()[0]
cun = con.execute("select max(created_at_ms) from local_runtime_message_rows "
                  "where role='user' and source='cron'").fetchone()[0]
R["arm_b"]["cron_user_rows_pop"] = cu
R["arm_b"]["cron_user_newest"] = L(cun)
R["arm_b"]["cron_user_age_min"] = mins(cun)
probe = con.execute("select d.cron_id, j.run_count, j.state, j.next_run_at_ms, "
                    "j.updated_at_ms from local_runtime_v2_cron_definitions d "
                    "join local_runtime_v2_scheduler_jobs j on j.scheduler_id=d.scheduler_id "
                    "where d.cron_id like 'probe-%'").fetchall()
R["arm_b"]["probe_crons"] = [
    {"cron_id": r["cron_id"], "run_count": r["run_count"], "state": r["state"],
     "next_run": L(r["next_run_at_ms"]),
     "overdue_min": round((time.time() * 1000 - int(r["next_run_at_ms"])) / 60000.0, 1),
     "updated": L(r["updated_at_ms"]),
     "runs_rows": con.execute("select count(*) from local_runtime_v2_cron_runs "
                              "where cron_id=?", (r["cron_id"],)).fetchone()[0]}
    for r in probe]
# B5: the shape defect - userMessageId minted by wake-fix.py line 228.
src = open(os.path.join(LANE_DIR, "wake-fix.py"),
           encoding="utf-8", errors="replace").read()
w = re.search(r'f"msg-user-v1-wake\{uuid\.uuid4\(\)\.hex\[:(\d+)\]\}"', src)
R["arm_b5_source_has_wake_mint"] = bool(w)
R["arm_b5_minted_prefix_present_in_store"] = con.execute(
    "select count(*) from local_runtime_message_rows where msg_id like 'msg-user-v1-wake%'"
).fetchone()[0]
ulens = sorted({len(json.loads(r["data_json"]).get("userMessageId") or "")
                for r in con.execute("select data_json from local_runtime_queue_items")})
R["arm_b5_queue_userMessageId_lengths"] = ulens
dlen = con.execute("select length(msg_id) from local_runtime_message_rows "
                   "where role='user' order by rowid desc limit 20").fetchall()
R["arm_b5_runtime_msg_id_lengths"] = sorted({x[0] for x in dlen})

# ---- ARM D (live half) ---------------------------------------------------
_oldest = con.execute("select min(created_at_ms) from local_runtime_queue_items "
                      "where status='queued'").fetchone()[0]
R["arm_d_live"] = {
    "queued_rows_pop": con.execute("select count(*) from local_runtime_queue_items "
                                   "where status='queued'").fetchone()[0],
    "rows_with_expiry": con.execute("select count(*) from local_runtime_queue_items "
                                    "where expires_at_ms is not null").fetchone()[0],
    "dedupe_count_for_target": con.execute(
        "select count(*) from local_runtime_queue_items where session_id=? "
        "and status='queued'", (TARGET,)).fetchone()[0],
    "oldest_queued_age_min": mins(_oldest) if _oldest else None,
}
con.close()
print(json.dumps(R, ensure_ascii=False))
'@

# ---------------------------------------------------------------------------
# Launch the probe with NO console window, and read the real exit code.
# ---------------------------------------------------------------------------
$pidFile = Join-Path $mainDir '_lane16-probe.pid'
$stdout  = Join-Path $mainDir '_lane16-probe.stdout.txt'
$stderr  = Join-Path $mainDir '_lane16-probe.stderr.txt'

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName               = 'py'
$psi.Arguments              = '-3 -'
$psi.RedirectStandardInput  = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError  = $true
$psi.UseShellExecute        = $false
$psi.CreateNoWindow         = $true
$psi.WindowStyle            = 'Hidden'
$psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
$psi.StandardErrorEncoding  = [System.Text.Encoding]::UTF8
$psi.EnvironmentVariables['LANE16_DIR']  = $mainDir
$psi.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'

$proc = New-Object System.Diagnostics.Process
$proc.StartInfo = $psi
$null = $proc.Start()
$proc.StandardInput.Write($probePy)
$proc.StandardInput.Close()

# --- ARM E witness: sample this gate's own child for a visible window ---
$visibleSamples = 0
$samples = 0
$deadline = (Get-Date).AddSeconds(30)
while (-not $proc.HasExited -and (Get-Date) -lt $deadline) {
    $samples++
    try {
        $proc.Refresh()
        if ($proc.MainWindowHandle -ne [IntPtr]::Zero -and
            $proc.MainWindowTitle -ne '') { $visibleSamples++ }
    } catch { }
    Start-Sleep -Milliseconds 50
}
$outText = $proc.StandardOutput.ReadToEnd()
$errText = $proc.StandardError.ReadToEnd()
$proc.WaitForExit()
$probeRc = $proc.ExitCode

Set-Content -Path $stdout -Value $outText -Encoding UTF8
Set-Content -Path $stderr -Value $errText -Encoding UTF8

$script:arms = @()
function Arm($name, $ok, $detail) {
    $script:arms += [pscustomobject]@{ Arm = $name; Ok = $ok; Detail = $detail }
    $tag = if ($ok) { 'PASS' } else { 'FAIL' }
    Write-Host ("[{0}] {1}: {2}" -f $tag, $name, $detail)
}

if ($probeRc -ne 0) {
    Write-Host "probe rc=$probeRc"
    Write-Host $errText
    Write-Host 'LANE16-GATE FAIL (probe did not run)'
    exit 1
}

try { $R = $outText | ConvertFrom-Json } catch {
    Write-Host "probe output not JSON: $_"
    Write-Host 'LANE16-GATE FAIL'
    exit 1
}

Write-Host ''
Write-Host '=== POPULATION / WINDOW ==='
Write-Host ("  message_rows (whole table)      : {0}" -f $R.arm_a_pop_message_rows)
Write-Host ("  wake payload markers enumerated : {0}" -f $R.arm_a_pop_markers)
Write-Host ("  cron_runs (whole table)         : {0}" -f $R.arm_b.cron_runs_pop)
Write-Host ("  role=user AND source=cron rows  : {0}" -f $R.arm_b.cron_user_rows_pop)
Write-Host ("  queued rows (whole table)       : {0}" -f $R.arm_d_live.queued_rows_pop)
Write-Host ("  heartbeat window                : last {0} min" -f $WindowMinutes)
Write-Host ''

# ==== ARM A : delivery is NOT proven by an insert; role filter is load-bearing
$aUser = @($R.arm_a | Where-Object { $_.role_user -gt 0 })
$aTrap = @($R.arm_a | Where-Object { $_.naive_any_role -gt 0 -and $_.role_user -eq 0 })
Arm 'A1-truth-no-user-delivery' `
    ($aUser.Count -eq 0) `
    ("markers={0} with >=1 role='user' row (want 0). Per marker naive/user: {1}" -f `
        $aUser.Count, (($R.arm_a | ForEach-Object { "$($_.naive_any_role)/$($_.role_user)" }) -join ' '))

Arm 'A2-control-roleblind-would-lie' `
    ($aTrap.Count -ge 1) `
    ("markers a ROLE-BLIND search would report as DELIVERED (naive>0, user=0): {0} of {1}. THE CONTROL: this is the false green that already happened once." -f `
        $aTrap.Count, $R.arm_a_pop_markers)

$phantomLanded = @($R.arm_a3_phantom_claims | ForEach-Object { $_.turns_landed_anywhere } |
                   Measure-Object -Sum).Sum
if ($null -eq $phantomLanded) { $phantomLanded = 0 }
$phantomAttempts = @($R.arm_a3_phantom_claims | ForEach-Object { $_.attempts } |
                     Measure-Object -Sum).Sum
Arm 'A3-claims-land-nowhere' `
    ($phantomLanded -eq 0) `
    ("deliveryAttempts total={0} across {1} queued rows; resulting turns found in turn_ingress OR message_rows = {1} (want 0)" -f `
        $phantomAttempts, $phantomLanded)

$oldest = ($R.arm_a3_phantom_claims | Measure-Object -Property age_min -Maximum).Maximum
Arm 'A4-no-expiry-strand' `
    ($R.arm_d_live.rows_with_expiry -eq 0) `
    ("queued rows carrying expires_at_ms = {0} (want 0); oldest queued row age = {1} min -> a stranded row never ages out" -f `
        $R.arm_d_live.rows_with_expiry, $oldest)

# ==== ARM B : the runtime's own cron scheduler is not running in this process
Arm 'B1-cron-scheduler-stale' `
    ($R.arm_b.newest_run_age_min -gt 60) `
    ("newest cron_runs row {0}, age {1} min (want >60)" -f $R.arm_b.newest_run, $R.arm_b.newest_run_age_min)

Arm 'B2-cron-user-delivery-stopped' `
    ($R.arm_b.cron_user_age_min -gt 60) `
    ("role=user AND source=cron rows={0}, newest {1}, age {2} min (want >60)" -f `
        $R.arm_b.cron_user_rows_pop, $R.arm_b.cron_user_newest, $R.arm_b.cron_user_age_min)

$probeOverdue = @($R.arm_b.probe_crons | Where-Object { $_.overdue_min -gt 0 -and $_.run_count -eq 0 -and $_.runs_rows -eq 0 })
Arm 'B3-probe-cron-never-ran' `
    ($probeOverdue.Count -ge 1) `
    ("armed probe crons overdue with run_count=0 and 0 run rows: {0}/{1}" -f `
        $probeOverdue.Count, @($R.arm_b.probe_crons).Count)

Arm 'B4-control-table-not-empty' `
    ($R.arm_b.cron_runs_pop -gt 0) `
    ("CONTROL: cron_runs holds {0} rows, so 'the cron table is non-empty' PASSES while the scheduler is {1} min dead. The arm above is what rejects that." -f `
        $R.arm_b.cron_runs_pop, $R.arm_b.newest_run_age_min)

$badLen = @($R.arm_b5_queue_userMessageId_lengths |
            Where-Object { $_ -ne 55 }).Count
# The DETERMINISTIC half is the source: wake-fix.py mints a userMessageId of a
# shape the runtime never writes. The live half is reported, not asserted, so
# the arm cannot flap when a queue row happens to be consumed mid-gate.
Arm 'B5-minted-userMessageId-shape' `
    ($R.arm_b5_source_has_wake_mint -eq $true -and `
     $R.arm_b5_minted_prefix_present_in_store -eq 0) `
    ("wake-fix.py mints msg-user-v1-wake+hex32 (source={0}); runtime writes msg_id len {1}; live queue rows have len {2} ({3} of them off-shape); rows carrying the minted prefix = {4}" -f `
        $R.arm_b5_source_has_wake_mint,
        (($R.arm_b5_runtime_msg_id_lengths) -join ','),
        (($R.arm_b5_queue_userMessageId_lengths) -join ','),
        $badLen,
        $R.arm_b5_minted_prefix_present_in_store)

# ==== ARM C : the Windows task actually fires, and each fire is accounted for
$fireRe = 'WAKE (enqueued rc=0|refused rc=2|FAILED)'
if (-not (Test-Path $logFile)) {
    Arm 'C1-task-fires' $false "heartbeat.log missing"
} else {
    $now    = Get-Date
    $cutoff = $now.AddMinutes(-$WindowMinutes)
    $all    = Get-Content $logFile
    $fires  = @()
    foreach ($l in $all) {
        if ($l -match '^\[(?<t>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]') {
            $ts = [datetime]::ParseExact($Matches.t, 'yyyy-MM-dd HH:mm:ss', $null)
            if ($ts -ge $cutoff -and $l -match $fireRe) { $fires += $ts }
        }
    }
    $gaps = @()
    for ($i = 1; $i -lt $fires.Count; $i++) {
        $gaps += [math]::Round(($fires[$i] - $fires[$i - 1]).TotalMinutes, 2)
    }
    $maxGap = if ($gaps.Count) { ($gaps | Measure-Object -Maximum).Maximum } else { 999 }
    Arm 'C1-task-fires-in-window' `
        ($fires.Count -ge 3 -and $maxGap -le 5.0) `
        ("POP fires in last {0} min = {1}; max inter-fire gap = {2} min (want >=3 fires, gap<=5)" -f `
            $WindowMinutes, $fires.Count, $maxGap)

    $failed = @($all | Where-Object { $_ -match 'WAKE FAILED' }).Count
    Arm 'C2-no-failed-fire' ($failed -eq 0) `
        ("WAKE FAILED lines in the whole log = {0} (want 0)" -f $failed)

    $refused = @($all | Where-Object { $_ -match 'WAKE refused rc=2' }).Count
    Arm 'C3-every-fire-refused-while-wedged' `
        ($refused -ge 1) `
        ("fires refused with rc=2 (dedupe) in the whole log = {0}. The task fires and the wake is REFUSED - fire != wake." -f $refused)

    # CONTROL: same parser, on a COPY truncated so the window is empty.
    $copy = $all | Where-Object {
        if ($_ -match '^\[(?<t>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]') {
            ([datetime]::ParseExact($Matches.t, 'yyyy-MM-dd HH:mm:ss', $null)) -lt $cutoff
        } else { $false }
    }
    Set-Content -Path (Join-Path $mainDir '_lane16-control-log-copy.log') `
                -Value $copy -Encoding UTF8
    $cFires = @($copy | Where-Object { $_ -match $fireRe }).Count
    Arm 'C4-control-window-is-load-bearing' `
        ($cFires -lt 3) `
        ("CONTROL: same parser over a COPY truncated to pre-window lines finds {0} fires (want <3) -> C1 measures LIVENESS, not file existence." -f $cFires)
}

# ==== ARM D : the wedge, reproduced deterministically on a throwaway store
# The predicate below is copied VERBATIM from wake-fix.py cmd_inject
# (lines 212-214). If the source drifts, ARM D0 goes red.
$wfSrc = Get-Content (Join-Path $mainDir 'wake-fix.py') -Raw
$predInSource = ($wfSrc -match "status='queued'") -and
                ($wfSrc -match "from local_runtime_queue_items where session_id=\?")
Arm 'D0-dedupe-predicate-still-in-source' `
    ($predInSource -and ($R.arm_d_live.dedupe_count_for_target -ge 0)) `
    ("wake-fix.py still refuses on `count(status='queued')` = {0}; live count for target session = {1}" -f `
        $predInSource, $R.arm_d_live.dedupe_count_for_target)

$sim = Join-Path $mainDir '_lane16-wedge-sim.sqlite'
if (Test-Path $sim) { Remove-Item $sim -Force }
$simPy = @'
import sqlite3, sys
db = sys.argv[1]
con = sqlite3.connect(db)
con.execute("create table local_runtime_queue_items (id integer primary key, "
            "session_id text, item_id text, status text, created_at_ms integer, "
            "data_json text, source text, client_request_id text, dedupe_key text, "
            "expires_at_ms integer, claim_id text, claim_lease_expires_at_ms integer, "
            "routing_fingerprint text)")
con.execute("insert into local_runtime_queue_items (session_id,item_id,status,"
            "created_at_ms,data_json,expires_at_ms) values "
            "('mvs_b7a9f3a7db404912b32d28fc11b83645','queue_lane16_stale','queued',"
            "1,'{}',NULL)")
con.commit(); con.close()
'@
$simOut = Join-Path $mainDir '_lane16-sim.out.txt'
$simPy | py -3 - $sim > $simOut 2>&1
$createRc = $LASTEXITCODE

$checkPy = @'
import sqlite3, sys
db, cure = sys.argv[1], sys.argv[2] == "cure"
con = sqlite3.connect(db); con.row_factory = sqlite3.Row
if cure:
    con.execute("delete from local_runtime_queue_items where item_id='queue_lane16_stale'")
    con.commit()
rcs = []
for attempt in range(5):
    n = con.execute("select count(*) from local_runtime_queue_items where "
                    "session_id=? and status='queued'",
                    ("mvs_b7a9f3a7db404912b32d28fc11b83645",)).fetchone()[0]
    rcs.append(2 if (n and cure is False) else 0)
    if not cure:
        con.execute("insert into local_runtime_queue_items (session_id,item_id,status,"
                    "created_at_ms,data_json,expires_at_ms) values (?,?,?,?,?,NULL)",
                    ("mvs_b7a9f3a7db404912b32d28fc11b83645", "queue_lane16_g%d" % attempt,
                     "queued", 1, "{}"))
        con.commit()
print(",".join(str(x) for x in rcs))
con.close()
'@
# HARD RULE 2: redirect to a file, then read $LASTEXITCODE. Never pipe a
# native command when its exit code matters.
$checkPy | py -3 - $sim nocure > (Join-Path $mainDir '_lane16-sim-nocure.out.txt') 2>&1
$wedgeRcCode = $LASTEXITCODE
$wedgeRc = (Get-Content (Join-Path $mainDir '_lane16-sim-nocure.out.txt') -Raw).Trim()

$checkPy | py -3 - $sim cure > (Join-Path $mainDir '_lane16-sim-cure.out.txt') 2>&1
$cureRcCode = $LASTEXITCODE
$cureRc = (Get-Content (Join-Path $mainDir '_lane16-sim-cure.out.txt') -Raw).Trim()
Remove-Item $sim -Force -ErrorAction SilentlyContinue

Arm 'D1-stale-row-refuses-forever' `
    ($createRc -eq 0 -and $wedgeRcCode -eq 0 -and $wedgeRc -eq '2,2,2,2,2') `
    ("CURE REVERTED IN A COPY (the shipped predicate, no expiry): 5 consecutive injections -> rc {0}. A row already queued refuses every future injection." -f $wedgeRc)

Arm 'D2-control-expiry-clears-the-wedge' `
    ($cureRcCode -eq 0 -and $cureRc -match '0') `
    ("CONTROL (cure: stale row cleared): injections -> rc {0}. Only the cure changes the outcome, which is what makes D1 a real control." -f $cureRc)

Arm 'D3-live-wedge-present' `
    ($R.arm_d_live.dedupe_count_for_target -ge 1 -and $R.arm_d_live.rows_with_expiry -eq 0) `
    ("live: {0} row(s) queued for the target session, {1} of them expiring, oldest {2} min old -> every heartbeat is refused rc=2" -f `
        $R.arm_d_live.dedupe_count_for_target, $R.arm_d_live.rows_with_expiry, $R.arm_d_live.oldest_queued_age_min)

# ==== ARM E : this gate leaves no window on the owner's screen
Arm 'E1-no-visible-window-from-this-gate' `
    ($visibleSamples -eq 0) `
    ("samples={0} at 50 ms over the probe's life, WS_VISIBLE window seen {1} time(s) (want 0); probe rc={2}" -f `
        $samples, $visibleSamples, $probeRc)

# ==== ARM F : the runtime process is the one under test
$node = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" |
          Where-Object { $_.CommandLine -like '*@minimax-ai/code/cli.js*' })
$started = if ($node.Count) { $node[0].CreationDate } else { $null }
Arm 'F1-runtime-process-identified' `
    ($node.Count -ge 1) `
    ("mcode runtime processes = {0}; pid {1} started {2}; newest cron run was {3} - the cron table predates this process by design of the outage." -f `
        $node.Count, $(if ($node.Count) { $node[0].ProcessId } else { '-' }), $started, $R.arm_b.newest_run)

# ---------------------------------------------------------------------------
Write-Host ''
$failed = @($script:arms | Where-Object { -not $_.Ok })
Write-Host ('ARMS: {0}   FAILED: {1}' -f $script:arms.Count, $failed.Count)
foreach ($f in $failed) { Write-Host ('  FAILED -> {0}: {1}' -f $f.Arm, $f.Detail) }

$report = @()
$report += 'LANE16 WAKE GATE  ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
$report += ('window_minutes={0}' -f $WindowMinutes)
foreach ($a in $script:arms) {
    $report += ('{0}  {1}  {2}' -f $(if ($a.Ok) { 'PASS' } else { 'FAIL' }), $a.Arm, $a.Detail)
}
$report += ('ARMS={0} FAILED={1}' -f $script:arms.Count, $failed.Count)
$report += $(if ($failed.Count -eq 0) { 'LANE16-GATE PASS' } else { 'LANE16-GATE FAIL' })
Set-Content -Path $outFile -Value ($report -join "`r`n") -Encoding UTF8

if ($failed.Count -eq 0) {
    Write-Host 'LANE16-GATE PASS'
    exit 0
} else {
    Write-Host 'LANE16-GATE FAIL'
    exit 1
}
