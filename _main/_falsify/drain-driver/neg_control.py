"""THE NEGATIVE CONTROL: a FORGED record where one chunk is missing from the
output set. The probe must go RED on it.

WHY THIS IS A CONTROL AND NOT A TEST OF THE PRODUCT. A probe that cannot go
RED proves nothing. This harness takes a REAL log, removes ONE transcribed
chunk from the OUTPUT side (and adjusts the counters to match a real worker
that had really lost that chunk), and requires the probe to call it RED.

TWO FORMS OF FORGERY, because there are two ways a claim like this can be
fooled:

  A. THE COUNTER FORM. `audio_s` (the streaming decoder's audio clock) is
     reduced by exactly one chunk (0.56 s) while `resampled_samples` is left
     alone. The audio is now IN the input set and OUT of the output set. This
     is the falsifying observation the claim names.

  B. THE TEXT FORM. One caption line is deleted from the history store while
     the counters stay intact -- the shape a "the transcript is missing a
     line" defect would have. The output-set difference must notice.

Usage:
    python neg_control.py            -> prints both arms, rc 0 if BOTH went RED
"""
from __future__ import annotations

import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from runs import load, kv  # noqa: E402
import drain_probe  # noqa: E402

LOG = r"H:\sotto\_main\webview-run.log"
WORK = os.path.join(HERE, "neg")
CHUNK_S = 0.56
TARGET_SR = 16000


def forge_counter_form():
    """A log where one 0.56 s chunk is in the input set and not in the output."""
    os.makedirs(WORK, exist_ok=True)
    out = os.path.join(WORK, "forged-counter.log")
    src = open(LOG, "r", encoding="utf-8", errors="replace")
    dst = open(out, "w", encoding="utf-8", errors="replace")
    changed = 0
    for line in src:
        if "WORKER_STATS tag=final" in line:
            m = re.search(r"audio_s=([0-9.]+)", line)
            if m:
                old = float(m.group(1))
                if old >= CHUNK_S:
                    new = round(old - CHUNK_S, 2)
                    line = line[:m.start(1)] + ("%.2f" % new) + line[m.end(1):]
                    changed += 1
        dst.write(line)
    src.close()
    dst.close()
    return out, changed


def forge_text_form():
    """A history store where one committed line is gone."""
    os.makedirs(WORK, exist_ok=True)
    root = os.path.join(WORK, "history")
    if os.path.isdir(root):
        shutil.rmtree(root)
    shutil.copytree(r"H:\sotto\history", root)
    target = None
    for day in sorted(os.listdir(root)):
        folder = os.path.join(root, day)
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh):
                    if line.startswith("- [") and "route=final" in line:
                        target = (path, i, line)
                        break
            if target:
                break
        if target:
            break
    if target is None:
        return root, 0
    path, i, line = target
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        lines = fh.readlines()
    removed = lines.pop(i)
    with open(path, "w", encoding="utf-8", errors="replace") as fh:
        fh.writelines(lines)
    return root, 1


def probe(log_path, history_root=None):
    """Run the SAME set arithmetic the main probe runs, on the given inputs."""
    if history_root:
        saved = drain_probe.history_entries.__defaults__
        drain_probe.history_entries.__defaults__ = (history_root,)
    try:
        runs, caps = load(log_path)
        rows = drain_probe.run_rows(runs)
        withbg = [r for r in rows if r["mode_known"]]
        verdicts = drain_probe.verdict_rows(withbg)
        reds = [v for v in verdicts if v["RED"]]
        hist = drain_probe.history_entries()
        log_texts = set(t for _ts, _ln, t in caps)
        hist_texts = set(h["text"] for h in hist)
        missing_from_store = len(log_texts - hist_texts)
        missing_from_log = len(hist_texts - log_texts)
        return {
            "runs": len(runs),
            "runs_with_bg": len(withbg),
            "red_runs": len(reds),
            "red_detail": reds[:5],
            "max_excess_s": max([v["excess_s"] for v in verdicts], default=None),
            "hist_lines": len(hist),
            "hist_texts": len(hist_texts),
            "log_texts": len(log_texts),
            "missing_from_store": missing_from_store,
            "missing_from_log": missing_from_log,
        }
    finally:
        if history_root:
            drain_probe.history_entries.__defaults__ = saved


def main():
    print("=" * 78)
    print("NEGATIVE CONTROL -- the probe MUST go RED on a forged record")
    print("=" * 78)

    print()
    print("--- BASELINE (the real log, the real history store) ---")
    base = probe(LOG)
    for k, v in base.items():
        print("   %-22s %s" % (k, v))

    print()
    print("--- ARM A: one 0.56 s chunk removed from the OUTPUT counters ---")
    forged, changed = forge_counter_form()
    print("   forged log:", forged, " lines altered:", changed)
    armA = probe(forged)
    for k, v in armA.items():
        print("   %-22s %s" % (k, v))
    okA = armA["red_runs"] > base["red_runs"]
    print("   ARM A went RED (red_runs %d -> %d): %s" % (
        base["red_runs"], armA["red_runs"], "YES" if okA else "NO -- PROBE IS BLIND"))
    print("   the RED run(s) the probe named:")
    for v in armA["red_detail"]:
        print("      %s" % v)

    print()
    print("--- ARM B: one committed line removed from the HISTORY store ---")
    forged_hist, removed = forge_text_form()
    print("   forged history:", forged_hist, " lines removed:", removed)
    armB = probe(LOG, history_root=forged_hist)
    for k, v in armB.items():
        print("   %-22s %s" % (k, v))
    okB = armB["hist_lines"] == base["hist_lines"] - 1
    print("   ARM B noticed the removal (hist_lines %d -> %d): %s" % (
        base["hist_lines"], armB["hist_lines"], "YES" if okB else "NO"))
    # The set difference that must GROW when a committed line is removed from
    # the STORE: "texts in the store but NOT in the log". A line deleted from
    # the store is one the log never had -> the store-minus-log set SHRINKS by
    # one. The probe must notice that exact one.
    okB2 = (base["missing_from_log"] - armB["missing_from_log"]) == 1
    print("   ARM B store-minus-log set shrank by exactly 1 (%d -> %d): %s" % (
        base["missing_from_log"], armB["missing_from_log"],
        "YES" if okB2 else "NO -- PROBE IS BLIND"))
    okB3 = armB["hist_texts"] == base["hist_texts"] - 1
    print("   ARM B distinct store texts shrank by exactly 1 (%d -> %d): %s" % (
        base["hist_texts"], armB["hist_texts"], "YES" if okB3 else "NO"))

    print()
    print("=" * 78)
    print("NEGATIVE CONTROL RESULT: A=%s B=%s -> %s" % (
        "RED" if okA else "NOT RED", "RED" if (okB and okB2 and okB3) else "NOT RED",
        "PASS" if (okA and okB and okB2 and okB3) else "FAIL"))
    return 0 if (okA and okB and okB2 and okB3) else 1


if __name__ == "__main__":
    sys.exit(main())
