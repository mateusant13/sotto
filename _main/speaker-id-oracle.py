#!/usr/bin/env python
"""ORACLE: WHO IS SPEAKING -- THE DECISION, PINNED, WITH THE BUG THAT WAS IN IT.

OWNER, 2026-10-18, verbatim:
    "e mostra pra mim a legenda ao vivo ou o parakeet processando os audios do
     discord meu e dos meus amigos. de forma natural, encaixa no sotto"

WHAT IS BEING GATED. `worker/speaker_id.py` turns diarizer segments into a
`speaker` per caption line. It is the piece the 2026-10-13 receipt
(`_main/receipt-20261013-no-speaker-attribution.md`) measured as MISSING --
"not a DESIGN gap that CSS can close -- it is an ENGINE gap". The module is pure
on purpose: no model, no audio device, no Win32, so a decision that decides
WHICH PERSON a sentence belongs to can be tested in milliseconds instead of
with a 639 MB checkpoint in the loop.

THE BUG THIS ORACLE WAS BUILT AROUND. Not a hypothetical. The first version of
`speaker_for_window` ranked each segment as it arrived, comparing against a
RUNNING per-speaker total, so a speaker's score depended on which of that
speaker's OWN segments had already been seen at the instant of the comparison.
Fuzzing 4 000 random segment sets against EVERY permutation of each:

    9 sets   whose winner flipped with the iteration order
    (window 0.71-2.68, c1 holding 2.44 s across two segments vs c2 holding 1.97 s
     and 1.78 s, beats whoever was visited first)

In a call that is a NAME FLICKERING on a finished sentence, and the docstring's
own promise -- "a caption that changes owner between two reads of the same line
is a visible flicker" -- was false. The fix accumulates first and ranks after.
A SECOND order dependence survived that and this fuzz found it too: two people
starting together is the NORMAL case in a call, and when they tie on all three
criteria the winner came out of dict iteration order:

    1 set    (c1 and c3 identical on total, longest and start; c1 vs c3 decided
              by which was inserted first)

Both cases are pinned here BY NAME, not left to random rediscovery.

THE ARMS:

    overlap        symmetric, half-open, never negative
    the majority   an overlapping line goes to whoever holds more of it
    the floor      0,30 s is SECONDS of voice and counts the TOTAL, so a voice
                   broken across two segments is still that voice
    honesty        a line no speaker owns enough of is `None`, never a guess
    stability      `speaker-N` follows FIRST APPEARANCE, not the cluster id, and
                   is the same whatever order the segments arrive in
    permutation    the two historical flippers, every permutation, one answer
    purity         the module imports no model, no audio stack, no Win32
    non-mutation   `attribute_lines` returns new dicts; the caller's are untouched
    a call         4 speakers / 10 lines shape a sensible attribution

THE NEGATIVE ARM re-runs the identical battery against 7 deliberately broken
copies. An oracle that cannot say NO is decoration.
"""
from __future__ import annotations

import ast
import importlib.util
import itertools
import os
import random
import shutil
import sys
import tempfile

REPO = r"H:\sotto"
MODULE_PATH = os.path.join(REPO, "worker", "speaker_id.py")

EXIT_PASS, EXIT_FAIL = 0, 1

