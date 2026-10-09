# SPEC 05 — THE OVERLAY HUD (the surface the user actually touches)

**Status: SPEC — nothing here is measured on this box yet.** Numbers marked ⚙ are engineering
decisions with the reasoning shown inline; a decision marked ⚙ is CLOSED, not open. There is no `TBD`
in this file: where a choice had to be made, it was made and the reason is written next to it.

Evidence labels, following `specs/03-capture-encode.md:18`:
`READ` = a vendor/other doc I opened, URL given · `READ-CODE` = a file+line in this repo or in
`H:\sotto` · `⚙` = our decision · **UNKNOWN** = nobody has shown it and a named lane must.

**A HUD that shows nothing on failure is the defect this product keeps paying for.** Every state in
§3 — including the four failure states this project has actually hit — has a visible representation,
a defined transition, and a pass condition in §6. That is the spine of this document.

---

## 1. THE OVERLAY SURFACE

### 1.1 What is drawn, and what is NOT

The HUD is a **single translucent plate, top-left of the foreground window's monitor**, carrying at
most three lines of text plus one status glyph plus one right-aligned timer:

```
 ●  RECORDING                             02:41
    gaming 1080p60 · ring 120s · 45 Mbps
```

Three lines is the ceiling. The state is legible in the **first 100 ms** at a glance from across a
desk; everything else is for the moment the user leans in. A fourth line is a design failure, not a
feature (`specs/03-capture-encode.md:221` — "A clip that cannot say how many frames it is missing is
not shippable" is the same discipline applied to text: every token on screen is a fact the HUD
computed, never a decoration).

**Never drawn:** a metrics graph, a timer bigger than the state name, a logo, a call-to-action, a
"press X to..." hint while recording. The HUD is a **readout**, not a control panel — the owner's
hands are on a controller.

### 1.2 The window: exact styles, exact reason for each

One top-level window, created once, owned by the capture process, **class `AireplayHudWindow`**.

| style | set? | why (normative) |
|---|---|---|
| `WS_POPUP` | **yes** | no title bar, no caption: a caption is a thing the user's mouse can grab, and this window is click-through by contract |
| `WS_EX_LAYERED` | **yes** | the ONLY documented route to a per-pixel-alpha window (`READ`: `SetLayeredWindowAttributes`, `https://raw.githubusercontent.com/MicrosoftDocs/sdk-api/docs/sdk-api-src/content/winuser/nf-winuser-setlayeredwindowattributes.md` — "A layered window is created by specifying `WS_EX_LAYERED` when creating the window with the `CreateWindowEx` function") |
| `WS_EX_TOPMOST` | **yes** | sits above the game window in Z-order without ever activating (`READ`: `SetWindowPos`, `https://raw.githubusercontent.com/MicrosoftDocs/sdk-api/docs/sdk-api-src/content/winuser/nf-winuser-setwindowpos.md` — `HWND_TOPMOST` "Places the window above all non-topmost windows. The window maintains its topmost position even when it is deactivated.") |
| `WS_EX_NOACTIVATE` | **yes** | **the single most important style in this file.** It is what makes it impossible for the HUD to steal focus from the game. `SetWindowPos` must always be called with `SWP_NOACTIVATE` to honour it (`READ`: same SetWindowPos URL — `SWP_NOACTIVATE` "Does not activate the window") |
| `WS_EX_TOOLWINDOW` | **yes** | keeps the HUD out of `Alt+Tab` and out of the taskbar; a recorder that appears in `Alt+Tab` is a recorder the user can alt-tab AWAY FROM mid-match |
| `WS_EX_TRANSPARENT` | **yes** | click-through: mouse input passes to the game. Without it the 480×96 plate is a hole in the user's aim |
| `WS_EX_APPWINDOW` | **no** | force it off after creation if the class defaults it on; it would put the HUD in the taskbar |
| `WS_EX_NOREDIRECTIONBITMAP` | **no** | **forbidden here.** The HUD draws with GDI into the DIB it hands `UpdateLayeredWindow`, and this style is incompatible with that path. Named explicitly so no lane adds it later |

