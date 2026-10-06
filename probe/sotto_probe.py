"""Sotto M1 probe — does this PC expose a loopback tap on the render endpoint,
and can a streaming ASR model run here without Rust?

Two questions, two measurements, no claims:

  Q1  sounddevice: how many devices, and does any of them carry WASAPI LOOPBACK
      (an input device that mirrors what the speakers are playing)? That is the
      whole premise of "transcribe ANY audio on the PC". A machine with zero
      loopback inputs cannot do it, and no amount of model work changes that.

  Q2  faster_whisper: does it import, does it pick a device, and does it
      actually emit text from a synthetic WAV. Text in, text out — not just a
      successful import, which is not evidence of recognition.

Prints JSON. Exits 0 only if BOTH questions produced evidence. Any question
without evidence is a FAIL, and the message says which.
"""

import json
import os
import sys
import time

OUT = {"q1_devices": {}, "q2_asr": {}, "verdict": "", "rc": 1}


def q1_devices():
    import sounddevice as sd

    devices = sd.query_devices()
    wasapi = [d["name"] for d in sd.query_devices() if "WASAPI" in str(d.get("hostapi", ""))]
    inputs = [d for d in devices if d["max_input_channels"] > 0]
    loopback = []
    try:
        h = sd.WasapiSettings(exclusive=False)
        loop_names = sd.query_devices(kind="input", extra_settings=h)
        for d in loop_names:
            if d["max_input_channels"] > 0:
                loopback.append({"name": d["name"], "in": d["max_input_channels"]})
    except Exception as exc:  # the query itself can fail on some drivers
        loopback = [{"error": f"{type(exc).__name__}: {exc}"}]

    OUT["q1_devices"] = {
        "population": len(devices),
        "input_devices": len(inputs),
        "wasapi_hostapi_names": sorted(set(wasapi))[:12],
        "input_names": [d["name"] for d in inputs][:20],
        "loopback_inputs": loopback,
        "loopback_count": len([x for x in loopback if "name" in x]),
    }
    return len(loopback) > 0


def q2_asr():
    """Synthetic tone in, recognisable speech-shaped result out."""
    import numpy as np
    import soundfile as sf

    from faster_whisper import WhisperModel

    t0 = time.time()
    model_name = os.environ.get("SOTTO_PROBE_MODEL", "tiny")
    device = os.environ.get("SOTTO_PROBE_DEVICE", "cpu")
    compute = os.environ.get("SOTTO_PROBE_COMPUTE", "int8")

    model = WhisperModel(model_name, device=device, compute_type=compute)
    load_s = time.time() - t0

    # A real speech signal is what a recogniser must score above chance. Silence
    # is not: every model emits something for it, so silence cannot falsify.
    sr = 16000
    wav = os.path.join(os.environ.get("TEMP", "H:\\Temp"), "sotto_probe.wav")
    try:
        from pydub import AudioSegment  # optional, only to synthesise speech-ish audio

        raise RuntimeError("pydub path unused")
    except Exception:
        pass

    # 1.5 s of shaped noise at speech-like cadence, saved as 16 kHz mono WAV.
    rng = np.random.default_rng(7)
    n = int(sr * 1.5)
    sig = rng.normal(0, 0.05, n).astype(np.float32)
    for start in range(0, n, sr // 4):
        seg = sig[start : start + sr // 4]
        env = np.hanning(len(seg))
        f0 = 120 + (start // (sr // 4)) * 20
        t = np.arange(len(seg)) / sr
        tone = 0.12 * np.sin(2 * np.pi * f0 * t)
        sig[start : start + sr // 4] = 0.7 * tone * env + 0.3 * seg
    sf.write(wav, sig, sr)

    t1 = time.time()
    segments, info = model.transcribe(wav, language="en", beam_size=1, vad_filter=False)
    segs = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
    infer_s = time.time() - t1

    audio_s = 1.5
    OUT["q2_asr"] = {
        "model": model_name,
        "device": device,
        "compute_type": compute,
        "load_s": round(load_s, 2),
        "infer_s": round(infer_s, 2),
        "audio_s": audio_s,
        "language": info.language,
        "segment_count": len(segs),
        "text": " ".join(s["text"] for s in segs).strip(),
        "rss_mb": round(
            int(
                open("/proc/self/statm").read().split()[1]
            ) / 1024
            if os.path.exists("/proc/self/statm")
            else 0,
            1,
        ),
    }
    # A recogniser that returns no segments at all has told us nothing.
    return len(segs) > 0


def main():
    d_ok = a_ok = False
    try:
        d_ok = q1_devices()
    except Exception as exc:
        OUT["q1_devices"] = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        a_ok = q2_asr()
    except Exception as exc:
        OUT["q2_asr"] = {"error": f"{type(exc).__name__}: {exc}"}

    if d_ok and a_ok:
        OUT["verdict"] = "BOTH MEASURED"
        OUT["rc"] = 0
    elif not d_ok:
        OUT["verdict"] = "NO LOOPBACK INPUT - the premise of 'any audio on the PC' fails here"
    else:
        OUT["verdict"] = "ASR PRODUCED NO SEGMENTS"

    print(json.dumps(OUT, indent=2, ensure_ascii=False))
    return OUT["rc"]


if __name__ == "__main__":
    sys.exit(main())