# The two sets that used to flip, kept verbatim so the regression is a NAME and
# not a coin toss on some future seed.
FLIP_RUNNING_TOTAL = (
    (0.71, 2.68),
    [
        (0.63, 3.27, "c2"),
        (0.30, 3.70, "c1"),
        (1.86, 0.91, "c1"),   # inverted on purpose: must be ignored, not crash
        (0.90, 3.28, "c2"),
    ],
)
FLIP_EXACT_TIE = (
    (0.78, 1.71),
    [
        (0.80, 2.37, "c3"),
        (0.80, 3.24, "c1"),   # identical to c3 on total, longest AND start
        (1.49, 2.84, "c2"),
    ],
)


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def battery(mod, trials: int = 1500) -> list:
    """Run every arm against `mod`. Returns [(ok, name, detail)]."""
    out = []
    Segment = mod.Segment

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))
        return bool(ok)

    # --- overlap -----------------------------------------------------------
    ov = mod.overlap
    chk(ov(0, 2, 1, 3) == 1, "overlap symmetric")
    chk(ov(1, 3, 0, 2) == 1, "overlap symmetric (reversed)")
    chk(ov(0, 1, 1, 2) == 0, "overlap half-open (touching edges do not count)")
    chk(ov(5, 6, 0, 1) == 0, "overlap disjoint is zero")
    chk(ov(0, 1, 5, 6) == 0, "overlap disjoint is zero (reversed)")
    chk(ov(0, 2, 3, 4) == 0, "overlap never negative")

    # --- degenerate inputs must not raise ----------------------------------
    chk(mod.speaker_for_window((), []) is None, "empty window -> None")
    chk(mod.speaker_for_window((1.0, 1.0), []) is None, "zero-length window -> None")
    chk(mod.speaker_for_window((2.0, 1.0), []) is None, "inverted window -> None")
    chk(mod.speaker_for_window((0, 1), []) is None, "no segments -> None")
    try:
        mod.speaker_for_window((0, 1), [Segment(0.5, "nope", "c1")])
        chk(True, "garbage segment survives")
    except Exception as exc:                                   # noqa: BLE001
        chk(False, "garbage segment survives", repr(exc))
    try:
        mod.attribute_lines([{"start": 0, "end": None}], [])
        chk(True, "garbage line survives")
    except Exception as exc:                                   # noqa: BLE001
        chk(False, "garbage line survives", repr(exc))

    # --- the majority owns the line ---------------------------------------
    two = [Segment(0.0, 1.2, "c1"), Segment(0.8, 4.0, "c2")]
    chk(mod.speaker_for_window((0.0, 4.0), two) == "c2", "majority wins the overlap")
    two_rev = [Segment(0.0, 1.2, "c2"), Segment(0.8, 4.0, "c1")]
    chk(mod.speaker_for_window((0.0, 4.0), two_rev) == "c1", "majority wins (labels swapped)")

    # --- the floor is SECONDS, and it counts the TOTAL ----------------------
    # One voice split either side of a pause still totals 0.6 s and is a person.
    split = [Segment(0.0, 0.3, "c1"), Segment(0.4, 0.7, "c1")]
    chk(mod.speaker_for_window((0.0, 0.7), split, 0.30) == "c1",
        "floor counts the total across segments")
    # The case that separates "total" from "longest single stretch": 0,45 s of
    # one voice in three pieces clears a 0,30 s floor as a TOTAL and fails it as
    # a longest-segment. A person interrupted three times is still a person.
    thirds = [Segment(0.0, 0.15, "c1"), Segment(0.20, 0.35, "c1"),
              Segment(0.40, 0.55, "c1")]
    chk(mod.speaker_for_window((0.0, 0.55), thirds, 0.30) == "c1",
        "0,45 s of one voice broken three ways still counts")
    below = [Segment(0.0, 0.1, "c1"), Segment(0.2, 0.3, "c1")]
    chk(mod.speaker_for_window((0.0, 0.3), below, 0.30) is None,
        "0,2 s total under a 0,30 s floor stays honest")
    chk(mod.speaker_for_window((0.0, 60.0), [Segment(0.0, 0.1, "c1")], 0.30) is None,
        "a 0,1 s sliver of a 60 s line is not a speaker")

    # --- silence is not a speaker ------------------------------------------
    quiet = [Segment(10.0, 12.0, "c1")]
    chk(mod.speaker_for_window((0.0, 1.0), quiet) is None, "silence -> None")

    # --- stability: labels by FIRST APPEARANCE ----------------------------
    # The ids are chosen so that sorting by id DISAGREES with listening: "9"
    # opens the call and "3" only shows up later. A label that numbered by id
    # would call the man who said nothing until second "speaker-1".
    numbered = [Segment(0.0, 1.0, "9"), Segment(2.0, 3.0, "3"),
                Segment(4.0, 5.0, "9")]
    labels = mod.stable_labels(numbered)
    chk(labels.get("9") == "speaker-1", "first appearance is speaker-1",
        repr(labels))
    chk(labels.get("3") == "speaker-2", "second appearance is speaker-2",
        repr(labels))
    shuffled = [Segment(4.0, 5.0, "9"), Segment(0.0, 1.0, "9"), Segment(2.0, 3.0, "3")]
    chk(mod.stable_labels(shuffled) == labels,
        "labels do not depend on arrival order")

    lab = mod.label_segments(numbered)
    chk([s.speaker for s in lab] == [labels["9"], labels["3"], labels["9"]],
        "label_segments maps through the stable labels")

    # --- the two historical flippers ---------------------------------------
    for title, (win, raw) in (("running-total", FLIP_RUNNING_TOTAL),
                              ("exact-tie", FLIP_EXACT_TIE)):
        segs = [Segment(a, b, s) for a, b, s in raw]
        answers = {mod.speaker_for_window(win, list(p))
                   for p in itertools.permutations(segs)}
        chk(len(answers) == 1, "permutation-invariant: " + title,
            "answers=%r" % (sorted(answers),))

    # --- permutation invariance, at scale ----------------------------------
    rng = random.Random(20261018)
    flips = 0
    for _ in range(trials):
        n = rng.randint(1, 6)
        segs = [Segment(round(rng.uniform(0, 5), 2), round(rng.uniform(0, 5), 2),
                        rng.choice(["c1", "c2", "c3"])) for _ in range(n)]
        win = (round(rng.uniform(0, 5), 2), round(rng.uniform(0, 5), 2))
        base = mod.speaker_for_window(win, segs)
        for perm in itertools.permutations(segs):
            if mod.speaker_for_window(win, list(perm)) != base:
                flips += 1
                break
    chk(flips == 0, "permutation-invariant over %d random sets" % trials,
        "flipping=%d" % flips)

    # --- a line that no one owns is honest, and the caller's dict is safe ---
    lines = [{"start": 0.0, "end": 1.0, "text": "oi"},
             {"start": 0.0, "end": 0.05, "text": "ruido"}]
    before = [dict(line) for line in lines]
    got = mod.attribute_lines(lines, [Segment(0.0, 1.0, "c9")])
    chk(got[0].get("speaker") == "speaker-1", "attribute_lines labels the owner",
        repr(got[0].get("speaker")))
    chk(got[1].get("speaker") is None, "attribute_lines refuses to guess",
        repr(got[1].get("speaker")))
    chk(lines == before, "attribute_lines does not mutate the caller's lines")

    # --- a four-person call, shape only ------------------------------------
    call_segs = [Segment(0.0, 3.0, 0), Segment(2.5, 6.0, 1),
                 Segment(6.0, 9.0, 2), Segment(8.0, 12.0, 3),
                 Segment(12.0, 14.0, 0)]
    call_lines = [{"start": t, "end": t + 1.8} for t in (0.0, 3.0, 6.5, 9.0, 12.5)]
    call_got = mod.attribute_lines(call_lines, call_segs)
    got_names = [line.get("speaker") for line in call_got]
    call_labels = mod.stable_labels(call_segs)
    expected = [call_labels[0], call_labels[1], call_labels[2], call_labels[3],
                call_labels[0]]
    chk(got_names == expected, "a 4-person call attributes each line to its owner",
        "got=%r" % (got_names,))
    chk(len(set(call_labels.values())) == 4, "four voices get four names")

    return out


