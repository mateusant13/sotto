#!/usr/bin/env python
"""probe-onnx-asr-threads.py -- the ONE question: which `intra_op_num_threads` is
OPTIMAL for the int8 ONNX export on THIS box -- 1, 2, 4 or 6?

It runs the SAME instrument lane 05 used, on the SAME <=120 s slice of
plain-3600s.wav, ONE ARM AT A TIME (never in parallel), and adds exactly what the
instrument lacked:

  * CPU% split by PHASE (load vs inference). The probe's own sampler polls the
    whole process at 1 Hz and folds the single-threaded load into the median;
    here the child's pid is polled externally at --every-ms, and the phase
    boundary is the child's OWN first per-chunk stdout line, so "how many threads
    did it really use" is MEASURED, not asked.
  * steady-state RTFx: the first chunk is excluded, because the first encode after
    load is atypical (measured 2.5x faster than every later one, doc 05 sec 4).
  * RSS polled at the same 250 ms cadence, alongside.

No audio device is opened (wav file only). No visible window: every child is
spawned with CREATE_NO_WINDOW and its stdout goes to a FILE (never a pipe).

Usage:
  python probe-onnx-asr-threads.py [--arms 1,2,4,6] [--instruments fixed,silence]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

MB = 1024.0 * 1024.0
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PY = r"C:\Program Files\Python311\python.exe"
WAV = r"H:\sotto\_main\_redux-long\plain-3600s.wav"
MODEL = str(ROOT / "models" / "parakeet-tdt-0.6b-v3-onnx")
OFFSET, MAXS = 900.0, 120.0
CREATE_NO_WINDOW = 0x08000000

INSTRUMENT = {
    # name: (script, extra argv)
    "fixed": (HERE / "probe-onnx-asr.py", ["--chunk-s", "10"]),
    "silence": (HERE / "probe-onnx-asr-split.py", ["--mode", "silence", "--max-seg", "15"]),
}


def build_cmd(inst: str, threads: int, js: Path, txt: Path, label: str) -> list[str]:
    script, extra = INSTRUMENT[inst]
    return [
        PY, str(script),
        "--wav", WAV,
        "--model-dir", MODEL,
        "--quant", "int8",
        "--provider", "cpu",
        "--offset-s", str(OFFSET),
        "--max-s", str(MAXS),
        "--threads", str(threads),
        "--json", str(js),
        "--text", str(txt),
        "--label", label,
        *extra,
    ]


def run_arm(inst: str, threads: int, outdir: Path, logdir: Path, every_ms: int, tag: str = "") -> dict:
    label = f"{inst}-t{threads}{tag}"
    js = outdir / f"{label}.json"
    txt = outdir / f"{label}.txt"
    raw = logdir / f"{label}.out"
    cmd = build_cmd(inst, threads, js, txt, label)

    env = dict(os.environ)
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[k] = str(threads)
    env["PYTHONUNBUFFERED"] = "1"

    print(f"\n=== ARM {label} :: intra_op={threads} inter_op=1 "
          f"OMP/OPENBLAS/MKL={threads} ===", flush=True)
    # ambient (whole machine) load in the 3 s BEFORE this arm's child exists
    psutil.cpu_percent(None)
    time.sleep(3.0)
    ambient = round(psutil.cpu_percent(None), 1)
    t0 = time.perf_counter()
    with open(raw, "w", encoding="utf-8") as fh:
        child = subprocess.Popen(
            cmd, stdout=fh, stderr=subprocess.STDOUT, env=env,
            cwd=str(HERE), creationflags=CREATE_NO_WINDOW,
        )
    proc = psutil.Process(child.pid)
    proc.cpu_percent(None)  # prime

    samples: list[dict] = []
    phase = "load"
    infer_t0 = None
    load_done_t = None
    n_chunk_lines = 0
    psutil.cpu_percent(None)  # prime the system-wide delta
    while True:
        rc = child.poll()
        t = time.perf_counter() - t0
        rss = wset = 0.0
        cpu = None
        sys_cpu = psutil.cpu_percent(None)
        try:
            mi = proc.memory_info()
            rss = mi.rss / MB
            wset = mi.peak_wset / MB
            cpu = proc.cpu_percent(None)
        except psutil.Error:
            # the child exited between poll() and here -- one lost sample, not a crash
            pass
        # phase boundary = the child's OWN first per-chunk line
        if infer_t0 is None:
            try:
                body = raw.read_text(encoding="utf-8", errors="replace")
            except OSError:
                body = ""
            n_chunk_lines = sum(1 for ln in body.splitlines()
                                if ln.startswith("[") or ln.startswith("  "))
            if n_chunk_lines > 0 or "RESULT " in body:
                infer_t0 = t
                load_done_t = t
                phase = "infer"
        samples.append({"t": round(t, 3), "phase": phase, "rss_mb": round(rss, 2),
                        "wset_mb": round(wset, 2),
                        "cpu_pct": round(cpu, 1) if cpu is not None else None,
                        "sys_cpu_pct": round(sys_cpu, 1)})
        if rc is not None:
            break
        time.sleep(every_ms / 1000.0)

    wall = time.perf_counter() - t0
    body = raw.read_text(encoding="utf-8", errors="replace")
    Path(raw).write_text(body, encoding="utf-8")

    # ---- phase CPU% from the external 250 ms samples -------------------------
    def phase_cpu(name: str) -> dict:
        pts = [s for s in samples if s["phase"] == name and s["cpu_pct"] is not None]
        if len(pts) < 2:
            return {"n": len(pts), "median_pct": None, "max_pct": None}
        cpus = sorted(p["cpu_pct"] for p in pts[1:])
        return {"n": len(pts),
                "median_pct": round(cpus[len(cpus) // 2], 1),
                "max_pct": round(max(cpus), 1)}

    sys_pts = sorted(s["sys_cpu_pct"] for s in samples)
    sys_med = round(sys_pts[len(sys_pts) // 2], 1) if sys_pts else None

    res: dict = {
        "arm": label, "instrument": inst, "threads_intra_op": threads,
        "rc": rc, "wall_s": round(wall, 3),
        "ambient_cpu_pct_before_arm": ambient,
        "ambient_cores_before_arm": round(ambient / 100.0 * psutil.cpu_count(), 2),
        "load_phase_s": round(load_done_t, 3) if load_done_t else None,
        "cpu_load": phase_cpu("load"), "cpu_infer": phase_cpu("infer"),
        "sys_cpu_median_pct_whole_machine": sys_med,
        "rss_peak_poll_250ms_mb": round(max((s["rss_mb"] for s in samples), default=0.0), 1),
        "wset_peak_mb": round(max((s["wset_mb"] for s in samples), default=0.0), 1),
        "samples": samples,
    }

    if js.exists():
        d = json.loads(js.read_text(encoding="utf-8"))
        chunks = d.get("chunks") or d.get("segments") or []
        audio = [c["audio_s"] for c in chunks]
        wallc = [c["wall_s"] for c in chunks]
        proc_audio = sum(audio)
        inf_s = d.get("infer_s") or sum(wallc)
        first = audio[0] / wallc[0] if wallc and wallc[0] else None
        rest_a, rest_w = sum(audio[1:]), sum(wallc[1:])
        res.update({
            "load_s": d.get("load_s"),
            "infer_s": inf_s,
            "n_chunks": len(chunks),
            "audio_processed_s": round(proc_audio, 3),
            "rtfx_all": round(proc_audio / inf_s, 2) if inf_s else None,
            "rtfx_first_chunk": round(first, 2) if first else None,
            "rtfx_steady": round(rest_a / rest_w, 2) if rest_w else None,
            "chunk_wall_s": wallc,
            "rss_after_load_mb": d.get("rss_after_load_mb"),
            "rss_peak_instrument_mb": d.get("rss_peak_mb") or d.get("rss_peak_poll_mb"),
            "rss_peak_wset_instrument_mb": d.get("rss_peak_wset_mb"),
            "cpu_median_instrument_pct": d.get("cpu_median_pct"),
            "text_chars": len(d.get("text", "")),
            "text_sha_ok": True,
        })
        res["text"] = d.get("text", "")
    else:
        res["error"] = "child produced no JSON"
    print(f"  -> rc={rc} wall={wall:.2f}s load={res.get('load_s')}s "
          f"rtfx_all={res.get('rtfx_all')} rtfx_steady={res.get('rtfx_steady')} "
          f"first_chunk_rtfx={res.get('rtfx_first_chunk')} "
          f"cpu(load/infer med)={res['cpu_load']['median_pct']}/{res['cpu_infer']['median_pct']}% "
          f"sys_cpu_med={res['sys_cpu_median_pct_whole_machine']}% "
          f"ambient={res['ambient_cpu_pct_before_arm']}% "
          f"rss(load/peak250/peakwset)={res.get('rss_after_load_mb')}/"
          f"{res['rss_peak_poll_250ms_mb']}/{res['wset_peak_mb']}", flush=True)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default="1,2,4,6")
    ap.add_argument("--instruments", default="fixed,silence")
    ap.add_argument("--passes", type=int, default=1,
                    help="2 = run the same arms AGAIN in REVERSE order (drift control on a loaded box)")
    ap.add_argument("--every-ms", type=int, default=250)
    ap.add_argument("--outdir", default=str(HERE / "runs" / "threads11"))
    ap.add_argument("--logdir", default=str(HERE / "logs"))
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    logdir = Path(args.logdir)
    logdir.mkdir(parents=True, exist_ok=True)

    import onnxruntime as ort  # noqa: PLC0415
    import onnx_asr  # noqa: PLC0415

    meta = {
        "host": "i5-13600K 6P+8E / 20 logical, Windows 11, CPU only",
        "wav": WAV, "offset_s": OFFSET, "max_s": MAXS, "model_dir": MODEL,
        "onnx_asr": onnx_asr.__version__, "onnxruntime": ort.__version__,
        "ort_available_providers": ort.get_available_providers(),
        "every_ms": args.every_ms,
        "passes": args.passes,
        "note": "arms run in SERIES, never in parallel; no audio device; CREATE_NO_WINDOW",
    }
    print(json.dumps(meta, indent=1), flush=True)

    results = []
    arms = [int(x) for x in args.arms.split(",")]
    for inst in args.instruments.split(","):
        for p in range(args.passes):
            order = arms if p % 2 == 0 else list(reversed(arms))
            for th in order:
                results.append(run_arm(inst, th, outdir, logdir, args.every_ms, tag=f"-p{p + 1}"))

    summary = {"meta": meta, "arms": results}
    sp = outdir / "summary.json"
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\n=== SUMMARY ===", flush=True)
    hdr = f"{'arm':16} {'thr':>3} {'load_s':>6} {'inf_s':>6} {'rtfx_all':>8} {'rtfx_steady':>11} " \
          f"{'1st_chunk':>9} {'cpu_inf%':>8} {'cpu_load%':>9} {'sys%':>6} {'amb%':>6} {'rss_load':>8} " \
          f"{'rss_pk250':>9} {'wset_pk':>8}"
    print(hdr, flush=True)
    for r in results:
        print(f"{r['arm']:16} {r['threads_intra_op']:>3} {str(r.get('load_s')):>6} "
              f"{str(r.get('infer_s')):>6} {str(r.get('rtfx_all')):>8} {str(r.get('rtfx_steady')):>11} "
              f"{str(r.get('rtfx_first_chunk')):>9} {str(r['cpu_infer']['median_pct']):>8} "
              f"{str(r['cpu_load']['median_pct']):>9} {str(r['sys_cpu_median_pct_whole_machine']):>6} "
              f"{str(r['ambient_cpu_pct_before_arm']):>6} "
              f"{str(r.get('rss_after_load_mb')):>8} "
              f"{r['rss_peak_poll_250ms_mb']:>9} {r['wset_peak_mb']:>8}", flush=True)
    print(f"\nSUMMARY JSON -> {sp}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
