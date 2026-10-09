"""chain.py -- CLIP -> AUDIO -> TRANSCRIPT -> INDEX ROW -> SEARCH, run as a CHAIN.

================================================================================
WHAT THIS IS, AND WHAT IT IS NOT
================================================================================
Every subsystem around this one is being built right now by lanes that cannot see each
other's work. Nothing else is proving the parts work as a CHAIN, so this runner does --
and it refuses to let a stage pass quietly, because a silent stage is a defect.

THE HEADLINE QUESTION, ANSWERED ON ITS FACE: **which stages ran for real?**
Every stage carries a `provenance` from `contracts.Provenance`:

    REAL               the shipped module in THIS repo did the work
    REAL_SUBSTITUTE    a real, working binary doing the job of a producer that DOES NOT
                       EXIST YET (ffmpeg stands in for the AAC `trak` that `mp4_writer`
                       has never had -- receipt-16 section 7)
    DOUBLE             a stand-in this lane wrote. The product did not do this.
    REFUSED            nothing ran; the stage said NO, with the measurement that proved it

A chain that passed entirely on doubles would be a SCAFFOLD, not a proof, and
`assert_provenance()` makes that state impossible to mistake for a pass.

================================================================================
FAILING LOUDLY, WHICH IS THE WHOLE POINT
================================================================================
Every stage either produces a MEASUREMENT or refuses with one. There is no third
outcome. Specifically:

  * `no-audio-stream` -- the clip has no audio. This is TRUE of 8/8 sample clips
    (receipt-13 claim 2) and is the measured state of this product's capture path. It is
    reported with the ffprobe evidence attached, not swallowed and not worked around.
  * `silent-device` -- audio WAS delivered and its peak is at or below the capture lane's
    own floor (`kAudioSilencePeakFloor`, checked against `wasapi_audio.h:65` at run time).
    **This is CORRECT BEHAVIOUR on this box**: receipt-16 measured a 0.000122 digital
    silence ceiling with nothing routed, and the routing is the owner's, not the code's.
  * `empty-transcript` -- 0 segments / 0 characters. The splitter drops silence-only
    segments (`segment.py:102-103`), so a silent clip transcribes to nothing and must stay
    searchable-as-nothing (`store.py:288-298`). Inventing text here would be the worst
    possible bug in this repo.
  * `not-found` -- the chain ran end to end and the clip did NOT come back from search.
    That is the failure this whole lane exists to catch.

THE ORDERING LAW IS ENFORCED, NOT ASSUMED: `ingest_clip` runs BEFORE the ASR pass
(`store.py:277-282` raises if the clip row is absent), which is S1-at-the-cut preceding
S3-in-the-background (specs/01-capture-modes-and-scheduling.md:68-70).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .contracts import (
    ASR_CHANNELS,
    ASR_SAMPLE_RATE_HZ,
    ASR_SAMPWIDTH,
    CUT_RESULT_TO_CLIP_PAYLOAD,
    REPO_ROOT,
    SILENCE_FLOOR_PROVENANCE,
    SILENCE_PEAK_FLOOR,
    ContractReport,
    Provenance,
    verify_contracts,
)

__all__ = [
    "StageRefused",
    "StageReport",
    "ChainReport",
    "ChainRunner",
    "CutResultMeta",
    "STAGE_ORDER",
    "VERDICTS",
    "main",
]

SRC = Path(__file__).resolve().parent.parent

#: What the transcript row says wrote it. The rewritten store's default is "light"
#: (store.py:164); this chain is the ASR pass, so it says so.
TRANSCRIPT_PRODUCER = "asr:parakeet-tdt-0.6b-v3:int8"


def _ms(seconds: float) -> int:
    """THE unit boundary: seconds (what the ASR produces) -> milliseconds (what the
    rewritten schema stores). It happens HERE and nowhere else, because the store that used
    to own this boundary (`store._ms`) was replaced."""
    return int(round(float(seconds) * 1000))

#: The stage names, in the order they run. The gate prints this table with provenance.
STAGE_ORDER: tuple[str, ...] = (
    "capture",      # a clip + its device metadata (CutResult-shaped)
    "probe",        # what is actually inside the clip
    "extract",      # clip audio -> 16 kHz mono PCM16 wav (the ASR's own contract)
    "ingest-clip",  # the index WRITER, at the cut
    "segments",     # the splitter, before any inference
    "asr",          # the real model
    "ingest-asr",   # the transcript, verbatim, into the index
    "search",       # the READ side must hand this clip back
)

#: Every named verdict this chain can emit. A stage that cannot name its outcome is a bug.
VERDICTS: tuple[str, ...] = (
    "ok",
    "no-audio-stream",
    "silent-device",
    "empty-transcript",
    "not-found",
    "missing-clip",
    "bad-wav",
    "clip-row-refused",
    "tool-missing",
)


class StageRefused(RuntimeError):
    """A stage said NO, with a verdict and the measurement that produced it.

    Raised, never returned: a refusal that a caller can forget to check is exactly the
    silent stage this lane was told to eliminate.
    """

    def __init__(self, verdict: str, message: str, measured: dict | None = None):
        super().__init__(message)
        self.verdict = verdict
        self.message = message
        self.measured = measured or {}


@dataclass
class StageReport:
    """One row of the provenance table. `provenance` is the whole value of this lane."""

    name: str
    provenance: str = Provenance.DOUBLE
    subject: str = ""                 # what actually ran: a module path or an exe name
    verdict: str = "ok"
    ok: bool = True
    measured: dict = field(default_factory=dict)
    error: str = ""
    note: str = ""

    def row(self) -> str:
        mark = "ok  " if self.ok else "FAIL"
        nums = " ".join(f"{k}={v}" for k, v in self.measured.items())
        return f"  {self.name:<12} {mark}  {self.provenance:<16} {self.subject:<44} {nums}"

    def as_dict(self) -> dict:
        return {
            "name": self.name, "provenance": self.provenance, "subject": self.subject,
            "verdict": self.verdict, "ok": self.ok, "measured": self.measured,
            "error": self.error, "note": self.note,
        }


@dataclass(frozen=True)
class CutResultMeta:
    """The C++ `CutResult` (src/capture/replay.h:65-82), shaped for a payload builder.

    This is a DOUBLE for the C++ value -- `Replay::perform_cut()` cannot be called from
    Python and cannot run on this box anyway (WGC refuses every capture item here,
    receipt-16). The FIELDS are the real ones, verified against the header by
    `contracts._check_cut_result`, so the mapping this chain writes is the mapping the
    product needs even though the value is not the product's.
    """

    clip_path: str
    clip_seconds: float = 0.0
    bytes_written: int = 0
    frames_in_clip: int = 0
    encoded_in_window: int = 0
    captured_in_window: int = 0
    expected_in_window: int = 0
    ring_dropped_at_cut: int = 0
    base_qpc_ns: int = 0
    cut_qpc_ns: int = 0
    base_abs: int = 0
    end_abs: int = 0
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    source_device: str | None = None
    mode: str = "instant"
    clip_id: str | None = None
    aac_path: str | None = None
    h264_path: str | None = None

    @classmethod
    def from_mapping(cls, data: dict) -> "CutResultMeta":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


# ======================================================================================
# the doubles -- every stage that cannot run for real, with its reason on its face
# ======================================================================================

class Doubles:
    """The stands-in, and WHY each one exists. Nothing here pretends to be the product.

    A double is not a failure of the lane. It is the honest boundary: the product cannot
    capture on this host, so the capture stage is a double, and the receipt says so in a
    table rather than in a footnote nobody reads.
    """

    @staticmethod
    def capture(meta: CutResultMeta) -> StageReport:
        return StageReport(
            "capture", Provenance.DOUBLE, "CutResultMeta (this lane) + a real clip on disk",
            ok=True,
            measured={"frames": meta.frames_in_clip, "clip_s": round(meta.clip_seconds, 3)},
            note="DOUBLE: Replay::perform_cut() is C++ and cannot run here (WGC refuses every "
                 "capture item, receipt-16). The clip is a REAL capture artefact from "
                 "_main/runs/; only the CutResult VALUE is a stand-in.",
        )

    @staticmethod
    def extractor() -> StageReport:
        return StageReport(
            "extract", Provenance.DOUBLE, "no extractor wired",
            ok=False, error="no extractor", note="test double requested but none configured",
        )

    @staticmethod
    def asr() -> StageReport:
        return StageReport(
            "asr", Provenance.DOUBLE, "canned `done` payload", ok=True,
            measured={"n_segments": 2, "chars": 11},
            note="DOUBLE: a fixed `done` dict, shaped like asr.runner.transcribe's return. "
                 "Used only to prove the INDEX half of the chain; never a transcript claim.",
        )

    @staticmethod
    def search() -> StageReport:
        return StageReport(
            "search", Provenance.DOUBLE, "canned SearchResult", ok=True,
            measured={"hits": 1},
            note="DOUBLE: proves nothing about the read path.",
        )


# The canned `done`, shaped field-for-field from `asr.runner.transcribe`'s return
# (src/asr/runner.py:259-306). Deliberately nonsense TEXT: a double must never be
# mistakable for a measurement, and the gate asserts this string appears nowhere real.
CANNED_DONE: dict = {
    "type": "done",
    "label": "DOUBLE",
    "wav": "<double>",
    "model_dir": "<double>",
    "quantization": "int8",
    "provider_requested": "cpu",
    "segment_mode": "silence",
    "offset_s": 0.0,
    "audio_s": 2.0,
    "audio_processed_s": 2.0,
    "n_segments": 2,
    "seg_median_s": 1.0,
    "seg_max_s": 1.0,
    "load_s": 0.0,
    "infer_s": 0.0,
    "rtfx_infer": None,
    "rtfx_steady": None,
    "rtfx_slice": None,
    "rss_start_mb": 0.0,
    "rss_after_load_mb": 0.0,
    "rss_peak_mb": 0.0,
    "rss_peak_wset_mb": 0.0,
    "cpu_median_pct": None,
    "cpu_max_pct": None,
    "rss_samples": 0,
    "rss_curve": [],
    "level": {"n_events": 0, "hz": 10.0},
    "phases": None,
    "segments": [
        {"i": 0, "start": 0.0, "end": 1.0, "audio_s": 1.0, "wall_s": 0.1, "chars": 5,
         "text": "zqxjk DOUBLEONLYTOKEN"},
        {"i": 1, "start": 1.0, "end": 2.0, "audio_s": 1.0, "wall_s": 0.1, "chars": 6,
         "text": "wvuut DOUBLEONLYTOKEN"},
    ],
    "text": "zqxjk wvuut DOUBLEONLYTOKEN",
}

#: A token that can ONLY appear if a double's text was written. The gate searches the db
#: for it and requires the real run to be empty. A scaffold cannot hide behind it.
DOUBLE_ONLY_TOKEN = "DOUBLEONLYTOKEN"


# ======================================================================================
# the runner
# ======================================================================================

class ChainRunner:
    """Drive one clip from disk to a searchable index row, loudly, with provenance."""

    def __init__(
        self,
        db_path: str | Path,
        work_dir: str | Path,
        *,
        model_dir: str | Path | None = None,
        max_audio_s: float = 0.0,
        segment_mode: str | None = None,
        run_asr: bool = True,
        extractor: str = "ffmpeg",
        label: str = "",
    ):
        self.db_path = Path(db_path)
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.model_dir = Path(model_dir) if model_dir else (
            REPO_ROOT / "models" / "parakeet-tdt-0.6b-v3-onnx")
        self.max_audio_s = float(max_audio_s)
        self.segment_mode = segment_mode          # None => the model's own default
        self.run_asr = bool(run_asr)
        self.extractor = extractor
        self.label = label
        self.stages: list[StageReport] = []
        self.contracts: ContractReport | None = None
        self._con: Any = None

    # -- helpers -----------------------------------------------------------------------
    def _stage(self, **kw) -> StageReport:
        rep = StageReport(**kw)
        self.stages.append(rep)
        return rep

    def _tool(self, name: str) -> str | None:
        found = shutil.which(name)
        if found:
            return found
        for guess in (rf"H:\ffmpeg\bin\{name}.exe", rf"C:\ffmpeg\bin\{name}.exe",
                      rf"C:\ProgramData\chocolatey\bin\{name}.exe"):
            if Path(guess).exists():
                return guess
        return None

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def _content_key(self, clip: Path) -> str:
        """The clip's IDENTITY: the whole-file SHA-256, hex, 64 chars.

        The rewritten schema makes this the PRIMARY identity and CHECKs its length
        (schema.sql:44); identity is NEVER the path (schema.sql:4-7, 07-index-search.md:46).
        This replaces the `clip_id` string the old store keyed on -- see `CONTRACT_GAPS`.
        """
        return self._sha256(clip)

    def clip_payload(self, clip: Path, meta: CutResultMeta) -> dict:
        """The `store.upsert_video` kwargs, built from the `CutResult` member names.

        `duration_s` is converted to `duration_ms` here because the new writer takes
        MILLISECONDS and has no `_ms()` boundary of its own.

        `started_at_s` HAS NO COLUMN in the rewritten schema: the video table carries
        `mtime_ns` and `last_seen_scan` only. The epoch time axis the old store filtered on
        is GONE, so this chain records the loss on the stage rather than inventing a column.
        """
        stat = clip.stat()
        dur = meta.clip_seconds or self._probe(clip).get("duration_s", 0.0) or 0.0
        self.started_at_s_source = (
            "NOT WRITABLE: the rewritten schema has no epoch column on `video` "
            "(schema.sql:41-63); only mtime_ns. The old store's started_at_s filter axis is gone.")
        return {
            "content_key": self._content_key(clip),
            "path": str(clip),
            "size_bytes": int(meta.bytes_written or stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
            "duration_ms": _ms(dur),
            "codec": meta.video_codec or None,
            "w": meta.width,
            "h": meta.height,
            "fps": meta.fps,
            "file_key": None,
            "bitrate": None,
            "last_seen_scan": None,
            "missing": 0,
            "state": "recorded",
        }

    # -- stage 1: the clip ------------------------------------------------------------
    def stage_capture(self, meta: CutResultMeta) -> StageReport:
        clip = Path(meta.clip_path)
        if not clip.exists():
            rep = self._stage(name="capture", provenance=Provenance.DOUBLE,
                              subject="CutResultMeta (this lane)", verdict="missing-clip",
                              ok=False, error=f"no such clip: {clip}")
            raise StageRefused("missing-clip", f"no such clip: {clip}", {"path": str(clip)})
        return self._stage(name="capture", provenance=Provenance.DOUBLE,
                           subject="CutResultMeta (this lane) + real clip on disk",
                           ok=True,
                           measured={"bytes": meta.bytes_written or clip.stat().st_size,
                                     "device": meta.source_device or "none"},
                           note="DOUBLE for the CutResult VALUE (C++, cannot run here: WGC "
                                "refuses every capture item, receipt-16). The clip is a REAL "
                                "capture artefact on disk.")

    # -- stage 2: what is actually in it ----------------------------------------------
    def _probe(self, clip: Path) -> dict:
        exe = self._tool("ffprobe")
        if not exe:
            return {"tool": "missing"}
        out = subprocess.run(
            [exe, "-v", "error", "-show_entries",
             "stream=index,codec_type,codec_name,width,height,sample_rate,channels:format=duration",
             "-of", "json", str(clip)],
            capture_output=True, text=True, timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        if out.returncode != 0:
            return {"tool": exe, "error": out.stderr.strip()[:400]}
        try:
            data = json.loads(out.stdout or "{}")
        except json.JSONDecodeError as exc:
            return {"tool": exe, "error": f"unparseable ffprobe json: {exc}"}
        streams = data.get("streams", [])
        fmt = data.get("format", {})
        audio = [s for s in streams if s.get("codec_type") == "audio"]
        video = [s for s in streams if s.get("codec_type") == "video"]
        try:
            duration_s = float(fmt.get("duration", 0.0))
        except (TypeError, ValueError):
            duration_s = 0.0
        return {
            "tool": exe, "duration_s": round(duration_s, 3),
            "n_streams": len(streams), "n_video": len(video), "n_audio": len(audio),
            "video_codec": video[0].get("codec_name") if video else None,
            "width": video[0].get("width") if video else None,
            "height": video[0].get("height") if video else None,
            "audio_codec": audio[0].get("codec_name") if audio else None,
            "audio_rate": audio[0].get("sample_rate") if audio else None,
        }

    def stage_probe(self, clip: Path) -> dict:
        info = self._probe(clip)
        if info.get("tool") == "missing":
            self._stage(name="probe", provenance=Provenance.REFUSED, subject="ffprobe",
                        verdict="tool-missing", ok=False,
                        error="ffprobe is not on PATH and not in the known locations")
            raise StageRefused("tool-missing", "ffprobe not found; cannot measure the clip",
                               {"searched": ["PATH", r"H:\ffmpeg\bin", r"C:\ffmpeg\bin"]})
        if info.get("error"):
            self._stage(name="probe", provenance=Provenance.REFUSED, subject=info.get("tool", "ffprobe"),
                        verdict="bad-wav", ok=False, error=info["error"])
            raise StageRefused("bad-wav", f"ffprobe could not read the clip: {info['error']}",
                               {"clip": str(clip)})
        n_audio = int(info.get("n_audio", 0))
        verdict = "ok" if n_audio else "no-audio-stream"
        self._stage(
            name="probe", provenance=Provenance.REAL_SUBSTITUTE, subject="ffprobe (external binary)",
            verdict=verdict, ok=True,
            measured={"n_streams": info["n_streams"], "n_video": info["n_video"],
                      "n_audio": n_audio, "dur_s": info["duration_s"],
                      "vcodec": info["video_codec"]},
            note=("REAL_SUBSTITUTE: ffprobe is an EXTERNAL binary, not a shipped module of "
                  "this repo -- `REAL` means the shipped module did the work "
                  "(contracts.Provenance.REAL), and applying that definition to ffmpeg while "
                  "denying it to ffprobe was the same class of external tool judged two ways. "
                  "CORRECTED by the verifier. It stands in for an mp4 INSPECTOR the product "
                  "has never had, where `extract` stands in for a WRITER it is missing."
                  if n_audio else
                  "REAL_SUBSTITUTE, and NO AUDIO STREAM. Measured, and TRUE of 8/8 sample "
                  "clips (receipt-13 claim 2): the muxer is video-only (receipt-16 "
                  "section 7). Nothing is invented to fill the hole."),
        )
        return info

    # -- stage 3: audio in --------------------------------------------------------------
    def stage_extract(self, clip: Path, wav_path: Path, max_s: float = 0.0) -> dict:
        """clip audio -> the ASR's own format: 16 kHz, mono, PCM16.

        ffmpeg is a REAL binary doing the job of a producer that DOES NOT EXIST: the AAC
        `trak` `mp4_writer` has never had. So this stage is REAL_SUBSTITUTE, and the gate
        prints it as such. It is not REAL, and calling it REAL would be the first lie in
        the chain.
        """
        exe = self._tool(self.extractor)
        if not exe:
            self._stage(name="extract", provenance=Provenance.REFUSED, subject=self.extractor,
                        verdict="tool-missing", ok=False, error=f"{self.extractor} not found")
            raise StageRefused("tool-missing", f"{self.extractor} not found", {})

        cmd = [exe, "-y", "-v", "error", "-i", str(clip), "-vn", "-sn", "-dn",
               "-ar", str(ASR_SAMPLE_RATE_HZ), "-ac", str(ASR_CHANNELS),
               "-c:a", "pcm_s16le"]
        if max_s > 0:
            cmd += ["-t", str(max_s)]
        cmd += [str(wav_path)]
        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=900,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        wall = time.perf_counter() - t0
        if proc.returncode != 0 or not wav_path.exists():
            self._stage(name="extract", provenance=Provenance.REAL_SUBSTITUTE, subject=exe,
                        verdict="bad-wav", ok=False,
                        error=f"rc={proc.returncode} {proc.stderr.strip()[:300]}")
            raise StageRefused("bad-wav", f"{exe} failed on {clip.name}: "
                                          f"{proc.stderr.strip()[:200]}",
                               {"rc": proc.returncode})
        return self._measure_wav(wav_path, subject=exe, wall=wall)

    def _measure_wav(self, wav_path: Path, subject: str, wall: float = 0.0) -> dict:
        """Read the wav back through the REAL `asr.audio` module and MEASURE it.

        The measurement is not decoration: the peak decides `silent-device`, and that
        threshold belongs to the capture lane, not to this one.
        """
        from asr.audio import read_slice, wav_info  # the REAL module, imported here

        info = wav_info(wav_path)
        x = read_slice(wav_path, 0.0, 0.0)
        import numpy as np
        peak = float(np.abs(x).max()) if len(x) else 0.0
        rms = float(np.sqrt((x ** 2).mean())) if len(x) else 0.0
        silent = peak <= SILENCE_PEAK_FLOOR
        verdict = "silent-device" if silent else "ok"
        self._stage(
            name="extract", provenance=Provenance.REAL_SUBSTITUTE, subject=subject,
            verdict=verdict, ok=True,
            measured={"dur_s": round(info.duration_s, 3), "rate": info.sample_rate,
                      "ch": info.channels, "sampwidth": info.sampwidth,
                      "peak": round(peak, 6), "rms": round(rms, 6),
                      "floor": SILENCE_PEAK_FLOOR, "bytes": wav_path.stat().st_size,
                      **({"extract_s": round(wall, 2)} if wall else {})},
            note=("REAL_SUBSTITUTE: ffmpeg does the extraction that the unwritten AAC "
                  "`trak` in mp4_writer.h cannot yet do (receipt-16 section 7). "
                  if not silent else
                  "SILENT DEVICE: audio was delivered and its peak is at/below "
                  f"kAudioSilencePeakFloor={SILENCE_PEAK_FLOOR}. {SILENCE_FLOOR_PROVENANCE}. "
                  "On this box that is CORRECT BEHAVIOUR with nothing routed into the "
                  "render endpoint — not a bug in this chain."),
        )
        if silent:
            raise StageRefused("silent-device", (
                f"audio delivered but peak {peak:.6f} <= floor {SILENCE_PEAK_FLOOR}: "
                "nothing is routed into the capture endpoint. Correct behaviour, reported "
                "loudly instead of transcribing a phantom transcript."),
                {"peak": round(peak, 6), "floor": SILENCE_PEAK_FLOOR,
                 "dur_s": round(info.duration_s, 3)})
        return {"info": info.as_dict(), "peak": peak, "rms": rms,
                "frames": info.frames, "duration_s": info.duration_s}

    # -- stage 4/6/7: the index ---------------------------------------------------------
    def _con_or_open(self):
        if self._con is None:
            # `search.py:28` does a bare `import store`, so the package DIRECTORY must be
            # importable -- `src/index/__init__.py` is gone from the tree. Measured: without
            # this, `import search` raises ModuleNotFoundError: No module named 'store'.
            import sys
            pkg_dir = str(SRC / "index")
            if pkg_dir not in sys.path:
                sys.path.insert(0, pkg_dir)
            import store  # the REAL module, top-level by the rewrite's own convention
            self._con = store.connect(str(self.db_path), create=True)
        return self._con

    def stage_ingest_clip(self, payload: dict) -> int:
        """S1 -- the clip row, at the cut, before any transcript exists.

        The writer is `store.upsert_video` (keyword-only, identity = `content_key`), so the
        payload is built here field-for-field and an unknown field is a REFUSAL, not a log
        line: a silently dropped keyword leaves a column empty forever with nothing wrong
        looking anywhere.
        """
        import store  # the REAL module

        wanted = {"content_key", "path", "size_bytes", "mtime_ns", "duration_ms", "file_key",
                  "codec", "w", "h", "fps", "bitrate", "last_seen_scan", "missing", "state"}
        unknown = sorted(set(payload) - wanted)
        if unknown:
            self._stage(name="ingest-clip", provenance=Provenance.REFUSED,
                        subject="store.upsert_video", verdict="clip-row-refused", ok=False,
                        error=f"payload carries field(s) upsert_video does not accept: {unknown}")
            raise StageRefused("clip-row-refused",
                               f"clip payload carries field(s) the index writer does not own: "
                               f"{unknown}. Refusing: a silently dropped field is how a column "
                               "stays empty forever.", {"unknown": unknown})
        con = self._con_or_open()
        video_id = int(store.upsert_video(con, **payload))
        ok = video_id > 0
        self._stage(name="ingest-clip", provenance=Provenance.REAL,
                    subject="store.upsert_video", ok=ok,
                    measured={"video_id": video_id, "content_key": payload["content_key"][:12],
                              "duration_ms": payload["duration_ms"],
                              "started_at_s_source": self.started_at_s_source,
                              "db_bytes": self.db_path.stat().st_size if
                                          self.db_path.exists() else 0},
                    note="S1: the clip row at the cut. Identity is content_key (the whole-file "
                         "SHA-256), NOT a minted id and NOT the path (schema.sql:4-7). "
                         "started_at_s is NOT a column in the new schema -- the time axis this "
                         "chain used to write is gone; recorded, not silently dropped.")
        if not ok:
            raise StageRefused("clip-row-refused",
                               f"upsert_video returned video_id={video_id}",
                               {"payload": {k: str(v)[:60] for k, v in payload.items()}})
        return video_id

    def stage_segments(self, wav_path: Path) -> list:
        from asr.audio import read_slice
        from asr.constants import DEFAULT_SEGMENT_MODE
        from asr.segment import segments_for_mode  # the REAL modules

        x = read_slice(wav_path, 0.0, 0.0)
        mode = self.segment_mode or DEFAULT_SEGMENT_MODE
        segs = segments_for_mode(x, mode=mode, sample_rate=ASR_SAMPLE_RATE_HZ)
        dur = len(x) / float(ASR_SAMPLE_RATE_HZ)
        self._stage(name="segments", provenance=Provenance.REAL,
                    subject="asr.segment.segments_for_mode",
                    verdict="empty-transcript" if not segs else "ok",
                    ok=True,
                    measured={"mode": mode, "n_segments": len(segs), "audio_s": round(dur, 3),
                              "covered_s": round(sum(b - a for a, b in segs), 3)},
                    note="" if segs else
                         "0 segments is a MEASURED outcome, not an error: the splitter "
                         "drops silence-only segments (segment.py:102-103) and sub-0.6 s "
                         "ones (segment.py:100). Text must NOT be invented here.")
        return segs

    def stage_asr(self, wav_path: Path, clip_id: str) -> dict:
        from asr.constants import (
            DEFAULT_SEGMENT_MODE,
            INTRA_OP_NUM_THREADS,
            INTER_OP_NUM_THREADS,
            QUANTIZATION,
        )
        from asr.runner import TranscribeConfig, transcribe  # the REAL module

        if not self.run_asr:
            self._stage(name="asr", provenance=Provenance.DOUBLE, subject="canned `done`",
                        ok=True, measured={"n_segments": len(CANNED_DONE["segments"])},
                        note="DOUBLE (--no-asr): the canned `done` in chain.py. Proves the "
                             "index half only; it is NOT a transcript claim.")
            return dict(CANNED_DONE)

        cfg = TranscribeConfig(
            wav=wav_path, model_dir=self.model_dir, quantization=QUANTIZATION,
            provider="cpu", intra_op_num_threads=INTRA_OP_NUM_THREADS,
            inter_op_num_threads=INTER_OP_NUM_THREADS,
            segment_mode=self.segment_mode or DEFAULT_SEGMENT_MODE,
            level=False, label=self.label or clip_id,
        )
        t0 = time.perf_counter()
        done = transcribe(cfg)
        wall = time.perf_counter() - t0
        rows = done.get("segments") or []
        self._stage(name="asr", provenance=Provenance.REAL,
                    subject="asr.runner.transcribe",
                    verdict="ok" if rows else "empty-transcript", ok=True,
                    measured={"n_segments": len(rows), "chars": len(done.get("text") or ""),
                              "audio_s": done.get("audio_s"), "rtfx_steady": done.get("rtfx_steady"),
                              "rss_peak_mb": done.get("rss_peak_mb"),
                              "providers": "x".join(
                                  str(p) for p in done.get("threads", {}).get(
                                      "session_providers", [])),
                              "wall_s": round(wall, 2)},
                    note="" if rows else
                         "0 segments from the REAL model: a measured outcome on silent or "
                         "unintelligible audio, not a failure of the chain.")
        return done

    def stage_ingest_asr(self, video_id: int, done: dict) -> dict:
        """S3 -- the transcript, verbatim, one row per ASR segment.

        SECONDS -> MILLISECONDS happens HERE and nowhere else: the ASR counts in 3-dp
        seconds, `segment.start_ms` is ms, and the rewritten store no longer owns a `_ms()`
        boundary (the old store.py:95 did). Writing seconds into a ms column puts every
        window at 1/1000 of its real position and every time filter misses silently.

        The FTS row is NOT written by this chain: schema.sql:173-186 carries triggers that
        mirror transcript -> text_fts. Writing it by hand would double every row.
        """
        import store  # the REAL module

        con = self._con_or_open()
        rows = done.get("segments") or []
        written = 0
        for row in rows:
            start_ms = _ms(row.get("start", 0.0))
            end_ms = _ms(row.get("end", 0.0))
            seg_id = int(store.upsert_segment(
                con, video_id=video_id, start_ms=start_ms, end_ms=end_ms,
                n_speech=1, state="closed"))
            text = str(row.get("text") or "")
            store.upsert_transcript(
                con, seg_id=seg_id, text=text, text_norm=text.lower(), start_ms=start_ms,
                producer=TRANSCRIPT_PRODUCER)
            written += 1
        fts = int(con.execute("SELECT count(*) FROM text_fts WHERE source='transcript'"
                              ).fetchone()[0])
        self._stage(name="ingest-asr", provenance=Provenance.REAL,
                    subject="store.upsert_segment + store.upsert_transcript",
                    ok=written == len(rows),
                    measured={"segments": written, "expected": len(rows),
                              "text_fts_rows": fts, "producer": TRANSCRIPT_PRODUCER,
                              "unit": "seconds in, ms stored (converted here)"},
                    note="S3: the transcript, into the row S1 already wrote. The FTS row came "
                         "from the schema's TRIGGERS, not from this chain.")
        if written != len(rows):
            raise StageRefused("not-found",
                               f"wrote {written} of {len(rows)} transcript rows",
                               {"written": written, "expected": len(rows)})
        return {"segments": written, "fts_rows": fts, "video_id": video_id}

    def stage_search(self, query: str, video_id: int) -> dict:
        """The last link: the clip must come BACK, named, from the read side."""
        import search  # the REAL module
        import store  # for the seg_id -> path mapping the reader itself uses

        con = self._con_or_open()
        index = search.SearchIndex(con)
        rows = index.search_text(query, k=10)
        meta = store.segments_for(con, [r[0] for r in rows]) if rows else {}
        hit_ids = [int(v["video_id"]) for v in meta.values()]
        hit_paths = {str(v["path"]) for v in meta.values()}
        found = video_id in hit_ids
        self._stage(
            name="search", provenance=Provenance.REAL,
            subject="search.SearchIndex.search_text",
            verdict="ok" if found else "not-found", ok=found,
            measured={"query": query, "n_lexical_hits": len(rows), "video_ids": hit_ids,
                      "paths": len(hit_paths),
                      "population": int(con.execute(
                          "SELECT count(*) FROM video").fetchone()[0])},
            note="" if found else
                 "THE CHAIN'S OWN FAILURE MODE: every stage completed and the clip did not "
                 "come back. Nothing here invents a hit.",
        )
        if not found:
            raise StageRefused("not-found",
                               f"search {query!r} returned {len(rows)} lexical hit(s), none "
                               f"belonging to video_id={video_id}",
                               {"query": query, "video_ids": hit_ids,
                                "lexical_hits": len(rows)})
        return {"query": query, "n_lexical_hits": len(rows), "video_ids": hit_ids}

    # -- the whole run -------------------------------------------------------------------
    def run(self, meta: CutResultMeta, query: str | None = None) -> "ChainReport":
        contracts = verify_contracts()
        self.contracts = contracts
        if not contracts.ok:
            raise StageRefused("not-found", "the declared contracts do not match the "
                                             "producers; refusing to run",
                               {"failed": [c.name for c in contracts.failed]})

        clip = Path(meta.clip_path)
        content_key = self._content_key(clip)
        label = content_key[:16]
        wav_path = self.work_dir / f"{label}.wav"
        done: dict = {}
        refusal: StageRefused | None = None
        text = ""
        video_id = 0

        try:
            self.stage_capture(meta)
            info = self.stage_probe(clip)
            if not info.get("n_audio"):
                # The MEASURED hole. Refuse here, with the probe evidence attached.
                raise StageRefused(
                    "no-audio-stream",
                    f"{clip.name} carries {info.get('n_audio')} audio stream(s) of "
                    f"{info.get('n_streams')} (measured by ffprobe). The muxer is video-only, "
                    "so this clip has nothing for the ASR to hear. Refusing rather than "
                    "inventing an audio track.",
                    {"n_streams": info.get("n_streams"), "n_video": info.get("n_video"),
                     "n_audio": info.get("n_audio"), "dur_s": info.get("duration_s"),
                     "probe": "ffprobe -show_entries stream=..."},
                )
            self.stage_extract(clip, wav_path, max_s=self.max_audio_s)
            payload = self.clip_payload(clip, meta)
            payload["codec"] = info.get("video_codec") or payload.get("codec")
            payload["w"] = payload.get("w") or info.get("width")
            payload["h"] = payload.get("h") or info.get("height")
            video_id = self.stage_ingest_clip(payload)
            self.stage_segments(wav_path)
            done = self.stage_asr(wav_path, label)
            text = done.get("text") or ""
            self.stage_ingest_asr(video_id, done)
            q = query or _pick_query(text)
            if not q:
                raise StageRefused(
                    "empty-transcript",
                    f"the ASR returned {len(text)} characters over "
                    f"{len(done.get('segments') or [])} segment(s), so there is no token to "
                    "search for. That is a MEASURED outcome; inventing a query would prove "
                    "nothing.", {"chars": len(text),
                                 "n_segments": len(done.get("segments") or [])})
            self.stage_search(q, video_id)
        except StageRefused as exc:
            refusal = exc
            self._stage(name="chain", provenance=Provenance.REFUSED, subject="-",
                        verdict=exc.verdict, ok=False, error=exc.message,
                        measured=exc.measured)

        return ChainReport(
            clip_id=content_key, clip_path=str(clip), refusal=refusal,
            stages=list(self.stages), contracts=contracts, transcript=text,
            db_path=str(self.db_path), video_id=video_id,
        )

    def close(self) -> None:
        if self._con is not None:
            try:
                self._con.close()
            finally:
                self._con = None


def _pick_query(text: str) -> str:
    """The longest alphabetic token of length >= 4 in the REAL transcript.

    The token is what `search_text` is asked, so the last stage of the chain can only pass
    on words the MODEL actually produced. Nothing here is seeded from a fixture.
    """
    import re
    tokens = [t for t in re.findall(r"[^\W_]+", text or "", re.UNICODE) if len(t) >= 4]
    if not tokens:
        return ""
    tokens.sort(key=lambda t: (-len(t), t))
    return tokens[0]


@dataclass
class ChainReport:
    """The result of one chain run. `provenance_table()` is the headline deliverable."""

    clip_id: str
    clip_path: str
    refusal: StageRefused | None
    stages: list[StageReport]
    contracts: ContractReport | None = None
    transcript: str = ""
    db_path: str = ""
    video_id: int = 0

    @property
    def ok(self) -> bool:
        return self.refusal is None and all(s.ok for s in self.stages)

    @property
    def verdict(self) -> str:
        if self.ok:
            return "ok"
        return self.refusal.verdict if self.refusal else "unknown"

    def provenance_table(self) -> str:
        """THE TABLE. Stage, did it pass, WHO ACTUALLY DID IT, and the numbers."""
        head = (f"  {'stage':<12} {'':<4}  {'provenance':<16} {'what actually ran':<44} numbers")
        rule = f"  {'-' * 12} {'-' * 4}  {'-' * 16} {'-' * 44} {'-' * 24}"
        return "\n".join([head, rule] + [s.row() for s in self.stages])

    def counts(self) -> dict:
        out: dict = {}
        for s in self.stages:
            out[s.provenance] = out.get(s.provenance, 0) + 1
        return out

    def is_scaffold(self) -> bool:
        """True when no stage ran against the real module. A scaffold says so on its face."""
        return not any(s.provenance == Provenance.REAL for s in self.stages)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok, "verdict": self.verdict, "clip_id": self.clip_id,
            "clip_path": self.clip_path, "db_path": self.db_path,
            "transcript": self.transcript,
            "transcript_chars": len(self.transcript),
            "is_scaffold": self.is_scaffold(),
            "provenance_counts": self.counts(),
            "stages": [s.as_dict() for s in self.stages],
            "refusal": (None if self.refusal is None else
                        {"verdict": self.refusal.verdict, "message": self.refusal.message,
                         "measured": self.refusal.measured}),
            "contracts": None if self.contracts is None else self.contracts.as_dict(),
        }


# ======================================================================================
# the CLI the gate drives
# ======================================================================================

def _load_meta(args: argparse.Namespace) -> CutResultMeta:
    if args.meta:
        data = json.loads(Path(args.meta).read_text(encoding="utf-8"))
        return CutResultMeta.from_mapping(data)
    clip = Path(args.clip)
    stat = clip.stat() if clip.exists() else None
    return CutResultMeta(
        clip_path=str(clip),
        bytes_written=stat.st_size if stat else 0,
        source_device=args.device,
        mode=args.mode,
        width=None, height=None, fps=None,
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m pipeline.chain",
        description="Clip -> audio -> transcript -> index row -> search, with provenance.",
    )
    p.add_argument("--clip", default="", help="the mp4 to drive")
    p.add_argument("--meta", default="", help="a CutResult-shaped JSON file; overrides --clip")
    p.add_argument("--device", default="", help="source_device recorded on the clip row")
    p.add_argument("--mode", default="instant", help="instant | manual | highlight")
    p.add_argument("--db", required=True, help="the sqlite index to write")
    p.add_argument("--work", required=True, help="scratch dir for the extracted wav")
    p.add_argument("--model-dir", default="")
    p.add_argument("--max-audio-s", type=float, default=0.0)
    p.add_argument("--segment-mode", default="")
    p.add_argument("--query", default="", help="search token; default = a token from the REAL transcript")
    p.add_argument("--no-asr", action="store_true",
                   help="run the index half on the canned double (NO transcript claim)")
    p.add_argument("--expect", default="", help="a verdict this run MUST produce, e.g. no-audio-stream")
    p.add_argument("--forbid-token", default="",
                   help="fail if this string appears anywhere in the db (double leakage)")
    p.add_argument("--json", default="", help="write the full report here")
    p.add_argument("--require-real-stages", type=int, default=0,
                   help="fail unless at least this many stages ran REAL")
    return p


def _db_contains(db: Path, needle: str) -> int:
    """How many `transcript` rows carry `needle`. An UNREADABLE db must NOT read as clean.

    The verifier caught the earlier version returning 0 on `sqlite3.OperationalError`, which
    reports an unreadable or absent-schema index as "no leak" -- i.e. a broken detector would
    have passed ARM D. A missing db is genuinely zero rows; a db that exists and cannot be
    queried is a FAILURE, and is raised as one.
    """
    import sqlite3
    if not needle:
        return 0
    if not db.exists():
        return 0        # nothing was written, so nothing leaked -- the honest zero
    con = sqlite3.connect(str(db))
    try:
        return int(con.execute(
            "SELECT count(*) FROM transcript WHERE text LIKE ?", (f"%{needle}%",)
        ).fetchone()[0])
    except sqlite3.OperationalError as exc:
        raise StageRefused(
            "not-found",
            f"the leak check could not read {db.name}: {exc}. A detector that cannot read the "
            "index would report 'no leak' and pass -- which is worse than no detector.",
            {"db": str(db), "error": str(exc)}) from exc
    finally:
        con.close()


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.clip and not args.meta:
        print("pipeline.chain: need --clip or --meta", file=sys.stderr)
        return 2
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))

    meta = _load_meta(args)
    runner = ChainRunner(
        args.db, args.work, model_dir=args.model_dir or None,
        max_audio_s=args.max_audio_s, segment_mode=args.segment_mode or None,
        run_asr=not args.no_asr, label=args.device,
    )
    try:
        report = runner.run(meta, query=args.query or None)
    except StageRefused as exc:
        print(f"pipeline.chain: REFUSED {exc.verdict}: {exc.message}", file=sys.stderr)
        print(json.dumps({"ok": False, "verdict": exc.verdict, "measured": exc.measured,
                          "contracts": verify_contracts().as_dict()}, indent=2))
        return 1
    finally:
        runner.close()

    print("PIPELINE CHAIN -- provenance table")
    # WHICH BYTES RAN. A control arm copies this package, mutates the copy, and asserts the
    # copy goes RED. If the import ever resolves to the live tree instead, the control
    # passes VACUOUSLY -- which is the exact failure receipt-16 section 10 records in this
    # repo ("live_state=ok control_state=ok disagrees=False... the cure under test was never
    # exercised"). So the module's own path is printed on every run and the gate reads it.
    print(f"  loaded from: {Path(__file__).resolve()}")
    print(report.provenance_table())
    if report.contracts is not None:
        print(f"  contracts: {len(report.contracts.checks)} check(s), "
              f"{len(report.contracts.failed)} failed")
    counts = report.counts()
    print("  provenance counts: " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    print(f"  SCAFFOLD: {report.is_scaffold()}")
    print(f"  VERDICT: {report.verdict}  clip_id={report.clip_id}")
    if report.transcript:
        print(f"  transcript ({len(report.transcript)} chars): {report.transcript[:220]}")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report.as_dict(), indent=2), encoding="utf-8")

    rc = 0
    failures: list[str] = []

    # THE EXIT CONTRACT, stated because it is easy to get backwards:
    #   * with `--expect V`, the run PASSES when the verdict IS V. A measured refusal is a
    #     valid expected outcome -- the same posture lane 2's audio gate takes ("a silent
    #     device is a valid green outcome"). Otherwise a gate could never assert that a
    #     refusal happens, only that a completion happens.
    #   * without `--expect`, the run passes only when the WHOLE chain completed.
    if args.expect:
        if report.verdict != args.expect:
            rc = 1
            failures.append(f"expected verdict {args.expect!r}, got {report.verdict!r}")
    elif not report.ok:
        rc = 1
        failures.append(f"chain verdict {report.verdict}: "
                        f"{report.refusal.message if report.refusal else 'incomplete'}")

    n_real = counts.get(Provenance.REAL, 0)
    if n_real < args.require_real_stages:
        rc = 1
        failures.append(f"only {n_real} REAL stage(s); {args.require_real_stages} required")
    # SCAFFOLD is a claim about a COMPLETED run. A chain that refused at stage 2 by design
    # never reached the stages that would have been real, so calling it a scaffold is a false
    # red -- MEASURED, and it is what the verifier's finding 1 exposed: relabelling `probe`
    # from REAL to REAL_SUBSTITUTE left the two early-refusal arms with zero REAL stages and
    # they failed as "SCAFFOLD" while behaving exactly right. Only a run that was supposed to
    # reach search can be a scaffold.
    if report.is_scaffold() and report.verdict == "ok":
        rc = 1
        failures.append("SCAFFOLD: the chain reported completion with no stage running REAL")
    elif report.is_scaffold():
        print(f"pipeline.chain: note: this run refused at "
              f"{report.verdict!r}, so it is thin by construction, not a scaffold")
    leaked = _db_contains(Path(args.db), args.forbid_token)
    if leaked:
        rc = 1
        failures.append(f"double text leaked into the index: {leaked} row(s)")
    if failures:
        for f in failures:
            print(f"pipeline.chain: FAIL {f}", file=sys.stderr)
        return rc or 1
    print(f"pipeline.chain: OK  verdict={report.verdict}  "
          f"real_stages={n_real}  double_stages={counts.get(Provenance.DOUBLE, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())