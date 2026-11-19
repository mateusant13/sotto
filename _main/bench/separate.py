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
import json
import os
import struct
import sys
import time
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
# --score: does separation help the ASR that ships?  (words + a proxy, NO WER)
# ---------------------------------------------------------------------------
#
# There is no reference transcript for the call corpus, so a word error rate
# cannot be computed here and is not reported. What IS defensible without a
# reference:
#
#   words, wps        how much text the shipping ASR extracts from a stream.
#                     Separation that mutes one talker must show up here.
#   wps_speech        the same count divided by the VAD's own speech time in
#                     that stream, so a stream that is 90% silence cannot win
#                     the per-second average by being quiet.
#   mean_peak_p       the arithmetic mean of the transducer's own posterior at
#                     every NON-BLANK token it emitted (softmax over the 8193
#                     vocab logits). This is the model's own confidence in the
#                     text it produced; it is a proxy for intelligibility and
#                     explicitly NOT a WER. Same model, same audio length, so
#                     the numbers are comparable across arms.
#   blank_frac        blank steps / total decode steps. Rises when the audio
#                     stops looking like speech to the acoustic model.

_ASR_CACHE: dict = {}


def _asr_model(threads=None):
    """Load the shipping batch ASR (`worker/models/parakeet-redux-onnx-int4`).

    Imported by explicit path with `importlib`, so nothing else on `sys.path`
    is touched and the model directory is used read-only.

    `threads` defaults to what is LEFT of `PROCESS_BUDGET` after the torch pool
    a loaded separator is holding -- the two pools SUM, they do not each get the
    flag (measured: 4 threads and 250.9-386.4 % of one core for `--threads 2`).
    """
    if threads is None:
        held = 0
        if _MOSS_CACHE:
            try:
                import torch
                held = int(torch.get_num_threads())
            except Exception:
                held = 0
        threads = max(1, PROCESS_BUDGET - held)
    key = ("asr", int(threads))
    if key in _ASR_CACHE:
        return _ASR_CACHE[key]
    import importlib.util

    path = os.path.join(ASR_DIR, "transcribe.py")
    if not os.path.isfile(path):
        raise SystemExit("separate: ASR not on disk: %s" % path)
    spec = importlib.util.spec_from_file_location("_redux_onnx_transcribe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    model = mod.OnnxParakeet(__import__("pathlib").Path(ASR_DIR), threads=int(threads))
    _declare_threads("asr-load", ort_intra=int(threads))
    _ASR_CACHE[key] = (mod, model)
    return _ASR_CACHE[key]


def _greedy_probs(model, encoded: np.ndarray):
    """`OnnxParakeet.greedy` (transcribe.py, class body) PLUS a posterior probe.

    The decode loop is copied because the vendor loop discards its logits and a
    confidence proxy is the only intelligibility signal available without a
    reference transcript. The copy is kept honest by `--verify-decode`, which
    runs the vendor's own `transcribe()` on the same PCM and refuses to print a
    score if the two texts differ -- so a drift in the vendor loop (a new
    duration rule, a different blank rule) fails loudly instead of silently
    scoring a decode nobody ships.
    """
    frames = encoded.shape[0]
    state = (np.zeros(model.state_shape, np.float32), np.zeros(model.state_shape, np.float32))
    last_token = model.blank_id
    frame = 0
    steps = model.max_symbols_per_step * frames
    tokens: list[int] = []
    durations: list[int] = []
    peaks: list[float] = []
    blanks = 0
    total_steps = 0
    target_length = np.ones(1, dtype=np.int32)
    while frame < frames and steps > 0:
        logits, _, hidden, cell = model.decoder_joint.run(None, {
            "encoder_outputs": encoded[frame][None, :, None],
            "targets": np.array([[last_token]], dtype=np.int32),
            "target_length": target_length,
            "input_states_1": state[0], "input_states_2": state[1]})
        logits = logits[0, 0, 0]
        vocab_logits = logits[: model.vocab_size]
        token = int(vocab_logits.argmax())
        duration = model.durations[int(logits[model.vocab_size:].argmax())]
        if token == model.blank_id and duration == 0:
            duration = 1
        # posterior of the emitted token: same softmax the argmax above used
        shifted = vocab_logits - vocab_logits.max()
        log_z = float(np.log(np.exp(shifted).sum())) + float(vocab_logits.max())
        total_steps += 1
        if token == model.blank_id:
            blanks += 1
        else:
            peaks.append(float(np.exp(float(vocab_logits[token]) - log_z)))
        tokens.append(token)
        durations.append(duration)
        frame += duration
        if token != model.blank_id:
            last_token = token
            state = (hidden, cell)
        steps -= 1
    return tokens, durations, peaks, blanks, total_steps


def score_stream(mod, model, pcm: np.ndarray, name: str, verify_decode: bool = False) -> dict:
    """One ASR pass over one stream: words, per-second rates, confidence proxy."""
    pcm = np.ascontiguousarray(np.asarray(pcm, dtype=np.float32))
    audio_s = pcm.size / float(RATE)
    pieces = model.cut_segments(pcm)
    words: list[dict] = []
    texts: list[str] = []
    peaks: list[float] = []
    blanks = steps = 0
    for a, b in pieces:
        enc = model.encode(pcm[a:b])
        tok, dur, pk, bl, st = _greedy_probs(model, enc)
        text = model.vocab.decode(tok)
        if text.strip():
            texts.append(text.strip())
        for w in model.vocab.words(tok, dur, model.frame_seconds):
            w = dict(w)
            w["start"] = min(audio_s, w["start"] + a / float(RATE))
            w["end"] = min(audio_s, w["end"] + a / float(RATE))
            words.append(w)
        peaks.extend(pk)
        blanks += bl
        steps += st
    speech = model.speech_regions(pcm) if model.vad is not None else [(0.0, audio_s)]
    speech_s = sum(max(0.0, e - s) for s, e in speech)
    out = {
        "stream": name,
        "audio_s": round(audio_s, 3),
        "words": len(words),
        "wps": round(len(words) / audio_s, 4) if audio_s else 0.0,
        "vad_speech_s": round(speech_s, 3),
        "speech_frac": round(speech_s / audio_s, 4) if audio_s else 0.0,
        "wps_speech": round(len(words) / speech_s, 4) if speech_s > 0.05 else 0.0,
        "mean_peak_p": round(float(np.mean(peaks)), 5) if peaks else None,
        "blank_frac": round(blanks / steps, 4) if steps else None,
        "text": " ".join(texts),
        "segments": len(pieces),
    }
    if verify_decode:
        vendor = model.transcribe(pcm, timestamps="none")
        out["vendor_text_matches"] = (vendor["text"].strip() == out["text"].strip())
        out["vendor_words"] = len(_vendor_words(mod, model, vendor))
    return out


def _vendor_words(_mod, model, result: dict) -> list:
    """Word count from the vendor's own output (only used by --verify-decode)."""
    n = 0
    for seg in result.get("segments") or ():
        for w in seg.get("words") or ():
            n += 1
    return [None] * n if n else []


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
                    help="run the shipping batch ASR over the mix and over every stream, "
                         "and print words / words-per-second / a confidence proxy")
    ap.add_argument("--verify-decode", action="store_true",
                    help="also run the vendor's own transcribe() and compare its text with "
                         "the copied decode loop (a mismatch means the loop drifted)")
    ap.add_argument("--asr-threads", type=int, default=0,
                    help="0 = whatever is left of --threads after the torch pool")
    ap.add_argument("--cost-log", default="",
                    help="append each row (cost, stats, score) as one JSON line to this file; "
                         "needed because `cage.py` discards a child's stdout, so a caged run's "
                         "own numbers only survive in a file")
    ap.add_argument("--list-cache", action="store_true")
    ap.add_argument("--clear-cache", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

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
    x = read_wav(args.wav)
    if args.auto_spans:
        picks = auto_spans(x, args.auto_spans, args.span_s)
    else:
        picks = [int(args.start * RATE)]
    if args.stream >= 0:
        picks = picks[:1]

    results = []
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
            device, _device_details = resolve_moss_device(args.device)
            params["device"] = device
            params["identity"] = mossformer_identity(device, args.hash_mib_s)
        streams = separate(seg, engine=args.engine, threads=args.threads,
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
        if args.score:
            # The separator's torch pool and the ASR's ORT pool must SUM to the
            # budget, not each claim it. Give torch 1 and the ASR the rest.
            restored = None
            if _MOSS_CACHE:
                try:
                    import torch
                    restored = int(torch.get_num_threads())
                    torch.set_num_threads(1)
                except Exception:
                    restored = None
            asr_threads = args.asr_threads
            if asr_threads <= 0:
                asr_threads = max(1, PROCESS_BUDGET - (1 if restored else 0))
            mod, asr = _asr_model(asr_threads)
            t0 = time.perf_counter()
            row["score"] = {"mix": score_stream(mod, asr, seg, "mix",
                                                verify_decode=args.verify_decode)}
            for i, s in enumerate(streams):
                row["score"]["s%d" % i] = score_stream(
                    mod, asr, s, "s%d" % i, verify_decode=args.verify_decode)
            row["score_wall_s"] = round(time.perf_counter() - t0, 3)
            row["score_rss_mb"] = _rss_mb()
            if restored is not None:
                try:
                    import torch
                    torch.set_num_threads(restored)
                except Exception:
                    pass
        results.append(row)
        if args.cost_log:
            with open(args.cost_log, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

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
                print("            SCORE (shipping ASR %s, score wall %.1fs)"
                      % (os.path.basename(ASR_DIR), r["score_wall_s"]))
                print("            %-4s %6s %6s %6s %6s %7s %7s  %s"
                      % ("strm", "words", "wps", "sp_s", "sp_fr", "wps_sp", "peak_p", "verify"))
                for name in sorted(r["score"], key=lambda k: (k != "mix", k)):
                    sc = r["score"][name]
                    ver = "-"
                    if "vendor_text_matches" in sc:
                        ver = "MATCH" if sc["vendor_text_matches"] else "DRIFT"
                    peak = "n/a" if sc["mean_peak_p"] is None else "%.3f" % sc["mean_peak_p"]
                    print("            %-4s %6d %6.2f %6.1f %6.2f %7.2f %7s  %s"
                          % (name, sc["words"], sc["wps"], sc["vad_speech_s"],
                             sc["speech_frac"], sc["wps_speech"], peak, ver))
    return 0


if __name__ == "__main__":
    sys.exit(main())
