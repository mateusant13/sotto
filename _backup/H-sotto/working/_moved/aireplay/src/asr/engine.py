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
    PROVIDER,
    PROVIDERS,
    QUANTIZATION,
    SAMPLE_RATE,
    THREAD_ENV_VARS,
)

__all__ = [
    "pin_thread_env", "ModelDirError", "ProviderUnavailableError", "LanguageNotSupportedError",
    "OnnxAsrEngine", "verify_model_dir", "LANGUAGE_INPUT_NAMES",
]


class ModelDirError(RuntimeError):
    """The model directory is not the verified artefact -- refuse, never run degraded."""


class ProviderUnavailableError(RuntimeError):
    """The requested execution provider did not load -- refuse, never run degraded on another.

    MEASURED on this box (2026-10-07, `_main/lane9-asr-gate.ps1` ARM P): `--provider cuda`
    exits **0**, prints the same transcript as `--provider cpu`, and ORT's own stderr says
    `Failed to create CUDAExecutionProvider ... cublasLt64_13.dll which is missing` -- while
    `session.get_providers()` reports `['CPUExecutionProvider']`. ORT falls back silently and
    the exit code says nothing. AGENTS.md:230-234 records the same fact; the gap was that no
    code compared the REQUEST against the LOADED provider.
    """


class LanguageNotSupportedError(ValueError):
    """A language was asked for on an export that declares no language input -- refuse, never
    silently ignore it.

    MEASURED (2026-10-07, ARM B): `nemo-parakeet-tdt-0.6b-v3` declares **no** language input on
    either graph -- encoder inputs are exactly `['audio_signal', 'length']`, decoder_joint's
    are `['encoder_outputs','targets','target_length','input_states_1','input_states_2']`
    (`_main/lane9-asr-gate.ps1` ARM B reads them off the model). `onnx_asr` accepts
    `recognize(..., language=...)` for Whisper/Canary (`onnx_asr/adapters.py:50`,
    `models/nemo.py:232-238`) and for this TDT export the kwarg is **swallowed**: the
    transducer path (`asr.py:192-229 _AsrWithTransducerDecoding._decoding`) reads only
    `need_logprobs`. Measured: `language='pt'`, `'en'`, `'Portuguese'` and even
    `'klingon'` all return the byte-identical transcript (sha256 prefix `6a5d7b8acad6` on
    `src-pt-15s.wav`). A caller who believes they selected a language selected NOTHING --
    the same failure class as the SOTTO worker's silent lang defaults, which cost a language
    twice (docs/model-specs/README.md section 3).
    """


# The input names that would mean "this export is prompt-conditioned". Checked against the
# DECLARED graph inputs, never inferred from the model name.
LANGUAGE_INPUT_NAMES = ("lang_id", "language", "language_id", "lang")


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
        self.graph_inputs: dict = {}
        self.language_conditioned: bool | None = None

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
        self.graph_inputs = {
            name: [i.name for i in s.get_inputs()]
            for name, s in (("encoder", getattr(asr, "_encoder", None)),
                            ("decoder_joint", getattr(asr, "_decoder_joint", None)))
            if s is not None
        }
        self.language_conditioned = any(
            n in LANGUAGE_INPUT_NAMES for names in self.graph_inputs.values() for n in names
        )
        self._verify_provider(providers)
        self.threads_reported = {
            "intra": self.intra_op_num_threads,
            "inter": self.inter_op_num_threads,
            "env": self.env,
            "session_providers": self.session_providers,
            "graph_inputs": self.graph_inputs,
            "language_conditioned": self.language_conditioned,
            "model_name": MODEL_NAME,
            "quantization": self.quantization,
            "provider_requested": self.provider,
            "onnx_asr": getattr(onnx_asr, "__version__", None),
            "onnxruntime": getattr(ort, "__version__", None),
            "ort_available_providers": ort.get_available_providers(),
        }
        return self.load_s

    def _verify_provider(self, requested: list[str]) -> None:
        """THE CURE: a provider that did not load is a refusal, never a silent downgrade.

        `session.get_providers()` is what the session REPORTS it bound. That is a READBACK,
        not proof of execution: a session can list a provider it never ran work on. It is
        still the only signal available, and it is what catches the real defect here -- ORT's
        provider requests are best-effort, so a missing provider is dropped in silence while
        the process still exits 0. So the check compares the first REQUESTED entry against
        what every loaded session reports, and says "reported", never "actually".

        FAIL-CLOSED on an unreadable session (MEASURED 2026-10-07, lane 9 self-audit; F4 fixed
        after verifier pass 2): an empty `session_providers` used to make `missing` empty, so
        a `--provider cuda` request with no session to read was ACCEPTED -- a verification
        that cannot verify must not pass. Verifier pass 2 also showed the `cpu` arm passed the
        same way, through `all([])`, which is vacuously True: zero sessions means zero stray
        providers, so the check passed without having checked anything. Both arms now refuse
        when there is nothing to read. That costs a real, harmless case -- a model whose
        adapter exposes no encoder session -- so it is a deliberate refusal, not an oversight.
        """
        if not self.session_providers:
            raise ProviderUnavailableError(
                f"provider {self.provider!r} was requested but no session was available to "
                f"verify what ORT reports it bound; refusing rather than reporting an "
                f"unverified provider (an empty session list verifies nothing, on either arm). "
                f"available={self.threads_reported_available()}."
            )
        if self.provider == "cpu":
            # The shipped arm: CPU must be the only provider reported, so a silent CUDA
            # promotion (or a TensorRT fallback) can never be mistaken for the measured config.
            stray = [p for ps in self.session_providers for p in ps if p != PROVIDER]
            if stray:
                raise ProviderUnavailableError(
                    f"requested CPU-only but a session reported {sorted(set(stray))}; "
                    f"sessions={self.session_providers}"
                )
            return
        wanted = requested[0]
        missing = [ps for ps in self.session_providers if wanted not in ps]
        if missing:
            raise ProviderUnavailableError(
                f"provider {wanted!r} did not load (ORT fell back silently): "
                f"sessions={self.session_providers}, available={self.threads_reported_available()}. "
                f"On this box CUDA is requested but not loadable (AGENTS.md:230-234); use --provider cpu."
            )

    def threads_reported_available(self) -> list:
        import onnxruntime as ort  # noqa: PLC0415

        return list(ort.get_available_providers())

    # -- inference -------------------------------------------------------------------
    def recognize(self, audio, sample_rate: int = SAMPLE_RATE, language: str | None = None) -> str:
        """Transcribe. `language` is accepted ONLY by an export that declares a language input.

        The parameter exists so a caller who wants to select a language has to say it here,
        where it can be REFUSED, instead of passing it to `onnx_asr`, which swallows it on this
        transducer path and returns the same text for every value (MEASURED, ARM B). For
        `nemo-parakeet-tdt-0.6b-v3` `language_conditioned` is False and any non-None value
        raises -- there is no prompt slot to condition on, so a silent no-op would be a lie.
        """
        if self.model is None:
            raise RuntimeError("engine.recognize() before engine.load()")
        if language is not None:
            if self.language_conditioned is not True:
                raise LanguageNotSupportedError(
                    f"language={language!r} cannot be honoured: {MODEL_NAME} declares no language "
                    f"input (graph inputs={self.graph_inputs}). onnx_asr accepts the kwarg for "
                    f"Whisper/Canary and IGNORES it here, returning the identical transcript for "
                    f"every value -- a silent no-op. See docs/model-specs/README.md section 3."
                )
            return self.model.recognize(audio, sample_rate=sample_rate, language=language)
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
