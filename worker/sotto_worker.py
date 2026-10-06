"""Sotto worker: system audio in, streamed captions out.

The panel's caption area said "Waiting for audio" forever because nothing fed
it. This is the thing that feeds it.

The pipeline, in the order the evidence forced:

  capture   sounddevice CALLBACK stream off a loopback input. NOT the blocking
            reader: PortAudio on this host refuses blocking reads with
            PaErrorCode -9999 'Blocking API not supported yet', which is why the
            first tap probe failed on every device including the Microsoft Sound
            Mapper. Measured working peak=0.883270 on "Mapeador de som da
            Microsoft - Input".
  resample  48 kHz stereo from the device -> 16 kHz mono for the model.
  features  onnxruntime_genai streaming processor, cache-aware.
  decode    encoder / decoder / joint ONNX sessions, greedy, streaming.

THE BUG THIS FILE EXISTS TO FIX. An earlier probe appended every emitted token to
a `pending` list that was never cleared between chunks, and then fed the WHOLE
list back into the decoder on every single step while ALSO carrying the LSTM
state h/c that had already consumed them. Every symbol was therefore consumed
twice, which is what produced:

    'sl  sl  slslusushhyyyeyy... c c c c c c c ... and and and and and'

The fix is one line of intent: `pending` belongs to the current chunk only,
because the carried LSTM state is the history. See reset_pending().

Output is JSON Lines on stdout, flushed, one object per line. The Electron side
consumes exactly this and nothing else.
"""

import argparse
import json
import os
import sys
import threading
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(HERE, "models", "nemotron-3.5-asr-streaming-0.6b-int4")
TARGET_SR = 16000
BLOCK_MS = 100
MAX_SYM = 10


