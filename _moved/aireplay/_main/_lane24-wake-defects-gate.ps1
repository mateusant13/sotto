# LANE 24 GATE — the six wake defects of receipt-21 plus D-7.
#
#   pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane24-wake-defects-gate.ps1
#
# DESIGN RULE: a gate that only ever prints PASS is not a gate.  Six arms are
# CONTROLS -- each one reverts its cure in a COPY of the artifact and asserts
# the arm goes RED on that copy.  Every revert is checked for having actually
# applied (New-Revert throws if the pattern is gone), because a control that
# silently no-ops is worse than no control.
#
# HARD RULES HONOURED HERE:
#   * never pipe a native command's OUTPUT when its exit code matters --
#     everything is redirected to a file and $LASTEXITCODE is read after.
#   * no visible console window: this runs under -WindowStyle Hidden pwsh and
#     ARM X1 censuses its own pid tree rather than trusting that.
#   * native H:\ paths only.
#
# The live runtime store is READ-ONLY here.  Every arm that needs to write
# builds a throwaway store under _main\_lane24-gate\.
$ErrorActionPreference = 'Continue'
$mainDir = 'H:\sotto\_moved\aireplay\_main'
$wf      = Join-Path $mainDir 'wake-fix.py'
$hb      = Join-Path $mainDir 'heartbeat.ps1'
$cd      = Join-Path $mainDir 'check-delivery.py'
$work    = Join-Path $mainDir '_lane24-gate'
$outFile = Join-Path $mainDir '_lane24-gate.out.txt'
$env:PYTHONIOENCODING = 'utf-8'

if (Test-Path $work) { Remove-Item $work -Recurse -Force }
New-Item -ItemType Directory -Path $work -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $work 'bin') -Force | Out-Null

$script:arms = @()
function Arm($name, $ok, $detail) {
    $script:arms += [pscustomobject]@{ name = $name; ok = [bool]$ok; detail = $detail }
    $tag = if ($ok) { 'PASS' } else { 'RED ' }
    Write-Host ("  [{0}] {1}" -f $tag, $name)
    Write-Host ("         {0}" -f $detail)
}

# Run a native command, capture stdout+stderr to a file, return the exit code.
# Never a pipe on the output side.
function RunNative($exe, $argList, $logName) {
    $p = Join-Path $work $logName
    & $exe @argList > $p 2>&1
    $rc = $LASTEXITCODE
    return @{ rc = $rc; out = (Get-Content $p -Raw -Encoding UTF8); file = $p }
}

# Revert one cure inside a COPY and assert the revert applied.
function New-Revert($src, $dst, $old, $new, $label) {
    $t = Get-Content $src -Raw
    if ($t.IndexOf($old) -lt 0) {
        throw "REVERT '$label' DID NOT APPLY -- pattern not found in $src. The shipped file drifted; the control would have silently no-opped."
    }
    $t = $t.Replace($old, $new)
    Set-Content -Path $dst -Value $t -Encoding utf8NoBOM -NoNewline
    return $dst
}

function Sha($p) { (Get-FileHash $p -Algorithm SHA256).Hash.Substring(0, 16) }

Write-Host ''
Write-Host '=== LANE24 WAKE-DEFECTS GATE ==='
Write-Host ("revision pin  heartbeat.ps1 {0} {1}" -f (Sha $hb), (Get-Item $hb).LastWriteTime)
Write-Host ("revision pin  wake-fix.py   {0} {1}" -f (Sha $wf), (Get-Item $wf).LastWriteTime)
Write-Host ("revision pin  check-deliv   {0} {1}" -f (Sha $cd), (Get-Item $cd).LastWriteTime)

# ---------------------------------------------------------------- D-1 mint
Write-Host ''
Write-Host '--- D-1  userMessageId shape ---'

$shapePy = @'
import sys, base64
sys.path.insert(0, sys.argv[1])
import importlib.util
spec = importlib.util.spec_from_file_location("wf", sys.argv[2])
wf = importlib.util.module_from_spec(spec); spec.loader.exec_module(wf)
ids = [wf.mint_user_message_id() for _ in range(5)]
for i in ids:
    body = i[len(wf.USER_MESSAGE_ID_PREFIX):]
    assert len(i) == 55, f"len={len(i)}"
    assert i.startswith("msg-user-v1-"), i
    assert len(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))) == 32
    assert all(c.isalnum() or c in "-_" for c in body), body
print("SHAPE_OK 5/5 len=55 prefix=msg-user-v1- body=43 base64url->32B")
'@
Set-Content -Path (Join-Path $work 'shape.py') -Value $shapePy -Encoding utf8NoBOM
$r = RunNative 'py' @('-3', (Join-Path $work 'shape.py'), $mainDir, $wf) 'd1-shape.out'
$liveIdsOk = ($r.rc -eq 0 -and $r.out -match 'SHAPE_OK')

