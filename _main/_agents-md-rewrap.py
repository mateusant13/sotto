"""Rewrap ONLY the CLOSED marker on AGENTS.md line 481 into three ~85-char lines.

Authorized by the coordinating agent (session-ab8603de-dc05-40ba-966c-f756dd2a5a4c),
who supplied the marker text itself in the earlier authorization. Word for word:
the script ASSERTS that the whitespace-normalised concatenation of the new lines is
byte-identical to the old line, so a dropped or added space fails the run instead of
shipping. Line endings are read and written as raw text (newline='') so the file
stays LF-only.
"""

from __future__ import annotations

import io
import os
import textwrap

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "AGENTS.md")
PATH = os.path.abspath(PATH)
WIDTH = 88          # including the bullet's 2-space indent
INDENT = "  "


def main():
    with io.open(PATH, encoding="utf-8", newline="") as fh:
        text = fh.read()
    lines = text.split("\n")

    i = next(n for n, l in enumerate(lines)
             if l.startswith("  **CLOSED 2026-10-08"))
    old = lines[i]
    cut = old.index("part:**") + len("part:**")
    marker, tail = old[:cut], old[cut:]
    assert marker.startswith(INDENT), "indent changed"
    assert tail.startswith(" words were split at CHUNK boundaries"), repr(tail)

    wrapped = textwrap.wrap(marker[len(INDENT):], width=WIDTH - len(INDENT),
                            initial_indent=INDENT, subsequent_indent=INDENT,
                            break_long_words=False, break_on_hyphens=False)
    wrapped[-1] = wrapped[-1] + tail

    # ── THE PROOF: nothing added, nothing removed, no extra space ────────────
    before = " ".join(old.split())
    after = " ".join(" ".join(wrapped).split())
    if before != after:
        raise SystemExit(f"REWRAP DRIFT\n  before={before!r}\n  after ={after!r}")

    lines[i:i + 1] = wrapped
    with io.open(PATH, "w", encoding="utf-8", newline="") as fh:
        fh.write("\n".join(lines))

    print(f"line {i+1}: {len(old)} chars -> {len(wrapped)} lines")
    for n, l in enumerate(wrapped):
        print(f"  {i+1+n}: [{len(l):3d}] {l}")
    print(f"WORDS UNCHANGED: {before == after} ({len(before.split())} words)")


if __name__ == "__main__":
    main()
