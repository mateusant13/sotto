# Audio tap: repeated 5x, peak varies, sample count is exact

Binary tap-selftest.exe, 333424 bytes, built rc=0.
Recipe from the comment at the top of audio_tap.cpp:
  g++ -std=c++17 -O2 -DAUDIO_TAP_SELFTEST -I <src> audio_tap.cpp -o tap.exe -lole32 -loleaut32

WINDOW: 15:04:18, five consecutive runs. POPULATION: 5 runs x 1 endpoint (CABLE Input),
1500 ms window each, five separate processes.

  run 1  OPEN=ok  VERDICT=ok  peak=0.060639  pcm_samples=23840  rc=0
  run 2  OPEN=ok  VERDICT=ok  peak=0.050359  pcm_samples=23840  rc=0
  run 3  OPEN=ok  VERDICT=ok  peak=0.048774  pcm_samples=24000  rc=0
  run 4  OPEN=ok  VERDICT=ok  peak=0.107190  pcm_samples=24000  rc=0
  run 5  OPEN=ok  VERDICT=ok  peak=0.070500  pcm_samples=24000  rc=0

  peak    min=0.048774  max=0.107190  mean=0.067492
  samples min=23840  max=24000
  runs with a NON-ZERO peak: 5 of 5

WHAT THE REPETITION ESTABLISHES, which one run could not:
- The peak VARIES by 2.2x across identical runs. A tap reporting silence, or a fixed
  artifact, would give the same number every time. This is signal whose amplitude follows
  whatever is playing. 5 of 5 non-zero is the load-bearing fact.
- Sample count lands on 24000 = 1500 ms x 16000 Hz EXACTLY on three of five runs, and
  23840 on two (160 samples = 10 ms short). The resample to the contract rate is arithmetically
  exact when the tap is not cut mid-block; the short runs are a block-boundary rounding, not a
  rate error. That 160-sample gap is a real, reproducible discrepancy worth naming rather than
  rounding away.

STILL NOT ESTABLISHED:
- One endpoint only. Four other endpoints enumerated (VoiceMeeter Input, Speakers/NVIDIA
  Broadcast, NVIDIA HD Audio, HyperX Quadcast) were never opened.
- The .wav is still not written to disk and re-read. WAV_FMT is what the writer reported.
- Still a selftest build: main.cpp does not call LoopbackTap.
- No claim about clipping: peak reached 0.107 but nothing pushed it near 1.0, so headroom
  behaviour at full scale is unmeasured.