# what shape does the RUNTIME actually use?  read it back from the store.
$rtPy = @'
import sqlite3, json, sys, collections
DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"
con = sqlite3.connect("file:" + DB + "?mode=ro", uri=True); con.row_factory = sqlite3.Row
rows = con.execute("select data_json from local_runtime_message_rows where role='user' order by id desc limit 40").fetchall()
h = collections.Counter()
for r in rows:
    d = json.loads(r["data_json"] or "{}")
    h[len(str(d.get("msg_id") or ""))] += 1
print("RUNTIME_LEN_HIST", dict(h))
'@
Set-Content -Path (Join-Path $work 'rt.py') -Value $rtPy -Encoding utf8NoBOM
$rtr = RunNative 'py' @('-3', (Join-Path $work 'rt.py')) 'd1-runtime.out'
$m = [regex]::Match($rtr.out, 'RUNTIME_LEN_HIST \{55: (\d+)')
$runtimeN55 = if ($m.Success) { [int]$m.Groups[1].Value } else { 0 }
Arm 'D1-minted-id-matches-the-runtime-shape' `
    ($liveIdsOk -and $runtimeN55 -ge 1) `
    ("shipped mint produced 5 ids of length 55 with a 43-char base64url body decoding to 32 bytes; runtime rows of length 55 in the newest 40 role='user' rows = {0} ({1})" -f $runtimeN55, $rtr.out.Trim())

# CONTROL 1 — revert the mint to the shipped-before shape.
$wfNoMint = New-Revert $wf (Join-Path $work 'wake-fix-nomint.py') `
    '    return USER_MESSAGE_ID_PREFIX + body' `
    '    return "msg-user-v1-wake" + uuid.uuid4().hex[:32]' `
    'D1-mint'
$r = RunNative 'py' @('-3', (Join-Path $work 'shape.py'), $work, $wfNoMint) 'd1-control.out'
Arm 'D1-control-mint-reverted-goes-RED' `
    ($r.rc -ne 0) `
    ("CURE REVERTED IN A COPY (48-char hex mint): the same shape assertion exits rc={0}. This arm is RED when the revert is present and GREEN only for the real shape -- so it cannot pass vacuously." -f $r.rc)

# ------------------------------------------------------------- D-2 / D-4 cron
Write-Host ''
Write-Host '--- D-2 + D-4  cron query and the dead-scheduler alarm ---'

$st = RunNative 'py' @('-3', $wf, 'status', '--session', 'mvs_a00662bff55242cb9b56c0f1165bdad7') 'd2-status.out'
$listedCron = ([regex]::Matches($st.out, "expression='")).Count
Arm 'D2-cron-query-finds-real-expressions' `
    ($st.rc -eq 0 -and $listedCron -ge 1) `
    ("status listed {0} cron-expression job(s). The shipped query `like '%* * * * *%'` matched 0 of 30; so did the audit's proposed `like '%* * * *'`. Counting FIELDS is the fix." -f $listedCron)

# CONTROL 2 — restore the five-star requirement, faithfully.  The first
# version of this revert counted every asterisk, which `*/3 * * * *` satisfies
# (its `*/3` contributes one), so the copy still listed 7 jobs and the control
# was measuring my own imprecision instead of the defect.  The real LIKE
# required FIVE fields that are each exactly "*", which is emulated here.
$wfNoCron = New-Revert $wf (Join-Path $work 'wake-fix-nocron.py') `
    '        if len(cron_fields(r["expression"])) != 5:' `
    '        if not (len(cron_fields(r["expression"])) == 5 and all(f.strip() == "*" for f in cron_fields(r["expression"]))):' `
    'D2-cron-field-count'
$stc = RunNative 'py' @('-3', (Join-Path $work 'wake-fix-nocron.py'), 'status', '--session', 'mvs_a00662bff55222cb9b56c0f1165bdad7') 'd2-control.out'
$listedCronRev = ([regex]::Matches($stc.out, "expression='")).Count
Arm 'D2-control-star-pattern-reverted-goes-RED' `
    ($stc.rc -eq 0 -and $listedCronRev -eq 0) `
    ("CURE REVERTED IN A COPY (five-star requirement): cron jobs listed = {0}. This is the exact failure the audit described -- a status tool that prints an EMPTY cron section and reads as 'no crons configured'." -f $listedCronRev)

$al = RunNative 'py' @('-3', $wf, 'cron-alarm') 'd4-alarm.out'
Arm 'D4-cron-alarm-fires-on-the-live-outage' `
    ($al.rc -eq 3) `
    ("cron-alarm rc=3 on the real store: {0}. POPULATION and window are in the output. An ALARM on a healthy scheduler would be its own defect." -f (($al.out -split "`n" | Where-Object { $_ -match 'CRON-ALARM' }) -join ' '))

