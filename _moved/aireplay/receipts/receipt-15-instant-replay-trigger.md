# receipt 15 — the instant-replay trigger (the key ShadowPlay's promise hangs on)

**Lane:** instant-replay trigger. **Owner of these four files:** `src/capture/trigger.{h,cpp}`,
`src/capture/trigger_selftest.{h,cpp}`. Nothing else was edited.
**Gate:** `_main\_lane1-trigger-gate.ps1` → `LANE1-GATE PASS`, exit **0**, 5/5 arms, BUILD MODE FULL.

---

## 1. The problem, and what now exists

Lane brief §3, measured: *"There is no hotkey. 0 hits across `src/capture`. The cut is by time
(`cut_at_s`)."* Confirmed in the code before writing anything: the only cut site was
`replay.cpp:539`, `if (!cut_issued && elapsed >= cut_ns) issue_cut(f.qpc_ns)` — one cut, on a
timer, per run. `Replay::issue_cut` is **private** (`replay.h:162`) and takes one argument, the
QPC to cut at.

`trigger.h` / `trigger.cpp` are that key. They produce a `CutRequest` and nothing else; they do
not know `Replay` exists. §6 below is the exact patch that plugs them in, in a file another lane
owns.

## 2. Why two paths, and which one I actually measured

Windows offers exactly two global-hotkey mechanisms and each fails where the other survives, so
the lane ships **both** and arms every binding on **both**:

| | `RegisterHotKey` + pump thread | `GetAsyncKeyState` polling (edge-detected) |
|---|---|---|
| survives a held key | yes, `MOD_NOREPEAT` suppresses in the kernel | only via the edge latch |
| idle cost | none — it is a message | one wakeup per 8 ms tick |
| fails when another app owns the key | **yes**, `ERROR_HOTKEY_ALREADY_REGISTERED` | no — it reads physical state |
| survives an integrity mismatch | no (UIPI can suppress delivery) | yes, for the current desktop |
| sees the UAC secure desktop | no | no — neither path can |

**Measured, 1 host / 1 session (`_main\logs\lane1\lane1-trigger-selftest.txt`):**
- Arm A ran the real `RegisterHotKey` ladder on this machine. **9 keys tried, 6 registered,
  3 refused**: `Alt+F9`, `PrintScreen`, `F12` → `ERROR_HOTKEY_ALREADY_REGISTERED`. So the
  "another app owns the key" case is not hypothetical **on this box** — three of nine were
  taken, and the poll path is what keeps them reachable.
- This process's integrity RID is **0x1000 = LOW**, not Medium (`Trigger::process_integrity_rid`,
  logged every arm). Reproduced in isolation by `_main\_lane1-integrity-probe.cpp`.

**NOT MEASURED IN-GAME.** No game was launched, fullscreen or otherwise. Everything above is a
desktop-session measurement. Which path a *fullscreen game* actually delivers to is **unknown**,
and this receipt does not license anyone to claim it. The LOW-integrity reading is a reason to
keep both paths armed — a game launched "as administrator" is a higher-integrity window, which is
exactly the case where the pump path is at risk — but it is a **reason, not a measurement**.

## 3. The three defects this lane's own gate caught (all real, all fixed)

These are the transferable part; each was found by the gate, not by reading the code.

**(a) The pump was on the wrong thread — the hotkey would have fired and never been seen.**
The window was created in `arm()` on the *caller's* thread while `pump_thread_` pumped
elsewhere. Messages and hotkey registrations route by **owning thread**, so every `WM_HOTKEY`
landed in the caller's queue — in this product, the capture loop sitting in a condition-variable
wait. Arm B measured it: `NO request within 800 ms of a real WM_HOTKEY`. Fixed by creating the
window and registering inside `pump_thread_main` and blocking `arm()` on a readiness handshake
(`trigger.cpp:arm_all_bindings` / `wait_pump_ready`). This is precisely the silent failure the
file's header claims to prevent, and it was in the first draft.

**(b) An access violation from an SDK signature.** `GetSidSubAuthorityCount` returns a **pointer
to** the count byte (`securitybaseapi.h:166`), not the count. Casting it gave **243871457** — a
heap address — and indexing the SID with it segfaulted (exit `0xC0000005`). Isolated with
`_main\_lane1-integrity-probe.cpp`, which prints each step and now reports `rid=0x1000 name=LOW`.
Fixed by dereferencing, plus `IsValidSid` and a `n_sub > 32` refusal.

