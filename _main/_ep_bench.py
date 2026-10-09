"""EP benchmark — the SAME model, the SAME audio, one provider per run.

Mirrors worker/sotto_worker.py's file arm (selftest) chunk for chunk, so the
numbers are about the model the product actually runs, not a toy graph.

Reports, per run:
  REAL session providers  (InferenceSession.get_providers(), never get_available_providers)
  latency per chunk (median / p95 / total), RTF
  process CPU%  -> cores_used = cpu_percent/100
  GPU% from nvidia-smi (sampled in a thread)
  RSS peak (worker's own psapi reader)
  transcript sha256 + token count  -> proves provider parity, not just speed

Usage:
  python _main/_ep_bench.py --model DIR --wav F --provider P [--threads N]
                            [--reps R] [--json OUT] [--no-cuda-dlls]
"""
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.normpath(os.path.join(HERE, "..", "worker"))
sys.path.insert(0, WORKER)

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--wav", required=True)
ap.add_argument("--provider", required=True, help="comma list, e.g. CPUExecutionProvider")
ap.add_argument("--threads", type=int, default=2)
ap.add_argument("--reps", type=int, default=1, help="full passes over the file")
ap.add_argument("--json", default=None)
ap.add_argument("--no-cuda-dlls", action="store_true")
ap.add_argument("--dll-dir", action="append", default=[],
                help="extra dir to put on the DLL search path (repeatable)")
ap.add_argument("--warmup-chunks", type=int, default=0)
ap.add_argument("--label", default="")
args = ap.parse_args()

# Pin threads BEFORE numpy/ort import (worker rule).
os.environ["OMP_NUM_THREADS"] = str(args.threads)
os.environ["MKL_NUM_THREADS"] = str(args.threads)
os.environ["OPENBLAS_NUM_THREADS"] = str(args.threads)

# ── GPU sampler (nvidia-smi, ~10 Hz) ─────────────────────────────────────────
_gpu_samples = []
_gpu_stop = threading.Event()


def _gpu_loop():
    while not _gpu_stop.is_set():
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=4,
                creationflags=0x08000000,
            ).stdout.strip().splitlines()
            if out:
                u, m = out[0].split(",")
                _gpu_samples.append((float(u), float(m)))
        except Exception:
            pass
        _gpu_stop.wait(0.1)


_gpu_thread = threading.Thread(target=_gpu_loop, daemon=True)
_gpu_thread.start()

# ── CPU sampler (psutil if present, else process-time delta) ─────────────────
try:
    import psutil
    _proc = psutil.Process()
    psutil.cpu_percent(interval=None)          # prime
    _proc.cpu_percent(interval=None)           # prime
    HAVE_PSUTIL = True
except Exception:
    HAVE_PSUTIL = False
    _proc = None

sys.path.insert(0, HERE)
import sotto_worker as sw  # noqa: E402

if not args.no_cuda_dlls:
    sw._add_cuda_dll_dirs()

# Explicit DLL dirs: held handles, prepended to PATH — the same mechanism
# `_add_cuda_dll_dirs()` uses, and needed when the CUDA runtime comes from
# `nvidia-*` wheels the running interpreter does not itself have.
_DLL_HANDLES = []
for _d in args.dll_dir:
    if os.path.isdir(_d):
        try:
            _DLL_HANDLES.append(os.add_dll_directory(_d))
        except Exception as exc:
            print(f"WARN add_dll_directory({_d}) failed: {exc}", file=sys.stderr)
        os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")

import numpy as np  # noqa: E402


