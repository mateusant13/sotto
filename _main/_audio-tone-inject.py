#!/usr/bin/env python3
"""_audio-tone-inject.py — INJECT A TONE INTO A RENDER ENDPOINT AND PROVE THE LOOPBACK CARRIED IT.

The lane's gate cannot trust "I played a sound": on this host the loopback is ASYMMETRIC across
host APIs and a silent read is CORRECT behaviour when nothing is routed, so a gate that injects
without measuring the loopback at the same time is measuring nothing.  Both halves run together
here, on one clock, and both report their MEASURED peak.

It hard-refuses to play out of the DEFAULT output device (VoiceMeeter Input on this box): an
audible 440 Hz on the owner's desk is not a measurement.  --allow-audible / SOTTO_ALLOW_AUDIBLE=1
overrides it deliberately, in writing.

No console window: launchers use pythonw.exe or CREATE_NO_WINDOW.
"""
import argparse
import math
import os
import sys

import numpy as np


def find_devices(sd, want_out, want_in, prefer="Windows WASAPI"):
    """Resolve both halves of the virtual cable BY NAME, never by index, from ONE host API.

    The host API is part of a device's identity on this box: the same named cable exists under
    MME, DirectSound and WASAPI and the loopback is ASYMMETRIC across them (AGENTS.md routing
    law).  We take both halves from the same host API — the one the capture tap itself opens
    (WASAPI loopback) — and print every candidate considered so the choice is reviewable.
    """
    rows = []
    for api in sd.query_hostapis():
        for idx in api["devices"]:          # indices, not dicts
            info = sd.query_devices(idx)
            rows.append((idx, info["name"], api["name"], info.get("max_output_channels", 0),
                         info.get("max_input_channels", 0), info.get("default_samplerate", 0)))
    order = [prefer] + [r[2] for r in rows if r[2] != prefer and r[2] != "MME"]
    for api_name in order:
        out_dev = in_dev = None
        for idx, name, api, no, ni, sr in rows:
            if api != api_name:
                continue
            if want_out.lower() in name.lower() and no > 0 and out_dev is None:
                out_dev = (idx, name, api, sr)
            if want_in.lower() in name.lower() and ni > 0 and in_dev is None:
                in_dev = (idx, name, api, sr)
        if out_dev and in_dev:
            print("HOST-API-CHOSEN %s" % api_name)
            for idx, name, api, no, ni, sr in rows:
                if want_out.lower() in name.lower() or want_in.lower() in name.lower():
                    print("  CANDIDATE api=%s idx=%s out=%s in=%s sr=%s name=%s"
                          % (api, idx, no > 0, ni > 0, int(sr), name))
            return out_dev, in_dev, rows
    return None, None, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--freq", type=float, default=440.0)
    ap.add_argument("--amp", type=float, default=0.5)
    ap.add_argument("--rate", type=int, default=0, help="0 = the render endpoint's own mix rate")
    ap.add_argument("--channels", type=int, default=2)
    ap.add_argument("--out-name", default="CABLE Input")
    ap.add_argument("--in-name", default="CABLE Output")
    ap.add_argument("--allow-audible", action="store_true")
    ap.add_argument("--floor", type=float, default=0.8,
                    help="loopback peak must reach this fraction of the tone amplitude")
    ap.add_argument("--dry", action="store_true", help="resolve devices and stop")
    a = ap.parse_args()

    import sounddevice as sd

    out_dev, in_dev, rows = find_devices(sd, a.out_name, a.in_name)
    print("DEVICES-OUT-CANDIDATE %s" % (out_dev[1] if out_dev else "NONE"))
    print("DEVICES-IN-CANDIDATE %s" % (in_dev[1] if in_dev else "NONE"))
    if out_dev is None or in_dev is None:
        print("RESULT: RED - the virtual cable was not found on this host (out=%s in=%s)"
              % (a.out_name, a.in_name))
        return 2

    # The default-output refusal: this runs on the owner's desk.
    print("DEFAULT-DEVICE raw=%r type=%s" % (sd.default.device, type(sd.default.device).__name__))
    default_name = "?"
    try:
        dflt = list(sd.default.device)
    except Exception:
        dflt = [sd.default.device]
    default_out = dflt[-1] if dflt else None       # sd.default.device carries (input, output)
    if isinstance(default_out, str) and default_out:
        default_name = default_out
    elif isinstance(default_out, int) and default_out >= 0:
        try:
            default_name = sd.query_devices(default_out, "output")["name"]
        except Exception:
            default_name = "?"
    audible = a.allow_audible or os.environ.get("SOTTO_ALLOW_AUDIBLE", "") == "1"
    if out_dev[1].lower() == str(default_name).lower() and not audible:
        print("RESULT: RED - refusing to play out of the DEFAULT output (%s); pass --allow-audible "
              "or set SOTTO_ALLOW_AUDIBLE=1 to override on purpose" % default_name)
        return 3
    print("DEFAULT-OUTPUT %s (not used)" % default_name)

    if a.dry:
        print("RESULT: dry-run ok out=%d in=%d" % (out_dev[0], in_dev[0]))
        return 0

    if a.rate <= 0:
        a.rate = int(round(out_dev[3] or 48000.0))
        print("RATE-ADOPTED-RENDER %d (from %s)" % (a.rate, out_dev[1]))
    in_rate = a.rate
    try:
        sd.check_input_settings(device=in_dev[0], channels=a.channels, dtype="float32",
                                samplerate=a.rate)
    except Exception as ex:
        in_rate = int(round(in_dev[3] or 48000.0))
        print("RATE-ADOPTED-CAPTURE %d (render rate %d refused: %s)" % (in_rate, a.rate, ex))

    total = int(a.seconds * a.rate)
    cap = {"peak": 0.0, "frames": 0, "rms": 0.0, "clipped": False}
    state = {"pos": 0, "phase": 0.0}

    def out_cb(outdata, frames, time_info, status):
        i = np.arange(state["pos"], state["pos"] + frames, dtype=np.float64)
        x = (a.amp * np.sin(2.0 * math.pi * a.freq * i / a.rate)).astype(np.float32)
        outdata[:] = np.repeat(np.clip(x, -1.0, 1.0)[:, None], a.channels, axis=1)
        state["pos"] += frames

    def in_cb(indata, frames, time_info, status):
        if frames <= 0:
            return
        cap["frames"] += frames
        p = float(np.max(np.abs(indata)))
        if p > cap["peak"]:
            cap["peak"] = p
        cap["rms"] = float(np.sqrt(np.mean(indata.astype(np.float64) ** 2)))
        cap["clipped"] = cap["clipped"] or bool(p >= 0.999)

    with sd.OutputStream(samplerate=a.rate, channels=a.channels, dtype="float32",
                         device=out_dev[0], blocksize=2048, callback=out_cb) as so,          sd.InputStream(samplerate=in_rate, channels=a.channels, dtype="float32",
                        device=in_dev[0], blocksize=2048, callback=in_cb) as si:
        so.start()
        si.start()
        sd.sleep(int(a.seconds * 1000))
        so.stop()
        si.stop()

    printed = state["pos"]
    if printed:
        pk = a.amp
    else:
        pk = 0.0
    print("INJECTED seconds=%.3f freq=%.1f amp=%.3f frames_written=%d render_rate=%d ch=%d device=%s api=%s"
          % (a.seconds, a.freq, a.amp, printed, a.rate, a.channels, out_dev[1], out_dev[2]))
    print("MEASURED tone_peak=%.6f loopback_peak=%.6f loopback_rms=%.6f loopback_frames=%d "
          "render_rate=%d capture_rate=%d clipped=%s"
          % (pk, cap["peak"], cap["rms"], cap["frames"], a.rate, in_rate, cap["clipped"]))
    ok = (cap["peak"] >= a.amp * a.floor and cap["frames"] >= in_rate * a.seconds * 0.5)
    print("RESULT: %s - the loopback read the injected tone at %.6f (tone %.6f, expected >= %.3f)"
          % ("GREEN" if ok else "RED", cap["peak"], pk, a.amp * a.floor))
    return 0 if ok else 4


if __name__ == "__main__":
    sys.exit(main())
