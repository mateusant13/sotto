"""Capture the RAW per-chunk detok text of a real decode, with NO audio device.

WHY THIS EXISTS (lane SottoWordSplit)
-------------------------------------
The owner reports a word split in half by a space in the captions ("shi t").
The registered cause is that `detok()` turns the word-start marker U+2581 into
a space and then `.strip()`s it away (`worker/sotto_worker.py:587`), while
`LineFormer.line()` joins the chunk texts with `" ".join(...)` — so every CHUNK
boundary becomes a WORD boundary.

That claim cannot be settled from the joined caption text alone: the joined
caption is exactly what destroys the evidence. This probe re-decodes a WAV with
the worker's OWN `StreamAsr` (never a copy of it), spies on `detok`'s `ids`, and
records for every 560 ms chunk BOTH

  * `raw`      — `"".join(vocab[i] ...).replace("\u2581", " ")`, NOT stripped:
                 the leading/trailing space IS the word-boundary fact, and
  * `stripped` — the same string `.strip()`ed, i.e. byte-for-byte what
                 `run_chunk()` returns on the shipped path.

`stripped` is asserted equal to `run_chunk()`'s own return value, so the trace
cannot silently drift from the shipped path.

NO AUDIO DEVICE IS OPENED: `soundfile` reads a file and the chunks are sliced
here. Nothing in this file imports or touches `sounddevice` / WASAPI.

Usage:
  pythonw.exe _main/word-split-trace.py --wav _main/pt-br-sample.wav \
      --out _main/word-split-trace.json
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(REPO, "worker")
sys.path.insert(0, WORKER)

MARK = "\u2581"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", default=os.path.join(HERE, "pt-br-sample.wav"))
    ap.add_argument("--out", default=os.path.join(HERE, "word-split-trace.json"))
    ap.add_argument("--config", default=os.path.join(WORKER, "config.json"))
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--lang-id", default=None)
    args = ap.parse_args()

    import sotto_worker as W  # noqa: E402

    W.limit_threads(args.threads)
    cfg = json.load(io.open(args.config, encoding="utf-8"))
    model_dir = cfg["model"]["dir"]
    if not os.path.isabs(model_dir):
        model_dir = os.path.join(WORKER, model_dir)
    use_vad = bool(cfg["model"].get("use_vad", True))
    lang = args.lang_id if args.lang_id is not None else cfg["model"].get("lang_id", "auto")

    import soundfile as sf  # noqa: E402

    pcm, sr = sf.read(args.wav, dtype="float32")
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    if sr != W.TARGET_SR:
        pcm = W.resample_to_16k(pcm, sr)

    t0 = time.time()
    asr = W.StreamAsr(model_dir, providers=None, use_vad=use_vad, lang_id=lang)
    load_s = time.time() - t0

    # Spy on `detok` so the RAW string is captured without touching the worker.
    spy = {}
    orig_detok = asr.detok

    def detok_spy(ids):
        spy["ids"] = list(ids)
        return orig_detok(ids)

    asr.detok = detok_spy

    chunk = asr.chunk
    total = len(pcm) // chunk
    rows = []
    for i in range(total):
        text, n = asr.run_chunk(pcm[i * chunk:(i + 1) * chunk])
        ids = spy.get("ids", [])
        parts = []
        for k in ids:
            t = asr.vocab[k]
            if t.startswith("<") and t.endswith(">"):
                continue
            parts.append(t)
        raw = "".join(parts).replace(MARK, " ")
        if raw.strip() != text:
            raise SystemExit(
                f"TRACE DRIFT at chunk {i}: stripped(raw)={raw.strip()!r} != run_chunk()={text!r}"
            )
        rows.append({
            "i": i,
            "start": round(i * chunk / W.TARGET_SR, 2),
            "end": round((i + 1) * chunk / W.TARGET_SR, 2),
            "n_tokens": n,
            "ids": ids,
            "first_tok": next(
                (asr.vocab[k] for k in ids
                 if not (asr.vocab[k].startswith("<") and asr.vocab[k].endswith(">"))),
                None,
            ),
            "raw": raw,
            "stripped": text,
        })

    out = {
        "wav": os.path.basename(args.wav),
        "wav_s": round(len(pcm) / W.TARGET_SR, 3),
        "model": os.path.basename(model_dir),
        "model_dir": os.path.relpath(model_dir, REPO).replace("\\", "/"),
        "worker_sha256": __import__("hashlib").sha256(
            io.open(os.path.join(WORKER, "sotto_worker.py"), "rb").read()
        ).hexdigest().upper(),
        "lang_id": asr.lang_id,
        "lang": asr.lang_tag,
        "use_vad": use_vad,
        "chunk": chunk,
        "load_s": round(load_s, 2),
        "chunks": rows,
    }
    with io.open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(f"wrote {args.out}: {len(rows)} chunks, load_s={load_s:.2f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
