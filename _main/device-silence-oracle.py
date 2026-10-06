"""ORACLE for the device/silence contract. One command, two arms, real exit codes.

This is the check that must be able to go RED, and it is deliberately built
from the two arms that cannot both pass by accident:

  ARM 1 (must FAIL LOUD): the owner has nothing playing into any loopback.
    Asserts exit code 3, verdict "silent-device", and that the status NAMES a
    device and its measured peak. A regression that lets a silent device pass as
    success turns this arm green-with-wrong-answer.

  ARM 2 (must SUCCEED): speech is rendered into the virtual cable and the real,
    unmodified worker captures it.
    Asserts exit code 0, verdict "captions-emitted", captions > 0, and that the
    device is the CABLE. A regression that breaks capture turns this arm red.

The two arms are opposites, so a run of this file that is all-green means both
the failure and the success paths were exercised in the same minute.

Usage: py -3 _main/device-silence-oracle.py [seconds]
Exit 0 = both arms behaved. Exit 1 = at least one arm misbehaved.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

import numpy as np
import sounddevice as sd

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.normpath(os.path.join(HERE, "..", "worker", "sotto_worker.py"))
RUNS = os.path.normpath(os.path.join(HERE, "..", "worker", "runs"))
SAMPLE = os.path.normpath(os.path.join(HERE, "..", "worker", "assets", "sample1.flac"))
NEG_CONFIG = os.path.join(RUNS, "oracle-neg-config.json")

CREATE_NO_WINDOW = 0x08000000
RENDER = "CABLE Input"
CABLE = "CABLE Output (VB-Audio Virtual Cable)"


def write_neg_config() -> str:
    """A config whose ONLY named device is a permanently silent one.

    Written from the shipped config so the model/lang settings under test are
    the real ones; only `audio.device` and `preferred_devices` are replaced.
    """
    with open(os.path.normpath(os.path.join(HERE, "..", "worker", "config.json")), encoding="utf-8") as f:
        cfg = json.load(f)
    silent = "Mixagem estéreo (Realtek HD Audio Stereo input)"
    cfg["audio"]["device"] = silent
    cfg["audio"]["preferred_devices"] = [silent]
    os.makedirs(RUNS, exist_ok=True)
    with open(NEG_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    return NEG_CONFIG


def run_worker(out_path: str, args: list[str]) -> dict:
    out = open(out_path, "wb")
    errf = open(out_path + ".err", "wb")
    proc = subprocess.Popen(
        [sys.executable, WORKER, *args],
        stdout=out, stderr=errf, stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW, cwd=os.path.dirname(WORKER),
    )
    rc = proc.wait(timeout=400)
    out.close()
    errf.close()
    statuses, captions = [], []
    with open(out_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") == "caption":
                captions.append(o.get("text", ""))
            else:
                statuses.append(o)
    done = next((o for o in statuses if o.get("state") == "done"), {})
    silent = next((o for o in statuses if o.get("state") == "silent-device"), None)
    return {"rc": rc, "done": done, "silent": silent, "captions": captions,
            "text": " ".join(c.strip() for c in captions if c.strip())}


def load_audio(path: str, rate: int):
    import soundfile as sf

    data, sr = sf.read(path, dtype="float32", always_2d=True)
    mono = data.mean(axis=1).astype(np.float32)
    if sr != rate:
        n = int(len(mono) * rate / sr)
        mono = np.interp(np.linspace(0, len(mono) - 1, n), np.arange(len(mono)), mono).astype(np.float32)
    return mono


def feed_cable(stop: threading.Event, rate: int = 44100) -> None:
    try:
        audio = load_audio(SAMPLE, rate)
    except Exception:
        return
    dev = next((d for d in sd.query_devices()
                if d["max_output_channels"] > 0 and RENDER.lower() in d["name"].lower()), None)
    if dev is None:
        return
    st = sd.OutputStream(device=dev["index"], channels=1, samplerate=rate, dtype="float32")
    st.start()
    pos = 0
    chunk = int(rate * 0.1)
    try:
        while not stop.is_set():
            if pos + chunk > len(audio):
                pos = 0
            st.write((0.6 * audio[pos:pos + chunk]).reshape(-1, 1))
            pos += chunk
    finally:
        st.stop()
        st.close()


def main() -> int:
    secs = sys.argv[1] if len(sys.argv) > 1 else "20"
    failures: list[str] = []
    os.makedirs(RUNS, exist_ok=True)

    # ── ARM 1: nothing routed -> must FAIL LOUD ──────────────────────────
    cfg = write_neg_config()
    a1 = run_worker(os.path.join(RUNS, "oracle-neg.jsonl"),
                    ["--max-seconds", secs, "--config", cfg])
    s = a1["silent"]
    if a1["rc"] == 0:
        failures.append(f"ARM1 exit code was 0; a silent device must not be success (rc={a1['rc']})")
    if a1["rc"] != 3:
        failures.append(f"ARM1 expected exit 3 (silent device), got {a1['rc']}")
    if a1["done"].get("verdict") != "silent-device":
        failures.append(f"ARM1 verdict was {a1['done'].get('verdict')!r}, expected 'silent-device'")
    if s is None:
        failures.append("ARM1 emitted no state='silent-device' status naming the device")
    elif not (s.get("device") and s.get("peak") is not None):
        failures.append(f"ARM1 silent-device status does not name device+peak: {s}")
    elif s.get("blocks", 0) < 20:
        failures.append(f"ARM1 silent verdict fired on only {s.get('blocks')} blocks; not a real window")
    print(json.dumps({
        "arm": "1-silent-must-fail-loud", "rc": a1["rc"],
        "verdict": a1["done"].get("verdict"), "captions": len(a1["captions"]),
        "device": (s or {}).get("device"), "api": (s or {}).get("api"),
        "peak": (s or {}).get("peak"), "peak_floor": (s or {}).get("peak_floor"),
        "blocks": (s or {}).get("blocks"),
    }, ensure_ascii=False), flush=True)

    # MEASURED: running ARM2 immediately after ARM1 makes ARM2 die at
    # "model-loading" with an EMPTY stderr and exit 4294967295. ARM1's process
    # has exited but its ~2.4 GB working set is still being torn down, and the
    # int8 session (~1 GB of weights) is mapped into the second one on top of
    # that. Run ALONE, ARM2 passed 3/3 (rc=0, 17 and 14 captions). This gap is
    # the difference between a real failure and a measurement artefact — and it
    # is a gap, not a retry: a retry would let a genuine memory failure pass.
    time.sleep(20)

    # ── ARM 2: speech routed into the cable -> must SUCCEED ──────────────
    stop = threading.Event()
    t = threading.Thread(target=feed_cable, args=(stop,), daemon=True)
    t.start()
    time.sleep(1.5)
    a2 = run_worker(os.path.join(RUNS, "oracle-pos.jsonl"),
                    ["--max-seconds", secs, "--device", CABLE])
    stop.set()
    t.join(timeout=5)
    if a2["rc"] != 0:
        failures.append(f"ARM2 expected exit 0 (captions emitted), got {a2['rc']}")
    if a2["done"].get("verdict") != "captions-emitted":
        failures.append(f"ARM2 verdict was {a2['done'].get('verdict')!r}, expected 'captions-emitted'")
    if len(a2["captions"]) == 0:
        failures.append("ARM2 produced 0 captions with audio routed into the cable")
    if CABLE not in str(a2["done"].get("device", "")):
        failures.append(f"ARM2 settled on {a2['done'].get('device')!r}, expected the CABLE")
    if not a2["done"].get("proved_alive"):
        failures.append("ARM2 done record does not carry proved_alive=true")
    print(json.dumps({
        "arm": "2-routed-must-succeed", "rc": a2["rc"],
        "verdict": a2["done"].get("verdict"), "captions": len(a2["captions"]),
        "device": a2["done"].get("device"), "peak": a2["done"].get("peak"),
        "proved_alive": a2["done"].get("proved_alive"),
        "rotations": a2["done"].get("rotations"),
        "caption_words": a2["text"][:180],
    }, ensure_ascii=False), flush=True)

    print(json.dumps({
        "oracle": "device-silence",
        "verdict": "PASS" if not failures else "FAIL",
        "failures": failures,
    }, ensure_ascii=False), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
