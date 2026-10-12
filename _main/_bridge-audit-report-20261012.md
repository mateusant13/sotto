# Sotto shell-side worker-bridge audit (2026-10-12, READ-ONLY)

Nothing under worker/ or app/ was written or edited. No app, shell, worker or
WebView2 process was started. Every claim is from reading files or grepping the
existing _main/webview-run.log (10 621 277 B) read-only.

## Re-measured pins

  app/webview/sotto_webview.py   460312 B   sha256 1153ba94d42eae90f50637ebb29c1b6c7fa3f8a41fab39f84ce107209f6812e8   9066 lines
  worker/sotto_worker.py (read-only, Q5 only)  320508 B  sha256 6ad267ebcd1cb6644c8fc11788dec4575faef87e1bcb52a647318353ff8cf5df  6090 lines

mtime of the shell file: 2026-10-12T08:33:27.608Z. Measured twice, ~15 min apart,
identical both times.

Correction to the shell's own comment: sotto_webview.py:7760-7761 cites the worker's
meter emit as sotto_worker.py:3591. That line number is STALE - the live emit is
worker/sotto_worker.py:4871. AGENTS.md rule 2 applies to the shell's own comments too.

======================================================================
Q1. BRIDGE_SILENT_BENIGN - is because= a stale snapshot or a live reading?
======================================================================

VERDICT: because= is a STALE SNAPSHOT of the last no-audio-evidence status the
bridge consumed, re-emitted VERBATIM on every 30 s tick. It is NOT a live reading.

Emission site - app/webview/sotto_webview.py:8052-8055 (inside WorkerBridge._on_silence):

    8052:             self.log(f'BRIDGE_SILENT_BENIGN ms={self.silence_ms} '
    8053:                      f'pid={self.child.pid} state={NO_AUDIO_STATE} '
    8054:                      f'because={json.dumps(self.no_audio_evidence)}'
    8055:                      f' evidence_age_s={age_s} restarts={self.restarts}')

- ms=30000 is the watchdog PERIOD, not a measurement. Constant at :422
  "WORKER_SILENCE_MS = 30000"; ctor default at :7301 "silence_ms=WORKER_SILENCE_MS";
  stored at :7326; armed as a timer at :7951
  "timer = threading.Timer(self.silence_ms / 1000.0, self._on_silence)".
  _on_silence re-arms itself at :8080 "self._arm_silence()", so it fires every
  30 s for the life of the process. (The log also carries ms=15000 - 754 lines -
  from probes that build a bridge with a smaller silence_ms; the SHIPPED default
  is 30000.)
- state=no-audio is a LITERAL CONSTANT, not a reading of the worker. :394
  "NO_AUDIO_STATE = 'no-audio'". The bridge's own self.state is set to it at :7517
  "self.state = state" via _bridge_status (:7516-7518). The log prints the constant.
- because= is self.no_audio_evidence, a CACHED STRING set only in the status
  consumer _consume, :7873-7877:

    7873:             evidence = self._no_audio_evidence(state, message)
    7874:             if evidence is not None:
    7875:                 self.no_audio = True
    7876:                 self.no_audio_evidence = evidence
    7877:                 self.no_audio_evidence_at = time.monotonic()

  _no_audio_evidence (:7993-8032) builds the string from ONE status line:

    8019:         if state == 'device-rotated':
    8020:             for str(message.get('reason') or '') == 'flat':
    8021:                 return (f'device-rotated reason=flat '
    8022:                         f'peak={message.get("peak")} '
    8023:                         f'floor={message.get("peak_floor")}')

  ...plus 'done verdict=<v>' (:8025-8028) and 'state=<s>' for WORKER_NO_AUDIO_STATES
  (:376-381, :8030-8031). It is overwritten ONLY when a NEW such status arrives,
  and reset to None on every respawn (_spawn :7593-7599) and on a manual revive
  (:5814-5815).
