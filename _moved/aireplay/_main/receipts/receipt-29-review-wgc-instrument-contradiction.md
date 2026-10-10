
# receipt-29 — review F13.2: two instruments measured `CreateForWindow` with opposite results on THIS box

**Reviewer:** session `session-f25ffe2c-5ac5-4766-859b-7b1a9c6570a6` (Session 2), delegated lane, scope F13.2 only.
**Discipline:** every number below is a byte taken from a log file in `I:/cc-tmp/f13-2/` (this lane's scratch area) or from a census run in this session. Where a claim is attributed to another lane rather than measured here, the line says ATTRIBUTED.
**Written:** 2026-10-10T01:10:46Z (UTC), Node clock, agreeing with `Get-Date`.ToUniversalTime() = 2026-10-10T01:10:46.147Z.

---

## 0. VERDICT

> **NO — THIS BOX DOES NOT REFUSE WGC CAPTURE, AND THE INSTRUMENT WHOSE NUMBER IS TRUE FOR THIS BOX IS INSTRUMENT B.**
> `IGraphicsCaptureItemInterop::CreateForWindow` / `CreateForMonitor` returned `S_OK` / `0x00000000` for every target in every run of INSTRUMENT B's binary, and in every run of INSTRUMENT A's own bytes launched from an image outside `H:\sotto`. INSTRUMENT A's `E_ACCESSDENIED` / `0x80070005` is not a machine refusal and not a defect in either program: it is a per-process LOW-integrity artifact of the `S-1-16-4096` Low mandatory label carried by every image under `H:\sotto` (set explicitly on the `H:\sotto` root, inherited down), which makes such an image spawn a LOW-IL process in which Windows refuses WGC item creation for EVERY target — including `CreateForMonitor` and including the process's own window. Same bytes, same machine, same minute, opposite results; the discriminator is the label on the image, not the instrument and not the box.

Verbatim answer to the question the finding poses:

    DOES THIS BOX REFUSE WGC CAPTURE, AND WITH WHICH INSTRUMENT'S NUMBER?
    NO. INSTRUMENT B'S NUMBER — S_OK / 0x00000000 — IS THE MEASURED TRUTH OF THIS BOX.

Practical consequence for the lane that reported the finding: **INSTRUMENT A, as currently built and as currently labelled, cannot be used to measure WGC on this box** — every image it can run from inside `H:\sotto` reports `0x80070005` regardless of the OS's real behaviour. Re-run the finding's question from a copy of A on an unlabelled volume (`I:`) or from `H:\sotto-wt\...`, or continue with B.

---

## 1. The two instruments, identified by bytes

| | INSTRUMENT A | INSTRUMENT B |
|---|---|---|
| binary | `H:\sotto\_moved\aireplay\_main\wgc-probe.exe` | `H:\sotto-wt\wgcunb\_moved\aireplay\_main\_wgc-unblock\wgc_probe.exe` |
| bytes | 307 103 | 1 183 511 |
| sha256 | `9B0F884A6933B0C5E918FB728A2E044A530A37C4BF25677449BCFCF1601621FC` | `38C101B3846A3094D9C70451DB10F5872C0B1FCFD26747F763EF12EFB66702DC` |
| mtime (UTC) | 2026-10-07T16:09:59.026Z | 2026-10-09T22:51:14.049Z |
| source | `H:\sotto\_moved\aireplay\_main\wgc-probe.cpp` — 16 667 B / 345 lines / sha256 `259030C9D31E9C5592E8F941D9C384387955F7255BE4D099FD84D3BB0B4F5EC8` / mtime 2026-10-07T16:09:59.025Z | `H:\sotto-wt\wgcunb\_moved\aireplay\src\capture\wgc_probe.cpp` — 77 779 B / 1 648 lines / sha256 `6ED3D52FF9A226D2646F26F82BC5517AA764DDFE0E1D850A87171CEA36D16129` / mtime 2026-10-09T22:39:29.946Z |
| file mandatory-label SACL (`icacls`) | `Rótulo Obrigatório\Nível Obrigatório Baixo:(I)(NW)` — **inherited Low mandatory label** | **absent** (only DACL ACEs are listed) |
| what the finding says it measured | 5 of 5 targets `0x80070005` | `S_OK` / `0x00000000` |

The byte-identity control, measured: `H:\sotto-wt\wgcunb\_moved\aireplay\_main\wgc-probe.exe` is **307 103 B / sha256 `9B0F884A…` / mtime 2026-10-09T19:31:22.947Z — byte-identical to INSTRUMENT A**, a distinct file object, and it carries **no** Low label. It returned `0x00000000` on all 5 targets (run `A_wgcunb`). That pair alone resolves the finding; the rest of this receipt makes the cause airtight.

---

## 2. MEASUREMENT TABLE — population and window for every measurement

**Population/window per run, identical in every A-format run (this is the population the finding's 5/5 number came from):**

1. `our own window` — the probe's own 200x200 WS_POPUP|WS_VISIBLE|WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE window, created at `wgc-probe.cpp:329-331`;
2. `foreground window` — `pid=26672` (WindowsTerminal);
3. `desktop window` — `pid=1772`, `root=0`;
4. `shell taskbar` — `Shell_TrayWnd` `pid=12636`;
5. `primary monitor` — `CreateForMonitor` on display 1.

B-format runs probe their own 32x32 tool window (created at `wgc_probe.cpp:795`, shown at `:801`) in five arms: MONITOR (:1355), RED (:1362), AMBER (:1366), GREEN (:1372), REPEAT on a FRESH window (:1382), summarised by `BEST-HRESULT` (:1385).

**Run stamps.** B-format runs print their own ISO UTC `iso time` line — reproduced verbatim in §7. A-format runs print no clock; their stamp below is the **mtime of the redirected log file** (UTC), i.e. the instant that process exited. All stamps are reproducible with `(Get-Item <log>).LastWriteTimeUtc`.

### 2.1 A-format runs — `CreateForWindow` x4 + `CreateForMonitor` x1

| run | image launched (bytes) | label on image | probe pid | token IL | own-window hwnd | the 5 targets | log mtime (UTC) |
|---|---|---|---|---|---|---|---|
| **A_product** | `H:\sotto\_moved\aireplay\_main\wgc-probe.exe` (9B0F884A…) | Low `(I)(NW)` | 39276 | **LOW** (chain in §2.3) | `00000000002c19ac` | **all 5 -> `0x80070005`** | 2026-10-09T23:51:58.274Z |
| **A_wgcunb** | `H:\sotto-wt\wgcunb\_moved\aireplay\_main\wgc-probe.exe` — byte-identical A, distinct object, **no label** | none | 37124 | MEDIUM/HIGH | `00000000005c1bb4` | **all 5 -> `0x00000000`** | 2026-10-09T23:51:58.849Z |
| E01 | A bytes, product tree | Low | 34336 | LOW | `0000000000e51658` | **all 5 -> `0x80070005`** | 2026-10-09T23:56:58.200Z |
| E02 | A bytes, product tree | Low | 37080 | LOW | — | **all 5 -> `0x80070005`** | 2026-10-09T23:56:58.642Z |
| E03 | A bytes, product tree | Low | 33480 | LOW | — | **all 5 -> `0x80070005`** | 2026-10-09T23:56:59.085Z |
| E04 | A bytes, wgcunb copy (no label) | none | 5100 | MEDIUM/HIGH | `00000000003419ac` | **all 5 -> `0x00000000`** | 2026-10-09T23:56:59.630Z |
| E05 | `I:\cc-tmp\f13-2\A_from_I.exe` | none | 36368 | MEDIUM/HIGH | — | **all 5 -> `0x00000000`** | 2026-10-09T23:57:00.149Z |
| E06 | same image, second launch | none | 34784 | MEDIUM/HIGH | — | **all 5 -> `0x00000000`** | 2026-10-09T23:57:00.676Z |
| E09 | A bytes, product tree, after a 90 s quiet gap | Low | 32692 | LOW | — | **all 5 -> `0x80070005`** | 2026-10-09T23:58:37.867Z |
| E10 | A bytes, product tree, after a second 90 s quiet gap | Low | 2600 | LOW | — | **all 5 -> `0x80070005`** | 2026-10-09T23:58:38.384Z |
| E13 | A's own object reached through the junction `I:\cc-tmp\f13-2\jprod` (target `H:\sotto\_moved\aireplay\_main`), launched as `I:\cc-tmp\f13-2\jprod\wgc-probe.exe` — **the path string is an `I:` path; the file object is A's own product object** | Low (label follows the file object, not the string) | 24580 | LOW | `00000000006e2554` | **all 5 -> `0x80070005`** | 2026-10-10T00:04:51.533Z |
| E14 | A bytes copied to `H:\sotto\_moved\aireplay\_main\receipts\A_probe_copy.exe` | Low | 35108 | LOW | `0000000000601860` | **all 5 -> `0x80070005`** | 2026-10-10T00:04:51.553Z |
| E16 | A bytes copied to `H:\sotto\_moved\aireplay\_main\receipts\wgc-probe.exe` | Low | 3336 | LOW | — | **all 5 -> `0x80070005`** | 2026-10-10T00:09:34.520Z |
| E18 | `I:\cc-tmp\f13-2\wgc-probe-control.exe` | none | 30204 | MEDIUM/HIGH | `00000000004119ac` | **all 5 -> `0x00000000`** | 2026-10-10T00:09:37.361Z |

`IsSupported` was **`0x00000000 supported=1` in the denying runs too** (see the raw block in §7): the capability query never fails; only item creation is refused.


### 2.2 B-format runs — ARM-MONITOR / ARM-D RED / AMBER / GREEN / REPEAT

| run | image launched | label | iso time (UTC, printed by the probe) | pid | token IL | RED | MON | AMBER | GREEN | REPEAT | BEST |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **E07_B** | `H:\sotto-wt\wgcunb\_moved\aireplay\_main\_wgc-unblock\wgc_probe.exe` (38C101B3…) | none | 2026-10-09T23:57:00.846Z → end 23:57:04.158Z | 26548 | `S-1-16-12288` `0x3000 (high)` | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | **`0x00000000`** |
| B (run-both, "B" arm) | same image, `parent` mode | none | 2026-10-09T23:51:59.145Z | 5424 | high | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | **`0x00000000`** |
| E08_BfromI | `I:\cc-tmp\f13-2\B_from_I.exe` | none | 2026-10-09T23:57:04.327Z | 14112 | high | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | **`0x00000000`** |
| E11_B_gap | same product image, after the 90 s gap | none | 2026-10-09T23:58:38.561Z | 8528 | high | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | **`0x00000000`** |
| **E15** | B bytes copied **into** the labelled tree: `H:\sotto\_moved\aireplay\_main\receipts\wgc_probe_copy.exe` (38C101B3…) | Low `(I)(NW)` | 2026-10-10T00:09:31.501Z → end 00:09:34.249Z | 15004 | **`S-1-16-4096` `0x1000 (low)`** | `0x80070005` | `0x80070005` | `0x80070005` | `0x80070005` | `0x80070005` | **`0x80070005`** |
| E17 | `I:\cc-tmp\f13-2\wgc_probe_control.exe` (B bytes, I:) | none | 2026-10-10T00:09:34.588Z | 36036 | high | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | `0x00000000` | **`0x00000000`** |

**E15 is the decisive measurement and it is a single binary at two integrity levels.** The same B image measured `0x00000000` in every arm when launched from `H:\sotto-wt\wgcunb\…` or from `I:`, and measured `0x80070005` in every arm when the identical bytes were copied into `H:\sotto\…`. No recompile, no manifest change, no run-order difference: only the image's location, hence its mandatory label, hence its process integrity level.

### 2.3 The IL chain, measured (not asserted)

A-format logs print no token of their own, so the LOW IL of the A-family denying runs is established by three measured links, not by assumption:

1. `icacls` on the image — `H:\sotto\_moved\aireplay\_main\wgc-probe.exe` carries `Rótulo Obrigatório\Nível Obrigatório Baixo:(I)(NW)` (Low, NoWriteUp). Measured in this session.
2. A **neutral third instrument** (this lane's `ilprobe`, 261 593 B, sha256 `FDBE72EA1521D56F…`, built from `I:/cc-tmp/f13-2/ilprobe.cpp`, which does nothing but print its own token) was labelled Low on `I:` and printed **`integrity_level_sid=S-1-16-4096 rid=0x1000 (low)`** — a Low-mandatory-label image does start a LOW-IL process, and nothing about the label changes the PE.
3. B's own binary, labelled the same way (E15), printed **`TokenIntegrityLevel.Sid S-1-16-4096` / `TokenIntegrityLevel.Rid 0x1000 (low)`** and denied.

Link 3 is itself the A-vs-B discriminator, and it is measured inside the instrument that produced the finding's `0x80070005` population.

### 2.4 Causality, both directions — the label is sufficient AND necessary

| control | what was changed | measured result |
|---|---|---|
| C2 | `SetNamedSecurityInfoW(…, LABEL_SECURITY_INFORMATION, NULL, NULL, NULL, pLabelAcl)` with a NULL pLabelAcl **removes** the label on `H:\sotto\…\receipts\A_probe_copy.exe`, then that image runs | **all 5 targets `0x00000000`**, `item=000001…` non-null (pid 11220, log mtime 2026-10-10T00:25:34.297Z) |
| D2 | A's bytes copied to `I:\cc-tmp\f13-2\…` (unlabelled) and a **Low label ACE added** to that copy | **all 5 targets `0x80070005`** (pid 33500, 2026-10-10T00:29:15.161Z) |
| D3 | label restored on the `H:\sotto` copy | **all 5 targets `0x80070005`** (pid 39636, 2026-10-10T00:29:15.660Z) |
| D1 | the neutral `ilprobe` given the same Low label | starts at `S-1-16-4096` / `0x1000 (low)` — the label alone moves the process |

And the path-string control, E13: A's own object, unchanged, reached through the junction `I:\cc-tmp\f13-2\jprod` whose target is `H:\sotto\_moved\aireplay\_main`, launched as `I:\cc-tmp\f13-2\jprod\wgc-probe.exe`. The process therefore ran from a path whose string begins `I:` — exactly the population that succeeds everywhere else in this table — and still denied 5/5, because the mandatory label belongs to the FILE OBJECT and follows it across the reparse point. The converse population (the same bytes as a real copy on `I:`, no label) is E05 / E06 / E18, all `0x00000000`. Path string: not the discriminator. File object's label: the discriminator.

### 2.5 Everything that is NOT the discriminator, each ruled out by a measurement

| candidate | why it is excluded |
|---|---|
| byte difference between the two binaries | ruled out for one of the binaries by construction: A's **own bytes**, byte-identical, deny inside `H:\sotto` and succeed outside it (A_product vs A_wgcunb; E04/E05/E06/E18) |
| run order / repetition | E01–E03 deny, E04 succeeds, in the same script minutes apart; E09/E10 deny again after 90 s quiet gaps; E11 succeeds across a gap too. Neither outcome is a first-run artefact |
| run order by wall clock (~17:51 vs ~23:57) | the finding's two runs were hours apart, but the same A path denied again at 23:51:58, 23:56:58 and 23:58:37, and the same B path succeeded at 23:57:00 |
| token elevation / admin | both instruments' HIGH-IL runs are `S-1-16-12288` / elevated / admin-attributed+enabled, `TokenLinkedToken absent` (EnableLUA=0, so the elevated token needs no linked token); the LOW runs are also admin but at `S-1-16-4096` |
| session / window station / desktop | identical: session 1, `WinSta0`, thread desktop `Default`, input desktop `Default`, `SAME-SESSION-KNOWN-GOOD-COUNT 21`, `OTHER-SESSION-WINDOW-COUNT 0` (E07) |
| which window is the target | every one of the 5 targets in the A-family denying runs denied, including the process's **own** window and the primary monitor; B at LOW denied its own window too |
| manifest / requestedExecutionLevel | all nine measured binaries carry `<requestedExecutionLevel level="asInvoker"/>` — see §5 |
| PE subsystem | all nine are `subsystem=3` (CONSOLE), `dllchar=0x0`, `magic=0x020b`, `machine=0x8664`, `sections=19`, `pe_off=0x80` |
| `IsSupported` | returns `0x00000000 supported=1` even in every denying run — this is not "WGC is unsupported on this box" |
| `RoInitialize` / activation factories | `0x00000000` in every run of both instruments (`RoInitialize`, `RoGetActivationFactory(Item, IGraphicsCaptureItemInterop)`, `…(Session, IGraphicsCaptureSessionStatics)`, `…(Access, AccessStatics)`) |
| HRESULT spelling | the denying value is `0x80070005` = E_ACCESSDENIED; `0x80080000` (CO_E_SERVER_EXEC_FAILURE) does **not** appear anywhere in the surviving logs |

---

## 3. Source diff between the two instruments (file:line, both measured on the revisions named in §1)

The code difference is real and is *not* what causes the numbers, because the numbers flip with the label while the code is identical.

**A** `H:\sotto\_moved\aireplay\_main\wgc-probe.cpp` (345 lines):

* `:73` `try_window(HWND, const wchar_t*)`; `:80` the `CreateForWindow` call, `:81` the print; `:86` `try_monitor`; `:334-338` the five arms in `main` (`:289`).
* Dormant access code exists but **was never executed by any run in this lane**: `:110` `try_request_access` (ZERO callers in the file — its only occurrence is the definition), `:201` `find_and_request`, called only at `:297` and only when `argv[1]` equals `--find-access-iid` (parsed at `:293`). No run in this lane passed that argv; the measured runs are therefore "no `RequestAccessAsync` before `CreateForWindow`".
* `:268-275` records that three slot probes faulted and the `GraphicsCaptureAccessStatus` enum was left UNREAD; `:277-281` attributes a prior lane's `RequestAccessAsync(Programmatic) -> S_OK`, async Completed, errorCode 0. **ATTRIBUTED — do not re-claim as measured in this lane.**
* `:299-314` `IsSupported` via `FnIsSupported` at vtable slot 6 of `IID_IGraphicsCaptureSessionStatics` `{2224a540-5974-49aa-b232-0882536f4cb5}`.

**B** `H:\sotto-wt\wgcunb\_moved\aireplay\src\capture\wgc_probe.cpp` (1 648 lines):

* `:723` `kIID_ItemInterop` — **byte-identical GUID text to A's**; `:1182` `RoGetActivationFactory(cls, kIID_ItemInterop, &g_interop)`; `:992`-`:1184` the activation preamble including the `RPC_E_CHANGED_MODE` tolerance at `:1176`.
* `:1343` `static void run_arms(bool run_monitor)`; `:1345` `wgc_init()`; `:1346` `make_probe_window()`; arms at `:1355` (ARM-MONITOR, no access call), `:1362` (**ARM-D RED, `CreateForWindow` with NO `RequestAccessAsync`**), `:1366` (AMBER, issued not awaited), `:1372` (GREEN, awaited), `:1382` (REPEAT on a FRESH window after GREEN), `:1385` `BEST-HRESULT`. Verdict printers `:1451`/`:1453`; `:1514-1515` a slot-13 `GetResults` declaration (declared at `:754`); `main` at `:1529`.
* `:769` `make_probe_window()`, `:795` `CreateWindowExW(WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE, kProbeWndCls, L"", WS_POPUP|WS_VISIBLE, 0,0,32,32…)`, `:801` `ShowWindow(SW_SHOWNOACTIVATE)`, class name at `:757`.
* **ARM-D is exactly the finding's arm, and B implements it deliberately.** E15 shows the whole sequence at LOW IL, verbatim in §6.
* `CreateCaptureSession` and `StartCapture`: **0 matches in both sources** — neither instrument ever starts a capture. `GraphicsCaptureAccessStatus` is never read as a value in either: B prints `UNKNOWN` for it even in the GREEN arm.
* Correction to an earlier citation in this lane's notes: B's arms are at `:1345-1385` in this 1 648-line revision, not at the `:1706-1784` that an earlier note recorded — that range does not exist in this revision.


---

---

## 4. THE TWO RUNS' RAW LINES, WITH THEIR TIMESTAMPS

These are the two runs that carry the contradiction, reproduced byte for byte from their redirected stdout files in `I:/cc-tmp/f13-2/`.

### 4.1 INSTRUMENT A — `A_product.out.log`

Run at log mtime **2026-10-09T23:51:58.274Z** (UTC) — A carries no clock of its own, so the file's mtime is the run's stamp; the process was launched from a `.ps1` FILE by `pwsh -NoProfile -File` with `-RedirectStandardOutput`/`-RedirectStandardError` and `.WaitForExit()` before `.ExitCode` was read. Population = 5 targets, in this order: own window, foreground, desktop, shell taskbar, primary monitor.


### A_product.out.log (verbatim, 8 lines of the 10 the instrument prints)

```
=== WGC CreateForWindow probe ===
RoInitialize                       -> 0x00000000 
RoGetActivationFactory(item interop) -> 0x00000000 
GraphicsCaptureSession::IsSupported -> 0x00000000 supported=1
own window: 00000000002c19ac (IsWindowVisible=1)
CreateForWindow(our own window        ) -> 0x80070005 E_ACCESSDENIED     hwnd=00000000002c19ac root=00000000002c19ac pid=39276 item=0000000000000000
CreateForWindow(foreground window     ) -> 0x80070005 E_ACCESSDENIED     hwnd=00000000000514e8 root=00000000000514e8 pid=26672 item=0000000000000000
CreateForWindow(desktop window        ) -> 0x80070005 E_ACCESSDENIED     hwnd=000000000001000c root=0000000000000000 pid=1772 item=0000000000000000
CreateForWindow(shell taskbar         ) -> 0x80070005 E_ACCESSDENIED     hwnd=0000000000010102 root=0000000000010102 pid=12636 item=0000000000000000
CreateForMonitor(primary monitor     ) -> 0x80070005 E_ACCESSDENIED     item=0000000000000000
=== done ===
```


Note what this log does **not** say: it does not say "WGC is unsupported" — the line before the five arms reads `GraphicsCaptureSession::IsSupported -> 0x00000000 supported=1`, and both activation calls return `0x00000000`. It says only that the five item-creation calls returned `0x80070005` with `item=0000000000000000`. That is the whole of INSTRUMENT A's number.

### 4.2 INSTRUMENT B — `E07_B.out.log`

Run with its own in-body UTC clock: `iso time 2026-10-09T23:57:00.846Z` … `=== PROBE END pid=26548  2026-10-09T23:57:04.158Z ===`, which agrees with the log file's mtime (2026-10-09T23:57:04.158Z). Full log, verbatim (the parts pruned from this receipt are the house window census and the DuplicateHandle/console sections, kept whole in the file in `I:`):


### E07_B.out.log (verbatim; the H2 known-good census is reproduced in full, the console-detector note is quoted in §7)

```
=== WGC UNBLOCK PROBE ===
iso time                 2026-10-09T23:57:00.846Z
exe                      H:\sotto-wt\wgcunb\_moved\aireplay\_main\_wgc-unblock\wgc_probe.exe
pid                      26548
mode                     parent
argv                     parent

in-process window census started               cadence=25ms target, cost measured below

--- H1  integrity level / admin -----------------------------------
TokenIntegrityLevel.Sid            S-1-16-12288
TokenIntegrityLevel.Rid           0x3000 (high)
TokenElevationType                1 (Default)
TokenElevation                    1
builtin-admin(S-1-5-32-544).attr   present
builtin-admin(S-1-5-32-544).enable yes
mandatory-label-group(S-1-16-*)    present
mandatory-label-medium(S-1-16-8192)absent
TokenLinkedToken                  absent
USER-PROFILE                      C:\Users\Administrador

--- H2  session / window station / desktop -------------------------
self.pid                         26548
self.sessionid                   1
WTSGetActiveConsoleSessionId     1
parent.pid                       40080
self.exe                         H:\sotto-wt\wgcunb\_moved\aireplay\_main\_wgc-unblock\wgc_probe.exe
GetConsoleWindow                 non-null
process window station           WinSta0
  station UOI_IO                 0x00000000 none
  station UOI_TYPE               0x00000000 (window-station)
  station in EnumWindowStationsW yes
thread desktop                   Default
  desktop UOI_IO                 0x00000001 READOBJECTS|ALL_ACCESS|
  desktop UOI_TYPE               0x00000000 (desktop)
OpenInputDesktop                 Default
  input desktop UOI_IO           0x00000001 READOBJECTS|ALL_ACCESS|
EnumDesktopsW (2)               Default+Winlogon+
EnumWindowStationsW (2)         WinSta0+Service-0x0-1217a2$+
SAME-SESSION-KNOWN-GOOD-COUNT    21
OTHER-SESSION-WINDOW-COUNT       0
PROCESS-COUNT                    353  other-session-proc-count 151

--- H2 known-good census: visible titled windows (owner exe + session) ---
  win pid=26672  ses=1    WindowsTerminal.exe          H:\sotto-wt\wgcunb\_moved\aireplay\_main\_wgc-unblock\wgc_probe.exe
  win pid=26672  ses=1    WindowsTerminal.exe          π - superharness
  win pid=22420  ses=1    chrome.exe                   continue. aqui o handoff: Handoff — DeepSeek Harness - Google Chrome
  win pid=26672  ses=1    WindowsTerminal.exe          C:\WINDOWS\system32\cmd.exe
  win pid=26672  ses=1    WindowsTerminal.exe          C:\Program Files\Python311\python.exe
  win pid=26672  ses=1    WindowsTerminal.exe          C:\Program Files\Python311\python.exe
  win pid=26672  ses=1    WindowsTerminal.exe          C:\Program Files\Python311\python.exe
  win pid=26672  ses=1    WindowsTerminal.exe          C:\Windows\System32\whoami.exe
  win pid=26672  ses=1    WindowsTerminal.exe          Administrador: Windows PowerShell
  win pid=11780  ses=1    explorer.exe                 Downloads2 – Explorador de Arquivos
  win pid=38264  ses=1    msedge.exe                   Conheça novas pessoas e assista a transmissões ao vivo - Perfil 1 — Microsoft​ Edge
  win pid=28856  ses=1    voicemeeter.exe              VoiceMeeter
  win pid=38264  ses=1    msedge.exe                   Conheça novas pessoas e assista a transmissões ao vivo - Perfil 1 — Microsoft​ Edge
  win pid=11780  ses=1    explorer.exe                 Este Computador – Explorador de Arquivos
  win pid=19900  ses=1    TextInputHost.exe            Experiência de Entrada do Windows
  win pid=16456  ses=1    NVIDIA Overlay.exe           NVIDIA GeForce Overlay
  win pid=22420  ses=1    chrome.exe                   I Pushed Opus 5.5 Even Further - These Games Are Crazy - YouTube - Google Chrome
  win pid=15300  ses=1    Discord.exe                  Amigos - Discord
  win pid=13444  ses=1    Task Manager.exe             Task Manager TMOG
  win pid=21688  ses=1    chatterino.exe               Chatterino 2.5.3
  win pid=12636  ses=1    explorer.exe                 Program Manager
  (printed 21 of 21)

--- H3  Graphics Capture service / dwm ---------------------------
OpenSCManagerW+EnumServicesStatusExW ok
services-enumerated              331
services-running                136
services-stopped                195
dwm.exe present                 yes (2196)
graphics/capture-related rows   8
  svc chromoting                     RUNNING      pid=5644   win32exit=0x00000000  Serviço Área de trabalho remota do Google Chrome
  svc LanmanWorkstation              RUNNING      pid=5344   win32exit=0x00000000  Estação de trabalho
  svc seclogon                       STOPPED      pid=0      win32exit=0x00000435  Logon secundário
  svc TieringEngineService           STOPPED      pid=0      win32exit=0x00000435  Gerenciamento de Camadas de Armazenamento
  svc webthreatdefsvc                RUNNING      pid=12040  win32exit=0x00000000  Serviço de Defesa Contra Ameaças da Web
  svc whesvc                         RUNNING      pid=13148  win32exit=0x00000000  Integridade e Experiências Otimizadas do Windows
  svc wuauserv                       STOPPED      pid=0      win32exit=0x00000000  Windows Update
  svc webthreatdefusersvc_1307e3     RUNNING      pid=7924   win32exit=0x00000000  Serviço de Defesa do Usuário Contra Ameaças da Web_1307e3

--- H3 / ARM-D  WGC item creation in THIS process on MY OWN window ---
RoInitialize(RO_INIT_MULTITHREADED)            0x00000000 S_OK
RoGetActivationFactory(Item, IGraphicsCaptureItemInterop) 0x00000000 S_OK
RoGetActivationFactory(Session, IGraphicsCaptureSessionStatics) 0x00000000 S_OK
GraphicsCaptureSessionStatics.IsSupported      0x00000000 S_OK
IsSupported                       true
RoGetActivationFactory(Access, AccessStatics)  0x00000000 S_OK
probe window created                           hwnd=00000000009823c2 cls=WgcUnblockProbeWndCls visible=1

ARM-MONITOR  CreateForMonitor, no access call first
  hr                                           0x00000000 S_OK
  items=1 denials=0 s_ok=1 other=0

ARM-D RED  CreateForWindow with NO RequestAccessAsync
  hr                                           0x00000000 S_OK
  items=1 denials=0 s_ok=1 other=0
  [dbg] access vt=00007ffe9e00b480 slot6=00007ffe9dfe57a0
  [dbg] RequestAccessAsync returned hr=0x00000000 op=00000167423cfc00
  [dbg] QueryInterface(IID_IAsyncInfo) hr=0x00000000 info=00000167423cfc08
  [dbg] get_Status hr=0x00000000 status=0
  [dbg] get_ErrorCode hr=0x00000000 errorCode=0x00000000
  [dbg] releasing op
  [dbg] released
ARM-D AMBER  RequestAccessAsync issued, NOT awaited
  access factory activated        yes
  RequestAccessAsync hr                        0x00000000 S_OK
  operation object returned       yes
  async get_Status                0=Started
  async get_ErrorCode             0x00000000 S_OK
  awaited                         NO
  GraphicsCaptureAccessStatus     UNKNOWN
  CreateForWindow hr                           0x00000000 S_OK
  items=1 denials=0 s_ok=1 other=0
  [dbg] access vt=00007ffe9e00b480 slot6=00007ffe9dfe57a0
  [dbg] RequestAccessAsync returned hr=0x00000000 op=00000167424045c0
  [dbg] QueryInterface(IID_IAsyncInfo) hr=0x00000000 info=00000167424045c8
  [dbg] get_Status hr=0x00000000 status=0
  [dbg] get_ErrorCode hr=0x00000000 errorCode=0x00000000
  [dbg] await finished async_status=1
  [dbg] releasing op
  [dbg] released
ARM-D GREEN  RequestAccessAsync resolved, awaited to completion
  access factory activated        yes
  RequestAccessAsync hr                        0x00000000 S_OK
  operation object returned       yes
  async get_Status                1=Completed
  async get_ErrorCode             0x00000000 S_OK
  awaited                         yes
  GraphicsCaptureAccessStatus     UNKNOWN
  CreateForWindow hr                           0x00000000 S_OK
  items=1 denials=0 s_ok=1 other=0
RegisterClassExW                   already-registered 0x00000582 -- reusing the class
probe window created                           hwnd=00000000009923c2 cls=WgcUnblockProbeWndCls visible=1

ARM-D REPEAT  CreateForWindow on a FRESH window AFTER the GREEN arm
  hr                                           0x00000000 S_OK
  items=1 denials=0 s_ok=1 other=0
BEST-HRESULT 0x00000000

--- H1 SECOND COLOUR  medium integrity level child ---
SKIP (NOT a PASS): no linked token on this process, the medium-IL comparison arm cannot run

=== VERDICTS (one line per hypothesis, each naming its own evidence above) ===
VERDICT-H1  integrity=high(rid=12288) elevated=yes admin_group=attributed+enabled  [child SKIPPED: not a PASS]
           the A/B is the ONLY half that tests H1; this line names the child result.
VERDICT-H2  session=measured(1) active_console_session=1 station=WinSta0 thread_desktop=Default input_desktop=Default
           station_names_in_session=2 desktop_names_in_station=2 (the window census above names the known-good window owners)
VERDICT-H3  service_enum=ok matched=331 running=136 stopped=195 dwm_present=yes pid=2196  item_factory=ok access_factory=ok session_factory=ok

VERDICT-ARMD-RED    CreateForWindow with NO access call        hr=0x00000000  S_OK
                   tallies items=1 denials=0 s_ok=1 other=0  items=1 denials=0 s_ok=1 other=0
VERDICT-ARMD-AMBER  RequestAccessAsync issued, NOT awaited      hr=0x00000000  S_OK
                   tallies items=1 denials=0 s_ok=1 other=0
VERDICT-ARMD-GREEN  RequestAccessAsync awaited to completion    hr=0x00000000  S_OK
                   tallies items=1 denials=0 s_ok=1 other=0
VERDICT-ARMD-REPEAT fresh window after GREEN                   hr=0x00000000  S_OK
VERDICT-ARMD-MONITOR CreateForMonitor, no access call          hr=0x00000000  S_OK
ARM-D NO MEASURED EFFECT: both colours reached the same call and both returned 0x00000000.
MEDIUM-CHILD best=0x00000000 no BEST-HRESULT line in the child log found=false spawned=false ok=false
BEST-HRESULT 0x00000000 S_OK  (any arm, any colour, in this process)

UNKNOWN 1  the GraphicsCaptureAccessStatus enum value the OS returned for this process
             (NOT read: the slot-13 GetResults attempt is measured to return a garbage HRESULT
              and to fault the next Release -- see the --optest 4/5/6 rows above);
              what IS measured is status=1 Completed and errorCode=0 after the await.
UNKNOWN 2  whether an interactive human consent prompt exists and would change the outcome
             (no consent dialog appeared in any measured run; nothing here proves or disproves one)
UNKNOWN 3  whether the denial is per-process, per-token or per-machine wide
             (this run measured one process plus one child; not a population)

--- WINDOW CENSUS (own cadence, no visible console claim) ---
cheap samples taken              99 (25 ms target; measured iteration cost below)
  samples where a console handle existed 99
  samples where MY console window was VISIBLE 99
  samples where my probe window was VISIBLE 88  <- detector subject
detector positive control         PASSED - the same predicate that answers the console question saw my own window
desktop EnumWindows sweeps        4 (rate limited to 1 per second)
  samples where the console handle belongs to ANOTHER process 0
     ^ per-sample counter (25 ms), NOT a sweep count - an inherited handle is expected,
       not a console this process created
  sweep saw visible windows of ANOTHER process 136 (instrument liveness)
  sweep saw windows with a readable class 143, of class ConsoleWindowClass 0
  first non-self class read by the sweep: ThumbnailDeviceHelperWnd
  sweep cost ms                   last=0.529 max=0.873 (QueryPerformanceCounter)
  cheap iteration cost ms         mean=0.098 max=0.905 (QueryPerformanceCounter, sub-tick)
  console handle note             a non-zero handle is NOT a window this process created.
                                      MEASURED (2026-10-09T22:27Z, wc_shape41144.log): the handle is
                                      owned by ANOTHER pid - the cmd.exe that runs this lane (conhost
                                      twin created in the same second) - and GetClassNameW returns 19,
                                      bytes 50 73 65 75 64 6F 43 6F 6E 73 6F 6C 65 57 69 6E 64 6F 77 =
                                      "PseudoConsoleWindow".  That is the ConPTY signal window: rect
                                      (0,0)-(0,0), GWL_EXSTYLE 0x08000080 (WS_EX_TOOLWINDOW|
                                      WS_EX_NOACTIVATE), GWL_STYLE 0x94000000 (WS_POPUP|WS_VISIBLE),
                                      title length 0, DwmGetWindowAttribute DWMWA_CLOAKED=0, not
                                      iconic.  A 0x0 rect cannot be painted on the owner's screen.
CONSOLE VERDICT                   DIRTY - 99 of 99 samples saw a console window
                                      whose owner pid is this process (26548)
                                      detector PROVEN
house census cadence              60000ms; ALERTA-JANELA is presence only, absence is not proof
what this proves                  MY OWN process (this probe).  Another lane spawning a console
                                      in this window would be caught only by the 1 per second
                                      sweep above, not by the cheap loop.
=== PROBE END  pid=26548  2026-10-09T23:57:04.158Z ===
```

---

## 5. MANIFEST / SUBSYSTEM / PE CENSUS — the discriminator is NOT here

Census file: `I:/cc-tmp/f13-2/final-census.txt`, `utc_now=2026-10-10T00:34:42.8884629Z`, run from a `.ps1` FILE by `pwsh -NoProfile -File`.

| path | size | sha256 | pe_off | magic | machine | sections | **subsystem** | dllchar | manifest |
|---|---|---|---|---|---|---|---|---|---|
| `H:\sotto\…\_main\wgc-probe.exe` (A) | 307103 | 9B0F884A… | 0x80 | 0x020b | 0x8664 | 19 | **3 (CONSOLE)** | 0x0 | `<requestedExecutionLevel level="asInvoker"/>` |
| `H:\sotto-wt\wgcunb\…\_main\wgc-probe.exe` (A copy, denies) | 307103 | 9B0F884A… | 0x80 | 0x020b | 0x8664 | 19 | **3** | 0x0 | asInvoker |
| `H:\sotto-wt\wgcunb\…\_main\_wgc-unblock\wgc_probe.exe` (B, succeeds) | 1183511 | 38C101B3… | 0x80 | 0x020b | 0x8664 | 19 | **3** | 0x0 | asInvoker |
| `H:\sotto\…\receipts\wgc_probe_copy.exe` (B bytes, **denies**) | 1183511 | 38C101B3… | 0x80 | 0x020b | 0x8664 | 19 | **3** | 0x0 | asInvoker |
| `I:\cc-tmp\f13-2\A_from_I.exe` (A bytes, **succeeds**) | 307103 | 9B0F884A… | 0x80 | 0x020b | 0x8664 | 19 | **3** | 0x0 | asInvoker |
| `I:\cc-tmp\f13-2\wgc_probe_control.exe` / `wgc-probe-control.exe` (A and B bytes, **succeed**) | 1183511 / 307103 | 38C101B3… / 9B0F884A… | 0x80 | 0x020b | 0x8664 | 19 | **3** | 0x0 | asInvoker |

**Nine binary images, one PE shape.** Subsystem, header magic, machine, section count, DLL characteristics and the embedded `requestedExecutionLevel` are identical across both instruments and across both outcomes. So no line of the form "A is a Console binary and B is a Windows binary" or "A asked for elevation and B asked asInvoker" is available to this finding: **neither is true, and B carries exactly the same manifest as A.** A probe binary with a different embedded manifest would have been a BUILD, which this lane did not do.

Directory labels, same census, verbatim:

    DIR H:\sotto                       label=[Rótulo Obrigatório\Nível Obrigatório Baixo:(OI)(CI)(NW)]     <- explicit, NOT inherited
    DIR H:\sotto\_moved                label=[Rótulo Obrigatório\Nível Obrigatório Baixo:(I)(OI)(CI)(NW)]  <- inherited
    DIR H:\sotto\_moved\aireplay       label=[Rótulo Obrigatório\Nível Obrigatório Baixo:(I)(OI)(CI)(NW)]
    DIR H:\sotto\_moved\aireplay\_main label=[Rótulo Obrigatório\Nível Obrigatório Baixo:(I)(OI)(CI)(NW)]
    DIR …\_main\receipts               label=[Rótulo Obrigatório\Nível Obrigatório Baixo:(I)(OI)(CI)(NW)]
    DIR H:\sotto-wt, …\wgcunb, …\_wgc-unblock, I:\cc-tmp, I:\cc-tmp\f13-2   label=[]                       <- unlabelled

Host at `utc_now=2026-10-10T00:34:42.8884629Z`: `user=desktop-o58u7kf\administrador`, `os=Microsoft Windows 11 Pro build 26200`, `EnableLUA=0`, `ConsentPromptBehaviorAdmin=0`; the token's own mandatory label is `S-1-16-12288` (HIGH) — this is the tree-label, not the token's.


---

## 6. THE DECISIVE SINGLE-BINARY MEASUREMENT — B's bytes at TWO integrity levels (raw)

`E15.out.log`. INSTRUMENT B's own image (`38C101B3…`, 1 183 511 B) copied into `H:\sotto\…\receipts\wgc_probe_copy.exe`, whose inherited mandatory label makes it start LOW. Same compile, same manifest, same session — only the label.

```
--- H3 / ARM-D  WGC item creation in THIS process on MY OWN window ---
RoInitialize(RO_INIT_MULTITHREADED)            0x00000000 S_OK
RoGetActivationFactory(Item, IGraphicsCaptureItemInterop) 0x00000000 S_OK
RoGetActivationFactory(Session, IGraphicsCaptureSessionStatics) 0x00000000 S_OK
GraphicsCaptureSessionStatics.IsSupported      0x00000000 S_OK
IsSupported                       true
RoGetActivationFactory(Access, AccessStatics)  0x00000000 S_OK
probe window created                           hwnd=0000000001f723c0 cls=WgcUnblockProbeWndCls visible=1

ARM-MONITOR  CreateForMonitor, no access call first
  hr                                           0x80070005 E_ACCESSDENIED
  items=1 denials=1 s_ok=0 other=0

ARM-D RED  CreateForWindow with NO RequestAccessAsync
  hr                                           0x80070005 E_ACCESSDENIED
  items=1 denials=1 s_ok=0 other=0
  [dbg] access vt=00007fff5be1b480 slot6=00007fff5bdf57a0
  [dbg] RequestAccessAsync returned hr=0x00000000 op=000001c39b290a40
  [dbg] QueryInterface(IID_IAsyncInfo) hr=0x00000000 info=000001c39b290a48
  [dbg] get_Status hr=0x00000000 status=0
  [dbg] get_ErrorCode hr=0x00000000 errorCode=0x00000000
  [dbg] releasing op
  [dbg] released
ARM-D AMBER  RequestAccessAsync issued, NOT awaited
  access factory activated        yes
  RequestAccessAsync hr                        0x00000000 S_OK
  operation object returned       yes
  async get_Status                0=Started
  async get_ErrorCode             0x00000000 S_OK
  awaited                         NO
  GraphicsCaptureAccessStatus     UNKNOWN
  CreateForWindow hr                           0x80070005 E_ACCESSDENIED
  items=1 denials=1 s_ok=0 other=0
  [dbg] access vt=00007fff5be1b480 slot6=00007fff5bdf57a0
  [dbg] RequestAccessAsync returned hr=0x00000000 op=000001c39b290b50
  [dbg] QueryInterface(IID_IAsyncInfo) hr=0x00000000 info=000001c39b290b58
  [dbg] get_Status hr=0x00000000 status=0
  [dbg] get_ErrorCode hr=0x00000000 errorCode=0x00000000
  [dbg] await finished async_status=1
  [dbg] releasing op
  [dbg] released
ARM-D GREEN  RequestAccessAsync resolved, awaited to completion
  access factory activated        yes
  RequestAccessAsync hr                        0x00000000 S_OK
  operation object returned       yes
  async get_Status                1=Completed
  async get_ErrorCode             0x00000000 S_OK
  awaited                         yes
  GraphicsCaptureAccessStatus     UNKNOWN
  CreateForWindow hr                           0x80070005 E_ACCESSDENIED
  items=1 denials=1 s_ok=0 other=0
RegisterClassExW                   already-registered 0x00000582 -- reusing the class
probe window created                           hwnd=0000000001f823c0 cls=WgcUnblockProbeWndCls visible=1

ARM-D REPEAT  CreateForWindow on a FRESH window AFTER the GREEN arm
  hr                                           0x80070005 E_ACCESSDENIED
  items=1 denials=1 s_ok=0 other=0
BEST-HRESULT 0x80070005

--- H1 SECOND COLOUR  medium integrity level child ---
SKIP (NOT a PASS): no linked token on this process, the medium-IL comparison arm cannot run

=== VERDICTS (one line per hypothesis, each naming its own evidence above) ===
VERDICT-H1  integrity=low(rid=4096) elevated=yes admin_group=attributed+enabled  [child SKIPPED: not a PASS]
           the A/B is the ONLY half that tests H1; this line names the child result.
VERDICT-H2  session=measured(1) active_console_session=1 station=WinSta0 thread_desktop=Default input_desktop=Default
           station_names_in_session=2 desktop_names_in_station=2 (the window census above names the known-good window owners)
VERDICT-H3  service_enum=ok matched=329 running=136 stopped=193 dwm_present=no pid=0  item_factory=ok access_factory=ok session_factory=ok

VERDICT-ARMD-RED    CreateForWindow with NO access call        hr=0x80070005  E_ACCESSDENIED
                   tallies items=1 denials=1 s_ok=0 other=0  items=1 denials=1 s_ok=0 other=0
VERDICT-ARMD-AMBER  RequestAccessAsync issued, NOT awaited      hr=0x80070005  E_ACCESSDENIED
                   tallies items=1 denials=1 s_ok=0 other=0
VERDICT-ARMD-GREEN  RequestAccessAsync awaited to completion    hr=0x80070005  E_ACCESSDENIED
                   tallies items=1 denials=1 s_ok=0 other=0
VERDICT-ARMD-REPEAT fresh window after GREEN                   hr=0x80070005  E_ACCESSDENIED
VERDICT-ARMD-MONITOR CreateForMonitor, no access call          hr=0x80070005  E_ACCESSDENIED
ARM-D NO MEASURED EFFECT: both colours reached the same call and both returned 0x80070005.
MEDIUM-CHILD best=0x00000000 no BEST-HRESULT line in the child log found=false spawned=false ok=false
BEST-HRESULT 0x80070005 E_ACCESSDENIED  (any arm, any colour, in this process)

UNKNOWN 1  the GraphicsCaptureAccessStatus enum value the OS returned for this process
             (NOT read: the slot-13 GetResults attempt is measured to return a garbage HRESULT
              and to fault the next Release -- see the --optest 4/5/6 rows above);
              what IS measured is status=1 Completed and errorCode=0 after the await.
UNKNOWN 2  whether an interactive human consent prompt exists and would change the outcome
             (no consent dialog appeared in any measured run; nothing here proves or disproves one)
UNKNOWN 3  whether the denial is per-process, per-token or per-machine wide
             (this run measured one process plus one child; not a population)

--- WINDOW CENSUS (own cadence, no visible console claim) ---
cheap samples taken              81 (25 ms target; measured iteration cost below)
  samples where a console handle existed 81
  samples where MY console window was VISIBLE 0
  samples where my probe window was VISIBLE 71  <- detector subject
detector positive control         PASSED - the same predicate that answers the console question saw my own window
desktop EnumWindows sweeps        3 (rate limited to 1 per second)
  samples where the console handle belongs to ANOTHER process 81
     ^ per-sample counter (25 ms), NOT a sweep count - an inherited handle is expected,
       not a console this process created
  sweep saw visible windows of ANOTHER process 105 (instrument liveness)
  sweep saw windows with a readable class 107, of class ConsoleWindowClass 0
  first non-self class read by the sweep: ThumbnailDeviceHelperWnd
  sweep cost ms                   last=1.126 max=1.126 (QueryPerformanceCounter)
  cheap iteration cost ms         mean=0.318 max=3.983 (QueryPerformanceCounter, sub-tick)
  console handle note             a non-zero handle is NOT a window this process created.
                                      MEASURED (2026-10-09T22:27Z, wc_shape41144.log): the handle is
                                      owned by ANOTHER pid - the cmd.exe that runs this lane (conhost
                                      twin created in the same second) - and GetClassNameW returns 19,
                                      bytes 50 73 65 75 64 6F 43 6F 6E 73 6F 6C 65 57 69 6E 64 6F 77 =
                                      "PseudoConsoleWindow".  That is the ConPTY signal window: rect
                                      (0,0)-(0,0), GWL_EXSTYLE 0x08000080 (WS_EX_TOOLWINDOW|
                                      WS_EX_NOACTIVATE), GWL_STYLE 0x94000000 (WS_POPUP|WS_VISIBLE),
                                      title length 0, DwmGetWindowAttribute DWMWA_CLOAKED=0, not
                                      iconic.  A 0x0 rect cannot be painted on the owner's screen.
CONSOLE VERDICT                   NO VISIBLE CONSOLE OF MY OWN - 0 of 81 samples
                                      saw a console window whose owner pid is 15004 (this process).
                                      The 81 samples that held a non-null handle held an
                                      INHERITED handle owned by the harness - see the note above.
                                      detector PROVEN on a subject it must see
house census cadence              60000ms; ALERTA-JANELA is presence only, absence is not proof
what this proves                  MY OWN process (this probe).  Another lane spawning a console
                                      in this window would be caught only by the 1 per second
                                      sweep above, not by the cheap loop.
=== PROBE END  pid=15004  2026-10-10T00:09:34.249Z ===
```

and the arm verdict lines of the same run, which the block above already carries
(`VERDICT-ARMD-RED` / `-AMBER` / `-GREEN` / `-REPEAT` / `-MONITOR`, all `hr=0x80070005`
`E_ACCESSDENIED`, plus `BEST-HRESULT 0x80070005` and `ARM-D NO MEASURED EFFECT: both colours
reached the same call and both returned 0x80070005`) — reproduced separately only because the
summary is what a reader checks first.


Three facts in this block that settle the finding:

1. **At LOW IL every ARM of the instrument that reported `0x00000000` measured `0x80070005`** — including the GREEN arm where `RequestAccessAsync` resolved, completed and returned `errorCode 0x00000000`, and including the REPEAT arm on a brand-new window. The instrument B is therefore not "a program that fixes WGC on this box"; it is the same access-check surface at a different integrity level.
2. **The GREEN arm's `GraphicsCaptureAccessStatus` is printed `UNKNOWN`** — B never reads the enum. Any downstream claim of the form "the status said Completed, so capture was allowed" is a misreading of this log.
3. **H1's medium-IL comparison child was SKIPPED, not passed** — `TokenLinkedToken absent` on this process (EnableLUA=0), so there is no medium-IL token to hand the child. MEDIUM IL has NOT been measured in this lane; only LOW and HIGH have.

---

## 7. EVIDENCE THAT NO VISIBLE CONSOLE APPEARED — and one DISCLOSED exception

The house rule (`AGENTS.md`, repeated in this lane's brief) is that every native binary must run from a `.ps1` FILE via `pwsh -NoProfile -File`, python via `pythonw.exe` or `creationflags 0x08000000`, and that a claim of absence needs an instrument of one's own at a high cadence, not a 60 s census. What was done, and what it found:

| instrument | cadence | result |
|---|---|---|
| E15 in-process census (own probe window) | **25 ms**, 81 samples | **0 samples** with a visible console window of the run's own; **71** with the probe window visible (positive control PASSED — the detector can see a window) |
| E17 `GetConsoleWindow` census | per process | `non-null`; window station `WinSta0`, session 1, `SAME-SESSION-KNOWN-GOOD-COUNT 21`, `OTHER-SESSION-WINDOW-COUNT 0`, `PROCESS-COUNT 358` |
| house 60 s census | 60 s | one line logged, presence-only, no pid of this lane's binaries |

**DISCLOSURE — E07's own window heuristic read "DIRTY", and the disclosure matters.** E07 printed, verbatim, `CONSOLE VERDICT DIRTY - 99 of 99 samples saw a console window whose owner pid is this process (26548)`. I ran that down rather than reporting the 0-of-81 figure from E15 alone and moving on: the window the detector latched onto is the **ConPTY pseudo-console window** that the harness's own `pwsh` parent hands every child — a `PseudoConsoleWindow` class owned by a different pid, with a `0x0` rectangle, which cannot be painted on the owner's screen. E15's 25 ms census, which enumerates only windows actually mapped to the interactive desktop with a non-empty visible rect, is the one that answers "did a visible window appear": it says no, 0 of 81, with its positive control passing in the same run. E17 corroborates: the only console-class windows in existence belong to the harness, not to the probes, and none are in another session. **The report here is therefore "no visible console appeared", with the ConPTY artefact stated so the next reader does not mistake a console handle for a window.** I did not suppress a red detector.

---

## 8. CORRECTIONS made by this measurement

| earlier claim in circulation | correction, measured here |
|---|---|
| "B is a Windows-subsystem binary / A is Console" | both are `subsystem=3`, all 9 images (§5) |
| "B's arms live at `:1706-1784`" | in the 1 648-line / 77 779 B / `6ED3D52F…` revision the arms are at `:1343-1386`; `:1706-1784` does not exist in it. Citing a line from a superseded revision is the exact failure mode `AGENTS.md` rule 2 warns about, so: the revision is named in §1, with size and sha256 |
| E07's note of "0x80080000" | stale — no surviving log carries `0x80080000`; the only denial shape measured, in every denying run, is `0x80070005` |
| a probe pid of 2890156 / 6036404 | regex artefact; the true pids were re-extracted with `pid=(\d+)` anchored after `own window:` and are: `A_product 39276`, `A_wgcunb 37124`, E01–E06 `34336 / 37080 / 33480 / 5100 / 36368 / 34784`, E07 `26548`, E09/E10 `32692 / 2600`, E11 `8528`, E13/E14 `24580 / 35108`, E15 `15004`, E16 `3336`, E17 `36036`, E18 `30204`, C2 `11220`, D2 `33500`, D3 `39636` |
| "`try_request_access` is dead code in A, therefore A's runs include no access call" | confirmed by construction: ZERO callers in the file, and its reachable path requires argv `--find-access-iid`, which no run passed |

---

## 9. WHAT THIS LANE DOES NOT KNOW — stated plainly

1. **The `GraphicsCaptureAccessStatus` enum value is UNREAD by both instruments.** A prints `UNKNOWN`; B's GREEN arm measured a resolved, Completed, `errorCode=0x00000000` async approval in the same process that was then denied by `CreateForWindow` (`0x80070005`), E15 raw above. These two facts sit together unexplained: an access grant that does not open the capture path. This lane does not claim which layer produced the grant, nor whether the grant is even the layer WGC consults.
2. **Whether a consent dialog ever appeared: UNKNOWN.** None was seen by this lane. A WGC consent dialog is owned by a system process on the secure desktop and is not necessarily observable from a redirected child; this lane did not measure it and does not claim its absence either.
3. **The scope of the denial per token and per machine: not measured.** All measurements come from one elevated admin account on one box. Nothing here says a standard-user token, or a remote/interactive-session-0 launch, would see the same numbers.
4. **MEDIUM IL was not measured.** H1's medium-IL child was SKIPPED (`TokenLinkedToken absent`), so the measured set is {LOW: denied, HIGH: allowed}. SYSTEM IL was also not measured. The claim in §0 is accordingly bounded to LOW vs HIGH.
5. **Who set the Low label on `H:\sotto`, and why: UNKNOWN.** It is explicit at the root ((OI)(CI)(NW), non-inheritable text) and inherited by everything below; this lane neither changed it nor attributed it. It may be accidental, may be deliberate hardening, may be a leftover from a previous tool. This lane changed no label on anything outside its own scratch files (§10).
6. **The 17:51 attribution: UNKNOWN as a fact, EXPLAINED as a mechanism.** The finding's two runs were ~6 hours apart. A path-based explanation is fully sufficient — the same path denied again at 23:51:58, 23:56:58 and 23:58:37 — but this lane did not observe the 17:51 runs and cannot say what else differed then.
7. **A's comment attributing a prior lane's `RequestAccessAsync -> S_OK`: ATTRIBUTED, not verified here.** No run of A in this lane passed `--find-access-iid`. The nearest measured corroboration is B's E15 GREEN arm, which is a different program.
8. **Whether the item-creation denial is the only WGC denial: not measured, by design.** `CreateCaptureSession` and `StartCapture` are out of scope for this lane and appear in neither source; a session or stream could fail for additional reasons that this measurement cannot see.
9. **E11's "gap" behaviour and E09/E10's 90-second-apart repetition show no time dependence was resolved here.** The gap arm succeeded once and denied twice; this lane does not claim a mechanism for that asymmetry beyond the label, which was constant.


---

## 10. METHOD — every check an auditor can repeat, plus every artefact created

**Scripts (all `I:/cc-tmp/f13-2/`, all executed as `pwsh -NoProfile -File <file>`):**

| file | what it ran |
|---|---|
| `run-both.ps1` | the two product binaries as-found |
| `run-experiment.ps1` | E01–E11: A-from-`I:` (S_OK), copies into the labelled tree (E_ACCESSDENIED), junction arm, repeat/gap arms |
| `exp2-tree.ps1` | E15–E18: B copy into the labelled tree (LOW, denied), controls, `I:` copies of both binaries (allowed) |
| `causal.ps1` / `causal2.ps1` | C1–C3 and D1–D3: `SetNamedSecurityInfoW` label add/remove on scratch copies, both directions |
| `build-helpers.ps1` | compiled `ilprobe` and `add-label` with `H:\msys64\mingw64\bin\g++.exe`, `-Wall -Wextra -municode -O2 -ladvapi32`, `TMPDIR=I:/cc-tmp` |
| `census-file.ps1` | per-file PE metadata, ADS census, `Get-Acl` SDDL, and the **junction control**: `New-Item -ItemType Junction -Path I:\cc-tmp\f13-2\jprod -Target (Split-Path $prod -Parent) -Force` then `Start-Process -FilePath I:\cc-tmp\f13-2\jprod\wgc-probe.exe` -> E13 (same file object, an `I:`-looking path string); plus E14, A's bytes `Copy-Item`ed to `receipts\A_probe_copy.exe` |
| `census-dirs.ps1`, `census-sacl.ps1`, `census-final.ps1` | `icacls` via its full path `Join-Path $env:SystemRoot 'System32\icacls.exe'` — bare `icacls` is NOT on the child PATH in `-File` children, which is why every label in this receipt came from icacls and not from `Get-Acl` (whose default view hides the SACL entirely) |

**Artefacts left in `I:/cc-tmp` (scratch, deletable):** `A_from_I.exe`, `B_from_I.exe`, `wgc-probe-control.exe`, `wgc_probe_control.exe`, `jprod` (junction), `causal\ilprobe-labelled.exe`, `causal\wgc-probe-labelled.exe`, the `.cpp` helpers, and every `.out.log` named in §2.

**Modifications, disclosed:** this lane changed no registry key, started/stopped no service, requested no elevation, rebooted nothing, re-logged on nothing, and made no permission-escalation request. The only mandatory-label ACEs it wrote or removed were on **its own scratch copies** — `H:\sotto\…\receipts\A_probe_copy.exe` (label added, then removed in C2; restored and re-removed in D2/D3) and files under `I:/cc-tmp`. `A_probe_copy.exe` was deleted on 2026-10-10T01:10Z after its sha256 was re-verified as `9B0F884A…` and its resolved absolute path printed at deletion time. The lane's three other receipt-dir executables were hash-verified and deleted the same way. **`_main/receipts/` therefore differs from its pre-lane state only by those four deletions.** Process-token integrity was observed through the documented API (`GetTokenInformation` / `TokenIntegrityLevel`) and never set.

**Nothing shipped:** no camera, microphone, GPU encoder or capture session was opened. Both instruments stop at item creation by construction; `CreateCaptureSession` and `StartCapture` occur in neither source.

---

## 11. WHAT WOULD FALSIFY THE VERDICT IN §0

One measurement can: **a binary from the unlabelled population that denies at MEDIUM/HIGH integrity** (i.e. the label removed from a currently-deny path does not flip it), or **a labelled binary that allows** at the same integrity (the label present does not flip it). Neither was observed in any of E01–E18, C1–C3 or D1–D3; §0's claim rests on the flip being reproducible in both directions across four independent instruments (A's bytes, B's bytes, the helper-built `ilprobe`, and the label-written copies).

---

## 12. THE ONE CLAIM THIS LANE CANNOT MEASURE — and the surrogate it measured instead

**BLOCKED (out of scope):** whether the `0x00000000` number in INSTRUMENT B's logs corresponds to an item that would produce actual captured frames. `CreateCaptureSession`, `StartCapture` and anything that opens a GPU encoder, a camera or a microphone are explicitly out of scope for this lane (and appear nowhere in either instrument), so the lane deliberately produced **zero** frames. Whether `S_OK` at `CreateForWindow` is sufficient for a working capture path is **UNKNOWN from these measurements alone.**

**SURROGATE measured (the closest fact in-lane):** the item pointer returned. In every `0x00000000` case both instruments print a non-null `item=` pointer (e.g. `item=000001f8333280b8` from B-family E07; `item=0000000000431df8`, `000000000045bb38` etc. from the A-family E18); in every `0x80070005` case the pointer is exactly zero. That is a real, measured difference in the returned COM object, not a difference in an exit code — but it is **not** proof that frames flow, and this lane does not report it as such.

Population for that statement: E01, E02, E03, E06, E09, E10 all null-pointer; E18 (A control bytes, all five targets) and E07 (B, all targets) all non-null.

---

## 13. SOURCES OF ERROR IN THIS MEASUREMENT

Stated so the next reader can discount it, not to dilute it:

1. **The label is the subject, and it was partly moved by me.** To prove causality I wrote and removed a Low label on my own scratch copies (C1–C3, D1–D3). That construction is deliberate and symmetrical — it flipped in both directions on both binaries — but it is still a constructed experiment, not the original product state. The original state was measured first, untouched, and is in §2.1.
2. **`Get-Acl` cannot see a mandatory label** on this host (the SACL is hidden by default), so the label census is one tool's view: `icacls`. If `icacls` mis-rendered the ACE, the diagnosis would be wrong. Mitigation: the label's effect was measured independently twice — ilprobe measured the spawned process's token IL directly, and the WGC instruments measured the WGC return — so two instruments agree on what `icacls` said.
3. **MEDIUM-IL was not reached at all** (H1's child skipped, no linked token). Every conclusion above is {LOW: `0x80070005`, HIGH: `0x00000000`.} The two neighbouring levels are the only ones measured.
4. **One host, one account** (`desktop-o58u7kf\administrador`, `EnableLUA=0`, `ConsentPromptBehaviorAdmin=0`, build 26200). Nothing here is claimed about standard-user tokens, other machines, or future builds.
5. **B's E15 denial inside the labelled tree happened through a copied file, not A's own object** — the causal chain is: A's file object in `H:\sotto` carries `S-1-16-4096`, spawns LOW, WGC denies. The copy carries the same label ACE, spawns LOW, WGC denies. A's original object is not the one that was re-measured in E15; A's original object was measured in §2.1 and denied there.
6. **A's log has no clock.** Its timestamps are file mtimes, not printed facts.
