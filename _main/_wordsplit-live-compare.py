"""Compare the three live file-tap arms: DEFAULT vs explicit --meter-hz 0 vs 10.

The claim the owner's decision rests on: with the SHIPPED DEFAULT, a live run
adds ZERO meter events and ZERO bytes, and the captions and the WORKER_STATS
stderr tick are the same as an explicit `--meter-hz 0` run.
"""

from __future__ import annotations

import io
import json
import os
import re

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_wordsplit-live-")


def rows(tag):
    with io.open(BASE + tag + ".jsonl", encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip().startswith("{")]


def captions(tag):
    return [(x["text"], {k: v for k, v in x.items() if k != "text"})
            for x in rows(tag) if x.get("type") == "caption"]


def stderr(tag):
    with io.open(BASE + tag + ".err", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    stats = []
    for line in text.splitlines():
        if line.startswith("WORKER_STATS"):
            d = dict(re.findall(r"(\w+)=([^ ]+)", line))
            stats.append((d["tag"], d["blocks"], d["peak"], d["rms"],
                          d["captions"], d["chunks"]))
    return stats, [l for l in text.splitlines() if l.startswith("meter")]


def main():
    res = {}
    for tag in ("default", "off0", "on10"):
        r = rows(tag)
        m = [x for x in r if x.get("type") == "meter"]
        st, ml = stderr(tag)
        res[tag] = {
            "meters": len(m),
            "bytes": os.path.getsize(BASE + tag + ".jsonl"),
            "caps": captions(tag),
            "stats": st,
            "types": sorted({x.get("type") for x in r}),
            "meter_line": ml,
        }
        print(f"{tag:8s} meter={len(m):3d}  stdout_bytes={res[tag]['bytes']:5d}  "
              f"captions={len(res[tag]['caps']):2d}")
        print(f"         stderr: {ml}")

    d, o, n = res["default"], res["off0"], res["on10"]
    print()
    print("DEFAULT vs explicit --meter-hz 0")
    print("  meter events            :", d["meters"], "vs", o["meters"])
    print("  captions byte-identical :", d["caps"] == o["caps"])
    print("  WORKER_STATS identical  :", d["stats"] == o["stats"])
    print("  stdout line-type census :", d["types"], "vs", o["types"],
          "equal:", d["types"] == o["types"])
    print("  stdout bytes            :", d["bytes"], "vs", o["bytes"],
          "delta:", d["bytes"] - o["bytes"])
    print()
    print("explicit --meter-hz 10 still turns it ON")
    print("  meter events            :", n["meters"])
    print("  captions identical to DEFAULT:", n["caps"] == d["caps"])
    print("  WORKER_STATS identical to DEFAULT:", n["stats"] == d["stats"])
    print("  stdout bytes            :", n["bytes"], "(+%d over DEFAULT)" % (n["bytes"] - d["bytes"]))


if __name__ == "__main__":
    main()
