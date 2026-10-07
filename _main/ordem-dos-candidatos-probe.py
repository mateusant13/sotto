"""Order probe: is the WASAPI rung's live meter the order the ladder actually walks?

Reads IAudioMeterInformation for EVERY active render endpoint TWICE (before and
after building the candidate list) and prints the list `device_candidates()`
returns, with each candidate's rung and the meter peak recorded at selection.

Usage:  python _main/ordem-dos-candidatos-probe.py [tag]
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(os.path.dirname(HERE), "worker")
sys.path.insert(0, WORKER)

import wasapi_loopback  # noqa: E402

tag = sys.argv[1] if len(sys.argv) > 1 else "run"


def read_meters(label):
    t0 = time.time()
    eps = wasapi_loopback.list_render_endpoints(meter_ms=0.4)
    print(f"[{tag}] {label} t={t0:.3f} n={len(eps)}")
    for i, e in enumerate(eps):
        print(f"    #{i} peak={e['meter_peak']!r} default={e['is_default']} "
              f"name={e['name']!r}")
    return eps


print(f"[{tag}] pid={os.getpid()}")
before = read_meters("BEFORE (list as list_render_endpoints returns it)")

import sotto_worker  # noqa: E402

cands = sotto_worker.device_candidates()
print(f"[{tag}] device_candidates() n={len(cands)}")
for i, d in enumerate(cands):
    print(f"    #{i} rung={d.get('rung')!r} idx={d.get('index')!r} "
          f"meter={d.get('meter_peak')!r} name={d['name']!r} why={d.get('rung_why')!r}")

after = read_meters("AFTER (second read of the same endpoints)")

print(f"[{tag}] SUMMARY first_candidate={cands[0]['name']!r} "
      f"rung={cands[0].get('rung')!r} meter_at_selection={cands[0].get('meter_peak')!r}")
