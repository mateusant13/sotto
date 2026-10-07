"""The ONNX engine: load the measured artefact, pin the measured thread knee, recognise.

`specs/02-asr.md` sections 1-2 and 5. The three things this module must not do:
  * it must not load the model without pinning `intra_op = 4` / `inter_op = 1` (the ORT
    default burns 690% of a core-set for one core's throughput, 05-onnx-asr.md:86-90);
  * it must not reach the network (the model dir is a local path => `offline=True`,
    resolver.py:69-72);
  * it must not claim a GPU it does not have (`CUDAExecutionProvider` does not load here,
    AGENTS.md:230-234).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from .constants import (
    INTRA_OP_NUM_THREADS,
    INTER_OP_NUM_THREADS,
    MODEL_DIR,
    MODEL_FILE_SIZES,
    MODEL_NAME,
    PROVIDERS,
    QUANTIZATION,
    SAMPLE_RATE,
    THREAD_ENV_VARS,
)

__all__ = ["pin_thread_env", "ModelDirError", "OnnxAsrEngine", "verify_model_dir"]


class ModelDirError(RuntimeError):
    """The model directory is not the verified artefact -- refuse, never run degraded."""


def pin_thread_env(threads: int) -> dict[str, str]:
    """Set OMP/OPENBLAS/MKL/NUMEXPR BEFORE numpy and onnxruntime load their thread pools.

    The measurement lanes set these at process launch (11-onnx-threads.md:15-16); setting
    them here, before the heavy imports, is the in-process equivalent and keeps the energy
    splitter from out-threading the budget.
    """
    value = str(int(threads))
    for var in THREAD_ENV_VARS:
        os.environ[var] = value
    return {var: os.environ[var] for var in THREAD_ENV_VARS}


def verify_model_dir(model_dir: str | Path = MODEL_DIR) -> dict:
    """Check the five registered files are present with their registered sizes.

    Sizes, not sha256: the hashes are verified in the receipt (670.6 MB, 5/5 MATCH); a size
    check is the cheap gate that runs on every start, and it catches a truncated download.
    """
    d = Path(model_dir)
    if not d.is_dir():
        raise ModelDirError(f"model dir not found: {d}")
    seen, problems = {}, []
    for name, size in MODEL_FILE_SIZES.items():
        p = d / name
        if not p.exists():
            problems.append(f"missing {name}")
            continue
        got = p.stat().st_size
        seen[name] = got
        if got != size:
            problems.append(f"{name}: {got} B, registered {size} B")
    if problems:
        raise ModelDirError(f"{d} is not the verified artefact: " + "; ".join(problems))
    return {"model_dir": str(d), "files": seen, "total_bytes": sum(seen.values())}


class OnnxAsrEngine:
    """One loaded model. Load once per process; a load is 1.9-4.1 s (11-onnx-threads.md:24)."""

    def __init__(
        self,
        model_dir: str | Path = MODEL_DIR,
        quantization: str = QUANTIZATION,
        provider: str = "cpu",
        intra_op_num_threads: int = INTRA_OP_NUM_THREADS,
        inter_op_num_threads: int = INTER_OP_NUM_THREADS,
        verify: bool = True,
    ):
        self.model_dir = Path(model_dir)
        self.quantization = quantization
        self.provider = provider
        self.intra_op_num_threads = int(intra_op_num_threads)
        self.inter_op_num_threads = int(inter_op_num_threads)
        self.verify = verify
        self.model = None
        self.load_s: float | None = None
        self.env: dict[str, str] = {}
        self.session_providers: list = []
        self.threads_reported: dict = {}

    def load(self):
        pin_thread_env(self.intra_op_num_threads)
        self.env = {var: os.environ.get(var) for var in THREAD_ENV_VARS}
        if self.verify:
            verify_model_dir(self.model_dir)

        import onnx_asr  # noqa: PLC0415 -- after the thread env is pinned
        import onnxruntime as ort  # noqa: PLC0415

        providers = list(PROVIDERS) if self.provider == "cpu" else ["CUDAExecutionProvider", "CPUExecutionProvider"]
        sess_options = ort.SessionOptions()
        # THE PIN. `0` would be ORT's pathological default and is refused by the runner.
        sess_options.intra_op_num_threads = self.intra_op_num_threads
        sess_options.inter_op_num_threads = self.inter_op_num_threads

        t0 = time.perf_counter()
        self.model = onnx_asr.load_model(
            MODEL_NAME,
            path=self.model_dir,
            quantization=self.quantization,
            providers=providers,
            sess_options=sess_options,
        )
        self.load_s = time.perf_counter() - t0

        asr = getattr(self.model, "asr", None)
        self.session_providers = [
            s.get_providers()
            for s in (getattr(asr, "_encoder", None), getattr(asr, "_decoder_joint", None))
            if s is not None
        ]
        self.threads_reported = {
            "intra": self.intra_op_num_threads,
            "inter": self.inter_op_num_threads,
            "env": self.env,
            "session_providers": self.session_providers,
            "model_name": MODEL_NAME,
            "quantization": self.quantization,
            "provider_requested": self.provider,
            "onnx_asr": getattr(onnx_asr, "__version__", None),
            "onnxruntime": getattr(ort, "__version__", None),
            "ort_available_providers": ort.get_available_providers(),
        }
        return self.load_s

    # -- inference -------------------------------------------------------------------
    def recognize(self, audio, sample_rate: int = SAMPLE_RATE) -> str:
        if self.model is None:
            raise RuntimeError("engine.recognize() before engine.load()")
        return self.model.recognize(audio, sample_rate=sample_rate)

    def phase_probe(self, audio) -> dict:
        """INSTRUMENT ONLY (`--phases`): split ONE call into preprocess/encode/decode.

        Same three calls onnx-asr itself makes (`asr.py:156-157`), the same instrument as
        `_main/probe-onnx-asr-phases.py` -- this is how the "the encoder is >=95%" claim
        (05-onnx-asr.md:91-93) is re-derived from the product code instead of believed.

        DISCLOSED: this re-encodes the audio, so the caller must not count it as the
        transcript's cost; the runner uses it on the first segment only and says so.
        """
        import numpy as np  # noqa: PLC0415

        if self.model is None:
            raise RuntimeError("engine.phase_probe() before engine.load()")
        asr = self.model.asr
        batch = np.asarray(audio, dtype=np.float32)[None, :]
        lens = np.array([batch.shape[1]], dtype=np.int64)

        t0 = time.perf_counter()
        feats, flens = asr._preprocessor(batch, lens)
        t1 = time.perf_counter()
        enc, encl = asr._encode(feats, flens)
        t2 = time.perf_counter()
        toks, _stamps, _lp = next(iter(asr._decoding(enc, encl)))
        t3 = time.perf_counter()

        total = t3 - t0
        return {
            "audio_s": round(len(audio) / float(SAMPLE_RATE), 3),
            "preprocess_s": round(t1 - t0, 4),
            "encode_s": round(t2 - t1, 4),
            "decode_s": round(t3 - t2, 4),
            "total_s": round(total, 4),
            "encoder_frames": int(enc.shape[1]) if getattr(enc, "ndim", 0) == 3 else int(enc.shape[0]),
            "tokens": int(len(toks)),
            "encoder_share": round((t2 - t1) / total, 4) if total > 0 else None,
            "note": "re-encodes the same audio; instrument only, not the transcript's cost",
        }
