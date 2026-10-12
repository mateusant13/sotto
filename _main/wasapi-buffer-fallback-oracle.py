#!/usr/bin/env python3
"""wasapi-buffer-fallback-oracle -- is the 100 ms retry dead code, and does the poll still need it?

AUDIT ROW F3 (inherited from #36): "o fallback de buffer de 100 ms e codigo morto
(audio-path.md:279)", whose text says the first Initialize succeeds on this host so the HNS_100MS
retry "never runs", and that "the buffer the 25 ms poll needs is exactly the one the fallback would ask
for, and it is unreachable".

MEASURED HERE, and each part of the finding lands somewhere different:

  1. THE ANCHORS ARE STALE. The finding cites wasapi_loopback.py:416 and the retry at :418-425; on the
     live file the Initialize pair is at :895-907 (rule 2 of AGENTS.md: name the revision).
  2. "DEAD CODE" IS FALSE AS STATED. The retry is guarded by the FIRST call failing --
     init(... hnsBufferDuration=0 ...) then "if hr != 0: init(... HNS_100MS ...)". A guarded retry is
     not unreachable: it runs whenever a device or driver refuses a zero duration. What is true is
     narrower and is what this oracle asserts: the retry is CONDITIONAL and carries HNS_100MS. The
     neg-arm removes the guard and that arm goes RED.
  3. THE PREMISE IS STALE. There is no 25 ms poll any more. The period is now
     min(0.005, max(0.001, block_ms/1000/20)) -- 5 ms at the shipped 100 ms block, i.e. ~4x FASTER than
     the 22 ms ring -- and the code carries its own measurement (:955-968): period 25 ms -> duty 0.815,
     period 5 ms -> duty 0.999, same process, same device, same block. So the requirement the finding
     names was met by changing the POLL, which is the cheaper and already-measured fix, not by asking
     for a bigger buffer.
  4. WHAT THIS ORACLE CANNOT SAY: it does not open a device. The ring this host grants today is read
     from the code's own recorded measurement (1056 frames = 22 ms), not re-measured, and the reason is
     stated rather than hidden: a device open is a device open, and the owner is using the machine.

Both colours come from the real source: --neg-arm deletes the guard in an extracted copy.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
MODULE = os.path.join(ROOT, "worker", "wasapi_loopback.py")
CONFIG = os.path.join(ROOT, "worker", "config.json")

RETRY_GUARD = "if hr != 0:"
OLD_PERIOD = "block_ms / 1000.0 / 4.0"
NEW_PERIOD = "block_ms / 1000.0 / 20.0"
RING_MS_RECORDED = 22.0


class _Self:
    """The formula reads self.block_ms, so it is evaluated against this instead of a bare name --
    a NameError here would be a defect of the oracle, not of the module."""

    def __init__(self, block_ms):
        self.block_ms = block_ms


def _namespace(block_ms):
    return {"block_ms": block_ms, "self": _Self(block_ms), "min": min, "max": max}


def initialize_pair(source):
    """The two init(...) calls and the code between them, or None."""
    start = source.find("init(client, AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 0, 0, mix, None)")
    if start < 0:
        return None
    end = source.find('Initialize(SHARED|LOOPBACK) failed', start)
    if end < 0:
        return None
    return source[start:end]


def retry_guarded(region):
    """Is the SECOND init() call guarded by the FIRST one's hr?

    The region also contains the "if hr != 0: raise" that follows the retry, so "the guard is in the
    region" is true even when the retry is NOT guarded -- which is exactly what the first version of
    this oracle asserted, and its neg-arm reported guarded=true with the mutant in place. The question
    is about the slice BETWEEN the two calls.
    """
    first = region.find("init(")
    second = region.find("init(", first + 5)
    if second < 0:
        return None
    return RETRY_GUARD in region[:second]


def period_of(source, mutate=False):
    match = re.search(r"period = min\(([^\n]+)\)", source)
    if not match:
        return None, None
    expression = match.group(1)
    if mutate:
        expression = expression.replace("1000.0 / 20.0", "1000.0 / 4.0")
    return expression, match.group(0)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(MODULE, encoding="utf-8") as handle:
        source = handle.read()
    with open(CONFIG, encoding="utf-8") as handle:
        block_ms = float(json.load(handle)["audio"]["block_ms"])
    say("wasapi-buffer-fallback-oracle -- row F3: the 100 ms retry, and the poll that needs it")
    wrong = []

    region = initialize_pair(source)
    if region is None:
        say("VERDICT: FAIL -- the Initialize pair was not found (the code moved again)")
        return 1
    first_call = region.count("init(")
    guarded = retry_guarded(region)
    carries_100ms = "HNS_100MS" in region
    line = source[:source.find(region)].count("\n") + 1
    say("  the Initialize pair lives at :%d, %d init() calls, retry guarded by '%s': %s"
        % (line, first_call, RETRY_GUARD, str(guarded).lower()))
    say("  the retry carries HNS_100MS (=%s): %s"
        % (re.search(r"HNS_100MS = ([^\n]+)", source).group(1), str(carries_100ms).lower()))
    if first_call != 2:
        wrong.append("expected TWO init() calls (default then retry), found " + str(first_call))
    if not guarded:
        wrong.append("the retry is NOT guarded -- it would run unconditionally, i.e. it WOULD be dead"
                     " only in the other direction (asking 100 ms first)")
    if not carries_100ms:
        wrong.append("the retry no longer passes HNS_100MS")

    old_gone = OLD_PERIOD not in source
    expression, _raw = period_of(source)
    if expression is None:
        say("VERDICT: FAIL -- the period formula was not found")
        return 1
    value = eval("min(" + expression + ")", {"__builtins__": {}}, _namespace(block_ms))
    say("  block_ms from config.json: %s" % block_ms)
    say("  period formula: min(%s)  ->  %.4f s (%.1f ms)" % (expression, value, value * 1000.0))
    say("  recorded ring on this host: %.1f ms (the module own measurement: 1056 frames at 48 kHz)"
        % RING_MS_RECORDED)
    say("  the OLD formula (block_ms/1000/4) is gone: " + str(old_gone).lower())
    if not old_gone:
        wrong.append("the OLD 25 ms formula is back in the file")
    if value * 1000.0 >= RING_MS_RECORDED:
        wrong.append("the poll (%.1f ms) is NOT faster than the recorded ring (%.1f ms) -- the overflow"
                     " the module documents would return" % (value * 1000.0, RING_MS_RECORDED))
    measured = "duty 0.815" in source and "duty 0.999" in source
    say("  the module still carries its own duty measurement (0.815 -> 0.999): "
        + str(measured).lower())
    if not measured:
        wrong.append("the recorded duty measurement is gone -- the comment would be an assertion again")

    if parsed.neg_arm:
        # MUTANT A: the guard removed INSIDE the region it belongs to. The first version replaced the
        # first "if hr != 0:" in the whole FILE, which is not this one, and the mutant then measured
        # nothing -- the mutant has to be built on the region under test.
        m_region = region.replace(RETRY_GUARD, "if True:", 1)
        m_guarded = retry_guarded(m_region)
        # MUTANT B: the OLD shipped period restored, cap and all -- the shipped formula is
        # min(0.005, ...), so mutating only the divisor inside it cannot move the answer (the cap wins);
        # a faithful mutant replaces the STATEMENT.
        m_source = re.sub(r"period = min\([^\n]+\)", "period = self.block_ms / 1000.0 / 4.0", source)
        m_expr, _ = period_of(m_source)
        m_value = None
        if m_expr is None:
            m_value = block_ms / 1000.0 / 4.0
        say("")
        say("  mutant A (guard -> if True, in the region): retry still guarded=%s" % str(m_guarded).lower())
        say("  mutant B (old statement restored): formula found=%s, period=%.1f ms (ring=%.0f ms)"
            % (str(m_expr is not None).lower(), (m_value or 0.0) * 1000.0, RING_MS_RECORDED))
        if m_guarded:
            wrong.append("NEG-ARM A: removing the guard inside the region did not change it")
        if m_expr is not None:
            wrong.append("NEG-ARM B: the old period statement was not recognised as a change")
        elif (m_value or 0.0) * 1000.0 < RING_MS_RECORDED:
            wrong.append("NEG-ARM B: the restored old period is still faster than the ring")
        say("")
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL")
            + ": removing the guard must make the retry unconditional, and restoring the OLD period"
            " statement must put the poll back ABOVE the ring")
        return 0 if not wrong else 1

    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the retry is CONDITIONAL (not dead: :%d, guarded by the first call failing), and the" % line
        + " poll is %.1f ms against a recorded %.0f ms ring, which is the requirement the finding named,"
          " met by the poll" % (value * 1000.0, RING_MS_RECORDED))
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
