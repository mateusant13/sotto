# LANE16: the OUTCOME CENSUS that ARM C1 conflates into "task cadence".
# C1 counts lines matching a phrasing regex and calls the space between them
# "cadence". MEASURED: TASK-FIRE lines fire every 180 s without exception
# (POP=160, median 180 s, max 186 s) -- the task is perfectly healthy -- while
# C1 reports a 12-min gap. The gap is a VOCABULARY artifact: 26 passes end in
# `WAKE QUEUE FAILED`, which the C1 regex does not match, so a fire the owner
# got NOTHING from reads as silence.
import re
from collections import Counter
from datetime import datetime

PAT = re.compile(r'^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (.*)$')
C1 = re.compile(r'WAKE (enqueued rc=0|refused rc=2|queued|sending|no-op|FAILED)|ABORT:')

fires, outcomes = [], []
for raw in open(r'H:\sotto\_moved\aireplay\_main\heartbeat.log', encoding='utf-8', errors='replace'):
    m = PAT.match(raw.rstrip('\n'))
    if not m:
        continue
    ts = datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')
    b = m.group(2)
    if b.startswith('TASK-FIRE'):
        fires.append(ts)
    if C1.search(b):
        outcomes.append((ts, b))

def cls(b):
    if 'WAKE sending ->' in b:            return 'SENT (wake dispatched)'
    if 'WAKE delivered rc=' in b:         return 'DELIVERED'
    if 'WAKE QUEUE FAILED' in b:          return 'QUEUE-FAILED (owner got nothing)'
    if 'WAKE queued' in b:                return 'QUEUED (not yet delivered)'
    if 'WAKE refused' in b:               return 'REFUSED (already queued)'
    if 'WAKE no-op' in b:                 return 'NO-OP (session already awake)'
    if 'WAKE rc=' in b:                   return 'UNKNOWN-KIND'
    if 'ABORT:' in b:                     return 'ABORT'
    return 'OTHER'

print('POP TASK-FIRE lines      = %d' % len(fires))
print('POP lines matching C1    = %d' % len(outcomes))
c = Counter(cls(b) for _, b in outcomes)
for k, v in c.most_common():
    print('  %-34s %d' % (k, v))

lost = sum(v for k, v in c.items() if k == 'QUEUE-FAILED (owner got nothing)')
print()
print('FIRES WITH NO WAKE SENT  = %d of %d = %.1f%% of the C1-visible outcomes'
      % (lost, len(outcomes), 100.0 * lost / max(1, len(outcomes))))
print('... but against the DENOMINATOR that matters -- every TASK-FIRE:')
print('   %d of %d fires produced a QUEUE-FAILED = %.1f%% delivery loss'
      % (lost, len(fires), 100.0 * lost / max(1, len(fires))))

# Reason breakdown for the losses.
print()
print('QUEUE-FAILED reasons (POP, whole log):')
r = Counter()
for raw in open(r'H:\sotto\_moved\aireplay\_main\heartbeat.log', encoding='utf-8', errors='replace'):
    m = re.search(r'WAKE QUEUE FAILED rc=\d+ reason=([a-z-]+)', raw)
    if m:
        r[m.group(1)] += 1
for k, v in r.most_common():
    print('  %-28s %d' % (k, v))