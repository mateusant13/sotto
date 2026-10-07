# Alt+C Hotkey Delivery — Evidence Receipt

**VERDICT: PROVEN (OS-level).** An Alt+C injected into the OS input queue was
delivered to the registering thread, consumed by the real handler, and the
panel window changed visibility — observed by a foreign process.

## A. Registration

`H:\sotto\app\webview\sotto_webview.py:1202-1203`
`user32.RegisterHotKey(None, _HOTKEY_ID, modifiers|MOD_NOREPEAT, vk)`

* Library: **none** — raw Win32 `user32.dll` via `ctypes.WinDLL` (`use_last_error`).
  `MOD_NOREPEAT=0x4000` (:788), `WM_HOTKEY=0x0312` (:789).
* Class `HotkeyThread` (:1171); armed by `arm_hotkey()` (:1985), constructed :1998.

## B. Destination

`hWnd=NULL` ⇒ the hotkey binds to the **calling thread**, and the OS posts
`WM_HOTKEY` to that thread's queue:
:1217 `GetMessageW` → :1220 match → :1221 `pressed+=1` → :1223 `on_hotkey()`
= the lambda at :1998 `shell.toggle_panel('hotkey')` → `toggle_panel` :4864 →
:4876 decides with a real `IsWindowVisible`, not a cache → :4890 `show_panel`
/ :4882 `hide_panel`. Consumer is real; it terminates in `show_panel`, not nothing.

## C. Firing it — observed

Subject: the **live** shell, PID 28428 (`pythonw … sotto_webview.py`), started
08:01:55. No second instance, so no mutex interference.

`_main/_altc_delivery_probe.py` (`SendInput` 4 events: Alt↓ C↓ C↑ Alt↑):

* `SendInput` returned **4/4**, `winerror=0` — not refused by UIPI.
* Window `0x914aa` class `WindowsForms10.Window.8`, title `Sotto`:
  `IsWindowVisible false → true` (read by `EnumWindows`, not by product code).
* Log bytes appended **after** the recorded offset (self-attributed):
  `PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false`
  and `PANEL_VISIBILITY_MODE visible=true reason=hotkey transitions=138`.
* `focus_stolen=false` — the no-focus-theft claim holds.
* A second injection restored hidden (state left as found).

**Not simulated.** `PANEL_SHOWN reason=hotkey` alone proves nothing:
`simulate_press()` (:1236, `PostThreadMessageW`) emits the identical line. That
is why this used `SendInput` + byte-offset attribution, and why the process was
never touched in-process.

Ownership closed: `HOTKEY_REGISTERED … thread=27184` (log line 26951) and
Toolhelp shows TID 27184 ∈ PID 28428.

Population/window: whole `webview-run.log`, 50 388 lines — 25
`HOTKEY_REGISTERED`, 0 fallbacks, 0 unavailable, 1 `HOTKEY_REGISTER_FAILED
winerror=1409` (line 2646, a historical second shell).

## D. Environment limits

None. It fired.

Commits (`lane/altc`, worktree `H:\sotto-wt\altc`): `77087e4`, `080bf76`, receipt.