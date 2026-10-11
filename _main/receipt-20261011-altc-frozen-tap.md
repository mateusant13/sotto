# Receipt - Alt+C "nao ta funcionando": the frozen tap, and its cure

Owner, verbatim: *"alt c mostre as transcricoes... alt c nao ta funcionando. faz funcionar. e continua"*
Measured 2026-10-11 on the owner box (America/Sao_Paulo). Every claim below carries its instrument.

## 1. The report is THREE defects, and only one of them is Alt+C

| # | claim | instrument | result |
|---|---|---|---|
| D1 | NO Sotto process was running at 13:43:53, so Alt+C could not answer | `Get-CimInstance Win32_Process` from a .ps1 file, filtered on the artifact `sotto_webview\.py` / `sotto_worker\.py` | EMPTY process list; `_main/panel-state.json` 4.5 h stale with `namedState="no-worker"` |
| D1-fix | relaunched exactly as the Run value does (`pythonw.exe ... --log ...`) | the log since the relaunch | `SINGLE_INSTANCE already_running=false`, `HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true thread=3340`, `BRIDGE_SPAWNED pid=14636`, `WORKER_AUTOSTART=started reason=default`, `CODE_STATE shell_disk=056fac42dbe74190 shell_loaded=056fac42dbe74190 shell_stale=False` |
| D2 | Alt+C itself WORKS | a real `WM_HOTKEY` posted to thread 3340 (`I:/cc-tmp/post-hotkey.py`), plus the app log | `PANEL_PLACED mode=strip docked=bottom-strip work=1920x1032@(0,0) window=1040x150@(440,870) margin=12` then `PANEL_SHOWN reason=hotkey mode=strip visible=true`; 4x PANEL_SHOWN + 4x PANEL_HIDDEN in one log window; one `HOTKEY_DOUBLE dt_ms=1359 window_ms=1500 mode=side action=switch reason=was-strip` |
| D3 | THE REAL BUG: the worker tap FREEZES and never recovers | the worker `stderr_tail` of the killed process, plus per-endpoint meters | last `WORKER_STATS tag=tick` frozen at `blocks=59 block_samples=283200 nonzero_blocks=56 peak=0.925995 ... captions=6`; 68x `BRIDGE_SILENT_BENIGN ms=30000 state=no-audio because="device-rotated reason=flat peak=0.925995"`; ~34 min deaf while the default endpoint carried peak 0.1444 |

Cure path proven BEFORE the patch: killing only the worker (`I:/cc-tmp/kill-worker.ps1`, artifact filter) while 90 s of speech played
made the shell respawn it and the fresh worker captured instantly - `BRIDGE_CAPTION_SENT text="nao posso deixar que demora muito pra matar essas pures tambem"`,
`panel-state.json` liveCount=3 with a provisional cursor. So the model, the decode and the panel were all healthy; the TAP was the dead part.

## 2. Root cause, read in the code (two halves)

1. `worker/sotto_worker.py` capture loop, the settled branch: `if settled: time.sleep(0.1); continue` - once a candidate had produced a caption it was
   the run FOR EVER, and the loop never asked again whether that tap was still delivering. `device_blocks` froze at 59 and nothing noticed.
2. `worker/wasapi_loopback.py::_pump`: BOTH exits on a non-zero HRESULT (`GetNextPacketSize`, `GetBuffer`) were a bare `break` - no exception, no
   callback, no flag. The pump died silently and `on_block` was never called again.

## 3. The cure (shipped)

| file | before | after |
|---|---|---|
| `worker/sotto_worker.py` | 238 427 B / sha256 `DB12C89B8CE9A547930A3DA04A2F9F372315CFFB7D8C96C45593C121F33F964F` / 4 539 CRLF / 0 bare LF | 244 046 B / sha256 `503F095DF893F358...` / 4 619 CRLF / **0 bare LF** / 4 620 lines |
| `worker/wasapi_loopback.py` | 50 461 B / 1 131 lines | 51 215 B / sha256 `09C65E941D757384...` / 0 CRLF / 1 146 bare LF / 1 147 lines |