# CONTROL 3 — two-sided: a COPY of the store whose newest cron run is fresh.
# An UPDATE of created_at_ms, not an INSERT: local_runtime_v2_cron_runs has
# five CHECK constraints and a FOREIGN KEY onto cron_definitions, and the first
# version of this control died on `CHECK constraint failed:
# local_runtime_cron_run_trigger`.  What is under test is the staleness
# predicate, not the insert path.
$freshPy = @'
import sqlite3, sys, time
src, dst = sys.argv[1], sys.argv[2]
con = sqlite3.connect("file:" + src + "?mode=ro", uri=True)
con.backup(sqlite3.connect(dst))
c = sqlite3.connect(dst)
now = int(time.time() * 1000)
c.execute("update local_runtime_v2_cron_runs set created_at_ms = ? "
          "where created_at_ms = (select max(created_at_ms) from "
          "local_runtime_v2_cron_runs)", (now,))
c.commit()
print("FRESHEST_RUN_NOW", c.execute("select max(created_at_ms) from "
      "local_runtime_v2_cron_runs").fetchone()[0])
c.close()
'@
Set-Content -Path (Join-Path $work 'fresh.py') -Value $freshPy -Encoding utf8NoBOM
$storeSrc = 'C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite'
$freshDb = Join-Path $work 'fresh-store.sqlite'
$fr = RunNative 'py' @('-3', (Join-Path $work 'fresh.py'), $storeSrc, $freshDb) 'd4-fresh-copy.out'
$env:SOTTO_WAKE_DB = $freshDb
$alf = RunNative 'py' @('-3', $wf, 'cron-alarm') 'd4-alarm-fresh.out'
Remove-Item Env:SOTTO_WAKE_DB
Arm 'D4-control-alarm-silent-when-cron-is-fresh' `
    ($fr.rc -eq 0 -and $alf.rc -eq 0) `
    ("TWO-SIDED, on a COPY of the store ({0}) with a fresh cron run planted: cron-alarm rc={1}. Same predicate, opposite data -- so the alarm measures staleness rather than always shouting." -f $fr.out.Trim(), $alf.rc)

# CONTROL 4 — revert the alarm threshold.
$wfNoAlarm = New-Revert $wf (Join-Path $work 'wake-fix-noalarm.py') `
    'CRON_ALARM_MIN_MS = 15 * 60_000' `
    'CRON_ALARM_MIN_MS = 10 ** 18' `
    'D4-alarm-threshold'
$alr = RunNative 'py' @('-3', (Join-Path $work 'wake-fix-noalarm.py'), 'cron-alarm') 'd4-control.out'
Arm 'D4-control-alarm-reverted-goes-RED' `
    ($alr.rc -eq 0) `
    ("CURE REVERTED IN A COPY (threshold 10**18 min): cron-alarm rc={0} on the SAME 26.7 h outage. An alarm that cannot fire is what receipt-21 measured." -f $alr.rc)

# ------------------------------------------------------------------ D-3 wedge
Write-Host ''
Write-Host '--- D-3  the dedupe predicate ---'

$wedgeSim = Join-Path $mainDir '_lane24-wedge-sim.py'
$simDb = Join-Path $work 'wedge.sqlite'
$r = RunNative 'py' @('-3', $wedgeSim, $simDb, 'expired') 'd3-expired.out'
$expiredRcs = $r.out.Trim()
Arm 'D3-wedge-is-impossible-not-merely-swept' `
    ($r.rc -eq 0 -and $expiredRcs -eq '0,0,0,0,0') `
    ("5 consecutive injections against a dead-but-EXPIRED row, shipped code, --stale-mins 999 so the PRUNE cure is switched OFF: rc {0}. A dead row that has passed its expiry cannot refuse a wake." -f $expiredRcs)

$r = RunNative 'py' @('-3', $wedgeSim, $simDb, 'nocure') 'd3-nocure.out'
$nocureRcs = $r.out.Trim()
Arm 'D3-shipped-predicate-still-wedges-on-a-NEVER-expiring-row' `
    ($r.rc -eq 0 -and $nocureRcs -eq '2,2,2,2,2') `
    ("SAME shipped code, expires_at_ms=NULL: rc {0} -- the audit's exact numbers, reproduced by driving the real wake-fix.py. This arm documents the LIMIT of the predicate fix and is why the D-5 sweep is load-bearing, not optional." -f $nocureRcs)

# CONTROL 5 — revert expiry-awareness in the predicate.
$wfNoExp = New-Revert $wf (Join-Path $work 'wake-fix-noexp.py') `
    '        (dead if (exp is not None and int(exp) <= now_ms) else live).append(r)' `
    '        live.append(r)' `
    'D3-expiry-aware-predicate'
