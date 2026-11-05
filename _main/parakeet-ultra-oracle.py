#!/usr/bin/env python3
# BATTERY-HEAVY: model -- carrega 2,4 GB (`model_weights.ckpt` / `unified.nemo`) e
# corre em CUDA; o passo `parakeet-ultra` da bateria e' `heavy`, e o portao
# `_main/battery-heavy-gate.py` exige que o INSTRUMENTO declare a classe onde a
# verdade esta' (medido 2026-11-05: C2 recusou o passo por falta deste marker).
"""Oraculo da comparacao parakeet-redux (ONNX int4) x parakeet-ultra.

O QUE JULGA
-----------
Duas perguntas, e cada uma precisa de um instrumento que possa falhar:

1. **Ultra transcreve igual ou melhor que o Redux, no MESMO audio?** Mede WER
   contra `_main/fixtures/stack-compare/reference.json` (referencia PROVISORIA
   -- serve para comparar engines entre si, nunca para afirmar "o WER deste
   modelo e' X"), com a contagem absoluta de substituicoes/insercoes/remocoes
   e a frase verbatim de cada engine.
2. **A que preco?** RTF, tempo de carga a frio, pico de RSS e pico de VRAM --
   porque o finisher corre em segundo plano ao lado de um jogo na mesma placa.

O audio e' o do dono (`ptbr-radio-14s.wav`, 15,0 s a 22 050 Hz -- o
`reference.json` diz 14,56 s a 16 kHz e essa parte esta' errada; o ficheiro
manda) e o clipe de debito `_main/live-sample-cable-input-90s.wav`, que NAO tem
referencia escrita e por isso nunca leva WER.

ARMAS
-----
    --engine all|redux|ultra-onnx|ultra-torch     (default: all que estiverem em disco)
    --neg-arm            controles do INSTRUMENTO de WER, sem modelos: a
                         referencia contra si propria tem de dar 0, uma palavra
                         trocada 1/25, um vazio 25 remocoes. Se alguma dessas
                         nao mexer, o WER nao mede nada e o oraculo diz RED.

SAIDA
-----
Uma linha JSON `RESULT {...}` por engine em stdout (UTF-8), mais `VERDICT`.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "worker"))

FIXTURES = REPO / "_main" / "fixtures" / "stack-compare"
REFERENCE = FIXTURES / "reference.json"
THROUGHPUT = REPO / "_main" / "live-sample-cable-input-90s.wav"

#: Redux: the int4 ONNX export `redux_live.py` runs by default. Measured
#: 2026-11-04: `worker/models/parakeet-redux-onnx-int4/` is EMPTY in the main
#: tree (16 files in the sibling nemotron dir, 0 here), so the lane's copy is
#: the pinned download under I:/cc-tmp (revision 1c285ba, byte counts as
#: `_main/fetch-parakeet.py` records them).
REDUX_ONNX_DIRS = (
    os.environ.get("SOTTO_REDUX_ONNX_DIR", ""),
    str(REPO / "worker" / "models" / "parakeet-redux-onnx-int4"),
    "I:/cc-tmp/models-src/parakeet-redux-onnx",
)
ULTRA_ONNX_DIRS = (
    os.environ.get("SOTTO_ULTRA_ONNX_DIR", ""),
    str(REPO / "worker" / "models" / "parakeet-ultra-onnx"),
    "I:/cc-tmp/models-src/parakeet-ultra-onnx",
)
ULTRA_SRC_DIRS = (
    os.environ.get("SOTTO_ULTRA_SRC_DIR", ""),
    str(REPO / "worker" / "models" / "parakeet-ultra"),
    "I:/cc-tmp/models-src",
)


# ---------------------------------------------------------------------------
# WER -- the instrument, and its normalisation as stated by the fixture
# ---------------------------------------------------------------------------
def normalise(text: str) -> list[str]:
    """lowercase, no punctuation, spaces collapsed, ACCENTS PRESERVED."""
    folded = "".join(character if not unicodedata.category(character).startswith("P") else " "
                     for character in text)
    return folded.lower().split()


def edit_counts(reference: list[str], hypothesis: list[str]) -> tuple[int, int, int]:
    """(substitutions, insertions, deletions) from the Levenshtein backtrace."""
    rows, cols = len(reference) + 1, len(hypothesis) + 1
    cost = [[0] * cols for _ in range(rows)]
    for i in range(1, rows):
        cost[i][0] = i
    for j in range(1, cols):
        cost[0][j] = j
    for i in range(1, rows):
        for j in range(1, cols):
            same = reference[i - 1] == hypothesis[j - 1]
            cost[i][j] = min(cost[i - 1][j - 1] + (0 if same else 1),
                             cost[i - 1][j] + 1,
                             cost[i][j - 1] + 1)
    subs = ins = dele = 0
    i, j = len(reference), len(hypothesis)
    while i > 0 or j > 0:
        if i > 0 and j > 0 and reference[i - 1] == hypothesis[j - 1] and cost[i][j] == cost[i - 1][j - 1]:
            i, j = i - 1, j - 1
        elif i > 0 and j > 0 and cost[i][j] == cost[i - 1][j - 1] + 1:
            subs += 1
            i, j = i - 1, j - 1
        elif i > 0 and cost[i][j] == cost[i - 1][j] + 1:
            dele += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    return subs, ins, dele


def wer(reference: list[str], hypothesis: list[str]) -> tuple[float, int, int, int]:
    subs, ins, dele = edit_counts(reference, hypothesis)
    total = len(reference)
    return (subs + ins + dele) / total if total else float("nan"), subs, ins, dele


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------
class Resources:
    def __init__(self):
        import psutil

        self._process = psutil.Process()
        self.peak_rss_mb = self._process.memory_info().rss / 1e6
        self._vram_base = self.vram_used_mb()

    @staticmethod
    def vram_used_mb():
        import subprocess

        flags = 0x08000000 if os.name == "nt" else 0
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, creationflags=flags,
                                 startupinfo=subprocess.STARTUPINFO(
                                     dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0),
                                 timeout=10).stdout
            return float(out.strip().splitlines()[0])
        except Exception:  # noqa: BLE001
            return None

    def sample(self):
        rss = self._process.memory_info().rss / 1e6
        self.peak_rss_mb = max(self.peak_rss_mb, rss)
        return rss

    def peak_vram_delta_mb(self):
        used = self.vram_used_mb()
        if used is None or self._vram_base is None:
            return None
        return round(used - self._vram_base, 1)


def read_wav16(path: Path):
    import numpy as np
    import soundfile as sf

    data, rate = sf.read(str(path), dtype="float32", always_2d=True)
    pcm = data.mean(axis=1)
    if rate != 16000:
        import soxr

        pcm = soxr.resample(pcm, rate, 16000).astype(np.float32)
    return np.ascontiguousarray(pcm, dtype=np.float32), rate


# ---------------------------------------------------------------------------
# Engines: every one is called through the SAME two calls
# ---------------------------------------------------------------------------
def resolve(candidates) -> Path | None:
    for candidate in candidates:
        if candidate and (Path(candidate) / "encoder-model.onnx").is_file():
            return Path(candidate)
    return None


def resolve_src() -> Path | None:
    for candidate in ULTRA_SRC_DIRS:
        if candidate and (Path(candidate) / "ultra.safetensors").is_file():
            return Path(candidate)
    return None


def build(engine: str):
    import parakeet_ultra

    if engine == "redux":
        import redux_live

        directory = resolve(REDUX_ONNX_DIRS)
        if directory is None:
            raise SystemExit("redux: no ONNX export on disk (checked %s)" % (REDUX_ONNX_DIRS,))
        started = time.perf_counter()
        backend = redux_live.OnnxBackend(str(directory))
        return backend, round(time.perf_counter() - started, 2), directory
    if engine == "ultra-onnx":
        directory = resolve(ULTRA_ONNX_DIRS)
        if directory is None:
            raise SystemExit("ultra-onnx: no build on disk (checked %s)" % (ULTRA_ONNX_DIRS,))
        started = time.perf_counter()
        backend = parakeet_ultra.OnnxBackend(str(directory))
        return backend, round(time.perf_counter() - started, 2), directory
    src = resolve_src()
    if src is None:
        raise SystemExit("ultra-torch: no checkpoint on disk (checked %s)" % (ULTRA_SRC_DIRS,))
    started = time.perf_counter()
    backend = parakeet_ultra.TorchBackend(src, device="auto", frontend="nemo",
                                          onnx_dir=resolve(ULTRA_ONNX_DIRS) or resolve(REDUX_ONNX_DIRS))
    return backend, round(time.perf_counter() - started, 2), src


# ---------------------------------------------------------------------------
def run_ready(engines, clips):
    fixture = json.loads(REFERENCE.read_text(encoding="utf-8"))
    clip = fixture["clips"][0]
    reference_words = normalise(clip["reference"])
    print("# reference (%d palavras, PROVISORIA): %s" % (len(reference_words), clip["reference"]))

    rows = []
    for engine in engines:
        row = {"engine": engine}
        resources = Resources()
        try:
            backend, load_s, directory = build(engine)
            row["dir"] = str(directory)
            row["cold_load_s"] = load_s
            resources.sample()
            wall = 0.0
            audio = 0.0
            for name, pcm, with_wer in clips:
                started = time.perf_counter()
                text, _segments = backend.transcribe(pcm)
                elapsed = time.perf_counter() - started
                resources.sample()
                seconds = pcm.size / 16000
                wall += elapsed
                audio += seconds
                row.setdefault("clips", {})[name] = {
                    "audio_s": round(seconds, 2),
                    "infer_s": round(elapsed, 3),
                    "xrt": round(seconds / elapsed, 2) if elapsed else None,
                    "text": text,
                }
                if with_wer:
                    hypothesis = normalise(text)
                    score, subs, ins, dele = wer(reference_words, hypothesis)
                    row["wer"] = round(score, 4)
                    row["subs"], row["ins"], row["del"] = subs, ins, dele
                    row["ref_words"] = len(reference_words)
                    # The fixture's own trap: "'radio' sem o artigo e' aceite".
                    # The strict number is the one quoted; this is the same
                    # number under the fixture's stated tolerance, and both are
                    # printed so neither can be mistaken for the other.
                    accepted = min(score, wer(reference_words, ["o"] + hypothesis)[0])
                    row["wer_accepted"] = round(accepted, 4)
            row["rtf"] = round(wall / audio, 4) if audio else None
            row["peak_rss_mb"] = round(resources.peak_rss_mb)
            vram = resources.peak_vram_delta_mb()
            allocated = getattr(backend, "peak_vram_mb", None)
            allocated = allocated() if callable(allocated) else None
            # nvidia-smi delta includes the CUDA context and the weights; the
            # torch counter includes only this process's allocations. Both are
            # printed because "beside a game" is a question about the card.
            row["peak_vram_mb"] = vram
            row["torch_allocated_mb"] = allocated
            del backend
        except SystemExit as exc:
            row["error"] = str(exc)
        print("RESULT " + json.dumps(row, ensure_ascii=False), flush=True)
        rows.append(row)
    return rows


def neg_arm() -> int:
    """The WER instrument against known answers. No model, no window, no audio."""
    reference = ["a", "ponte", "sobre", "o", "rio", "vai", "cair"]
    cases = [
        ("identical", reference, 0.0, (0, 0, 0)),
        ("one-substitution", ["a", "ponte", "sobre", "o", "mar", "vai", "cair"], 1 / 7, (1, 0, 0)),
        ("one-deletion", ["a", "ponte", "sobre", "o", "vai", "cair"], 1 / 7, (0, 0, 1)),
        ("one-insertion", ["a", "ponte", "sobre", "o", "rio", "do", "vai", "cair"], 1 / 7, (0, 1, 0)),
        ("accent-swap", ["a", "ponte", "sobre", "o", "rio", "vai", "cair"], 0.0, (0, 0, 0)),
        ("empty", [], 1.0, (0, 0, 7)),
        ("all-wrong", ["x", "y", "z", "w", "v", "u", "t"], 1.0, (7, 0, 0)),
    ]
    failures = 0
    for name, hypothesis, expected_wer, expected_counts in cases:
        score, subs, ins, dele = wer(reference, hypothesis)
        counts = (subs, ins, dele)
        ok = abs(score - expected_wer) < 1e-9 and counts == expected_counts
        failures += 0 if ok else 1
        print("  %-5s %-16s wer=%.4f counts=%s esperado=(%.4f, %s)"
              % ("GREEN" if ok else "RED", name, score, counts, expected_wer, expected_counts))
    # The normalisation itself: punctuation and case must not cost a word, an
    # accent must be one substitution (the fixture's own rule).
    plain = normalise("A ponte, sobre o rio! Vai cair?")
    accented = normalise("A ponte, sobre o rio! Vai cair?")
    accent_fail = normalise("A ponte sobre o rio vai caiu")
    norm_ok = plain == reference and accented == reference
    accent_ok = edit_counts(reference, accent_fail)[0] == 1
    failures += 0 if norm_ok else 1
    failures += 0 if accent_ok else 1
    print("  %-5s %-16s %s" % ("GREEN" if norm_ok else "RED", "normalise", plain))
    print("  %-5s %-16s subs=%d" % ("GREEN" if accent_ok else "RED", "accent-is-1-sub",
                                    edit_counts(reference, accent_fail)[0]))
    print("NEG-ARM %s -- %d caso(s) divergentes"
          % ("GREEN" if failures == 0 else "RED", failures))
    # rc=1 POR DESENHO quando o instrumento se prova (convencao da casa,
    # `_main/_audit-verify-all.cmd:1261`). O `:expectred` deste passo declara
    # rc=1 e a frase `NEG-ARM GREEN`; responder 0 fazia o passo vermelho a
    # fazer tudo certo -- medido 2026-11-05: `red-as-expected-parakeet-ultra=0`
    # com 0 casos divergentes no log.
    return 1 if failures == 0 else 0


def window_probe(engines, window_s: float, step_s: float) -> int:
    """Per-pass cost of the LIVE refine policy: 5 s window, re-decoded every 2 s.

    The Redux lane's own numbers are a 5 s window costing 1,32-1,36 s wall with
    2 threads, and its step is 2,0 s because 1,0 s does not fit. The same
    question is asked of every engine here: does ONE pass fit inside the step?
    A pass that does not fit makes the lag diverge, which is the failure the
    Redux lane already paid for once.
    """
    import statistics

    pcm, _ = read_wav16(THROUGHPUT if THROUGHPUT.is_file() else FIXTURES / "ptbr-radio-14s.wav")
    size = round(window_s * 16000)
    stride = round(step_s * 16000)
    windows = [pcm[start:start + size] for start in range(0, max(0, pcm.size - size), stride)]
    print("# window %.1f s, passo %.1f s, %d passagens, audio %s"
          % (window_s, step_s, len(windows), "90 s" if THROUGHPUT.is_file() else "fixture"))
    failures = 0
    for engine in engines:
        try:
            backend, load_s, directory = build(engine)
        except SystemExit as exc:
            print("# %s: %s" % (engine, exc))
            continue
        costs = []
        for window in windows:
            started = time.perf_counter()
            backend.transcribe(window)
            costs.append(time.perf_counter() - started)
        if not costs:
            continue
        overruns = sum(1 for cost in costs if cost > step_s)
        row = {"engine": engine, "window_s": window_s, "step_s": step_s,
               "passes": len(costs), "cold_load_s": load_s,
               "p50_s": round(statistics.median(costs), 3),
               "p95_s": round(sorted(costs)[max(0, int(len(costs) * 0.95) - 1)], 3),
               "max_s": round(max(costs), 3),
               "overruns": overruns}
        failures += 1 if overruns else 0
        print("RESULT " + json.dumps(row, ensure_ascii=False), flush=True)
        del backend
    print("VERDICT %s -- %s"
          % ("GREEN" if failures == 0 else "RED",
             "todas as passagens caberam no passo" if failures == 0
             else "ha' passagem(ns) que nao cabem no passo: o atraso diverge"))
    return 0 if failures == 0 else 1


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

    argv = list(sys.argv[1:] if argv is None else argv)
    if "--neg-arm" in argv:
        return neg_arm()
    window = None
    if "--windows" in argv:
        window = float(argv[argv.index("--windows") + 1])
    engine = "all"
    if "--engine" in argv:
        engine = argv[argv.index("--engine") + 1]
    engines = ["redux", "ultra-onnx", "ultra-torch"] if engine == "all" else [engine]
    if window:
        return window_probe(engines, window, 2.0)

    pcm, rate = read_wav16(FIXTURES / "ptbr-radio-14s.wav")
    print("# clip %s: %d amostras @ %d Hz -> 16000 = %.2f s"
          % ((FIXTURES / "ptbr-radio-14s.wav").name, pcm.size, rate, pcm.size / 16000))
    clips = [("ptbr-radio-14s", pcm, True)]
    if THROUGHPUT.is_file():
        long_pcm, _ = read_wav16(THROUGHPUT)
        clips.append(("live-sample-90s", long_pcm, False))
    rows = run_ready(engines, clips)

    measured = [row for row in rows if "error" not in row and row.get("wer") is not None]
    if not measured:
        print("VERDICT UNPROVEN -- nenhuma engine produziu um numero")
        return 2
    for row in rows:
        if "error" in row:
            print("# %s: %s" % (row["engine"], row["error"]))
    best = min(measured, key=lambda row: (row["wer"], row["rtf"] or 99))
    print("VERDICT %s -- WER=%s (%d subs/%d ins/%d del em %d palavras), RTF=%s, carga=%ss, RSS=%s MB, VRAM=%s MB"
          % (best["engine"], best["wer"], best.get("subs", 0), best.get("ins", 0), best.get("del", 0),
             best.get("ref_words", 0), best["rtf"], best["cold_load_s"], best["peak_rss_mb"],
             best["peak_vram_mb"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
