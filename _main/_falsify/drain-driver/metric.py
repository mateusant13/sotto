"""THE METRIC -- two independent set differences, computed here, from the
worker's OWN published facts.

THE CLAIM (owner, 2026-11-01, verbatim):
    "quando a carga liberar, o Sotto recarrega sozinho e processa QUALQUER
     audio nao processado, com o parakeet"
  i.e. every audio chunk NOT transcribed while the load-shedder held the
  nemotron back IS transcribed later by the background engine (parakeet),
  with ZERO dropped chunks.

THE SETS (all reconstructed from the worker's own counters and its own
output -- nothing is recomputed from the audio itself):

  A_dec  = `resampled_samples` / 16000
           The audio the DECODER RECEIVED at 16 kHz. The audio the worker
           SAW and HANDED ON. (`counters["resampled_samples"]`,
           `worker/sotto_worker.py`.)

  WAIT   = `REDUX_SWITCH_STOP left_s=`
           The audio still HELD when the worker stopped -- the shedder's
           backlog that never got transcribed. The claim says this must be 0
           once the load has freed.

  CONSUMED = the yield-chain sum.
           Each background pass is handed `audio_s` and, if it yields, hands
           BACK `requeued_s`. The audio that was really TRANSCRIBED by that
           pass is `audio_s - requeued_s`. The chain is walked in order and
           each pass's yield is subtracted from the pass that produced it.
           (A pass that yields requeues its remainder, so a naive sum of
           `audio_s` DOUBLE COUNTS -- that was the flaw the negative control
           caught, and it is fixed here.)

  COVER  = the union of the parakeet's caption-line [start, end] intervals.
           The audio seconds the parakeet's OUTPUT actually accounts for.

  GAPS   = the holes inside COVER.

TWO INDEPENDENT METRICS (each catches a different kind of loss):

  THE COUNTER METRIC   A_dec - WAIT - CONSUMED
                       "the audio the worker received is neither held nor
                        transcribed" -- a loss the counters would report.

  THE TEXT METRIC      (A_dec - WAIT) - COVER
                       "the audio the worker received produced NO TEXT" --
                       a loss the counters would NOT report, because the
                       counters only know what was handed to the engine.

  VERDICT = RED when EITHER metric exceeds its tolerance.

THE TOLERANCES, stated:
  * one CAPTURE BLOCK = 0.1 s (measured: `block_samples / blocks` = 1600
    samples). The audio quantum. A difference under one block is rounding.
  * one DECODER CHUNK = 0.56 s (`TARGET_CHR`/8960 samples) -- the partial the
    decoder had not assembled when the mode changed. It applies ONLY when the
    STREAMING engine ran (`chunks > 0`); the background path consumes exact
    sample counts and has no chunk boundary.
  * the BOUNDARY ROUNDING allowance: a caption's own [start, end] is the
    parakeet's segment timeline, which is quantised to the capture block, so
    a boundary can leave a hole of up to one block (0.1 s). The allowance is
    0.1 s per boundary (per gap + per pass).

THE CONSISTENCY CHECK (this is what catches a lie in the counters):
  if COVER reaches PAST `A_dec - WAIT`, the record claims text for audio it
  also claims is still waiting -- impossible. That is RED.

Read-only. Writes nothing.
"""
from __future__ import annotations

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, "arm")
TARGET_SR = 16000
BLOCK_S = 0.1
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
    items = sorted((s, e) for s, e in intervals
                   if s is not None and e is not None and e > s)
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


