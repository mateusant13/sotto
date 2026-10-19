#!/usr/bin/env python
"""speaker_id.py -- WHO IS SPEAKING, as a pure function of time.

OWNER, 2026-10-18, verbatim:
    "e por que tu ta commitando de forma burra/pushando? ... e mostra pra mim a
     legenda ao vivo ou o parakeet processando os audios do discord meu e dos
     meus amigos. de forma natural, encaixa no sotto"

THE GAP THIS FILE IS THE ANSWER TO, and it is measured, not assumed.
`_main/receipt-20261013-no-speaker-attribution.md` (2026-10-13) put a number on
it:

    worker/sotto_worker.py    3 matches for "speaker" -- ALL THREE ARE PROSE
    app/panel/panel.js        1 match  -- also prose ("Captions may lag the
                                           speaker.")

There is no field, no id, no code. The same receipt says what that means: *"This
is not a DESIGN gap that CSS can close -- it is an ENGINE gap."* A zip can style a
speaker badge all it likes; the line still carries no name.

WHAT ALREADY EXISTS, so this module does the smallest possible thing:

  * CAPTURE. `worker/wasapi_loopback.py` already captures the default render
    endpoint, which is where Discord puts the MIX of a call. Driver-free.
  * SEPARATION. `_main/diar-models/` holds pyannote-segmentation-3.0 exported to
    ONNX plus a 3D-Speaker embedding model, `sherpa_onnx 1.13.4` is installed,
    and `_main/receipt-diarization-decisive.md` measured the whole thing. Re-run
    today against the vendor's ground-truth file: **DER 0,03 %, 10 segments,
    4 speakers** (`_main/_hoje-ctrl.json`).
  * THE PANEL IS ALREADY N-SPEAKER. `panel.js` keys its open provisional rows by
    `source` ("ONE OPEN ROW PER SOURCE", 2026-10-11) and never matches on an
    attribute, precisely because a device name contains `:`, quotes and
    backslashes.

THE LAST POINT IS THE WHOLE ARCHITECTURE. If each speaker becomes its own
`source`, the panel keeps one forming line per person with NO structural change
to the panel at all. So the missing piece is only this: turn diarizer segments
into a label per caption line, and hand it over on the channel that already
exists.

WHY PURE FUNCTIONS AND NO MODEL HERE. This module never loads a model, opens an
audio device, or touches Win32. The model is somebody else's job (sherpa-onnx,
already measured); the decision of WHICH SEGMENT OWNS WHICH WORDS is this
module's, and a decision is worth testing without a 639 MB checkpoint in the
loop. Everything here is milliseconds.

THE FOUR THINGS THAT ARE EASY TO GET WRONG, and are therefore the four the
oracle pins:

  1. A caption line that OVERLAPS two speakers must go to the one who holds more
     of it, and to NOBODY when neither holds enough of it. Overlap has to be
     measured against the audio, not decided by who started first.
  2. The label must be STABLE. Numbering by cluster id would relabel a speaker
     mid-call as soon as a new cluster appeared; numbering by FIRST APPEARANCE
     does not.
  3. Silence is not a speaker. A line whose audio is entirely outside every
     segment is `None`, and the panel then shows the line with no name -- which
     is honest, and is what the 2026-10-13 receipt asked for instead of a blank.
  4. Words spanning a turn DO HAPPEN ("e eu ia dizer que" / "mas não"). The
     overlap rule sends the whole line to one speaker, which is a product
     decision and is stated here rather than discovered later.
"""
from __future__ import annotations

import math
from typing import Iterable, NamedTuple, Optional, Sequence


class Segment(NamedTuple):
    """One diarizer segment: half-open `[start, end)` in seconds."""

    start: float
    end: float
    speaker: object


def overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    """Seconds of `[a0, a1)` that also lie in `[b0, b1)`. Never negative."""
    return max(0.0, min(a1, b1) - max(a0, b0))