- evidence_age_s = time.monotonic() - self.no_audio_evidence_at (:8050-8051).
  It is the AGE OF THE SNAPSHOT, and it grows on every tick while because= does not
  move - that growth is the on-disk proof of staleness.
- restarts = self.restarts, the CUMULATIVE restart counter for the bridge's whole
  life. It is only ever INCREMENTED (:8148 "self.restarts += 1"), never reset -
  grep "self.restarts" = 6 hits: :7332 init, :7471 snapshot, :8055 log,
  :8147-8150 increment. So restarts=6 means 6 restarts since the shell started,
  NOT 6 within this quiet period.

LOG PROOF (instrument: grep over H:\sotto\_main\webview-run.log). 2896
BRIDGE_SILENT_BENIGN lines. For pid 39388 the SAME string

    because="device-rotated reason=flat peak=0.0 floor=0.002"

is re-emitted with evidence_age_s climbing 649 -> 3092.1 s (45 lines). Measured
window log:103256..104193 shows STATUS_APPLIED text="device-rotated (tap-stalled)"
(the LIVE reason) interleaved with BENIGN lines still carrying reason=flat. The
parent's measurement (36 consecutive 30 s ticks) is CONFIRMED by both the code
path and the log.

======================================================================
Q2. BRIDGE_RESTART reason=silent
======================================================================

Emission site - sotto_webview.py:8149-8150 (in _schedule_restart):

    8149:         self.log(f'BRIDGE_RESTART reason={reason} in_ms={delay} '
    8150:                  f'restart={self.restarts}')

Armed from exactly ONE place - the ANOMALOUS branch of the watchdog, :8082-8090:

    8085:         self.log(f'BRIDGE_SILENT ms={self.silence_ms} pid={self.child.pid}')
    8090:         self._kill_and_restart('silent')

i.e. the 30 s timer fired while self.no_audio is False - the tap was open (or had
declared itself) and the worker published NOTHING on stdout without ever saying what
the audio was. The BENIGN branch (no_audio True, :8037-8081) deliberately does NOT
restart - :8042-8045: "Killing it here is what produced 8 BRIDGE_SILENT and
spawns=10 in ONE live run ... The loop could not converge".

in_ms=1000 is the BACKOFF DELAY, :8147:
"delay = min(self.backoff_max, self.backoff_base * (2 ** self.restarts))" with
backoff_base=1000 / backoff_max=30000 (ctor defaults :7302). restarts=0 ->
in_ms=1000; the counter is then incremented, hence restart=1. The same call with
reason=exit comes from _wait :8133 "self._schedule_restart('exit')".

Log: 444 BRIDGE_RESTART lines, reasons {"exit":276,"silent":168}; the backoff
ladder is visible verbatim at log:2894-4551 (1000/2000/4000/8000/16000/30000/30000...).

NOT DETERMINED: nothing in this file decides WHY a given run goes anomalous vs
benign - that is the worker's own stdout, which I did not launch.

======================================================================
Q3. Every shell -> WebView2 UI-thread call with a timeout
======================================================================

ONE seam carries all of them - exec_js, sotto_webview.py:4581-4627:

    4581:     def exec_js(self, script, timeout=10.0):
    4608:             self.webview2.Invoke(Func[Object](
    4609:                 lambda: self.core.ExecuteScriptAsync(script).ContinueWith(
    4610:                     Action[Task[String]](_complete))))
    4613:             self._ui(_run)
    4618:         if not done.wait(timeout):
    4619:             warn(f'exec_js TIMEOUT after {timeout}s script={script[:90]!r}')
    4620:             return None

_ui (:4507-4544) is the UI-thread hop: :4519 "if form.InvokeRequired:" -> :4531
"form.BeginInvoke(Func[Type](run))" then :4538 "for not done.wait(10):" with
:4539 "warn('UI_THREAD_STALL begin-invoke not run in 10 s fn=' + ...)". If
InvokeRequired is False it runs fn() INLINE on the caller (:4544 "return fn()").

So: YES, every exec_js runs on the UI thread (the thread that owns the WebView2
control), and the wait is on the CALLER's thread, not the UI thread.

