"""SottoDeviceRouting — MEASURE a model-free discriminator between a virtual
endpoint's IDLE FLOOR and a SPEECH-carrying capture, on the SAME tap.

Two arms, same process, same tap:
  IDLE   : open the WASAPI loopback of the default render endpoint, play nothing.
  SPEECH : open it again, render worker/assets/sample1.flac to the default output.

Prints per-arm peak/rms/zcr/env_hi_frac so a threshold can be chosen from data,
not from a guess. Hidden (no console): the driver is launched by the caller with
CREATE_NO_WINDOW; this script only uses PortAudio + the WASAPI tap.
"""
import os
import sys
import threading
import time

import numpy as np
import soundfile as sf

sys.path.insert(0, r"H:\sotto\worker")
import wasapi_loopback  # noqa: E402
import sounddevice as sd  # noqa: E402

SAMPLE = r"H:\sotto\worker\assets\sample1.flac"


def capture(seconds, play=False, gain=0.30):
    blocks = []

    def on_block(b):
        blocks.append(np.asarray(b, dtype=np.float32).copy())

    tap = wasapi_loopback.WasapiLoopbackTap(on_block, block_ms=100)
    stop = threading.Event()
    player = None
    if play:
        pcm, sr = sf.read(SAMPLE, dtype="float32", always_2d=True)
        if sr != tap.rate:
            n = int(len(pcm) * tap.rate / sr)
            idx = np.linspace(0, len(pcm) - 1, n)
            pcm = np.stack([np.interp(idx, np.arange(len(pcm)), pcm[:, c]) for c in range(pcm.shape[1])], axis=1)
        pcm = np.ascontiguousarray(pcm * gain, dtype="float32")
        # Render to the WASAPI DEFAULT OUTPUT device — the same endpoint the
        # loopback taps (rung a). `sd.default.device` is [MME-in, MME-out]; the
        # endorsed endpoint is faster to name through its own host API.
        wasapi = next((a for a in sd.query_hostapis() if "wasapi" in a["name"].lower()), None)
        out_dev = wasapi["default_output_device"] if wasapi else None
        info = sd.query_devices(out_dev)
        rate0 = int(info["default_samplerate"])
        ch0 = int(info["max_output_channels"])
        print(f"  rendering to out[{out_dev}] {info['name']!r} {rate0}Hz {ch0}ch")
        if rate0 != tap.rate:
            n = int(len(pcm) * rate0 / tap.rate)
            idx = np.linspace(0, len(pcm) - 1, n)
            pcm = np.stack([np.interp(idx, np.arange(len(pcm)), pcm[:, c]) for c in range(pcm.shape[1])], axis=1)
        if pcm.shape[1] < ch0:
            pcm = np.repeat(pcm, ch0, axis=1)[:, :ch0]
        elif pcm.shape[1] > ch0:
            pcm = pcm[:, :ch0]
        pcm = np.ascontiguousarray(pcm, dtype="float32")

        def loop():
            with sd.OutputStream(device=out_dev, samplerate=rate0, channels=ch0, dtype="float32") as out:
                t0 = time.time()
                while not stop.is_set() and (time.time() - t0) < seconds + 1.0:
                    out.write(pcm)

        player = threading.Thread(target=loop, daemon=True)
        player.start()
        time.sleep(0.4)

    t0 = time.time()
    with tap:
        while time.time() - t0 < seconds:
            time.sleep(0.05)
    stop.set()
    if player:
        player.join(timeout=2.0)
    fs = np.concatenate(blocks) if blocks else np.zeros(0, dtype=np.float32)
    return fs, tap.rate


def stats(x, rate, label):
    if x.size == 0:
        print(f"{label}: EMPTY")
        return
    peak = float(np.abs(x).max())
    rms = float(np.sqrt((x.astype("float64") ** 2).mean()))
    # zero-crossing rate over the whole capture (per sample)
    zc = int(np.count_nonzero(np.diff(np.signbit(x))))
    zcr = zc / max(1, x.size)
    # block-RMS coefficient of variation (100 ms blocks)
    blk = rate // 10
    n = (x.size // blk) * blk
    if n >= blk * 4:
        b = x[:n].reshape(-1, blk)
        br = np.sqrt((b.astype("float64") ** 2).mean(axis=1))
        cv = float(br.std() / br.mean()) if br.mean() > 0 else 0.0
    else:
        cv = float("nan")
    # envelope modulation: fraction of envelope energy ABOVE 4 Hz
    env = np.abs(x)
    w = max(1, rate // 100)
    n2 = (env.size // w) * w
    if n2 >= w * 16:
        e = env[:n2].reshape(-1, w).mean(axis=1)
        e = e - e.mean()
        sp = np.abs(np.fft.rfft(e)) ** 2
        freqs = np.fft.rfftfreq(e.size, d=w / rate)
        tot = sp[1:].sum()
        hi = sp[1:][freqs[1:] > 4.0].sum()
        env_hi = float(hi / tot) if tot > 0 else 0.0
    else:
        env_hi = float("nan")
    print(
        f"{label}: n={x.size} ({x.size/rate:.2f}s) peak={peak:.5f} rms={rms:.6f} "
        f"zcr={zcr:.5f} block_rms_cv={cv:.4f} env_hi_frac(>4Hz)={env_hi:.4f}"
    )


if __name__ == "__main__":
    secs = float(sys.argv[1]) if len(sys.argv) > 1 else 6.0
    print("default render endpoint:", wasapi_loopback.default_render_endpoint().name)
    print(sd.default.device)
    idle, rate = capture(secs, play=False)
    stats(idle, rate, "IDLE-1 (cold, nothing playing)")
    time.sleep(1.0)
    speech, rate = capture(secs, play=True)
    stats(speech, rate, "SPEECH (clip playing)        ")
    print("  ...sleeping %ds to see whether the floor DRAINS or PERSISTS" % int(secs * 4))
    time.sleep(secs * 4)
    idle2, rate = capture(secs, play=False)
    stats(idle2, rate, "IDLE-2 (after playback)      ")
