"""Decode-arms probe for the Sotto vs reference audit (lane SottoVsReferencia).

WHY: the shipped `StreamAsr.run_chunk` re-primes the RNN-T prediction network
(`h`/`c` back to zero, first decoder call consumes only the blank) at EVERY
560 ms chunk boundary. That is a DECODE decision, documented in the worker's own
README, taken on a 13.44 s clip. This probe asks, with the same weights and the
same encoder features, what happens under two other priming policies — so the
answer to "why does it skip words" can be attributed to the code and not to the
model.

ARMS (only the predictor policy differs; the encoder, the front end, the chunk
grid, the argmax and the blank all stay identical):
  1 = shipped     : h/c re-primed to zero each chunk, first decode consumes blank
  2 = carry-state : h/c carried ACROSS chunk boundaries
  3 = carry+seed  : h/c carried, and the first decode of a chunk consumes the
                    LAST EMITTED symbol instead of the blank

Arm 1 is asserted equal to the shipped transcript on the same audio: if it is
not, this probe is measuring something else and must not be believed.

Usage:
  python _main/sotto-vs-ref-decode-arms.py <audio.wav> <out.json> [--seconds N] [--arms 1,2,3]
"""

import argparse
import json
import os
import sys
import time

import numpy as np


def arm_walk(asr, pcm, arm, max_seconds=0.0):
    """The shipped walk, with the predictor policy chosen by `arm`.

    Copied from `sotto_worker.StreamAsr.run_chunk` deliberately, line for line,
    so the ONLY difference between arms is where h/c and the seed target come
    from. Every other statement (feats, encoder call, joint argmax, blank,
    detok, counters) is identical, which is what makes an arm-vs-arm delta
    attributable.
    """
    np_ = asr.np
    chunk = asr.chunk
    total = len(pcm) // chunk
    if max_seconds:
        total = min(total, int(max_seconds * 16000) // chunk)

    # a fresh encoder state per arm: the caches are the ARM's, not a leftover
    cc, ct, ccl = _fresh_caches(asr)
    h = np_.zeros((2, 1, asr.hidden), np_.float32)
    c = np_.zeros((2, 1, asr.hidden), np_.float32)
    seed = np_.array([[asr.blank]], np_.int64)  # arm 3 re-seeds this
    labels = []
    frames = blanks = empty = vad_gated = 0
    t0 = time.time()
    per_chunk = []
    last_sym = asr.blank

    for i in range(total):
        pcm_chunk = pcm[i * chunk : (i + 1) * chunk]
        feats = asr.sp.process(pcm_chunk)
        if feats is None:
            vad_gated += 1
            per_chunk.append({"i": i, "sym": 0, "vad_gated": True})
            continue
        af = feats["audio_features"]
        af = af.as_numpy() if hasattr(af, "as_numpy") else np_.asarray(af)
        enc_out, enc_len, cc, ct, ccl = asr.enc.run(
            ["outputs", "encoded_lengths", "cache_last_channel_next",
             "cache_last_time_next", "cache_last_channel_len_next"],
            {
                "audio_signal": af.astype(np.float32),
                "length": np_.array([af.shape[1]], np_.int64),
                "cache_last_channel": cc,
                "cache_last_time": ct,
                "cache_last_channel_len": ccl,
                "lang_id": asr.lid,
            },
        )
        T = int(np_.asarray(enc_len).reshape(-1)[0])

        # ── the arm's priming policy ────────────────────────────────────────
        if arm == 1:
            h = np_.zeros((2, 1, asr.hidden), np_.float32)
            c = np_.zeros((2, 1, asr.hidden), np_.float32)
            first = np_.array([[asr.blank]], np_.int64)
        elif arm == 2:
            first = np_.array([[asr.blank]], np_.int64)
        else:  # arm 3
            first = np_.array([[last_sym]], np_.int64)

        dout, h, c = asr._decode(first, h, c)
        dd = np_.ascontiguousarray(np_.transpose(dout, (0, 2, 1))[0][-1].reshape(1, 1, asr.hidden), dtype=np.float32)

        limit = asr.max_sym * T + 16
        ti = guard = 0
        n = 0
        while ti < T and guard < limit:
            guard += 1
            e1 = np_.ascontiguousarray(enc_out[:, ti : ti + 1, :], dtype=np.float32)
            y = int(asr.joint.run(["joint_output"], {"encoder_output": e1, "decoder_output": dd})[0][0, 0].argmax())
            frames += 1
            if y == asr.blank:
                blanks += 1
                ti += 1
                continue
            labels.append(y)
            last_sym = y
            n += 1
            dout, h, c = asr._decode(np_.array([[y]], np_.int64), h, c)
            dd = np_.ascontiguousarray(np_.transpose(dout, (0, 2, 1))[0][-1].reshape(1, 1, asr.hidden), dtype=np.float32)
        if n == 0:
            empty += 1
        per_chunk.append({"i": i, "sym": n, "T": T})

    wall = time.time() - t0
    text = asr.detok(labels)
    return {
        "arm": arm,
        "audio_s": round(total * chunk / 16000, 3),
        "tokens": len(labels),
        "words": len(text.split()),
        "frames": frames,
        "blanks": blanks,
        "blank_frac": round(blanks / frames, 4) if frames else None,
        "empty_chunks": empty,
        "chunks": total,
        "vad_gated_chunks": vad_gated,
        "wall_s": round(wall, 3),
        "text": text,
        "per_chunk": per_chunk,
    }


def _fresh_caches(asr):
    import json as _json
    d = {"cache_last_channel": np.float32, "cache_last_time": np.float32,
         "cache_last_channel_len": np.int64}
    shapes = {}
    for i in asr.enc.get_inputs():
        if i.name in d:
            shapes[i.name] = tuple(i.shape)
    return (np.zeros(shapes["cache_last_channel"], d["cache_last_channel"]),
            np.zeros(shapes["cache_last_time"], d["cache_last_time"]),
            np.zeros(shapes["cache_last_channel_len"], d["cache_last_channel_len"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--seconds", type=float, default=0.0)
    ap.add_argument("--arms", default="1,2,3")
    ap.add_argument("--model", default=None)
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(os.path.dirname(here), "worker"))
    import sotto_worker as W
    import soundfile as sf

    pcm, sr = sf.read(args.audio, dtype="float32")
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    if sr != W.TARGET_SR:
        pcm = W.resample_to_16k(pcm, sr)
    pcm = np.ascontiguousarray(pcm, dtype=np.float32)

    # Same provider stack as the shipped run: `_add_cuda_dll_dirs()` is what
    # makes CUDA loadable from the torch/nvidia wheels, and a probe that skips
    # it falls back to CPU, whose logits differ from CUDA's.
    W._add_cuda_dll_dirs()
    asr = W.StreamAsr(args.model or W.DEFAULT_MODEL,
                      providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
                      use_vad=True, lang_id="auto")
    print(f"providers: {asr.providers}", file=sys.stderr)
    arms = [int(a) for a in args.arms.split(",")]
    out = {"arms": []}
    for a in arms:
        r = arm_walk(asr, pcm, a, args.seconds)
        out["arms"].append(r)
        print(f"arm {a}: tokens={r['tokens']} words={r['words']} empty={r['empty_chunks']}/{r['chunks']} "
              f"blank_frac={r['blank_frac']} wall={r['wall_s']}s", file=sys.stderr)
        print(f"  {r['text'][:180]}", file=sys.stderr)
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