**(c) The gate itself could report PASS over a crash.** The first version used `goto fail`;
PowerShell rejects it at those positions, so execution fell **through** to the `LANE1-GATE PASS`
line and printed PASS while the self-test had **crashed**. The gate now has exactly one exit
point, `exit $code`, and `$code` is 0 only when every check ran.

A fourth, of the same family: when a redirect target is locked by another lane, **PowerShell
skips the command entirely and `$LASTEXITCODE` keeps its previous `0`**. The gate then read a
stale log, reported `warnings=0`, and ran a **stale `.exe`** — caught because an arm's output
was impossible for the current source. `BuildSelftest` now deletes the log first and **fails with
rc 99 if it was not recreated**, and all build logs live in the lane-private
`_main\logs\lane1\` (measured: `_main\build\*.txt` is contended by concurrent lanes).

## 4. Failure modes required by the brief

| failure mode | where it is handled | how it is gated |
|---|---|---|
| hotkey registration failure | `BindingStatus` per binding: raw `GetLastError()` + text + `owned_by_other_process`; the key is **still polled** | arm A — and 3/9 keys were really refused on this host |
| autorepeat / held key | poll path: per-binding `held_` edge latch (`//CURE-EDGE-LATCH`); pump path: `MOD_NOREPEAT` **plus** a 50 ms repeat guard | arm C (2 cuts from 8 ticks), arm B (immediate repeat suppressed) |
| ring shorter than N seconds | `RingSpanProbe` (one virtual method, so this lane never touches `RingBuffer`), surfaced as `CutRequest::ring_span_s` + `shorter_than_requested` + a human `note` | arm E — 2 s/45 s/0 s, and **no probe ⇒ `ring_span = -1` (unknown), never a fabricated span** |
| queue overrun | bounded depth 8; a refused press increments `queue_refused` and **logs that a press was dropped** | not separately gated — stated as an unverified design choice |

The ring-short case is deliberately a *named field*, not a silent clamp: "press the key, get a
4-second clip, no explanation" is how an instant-replay product feels broken.

## 5. The gate, and why arm D makes it non-vacuous

`_main\_lane1-trigger-gate.ps1`. Builds with the repo's own path (mingw-w64 g++ 15.2.0, `-std=c++17
-O2 -Wall -Wextra`, the same lib set as `src\capture\build.cmd`), linking **every capture source
except `main.cpp`**, which owns a colliding `main()`. ARM 0 also runs `build.cmd` itself.

Arm D is a **control**: the cure is one line, the gate deletes it in a **copy** of `trigger.cpp`,
builds a mutant, and **requires the mutant to fail**. Reverting the cure turns a held key into
one clip per 8 ms. Measured: fixed `cuts=2 suppressed=5`; mutant `cuts=5 suppressed=0`. If the
deletion ever stopped matching, the mutant would equal the fixed build and arm D goes red.

Authoritative output (exit 0, `BUILD MODE :: FULL`):

```
ARM 0 repo build.cmd rc=0
STEP 1 build FULL rc=0
STEP 1 compiler warnings=0 (built -Wall -Wextra; a warning is a finding)
STEP 2 cure line occurrences in trigger.cpp = 1
STEP 2 cure line occurrences in the MUTANT COPY = 0
STEP 2 sha256 fixed  = B2495E4A80C38A3D2DFD77BE9D5F7DE0B2410ADE8BBED9845FB22CE8A5884456
STEP 2 sha256 mutant = 5D3476E827612FAE35EB89AE0C585CE7F2858C6FA6E5326DC6521232864FD454
STEP 2 build MUTANT (FULL) rc=0
STEP 3 selftest rc=0
ARM A PASS :: keys=9 registered=6 polled_only=3 pump_live=1 poll_live=1 integrity=LOW | refused: Alt+F9=ERROR_HOTKEY_ALREADY_REGISTERED; PrintScreen=ERROR_HOTKEY_ALREADY_REGISTERED; F12=ERROR_HOTKEY_ALREADY_REGISTERED;
ARM B PASS :: F24 registered=1 | first press -> seq=0 via_rhk=1 via_poll=0 window=30000ms t_cut_ns>0=1 pump_messages=1 | extra_requests=0 autorepeat_suppressed=1
ARM C PASS :: 8 ticks over down,down,down,up,up,down,down,up -> cuts=2 (want 2) suppressed=5 (want 5)
ARM D PASS :: mutant=aireplay-trigger-mutant.exe rc=0 | mutant cuts=5 suppressed=0 (the FIXED build must say cuts=2 suppressed=5)
ARM E PASS :: ring 2s vs 30s asked -> shorter=1 ... | ring 45s vs 30s asked -> shorter=0 ... | ring empty vs 30s asked -> shorter=1 ... | no probe -> ring_span=-1 shorter=0
TRIGGER-SELFTEST 5/5 arms :: GREEN
BUILD MODE :: FULL
LANE1-GATE PASS
```

Re-run it yourself: `pwsh -NoProfile -File H:\sotto\_moved\aireplay\_main\_lane1-trigger-gate.ps1`

**No `git commit` was made** (rule 7 reserves that for an owner-level decision; the gate is green
but the tree is shared with lanes editing it right now).

## 6. HOOKUP — the exact patch, for the lane that owns `replay.{h,cpp}`

Not applied. Those files belong to another lane (rule 5). Two edits:

**`src/capture/replay.h`** — add a member next to `Trigger`-using members (after line 134, `TestWindow tw_;`):

```cpp
#include "trigger.h"
...
    Trigger       trig_;      // the instant-replay key: ring_buffer.h's "the hotkey must be a
                               // pointer flip" finally has a hotkey
