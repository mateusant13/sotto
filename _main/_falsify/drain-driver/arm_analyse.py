"""THE ARITHMETIC ON THE ARM'S RECORDS -- the set difference, from the worker's
own published numbers.

THE SETS (all of them the WORKER's own counters, read off its stderr):

  IN   = `resampled_samples` / 16000
         The audio the tap delivered, at 16 kHz, AFTER the resample -- the same
         PCM the decoder is about to see. `worker/sotto_worker.py`,
         `counters["resampled_samples"] += int(block.size)`.

  OUT  = `audio_s` (the STREAMING decoder's own clock, `asr.audio_s`)
         + the background engine's `audio_s` on every `REDUX_ENGINE_DONE` line
           (the seconds it was HANDED; `engine_policy.run_engine_pass`:
           `sw.batch_seconds += samples / rate` is the same number).

         The background side is an UPPER BOUND, not a lower one: a pass that
         yields requeues the rest (`REDUX_ENGINE_YIELD ... requeued_s=`), so the
         same seconds can be counted twice. That makes OUT generous, which is
         the SAFE direction for a probe whose job is to find a loss.

  WAIT = the seconds still held when the worker stopped:
         `REDUX_SWITCH_STOP left_s=` and, if the shutdown tail ran, the
         `REDUX_SHUTDOWN_TAIL audio_s=` that was transcribed at exit.

  LOST = IN - OUT - WAIT.

THE TOLERANCE. The chunk the decoder had not yet assembled when the mode
changed (`buf = np.zeros(0)`, `asr_thread`) is under 560 ms and was never a
chunk. Plus the blocks the LIVE queue evicted to make room for the newest
(`queue_evicted` x 100 ms) -- those are a DELIBERATE policy ("o NOVO e' o que
se transcreve"), not the load-shedder's doing, and the claim is about the
load-shedder's backlog. Both are reported SEPARATELY so a reader can see
exactly what was subtracted.

THE FALSIFYING OBSERVATION, restated as a number:
  LOST > tolerance  ->  the claim is REFUTED for that run.

Read-only. Writes nothing.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, "arm")
TARGET_SR = 16000
CHUNK_S = 0.56


def kv(text):
    out = {}
    for m in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)=("[^"]*"|[^\s]*)', text):
        out[m.group(1)] = m.group(2).strip('"')
    return out


def fnum(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def read_arm(label):
    """The worker's own published facts for one arm."""
    err_path = os.path.join(ARM, "%s.stderr.log" % label)
    out_path = os.path.join(ARM, "%s.stdout.jsonl" % label)
    if not os.path.exists(err_path):
        return None
    stderr_lines = open(err_path, "r", encoding="utf-8", errors="replace").read().splitlines()
    stdout_lines = []
    if os.path.exists(out_path):
        for line in open(out_path, "r", encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                stdout_lines.append(json.loads(line))
            except ValueError:
                pass

    finals = [kv(l) for l in stderr_lines if l.startswith("WORKER_STATS tag=final")]
    stats = finals[-1] if finals else {}
    stops = [kv(l) for l in stderr_lines if l.startswith("REDUX_SWITCH_STOP")]
    stop = stops[-1] if stops else {}
    dones = [kv(l) for l in stderr_lines if l.startswith("REDUX_ENGINE_DONE")]
    yields = [kv(l) for l in stderr_lines if l.startswith("REDUX_ENGINE_YIELD")]
    tails = [kv(l) for l in stderr_lines if l.startswith("REDUX_SHUTDOWN_TAIL")]
    modes = [l for l in stderr_lines if l.startswith("REDUX_MODE")]
    sheddings = [l for l in stderr_lines if l.startswith("REDUX_SHEDDING")]
    kicks = [kv(l) for l in stderr_lines if l.startswith("REDUX_BATCH_KICK")]

    captions = [m for m in stdout_lines if m.get("type") == "caption"]
    bg_captions = [c for c in captions if c.get("route") == "redux-batch"
                   or c.get("producer") == "redux"]

    in_s = fnum(stats.get("resampled_samples"))
    in_s = in_s / float(TARGET_SR) if in_s is not None else None
    out_stream = fnum(stats.get("audio_s"), 0.0)
    out_bg = sum(fnum(d.get("audio_s"), 0.0) for d in dones)
    out_s = out_stream + out_bg
    wait_s = fnum(stop.get("left_s"), 0.0)
    evicted_s = (fnum(stats.get("queue_evicted"), 0.0) or 0.0) * 0.1
    dropped_s = (fnum(stats.get("queue_drops"), 0.0) or 0.0) * 0.1
    tolerance = CHUNK_S + evicted_s + dropped_s
    lost = None if in_s is None else in_s - out_s - wait_s

    return {
        "label": label,
        "in_s": in_s,
        "out_stream_s": out_stream,
        "out_bg_s": out_bg,
        "out_s": out_s,
        "wait_s": wait_s,
        "lost_s": lost,
        "evicted_s": evicted_s,
        "dropped_s": dropped_s,
        "tolerance_s": tolerance,
        "excess_s": None if lost is None else lost - tolerance,
        "RED": (lost is not None and (lost - tolerance) > 0.05),
        "engine_dones": dones,
        "engine_yields": yields,
        "shutdown_tails": tails,
        "kicks": kicks,
        "modes": modes,
        "sheddings": sheddings,
        "captions_total": len(captions),
        "captions_bg": len(bg_captions),
        "bg_texts": [c.get("text") for c in bg_captions],
        "stats": stats,
        "stop": stop,
    }


def main():
    labels = sys.argv[1:] or ["arm1_shed_then_free", "arm2_never_frees",
                              "arm3_never_shed"]
    print("=" * 96)
    print("THE SET DIFFERENCE, per arm -- every number is the WORKER's own")
    print("=" * 96)
    print("%-22s %7s %8s %8s %8s %8s %7s %8s  %s" % (
        "arm", "IN_s", "OUTstrm", "OUTbg", "OUT_s", "WAIT_s", "LOST_s", "EXCESS", "VERDICT"))
    print("-" * 96)
    out = []
    for label in labels:
        rec = read_arm(label)
        if rec is None:
            print("%-22s (no record)" % label)
            continue
        out.append(rec)
        print("%-22s %7.2f %8.2f %8.2f %8.2f %8.2f %7.2f %8.2f  %s" % (
            label, rec["in_s"] or 0, rec["out_stream_s"], rec["out_bg_s"],
            rec["out_s"], rec["wait_s"], rec["lost_s"] or 0,
            rec["excess_s"] or 0, "RED" if rec["RED"] else "green"))
    print("-" * 96)
    for rec in out:
        print()
        print("### ", rec["label"])
        print("  mode lines:")
        for m in rec["modes"]:
            print("     ", m[:200])
        print("  shedding lines:")
        for s in rec["sheddings"]:
            print("     ", s[:240])
        print("  kicks:", len(rec["kicks"]))
        for k in rec["kicks"]:
            print("     ", k)
        print("  engine passes (REDUX_ENGINE_DONE):")
        for d in rec["engine_dones"]:
            print("     ", d)
        print("  engine yields (REDUX_ENGINE_YIELD):")
        for y in rec["engine_yields"]:
            print("     ", y)
        print("  shutdown tails:", rec["shutdown_tails"])
        print("  stop:", rec["stop"])
        print("  captions total=%d  background(parakeet)=%d" % (
            rec["captions_total"], rec["captions_bg"]))
        for t in rec["bg_texts"]:
            print("     bg:", repr(t))
        print("  IN=%.2f OUT_stream=%.2f OUT_bg=%.2f OUT=%.2f WAIT=%.2f LOST=%.2f TOL=%.2f EXCESS=%.2f -> %s" % (
            rec["in_s"] or 0, rec["out_stream_s"], rec["out_bg_s"], rec["out_s"],
            rec["wait_s"], rec["lost_s"] or 0, rec["tolerance_s"],
            rec["excess_s"] or 0, "RED" if rec["RED"] else "green"))
    return out


if __name__ == "__main__":
    main()
