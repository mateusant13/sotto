"""Compara motores no MESMO wav: parakeet-redux ONNX int4 vs nemotron int4.

Nao corrige nada: mede (texto, xRT, RSS de pico) para responder "o ARK-ASR e'
melhor?" com numeros locais em vez de com o README de quem o publica.

Uso:  python engine-compare.py <wav>[,<wav>] [--engine parakeet|nemotron]
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(r"H:\sotto")
sys.path.insert(0, str(ROOT / "worker"))

import psutil  # noqa: E402

PROC = psutil.Process()


def peak_mb():
    return PROC.memory_info().rss / 1e6


def read_wav16(path):
    import numpy as np
    import soundfile as sf
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if sr != 16000:
        import soxr
        mono = soxr.resample(mono, sr, 16000)
        print("# resampled %s -> 16000" % sr, flush=True)
    return mono.astype(np.float32)


def run_nemotron(wav, chunk_s=0.56):
    import sotto_worker as sw
    pcm = read_wav16(wav)
    t0 = time.perf_counter()
    asr = sw.StreamAsr(sw.DEFAULT_MODEL, providers=['CPUExecutionProvider'])
    t_load = time.perf_counter() - t0
    rss = peak_mb()
    n = int(16000 * chunk_s)
    out = []
    t0 = time.perf_counter()
    for i in range(0, len(pcm), n):
        piece = pcm[i:i + n]
        if len(piece) < n:
            piece = np.pad(piece, (0, n - len(piece))) if False else piece
        try:
            res = asr.run_chunk(piece)
        except Exception as exc:  # noqa: BLE001
            out.append("<%s>" % exc)
            break
        text = ""
        if isinstance(res, dict):
            text = str(res.get("text") or res.get("delta") or "")
        elif isinstance(res, (list, tuple)):
            text = " ".join(str(x) for x in res)
        else:
            text = str(res or "")
        text = text.strip()
        if text:
            out.append(text)
    elapsed = time.perf_counter() - t0
    dur = len(pcm) / 16000.0
    return {"engine": "nemotron-int4", "load_s": round(t_load, 2),
            "infer_s": round(elapsed, 2), "audio_s": round(dur, 1),
            "xrt": round(dur / elapsed, 2) if elapsed else None,
            "rss_mb": round(rss), "peak_mb": round(peak_mb()),
            "text": " ".join(out)[:600]}


def run_parakeet(wav):
    import redux_live
    t0 = time.perf_counter()
    backend = redux_live.OnnxBackend(redux_live.DEFAULT_ONNX_DIR)
    load = time.perf_counter() - t0
    pcm = read_wav16(wav)
    rss = peak_mb()
    t0 = time.perf_counter()
    text, segs = backend.transcribe(pcm)
    elapsed = time.perf_counter() - t0
    dur = len(pcm) / 16000.0
    return {"engine": "parakeet-onnx-int4", "load_s": round(load, 2),
            "infer_s": round(elapsed, 2), "audio_s": round(dur, 1),
            "xrt": round(dur / elapsed, 2) if elapsed else None,
            "rss_mb": round(rss), "peak_mb": round(peak_mb()),
            "text": str(text)[:600]}


def main(argv):
    engine = "all"
    if "--engine" in argv:
        i = argv.index("--engine")
        engine = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    wavs = []
    for arg in argv:
        for part in str(arg).split(","):
            if part.strip():
                wavs.append(Path(part.strip()))
    for wav in wavs:
        for name in (("nemotron", "parakeet") if engine == "all" else (engine,)):
            try:
                row = run_nemotron(wav) if name == "nemotron" else run_parakeet(wav)
            except Exception as exc:  # noqa: BLE001
                row = {"engine": name, "error": "%s: %s" % (type(exc).__name__, exc)}
            row["wav"] = wav.name
            print("RESULT " + json.dumps(row, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