New: `TAP_STALL_S = 8.0`, `TAP_STALL_MAX_S = 60.0`, `TAP_STALL_SAME_DEVICE_TRIES = 2` (after `TAP_SILENT_BLOCKS = 20`); the per-candidate reset seeds
`stall_blocks/stall_since/stall_backoff/stall_reopens`; the settled branch now watches BLOCK ARRIVAL - 8 s without a new block logs `TAP_STALLED` with the
tap own diagnosis (`pump_exited`, `pump_exit_hr`, `pump_exit_where`, `silent_packets`, `position_gap_packets`), then RE-OPENS IN PLACE
(`close_tap` + a fresh `LoopbackTap` + `tap.stream.start()`, `tap_holder["gen"]` bumped on both sides), emits `device-rotated reason=tap-stalled` and
`capture-started ... reopened=True`, and never exits. The first two stalls re-open the SAME endpoint; after that a fresh `device_candidates()` endpoint that
is not the current one is taken - except when the device was explicit (`rung == "c"`), which is never substituted silently. Backoff doubles to 60 s while
starved and resets on any delivered block. `_pump` now records both break sites instead of swallowing them.

**Why BLOCK ARRIVAL and not peak:** a pumped but idle endpoint keeps delivering SILENT blocks (the tap own `silent_packets` counter proves it); a starved or
dead one delivers none. Peak cannot tell those apart, and the old message quoted the run HIGH-WATER mark (`peak=0.925995`) while the window was silent.

## 4. Instrument: `_main/tap-stall-watchdog-oracle.py`

12 733 B, LF. `python _main/tap-stall-watchdog-oracle.py` -> `VERDICT: GREEN -- every arm as expected`, rc=0.
The block under test is EXTRACTED FROM THE LIVE WORKER FILE by indentation (lines 4175-4244, 70 lines), so a stale copy cannot pass.

| arm | what it measures | result |
|---|---|---|
| ARM 1 | the REAL `_pump` executed with a stubbed COM layer (`_vtbl` indices 5 and 3 discovered from the source), `GetNextPacketSize` failing | `pump_exited=True hr=0x88890004 where=GetNextPacketSize delivered=0` |
| ARM 2 | the same for `GetBuffer` | `pump_exited=True hr=0x88890004 where=GetBuffer delivered=0` |
| ARM 3 | NO FALSE POSITIVE: blocks still arriving | no emit, no close |
| ARM 4 | blocks frozen 20 s past the bound | `device-rotated/tap-stalled` + `capture-started reopened=True`, closed=1, same endpoint |
| ARM 4b | retries spent (2) | the fresh enumeration OTHER endpoint is taken (`VoiceMeeter Input`) |
| ARM 5 | NEGATIVE CONTROL: the watchdog branch deleted (60 lines) on ARM 4 inputs | nothing happens - the gate can say NO |
| ARM 6 | PREMISE: the counter is the TAP callback (`on_block`, line 3542), and the watchdog sits inside `if settled:` (4175 -> 4178, indent 24 > 20) | PASS |

## 5. Live evidence after the cure

Worker restarted onto the patched bytes (kill by artifact filter; the shell respawned it) with speech playing, then observed for 142 s:
**47 `BRIDGE_CAPTION_SENT`, `spawns=1`, `exits/deaths=1` - both of them MY kill - and `tap-stalled=0`.**
The worker transcribed the owner real desktop audio continuously with no restart and no false stall, and the panel painted it.

## 6. NOT PROVEN (stated, not glossed)

- The watchdog has NOT yet fired on a GENUINELY starved endpoint in a live run: the owner desktop never went silent during the observation window
  (the transcript is his own game audio), and starving the tap on demand would mean disturbing his live audio. The firing path is proven by executing the
  real extracted branch under a controlled frozen counter (ARM 4/4b) with a negative control (ARM 5), not by a live starvation event.
- The misleading text defect is NOT fixed: the shell replays the stale worker status string (`state=no-audio because="device-rotated reason=flat"`) every 30 s.
  A quieter, truer sentence is a separate change.
- The reason the app was not running at 13:43:53 is UNATTRIBUTED: there is no `SHELL_EXIT` line, and a probe killing by artifact filter is the prime suspect.
