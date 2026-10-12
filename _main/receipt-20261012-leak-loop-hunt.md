# Receipt — leak / loop hunt (2026-10-12)

Lane **leak-loop-hunt**. Branch `chore/measurement-instruments-2026-051354`, tip `3df512b` + this lane's
uncommitted edits. Scope written: `worker/sotto_worker.py`, `app/webview/sotto_webview.py` (+ own instrument
under `_main/`). `app/panel/**` untouched. Nothing was launched, relaunched or killed; every measurement below
runs **in process** (`pythonw.exe`, no window) or is a **read-only** census of an already-running pid.

## Pins

| file | before | after |
|---|---|---|
| `app/webview/sotto_webview.py` | 471 786 B, 9 264 CRLF, **0 bare LF** | **473 486 B**, 9 287 CRLF, **0 bare LF** |
| `worker/sotto_worker.py` | 326 681 B, 6 175 CRLF, **0 bare LF** | **327 114 B**, **0 bare LF** |

Both compile (`py_compile`) and import (`import sotto_worker`, `import sotto_webview`).

---

## F1 — the panel names itself `no-audio` **while captions are demonstrably flowing**

**file:line (pre-fix revision)** `app/webview/sotto_webview.py:4821` (`panel_state_snapshot`) and
`:4851` (`_named_panel_state`).

**What it does.** `panel_state_snapshot` read **only** `((dom or {}).get('status') or {}).get('text')` —
it threw away the sibling `kind` field that `PANEL_STATE_PROBE` (`:3237-3297`) already returns. The predicate
then opened with `if panel_status == 'Receiving captions': return 'receiving'`.

**Why that test is DEAD on the live path.** `app/panel/panel.js:2882-2905` `setStatus()` computes
`const paintsText = state === 'error'` and then `dom.statusText.textContent = paintsText ? text : ''` — every
state that is not an error gets its text **blanked**, and the healthy state is carried by the `status--live`
class instead. That is the owner's own order of 2026-10-08, verbatim: *"tira o 'receiving captions'. deixa só um
icone dinamico"*. So on the live path `panel_status` is `''`, the literal comparison never fires, and the
precedence falls through to the worker's `noAudio` latch — which **no caption clears** (it is set at
`:8014-8018` and reset only in `_spawn`, `__init__` and `_do_revive`).

