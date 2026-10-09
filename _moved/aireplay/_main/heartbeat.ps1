# SO REPLAY HEARTBEAT - driver v6.
#
# ============================================================================
# v6 EXISTS FOR ONE REASON: THE WAKE WAS LANDING EVERY ~5 MIN, NOT EVERY 3.
#
# THE MECHANISM, MEASURED (not inferred) -- receipt-33, POPULATION = 6
# complete passes, WINDOW = 13:04:03 -> 13:28:02 BRT on 2026-10-07:
#
#   pass fired   pass wall time   >180 s?   overran its own next tick?  next actual fire
#   13:04:03     156 s             no        no                       13:07:05
#   13:07:05     229 s             YES       YES                      13:13:02  <- 13:10 DROPPED
#   13:13:02      98 s             no        no                       13:16:02
#   13:16:02     185 s             YES       YES                      13:22:01  <- 13:19 DROPPED
#   13:22:01     131 s             no        no                       13:25:03
#   13:25:03     162 s             no        no                       13:28:02
#
#   predicate: a scheduled tick is DROPPED iff the previous pass was still
#   running at that instant. 6 of 6 correct, and the two drops are exactly the
#   two passes longer than the 180 s interval.
#
# WHY THE TICK IS DROPPED RATHER THAN QUEUED, measured on the task itself:
#     (Get-ScheduledTask SottoReplayHeartbeat).Settings
#         .MultipleInstances  = IgnoreNew
#         .StartWhenAvailable = False
#     .Triggers[0].Repetition.Interval = PT3M
#   IgnoreNew means "a tick that arrives while an instance is running is
#   DISCARDED, not deferred and not run in parallel". StartWhenAvailable=False
#   means the dropped tick is not made up later. So the miss leaves NO log line
#   at all -- the driver cannot even see the tick it lost, which is why the
#   defect read as an unexplained ~5 minute cadence for hours.
#
# THE FIX: THE PASS MUST NOT OUTLIVE THE INTERVAL. `mcode exec` takes 98-229 s
# because it runs a whole agent turn; that is not negotiable and is not the bug.
# The bug is that the DRIVER WAITS FOR IT. So the exec is DETACHED: the driver
# enqueues it as a child process and returns in ~1 s, which takes the pass wall
# time from ~180 s to ~1 s and removes the overlap entirely. Nothing is skipped
# any more because nothing is still running when the next tick arrives.
#
# THE CHILD IS THE SAME FILE (`-ChildExec`). It owns everything that used to
# happen after the exec returned: the stdout capture, the four-bucket
# classification, the D-6 counters, the D-7 queue fallback, and the in-flight
# marker's removal. The parent owns the scheduling-critical prefix only:
# cron-alarm, wake-plan, prune. Those three are milliseconds, and PRUNE is
# UNCHANGED and still runs exactly once per pass.
#
# THE CHILD MUST NEVER BE A WINDOW. It is started with CreateNoWindow=$true
# plus WindowStyle=Hidden, which is CREATE_NO_WINDOW (0x08000000) -- the flag
# this project already paid for twice in visible consoles.
#
# ============================================================================
# v5 applied the six defects of receipt-21 (audit) in one place. The runtime
# cron alarm is ONE wire for two of them, on purpose:
#   D-1 mint shape        -> wake-fix.py mint_user_message_id()
#   D-2 broken cron LIKE -> wake-fix.py cron_fields() (count fields, not stars)
#   D-3 dedupe wedge      -> wake-fix.py split_pending() + the BLOCKING log line
#   D-4 no dead-cron alarm-> wake-fix.py cmd_cron_alarm, called every fire below
#   D-5 orphan rows       -> --all-sessions sweep with a 60 min foreign floor
#   D-6 shutdown deadline -> PASS-SHUTDOWN-COUNTER, counted not described
#   D-7 wrong predictor    -> wake-plan (lease / bounded open turn) + a QUEUE
#                             FALLBACK whenever exec is refused anyway
# TWO THINGS THIS FILE MUST KEEP (they are other lanes' fixes, not mine):
#   * the prompt goes over STDIN via `--input -`. A 3954-char multi-line argv
#     does not survive the mcode.ps1 wrapper (measured rc=1, 12:52:38).
#   * the status/workspace branch: a 'started' session QUEUES and is not
#     pruned; an 'idle' session prunes then execs.
# ============================================================================
# v4 REPLACES THE SQLITE INJECTION BECAUSE IT WAS MEASURED NOT TO DELIVER.
#
# WHAT WAS MEASURED (read-only, POPULATION = whole queue table):
#   A row written into local_runtime_queue_items for a LIVE session sat at
#   status='queued', claim_id=NULL for 6+ minutes, and produced ZERO new
#   role='user' rows. The runtime DOES read that table -- it answered with
#   "Queue row is corrupt: <session>/<item>" naming our own item -- but it
#   VALIDATES without CONSUMING. Writing the row is not waking the agent.
#
# SO: the channel is wrong, not the shape. (The shape still had to be fixed --
# see v3 -- but a correct shape in a table nobody drains wakes nobody.)
#
# THE DOOR THAT EXISTS: `mcode exec --session <id>` -- "run in an existing
# active Session". That is a prompt delivered into a named session, which is
# what the owner asked for: "nao e pro cronjob criar sessao nova, e pra ele
# injetar mensagem em voce, tipo um usuario".
#
# SEMANTICS THIS PRODUCES, and they are the ones we want:
#   * owner/session idle  -> the turn starts -> the agent is woken
#   * turn already active -> the runtime refuses (it told us so itself:
#     "Session already has an active Turn") -> this fire is a correct NO-OP
# A cron that no-ops while the agent is already working is healthy. A cron
# that stacks a second prompt on a live turn is a defect.
#
# THE SECOND DOOR (independent, and proven): wake-loop.py. It exits on an
# event, and a background task exiting RESUMES the owning conversation. That
# is the floor: even if every path in this file fails, a running subagent
# returning brings the orchestrator back.
# ============================================================================