$r = RunNative 'py' @('-3', $wedgeSim, (Join-Path $work 'wedge2.sqlite'), 'expired', (Join-Path $work 'wake-fix-noexp.py')) 'd3-control.out'
$controlRcs = $r.out.Trim()
Arm 'D3-control-expiry-blind-predicate-goes-RED' `
    ($r.rc -eq 0 -and $controlRcs -eq '2,2,2,2,2') `
    ("CURE REVERTED IN A COPY (predicate ignores expires_at_ms) on the SAME expired row the live arm healed: rc {0}. Only the cure changes the outcome, which is what makes the live arm real." -f $controlRcs)

# ---------------------------------------------------------------- D-5 orphans
Write-Host ''
Write-Host '--- D-5  orphan rows in sessions nobody is attached to ---'

$orphanSim = Join-Path $mainDir '_lane24-orphan-sim.py'
$r = RunNative 'py' @('-3', $orphanSim, (Join-Path $work 'orphan.sqlite'), $wf) 'd5-sweep.out'
$swept = ($r.out -match 'SWEPT=1')
$keptForeign = ($r.out -match 'KEPT_FOREIGN=1')
$keptTarget = ($r.out -match 'KEPT_TARGET=1')
Arm 'D5-orphan-swept-but-no-fresh-row-is-collateral' `
    ($r.rc -eq 0 -and $swept -and $keptForeign -and $keptTarget) `
    ("sweep on the driver's own BUSY-path command: 900-min orphan swept={0}; another session's 5-min row kept={1} (foreign floor 60 min); the target's own 5-min row kept={2} (stale-mins 999, so the driver never deletes the wake it is about to queue -- the bug the previous prune fix shipped). Output: {3}" -f $swept, $keptForeign, $keptTarget, (($r.out -split "`n" | Where-Object { $_ -match '^(SWEPT|KEPT|RC)' }) -join ' '))

# CONTROL 6 — revert to the session-scoped prune.
$wfNoSweep = New-Revert $wf (Join-Path $work 'wake-fix-nosweep.py') `
    "        rows = con.execute(`n            `"select * from local_runtime_queue_items where status='queued' `"`n            `"order by rowid`").fetchall()" `
    "        rows = con.execute(`n            `"select * from local_runtime_queue_items where session_id=? `"`n            `"and status='queued' order by rowid`", (args.session,)).fetchall()" `
    'D5-all-sessions'
$r = RunNative 'py' @('-3', $orphanSim, (Join-Path $work 'orphan2.sqlite'), (Join-Path $work 'wake-fix-nosweep.py')) 'd5-control.out'
$orphanSurvived = ($r.out -match 'SWEPT=0')
Arm 'D5-control-session-scoped-prune-reverted-goes-RED' `
    ($r.rc -eq 0 -and $orphanSurvived) `
    ("CURE REVERTED IN A COPY (session-scoped prune, i.e. the pre-fix behaviour): SWEPT={0}. The orphan survives, exactly as queue_1dfd5c7c survived the one logged PRUNE event." -f $(if ($orphanSurvived) { 0 } else { 1 }))

# ------------------------------------------------------------- D-7 the branch
Write-Host ''
Write-Host '--- D-7  which transport: status does NOT predict exec acceptance ---'

# The control the orchestrator asked for: a session whose store status says
# idle while a turn lease is held MUST take the queue path.  Driven end to end
# through the REAL wake-plan, against a throwaway store built to look exactly
# like the measured refusal.
#
# Three stores, so each signal is tested ALONE.  The first version used one
# store carrying both a lease and an open turn, which let the secondary signal
# mask the reverted primary: the "branch on status" copy still answered
# busy=YES, and the arm passed only because the regex `busy=NO` matched the
# substring inside `status_says_busy=NO`.  Both faults are why the parse below
# anchors on a space-delimited field and the stores are split.
$branchPy = @'
import os, sqlite3, subprocess, sys, time
db, wf, mode = sys.argv[1], sys.argv[2], sys.argv[3]
SESS = "mvs_lane24branch000000000000000000000"
NOW = int(time.time() * 1000)
if os.path.exists(db): os.remove(db)
c = sqlite3.connect(db)
c.execute("create table local_runtime_sessions (session_id text primary key, status text, workspace_dir text, updated_at_ms integer)")
c.execute("insert into local_runtime_sessions values (?,?,?,?)", (SESS, "idle", "H:\\sotto", NOW))
c.execute("create table local_runtime_session_locks (session_id text, owner_id text, owner_kind text, acquired_at_ms integer, expires_at_ms integer)")
c.execute("create table local_runtime_turn_ingress (turn_id text primary key, session_id text, source text, client_request_id text, claim_id text, claim_source text, queue_item_ids_json text, input_json text, status text, accepted_at_ms integer, accepted_sequence integer, completed_at_ms integer, queue_acknowledged_at_ms integer, input_digest text, input_metadata_json text)")
if mode == "lease":            # PRIMARY signal alone, the measured refusal state
    c.execute("insert into local_runtime_session_locks values (?,?,?,?,?)",
              (SESS, "turn-lease:9999:abc.def", "turn", NOW, NOW + 20 * 60_000))
elif mode == "openturn":       # SECONDARY signal alone
    c.execute("insert into local_runtime_turn_ingress (turn_id,session_id,status,accepted_at_ms,completed_at_ms) values (?,?,?,?,NULL)",
              ("turn_lane24_open", SESS, "accepted", NOW - 60_000))
elif mode == "stuck":          # an open turn OLDER than the bound: must NOT wedge
    c.execute("insert into local_runtime_turn_ingress (turn_id,session_id,status,accepted_at_ms,completed_at_ms) values (?,?,?,?,NULL)",
              ("turn_lane24_stuck", SESS, "accepted", NOW - 90 * 60_000))
elif mode == "empty":          # nothing running at all
    pass
c.commit(); c.close()
env = dict(os.environ); env["SOTTO_WAKE_DB"] = db; env["PYTHONIOENCODING"] = "utf-8"
p = subprocess.run([sys.executable, wf, "wake-plan", "--session", SESS],
                   capture_output=True, text=True, env=env)
line = [l for l in p.stdout.splitlines() if l.startswith("SESSION-STATE")]
print("RC", p.returncode)
print(line[0] if line else "NO-SESSION-STATE-LINE")
'@
Set-Content -Path (Join-Path $work 'branch.py') -Value $branchPy -Encoding utf8NoBOM

# Parse the space-delimited ` busy=` FIELD.  A loose /busy=NO/ matches the
# substring inside `status_says_busy=NO`, which is how a control once passed
# for the wrong reason.
function BusyField($line) {
    if ($line -match '(?<![_a-zA-Z])busy=(YES|NO)') { return $Matches[1] }
    return 'MISSING'
}

$wfNoPlan = New-Revert $wf (Join-Path $work 'wake-fix-noplan.py') `
    '    if lease_live:' `
    "    if status != 'idle':" `
    'D7-branch-on-status'