**Measured cost — it is live right now, in one write.** `_main/panel-state.json` (read-only, produced by the
shell's own probe) carries, in the **same** snapshot:
`namedState="no-audio"` **and** `panel.live.count=201` **and** `panel.status={"kind":"live","text":""}`
**and** `worker.noAudio=true`. 201 captions had committed; the panel named itself dead. The two facts are
simultaneously true, which is the whole finding.

**Fix.** Carry the status **object** through: `panel_status_obj = (dom or {}).get('status') or {}`, pass
`panel_status_obj.get('text')` **and** `panel_status_obj.get('kind')`, and widen the test to
`if panel_status == 'Receiving captions' or panel_kind == 'live':`. The literal comparison is kept for a panel
that still paints the phrase; `kind == 'live'` is the one that actually fires. `panel_kind` defaults to
`None` so every existing caller keeps working.

**Gate — both colours, `_main/named-panel-state-oracle.py`** (imports the REAL shell in process and finds the
owning class dynamically; `--neg-arm` restores the text-only predicate in a COPY):

| arm | BEFORE (shipped) | AFTER (fixed) | NEG-ARM |
|---|---|---|---|
| 1 LIVE `text='' kind='live' noAudio=True` | **FAIL** `got=no-audio want=receiving` | PASS `receiving` | **FAIL** |
| 2 the sentence, if a panel still paints it | PASS | PASS | PASS |
| 3 a death held until a caption proves recovery | PASS | PASS | PASS |
| 4 a quiet worker, panel idle | PASS | PASS | PASS |
| 5 no bridge at all | PASS | PASS | PASS |
| 6 an idle worker, nothing latched | PASS | PASS | PASS |
| 7 the worker's own error vocabulary | PASS | PASS | PASS |
| 8 old predicate says `no-audio` on the live path | PASS | PASS | PASS |
| 8 new predicate says `receiving` on the live path | **FAIL** | PASS | **FAIL** |
| **VERDICT** | **RED** (2 failures) | **PASS** (0) | **RED** (2) |

`py -3 _main/named-panel-state-oracle.py` → `PASS`, rc 0. `--neg-arm` → `RED`, and the **shipped file also
went RED before the fix** — the gate can say NO, and it said it about the code that was actually on disk.

---

## F2 — `ProcessLoopbackTap` leaks **4 Windows handles per open/close cycle**, unbounded

**file:line** `worker/sotto_worker.py` `ProcessLoopbackTap._open` / `close` (`:2407-2423`) over
`_plp_activate` (`:2023`) and `_plp_open_capture` (`:2124`).

**Measured (in process, 10 full tap cycles, my own pid as the target).** Instrument counts **native** threads
(`CreateToolhelp32Snapshot`) and **handles** (`GetProcessHandleCount`) per cycle:

```
baseline native_threads=5 py_threads=1 handles=171
  cycle  0 native_threads= 25 py_threads= 1 handles= 249
  cycle  1 native_threads= 25 py_threads= 1 handles= 253
  cycle  2 native_threads= 25 py_threads= 1 handles= 257
  ...                                          (exactly +4 every cycle, monotonic)
  cycle  9 native_threads= 25 py_threads= 1 handles= 285
```

* **Threads: NO leak.** 5 → 25 **once**, then **flat at 25** for all ten cycles. The audio stack builds its MTA
  pool on the first activation and reuses it. This answers the Lead's "what ARE the 81 threads": the tap's
  thread cost is a **one-time** +20, and the rest is the ORT/CUDA pools. A thread leak was the hypothesis; it
  is **refuted by measurement**, not by reading.
* **Handles: a real leak.** +4 per cycle, monotonic, with no ceiling.

**Bisected by measurement** (8 iterations per arm, COM initialised; the one-time `LoadLibraryW` paid before any
arm measured):

| arm | what it calls | per-cycle |
|---|---|---|
| A | `_plp_activate_export()` only | +0.50 (**one-time** +4 — `LoadLibraryW`) |
| B | `_plp_activate` + release the client | **+6.50** |
| C | `_plp_activate` + `_plp_open_capture` + release both | **+9.00** |
| D | the full `ProcessLoopbackTap` open/start/stop/close | **+8.25** |
| E | `_com_init` / `_com_uninit` only | **+0.00** |

**COM init/uninit is balanced — it is NOT the cause** (arm E, exactly +0). The growth lives inside
`ActivateAudioInterfaceAsync` and `IAudioClient::Initialize`.

**Tested mitigation, deliberately NOT shipped.** The completion handler is never released by us
(`_plp_activate` builds it at `:2047` and drops it; `_PlpCompletionHandler.release` `:1964-1966` only
decrements and never frees). Releasing our reference via the vtable drops the leak from **+6.50 to +4.25** per
cycle — measured, a **35 %** cut, not a cure: the handler's refcount reads **2** after activation (ours + one
Windows AddRef) and **1** after our `Release`, so Windows still holds it. **Not shipped**, because it is
partial and it changes the lifetime of a hand-rolled COM object whose own docstring (`:1907-1922`) warns that
if the thunks are collected the vtable slot becomes a dangling pointer and *"activation either never completes or
takes the process down"* — and the owner's standing rule forbids me the launch that would catch a crash.

**Live sampling — and it caught a DEATH instead of a slope.** A read-only `GetProcessHandleCount`
sampler against the then-running worker (pid 11584, `PROCESS_QUERY_LIMITED_INFORMATION`, no attach, no
injection; `I:\cc-tmp\_lh2.out`) read **746 handles** at t=0, **745** at t=5, then **0 from t=10 onward** —
the pid **exited mid-sample**. `_main/webview-run.log` says what happened, in order:
`BRIDGE_SILENT_BENIGN ms=30000 pid=11584 state=no-audio because="device-rotated reason=flat peak=0.0
floor=0.002" evidence_age_s=568.9 restarts=7` → `BRIDGE_EXIT pid=11584 rc=1 spawns=7 captions=4940
statuses=113 malformed=0` → `BRIDGE_SPAWNED pid=5472`. So the worker the Lead censused at **840 handles**
is **gone**, and its replacement is **pid 5472, 82 threads** (read-only `CreateToolhelp32Snapshot` census).