def analyse(label, err_path=None, out_path=None):
    err_path = err_path or os.path.join(ARM, "%s.stderr.log" % label)
    out_path = out_path or os.path.join(ARM, "%s.stdout.jsonl" % label)
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
    yields = [kv(l) for l in stderr_lines if l.startswith("REDUX_ENGINE_YIELD")]
    tails = [kv(l) for l in stderr_lines if l.startswith("REDUX_SHUTDOWN_TAIL")]
    modes = [l for l in stderr_lines if l.startswith("REDUX_MODE")]
    sheddings = [l for l in stderr_lines if l.startswith("REDUX_SHEDDING")]
    loads = [l for l in stderr_lines if l.startswith("REDUX_ENGINE_LOAD")]
    releases = [l for l in stderr_lines if l.startswith("REDUX_ENGINE_RELEASE")]

    # ── THE YIELD CHAIN, WALKED IN LOG ORDER ─────────────────────────────
    # The log is the ground truth for the ORDER. A `REDUX_ENGINE_DONE` opens
    # a pass (it was HANDED `audio_s`); a `REDUX_ENGINE_YIELD` that FOLLOWS
    # it says the pass only got through `done_s` and handed the REST back.
    # A pass with no yield after it consumed everything it was handed.
    passes = []
    cur = None
    for line in stderr_lines:
        if line.startswith("REDUX_ENGINE_DONE"):
            cur = {
                "reason": kv(line).get("reason"),
                "audio_s": fnum(kv(line).get("audio_s"), 0.0),
                "done_s": None,
                "requeued_s": 0.0,
                "lines": fnum(kv(line).get("lines"), 0.0),
                "windows": fnum(kv(line).get("windows"), 0.0),
            }
            passes.append(cur)
        elif line.startswith("REDUX_ENGINE_YIELD"):
            if cur is not None:
                cur["done_s"] = fnum(kv(line).get("done_s"), 0.0)
                cur["requeued_s"] = fnum(kv(line).get("requeued_s"), 0.0)
                cur = None
    for p in passes:
        # a pass that yielded consumed only `done_s`; one that did not
        # consumed everything it was handed.
        p["consumed_s"] = p["done_s"] if p["done_s"] is not None else p["audio_s"]
    consumed = sum(p["consumed_s"] for p in passes)
    # the shutdown tail is audio that WAS transcribed, at exit.
    tail_consumed = sum(fnum(t.get("audio_s"), 0.0) for t in tails)

    captions = [m for m in stdout_lines if m.get("type") == "caption"]
    bg = [c for c in captions
          if c.get("route") == "redux-batch" or c.get("producer") == "redux"]
    stream = [c for c in captions if c not in bg]
    bg_iv = [(fnum(c.get("start")), fnum(c.get("end"))) for c in bg]
    st_iv = [(fnum(c.get("start")), fnum(c.get("end"))) for c in stream]
    # The STREAMING engine's lines often carry NO `start` (the live engine
    # stamps only `end`). A line with no `start` covers the audio up to its
    # `end`; a line with no `end` at all covers nothing measurable. Those are
    # normalised here so the coverage union is not quietly UNDER-counted --
    # under-counting the coverage would make the TEXT metric look RED for the
    # wrong reason.
    st_iv = [(s if s is not None else 0.0, e) for s, e in st_iv if e is not None]
    bg_merged, _ = merge(bg_iv)
    all_merged, gaps = merge(bg_iv + st_iv)
    cover_s = sum(e - s for s, e in all_merged)
    cover_end = max((e for _, e in all_merged), default=0.0)
    bg_cover_s = sum(e - s for s, e in bg_merged)

    a_tap = (fnum(stats.get("block_samples")) or 0) / float(TARGET_SR)
    a_dec = (fnum(stats.get("resampled_samples")) or 0) / float(TARGET_SR)
    wait_s = fnum(stop.get("left_s"), 0.0)
    streaming_ran = (fnum(stats.get("chunks"), 0.0) or 0.0) > 0
    b_stream = fnum(stats.get("audio_s"), 0.0)

    n_boundaries = len(gaps) + len(passes)
    rounding = BLOCK_S * n_boundaries
    tol_counter = BLOCK_S + (CHUNK_S if streaming_ran else 0.0)
    tol_text = rounding + BLOCK_S + (CHUNK_S if streaming_ran else 0.0)

    # The STREAMING engine also transcribed (ARM 3 never sheds at all): its own
    # `audio_s` clock counts. It must be subtracted too, or the metric would
    # report a loss that the streaming path already covered.
    #
    # NOTE: the shutdown tail is NOT added here -- the shutdown pass is one of
    # `dones`, and the yield chain already accounts for what it consumed
    # (`done_s`), so adding the tail would count the same audio twice.
    lost_counter = a_dec - wait_s - consumed - b_stream
    lost_text = (a_dec - wait_s) - cover_s
    # ── THE THIRD METRIC ─────────────────────────────────────────────────
    # CONSUMED vs COVERED: the background engine was HANDED `consumed` seconds
    # and its own caption lines account for `cover_bg` seconds of audio. The
    # difference is audio the engine PROCESSED that produced NO TEXT.
    #
    # This is the metric that survives the nastiest forgery: when a counter
    # claims the audio is "still waiting" (left_s inflated) while the audio is
    # in fact GONE, the first two metrics can both be green -- but the engine
    # still consumed more audio than it covered, and only THIS catches it.
    lost_consumed_vs_cover = consumed - bg_cover_s
    inconsistent = cover_end > (a_dec - wait_s) + BLOCK_S

    red_counter = lost_counter > tol_counter + 0.05
    red_text = lost_text > tol_text + 0.05
    red_cvc = lost_consumed_vs_cover > tol_text + 0.05
    big_gap = any((e - s) > CHUNK_S for s, e in gaps)

    return {
        "label": label,
        "a_tap_s": a_tap,
        "a_dec_s": a_dec,
        "wait_s": wait_s,
        "consumed_s": consumed,
        "tail_consumed_s": tail_consumed,
        "b_stream_s": b_stream,
        "cover_s": cover_s,
        "cover_end": cover_end,
        "n_passes": len(passes),
        "passes": passes,
        "yields": yields,
        "tails": tails,
        "gaps": gaps,
        "merged": all_merged,
        "bg_merged": bg_merged,
        "bg_lines": len(bg),
        "stream_lines": len(stream),
        "bg_texts": [c.get("text") for c in bg],
        "lost_counter_s": lost_counter,
        "lost_text_s": lost_text,
        "tol_counter_s": tol_counter,
        "tol_text_s": tol_text,
        "rounding_s": rounding,
        "inconsistent": inconsistent,
        "big_gap": big_gap,
        "red_counter": red_counter,
        "red_text": red_text,
        "lost_consumed_vs_cover_s": lost_consumed_vs_cover,
        "red_consumed_vs_cover": red_cvc,
        "RED": red_counter or red_text or red_cvc or inconsistent or big_gap,
        "stats": stats,
        "stop": stop,
        "modes": modes,
        "sheddings": sheddings,
        "loads": loads,
        "releases": releases,
    }


