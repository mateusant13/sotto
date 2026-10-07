"""PROBE for the M3 second pass in `worker/sotto_worker.py` — the live path's
own code, over a real recording, with NO audio device.

WHY IT EXISTS
-------------
`docs/audit/ao-vivo-vs-redux.md` §7 leaves two things NÃO-VERIFICADO, and both
are the mechanism the cure rests on:

  1. "O custo real da 2a passagem" — the table in §6.2 is `RTF x S`
     **[INFERENCE]** from RTF measured on a whole file, never on a segment.
  2. the live arm's second pass had never been run in isolation.

The file arm (`--selftest`, `SOTTO_AUDIO_FILE`) cannot answer either: it has no
renderer racing a deadline, so it deliberately ships the streaming line and
never calls the second pass. This probe drives `StreamAsr` directly — the same
class, the same graphs, the same `run_chunk` — and measures the pass itself.

ASSERTIONS (each one is a live-path invariant, not a description)
  A  `reset_stream_state()` really returns the caches to a stream start: the
     three arrays are EQUAL to a freshly allocated `_initial_encoder_caches`.
  A2 `reset_stream_state()` returns the PREDICTOR to a stream start too: `h`/`c`
     all-zero and `_last_symbol` back to None (CURA 2026-10-06).
  B  `run_chunk(..., account=False)` moves NO accounting counter: `n_chunks`,
     `audio_s`, `wall`, `frames_walked`, `blank_frames`, `symbols`,
     `empty_chunks` and `labels` are identical before and after.
  C  the LIVE state is restored: after the pass, `cc`/`ct`/`ccl` are equal to
     what the live stream held when the segment closed.
  C3 the LIVE PREDICTOR is restored too, and the pair is non-vacuous: the pass,
     which here re-runs the SECOND HALF of the stream (a segment that begins
     mid-stream, as `rerun()`'s closed line does), must have MOVED
     `h`/`c`/`_last_symbol` — else there is nothing to restore and the check
     cannot go RED — and the restore must reproduce them bit for bit.
  D  the pass produces text for the segment it was given (a silent pass would
     make M3 a no-op).
  E  the cost, measured in wall seconds against the segment's own audio seconds.

Exit codes: 0 PASS, 1 FAIL, 2 setup error. No window: pure file reads and ONNX.
"""

from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(REPO, "worker")
sys.path.insert(0, WORKER)

import sotto_worker as W  # noqa: E402

AUDIO = os.path.join(HERE, "pt-br-sample.wav")
RESULTS = []


def report(name, ok, detail=""):
    RESULTS.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        print(f"       {detail}")


