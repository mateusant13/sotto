# WHY THE ORCHESTRATOR'S LATENCY (median 2537s) AND MINE (median 87s) DISAGREE.
# 146 sends vs 121 deliveries. Any index-pairing DRIFTS by 25 slots. This
# enumerates every plausible pairing rule and asks which one REPRODUCES the
# brief's numbers (POP=121, min 979s, median 2537s, max 6019s).
import re, statistics as st
from datetime import datetime

TS = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.*)$')
sends, dels = [], []
for raw in open(r'H:\sotto\_moved\aireplay\_main\heartbeat.log', encoding='utf-8', errors='replace'):
    m = TS.match(raw.rstrip('\n'))
    if not m:
        continue
    ts = datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
    b = m.group(2)
    if re.search(r'WAKE sending ->', b):
        sends.append(ts)
    elif re.search(r'WAKE delivered rc=', b):
        dels.append(ts)

def show(name, xs):
    if not xs:
        print('  %-26s POP=0' % name); return
    print('  %-26s POP=%d min=%.0fs median=%.0fs max=%.0fs' % (
        name, len(xs), min(xs), st.median(xs), max(xs)))

print('POP sends=%d deliveries=%d  drift=%d' % (len(sends), len(dels), len(sends) - len(dels)))
print('TARGET from the brief: POP=121 min=979s median=2537s max=6019s')
print()

# P1: NAIVE index pair send[i] -> delivery[i]. Ignores the drift entirely.
show('P1 index send[i]->del[i]', [(dels[i] - sends[i]).total_seconds() for i in range(len(dels))])

# P2: index pair over the LAST 121 sends (tail-aligned).
show('P2 index tail-121', [(dels[i] - sends[-(len(dels) - i)]).total_seconds() for i in range(len(dels))])

# P3: cumulative sum of gaps (what a "queue drain time" fudge produces).
show('P3 cumsum of gaps', [sum((dels[i] - dels[i-1]).total_seconds() for i in range(1, j+1)) for j in range(len(dels))])

# P4: FIRST delivery at-or-after each send, no overtake filter (what I measured)
p4 = []
di = 0
for s in sends:
    while di < len(dels) and dels[di] < s:
        di += 1
    if di < len(dels):
        p4.append((dels[di] - s).total_seconds())
show('P4 first-delivery-at-or-after', p4)

# P5: the sum of ALL gap time up to each delivery, counted as one series.
# This is the "how long from window start did delivery N take" reading.
show('P5 delivery-minus-first-send',
     [(d - sends[0]).total_seconds() for d in dels])

print()
print('READING: if P1/P2/P5 reproduce median~2537s, the brief\'s latency column')
print('is an INDEX-OR-CUMULATIVE artifact of the 25-slot drift, not a per-wake')
print('latency. A gate must assert the column that means "how long the owner')
print('waited for THIS wake", which is P4 -- and P4 must be printed too, so the')
print('two readings are never confused again.')