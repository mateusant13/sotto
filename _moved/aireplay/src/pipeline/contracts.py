"""contracts.py -- WHAT I NEED FROM THE OTHER LANES, spelled out, and checked against them.

================================================================================
WHY THIS FILE EXISTS
================================================================================
Every subsystem around this one is being written RIGHT NOW by lanes that cannot see
each other's work. The product's promise is "press a key, get the last N seconds,
with a transcript you can search" -- a CHAIN. Nobody else is proving the chain works
as a chain, so this file is the boundary that can lie quietly: a field name I
invent, a keyword a producer never accepted, a payload field the writer silently
ignores. `store.py:154` already warns about exactly that shape --

    "index: clip {clip_id}: ignoring unknown field(s) [...]"

-- a silently dropped field is how a column stays empty forever without anyone
noticing. So this module does not merely DECLARE the interfaces. It VERIFIES them,
by importing the real module and reading its real signature, and by reading the C++
header text for the fields no Python can introspect. A drifted producer makes this
file RED, loudly, at chain time.

================================================================================
THE RULE: A CONTRACT THAT DOES NOT MATCH THE PRODUCER IS THE DEFECT THIS PROJECT
KEEPS PAYING FOR.
================================================================================
Every signature below was captured with `inspect.signature` from the live tree on
2026-10-07 and is reproduced VERBATIM in `signature`. `check()` re-derives it and
compares. Nothing here is aspirational and nothing here is a wish.

THE TWO CONTRACTS THAT CANNOT BE CHECKED BY REFLECTION, AND WHAT I DO INSTEAD:
  * `CutResult` (src/capture/replay.h:65-82) is C++ and cannot be imported. I read
    the HEADER TEXT and match the member names, so a rename in C++ turns this RED.
  * The AAC elementary stream has NO producer at all. `mp4_writer` is video-only
    (receipt-16 section 7 specifies the audio `trak` as code to INSERT, never as an
    edit), so `aac_path` is NULL everywhere and the audio path has to come from
    somewhere else. That gap is declared as `CONTRACT_GAP`, not hidden.
"""

from __future__ import annotations

import inspect
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

__all__ = [
    "Provenance",
    "ContractCheck",
    "Contract",
    "CONTRACTS",
    "CONTRACT_GAPS",
    "ContractReport",
    "verify_contracts",
    "REPO_ROOT",
    "ASR_SAMPLE_RATE_HZ",
    "ASR_CHANNELS",
    "ASR_SAMPWIDTH",
    "SILENCE_PEAK_FLOOR",
    "SILENCE_FLOOR_PROVENANCE",
    "CUT_RESULT_FIELDS",
    "CUT_RESULT_TO_CLIP_PAYLOAD",
]

def _find_repo_root() -> Path:
    """The product root, found by LOOKING for it rather than by counting parents.

    MEASURED, and it is the reason this function exists. The control arm copies this whole
    package to a scratch directory and reverts the cure in the COPY. With the root computed
    as `parents[2]`, the copy resolves to `<scratch>/controlA`, every C++ header check fails
    on a path that does not exist, and the control goes RED **for the wrong reason** — the
    cure under test was never exercised at all. That is precisely the failure receipt-16
    section 10 records in this repo ("live_state=ok control_state=ok disagrees=False … the
    cure under test was, in that run, not exercised"), and a control that is red for an
    unrelated reason is worse than no control, because it looks like evidence.

    So: walk up until a directory actually contains the files the contracts name, and only
    then trust it. `SOTTO_PIPELINE_ROOT` overrides, for the case of a tree laid out elsewhere.
    """
    override = os.environ.get("SOTTO_PIPELINE_ROOT", "")
    here = Path(__file__).resolve()
    starts = [Path(override)] if override else []
    starts.append(here)
    starts.extend(here.parents)
    for cand in starts:
        try:
            base = cand if cand.name != "pipeline" else cand.parent
            if (base / "src" / "capture" / "replay.h").exists() and \
               (base / "src" / "asr" / "runner.py").exists():
                return base
            # also accept being handed `.../src` directly
            if (base / "capture" / "replay.h").exists() and (base / "asr" / "runner.py").exists():
                return base.parent
        except OSError:  # pragma: no cover - a permission error walking the tree
            continue
    # nothing found: fall back to the positional guess, and the checks will say so loudly
    return here.parents[2]