```

**`src/capture/replay.cpp`** — three edits:

1. In `Replay::arm()`, **after** `cut_thread_ = std::thread(&Replay::cut_thread_main, this);`
   (`replay.cpp:166`) and before `return true`:

```cpp
    // Arm the key only once the ring exists, and only when an encoder really initialised —
    // LAW 6: an armed hotkey that writes nothing is the worst failure this product has.
    if (gate_passed_) {
        std::string terr;
        if (!trig_.arm(aireplay::default_binding_ladder(), (double)cfg_.ring_seconds, &terr))
            log_line("  WARN the replay hotkey did NOT arm: %s - a dead hotkey that says why "
                     "beats a live hotkey that does nothing", terr.c_str());
        else
            log_line("  %s", trig_.arm_summary().c_str());
    } else {
        log_line("  The replay hotkey is NOT armed: no encoder initialised (LAW 6).");
    }
```

2. In `Replay::run()`, **replace** the timer-only cut at `replay.cpp:539-542`:

```cpp
        if (!cut_issued && elapsed >= cut_ns) { issue_cut(f.qpc_ns); cut_issued = true; }

        // The KEY.  Drained every frame, so the trigger never sits in a queue waiting for a
        // capture tick; `cut_issued` still guards the timer path from firing a second clip.
        CutRequest req;
        while (trig_.take(&req, 0)) {
            issue_cut(req.t_cut_ns);            // the one argument issue_cut() takes
            cut_issued = true;                  // the timer cut is now suppressed
            log_line("  HOTKEY %s -> cut at QPC %llu (%s, window %.1fs requested, %.1fs in ring%s)",
                     req.binding.name, (unsigned long long)req.t_cut_ns,
                     req.from_registerhotkey ? "RegisterHotKey" : "GetAsyncKeyState",
                     req.requested_window_s, req.ring_span_s,
                     req.note.empty() ? "" : (" - " + req.note).c_str());
        }
```

3. In `Replay::shutdown()`, **before** `cut_quit_ = true;` (`replay.cpp:568`): `trig_.disarm();`

**Not covered by the hookup, and someone must own it:** passing a `RingSpanProbe` so
`CutRequest::ring_span_s` is real rather than `-1`. `Replay` would implement the one-method
`RingSpanProbe` over its own `ring_` (`newest_abs()`/`oldest_abs()` + QPC) and call
`trig_.set_ring_probe(...)` in `arm()`. Without it arm E's short-ring case is proven but the
product reports "unknown", which is honest and not yet useful.

## 7. Limits of this receipt

- **NOT MEASURED IN-GAME.** No game, no fullscreen, no elevated window. 1 host, 1 desktop session.
- The three refused keys are **this host, this moment**; another machine will differ. `F12` moved
  between two of my own runs, which is itself the point.
- Arm C drives a **synthetic** key-state function, not real keystrokes — deliberately, so the test
  never types into whatever the owner has focused.
- Arm B posts a **real `WM_HOTKEY` to a message-only window**; it proves the pump, not the keyboard.
- `TriggerStats::queue_refused` / the depth-8 bound are **design, not measurement**.
- I did not touch `main.cpp`, `replay.cpp`, `replay.h`, `ring_buffer.*` or `build.cmd`; §6 is a
  proposal, and the product does not transcribe from a hotkey until someone applies it.