def emit(**payload):
    """One JSON object, one line, flushed. The whole inter-process contract."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


# ── model ────────────────────────────────────────────────────────────────────
class StreamAsr:
    def __init__(self, providers):
        import onnxruntime as ort
        import onnxruntime_genai as og

        cfg = json.load(open(os.path.join(MODEL_DIR, "genai_config.json"), encoding="utf-8"))["model"]
        self.blank = cfg["blank_id"]
        self.chunk = cfg["chunk_samples"]
        self.hidden = cfg["decoder"]["hidden_size"]
        self.max_sym = cfg.get("max_symbols_per_step", MAX_SYM)

        vocab = open(os.path.join(MODEL_DIR, "vocab.txt"), encoding="utf-8").read().split("\n")
        if vocab and vocab[-1] == "":
            vocab.pop()
        self.vocab = vocab

        so = ort.SessionOptions()
        so.log_severity_level = 3
        self.enc = ort.InferenceSession(os.path.join(MODEL_DIR, "encoder.onnx"), so, providers=providers)
        self.dec = ort.InferenceSession(os.path.join(MODEL_DIR, "decoder.onnx"), so, providers=providers)
        self.joint = ort.InferenceSession(os.path.join(MODEL_DIR, "joint.onnx"), so, providers=providers)

        self.model = og.Model(MODEL_DIR)
        self.sp = self.model.create_streaming_processor()
        self.sp.set_option("use_vad", "0")

        self.cc = np.zeros((1, 24, 56, 1024), np.float32)
        self.ct = np.zeros((1, 24, 1024, 8), np.float32)
        self.ccl = np.zeros((1,), np.int64)
        self.h = np.zeros((2, 1, self.hidden), np.float32)
        self.c = np.zeros((2, 1, self.hidden), np.float32)
        self.lid = np.array([0], np.int64)

        self.labels = []
        self.n_chunks = 0
        self.wall = 0.0
        self.audio_s = 0.0

    def detok(self, ids):
        parts = []
        for i in ids:
            t = self.vocab[i]
            if t.startswith("<") and t.endswith(">"):
                continue
            parts.append(t)
        return "".join(parts).replace("▁", " ").strip()

    def reset_pending(self):
        """The fix. Pending tokens belong to the CURRENT chunk only.

        The LSTM state h/c carries the history. Re-feeding the accumulated token
        list on every step double-counts every symbol, which is exactly the
        'c c c c' / 'and and and' repetition seen in the earlier probe.
        """
        return [self.blank]

    def run_chunk(self, pcm_chunk):
        """Feed one chunk of 16 kHz float32. Returns (text, emitted_count)."""
        t0w = time.time()
        feats = self.sp.process(pcm_chunk)
        af = feats["audio_features"]
        af = af.as_numpy() if hasattr(af, "as_numpy") else np.asarray(af)

        enc_out, enc_len, self.cc, self.ct, self.ccl = self.enc.run(
            [
                "outputs",
                "encoded_lengths",
                "cache_last_channel_next",
                "cache_last_time_next",
                "cache_last_channel_len_next",
            ],
            {
                "audio_signal": af.astype(np.float32),
                "length": np.array([af.shape[1]], np.int64),
                "cache_last_channel": self.cc,
                "cache_last_time": self.ct,
                "cache_last_channel_len": self.ccl,
                "lang_id": self.lid,
            },
        )
        T = int(enc_len[0])

        targets = np.array([self.reset_pending()], np.int64)
        dout, self.h, self.c = self.dec.run(
            ["decoder_output", "h_out", "c_out"],
            {"targets": targets, "h_in": self.h, "c_in": self.c},
        )

        pending = []
        emitted = 0
        ti = k0 = 0
        chunk_ids = []
        guard = 0
        while ti < T:
            guard += 1
            if guard > self.max_sym * T + 16:
                break
            dd = np.ascontiguousarray(
                np.transpose(dout, (0, 2, 1))[:, k0:, :], dtype=np.float32
            )
            e = np.ascontiguousarray(enc_out[:, ti:T, :], dtype=np.float32)
            logits = self.joint.run(["joint_output"], {"encoder_output": e, "decoder_output": dd})[0]
            hit = None
            for tt in range(logits.shape[1]):
                flat = logits[0, tt].reshape(-1, logits.shape[3]).argmax(axis=1)
                nz = np.nonzero(flat != self.blank)[0]
                if nz.size:
                    hit = (tt, int(nz[0]))
                    break
            if hit is None:
                break
            tid = int(flat[nz[0]])
            chunk_ids.append(tid)
            self.labels.append(tid)
            pending.append(tid)
            emitted += 1
            ti += hit[0]
            k0 += hit[1] + 1
            targets = np.array([[self.blank] + pending], np.int64)
            dout, self.h, self.c = self.dec.run(
                ["decoder_output", "h_out", "c_out"],
                {"targets": targets, "h_in": self.h, "c_in": self.c},
            )

        self.n_chunks += 1
        self.audio_s += len(pcm_chunk) / TARGET_SR
        self.wall += time.time() - t0w
        return self.detok(chunk_ids), emitted


# ── capture ──────────────────────────────────────────────────────────────────
def pick_device(preferred):
    import sounddevice as sd

    devs = [d for d in sd.query_devices() if d["max_input_channels"] > 0]
    by_name = {d["name"]: d for d in devs}
    for want in preferred:
        for name, d in by_name.items():
            if want.lower() in name.lower():
                return d
    return devs[0] if devs else None


class LoopbackTap:
    """Callback stream. Blocking reads fail on this host with PaErrorCode -9999."""

    def __init__(self, device, on_block):
        import sounddevice as sd

        self.device = device
        self.on_block = on_block
        self.rate = 48000
        self.channels = min(2, device["max_input_channels"])
        self.block = int(self.rate * BLOCK_MS / 1000)
        self.peak = 0.0
        self._buf = np.zeros(0, dtype=np.float32)
        self.stream = sd.InputStream(
            device=device["index"],
            channels=self.channels,
            samplerate=self.rate,
            dtype="float32",
            blocksize=self.block,
            callback=self._cb,
        )

    def _cb(self, indata, frames, time_info, status):
        mono = indata.mean(axis=1) if indata.ndim > 1 else indata
        self.peak = max(self.peak, float(np.max(np.abs(mono))) if mono.size else 0.0)
        self._buf = np.concatenate([self._buf, mono.astype(np.float32)])
        self.on_block(mono.astype(np.float32))

    def __enter__(self):
        self.stream.start()
        return self

    def __exit__(self, *exc):
        self.stream.stop()
        self.stream.close()
        return False


def resample_to_16k(x, src=48000):
    """Linear resample. scipy is not a dependency and this is adequate for 48k->16k."""
    if src == TARGET_SR:
        return x
    n = int(len(x) * TARGET_SR / src)
    if n <= 1 or len(x) < 2:
        return np.zeros(0, dtype=np.float32)
    return np.interp(
        np.linspace(0, len(x) - 1, n),
        np.arange(len(x)),
        x,
    ).astype(np.float32)


def main():
    ap = argparse.ArgumentParser(description="Sotto caption worker: JSONL on stdout")
    ap.add_argument("--device", default=None, help="substring of the input device name")
    ap.add_argument("--wav", default=None, help="transcribe a file instead of capturing")
    ap.add_argument("--max-chunks", type=int, default=0, help="stop after N chunks (0 = forever)")
    ap.add_argument("--providers", default="CPUExecutionProvider")
    args = ap.parse_args()

    providers = [p.strip() for p in args.providers.split(",") if p.strip()]
    import onnxruntime as ort

    available = ort.get_available_providers()
    emit(type="status", state="boot", providers=available, requested=providers)
    use = [p for p in providers if p in available] or ["CPUExecutionProvider"]
    if "CPUExecutionProvider" not in use:
        use.append("CPUExecutionProvider")

    emit(type="status", state="model-loading", model=os.path.basename(MODEL_DIR))
    t0 = time.time()
    try:
        asr = StreamAsr(use)
    except Exception as exc:
        emit(type="status", state="error", stage="model-load", detail=f"{type(exc).__name__}: {exc}")
        return 2
    emit(type="status", state="model-loaded", providers=use, load_s=round(time.time() - t0, 2))

    # File mode, for proving the decoder without an audio device.
    if args.wav:
        import soundfile as sf

        pcm, _ = sf.read(args.wav, dtype="float32")
        if pcm.ndim > 1:
            pcm = pcm.mean(axis=1)
        emit(type="status", state="listening", source="file", path=os.path.basename(args.wav))
        for i in range(len(pcm) // asr.chunk):
            text, n = asr.run_chunk(pcm[i * asr.chunk : (i + 1) * asr.chunk])
            if text.strip():
                emit(
                    type="caption",
                    text=text,
                    start=round(i * asr.chunk / TARGET_SR, 2),
                    end=round((i + 1) * asr.chunk / TARGET_SR, 2),
                    model=os.path.basename(MODEL_DIR),
                )
            if args.max_chunks and i + 1 >= args.max_chunks:
                break
        emit(
            type="status",
            state="done",
            text=asr.detok(asr.labels),
            rtf=round(asr.wall / asr.audio_s, 2) if asr.audio_s else None,
            audio_s=round(asr.audio_s, 2),
            wall_s=round(asr.wall, 2),
        )
        return 0

    preferred = [
        "Mapeador de som da Microsoft - Input",
        "VoiceMeeter Output",
        "CABLE Output (VB-Audio Virtual Cable)",
    ]
    dev = pick_device([args.device] if args.device else preferred)
    if dev is None:
        emit(type="status", state="error", stage="device", detail="no input device")
        return 2
    emit(type="status", state="device", device=dev["name"], channels=dev["max_input_channels"])

    pending_audio = np.zeros(0, dtype=np.float32)
    started = time.time()
    chunks = 0

    def on_block(block):
        nonlocal pending_audio, chunks
        pending_audio = np.concatenate([pending_audio, resample_to_16k(block)])
        while len(pending_audio) >= asr.chunk:
            seg = pending_audio[: asr.chunk]
            pending_audio = pending_audio[asr.chunk :]
            try:
                text, n = asr.run_chunk(seg)
            except Exception as exc:
                emit(type="status", state="error", stage="chunk", detail=f"{type(exc).__name__}: {exc}")
                return
            chunks += 1
            if text.strip():
                emit(
                    type="caption",
                    text=text,
                    start=round((chunks * asr.chunk) / TARGET_SR, 2),
                    end=round(((chunks + 1) * asr.chunk) / TARGET_SR, 2),
                    model=os.path.basename(MODEL_DIR),
                )
            if args.max_chunks and chunks >= args.max_chunks:
                raise KeyboardInterrupt

    try:
        with LoopbackTap(dev, on_block):
            emit(type="status", state="listening", source="loopback", device=dev["name"])
            while True:
                time.sleep(0.2)
                if args.max_chunks and chunks >= args.max_chunks:
                    break
    except KeyboardInterrupt:
        pass
    emit(
        type="status",
        state="done",
        chunks=chunks,
        audio_s=round(asr.audio_s, 2),
        wall_s=round(time.time() - started, 2),
        rtf=round(asr.wall / asr.audio_s, 2) if asr.audio_s else None,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)