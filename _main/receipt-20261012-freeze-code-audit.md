# Receipt - the "travada a cada alguns segundos": root cause, and the fix that is ALREADY in the worker

Owner, verbatim: *"alguma coisa do sotto, faz meu pc dar uma travada muito forte a cada
alguns segundos. entenda o q é e arruam pra sempre. faz full hunt desse bug, trace,
audit com fix, etc. usa subagents enquanto tu continua teu trabalho"*

Measured 2026-10-12 on the owner box (America/Sao_Pao_Paulo). Read-only throughout:
nothing under `worker/` or `app/` was written, and no app, shell, worker or WebView2
process was launched. Every claim below names its instrument.

## 0. THE HEADLINE - the fix is already in the worker, and it is verified

**A concurrent lane landed the cure while this audit was running.** The worker moved
under this audit's feet twice:

| when | bytes | sha256 |
|---|---|---|
| audit start | 320 508 | `6ad267ebcd1cb6644c8fc11788dec4575faef87e1bcb52a647318353ff8cf5df` |
| **now (pinned)** | **325 485** | **`d06bb73019d7dfd38f887b53a3ad1dcabed6bcf24c36157115b8ff60736b9cd6`** |

The current bytes already contain the exact policy this audit derived independently:
a pure classifier `tap_stall_reason()` that separates a BROKEN CLIENT from an IDLE
ENDPOINT, and a run loop that WAITS on the latter instead of re-opening the shared
audio endpoint. So this receipt does **not** re-deliver that patch. It delivers
(a) the root-cause proof, (b) the verification of what is shipped, and (c) the
**one remaining gap**, with exact text.

## 1. PINS (re-measured at the end of the audit, instrument: node over the bytes)

| file | bytes | sha256 | mtime | lines |
|---|---|---|---|---|
| `worker/sotto_worker.py` | **325 485** | **`d06bb73019d7dfd38f887b53a3ad1dcabed6bcf24c36157115b8ff60736b9cd6`** | 2026-10-12T16:50:51.654Z | 6 160 CRLF / **0 bare LF** |
| `worker/wasapi_loopback.py` | 52 369 | `ed81a8b58ad80ae8b7d5e1ed3f7af02a2d9e111357bb325f4dbef836e584f4d9` | 2026-10-11T23:31:37.434Z | 1 162 bare LF / 0 CRLF |
| `app/webview/sotto_webview.py` | 460 312 | `1153ba94d42eae90f50637ebb29c1b6c7fa3f8a41fab39f84ce107209f6812e8` | 2026-10-12T08:33:27.608Z | 9 066 |

The CRLF property of the worker HOLDS (0 bare LF). `wasapi_loopback.py` is bare LF.
Both were re-measured twice, ~1 h apart, identical.

## 2. ROOT CAUSE - three independent sources, one conclusion

### 2.1 SOURCE 1: the worker's own stderr, captured by the shell

`_main/webview-run.log` **L93666** - the only `TAP_STALLED` line in 103 648 lines of
that log, verbatim:

```
TAP_STALLED device='WASAPI loopback: VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)'
  stalled_s=60.0 blocks=0 captions=608 reopens=32
  pump_exited=False pump_hr=0 pump_where=''
  silent_packets=0 gap_packets=0 disco_packets=0
```

Read it carefully, because it is the whole bug in one line:

- `pump_exited=False`, `pump_hr=0`, `pump_where=''` - **the pump thread was ALIVE**.
  The only two writers of `pump_exited` are the HRESULT breaks at
  `worker/wasapi_loopback.py:978` (`GetNextPacketSize`) and `:992` (`GetBuffer`).
  Neither fired.
- `silent_packets=0` - not one packet was even flagged SILENT. The endpoint was not
  "rendering silence"; it was rendering **nothing at all**.
- `blocks=0` - the tap had delivered **zero** blocks on this candidate.
- `reopens=32` - and the worker had already re-opened it **32 times**.

So the watchdog was rotating a tap that was alive and reading zero packets, 33 times,
and each rotation is an `IAudioClient::Initialize(SHARED|LOOPBACK)` on an endpoint the
owner's other apps share.

