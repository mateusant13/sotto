#!/usr/bin/env python3
"""Build the ONNX form of a Parakeet TDT checkpoint (moondream/parakeet-ultra).

WHY THIS EXISTS
---------------
`worker/models/parakeet-redux-onnx-int4/` is read by `redux_live.OnnxBackend`,
which delegates the whole decode to the export's OWN `transcribe.py`: the NeMo
mel front end, the greedy token-and-duration walk, the word timing and the
pause-based segmentation. That is the contract the tree already runs.

Ultra is the same architecture as Redux -- same 24-layer 1024-d conformer,
640-d 2-layer LSTM predictor, 8193-token vocabulary with blank 8192, durations
[0,1,2,3,4] -- and its checkpoint carries the SAME tensor names as
`transformers.ParakeetForTDT` (0 missing keys; the only extras are Moondream's
six `vad_head.*` tensors). So the least new surface is not a second runtime: it
is this exporter, which writes the same three-graph ABI that `transcribe.py`
already speaks.

    preprocessor.onnx        reused as-is: the NeMo mel is a front end, not
                             weights, and Ultra is the same Photon lineage.
    encoder-model.onnx       audio_signal [B,128,T] + length -> outputs
                             [B,1024,T/8] + encoded_lengths
    decoder_joint-model.onnx encoder_outputs [B,1024,1] + targets [B,1] +
                             LSTM states -> logits [B,1,1,8198] + new states
    vad-model.onnx           optional: features -> speech probability per
                             encoder frame, from Ultra's own `vad_head.*`
    config.json / vocab.txt  the two files `transcribe.py` reads

USO
    python worker/ultra_export.py --src I:/cc-tmp/models-src \\
        --out I:/cc-tmp/models-src/parakeet-ultra-onnx \\
        --reference-transcribe I:/cc-tmp/models-src/parakeet-redux-onnx/transcribe.py

`--verify <wav>` additionally decodes one clip through torch and through the
export and prints whether the two token streams agree.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import torch


# ---------------------------------------------------------------------------
# The checkpoint, as a torch model
# ---------------------------------------------------------------------------
def build_config(src: Path):
    from transformers import ParakeetTDTConfig

    raw = json.loads((src / "ultra-config.json").read_text(encoding="utf-8"))
    raw.pop("architectures", None)
    return ParakeetTDTConfig(**raw), raw


def load_model(src: Path, dtype=torch.float32):
    """Build + load without ever holding two full copies of the weights.

    MEASURED 2026-11-04: instantiating the model and THEN loading the state dict
    peaked ~6 GB of commit on a box the owner was already freezing. Building on
    the meta device and assigning the loaded tensors (`assign=True`) keeps one
    copy (1,25 GB fp16 on disk) plus the exported dtype, instead of three.
    """
    from safetensors.torch import load_file
    from transformers import ParakeetForTDT

    config, raw = build_config(src)
    with torch.device("meta"):
        model = ParakeetForTDT(config)
    state = load_file(str(src / "ultra.safetensors"))
    extra = sorted(k for k in state if k.startswith("vad_head."))
    for key in extra:
        del state[key]
    missing, unexpected = model.load_state_dict(state, strict=False, assign=True)
    del state
    materialize_meta(model)
    # The ONLY tolerated difference is the six vad_head tensors this model class
    # does not carry; anything else means the exporter is describing the wrong
    # architecture and must stop instead of exporting a half-loaded network.
    if missing or unexpected:
        raise SystemExit(
            "ckpt does not match ParakeetForTDT: missing=%r unexpected=%r" % (missing[:8], unexpected[:8])
        )
    model.eval()
    if dtype not in (torch.float32, torch.float16):
        raise SystemExit("unsupported dtype %r" % (dtype,))
    model = model.to(dtype=dtype)
    return model, config, raw, extra


def materialize_meta(model) -> None:
    """Fill the tensors a checkpoint legitimately does not carry.

    `assign=True` leaves everything outside the checkpoint on the meta device
    (all zeros-size, no storage). For this architecture exactly one such tensor
    exists and it MATTERS: the relative-positional `inv_freq` buffer, which the
    checkpoint does not contain because it is computed from the config. Writing
    it as zeros would silently destroy the attention bias, so it is recomputed
    by the module's own static method -- and anything else left on meta raises
    instead of exporting a graph made of nothing.
    """
    from transformers.models.parakeet.modeling_parakeet import ParakeetEncoderRelPositionalEncoding

    positions = model.encoder.encode_positions
    if positions.inv_freq.is_meta:
        positions.inv_freq = ParakeetEncoderRelPositionalEncoding.compute_default_relative_positional_parameters(
            positions.config)
    stale = [name for name, tensor in list(model.named_parameters()) + list(model.named_buffers())
             if tensor.is_meta]
    if stale:
        raise SystemExit("unmaterialized tensors after load: %r" % (stale[:8],))


# ---------------------------------------------------------------------------
# Graph wrappers, each one exactly the ABI the reference loop calls
# ---------------------------------------------------------------------------
class EncoderGraph(torch.nn.Module):
    def __init__(self, model):
        super().__init__()
        self.encoder = model.encoder

    def forward(self, audio_signal: torch.Tensor, length: torch.Tensor):
        # The export's ABI is mel-major ([B,128,T], the Redux encoder's input);
        # the HF encoder wants time-major ([B,T,128]). One transpose, here.
        features = audio_signal.transpose(1, 2)
        mask = torch.arange(features.shape[1], device=features.device)[None, :] < length[:, None]
        hidden = self.encoder(input_features=features, attention_mask=mask,
                              output_attention_mask=False).last_hidden_state
        return hidden.transpose(1, 2), self.encoder._get_subsampling_output_length(length)


class DecoderJointGraph(torch.nn.Module):
    """The predictor + joiner of one step, fused like the Redux export."""

    def __init__(self, model):
        super().__init__()
        self.embedding = model.decoder.embedding
        self.lstm = model.decoder.lstm
        self.decoder_projector = model.decoder.decoder_projector
        self.encoder_projector = model.encoder_projector
        self.head = model.joint.head
        self.activation = model.joint.activation

    def forward(self, encoder_outputs, targets, target_length, state_1, state_2):
        enc = self.encoder_projector(encoder_outputs.transpose(1, 2))       # [B,1,640]
        emb = self.embedding(targets.long())                                # [B,1,640]
        lstm_out, (hidden, cell) = self.lstm(emb, (state_1, state_2))
        dec = self.decoder_projector(lstm_out)                              # [B,1,640]
        logits = self.head(self.activation(enc + dec))                      # [B,1,8198]
        return logits[:, None, :, :], target_length, hidden, cell


class VadGraph(torch.nn.Module):
    """Moondream's VAD head, sitting on the encoder's subsampler output."""

    def __init__(self, model, vad_state):
        super().__init__()
        self.encoder = model.encoder
        self.subsampling = model.encoder.subsampling
        self.proj = torch.nn.Conv1d(1024, 128, 1)
        self.ctx = torch.nn.Conv1d(128, 128, 5, padding=2)
        self.out = torch.nn.Conv1d(128, 1, 1)
        self.proj.load_state_dict({"weight": vad_state["vad_head.proj.weight"],
                                   "bias": vad_state["vad_head.proj.bias"]})
        self.ctx.load_state_dict({"weight": vad_state["vad_head.ctx.weight"],
                                  "bias": vad_state["vad_head.ctx.bias"]})
        self.out.load_state_dict({"weight": vad_state["vad_head.out.weight"],
                                  "bias": vad_state["vad_head.out.bias"]})

    def forward(self, audio_signal: torch.Tensor, length: torch.Tensor):
        features = audio_signal.transpose(1, 2)                  # [B,T,128]
        mask = torch.arange(features.shape[1], device=features.device)[None, :] < length[:, None]
        hidden = self.subsampling(features, mask)                # [B,T/8,1024]
        x = hidden.transpose(1, 2)                               # [B,1024,T/8]
        x = torch.relu(self.proj(x))
        x = torch.relu(self.ctx(x))
        prob = torch.sigmoid(self.out(x))[:, 0]                  # [B,T/8]
        return prob, self.encoder._get_subsampling_output_length(length)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
#: Everything a finished build directory is allowed to contain. torch writes
#: one loose blob per tensor name; those are folded back into the three graphs.
GRAPHS = ("encoder-model.onnx", "decoder_joint-model.onnx", "vad-model.onnx")
#: Everything a finished build directory is allowed to contain. torch writes one
#: loose blob per tensor name; those are folded into a ``<graph>.onnx.data``
#: sidecar -- the same two-file layout `worker/models/nemotron-3.5-.../` uses.
ARTIFACTS = set(GRAPHS) | {name + ".data" for name in GRAPHS} | {
    "preprocessor.onnx", "config.json", "vocab.txt", "transcribe.py"}


def consolidate(out: Path) -> None:
    """Fold the loose per-tensor blobs into one sidecar per graph.

    A monolithic fp32 file is NOT an option: the encoder is 2,4 GB of weights
    and protobuf refuses a message over 2 GB ("Protobuf parsing failed",
    measured). One `.onnx.data` sidecar per graph is both the only shape that
    loads and the shape this tree already reads.
    """
    import onnx
    from onnx.external_data_helper import convert_model_to_external_data

    for name in GRAPHS:
        path = out / name
        if not path.is_file():
            continue
        model = onnx.load(str(path))
        sidecar = name + ".data"
        convert_model_to_external_data(model, all_tensors_to_one_file=True, location=sidecar,
                                       size_threshold=1024, convert_attribute=False)
        onnx.save_model(model, str(path), save_as_external_data=True, all_tensors_to_one_file=True,
                        location=sidecar, size_threshold=1024)
    for blob in out.iterdir():
        if blob.is_file() and blob.name not in ARTIFACTS:
            blob.unlink()


def export(model, config, raw, vad_state, out: Path, reference_transcribe: Path | None, opset: int) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    frames = 600  # 6 s of mel frames: still dynamic, just a concrete trace size

    encoder = EncoderGraph(model)
    with torch.inference_mode():
        torch.onnx.export(
            encoder,
            (torch.zeros(1, 128, frames), torch.tensor([frames], dtype=torch.int64)),
            str(out / "encoder-model.onnx"),
            input_names=["audio_signal", "length"],
            output_names=["outputs", "encoded_lengths"],
            dynamic_axes={"audio_signal": {0: "batch", 2: "time"},
                          "length": {0: "batch"},
                          "outputs": {0: "batch", 2: "frames"},
                          "encoded_lengths": {0: "batch"}},
            opset_version=opset,
            do_constant_folding=True,
        )
    written.append("encoder-model.onnx")
    print("  encoder exported", flush=True)

    head = DecoderJointGraph(model)
    states = torch.zeros(2, 1, config.decoder_hidden_size)
    with torch.inference_mode():
        torch.onnx.export(
            head,
            (torch.zeros(1, 1024, 1), torch.zeros(1, 1, dtype=torch.int32),
             torch.ones(1, dtype=torch.int32), states, states),
            str(out / "decoder_joint-model.onnx"),
            input_names=["encoder_outputs", "targets", "target_length",
                         "input_states_1", "input_states_2"],
            output_names=["outputs", "prednet_lengths", "output_states_1", "output_states_2"],
            dynamic_axes={"encoder_outputs": {0: "batch"},
                          "targets": {0: "batch"},
                          "target_length": {0: "batch"},
                          "input_states_1": {1: "batch"},
                          "input_states_2": {1: "batch"},
                          "outputs": {0: "batch"},
                          "prednet_lengths": {0: "batch"},
                          "output_states_1": {1: "batch"},
                          "output_states_2": {1: "batch"}},
            opset_version=opset,
            do_constant_folding=True,
        )
    written.append("decoder_joint-model.onnx")
    print("  decoder_joint exported", flush=True)

    if vad_state:
        vad = VadGraph(model, vad_state)
        vad.eval()
        try:
            with torch.inference_mode():
                torch.onnx.export(
                    vad,
                    (torch.zeros(1, 128, frames), torch.tensor([frames], dtype=torch.int64)),
                    str(out / "vad-model.onnx"),
                    input_names=["audio_signal", "length"],
                    output_names=["probabilities", "valid_lengths"],
                    dynamic_axes={"audio_signal": {0: "batch", 2: "time"},
                                  "length": {0: "batch"},
                                  "probabilities": {0: "batch", 1: "frames"},
                                  "valid_lengths": {0: "batch"}},
                    opset_version=opset,
                    do_constant_folding=True,
                )
            written.append("vad-model.onnx")
        except Exception as exc:  # noqa: BLE001
            print("vad-model.onnx NOT exported: %s: %s" % (type(exc).__name__, exc))

    meta = {
        "model_type": "nemo-conformer-tdt",
        "features_size": 128,
        "subsampling_factor": 8,
        "max_tokens_per_step": int(config.max_symbols_per_step),
        "vocab_size": int(config.vocab_size),
        "blank_token_id": int(config.blank_token_id),
        "durations": list(config.durations),
        "encoder_frame_seconds": 0.08,
        "sample_rate": 16000,
        "source": "moondream/parakeet-ultra",
        "weights": "%s ONNX graph (worker/ultra_export.py)" % args.dtype,
        "checkpoint_config": raw,
    }
    (out / "config.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    written.append("config.json")

    if reference_transcribe and reference_transcribe.is_file():
        shutil.copyfile(reference_transcribe, out / "transcribe.py")
        written.append("transcribe.py")
        # The mel is a front end, not weights: the same graph the Redux export
        # ships feeds Ultra, so both engines are measured through ONE
        # implementation of the NeMo preprocessor instead of two that could drift.
        preprocessor = reference_transcribe.parent / "preprocessor.onnx"
        if preprocessor.is_file():
            shutil.copyfile(preprocessor, out / "preprocessor.onnx")
            written.append("preprocessor.onnx")
    print("  consolidating external weights", flush=True)
    consolidate(out)
    print("  consolidated", flush=True)
    return written


# ---------------------------------------------------------------------------
# vocab.txt, in the exact shape onnx-asr writes and transcribe.py reads
# ---------------------------------------------------------------------------
def write_vocab(tokenizer_json: Path, path: Path) -> int:
    vocab = json.loads(Path(tokenizer_json).read_text(encoding="utf-8"))["model"]["vocab"]
    rows = sorted(vocab.items(), key=lambda item: item[1])
    lines = ["%s %d" % (piece, index) for piece, index in rows]
    blank = rows[-1][1] + 1
    lines.append("<blk> %d" % blank)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(lines)


# ---------------------------------------------------------------------------
# The verification: same audio, torch vs the export, token stream compared
# ---------------------------------------------------------------------------
def read_wav16(path: Path) -> np.ndarray:
    import soundfile as sf

    data, rate = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if rate != 16000:
        import soxr

        mono = soxr.resample(mono, rate, 16000).astype(np.float32)
    return mono.astype(np.float32)


def verify(out: Path, src: Path, wav: Path) -> int:
    """Same audio, one decode contract, two execution paths.

    Both arms are driven by the SAME greedy walk (the export's `transcribe.py`
    via `parakeet_ultra.OnnxBackend`, and the torch modules via
    `parakeet_ultra.TorchBackend.tokens`), so a difference here is a difference
    in the exported GRAPH -- which is exactly what this exporter can get wrong.
    """
    import parakeet_ultra

    pcm = read_wav16(wav)
    torch_backend = parakeet_ultra.TorchBackend(src, device="cpu", frontend="nemo", onnx_dir=out)
    onnx_backend = parakeet_ultra.OnnxBackend(out)
    reference = onnx_backend._engine
    reference_tokens, _ = reference.greedy(reference.encode(pcm))
    torch_tokens, _ = torch_backend.tokens(pcm)
    same = torch_tokens == reference_tokens
    print("PARITY torch=%d tokens onnx=%d tokens identical=%s"
          % (len(torch_tokens), len(reference_tokens), same))
    if not same:
        first = next((i for i, (a, b) in enumerate(zip(torch_tokens, reference_tokens)) if a != b),
                     min(len(torch_tokens), len(reference_tokens)))
        print("  first divergence at %d: torch=%r onnx=%r"
              % (first, torch_tokens[first:first + 8], reference_tokens[first:first + 8]))
    text = onnx_backend.transcribe(pcm)[0]
    print("TEXT %s" % text)
    return 0 if same else 1


# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="I:/cc-tmp/models-src")
    ap.add_argument("--out", default="I:/cc-tmp/models-src/parakeet-ultra-onnx")
    ap.add_argument("--tokenizer", default=None, help="default: <src>/ultra-tokenizer.json")
    ap.add_argument("--reference-transcribe", default=None)
    ap.add_argument("--opset", type=int, default=17)
    ap.add_argument("--dtype", choices=("float32", "float16"), default="float32")
    ap.add_argument("--verify", default=None, help="wav decoded through torch AND the export")
    args = ap.parse_args(argv)

    src = Path(args.src)
    out = Path(args.out)
    model, config, raw, extra = load_model(src, dtype=getattr(torch, args.dtype))
    vad_state = {}
    if extra:
        from safetensors.torch import load_file

        full = load_file(str(src / "ultra.safetensors"))
        vad_state = {k: full[k] for k in extra}
        del full
    print("checkpoint  %s" % src)
    print("architecture ParakeetForTDT vocab=%d blank=%d durations=%s decoder=%dd/%dL"
          % (config.vocab_size, config.blank_token_id, list(config.durations),
             config.decoder_hidden_size, config.num_decoder_layers))
    print("unmapped tensors: %s" % (", ".join(sorted(vad_state)) or "none"))

    written = export(model, config, raw, vad_state, out,
                     Path(args.reference_transcribe) if args.reference_transcribe else None,
                     args.opset)
    tokenizer = Path(args.tokenizer) if args.tokenizer else src / "ultra-tokenizer.json"
    rows = write_vocab(tokenizer, out / "vocab.txt")
    print("vocab.txt   %d rows" % rows)
    for name in written:
        print("  %-26s %10d B" % (name, (out / name).stat().st_size))

    if args.verify:
        return verify(out, src, Path(args.verify))
    return 0


if __name__ == "__main__":
    sys.exit(main())
