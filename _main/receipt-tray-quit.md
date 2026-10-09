# Receipt — the system tray, and a Quit that really quits (2026-10-08)

Owner, verbatim: *"tira o botao de quit sotto do painel. só tem q quit no icon do system tray"*.

**THE TRAY DID NOT EXIST.** Measured before writing anything:
`grep -rn 'pystray|NotifyIcon|Shell_NotifyIcon|QSystemTrayIcon' app/` → **zero matches**. So the Quit
had to be BUILT before it could be moved; had the panel's button been removed first, the owner would
have had no way to close the app except the task manager.

Nothing was removed from `app/panel/` — that directory belongs to another lane. The panel's Quit
button can be removed once this receipt is accepted.

## What was built (all in `app/webview/sotto_webview.py`, the shell)

- `TrayIcon` — plain Win32 `Shell_NotifyIconW` on a **message-only window** (`HWND_MESSAGE`,
  class `SottoTrayWindow`) owned by its own daemon thread with its own `GetMessageW` loop. No new
  dependency; the hotkey thread could not be borrowed (a `--no-hotkey` run has none).
- **The icon is the one already generated for the window** — `app/webview/sotto.ico`, loaded with
  `LoadImageW`. No second icon file.
- Menu: `Open panel` · separator · **`Quit Sotto`** (id 2). Drawn with
  `TrackPopupMenu(TPM_RIGHTBUTTON|TPM_RETURNCMD)`, and the chosen id is then posted back as a **real
  `WM_COMMAND`** — so the menu and the probe drive ONE handler, and the probe does not need a test
  hook that bypasses the menu.
- The Quit calls the shell's existing `request_exit(0, reason='tray-quit')`, which already
  terminates the worker child (`WorkerBridge.stop` → `child.terminate()`, wait 5 s, then `kill`).
  The tray is stopped FIRST inside `request_exit`, because `os._exit` at the end would leave a ghost
  icon in the notification area pointing at a dead window.

## Two defects found by measuring, both of which would have shipped

1. **The tray thread joined ITSELF, and the app did not close.** The menu command is handled on the
   tray thread, so `TrayIcon.stop()` → `self._thread.join(2)` raised
   `RuntimeError: cannot join current thread`. Measured: `TRAY_QUIT requested=true`,
   `TRAY_ICON_DELETE ok=true`, then `WARN TRAY_COMMAND_FAILED id=2 RuntimeError: cannot join current
   thread` — **shell and both workers still alive**, mutex still held, no `SHELL_EXIT`. An app that
   will not quit is worse than one that will not start, and this is exactly the failure that would
   have been reported as *"o quit do tray não funciona"*.
2. **`Shell_NotifyIconW` `cbSize`** — the struct as declared is **976 B** (`0x3D0`, the documented
   V4 x64 size) and Windows accepts it; logged as `cbSize=976` in every run, so a future edit that
   changes the struct will show up here rather than as a silently missing icon.

## Proof, with numbers — `python _main/tray-quit-probe.py`

The probe is OUTSIDE the shell. The subject run is a real shell with `--with-worker --worker
_main/_fake-worker-stdout.py`: a **stand-in worker** that occupies the same slot (a child process of
the shell) and **opens no audio device**, because the lane's rules forbid opening one. It is not the
worker and nothing here claims it is. No `--show`; `pythonw.exe` with `CREATE_NO_WINDOW`.

| what | measured |
|---|---|
| tray window exists | `TRAY_WINDOW created=true hwnd=49945546 class=SottoTrayWindow message_only=true` |
| icon actually in the notification area | **proved from another process**: `Shell_NotifyIconW(NIM_MODIFY)` on the same `(hwnd,uID)` → **TRUE** |
| menu contains the Quit | `TRAY_MENU [1]='Open panel' [sep] [2]='Quit Sotto'` |
| Quit id used | `2` |
| pids BEFORE | shell `32996`; workers `[33296, 27156]` |
| Quit driven through | `PostMessageW(tray_hwnd, WM_COMMAND, 2, 0)` → log `TRAY_COMMAND id=2`, `TRAY_QUIT requested=true` |
| pids AFTER | shell **dead**; `workers_after = []` — **both workers dead** |
| shell's own exit | `SHELL_EXIT rc=0 reason=tray-quit` |
| mutex | private name `Local\SottoShell-probe-10664`: free before → **held** with the app → **FREE after** |
| icon after | `NIM_MODIFY` → **FALSE** (gone); log `TRAY_ICON_DELETE ok=true` |
| windows | 0 visible before, 0 visible after (census over the shell's own pid) |
| tray does not come up twice | relaunch: new icon registered **TRUE**, the OLD hwnd's icon **FALSE** |

## What is NOT proved, stated plainly

- **The default mutex name is unmeasurable in this session.** The owner's own shell (pid 28428) holds
  `Local\SottoShell` for the whole probe, so `mutex_held_after` is TRUE with or without my run. That
  is why the probe uses a **private** name via `--mutex-name`: that arm is a real before/held/after
  measurement. The default-name reading is context, not a failure.
- **The tray WINDOW cannot appear in a window census.** `EnumWindows` does not enumerate
  message-only windows, so `tray_windows_for_pid` is `[]` in the relaunch arm even though the window
  exists — the hwnd comes from the shell's own log. The "no duplicate" claim rests on the two
  `NIM_MODIFY` answers (new TRUE, old FALSE), which is the stronger of the two.
- **The menu was never opened by a real right-click.** The id was driven as `WM_COMMAND` directly —
  everything except the mouse. `TrackPopupMenu` itself is not exercised by the probe.
- **`single_instance` is FALSE in the relaunch arm** because that arm passes `--no-hotkey` with the
  DEFAULT mutex name, and the lock is skipped by design for measurement runs (`SINGLE_INSTANCE_SKIPPED`).
  The single-instance refusal is not re-measured here; it has its own oracle.
- **The real `worker/sotto_worker.py` was never the subject.** The audio device it opens is forbidden
  here. What is proved is that `WorkerBridge.stop()` terminates the child process it spawned; the
  stand-in is that child.
- Not measured: what the owner sees in the notification area (its tooltip rendering, the icon at
  real DPI), and the tray's behaviour across a display change.

## Reproduce

```
python _main/tray-quit-probe.py          # both arms, ~40 s, prints one JSON
```
