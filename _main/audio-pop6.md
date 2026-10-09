# Audio: frequency at population 6, 6/6 clean

The previous pass got population 2 because the 4-second tone ran out across a batch of
captures. This pass starts a FRESH SoundPlayer for every capture, so each one is captured
while the tone is genuinely playing.

WINDOW: 15:25:18. POPULATION: 6 captures, 6 attempts, 1 endpoint, 1200 ms each.
Analyser: the one self-tested against synthetic 1 kHz and 7 kHz controls before use.

  cap 1  peak=0.500000  peak_bin=1000 Hz
  cap 2  peak=0.500000  peak_bin=1000 Hz
  cap 3  peak=0.500000  peak_bin=1000 Hz
  cap 4  peak=0.500000  peak_bin=1000 Hz
  cap 5  peak=0.500000  peak_bin=1000 Hz
  cap 6  peak=0.500000  peak_bin=1000 Hz

  6 of 6 at exactly 1000 Hz, 6 of 6 at exactly 0.500000, 0 discarded.

Both axes of the chain now hold across every run with no exceptions to explain away:
  generated 0.5 amplitude  -> measured 0.500000   (6/6)
  generated 1000 Hz        -> measured 1000 Hz    (6/6, 1 Hz bins, decoy bins zero)

WHAT IS STILL NOT MEASURED, unchanged by this:
- 1 endpoint. The other four are genuinely silent because nothing plays into them.
- Endpoint ORDERING is unstable between runs, so nothing may be addressed by index.
- Still a selftest build. main.cpp never calls LoopbackTap, so none of this is reachable
  from the shipping capture binary.
- The RRF, crash-recovery and index-scale probes have still never been executed.