def show(r):
    print("### %s" % r["label"])
    print("   A_tap=%.2f  A_dec=%.2f  WAIT=%.2f  CONSUMED=%.2f  TAIL=%.2f  "
          "STREAM=%.2f  COVER=%.2f (ends at %.2f)" % (
              r["a_tap_s"], r["a_dec_s"], r["wait_s"], r["consumed_s"],
              r["tail_consumed_s"], r["b_stream_s"], r["cover_s"],
              r["cover_end"]))
    print("   parakeet lines=%d  streaming lines=%d  passes=%d  "
          "gaps=%s" % (r["bg_lines"], r["stream_lines"], r["n_passes"],
                       [(round(s, 2), round(e, 2)) for s, e in r["gaps"]] or "none"))
    print("   COUNTER metric: LOST=%+.2f (tol %.2f) -> %s" % (
        r["lost_counter_s"], r["tol_counter_s"],
        "RED" if r["red_counter"] else "green"))
    print("   TEXT    metric: LOST=%+.2f (tol %.2f = %.2f rounding + %.2f) -> %s" % (
        r["lost_text_s"], r["tol_text_s"], r["rounding_s"],
        r["tol_text_s"] - r["rounding_s"],
        "RED" if r["red_text"] else "green"))
    print("   CONSUMED vs COVERED: LOST=%+.2f (tol %.2f) -> %s" % (
        r["lost_consumed_vs_cover_s"], r["tol_text_s"],
        "RED" if r["red_consumed_vs_cover"] else "green"))
    if r["inconsistent"]:
        print("   CONSISTENCY: the record claims text for audio it also claims "
              "is still waiting -> RED")
    if r["big_gap"]:
        print("   a coverage gap is larger than one decoder chunk -> RED")
    print("   VERDICT: %s" % ("RED" if r["RED"] else "green"))


if __name__ == "__main__":
    import sys
    labels = sys.argv[1:] or ["arm1_shed_then_free", "arm2_never_frees",
                              "arm3_never_shed", "arm4_disk_spool",
                              "arm5_release_reload"]
    print("=" * 92)
    print("THE TWO SET DIFFERENCES -- every number is the WORKER's own")
    print("=" * 92)
    print("%-22s %8s %8s %8s %9s %8s %8s %8s %7s" % (
        "arm", "A_tap", "A_dec", "WAIT", "CONSUMED", "COVER", "LOSTcnt", "LOSTtxt", "VERDICT"))
    print("-" * 92)
    recs = []
    for lab in labels:
        if not os.path.exists(os.path.join(ARM, "%s.stderr.log" % lab)):
            continue
        r = analyse(lab)
        recs.append(r)
        print("%-22s %8.2f %8.2f %8.2f %9.2f %8.2f %8.2f %8.2f %7s" % (
            r["label"], r["a_tap_s"], r["a_dec_s"], r["wait_s"],
            r["consumed_s"], r["cover_s"], r["lost_counter_s"],
            r["lost_text_s"], "RED" if r["RED"] else "green"))
    print("-" * 92)
    for r in recs:
        print()
        show(r)
