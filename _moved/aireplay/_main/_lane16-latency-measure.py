# LANE16 measurement: BOTH columns over heartbeat.log.
#   GAP     = delivery -> delivery   (what the current gate's C1 half-metrics)
#   LATENCY = send     -> delivery   (the owner's requirement)
# Pairing rule matters: 146 sends vs 121 deliveries, so an index-pair would
# DRIFT. Each send is paired with the FIRST delivery at-or-after it; a send
# followed by another send (or a QUEUE FAILED) is UNFULFILLED, not slow.
import re, statistics as st
from datetime import datetime

TS = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.*)$')

def parse(path):
    sends, dels, other = [], [], []
    for raw in open(path, encoding='utf-8', errors='replace'):
        m = TS.match(raw.rstrip('\n'))
        if not m:
            continue
        ts = datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
        body = m.group(2)
        if re.search(r'WAKE sending ->', body):
            sends.append(ts)
        elif re.search(r'WAKE delivered rc=', body):
            dels.append(ts)
        elif re.search(r'WAKE (queued|refused|no-op|enqueued|already queued)', body):
            other.append(ts)
    return sends, dels, other

sends, dels, other = parse(r'H:\sotto\_moved\aireplay\_main\heartbeat.log')
print('POP sends=%d deliveries=%d other-outcomes=%d' % (len(sends), len(dels), len(other)))

# --- GAP: delivery -> next delivery
gaps = [(dels[i] - dels[i-1]).total_seconds() for i in range(1, len(dels))]
# --- LATENCY: send -> FIRST delivery at-or-after it, same-index pair broken
lat, unfulfilled, spans = [], 0, 0
di = 0
for s in sends:
    while di < len(dels) and dels[di] < s:
        di += 1
    if di >= len(dels):
        unfulfilled += 1
        continue
    nxt_send = next((x for x in sends if x > s), None)
    if nxt_send is not None and dels[di] > nxt_send:
        unfulfilled += 1          # next send overtook this one: NOT a slow delivery
        continue
    lat.append((dels[di] - s).total_seconds())
    spans += 1

def stat(name, xs):
    if not xs:
        print('%-8s POP=0' % name); return
    under = sum(1 for x in xs if x < 180)
    print('%-8s POP=%d min=%.0fs median=%.0fs (%.1f min) max=%.0fs (%.1f min) '
          'p90=%.0fs under180s=%d/%d (%.0f%%)' % (
        name, len(xs), min(xs), st.median(xs), st.median(xs)/60.0, max(xs),
        max(xs)/60.0, sorted(xs)[int(len(xs)*0.9)-1], under, len(xs),
        100.0*under/len(xs)))

stat('GAP', gaps)
stat('LATENCY', lat)
print('unfulfilled sends=%d (no delivery before the next send)' % unfulfilled)
print('window first=%s last=%s' % (
    min(sends + dels).strftime('%Y-%m-%d %H:%M:%S'),
    max(sends + dels).strftime('%Y-%m-%d %H:%M:%S')))