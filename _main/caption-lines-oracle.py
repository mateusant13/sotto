"""ORACLE for the caption FORMULATION layer in `worker/sotto_worker.py`.

THE DEFECT THIS CLOSES
----------------------
`nemotron-3.5-asr-streaming-0.6b` is a streaming RNN-T: `run_chunk()` returns the
text decoded from ONE 560 ms chunk, and consecutive chunks are DELTAS, not a
re-reading of the utterance. Both emitters printed each chunk VERBATIM, so a
caption was a word and the panel showed a column of them. Owner, 2026-10-06,
verbatim: "tem palavras, inves de frases".

`LineFormer` accumulates decoded text into a LINE and closes it on a real
boundary. This oracle drives the REAL class — imported from the shipped module,
never a hand-copied transcription of it — and it carries a NEGATIVE CONTROL: the
pre-change behaviour ("print the chunk if it is long enough") is re-implemented
below as `_PassThrough`, and every arm the fix earns must go RED against it. A
green arm the control also passes proves nothing.

ARMS
----
 1  a >= SENTENCE_GAP_S silence closes the line BEFORE the new chunk
 2  a < SENTENCE_GAP_S gap does NOT split continuous speech
 3  terminal punctuation closes AFTER the chunk
 4  the char cap closes before the fragment that would overflow
 5  min_chars is the floor for what is worth a caption
 6  output.partial=true ships the GROWING line
 7  output.partial=false ships ONLY the closed line
 8  `start` is the START OF THE LINE, never the newest chunk's — the renderer
    detects a re-cover by `start < lastAudioEnd`; a chunk start would make the
    line duplicate itself word for word
 9  flush closes the held line once: a partial equal to the final is not re-sent
10  REAL DATA — replaying the fragments the worker MEASURED on
    `_main/pt-br-sample.wav` (the BEFORE run) through the former reproduces the
    AFTER run caption for caption

Exit codes: 0 PASS, 1 FAIL, 2 setup error. No window: pure file reads.
"""

from __future__ import annotations

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(REPO, "worker")
sys.path.insert(0, WORKER)
import sotto_worker as W  # noqa: E402

BEFORE = os.path.join(HERE, "_wav-before.jsonl")
AFTER = os.path.join(HERE, "_wav-after.jsonl")

RESULTS = []


def arm(name, real, control, want, control_must_differ=True):
    ok = real == want
    differs = real != control
    good = ok and (differs or not control_must_differ)
    RESULTS.append(good)
    tag = "PASS" if good else "FAIL"
    print(f"[{tag}] arm: {name}")
    print(f"       real    = {real!r}")
    print(f"       want    = {want!r}")
    if control_must_differ:
        print(f"       control = {control!r}  (must differ: {'yes' if differs else 'NO'})")


class _PassThrough:
    """The PRE-CHANGE emitter, verbatim in behaviour: every decoded chunk whose
    trimmed text clears the floor becomes its own caption, carrying the CHUNK's
    own audio window. This is the control; it must FAIL the arms the fix earns."""

    def __init__(self, min_chars=1, emit_partial=True, **_):
        self.min_chars = max(1, int(min_chars))

    def push(self, text, start=None, end=None):
        t = (text or "").strip()
        if len(t) < self.min_chars:
            return []
        return [{"type": "caption", "text": t, "start": start, "end": end}]

    def flush(self):
        return []


def captions(events):
    return [e["text"] for e in events]


def starts(events):
    return [e["start"] for e in events]


def texts(seq):
    """The text column of `(text, start, end)` tuples, as read from a JSONL run."""
    return [t for t, _s, _e in seq]


def drive(impl, chunks, **kw):
    f = impl(**kw)
    out = []
    for text, s, e in chunks:
        out += f.push(text, s, e)
    out += f.flush()
    return out


def load(path):
    out = []
    with io.open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") == "caption":
                out.append((rec.get("text", ""), rec.get("start"), rec.get("end")))
    return out


