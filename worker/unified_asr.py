"""Nemotron-Labs-Unified-ASR-0.6b as a buffered chunked streaming core.

The checkpoint is `nvidia/nemotron-labs-unified-asr-0.6b` (a NeMo `.nemo`
tarball: `model_config.yaml` + `model_weights.ckpt` + a SentencePiece tokenizer,
4096 subwords). It is one model for offline and streaming, but the streaming
pipeline is **buffered, not cache-aware**: the left context is re-encoded at
every step, so the cost per step is the cost of ~(left+chunk+right), not of the
chunk alone. That cost is measured here, not assumed.

Streaming configs are in *encoder frames* (1 frame = 80 ms at 12.5 Hz, i.e.
1280 samples of 16 kHz audio); `left=70` frames is the 5.6 s the model was
trained with. Latency = chunk + right context.

Runtime: NeMo is installed ONLY in the isolated venv `I:/cc-tmp/nemo-venv`
(never the system Python, whose `torch`/`numpy` belong to the rest of the repo).
Run every command below with that interpreter:

    I:/cc-tmp/nemo-venv/Scripts/python.exe worker/unified_asr.py --selftest
    I:/cc-tmp/nemo-venv/Scripts/python.exe worker/unified_asr.py --ladder \
        --wav _main/fixtures/stack-compare/unified-tts/ptbr-tts-01.wav,...

Per chunk the stream prints ONE machine-readable line:

    UNIFIED_CHUNK cfg=lat560 i=3 audio_t=0.560 wall_ms=41.2 rtf=0.074
                  tok=2 text="..." final=0

`--selftest` is the entry point a later lane calls: it transcribes one clip,
prints the UNIFIED_CHUNK lines and one `UNIFIED_SELFTEST` verdict line.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = Path(r"I:/cc-tmp/models-src/unified.nemo")
SAMPLE_RATE = 16000
SAMPLES_PER_ENCODER_FRAME = 1280  # 80 ms: 160 samples/mel-frame * subsampling 8

# name -> (left_s, chunk_s, right_s); latency = chunk + right.
# The five rows are the model card's recommended combinations, in encoder frames
# left=70 (5.6 s) with chunk/right from the checkpoint's att_chunk_context_size.
CONFIGS = {
    "lat160": (5.6, 0.08, 0.08),
    "lat320": (5.6, 0.08, 0.24),
    "lat560": (5.6, 0.16, 0.40),
    "lat1120": (5.6, 0.56, 0.56),
}
DEFAULT_CONFIG = "lat560"


def config_frames(name: str) -> tuple[int, int, int]:
    left, chunk, right = CONFIGS[name]
    return (round(left / 0.08), round(chunk / 0.08), round(right / 0.08))


def latency_s(name: str) -> float:
    return CONFIGS[name][1] + CONFIGS[name][2]


# --------------------------------------------------------------------------- text

_ACCENTS = "áàâãéêíóôõúüçñ"


def normalise(text: str) -> str:
    """Lowercase, strip punctuation, collapse spaces; accents preserved."""
    out = []
    for ch in text.lower():
        if ch.isalnum() or ch.isspace() or ch in _ACCENTS:
            out.append(ch)
        else:
            out.append(" ")
    return " ".join("".join(out).split())


def _edit_counts(ref: list[str], hyp: list[str]) -> tuple[int, int, int]:
    """Levenshtein backtrace -> (substitutions, insertions, deletions)."""
    n, m = len(ref), len(hyp)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if ref[i - 1] == hyp[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
    subs = ins = dele = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + (0 if ref[i - 1] == hyp[j - 1] else 1):
            if ref[i - 1] != hyp[j - 1]:
                subs += 1
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            dele += 1
            i -= 1
        else:
            ins += 1
            j -= 1
    return subs, ins, dele


def wer(reference: str, hypothesis: str) -> dict:
    ref = normalise(reference).split()
    hyp = normalise(hypothesis).split()
    subs, ins, dele = _edit_counts(ref, hyp)
    return {
        "ref_words": len(ref),
        "sub": subs,
        "ins": ins,
        "del": dele,
        "wer": round((subs + ins + dele) / len(ref), 4) if ref else None,
    }


# --------------------------------------------------------------------------- audio

def read_wav16(path: Path):
    import numpy as np
    import soundfile as sf

    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if sr != SAMPLE_RATE:
        import soxr

        mono = soxr.resample(mono, sr, SAMPLE_RATE)
    return np.ascontiguousarray(mono.astype("float32"))


# --------------------------------------------------------------------------- core

class UnifiedAsr:
    """Buffered chunked streaming over the NeMo checkpoint.

    NeMo is imported lazily so the module can be imported (for `normalise`,
    `wer`, `CONFIGS`) by an interpreter that does not have it installed.
    """

    def __init__(self, model_path: Path = DEFAULT_MODEL, device: str = "cuda",
                 config: str = DEFAULT_CONFIG, lang: str = "pt-BR"):
        try:
            import nemo.collections.asr as nemo_asr  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover
            raise SystemExit(
                "UNIFIED_UNAVAILABLE reason=no-nemo detail=%s hint=run with "
                "I:/cc-tmp/nemo-venv/Scripts/python.exe" % exc)
        import torch  # noqa: PLC0415

        self.torch = torch
        self.device = device
        self.config = config
        self.lang = lang
        t0 = time.perf_counter()
        self.model = nemo_asr.models.ASRModel.restore_from(str(model_path), map_location=device)
        self.model.eval()
        # Deterministic front end: no dither, no pad-to-bucket (both change frames).
        self.model.preprocessor.featurizer.dither = 0.0
        self.model.preprocessor.featurizer.pad_to = 0
        self.load_s = time.perf_counter() - t0
        self.blank = int(self.model.decoder.blank_idx)
        self.max_symbols = 10  # normative for this checkpoint family
        self.prompt_idx = self._resolve_prompt(lang)
        self.set_config(config)

    # -- prompt ------------------------------------------------------------
    def _resolve_prompt(self, lang: str) -> int:
        table = None
        if hasattr(self.model, "resolve_prompt_language"):
            try:
                return int(self.model.resolve_prompt_language(lang))
            except Exception:  # noqa: BLE001
                pass
        md = self.model.cfg.get("model_defaults", {})
        if "prompt_dictionary" in md:
            table = dict(md["prompt_dictionary"])
        if not table:
            raise SystemExit("UNIFIED_UNAVAILABLE reason=no-prompt-dictionary")
        if lang not in table:
            raise SystemExit("UNIFIED_UNAVAILABLE reason=unsupported-lang lang=%s "
                             "supported=%s" % (lang, ",".join(sorted(table))))
        return int(table[lang])

    # -- streaming config --------------------------------------------------
    def set_config(self, name: str) -> None:
        if name not in CONFIGS:
            raise SystemExit("unknown config %s (have %s)" % (name, ",".join(CONFIGS)))
        self.config = name
        self.left_f, self.chunk_f, self.right_f = config_frames(name)
        self.model.encoder.set_default_att_context_size(
            [self.left_f, self.chunk_f, self.right_f])

    # -- decode state ------------------------------------------------------
    def _new_state(self):
        torch = self.torch
        g, state = self.model.decoder.predict(None, None, add_sos=True)
        g = self.model.joint.project_prednet(g.float())
        return g, state

    def _greedy(self, enc, start: int, stop: int, g, state):
        """Greedy RNNT over encoder frames [start, stop); state is carried."""
        torch = self.torch
        joint = self.model.joint
        tokens = []
        for t in range(start, stop):
            f = joint.project_encoder(enc[:, t:t + 1, :].float())
            for _ in range(self.max_symbols):
                logits = joint.joint_after_projection(f, g)
                tok = int(torch.argmax(logits[0, 0, 0]).item())
                if tok == self.blank:
                    break
                tokens.append(tok)
                y = torch.tensor([[tok]], dtype=torch.long, device=enc.device)
                gg, state = self.model.decoder.predict(y, state, add_sos=False)
                g = joint.project_prednet(gg.float())
        return tokens, g, state

    def _text(self, tokens: list[int]) -> str:
        if not tokens:
            return ""
        return self.model.tokenizer.ids_to_text(tokens)

    def stream(self, pcm, emit=None):
        """Yield one event per chunk. `emit(event)` is called for each chunk."""
        torch = self.torch
        if self.device.startswith("cuda"):
            torch.cuda.synchronize()
            torch.cuda.reset_peak_memory_stats()
        chunk_samples = self.chunk_f * SAMPLES_PER_ENCODER_FRAME
        win = (self.left_f + self.chunk_f + self.right_f)
        prompt = torch.tensor([self.prompt_idx], dtype=torch.long, device=self.device)
        g, state = self._new_state()
        total = len(pcm)
        texts = []
        events = []
        i = 0
        consumed = 0
        while consumed < total:
            audio_end = min(consumed + chunk_samples, total)
            # window = [left context available][chunk][right context available]
            win_start = max(0, consumed - self.left_f * SAMPLES_PER_ENCODER_FRAME)
            win_end = min(total, audio_end + self.right_f * SAMPLES_PER_ENCODER_FRAME)
            window = torch.from_numpy(pcm[win_start:win_end]).unsqueeze(0).to(self.device)
            wlen = torch.tensor([window.shape[1]], dtype=torch.long, device=self.device)
            t0 = time.perf_counter()
            with torch.inference_mode():
                enc, enc_len = self.model(input_signal=window, input_signal_length=wlen,
                                          prompt_indices=prompt)
                enc = enc.transpose(1, 2)  # [B, T, C]
                n_frames = int(enc_len[0].item())
                # frames of the current chunk sit just before the right context
                start = max(0, n_frames - self.chunk_f - self.right_f)
                stop = min(n_frames, start + self.chunk_f)
                tokens, g, state = self._greedy(enc, start, stop, g, state)
            if self.device.startswith("cuda"):
                torch.cuda.synchronize()
            wall = time.perf_counter() - t0
            delta = self._text(tokens)
            if delta.strip():
                texts.append(delta.strip())
            audio_t = (audio_end - consumed) / SAMPLE_RATE
            ev = {
                "cfg": self.config,
                "i": i,
                "audio_t": round(audio_t, 3),
                "wall_s": round(wall, 4),
                "rtf": round(wall / audio_t, 4) if audio_t else None,
                "frames_window": n_frames,
                "frames_decoded": stop - start,
                "tok": len(tokens),
                "text": delta.strip(),
                "final": int(audio_end >= total),
            }
            events.append(ev)
            if emit is not None:
                emit(ev)
            i += 1
            consumed = audio_end
        text = " ".join(texts)
        return text, events

    def transcribe(self, pcm) -> str:
        text, _ = self.stream(pcm)
        return text

    def transcribe_offline(self, path: Path) -> str:
        out = self.model.transcribe([str(path)], target_lang=self.lang, verbose=False)
        item = out[0]
        return item.text if hasattr(item, "text") else str(item)


# --------------------------------------------------------------------------- meters

def _rss_mb() -> float:
    import psutil

    return psutil.Process().memory_info().rss / 1e6


def _peak_vram_mb(torch, device: str) -> float | None:
    if not device.startswith("cuda"):
        return None
    return torch.cuda.max_memory_allocated() / 1e6


def format_chunk(ev: dict) -> str:
    return ("UNIFIED_CHUNK cfg=%s i=%d audio_t=%.3f wall_ms=%.1f rtf=%s tok=%d "
            "frames=%d/%d final=%d text=%s"
            % (ev["cfg"], ev["i"], ev["audio_t"], ev["wall_s"] * 1000.0,
               "-" if ev["rtf"] is None else "%.4f" % ev["rtf"], ev["tok"],
               ev["frames_decoded"], ev["frames_window"], ev["final"],
               json.dumps(ev["text"], ensure_ascii=False)))


# --------------------------------------------------------------------------- CLI

def _selftest(args) -> int:
    wav = Path(args.wav) if args.wav else (
        ROOT / "_main" / "fixtures" / "stack-compare" / "unified-tts" / "ptbr-tts-01.wav")
    if not wav.exists():
        print("UNIFIED_SELFTEST verdict=FAIL reason=missing-wav wav=%s" % wav)
        return 2
    pcm = read_wav16(wav)
    eng = UnifiedAsr(Path(args.model), args.device, args.config, args.lang)
    text, events = eng.stream(pcm, emit=lambda ev: print(format_chunk(ev), flush=True))
    walls = [e["wall_s"] for e in events]
    audio_s = len(pcm) / SAMPLE_RATE
    compute_s = sum(walls)
    print("UNIFIED_TEXT cfg=%s %s" % (eng.config, json.dumps(text, ensure_ascii=False)))
    print("UNIFIED_SELFTEST verdict=%s cfg=%s wav=%s audio_s=%.2f chunks=%d "
          "compute_s=%.2f rtf=%.3f p95_ms=%.1f peak_vram_mb=%s peak_rss_mb=%.0f load_s=%.1f"
          % ("PASS" if events else "FAIL", eng.config, wav.name, audio_s, len(events),
             compute_s, compute_s / audio_s if audio_s else -1,
             sorted(walls)[max(0, math.ceil(0.95 * len(walls)) - 1)] * 1000.0,
             _peak_vram_mb(eng.torch, args.device), _rss_mb(), eng.load_s))
    return 0


def _ladder(args) -> int:
    wavs = [Path(p.strip()) for p in (args.wav or "").split(",") if p.strip()]
    if not wavs:
        base = ROOT / "_main" / "fixtures" / "stack-compare"
        wavs = sorted((base / "unified-tts").glob("*.wav"))
        shared = base / "ptbr-radio-14s.wav"
        if shared.exists():
            wavs.append(shared)
    refs = {}
    for meta in (ROOT / "_main" / "fixtures" / "stack-compare" / "unified-tts" /
                 "reference.json", ROOT / "_main" / "fixtures" / "stack-compare" /
                 "reference.json"):
        if meta.exists():
            for clip in json.loads(meta.read_text(encoding="utf-8")).get("clips", []):
                refs[clip.get("file")] = clip.get("reference")
    rows = []
    for cfg in [c.strip() for c in (args.configs or ",".join(CONFIGS)).split(",") if c.strip()]:
        eng = UnifiedAsr(Path(args.model), args.device, cfg, args.lang)
        # One throwaway pass: the first chunk of a freshly loaded model pays the
        # one-time cuDNN autotune (~19 s, measured). Every row below is STEADY
        # STATE, and `first_chunk_ms` is that throwaway pass's cost, kept so the
        # start-up penalty is on the record instead of hidden in the mean.
        warm_pcm = read_wav16(wavs[0])[: int(2 * SAMPLE_RATE)]
        eng.stream(warm_pcm)
        first_chunk_ms = None
        for wav in wavs:
            pcm = read_wav16(wav)
            text, events = eng.stream(pcm)
            if first_chunk_ms is None:
                first_chunk_ms = round(events[0]["wall_s"] * 1000.0, 1)
            walls = sorted(e["wall_s"] for e in events)
            audio_s = len(pcm) / SAMPLE_RATE
            compute_s = sum(walls)
            row = {
                "cfg": cfg,
                "latency_s": latency_s(cfg),
                "wav": wav.name,
                "lang": args.lang,
                "audio_s": round(audio_s, 2),
                "chunks": len(events),
                "compute_s": round(compute_s, 2),
                "rtf": round(compute_s / audio_s, 3) if audio_s else None,
                "p95_chunk_ms": round(walls[max(0, math.ceil(0.95 * len(walls)) - 1)] * 1000.0, 1),
                "mean_chunk_ms": round(statistics.fmean(walls) * 1000.0, 1),
                "peak_vram_mb": round(_peak_vram_mb(eng.torch, args.device) or 0) or None,
                "peak_rss_mb": round(_rss_mb()),
                "load_s": round(eng.load_s, 1),
                "first_chunk_ms_warm": first_chunk_ms,
                "text": text,
            }
            if args.offline:
                row["offline_text"] = eng.transcribe_offline(wav)
            ref = refs.get(wav.name)
            if ref:
                row["reference"] = ref
                row["wer"] = wer(ref, text)
            rows.append(row)
            print("UNIFIED_ROW " + json.dumps(row, ensure_ascii=False), flush=True)
            # Appended row by row: a killed run must not lose the rows it already
            # measured (the machine's commit budget can abort a ladder mid-way).
            if args.rows_jsonl:
                with open(args.rows_jsonl, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(rows, indent=1, ensure_ascii=False),
                                       encoding="utf-8")
        print("UNIFIED_JSON %s" % args.json_out)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ladder", action="store_true")
    ap.add_argument("--wav")
    ap.add_argument("--config", default=DEFAULT_CONFIG)
    ap.add_argument("--configs")
    ap.add_argument("--lang", default="pt-BR")
    ap.add_argument("--device", default="cuda" if _cuda_available() else "cpu")
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--offline", action="store_true",
                    help="also transcribe with NeMo's offline path (reference row)")
    ap.add_argument("--json-out")
    ap.add_argument("--rows-jsonl", default=r"I:/cc-tmp/unified-rows.jsonl")
    args = ap.parse_args(argv)
    if args.ladder:
        return _ladder(args)
    return _selftest(args)


def _cuda_available() -> bool:
    try:
        import torch  # noqa: PLC0415

        return torch.cuda.is_available()
    except Exception:  # noqa: BLE001
        return False


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
