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
# 2026-10-07 -- three controls that could not fail, closed (review W-10):
#   D1  A1 read `limit 20` and asserted `-ge 1`. Now: NO LIMIT, and FULL
#       POPULATION EQUALITY (linked == carrying a role='user' row) over a
#       whole-table GROUP BY. A second arm (A1b) checks a 2x wider
#       population, and the whole-linked census is printed with its
#       counter-examples NAMED rather than silently scoped away.
#   D2  D2's control asserted `$cureRc -match '0'` -- a SUBSTRING REGEX, so
#       '2,2,2,2,0' and '20,2,2,2,2' both PASSED. Now `-eq '0,0,0,0,0'`,
#       the full five-vector the arm's own simulator produces, matching how
#       D1 asserts its treatment.
#   D3  B4 asserted `cron_runs_pop -gt 0` on a 1 442-row append-only table.
#       It CANNOT FAIL. Replaced by `B4-control-cron-regime-is-two-sided`,
#       a two-sided control on the same measurement: the newest-run age must
#       sit in exactly one of ALIVE (<= $CronFreshMinutes) / DEAD
#       (> $CronDeadMinutes); the flapping band between them is RED. The
#       1 442-row fact survives as [PROSE], asserted by nothing.
#   Also: every arm that carries a population reports it, and an arm whose
#   population is 0 prints PASS/VACUOUS-POP and is counted separately, so a
#   green gate can never be read as coverage it does not have.
#
# 2026-10-07 (re-dispatch) -- DEFECT 4, THE ONE THAT MATTERS MOST:
#   This gate could report GREEN on a quantity that is not the requirement.
#   ARM C measured only the delivery->delivery GAP and called it cadence. The
#   owner's actual metric is the send->delivery LATENCY, and the two columns
#   are NOT interchangeable -- which is exactly what made the gate dangerous:
#   a gate that measures the wrong column converts a regression into a pass.
#   ARM L now asserts BOTH and labels which is which:
#     L1  send->delivery latency  = *** THE REQUIREMENT *** (owner's wait)
#     L2  delivery->delivery gap  = SUPPORTING, and its own name says so
#     L3  CONTROL: the pairing rule is load-bearing (identity != naive index)
#     L4  CONTROL: asserts the "latency got an order of magnitude worse"
#                  claim FALSE on this log -- see the retraction below.
#
#   RETRACTION, MEASURED (POP and window in ARM L, receipts/receipt-35):
#   The orchestrator reported send->delivery latency median 2537 s (42 min),
#   0 of 121 under 180 s, against a healthy gap. That figure is an INDEX
#   PAIRING ARTIFACT, not a wake latency. The log holds 146 sends and 122
#   deliveries; `send[i] -> delivery[i]` drifts 24 slots and measures the
#   BACKLOG. It reproduces the reported numbers (min 979 s and max 6019 s are
#   bit-for-bit matches), which is how an artifact gets believed. Paired by
#   IDENTITY -- each send to the first delivery at-or-after it, a send its
#   successor pre-empts counted UNFULFILLED, not slow -- the real latency is
#   POP=121, min 27 s, median 87 s, 101 of 121 under 180 s.
#   The "order of magnitude worse" conclusion is FALSE. L3 asserts the artifact
#   is visible and L4 asserts the retraction, so neither can be re-asserted by
#   the next reader without the gate going red.
#
# Usage:  pwsh -NoProfile -File _lane16-wake-gate.ps1
#         pwsh -NoProfile -File _lane16-wake-gate.ps1 -WindowMinutes 20
# Exit:   0 + "LANE16-GATE PASS"   |   1 + "LANE16-GATE FAIL"

[CmdletBinding()]
param(
    [int]$WindowMinutes = 15,
    # ARM B thresholds, exposed so a caller can state the regime a run claims
    # to be measuring instead of inheriting two literals buried in an arm.
    [int]$CronFreshMinutes = 15,
    [int]$CronDeadMinutes  = 60,
    # ARM L budgets. DERIVED from the task's own interval, not invented: the
    # Windows task fires every 180 s (MEASURED: TASK-FIRE POP=160, median gap
    # 180 s, max 186 s, 159/159 gaps inside 180+/-6 s). A wake that took longer
    # than a couple of task intervals to land is already more than one full
    # cycle of latency the owner would have felt. LatencyMaxMinutes=2 => 3.4
    # task intervals; the p90 is held tighter than the median so a tail of
    # slow wakes cannot hide behind a good median -- a MEDIAN-ONLY gate is how
    # this gate went wrong once already (see ARM L below).
    [double]$LatencyMaxMinutes = 2.0,
    [double]$LatencyP90MaxMinutes = 5.0,
    # The GAP column is the supporting metric, NOT the requirement. Its budget
    # is the task interval plus one cycle, so it is a liveness check on the
    # task, never a proxy for the owner's wait.
    [double]$GapMaxMinutes = 6.0,
    # BOTH COLOURS. Reverts ONLY the three fixes of 2026-10-07 in a COPY of
    # this gate and runs that copy against the SAME live store. The fixed gate
    # is GREEN on these arms; the copy must be RED on the same arm names, which
    # is what "this arm can fail" means. Each revert is checked for having
    # applied -- a revert that silently no-ops is worse than no revert.
    [switch]$NegArm,
    # Artifact name. The neg-arm runs children of this same gate; without this
    # every child would overwrite the live run's report.
    [string]$OutFileName = '_lane16-gate.out.txt',
    # Suffix for the probe/sim artifacts. The neg-arm's children get their own,
    # so a -NegArm run does not leave the live run's `_lane16-probe.*` files
    # holding a CHILD's measurements.
    [string]$ArtifactTag = '',
    # DOCTOR HOOKS -- used only by -NegArm, to feed the arms a measurement the
    # old predicates would wave through and the new ones must reject. With all
    # three set, this gate is EXPECTED TO GO RED: that red is the proof.
    [int]$DoctorApiMissing = 0,
    [string]$DoctorCureRc  = '',
    [double]$DoctorCronAge = -1,
    # DOCTOR (neg-arm only): feed ARM L the REGRESSION the wrong-column gate
    # could not see -- sends that take an eternity to land while the
    # delivery->delivery gap stays perfect. That is the brief's finding,
    # reproduced exactly, and it is what L1 must reject and the reverted L1
    # (which reads the gap) calls PASS.
    [double]$DoctorLatencyMedianMin = -1,
    [double]$DoctorGapMedianMin     = -1
)

$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'

$mainDir  = 'H:\sotto\_moved\aireplay\_main'
$logFile  = Join-Path $mainDir 'heartbeat.log'
$outFile  = Join-Path $mainDir $OutFileName
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
    "ORCHESTRATOR MANDATE",                 # payload of queue row 4691
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
# THE INSTRUMENT. A queue delivery is real ONLY if a turn_ingress row LINKS a
# queue item_id to a turn (queue_item_ids_json). Text search is NOT an
# instrument: this store already holds a role='user' row whose payload is
# byte-identical to a live queue item and whose turn carries
# queue_item_ids_json = NULL. That is a hand-pushed message, and a text search
# credits it to the cron. That is the false-positive class, with a live
# example, and it is what the naive watcher would have reported.
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

# A-instrument, FULL POPULATION -- DEFECT 2 FIXED HERE.
# The shipped query was `... order by accepted_at_ms desc limit 20` and the arm
# then asserted `-ge 1`: a census of 20 rows that 19 missing user rows could
# not turn red, over a population of ~600. Two changes, both load-bearing:
#   * NO LIMIT -- every queue-linked ingress row is read;
#   * EQUALITY, not existence -- the arm compares the number of linked turns
#     against the number that carry a role='user' row, so ONE counter-example
#     is enough to go red.
# The per-turn probe is one GROUP BY over the whole table (0.06 s measured),
# not a correlated subquery per row (20 s measured), so the full population is
# affordable.
user_rows_by_turn = {}
for tid, n in con.execute(
        "select turn_id, count(*) from local_runtime_message_rows "
        "where role='user' and turn_id is not null group by turn_id"):
    user_rows_by_turn[tid] = n

