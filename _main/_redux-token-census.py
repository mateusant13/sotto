"""FALSIFIER: are <|diarize|> (12) / <|nodiarize|> (13) / <|spkchange|> (14)
live tokens of parakeet-redux, or dead vocabulary inherited from the
Canary/Parakeet tokenizer?

Method: a faithful copy of the vendor reference loop
(worker/models/parakeet-redux-reference/transcribe.py, OnnxParakeet.greedy,
lines 235-262) with three additions and NOTHING else changed:

  1. the decoder's first input token is settable (--seed), so the model can be
     FORCED into <|diarize|> mode exactly the way a prompt-conditioned TDT is
     driven in this runner's idiom (last_token = seed, state = zeros);
  2. every greedy step records the softmax mass the joint head puts on the
     special ids, plus the rank of id 14 -- so "14 never appeared" is joined by
     "14 never had any probability", which is the stronger claim;
  3. the full token id sequence is returned, not just the decoded text.

Controls (both colours in one run, see --selftest):
  * census unit control: a hand-made token list containing 14 must be counted.
  * prompt liveness control: <|diarize|> vs <|nodiarize|> vs blank must not be
    a no-op -- if all three give byte-identical tokens the prompt path is dead
    and a "14 never appeared" reading from that arm would be vacuous.

READ ONLY on the model dir and the wav. Writes only under _main/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import soundfile as sf

HERE = Path(__file__).resolve().parent
REF = HERE.parent / "worker" / "models" / "parakeet-redux-reference" / "transcribe.py"

SPECIAL = {
    12: "<|diarize|>",
    13: "<|nodiarize|>",
    14: "<|spkchange|>",
    15: "<|audioseparator|>",
    218: "<|spk0|>",
    219: "<|spk1|>",
    8192: "<blk>(blank)",
}
WATCH = sorted(SPECIAL)


# ---------------------------------------------------------------- vocabulary
def load_vocab(path: Path):
    pieces = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line:
            piece, index = line.rsplit(" ", 1)
            pieces[int(index)] = piece
    return pieces


def census(tokens, ids):
    """The counter under test. Kept tiny so --selftest can drive it directly."""
    return {i: int(sum(1 for t in tokens if t == i)) for i in ids}


def selftest():
    ok = True
    c = census([14, 14, 3, 8192, 12], WATCH)
    checks = [("id14 counted twice", c[14] == 2), ("id12 counted once", c[12] == 1),
              ("blank counted once", c[8192] == 1), ("absent id15 is 0", c[15] == 0),
              ("absent id218 is 0", c[218] == 0)]
    for name, good in checks:
        print(f"  [{'PASS' if good else 'FAIL'}] census unit control: {name}")
        ok &= good
    # the counter must NOT be blind: feed a pure-14 list
    c2 = census([14] * 7, WATCH)
    good = c2[14] == 7
    print(f"  [{'PASS' if good else 'FAIL'}] census unit control: pure-14 list -> 7")
    ok &= good
    print("SELFTEST:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ---------------------------------------------------------------- the model
class Census:
    def __init__(self, model_dir: Path, threads: int = 2):
        cfg = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        self.durations = list(cfg["durations"])
        self.vocab_size = int(cfg["vocab_size"])
        self.max_symbols_per_step = int(cfg["max_tokens_per_step"])
        self.frame_seconds = float(cfg["encoder_frame_seconds"])
        self.pieces = load_vocab(model_dir / "vocab.txt")
        self.blank_id = int(cfg.get("blank_token_id", 8192))
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        prov = ["CPUExecutionProvider"]
        self.preprocessor = ort.InferenceSession(str(model_dir / "preprocessor.onnx"), so, providers=prov)
        self.encoder = ort.InferenceSession(str(model_dir / "encoder-model.onnx"), so, providers=prov)
        self.decoder_joint = ort.InferenceSession(str(model_dir / "decoder_joint-model.onnx"), so, providers=prov)
        st = next(i.shape for i in self.decoder_joint.get_inputs() if i.name == "input_states_1")
        self.state_shape = (int(st[0]), 1, int(st[2]))
        # sanity: the ids we are hunting must really be these pieces
        for i in WATCH:
            got = self.pieces.get(i)
            want = SPECIAL[i].split("(")[0]
            if got != want:
                raise SystemExit(f"VOCAB-MISMATCH id {i}: file says {got!r}, expected {want!r}")

    def encode(self, pcm: np.ndarray) -> np.ndarray:
        feats, lens = self.preprocessor.run(None, {
            "waveforms": pcm[None].astype(np.float32),
            "waveforms_lens": np.array([pcm.size], dtype=np.int64)})
        out, out_len = self.encoder.run(None, {"audio_signal": feats, "length": lens})
        return np.ascontiguousarray(out[0, :, : int(out_len[0])].T)

    def greedy(self, encoded: np.ndarray, seed: int | None = None):
        frames = encoded.shape[0]
        state = (np.zeros(self.state_shape, np.float32), np.zeros(self.state_shape, np.float32))
        last_token = self.blank_id if seed is None else int(seed)
        seed_used = last_token
        frame = 0
        steps = self.max_symbols_per_step * frames
        tokens: list[int] = []
        durations: list[int] = []
        target_length = np.ones(1, dtype=np.int32)
        probe = {i: {"count": 0, "max_prob": 0.0, "best_rank": 10 ** 9, "steps_top": 0}
                 for i in WATCH}
        n_steps = 0
        argmax_prob_sum = 0.0
        while frame < frames and steps > 0:
            logits, _, hidden, cell = self.decoder_joint.run(None, {
                "encoder_outputs": encoded[frame][None, :, None],
                "targets": np.array([[last_token]], dtype=np.int32),
                "target_length": target_length,
                "input_states_1": state[0], "input_states_2": state[1]})
            logits = logits[0, 0, 0]
            tok_logits = logits[: self.vocab_size]
            token = int(tok_logits.argmax())
            duration = self.durations[int(logits[self.vocab_size:].argmax())]
            # -- probe: softmax mass on the watched ids, and id 14's rank
            m = float(tok_logits.max())
            ex = np.exp(tok_logits - m)
            s = float(ex.sum())
            probs = ex / s
            argmax_prob_sum += float(probs[token])
            n_steps += 1
            for i in WATCH:
                p = float(probs[i])
                rec = probe[i]
                if p > rec["max_prob"]:
                    rec["max_prob"] = p
                if i == 14:
                    rank = int((tok_logits > tok_logits[i]).sum()) + 1
                    if rank < rec["best_rank"]:
                        rec["best_rank"] = rank
                    if rank <= 5:
                        rec["steps_top"] += 1
            for i in WATCH:
                if token == i:
                    probe[i]["count"] += 1
            if token == self.blank_id and duration == 0:
                duration = 1
            tokens.append(token)
            durations.append(duration)
            frame += duration
            if token != self.blank_id:
                last_token = token
                state = (hidden, cell)
            steps -= 1
        for i in WATCH:
            probe[i]["max_prob"] = round(probe[i]["max_prob"], 12)
            probe[i]["piece"] = self.pieces[i]
            if i != 14:
                probe[i].pop("best_rank", None)
                probe[i].pop("steps_top", None)
        return {"seed_used": seed_used, "frames": int(frames), "steps": n_steps,
                "tokens": tokens, "durations": durations,
                "mean_argmax_prob": argmax_prob_sum / max(1, n_steps),
                "probe": probe}


def read_wav(path: Path, max_seconds: float | None):
    a, sr = sf.read(str(path), dtype="float32", always_2d=True)
    a = a[:, 0]
    if sr != 16000:
        import librosa
        a = librosa.resample(a, orig_sr=sr, target_sr=16000)
    if max_seconds:
        a = a[: int(max_seconds * 16000)]
    return np.ascontiguousarray(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--wav", default="")
    ap.add_argument("--model-dir", default=str(HERE.parent / "worker" / "models" / "parakeet-redux-onnx-int4"))
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--seeds", default="none", help="comma list: none|12|13|15")
    ap.add_argument("--max-seconds", type=float, default=None)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.selftest:
        return selftest()
    if not args.wav:
        raise SystemExit("--wav required (or --selftest)")

    pcm = read_wav(Path(args.wav), args.max_seconds)
    model_dir = Path(args.model_dir)
    t0 = time.perf_counter()
    c = Census(model_dir, threads=args.threads)
    load_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    enc = c.encode(pcm)
    enc_s = time.perf_counter() - t0

    seeds = []
    for s in args.seeds.split(","):
        seeds.append(None if s.strip() in ("", "none") else int(s))

    arms = []
    for seed in seeds:
        t0 = time.perf_counter()
        r = c.greedy(enc, seed=seed)
        wall = time.perf_counter() - t0
        text = "".join(c.pieces[t] for t in r["tokens"] if t not in (8192, 0, 2)).replace("▁", " ").strip()
        counts = census(r["tokens"], WATCH)
        arms.append({
            "seed": seed,
            "seed_piece": c.pieces.get(seed) if seed is not None else "(blank 8192)",
            "wall_s": round(wall, 3),
            "n_steps": r["steps"], "frames": r["frames"],
            "n_nonblank": int(sum(1 for t in r["tokens"] if t != 8192)),
            "counts": counts,
            "probe": r["probe"],
            "mean_argmax_prob": round(r["mean_argmax_prob"], 6),
            "tokens_sha256": __import__("hashlib").sha256(
                ",".join(str(t) for t in r["tokens"]).encode()).hexdigest(),
            "text": text[:400],
        })
    doc = {
        "instrument": "_redux-token-census.py (faithful copy of transcribe.py greedy, lines 235-262)",
        "reference_loop": str(REF),
        "model_dir": str(model_dir),
        "wav": os.path.abspath(args.wav),
        "audio_s": len(pcm) / 16000.0,
        "threads": args.threads,
        "model_load_s": round(load_s, 3),
        "encode_s": round(enc_s, 3),
        "encoder_frames": int(enc.shape[0]),
        "arms": arms,
    }
    out = json.dumps(doc, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out + "\n", encoding="utf-8")
    print(out)
    print("\n--- summary ---", file=sys.stderr)
    for a in arms:
        print("seed=%-4s steps=%-6d nonblank=%-5d id14=%d id12=%d id13=%d id15=%d id218=%d "
              "id14_maxprob=%.3e id14_best_rank=%s id14_top5_steps=%s"
              % (a["seed"], a["n_steps"], a["n_nonblank"], a["counts"][14], a["counts"][12],
                 a["counts"][13], a["counts"][15], a["counts"][218],
                 a["probe"][14]["max_prob"], a["probe"][14].get("best_rank"),
                 a["probe"][14].get("steps_top")), file=sys.stderr)
        print("     sha=%s text=%r" % (a["tokens_sha256"][:16], a["text"][:160]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
