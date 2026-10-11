# Receipt -- per-app tap, STEP 2 (the tap) + STEP 3 (the source), 2026-10-11

**Scope of the claim.** This receipt covers the code that lets ONE process tree's audio be
captured instead of the whole endpoint mix, and the identity string that says which source a
caption came from. It does NOT claim that two apps are separated end-to-end: nothing has been
launched since the owner's stop order, so no process-loopback tap has been opened *inside the
worker* and no second worker exists. What is measured here is the code, its gating, and its
import safety.

## The artefacts

| file | bytes | sha256 (16 hex) | line endings |
|---|---|---|---|
| `worker/sotto_worker.py` | 291 873 | `EFDFB09851CC2BAD…` | 5 631 CRLF / 0 bare LF |
| `_main/per-app-source-plumbing-oracle.py` | 12 997 | `72B46E413AF34442…` | 0 CRLF / 257 bare LF |

`py -3 -m py_compile worker/sotto_worker.py` → rc=0. `py -3 worker/sotto_worker.py --help` → rc=0
(that command imports the module, so it is also an import check).

## A DEFECT WAS FOUND IN THE DELIVERED CODE, AND FIXED HERE

`py_compile` passes on a module-level `NameError`, and the stop order forbids the launch that
would have caught it. Measured, before the fix:

    $ py -3 -c "import sys; sys.path.insert(0,'H:/sotto/worker'); import sotto_worker"
    File "H:\sotto/worker\sotto_worker.py", line 1639, in <module>
        _PLP_DWORD = ctypes.c_ulong
    NameError: name 'ctypes' is not defined

The only other `import ctypes` in the file is **local to `_pmc()`** (:341), so every name in the
new PLP block that reads `ctypes` at import time was unbound. The app would have started, spawned
a worker, and shown nothing -- the same shape as the frozen tap the owner reported. The fix is one
module-level `import ctypes` immediately above the block it serves, with the reason written beside
it. After the fix: `IMPORT-OK 0.04 s`, and `--help` rc=0.

## STEP 2 -- the tap (`ProcessLoopbackTap`)

* COM plumbing: `VAD\Process_Loopback`, `PROPVARIANT` **direct** `vt=VT_BLOB` / `cbSize=12`
  (the wrapped layout returned `0x80070057` in the gate), `PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE`
  (= 0) as the default mode, and a DECLARED format -- float32 / 48 000 / 2ch -- because
  `GetMixFormat` answers `0x80004001` E_NOTIMPL on an application-loopback client.
* Its read contract is copied field for field from `WasapiLoopbackTap` (`stream IS self`,
  `start()` opens, `stop()` idempotent, `close()` releases COM, float32 mono blocks at `self.rate`,
  `silent_packets` / `position_gap_packets` / `pump_exited` / `pump_exit_hr` / `pump_exit_where`),
  so the ladder, the ledger, `close_tap()` and the silent-device verdict need no branch for it.
* `LoopbackTap()` (the factory the run loop already called) dispatches on the candidate row:
  `process_loopback` → `ProcessLoopbackTap`, `file_tap` → `FileTap`, `wasapi_loopback` →
  `WasapiLoopbackTap`, else the PortAudio tap.

**Where the gate ends and this begins:** the gate receipt
(`_main/receipt-20261011-per-app-tap-gate.md`, 19 700 B, sha256 `222412A545ECF188…`) measured the
API OUTSIDE the worker -- INCLUDE-mode on a renderer pid read peak 0.399993 while an independent
`CABLE Output` capture read the same tone at 0.399834. Nothing here re-measures that. **UNMEASURED:
that this class opens on a real pid from inside the worker.**

## STEP 3 -- the source (`tap_source`, `LineFormer.set_source`, the `source` key)

    proc:<pid>     a process-loopback tap -- one app's tree
    device:<name>  a PortAudio / WASAPI-endpoint tap -- the whole endpoint
    file:<name>    the SOTTO_FILE_TAP arm

