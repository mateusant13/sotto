"""Read the LIVE `_main/panel-state.json` and print the fields the brief asks for.

Writes UTF-8 to a file: printing Portuguese through the PowerShell pipe turns
`ã` into U+FFFD, so the console capture of this file is NOT evidence -- the file
is.

Usage: py -3 _main/live-panel-read.py --out _main/panel-live-read.txt
"""

from __future__ import annotations

import argparse
import io
import json
import os
import time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default=os.path.join("_main", "panel-state.json"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    st = os.stat(a.state)
    with io.open(a.state, "r", encoding="utf-8") as fh:
        d = json.load(fh)

    panel = d.get("panel") or {}
    live = panel.get("live") or {}
    scroll = live.get("scroll") or {}
    lines = live.get("lines") or []
    worker = d.get("worker") or {}
    ws = worker.get("workerStats") or {}
    fields = ws.get("fields") or {}
    vis = d.get("panelVisibility") or {}

    out = []
    w = out.append
    w("# _main/panel-state.json -- read at %s" % time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    w("file: %d bytes, mtime %s, sha256 pending" % (st.st_size,
      time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(st.st_mtime))))
    w("")
    w("sequence            : %r" % d.get("sequence"))
    w("writtenAt           : %r" % d.get("writtenAt"))
    w("producerPid         : %r" % d.get("producerPid"))
    w("schema              : %r" % d.get("schema"))
    w("reason              : %r" % d.get("reason"))
    w("staleAfterSeconds   : %r" % d.get("staleAfterSeconds"))
    w("namedState          : %r" % d.get("namedState"))
    w("")
    w("panel.url           : %r" % panel.get("url"))
    w("panel.live.hidden   : %r" % live.get("hidden"))
    w("panel.live.hint     : %r   <-- developer prose, if any" % live.get("hint"))
    w("panel.live.count    : %r   <-- number of <li> the panel holds" % live.get("count"))
    w("panel.live.provisionalCount : %r" % live.get("provisionalCount"))
    w("panel.live.scroll   : top=%r height=%r client=%r atBottom=%r overflowing=%r"
      % (scroll.get("top"), scroll.get("height"), scroll.get("client"),
         scroll.get("atBottom"), scroll.get("overflowing")))
    w("panel.placeholder.hidden : %r" % (panel.get("placeholder") or {}).get("hidden"))
    w("")
    w("--- the lines the panel is painting (%d) ---" % len(lines))
    idx_field = None
    for ln in lines:
        for k in ln:
            if "index" in k.lower() or k.lower() in ("i", "n", "line"):
                idx_field = k
    w("line object keys        : %r" % (sorted(lines[0].keys()) if lines else None))
    w("ANY line-index field?   : %r" % (idx_field,))
    w("lines with latest=true  : %d" % sum(1 for ln in lines if ln.get("latest")))
    w("lines with provisional  : %d" % sum(1 for ln in lines if ln.get("provisional")))
    for i, ln in enumerate(lines):
        if i < 3 or i >= len(lines) - 3:
            w("  [%3d] latest=%-5r prov=%-5r %s"
              % (i, ln.get("latest"), ln.get("provisional"), ascii(ln.get("text"))))
        elif i == 3:
            w("  ...")
    w("")
    w("--- worker ---")
    w("state               : %r" % worker.get("state"))
    w("capturing           : %r" % worker.get("capturing"))
    w("childPid            : %r" % worker.get("childPid"))
    w("spawns/restarts/deaths : %r/%r/%r" % (worker.get("spawns"), worker.get("restarts"),
                                             worker.get("deaths")))
    w("captions            : %r" % worker.get("captions"))
    w("statuses            : %r" % worker.get("statuses"))
    w("malformed           : %r" % worker.get("malformed"))
    w("noAudio             : %r" % worker.get("noAudio"))
    w("noAudioEvidence     : %r" % worker.get("noAudioEvidence"))
    w("device.device       : %r" % (worker.get("device") or {}).get("device"))
    w("device.api          : %r" % (worker.get("device") or {}).get("api"))
    w("device.peak         : %r" % (worker.get("device") or {}).get("peak"))
    w("workerStats.tag     : %r" % ws.get("tag"))
    for k in ("blocks", "block_samples", "nonzero_blocks", "peak", "rms", "gain_db",
              "gain_min_db", "gain_max_db", "peak_out", "held_blocks", "speech_blocks",
              "agc", "chunks", "captions", "tokens", "frames", "blanks", "blank_frac",
              "empty_chunks", "vad_gated_chunks", "music_gated_chunks", "gate_kept",
              "gate", "queue_drops", "reruns", "audio_s", "infer_wall_s"):
        if k in fields:
            w("  %-18s: %r" % (k, fields[k]))
    w("")
    w("--- visibility ---")
    w("shell.visible       : %r" % (d.get("shell") or {}).get("visible"))
    w("shell.reloadCount   : %r" % (d.get("shell") or {}).get("reloadCount"))
    w("panelVisibility     : visible=%r reason=%r transitions=%r writes=%r errors=%r"
      % (vis.get("visible"), vis.get("reason"), vis.get("transitions"),
         vis.get("writes"), vis.get("errors")))

    with io.open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(out) + "\n")
    print("wrote %s (%d lines)" % (a.out, len(out)))


if __name__ == "__main__":
    main()
