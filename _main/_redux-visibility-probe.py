#!/usr/bin/env python3
"""Sotto — the panel-visibility channel and the worker's mode switch, MEASURED.

OWNER, 2026-10-07, verbatim: *"o nvidia é pro ao vivo, o parakeet redux é pro
geral. o ao vivo só acontece quando o painel ta aberto. quando ta fechado, o
redux entra, e vira um transcritor LEVE ao contrario do nvidia."*

WHAT THIS PROBE DRIVES, AND WHAT IT DOES NOT. It runs the REAL worker
(`worker/sotto_worker.py`) through the REAL live loop, fed from a FILE
(`SOTTO_FILE_TAP`, lane SottoAsrTap) so that NO audio device is opened and no
global hotkey is registered — there is no shell in this process at all. The
visibility file is written by the REAL writer class from the shipped shell
(`app/webview/sotto_webview.py::PanelVisibilityWriter`, imported headless), driven
exactly as `SottoShell.publish_panel_visibility(reason)` drives it, so the file's
shape and its `PANEL_VISIBILITY_MODE` transition lines are the shipped ones and
not a probe's imitation.

THE BATCH RUNNER: BOTH, AND WHICH ARM USES WHICH. `worker/redux_batch.py` did NOT
exist when this lane started and landed while it was running, so the probe carries
BOTH ends of that fact:

  * `on`   drives `_main/_redux-batch-stub.py`, a stand-in that implements ONLY
           the CLI contract and says so in every line it emits. Nothing fed by it
           may be read as "transcription works"; what it proves is the SWITCH and
           the STAMP.
  * `real` drives the REAL `worker/redux_batch.py` (if it is on disk, which the
           probe states in its own log). That arm is the end-to-end one: real
           Parakeet Redux text through the worker's mode switch.

ARMS, and the two colours the brief asks for:
  off        the flag ABSENT. The control: the run must be exactly today's run —
             streaming chunks, streaming captions, NO `REDUX_*` line, and no
             `reduxCaptions` key on `done`.
  on         the flag PRESENT, with a hidden window longer than
             `--redux-hidden-after`: the transition chain must appear, streaming
             chunks must STOP, batch segments must appear, and every batch line
             must carry `producer:"redux"`.
  missing    the flag present but the runner path does not exist: the HARD RULE —
             the switch must REFUSE and keep streaming.
  stale      the flag present and the file says `visible:false` but is STALE
             (`writtenAtEpoch` older than `staleAfterSeconds`): the worker must
             treat a dead producer's sentence as VISIBLE and keep streaming.

    python _main/_redux-visibility-probe.py            # all four arms
    python _main/_redux-visibility-probe.py --arm on   # one arm
    python _main/_redux-visibility-probe.py --keep     # keep the logs it parsed

Exit 0 when every arm behaves as stated, 1 when an arm moves, 2 on a setup error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
STUB = os.path.join(HERE, "_redux-batch-stub.py")
FAIL_STUB = os.path.join(HERE, "_redux-batch-fail.py")
SHELL_DIR = os.path.join(ROOT, "app", "webview")
SAMPLE = os.path.join(HERE, "pt-br-sample.wav")
OUT_DIR = os.path.join(HERE, "_redux-visibility")
PYTHONW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")

#: CREATE_NO_WINDOW. The house rule: never leave a window on the owner's screen,
#: and a child python.exe launched from a parent with no console OPENS one unless
#: this is passed. The 60 s census would name the pid.
CREATE_NO_WINDOW = 0x08000000

log_lines: list[str] = []
LOG_PATH = os.path.join(HERE, "_redux-visibility-probe.log")


def say(msg: str) -> None:
    # The console this runs in is cp1252 on this box, and the worker's own log
    # lines carry characters it cannot encode — MEASURED: the FIRST run of this
    # probe died with `UnicodeEncodeError: 'charmap' codec can't encode character
    # '\ufffd'` inside `print`, i.e. the instrument crashed while REPORTING a
    # passing arm and took three unrun arms with it. The log file is UTF-8 and
    # always gets the real string; only the console copy is escaped.
    log_lines.append(msg)
    with open(LOG_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(log_lines) + "\n")
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        safe = msg.encode(enc).decode(enc)
    except (UnicodeEncodeError, LookupError, UnicodeDecodeError):
        safe = msg.encode(enc, "replace").decode(enc, "replace")
    print(safe, flush=True)


# ---------------------------------------------------------------------------
# the visibility file: the SHIPPED writer, driven the way the shell drives it
# ---------------------------------------------------------------------------

class VisibilityDriver:
    """The shell's own writer, with a switch the probe can flip.

    `visible=False` is what a HIDDEN panel reads, and the writer's `observe()`
    mirrors `SottoShell.observe_panel_visible()`: the value is read at write
    time, never assumed. `flip(False, 'hotkey')` is the probe's Alt+C.
    """

    def __init__(self, path, initial=True, interval_s=1.0):
        if SHELL_DIR not in sys.path:
            sys.path.insert(0, SHELL_DIR)
        import sotto_webview  # the REAL module; it imports headless

        self.state = {"v": bool(initial)}
        self.transitions: list[str] = []
        self._writer = sotto_webview.PanelVisibilityWriter(
            path=path,
            observe=lambda: self.state["v"],
            log=self._log,
            interval_s=interval_s,
        )

    def _log(self, line):
        if line.startswith("PANEL_VISIBILITY_MODE"):
            self.transitions.append(line)

    def start(self):
        return self._writer.start()

    def flip(self, visible, reason):
        """The transition, as a SHOW/HIDE call publishes it."""
        self.state["v"] = bool(visible)
        return self._writer.write(reason, visible=bool(visible))

    def stop(self):
        self._writer.stop("probe")
        return self._writer


def write_stale_file(path, seconds_old=10.0):
    """A hand-written dump from a shell that is no longer running.

    `writtenAtEpoch` is older than `staleAfterSeconds`, which is the ONLY fact
    that distinguishes "the owner closed the panel" from "the process that said
    so is dead" — the reader must not obey the second one.
    """
    payload = {
        "schema": "sotto.panel-visibility/1",
        "visible": False,
        "since_ms": int((time.time() - seconds_old) * 1000),
        "age_ms": int(seconds_old * 1000),
        "pid": 999999,
        "reason": "hotkey",
        "transitions": 2,
        "writtenAt": "1970-01-01T00:00:00+00:00",
        "writtenAtEpoch": round(time.time() - seconds_old, 3),
        "staleAfterSeconds": 5.0,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


# ---------------------------------------------------------------------------
# running the real worker, no device, no window
# ---------------------------------------------------------------------------

def run_worker(tag, extra_args, visibility_path, seconds, hidden_plan, runner_path,
               vis_mode="driver"):
    """One worker run. Returns the parsed result; never raises on a bad exit.

    `hidden_plan` is a list of `(at_seconds, visible, reason)` applied against
    the worker's OWN start (`t_start`, measured from the boot line, i.e. after
    the model loaded) — a schedule written against wall clock instead would drift
    with the model load, which on this box is seconds.

    `vis_mode` says what the file IS for this arm: `driver` = the shipped writer,
    flipped on a schedule; `stale` = one hand-written dump from a dead shell;
    `none` = no file at all (the flag-off control must not depend on a file
    existing, and leaving a leftover from another arm in the directory is how a
    control gets contaminated).
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{tag}.stdout.jsonl")
    err_path = os.path.join(OUT_DIR, f"{tag}.stderr.log")
    vis_log = os.path.join(OUT_DIR, f"{tag}.visibility.log")

    env = dict(os.environ)
    env["SOTTO_FILE_TAP"] = SAMPLE
    env.pop("SOTTO_CHUNK_TRACE", None)   # leave the shared trace knob alone
    env.pop("SOTTO_REDUX_WAV_DIR", None)
    env.pop("SOTTO_AUDIO_FILE", None)    # SOTTO_FILE_TAP is the live-loop arm

    driver = None
    if visibility_path is not None:
        if os.path.exists(visibility_path):
            os.remove(visibility_path)
        if vis_mode == "driver":
            driver = VisibilityDriver(visibility_path)
        elif vis_mode == "stale":
            write_stale_file(visibility_path, seconds_old=10.0)

    cmd = [sys.executable, WORKER,
           "--max-seconds", str(seconds),
           "--panel-visibility", visibility_path or os.path.join(HERE, "unused.json"),
           "--redux-batch", runner_path,
           "--stats-interval", "4"]
    cmd += extra_args

    t0 = time.time()
    with open(out_path, "w", encoding="utf-8") as out, \
            open(err_path, "w", encoding="utf-8") as er:
        # `pythonw.exe` when it exists: no console, so no window can appear even
        # if CREATE_NO_WINDOW were dropped. Both are set — belt and braces,
        # because a stray console is the one thing the owner has complained about.
        exe = PYTHONW if os.path.exists(PYTHONW) else sys.executable
        proc = subprocess.Popen([exe] + cmd[1:], cwd=ROOT, env=env,
                                stdout=out, stderr=er,
                                creationflags=CREATE_NO_WINDOW)

        # The schedule is applied in WALL time, and the worker's own `t_start`
        # is the moment the FIRST `capture-started` lands (model loaded, tap
        # open). Waiting for it removes the model-load variance instead of
        # guessing a constant.
        started = None
        while time.time() - t0 < 240:
            txt = read_text(err_path) + read_text(out_path)
            if "capture-started" in txt:
                started = time.time()
                break
            if proc.poll() is not None:
                break
            time.sleep(0.2)

        if driver is not None and started is not None:
            driver.start()
            for at, visible, reason in hidden_plan:
                while time.time() - started < at:
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)
                if proc.poll() is not None:
                    break
                driver.flip(visible, reason)
        rc = proc.wait(timeout=240)

    transitions = []
    writer = None
    if driver is not None:
        transitions = list(driver.transitions)
        writer = driver.stop()

    result = {
        "tag": tag,
        "rc": rc,
        "wall_s": round(time.time() - t0, 2),
        "stdout": read_text(out_path),
        "stderr": read_text(err_path),
        "transitions": transitions,
        "events": [],
        "captions": [],
        "redux_lines": [],
        "visibility": None,
        "out_path": out_path,
        "err_path": err_path,
        "vis_log": vis_log,
    }
    if writer is not None:
        result["visibility"] = {
            "writes": writer.writes,
            "transitions": writer.transitions,
            "errors": writer.errors,
        }
        with open(vis_log, "w", encoding="utf-8") as fh:
            fh.write("\n".join(transitions) + "\n")
    for line in result["stdout"].splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        result["events"].append(payload)
        if payload.get("type") == "caption":
            result["captions"].append(payload)
            if payload.get("producer") == "redux":
                result["redux_lines"].append(payload)
    return result


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def grep(text, needle):
    return [ln for ln in text.splitlines() if needle in ln]