def read_wav(path):
    """soundfile when available, else the stdlib wave module (16-bit PCM mono)."""
    try:
        import soundfile as sf
        x, sr = sf.read(path, dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
        return x, sr
    except ImportError:
        import wave
        with wave.open(path, "rb") as w:
            sr = w.getframerate()
            nch = w.getnchannels()
            sw_ = w.getsampwidth()
            raw = w.readframes(w.getnframes())
        if sw_ != 2:
            raise SystemExit(f"wave fallback: unsupported sample width {sw_*8}-bit")
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        if nch > 1:
            x = x.reshape(-1, nch).mean(axis=1)
        return x, sr

result = {
    "label": args.label,
    "python": sys.version.split()[0],
    "executable": sys.executable,
    "requested": args.provider,
    "threads_env": args.threads,
    "model_dir": os.path.basename(os.path.normpath(args.model)),
    "wav": os.path.basename(args.wav),
    "cuda_dlls": not args.no_cuda_dlls,
}

t0 = time.perf_counter()
asr = sw.StreamAsr(args.model, providers=args.provider.split(","), use_vad=True, lang_id="auto")
result["load_s"] = round(time.perf_counter() - t0, 3)
result["REAL_get_providers"] = list(asr.enc.get_providers())
result["REAL_decoder"] = list(asr.dec.get_providers())
result["REAL_joint"] = list(asr.joint.get_providers())
result["intra_op_num_threads_effective"] = asr.enc._sess_options.intra_op_num_threads
result["rss_after_load_mb"] = round(sw.current_rss_mb(), 1)

pcm, sr = read_wav(args.wav)
if sr != sw.TARGET_SR:
    pcm = sw.resample_to_16k(pcm, sr)
n_chunks = len(pcm) // asr.chunk
result["audio_s"] = round(len(pcm) / sw.TARGET_SR, 3)
result["chunks"] = n_chunks

# ── warmup (not counted) ─────────────────────────────────────────────────────
for i in range(min(args.warmup_chunks, n_chunks)):
    asr.run_chunk(pcm[i * asr.chunk:(i + 1) * asr.chunk])

per_chunk_ms = []
pass_walls = []
pass_texts = []
for rep in range(args.reps):
    if HAVE_PSUTIL:
        _proc.cpu_percent(interval=None)
    cpu0 = time.process_time()
    gpu0 = len(_gpu_samples)
    tstart = time.perf_counter()
    for i in range(n_chunks):
        c0 = time.perf_counter()
        asr.run_chunk(pcm[i * asr.chunk:(i + 1) * asr.chunk])
        per_chunk_ms.append((time.perf_counter() - c0) * 1000.0)
    wall = time.perf_counter() - tstart
    cpu_used = time.process_time() - cpu0
    pass_walls.append(wall)
    pass_texts.append(asr.detok(asr.labels))

result["reps"] = args.reps
result["wall_s_per_pass"] = [round(w, 3) for w in pass_walls]
result["wall_s_best"] = round(min(pass_walls), 3)
result["rtf_best"] = round(min(pass_walls) / (n_chunks * asr.chunk / sw.TARGET_SR), 4)
result["chunk_ms_median"] = round(statistics.median(per_chunk_ms), 2)
result["chunk_ms_mean"] = round(statistics.fmean(per_chunk_ms), 2)
result["chunk_ms_p95"] = round(sorted(per_chunk_ms)[int(len(per_chunk_ms) * 0.95) - 1], 2)
result["chunk_ms_max"] = round(max(per_chunk_ms), 2)
result["chunk_ms_min"] = round(min(per_chunk_ms), 2)

# cores consumed by the ASR work itself (process CPU time / wall), the honest number
result["cores_used_infer"] = round(
    (time.process_time() - cpu0) / min(pass_walls), 2
)
if HAVE_PSUTIL:
    result["cpu_percent_process"] = round(_proc.cpu_percent(interval=None), 1)
    result["system_cpu_percent"] = round(psutil.cpu_percent(interval=None), 1)
    result["cpu_count_logical"] = psutil.cpu_count()
    result["cpu_count_physical"] = psutil.cpu_count(logical=False)

result["rss_peak_mb"] = round(sw.peak_rss_mb(), 1)
result["rss_end_mb"] = round(sw.current_rss_mb(), 1)
result["tokens_total"] = asr.labels_total
text = pass_texts[-1]
result["text_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
result["text_chars"] = len(text)
result["text_head"] = text[:120]

_gpu_stop.set()
time.sleep(0.15)
if _gpu_samples:
    us = [s[0] for s in _gpu_samples]
    ms = [s[1] for s in _gpu_samples]
    result["gpu_util_mean"] = round(statistics.fmean(us), 1)
    result["gpu_util_max"] = round(max(us), 1)
    result["gpu_mem_mb_max"] = round(max(ms), 0)
    result["gpu_samples"] = len(us)
else:
    result["gpu_util_mean"] = None
    result["gpu_samples"] = 0

print(json.dumps(result, indent=2, ensure_ascii=False))
if args.json:
    with open(args.json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
