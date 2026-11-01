"""THE NEGATIVE CONTROL FOR THE ARM HARNESS ITSELF.

A green ARM 1 is worth nothing unless the ARM can go RED. This is the proof
that it can.

TWO METRICS, and each forgery must break the RIGHT one:

  THE SECONDS METRIC   A_dec - (B_stream + B_bg + WAIT).
                        It trusts the worker's COUNTERS.
  THE COVERAGE METRIC  A_dec - (the union of the parakeet's caption-line
                        [start, end] intervals).
                        It trusts the worker's OUTPUT -- which is the thing the
                        claim is actually about ("processa QUALQUER audio nao
                        processado": the audio that PRODUCED TEXT).

  THE VERDICT is RED when EITHER metric's excess is positive.

THE FORGERIES:

  FORM A -- THE COUNTER FORM. One `REDUX_ENGINE_DONE ... audio_s=X` line has
  its seconds reduced by one chunk (0.56 s). The audio the parakeet was HANDED
  is now smaller than the audio the decoder RECEIVED. The SECONDS metric must
  go RED. (The COVERAGE metric does NOT have to: the caption LINES still cover
  the audio, so nothing was really lost -- which is exactly why the coverage
  metric is the honest one and the counter metric is only a cross-check.)

  FORM B -- THE TEXT FORM. One parakeet caption line is deleted from the
  stdout. The coverage now has a hole in it. The COVERAGE metric must go RED.

  FORM C -- THE COUNTERS-HIDE-IT FORM. The nastiest one: one caption line is
  deleted AND `REDUX_SWITCH_STOP left_s=` is inflated by the same amount, so
  the SECONDS metric is GREEN (the counter claims the audio is "still waiting
  for a motor") while the audio is in fact GONE. Only the COVERAGE metric can
  catch this. The probe must still go RED.

Read-only against the repo; it writes only under `_falsify_drain/neg/`.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ARM = os.path.join(HERE, "arm")
NEG = os.path.join(HERE, "neg")
CHUNK_S = 0.56

sys.path.insert(0, HERE)
import metric  # noqa: E402


def _paths(label):
    return (os.path.join(ARM, "%s.stderr.log" % label),
            os.path.join(ARM, "%s.stdout.jsonl" % label))


def forge_counter(label):
    """One engine pass loses 0.56 s (the COUNTER form)."""
    src, _ = _paths(label)
    dst = os.path.join(NEG, "forged-%s.stderr.log" % label)
    os.makedirs(NEG, exist_ok=True)
    changed = 0
    with open(src, "r", encoding="utf-8", errors="replace") as fh, \
            open(dst, "w", encoding="utf-8", errors="replace") as out:
        for line in fh:
            if not changed and line.startswith("REDUX_ENGINE_DONE"):
                m = re.search(r"audio_s=([0-9.]+)", line)
                if m and float(m.group(1)) >= CHUNK_S:
                    line = (line[:m.start(1)]
                            + ("%.2f" % (float(m.group(1)) - CHUNK_S))
                            + line[m.end(1):])
                    changed += 1
            out.write(line)
    return dst, changed


def forge_text(label):
    """One parakeet caption line is deleted (the TEXT form)."""
    _, src = _paths(label)
    dst = os.path.join(NEG, "forged-%s.stdout.jsonl" % label)
    os.makedirs(NEG, exist_ok=True)
    removed = 0
    with open(src, "r", encoding="utf-8", errors="replace") as fh, \
            open(dst, "w", encoding="utf-8", errors="replace") as out:
        for line in fh:
            if not removed:
                try:
                    m = json.loads(line)
                except ValueError:
                    m = None
                if m and m.get("type") == "caption" and \
                        (m.get("route") == "redux-batch" or m.get("producer") == "redux"):
                    removed = 1
                    continue
            out.write(line)
    return dst, removed


def forge_hold(label, add_s):
    """`left_s` is inflated: the counter claims the audio is still waiting."""
    src, _ = _paths(label)
    dst = os.path.join(NEG, "forged-hold-%s.stderr.log" % label)
    os.makedirs(NEG, exist_ok=True)
    changed = 0
    with open(src, "r", encoding="utf-8", errors="replace") as fh, \
            open(dst, "w", encoding="utf-8", errors="replace") as out:
        for line in fh:
            if line.startswith("REDUX_SWITCH_STOP"):
                m = re.search(r"left_s=([0-9.]+)", line)
                if m:
                    line = (line[:m.start(1)]
                            + ("%.2f" % (float(m.group(1)) + add_s))
                            + line[m.end(1):])
                    changed += 1
            out.write(line)
    return dst, changed


def probe(label, err_path=None, out_path=None):
    """Run the SAME analysis over a (possibly forged) arm record, then put the
    original records back."""
    saved_err, saved_out = _paths(label)
    bak_err, bak_out = saved_err + ".bak", saved_out + ".bak"
    shutil.copyfile(saved_err, bak_err)
    shutil.copyfile(saved_out, bak_out)
    try:
        if err_path:
            shutil.copyfile(err_path, saved_err)
        if out_path:
            shutil.copyfile(out_path, saved_out)
        rec = metric.analyse(label)
    finally:
        shutil.copyfile(bak_err, saved_err)
        shutil.copyfile(bak_out, saved_out)
        os.remove(bak_err)
        os.remove(bak_out)
    return rec


def show(tag, rec):
    print("   %-22s A_dec=%.2f  cover=%.2f  wait=%.2f  consumed=%.2f  bg=%d" % (
        tag, rec["a_dec_s"], rec["cover_s"], rec["wait_s"],
        rec["consumed_s"], rec["bg_lines"]))
    print("   %-22s COUNTER: %+.2f/%.2f  TEXT: %+.2f/%.2f  "
          "CONSUMED-vs-COVER: %+.2f/%.2f  -> %s" % (
              "", rec["lost_counter_s"], rec["tol_counter_s"],
              rec["lost_text_s"], rec["tol_text_s"],
              rec["lost_consumed_vs_cover_s"], rec["tol_text_s"],
              "RED" if rec["RED"] else "green"))


def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "arm1_shed_then_free"
    print("=" * 78)
    print("NEGATIVE CONTROL FOR THE ARM HARNESS -- arm:", label)
    print("=" * 78)

    base = metric.analyse(label)
    print()
    print("--- BASELINE (the arm's own records) ---")
    show("baseline", base)
    results = {}

    print()
    print("--- FORM A: one engine pass loses 0.56 s (the COUNTER form) ---")
    err_f, changed = forge_counter(label)
    recA = probe(label, err_path=err_f)
    print("   lines altered:", changed)
    show("FORM A", recA)
    okA = recA["lost_counter_s"] > 0.05 and base["lost_counter_s"] <= 0.05
    print("   the SECONDS metric went RED while the baseline is green: %s" % (
        "YES" if okA else "NO -- THE PROBE IS BLIND"))
    results["A"] = okA

    print()
    print("--- FORM B: one parakeet caption line is DELETED (the TEXT form) ---")
    out_f, removed = forge_text(label)
    recB = probe(label, out_path=out_f)
    print("   lines removed:", removed)
    show("FORM B", recB)
    okB = recB["RED"] and not base["RED"]
    print("   the probe went RED while the baseline is green: %s" % (
        "YES" if okB else "NO -- THE PROBE IS BLIND"))
    results["B"] = okB

    print()
    print("--- FORM C: a line is deleted AND left_s is inflated (the COUNTERS "
          "HIDE IT form) ---")
    out_f2, removed2 = forge_text(label)
    err_h, changed_h = forge_hold(label, add_s=3.0)
    recC = probe(label, err_path=err_h, out_path=out_f2)
    print("   lines removed:", removed2, " left_s inflated by:", changed_h)
    show("FORM C", recC)
    okC = (recC["lost_text_s"] > recC["tol_text_s"]
           or recC["lost_consumed_vs_cover_s"] > recC["tol_text_s"])
    print("   the COUNTER metric is GREEN (the counter hides it) but a "
          "TEXT-side metric is RED (TEXT=%+.2f, CONSUMED-vs-COVER=%+.2f, "
          "tol %.2f): %s" % (recC["lost_text_s"],
                             recC["lost_consumed_vs_cover_s"],
                             recC["tol_text_s"], "YES" if okC else "NO"))
    results["C"] = okC

    print()
    print("=" * 78)
    print("ARM-HARNESS NEGATIVE CONTROL: A=%s B=%s C=%s -> %s" % (
        "RED" if results["A"] else "NOT RED",
        "RED" if results["B"] else "NOT RED",
        "RED" if results["C"] else "NOT RED",
        "PASS" if all(results.values()) else "FAIL"))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
