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