### 2.2 SOURCE 2: the cadence in the live run

Instrument: grep over `_main/webview-run.log`, counting `STATUS_APPLIED
text="device-rotated (tap-stalled)"` between L101296 and L104104 (the live run,
pid 39388, spawned 12:34:46). **34 rotations.** Inter-rotation intervals, in seconds:

```
21 14 11 13 17 18 16 22 4.4 5.5 20 42 30 11 13 14 16 17 18 21 22 4.4 5.5 ...
```

The log carries no per-line timestamp, so the cadence is derived from the
`evidence_age_s` field of the interleaved `BRIDGE_SILENT_BENIGN` lines (measured
~1.10 s per log line over that window). The clusters at **4.4 s and 5.5 s** and the
chains of 11-22 s are the owner's *"travada muito forte a cada alguns segundos"*.

For scale, the same log holds **2 146** `reason=flat` rotations, **56**
`device-exhausted` and **444** `BRIDGE_RESTART` - the ladder is the second, slower
half of the same disease (see section 6).

### 2.3 SOURCE 3: the code, before the concurrent fix

`worker/sotto_worker.py` (320 508 B revision), the settled-tap watchdog:

```
5602|                        if device_blocks["value"] != stall_blocks:
5603|                            # Still delivering: this tap IS the run.
5604|                            stall_blocks = device_blocks["value"]
5605|                            stall_since = now
5606|                            stall_backoff = TAP_STALL_S      <-- THE RESET
5607|                        elif now - stall_since >= stall_backoff:
5608|                            # -- THE TAP STOPPED DELIVERING (added 2026-10-11) ---
```

Two defects, and they compound:

**D1 - a frozen block counter was read as a dead tap.** The 2026-10-11 cure chose
BLOCK ARRIVAL as the liveness signal, on the premise (its own comment, L5615-5616)
that *"a pumped but idle endpoint delivers SILENT blocks; a starved or dead one
delivers none"*. **That premise is false on this box.** Measured
(`docs/audit/blank-frames-root-cause.md:154`, `_main/_bfrc_all_endpoints.py`, all 6
active render endpoints): **only the default endpoint returns packets; the other 5
return `n=0`**. And `worker/wasapi_loopback.py:982-984` is

```
982|        if n.value == 0:
983|            time.sleep(period);      # period = 5 ms at the shipped 100 ms block
984|            continue
```

An idle endpoint therefore produces **no packets and no SILENT flag**, so
`device_blocks` freezes while the pump stays alive - indistinguishable from a dead
tap by every counter except `pump_exited`.

**D2 - the exponential backoff was erased by a single block.** L5606 assigned
`stall_backoff = TAP_STALL_S` (8 s) on **every** delivered block, so the growth to
16/32/60 s could never survive a tap that delivered anything. That is why the measured
cadence stayed at 4-22 s while `reopens` climbed to 32.

### 2.4 Why the tap stops - the distinction the owner asked for

The owner's question was: *why does the tap stop, and is the device silent or is the
tap dead?* They are different states with different cures:

| state | what the counters say | what is true | cure |
|---|---|---|---|
| **endpoint idle** | `pump_exited=False`, `silent_packets=0`, `blocks=0` | the pump is alive and polling; the endpoint renders nothing | **wait** - rotating cannot conjure audio into it |
| **tap dead (client broken)** | `pump_exited=True`, `pump_hr=0x88890004`, `pump_where="GetNextPacketSize"` | the WASAPI client broke on an HRESULT | **re-open now** |
| **engine stopped mid-stream** | `pump_exited=False`, `blocks>0` then frozen | it delivered, then stopped | **re-open** |

The discriminator is `pump_exited` - the ONLY affirmative dead-client signal. The
2026-10-11 comment's premise ("a pumped but idle endpoint delivers SILENT blocks")
is refuted by the live `TAP_STALLED` line above: `silent_packets=0`.

## 3. WHAT IS SHIPPED NOW (the concurrent fix), with its lines

