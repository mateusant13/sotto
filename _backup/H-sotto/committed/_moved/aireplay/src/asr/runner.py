"""The transcription loop -- one function, used by both the CLI and the parity harness.

Everything the receipt quotes is produced HERE, by the process that did the work: the RSS
comes from this process's own `psutil` poll plus the OS `peak_wset` (the instrument of
`_main/probe-onnx-asr.py:43-66`), the RTFx from the wall clock around the model call, and the
thread count from the session the engine actually built.

Steady-state RTFx is the product number: the first segment is EXCLUDED, because the first
call after load is atypical with an unstable sign (0.41-2.63x across 16 arms, sign not
stable, mechanism UNKNOWN -- docs/research/11-onnx-threads.md:46-49).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .constants import (
    DEFAULT_SEGMENT_MODE,
    FIXED_GRID_S,
    INTRA_OP_NUM_THREADS,
    INTER_OP_NUM_THREADS,
    MAX_SEGMENT_S,
    MODE_FIXED,
    MODEL_DIR,
    QUANTIZATION,
    RSS_POLL_INTERVAL_S,
    SAMPLE_RATE,
)
from .engine import OnnxAsrEngine, pin_thread_env
from .level import LevelEmitter
from .segment import segments_for_mode

__all__ = ["TranscribeConfig", "transcribe"]

MB = 1024.0 * 1024.0


@dataclass
class TranscribeConfig:
    wav: Path
    model_dir: Path = MODEL_DIR
    quantization: str = QUANTIZATION
    provider: str = "cpu"
    offset_s: float = 0.0
    max_s: float = 0.0
    segment_mode: str = DEFAULT_SEGMENT_MODE
    max_segment_s: float = MAX_SEGMENT_S
    fixed_chunk_s: float = FIXED_GRID_S
    intra_op_num_threads: int = INTRA_OP_NUM_THREADS
    inter_op_num_threads: int = INTER_OP_NUM_THREADS
    level: bool = True
    phases: bool = False
    verify_model: bool = True
    label: str = ""

    def __post_init__(self):
        self.wav = Path(self.wav)
        self.model_dir = Path(self.model_dir)
        if self.segment_mode == MODE_FIXED and self.max_s <= 0:
            # The fixed grid is a CONTROL. Running it over an unbounded file is almost
            # certainly a mistake, and a silent 3-hour control is a waste of the box.
            raise ValueError("segment-mode 'fixed' is a CONTROL: pass --max-s (a bounded slice)")
        if self.intra_op_num_threads <= 0:
            raise ValueError("intra_op_num_threads must be > 0; ORT's default (0) is forbidden")


class _RssSampler(threading.Thread):
    """1 Hz RSS + CPU poll, stamped with the audio clock AND the phase (load vs infer).

    Same instrument as `_main/probe-onnx-asr.py:43-66` plus the phase split lane 11 added
    (`probe-onnx-asr-threads.py:117-132`): the CPU% the thread pin is judged on is the
    INFERENCE phase's, because session creation is a one-off load cost, not the steady state
    the budget is about.
    """

    def __init__(self, every: float, clock: dict):
        super().__init__(daemon=True)
        self.every = every
        self.clock = clock
        self.points: list[list] = []
        # NOT `_stop`: threading.Thread owns a private `_stop()` method, and shadowing it
        # with an Event makes the interpreter's own teardown call an Event -> TypeError.
        self._stop_evt = threading.Event()
        self._proc = None

    def run(self) -> None:
        import psutil  # noqa: PLC0415

        self._proc = psutil.Process()
        self._proc.cpu_percent(None)
        t0 = time.perf_counter()
        while not self._stop_evt.is_set():
            try:
                mem = self._proc.memory_info()
                cpu = self._proc.cpu_percent(None)
            except Exception:  # noqa: BLE001 -- a lost sample is not a crash
                self._stop_evt.wait(self.every)
                continue
            self.points.append(
                [
                    round(time.perf_counter() - t0, 3),
                    round(self.clock.get("audio_s", 0.0), 3),
                    round(mem.rss / MB, 2),
                    round(cpu, 1),
                    self.clock.get("phase", "load"),
                ]
            )
            self._stop_evt.wait(self.every)

    def stop(self) -> None:
        self._stop_evt.set()
        self.join(timeout=5.0)

    def peak_rss(self) -> float:
        return max((p[2] for p in self.points), default=0.0)

    def cpu_stats(self, phase: str | None = None) -> tuple[float | None, float | None]:
        """(median, max) CPU% for a phase; the first sample of a phase is dropped when there
        are enough samples to afford it (the phase boundary sample spans two phases)."""
        pts = [p for p in self.points if phase is None or p[4] == phase]
        vals = sorted(p[3] for p in (pts[1:] if len(pts) > 2 else pts))
        if not vals:
            return None, None
        return vals[len(vals) // 2], vals[-1]


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[len(s) // 2]


def transcribe(cfg: TranscribeConfig, on_event: Callable[[dict], None] | None = None) -> dict:
    """Transcribe one wav slice. Returns the `done` event; `on_event` sees every event."""
    import psutil  # noqa: PLC0415

    from .audio import read_slice, wav_info

    def emit(ev: dict) -> None:
        if on_event is not None:
            on_event(ev)

    # 1. pin the measured knee BEFORE numpy / onnxruntime load their thread pools
    env = pin_thread_env(cfg.intra_op_num_threads)

    proc = psutil.Process()
    rss_start = proc.memory_info().rss / MB
    clock: dict = {"audio_s": 0.0, "phase": "load"}
    sampler = _RssSampler(RSS_POLL_INTERVAL_S, clock)
    sampler.start()

    # 2. load
    engine = OnnxAsrEngine(
        model_dir=cfg.model_dir,
        quantization=cfg.quantization,
        provider=cfg.provider,
        intra_op_num_threads=cfg.intra_op_num_threads,
        inter_op_num_threads=cfg.inter_op_num_threads,
        verify=cfg.verify_model,
    )
    engine.load()
    rss_after_load = proc.memory_info().rss / MB

    # 3. audio in (16 kHz mono PCM16, or a loud refusal)
    info = wav_info(cfg.wav)
    x = read_slice(cfg.wav, cfg.offset_s, cfg.max_s)
    slice_s = len(x) / float(SAMPLE_RATE)

    # 4. segment -- by silence, never on a fixed grid
    segs = segments_for_mode(
        x,
        mode=cfg.segment_mode,
        max_segment_s=cfg.max_segment_s,
        fixed_chunk_s=cfg.fixed_chunk_s,
        sample_rate=SAMPLE_RATE,
    )

    # 5. the 10 Hz level emitter, on the AUDIO clock
    level = LevelEmitter(
        sink=emit if cfg.level else None,
        sample_rate=SAMPLE_RATE,
        audio_offset_s=cfg.offset_s,
    )

    # 6. infer, segment by segment
    rows: list[dict] = []
    texts: list[str] = []
    phases: dict | None = None
    infer_t0 = time.perf_counter()
    clock["phase"] = "infer"
    # The level emitter is fed CONTIGUOUSLY, in audio order: the silence before a segment and
    # the segment itself, each sample exactly once. So the wave covers the whole slice (10
    # events per audio second, gaps included -- a wave that skipped silence would mislead about
    # pauses), and each segment's levels arrive just before its text.
    cursor = 0
    for i, (a, b) in enumerate(segs):
        s0 = max(cursor, int(round(a * SAMPLE_RATE)))
        s1 = int(round(b * SAMPLE_RATE))
        if cfg.level:
            if s0 > cursor:
                level.feed(x[cursor:s0])  # the silence between the previous segment and this one
            if s1 > s0:
                level.feed(x[s0:s1])
        cursor = max(cursor, s1)
        audio = x[int(round(a * SAMPLE_RATE)) : s1]
        if cfg.phases and i in (0, len(segs) - 1):
            # BOTH ends: the FIRST call after load is atypical (its preprocessor is cold), and
            # the >=95% encoder share was measured on later chunks (05-onnx-asr.md:91-95).
            key = "first" if i == 0 else "last"
            try:
                if phases is None:
                    phases = {}
                probe = engine.phase_probe(audio)
                phases[key] = probe
                if i == 0 and len(segs) == 1:
                    phases["last"] = probe
            except Exception as exc:  # noqa: BLE001 -- instrument, never fatal
                phases = phases or {}
                phases[key] = {"error": f"{type(exc).__name__}: {exc}"}
        c0 = time.perf_counter()
        text = engine.recognize(audio, sample_rate=SAMPLE_RATE)
        wall = time.perf_counter() - c0
        clock["audio_s"] = cfg.offset_s + b
        texts.append(text or "")
        row = {
            "i": i,
            "start": round(cfg.offset_s + a, 3),
            "end": round(cfg.offset_s + b, 3),
            "audio_s": round(b - a, 3),
            "wall_s": round(wall, 3),
            "chars": len(text or ""),
            "text": text or "",
        }
        rows.append(row)
        emit({"type": "segment", **row})
    if cfg.level and cursor < len(x):
        level.feed(x[cursor:])  # the tail after the last segment
    infer_s = time.perf_counter() - infer_t0
    if cfg.level:
        level.close()
    sampler.stop()

    text = " ".join(t.strip() for t in texts if t and t.strip())
    durs = [r["audio_s"] for r in rows]
    walls = [r["wall_s"] for r in rows]
    processed = sum(durs)
    # steady state EXCLUDES the first segment (11-onnx-threads.md:46-49)
    steady_audio, steady_wall = sum(durs[1:]), sum(walls[1:])
    cpu_med, cpu_max = sampler.cpu_stats("infer")
    cpu_load_med, cpu_load_max = sampler.cpu_stats("load")
    mem = proc.memory_info()

    done = {
        "type": "done",
        "label": cfg.label or cfg.wav.name,
        "wav": str(cfg.wav),
        "model_dir": str(cfg.model_dir),
        "quantization": cfg.quantization,
        "provider_requested": cfg.provider,
        "segment_mode": cfg.segment_mode,
        "threads": {
            "intra": cfg.intra_op_num_threads,
            "inter": cfg.inter_op_num_threads,
            "env": env,
            "session_providers": engine.session_providers,
            "model_name": engine.threads_reported.get("model_name"),
            "onnx_asr": engine.threads_reported.get("onnx_asr"),
            "onnxruntime": engine.threads_reported.get("onnxruntime"),
            "ort_available_providers": engine.threads_reported.get("ort_available_providers"),
        },
        "wav_format": info.as_dict(),
        "offset_s": cfg.offset_s,
        "audio_s": round(slice_s, 3),
        "audio_processed_s": round(processed, 3),
        "n_segments": len(rows),
        "seg_median_s": round(_median(durs), 3),
        "seg_max_s": round(max(durs), 3) if durs else 0.0,
        "load_s": round(engine.load_s or 0.0, 3),
        "infer_s": round(infer_s, 3),
        "rtfx_infer": round(processed / infer_s, 2) if infer_s > 0 else None,
        "rtfx_steady": round(steady_audio / steady_wall, 2) if steady_wall > 0 else None,
        "rtfx_slice": round(slice_s / infer_s, 2) if infer_s > 0 else None,
        "rss_start_mb": round(rss_start, 1),
        "rss_after_load_mb": round(rss_after_load, 1),
        # the 1 Hz poll can miss the peak on a short run; the after-load reading is folded in
        "rss_peak_mb": round(max(sampler.peak_rss(), rss_after_load), 1),
        "rss_peak_wset_mb": round(mem.peak_wset / MB, 1),
        "cpu_median_pct": cpu_med,
        "cpu_max_pct": cpu_max,
        "cpu_load_median_pct": cpu_load_med,
        "cpu_load_max_pct": cpu_load_max,
        "rss_samples": len(sampler.points),
        "rss_curve": sampler.points,  # [wall_s, audio_s, rss_mb, cpu_pct, phase]
        "level": level.summary(),
        "phases": phases,
        "segments": rows,
        "text": text,
    }
    emit(done)
    return done
