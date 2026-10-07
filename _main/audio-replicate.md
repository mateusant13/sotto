# Audio: frequency replicated on 2 independent captures, and the other 4 endpoints answered

The previous pass failed twice and I am recording why before the result.

FAILURE 1 - the analyser was broken. My rewritten Goertzel returned 0.000000 in every bin.
FAILURE 2 - the patch lacked endpoint selection, so all five runs hit eps[0].

BOTH FIXED, and the analyser was self-tested BEFORE being used on real data, with a positive
and a negative control:
  synthetic 1 kHz, scanned 900-1100 Hz  -> peak_bin=1000 Hz, g1000=0.249977, g900=0.000000
  synthetic 7 kHz, scanned 6500-7500 Hz  -> peak_bin=7000 Hz, g1000=0.000004, g900=0.000000
An analyser that finds 7000 Hz where there is 7 kHz, and finds almost nothing at 1000 Hz there,
is not one that will agree with me by accident.

Binary tap-both.exe carries BOTH patches: the allpcm accumulator and the endpoint index.
Recipe: g++ -std=c++17 -O2 -DAUDIO_TAP_SELFTEST -I <src> tap_both.cpp -o tap-both.exe -lole32 -loleaut32

WINDOW: 15:22:48. POPULATION: 3 captures on the default endpoint plus 1 per other endpoint.

TONE PLAYING, 3 captures:
  cap 1  frames=28960 1.810s  peak=0.500000  peak_bin=1000 Hz  g1000=0.249977  g900=0.000000
  cap 2  frames=28800 1.800s  peak=0.500000  peak_bin=1000 Hz  g1000=0.249977  g900=0.000000
  cap 3  frames=28960 1.810s  peak=0.362915  peak_bin= 969 Hz  g1000=0.000107  g900=0.000212

caps 1 and 2 are the real ones: exactly 1000 Hz, exactly 0.500000, and every decoy bin zero.
cap 3 caught the tail, where the tone had stopped and only ambient material remained -- and it
reports exactly that, a weak broadband 969 Hz bin. The instrument discriminated rather than
repeating a green.

THE OTHER FOUR ENDPOINTS, driven with the same tone:
  ep1 VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)  VERDICT=no  wav EMPTY (0 samples)
  ep2 Speakers (NVIDIA Broadcast)                   VERDICT=no  wav EMPTY (0 samples)
  ep3 AG251F1WG2 (NVIDIA High Definition Audio)     VERDICT=no  wav EMPTY (0 samples)
  ep4 Alto-falantes (HyperX Quadcast)                VERDICT=no  wav EMPTY (0 samples)

This answers the question I had been treating as an open debt. The tone does not REACH those
four endpoints. They are not failing to report audio that is there; there is no audio there. A
loopback tap on a device nothing plays into correctly yields silence. Demanding that they
respond was my premise, and the premise was wrong, not the instrument.

STILL NOT ESTABLISHED:
- 2 clean captures, not more. Population is still small.
- The endpoint ordering is NOT stable between runs: at 15:14 VoiceMeeter Input was eps[0],
  at 15:22 CABLE Input was eps[0]. Anything addressed by index is addressing a moving target.
- Still a selftest build. main.cpp does not call LoopbackTap.