**Therefore the sampler is NOT corroboration of the leak rate, and I am not claiming it is.** What it shows is
that the worker **exited rc=1 after ~569 s of benign no-audio rotation having emitted 4 940 captions**, and was
respawned. The arithmetic that *would* corroborate (+4 handles × ~195 rotations at the 8 s backoff cap ≈ 780)
is a **plausible fit to a number I did not take on a process I cannot re-measure** — the pid is dead. The
per-cycle leak itself is **measured and reproducible in process** (the table above); its **live magnitude is
UNMEASURED**.

**What the 82 threads ARE — the Lead's question, answered.** My in-process census shows the tap costs a
**one-time +20 native threads** (5 → 25 on the first activation) and **zero per cycle thereafter** (flat at 25
across ten cycles). A tap pump thread would have to be joined-and-replaced to leak, and it is not: the count
does not move. So the worker's 82 threads are the **audio-stack MTA pool (one-time) plus the ORT/CUDA pools**,
not a per-rotation thread leak. The hypothesis is **refuted by measurement**.

**Unbounded Python-side growth, same call site.** `_PLP_HANDLERS[id(self)] = self` (`:2014`) is never
removed: measured **24 entries after 24 activations**. ~200 B per rotation, and the docstring's reason for
keeping them is sound (thunk lifetime), so this is a **slow, bounded-by-rotations** growth, not the handle leak.

---

## F3 — error-path interface leak in `_plp_open_capture` (**fixed**)

**file:line** `worker/sotto_worker.py:2210-2212` (pre-fix).

`GetService(IAudioCaptureClient)` hands us a reference at `:2205` (`out["capture"] = cap`). If
`IAudioClient::Start` then fails, the function returned `out` with `ok=False` — and the caller
`ProcessLoopbackTap._open` **raises** on `ok=False` without ever installing `_capture`, so
`close()` could never release it. **One `IAudioCaptureClient` leaked per failed open** — the path the
ladder walks on a host with no audio routed. Fixed by releasing `cap` and nulling `out["capture"]` on that
branch. Verified: `py_compile` OK, module imports, and a 3-cycle smoke test still logs `PLP_OPEN_OK`
(48000 Hz, 2 ch, the declared-format winner) so the success path is untouched.

**Also found, NOT fixed (latent on this host):** `GetMixFormat`'s `mix` (`:2143-2144`) is a
**CoTaskMemAlloc'd** block that is never `CoTaskMemFree`d. On this box `GetMixFormat` returns
`E_NOTIMPL` (measured, and the code already records it), so `mix` is null and nothing leaks here — but on a
host where it succeeds the block leaks on every open. Left alone: it is dead on this host, and the fix needs a
new `ole32` binding whose failure mode I cannot exercise without a launch.

---

## Deliberately left alone