def speaker_for_window(
    window: Sequence[float],
    segments: Iterable[Segment],
    min_overlap: float = 0.30,
) -> Optional[object]:
    """The speaker holding most of `window` (a `(start, end)` pair).

    `min_overlap` is the floor in SECONDS of speech, not a fraction: a caption
    line is seconds long, and "at least 0,3 s of somebody's voice" is a statement
    about the world that survives a line of any length. It is measured against
    the WINNER'S TOTAL, so a voice broken into two segments still counts as the
    voice it is. `None` means no speaker owns enough of it, and `None` is a
    legitimate answer -- see rule 3 above.

    WHO WINS. Primary is the TOTAL overlap: rule 1's "the one who holds more of
    it", read literally. Ties go to the longer unbroken stretch, then to whoever
    started first. All three are arbitrary in the sense that a call has no right
    answer at the boundary; what is NOT arbitrary is that they give the SAME
    answer every time, because a caption that changes owner between two reads of
    the same line is a visible flicker.

    THE BUG THIS REPLACED, because it is the kind that survives review.
    `_main/speaker-id-oracle.py` fuzzed this function over 4 000 random segment
    sets against every permutation of each and found **9 sets** whose winner
    flipped with the iteration order. The old code ranked each segment as it
    arrived, comparing against a RUNNING total, so a speaker's score depended on
    which of that speaker's own segments happened to have been seen at the moment
    the comparison ran. The totals are now accumulated first and ranked
    afterwards, and summed with `math.fsum`, whose result is correctly rounded and
    therefore identical whatever order the terms arrive in. Same audio, same
    person, every time.

    One order dependence survived that fix and the oracle's fuzz caught it: when
    two speakers tie on ALL THREE of the above -- which a two-person call can do
    easily, because two people starting together is the normal case, not the rare
    one -- the winner fell out of the iteration order of a dict. The last
    criterion, applied only on an exact tie, is therefore the speaker's own text
    form, so the answer is total. Measured: 9 flipping sets before, 1 after the
    `fsum` fix, 0 after this one, out of the same 4 000 sets x every permutation.
    """
    try:
        t0, t1 = float(window[0]), float(window[1])
    except (TypeError, IndexError, ValueError):
        return None
    if not (t1 > t0):
        return None

    parts: dict = {}
    longest: dict = {}
    first_start: dict = {}
    for seg in segments:
        try:
            ov = overlap(t0, t1, float(seg.start), float(seg.end))
        except (TypeError, ValueError):
            continue
        if ov <= 0.0:
            continue
        speaker = seg.speaker
        parts.setdefault(speaker, []).append(ov)
        if ov > longest.get(speaker, 0.0):
            longest[speaker] = ov
        st = float(seg.start)
        if speaker not in first_start or st < first_start[speaker]:
            first_start[speaker] = st

    best = None
    best_key = None
    for speaker, chunks in parts.items():
        key = (round(math.fsum(chunks), 9),
               round(longest[speaker], 9),
               -first_start[speaker])
        if (best_key is None or key > best_key
                or (key == best_key and str(speaker) < str(best))):
            best_key = key
            best = speaker
    if best is None or best_key[0] < min_overlap:
        return None
    return best


def stable_labels(segments: Iterable[Segment]) -> dict:
    """Cluster ids -> `speaker-1`, `speaker-2`, ... in FIRST-APPEARANCE order.

    Rule 2. A diarizer's own cluster ids are arbitrary integers assigned by the
    clustering, and they are not promised to be stable as the file grows -- a
    speaker can be renumbered when a new cluster appears. Renumbering by first
    appearance makes "speaker-3" mean the same person for the whole call, which
    is the only thing a label in a transcript is allowed to promise.

    Sorted by start time first, so "first appearance" is a fact about the audio
    and not about the order the caller happened to iterate in.
    """
    ordered = sorted(segments, key=lambda s: (float(s.start), str(s.speaker)))
    out: dict = {}
    for seg in ordered:
        if seg.speaker not in out:
            out[seg.speaker] = "speaker-%d" % (len(out) + 1)
    return out


def label_segments(segments: Iterable[Segment]) -> list:
    """`Segment`s with their speaker replaced by the stable label."""
    segs = list(segments)
    labels = stable_labels(segs)
    return [Segment(s.start, s.end, labels[s.speaker]) for s in segs]


def attribute_lines(lines: Iterable[dict], segments: Iterable[Segment],
                    min_overlap: float = 0.30) -> list:
    """Give each caption line a `speaker`, IN PLACE of nothing.

    A line is a dict with `start` and `end`. The function RETURNS new dicts and
    does not mutate the caller's: the worker's caption objects travel to the
    panel, to the history and to the log, and mutating them in place would make
    "what did the engine emit" depend on "what ran after it".

    A line with no confident owner gets `speaker: None`, which is the honest
    value and the one the 2026-10-13 receipt asked for instead of a blank.
    """
    segs = label_segments(segments)
    out = []
    for line in lines:
        new = dict(line)
        try:
            win = (float(line.get("start")), float(line.get("end")))
        except (TypeError, ValueError):
            win = None
        new["speaker"] = (speaker_for_window(win, segs, min_overlap)
                          if win is not None else None)
        out.append(new)
    return out


# ---------------------------------------------------------------------------
# THE REAL DIARIZER'S OUTPUT -> the types above. No model is loaded here either;
# the rows arrive already computed, and this is the only code that has to know
# what sherpa-onnx calls its fields.
# ---------------------------------------------------------------------------

