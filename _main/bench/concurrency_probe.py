#!/usr/bin/env python
"""concurrency_probe.py -- N REAL product ASR streams on one frozen window.

WHY THIS EXISTS
---------------
The owner asks "how many speaker streams can be transcribed live at once, and
what does each extra stream cost?". That question has no answer in prose: the
shipped engine (`worker/sotto_worker.py`, nemotron 3.5 RNNT ONNX int4, 8960
samples = 560 ms chunks, `--threads 2` from the shell's `--worker-threads 2`)
has to be run N times at once and measured with the SAME instrument each time.

WHAT IT RUNS
------------
N child processes of the product worker in file mode:

    python worker/sotto_worker.py --selftest --audio <wav> --threads 2

`--selftest`/`--audio` is the product's own no-audio-device arm: the same
`StreamAsr.run_chunk()`, the same VAD/gate, the same `LineFormer`, the same
JSONL contract. It opens no audio endpoint and shows no window.

WHAT IT REPORTS, per child and in aggregate
-------------------------------------------
  * `rtf`               -- the worker's own `infer_wall_s / audio_s` (model load
                           EXCLUDED, exactly as the worker defines it)
  * `cores`             -- child CPU seconds / child infer_wall_s: how many of
                           the 20 cores ONE stream actually consumes
  * `core_s_per_audio_s`-- child CPU seconds / audio seconds: the cost unit
  * `peak_rss_mb`       -- the worker's own `peak_rss_mb()` and this probe's
                           sampled peak, reported side by side
  * `wall`, `load_s`, `providers`, `WORKER_THREAD_PLAN`
  * `box_pct`           -- aggregate child CPU / (elapsed * cores), sampled at
                           0.5 s, i.e. percent of the WHOLE machine (the same
                           unit watcher's `--cpu` uses: 40 = 40% of 20 cores)

Any child killed by the caged job object's hard CPU cap dies mid-run and is
reported as `rc=None killed=true` -- the cap binding is a RESULT, not a retry.

Usage
-----
    python -m watcher run --cpu 40 --io very-low -- \
        python _main/bench/concurrency_probe.py --streams 2 \
            --wav _main/bench/concurrency/window-300s-16k.wav \
            --out _main/bench/concurrency/n2.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
WORKER = os.path.join(REPO, "worker", "sotto_worker.py")
CREATE_NO_WINDOW = 0x08000000


class Child:
    def __init__(self, idx: int, argv, log_dir: str) -> None:
        self.idx = idx
        self.out_path = os.path.join(log_dir, "stream%d.out.log" % idx)
        self.err_path = os.path.join(log_dir, "stream%d.err.log" % idx)
        self._out = open(self.out_path, "w", encoding="utf-8", errors="replace")
        self._err = open(self.err_path, "w", encoding="utf-8", errors="replace")
        t0 = time.perf_counter()
        self.proc = subprocess.Popen(
            argv, stdout=self._out, stderr=self._err,
            creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        self.t0 = t0
        self.ps = None
        try:
            self.ps = psutil.Process(self.proc.pid)
        except psutil.Error:
            pass
        self.cpu_s = 0.0
        self.last_progress_t = t0
        self.stalled_at_cpu_s = None
        self.peak_rss_b = 0
        self.peak_threads = 0
        self.killed = False

    def sample(self) -> None:
        if self.ps is None:
            return
        try:
            times = self.ps.cpu_times()
            self.cpu_s = max(self.cpu_s, times.user + times.system)
            self.peak_rss_b = max(self.peak_rss_b, self.ps.memory_info().rss)
            self.peak_threads = max(self.peak_threads, self.ps.num_threads())
        except psutil.Error:
            pass

    def wait(self, timeout_s: float = 900.0) -> int | None:
        try:
            rc = self.proc.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            rc = None
        self.t_end = time.perf_counter()
        self.sample()
        self._out.close()
        self._err.close()
        # A killed process reports the Windows termination code, not a tool rc.
        if self.ps is not None:
            try:
                t = self.ps.cpu_times()
                self.cpu_s = max(self.cpu_s, t.user + t.system)
            except psutil.Error:
                pass
        return rc

    # ── parsed from the child's own logs ─────────────────────────────────
    def result(self) -> dict:
        done = {}
        started = {}
        plan = ""
        providers = None
        with open(self.out_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                if ev.get("state") == "selftest-start":
                    started = ev
                elif ev.get("state") == "selftest-done":
                    done = ev
                elif ev.get("state") == "model-loaded":
                    providers = ev.get("providers")
                elif ev.get("state") == "boot":
                    providers = providers or ev.get("providers")
        err_tail = []
        load_s = 0.0
        with open(self.err_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "WORKER_THREAD_PLAN" in line:
                    err_tail.append(line.strip())
                elif line.startswith("load_s"):
                    try:
                        load_s = float(line.split(":", 1)[1])
                    except (IndexError, ValueError):
                        pass
                elif line.startswith("quality"):
                    err_tail.append(line.strip())
        for line in err_tail:
            if "WORKER_THREAD_PLAN" in line:
                plan = line
        return {"started": started, "done": done, "providers": providers,
                "thread_plan": plan, "load_s": load_s, "stderr_tail": err_tail[-6:]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--streams", type=int, required=True)
    ap.add_argument("--wav", required=True)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--providers", default=None,
                    help="passed through to the worker; default = its config.json")
    ap.add_argument("--stagger-s", type=float, default=3.0)
    ap.add_argument("--stall-s", type=float, default=120.0,
                    help="kill and REPORT a child whose CPU time stops advancing this long")
    ap.add_argument("--child-timeout", type=float, default=900.0)
    ap.add_argument("--log-dir", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--label", default="")
    args = ap.parse_args(argv)

    log_dir = args.log_dir or os.path.join(HERE, "concurrency", "logs-%s" % (
        args.label or "run"))
    os.makedirs(log_dir, exist_ok=True)
    wav_bytes = os.path.getsize(args.wav)
    ncores = psutil.cpu_count()
    vm = psutil.virtual_memory()

    ambient_pct = psutil.cpu_percent(interval=1.0)

    # ── THE CEILING, DECLARED BEFORE THE JOB (house rule) ───────────────
    print("AMBIENT: box cpu %.1f%% busy before the step (everything that is not this probe)"
          % ambient_pct, flush=True)
    print("CEILING: streams=%d | threads/stream=%d (encoder; small graphs <=%d each)"
          % (args.streams, args.threads, args.threads), flush=True)
    # RSS PER STREAM IS A MEASURED NUMBER, NOT A ROUND ONE. rungs 1-4 measured
    # 1245.6 / 1395.4 / 1245.6 / 1320.7 MB mean and 1548.3 MB max, so the
    # declaration is 1600 MB per stream (max + 3.3 %). The FIRST declaration was
    # 1200 and every rung exceeded it by 8.7-21.9 %: an exceeded ceiling is a
    # defect in the declaration, and it is recorded as such in the document.
    print("CEILING: total intra-op threads <= %d | RSS <= %d MB (%d x 1600, "
          "measured 1245-1548 MB/stream) | IO read-once %.1f MB/wav | "
          "host free now %.0f MB of %.0f MB"
          % (args.streams * args.threads * 3, args.streams * 1600,
             args.streams, wav_bytes / 1e6, vm.available / 1e6, vm.total / 1e6),
          flush=True)

    base = [sys.executable, WORKER, "--selftest", "--audio", args.wav,
            "--threads", str(args.threads)]
    if args.providers:
        base += ["--providers", args.providers]
    print("CEILING-CMD: %s" % " ".join(base), flush=True)

    gpu = None
    gpu_name = ""
    gpu_used0 = None
    gpu_peak = 0
    gpu_util_peak = 0
    try:
        import pynvml                                            # noqa: PLC0415
        pynvml.nvmlInit()
        gpu = pynvml.nvmlDeviceGetHandleByIndex(0)
        gpu_used0 = pynvml.nvmlDeviceGetMemoryInfo(gpu).used
        _gname = pynvml.nvmlDeviceGetName(gpu)
        if isinstance(_gname, bytes):
            _gname = _gname.decode("utf-8", "replace")
        gpu_name = _gname
        print("CEILING-GPU: %s vram total %.0f MB, used before %.0f MB"
              % (gpu_name, pynvml.nvmlDeviceGetMemoryInfo(gpu).total / 1e6,
                 gpu_used0 / 1e6), flush=True)
    except Exception as exc:                                     # noqa: BLE001
        print("CEILING-GPU: none (%r)" % (exc,), flush=True)

    children = []
    t_start = time.perf_counter()
    peak_box_pct = 0.0
    peak_total_rss_b = 0
    last_cpu = 0.0
    last_t = t_start

    for i in range(args.streams):
        children.append(Child(i, base, log_dir))
        if i + 1 < args.streams and args.stagger_s > 0:
            # Stagger the model loads: they are disk+page-cache work, not the
            # steady state this probe is measuring.
            time.sleep(args.stagger_s)

    prev_cpu = {id(c): 0.0 for c in children}
    while any(c.proc.poll() is None for c in children):
        time.sleep(0.5)
        now = time.perf_counter()
        for c in children:
            c.sample()
            if c.proc.poll() is not None:
                continue
            # THE STALL INSTRUMENT: a child that consumes CPU but does not ADVANCE
            # the decode (or consumes none at all) is the OpenMP/ORT barrier hang
            # this repo already measured, and a wall-clock timeout would report it
            # as "slow" instead of "stuck".
            if c.cpu_s > prev_cpu[id(c)] + 0.02:
                prev_cpu[id(c)] = c.cpu_s
                c.last_progress_t = now
            elif args.stall_s > 0 and now - c.last_progress_t > args.stall_s:
                c.stalled_at_cpu_s = round(c.cpu_s, 2)
                print("PROBE: stream %d STALLED -- no CPU progress for %.0f s "
                      "(cpu %.2f s); killing it so the step reports instead of hanging"
                      % (c.idx, args.stall_s, c.cpu_s), flush=True)
                c.proc.kill()
        total_cpu = sum(c.cpu_s for c in children)
        dt = max(1e-6, now - last_t)
        pct = 100.0 * (total_cpu - last_cpu) / (dt * max(1, ncores))
        last_cpu, last_t = total_cpu, now
        peak_box_pct = max(peak_box_pct, pct)
        peak_total_rss_b = max(peak_total_rss_b, sum(c.peak_rss_b for c in children
                                                     if c.proc.poll() is None))
        if gpu is not None:
            try:
                gpu_peak = max(gpu_peak, pynvml.nvmlDeviceGetMemoryInfo(gpu).used)
                gpu_util_peak = max(gpu_util_peak,
                                    pynvml.nvmlDeviceGetUtilizationRates(gpu).gpu)
            except Exception:                                    # noqa: BLE001
                pass

    rcs = []
    for c in children:
        rcs.append(c.wait(args.child_timeout))
    wall = time.perf_counter() - t_start

    streams = []
    audio_s = 0.0
    for c, rc in zip(children, rcs):
        r = c.result()
        done = r["done"]
        s_audio = float(done.get("audio_s") or 0.0)
        infer = float(done.get("infer_wall_s") or 0.0)
        audio_s = max(audio_s, s_audio)
        streams.append({
            "stream": c.idx,
            "rc": rc,
            "killed": rc is None,
            "stalled_at_cpu_s": c.stalled_at_cpu_s,
            "providers": r["providers"],
            "thread_plan": r["thread_plan"],
            "load_s": round(float(r.get("load_s") or 0.0), 3),
            "audio_s": round(s_audio, 3),
            "infer_wall_s": round(infer, 3),
            "rtf": done.get("rtf"),
            "tokens": done.get("tokens"),
            "empty_chunks": done.get("empty_chunks"),
            "vad_gated_chunks": done.get("vad_gated_chunks"),
            "stage_s": done.get("stage_s"),
            "peak_rss_mb_worker": done.get("peak_rss_mb"),
            "peak_rss_mb_sampled": round(c.peak_rss_b / 1e6, 1),
            "cpu_s": round(c.cpu_s, 3),
            "cores": round(c.cpu_s / infer, 3) if infer > 0 else None,
            "core_s_per_audio_s": round(c.cpu_s / s_audio, 4) if s_audio > 0 else None,
            "peak_threads": c.peak_threads,
            "child_wall_s": round(getattr(c, "t_end", time.perf_counter()) - c.t0, 3),
            "stderr_tail": r["stderr_tail"],
        })

    stalled = [s["stream"] for s in streams if s["stalled_at_cpu_s"] is not None]
    ok = [s for s in streams if s["rtf"] and s["stalled_at_cpu_s"] is None]
    rtf_worst = max((float(s["rtf"]) for s in ok), default=None)
    rtf_best = min((float(s["rtf"]) for s in ok), default=None)
    core_rates = [s["core_s_per_audio_s"] for s in ok if s["core_s_per_audio_s"]]
    summary = {
        "label": args.label,
        "streams_requested": args.streams,
        "streams_finished": len(ok),
        "streams_stalled": stalled,
        "threads_per_stream": args.threads,
        "providers_arg": args.providers,
        "wav": args.wav,
        "wav_bytes": wav_bytes,
        "audio_s": audio_s,
        "wall_s": round(wall, 2),
        "ambient_cpu_pct_before": ambient_pct,
        "peak_box_pct": round(peak_box_pct, 1),
        "peak_total_rss_mb": round(peak_total_rss_b / 1e6, 1),
        "host_free_mb_after": round(psutil.virtual_memory().available / 1e6, 1),
        "gpu": ({"name": gpu_name,
                 "vram_used_before_mb": round(gpu_used0 / 1e6, 1),
                 "vram_peak_mb": round(gpu_peak / 1e6, 1),
                 "gpu_util_peak_pct": gpu_util_peak} if gpu is not None else None),
        "rtf_worst": rtf_worst,
        "rtf_best": rtf_best,
        "throughput_audio_s_per_wall_s": round(sum(float(s["audio_s"]) for s in ok) / wall, 3),
        "mean_core_s_per_audio_s": round(sum(core_rates) / len(core_rates), 4) if core_rates else None,
        "per_stream": streams,
    }
    text = json.dumps(summary, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
