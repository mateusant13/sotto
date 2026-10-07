# Audio tap: CONTROLLED input. The measured peak equals the amplitude I generated.

The gap this closes: every previous audio run measured whatever happened to be playing, so a
peak of 0.05 and a peak of 0.15 proved only that something was audible. Nobody had shown the
tap reports the amplitude of a KNOWN signal, and a scale error or a 48k-to-16k conversion
that quietly halved everything would still have looked like "audio works".

INPUT, fully under my control:
  1 kHz sine, amplitude exactly 0.5, 4 s, 16-bit mono at 48000 Hz, written as a real RIFF/WAVE
  by Python's wave module. File size 384044 bytes = 44 + 48000*4*2, so the header is correct.

WINDOW: 15:10:32. POPULATION: 1 baseline tap plus 5 taps, all on the same endpoint
(CABLE Input), 700-1200 ms windows.

  BASELINE, nothing playing:  peak=0.036513   VERDICT=ok
  tone playing, tap 1:        peak=0.500000   samples=11200
  tone playing, tap 2:        peak=0.500000   samples=11200
  tone playing, tap 3:        peak=0.500000   samples=10880
  tone playing, tap 4:        peak=0.500000   samples=11200
  tone playing, tap 5:        peak=0.500000   samples=11200

WHAT THIS PROVES, which nothing before it did:
- The measured peak is 0.500000 on 5 of 5, against an input generated at exactly 0.500000.
  There is no scaling error, no attenuation through the 48000 to 16000 conversion, and no
  clipping. The amplitude chain is correct to the printed precision.
- The baseline to tone contrast is 0.036513 -> 0.500000, a 13.7x rise caused solely by the
  controlled input. So the earlier "peaks vary between runs" readings were measuring real
  programme material, not a fixed artefact of the instrument.
- 11200 samples for a 700 ms window at 16000 Hz is exactly 11200. The rate contract holds while
  real audio is flowing, not only in quiet.

STILL NOT MEASURED:
- The FREQUENCY content of what was captured. I verified amplitude, not that the captured PCM
  is a 1 kHz sine. That needs a spectrum or a zero-crossing count on the captured samples, and
  the tap does not currently write the samples to disk for inspection.
- One endpoint only. The four silent endpoints were never driven with this tone.
- The .wav has still not been written and re-read by a decoder.
- Still a selftest build; main.cpp does not call LoopbackTap.
