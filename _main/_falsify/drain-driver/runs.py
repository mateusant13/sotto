"""THE RUN RECORDS: every worker run the live shell logged, with its own numbers.

INSTRUMENT: a from-scratch parser over `H:/sotto/_main/webview-run.log`. It does
NOT import, run or reuse `_main/load-shedding-oracle.py` or
`_main/live-queue-drain-oracle.py` (the author's instruments). It reads the
shell's own log lines and rebuilds the per-run records from them.

WHAT A "RUN" IS HERE. The shell logs `BRIDGE_SPAWNED pid=...` when it starts a
worker and `BRIDGE_EXIT pid=... rc=... stderr_tail=[...]` when that worker dies.
The `stderr_tail` is the worker's OWN last three stderr lines -- and the worker
publishes its per-run counters there (`WORKER_STATS tag=final`) and the
background engine's own summary (`REDUX_SWITCH_STOP`). Those two lines are the
whole evidence surface for the drain question that survives in the shell's log.

THE FIELDS THAT MATTER (and where each one comes from):

  blocks / resampled_samples   the tap's audio: how much the worker SAW
  chunks / captions            the STREAMING engine: how much it decoded
  redux_held_s                 audio STILL WAITING for the background engine
  redux_kicks / redux_segments background passes started / completed
  redux_captions               lines the background (parakeet) engine produced
  queue_drops / queue_evicted  audio the LIVE queue threw away
  left_s (REDUX_SWITCH_STOP)   audio still waiting at the moment of the stop
  failures / deferred          background passes that failed / were deferred

Read-only. It writes nothing but stdout.
"""
from __future__ import annotations

import json
import re

LOG = r"H:\sotto\_main\webview-run.log"

TS_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) sotto: (\S+)')
SPAWN_RE = re.compile(r'BRIDGE_SPAWNED pid=(\d+)')
EXIT_RE = re.compile(r'BRIDGE_EXIT pid=(\d+) rc=(-?\d+) spawns=(\d+) captions=(\d+) '
                     r'statuses=(\d+) malformed=(\d+) stderr_tail=(.*)$')
CAP_RE = re.compile(r'BRIDGE_CAPTION_SENT delivered=(\S+) text=(".*?"|\S*)\s*$')


def kv(text):
    """`key=value` -> dict. Values may be quoted or bare; quoted wins."""
    out = {}
    for m in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)=("[^"]*"|[^\s]*)', text):
        out[m.group(1)] = m.group(2).strip('"')
    return out


def parse_stderr_tail(raw):
    """The `stderr_tail=[...]` JSON array -- tolerant of a truncated array."""
    raw = raw.strip()
    if not raw.startswith('['):
        return []
    try:
        return json.loads(raw)
    except Exception:
        # The shell truncates the tail to 3 lines; a long line can leave the
        # JSON unterminated when the log itself was cut. Recover the quoted
        # strings by hand instead of dropping the record.
        out = []
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', raw):
            try:
                out.append(json.loads('"%s"' % m.group(1)))
            except Exception:
                pass
        return out


def load(log_path=LOG):
    """-> (runs, captions) where `runs` is one dict per worker run."""
    spawns = {}          # pid -> (ts, lineno)
    runs = []
    captions = []        # (ts, lineno, text)

    with open(log_path, 'r', encoding='utf-8', errors='replace') as fh:
        for lineno, line in enumerate(fh, 1):
            m = TS_RE.match(line)
            if not m:
                continue
            ts, kind = m.group(1), m.group(2)
            if kind == 'BRIDGE_SPAWNED':
                sm = SPAWN_RE.search(line)
                if sm:
                    spawns[sm.group(1)] = (ts, lineno)
            elif kind == 'BRIDGE_EXIT':
                em = EXIT_RE.search(line)
                if not em:
                    continue
                pid, rc, spawns_n, caps = em.group(1), int(em.group(2)), em.group(3), em.group(4)
                tail = parse_stderr_tail(em.group(7))
                rec = {
                    'pid': pid,
                    'rc': rc,
                    'ts_exit': ts,
                    'lineno': lineno,
                    'spawn_ts': spawns.get(pid, (None, None))[0],
                    'spawn_lineno': spawns.get(pid, (None, None))[1],
                    'captions_bridge': int(caps),
                    'tail': tail,
                }
                ws = [t for t in tail if t.startswith('WORKER_STATS')]
                sw = [t for t in tail if t.startswith('REDUX_SWITCH_STOP')]
                rec['stats'] = kv(ws[-1]) if ws else {}
                rec['stop'] = kv(sw[-1]) if sw else {}
                runs.append(rec)
            elif kind == 'BRIDGE_CAPTION_SENT':
                cm = CAP_RE.search(line)
                if cm:
                    captions.append((ts, lineno, cm.group(2).strip('"')))

    return runs, captions


if __name__ == '__main__':
    runs, caps = load()
    print("runs:", len(runs), "caption lines:", len(caps))
    print("runs with a WORKER_STATS final:", sum(1 for r in runs if r['stats']))
    print("runs with a REDUX_SWITCH_STOP:", sum(1 for r in runs if r['stop']))
    print("runs with redux_mode field:", sum(1 for r in runs if 'redux_mode' in r['stats']))