All on the pinned 325 485 B revision:

```
252|TAP_IDLE_MAX_S = 300.0   # a live pump plus zero packets for this long: re-arm ONCE
253|TAP_REOPEN_MAX = 20      # never open more than this many clients in one run
254|TAP_REOPEN_MIN_S = 5.0   # and never faster than this, whatever the state says
255|def tap_stall_reason(pump_exited, idle_s, reopens):
271|    if pump_exited:
272|        return "pump-dead"
273|    if idle_s >= TAP_IDLE_MAX_S and reopens < TAP_REOPEN_MAX:
274|        return "idle-rearm"
275|    return "endpoint-idle"
```

and in the run loop:

```
5640|                    if settled:
5643|                        if device_blocks["value"] != stall_blocks:
5647|                            stall_backoff = TAP_STALL_S
5648|                        elif now - stall_since >= stall_backoff:
5671|                            client_dead = bool(getattr(inner, "pump_exited", False))
5672|                            stall_reason = tap_stall_reason(client_dead, stalled_s, stall_reopens)
5674|                            if stall_reason == "endpoint-idle":
5679|                                if idle_s >= TAP_IDLE_MAX_S + TAP_STALL_MAX_S and not idle_logged:
5680|                                    err(f"TAP_IDLE device={dev['name']!r} idle_s={idle_s:.0f} "
5683|                                    idle_logged = True
5684|                                time.sleep(0.1)
5685|                                continue                      # <-- WAIT, do not re-open
5686|                            err(f"TAP_STALLED device={dev['name']!r} stalled_s={stalled_s:.1f} "
5687|                                f"reason={stall_reason} "
5709|                            emit(type="status", state="device-rotated", reason=stall_reason,
5733|                            stall_since = time.time()
5736|                            stall_backoff = max(TAP_REOPEN_MIN_S,
5737|                                TAP_STALL_S
5738|                                if stall_reopens < TAP_STALL_SAME_DEVICE_TRIES
5739|                                else min(stall_backoff * 2.0, TAP_STALL_MAX_S))
```

This satisfies all three of the owner's requirements:

- **(a) it does not rotate a merely-silent device** - `endpoint-idle` waits;
- **(b) there is a real backoff** - `TAP_REOPEN_MIN_S` floor plus the doubling to
  `TAP_STALL_MAX_S`, and the idle bound of 300 s before the first re-arm;
- **(c) the real dead-tap case is not lost** - `pump-dead` re-opens immediately, and
  `idle-rearm` still re-scans once after a long idle (the audio may have MOVED).

## 4. VERIFICATION - two gates, both GREEN, both able to say NO

### 4.1 `_main/tap-stall-policy-oracle.py` (the concurrent lane's gate)

    python _main/tap-stall-policy-oracle.py
    -> PASS -- an idle endpoint costs no re-open; a broken client still earns one
       shipped failures : 0
       control failures  : 17 (must be > 0)

It tests the pure policy table against 10 inputs, then two CONTROL mutants
("always re-open" and "always re-arm") which must FAIL 17 arms between them - so the
gate is not vacuous. ARM 2 additionally checks the run loop CALLS the policy exactly
once, that no inline re-decision exists, and that the three constants and the
re-open floor are honoured.

### 4.2 `_main/tap-idle-liveness-oracle.py` (this audit's gate - the integration arm)

    python _main/tap-idle-liveness-oracle.py
    -> VERDICT: GREEN -- every arm as expected

The policy oracle tests the function; this one **executes the run-loop branch
extracted from the live file by indentation**, with a stubbed tap, so it proves the
integrated behaviour rather than the table:

| arm | input | expected | measured |
|---|---|---|---|
| 1 | idle, blocks=0, pump alive, 60 s, 0 reopens | NO rotation, NO close | PASS `emit=[] closed=0 err=0` |
| 2 | pump dead, blocks=0 | rotates, `reason=pump-dead` | PASS |
| 3 | idle 400 s, 0 reopens | rotates once, `reason=idle-rearm` | PASS |
| 4 | idle 400 s, 20 reopens (capped) | waits | PASS |
| 5 | blocks still arriving | nothing | PASS |
| 6 | **negative control**: the call replaced by the unconditional re-open | DOES rotate | PASS |

