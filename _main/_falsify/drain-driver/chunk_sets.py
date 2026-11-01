"""THE CHUNK-SET DIFFERENCE -- the two set differences, computed here.

THE CLAIM (owner, 2026-11-01, verbatim):
    "quando a carga liberar, o Sotto recarrega sozinho e processa QUALQUER
     audio nao processado, com o parakeet"
  i.e. every audio chunk NOT transcribed while the load-shedder held the
  nemotron back IS transcribed later by the background engine, ZERO dropped.

THE SETS, both reconstructed from the WORKER's OWN published numbers:

  SET A -- "the audio the worker SAW"
      A_tap   = `block_samples` / 16000   -- every sample the TAP delivered
               (`counters["block_samples"]`, `worker/sotto_worker.py`)
      A_dec   = `resampled_samples` / 16000 -- the samples that REACHED the
               decoder's thread at 16 kHz. The difference is the LIVE QUEUE's
               `queue_evicted` blocks: audio the tap delivered that the
               2 s live-queue cap threw away before the decoder ever saw it
               (`live_queue.enqueue_live`, "o NOVO e' o que se transcreve").

  SET B -- "the audio that WAS TRANSCRIBED"
      B_stream = `audio_s`   -- the STREAMING decoder's own clock (`asr.audio_s`)
      B_bg     = the parakeet's `audio_s` on every `REDUX_ENGINE_DONE`
                 (the seconds the background engine was HANDED) plus the
                 `REDUX_SHUTDOWN_TAIL audio_s=` tail.
      B_cover  = the UNION of the [start, end] intervals the parakeet's own
                 caption lines carry. This is the SET-THEORETIC coverage: it
                 says WHICH audio seconds the background engine's output
                 actually accounts for, without trusting any counter.

  THE TWO SET DIFFERENCES:
      A_dec - B_cover      -- seconds the decoder saw that NO parakeet line
                              covers. THIS IS THE CLAIM'S OWN MEASURE.
      A_dec - (B_stream + B_bg + WAIT)  -- the same thing in seconds.

  WAIT = `REDUX_SWITCH_STOP left_s=` -- the seconds still held at the stop.

THE TOLERANCE, said out loud:
  (a) the sub-chunk partial the decoder had not assembled when the mode
      changed (< 560 ms; `buf = np.zeros(0)`), and
  (b) the live queue's `queue_evicted` blocks (x 100 ms) -- a DELIBERATE,
      PRE-EXISTING policy of the LIVE stream ("a legenda que reproduz o
      passado e' pior do que uma legenda que perdeu um instante"), NOT the
      load-shedder's backlog. Reported separately so the reader can see
      exactly what was subtracted and why.

THE FALSIFYING OBSERVATION (named before any run):
  A_dec - B_cover > tolerance  ->  a chunk the worker SAW and the decoder
  RECEIVED is absent from the parakeet's output, older than the resume plus
  one drain cycle -> the claim is REFUTED.

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


def merge(intervals):
    """Union of [start, end] intervals -> (merged, gaps)."""
    items = sorted((s, e) for s, e in intervals if s is not None and e is not None and e > s)
    merged = []
    for s, e in items:
        if merged and s <= merged[-1][1] + 1e-9:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    gaps = []
    for i in range(1, len(merged)):
        gaps.append((merged[i - 1][1], merged[i][0]))
    return merged, gaps


def analyse(label):
    err_path = os.path.join(ARM, "%s.stderr.log" % label)
    out_path = os.path.join(ARM, "%s.stdout.jsonl" % label)
    stderr_lines = open(err_path, "r", encoding="utf-8", errors="replace").read().splitlines()
    stdout_lines = []
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
    tails = [kv(l) for l in stderr_lines if l.startswith("REDUX_SHUTDOWN_TAIL")]

    captions = [m for m in stdout_lines if m.get("type") == "caption"]
    bg = [c for c in captions if c.get("route") == "redux-batch" or c.get("producer") == "redux"]
    stream = [c for c in captions if c not in bg]
    bg_intervals = [(fnum(c.get("start")), fnum(c.get("end"))) for c in bg]
    stream_intervals = [(fnum(c.get("start")), fnum(c.get("end"))) for c in stream]
    bg_merged, bg_gaps = merge(bg_intervals)
    all_merged, gaps = merge(bg_intervals + stream_intervals)
    cover_s = sum(e - s for s, e in all_merged)
    bg_cover_s = sum(e - s for s, e in bg_merged)
    stream_cover_s = cover_s - bg_cover_s

    a_tap = (fnum(stats.get("block_samples")) or 0) / float(TARGET_SR)
    a_dec = (fnum(stats.get("resampled_samples")) or 0) / float(TARGET_SR)
    b_stream = fnum(stats.get("audio_s"), 0.0)
    b_bg = sum(fnum(d.get("audio_s"), 0.0) for d in dones) + sum(fnum(t.get("audio_s"), 0.0) for t in tails)
    wait_s = fnum(stop.get("left_s"), 0.0)
    evicted_s = (fnum(stats.get("queue_evicted"), 0.0) or 0.0) * 0.1
    dropped_s = (fnum(stats.get("queue_drops"), 0.0) or 0.0) * 0.1
    tolerance = CHUNK_S + evicted_s + dropped_s

    lost_cover = a_dec - cover_s
    lost_secs = a_dec - (b_stream + b_bg + wait_s)

    return {
        "label": label,
        "a_tap_s": a_tap,
        "a_dec_s": a_dec,
        "b_stream_s": b_stream,
        "b_bg_s": b_bg,
        "b_cover_s": cover_s,
        "wait_s": wait_s,
        "evicted_s": evicted_s,
        "dropped_s": dropped_s,
        "tolerance_s": tolerance,
        "lost_cover_s": lost_cover,
        "lost_secs_s": lost_secs,
        "excess_cover_s": lost_cover - tolerance,
        "excess_secs_s": lost_secs - tolerance,
        "RED": (lost_cover - tolerance) > 0.05,
        "bg_lines": len(bg),
        "stream_lines": len(stream),
        "bg_cover_s": bg_cover_s,
        "stream_cover_s": stream_cover_s,
        "merged_intervals": all_merged,
        "bg_intervals": bg_merged,
        "gaps": gaps,
        "stats": stats,
        "stop": stop,
        "dones": dones,
    }


def main():
    labels = sys.argv[1:] or ["arm1_shed_then_free", "arm2_never_frees",
                              "arm3_never_shed"]
    out = []
    for label in labels:
        if not os.path.exists(os.path.join(ARM, "%s.stderr.log" % label)):
            continue
        out.append(analyse(label))
    if not out:
        print("no arm records")
        return []
    print("=" * 104)
    print("THE TWO SET DIFFERENCES -- every number is the WORKER's own")
    print("=" * 104)
    print("%-22s %8s %8s %8s %8s %8s %8s %9s %9s %7s" % (
        "arm", "A_tap", "A_dec", "Bstrm", "B_bg", "Bcover", "WAIT", "LOSTcov", "LOSTsec", "VERDICT"))
    print("-" * 104)
    for r in out:
        print("%-22s %8.2f %8.2f %8.2f %8.2f %8.2f %8.2f %9.2f %9.2f %7s" % (
            r["label"], r["a_tap_s"], r["a_dec_s"], r["b_stream_s"], r["b_bg_s"],
            r["b_cover_s"], r["wait_s"], r["lost_cover_s"], r["lost_secs_s"],
            "RED" if r["RED"] else "green"))
    print("-" * 104)
    for r in out:
        print()
        print("### %s" % r["label"])
        print("   A_tap  = %.2f s  (the tap delivered %.2f s)" % (r["a_tap_s"], r["a_tap_s"]))
        print("   A_dec  = %.2f s  (the decoder RECEIVED %.2f s; the %.2f s "
              "difference is the live queue's cap)" % (
                  r["a_dec_s"], r["a_dec_s"], r["a_tap_s"] - r["a_dec_s"]))
        print("   B      : stream=%.2f  parakeet=%.2f  cover=%.2f  wait=%.2f" % (
            r["b_stream_s"], r["b_bg_s"], r["b_cover_s"], r["wait_s"]))
        print("   parakeet lines: %d (covering %.2f s) | streaming lines: %d (covering %.2f s)" % (
            r["bg_lines"], r["bg_cover_s"], r["stream_lines"], r["stream_cover_s"]))
        print("   merged coverage:", [(round(s, 2), round(e, 2)) for s, e in r["merged_intervals"]])
        print("   GAPS in the coverage:", [(round(s, 2), round(e, 2)) for s, e in r["gaps"]] or "NONE")
        print("   TOLERANCE = %.2f s (partial chunk %.2f + evicted %.2f + dropped %.2f)" % (
            r["tolerance_s"], CHUNK_S, r["evicted_s"], r["dropped_s"]))
        print("   LOST(cover) = %.2f s   EXCESS = %.2f s   -> %s" % (
            r["lost_cover_s"], r["excess_cover_s"], "RED" if r["RED"] else "green"))
        print("   LOST(secs)  = %.2f s   EXCESS = %.2f s" % (
            r["lost_secs_s"], r["excess_secs_s"]))
    return out


if __name__ == "__main__":
    main()
