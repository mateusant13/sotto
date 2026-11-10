"""live-engine-provider-ab — the LIVE (streaming) engine on CPU vs CUDA: cost, not quality.

ANSWERED QUESTION (lane GpuLiveEngine, 2026-11-09): which execution provider should
the STREAMING engine (`StreamAsr`: encoder + decoder + joint, 560 ms chunks) run on,
and is the answer the one the shipped code actually takes?

WHY ONE ARM PER PROCESS. Model load seconds, peak RSS and the process's CPU% are
per-PROCESS numbers. A run that built both arms in one interpreter would attribute
the first arm's CUDA arena and its warmed DLLs to the second arm, and the second
arm's numbers would be the first arm's leftovers. So `--arm` builds exactly one
`StreamAsr` in a fresh interpreter; `--compare a.json b.json` prints the table.

WHAT IS MEASURED, and why each one is here:
  * load_s          `StreamAsr.__init__` wall time — the three `InferenceSession`
                    creations, i.e. what the owner waits for at panel-open
                    (`load_phases_s` splits it per graph).
  * frontend_s      `og.Model` + the streaming processor, built lazily on first
                    `asr.sp`. Reported apart because it is NOT the provider's cost.
  * p50/p95/max_ms  per-chunk wall time of `run_chunk` (one 8960-sample = 560 ms
                    chunk), over the WARM passes (pass 1 dropped: the first chunk
                    of a CUDA session pays cuDNN heuristic selection / arena
                    growth, which is a load cost, not a steady-state one).
                    Pass 1 is still recorded as `pass1_p50_ms`.
  * rtf             decode_wall_s / audio_s (<1 means faster than real time).
  * cpu_pct         process CPU time / wall time over the warm decode loop,
                    in percent of ONE core (so 200 % = two cores saturated).
  * rss_peak_mib    `PeakWorkingSetSize` of this process at the end.
  * gpu_mib         nvidia-smi total used AND this pid's used, before load, after
                    load, after the front end, at the end.
  * text_sha256     the transcript, hashed. The whole comparison is worthless if
                    the two arms disagree about the TEXT: a provider that changes
                    the words is a defect, not an optimisation, and `--compare`
                    says so and exits non-zero.

THE PROVIDER IS RESOLVED BY THE SHIPPED RESOLVER (`choose_providers`), not by a
literal list written here, so the arm exercises the code the product runs.

USAGE (from H:/sotto):
  PYTHONPATH=I:/!watcher python -m watcher run --cpu 40 -- python _main/live-engine-provider-ab.py --arm cpu  --out _main/_cache/provider-ab-cpu.json
  PYTHONPATH=I:/!watcher python -m watcher run --cpu 40 -- python _main/live-engine-provider-ab.py --arm cuda --out _main/_cache/provider-ab-cuda.json
  python _main/live-engine-provider-ab.py --compare _main/_cache/provider-ab-cpu.json _main/_cache/provider-ab-cuda.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
import traceback

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(REPO, "worker")
CONFIG = os.path.join(WORKER, "config.json")
DEFAULT_AUDIO = os.path.join(REPO, "_main", "fixtures", "stack-compare", "ptbr-radio-14s.wav")

# The SHORT names `choose_providers` accepts (its `aliases` table), one entry per
# arm. `cuda` keeps the CPU as the fallback, exactly like the shipped config.
ARMS = {
    "cpu": ["cpu"],
    "cuda": ["cuda", "cpu"],
}

CREATE_NO_WINDOW = 0x08000000

#: O LARGADOR da casa. `CREATE_NO_WINDOW` sozinho e' a metade barata da guarda:
#: sem `startupinfo`/`STARTF_USESHOWWINDOW` um filho de consola nascido de um pai
#: SEM consola recebe uma NOVA (o Windows Terminal a pinta), e o censo
#: `console-window-audit` nomeia esse sitio `WEAK-FLAG`. Importado pelo caminho
#: e pelo nome: e' a forma que esta arvore usa para um modulo com HIFEN.
def _load_hidden_launch():
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "hidden-launch.py")
    if not os.path.isfile(path):
        return None
    spec = importlib.util.spec_from_file_location("hidden_launch", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_HL = _load_hidden_launch()


def _hidden(argv, timeout=None):
    """(rc, out, err) com a guarda INTEIRA -- pelo helper da casa quando existe."""
    if _HL is not None:
        return _HL.run(argv, capture=True, timeout=timeout)
    si = None
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                          creationflags=CREATE_NO_WINDOW if os.name == "nt" else 0,
                          startupinfo=si)
    return proc.returncode, proc.stdout, proc.stderr


# ── GPU meters ────────────────────────────────────────────────────────────────
def gpu_mib(pid: int):
    """(total_used_mib, this_pid_mib) — None for any field that could not be read.

    `nvidia-smi` is started with CREATE_NO_WINDOW (this tree's rule: no console on
    the owner's screen, ever). A failure here is reported as None, never as 0: an
    unreadable memory counter is not "no memory used".

    MEASURED 2026-11-09 on this box: `--query-compute-apps=used_memory` answers
    `[N/A]` for EVERY process (WDDM), so `pid_mib` is legitimately None here and
    the per-process number cannot be read. The proof of use is then the TOTAL
    delta plus `utilization.gpu` during the decode — see `GpuSampler`.
    """
    out = {"total_mib": None, "pid_mib": None, "util_pct": None, "pid_listed": None}
    try:
        rc, out1, _err1 = _hidden(
            ["nvidia-smi", "--query-gpu=memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"], timeout=20)
        if rc == 0 and out1.strip():
            parts = [p.strip() for p in out1.strip().splitlines()[0].split(",")]
            if parts and parts[0].isdigit():
                out["total_mib"] = int(parts[0])
            if len(parts) > 1 and parts[1].isdigit():
                out["util_pct"] = int(parts[1])
    except Exception:                                            # noqa: BLE001
        pass
    try:
        rc2, out2, _err2 = _hidden(
            ["nvidia-smi", "--query-compute-apps=pid,used_memory",
             "--format=csv,noheader,nounits"], timeout=20)
        if rc2 == 0:
            for line in out2.splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 2 and parts[0].isdigit() and int(parts[0]) == pid:
                    out["pid_listed"] = True
                    if parts[1].isdigit():
                        out["pid_mib"] = int(parts[1])
                    break
    except Exception:                                            # noqa: BLE001
        pass
    return out


class GpuSampler:
    """Sample total VRAM + GPU utilization in the background, every 150 ms.

    A single before/after reading proves the memory moved; the SERIES proves the
    ENGINE moved it — utilization above zero WHILE the chunks are decoding is the
    claim "this ran on the GPU", and a CPU-only session cannot produce it.
    """

    def __init__(self, pid: int, period_s: float = 0.15):
        import threading

        self.pid = pid
        self.period_s = period_s
        self.samples = []
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._run, name="gpu-sampler", daemon=True)

    def _run(self):
        while not self._stop.is_set():
            self.samples.append(gpu_mib(self.pid))
            self._stop.wait(self.period_s)

    def start(self):
        self._t.start()
        return self

    def stop(self):
        self._stop.set()
        self._t.join(timeout=5)
        utils = [s["util_pct"] for s in self.samples if s.get("util_pct") is not None]
        mems = [s["total_mib"] for s in self.samples if s.get("total_mib") is not None]
        return {
            "samples": len(self.samples),
            "util_max_pct": max(utils) if utils else None,
            "util_mean_pct": round(sum(utils) / len(utils), 1) if utils else None,
            "util_nonzero_samples": sum(1 for u in utils if u > 0),
            "total_mib_max": max(mems) if mems else None,
            "total_mib_min": min(mems) if mems else None,
        }


# ── the arm ───────────────────────────────────────────────────────────────────
def run_arm(arm: str, audio: str, npasses: int, out_path: str, threads: int = 0) -> int:
    sys.path.insert(0, WORKER)
    import psutil

    import sotto_worker as sw

    # MUST run before onnxruntime is imported: it is what puts cublasLt64_13 and
    # cuDNN 9 (which ship inside the `nvidia-*` wheels) on the DLL search path.
    # Without it a CUDA EP is REGISTERED and cannot dlopen — the silent CPU
    # fallback this whole measurement exists to rule out.
    sw._add_cuda_dll_dirs()

    import numpy as np
    import onnxruntime as ort
    import soundfile as sf

    cfg = json.load(open(CONFIG, encoding="utf-8"))
    model_dir = os.path.join(WORKER, cfg["model"]["dir"])
    use_vad = bool(cfg["model"].get("use_vad", True))
    lang_id = cfg["model"].get("lang_id")

    proc = psutil.Process()
    pid = os.getpid()
    # The THREAD BUDGET, resolved by the shipped resolver (main() does exactly
    # this with `--threads`): 0 = auto, which is what the product ships.
    result = {
        "arm": arm,
        "pid": pid,
        "threads_args": threads,
        "threads_effective": int(sw.resolve_threads(threads)[0]),
        "audio": os.path.relpath(audio, REPO),
        "python": sys.version.split()[0],
        "onnxruntime": ort.__version__,
        "providers_available": list(ort.get_available_providers()),
        "requested_flag": ARMS[arm],
        "audio_s": None,
        "chunks": None,
        "passes": npasses,
        "gpu_before": gpu_mib(pid),
    }

    pcm, sr = sf.read(audio, dtype="float32")
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    result["fixture_rate"] = int(sr)
    if sr != 16000:
        # THE LIVE PATH'S OWN RESAMPLER, not a second convention: `_FileTap` does
        # exactly this when a device delivers a native rate (`sotto_worker.py`,
        # `resample_to_16k`). 22050 -> 16 kHz is the non-integer arm (np.interp).
        pcm = sw.resample_to_16k(np.ascontiguousarray(pcm, np.float32), sr)
    pcm = np.ascontiguousarray(pcm, dtype=np.float32)

    providers, available, note, _probed = sw.choose_providers(ARMS[arm], model_dir)
    result["providers_requested"] = list(providers)
    result["resolver_note"] = note

    # ── LOAD ─────────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    asr = sw.StreamAsr(model_dir, providers=providers, use_vad=use_vad, lang_id=lang_id)
    result["load_s"] = round(time.perf_counter() - t0, 3)
    result["load_phases_s"] = dict(getattr(asr, "load_phases_s", {}) or {})
    # THE ANSWER, read off the encoder session that will actually run — not the
    # request. A CUDA EP that is registered but cannot dlopen leaves this list
    # CPU-only, and that IS the measurement in that case.
    result["providers_selected"] = list(asr.providers)
    result["provider_note"] = getattr(asr, "provider_note", "")
    result["gpu_active"] = "CUDAExecutionProvider" in asr.providers
    result["gpu_after_load"] = gpu_mib(pid)
    result["rss_after_load_mib"] = round(proc.memory_info().rss / 1048576.0, 1)

    # ── FRONT END (not the provider's cost, reported apart) ──────────────────
    t1 = time.perf_counter()
    _ = asr.sp
    result["frontend_s"] = round(time.perf_counter() - t1, 3)
    result["gpu_after_frontend"] = gpu_mib(pid)

    chunk = int(asr.chunk)
    n = len(pcm) // chunk
    result["chunks"] = n
    result["audio_s"] = round(n * chunk / 16000.0, 3)
    result["audio_tail_samples_dropped"] = int(len(pcm) - n * chunk)

    pass_rows = []
    sampler = GpuSampler(pid).start()
    for p in range(1, npasses + 1):
        if p > 1:
            # BOTH halves of a stream start: the caches/predictor AND a new
            # streaming processor (the mel window and VAD state live in it).
            asr.reset_stream_state()
            asr.reset_frontend()
        stage0 = dict(asr.stage_s)
        cpu0 = time.process_time()
        wall0 = time.perf_counter()
        lat = []
        texts = []
        for i in range(n):
            c = pcm[i * chunk:(i + 1) * chunk]
            t = time.perf_counter()
            txt, _ntok = asr.run_chunk(c)
            lat.append((time.perf_counter() - t) * 1000.0)
            texts.append(txt)
        wall = time.perf_counter() - wall0
        cpu_s = time.process_time() - cpu0
        text = "".join(texts)
        pass_rows.append({
            "pass": p,
            "lat_ms": lat,
            "p50_ms": round(statistics.median(lat), 2),
            "p95_ms": round(sorted(lat)[max(0, int(round(0.95 * len(lat))) - 1)], 2),
            "max_ms": round(max(lat), 2),
            "wall_s": round(wall, 3),
            "cpu_pct_one_core": round(cpu_s / wall * 100.0, 1),
            "stage_ms": {
                k: round((asr.stage_s.get(k, 0.0) - stage0.get(k, 0.0)) * 1000.0, 1)
                for k in ("pre", "enc", "dec")
            },
            "text": text,
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        })

    # The headline cells: WARM passes only (pass 1 = session warm-up).
    result["gpu_during_decode"] = sampler.stop()
    warm = pass_rows[1:] or pass_rows
    warm_lat = [x for row in warm for x in row["lat_ms"]]
    warm_wall = sum(row["wall_s"] for row in warm)
    warm_cpu = sum(row["cpu_pct_one_core"] * row["wall_s"] for row in warm) / 100.0
    result["pass1_p50_ms"] = pass_rows[0]["p50_ms"]
    result["p50_ms"] = round(statistics.median(warm_lat), 2)
    result["p95_ms"] = round(sorted(warm_lat)[max(0, int(round(0.95 * len(warm_lat))) - 1)], 2)
    result["max_ms"] = round(max(warm_lat), 2)
    result["rtf"] = round(warm_wall / (result["audio_s"] * len(warm)), 4)
    result["x_realtime"] = round(1.0 / result["rtf"], 2) if result["rtf"] else None
    result["cpu_pct_one_core"] = round(warm_cpu / warm_wall * 100.0, 1)
    result["stage_ms"] = {
        k: round(sum(row["stage_ms"][k] for row in warm) / len(warm), 1)
        for k in ("pre", "enc", "dec")
    }
    result["text"] = pass_rows[0]["text"]
    result["text_sha256"] = pass_rows[0]["text_sha256"]
    result["text_sha256_warm_passes"] = sorted({row["text_sha256"] for row in warm})
    result["pass1_equals_warm"] = result["text_sha256_warm_passes"] == [result["text_sha256"]]
    mi = proc.memory_info()
    result["rss_peak_mib"] = round(float(getattr(mi, "peak_wset", mi.rss)) / 1048576.0, 1)
    result["gpu_end"] = gpu_mib(pid)
    result["pass_rows"] = [{
        "pass": row["pass"], "p50_ms": row["p50_ms"], "p95_ms": row["p95_ms"],
        "max_ms": row["max_ms"], "wall_s": row["wall_s"],
        "cpu_pct_one_core": row["cpu_pct_one_core"], "stage_ms": row["stage_ms"],
        "text_sha256": row["text_sha256"],
    } for row in pass_rows]

    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=2)
    summary = {k: result[k] for k in (
        "arm", "load_s", "frontend_s", "p50_ms", "p95_ms", "max_ms", "rtf",
        "cpu_pct_one_core", "rss_peak_mib", "providers_selected", "gpu_active",
        "text_sha256")}
    print(json.dumps(summary, ensure_ascii=False))
    print("TEXT: %s" % result["text"])
    return 0 if result["gpu_active"] == (arm == "cuda") else 4


# ── the table ─────────────────────────────────────────────────────────────────
def _cell(row, key, fmt="%s"):
    if row is None:
        return "n/a"
    v = row.get(key)
    return "n/a" if v is None else (fmt % v)


def _stage(row, stage, per):
    """A per-pass stage sum turned into ms per CHUNK (the unit the latencies use)."""
    if not row:
        return "n/a"
    v = (row.get("stage_ms") or {}).get(stage)
    n = row.get(per)
    if v is None or not n:
        return "n/a"
    return "%.1f" % (v / n)


def compare(paths: list[str]) -> int:
    rows = {}
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            r = json.load(fh)
        rows[r["arm"]] = r
    cpu, cuda = rows.get("cpu"), rows.get("cuda")
    if cpu is None or cuda is None:
        print("need one file per arm (got %s)" % sorted(rows))
        return 2

    def g(r, stage, field):
        if not r:
            return None
        gg = r.get(stage) or {}
        return gg.get(field)

    hdr = ["metric", "cpu", "cuda"]
    table = [
        ["load_s (3 sessions)", _cell(cpu, "load_s"), _cell(cuda, "load_s")],
        ["  of which encoder", g(cpu, "load_phases_s", "encoder"), g(cuda, "load_phases_s", "encoder")],
        ["frontend_s (og.Model)", _cell(cpu, "frontend_s"), _cell(cuda, "frontend_s")],
        ["chunk p50 (ms)", _cell(cpu, "p50_ms"), _cell(cuda, "p50_ms")],
        ["chunk p95 (ms)", _cell(cpu, "p95_ms"), _cell(cuda, "p95_ms")],
        ["chunk max (ms)", _cell(cpu, "max_ms"), _cell(cuda, "max_ms")],
        ["pass1 p50 (ms)", _cell(cpu, "pass1_p50_ms"), _cell(cuda, "pass1_p50_ms")],
        ["RTF (wall/audio)", _cell(cpu, "rtf"), _cell(cuda, "rtf")],
        ["x realtime", _cell(cpu, "x_realtime"), _cell(cuda, "x_realtime")],
        ["CPU % of one core", _cell(cpu, "cpu_pct_one_core"), _cell(cuda, "cpu_pct_one_core")],
        ["RSS peak (MiB)", _cell(cpu, "rss_peak_mib"), _cell(cuda, "rss_peak_mib")],
        ["GPU this pid (MiB)", g(cpu, "gpu_end", "pid_mib"), g(cuda, "gpu_end", "pid_mib")],
        ["our pid in nvidia-smi compute-apps",
         g(cpu, "gpu_end", "pid_listed"), g(cuda, "gpu_end", "pid_listed")],
        ["GPU total (MiB) at end", g(cpu, "gpu_end", "total_mib"), g(cuda, "gpu_end", "total_mib")],
        ["GPU total (MiB) at start", g(cpu, "gpu_before", "total_mib"),
         g(cuda, "gpu_before", "total_mib")],
        # MACHINE-WIDE util, not ours: another app on this box keeps the number
        # above zero even during the CPU arm, so it is the pid row above — not
        # this one — that says whether THIS process touched the GPU.
        ["GPU util machine-wide max % (all apps)", g(cpu, "gpu_during_decode", "util_max_pct"),
         g(cuda, "gpu_during_decode", "util_max_pct")],
        ["GPU total (MiB) max during decode", g(cpu, "gpu_during_decode", "total_mib_max"),
         g(cuda, "gpu_during_decode", "total_mib_max")],
        ["stage pre (ms/chunk)", _stage(cpu, "pre", "chunks"), _stage(cuda, "pre", "chunks")],
        ["stage enc (ms/chunk)", _stage(cpu, "enc", "chunks"), _stage(cuda, "enc", "chunks")],
        ["stage walk dec+joint (ms/chunk)", _stage(cpu, "dec", "chunks"),
         _stage(cuda, "dec", "chunks")],
        ["providers selected", ",".join(cpu.get("providers_selected") or []),
         ",".join(cuda.get("providers_selected") or [])],
        ["text sha256", (cpu.get("text_sha256") or "")[:16], (cuda.get("text_sha256") or "")[:16]],
    ]
    widths = [max(len(str(r[i])) for r in [hdr] + table) for i in range(3)]
    def line(cells):
        return "| " + " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cells)) + " |"
    print(line(hdr))
    print("|" + "|".join("-" * (widths[i] + 2) for i in range(3)) + "|")
    for r in table:
        print(line(r))

    same = cpu.get("text_sha256") == cuda.get("text_sha256")
    print("\nTRANSCRIPT IDENTICAL: %s (%s vs %s)" % (
        "YES" if same else "NO", cpu.get("text_sha256"), cuda.get("text_sha256")))
    if not same:
        print("cpu : %s" % cpu.get("text"))
        print("cuda: %s" % cuda.get("text"))
        print("VERDICT: the provider CHANGED THE TEXT — a defect, not an optimisation. "
              "No product default may be changed on this evidence.")
        return 5
    if cpu.get("rtf") and cuda.get("rtf"):
        print("RTF: cuda %.4f vs cpu %.4f -> cuda is %.2fx faster (cuda's RTF is %.1f%% lower)"
              % (cuda["rtf"], cpu["rtf"], cpu["rtf"] / cuda["rtf"],
                 (1.0 - cuda["rtf"] / cpu["rtf"]) * 100.0))
        print("VERDICT: %s" % ("cuda-wins" if cuda["rtf"] < cpu["rtf"] else "cpu-wins"))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=sorted(ARMS))
    ap.add_argument("--compare", nargs="+", metavar="JSON")
    ap.add_argument("--audio", default=DEFAULT_AUDIO)
    ap.add_argument("--passes", type=int, default=3)
    ap.add_argument("--threads", type=int, default=0,
                    help="thread budget, resolved by the shipped resolve_threads (0 = auto)")
    ap.add_argument("--out", default="")
    a = ap.parse_args(argv)
    if a.compare:
        return compare(a.compare)
    if not a.arm:
        ap.error("--arm or --compare is required")
    try:
        return run_arm(a.arm, a.audio, max(1, a.passes), a.out, a.threads)
    except Exception:                                            # noqa: BLE001
        tb = traceback.format_exc()
        sys.stderr.write(tb)
        if a.out:
            os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
            with open(a.out, "w", encoding="utf-8") as fh:
                json.dump({"arm": a.arm, "error": tb.strip().splitlines()[-1],
                           "traceback": tb, "audio": os.path.relpath(a.audio, REPO)},
                          fh, ensure_ascii=False, indent=2)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
