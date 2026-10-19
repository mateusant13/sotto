#!/usr/bin/env python
"""PROBE: does opening a capture endpoint BLOCK, or does it raise?

DONO, 2026-10-15/17 (prompt #20): *"por que eu fico sem audio de tempos em
tempos?"* -- and the panel had gone red with "audio device is in use".

THE QUESTION THIS ANSWERS
-------------------------
The worker's ladder opens every capture candidate INLINE
(`worker/sotto_worker.py:6127` `LoopbackTap(...)` -> `:1764`
`sd.InputStream(...)`). Its retry logic only runs if the open RAISES
(`:6178` `if not _is_device_in_use(detail) or retry >= 2`). So if an endpoint's
open BLOCKS instead of raising, the ladder never rotates: the worker sits
there, no captions, and the owner hears nothing.

MEASURED 2026-10-19 on this box, with this instrument:

    Headset (soundcore Space Q45)          [MME]              BLOQUEIOU (>4 s)
    Headset (soundcore Space Q45)          [Windows WASAPI]   BLOQUEIOU (>4 s)
    Headset (soundcore Space Q45)          [DirectSound]      aberto em 0,01 s
    CABLE Output (VB-Audio Virtual Cable)  [MME/DS/WASAPI]    abre

The SAME device, three APIs: two of them block and one does not. And the
worker's own log, on 2026-10-15 15:56, shows exactly this event:

    BRIDGE_EXIT  pid=43676 rc=3 captions=0
      stderr_tail=["OPEN_RETRY_RETRY device='WASAPI loopback: Fones de ouvido (...
    BRIDGE_DEATH last="Sotto could not start listening - The audio device is
      already in use by another program, so Sotto co..."

WHAT IT DOES NOT TOUCH: no output device is opened, nothing is rendered, the
owner's default output is not touched, and every stream opened here is closed
again. It only opens and closes CAPTURE endpoints, exactly as the worker does.

HOW IT MEASURES "BLOCKS": each endpoint is opened in its own THREAD with a
timeout. If the thread has not finished when the timeout expires, the open
is BLOCKED -- not slow, not busy, blocked. The threads are daemons and the
process leaves with `os._exit()`, so a thread stuck in PortAudio cannot hold
the process.

    python _main\probe-capture-open.py
    python _main\probe-capture-open.py --timeout 6
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time

import sounddevice as sd

#: Only the endpoints a caption chain would care about: the virtual cables,
#: the loopbacks, and the headsets. Opening every microphone on the box would
#: be rude to whatever else is listening.
WANT = ("loopback", "cable", "fones", "headset", "headphone", "voicemeeter")


def try_open(dev, result):
    try:
        channels = min(2, int(dev["max_input_channels"]) or 1)
        rate = int(dev["default_samplerate"])
        t0 = time.time()
        with sd.InputStream(device=dev["index"], channels=channels,
                            samplerate=rate, dtype="float32") as st:
            data, _ = st.read(int(rate * 0.2))
            peak = 0.0
            if len(data):
                peak = float(max(abs(float(row[0])) for row in data))
            result["ok"] = True
            result["detail"] = "aberto em %.2fs, pico=%.4f" % (time.time() - t0, peak)
    except Exception as exc:  # noqa: BLE001 -- the failure IS the measurement
        result["ok"] = False
        result["detail"] = "%s: %s" % (type(exc).__name__, exc)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=float, default=4.0,
                    help="seconds before an open counts as BLOCKED")
    ap.add_argument("--out", default=r"I:\cc-tmp\probe-capture-open.json")
    args = ap.parse_args(argv)

    rows = []
    for dev in sd.query_devices():
        if dev["max_input_channels"] <= 0:
            continue
        name = dev["name"]
        if not any(w in name.lower() for w in WANT):
            continue
        api = sd.query_hostapis(dev["hostapi"])["name"]
        res = {"ok": None, "detail": "", "name": name, "api": api}
        th = threading.Thread(target=try_open, args=(dev, res), daemon=True)
        t0 = time.time()
        th.start()
        th.join(args.timeout)
        if th.is_alive():
            res["ok"] = False
            res["blocked"] = True
            res["detail"] = "BLOQUEIOU (open nao voltou em %.1fs)" % args.timeout
        else:
            res["blocked"] = False
        res["waited"] = round(time.time() - t0, 2)
        rows.append(res)
        print("%-58s" % name[:58])
        print("    %-26s %s (%.2fs)" % (api, res["detail"], res["waited"]), flush=True)

    blocked = [r for r in rows if r.get("blocked")]
    denied = [r for r in rows if r["ok"] is False and not r.get("blocked")]
    free = [r for r in rows if r["ok"] is True]
    print()
    print("RESUMO: %d testado(s) | %d LIVRE | %d com ERRO | %d BLOQUEADO"
          % (len(rows), len(free), len(denied), len(blocked)))
    for r in blocked:
        print("  BLOQUEIOU: %s [%s]" % (r["name"], r["api"]))
    for r in denied:
        print("  ERRO:      %s [%s] -> %s" % (r["name"], r["api"], r["detail"]))
    for r in free:
        print("  LIVRE:     %s [%s]" % (r["name"], r["api"]))
    try:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"timeout_s": args.timeout, "rows": rows}, fh,
                      ensure_ascii=False, indent=2)
        print("\nrecibo: %s" % args.out)
    except OSError as exc:
        print("\nrecibo NAO escrito: %s" % exc)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
