#!/usr/bin/env python3
"""Parakeet Ultra (moondream/parakeet-ultra) as a Sotto FINISHER engine.

WHAT THIS IS
------------
Ultra is `parakeet-tdt-0.6b-v3` post-trained by Moondream: same 24-layer
1024-d conformer, 640-d 2-layer LSTM predictor, 8193-token vocabulary with
blank 8192, durations [0,1,2,3,4], and -- measured from the checkpoint itself
-- the SAME tensor names `transformers.ParakeetForTDT` uses (0 missing keys;
the six `vad_head.*` tensors are the stamp of Moondream's own VAD head).

So it is the same family as the Redux export this tree already runs, and the
decode contract does not change. Two backends, one API, deliberately:

* ``onnx``  -- ``worker/ultra_export.py`` writes the three-graph ABI that the
  export's own ``transcribe.py`` speaks. This backend then delegates to it, so
  Ultra and Redux run the SAME mel front end, the SAME greedy
  token-and-duration walk and the SAME segmentation; only the weights differ.
  That is what makes their WER/RTF numbers comparable.
* ``torch`` -- the checkpoint loaded straight into ``ParakeetForTDT`` and
  decoded by its own ``generate``; float16 on CUDA. This is the fast arm, and
  the only one that uses the GPU.

``transcribe(pcm)`` returns ``(text, segments)`` -- the same tuple
``redux_live.OnnxBackend``/``TernaryBackend`` return -- so a harness can swap
one engine for the other without knowing which is which.

USO
    python worker/parakeet_ultra.py --onnx-dir I:/cc-tmp/models-src/parakeet-ultra-onnx --wav X.wav
    python worker/parakeet_ultra.py --backend torch --src I:/cc-tmp/models-src --wav X.wav
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

#: The build `worker/ultra_export.py` writes. Overridable, because a model
#: directory is 1,3 GB of build product and does not belong in a lane's tree.
DEFAULT_ONNX_DIR = os.environ.get("SOTTO_ULTRA_ONNX_DIR", str(HERE / "models" / "parakeet-ultra-onnx"))
#: The downloaded checkpoint (ultra.safetensors + ultra-config.json +
#: ultra-tokenizer.json). Nothing here writes to it.
DEFAULT_SRC_DIR = os.environ.get("SOTTO_ULTRA_SRC_DIR", str(HERE / "models" / "parakeet-ultra"))
#: The NeMo mel graph, reused as a front end. It is a graph, not weights.
PREPROCESSOR = "preprocessor.onnx"

PRODUCER = "ultra"


def _utf8_streams() -> None:
    """Same convention as the other engines: captions are UTF-8 JSON."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------
def _decode_tokenizer(path: Path):
    import tokenizers

    tokenizer = tokenizers.Tokenizer.from_file(str(path))
    vocab = json.loads(Path(path).read_text(encoding="utf-8"))["model"]["vocab"]
    # Everything below 8192 is text; 8192 is <blk>. The specials (0..): the
    # generated stream for this model is plain text tokens only, and a special
    # that slipped through would print as "<|...|>" in a caption.
    specials = {index for piece, index in vocab.items() if piece.startswith("<") and piece.endswith(">")}
    return tokenizer, specials


def _segments(tokens, durations, frame_seconds: float, decode) -> list[dict]:
    """One segment per sentence, timed from the TDT durations.

    Same shape the panel consumes from the Redux lane (``text``/``start``/
    ``end``); a sentence ends on ``. ! ?`` in the decoded piece stream.
    """
    segments: list[dict] = []
    pending: list[int] = []
    start = 0.0
    frame = 0.0
    for token, duration in zip(tokens, durations):
        if not pending:
            start = frame
        pending.append(token)
        frame += duration * frame_seconds
        piece = decode([token]).strip()
        if piece.endswith((".", "?", "!")):
            segments.append({"text": decode(pending).strip(), "start": round(start, 2),
                             "end": round(frame, 2)})
            pending = []
    if pending:
        text = decode(pending).strip()
        if text:
            segments.append({"text": text, "start": round(start, 2), "end": round(frame, 2)})
    return segments


