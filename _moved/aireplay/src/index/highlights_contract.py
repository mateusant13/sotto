"""highlights_contract.py -- WHAT THE HIGHLIGHTS DETECTOR NEEDS FROM THE REPLAY LANE.

================================================================================
WHY THIS FILE EXISTS, AND WHY IT READS HEADER TEXT
================================================================================

This lane does NOT own clip extraction.  `src/capture/trigger.*` and
`src/capture/replay.*` belong to the `bg_feb2d120` family and are mid-flight, so
this file does two things instead of touching them:

  1. it states, field by field and unit by unit, exactly what a fired
     `Highlight` has to become in order to cut a retroactive clip; and
  2. it VERIFIES the producer against the C++ header TEXT, so a renamed field
     turns this file RED at chain time instead of silently dropping a number.

It reads text rather than importing because C++ cannot be imported -- the same
constraint `src/pipeline/contracts.py` already handles for `CutResult`, and for
the same reason: a boundary nobody checks is a boundary that lies quietly.

================================================================================
THE ONE-LINE HOOKUP, AND WHO OWNS IT
================================================================================

The detector's product is `Highlight`.  The capture side's product is
`CutRequest` (trigger.h:106), and the run loop already consumes it through
`Trigger::take(CutRequest*, timeout_ms)` (trigger.h:175).  So the intended seam
is NOT a new pipeline: it is "a highlight becomes one more CutRequest".

THE COUPLING, STATED PLAINLY, because it is the one thing this lane cannot
finish on its own:

    `Trigger::emit(CutRequest&&, bool, bool)` is PRIVATE  -- trigger.h:224
    `Replay::issue_cut(uint64_t)`        is PRIVATE       -- replay.h:175

There is therefore NO public way, today, for a detector outside `src/capture` to
inject a `CutRequest`, and none is added here.  The missing piece is one public
injection point in `Trigger` (or one call to the existing `take()` consumer from
whatever thread runs the detector).  That file is not this lane's.  The gate in
this module asserts that the seam is still missing, so when the replay lane adds
it, this file says so loudly instead of the highlights feature quietly never
firing in the product.

THE UNIT GAP, which is the subtler of the two and is easy to miss:

    `Highlight.t_peak_s` is in SECONDS, on the detector's own analysis clock.
    `CutRequest.t_cut_ns` is in QPC NANOSECONDS.

Nothing on this box converts between the two.  `src/pipeline/contracts.py`
already carries this exact gap for `CutResult.base_qpc_ns` (its
`CONTRACT_GAPS[1]`) and works around it by deriving wall-clock from the file
mtime and RECORDING that it did.  The highlights lane must not invent a clock:
it hands over seconds and says so, and the replay lane -- which owns the QPC base
-- converts.  Getting this wrong does not crash; it cuts a clip from a ring
position that is off by however far the two clocks have drifted, which is the
kind of bug that looks like "the highlight is always slightly wrong".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from highlights import Highlight

__all__ = [
    "CUT_REQUEST_FIELDS",
    "REPLAY_H_RELPATH",
    "TRIGGER_H_RELPATH",
    "HighlightToCut",
    "ContractStatus",
    "check_seam",
    "to_cut_request_payload",
    "UNIT_GAP",
    "COUPLING",
]

_SRC = Path(__file__).resolve().parent.parent          # src/
REPO = _SRC.parent

TRIGGER_H_RELPATH = "src/capture/trigger.h"
REPLAY_H_RELPATH = "src/capture/replay.h"

#: The fields this lane must fill, taken from `CutRequest` as it stands in
#: trigger.h TODAY.  `check_seam()` re-reads the header and fails if a name
#: disappears; that is the whole point -- a renamed field here is a highlight
#: that gets cut with somebody else's window.
CUT_REQUEST_FIELDS: tuple[str, ...] = (
    "t_cut_ns", "request_seq", "detected_latency_us", "requested_window_s",
    "ring_span_s", "shorter_than_requested", "from_registerhotkey",
    "from_async_poll", "binding", "note",
)

#: The two fields the replay lane has not built yet, named by owner.
UNIT_GAP = (
    "seconds -> QPC nanoseconds. `Highlight.t_peak_s` is seconds on the "
    "detector's analysis clock; `CutRequest.t_cut_ns` is QPC ns. No producer on "
    "this box converts between them (`src/pipeline/contracts.py` CONTRACT_GAPS[1] "
    "carries the same gap for `CutResult.base_qpc_ns`). OWNER: the replay lane, "
    "which owns the QPC base. Until it exists this lane emits SECONDS and says so."
)

COUPLING = (
    "`Trigger::emit` (trigger.h:224) and `Replay::issue_cut` (replay.h:175) are "
    "both PRIVATE, so no detector outside src/capture can inject a CutRequest "
    "today. Missing piece: ONE public injection point in Trigger. OWNER: the "
    "`bg_feb2d120` family (src/capture/trigger.*, replay.*). This lane does not "
    "edit that file and does not fake the call."
)


@dataclass(frozen=True)
class HighlightToCut:
    """The payload a fired `Highlight` becomes, field by field, with its unit."""

    #: what the detector knows
    t_peak_s: float
    window_start_s: float
    window_end_s: float
    requested_window_s: float
    reason: str
    #: what the detector does NOT know and MUST NOT invent
    ring_span_s: float = -1.0          # -1 = not probed, exactly as trigger.h:111
    shorter_than_requested: bool = False

    @property
    def needs_conversion(self) -> bool:
        return True   # seconds -> QPC ns. Always. See UNIT_GAP.


def to_cut_request_payload(h: Highlight) -> HighlightToCut:
    """Turn a fired highlight into the payload the replay lane consumes.

    Deliberately does NOT produce a `CutRequest`: that struct is C++, and the two
    fields that would fill it honestly -- `t_cut_ns` and `ring_span_s` -- are not
    knowable from here.  `ring_span_s` stays -1, which is the value trigger.h:111
    documents as "not probed", so the replay lane can tell "no history" apart
    from "did not ask".
    """
    return HighlightToCut(
        t_peak_s=h.t_peak_s,
        window_start_s=h.window_start_s,
        window_end_s=h.window_end_s,
        requested_window_s=h.window_s,
        reason=h.reason,
        ring_span_s=-1.0,
        shorter_than_requested=False,
    )


@dataclass(frozen=True)
class ContractStatus:
    name: str
    ok: bool
    detail: str


def _read(rel: str) -> str:
    p = REPO / rel
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def check_seam() -> list[ContractStatus]:
    """Read the C++ headers and report what is true about the seam RIGHT NOW.

    Every check below is a statement about bytes on disk, not about an intention.
    """
    out: list[ContractStatus] = []
    trig = _read(TRIGGER_H_RELPATH)
    rep = _read(REPLAY_H_RELPATH)

    if not trig:
        out.append(ContractStatus("trigger.h readable", False,
                                  f"{TRIGGER_H_RELPATH} not found from {REPO}"))
        return out
    out.append(ContractStatus("trigger.h readable", True, TRIGGER_H_RELPATH))

    struct = re.search(r"struct\s+CutRequest\s*\{(.*?)\n\};", trig, re.S)
    if not struct:
        out.append(ContractStatus("CutRequest found", False,
                                  "no `struct CutRequest { ... };` in trigger.h -- the "
                                  "replay lane renamed or moved it"))
        return out
    body = struct.group(1)
    missing = [f for f in CUT_REQUEST_FIELDS if not re.search(rf"\b{re.escape(f)}\b", body)]
    out.append(ContractStatus(
        "CutRequest fields", not missing,
        "all %d fields present" % len(CUT_REQUEST_FIELDS) if not missing
        else "MISSING: " + ", ".join(missing)))

    take = re.search(r"bool\s+take\s*\(\s*CutRequest\s*\*\s*out", trig)
    out.append(ContractStatus(
        "consumer take(CutRequest*) exists", bool(take),
        f"{TRIGGER_H_RELPATH}:175 shape found" if take
        else "no `bool take(CutRequest* out, ...)` -- the consumer side moved"))

    probe = re.search(r"virtual\s+double\s+span_seconds\s*\(\s*\)\s*=\s*0\s*;", trig)
    out.append(ContractStatus(
        "RingSpanProbe::span_seconds() exists", bool(probe),
        "the one-method probe the clip window must ASK, not assume" if probe
        else "gone -- the ring can no longer be asked how much history it holds"))

    # The seam itself.  It is expected to be MISSING; when it appears, this is the
    # check that tells the highlights feature to go looking for a call site.
    emit_pub = re.search(r"^\s{4}void\s+emit\s*\(", trig, re.M)
    out.append(ContractStatus(
        "a public CutRequest injection point exists", bool(emit_pub),
        "FOUND -- a detector can now inject a CutRequest; wire "
        "to_cut_request_payload() to it and re-check this file"
        if emit_pub else COUPLING))

    issue_cut = re.search(r"^\s{4}void\s+issue_cut\s*\(", rep, re.M) if rep else None
    out.append(ContractStatus(
        "Replay::issue_cut reachable from outside", bool(issue_cut),
        f"{REPLAY_H_RELPATH} declares issue_cut PUBLIC" if issue_cut
        else "still private, as it was when this contract was written"))

    out.append(ContractStatus(
        "seconds -> QPC conversion available", False,
        UNIT_GAP + "  (declared RED deliberately: until the replay lane owns this "
                   "conversion, a highlight cannot name its own ring position)"))

    return out


if __name__ == "__main__":      # pragma: no cover - the receipt quotes this
    import sys
    rows = check_seam()
    for r in rows:
        print(f"[{'ok ' if r.ok else 'GAP'}] {r.name}: {r.detail}")
    sys.exit(0)