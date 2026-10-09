# THE OVERLAY HOTKEY CONTRACT — NORMATIVE

Lane `single-app-design`. Written 2026-10-07. **This file is the contract L1 codes the trigger
against.** Where it disagrees with the code currently on disk, it says so explicitly and
gives the line.

Companion: `docs/integration-sotto-app.md` (process model, failure matrix).
Win32 semantics cited below were **READ** on 2026-10-07 from Microsoft Learn, page last
updated **2024-06-12**:
<https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey>

---

## 0. PROVENANCE — WHAT IS CITED AND WHAT IS NOT

| claim | status | source |
|---|---|---|
| `hWnd = NULL` → WM_HOTKEY goes to the **calling thread's** queue and "must be processed in the message loop" | **READ** | MS Learn, `RegisterHotKey`, Parameters/`hWnd` |
| `RegisterHotKey` "fails if you try to associate a hot key with a window created by another thread" | **READ** | MS Learn, Return value |
| `RegisterHotKey` "typically fails if the keystrokes … have already been registered for another hot key" | **READ** | MS Learn, Return value |
| `MOD_NOREPEAT` (0x4000): auto-repeat "does not yield multiple hotkey notifications" | **READ** | MS Learn, `fsModifiers` table |
| `MOD_WIN` shortcuts "are reserved for use by the operating system" | **READ** | MS Learn, `fsModifiers` table |
| **"The F12 key is reserved for use by the debugger at all times, so it should not be registered as a hot key."** | **READ** | MS Learn, Remarks |
| `id` must be `0x0000`–`0xBFFF` for an EXE | **READ** | MS Learn, Remarks |
| **NVIDIA's actual default key set** | **`NOT VERIFIED`** | `nvidia.custhelp.com/…/a_id/5035` and `a_id/5042` both returned an Oracle *"Technical Difficulties"* page; `nvidia.com/en-us/geforce/shadowplay/` returned 404. **No number below is attributed to NVIDIA.** |
| In-game (fullscreen-exclusive) delivery | **`NOT MEASURED`** | no game was run on this host |
| `Alt+C` FREE / `Alt+F9` OWNED **on this box** | **READ** (in-repo measurement, quoted by the production shell) | `app/webview/sotto_webview.py:1254-1256`, attributing `_main/_audit-hotkey-probe.py` |
| The trigger's own gate script and receipt | **DO NOT EXIST** | `trigger.h:34-38` cites `_main\_lane1-trigger-gate.ps1` and `receipts\receipt-15-instant-replay-trigger.md`. Measured: `Test-Path` → **False**; `receipts/` has 17 files and its `receipt-15` is `receipt-15-offline-cut-pass1147.md`, a different document. **Do not cite that measurement.** |

---

## 1. THE TRUTH THAT DECIDES THE WHOLE CONTRACT

> **`RegisterHotKey` reports PRESS ONLY. It has no release, and no hold.**

READ, MS Learn: the mechanism is *"When a key is pressed, the system looks for a match …
the system posts the WM_HOTKEY message"*. There is one message type, and it is emitted on the
press. The `MOD_NOREPEAT` example says the thread *"will only receive another WM_HOTKEY message
when the 'b' key is released and then pressed again"* — i.e. **release is only implied by the
next press; it is never delivered.**

Everything normative in §3 follows from this one fact.

---

## 2. THE FULL DEFAULT KEY SET

### 2.1 Replay (the capture trigger) — 9 bindings

This is `default_binding_ladder()`, READ from `src/capture/trigger.cpp:59-76`
(file **17373 B, sha256 `2B4C2C3E3F4A12BEF2981176F55FE9CACA67C452195895D1C8B76799389139BE`,
mtime 2026-10-07 12:15:26**). **Reordered here — see §2.2, which is normative and which the
current code contradicts.**

> **THE TRIGGER IS A MOVING TARGET — re-run the pin before trusting any line below.**
> This file was written against a 16704 B revision (sha256 `795739268E…`, 12:12:41) and the
> lane changed it **twice in four minutes** while I was writing. Every `trigger.cpp` line in
> this document is against the 17373 B / 12:15:26 revision above. If your sha256 differs, this
> table is a HINT, not a citation. (AGENTS.md, rule 2.)

