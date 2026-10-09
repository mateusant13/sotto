"""Lane SottoLiveAudioSweep -- INSTRUMENT 2: a live tap on an endpoint the owner's
worker does NOT hold, plus the instrument's own positive control.

WHAT IS BEING RESOLVED. `worker/sotto_worker.py` (pid 29008) holds a capture stream
on the CAPTURE endpoint `CABLE Output (VB-Audio Virtual Cable)`. The ONLY endpoint
carrying the owner's live audio, per `live-audio-sweep-endpoints.py`, is that same
VB-Cable pair: `CABLE Input` (RENDER, meter 0.0996) -> `CABLE Output` (CAPTURE,
meter 0.1268). VoiceMeeter is RUNNING (pid 32276) but its own bus outputs read
0.000000, i.e. VoiceMeeter is not in the audio path today.

So the free way in is a WASAPI LOOPBACK of the `CABLE Input` RENDER endpoint: a
different IMMDevice, in the other flow, from the one the worker holds. Whether the
VB-Cable driver allows that is a MEASUREMENT, not a guess: a refusal is reported
with its HRESULT (0x8889000A = AUDCLNT_E_DEVICE_IN_USE) instead of being retried.

ARMS, one process, sequential:
  * `live`    -- loopback of `CABLE Input`, N seconds -> the sample every other lane
                 uses. Recorded native (48 kHz float32 MONO, the tap's own mix
                 format) so nothing in the chain is re-quantised here.
  * `control` -- the SAME instrument, same block size, on `VoiceMeeter Input`
                 (meter 0.000000, nothing rendering to it), 5 s. This is the
                 instrument's positive control: a tap that reads audio on the live
                 arm MUST read digital silence here, or the "peak" it reports says
                 nothing about the endpoint.

Threads: ONE (the tap's own pump). No audio is played. Every tap is closed in a
`finally`, and the close is asserted by re-reading the endpoint's meter afterwards.
"""

import ctypes
import json
import os
import sys
import time

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(os.path.dirname(HERE), "worker")
sys.path.insert(0, WORKER)

import wasapi_loopback as W  # noqa: E402

CABLE_INPUT = "{0.0.0.00000000}.{2f1295af-8529-4f15-b00d-7b9bba575ac0}"     # render, LIVE
VOICEMEETER_INPUT = "{0.0.0.00000000}.{55395a4e-97b2-4b96-9878-18be1ed894e0}"  # render, idle


def record(endpoint_id, seconds, block_ms=100):
    """Open ONE loopback tap, record `seconds`, close it, return the measurement."""
    blocks = []
    block_peaks = []
    t_state = {"t0": None, "t_last": None}

    def on_block(block):
        now = time.time()
        if t_state["t0"] is None:
            t_state["t0"] = now
        t_state["t_last"] = now
        blocks.append(block)
        block_peaks.append(float(np.max(np.abs(block))) if block.size else 0.0)

    row = {
        "endpoint_id": endpoint_id,
        "requested_seconds": seconds,
        "block_ms": block_ms,
        "opened": False,
        "open_error": None,
        "open_error_hresult": None,
        "closed": False,
        "blocks": 0,
        "block_peaks": [],
        "peak": None,
        "rms": None,
        "nonzero_blocks": None,
        "distinct_block_peaks": None,
        "wall_s": None,
        "rate": None,
        "channels": None,
        "samples": 0,
        "wav": None,
        "samples_sha256": None,
    }
    tap = None
    t0 = time.time()
    try:
        try:
            tap = W.WasapiLoopbackTap(on_block, block_ms=block_ms, endpoint_id=endpoint_id)
            tap.start()
            row["opened"] = True
            row["rate"] = tap.rate
            row["channels"] = tap.channels
            row["name"] = tap.name
        except W.WasapiError as exc:
            row["open_error"] = str(exc)
            msg = str(exc)
            if "0x" in msg:
                row["open_error_hresult"] = msg[msg.rfind("0x"):].strip()
            return row
        except Exception as exc:  # noqa: BLE001
            row["open_error"] = "%s: %s" % (type(exc).__name__, exc)
            return row

        deadline = t0 + seconds
        while time.time() < deadline:
            time.sleep(0.05)
        time.sleep(0.15)
    finally:
        if tap is not None:
            tap.close()
            row["closed"] = True
            row["silent_packets"] = int(getattr(tap, "silent_packets", 0))
            row["position_gap_packets"] = int(getattr(tap, "position_gap_packets", 0))

    row["wall_s"] = round(time.time() - t0, 3)
    row["blocks"] = len(blocks)
    row["block_peaks"] = [round(p, 6) for p in block_peaks]
    if blocks:
        joined = np.concatenate(blocks)
        row["samples"] = int(joined.size)
        row["peak"] = round(float(np.max(np.abs(joined))), 6)
        row["rms"] = round(float(np.sqrt(np.mean(np.square(joined.astype(np.float64))))), 8)
        row["nonzero_blocks"] = int(sum(1 for p in block_peaks if p > 0.0))
        row["distinct_block_peaks"] = int(len(set(round(p, 6) for p in block_peaks)))
        row["duration_s"] = round(joined.size / float(row["rate"]), 3)
        row["_audio"] = joined
    return row


def main():
    args = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    live_seconds = float(args.get("live", 30))
    control_seconds = float(args.get("control", 5))
    out_wav = args.get("out", os.path.join(HERE, "live-sample-cable-input.wav"))

    doc = {
        "instrument": "live-audio-sweep-tap.py",
        "cadence": "one block peak per 100 ms tap block; one tap per arm, closed in finally",
        "threads": 1,
        "played_any_audio": False,
        "arms": [],
    }

    # -- ARM live ------------------------------------------------------------
    live = record(CABLE_INPUT, live_seconds)
    audio = live.pop("_audio", None)
    if audio is not None and audio.size:
        sf.write(out_wav, audio, int(live["rate"]), subtype="FLOAT")
        import hashlib
        with open(out_wav, "rb") as fh:
            live["samples_sha256"] = hashlib.sha256(fh.read()).hexdigest()
        live["wav"] = out_wav
        live["wav_bytes"] = os.path.getsize(out_wav)
    doc["arms"].append(dict(live, arm="live"))

    # -- ARM control ---------------------------------------------------------
    control = record(VOICEMEETER_INPUT, control_seconds)
    control.pop("_audio", None)
    doc["arms"].append(dict(control, arm="control"))

    # -- did the tap actually release the endpoint? --------------------------
    time.sleep(0.5)
    try:
        peaks = W.live_render_peaks(meter_ms=0.2)
        doc["meter_after_close"] = {
            CABLE_INPUT: peaks.get(CABLE_INPUT),
            VOICEMEETER_INPUT: peaks.get(VOICEMEETER_INPUT),
        }
    except Exception as exc:  # noqa: BLE001
        doc["meter_after_close"] = {"error": "%s: %s" % (type(exc).__name__, exc)}

    summary = {
        "instrument": doc["instrument"],
        "cadence": doc["cadence"],
        "arms": [{k: v for k, v in a.items() if k != "block_peaks"} for a in doc["arms"]],
        "meter_after_close": doc["meter_after_close"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    with open(os.path.join(HERE, "live-audio-sweep-tap.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
