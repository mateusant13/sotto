"""ARM 5 -- THE "RECARREGA SOZINHO" CYCLE: release, then reload, by itself.

THE CLAIM has TWO halves and the first arm only exercised the second:

  (a) "quando a carga liberar, o Sotto RECARREGA SOZINHO"
      -- when the load is released, the model RELOADS BY ITSELF.
  (b) "e processa QUALQUER audio nao processado, com o parakeet"
      -- and processes ANY unprocessed audio, with the parakeet.

ARM 1 (shed -> free) showed (b) and showed the FIRST load (the parakeet was
never loaded before the load freed -- `REDUX_ENGINE_LOAD` appears only after
`REDUX_SHEDDING level=leve`). But it never showed a RELEASE followed by a
RELOAD: the engine stayed loaded until the stop.

ARM 5 is the cycle that needs both halves at once:

    muito-alta  ->  leve  ->  muito-alta  ->  leve

  1. `muito-alta`: nothing runs; the audio accumulates.
  2. `leve`: the batch pass starts, the parakeet LOADS ITSELF
     (`REDUX_ENGINE_LOAD`) and drains what accumulated.
  3. `muito-alta` again: the load is back, so the engine is RELEASED
     (`REDUX_ENGINE_RELEASE`) and the audio accumulates again.
  4. `leve` again: the parakeet LOADS ITSELF A SECOND TIME and drains the
     SECOND backlog.

The counters that answer the claim, all the worker's own:
  REDUX_ENGINE_LOAD     -- the reload happened, by itself
  REDUX_ENGINE_RELEASE  -- the release happened when the load came back
  REDUX_ENGINE_DONE     -- what each pass transcribed
  reduxAudioIn/Out      -- the pending-audio ledger (`done` payload)
  reduxAudioDropped     -- must be 0

Same discipline as ARM 1: a FILE tap (no device), a PRIVATE visibility file
(the live shell's file is never touched), audio MUTED, no window, no tray.
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
SAMPLE = os.path.join(ROOT, "_main", "pt-br-sample.wav")


def write_visibility(visible: bool, shed: str = "leve", age_ms: int = 60000):
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


def run_cycle(duration_s=120, label="arm5_release_reload"):
    """muito-alta -> leve -> muito-alta -> leve, each step gated on the
    worker's OWN signal for that step."""
    os.makedirs(ARM, exist_ok=True)
    write_visibility(visible=False, shed="muito-alta")

    env = dict(os.environ)
    env["SOTTO_FILE_TAP"] = SAMPLE
    env["SOTTO_REDUX_WHEN_HIDDEN"] = "1"
    env["SOTTO_REDUX_SPOOL_DIR"] = SPOOL
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("SOTTO_LOAD_SHED", None)

    cmd = [sys.executable, WORKER,
           "--redux-when-hidden",
           "--panel-visibility", VIS_PATH,
           "--redux-hidden-after", "1.0",
           "--redux-batch-interval", "3.0",
           "--redux-max-audio", "120.0",
           "--meter-hz", "0",
           "--stats-interval", "2.0",
           "--max-seconds", str(duration_s)]
    out_path = os.path.join(ARM, "%s.stdout.jsonl" % label)
    err_path = os.path.join(ARM, "%s.stderr.log" % label)
    out_fh = open(out_path, "w", encoding="utf-8", errors="replace")
    err_fh = open(err_path, "w", encoding="utf-8", errors="replace")
    flags = 0x08000000 if os.name == "nt" else 0
    proc = subprocess.Popen(cmd, cwd=os.path.join(ROOT, "worker"),
                            stdout=out_fh, stderr=err_fh, stdin=subprocess.DEVNULL,
                            env=env, creationflags=flags)

    # THE CYCLE, each step waiting for the worker's own signal.
    steps = [
        # (signal to wait for, dwell after it, (visible, shed) to write)
        ("REDUX_MODE mode=shed", 8.0, (False, "leve")),        # step 2
        ("REDUX_ENGINE_LOAD", 8.0, (False, "muito-alta")),      # step 3
        ("REDUX_MODE mode=shed", 8.0, (False, "leve")),         # step 4
    ]
    log = []

    def watcher():
        pending = list(steps)
        deadline = time.time() + duration_s + 180
        with open(err_path, "r", encoding="utf-8", errors="replace") as fh:
            while pending and time.time() < deadline:
                line = fh.readline()
                if not line:
                    if proc.poll() is not None:
                        return
                    time.sleep(0.05)
                    continue
                sig, dwell, target = pending[0]
                if sig in line:
                    pending.pop(0)
                    time.sleep(dwell)
                    write_visibility(visible=target[0], shed=target[1])
                    log.append((sig, target, time.time()))
    threading.Thread(target=watcher, daemon=True).start()

    rc = proc.wait(timeout=duration_s + 240)
    out_fh.close()
    err_fh.close()
    return {"label": label, "rc": rc, "steps": log}


def main():
    os.makedirs(ARM, exist_ok=True)
    if os.path.isdir(SPOOL):
        shutil.rmtree(SPOOL, ignore_errors=True)
    print("=" * 78)
    print("ARM 5 -- release -> SELF-RELOAD -> drain, twice")
    print("=" * 78)
    out = run_cycle()
    print("rc:", out["rc"], " steps:", out["steps"])
    err = os.path.join(ARM, "%s.stderr.log" % out["label"])
    for line in open(err, "r", encoding="utf-8", errors="replace"):
        line = line.rstrip()
        if line.startswith(("REDUX_", "WORKER_STATS tag=final")):
            print("   ", line[:300])
    print()
    print("-- stdout parakeet lines --")
    op = os.path.join(ARM, "%s.stdout.jsonl" % out["label"])
    n = 0
    for line in open(op, "r", encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
        except ValueError:
            continue
        if m.get("type") == "caption":
            n += 1
            print("    %-56s start=%-7s end=%-7s route=%s" % (
                str(m.get("text"))[:56], m.get("start"), m.get("end"),
                m.get("route")))
        elif m.get("type") == "status" and m.get("state") == "done":
            print("-- done payload (the pending-audio ledger) --")
            for k in sorted(m):
                if k.startswith("redux") or k in ("captions", "audio_s", "verdict", "rotations"):
                    print("    %-26s %s" % (k, m[k]))
    print("   caption lines:", n)


if __name__ == "__main__":
    main()