| order | key | `mods` | window | id | status on this box |
|---|---|---|---|---|---|
| 1 | **Ctrl+Alt+R** | `MOD_CONTROL\|MOD_ALT` | 30 s | — | **NEW BINDING, added by this contract.** Free by construction (`R` + two modifiers). |
| 2 | `Alt+F11` | `MOD_ALT` | 60 s | — | polled-only |
| 3 | `Ctrl+F12` | `MOD_CONTROL` | 60 s | — | polled-only |
| 4 | `F11` | 0 | 30 s | — | polled-only |
| 5 | `F10` | 0 | 30 s | — | polled-only |
| 6 | `Alt+F10` | `MOD_ALT` | 30 s | — | polled-only |
| 7 | `Alt+F9` | `MOD_ALT` | 30 s | — | **KNOWN OWNED by another program on this box** (`sotto_webview.py:1254-1256`) → polled-only |
| 8 | `PrintScreen` | 0 | 10 s | — | **DEMOTED — see §2.3** |
| 9 | `F12` | 0 | 30 s | — | **DEMOTED TO LAST — see §2.2** |

**POPULATION / WINDOW** for the whole table: **9 bindings**, from **1 vector**
(`trigger.cpp:59-76`), across a **file** P/WINDOW of 17373 B / mtime 2026-10-07 12:15:26,
**read 12:15 UTC-3**. The `Alt+F9` OWNED claim is POPULATION **2 measurements on 1 host**
(`sotto_webview.py:1254-1256` + `AGENTS.md`), WINDOW **this desktop session only** — it is a
point-in-time fact about one machine and must be re-probed, not inherited.

`mods` is the Win32 mask **without** `MOD_NOREPEAT`; `trigger.h:71-73` makes the trigger OR it
in itself *"so no caller can accidentally ship a repeating hotkey"*. Keep that.
`id` range `0x0000`–`0xBFFF` (READ, MS Learn); `trigger.h:194` starts at `0xA17E` — inside the
range. Keep.

### 2.2 F12 goes LAST. This contract contradicts the code on disk, deliberately.

`trigger.cpp:65` puts `{VK_F12, 0, "F12", 30.0}` **first**, and `trigger.h:229` justifies
it: *"F12 first is deliberate: NVIDIA's own overlay and most screen recorders default away
from it…"*

Microsoft Learn, Remarks, read 2026-10-07, says the opposite about F12 specifically:

> **"The F12 key is reserved for use by the debugger at all times, so it should not be
> registered as a hot key. Even when you are not debugging an application, F12 is reserved in
> case a kernel-mode debugger or a just-in-time debugger is resident."**

The lane's rationale ("most recorders default away from it") is a **convenience** argument.
The vendor's statement is a **reservation**. A convenience argument does not outrank a
reservation, so the order in §2.1 governs.

**This is a `trigger.cpp` change and it is NOT mine to make** (lane brief rule 5). The exact
hookup for the trigger lane: move the `{VK_F12, …}` entry from `trigger.cpp:65` to the **end**
of the vector in `default_binding_ladder()` (`trigger.cpp:59-76`), and amend the
`trigger.h:229` comment so the file stops asserting a reason the vendor contradicts.

Note `trigger.cpp:61-63` now justifies the order differently — *"the first binding that
REGISTERS is the one the receipt reports as the armed key"* — which is compatible with
reordering and does not require F12 to stay first.

**If F12 is kept at position 1 anyway, that is a decision to record, not a detail** — and the
arm summary must still print F12's real status rather than assuming it armed.

### 2.3 `PrintScreen` is unreliable *by design of the OS*, so it is demoted

READ, MS Learn, Return value:

> *"some pre-existing, default hotkeys registered by the OS (such as PrintScreen, which
> launches the Snipping tool) may be overridden by another hot key registration when one of
> the app's windows is in the foreground."*

So `PrintScreen` registration succeeds **only while our window has focus** and the OS
re-registers when it does not. It is not a global key. It stays in the ladder — a user who
wants it can have it — but it must never be first, and `register_error == 0` must never be
reported for it as "globally armed".

### 2.4 Overlay / panel (the Sotto half) — unchanged, and it does not collide

| key | action | source |
|---|---|---|
| **`Alt+C`** | toggle the caption panel | `sotto_webview.py:7067` (`--hotkey` default), `:4801` `toggle_panel` |
| `Alt+Shift+C` | fallback 1 | `:1259` `HOTKEY_FALLBACKS` |
| `Ctrl+Alt+C` | fallback 2 | `:1259` |
| `Ctrl+Shift+C` | fallback 3 | `:1259` |

