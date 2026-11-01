"""DUMP: every run that carried the background-engine counters, side by side."""
from __future__ import annotations

import sys

sys.path.insert(0, r"H:\sotto\_falsify_drain")
from runs import load  # noqa: E402


def main():
    runs, caps = load()
    redux = [r for r in runs if 'redux_mode' in r['stats']]
    print("runs with background-engine counters: %d of %d" % (len(redux), len(runs)))
    print()
    hdr = ("#", "spawn", "exit", "pid", "rc", "mode", "sw", "kicks", "segs", "caps",
           "held_s", "defer", "left_s", "fail", "spool", "chunks", "cap_strm",
           "blocks", "audio_s", "qdrop", "qevict")
    print("\t".join(hdr))
    for i, r in enumerate(redux, 1):
        s = r['stats']
        st = r['stop']
        print("\t".join(str(x) for x in (
            i, (r['spawn_ts'] or '?')[11:], r['ts_exit'][11:], r['pid'], r['rc'],
            s.get('redux_mode'), s.get('redux_switches'), s.get('redux_kicks'),
            s.get('redux_segments'), s.get('redux_captions'), s.get('redux_held_s'),
            s.get('redux_deferred'), st.get('left_s'), st.get('failures'),
            st.get('spooled'), s.get('chunks'), s.get('captions'),
            s.get('blocks'), s.get('audio_s'), s.get('queue_drops'),
            s.get('queue_evicted'))))


if __name__ == '__main__':
    main()
