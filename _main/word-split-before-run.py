"""The NEGATIVE-CONTROL run: the file-mode caption path with ONE line reverted.

WHY THIS EXISTS (lane SottoWordSplit)
-------------------------------------
The cure for "shi t" is `join_fragments()` in `worker/sotto_worker.py`: the
single place that decides the separator between two decoded chunks. This driver
runs the REAL file-mode path (`sotto_worker.selftest`, the same function
`--selftest` calls) with that ONE function replaced by its pre-fix body
(`" ".join(...)`), so the BEFORE text is produced by the same code, the same
model and the same audio as the AFTER text — not by a hand-copied re-implementation.

It opens NO audio device: the WAV is read with `soundfile`.

`emit()` writes JSONL to stdout and this runs under `pythonw.exe` (no console),
so stdout is redirected to `--out` inside the process.

Usage:
  pythonw.exe _main/word-split-before-run.py --wav _main/pt-br-sample.wav \
      --out _main/_wordsplit-before.jsonl
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(REPO, "worker")
sys.path.insert(0, WORKER)


def pre_fix_join(frags) -> str:
    """The shipped join, verbatim: every chunk seam became a word boundary."""
    return " ".join(t for t, _c in frags if t).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", default=os.path.join(HERE, "pt-br-sample.wav"))
    ap.add_argument("--out", default=os.path.join(HERE, "_wordsplit-before.jsonl"))
    ap.add_argument("--config", default=os.path.join(WORKER, "config.json"))
    ap.add_argument("--threads", type=int, default=2)
    args = ap.parse_args()

    import sotto_worker as W  # noqa: E402

    W.limit_threads(args.threads)
    cfg = json.load(io.open(args.config, encoding="utf-8"))
    model_dir = cfg["model"]["dir"]
    if not os.path.isabs(model_dir):
        model_dir = os.path.join(WORKER, model_dir)

    # ── THE REVERT: exactly one function ────────────────────────────────────
    W.join_fragments = pre_fix_join

    asr = W.StreamAsr(model_dir, providers=None,
                      use_vad=bool(cfg["model"].get("use_vad", True)),
                      lang_id=cfg["model"].get("lang_id", "auto"))

    fh = io.open(args.out, "w", encoding="utf-8")
    real_stdout = sys.stdout
    sys.stdout = fh
    try:
        rc = W.selftest(asr, args.wav, None,
                        int((cfg.get("output") or {}).get("min_chars", 1)),
                        bool((cfg.get("output") or {}).get("partial", True)),
                        int((cfg.get("output") or {}).get("done_text_max_chars", 20000)))
    finally:
        sys.stdout = real_stdout
        fh.close()
    print(f"wrote {args.out} rc={rc} (join_fragments REVERTED)", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