**No collision with §2.1:** the replay ladder uses `R` and the F-keys; the overlay uses `C`.
`Ctrl+Alt+R` (new) and `Ctrl+Alt+C` (overlay) are distinct `vk`+`mods` pairs.
`HotkeyBinding::operator==` (`trigger.h:79`) compares exactly those two fields, so a duplicate
is detectable — and **§6.3 requires that check run at arm time.**

---

## 3. PRESS / HOLD / RELEASE — NORMATIVE

### 3.1 The two paths (both shipped; each survives what the other does not)

`trigger.h:8-33` already documents this correctly. Restated normatively:

| | **Path A — `RegisterHotKey`** | **Path B — `GetAsyncKeyState` poll** |
|---|---|---|
| cost when idle | a message, zero wakes | one wake per `kPollTickMs` = **8 ms** (`trigger.cpp:28`) |
| survives a held key | yes, via `MOD_NOREPEAT` (suppression is in the kernel) | only via the edge latch (`trigger.cpp:346`) |
| works if another app owns the key | **NO** → 1409 | yes, it reads physical state |
| works if the target runs elevated | **NO** (UIPI) — `trigger.h:27-29`; `Trigger::process_integrity_rid()` (`trigger.h:192`) exists to *report* this | yes |
| sees the UAC secure desktop | no | no (`trigger.h:32`) — **neither path can; state it, do not pretend otherwise** |

`arm()` (`trigger.h:146-147`) is correct to **never fail because a key was taken** — that is a
per-binding `BindingStatus` (`trigger.h:108-115`), and `armed()` is true when at least one path
works for at least one binding. Keep that.

### 3.2 PRESS — the only event either path can deliver

**A press produces exactly one `CutRequest`.** Normative:
- Path A: one `WM_HOTKEY`, suppressed thereafter by `MOD_NOREPEAT` until release+repress.
- Path B: edge detect at `trigger.cpp:332` (`down && !was_down`), latched at `:346`.
- **A single physical press must never produce two cuts** — including when BOTH paths are live
  for the same binding. §6.1 specifies the de-duplication.
- A press **never blocks**. `emit` (`trigger.cpp:392`) drops at `kQueueCapacity = 8` and
  counts `queue_refused` + logs. Law 1.

### 3.3 HOLD — semantics, and the one thing that is forbidden

**A hold is NOT a distinct product action, and it MUST NOT be built on `RegisterHotKey`.**

Why: §1 — `RegisterHotKey` never reports release, so "hold to mark, release to save the
marked interval" is **not implementable on Path A at all**. It is implementable only on Path B,
where a `down → up` transition on the latch is observable.

**NORMATIVE, and this is the rule L1 must not break:**
> The shipped replay binding is **press-to-save-the-last-N-seconds**, and nothing else.
> A held key produces **exactly one** cut at the moment of the press. **There is no
> release-triggered behaviour anywhere in v1.** A design that wants "hold to record, release to
> stop" must wait until a Path-B-only binding exists and must not inherit the instant-replay
> key's semantics.

Hold-time must still be **counted**, because a user who rests a finger on the key is
diagnosing something: `TriggerStats::autorepeat_suppressed` (`trigger.h:122`,
incremented `trigger.cpp:343` (poll) and `:297` (WM_HOTKEY path)) is that number, and it is what distinguishes "the key fired
once and the OS suppressed the repeats" from "the key fired once because the user released it".

### 3.4 RELEASE — normative

**No path delivers a release event, and v1 defines no action on release.** Release is
observable **only** as the precondition for the next press (Path A, `MOD_NOREPEAT`) and as the
`was_down → down` transition that rearms the latch (Path B). `trigger.h` has no release
callback and **must not grow one in v1** without changing this contract.

---

## 4. CONFLICT RESOLUTION — "ANOTHER APP OWNS THE KEY"

### 4.1 What actually happens, and the trap

READ, MS Learn: `RegisterHotKey` "typically fails if the keystrokes … have already been
registered for another hot key". The failure code observed in production on this box is
**1409** (`ERROR_HOTKEY_ALREADY_REGISTERED`), read from `app/webview/sotto_webview.py:1280`
("RegisterHotKey` → 1409"), and independently recorded in `AGENTS.md:416`.

**The trap, and it is the same trap `receipt-13` documents for a claim that was true when
measured:** *"0 hits" and "it registered" are both claims with a shelf life.* This box has
already changed under a receipt — `receipt-13` row 1 ("no hotkey anywhere in capture") was
correct at 11:39 and false by 12:12. **Re-run the probe; do not quote a date.**

