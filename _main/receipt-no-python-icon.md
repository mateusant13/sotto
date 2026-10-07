# Receipt — no Python icon on the panel (2026-10-08)

Owner's report, verbatim: *"eu tambem nao gosto que aparece um icone de python quando eu aperto o
painel"*. He was right, and the mechanism is exact.

## What the window presented, and why

`app/webview/sotto_webview.py` runs under `pythonw.exe`. pywebview's WinForms backend, when it is
given no icon, copies the icon out of **`sys.executable`** into the form
(`webview/platforms/winforms.py:243-251`):

```python
if _state['icon'] and os.path.isfile(_state['icon']):
    self.Icon = Icon(_state['icon'])
else:
    icon_handle = windll.shell32.ExtractIconW(handle, sys.executable, 0)
```

`sys.executable` here is `C:\Program Files\Python311\pythonw.exe`. The panel therefore presented the
**Python icon** in the taskbar and in Alt+Tab, and — because the process had no AppUserModelID — the
taskbar grouped it with every other `pythonw.exe` on the box.

Two further facts were found by measurement, not by reading:

1. **The window's icon was byte-identical to pythonw.exe's icon.** The probe draws the icon it reads
   back from the window and hashes the pixels; the same method on `pythonw.exe`'s own icon returns
   the **same 16 hex chars** (`8bfd03e267b05c81`). A non-zero handle could have meant anything.
2. **The ex-style the shell logs as set was NOT in effect.** At `PANEL_VISIBILITY_AT_STARTUP` the
   hwnd carried `WS_EX_APPWINDOW|WS_EX_CONTROLPARENT|WS_EX_TOPMOST` (`0x00050008`) — **no
   `WS_EX_TOOLWINDOW`** — although the shell had logged setting it a few lines earlier. WinForms
   re-applies `Form.CreateParams` (which sets `WS_EX_APPWINDOW` while `ShowInTaskbar` is true and the
   form has no owner) when pywebview's startup `Opacity`/`Show`/`Hide` dance recreates the handle.
   `WS_EX_APPWINDOW` **beats** `WS_EX_TOOLWINDOW`, so the panel got a real taskbar button — the exact
   surface the owner was looking at. `skipTaskbar=true` in the shell's own log was a **false claim**.

## What it presents now

- `webview.start(icon=SOTTO_ICON)` — the channel pywebview actually implements, despite its own
  docstring calling the parameter "Supported only for GTK/QT" (`webview/__init__.py:205`).
- `apply_window_icon()` in `_on_before_show`: the WinForms `Icon` property **and** three explicit
  `WM_SETICON` sends — `ICON_BIG`, `ICON_SMALL`, and **`ICON_SMALL2`**, which the taskbar and Alt+Tab
  read and which .NET's own `Form.Icon` setter never sends. The `Icon` object is kept alive on the
  form (`_sotto_icon`) because `WM_SETICON` stores the **handle**, not a copy.
- `set_process_app_user_model_id('sotto.overlay')`, called **before** any window exists.
- `reassert_taskbar_ex_style()` at the first moment after the startup dance: re-adds
  `WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE` and **removes `WS_EX_APPWINDOW`**. Measured to stick (the
  external read 3 s later still shows `0x08010088`, `toolwindow=true appwindow=false`).

## The icon: GENERATED, and that is stated

The repo had **no Sotto icon**. `glob **/*.{ico,png}` returns exactly one `.ico`:
`app/src-tauri/icons/icon.ico`, which is the **stock Tauri scaffold icon** (the Tauri logo) belonging
to a shell that is not the app; `grep -rn 'pystray|NotifyIcon|Shell_NotifyIcon|tray_icon'` over
`app/` returns **no matches**, so there is no tray icon to reuse either. Copying the Tauri logo would
have replaced one lie ("this is Python") with another ("this is Tauri").

So a **minimal mark was generated**: `app/webview/sotto.ico` (13 652 B, frames 16/32/48/64/128/256,
sha256 `d3442cfc32c96e33…`), drawn by `_main/make-sotto-icon.py` from the panel's OWN accent, read out
of `app/panel/panel.css:19-22` (READ ONLY — that directory belongs to another lane):
`--accent-from: #7dd3fc` → `--accent-to: #a78bfa`, 135°, on the shell's own `background_color`
`#0b0f14`, with three caption bars. **It is not a brand and it is not the owner's design; it is a
placeholder that is at least Sotto's own colour instead of the interpreter's.**

## Before / after — ONE instrument, ONE moment

Both arms are the **same file** with only the fix reverted
(`_main/make-no-icon-negarm.py` builds the control arm by four literal textual reverts; the copy is
deleted after the run). Same probe, same `--settle`, same timing, both reaching `RECEIVER_READY`.
The instrument lines are kept in BOTH arms, so the control reports its own source from inside its own
process. Files: shell sha256 `6132bf5c54e2c180…`, neg-arm `28b4e49b775d3b82…`.

