# ORCHESTRATOR STATE — read this FIRST on every wake

Written by the orchestrator at 2026-10-07 12:15 local. If you are reading this on a wake,
this file is your context. If it contradicts what you remember, the FILE wins — the
memory of a previous turn is not evidence.

---

## 1. What I am

I am the **orchestrator**. I dispatch; I do not implement. Goal: a complete NVIDIA
ShadowPlay clone as one integrated app under Sotto, frontend last.

Repo: `H:\sotto\_moved\aireplay` (git). Parent: `H:\sotto` (Sotto = transcription overlay).
`H:\aireplay` is a junction into the moved tree — do not delete it.

## 2. The doors that can wake me — MEASURED at 12:16-12:20

| door | measured state | evidence |
|---|---|---|
| **wake-loop.py watcher** | **WORKS, PROVEN END-TO-END** | armed 12:15:14, exited 12:16:14 on event E4 (the Windows task fired and `heartbeat.log` gained a WAKE line). Its exit RESUMED this conversation. This is the guaranteed floor. |
| **subagent completion** | **WORKS, proven** | 16 lanes dispatched; a background task finishing auto-resumes the owning conversation. Observed twice. |
| **`mcode exec --session <id>`** | **the real external door** | `mcode exec --help`: "run in an existing active Session". First attempt returned rc=4 `Session workspace does not match --cwd` — the command reaches the runtime, the WORKSPACE must equal the session's `workspace_dir`. |
| Windows task `SottoReplayHeartbeat` | fires, rc=0 | 12:04:01 · 12:07:02 · 12:10:03 · 12:13:03 · 12:14:33 · 12:16:0x |
| **SQLite queue injection** | **DOES NOT DELIVER — retired** | a row for a live session sat `status='queued'`, `claim_id=NULL` for **6+ minutes** and produced **0** new `role='user'` rows. The runtime VALIDATES that table (it named our item in `Queue row is corrupt`) but does not CONSUME it. |
| runtime's own cron scheduler | **DEAD in this process** | `local_runtime_v2_cron_runs` newest row = 2026-10-06 10:11. A probe cron armed for 12:07:51 produced **0 runs**. |

**Session facts — the `--cwd` MUST equal the session's `workspace_dir`:**

| session | workspace_dir | status | note |
|---|---|---|---|
| `mvs_b7a9f3a7db404912b32d28fc11b83645` (this one) | `H:\sotto` | `started` | the session the owner talks to me in |
| `mvs_a00662bff55242cb9b56c0f1165bdad7` | `C:\Users\Administrador` | `idle` | title: "Pesquisa e roadmap do clone do H:\aireplay" |

**Rule: never end a turn without (a) subagents running and (b) a wake-loop armed.**

### 2b. The scheduled fires, as logged (POPULATION = whole heartbeat.log)

```
12:22:04 WAKE sending -> mvs_b7a9f3a7... chars=3954
12:22:11 WAKE no-op rc=4 :: "Session already has an active Turn. Use queue send
          to deliver the message after it."
12:25:03 ABORT: could not read the target workspace (mode not yet registered)
12:28:03 TARGET mvs_b7a9f3a7... workspace=H:\sotto
12:28:03 PRUNE rc=0 :: PRUNED 3ee05a09 age=13.1min never claimed (backed up)
12:28:03 WAKE sending -> mvs_b7a9f3a7... chars=3954
```

Three things worth keeping:

1. **The no-op is the runtime's own semantics, not our invention.** rc=4 with *"Use
   queue send to deliver the message after it"* is what the cron SHOULD do when the agent
   is already working. A cron that stacks a second prompt on a live turn is a defect.
2. **The 12:25 ABORT is the guard working.** Driver v5 asked for a mode that did not exist
   yet (I edited the driver before registering the mode). It ABORTED instead of sending
   with a guessed workspace. A driver that falls back to a hardcoded `--cwd` would have
   sent to the wrong place silently.
3. **The delivery case under a SCHEDULE is the open measurement.** Manual delivery is
   proven (receipt-22, `role='user'` id=225419). Scheduled fires so far have been
   correct no-ops because the agent was awake. The delivering case is what happens the
   first time a fire lands while this turn is over — that is the loop closing.

## 3. THE LOOP — do not skip it

