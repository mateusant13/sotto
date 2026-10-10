# Receipt — who swallows the owner's caret chords (2026-10-10)

Owner's report, verbatim: *"one thing that might be because of sotto: alt or ctrl keys are not
working with text. if i trye ctrl and arrow left i cant select the start of the word, or using alt
left arrow key it also does not let anything happen. i cant recall which keys do this, i think are
these two. if im wrong, restore only the right ones."*

## Verdict — SOTTO BLOCKS NONE OF THEM. ZERO SOTTO EDITS.

| the owner's chord | measured | owner |
|---|---|---|
| `Ctrl+Left` (`notchHistoryPrev` in the thief) | **BLOCKED, `ERROR_HOTKEY_ALREADY_REGISTERED` 1409** | **Perssua** |
| `Ctrl+Right` (`notchHistoryNext`) | **BLOCKED, 1409** | **Perssua** |
| `Alt+Left` | **FREE** (`ok=1 err=0`) | nobody — and it is not a caret/word chord on Windows |

`Ctrl+Left` is the caret-to-previous-word chord, so the owner's report is exact for it. `Alt+Left`
is "Back" in browsers and VS Code and is unclaimed; his recollection of which modifier does the
word jump was off by one, which is why "restore only the right ones" lands on `Ctrl+Left`.

## WHERE — Perssua (Perssua 0.28.0), Electron main process

`C:\Users\Administrador\AppData\Local\Programs\perssua\resources\app.asar`
(412791524 B, mtime 2026-09-29T16:01:02Z):

- `DEFAULT_SHORTCUTS`, webpack module 1411, asar offset `401071713-401072413` — 19 actions, verbatim:
  `notchHistoryPrev:"CommandOrControl+Left"`, `notchHistoryNext:"CommandOrControl+Right"`,
  `scrollUp:"CommandOrControl+Up"`, `scrollDown:"CommandOrControl+Down"`, `execute:"CommandOrControl+Enter"`,
  `screenshot:"CommandOrControl+E"`, `whisper:"CommandOrControl+D"`, `toggleMicCapture:"CommandOrControl+Shift+D"`,
  `anchorPrev:"CommandOrControl+Alt+Up"`, `anchorNext:"CommandOrControl+Alt+Down"`,
  `toggleVisibility:"CommandOrControl+Shift+B"`, `toggleActionBar:"CommandOrControl+M"`,
  `toggleAlwaysOnTop:"CommandOrControl+Shift+A"`, `increaseAppOpacity:"CommandOrControl+Shift+Plus"`,
  `decreaseAppOpacity:"CommandOrControl+Shift+-"`, `moveWindow{Left,Right,Up,Down}:"CommandOrControl+Shift+<dir>"`.
- `globalShortcut.register(` — 12 call sites, incl. the per-action registrations at
  `410928993 / 410929173 / 410929331 / 410929488`, `registerShortcut` @`410590088`,
  `safeRegisterAccelerator` @`410604623`, and two chords that are NOT in the map:
  `Ctrl+Shift+S` @`410422375` ("screenshot with text selection") and
  `Ctrl+Shift+C` @`410422787` ("clipboard text analysis").
- Electron `globalShortcut` is a thin wrapper over Win32 `RegisterHotKey`.

## WHY the signal never reaches the editor

`RegisterHotKey` claims are **session-scoped and system-wide**: while a claim is live the OS routes
`WM_HOTKEY` to the claimant and **does not deliver the keystroke to the foreground window**. The chord
is consumed before the editor's message loop sees it, so no amount of caret code in VS Code/Word can
react. Proof of the claim is `ERROR_HOTKEY_ALREADY_REGISTERED` (1409) — the API refuses a second
registrant and NEVER names the first. Hence the attribution below is a fingerprint, not a query.

## The fingerprint that makes it Perssua (session 1, BOOL-based)

Instrument: `ctypes.WinDLL('user32', use_last_error=True)`, `ctypes.set_last_error(0)` before each
`RegisterHotKey(None, id, mods, vk)`; the **BOOL return** is the verdict. `RegisterHotKey` does NOT
clear the last-error slot on success, so a verdict read from `get_last_error()` alone reports a stale
1409 on successes — that mistake produced one bogus "everything blocked" readout this session and is
recorded here so it is not repeated.

- **17 of 19 declared chords BLOCKED (1409)** in both the plain and the `MOD_NOREPEAT` form —
  mapping 1:1 onto the map above, including all four caret chords (`Ctrl+Left/Right/Up/Down`).
