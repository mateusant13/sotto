"""THE PARAKEET DRAIN PROBE -- an INDEPENDENT instrument.

WHAT IT CLAIMS TO MEASURE, and what it does NOT:

  THE CLAIM (owner, 2026-11-01, verbatim):
      "quando a carga liberar, o Sotto recarrega sozinho e processa QUALQUER
       audio nao processado, com o parakeet"

  i.e. every audio chunk that was NOT transcribed while the load-shedder was
  holding the nemotron back IS transcribed later by the background engine, with
  ZERO dropped chunks.

  THE SETS, reconstructed from the log's OWN timestamps and the history store:

    IN  = the audio the worker SAW.  `resampled_samples` is the tap's audio
          after the 16 kHz conversion -- the same PCM the decoder is about to
          see (`worker/sotto_worker.py`, `counters["resampled_samples"]`).
    OUT = the audio that was TRANSCRIBED.
          `audio_s`       -- the STREAMING decoder's own audio clock
                             (`asr.audio_s`, advanced once per decoded chunk).
          `batch_seconds` -- the audio the BACKGROUND (parakeet) pass was
                             HANDED (`engine_switch._start_pass`:
                             `self.batch_seconds += samples / TARGET_SR`).
                             This is an UPPER BOUND on what the background
                             engine consumed: a pass that fails requeues its
                             audio (`engine_policy.park_pass`), so the same
                             seconds can be counted twice.
    WAIT = `left_s` -- the audio still waiting for a motor when the worker
          stopped (`REDUX_SWITCH_STOP left_s=`).

    THE DIFFERENCE THAT MATTERS:
          LOST = IN - OUT - WAIT
    and its parts:
      QUEUE_EVICTED  -- blocks the LIVE queue threw away to make room for the
                        newest (`live_queue.enqueue_live`, the OLDEST goes).
      PARTIAL        -- the <560 ms partial chunk sitting in `buf` when the
                        mode changed (`buf = np.zeros(0)`, `asr_thread`).

  THE FALSIFYING OBSERVATION (named BEFORE any run):
      a chunk in IN, absent from OUT, older than the resume + one drain cycle
      -- i.e. `LOST > 0` after the load-shed window closed.

WHY THIS IS NOT THE AUTHOR'S INSTRUMENT:
  `_main/load-shedding-oracle.py` drives the DECISION CLASS in isolation
  (synthetic pressures, a temp file, the real `load_shedding.py`). This probe
  reads the LIVE records and does the set arithmetic itself. Neither
  `load-shedding-oracle.py` nor `live-queue-drain-oracle.py` is imported,
  executed or copied here.

Read-only. It writes nothing.
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from runs import load, kv  # noqa: E402  (my own parser, same lane)

TARGET_SR = 16000
BLOCK_MS = 100


def fnum(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def history_entries(root=r"H:\sotto\history"):
    """The history store, as a list of dicts. The OUTPUT store, read as data."""
    out = []
    if not os.path.isdir(root):
        return out
    for day in sorted(os.listdir(root)):
        folder = os.path.join(root, day)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(folder, name)
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                for lineno, line in enumerate(fh, 1):
                    m = re.match(r"^-\s+\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$", line)
                    if not m:
                        continue
                    body = m.group(2)
                    prov = {}
                    pm = re.search(r"<!--(.*?)-->", body)
                    if pm:
                        prov = kv(pm.group(1))
                        body = body[:pm.start()].strip()
                    out.append({
                        "date": day,
                        "hour": name[:-3],
                        "time": m.group(1),
                        "text": body,
                        "prov": prov,
                        "path": path,
                        "lineno": lineno,
                    })
    return out


def run_rows(runs):
    """One row per run, with the SET ARITHMETIC done here."""
    rows = []
    for r in runs:
        s = r["stats"]
        st = r["stop"]
        if not s:
            continue
        res = fnum(s.get("resampled_samples"))
        blocks = fnum(s.get("blocks"))
        audio_s = fnum(s.get("audio_s"))
        qevict = fnum(s.get("queue_evicted"), 0.0)
        qdrop = fnum(s.get("queue_drops"), 0.0)
        chunks = fnum(s.get("chunks"), 0.0)
        caps = fnum(s.get("captions"), 0.0)
        rcaps = fnum(s.get("redux_captions"), 0.0)
        kicks = fnum(s.get("redux_kicks"), 0.0)
        segs = fnum(s.get("redux_segments"), 0.0)
        held = fnum(s.get("redux_held_s"), 0.0)
        mode = s.get("redux_mode")
        switches = fnum(s.get("redux_switches"), 0.0)
        batch_s = fnum(st.get("batch_seconds"), 0.0)
        left_s = fnum(st.get("left_s"), 0.0)
        seg_lines = fnum(st.get("segment_lines"), 0.0)
        failures = fnum(st.get("failures"), 0.0)
        deferred = fnum(s.get("redux_deferred"), 0.0)

        in_s = res / float(TARGET_SR) if res is not None else None
        out_s = (audio_s or 0.0) + batch_s
        wait_s = left_s
        lost = None if in_s is None else in_s - out_s - wait_s
        rows.append({
            "pid": r["pid"],
            "rc": r["rc"],
            "spawn_ts": r["spawn_ts"],
            "exit_ts": r["ts_exit"],
            "lineno": r["lineno"],
            "mode": mode,
            "switches": switches,
            "mode_known": mode is not None,
            "in_s": in_s,
            "blocks": blocks,
            "out_stream_s": audio_s,
            "out_bg_s": batch_s,
            "out_s": out_s,
            "wait_s": wait_s,
            "lost_s": lost,
            "evicted_s": (qevict or 0.0) * BLOCK_MS / 1000.0,
            "dropped_s": (qdrop or 0.0) * BLOCK_MS / 1000.0,
            "chunks": chunks,
            "captions_stream": caps,
            "captions_bg": rcaps,
            "kicks": kicks,
            "segments": segs,
            "bg_lines": seg_lines,
            "failures": failures,
            "deferred": deferred,
            "held_s": held,
        })
    return rows


def verdict_rows(rows, mode_filter=None):
    """The runs under test, with the verdict line each one earns."""
    out = []
    for row in rows:
        if mode_filter and row["mode"] not in mode_filter:
            continue
        lost = row["lost_s"]
        if lost is None:
            continue
        # TOLERANCE: the partial chunk in `buf` (<560 ms) plus the block that
        # arrived after the last decode are NOT "lost" -- they never reached the
        # decoder's chunk boundary. Anything above one chunk (0.56 s) plus the
        # evicted blocks is a real loss.
        tolerance = 0.56 + row["evicted_s"] + row["dropped_s"]
        out.append({
            "pid": row["pid"],
            "mode": row["mode"],
            "in_s": round(row["in_s"], 2),
            "out_s": round(row["out_s"], 2),
            "wait_s": round(row["wait_s"], 2),
            "lost_s": round(lost, 2),
            "evicted_s": round(row["evicted_s"], 2),
            "tolerance_s": round(tolerance, 2),
            "excess_s": round(lost - tolerance, 2),
            "RED": (lost - tolerance) > 0.05,
        })
    return out


def main():
    log_path = sys.argv[1] if len(sys.argv) > 1 else r"H:\sotto\_main\webview-run.log"
    runs, caps = load(log_path)
    rows = run_rows(runs)
    withbg = [r for r in rows if r["mode_known"]]
    print("=" * 78)
    print("PARAKEET DRAIN PROBE -- set arithmetic over the LIVE records")
    print("log:", log_path)
    print("=" * 78)
    print("runs total              : %d" % len(runs))
    print("runs with a WORKER_STATS : %d" % len(rows))
    print("runs with background ctr : %d" % len(withbg))
    print("caption events in log    : %d" % len(caps))
    hist = history_entries()
    print("history lines in store   : %d" % len(hist))
    print()

    # ── THE SET DIFFERENCE, per run, for the runs that carried the counters ──
    print("-" * 78)
    print("RUN  mode     IN_s   OUT_s  WAIT_s  LOST_s  EVICT_s  TOL_s  EXCESS  VERDICT")
    print("-" * 78)
    verdicts = verdict_rows(withbg)
    for v, row in zip(verdicts, withbg):
        print("%-5s %-8s %6.2f %7.2f %7.2f %7.2f %8.2f %6.2f %7.2f  %s" % (
            v["pid"], v["mode"], v["in_s"], v["out_s"], v["wait_s"], v["lost_s"],
            v["evicted_s"], v["tolerance_s"], v["excess_s"],
            "RED" if v["RED"] else "green"))
    print("-" * 78)
    reds = [v for v in verdicts if v["RED"]]
    print("runs with a REAL loss (lost_s > tolerance): %d of %d" % (
        len(reds), len(verdicts)))
    print()

    # ── THE POSITIVE CONTROL: a window where nothing was shed ───────────────
    print("-" * 78)
    print("POSITIVE CONTROL -- runs that NEVER shed (mode=stream, switches=0):")
    print("-" * 78)
    pos = [v for v, r in zip(verdicts, withbg)
           if r["mode"] == "stream" and r["switches"] == 0]
    for v in pos:
        print("%-5s IN=%.2f OUT=%.2f WAIT=%.2f LOST=%.2f TOL=%.2f EXCESS=%.2f %s" % (
            v["pid"], v["in_s"], v["out_s"], v["wait_s"], v["lost_s"],
            v["tolerance_s"], v["excess_s"], "RED" if v["RED"] else "green"))
    print("positive-control runs: %d, RED among them: %d" % (
        len(pos), sum(1 for v in pos if v["RED"])))
    print()

    # ── THE HISTORY STORE as the OUTPUT side ────────────────────────────────
    print("-" * 78)
    print("HISTORY STORE -- the committed output")
    print("-" * 78)
    routes = {}
    reasons = {}
    srcs = {}
    for h in hist:
        routes[h["prov"].get("route", "(none)")] = routes.get(h["prov"].get("route", "(none)"), 0) + 1
        reasons[h["prov"].get("reason", "(none)")] = reasons.get(h["prov"].get("reason", "(none)"), 0) + 1
        srcs[h["prov"].get("src", "(none)")] = srcs.get(h["prov"].get("src", "(none)"), 0) + 1
    print("routes :", routes)
    print("reasons:", reasons)
    print("srcs   :", srcs)
    print("history lines per day/hour:")
    per = {}
    for h in hist:
        per[(h["date"], h["hour"])] = per.get((h["date"], h["hour"]), 0) + 1
    for k in sorted(per):
        print("   %s/%s  %d" % (k[0], k[1], per[k]))
    print()

    # ── THE HISTORY vs THE LOG's caption events ─────────────────────────────
    print("-" * 78)
    print("OUTPUT SET DIFFERENCE -- history store vs the log's caption events")
    print("-" * 78)
    log_texts = {}
    for ts, lineno, text in caps:
        log_texts.setdefault(text, []).append((ts, lineno))
    hist_texts = {}
    for h in hist:
        hist_texts.setdefault(h["text"], []).append(h)
    only_log = [t for t in log_texts if t not in hist_texts]
    only_hist = [t for t in hist_texts if t not in log_texts]
    print("distinct texts in the log's BRIDGE_CAPTION_SENT : %d" % len(log_texts))
    print("distinct texts in the history store             : %d" % len(hist_texts))
    print("texts in the log but NOT in the history store   : %d" % len(only_log))
    print("texts in the history but NOT in the log         : %d" % len(only_hist))
    for t in only_hist[:20]:
        print("   history-only:", h_ := t[:90], [ (x['date'],x['hour'],x['time'],x['prov']) for x in hist_texts[t][:2] ])
    print()

    # ── THE SHED EPISODES ────────────────────────────────────────────────────
    print("-" * 78)
    print("SHED EPISODES -- the runs whose mode was 'shed' (muito-alta) or 'batch'")
    print("-" * 78)
    print("run    mode    IN_s  OUTstream  OUTbg  WAIT  kicks  segs  bg_lines  bg_caps")
    for row in withbg:
        if row["mode"] not in ("shed", "batch"):
            continue
        print("%-6s %-7s %5.2f %9.2f %7.2f %5.2f %5d %5d %9d %8d" % (
            row["pid"], row["mode"], row["in_s"], row["out_stream_s"],
            row["out_bg_s"], row["wait_s"], row["kicks"], row["segments"],
            row["bg_lines"], row["captions_bg"]))
    print()
    return rows, verdicts, hist, caps


if __name__ == "__main__":
    main()
