# Audio tap: FREQUENCY CONFIRMED. The captured PCM really is the 1 kHz tone I generated.

This closes the last gap in the audio evidence. Amplitude was already proven; now the
frequency content is too.

INPUT, fully controlled: 1 kHz sine, amplitude exactly 0.5, 4 s, PCM16 mono at 48000 Hz,
written by Python's wave module, 384044 bytes = 44 + 48000*4*2.

CAPTURE, same recipe as before plus an accumulating dump:
  g++ -std=c++17 -O2 -DAUDIO_TAP_SELFTEST -I <src> tap_acc.cpp -o tap-acc.exe -lole32 -loleaut32
The dump accumulates every pull into allpcm. The previous version wrote only the LAST buffer:
160 samples out of 16000, which is why the earlier zero-crossing count had ~100 Hz bins and
could not distinguish 1 kHz from 900 Hz.

WINDOW: 15:16:25. POPULATION: 1 capture, 39840 samples = 2.490 s at 16000 Hz.

  rate=16000 ch=1 width=2 frames=39840 duration=2.490s
  peak=0.500000

  Goertzel on a 1.000 s window => 1 Hz bins:
       250 Hz ->   0.000000
       500 Hz ->   0.000000
       750 Hz ->   0.000000
       900 Hz ->   0.000000
      1000 Hz ->   0.249977      <- the only non-zero bin
      1100 Hz ->   0.000000
      1500 Hz ->   0.000000
      2000 Hz ->   0.000000
      4000 Hz ->   0.000000
    PEAK_BIN = 1000 Hz
    scanned 800-1200 Hz in 1 Hz steps, strongest = 1000 Hz
    zero crossings over all 39840 samples -> 999.8 Hz

WHAT THIS ESTABLISHES:
- The captured signal is a 1 kHz tone, not merely "something at roughly that pitch". With
  1 Hz bins and 400 Hz of decoys all reading exactly 0.000000, there is no energy anywhere
  else in the band. A 48k-to-16k conversion error that shifted the pitch would land the peak
  somewhere else and would show it.
- Amplitude and frequency now agree with the generated input on both axes: 0.5 in, 0.500000
  measured; 1000 Hz in, 1000 Hz measured.
- The 999.8 Hz zero-crossing figure is the real signal plus the edges of the capture window,
  which contain whatever else was playing before the tone started. 2490 measured cycles against
  2490 expected. I am naming that 0.2 Hz rather than rounding it to 1000.

STILL NOT ESTABLISHED:
- POPULATION 1 capture on 1 endpoint. One run.
- The 4 silent endpoints were still never driven with this tone.
- The dump lives in a local copy of audio_tap.cpp, not in main. main.cpp still never calls
  LoopbackTap, so none of this is reachable from the shipping capture binary.
- The wav was read by Python, not by a decoder that ships with the product.