1. **Do NOT clear `worker.noAudio` on a caption** (the Lead's second ask). `_on_silence` `:8282-8287`
   calls `self._kill_and_restart('silent')` **only when `no_audio` is False** and no block progress arrived
   inside `silence_ms`. The live worker sits on an idle endpoint that delivers nothing, so clearing the latch
   on a caption would make the shell **kill and respawn the worker — paying a ~1 GB model reload — every time
   the owner pauses after speaking**. That is precisely the "loop that should not loop" he complained about.
   `noAudio` is a **worker verdict about the audio**, not a death a caption retracts — unlike `pendingError`,
   which a caption legitimately lifts at `:7970-7972`. The defect was the **predicate**, and it is fixed in
   `_named_panel_state` alone.
2. **`_PLP_HANDLERS`** — see F2; the retention is deliberate and its stated reason is sound.
3. **`BRIDGE_CAPTION_SENT`** (`:5935`) writes **one log line per caption, unconditionally**: **51 445 lines =
   6 020 862 B = 51.0 %** of the 11 801 627 B `_main/webview-run.log`. `BRIDGE_METER` (`:7922`) and
   `BRIDGE_STATS_PUSH` (`:6323`) are already throttled to one line per interval with a count, so the caption
   line is the outlier and the dominant log-growth term. **Left alone** because it is the only per-caption
   evidence trail and the owner's complaint is about hangs, not disk; throttling it would trade a diagnostic
   away for a cost he has not reported. **Flagged, not changed.**
4. **`ProcessLoopbackTap.stop`'s `join(timeout=2.0)`** — the pump thread is a daemon and `_stop` is set
   before the join, and the measured thread count is **flat** (F2), so there is nothing to fix here.

---

## Not measured / limits

* Nothing was launched, so **no claim here is about the WebView2's real DOM**. F1's live evidence is the shell's
  **own** probe output, not a paint.
* The F2 handle leak's **live rate on pid 11584** is corroboration only (see F2).
* The worker respawn at ~16:13 is explained from `_main/webview-run.log` (`BRIDGE_SILENT ms=30000` →
  `BRIDGE_RESTART reason=silent` → `BRIDGE_EXIT rc=1` → rc=3 restarts → spawn 7 = pid 11584, rotating,
  `BRIDGE_SILENT_BENIGN ... because="device-rotated"`), but that running shell is the **pre-pin** one and
  those lines carry **no hour stamp**, so no time is claimed.

---

# ROUND 2 — "the worker restart loop" (2026-10-12)

**Target given by the Lead:** *"ONE worker: ~569 s of run, FOUR THOUSAND NINE HUNDRED AND
FORTY captions emitted, then it exits rc=1 because a tap rotated onto a FLAT endpoint, and the
bridge respawns it into a ~1 GB model reload. That is the loop."*

## THE PREMISE IS REFUTED BY THE LOG. The flat rotation did not kill that worker.

Read in order from `_main/webview-run.log` (live, read-only), the lines around index 117385:

```
HOT_RELOAD_WORKER_DEFERRED files=1 reason=capturing waited_ms=2014 max_defer_ms=25000 \
    code_is_stale=True sha256_disk=44f9dbe80d130af6 sha256_at_spawn=5ed6d0a5697bd654
HOT_RELOAD_WORKER_FORCED   files=1 reason=no-boundary-in-25000ms waited_ms=32046 \
    code_is_stale=True sha256_disk=44f9dbe80d130af6 sha256_at_spawn=5ed6d0a5697bd654 cos...
HOT_RELOAD_WORKER_RESTART  files=1 after_idle_ms=32046 waited_ms=32046
BRIDGE_STOP reason=hot-reload pid=11584
BRIDGE_EXIT pid=11584 rc=1 spawns=7 captions=4940 statuses=113 malformed=0 stderr_tail=[...]
BRIDGE_START reason=hot-reload ...
BRIDGE_SPAWNED pid=5472 ...
```

Three facts settle it:

1. **`rc=1` is not a worker exit code.** CPython's `Popen.terminate()`/`kill()` on Windows calls
   `TerminateProcess(handle, 1)`. The worker's OWN exits are 0 / 2 / 3 / 130 / 4. So `rc=1` means
   **the shell killed it**, and the line immediately above names the shell's path:
   `BRIDGE_STOP reason=hot-reload` -> `WorkerBridge.stop()` -> `child.terminate()`.
2. **The kill was a HOT RELOAD, and `sha256_disk=44f9dbe80d130af6` is this lane's own round-1 F3
   edit to `worker/sotto_worker.py`** (the previous pinned revision was `5ed6d0a5697bd654`).
   `code_is_stale=True` is the whole reason the reload was requested at all. **This restart is a
   self-inflicted measurement artefact of round 1, not an owner-visible loop, and it is reported as
   such.**
3. **No flat rotation is anywhere in that sequence.** `_on_silence`'s last word before the reload was
   the BENIGN branch: `no_audio` was True (`device-rotated` + `reason=flat` is a
   `WORKER_NO_AUDIO_VERDICTS` sentence), so it re-armed the watchdog and **returned without killing
   anything** (`sotto_webview.py`, the `BRIDGE_SILENT_BENIGN` arm). The `BRIDGE_SILENT` +
   `_kill_and_restart('silent')` path requires `no_audio == False`, and it never fired here.

## The three questions, answered

**Q1 — "why does a flat rotation end the whole process?"** It does not. The predicate that DID end it
is `WorkerReloadPolicy._fire` -> `forced = capturing and not boundary and waited_ms >=
self.max_defer_ms` -> `self.restart(files)`. The counter `_on_silence` reads is not involved:
`_on_silence` never reached a kill.

**Q2 — "does a flat rotation share a counter with a stall?"** **No, and the hypothesis is refuted by
reading the code.** In `worker/sotto_worker.py`: `stall_reopens` (incremented at `:5733`) is the
STALL counter and it is per-candidate, reset at `:5608-5611`; `rotations` (the ladder's) is the FLAT
ROTATION counter and it is separate. `tap_stall_reason(pump_exited, idle_s, reopens)` (`:255-275`)
is fed only `client_dead = bool(getattr(inner, "pump_exited", False))` (`:5678`) — `pump_exited` is
the ONLY affirmative dead-client signal, and a flat rotation never sets it. Neither counter feeds any
kill: the stall path's own comment at `:5707` says *"the process NEVER exits on a stall"*, and the
`endpoint-idle` branch `time.sleep(0.1); continue`s.

**Q3 — is the honest verdict intact?** **Yes, already.** `worker/sotto_worker.py` separates the two
facts: `proved_alive["any"]` is set only by a candidate that `settled` (`:5792-5798`), and
`ran_but_silent = bool(silent_rows) and not proved_alive["any"]` (`:5915`) -> `return 3 if
ran_but_silent else 0` (`:6137`). A worker that emitted N>0 captions and then rotated is
`proved_alive`, so it is NOT `ran_but_silent`. **I did not touch the silence verdict, the ladder, the
rotation counter, the tap policy, or the worker at all in round 2.** `worker/sotto_worker.py` is
round 2 did not
edit `worker/sotto_worker.py` at all. **It has since moved again under another lane** — it now reads
330239 B / sha256 `A30BA3B4BEB9A7CE...`, where at the time of the incident `sha256_disk` was
`44f9dbe80d130af6` (round 1's F3 revision). So the digest in that FORCED line names a *past* revision of
a file other lanes also edit, which is exactly the point.

## But the Lead's QUESTION WAS RIGHT ABOUT THE CLASS, AND THE CONFLATION IS REAL — IN THE SHELL

The two facts **are** conflated, one layer up. `WorkerReloadPolicy._fire` held the reload on
`bridge.is_capturing()` = `bool(self.capturing) and self.child is not None` — **ONE flag for TWO
different workers**:

* a worker that is **TRANSCRIBING** (a caption may be in flight — restarting cuts it), and
* a worker that merely has a stream **OPEN** (nothing in flight — restarting disturbs nothing).

The guard exists for the first. **The second is the measured normal on this box** (a tap that is open
and delivering nothing, because nothing is routed into it — see AGENTS.md *"The routing law on THIS
box"*). Its only other exit is a closed-line boundary, raised by `on_worker_caption` on a
`final:true` caption — **which an idle endpoint will never produce.** So the guard DEFERRED at every
check and the ceiling FORCED the reload anyway. Measured cost, from the log above:
`max_defer_ms=25000` but `waited_ms=32046` — because the check only runs when the timer fires, and it
was armed with the full 10 s re-check, so the ceiling was observed **7 046 ms late**. The deferral
bought **nothing** and cost a 32 s stall of the capture pipeline plus a ~1 GB model warm-up.

This is not a one-off. Counted over the live log: **28 `HOT_RELOAD_WORKER_RESTART`, 5 of them
`FORCED`, 188 `DEFERRED`, 68 `COOLDOWN`, 16 `APPLIED_AT_BOUNDARY`, and 14
`BRIDGE_STOP reason=hot-reload`.** Every worker-file edit on this box pays it.

## The fix (`app/webview/sotto_webview.py`, 2 places + 1 stamp)

1. `WorkerBridge` now records **when** the last caption arrived, not just how many:
   `self.last_caption_at = 0.0` in `__init__`, stamped `time.monotonic()` where a caption is
   accepted (next to `self.captions += 1`).
2. `_fire` computes the second fact and holds **only while a caption is RECENT**:
   `transcribing = last_caption_at > 0 and (now - last_caption_at)*1000 < max_defer_ms`.
   `if capturing and not boundary and not forced and transcribing:` -> defer.
   Otherwise a worker with **nothing in flight** falls through to the same
   boundary/floor/restart path a boundary would have taken, logging
   `HOT_RELOAD_WORKER_IDLE_APPLIED ... reason=no-caption-in-25000ms idle_ms=... cost=one-model-warm-up`.
3. **The ceiling is a DEADLINE, not a hint**: the re-arm is
   `self._arm(min(self.defer_recheck_ms, max(0, self.max_defer_ms - waited_ms)))`, so
   `max_defer_ms=25000` means 25 000 ms instead of 32 046.

**The GUARD and the FLOOR are intact**: a transcribing worker still waits for a closed line
(arm 2), the 180 s `WORKER_RELOAD_MIN_INTERVAL_MS` floor still bounds the rate (arm 8), and a
non-capturing worker is unchanged (arm 9). Nothing in `worker/` moved, so the silence verdict and the
exit-on-idle policy the owner feels when he pauses are untouched.

## New instrument — `_main/worker-reload-guard-oracle.py` (house style, 9 arms)

Imports the REAL shell in process and drives the REAL `WorkerReloadPolicy._fire` against a stand-in
bridge that carries the two facts. `--neg-arm` restores the pre-fix policy (both anchors) in a COPY.

| colour | result |
|---|---|
| BEFORE (shipped, unfixed) | **RED** — arms **1, 3, 5, 8** |
| AFTER (fixed) | **PASS — failures: 0 (9 checks)** |
| NEG-ARM (pre-fix restored in a copy) | **RED — failures: 4, arms 1, 3, 5, 8** |

The neg-arm reproduces the BEFORE arm-for-arm, which is what makes it a control. Arm 5 prints
`arm_ms=2986` where the old code armed `10000` (22014 + 2986 = 25000 exactly).

## Gate battery

| gate | result |
|---|---|
| `py -3 _main/device-silence-oracle.py` | **UNMEASURED — cannot run here** |
| `py -3 _main/verdict-order-oracle.py` | **UNMEASURED — cannot run here** |
| `py -3 _main/panel-exit3-oracle.py --unit --neg-arm` | **PASS** (`"verdict": "PASS"`, `failures: []`) |
| `py -3 _main/tap-stall-policy-oracle.py` | **PASS** (shipped failures 0; control failures 17) |
| `py -3 _main/tap-idle-liveness-oracle.py` | **VERDICT: GREEN** |
| `py -3 _main/tap-stall-watchdog-oracle.py` | **VERDICT: GREEN -- every arm as expected** |
| `py -3 _main/device-ladder-rescan-oracle.py` | **VERDICT: PASS** |
| `py -3 _main/worker-reload-guard-oracle.py` (+ `--neg-arm`) | **PASS / RED** — see above |

**Why the two are UNMEASURED, stated plainly: `sounddevice` is not installed on this box.**
`py -3 _main/device-silence-oracle.py` dies at `line 33, import sounddevice` and
`verdict-order-oracle.py` at `line 104` inside `pick_silent_device()`. Measured: the module is absent
from `C:\Program Files\Python311\Lib\site-packages` (only `openai\_extras\sounddevice_proxy.py`
matches the name), and **every** interpreter on the box returns `ModuleNotFoundError` for it —
3.11 (`py -3`), the uv 3.13.14, the Astral 3.11.13, and msys64's python. So I have **no reading** for
those two gates: not green, not red, and **not a regression** — round 2 did not touch `worker/` or the
device ladder, and both oracles fail at import, before any subject code runs. The Lead's warning about
device-silence ARM1 being environmentally RED is moot here: the oracle cannot reach its arms at all.
**This is the one thing in this round I could not gate, and it needs a box with `sounddevice`.**

## Left alone deliberately (round 2)

* The worker's silence verdict, ladder, `TAP_IDLE_MAX_S`, `tap_stall_reason`, `stall_reopens` — the
  Lead's rule, and Q3 shows they were already correct.
* The worker exit-on-idle policy the owner feels when he pauses — untouched, as instructed.
* `_on_silence`'s `BRIDGE_SILENT` kill path (`no_audio == False`) — not reached in this incident and
  not weakened.
* Round-1 residuals stand unchanged: `_PLP_HANDLERS` retention, `GetMixFormat`'s `mix`, and
  `BRIDGE_CAPTION_SENT`'s one log line per caption.

## Pin

`app/webview/sotto_webview.py` = **476471 B**, sha256 `F141842E5151968DC5C53D4A1C778E16DDDC287DE86C83250F792FD5CBA5A5B4`, 0 bare LF.
`worker/sotto_worker.py` = **330239 B**, sha256 `A30BA3B4BEB9A7CE4A1624B37D15872F51AC99DCE110910668C72D26D2D9EE1C` (round-1 F3, unmoved).

## ROUND 2 — ADDENDUM: the shell's OWN self-test pinned the old predicate, and how that is handled

Found while gating: `app/webview/sotto_webview.py` carries its own arms for this exact policy inside
`run_selftest` (`StandInBridge` + `run_arm`). **Its arm 1 is the defect I changed** — it sets
`br.capturing = True`, touches the worker file 6 times and asserts
`ARM guard touches=6 restarts_during_capture=0 expect=0`, i.e. it pins *"while a capture is open, no
restart"*. Its stand-in bridge has **no caption clock at all**, so under my first cut it would have
taken the IDLE_APPLIED path, restarted, and turned the shell's self-test RED.

**I could not run that self-test to verify a repair:** `run_selftest` is reached only from
`if self.args.selftest: self.run_selftest()` inside the shell's startup, so running it means
**launching the app**, which the owner's rule reserves to the Lead. Shipping an unverified edit to a
gate is worse than not touching it, so the code was changed instead of the gate:

> **A bridge that cannot report the second fact is treated as IN FLIGHT.** `getattr(bridge,
> 'last_caption_at', None)`; `None` -> `transcribing = True` -> the reload is HELD. The guard's
> failure mode is therefore always **"do not restart"**, which is the conservative direction and
> exactly the contract arm 1 asserts. The REAL `WorkerBridge` always carries the attribute (0.0 until
> the first caption), so the live path gets the fix and a never-captioned worker is still applied at
> once.

**That contract is now gated in-process instead: arm 10 of `_main/worker-reload-guard-oracle.py`
builds a bridge with `has_clock=False` — byte-for-byte the StandInBridge surface — and asserts
`restart=0, kinds=DEFERRED`.** It passes in BOTH colours, which is its job: it is the arm that proves
the shell's self-test contract did **not** move. **STILL UNMEASURED: the shell's own `run_selftest`
has not been run** — the claim here is "the conditions arm 1 drives now hold", measured in process, not
"the self-test was executed".

The docstring's rule 2 (`is_capturing() is the state the owner is watching`) and the ceiling paragraph
were both rewritten to state the second fact and the deadline, so the file no longer documents the
predicate it stopped using.

**Final arm table (`_main/worker-reload-guard-oracle.py`, 10 checks):**

| colour | result |
|---|---|
| BEFORE (shipped, unfixed) | **RED** — arms 1, 3, 5, 8 |
| AFTER (fixed) | **PASS — failures: 0 (10 checks)** |
| NEG-ARM (pre-fix restored in a copy) | **RED — failures: 4, arms 1, 3, 5, 8** |

Gates re-run after the sentinel edit: `panel-exit3 --unit --neg-arm` **PASS**, `tap-stall-policy`
**PASS** (0 shipped / 17 control), `tap-stall-watchdog` **GREEN**, `tap-idle-liveness` **GREEN**,
`device-ladder-rescan` **PASS**. `device-silence` and `verdict-order` remain **UNMEASURED**
(`sounddevice` absent — see above).

**FINAL PIN:** `app/webview/sotto_webview.py` = **477839 B**, sha256
`CD00E071341E9BC3A31FAC3F7DE95B477464A6C71A30D3359C1136E1A51C81CA`, 0 bare LF.