### 4.2 The resolution ladder (normative, ordered)

1. **`arm()` never returns false because a key was taken** (`trigger.h:142-145`). A taken key
   is a `BindingStatus` (`trigger.h:114` `owned_by_other_process`), not a failure.
2. **Every binding is polled regardless of whether it registered** (`trigger.cpp:329-346`).
   This is why the ladder still works when a key is owned: Path B reads physical state and is
   immune to 1409.
3. **A press on an unregistered-but-polled binding is annotated, not silent** — `trigger.cpp:334-336`:
   *"key not registerable (…): fired by the poll path instead"*. Keep it: it is the difference
   between a key that works and a key the user will report as broken.
4. **Per-binding truth is reported, never aggregated** — `Trigger::arm_summary()`
   (`trigger.h:181`) and the arm line at `trigger.cpp:211-215`, which prints registered /
   polled-only / `poll_tick` / integrity / capacity. `arm_summary()` must name **every**
   binding's state; a summary that says "armed" when 8 of 9 are polled-only is a lie.
5. **The user's requested key is honoured first, then the fallback chain** — the production
   behaviour at `sotto_webview.py:1995`:
   `order = [requested] + [a for a in HOTKEY_FALLBACKS if a != requested]`, with
   `WARN HOTKEY_FALLBACK requested=… using=…` (`:2003-2004`).
   **The overlay key chain and the replay key chain are SEPARATE chains.** A taken replay key
   must never change which overlay key is live, and vice versa.
6. **If every key in a chain is taken, say so LOUDLY, once.**
   `warn_hotkey_unavailable` (`sotto_webview.py:1963-1982`) raises a one-off `MessageBoxW` on
   a dedicated thread, because *"the panel cannot be the messenger: nothing can open it."*
   The replay chain's equivalent has no panel at all — **it must log AND set a non-zero exit
   path**, or an armed-looking app with a dead key is the bricked-app failure this repo has
   already paid for (`sotto_webview.py:1988-1993`).

### 4.3 The UIPI case, which is NOT a key conflict

`trigger.h:27-29` and `Trigger::process_integrity_rid()` (`trigger.h:191-192`) exist for this:
a hotkey registered at **medium** integrity is not delivered to a window running **higher** —
and a game launched *"Run as administrator"* is exactly that. The arm line prints the
integrity RID (`trigger.cpp:215`).

**Normative:** an elevated target is **not** a key conflict and must never be reported as
1409. Path B survives it; Path A does not. Say which path is live.

---

## 5. WHAT L1 MUST NOT CHANGE

The in-flight implementation is sound on these points. They are load-bearing:

| # | what | where | why it matters |
|---|---|---|---|
| 5.1 | `arm()` owns the pump thread — there is no way to arm without one | `trigger.h:19-22` | *"The naive wiring — call RegisterHotKey from the capture thread and then sit in the capture loop — compiles, runs, reports 'armed', and never fires."* **READ, MS Learn:** the message "must be processed in the message loop". This is the #1 wiring bug and the header already forbids it. |
| 5.2 | `Trigger::take(&out, 0)` is the **non-blocking** consumer drain | `trigger.h:153` | the only thing standing between a wedged panel and the capture loop — see `integration-sotto-app.md` §1.3 |
| 5.3 | the edge latch line | `trigger.cpp:346` | a held key must produce exactly ONE cut; this is the both-colour gate |
| 5.4 | drop-with-a-counter at the queue | `trigger.cpp:392-397`, `queue.h:69` | law 1 |
| 5.5 | the short-ring case is **named**, not clamped | `trigger.cpp:378-382` | F7 in the failure matrix |
| 5.6 | `RingSpanProbe` is **borrowed** and one method wide | `trigger.h:97-104` | keeps the trigger decoupled from `Replay`'s ring |
| 5.7 | the cut is executed on the **capture** thread, never where it arrives | `integration-sotto-app.md` §1.3 Rule A | `issue_cut` reads `capture_qpc_` unlocked (`replay.cpp:210`) |

---

## 6. DEFECTS IN THE CODE ON DISK THAT THIS CONTRACT FORBIDS

Found by reading `trigger.cpp` (sha256 `2B4C2C3E3F4A…`, 17373 B, mtime 12:15:26) and
re-confirmed after the lane's second edit. **I did not edit them — they are L1's files**
(lane brief rule 5). Each is stated as a rule L1 can implement.

### 6.1 CRITICAL — the poll path ignores `mods`, so one press fires several bindings

