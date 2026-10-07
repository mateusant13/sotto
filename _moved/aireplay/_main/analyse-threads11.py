#!/usr/bin/env python
"""analyse-threads11.py -- fold runs/threads11/summary.json into the table the doc needs."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
S = json.loads((HERE / "runs" / "threads11" / "summary.json").read_text(encoding="utf-8"))
arms = S["arms"]


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


print("=== per-arm ===")
for a in arms:
    print(f"{a['arm']:16} thr={a['threads_intra_op']} rc={a['rc']} load={a.get('load_s')} "
          f"inf={a.get('infer_s')} rtfx_all={a.get('rtfx_all')} steady={a.get('rtfx_steady')} "
          f"first={a.get('rtfx_first_chunk')} cpu_inf={a['cpu_infer']['median_pct']} "
          f"cpu_max={a['cpu_infer']['max_pct']} rss_load={a.get('rss_after_load_mb')} "
          f"pk250={a['rss_peak_poll_250ms_mb']} wset={a['wset_peak_mb']} "
          f"amb={a['ambient_cpu_pct_before_arm']} sys={a['sys_cpu_median_pct_whole_machine']} "
          f"audio={a.get('audio_processed_s')} nseg={a.get('n_chunks')} chars={a.get('text_chars')}")

print("\n=== folded by (instrument, threads) ===")
print(f"{'inst':8} {'thr':>3} {'steady_p1':>9} {'steady_p2':>9} {'steady_med':>10} {'rtfx_all_med':>12} "
      f"{'cpu_inf%':>8} {'cpu_max%':>8} {'rss_load':>9} {'pk250':>8} {'wset':>8} {'load_s':>8} {'amb%':>6}")
for inst in ("fixed", "silence"):
    for th in (1, 2, 4, 6):
        rows = [a for a in arms if a["instrument"] == inst and a["threads_intra_op"] == th]
        st = [r["rtfx_steady"] for r in rows]
        al = [r["rtfx_all"] for r in rows]
        cpu = med([r["cpu_infer"]["median_pct"] for r in rows if r["cpu_infer"]["median_pct"]])
        cmax = max(r["cpu_infer"]["max_pct"] for r in rows if r["cpu_infer"]["max_pct"])
        rl = med([r["rss_after_load_mb"] for r in rows])
        pk = med([r["rss_peak_poll_250ms_mb"] for r in rows])
        ws = med([r["wset_peak_mb"] for r in rows])
        ld = med([r["load_s"] for r in rows])
        amb = med([r["ambient_cpu_pct_before_arm"] for r in rows])
        print(f"{inst:8} {th:>3} {st[0]:>9} {st[1] if len(st) > 1 else '-':>9} {med(st):>10} "
              f"{med(al):>12} {cpu:>8} {cmax:>8} {rl:>9} {pk:>8} {ws:>8} {ld:>8} {amb:>6}")

print("\n=== parity: is the transcript identical across all arms of one instrument? ===")
for inst in ("fixed", "silence"):
    texts = {a["arm"]: a.get("text", "") for a in arms if a["instrument"] == inst}
    ref_arm = sorted(texts)[0]
    ref = texts[ref_arm]
    print(f"{inst}: {len(texts)} arms, ref={ref_arm} chars={len(ref)}")
    for k in sorted(texts):
        t = texts[k]
        same = "IDENTICAL" if t == ref else f"DIFFERS ({len(t)} chars)"
        print(f"   {k:16} {same}")

print("\n=== knee arithmetic (steady-state, median of the 2 passes) ===")
for inst in ("fixed", "silence"):
    m = {}
    for th in (1, 2, 4, 6):
        m[th] = med([a["rtfx_steady"] for a in arms if a["instrument"] == inst and a["threads_intra_op"] == th])
    print(f"{inst}: " + " | ".join(
        f"{a}->{b}: {m[b] / m[a]:.3f}x" for a, b in ((1, 2), (2, 4), (4, 6))))
    print(f"{inst}: peak = {max(m, key=lambda k: m[k])} threads "
          f"(2->4 {m[4] / m[2]:+.2f}x, 4->6 {m[6] / m[4]:+.2f}x, 1->4 {m[4] / m[1]:+.2f}x)")

print("\n=== RSS spread across thread counts (same instrument) ===")
for inst in ("fixed", "silence"):
    rl = [a["rss_after_load_mb"] for a in arms if a["instrument"] == inst]
    pk = [a["rss_peak_poll_250ms_mb"] for a in arms if a["instrument"] == inst]
    ws = [a["wset_peak_mb"] for a in arms if a["instrument"] == inst]
    print(f"{inst}: after_load {min(rl)}-{max(rl)} (spread {max(rl) - min(rl):.1f} MB) | "
          f"pk250 {min(pk)}-{max(pk)} | wset {min(ws)}-{max(ws)}")

print("\n=== first chunk vs steady (is the first call atypical?) ===")
for a in arms:
    print(f"{a['arm']:16} first={a.get('rtfx_first_chunk')} steady={a.get('rtfx_steady')} "
          f"ratio={round(a['rtfx_first_chunk'] / a['rtfx_steady'], 2) if a.get('rtfx_first_chunk') and a.get('rtfx_steady') else None}")
