"""Show what the FIXED live path actually emitted, and hunt for remaining splits."""

from __future__ import annotations

import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    with io.open(os.path.join(HERE, "_live-seam-probe.json"), encoding="utf-8") as fh:
        d = json.load(fh)
    print("=== the LIVE path captions, in order (final=true = the closed line) ===")
    for i, e in enumerate(d["captions"]):
        print("%2d final=%-5s %r" % (i, e.get("final"), e.get("text")))

    print()
    print("=== every push, with the seam decision ===")
    for i, p in enumerate(d["pushes"]):
        if not p["text"]:
            continue
        seam = "GLUE" if p["continues"] else "space"
        print("%2d %-5s %r" % (i, seam, p["text"]))


if __name__ == "__main__":
    main()
