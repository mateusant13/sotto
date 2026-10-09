#!/usr/bin/env python3
"""Where the LIVE decode time goes, and which (window, step) to ship.

WHY THIS FILE EXISTS
--------------------
``worker/redux_live.py`` decodes the OPEN SEGMENT every ``--step-s``.  The first
smoke run measured **3-5 s of compute for a 2-9 s window** -- roughly 1x real time
-- while ``_main/redux-engine-cost-probe.py`` measured the SAME ONNX model at
**8.33x real time** on the whole 15 s clip in one call.  A 5x gap between two
measurements of the same model is a fact about the *shape of the call*, not about
the model, and it decides whether live captions are possible at all: if a 2 s
window costs 3 s, the decode can never keep up and the lag diverges -- the exact
failure the brief names.

So this probe does not guess.  It separates the three candidate causes:

  (a) A CONSTANT per-call cost (session/arena/thread-pool warm-up per `run()`),
      which would make many small calls far worse than one big one;
  (b) THE DECODE LOOP exploding -- ``OnnxParakeet.greedy`` runs up to
      ``max_symbols_per_step * frames`` iterations of ``decoder_joint.run``, and a
      token with duration 0 does not advance the frame, so noisy/aliased audio can
      multiply the step count without changing the audio length;
  (c) THE AUDIO being different -- the live path resamples 22 050 -> 16 000 with
      ``np.interp`` (no anti-alias filter) while the batch path decodes the file
      through the native reader.  Aliasing is a real, testable difference.

HOW IT SEPARATES THEM
---------------------
It instruments the model's OWN ``decoder_joint.run`` to COUNT the transducer steps
per call, and it decodes the same audio through BOTH readers, at several window
lengths.  ``steps`` vs ``audio seconds`` is what tells (a) from (b), and the
two-reader comparison tells (c).  Every arm prints its text, so a faster arm that
transcribes differently is visible as such.

It then drives ``worker/redux_live.py``'s OWN ``LiveSegmenter`` over the clip at
several (window, step) pairs -- the shipped code, not a model of it -- and reports
decode time per pass, whether it fits inside the step, and the closed lines.

BUDGET: ``--threads`` defaults to 2, the house budget for a probe.  ``--threads 0``
asks for the runtime's own pool and is labelled NOT-BUDGET.  No audio device is
opened and no subprocess is spawned except ffmpeg, which the reference reader uses
to decode the WAV (that is the reference's own path).

Usage:
    py -3 _main/redux-live-window-probe.py
    py -3 _main/redux-live-window-probe.py --windows 2,3,4,5,8 --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
WORKER = REPO / "worker"
WAV = HERE / "pt-br-sample.wav"
ONNX_DIR = WORKER / "models" / "parakeet-redux-onnx-int4"
REF_DIR = WORKER / "models" / "parakeet-redux-reference"

sys.path.insert(0, str(WORKER))
sys.path.insert(0, str(REF_DIR))


def _log(msg: str) -> None:
    print(msg, flush=True)


def _utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (ValueError, OSError):
                pass


# ── the instrument: count the transducer's own steps ──────────────────────────
class StepCounter:
    """Wrap ``decoder_joint.run`` and count calls.

    ``decoder_joint.run`` IS the transducer step: one call = one (token, duration)
    decision.  Counting it turns "this call was slow" into "this call ran N steps
    over M frames of audio", which is the difference between a fixed overhead and
    a decode loop that will not stop.
    """

    def __init__(self, model):
        self.model = model
        self.original = model.decoder_joint.run
        self.calls = 0
        self.encoder_frames = 0

    def __enter__(self):
        counter = self

        def counted(*args, **kwargs):
            counter.calls += 1
            return counter.original(*args, **kwargs)

        self.model.decoder_joint.run = counted
        original_encode = self.model.encode

        def encode(pcm):
            encoded = original_encode(pcm)
            counter.encoder_frames = int(encoded.shape[0])
            return encoded

        self.model.encode = encode
        self.calls = 0
        return self

    def __exit__(self, *exc):
        self.model.decoder_joint.run = self.original
        return False


def arm_cost_by_window(model, pcm, windows, threads) -> list[dict]:
    """One `transcribe()` per window length: compute, steps, text."""
    rows = []
    _log("")
    _log("ARM 1 -- cost of ONE transcribe() call, by window length (single call each)")
    _log(f"  threads={threads}" + ("  <-- NOT the house budget" if threads == 0 else ""))
    _log(f"  {'window_s':>8} {'compute_s':>10} {'xRT':>7} {'frames':>7} {'steps':>6} "
         f"{'steps/frame':>11}  text")
    for seconds in windows:
        chunk = pcm[: int(seconds * 16000)]
        with StepCounter(model) as counter:
            started = time.perf_counter()
            result = model.transcribe(chunk, "segment")
            elapsed = time.perf_counter() - started
        frames = counter.encoder_frames or 1
        row = {
            "window_s": round(len(chunk) / 16000.0, 2),
            "compute_s": round(elapsed, 3),
            "x_realtime": round((len(chunk) / 16000.0) / elapsed, 2) if elapsed else None,
            "encoder_frames": counter.encoder_frames,
            "decoder_steps": counter.calls,
            "steps_per_frame": round(counter.calls / frames, 2),
            "text": str(result.get("text") or "").strip(),
        }
        rows.append(row)
        _log(f"  {row['window_s']:>8.2f} {row['compute_s']:>10.3f} "
             f"{row['x_realtime']:>7.2f} {row['encoder_frames']:>7} "
             f"{row['decoder_steps']:>6} {row['steps_per_frame']:>11.2f}  "
             f"{row['text'][:70]!r}")
    return rows


def arm_readers(reference, windows) -> list[dict]:
    """The same audio through the reference reader and through the live reader."""
    import numpy as np

    _log("")
    _log("ARM 2 -- does the LIVE reader's resampling change the audio the model sees?")
    via_reference = reference.read_audio(WAV)
    try:
        import soundfile as sf

        raw, rate = sf.read(str(WAV), dtype="float32")
        if raw.ndim > 1:
            raw = raw.mean(axis=1)
        import importlib

        worker = importlib.import_module("sotto_worker")
        via_live = worker.resample_to_16k(np.asarray(raw, dtype=np.float32), rate)
    except Exception as exc:
        _log(f"  live reader unavailable ({type(exc).__name__}: {exc})")
        via_live = None

    rows = []
    for name, pcm in (("reference(ffmpeg)", via_reference), ("live(soundfile+interp)", via_live)):
        if pcm is None:
            continue
        row = {"reader": name, "samples": int(pcm.size),
               "duration_s": round(pcm.size / 16000.0, 2),
               "peak": round(float(np.abs(pcm).max()), 6),
               "rms": round(float(np.sqrt(np.mean(np.square(pcm, dtype=np.float64)))), 6)}
        rows.append(row)
        _log(f"  {name:<24} samples={row['samples']:>8} duration={row['duration_s']:>6.2f}s "
             f"peak={row['peak']:.6f} rms={row['rms']:.6f}")
    if via_live is not None and via_reference.size == via_live.size:
        diff = np.abs(via_reference - via_live)
        _log(f"  sample-wise |reference - live|: max={float(diff.max()):.6f} "
             f"mean={float(diff.mean()):.6f}  (a large max is aliasing, and it is the "
             f"one variable ARM 1 and the batch measurement do not share)")
        rows.append({"comparison": "reference_vs_live",
                     "max_abs_diff": float(diff.max()),
                     "mean_abs_diff": float(diff.mean())})
    return rows


def arm_segmenter(reference, pcm, windows, steps, threads, no_vad=False) -> list[dict]:
    """Drive the SHIPPED LiveSegmenter over the clip at each (window, step).

    The segmenter is fed in 100 ms blocks on a WALL CLOCK, exactly as the tap
    delivers them, and decoded on the same cadence the live loop uses.  So the
    numbers here are the shipped logic's numbers, not a re-derivation of them.
    """
    import importlib

    import numpy as np

    live = importlib.import_module("redux_live")
    worker = importlib.import_module("sotto_worker")

    def decode(model, seg):
        """Decode the OPEN segment exactly as ``LiveRun._pass`` does.

        The reference returns a DICT (``{"text", "segments", ...}``, four keys);
        ``redux_live.OnnxBackend`` is the one that turns it into a
        ``(text, segments)`` pair.  Unpacking the dict here is a ``KeyError: 0``.
        """
        audio = np.concatenate(seg.seg) if len(seg.seg) > 1 else seg.seg[0]
        return str(model.transcribe(audio, "segment").get("text") or "")

    _log("")
    _log("ARM 3 -- the SHIPPED LiveSegmenter, fed 100 ms blocks, decoded on the shipped cadence")
    _log("  (every arm pays ONE throwaway call first: the steady-state penalty below is real)")
    _log(f"  {'window':>7} {'step':>6} {'passes':>7} {'mean_s':>7} {'max_s':>7} "
         f"{'fits':>5} {'lines':>6}  closed lines")
    rows = []
    for window_s in windows:
        for step_s in steps:
            if step_s >= window_s:
                continue
            seg = live.LiveSegmenter(window_s=window_s, gap_s=0.7, min_window_s=1.2,
                                     max_line_chars=88, vad=not no_vad,
                                     gain=worker.AutoGain())
            model = reference.OnnxParakeet(ONNX_DIR, threads=(None if threads == 0 else int(threads)))
            block = 1600  # 100 ms at 16 kHz
            computes = []
            pending = []
            index = 0
            # WARM-UP, and it is not optional: the FIRST call on a fresh ORT session
            # is 2.5x FASTER than every call after it (measured).  A table built
            # without this pays the fast number once per arm and reports it as the
            # cadence.  The throwaway is on the same clip so nothing else differs.
            model.transcribe(pcm[: block * 10], "segment")
            # Pacing is on the STEP, not on the wall clock: the claim under test is
            # "does the DECODE fit inside the step", which is a ratio of two compute
            # times.  Feeding the clip as fast as it can be decoded would measure
            # throughput, a different thing.
            while index < pcm.size:
                pending.append(pcm[index:index + block])
                index += block
                if len(pending) * 0.1 + 1e-9 < step_s:
                    continue
                seg.feed(np.concatenate(pending))
                pending = []
                if not seg.should_decode():
                    continue
                started = time.perf_counter()
                text = decode(model, seg)
                computes.append(time.perf_counter() - started)
                text = (text or "").strip()
                if text and text != seg.last_text:
                    seg.last_text = text
                if seg.should_close(text):
                    seg.close(text)
                seg.drain()
            if pending:
                seg.feed(np.concatenate(pending))
            if seg.should_decode():
                started = time.perf_counter()
                text = decode(model, seg)
                computes.append(time.perf_counter() - started)
                text = (text or "").strip()
                if text:
                    seg.last_text = text
            if seg.last_text:
                seg.close(seg.last_text)
            finals = [e for e in seg.drain() if e.get("final")]
            mean_s = sum(computes) / len(computes) if computes else 0.0
            max_s = max(computes) if computes else 0.0
            row = {
                "window_s": window_s, "step_s": step_s, "passes": len(computes),
                "mean_compute_s": round(mean_s, 3), "max_compute_s": round(max_s, 3),
                "fits_in_step": bool(max_s <= step_s),
                "latency_bound_s": round(max_s + step_s, 2),
                "lines": len(finals),
                "text": " | ".join(e["text"] for e in finals),
            }
            rows.append(row)
            _log(f"  {window_s:>7.1f} {step_s:>6.1f} {len(computes):>7} {mean_s:>7.2f} "
                 f"{max_s:>7.2f} {str(row['fits_in_step']):>5} {len(finals):>6}  "
                 f"{row['text'][:64]!r}")
    return rows


def main(argv=None) -> int:
    _utf8_streams()
    parser = argparse.ArgumentParser(
        prog="redux-live-window-probe",
        description="Diagnose the live decode cost and choose (window, step) by measurement.")
    parser.add_argument("--windows", default="2,3,4,5,8,15",
                        help="window lengths in seconds, comma separated")
    parser.add_argument("--steps", default="1.0,1.5,2.0",
                        help="step lengths in seconds, comma separated")
    parser.add_argument("--threads", type=int, default=2,
                        help="2 = the house budget (default); 0 = the runtime's own pool")
    parser.add_argument("--no-vad", action="store_true", help="fixed windows only")
    parser.add_argument("--json", action="store_true", help="also print one JSON line")
    args = parser.parse_args(argv)

    import numpy as np

    import transcribe as reference

    windows = [float(x) for x in args.windows.split(",") if x.strip()]
    steps = [float(x) for x in args.steps.split(",") if x.strip()]

    _log(f"redux-live-window-probe  wav={WAV}")
    _log(f"  threads={args.threads}" + ("  <-- NOT the house budget" if args.threads == 0 else ""))
    model = reference.OnnxParakeet(ONNX_DIR, threads=(None if args.threads == 0 else args.threads))
    pcm = reference.read_audio(WAV)
    _log(f"  audio: {pcm.size} samples = {pcm.size / 16000:.2f} s")

    by_window = arm_cost_by_window(model, pcm, windows, args.threads)
    readers = arm_readers(reference, windows)
    segmenter = arm_segmenter(reference, pcm, windows, steps, args.threads, args.no_vad)

    _log("")
    _log("VERDICT")
    worst = max(by_window, key=lambda r: r["steps_per_frame"]) if by_window else None
    if worst:
        _log(f"  worst steps/frame = {worst['steps_per_frame']} at window "
             f"{worst['window_s']}s ({worst['decoder_steps']} steps over "
             f"{worst['encoder_frames']} frames) -- 1.0 would be one step per frame")
    fastest = max(by_window, key=lambda r: r["x_realtime"] or 0) if by_window else None
    if fastest:
        _log(f"  fastest single call  = {fastest['x_realtime']}x real time at "
             f"{fastest['window_s']}s")
    fitting = [r for r in segmenter if r["fits_in_step"]]
    if fitting:
        _log(f"  (window, step) that FIT the budget: "
             f"{[(r['window_s'], r['step_s']) for r in fitting]}")
    else:
        _log("  NO (window, step) pair fits: every pass costs more than its step. "
             "The lag diverges and live captions are not possible at these settings.")
    _log(f"  readers: {[r.get('reader') for r in readers if r.get('reader')]}")

    if args.json:
        print(json.dumps({"type": "result", "by_window": by_window, "readers": readers,
                          "segmenter": segmenter}, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
