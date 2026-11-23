#!/usr/bin/env python
"""separate.py -- voice separation over spans of the call corpus, with a
content-keyed cache.

THE QUESTION THIS SERVES
------------------------
`worker/speaker_sidecar.py` (Arm A, what ships) does NOT separate: it labels a
window with slot ids and hands whole-window audio to the ASR. If two people
overlap, the ASR still receives both voices on one stream. Arm B is the
alternative -- separate the speakers first, transcribe each stream -- and the
only honest way to choose is to measure both on the same call audio.

WHY THIS FILE EXISTS INSTEAD OF A ONE-OFF SCRIPT
------------------------------------------------
Arm B is expensive (one MossFormer2 pass is seconds of CPU per 10 s of audio)
and the natural way to work is iterative: run a span, look at the text, run it
again. Recomputing the same span is pure waste, and worse, it makes two runs of
the same experiment silently incomparable when a parameter drifted. So every
result is cached under a key computed from the CONTENT of the span plus the
engine's identity and parameters:

    key = sha256(engine_id | params | int16 PCM of the span)

`MISS <key>` is printed before the compute, `CACHE HIT <key>` when the bytes are
reused. Run the same span twice and the second run costs a hash and a copy.

CALLABLE PER STREAM
-------------------
`separate(...)` returns `list[np.ndarray]` and is imported by the scoring code,
so one caching path serves both the library caller and the CLI. `--stream N`
prints only that stream's path, for a shell loop over voices.

ENGINES -- and what each one IS (checked, not assumed)
------------------------------------------------------
  mossformer2  REAL 2-speaker speech separation. `_main/diar-models/mossformer2/
               last_best_checkpoint.pt` is the ClearerVoice-Studio
               `MossFormer2_SS_16K` weights (its README says exactly that:
               "separates mixed-speaker speeches into individual speaker's
               speech"), 55.7 M fp32 params derived from the checkpoint's own
               key shapes: enc.conv1d (512,1,16), conv1d_encoder (512,512,1),
               conv1d_out (1024,512,1) -> 2 speakers, 24 MossFormerM blocks.
               Needs the vendored code in `_main/bench/_vendor`.
  uvr          UVR_MDXNET_9482.onnx. NOT multi-talker separation. Its ONNX
               metadata says sample_rate 44100, stems 2, n_fft 4096, and the
               graph takes [batch,4,2048,256] -- a 4-channel complex
               spectrogram, i.e. 2 stems x (re,im). That is a music model
               (UVR = Ultimate Vocal Remover): it splits a SONG into
               vocals/instrumental. On a two-person call both voices are
               "vocals", so this arm is included only so the claim "it does
               not separate two talkers" is measured rather than asserted.
  passthrough  the control arm: the mix itself as one stream. This is what the
               ASR sees today, and it is the negative arm for every text score.

NOT an engine here: the diarizer. `--engine diarizer` is refused on purpose --
Arm A produces LABELS, not audio, so pretending it emits streams would make the
two arms look comparable when they are not. Arm A is measured by
`_main/bench/arm_a_diarize.py`.

Usage
-----
    # one 30 s span from the corpus, two voices written to the cache
    python _main/bench/separate.py --engine mossformer2 --wav MIX.wav --start 300 --span-s 30

    # a whole wav (no offset), only stream 0, path on stdout
    python _main/bench/separate.py --engine mossformer2 --wav span.wav --stream 0

    # three speech-dense spans chosen by energy alone
    python _main/bench/separate.py --engine mossformer2 --wav MIX.wav --auto-spans 3 --span-s 30 --json

Cache lives in `_main/bench/.cache/sep/<engine>/<key>/`; `--list-cache` prints
what is in it and `--clear-cache` removes it.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import re
import struct
import sys
import time
import unicodedata
from pathlib import Path


def _budget_from_argv(default: int = 2) -> int:
    """`--threads N` read from the RAW argv, before argparse exists.

    The environment has to be set before numpy/torch are imported or it does
    nothing: `OMP_NUM_THREADS` is read once, at BLAS load time. argparse stays
    the authority for the code paths; this scan exists only to make the env
    truthful, and main() calls `_declare_threads()` so the two can be compared.
    """
    raw = sys.argv[1:]
    val = None
    for i, a in enumerate(raw):
        if a == "--threads" and i + 1 < len(raw):
            val = raw[i + 1]
        elif a.startswith("--threads="):
            val = a.split("=", 1)[1]
    try:
        return max(1, int(val)) if val else default
    except (TypeError, ValueError):
        return default


#: The PROCESS budget -- torch's pool and ONNX Runtime's intra-op pool SUM to
#: this, they do not each get it. Measured on this box: `--threads 2` with both
#: libraries loaded held 4 threads and sampled 250.9-386.4 % of one core, and
#: the owner felt it as a stutter.
PROCESS_BUDGET = _budget_from_argv()
for _k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_k] = str(PROCESS_BUDGET)

import numpy as np  # noqa: E402  -- imported AFTER the env above, on purpose

_DECLARED: set = set()


def _declare_threads(stage: str, torch_threads=None, ort_intra=None) -> None:
    """Print the budget ONCE PER STAGE, with the numbers the libraries hold.

    A ceiling the process does not print is a claim, not a measurement. The
    stages are the proof that the two pools SUM to the budget: deduping on
    "declared" printed the torch pool and hid the ASR pool that was handed the
    remainder (measured: no `asr-load` line ever appeared in a scored run).
    """
    if stage in _DECLARED:
        return
    _DECLARED.add(stage)
    env = {k: os.environ.get(k) for k in
           ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")}
    print("THREADS process_budget=%d torch=%s ort_intra=%s env OMP=%s MKL=%s OPENBLAS=%s stage=%s"
          % (PROCESS_BUDGET,
             "n/a" if torch_threads is None else torch_threads,
             "n/a" if ort_intra is None else ort_intra,
             env["OMP_NUM_THREADS"], env["MKL_NUM_THREADS"], env["OPENBLAS_NUM_THREADS"],
             stage), file=sys.stderr, flush=True)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
CACHE_ROOT = os.path.join(HERE, ".cache", "sep")
MOSSFORMER_CKPT = os.path.join(REPO, "_main", "diar-models", "mossformer2",
                               "last_best_checkpoint.pt")
UVR_ONNX = os.path.join(REPO, "_main", "diar-models", "UVR_MDXNET_9482.onnx")
VENDOR = os.path.join(HERE, "_vendor")
#: The batch ASR that ships in the product (`parakeet-redux`, ONNX int4). It is
#: imported BY PATH, never edited: `--score` must measure the same engine the
#: worker runs, not a copy of it.
ASR_DIR = os.path.join(REPO, "worker", "models", "parakeet-redux-onnx-int4")
RATE = 16000

#: Encoder stride of MossFormer2 is kernel_size//2 = 8, so one feature frame is
#: 8 samples: 125 frames/s of audio.
FRAME_STRIDE = 8


# ---------------------------------------------------------------------------
# cache
# ---------------------------------------------------------------------------

def span_key(engine: str, params: dict, samples: np.ndarray) -> str:
    """Content key: engine identity + parameters + the PCM itself.

    The PCM is quantised to int16 before hashing because that is exactly what
    lands in the cache as a wav; able to hash float32 and cache int16 would key
    two runs differently for bytes that are equal on disk.
    """
    h = hashlib.sha256()
    h.update(engine.encode("utf-8"))
    h.update(b"\x00")
    h.update(json.dumps(params, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    h.update(b"\x00")
    pcm = np.clip(np.round(np.asarray(samples, dtype=np.float64) * 32767.0),
                  -32768, 32767).astype("<i2")
    h.update(struct.pack("<I", pcm.size))
    h.update(pcm.tobytes())
    return h.hexdigest()


def cache_dir(engine: str, key: str) -> str:
    return os.path.join(CACHE_ROOT, engine, key[:2], key)


def cache_load(engine: str, key: str, n_streams: int):
    d = cache_dir(engine, key)
    meta_path = os.path.join(d, "meta.json")
    if not os.path.isfile(meta_path):
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as fh:
            meta = json.load(fh)
    except (OSError, ValueError):
        return None
    if int(meta.get("n_streams", -1)) != n_streams:
        return None
    out = []
    for i in range(n_streams):
        p = os.path.join(d, "s%02d.wav" % i)
        if not os.path.isfile(p):
            return None
        out.append(read_wav(p))
    return out, meta


def cache_store(engine: str, key: str, streams, meta: dict) -> str:
    import soundfile as sf
    d = cache_dir(engine, key)
    os.makedirs(d, exist_ok=True)
    for i, s in enumerate(streams):
        sf.write(os.path.join(d, "s%02d.wav" % i),
                 np.clip(np.asarray(s, dtype=np.float32), -1.0, 1.0),
                 meta.get("rate", RATE), subtype="PCM_16")
    meta = dict(meta)
    meta["n_streams"] = len(streams)
    meta["key"] = key
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, sort_keys=True)
    return d


def _rss_mb():
    """Process RSS in MB, or None when psutil is unavailable."""
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1e6, 1)
    except Exception:
        return None


class PeakRSS:
    """Peak resident MB of this process, sampled while a model runs.

    A single `rss` reading after the call understates a torch model by ~2x,
    because the interpreter hands pages back between the load and the exit.
    The peak is the number that decides whether this fits next to the ASR, so
    it is sampled, not guessed. `_cage.py` reports the tree's peak too; this one
    is the figure the cache records, so a rerun reads it without a cage.
    """

    def __init__(self, every_s: float = 0.2, device: str = "cpu") -> None:
        self.peak = 0.0
        self.thread_peak = 0
        self.device = device
        self.gpu_allocated_peak_mb = None
        self.gpu_reserved_peak_mb = None
        self.gpu_nvml_baseline_free_mib = None
        self.gpu_nvml_min_free_mib = None
        self.gpu_nvml_peak_used_mib = None
        self._nvml = None
        self._nvml_handle = None
        self._every = every_s
        self._stop = None
        self._thread = None

    def __enter__(self):
        if self.device.startswith("cuda"):
            try:
                import pynvml
                pynvml.nvmlInit()
                self._nvml = pynvml
                self._nvml_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                self._sample_gpu()
                import torch
                torch.cuda.synchronize()
                self.gpu_reserved_baseline_mb = torch.cuda.memory_reserved() / 1e6
                torch.cuda.reset_peak_memory_stats()
            except Exception as exc:
                raise SystemExit("separate: cannot measure CUDA device memory with NVML: %s"
                                 % type(exc).__name__)
        try:
            import psutil
            import threading
            self._proc = psutil.Process()
            self._stop = threading.Event()
            self.thread_peak = self._proc.num_threads()

            def run():
                while not self._stop.is_set():
                    try:
                        self.peak = max(self.peak, self._proc.memory_info().rss / 1e6)
                        self.thread_peak = max(self.thread_peak, self._proc.num_threads())
                        self._sample_gpu()
                    except Exception:
                        pass
                    self._stop.wait(self._every)

            self._thread = threading.Thread(target=run, daemon=True)
            self._thread.start()
        except Exception:
            self._thread = None
        return self

    def _sample_gpu(self) -> None:
        if self._nvml is None or self._nvml_handle is None:
            return
        info = self._nvml.nvmlDeviceGetMemoryInfo(self._nvml_handle)
        free_mib = info.free / (1024 * 1024)
        used_mib = info.used / (1024 * 1024)
        self.gpu_nvml_min_free_mib = (free_mib if self.gpu_nvml_min_free_mib is None
                                      else min(self.gpu_nvml_min_free_mib, free_mib))
        self.gpu_nvml_peak_used_mib = (used_mib if self.gpu_nvml_peak_used_mib is None
                                       else max(self.gpu_nvml_peak_used_mib, used_mib))
        if self.gpu_nvml_baseline_free_mib is None:
            self.gpu_nvml_baseline_free_mib = free_mib

    def __exit__(self, *exc):
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=2.0)
        try:
            import psutil
            self.peak = max(self.peak, psutil.Process().memory_info().rss / 1e6)
            self.thread_peak = max(self.thread_peak, psutil.Process().num_threads())
        except Exception:
            pass
        if self.device.startswith("cuda"):
            try:
                import torch
                torch.cuda.synchronize()
                self.gpu_allocated_peak_mb = torch.cuda.max_memory_allocated() / 1e6
                self.gpu_reserved_peak_mb = torch.cuda.max_memory_reserved() / 1e6
            except Exception as exc:
                self.gpu_error = type(exc).__name__
            try:
                self._sample_gpu()
            finally:
                if self._nvml is not None:
                    self._nvml.nvmlShutdown()
        return False


def read_wav(path: str) -> np.ndarray:
    import soundfile as sf
    x, sr = sf.read(path, dtype="float32", always_2d=False)
    if getattr(x, "ndim", 1) > 1:
        x = x.mean(axis=1)
    if sr != RATE:
        raise SystemExit("separate: %s is %d Hz, expected %d" % (path, sr, RATE))
    return np.ascontiguousarray(x, dtype=np.float32)


# ---------------------------------------------------------------------------
# MossFormer2 -- real speech separation
# ---------------------------------------------------------------------------

_MOSS_CACHE: dict = {}


def _mossformer_model(threads: int = 2, device: str = "cpu"):
    """Build MossFormer2_SS_16K and load the vendored ClearerVoice checkpoint.

    `mmap=True` matters: the file holds 669 MB (model + Adam state), of which
    only the 223 MB `model` dict is needed. Mapping instead of reading keeps the
    transient allocation to the tensors actually copied into the module -- on a
    box whose free RAM swings by gigabytes in seconds, that is the difference
    between measuring and swapping.
    """
    key = ("moss", threads, device)
    if key in _MOSS_CACHE:
        return _MOSS_CACHE[key]
    import torch
    #: torch's pool IS the process budget while no other library is loaded.
    torch.set_num_threads(int(min(threads, PROCESS_BUDGET)))
    torch.set_grad_enabled(False)
    _declare_threads("mossformer2-load", torch_threads=torch.get_num_threads())
    if device.startswith("cuda"):
        torch.cuda.init()
    if VENDOR not in sys.path:
        sys.path.insert(0, VENDOR)
    from mossformer2.mossformer2 import MossFormer

    # The checkpoint IS the inner MossFormer: its keys start at `enc.`/
    # `mask_net.`, not at `model.enc.`. Building the `MossFormer2_SS_16K`
    # wrapper (which owns `self.model = MossFormer(...)`) makes every key
    # miss by exactly that one prefix -- 1099 missing / 1099 unexpected,
    # measured. So the wrapper is not the object to instantiate here.
    model = MossFormer(in_channels=512, out_channels=512, num_blocks=24,
                       kernel_size=16, norm="ln", num_spks=2,
                       skip_around_intra=True, use_global_pos_enc=True,
                       max_length=20000)
    sd = torch.load(MOSSFORMER_CKPT, map_location="cpu", mmap=True)
    state = sd["model"] if isinstance(sd, dict) and "model" in sd else sd
    missing, unexpected = model.load_state_dict(state, strict=False)
    if missing or unexpected:
        raise SystemExit("separate: checkpoint does not fit the model: "
                         "missing=%d unexpected=%d (%s | %s)"
                         % (len(missing), len(unexpected), missing[:3], unexpected[:3]))
    model.eval()
    model.to(torch.device(device))
    nparam = sum(p.numel() for p in model.parameters())
    _MOSS_CACHE[key] = (model, torch, nparam, device)
    return _MOSS_CACHE[key]


def resolve_moss_device(requested: str) -> tuple[str, dict]:
    """Resolve auto inside the caged process and record the actual accelerator."""
    import torch
    torch.set_num_threads(PROCESS_BUDGET)
    _declare_threads("mossformer2-device-resolve", torch_threads=torch.get_num_threads())
    available = bool(torch.cuda.is_available())
    if requested == "cuda" and not available:
        raise SystemExit("separate: --device cuda requested, but CUDA is unavailable")
    device = "cuda" if requested == "auto" and available else requested
    if device == "auto":
        device = "cpu"
    details = {"requested": requested, "resolved": device}
    if device.startswith("cuda"):
        details["name"] = torch.cuda.get_device_name(0)
        try:
            import pynvml
            pynvml.nvmlInit()
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                details["nvml_free_mib_before"] = round(info.free / (1024 * 1024), 1)
                details["nvml_total_mib"] = round(info.total / (1024 * 1024), 1)
            finally:
                pynvml.nvmlShutdown()
        except Exception as exc:
            raise SystemExit("separate: --device cuda requires working NVML for the VRAM floor: %s"
                             % type(exc).__name__)
    print("DEVICE " + json.dumps(details, sort_keys=True), file=sys.stderr, flush=True)
    return device, details


def _hash_file(path: str, *, mib_s: float = 0.0, label: str = "file") -> str:
    """Hash file contents with a measured-rate ceiling when one is requested."""
    if mib_s < 0:
        raise ValueError("hash rate must be non-negative")
    h = hashlib.sha256()
    block_size = 1024 * 1024
    total = 0
    started = time.perf_counter()
    with open(path, "rb") as fh:
        while True:
            block = fh.read(block_size)
            if not block:
                break
            h.update(block)
            total += len(block)
            elapsed = time.perf_counter() - started
            if mib_s:
                target = total / (mib_s * 1024 * 1024)
                if target > elapsed:
                    time.sleep(target - elapsed)
            if total and total % (64 * block_size) < len(block):
                elapsed = max(time.perf_counter() - started, 1e-9)
                print("HASH_PROGRESS label=%s bytes=%d elapsed_s=%.1f mib_s=%.2f"
                      % (label, total, elapsed, total / elapsed / (1024 * 1024)),
                      file=sys.stderr, flush=True)
    elapsed = max(time.perf_counter() - started, 1e-9)
    digest = h.hexdigest()
    print("HASH_DONE label=%s bytes=%d elapsed_s=%.2f average_mib_s=%.2f sha256=%s"
          % (label, total, elapsed, total / elapsed / (1024 * 1024), digest),
          file=sys.stderr, flush=True)
    return digest


def mossformer_identity(device: str, hash_mib_s: float) -> dict:
    """Content identity for weights, this runner and every vendored Python file."""
    checkpoint_hash = _hash_file(MOSSFORMER_CKPT, mib_s=hash_mib_s,
                                 label="mossformer-checkpoint")
    source_paths = [Path(__file__).resolve(), *sorted(Path(VENDOR).rglob("*.py"))]
    code_hash = hashlib.sha256()
    for path in source_paths:
        rel = os.path.relpath(str(path), REPO).replace("\\", "/")
        code_hash.update(rel.encode("utf-8") + b"\x00")
        code_hash.update(bytes.fromhex(_hash_file(str(path))))
    return {"device": device, "checkpoint_sha256": checkpoint_hash,
            "code_sha256": code_hash.hexdigest()}


def _xfade(n: int) -> np.ndarray:
    w = np.ones(n, dtype=np.float32)
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    w[: n // 2] = ramp[: n // 2]
    w[n // 2:] = 1.0 - ramp[n // 2:]
    return w


def _chunk_window(chunk: int, fade: int, ramp_up: bool, ramp_down: bool) -> np.ndarray:
    """The overlap-add window for ONE chunk: flat, with `fade`-sample ramps at the ends.

    This used to be `_xfade(fade)` -- a window `fade` samples long applied to a
    `chunk`-sample block, which is a broadcast error (`(160000,) (4000,)`), so
    the arm never produced a stream. The window belongs to the CHUNK, and the
    ramp length is the overlap with its neighbour.
    """
    w = np.ones(chunk, dtype=np.float32)
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
        if ramp_up:
            w[:fade] = ramp
        if ramp_down:
            w[chunk - fade:] = ramp[::-1]
    return w


def run_mossformer2(samples: np.ndarray, threads: int = 2, chunk_s: float = 10.0,
                    fade_s: float = 0.25, scale: str = "match",
                    device: str = "cpu") -> list[np.ndarray]:
    """Separate into 2 streams, in chunks with a linear crossfade.

    Chunking is not an optimisation detail: the encoder runs at 125 frames/s, so
    a 30 s span is 3750 frames and a 10 min file is 75 000. The product cannot
    hold the 10 min in one attention pass on this box, and measuring a shape the
    product cannot run would pick an arm nobody can ship. `chunk_s` is therefore
    a documented parameter of the arm, not a hidden default.

    `scale="match"` is NOT cosmetic. Measured: the raw estimate comes out
    **+17.3 dB hot** (stream RMS −1.06 dB against a −18.37 dB mixture), so
    written straight to PCM16 it clipped **72 % of its samples** (690 600 of
    960 000 at |x| ≥ 0.999) — a measurement of the clipping, not of the
    separator. A mask-based separator's estimate lives on the MIXTURE's scale;
    the ClearerVoice framework normalises it and this loader does the same: one
    joint factor per chunk, `input_rms / estimate_rms`, applied to BOTH streams,
    so their relative balance is untouched. `scale="raw"` is kept so the clipping
    itself stays reproducible.

    The FIRST chunk does not ramp up and the LAST does not ramp down: a window
    that ramps at a file edge would divide real audio by a small weight and
    fade the first and last 250 ms of every stream into silence.
    """
    model, torch, _, device = _mossformer_model(threads, device)
    x = np.ascontiguousarray(np.asarray(samples, dtype=np.float32))
    n = x.size
    if n == 0:
        return [x.copy(), x.copy()]
    chunk = max(int(chunk_s * RATE), RATE)
    fade = int(min(max(fade_s, 0.0), chunk_s / 4.0) * RATE)
    hop = max(1, chunk - fade)
    starts = list(range(0, n, hop))
    out = np.zeros((2, n + 2 * chunk), dtype=np.float32)
    wsum = np.zeros(n + 2 * chunk, dtype=np.float32)
    for s0 in starts:
        seg = x[s0: s0 + chunk]
        m = int(seg.size)
        if m < 1600:                                    # < 0.1 s: pad, do not forward it
            m = 1600
        if seg.size < m:
            seg = np.pad(seg, (0, m - seg.size))
        w = _chunk_window(m, fade, ramp_up=s0 > 0, ramp_down=s0 + chunk < n)
        t = torch.from_numpy(seg)[None, :].to(device)
        est = model(t)
        if device.startswith("cuda"):
            torch.cuda.synchronize()
        ys = []
        for spk in range(2):
            y = est[spk][0].detach().to("cpu").numpy().astype(np.float32)
            if y.size < m:
                y = np.pad(y, (0, m - y.size))
            ys.append(y[:m])
        if scale == "match":
            est_rms = float(np.sqrt(np.mean(np.square(np.stack(ys), dtype=np.float64))))
            in_rms = float(np.sqrt(np.mean(np.square(seg.astype(np.float64)))))
            if est_rms > 1e-9 and in_rms > 1e-9:
                g = in_rms / est_rms
                ys = [y * np.float32(g) for y in ys]
        for spk in range(2):
            out[spk, s0: s0 + m] += ys[spk] * w
        wsum[s0: s0 + m] += w
    wsum[wsum == 0] = 1.0
    streams = [out[spk, :n] / wsum[:n] for spk in range(2)]
    if scale == "match":
        # RMS matching does not bound the PEAK: measured 1.381 after matching, and
        # PCM16 writes clip at 1.0. One common factor keeps the split intact.
        peak = float(max(np.max(np.abs(streams[0])), np.max(np.abs(streams[1]))))
        if peak > 0.999:
            g = np.float32(0.999 / peak)
            streams = [y * g for y in streams]
    return streams


# ---------------------------------------------------------------------------
# UVR MDX-Net -- music vocal/instrumental split, kept as the refuted arm
# ---------------------------------------------------------------------------

def run_uvr(samples: np.ndarray, threads: int = 2, seg_frames: int = 256,
            overlap: float = 0.25) -> list[np.ndarray]:
    """Run UVR_MDXNET_9482 exactly as its metadata declares it.

    Metadata, read from the graph itself (`get_modelmeta().custom_metadata_map`):
    model_type UVR, sample_rate 44100, n_fft 4096, hop 1024, center 1, hann,
    dim_f 2048, dim_t 256, dim_c 4, stems 2; input and output both
    [batch, 4, 2048, 256]. Four channels = two complex spectrograms stacked
    (stereo re/im), and the graph emits 4 channels = 2 stems x (re, im).

    Feeding it a 16 kHz mono call therefore requires a 44.1 kHz resample and a
    mono-to-stereo duplication first -- an admission in itself, since a speech
    separator for this product would have been trained at 16 kHz like the ASR
    it feeds.

    This arm exists to MEASURE the claim "UVR does not separate two talkers",
    not to assert it: UVR is a music separator (vocal/instrumental), so both
    voices are "vocals" and should land in the SAME stem. The STFT/iSTFT is
    librosa's, one owner, instead of a hand-rolled one.
    """
    import librosa
    import onnxruntime as ort
    import scipy.signal as sps

    x = np.asarray(samples, dtype=np.float32)
    g = np.gcd(int(RATE), 44100)
    x44 = sps.resample_poly(x, 44100 // g, int(RATE) // g).astype(np.float32)
    n_fft, hop, dim_f = 4096, 1024, 2048
    spec = librosa.stft(x44, n_fft=n_fft, hop_length=hop, win_length=n_fft,
                        window="hann", center=True)[:dim_f]        # [2048, T], Nyquist dropped
    tframes = spec.shape[1]
    so = ort.SessionOptions()
    so.intra_op_num_threads = int(min(threads, PROCESS_BUDGET))
    _declare_threads("uvr-load", ort_intra=so.intra_op_num_threads)
    sess = ort.InferenceSession(UVR_ONNX, so, providers=["CPUExecutionProvider"])
    in_name = sess.get_inputs()[0].name
    step = max(1, int(seg_frames * (1.0 - overlap)))
    acc = np.zeros((2, dim_f, tframes), dtype=np.complex64)
    wsum = np.zeros(tframes, dtype=np.float32)
    w = _xfade(seg_frames)                                        # triangle, sums to 1
    for f0 in range(0, max(1, tframes - seg_frames + 1), step):
        take = min(seg_frames, tframes - f0)
        blk = np.zeros((dim_f, seg_frames), dtype=np.complex64)
        blk[:, :take] = spec[:, f0: f0 + take]
        # dim_c 4 = stereo re/im: the mono call is duplicated into both channels
        inp = np.stack([blk.real, blk.imag, blk.real, blk.imag], axis=0)[None]
        est = sess.run(None, {in_name: inp.astype(np.float32)})[0][0]
        for spk in range(2):
            c = (est[2 * spk] + 1j * est[2 * spk + 1]).astype(np.complex64)
            acc[spk, :, f0: f0 + take] += c[:, :take] * w[:take]
        wsum[f0: f0 + take] += w[:take]
    wsum[wsum == 0] = 1.0
    out = []
    for spk in range(2):
        full = np.zeros((dim_f + 1, tframes), dtype=np.complex64)
        full[:dim_f] = acc[spk] / wsum[None, :]
        y44 = librosa.istft(full, hop_length=hop, win_length=n_fft,
                            window="hann", center=True, length=len(x44))
        out.append(sps.resample_poly(np.asarray(y44, np.float32),
                                     int(RATE) // g, 44100 // g).astype(np.float32))
    return out


def run_passthrough(samples: np.ndarray, **_) -> list[np.ndarray]:
    x = np.asarray(samples, dtype=np.float32)
    return [x.copy()]


ENGINES = {
    "mossformer2": (run_mossformer2, 2),
    "uvr": (run_uvr, 2),
    "passthrough": (run_passthrough, 1),
}


# ---------------------------------------------------------------------------
# --score: production Redux consumer; metrics only, no transcript text or WER
# ---------------------------------------------------------------------------
# The shipped Consumer/OnnxBackend is the scorer. Legacy copied decode code is
# intentionally removed so the benchmark cannot silently score a different path.

REDUX_EAGER_GRAPHS = (
    "preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx",
)
REDUX_VAD_GRAPH = "vad-model.onnx"
SCORE_STREAM_NAMES = frozenset(("mix", "stem_0", "stem_1"))


def _score_gpu_preflight(args) -> dict:
    """Refuse unsupported score runs before the WAV is opened.

    This checks the installed CUDA device census and the same ORT fallback
    controls that Redux's session proxy uses. The live session readback is
    checked again after model construction and before the first transcribe.
    """
    if args.engine != "mossformer2":
        raise RuntimeError("--score requires the MossFormer2 speech separator")
    if args.device != "cuda":
        raise RuntimeError("--score requires explicit --device cuda; auto/CPU is not accepted")
    if args.no_cache:
        raise RuntimeError("--score requires the bounded content cache for separated stems")
    if PROCESS_BUDGET < 2:
        raise RuntimeError("--score needs a process budget of at least 2 pools")
    separator_threads = max(1, PROCESS_BUDGET // 2)
    asr_threads = int(args.asr_threads or max(1, PROCESS_BUDGET - separator_threads))
    if separator_threads + asr_threads > PROCESS_BUDGET:
        raise RuntimeError("--score separator plus Redux threads exceed --threads process budget")
    if args.auto_spans > 8 or args.span_s <= 0 or args.span_s > 30:
        raise RuntimeError("--score is bounded to 1..30 s spans and at most 8 spans")
    for name in ("transcribe.py", "preprocessor.onnx", "encoder-model.onnx",
                 "decoder_joint-model.onnx"):
        if not os.path.isfile(os.path.join(ASR_DIR, name)):
            raise RuntimeError("--score Redux artifact is missing: %s" % name)

    worker_dir = os.path.join(REPO, "worker")
    if worker_dir not in sys.path:
        sys.path.insert(0, worker_dir)
    import onnxruntime as ort
    import sotto_worker

    options_factory = getattr(ort, "SessionOptions", None)
    session_type = getattr(ort, "InferenceSession", None)
    if not callable(options_factory) or not callable(session_type):
        raise RuntimeError("--score installed ONNX Runtime lacks session APIs")
    options = options_factory()
    if (not callable(getattr(options, "add_session_config_entry", None))
            or not callable(getattr(options, "get_session_config_entry", None))
            or not callable(getattr(session_type, "disable_fallback", None))):
        raise RuntimeError("--score ONNX Runtime cannot verify/disable session fallback")

    sotto_worker._add_cuda_dll_dirs()
    sotto_worker._preload_cuda_runtime(ort)
    registered = sotto_worker.asr_cuda_device_registered(ort)
    if registered is not True:
        raise RuntimeError("--score CUDA device census is not positive: %r" % registered)
    separator_device, device_details = resolve_moss_device("cuda")
    if separator_device != "cuda":
        raise RuntimeError("--score MossFormer2 CUDA device did not read back")
    return {
        "cuda_device_registered": True,
        "ort_fallback_controls": "SessionOptions readback + enable_fallback=0 + disable_fallback",
        "model_dir": ASR_DIR,
        "separator_device": device_details,
    }


def read_audio_after_score_preflight(args, preflight, wav_reader):
    """Keep the fail-closed score gate strictly before opening input audio."""
    score_readback = preflight(args) if args.score else None
    private_bundle = (_load_certas_reference_bundle(args.wav)
                      if getattr(args, "score_certas", False) else None)
    return wav_reader(args.wav), score_readback, private_bundle


def _session_guard_readback(session) -> bool:
    """Read the Python InferenceSession switch after Redux disabled fallback."""
    return getattr(session, "_enable_fallback", None) is False


def require_redux_gpu_backend(engine) -> dict:
    """Require live device, provider, option, and session fallback readbacks."""
    if getattr(engine, "device", None) != "cuda":
        raise RuntimeError("--score Redux backend did not read back device=cuda")
    if getattr(engine, "cpu_execution_policy", None) != "cuda-only":
        raise RuntimeError("--score Redux CPU execution policy is not cuda-only")
    model = getattr(engine, "_model", None)
    if model is None or getattr(model, "cpu_ep_fallback_disabled", None) is not True:
        raise RuntimeError("--score Redux model lacks CPU EP fallback-disabled readback")

    # Materialize deferred VAD now, without decoding audio. Its session must
    # have the same guards before transcribe() is allowed to reach speech_regions.
    if getattr(model, "_sotto_vad_deferred", False):
        factory = getattr(model, "_sotto_session_factory", None)
        if not callable(factory):
            raise RuntimeError("--score deferred Redux VAD has no guarded session factory")
        model.vad = factory(REDUX_VAD_GRAPH)
        model._sotto_vad_deferred = False

    sessions = {
        "preprocessor.onnx": getattr(model, "preprocessor", None),
        "encoder-model.onnx": getattr(model, "encoder", None),
        "decoder_joint-model.onnx": getattr(model, "decoder_joint", None),
    }
    if getattr(model, "_sotto_vad_exists", False):
        sessions[REDUX_VAD_GRAPH] = getattr(model, "vad", None)
    providers = getattr(engine, "provider_readback", None)
    policy = getattr(engine, "thread_policy", None)
    options = policy.get("session_options_readback") if isinstance(policy, dict) else None
    fallback = policy.get("runtime_fallback_readback") if isinstance(policy, dict) else None
    expected = set(sessions)
    if (not isinstance(providers, dict) or set(providers) != expected
            or not isinstance(options, dict) or set(options) != expected
            or not isinstance(fallback, dict)):
        raise RuntimeError("--score Redux GPU/readback graph inventory is incomplete")

    provider_report = {}
    for graph, session in sessions.items():
        names = providers.get(graph)
        row = options.get(graph)
        if (session is None or not isinstance(names, (list, tuple))
                or "CUDAExecutionProvider" not in names
                or not isinstance(row, dict)
                or row.get("disable_cpu_ep_fallback") != "1"
                or row.get("runtime_fallback_disabled") is not True
                or not _session_guard_readback(session)
                or (graph != REDUX_VAD_GRAPH and fallback.get(graph) is not True)):
            raise RuntimeError("--score Redux CUDA/fallback readback failed for %s" % graph)
        provider_report[graph] = list(names)
    return {
        "device": "cuda",
        "cpu_execution_policy": "cuda-only",
        "provider_readback": provider_report,
        "fallback_disabled_graphs": sorted(expected),
    }


def create_score_backend(consumer_factory, release_separator):
    """Release separator VRAM before constructing the production ASR consumer."""
    separator_release = release_separator()
    consumer = consumer_factory()
    engine = consumer.engine()
    readback = require_redux_gpu_backend(engine)
    return consumer, engine, {"separator_release": separator_release, "asr": readback}


def _transcribe_private(engine, pcm: np.ndarray):
    """Return text only to the caller's private scoring stack."""
    pcm = np.ascontiguousarray(np.asarray(pcm, dtype=np.float32))
    audio_s = pcm.size / float(RATE)
    result = engine.transcribe(pcm)
    if isinstance(result, tuple) and result:
        text = str(result[0] or "")
        segments = result[1] if len(result) > 1 else ()
    elif isinstance(result, dict):
        text = str(result.get("text") or "")
        segments = result.get("segments") or ()
    else:
        raise RuntimeError("--score Redux consumer returned an unsupported result")
    if len(text) > 16384:
        raise RuntimeError("--score transcript exceeds its private scoring cap")
    return text, audio_s, len(segments)