COMPLETE CALL-SITE CENSUS (grep "self.exec_js" = 16 hits, all listed):

  :4304  _on_loaded           BRIDGE_PROBE                        10.0 default  shell/main thread
  :4631  emit()               window.__sotto_emit(kind, json)     10.0 default  BLOCKING; captions (:5830), status (:4649)
  :4676  apply_panel_state    placeholder title/body/kind write    10.0 default  every worker status (pump thread)
  :4713  panel_state_snapshot PANEL_STATE_PROBE                   5.0 EXPLICIT  writer thread, every 2.0 s (PANEL_STATE_INTERVAL_S :235, wired :4836)
  :5005  reply_history        __sotto_history                    10.0 default  page request
  :5482  reply_info           __sotto_info                       10.0 default  page request
  :6186  reply_stats          __sotto_stats(id, payload)          10.0 default  panel 1000 ms poll (panel.js:1722 per :6178)
  :6385  refresh_strip_height getComputedStyle(--strip-height)  10.0 default  surface change
  :6458  set_panel_surface     window.SottoSurfaces.set            10.0 default  page _surface
  :6751  run_dump_dom         DUMP_DOM_PROBE                      10.0 default  --dump-dom; exits 3 on None (:6754)
  :6757  run_dump_dom         BRIDGE_PROBE                        10.0 default  --dump-dom
  :6799  PANEL_V2_PROBE       PANEL_V2_INJECT                    10.0 default  --probe-v2
  :6807  PANEL_V2_PROBE       PANEL_V2_READ_LIVE                 10.0 default  --probe-v2
  :6809  PANEL_V2_PROBE       PANEL_V2_READ_SEARCH               10.0 default  --probe-v2
  :6915  run_stats_probe      meter bars read                     10.0 default  --probe-stats

RETRY: NO. exec_js has no retry, no loop, no re-arm. Each caller fires once and
takes None (:4619-4620); the callers log and move on.

The FIRE-AND-FORGET twin is emit_async (:6246-6326), used for the stats/meter feed:
:6314 "queued = self._post(_run)", and _post does form.BeginInvoke and returns
immediately (:4577), so it has NO timeout and NO UI_THREAD_STALL warning.

COULD REPEATED 5 s/10 s TIMEOUTS CAUSE "travada muito forte a cada alguns segundos"?

WHAT THE CODE PROVES - the timeout is a SYMPTOM, not a cause. done.wait(timeout)
blocks the CALLER (pump thread / panel-state writer thread) and gives up; the UI
thread itself is never blocked by exec_js - it is merely too BUSY to service the
BeginInvoke. So repeated timeouts are positive evidence that the UI thread is
already stalled. Two second-order effects ARE in the code:

 (a) CAPTIONS. on_worker_caption -> emit -> exec_js(10.0) is BLOCKING
     (:4629-4632, called from :5829-5831). While the UI thread is stuck, the stdout
     PUMP thread - which carries every caption - sits in done.wait for up to 10 s per
     caption. That is a real, visible caption stall of up to 10 s at a time: the
     closest thing in this file to "travada a cada alguns segundos".
 (b) THE PANEL-STATE DUMP GOES STALE. PanelStateWriter._loop
     (app/webview/panel_state.py:147-149) is
     "while not self._stop.wait(self.interval_s): self.write(...)" - a 5 s blocking
     snapshot delays the next tick by 5 s, and staleAfterSeconds = max(2.0*3, 5) = 6.0
     (:170), so a 5 s timeout puts the dump over its own freshness limit.

MEASURED IN THE LOG: 106 exec_js TIMEOUT lines - 66 at 5.0 s (all the
PANEL_STATE_PROBE, script begins "const txt = (el) => (el && el.textContent ? el.textContent : '')")
and 40 at 10.0 s. The 10.0 s ones are exactly the blocking call sites:
__sotto_emit("caption", ...) x20, __sotto_stats("s146"/"s74"/"s79"/"s154"/"s155", ...) x6,
the apply_panel_state placeholder x2, SottoSurfaces.set x1, --strip-height x1.
Example burst log:92562-92565 shows 5.0 + 10.0 + 5.0 + 10.0 interleaved with
BRIDGE_CAPTION_SENT - the stall window is real and captions ARE arriving around it.