**Activation is never requested.** `SetForegroundWindow` is never called by the HUD, for any reason,
in any state. (`READ`: the same SetWindowPos URL documents the consequence from the other side — "If
an application is not in the foreground, and should be in the foreground, it must call
`SetForegroundWindow`" — which is exactly the call this spec forbids the HUD from making.)

**After any `SetWindowLong`/style change, `SetWindowPos` must be re-issued** with
`SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED`, verbatim from `READ`: the same
SetWindowPos URL — "If you have changed certain window data using `SetWindowLong`, you must call
`SetWindowPos` for the changes to take effect."

### 1.3 How it composites — and the one technique we do NOT use

**The HUD owns no DXGI swap chain.** It renders into an offscreen `DXGI_FORMAT_B8G8R8A8_UNORM`
texture on **the same `ID3D11Device` the capture already created**
(`src/capture/d3d11_ctx.h`, `D3d11Context::createOnVendor(0x10DE)`, per `specs/03-capture-encode.md:71`),
reads it back once per frame into a staging texture, and publishes it with **one
`UpdateLayeredWindow(..., ULW_ALPHA)` call per frame**.

Why not a swap chain: a flip-model swap chain is composited by DWM and *nothing else in that window
is*. `READ`: `https://raw.githubusercontent.com/MicrosoftDocs/win32/docs/desktop-src/direct3ddxgi/dxgi-flip-model.md`
— "Use flip model in an `HWND` that is not also targeted by other APIs … When you use the flip model,
only Direct3D content in flip model swap chains that the runtime passes to DWM are visible. The
runtime ignores all other bitblt model Direct3D or GDI content updates." A text HUD needs GDI/DirectWrite
drawing. The two techniques are mutually exclusive on one `HWND`. We take GDI and pay a readback.

**The alpha rule, normative, one sentence:** *alpha reaches the screen only through
`UpdateLayeredWindow`'s `AC_SRC_ALPHA`; `SetLayeredWindowAttributes` is never called on the HUD
window.* `SetLayeredWindowAttributes` switches a layered window to a mode where the source alpha is
ignored, so a lane that "just adds a global fade" with it silently destroys per-pixel alpha and gets
a solid rectangle — this rule exists to make that failure impossible to write by accident.

**Alpha budget (⚙, all values ARGB, premultiplied):**

| element | colour | α | reason |
|---|---|---|---|
| plate | `0x0C0C10` | 204 (80 %) | a game is bright and moving; the plate must read as a hole cut in it without hiding the frame underneath. 80 % is the last value before the HUD starts to look like a wallpaper |
| plate outline | `0x000000` | 64 (25 %) | separates the plate from a dark scene. **No shadow, no blur** — a blur is a per-frame full-surface D3D pass for a 1-pixel visual gain; the outline is the same information for free |
| primary text | `0xF0F0F5` | 255 | max contrast against the plate |
| secondary text | `0xB4B4BE` | 204 (80 %) | one step down so the state name wins; equal weight would make the two lines compete |
| recording glyph | `0xE24A4A` | 255 | red is the universal "this is live" colour and it is the only saturated pixel on screen |
| saving glyph | `0xF0B43C` | 255 | amber: in-between, reads as transient without reading as failure |
| armed glyph | `0x56BE78` | 255 | green = ready, not doing anything |
| error glyph | `0xE0553A` | 255 | red-orange, deliberately distinct from the recording red so a failure never reads as "recording" |

**The fade is a single uniform multiplier applied to every pixel after compositing**, never a
per-element alpha. A per-element fade is how a 1-pixel magenta fringe appears at the plate edge and
gets blamed on the game's renderer.

**High contrast (`SPI_GETHIGHCONTRAST`)**: if the user has it on, the plate becomes opaque
(`α = 255`), the outline becomes `1 px solid 0xFFFFFF`, and every text colour becomes
`GetSysColor(COLOR_WINDOWTEXT)`. No transparency is honoured at all in this mode. ⚙ — because an
HUD at 80 % alpha over a high-contrast desktop is a legibility bug the user cannot fix.

### 1.4 Draw order — bottom to top, one pass, one publish

1. clear the render target to transparent (`0x00000000`)
2. plate: rounded rect, **radius 8 px × dpi**, fill + 1 px outline
3. status glyph (12 px disc), left edge, vertically centred on the plate
4. primary line — state name, `Segoe UI Semibold` (fallback `Tahoma`), the font size from §5
5. secondary line — the reason / the facts, `Segoe UI` regular, 80 % α
6. tertiary line — **only in `RECORDING`**, the mode/bitrate/ring line
7. right-aligned timer — `Segoe UI Semibold`, **tabular figures** (`SPI_GETFONTSMOOTHING`-independent;
   the font is created with `CLEARTYPE_QUALITY` and the digits are laid out in a fixed advance so the
   timer does not jitter every second)
8. fade multiply (uniform, §1.3)
9. **readback + `UpdateLayeredWindow` — exactly once**

### 1.5 Refresh: a paced thread, not a timer, not a busy loop

**The HUD runs on its own thread with a QPC-paced sleep at 16.67 ms (60 Hz).** It is never a
`WM_TIMER` (whose resolution is poor and whose priority is not ours) and never a spin loop (law 8 —
`AGENTS.md:306-317`, the measured 731.9 % CPU incident: *"For our lanes: a measurement on this machine
runs with ≤2 threads"*; the same restraint is a product requirement, not only a lane one).

**The idle rule, normative and the reason the HUD is affordable: the thread repaints ONLY when its
rendered content hash or its fade alpha changed.** Steady `IDLE` costs one state change per event —
**measured target ≤ 0.5 % of one core** (⚙; if this is ever exceeded the defect is the hash, not the
rate). `RECORDING` repaints at 60 Hz because the timer changes every second and the glyph pulses;
`SAVING` repaints at 60 Hz for the same reason; `ERROR` repaints at **10 Hz** — an error must not
move, and a static error at 60 Hz is the HUD burning a core to say nothing.

The HUD thread **never touches the ring, the encoder, or the WGC session** (law 1,
`AGENTS.md:280-282`), and it holds **no lock the capture path holds**. Its only inputs are two atomics
(the desired state, the desired alpha) and one immutable snapshot pointer.

### 1.6 The rule the HUD inherits from the Sotto panel-flash incident — stated once, not re-litigated

Sotto measured that a pywebview shell **maps its window on every navigation start** and that the cure
was to **refuse the mapping at full opacity while nobody asked**. The receipt is in `H:\sotto\AGENTS.md:306-327`
and the implementation is `H:\sotto\app\webview\sotto_webview.py:3365` (`_gate_form_show`), refused at
`:3404-3411`, with `_on_before_show` at `:3187` and `_reassert_hidden` at `:4450`.

**The rule the HUD inherits, verbatim in effect:**

> **A window this product maps is a promise the user asked for. The HUD window is NOT CREATED VISIBLE
> and NOTHING IS PAINTED OR PUBLISHED until a HUD binding fires or the owner passed `--show-hud`.**
>
> Concretely, and in this exact order, because **`UpdateLayeredWindow` updates content, size, position
> and alpha — it does NOT set `WS_VISIBLE`, so it cannot map anything by itself**:
>
> 1. **Creation:** `CreateWindowEx` with `WS_EX_LAYERED` and **`WS_VISIBLE` clear**. **No**
>    `ShowWindow`, **no** `SWP_SHOWWINDOW`, **no** `UpdateLayeredWindow`. An unmapped window has no
>    alpha state at all — "invisible" here means *never published*, not *published at alpha 0*.
> 2. **`Hud::show()` — the ONLY mapping site, reachable only from a HUD binding or `--show-hud`:**
>    a. first `UpdateLayeredWindow` at **α = 0**, which sizes and positions the window;
>    b. then `SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE |
>       SWP_NOACTIVATE | SWP_SHOWWINDOW)` — **`SWP_SHOWWINDOW` (`0x0040`) is what maps it**
>       (`READ`: `SetWindowPos`, `https://raw.githubusercontent.com/MicrosoftDocs/sdk-api/docs/sdk-api-src/content/winuser/nf-winuser-setwindowpos.md`);
>    c. the next frame publishes α > 0.
>    **Order (a)→(b)→(c) is load-bearing:** mapping before the window is sized and positioned is a
>    one-frame flash of an unsized rectangle at the wrong origin — the exact class of flash §1.6
>    exists to prevent. Between (b) and (c) the window is mapped at α = 0, which is invisible.
> 3. **`Hud::hide()`** is `ShowWindow(hwnd, SW_HIDE)` and nothing else.
>
> There is no "warm-up" paint, no "armed" paint, no 1-frame paint at start-up.
> This is also why §1.3's ban is absolute and load-bearing: calling `SetLayeredWindowAttributes` even
> once (including to set alpha 0) puts a layered window into a different mode, and the whole
> `UpdateLayeredWindow` publishing path in §1.3 stops being the mechanism. **The HUD's alpha comes
> from exactly one API, always.**

This matters more than a normal window because **the HUD's whole purpose is to appear over a game**:
a HUD that flashes for 60 ms at launch is a HUD that will flash for 60 ms every time the user starts
the app to watch a replay, and the Sotto census found exactly that — **~63 ms of visible form in 18 of
20 launches** (`H:\sotto\AGENTS.md` bullet "A panel hot reload…", the 25 ms
`_main/panel-startup-flash-census.py` result). **PASS-1 in §6 exists only to keep that history from
repeating here, and its cadence is 25 ms for the same reason: a 60 s census cannot see a 63 ms flash.**

### 1.7 Not burned into the recording — a decision, with its cost

**The HUD is composited on screen only. It is NOT drawn into the captured frame.** ⚙

Rationale, both halves measured rather than assumed: (a) compositing it into the capture path would
add a full-frame blend to the **only pixel work this product owns** — `specs/03-capture-encode.md:79-93`
names that conversion as the one transfer that is ours and measures it at **0.010–0.017 ms/frame** at
1080p, so the addition is real and would be paid on every frame forever; (b) a burned-in HUD becomes
**onscreen text** in the index, i.e. it pollutes the OCR channel and every search built over it
(law 4, `AGENTS.md:287-289`).

**`hud.burn_into_capture: false` is the shipped default and the key is read, not dead** — setting it
`true` compiles the blend into the existing `nv12_convert` pass and is a documented opt-in, not a
TBD. It is listed here so the next lane knows the flag exists and what it costs.

---

## 2. FULLSCREEN EXCLUSIVE vs BORDERLESS — the part a spec must not wave at

### 2.1 The fact, stated without hedging

Two different things get called "fullscreen" and they differ in whether the Desktop Window Manager is
composing the screen at all:

- **Borderless windowed** (what almost every modern game uses when you pick "borderless", and what
  Windows itself does for most store apps): the game is an ordinary top-level window; DWM composes
  every top-level window together; `HWND_TOPMOST` is honoured and the HUD is visible. **`READ`**:
  flip-model doc (`dxgi-flip-model.md`) — "In the flip model, all back buffers are shared with the
  Desktop Window Manager (DWM). Therefore, the DWM can compose straight from those back buffers."
  A layered window is composited by the same DWM pass, so both are on screen together.
- **Exclusive fullscreen**: the game takes the display mode and its swap chain presents **directly to
  the display**; the desktop is not composited for that display. There is no Z-order to win.
  `SetWindowPos(HWND_TOPMOST)` **returns success** and changes the Z-order, and **nothing appears**,
  because there is no compositor to place it in front of anything.

**So the honest answer, and it is the answer real overlays give up on too:** *a normal window cannot
overlay exclusive fullscreen, and `SetWindowPos` will not tell you it failed.* The return value is not
the signal. §2.5 defines the signal that is.

### 2.2 What we do NOT do, and why — the injection ban

**The HUD NEVER injects a DLL into the game's process and NEVER hooks its swap chain.** ⚙

This is the technique that makes NVIDIA's overlay work in exclusive fullscreen. We refuse it, and the
reason is not difficulty: it is that a user-side injected overlay is an anti-cheat detection surface
(EAC/BattlEye/Vanguard all scan for foreign modules and injected hooks), and the outcome for the
user of this product is a **ban of their game account**, not a missing HUD. A recorder that can get
you banned is worse than a recorder that shows nothing. **This decision is closed and applies to every
future lane in this repo.**

### 2.3 What we DO do in exclusive fullscreen — three mechanisms, in order

**(1) Detect it** (§2.4, normative, `hud.exclusive_mode`).

**(2) In exclusive fullscreen the HUD reports honestly instead of pretending.** State
`HIDDEN_EXCLUSIVE` (`§3.2`): **the HUD window is not mapped at all** — obeying §1.6 strictly — and the
state is carried by three channels that do not need the display:
  - the **tray icon glyph** (`Shell_NotifyIcon`, `NIM_MODIFY`) changes to the error glyph and its
    tooltip carries the exact sentence;
  - a **balloon/toast** (`NIF_INFO`, `Shell_NotifyIcon`) fires **once** on entering the state — once,
    because a toast that repeats every second is a toast the owner learns to dismiss by reflex;
  - the **log** (`hud_state=` line per transition, and a `hud_exclusive=1` line per second while
    held, so a post-mortem has the duration).

**(3) Forced borderless — OFF by default, one keystroke, and the HUD says it did it.**
`hud.force_borderless: false` in config. When `true`, on detecting exclusive fullscreen the app:
  1. captures the desktop `DEVMODE` (`EnumDisplaySettings(ENUM_CURRENT_SETTINGS)`) **before** the
     mode change, if it has not already;
  2. calls `ChangeDisplaySettingsEx(NULL, &desktopMode, CDS_UPDATEREGISTRY | CDS_RESET, NULL)` to put
     the desktop mode back;
  3. `SetWindowPos(gameHwnd, HWND_TOP, 0, 0, w, h, SWP_NOACTIVATE | SWP_FRAMECHANGED)` on the
     foreground window;
  4. shows the HUD, which states verbatim: `forced borderless — Alt+F7 to refuse`.

**This is invasive to another application's display mode, so it is off by default, it is announced
before it happens, and the refusal key is always live.** ⚙ The alternative — leaving the user staring
at a fullscreen game with no HUD and no explanation — is the failure this whole document exists to
prevent. The status line for the trade is: `H:\sotto\AGENTS.md` measured the same class of problem
(`SOTTO_LANG_ID` default choice) and the rule it landed on is that a product must **say what it chose
and why**; this spec says it in the HUD itself.

### 2.4 Detecting exclusive fullscreen — three signals, all cheap, none of them a guess

The HUD thread evaluates these **every 250 ms** (not every frame — a mode query is a kernel call)
and enters/leaves `HIDDEN_EXCLUSIVE` on a **2-sample hysteresis** (2 samples to enter, 2 to leave:
without it a mode that flaps once at a cutscene flashes the HUD in and out).

| # | signal | API | interpretation |
|---|---|---|---|
| S1 | **mode change** | `EnumDisplaySettings(monitor, ENUM_CURRENT_SETTINGS, &dm)` compared to the previous sample on `dmPelsWidth`/`dmPelsHeight`/`dmBitsPerPel`/`dmDisplayFrequency` | a change while a foreground window covers ≥ 98 % of the monitor is an exclusive-mode entry/exit. This is the primary signal |
| S2 | **foreground geometry** | `GetWindowRect(GetForegroundWindow())` vs `MonitorFromWindow`/`GetMonitorInfo` rect | ≥ 98 % coverage + a class we did not create + no `WS_THICKFRAME` ⇒ a game in some fullscreen mode (both kinds match, so this narrows S1, it does not replace it) |
| S3 | **DWM still alive on that monitor** | `EnumDisplayMonitors` + `IsWindowVisible` of the desktop's `WorkerW`/`Progman` | an exclusive app does not hide the desktop shell the way a lock screen does; a **missing** shell is corroboration, never a trigger |

**The HUD never calls `SetProcessDpiAwarenessContext`, `ChangeDisplaySettingsEx` or anything else
inside the detector.** S1-S3 are read-only. A detector that changes display state is a detector that
can strand the user on a wrong mode, and `H:\sotto\AGENTS.md` has the receipt for what a wrong
default did there.

**UNKNOWN (named lane, not a TBD):** the false-positive rate of S1+S2+S3 across a real game library
(how often a borderless game trips it, how often an exclusive game hides it). Mitigation decided now:
on any **ambiguous** sample the HUD assumes **borderless** (shows), because the cost of showing the
HUD when it cannot be seen is zero and the cost of hiding it when it could is a broken product.

### 2.5 What the exclusive refusal actually looks like — observable, not inferred

`SetWindowPos` returning non-zero proves nothing (§2.1): `SWP_SHOWWINDOW` succeeding only means the
window is mapped, not that it is in front of the game. **The observable is the pixel, and the pixel
proof is PASS-4** (§6) — the monitor-item WGC grab that must contain the plate's colour inside the
expected inset rect. This is the same discipline `specs/03-capture-encode.md:231` already demands of
the capture path — *"protected content / DRM / exclusive fullscreen | frame-liveness watchdog … → …
stop claiming to record"* — applied to the HUD.

**The HUD therefore never reports visibility from an API return value.** It emits two separate facts
and they are not the same fact:

| log field | meaning | can it be false while the HUD is fine? |
|---|---|---|
| `hud_mapped=1` | `SWP_SHOWWINDOW` succeeded, the window is mapped | no — this is the low bar |
| `hud_pixel_proven=1` | PASS-4's grab found the plate's pixels | **yes — and that is the point** |

**`hud_pixel_proven=0` with a named reason is the normal state on this box today**, because
monitor-item WGC was measured refused here — `CreateForWindow`/`CreateForMonitor` → `E_ACCESSDENIED`
for every item while `IsSupported()` still returned true (`specs/03-capture-encode.md:8-16`). While
that holds, the HUD must log `hud_pixel_proven=0 reason=wgc-denied` and **a lane may not write that
the overlay was seen over a game.** When PASS-4 SKIPs, PASS-13's census is the only proof available and
it proves only that *a* window was mapped — the log says so in those words, not in the stronger ones.
(The claim "exclusive fullscreen unmaps the HUD" is still discharged by **PASS-7**, which needs no
pixel grab: it asserts the mapping is *released*.)

### 2.6 Protected content (DRM) — the same rule, different cause

If a capture item is refused or black **because the window is protected** (DRM video, some banking
and streaming apps), the HUD enters `BLOCKED_PROTECTED` (§3.2) and names the window class it could
not read. This is not a spec invention: NVIDIA shipped the same user-facing behaviour — `READ`:
`https://www.nvidia.com/en-us/software/nvidia-app/release-highlights.md` — *"NVIDIA app overlay now
notifies users if protected content restricts ShadowPlay recording."* We ship the notification; we do
not ship the capture.

---

## 3. THE STATE MACHINE

### 3.1 The states

`HudState` is one enum. The **HUD's word and the log's word are the same string** — the bug this
project already paid for was a verdict that disagreed with the emitted state inside one run
(`H:\sotto\AGENTS.md`, verdict-order bullet, measured on disk in
`worker/runs/exit3-armB-worker.jsonl`: `done.verdict "all-candidate-taps-flat"` beside
`state="silent-device"` and exit 3). Rule: **`hud_state=` in the log is the enum name, verbatim, and
nothing else.**

| state | meaning | glyph | plate α |
|---|---|---|---|
| `HIDDEN` | window exists at α=0, nothing mapped | — | 0 |
| `ARMING` | a HUD binding fired; the capture self-test (law 6) has not returned | saving (amber, pulsing) | 204 |
| `IDLE` | armed, recording nothing, ring filling | armed (green) | 204 |
| `RECORDING` | manual record running | recording (red, pulsing 1 Hz) | 204 |
| `SAVING` | the cut/write is running (spec 01 §4 stage S1) | saving (amber, pulsing) | 204 |
| `HIDDEN_EXCLUSIVE` | exclusive fullscreen detected; HUD unmapped, tray+toast carry the state | error | n/a |
| `ERROR_SILENT_DEVICE` | the capture opened a device and the device delivered silence | error | 204 |
| `ERROR_DEVICE_EXHAUSTED` | every candidate capture source was refused or flat | error | 204 |
| `ERROR_CORRUPT_ROW` | a queue/IPC record arrived malformed and was rejected | error | 204 |
| `ERROR_ENCODER_REFUSED` | no encoder initialised ⇒ the hotkey was never armed (law 6) | error | 204 |
| `ERROR_PROTECTED` | protected content blocks capture (§2.6) | error | 204 |

### 3.2 Transition table — every edge, no gaps

| from | event | to | HUD behaviour | latency budget |
|---|---|---|---|---|
| `HIDDEN` | HUD binding pressed (or `--show-hud`) | `ARMING` | `ULW(α=0)` → `SWP_SHOWWINDOW` → fade in (§1.6 step 2) | **≤ 16 ms** to first mapped frame |
| `ARMING` | self-test OK (`specs/03` §5) | `IDLE` | line 2 becomes `armed · H.264 · 45 Mbps · ring 675 MB` | ≤ 250 ms after the test returns |
| `ARMING` | self-test failed, no encoder | `ERROR_ENCODER_REFUSED` | **and the replay hotkey is NOT armed** (law 6, `AGENTS.md:293-299`) | ≤ 250 ms |
| `IDLE` | manual record pressed | `RECORDING` | timer starts; third line appears | ≤ 16 ms |
| `RECORDING` | stop pressed, or ring cut requested | `SAVING` | timer freezes at its final value | ≤ 16 ms |
| `SAVING` | clip written | `IDLE` | one line `saved clip_0644.mp4 · 12.4 s · 71 MB` for 2 s, then back | ≤ 250 ms after `close()` returns |
| `SAVING` | no IDR in ring ⇒ the cut refuses | `ERROR_*` | **the error names the refusal** (`specs/03` §2.7: "A file that a decoder cannot start is worse than an error") | ≤ 250 ms |
| any non-error | exclusive fullscreen detected (2 samples, §2.4) | `HIDDEN_EXCLUSIVE` | window **unmapped**; tray glyph + one toast + `hud_exclusive=1` per second | ≤ 500 ms (2 × 250 ms) |
| `HIDDEN_EXCLUSIVE` | exclusive left (2 samples) | previous | re-map if that state was non-`HIDDEN` | ≤ 500 ms |
| any | device opened and delivered digital silence | `ERROR_SILENT_DEVICE` | sticky, §3.3 | ≤ 1 s |
| any | every candidate capture source flat/refused | `ERROR_DEVICE_EXHAUSTED` | sticky, §3.3 | ≤ 1 s |
| any | malformed IPC record | `ERROR_CORRUPT_ROW` | sticky, §3.3, **non-fatal** | ≤ 1 s |
| any error | owning subsystem recovers | `IDLE` | error line replaced, `recovered` token in the log | ≤ 500 ms |
| any error | HUD binding pressed | `ARMING` | **re-arms**, because the user pressing the key is a request to look again | ≤ 16 ms |
| any | `WM_DISPLAYCHANGE` / `WM_DPICHANGED` / foreground moved to another monitor | same | **re-anchor + re-scale, keep the state** | ≤ 250 ms (debounced) |
| any | process exit | — | `WM_DESTROY`, `PostQuitMessage`, no orphan window | — |

### 3.3 The four failure states — what they are, where they come from, what the HUD says

**A HUD that shows nothing on failure is the defect the owner keeps paying for.** Each of these is a
failure this repo or its sibling has **actually measured**; none is hypothetical.

**`ERROR_SILENT_DEVICE`** — the capture opened a device, delivered a full window, and that window
was digital silence below the peak floor. Source: `H:\sotto\worker\sotto_worker.py:4390`
(`state="silent-device"`), with the verdict at `:2882` and the exit code 3 at the same site. The
measured shape: `H:\sotto\docs\research\12-audio-level-contract.md:38` quotes
`worker/runs/gate-live-silence.jsonl:11` — `"state": "silent-device" … "peak": 9.2e-05, "peak_floor": 0.002`.
**HUD line 2: `peak 9.2e-05 < floor 0.002 — nothing is routed into it` and the state name is the
first thing on screen.** Not "error 3". Not "device issue". The number that failed, and the number it
had to beat.

**`ERROR_DEVICE_EXHAUSTED`** — every candidate source was refused or flat. Source:
`H:\sotto\worker\sotto_worker.py:4342` (`state="device-exhausted"`, with `reason=outcome` and a
`detail` naming the tap window and floor). **HUD line 2: the ladder's last reason verbatim** — the app
must be able to say which rung failed, because the fix is per-rung (plug a cable back, pick a
different output, unlock a device).

**`ERROR_CORRUPT_ROW`** — a queue record arrived malformed. Source in **this** repo:
`src/engine/queue.h:32-47` (`LineReader` — "A line is only delivered once its `\n` has arrived …
`finish()` is EOF: a non-empty tail means the peer died mid-record, so it is REJECTED and counted,
never delivered"), `:69-71` (`Queue::push` "false == dropped"), and
`docs/design-notes/03-engine-ipc.md:101` (a string containing any byte `< 0x20` is **REJECTED and
counted** as `enc_rejected`, because "an unescaped `\n` inside a string would split one message into
two"). **This state is non-fatal and the HUD must say so**: the clip is already written (law 2,
`AGENTS.md:283-284`), so a rejected row costs a **count**, not a recording. **HUD line 2:
`1 record rejected (malformed) — recording unaffected`**, and the state auto-clears after the
recovery the store already performs.

**`ERROR_ENCODER_REFUSED`** — law 6 (`AGENTS.md:293-299`): no encoder ⇒ **the replay hotkey is never
armed**. The HUD is the only place this can be seen before the user presses a key that does nothing.
**HUD line 2: the encoder's raw status and `nvEncGetLastErrorString`, verbatim**
(`specs/03-capture-encode.md:251-253`). This state and `specs/03` §5 are one design.

### 3.4 Error presentation — three rules, because errors are where HUDs are worst

1. **Sticky.** An error state persists until the owning subsystem recovers or the user presses the
   HUD key — **never a timed disappear**. An error that vanishes before it is read is a bug report
   the owner has to file with a screenshot of nothing. (Contrast the transient 2 s success line,
   which is genuinely transient.)
2. **The state name is the first token and it is the enum name.** No localised string, no emoji, no
   paraphrase. `ERROR_SILENT_DEVICE` is what the log says, what the receipt says, and what the HUD says.
3. **Every error carries the one number or one string that would let the owner act on it.** An error
   line with no actionable datum is decoration.

---

## 4. THE HOTKEY MAP

### 4.1 What is NVIDIA-attested and what is our decision — separated, because we could not verify the table

**NVIDIA's own site was reachable for exactly two hotkey facts, and only two.** `READ`, both opened:

- `https://www.nvidia.com/en-us/software/nvidia-app.md` — *"NVIDIA ShadowPlay simplifies recording of
  videos and screenshots, featuring DVR-style Instant Replay, enabling users to instantly save the
  last 30 seconds of gameplay."* and, under `## NVIDIA Overlay`, *"Display real-time FPS and
  performance statistics through the newly updated NVIDIA overlay."* **This page names no key.**
- `https://www.nvidia.com/en-us/software/nvidia-app/release-highlights.md` — *"Configure via
  **Alt+Z** > Settings > Video Capture"*; *"Enable this feature in the overlay using **Alt+Z** >
  Statistics > Statistics View > DLSS."*; *"press **Alt+G** to speak with G-Assist"*; and, on the same
  page, *"Fixed an issue that prevented the use of Numpad keys for overlay shortcuts"*.

**So: `Alt+Z` is NVIDIA-attested as the overlay key, and `Alt+G` is NVIDIA-attested as G-Assist.**
The `Alt+F1…F12` ShadowPlay table that circulates on forums **was not verifiable from a page I could
open** (`nvidia.custhelp.com` returned an Oracle error page on every attempt during this lane, and the
NVIDIA knowledge-base article resolved to a 404). This spec therefore **does not claim** those
defaults as NVIDIA's. The map below is **our decision**, designed to (a) not collide with the one
NVIDIA key we could verify, (b) match the ladder lane L1 already shipped, (c) never require `MOD_WIN`,
because Microsoft reserves those (`READ`: RegisterHotKey doc,
`https://raw.githubusercontent.com/MicrosoftDocs/sdk-api/docs/sdk-api-src/content/winuser/nf-winuser-registerhotkey.md`
— `MOD_WIN` "Keyboard shortcuts that involve the WINDOWS key are reserved for use by the operating
system"), and (d) be remappable.

### 4.2 The map — every binding, with its semantic and its geometry

`semantic` is the contract the HUD binding obeys. `L1 codes against this table, not against ours.`

| # | binding (`vk` + `mods`) | name | semantic | window_s | action | rationale |
|---|---|---|---|---|---|---|
| H1 | `VK_F9` \| `MOD_ALT` | `Alt+F9` | **press** | 30 | save last 30 s | the primary act; matches L1's shipped ladder row `trigger.cpp:69` |
| H2 | `VK_F9` \| `MOD_CONTROL` | `Ctrl+F9` | **press** | 30 | save last 30 s (duplicate) | L1's second rung, `trigger.cpp:68` — a duplicate so a machine that owns `Alt+F9` still has one free |
| H3 | `VK_F10` \| `MOD_ALT` | `Alt+F10` | **press** | 30 | save last 30 s (duplicate) | L1's rung, `trigger.cpp:70` |
| H4 | `VK_F11` \| `MOD_ALT` | `Alt+F11` | **press** | 60 | save last 60 s | L1's rung with a longer window, `trigger.cpp:71` — the "I needed more" key |
| H5 | `VK_F12` \| `MOD_CONTROL` | `Ctrl+F12` | **press** | 60 | save last 60 s (duplicate) | L1's rung, `trigger.cpp:72` |
| H6 | `VK_SNAPSHOT` \| `0` | `PrintScreen` | **press** | 10 | save last 10 s | L1's rung, `trigger.cpp:73`; 10 s because that key is the single most contended on a gaming PC and a short window is the least annoying if it leaks to another app |
| H7 | `VK_F10` \| `MOD_CONTROL` | `Ctrl+F10` | **press** | — | **toggle manual record** (stop ⇒ `SAVING`) | ⚙ new. The one binding that is not a replay save, because `RECORDING` needs a key that is not also the save key |
| H8 | `VK_Z` \| `MOD_ALT` | `Alt+Z` | **press** | — | **toggle HUD** (show ⇄ hide) | ⚙ **deliberately `Alt+Z`**: it is NVIDIA's own overlay key (`§4.1`), so a user who has both installed is already used to the muscle memory, and this product is a ShadowPlay clone — matching the key it clones is the feature. **Consequence, stated in §4.4: we refuse to register it if NVIDIA's overlay owns it** |
| H9 | `VK_S` \| `MOD_ALT` | `Alt+S` | **press** | — | **cycle HUD anchor** (TL → TR → hide) | ⚕ new. Owner-only convenience; costs nothing |
| H10 | `VK_F7` \| `MOD_ALT` | `Alt+F7` | **press** | — | **refuse forced borderless** / re-arm it | ⚙ the refusal key promised by §2.3(3) |

**`window_s` semantics** are L1's: `CutRequest::requested_window_s` and
`shorter_than_requested` (`src/capture/trigger.h:84-95`). When the ring cannot give the requested
span the HUD must show it, not clamp silently — L1's own header says so (`trigger.h:47-53`:
*"you press the key, you get a 4-second clip and no explanation"* is the failure).

**`press` / `hold` / `release`, defined once:**

- **press** — act on the **down edge**, once. Autorepeat is suppressed twice over: by `MOD_NOREPEAT`
  (`READ`: RegisterHotKey doc — `MOD_NOREPEAT` `0x4000` "Changes the hotkey behavior so that the
  keyboard auto-repeat does not yield multiple hotkey notifications") **and** by L1's per-binding
  edge latch (`trigger.h:189`, `std::vector<uint8_t> held_`).
- **hold** — act **continuously while down**, re-firing every 1000 ms. **No binding in this table uses
  it.** It is defined because L1's `GetAsyncKeyState` path is level-triggered and the next lane will
  ask; the definition exists so the answer is not re-litigated.
- **release** — act on the **up edge**. **No binding in this table uses it.** Defined for the same
  reason.

### 4.3 The behaviour when another app owns the key — and the HUD's obligation to say so

`RegisterHotKey` fails with `ERROR_HOTKEY_ALREADY_REGISTERED` when another process owns the
combination; `BindingStatus::owned_by_other_process` already exists to carry that
(`READ-CODE`: `src/capture/trigger.h:108-115`). **Every HUD binding therefore has exactly three
outcomes, and none of them is silent:**

1. **Registered** — normal. The binding is live and the HUD shows its name.
2. **Taken by another process** — the `GetAsyncKeyState` poll still watches it (L1's header,
   `trigger.h:24-31`: the poll "works even when the key IS already registered by somebody else — it
   reads the physical key state, not an owned registration"), so the binding **still works**, and the
   HUD marks it `pinned` in the binding line. It does **not** disable the key, because a key that
   works and says it is pinned is strictly better than a key that silently died.
3. **Neither path can see it** — only possible on the **UAC secure desktop**, which neither path can
   reach (`READ-CODE`: `trigger.h:32` — "cannot see the UAC secure desktop (a different desktop);
   neither path can"). **This is the only case where the HUD says the key does not work**, and it
   says it with the reason.

**The HUD's line 3 (when the state is not `RECORDING`) is the binding line:**
`Alt+F9 live · Alt+Z live · Ctrl+F10 taken by another app`. A trigger whose keys have silently
degraded is the exact class of defect `specs/03-capture-encode.md:250-253` calls "a dead hotkey that
says why beats a live hotkey that does nothing".

### 4.4 The `Alt+Z` collision rule — stated because it is a real conflict with NVIDIA

If NVIDIA's overlay (or anything else) has registered `Alt+Z`, this product **does not fight for it**
and **does not fall back to a different key without saying so**:

1. `RegisterHotKey(Alt+Z)` → `ERROR_HOTKEY_ALREADY_REGISTERED` ⇒ binding is `pinned` per §4.3(2);
   the poll still works; the HUD says `Alt+Z pinned`.
2. `Alt+Z` is **never re-bound to a different combination behind the user's back.** A product that
   moves your key is a product you cannot configure.
3. **The NVIDIA App's own behaviour with `Alt+Z` is cited in the log, not emulated:** the release
   notes show `Alt+Z` navigating a settings tree (`Alt+Z > Settings > Video Capture`,
   `§4.1`), which is a full overlay. Our `Alt+Z` shows only the HUD. If both run, pressing `Alt+Z`
   shows whichever overlay registered first — an ambiguity we **document** rather than solve by
   stealing the key.

### 4.5 What is NOT measured about all of this

`READ-CODE`: `src/capture/trigger.h:34-38` states it plainly for the trigger, and it stands for the
HUD keys too — *"WHICH PATH FIRES INSIDE A FULLSCREEN GAME IS **NOT MEASURED IN-GAME** — no game was
run."* **UNKNOWN:** that no lane may write "the hotkey works in-game" until a lane runs one real
exclusive-fullscreen game and one real borderless one and records which path fired
(`from_registerhotkey` vs `from_async_poll`, both already counted at `trigger.h:119-128`).

---

## 5. PARAMETERS — every number, its unit, and why it is that number

| parameter | value | unit | reason |
|---|---|---|---|
| `hud.refresh_hz` | **60** | Hz | matches the 60 fps gaming mode (`specs/01` §1) so the HUD's own motion cadence cannot alias against the frame the user is watching. **UNKNOWN:** whether a 30 Hz HUD is indistinguishable on this panel — a sweep is a lane, not an assumption |
| `hud.repaint_idle` | **on content change only** | — | an idle HUD that repaints at 60 Hz burns a core to redraw identical pixels; law 8 (`AGENTS.md:306-317`) |
| `hud.error_repaint_hz` | **10** | Hz | an error must not shimmer; 10 Hz is enough for the amber/red pulse and cheap enough to be free |
| `hud.fade_in_ms` | **120** | ms | fast enough that pressing the key feels like the key worked **in the same breath**; slower reads as lag, and a user who is unsure whether the key registered presses it again |
| `hud.fade_out_ms` | **250** | ms | asymmetric on purpose: **fade out slower than in**, so the state is still readable at the moment it leaves |
| `hud.ease_in` | `easeOutCubic` | — | starts fast, so the first frame is already visible; a linear fade at 120 ms spends its first 30 ms below 25 % α and looks broken |
| `hud.ease_out` | `easeInQuad` | — | lingers at readable α, then leaves; the mirror of the above |
| `hud.success_hold_ms` | **2000** | ms | one glance, one read. Longer and it obstructs the game; shorter and the user misses the filename |
| `hud.inset_px` | **round(24 × dpi/96)** | px | DPI-derived, so 4K-at-200 % behaves identically to 1080p-at-100 %. It clears the Windows toast corner (~16 px) and the HUD strip most games put top-left |
| `hud.plate_max_w_px` | **480 × dpi/96** | px | wide enough for `ARMING · H.264 · 45 Mbps · ring 675 MB` at the §5 font sizes; beyond that the plate is a billboard over the fight |
| `hud.plate_min_w_px` | **240 × dpi/96** | px | a two-word state name (`IDLE`, `SAVING`) must never wrap |
| `hud.corner_radius_px` | **8 × dpi/96** | px | visually soft at every DPI; a constant 8 px looks sharp at 100 % and razor-thin at 200 % |
| `hud.glyph_px` | **12 × dpi/96** | px | ~1.1 % of plate height — present at a glance, never the thing you look at |
| `hud.font_px_primary` | **13 × dpi/96**, clamp **[12, 22]** | px | the floor is the legibility floor for `Segoe UI Semibold` at 100 % — below 12 the counters in `02:41` smear; the ceiling stops a 4K-at-200 % monitor from producing a plate that covers a quarter of the game |
| `hud.font_px_secondary` | **0.82 × primary**, min **11** | px | ratio, not a second constant, so the two lines stay in proportion at every DPI |
| `hud.font_family` | `Segoe UI`, `Segoe UI Semibold`, fallback `Tahoma` | — | present on every supported Windows; no webfont download on the game-launch path |
| `hud.detect_interval_ms` | **250** | ms | ~4 samples/s: fast enough that entering exclusive fullscreen costs the user ≤ 500 ms (§3.2), slow enough that a kernel mode query is not a hot poll |
| `hud.exclusive_hysteresis_samples` | **2 in / 2 out** | samples | without it a single flapping sample at a cutscene flashes the HUD in and out |
| `hud.anchor_switch_debounce_ms` | **250** | ms | `WM_MOVE` on the foreground window arrives in bursts |
| `hud.exclusive_toast_repeat` | **once per entry** | — | a repeating toast is dismissed by reflex, which defeats the notice |
| `hud.tray_balloon_timeout_ms` | **10000** | ms | Windows' own default for `NIF_INFO`; long enough to read one line |
| `hud.ring_seconds_displayed` | **1** | decimal | one decimal — "119.4 s left" is useful, "119.4165 s" is a log line |

**Minimum legible size, worked (⚙ — the table is the implementation's output, not a second constant):**

| monitor | OS scaling | effective dpi | primary font | plate min × max | physical result |
|---|---|---|---|---|---|
| 1920×1080 @ 100 % | 1.00 | 96 | **13 px** | 240 × 480 px | the floor case; legible at arm's length from a 24″ |
| 2560×1440 @ 100 % | 1.00 | 96 | **13 px** | 240 × 480 px | identical to 1080p — the point of the dpi formula |
| 3840×2160 @ 100 % | 1.00 | 96 | **13 px** | 240 × 480 px | **small on a desk, and that is correct**: at 100 % on a 32″ 4K, 13 px subtends ≈ 3.3 mm |
| 3840×2160 @ 150 % | 1.50 | 144 | **20 px** | 360 × 720 px | the real 4K case; 20 px subtends ≈ 3.5 mm — the same physical size as the 1080p floor |
| 3840×2160 @ 200 % | 2.00 | 192 | **22 px** (clamped) | 480 × 960 px | clamped at 22 so the plate does not become the game |

**The rule behind the table, and it is the one that matters:** the HUD is sized in **DPI**, never in
pixels, and its `plate_max_w_px` is clamped to **≤ 25 % of the display width** so no combination of
DPI and resolution can produce a plate that owns the screen. Both are decisions, both are closed.

---

## 6. PASS CONDITIONS — observable, and each one has a falsifier

The repo's verification rule (`AGENTS.md:322-333`): **every gate ships both colours** — the pass and a
deliberately-broken copy that must go RED. "A control that stays green is a failing control."

| # | PASS condition (observable) | instrument (name) | the RED arm |
|---|---|---|---|
| **PASS-1** | **N ≥ 20 launches at a 25 ms census of the HUD's own pid tree: the HUD window is `WS_VISIBLE` in 0 samples, longest visible 0 ms** — **AND, in the same run, after the first HUD binding the window IS `WS_VISIBLE` in ≥ 1 sample** | `_hud-startup-flash-census.py` (25 ms cadence, names the class `AireplayHudWindow`) | the §1.6 step-1 line broken (`WS_VISIBLE` set at creation, or an `UpdateLayeredWindow` at start-up) ⇒ **≥ 1 sample in ≥ 5 launches**. A 60 s house census **cannot** substitute: `H:\sotto\AGENTS.md` measured a window visible for a whole 6 s run that the 60 s census never named. **The second clause is not decoration:** without it a HUD that is *never* mapped at all scores a perfect PASS-1 — the instrument would be unable to say NO in the direction that matters |
| **PASS-2** | after a HUD binding, exactly **one** window of class `AireplayHudWindow` is mapped, and its extended styles are **exactly** `LAYERED\|TOPMOST\|NOACTIVATE\|TOOLWINDOW\|TRANSPARENT` — asserted as a set equality, not a subset | `_hud-style-oracle.py` (`GetWindowLongPtr(GWL_EXSTYLE)`) | add `WS_EX_APPWINDOW` ⇒ fails |
| **PASS-3** | with the HUD mapped, `GetForegroundWindow()` is **unchanged** across 10 HUD updates | `_hud-no-focus-probe.py` | drop `SWP_NOACTIVATE` from the `SetWindowPos` call ⇒ the foreground window changes |
| **PASS-4** | **the plate is in the pixels**: a monitor-item WGC grab 100 ms after `Alt+Z` contains ≥ 4 pixels within RGB tolerance 6 of `0x0C0C10` at α>0.5, inside the expected inset rect | `_hud-pixel-proof.py` | swap `UpdateLayeredWindow` for `SetLayeredWindowAttributes` ⇒ 0 matching pixels. **This arm has a named failure mode of its own and it is SKIPPED, never green:** monitor-item WGC was measured **refused** on this box — `CreateForWindow`/`CreateForMonitor` → `E_ACCESSDENIED` for *every* item while `GraphicsCaptureSession::IsSupported` still returned true (`specs/03-capture-encode.md:8-16`). If the grab is refused, the instrument prints `PASS-4 SKIPPED reason=wgc-denied` in **its own column** (`AGENTS.md:333-334` — "a SKIP is not a pass") and PASS-13's census becomes the only proof for that run |
| **PASS-5** | **every** state of §3.1 is reachable and paints a **distinct** plate glyph colour; a scripted driver walks all 11 states | `_hud-state-oracle.py --unit` (state table in, painted RGBA out) | a build where `HIDDEN_EXCLUSIVE` paints the idle glyph ⇒ the distinctness assertion fails |
| **PASS-6** | in `ERROR_SILENT_DEVICE`, the plate's second line **contains the measured peak and the floor** (`9.2e-05` / `0.002` in the fixture) | part of `_hud-state-oracle.py --unit` | a state driver that emits a generic "error" string ⇒ fails |
| **PASS-7** | with a synthetic exclusive-mode `DEVMODE` change held for 2 samples: the HUD window is **unmapped** within 500 ms, the log has exactly **one** `hud_exclusive=1` toast per entry, and `hud.state` == `HIDDEN_EXCLUSIVE` | `_hud-exclusive-oracle.py` | the hysteresis counter removed ⇒ one flipped sample re-maps the HUD |
| **PASS-8** | `PASS-7`'s control arm — with the `DEVMODE` fixture cleared, the HUD returns to its prior state within 500 ms | same | — |
| **PASS-9** | `hud.state` in the log **string-equals** the `HudState` enum name on every transition, over a 200-event run | `_hud-state-oracle.py --log-eq` | map one state to a friendly string ⇒ fails. This is the `exit3-armB-worker.jsonl` defect (`§3.1`) proved at HUD scale |
| **PASS-10** | idle for 60 s: `hud.repaints` ≤ **2** and CPU time of the HUD thread ≤ **0.5 %** of one core (population: 1 process, window: 60 s) | `_hud-idle-cost.py` | force the repaint on every tick ⇒ fails |
| **PASS-11** | `RECORDING` for 30 s: the rendered plate hash changes at **60 Hz ± 2 Hz** and the timer's final value is the frozen one | `_hud-refresh-probe.py` | drop to on-change-only repaint while recording ⇒ fails |
| **PASS-12** | **every** frame of the state walk produces exactly **one** `UpdateLayeredWindow` call (counted, not inferred) | `_hud-composite-oracle.py` | a retry loop that calls it twice on failure ⇒ fails |
| **PASS-13** | the PID census over **every** run above reports `ALERTA-JANELA`-equivalent **0** samples for any window that is not the HUD's own | `_hud-window-census.py` at 25 ms | — |

**Two of these exist only because of history, and are marked:** PASS-1 (Sotto measured a 63 ms panel
flash in 18 of 20 launches) and PASS-9 (Sotto measured a verdict and a state disagreeing inside one
run). Neither is hypothetical paranoia; both are receipts from this owner's machine.

**Gate for this lane: I have run NONE of these.** They are the exit criteria for the lane that
implements the HUD. Every one is written so it can be implemented without asking a question, which is
the actual deliverable here.

---

## 7. THE INTERFACE — what the HUD lane codes against

```
hud.h           HudState                  // the §3.1 enum; its name IS the log token
                HudConfig                 // every §5 key, one struct, one JSON file
                Hud::create(device, cfg, log*) -> bool       // created unmapped; nothing published
                Hud::set_state(HudState, const char* line2, const char* line3)
                Hud::show() / Hud::hide() / Hud::toggle()    // the only ways to map
                Hud::exclusive_probe(const HudProbeSample&) // S1-S3, read-only, §2.4
                Hud::thread_tick()                           // paced, §1.5
                HudStats                  // repaints, paints, state_transitions, alpha0_frames,
                                            //   umw_calls, unmaps, exclusive_entries, peak_cpu_pct
```

**Every counter is a fact (law 6 / `AGENTS.md:293`):** a HUD that cannot say how many frames it
painted or how many times it was unmapped is not shippable, by the same argument
`specs/03-capture-encode.md:219-221` makes about frames.

**Config keys** (all read, none inert — an unused key is a deleted key in this repo):
`hud.refresh_hz`, `hud.fade_in_ms`, `hud.fade_out_ms`, `hud.success_hold_ms`, `hud.inset_px`,
`hud.plate_max_w_px`, `hud.plate_min_w_px`, `hud.corner_radius_px`, `hud.font_px_primary`,
`hud.font_family`, `hud.detect_interval_ms`, `hud.exclusive_hysteresis_samples`,
`hud.force_borderless`, `hud.burn_into_capture`, `hud.anchor` (`top-left`|`top-right`|`hidden`),
`hud.high_contrast` (`auto`|`force`|`off`).

---

## 8. WHAT THIS SPEC DELIBERATELY DOES NOT DO

- **It does not inject, hook, or impersonate.** §2.2 is a ban, not a backlog item.
- **It does not promise the HUD inside exclusive fullscreen.** §2.3 says what happens instead, and
  §2.6 says the same for protected content: **announce, never pretend.**
- **It does not draw anything that is not a computed fact.** No decorative stats, no fake FPS.
- **It does not own the trigger.** L1 owns `RegisterHotKey` and the poll; this spec defines the
  **table and the semantics** L1 must satisfy (§4.2) and the **obligation to display the degradation**
  (§4.3), and nothing else. If a binding table and `src/capture/trigger.cpp:64-75` ever disagree,
  **the code is wrong, not this table** — the table is the contract and L1's ladder was written to
  match it.
- **It does not re-open the Sotto panel-flash fight.** §1.6 inherits the measured rule; a lane that
  wants to re-derive it must go read `H:\sotto\AGENTS.md:306-327` first.