`trigger.cpp:330`:
```cpp
const bool down = (ksf((int)bindings_[i].vk) & 0x8000) != 0;
```

**Only `vk` is tested. `bindings_[i].mods` is never consulted** — note that `ksf` (line 30:
`int real_keystate(int vk) { return GetAsyncKeyState(vk); }`) takes a single `vk`, so there is
nowhere for a modifier to enter the test. With the shipped ladder that has F12, F11 and F10 as
*plain* bindings **and** `Ctrl+F9`, `Alt+F9`, `Alt+F10`, `Alt+F11`, `Ctrl+F12` as modified
ones, pressing **Alt+F10** evaluates `GetAsyncKeyState(VK_F10)` → down, and matches **both**
binding `F10` and binding `Alt+F10`. The edge latch stops repeats; it does **not** stop two
different bindings firing on one press.

**RULE:** the poll path MUST test the modifier set. `GetAsyncKeyState(vk) & 0x8000` for the
key **and** `GetAsyncKeyState(VK_MENU/VK_CONTROL/VK_SHIFT) & 0x8000` for each modifier in
`mods`. A binding with `mods == 0` additionally requires **no** modifier key down — otherwise
`F10` fires while the user is typing `Alt+F10`. Without this the ladder is unusable and the
edge latch (5.3) proves nothing.

**Also required:** both paths live for the same binding, so a key that BOTH registers and is
polled can fire **twice**. **RULE:** de-duplicate per binding on `request_seq` — if Path A
delivered within `kRepeatGuardNs` (`trigger.cpp:26`, 50 ms) of Path B for the same `vk`+`mods`,
drop the second and count it. There is a `kRepeatGuardNs` constant already declared for
exactly this and it is **currently unused** in the poll path — that is the tell.

### 6.2 The UAC secure desktop — state it, do not solve it
`trigger.h:32` is right that neither path sees it. **RULE:** the arm summary must say so when
the app is armed, so "the key did nothing" is never mysterious during a UAC prompt.
`trigger.cpp:211-215` prints integrity; extend that line to name the secure-desktop limit.

### 6.3 Duplicate bindings must be refused at arm time
**RULE:** `arm()` compares every pair with `HotkeyBinding::operator==` (`trigger.h:79`) and
refuses the later duplicate with a named log line. §2.1 and §2.4 are disjoint today; a future
edit that adds `Ctrl+Alt+R` to the overlay chain must not silently double-fire.

---

## 7. ACCEPTANCE — WHAT "DONE" LOOKS LIKE, BOTH COLOURS

Every arm must be able to say NO. A trigger that cannot report failure is a bricked app with
a working-looking key.

| arm | colour | what it must prove | how it goes RED |
|---|---|---|---|
| **A** | GREEN | one press on a registered binding → exactly **1** `CutRequest`; a press held 2 s → exactly **1** | a held key yielding ≥2 → rc≠0 |
| **B** | RED | deleting `trigger.cpp:346` (the latch) in a **COPY** makes arm A produce ≥2 cuts | if the copy still passes, the latch is not load-bearing and arm A is vacuous |
| **C** | GREEN | pressing `Alt+F10` emits **exactly one** request, bound to the `Alt+F10` binding — not two, and not the plain `F10` one | two requests, or one bound to `F10` → rc≠0 (this is §6.1) |
| **D** | GREEN | every binding in the ladder reports its own true state in `arm_summary()`: registered / polled-only / owned-by-other / winerror | a summary reading "armed" with a taken key unreported → rc≠0 |
| **E** | GREEN | on this box, `Alt+F9` is reported **owned by another program**, and pressing it **still produces a cut** via the poll path | a run that either hides the conflict or drops the press |
| **F** | GREEN | `arm()` returns true even when every `RegisterHotKey` fails | `arm()` false → rc≠0 |
| **G** | RED | an arm where the pump thread is not started registers keys and **never fires** | this is the naive wiring `trigger.h:19-22` exists to make impossible; the gate must prove it |

**A SKIP is never a pass** (`design-notes/03-engine-ipc.md:149`).

**Gates that do not exist yet.** `trigger.h:35-37` asserts measurement by
`_main\_lane1-trigger-gate.ps1` (arms A/B/C/E) and cites `receipts\receipt-15-instant-replay-trigger.md`.
**Neither file exists** (§0). Until one does, no arm above has run. The integration step
gates the trigger into `src/capture/build.cmd` **first** (`trigger.cpp` is absent from the
compile line today) — a file that has never been compiled has no arms at all.