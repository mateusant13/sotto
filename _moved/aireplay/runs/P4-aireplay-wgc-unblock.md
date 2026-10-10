# P4 — WGC UNBLOCK: WHY E_ACCESSDENIED WHEN POLICY SAYS ALLOW

Status: **SPEC — investigation + fix**
Lane: `feat/wgc-unblock`
Depends on: `HANDOVER.md` §3, `_main/wgc-probe.cpp`

## 1. THE BLOCK

`Windows.Graphics.Capture` refuses **all** capture attempts with `E_ACCESSDENIED`
(`0x80070005`). Measured on this box 2026-10-07 at four independent instants:

| time | log | result |
|---|---|---|
| 11:55:11 | `_main\logs\wgc-denial-probe-3.txt` | 5/5 `0x80070005` |
| 12:10:27 | `_main\logs\handover-wgc-verify.txt` | 5/5 `0x80070005` |
| 12:28:11 | `_main\logs\cap-battery-20261007-122811.txt` | 5/5 `0x80070005` |
| ~12:39 | `_main\logs\handover-wgc-verify-2.txt` | 5/5 `0x80070005` |

The instrument is `_main\wgc-probe.exe` (307 103 B, sha256
`9B0F884A6933B0C5E918FB728A2E044A530A37C4BF25677449BCFCF1601621FC`). It tries 5 call
points: own window, foreground window, desktop window, shell taskbar, primary monitor.
All 5 are refused.

## 2. WHAT THE BLOCK IS NOT

The consent policy is **not** the cause. Read from the registry:

- `HKLM` and `HKCU\...\ConsentStore\graphicsCaptureProgrammatic` = **`Allow`**
- `HKCU\...\graphicsCaptureProgrammatic\NonPackaged` = **`Allow`**
- `HKLM` and `HKCU\...\graphicsCaptureWithoutBorder` = **`Allow`**
- Per-executable keys exist under `HKCU\...\graphicsCaptureWithoutBorder\NonPackaged\`

So: **policy says `Allow`, API says `E_ACCESSDENIED`.** The denial is not in the policy
value.

## 3. WHAT THE BLOCK COULD BE

Three hypotheses, ordered by prior probability:

### H1: Process integrity level / token

WGC may require the calling process to have a specific integrity level or token privilege.
The probe runs as a normal user process. If WGC requires `SECURITY_MANDATORY_MEDIUM`
or higher (or a specific capability), a normal user process would be refused.

**Test:** Run the probe as administrator. If it succeeds, the block is integrity-level.
If it still fails, H1 is refuted.

### H2: Window station / desktop access

WGC may require the calling process to be in the same window station and desktop as
the target. If the probe runs in a different session (e.g. session 0 or a service
session), WGC would refuse.

**Test:** Run the probe in the owner's interactive session (session 1). If it
succeeds, H2 is confirmed.

### H3: Graphics capture service state

The Windows Graphics Capture service may be disabled or in a bad state. The API
returns `E_ACCESSDENIED` when the service cannot create a capture session.

**Test:** Query the service state with `Get-Service -Name "GraphicsCapture"` or
`sc queryex`. If the service is stopped, start it and re-run the probe.

## 4. THE REQUESTACCESS EXPERIMENT

`_main\logs\wgc-request-access.txt` (12:04:13, 528 B) shows:
```
MATCH after 89 candidate(s): {743ED370-06EC-5040-A58A-901F0F757095}
RequestAccessAsync(Programmatic) -> 0x00000000
async status = 1 (Completed) errorCode=0x00000000
calling slot 6 ...
```

The file ends there. `RequestAccessAsync` returned success, but the subsequent
`CreateForWindow` call was never logged. **It is unknown whether `RequestAccessAsync`
fixes the block.**

**Next step:** Re-run the probe with `RequestAccessAsync` called before each
`CreateForWindow`. If the block is lifted, the fix is to call `RequestAccessAsync`
in the capture binary before creating the capture item.

## 5. THE CAPTURE BINARY

`src/capture/wgc_capture.cpp` (14 150 B) is the WGC capture implementation. It:
1. Creates a `GraphicsCaptureItem` for the target window/monitor.
2. Creates a `Direct3D11CaptureFramePool`.
3. Starts a capture session.

The fix (if H1/H2/H3 is confirmed) goes here. If `RequestAccessAsync` is the fix,
add it before step 1.

## 6. ACCEPTANCE — tests that can go RED

### ARM-A: Probe as administrator

```
wgc-probe.exe run as admin → if 5/5 succeed, H1 confirmed. If 5/5 still fail, H1 refuted.
```

### ARM-B: Probe in interactive session

```
wgc-probe.exe in session 1 → if 5/5 succeed, H2 confirmed. If 5/5 still fail, H2 refuted.
```

### ARM-C: Service state check

```
Get-Service GraphicsCapture → if stopped, start it, re-run probe. If probe succeeds, H3 confirmed.
```

### ARM-D: RequestAccessAsync before CreateForWindow

```
wgc-probe.exe with RequestAccessAsync → if 5/5 succeed, the fix is RequestAccessAsync.
```

### ARM-E: Capture binary with fix

```
aireplay-capture --run --monitor → if clip is written with video, the block is lifted.
```

## 7. FILES TO MODIFY

| file | change |
|---|---|
| `_main/wgc-probe.cpp` | Add `RequestAccessAsync` call before each `CreateForWindow` |
| `src/capture/wgc_capture.cpp` | Add the fix (if confirmed) before `CreateForWindow` |

## 8. PROVENANCE

- Block measurements: `HANDOVER.md` §3 (READ, 2026-10-07)
- Policy values: `HANDOVER.md` §3.2 (READ, 2026-10-07)
- RequestAccessAsync: `HANDOVER.md` §3.3 (READ, 2026-10-07, INCOMPLETE)
- Hypotheses: UNKNOWN (not yet tested)
- Fix: UNKNOWN (depends on which hypothesis is confirmed)