# ---------------------------------------------------------------------------
# Front ends
# ---------------------------------------------------------------------------
class NemoFeatures:
    """The export's own mel graph: 16 kHz PCM -> [B,T,128] + attention mask.

    Deliberately the same graph the Redux export ships, so the two engines are
    fed by the same instrument instead of by two implementations of the NeMo
    preprocessor that could drift.
    """

    def __init__(self, onnx_dir: Path):
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self._session = ort.InferenceSession(str(Path(onnx_dir) / PREPROCESSOR), options,
                                             providers=["CPUExecutionProvider"])

    def __call__(self, pcm):
        import numpy as np

        features, lengths = self._session.run(None, {"waveforms": pcm[None].astype(np.float32),
                                                    "waveforms_lens": np.array([pcm.size], dtype=np.int64)})
        frames = int(lengths[0])
        mask = (np.arange(features.shape[2]) < frames).astype(np.int64)
        return np.ascontiguousarray(features[0, :, :].T)[None], mask[None]


class HfFeatures:
    """transformers' own extractor for this checkpoint family."""

    def __init__(self):
        from transformers import ParakeetFeatureExtractor

        self._extractor = ParakeetFeatureExtractor(feature_size=128)

    def __call__(self, pcm):
        batch = self._extractor(pcm, sampling_rate=16000, return_tensors="pt")
        return batch["input_features"].numpy(), batch["attention_mask"].numpy()


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------
class OnnxBackend:
    """Ultra through the export's published decode loop (CPU, onnxruntime)."""

    name = "ultra-onnx"
    producer = PRODUCER

    def __init__(self, model_dir: str | os.PathLike, threads: int = 0):
        model_path = Path(model_dir)
        if not (model_path / "encoder-model.onnx").is_file():
            raise SystemExit(
                "parakeet_ultra: no ONNX build in %s\n"
                "  build it once (no download, the checkpoint is on disk):\n"
                "    python worker/ultra_export.py --src <checkpoint dir> --out %s\n"
                "  --reference-transcribe <redux export>/transcribe.py" % (model_path, model_path)
            )
        for candidate in (str(model_path), str(model_path.parent)):
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
        import transcribe as reference

        self.model_dir = str(model_path)
        self.threads = threads
        self._engine = reference.OnnxParakeet(model_path, threads=(None if threads == 0 else int(threads)))

    def transcribe(self, pcm):
        result = self._engine.transcribe(pcm, "segment")
        return str(result.get("text") or "").strip(), list(result.get("segments") or ())


