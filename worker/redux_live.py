#!/usr/bin/env python3
"""Sotto LIVE transcriber — **Parakeet Redux (TDT)** as the engine of the live box.

WHY THIS FILE EXISTS
--------------------
The owner's request, verbatim: *"troca o nemotron 3.5 pelo parakeet redux, pra
legenda ao vivo. quero testar"*.  The live engine was the NVIDIA nemotron RNNT
streamer (`worker/sotto_worker.py`); this file is the Redux alternative, and it
speaks **the same JSONL contract on stdout**, so the panel is not touched at all.

THE SWITCH (two levels, both trivially reversible)
--------------------------------------------------
1. **WHICH process is the live engine** — the shell already owns this flag:

       run.cmd                                     -> nemotron  (the default; the way back)
       run.cmd --worker worker\\redux_live.py        -> Redux     (this file)

   `--worker` is `app/webview/sotto_webview.py`'s own documented option
   (`sotto_webview.py:6686`, default `DEFAULT_WORKER_PATH`), so turning Redux on
   and off is one argument, and **no file outside `worker/redux_live.py` has to
   change**.  A double-click on `run.cmd` is the OFF position.

2. **WHICH Redux export** — `--engine onnx|ternary`, or `SOTTO_LIVE_ENGINE`:

       --engine onnx      (DEFAULT) the ONNX int4 export, onnxruntime + numpy only
       --engine ternary   the canonical ternary checkpoint through Photon/kestrel

   WHY THE DEFAULT IS `onnx`, AND IT IS A MEASUREMENT, NOT A PREFERENCE.
   `_main/redux-engine-cost-probe.py` measured all three engines on the same
   15 s clip (`_main/pt-br-sample.wav`), each in a FRESH process, with the text
   compared byte-for-byte against the parity oracle `_main/redux-ptbr.txt`:

       engine            peak RSS    load    15 s in    RTF     text
       ternary (cpu)     3855.8 MB   7.8 s    3.94 s    3.81x   = oracle
       ternary (cuda)    1860.3 MB   4.9 s    2.26 s    6.64x   = oracle
       onnx int4 (cpu)    615.3 MB   1.1 s    1.80 s    8.33x   = oracle

   The ternary costs **6.3x the RAM** and is **2.2x slower** for byte-identical
   text, because `_main/redux-gemm8-probe.py` proved the packed int8 CPU kernel
   ("gemm8") is NOT in the published wheel: the payload's own answer is
   `ValueError: no 'avx2' matrix-multiply path on this machine` (and it is the
   same payload in the wheel PyPI publishes for this platform).  So the ternary
   always falls to the documented `dense` form -- 193/193 layers dequantized at
   load.  What that buys the owner is not asserted here, it is measured: 3.9 GB
   RESIDENT for live captions, on a box that was already 59.1% busy when the
   live ONNX arm ran (`_main/redux-live-latency-onnx-v2.out`).  `--engine
   ternary` is kept because it is the canonical checkpoint and the owner tests
   and decides -- but it is NOT the default, and the receipt states the cost.

   Both exports ARE `moondream/parakeet-redux` (CC-BY-4.0, based on
   `nvidia/parakeet-tdt-0.6b-v3`): the same weights, two packagings, the same
   TDT decode.  The choice is cost, not text.

THE JSONL CONTRACT (confirmed against the two files that consume it, not guessed)
--------------------------------------------------------------------------------
`worker/sotto_worker.py` `_event()` and `app/panel/caption-formulation.js`
`ingest()/commit()` agree on exactly this, and the panel's rule is why the shape
below is what it is:

    {"type":"caption","text":"<WHOLE line so far>","start":<seg start s>,
     "end":<growing end s>,"final":false}          <- the LIVE box (replaces in place)
    {"type":"caption","text":"<the closed line>","start":<same start>,
     "end":<final end>,"final":true}               <- the line is CLOSED

* `start` is the LINE's start and **never moves inside a line**.  The panel
  identifies the in-progress row by `start`; `caption-formulation.js:534` reads
  `start < lastAudioEnd` as "this fragment re-covers audio already shown" and
  REWRITES the one `.caption--provisional` row.  A `start` that moved every step
  would read as a NEW fragment and the box would duplicate the line instead of
  replacing it -- which is the failure the brief names.
* `text` is CUMULATIVE (the whole line), not a delta.
* `final:true` is the ONLY text the transcript may take
  (`panel.js recordHistory`: `if (route !== 'final') return`), so a line is
  closed exactly once, with `final:true`, and the next line gets a NEW `start`.
* **A line is closed before its text reaches the panel's own cap** (90 chars,
  `SENTENCE_MAX_CHARS`).  Why it matters: `panel.js addCaption` keys the row by
  `meta.start` and REPLACES an existing row with that start.  If a line were
  allowed to exceed the panel's cap, the panel would commit a prefix and then
  commit the rest under the SAME `start`, replacing the prefix instead of
  appending it -- the first words would vanish from the box.  So the engine
  closes on `--max-line-chars` (default 88) as well as on silence and on the
  window cap.

WINDOW AND STEP: CHOSEN BY MEASUREMENT, NOT BY TASTE
----------------------------------------------------
The engine decodes the OPEN SEGMENT, from its start, every `--step-s`.  That is
what makes the hypothesis cumulative and its `start` stable.  The hard
constraint the brief names is:

    decode(window) < step        otherwise the backlog grows and the lag diverges

`--window-s` is therefore a HARD cap and not a wish: `_drain_pending(limit=...)`
refuses to feed the segmenter past it, so a pass that arrives late does not get a
bigger window to decode -- the audio it did not consume is put back at the FRONT
of the queue and `backlog_s()` reports how much is waiting.  A non-zero backlog
at exit is the honest shape of "this box could not keep up"; it is published in
`LIVE_STATS` and in the `done` line next to `max_window_s` (the largest window
actually decoded, which is how the cap is CHECKED from outside rather than
claimed).  It also REPORTS the cadence: `passes`, `mean_compute_s`,
`max_compute_s`, `effective_step_s` and a loud `WARN LIVE_STEP_OVERRUN` when a
pass takes longer than the step, because a silently-adaptive cadence is exactly
the "queue grows without end" failure dressed up as health.

The shipped defaults were picked from `_main/redux-live-window-probe.py` (which
drives THIS file's own segmenter over the reference clip at several
(window, step) pairs, measuring decode time and the text against the oracle) and
re-measured, uncontended, by `_main/redux-live-arm1-recheck.py`; that probe's own
`VERDICT` ("NO (window, step) pair fits") is the CONTENDED bound and must be read
with the second table, because a single 5 s window costs 1.32 s here and 10.77 s
there.  Numbers for `--window-s 5.0 --step-s 2.0` are in the comment on
`DEFAULT_STEP_S` below.

ATTRIBUTION
-----------
Model ``moondream/parakeet-redux`` (CC-BY-4.0), a ternary re-quantisation of
``nvidia/parakeet-tdt-0.6b-v3`` by NVIDIA.  Ternary runtime: Photon / kestrel
(moondream).  ONNX export: ``eschmidbauer/parakeet-redux-onnx`` (CC-BY-4.0).

Usage
-----
    py worker/redux_live.py --help
    py worker/redux_live.py                          # live loopback, ONNX engine
    py worker/redux_live.py --engine ternary         # the canonical checkpoint
    py worker/redux_live.py --wav FILE --max-seconds 30   # no device opened
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
import time
from collections import deque
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

#: The ONNX int4 export -- the DEFAULT, measured at 615 MB peak RSS.
DEFAULT_ONNX_DIR = os.path.join(HERE, "models", "parakeet-redux-onnx-int4")
#: The canonical ternary checkpoint -- measured at 3856 MB peak RSS on CPU.
DEFAULT_TERNARY_DIR = os.path.join(HERE, "models", "parakeet-redux-ternary")
#: The ONNX export's OWN reference implementation (the TDT loop, parity-proven).
#: It is REUSED, not rewritten: a second decode loop is a second thing to get wrong.
ONNX_REFERENCE_DIR = os.path.join(HERE, "models", "parakeet-redux-reference")

ENGINES = ("onnx", "ternary")
DEFAULT_ENGINE = "onnx"
ENGINE_ENV = "SOTTO_LIVE_ENGINE"

PRODUCER = "redux"

#: How much audio one line may cover before it is force-closed. It is the DECODE
#: window: the longest stretch the model sees in one pass, so it also bounds the
#: per-pass cost. It is a HARD cap -- `_drain_pending(limit=...)` refuses to feed
#: past it, so a late pass queues audio instead of decoding an oversize window.
#: See the module docstring for how this number was chosen.
DEFAULT_WINDOW_S = 5.0
#: How often the open segment is re-decoded. Must EXCEED the per-pass cost or the
#: lag diverges. MEASURED 2026-10-08 on `_main/pt-br-sample.wav`, uncontended,
#: `--threads 2`: a 5 s window costs **1.32-1.36 s wall** (2.67 CPU-s, wall/cpu
#: 0.50, i.e. two threads busy). 1.0 s does NOT fit it -- the first smoke run
#: reported `overruns=5/5` for exactly that reason -- so the default is 2.0 s,
#: which leaves ~0.65 s of headroom on a contended box.
DEFAULT_STEP_S = 2.0
#: Trailing silence that closes a line. The panel's own audio-gap rule is 8 s
#: (`caption-formulation.js SENTENCE_GAP_S`); 0.7 s is the SPEECH pause, which is
#: a different boundary and the one that makes captions read like sentences.
DEFAULT_GAP_S = 0.7
#: Below this, a segment is not worth a decode pass.
DEFAULT_MIN_WINDOW_S = 1.2
#: The panel commits and re-keys a row at 90 chars (`SENTENCE_MAX_CHARS`); close
#: BEFORE that so the panel's cap never fires (see the module docstring).
DEFAULT_MAX_LINE_CHARS = 88

# ── the energy VAD that places the line boundaries ────────────────────────────
#: 20 ms at 16 kHz.
VAD_FRAME = 320
#: An absolute RMS floor, so digital silence is never "speech".
VAD_ABS_FLOOR = 0.0015
#: How far above the tracked noise floor a frame must be to count as speech.
VAD_RATIO = 3.0


def _utf8_streams() -> None:
    """Pin stdout/stderr to UTF-8, whatever the console code page is.

    Same convention as ``sotto_worker.py``/``redux_batch.py``: a caption's text is
    UTF-8 JSON, so a redirect to a file must not silently re-encode it into the
    host locale -- on this pt-BR box that writes ``á`` as ``0xE1`` and the line
    stops being valid UTF-8.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except (ValueError, OSError):
                pass


