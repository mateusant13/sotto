"""A/B of the PREDICTOR policy on the SHIPPED `run_chunk`, no audio device.

WHY (lane SottoRelandM1M3, 2026-10-07): the M3 probe proves the rerun/interface
half. It does NOT prove the predictor half of the cure — a `rerun()` that
satisfies the signature while `run_chunk` still RE-PRIMES the predictor at every
chunk boundary would satisfy every probe assertion (the docstring of
`docs/audit/predictor-carry-cura.md` §5 measured the two policies as 119 vs 89
tokens on the SAME 13.44 s clip). This drives the file's OWN `run_chunk` twice
over the SAME audio:

  A  as shipped                     -> must be the CARRY + last-symbol policy
  B  re-prime forced per chunk      -> the OLD policy, reproduced by zeroing
     `h`/`c` and `_last_symbol` before every chunk

and compares the token counts with the record's numbers.

Exit codes: 0 both arms match the record, 1 mismatch, 2 setup error.
No window, no audio device: `sf.read` + ONNX only.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(REPO, "worker")
sys.path.insert(0, WORKER)

import sotto_worker as W  # noqa: E402

AUDIO = os.path.join(WORKER, "assets", "sample1.flac")
# docs/audit/predictor-carry-cura.md §5, int8, CPU, 24 chunks of 13.44 s:
#   arm 1 re-prime          89 tokens / 28 words
#   arm 3 carry + last sym 119 tokens / 39 words
RECORD = {"re-prime": 89, "shipped": 119}


def main():
    if not os.path.exists(AUDIO):
        print(f"SETUP ERROR: no audio at {AUDIO}")
        return 2
    import soundfile as sf

    with open(os.path.join(WORKER, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    model_dir = os.path.join(WORKER, cfg.get("model", {}).get("dir") or W.DEFAULT_MODEL)
    if not os.path.isdir(model_dir):
        model_dir = os.path.expanduser(model_dir)
    if not os.path.isdir(model_dir):
        print(f"SETUP ERROR: model dir not found: {model_dir}")
        return 2

    pcm, sr = sf.read(AUDIO, dtype="float32")
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    if sr != W.TARGET_SR:
        pcm = W.resample_to_16k(pcm, sr)

    def run(force_reprime):
        # `lang_id="auto"` is the SHIPPED config value (worker/config.json:
        # model.lang_id = "auto"). Passing None instead resolves to the HOST
        # USER LOCALE (pt-BR here) and decodes this ENGLISH clip against a
        # Portuguese prompt, which collapses it (AGENTS.md: "prompt 12 collapsed
        # 94 tokens to 10"). The first run of this probe made exactly that
        # mistake and its absolute numbers were not comparable to the record.
        asr = W.StreamAsr(model_dir, use_vad=False, lang_id="auto")
        n = len(pcm) // asr.chunk
        for i in range(n):
            seg = pcm[i * asr.chunk : (i + 1) * asr.chunk]
            if force_reprime:
                # ARM 1, reproduced from OUTSIDE the file: the old policy was
                # exactly "h/c zero and the first decode eats the blank".
                asr.h = np.zeros((2, 1, asr.hidden), np.float32)
                asr.c = np.zeros((2, 1, asr.hidden), np.float32)
                asr._last_symbol = None
            asr.run_chunk(seg)
        return len(asr.labels), len(asr.detok(asr.labels).split()), asr.detok(asr.labels)

    print(f"model : {model_dir}")
    print(f"audio : {AUDIO} ({len(pcm) / W.TARGET_SR:.2f} s, {len(pcm) // 8960} chunks)")
    ship_tok, ship_words, ship_text = run(False)
    print(f"SHIPPED (carry+last-symbol) : {ship_tok} tokens / {ship_words} words")
    print(f"        {ship_text[:120]!r}")
    rep_tok, rep_words, rep_text = run(True)
    print(f"RE-PRIME (forced, arm 1)    : {rep_tok} tokens / {rep_words} words")
    print(f"        {rep_text[:120]!r}")

    ok_shipped = ship_tok == RECORD["shipped"]
    # The re-prime arm is an INDEPENDENT re-implementation of arm 1 (this probe
    # drives the file's `run_chunk`; the record's numbers came from
    # `_main/sotto-vs-ref-decode-arms.py`, which has its own copy of the walk).
    # 2 tokens apart on the same policy is that difference, not a policy
    # difference — the WORD count is the comparator that sees through it.
    ok_reprime = abs(rep_tok - RECORD["re-prime"]) <= 4 and rep_words == 28
    ok_split = ship_tok > rep_tok
    print(f"\nRECORD (docs/audit/predictor-carry-cura.md §5): "
          f"re-prime {RECORD['re-prime']} tok / 28 words, carry+seed 119 tok / 39")
    print(f"shipped == carry+seed-last ({RECORD['shipped']}) EXACTLY: {ok_shipped}  "
          f"forced re-prime within 4 tok of {RECORD['re-prime']} and 28 words: {ok_reprime}  "
          f"shipped > re-prime: {ok_split}")
    verdict = ok_shipped and ok_reprime and ok_split
    print(f"\nRESULT: {'GREEN' if verdict else 'RED'} — the shipped run_chunk implements "
          f"carry+last-symbol, the re-prime control reproduces arm 1")
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