$d7rows = @()
foreach ($m in @('lease', 'openturn', 'stuck', 'empty')) {
    $r = RunNative 'py' @('-3', (Join-Path $work 'branch.py'), (Join-Path $work "branch-$m.sqlite"), $wf, $m) "d7-$m.out"
    $ln = ($r.out -split "`n" | Where-Object { $_ -match '^SESSION-STATE' }) -join ''
    $d7rows += [pscustomobject]@{ mode = $m; line = $ln; busy = (BusyField $ln) }
    $r = RunNative 'py' @('-3', (Join-Path $work 'branch.py'), (Join-Path $work "branchctl-$m.sqlite"), $wfNoPlan, $m) "d7ctl-$m.out"
    $ln = ($r.out -split "`n" | Where-Object { $_ -match '^SESSION-STATE' }) -join ''
    $d7rows += [pscustomobject]@{ mode = ($m + ' [REVERTED]'); line = $ln; busy = (BusyField $ln) }
}

$byMode = @{}
foreach ($x in $d7rows) { $byMode[$x.mode] = $x.busy }
Arm 'D7-idle-status-but-turn-lease-held-takes-the-QUEUE-path' `
    ($byMode['lease'] -eq 'YES') `
    ("store says status=idle with a turn lease held and NOTHING else -- the measured refusal state, tested with the PRIMARY signal alone: busy={0}. {1}" -f $byMode['lease'], $byMode['lease'] + '')
Arm 'D7-open-turn-alone-also-marks-busy' `
    ($byMode['openturn'] -eq 'YES') `
    ("no lease, one open turn 1 min old: busy={0} (the SECONDARY signal, bounded at 45 min)" -f $byMode['openturn'])
Arm 'D7-a-stuck-open-turn-cannot-wedge-the-channel' `
    ($byMode['stuck'] -eq 'NO') `
    ("no lease, one open turn 90 min old (older than the 45 min bound): busy={0}. This is the anti-wedge property -- an unfinished turn row must not hold the wake channel for ever, which is the D-3 defect class." -f $byMode['stuck'])
Arm 'D7-control-branching-on-status-reverted-goes-RED' `
    (($byMode['lease [REVERTED]'] -eq 'NO') -and ($byMode['lease'] -eq 'YES')) `
    ("CURE REVERTED IN A COPY (branch on sessions.status, exactly as before). On the lease-only store -- the MEASURED refusal state -- the live arm says busy={0} and the reverted copy says busy={1}: the defect, reproduced. On the open-turn store the reverted copy still says busy={2}, because the revert removes the lease as a PRIMARY signal but leaves the secondary one intact; that store is what arm D7-open-turn-alone covers. This control can no longer pass on a substring." -f $byMode['lease'], $byMode['lease [REVERTED]'], $byMode['openturn [REVERTED]'])

