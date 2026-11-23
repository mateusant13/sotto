#!/usr/bin/env python3
"""Run the pinned FLEURS pt-BR cohort through Sotto's Redux Consumer.

Public output is aggregate-only. Hypotheses are written to a content-addressed
private cache for the reference scorer; no transcript is logged or printed.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import importlib
import importlib.metadata
import importlib.machinery
import importlib.util
import json
import math
import os
import re
import sys
import tempfile
import time
import types
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
MANIFEST_DEFAULT = ROOT / ".agent-work/asr-cache/fleurs/pt_br/b74b61db926bee40ba21ab385264b0e8cbc89d4d10f93a4c51bcb54e95f3033c.manifest.json"
MODEL_DEFAULT = WORKER / "models/parakeet-redux-onnx-int4"
SCORER_PATH = ROOT / "_main/asr-reference-score.py"
DEFAULT_CACHE = ROOT / ".agent-work/asr-cache/fleurs-gpu"
PINNED_MANIFEST_SHA256 = "b74b61db926bee40ba21ab385264b0e8cbc89d4d10f93a4c51bcb54e95f3033c"
REDUX_HF_REVISION = "1c285ba78d6f1880803f65355133a5ad3559a407"
REDUX_HF_TREE_SHA256 = "d4012cb7fba10b91855ebccd4be53aa3ac1e0f6ce324582b4371648b10bd95ee"
REDUX_CONTROL_HASHES = {
    "preprocessor.onnx": "3de5742f5780fc8615c1d883a2a60e28621ff13d2e20d24d76e94b9e4168445f",
    "encoder-model.onnx": "ade2c65c188776b3662db620a553ab82ac7e9ca11a7be6b696bcc5190f75382e",
    "vad-model.onnx": "18dfbe344307f9eda4735d4da1fe1cd6e3be27055a6c25b4a4a2e6fe0bffde50",
}
REDUX_CONTROL_NODES = {
    "preprocessor.onnx": {
        "node_sym_size_int_21": "Squeeze", "node_floordiv": "Div",
        "node_add_100": "Add",
    },
    "encoder-model.onnx": {
        "node_Concat_153": "Concat", "node_Concat_184": "Concat",
        "node_Concat_191": "Concat", "node_Concat_342": "Concat",
        "node_Concat_387": "Concat", "node_Concat_394": "Concat",
        "node_Concat_420": "Concat", "node_Concat_467": "Concat",
        "node_Reshape_151": "Reshape", "node_Reshape_188": "Reshape",
        "node_add_152": "Add", "node_add_38": "Add", "node_add_39": "Add",
        "node_add_8393": "Add", "node_add_93": "Add", "node_floordiv": "Div",
        "node_floordiv_1": "Div", "node_floordiv_2": "Div", "node_mul_6234": "Mul",
        "node_neg": "Neg", "node_sym_size_int_318": "Squeeze",
    },
    "vad-model.onnx": {
        "node_Concat_153": "Concat", "node_Reshape_151": "Reshape",
        "node_add_152": "Add", "node_add_38": "Add", "node_add_39": "Add",
        "node_add_93": "Add", "node_floordiv": "Div", "node_floordiv_1": "Div",
        "node_floordiv_2": "Div", "node_sym_size_int_28": "Squeeze",
    },
}
EXPECTED_SAMPLES = 20
THREAD_ENV = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
CORE_GRAPHS = frozenset(("preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx"))
ACOUSTIC_GRAPHS = CORE_GRAPHS | {"vad-model.onnx"}
CUDA_PROVIDER = "CUDAExecutionProvider"
CPU_EXECUTION_POLICY = "neural-cuda;pinned-shape-control-cpu"
HASH_READ_BYTES_PER_SECOND = 4 * 1024 * 1024
MAX_MODEL_FILES = 128
MAX_MODEL_BYTES = 2_000_000_000
MAX_JSONL_BYTES = 1024 * 1024
MAX_ROW_TEXT_BYTES = 256 * 1024
MAX_CACHE_BYTES = 2 * 1024 * 1024
MAX_MODEL_IDENTITY_BYTES = 64 * 1024
MAX_SMALL_MODEL_FILE_BYTES = 1024 * 1024
MAX_IDENTITY_FILE_BYTES = 32 * 1024 * 1024
MAX_SOUNDFILE_NATIVE_HASH_BYTES = 8 * 1024 * 1024
SCHEMA = "sotto-fleurs-redux-consumer-gpu-v3"
MODEL_IDENTITY_SCHEMA = "sotto-redux-model-identity-v1"
PROCESS_POOL_BUDGET = {
    "ort_intra_op": 1,
    "ort_inter_op": 1,
    "core_session_loader": 0,
    "integrity_hash": 0,
    "configured_total": 2,
}
NODE_ASSIGNMENT_TRACE_ENV = "SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"
SESSION_FAILURE_TRACE_ENV = "SOTTO_REDUX_ORT_SESSION_FAILURE_TRACE"
DIAGNOSTIC_CONFIG = {
    "node_assignment_trace": True,
    "environment_flag": NODE_ASSIGNMENT_TRACE_ENV,
    "ort_session_entry": "session.record_ep_graph_assignment_info=1",
    "readback_method": "get_provider_graph_assignment_info",
    "provider_policy": CPU_EXECUTION_POLICY,
    "requested_providers_by_graph": {
        "preprocessor.onnx": [CUDA_PROVIDER, "CPUExecutionProvider"],
        "encoder-model.onnx": [CUDA_PROVIDER, "CPUExecutionProvider"],
        "decoder_joint-model.onnx": [CUDA_PROVIDER],
        "vad-model.onnx": [CUDA_PROVIDER, "CPUExecutionProvider"],
    },
    "cpu_ep_fallback_key_by_graph": {
        "preprocessor.onnx": "0", "encoder-model.onnx": "0",
        "decoder_joint-model.onnx": "1", "vad-model.onnx": "0",
    },
    "production_latency_comparable": False,
}
GRAPH_NODE_COUNTS = {
    "preprocessor.onnx": 55,
    # Actual ORT 1.30 assignment readback is 1,713, including the same pinned
    # 21 CPU controls and 1,692 CUDA assignments.
    "encoder-model.onnx": 1713,
    "decoder_joint-model.onnx": 51,
    "vad-model.onnx": 101,
}
GRAPH_PROVIDER_NODE_COUNTS = {
    "preprocessor.onnx": {CUDA_PROVIDER: 52, "CPUExecutionProvider": 3},
    "encoder-model.onnx": {CUDA_PROVIDER: 1692, "CPUExecutionProvider": 21},
    "decoder_joint-model.onnx": {CUDA_PROVIDER: 51},
    "vad-model.onnx": {CUDA_PROVIDER: 91, "CPUExecutionProvider": 10},
}
RUNTIME_PACKAGE_FILES = {
    "onnxruntime": (
        "onnxruntime/__init__.py",
        "onnxruntime/capi/onnxruntime_inference_collection.py",
    ),
    "numpy": ("numpy/__init__.py",),
    "soundfile": ("soundfile.py",),
}
GPU_EXECUTION_EVIDENCE = (
    "diagnostic node-assignment trace enabled; neural nodes are CUDA and only the "
    "hash-pinned shape/control node maps use CPU EP; per-graph providers, node maps, "
    "and runtime fallback are read back; production latency is not comparable"
)

# These must be set before importing any project, numeric, audio or ORT module.
for _name in THREAD_ENV:
    os.environ[_name] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True


class Refusal(RuntimeError):
    pass


def _safe_exception_site(exc: BaseException) -> str:
    """Return bounded failure context without paths or exception payloads."""
    tb = exc.__traceback__
    graph_name = None
    redux_graphs = ACOUSTIC_GRAPHS
    cursor = tb
    while cursor is not None:
        frame = cursor.tb_frame
        if Path(frame.f_code.co_filename).name.lower() == "redux_live.py":
            graph = frame.f_locals.get("graph")
            try:
                candidate = Path(graph).name
            except (TypeError, ValueError, OSError):
                candidate = None
            if candidate in redux_graphs:
                graph_name = candidate
        cursor = cursor.tb_next
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if tb is None:
        return "unknown-site"
    code = tb.tb_frame.f_code
    label = "%s:%d in %s" % (Path(code.co_filename).name, tb.tb_lineno, code.co_name)
    if graph_name is not None:
        label += " graph=" + graph_name
    error_text = next((arg for arg in exc.args if isinstance(arg, str)
                       and len(arg) <= 16384), "")
    match = re.search(
        r"\[ONNXRuntimeError\]\s*:\s*(\d{1,4})\s*:\s*[A-Z_]+\s*:",
        error_text)
    if match is not None:
        label += " ort_code=" + match.group(1)
    attribute = getattr(exc, "name", None)
    if (isinstance(attribute, str) and len(attribute) <= 64
            and attribute.isascii() and attribute.isidentifier()):
        label += " attribute=" + attribute
    return label


def _safe_node_assignment_diagnostic(exc: BaseException) -> str | None:
    """Serialize only bounded ORT placement counts attached by Redux."""
    seen = set()
    current = exc
    for _ in range(6):
        if current is None or id(current) in seen:
            break
        seen.add(id(current))
        raw = getattr(current, "sotto_node_assignment_diagnostic", None)
        if isinstance(raw, dict):
            graph = raw.get("graph")
            if not isinstance(graph, str) or graph not in ACOUSTIC_GRAPHS:
                return None

            def count(name, *, nullable=False):
                value = raw.get(name)
                if nullable and value is None:
                    return None
                if (not isinstance(value, int) or isinstance(value, bool)
                        or value < 0 or value > 1_000_000):
                    raise ValueError("invalid placement count")
                return value

            def provider_counts(name):
                value = raw.get(name)
                if value is None:
                    return None
                if not isinstance(value, dict) or len(value) > 16:
                    raise ValueError("invalid provider count map")
                normalized = {}
                other = 0
                for provider, amount in value.items():
                    if (not isinstance(provider, str)
                            or not isinstance(amount, int)
                            or isinstance(amount, bool)
                            or amount < 0 or amount > 1_000_000):
                        raise ValueError("invalid provider count")
                    if provider in {CUDA_PROVIDER, "CPUExecutionProvider"}:
                        normalized[provider] = amount
                    else:
                        other += amount
                if other:
                    normalized["OtherExecutionProviders"] = other
                return dict(sorted(normalized.items()))

            try:
                readback_state = raw.get("readback_state")
                if readback_state not in {
                        "populated", "empty", "invalid-type", "oversized"}:
                    raise ValueError("invalid placement readback state")
                session_input_format = raw.get("session_input_format")
                if session_input_format not in {"onnx", "ort"}:
                    raise ValueError("invalid placement session format")
                optimized_model_output = raw.get("optimized_model_output")
                if not isinstance(optimized_model_output, bool):
                    raise ValueError("invalid optimized output flag")
                examples = raw.get("examples", [])
                if not isinstance(examples, list) or len(examples) > 4:
                    raise ValueError("invalid placement examples")
                safe_examples = []
                for item in examples:
                    if not isinstance(item, str) or len(item) > 600:
                        continue
                    if re.fullmatch(
                            r"(?:missing|extra):[A-Za-z0-9_.-]{1,256}:[A-Za-z0-9_.-]{1,80}"
                            r"|op:[A-Za-z0-9_.-]{1,256}:[A-Za-z0-9_.-]{1,80}>[A-Za-z0-9_.-]{1,80}",
                            item, flags=re.ASCII):
                        safe_examples.append(item)
                truncated = raw.get("examples_truncated", False)
                if not isinstance(truncated, bool):
                    raise ValueError("invalid placement truncation flag")
                trace_enabled = raw.get("trace_enabled")
                if not isinstance(trace_enabled, bool):
                    raise ValueError("invalid placement trace flag")
                normalized = {
                    "graph": graph,
                    "trace_enabled": trace_enabled,
                    "readback_state": readback_state,
                    "assignment_rows": count("assignment_rows", nullable=True),
                    "session_input_format": session_input_format,
                    "optimized_model_output": optimized_model_output,
                    "actual_total": count("actual_total", nullable=True),
                    "expected_total": count("expected_total", nullable=True),
                    "actual_providers": provider_counts("actual_providers"),
                    "expected_providers": provider_counts("expected_providers"),
                    "actual_cpu_nodes": count("actual_cpu_nodes", nullable=True),
                    "expected_cpu_nodes": count("expected_cpu_nodes"),
                    "missing_cpu_nodes": count("missing_cpu_nodes", nullable=True),
                    "extra_cpu_nodes": count("extra_cpu_nodes", nullable=True),
                    "changed_cpu_ops": count("changed_cpu_ops", nullable=True),
                    "examples": safe_examples,
                    "examples_truncated": truncated,
                }
            except (KeyError, TypeError, ValueError):
                return None
            return json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        current = current.__cause__ or current.__context__
    return None


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _safe_under(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError:
        raise Refusal("path escaped its permitted root") from None
    return candidate_resolved


def _hash_file(path: Path, *, paced: bool = False) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    started = time.perf_counter()
    with path.open("rb", buffering=0) as stream:
        while True:
            chunk = stream.read(256 * 1024)
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
            if paced:
                target = size / HASH_READ_BYTES_PER_SECOND
                remaining = target - (time.perf_counter() - started)
                if remaining > 0:
                    time.sleep(remaining)
    return digest.hexdigest(), size


def _verify_manifest(manifest_path: Path, expected_sha256: str,
                     required_count: int = EXPECTED_SAMPLES,
                     *, paced_hashes: bool = True):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256 or ""):
        raise Refusal("expected manifest SHA-256 is required")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise Refusal("pinned manifest is unavailable")
    if manifest_path.stat().st_size > 1024 * 1024:
        raise Refusal("manifest exceeds its size budget")
    raw = manifest_path.read_bytes()
    actual_manifest_sha = _sha(raw)
    if actual_manifest_sha != expected_sha256:
        raise Refusal("manifest SHA-256 mismatch")
    if required_count == EXPECTED_SAMPLES and expected_sha256 != PINNED_MANIFEST_SHA256:
        raise Refusal("only the pinned FLEURS cohort is accepted")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("manifest is not valid JSON") from None
    records = manifest.get("records") if isinstance(manifest, dict) else None
    if not isinstance(records, list) or len(records) != required_count:
        raise Refusal("manifest cohort size mismatch")
    transcript_sha = manifest.get("transcript_sha256")
    if not isinstance(transcript_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", transcript_sha):
        raise Refusal("transcript sidecar hash is invalid")
    sidecar = manifest_path.with_name(transcript_sha + ".trans.txt")
    if sidecar.is_symlink() or not sidecar.is_file():
        raise Refusal("transcript sidecar is unavailable")
    sidecar_sha, _ = _hash_file(sidecar)
    if sidecar_sha != transcript_sha:
        raise Refusal("transcript sidecar SHA-256 mismatch")

    seen = set()
    verified = []
    for record in records:
        if not isinstance(record, dict):
            raise Refusal("manifest row is invalid")
        sample_id = str(record.get("id", ""))
        audio_sha = record.get("audio_sha256")
        reference = record.get("reference")
        reference_sha = record.get("reference_sha256")
        try:
            audio_bytes = int(record.get("audio_bytes", 0))
        except (TypeError, ValueError, OverflowError):
            raise Refusal("audio size is invalid") from None
        if (not sample_id or sample_id in seen or not isinstance(audio_sha, str)
                or not re.fullmatch(r"[0-9a-f]{64}", audio_sha)
                or audio_bytes <= 0 or not isinstance(reference, str)
                or not isinstance(reference_sha, str)
                or _sha(reference.encode("utf-8")) != reference_sha):
            raise Refusal("manifest row identity is invalid")
        seen.add(sample_id)
        audio_path = manifest_path.with_name(audio_sha + ".wav")
        if audio_path.is_symlink() or not audio_path.is_file():
            raise Refusal("pinned audio file is unavailable")
        actual_audio_sha, actual_audio_bytes = _hash_file(audio_path, paced=paced_hashes)
        if actual_audio_sha != audio_sha or actual_audio_bytes != audio_bytes:
            raise Refusal("pinned audio content mismatch")
        try:
            with wave.open(str(audio_path), "rb") as audio:
                rate, frames = audio.getframerate(), audio.getnframes()
                if rate <= 0 or frames <= 0 or audio.getnchannels() <= 0:
                    raise Refusal("pinned WAV metadata is invalid")
                audio_s = frames / rate
        except (wave.Error, EOFError, OSError):
            raise Refusal("pinned audio WAV metadata is invalid") from None
        if not math.isfinite(audio_s) or audio_s <= 0:
            raise Refusal("pinned WAV duration is invalid")
        verified.append({
            "id": sample_id,
            "audio_path": audio_path,
            "audio_sha256": audio_sha,
            "audio_bytes": audio_bytes,
            "audio_s": audio_s,
        })
    if len(seen) != required_count:
        raise Refusal("manifest IDs are not one-to-one")
    return manifest, verified, actual_manifest_sha


def _redux_tree_path(model_dir: Path, revision: str = REDUX_HF_REVISION) -> Path:
    return model_dir / ".cache/huggingface/trees" / (revision + ".json")


def _model_identity_cache_path(model_dir: Path, cache_root: Path,
                               revision: str = REDUX_HF_REVISION,
                               tree_sha256: str = REDUX_HF_TREE_SHA256) -> Path:
    key = _sha(_canonical({
        "model_dir": str(model_dir.resolve()).casefold(),
        "revision": revision,
        "tree_sha256": tree_sha256,
        "schema": MODEL_IDENTITY_SCHEMA,
    }))
    return cache_root / "model-identities" / (key + ".json")


def _file_fingerprint(path: Path) -> dict[str, int]:
    stat = path.stat()
    file_id = int(getattr(stat, "st_ino", 0))
    if file_id <= 0:
        raise Refusal("filesystem does not expose a stable model-file ID")
    return {
        "size": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "ctime_ns": int(stat.st_ctime_ns),
        "device": int(stat.st_dev),
        "file_id": file_id,
    }


def _git_blob_and_sha256(path: Path) -> tuple[str, str, int]:
    size = path.stat().st_size
    if size > MAX_SMALL_MODEL_FILE_BYTES:
        raise Refusal("unhashed large model asset lacks a trusted LFS digest")
    content = path.read_bytes()
    if len(content) != size:
        raise Refusal("small model asset changed while reading")
    git_blob = hashlib.sha1(b"blob " + str(size).encode("ascii") + b"\0" + content).hexdigest()
    return git_blob, _sha(content), size


def _read_pinned_hf_tree(model_dir: Path, tree_path: Path,
                         revision: str, expected_tree_sha256: str) -> tuple[dict, str]:
    if tree_path.is_symlink() or not tree_path.is_file():
        raise Refusal("pinned Redux Hugging Face tree manifest is unavailable")
    if tree_path.stat().st_size > MAX_MODEL_IDENTITY_BYTES:
        raise Refusal("pinned Redux tree manifest exceeds its size budget")
    raw = tree_path.read_bytes()
    tree_sha = _sha(raw)
    if tree_sha != expected_tree_sha256:
        raise Refusal("pinned Redux tree manifest SHA-256 mismatch")
    try:
        tree = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("pinned Redux tree manifest is malformed") from None
    if tree.get("format_version") != 1 or not isinstance(tree.get("files"), dict):
        raise Refusal("pinned Redux tree manifest schema differs")
    return tree, tree_sha


def _read_hf_lfs_metadata(model_dir: Path, relative: str, revision: str,
                          expected_sha256: str) -> None:
    metadata_path = model_dir / ".cache/huggingface/download" / (relative + ".metadata")
    if metadata_path.is_symlink() or not metadata_path.is_file():
        raise Refusal("Redux LFS provenance metadata is unavailable")
    if metadata_path.stat().st_size > 4096:
        raise Refusal("Redux LFS provenance metadata exceeds its size budget")
    lines = metadata_path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 3 or lines[0] != revision or lines[1].lower() != expected_sha256:
        raise Refusal("Redux LFS provenance metadata differs from the pinned tree")
    try:
        if not math.isfinite(float(lines[2])) or float(lines[2]) <= 0:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise Refusal("Redux LFS provenance timestamp is invalid") from None


def _model_identity(model_dir: Path, identity_cache_path: Path, *,
                    tree_path: Path | None = None,
                    revision: str = REDUX_HF_REVISION,
                    expected_tree_sha256: str = REDUX_HF_TREE_SHA256,
                    hash_file_fn=_hash_file) -> dict:
    """Use the pinned HF LFS hashes once, then validate only file metadata.

    Small non-LFS assets are rehashed on each call. A changed LFS file fails
    closed until its identity cache is deliberately removed and the bytes are
    revalidated against the pinned SHA-256.
    """
    if model_dir.is_symlink() or not model_dir.is_dir():
        raise Refusal("Redux model directory is unavailable")
    if "parakeet-redux" not in str(model_dir).lower():
        raise Refusal("model path is not the Redux checkpoint")
    identity_cache_path.parent.mkdir(parents=True, exist_ok=True)
    tree_path = tree_path or _redux_tree_path(model_dir, revision)
    tree, tree_sha = _read_pinned_hf_tree(
        model_dir, tree_path, revision, expected_tree_sha256)
    tree_files = tree["files"]

    discovered = {}
    total_bytes = 0
    directory_count = 0
    excluded_dirs = {".cache", ".sotto-ort-cache", "__pycache__"}
    for current, dirs, files in os.walk(model_dir, topdown=True, followlinks=False):
        current_path = Path(current)
        kept_dirs = []
        for name in sorted(dirs):
            if name in excluded_dirs:
                continue
            directory = current_path / name
            if directory.is_symlink() or not directory.is_dir():
                raise Refusal("model tree contains a non-regular directory")
            kept_dirs.append(name)
            directory_count += 1
            if directory_count > MAX_MODEL_FILES:
                raise Refusal("model tree exceeds its inventory budget")
        dirs[:] = kept_dirs
        for name in sorted(files):
            path = current_path / name
            if name.endswith((".lock", ".tmp", ".partial")):
                raise Refusal("model tree contains an unfinished asset")
            if path.is_symlink() or not path.is_file():
                raise Refusal("model tree contains a non-regular file")
            relative = path.relative_to(model_dir).as_posix()
            fingerprint = _file_fingerprint(path)
            total_bytes += fingerprint["size"]
            if total_bytes > MAX_MODEL_BYTES or len(discovered) >= MAX_MODEL_FILES:
                raise Refusal("model tree exceeds its inventory budget")
            discovered[relative] = {"path": path, "fingerprint": fingerprint}
    required = {
        "config.json", "preprocessor.onnx", "encoder-model.onnx",
        "decoder_joint-model.onnx", "vad-model.onnx", "vocab.txt", "transcribe.py",
    }
    if not required.issubset(discovered):
        raise Refusal("Redux runtime model files are incomplete")
    lfs_records = {}
    expected_lfs = {}
    for relative, record in discovered.items():
        entry = tree_files.get(relative)
        if isinstance(entry, dict) and "lfs_sha256" in entry:
            expected_sha = entry.get("lfs_sha256")
            expected_size = entry.get("lfs_size")
            if (not isinstance(expected_sha, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", expected_sha)
                    or entry.get("size") != expected_size
                    or record["fingerprint"]["size"] != expected_size):
                raise Refusal("Redux LFS asset size/hash metadata differs")
            _read_hf_lfs_metadata(model_dir, relative, revision, expected_sha)
            expected_lfs[relative] = expected_sha
        elif relative in tree_files and relative != "transcribe.py":
            expected = tree_files[relative]
            if (not isinstance(expected, dict)
                    or record["fingerprint"]["size"] != expected.get("size")):
                raise Refusal("Redux small asset size differs from the pinned tree")

    root_key = _sha(_canonical({
        "model_dir": str(model_dir.resolve()).casefold(),
        "revision": revision,
        "tree_sha256": tree_sha,
        "schema": MODEL_IDENTITY_SCHEMA,
    }))
    cache = None
    if identity_cache_path.exists() or identity_cache_path.is_symlink():
        if identity_cache_path.is_symlink() or not identity_cache_path.is_file():
            raise Refusal("Redux model identity cache is not a regular file")
        if identity_cache_path.stat().st_size > MAX_MODEL_IDENTITY_BYTES:
            raise Refusal("Redux model identity cache exceeds its size budget")
        try:
            cache = json.loads(identity_cache_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise Refusal("Redux model identity cache is malformed") from None
        if (cache.get("schema") != MODEL_IDENTITY_SCHEMA
                or cache.get("root_key") != root_key
                or cache.get("revision") != revision
                or cache.get("tree_sha256") != tree_sha
                or not isinstance(cache.get("lfs_files"), dict)
                or set(cache["lfs_files"]) != set(expected_lfs)):
            raise Refusal("Redux model identity cache does not match the pinned tree")
        for relative, expected_sha in expected_lfs.items():
            cached = cache["lfs_files"].get(relative)
            current = discovered[relative]["fingerprint"]
            if (not isinstance(cached, dict)
                    or cached.get("sha256") != expected_sha
                    or cached.get("fingerprint") != current):
                raise Refusal("Redux weight metadata changed; revalidate the pinned model identity")

    weight_bytes_hashed = 0
    for relative, record in sorted(discovered.items()):
        path = record["path"]
        fingerprint = record["fingerprint"]
        if relative in expected_lfs:
            expected_sha = expected_lfs[relative]
            if cache is None:
                actual_sha, actual_size = hash_file_fn(path, paced=True)
                weight_bytes_hashed += actual_size
                if actual_sha != expected_sha or actual_size != fingerprint["size"]:
                    raise Refusal("Redux weight bytes do not match the pinned LFS digest")
            file_sha = expected_sha
            lfs_records[relative] = {"sha256": expected_sha, "fingerprint": fingerprint}
        else:
            if fingerprint["size"] > MAX_SMALL_MODEL_FILE_BYTES:
                raise Refusal("unmanifested large Redux asset is not accepted")
            git_entry = tree_files.get(relative)
            if relative != "transcribe.py" and isinstance(git_entry, dict) and "blob_id" in git_entry:
                git_sha, file_sha, size = _git_blob_and_sha256(path)
                if git_sha != git_entry["blob_id"] or size != git_entry.get("size"):
                    raise Refusal("Redux small asset differs from its pinned Git blob")
            else:
                file_sha, size = _hash_file(path)
                if size != fingerprint["size"]:
                    raise Refusal("Redux small asset changed while hashing")
        record["sha256"] = file_sha

    cache_hit = cache is not None
    if cache is None:
        cache_payload = {
            "schema": MODEL_IDENTITY_SCHEMA,
            "root_key": root_key,
            "revision": revision,
            "tree_sha256": tree_sha,
            "lfs_files": lfs_records,
        }
        _atomic_write(identity_cache_path, _canonical(cache_payload) + b"\n")
    content_records = [
        (relative, record["fingerprint"]["size"], record["sha256"])
        for relative, record in sorted(discovered.items())
    ]
    model_sha = _sha(_canonical({
        "schema": MODEL_IDENTITY_SCHEMA,
        "revision": revision,
        "tree_sha256": tree_sha,
        "files": content_records,
    }))
    return {
        "sha256": model_sha,
        "bytes": total_bytes,
        "files": len(discovered),
        "cache_hit": cache_hit,
        "weight_bytes_hashed": weight_bytes_hashed,
    }


def _path_identity(path: Path) -> dict:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise Refusal("a source or runtime identity input is unavailable")
    if path.stat().st_size > MAX_IDENTITY_FILE_BYTES:
        raise Refusal("a source or runtime identity input exceeds its size budget")
    path = path.resolve()
    digest, size = _hash_file(path)
    return {"path": str(path), "size": size, "sha256": digest}


def _redux_import_search_path(model_dir: Path) -> list[str]:
    search_path = list(sys.path)
    reference_dir = WORKER / "models" / "parakeet-redux-reference"
    # Match OnnxBackend's ordered insert(0, candidate) operations exactly.
    for candidate in (str(Path(model_dir).resolve()), str(reference_dir.resolve())):
        if candidate not in search_path:
            search_path.insert(0, candidate)
    return search_path


def _resolve_transcribe_path(model_dir: Path) -> Path:
    """Resolve the module import will use without importing model/runtime code."""
    loaded = sys.modules.get("transcribe")
    if loaded is not None:
        origin = getattr(loaded, "__file__", None)
        if not origin:
            raise Refusal("preloaded transcribe module has no stable file origin")
        path = Path(origin)
        if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".py":
            raise Refusal("preloaded transcribe module is not a source file")
        return path.resolve()

    search_path = _redux_import_search_path(model_dir)
    try:
        spec = importlib.machinery.PathFinder.find_spec("transcribe", search_path)
    except (ImportError, OSError, ValueError):
        spec = None
    origin = getattr(spec, "origin", None) if spec is not None else None
    if not origin:
        raise Refusal("the transcribe module selected by Redux is unavailable")
    path = Path(origin)
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".py":
        raise Refusal("the transcribe module selected by Redux is not a source file")
    return path.resolve()


def _code_identity(model_dir: Path | None = None) -> dict[str, dict]:
    model_dir = Path(model_dir or MODEL_DEFAULT).resolve()
    transcribe_path = _resolve_transcribe_path(model_dir)
    paths = {
        "runner": Path(__file__),
        "consumer": WORKER / "audio_queue_consumer.py",
        "redux": WORKER / "redux_live.py",
        "sotto_worker": WORKER / "sotto_worker.py",
        "cuda_bootstrap": WORKER / "ort_cuda_runtime.py",
        "engine_policy": WORKER / "engine_policy.py",
        "scorer": SCORER_PATH,
        "transcribe": transcribe_path,
    }
    return {label: _path_identity(path) for label, path in paths.items()}


def _runtime_identity(ort_distribution: str, model_dir: Path | None = None, *,
                      distribution_loader=None,
                      include_import_origins: bool = True,
                      include_provider_packages: bool = True,
                      provider_distributions_loader=None) -> dict:
    """Fingerprint source-level identities of the runtime packages used by this route."""
    distribution_loader = distribution_loader or importlib.metadata.distribution
    selected = {
        "onnxruntime": str(ort_distribution),
        "numpy": "numpy",
        "soundfile": "soundfile",
    }
    result = {
        "python": {
            "implementation": sys.implementation.name,
            "version": list(sys.version_info[:3]),
            "executable": str(Path(sys.executable).resolve()),
            "platform": sys.platform,
            "os_name": os.name,
        },
        "provider_environment": {
            "path_sha256": _sha(os.environ.get("PATH", "").encode("utf-8")),
            "cuda_path": os.environ.get("CUDA_PATH", ""),
            "cuda_home": os.environ.get("CUDA_HOME", ""),
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
        },
        "packages": {},
    }
    imported_modules = {
        "onnxruntime": "onnxruntime",
        "numpy": "numpy",
        "soundfile": "soundfile",
    }
    for label, package_name in selected.items():
        try:
            distribution = distribution_loader(package_name)
        except importlib.metadata.PackageNotFoundError:
            raise Refusal("a required runtime package identity is unavailable") from None
        root = Path(distribution.locate_file("")).resolve()
        sources = {}
        for relative in RUNTIME_PACKAGE_FILES[label]:
            path = Path(distribution.locate_file(relative))
            if path.is_file() and not path.is_symlink():
                sources[relative] = _path_identity(path)
        if not sources:
            raise Refusal("a required runtime package source identity is unavailable")
        package_row = {
            "distribution": str(distribution.metadata.get("Name") or package_name),
            "version": str(distribution.version),
            "root": str(root),
            "sources": sources,
        }
        package_row["native_files"] = _runtime_native_file_identity(
            distribution, label)
        if include_import_origins:
            module_name = imported_modules[label]
            module = sys.modules.get(module_name)
            origin = getattr(module, "__file__", None) if module is not None else None
            if not origin:
                try:
                    spec = importlib.machinery.PathFinder.find_spec(
                        module_name, _redux_import_search_path(
                            Path(model_dir or MODEL_DEFAULT).resolve()))
                except (ImportError, OSError, ValueError):
                    spec = None
                origin = getattr(spec, "origin", None) if spec is not None else None
            if not origin:
                raise Refusal("the selected runtime module import origin is unavailable")
            import_origin = _path_identity(Path(origin))
            expected_relative = RUNTIME_PACKAGE_FILES[label][0]
            if import_origin["path"] != sources[expected_relative]["path"]:
                raise Refusal("a runtime module is shadowed outside its package distribution")
            package_row["import_origin"] = import_origin
        result["packages"][label] = package_row
    result["cuda_provider_dependencies"] = (
        _cuda_provider_dependency_identity(
            distributions_loader=provider_distributions_loader)
        if include_provider_packages else [])
    return result


def _cuda_provider_dependency_identity(*, distributions_loader=None) -> list[dict]:
    """Fingerprint installed Torch/NVIDIA DLL candidates without importing them."""
    rows = []
    binary_count = 0
    distributions_loader = distributions_loader or importlib.metadata.distributions
    try:
        distributions = distributions_loader()
        for distribution in distributions:
            name = str(distribution.metadata.get("Name") or "").strip()
            normalized = name.lower().replace("_", "-")
            if normalized != "torch" and not normalized.startswith("nvidia-"):
                continue
            if len(rows) >= 64:
                raise Refusal("CUDA provider package inventory exceeds its bound")
            root = Path(distribution.locate_file("")).resolve()
            files = distribution.files or ()
            dll_rows = []
            for relative in files:
                if Path(str(relative)).suffix.lower() not in (".dll", ".so", ".dylib"):
                    continue
                path = Path(distribution.locate_file(relative))
                try:
                    stat = path.stat()
                except OSError:
                    continue
                dll_rows.append({
                    "path": str(path.resolve()),
                    "size": int(stat.st_size),
                    "mtime_ns": int(stat.st_mtime_ns),
                })
                binary_count += 1
                if binary_count > 512:
                    raise Refusal("CUDA provider DLL inventory exceeds its bound")
            package_row = {
                "distribution": name,
                "version": str(distribution.version),
                "root": str(root),
                "dll_candidates": sorted(dll_rows, key=lambda item: item["path"].casefold()),
            }
            source_relative = "torch/__init__.py" if normalized == "torch" else None
            if source_relative:
                source_path = Path(distribution.locate_file(source_relative))
                if source_path.is_file():
                    package_row["source"] = _path_identity(source_path)
            rows.append(package_row)
    except Refusal:
        raise
    except Exception:
        raise Refusal("CUDA provider package inventory could not be identified") from None
    rows.sort(key=lambda item: (item["distribution"].lower(), item["root"].casefold()))
    return rows


def _runtime_native_file_identity(distribution, package_label: str) -> list[dict]:
    """Fingerprint the native extension/decoder files that affect this route."""
    candidates = []
    for relative in distribution.files or ():
        path_text = str(relative).replace("\\", "/")
        basename = Path(path_text).name.lower()
        suffix = Path(path_text).suffix.lower()
        if package_label == "onnxruntime":
            match = ("onnxruntime" in basename
                     and suffix in (".dll", ".pyd", ".so", ".dylib"))
        elif package_label == "numpy":
            match = ("_multiarray_umath" in basename
                     and suffix in (".dll", ".pyd", ".so", ".dylib"))
        else:
            match = ("libsndfile" in basename
                     and suffix in (".dll", ".pyd", ".so", ".dylib"))
        if match:
            candidates.append(relative)
    if len(candidates) > 64:
        raise Refusal("runtime native-file identity exceeds its entry bound")
    rows = []
    for relative in sorted(candidates, key=lambda item: str(item).casefold()):
        path = Path(distribution.locate_file(relative))
        try:
            stat = path.stat()
        except OSError:
            continue
        row = {
            "path": str(path.resolve()),
            "size": int(stat.st_size),
            "mtime_ns": int(stat.st_mtime_ns),
        }
        if package_label == "soundfile" and stat.st_size <= MAX_SOUNDFILE_NATIVE_HASH_BYTES:
            row["sha256"] = _path_identity(path)["sha256"]
        rows.append(row)
    return rows


def _build_run_identity(*, manifest_sha: str, rows: list[dict],
                        model_identity: dict, source_identity: dict,
                        runtime_identity: dict,
                        diagnostic_config: dict | None = None) -> dict:
    return {
        "schema": SCHEMA,
        "manifest_sha256": manifest_sha,
        "audio": [(row["id"], row["audio_sha256"], row["audio_bytes"])
                  for row in rows],
        "model_sha256": model_identity["sha256"],
        "model_bytes": model_identity["bytes"],
        "model_files": model_identity["files"],
        "source_identity": source_identity,
        "runtime_identity": runtime_identity,
        "route": "Consumer.transcribe -> Redux OnnxBackend",
        "device": "cuda-neural; pinned-cpu-shape-control",
        "numeric_thread_environment": 1,
        "process_pool_budget": PROCESS_POOL_BUDGET,
        "diagnostic_config": dict(diagnostic_config or DIAGNOSTIC_CONFIG),
        "core_session_loader_workers": 0,
        "integrity_hash_workers": 0,
        "window_s": 3.0,
        "step_s": 3.0,
    }


def _validate_engine(engine, *, require_vad: bool) -> None:
    if str(getattr(engine, "device", "")).lower() != "cuda":
        raise Refusal("engine device readback is not CUDA")
    if getattr(engine, "cpu_execution_policy", None) != CPU_EXECUTION_POLICY:
        raise Refusal("engine CPU execution policy differs from the pinned graph exception")
    providers = getattr(engine, "provider_readback", None)
    policy = getattr(engine, "thread_policy", None)
    if not isinstance(providers, dict) or not isinstance(policy, dict):
        raise Refusal("engine provider/thread readbacks are missing")
    graph_names = set(providers)
    if (not CORE_GRAPHS.issubset(graph_names)
            or graph_names != ACOUSTIC_GRAPHS):
        raise Refusal("acoustic graph readback set is incomplete or unexpected")
    redux_module = sys.modules.get("redux_live")
    if redux_module is not None:
        live_allowlist = getattr(redux_module, "REDUX_CONTROL_GRAPH_ALLOWLIST", None)
        expected_allowlist = {
            name: (REDUX_CONTROL_HASHES[name], REDUX_CONTROL_NODES[name])
            for name in REDUX_CONTROL_HASHES
        }
        if live_allowlist != expected_allowlist:
            raise Refusal("Redux graph/control-node allowlist differs from its pinned values")
    options = policy.get("session_options_readback")
    if not isinstance(options, dict) or set(options) != graph_names:
        raise Refusal("per-graph session-option readbacks are incomplete")
    for graph in sorted(graph_names):
        actual = providers.get(graph)
        if (not isinstance(actual, (tuple, list)) or not actual
                or actual[0] != CUDA_PROVIDER
                or len(set(actual)) != len(actual)
                or any(name not in (CUDA_PROVIDER, "CPUExecutionProvider") for name in actual)):
            raise Refusal("CUDA is not the primary registered acoustic provider")
        row = options.get(graph)
        expected_requested = DIAGNOSTIC_CONFIG["requested_providers_by_graph"][graph]
        expected_cpu_fallback = DIAGNOSTIC_CONFIG[
            "cpu_ep_fallback_key_by_graph"][graph]
        requested = (row.get("requested_provider_names")
                     if isinstance(row, dict) else None)
        if (not isinstance(row, dict)
                or row.get("disable_cpu_ep_fallback") != expected_cpu_fallback
                or requested != expected_requested
                or row.get("runtime_fallback_disabled") is not True
                or row.get("intra_op_threads") != 1
                or row.get("inter_op_threads") != 1
                or row.get("use_per_session_threads") is not False
                or row.get("execution_mode_sequential") is not True
                or row.get("intra_op_spinning") != "0"
                or row.get("inter_op_spinning") != "0"
                or row.get("node_assignment_trace") is not True):
            raise Refusal("per-graph CPU/runtime fallback or thread readback is unsafe")
    node_assignments = _normalize_node_assignment_readback(
        getattr(engine, "node_assignment_readback", None), graph_names)
    if (policy.get("node_assignment_trace") is not True
            or policy.get("node_assignment_readback") != node_assignments):
        raise Refusal("diagnostic node-assignment trace is absent or inconsistent")
    control_readback = getattr(engine, "control_hash_readback", None)
    base_controls = {"preprocessor.onnx", "encoder-model.onnx"}
    allowed_controls = base_controls | {"vad-model.onnx"}
    if (not isinstance(control_readback, dict)
            or set(control_readback) != allowed_controls):
        raise Refusal("Redux control-graph hash readback set is incomplete or unexpected")
    for graph, row in control_readback.items():
        if (not isinstance(row, dict)
                or row.get("sha256") != REDUX_CONTROL_HASHES[graph]
                or row.get("verified_before_session_return") is not True
                or row.get("verification") not in {
                    "source-sha256", "source-stat-and-ort-cache-sha256"
                }):
            raise Refusal("Redux control-graph pinned hash was not verified")
    runtime_fallback = policy.get("runtime_fallback_readback")
    if (not isinstance(runtime_fallback, dict)
            or set(runtime_fallback) != graph_names
            or any(value is not True for value in runtime_fallback.values())):
        raise Refusal("runtime fallback readback is missing or enabled")
    environment = policy.get("environment")
    if not isinstance(environment, dict) or any(environment.get(name) != "1" for name in THREAD_ENV):
        raise Refusal("numeric thread environment readback is not one")
    budget = policy.get("process_pool_budget")
    expected_budget = dict(PROCESS_POOL_BUDGET)
    if (not isinstance(budget, dict)
            or any(budget.get(key) != value for key, value in expected_budget.items())
            or budget.get("scope") != "configured pools; OS thread IDs are not inferred"):
        raise Refusal("engine process pool budget readback is missing or inaccurate")
    helpers = policy.get("helper_execution_readback")
    if (not isinstance(helpers, dict)
            or helpers.get("core_session_loader") != "caller-thread"
            or helpers.get("integrity_hash") != "caller-thread"
            or helpers.get("integrity_hash_executor_created") is not False):
        raise Refusal("Redux helper execution readback is not fully serial")
    if (policy.get("ort_global_intra_op_threads") != 1
            or policy.get("ort_global_inter_op_threads") != 1
            or policy.get("ort_intra_op_total") != 1
            or policy.get("ort_inter_op_total") != 1
            or policy.get("ort_per_session_pools") is not False
            or policy.get("ort_shared_global_pool") is not True
            or policy.get("ort_execution_mode") != "ORT_SEQUENTIAL"
            or policy.get("ort_spinning") is not False
            or policy.get("core_session_loader_workers") != 0
            or policy.get("integrity_hash_workers") != 0
            or policy.get("ort_intra_op_sessions") != len(graph_names)
            or policy.get("ort_inter_op_sessions") != len(graph_names)):
        raise Refusal("engine configured process pool budget is not two-thread sequential")


def _normalize_node_assignment_readback(assignments, graph_names=None) -> dict:
    """Require exact pinned CPU control nodes and CUDA placement for all others."""
    expected_graphs = set(graph_names or ACOUSTIC_GRAPHS)
    if expected_graphs != set(ACOUSTIC_GRAPHS):
        raise Refusal("Redux node-assignment graph set is incomplete")
    if not isinstance(assignments, dict) or set(assignments) != expected_graphs:
        raise Refusal("Redux per-graph node-assignment readback is missing")
    normalized = {}
    for graph in sorted(expected_graphs):
        info = assignments[graph]
        if (not isinstance(info, dict)
                or info.get("method") != "get_provider_graph_assignment_info"):
            raise Refusal("Redux graph/node assignment method is unavailable")
        providers = info.get("providers")
        cpu_nodes = info.get("cpu_nodes")
        total = info.get("total_nodes")
        if (not isinstance(providers, dict) or not providers or len(providers) > 32
                or not isinstance(total, int) or isinstance(total, bool)
                or total < 1 or total > 1_000_000):
            raise Refusal("Redux graph/node assignment counts are invalid")
        if any(not isinstance(name, str) or not name or len(name) > 80
               or not isinstance(count, int) or isinstance(count, bool)
               or count < 0 or count > 1_000_000 for name, count in providers.items()):
            raise Refusal("Redux graph/node provider counts are invalid")
        if (not isinstance(cpu_nodes, dict) or len(cpu_nodes) > 64
                or any(not isinstance(name, str) or not name or len(name) > 256
                       or not isinstance(op, str) or not op or len(op) > 80
                       for name, op in cpu_nodes.items())):
            raise Refusal("Redux CPU control-node identity map is invalid")
        expected_total = GRAPH_NODE_COUNTS[graph]
        expected_provider_counts = GRAPH_PROVIDER_NODE_COUNTS[graph]
        expected_cpu_nodes = REDUX_CONTROL_NODES.get(graph, {})
        if (total != expected_total or providers != expected_provider_counts
                or cpu_nodes != expected_cpu_nodes):
            raise Refusal("Redux graph contains unpinned CPU, unknown, or missing nodes")
        normalized[graph] = {
            "providers": dict(sorted(providers.items())),
            "cpu_nodes": dict(sorted(cpu_nodes.items())),
            "total_nodes": total,
            "method": "get_provider_graph_assignment_info",
        }
    return normalized


def _validate_loaded_sources(source_identity: dict | None, *,
                            loaded_modules: dict | None = None,
                            required_labels=()) -> None:
    required = set(required_labels)
    if source_identity is None:
        if required:
            raise Refusal("required route source identity is unavailable")
        return
    explicit_modules = {} if loaded_modules is None else dict(loaded_modules)
    module_names = {
        "consumer": ("audio_queue_consumer",),
        "redux": ("redux_live",),
        "sotto_worker": ("sotto_worker",),
        "cuda_bootstrap": ("ort_cuda_runtime", "worker.ort_cuda_runtime"),
        "engine_policy": ("engine_policy", "worker.engine_policy"),
        "scorer": ("sotto_fleurs_reference_score",),
        "transcribe": ("transcribe",),
    }
    if not required.issubset(module_names):
        raise Refusal("required route source label is unknown")
    missing_identity = required.difference(source_identity)
    if missing_identity:
        raise Refusal(
            "required route source identity is missing: "
            + sorted(missing_identity)[0])
    for label, aliases in module_names.items():
        if label not in source_identity:
            continue
        if label in explicit_modules:
            loaded = explicit_modules[label]
        else:
            loaded = next((sys.modules[name] for name in aliases
                           if name in sys.modules), None)
        if loaded is None:
            if label in required:
                raise Refusal(
                    "required loaded route module identity is unavailable: " + label)
            continue
        expected = source_identity.get(label)
        origin = getattr(loaded, "__file__", None) if loaded is not None else None
        if not isinstance(expected, dict) or not origin:
            raise Refusal(
                "a loaded route module identity is unavailable: " + label)
        if _path_identity(Path(origin)) != expected:
            raise Refusal(
                "a loaded route module differs from the content-addressed run key: "
                + label)


def _validate_runtime_modules(runtime_identity: dict | None, *, preload_audio: bool,
                              require_ort_loaded: bool = False) -> None:
    if runtime_identity is None:
        return
    packages = runtime_identity.get("packages")
    if not isinstance(packages, dict):
        raise Refusal("runtime package identities are missing")
    for label, module_name in (("onnxruntime", "onnxruntime"),
                               ("numpy", "numpy"), ("soundfile", "soundfile")):
        package = packages.get(label)
        expected = package.get("import_origin") if isinstance(package, dict) else None
        if not isinstance(expected, dict):
            raise Refusal("runtime module import identity is missing")
        module = sys.modules.get(module_name)
        if module is None and preload_audio and label in {"numpy", "soundfile"}:
            try:
                module = importlib.import_module(module_name)
            except Exception:
                raise Refusal("a required audio runtime module could not be imported") from None
        if module is None:
            if label == "onnxruntime" and require_ort_loaded:
                raise Refusal("ONNX Runtime was not loaded by the Redux engine")
            try:
                spec = importlib.machinery.PathFinder.find_spec(module_name, sys.path)
            except (ImportError, OSError, ValueError):
                spec = None
            origin = getattr(spec, "origin", None) if spec is not None else None
            if not origin or _path_identity(Path(origin)) != expected:
                raise Refusal("a selected runtime module differs from its cache identity")
        else:
            origin = getattr(module, "__file__", None)
            if not origin or _path_identity(Path(origin)) != expected:
                raise Refusal("an imported runtime module differs from its cache identity")


def _validate_result_row(row, expected) -> None:
    if (not isinstance(row, dict) or row.get("completed") is not True
            or row.get("id") != expected["id"]
            or row.get("audio_sha256") != expected["audio_sha256"]
            or row.get("audio_bytes") != expected["audio_bytes"]
            or row.get("audio_s") != expected["audio_s"]
            or not isinstance(row.get("text"), str)
            or _sha(row["text"].encode("utf-8")) != row.get("text_sha256")
            or row.get("state") not in ("done", "empty")):
        raise Refusal("cached completed row identity is invalid")
    text_size = len(row["text"].encode("utf-8"))
    if text_size > MAX_ROW_TEXT_BYTES:
        raise Refusal("cached transcript row exceeds its size budget")
    if (row["state"] == "empty") != (row["text"] == ""):
        raise Refusal("cached row state does not match its transcript digest")
    for key in ("consumer_s", "audio_s"):
        value = row.get(key)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise Refusal("cached row timing is invalid")
    if row.get("inference_s") != row.get("consumer_s"):
        raise Refusal("cached scorer timing differs from Consumer wall time")


def _read_resume(path: Path, expected_rows: list[dict]) -> dict[str, dict]:
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file():
        raise Refusal("private cache result is not a regular file")
    raw = path.read_bytes()
    if len(raw) > MAX_JSONL_BYTES:
        raise Refusal("private cache result exceeds its size budget")
    expected_by_id = {row["id"]: row for row in expected_rows}
    complete = {}
    try:
        lines = raw.decode("utf-8").splitlines()
        for line in lines:
            if not line.strip():
                raise Refusal("private cache contains a blank row")
            row = json.loads(line)
            sample_id = row.get("id") if isinstance(row, dict) else None
            if sample_id not in expected_by_id or sample_id in complete:
                raise Refusal("private cache IDs are not one-to-one")
            _validate_result_row(row, expected_by_id[sample_id])
            complete[sample_id] = row
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("private cache JSONL is malformed") from None
    return complete


def _dir_bytes(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    if path.is_symlink() or not path.is_dir():
        raise Refusal("content-addressed result path is not a directory")
    for child in path.iterdir():
        if child.is_symlink() or not child.is_file():
            raise Refusal("cache directory contains an unexpected artifact")
        total += child.stat().st_size
    return total


def _atomic_write(path: Path, raw: bytes) -> None:
    if len(raw) > MAX_JSONL_BYTES and path.name == "hypotheses.jsonl":
        raise Refusal("hypothesis file exceeds its size budget")
    if path.name == "score.json" and len(raw) > 64 * 1024:
        raise Refusal("aggregate report exceeds its size budget")
    if path.name == "ready.json" and len(raw) > 64 * 1024:
        raise Refusal("readiness receipt exceeds its size budget")
    temp_path = path.with_name(path.name + ".tmp")
    if temp_path.exists() or temp_path.is_symlink():
        raise Refusal("stale atomic-write temporary exists")
    old_size = path.stat().st_size if path.is_file() else 0
    if _dir_bytes(path.parent) - old_size + len(raw) + old_size > MAX_CACHE_BYTES:
        raise Refusal("content-addressed cache exceeds its size budget")
    try:
        with temp_path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _write_hypotheses(path: Path, expected_rows: list[dict], rows: dict[str, dict]) -> None:
    ordered = [rows[row["id"]] for row in expected_rows if row["id"] in rows]
    raw = b"".join(_canonical(row) + b"\n" for row in ordered)
    if len(raw) > MAX_JSONL_BYTES:
        raise Refusal("hypothesis file exceeds its size budget")
    _atomic_write(path, raw)


def _load_scorer():
    spec = importlib.util.spec_from_file_location("sotto_fleurs_reference_score", SCORER_PATH)
    if spec is None or spec.loader is None:
        raise Refusal("reference scorer is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_ready_receipt(path: Path, cache_key: str) -> dict | None:
    if path.is_symlink():
        raise Refusal("cached readiness receipt is a symlink")
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > 64 * 1024:
        raise Refusal("cached readiness receipt is not a bounded regular file")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("cached readiness receipt is malformed") from None
    if not isinstance(receipt, dict):
        raise Refusal("cached readiness receipt is malformed")
    value = receipt.get("ready_s")
    if (set(receipt) != {
                "schema", "runner_cache_key", "ready_s", "diagnostic_config",
                "node_assignment_readback", "node_assignment_readback_s"}
            or receipt.get("schema") != SCHEMA
            or receipt.get("runner_cache_key") != cache_key
            or not isinstance(value, (int, float))
            or isinstance(value, bool) or not math.isfinite(value) or value <= 0
            or receipt.get("diagnostic_config") != DIAGNOSTIC_CONFIG):
        raise Refusal("cached readiness receipt identity or value is invalid")
    assignments = _normalize_node_assignment_readback(
        receipt.get("node_assignment_readback"))
    readback_s = receipt.get("node_assignment_readback_s")
    if (not isinstance(readback_s, (int, float)) or isinstance(readback_s, bool)
            or not math.isfinite(readback_s) or readback_s < 0):
        raise Refusal("cached node-assignment diagnostic cost is invalid")
    return {
        "ready_s": float(value),
        "node_assignment_readback": assignments,
        "node_assignment_readback_s": float(readback_s),
    }


def _write_ready_receipt(path: Path, cache_key: str, ready_s: float,
                         node_assignment_readback: dict,
                         node_assignment_readback_s: float) -> None:
    if (not isinstance(ready_s, (int, float)) or isinstance(ready_s, bool)
            or not math.isfinite(ready_s) or ready_s <= 0):
        raise Refusal("Consumer readiness timing is invalid")
    assignments = _normalize_node_assignment_readback(node_assignment_readback)
    if (not isinstance(node_assignment_readback_s, (int, float))
            or isinstance(node_assignment_readback_s, bool)
            or not math.isfinite(node_assignment_readback_s)
            or node_assignment_readback_s < 0):
        raise Refusal("node-assignment diagnostic cost is invalid")
    receipt = {
        "schema": SCHEMA,
        "runner_cache_key": cache_key,
        "ready_s": float(ready_s),
        "diagnostic_config": DIAGNOSTIC_CONFIG,
        "node_assignment_readback": assignments,
        "node_assignment_readback_s": float(node_assignment_readback_s),
    }
    _atomic_write(path, _canonical(receipt) + b"\n")


def _previous_ready_s(score_path: Path, hypotheses_path: Path,
                      cache_key: str, ready_path: Path) -> float | None:
    readiness = _read_ready_receipt(ready_path, cache_key)
    ready_s = readiness["ready_s"] if readiness is not None else None
    if not score_path.exists():
        return ready_s
    if score_path.is_symlink() or not score_path.is_file():
        raise Refusal("cached aggregate report is not a regular file")
    if score_path.stat().st_size > 64 * 1024 or not hypotheses_path.is_file():
        raise Refusal("cached aggregate report cannot be reconciled")
    try:
        report = json.loads(score_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("cached aggregate report is malformed") from None
    if not isinstance(report, dict):
        raise Refusal("cached aggregate report is malformed")
    hypotheses_sha = _sha(hypotheses_path.read_bytes())
    value = report.get("ready_s") if isinstance(report, dict) else None
    report_assignments = _normalize_node_assignment_readback(
        report.get("node_assignment_readback") if isinstance(report, dict) else None)
    if (ready_s is None
            or report.get("schema") != SCHEMA
            or report.get("runner_cache_key") != cache_key
            or report.get("hypotheses_sha256") != hypotheses_sha
            or value != ready_s
            or not isinstance(report.get("score"), dict)
            or report["score"].get("ready_s") != ready_s
            or report.get("diagnostic_config") != DIAGNOSTIC_CONFIG
            or report.get("cpu_execution_policy") != CPU_EXECUTION_POLICY
            or report_assignments != readiness["node_assignment_readback"]
            or report.get("node_assignment_readback_s")
            != readiness["node_assignment_readback_s"]
            or report.get("production_latency_comparable") is not False):
        raise Refusal("cached ready_s does not match its atomic readiness receipt")
    return ready_s


def _execute(manifest_path: Path, manifest: dict, expected_rows: list[dict],
             expected_sha: str, result_dir: Path, consumer_factory,
             scorer, *, model_label: str, clock=time.perf_counter,
             model_identity: dict | None = None,
             source_identity: dict | None = None,
             runtime_identity: dict | None = None) -> tuple[dict, int, int]:
    result_dir.mkdir(parents=True, exist_ok=True)
    result_path = result_dir / "hypotheses.jsonl"
    score_path = result_dir / "score.json"
    ready_path = result_dir / "ready.json"
    rows = _read_resume(result_path, expected_rows)
    readiness = _read_ready_receipt(ready_path, result_dir.name)
    ready_s = _previous_ready_s(score_path, result_path, result_dir.name, ready_path)
    node_assignment_readback = (
        readiness["node_assignment_readback"] if readiness is not None else None)
    node_assignment_readback_s = (
        readiness["node_assignment_readback_s"] if readiness is not None else None)
    cache_hits = len(rows)
    missing = [row for row in expected_rows if row["id"] not in rows]
    if missing:
        ready_started = clock()
        consumer = consumer_factory(result_dir)
        _validate_runtime_modules(runtime_identity, preload_audio=True)
        engine = consumer.engine()
        _validate_runtime_modules(runtime_identity, preload_audio=False,
                                  require_ort_loaded=True)
        _validate_engine(engine, require_vad=False)
        _validate_loaded_sources(
            source_identity,
            loaded_modules={"scorer": scorer},
            required_labels={
                "consumer", "redux", "sotto_worker", "cuda_bootstrap",
                "scorer", "transcribe",
            })
        measured_assignments = _normalize_node_assignment_readback(
            getattr(engine, "node_assignment_readback", None))
        measured_assignment_s = engine.thread_policy.get(
            "node_assignment_readback_s")
        if (not isinstance(measured_assignment_s, (int, float))
                or isinstance(measured_assignment_s, bool)
                or not math.isfinite(measured_assignment_s)
                or measured_assignment_s < 0):
            raise Refusal("Consumer node-assignment readback timing is invalid")
        if readiness is not None and (
                measured_assignments != node_assignment_readback
                or ready_s != readiness["ready_s"]):
            raise Refusal("resumed node-assignment evidence changed for this run")
        node_assignment_readback = measured_assignments
        if readiness is None:
            node_assignment_readback_s = float(measured_assignment_s)
        measured_ready_s = clock() - ready_started
        if not math.isfinite(measured_ready_s) or measured_ready_s <= 0:
            raise Refusal("Consumer construction and first engine readiness timing is invalid")
        if ready_s is None:
            ready_s = float(measured_ready_s)
            _write_ready_receipt(
                ready_path, result_dir.name, ready_s, node_assignment_readback,
                node_assignment_readback_s)
        budget = engine.thread_policy["process_pool_budget"]
        print(
            "THREADS process_budget=%d ort_intra=%d ort_inter=%d "
            "core_loader=%d integrity_hash=%d scope=configured-pools"
            % (budget["configured_total"], budget["ort_intra_op"],
               budget["ort_inter_op"], budget["core_session_loader"],
               budget["integrity_hash"]),
            file=sys.stderr, flush=True)
        for item in missing:
            started = clock()
            try:
                with open(os.devnull, "w", encoding="utf-8") as sink:
                    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                        text, state = consumer.transcribe(str(item["audio_path"]))
            except Exception as exc:
                raise Refusal("Consumer.transcribe failed (%s)" % type(exc).__name__) from None
            consumer_s = clock() - started
            if not isinstance(text, str) or state not in ("done", "empty"):
                raise Refusal("Consumer returned an invalid transcript result")
            if (state == "empty") != (text.strip() == ""):
                raise Refusal("Consumer state does not agree with transcript emptiness")
            text = text.strip()
            if len(text.encode("utf-8")) > MAX_ROW_TEXT_BYTES:
                raise Refusal("Consumer transcript exceeds its private row budget")
            if not math.isfinite(consumer_s) or consumer_s <= 0:
                raise Refusal("Consumer wall-time measurement is invalid")
            if consumer.engine() is not engine:
                raise Refusal("Consumer replaced the single loaded engine")
            _validate_engine(engine, require_vad=True)
            row = {
                "schema": SCHEMA,
                "completed": True,
                "id": item["id"],
                "audio_sha256": item["audio_sha256"],
                "audio_bytes": item["audio_bytes"],
                "audio_s": item["audio_s"],
                "consumer_s": round(consumer_s, 6),
                "inference_s": round(consumer_s, 6),
                "text": text,
                "text_sha256": _sha(text.encode("utf-8")),
                "state": state,
            }
            _validate_result_row(row, item)
            rows[item["id"]] = row
            _write_hypotheses(result_path, expected_rows, rows)
    if set(rows) != {row["id"] for row in expected_rows}:
        raise Refusal("completed hypotheses do not cover the pinned cohort")
    if ready_s is None:
        raise Refusal("completed hypotheses are missing their atomic readiness receipt")
    if node_assignment_readback is None or node_assignment_readback_s is None:
        raise Refusal("completed hypotheses are missing node-level CUDA evidence")
    score = scorer.score(Path(manifest_path), result_path, model_label, expected_sha)
    score["ready_s"] = ready_s
    report = {
        "schema": SCHEMA,
        "runner_cache_key": result_dir.name,
        "ready_s": ready_s,
        "cpu_execution_policy": CPU_EXECUTION_POLICY,
        "latency_mode": "diagnostic-node-assignment-trace",
        "production_latency_comparable": False,
        "gpu_execution_evidence": GPU_EXECUTION_EVIDENCE,
        "diagnostic_config": DIAGNOSTIC_CONFIG,
        "node_assignment_readback": node_assignment_readback,
        "node_assignment_readback_s": node_assignment_readback_s,
        "process_pool_budget": PROCESS_POOL_BUDGET,
        "model_identity": model_identity or {},
        "score": score,
        "hypotheses_sha256": _sha(result_path.read_bytes()),
    }
    _atomic_write(score_path, _canonical(report) + b"\n")
    return report, cache_hits, len(missing)


def _create_consumer(queue_dir: Path, model_dir: Path,
                    source_identity: dict | None = None):
    for name in THREAD_ENV:
        os.environ[name] = "1"
    os.environ[NODE_ASSIGNMENT_TRACE_ENV] = "1"
    os.environ[SESSION_FAILURE_TRACE_ENV] = "1"
    if str(WORKER) not in sys.path:
        sys.path.insert(0, str(WORKER))
    # This route assigns zero helper workers, so hash and core-session loading
    # happen on the caller thread. ORT's configured intra/inter pools are counted
    # separately in the aggregate process budget.
    import redux_live
    from audio_queue_consumer import Consumer
    _validate_loaded_sources(
        ({label: source_identity[label]
          for label in ("consumer", "redux") if label in source_identity}
         if source_identity is not None else None),
        required_labels={"consumer", "redux"})
    reference_dir = WORKER / "models" / "parakeet-redux-reference"
    for candidate in (str(Path(model_dir).resolve()), str(reference_dir.resolve())):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
    redux_live.CORE_SESSION_WORKERS = PROCESS_POOL_BUDGET["core_session_loader"]
    redux_live.CONTROL_HASH_WORKERS = PROCESS_POOL_BUDGET["integrity_hash"]
    if (redux_live.CORE_SESSION_WORKERS != 0
            or redux_live.CONTROL_HASH_WORKERS != 0
            or getattr(redux_live, "_CONTROL_HASH_EXECUTOR", None) is not None):
        raise Refusal("Redux loader concurrency did not honor the process budget")
    return Consumer(queue_dir=str(queue_dir), model_dir=str(model_dir),
                    log=lambda _message: None, threads=1)


def _public_summary(report: dict, cache_hits: int, executed: int, cache_dir: Path) -> str:
    score = report["score"]
    model_identity = report.get("model_identity") or {}
    public = {
        "status": "complete",
        "dataset": score.get("dataset"),
        "samples": score.get("samples"),
        "coverage": score.get("coverage"),
        "manifest_sha256": score.get("manifest_sha256"),
        "hypotheses_sha256": report.get("hypotheses_sha256"),
        "ready_s": report.get("ready_s"),
        "latency_mode": report.get("latency_mode"),
        "production_latency_comparable": report.get("production_latency_comparable"),
        "cpu_execution_policy": report.get("cpu_execution_policy"),
        "gpu_execution_evidence": report.get("gpu_execution_evidence"),
        "diagnostic_config": report.get("diagnostic_config"),
        "node_assignment_readback": report.get("node_assignment_readback"),
        "node_assignment_readback_s": report.get("node_assignment_readback_s"),
        "process_pool_budget": report.get("process_pool_budget"),
        "model_sha256": model_identity.get("sha256"),
        "model_identity_cache_hit": model_identity.get("cache_hit"),
        "model_bytes_hashed_this_run": model_identity.get("weight_bytes_hashed"),
        "wer": score.get("wer"),
        "cer_no_whitespace": score.get("cer_no_whitespace"),
        "rtf": score.get("rtf"),
        "inference_s_p50": score.get("inference_s_p50"),
        "inference_s_p95": score.get("inference_s_p95"),
        "inference_s_p99": score.get("inference_s_p99"),
        "cache_hits": cache_hits,
        "samples_executed": executed,
        "cache_dir": str(cache_dir),
    }
    return json.dumps(public, ensure_ascii=False, sort_keys=True)


def _selftest_engine(*, device="cuda", cpu_fallback="1", runtime_disabled=True,
                     include_vad=True, providers=None):
    graphs = set(ACOUSTIC_GRAPHS if include_vad else CORE_GRAPHS)
    registered = list(providers or (CUDA_PROVIDER, "CPUExecutionProvider"))
    provider_map = {name: registered[:] for name in graphs}
    options = {name: {
        "disable_cpu_ep_fallback": (
            cpu_fallback if cpu_fallback != "1" else
            DIAGNOSTIC_CONFIG["cpu_ep_fallback_key_by_graph"][name]),
        "requested_provider_names": list(
            DIAGNOSTIC_CONFIG["requested_providers_by_graph"][name]),
        "runtime_fallback_disabled": runtime_disabled,
        "intra_op_threads": 1,
        "inter_op_threads": 1,
        "use_per_session_threads": False,
        "execution_mode_sequential": True,
        "intra_op_spinning": "0",
        "inter_op_spinning": "0",
        "node_assignment_trace": True,
    } for name in graphs}
    node_assignments = {name: {
        "providers": dict(GRAPH_PROVIDER_NODE_COUNTS[name]),
        "cpu_nodes": dict(REDUX_CONTROL_NODES.get(name, {})),
        "total_nodes": GRAPH_NODE_COUNTS[name],
        "method": "get_provider_graph_assignment_info",
    } for name in graphs}
    return type("FakeEngine", (), {
        "device": device,
        "cpu_execution_policy": CPU_EXECUTION_POLICY,
        "provider_readback": provider_map,
        "node_assignment_readback": node_assignments,
        "control_hash_readback": {
            name: {"sha256": REDUX_CONTROL_HASHES[name],
                   "verified_before_session_return": True,
                   "verification": "source-sha256"}
            for name in ("preprocessor.onnx", "encoder-model.onnx", "vad-model.onnx")
        },
        "thread_policy": {
            "process_pool_budget": {
                **PROCESS_POOL_BUDGET,
                "scope": "configured pools; OS thread IDs are not inferred",
            },
            "helper_execution_readback": {
                "core_session_loader": "caller-thread",
                "integrity_hash": "caller-thread",
                "integrity_hash_executor_created": False,
            },
            "session_options_readback": options,
            "node_assignment_trace": True,
            "node_assignment_readback": node_assignments,
            "node_assignment_readback_s": 0.001,
            "runtime_fallback_readback": {name: True for name in graphs},
            "environment": {name: "1" for name in THREAD_ENV},
            "ort_global_intra_op_threads": 1,
            "ort_global_inter_op_threads": 1,
            "ort_intra_op_total": 1,
            "ort_inter_op_total": 1,
            "ort_per_session_pools": False,
            "ort_shared_global_pool": True,
            "ort_execution_mode": "ORT_SEQUENTIAL",
            "ort_spinning": False,
            "core_session_loader_workers": 0,
            "integrity_hash_workers": 0,
            "ort_intra_op_sessions": len(graphs),
            "ort_inter_op_sessions": len(graphs),
        },
    })()


def _selftest_manifest(base: Path):
    rows = []
    for sample_id, frame_byte in (("a", 1), ("b", 2)):
        wav_path = base / (sample_id + ".wav")
        with wave.open(str(wav_path), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(bytes((frame_byte, 0)) * 160)
        audio_sha, audio_size = _hash_file(wav_path)
        content_path = base / (audio_sha + ".wav")
        wav_path.replace(content_path)
        reference = "referencia " + sample_id
        rows.append({
            "id": sample_id,
            "source_path": "pt_br/" + sample_id + ".wav",
            "audio_sha256": audio_sha,
            "audio_bytes": audio_size,
            "reference": reference,
            "reference_sha256": _sha(reference.encode("utf-8")),
        })
    sidecar_bytes = b"synthetic reference sidecar\n"
    sidecar_sha = _sha(sidecar_bytes)
    manifest = {"dataset": "synthetic FLEURS contract test", "transcript_sha256": sidecar_sha,
                "records": rows}
    manifest_path = base / "fixture.manifest.json"
    manifest_path.write_bytes(_canonical(manifest))
    (base / (sidecar_sha + ".trans.txt")).write_bytes(sidecar_bytes)
    return manifest_path, _sha(manifest_path.read_bytes())


def _selftest_model_identity(base: Path) -> tuple[dict, Path]:
    model_dir = base / "parakeet-redux-fake"
    model_dir.mkdir()
    tree_dir = model_dir / ".cache/huggingface/trees"
    download_dir = model_dir / ".cache/huggingface/download"
    tree_dir.mkdir(parents=True)
    download_dir.mkdir(parents=True)
    files = {}
    for index, name in enumerate(sorted(CORE_GRAPHS | {"vad-model.onnx"}), 1):
        content = ("synthetic-weight-%d" % index).encode("ascii")
        (model_dir / name).write_bytes(content)
        digest = _sha(content)
        files[name] = {"size": len(content), "lfs_size": len(content), "lfs_sha256": digest}
        (download_dir / (name + ".metadata")).write_text(
            "fake-revision\n" + digest + "\n1700000000.0\n", encoding="utf-8")
    for name, content in (("config.json", b"{}"), ("vocab.txt", b"a\nb\n"),
                          ("transcribe.py", b"# fake local runtime\n")):
        (model_dir / name).write_bytes(content)
        blob_id = hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()
        files[name] = {"size": len(content), "blob_id": blob_id}
    tree_bytes = _canonical({"format_version": 1, "files": files})
    tree_path = tree_dir / "fake-revision.json"
    tree_path.write_bytes(tree_bytes)
    cache_path = base / "model-identities" / "fake.json"
    identity = _model_identity(
        model_dir, cache_path, tree_path=tree_path, revision="fake-revision",
        expected_tree_sha256=_sha(tree_bytes))
    return identity, cache_path


def selftest() -> None:
    forbidden_modules = {"audio_queue_consumer", "redux_live", "onnxruntime", "numpy", "soundfile"}
    loaded_before = forbidden_modules.intersection(sys.modules)
    if loaded_before:
        raise Refusal("selftest started after a heavy module was imported")
    try:
        object()._safe_probe_attribute
    except AttributeError as exc:
        diagnostic = _safe_exception_site(exc)
    else:
        raise AssertionError("safe exception-site fixture did not fail")
    if ("attribute=_safe_probe_attribute" not in diagnostic
            or "object at" in diagnostic or not diagnostic.startswith("fleurs-gpu-runner.py:")):
        raise AssertionError("safe exception-site diagnostic is incomplete or leaks repr")
    diagnostic_ns = {}
    exec(compile(
        "def _fake_ort_session(graph):\n"
        "    raise RuntimeError('[ONNXRuntimeError] : 1 : FAIL : H:/private/audio.wav')\n",
        "redux_live.py", "exec"), diagnostic_ns)
    try:
        diagnostic_ns["_fake_ort_session"](Path("encoder-model.onnx"))
    except RuntimeError as exc:
        ort_diagnostic = _safe_exception_site(exc)
    else:
        raise AssertionError("ORT diagnostic fixture did not fail")
    if ("graph=encoder-model.onnx" not in ort_diagnostic
            or "ort_code=1" not in ort_diagnostic
            or "private/audio.wav" in ort_diagnostic):
        raise AssertionError("ORT failure diagnostic leaks payload or lacks graph/code")
    assignment_error = RuntimeError("PRIVATE_TRANSCRIPT_SENTINEL")
    assignment_error.sotto_node_assignment_diagnostic = {
        "graph": "preprocessor.onnx",
        "trace_enabled": True,
        "readback_state": "populated",
        "assignment_rows": 2,
        "session_input_format": "onnx",
        "optimized_model_output": True,
        "actual_total": 58,
        "expected_total": 55,
        "actual_providers": {
            CUDA_PROVIDER: 52, "CPUExecutionProvider": 4,
            "PRIVATE_AUDIO_PATH": 2},
        "expected_providers": {
            CUDA_PROVIDER: 52, "CPUExecutionProvider": 3},
        "actual_cpu_nodes": 4,
        "expected_cpu_nodes": 3,
        "missing_cpu_nodes": 0,
        "extra_cpu_nodes": 1,
        "changed_cpu_ops": 0,
        "examples": ["extra:node_extra:Add", "PRIVATE_TRANSCRIPT_SENTINEL"],
        "examples_truncated": False,
    }
    wrapped_assignment_error = RuntimeError("session setup failed")
    wrapped_assignment_error.__cause__ = assignment_error
    assignment_summary = _safe_node_assignment_diagnostic(
        wrapped_assignment_error)
    if (assignment_summary is None
            or "PRIVATE_TRANSCRIPT_SENTINEL" in assignment_summary
            or "PRIVATE_AUDIO_PATH" in assignment_summary
            or "node_extra" not in assignment_summary
            or '"readback_state":"populated"' not in assignment_summary
            or '"session_input_format":"onnx"' not in assignment_summary
            or "\"actual_total\":58" not in assignment_summary
            or "\"OtherExecutionProviders\":2" not in assignment_summary):
        raise AssertionError(
            "node-assignment diagnostic was lost, unbounded, or not redacted")
    if _safe_node_assignment_diagnostic(RuntimeError("no node detail")) is not None:
        raise AssertionError("an untagged exception gained assignment details")
    empty_assignment_error = RuntimeError("empty assignment readback")
    empty_assignment_error.sotto_node_assignment_diagnostic = {
        "graph": "preprocessor.onnx",
        "trace_enabled": True,
        "readback_state": "empty",
        "assignment_rows": 0,
        "session_input_format": "ort",
        "optimized_model_output": False,
        "actual_total": None,
        "expected_total": 55,
        "actual_providers": None,
        "expected_providers": {CUDA_PROVIDER: 52, "CPUExecutionProvider": 3},
        "actual_cpu_nodes": None,
        "expected_cpu_nodes": 3,
        "missing_cpu_nodes": None,
        "extra_cpu_nodes": None,
        "changed_cpu_ops": None,
        "examples": [],
        "examples_truncated": False,
    }
    empty_assignment_summary = _safe_node_assignment_diagnostic(empty_assignment_error)
    if (empty_assignment_summary is None
            or '"assignment_rows":0' not in empty_assignment_summary
            or '"session_input_format":"ort"' not in empty_assignment_summary
            or '"actual_total":null' not in empty_assignment_summary):
        raise AssertionError("empty assignment-readback diagnostics were not preserved safely")
    malformed_assignment = RuntimeError("invalid diagnostic shape")
    malformed_assignment.sotto_node_assignment_diagnostic = {"graph": []}
    if _safe_node_assignment_diagnostic(malformed_assignment) is not None:
        raise AssertionError("malformed diagnostic graph escaped the safe serializer")
    unknown_format_assignment = RuntimeError("unknown session input format")
    unknown_format_assignment.sotto_node_assignment_diagnostic = {
        **empty_assignment_error.sotto_node_assignment_diagnostic,
        "session_input_format": "unknown",
    }
    if _safe_node_assignment_diagnostic(unknown_format_assignment) is not None:
        raise AssertionError("unknown session format escaped the strict serializer")
    agent_work = ROOT / ".agent-work"
    agent_work.mkdir(parents=True, exist_ok=True)
    if agent_work.drive.upper() != "H:":
        raise Refusal("selftest scratch is not on H:")
    all_output = None
    with tempfile.TemporaryDirectory(prefix="fleurs-gpu-fake-", dir=agent_work) as temp_name:
        temp = Path(temp_name)
        manifest_path, manifest_sha = _selftest_manifest(temp)
        manifest, expected_rows, actual_sha = _verify_manifest(
            manifest_path, manifest_sha, required_count=2, paced_hashes=False)
        if actual_sha != manifest_sha:
            raise Refusal("synthetic manifest hash verification failed")
        model_identity, model_identity_cache = _selftest_model_identity(temp)
        fake_model_dir = temp / "parakeet-redux-fake"
        fake_tree_path = _redux_tree_path(fake_model_dir, "fake-revision")
        fake_tree_sha = _sha(fake_tree_path.read_bytes())
        weight_reader_calls = []

        def forbid_fake_weight_read(path, *, paced=False):
            weight_reader_calls.append(path.name)
            raise AssertionError("identity cache hit read fake weight bytes")

        cached_model_identity = _model_identity(
            fake_model_dir, model_identity_cache, tree_path=fake_tree_path,
            revision="fake-revision", expected_tree_sha256=fake_tree_sha,
            hash_file_fn=forbid_fake_weight_read)
        if (not cached_model_identity["cache_hit"]
                or cached_model_identity["weight_bytes_hashed"] != 0
                or cached_model_identity["sha256"] != model_identity["sha256"]
                or weight_reader_calls):
            raise Refusal("model identity cache did not avoid weight reads")
        fake_encoder = fake_model_dir / "encoder-model.onnx"
        fake_encoder_stat = fake_encoder.stat()
        os.utime(fake_encoder, ns=(fake_encoder_stat.st_atime_ns,
                                   fake_encoder_stat.st_mtime_ns + 5_000_000_000))
        try:
            _model_identity(
                fake_model_dir, model_identity_cache, tree_path=fake_tree_path,
                revision="fake-revision", expected_tree_sha256=fake_tree_sha,
                hash_file_fn=forbid_fake_weight_read)
        except Refusal:
            pass
        else:
            raise Refusal("changed weight metadata did not invalidate its identity cache")
        if weight_reader_calls:
            raise Refusal("model identity invalidation reread fake weights")

        source_identity = _code_identity(fake_model_dir)
        required_sources = {
            "runner", "consumer", "redux", "sotto_worker", "cuda_bootstrap",
            "engine_policy", "scorer", "transcribe",
        }
        if not required_sources.issubset(source_identity):
            raise Refusal(
                "run cache identity omits a transitive route source"
            )
        if not callable(globals().get("_build_run_identity")):
            raise Refusal("content-addressed run identity has no testable builder")

        source_fixture_dir = temp / "source-identity-fixtures"
        source_fixture_dir.mkdir()
        source_fixture = {}
        for label in sorted(required_sources):
            fixture_path = source_fixture_dir / (label + ".py")
            fixture_path.write_bytes(("fixture:" + label).encode("ascii"))
            source_fixture[label] = _path_identity(fixture_path)

        worker_path_was_present = str(WORKER) in sys.path
        previous_route_modules = {
            name: sys.modules.get(name)
            for name in ("redux_live", "audio_queue_consumer")}
        sys.modules["redux_live"] = types.SimpleNamespace()
        sys.modules["audio_queue_consumer"] = types.SimpleNamespace(
            Consumer=object)
        try:
            for missing_identity in (None, {}):
                try:
                    _create_consumer(temp / "unused-queue", fake_model_dir,
                                     missing_identity)
                except Refusal:
                    pass
                else:
                    raise Refusal(
                        "consumer route accepted without required source identities")
        finally:
            for name, previous in previous_route_modules.items():
                if previous is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = previous
            if not worker_path_was_present:
                try:
                    sys.path.remove(str(WORKER))
                except ValueError:
                    pass

        scorer_fixture_module = types.SimpleNamespace(
            __file__=str(source_fixture_dir / "scorer.py"))
        _validate_loaded_sources(
            {"scorer": source_fixture["scorer"]},
            loaded_modules={"scorer": scorer_fixture_module},
            required_labels={"scorer"})
        for missing_identity, missing_modules in (
                (None, {"scorer": scorer_fixture_module}),
                ({}, {"scorer": scorer_fixture_module})):
            try:
                _validate_loaded_sources(
                    missing_identity,
                    loaded_modules=missing_modules,
                    required_labels={"scorer"})
            except Refusal:
                pass
            else:
                raise Refusal(
                    "required loaded scorer accepted without source identity")
        try:
            _validate_loaded_sources(
                {"scorer": source_fixture["scorer"]},
                loaded_modules={"scorer": None},
                required_labels={"scorer"})
        except Refusal:
            pass
        else:
            raise Refusal("missing required loaded scorer did not refuse")
        try:
            _validate_loaded_sources(
                {"scorer": {**source_fixture["scorer"], "sha256": "f" * 64}},
                loaded_modules={"scorer": scorer_fixture_module},
                required_labels={"scorer"})
        except Refusal:
            pass
        else:
            raise Refusal("loaded scorer source mutation did not refuse")
        _validate_loaded_sources(
            {"engine_policy": source_fixture["engine_policy"]},
            loaded_modules={"engine_policy": None})

        package_fixture_root = temp / "runtime-identity-fixtures"
        package_fixture_root.mkdir()
        package_fixture_dirs = {
            "onnxruntime-gpu": package_fixture_root / "onnxruntime-gpu",
            "numpy": package_fixture_root / "numpy",
            "soundfile": package_fixture_root / "soundfile",
        }
        for package_root in package_fixture_dirs.values():
            package_root.mkdir()
        for package_label, package_root in (
                ("onnxruntime", package_fixture_dirs["onnxruntime-gpu"]),
                ("numpy", package_fixture_dirs["numpy"]),
                ("soundfile", package_fixture_dirs["soundfile"])):
            for relative in RUNTIME_PACKAGE_FILES[package_label]:
                fixture_path = package_root / relative
                fixture_path.parent.mkdir(parents=True, exist_ok=True)
                fixture_path.write_bytes(("fixture:" + relative).encode("ascii"))

        fake_native_files = {
            "onnxruntime-gpu": Path("onnxruntime/capi/onnxruntime_providers_cuda.dll"),
            "numpy": Path("numpy/_core/_multiarray_umath.pyd"),
            "soundfile": Path("soundfile.libs/libsndfile-1.dll"),
        }
        for name, relative in fake_native_files.items():
            native_path = package_fixture_dirs[name] / relative
            native_path.parent.mkdir(parents=True, exist_ok=True)
            native_path.write_bytes(("native:" + name).encode("ascii"))

        class FakeDistribution:
            def __init__(self, name, root, files=()):
                self.metadata = {"Name": name}
                self.version = "0.fake"
                self._root = root
                self.files = tuple(files)

            def locate_file(self, relative):
                return self._root / relative

        fake_distributions = {
            name: FakeDistribution(name, package_root, (fake_native_files[name],))
            for name, package_root in package_fixture_dirs.items()
        }

        torch_root = package_fixture_root / "torch"
        torch_root.mkdir()
        torch_init = torch_root / "torch" / "__init__.py"
        torch_dll = torch_root / "torch" / "lib" / "torch-cuda.dll"
        torch_init.parent.mkdir(parents=True)
        torch_dll.parent.mkdir(parents=True)
        torch_init.write_bytes(b"fake torch runtime source")
        torch_dll.write_bytes(b"fake torch CUDA loader")
        nvidia_root = package_fixture_root / "nvidia-runtime"
        nvidia_root.mkdir()
        nvidia_dll = nvidia_root / "nvidia" / "cublas" / "cublas64.dll"
        nvidia_dll.parent.mkdir(parents=True)
        nvidia_dll.write_bytes(b"fake NVIDIA runtime library")
        fake_provider_distributions = [
            FakeDistribution("torch", torch_root, (
                Path("torch/__init__.py"), Path("torch/lib/torch-cuda.dll"))),
            FakeDistribution("nvidia-cublas-cu12", nvidia_root, (
                Path("nvidia/cublas/cublas64.dll"),)),
        ]

        def fake_distribution_loader(name):
            return fake_distributions[name]

        runtime_fixture = _runtime_identity(
            "onnxruntime-gpu", distribution_loader=fake_distribution_loader,
            include_import_origins=False,
            provider_distributions_loader=lambda: fake_provider_distributions)
        fake_model_for_key = {"sha256": "c" * 64, "bytes": 1, "files": 1}
        fake_rows_for_key = [{
            "id": "fixture", "audio_sha256": "d" * 64, "audio_bytes": 1,
        }]

        def run_key(source_rows, runtime_rows, diagnostic=DIAGNOSTIC_CONFIG):
            return _sha(_canonical(_build_run_identity(
                manifest_sha="e" * 64, rows=fake_rows_for_key,
                model_identity=fake_model_for_key, source_identity=source_rows,
                runtime_identity=runtime_rows, diagnostic_config=diagnostic)))

        diagnostic_key = run_key(source_fixture, runtime_fixture)
        changed_diagnostic = dict(DIAGNOSTIC_CONFIG)
        changed_diagnostic["node_assignment_trace"] = False
        if run_key(source_fixture, runtime_fixture, changed_diagnostic) == diagnostic_key:
            raise Refusal("node-assignment diagnostic flag did not change the run key")

        for label, fixture_record in tuple(source_fixture.items()):
            fixture_path = Path(fixture_record["path"])
            original = fixture_path.read_bytes()
            baseline = dict(source_fixture)
            baseline_key = run_key(baseline, runtime_fixture)
            fixture_path.write_bytes(original + b"-mutated")
            mutated = dict(source_fixture)
            mutated[label] = _path_identity(fixture_path)
            if run_key(mutated, runtime_fixture) == baseline_key:
                raise Refusal("a source-file mutation reused the previous cache identity")
            fixture_path.write_bytes(original)
            source_fixture[label] = _path_identity(fixture_path)

        runtime_paths = [
            (fake_distributions[name].locate_file(relative), package_label)
            for package_label, name in (("onnxruntime", "onnxruntime-gpu"),
                                        ("numpy", "numpy"),
                                        ("soundfile", "soundfile"))
            for relative in RUNTIME_PACKAGE_FILES[package_label]
        ]
        runtime_paths.extend(((torch_init, "torch"), (torch_dll, "torch"),
                              (nvidia_dll, "nvidia")))
        runtime_paths.extend(
            (package_fixture_dirs[name] / relative, name)
            for name, relative in fake_native_files.items())
        for fixture_path, _package_label in runtime_paths:
            original = fixture_path.read_bytes()
            baseline_key = run_key(source_fixture, runtime_fixture)
            fixture_path.write_bytes(original + b"-mutated")
            mutated_runtime = _runtime_identity(
                "onnxruntime-gpu", distribution_loader=fake_distribution_loader,
                include_import_origins=False,
                provider_distributions_loader=lambda: fake_provider_distributions)
            if run_key(source_fixture, mutated_runtime) == baseline_key:
                raise Refusal("a runtime-source mutation reused the previous cache identity")
            fixture_path.write_bytes(original)
            runtime_fixture = _runtime_identity(
                "onnxruntime-gpu", distribution_loader=fake_distribution_loader,
                include_import_origins=False,
                provider_distributions_loader=lambda: fake_provider_distributions)

        runtime_metadata_mutations = [
            ("python", "version"),
            ("provider_environment", "path_sha256"),
        ]
        for first, second in runtime_metadata_mutations:
            baseline_key = run_key(source_fixture, runtime_fixture)
            mutated_runtime = json.loads(_canonical(runtime_fixture).decode("utf-8"))
            if first == "python":
                mutated_runtime[first][second][2] += 1
            else:
                mutated_runtime[first][second] = "f" * 64
            if run_key(source_fixture, mutated_runtime) == baseline_key:
                raise Refusal("a runtime version/path environment mutation reused its cache key")
        for package_label in ("onnxruntime", "numpy", "soundfile"):
            for field in ("version", "root"):
                baseline_key = run_key(source_fixture, runtime_fixture)
                mutated_runtime = json.loads(_canonical(runtime_fixture).decode("utf-8"))
                mutated_runtime["packages"][package_label][field] += ".mutated"
                if run_key(source_fixture, mutated_runtime) == baseline_key:
                    raise Refusal("a runtime package version/path mutation reused its cache key")

        expected_pool_budget = {
            "ort_intra_op": 1,
            "ort_inter_op": 1,
            "core_session_loader": 0,
            "integrity_hash": 0,
            "configured_total": 2,
            "scope": "configured pools; OS thread IDs are not inferred",
        }
        if _selftest_engine().thread_policy.get("process_pool_budget") != expected_pool_budget:
            raise Refusal("Redux process-wide pool budget is missing or inaccurate")

        fake_allowlist = {
            name: (REDUX_CONTROL_HASHES[name], REDUX_CONTROL_NODES[name])
            for name in REDUX_CONTROL_HASHES
        }
        sys.modules["redux_live"] = types.SimpleNamespace(
            REDUX_CONTROL_GRAPH_ALLOWLIST=fake_allowlist)
        try:
            _validate_engine(_selftest_engine(), require_vad=False)
            bad_allowlist = dict(fake_allowlist)
            bad_allowlist["encoder-model.onnx"] = (
                REDUX_CONTROL_HASHES["encoder-model.onnx"], {"unexpected_node": "Add"})
            sys.modules["redux_live"].REDUX_CONTROL_GRAPH_ALLOWLIST = bad_allowlist
            try:
                _validate_engine(_selftest_engine(), require_vad=False)
            except Refusal:
                pass
            else:
                raise Refusal("changed Redux control-node allowlist was accepted")
        finally:
            sys.modules.pop("redux_live", None)

        scorer = _load_scorer()
        route_source_labels = (
            "consumer", "redux", "sotto_worker", "cuda_bootstrap", "transcribe")
        route_module_aliases = {
            "consumer": "audio_queue_consumer",
            "redux": "redux_live",
            "sotto_worker": "sotto_worker",
            "cuda_bootstrap": "ort_cuda_runtime",
            "transcribe": "transcribe",
        }

        def execute_fixture(*args, **kwargs):
            scorer_module = args[6] if len(args) > 6 else kwargs["scorer"]
            scorer_origin = getattr(scorer_module, "__file__", None)
            if not scorer_origin:
                scorer_origin = str(source_fixture_dir / "scorer.py")
                scorer_module.__file__ = scorer_origin
            fixture_sources = {
                label: source_fixture[label] for label in route_source_labels}
            fixture_sources["scorer"] = _path_identity(Path(scorer_origin))
            previous_modules = {}
            try:
                for label in route_source_labels:
                    alias = route_module_aliases[label]
                    previous_modules[alias] = sys.modules.get(alias)
                    attributes = {
                        "__file__": str(source_fixture_dir / (label + ".py"))}
                    if label == "redux":
                        attributes["REDUX_CONTROL_GRAPH_ALLOWLIST"] = fake_allowlist
                    sys.modules[alias] = types.SimpleNamespace(**attributes)
                kwargs["source_identity"] = fixture_sources
                return _execute(*args, **kwargs)
            finally:
                for alias, previous in previous_modules.items():
                    if previous is None:
                        sys.modules.pop(alias, None)
                    else:
                        sys.modules[alias] = previous

        fake_cache_key = _sha(_canonical({"fixture": manifest_sha, "schema": SCHEMA}))
        cache_dir = temp / "cache" / fake_cache_key
        transcripts = "TRANSCRIPT_SENTINEL"

        class FakeConsumer:
            def __init__(self):
                self._engine = _selftest_engine()
                self.engine_loads = 1
                self.calls = 0

            def engine(self):
                return self._engine

            def transcribe(self, _path):
                self.calls += 1
                self._engine.provider_readback["vad-model.onnx"] = [
                    CUDA_PROVIDER, "CPUExecutionProvider"]
                self._engine.thread_policy["session_options_readback"]["vad-model.onnx"] = {
                    "disable_cpu_ep_fallback": "0",
                    "requested_provider_names": [CUDA_PROVIDER, "CPUExecutionProvider"],
                    "runtime_fallback_disabled": True,
                    "intra_op_threads": 1, "inter_op_threads": 1,
                    "use_per_session_threads": False, "execution_mode_sequential": True,
                    "intra_op_spinning": "0", "inter_op_spinning": "0",
                    "node_assignment_trace": True,
                }
                vad_map = dict(self._engine.node_assignment_readback)
                vad_map["vad-model.onnx"] = {
                    "providers": dict(GRAPH_PROVIDER_NODE_COUNTS["vad-model.onnx"]),
                    "cpu_nodes": dict(REDUX_CONTROL_NODES["vad-model.onnx"]),
                    "total_nodes": GRAPH_NODE_COUNTS["vad-model.onnx"],
                    "method": "get_provider_graph_assignment_info",
                }
                self._engine.node_assignment_readback = vad_map
                self._engine.thread_policy["node_assignment_readback"] = vad_map
                self._engine.thread_policy["ort_intra_op_sessions"] = 4
                self._engine.thread_policy["ort_inter_op_sessions"] = 4
                return transcripts, "done"

        fake = FakeConsumer()
        factory_calls = [0]

        class DeterministicClock:
            def __init__(self):
                self.values = iter((1.0, 3.5, 10.0, 10.125, 20.0, 20.25))

            def __call__(self):
                return next(self.values)

        fake_clock = DeterministicClock()

        def valid_factory(_queue):
            factory_calls[0] += 1
            return fake

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            report, hits, executed = execute_fixture(
                manifest_path, manifest, expected_rows, manifest_sha, cache_dir,
                valid_factory, scorer, model_label="fake-redux", clock=fake_clock,
                model_identity=model_identity)
            print(_public_summary(report, hits, executed, cache_dir))
        if (fake.calls != 2 or fake.engine_loads != 1 or factory_calls[0] != 1
                or hits != 0 or executed != 2):
            raise Refusal("synthetic execution did not run exactly once per row")
        if report.get("ready_s") != 2.5 or report["score"].get("ready_s") != 2.5:
            raise Refusal("deterministic Consumer startup ready_s was not reported")
        ready_path = cache_dir / "ready.json"
        if not ready_path.is_file():
            raise Refusal("readiness was not persisted before the score report")
        if _read_ready_receipt(ready_path, cache_dir.name)["ready_s"] != 2.5:
            raise Refusal("persisted readiness receipt does not match the current run")
        if not cached_model_identity["cache_hit"] or cached_model_identity["weight_bytes_hashed"] != 0:
            raise Refusal("model identity cache-hit report is incorrect")
        if transcripts in stdout.getvalue() or transcripts in json.dumps(report):
            raise Refusal("transcript sentinel leaked to public output or report")
        hypothesis_path = cache_dir / "hypotheses.jsonl"
        if transcripts not in hypothesis_path.read_text(encoding="utf-8"):
            raise Refusal("private hypotheses file did not preserve scorer input")
        if _dir_bytes(cache_dir) > MAX_CACHE_BYTES:
            raise Refusal("synthetic output exceeded the private cache ceiling")

        def must_not_create(_queue):
            raise Refusal("complete cache attempted to construct another consumer")

        _, second_hits, second_executed = execute_fixture(
            manifest_path, manifest, expected_rows, manifest_sha, cache_dir,
            must_not_create, scorer, model_label="fake-redux")
        if second_hits != 2 or second_executed != 0:
            raise Refusal("completed rows were not resumed from cache")
        if factory_calls[0] != 1:
            raise Refusal("resume constructed an unnecessary second Consumer")
        if transcripts in _public_summary(report, second_hits, second_executed, cache_dir):
            raise Refusal("cached public summary leaked transcript text")

        crash_cache_dir = temp / "cache-crash" / _sha(
            _canonical({"fixture": manifest_sha, "schema": SCHEMA, "crash": True})
        )
        crashed_consumer = FakeConsumer()

        class InjectedScoreCrash:
            @staticmethod
            def score(*_args, **_kwargs):
                raise RuntimeError("synthetic crash before aggregate report")

        try:
            execute_fixture(
                manifest_path, manifest, expected_rows, manifest_sha,
                crash_cache_dir, lambda _queue: crashed_consumer,
                InjectedScoreCrash, model_label="fake-redux",
                clock=DeterministicClock(), model_identity=model_identity)
        except RuntimeError as exc:
            if str(exc) != "synthetic crash before aggregate report":
                raise
        else:
            raise Refusal("synthetic crash was not injected before score write")
        if not (crash_cache_dir / "hypotheses.jsonl").is_file():
            raise Refusal("crash control did not reach the final hypothesis artifact")
        if not (crash_cache_dir / "ready.json").is_file():
            raise Refusal("crash control lost its already-measured readiness receipt")
        recovered, recovered_hits, recovered_executed = execute_fixture(
            manifest_path, manifest, expected_rows, manifest_sha,
            crash_cache_dir, must_not_create, scorer, model_label="fake-redux")
        if (recovered.get("ready_s") != 2.5 or recovered_hits != 2
                or recovered_executed != 0):
            raise Refusal("crash resume claimed completion without the measured readiness")
        corrupt_ready_path = crash_cache_dir / "ready.json"
        corrupt_ready = json.loads(corrupt_ready_path.read_text(encoding="utf-8"))
        corrupt_ready["runner_cache_key"] = "foreign-run"
        corrupt_ready_path.write_bytes(_canonical(corrupt_ready) + b"\n")
        try:
            execute_fixture(manifest_path, manifest, expected_rows, manifest_sha,
                     crash_cache_dir, must_not_create, scorer, model_label="fake-redux")
        except Refusal:
            pass
        else:
            raise Refusal("foreign readiness receipt was accepted")
        corrupt_ready_path.write_bytes(b"{corrupt-json\n")
        try:
            execute_fixture(manifest_path, manifest, expected_rows, manifest_sha,
                     crash_cache_dir, must_not_create, scorer, model_label="fake-redux")
        except Refusal:
            pass
        else:
            raise Refusal("corrupt readiness receipt was accepted")

        try:
            _verify_manifest(manifest_path, "0" * 64, required_count=2, paced_hashes=False)
        except Refusal:
            pass
        else:
            raise Refusal("manifest hash mismatch was accepted")

        first_audio = expected_rows[0]["audio_path"]
        original_audio = first_audio.read_bytes()
        first_audio.write_bytes(original_audio[:-1] + bytes((original_audio[-1] ^ 1,)))
        try:
            _verify_manifest(manifest_path, manifest_sha, required_count=2, paced_hashes=False)
        except Refusal:
            pass
        else:
            raise Refusal("per-file audio hash/size mismatch was accepted")
        first_audio.write_bytes(original_audio)

        cached = json.loads(hypothesis_path.read_text(encoding="utf-8").splitlines()[0])
        cached["audio_sha256"] = "0" * 64
        hypothesis_path.write_text(_canonical(cached).decode("utf-8") + "\n", encoding="utf-8")
        try:
            _read_resume(hypothesis_path, expected_rows)
        except Refusal:
            pass
        else:
            raise Refusal("cached row hash mismatch was accepted")

        missing_assignment_engine = _selftest_engine()
        missing_assignment_engine.node_assignment_readback = {}
        missing_assignment_engine.thread_policy["node_assignment_readback"] = {}
        cpu_assignment_engine = _selftest_engine()
        cpu_assignments = dict(cpu_assignment_engine.node_assignment_readback)
        cpu_assignments["encoder-model.onnx"] = {
            "providers": {"CPUExecutionProvider": 3},
            "total_nodes": 3,
            "method": "get_provider_graph_assignment_info",
        }
        cpu_assignment_engine.node_assignment_readback = cpu_assignments
        cpu_assignment_engine.thread_policy["node_assignment_readback"] = cpu_assignments
        unknown_assignment_engine = _selftest_engine()
        unknown_assignments = dict(unknown_assignment_engine.node_assignment_readback)
        unknown_assignments["encoder-model.onnx"] = {
            "providers": {CUDA_PROVIDER: 2, "UnknownExecutionProvider": 1},
            "total_nodes": 3,
            "method": "get_provider_graph_assignment_info",
        }
        unknown_assignment_engine.node_assignment_readback = unknown_assignments
        unknown_assignment_engine.thread_policy["node_assignment_readback"] = unknown_assignments
        added_cpu_engine = _selftest_engine()
        added_cpu = dict(added_cpu_engine.node_assignment_readback)
        added_cpu["encoder-model.onnx"] = dict(added_cpu["encoder-model.onnx"])
        added_cpu["encoder-model.onnx"]["providers"] = {
            CUDA_PROVIDER: 1617, "CPUExecutionProvider": 22}
        added_cpu["encoder-model.onnx"]["cpu_nodes"] = {
            **REDUX_CONTROL_NODES["encoder-model.onnx"], "unmeasured_cpu": "Add"}
        added_cpu["encoder-model.onnx"]["total_nodes"] = 1639
        added_cpu_engine.node_assignment_readback = added_cpu
        added_cpu_engine.thread_policy["node_assignment_readback"] = added_cpu
        substituted_cpu_engine = _selftest_engine()
        substituted_cpu = dict(substituted_cpu_engine.node_assignment_readback)
        substituted_cpu["encoder-model.onnx"] = dict(substituted_cpu["encoder-model.onnx"])
        substituted_map = dict(REDUX_CONTROL_NODES["encoder-model.onnx"])
        substituted_map["node_Concat_153"] = "OtherOp"
        substituted_cpu["encoder-model.onnx"]["cpu_nodes"] = substituted_map
        substituted_cpu_engine.node_assignment_readback = substituted_cpu
        substituted_cpu_engine.thread_policy["node_assignment_readback"] = substituted_cpu
        changed_op_engine = _selftest_engine()
        changed_op = dict(changed_op_engine.node_assignment_readback)
        changed_op["encoder-model.onnx"] = dict(changed_op["encoder-model.onnx"])
        changed_op_map = dict(REDUX_CONTROL_NODES["encoder-model.onnx"])
        changed_op_map["node_Concat_153"] = "Identity"
        changed_op["encoder-model.onnx"]["cpu_nodes"] = changed_op_map
        changed_op_engine.node_assignment_readback = changed_op
        changed_op_engine.thread_policy["node_assignment_readback"] = changed_op
        cpu_decoder_engine = _selftest_engine()
        cpu_decoder = dict(cpu_decoder_engine.node_assignment_readback)
        cpu_decoder["decoder_joint-model.onnx"] = {
            "providers": {CUDA_PROVIDER: 50, "CPUExecutionProvider": 1},
            "cpu_nodes": {"decoder_cpu": "Add"},
            "total_nodes": 51,
            "method": "get_provider_graph_assignment_info",
        }
        cpu_decoder_engine.node_assignment_readback = cpu_decoder
        cpu_decoder_engine.thread_policy["node_assignment_readback"] = cpu_decoder
        changed_hash_engine = _selftest_engine()
        changed_hash = dict(changed_hash_engine.control_hash_readback)
        changed_hash["encoder-model.onnx"] = dict(changed_hash["encoder-model.onnx"])
        changed_hash["encoder-model.onnx"]["sha256"] = "0" * 64
        changed_hash_engine.control_hash_readback = changed_hash
        for index, bad_engine in enumerate((
            _selftest_engine(device="cpu"),
            _selftest_engine(cpu_fallback="0"),
            _selftest_engine(runtime_disabled=False),
            _selftest_engine(providers=("CPUExecutionProvider",)),
            missing_assignment_engine,
            cpu_assignment_engine,
            unknown_assignment_engine,
            added_cpu_engine,
            substituted_cpu_engine,
            changed_op_engine,
            cpu_decoder_engine,
            changed_hash_engine,
        )):
            class RefusingConsumer:
                def __init__(self):
                    self.calls = 0

                def engine(self):
                    return bad_engine

                def transcribe(self, _path):
                    self.calls += 1
                    return transcripts, "done"

            refusing = RefusingConsumer()
            try:
                execute_fixture(manifest_path, manifest, expected_rows, manifest_sha,
                         temp / "refused" / str(index), lambda _queue: refusing,
                         scorer, model_label="fake-redux")
            except Refusal:
                pass
            else:
                raise Refusal("CPU/fallback/unattested-node engine was accepted")
            if refusing.calls != 0:
                raise Refusal("fallback refusal happened after transcription")

        if forbidden_modules.intersection(sys.modules):
            raise Refusal("fake selftest imported an audio/model/GPU module")
        all_output = sum(p.stat().st_size for p in temp.rglob("*") if p.is_file())
        if all_output > MAX_CACHE_BYTES:
            raise Refusal("selftest scratch exceeded 2 MiB")
    if (temp.exists() or all_output is None or all_output > MAX_CACHE_BYTES
            or forbidden_modules.intersection(sys.modules)):
        raise Refusal("selftest cleanup or resource proof failed")
    print("SELFTEST PASS: manifest/hash, transitive cache identity, ready_s receipt recovery, pinned CPU control-node/CUDA neural placement, provider/runtime fallback gates, transcript-safe output, <=2MiB scratch")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run only tiny synthetic fakes")
    parser.add_argument("--expected-manifest-sha256", help="required exact pinned cohort SHA-256")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_DEFAULT)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DEFAULT)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE)
    args = parser.parse_args(argv)
    stage = "argument-validation"
    try:
        if args.selftest:
            selftest()
            return 0
        if args.expected_manifest_sha256 != PINNED_MANIFEST_SHA256:
            raise Refusal("the exact pinned expected manifest SHA-256 is mandatory")
        if ROOT.drive.upper() != "H:" or args.cache_root.drive.upper() != "H:":
            raise Refusal("the runner and cache must stay on H:")
        manifest_path = _safe_under(ROOT, args.manifest)
        cache_root = _safe_under(ROOT, args.cache_root)
        model_dir = _safe_under(ROOT, args.model_dir)
        stage = "manifest-validation"
        manifest, rows, manifest_sha = _verify_manifest(
            manifest_path, args.expected_manifest_sha256)
        cache_root.mkdir(parents=True, exist_ok=True)
        stage = "model-identity"
        model_identity_path = _model_identity_cache_path(model_dir, cache_root)
        if model_identity_path.parent.is_symlink() or model_identity_path.is_symlink():
            raise Refusal("Redux model identity cache path is a symlink")
        model_identity = _model_identity(model_dir, model_identity_path)
        stage = "source-identity"
        source_identity = _code_identity(model_dir)
        stage = "runtime-artifact-discovery"
        ort_distribution = None
        for candidate in ("onnxruntime-gpu", "onnxruntime"):
            try:
                importlib.metadata.version(candidate)
                ort_distribution = candidate
                break
            except importlib.metadata.PackageNotFoundError:
                continue
        if ort_distribution is None:
            raise Refusal("ONNX Runtime package version is unavailable")
        stage = "runtime-identity"
        runtime_identity = _runtime_identity(ort_distribution, model_dir)
        identity = _build_run_identity(
            manifest_sha=manifest_sha, rows=rows, model_identity=model_identity,
            source_identity=source_identity, runtime_identity=runtime_identity)
        stage = "result-cache-identity"
        cache_key = _sha(_canonical(identity))
        cache_root.mkdir(parents=True, exist_ok=True)
        cache_candidate = cache_root / cache_key
        if cache_candidate.is_symlink():
            raise Refusal("content-addressed result directory is a symlink")
        cache_dir = _safe_under(ROOT, cache_candidate)
        stage = "scorer-load"
        scorer = _load_scorer()
        stage = "consumer-execution"
        report, cache_hits, executed = _execute(
            manifest_path, manifest, rows, manifest_sha, cache_dir,
            lambda queue: _create_consumer(queue, model_dir, source_identity), scorer,
            model_label="Parakeet Redux ONNX int4 via Sotto Consumer.transcribe",
            model_identity=model_identity, source_identity=source_identity,
            runtime_identity=runtime_identity)
        print(_public_summary(report, cache_hits, executed, cache_dir))
        return 0
    except Refusal as exc:
        # Refusal text is deliberately generic and never includes audio/transcript content.
        safe_code = re.sub(r"[^a-zA-Z0-9 _:-]", "", str(exc))[:120]
        print("REFUSED: " + safe_code, file=sys.stderr)
        return 2
    except Exception as exc:
        print("FAILED stage=%s type=%s at %s" %
              (stage, type(exc).__name__, _safe_exception_site(exc)), file=sys.stderr)
        placement = _safe_node_assignment_diagnostic(exc)
        if placement is not None:
            print("SOTTO_REDUX_NODE_ASSIGNMENT_REFUSED " + placement,
                  file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