param(
    # v6: the detached half of the pass. Same file, one switch, so the exec
    # policy and the scheduling policy cannot drift apart in two files.
    [switch]$ChildExec,
    [string]$ChildWorkspace = ''
)

$ErrorActionPreference = 'Continue'
$root      = 'H:\sotto\_moved\aireplay'
$mainDir   = Join-Path $root '_main'
$lockFile  = Join-Path $mainDir 'heartbeat.lock'
$execLock  = Join-Path $mainDir 'heartbeat-exec.lock'
$logFile   = Join-Path $mainDir 'heartbeat.log'
$inflight  = Join-Path $mainDir 'wake-inflight.txt'
$promptMd  = Join-Path $mainDir 'ORCHESTRATOR-PROMPT.md'
$outFile   = Join-Path $mainDir 'heartbeat-exec-output.txt'
$fixPy     = Join-Path $mainDir 'wake-fix.py'
$counters  = Join-Path $mainDir 'wake-counters.json'

# The session to wake. THIS IS THE ONLY LINE THAT DECIDES WHOSE SESSION GETS
# THE MESSAGE.
$TARGET_SESSION = 'mvs_a00662bff55242cb9b56c0f1165bdad7'

# v6: the wall-clock clock for THIS pass, started before anything else runs.
# (Get-Process -Id $PID).StartTime is when the scheduler created this pwsh, so
# it is a MEASUREMENT of the task-fire instant, not an inference from a log
# line. Everything below is relative to it, which is what makes pass duration
# comparable across passes.
$passStart = (Get-Process -Id $PID).StartTime
$swPass    = [System.Diagnostics.Stopwatch]::StartNew()

function Ms($sw) { [int][Math]::Round($sw.Elapsed.TotalMilliseconds) }

# --- D-6: make a rate measurable instead of asserting one -------------------
# The audit saw "Runtime shutdown deadline exceeded after 60000ms" N=1 and
# refused to call it a rate because 20 passes is ~60 minutes.  So this file no
# longer leaves the rate to a reader: every pass counts itself, and every pass
# that sees the string counts it, in a file that outlives the log rotation.
function Read-Counters {
    if (Test-Path $counters) {
        try { return (Get-Content $counters -Raw -Encoding UTF8 | ConvertFrom-Json) }
        catch { Write-Verbose "counters unreadable: $($_.Exception.Message)" }
    }
    return [pscustomobject]@{ passes = 0; shutdown_deadline = 0; first_pass_utc = $null }
}
function Save-Counters($c) {
    try { $c | ConvertTo-Json -Compress | Set-Content -Path $counters -Encoding UTF8 }
    catch { Log ("COUNTER-WRITE-FAILED " + $_.Exception.Message) }
}