# -------------------------------------------------------------- D-6 counter
Write-Host ''
Write-Host '--- D-6  the shutdown counter is instrumented, not described ---'

# Run the REAL heartbeat.ps1 against a stub `mcode`, on a throwaway store and a
# throwaway _mainDir, so the live log and the live counters are not touched.
$hbWork = Join-Path $work 'hb'
New-Item -ItemType Directory -Path $hbWork -Force | Out-Null
Copy-Item (Join-Path $mainDir 'ORCHESTRATOR-PROMPT.md') (Join-Path $hbWork 'ORCHESTRATOR-PROMPT.md') -Force
# $mainDir also relocates $fixPy (it is Join-Path $mainDir 'wake-fix.py'), so the
# copy has to bring the python with it -- the first version of this arm aborted
# with "can't open file ...\hb\wake-fix.py" and reported exec_passes=0.
Copy-Item $wf (Join-Path $hbWork 'wake-fix.py') -Force
$hbCopy = New-Revert $hb (Join-Path $hbWork 'heartbeat.ps1') `
    "`$mainDir   = Join-Path `$root '_main'" `
    ("`$mainDir   = '" + $hbWork + "'") `
    'D6-redirect-mainDir-for-the-test'
# ...and the target session must exist in the synthetic store, or wake-plan
# answers NO-SUCH-SESSION and the pass aborts before the counter runs.
$hbCopy = New-Revert $hbCopy $hbCopy `
    "`$TARGET_SESSION = 'mvs_a00662bff55242cb9b56c0f1165bdad7'" `
    "`$TARGET_SESSION = 'mvs_lane24hb00000000000000000000000'" `
    'D6-target-session-for-the-test'
# a stub that produces the exact shutdown string and fails, like the real one
Set-Content -Path (Join-Path $work 'bin\mcode.cmd') -Encoding ascii -Value @(
    '@echo off',
    'echo [minimax-code] embedded Runtime cleanup failed: Runtime shutdown deadline exceeded after 60000ms',
    'echo Session already has an active Turn. Use queue send to deliver the message after it.',
    'exit /b 4') -NoNewline

$hbStore = Join-Path $work 'hb-store.sqlite'
$hbStorePy = @'
import sqlite3, sys, time
db = sys.argv[1]; NOW = int(time.time() * 1000)
c = sqlite3.connect(db)
c.execute("create table local_runtime_sessions (session_id text primary key, status text, workspace_dir text, updated_at_ms integer)")
c.execute("insert into local_runtime_sessions values ('mvs_lane24hb00000000000000000000000','idle','H:\\sotto',?)", (NOW,))
c.execute("create table local_runtime_session_locks (session_id text, owner_id text, owner_kind text, acquired_at_ms integer, expires_at_ms integer)")
c.execute("create table local_runtime_turn_ingress (turn_id text primary key, session_id text, source text, client_request_id text, claim_id text, claim_source text, queue_item_ids_json text, input_json text, status text, accepted_at_ms integer, accepted_sequence integer, completed_at_ms integer, queue_acknowledged_at_ms integer, input_digest text, input_metadata_json text)")
c.execute("create table local_runtime_queue_items (id integer primary key, session_id text, item_id text, status text, created_at_ms integer, data_json text, source text, client_request_id text, dedupe_key text, expires_at_ms integer, claim_id text, claim_lease_expires_at_ms integer, routing_fingerprint text)")
c.execute("create table local_runtime_v2_cron_runs (cron_id text, trigger_source text, status text, session_id text, created_at_ms integer)")
c.execute("create table local_runtime_v2_cron_definitions (cron_id text, scheduler_id text, name text, target_session_id text, session_target_mode text, deleted_at_ms integer)")
c.execute("create table local_runtime_v2_scheduler_jobs (scheduler_id text, state text, next_run_at_ms integer)")
c.commit(); c.close()
'@
Set-Content -Path (Join-Path $work 'hbstore.py') -Value $hbStorePy -Encoding utf8NoBOM
$r = RunNative 'py' @('-3', (Join-Path $work 'hbstore.py'), $hbStore) 'd6-store.out'

$oldPath = $env:PATH
$env:PATH = (Join-Path $work 'bin') + ';' + $oldPath
$env:SOTTO_WAKE_DB = $hbStore
$hbRun = Join-Path $work 'hb-run.log'
& pwsh -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File $hbCopy > $hbRun 2>&1
$hbRc = $LASTEXITCODE
$env:PATH = $oldPath
Remove-Item Env:SOTTO_WAKE_DB