class TorchBackend:
    """Ultra through its own modules, float16 on CUDA when present.

    ``greedy`` is the export's TDT walk, not ``ParakeetForTDT.generate``: the
    reference loop is the contract the tree ships, and a second decoder would
    be a second thing to get wrong.
    """

    name = "ultra-torch"
    producer = PRODUCER

    def __init__(self, src_dir: str | os.PathLike, device: str = "auto", frontend: str = "nemo",
                 onnx_dir: str | os.PathLike | None = None):
        import torch

        self._torch = torch
        self.src = Path(src_dir)
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        self.dtype = torch.float16 if device == "cuda" else torch.float32

        config_json = self.src / "ultra-config.json"
        raw = json.loads(config_json.read_text(encoding="utf-8"))
        raw.pop("architectures", None)
        from transformers import ParakeetTDTConfig, ParakeetForTDT

        self.config = ParakeetTDTConfig(**raw)
        # Meta device + assign=True: the loader never holds a float32 copy of
        # 0,6 B parameters on top of the checkpoint. Measured on the owner's box
        # 2026-11-04: the naive order peaked ~6 GB of commit for a 1,25 GB file,
        # on a machine already freezing under another lane's load.
        with torch.device("meta"):
            model = ParakeetForTDT(self.config)
        from safetensors.torch import load_file

        state = load_file(str(self.src / "ultra.safetensors"))
        unloaded = [key for key in state if key.startswith("vad_head.")]
        for key in unloaded:
            del state[key]
        missing, unexpected = model.load_state_dict(state, strict=False, assign=True)
        del state
        if missing or unexpected:
            raise SystemExit("parakeet_ultra: checkpoint does not match ParakeetForTDT "
                             "(missing=%r unexpected=%r)" % (missing[:6], unexpected[:6]))
        self.unmapped = tuple(sorted(unloaded))
        # O `assign=True` so' substitui as chaves que o CHECKPOINT tem. Um buffer
        # que o modulo CRIA (e nao carrega) fica no device `meta`, e o `.to()`
        # seguinte recusa o passeio inteiro com "Cannot copy out of meta tensor"
        # -- medido nesta maquina a 2026-11-04, e a lista e' de UM nome:
        # `encoder.encode_positions.inv_freq` (persistent=False, construido por
        # `compute_default_relative_positional_parameters`). Um placeholder de
        # zeros deixa o `.to()` correr; o buffer e' RECONSTRUIDO pela funcao do
        # proprio modulo DEPOIS do cast, e em float32: e' uma frequencia de
        # rotacao, e metade da precisao dela degrada a posicao.
        meta_buffers = [name for name, buf in model.named_buffers() if buf.is_meta]
        for name in meta_buffers:
            if name != 'encoder.encode_positions.inv_freq':
                raise SystemExit('parakeet_ultra: buffer %r ficou em meta e nao ha' % name)
            model.encoder.encode_positions.inv_freq = torch.zeros(
                model.encoder.encode_positions.inv_freq.shape,
                dtype=model.encoder.encode_positions.inv_freq.dtype)
        self.model = model.eval().to(device, dtype=self.dtype)
        if meta_buffers:
            positions = self.model.encoder.encode_positions
            positions.inv_freq = positions.compute_default_relative_positional_parameters(
                positions.config, device=device).float()
        if self.dtype == torch.float16:
            # The predictor is 8 M parameters and 2 LSTM layers: cuDNN's RNN
            # kernels are the one part of this graph that does not want half
            # precision, and it costs nothing to keep it in float32.
            self.model.decoder.float()
        self.frame_seconds = 0.08
        self.vocab_size = int(self.config.vocab_size)
        self.blank_id = int(self.config.blank_token_id)
        self.durations = [int(value) for value in self.config.durations]
        self.max_symbols_per_step = int(self.config.max_symbols_per_step)
        self._state_shape = (int(self.config.num_decoder_layers), 1, int(self.config.decoder_hidden_size))

        self._frontend_name = frontend
        if frontend == "nemo":
            self._features = NemoFeatures(Path(onnx_dir or DEFAULT_ONNX_DIR))
        else:
            self._features = HfFeatures()
        self._tokenizer, self._specials = _decode_tokenizer(self.src / "ultra-tokenizer.json")

    def _decode(self, ids) -> str:
        return self._tokenizer.decode([int(i) for i in ids])

    def greedy(self, features, mask):
        """The export's own TDT walk, step for step, on torch tensors.

        Deliberately NOT ``model.generate``: the reference loop is the contract
        this tree already ships (`transcribe.py`), and reusing its arithmetic
        here is what makes the torch arm comparable to the two ONNX arms
        instead of comparable to a second implementation of the same idea.
        """
        torch = self._torch
        model = self.model
        with torch.inference_mode():
            hidden = model.encoder(input_features=features, attention_mask=mask).last_hidden_state
            frames = int(hidden.shape[1])
            state = torch.zeros(self._state_shape, device=hidden.device, dtype=torch.float32)
            cell = torch.zeros_like(state)
            token = self.blank_id
            tokens: list[int] = []
            durations: list[int] = []
            frame = 0
            steps = self.max_symbols_per_step * frames
            while frame < frames and steps > 0:
                encoder_frame = hidden[:, frame:frame + 1, :].transpose(1, 2)   # [1,1024,1]
                enc = model.encoder_projector(encoder_frame.transpose(1, 2))    # [1,1,640]
                dec, (hidden_state, cell_state) = model.decoder.lstm(
                    model.decoder.embedding(torch.tensor([[token]], device=hidden.device)), (state, cell))
                dec = model.decoder.decoder_projector(dec).to(enc.dtype)
                logits = model.joint.head(model.joint.activation(enc + dec))[0, 0]
                token = int(logits[: self.vocab_size].argmax())
                duration = self.durations[int(logits[self.vocab_size:].argmax())]
                if token == self.blank_id and duration == 0:
                    duration = 1
                tokens.append(token)
                durations.append(duration)
                frame += duration
                if token != self.blank_id:
                    state, cell = hidden_state, cell_state
                steps -= 1
        return tokens, durations

    def tokens(self, pcm):
        """Raw (token ids, durations) for one waveform -- the parity surface."""
        torch = self._torch
        features, mask = self._features(pcm)
        return self.greedy(
            torch.from_numpy(features).to(self.device, dtype=self.dtype),
            torch.from_numpy(mask).to(self.device),
        )

    def transcribe(self, pcm):
        sequence, durations = self.tokens(pcm)
        keep = [(token, duration) for token, duration in zip(sequence, durations)
                if 0 < token < self.vocab_size and token not in self._specials]
        if not keep:
            return "", []
        text = self._decode([token for token, _ in keep]).strip()
        segments = _segments([token for token, _ in keep], [duration for _, duration in keep],
                             self.frame_seconds, self._decode)
        return text, segments

    def peak_vram_mb(self) -> float | None:
        if self.device != "cuda":
            return None
        return round(self._torch.cuda.max_memory_allocated() / 1e6, 1)