Arm 6 is the one that makes the gate honest: with the pre-patch policy restored, the
same input rotates. Without that arm a green here would prove nothing.

## 5. THE ONE REMAINING GAP - exact text

### 5.1 The ladder still rotates with no backoff of its own

`worker/sotto_worker.py:5842` is still a bare `rotations += 1` with nothing after
it. A `flat` rotation is therefore IMMEDIATE: close one tap, open the next, serve out
its `tap_window` (6 s), rotate again. With nothing routed into any candidate - the
measured normal on this box - the whole ladder is burned at one endpoint per window
and the run dies `device-exhausted`, which the shell then restarts on its own
2 s/8 s/16 s/30 s backoff (`app/webview/sotto_webview.py:8147`). Measured in one
owner run: **2 146** `reason=flat` rotations, **56** `device-exhausted`, **444**
`BRIDGE_RESTART`.

This is the SECOND half of the freeze, and it is untouched. Exact patch:

**site** - `worker/sotto_worker.py:5842`, the line `            rotations += 1`
(the one at the end of the `flat` emit, NOT the one at `:5583` which belongs to the
`open-failed` path).

**before**

```
            rotations += 1
```

**after**

```
            rotations += 1
            # -- THE LADDER'S OWN BACKOFF (added 2026-10-12) -------------------------
            # A `flat` rotation used to be IMMEDIATE: close one tap, open the next,
            # serve out its window, rotate again. With nothing routed into any
            # candidate -- the measured normal on this box, where every loopback reads
            # digital silence -- the whole ladder is burned at one endpoint per
            # tap_window and the run dies `device-exhausted`, which the shell then
            # restarts on its own 2 s/8 s/16 s/30 s backoff
            # (app/webview/sotto_webview.py:8147). Measured in one owner run: 2 146
            # `reason=flat` rotations, 56 `device-exhausted`, 444 BRIDGE_RESTART.
            # Each rotation is an IAudioClient::Initialize on a new endpoint, so the
            # ladder is the OTHER half of the owner's freeze. 1 s, doubling to 8 s per
            # rotation, so a machine with nothing to capture stops paying for it
            # every few seconds. `stop.wait` (never `time.sleep`) so `stop` and
            # `--max-seconds` still answer at once.
            stop.wait(float(min(8.0, 2.0 ** (rotations - 1))))
```

**Risk, stated plainly.** This changes the timing contract of the ladder, so any
oracle that measures an all-flat run end-to-end will see up to +8 s per rotation.
The two instruments that watch this area are measurement tools, not gates, and
neither asserts a cadence: `_main/rotation-burst-monitor.py` (samples a 20 ms stall
detector and stamps rotation lines) and `_main/tap-stall-rate-probe.py` (counts
`tap-stall` / `ladder-flat` / `benign` / `execjs` / `caption` / `restart` per 2 s
slice and prints per-minute rates). Re-run both after applying. The gates that DO
pin ladder behaviour - `_main/flat-endpoint-oracle.py`,
`_main/device-silence-oracle.py`, `_main/device-ladder-rescan-oracle.py` - should
be re-run, and are expected to stay green because the backoff only delays a
rotation, it does not change which candidate is chosen or what is emitted.

### 5.2 Two smaller observations, no patch offered

1. **`stall_backoff = TAP_STALL_S` at `:5647` still resets the backoff on every
   delivered block.** Benign today - the `endpoint-idle` branch never re-arms, so the
   growth is irrelevant while the endpoint is idle - but it means the exponential
   ladder can never be armed for a tap that delivers anything. If a future change
   makes `endpoint-idle` re-arm, D2 comes back. Deleting `:5647` is the one-line
   cure; it is NOT applied here because it is not needed for the measured bug.
