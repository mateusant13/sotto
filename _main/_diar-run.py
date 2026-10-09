"""Decisive diarization measurement on REAL owner audio.

Instrument: sherpa-onnx OfflineSpeakerDiarization (pyannote segmentation-3.0 +
speaker embedding) over a WAV file.  READ ONLY on the WAV; writes only its own
JSON receipt under _main/.

Never imports onnxruntime_genai (the measured DLL-order trap in
_main/research-backend-per-model.md): sherpa_onnx bundles ORT 1.24.4 and the
genai DLL binds to whatever loaded first.

Usage:
  python _diar-run.py --wav F --seg S --emb E --threads 2 --out J.json
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import psutil
import soundfile as sf

import sherpa_onnx

HERE = os.path.dirname(os.path.abspath(__file__))


def resample(audio, sr, target):
    if sr == target:
        return audio, sr
    import librosa

    return librosa.resample(audio, orig_sr=sr, target_sr=target), target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--seg", default=os.path.join(
        HERE, "diar-models", "sherpa-onnx-pyannote-segmentation-3-0", "model.onnx"))
    ap.add_argument("--emb", default=os.path.join(
        HERE, "diar-models", "3dspeaker_eres2net_base_16k.onnx"))
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--num-speakers", type=int, default=-1)
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--min-duration-on", type=float, default=0.3)
    ap.add_argument("--min-duration-off", type=float, default=0.5)
    ap.add_argument("--window-shift-ratio", type=float, default=0.1)
    ap.add_argument("--provider", default="cpu")
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    assert "onnxruntime_genai" not in sys.modules, "genai must not be imported"

    t0 = time.perf_counter()
    audio, sr = sf.read(args.wav, dtype="float32", always_2d=True)
    channels_in = audio.shape[1]
    rate_in = sr
    audio = audio[:, 0].copy()
    load_s = time.perf_counter() - t0

    pyannote_fn = sherpa_onnx.OfflineSpeakerSegmentationPyannoteModelConfig
    try:
        pyannote_cfg = pyannote_fn(model=args.seg, window_shift_ratio=args.window_shift_ratio)
        wsr_supported = True
    except TypeError:
        # sherpa-onnx 1.13.4's pybind signature is (model: str) only; the
        # window_shift_ratio kwarg arrived on master after this release.
        pyannote_cfg = pyannote_fn(model=args.seg)
        wsr_supported = False

    cfg = sherpa_onnx.OfflineSpeakerDiarizationConfig(
        segmentation=sherpa_onnx.OfflineSpeakerSegmentationModelConfig(
            pyannote=pyannote_cfg,
            num_threads=args.threads,
            provider=args.provider,
        ),
        embedding=sherpa_onnx.SpeakerEmbeddingExtractorConfig(
            model=args.emb, num_threads=args.threads, provider=args.provider),
        clustering=sherpa_onnx.FastClusteringConfig(
            num_clusters=args.num_speakers, threshold=args.threshold),
        min_duration_on=args.min_duration_on,
        min_duration_off=args.min_duration_off,
    )
    if not cfg.validate():
        raise SystemExit("CONFIG-INVALID: %r" % (cfg,))

    t0 = time.perf_counter()
    sd = sherpa_onnx.OfflineSpeakerDiarization(cfg)
    model_load_s = time.perf_counter() - t0
    target = sd.sample_rate
    audio, sr = resample(audio, sr, target)
    if sr != target:
        raise SystemExit("RESAMPLE-FAILED %d != %d" % (sr, target))
    audio_s = len(audio) / float(target)

    proc = psutil.Process()
    rss_before = proc.memory_info().rss
    c0 = time.process_time()
    w0 = time.perf_counter()
    result = sd.process(audio).sort_by_start_time()
    wall = time.perf_counter() - w0
    cpu = time.process_time() - c0
    rss_peak = proc.memory_info().rss

    segs = [{"start": float(r.start), "end": float(r.end), "speaker": int(r.speaker)}
            for r in result]
    speakers = sorted({s["speaker"] for s in segs})
    dur_total = sum(s["end"] - s["start"] for s in segs)
    doc = {
        "instrument": "_diar-run.py (sherpa-onnx OfflineSpeakerDiarization)",
        "tag": args.tag,
        "wav": os.path.abspath(args.wav),
        "wav_bytes": os.path.getsize(args.wav),
        "channels_in": channels_in,
        "rate_in": rate_in,
        "rate_model": target,
        "audio_s": audio_s,
        "seg_model": os.path.abspath(args.seg),
        "emb_model": os.path.abspath(args.emb),
        "threads": args.threads,
        "provider": args.provider,
        "num_clusters_arg": args.num_speakers,
        "threshold": args.threshold,
        "min_duration_on": args.min_duration_on,
        "min_duration_off": args.min_duration_off,
        "window_shift_ratio": args.window_shift_ratio if wsr_supported else None,
        "window_shift_ratio_supported": wsr_supported,
        "load_s": load_s,
        "model_load_s": model_load_s,
        "wall_s": wall,
        "cpu_s": cpu,
        "rtf": wall / audio_s,
        "cpu_pct_of_one_core": 100.0 * cpu / wall,
        "rss_before_mb": rss_before / 1e6,
        "rss_after_mb": rss_peak / 1e6,
        "n_segments": len(segs),
        "n_speakers": len(speakers),
        "speakers": speakers,
        "speech_s": dur_total,
        "speech_frac": dur_total / audio_s,
        "segments": segs,
    }
    txt = json.dumps(doc, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(txt + "\n")
    print(txt)
    print("\n--- segments ---", file=sys.stderr)
    for s in segs:
        print("  %7.3f -- %7.3f  speaker_%02d  (%5.2fs)"
              % (s["start"], s["end"], s["speaker"], s["end"] - s["start"]), file=sys.stderr)
    print("  speakers=%d segments=%d speech=%.2fs/%.2fs (%.1f%%)"
          % (len(speakers), len(segs), dur_total, audio_s, 100 * dur_total / audio_s),
          file=sys.stderr)
    print("  wall=%.3fs cpu=%.3fs rtf=%.4f cpu%%=%.1f threads=%d"
          % (wall, cpu, wall / audio_s, 100.0 * cpu / wall, args.threads), file=sys.stderr)


if __name__ == "__main__":
    main()
