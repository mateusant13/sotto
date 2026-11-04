"""THE CONTROLLED ARM: a REAL shed -> resume -> drain cycle, with REAL speech.

WHY THIS ARM EXISTS. The LIVE records (`H:\sotto\_main\webview-run.log`) show
43 runs that carried the background engine's counters -- and EVERY ONE of them
was a run whose device was SILENT (`nonzero_blocks` 0-2, `peak=0.000122`,
`music_gated_chunks` == every chunk). The background engine ran 25 passes over
that silence and produced ZERO lines. So the live log CANNOT answer the drain
question in either direction: there is no run in it where speech was held by
the load-shedder and then transcribed.

This arm supplies the missing run, WITHOUT touching the owner's screen:
  * the audio comes from a FILE (`SOTTO_FILE_TAP`), so no device is opened;
  * the worker runs with `--redux-when-hidden`, so the mode switch is live;
  * the visibility/shed file is a PRIVATE one (`--panel-visibility`), so the
    live shell's own file is never touched and the single-instance lock is
    irrelevant (this is a WORKER, not a shell: no window, no tray, no Alt+C);
  * the file carries a REAL speech sample, so the parakeet has something to
    say.

THE SEQUENCE (the claim's own scenario, and the claim's OWN words):
  1. `shed: muito-alta` -> mode=shed: NOTHING is transcribed, the audio
     accumulates in `PendingAudio` (RAM -> disk spool, lossless).
  2. THE LOAD FREES -> the level drops to `leve` (the panel stays hidden, so
     the mode becomes `batch`) -> the background engine (parakeet) must
     transcribe EVERYTHING that accumulated.
  3. the difference IN - OUT - WAIT must be ZERO (minus the sub-chunk partial).

THE FLIP IS TRIGGERED BY THE WORKER'S OWN SIGNAL, not by a wall-clock guess:
the harness watches the worker's stderr for `REDUX_MODE mode=shed` and only
then starts the dwell. (The first version flipped on a timer and the flip
landed BEFORE the model finished loading, so the mode never entered `shed` at
all -- an arm that measured nothing while looking like it measured something.)

EVERYTHING is written to disk by the worker itself: `REDUX_*` lines on stderr,
`WORKER_STATS` on stderr, the caption lines on stdout. This harness does not
recompute anything the worker already publishes -- it ASSEMBLES the sets from
those published facts and does its own subtraction.

Read-only against the repo. It writes only under `_falsify_drain/arm/`.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"H:\sotto"
ARM = os.path.join(HERE, "arm")
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
VIS_PATH = os.path.join(ARM, "panel-visibility.json")
SPOOL = os.path.join(ARM, "spool")

#: The real speech sample (pt-BR, 15 s, peak 0.58) -- the repo's own fixture.
SAMPLE = os.path.join(ROOT, "_main", "pt-br-sample.wav")


def write_visibility(visible: bool, shed: str = "leve", age_ms: int = 60000):
    """The PRIVATE visibility file the worker polls."""
    now = time.time()
    payload = {
        "schema": "sotto.panel-visibility/1",
        "visible": bool(visible),
        "since_ms": int((now - age_ms / 1000.0) * 1000),
        "age_ms": int(age_ms),
        "pid": os.getpid(),
        "reason": "arm",
        "transitions": 1,
        "writtenAt": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "writtenAtEpoch": now,
        "staleAfterSeconds": 3600.0,
        "shed": shed,
    }
    tmp = VIS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    os.replace(tmp, VIS_PATH)
    return payload


def run_worker(duration_s, shed="muito-alta", visible=False, label="arm",
               env_extra=None, flip_when=None, dwell_s=0.0,
               flip_to=None, max_audio_s=120.0):
    """One worker run against the FILE tap.

    `flip_when`   -- a substring of a worker stderr line that must appear
                     before the flip is allowed to happen (e.g.
                     "REDUX_MODE mode=shed"). The flip is then `dwell_s`
                     seconds later.
    `flip_to`     -- the (visible, shed) to write at the flip. None = no flip.

    Returns a dict with everything the worker published.
    """
    os.makedirs(ARM, exist_ok=True)
    write_visibility(visible=visible, shed=shed)

    env = dict(os.environ)
    env["SOTTO_FILE_TAP"] = SAMPLE
    env["SOTTO_REDUX_WHEN_HIDDEN"] = "1"
    env["SOTTO_REDUX_SPOOL_DIR"] = SPOOL
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("SOTTO_LOAD_SHED", None)
    if env_extra:
        env.update(env_extra)

    cmd = [sys.executable, WORKER,
           "--redux-when-hidden",
           "--panel-visibility", VIS_PATH,
           "--redux-hidden-after", "1.0",
           "--redux-batch-interval", "3.0",
           "--redux-max-audio", str(max_audio_s),
           "--meter-hz", "0",
           "--stats-interval", "2.0",
           "--max-seconds", str(duration_s)]
    out_path = os.path.join(ARM, "%s.stdout.jsonl" % label)
    err_path = os.path.join(ARM, "%s.stderr.log" % label)
    out_fh = open(out_path, "w", encoding="utf-8", errors="replace")
    err_fh = open(err_path, "w", encoding="utf-8", errors="replace")

    flags = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW

    proc = subprocess.Popen(cmd, cwd=os.path.join(ROOT, "worker"),
                            stdout=out_fh, stderr=err_fh, stdin=subprocess.DEVNULL,
                            env=env, creationflags=flags, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))

    state = {"flip_at": None, "flipped": None, "signal_at": None}

    def watcher():
        """Read the worker's stderr live; fire the flip when told to."""
        if flip_when is None or flip_to is None:
            return
        seen = False
        deadline = time.time() + duration_s + 120
        with open(err_path, "r", encoding="utf-8", errors="replace") as fh:
            while time.time() < deadline:
                line = fh.readline()
                if not line:
                    if proc.poll() is not None:
                        return
                    time.sleep(0.05)
                    continue
                if not seen and flip_when in line:
                    seen = True
                    state["signal_at"] = time.time()
                    time.sleep(dwell_s)
                    write_visibility(visible=flip_to[0], shed=flip_to[1])
                    state["flip_at"] = time.time()
                    state["flipped"] = flip_to
    threading.Thread(target=watcher, daemon=True).start()

    rc = proc.wait(timeout=duration_s + 240)
    out_fh.close()
    err_fh.close()

    stdout_lines = []
    with open(out_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                stdout_lines.append(json.loads(line))
            except ValueError:
                pass
    stderr_text = open(err_path, "r", encoding="utf-8", errors="replace").read()
    stderr_lines = stderr_text.splitlines()

    return {
        "label": label,
        "rc": rc,
        "cmd": cmd,
        "stdout": stdout_lines,
        "stderr_lines": stderr_lines,
        "flip_when": flip_when,
        "dwell_s": dwell_s,
        "flip_to": flip_to,
        "signal_at": state["signal_at"],
        "flip_at": state["flip_at"],
        "started_at": None,
    }


def report(arm):
    """Print the arm's own published facts."""
    print("label          :", arm["label"])
    print("rc             :", arm["rc"])
    print("flip_when      :", arm["flip_when"], " dwell_s:", arm["dwell_s"],
          " flip_to:", arm["flip_to"])
    print()
    print("-- the worker's REDUX lines (its own words) --")
    for line in arm["stderr_lines"]:
        if line.startswith("REDUX_"):
            print("   ", line[:400])
    print()
    print("-- the worker's FINAL WORKER_STATS --")
    finals = [l for l in arm["stderr_lines"] if l.startswith("WORKER_STATS tag=final")]
    for l in finals:
        print("   ", l)
    print()
    captions = [m for m in arm["stdout"] if m.get("type") == "caption"]
    print("-- stdout caption lines: %d --" % len(captions))
    for c in captions:
        print("    %-58s start=%-7s end=%-7s route=%-12s producer=%s" % (
            str(c.get("text"))[:58], c.get("start"), c.get("end"),
            c.get("route"), c.get("producer")))
    print()


ARMS = {
    # ARM 1 -- THE CLAIM'S SCENARIO: shed (muito-alta), then the load frees.
    "arm1_shed_then_free": dict(
        duration_s=60, shed="muito-alta", visible=False,
        label="arm1_shed_then_free",
        flip_when="REDUX_MODE mode=shed", dwell_s=10.0,
        flip_to=(False, "leve")),
    # ARM 2 -- NEGATIVE CONTROL FOR THE HARNESS: the load NEVER frees. The
    # audio must still be HELD at the end (left_s > 0); if it were 0 here,
    # ARM 1's zero would be vacuous.
    "arm2_never_frees": dict(
        duration_s=26, shed="muito-alta", visible=False,
        label="arm2_never_frees", flip_when=None, flip_to=None),
    # ARM 4 -- THE DISK-SPOOL PATH. ARM 1 held the backlog in RAM (120 s cap).
    # This one sets `--redux-max-audio 4` so the backlog MUST spill to the disk
    # spool (`PendingAudio._spill_locked`) -- the path where a drop could
    # plausibly happen (a full disk, a write failure). Then the load frees and
    # the parakeet must transcribe the whole backlog, RAM and spool alike.
    "arm4_disk_spool": dict(
        duration_s=60, shed="muito-alta", visible=False,
        label="arm4_disk_spool",
        flip_when="REDUX_MODE mode=shed", dwell_s=10.0,
        flip_to=(False, "leve"),
        max_audio_s=4.0),
    # ARM 3 -- POSITIVE CONTROL: nothing is ever shed (leve + visible). Every
    # chunk in == every chunk out, through the STREAMING engine.
    "arm3_never_shed": dict(
        duration_s=26, shed="leve", visible=True,
        label="arm3_never_shed", flip_when=None, flip_to=None),
}


def main():
    os.makedirs(ARM, exist_ok=True)
    if os.path.isdir(SPOOL):
        shutil.rmtree(SPOOL, ignore_errors=True)
    only = sys.argv[1:] or list(ARMS)
    results = {}
    for key in only:
        spec = dict(ARMS[key])
        print("=" * 78)
        print("ARM:", key, "--", spec.get("label"))
        print("=" * 78)
        arm = run_worker(**spec)
        report(arm)
        results[key] = arm
    with open(os.path.join(ARM, "arms.json"), "w", encoding="utf-8") as fh:
        json.dump({k: {kk: vv for kk, vv in v.items()
                       if kk not in ("stdout", "stderr_lines")}
                   for k, v in results.items()}, fh, indent=1, default=str)
    return results


if __name__ == "__main__":
    main()
