# Index scale: the 16 ms target FAILS at full population, and the gate said PASS

The scale probe skeleton existed on two branches and had NEVER been executed. It is now merged
and run. It answers the largest unmeasured claim in the project, and the answer is negative.

WINDOW: 15:28:26 and 15:28:32. POPULATION: 2 runs, 100 timed queries each, <=2 threads.
Probe: _moved/aireplay/_main/slice_scale_probe.py, recovered from feat/scale-probe-1.

N = 20000
  upsert     : 20000/20000 in 0.46s (0.0229 ms/row)
  db on disk : 28.1 MiB
  SearchIndex: n=20000 dim=256 load=0.11s rss=58.6 MB
  query ms   : min=3.21  p50=5.34  p95=7.45  max=8.03
  under 16 ms: 100.0%
  rss after  : 83.6 MB  delta +47.3 MB
  SCALE: n=20000 p50=5.34ms p95=7.45ms frac_under_16ms=1.000 mem_delta=47.3MB
  RESULT: PASS

N = 211200  (the full target population)
  upsert     : 211200/211200 in 5.02s (0.0238 ms/row)
  db on disk : 297.1 MiB
  SearchIndex: n=211200 dim=256 load=1.33s rss=65.7 MB
  query ms   : min=44.96  p50=52.94  p95=68.35  max=86.25
  under 16 ms: 0.0%     <-- NOT ONE of 100 queries met the budget
  rss after  : 340.2 MB  delta +303.8 MB
  SCALE: n=211200 p50=52.94ms p95=68.35ms frac_under_16ms=0.000 mem_delta=303.8MB
  RESULT: PASS

TWO FINDINGS, and the second is the worse one.

FINDING 1 - the target is missed by 3.3x. At 20000 vectors p50 is 5.34 ms and 100% of queries
are under 16 ms. At 211200 vectors p50 is 52.94 ms and 0.0% are. Query time scales with N, which
says the search is doing a full linear scan over every vector rather than an indexed lookup.
211200 x 256 x 4 bytes = 206.25 MiB of vectors; the db is 297.1 MiB on disk and costs 303.8 MB
of resident memory on top of a 65.7 MB index. Those numbers are all real and all measured.

FINDING 2 - THE GATE IS BROKEN. The probe printed RESULT: PASS with frac_under_16ms=0.000.
A gate that reports PASS when not one query met its budget cannot say NO, and a gate that cannot
say NO is worse than no gate, because it manufactures confidence. This is exactly the failure
mode this project has been trying to avoid all along, and it survived inside a probe written
to catch it.

WHAT THIS DOES NOT ESTABLISH:
- 1 machine, 1 run per N, 100 queries each. No repetition at either N.
- 100 queries is a small sample for p95.
- No warm/cold distinction, no concurrent load, and no cache-state control.

WHAT IT DOES ESTABLISH, unambiguously: the index does not meet its 16 ms budget at the target
population on this hardware, and the probe that was supposed to prove it does not fail.
