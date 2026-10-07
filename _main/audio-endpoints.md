# Audio tap: all five endpoints, and the negative arm actually discriminates

The selftest hardcodes eps[0], so I made a local copy that takes the endpoint index as argv[2].
Nothing in the repo was changed to get this measurement.

Binary tap-all.exe, built rc=0 with the same recipe:
  g++ -std=c++17 -O2 -DAUDIO_TAP_SELFTEST -I <src> -I <tmp> tap_sel.cpp -o tap-all.exe -lole32 -loleaut32

WINDOW: one pass, this turn. POPULATION: 5 endpoints, 1 run each, 1200 ms window.

  [0] CABLE Input (VB-Audio Virtual Cable)          OPEN=ok VERDICT=ok  peak=0.155906 samples=19200 rc=0
  [1] VoiceMeeter Input (VB-Audio VoiceMeeter VAIO) OPEN=ok VERDICT=no  peak=0.000000 samples=0     rc=0
  [2] Speakers (NVIDIA Broadcast)                   OPEN=ok VERDICT=no  peak=0.000000 samples=0     rc=0
  [3] AG251F1WG2 (NVIDIA High Definition Audio)     OPEN=ok VERDICT=no  peak=0.000000 samples=0     rc=0
  [4] Alto-falantes (HyperX Quadcast)                OPEN=ok VERDICT=no  peak=0.000000 samples=0     rc=0

19200 samples = 1200 ms x 16000 Hz, exactly. The endpoint that carries audio lands on the
contract rate with no residual.

WHY THIS IS THE MOST USEFUL AUDIO MEASUREMENT SO FAR.
Every one of the five opened successfully. Four of the five carry nothing, and the tap SAYS SO
with VERDICT=no rather than reporting success on silence. That is the negative arm working: the
instrument distinguishes "it opened" from "it carried audio", which is exactly what the comment
at the top of audio_tap.cpp claimed it was built to do. A gate that passes on silence would
have printed ok five times; this one printed ok once.

It also agrees with the endpoint meters read during enumeration: [0] carried meter=0.136675 and
was the only one non-zero, and it is the only one that produced audio. Two independent
measurements, same ordering.

WHAT IS STILL UNMEASURED:
- 1 run per endpoint. Four of the five are silent on this machine at this moment because
  nothing is playing to them, which is a fact about the box, not about the tap.
- No endpoint has been driven with a known signal, so there is no controlled input.
- The .wav still has not been written and re-read by a decoder.
- Still a selftest build; main.cpp does not call LoopbackTap.
