@echo off
REM ===========================================================================
REM  Sotto -- the whole verification battery in one command, AND IT SAYS NO.
REM
REM    _main\_audit-verify-all.cmd            run everything; exit 0 ONLY if every
REM                                           step held and every control went RED
REM
REM  Every step prints a `[step] name rc=N` beacon to the console and the full
REM  output to _main\_audit-verify\*.log, so a claim in the receipt can be
REM  re-checked without re-reading this file. Nothing here starts a window, an
REM  audio device, or the app: the app itself cannot run in this session's
REM  sandbox (pythonnet is denied), which is why the battery is all DOM-free
REM  oracles and compile checks.
REM
REM  ---------------------------------------------------------------------------
REM  AGGREGATION -- added 2026-10-08. WHY IT EXISTS (measured, not imagined):
REM  this file used to print each step's rc and then `exit /b 0` unconditionally,
REM  so a run with THREE red steps (`hotkey-delivery` rc=1, `verdict-gate` rc=2,
REM  `history-producer-gate` rc=1) exited 0. The file everyone quoted as "the
REM  battery is green" could report success while steps were red -- the exact
REM  defect class this repo has been fighting: a failure answering as success.
REM
REM  Now every step's rc is recorded and the batch exits NON-ZERO if ANY step
REM  failed, printing a final summary: total steps, the per-step rc list, the
REM  controls seen, and the names of the failed ones.
REM
REM  FOUR KINDS OF STEP, and the difference matters to a reader:
REM    gate        succeeds when it exits 0                  (:record)
REM    control     succeeds ONLY by catching a deliberately-broken COPY, so it
REM                must exit 0 AND print its own control verdict. A control that
REM                does NOT go red is a FAILURE here, never a pass.       (:control)
REM    skipped     an arm the environment can make UNRUNNABLE (the Alt+C delivery
REM                arm, while the owner's app holds the key): rc=0 AND EITHER the
REM                instrument's skip verdict -- then it is counted in `skipped=` and
REM                NEVER in `gate=`, because it did not verify anything -- OR its
REM                verified verdict, then it counts as a real gate. Neither verdict
REM                present is a FAILURE: a step that cannot say what it did is not a
REM                pass.                                            (:skipped)
REM    expect-red  an instrument with no control mode of its own, run in the mode
REM                that is RED BY DESIGN: it must exit 1 (the defect found) and
REM                print the violation. rc=0 means the defect did not appear,
REM                rc=2 is a setup error -- both are failures here.  (:expectred)
REM  The summary prints which steps are controls and which are skipped, and the
REM  `skipped=` column is the part of the green that is NOT CLAIMED. When the owner
REM  closes the app, that arm stops being skipped and moves from `skipped=` to
REM  `gate=` in the same line -- the transition is visible, never silent.
REM
REM  THE SKIP GUARD closes the other direction: after every step has written its log,
REM  one sweep fails the run if any STEP log carries `VERDICT: SKIPPED` while its step
REM  is not declared skip-capable. An instrument that skips an arm and still exits 0
REM  must not be printed as a pass by a battery that cannot see it.       (skip-verdict-guard)
REM  "STEP log" is load-bearing: the battery's OWN console carries the same literal
REM  text (its beacon ECHOES it), so a sweep that reads the console fails on its own
REM  output -- measured, and cured at the step below.
REM
REM  A MISSING INSTRUMENT IS A FAILURE, NEVER A PASS: a step whose file does not
REM  exist is recorded as rc=MISSING and fails the run. `else ( echo ... MISSING )`
REM  used to be a line on a screen; now it is a red step.
REM
REM  THIS FILE MUST KEEP CRLF LINE ENDINGS. MEASURED 2026-10-08, the first run of
REM  the aggregating version: written LF-only, the batch executed its step list
REM  TWICE and printed TWO summaries -- pass 1 skipped 13 steps and reported
REM  `steps : 16` GREEN, then cmd resumed and re-ran the skipped steps plus the
REM  whole tail, printing a second summary with `steps : 40`. Every beacon was
REM  duplicated (2 model loads, 2 of every control). The subroutines are reached
REM  by `call :label` / `exit /b`, and cmd seeks a batch file by BYTE OFFSET:
REM  with 1-byte LF endings those stored offsets drift, so the interpreter
REM  resumes at the wrong line. Converted to CRLF the same file ran the step list
REM  ONCE (`steps : 29`). If you rewrite this file with a tool that writes `\n`,
REM  convert it back (`-replace "\n", "\r\n"`) or the aggregation will lie.
REM ===========================================================================
setlocal EnableDelayedExpansion
set "ROOT=%~dp0.."
cd /d "%ROOT%"
set "OUT=%ROOT%\_main\_audit-verify"
if not exist "%OUT%" mkdir "%OUT%"
set "CACHE_STATE=%ROOT%\_cache\battery-steps.json"

set "N=0"
set "GATES=0"
set "CTRLS=0"
set "SKIPN=0"
set "REDS=0"
set "MISSINGN=0"
set "BAD=0"
set "CACHEDN=0"
set "STEPLIST="
set "FAILED="
set "CONTROLLIST="
set "SKIPLIST="
REM Basenames of the logs whose step is DECLARED skip-capable and really skipped this
REM run -- the only logs the skip guard below is allowed to see a skip verdict in.
set "SKIPLOGS=,"

echo === compile checks ===
call :step pycompile-sotto_webview 0 "app\webview\sotto_webview.py" "%OUT%\pycompile-webview.log" python -m py_compile app\webview\sotto_webview.py
call :record pycompile-sotto_webview !STEP_RC!
call :step pycompile-webview-helpers 0 "app\webview\hot_reload.py;app\webview\panel_state.py" "%OUT%\pycompile-webview-helpers.log" python -m py_compile app\webview\hot_reload.py app\webview\panel_state.py
call :record pycompile-webview-helpers !STEP_RC!
call :step pycompile-sotto_worker 0 "worker\sotto_worker.py" "%OUT%\pycompile-worker.log" python -m py_compile worker\sotto_worker.py
call :record pycompile-sotto_worker !STEP_RC!
call :step pycompile-wasapi+lang 0 "worker\wasapi_loopback.py;worker\lang_prompt.py" "%OUT%\pycompile-capture.log" python -m py_compile worker\wasapi_loopback.py worker\lang_prompt.py
call :record pycompile-wasapi+lang !STEP_RC!

echo === the panel/engine oracles that were GREEN before the fixes ===
call :step transcript-append-oracle 0 "app\_legacy-electron\transcript-append-oracle.js;app\panel\caption-formulation.js;worker\runs\gate-live-speech.jsonl;worker\runs\ACCEPT-after.jsonl" "%OUT%\oracle-transcript-append.log" node app\_legacy-electron\transcript-append-oracle.js
call :record transcript-append-oracle !STEP_RC!
call :step live-vs-history-source-oracle 0 "_main\live-vs-history-source-oracle.js;app\panel\history-source.js;app\panel\caption-formulation.js;app\panel\panel.js;app\panel\history-store.js" "%OUT%\oracle-live-vs-history.log" node _main\live-vs-history-source-oracle.js
call :record live-vs-history-source-oracle !STEP_RC!
call :step historico-vs-redux-probe 0 "_main\historico-vs-redux-probe.js;app\panel\caption-formulation.js;app\panel\history-store.js" "%OUT%\oracle-historico-vs-redux.log" node _main\historico-vs-redux-probe.js
call :record historico-vs-redux-probe !STEP_RC!

echo === the gates added by this round ===
REM The SECOND control of the same gate, added 2026-10-19: the first one
REM drops the `captions-zero` guard; this one drops the LIVE-OVERLAY term
REM from `emitted` while KEEPING the read. A control that fails for the
REM wrong reason is not a control, and the read is kept on purpose so the
REM copy goes RED on the CLAIM and not on a KeyError.
if exist _main\verdict-gate.py (
  call :step control-verdict-gate-drop-redux-live 0 "_main\verdict-gate.py;worker\sotto_worker.py" "%OUT%\control-verdict-gate-drop-redux-live.log" python _main\verdict-gate.py --control-drop-redux-live
  call :control control-verdict-gate-drop-redux-live !STEP_RC! "%OUT%\control-verdict-gate-drop-redux-live.log" "CONTROL PASS"
) else ( call :control control-verdict-gate-drop-redux-live MISSING "%OUT%\control-verdict-gate-drop-redux-live.log" "CONTROL PASS" )
if exist _main\history-producer-gate.js (
  call :step history-producer-gate 0 "_main\history-producer-gate.js;app\panel\caption-formulation.js;worker\redux_batch.py;worker\sotto_worker.py" "%OUT%\gate-history-producer.log" node _main\history-producer-gate.js
  call :record history-producer-gate !STEP_RC!
) else ( call :record history-producer-gate MISSING )
if exist _main\panel-state-guard-gate.js (
  call :step panel-state-guard-gate 0 "_main\panel-state-guard-gate.js;app\panel\caption-formulation.js;app\panel\panel.js" "%OUT%\gate-panel-state-guard.log" node _main\panel-state-guard-gate.js
  call :record panel-state-guard-gate !STEP_RC!
) else ( call :record panel-state-guard-gate MISSING )
if exist _main\verdict-gate.py (
  call :step verdict-gate 0 "_main\verdict-gate.py;worker\sotto_worker.py" "%OUT%\gate-verdict.log" python _main\verdict-gate.py
  call :record verdict-gate !STEP_RC!
) else ( call :record verdict-gate MISSING )

echo === the per-lane probes ===
if exist _main\_lane2-reset-probe.js (
  call :step lane2-reset-probe 0 "_main\_lane2-reset-probe.js;app\panel\caption-formulation.js;app\panel\panel.js" "%OUT%\lane2-reset.log" node _main\_lane2-reset-probe.js
  call :record lane2-reset-probe !STEP_RC!
) else ( call :record lane2-reset-probe MISSING )
if exist _main\_lane3-verdict-probe.py (
  call :step lane3-verdict-probe 0 "_main\_lane3-verdict-probe.py;worker\sotto_worker.py;worker\config.json" "%OUT%\lane3-verdict.log" python _main\_lane3-verdict-probe.py
  call :record lane3-verdict-probe !STEP_RC!
) else ( call :record lane3-verdict-probe MISSING )
if exist _main\_lane4-tap-stop-probe.py (
  call :step lane4-tap-stop-probe 0 "_main\_lane4-tap-stop-probe.py;worker\wasapi_loopback.py" "%OUT%\lane4-tap-stop.log" python _main\_lane4-tap-stop-probe.py
  call :record lane4-tap-stop-probe !STEP_RC!
) else ( call :record lane4-tap-stop-probe MISSING )
if exist _main\_audit-history-dead.js (
  call :step audit-history-dead 0 "_main\_audit-history-dead.js;app\panel\caption-formulation.js;app\panel\history-source.js;app\panel\history-store.js" "%OUT%\audit-history-dead.log" node _main\_audit-history-dead.js
  call :record audit-history-dead !STEP_RC!
) else ( call :record audit-history-dead MISSING )

echo === the panel's row-identity rule: the SAME probe, both colours (gate here, control in CONTROLS) ===
REM `_panel2-repeat-probe.js` has no `--control-*` flag: its control mode IS `--revert`, whose
REM mutant COPY of panel.js is built inline. Wiring BOTH halves means one battery run shows the
REM rule holding on the shipped panel AND the probe able to go RED without it. This row is the
REM GREEN half; `control-panel2-repeat-revert` is the control.
if exist _main\_panel2-repeat-probe.js (
  call :step panel2-repeat-probe 0 "_main\_panel2-repeat-probe.js;app\panel\panel.html;app\panel\panel.js" "%OUT%\panel2-repeat.log" node _main\_panel2-repeat-probe.js
  call :record panel2-repeat-probe !STEP_RC!
) else ( call :record panel2-repeat-probe MISSING )

echo === the day/hour gallery: the module arithmetic, and the DOM that shows it ===
REM Two instruments, two claims. `history-gallery-oracle.js` requires the SHIPPED
REM `app/panel/history-gallery.js` as a plain module (no DOM, no jsdom) and checks the
REM bucketing plus the LOCAL-time stamp; its `--neg-arm` is the control row below.
REM `_panel2-dom-probe.js` is the jsdom probe that presses the real buttons in the real
REM document -- 78 arms, ARM G being the gallery's. Measured 2026-10-08: GREEN 78/78 on
REM the shipped panel, and RED on exactly the two arms that name the auto-append the
REM owner had removed when the same probe was pointed at a mutant copy via
REM `SOTTO_PANEL_DIR` (the other 76 stayed green).
if exist _main\history-gallery-oracle.js (
  call :step history-gallery-oracle 0 "_main\history-gallery-oracle.js;app\panel\history-gallery.js" "%OUT%\gallery-oracle.log" node _main\history-gallery-oracle.js
  call :record history-gallery-oracle !STEP_RC!
) else ( call :record history-gallery-oracle MISSING )
if exist _main\_panel2-dom-probe.js (
  call :step panel2-dom-probe 0 "_main\_panel2-dom-probe.js;app\panel\panel.html;app\panel\panel.css;app\panel\caption-formulation.js;app\panel\history-source.js;app\panel\history-gallery.js;app\panel\surface.js;app\panel\themes\themes.js;app\panel\themes\panel-designs.js;app\panel\themes\zipc-panels.js;app\panel\theme-switcher.js;app\panel\theme-tune.js;app\panel\panel.js;app\panel\letter-swap.js;app\panel\caption-float.js;app\panel\strip-drag.js" "%OUT%\panel2-dom-probe.log" node _main\_panel2-dom-probe.js
  call :record panel2-dom-probe !STEP_RC!
) else ( call :record panel2-dom-probe MISSING )

REM The live caption BOX (owner, 2026-10-20, verbatim: "a app parece viva mas
REM nao entrega nada"): the caption arrived as a PROVISIONAL line, the list was
REM born with the `hidden` attribute, and only the COMMIT path ever took that
REM attribute off -- so the line was in the DOM and INVISIBLE while the
REM placeholder stayed on screen. This gate runs the REAL panel in jsdom and
REM asserts that the box shows the line, that the placeholder comes back when
REM the box empties, and that the painted line carries the cue the owner saw.
REM Its THREE MUTANTS (real copies of the panel, one break each) must each go
REM RED on the claim they break -- a gate that cannot say NO is decoration.
if exist _main\panel-live-box-oracle.js (
  call :step panel-live-box-oracle 0 "_main\panel-live-box-oracle.js;app\panel\panel.html;app\panel\panel.css;app\panel\panel.js;app\panel\caption-formulation.js;app\panel\surface.js;app\panel\theme-switcher.js;app\panel\letter-swap.js;app\panel\caption-float.js;app\panel\strip-drag.js" "%OUT%\panel-live-box-oracle.log" node _main\panel-live-box-oracle.js
  call :record panel-live-box-oracle !STEP_RC!
) else ( call :record panel-live-box-oracle MISSING )

echo === the wiring and the embedded JS (the two things the other gates cannot see) ===
if exist _main\_audit-worker-start-wiring.py (
  call :step worker-start-wiring 0 "_main\_audit-worker-start-wiring.py;app\webview\sotto_webview.py" "%OUT%\wiring-worker-start.log" python _main\_audit-worker-start-wiring.py
  call :record worker-start-wiring !STEP_RC!
) else ( call :record worker-start-wiring MISSING )
if exist _main\_audit-embedded-js-check.py (
  call :step embedded-js-check 0 "_main\_audit-embedded-js-check.py;app\webview\sotto_webview.py;app\webview\hot_reload.py;app\webview\panel_state.py;app\webview\external_subs.py;app\webview\youtube_captions.py;app\webview\caption_overlay.py;app\webview\caption_wrap.py" "%OUT%\embedded-js.log" python _main\_audit-embedded-js-check.py
  call :record embedded-js-check !STEP_RC!
) else ( call :record embedded-js-check MISSING )
if exist _main\_lane1-worker-default-arms.py (
  call :step lane1-worker-default-arms 0 "_main\_lane1-worker-default-arms.py;app\webview\sotto_webview.py" "%OUT%\lane1-arms.log" python _main\_lane1-worker-default-arms.py
  call :record lane1-worker-default-arms !STEP_RC!
) else ( call :record lane1-worker-default-arms MISSING )

echo === the YouTube captions that REPLACE the live one: the chrome must not reach the box ===
REM Owner, 2026-10-19, verbatim: "eu quero que tu trabalhe nas legendas do youtube
REM substituem a ao vivo". TWO instruments, two claims.
REM
REM `_external-subs-stability-oracle.py` drives the REAL `app/webview/external_subs.py`
REM `caption_lines` against synthetic UI Automation polls, and checks that the chrome the
REM owner's own log produced -- the view counter, the age of the video, a chat handle, a
REM separator glyph, and the counter SPLIT IN TWO WORDS (the case an element-shaped rule
REM cannot see) -- never reaches the caption box. Its `nochrome` arm removes the rule from
REM a COPY and MUST let the chrome through: the oracle has to be able to say no.
REM
REM `external-caption-chrome-census.py` reads the 220 real external lines out of the app's
REM OWN log and says how many of them were chrome; its negative arm removes the rule and
REM shows the survivors going back up.
REM
REM BOTH were outside this battery until 2026-10-19, which is how the `head` arm of the
REM first one rotted in silence: it kept running and it stopped proving anything.
if exist _main\_external-subs-stability-oracle.py (
  call :step external-subs-stability 0 "_main\_external-subs-stability-oracle.py;app\webview\external_subs.py" "%OUT%\external-subs-stability.log" python _main\_external-subs-stability-oracle.py
  call :record external-subs-stability !STEP_RC!
) else ( call :record external-subs-stability MISSING )
if exist _main\external-caption-chrome-census.py (
  call :step external-caption-chrome-census 0 "_main\external-caption-chrome-census.py;app\webview\external_subs.py;_main\webview-run.log" "%OUT%\external-caption-chrome-census.log" python _main\external-caption-chrome-census.py --neg-arm
  call :record external-caption-chrome-census !STEP_RC!
) else ( call :record external-caption-chrome-census MISSING )
REM Owner, 2026-10-20, verbatim: "eu ja mandei tu resolver o negocio de que por
REM algum motivo texto de outras coisas que nao sao o transcript do video do youtube
REM fica vazando pro nosso app". TWO HOLES, and this is the instrument that says
REM no to both of them.
REM
REM `external-subs-geometry-window-oracle.py` drives the REAL
REM `app/webview/external_subs.py` against SYNTHETIC UI Automation trees -- no real
REM window, no browser, no app, no audio, and none of the owner's state touched.
REM It pins:
REM   * the GEOMETRY: with the page rect (0,121,1905,4107) AND the real video
REM     element (16,189,1354,942) both present, the band is 655.86..942 (inside
REM     the video) and NOT 2592.32 (inside the comments), and the measured page
REM     chrome does not reach the caption box; with no video element the old
REM     fallback still reads the window;
REM   * the WINDOW: a "youtube" title in a NON-BROWSER (the owner's own File
REM     Explorer, "kicktwitchyoutube_instagram - Explorador de Arquivos") is not
REM     a player, the YouTube URL is proof on its own, the measured real window
REM     is still external:youtube and still yields its video id, and
REM     find_player_window returns the browser's window, not the Explorer's.
REM
REM Its NEGATIVE ARM is EXECUTED: six broken copies of the module, and each one
REM has to turn an arm RED. A gate that cannot fail is a promise.
if exist _main\external-subs-geometry-window-oracle.py (
  call :step external-subs-geometry-window 0 "_main\external-subs-geometry-window-oracle.py;app\webview\external_subs.py" "%OUT%\external-subs-geometry-window.log" python _main\external-subs-geometry-window-oracle.py
  call :record external-subs-geometry-window !STEP_RC!
) else ( call :record external-subs-geometry-window MISSING )


echo === the YOUTUBE REAL TRACK, the MUTE, and the rule that the ASR is the base ===

REM Three instruments for the owner's order of 2026-10-19: *"faz a legenda do
REM youtube mostrar na tela em tempo real"*, *"youtube ta mostrando texto burro
REM da pagina inves da porra da legenda/transcriptino de um video"* and *"e nao
REM e pra tu parar de transcrever audio do chrome. e audio do youtube CASO
REM tenha legenda do youtube. se for um video sem legenda, vaio transcrever ao
REM vivo igual."*
REM
REM `youtube-captions-oracle.py` judges the READER: the video's OWN caption
REM track (yt-dlp), the four states (has-track / no-track / no-cue-in-window /
REM time-unknown), and the player's clock read from the real seek bar.
REM
REM `youtube-track-wiring-oracle.py` judges the WIRING: that the PAGE's own text
REM never reaches the caption box for a YouTube window, that only a REAL cue
REM ever stops the live transcription, and that a video with no caption track
REM gives the microphone back. It builds FIVE broken copies of the shell and
REM requires each one to turn an arm RED.
REM
REM `mute-audio-oracle.py` is the MUTE (owner, 2026-10-19, verbatim: *"se tu
REM vai usar audio padrao pra testar qualquer coisa, muta"*). It was OUTSIDE
REM this battery until now -- which is exactly how a gate rots in silence: it
REM kept passing and it stopped being asked. Its arms restore the original
REM volume in a `finally`, so a failed arm cannot leave the owner's speakers
REM muted.
if exist _main\youtube-captions-oracle.py (
  call :step youtube-captions 0 "_main\youtube-captions-oracle.py;app\webview\youtube_captions.py" "%OUT%\youtube-captions.log" python _main\youtube-captions-oracle.py
  call :record youtube-captions !STEP_RC!
) else ( call :record youtube-captions MISSING )
if exist _main\youtube-track-wiring-oracle.py (
  call :step youtube-track-wiring 0 "_main\youtube-track-wiring-oracle.py;app\webview\sotto_webview.py" "%OUT%\youtube-track-wiring.log" python _main\youtube-track-wiring-oracle.py
  call :record youtube-track-wiring !STEP_RC!
) else ( call :record youtube-track-wiring MISSING )
REM The FREEZE. Owner, 2026-10-20, verbatim: *"abrir ou fechar o sotto,
REM principalemnte fechar, trava pra caralho meu pc. arruma."* -- and the
REM owner's own log says why, with a number: 68 s from the spawn to the model
REM (`BRIDGE_LOAD_MS ms=67969` with `worker_load_s=8.75`), of which ~59 s was
REM the CAPTURE LADDER waiting on a Bluetooth headset whose open BLOCKS (it
REM does not come back and it raises nothing), and at QUIT the caption
REM reader's release path brought the worker BACK, 0.65 s before the shell
REM exited -- an orphan, because `os._exit` does not kill a child.
REM The gate judges the two fixes: the open has a DEADLINE, and the shell does
REM not bring the worker back while it is dying.
if exist _main\tap-open-timeout-oracle.py (
  call :step tap-open-timeout 0 "_main\tap-open-timeout-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\tap-open-timeout.log" python _main\tap-open-timeout-oracle.py
  call :record tap-open-timeout !STEP_RC!
) else ( call :record tap-open-timeout MISSING )
if exist _main\mute-audio-oracle.py (
  call :step always mute-audio 0 "_main\mute-audio-oracle.py" "%OUT%\mute-audio.log" python _main\mute-audio-oracle.py
  call :record mute-audio !STEP_RC!
) else ( call :record mute-audio MISSING )

echo === the adversary lane's probes (corrected: the filters it wrote were RED-forever) ===
if exist _main\_review-f1f3.py (
  call :step review-f1f3 0 "_main\_review-f1f3.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\review-f1f3.log" python _main\_review-f1f3.py
  call :record review-f1f3 !STEP_RC!
) else ( call :record review-f1f3 MISSING )
if exist _main\_review-tapstop.py (
  call :step review-tapstop 0 "_main\_review-tapstop.py;worker\wasapi_loopback.py" "%OUT%\review-tapstop.log" python _main\_review-tapstop.py
  call :record review-tapstop !STEP_RC!
) else ( call :record review-tapstop MISSING )

echo === the strip surface, the wave, and the hot reload that must never wait forever ===
REM Five instruments from the strip-surface lane. The ORACLE builds FOUR broken
REM copies of today's shell (the JS member removed, the dispatch routing removed,
REM the CSS height blinded, the per-sample log restored) and requires each to go
REM RED on its own claim -- so it is a `:control`, and it prints its control
REM verdict. The LOG probe does the same with ONE copy (the per-sample push) and
REM prints its own. The other three are plain gates: each exits 0 only after its
REM arms held, and each is launched with `--no-worker`/`--no-hotkey` so no model
REM is loaded and no audio device is opened.
if exist _main\_strip-surface-oracle.py (
  call :step strip-surface-oracle 0 "_main\_strip-surface-oracle.py;app\webview\sotto_webview.py;app\panel\panel.js;worker\sotto_worker.py" "%OUT%\strip-surface-oracle.log" python _main\_strip-surface-oracle.py
  call :control strip-surface-oracle !STEP_RC! "%OUT%\strip-surface-oracle.log" "STRIP-ORACLE CONTROL PASS"
) else ( call :control strip-surface-oracle MISSING "%OUT%\strip-surface-oracle.log" "STRIP-ORACLE CONTROL PASS" )
if exist _main\_strip-stats-log-probe.py (
  call :step strip-stats-log-budget 0 "_main\_strip-stats-log-probe.py;app\webview\sotto_webview.py;_main\_strip-stats-worker.py" "%OUT%\strip-stats-log.log" python _main\_strip-stats-log-probe.py
  call :control strip-stats-log-budget !STEP_RC! "%OUT%\strip-stats-log.log" "STRIP-LOG CONTROL PASS"
) else ( call :control strip-stats-log-budget MISSING "%OUT%\strip-stats-log.log" "STRIP-LOG CONTROL PASS" )
if exist _main\_strip-reload-probe.py (
  call :step strip-hot-reload 0 "_main\_strip-reload-probe.py;app\webview\sotto_webview.py;_main\_strip-stats-worker.py" "%OUT%\strip-reload.log" python _main\_strip-reload-probe.py
  call :record strip-hot-reload !STEP_RC!
) else ( call :record strip-hot-reload MISSING )
if exist _main\_strip-surface-probe.py (
  call :step strip-surface-runtime 0 "_main\_strip-surface-probe.py;app\webview\sotto_webview.py;app\panel\panel.css" "%OUT%\strip-surface.log" python _main\_strip-surface-probe.py
  call :record strip-surface-runtime !STEP_RC!
) else ( call :record strip-surface-runtime MISSING )
if exist _main\_strip-restore-probe.py (
  call :step strip-geometry-restore 0 "_main\_strip-restore-probe.py;app\webview\sotto_webview.py" "%OUT%\strip-restore.log" python _main\_strip-restore-probe.py
  call :record strip-geometry-restore !STEP_RC!
) else ( call :record strip-geometry-restore MISSING )
if exist _main\_strip-stats-probe.py (
  call :step strip-stats-wave 0 "_main\_strip-stats-probe.py;app\webview\sotto_webview.py;_main\_strip-stats-worker.py" "%OUT%\strip-stats.log" python _main\_strip-stats-probe.py
  call :record strip-stats-wave !STEP_RC!
) else ( call :record strip-stats-wave MISSING )

echo === Alt+C, the only control: registration table, delivery+fallback+mutex, autostart ===
if exist _main\_audit-hotkey-probe.py (
  call :step always hotkey-registration 0 "_main\_audit-hotkey-probe.py" "%OUT%\hotkey-registration.log" python _main\_audit-hotkey-probe.py
  call :record hotkey-registration !STEP_RC!
) else ( call :record hotkey-registration MISSING )
if exist _main\_audit-hotkey-delivery.py (
  call :step always hotkey-delivery 0 "_main\_audit-hotkey-delivery.py;app\webview\sotto_webview.py" "%OUT%\hotkey-delivery.log" python _main\_audit-hotkey-delivery.py
  call :skipped hotkey-delivery !STEP_RC! "%OUT%\hotkey-delivery.log" "VERDICT: GREEN" "VERDICT: SKIPPED" "CANNOT claim"
) else ( call :skipped hotkey-delivery MISSING "%OUT%\hotkey-delivery.log" "VERDICT: GREEN" "VERDICT: SKIPPED" "CANNOT claim" )
REM The autostart check READS the registry (a read needs no elevation) and fails
REM if the Run value points somewhere other than THIS checkout -- which is what a moved tree looks like from the login side. The step runs _main\autostart-status-check.py (2026-10-12) because the shell OWN exit code IS the status (0=on+matching, 1=off, 2=unreadable, 3=elsewhere): recording that rc as a plain gate painted a healthy OFF machine RED. The wrapper reads the registry itself, cross-checks the shell own answer, exits 0 for the two VALID states and 3 for another checkout. The REM line below keeps its original wording.
REM moved tree looks like from the login side.
call :step always autostart-status 0 "_main\autostart-status-check.py;app\webview\sotto_webview.py" "%OUT%\autostart-status.log" python _main\autostart-status-check.py
call :record autostart-status !STEP_RC!

echo === CONTROLS: every one of these succeeds ONLY by going RED on a broken copy ===
REM ---------------------------------------------------------------------------
REM These are the arms that had ROTTED because nothing ever ran them. A control
REM that is never executed silently stops being a control: `verdict-gate.py
REM --control-unguard-captions-zero` and `history-producer-gate.js
REM --control-stamp-nvidia` both sat exiting 2 (a setup error, i.e. no control at
REM all) with every gate around them green. They are steps now, and the summary
REM marks them as controls.
REM
REM Each line requires BOTH: the instrument's rc=0 -- which each of these returns
REM ONLY after it has built its broken copy and seen the gate go RED on it -- AND
REM the control verdict text in the log, quoted with python (ASCII substrings, so
REM a console-codepage mojibake cannot hide a missing verdict). rc=0 without the
REM text is a failure here, and so is a MISSING instrument.
REM ---------------------------------------------------------------------------
if exist _main\verdict-gate.py (
  call :step control-verdict-gate-unguard 0 "_main\verdict-gate.py;worker\sotto_worker.py" "%OUT%\control-verdict-gate-unguard.log" python _main\verdict-gate.py --control-unguard-captions-zero
  call :control control-verdict-gate-unguard !STEP_RC! "%OUT%\control-verdict-gate-unguard.log" "CONTROL PASS"
) else ( call :control control-verdict-gate-unguard MISSING "%OUT%\control-verdict-gate-unguard.log" "CONTROL PASS" )
if exist _main\history-producer-gate.js (
  call :step control-history-producer-stamp-nvidia 0 "_main\history-producer-gate.js;app\panel\caption-formulation.js;worker\redux_batch.py;worker\sotto_worker.py" "%OUT%\control-history-producer-stamp-nvidia.log" node _main\history-producer-gate.js --control-stamp-nvidia
  call :control control-history-producer-stamp-nvidia !STEP_RC! "%OUT%\control-history-producer-stamp-nvidia.log" "CONTROL PASS"
) else ( call :control control-history-producer-stamp-nvidia MISSING "%OUT%\control-history-producer-stamp-nvidia.log" "CONTROL PASS" )
REM `redux-flag-gate.py --neg-arm` already runs the shipped pair GREEN and then
REM builds one mutant COPY per claim, requiring each to go RED on its own claim
REM ONLY; rc=0 is that conjunction. This is the superset of the plain gate, which
REM is why the plain form is not a separate step.
if exist _main\redux-flag-gate.py (
  call :step control-redux-flag-neg-arm 0 "_main\redux-flag-gate.py;worker\sotto_worker.py;app\webview\sotto_webview.py" "%OUT%\control-redux-flag-neg-arm.log" python _main\redux-flag-gate.py --neg-arm
  call :control control-redux-flag-neg-arm !STEP_RC! "%OUT%\control-redux-flag-neg-arm.log" "NEG-VERDICT: GREEN"
) else ( call :control control-redux-flag-neg-arm MISSING "%OUT%\control-redux-flag-neg-arm.log" "NEG-VERDICT: GREEN" )
REM `--unit --neg-arm` is the no-shell half: the classifier's arms, the `done`
REM mapping and the recovery arm, plus two reverted COPIES of today's shell that
REM must go RED. rc=0 requires every one of those; the JSON keys `neg_arm` /
REM `neg_arm_e` prove the control halves actually ran rather than being skipped.
if exist _main\panel-exit3-oracle.py (
  call :step control-panel-exit3-neg-arm 0 "_main\panel-exit3-oracle.py;app\webview\sotto_webview.py;worker\sotto_worker.py" "%OUT%\control-panel-exit3-neg-arm.log" python _main\panel-exit3-oracle.py --unit --neg-arm
  call :control control-panel-exit3-neg-arm !STEP_RC! "%OUT%\control-panel-exit3-neg-arm.log" "neg_arm_e"
) else ( call :control control-panel-exit3-neg-arm MISSING "%OUT%\control-panel-exit3-neg-arm.log" "neg_arm_e" )
REM `wasapi-com-init-oracle.py` with NO flag is already both colours in one
REM command: the live module must PASS and the recorded pre-fix copy must be RED.
REM It opens no audio device by construction (stubbed `_ole32`, arms 5-6 only
REM CoInitialize/CoUninitialize). Its own `--neg-arm` is the pre-fix copy ALONE --
REM a debug subset of this run -- so the plain form is what is wired.
if exist _main\wasapi-com-init-oracle.py (
  call :step control-wasapi-com-init 0 "_main\wasapi-com-init-oracle.py;worker\wasapi_loopback.py" "%OUT%\control-wasapi-com-init.log" python _main\wasapi-com-init-oracle.py
  call :control control-wasapi-com-init !STEP_RC! "%OUT%\control-wasapi-com-init.log" "NEGARM : PASS"
) else ( call :control control-wasapi-com-init MISSING "%OUT%\control-wasapi-com-init.log" "NEGARM : PASS" )
REM `_panel2-repeat-probe.js --revert` is the row-identity rule's negative control: it builds a COPY
REM of `app/panel/panel.js` with the identity lookup disabled, and all four arms must then FAIL.
REM TWO verdict strings are required, not one, because this probe's failure mode was not a wrong
REM verdict but an UNREACHABLE one: rc=1 with a `TypeError` and no `RESULT:` line at all, and the
REM mutant left on disk, in BOTH colours (measured 2026-10-08 against the pre-fix revision). rc=0 now
REM means the arms ran, the control went RED, and the mutant was removed.
if exist _main\_panel2-repeat-probe.js (
  call :step control-panel2-repeat-revert 0 "_main\_panel2-repeat-probe.js;app\panel\panel.html;app\panel\panel.js" "%OUT%\control-panel2-repeat-revert.log" node _main\_panel2-repeat-probe.js --revert
  call :control control-panel2-repeat-revert !STEP_RC! "%OUT%\control-panel2-repeat-revert.log" "CONTROL PASS" "control copy removed: true"
) else ( call :control control-panel2-repeat-revert MISSING "%OUT%\control-panel2-repeat-revert.log" "CONTROL PASS" "control copy removed: true" )
REM `history-gallery-oracle.js --neg-arm` injects the bare-date stamp
REM (`new Date(entry.date)`) into a COPY of the module's parse and requires the LOCAL-time
REM arm to go RED while the stamp-independent arms stay green. The box is GMT-0300
REM (offsetMinutes=180, printed by the run), so the trap is OBSERVABLE here; on a UTC box
REM the same injection moves nothing and the oracle says so instead of claiming a control
REM it did not have -- that vacuity is the failure this row exists to catch.
if exist _main\history-gallery-oracle.js (
  call :step control-history-gallery-neg-arm 0 "_main\history-gallery-oracle.js;app\panel\history-gallery.js" "%OUT%\control-history-gallery-neg-arm.log" node _main\history-gallery-oracle.js --neg-arm
  call :control control-history-gallery-neg-arm !STEP_RC! "%OUT%\control-history-gallery-neg-arm.log" "NEG-ARM-VERDICT: PASS" "local-arm-red=true"
) else ( call :control control-history-gallery-neg-arm MISSING "%OUT%\control-history-gallery-neg-arm.log" "NEG-ARM-VERDICT: PASS" "local-arm-red=true" )
REM `historico-vs-redux-probe.js --gate-off` has NO control mode of its own: the
REM flag loads the store with the one guard line DELETED, so the probe is RED BY
REM DESIGN and exits 1 (its own "FAIL" code) with the violation named. That is why
REM this one is :expectred and not :control.
if exist _main\historico-vs-redux-probe.js (
  call :step red-as-expected-historico-gate-off 1 "_main\historico-vs-redux-probe.js;app\panel\caption-formulation.js;app\panel\history-store.js" "%OUT%\control-historico-gate-off.log" node _main\historico-vs-redux-probe.js --gate-off
  call :expectred red-as-expected-historico-gate-off !STEP_RC! "%OUT%\control-historico-gate-off.log" "RESULT: RED" "FAIL] no provisional draft reaches the transcript"
) else ( call :expectred red-as-expected-historico-gate-off MISSING "%OUT%\control-historico-gate-off.log" "RESULT: RED" "FAIL] no provisional draft reaches the transcript" )

echo === the heavy one LAST: loads the int8 model, opens NO device ===
if exist _main\_audit-fresh-processor-probe.py (
  call :step fresh-processor-probe 0 "_main\_audit-fresh-processor-probe.py;worker\config.json;worker\sotto_worker.py;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\.gitattributes;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\audio_processor_config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\decoder.onnx;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\decoder.onnx.data;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\encoder.onnx;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\encoder.onnx.data;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\genai_config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\joint.onnx;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\joint.onnx.data;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\model_config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\README.md;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\silero_vad.onnx;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\tokenizer_config.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\tokenizer.json;worker\models\nemotron-3.5-asr-ptbr-onnx-int4\vocab.txt" "%OUT%\fresh-processor.log" python _main\_audit-fresh-processor-probe.py
  call :record fresh-processor-probe !STEP_RC!
) else ( call :record fresh-processor-probe MISSING )

echo === the cache that makes this battery incremental ===
REM The oracle of the cache itself: the arms (HIT/MISS by CONTENT) and the
REM EXECUTED negative arm -- four broken copies of the engine, each of which
REM has to go RED on its own claim. It runs in its own temp dir and never
REM touches this battery or the real state.
if exist _main\_stepcache-oracle.py (
  call :step stepcache-oracle 0 "_main\_stepcache-oracle.py;_main\_stepcache.py" "%OUT%\stepcache-oracle.log" python _main\_stepcache-oracle.py
  call :record stepcache-oracle !STEP_RC!
) else ( call :record stepcache-oracle MISSING )

echo === the skip guard: NO step may print a skip verdict unless its kind declares it ===
REM Every step above wrote its log. An instrument that silently skips an arm and still
REM exits 0 is a skip wearing a pass, and the difference is visible only in its log --
REM so this single sweep refuses the whole run if ANY step's log carries a skip verdict
REM (`VERDICT: SKIPPED`) while that step is not declared skip-capable. The declared
REM logs are named by `:skipped` itself and handed to the instrument in `--exclude`.
REM
REM IT USED TO READ ITS OWN TRANSCRIPT -- measured 2026-10-08, do not narrow this
REM back. The sweep was an inline python that globbed `%OUT%\*.log` and excluded only
REM `_run-*`. The battery's own console, kept in `%OUT%` as `_battery-run-<ts>.log`,
REM carries the literal `VERDICT: SKIPPED` -- because `:skipped` ECHOES the skip text
REM in its beacon line -- so the guard failed the whole run for a DECLARED skip,
REM naming `_battery-run-20261007-130942.log` and `_battery-run-20261007-131528.log`.
REM A guard that fails on its own output is not measuring the steps. THE RULE NOW: a
REM STEP LOG is a `*.log` in `%OUT%` whose basename does NOT start with `_`, because
REM every artifact the battery itself writes is `_`-prefixed (`_battery-run-*`,
REM `_run-*`, `_skip-guard.log`, `_battery-summary.txt`) and a run console is a
REM transcript of the whole run, not the log of a step.
REM The instrument ALSO runs a five-arm control on EVERY invocation, so it cannot be
REM green by reading nothing. Both colours, one command each:
REM   python _main\_skip-verdict-guard.py --dir _main\_audit-verify --exclude ",hotkey-delivery.log,"   -> rc 0, 64 logs read
REM   python _main\_skip-verdict-guard.py --dir _main\_skip-guard-redcheck --exclude ","                   -> rc 1, names bogus-step.log only
if exist _main\_skip-verdict-guard.py (
  call :step always skip-verdict-guard 0 "_main\_skip-verdict-guard.py" "%OUT%\_skip-guard.log" python _main\_skip-verdict-guard.py --dir "%OUT%" --exclude "!SKIPLOGS!"
  call :record skip-verdict-guard !STEP_RC!
) else ( call :record skip-verdict-guard MISSING )

echo.
echo =============== BATTERY SUMMARY ===============
echo steps    : !N!   gate=!GATES!  control=!CTRLS!  skipped=!SKIPN!  expect-red=!REDS!  missing=!MISSINGN!  cached=!CACHEDN!
echo cached   : !CACHEDN! step(s) were reused from the cache (their content and their logs were unchanged)
echo per-step : !STEPLIST!
echo controls : !CONTROLLIST!
if "!FAILED!"=="" ( set "FAILEDTEXT=-none-" ) else ( set "FAILEDTEXT=!FAILED!" )
if "!SKIPLIST!"=="" ( set "SKIPTEXT=-none-" ) else ( set "SKIPTEXT=!SKIPLIST!" )
echo failed   : !FAILEDTEXT!
echo skipped  : !SKIPTEXT!
if "!BAD!"=="0" (
  set "VERDICT=GREEN - every step held and every control went RED on its broken copy"
)
if "!BAD!"=="0" if not "!SKIPN!"=="0" (
  set "VERDICT=GREEN WITH !SKIPN! SKIPPED - !SKIPN! step(s) did NOT verify this run and are NOT counted as gates: !SKIPTEXT!"
)
if "!BAD!"=="0" if not "!CACHEDN!"=="0" (
  set "VERDICT=!VERDICT! - !CACHEDN! step(s) were reused from the cache: their files did not change and their logs are still the ones that were verified"
)
if not "!BAD!"=="0" (
  set "VERDICT=RED - !BAD! step(s) failed"
)
echo BATTERY-VERDICT: !VERDICT!
echo receipts in %OUT%
>"%OUT%\_battery-summary.txt" echo steps=!N! gate=!GATES! control=!CTRLS! skipped=!SKIPN! expect-red=!REDS! missing=!MISSINGN! cached=!CACHEDN! failed=!BAD!
>>"%OUT%\_battery-summary.txt" echo rcs: !STEPLIST!
>>"%OUT%\_battery-summary.txt" echo controls: !CONTROLLIST!
>>"%OUT%\_battery-summary.txt" echo skipped: !SKIPTEXT!
>>"%OUT%\_battery-summary.txt" echo failed: !FAILEDTEXT!
>>"%OUT%\_battery-summary.txt" echo exit-code: !BAD!
>>"%OUT%\_battery-summary.txt" echo BATTERY-VERDICT: !VERDICT!
REM The exit code IS the aggregation: 0 only when nothing failed. Nothing else in
REM this file may return 0 on a red step.
if not "!BAD!"=="0" exit /b 1
exit /b 0

REM ===========================================================================
REM  The recorders. Every step calls exactly one of these with its OWN rc as an
REM  argument, so no step can print a beacon without being counted.
REM ===========================================================================

REM ===========================================================================
REM  THE STEP CACHE. One step, one fingerprint, one honest answer.
REM ===========================================================================
REM
REM :step [always] <name> <expect-rc> <deps;> <logfile> <command...>
REM
REM   The engine is _main\_stepcache.py and the state is _cache\battery-steps.json.
REM   The fingerprint of a step is the CONTENT of every file it judges -- the
REM   instrument itself plus the product files it reads. Change the bytes and
REM   the step runs again; touch a file without changing a byte and it does
REM   NOT. mtime alone decides nothing, because mtime is not what the gate read.
REM
REM   A HIT is only a HIT when all three hold: the fingerprint matches, the
REM   recorded rc is the rc this step is SUPPOSED to produce, and the log the
REM   step produced is still there, byte for byte. Anything else is a MISS. A
REM   step that FAILED is never reused as if it had passed: the rc is part of
REM   the proof, not a decoration.
REM
REM   `always` marks a step whose truth is OUTSIDE the files -- the Windows
REM   registry, the real keyboard, the real audio device, the owner's own app
REM   holding Alt+C, and the sweep that proves no step lied. Those are NEVER
REM   cached: a cache that reuses a reading of the outside world is a lie, and
REM   a lie that is faster is still a lie.
REM
REM   The command's exit code comes back in STEP_RC, and the caller hands it to
REM   the recorder (:record / :control / :skipped / :expectred), so the FOUR
REM   KINDS keep their meaning exactly as before. A cached step still has to
REM   prove its verdict in its log -- the control reads the SAME log the
REM   previous run wrote, and if the verdict text is not there, it FAILS.
REM
REM   STEP_CACHED says whether the step was reused (the summary counts them),
REM   and STEP_TAG is the "  (cached)" the beacon carries so a reader can see
REM   which steps did not run.
:step
set "STEP_RC="
set "STEP_CACHED=0"
set "STEP_TAG="
set "S_ALWAYS="
if /i "%~1"=="always" goto step_take_always
goto step_args
:step_take_always
set "S_ALWAYS=1"
shift
:step_args
set "S_NAME=%~1"
set "S_EXPECT=%~2"
set "S_DEPS=%~3"
set "S_LOG=%~4"
shift
shift
shift
shift
set "S_CMD="
:step_build
if "%~1"=="" goto step_built
if defined S_CMD goto step_append
set "S_CMD=%~1"
shift
goto step_build
:step_append
set "S_CMD=!S_CMD! "%~1""
shift
goto step_build
:step_built
if "!S_ALWAYS!"=="1" goto step_run
set "S_HIT=0"
set "S_CACHED_RC="
for /f "tokens=1,* delims==" %%A in ('python _main\_stepcache.py check --step "!S_NAME!" --expect-rc !S_EXPECT! --deps "!S_DEPS!" --log "!S_LOG!" --state "%CACHE_STATE%" 2^>nul') do (
  if /i "%%A"=="HIT" set "S_HIT=1"
  if /i "%%A"=="rc" set "S_CACHED_RC=%%B"
)
if "!S_HIT!"=="1" goto step_hit
:step_run
!S_CMD! > "!S_LOG!" 2>&1
set "STEP_RC=!ERRORLEVEL!"
python _main\_stepcache.py record --step "!S_NAME!" --expect-rc !S_EXPECT! --deps "!S_DEPS!" --rc !STEP_RC! --log "!S_LOG!" --state "%CACHE_STATE%" >nul 2>&1
exit /b 0
:step_hit
set "STEP_RC=!S_CACHED_RC!"
set "STEP_CACHED=1"
set "STEP_TAG=  (cached)"
set /a CACHEDN+=1
exit /b 0
REM :record <name> <rc>          -- an ordinary gate: rc=0 is the only pass.
:record
set /a N+=1
set /a GATES+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
if "%~2"=="0" (
  echo [step] %~1 rc=0!STEP_TAG!
  exit /b 0
)
if /i "%~2"=="MISSING" (
  set /a MISSINGN+=1
  set /a BAD+=1
  set "FAILED=!FAILED! %~1=MISSING"
  echo [step] %~1 MISSING  ** THE INSTRUMENT IS NOT THERE: a missing step is not a pass **
  exit /b 0
)
set /a BAD+=1
set "FAILED=!FAILED! %~1=%~2"
echo [step] %~1 rc=%~2  ** FAILED **
exit /b 0

REM :skipped <name> <rc> <log> <verified-text> <skip-text> [<skip-text-2>]
REM   For an arm the ENVIRONMENT can make unrunnable -- today the Alt+C delivery arm,
REM   which `_audit-hotkey-delivery.py` skips by design while the owner's live shell
REM   holds the key. Three outcomes, and no fourth:
REM     * rc<>0 or MISSING                 -> FAILURE (a step that exits non-zero has
REM                                           not "skipped", it has failed)
REM     * rc=0 AND the skip text(s) present -> SKIPPED: counted in `skipped=`, listed
REM                                           in the summary, and NEVER counted in
REM                                           `gate=`, because nothing was verified
REM     * rc=0 AND the verified text present, no skip text -> a REAL gate this run
REM     * rc=0 with NEITHER                -> FAILURE. This is the direction that
REM       matters: an instrument that cannot say whether it verified or skipped must
REM       not be rounded up to a pass, and a silent no-op posing as a skip is exactly
REM       the family this battery exists to kill.
REM   A second skip text makes the skip claim stronger: for this probe both
REM   `VERDICT: SKIPPED` AND `CANNOT claim` are required, so a stray mention of the
REM   word in a verified run cannot be read as a skip.
:skipped
set /a N+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
set "WHY="
set "OUTCOME="
if /i "%~2"=="MISSING" set "WHY=THE INSTRUMENT IS NOT THERE - a missing step is not a pass, and it is not a skip either"
if not "%~2"=="0" if not defined WHY set "WHY=rc=%~2 - this step exits 0 whether it verifies or skips, so a non-zero rc is a FAILURE, not a skip"
if not defined WHY (
  call :hastext "%~3" "%~5"
  if "!HAS!"=="yes" set "OUTCOME=skipped"
)
if not defined WHY if not "%~6"=="" (
  call :hastext "%~3" "%~6"
  if not "!HAS!"=="yes" set "OUTCOME="
)
if not defined WHY if not defined OUTCOME (
  call :hastext "%~3" "%~4"
  if "!HAS!"=="yes" set "OUTCOME=verified"
)
if not defined WHY if not defined OUTCOME set "WHY=rc=0 but the log carries NEITHER the skip verdict (%~5) NOR the verified verdict (%~4) - the instrument cannot say what it did, and a step that cannot say is not a pass"
if defined WHY (
  set /a BAD+=1
  set "FAILED=!FAILED! %~1=%~2"
  echo [step] %~1 rc=%~2  [SKIP-CAPABLE]  ** STEP FAILED: !WHY! **
  if /i "%~2"=="MISSING" set /a MISSINGN+=1
  exit /b 0
)
if "!OUTCOME!"=="skipped" (
  set /a SKIPN+=1
  set "SKIPLIST=!SKIPLIST! %~1"
  for %%F in ("%~3") do set "SKIPLOGS=!SKIPLOGS!%%~nxF,"
  echo [step] %~1 rc=0  [SKIPPED] NOT VERIFIED: the instrument itself says this arm did not run, its own words being %~5!STEP_TAG!
  exit /b 0
)
set /a GATES+=1
echo [step] %~1 rc=0  [SKIP-CAPABLE, verified this run] %~4 - the skip verdict is absent, so this IS a gate!STEP_TAG!
exit /b 0

REM :control <name> <rc> <log> <required-text> [<required-text-2>]
REM   A control PASSES only when the instrument exits 0 (its own "the copy went
REM   RED" signal) AND its log carries the required verdict text. Anything else --
REM   a non-zero rc, a missing file, an rc=0 with no verdict in the log -- FAILS.
REM   The optional second text exists for a probe whose verdict can be unreachable
REM   (rc=1 and a traceback instead of a verdict): it lets the step demand a second,
REM   independent fact from the same run (e.g. that the mutant COPY was removed).
:control
set /a N+=1
set /a CTRLS+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
set "CONTROLLIST=!CONTROLLIST! %~1(rc=%~2)"
set "WHY="
if /i "%~2"=="MISSING" set "WHY=THE INSTRUMENT IS NOT THERE - a missing control is not a pass"
if not "%~2"=="0" if not defined WHY set "WHY=rc=%~2 and this step succeeds ONLY by catching its broken copy"
if not defined WHY (
  call :hastext "%~3" "%~4"
  if not "!HAS!"=="yes" set "WHY=rc=0 but the log never printed the control verdict %~4 - the control did not report catching its copy"
)
if not defined WHY if not "%~5"=="" (
  call :hastext "%~3" "%~5"
  if not "!HAS!"=="yes" set "WHY=rc=0 but the log never printed %~5"
)
if not defined WHY (
  echo [step] %~1 rc=0  [CONTROL] went RED on the broken copy as required!STEP_TAG!
  exit /b 0
)
set /a BAD+=1
set "FAILED=!FAILED! %~1=%~2"
echo [step] %~1 rc=%~2  [CONTROL]  ** CONTROL FAILED: !WHY! **
if /i "%~2"=="MISSING" set /a MISSINGN+=1
exit /b 0

REM :expectred <name> <rc> <log> <required-text> [<required-text-2>]
REM   For an instrument whose RED-by-design mode has NO control wrapper. It must
REM   exit 1 -- the defect found -- and print the violation it found. rc=0 means
REM   the deliberately-broken copy was NOT caught (the control did not go red),
REM   and rc=2 is a setup error: both FAIL.
:expectred
set /a N+=1
set /a REDS+=1
set "STEPLIST=!STEPLIST! %~1=%~2"
set "CONTROLLIST=!CONTROLLIST! %~1(rc=%~2)"
set "WHY="
if /i "%~2"=="MISSING" set "WHY=THE INSTRUMENT IS NOT THERE - a missing control is not a pass"
if not "%~2"=="1" if not defined WHY set "WHY=rc=%~2 - this step must find the injected defect and exit 1; rc=0 means the control did NOT go red, rc=2 is a setup error"
if not defined WHY (
  call :hastext "%~3" "%~4"
  if not "!HAS!"=="yes" set "WHY=rc=1 but the log never printed %~4"
)
if not defined WHY if not "%~5"=="" (
  call :hastext "%~3" "%~5"
  if not "!HAS!"=="yes" set "WHY=rc=1 but the log never printed %~5"
)
if not defined WHY (
  echo [step] %~1 rc=1  [EXPECT-RED] the defect was found and named, as required!STEP_TAG!
  exit /b 0
)
set /a BAD+=1
set "FAILED=!FAILED! %~1=%~2"
echo [step] %~1 rc=%~2  [EXPECT-RED]  ** CONTROL FAILED: !WHY! **
if /i "%~2"=="MISSING" set /a MISSINGN+=1
exit /b 0

REM :hastext <file> <text>  -- sets HAS=yes|no. Read as BYTES and decoded as
REM UTF-8 so a console-codepage mojibake in the log cannot hide a verdict, and so
REM the required text may contain quotes or an em dash.
:hastext
set "HAS=no"
python -c "import io,sys;t=io.open(sys.argv[1],'rb').read().decode('utf-8','replace');sys.exit(0 if sys.argv[2] in t else 3)" "%~1" "%~2" >nul 2>&1
if "!ERRORLEVEL!"=="0" set "HAS=yes"
exit /b 0
