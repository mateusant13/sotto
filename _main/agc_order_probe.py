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
#: `--worker PATH` / `SOTTO_AGC_WORKER` — the negative control needs to judge a
#: MUTATED COPY without touching the live file. Without the argument the probe
#: reads the real worker, which is what the positive step must always do.
WORKER_PATH = os.environ.get("SOTTO_AGC_WORKER") or WORKER


def load():
    spec = importlib.util.spec_from_file_location("sotto_worker", WORKER_PATH)
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


def loud_transient_chunk(n=8960, sr=16000):
    """O formato do defeito: RMS baixo (o alvo pede ganho) com picos em cheio.

    Speech-shaped bed at the AGC floor plus a few sharp transients at 0.99 --
    exactly the shape of 30 s of the owner's live loopback, whose BRUTE peak was
    1.0045 and whose RMS per chunk sat ~-24 dBFS. The RMS target therefore asks
    for more than +20 dB of gain on a wave that already touches full scale.
    """
    t = np.arange(n) / sr
    env = 0.35 * (1.0 + np.sin(2 * np.pi * 3.0 * t))
    bed = 0.02 * env * (np.sin(2 * np.pi * 200 * t) + 0.4 * np.sin(2 * np.pi * 1100 * t))
    x = bed.astype(np.float32)
    for k in (0.11, 0.37, 0.62, 0.85):
        i = int(k * n)
        m = max(8, n // 200)
        x[i:i + m] += (0.99 * np.hanning(m)).astype(np.float32)
    return x


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

    # D. THE PEAK CEILING — the defect measured on the owner's own capture.
    #    A LOUD transient riding a quiet bed asks the RMS target for ~+24 dB
    #    while its own peak is already at full scale: the old code multiplied
    #    and then `np.clip`-ed, i.e. flat-topped the wave. MEASURED 2026-11-02 on
    #    30 s of his live loopback: `peak_out=1.000000` on EVERY tick, `gain_max_db`
    #    up to +23.5. Here the same shape is proven mechanically: the input is
    #    loud at the peak (0.99) and quiet in RMS (so the target asks for gain).
    loud = loud_transient_chunk()
    agc3 = w.AutoGain()
    out_l = agc3.process(loud, speech=True)
    peak_in = float(np.abs(loud).max())
    peak_out = float(np.abs(out_l).max())
    ceiling = float(getattr(w, "AGC_CEILING", 1.0))
    # The no-ceiling arm: the OLD behaviour, reproduced in-file, so the negative
    # control is the defect itself and not a story about it.
    g = 10.0 ** (agc3.max_applied_db / 20.0)
    old_out = np.clip((loud * g).astype(np.float32), -1.0, 1.0)
    old_peak = float(np.abs(old_out).max())
    print(f"D loud  peak_in={peak_in:.4f} peak_out={peak_out:.4f} ceiling={ceiling} "
          f"limited_blocks={agc3.limited_blocks} limit_db_min={agc3.limit_db_min:+.1f} "
          f"gain_would_max_db={agc3.would_max_db:+.1f} | no-ceiling peak={old_peak:.4f}")

    ok = (
        (d_speech is False) and (s_speech is True)
        and same_d and (agc.max_applied_db == 0.0) and (agc.would_max_db > 6.0)
        and (agc2.max_applied_db > 6.0) and (rms_db(out_s) > rms_db(speech) + 3.0)
        # D: o teto segura o pico e o braco SEM teto o mostra a 1.0.
        and (peak_out <= ceiling + 1e-6)
        and (agc3.limited_blocks > 0) and (agc3.limit_db_min < 0.0)
        and (old_peak >= 0.999)
    )
    if not ok:
        print("D FAILED:", dict(peak_out=peak_out, ceiling=ceiling,
                                limited=agc3.limited_blocks, old_peak=old_peak))
    print("VERDICT:", "GREEN" if ok else "RED")
    return 0 if ok else 1


def neg_arm():
    """O BRACO NEGATIVO: o mutante e' o DEFEITO, nao uma historia sobre ele.

    Copia o worker vivo, desarma o teto com um token (`if g > g_ceiling:` ->
    `if False and g > g_ceiling:`), e exige que a arm D do MESMO `main()` fique
    RED nessa copia. Um detector que nao derruba o mutante nao estava a medir o
    teto -- media o `np.clip` que ja' la estava.
    """
    import subprocess
    import sys
    import tempfile

    src = WORKER_PATH
    text = open(src, encoding="utf-8", newline="").read()
    needle = "            if g > g_ceiling:"
    if needle not in text:
        print("NEG-ARM FAIL: o teto nao esta' no worker:", src)
        return 1
    mutant = text.replace(needle, "            if False and g > g_ceiling:", 1)
    # O mutante VIVE AO LADO do worker: o modulo importa os seus irmaos
    # (`engine_switch`, `wasapi_loopback`, ...) pelo diretorio do ficheiro, e uma
    # copia em %TEMP% morre com `ModuleNotFoundError` -- medido, o oraculo nunca
    # chegava a medir nada.
    fd, tmp = tempfile.mkstemp(prefix="_mutant_agc_", suffix=".py",
                               dir=os.path.dirname(os.path.abspath(src)))
    os.close(fd)
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(mutant)
    try:
        proc = subprocess.run([sys.executable, os.path.abspath(__file__), "--worker", tmp],
                              capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    caught = proc.returncode != 0 and "D FAILED" in (proc.stdout or "")
    tail = [ln for ln in (proc.stdout or "").splitlines() if ln.startswith(("D loud", "D FAILED", "VERDICT"))]
    print("NEG-ARM mutant rc=%d caught=%s" % (proc.returncode, caught))
    for ln in tail:
        print("  ", ln)
    print("NEG-ARM PASS" if caught else "NEG-ARM FAIL")
    # O `:expectred` da bateria exige rc=1 quando o mutante APANHADO: o passo
    # negativo PASSA com um RED (o defeito foi nomeado), nao com um zero.
    return 1 if caught else 0


if __name__ == "__main__":
    import sys as _sys

    if "--neg-arm" in _sys.argv[1:]:
        raise SystemExit(neg_arm())
    for _i, _a in enumerate(_sys.argv[1:]):
        if _a == "--worker":
            WORKER_PATH = _sys.argv[_i + 2]
        elif _a.startswith("--worker="):
            WORKER_PATH = _a.split("=", 1)[1]
    print("worker:", WORKER_PATH)
    raise SystemExit(main())
