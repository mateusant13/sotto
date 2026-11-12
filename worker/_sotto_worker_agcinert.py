"""Sotto caption worker: system audio in, streamed captions out.

The Electron shell already exists; this is the thing that feeds it. The contract
is JSON Lines on stdout, one object per line, flushed immediately:

    {"type":"status","state":"model-loaded",...}
    {"type":"caption","text":"...","start":0.56,"end":1.12,"model":"..."}

Pipeline (each stage forced by a measurement, not a preference):

  capture   sounddevice InputStream with a CALLBACK on a loopback input. Blocking
            reads fail on this host with PaErrorCode -9999, which is why the
            callback form is mandatory here. The callback only enqueues; ASR runs
            on a separate thread so a slow chunk never drops audio.
  resample  the device is asked for 16 kHz mono directly (PortAudio/WASAPI does
            the conversion). If the device refuses, we fall back to its native
            rate and resample with numpy. No scipy.
  features  onnxruntime_genai StreamingProcessor -- cache-aware, and the only
            generator-supplied front end for this export. It returns exactly the
            encoder's (1,65,128) input, so no feature maths is reimplemented here.
  decode    encoder / decoder / joint ONNX sessions driven by an RNN-T greedy
            walk over the (time, label) grid.

WHAT WAS ACTUALLY EATING THE WORDS (measured 2026-10-06, this file's own
selftest on worker/assets/sample1.flac, 13.44 s of read speech). The degradation
was NEVER the 4-bit weights. It was the greedy walk, in two separate defects:

  1. the label cursor `k0` counted emitted symbols but was used to slice an
     array that only ever held 1-2 decoder steps, so the walk ran off the end of
     it and each chunk stopped after a couple of symbols;
  2. the decoder's LSTM state was carried ACROSS the chunk boundary on top of
     the encoder cache that already carries the acoustic history, which
     duplicated word tails ("country roadss", "fortnightnight'll").

Before: 37 tokens, "go sl cous ands droom for night' an somece of on moni and
can come ily after" -- 17 words where 39 were spoken, with rc=0 and RTF 0.20,
i.e. a green exit code on word salad. That was measured as "the int4
quantisation" for two days. It is not: running the SAME 4-bit weights through
the corrected walk returns fluent English, and running a NON-quantised INT8
export of the same generation through the OLD walk returns the same word salad.

The corrected walk on the shipped configuration (INT8, CUDA) returns, for the
same file:

    'Going along  slushy Country roads  speaking damp  in dr drafty school  day
     For a fortnight He'll have  an appearance At some Sunday morning and  he
     can come to  immediate'

94 tokens, RTF 0.144, peak RSS 2393.7 MB, against the sherpa-onnx INT8 reference
for the same audio (39 fluent words, peak RSS 792.6 MB, RTF 1.334 on CPU). The
INT4 export is one flag away and is also fluent now (80 tokens, RTF 0.110,
2393.7 -> 2129.1 MB); INT8 recovers more words and is what config.json selects.
Full audit: docs/accuracy-int4-vs-fp16-20261006.md plus
docs/int8-route-20261006.md.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import queue
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# The model loaded when NEITHER `--model` NOR config.json's `model.dir` names one.
# It MUST be the export the shipped config.json points at (…-int8). It used to be
# …-int4 while config.json said …-int8, so deleting `model.dir` silently substituted
# a DIFFERENT (smaller) model even though worker/README.md and AGENTS.md both state
# the shipped choice is int8 — the same "silent substitution" class the device ladder
# removed. Defect and evidence: docs/audit/model-config.md §6.3; fix receipts:
# docs/audit/config-inert-fixed.md.
DEFAULT_MODEL = os.path.join(HERE, "models", "nemotron-3.5-asr-streaming-0.6b-int8")
TARGET_SR = 16000

# ── the universal ladder ──────────────────────────────────────────────────────
# OWNER DIRECTIVE: "esse app nao é so pra uso meu, é pra qualquer usuario. entao
# tem que detectar audio de uma forma universal e robusta".
#
# The list that used to live here named three devices that exist on THIS box and
# on almost no other machine ("CABLE Output (VB-Audio Virtual Cable)",
# "VoiceMeeter Output", "Mapeador de som da Microsoft - Input"). A normal
# Windows PC has no VB-Cable at all, so the shipped product could not capture
# system audio anywhere else. A literal name is not a universal detector; it is
# a description of one person's routing.
#
# Names are also not even self-consistent: MEASURED (H:/sotto/_main/device-names.log)
# MME truncates device names at 31 characters ("CABLE Output (VB-Audio Virtual "),
# so a name-equality test over the MME device list cannot succeed for any name
# longer than that. DirectSound and WASAPI carry the full string.
#
# So the shipped list is now empty ON PURPOSE, and matching is HEURISTIC.
# Rungs, tried in this order (recorded per candidate as `rung` in the tap ledger):
#   a) WASAPI loopback of the DEFAULT RENDER endpoint -- driver-free, works with
#      no virtual cable installed. See worker/wasapi_loopback.py.
#   b) a virtual-cable / stereo-mix INPUT matched by name pattern below, any
#      host API, any language and any suffix.
#   c) an explicit --device / SOTTO_AUDIO_DEVICE override, which ALWAYS WINS.
PREFERRED_DEVICES = ()

# The vocabulary that identifies a "this is the PC's own output, looped back"
# endpoint. Matched case-insensitively as SUBSTRINGS, so the same pattern covers
# "CABLE Output (VB-Audio Virtual Cable)", "Stereo Mix (Realtek Audio)",
# "Mixagem estéreo (Realtek HD Audio Stereo input)", "VoiceMeeter Output
# (VB-Audio VoiceMeeter VAIO)" and "Microphone (NVIDIA Broadcast)"-style names
# are excluded by the microphone filter later, not here.
LOOPBACK_NAME_PATTERNS = (
    "cable",          # VB-Cable / VB-Audio Cable
    "virtual",        # any "Virtual Cable"/"Virtual Audio" driver
    "loopback",       # drivers that name the endpoint what it is
    "voicemeeter",    # VB-Audio VoiceMeeter
    "vb-audio",       # other VB-Audio products
    "stereo mix",     # the Realtek/Windows "what you hear" endpoint (en)
    "mixagem est",    # ...and its pt-BR name, "Mixagem estéreo"
    "what u hear",    # Sound Blaster's name for the same thing
    "wave out",       # legacy "Wave Out Mix"
    "monitor",        # some drivers call the loopback a "Monitor"
    "aquario",        # VB-Audio "Hi-Fi Cable" family aliases
    "vac",            # Virtual Audio Cable
)

# The devices that are NOT endpoints at all. Windows' Sound Mapper (MME) and
# Primary Sound Capture Driver (DirectSound) are PSEUDO-devices: they name "the
# current default capture device", open successfully, deliver a full window of
# blocks, and are DIGITAL SILENCE — MEASURED `peak=9.2e-05`, `nonzero_blocks=0`
# (`worker/runs/census-own-worker.jsonl:10`, device "Mapeador de som da
# Microsoft - Input" [MME]). A loopback tap can NEVER carry the PC's output
# through one, so offering one as "somewhere to go" spends a whole tap window
# and then reports a device outcome the reader mistakes for an ASR failure —
# which is exactly how the `frames=35 blanks=35 blank_frac=1.0` run was
# misdiagnosed as a model fault.
#
# Matched as SUBSTRINGS, case-insensitively, in every language this product has
# been measured on: the pt-BR "Mapeador de som da Microsoft" / "Driver de
# captura de som primário" and the en-US "Sound Mapper" / "Primary Sound
# Capture Driver". This is the SAME class of match the microphone filter below
# already uses; it is not claimed to be language-free, and it is applied only
# to the LAST-RESORT rung, so an unknown spelling costs a rotation rung, never
# the tap: rung (a) WASAPI loopback and rung (b) name heuristics are untouched.
SOUNDMAPPER_PATTERNS = (
    "mapeador de som",             # pt-BR "Mapeador de som da Microsoft"
    "sound mapper",                # en-US "Sound Mapper"
    "soundmapper",
    "driver de captura de som prim",  # pt-BR "Driver de captura de som primário"
    "driver de som prim",          # pt-BR "Driver de som primário"
    "primary sound capture",       # en-US "Primary Sound Capture Driver"
    "primary sound driver",
    "capture driver",              # "...Capture Driver" in any prefix
)


def is_soundmapper_pseudo(name):
    """True for a Sound-Mapper / Primary-Capture-Driver PSEUDO-device.

    Such a name is never a concrete endpoint: it is a redirect to whatever the
    system's default capture device happens to be, and it can never carry the
    PC's own output looped back.
    """
    low = str(name).lower()
    return any(pat in low for pat in SOUNDMAPPER_PATTERNS)


def heuristic_loopback_score(name):
    """How much a device NAME looks like a loopback of the PC's own output.

    Returns (score, matched_pattern). Higher is better. A plain name match is
    a heuristic and is RECORDED as one: the run reports rung "b" and names the
    pattern that matched, so a wrong guess is visible instead of silent.
    """
    low = str(name).lower()
    best = (0, None)
    for pat in LOOPBACK_NAME_PATTERNS:
        if pat in low:
            # A name that says "output" is more likely the carrying side than
            # one that says "input"; both are accepted, the former wins.
            score = 2 if "output" in low else 1
            if score > best[0]:
                best = (score, pat)
    return best


# ── tap rotation bounds ───────────────────────────────────────────────────────
# MEASURED both arms in the same minute: run ALONE, config.json resolved
# "CABLE Output (VB-Audio Virtual Cable)" and read SILENCE (nonzero_blocks=0,
# peak=0.000031, captions=0); the shell-launched arm opened "Mapeador de som da
# Microsoft - Input" and produced 29 captions. Neither name is stable — the
# endpoint that carries audio flips with the owner's routing, and which one is
# alive is a property of THIS RUN, not of a config file written earlier.
#
# So a name is no longer trusted for longer than one bounded window. Six seconds
# is long enough for a speaking source to produce signal far above the floor and
# short enough that three dead candidates cost less than the caption stream being
# silently wrong. 0.002 is ~65x the measured dead-tap peak (0.000031) and ~450x
# below the measured live peak (0.883270): it separates DEAD from RENDERED, and
# that is ALL it can do — see the correction below, which is why the floor is no
# longer an acceptance test on its own.
#
# ── CORRECTION 2026-10-06 (lane SottoDeviceRouting), MEASURED ────────────────
# The brief that named this floor also named an "IDLE FLOOR at peak=0.101929"
# that it said the floor cannot separate from speech. Direct measurement on the
# SAME tap refutes the premise: with NOTHING rendering, the WASAPI loopback of
# the default render endpoint delivers DIGITAL SILENCE — three independent 6 s
# captures, `peak=0.000000, rms=0, zcr=0` (`_main/sdr_idlefloor.out`,
# `_main/sdr_idlefloor2.out`). A nonzero reading appears only WHILE a stream
# renders, and it DRAINS when the stream stops (IDLE-2 after a 24 s wait:
# `peak=0.000000` again). So the `0.101929` of `_main/bfrc_b_live.jsonl` was
# REAL RENDERED AUDIO (ambient with no speech), not an endpoint idle floor.
#
# Consequence for the acceptance test: the floor still tells DEAD from RENDERED
# correctly, but RENDERED is not SPEECH. It therefore no longer SETTLES the
# ladder by itself — a caption does (see the window loop's acceptance test and
# `best_carried`). Keeping the floor at 0.002 is deliberate: a lower floor would
# accept the dead tap, and a higher one would reject quiet speech.
TAP_WINDOW_S = 6.0
TAP_PEAK_FLOOR = 0.002

# A tap that OPENS is not a tap that HEARS. These two numbers are what turn
# "the stream started" into a claim that can be wrong, and they exist because
# the 22 s smoke run of 2026-10-06 opened "CABLE Output", delivered 214 blocks,
# and read peak=0.000122 — digital silence — then exited 0 with verdict
# "model-emitted-nothing". That verdict blames the MODEL for a device that never
# delivered a sample. The device was the fault and the run said otherwise.
#
# TAP_SILENT_BLOCKS is the number of callbacks a candidate must deliver before
# its silence is believed. Below it the honest word is "no-data", not "silent":
# 6 s at block_ms=100 is ~60 blocks, so 20 (2 s) rejects a candidate that died
# on open while accepting every candidate that actually ran and heard nothing.
TAP_MIN_WINDOW_S = 2.0
TAP_SILENT_BLOCKS = 20


# ── thread limiting ───────────────────────────────────────────────────────────
# Measured failure this prevents: on a 20-logical-core host ORT/MKL spawned ~98
# worker threads per process. Two concurrent worker processes (152 s and 703 s of
# CPU, then CPU time completely FLAT while the run never advanced) deadlocked in
# the OpenMP barrier. A worker that must run alongside other lanes cannot leave
# thread count to chance, so it is pinned before numpy/onnxruntime import.
def limit_threads(n: int = 0) -> int:
    import multiprocessing

    if n <= 0:
        n = max(1, min(8, (multiprocessing.cpu_count() or 4) // 2))
    for var in (
        "OMP_NUM_THREADS",
        "MKL_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
        "VECLIB_MAXIMUM_THREADS",
    ):
        os.environ.setdefault(var, str(n))
    return n


# os.add_dll_directory() returns a handle that KEEPS the directory registered.
# Drop it and the registration is undone the moment CPython collects it, which
# made that call a silent no-op: CUDA worked only because the PATH line beside
# it happened to be enough. Holding the handles makes both halves real.
_DLL_DIR_HANDLES = []


# ── CUDA plumbing ─────────────────────────────────────────────────────────────
def _add_cuda_dll_dirs() -> None:
    """Make CUDA/cuDNN importable from the torch + nvidia pip wheels.

    onnxruntime-gpu needs cublas/cudnn on the DLL search path. On this host they
    ship inside site-packages (torch/lib and nvidia/*/lib), NOT on PATH, so a
    plain shell gets a CUDA provider that silently fails to load. Must run
    BEFORE onnxruntime is imported.
    """
    import site

    candidates = []
    try:
        import torch

        candidates.append(os.path.join(os.path.dirname(torch.__file__), "lib"))
    except Exception:
        pass
    bases = []
    try:
        bases.extend(site.getsitepackages())
    except Exception:
        pass
    try:
        import sysconfig

        bases.append(sysconfig.get_paths()["purelib"])
    except Exception:
        pass
    for base in bases:
        nv = os.path.join(base, "nvidia")
        if not os.path.isdir(nv):
            continue
        # Windows and Linux lay these out differently: cu13 wheels use
        # nvidia/cu13/bin/x86_64/, the older ones nvidia/<pkg>/lib/. Scan for
        # directories that actually contain DLLs instead of guessing a name.
        for root, dirs, files in os.walk(nv):
            depth = root[len(nv) :].count(os.sep)
            if depth > 3:
                dirs[:] = []
                continue
            if any(f.lower().endswith((".dll", ".so")) for f in files):
                candidates.append(root)
    for d in candidates:
        if not os.path.isdir(d):
            continue
        try:
            _DLL_DIR_HANDLES.append(os.add_dll_directory(d))
        except (AttributeError, OSError):
            pass
        if d not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def _pmc():
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    psapi = ctypes.WinDLL("psapi")
    k32 = ctypes.WinDLL("kernel32")
    # Without explicit argtypes ctypes marshals the pointer as a 32-bit int and
    # the call fails, which is why this used to report -1.0.
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    handle = k32.GetCurrentProcess()
    ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(c), c.cb)
    return (ok, c)


def peak_rss_mb() -> float:
    """Peak working set of THIS process, read from the OS. Never estimated."""
    ok, c = _pmc()
    return c.PeakWorkingSetSize / (1024.0 * 1024.0) if ok else -1.0


def current_rss_mb() -> float:
    ok, c = _pmc()
    return c.WorkingSetSize / (1024.0 * 1024.0) if ok else -1.0


# ── output ────────────────────────────────────────────────────────────────────
def emit(**payload) -> None:
    """One JSON object, one line, flushed. The whole inter-process contract."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def err(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


# ── model ─────────────────────────────────────────────────────────────────────


def _initial_encoder_caches(np, enc, model_dir):
    """Allocate the encoder's cross-attention caches at the shape IT declares.

    MEASURED failure this replaces: the shapes were written down in `__init__` as
    (1,24,56,1024) / (1,24,1024,8) / (1,), which are the int4 export's
    `left_context=56`. The int8 export of the SAME generation declares
    `left_context=70`, and ORT refused the 56-wide cache before the first chunk:
        INVALID_ARGUMENT : Got invalid dimensions for input: cache_last_channel
        index: 2 Got: 56 Expected: 70
    The cache width is a property of the WEIGHTS, so it is read from the graph
    that will consume it rather than asserted here. Cross-checked against
    `genai_config.json`'s `left_context`, because two files in one directory
    disagreeing about the model is a failure mode that produces a plausible
    transcript instead of an error.
    """
    dtypes = {
        "cache_last_channel": np.float32,
        "cache_last_time": np.float32,
        "cache_last_channel_len": np.int64,
    }
    with open(os.path.join(model_dir, "genai_config.json"), encoding="utf-8") as fh:
        cfg_left_context = json.load(fh)["model"].get("left_context")
    declared = {}
    for i in enc.get_inputs():
        if i.name not in dtypes:
            continue
        shape = []
        for d in i.shape:
            if not isinstance(d, int) or d <= 0:
                raise RuntimeError(
                    f"encoder input {i.name} has non-static dim {d!r}; a cache cannot be "
                    f"invented for it"
                )
            shape.append(d)
        declared[i.name] = tuple(shape)
    missing = sorted(set(dtypes) - set(declared))
    if missing:
        raise RuntimeError(f"encoder declares no {missing}; not a genai streaming encoder")
    cc = declared["cache_last_channel"]
    if cfg_left_context is not None and cc[2] != cfg_left_context:
        raise RuntimeError(
            f"encoder cache_last_channel width {cc[2]} != genai_config left_context "
            f"{cfg_left_context}: the two files disagree about this model"
        )
    return (
        np.zeros(cc, dtypes["cache_last_channel"]),
        np.zeros(declared["cache_last_time"], dtypes["cache_last_time"]),
        np.zeros(
            declared["cache_last_channel_len"], dtypes["cache_last_channel_len"]
        ),
    )


def _lang_prompt():
    """The language-prompt resolver, imported the way `wasapi_loopback` is.

    Kept lazy so this file stays runnable both as a script (sys.path[0] is
    worker/) and as an imported module, exactly like the sibling modules.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import lang_prompt

    return lang_prompt


class StreamAsr:
    """Streaming RNN-T over the encoder/decoder/joint ONNX graphs."""

    def __init__(self, model_dir: str, providers=None, use_vad: bool = False, lang_id=None):
        # `lang_id=None` means the resolver runs its sentinel (host user locale,
        # falling back to the model's auto slot); the shipped CONFIG default is
        # "auto" (autoSlot 101). There is deliberately NO
        # literal `0` default here: 0 is en-US, and a silent en-US prompt in
        # front of Portuguese audio is the deviation this parameter replaced.
        # Whatever arrives is validated against the model's OWN languages.json
        # and REFUSED if undeclared — see worker/lang_prompt.py.
        import numpy as np
        import onnxruntime as ort
        import onnxruntime_genai as og

        self.np = np
        self.ort = ort
        self.model_dir = model_dir
        cfg = json.load(open(os.path.join(model_dir, "genai_config.json"), encoding="utf-8"))["model"]
        self.blank = cfg["blank_id"]
        self.chunk = cfg["chunk_samples"]
        self.hidden = cfg["decoder"]["hidden_size"]
        self.max_sym = cfg.get("max_symbols_per_step", 10)

        # The prompt, resolved against the model's OWN table and validated HERE
        # as well as in main(): a probe or a test that constructs StreamAsr
        # directly must not be able to put an undeclared id in front of the
        # encoder. Raises lang_prompt.LangIdError — never clamps.
        _lp = _lang_prompt()
        self.lang_table = _lp.load_language_table(model_dir)
        self.lang_prompt = _lp.resolve_lang_id(lang_id, model_dir, table=self.lang_table)
        self.lang_id = self.lang_prompt.lang_id
        self.lang_tag = self.lang_prompt.tag

        vocab = open(os.path.join(model_dir, "vocab.txt"), encoding="utf-8").read().split("\n")
        if vocab and vocab[-1] == "":
            vocab.pop()
        self.vocab = vocab

        so = ort.SessionOptions()
        so.log_severity_level = 3
        try:
            so.intra_op_num_threads = int(os.environ.get("OMP_NUM_THREADS", "8"))
            so.inter_op_num_threads = 1
        except Exception:
            pass
        self.enc = ort.InferenceSession(os.path.join(model_dir, "encoder.onnx"), so, providers=providers)
        self.dec = ort.InferenceSession(os.path.join(model_dir, "decoder.onnx"), so, providers=providers)
        self.joint = ort.InferenceSession(os.path.join(model_dir, "joint.onnx"), so, providers=providers)

        self.providers = self.enc.get_providers()

        # genai owns the cache-aware feature front end for this export.
        self._og = og
        self.model = og.Model(model_dir)
        self.sp = self.model.create_streaming_processor()
        self.sp.set_option("use_vad", "1" if use_vad else "0")

        self.cc, self.ct, self.ccl = _initial_encoder_caches(np, self.enc, model_dir)
        self.h = np.zeros((2, 1, self.hidden), np.float32)
        self.c = np.zeros((2, 1, self.hidden), np.float32)
        self.lid = np.array([self.lang_id], np.int64)

        # READ-BACK, not a claim: the encoder graph must itself DECLARE the
        # `lang_id` input this run feeds (genai_config.json lists it, but the
        # loaded graph is what is actually driven). If it does not, the prompt
        # cannot be delivered and the run must not pretend otherwise.
        self.lang_input = next((i.name for i in self.enc.get_inputs() if i.name == "lang_id"), None)
        if self.lang_input is None:
            raise _lp.LangIdError(
                f"encoder in {model_dir} declares no 'lang_id' input "
                f"(inputs: {[i.name for i in self.enc.get_inputs()]}) — the language prompt "
                "cannot be delivered to the model"
            )

        self.labels = []
        self.n_chunks = 0
        self.audio_s = 0.0
        self.wall = 0.0
        self.load_s = 0.0
        # Stage counters for the live path. `frames_walked` / `blank_frames` are
        # the discriminator the live run was missing: a greedy walk that only ever
        # argmaxes to blank means the model saw nothing to say, and `blank_frac`
        # is directly comparable with the measured file-mode 0.7562. Pure digital
        # silence sits at ~1.0; real speech on this model sat at 0.7562.
        self.frames_walked = 0
        self.blank_frames = 0
        self.symbols = 0
        self.empty_chunks = 0
        # Chunks the SHIPPED VAD withheld, as opposed to chunks the model walked
        # and had nothing to say about. VAD-on and "the model saw silence" are
        # not the same event and were indistinguishable before this counter.
        self.vad_gated_chunks = 0
        # Chunks OUR OWN speech/music gate withheld (lane SottoSpeechSeparation):
        # audio that is measurably not speech, removed from what the encoder
        # sees. Set to a SpeechMusicGate by main() when the gate is enabled;
        # None leaves run_chunk byte-identical to its pre-gate behaviour.
        self.gate = None
        self.music_gated_chunks = 0

    @property
    def name(self) -> str:
        return os.path.basename(self.model_dir)

    def detok(self, ids):
        parts = []
        for i in ids:
            t = self.vocab[i]
            if t.startswith("<") and t.endswith(">"):
                continue
            parts.append(t)
        return "".join(parts).replace("\u2581", " ").strip()

    def _decode(self, targets, h, c):
        return self.dec.run(["decoder_output", "h_out", "c_out"], {"targets": targets, "h_in": h, "c_in": c})

    def run_chunk(self, pcm_chunk, speech=None):
        """One 8960-sample (560 ms) chunk of 16 kHz mono float32 -> (text, n_tokens).

        `speech` is the speech/music decision the CALLER already made on the
        PRE-GAIN signal (asr_thread, lane SottoAgcSpeechOrder). When it is not
        None the gate is NOT consulted here again — deciding a second time on the
        post-gain chunk would put the decision AFTER the gain and defeat the
        order. When it is None (the FILE arm, `selftest()`, and any direct
        caller) the gate is consulted here, on `pcm_chunk`, exactly as before.


        THE GREEDY WALK, AND THE BUG THAT WAS IN IT. The previous version kept a
        label cursor `k0` and sliced the decoder output with it:

            dd   = dout.transpose(0,2,1)[:, k0:, :]
            ti  += hit[0];  k0 += hit[1] + 1

        `k0` counts EMITTED SYMBOLS, but it was used to index an array that only
        ever held 1-2 decoder steps, so after two emissions the slice was empty
        and the chunk ended early. It also scanned all remaining frames for any
        non-blank at once, which lets the walk jump forward in time past frames
        whose prediction it never evaluated. MEASURED consequence on sample1.flac
        (13.44 s, both exports): 37 tokens (int4) / 38 tokens (int8) of word
        salad -- "go sl cous ands droom for night' an somece of on moni" -- with
        RTF 0.20 and a green exit code. That output was blamed on the 4-bit
        weights until the SAME weights were run through sherpa-onnx (39 fluent
        words) and then, here, through this corrected walk.

        The canonical RNN-T greedy search needs no label cursor at all. The
        prediction vector is ALWAYS the decoder's output at its LAST position:
        the LSTM emits position i after consuming targets[:i+1], so position
        len-1 is "given everything emitted so far". One (time, label) cell at a
        time: blank advances time, a symbol emits and re-runs the decoder.

        CARRY INVARIANT (the one this file's older revision broke): h/c is the
        entire history, so each decoder call consumes ONLY the symbol just
        emitted. Re-feeding the accumulated list re-processes history the state
        already holds. Measured equal either way on this checkpoint -- variants
        "carry one symbol" and "replay from zero" produced byte-identical
        transcripts -- so the O(1) form is what ships.
        """
        np = self.np
        t_start = time.time()

        # ── the speech/music gate (lane SottoSpeechSeparation) ───────────────
        # A chunk the gate calls non-speech never reaches the encoder: it is
        # ISOLATED out here, exactly like a VAD-gated chunk, and its elapsed
        # time still advances the clock. `music_gated_chunks` is the visible
        # count (surfaced in WORKER_STATS and the status emits). The gate is
        # None unless main() enabled it, so without SOTTO_GATE this function is
        # byte-identical to its pre-gate behaviour.
        #
        # ORDER (lane SottoAgcSpeechOrder): when the caller passes `speech` it
        # has ALREADY run the gate on the PRE-GAIN chunk, so the decision is used
        # as given and the gate is never consulted on the post-gain audio.
        if speech is None:
            speech = True if self.gate is None else self.gate.is_speech(pcm_chunk)
        if not speech:
            self.music_gated_chunks += 1
            self.n_chunks += 1
            self.audio_s += len(pcm_chunk) / TARGET_SR
            self.wall += time.time() - t_start
            return "", 0

        feats = self.sp.process(pcm_chunk)
        # ── the VAD-gated chunk ──────────────────────────────────────────────
        # `use_vad` is not a passive flag in onnxruntime-genai 0.17.1: the
        # StreamingProcessor CONSUMES it, and when the shipped Silero VAD
        # (threshold 0.3 / silence_duration_ms 3360 / prefix_padding_ms 560,
        # genai_config.json) holds a chunk back, `process()` returns None — the
        # model's own README guards exactly this (`if inputs is not None`).
        # MEASURED 2026-10-06, `_main/vad-option-probe.py`: feeding the same
        # digital-silence chunk with use_vad=0 returns a (1,65,128) feature
        # block 12 times out of 12; with use_vad=1 the first two pass and the
        # remaining 10 return None. Unhandled, the next line raises
        #   TypeError: 'NoneType' object is not subscriptable
        # and the whole worker EXITS 1 on the first pause longer than 3.36 s —
        # measured on `_main/vad-gap-sample.flac` (sample1 + 6.0 s of digital
        # silence + sample2): rc=1, 16 of 26 captions, traceback at line 477.
        # A gated chunk is real elapsed audio, so the clock still advances; it
        # simply contributes no features, no frames and no text.
        if feats is None:
            self.vad_gated_chunks += 1
            self.n_chunks += 1
            self.audio_s += len(pcm_chunk) / TARGET_SR
            self.wall += time.time() - t_start
            return "", 0
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
        T = int(np.asarray(enc_len).reshape(-1)[0])

        # The prediction network is RE-PRIMED at every chunk boundary: h/c start
        # at zero and the first decoder call consumes only the blank. MEASURED
        # reason, same file, same weights, CPU, only this line differing:
        #   carry across chunks -> 86 tokens (int4) / 108 (int8), with doubled
        #     word tails ("Goinging along country roadskingss infty schoolros")
        #   re-prime per chunk  -> 81 tokens (int4) /  91 (int8), clean, and the
        #     int8 line matches the sherpa-onnx reference almost word for word.
        # The acoustic history crosses the boundary in the ENCODER cache
        # (cache_last_channel / cache_last_time), which is what carries it; the
        # decoder state carrying it too is what duplicates the words.
        self.h = np.zeros((2, 1, self.hidden), np.float32)
        self.c = np.zeros((2, 1, self.hidden), np.float32)
        # Blank first: position 0 of the decoder output is "nothing emitted yet".
        dout, self.h, self.c = self._decode(np.array([[self.blank]], np.int64), self.h, self.c)

        def _pred(dout_arr):
            """The decoder output at its last position, shaped for the joint."""
            last = np.transpose(dout_arr, (0, 2, 1))[0][-1]
            return np.ascontiguousarray(last.reshape(1, 1, self.hidden), dtype=np.float32)

        dd = _pred(dout)
        limit = self.max_sym * T + 16
        ti = 0
        guard = 0
        chunk_ids = []
        # ONE joint call per (frame, label) cell. MEASURED reason this is not
        # batched: scanning several frames in a single joint call and picking the
        # first non-blank gave 89 tokens / RTF 0.45 on sample1.flac, including
        # doubled word tails ("country roadss", "fortnightnight'll", "worshi
        # on"). Evaluating the same frames one at a time gave 81 tokens and no
        # doubling. The two disagree because a batched GEMM over N frames and a
        # single-frame GEMM do not produce bit-identical logits, so a frame whose
        # top-2 are within float noise flips, the walk skips it, and every later
        # symbol lands one position out of alignment. The extra calls cost ~7
        # joint evaluations per 560 ms chunk and buy an aligned transcript.
        while ti < T and guard < limit:
            guard += 1
            e1 = np.ascontiguousarray(enc_out[:, ti : ti + 1, :], dtype=np.float32)
            y = int(
                self.joint.run(["joint_output"], {"encoder_output": e1, "decoder_output": dd})[0][
                    0, 0
                ].argmax()
            )
            # Counted per joint call: a frame whose argmax is blank is the
            # signature of "the model had nothing to emit here", which is a
            # different failure from "no audio arrived" and was indistinguishable
            # before these counters existed.
            self.frames_walked += 1
            if y == self.blank:
                self.blank_frames += 1
                ti += 1
                continue
            chunk_ids.append(y)
            self.labels.append(y)
            self.symbols += 1
            dout, self.h, self.c = self._decode(np.array([[y]], np.int64), self.h, self.c)
            dd = _pred(dout)

        self.n_chunks += 1
        if not chunk_ids:
            self.empty_chunks += 1
        self.audio_s += len(pcm_chunk) / TARGET_SR
        self.wall += time.time() - t_start
        return self.detok(chunk_ids), len(chunk_ids)


# ── device selection ──────────────────────────────────────────────────────────
def device_candidates(cfg_audio=None, wanted=None):
    """Ordered, de-duplicated list of concrete input devices to try.

    Order is the whole contract here. `wanted` (an explicit `--device`, or the
    `SOTTO_AUDIO_DEVICE` the Electron shell exports) is the owner's decision
    and goes first. Then `audio.device` from config.json — the owner's own
    file. Then `audio.preferred_devices`, then the built-in PREFERRED_DEVICES,
    which is where the shell's historical default lands. Only after every name
    above is spent do non-microphone inputs join the tail, so a rotation always
    has somewhere to go on a host whose routing renamed its endpoints.

    Names are matched as case-insensitive SUBSTRINGS (a device name carries a
    host API suffix the configured string never has) and a device index is
    never offered twice, so the caller's bounded rotation cannot re-open the
    tap it just abandoned.
    """
    import sounddevice as sd

    devs = [d for d in sd.query_devices() if d["max_input_channels"] > 0]
    cfg_audio = cfg_audio or {}

    # RUNG C -- the explicit override. It ALWAYS WINS: it is the first candidate
    # offered and, when it is present, a flat window does NOT rotate away from
    # it (see the rotation loop, which breaks instead of rotating when
    # `explicit` is set). Rotating away from a device the owner named by hand is
    # exactly the silent substitution this ladder exists to remove.
    names = []
    if wanted:
        names.append(str(wanted))
    # RUNG B -- configured names (the owner's own file, or a future operator),
    # still matched as substrings. These come AFTER the heuristic so a stale
    # literal cannot outrank a live endpoint.
    if cfg_audio.get("device"):
        names.append(str(cfg_audio["device"]))
    names.extend(str(n) for n in (cfg_audio.get("preferred_devices") or ()))
    names.extend(PREFERRED_DEVICES)

    # De-duplicate on the PHYSICAL ENDPOINT, not the PortAudio index. Measured
    # on this host: `sd.query_devices()` lists one cable under four indices with
    # four different truncations of the same name, and PortAudio appends its own
    # API suffix ("... (MME)", "(WDM-KS)"). Opening index 5 then index 9 is the
    # SAME cable, so a rotation that treated them as different candidates would
    # burn the entire budget re-probing one dead endpoint and then report
    # "tried every candidate" — the precise lie this change exists to remove.
    # The key is the name up to the first "(" and up to PortAudio's truncation,
    # lowercased and whitespace-collapsed.
    def endpoint_key(name):
        base = str(name).split("(")[0]
        return " ".join(base.split()).lower()

    out = []
    seen_idx = set()
    seen_ep = set()

    def offer(d, rung, why=None):
        key = endpoint_key(d["name"])
        if d.get("index") is not None and d["index"] in seen_idx:
            return False
        if key in seen_ep:
            return False
        d = dict(d)
        d["rung"] = rung
        if why:
            d["rung_why"] = why
        out.append(d)
        if d.get("index") is not None:
            seen_idx.add(d["index"])
        seen_ep.add(key)
        return True

    # RUNG C first, and only the EXPLICIT name(s) -- config names are held back
    # so they cannot displace the heuristic. `wanted` is the owner's decision.
    if wanted:
        low = str(wanted).strip().lower()
        for d in devs:
            if low and low in d["name"].lower():
                if offer(d, "c", "explicit override"):
                    break

    # RUNG A -- WASAPI loopback of the default render endpoint. Added as a
    # candidate only when this machine can actually open it, so a box with no
    # render endpoint silently skips to rung B rather than failing the run.
    try:
        import wasapi_loopback

        spec = wasapi_loopback.loopback_device_spec()
    except Exception as exc:  # import or enumeration failure -> rung B
        spec = None
        err(f"loopback rung unavailable: {type(exc).__name__}: {exc}")
    if spec is not None:
        offer(spec, "a", "WASAPI loopback of the default render endpoint")

    # RUNG B -- heuristic. Score every input by how much its NAME looks like the
    # PC's own output looped back, best first. No literal list is consulted.
    scored = []
    for d in devs:
        score, pat = heuristic_loopback_score(d["name"])
        if score:
            scored.append((score, pat, d))
    scored.sort(key=lambda t: -t[0])
    for score, pat, d in scored:
        offer(d, "b", f"name matches {pat!r}")

    # Configured names (audio.device / preferred_devices / PREFERRED_DEVICES).
    for name in names:
        low = name.strip().lower()
        if not low:
            continue
        for d in devs:
            if low in d["name"].lower():
                offer(d, "b", f"configured name {name!r}")
                # ONE device per configured name: every further match is the
                # same physical endpoint behind another host API.
                break

    # Tail: any remaining non-microphone input, so a rotation always has
    # somewhere to go on a host whose routing renamed its endpoints. A
    # Sound-Mapper / Primary-Capture PSEUDO-device is not such a place — see
    # SOUNDMAPPER_PATTERNS above: it is a redirect, not an endpoint, and a
    # loopback never comes through it. Excluded here so the ladder never spends
    # a window on it and never reports its digital silence as the run's device.
    for d in devs:
        low = d["name"].lower()
        if "micro" in low or "mic" in low:
            continue
        if is_soundmapper_pseudo(d["name"]):
            continue
        offer(d, "tail", "remaining non-microphone input")
    return out


def resample_to_16k(x, src):
    """numpy-only resample. Exact integer ratios use block averaging."""
    import numpy as np

    if src == TARGET_SR:
        return x.astype(np.float32)
    if len(x) < 2:
        return np.zeros(0, dtype=np.float32)
    if src > TARGET_SR and src % TARGET_SR == 0:
        k = src // TARGET_SR
        usable = (len(x) // k) * k
        return x[:usable].reshape(-1, k).mean(axis=1).astype(np.float32)
    n = int(len(x) * TARGET_SR / src)
    if n <= 1:
        return np.zeros(0, dtype=np.float32)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


# ── automatic gain, LIVE capture branch only (lane SottoAutoGain) ────────────
# MEASURED 2026-10-06 — the SAME worker, device and code path produced ZERO
# captions when the loopback carried a QUIET source and FIVE when it carried the
# same speech at normal level:
#   quiet  : peak=0.100510 rms=0.0147 -> 35/35 frames blank, blank_frac=1.0000,
#            captions=0
#   normal : peak=0.620738 rms=0.0689 -> blank_frac=0.8623, captions=5
#            (["Sobre o", "O rio", "Segunda", "Os moradores", "O rádio"],
#             queue_drops=0, audio_s=19.60)
# The live path and the 3:1 boxcar resample are CORRECT — the same WAV played
# through the device produced captions. The ONE differing variable was amplitude.
# Nothing in the chain normalised level, so every quiet source — a browser tab at
# low volume, a video at half volume, a quiet microphone — transcribes to nothing
# while every counter reports the run green. That is the product blocker: the
# owner sees "no captions" and the pipe looks healthy end to end.
#
# FORM CHOSEN: per-block RMS target (-20 dBFS) with a CLAMPED gain and an
# ATTACK/RELEASE smoother. REJECTED: per-chunk PEAK normalisation — on a
# near-silent block the peak is ~0 and `target/peak` explodes, so the stage
# PUMPS the gain to its ceiling and amplifies the noise floor between words (a
# genuinely silent device would then be decoded as loud noise). An RMS target
# with a floor does not: at or below the floor the block is HELD, never boosted,
# and gain is smoothed so a sudden loud transient pulls it down fast (attack)
# while it recovers slowly (release).
#
# Applied to exactly the 16 kHz samples the model sees (after resample, before
# the chunker), LIVE branch only: the file arm (`selftest()`) already
# transcribes and is left untouched. `peak` in WORKER_STATS stays the RAW tap
# peak, so the pre-gain level and the applied gain are both visible; `peak_out`
# is the post-gain peak and shows the clamp is not saturating.
AGC_TARGET_DBFS = -20.0   # target RMS for the model's input (~0.1 full scale)
AGC_MAX_GAIN_DB = 24.0    # never boost more than 16x
AGC_MIN_GAIN_DB = -6.0    # never attenuate more than 2x
AGC_FLOOR_DBFS = -60.0    # at/below this the block is silence: hold, do not boost
AGC_ATTACK = 0.50         # loud transient -> pull gain DOWN fast (per ~100 ms block)
AGC_RELEASE = 0.10        # recover gain UP slowly
AGC_SUBBLOCK = 1600       # 100 ms @ 16 kHz — the block AGC_ATTACK/AGC_RELEASE are per
# ── THE ORDER: SPEECH DECISION FIRST, GAIN AFTER (lane SottoAgcSpeechOrder) ──
# The AGC (above) and the speech/music gate (below) were landed by two lanes and
# wired so that the GAIN ran FIRST, on the whole block, and the SPEECH DECISION
# ran second, inside run_chunk, on the POST-gain chunk. That order is backwards:
# the gain lifts whatever is there, speech or not. MEASURED 2026-10-06 on the
# real capture — a drone with 90% of its energy below 1 kHz, sample-for-sample
# identical 3.5 h apart, MiiChan.exe the only active session — sits at an idle
# floor ABOVE the AGC's -60 dBFS hold floor, so the old order boosted that drone
# ~17 dB BEFORE anything asked whether it was speech. The owner's rule is the
# other way round: decide first, then amplify only what the decision kept.
# So `asr_thread` now runs `gate.is_speech` on the PRE-GAIN chunk, and `AutoGain`
# is TOLD that decision: `process(block, speech=False)` HOLDS — no gain is moved
# and none is applied, so a non-speech source passes through at unity. The gain
# the stage WOULD have applied is still recorded (`would_*`) so an arm can report
# what it did against what it would have done.


class AutoGain:
    """Bounded, smoothed RMS-target automatic gain for the live capture branch.

    One instance per run; `reset()` when the tap rotates to a new device. The
    form decision is stated once, in the module comment above, and `process()`
    is the only place the gain moves. Silent/empty blocks are returned untouched
    so nothing is invented where the source had no signal.

    THE ORDER (lane SottoAgcSpeechOrder). `process()` takes the speech decision
    made by the gate on the PRE-GAIN signal. When `speech=False` the gain is
    neither moved nor applied: the block is returned at UNITY, so a non-speech
    source (a drone, an idle floor) is never amplified. `would_*` record the
    RMS-target gain the stage WOULD have asked for regardless, so a run can
    report what it did against what it would have done.
    """

    def __init__(
        self,
        target_dbfs=AGC_TARGET_DBFS,
        max_gain_db=AGC_MAX_GAIN_DB,
        min_gain_db=AGC_MIN_GAIN_DB,
        floor_dbfs=AGC_FLOOR_DBFS,
        attack=AGC_ATTACK,
        release=AGC_RELEASE,
    ):
        self.target_dbfs = float(target_dbfs)
        self.max_gain_db = float(max_gain_db)
        self.min_gain_db = float(min_gain_db)
        self.floor_dbfs = float(floor_dbfs)
        self.attack = float(attack)
        self.release = float(release)
        # Published figures are RUN maxima — set here and NEVER cleared by reset(),
        # so a mid-run device rotation cannot make the run's loudest gain
        # unreportable. (Defect found by the peer falsifier on _main/bfrc_head.jsonl:
        # a tick printed gain_max_db=+20.1 / peak_out=0.7679 and the final line then
        # printed +2.4 / 0.0075, because reset() cleared them on rotation.)
        self.min_applied_db = 0.0
        self.max_applied_db = 0.0
        self.peak_out = 0.0
        self.blocks = 0
        self.gain_db = 0.0
        # WHAT THE STAGE WOULD HAVE DONE, and whether it was allowed to act.
        # `would_db` is the RMS-target gain asked for by the last block that had
        # a level above the floor, speech or not; `would_min/max_db` are its run
        # range. They are the "would-have" against the "_applied_" the stats line
        # already reports, so a non-speech arm can state the boost it did NOT take.
        self.would_db = 0.0
        self.would_min_db = 0.0
        self.would_max_db = 0.0
        self.non_speech_blocks = 0   # blocks the gate called not-speech: gain HELD at unity
        self.speech_blocks = 0       # blocks the gate kept: gain applied

    def reset(self):
        """Forget ONLY the smoothing state: a rotated-to device starts from unity
        gain. The published maxima above are run figures and are deliberately kept."""
        self.gain_db = 0.0

    def process(self, block, speech=True):
        """Return `block` with the smoothed gain applied — to SPEECH ONLY.

        `speech` is the pre-gain decision from the speech/music gate (lane
        SottoSpeechSeparation). When it is True the RMS-target gain is smoothed
        and applied. When it is False the gain is HELD — not moved and not
        applied — and the block is returned at unity, so a drone/idle floor is
        never amplified. The block is walked in `AGC_SUBBLOCK` (~100 ms) pieces so
        the attack/release smoothing keeps the timing it was calibrated for even
        though the caller now hands over a whole chunk. Never raises on silence.
        """
        import numpy as np

        if block.size == 0:
            return block
        if block.size <= AGC_SUBBLOCK:
            return self._process_sub(block, speech)
        out = np.empty_like(block)
        for i in range(0, block.size, AGC_SUBBLOCK):
            j = min(i + AGC_SUBBLOCK, block.size)
            out[i:j] = self._process_sub(block[i:j], speech)
        return out

    def _process_sub(self, sub, speech):
        import numpy as np

        if sub.size == 0:
            return sub
        rms = float(np.sqrt(np.mean(sub.astype(np.float64) ** 2)))
        if rms <= 1e-12:
            return sub                        # digital silence: nothing to boost
        rms_db = 20.0 * math.log10(rms)
        if rms_db > self.floor_dbfs:
            desired = self.target_dbfs - rms_db
            desired = min(self.max_gain_db, max(self.min_gain_db, desired))
            # WHAT IT WOULD HAVE APPLIED — recorded whether or not it is allowed to.
            self.would_db = desired
            self.would_min_db = min(self.would_min_db, desired)
            self.would_max_db = max(self.would_max_db, desired)
            if speech:
                coef = self.attack if desired < self.gain_db else self.release
                self.gain_db += coef * (desired - self.gain_db)
        if not speech:
            # HELD: the decision said not-speech. No gain moved, none applied;
            # the drone passes through untouched. This is the whole point of the
            # order — the gain is never allowed to amplify a non-speech source.
            self.non_speech_blocks += 1
            return sub
        # Gain HELD (at its last value) across sub-floor blocks: a pause must not
        # pump, and the level is already right when speech resumes.
        g = 10.0 ** (self.gain_db / 20.0)
        out = (sub * g).astype(np.float32)
        np.clip(out, -1.0, 1.0, out=out)
        self.blocks += 1
        self.speech_blocks += 1
        p = float(np.abs(out).max()) if out.size else 0.0
        if p > self.peak_out:
            self.peak_out = p
        self.min_applied_db = min(self.min_applied_db, self.gain_db)
        self.max_applied_db = max(self.max_applied_db, self.gain_db)
        return out


# ── speech/music decision, cheap and local (lane SottoSpeechSeparation) ─────
# OWNER: "precisamos de algo novo. que divida musica de fala, isole a fala, e ai
# aplicamos a legenda ao vivo nisso."
#
# WHAT WAS MEASURED FIRST, before any threshold was written (`worker/_probe/
# gate_sweep.py`, pasted in docs/audit/speech-separation.md). The per-chunk
# 560 ms SPECTRAL features do NOT separate this box's drone from real speech:
# median spectral centroid 471 Hz (drone) vs 465 Hz (sample1 speech) and median
# energy-above-3 kHz 1.8% vs 1.4%. Speech here is low-frequency-heavy too, so a
# spectral rule gates the speech out along with the music.
#
# The feature that DOES separate them is TEMPORAL, and it is still computed
# PER CHUNK: split the 560 ms chunk into 20 ms sub-frames and take the dB RANGE
# of the sub-frame RMS. A drone/tone/ambient bed is stationary (its level barely
# moves inside 560 ms); speech is syllabically modulated and swings far wider.
# MEASURED over 6 fixtures:
#   drone (captured)  dbrange med 12.5 / 9.5, max 15.6  (one 63 dB transient)
#   pure 60 Hz tone   dbrange 1.3
#   pink noise        dbrange 7.6
#   digital silence   dbrange 0.0
#   speech x4         dbrange med 27.5 / 30.5 / 30.8 / 40.0, p10 20.2
# The empty band between 15.6 (worst non-speech) and 20.2 (worst speech p10) is
# where GATE_DB_RANGE_MIN lives. This is a SPEECH-PRESENCE gate, not a music
# classifier: percussive music has syllabic-rate dynamics too and is only
# partially separated — stated honestly rather than overclaimed (see the audit
# doc's `falta-no-gate:` row). Real source separation is the escalation, and it
# is NOT taken: a Demucs htdemucs checkpoint is ~80 MB on disk and runs at RTF
# ~1-3 on CPU (seconds of model time per second of audio) — orders of magnitude
# past this gate's ~0.2 ms/chunk. Measured cost of THIS gate: printed in the
# audit doc's SELF-AUDIT / cost section.
GATE_SUBFRAME = 320          # 20 ms at 16 kHz
GATE_DB_RANGE_MIN = 18.0     # dB span of sub-frame RMS inside one 560 ms chunk
GATE_RMS_FLOOR = 0.004       # below this the chunk is silence, not speech
GATE_HOLD_CHUNKS = 3         # after speech, keep the gate OPEN this many chunks


class SpeechMusicGate:
    """Per-chunk speech/music decision. numpy only, no new dependency, no cloud.

    `is_speech(chunk)` returns True to KEEP the chunk (feed the encoder) and
    False to GATE it out (music/ambient/silence). Stateful only in the hangover
    counter: one chunk that dips below the threshold — a stop closure inside a
    word, a 20 ms lull — does not chop the utterance, because the gate stays
    OPEN for GATE_HOLD_CHUNKS chunks after the last speech chunk.

    The dB range is a RATIO, so it is immune to the automatic gain upstream: a
    constant gain shifts every sub-frame the same way and leaves the span
    unchanged. That is why AGC (SottoAutoGain) and this gate do not fight.
    """

    def __init__(self, db_range_min=None, rms_floor=None,
                 hold_chunks=None, subframe=None):
        # Read the module constants at CALL time, not as default arguments:
        # default-argument values are bound once at class-definition time, so
        # `W.GATE_DB_RANGE_MIN = X` after import had NO effect and the oracle's
        # mutation arm could not move the threshold (measured: mutated to 999.0,
        # oracle still PASSED). The constants are the single source of truth.
        self.db_range_min = float(GATE_DB_RANGE_MIN if db_range_min is None else db_range_min)
        self.rms_floor = float(GATE_RMS_FLOOR if rms_floor is None else rms_floor)
        self.hold = int(GATE_HOLD_CHUNKS if hold_chunks is None else hold_chunks)
        self.sub = int(GATE_SUBFRAME if subframe is None else subframe)
        self._open_for = 0        # chunks of hangover left
        # Published figures, for the WORKER_STATS line and the audit doc.
        self.gated = 0
        self.kept = 0
        self.last_db_range = 0.0
        self.last_rms = 0.0

    def reset(self):
        """A new device is a new stream: drop the hangover and the last figures."""
        self._open_for = 0
        self.last_db_range = 0.0
        self.last_rms = 0.0

    def is_speech(self, chunk) -> bool:
        import numpy as np

        n = int(chunk.size)
        nsub = n // self.sub
        if nsub < 2:
            # Too short to measure dynamics: never gate on a chunk we cannot
            # measure — withholding audio on missing evidence is the silent
            # substitution this file's device ladder exists to remove.
            self.kept += 1
            return True
        c = chunk.astype(np.float64)
        e = np.sqrt(np.mean((c.reshape(nsub, self.sub)) ** 2, axis=1) + 1e-20)
        rms = float(np.sqrt(np.mean(c ** 2)))
        db = 20.0 * np.log10(e / (e.mean() + 1e-12) + 1e-12)
        span = float(db.max() - db.min())
        self.last_db_range = span
        self.last_rms = rms
        speech = (rms >= self.rms_floor) and (span >= self.db_range_min)
        if speech:
            self._open_for = self.hold
        elif self._open_for > 0:
            self._open_for -= 1
            speech = True                 # inside the hangover: a held word
        if speech:
            self.kept += 1
        else:
            self.gated += 1
        return speech


def _host_api_name(dev):
    """Human-readable host API behind a PortAudio device dict.

    A device NAME is not enough to identify what was opened. Measured on this
    host: "CABLE Output (VB-Audio Virtual Cable)" exists at THREE indices under
    three different host APIs (MME, DirectSound, WASAPI), and only the API
    distinguishes them. A failure report that names the device without the API
    cannot be acted on, because the fix is usually "open the same cable through
    a different API".
    """
    # A synthetic candidate (rung a) has no PortAudio hostapi index; it carries
    # its own name, and reporting it by index would label WASAPI loopback
    # wrongly (index None would read the LAST host API in the list).
    if dev.get("hostapi_name"):
        return dev["hostapi_name"]
    if dev.get("hostapi") is None:
        return "unknown host API"
    try:
        import sounddevice as sd

        return sd.query_hostapis(dev["hostapi"])["name"]
    except Exception:
        return f"hostapi-{dev.get('hostapi')}"


# ── capture ───────────────────────────────────────────────────────────────────
class _PortAudioTap:
    """Callback capture through sounddevice/PortAudio (rung b and the tail).

    A blocking read is not available on this host.
    """

    def __init__(self, device, on_block, want_rate=TARGET_SR, block_ms=100):
        import numpy as np
        import sounddevice as sd

        self.np = np
        self.on_block = on_block
        self.device = device
        self.channels = min(2, int(device["max_input_channels"]))
        self.block_ms = block_ms

        # Ask for 16 kHz mono directly; WASAPI converts for us when it can.
        self.rate = want_rate
        self.native_rate = None
        try:
            sd.check_input_settings(
                device=device["index"], channels=1, dtype="float32", samplerate=want_rate
            )
        except Exception:
            self.rate = int(device["default_samplerate"])
            self.native_rate = self.rate
        self.block = int(self.rate * block_ms / 1000)

        self.stream = sd.InputStream(
            device=device["index"],
            channels=1,
            samplerate=self.rate,
            dtype="float32",
            blocksize=self.block,
            callback=self._cb,
        )

    def _cb(self, indata, frames, time_info, status):
        if status:
            err(f"portaudio: {status}")
        mono = indata
        if mono.ndim > 1:
            mono = mono.mean(axis=1)
        self.on_block(self.np.ascontiguousarray(mono, dtype=self.np.float32))

    def __enter__(self):
        self.stream.start()
        return self

    def __exit__(self, *exc):
        try:
            self.stream.stop()
            self.stream.close()
        except Exception:
            pass
        return False


def LoopbackTap(device, on_block, want_rate=TARGET_SR, block_ms=100):
    """Factory for the ladder's rung (a) and the PortAudio rungs.

    Kept as a FUNCTION under the name the run loop already calls, so the rotation
    loop, the tap ledger and the silent-device verdict are untouched by which
    backend a rung uses.

    Rung (a) hands back a WasapiLoopbackTap -- a real loopback CAPTURE client on
    the default render endpoint. It delivers float32 mono at the endpoint's MIX
    rate (typically 48 kHz), because a loopback stream has no format negotiation
    and must be initialised with the mix format; `resample_to_16k` downstream
    does the 48k -> 16k step (an exact 3:1 ratio, so it is block averaging, not
    interpolation).
    """
    if device.get("wasapi_loopback"):
        import wasapi_loopback

        return wasapi_loopback.WasapiLoopbackTap(on_block, block_ms=block_ms)
    return _PortAudioTap(device, on_block, want_rate=want_rate, block_ms=block_ms)


# ── provider selection ────────────────────────────────────────────────────────
def choose_providers(requested, model_dir=None):
    """Return (providers, available, note, probed_model).

    A registered CUDA provider is not a working one: onnxruntime-gpu registers
    CUDAExecutionProvider and then fails to dlopen it when the CUDA runtime is
    absent, silently leaving a CPU-only session. So we probe it with a real
    session and fall back honestly.

    `model_dir` is the model THIS RUN will load. The probe used to open
    os.path.join(DEFAULT_MODEL, "joint.onnx") — the …-int4 export — no matter what
    config.json said, so the CUDA liveness test ran against a graph the run never
    loaded (docs/audit/model-config.md §6.5). The probed path is now derived from
    the configured model and RETURNED, so a run can print which export it probed.
    """
    import onnxruntime as ort

    available = list(ort.get_available_providers())
    if isinstance(requested, str):
        requested = requested.split(",")
    # Short names are what a person types and what the flag's help promises
    # ("comma list"). MEASURED: `--providers cuda` matched nothing in `available`
    # and was dropped as "not registered here", so the arm silently ran on CPU.
    aliases = {
        "cpu": "CPUExecutionProvider",
        "cuda": "CUDAExecutionProvider",
        "gpu": "CUDAExecutionProvider",
        "trt": "TensorrtExecutionProvider",
        "tensorrt": "TensorrtExecutionProvider",
    }
    req = [aliases.get(p.strip().lower(), p.strip()) for p in (requested or []) if p.strip()]
    auto = not req or "auto" in [p.lower() for p in req]
    if auto:
        req = ["CUDAExecutionProvider", "CPUExecutionProvider"]

    order = [p for p in req if p in available]
    missing = [p for p in req if p not in available]
    # An EXPLICIT request is honoured exactly. MEASURED reason: `--providers cpu`
    # used to be silently overridden by the append loop below, so a run meant to
    # isolate the execution provider ran on CUDA anyway -- and the two do not
    # agree on these quantized graphs (see the note in run_chunk). A flag that
    # names providers must be able to say "not those".
    if not auto:
        if missing:
            err(f"choose_providers: not registered here, ignored: {missing}")
    else:
        for p in available:
            if p not in order and p != "TensorrtExecutionProvider":
                order.append(p)
        if "CPUExecutionProvider" not in order:
            order.append("CPUExecutionProvider")

    note = ""
    # Probe the model THIS RUN will load, not a hard-coded export (see docstring).
    probed_model = os.path.join(model_dir or DEFAULT_MODEL, "joint.onnx")
    if "CUDAExecutionProvider" in order:
        try:
            so = ort.SessionOptions()
            so.log_severity_level = 4
            probe = ort.InferenceSession(probed_model, so, providers=["CUDAExecutionProvider"])
            if "CUDAExecutionProvider" not in probe.get_providers():
                order.remove("CUDAExecutionProvider")
                note = "cuda-registered-but-not-loadable"
            del probe
        except Exception as exc:
            if "CUDAExecutionProvider" in order:
                order.remove("CUDAExecutionProvider")
            note = f"cuda-unavailable: {type(exc).__name__}: {str(exc)[:160]}"
    if "CUDAExecutionProvider" not in order and not note:
        note = "cuda-not-registered"
    return order, available, note, probed_model


# ── caption formulation: the chunk stream -> a readable LINE ─────────────────
# THE DEFECT THIS CLOSES (owner, 2026-10-06: "tem palavras, inves de frases").
#
# `nemotron-3.5-asr-streaming-0.6b` is a STREAMING RNN-T: `run_chunk()` returns
# the text decoded from ONE 560 ms chunk, and consecutive chunks are DELTAS
# ("A" | "Segunda" | "Seg" | "Os mora"), not a re-reading of the utterance.
# Both emitters used to print each chunk VERBATIM, so the panel received a
# shower of fragments and showed them one at a time. Nothing joined them,
# because nothing owned the line.
#
# The boundary rules below are the SAME ones `app/electron/caption-formulation.js`
# applies at the renderer (`SENTENCE_GAP_S`, `SENTENCE_MAX_CHARS`), reused rather
# than re-invented so the two layers cannot disagree about where a line ends. The
# difference is WHERE they run: there the panel joins the fragments it received;
# here the worker never emits a bare fragment, so every consumer of the JSONL —
# the panel, the oracles, a human reading run.log — sees a line, not a word.

# Audio seconds of silence that ends a line. Measured on the owner's own stream:
# within-burst fragment gaps reached 2.80 s and the next distinct step was
# 11.20 s, so the boundary lives in the empty band between them. Same constant
# as `caption-formulation.js:72`; one value, two layers, no second convention.
SENTENCE_GAP_S = 8.0

# Hard cap, so a speaker who never pauses cannot grow one line without bound.
# Same value as `caption-formulation.js:73`.
SENTENCE_MAX_CHARS = 90

# Sentence-ending marks. A line ending in one of these is closed where it is.
LINE_TERMINAL = ".!?…"


class LineFormer:
    """Accumulate decoded chunk text into a LINE, and say when to emit it.

    Pure: it owns no I/O and no clock. `push()` returns the caption events the
    caller must emit, so ONE object is exercised by the self-test arm, the live
    arm, and the boundary-rule oracle (`_main/caption-lines-oracle.py`).

    `min_chars` is `output.min_chars` — the floor the emitters already applied to
    a fragment; it is now applied to the LINE.
    `emit_partial` is `output.partial`: True ships the running line as it GROWS
    (the owner's ask — a phrase that grows, not a column of words), False ships
    the line only once it CLOSES.
    """

    def __init__(self, min_chars=1, emit_partial=True, gap_s=SENTENCE_GAP_S,
                 max_chars=SENTENCE_MAX_CHARS):
        self.min_chars = 1 if int(min_chars) < 1 else int(min_chars)
        self.emit_partial = bool(emit_partial)
        self.gap_s = float(gap_s)
        self.max_chars = int(max_chars)
        self.reset()

    def reset(self):
        self._words = []
        self._start = None
        self._end = None
        # The text this LINE last sent, so a partial and the final of the same
        # text cannot both go out. Reset with the line, never across lines.
        self._shown = None

    def line(self):
        return " ".join(self._words).strip()

    def _worthy(self, text):
        return len(text.strip()) >= self.min_chars

    def _event(self, text):
        return {
            "type": "caption",
            "text": text,
            # `start` is the START OF THE LINE, never the newest chunk's start.
            # A renderer that joins fragments itself (panel.js /
            # caption-formulation.js) detects a re-cover by `start < lastAudioEnd`
            # and REPLACES the line it already shows; sending the chunk's own
            # start instead reads as a NEW fragment and the line duplicates
            # itself word for word. MEASURED against the real renderer module.
            "start": None if self._start is None else round(self._start, 2),
            "end": None if self._end is None else round(self._end, 2),
        }

    def _close(self):
        text = self.line()
        out = []
        if text and self._worthy(text) and text != self._shown:
            out.append(self._event(text))
        self._words, self._start, self._end, self._shown = [], None, None, None
        return out

    def push(self, text, start=None, end=None):
        """Feed ONE decoded chunk; return the caption events to emit (0..2)."""
        frag = (text or "").strip()
        if not frag:
            return []
        out = []
        # (1) a silence in the AUDIO closes the line BEFORE this chunk. This is
        # the boundary the old 1200 ms WALL-clock rule could never see.
        if (
            self._words
            and self._end is not None
            and start is not None
            and (start - self._end) >= self.gap_s
        ):
            out += self._close()
        # (2) the cap is a LOOKAHEAD, so the fragment that would overflow opens
        # the next line instead of being appended to a line already full.
        if self._words and (len(self.line()) + 1 + len(frag)) > self.max_chars:
            out += self._close()
        # (3) append, remembering where the LINE began.
        if not self._words:
            self._start = start
        self._words.append(frag)
        if end is not None:
            self._end = end
        # (4) terminal punctuation closes AFTER this chunk — the model has
        # already decided the sentence ended.
        line = self.line()
        if line and line[-1] in LINE_TERMINAL:
            out += self._close()
        elif self.emit_partial and self._worthy(line):
            self._shown = line
            out.append(self._event(line))
        return out

    def flush(self):
        """End of stream is a boundary: return the line still held, if any."""
        return self._close()


# ── selftest ──────────────────────────────────────────────────────────────────
def selftest(asr, audio_path, args, min_chars=1, partial=True):
    """Prove the model works with NO audio device involved.

    `min_chars` is `output.min_chars` from config.json — the same caption floor the
    live path applies, so the two emitters cannot drift. Default 1 = the code's own
    historic `if text.strip():` threshold. `partial` is `output.partial`: whether
    the growing line is emitted as it grows, or only once it closes.
    """
    import soundfile as sf

    pcm, sr = sf.read(audio_path, dtype="float32")
    if pcm.ndim > 1:
        pcm = pcm.mean(axis=1)
    if sr != TARGET_SR:
        pcm = resample_to_16k(pcm, sr)
    total_chunks = len(pcm) // asr.chunk
    if total_chunks == 0:
        emit(type="status", state="error", stage="selftest", detail="audio shorter than one chunk")
        return 2

    emit(
        type="status",
        state="selftest-start",
        audio=os.path.basename(audio_path),
        audio_s=round(len(pcm) / TARGET_SR, 3),
        chunks=total_chunks,
    )
    t0 = time.time()
    # One LineFormer for the whole file, flushed at the end: the chunk stream is
    # joined into lines here, so this arm and the live arm cannot drift.
    former = LineFormer(min_chars=min_chars, emit_partial=partial)
    for i in range(total_chunks):
        text, n = asr.run_chunk(pcm[i * asr.chunk : (i + 1) * asr.chunk])
        for event in former.push(
            text,
            round(i * asr.chunk / TARGET_SR, 2),
            round((i + 1) * asr.chunk / TARGET_SR, 2),
        ):
            emit(model=asr.name, **event)
    for event in former.flush():
        emit(model=asr.name, **event)
    wall = time.time() - t0
    full = asr.detok(asr.labels)
    emit(
        type="status",
        state="selftest-done",
        text=full,
        empty=(full.strip() == ""),
        tokens=len(asr.labels),
        audio_s=round(asr.audio_s, 3),
        infer_wall_s=round(wall, 3),
        rtf=round(wall / asr.audio_s, 3) if asr.audio_s else None,
        frames=asr.frames_walked,
        blanks=asr.blank_frames,
        blank_frac=round(asr.blank_frames / asr.frames_walked, 4) if asr.frames_walked else None,
        empty_chunks=asr.empty_chunks,
        vad_gated_chunks=asr.vad_gated_chunks,
        music_gated_chunks=asr.music_gated_chunks,
        gate=("on" if asr.gate else "off"),
        peak_rss_mb=round(peak_rss_mb(), 1),
    )
    # The human-readable proof goes to STDERR, never stdout: stdout is the
    # inter-process contract (one JSON object per line) and every non-JSON byte
    # there is counted as BRIDGE_MALFORMED by the shell that consumes it.
    print("--- selftest ---", file=sys.stderr)
    print(f"audio        : {audio_path}", file=sys.stderr)
    print(f"audio_s      : {asr.audio_s:.3f}", file=sys.stderr)
    print(f"load_s       : {asr.load_s:.3f}", file=sys.stderr)
    print(f"infer_wall_s : {wall:.3f}", file=sys.stderr)
    print(f"rtf          : {(wall / asr.audio_s) if asr.audio_s else 0:.3f}", file=sys.stderr)
    print(f"tokens       : {len(asr.labels)}", file=sys.stderr)
    print(
        f"blank_frac   : {(asr.blank_frames / asr.frames_walked) if asr.frames_walked else 0:.4f} "
        f"(frames={asr.frames_walked} empty_chunks={asr.empty_chunks} "
        f"vad_gated_chunks={asr.vad_gated_chunks} "
        f"music_gated_chunks={asr.music_gated_chunks} gate={'on' if asr.gate else 'off'})",
        file=sys.stderr,
    )
    print(f"peak_rss_mb  : {peak_rss_mb():.1f}", file=sys.stderr)
    print(f"providers    : {asr.providers}", file=sys.stderr)
    print(f"RECOGNISED   : {full!r}", file=sys.stderr)
    print("--- end selftest ---", file=sys.stderr)
    return 0


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Sotto caption worker (JSONL on stdout)")
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--selftest", action="store_true", help="transcribe a file, no audio device needed")
    ap.add_argument("--audio", default=None, help="audio for --selftest (default: bundled sample1.flac)")
    ap.add_argument("--device", default=None, help="substring of the input device name")
    ap.add_argument("--model", default=None)
    ap.add_argument(
        "--lang-id",
        default=None,
        help="language prompt for the model: an id (12), a tag (pt-BR), 'auto' (101; the "
        "shipped config default), or 'os' = the host's user locale (falls back to auto). "
        "Overrides SOTTO_LANG_ID and config.json's model.lang_id. An undeclared "
        "value is refused, never clamped.",
    )
    ap.add_argument("--max-chunks", type=int, default=0, help="stop after N chunks (0 = forever)")
    ap.add_argument("--providers", default=None, help="comma list, or 'auto'")
    ap.add_argument("--max-seconds", type=float, default=0.0, help="stop after N seconds of wall time")
    ap.add_argument("--threads", type=int, default=0, help="BLAS/OMP threads (0 = auto)")
    ap.add_argument(
        "--stats-interval",
        type=float,
        default=10.0,
        help="seconds between WORKER_STATS stage counters on stderr (0 = off)",
    )
    ap.add_argument(
        "--tap-window",
        type=float,
        default=0.0,
        help="seconds a flat tap is given before rotating (0 = built-in default)",
    )
    ap.add_argument(
        "--tap-peak-floor",
        type=float,
        default=0.0,
        help="peak amplitude a tap must reach to count as carrying audio (0 = built-in default)",
    )
    args = ap.parse_args()

    limit_threads(args.threads)

    # stdout is a pipe: force UTF-8 or a non-ASCII caption raises UnicodeEncodeError.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

    # ── the FIRST line on stdout, before any heavy import ────────────────────
    # Measured failure this exists to prevent: a 75 s live run produced a
    # COMPLETELY EMPTY stdout — not even a boot line — because the first `emit`
    # sat behind `import torch` (inside _add_cuda_dll_dirs, ~10 s cold) and a real
    # CUDA InferenceSession probe of joint.onnx (several more seconds, and the
    # dlopen failure lands on stderr). Empty stdout is indistinguishable from a
    # worker that never started, which is exactly the state the shell then has to
    # guess about. A boot line carrying the pid and argv is not ambiguous, and the
    # per-stage timings below say exactly where the remaining seconds went.
    t_boot = time.time()
    emit(
        type="status",
        state="boot",
        stage="start",
        pid=os.getpid(),
        argv=sys.argv[1:],
        mode="file" if (os.environ.get("SOTTO_AUDIO_FILE") or args.selftest) else "live",
    )

    cfg = {}
    if os.path.exists(args.config):
        try:
            cfg = json.load(open(args.config, encoding="utf-8"))
        except Exception as exc:
            emit(type="status", state="error", stage="config", detail=f"{type(exc).__name__}: {exc}")
            return 2

    model_dir = args.model or cfg.get("model", {}).get("dir") or DEFAULT_MODEL
    if not os.path.isabs(model_dir):
        model_dir = os.path.join(HERE, model_dir)

    # ── `output.min_chars` — a LIVE knob as of 2026-10-06 ────────────────────
    # It used to be inert (no consumer; docs/audit/model-config.md §6.1). It is the
    # minimum length of a trimmed caption both emitters will print; the code's own
    # `if text.strip():` was always "at least 1 character", so this NAMES an
    # existing threshold rather than inventing one. A value below 1 (or a
    # non-integer) is refused back to 1, loudly, not silently clamped to something
    # else. Proven to move behaviour in docs/audit/config-inert-fixed.md.
    try:
        min_chars = int((cfg.get("output") or {}).get("min_chars", 1))
    except (TypeError, ValueError):
        min_chars = 1
    if min_chars < 1:
        err(f"config output.min_chars={((cfg.get('output') or {}).get('min_chars'))!r} is below 1; using 1")
        min_chars = 1

    # ── `output.partial` — REBUILT as a LIVE knob, 2026-10-06 ────────────────
    # This key used to be inert and was deleted the same day for that reason
    # (docs/audit/config-inert-fixed.md). It named exactly the behaviour that was
    # missing: the emitters printed each DECODED CHUNK, so a caption was a word
    # and the panel showed a column of them (owner: "tem palavras, inves de
    # frases"). It is not restored as inert text — it now SELECTS between the two
    # honest shapes of a caption stream, and both arms are proven in
    # docs/audit/caption-formulation.md §5:
    #
    #   true  (default) — the LineFormer ships the running LINE as it GROWS: the
    #                     panel shows a phrase that builds up, which is what a
    #                     live caption is.
    #   false           — only a CLOSED line is shipped. Fewer events; a consumer
    #                     that shows one caption at a time sees whole sentences
    #                     appear rather than grow.
    #
    # A non-boolean is refused back to true, loudly, like min_chars below 1.
    partial = (cfg.get("output") or {}).get("partial", True)
    if not isinstance(partial, bool):
        err(f"config output.partial={partial!r} is not a boolean; using true")
        partial = True

    # ── the language prompt, resolved ONCE and NAMED ─────────────────────────
    # Precedence: --lang-id > SOTTO_LANG_ID > config.json > 'os' sentinel (host locale).
    # config.json ships "auto" (autoSlot 101) as of 2026-10-06.
    #
    # The env rung is not decoration. worker-bridge.js#spawn builds argv as
    # `python [...extraArgs, workerPath]`, so a flag handed over by the shell
    # lands BEFORE the script path and is eaten by the interpreter instead of by
    # this parser — the same measured reason SOTTO_AUDIO_DEVICE exists. A shell
    # that must change the prompt therefore travels by env, like the device.
    #
    # This runs BEFORE _add_cuda_dll_dirs() and the model load on purpose: a
    # refused prompt must cost milliseconds, not a 1.2 GB session.
    _lp = _lang_prompt()
    if args.lang_id is not None:
        lang_requested, lang_from = args.lang_id, "cli"
    elif os.environ.get(_lp.ENV_VAR):
        lang_requested, lang_from = os.environ[_lp.ENV_VAR], "env"
    elif "lang_id" in (cfg.get("model") or {}):
        lang_requested, lang_from = cfg["model"]["lang_id"], "config"
    else:
        lang_requested, lang_from = None, "default"
    try:
        lang_res = _lp.resolve_lang_id(lang_requested, model_dir)
    except _lp.LangIdError as exc:
        emit(type="status", state="error", stage="lang-id", detail=str(exc),
             requested=lang_requested, source=lang_from)
        err(f"FATAL lang-id: {exc}")
        return 2
    lang_id = lang_res.lang_id
    emit(
        type="status",
        # `boot` + `stage`, not a new state token: both shells already render
        # `boot`, and the file's own convention for pre-load lifecycle events is
        # `state="boot", stage=...` (there is already stage="start"/"providers").
        # A brand-new state name would paint "a state this build does not name"
        # in the Electron bridge and a raw token in the webview panel.
        state="boot",
        stage="lang",
        lang_id=lang_id,
        lang=lang_res.tag,
        requested=lang_res.requested,
        source=f"{lang_from}:{lang_res.source}",
        table=lang_res.table,
        note=lang_res.note,
    )
    err(
        f"lang_id      : {lang_id} ({lang_res.tag}) "
        f"source={lang_from}:{lang_res.source} table={os.path.basename(lang_res.table)}"
    )

    use_vad = bool(cfg.get("model", {}).get("use_vad", False))

    _add_cuda_dll_dirs()
    t_cuda = time.time()
    providers, available, note, cuda_probe_model = choose_providers(
        args.providers or cfg.get("model", {}).get("providers"), model_dir
    )
    t_probe = time.time()
    emit(
        type="status",
        state="boot",
        stage="providers",
        providers_available=available,
        providers_selected=providers,
        note=note,
        # WHICH export the CUDA liveness probe opened. Printed so a run can prove
        # the probe matched the model it will load (…-int8) instead of defaulting
        # to …-int4 (docs/audit/model-config.md §6.5).
        cuda_probe_model=os.path.basename(os.path.dirname(cuda_probe_model)),
        cuda_dirs_ms=round((t_cuda - t_boot) * 1000),
        provider_probe_ms=round((t_probe - t_cuda) * 1000),
    )

    if not os.path.isdir(model_dir):
        emit(type="status", state="error", stage="model", detail=f"model dir not found: {model_dir}")
        return 2

    emit(type="status", state="model-loading", model=os.path.basename(model_dir))
    t0 = time.time()
    try:
        asr = StreamAsr(model_dir, providers=providers, use_vad=use_vad, lang_id=lang_id)
    except Exception as exc:
        emit(
            type="status",
            state="error",
            stage="model-load",
            detail=f"{type(exc).__name__}: {exc}",
            peak_rss_mb=round(peak_rss_mb(), 1),
        )
        return 2
    asr.load_s = time.time() - t0
    emit(
        type="status",
        state="model-loaded",
        model=asr.name,
        providers=asr.providers,
        load_s=round(asr.load_s, 2),
        rss_mb=round(current_rss_mb(), 1),
        peak_rss_mb=round(peak_rss_mb(), 1),
        # Read back off the constructed session, not echoed from the request:
        # `lang_id`/`lang` here are what StreamAsr validated and will feed, and
        # `lang_input` is the encoder input the graph itself declares.
        lang_id=asr.lang_id,
        lang=asr.lang_tag,
        lang_input=asr.lang_input,
    )

    # ── the speech/music gate (lane SottoSpeechSeparation) ───────────────────
    # OWNER: "que divida musica de fala, isole a fala, e ai aplicamos a legenda
    # ao vivo nisso". The gate is on by DEFAULT for the LIVE capture branch (the
    # branch the owner watches) and off by default for the file/`--selftest`
    # branch, because the file branch is what every existing oracle compares
    # against and its output must not move under them. An explicit SOTTO_GATE
    # wins in BOTH branches — `SOTTO_GATE=1` turns the file arm into the
    # negative/positive control harness this lane's proof runs use, and
    # `SOTTO_GATE=0` is the live CONTROL arm (same device, gate off).
    _gate_env = os.environ.get("SOTTO_GATE")
    _file_mode = bool(os.environ.get("SOTTO_AUDIO_FILE") or args.selftest)
    if _gate_env is None:
        gate_enabled = not _file_mode
    else:
        gate_enabled = _gate_env.strip().lower() not in ("0", "off", "false", "no")
    if gate_enabled:
        asr.gate = SpeechMusicGate()
    emit(
        type="status",
        state="gate",
        gate="on" if gate_enabled else "off",
        source="env" if _gate_env is not None else ("file-default" if _file_mode else "live-default"),
        db_range_min=GATE_DB_RANGE_MIN,
        rms_floor=GATE_RMS_FLOOR,
        hold_chunks=GATE_HOLD_CHUNKS,
    )

    # ── the SECOND mode: transcribe a FILE instead of the loopback ───────────
    # Reachable by ENVIRONMENT as well as by flag, and that is the whole point.
    # The Electron bridge builds argv as `python [args] <workerPath> [extraArgs]`,
    # so a flag handed over from the shell lands BEFORE the script path and is
    # eaten by the interpreter's own parser ("unknown option") instead of by this
    # file's. Capture preferences already travel by environment for exactly this
    # reason — see worker-bridge.js `#spawn` — so file mode travels the same way.
    # This is what makes the end-to-end caption path provable with REAL model text
    # and no audio device: the same worker, the same JSONL, the same renderer.
    audio_file = os.environ.get("SOTTO_AUDIO_FILE") or (args.audio if args.selftest else None)
    if args.selftest or audio_file:
        audio = audio_file or os.path.join(HERE, "assets", "sample1.flac")
        if not os.path.exists(audio):
            emit(type="status", state="error", stage="selftest", detail=f"no audio at {audio}")
            return 2
        return selftest(asr, audio, args, min_chars, partial)

    # Live capture. The tap is RESOLVED AT RUNTIME, not read once and trusted:
    # an explicit `--device`, then the shell's `SOTTO_AUDIO_DEVICE` (the channel
    # the bridge uses when the owner DID ask for a device), then config.json's
    # `audio.device`, then its `preferred_devices`, then this file's
    # PREFERRED_DEVICES. Every one of them is TRIED, not trusted — the rotation
    # loop below is what decides, and it decides on measured signal.
    wanted = args.device or os.environ.get("SOTTO_AUDIO_DEVICE") or None
    audio_cfg = cfg.get("audio") or {}
    # ── `audio.block_ms` — a LIVE knob as of 2026-10-06 ──────────────────────
    # It used to be inert: `LoopbackTap`/`WasapiLoopbackTap` take block_ms as a
    # parameter defaulting to 100, and the call site below passed none, so the
    # config file's value was decorative (docs/audit/model-config.md §6.1). It is
    # now read here and handed to the tap, where it sets the block the pump emits
    # (and the WASAPI poll period derives from it). A non-positive value is
    # refused back to 100, loudly. Proven to move `capture-started.block` in
    # docs/audit/config-inert-fixed.md.
    try:
        block_ms = int(audio_cfg.get("block_ms", 100))
    except (TypeError, ValueError):
        block_ms = 100
    if block_ms <= 0:
        err(f"config audio.block_ms={audio_cfg.get('block_ms')!r} is not positive; using 100")
        block_ms = 100
    candidates = device_candidates(audio_cfg, wanted)
    if not candidates:
        emit(type="status", state="error", stage="device", detail="no input device available")
        return 2
    tap_window = args.tap_window if args.tap_window > 0 else TAP_WINDOW_S
    tap_floor = args.tap_peak_floor if args.tap_peak_floor > 0 else TAP_PEAK_FLOOR
    emit(
        type="status",
        state="device",
        device=candidates[0]["name"],
        max_input_channels=candidates[0]["max_input_channels"],
        candidates=[d["name"] for d in candidates],
        wanted=wanted,
        tap_window_s=tap_window,
        tap_peak_floor=tap_floor,
    )

    audio_q: queue.Queue = queue.Queue(maxsize=256)
    stop = threading.Event()
    # ── one counter per stage the live path can stall at ────────────────────
    # "Zero captions" is not a diagnosis. Each of these answers a different
    # question, and until they existed the only evidence available was the
    # absence of output:
    #   blocks            did the PortAudio callback fire at all
    #   block_samples     samples handed over by that callback
    #   nonzero_blocks    of those blocks, how many carried actual signal
    #   peak              loudest single sample seen on the tap
    #   resampled_samples samples that survived the 16 kHz conversion
    #   chunks            how many reached the encoder's chunk size
    #   captions          what the model actually emitted
    #   queue_drops       blocks lost because ASR could not keep up
    counters = {
        "blocks": 0,
        "block_samples": 0,
        "nonzero_blocks": 0,
        "peak": 0.0,
        "sumsq": 0.0,
        "resampled_samples": 0,
        "chunks": 0,
        "captions": 0,
        "queue_drops": 0,
    }

    # Live-branch automatic gain (see AutoGain). `SOTTO_AGC=0` disables it — the
    # CONTROL arm for measuring the gain's effect: the SAME source, no gain.
    # MEASURED 2026-10-06 (this lane): a quiet-but-SPEECH source at tap peak
    # 0.100952 emits captions BOTH with the gain (7 captions) and WITHOUT it (6),
    # so at that level a caption/no-caption flip is NOT the instrument for this
    # stage — the stage's measured effect is the gain it applies (reported below).
    # The zero-caption case Main measured at peak 0.100510 was AMBIENT (nothing
    # playing, _main/_diary2.md:10) — speech vs no-speech, not amplitude; the peer
    # falsifier reached the same conclusion (bfrc_decisive-report.md §5).
    agc_enabled = os.environ.get("SOTTO_AGC", "1").strip().lower() not in (
        "0",
        "off",
        "false",
        "no",
    )
    agc = AutoGain()

    # `peak` above is the RUN maximum and must stay that way — it is what the
    # final WORKER_STATS reports. But a rotation log line quoting it names the
    # loudest sample of the whole RUN, not of the device being abandoned:
    # measured, all five rotations of a forced run printed peak=0.507294, the
    # first device's number, which is a claim about an already-closed device.
    # `device_peak` is reset per candidate and is the honest figure.
    device_peak = {"value": 0.0}
    # Per-candidate BLOCK COUNT, for the same reason device_peak exists: peak
    # alone cannot tell "this device delivered 400 blocks of digital silence"
    # from "this device delivered 3 blocks and then the run ended". The
    # silent-device verdict is only allowed to fire on a candidate that
    # actually ran, so it needs its own counter reset beside the peak.
    device_blocks = {"value": 0}
    # The loudest candidate that CLEARED the floor but produced no caption. The
    # acceptance test no longer settles the ladder on a bare peak: measured on
    # this box, the loopback of the default render endpoint delivers DIGITAL
    # SILENCE when nothing renders (three independent 6 s captures, peak=0.000000,
    # `_main/sdr_idlefloor.out`), so anything above the floor is real rendered
    # audio — but real rendered audio is NOT the same claim as SPEECH. The ladder
    # therefore keeps looking (the brief) and, if no candidate ever captions,
    # RE-ENTERS on this one so the run keeps streaming instead of exiting on the
    # owner. `retried` makes the re-entry happen at most once.
    best_carried = {"dev": None, "peak": 0.0, "retried": False}

    def stats_line(tag: str) -> str:
        n = max(1, counters["block_samples"])
        rms = (counters["sumsq"] / n) ** 0.5
        bf = (asr.blank_frames / asr.frames_walked) if asr.frames_walked else None
        return (
            f"WORKER_STATS tag={tag} blocks={counters['blocks']} "
            f"block_samples={counters['block_samples']} nonzero_blocks={counters['nonzero_blocks']} "
            f"peak={counters['peak']:.6f} rms={rms:.8f} "
            f"gain_db={agc.gain_db:+.1f} gain_min_db={agc.min_applied_db:+.1f} "
            f"gain_max_db={agc.max_applied_db:+.1f} peak_out={agc.peak_out:.6f} "
            f"gain_would_db={agc.would_db:+.1f} gain_would_max_db={agc.would_max_db:+.1f} "
            f"held_blocks={agc.non_speech_blocks} speech_blocks={agc.speech_blocks} "
            f"agc={'on' if agc_enabled else 'off'} "
            f"resampled_samples={counters['resampled_samples']} chunks={counters['chunks']} "
            f"captions={counters['captions']} tokens={len(asr.labels)} "
            f"frames={asr.frames_walked} blanks={asr.blank_frames} "
            f"blank_frac={bf if bf is None else round(bf, 4)} "
            f"empty_chunks={asr.empty_chunks} vad_gated_chunks={asr.vad_gated_chunks} "
            f"music_gated_chunks={asr.music_gated_chunks} "
            f"gate_kept={asr.gate.kept if asr.gate else 0} gate={'on' if asr.gate else 'off'} "
            f"queue_drops={counters['queue_drops']} "
            f"audio_s={asr.audio_s:.2f} infer_wall_s={asr.wall:.2f} rss_mb={current_rss_mb():.1f}"
        )

    def on_block(block):
        counters["blocks"] += 1
        counters["block_samples"] += int(block.size)
        device_blocks["value"] += 1
        p = float(abs(block).max()) if block.size else 0.0
        if p > counters["peak"]:
            counters["peak"] = p
        if p > device_peak["value"]:
            device_peak["value"] = p
        if p > 1e-4:
            counters["nonzero_blocks"] += 1
        counters["sumsq"] += float((block.astype("float64") ** 2).sum())
        try:
            audio_q.put_nowait(block)
        except queue.Full:
            counters["queue_drops"] += 1
            # Three, not sixty thousand: a full queue is a slow-consumer symptom
            # and the count above already carries the magnitude.
            if counters["queue_drops"] <= 3:
                err(f"audio queue full: dropping a block (drops={counters['queue_drops']})")

    # The tap is swappable underneath the ASR thread: rotation replaces the
    # stream, not the thread. `gen` is the invalidation token — a changed gen
    # means the buffer holds audio from a device that is no longer open, so it
    # is dropped rather than spliced onto the new device's first chunk, and the
    # native rate is re-read because the two devices need not agree.
    tap_holder = {"tap": None, "gen": 0}

    def asr_thread():
        import numpy as np

        buf = np.zeros(0, dtype=np.float32)
        gen = -1
        native = False
        rate = TARGET_SR
        # The chunk stream is joined into LINES here, so the panel receives a
        # phrase that grows instead of one decoded chunk per caption.
        former = LineFormer(min_chars=min_chars, emit_partial=partial)
        while not stop.is_set():
            try:
                block = audio_q.get(timeout=0.25)
            except queue.Empty:
                continue
            if tap_holder["gen"] != gen:
                gen = tap_holder["gen"]
                buf = np.zeros(0, dtype=np.float32)
                live = tap_holder["tap"]
                native = live is not None and live.rate != TARGET_SR
                rate = live.rate if live is not None else TARGET_SR
                agc.reset()  # a new device starts from unity gain
                if asr.gate is not None:
                    asr.gate.reset()  # and from a closed speech/music gate
                # A new device is a new stream: close the held line here rather
                # than splice audio from a device that is no longer open onto
                # the first chunk of its replacement.
                for event in former.flush():
                    counters["captions"] += 1
                    emit(model=asr.name, **event)
            if native:
                # WASAPI refused 16 kHz; convert here instead.
                block = resample_to_16k(block, rate)
            # Counted either way: this is the stage boundary "samples that
            # reached the ASR side at 16 kHz", and a zero here means the
            # conversion ate the audio even though the callback delivered it.
            counters["resampled_samples"] += int(block.size)
            # ── PRE-GAIN buffer ──────────────────────────────────────────────
            # The chunk the model sees is assembled here, BEFORE any gain: the
            # speech/music decision below runs on THESE samples, so the decision
            # is never made on audio the gain has already amplified (the order
            # lane SottoAgcSpeechOrder fixes — see AutoGain).
            buf = np.concatenate([buf, block])
            while len(buf) >= asr.chunk:
                seg = buf[: asr.chunk]
                buf = buf[asr.chunk :]
                counters["chunks"] += 1
                idx = counters["chunks"]
                # ── SPEECH DECISION FIRST, on the PRE-GAIN signal ────────────
                # (lane SottoSpeechSeparation's gate). `speech` is then handed
                # to the AGC — which applies gain ONLY when it is True — and to
                # run_chunk, which must NOT decide a second time on post-gain
                # audio. With the gate off this is always True, i.e. the AGC
                # behaves exactly as it did before this order was imposed.
                speech = True if asr.gate is None else asr.gate.is_speech(seg)
                # ── automatic gain, SPEECH component only (see AutoGain) ─────
                # `counters['peak']`/`sumsq` were taken from the RAW tap block,
                # so the pre-gain level and the applied gain stay independent.
                seg_in = seg  # MUTANT: AGC application removed
                try:
                    text, n = asr.run_chunk(seg_in, speech=speech)
                except Exception as exc:
                    for event in former.flush():
                        emit(model=asr.name, **event)
                    emit(type="status", state="error", stage="chunk", detail=f"{type(exc).__name__}: {exc}")
                    stop.set()
                    return
                for event in former.push(
                    text,
                    round((idx - 1) * asr.chunk / TARGET_SR, 2),
                    round(idx * asr.chunk / TARGET_SR, 2),
                ):
                    counters["captions"] += 1
                    emit(model=asr.name, **event)
                if args.max_chunks and idx >= args.max_chunks:
                    for event in former.flush():
                        counters["captions"] += 1
                        emit(model=asr.name, **event)
                    stop.set()
                    return
        # The stream stopped: the last words must not be stranded in a buffer
        # nobody will read again, so the held line is closed here.
        for event in former.flush():
            counters["captions"] += 1
            emit(model=asr.name, **event)

    # ── run the candidates until one of them is measurably alive ────────────
    # The loop is bounded twice over: at most one pass per candidate, and at
    # most `--tap-window` seconds spent on any candidate that stays flat. It
    # exits the moment a candidate proves itself — and since 2026-10-06 (lane
    # SottoDeviceRouting) PROVING itself means producing a CAPTION, not merely
    # clearing the peak floor: the floor proves the tap HEARS, not that it
    # hears SPEECH, so a bare floor no longer settles the ladder (see the
    # acceptance test in the window loop). Every candidate is tried once; if
    # none captions, the loudest signal-carrying one is re-entered so the run
    # still streams. From the moment a caption lands, that tap is simply the
    # run — a live run must not keep rotating away from the device that is
    # carrying audio.
    t_start = time.time()
    worker = threading.Thread(target=asr_thread, name="asr", daemon=True)
    worker.start()
    next_stats = time.time() + args.stats_interval if args.stats_interval > 0 else float("inf")
    outcome = "all-flat"
    rotations = 0
    device = candidates[0]
    # One row per candidate this run actually OPENED, with the peak and block
    # count MEASURED ON THAT CANDIDATE. This is the ledger the loud failure is
    # built from: without it, "every device was silent" is an assertion, and
    # the 22 s smoke run of 2026-10-06 asserted it while reporting
    # verdict="model-emitted-nothing" — a MODEL failure verdict for a DEVICE
    # failure. `proved_alive` is the positive side of the same ledger: a tap is
    # only allowed to be called the run's device once it produced a caption or
    # was the re-entered fallback.
    tap_ledger = []
    proved_alive = {"any": False, "device": None, "peak": 0.0, "reason": ""}

    def close_tap(t):
        try:
            t.stream.stop()
            t.stream.close()
        except Exception:
            pass

    try:
        for attempt_no, dev in enumerate(candidates):
            device = dev
            try:
                tap = LoopbackTap(dev, on_block, block_ms=block_ms)
            except Exception as exc:
                # Unopenable is not the same as silent, but neither is usable:
                # say which, and keep rotating rather than dying on candidate 1.
                emit(
                    type="status",
                    state="error",
                    stage="open-stream",
                    device=dev["name"],
                    detail=f"{type(exc).__name__}: {exc}",
                )
                outcome = "open-failed"
                if attempt_no + 1 >= len(candidates):
                    break
                emit(
                    type="status",
                    state="device-rotated",
                    reason="open-failed",
                    to=candidates[attempt_no + 1]["name"],
                    attempt=attempt_no + 1,
                    of=len(candidates),
                )
                rotations += 1
                continue

            tap_holder["tap"] = tap
            tap_holder["gen"] += 1
            tap.stream.start()
            emit(
                type="status",
                state="capture-started",
                device=dev["name"],
                rate=tap.rate,
                block=tap.block,
                attempt=attempt_no + 1,
                of=len(candidates),
            )
            # Per-candidate baselines. `device_peak` is reset here so the
            # settle test and the rotation log both describe THIS device and
            # not the run's high-water mark from a device already closed.
            device_peak["value"] = 0.0
            device_blocks["value"] = 0
            caps_before = counters["captions"]
            window_end = time.time() + tap_window
            settled = False
            try:
                while not stop.is_set():
                    now = time.time()
                    if args.max_seconds and (now - t_start) >= args.max_seconds:
                        outcome = "run-ended"
                        break
                    if now >= next_stats:
                        err(stats_line("tick"))
                        next_stats = now + args.stats_interval
                    # THE ACCEPTANCE TEST. A CAPTION is the only evidence that
                    # settles the ladder, and that is deliberate: `peak >=
                    # tap_floor` proves the tap HEARS SOMETHING, not that it
                    # hears SPEECH, and the brief names the cost of conflating
                    # them — the run "settled on the first non-dead one" and
                    # then reported captions=0. MEASURED on this box
                    # (`_main/sdr_idlefloor.out`): with NOTHING rendering the
                    # loopback of the default render endpoint is DIGITAL
                    # SILENCE (peak=0.000000, three independent 6 s captures),
                    # so above-floor really is rendered audio — but rendered
                    # audio is not speech, and the model's own front end gates
                    # it (`vad_gated_chunks`). So the ladder KEEPS LOOKING;
                    # `best_carried` re-enters the loudest non-captioning
                    # candidate below so the run still streams.
                    if counters["captions"] > caps_before:
                        settled = True
                    elif dev.get("rung") == "fallback" and device_peak["value"] >= tap_floor:
                        # The ladder has now TRIED EVERY candidate and none
                        # produced a caption; this is the loudest one that
                        # carried signal, re-entered so a live run keeps
                        # streaming instead of exiting on the owner.
                        settled = True
                    if settled:
                        # Proven alive: this tap is the run now, and the window
                        # no longer applies to it.
                        time.sleep(0.1)
                        continue
                    if now >= window_end:
                        outcome = "flat"
                        break
                    time.sleep(0.05)
            finally:
                tap_holder["tap"] = None
                tap_holder["gen"] += 1
                close_tap(tap)

            # The ledger row is written on the way OUT of the window, whatever
            # ended it, so it describes the CANDIDATE and not the run. It is
            # written after the tap is closed but before anything else can
            # touch the per-candidate counters, which are the honest figures
            # here — `counters["peak"]` is the run high-water mark and would
            # name a device that is already closed.
            tap_ledger.append(
                {
                    "device": dev["name"],
                    "index": dev["index"],
                    "api": _host_api_name(dev),
                    # WHICH RUNG of the ladder this candidate came from, and why.
                    # Required by the brief: a run must be able to say "I took
                    # rung (a), WASAPI loopback of the default render endpoint",
                    # not merely "I opened something".
                    "rung": dev.get("rung"),
                    "rung_why": dev.get("rung_why"),
                    "peak": round(device_peak["value"], 6),
                    "blocks": device_blocks["value"],
                    "captions": counters["captions"] - caps_before,
                    "settled": settled,
                    "outcome": outcome,
                }
            )
            # Remember the LOUDEST candidate that carried signal but produced
            # no caption. Below, when the ladder runs out with no caption, this
            # one is re-entered so the run keeps streaming instead of exiting.
            if (
                not settled
                and device_peak["value"] >= tap_floor
                and device_peak["value"] > best_carried["peak"]
            ):
                best_carried["dev"] = dev
                best_carried["peak"] = device_peak["value"]
            if settled and not proved_alive["any"]:
                proved_alive["any"] = True
                proved_alive["device"] = dev["name"]
                proved_alive["peak"] = device_peak["value"]
                proved_alive["reason"] = (
                    "caption" if counters["captions"] > caps_before else "peak>=floor"
                )

            if outcome != "flat" or stop.is_set():
                break
            # RUNG C is an EXPLICIT override and ALWAYS WINS: it is never
            # rotated away from. If the owner named a device and it carries
            # nothing, the run reports the NAMED silent-device failure below
            # rather than silently opening a different endpoint behind his
            # back -- silent substitution is the defect this ladder removes.
            if wanted and dev.get("rung") == "c":
                outcome = "explicit-flat"
                break
            nxt = candidates[attempt_no + 1] if attempt_no + 1 < len(candidates) else None
            if nxt is None:
                # RE-ENTER — the brief's "keep looking at candidates rather than
                # settling on the first non-dead one". Every candidate has now
                # been OPENED once and NONE produced a caption. If one of them
                # carried signal, commit to the loudest and keep streaming on it
                # rather than exiting on the owner with nothing. Appending to
                # `candidates` extends THIS for-loop (Python iterates lists by
                # index), so the re-entry reuses the same window machinery and
                # the same ledger; `retried` allows it at most once.
                if best_carried["dev"] is not None and not best_carried["retried"]:
                    best_carried["retried"] = True
                    fb = dict(best_carried["dev"])
                    fb["rung"] = "fallback"
                    fb["rung_why"] = (
                        "loudest signal-carrying candidate, re-entered: the ladder "
                        "opened every candidate and none produced a caption"
                    )
                    candidates.append(fb)
                    nxt = fb
                else:
                    outcome = "all-flat"
                    break
            # `from` is a Python keyword, so the payload is built as a dict.
            emit(
                **{
                    "type": "status",
                    "state": "device-rotated",
                    "reason": "flat",
                    "from": dev["name"],
                    "to": nxt["name"],
                    "peak": round(device_peak["value"], 6),
                    "run_peak": round(counters["peak"], 6),
                    "window_s": tap_window,
                    "peak_floor": tap_floor,
                    "attempt": attempt_no + 1,
                    "of": len(candidates),
                }
            )
            rotations += 1
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        try:
            worker.join(timeout=5)
        except Exception:
            pass

    if outcome in ("all-flat", "open-failed"):
        emit(
            type="status",
            state="device-exhausted",
            reason=outcome,
            detail=f"every candidate tap was flat over {tap_window}s (peak floor {tap_floor})",
            device=device["name"],
            tried=[d["name"] for d in candidates],
            rotations=rotations,
            peak=round(counters["peak"], 6),
            captions=counters["captions"],
        )

    err(stats_line("final"))

    # The exhaustion case is decided FIRST and on captions, not on tokens.
    # Measured on a forced all-flat run: `tokens=1` with `captions=0` sent this
    # chain to "captions-emitted" — a run that produced nothing announced that
    # it had produced captions. `asr.labels` holds partial symbols too, so
    # len(labels)>0 does not mean a caption was ever emitted; only the
    # `counters["captions"]` counter does.
    #
    # The branch the 2026-10-06 smoke run needed, and did not have: a candidate
    # that OPENED and delivered a full window of callbacks while never reaching
    # the peak floor is a SILENT DEVICE, and no verdict about the model is
    # honest here. Measured on that run: blocks=214, peak=0.000122 against a
    # floor of 0.002, and the run still reported "model-emitted-nothing" with
    # exit 0. The device was the fault. It is now named, and it is non-zero.
    silent_rows = [
        r
        for r in tap_ledger
        if not r["settled"] and r["blocks"] >= TAP_SILENT_BLOCKS and r["peak"] < tap_floor
    ]
    ran_but_silent = bool(silent_rows) and not proved_alive["any"]
    # ORDER IS THE CONTRACT, and it was wrong until now. This branch used to test
    # the DEVICE-SELECTION outcome FIRST, so a run that BOTH exhausted the ladder
    # AND measured a silent device reported `all-candidate-taps-flat` in its `done`
    # while the very same run emitted `state="silent-device"` and returned exit 3 —
    # the word and the code disagreed inside one run. Measured on disk before the
    # fix: worker/runs/exit3-armB-worker.jsonl, `done` verdict
    # "all-candidate-taps-flat", device_outcome "all-flat", beside a silent-device
    # status with blocks=34 (oracle: _main/verdict-order-oracle.py, red arm).
    #
    # `ran_but_silent` is the MEASURED, device-attributable fact (a candidate
    # OPENED, ran a full window and stayed under the floor); `outcome in
    # ("all-flat","open-failed")` is only the weaker statement that no candidate
    # settled. The specific fact, and the one the exit code is already built from
    # (`return 3 if ran_but_silent else 0`), is tested FIRST, so the verdict word
    # and the exit code can no longer diverge.
    if ran_but_silent:
        verdict = "silent-device"
    elif outcome in ("all-flat", "open-failed"):
        verdict = "all-candidate-taps-flat"
    elif counters["blocks"] == 0:
        verdict = "no-callback-blocks"
    elif counters["nonzero_blocks"] == 0:
        verdict = "silent-capture"
    elif counters["resampled_samples"] == 0:
        verdict = "resample-produced-nothing"
    elif counters["chunks"] == 0:
        verdict = "buffer-never-reached-chunk-size"
    elif (
        counters["captions"] == 0
        and counters["chunks"] > 0
        and asr.music_gated_chunks >= counters["chunks"]
    ):
        # Lane SottoSpeechSeparation. The tap is alive and carried signal, but
        # OUR OWN speech/music gate withheld EVERY chunk: what the endpoint is
        # carrying is not speech. Distinct from `captured-signal-has-no-speech`
        # (that one is the model's front-end VAD, no gate involved) and from a
        # model fault — the encoder was never even asked.
        verdict = "captions-all-music-gated"
    elif counters["captions"] == 0 and asr.vad_gated_chunks > 0:
        # MEASURED 2026-10-06 (lane BlankFramesRootCause). A live run landed here
        # with peak=0.101929 (floor 0.002), chunks=44, captions=0, frames=77,
        # blanks=77, and vad_gated_chunks=33 -- i.e. the tap was measurably ALIVE
        # and the model's OWN front-end withheld three quarters of the mix as
        # non-speech. The word it got was "model-emitted-nothing", which points
        # every reader at the model, and the model was provably innocent: the same
        # audio, through the same worker in file mode, transcribes a known speech
        # clip word for word (`_main/bfrc_playedfile.jsonl`). The honest name for
        # "signal arrived, the VAD called it not-speech, the model found nothing to
        # say" is NOT a model fault, and this lane exists because that word sent
        # four separate investigations after the model.
        verdict = "captured-signal-has-no-speech"
    else:
        verdict = "captions-emitted"

    # The LOUD failure. Emitted whenever a device opened, ran a real window and
    # delivered digital silence: it names the device, its host API, the peak it
    # actually reached and the floor it failed to reach, so the owner is told
    # which endpoint to re-route instead of being told the model was quiet.
    if ran_but_silent:
        loudest = max(silent_rows, key=lambda r: r["peak"])
        emit(
            type="status",
            state="silent-device",
            verdict="silent-device",
            device=loudest["device"],
            api=loudest["api"],
            peak=loudest["peak"],
            peak_floor=tap_floor,
            blocks=loudest["blocks"],
            window_s=tap_window,
            silent_min_blocks=TAP_SILENT_BLOCKS,
            detail=(
                f"{loudest['device']} [{loudest['api']}] opened and delivered "
                f"{loudest['blocks']} blocks but never reached peak {tap_floor} "
                f"(measured peak {loudest['peak']}) — digital silence, not a model fault. "
                f"{len(silent_rows)} of {len(tap_ledger)} opened candidates were silent."
            ),
            silent=silent_rows,
            tried=[d["name"] for d in candidates],
            captions=counters["captions"],
        )
        err(
            f"SILENT-DEVICE {loudest['device']} [{loudest['api']}] "
            f"peak={loudest['peak']} < floor={tap_floor} over {loudest['blocks']} blocks "
            f"({len(silent_rows)}/{len(tap_ledger)} opened candidates silent, "
            f"captions={counters['captions']})"
        )

    # THE GATE'S OWN LOUD FAILURE (lane SottoSpeechSeparation). The tap carried
    # signal and OUR speech/music gate withheld every chunk: the endpoint is
    # carrying something that is measurably not speech. `music-only-capture` is
    # a state the shells render safely: worker-bridge.js `describeState()` has no
    # mapping for it, so it falls through to `humaniseState()` -> "Worker: Music
    # only capture", and FAILURE_WORDS does not match, so it is not coloured as
    # an error. It is a fact about WHAT is playing, not a fault.
    if verdict == "captions-all-music-gated":
        emit(
            type="status",
            state="music-only-capture",
            verdict=verdict,
            device=device["name"],
            device_api=(tap_ledger[-1]["api"] if tap_ledger else None),
            peak=round(counters["peak"], 6),
            peak_floor=tap_floor,
            blocks=counters["blocks"],
            chunks=counters["chunks"],
            music_gated_chunks=asr.music_gated_chunks,
            gate_thresholds={
                "db_range_min": GATE_DB_RANGE_MIN,
                "rms_floor": GATE_RMS_FLOOR,
                "hold_chunks": GATE_HOLD_CHUNKS,
            },
            sample_rate=TARGET_SR,
            detail=(
                f"the tap is alive (peak {counters['peak']:.6f} >= floor {tap_floor}, "
                f"{counters['blocks']} blocks) but the speech/music gate withheld all "
                f"{asr.music_gated_chunks} chunks: the endpoint carries signal that is not "
                f"speech (music/ambient bed), so the encoder was never asked. This is the "
                f"feature working, not a fault."
            ),
            captions=counters["captions"],
        )
        err(
            f"MUSIC-ONLY-CAPTURE {device['name']} peak={counters['peak']:.6f} "
            f"chunks={counters['chunks']} music_gated={asr.music_gated_chunks} "
            f"captions=0 -- the endpoint carries non-speech, gated out before the encoder"
        )

    # THE OTHER LOUD FAILURE, and the one the owner was actually sitting in.
    # The tap is measurably ALIVE (peak is above the floor, blocks arrived), the
    # model ran, and the mix carried nothing the front-end would call speech --
    # the shipped VAD withheld chunks and every frame the encoder walked argmaxed
    # to blank. Naming only the model here is the defect this lane was opened for:
    # `docs/audit/blank-frames-root-cause.md` shows the same worker transcribing a
    # known speech clip through this same live tap word for word, so the model is
    # exonerated and the ENDPOINT is what has to be looked at.
    # `no-speech-in-capture` is a state BOTH shells render safely: worker-bridge.js
    # `describeState()` falls through to `humaniseState()` for any token it does not
    # know and prints "Worker: No speech in capture", and FAILURE_WORDS does not
    # match it, so it is not coloured as an error.
    if verdict == "captured-signal-has-no-speech":
        alive_chunks = max(0, counters["chunks"])
        gated = asr.vad_gated_chunks
        emit(
            type="status",
            state="no-speech-in-capture",
            verdict=verdict,
            device=device["name"],
            device_api=(tap_ledger[-1]["api"] if tap_ledger else None),
            peak=round(counters["peak"], 6),
            peak_floor=tap_floor,
            blocks=counters["blocks"],
            chunks=alive_chunks,
            vad_gated_chunks=gated,
            music_gated_chunks=asr.music_gated_chunks,
            frames=asr.frames_walked,
            blank_frac=round(asr.blank_frames / asr.frames_walked, 4) if asr.frames_walked else None,
            sample_rate=TARGET_SR,
            detail=(
                f"the tap is alive (peak {counters['peak']:.6f} >= floor {tap_floor}, "
                f"{counters['blocks']} blocks) and {alive_chunks} chunks reached the encoder, "
                f"but {gated} of them were withheld by the shipped VAD and every frame the "
                f"model walked was blank -- the capture carries signal, it does not carry "
                f"speech. This is not a model fault: re-route the app to this endpoint, or "
                f"capture the endpoint the audio is actually on."
            ),
            captions=counters["captions"],
        )
        err(
            f"NO-SPEECH-IN-CAPTURE {device['name']} peak={counters['peak']:.6f} "
            f"chunks={alive_chunks} vad_gated={gated} frames={asr.frames_walked} "
            f"captions=0 -- the endpoint carries signal that is not speech, not a model fault"
        )

    emit(
        type="status",
        state="done",
        verdict=verdict,
        blocks=counters["blocks"],
        block_samples=counters["block_samples"],
        nonzero_blocks=counters["nonzero_blocks"],
        peak=round(counters["peak"], 6),
        peak_out=round(agc.peak_out, 6),
        gain_db=round(agc.gain_db, 1),
        gain_max_db=round(agc.max_applied_db, 1),
        gain_would_db=round(agc.would_db, 1),
        gain_would_max_db=round(agc.would_max_db, 1),
        held_blocks=agc.non_speech_blocks,
        speech_blocks=agc.speech_blocks,
        agc=agc_enabled,
        resampled_samples=counters["resampled_samples"],
        chunks=counters["chunks"],
        captions=counters["captions"],
        tokens=len(asr.labels),
        queue_drops=counters["queue_drops"],
        frames=asr.frames_walked,
        blanks=asr.blank_frames,
        blank_frac=round(asr.blank_frames / asr.frames_walked, 4) if asr.frames_walked else None,
        empty_chunks=asr.empty_chunks,
        vad_gated_chunks=asr.vad_gated_chunks,
        music_gated_chunks=asr.music_gated_chunks,
        gate=("on" if asr.gate else "off"),
        audio_s=round(asr.audio_s, 2),
        infer_wall_s=round(asr.wall, 2),
        rtf=round(asr.wall / asr.audio_s, 2) if asr.audio_s else None,
        peak_rss_mb=round(peak_rss_mb(), 1),
        device=device["name"],
        device_outcome=outcome,
        tap_ledger=tap_ledger,
        proved_alive=proved_alive["any"],
        proved_device=proved_alive["device"],
        proved_reason=proved_alive["reason"],
        rotations=rotations,
        text=asr.detok(asr.labels),
    )
    # A run that captured digital silence is NOT a successful run. Returning 0
    # here is the specific defect measured on 2026-10-06: the worker opened a
    # device, heard nothing, and reported success to a caller that has no other
    # way to tell. 3 is distinct from 2 (setup error) so a caller can separate
    # "never started" from "started and got nothing".
    return 3 if ran_but_silent else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(0)