linked_rows = con.execute(
    "select turn_id, session_id, claim_source, queue_item_ids_json, status, "
    "accepted_at_ms, completed_at_ms from local_runtime_turn_ingress "
    "where queue_item_ids_json is not null "
    "order by accepted_at_ms desc").fetchall()

def _census(sel):
    pop = [r for r in linked_rows if sel(r)]
    with_user = [r for r in pop if user_rows_by_turn.get(r["turn_id"], 0) >= 1]
    missing = [{"turn_id": r["turn_id"], "claim_source": r["claim_source"],
                "status": r["status"], "accepted": L(r["accepted_at_ms"])}
               for r in pop if user_rows_by_turn.get(r["turn_id"], 0) < 1]
    return {"pop": len(pop), "with_user": len(with_user),
            "missing": missing, "rows": pop, "with_rows": with_user}

# P1: the population receipt-23 states (queue-driven turn == claim_source 'api').
api = _census(lambda r: r["claim_source"] == "api")
# P2: the wider, still-honest one -- every COMPLETED turn the queue or the
# background-task runner claimed. 'communication' turns are deliberately OUT:
# a channel reply that names a queue item is not a queue DELIVERY, and this
# store holds one of them (turn_43d6e94b, completed, claim_source
# 'communication', 0 role='user' rows). Asserting over it would make the gate
# permanently red for a fact that is not a wake defect -- so it is REPORTED
# below, by turn id, rather than hidden or asserted.
bg_done = _census(lambda r: r["claim_source"] in ("api", "background-task")
                  and r["status"] == "completed")
all_linked = _census(lambda r: True)

deliveries = [{
    "turn_id": r["turn_id"], "session": r["session_id"][:14],
    "queue_items": json.loads(r["queue_item_ids_json"]),
    "status": r["status"], "accepted": L(r["accepted_at_ms"]),
    "completed": L(r["completed_at_ms"]) if r["completed_at_ms"] else None,
    "user_rows": user_rows_by_turn.get(r["turn_id"], 0),
} for r in api["rows"][:5]]

# claim_source x status breakdown of the WHOLE linked population: this is what
# makes the scoping of P1/P2 visible instead of asserted.
breakdown = {}
for r in linked_rows:
    k = "%s/%s" % (r["claim_source"], r["status"])
    b = breakdown.setdefault(k, {"pop": 0, "with_user": 0})
    b["pop"] += 1
    if user_rows_by_turn.get(r["turn_id"], 0) >= 1:
        b["with_user"] += 1

R["arm_a_proven_deliveries"] = deliveries
R["arm_a_proven_delivery_pop"] = api["pop"]
R["arm_a_api_with_user"] = api["with_user"]
R["arm_a_api_missing"] = api["missing"]
# What the PRE-FIX assertion would have said on this same population: the
# newest 20 api-linked turns (the `limit 20` the shipped query carried) and how
# many of them carry a role='user' row. Printed by A1 so the old verdict and
# the new one are always visible side by side.
R["arm_a_api_latest20_with_user"] = sum(
    1 for r in api["rows"][:20] if user_rows_by_turn.get(r["turn_id"], 0) >= 1)
R["arm_a_bg_done_pop"] = bg_done["pop"]
R["arm_a_bg_done_with_user"] = bg_done["with_user"]
R["arm_a_bg_done_missing"] = bg_done["missing"]
R["arm_a_ingress_queue_linked_pop"] = all_linked["pop"]
R["arm_a_linked_with_user"] = all_linked["with_user"]
R["arm_a_linked_missing"] = all_linked["missing"]
R["arm_a_linked_breakdown"] = breakdown

# A2 CONTROL: role='user' rows whose payload matches a wake marker but whose
# turn has NO queue linkage. Text search would credit these to the wake.
unlinked = []
for m in markers:
    for r in con.execute("select id, session_id, turn_id, created_at_ms from "
                         "local_runtime_message_rows where data_json like ? "
                         "and role='user'", ("%" + m + "%",)):
        ing = con.execute("select queue_item_ids_json, claim_source from "
                          "local_runtime_turn_ingress where turn_id=?",
                          (r["turn_id"],)).fetchone()
        if ing is None or ing["queue_item_ids_json"] is None:
            unlinked.append({"msg_row": r["id"], "session": r["session_id"][:14],
                             "turn": r["turn_id"], "at": L(r["created_at_ms"]),
                             "marker": m[:40]})
R["arm_a_control_unlinked_user_rows"] = unlinked

# A3: per live queue row, attempts vs PROVEN deliveries.
phantom = []
for r in con.execute("select id, session_id, item_id, status, claim_id, created_at_ms, "
                     "data_json from local_runtime_queue_items order by id"):
    d = json.loads(r["data_json"])
    att = d.get("deliveryAttempts", [])
    linked = con.execute("select count(*) from local_runtime_turn_ingress "
                         "where queue_item_ids_json like ?",
                         ("%" + r["item_id"] + "%",)).fetchone()[0]
    um = d.get("userMessageId")
    um_rows = con.execute("select count(*) from local_runtime_message_rows "
                          "where msg_id=?", (um,)).fetchone()[0] if um else 0
    phantom.append({"id": r["id"], "session": r["session_id"][:12],
                    "item_id": r["item_id"][:18], "status": r["status"],
                    "claim_id": r["claim_id"], "created": L(r["created_at_ms"]),
                    "age_min": mins(r["created_at_ms"]),
                    "attempts": len(att), "proven_deliveries": linked,
                    "msg_id_rows": um_rows})
R["arm_a3_phantom_claims"] = phantom