$countersPath = Join-Path $hbWork 'wake-counters.json'
$counterLine = ''
if (Test-Path $countersPath) { $counterLine = (Get-Content $countersPath -Raw).Trim() }
$passes = 0; $deads = 0
if ($counterLine -match '"passes":\s*(\d+)') { $passes = [int]$Matches[1] }
if ($counterLine -match '"shutdown_deadline":\s*(\d+)') { $deads = [int]$Matches[1] }
Arm 'D6-shutdown-deadline-counter-is-instrumented' `
    ($hbRc -eq 0 -and $passes -ge 1 -and $deads -ge 1) `
    ("the REAL heartbeat.ps1 ran against a stub mcode that emits the shutdown string: exec_passes={0} shutdown_deadline={1} ({2}). N={0} is the real denominator -- a rate over N<20 is not a rate, and this lane does NOT claim one." -f $passes, $deads, $counterLine)

# ---------------------------------------------------------- delivery proof
Write-Host ''
Write-Host '--- delivery: the authoritative link, never a marker ---'

$r = RunNative 'py' @('-3', $cd, 'mvs_b7a9f3a7db404912b32d28fc11b83645', '0', 'msg-user-v1-wake') 'delivery.out'
$linked = 0; $linkedOf = 0
if ($r.out -match 'DELIVERED_BY_QUEUE = (\d+)/(\d+)') { $linked = [int]$Matches[1]; $linkedOf = [int]$Matches[2] }
Arm 'A1-queue-linked-delivery-proven-by-turn-ingress' `
    ($r.rc -eq 0 -and $linked -ge 1) `
    ("DELIVERED_BY_QUEUE = {0}/{1}. Proof = turn_ingress.queue_item_ids_json names the item AND queue_acknowledged_at_ms is set AND a role='user' row in the same session carries that turn_id. Three runtime tables joined by runtime-written identifiers." -f $linked, $linkedOf)

$unlinked = 0
if ($r.out -match 'of which NOT queue-linked = (\d+)') { $unlinked = [int]$Matches[1] }
$saysNo = ($r.out -match 'MARKER_MATCHES_ARE_NOT_PROOF')
Arm 'A2-control-textsearch-would-lie' `
    ($r.rc -eq 0 -and $unlinked -ge 1 -and $saysNo) `
    ("CONTROL: {0} role='user' marker hit(s) are NOT queue-linked -- they carry turn_id NULL and have no turn_ingress row, because a hand-pushed `mcode exec --session` produced them. A text search credits them to the queue. The checker prints MARKER_MATCHES_ARE_NOT_PROOF so the distinction cannot be lost again." -f $unlinked)

# A doctored store: the marker matches, nothing is linked.  A marker-grep
# would report a delivery here; the real check must report none.
$docPy = @'
import os, sqlite3, sys
db = sys.argv[1]
if os.path.exists(db): os.remove(db)
c = sqlite3.connect(db)
c.execute("create table local_runtime_queue_items (id integer primary key, session_id text, item_id text, status text, created_at_ms integer, data_json text, source text, client_request_id text, dedupe_key text, expires_at_ms integer, claim_id text, claim_lease_expires_at_ms integer, routing_fingerprint text)")
c.execute("create table local_runtime_message_rows (id integer primary key, session_id text, role text, source text, created_at_ms integer, data_json text)")
c.execute("create table local_runtime_turn_ingress (turn_id text primary key, session_id text, source text, client_request_id text, claim_id text, claim_source text, queue_item_ids_json text, input_json text, status text, accepted_at_ms integer, accepted_sequence integer, completed_at_ms integer, queue_acknowledged_at_ms integer, input_digest text, input_metadata_json text)")
c.execute("create table local_runtime_v2_cron_runs (cron_id text, trigger_source text, status text, session_id text, created_at_ms integer)")
c.execute("create table local_runtime_v2_cron_definitions (cron_id text, scheduler_id text, name text, target_session_id text, session_target_mode text, deleted_at_ms integer)")
c.execute("create table local_runtime_v2_scheduler_jobs (scheduler_id text, state text, next_run_at_ms integer)")
c.execute("insert into local_runtime_message_rows (session_id,role,source,data_json) values (?,?,?,?)",
          ("mvs_doc", "user", "api", '{"msg_id":"msg-user-v1-wake0123456789abcdef0123456789abcdef01234567","msg_content":"ORCHESTRATOR MANDATE","turn_id":null}'))