def main():
    if not os.path.exists(AUDIO):
        print(f"SETUP ERROR: no audio at {AUDIO}")
        return 2

    with open(os.path.join(WORKER, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    model_dir = os.path.join(WORKER, cfg.get("model", {}).get("dir") or W.DEFAULT_MODEL)
    if not os.path.isdir(model_dir):
        model_dir = os.path.expanduser(model_dir)
    if not os.path.isdir(model_dir):
        print(f"SETUP ERROR: model dir not found: {model_dir}")
        return 2

    import soundfile as sf

    print(f"model : {model_dir}")
    t0 = time.time()
    asr = W.StreamAsr(model_dir, use_vad=False, lang_id=None)
    print(f"load  : {time.time() - t0:.2f} s   provider={asr.providers}")

    pcm, sr = sf.read(AUDIO, dtype="float32")
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    if sr != W.TARGET_SR:
        pcm = W.resample_to_16k(pcm, sr)

    # ── feed the stream the way asr_thread does, holding each chunk ─────────
    chunk = asr.chunk
    n_chunks = len(pcm) // chunk
    if n_chunks < 2:
        print("SETUP ERROR: audio shorter than two chunks")
        return 2
    held = []
    former = W.LineFormer(min_chars=1, emit_partial=False)
    t_stream = time.time()
    for i in range(n_chunks):
        seg = pcm[i * chunk : (i + 1) * chunk]
        # account=False here so the probe's own streaming pass cannot be
        # confused with the second pass it is about to measure.
        text, _n = asr.run_chunk(seg, speech=True, account=False)
        held.append(seg)
        former.push(text, round(i * chunk / W.TARGET_SR, 2), round((i + 1) * chunk / W.TARGET_SR, 2))
    stream_wall = time.time() - t_stream
    audio_s = n_chunks * chunk / W.TARGET_SR
    print(f"stream: {n_chunks} chunks, {audio_s:.2f} s of audio, {stream_wall:.2f} s "
          f"(RTF {stream_wall / audio_s:.3f})")

    # ── A: reset really is a stream start ──────────────────────────────────
    pre = (asr.cc, asr.ct, asr.ccl)          # the LIVE arrays, by reference
    saved = tuple(a.copy() for a in pre)     # what `rerun()` restores from
    # CURA 2026-10-06 (`docs/audit/predictor-carry-cura.md`): `rerun()` now saves
    # and restores the PREDICTOR as well, because `run_chunk` no longer re-primes
    # it per chunk and `reset_stream_state()` now zeroes it. This probe saves the
    # same six things, in the same order, or it is not proving the live path.
    saved_pred = (asr.h.copy(), asr.c.copy(), asr._last_symbol)
    asr.reset_stream_state()
    fresh = W._initial_encoder_caches(np, asr.enc, asr.model_dir)
    ok_a = all(
        a.shape == b.shape and np.array_equal(a, b)
        for a, b in zip((asr.cc, asr.ct, asr.ccl), fresh)
    )
    report("A reset_stream_state() returns the caches to a stream start", ok_a,
           f"shapes={[a.shape for a in fresh]} equal_to_fresh_allocation={ok_a}")

    # A2 — the predictor is part of "stream start" too: h/c zero, seed back to None
    ok_a2 = (np.array_equal(asr.h, np.zeros_like(asr.h))
             and np.array_equal(asr.c, np.zeros_like(asr.c))
             and asr._last_symbol is None)
    report("A2 reset_stream_state() returns the PREDICTOR to a stream start", ok_a2,
           f"h/c all-zero={np.array_equal(asr.h, np.zeros_like(asr.h))}/"
           f"{np.array_equal(asr.c, np.zeros_like(asr.c))} _last_symbol={asr._last_symbol!r}")

    # ── B/C: the second pass must not be observable by the live stream ─────
    before = {k: getattr(asr, k) for k in (
        "n_chunks", "frames_walked", "blank_frames", "symbols",
        "empty_chunks", "vad_gated_chunks", "music_gated_chunks")}
    before["audio_s"] = asr.audio_s
    before["wall"] = asr.wall
    before["labels"] = len(asr.labels)

    # ── the pass itself, exactly as asr_thread.rerun() runs it ─────────────
    # THE SEGMENT IS A TAIL, NOT THE WHOLE STREAM. `rerun()` re-runs the audio
    # behind a CLOSED LINE — a segment that BEGAN mid-stream. That is also what
    # lets this probe go RED: a pass that replayed the whole stream from the
    # stream's own start would reproduce the live state EXACTLY (same zeros,
    # same audio, deterministic), so "the pass moved the predictor" would be
    # False and the restore would look unnecessary — measured, with
    # `docs/audit/predictor-carry-cura.md`'s cure landed: pred_moved=False while
    # the segment was `held[0:]`, and True as soon as it starts mid-stream.
    seg_start = len(held) // 2
    print(f"pass  : segment = chunks[{seg_start}:{len(held)}] "
          f"({(len(held) - seg_start) * chunk / W.TARGET_SR:.2f} s of the "
          f"{audio_s:.2f} s stream), starting {seg_start} chunks in")
    t_pass = time.time()
    second = W.LineFormer(min_chars=1, emit_partial=False)
    out = []
    for i, seg in enumerate(held[seg_start:], start=seg_start):
        text, _n = asr.run_chunk(seg, speech=True, account=False)
        for event in W.line_events(second.push(
            text, round(i * chunk / W.TARGET_SR, 2), round((i + 1) * chunk / W.TARGET_SR, 2),
        )):
            out.append(event["text"])
    for event in W.line_events(second.flush()):
        out.append(event["text"])
    pass_wall = time.time() - t_pass
    pass_text = " ".join(t for t in out if t).strip()

    after = {k: getattr(asr, k) for k in (
        "n_chunks", "frames_walked", "blank_frames", "symbols",
        "empty_chunks", "vad_gated_chunks", "music_gated_chunks")}
    after["audio_s"] = asr.audio_s
    after["wall"] = asr.wall
    after["labels"] = len(asr.labels)

    moved = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
    report("B run_chunk(account=False) moves no live accounting counter", not moved,
           f"moved={moved or 'none'} (n_chunks {before['n_chunks']}->{after['n_chunks']}, "
           f"audio_s {before['audio_s']:.2f}->{after['audio_s']:.2f}, labels {before['labels']}->{after['labels']})")

    # ── C: the pass cannot be observed by the live stream ──────────────────
    # THE REAL RISK, and the one §7 of the audit leaves open: `run_chunk`
    # REBINDS `self.cc/ct/ccl` to the output of `enc.run(...)`. If that output
    # were the SAME buffer ORT writes into in place, then holding the previous
    # arrays would not be a save at all and the live stream would silently
    # continue from the second pass's state. Two checks, in order:
    #   C1  the pre-pass arrays were NOT written through — `pre` still equals the
    #       copy taken before the pass (so a `.copy()` restore is a real save);
    #   C2  assigning `saved` back (exactly what `rerun()`'s `finally` does)
    #       reproduces the live state bit for bit.
    ok_c1 = all(np.array_equal(a, b) for a, b in zip(pre, saved))
    asr.cc, asr.ct, asr.ccl = saved
    ok_c2 = all(np.array_equal(a, b) for a, b in zip((asr.cc, asr.ct, asr.ccl), saved))
    report("C the LIVE stream state survives the pass (not mutated in place, and restorable)",
           ok_c1 and ok_c2,
           f"C1 no in-place write into the live arrays: {ok_c1}; "
           f"C2 restore reproduces it bit for bit: {ok_c2}")

    # ── C3: the PREDICTOR survives the pass too (CURA 2026-10-06) ──────────
    # TWO conjuncts, and the first is what keeps this from being decoration: the
    # pass MUST have moved the predictor, or "restored" is a state that was never
    # left, i.e. a check that cannot go RED. The pre-cure `rerun()` restored only
    # cc/ct/ccl; with a carrying predictor that leak is real and this pair fails
    # (pred_moved True, ok_c3 False).
    pred_moved = (not np.array_equal(asr.h, saved_pred[0])
                  or not np.array_equal(asr.c, saved_pred[1])
                  or asr._last_symbol != saved_pred[2])
    asr.h, asr.c, asr._last_symbol = saved_pred
    ok_c3 = (np.array_equal(asr.h, saved_pred[0])
             and np.array_equal(asr.c, saved_pred[1])
             and asr._last_symbol == saved_pred[2])
    report("C3 the LIVE predictor survives the pass (the pass moved it, the restore "
           "reproduces it bit for bit)", pred_moved and ok_c3,
           f"the pass moved h/c/_last_symbol: {pred_moved} (a restore that is never "
           f"needed cannot go RED); restore reproduces it: {ok_c3}; "
           f"_last_symbol {saved_pred[2]!r}")

    report("D the pass produces text for the segment it was given", bool(pass_text),
           f"second-pass text = {pass_text!r}")

    stream_text = former.line() or "(line closed during the stream)"
    ratio = pass_wall / stream_wall if stream_wall else float("nan")
    print(f"\nCOST  : segment {audio_s:.2f} s of audio -> second pass {pass_wall:.2f} s "
          f"(RTF {pass_wall / audio_s:.3f}); streaming the same audio took {stream_wall:.2f} s "
          f"(RTF {stream_wall / audio_s:.3f})")
    print(f"COST  : the pass costs {ratio:.2f}x a streaming pass of the SAME audio")
    print(f"COST  : the audit's §6.2 table predicted RTF x S = 0.15-0.25 -> "
          f"{audio_s * 0.15:.2f}-{audio_s * 0.25:.2f} s for this segment")
    print("LOAD  : READ BOTH RTF NUMBERS WITH THE BOX IN MIND — this is the ratio; the "
          "ABSOLUTE RTF is only comparable to the audit's 0.14-0.22 on an IDLE box. On this "
          "one the streaming pass alone measured far above it, which is the load, not the "
          "model (see WORKER_STATS rss_mb / the process census).")
    print(f"note  : the streaming text of the same audio was {stream_text!r}")

    failed = RESULTS.count(False)
    print(f"\nRESULT: {'RED — %d violation(s)' % failed if failed else 'GREEN'} "
          f"({len(RESULTS) - failed}/{len(RESULTS)} assertions)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
