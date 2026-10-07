# WASAPI audio tap: FIRST runtime proof

Repo H:\sotto, main at 4af24bc. Binary: tap-selftest.exe, 333424 bytes, built rc=0.
Recipe, taken from the recipe documented in audio_tap.cpp itself:
  g++ -std=c++17 -O2 -DAUDIO_TAP_SELFTEST -I <src> audio_tap.cpp -o tap.exe -lole32 -loleaut32
The main() is inside #ifdef AUDIO_TAP_SELFTEST; without that define there is no main at all
and the link fails with "undefined reference to WinMain". That cost three build attempts.

WINDOW: one run, this turn. POPULATION: 1 endpoint opened, 1 bounded 1500 ms window.

  ENDPOINTS=5
    CABLE Input (VB-Audio Virtual Cable)            meter=0.136675  default=0  48000 Hz 2ch 32bit
    VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)   meter=0.000000  default=1  48000 Hz 2ch 32bit
    Speakers (NVIDIA Broadcast)                      meter=0.000000  default=0  48000 Hz 2ch 32bit
    AG251F1WG2 (NVIDIA High Definition Audio)       meter=0.000000  default=0  48000 Hz 2ch 32bit
    Alto-falantes (HyperX Quadcast)                 meter=0.000000  default=0  48000 Hz 2ch 32bit

  OPEN=ok endpoint=CABLE Input (VB-Audio Virtual Cable)
  VERDICT=ok packets=148 frames=71040 silent_packets=0 empty_polls=96 blocks=148 pulls=148
           pcm_samples=23680 peak=0.200740
  WAV_FMT=1 ch / 16000 Hz / 2 bytes PCM16 (the contract)
  COM_BALANCE=0
  RUN_RC=0

WHAT THIS ESTABLISHES, and what it does not.
- peak=0.200740 is the load-bearing number: a tap that reported silence would also print
  VERDICT=ok. A non-zero peak is what separates "it opened" from "it carried audio".
- The device mixes at 48000 Hz / 2ch / 32-bit float and the tap delivers 16000 / 1 / PCM16.
  The conversion the contract demands is real, not assumed.
- COM_BALANCE=0: no COM leak across 5 enumerated endpoints and one opened tap.

NOT ESTABLISHED:
- POPULATION 1. One run, one window, one endpoint. No repeat, no other endpoint, no
  comparison against the contract's WAV written to disk and read back.
- The .wav was not written and re-read; WAV_FMT is what the writer reported, not what a
  decoder saw.
- This is a SELFTEST build. main.cpp still never calls LoopbackTap; the tap is not in the
  shipping binary's control path yet.
- 32-bit float mix format: the contract header says PCM16/16k/mono, and that is what came
  out, but the intermediate float path is unverified against clipping at full scale.
