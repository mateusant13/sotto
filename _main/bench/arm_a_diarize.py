#!/usr/bin/env python
"""arm_a_diarize.py -- measure ARM A (diarize-then-label) on the call corpus.

WHY THIS EXISTS
---------------
Arm A is what ships today: `worker/speaker_sidecar.py` pushes one window of
audio into sherpa-onnx's `OfflineSpeakerDiarization` (pyannote segmentation-3.0
+ 3dspeaker eres2net embeddings + FastClustering), remaps the local labels onto
global slots, and publishes them. The owner's ask is to decide, by measurement,
whether that is the best this machine holds in real time, and a decision needs
numbers, not architecture.

WHAT THIS DOES
--------------
It replays the corpus through the REAL product path -- `RingBuffer` + `tick()`
+ `StableSpeakerSlots`, imported from `worker/speaker_sidecar.py`, not a copy --
so the numbers belong to what ships, and records per window:

  * wall time of the model call            -> RTF, wall s per audio-minute
  * speaker count per window and per 60 s bucket
  * dominant-slot share of speaking time   -> how much audio lands in one bucket
  * slot flips between consecutive windows -> stability
  * slots created                          -> 2 people should be 2 slots

Then a second phase measures CONTEXT STABILITY: the same 30 s span diarized
alone and diarized inside a 60 s context, aligned by best overlap, scored as
label agreement on the centre 30 s. A diarizer whose labels move with the
context cannot be the identity source for per-voice text.

The number that decides is RTF at the shipping window (10 s), because the
product runs this during the call, next to the ASR.

Usage
-----
    python -m watcher run --cpu 40 --io very-low -- \
        python _main/bench/arm_a_diarize.py --wav MIX.wav [--limit-s 600]

Everything is reported as JSON on stdout; `--out` also writes it to a file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
sys.path.insert(0, os.path.join(REPO, "worker"))

import speaker_sidecar as sc  # noqa: E402  the SHIPPING code path, not a copy


class PeakRSS:
    """Peak resident bytes of this process, sampled while the model runs."""

    def __init__(self, every_s: float = 0.25) -> None:
        import psutil                                            # noqa: PLC0415
        self._proc = psutil.Process()
        self._every = every_s
        self.peak = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.peak = max(self.peak, self._proc.memory_info().rss)
            except Exception:                                    # noqa: BLE001
                pass
            self._stop.wait(self._every)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2.0)
        try:
            self.peak = max(self.peak, self._proc.memory_info().rss)
        except Exception:                                        # noqa: BLE001
            pass


def read_wav16k(path: str):
    import soundfile as sf                                        # noqa: PLC0415
    x, sr = sf.read(path, dtype="float32", always_2d=False)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != sc.DEFAULT_RATE:
        raise SystemExit("arm_a: %s is %d Hz, want %d" % (path, sr, sc.DEFAULT_RATE))
    return x


def _slot_seconds(segments) -> dict:
    out = {}
    for s in segments or ():
        out[int(s["speaker"])] = out.get(int(s["speaker"]), 0.0) + max(
            0.0, float(s["end"]) - float(s["start"]))
    return out


def _speech_seconds(segments) -> float:
    return sum(_slot_seconds(segments).values())


def run_arm_a(samples, window_s: float, threshold: float, threads: int,
              out_json: str, progress_every: int = 6) -> dict:
    """Replay the corpus through the product's own tick(), window by window."""
    rate = sc.DEFAULT_RATE
    sdk = sc._load_sherpa_diarizer(
        sc.DEFAULT_SEG_MODEL, sc.DEFAULT_EMB_MODEL, threads,
        num_clusters=-1, threshold=threshold)

    def diarize(window, threshold=threshold, num_speakers=-1):
        import numpy as np                                        # noqa: PLC0415
        res = sdk.process(np.asarray(window, dtype=np.float32)).sort_by_start_time()
        return {"segments": [{"start": float(s.start), "end": float(s.end),
                              "speaker": int(s.speaker)} for s in res]}

    buf = sc.RingBuffer(rate=rate, window_s=window_s)
    slots = sc.StableSpeakerSlots()
    payload_path = os.path.join(HERE, "_arm_a_payload.json")
    rows = []
    slot_seconds_total = {}
    step = int(window_s * rate)
    n_steps = len(samples) // step

    t_capture = 0.0
    with PeakRSS() as rss:
        t_all = time.perf_counter()
        for i in range(n_steps):
            chunk = samples[i * step:(i + 1) * step]
            t0 = time.perf_counter()
            buf.push(chunk, t_capture)
            t_capture += len(chunk) / float(rate)
            state = sc.tick(buf, diarize, payload_path, threshold=threshold,
                            num_speakers=-1, slots=slots)
            dt = time.perf_counter() - t0
            with open(payload_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            segs = payload.get("segments") or []
            per_slot = _slot_seconds(segs)
            for k, v in per_slot.items():
                slot_seconds_total[k] = slot_seconds_total.get(k, 0.0) + v
            speech_s = sum(per_slot.values())
            dominant = (max(per_slot.items(), key=lambda kv: kv[1])[0]
                        if per_slot else None)
            rows.append({
                "i": i,
                "t": round(i * window_s, 3),
                "wall_s": round(dt, 4),
                "n_segments": len(segs),
                "local_speakers": len({int(s["speaker"]) for s in segs}),
                "slots": sorted(per_slot),
                "dominant_slot": dominant,
                "speech_s": round(speech_s, 3),
                "dominant_s": round(per_slot.get(dominant, 0.0), 3) if dominant else 0.0,
                "speech_fraction": payload.get("speech_fraction"),
                "slots_created": payload.get("speaker_slots_created") or [],
                "state": state.get("state"),
            })
            if progress_every and (i + 1) % progress_every == 0:
                print("arm_a: %d/%d windows, %.1fs wall (RTF %.4f)"
                      % (i + 1, n_steps, time.perf_counter() - t_all,
                         (time.perf_counter() - t_all) / max(1e-9, (i + 1) * window_s)),
                      file=sys.stderr, flush=True)
        total_wall = time.perf_counter() - t_all

    audio_s = n_steps * window_s
    speech_total = sum(r["speech_s"] for r in rows)
    flips = 0
    last = None
    for r in rows:
        if r["dominant_slot"] is not None:
            if last is not None and r["dominant_slot"] != last:
                flips += 1
            last = r["dominant_slot"]

    # 60 s buckets: how many distinct global slots each bucket saw
    buckets = {}
    for r in rows:
        b = int(r["t"] // 60.0)
        buckets.setdefault(b, set()).update(r["slots"])
    bucket_counts = [{"minute": b, "slots": sorted(v), "n_slots": len(v)}
                     for b, v in sorted(buckets.items())]

    # dominant bucket: the share of ALL speaking time that landed in the single
    # busiest global slot. A correct "2 people" answer concentrates speech in 2
    # slots; a fragmented one spreads it over many.
    ranked = sorted(slot_seconds_total.items(), key=lambda kv: -kv[1])
    top = ranked[0][1] if ranked else 0.0
    return {
        "arm": "A diarize-then-label",
        "wav": None,
        "window_s": window_s,
        "threshold": threshold,
        "threads": threads,
        "audio_s": round(audio_s, 1),
        "wall_s": round(total_wall, 2),
        "rtf": round(total_wall / max(1e-9, audio_s), 5),
        "wall_s_per_audio_min": round(60.0 * total_wall / max(1e-9, audio_s), 2),
        "peak_rss_mb": round(rss.peak / 1e6, 1),
        "windows": len(rows),
        "empty_windows": sum(1 for r in rows if not r["slots"]),
        "declined_windows": sum(1 for r in rows if r["speech_fraction"] is not None
                                and r["speech_fraction"] < sc.MIN_SPEECH_FRACTION),
        "slots_created": sorted({int(x) for r in rows for x in r["slots_created"]}),
        "n_slots_total": len(ranked),
        "slot_flips_between_windows": flips,
        "slot_seconds": {str(k): round(v, 1) for k, v in ranked},
        "dominant_slot_share": round(top / max(1e-9, speech_total), 4),
        "top2_slot_share": round(sum(v for _, v in ranked[:2]) / max(1e-9, speech_total), 4),
        "speech_s_total": round(speech_total, 1),
        "speech_share": round(speech_total / max(1e-9, audio_s), 4),
        "slots_per_minute": bucket_counts,
        "rows": rows,
    }


def run_context_agreement(samples, n_spans: int, span_s: float, context_s: float,
                          threshold: float, threads: int) -> dict:
    """Same span alone vs the same span inside more context -> label agreement.

    Alignment is a best-overlap mapping between the two label sets (the standard
    cMAP move); what is scored is the FRACTION OF TIME that agrees, because a
    label that moves with the context is not an identity, whatever its number.
    """
    import numpy as np                                            # noqa: PLC0415
    rate = sc.DEFAULT_RATE
    sdk = sc._load_sherpa_diarizer(
        sc.DEFAULT_SEG_MODEL, sc.DEFAULT_EMB_MODEL, threads,
        num_clusters=-1, threshold=threshold)

    def labels(x):
        res = sdk.process(np.asarray(x, dtype=np.float32)).sort_by_start_time()
        return [(float(s.start), float(s.end), int(s.speaker)) for s in res]

    def frame_labels(spans, n_frames, offset_s: float = 0.0):
        """Interval labels -> one label per 10 ms frame of the CENTRE window."""
        lab = np.full(n_frames, -1, dtype=np.int64)
        for a, b, k in spans:
            i0 = max(0, int(round((a - offset_s) * rate / 160)))
            i1 = min(n_frames, int(round((b - offset_s) * rate / 160)))
            if i1 > i0:
                lab[i0:i1] = k
        return lab

    step = int(span_s * rate)
    ctx = int(context_s * rate)
    half = (ctx - step) // 2
    usable = (len(samples) - ctx) // step
    if usable <= 0:
        return {"spans": 0}
    picks = [int(round(k * usable / float(n_spans))) for k in range(n_spans)]
    pairs = []
    n_frames = step // 160
    for k, p in enumerate(picks):
        centre = half + p * step
        alone = samples[centre:centre + step]
        wide = samples[centre - half:centre - half + ctx]
        a_lab = frame_labels(labels(alone), n_frames)
        b_lab = frame_labels(labels(wide), n_frames, offset_s=half / float(rate))
        speech = (a_lab >= 0) | (b_lab >= 0)
        both = (a_lab >= 0) & (b_lab >= 0)
        # best-overlap mapping, measured in frames
        mapping, score = {}, {}
        for la in set(a_lab[a_lab >= 0].tolist()):
            for lb in set(b_lab[b_lab >= 0].tolist()):
                score[(la, lb)] = int(((a_lab == la) & (b_lab == lb)).sum())
        used_b = set()
        for (la, lb), n in sorted(score.items(), key=lambda kv: -kv[1]):
            if la in mapping or lb in used_b:
                continue
            mapping[la] = lb
            used_b.add(lb)
        agree = 0
        for la, lb in mapping.items():
            agree += int(((a_lab == la) & (b_lab == lb)).sum())
        pairs.append({
            "span": k,
            "t_src": round((centre - half) / rate, 2),
            "frames": int(speech.sum()),
            "frames_both": int(both.sum()),
            "agree_frames": agree,
            "agreement": round(agree / max(1, int(speech.sum())), 4),
            "n_a": int(len(set(a_lab[a_lab >= 0].tolist()))),
            "n_b": int(len(set(b_lab[b_lab >= 0].tolist()))),
            "map": {str(k2): v for k2, v in sorted(mapping.items())},
        })
    ags = [p["agreement"] for p in pairs]
    return {
        "spans": len(pairs),
        "span_s": span_s,
        "context_s": context_s,
        "mean_agreement": round(sum(ags) / len(ags), 4) if ags else None,
        "min_agreement": round(min(ags), 4) if ags else None,
        "pairs": pairs,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--wav", required=True)
    ap.add_argument("--window-s", type=float, default=10.0)
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--limit-s", type=float, default=0.0,
                    help="use only the first N seconds of the wav")
    ap.add_argument("--agreement-spans", type=int, default=12)
    ap.add_argument("--agreement-span-s", type=float, default=30.0)
    ap.add_argument("--agreement-context-s", type=float, default=60.0)
    ap.add_argument("--no-agreement", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    x = read_wav16k(args.wav)
    if args.limit_s > 0:
        x = x[:int(args.limit_s * sc.DEFAULT_RATE)]
    result = run_arm_a(x, args.window_s, args.threshold, args.threads,
                       os.path.join(HERE, "_arm_a_payload.json"))
    result["wav"] = os.path.abspath(args.wav)
    result["audio_s"] = round(len(x) / float(sc.DEFAULT_RATE), 1)

    # exact per-slot seconds over the whole corpus, from the row payloads
    slot_total = {}
    for r in result["rows"]:
        for s in r["slots"]:
            slot_total[s] = slot_total.get(s, 0.0)
    result["slot_windows"] = {str(k): v for k, v in sorted(
        __import__("collections").Counter(
            s for r in result["rows"] for s in r["slots"]).items())}
    if not args.no_agreement:
        result["context_agreement"] = run_context_agreement(
            x, args.agreement_spans, args.agreement_span_s,
            args.agreement_context_s, args.threshold, args.threads)

    print(json.dumps(result, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