| what | BEFORE (neg-arm) | AFTER |
|---|---|---|
| `WINDOW_ICON source=` | `pythonw-fallback:C:\Program Files\Python311\pythonw.exe` | `file:H:\sotto\app\webview\sotto.ico` |
| `form_icon` (in-process pixels of `form.Icon`) | `32x32:64d0d3f083272dfa` | `32x32:2ef8b72584f0f902` |
| `WM_GETICON` small / big / small2 | `22748336 / 9575694 / 22748336` (big ≠ small) | `53418490 / 53418490 / 53418490` |
| window icon pixels (external draw+hash) | **`8bfd03e267b05c81`** | `a599b2bb6af24f57` |
| `pythonw.exe` icon pixels (same method) | `8bfd03e267b05c81` — **IDENTICAL** | `8bfd03e267b05c81` — **different** |
| `GetClassLongPtr GCLP_HICON/HICONSM` | `0 / 0` | `0 / 0` (unchanged: the class icon is still unset) |
| `GWL_EXSTYLE` | `0x00050008` appwindow=**true** toolwindow=false | `0x08010088` appwindow=false toolwindow=**true** |
| `APP_USER_MODEL_ID` (process read-back) | `value=None ok=false hr=2147500037` (`E_NOT_SET`) `set=false` | `value=sotto.overlay ok=true hr=0 set=true set_hr=0` |
| window's own AUMID property store | `value=null vt=0` (VT_EMPTY) | `value=null vt=0` (VT_EMPTY, unchanged) |
| panel loads | `receiver_ready=true` | `receiver_ready=true` |
| visible window samples (100 ms × 20, own pid) | 0 of 20, 6 windows | 0 of 20, 6 windows |

The `file_sha256=d3442cfc32c96e33` the shell logs is the same value the probe hashes off the file, in
both arms — so the pixel hash is bound to the exact bytes the shell loaded.

## What is NOT proved

- **The taskbar button's rendered icon and its grouping are NOT confirmed.** Confirming them needs a
  visible window, and `--show` is forbidden in this lane. What is proved is the window-level facts
  the taskbar reads: `WM_SETICON` for all three icon slots, a non-Python icon, an explicit
  `AppUserModelID`, and no `WS_EX_APPWINDOW`.
- **The window's AUMID property store stayed `VT_EMPTY`** in both arms. That is expected — the
  per-window store is not where a process-wide AUMID lands — but it means the AUMID reaches the
  taskbar through the process, and the process-side read-back is the only evidence here. Nothing
  external confirms the taskbar consumed it.
- **`GCLP_HICON`/`GCLP_HICONSM` remain 0** after the fix. The class icon is untouched; only the
  window icon is set. If any surface reads the CLASS icon, it is unchanged (and was 0 before, so
  Windows falls back to the exe icon there).
- **The ex-style re-assert is measured to stick for ~3 s** (one read). It is not measured across a
  full session, a hot reload, or a navigation after startup.
- Not measured at all: the icon Windows shows in the **Alt+Tab** switcher, and the tray (there is no
  tray icon in this shell — `grep` above).

## Incidental defect found and fixed

`_post` passed the callable straight to `BeginInvoke`, so anything it raised was an **unhandled
UI-thread exception** — WinForms answers that with a `ThreadExceptionDialog`, a VISIBLE window. It is
now wrapped and logged as `POSTED_CALLABLE_FAILED`. Measured cause: a `NameError` in a posted
callable produced neither a log line nor a crash, and the run looked healthy.

## Also fixed on the way

Passing `icon=` to `create_window` **kills the shell silently** on `pythonw.exe`: `icon` is a
`start()` parameter (`webview/__init__.py:179`), not a `create_window()` one (`:309`), and the
resulting `TypeError` has nowhere to print. Measured: the run stopped at `panel geometry:` with no
traceback, no window, and no log line. The trap is documented in place in the shell.

## Reproduce

```
python _main/make-sotto-icon.py                       # the icon (generated, not a brand)
python _main/make-no-icon-negarm.py                   # the control arm
python _main/no-python-icon-probe.py --label before --settle 12 ^
    --shell app/webview/_negarm_sotto_webview.py --icon app/webview/sotto.ico
python _main/no-python-icon-probe.py --label after  --settle 12 --icon app/webview/sotto.ico
python _main/make-no-icon-negarm.py --clean
```

Never `--show`; both arms pass `--no-hotkey --no-hot-reload --exit-after` (so no worker and no audio
device), the child is `pythonw.exe` with `CREATE_NO_WINDOW`, and the probe terminates only the exact
pid it spawned, after reading that pid's image path.
