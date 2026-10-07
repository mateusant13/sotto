"""Measured constants for the Sotto ASR engine -- spec `specs/02-asr.md`.

EVERY constant in this file is MEASURED on this box and carries its provenance in the
adjacent comment, as `path:line`:

  docs/research/NN-*.md:line   a research doc, line number
  _main/<probe>.py:line        the probe source line that produced the number
  AGENTS.md:line               the repo's own record

A constant without provenance does not belong here. The few constants that a measurement
BOUNDS rather than fixes are marked ``CHOICE`` and name the band that bounds them.

The package `asr` deliberately imports nothing heavy at module import time: the thread
environment (OMP/OPENBLAS/MKL/NUMEXPR) must be pinned BEFORE numpy and onnxruntime load
their thread pools, so `asr.engine.pin_thread_env()` is called first by the CLI.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "REPO_ROOT", "MODEL_DIR", "SOTTO_ROOT", "SOTTO_REDUX_LONG", "REGISTERED_REFERENCE_DIR",
    "MODEL_NAME", "MODEL_REVISION", "QUANTIZATION", "PROVIDER", "PROVIDERS",
    "MODEL_FILE_SIZES", "MODEL_FILE_SHA256", "MODEL_TOTAL_BYTES", "MODEL_TOTAL_MB",
    "LICENSE", "SAMPLE_RATE", "VOCAB_SIZE", "BLANK_IDX", "MAX_TOKENS_PER_STEP",
    "SUBSAMPLING", "FEATURES", "NEMO128_LOADED",
    "INTRA_OP_NUM_THREADS", "INTER_OP_NUM_THREADS", "THREAD_ENV_VARS",
    "PROCESS_CPU_PCT_MEASURED",
    "RTFX_STEADY_BY_THREADS", "THREAD_MARGINAL_GAIN", "CPU_PCT_EQUALS_THREADS",
    "RSS_AFTER_LOAD_MB", "RSS_PEAK_WSET_MB", "LOAD_S_AT_4_THREADS", "ORT_DEFAULT",
    "FRAME_MS", "SILENCE_FLOOR_PERCENTILE", "SILENCE_THRESHOLD_MULT", "SILENCE_ABS_FLOOR",
    "MIN_SILENCE_S", "MIN_SEGMENT_S", "MAX_SEGMENT_S", "PAD_S",
    "DEFAULT_SEGMENT_MODE", "CONTROL_SEGMENT_MODE", "MODE_SILENCE", "MODE_FIXED",
    "FIXED_GRID_S", "FIXED_GRID_RATIO",
    "RSS_PEAK_GB_BY_SEGMENT_S", "TERNARY_PEAK_MB", "TERNARY_RTFX",
    "BLOCK_MS", "LEVEL_HZ", "RELEASE_TAU_S", "LEVEL_HISTORY", "LEVEL_EVENT_TYPE",
    "LEVEL_KEYS", "LEVEL_MAX_EVENT_BYTES", "PUBLISHED_STATS_INTERVAL_S",
    "RSS_POLL_INTERVAL_S", "ENCODER_SHARE_MIN", "ENCODE_S_RANGE", "DECODE_S_RANGE",
    "PREPROCESS_S_RANGE", "PARITY_EN", "PARITY_PT", "PARITY_LONG_SEGMENTS",
    "REFERENCE_SILENCE_CHARS", "REFERENCE_SILENCE_SHA256",
    "PROVENANCE",
]

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------

# The repo root is derived from this file (src/asr/constants.py -> repo), NOT hard-coded:
# AGENTS.md:8-9 says the folder H:\aireplay will be renamed when the tree is quiet, and a
# hard-coded root would break silently on that day.
REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = REPO_ROOT / "models" / "parakeet-tdt-0.6b-v3-onnx"  # AGENTS.md:162
REGISTERED_REFERENCE_DIR = REPO_ROOT / "_main" / "runs" / "threads11"

# READ-ONLY reference material from the sibling project (H:\sotto stays live, AGENTS.md:350-352).
# Only the parity oracle touches these, and only to read.
SOTTO_ROOT = Path(r"H:\sotto")
SOTTO_REDUX_LONG = SOTTO_ROOT / "_main" / "_redux-long"

# --------------------------------------------------------------------------------------
# The artefact -- spec 02 section 1
# --------------------------------------------------------------------------------------

MODEL_NAME = "nemo-parakeet-tdt-0.6b-v3"  # docs/research/05-onnx-asr.md:36
MODEL_REVISION = "8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce"  # 05-onnx-asr.md:21
QUANTIZATION = "int8"  # 05-onnx-asr.md:37-38 (a GLOB: encoder-model?int8.onnx)
PROVIDER = "CPUExecutionProvider"  # 05-onnx-asr.md:37-39
PROVIDERS = (PROVIDER,)  # AGENTS.md:230-234 -- CUDAExecutionProvider does not load here
LICENSE = "cc-by-4.0"  # docs/research/04-asr.md:23 + the HF API `tags`

MODEL_FILE_SIZES = {  # 05-onnx-asr.md:22-25
    "encoder-model.int8.onnx": 652_183_999,
    "decoder_joint-model.int8.onnx": 18_202_004,
    "nemo128.onnx": 139_764,
    "vocab.txt": 93_939,
    "config.json": 97,
}
MODEL_FILE_SHA256 = {  # 05-onnx-asr.md:22-24, re-verified against the HF API 5/5
    "encoder-model.int8.onnx": "6139d2fa7e1b086097b277c7149725edbab89cc7c7ae64b23c741be4055aff09",
    "decoder_joint-model.int8.onnx": "eea7483ee3d1a30375daedc8ed83e3960c91b098812127a0d99d1c8977667a70",
    "nemo128.onnx": "a9fde1486ebfcc08f328d75ad4610c67835fea58c73ba57e3209a6f6cf019e9f",
}
MODEL_TOTAL_BYTES = 670_619_803  # the SUM of the five registered sizes above.
# DISCREPANCY, recorded rather than copied: docs/research/05-onnx-asr.md:25 prints
# "670 589 803 B" -- a 30 000-byte arithmetic slip (619 -> 589). Both figures round to
# 670.6 MB, which is the number AGENTS.md:162 and the HF tree agree on. The sum of the
# five files on disk is the number used here, and it is the one the selftest checks.
MODEL_TOTAL_MB = 670.6

SAMPLE_RATE = 16_000  # 05-onnx-asr.md:41 + probe-onnx-asr-split.py:30
VOCAB_SIZE = 8193  # 05-onnx-asr.md:41 (MEASURED off the loaded object)
BLANK_IDX = 8192  # 05-onnx-asr.md:41
MAX_TOKENS_PER_STEP = 10  # 05-onnx-asr.md:41
SUBSAMPLING = 8  # 05-onnx-asr.md:41
FEATURES = 128  # 05-onnx-asr.md:41
# The preprocessor is NemoPreprocessorNumpy: mel runs in NumPy, so nemo128.onnx is verified
# but NOT loaded. Never design around it being in the graph. 05-onnx-asr.md:41-43
NEMO128_LOADED = False

# --------------------------------------------------------------------------------------
# Threads -- spec 02 section 2.  THE KNEE IS 4; ORT's default is FORBIDDEN.
# --------------------------------------------------------------------------------------

INTRA_OP_NUM_THREADS = 4  # 11-onnx-threads.md:53 (the measured knee)
INTER_OP_NUM_THREADS = 1  # 11-onnx-threads.md:53
# 11-onnx-threads.md:15-16 -- the lane set all four at process launch; the runner sets them
# before numpy/onnxruntime import so the energy splitter cannot out-thread the budget.
THREAD_ENV_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")

# Steady-state RTFx, mean of two passes (the second reversed), same <=120 s slice.
# 11-onnx-threads.md:22-25
RTFX_STEADY_BY_THREADS = {
    1: {"fixed": 2.82, "silence": 3.28},
    2: {"fixed": 4.93, "silence": 5.62},
    4: {"fixed": 7.29, "silence": 8.74},
    6: {"fixed": 7.34, "silence": 7.23},
}
# 11-onnx-threads.md:29 -- 1->2 1.75x, 2->4 1.48-1.55x, 4->6 1.01x (fixed) / 0.83x (silence)
THREAD_MARGINAL_GAIN = {"1->2": (1.75, 1.72), "2->4": (1.48, 1.55), "4->6": (1.01, 0.83)}
# 11-onnx-threads.md:27 -- lane 11's instruments measured CPU% EXACTLY N: the pin is verifiable.
# MEASURED AGAIN on the PRODUCT's own engine 2026-10-08 (_main/asr02-threadprobe.py, same 10 s
# chunk x3, in-process 250 ms poll, inference phase only): intra=1 -> 99.9% median (exactly one
# core), intra=4 -> 507.1% median / 781.2% max. So the pin bounds ORT's POOL, not the process:
# the mel preprocessor and the pool's own behaviour add cores. The AI Scheduler must budget
# ~5-8 cores for the ASR process, not 4 (law 8). The CONFIGURATION is still the contract.
CPU_PCT_EQUALS_THREADS = True  # at 1 thread, exactly; at 4 threads the PROCESS reads ~507%
PROCESS_CPU_PCT_MEASURED = {1: {"median": 99.9, "max": 106.2}, 4: {"median": 507.1, "max": 781.2}}

RSS_AFTER_LOAD_MB = (734.9, 741.6)  # 11-onnx-threads.md:30-31 (16 arms, 6.7 MB spread)
RSS_PEAK_WSET_MB = {"fixed": (879.6, 886.9), "silence": (920.2, 929.7)}  # 11-onnx-threads.md:31-33
LOAD_S_AT_4_THREADS = (1.96, 4.13)  # 11-onnx-threads.md:24
# ORT's default (intra_op=0) burns 690% of a core-set to deliver 3.11x -- one core's throughput
# for 6.9 cores; 2 threads beat it by 1.95x. It is forbidden in the product. 05-onnx-asr.md:86-90
ORT_DEFAULT = {"rtfx": 3.11, "cpu_pct": 690.0, "forbidden": True}

# --------------------------------------------------------------------------------------
# Silence segmentation -- spec 02 section 3.  Ported verbatim from the measured splitter.
# --------------------------------------------------------------------------------------

FRAME_MS = 20  # _main/probe-onnx-asr-split.py:46 (RMS frame)
SILENCE_FLOOR_PERCENTILE = 10  # probe-onnx-asr-split.py:50 (the noise floor)
SILENCE_THRESHOLD_MULT = 4.0  # probe-onnx-asr-split.py:51
SILENCE_ABS_FLOOR = 0.005  # probe-onnx-asr-split.py:51
MIN_SILENCE_S = 0.30  # probe-onnx-asr-split.py:45 (shorter runs are not cuts)
MIN_SEGMENT_S = 0.6  # probe-onnx-asr-split.py:45 (shorter segments are dropped)
MAX_SEGMENT_S = 15.0  # probe-onnx-asr-split.py:45; the memory knob -- 05-onnx-asr.md:67
PAD_S = 0.10  # probe-onnx-asr-split.py:77 (why recorded segments overlap)

# THE MODE NAMES ARE LITERALS, and the dispatch compares against THESE, never against
# DEFAULT_SEGMENT_MODE. Learned the hard way: when the oracle's broken copy set the DEFAULT to
# "fixed", a dispatch written as `if mode == DEFAULT_SEGMENT_MODE` still called the SILENCE
# splitter while reporting mode="fixed" -- a control that silently ran the product's own path.
MODE_SILENCE = "silence"  # 05-onnx-asr.md:107-110 -- cut on silence and the text IS Redux
MODE_FIXED = "fixed"  # CONTROL ONLY, never a default: 05-onnx-asr.md:105
DEFAULT_SEGMENT_MODE = MODE_SILENCE
CONTROL_SEGMENT_MODE = MODE_FIXED
FIXED_GRID_S = 10.0  # probe-onnx-asr-split.py:88-95
FIXED_GRID_RATIO = 0.229  # 05-onnx-asr.md:105 -- 648 vs 741 chars, garbage at the seams

# Peak RSS is set by SEGMENT LENGTH, not by time on task. 05-onnx-asr.md:67
RSS_PEAK_GB_BY_SEGMENT_S = {10: 0.88, 30: 1.17, 120: 1.77}
# The ternary Redux runner, the same job, the same 120 s slice: 10-redux-2-threads.md:62-63,71-79
TERNARY_PEAK_MB = (4490.0, 4580.0)
TERNARY_RTFX = (3.48, 4.30)

# --------------------------------------------------------------------------------------
# The 10 Hz level event -- spec 02 section 7
# --------------------------------------------------------------------------------------

BLOCK_MS = 100  # docs/research/12-audio-level-contract.md:20 (the native block rate -> 10 Hz)
LEVEL_HZ = 10  # 12-audio-level-contract.md:20,23
# CHOICE: inside the measured 150-250 ms band, midpoint. 12-audio-level-contract.md:45
RELEASE_TAU_S = 0.200
LEVEL_HISTORY = 128  # 12-audio-level-contract.md:44 (128 @ 10 Hz = 12.8 s of visible wave)
LEVEL_EVENT_TYPE = "level"  # 12-audio-level-contract.md:43 (compact, on stdout)
# Keys are short BECAUSE the channel also carries captions: 12-audio-level-contract.md:43.
#   a = audio seconds at the end of the window, p = window peak (linear 0..1),
#   r = window RMS (linear), e = smoothed envelope the wave draws.
LEVEL_KEYS = ("a", "p", "r", "e")
LEVEL_MAX_EVENT_BYTES = 96  # budget: <= ~1 KB/s at 10 Hz, vs ~6 KB/s for the 600 B stats line
# The defect this contract fixes: today the level is a RUN MAXIMUM published at 0.1 Hz.
# 12-audio-level-contract.md:14,21
PUBLISHED_STATS_INTERVAL_S = 10.0
RSS_POLL_INTERVAL_S = 1.0  # _main/probe-onnx-asr.py:90 (--sample-every default)

# --------------------------------------------------------------------------------------
# Where the cost is -- spec 02 section 5
# --------------------------------------------------------------------------------------

ENCODER_SHARE_MIN = 0.95  # 05-onnx-asr.md:91-93 (10 s chunk, 2 threads, 126 encoder frames)
ENCODE_S_RANGE = (0.63, 1.78)  # 05-onnx-asr.md:92
DECODE_S_RANGE = (0.009, 0.023)  # 05-onnx-asr.md:92
PREPROCESS_S_RANGE = (0.006, 0.011)  # 05-onnx-asr.md:92

# --------------------------------------------------------------------------------------
# Parity -- spec 02 section 6
# --------------------------------------------------------------------------------------

PARITY_EN = {  # 05-onnx-asr.md:101
    "kind": "ternary",
    "wav": SOTTO_REDUX_LONG / "src-en-8s.wav",
    "oracle": SOTTO_ROOT / "_main" / "redux-en.txt",
    "audio_s": 8.5,
    "ratio_min": 1.0,
    "max_char_diff_blocks": 0,
}
PARITY_PT = {  # 05-onnx-asr.md:102 registered ratio 0.993711 with ONE char differing
    # CORRECTED 2026-10-08 (receipt 02): that arm was a ONE-SHOT 15 s pass. With SILENCE
    # SEGMENTATION the same clip matches the ternary oracle EXACTLY -- the hyphen in
    # "segunda-feira" survives -- so the registered difference was a chunking effect, not the
    # model. The lock is tightened to EXACT accordingly.
    "kind": "ternary",
    "wav": SOTTO_REDUX_LONG / "src-pt-15s.wav",
    "oracle": SOTTO_ROOT / "_main" / "redux-ptbr.txt",
    "audio_s": 15.0,
    "ratio_min": 1.0,
    "max_char_diff_blocks": 0,
}
PARITY_LONG = {  # regression lock: the same engine's measured text, 11-onnx-threads.md:45
    "kind": "regression",
    "wav": SOTTO_REDUX_LONG / "plain-3600s.wav",
    "offset_s": 900.0,
    "max_s": 120.0,
    "oracle": REGISTERED_REFERENCE_DIR / "silence-t4-p1.txt",
    "ratio_min": 1.0,
    "max_char_diff_blocks": 0,
}
PARITY_LONG_SEGMENTS = 11  # _main/runs/threads11/silence-t4-p1.json
REFERENCE_SILENCE_CHARS = 814  # 11-onnx-threads.md:45 (byte-identical in all 8 arms)
REFERENCE_SILENCE_SHA256 = "746dfd19eabd1644d37dd5dbc9df4d661926b50c99d8d94520f732404bbd81cf"

# --------------------------------------------------------------------------------------
# Machine-readable provenance for the key constants (the oracle prints these)
# --------------------------------------------------------------------------------------

PROVENANCE = {
    "MODEL_REVISION": "docs/research/05-onnx-asr.md:21",
    "MODEL_TOTAL_BYTES": "docs/research/05-onnx-asr.md:25",
    "INTRA_OP_NUM_THREADS": "docs/research/11-onnx-threads.md:53",
    "INTER_OP_NUM_THREADS": "docs/research/11-onnx-threads.md:53",
    "RTFX_STEADY_BY_THREADS": "docs/research/11-onnx-threads.md:22-25",
    "RSS_AFTER_LOAD_MB": "docs/research/11-onnx-threads.md:30-31",
    "MAX_SEGMENT_S": "_main/probe-onnx-asr-split.py:45",
    "MIN_SILENCE_S": "_main/probe-onnx-asr-split.py:45",
    "PAD_S": "_main/probe-onnx-asr-split.py:77",
    "DEFAULT_SEGMENT_MODE": "docs/research/05-onnx-asr.md:107-110",
    "FIXED_GRID_RATIO": "docs/research/05-onnx-asr.md:105",
    "RSS_PEAK_GB_BY_SEGMENT_S": "docs/research/05-onnx-asr.md:67",
    "BLOCK_MS": "docs/research/12-audio-level-contract.md:20",
    "RELEASE_TAU_S": "docs/research/12-audio-level-contract.md:45 (CHOICE inside 150-250 ms)",
    "ENCODER_SHARE_MIN": "docs/research/05-onnx-asr.md:91-93",
    "ORT_DEFAULT": "docs/research/05-onnx-asr.md:86-90",
}