def _score_one(engine, pcm: np.ndarray, name: str) -> dict:
    if name not in SCORE_STREAM_NAMES:
        raise ValueError("score stream labels must remain anonymous")
    text, audio_s, segment_count = _transcribe_private(engine, pcm)
    return _public_score(text, audio_s, segment_count, name)


def _public_score(text: str, audio_s: float, segment_count: int, name: str) -> dict:
    if name not in CERTAS_STREAMS:
        raise ValueError("score stream labels must remain anonymous")
    words = len(text.split())
    # Keep only reproducibility metrics; the transcript itself is discarded.
    return {
        "stream": name,
        "audio_s": round(audio_s, 3),
        "words": words,
        "wps": round(words / audio_s, 4) if audio_s else 0.0,
        "segments": segment_count,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def score_inputs(engine, named_audio, retain_private_text: bool = False):
    """Run distinct mix/stem calls through one already-attested backend."""
    prepared = []
    seen = set()
    for index, item in enumerate(named_audio):
        if index >= 3:
            raise RuntimeError("--score accepts at most one mix and two anonymous stems")
        name, pcm = item
        if name not in SCORE_STREAM_NAMES or name in seen:
            raise ValueError("score stream labels must be unique and anonymous")
        seen.add(name)
        prepared.append((name, pcm))
    if "mix" not in seen:
        raise RuntimeError("--score requires the mix before any stem is transcribed")
    rows = {}
    private_texts = {}
    for name, pcm in prepared:
        text, audio_s, segment_count = _transcribe_private(engine, pcm)
        rows[name] = _public_score(text, audio_s, segment_count, name)
        if retain_private_text:
            private_texts[name] = text
    return (rows, private_texts) if retain_private_text else rows


CERTAS_STREAMS = frozenset(("mix", "stem_0", "stem_1", "clean_0", "clean_1"))


def _private_tokens(text: str) -> list[str]:
    if not isinstance(text, str) or len(text) > 16384:
        raise ValueError("private reference/transcript exceeds its scoring cap")
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return re.findall(r"[^\W_]+(?:['’][^\W_]+)*", normalized, flags=re.UNICODE)


def _private_chars(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return [char for char in normalized if char.isalnum()]


def _levenshtein(left, right) -> int:
    if len(left) > len(right):
        left, right = right, left
    previous = list(range(len(left) + 1))
    for row_index, right_item in enumerate(right, 1):
        current = [row_index]
        for column_index, left_item in enumerate(left, 1):
            current.append(min(
                current[-1] + 1,
                previous[column_index] + 1,
                previous[column_index - 1] + (left_item != right_item),
            ))
        previous = current
    return previous[-1]


def _reference_metrics(reference: str, hypothesis: str) -> dict:
    ref_words = _private_tokens(reference)
    hyp_words = _private_tokens(hypothesis)
    ref_chars = _private_chars(reference)
    hyp_chars = _private_chars(hypothesis)
    if not ref_words or not ref_chars:
        raise ValueError("private Certas reference has no normalized tokens")
    word_errors = _levenshtein(ref_words, hyp_words)
    char_errors = _levenshtein(ref_chars, hyp_chars)
    ref_counts = __import__("collections").Counter(ref_words)
    hyp_counts = __import__("collections").Counter(hyp_words)
    return {
        "reference_words": len(ref_words),
        "hypothesis_words": len(hyp_words),
        "word_errors": word_errors,
        "wer": round(word_errors / len(ref_words), 6),
        "reference_chars": len(ref_chars),
        "hypothesis_chars": len(hyp_chars),
        "char_errors": char_errors,
        "cer": round(char_errors / len(ref_chars), 6),
        "matched_reference_tokens": sum((ref_counts & hyp_counts).values()),
    }


def _aggregate_reference_metrics(rows: list[dict]) -> dict:
    words = sum(row["reference_words"] for row in rows)
    chars = sum(row["reference_chars"] for row in rows)
    word_errors = sum(row["word_errors"] for row in rows)
    char_errors = sum(row["char_errors"] for row in rows)
    return {
        "reference_words": words,
        "word_errors": word_errors,
        "wer": round(word_errors / words, 6) if words else None,
        "reference_chars": chars,
        "char_errors": char_errors,
        "cer": round(char_errors / chars, 6) if chars else None,
        "matched_reference_tokens": sum(row["matched_reference_tokens"] for row in rows),
    }


def _require_stem_permutations(permutations: list[tuple[int, int]]) -> None:
    expected = list(itertools.permutations((0, 1)))
    if (len(permutations) != 2
            or {tuple(row) for row in permutations} != set(expected)):
        raise ValueError("Certas reference scoring requires both exact stem permutations")


def _contains_private_text(value, private_texts: set[str], field_name: str = "") -> bool:
    """Detect transcript payloads while allowing only explicit schema labels."""
    sensitive_keys = {"text", "transcript", "transcription", "hypothesis",
                      "hypotheses", "reference_text"}
    fixed_labels = {
        "stream": {"mix", "stem_0", "stem_1", "clean_0", "clean_1"},
        "reference_basis": {"ordered_concat_proxy_no_word_timing"},
        "basis": {"reference_token_inventory_delta_vs_mix_including_false_insertions"},
        "metric_normalization": {
            "NFKC casefold; Unicode alphanumeric words; CER excludes spaces and punctuation",
        },
    }
    if isinstance(value, dict):
        for key, item in value.items():
            key_name = str(key).casefold()
            if key_name in sensitive_keys:
                return True
            if (isinstance(item, str) and item in fixed_labels.get(key_name, set())):
                continue
            if _contains_private_text(item, private_texts, key_name):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(_contains_private_text(item, private_texts, field_name) for item in value)
    if isinstance(value, str):
        return (value in private_texts
                or any(len(text) >= 12 and text in value for text in private_texts))
    return False


def evaluate_certas_private(texts: dict, reference_rows: list[dict],
                             prepared_key: str, reference_manifest_sha256: str) -> dict:
    """Compare private texts to pinned refs and return aggregate metrics/hashes only."""
    expected = {"mix", "stem_0", "stem_1", "clean_0", "clean_1"}
    if (not isinstance(texts, dict) or set(texts) != expected
            or not isinstance(reference_rows, list) or len(reference_rows) != 2
            or not re.fullmatch(r"[0-9a-f]{64}", str(prepared_key))
            or not re.fullmatch(r"[0-9a-f]{64}", str(reference_manifest_sha256))):
        raise ValueError("Certas scoring requires exactly two anonymous stems and two references")
    if (any(not isinstance(texts.get(name), str) for name in expected)
            or any(len(texts[name]) > 16384 for name in expected)
            or any(not isinstance(row, dict) for row in reference_rows)):
        raise ValueError("Certas private scoring inputs have an invalid shape")
    references = [row.get("reference_text") for row in reference_rows]
    reference_hashes = [row.get("reference_sha256") for row in reference_rows]
    if any(not isinstance(ref, str) or not ref.strip() for ref in references):
        raise ValueError("private Certas references are incomplete")
    if (any(not re.fullmatch(r"[0-9a-f]{64}", str(digest)) for digest in reference_hashes)
            or any(hashlib.sha256(ref.encode("utf-8")).hexdigest() != digest
                   for ref, digest in zip(references, reference_hashes))):
        raise ValueError("private Certas reference identity is invalid")

    clean_rows = []
    for index in range(2):
        metrics = _reference_metrics(references[index], texts["clean_%d" % index])
        clean_rows.append({"stream": "clean_%d" % index,
                           "reference_sha256": reference_hashes[index],
                           "transcript_sha256": hashlib.sha256(
                               texts["clean_%d" % index].encode("utf-8")).hexdigest(),
                           **metrics})

    # The overlapping mixture has no word timestamps in this small reference
    # slice. Its ordered concatenation score is explicitly a proxy, not human
    # word-level ground truth for simultaneous speech.
    joined_reference = " ".join(references)
    mix_metrics = _reference_metrics(joined_reference, texts["mix"])
    mix_row = {
        "stream": "mix",
        "reference_basis": "ordered_concat_proxy_no_word_timing",
        "reference_sha256": reference_manifest_sha256,
        "transcript_sha256": hashlib.sha256(texts["mix"].encode("utf-8")).hexdigest(),
        **mix_metrics,
    }

    permutation_rows = []
    for assignment in itertools.permutations((0, 1)):
        rows = []
        for stem_index, reference_index in enumerate(assignment):
            stream = "stem_%d" % stem_index
            metrics = _reference_metrics(references[reference_index], texts[stream])
            rows.append({
                "stream": stream,
                "reference_index": reference_index,
                "reference_sha256": reference_hashes[reference_index],
                "transcript_sha256": hashlib.sha256(texts[stream].encode("utf-8")).hexdigest(),
                **metrics,
            })
        aggregate = _aggregate_reference_metrics(rows)
        aggregate.update({"stem_to_reference": list(assignment), "streams": rows})
        permutation_rows.append(aggregate)
    _require_stem_permutations([tuple(row["stem_to_reference"])
                                for row in permutation_rows])
    selected = min(permutation_rows,
                   key=lambda row: (row["word_errors"], row["char_errors"],
                                    tuple(row["stem_to_reference"])))

    # The aggregate token inventory avoids assigning mixture words to one
    # speaker. Counts are a bounded proxy for words recovered/lost vs. the mix.
    from collections import Counter
    reference_inventory = Counter()
    for reference in references:
        reference_inventory.update(_private_tokens(reference))
    mix_inventory = Counter(_private_tokens(texts["mix"]))
    separated_inventory = Counter()
    for stream in ("stem_0", "stem_1"):
        separated_inventory.update(_private_tokens(texts[stream]))
    mix_hits = sum((reference_inventory & mix_inventory).values())
    separated_hits = sum((reference_inventory & separated_inventory).values())
    mix_insertions = sum((mix_inventory - reference_inventory).values())
    separated_insertions = sum((separated_inventory - reference_inventory).values())
    correction_damage = {
        "basis": "reference_token_inventory_delta_vs_mix_including_false_insertions",
        "mix_matched_reference_tokens": mix_hits,
        "separated_matched_reference_tokens": separated_hits,
        "mix_false_insertions": mix_insertions,
        "separated_false_insertions": separated_insertions,
        "correction_count": (max(0, separated_hits - mix_hits)
                             + max(0, mix_insertions - separated_insertions)),
        "damage_count": (max(0, mix_hits - separated_hits)
                         + max(0, separated_insertions - mix_insertions)),
    }
    public = {
        "metric_normalization": "NFKC casefold; Unicode alphanumeric words; CER excludes spaces and punctuation",
        "prepared_key": prepared_key,
        "reference_manifest_sha256": reference_manifest_sha256,
        "reference_rows": 2,
        "clean_baselines": clean_rows,
        "mix": mix_row,
        "stem_permutations": permutation_rows,
        "selected_stem_permutation": selected["stem_to_reference"],
        "selected_stem_scores": {key: value for key, value in selected.items()
                                  if key != "streams"},
        "correction_damage": correction_damage,
    }
    private_values = {value for value in [*references, *texts.values()] if value}
    if _contains_private_text(public, private_values):
        raise RuntimeError("Certas aggregate scoring privacy guard failed")
    return public


def _load_certas_reference_bundle(wav_path: str) -> dict:
    """Load the helper by path without exposing its private references."""
    import importlib.util
    helper_path = os.path.join(HERE, "prepare-certas-overlap.py")
    spec = importlib.util.spec_from_file_location("_certas_overlap_private", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Certas overlap helper is unavailable")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    bundle = helper.load_reference_bundle(Path(wav_path).parent)
    if Path(wav_path).resolve() != Path(bundle["mix_wav"]).resolve():
        raise ValueError("--score-certas requires the pinned prepared mix.wav")
    return bundle


def score_selftest() -> int:
    """Synthetic, model-free controls for reference fusion and privacy gates."""
    secret_a = "mix"
    secret_b = "beta private reference"
    texts = {
        "clean_0": secret_a, "clean_1": secret_b,
        "mix": "beta syntheticinsertedtoken",
        "stem_0": "beta", "stem_1": "mix",
    }
    refs = [
        {"reference_text": secret_a, "reference_sha256": hashlib.sha256(secret_a.encode()).hexdigest()},
        {"reference_text": secret_b, "reference_sha256": hashlib.sha256(secret_b.encode()).hexdigest()},
    ]
    key = "a" * 64
    manifest = "b" * 64
    result = evaluate_certas_private(texts, refs, key, manifest)
    private_values = {value for value in [*texts.values(), secret_a, secret_b] if value}
    score_envelope = {
        "score": {name: _public_score(texts[name], 0.56, 1, name)
                  for name in ("mix", "stem_0", "stem_1")},
        "reference_score": result,
    }
    ok = (len(result["stem_permutations"]) == 2
          and result["selected_stem_permutation"] == [1, 0]
          and result["correction_damage"]["correction_count"] == 2
          and result["correction_damage"]["damage_count"] == 0
          and all("wer" in row and "cer" in row for row in result["stem_permutations"])
          and "beta private reference" not in json.dumps(score_envelope)
          and not _contains_private_text(score_envelope, private_values))
    leaked_envelope = {"score": {name: dict(row) for name, row
                                  in score_envelope["score"].items()},
                       "reference_score": result}
    leaked_envelope["score"]["mix"]["transcript"] = texts["clean_0"]
    ok = ok and _contains_private_text(leaked_envelope, private_values)
    normal_value_leak = {"score": {"stem_0": {"diagnostic": "mix"}}}
    ok = ok and _contains_private_text(normal_value_leak, private_values)
    for bad_texts in (
        {**texts, "stem_2": "extra"},
        {key: value for key, value in texts.items() if key != "stem_1"},
    ):
        try:
            evaluate_certas_private(bad_texts, refs, key, manifest)
            ok = False
        except ValueError:
            pass
    try:
        _require_stem_permutations([(0, 1), (0, 2)])
        ok = False
    except ValueError:
        pass
    wrong_hash_refs = [dict(refs[0]), dict(refs[1])]
    wrong_hash_refs[0]["reference_sha256"] = "c" * 64
    try:
        evaluate_certas_private(texts, wrong_hash_refs, key, manifest)
        ok = False
    except ValueError:
        pass
    print("CERTAS_SCORE_SELFTEST %s controls=8" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def _load_redux_consumer(threads: int):
    worker_dir = os.path.join(REPO, "worker")
    if worker_dir not in sys.path:
        sys.path.insert(0, worker_dir)
    import audio_queue_consumer
    return audio_queue_consumer.Consumer(
        queue_dir=os.path.join(HERE, ".cache", "score-queue"),
        model_dir=ASR_DIR, log=lambda _message: None,
        window_s=3.0, step_s=3.0, threads=threads,
    )


def _release_mossformer2() -> dict:
    """Drop cached separator weights and request allocator release before ASR load."""
    entries = list(_MOSS_CACHE.values())
    if not entries:
        return {"models_cleared": 0, "torch_cuda_allocated_mb_after": None,
                "torch_cuda_reserved_mb_after": None}
    models_cleared = len(entries)
    torch = entries[0][1]
    allocated_before = float(torch.cuda.memory_allocated()) / 1e6
    _MOSS_CACHE.clear()
    del entries
    import gc
    gc.collect()
    torch.cuda.synchronize()
    torch.cuda.empty_cache()
    allocated_after = float(torch.cuda.memory_allocated()) / 1e6
    reserved_after = float(torch.cuda.memory_reserved()) / 1e6
    if allocated_after >= allocated_before:
        raise RuntimeError("--score MossFormer CUDA allocations were not released")
    return {"models_cleared": models_cleared,
            "torch_cuda_allocated_mb_before": round(allocated_before, 1),
            "torch_cuda_allocated_mb_after": round(allocated_after, 1),
            "torch_cuda_reserved_mb_after": round(reserved_after, 1)}


# ---------------------------------------------------------------------------
# the one entry point
# ---------------------------------------------------------------------------

def separate(samples: np.ndarray, engine: str = "mossformer2", threads: int = 2,
             use_cache: bool = True, verbose: bool = True, **params) -> list[np.ndarray]:
    """Separate `samples` (16 kHz mono float32) into 1..2 streams, cached.

    Returns the streams in engine order. Prints `MISS <key>` / `CACHE HIT <key>`
    on the SAME line format the caller can grep, because the cache is only
    trustworthy if the reader can tell which path ran.
    """
    if engine not in ENGINES:
        raise SystemExit("separate: unknown engine %r (have: %s)"
                         % (engine, ", ".join(sorted(ENGINES))))
    fn, n_streams = ENGINES[engine]
    params = dict(params)
    params.pop("verbose", None)
    #: `rev` belongs to the CONTENT KEY only: it marks a change in the code that
    #: alters the bytes written, so stale streams are not served, but it is not an
    #: argument of any engine (passing it as one is a TypeError, found by running).
    key_params = dict(params)
    call_params = {k: v for k, v in params.items()
                   if k not in {"rev", "identity", "hash_mib_s"}}
    key = span_key(engine, key_params, samples)
    if use_cache:
        hit = cache_load(engine, key, n_streams)
        if hit is not None:
            streams, meta = hit
            if verbose:
                print("CACHE HIT %s  (%s, %.2f s of audio, streams=%d, cached at %s)"
                      % (key, engine, len(samples) / float(RATE), len(streams),
                         meta.get("written_at")), file=sys.stderr, flush=True)
                print("COST engine=%s audio_s=%.2f wall_s=0.000 rtf=0.0000 "
                      "rss_mb=%s cached_rtf=%s (CACHE HIT, no compute)"
                      % (engine, len(samples) / float(RATE), _rss_mb(),
                         meta.get("rtf")), file=sys.stderr, flush=True)
            return streams
    if verbose:
        print("MISS %s  (%s, %.2f s of audio)" % (key, engine, len(samples) / float(RATE)),
              file=sys.stderr, flush=True)
    t0 = time.perf_counter()
    device = str(call_params.get("device", "cpu"))
    with PeakRSS(device=device) as meter:
        streams = fn(samples, threads=threads, **call_params)
    wall = time.perf_counter() - t0
    audio_s = len(samples) / float(RATE)
    rss_peak = round(meter.peak, 1) if meter.peak else _rss_mb()
    if verbose:
        print("COST engine=%s audio_s=%.2f wall_s=%.3f rtf=%.4f rss_peak_mb=%s "
              "threads_budget=%d process_threads_peak=%d gpu_allocated_peak_mb=%s "
              "gpu_reserved_peak_mb=%s gpu_nvml_baseline_free_mib=%s "
              "gpu_nvml_min_free_mib=%s gpu_nvml_peak_used_mib=%s "
              "(PROCESS total: torch+ort SUM to it, not each)"
              % (engine, audio_s, wall, wall / max(1e-9, audio_s), rss_peak,
                 PROCESS_BUDGET, meter.thread_peak,
                 None if meter.gpu_allocated_peak_mb is None else round(meter.gpu_allocated_peak_mb, 1),
                 None if meter.gpu_reserved_peak_mb is None else round(meter.gpu_reserved_peak_mb, 1),
                 None if meter.gpu_nvml_baseline_free_mib is None else round(meter.gpu_nvml_baseline_free_mib, 1),
                 None if meter.gpu_nvml_min_free_mib is None else round(meter.gpu_nvml_min_free_mib, 1),
                 None if meter.gpu_nvml_peak_used_mib is None else round(meter.gpu_nvml_peak_used_mib, 1)),
              file=sys.stderr, flush=True)
    if meter.thread_peak > 32:
        raise SystemExit("separate: process OS-thread ceiling exceeded: %d > 32" % meter.thread_peak)
    if rss_peak is not None and rss_peak > 3072:
        raise SystemExit("separate: RSS ceiling exceeded: %.1f MiB > 3072 MiB" % rss_peak)
    if meter.gpu_reserved_peak_mb is not None:
        if meter.gpu_nvml_min_free_mib is None or meter.gpu_nvml_baseline_free_mib is None:
            raise SystemExit("separate: NVML did not produce a measurable VRAM window")
        growth = meter.gpu_nvml_baseline_free_mib - meter.gpu_nvml_min_free_mib
        if growth > 8192:
            raise SystemExit("separate: GPU free-memory drop ceiling exceeded: %.1f MiB > 8192 MiB" % growth)
        if meter.gpu_nvml_min_free_mib < 4096:
            raise SystemExit("separate: GPU free-memory floor breached: %.1f MiB < 4096 MiB"
                             % meter.gpu_nvml_min_free_mib)
    output_bytes = sum(int(np.asarray(s).size) * 2 for s in streams)
    if output_bytes > 1024 * 1024:
        raise SystemExit("separate: output byte ceiling exceeded: %d > 1048576" % output_bytes)
    if use_cache:
        rate = params.get("rate", RATE)
        meta = {"engine": engine, "params": key_params, "wall_s": round(wall, 4),
                "audio_s": round(len(samples) / float(RATE), 3),
                "rtf": round(wall / max(1e-9, len(samples) / float(RATE)), 5),
                "written_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "rate": rate,
                "threads": threads, "process_threads_peak": meter.thread_peak,
                "rss_peak_mb": rss_peak,
                "gpu_allocated_peak_mb": meter.gpu_allocated_peak_mb,
                "gpu_reserved_peak_mb": meter.gpu_reserved_peak_mb,
                "gpu_nvml_baseline_free_mib": meter.gpu_nvml_baseline_free_mib,
                "gpu_nvml_min_free_mib": meter.gpu_nvml_min_free_mib,
                "gpu_nvml_peak_used_mib": meter.gpu_nvml_peak_used_mib,
                "output_bytes": output_bytes,
                "identity": params.get("identity")}
        path = cache_store(engine, key, streams, meta)
        if verbose:
            print("STORED %s -> %s" % (key, path), file=sys.stderr, flush=True)
    return streams


def auto_spans(x: np.ndarray, n: int, span_s: float, hop_s: float = 10.0) -> list[int]:
    """Pick N energy-dense spans, no model. Deterministic, so a rerun is the same KV.

    Energy is the cheapest honest selector: a span of silence separates into two
    streams of silence and would score a perfect "0 words for both voices"
    result that says nothing about the separator.
    """
    w = int(span_s * RATE)
    h = max(1, int(hop_s * RATE))
    scores = []
    for s0 in range(0, max(1, len(x) - w + 1), h):
        seg = x[s0: s0 + w]
        scores.append((float(np.sqrt(np.mean(seg ** 2))), s0))
    scores.sort(reverse=True)
    chosen: list[int] = []
    for _, s0 in scores:
        if all(abs(s0 - c) >= w for c in chosen):
            chosen.append(s0)
        if len(chosen) >= n:
            break
    return sorted(chosen)


def _stream_stats(streams, mix) -> list[dict]:
    stats = []
    for i, s in enumerate(streams):
        rms = float(np.sqrt(np.mean(np.square(s, dtype=np.float64))))
        stats.append({"stream": i, "rms_db": round(20 * np.log10(max(rms, 1e-9)), 2),
                      "peak": round(float(np.max(np.abs(s))), 4),
                      "samples": int(s.size)})
    if len(streams) == 2:
        a, b = streams
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        corr = float(np.dot(a, b) / max(1e-9, na * nb))
        resid = mix - (a + b)
        stats.append({"stream": "pair",
                      "corr": round(corr, 4),
                      "residual_rms_db": round(20 * np.log10(max(1e-9, float(np.sqrt(np.mean(resid ** 2))))), 2),
                      "corr_note": "corr near 1.0 means the two streams are the same audio, "
                                   "i.e. no separation happened"})
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--engine", default="mossformer2", choices=sorted(ENGINES))
    ap.add_argument("--wav", default="", help="16 kHz mono wav (corpus or span)")
    ap.add_argument("--start", type=float, default=0.0, help="span start, seconds")
    ap.add_argument("--span-s", type=float, default=30.0)
    ap.add_argument("--auto-spans", type=int, default=0,
                    help="ignore --start and pick N energy-dense spans")
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"),
                    help="mossformer2 device; auto prefers CUDA when available")
    ap.add_argument("--hash-mib-s", type=float, default=4.0,
                    help="maximum checkpoint hashing rate; 0 disables pacing")
    ap.add_argument("--chunk-s", type=float, default=10.0, help="mossformer2 chunk length")
    ap.add_argument("--scale", default="match", choices=("match", "raw"),
                    help="mossformer2 estimate scale: 'match' normalises each chunk's "
                         "estimate to the mixture RMS (the framework's own behaviour); "
                         "'raw' keeps the +17.3 dB-hot estimate that clips")
    ap.add_argument("--stream", type=int, default=-1,
                    help="print only this stream's cached path")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--score", action="store_true",
                    help="score mix and up to two anonymous stems through the production "
                         "audio_queue_consumer / CUDA-only Redux backend; store only hashes/metrics")
    ap.add_argument("--score-certas", action="store_true",
                    help="privately score the pinned two-source Certas controls and both stem mappings; "
                         "requires --score and its content-addressed prepared mix.wav")
    ap.add_argument("--score-selftest", action="store_true",
                    help="run model-free synthetic controls for Certas reference metrics/privacy")
    ap.add_argument("--asr-threads", type=int, default=0,
                    help="Redux ORT threads; 0 = remaining --threads process budget")
    ap.add_argument("--cost-log", default="",
                    help="append each row (cost, stats, score) as one JSON line to this file; "
                         "needed because `cage.py` discards a child's stdout, so a caged run's "
                         "own numbers only survive in a file")
    ap.add_argument("--list-cache", action="store_true")
    ap.add_argument("--clear-cache", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if args.score_selftest:
        if PROCESS_BUDGET != 1:
            ap.error("--score-selftest requires --threads 1")
        return score_selftest()

    if args.list_cache:
        rows = []
        for root, _dirs, files in os.walk(CACHE_ROOT):
            if "meta.json" in files:
                try:
                    with open(os.path.join(root, "meta.json"), "r", encoding="utf-8") as fh:
                        meta = json.load(fh)
                except (OSError, ValueError):
                    continue
                rows.append({"key": meta.get("key"), "engine": meta.get("engine"),
                             "audio_s": meta.get("audio_s"), "rtf": meta.get("rtf"),
                             "dir": root})
        print(json.dumps(rows, indent=2))
        return 0
    if args.clear_cache:
        import shutil
        shutil.rmtree(CACHE_ROOT, ignore_errors=True)
        print("separate: cache cleared (%s)" % CACHE_ROOT)
        return 0

    if not args.wav:
        ap.error("--wav is required (or --list-cache/--clear-cache)")
    if args.score and args.stream >= 0:
        ap.error("--score needs mix plus stems; --stream cannot be combined with --score")
    if args.score_certas and not args.score:
        ap.error("--score-certas requires --score")
    if args.score_certas and (args.auto_spans or args.start != 0):
        ap.error("--score-certas is one prepared overlap span at start 0; auto/multi-span is refused")
    if not os.path.isfile(args.wav):
        ap.error("audio file is missing: %s" % args.wav)
    try:
        x, score_preflight, certas_bundle = read_audio_after_score_preflight(
            args, _score_gpu_preflight, read_wav)
    except (OSError, ValueError, RuntimeError) as exc:
        ap.error(str(exc))
    if args.auto_spans:
        picks = auto_spans(x, args.auto_spans, args.span_s)
    else:
        picks = [int(args.start * RATE)]
    if args.stream >= 0:
        picks = picks[:1]

    results = []
    score_sources = []
    score_separator_threads = max(1, PROCESS_BUDGET // 2)
    score_asr_threads = (int(args.asr_threads) if args.asr_threads > 0 else
                         max(1, PROCESS_BUDGET - score_separator_threads))
    if args.score and score_separator_threads + score_asr_threads > PROCESS_BUDGET:
        ap.error("--asr-threads plus separator threads exceed the --threads process budget")
    score_device = "cuda" if args.score else None
    score_identity = (mossformer_identity("cuda", args.hash_mib_s)
                      if args.score else None)
    for s0 in picks:
        seg = x[s0: s0 + int(args.span_s * RATE)]
        if seg.size == 0:
            print("separate: span at %.1f s is past the end of %s -- nothing to do"
                  % (s0 / float(RATE), args.wav), file=sys.stderr)
            continue
        #: `rev` bumps whenever the SEPARATION CODE changes the bytes it writes
        #: without changing the parameters -- the content key must not serve a
        #: stream produced by an older pipeline (rev 2: peak guard + thread budget).
        params = ({"chunk_s": args.chunk_s, "scale": args.scale, "rev": 3}
                  if args.engine == "mossformer2" else {})
        if args.engine == "mossformer2":
            if args.score:
                device = score_device
            else:
                device, _device_details = resolve_moss_device(args.device)
            params["device"] = device
            params["identity"] = (score_identity if args.score else
                                  mossformer_identity(device, args.hash_mib_s))
        separator_threads = score_separator_threads if args.score else args.threads
        streams = separate(seg, engine=args.engine, threads=separator_threads,
                           use_cache=not args.no_cache, **params)
        key = span_key(args.engine, params, seg)
        row = {"engine": args.engine, "wav": os.path.abspath(args.wav),
               "start_s": round(s0 / float(RATE), 2),
               "audio_s": round(seg.size / float(RATE), 2),
               "key": key,
               "cache_dir": cache_dir(args.engine, key),
               "streams": [os.path.join(cache_dir(args.engine, key), "s%02d.wav" % i)
                           for i in range(len(streams))],
               "stats": _stream_stats(streams, seg)}
        meta_path = os.path.join(cache_dir(args.engine, key), "meta.json")
        if os.path.isfile(meta_path):
            with open(meta_path, "r", encoding="utf-8") as fh:
                m = json.load(fh)
            row["wall_s"] = m.get("wall_s")
            row["rtf"] = m.get("rtf")
            row["rss_peak_mb"] = m.get("rss_peak_mb")
        results.append(row)
        if args.score:
            score_sources.append((row, s0))
        elif args.cost_log:
            with open(args.cost_log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        del streams, seg

    if args.score and results:
        consumer, asr_engine, score_policy = create_score_backend(
            lambda: _load_redux_consumer(score_asr_threads), _release_mossformer2)
        del consumer
        for row, s0 in score_sources:
            cached = cache_load(args.engine, row["key"], len(row["streams"]))
            if cached is None:
                raise RuntimeError("--score separated stream cache disappeared before ASR pass")
            stems, _meta = cached
            if len(stems) > 2:
                raise RuntimeError("--score separator returned more than two anonymous stems")
            seg = x[s0: s0 + int(args.span_s * RATE)]
            t0 = time.perf_counter()
            named_audio = [("mix", seg)] + [
                ("stem_%d" % i, stem) for i, stem in enumerate(stems)
            ]
            if certas_bundle is not None:
                row["score"], private_texts = score_inputs(
                    asr_engine, named_audio, retain_private_text=True)
                for index, record in enumerate(certas_bundle["records"]):
                    clean_audio = read_wav(str(record["clean_wav"]))
                    clean_text, _clean_s, _clean_segments = _transcribe_private(
                        asr_engine, clean_audio)
                    private_texts["clean_%d" % index] = clean_text
                    del clean_audio, clean_text
                row["reference_score"] = evaluate_certas_private(
                    private_texts, certas_bundle["records"],
                    certas_bundle["meta"]["key"],
                    certas_bundle["meta"]["source_manifest_sha256"])
                del private_texts
            else:
                row["score"] = score_inputs(asr_engine, named_audio)
            row["score_wall_s"] = round(time.perf_counter() - t0, 3)
            row["score_rss_mb"] = _rss_mb()
            row["asr_policy"] = score_policy["asr"]
            row["separator_release"] = score_policy["separator_release"]
            row["score_preflight"] = score_preflight
            if args.cost_log:
                with open(args.cost_log, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            del named_audio, stems, seg
        if certas_bundle is not None:
            del certas_bundle

    if args.stream >= 0:
        if not results:
            return 2
        print(results[0]["streams"][args.stream])
        return 0
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print("%-11s %6.1fs +%-5.1fs key=%s  cost: wall=%ss rtf=%s rss_peak_mb=%s"
                  % (r["engine"], r["start_s"], r["audio_s"], r["key"][:16],
                     r.get("wall_s"), r.get("rtf"), r.get("rss_peak_mb")))
            for s in r["stats"]:
                if s["stream"] == "pair":
                    print("            corr %.3f  residual %+.1f dB" % (s["corr"], s["residual_rms_db"]))
                else:
                    print("            s%d  rms %+6.1f dB  peak %.3f" % (s["stream"], s["rms_db"], s["peak"]))
            if "score" in r:
                print("            SCORE (production Redux %s, score wall %.1fs)"
                      % (os.path.basename(ASR_DIR), r["score_wall_s"]))
                print("            %-7s %6s %7s %7s %s"
                      % ("stream", "words", "wps", "segments", "text-sha256"))
                for name in sorted(r["score"], key=lambda k: (k != "mix", k)):
                    sc = r["score"][name]
                    print("            %-7s %6d %7.2f %7d %s"
                          % (name, sc["words"], sc["wps"], sc["segments"],
                             sc["text_sha256"][:16]))
            if "reference_score" in r:
                ref_score = r["reference_score"]
                changes = ref_score["correction_damage"]
                for clean in ref_score["clean_baselines"]:
                    print("            CERTAS %-7s WER %.4f CER %.4f"
                          % (clean["stream"], clean["wer"], clean["cer"]))
                mix_score = ref_score["mix"]
                print("            CERTAS mix-proxy WER %.4f CER %.4f basis=%s"
                      % (mix_score["wer"], mix_score["cer"],
                         mix_score["reference_basis"]))
                for permutation in ref_score["stem_permutations"]:
                    print("            CERTAS stems %d->ref%d,%d->ref%d WER %.4f CER %.4f"
                          % (0, permutation["stem_to_reference"][0],
                             1, permutation["stem_to_reference"][1],
                             permutation["wer"], permutation["cer"]))
                print("            token inventory vs mix: corrected=%d damaged=%d; refs/transcripts private"
                      % (changes["correction_count"], changes["damage_count"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