WHAT THE CODE DOES NOT PROVE (labelled explicitly): it does not identify WHAT
blocks the UI thread. The one mechanism this repo already removed is an unbounded
WinForms queue - emit_async holds at most ONE pending callable per channel
(:6277-6281 "if already: return"), a push that arrives with one queued REPLACES the
payload (:6294-6297 "POP AT RUN TIME"), and _post returns False when the form does
not exist so the slot is released (:6319-6326). The residual risk named in AGENTS.md
(43 stats pushes/s into the UI thread) is NOT measured - I launched nothing.

NOT DETERMINED: whether the UI-thread stall is the actual cause of the owner's
freeze; how long each stall lasts; and whether anything OUTSIDE this file (WebView2
itself, the panel's JS) blocks the UI thread. No window was opened, so no freeze was
reproduced or timed.

======================================================================
Q4. "device-rotated (tap-stalled)" and "Audio tap silent - nothing to transcribe"
======================================================================

The (tap-stalled) suffix is BUILT IN THE SHELL, by _readable,
sotto_webview.py:7920-7928:

    7920:     def _readable(self, state, reason):
    7928:         return f'{state} ({reason})' if reason else state

called at :7893-7894
"text = worker_status_text(state, message, self._readable(state, reason))".
worker_status_text (:523-565) returns readable UNCHANGED for a state that is not
in WORKER_ERROR_STATES (:544-545), and device-rotated is not one
(WORKER_ERROR_STATES :336-340 = error/device-exhausted/silent-device).
So the footer text IS the _readable output: state + " (" + reason + ")".

The reason VALUE comes from the WORKER - worker/sotto_worker.py:5641-5644:

    5641:                             emit(type="status", state="device-rotated", reason="tap-stalled",
    5642:                                  to=target["name"], device=dev["name"],

The panel-text mapping chain: shell bridge :7886-7915 -> _status (:7495) ->
on_status callback -> SottoShell.on_worker_status (:6608-6609) ->
apply_panel_state (:4655) -> send_status + the exec_js placeholder write
(:4674-4689). The page acks it back and the shell logs it: _status_applied
:3477-3479 "log(f'STATUS_APPLIED text={json.dumps(text)}')" - the exact line in the
log. The ack is posted by the injected bridge shim :2849-2851
"statusApplied: function (text) { post('status-applied', ...) }", dispatched at :3395.

"Audio tap silent - nothing to transcribe" is NOT a worker-state mapping at all -
it is the SHELL'S OWN sentence, hardcoded at :8060-8076, emitted from the BENIGN
branch of _on_silence:

    8060:                 self._bridge_status(
    8061:                     'Audio tap silent - nothing to transcribe', 'busy',
    8062:                     {'title': 'No audio to transcribe',
    8076:                     NO_AUDIO_STATE)

It fires when self.no_audio is True (:8037) - i.e. the WORKER already said the tap
carried nothing (device-rotated reason=flat, a terminal no-audio state, or a done
with a WORKER_NO_AUDIO_VERDICTS verdict, :7993-8032). Severity is busy, not
error, on purpose.

Note the rewrite guard at :7500-7507: FALSE_AUDIO_ABSENT_RE (:318) only rewrites
a status to CAPTURE_NOT_STARTED while self.captions == 0, and it logs
BRIDGE_STATUS_FALSIFIED. "Audio tap silent - nothing to transcribe" survives because
the log shows it - so either the regex does not match it or a caption had already
arrived. NOT DETERMINED which of the two (:318-319 is a multi-line re.compile
I did not read in full).

======================================================================
Q5. BRIDGE_METER / BRIDGE_STATS_PUSH - the worker meter event and blocks
======================================================================

Worker producer: AudioMeter class, worker/sotto_worker.py:1359-1438; fed per
audio block in on_block, emitted at :4868-4871:

    4868:         if meter.enabled:
    4869:             level = meter.tick(p, time.time())
    4870:             for level is not None:
    4871:                 emit(type="meter", **level)

emit itself is :384-387 (one JSON line on stdout). Window cadence
METER_HZ = 10.0 (:1338); the meter is built once per run at :4787
"meter = AudioMeter(meter_hz, now=time.time(), block_s=block_ms / 1000.0)".

WHAT blocks MEANS: the number of AUDIO BLOCKS THE WINDOW COVERED - a per-window
block COUNT, not a cumulative counter and not a level. :1397-1399
"Returns {\"peak\": <window peak>, \"blocks\": <blocks in it>}"; :1427
"out = {\"peak\": round(self.peak, 4), \"blocks\": self.blocks}" then :1428 "reset()".
The reason it is a count is stated at :1402-1405 and :4773-4777: "reporting how
MANY blocks a window covered -- a stalled tap yields a LONGER window, and blocks is
how a consumer sees the gap instead of reading a smooth wave over it".

So blocks=1.0 means the 100 ms window closed after exactly ONE audio block - the
healthy, normal cadence (10 Hz window, 100 ms block). A LARGER blocks means the tap
stalled and the window ran long. peak is the peak OF THAT WINDOW (:4863-4867) -
deliberately NOT counters["peak"], the run maximum, "which IS the staircase the
owner reported".

Shell side, three hops:

 1. _meter (sotto_webview.py:7757-7808) stores self.last_meter (:7791) and logs
    BRIDGE_METER on its own budget - :7793-7800
    "if self._meter_logged == 0 or ((now - self._meter_logged_at) >= METER_LOG_INTERVAL_S)"
    with METER_LOG_INTERVAL_S = 30.0 (:808). So BRIDGE_METER = first sample, then
    one line per 30 s. That is the count=14049 in_window_s=30.0 line.
 2. on_worker_meter (:6225-6245) - the PUSH: :6244 "self.meter_pushes += 1"
    then :6245 "self.emit_async('stats', self.stats())". NO log line per sample here.
 3. _stats_log_maybe (:6211-6224) logs BRIDGE_STATS_PUSH - :6219-6222
    "log(f'BRIDGE_STATS_PUSH count={self.stats_pushes} in_window_s=... rate_hz=... payload=...')",
    gated on first-or-STATS_LOG_INTERVAL_S = 30.0 (:794).

The payload {"tag":"meter","peak":0.0655,"blocks":1.0} is built by stats()
(:6102-6176): if a meter sample is younger than METER_FRESH_S = 2.0 (:803,
:6146-6147) it wins - :6152 "payload['tag'] = 'meter'", and :6153-6156 copies
peak/blocks; otherwise the WORKER_STATS stderr line supplies tag=tick|final with
the RUNNING-MAXIMUM peak (:6158-6175). The two are never mixed (:6133-6137).

Log matches: BRIDGE_METER count=14049 in_window_s=30.0 sample={"peak":0.064,"blocks":1.0,"childPid":39388}
and BRIDGE_STATS_PUSH count=299 in_window_s=30.7 rate_hz=0.1 payload={"tag":"meter","peak":0.0655,"blocks":1.0}.
rate_hz 0.1 is one LOG line per 30 s, NOT the data rate; the data rate is ~10 Hz
(100 ms windows), and BRIDGE_METER count=14049 over 30 s windows is consistent with
~10 Hz.

on_worker_stats (:6188-6210) is the stderr WORKER_STATS twin: :6210
"self.emit_async('stats', payload)" from the SAME stats() shape - the panel cannot
tell a tick from a meter tick except by the tag (:6149-6152, the "row #38" fix).

======================================================================
DELIVERABLE CLEANLINESS
======================================================================

Nothing was written under worker/ or app/. The only file created is this report
under _main/. No process was launched at any point.