def segments_from_rows(rows: Iterable) -> list:
    """Diarizer rows -> `Segment`s. Rows may be dicts or `Segment`s.

    Tolerates junk on purpose. This reads a file produced by a model run, and a
    model run is exactly the thing that emits a `null` where a number was
    promised. One bad row must cost one row, not the call.
    """
    out = []
    for row in rows or ():
        if isinstance(row, Segment):
            out.append(row)
            continue
        if not isinstance(row, dict):
            continue
        try:
            start = float(row["start"])
            end = float(row["end"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (end > start):
            continue
        speaker = row.get("speaker", row.get("cluster", row.get("label")))
        if speaker is None:
            continue
        out.append(Segment(start, end, speaker))
    return out


def segments_from_payload(payload) -> list:
    """A whole `_diar-run.py` JSON payload -> `Segment`s.

    Measured against the vendor's own ground truth today (2026-10-18,
    `_main/_hoje-ctrl.json`): 10 segments, 4 speakers, **DER 0,03 %**, RTF 0,416.
    """
    if not isinstance(payload, dict):
        return []
    return segments_from_rows(payload.get("segments"))


def speaker_source(base_source, label: Optional[str]) -> Optional[str]:
    """The per-person `source` key, or `None` when nobody owns the line.

    WHY THIS EXISTS, and it is the whole wiring. `panel.js` already keys its
    open provisional rows, its engines and its paint cache by the `source`
    STRING -- `rowIdentity` at `panel.js:386`, `engineFor` at `:743`, one engine
    per source so two apps cannot interleave into one garbled sentence. The row
    key is `source + NUL + start`. Nothing in the panel or the shell parses the
    prefix: a measured search for `startsWith('device:'|'proc:'|'file:')` across
    `app/` and `worker/` returns nothing, so the value is an OPAQUE label.

    That is the whole trick. Give every voice its own `source` and the panel
    keeps one FORMING line per person, with no change to the panel at all -- the
    machinery is already built and already per-source; it has simply never been
    given more than one source in a call.

    The base source is kept in front so provenance survives: a line still says
    which device it came from, and history still knows the call came off the
    cable rather than out of a file.
    """
    if label is None:
        return None
    label = str(label)
    if base_source in (None, ""):
        return "voice:" + label
    return "%s/voice:%s" % (base_source, label)


def attribute_from_payload(payload, lines: Iterable[dict],
                          base_source=None, min_overlap: float = 0.30,
                          window_offset: float = 0.0) -> list:
    """THE CHOKE POINT: diarizer output + caption lines -> attributed lines.

    Each returned line gains `speaker` (the stable label or `None`) and, when a
    voice owns it, `source` becomes that voice's key. A line nobody owns keeps
    `base_source` -- an unattributed line is still the device's line, and losing
    the device on a line of silence would be a worse lie than no name at all.

    Call it with `payload = None` when diarization is off: it is a pass-through
    that still stamps `speaker: None`, so the field is present in every caption
    and the panel never has to ask whether the field exists.

    `window_offset` IS THE JOIN BETWEEN TWO PROCESSES, and it exists because of
    a bug this very session nearly shipped.

    The worker stamps a caption's `start`/`end` as seconds since ITS OWN capture
    began -- `sotto_worker.py:5736` computes `(idx - 1) * asr.chunk / TARGET_SR`,
    where `idx` is the worker's own chunk counter. The sidecar, a DIFFERENT
    process, publishes segments on the wall clock. Those two zeros are unrelated:
    the worker's stream 12,0 s and the sidecar's wall 12,0 s are not the same
    instant, and the difference is however long ago either process happened to
    start.

    Handing one frame's numbers to the other produces NO error and no log line.
    It just attributes every line to whichever stranger happened to speak at that
    stream position in the sidecar's window -- a badge that looks entirely
    plausible and is completely wrong, which is the worst failure a caption can
    have. No oracle could catch it, because every oracle drives both sides from
    one fake clock.

    So the offset is added HERE, and only here: it moves the LOOKUP window into
    the payload's frame and leaves the line's own `start`/`end` untouched, since
    those travel on to the panel, the history and the transcript, and rewriting
    them would corrupt all three.
    """
    segs = label_segments(segments_from_payload(payload))
    try:
        offset = float(window_offset)
    except (TypeError, ValueError):
        offset = 0.0
    out = []
    for line in lines or ():
        new = dict(line)
        try:
            win = (float(line.get("start")) + offset,
                   float(line.get("end")) + offset)
        except (TypeError, ValueError):
            win = None
        label = (speaker_for_window(win, segs, min_overlap)
                 if win is not None else None)
        new["speaker"] = label
        new["source"] = speaker_source(base_source, label) or base_source
        out.append(new)
    return out


def summarize(payload) -> dict:
    """What to tell the owner on the status strip: how many voices were heard."""
    if not isinstance(payload, dict):
        return {"n_speakers": 0, "n_segments": 0, "speech_s": 0.0, "labels": {}}
    segs = segments_from_payload(payload)
    labels = stable_labels(segs)
    return {
        "n_speakers": len(labels),
        "n_segments": len(segs),
        "speech_s": float(payload.get("speech_s") or 0.0),
        "labels": labels,
    }