#: How many batch kicks each arm's hidden window may legitimately produce:
#: ceil(hidden_s / interval) + 1 for the tail. Counted from the arm's OWN numbers
#: so that changing a window without changing this table is visible, not silent.
MAX_KICKS = {"on": 5, "real": 4}


def interval_of(extra):
    if "--redux-batch-interval" not in extra:
        return 0.0
    try:
        return float(extra[extra.index("--redux-batch-interval") + 1])
    except (IndexError, ValueError):
        return 0.0


def max_kicks_of(tag):
    return MAX_KICKS.get(tag, 0)


def done_of(res):
    for ev in res["events"]:
        if ev.get("type") == "status" and ev.get("state") == "done":
            return ev
    return {}


def streaming_chunks_before_switch(res):
    """Chunks cut before the first `REDUX_MODE mode=batch` line.

    The count is taken from `WORKER_STATS` ticks, so it is the worker's OWN
    number and not the probe's arithmetic on the log's shape.
    """
    for line in grep(res["stderr"], "REDUX_MODE mode=batch")[:1]:
        return line
    return None


def report_arm(name, res, expected, failures, batch_interval_s=0.0, max_kicks=0):
    err = res["stderr"]
    done = done_of(res)
    modes = grep(err, "REDUX_MODE mode=")
    batch_modes = grep(err, "REDUX_MODE mode=batch")
    stream_modes = grep(err, "REDUX_MODE mode=stream")
    kicks = grep(err, "REDUX_BATCH_KICK")
    finished = grep(err, "REDUX_BATCH_DONE")
    refused = grep(err, "REDUX_SWITCH_REFUSED")
    vis = grep(err, "REDUX_VISIBILITY")
    problems = []

    if res["rc"] != 0:
        # An exit of 3 is the worker's own honest "silent device" verdict; a file
        # tap with real speech must not produce one, so anything non-zero here is
        # a real signal and is reported rather than swallowed.
        problems.append(f"rc={res['rc']} (expected 0)")

    if expected == "off":
        if modes or refused or kicks:
            problems.append(f"flag OFF produced REDUX_* lines: "
                            f"{len(modes)} mode / {len(kicks)} kick")
        if "reduxCaptions" in done:
            problems.append("flag OFF carried reduxCaptions on `done`")
        if done.get("chunks", 0) <= 0:
            problems.append("flag OFF cut no streaming chunks")
        if not res["captions"]:
            problems.append("flag OFF emitted no caption")
        if res["redux_lines"]:
            problems.append(f"flag OFF emitted {len(res['redux_lines'])} redux lines")

    elif expected == "on":
        if not vis:
            problems.append("no REDUX_VISIBILITY line — the file was never read")
        if not batch_modes:
            problems.append("never entered batch mode")
        if not stream_modes:
            problems.append("never came back to streaming")
        if not kicks:
            problems.append("no REDUX_BATCH_KICK — the accumulated audio was never batched")
        if not finished:
            problems.append("no REDUX_BATCH_DONE — the runner never answered")
        if not res["redux_lines"]:
            problems.append("no caption carried producer:'redux'")
        for line in res["redux_lines"]:
            if line.get("final") is not True:
                problems.append(f"redux line without final:true: {line.get('text')!r}")
                break
        if done.get("reduxCaptions") != len(res["redux_lines"]):
            problems.append(
                f"done.reduxCaptions={done.get('reduxCaptions')} but "
                f"{len(res['redux_lines'])} redux lines were on stdout")
        if done.get("reduxArmed") is not True:
            problems.append("done.reduxArmed is not true")
        if done.get("verdict") != "captions-emitted":
            problems.append(f"done.verdict={done.get('verdict')!r} "
                            f"(a batch run must not be verdicted a failure word)")
        # The runner's OWN non-caption lines must not reach the worker's stdout:
        # the real engine prints a `{"type":"result"}` summary, and a switch that
        # passed it through would inject a bogus line into the JSONL contract.
        if any(ev.get("type") == "result" for ev in res["events"]):
            problems.append("a runner `result` line leaked onto the worker's stdout")
        # THE CADENCE IS CHECKED, NOT TRUSTED. The first version of the switch
        # kicked a batch every time ONE SECOND of audio had accumulated — twelve
        # invocations for a sixteen-second hidden window, i.e. a queue of model
        # loads, which is the opposite of the "transcritor LEVE" the owner asked
        # for. The count alone would not have caught it (twelve is a number), so
        # the check below is on the INTERVAL kicks' own `audio_s=`, which must
        # reach the configured interval.
        interval_kicks = []
        for line in kicks:
            if "reason=interval" in line:
                found = re.search(r'audio_s=([0-9.]+)', line)
                interval_kicks.append(float(found.group(1)) if found else 0.0)
        if batch_interval_s and interval_kicks:
            thin = [s for s in interval_kicks if s < batch_interval_s - 0.6]
            if thin:
                problems.append(
                    f"{len(thin)} interval kick(s) fired with less audio than the "
                    f"configured interval ({batch_interval_s}s): {thin} — the light "
                    f"path is a queue of model loads, not a batch cadence")
        if max_kicks and len(kicks) > max_kicks:
            problems.append(
                f"{len(kicks)} batch kicks for this window (max {max_kicks}) — the "
                f"interval floor is not being applied")
        # THE STOPPING HALF: the light path must actually have stopped cutting
        # chunks. Proved by the batch window closing the stream, not by a guess.
        if done.get("chunks", 0) <= 0:
            problems.append("no streaming chunk was ever cut (the visible arm)")

    elif expected == "missing":
        if not refused:
            problems.append("runner missing but NO REDUX_SWITCH_REFUSED line")
        if batch_modes:
            problems.append("runner missing but the worker ENTERED batch mode")
        if kicks:
            problems.append("runner missing but a batch was kicked")
        if done.get("reduxArmed") is not False:
            problems.append(f"done.reduxArmed={done.get('reduxArmed')!r} (expected false)")
        if res["rc"] != 0:
            problems.append(f"rc={res['rc']}")
        if not res["captions"]:
            problems.append("refused switch left the run with no streaming caption")

    elif expected == "stale":
        if batch_modes:
            problems.append("a STALE file put the worker into batch mode")
        if vis:
            problems.append("a stale dump was read as fresh")
        if not res["captions"]:
            problems.append("stale arm emitted no streaming caption")
        if "reduxCaptions" not in done:
            problems.append("stale arm ran without the flag's done fields")

    elif expected == "fail":
        # The runner refuses. The worker must report the pass it LOST, count it,
        # and print the stderr it captured — an `lines=0` with no cause is the
        # silent failure this arm exists to rule out.
        if not batch_modes:
            problems.append("fail arm never entered batch mode")
        if not finished:
            problems.append("fail arm: the runner returned but REDUX_BATCH_DONE is absent")
        for line in finished:
            if "rc=4" not in line:
                problems.append(f"fail arm: {line!r} does not carry the runner's rc")
                break
        if not grep(err, "REDUX_BATCH_FAILED reason=runner-rc"):
            problems.append("fail arm: a non-zero runner rc was NOT counted/named "
                            "as a failure")
        tail = grep(err, "REDUX_BATCH_FAILED reason=runner-rc")
        if tail and "DELIBERATE FAILURE" not in tail[0]:
            problems.append("fail arm: the runner's captured stderr tail was not printed")
        empty = [ev for ev in res["events"]
                 if ev.get("type") == "status" and ev.get("state") == "redux-batch-empty"]
        if not empty:
            problems.append("fail arm: a batch that produced no caption did not emit "
                            "redux-batch-empty — silence was not stated")
        if done.get("reduxRunnerFailures", 0) < 1:
            problems.append(f"fail arm: done.reduxRunnerFailures="
                            f"{done.get('reduxRunnerFailures')} (expected >= 1)")
        if not res["captions"] and not res["redux_lines"]:
            problems.append("fail arm: the run emitted nothing at all — the streaming "
                            "side must be unaffected by a batch failure")

    elif expected == "throttle":
        # Under the floor, every INTERVAL pass must be deferred and no interval
        # kick may happen; the TAIL must still attempt, because a tail deferred is
        # a tail dropped.
        if not grep(err, "REDUX_BATCH_DEFERRED reason=low-memory"):
            problems.append("throttle arm: low memory did NOT defer the interval pass")
        # THE DEFERRAL LOG IS RATE-LIMITED, and a deferral that logs per block is
        # a log nobody can read: MEASURED, the first version wrote 90 lines in
        # 13 s (~36 000/hour) on the exact path where nobody is watching. The
        # COUNT must stay exact while the prose stays thin — so both are checked.
        deferrals = grep(err, "REDUX_BATCH_DEFERRED")
        if len(deferrals) > 6:
            problems.append(f"throttle arm: {len(deferrals)} deferral lines — the "
                            f"rate limit is missing or broken (<= 6 expected for this "
                            f"window)")
        if len(deferrals) < 3:
            problems.append(f"throttle arm: only {len(deferrals)} deferral lines — the "
                            f"first few must always be said")
        interval_kicks = [k for k in kicks if "reason=interval" in k]
        if interval_kicks:
            problems.append(f"throttle arm: {len(interval_kicks)} interval kick(s) ran "
                            f"under the memory floor")
        tail_kicks = [k for k in kicks if "reason=stream-end" in k or "visible-again" in k]
        if not tail_kicks:
            problems.append("throttle arm: the TAIL did not attempt — a tail cannot be "
                            "deferred, so this is lost audio")
        if not grep(err, "REDUX_BATCH_LOW_MEMORY"):
            problems.append("throttle arm: the tail ran under pressure WITHOUT saying so")
        if done.get("reduxBatchDeferred", 0) < 1:
            problems.append(f"throttle arm: done.reduxBatchDeferred="
                            f"{done.get('reduxBatchDeferred')} (expected >= 1)")
        if not res["captions"]:
            problems.append("throttle arm: the streaming side stopped while deferred")

    say(f"ARM {name:8s} rc={res['rc']:<3} wall={res['wall_s']:>6}s "
        f"mode_lines={len(modes)} batch={len(batch_modes)} stream={len(stream_modes)} "
        f"kicks={len(kicks)} done_lines={len(finished)} "
        f"redux_captions={len(res['redux_lines'])} "
        f"stream_captions={len(res['captions']) - len(res['redux_lines'])} "
        f"chunks={done.get('chunks')} verdict={done.get('verdict')!r} "
        f"reduxSegments={done.get('reduxSegments')} "
        f"reduxSwitches={done.get('reduxSwitches')}")
    for line in vis + modes + [f"  {k}" for k in kicks] + [f"  {f}" for f in finished] + refused:
        say(f"    {line}")
    for line in res["transitions"]:
        say(f"    shell-writer: {line}")
    if res["redux_lines"]:
        for line in res["redux_lines"][:4]:
            say(f"    REDUX LINE producer={line.get('producer')!r} "
                f"final={line.get('final')!r} start={line.get('start')} "
                f"text={line.get('text')!r}")
    if problems:
        for p in problems:
            say(f"    !! {p}")
            failures.append(f"{name}: {p}")
    else:
        say(f"ARM {name:8s} VERDICT PASS")
    return len(problems) == 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="redux-visibility-probe")
    ap.add_argument("--arm", default="all",
                    choices=("all", "off", "on", "real", "missing", "stale", "fail",
                             "throttle"))
    ap.add_argument("--seconds", type=float, default=0.0,
                    help="override the per-arm wall clock")
    ap.add_argument("--keep", action="store_true",
                    help="keep the per-arm logs (they are kept by default; this is a no-op)")
    args = ap.parse_args()

    if not os.path.exists(SAMPLE):
        say(f"SETUP ERROR: no sample audio at {SAMPLE}")
        return 2
    if not os.path.exists(WORKER):
        say(f"SETUP ERROR: no worker at {WORKER}")
        return 2

    worker_stat = os.stat(WORKER)
    shell_path = os.path.join(SHELL_DIR, "sotto_webview.py")
    say(f"PROBE redux-visibility  worker={WORKER} "
        f"({worker_stat.st_size} B, mtime {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(worker_stat.st_mtime))})")
    say(f"PROBE sample={os.path.basename(SAMPLE)} python={sys.executable} "
        f"pythonw={'yes' if os.path.exists(PYTHONW) else 'NO (a console may appear)'}")
    say(f"PROBE runner(stub)={STUB}  the REAL worker/redux_batch.py exists: "
        f"{os.path.exists(os.path.join(ROOT, 'worker', 'redux_batch.py'))} "
        f"— arms `off`/`on`/`missing`/`stale` drive the STUB; arm `real` drives "
        f"the real engine")
    say("")

    failures: list[str] = []
    os.makedirs(OUT_DIR, exist_ok=True)
    # One file per arm: a probe that reuses one path cannot show WHICH arm's
    # transition it read, and two arms against one file is how a stale read
    # becomes a false PASS.
    vis_off = os.path.join(OUT_DIR, "vis-off.json")
    vis_on = os.path.join(OUT_DIR, "vis-on.json")
    vis_real = os.path.join(OUT_DIR, "vis-real.json")
    vis_missing = os.path.join(OUT_DIR, "vis-missing.json")
    vis_stale = os.path.join(OUT_DIR, "vis-stale.json")
    vis_fail = os.path.join(OUT_DIR, "vis-fail.json")
    vis_throttle = os.path.join(OUT_DIR, "vis-throttle.json")
    for p in (vis_off, vis_on, vis_real, vis_missing, vis_stale, vis_fail,
              vis_throttle):
        if os.path.exists(p):
            os.remove(p)

    arms: list[tuple[str, list[str], str, float, list, str, str]] = [
        # tag, args, expected, seconds, hidden_plan, runner_path, vis_mode
        ("off", [], "off", 14.0, None, STUB, "none"),
        ("on", ["--redux-when-hidden", "--redux-hidden-after", "4",
                "--redux-batch-interval", "5"],
         "on", 34.0,
         [(6.0, False, "hotkey"),                  # Alt+C: the panel goes away
          (6.0 + 16.0, True, "hotkey")],           # Alt+C again: it comes back
         STUB, "driver"),
        # THE SAME SWITCH, THE REAL ENGINE. `worker/redux_batch.py` landed while
        # this lane was running, so the light path is exercised end to end here:
        # real Parakeet Redux text, its OWN `producer:'redux'`, through the
        # worker's mode switch. The stub arm above stays because it is the only
        # one that can drive a NON-ZERO runner rc and a silent batch.
        #
        # THE CADENCE IS 10 s AND THE WINDOW 24 s ON PURPOSE. The real runner's
        # own log carries `LOADED` + per-invocation wall time, and a cadence BELOW
        # that wall time makes the in-flight guard refuse every later kick, so the
        # pass stops being interval-shaped — MEASURED on the first run of this
        # arm at `--redux-batch-interval 6`: the first invocation took 11.48 s of
        # wall for 1.0 s of audio, and the whole hidden window produced ONE
        # interval pass plus one tail. That is a fact about the runner's cost, and
        # it is reported rather than tuned away: at the DEFAULT interval (15 s) it
        # fits; the numbers below are what says so.
        ("real", ["--redux-when-hidden", "--redux-hidden-after", "4",
                  "--redux-batch-interval", "10"],
         "on", 46.0,
         [(6.0, False, "hotkey"),
          (6.0 + 24.0, True, "hotkey")],
         os.path.join(ROOT, "worker", "redux_batch.py"), "driver"),
        ("missing", ["--redux-when-hidden", "--redux-hidden-after", "2"],
         "missing", 14.0,
         [(6.0, False, "hotkey")],
         os.path.join(HERE, "_redux-batch-DOES-NOT-EXIST.py"), "driver"),
        ("stale", ["--redux-when-hidden", "--redux-hidden-after", "2"],
         "stale", 14.0,
         None,   # a hand-written, stale dump is placed instead
         STUB, "stale"),
        # THE FAILURE ARM. A runner that exits non-zero is the ONE case a passing
        # engine cannot exercise, and it is where a silent failure would live: the
        # runner's stderr is captured, so unless the worker logs it, a refusal
        # looks exactly like silence. This arm requires the worker to say the pass
        # happened, to COUNT it as a failure, and to print the tail.
        ("fail", ["--redux-when-hidden", "--redux-hidden-after", "2",
                  "--redux-batch-interval", "4"],
         "fail", 20.0,
         [(5.0, False, "hotkey")],
         FAIL_STUB, "driver"),
        # THE MEMORY GATE. `--redux-min-free-mb` set absurdly high is the only way
        # to drive the pressure branch on a box that has the RAM: the interval
        # passes must be DEFERRED (loudly, with the audio kept) while the TAIL —
        # which has no next tick — attempts anyway and says so.
        ("throttle", ["--redux-when-hidden", "--redux-hidden-after", "2",
                      "--redux-batch-interval", "4",
                      "--redux-min-free-mb", "999999"],
         "throttle", 20.0,
         [(5.0, False, "hotkey")],
         STUB, "driver"),
    ]

    wanted = [a for a in arms if args.arm in ("all", a[0])]
    for tag, extra, expected, seconds, plan, runner_path, vis_mode in wanted:
        if args.seconds:
            seconds = args.seconds
        vis = {"off": vis_off, "on": vis_on, "missing": vis_missing,
               "stale": vis_stale, "real": vis_real, "fail": vis_fail,
               "throttle": vis_throttle}[tag]
        say(f"--- ARM {tag}: seconds={seconds} plan={plan} "
            f"runner={os.path.relpath(runner_path, ROOT)} "
            f"exists={os.path.exists(runner_path)} "
            f"visibility={os.path.basename(vis)} vis_mode={vis_mode}")
        res = run_worker(tag, extra, vis, seconds, plan, runner_path=runner_path,
                         vis_mode=vis_mode)
        report_arm(tag, res, expected, failures, batch_interval_s=interval_of(extra),
                   max_kicks=max_kicks_of(tag))
        say(f"    log: {res['out_path']} | {res['err_path']}")

    say("")
    if failures:
        say(f"VERDICT: RED — {len(failures)} arm(s) moved: " + "; ".join(failures[:4]))
        return 1
    say(f"VERDICT: PASS — {len(wanted)}/{len(wanted)} arm(s). "
        f"Flag OFF is today's run; flag ON switches on the SAME file the shell writes; "
        f"a missing runner and a stale dump both REFUSE to cut the streaming capture.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