def load_backend(backend: str, onnx_dir=None, src_dir=None, device="auto", frontend="nemo", threads=0):
    started = time.perf_counter()
    if backend == "onnx":
        engine = OnnxBackend(onnx_dir or DEFAULT_ONNX_DIR, threads=threads)
    else:
        engine = TorchBackend(src_dir or DEFAULT_SRC_DIR, device=device, frontend=frontend, onnx_dir=onnx_dir)
    engine.load_s = round(time.perf_counter() - started, 2)
    return engine


# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    _utf8_streams()
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--backend", choices=("onnx", "torch"), default="onnx")
    ap.add_argument("--onnx-dir", default=None)
    ap.add_argument("--src", default=None)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--frontend", choices=("nemo", "hf"), default="nemo")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    import numpy as np
    import soundfile as sf

    data, rate = sf.read(args.wav, dtype="float32", always_2d=True)
    pcm = data.mean(axis=1)
    if rate != 16000:
        import soxr

        pcm = soxr.resample(pcm, rate, 16000).astype(np.float32)
    pcm = np.ascontiguousarray(pcm, dtype=np.float32)

    engine = load_backend(args.backend, args.onnx_dir, args.src, args.device, args.frontend, args.threads)
    started = time.perf_counter()
    text, segments = engine.transcribe(pcm)
    elapsed = time.perf_counter() - started
    row = {"engine": engine.name, "load_s": engine.load_s, "infer_s": round(elapsed, 3),
           "audio_s": round(pcm.size / 16000, 2),
           "xrt": round((pcm.size / 16000) / elapsed, 3) if elapsed else None,
           "text": text, "segments": [dict(s) for s in segments]}
    if args.json:
        print(json.dumps(row, ensure_ascii=False))
    else:
        print("%s load=%ss infer=%ss xrt=%sx" % (row["engine"], row["load_s"], row["infer_s"], row["xrt"]))
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
