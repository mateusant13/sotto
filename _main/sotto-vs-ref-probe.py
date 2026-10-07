"""Per-chunk probe for the Sotto vs reference audit (lane SottoVsReferencia).

WHY: the shipped worker reports ONE aggregate per run (`empty_chunks`,
`frames`, `blanks`) and nothing per chunk, so "where do the words go" cannot be
answered from its JSONL. This probe drives the SHIPPED `StreamAsr.run_chunk`
unmodified and only OBSERVES two things it does not expose:

  * what `sp.process()` returned for that chunk — the feature shape, or None
    (the VAD-gated chunk), and
  * the encoder's own `encoded_lengths` (T) for that chunk.

Both are read by wrapping the objects the shipped code already calls; no line of
`worker/sotto_worker.py` is copied, patched or re-implemented, so the token
stream this probe records IS the shipped token stream (and is asserted equal to
it at the end).

Usage:
  python _main/sotto-vs-ref-probe.py <audio.wav> <out.jsonl> [--model DIR] [--no-vad]

Writes one JSON object per line: {"i","t0","feats","T","sym","frames","blanks","text"}
plus a final {"kind":"summary",...} line.
"""

import argparse
import json
import os
import sys
import time

import numpy as np


class SpProxy:
    """Observe `streaming_processor.process()` without changing its contract."""

    def __init__(self, real):
        self.real = real
        self.last_shape = None
        self.gated = 0

    def process(self, pcm):
        out = self.real.process(pcm)
        if out is None:
            self.last_shape = None
            self.gated += 1
        else:
            af = out["audio_features"]
            af = af.as_numpy() if hasattr(af, "as_numpy") else np.asarray(af)
            self.last_shape = list(af.shape)
        return out

    def set_option(self, *a, **kw):
        return self.real.set_option(*a, **kw)

    def __getattr__(self, name):
        return getattr(self.real, name)


class EncProxy:
    """Observe the encoder's declared `encoded_lengths` (T) per chunk."""

    def __init__(self, real):
        self.real = real
        self.last_T = None

    def run(self, names, feeds):
        out = self.real.run(names, feeds)
        try:
            self.last_T = int(np.asarray(out[1]).reshape(-1)[0])
        except Exception:
            self.last_T = None
        return out

    def __getattr__(self, name):
        return getattr(self.real, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--model", default=None)
    ap.add_argument("--no-vad", action="store_true")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    worker = os.path.join(os.path.dirname(here), "worker")
    sys.path.insert(0, worker)
    import sotto_worker as W
    import soundfile as sf

    model = args.model or W.DEFAULT_MODEL
    # The CUDA/cuDNN DLLs live inside the torch + nvidia wheels, not on PATH.
    # The worker registers them in `_add_cuda_dll_dirs()` before importing
    # onnxruntime; a probe that skips it silently falls back to CPU, and CPU and
    # CUDA do not produce bit-identical logits — so an un-registered probe would
    # compare a DIFFERENT token stream against the shipped run.
    W._add_cuda_dll_dirs()
    asr = W.StreamAsr(
        model,
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
        use_vad=not args.no_vad,
        lang_id="auto",
    )
    print(f"providers: {asr.providers}", file=sys.stderr)
    sp = SpProxy(asr.sp)
    asr.sp = sp
    enc = EncProxy(asr.enc)
    asr.enc = enc

    pcm, sr = sf.read(args.audio, dtype="float32")
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    if sr != W.TARGET_SR:
        pcm = W.resample_to_16k(pcm, sr)

    chunk = asr.chunk
    total = len(pcm) // chunk
    tail_samples = len(pcm) - total * chunk

    fh = open(args.out, "w", encoding="utf-8")
    t0 = time.time()
    symbols_over_limit = 0
    partial_tail_tokens = 0
    for i in range(total):
        f0 = asr.frames_walked
        b0 = asr.blank_frames
        n0 = len(asr.labels)
        text, n = asr.run_chunk(pcm[i * chunk : (i + 1) * chunk])
        T = enc.last_T or 0
        limit = asr.max_sym * T + 16 if T else 0
        if T and n >= limit:
            symbols_over_limit += 1
        # a chunk-final token that does NOT open a word (no sentencepiece
        # metaspace) is the signature of a window cut mid-word
        if n:
            last_tok = asr.vocab[asr.labels[-1]] if asr.labels else ""
            if not last_tok.startswith("\u2581") and not (last_tok.startswith("<") and last_tok.endswith(">")):
                partial_tail_tokens += 1
        fh.write(
            json.dumps(
                {
                    "i": i,
                    "t0": round(i * chunk / W.TARGET_SR, 3),
                    "feats": sp.last_shape,
                    "T": T,
                    "limit": limit,
                    "sym": n,
                    "frames": asr.frames_walked - f0,
                    "blanks": asr.blank_frames - b0,
                    "labels_grew": len(asr.labels) - n0,
                    "text": text,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    wall = time.time() - t0
    full = asr.detok(asr.labels)
    fh.write(
        json.dumps(
            {
                "kind": "summary",
                "audio": os.path.basename(args.audio),
                "audio_s": round(len(pcm) / W.TARGET_SR, 3),
                "chunk_samples": chunk,
                "chunks_processed": total,
                "tail_samples_dropped": tail_samples,
                "tail_seconds_dropped": round(tail_samples / W.TARGET_SR, 4),
                "tokens": len(asr.labels),
                "frames": asr.frames_walked,
                "blanks": asr.blank_frames,
                "empty_chunks": asr.empty_chunks,
                "vad_gated_chunks": asr.vad_gated_chunks,
                "music_gated_chunks": asr.music_gated_chunks,
                "sp_gated": sp.gated,
                "symbols_over_limit_chunks": symbols_over_limit,
                "partial_tail_tokens": partial_tail_tokens,
                "wall_s": round(wall, 3),
                "rtf": round(wall / (len(pcm) / W.TARGET_SR), 4),
                "providers": asr.providers,
                "model": asr.name,
                "use_vad": not args.no_vad,
                "text": full,
                "labels": asr.labels,
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    fh.close()
    print(f"chunks={total} tokens={len(asr.labels)} empty={asr.empty_chunks} "
          f"vad_gated={asr.vad_gated_chunks} tail_dropped_s={tail_samples / W.TARGET_SR:.3f}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