# A4: stranded rows for sessions nobody is attached to.
R["arm_a4_owner_rows"] = [
    {"id": p["id"], "session": p["session"], "created": p["created"],
     "age_min": p["age_min"], "attempts": p["attempts"],
     "proven_deliveries": p["proven_deliveries"]}
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
$pidFile = Join-Path $mainDir "_lane16-probe$ArtifactTag.pid"
$stdout  = Join-Path $mainDir "_lane16-probe$ArtifactTag.stdout.txt"
$stderr  = Join-Path $mainDir "_lane16-probe$ArtifactTag.stderr.txt"

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
# -pop is the arm's DENOMINATOR, stated on the face of the result. An arm whose
# population is 0 is not a PASS: it is an unmeasured arm, and a gate that
# prints it in the same green as a measured one is the defect this lane was
# opened to close (W-10: of six controls, two could not fail).
function Arm($name, $ok, $detail, $pop) {
    $script:arms += [pscustomobject]@{ Arm = $name; Ok = $ok; Detail = $detail; Pop = $pop }
    $tag = if ($ok) { 'PASS' } else { 'FAIL' }
    if ($null -ne $pop -and $pop -eq 0) { $tag = 'PASS/VACUOUS-POP' }
    Write-Host ("[{0}] {1}: {2}" -f $tag, $name, $detail)
}

# --- Statistics for the TWO latency columns (ARM L). Both are over the whole
# log, not a sample, and both print POP and WINDOW on the face of the arm.
function Get-Median([object[]]$xs) {
    if ($null -eq $xs -or $xs.Count -eq 0) { return $null }
    $s = @($xs | Sort-Object)
    $n = $s.Count
    if ($n % 2 -eq 1) { return [double]$s[[int](($n - 1) / 2)] }
    return ([double]$s[[int]($n / 2) - 1] + [double]$s[[int]($n / 2)]) / 2.0
}
function Get-Pct([object[]]$xs, [double]$p) {
    if ($null -eq $xs -or $xs.Count -eq 0) { return $null }
    $s = @($xs | Sort-Object)
    $idx = [int][math]::Ceiling($p * $s.Count) - 1
    if ($idx -lt 0) { $idx = 0 }
    if ($idx -ge $s.Count) { $idx = $s.Count - 1 }
    return [double]$s[$idx]
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
Write-Host ("  linked turn_ingress (claim=api) : {0}   (full population, no LIMIT)" -f $R.arm_a_proven_delivery_pop)
Write-Host ("  linked turn_ingress (ALL srcs)  : {0}   (full population, no LIMIT)" -f $R.arm_a_ingress_queue_linked_pop)
Write-Host ("  heartbeat window                : last {0} min" -f $WindowMinutes)
Write-Host ''

# ==== ARM A : delivery needs a QUEUE LINK, not a text match.
# DEFECT 2 FIXED HERE. The shipped assertion was `delivered.Count -ge 1` over a
# `limit 20` query: existence, over a truncated population. It is now FULL
# POPULATION EQUALITY -- linked == carrying a role='user' row -- over a query
# with no LIMIT. The denominator is printed in the detail string; a gate that
# does not state its denominator is not a gate.
$deliveries = @($R.arm_a_proven_deliveries)
$apiMissing = @($R.arm_a_api_missing)
$apiPop     = [int]$R.arm_a_proven_delivery_pop
$apiWith    = [int]$R.arm_a_api_with_user
# DOCTOR (neg-arm only): remove N user rows from the api-linked census, i.e.
# hand this gate a store that DOES carry the counter-example it must reject.
if ($DoctorApiMissing -gt 0) {
    $apiWith = $apiWith - $DoctorApiMissing
    $apiMissing = @($apiMissing) + @(
        1..$DoctorApiMissing | ForEach-Object {
            [pscustomobject]@{ turn_id = "DOCTORED-{0}" -f $_; claim_source = 'api'
                               status = 'completed'; accepted = '<doctored>' }
        })
    Write-Host ("[DOCTOR] api-linked census: {0} of {1} rows now lack a role='user' row" -f `
                $DoctorApiMissing, $apiPop)
}
Arm 'A1-queue-linked-delivery-proven' `
    ($apiPop -ge 1 -and $apiWith -eq $apiPop) `
    ("queue-driven deliveries: POPULATED OVER THE WHOLE TABLE -- turn_ingress rows with queue_item_ids_json NOT NULL AND claim_source='api' = {0}; of those, carrying >=1 role='user' row = {1}; COUNTER-EXAMPLES = {2} (want 0). WINDOW = whole table, no LIMIT. For contrast, the PRE-FIX predicate (`limit 20` + `-ge 1`) would have seen {3} user-bearing rows in its 20-row sample -> PASS on {4} of these counter-examples. Latest: turn={5} accepted={6} session={7} -> user_rows={8}{9}" -f `
        $apiPop, $apiWith, $apiMissing.Count, $R.arm_a_api_latest20_with_user,
        $apiMissing.Count,
        $(if ($deliveries.Count) { $deliveries[0].turn_id } else { '-' }),
        $(if ($deliveries.Count) { $deliveries[0].accepted } else { '-' }),
        $(if ($deliveries.Count) { $deliveries[0].session } else { '-' }),
        $(if ($deliveries.Count) { $deliveries[0].user_rows } else { 0 }),
        $(if ($apiMissing.Count) { ' :: OFFENDERS ' + (($apiMissing | ForEach-Object { $_.turn_id }) -join ',') } else { '' })) `
    $apiPop

# A1b: the WIDER population, same equality, different denominator. The
# claim_source='api' filter excludes the background-task runner's turns; that
# is a scope note, not a licence to check less. 'communication' is excluded on
# PURPOSE and the exclusion is measured below rather than assumed.
$bgPop  = [int]$R.arm_a_bg_done_pop
$bgWith = [int]$R.arm_a_bg_done_with_user
$bgMiss = @($R.arm_a_bg_done_missing)
Arm 'A1b-queue-linked-delivery-proven-wider' `
    ($bgPop -ge 1 -and $bgWith -eq $bgPop) `
    ("POPULATION 2x wider: turn_ingress rows with queue_item_ids_json NOT NULL AND claim_source IN ('api','background-task') AND status='completed' = {0}; carrying >=1 role='user' row = {1}; COUNTER-EXAMPLES = {2} (want 0). WINDOW = whole table." -f `
        $bgPop, $bgWith, $bgMiss.Count) `
    $bgPop

# The whole linked population, INCLUDING the excluded claim sources, reported
# with its denominator and its counter-examples named -- never asserted, and
# never silently dropped.
$allPop   = [int]$R.arm_a_ingress_queue_linked_pop
$allWith  = [int]$R.arm_a_linked_with_user
$allMiss  = @($R.arm_a_linked_missing)
$bd = ($R.arm_a_linked_breakdown.PSObject.Properties |
       ForEach-Object { '{0}={1}/{2}' -f $_.Name, $_.Value.with_user, $_.Value.pop }) -join '  '
Write-Host ''
Write-Host '=== LINKED-TURN CENSUS (REPORT, every claim_source) ==='
Write-Host ("  queue-linked turn_ingress rows (any claim_source) : {0}" -f $allPop)
Write-Host ("  of those carrying >=1 role='user' row              : {0}" -f $allWith)
Write-Host ("  counter-examples                                  : {0}" -f $allMiss.Count)
Write-Host ("  with_user/pop by claim_source/status               : {0}" -f $bd)
foreach ($m in $allMiss) {
    Write-Host ("  NOT ASSERTED, NAMED: turn={0} claim_source={1} status={2} accepted={3}" -f `
        $m.turn_id, $m.claim_source, $m.status, $m.accepted)
}
Write-Host ''

$unlinked = @($R.arm_a_control_unlinked_user_rows)
Arm 'A2-control-textsearch-would-lie' `
    ($unlinked.Count -ge 1) `
    ("CONTROL: {0} role='user' row(s) carry a wake payload whose turn has NO queue linkage (queue_item_ids_json IS NULL) - hand-pushed, not cron-delivered. A text search credits these to the wake; that is the false green." -f `
        $unlinked.Count)

# A3 CONTRACT: a queue item must NEVER be delivered more than once. The
# attempts-vs-deliveries ratio is reported; what is asserted is the invariant
# "proven deliveries <= attempts", which a duplicate-wake bug would break.
$overDelivered = @($R.arm_a3_phantom_claims | Where-Object {
    $_.proven_deliveries -gt $_.attempts })
$totAttempts = @($R.arm_a3_phantom_claims | ForEach-Object { $_.attempts } |
                 Measure-Object -Sum).Sum
if ($null -eq $totAttempts) { $totAttempts = 0 }
$totProven = @($R.arm_a3_phantom_claims | ForEach-Object { $_.proven_deliveries } |
               Measure-Object -Sum).Sum
if ($null -eq $totProven) { $totProven = 0 }
Arm 'A3-no-duplicate-delivery' `
    ($overDelivered.Count -eq 0) `
    ("live queued rows: attempts={0}, proven deliveries={1}, rows delivered more than once={2}. A row CAN legitimately burn many attempts before the session goes idle - that is the retry, not a duplicate." -f `
        $totAttempts, $totProven, $overDelivered.Count) `
    @($R.arm_a3_phantom_claims).Count

$stranded = @($R.arm_a4_owner_rows | Where-Object { $_.age_min -gt 60 })
$oldestA = ($R.arm_a3_phantom_claims | Measure-Object -Property age_min -Maximum).Maximum
Arm 'A4-no-expiry-strand' `
    ($R.arm_d_live.rows_with_expiry -eq 0) `
    ("queued rows carrying expires_at_ms = {0} (want 0); oldest queued row = {1} min old; rows older than 60 min for a non-target session = {2} -> nothing ages them out" -f `
        $R.arm_d_live.rows_with_expiry, $oldestA, $stranded.Count)