# v6: the log now has TWO writers -- the driver (milliseconds, then gone) and
# the detached exec child (up to 12 min later). Add-Content opens, writes and
# closes, and two processes doing that inside the same few milliseconds can
# collide. A dropped or truncated cadence line would be indistinguishable from
# a missing pass, which is precisely the class of error this lane exists to
# kill, so Log retries instead of losing the evidence.
function Log($msg) {
    $line = ("[{0}] {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $msg)
    for ($i = 1; $i -le 5; $i++) {
        try {
            Add-Content -Path $logFile -Value $line -Encoding UTF8 -ErrorAction Stop
            return
        } catch {
            Start-Sleep -Milliseconds (40 * $i)
        }
    }
}

# The session's own workspace_dir. The CHILD receives it from the parent
# because the child cannot re-read the plan cheaply and must not re-run it:
# re-planning in the child would be a second, racing read of the same turn
# lease. Absent (a hand-run child), fall back to the plan.
function Resolve-Workspace {
    param([string]$Given)
    if ($Given -match '^[A-Za-z]:\\') { return $Given }
    $o = & python $fixPy session-workspace --session $TARGET_SESSION 2>&1
    if ($LASTEXITCODE -eq 0) { return (($o | Select-Object -Last 1) -replace '\s+', ' ').Trim() }
    return $null
}

# ============================================================================
# THE QUEUE TRANSPORT, factored out of the busy branch.
#
# v6 moved the SECOND caller here. Two callers:
#   1. the plan said busy (a turn lease is held)  -- unchanged from v5;
#   2. a previous exec child is still running     -- NEW in v6.
#
# Caller 2 is the reason this function exists. Before v6 that case ended in
# `SKIP - a wake is already in flight` and the tick produced NOTHING, which is
# the same defect class as the Windows drop, just one layer down: a served tick
# that silently delivers no wake. Now a tick that cannot exec still leaves a
# durable row that the runtime drains at turn close (receipt-27: queue latency
# 2m56s). A tick is served or it is queued; it is never dropped.
# ============================================================================
function Invoke-QueueWake($reason) {
    $out = & python $fixPy inject --session $TARGET_SESSION `
        --fallback-session $TARGET_SESSION --text-file $promptMd `
        --stale-mins 999 2>&1
    $rc = $LASTEXITCODE
    $flat = (($out -join ' ') -replace '\s+', ' ').Trim()
    if ($rc -eq 0) {
        Log ('WAKE queued for after this turn ends rc=0 reason=' + $reason + ' -> ' + $TARGET_SESSION + ' :: ' + $flat)
    } elseif ($rc -eq 2) {
        # D-3: NAME the blocker. The old line was the fixed string
        # 'WAKE already queued (rc=2) - not stacking', which was read as
        # healthy for six consecutive fires (12:07 -> 12:19, 12 minutes)
        # because it looked exactly like a success. wake-fix.py now prints
        # one BLOCKING line per row with item_id, age, claim and expiry.
        Log ('WAKE refused rc=2 (queued and not stacking) reason=' + $reason + ' :: ' + $flat)
    } else {
        Log ('WAKE QUEUE FAILED rc=' + $rc + ' reason=' + $reason + ' :: ' + $flat)
    }
    return $rc
}

# ============================================================================
# CHILD MODE: everything after the exec returns.
# ============================================================================
if ($ChildExec) {
    $childLock = $null
    try {
        $childLock = [System.IO.File]::Open($execLock,
            [System.IO.FileMode]::OpenOrCreate,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None)
    } catch {
        Log 'EXEC-CHILD skipped - another exec child holds heartbeat-exec.lock'
        exit 0
    }
    try {
        $WORKSPACE = Resolve-Workspace -Given $ChildWorkspace
        if ($WORKSPACE -notmatch '^[A-Za-z]:\\') {
            Log ('EXEC-CHILD abort: no workspace (got: ' + $ChildWorkspace + ')')
            exit 1
        }
        $swExec = [System.Diagnostics.Stopwatch]::StartNew()
        Log ('EXEC-CHILD-START fire=' + $passStart.ToString('HH:mm:ss') +
             ' workspace=' + $WORKSPACE + ' target=' + $TARGET_SESSION)
        Log 'EXEC-PRE ts_pre_exec'

        # MEASURED 12:52:38, rc=1: "too many arguments for 'exec'. Expected 1
        # argument but got 19." A 3954-char multi-line prompt does NOT survive
        # argv: the mcode.ps1 wrapper re-splits it on whitespace. The prompt
        # goes in over STDIN via --input -, never as an argument. (Piping INPUT
        # into a command is safe; the hard rule is about piping a native
        # command's OUTPUT, which closes the pipe early and hides the real exit
        # code.)
        Get-Content $promptMd -Raw -Encoding UTF8 |
            & mcode exec --session $TARGET_SESSION --cwd $WORKSPACE --permission off `
                --input - --timeout 12m `
                --output-last-message (Join-Path $mainDir 'wake-last-message.md') `
                > $outFile 2>&1
        $rc = $LASTEXITCODE
        $execMs = Ms $swExec
        Log ('EXEC-POST ts_post_exec rc=' + $rc + ' exec_ms=' + $execMs)

        # CLASSIFY BY THE WHOLE OUTPUT, NOT ITS FIRST LINES, AND NOT BY rc
        # ALONE. MEASURED 12:34: the four leading lines were four "Runtime
        # shutdown deadline exceeded after 60000ms" warnings and the actual
        # reason was LINE 5 ("Session already has an active Turn"). Reading
        # only the head made the driver report the WRONG CAUSE, and a wrong
        # cause is worse than none, because it sends you to fix the wrong thing.
        $body = ''
        if (Test-Path $outFile) { $body = ((Get-Content $outFile -Encoding UTF8) -join ' ') }
        $show = $body.Substring(0, [Math]::Min(300, $body.Length))

        # --- D-6: COUNT IT, do not describe it. ---------------------------------
        $c = Read-Counters
        $c.passes = [int]$c.passes + 1
        if (-not $c.first_pass_utc) {
            $c.first_pass_utc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        }
        $thisPassDeadline = ($body -match 'shutdown deadline exceeded')
        if ($thisPassDeadline) { $c.shutdown_deadline = [int]$c.shutdown_deadline + 1 }
        Save-Counters $c
        $rate = if ([int]$c.passes -gt 0) {
            '{0:P1}' -f ([double]$c.shutdown_deadline / [double]$c.passes)
        } else { 'n/a' }
        Log ('PASS-SHUTDOWN-COUNTER exec_passes=' + $c.passes +
            ' shutdown_deadline=' + $c.shutdown_deadline +
            ' this_pass=' + $(if ($thisPassDeadline) { 1 } else { 0 }) +
            ' rate=' + $rate +
            ' first_exec_utc=' + $c.first_pass_utc +
            ' (denominator = passes that actually ran mcode exec; rate over N<20 is not a rate)')

        if ($rc -eq 0) {
            Log ('WAKE delivered rc=0 -> ' + $TARGET_SESSION + ' :: ' + $show)
        } else {
            # Four buckets, matched ANYWHERE in the body, most specific first.
            $kind = 'UNKNOWN'
            if ($body -match 'already has an active Turn') {
                $kind = 'REFUSED-BUSY (the plan said not-busy; the runtime disagrees -- falling back to the queue)'
            } elseif ($body -match 'An earlier queued message has priority') {
                $kind = 'BLOCKED-BY-STALE-QUEUE (prune should have cleared this - it is not keeping up)'
            } elseif ($body -match 'workspace does not match') {
                $kind = 'WORKSPACE-MISMATCH (the session moved - re-read its workspace_dir)'
            } elseif ($body -match 'shutdown deadline exceeded') {
                $kind = 'SHUTDOWN-NOISE (only meaningful when no other bucket matched)'
            }
            Log ('WAKE rc=' + $rc + ' kind=' + $kind + ' :: ' + $show)

            # --- D-7 BELT: the refusal is the FACT, the plan is only a heuristic.
            # Measured POP = 2 of 2: status said 'idle' and exec was refused
            # anyway.  Any pre-flight read can miss a turn that starts between the
            # read and the exec, so when the runtime refuses for exactly this
            # reason we take the transport IT names (the queue) in the SAME pass
            # instead of burning the fire.
            if ($body -match 'already has an active Turn') {
                Log 'FALLBACK: exec refused for an active turn -> queue transport (named by the runtime itself)'
                [void](Invoke-QueueWake 'exec-refused-active-turn')
            }
        }
        Log ('EXEC-CHILD-END exec_ms=' + $execMs + ' child_wall_ms=' + (Ms $swPass))
        exit 0
    }
    catch {
        Log ('EXEC-CHILD ERROR: ' + $_.Exception.Message)
        exit 1
    }
    finally {
        # The marker was written by the PARENT at spawn. Only the child may
        # clear it -- if the parent cleared it on its way out, the next tick
        # would spawn a second exec on top of this one.
        if (Test-Path $inflight) { Remove-Item $inflight -Force -ErrorAction SilentlyContinue }
        if ($childLock) { $childLock.Close(); $childLock.Dispose() }
    }
}

# ============================================================================
# PARENT MODE: the scheduling-critical prefix. Every statement here must be
# milliseconds, because this process's lifetime IS the overlap window.
# ============================================================================

# --- exclusive handle lock (proved by _hb-lock-selftest.ps1) ---
$lock = $null
try {
    $lock = [System.IO.File]::Open($lockFile,
        [System.IO.FileMode]::OpenOrCreate,
        [System.IO.FileAccess]::ReadWrite,
        [System.IO.FileShare]::None)
} catch {
    # The fire timestamp is IN this line on purpose. The pass being unable to
    # take the lock, and the scheduler never firing at all, look identical from
    # the outside -- both are a missing pass. Only this line tells them apart:
    # if a 180 s slot has no TASK-FIRE and no SKIP either, Windows discarded the
    # trigger (MultipleInstances=IgnoreNew), which is the defect v6 removed.
    Log ('SKIP - a previous wake pass still holds the lock fire=' + $passStart.ToString('yyyy-MM-dd HH:mm:ss') + ' pid=' + $PID)
    exit 0
}

# v6: one line per pass that a reader can diff across passes. TASK-FIRE is the
# scheduler's own fire instant (this process's creation time); the other two
# bracket the scheduling-critical prefix. If TASK-FIRE stops advancing by 180 s
# the drop is back and this file says so without anyone re-deriving it.
Log ('TASK-FIRE fire=' + $passStart.ToString('yyyy-MM-dd HH:mm:ss') +
     ' mode=parent pid=' + $PID +
     ' schedule_interval_s=180 multiple_instances=IgnoreNew (measured by cadence-probe.py)')

$spawned = $false
try {
    if (-not (Test-Path $promptMd)) { Log ('MISSING ' + $promptMd); exit 0 }

    # --- D-2 + D-4: THE cron alarm, once per fire, before anything else ------
    # One alarm, not two: D-2 (the status query that matched nothing) and D-4
    # (nothing alarmed on a dead scheduler) are the same missing wire.  It is
    # read from the STORE every fire, never inferred from a log line, because
    # the previous cron observability was a status line whose LIKE pattern
    # matched 0 of 30 scheduler jobs -- which printed an empty cron section and
    # read as "no crons configured" through a 26.7 h outage.
    $alarmOut = (& python $fixPy cron-alarm 2>&1)
    $alarmRc = $LASTEXITCODE
    Log ('CRON-ALARM rc=' + $alarmRc + ' :: ' + (($alarmOut -join ' ') -replace '\s+', ' ').Trim())
    if ($alarmRc -eq 3) {
        Log 'WARNING: the runtime cron scheduler is dead. The owner is NOT being woken by the runtime own cron; only this Windows task is still firing.'
    }

    # --- STEP 0: D-7.  ASK WHICH TRANSPORT, DO NOT INFER IT FROM status -----
    # `local_runtime_sessions.status` IS NOT A PREDICTOR of exec acceptance.
    # MEASURED, POP = 2 refusals (13:05:05 and 13:08:59, both rc=4, both with
    # the runtime's own "Session already has an active Turn. Use queue send to
    # deliver the message after it."): the store said 'idle' at BOTH, while a
    # turn was open at both.  status was a false negative on 2 of 2.
    # And it fails the other way too: measured live while writing this, session
    # mvs_ea552229 reads status='aborted' with no turn and no lease -- status
    # says busy, nothing is running.
    #
    # wake-plan computes busy from the two signals that were measured: a held
    # turn lease (self-expiring: POP 10 lock rows store-wide, all with an
    # expiry, 0 expired) and an open turn BOUNDED at 45 min (p90 turn duration
    # is 41.8 min over POP 3743 completed turns; unbounded it would wedge).
    #
    # --cwd must equal the session's own workspace_dir either way.  Two
    # sessions on this box differ (H:\sotto, C:\Users\Administrador), so it is
    # read, never hardcoded.
    $info = & python $fixPy wake-plan --session $TARGET_SESSION 2>&1
    $infoRc = $LASTEXITCODE
    $stateLine = ($info | Where-Object { $_ -match '^SESSION-STATE ' }) -join ' '
    $wsLine = ($info | Where-Object { $_ -match '^WORKSPACE ' }) -join ' '
    $busy = 'UNKNOWN'
    $status = 'unknown'
    if ($stateLine -match 'status=([a-zA-Z_-]+)') { $status = $Matches[1] }
    if ($stateLine -match 'busy=(YES|NO)') { $busy = $Matches[1] }
    $WORKSPACE = ($wsLine -replace '^WORKSPACE\s+', '')
    if ($infoRc -ne 0 -or $busy -eq 'UNKNOWN' -or $WORKSPACE -notmatch '^[A-Za-z]:\\') {
        Log ('ABORT: could not compute the wake plan (rc=' + $infoRc + ', got: ' + ($info -join ' ') + ')')
        exit 1
    }
    Log ('WAKE-PLAN ' + $stateLine + ' workspace=' + $WORKSPACE)

    # --- STEP 0b: sweep orphans on BOTH paths -------------------------------
    # D-5.  --all-sessions, because the wedge predicate is keyed on session_id
    # and a session-scoped prune can never reach an orphan in another session.
    # MEASURED: queue_1dfd5c7c, session mvs_ea552229, unclaimed, aged
    # 959 -> 974 min over 5 samples, outlived the one logged PRUNE event.
    # SAFETY: this session's OWN rows are floored at --stale-mins.  On the busy
    # path that floor is 999 so the wake we are about to queue is never
    # deleted -- the bug the previous prune fix introduced -- while foreign
    # sessions are still floored at 60 min, so an orphan is swept even when the
    # target session is busy.
    # UNCHANGED BY v6: still exactly one prune per pass, still the same floors.
    $sweepStale = if ($busy -eq 'YES') { 999 } else { 3 }
    $pruneOut = (& python $fixPy prune --session $TARGET_SESSION --stale-mins $sweepStale `
        --all-sessions --orphan-min-mins 60 2>&1)
    $pruneRc = $LASTEXITCODE
    Log ('PRUNE rc=' + $pruneRc + ' all-sessions sweep_stale=' + $sweepStale +
        ' :: ' + (($pruneOut -join ' ') -replace '\s+', ' ').Trim())
    if ($pruneRc -ne 0) { Log 'ABORT: prune failed - refusing to send behind an unknown queue'; exit 1 }

    # --- STEP 1: a previous exec child is still running ---------------------
    # The marker is written by the parent AT SPAWN and cleared by the child.
    # A wake that has been running longer than the exec timeout is presumed
    # dead: the timeout is 12 min and we mark stale at 15.
    if (Test-Path $inflight) {
        $age = (Get-Date) - (Get-Item $inflight).CreationTime
        if ($age.TotalMinutes -lt 15) {
            # v5 logged `SKIP - a wake is already in flight` and stopped. That
            # made a SERVED tick deliver nothing, which is the same defect as
            # the Windows drop one layer down. v6 serves it through the queue
            # instead: the runtime drains the row when the turn closes.
            Log ('EXEC-INFLIGHT previous exec child still running (' + [int]$age.TotalMinutes + ' min old) -> this tick uses the queue transport, it is not dropped')
            [void](Invoke-QueueWake 'exec-child-inflight')
            exit 0
        }
        Log ('STALE inflight marker (' + [int]$age.TotalMinutes + ' min old) - clearing')
        Remove-Item $inflight -Force
    }

    if ($busy -eq 'YES') {
        # ---- BUSY: the queue is the transport, and the runtime names it ----
        # in the very error message it refuses exec with.
        [void](Invoke-QueueWake 'plan-busy')
        exit 0
    }

    # ---- NOT BUSY per the measured signals: DETACH the exec ----------------
    # The sweep already ran in STEP 0b, so no second prune here: two prunes in
    # one pass is how the previous version deleted its own pending wake.

    # Remove-then-create, not New-Item -Force: an existing file keeps its
    # CreationTime under -Force, and the age test above reads CreationTime.
    if (Test-Path $inflight) { Remove-Item $inflight -Force }
    New-Item -ItemType File -Path $inflight -Force | Out-Null

    $prompt = (Get-Content $promptMd -Raw -Encoding UTF8)
    Log ('WAKE sending -> session ' + $TARGET_SESSION + ' chars=' + $prompt.Length + ' transport=detached-exec')

    # --- THE DETACH -------------------------------------------------------
    # CreateNoWindow = true is CREATE_NO_WINDOW (0x08000000): the child gets no
    # console at all, so there is nothing to flash on the owner's screen. This
    # project has been shown two stray python consoles already.
    # UseShellExecute = false is required for CreateNoWindow to be honoured and
    # also keeps the child off the parent's console, which is what lets it
    # outlive the parent (which is the entire point -- the parent must exit
    # before the next 180 s tick).
    $pwshExe = Join-Path $PSHOME 'pwsh.exe'
    if (-not (Test-Path $pwshExe)) { $pwshExe = 'pwsh.exe' }
    $self = $MyInvocation.MyCommand.Path
    $childArgs = @(
        '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
        '-WindowStyle', 'Hidden',
        '-File', ('"' + $self + '"'),
        '-ChildExec',
        '-ChildWorkspace', ('"' + $WORKSPACE + '"')
    ) -join ' '
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $pwshExe
    $psi.Arguments = $childArgs
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
    $psi.WorkingDirectory = $mainDir
    $child = $null
    try {
        $child = [System.Diagnostics.Process]::Start($psi)
        $spawned = $true
        Log ('EXEC-DETACH child_pid=' + $child.Id + ' spawn_ms=' + (Ms $swPass) +
             ' create_no_window=True exe=' + $pwshExe)
    } catch {
        # The marker must not survive a spawn that never happened, or the next
        # three ticks would all queue behind a child that does not exist.
        Remove-Item $inflight -Force -ErrorAction SilentlyContinue
        Log ('EXEC-DETACH FAILED: ' + $_.Exception.Message +
             ' -- falling back to the queue transport in THIS pass')
        [void](Invoke-QueueWake 'detach-spawn-failed')
    }
}
catch {
    Log ('ERROR: ' + $_.Exception.Message)
}
finally {
    # v6: the in-flight marker now belongs to the child once it is spawned.
    # Clearing it here would let the next tick stack a second exec on top of a
    # running one, which is the exact stacking defect this marker exists for.
    if (-not $spawned -and (Test-Path $inflight)) {
        Remove-Item $inflight -Force -ErrorAction SilentlyContinue
    }
    if ($lock) { $lock.Close(); $lock.Dispose() }
    # headroom_ms is a MARGIN AGAINST IGNORENEW, and NOTHING in this file reads
    # it. pass_ms is the whole of this process's lifetime; the only thing that
    # acts on pass_ms > 180000 is Windows, which discards the next trigger
    # because an instance is still running. That external reaction is why v6
    # drives pass_ms under a second instead of trying to police it here.
    Log ('PASS-END fire=' + $passStart.ToString('HH:mm:ss') +
         ' pass_ms=' + (Ms $swPass) + ' spawned=' + $spawned +
         ' interval_s=180 headroom_ms=' + (180000 - (Ms $swPass)))
}