#: The product root. `src/pipeline/contracts.py` -> `src/pipeline` -> `src` -> root.
REPO_ROOT = _find_repo_root()
_SRC = REPO_ROOT / "src"


class Provenance:
    """How a stage was executed. A chain that hides this is a scaffold, not a proof."""

    #: the real, shipped module in this repo did the work
    REAL = "REAL"
    #: a real, working binary/tool doing the job of a producer that DOES NOT EXIST YET
    REAL_SUBSTITUTE = "REAL_SUBSTITUTE"
    #: a test double written by this lane -- the product did not do this
    DOUBLE = "DOUBLE"
    #: nothing ran; the stage was refused with a measurement
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class ContractCheck:
    """One verification of one contract. `ok` False is a DRIFT, not a soft warning."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class Contract:
    """One interface this chain needs from a lane this chain does not own.

    `signature` is the producer's REAL signature, captured 2026-10-07. `check()` is
    the re-derivation. `why` names what breaks if the payload is wrong, because a
    contract with no consequence is a comment.
    """

    key: str
    owner: str                       # which lane owns the producer
    producer: str                    # the file, as the repo names it
    symbol: str                      # the qualified name
    signature: str                   # VERBATIM from inspect.signature / the header
    payload: str                     # exactly what I hand it
    returns: str                     # exactly what I read back
    why: str                         # the concrete failure this prevents
    provenance_note: str = ""        # how it was captured

    # --- resolution -------------------------------------------------------------------------
    def resolve(self) -> Any:
        """Import the real object, or raise `LookupError` naming the producer.

        `index.*` is imported as a TOP-LEVEL module name, not as `index.store`: the rewrite
        DELETED `src/index/__init__.py`, so `import index.store` is not the entry point any
        more, and `search.py:28` does a bare `import store`. Both facts are the producer's
        shape, not a preference of this lane's.
        """
        import importlib
        import sys

        # `search.py:28` does a bare `import store`, so the package DIRECTORY must be on
        # sys.path. `src/index/__init__.py` was DELETED by the rewrite, so `index.store` is no
        # longer an importable dotted path. Import the FIRST component as a top-level module
        # and walk the rest by attribute -- which is how the producer itself is shaped.
        pkg_dir = str(_SRC / "index")
        if pkg_dir not in sys.path:
            sys.path.insert(0, pkg_dir)

        parts = self.symbol.split(".")
        root = parts[0]
        try:
            obj: Any = importlib.import_module(root)
        except ImportError as exc:
            raise LookupError(
                f"contract {self.key}: cannot import {root!r} from {pkg_dir} "
                f"(producer {self.producer}): {exc}") from exc
        for i, attr in enumerate(parts[1:], start=1):
            try:
                obj = getattr(obj, attr)
            except AttributeError:
                # A package's submodule is not an attribute until something imports it, so
                # `asr.runner` is invisible on a bare `import asr`. Import the dotted path
                # and retry -- this is what makes one walker serve BOTH conventions.
                dotted = ".".join(parts[: i + 1])
                try:
                    obj = importlib.import_module(dotted)
                except ImportError as exc:
                    raise LookupError(
                        f"contract {self.key}: cannot import {dotted!r} "
                        f"(producer {self.producer}): {exc}") from exc
        return obj

    def check(self) -> list[ContractCheck]:
        """Re-derive every claim this contract makes. Never raises; returns the checks."""
        out: list[ContractCheck] = []
        try:
            obj = self.resolve()
        except LookupError as exc:
            return [ContractCheck(f"{self.key}.resolves", False, str(exc))]

        out.append(ContractCheck(
            f"{self.key}.resolves", True, f"{self.symbol} resolved from {self.producer}"))

        if inspect.isfunction(obj) or inspect.ismethod(obj):
            try:
                live = str(inspect.signature(obj))
            except (TypeError, ValueError) as exc:  # a C function or a builtin
                out.append(ContractCheck(f"{self.key}.signature", False,
                                         f"cannot introspect {self.symbol}: {exc}"))
                return out
            norm_live = _normalise_signature(live)
            norm_want = _normalise_signature(self.signature)
            out.append(ContractCheck(
                f"{self.key}.signature", norm_live == norm_want,
                "signature matches" if norm_live == norm_want
                else f"DRIFT\n      declared: {self.signature}\n      producer: {live}"))
        return out

    def as_dict(self) -> dict:
        return {
            "key": self.key, "owner": self.owner, "producer": self.producer,
            "symbol": self.symbol, "signature": self.signature, "payload": self.payload,
            "returns": self.returns, "why": self.why,
            "captured": self.provenance_note,
        }


def _normalise_signature(text: str) -> str:
    """Whitespace- AND quoting-insensitive comparison.

    Every producer under `src/` uses `from __future__ import annotations` (PEP 563), so
    `inspect.signature` renders each annotation as a QUOTED string: `mode: 'str'` where the
    source says `mode: str`. Reporting that as a drift would make this file permanently RED
    over its own formatting, and a permanently-red check is a check nobody reads.

    THE BOUNDED LOSS, stated rather than hidden: dropping quotes also cannot distinguish
    `Union[str, Path]` from `str | Path`, nor `'str'` from `str`. Both spell the SAME type to
    this codebase, and what this check exists to catch is a RENAMED PARAMETER, a CHANGED
    DEFAULT, or a REMOVED KEYWORD -- all of which survive quote-stripping intact.
    Defaults are never normalised away: `max_s=0.0` -> `None` is a behaviour change that
    matters and would still be caught.
    """
    return re.sub(r"\s+", "", text).replace("'", "").replace('"', "")


# ==================================================================================
# THE CONTRACTS. Captured 2026-10-07 from the live tree with inspect.signature.
# ==================================================================================

CONTRACTS: tuple[Contract, ...] = (
    Contract(
        key="asr-transcribe",
        owner="lane 04/09 (src/asr)",
        producer="src/asr/runner.py:139",
        symbol="asr.runner.transcribe",
        signature="(cfg: TranscribeConfig, on_event: Callable[[dict], None] | None = None) -> dict",
        payload="TranscribeConfig(wav=<16 kHz mono PCM16>, model_dir=<repo>/models/"
                "parakeet-tdt-0.6b-v3-onnx, quantization='int8', provider='cpu', "
                "intra_op_num_threads=4, inter_op_num_threads=1, level=False)",
        returns="the `done` dict: keys `segments` (rows of {i,start,end,audio_s,wall_s,"
                "chars,text}), `n_segments`, `text`, `segment_mode`, `quantization`, "
                "`model_dir`, `rss_*`, `rtfx_*`. Fed VERBATIM to ingest_asr_done.",
        why="`store.ingest_asr_done` reads EXACTLY these keys (store.py:284-304). A renamed "
            "key here is a transcript that indexes as nothing, with no error anywhere.",
        provenance_note="inspect.signature(asr.runner.transcribe) on the live tree",
    ),
    Contract(
        key="asr-segment",
        owner="lane 04/09 (src/asr)",
        producer="src/asr/segment.py:119",
        symbol="asr.segment.segments_for_mode",
        signature="(x, mode: str = 'silence', max_segment_s: float = 15.0, "
                  "fixed_chunk_s: float = 10.0, sample_rate: int = 16000)",
        payload="x = float32 mono numpy array from asr.audio.read_slice",
        returns="[(start_s, end_s)] in SECONDS relative to x, overlapping by pad_s",
        why="The chain must call the SPLITTER itself to report a segment count before any "
            "inference happens -- a 0-segment clip is a MEASURED outcome (silence), and "
            "0.6 s is the drop threshold (segment.py:100), not an error.",
        provenance_note="inspect.signature(asr.segment.segments_for_mode)",
    ),
    Contract(
        key="asr-audio-read",
        owner="lane 04/09 (src/asr)",
        producer="src/asr/audio.py:64",
        symbol="asr.audio.read_slice",
        signature="(path: str | Path, offset_s: float = 0.0, max_s: float = 0.0)",
        payload="the extracted wav path, offset_s=0.0, max_s=<clip duration>",
        returns="float32 mono numpy array in [-1, 1]",
        why="`_check` (audio.py:53-61) RAISES on anything but 16 kHz mono PCM16. That "
            "refusal is the last line of defence, so my extractor must satisfy it or the "
            "chain dies here -- which is the correct place to die.",
        provenance_note="inspect.signature(asr.audio.read_slice)",
    ),
    Contract(
        key="index-connect",
        owner="lane 04 (src/index)",
        producer="src/index/store.py:38",
        symbol="index.store.connect",
        signature="(path: str | os.PathLike, *, create: bool = True) -> sqlite3.Connection",
        payload="a sqlite path under the gate's work dir, create=True",
        returns="a connection with schema.sql applied (idempotent, CREATE IF NOT EXISTS)",
        why="The index was REWRITTEN mid-flight while this lane was running: `schema.open_index` "
            "is GONE (schema.py -> schema.sql) and this is its replacement. A chain written "
            "against the old name fails to import, which is loud -- but only because the "
            "contract file checks it. This entry is the record of the rewrite.",
        provenance_note="inspect.signature(index.store.connect), re-read after the rewrite",
    ),
    Contract(
        key="index-upsert-video",
        owner="lane 04 (src/index)",
        producer="src/index/store.py:67",
        symbol="index.store.upsert_video",
        signature="(conn: sqlite3.Connection, *, content_key: str, path: str, size_bytes: int, "
                  "mtime_ns: int, duration_ms: int = 0, file_key: str | None = None, "
                  "codec: str | None = None, w: int | None = None, h: int | None = None, "
                  "fps: float | None = None, bitrate: int | None = None, "
                  "last_seen_scan: int | None = None, missing: int = 0, state: str = 'discovered') "
                  "-> int",
        payload="content_key = the whole-file SHA-256 of the clip (HEX, 64 chars -- the schema "
                "CHECKs the length, schema.sql:44), path, size_bytes, mtime_ns, duration_ms in "
                "MILLISECONDS, w/h/fps from the CutResult, state='recorded'",
        returns="the video row id (INTEGER), new or existing",
        why="IDENTITY IS `content_key`, NOT a minted clip_id and NOT the path (schema.sql:4-7). "
            "The old store keyed on a TEXT clip_id; the new one keys on a 64-char SHA-256, so "
            "a payload carrying `clip_id` is a payload this writer cannot accept. Keyword-only: "
            "a positional call raises TypeError.",
        provenance_note="inspect.signature(index.store.upsert_video) after the rewrite",
    ),
    Contract(
        key="index-upsert-segment",
        owner="lane 04 (src/index)",
        producer="src/index/store.py:140",
        symbol="index.store.upsert_segment",
        signature="(conn: sqlite3.Connection, *, video_id: int, start_ms: int, end_ms: int, "
                  "seg_id: int | None = None, n_visual: int = 0, n_speech: int = 0, "
                  "n_ocr: int = 0, state: str = 'pending') -> int",
        payload="video_id from upsert_video, start_ms/end_ms converted from the ASR row's "
                "SECONDS, n_speech=1, state='closed'",
        returns="the seg_id (INTEGER), new or existing",
        why="SECONDS IN, MILLISECONDS STORED, and the conversion happens in THIS chain because "
            "the writer no longer owns a `_ms()` boundary (the old store.py:95 did). The ASR "
            "counts in seconds; `segment.start_ms` is ms. Getting it wrong writes a clip's "
            "window at 1/1000 of its real position and every time filter silently misses.",
        provenance_note="inspect.signature(index.store.upsert_segment) after the rewrite",
    ),
    Contract(
        key="index-upsert-transcript",
        owner="lane 04 (src/index)",
        producer="src/index/store.py:163",
        symbol="index.store.upsert_transcript",
        signature="(conn: sqlite3.Connection, *, seg_id: int, text: str, text_norm: str, "
                  "start_ms: int = 0, producer: str = 'light', model_sha256: str | None = None) "
                  "-> None",
        payload="seg_id from upsert_segment, text = the ASR row's `text` VERBATIM, text_norm = "
                "the SAME text lowercased (schema.sql:151: 'The writer lowercases into "
                "text_norm'), producer = the engine tag",
        returns="None -- the FTS row is written by a TRIGGER, not by the caller",
        why="THE FTS ROW IS NOT THE CALLER'S JOB ANY MORE. schema.sql:173-186 carries triggers "
            "that mirror transcript -> text_fts on insert/update/delete. A chain that still "
            "writes text_fts by hand now writes it TWICE, and a chain that reads `text_norm` "
            "must supply it itself: this writer takes it as an argument.",
        provenance_note="inspect.signature(index.store.upsert_transcript) after the rewrite",
    ),
    Contract(
        key="index-search",
        owner="lane 04 (src/index)",
        producer="src/index/search.py:113",
        symbol="search.SearchIndex.search_text",
        signature="(self, query: str, *, k: int = 100) -> list[tuple[int, int, float]]",
        payload="one token taken from the REAL transcript",
        returns="[(seg_id, rank, -bm25)] from the FTS5 `text_fts` table",
        why="It is a METHOD on SearchIndex, not a module-level `search_text(con, ...)`. The old "
            "module function is gone. A malformed FTS5 expression returns [] rather than "
            "raising (search.py:126-127), so an empty result is NOT proof of a bad query -- "
            "the chain therefore asserts the clip came back, not merely that the call ran.",
        provenance_note="inspect.signature(search.SearchIndex.search_text) after the rewrite",
    ),
    Contract(
        key="index-import-shape",
        owner="lane 04 (src/index)",
        producer="src/index/search.py:28",
        symbol="search",
        signature="search.py line 28 reads `import store` (ABSOLUTE, not `from . import store`)",
        payload="`src/index/` itself must be on sys.path before `search` is imported",
        returns="otherwise: ModuleNotFoundError: No module named 'store'",
        why="MEASURED, and it is a real integration obstacle, not a style note. The old "
            "`index/__init__.py` is GONE from the tree, so `import index.search` no longer "
            "works; the package is only importable with `src/index` on sys.path. Anything that "
            "expects `index.open_index` or `index.ingest_clip` is calling an API that no longer "
            "exists. This chain adds `src/index` to sys.path and says so.",
        provenance_note="verified by import attempt after the rewrite; the error is verbatim",
    ),
)

# ==================================================================================
# THE C++ CONTRACT, and the one gap. Read from the HEADER TEXT, never invented.
# ==================================================================================

CUT_RESULT_FIELDS: tuple[str, ...] = (
    "ok", "path", "note", "frames_in_clip", "encoded_in_window", "captured_in_window",
    "expected_in_window", "ring_dropped_at_cut", "bytes", "base_qpc_ns", "cut_qpc_ns",
    "base_abs", "end_abs", "clip_seconds", "idr_pre_roll_ms", "wall_ms",
)

#: How each `CutResult` member becomes the `ingest_clip` mapping. This table is the
#: seam between C++ and the index, written down because C++ cannot import Python and
#: Python cannot import `CutResult`.
CUT_RESULT_TO_CLIP_PAYLOAD: dict[str, str] = {
    "path": "clip_path",          # replay.h:67 -> store.ClipRecord.clip_path
    "clip_seconds": "duration_s",  # replay.h:79 -> store.ClipRecord.duration_s (s in)
    "bytes": "size_bytes",         # replay.h:70 -> store.ClipRecord.size_bytes
    # `base_qpc_ns` (replay.h:75) + `base_abs` (replay.h:77) name the clip WINDOW START
    # in QPC ticks -- the axis `SearchFilter.since_s/until_s` filter on. It is NOT
    # epoch seconds and NOT stored as such: no producer on this box converts QPC to
    # epoch, so `started_at_s` is derived from the FILE mtime and said so.
}

#: Gaps I am NOT papering over. Each names who owns the fix.
CONTRACT_GAPS: tuple[dict, ...] = (
    {
        "gap": "AAC elementary stream (`aac_path`) has NO producer",
        "evidence": "src/capture/mp4_writer.h:16-24 is video-only; receipt-16 section 7 "
                    "specifies the audio `trak` as code to INSERT and explicitly did not "
                    "insert it. Measured: 8/8 sample clips carry no audio stream "
                    "(receipt-13 claim 2).",
        "owner": "the mp4_writer / replay lane",
        "consequence_here": "`aac_path` is NULL in every payload this chain writes, and "
                            "the chain's audio stage therefore cannot read audio out of a "
                            "clip this repo produced. It says so loudly instead.",
    },
    {
        "gap": "`CutResult` exposes QPC ticks, the index filters on epoch seconds",
        "evidence": "replay.h:75-78 gives base_qpc_ns/cut_qpc_ns/base_abs/end_abs; "
                    "store.py:31-33 wants `started_at_s` in epoch seconds.",
        "owner": "the trigger/replay lane + whoever owns the QPC->epoch base",
        "consequence_here": "this chain derives `started_at_s` from the clip file's mtime "
                            "and RECORDS that it did so (`started_at_s_source=mtime_ns`). "
                            "A mtime-derived time axis is a stand-in, not the product's.",
    },
    {
        "gap": "the `clip_id` mint is L1's, and this chain has no L1 to call",
        "evidence": "store.py:22 -- 'stable identity, L1's to mint'. The trigger lane "
                    "receipt-15 is the instant-cut lane.",
        "owner": "lane 15 (instant cut)",
        "consequence_here": "this chain mints a DETERMINISTIC id from the clip's content "
                            "hash, so a re-run is idempotent (that is the store's own "
                            "requirement, store.py:22-23). It is NOT the product's id "
                            "scheme and says so.",
    },
    {
        "gap": "WGC refuses every capture item on this box (E_ACCESSDENIED)",
        "evidence": "src/capture/replay.h:120-123 -- the OFFLINE cut path exists precisely "
                    "because WGC began refusing every capture item here.",
        "owner": "the capture lane",
        "consequence_here": "no stage of this chain can PRODUCE a clip on this host, so the "
                            "`capture` stage is a DOUBLE over a real clip already on disk. "
                            "The gate prints it as such.",
    },
)


def _check_cut_result() -> list[ContractCheck]:
    """The C++ contract, verified by reading the header TEXT.

    A C++ `struct` cannot be imported, so the honest check is textual: every member
    the chain maps must still be spelled in `src/capture/replay.h`. A rename there
    turns this RED instead of silently landing NULL in a column.
    """
    header = _SRC / "capture" / "replay.h"
    if not header.exists():
        return [ContractCheck("capture-cut-result.header", False,
                              f"header not found: {header}")]
    text = header.read_text(encoding="utf-8", errors="replace")
    out = [ContractCheck("capture-cut-result.header", True, f"read {header}")]
    missing = []
    for member in CUT_RESULT_FIELDS:
        # a member declaration looks like `    bool        ok = false;` or `double clip_seconds`
        if not re.search(rf"\b{re.escape(member)}\b", text):
            missing.append(member)
    out.append(ContractCheck(
        "capture-cut-result.members", not missing,
        f"all {len(CUT_RESULT_FIELDS)} CutResult members present in replay.h"
        if not missing else f"DRIFT: replay.h no longer declares {missing}"))
    for c_member, py_field in CUT_RESULT_TO_CLIP_PAYLOAD.items():
        out.append(ContractCheck(
            f"capture-cut-result.map.{py_field}", c_member in text and bool(py_field),
            f"{c_member} -> {py_field}"))
    return out


#: The ASR sink contract, and the ONE threshold this chain is not allowed to invent.
#: `kAudioSilencePeakFloor` is declared by the capture lane at
#: `src/capture/wasapi_audio.h:65` and is checked below against that header, so the
#: chain cannot quietly restate it with different digits.
ASR_SAMPLE_RATE_HZ = 16_000          # src/asr/constants.py:91 (SAMPLE_RATE)
ASR_CHANNELS = 1                     # src/asr/audio.py:57 refuses anything else
ASR_SAMPWIDTH = 2                    # src/asr/audio.py:54 (PCM_16)
SILENCE_PEAK_FLOOR = 1.0e-3          # src/capture/wasapi_audio.h:65 (kAudioSilencePeakFloor)
#: Why that floor, quoted from the header that measured it (wasapi_audio.h:59-65):
#: 8x above the 0.000122 digital-silence ceiling of a 22 s passive listen, and ~500x below
#: the 0.4999 an injected tone reached. A silent device is therefore a CORRECT outcome on
#: this box, and the chain says so instead of calling it a failure.
SILENCE_FLOOR_PROVENANCE = (
    "src/capture/wasapi_audio.h:59-65 — 0.000122 silence ceiling over a 22 s passive listen, "
    "0.4999 injected tone; the floor sits between them with an ~8x/~500x margin"
)


def _check_silence_floor() -> list[ContractCheck]:
    """The silence floor must still be spelled in the capture lane's header.

    This chain does not OWN the number. If the capture lane retunes it, the chain has to
    follow, not keep its own copy -- so the literal is checked against the header.
    """
    header = _SRC / "capture" / "wasapi_audio.h"
    if not header.exists():
        return [ContractCheck("capture-silence-floor.header", False, f"missing: {header}")]
    text = header.read_text(encoding="utf-8", errors="replace")
    literal_ok = re.search(r"kAudioSilencePeakFloor\s*=\s*1\.0e-3f", text) is not None
    return [
        ContractCheck("capture-silence-floor.header", True, f"read {header}"),
        ContractCheck(
            "capture-silence-floor.literal", literal_ok,
            f"kAudioSilencePeakFloor = 1.0e-3f present; this chain uses {SILENCE_PEAK_FLOOR}"
            if literal_ok else
            "DRIFT: wasapi_audio.h no longer declares kAudioSilencePeakFloor = 1.0e-3f — "
            "re-read the header before trusting this chain's silent-device verdict"),
        ContractCheck(
            "asr-format-contract.rate",
            bool(re.search(r"SAMPLE_RATE\s*=\s*16_000", (_SRC / "asr" / "constants.py")
                           .read_text(encoding="utf-8", errors="replace"))),
            "src/asr/constants.py still declares SAMPLE_RATE = 16_000"),
    ]


#: The extra, non-reflection checks. Same shape as Contract.check() returns.
EXTRA_CHECKS: tuple[tuple[str, Callable[[], list[ContractCheck]]], ...] = (
    ("capture-cut-result", _check_cut_result),
    ("capture-silence-floor", _check_silence_floor),
)


@dataclass
class ContractReport:
    """The verdict on every contract. `ok` False means the chain is built on sand."""

    checks: list[ContractCheck] = field(default_factory=list)
    gaps: tuple[dict, ...] = CONTRACT_GAPS

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failed(self) -> list[ContractCheck]:
        return [c for c in self.checks if not c.ok]

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "n_checks": len(self.checks),
            "n_failed": len(self.failed),
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
            "contracts": [c.as_dict() for c in CONTRACTS],
            "gaps": [dict(g) for g in self.gaps],
        }

    def table(self) -> str:
        lines = []
        for c in self.checks:
            lines.append(f"    [{'ok  ' if c.ok else 'FAIL'}] {c.name}: {c.detail}")
        return "\n".join(lines)


def verify_contracts() -> ContractReport:
    """Check EVERY declared interface against the live producer. Cheap, and it is the
    only thing standing between a renamed keyword and a chain that looks green."""
    report = ContractReport()
    for contract in CONTRACTS:
        report.checks.extend(contract.check())
    for _, fn in EXTRA_CHECKS:
        report.checks.extend(fn())
    return report