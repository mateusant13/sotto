"""SottoAgcSpeechOrder — the ORDER, proven mechanically, no device and no model.

Exercises the two classes the order connects, directly:
  * SpeechMusicGate.is_speech(chunk)  -> the PRE-GAIN decision
  * AutoGain.process(chunk, speech=…) -> the gain, applied to speech ONLY

Fixtures (numpy only):
  drone  : a stationary low tone bed (what the capture actually carries)
  speech : a syllabically-modulated envelope (what real speech looks like)

Assertions:
  A. gate(drone)  is False   and gate(speech) is True   (the decision discriminates)
  B. process(drone, speech=False) returns the block UNCHANGED (unity) while
     gain_would_max_db is LARGE  -> the drone is left un-boosted, and the boost it
     refused is reported.
  C. process(speech, speech=True) returns a LARGER block and gain_max_db > 0
     -> the quiet speech IS lifted.
"""
import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER = os.path.join(HERE, "..", "worker", "sotto_worker.py")


def load():
    spec = importlib.util.spec_from_file_location("sotto_worker", WORKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def drone_chunk(n=8960, sr=16000, amp=0.02):
    """Stationary bed: three low tones, no envelope. RMS ~ -37 dBFS, well ABOVE the
    AGC -60 dBFS hold floor, so a gain-blind stage WOULD boost it."""
    t = np.arange(n) / sr
    x = amp * (np.sin(2 * np.pi * 90 * t) + 0.6 * np.sin(2 * np.pi * 240 * t)
               + 0.4 * np.sin(2 * np.pi * 620 * t))
    return x.astype(np.float32)


def speech_chunk(n=8960, sr=16000, amp=0.02):
    """Quiet but speech-shaped: a low carrier under a syllabic (4 Hz) envelope with
    deep dips, so the sub-frame dB range is wide like real speech."""
    t = np.arange(n) / sr
    env = 0.5 * (1.0 + np.sin(2 * np.pi * 4.0 * t - np.pi / 2))  # 0..1, syllabic
    carrier = np.sin(2 * np.pi * 210 * t) + 0.5 * np.sin(2 * np.pi * 900 * t)
    return (amp * (0.05 + env ** 1.5) * carrier).astype(np.float32)


def rms_db(x):
    r = float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    return 20.0 * np.log10(r) if r > 0 else float("-inf")


def main():
    w = load()
    gate = w.SpeechMusicGate()
    drone = drone_chunk()
    speech = speech_chunk()

    # A. the decision discriminates, on the PRE-GAIN signal, as configured.
    #    Capture the figures AT CALL TIME: last_db_range is overwritten by the
    #    next call, and reading it afterwards printed the same number for both.
    d_speech = gate.is_speech(drone)
    d_range, d_rms = gate.last_db_range, gate.last_rms
    s_speech = gate.is_speech(speech)
    s_range, s_rms = gate.last_db_range, gate.last_rms
    print(f"A gate(drone)={d_speech} (db_range={d_range:.1f} rms={d_rms:.5f} vs min {w.GATE_DB_RANGE_MIN})")
    print(f"A gate(speech)={s_speech} (db_range={s_range:.1f} rms={s_rms:.5f})")

    # B. drone -> gain HELD: output byte-identical to input, would-be huge.
    agc = w.AutoGain()
    out_d = agc.process(drone, speech=d_speech)
    same_d = bool(np.array_equal(out_d, drone))
    print(f"B drone  in_dbfs={rms_db(drone):+.2f} out_dbfs={rms_db(out_d):+.2f} "
          f"unchanged={same_d} gain_max_db={agc.max_applied_db:+.1f} "
          f"gain_would_max_db={agc.would_max_db:+.1f} held_blocks={agc.non_speech_blocks}")

    # C. speech -> gain APPLIED: output larger, gain_max > 0.
    agc2 = w.AutoGain()
    out_s = agc2.process(speech, speech=s_speech)
    print(f"C speech in_dbfs={rms_db(speech):+.2f} out_dbfs={rms_db(out_s):+.2f} "
          f"gain_max_db={agc2.max_applied_db:+.1f} gain_would_max_db={agc2.would_max_db:+.1f} "
          f"speech_blocks={agc2.speech_blocks}")

    ok = (
        (d_speech is False) and (s_speech is True)
        and same_d and (agc.max_applied_db == 0.0) and (agc.would_max_db > 6.0)
        and (agc2.max_applied_db > 6.0) and (rms_db(out_s) > rms_db(speech) + 3.0)
    )
    print("VERDICT:", "GREEN" if ok else "RED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