# (label, old, new) -- each MUST turn at least one arm RED.
MUTANTS = [
    ("no-exact-tie-break",
     "or (key == best_key and str(speaker) < str(best))",
     "or False"),
    ("running-total-again",
     "key = (round(math.fsum(chunks), 9),",
     "key = (round(chunks[-1], 9),"),
    ("floor-on-longest-not-total",
     "if best is None or best_key[0] < min_overlap:",
     "if best is None or best_key[1] < min_overlap:"),
    ("labels-by-cluster-id",
     "ordered = sorted(segments, key=lambda s: (float(s.start), str(s.speaker)))",
     "ordered = sorted(segments, key=lambda s: str(s.speaker))"),
    ("guess-when-unsure",
     "                          if win is not None else None)",
     "                          if win is not None else None) or 'speaker-?'"),
    ("mutates-the-caller",
     "        new = dict(line)",
     "        new = line"),
    ("overlap-may-go-negative",
     "    return max(0.0, min(a1, b1) - max(a0, b0))",
     "    return min(a1, b1) - max(a0, b0)"),
    ("one-source-for-the-whole-call",
     "        new[\"source\"] = speaker_source(base_source, label) or base_source",
     "        new[\"source\"] = base_source"),
    # The epoch mutants. The first is the bug this file exists to prevent: it
    # raises nothing, logs nothing, and gets every line wrong.
    ("the-epoch-offset-is-ignored",
     "            win = (float(line.get(\"start\")) + offset,\n"
     "                   float(line.get(\"end\")) + offset)",
     "            win = (float(line.get(\"start\")),\n"
     "                   float(line.get(\"end\")))"),
    # ...and the second is the tempting wrong fix: move the offset into the
    # line itself. That "works" for attribution and silently corrupts the times
    # the panel, the history and the transcript are keyed on.
    ("the-offset-rewrites-the-line",
     "        new[\"speaker\"] = label\n"
     "        new[\"source\"] = speaker_source(base_source, label) or base_source",
     "        new[\"speaker\"] = label\n"
     "        if offset:\n"
     "            new[\"start\"] = float(line.get(\"start\")) + offset\n"
     "            new[\"end\"] = float(line.get(\"end\")) + offset\n"
     "        new[\"source\"] = speaker_source(base_source, label) or base_source"),
]