def emit(**payload) -> None:
    """One JSON object, one line, flushed. The whole inter-process contract."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def err(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


# ── RSS, read from the OS (never estimated) ───────────────────────────────────
def _pmc():
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    c = PMC()
    c.cb = ctypes.sizeof(PMC)
    psapi = ctypes.WinDLL("psapi")
    k32 = ctypes.WinDLL("kernel32")
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    ok = psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return ok, c


def rss_mb() -> float:
    ok, c = _pmc()
    return c.WorkingSetSize / (1024.0 * 1024.0) if ok else -1.0


def peak_rss_mb() -> float:
    ok, c = _pmc()
    return c.PeakWorkingSetSize / (1024.0 * 1024.0) if ok else -1.0


# ── the reused sibling code, named and hashed so the reuse is auditable ───────
def _sibling(name: str):
    """Import ``worker/<name>.py`` and report WHICH revision was imported.

    ``sotto_worker.py`` is edited by other lanes while this lane runs, so "the same
    tap as the worker" is only a true statement about a NAMED revision. The size
    and sha256 of the file actually imported are printed once, at startup, and
    travel in the run's ``done`` line -- a citation with a revision, per the house
    rule, instead of a line number that goes stale.
    """
    import hashlib
    import importlib

    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    module = importlib.import_module(name)
    path = getattr(module, "__file__", None)
    revision = {"module": name, "path": path}
    if path and os.path.isfile(path):
        with open(path, "rb") as fh:
            blob = fh.read()
        revision["bytes"] = len(blob)
        revision["sha256"] = hashlib.sha256(blob).hexdigest()
    return module, revision


# ── backends ──────────────────────────────────────────────────────────────────
class OnnxBackend:
    """The ONNX int4 export, through its OWN reference TDT loop (reused).

    ``worker/models/parakeet-redux-reference/transcribe.py`` is the export's
    published reference implementation -- the mel front end, the greedy
    token-and-duration walk, the word timing and the VAD segmentation. It is
    imported rather than reimplemented: it is the thing the parity oracle was
    produced with, so reusing it is what keeps this engine's text comparable to
    ``_main/redux-ptbr.txt``.
    """

    name = "onnx-int4"
    producer = PRODUCER

    def __init__(self, model_dir: str, threads: int = 0):
        if ONNX_REFERENCE_DIR not in sys.path:
            sys.path.insert(0, ONNX_REFERENCE_DIR)
        import transcribe as reference

        # The reference implementation takes a Path and divides it
        # (`model_dir / "config.json"`); handing it the CLI's str is a TypeError,
        # measured. Convert once, here.
        model_path = Path(model_dir)
        if not (model_path / "encoder-model.onnx").is_file():
            raise SystemExit(
                f"redux_live: no ONNX export in {model_path}\n"
                f"  fetch it (measured: 12.4 s on this box, 445 MB):\n"
                f"    hf download eschmidbauer/parakeet-redux-onnx --local-dir {model_path}"
            )
        self._ref = reference
        self._model = reference.OnnxParakeet(model_path,
                                             threads=(None if threads == 0 else int(threads)))
        self.model_dir = str(model_path)
        self.threads = threads

    def transcribe(self, pcm):
        result = self._model.transcribe(pcm, "segment")
        return str(result.get("text") or "").strip(), list(result.get("segments") or ())


class TernaryBackend:
    """The canonical ternary checkpoint, through Photon/kestrel (the vendor runtime).

    ``worker/redux_batch.py`` already owns this path -- its loader, its
    ``resident_form`` patch for the ``dense`` fallback, and its decode. This class
    calls the vendor runtime's ``transcribe`` with an IN-MEMORY waveform
    (``{"audio": ndarray, "sample_rate": 16000}``, which ``AudioChunks`` accepts --
    ``kestrel/models/asr/audio.py:13``), so no WAV is written per pass.
    """

    name = "ternary"
    producer = PRODUCER

    def __init__(self, model_dir: str, threads: int = 0, device: str = "cpu"):
        import numpy as np

        import redux_batch

        self._np = np
        self._batch = redux_batch
        # redux_batch.load_runtime does `model_dir / "config.json"` and is typed
        # `model_dir: Path`; handing it the CLI's str is a TypeError ("unsupported
        # operand type(s) for /: 'str' and 'str'", measured 2026-10-08 on the
        # --engine ternary arm). Convert once, here -- the same cure OnnxBackend
        # needed. Do NOT edit redux_batch.py for this: it is another lane's file.
        model_path = Path(model_dir)
        self.model_dir = str(model_path)
        self.device = device
        self._runtime = redux_batch.load_runtime(model_path, device=device)
        self._threads = threads
        if device == "cpu":
            import torch

            if threads:
                torch.set_num_threads(int(threads))

    def transcribe(self, pcm):
        np = self._np
        array = np.ascontiguousarray(pcm, dtype=np.float32)
        if array.size < 320:
            return "", []
        result = self._runtime.forward(
            "transcribe",
            [{"audio": array, "sample_rate": 16000, "timestamps": "segment"}],
        )[0]
        if isinstance(result, BaseException):
            raise result
        segments = []
        for segment in result.get("segments") or ():
            segments.append({
                "text": str(segment.get("text") or "").strip(),
                "start": float(segment.get("start") or 0.0),
                "end": float(segment.get("end") or 0.0),
            })
        return str(result.get("text") or "").strip(), segments


def load_backend(engine: str, onnx_dir: str, ternary_dir: str, threads: int, device: str):
    started = time.perf_counter()
    if engine == "onnx":
        backend = OnnxBackend(onnx_dir, threads=threads)
    else:
        backend = TernaryBackend(ternary_dir, threads=threads, device=device)
    backend.load_s = round(time.perf_counter() - started, 2)
    return backend


# ── the segmenter: pure logic, no device and no threads ───────────────────────
class EnergyVad:
    """A cheap, ADAPTIVE energy gate, used only to place LINE BOUNDARIES.

    It is deliberately not a speech/music classifier: its single job is to answer
    "has the audio gone quiet for long enough that this line is over", and to keep
    a very quiet source from being called silence. The threshold is
    ``max(absolute floor, tracked noise floor * ratio)``, with the noise floor
    falling fast and rising very slowly -- so a pause is recognised immediately
    and a long loud passage does not raise the threshold enough to swallow the
    next quiet word.
    """

    def __init__(self, abs_floor=VAD_ABS_FLOOR, ratio=VAD_RATIO, frame=VAD_FRAME):
        self.abs_floor = float(abs_floor)
        self.ratio = float(ratio)
        self.frame = int(frame)
        self.noise = None
        self.frames = 0
        self.voiced_frames = 0

    def scan(self, pcm):
        """Return ``(voiced_flags, n_frames)`` for the frames wholly inside pcm."""
        import numpy as np

        count = int(pcm.size // self.frame)
        flags = []
        for index in range(count):
            chunk = pcm[index * self.frame:(index + 1) * self.frame]
            rms = float(np.sqrt(np.mean(np.square(chunk, dtype=np.float64)) + 1e-20))
            if self.noise is None:
                self.noise = rms
            elif rms < self.noise:
                self.noise = 0.7 * self.noise + 0.3 * rms
            else:
                self.noise = 0.9995 * self.noise + 0.0005 * rms
            voiced = rms > max(self.abs_floor, self.noise * self.ratio)
            flags.append(voiced)
            self.frames += 1
            self.voiced_frames += 1 if voiced else 0
        return flags, count


class LiveSegmenter:
    """Turns a stream of 16 kHz PCM into the panel's cumulative-line contract.

    PURE: no device, no thread, no clock. ``feed()`` accepts audio,
    ``pass_events()`` decides what the panel should see now, and both are driven
    by the caller. That is what lets ``_main/redux-live-window-probe.py`` run this
    EXACT logic over a file at several (window, step) pairs -- the numbers behind
    the shipped defaults come from the shipped code, not from a model of it.
    """

    def __init__(self, window_s=DEFAULT_WINDOW_S, gap_s=DEFAULT_GAP_S,
                 min_window_s=DEFAULT_MIN_WINDOW_S, max_line_chars=DEFAULT_MAX_LINE_CHARS,
                 vad=True, gain=None):
        import numpy as np

        self._np = np
        self.window_s = float(window_s)
        self.gap_s = float(gap_s)
        self.min_window_s = float(min_window_s)
        self.max_line_chars = int(max_line_chars)
        self.use_vad = bool(vad)
        self.vad = EnergyVad() if self.use_vad else None
        self.gain = gain

        self.seg = []              # list of np arrays, the OPEN line's audio
        self.seg_samples = 0
        self.seg_start = None      # absolute audio second where the open line began
        self.audio_s = 0.0         # absolute audio second at the end of what was fed
        self.last_voiced_s = 0.0   # absolute second of the last voiced frame's end
        self.tail = self._np.zeros(0, dtype=self._np.float32)  # < one VAD frame
        self.last_text = None
        self.closed = []           # lines closed since the last drain (final events)
        self.emitted = []          # the partial events this pass produced
        self.lines = 0
        self.passes = 0

    # -- audio in ------------------------------------------------------------
    def feed(self, pcm):
        np = self._np
        block = np.ascontiguousarray(pcm, dtype=np.float32)
        if block.size == 0:
            return
        if self.gain is not None:
            block = self.gain.process(block, True)
        self.audio_s += block.size / 16000.0
        if self.seg_start is None:
            self.seg_start = self.audio_s - block.size / 16000.0
        self.seg.append(block)
        self.seg_samples += int(block.size)
        if self.use_vad:
            # A VAD frame boundary does not move, so the sub-frame tail is carried
            # across feeds instead of being rounded away at every 100 ms block.
            joined = np.concatenate([self.tail, block]) if self.tail.size else block
            flags, count = self.vad.scan(joined)
            consumed = count * self.vad.frame
            self.tail = joined[consumed:]
            voiced_end = self.audio_s - (joined.size - consumed) / 16000.0
            for index in range(count - 1, -1, -1):
                if flags[index]:
                    self.last_voiced_s = voiced_end - (count - 1 - index) * self.vad.frame / 16000.0
                    break

    # -- decisions -----------------------------------------------------------
    @property
    def open_seconds(self):
        return self.seg_samples / 16000.0

    def trailing_silence_s(self):
        if self.seg_start is None:
            return 0.0
        return max(0.0, self.audio_s - max(self.last_voiced_s, self.seg_start))

    def should_decode(self):
        if self.seg_start is None or self.seg_samples == 0:
            return False
        if self.open_seconds < self.min_window_s:
            return False
        return True

    def should_close(self, text):
        """The three boundaries, in the order they are checked.

        The window test carries a tiny epsilon because `_drain_pending` fills to
        the cap EXACTLY: with ragged blocks (resampling, a rate that is not 16 kHz)
        the fill lands a sample or two short, and without the epsilon the line
        would stay open and burn a whole extra pass to close.
        """
        if self.seg_start is None:
            return False
        if text and len(text) >= self.max_line_chars:
            return True
        if self.open_seconds >= self.window_s - 1e-6:
            return True
        if self.use_vad and self.trailing_silence_s() >= self.gap_s:
            return True
        return False

    def _event(self, text, final):
        return {
            "type": "caption",
            "text": text,
            "start": round(float(self.seg_start), 2),
            "end": round(float(self.audio_s), 2),
            "final": bool(final),
            "producer": PRODUCER,
        }

    def close(self, text):
        """Publish the closed line (final:true) and start a fresh one."""
        if self.seg_start is not None and text:
            self.closed.append(self._event(text, True))
            self.lines += 1
        self.seg = []
        self.seg_samples = 0
        self.seg_start = None
        self.tail = self._np.zeros(0, dtype=self._np.float32)
        self.last_text = None

    def drain(self):
        """The events accumulated since the last call: partials then finals."""
        out = list(self.emitted) + list(self.closed)
        self.emitted = []
        self.closed = []
        return out


# ── the tap: the WORKER's own ladder, reused (not copied) ─────────────────────
#: ``0x8889000A`` = AUDCLNT_E_DEVICE_IN_USE. Same predicate, same source as the
#: worker's (`sotto_worker.py:4051`), and the same conclusion: it is usually the
#: process's OWN PREDECESSOR still releasing the endpoint, so the busy endpoint is
#: WAITED FOR, never rotated away from.
DEVICE_IN_USE_RETRIES = 3
DEVICE_IN_USE_WAIT_S = 1.5


def _is_device_in_use(text: str) -> bool:
    return "8889000a" in str(text).lower()


def tap_candidates(worker, audio_cfg, wanted):
    """The worker's OWN candidate rule, including its file-tap override.

    ``worker.device_candidates`` does **not** read ``SOTTO_FILE_TAP``: the worker
    branches on that variable in its run loop, BEFORE the ladder
    (``sotto_worker.py:3374-3382``, 242 082 B revision). Calling the ladder
    directly would therefore open a REAL endpoint where the shipped worker opens
    none -- a deviation from "the same tap as the worker", and one that would
    collide with the endpoint the owner's worker holds. So the branch is
    reproduced here. OFF by default: with the variable unset this is exactly
    ``device_candidates``.

    Returns ``(candidates, missing_path)``; ``missing_path`` is not None only when
    the variable names audio that is not there, which the worker answers with
    exit 2 and a named error rather than by falling back to a device.
    """
    path = os.environ.get("SOTTO_FILE_TAP")
    if not path:
        return worker.device_candidates(audio_cfg, wanted), None
    if not os.path.exists(path):
        return [], path
    return [worker.file_tap_candidate(path)], None


def open_tap(worker, audio_cfg, wanted, on_block, block_ms, stop, log):
    """Open the first candidate tap that WORKS, with the worker's own rules.

    Returns ``(tap, device, ledger, denials, fatal_rc)``. The ladder, the tap
    factory and the busy-endpoint policy all come from ``worker/sotto_worker.py``
    by import, so "the same tap as the worker" is true by construction rather than
    by a copy that can drift -- and the revision imported is reported by the
    caller. ``fatal_rc`` is set only for a source that is misconfigured (a
    ``SOTTO_FILE_TAP`` pointing at nothing), which must not be reported as
    "every candidate failed".

    A denial is recorded with its CAUSE. "every candidate failed" and "every
    candidate failed BECAUSE ANOTHER PROGRAM HOLDS THE ENDPOINT" are different
    facts about the owner's machine: the second one's fix is in VoiceMeeter, not
    here, and the run has to say which one it hit.
    """
    candidates, missing = tap_candidates(worker, audio_cfg, wanted)
    ledger = []
    denials = []
    if missing is not None:
        emit(type="status", state="error", stage="file-tap",
             detail=f"SOTTO_FILE_TAP set but no audio at {missing}")
        return None, None, ledger, [f"SOTTO_FILE_TAP: no audio at {missing}"], 2
    for attempt_no, dev in enumerate(candidates):
        tap = None
        open_error = None
        for retry in range(DEVICE_IN_USE_RETRIES):
            if stop.is_set():
                return None, None, ledger, denials, None
            try:
                tap = worker.LoopbackTap(dev, on_block, block_ms=block_ms)
                tap.stream.start()
                open_error = None
                break
            except Exception as exc:
                open_error = exc
                detail = f"{type(exc).__name__}: {exc}"
                emit(type="status", state="error", stage="open-stream",
                     device=dev["name"], api=dev.get("api"), detail=detail, retry=retry)
                if tap is not None:
                    try:
                        tap.stream.stop()
                        tap.stream.close()
                    except Exception:
                        pass
                    tap = None
                if not _is_device_in_use(detail) or retry >= DEVICE_IN_USE_RETRIES - 1:
                    break
                log(f"OPEN_RETRY_RETRY device={dev['name']!r} reason=device-in-use "
                    f"retry={retry + 1} in_ms={int(DEVICE_IN_USE_WAIT_S * 1000)} "
                    f"(the previous worker may still be releasing it)")
                stop.wait(DEVICE_IN_USE_WAIT_S)
        if open_error is not None:
            denials.append(f"{dev['name']} [{dev.get('api')}]: "
                           f"{type(open_error).__name__}: {open_error}")
            if attempt_no + 1 < len(candidates):
                emit(type="status", state="device-rotated",
                     reason="open-denied" if _is_device_in_use(str(open_error)) else "open-failed",
                     to=candidates[attempt_no + 1]["name"],
                     attempt=attempt_no + 1, of=len(candidates))
            continue
        ledger.append({"name": dev["name"], "api": dev.get("api"),
                       "rung": dev.get("rung"), "rate": getattr(tap, "rate", None)})
        return tap, dev, ledger, denials, None
    return None, None, ledger, denials, None


# ── the run loop ──────────────────────────────────────────────────────────────
class LiveRun:
    """One live run: a tap (or a file), a decode cadence, and the JSONL contract."""

    def __init__(self, backend, args, worker, revision):
        import numpy as np

        self.np = np
        self.backend = backend
        self.args = args
        self.worker = worker
        self.revision = revision
        self.stop = threading.Event()
        self.pending = deque()
        self.lock = threading.Lock()
        self.seg = LiveSegmenter(
            window_s=args.window_s, gap_s=args.gap_s,
            min_window_s=args.min_window_s, max_line_chars=args.max_line_chars,
            vad=not args.no_vad,
            gain=(None if args.no_agc else worker.AutoGain()),
        )
        self.rate = worker.TARGET_SR
        self.peak = 0.0
        self.blocks = 0
        self.samples = 0
        self.captions = 0
        self.finals = 0
        self.passes = 0
        self.compute_s = []
        self.overruns = 0
        #: The largest window actually decoded. `--window-s` is a hard cap, so this
        #: must never exceed it by more than one audio block; the done payload
        #: publishes it so the cap is a MEASURED property, not a claimed one.
        self.max_window_s = 0.0
        self.tap = None
        self.device = None
        self.ledger = []
        self.denials = []
        self.started = time.monotonic()

    # -- the tap callback: enqueue only, never decode here -------------------
    def on_block(self, block, time_info=None):
        with self.lock:
            self.pending.append(block)
            self.blocks += 1
            self.samples += int(getattr(block, "size", 0))
            if block.size:
                self.peak = max(self.peak, float(abs(block).max()))

    def _drain_pending(self, limit=None):
        """Feed pending audio to the segmenter, never past `limit` seconds.

        `limit` IS the window cap, and it is the fix for a measured defect: this
        method used to feed EVERYTHING that had queued, so a pass that ran late
        (the decode before it was slow) pushed `open_seconds` from ~2 s straight to
        10.1 s in one call -- `should_close` was consulted only AFTERWARDS, so the
        engine happily decoded and closed a window twice its configured size.
        MEASURED 2026-10-08, `--window-s 5.0`: `WARN LIVE_STEP_OVERRUN ... window_s=10.10`,
        `max_compute_s=16.61`. The window is now a HARD cap: the excess stays in
        `self.pending` and is picked up by the next pass, so what accumulates when
        the decode cannot keep up is a visible BACKLOG (`backlog_s`) instead of an
        ever-growing window -- the difference between "the caption is late" and
        "the caption is late AND every pass costs more than the last".
        """
        with self.lock:
            blocks, self.pending = list(self.pending), deque()
        if not blocks:
            return 0
        np = self.np
        joined = np.concatenate(blocks) if len(blocks) > 1 else blocks[0]
        if self.rate != self.worker.TARGET_SR:
            joined = self.worker.resample_to_16k(joined, self.rate)
        if limit:
            room = int(float(limit) * self.worker.TARGET_SR) - self.seg.seg_samples
            if room <= 0:
                with self.lock:
                    self.pending.extendleft(reversed(blocks))
                return 0
            if joined.size > room:
                # The remainder goes back to the FRONT, in one piece, so block
                # order survives; it is already at TARGET_SR.
                with self.lock:
                    self.pending.appendleft(joined[room:])
                joined = joined[:room]
        self.seg.feed(joined)
        return int(joined.size)

    def backlog_s(self):
        """Audio received but not yet in the open line -- the honest queue depth."""
        with self.lock:
            queued = sum(int(getattr(b, "size", 0)) for b in self.pending)
        if self.rate != self.worker.TARGET_SR:
            queued = int(queued * self.worker.TARGET_SR / max(1, self.rate))
        return queued / float(self.worker.TARGET_SR)

    # -- the decode thread ---------------------------------------------------
    def decode_loop(self):
        step = float(self.args.step_s)
        next_step = time.monotonic() + step
        while not self.stop.is_set():
            now = time.monotonic()
            if now < next_step:
                self.stop.wait(min(next_step - now, 0.05))
                continue
            # NOTE: `next_step = now + step`, NOT `+= step`. The engine always
            # decodes the CURRENT segment state and never a queued item, so a pass
            # slower than the step COALESCES the passes instead of growing a
            # backlog. That is the whole answer to "the queue grows without end",
            # and the overrun is reported rather than hidden.
            next_step = now + step
            self._pass()

    def _pass(self):
        # `limit` = the window cap: one pass feeds at most ONE window, so the
        # window cannot grow past `--window-s` no matter how late this pass ran.
        added = self._drain_pending(limit=self.seg.window_s)
        if not added or not self.seg.should_decode():
            return
        pcm = self.np.concatenate(self.seg.seg) if len(self.seg.seg) > 1 else self.seg.seg[0]
        self.max_window_s = max(self.max_window_s, len(pcm) / float(self.worker.TARGET_SR))
        started = time.perf_counter()
        try:
            text, _segments = self.backend.transcribe(pcm)
        except Exception as exc:
            emit(type="status", state="error", stage="decode",
                 detail=f"{type(exc).__name__}: {exc}")
            err(f"decode failed ({type(exc).__name__}: {exc}); the line is left open")
            return
        elapsed = time.perf_counter() - started
        self.passes += 1
        self.compute_s.append(elapsed)
        if elapsed > float(self.args.step_s):
            self.overruns += 1
            err(f"WARN LIVE_STEP_OVERRUN pass={self.passes} compute_s={elapsed:.2f} "
                f"step_s={self.args.step_s} window_s={self.seg.open_seconds:.2f} "
                f"backlog_s={self.backlog_s():.2f} -- this pass cost more than the "
                f"step, so the next partial is late; the window stays capped and "
                f"the excess audio queues (see backlog_s)")
        text = (text or "").strip()
        if text and text != self.seg.last_text:
            self.seg.last_text = text
            self.seg.emitted.append(self.seg._event(text, False))
        if self.seg.should_close(text):
            self.seg.close(text)
        for event in self.seg.drain():
            self.captions += 1
            if event.get("final"):
                self.finals += 1
            emit(model=self.backend.name, **event)

    def stats_line(self):
        computes = self.compute_s
        return (
            f"LIVE_STATS passes={self.passes} captions={self.captions} "
            f"finals={self.finals} blocks={self.blocks} audio_s={self.seg.audio_s:.1f} "
            f"backlog_s={self.backlog_s():.2f} peak={self.peak:.6f} overruns={self.overruns} "
            f"mean_compute_s={sum(computes) / len(computes):.2f} "
            f"max_compute_s={max(computes):.2f}" if computes else
            f"LIVE_STATS passes=0 captions=0 blocks={self.blocks} "
            f"audio_s={self.seg.audio_s:.1f} backlog_s={self.backlog_s():.2f} "
            f"peak={self.peak:.6f} overruns=0"
        )

    def flush(self):
        """End of stream: publish the open line as a CLOSED one.

        NO limit here -- this is the end, so everything queued is decoded. The
        tail is flushed in window-sized pieces so the last line is not a 30 s
        window, which would cost far more than the rest of the run together.
        """
        for _ in range(64):
            added = self._drain_pending(limit=self.seg.window_s)
            if not added:
                break
            if not self.seg.should_decode():
                continue
            pcm = self.np.concatenate(self.seg.seg) if len(self.seg.seg) > 1 else self.seg.seg[0]
            try:
                text, _ = self.backend.transcribe(pcm)
            except Exception as exc:
                err(f"final decode failed ({type(exc).__name__}: {exc})")
                text = ""
            self.seg.close((text or "").strip() or self.seg.last_text or "")
            for event in self.seg.drain():
                self.captions += 1
                if event.get("final"):
                    self.finals += 1
                emit(model=self.backend.name, **event)
            if self.backlog_s() <= 0:
                break
        if self.seg.last_text:
            self.seg.close(self.seg.last_text)
        for event in self.seg.drain():
            self.captions += 1
            if event.get("final"):
                self.finals += 1
            emit(model=self.backend.name, **event)


# ── the two sources ───────────────────────────────────────────────────────────
def run_device(run: LiveRun, args) -> int:
    worker = run.worker
    audio_cfg = args.audio_cfg
    wanted = args.device or os.environ.get("SOTTO_AUDIO_DEVICE") or None
    tap, dev, ledger, denials, fatal_rc = open_tap(
        worker, audio_cfg, wanted, run.on_block, args.block_ms, run.stop, err)
    run.ledger, run.denials = ledger, denials
    if fatal_rc is not None:
        return fatal_rc
    if tap is None:
        state = "device-exhausted"
        emit(type="status", state=state, tried=[d for d in denials],
             detail="no candidate tap opened; the endpoint may be held by another "
                    "process, or the routing may carry nothing")
        for denial in denials:
            err(f"candidate denied: {denial}")
        return 3
    run.tap, run.device = tap, dev
    run.rate = getattr(tap, "rate", worker.TARGET_SR)
    emit(type="status", state="capture-started", device=dev["name"],
         api=dev.get("api"), rung=dev.get("rung"), rate=run.rate,
         block=getattr(tap, "block", None))
    err(f"tap open: {dev['name']} [{dev.get('api')}] rung={dev.get('rung')} "
        f"rate={run.rate} native={run.rate != worker.TARGET_SR}")

    thread = threading.Thread(target=run.decode_loop, name="redux-live-decode", daemon=True)
    thread.start()

    next_stats = time.monotonic() + args.stats_interval
    window_end = time.monotonic() + worker.TAP_WINDOW_S
    silent = False
    try:
        while not run.stop.is_set():
            now = time.monotonic()
            if args.max_seconds and (now - run.started) >= args.max_seconds:
                break
            if now >= next_stats:
                err(run.stats_line())
                next_stats = now + args.stats_interval
            if now >= window_end and run.blocks == 0:
                # The worker's own silent-device rule (sotto_worker.py): a tap that
                # opens and delivers NOTHING for a full window is a routing fact
                # about the machine, and it must be said loudly rather than exiting 0.
                silent = True
                break
            run.stop.wait(0.1)
    except KeyboardInterrupt:
        err("interrupted")
    finally:
        run.stop.set()
        thread.join(timeout=30)
        run.flush()
        try:
            tap.stream.stop()
            tap.stream.close()
        except Exception as exc:
            err(f"close_tap failed ({type(exc).__name__}: {exc})")
    if silent or (run.peak < worker.TAP_PEAK_FLOOR and run.captions == 0):
        emit(type="status", state="silent-device", device=run.device["name"],
             peak=run.peak, blocks=run.blocks,
             detail="the tap opened and delivered no captions above the peak floor")
        return 3
    return 0


def run_wav(run: LiveRun, args) -> int:
    """A FILE as the source, at a real-time pace, opening NO device.

    This is the measurement path AND the honest fallback the house rules ask for:
    the owner's worker holds the loopback endpoint while his app is up, so a probe
    that needs the same endpoint cannot run. `worker.FileTap` is the worker's own
    file-fed tap, reused, so the timing this measures is the timing a device would
    produce (one block per `block_ms` on a wall clock).
    """
    worker = run.worker
    tap = worker.FileTap(args.wav, run.on_block, block_ms=args.block_ms)
    # FileTap owns a pump THREAD and does nothing until it is started -- measured:
    # without this call the run reported blocks=0 for its whole length and exited
    # with verdict `no-captions`, i.e. a silent, green-looking failure.
    tap.stream.start()
    run.tap, run.device = tap, {"name": f"file:{os.path.basename(args.wav)}"}
    run.rate = worker.TARGET_SR
    emit(type="status", state="capture-started", device=run.device["name"],
         api=None, rung="file", rate=run.rate, block=tap.block)
    err(f"file tap: {args.wav} ({tap.pcm.size / worker.TARGET_SR:.1f} s), "
        f"no audio device opened")
    thread = threading.Thread(target=run.decode_loop, name="redux-live-decode", daemon=True)
    thread.start()
    next_stats = time.monotonic() + args.stats_interval
    try:
        while not run.stop.is_set():
            now = time.monotonic()
            if args.max_seconds and (now - run.started) >= args.max_seconds:
                break
            if now >= next_stats:
                err(run.stats_line())
                next_stats = now + args.stats_interval
            run.stop.wait(0.1)
    except KeyboardInterrupt:
        err("interrupted")
    finally:
        run.stop.set()
        thread.join(timeout=60)
        run.flush()
        try:
            tap.stream.stop()
            tap.stream.close()
        except Exception:
            pass
    return 0


# ── config ────────────────────────────────────────────────────────────────────
def load_config(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        err(f"config {path} unreadable ({type(exc).__name__}: {exc}); using defaults")
        return {}


def resolve_engine(args):
    """`--engine` > `SOTTO_LIVE_ENGINE` > the measured default. Never clamped silently."""
    value = args.engine or os.environ.get(ENGINE_ENV) or DEFAULT_ENGINE
    value = str(value).strip().lower()
    if value not in ENGINES:
        err(f"engine {value!r} is not one of {ENGINES}; refusing (exit 2)")
        raise SystemExit(2)
    return value


def main(argv=None) -> int:
    _utf8_streams()
    parser = argparse.ArgumentParser(
        prog="redux_live",
        description="Sotto LIVE transcriber: Parakeet Redux (TDT) as the live engine, "
                    "speaking the SAME JSONL contract as worker/sotto_worker.py so the "
                    "panel is not touched.",
        epilog=(
            "THE SWITCH, both directions:\n"
            "  OFF (nemotron, the default)   run.cmd\n"
            "  ON  (Redux, this file)        run.cmd --worker worker\\redux_live.py\n"
            "  which Redux export            --engine onnx (default, 615 MB) | ternary (3856 MB)\n"
            "  ...or the environment         SOTTO_LIVE_ENGINE=ternary\n"
            "\n"
            "The default is `onnx` because it was MEASURED: the ternary costs 6.3x the\n"
            "RAM and is 2.2x slower for byte-identical text, since the packed int8 CPU\n"
            "kernel is absent from the published kestrel wheel. See\n"
            "_main/receipt-redux-live.md and _main/redux-gemm8-probe.py.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--engine", choices=ENGINES, default=None,
                        help=f"which Redux export ({'/'.join(ENGINES)}); "
                             f"default from ${ENGINE_ENV} or {DEFAULT_ENGINE!r}")
    parser.add_argument("--window-s", type=float, default=DEFAULT_WINDOW_S,
                        help=f"longest audio one line may cover (default {DEFAULT_WINDOW_S})")
    parser.add_argument("--step-s", type=float, default=DEFAULT_STEP_S,
                        help=f"cadence of the cumulative decode passes (default {DEFAULT_STEP_S})")
    parser.add_argument("--gap-s", type=float, default=DEFAULT_GAP_S,
                        help=f"trailing silence that closes a line (default {DEFAULT_GAP_S})")
    parser.add_argument("--min-window-s", type=float, default=DEFAULT_MIN_WINDOW_S,
                        help=f"do not decode less than this (default {DEFAULT_MIN_WINDOW_S})")
    parser.add_argument("--max-line-chars", type=int, default=DEFAULT_MAX_LINE_CHARS,
                        help=f"close a line at this length (default {DEFAULT_MAX_LINE_CHARS}; "
                             f"the panel's own cap is 90)")
    parser.add_argument("--no-vad", action="store_true",
                        help="do not close on silence: fixed windows only (diagnostic arm)")
    parser.add_argument("--no-agc", action="store_true",
                        help="do not apply the worker's automatic gain (diagnostic arm; "
                             "the live device path uses it because a quiet source "
                             "transcribes to nothing without it)")
    parser.add_argument("--onnx-dir", default=DEFAULT_ONNX_DIR, help="ONNX int4 export")
    parser.add_argument("--ternary-dir", default=DEFAULT_TERNARY_DIR, help="ternary checkpoint")
    parser.add_argument("--device", default=None,
                        help="audio device to tap (default: the worker's own ladder)")
    parser.add_argument("--photon-device", default="cpu", choices=("cpu", "cuda", "mps"),
                        help="device for the TERNARY engine only (default cpu)")
    parser.add_argument("--threads", type=int, default=0,
                        help="decode threads; 0 = the runtime's own pool (default)")
    parser.add_argument("--config", default=os.path.join(HERE, "config.json"),
                        help="worker config.json, read for audio.block_ms/device")
    parser.add_argument("--block-ms", type=int, default=None,
                        help="tap block size in ms (default: config audio.block_ms, else 100)")
    parser.add_argument("--wav", default=None,
                        help="feed a WAV instead of opening a device (measurement path)")
    parser.add_argument("--max-seconds", type=float, default=0.0,
                        help="stop after this many wall seconds (0 = run until stopped)")
    parser.add_argument("--stats-interval", type=float, default=10.0,
                        help="seconds between LIVE_STATS lines on stderr")
    args = parser.parse_args(argv)

    engine = resolve_engine(args)
    cfg = load_config(args.config)
    audio_cfg = (cfg.get("audio") or {})
    args.audio_cfg = audio_cfg
    if args.block_ms is None:
        try:
            args.block_ms = int(audio_cfg.get("block_ms") or 100)
        except Exception:
            args.block_ms = 100

    worker, revision = _sibling("sotto_worker")
    err(f"redux_live: engine={engine} window_s={args.window_s} step_s={args.step_s} "
        f"gap_s={args.gap_s} max_line_chars={args.max_line_chars} "
        f"vad={not args.no_vad} agc={not args.no_agc} threads={args.threads}")
    err(f"redux_live: reused worker/sotto_worker.py revision bytes={revision.get('bytes')} "
        f"sha256={str(revision.get('sha256'))[:16]}...")

    emit(type="status", state="boot", engine=engine, producer=PRODUCER,
         window_s=args.window_s, step_s=args.step_s)
    emit(type="status", state="model-loading", engine=engine,
         model=os.path.basename(args.onnx_dir if engine == "onnx" else args.ternary_dir))
    try:
        backend = load_backend(engine, args.onnx_dir, args.ternary_dir,
                               args.threads, args.photon_device)
    except SystemExit as exc:
        emit(type="status", state="error", stage="model", detail=str(exc))
        raise
    except Exception as exc:
        emit(type="status", state="error", stage="model",
             detail=f"{type(exc).__name__}: {exc}")
        err(f"model load failed: {type(exc).__name__}: {exc}")
        return 1
    emit(type="status", state="model-loaded", engine=engine, model=backend.name,
         load_s=backend.load_s, rss_mb=round(rss_mb(), 1))
    err(f"redux_live: {backend.name} loaded in {backend.load_s:.2f} s, "
        f"rss={rss_mb():.1f} MB")

    run = LiveRun(backend, args, worker, revision)
    rc = run_wav(run, args) if args.wav else run_device(run, args)

    computes = run.compute_s
    verdict = "captions-emitted" if run.finals or run.captions else (
        "silent-device" if rc == 3 else "no-captions")
    emit(type="status", state="done", engine=engine, model=backend.name, verdict=verdict,
         exit=rc, captions=run.captions, finals=run.finals, lines=run.seg.lines,
         passes=run.passes, overruns=run.overruns,
         mean_compute_s=round(sum(computes) / len(computes), 3) if computes else None,
         max_compute_s=round(max(computes), 3) if computes else None,
         effective_step_s=round(max(computes) if computes else args.step_s, 3),
         window_s=args.window_s, step_s=args.step_s,
         max_window_s=round(run.max_window_s, 2), backlog_s=round(run.backlog_s(), 2),
         audio_s=round(run.seg.audio_s, 2), peak=round(run.peak, 6),
         blocks=run.blocks, device=(run.device or {}).get("name"),
         ledger=run.ledger, denials=run.denials,
         rss_mb=round(rss_mb(), 1), peak_rss_mb=round(peak_rss_mb(), 1),
         worker_revision=revision)
    err(run.stats_line())
    err(f"redux_live: done verdict={verdict} rc={rc} captions={run.captions} "
        f"finals={run.finals} peak_rss={peak_rss_mb():.1f} MB")
    return rc


if __name__ == "__main__":
    sys.exit(main())
