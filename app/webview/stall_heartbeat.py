"""A 1 Hz heartbeat from a process of its own.

WHY A PROCESS AND NOT A THREAD (MEASURED 2026-11-26). The owner's session (pid
103760) went silent twice, and the two silences looked like a caption bug:

    05:42:22.751 -> 05:44:14.916   (112.2 s, no line at all)
    05:44:51.524 -> 05:45:58.627   ( 67.1 s, no line at all)

A thread inside the shell could not have told us the truth: Python has one GIL,
so a thread that stalls with the rest of the process looks exactly like a host
that stopped scheduling — the same silence, written by the same writer. The
worker's OWN clock settled it: `WORKER_COST wall_s=112.9` and the worker-written
`history/audio/gaps.jsonl` records 111.241 s / 100.824 s inside those exact
windows. Two processes, two independent clocks, one window: the stall is
cross-process, not the shell's GIL.

That was decidable only because the worker happens to write gaps. The next
stall may happen with no worker running, and then there is nothing to compare
against. This module is the third witness: a separate OS process, no pipes to
the shell's log, its own file, appending one line per second.

WHAT IT PROVES, in one line: a hole in this file is a hole in the MACHINE (or in
this process's scheduling); a continuous file while the shell is silent is the
shell's own GIL, and the two are never confused again.

Lifecycle: the shell starts it and owns its stdin. When the shell dies the pipe
closes, the reader thread sees EOF and the child exits by itself — no orphan, no
kill by name, and no way for a stale heartbeat to outlive the app that started
it.

Pure by design: `record`, `scan` and `tail_gaps` take data and return data; the
oracle owns the schedule and the fixtures.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time

#: One tick a second: cheap enough to ignore (one `write` + one `flush`), fine
#: enough to resolve a stall the size of the ones measured (67 s and 112 s).
TICK_S = 1.0

#: A hole longer than one missed tick plus scheduling slack. Below this a 1 Hz
#: writer on a busy box would report noise instead of a stall.
GAP_S = 2.5

#: The three fields the reader relies on. `t` is wall time (compare with log
#: stamps), `m` is `perf_counter` (survives a wall-clock correction), `n` is the
#: tick number (proves the writer kept counting through a slow patch).
KEYS = ('n', 't', 'm')


def record(n, wall_s, mono_s):
    """One heartbeat line, no trailing newline."""
    return json.dumps({'n': int(n), 't': round(float(wall_s), 3),
                       'm': round(float(mono_s), 3)},
                      separators=(',', ':'), sort_keys=True)


def scan(rows, gap_s=GAP_S):
    """Every hole in `rows` longer than `gap_s`, as `[{i, from, to, gap_s, n0, n1}]`.

    `rows` is an iterable of parsed records (dicts). A malformed row is skipped,
    never fatal: half a line from a killed writer must not blind the reader.
    """
    holes = []
    prev = None
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        try:
            t = float(row['t'])
        except (KeyError, TypeError, ValueError):
            continue
        if prev is not None:
            gap = t - prev['t']
            if gap > gap_s:
                holes.append({'i': i, 'from': prev['t'], 'to': t,
                              'gap_s': round(gap, 3),
                              'n0': prev.get('n'), 'n1': row.get('n')})
        prev = {'t': t, 'n': row.get('n')}
    return holes


def tail_gaps(path, gap_s=GAP_S, max_bytes=65536):
    """The holes in the last `max_bytes` of a heartbeat file.

    Returns `(holes, span)` where `span` is `(first_t, last_t, count)`; an
    unreadable or empty file returns `([], None)` — the caller MUST call that
    `no-heartbeat` and never `clean`. A reader that treats absence as health is
    the same defect this file exists to catch.
    """
    try:
        size = os.path.getsize(path)
    except OSError:
        return [], None
    try:
        with open(path, 'rb') as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()             # drop the half line at the cut
            raw = fh.read()
    except OSError:
        return [], None
    rows = []
    for line in raw.decode('utf-8', 'replace').splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    if not rows:
        return [], None
    holes = scan(rows, gap_s)
    span = (float(rows[0].get('t', 0.0)), float(rows[-1].get('t', 0.0)), len(rows))
    return holes, span


def _watch_stdin(stop):
    """Set `stop` when the parent closes our stdin (i.e. the shell is gone)."""
    try:
        while sys.stdin.buffer.read(1):
            pass
    except Exception:                     # noqa: BLE001
        pass
    stop.set()


def main(argv):
    path = None
    tick = TICK_S
    args = list(argv)
    while args:
        a = args.pop(0)
        if a == '--path' and args:
            path = args.pop(0)
        elif a == '--tick' and args:
            tick = float(args.pop(0))
    if not path:
        sys.stderr.write('usage: stall_heartbeat.py --path <file> [--tick s]\n')
        return 2
    stop = threading.Event()
    threading.Thread(target=_watch_stdin, args=(stop,), daemon=True,
                     name='heartbeat-stdin').start()
    d = os.path.dirname(path)
    if d:
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
    n = 0
    with open(path, 'a', encoding='utf-8', newline='\n') as fh:
        while not stop.is_set():
            n += 1
            fh.write(record(n, time.time(), time.perf_counter()) + '\n')
            fh.flush()
            stop.wait(max(0.05, tick))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