FORBIDDEN_IMPORTS = ("onnxruntime", "torch", "soundfile", "numpy", "pyaudio",
                     "win32", "webview", "sherpa_onnx", "pyannote")


FIXTURE = os.path.join(REPO, "_main", "_hoje-ctrl.json")


def real_data_arms(mod) -> list:
    """The same battery, against the REAL diarizer output saved on 2026-10-18.

    `_main/_hoje-ctrl.json` is the payload `_diar-run.py` produced against the
    vendor's own four-speaker ground truth: **DER 0,03 %, 10 segments, 4
    speakers, RTF 0,416, 276 MB RSS**. Using it means the adapter is tested
    against the shape the model ACTUALLY emits, and it costs nothing to run --
    no checkpoint, no inference, no CPU. The owner's PC is not a test bench.
    """
    out = []

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))
        return bool(ok)

    if not os.path.isfile(FIXTURE):
        chk(False, "real diarizer fixture present", FIXTURE)
        return out
    import json
    with open(FIXTURE, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    segs = mod.segments_from_payload(payload)
    chk(len(segs) == 10, "fixture: 10 segments", "got %d" % len(segs))

    summary = mod.summarize(payload)
    chk(summary["n_speakers"] == 4, "fixture: 4 voices", repr(summary["n_speakers"]))
    chk(summary["n_segments"] == 10, "summarize agrees with the parse")
    chk(sorted(summary["labels"]) == [0, 1, 2, 3],
        "labels cover every cluster the model emitted", repr(summary["labels"]))

    labelled = mod.label_segments(segs)
    first = labelled[0]
    got_voice = mod.speaker_for_window((first.start + 0.4, first.start + 1.2),
                                       labelled)
    chk(got_voice == first.speaker, "a line inside a real segment gets that voice",
        "got=%r want=%r" % (got_voice, first.speaker))
    chk(isinstance(got_voice, str) and got_voice.startswith("speaker-"),
        "the answer is a LABEL, not a raw cluster id", repr(got_voice))

    # THE WIRING. This is the property the panel needs and the reason no panel
    # change is required: one distinct `source` per voice, all under the base.
    base = "device:CABLE Output (VB-Audio Virtual Cable)"
    lines = [{"start": s.start + 0.2, "end": s.start + 1.6} for s in segs]
    got = mod.attribute_from_payload(payload, lines, base_source=base)
    sources = [ln.get("source") for ln in got]
    chk(len(set(sources)) >= 4, "one distinct source per voice",
        "%d distinct of %d" % (len(set(sources)), len(sources)))
    chk(all(s and s.startswith(base) for s in sources),
        "every attributed line keeps its device in the source")
    chk(all("voice:speaker-" in s for s in sources),
        "each attributed source names the voice", repr(sources[:2]))
    named = [ln for ln in got if ln.get("speaker")]
    chk(len(named) >= 8, "most real lines land on a voice",
        "%d of %d" % (len(named), len(got)))

    # Silence is outside every segment here (0 -> first.start is ~0,32 s).
    quiet = mod.attribute_from_payload(
        payload, [{"start": 0.0, "end": 0.2, "text": ""}], base_source=base)
    chk(quiet[0].get("speaker") is None, "a silent line names nobody")
    chk(quiet[0].get("source") == base,
        "a silent line stays the DEVICE's line, not nobody's",
        repr(quiet[0].get("source")))

    # Off means pass-through, but the field is always present.
    off = mod.attribute_from_payload(None, [{"start": 0.0, "end": 3.0}], base_source=base)
    chk(off[0].get("speaker") is None, "diarization off -> speaker None")
    chk(off[0].get("source") == base, "diarization off -> source untouched")
    chk("speaker" in off[0], "the field exists even when attribution is off")

    # One model run must not be able to take the app down.
    junk = mod.segments_from_rows([
        {"start": 0.0, "end": 1.0, "speaker": 0},
        {"start": 2.0, "end": 1.0, "speaker": 1},   # inverted
        {"start": 3.0, "end": 4.0},                  # no speaker
        {"start": "x", "end": 4.0, "speaker": 2},     # not a number
        {"nope": 1},                                 # not a row at all
        mod.Segment(5.0, 6.0, 3),                    # already a Segment
        "not a row",
    ])
    chk(len(junk) == 2, "junk rows cost rows, not the call", "kept %d" % len(junk))
    chk(mod.segments_from_payload(None) == [], "a None payload is empty, not a crash")
    chk(mod.segments_from_payload({"segments": None}) == [],
        "a payload with no segments is empty, not a crash")
    chk(mod.summarize(None)["n_speakers"] == 0, "summarize of nothing is 0")
    return [r for r in out if r[1]]


def epoch_arms(mod) -> list:
    """THE EPOCH: two processes, two zeros, one number that bridges them.

    This arm exists because of a bug that NO oracle in this repo could have
    caught, and which is worth writing down rather than fixing quietly.

    The worker stamps a caption's `start` as seconds since ITS OWN capture
    began -- `sotto_worker.py:5736` computes `(idx - 1) * asr.chunk / TARGET_SR`,
    where `idx` is the worker's own chunk counter. The sidecar is a DIFFERENT
    process and publishes on the wall clock. Handing one frame's numbers to the
    other raises nothing, logs nothing, and attributes every line to whichever
    stranger spoke at that stream position in the sidecar's window.

    Every oracle until now drove both sides from one fake clock, so the
    arithmetic was consistent in the test and meaningless in production. These
    arms pin the property that makes it meaningful, and the live instrument
    `_main/_speaker-chain-live.py` measures what it buys: 14 of 37 captions
    named WITH the epoch, 0 without.
    """
    out = []

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))
        return bool(ok)

    # A line at stream 0,2-0,9 s and a voice at wall 300,2-300,9 s. Those are
    # the SAME 0,7 s of audio -- or they are unrelated, depending entirely on
    # whether the epoch is carried.
    payload = {"segments": [{"start": 300.2, "end": 300.9, "speaker": 0}]}
    line = {"start": 0.2, "end": 0.9, "text": "e eu quero que o alt c"}

    without = mod.attribute_from_payload(payload, [line], base_source="device:X")[0]
    chk(without.get("speaker") is None,
        "WITHOUT the epoch the same line names nobody -- the two zeros are "
        "unrelated", repr(without.get("speaker")))

    with_off = mod.attribute_from_payload(payload, [line],
                                          base_source="device:X",
                                          window_offset=300.0)[0]
    chk(with_off.get("speaker") == "speaker-1",
        "WITH the epoch it finds its voice", repr(with_off.get("speaker")))
    chk(with_off.get("source") == "device:X/voice:speaker-1",
        "and gets the voice's own source", repr(with_off.get("source")))

    # THE PROPERTY THAT MATTERS MOST: the offset moves the LOOKUP, never the
    # line. These `start`/`end` travel on to the panel, the history and the
    # transcript; rewriting them into wall clock would corrupt all three and
    # nothing would say so.
    chk(with_off.get("start") == 0.2 and with_off.get("end") == 0.9,
        "the line's OWN times are not rewritten by the offset",
        repr([with_off.get("start"), with_off.get("end")]))
    chk(without.get("start") == 0.2 and without.get("end") == 0.9,
        "...nor by its absence")

    chk(mod.attribute_from_payload(payload, [line], base_source="device:X",
                                   window_offset="nonsense")[0].get("speaker")
        is None,
        "a nonsense epoch is ignored, not fatal")
    chk(mod.attribute_from_payload(payload, [line], base_source="device:X",
                                   window_offset=0.0)[0].get("speaker") is None,
        "a zero epoch is the identity")

    # A negative epoch is legitimate: the worker can start its stream stamp
    # after the sidecar's window began. The line is long enough on purpose --
    # a first draft used the 0,7 s line above, whose shifted window overlapped
    # only 0,2 s and fell under the 0,30 s floor, so the arm reported the
    # arithmetic I had got wrong as a product defect.
    long_line = {"start": 0.2, "end": 1.5, "text": "e ai pessoal tudo bem"}
    back = mod.attribute_from_payload(
        {"segments": [{"start": 0.2, "end": 0.9, "speaker": 0}]}, [long_line],
        base_source="device:X", window_offset=-0.5)[0]
    chk(back.get("speaker") == "speaker-1", "a negative epoch works too",
        repr(back.get("speaker")))
    chk(back.get("start") == 0.2 and back.get("end") == 1.5,
        "and still does not rewrite the line")
    return out