Computed from the **candidate row the ladder actually opened**, never from what a tap object
reports later. Both open sites stamp it (`tap.source = tap_source(dev)`, 2 sites), and the run loop
hands it to the former (`former.set_source(getattr(live, "source", None))`) in the same
gen-change branch that resets the stream, so no event formed from a new tap can carry the old
tap's identity.

**The key is ADDITIVE and it is omitted, not nulled, when there is no source** -- so the arms that
have none (`--selftest`, the file arm) emit exactly the bytes they emitted before it existed.
Measured key set with no source: `{type, text, start, end, final, closed}`.

**Why adding it to the live path is safe -- three measured checks, not an assumption:**
`history-source.js:54-63` `producerOf()` reads `meta.producer` only; `app/panel/**` has **zero**
`.source` reads; and the shell's caption path never reads `source` (its `source=` hits are the
click watcher, the page-error channel and icon/strip diagnostics). `line_events()` keeps the key
(`dict(ev)`, drops only `closed`).

## The gate on the new rung -- and why the shipped path is unchanged

Rung **`p`** is offered **only** behind `if target_pid:` (:1044-1046), from `--target-pid` or
`SOTTO_TARGET_PID` (:4320-4321), and it is offered **after** rung C, so an explicit `--device`
still always wins. Its rung is `p`, not a letter, so the rotation loop's rung-C pinning rule is
untouched. With no pid, `target_pid=None` and the candidate list is the pre-change list.

A pid that does not exist is refused loudly (`_plp_pid_state`, :4333-4339) instead of falling back.
If the ladder ever moves past the app's tree while a pid WAS named, the run says so once, on stderr
AND in the event stream: `state="device-rotated" reason="per-app-tap-lost"` (:5034-5047) -- a silent
fall-back to the whole mix is the exact defect the owner's requirement is about.

## The instrument, and both colours

`py -3 _main/per-app-source-plumbing-oracle.py` -- **in process, launches nothing** -- 24 checks:
import safety, the three identity strings, the omitted-when-absent key, the key on both channels
(partial and the closed `final`), `set_source` repointing and surviving `reset()`, the wire shape,
the factory dispatch, both stamp sites, the run-loop hand-off, the rung gate (5 checks), the
separation-lost event, the declared format and the SDK mode values.
**`VERDICT: PASS`, rc=0.**

`--neg-arm` mutates a COPY beside the worker (deleted in `finally`), two mutants:

* **A** -- the `source` key removed from the event → **RED** on
  `CHK-4 partial carries source`, `CHK-4 closed carries source`, `CHK-5 set_source repoints and survives reset`;
* **B** -- the module-level `import ctypes` removed → **RED**, reproducing the exact
  `NameError: name 'ctypes' is not defined` that the delivered code had.

`NEG-ARM: PASS -- both mutants RED`, rc=0. The instrument can say NO, and CHK-1 is not vacuous.

**Two assertions were WRONG on the first run and the oracle is what caught them** (recorded because
it is the evidence that the thing discriminates): it asserted `INCLUDE_TARGET_PROCESS_TREE == 1`
(the SDK value is **0**; `EXCLUDE` is 1) and that `target_pid=target_pid` appears exactly twice
(the third occurrence is the *event field* of the separation-lost status, not a ladder entry). Both
were fixed in the oracle, not in the worker -- the worker was right and the test was wrong.

## NOT MEASURED, and not claimable from this green

1. That a process-loopback tap opens inside the worker on a real pid (the gate measured the API
   outside it; the owner's stop order forbids the launch).
2. That two apps are transcribed separately end-to-end -- **STEP 5 (two workers in one shell) does
   not exist yet**, and this receipt does not pretend otherwise.
3. **STEP 4**: `app/panel/panel.js` still keys a row by `start` alone (`committedByStart`, :785-819),
   so two sources that both start at the same audio second would collide. The worker now ships the
   identity the panel needs; the panel does not consume it yet.
4. CPU/RAM cost of a process-loopback client inside the worker, and whether the app-loopback client
   survives an app that restarts (the pid goes stale; `_plp_pid_state` is the only guard wired so far).