- **2 of 19 FREE** — `Ctrl+Shift+Left` and `Ctrl+Shift+Right` (`moveWindowLeft/Right`), exactly the
  two ids in module 1411's hardcoded exclusion set `a = new Set(["moveWindowLeft","moveWindowRight"])`
  (verbatim), which the settings logic treats as not-enabled-by-default. Predicted free, measured free.
- **2 chords BLOCKED that are NOT in the map** — `Ctrl+Shift+S` and `Ctrl+Shift+C`, predicted from the
  two independent registration sites above. Predicted blocked, measured blocked.
- **All controls FREE** — `Alt+C`, `Alt+Shift+C`, `Ctrl+Alt+C`, `Ctrl+Shift+C`(control arm), `Ctrl+F11`,
  `Shift+F11`, `Ctrl+Alt+F11`, `Alt+F10`, `Ctrl+Shift+X`, `Ctrl+Shift+V`, `Alt+Left/Right/Up/Down`,
  `Ctrl+Alt+Left/Right`, `Alt+F9`. Measured "CONTROLS VALID" on both earlier grids and again here.

19/19 predictions confirmed and 2/2 exclusions confirmed, with two of the predictions coming from a
code site entirely outside the map. That is the attribution.

## FIX (owner-side, in Perssua — not in Sotto)

Perssua ships a real Shortcuts editor: `settings.tabs.shortcuts` (sidebar tab, keyboard icon) with
`settings.shortcuts.title`, `.description`, `.enabled`, `.disabledBadge`, `.customBadge`, `.notBound`,
`.reset`, `.resetAll`, and the tip `settings.shortcuts.tips.effectImmediate` ("takes effect
immediately" — no restart). Its validation keys `.alreadyUsedBy` / `.usedBy` refuse duplicate binds.

So, 20 seconds, no restart: **Perssua -> Settings -> "shortcuts" -> disable (or rebind) the four
chords that collide with text editing** — `notchHistoryPrev` (`Ctrl+Left`), `notchHistoryNext`
(`Ctrl+Right`), `scrollUp` (`Ctrl+Up`), `scrollDown` (`Ctrl+Down`). The same list also holds a
`resetAll` if an experiment goes wrong. If Perssua is not wanted at all: quit it (its claims die with
the process) or uninstall it; nothing in Sotto depends on it.

## What was NOT changed, and why

Sotto's shell was re-verified at the time of writing: `app/webview/sotto_webview.py`,
`326796 B`, `6583` lines, sha256 `557A2B0D4CA43752EAE48E371E6B25C5CB76189179A3E2D2960C6FBE77FACB1A`, mtime
`2026-10-09T22:11:18.423Z`. Its ONLY hotkey registration is line 1366
(`if not user32.RegisterHotKey(None, _HOTKEY_ID, ...)`), one `UnregisterHotKey` call
(`1`), and the fallbacks are `Alt+C` -> `Alt+Shift+C` -> `Ctrl+Alt+C` -> `Ctrl+Shift+C`.
Fresh grep counts in that revision: `SetWindowsHookEx`=0, `RegisterRawInputDevices`=0, `WM_INPUT`=0, `GetAsyncKeyState`=0, `SendInput`=0, `keybd_event`=0, `globalShortcut`=0, `VK_LEFT`=0, `VK_RIGHT`=0, `VK_UP`=0, `VK_DOWN`=0.
**Zero** hooks, zero raw-input registration, zero key injection, zero arrow/VK registrations — the
shell cannot swallow an arrow chord even in principle.

Runtime confirmation in the same hour: the single-instance mutex `Local\SottoShell` was NOT held
(`CreateMutexW` -> `handle=556 err=0 already_exists=False`), and no live process command line is
`sotto_webview.py`. **No Sotto shell was running at all**, and all four of its candidate chords were
free. A process that is not running cannot take a hotkey.

## Re-verify in 30 seconds (falsifier)

Quit Perssua and re-run the chord grid: `Ctrl+Left/Right/Up/Down` must flip from 1409 to `ok=1`
while the controls stay free. If they do, the attribution is complete; if even one stays blocked, the
owner is a second claimant and this receipt is wrong — say so and re-open it.

## Related, latent, NOT a change to make

Sotto's 4th fallback is `Ctrl+Shift+C`, which Perssua currently holds as its "clipboard text
analysis" shortcut (asar @`410422787`). So if `Alt+C`, `Alt+Shift+C` and `Ctrl+Alt+C` were ever all
taken, Sotto's last fallback would fail too and it would raise its error dialog. Latent only; today
`Alt+C`, `Alt+Shift+C` and `Ctrl+Alt+C` are all free.