def bridge_arms(mod) -> list:
    """The bridge: every reason to REFUSE a payload is an ordinary answer.

    This is the arm that matters most in the product and it is the one nothing
    else covers. A stale payload does not crash anything -- it labels a
    stranger's voice "speaker-1" for as long as the app runs, which is the kind
    of bug a human notices three hours later and cannot explain.
    """
    import json
    import time
    out = []

    def chk(ok, name, detail=""):
        out.append((bool(ok), name, detail))
        return bool(ok)

    tmp = tempfile.mkdtemp(prefix="speaker-bridge-")
    try:
        good = os.path.join(tmp, "good.json")
        with open(FIXTURE, "r", encoding="utf-8") as fh:
            body = fh.read()
        with open(good, "w", encoding="utf-8") as fh:
            fh.write(body)

        missing = os.path.join(tmp, "nope.json")

        empty = os.path.join(tmp, "empty.json")
        open(empty, "w").close()

        partial = os.path.join(tmp, "partial.json")
        with open(partial, "w", encoding="utf-8") as fh:
            fh.write(body[:len(body) // 2])

        garbage = os.path.join(tmp, "garbage.json")
        with open(garbage, "w", encoding="utf-8") as fh:
            fh.write("this is not json at all")

        nosegs = os.path.join(tmp, "nosegs.json")
        with open(nosegs, "w", encoding="utf-8") as fh:
            json.dump({"rtf": 0.4}, fh)

        notadict = os.path.join(tmp, "list.json")
        with open(notadict, "w", encoding="utf-8") as fh:
            json.dump([1, 2, 3], fh)

        # `payload_if_fresh` tem de devolver None, NUNCA LEVANTAR. E o mutante
        # `raises-on-a-partial-read` existe precisamente para rebentar essa
        # promessa. UMA EXCEPCA QUE ESCAPA DO CODIGO EM TESTE E' UM VERMELHO,
        # NAO UMA FALHA DO HARNESS: sem esta proteccao o mutante rebentava a
        # bateria com JSONDecodeError e o gate reportava-o como DECORATIVO --
        # trocando uma prova por uma mentira na direccao oposta.
        def none_or_red(path, label):
            try:
                got = mod.payload_if_fresh(path)
            except Exception as exc:                            # noqa: BLE001
                chk(False, label, "LEVANTOU %s em vez de devolver None: %r"
                    % (type(exc).__name__, exc))
                return None
            chk(got is None, label,
                "" if got is None else "devolveu %r em vez de None" % (got,))
            return got

        none_or_red(missing, "absent payload -> None")
        none_or_red("", "empty path -> None")
        none_or_red(empty, "zero-byte payload -> None")
        none_or_red(partial,
                    "a payload caught mid-write -> None, not an exception")
        none_or_red(garbage, "garbage payload -> None")
        none_or_red(nosegs, "a payload with no segments -> None")
        none_or_red(notadict, "a JSON list -> None")

        got = mod.payload_if_fresh(good)
        chk(isinstance(got, dict) and len(got.get("segments", [])) == 10,
            "a fresh payload is honoured")

        # STALE. The dangerous one.
        old = os.path.join(tmp, "old.json")
        with open(old, "w", encoding="utf-8") as fh:
            fh.write(body)
        stale_t = time.time() - 3600.0
        os.utime(old, (stale_t, stale_t))
        chk(mod.payload_if_fresh(old, max_age_s=30.0) is None,
            "an hour-old payload is refused")
        chk(mod.payload_if_fresh(old, max_age_s=7200.0) is not None,
            "the age limit is a parameter, not a constant in stone")
        chk(mod.payload_if_fresh(good, max_age_s=30.0) is not None,
            "a payload written now is inside any sane window")

        # A size guard, measured by shrinking the limit rather than by writing
        # 4 MB of junk to the owner's disk.
        saved = mod.MAX_PAYLOAD_BYTES
        try:
            mod.MAX_PAYLOAD_BYTES = 16
            chk(mod.payload_if_fresh(good) is None,
                "something too big to be a payload -> None")
        finally:
            mod.MAX_PAYLOAD_BYTES = saved

        # And what the app actually does with it.
        base = "device:CABLE Output (VB-Audio Virtual Cable)"
        lines = [{"start": 0.5, "end": 2.0, "text": "e eu quero que o alt c"}]
        off = mod.apply_to_lines(lines, base_source=base)
        chk(off[0].get("speaker") is None, "OFF: no attribution")
        chk(off[0].get("source") == base, "OFF: the source is untouched")
        chk(off[0].get("text") == lines[0]["text"], "OFF: the words survive")

        payload = mod.payload_if_fresh(good)
        on = mod.apply_to_lines(lines, base_source=base, payload=payload)
        chk(on[0].get("speaker") == "speaker-1",
            "ON: the line that is actually speech gets a voice",
            repr(on[0].get("speaker")))
        chk("voice:speaker-1" in str(on[0].get("source")),
            "ON: and its own source key", repr(on[0].get("source")))

        chk(mod.voices(None)["n_speakers"] == 0, "OFF: zero voices")
        chk(mod.voices(payload)["n_speakers"] == 4, "ON: four voices heard")

        stale_line = mod.apply_to_lines(lines, base_source=base,
                                        payload=mod.payload_if_fresh(old, 30.0))
        chk(stale_line[0].get("speaker") is None,
            "a stale payload attributes NOTHING -- the whole point")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


BRIDGE_MUTANTS = [
    ("accepts-a-stale-payload",
     "    if age > max_age_s:",
     "    if False:"),
    ("raises-on-a-partial-read",
     "    except (OSError, ValueError, UnicodeDecodeError):",
     "    except ZeroDivisionError:"),
    ("no-size-guard",
     "    if stat.st_size <= 0 or stat.st_size > MAX_PAYLOAD_BYTES:",
     "    if False:"),
]


def run_mutants(label_prefix, source, mutants, arms_for, tmp):
    """Break one file on purpose, N ways, and demand the gate notice each.

    UM MUTANTE QUE NAO CORRE NAO E' UM MUTANTE APANHADO. Este codigo contava
    uma excepcao de import/carregamento como "GREEN mutant ... refused to run" e
    somava ao contador -- exactamente o defeito que um auditor provou no
    oraculo de plumbing em 2026-10-19 (mutantes que nunca executam um unico
    check, gate a dizer 6/6). O veredicto tem de REPROVAR um braco decorativo,
    nunca inflar a contagem. `weak` conta os que nao provaram nada.
    """
    caught = 0
    weak = 0
    for offset, (label, old, new) in enumerate(mutants):
        if old not in source:
            print("  RED   mutant %-32s ANCHOR MISSING -- the oracle is stale"
                  % label)
            weak += 1
            continue
        broken = source.replace(old, new, 1)
        path = os.path.join(tmp, "%s_%d.py" % (label_prefix, offset))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(broken)
        # CARREGAR e CORRER sao coisas diferentes e nunca podem ser confundidas:
        # se a copia nao carrega, o mutante nao foi testado; se carrega mas
        # rebenta a bateria, o codigo partiu mas o gate nao consegue dizer QUAL
        # check o apanhou. Nenhum dos dois pode virar "caught".
        try:
            bad = load_module(path, "%s_mut_%d" % (label_prefix, offset))
        except Exception as exc:                                # noqa: BLE001
            print("  RED   mutant %-32s DECORATIVO: nao carregou (%s) -- "
                  "NAO foi testado" % (label, type(exc).__name__))
            weak += 1
            continue
        try:
            res = arms_for(bad)
        except Exception as exc:                                # noqa: BLE001
            print("  RED   mutant %-32s INCONCLUSIVO: carregou mas a bateria "
                  "morreu antes de um check nomeado (%s)"
                  % (label, type(exc).__name__))
            weak += 1
            continue
        reds = [name for ok, name, _ in res if not ok]
        if reds:
            print("  GREEN mutant %-32s caught by: %s"
                  % (label, "; ".join(reds[:3])))
            caught += 1
        else:
            print("  RED   mutant %-32s SURVIVED -- the gate is blind here"
                  % label)
    return caught, weak


def main() -> int:
    if not os.path.isfile(MODULE_PATH):
        print("RED   module missing: %s" % MODULE_PATH)
        return EXIT_FAIL
    bridge_path = os.path.join(REPO, "worker", "speaker_bridge.py")
    if not os.path.isfile(bridge_path):
        print("RED   bridge missing: %s" % bridge_path)
        return EXIT_FAIL
    with open(MODULE_PATH, "r", encoding="utf-8") as fh:
        source = fh.read()
    with open(bridge_path, "r", encoding="utf-8") as fh:
        bridge_source = fh.read()

    print("PURITY (the owner: PARE DE FAZER MEU PC TRAVAR)")
    heavy = []
    for label, text in (("speaker_id", source), ("speaker_bridge", bridge_source)):
        imported = set()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        found = sorted(imported & set(FORBIDDEN_IMPORTS))
        if found:
            heavy.append((label, found))
    print("  %s neither module imports a model, an audio stack or Win32%s"
          % ("GREEN" if not heavy else "RED  ",
             "" if not heavy else "  %r" % (heavy,)))

    print("\nARMS (real module, then the REAL diarizer output, then the bridge)")
    mod = load_module(MODULE_PATH, "speaker_id_live")
    sys.path.insert(0, os.path.join(REPO, "worker"))
    bridge = load_module(bridge_path, "speaker_bridge_live")
    rows = battery(mod) + real_data_arms(mod) + epoch_arms(mod) + bridge_arms(bridge)
    for ok, name, detail in rows:
        print("  %s %s%s" % ("GREEN" if ok else "RED  ", name,
                             ("  " + detail) if detail else ""))
    green = sum(1 for ok, _, _ in rows if ok)
    print("\n  %d/%d" % (green, len(rows)))

    print("\nNEGATIVE ARM (broken copies must go RED)")
    tmp = tempfile.mkdtemp(prefix="speaker-id-oracle-")
    weak = 0
    try:
        caught, weak_a = run_mutants(
            "sid", source, MUTANTS,
            lambda bad: battery(bad, trials=600) + real_data_arms(bad)
            + epoch_arms(bad), tmp)
        weak += weak_a
        caught_b, weak_b = run_mutants("brg", bridge_source, BRIDGE_MUTANTS,
                                       bridge_arms, tmp)
        caught += caught_b
        weak += weak_b
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    total_mutants = len(MUTANTS) + len(BRIDGE_MUTANTS)
    ok = ((not heavy) and green == len(rows)
          and caught == total_mutants and weak == 0)
    print("\nVERDICT: %s  arms %d/%d  mutants %d/%d"
          % ("PASS" if ok else "FAIL", green, len(rows), caught, total_mutants))
    if weak:
        print("  %d mutante(s) DECORATIVO(S): nao correram, logo nao provaram "
              "nada. Um braco negativo que promete %d e testa %d nao cumpre."
              % (weak, total_mutants, caught))
    return EXIT_PASS if ok else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())