def main():
    if not os.path.exists(BEFORE) or not os.path.exists(AFTER):
        print(f"SETUP ERROR: need {BEFORE} and {AFTER} "
              f"(run the WAV arm first: SOTTO_AUDIO_FILE=_main/pt-br-sample.wav)")
        return 2

    # ── arm 1: an 8 s silence closes the line BEFORE the new chunk ──────────
    # The line is built from TWO chunks and then a >=8 s gap, so the control
    # (one caption per chunk) cannot produce the same answer for any reason
    # other than agreement.
    chunks = [("hello", 0.0, 0.5), ("there", 0.5, 1.0), ("again", 12.0, 13.0)]
    arm("a >= SENTENCE_GAP_S silence splits the line",
        captions(drive(W.LineFormer, chunks, emit_partial=False)),
        captions(drive(_PassThrough, chunks, emit_partial=False)),
        ["hello there", "again"])

    # ── arm 2: a sub-gap pause does NOT split continuous speech ─────────────
    chunks = [("this is", 0.0, 1.0), ("one sentence", 3.8, 4.4)]   # 2.8 s gap
    arm("a 2.80s gap keeps ONE line",
        captions(drive(W.LineFormer, chunks, emit_partial=False)),
        captions(drive(_PassThrough, chunks, emit_partial=False)),
        ["this is one sentence"])

    # ── arm 3: terminal punctuation closes the line ─────────────────────────
    chunks = [("the roads", 0.0, 0.5), ("are closed.", 0.5, 1.0), ("we go home", 1.5, 2.0)]
    arm("terminal punctuation closes the line",
        captions(drive(W.LineFormer, chunks, emit_partial=False)),
        captions(drive(_PassThrough, chunks, emit_partial=False)),
        ["the roads are closed.", "we go home"])

    # ── arm 4: the cap closes before the fragment that would overflow ───────
    # The discriminating fact is not "<= cap" (a single over-long fragment is
    # emitted as-is by both) but that the cap HANDS OUT FEWER lines than the
    # per-chunk control.
    big = [(f"word{i:02d}", i, i + 0.5) for i in range(14)]        # 14 x 6 chars
    real_caps = captions(drive(W.LineFormer, big, emit_partial=False, max_chars=20))
    ctrl_caps = captions(drive(_PassThrough, big, emit_partial=False, max_chars=20))
    arm("the char cap splits instead of overflowing",
        (max(len(t) for t in real_caps) <= 20, len(real_caps) < len(ctrl_caps)),
        (max(len(t) for t in ctrl_caps) <= 20, len(ctrl_caps) < len(ctrl_caps)),
        (True, True))

    # ── arm 5: min_chars is the floor for what is worth a caption ───────────
    # Applied to the LINE, not the fragment: two 2-char chunks join into a
    # 5-char line that clears a 4-char floor, where the per-chunk control drops
    # both fragments and emits nothing at all.
    chunks = [("ok", 0.0, 0.5), ("go", 0.5, 1.0)]
    arm("min_chars floors the LINE, not the fragment",
        captions(drive(W.LineFormer, chunks, min_chars=4, emit_partial=False)),
        captions(drive(_PassThrough, chunks, min_chars=4, emit_partial=False)),
        ["ok go"])

    # ── arm 6: partial=true ships the GROWING line ──────────────────────────
    chunks = [("going", 0.0, 0.5), ("along", 0.5, 1.0), ("the road", 1.0, 1.5)]
    arm("partial=true emits the growing line",
        captions(drive(W.LineFormer, chunks, emit_partial=True)),
        captions(drive(_PassThrough, chunks, emit_partial=True)),
        ["going", "going along", "going along the road"])

    # ── arm 7: partial=false ships ONLY the closed line ─────────────────────
    arm("partial=false emits only the closed line",
        captions(drive(W.LineFormer, chunks, emit_partial=False)),
        captions(drive(_PassThrough, chunks, emit_partial=False)),
        ["going along the road"])

    # ── arm 8: `start` is the LINE's start, never the newest chunk's ────────
    arm("start is the line's start, not the newest chunk's",
        starts(drive(W.LineFormer, chunks, emit_partial=True)),
        starts(drive(_PassThrough, chunks, emit_partial=True)),
        [0.0, 0.0, 0.0])

    # ── arm 9: flush closes once; a partial equal to the final is not resent ─
    held = [("held", 0.0, 0.5), ("back", 0.5, 1.0)]
    real9 = captions(drive(W.LineFormer, held, emit_partial=True))
    arm("flush does not re-send the text it already showed",
        (real9, real9.count("held back")),
        (captions(drive(_PassThrough, held, emit_partial=True)), 0),
        (["held", "held back"], 1))

    # ── arm 10: REAL DATA — the BEFORE fragments reproduce the AFTER run ────
    before, after = load(BEFORE), load(AFTER)
    real = captions(drive(W.LineFormer, before, emit_partial=True))
    arm("real WAV fragments reproduce the AFTER caption run",
        real,
        captions(drive(_PassThrough, before, emit_partial=True)),
        texts(after))

    # ── acceptance, stated as the owner reads it, on the REAL run ───────────
    words = [len(t.split()) for t in texts(after)]
    phrase = max(words) if words else 0
    ok = phrase >= 3
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] acceptance: the real run has a caption "
          f"with >= 3 words (longest = {phrase})")
    print(f"       AFTER  captions = {texts(after)!r}")
    print(f"       BEFORE captions = {texts(before)!r}")

    failed = RESULTS.count(False)
    print(f"caption-lines-oracle: {len(RESULTS) - failed} PASS / {failed} FAIL "
          f"({len(RESULTS)} arms)  impl={W.__file__}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
