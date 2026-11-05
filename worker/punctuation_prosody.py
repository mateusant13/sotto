"""Punctuation from prosody: normalise ASR punctuation using measured silence.

The ASR model emits punctuation of its own and it is frequently wrong: the live
panel carried "What's, crazy is, that Astro at the." -- commas landing inside a
phrase with no pause behind them. This module replaces "trust the model's marks"
with "trust the marks only where the audio agrees".

Measured basis (see _main/receipt-20261105-punct-from-prosody.md, produced by
`python _main/punct-prosody-oracle.py --measure` on the fixture WAVs):

  * 47 inner silences >= 80 ms across the 6 clean fixtures: 41 below 250 ms, 5
    between 250 and 600 ms, 1 at 1100 ms.
  * Of the 6 authored commas, 5 have a 250-600 ms pause at their expected
    position; the sixth (ptbr-tts-02) has 240 ms. No authored comma sits below
    240 ms, so 200 ms is the largest floor that costs no measured comma while
    still killing commas with no pause behind them.
  * All 5 clause-band gaps sit at an authored comma (5/5 precision) and the one
    inner sentence-band gap (1100 ms, pt-br-sample, "segunda-feira. Os
    moradores") sits at the authored sentence break. The 6 sentence-final pauses
    measured 773-878 ms, and no gap in any of the 6 clean fixtures falls between
    441 and 772 ms, which is why the sentence floor sits at 600 ms.

Input contract
    `pauses[i]` is the silence, in milliseconds, AFTER the i-th whitespace token
    of `text`. `len(pauses) == len(tokens) - 1` covers every inner boundary; an
    extra entry at `len(pauses) == len(tokens)` is the trailing silence, used to
    close the last word. Entries may be dicts (`{"ms": ...}`) or plain numbers.

    The dict form also carries `f0_slope` and `rms_slope` from the measurement
    pass. They are accepted and deliberately NOT used: over the 5 clean clause
    gaps the pre-gap F0 direction was 3 rising / 2 falling, i.e. coin-flip, and
    no fixture contains a question, so the "rising F0 turns '.' into '?'" rule has
    no evidence and is not implemented. `?` the model produced is never touched.

Degenerate input is identity: empty text, empty/absent pauses, or a pauses list
shorter than the text means the caller has no audio evidence yet, and this module
never invents punctuation. That is the default until the worker feeds it real
pauses.

Pure stdlib, no I/O, no state.
"""
from __future__ import annotations

import re

__all__ = [
    "normalise",
    "DROP_FLOOR_MS",
    "CLAUSE_MIN_MS",
    "SENTENCE_MIN_MS",
]

#: A model comma with less silence than this behind it is noise. Measured: no
#: authored comma occurred below 240 ms, 69 of 91 measured gaps are below 200 ms.
DROP_FLOOR_MS = 200.0

#: Silence from here up marks a clause boundary.
CLAUSE_MIN_MS = 250.0

#: Silence from here up marks a sentence boundary. 600 ms sits in the measured
#: gap between the widest clause pause (440 ms) and the narrowest sentence pause
#: (773 ms).
SENTENCE_MIN_MS = 600.0

_TOKEN_RE = re.compile(r"\S+")

#: Marks we never drop and never duplicate. `,;:` drop only as junk commas.
_DROPPABLE = ","
_TERMINALS = ",.;:!?…"

#: Closing quotes/brackets are transparent: `"Sim," ele disse` must lose its
#: comma, and a mark added after a quoted phrase belongs INSIDE the quote.
_CLOSERS = "\"'”’)]»"


def _pause_ms(entry):
    """Coerce one pauses[] entry to ms, or None when it carries no evidence."""
    if entry is None:
        return None
    if isinstance(entry, dict):
        if "ms" not in entry:
            return None
        v = entry["ms"]
    else:
        v = entry
    if v is None or isinstance(v, bool):
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if v != v or v < 0.0:  # NaN or nonsense
        return None
    return v


def _at(pauses, i):
    return _pause_ms(pauses[i]) if i < len(pauses) else None


def _peel(token):
    """Split (body, closing quotes/brackets) so marks land inside the quote."""
    i = len(token)
    while i > 0 and token[i - 1] in _CLOSERS:
        i -= 1
    return token[:i], token[i:]


def normalise(text, pauses):
    """Return `text` with punctuation corrected by the measured pauses.

    Rules, in order, each at a word boundary i (between token i and token i+1):

    1. drop a trailing "," on token i when the pause behind it is < DROP_FLOOR_MS.
       No other mark is ever dropped.
    2. append "," when the pause is >= CLAUSE_MIN_MS, "." when it is
       >= SENTENCE_MIN_MS. Skipped when token i already ends with a mark, when
       token i+1 starts with one, or when token i is not a word (so two marks are
       never adjacent).
    3. at the trailing boundary (only if `pauses` has an entry for it) append "."
       when the trailing silence is >= SENTENCE_MIN_MS and the last token has no
       mark of its own.

    Boundaries whose pause is missing or unknown are left exactly as they are.
    Original inter-token whitespace is preserved, so with no pauses this returns
    the input unchanged.
    """
    if not text or not pauses or not isinstance(pauses, (list, tuple)):
        return text

    matches = list(_TOKEN_RE.finditer(text))
    if not matches:
        return text
    n = len(matches)
    pieces = [m.group(0) for m in matches]
    changed = False

    # 1. drop commas the audio does not support.
    for i in range(n - 1):
        ms = _at(pauses, i)
        if ms is None or ms >= DROP_FLOOR_MS:
            continue
        body, close = _peel(pieces[i])
        if body.endswith(_DROPPABLE):
            pieces[i] = body[:-1] + close
            changed = True

    # 2. add marks where the audio does support one.
    for i in range(n - 1):
        ms = _at(pauses, i)
        if ms is None or ms < CLAUSE_MIN_MS:
            continue
        body, close = _peel(pieces[i])
        nxt = pieces[i + 1]
        if not body or body[-1] in _TERMINALS:
            continue
        if nxt and nxt[0] in _TERMINALS:
            continue
        pieces[i] = body + ("." if ms >= SENTENCE_MIN_MS else ",") + close
        changed = True

    # 3. close the last word on trailing silence, if the caller measured it.
    if n >= 1 and len(pauses) >= n:
        ms = _at(pauses, n - 1)
        if ms is not None and ms >= SENTENCE_MIN_MS:
            body, close = _peel(pieces[-1])
            if body and body[-1] not in _TERMINALS:
                pieces[-1] = body + "." + close
                changed = True

    if not changed:
        return text

    seps = [""] * n
    seps[0] = text[: matches[0].start()]
    for i in range(1, n):
        seps[i] = text[matches[i - 1].end(): matches[i].start()]
    # a token that vanished (standalone mark dropped) must not leave two spaces
    for i in range(1, n):
        if not pieces[i - 1]:
            seps[i] = ""

    out = [seps[0]]
    for i in range(n):
        out.append(pieces[i])
        if i + 1 < n:
            out.append(seps[i + 1])
    out.append(text[matches[-1].end():])
    return "".join(out)
