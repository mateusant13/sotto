"""DER (Diarization Error Rate) between a reference segmentation and a hypothesis,
with the standard three components and an OPTIMAL one-to-one speaker mapping.

Frame grid: 10 ms. No collar (stated, because a collar hides exactly the boundary
error we care about). Overlap policy: in a frame where several hypothesis
segments overlap, the one covering the most of that frame wins; ties go to the
later-starting segment. A frame is "reference speech" if any reference segment
covers it, "hypothesis speech" likewise.

    DER = (miss + false_alarm + speaker_error) / reference_speech_duration

Speaker error is counted ONLY on frames where both are speech, after the optimal
label mapping (Hungarian on the confusion matrix). Miss = ref speech, no hyp.
False alarm = hyp speech, no ref.

The mapping is optimal, which is the GENEROUS direction for the hypothesis: a
DER computed this way is a lower bound on the hypothesis's error. Say so.

CLI:
  --ref   vendor|path.json    reference segmentation
  --hyp   path.json           hypothesis JSON from _diar-run.py
  --ref-vendor                use the vendor's published 10-segment/4-speaker
                              ground truth for 0-four-speakers-zh.wav
"""
import argparse
import json
import sys

import numpy as np
from scipy.optimize import linear_sum_assignment

FRAME = 0.01

# The vendor's published output for 0-four-speakers-zh.wav (56.861 s), verbatim
# from docs/source/onnx/speaker-diarization/code/pyannote-segmentation-3-0-3dspeaker.txt
# (--clustering.num-clusters=4). Independently CONFIRMED on this box: our own
# --num-speakers 4 arm reproduced all ten boundaries and all four labels exactly.
VENDOR_4SPK = [
    (0.318, 6.865, "s00"),
    (7.017, 10.747, "s01"),
    (11.455, 13.632, "s01"),
    (13.750, 17.041, "s02"),
    (22.137, 24.837, "s00"),
    (27.638, 29.478, "s03"),
    (30.001, 31.553, "s03"),
    (33.680, 37.932, "s03"),
    (48.040, 50.470, "s02"),
    (52.529, 54.605, "s00"),
]


def frame_labels(segments, n_frames):
    """per-frame label array; '' = no speech. Longest-covering-segment wins."""
    lab = np.array([""] * n_frames, dtype=object)
    best = np.zeros(n_frames, dtype=np.float64)
    for (a, b, spk) in segments:
        i = max(0, int(round(a / FRAME)))
        j = min(n_frames, int(round(b / FRAME)))
        if j <= i:
            continue
        span = j - i
        take = span > best[i:j]
        idx = i + np.nonzero(take)[0]
        lab[idx] = spk
        best[idx] = span
    return lab


def der(ref, hyp, duration):
    n = int(round(duration / FRAME))
    R = frame_labels(ref, n)
    H = frame_labels(hyp, n)
    ref_sp = R != ""
    hyp_sp = H != ""
    ref_dur = float(ref_sp.sum()) * FRAME

    miss = float((ref_sp & ~hyp_sp).sum()) * FRAME
    fa = float((~ref_sp & hyp_sp).sum()) * FRAME
    both = ref_sp & hyp_sp

    ref_speakers = sorted(set(R[ref_sp].tolist()))
    hyp_speakers = sorted(set(H[hyp_sp].tolist()))
    conf = np.zeros((len(ref_speakers), len(hyp_speakers)), dtype=np.float64)
    ri = {s: i for i, s in enumerate(ref_speakers)}
    hi = {s: i for i, s in enumerate(hyp_speakers)}
    for r, h in zip(R[both].tolist(), H[both].tolist()):
        conf[ri[r], hi[h]] += 1.0
    se_frames = 0.0
    mapping = {}
    if conf.size:
        rr, cc = linear_sum_assignment(-conf)
        total = conf.sum()
        matched = conf[rr, cc].sum()
        se_frames = total - matched
        for a, b in zip(rr, cc):
            mapping[ref_speakers[a]] = hyp_speakers[b]
    se = se_frames * FRAME

    denom = ref_dur if ref_dur > 0 else 1e-9
    return {
        "ref_speech_s": round(ref_dur, 3),
        "ref_speakers": len(ref_speakers),
        "hyp_speakers": len(hyp_speakers),
        "miss_s": round(miss, 3),
        "false_alarm_s": round(fa, 3),
        "speaker_error_s": round(se, 3),
        "miss_pct": round(100 * miss / denom, 2),
        "false_alarm_pct": round(100 * fa / denom, 2),
        "speaker_error_pct": round(100 * se / denom, 2),
        "DER_pct": round(100 * (miss + fa + se) / denom, 2),
        "mapping_ref_to_hyp": mapping,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default=None)
    ap.add_argument("--ref-vendor", action="store_true")
    ap.add_argument("--hyp", required=True)
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    H = json.load(open(args.hyp, encoding="utf-8"))
    hyp = [(s["start"], s["end"], "h%02d" % s["speaker"]) for s in H["segments"]]
    dur = args.duration or H["audio_s"]

    if args.ref_vendor:
        ref = VENDOR_4SPK
        refname = "vendor-published-4spk-10seg"
    elif args.ref:
        R = json.load(open(args.ref, encoding="utf-8"))
        ref = [(s["start"], s["end"], "h%02d" % s["speaker"]) for s in R["segments"]]
        refname = args.ref
    else:
        raise SystemExit("need --ref or --ref-vendor")

    out = der(ref, hyp, dur)
    out["hyp_file"] = args.hyp
    out["tag"] = H.get("tag")
    out["ref"] = refname
    out["duration_s"] = round(dur, 3)
    out["frame_ms"] = int(FRAME * 1000)
    out["collar_ms"] = 0
    out["n_hyp_segments"] = len(hyp)
    out["rtf"] = H.get("rtf")
    out["threads"] = H.get("threads")
    if args.json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
    else:
        print("%-28s DER %6.2f%%  (miss %5.2f + fa %5.2f + spk %5.2f)  ref_sp %.2fs  spk ref=%d hyp=%d  nseg=%d"
              % (out["tag"] or args.hyp, out["DER_pct"], out["miss_pct"],
                 out["false_alarm_pct"], out["speaker_error_pct"],
                 out["ref_speech_s"], out["ref_speakers"], out["hyp_speakers"],
                 out["n_hyp_segments"]))


if __name__ == "__main__":
    main()