2. **The `endpoint-idle` branch spins at 10 Hz** (`time.sleep(0.1)` at `:5684`). It
   emits nothing and closes nothing, so it is cheap, but it is a spin. A
   `stop.wait(...)` on the remaining idle time would be the tidy form.

## 6. A BROKEN GATE - exact fix, not applied

`_main/tap-stall-watchdog-oracle.py` - the gate for the 2026-10-11 frozen-tap cure -
**crashes on the current worker and never reaches a verdict**:

    File "<extracted:arm4b>", line 47, in run
    NameError: name 'tap_stall_reason' is not defined

It extracts the settled branch by indentation and `exec`s it with a fixed PARAMS
list. The branch now references three names that list does not provide:
`tap_stall_reason` (`:5672`), `tap_source` (`:5718`) and `target_pid` (`:5705`).
It was already broken before this revision on `tap_source`/`target_pid` (it exited 1
with a traceback then too), so the 2026-10-11 cure has had **no working gate**
since the worker grew past it.

Exact fix - in `_main/tap-stall-watchdog-oracle.py`, add three names to PARAMS:

```
PARAMS = ("settled, device_blocks, now, err, emit, close_tap, LoopbackTap, tap_holder, "
          "block_ms, on_block, device_candidates, audio_cfg, wanted, candidates, "
          "attempt_no, counters, device_peak, time, tap_stall_reason, "
          "TAP_STALL_S, TAP_STALL_SAME_DEVICE_TRIES, TAP_STALL_MAX_S, "
          "seed_tap, seed_dev, seed_stall_blocks, seed_stall_since, "
          "seed_stall_backoff, seed_stall_reopens")
```

and two lines to INIT:

```
        "    tap_source = lambda d: 'device:' + str(d.get('name'))\n"
        "    target_pid = None\n")
```

Note that its ARM 5 (negative control) deletes from the `elif` line to the end of
its suite, so any future edit that moves the `elif` line's text will break that arm
too - the anchor is `l.strip().startswith("elif now - stall_since >= stall_backoff:")`.

## 7. WHAT WAS NOT MEASURED

- **No live run.** The owner's order for this emergency is that only the Lead
  launches the app/worker, and the app is in use. So the cure is verified by two
  extracted-branch gates, not by a live freeze reproduction. The pre-fix behaviour
  IS measured - it is in the owner's own log at L93666 and in the 34-rotation
  cadence - but the post-fix behaviour is not.
- **The UI-thread stall is unattributed.** 106 `exec_js TIMEOUT` lines (66 at 5 s,
  40 at 10 s) are in the log. The shell's own audit
  (`_main/_bridge-audit-report-20261012.md`) proves those timeouts are a SYMPTOM - the
  wait blocks the caller, not the UI thread - and that a blocking caption `emit` can
  stall a caption for up to 10 s. What blocks the UI thread is NOT DETERMINED, and
  this audit did not test whether the rotation churn contributes to it.
- **`BRIDGE_SILENT_BENIGN because=` is a stale snapshot** (the shell re-emits the
  last `reason=flat` with a climbing `evidence_age_s`, measured to 3092.1 s, while the
  live statuses all say `tap-stalled`). The panel and the log were describing
  DIFFERENT rotations. That is a shell-side defect, out of this audit's scope.

## 8. FILES

| file | what |
|---|---|
| `_main/tap-idle-liveness-oracle.py` | new. Integration gate: executes the extracted run-loop branch. 6 arms + negative control. GREEN. |
| `_main/_tap-idle-patch.py` | new. The patch this audit originally derived, as exact before/after text plus a COPY-ONLY applier (refuses `--out` under `worker/`). **Now obsolete** - the concurrent lane shipped the same policy. Kept as the record of the independent derivation. |
| `_main/tap-stall-policy-oracle.py` | the concurrent lane's gate for the shipped policy. GREEN, 17 control failures. |
| `_main/tap-stall-watchdog-oracle.py` | **broken** (section 6). Fix given as text. |
| `_main/_bridge-audit-report-20261012.md` | the shell-side audit, delivered by the second subagent. |

Nothing under `worker/` or `app/` was written. No process was launched.

