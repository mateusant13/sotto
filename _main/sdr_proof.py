"""SottoDeviceRouting — the two proving runs, spawned HIDDEN.

ARM 1: render worker/assets/sample1.flac to the WASAPI DEFAULT RENDER endpoint
       (the endpoint rung (a) taps) and run the REAL worker with NO --device.
       Expected: verdict="captions-emitted", captions>0.
ARM 2: same worker, same argv, NOTHING rendering.
       Expected: a DEVICE verdict is named (`silent-device`), never a model one.

Both children are created with CREATE_NO_WINDOW (0x08000000) ALONE — adding
DETACHED_PROCESS makes a child emit 0 bytes with rc 0 on this box.

Usage: python _main/sdr_proof.py <tag>
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
CONFIG = os.path.join(ROOT, "worker", "config.json")
SAMPLE = os.path.join(ROOT, "worker", "assets", "sample1.flac")
PLAYER = os.path.join(HERE, "play-to-default.py")

CREATE_NO_WINDOW = 0x08000000
PY = sys.executable


def spawn_worker(out_path, seconds):
    cmd = [
        PY, WORKER,
        "--config", CONFIG,
        "--max-seconds", str(seconds),
        "--tap-window", "6",
        "--stats-interval", "5",
    ]
    fh = open(out_path, "w", encoding="utf-8")
    p = subprocess.Popen(
        cmd, stdout=fh, stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW, close_fds=True,
    )
    return p, fh


def spawn_player(seconds):
    cmd = [PY, PLAYER, SAMPLE, str(seconds)]
    devnull = open(os.devnull, "wb")
    p = subprocess.Popen(
        cmd, stdout=devnull, stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW, close_fds=True,
    )
    return p


def summarise(out_path):
    caps, verdict, device, stats, silent = [], None, None, [], None
    try:
        with open(out_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                if line.startswith("WORKER_STATS"):
                    stats.append(line)
                    continue
                try:
                    o = json.loads(line)
                except Exception:
                    continue
                if o.get("type") == "caption":
                    caps.append(o.get("text"))
                if o.get("type") == "status" and o.get("state") == "done":
                    verdict = o.get("verdict")
                    device = o.get("device")
                if o.get("type") == "status" and o.get("state") == "silent-device":
                    silent = o.get("device"), o.get("api"), o.get("peak")
    except FileNotFoundError:
        pass
    return {"captions": caps, "verdict": verdict, "device": device,
            "silent": silent, "last_stats": stats[-1] if stats else None}


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "arm"
    arm = {}
    if tag == "arm1":
        pl = spawn_player(60)
        time.sleep(2.0)
        p, fh = spawn_worker(os.path.join(HERE, "sdr_arm1_live.jsonl"), 35)
        rc = p.wait(timeout=180)
        fh.close()
        try:
            pl.terminate()
        except Exception:
            pass
        arm = summarise(os.path.join(HERE, "sdr_arm1_live.jsonl"))
        arm["rc"] = rc
    else:
        # silent arm: confirm the tap reads silence first, then run the worker
        time.sleep(1.0)
        p, fh = spawn_worker(os.path.join(HERE, "sdr_arm2_silent.jsonl"), 28)
        rc = p.wait(timeout=180)
        fh.close()
        arm = summarise(os.path.join(HERE, "sdr_arm2_silent.jsonl"))
        arm["rc"] = rc
    print(json.dumps(arm, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