c.commit(); c.close()
'@
Set-Content -Path (Join-Path $work 'doc.py') -Value $docPy -Encoding utf8NoBOM
$r = RunNative 'py' @('-3', (Join-Path $work 'doc.py'), (Join-Path $work 'doc.sqlite')) 'a3-doc.out'
$docDb = Join-Path $work 'doc.sqlite'
$rd = RunNative 'py' @('-3', $cd, 'mvs_doc', '0', 'ORCHESTRATOR MANDATE', '--db', $docDb) 'a3-doctored.out'
$dlinked = 0; $dlinkedOf = 0
if ($rd.out -match 'DELIVERED_BY_QUEUE = (\d+)/(\d+)') { $dlinked = [int]$Matches[1]; $dlinkedOf = [int]$Matches[2] }
$dmarker = 0
if ($rd.out -match 'marker hits = (\d+)') { $dmarker = [int]$Matches[1] }
Arm 'A3-doctored-store-marker-matches-but-nothing-is-linked' `
    ($rd.rc -eq 0 -and $dmarker -ge 1 -and $dlinked -eq 0) `
    ("a store where the marker matches {0} role='user' row and NO turn names it: DELIVERED_BY_QUEUE = {1}/{2}. An instrument that grepped for the marker would have reported a delivery here. This arm is the direct test of the trap receipt-21 caught." -f $dmarker, $dlinked, $dlinkedOf)

# ---------------------------------------------------------------- window
Write-Host ''
Write-Host '--- window census (hard rule 1) ---'
Add-Type -Namespace Win -Name U -MemberDefinition @'
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
[DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
'@
$samples = 0; $visible = 0
$myPid = $PID
for ($i = 0; $i -lt 40; $i++) {
    Get-CimInstance Win32_Process -Filter "ParentProcessId=$myPid" -ErrorAction SilentlyContinue | ForEach-Object {
        $samples++
        $p = Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue
        if ($p -and $p.MainWindowHandle -ne 0) {
            if ([Win.U]::IsWindowVisible($p.MainWindowHandle)) { $visible++ }
        }
    }
    Start-Sleep -Milliseconds 25
}
Arm 'X1-no-visible-window-from-this-gate' `
    ($visible -eq 0) `
    ("census of this gate's own child processes: {0} samples at 25 ms, {1} with a visible main window. The house 60 s census cannot see a short-lived window, so this samples at its own cadence." -f $samples, $visible)

# ------------------------------------------------- the two inherited fixes
Write-Host ''
Write-Host '--- the two fixes from other lanes that must survive ---'
$hbTxt = Get-Content $hb -Raw
$stdinOk = ($hbTxt -match '--input\s+-') -and ($hbTxt -notmatch '--prompt\s+\$prompt')
Arm 'X2-multiline-prompt-goes-over-stdin-not-argv' `
    $stdinOk `
    ("heartbeat.ps1 uses `--input -` and never passes the prompt as an argument. MEASURED 12:52:38 rc=1: 'too many arguments for exec. Expected 1 argument but got 19' -- a 3954-char multi-line argv does not survive the mcode.ps1 wrapper.")

$planOk = ($hbTxt -match 'wake-plan') -and ($hbTxt -match 'FALLBACK')
Arm 'X3-driver-branches-on-wake-plan-and-falls-back-to-queue' `
    $planOk `
    ("heartbeat.ps1 calls wake-plan (the measured predicate) AND falls back to the queue transport when exec is refused with 'already has an active Turn'. A pre-flight read is a heuristic; the refusal is the fact.")

# ---------------------------------------------------------------- verdict
$red = @($script:arms | Where-Object { -not $_.ok })
$controls = @($script:arms | Where-Object { $_.name -match 'control' })
Write-Host ''
Write-Host ('=== ARMS {0}  CONTROLS {1}  RED {2} ===' -f $script:arms.Count, $controls.Count, $red.Count)
if ($red.Count -gt 0) {
    Write-Host 'LANE24-GATE FAIL — RED arms:'
    $red | ForEach-Object { Write-Host ("  - {0}: {1}" -f $_.name, $_.detail) }
} else {
    Write-Host 'LANE24-GATE PASS'
}
# The result file is built as an explicit array and passed with -Value.
# The first version piped a { ... } block into Set-Content and, MEASURED on
# this pwsh, that wrote the block's own SOURCE TEXT (529 bytes of script) into
# the result file instead of the report.  A gate whose artefact is unreadable
# is not evidence.
$report = @(
    ("LANE24-GATE " + $(if ($red.Count -gt 0) { 'FAIL' } else { 'PASS' }))
    ("arms={0} controls={1} red={2}" -f $script:arms.Count, $controls.Count, $red.Count)
    ("heartbeat.ps1 sha=" + (Get-FileHash $hb -Algorithm SHA256).Hash)
    ("wake-fix.py   sha=" + (Get-FileHash $wf -Algorithm SHA256).Hash)
    ("check-deliv   sha=" + (Get-FileHash $cd -Algorithm SHA256).Hash)
    ("utc=" + [DateTime]::UtcNow.ToString('o'))
    ''
)
foreach ($a in $script:arms) {
    $report += ("{0}`t{1}`t{2}" -f $(if ($a.ok) { 'PASS' } else { 'RED' }), $a.name, $a.detail)
}
Set-Content -Path $outFile -Value $report -Encoding utf8NoBOM
Write-Host ("result file: {0}" -f $outFile)
exit $(if ($red.Count -gt 0) { 1 } else { 0 })