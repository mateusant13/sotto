"""What is the OWNER's real speech-to-bed ratio?

The mix ladder in _diar-mix.py defines SNR against the WHOLE target file
(rms(target)/rms(bed)), and the target is 53.8 % speech, so a "+5 dB" mix is
much harsher on the speech frames than the label suggests. To read the ladder
against the owner's own audio, the ladder's SNR must be converted to the same
basis the owner's audio is measured on.

This instrument measures BOTH, on the owner's real 90 s file:

  * speech-region RMS  — 29.5..49.4 s, the stretch BOTH instruments (pyannote
    segmenter and Redux word timestamps) independently mark as speech;
  * bed-region RMS     — 50.0..88.0 s, the stretch BOTH instruments mark as
    having no speech at all.

  owner_snr_db = 20*log10(rms(speech_region)/rms(bed_region))

and the same quantity on each MIX, where the speech region is the target's own
speech frames and the bed is the added bed — so the ladder can be reported in
the owner's units instead of the whole-file units.

Reported both ways, because the choice moves the number and the number decides
whether the recommendation survives.
"""
import json
import sys

import numpy as np
import soundfile as sf

SR = 16000


def load_mono16k(path):
    a, sr = sf.read(path, dtype="float64", always_2d=False)
    if a.ndim > 1:
        a = a.mean(axis=1)
    if sr != SR:
        n = int(round(len(a) * SR / sr))
        a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a)
    return a


def rms_db(x):
    if len(x) == 0:
        return float("nan")
    r = float(np.sqrt(np.mean(x * x)))
    return 20 * np.log10(max(r, 1e-12))


def speech_frames(path, ref_segments, pad=0.0):
    """boolean mask over 16 kHz samples, True where a reference segment speaks"""
    a = load_mono16k(path)
    m = np.zeros(len(a), dtype=bool)
    for (s, e, _) in ref_segments:
        i = max(0, int((s - pad) * SR))
        j = min(len(a), int((e + pad) * SR))
        m[i:j] = True
    return a, m


def main():
    VENDOR = json.load(open("_main/diar-mix/manifest.json", encoding="utf-8"))
    if isinstance(VENDOR, dict):
        VENDOR = VENDOR.get("mixes", [])
    VENDOR = {"mixes": VENDOR}
    ref = [(s["start"], s["end"], s["speaker"])
           for s in json.load(open("_main/_diar-arm-ctrl-thr090-fp32-eres.json",
                                   encoding="utf-8"))["segments"]]

    print("== target file, speech frames vs the 46.4 % of it that is NOT speech ==")
    a, m = speech_frames("_main/diar-models/0-four-speakers-zh.wav", ref)
    sp = rms_db(a[m])
    ns = rms_db(a[~m])
    print("   target speech-frame rms %8.2f dBFS   non-speech-frame rms %8.2f dBFS"
          % (sp, ns))
    print("   -> whole-file rms is %.2f dBFS (the basis _diar-mix.py calls 'target')"
          % rms_db(a))

    print()
    print("== the OWNER's real 90 s file ==")
    ow = "H:/sotto/_main/live-sample-cable-input-90s.wav"
    ob = load_mono16k(ow)
    sp_r = ob[int(29.5 * SR):int(49.4 * SR)]
    bed_r = ob[int(50.0 * SR):int(88.0 * SR)]
    owner_snr = rms_db(sp_r) - rms_db(bed_r)
    print("   speech region 29.5-49.4 s  rms %8.2f dBFS  (%d samples)"
          % (rms_db(sp_r), len(sp_r)))
    print("   bed    region 50.0-88.0 s  rms %8.2f dBFS  (%d samples)"
          % (rms_db(bed_r), len(bed_r)))
    print("   OWNER SPEECH-TO-BED RATIO = %+.2f dB" % owner_snr)

    print()
    print("== the ladder, restated in the owner's units ==")
    print("   %-12s %10s %14s %12s %8s" %
          ("mix", "ladder SNR", "speech-frame", "true SNR", "DER"))
    ders = {"mix-clean": 0.03, "mix-snr+15": 2.98, "mix-snr+05": 21.88,
            "mix-snr+00": 48.38, "mix-snr-05": 71.77, "mix-bedonly": 100.0}
    rows = []
    for name in ["mix-clean", "mix-snr+15", "mix-snr+05", "mix-snr+00",
                 "mix-snr-05", "mix-bedonly"]:
        p = "_main/diar-mix/%s.wav" % name
        x, mm = speech_frames(p, ref)
        s_rms = rms_db(x[mm])
        # bed energy is whatever is in the file OUTSIDE the speech frames
        b_rms = rms_db(x[~mm])
        true_snr = s_rms - b_rms
        ladder = [r for r in VENDOR["mixes"] if r["name"] == name]
        lad = ladder[0]["snr_db"] if ladder else None
        rows.append((name, lad, s_rms, true_snr, ders[name]))
        print("   %-12s %+10s %12.2f %+12.2f %7.2f%%" %
              (name, ("%+.0f" % lad) if lad is not None else "-",
               s_rms, true_snr, ders[name]))

    print()
    print("== reading ==")
    print("   The owner's own ratio is %+.2f dB. Interpolating the ladder on the" % owner_snr)
    print("   TRUE (speech-frame) SNR column:")
    pts = [(r[3], r[4]) for r in rows if r[0] not in ("mix-clean", "mix-bedonly")]
    pts.sort()
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])
    est = float(np.interp(owner_snr, xs, ys))
    print("   %-28s %s" % ("true SNR (dB) -> DER (%)", ""))
    for x, y in pts:
        print("      %+7.2f dB -> %6.2f %%" % (x, y))
    print("   -> at the owner's measured %+.2f dB the ladder predicts DER ~ %.1f %%"
          % (owner_snr, est))
    json.dump({"owner_snr_db": round(owner_snr, 2),
               "speech_region_dbfs": round(rms_db(sp_r), 2),
               "bed_region_dbfs": round(rms_db(bed_r), 2),
               "target_speech_frame_dbfs": round(sp, 2),
               "target_nonspeech_frame_dbfs": round(ns, 2),
               "ladder": [{"mix": r[0], "ladder_snr_db": r[1],
                           "speech_frame_dbfs": round(r[2], 2),
                           "true_snr_db": round(r[3], 2), "DER_pct": r[4]}
                          for r in rows],
               "interp_DER_at_owner_snr_pct": round(est, 2)},
              open("_main/_diar-owner-snr.json", "w", encoding="utf-8"),
              indent=1)


if __name__ == "__main__":
    main()