# ==== ARM B : the runtime's own cron scheduler is not running in this process
# POPULATION for ARM B: cron_runs rows = the whole table (one number, printed
# every run). PROSE, not a control: "the table is non-empty" is a fact about a
# table that only grows and that held 1 442 rows while the scheduler was dead
# for 27 h. It is not asserted, and no arm depends on it.
$cronPop  = [int]$R.arm_b.cron_runs_pop
$cronAge  = [double]$R.arm_b.newest_run_age_min
# DOCTOR (neg-arm only): an age INSIDE the flapping band (fresh <= age <=
# dead) -- a scheduler that fires, but not on the cron interval. The shipped
# `-gt 0` on a 1 442-row table called this PASS.
if ($DoctorCronAge -ge 0) {
    $cronAge = [double]$DoctorCronAge
    Write-Host ("[DOCTOR] newest-cron-run age forced to {0} min (inside the flapping band)" -f $cronAge)
}

Arm 'B1-cron-scheduler-stale' `
    ($cronAge -gt $CronDeadMinutes) `
    ("POPULATION = cron_runs whole table ({0} rows), WINDOW = whole table. Newest row {1}, age {2} min (want > {3}: the outage this gate measures)." -f `
        $cronPop, $R.arm_b.newest_run, $cronAge, $CronDeadMinutes) `
    $cronPop

Arm 'B2-cron-user-delivery-stopped' `
    ($R.arm_b.cron_user_age_min -gt $CronDeadMinutes) `
    ("role=user AND source=cron rows={0}, newest {1}, age {2} min (want >{3})" -f `
        $R.arm_b.cron_user_rows_pop, $R.arm_b.cron_user_newest, $R.arm_b.cron_user_age_min, $CronDeadMinutes)

$probeOverdue = @($R.arm_b.probe_crons | Where-Object { $_.overdue_min -gt 0 -and $_.run_count -eq 0 -and $_.runs_rows -eq 0 })
Arm 'B3-probe-cron-never-ran' `
    ($probeOverdue.Count -ge 1) `
    ("armed probe crons overdue with run_count=0 and 0 run rows: {0}/{1}" -f `
        $probeOverdue.Count, @($R.arm_b.probe_crons).Count)

# DEFECT 3 FIXED HERE. The shipped arm was
#   Arm 'B4-control-table-not-empty' ($R.arm_b.cron_runs_pop -gt 0)
# on a table the reviewer measured at 1 442 rows, in an append-only store:
# IT CANNOT FAIL. A control that cannot fail is decoration wearing a
# control's name. It is replaced by a control on the SAME measurement --
# the age of the newest cron run -- that is TWO-SIDED: the measurement must
# sit in exactly one of the two regimes this gate knows how to describe,
#   ALIVE  : age <= $CronFreshMinutes  (the scheduler is firing)
#   DEAD   : age >  $CronDeadMinutes   (the outage B1 measures)
# and the gate goes RED in the band between them, ($CronFreshMinutes,
# $CronDeadMinutes], which is a FLAPPING scheduler -- firing, but not on the
# cron interval. That is a real reachable state, it is not the state any
# receipt here claims, and the old `-gt 0` predicate called it PASS.
$cronFresh = ($cronAge -le $CronFreshMinutes)
$cronDead  = ($cronAge -gt $CronDeadMinutes)
$regime = if ($cronFresh) { 'ALIVE' } elseif ($cronDead) { 'DEAD' } else { 'FLAPPING-BAND' }
Arm 'B4-control-cron-regime-is-two-sided' `
    ($cronFresh -ne $cronDead) `
    ("POPULATION = cron_runs whole table ({0} rows), WINDOW = whole table. CONTROL, two-sided: newest run age {1} min sits in EXACTLY ONE of ALIVE (<={2}) / DEAD (>{3}); measured regime = {4}. RED in the flapping band ({2},{3}] -- a scheduler that fires but not on the cron interval, which the old `-gt 0` on a {0}-row table called PASS." -f `
        $cronPop, $cronAge, $CronFreshMinutes, $CronDeadMinutes, $regime) `
    $cronPop
Write-Host ("[PROSE] cron_runs non-empty = {0} rows. NOT asserted, NOT a control: the table only grows." -f $cronPop)

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

# ==== ARM C : the Windows task actually fires, and each fire is accounted for.
# The vocabulary of the log has changed twice under this audit (v2 'queued',
# v3 'enqueued/refused', v4 'sending/no-op'). A FIRE is any pass that logged
# its outcome, so the arm measures firing, not phrasing.
$fireRe = 'WAKE (enqueued rc=0|refused rc=2|queued|sending|no-op|FAILED)|ABORT:'
if (-not (Test-Path $logFile)) {
    Arm 'C1-task-fires' $false "heartbeat.log missing"
} else {
    $now    = Get-Date
    $cutoff = $now.AddMinutes(-$WindowMinutes)
    $all    = Get-Content $logFile
    $parse  = {
        param($lines, $since)
        $hits = @()
        foreach ($l in $lines) {
            if ($l -match '^\[(?<t>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]') {
                $ts = [datetime]::ParseExact($Matches.t, 'yyyy-MM-dd HH:mm:ss', $null)
                if ($ts -ge $since -and $l -match $fireRe) { $hits += $ts }
            }
        }
        return $hits
    }
    $fires = & $parse $all $cutoff
    $gaps = @()
    for ($i = 1; $i -lt $fires.Count; $i++) {
        $gaps += [math]::Round(($fires[$i] - $fires[$i - 1]).TotalMinutes, 2)
    }
    $maxGap = if ($gaps.Count) { ($gaps | Measure-Object -Maximum).Maximum } else { 999 }
    Arm 'C1-task-fires-in-window' `
        ($fires.Count -ge 3 -and $maxGap -le 5.0) `
        ("POP fires in last {0} min = {1}; max inter-fire gap = {2} min (want >=3 fires, gap<=5)" -f `
            $WindowMinutes, $fires.Count, $maxGap)

    # C2 is a LIVENESS contract on the LATEST fire, not a lifetime count: a past
    # ABORT line is a permanent scar in an append-only log and can never be
    # un-logged, so "zero failures in the whole log" is red by construction and
    # "zero in the window" is red until the scar ages out. What actually
    # matters to an unattended agent is: is the MOST RECENT pass healthy?
    $passLines = @($all | Where-Object {
        if ($_ -match '^\[(?<t>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]') {
            ([datetime]::ParseExact($Matches.t, 'yyyy-MM-dd HH:mm:ss', $null)) -ge $cutoff -and
                $_ -match 'WAKE (enqueued rc=0|refused rc=2|queued|sending|no-op|FAILED)|ALREADY PENDING|ABORT:|PRUNE rc'
        } else { $false }
    })
    $failedWin = @($passLines | Where-Object { $_ -match 'WAKE FAILED|ABORT:' }).Count
    $lastPass = if ($passLines.Count) { $passLines[$passLines.Count - 1] } else { '<none in window>' }
    Arm 'C2-latest-fire-is-healthy' `
        ($lastPass -notmatch 'WAKE FAILED|ABORT:') `
        ("latest pass in the {0}-min window: {1} :: {2} || failures still inside the window = {3} (scars age out; the latest one is the contract)" -f `
            $WindowMinutes, $lastPass.Substring(0, [Math]::Min(19, $lastPass.Length)), `
            $lastPass.Substring([Math]::Min(20, $lastPass.Length)), $failedWin)

    # Each fire must be accounted for by an outcome, never silently skipped.
    $outcomes = @($all | Where-Object {
        $_ -match 'WAKE (enqueued rc=0|refused rc=2|sending|no-op|FAILED|queued)|ALREADY PENDING|ABORT:|PRUNE rc'
    }).Count
    Arm 'C3-every-fire-accounted' `
        ($outcomes -ge 1) `
        ("lines carrying a pass outcome in the whole log = {0}; the task fires and every pass reaches a decision - fire != wake, but fire != silence is the contract." -f `
            $outcomes)

    # CONTROL, two-sided: the same parser must be a function of the WINDOW.
    # (a) truncated copy -> nothing in the window; (b) wide window -> fires.
    $copy = @($all | Where-Object {
        if ($_ -match '^\[(?<t>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]') {
            ([datetime]::ParseExact($Matches.t, 'yyyy-MM-dd HH:mm:ss', $null)) -lt $cutoff
        } else { $false }
    })
    Set-Content -Path (Join-Path $mainDir "_lane16-control-log-copy$ArtifactTag.log") `
                -Value $copy -Encoding UTF8
    $cNarrow = @(& $parse $copy $cutoff).Count
    $cWide   = @(& $parse $all ($now.AddMinutes(-$WindowMinutes * 12))).Count
    Arm 'C4-control-window-is-load-bearing' `
        ($cNarrow -lt 3 -and $cWide -ge 3) `
        ("CONTROL: same parser, truncated copy -> {0} fires in the {1}-min window (want <3); whole log over a {2}-min window -> {3} fires (want >=3). C1 measures LIVENESS, not file existence." -f `
            $cNarrow, $WindowMinutes, ($WindowMinutes * 12), $cWide)

    # ==== ARM L : THE OWNER'S METRIC. THE REQUIREMENT IS THE LATENCY COLUMN.
    # ---------------------------------------------------------------------------
    # WHY THIS ARM EXISTS, and why it sits directly under C1.
    #
    # The orchestrator's measurement of this log reported:
    #     delivery->delivery GAP:  POP=120, median  191 s, 49/120 under 180 s  -> "healthy"
    #     send->delivery LATENCY: POP=121, median 2537 s,  0/121 under 180 s  -> "terrible"
    # and concluded the wake got an order of magnitude worse.
    #
    # REPRODUCED AND CORRECTED (see _main/_lane16-latency-pairings.out.txt):
    # that 2537 s is an INDEX-PAIRING ARTIFACT, not a wake latency. The log
    # holds 146 sends and 122 deliveries, so `send[i] -> delivery[i]` drifts 24
    # slots and silently measures the backlog instead of the wait. It reproduces
    # the orchestrator's figures essentially exactly (min 979 s and max 6019 s
    # are bit-for-bit matches), which is how an artifact gets believed.
    #
    # THE HONEST NUMBER, identity-paired: each send matched to the FIRST
    # delivery at-or-after it, and a send whose successor fires first is
    # UNFULFILLED, not slow. POP=121, min 27 s, median 87 s, max 585 s.
    #
    # So the "order of magnitude worse" conclusion is RETRACTED, and the reason
    # it was drawn is the exact disease this arm is built to prevent: A GATE
    # THAT MEASURES THE WRONG COLUMN TURNS A REGRESSION INTO A PASS -- or, here,
    # a healthy column into a fake regression. Therefore:
    #   * L1 asserts the REQUIREMENT (send -> delivery latency), on its own;
    #   * L2 asserts the SUPPORTING column (delivery -> delivery gap) and says
    #     out loud that it is NOT the requirement;
    #   * L3 asserts the two AGREE on which one is the requirement, by proving
    #     the pairing rule is load-bearing and cannot be swapped for the gap.
    # A reader who reads only the green L2 has read a number that does not
    # answer "how long did the owner wait".
    $sendTs = @()
    $delTs  = @()
    foreach ($l in $all) {
        if ($l -match '^\[(?<t>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]') {
            $ts = [datetime]::ParseExact($Matches.t, 'yyyy-MM-dd HH:mm:ss', $null)
            if ($l -match 'WAKE sending ->')      { $sendTs += $ts }
            elseif ($l -match 'WAKE delivered rc=') { $delTs  += $ts }
        }
    }
    $logFirst = if ($all.Count) { ($all[0] -replace '^\[([^\]]+)\].*$', '$1') } else { '-' }
    $logLast  = if ($all.Count) { ($all[-1] -replace '^\[([^\]]+)\].*$', '$1') } else { '-' }

    # --- THE REQUIREMENT: send -> delivery, identity-paired. -----------------
    # The overtake rule is the whole measurement. Without it a send that its
    # successor pre-empted is credited with the successor's much later
    # delivery, and the "latency" becomes a measure of queue depth.
    $latSec = @()
    $unfulfilled = 0
    $di = 0
    for ($i = 0; $i -lt $sendTs.Count; $i++) {
        $s = $sendTs[$i]
        while ($di -lt $delTs.Count -and $delTs[$di] -lt $s) { $di++ }
        if ($di -ge $delTs.Count) { $unfulfilled++; continue }
        $nextSend = if ($i + 1 -lt $sendTs.Count) { $sendTs[$i + 1] } else { $null }
        if ($nextSend -and $delTs[$di] -gt $nextSend) { $unfulfilled++; continue }
        $latSec += ($delTs[$di] - $s).TotalSeconds
    }
    # --- THE SUPPORTING COLUMN: delivery -> delivery. ------------------------
    $gapSec = @()
    for ($i = 1; $i -lt $delTs.Count; $i++) {
        $gapSec += ($delTs[$i] - $delTs[$i - 1]).TotalSeconds
    }
    # --- THE ARTIFACT, computed and PRINTED so it can never be re-derived
    # from a stale claim again. It is reported, never asserted: it is a bug in
    # a METHOD, not a property of the wake.
    $naiveSec = @()
    for ($i = 0; $i -lt $delTs.Count -and $i -lt $sendTs.Count; $i++) {
        $naiveSec += ($delTs[$i] - $sendTs[$i]).TotalSeconds
    }

    if ($DoctorLatencyMedianMin -ge 0) {
        # Force the requirement's column into regression while the gap stays
        # perfect: the exact shape of the orchestrator's reading.
        $latSec = @($latSec | ForEach-Object { $_ * (($DoctorLatencyMedianMin * 60.0) /
                                 [double](Get-Median $latSec)) })
        Write-Host ("[DOCTOR] send->delivery latency scaled to median {0} min (the gap below is left ALONE)" -f `
                    $DoctorLatencyMedianMin)
    }
    if ($DoctorGapMedianMin -ge 0) {
        $gapSec = @($gapSec | ForEach-Object { $_ * (($DoctorGapMedianMin * 60.0) /
                                 [double](Get-Median $gapSec)) })
        Write-Host ("[DOCTOR] delivery->delivery gap scaled to median {0} min" -f $DoctorGapMedianMin)
    }

    $latMed  = Get-Median $latSec
    $latP90  = Get-Pct $latSec 0.90
    $latMax  = if ($latSec.Count) { ($latSec | Measure-Object -Maximum).Maximum } else { $null }
    $latU180 = @($latSec | Where-Object { $_ -lt 180 }).Count
    $gapMed  = Get-Median $gapSec
    $gapMax  = if ($gapSec.Count) { ($gapSec | Measure-Object -Maximum).Maximum } else { $null }
    $gapU180 = @($gapSec | Where-Object { $_ -lt 180 }).Count

    Write-Host ''
    Write-Host '=== ARM L -- TWO COLUMNS. THE REQUIREMENT IS LATENCY, NOT GAP. ==='
    Write-Host ("  WINDOW = whole log, {0} -> {1}" -f $logFirst, $logLast)
    Write-Host ("  sends POP={0}  deliveries POP={1}  drift={2}  unfulfilled sends={3}" -f `
        $sendTs.Count, $delTs.Count, ($sendTs.Count - $delTs.Count), $unfulfilled)
    Write-Host ("  [THE REQUIREMENT] send->delivery   POP={0} min={1}s median={2}s ({3} min) p90={4}s max={5}s under180s={6}/{7}" -f `
        $latSec.Count, $(if($latSec.Count){[math]::Round(($latSec|Measure-Object -Minimum).Minimum)}else{'-'}), `
        $(if($null -ne $latMed){[math]::Round($latMed)}else{'-'}), `
        $(if($null -ne $latMed){[math]::Round($latMed/60.0,2)}else{'-'}), `
        $(if($null -ne $latP90){[math]::Round($latP90)}else{'-'}), `
        $(if($null -ne $latMax){[math]::Round($latMax)}else{'-'}), $latU180, $latSec.Count)
    Write-Host ("  [SUPPORTING, NOT the requirement] delivery->delivery POP={0} median={1}s ({2} min) max={3}s under180s={4}/{0}" -f `
        $gapSec.Count, $(if($null -ne $gapMed){[math]::Round($gapMed)}else{'-'}), `
        $(if($null -ne $gapMed){[math]::Round($gapMed/60.0,2)}else{'-'}), `
        $(if($null -ne $gapMax){[math]::Round($gapMax)}else{'-'}), $gapU180)
    Write-Host ("  [ARTIFACT, REPORTED NEVER ASSERTED] naive index-pair send[i]->delivery[i] POP={0} min={1}s median={2}s max={3}s" -f `
        $naiveSec.Count, $(if($naiveSec.Count){[math]::Round(($naiveSec|Measure-Object -Minimum).Minimum)}else{'-'}), `
        $(if($naiveSec.Count){[math]::Round((Get-Median $naiveSec))}else{'-'}), `
        $(if($naiveSec.Count){[math]::Round(($naiveSec|Measure-Object -Maximum).Maximum)}else{'-'}))
    Write-Host ''

    # L1 is the arm that owns the requirement. Median AND p90: a median-only
    # latency gate is satisfiable by a population where half the owner waits
    # are unbounded, which is precisely how a latency regression survives.
    Arm 'L1-REQUIREMENT-send-to-delivery-latency' `
        ($latSec.Count -ge 1 -and $latMed -le ($LatencyMaxMinutes * 60) -and `
         $latP90 -le ($LatencyP90MaxMinutes * 60)) `
        ("*** THIS IS THE REQUIREMENT: how long the owner waited for THIS wake. *** POP={0} (each send paired with the FIRST delivery at-or-after it), WINDOW = whole log {1} -> {2}. median={3}s ({4} min, want <={5} min), p90={6}s (want <={7} min), max={8}s, under 180 s = {9}/{0}, unfulfilled sends (overtaken, NOT counted as slow) = {10}. {11}" -f `
            $latSec.Count, $logFirst, $logLast,
            [math]::Round($latMed), [math]::Round($latMed/60.0, 2), $LatencyMaxMinutes,
            [math]::Round($latP90), $LatencyP90MaxMinutes, [math]::Round($latMax),
            $latU180, $unfulfilled,
            'NOT the delivery->delivery gap: that column is measured by L2 and is not what the owner waits for.') `
        $latSec.Count

    # L2 is the supporting column, and its own text says so in the arm NAME.
    # It is asserted because the task must keep delivering AT ALL -- but a
    # reader who stops here has measured liveness, not latency.
    Arm 'L2-supporting-delivery-to-delivery-gap' `
        ($gapSec.Count -ge 1 -and $gapMed -le ($GapMaxMinutes * 60)) `
        ("SUPPORTING METRIC -- NOT THE REQUIREMENT. This column says deliveries keep ARRIVING; it says NOTHING about how long one wake took to arrive. POP={0}, WINDOW = whole log {1} -> {2}. median={3}s ({4} min, want <={5} min), max={6}s, under 180 s = {7}/{0}. A green L2 ALONE IS NOT A PASS ON THE OWNER'S WAIT -- read L1." -f `
            $gapSec.Count, $logFirst, $logLast, [math]::Round($gapMed), `
            [math]::Round($gapMed/60.0, 2), $GapMaxMinutes, [math]::Round($gapMax), $gapU180) `
        $gapSec.Count

    # L3 -- the control that makes the two columns non-interchangeable. It is
    # two-sided: the identity pairing must produce a MEDIUM that DIFFERS from
    # the naive one by the drift (if they agree, the pairing is not doing
    # anything and this arm is meaningless), and it must NOT reproduce the
    # artifact (if the identity pairing equalled the naive figure, the
    # identity pairing would BE the artifact).
    $naiveMed = Get-Median $naiveSec
    $differsFromArtifact = ($null -ne $latMed -and $null -ne $naiveMed -and
                            ([math]::Abs($naiveMed - $latMed) -gt 60))
    $healthyLatency = ($null -ne $latMed -and $latMed -le ($LatencyMaxMinutes * 60))
    Arm 'L3-control-pairing-is-load-bearing' `
        ($sendTs.Count -ne $delTs.Count -and $differsFromArtifact) `
        ("CONTROL, two-sided: sends POP={0} vs deliveries POP={1} -- drift {2} slots. Identity pairing gives median {3}s; the NAIVE index pairing gives median {4}s, a {5}s difference. The gate must read the IDENTITY column: an index pair over a drift of {2} silently measures backlog as latency (that artifact reads as a 42-min 'regression' and is WRONG). Red if the two agree, because then the pairing rule is not carrying weight." -f `
            $sendTs.Count, $delTs.Count, ($sendTs.Count - $delTs.Count),
            $(if ($null -ne $latMed) { [math]::Round($latMed) } else { '-' }),
            $(if ($null -ne $naiveMed) { [math]::Round($naiveMed) } else { '-' }),
            $(if ($null -ne $latMed -and $null -ne $naiveMed) { [math]::Round([math]::Abs($naiveMed - $latMed)) } else { '-' }),
            ($sendTs.Count - $delTs.Count)) `
        $naiveSec.Count

    # L4 -- the honest RETRACTION, asserted. The brief's finding is that the
    # owner's latency got an order of magnitude worse while the gap improved.
    # On the identity pairing that is FALSE. If someone re-reads this log and
    # believes the regression is real, this arm goes red and names it, instead
    # of the regression being quietly re-asserted in the next receipt.
    Arm 'L4-control-no-latency-regression-from-the-gap' `
        ($healthyLatency) `
        ("CONTROL: the claim 'the owner's latency got an order of magnitude worse' is asserted FALSE on this log by the identity pairing (median {0}s, want <={1} min). It was produced by index-pairing across a {2}-slot drift, NOT by the wake. If a real regression appears, it must appear in send->delivery -- L1 will go red and this control will go red with it." -f `
            $(if ($null -ne $latMed) { [math]::Round($latMed) } else { '-' }),
            $LatencyMaxMinutes, ($sendTs.Count - $delTs.Count)) `
        $latSec.Count
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

$sim = Join-Path $mainDir "_lane16-wedge-sim$ArtifactTag.sqlite"
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
$simOut = Join-Path $mainDir "_lane16-sim$ArtifactTag.out.txt"
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
$checkPy | py -3 - $sim nocure > (Join-Path $mainDir "_lane16-sim-nocure$ArtifactTag.out.txt") 2>&1
$wedgeRcCode = $LASTEXITCODE
$wedgeRc = (Get-Content (Join-Path $mainDir "_lane16-sim-nocure$ArtifactTag.out.txt") -Raw).Trim()

$checkPy | py -3 - $sim cure > (Join-Path $mainDir "_lane16-sim-cure$ArtifactTag.out.txt") 2>&1
$cureRcCode = $LASTEXITCODE
$cureRc = (Get-Content (Join-Path $mainDir "_lane16-sim-cure$ArtifactTag.out.txt") -Raw).Trim()
# DOCTOR (neg-arm only): a PARTIAL cure -- 4 of 5 injections still refusing.
# The shipped `-match '0'` predicate accepts this string; `-eq '0,0,0,0,0'`
# must not. That single line is the whole of defect 1.
if ($DoctorCureRc) {
    $cureRc = $DoctorCureRc
    Write-Host ("[DOCTOR] cure vector forced to '{0}' (a partial cure: not every injection was unblocked)" -f $cureRc)
}
Remove-Item $sim -Force -ErrorAction SilentlyContinue

Arm 'D1-stale-row-refuses-forever' `
    ($createRc -eq 0 -and $wedgeRcCode -eq 0 -and $wedgeRc -eq '2,2,2,2,2') `
    ("CURE REVERTED IN A COPY (the shipped predicate, no expiry): 5 consecutive injections -> rc {0}. A row already queued refuses every future injection." -f $wedgeRc)

# DEFECT 1 FIXED HERE. The shipped assertion was `$cureRc -match '0'` -- a
# SUBSTRING REGEX, not equality: PowerShell answers True for
# '20,2,2,2,2' -match '0' and for '2,2,2,2,0' -match '0', so the arm passed
# with FOUR of FIVE injections still refusing. The arm's real contract, read
# off $checkPy, is the FULL FIVE-VECTOR '0,0,0,0,0' (loop of 5, rc 0 each:
# `rcs.append(2 if (n and cure is False) else 0)`), and D1 above already
# compares the no-cure vector with -eq. Symmetry with D1 is the point: the
# control and the treatment must be asserted the SAME way, or the control
# certifies nothing.
Arm 'D2-control-expiry-clears-the-wedge' `
    ($cureRcCode -eq 0 -and $cureRc -eq '0,0,0,0,0') `
    ("CONTROL (cure: stale row cleared): 5 consecutive injections -> rc {0}, compared with -eq '0,0,0,0,0' (EQUALITY, not -match '0', which also answers True for 2,2,2,2,0 and 20,2,2,2,2). Only the cure changes the outcome, which is what makes D1 a real control." -f $cureRc)

$stale = $R.arm_d_live.dedupe_count_for_target
$hbSrc = Get-Content (Join-Path $mainDir 'heartbeat.ps1') -Raw
$defence = @()
if ($wfSrc -match 'def prune|"prune"' -or $wfSrc -match "choices=\[.*prune") { $defence += 'wake-fix.py prune mode' }
if ($hbSrc -match 'prune') { $defence += 'heartbeat.ps1 calls prune' }
if ($R.arm_d_live.rows_with_expiry -gt 0) { $defence += 'rows carry expires_at_ms' }
Arm 'D3-stale-row-never-blocks-a-wake' `
    ($stale -eq 0 -or $defence.Count -ge 1) `
    ("live stale rows for the target session = {0}; defences present = {1}. RED only when a stale row exists AND nothing prunes or expires it - that is the permanent wedge." -f `
        $stale, $(if ($defence.Count) { $defence -join ' + ' } else { 'NONE' }))

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
# NEG-ARM: BOTH COLOURS, in one command. The three fixes are reverted in a COPY
# and both copies are fed the SAME DOCTORED MEASUREMENTS -- the ones the fixed
# arms must reject. If the copy that carries the old predicates comes back
# GREEN on them, those predicates never could have failed, and the fix is what
# makes them bind. Live store, read-only, for both children.
$negArms = @()
if ($NegArm) {
    Write-Host ''
    Write-Host '=== NEG-ARM: same doctored measurements, reverted copy vs fixed gate ==='
    $negDir = Join-Path $mainDir '_lane16-gate-revert'
    if (Test-Path $negDir) { Remove-Item $negDir -Recurse -Force }
    New-Item -ItemType Directory -Path $negDir -Force | Out-Null
    $selfPath = $MyInvocation.MyCommand.Path

    # Revert ONE fix at a time, and refuse to continue if a pattern is gone: a
    # revert that silently no-ops would make the whole neg-arm a no-op too.
    function Revert-Fix([string]$text, [string]$old, [string]$new, [string]$label) {
        if ($text.IndexOf($old) -lt 0) {
            throw "REVERT '$label' DID NOT APPLY -- pattern not found. The shipped file drifted; this neg-arm would have certified nothing."
        }
        Write-Host ("  revert applied: {0}" -f $label)
        return $text.Replace($old, $new)
    }
    $rev = Get-Content $selfPath -Raw
    $rev = Revert-Fix $rev `
        "(`$cureRcCode -eq 0 -and `$cureRc -eq '0,0,0,0,0')" `
        "(`$cureRcCode -eq 0 -and `$cureRc -match '0')" `
        'D2: -eq 0,0,0,0,0 -> -match 0'
    $rev = Revert-Fix $rev `
        '($apiPop -ge 1 -and $apiWith -eq $apiPop)' `
        '($apiWith -ge 1)' `
        'A1: full-population equality -> -ge 1'
    $rev = Revert-Fix $rev `
        '($cronFresh -ne $cronDead)' `
        '($cronPop -gt 0)' `
        'B4: two-sided regime test -> cron_runs_pop -gt 0'
    # The 2026-10-07 re-dispatch fix: L1 must read the send->delivery column.
    # The reverted copy reads the delivery->delivery GAP instead -- which is
    # the defect the orchestrator measured (a green gap while latency rotted).
    # Same arms, same log, one column swapped.
    $rev = Revert-Fix $rev `
        '($latSec.Count -ge 1 -and $latMed -le ($LatencyMaxMinutes * 60) -and ' `
        '($gapSec.Count -ge 1 -and $gapMed -le ($GapMaxMinutes * 60) -and ' `
        'L1: send->delivery latency -> delivery->delivery gap (wrong column)'
    $revCopy = Join-Path $negDir '_lane16-wake-gate-reverted.ps1'
    Set-Content -Path $revCopy -Value $rev -Encoding utf8NoBOM -NoNewline

    # The three measurements the old predicates waved through and the fixed
    # arms must reject. POPULATION and WINDOW are stated in every arm detail.
    $docApi     = 1            # 1 counter-example inside an api-linked pop of ~80
    $docCure    = '2,2,2,2,0'  # 4 of 5 injections still refusing
    $docAge     = 30.0         # inside the flapping band (fresh<=age<=dead)
    # The regression the WRONG column cannot see: latency median pushed to
    # 42 min -- the exact figure the orchestrator reported -- while the
    # delivery->delivery gap is left at its measured value. A gate reading the
    # gap says PASS. That is the whole point of ARM L.
    $docLatMed  = 42.0
    $docGapMed  = -1           # untouched

    function Invoke-GateChild([string]$script, [string]$outRelName, [bool]$doctor, [string]$label) {
        $childOutRel = Join-Path '_lane16-gate-revert' $outRelName
        $a = @('-NoProfile', '-File', $script, '-OutFileName', $childOutRel,
               '-ArtifactTag', ("-" + $label))
        if ($doctor) {
            $a += @('-DoctorApiMissing', $docApi, '-DoctorCureRc', $docCure, '-DoctorCronAge', $docAge,
                    '-DoctorLatencyMedianMin', $docLatMed, '-DoctorGapMedianMin', $docGapMed)
        }
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = (Get-Command pwsh).Source
        $psi.Arguments = ($a | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        $psi.WindowStyle = 'Hidden'
        $psi.RedirectStandardOutput = $true
        $psi.RedirectStandardError = $true
        $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
        $psi.StandardErrorEncoding = [System.Text.Encoding]::UTF8
        $p = New-Object System.Diagnostics.Process
        $p.StartInfo = $psi
        $null = $p.Start()
        $so = $p.StandardOutput.ReadToEnd()
        $se = $p.StandardError.ReadToEnd()
        $p.WaitForExit()
        Set-Content -Path (Join-Path $negDir "$label.console.txt") -Value ($so + "`r`n" + $se) -Encoding UTF8
        $childOut = Join-Path $mainDir $childOutRel
        $statuses = @{}
        if (Test-Path $childOut) {
            foreach ($l in (Get-Content $childOut)) {
                if ($l -match '^(?<tag>PASS|FAIL|PASS/VACUOUS-POP)\s{2}(?<arm>\S+)') {
                    $statuses[$Matches.arm] = $Matches.tag
                }
            }
        }
        Write-Host ("  child {0}: rc={1} report={2}" -f $label, $p.ExitCode, $childOut)
        return @{ rc = $p.ExitCode; statuses = $statuses; out = $childOut }
    }

    $fixedChild = Invoke-GateChild $selfPath 'doctored-fixed.out.txt' $true 'fixed'
    $revChild   = Invoke-GateChild $revCopy   'doctored-reverted.out.txt' $true 'reverted'

    $threeArms = @('A1-queue-linked-delivery-proven',
                   'D2-control-expiry-clears-the-wedge',
                   'B4-control-cron-regime-is-two-sided')
    # ARM L joins the both-colours set: L1 (the requirement) must go RED on the
    # doctored latency regression, and the reverted copy -- which reads the
    # delivery->delivery gap -- must come back GREEN on the same data. That is
    # the finding from the brief, as a machine check rather than a paragraph.
    $latArms    = @('L1-REQUIREMENT-send-to-delivery-latency',
                    'L4-control-no-latency-regression-from-the-gap')
    $allNegArms = $threeArms + $latArms
    $fixedRed = @($allNegArms | Where-Object { $fixedChild.statuses[$_] -eq 'FAIL' })
    $revGreen = @($allNegArms | Where-Object { $revChild.statuses[$_] -match '^PASS' })
    $liveGreen = @($allNegArms | Where-Object {
        $armName = $_
        (($script:arms | Where-Object { $_.Arm -eq $armName } | Select-Object -First 1).Ok) -eq $true })

    $negArms += [pscustomobject]@{
        Arm = 'NEG1-fixed-gate-goes-red-on-doctored-measurements'; Ok = ($fixedRed.Count -eq $allNegArms.Count)
        Detail = ("FIXED gate fed the doctored measurements (api-linked POP ~{0} with {1} counter-example; cure vector '{2}' = 4 of 5 injections still refusing; newest cron run aged {3} min, inside the flapping band; send->delivery latency median forced to {4} min WITH the delivery->delivery gap left healthy) -> RED on {5}/{6} arms: {7}. Report: {8}" -f `
            $R.arm_a_proven_delivery_pop, $docApi, $docCure, $docAge, $docLatMed, $fixedRed.Count, $allNegArms.Count,
            ($fixedRed -join ', '), $fixedChild.out) }
    $negArms += [pscustomobject]@{
        Arm = 'NEG2-reverted-gate-cannot-see-them'; Ok = ($revGreen.Count -eq $allNegArms.Count)
        Detail = ("COPY of this gate with ONLY the fixes reverted (incl. L1 reading the delivery->delivery GAP instead of the send->delivery latency) fed the SAME doctored measurements -> GREEN on {0}/{1} arms: {2}. THAT is the defect: those controls could not fail. Reverted copy: {3}; rc={4}." -f `
            $revGreen.Count, $allNegArms.Count, ($revGreen -join ', '), $revChild.out, $revChild.rc) }
    $negArms += [pscustomobject]@{
        Arm = 'NEG3-live-store-green'; Ok = ($liveGreen.Count -eq $allNegArms.Count)
        Detail = ("LIVE run, no doctoring: {0}/{1} of the neg-arm set GREEN on the real store (api-linked POP {2}, cure rc '{3}', newest cron run age {4} min, send->delivery latency median {5} s). The fixed arms reject the doctored data and accept the real one -- they discriminate; the reverted ones accepted both." -f `
            $liveGreen.Count, $allNegArms.Count, $R.arm_a_proven_delivery_pop, $cureRc, $cronAge,
            $(if ($null -ne $latMed) { [math]::Round($latMed) } else { '-' })) }
    foreach ($n in $negArms) {
        $tag = if ($n.Ok) { 'PASS' } else { 'FAIL' }
        Write-Host ("[{0}] {1}: {2}" -f $tag, $n.Arm, $n.Detail)
    }
    Write-Host ("  reverted copy sha256={0}" -f (Get-FileHash $revCopy -Algorithm SHA256).Hash)
}

# ---------------------------------------------------------------------------
Write-Host ''
$failed  = @($script:arms | Where-Object { -not $_.Ok })
$vacuous = @($script:arms | Where-Object { $null -ne $_.Pop -and $_.Pop -eq 0 })
Write-Host ('ARMS: {0}   FAILED: {1}   VACUOUS-POP: {2}' -f `
    $script:arms.Count, $failed.Count, $vacuous.Count)
foreach ($f in $failed) { Write-Host ('  FAILED -> {0}: {1}' -f $f.Arm, $f.Detail) }
if ($vacuous.Count) {
    Write-Host '  UNMEASURED (population 0, PASS means nothing here):'
    foreach ($v in $vacuous) { Write-Host ('    -> {0} (POP=0)' -f $v.Arm) }
}

$report = @()
$report += 'LANE16 WAKE GATE  ' + (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
$report += ('window_minutes={0}' -f $WindowMinutes)
$report += ('cron_thresholds_min=fresh:{0},dead:{1}' -f $CronFreshMinutes, $CronDeadMinutes)
# REVISION PIN. The wake machinery is being edited concurrently by another
# lane (heartbeat.ps1 changed shape at 12:07 and again at 12:22; wake-fix.py
# gained a prune mode at 12:28). Every number above belongs to THESE bytes.
$gateSelf = $MyInvocation.MyCommand.Path
foreach ($f in @('heartbeat.ps1', 'wake-fix.py', 'watch-wake.py')) {
    $p = Join-Path $mainDir $f
    if (Test-Path $p) {
        $report += ('PIN {0}  sha256={1}  mtime={2}' -f $f,
                    (Get-FileHash $p -Algorithm SHA256).Hash,
                    (Get-Item $p).LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))
    }
}
if ($gateSelf -and (Test-Path $gateSelf)) {
    $report += ('PIN _lane16-wake-gate.ps1  sha256={0}  mtime={1}' -f `
                (Get-FileHash $gateSelf -Algorithm SHA256).Hash,
                (Get-Item $gateSelf).LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))
}
$report += ('CENSUS linked_turn_ingress_any_claim_source={0} with_user={1} counter_examples={2}' -f `
            $allPop, $allWith, $allMiss.Count)
foreach ($m in $allMiss) {
    $report += ('CENSUS NOT_ASSERTED_NAMED turn={0} claim_source={1} status={2} accepted={3}' -f `
                $m.turn_id, $m.claim_source, $m.status, $m.accepted)
}
foreach ($a in $script:arms) {
    $tag = if (-not $a.Ok) { 'FAIL' }
           elseif ($null -ne $a.Pop -and $a.Pop -eq 0) { 'PASS/VACUOUS-POP' }
           else { 'PASS' }
    $report += ('{0}  {1}  [pop={2}]  {3}' -f $tag, $a.Arm, $a.Pop, $a.Detail)
}
$report += ('ARMS={0} FAILED={1} VACUOUS_POP={2}' -f `
            $script:arms.Count, $failed.Count, $vacuous.Count)
if ($NegArm) {
    $negFailed = @($negArms | Where-Object { -not $_.Ok })
    $report += ('NEGARMS={0} NEGFAILED={1}' -f $negArms.Count, $negFailed.Count)
    foreach ($n in $negArms) {
        $report += ('{0}  {1}  {2}' -f $(if ($n.Ok) { 'PASS' } else { 'FAIL' }), $n.Arm, $n.Detail)
    }
    if (Test-Path (Join-Path $mainDir '_lane16-gate-revert\_lane16-wake-gate-reverted.ps1')) {
        $report += ('PIN reverted-copy  sha256={0}' -f (Get-FileHash (Join-Path $mainDir '_lane16-gate-revert\_lane16-wake-gate-reverted.ps1') -Algorithm SHA256).Hash)
    }
}
$report += $(if ($failed.Count -eq 0) { 'LANE16-GATE PASS' } else { 'LANE16-GATE FAIL' })
if ($NegArm) {
    $report += $(if ($negArms.Count -gt 0 -and @($negArms | Where-Object { -not $_.Ok }).Count -eq 0) { 'LANE16-NEGARM PASS' } else { 'LANE16-NEGARM FAIL' })
}
Set-Content -Path $outFile -Value ($report -join "`r`n") -Encoding UTF8

if ($NegArm) {
    $negFailed = @($negArms | Where-Object { -not $_.Ok })
    Write-Host ('NEG-ARMS: {0}   NEG-FAILED: {1}' -f $negArms.Count, $negFailed.Count)
    if ($negArms.Count -gt 0 -and $negFailed.Count -eq 0) { Write-Host 'LANE16-NEGARM PASS' }
    else { Write-Host 'LANE16-NEGARM FAIL'; exit 1 }
}
if ($failed.Count -eq 0) {
    Write-Host 'LANE16-GATE PASS'
    exit 0
} else {
    Write-Host 'LANE16-GATE FAIL'
    exit 1
}