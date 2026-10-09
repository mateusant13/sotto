#!/usr/bin/env python
"""`python -m asr.transcribe --wav FILE [--json]` -- the Sotto ASR runner (spec 02).

STDOUT IS A CONTRACT: one compact JSON object per line (NDJSON).
  {"type":"level","a":..,"p":..,"r":..,"e":..}   10 Hz, on the AUDIO clock -- the panel's wave
  {"type":"segment","i":..,"start":..,"end":..,"audio_s":..,"wall_s":..,"chars":..,"text":..}
  {"type":"done", ...}                            once: transcript + every metric
`--json` prints EXACTLY ONE line -- the `done` object -- and nothing else.
Diagnostics and the human summary go to STDERR, so `... | jq` is always safe.

Exit codes: 0 ok · 2 bad input (argparse, wrong wav format, model dir not the artefact).

Run from `src/` (`python -m asr.transcribe ...`), or as a file (`python src/asr/transcribe.py ...`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python src/asr/transcribe.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asr.constants import (  # noqa: E402
    DEFAULT_SEGMENT_MODE,
    FIXED_GRID_S,
    INTRA_OP_NUM_THREADS,
    INTER_OP_NUM_THREADS,
    MAX_SEGMENT_S,
    MODEL_DIR,
    MODEL_TOTAL_MB,
    QUANTIZATION,
)
from asr.level import compact_json  # noqa: E402
from asr.runner import TranscribeConfig, transcribe  # noqa: E402
from asr.segment import SEGMENT_MODES  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m asr.transcribe",
        description=f"Sotto ASR: int8 ONNX Parakeet-TDT ({MODEL_TOTAL_MB} MB), CPU, "
                    f"intra_op={INTRA_OP_NUM_THREADS}/inter_op={INTER_OP_NUM_THREADS}, cut on silence.",
    )
    p.add_argument("--wav", required=True, help="16 kHz mono PCM16 wav (anything else is refused)")
    p.add_argument("--model-dir", default=str(MODEL_DIR))
    p.add_argument("--quant", default=QUANTIZATION, help="onnx-asr quantization glob suffix")
    p.add_argument("--provider", default="cpu", choices=["cpu", "cuda"],
                   help="execution provider; a provider that does not LOAD is refused (exit 2), "
                        "never silently downgraded to CPU")
    p.add_argument("--offset-s", type=float, default=0.0)
    p.add_argument("--max-s", type=float, default=0.0, help="0 = to the end of the file")
    p.add_argument("--segment-mode", default=DEFAULT_SEGMENT_MODE, choices=list(SEGMENT_MODES),
                   help="'fixed' is a CONTROL ONLY: the measured trap (ratio 0.229)")
    p.add_argument("--max-seg", type=float, default=MAX_SEGMENT_S, help="segment cap; sets the RSS peak")
    p.add_argument("--chunk-s", type=float, default=FIXED_GRID_S, help="grid step, --segment-mode fixed only")
    p.add_argument("--threads", type=int, default=INTRA_OP_NUM_THREADS,
                   help="ORT intra_op_num_threads (the measured knee is 4; 0 = ORT default, forbidden)")
    p.add_argument("--inter-threads", type=int, default=INTER_OP_NUM_THREADS)
    p.add_argument("--level", default="on", choices=["on", "off"], help="10 Hz level events on stdout")
    p.add_argument("--phases", action="store_true",
                   help="instrument: split the first segment into preprocess/encode/decode")
    p.add_argument("--json", action="store_true", help="print ONLY the final done object")
    p.add_argument("--out-text", default="", help="also write the transcript to this file")
    p.add_argument("--label", default="")
    p.add_argument("--language", default=None,
                   help="language prompt; REFUSED (exit 2) unless the export declares a language "
                        "input. nemo-parakeet-tdt-0.6b-v3 does NOT, and onnx_asr ignores the "
                        "kwarg there -- so this is a refusal, not a selector.")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.threads <= 0:
        print("asr: --threads 0 (ORT's default) is FORBIDDEN: it burns 690% of a core-set for one "
              "core's throughput (docs/research/05-onnx-asr.md:86-90)", file=sys.stderr)
        return 2

    cfg = TranscribeConfig(
        wav=Path(args.wav),
        model_dir=Path(args.model_dir),
        quantization=args.quant,
        provider=args.provider,
        offset_s=args.offset_s,
        max_s=args.max_s,
        segment_mode=args.segment_mode,
        max_segment_s=args.max_seg,
        fixed_chunk_s=args.chunk_s,
        intra_op_num_threads=args.threads,
        inter_op_num_threads=args.inter_threads,
        level=(args.level == "on"),
        phases=args.phases,
        label=args.label,
        language=args.language,
    )

    done: dict | None = None

    def on_event(ev: dict) -> None:
        nonlocal done
        if ev.get("type") == "done":
            done = ev
        if args.json:
            return  # --json prints EXACTLY ONE line: the done object, below
        print(compact_json(ev), flush=True)

    try:
        done = transcribe(cfg, on_event=on_event)
    except Exception as exc:  # noqa: BLE001 -- a refusal is an exit code, not a traceback
        print(f"asr: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json and done is not None:
        print(compact_json(done), flush=True)
    if args.out_text and done is not None:
        Path(args.out_text).write_text(done["text"], encoding="utf-8")

    if done is not None:
        t = done["threads"]
        print(
            f"RESULT {done['label']}: {done['segment_mode']} {done['n_segments']} segs "
            f"(med {done['seg_median_s']}s max {done['seg_max_s']}s) audio {done['audio_s']}s "
            f"load {done['load_s']}s infer {done['infer_s']}s rtfx(infer/steady/slice)="
            f"{done['rtfx_infer']}/{done['rtfx_steady']}/{done['rtfx_slice']} "
            f"threads(intra={t['intra']},inter={t['inter']}) "
            f"provider(requested={done['provider_requested']},loaded={t['session_providers']},"
            f"lang_conditioned={t.get('language_conditioned')}) cpu(infer med/max)={done['cpu_median_pct']}/"
            f"{done['cpu_max_pct']}% cpu(load med/max)={done['cpu_load_median_pct']}/"
            f"{done['cpu_load_max_pct']}% rss(load/peak/peak_wset)={done['rss_after_load_mb']}/"
            f"{done['rss_peak_mb']}/{done['rss_peak_wset_mb']}MB "
            f"level(n={done['level']['n_events']},hz={done['level']['hz']}) chars={len(done['text'])}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