```
count live fleet
  if < 15  -> dispatch more lanes; let lanes delegate (each may spawn 3 children)
arm wake-loop.py (background, bounded secs)  -> ending it wakes me
end turn
on wake:
    what woke me?
      - subagent finished  -> dispatch its REVIEWER (verifier, edits nothing)
      - cron woke me       -> keep going
      - cron silent but lanes returned -> THE CRON IS BROKEN -> fix the cron
    dispatch fixes for everything the reviewers found
    every P0 / SELF-AUDIT item I report is a WORK ORDER -> dispatch it
    goto top
```

## 4. Fleet dispatched at 12:03–12:14 (16 lanes, 0 concurrency refusals)

| lane | owns | asks for |
|---|---|---|
| L1 TRIGGER | `src/capture/trigger.{h,cpp}`, `trigger_selftest.*` | the instant-replay hotkey that does not exist |
| L2 AUDIO | `src/capture/wasapi_audio.{h,cpp}` | WASAPI loopback, reuse `H:\sotto\worker\wasapi_loopback.py` |
| L3 RINGCAP | `src/capture/ring_buffer.{h,cpp}` | ring sized from RAM, not VRAM |
| L4 INDEX | `src/index/**` (was EMPTY) | the search index |
| L5 RESEARCH | `research/shadowplay-parity.md`, `open-source-alternatives.md` | the parity matrix, researched online |
| L6 SPEC04 | `specs/04-index-search.md` | the missing spec |
| L7 WINDOW | `src/capture/replay.*`, `test_window.*` | kill the hardcoded 1920x1080 |
| L8 INTEGRATION | `docs/integration-sotto-app.md`, `docs/overlay-hotkey-contract.md` | one app, everything under Sotto |
| L9 ASR | `src/asr/**` | ASR end-to-end on real audio, spec-compliant decode |
| L10 BATTERY | `src/capture/run_battery.ps1`, `probe-cap-*.ps1` | MEASURE what this box encodes |
| L11 ALLGATES | `_main/all-gates.ps1` | one honest command for the whole project |
| L12 DURABILITY | `_main/durability-gate.ps1` | prove no work can be lost |
| L13 HUD | `specs/05-overlay-hud.md` | the overlay HUD spec |
| L14 BROADCAST | `specs/06-broadcast-and-capture-card.md` | Broadcast + Capture Card |
| L15 HIGHLIGHTS | `specs/07-highlights.md` | automatic clip extraction, honestly scoped |
| L16 WAKE-AUDIT | `_main/_lane16-wake-gate.ps1`, receipt 21 | **audit this whole mechanism; edits nothing** |

Shared context + hard rules: `_main\LANE-BRIEF.md`. Every lane was told to dispatch its
own verifier and to report its verdict verbatim.

## 5. Mistakes already made today — do not repeat them

1. **Injected a malformed queue row.** It produced `Queue row is corrupt` AND it sat
   ahead of the owner's own real message, killing that session's continuation. Repaired
   12:06:02. **The runtime DOES read the queue** — the earlier claim "nothing consumes
   it" was wrong.
2. **Reported "end-to-end" after an INSERT.** Inserting a row is not delivering it.
   Delivery is proven only by a new `role='user'` message row.
3. **Counted 95 HEARTBEAT messages that were my own report text.** An instrument that
   matches its own output proves nothing. Twice today now. Always filter `role='user'`.
4. **Told the owner the cron needed a session restart** before checking whether the
   queue was even consumed.
5. A `write` was refused by a hook for a bare `except OSError: continue`; the ENOENT that
   followed proved the file had never been created. The hook was right.

## 6. Commands

```powershell
# fleet: what is running
mcode session list   # plus the task ids the runtime reports on wake

# queue + cron facts (READ-ONLY sqlite)
$env:PYTHONIOENCODING='utf-8'
py -3 _main\wake-fix.py status --session <sessionId>

# arm the wake loop (this is what wakes me)
py -3 _main\wake-loop.py --session <sessionId> --secs 900 --poll 20

# the 3-minute driver
powershell -NoProfile -ExecutionPolicy Bypass -File _main\heartbeat.ps1
```

Never pipe a native command for its exit code: `cmd > file 2>&1`, then `$LASTEXITCODE`.
Never leave a visible console window (`pythonw.exe`, or creationflags 0x08000000|0x00000008).