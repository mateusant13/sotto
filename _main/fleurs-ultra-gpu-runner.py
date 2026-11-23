#!/usr/bin/env python3
"""Score the pinned FLEURS pt-BR cohort through Parakeet Ultra ONNX on CUDA.

This is a batch comparison runner. It does not implement or claim stateful
560 ms streaming. Public output contains aggregate scores only; hypotheses are
kept in a content-addressed private H: cache.
"""
from __future__ import annotations

import argparse
import contextlib
import ctypes
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import os
import re
import stat
import struct
import sys
import tempfile
import time
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
MANIFEST_DEFAULT = ROOT / ".agent-work/asr-cache/fleurs/pt_br/b74b61db926bee40ba21ab385264b0e8cbc89d4d10f93a4c51bcb54e95f3033c.manifest.json"
MODEL_DEFAULT = Path(os.environ.get(
    "SOTTO_ULTRA_ONNX_DIR", str(WORKER / "models" / "parakeet-ultra-onnx")))
SCORER_PATH = ROOT / "_main" / "asr-reference-score.py"
CACHE_DEFAULT = ROOT / ".agent-work/asr-cache/fleurs-ultra-gpu"
PINNED_MANIFEST_SHA256 = "b74b61db926bee40ba21ab385264b0e8cbc89d4d10f93a4c51bcb54e95f3033c"
EXPECTED_SAMPLES = 20
THREAD_ENV = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
SCHEMA = "sotto-fleurs-parakeet-ultra-onnx-cuda-v2"
MODEL_SCHEMA = "sotto-parakeet-ultra-onnx-content-v2"
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_JSONL_BYTES = 1024 * 1024
MAX_REPORT_BYTES = 64 * 1024
MAX_CACHE_BYTES = 2 * 1024 * 1024
MAX_IDENTITY_BYTES = 64 * 1024
MAX_MODEL_FILES = 16
MAX_MODEL_BYTES = 2_000_000_000
MAX_AUDIO_BYTES = 32 * 1024 * 1024
HASH_READ_BYTES_PER_SECOND = 4 * 1024 * 1024
MAX_RESULT_GENERATIONS = 2
MAX_RESULT_CACHE_BYTES = 3 * 1024 * 1024
MAX_PROCESS_OS_THREADS = 32
RESULTS_DIRNAME = "results"
IDENTITIES_DIRNAME = "model-identities"
LOCK_FILENAME = ".cache.lock"
REQUIRED_MODEL_FILES = frozenset({
    "config.json", "preprocessor.onnx", "encoder-model.onnx",
    "decoder_joint-model.onnx", "vocab.txt", "transcribe.py",
})
OPTIONAL_MODEL_FILES = frozenset({"vad-model.onnx"})
MODEL_ROUTE = "worker.parakeet_ultra.OnnxBackend -> ONNX Runtime CUDA"

# Set before any project, NumPy, audio, CUDA, or ORT import.
for _name in THREAD_ENV:
    os.environ[_name] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
sys.dont_write_bytecode = True


class Refusal(RuntimeError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _require_h_path(value, label: str, *, must_exist: bool):
    path = Path(value).expanduser()
    if path.drive and path.drive.upper() != "H:":
        raise Refusal(label + " must be on H:")
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError:
        raise Refusal(label + " is unavailable") from None
    if resolved.drive.upper() != "H:":
        raise Refusal(label + " resolves outside H:")
    if path.is_symlink() or resolved.is_symlink():
        raise Refusal(label + " cannot be a symlink")
    return resolved


def _reject_reparse(path: Path, label: str) -> None:
    try:
        info = path.lstat()
    except OSError:
        raise Refusal(label + " is unavailable") from None
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & reparse_flag):
        raise Refusal(label + " cannot be a link or reparse point")


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
                target_s = size / HASH_READ_BYTES_PER_SECOND
                remaining_s = target_s - (time.perf_counter() - started)
                if remaining_s > 0:
                    time.sleep(remaining_s)
    return digest.hexdigest(), size


def _atomic_write(path: Path, raw: bytes, *, limit: int = MAX_CACHE_BYTES) -> None:
    if len(raw) > limit:
        raise Refusal("private artifact exceeds its size budget")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise Refusal("private output path cannot be a symlink")
    temp_path = path.with_name(path.name + ".tmp")
    if temp_path.exists() or temp_path.is_symlink():
        raise Refusal("stale atomic-write temporary exists")
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


@contextlib.contextmanager
def _cache_lease(cache_root: Path):
    """Serialize writers; the OS releases the byte-range lock after a crash."""
    lock_path = cache_root / LOCK_FILENAME
    if lock_path.is_symlink():
        raise Refusal("private cache lock cannot be a symlink")
    try:
        with lock_path.open("a+b") as stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            locked = False
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
            except (ImportError, OSError):
                raise Refusal("private cache is already in use") from None
            try:
                yield
            finally:
                if locked:
                    if os.name == "nt":
                        msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    except Refusal:
        raise
    except OSError:
        raise Refusal("private cache lock is unavailable") from None


def _result_cache_inventory(results_root: Path) -> list[dict]:
    if results_root.exists():
        if results_root.is_symlink() or not results_root.is_dir():
            raise Refusal("result cache root is not a regular directory")
        _reject_reparse(results_root, "result cache root")
    else:
        results_root.mkdir(parents=True, exist_ok=True)
    rows = []
    allowed_files = {"hypotheses.jsonl", "score.json",
                     "hypotheses.jsonl.tmp", "score.json.tmp"}
    for directory in results_root.iterdir():
        if len(rows) >= MAX_RESULT_GENERATIONS + 1:
            raise Refusal("result cache exceeds its bounded generation scan")
        if not re.fullmatch(r"[0-9a-f]{64}", directory.name):
            raise Refusal("result cache contains an unexpected entry")
        if directory.is_symlink() or not directory.is_dir():
            raise Refusal("result cache generation is not a regular directory")
        _reject_reparse(directory, "result cache generation")
        files = []
        for item in directory.iterdir():
            if len(files) >= len(allowed_files):
                raise Refusal("result cache generation exceeds its bounded artifact scan")
            _reject_reparse(item, "result cache artifact")
            if item.name not in allowed_files or not item.is_file():
                raise Refusal("result cache generation contains an unexpected artifact")
            files.append(item)
        rows.append({"key": directory.name, "path": directory, "files": files})
    return rows


def _maintain_result_cache(results_root: Path, current_key: str) -> dict:
    """Keep the active generation and one completed predecessor, within an aggregate cap."""
    if not re.fullmatch(r"[0-9a-f]{64}", current_key or ""):
        raise Refusal("result cache key is invalid")
    inventory = _result_cache_inventory(results_root)
    completed = []
    for row in inventory:
        key = row["key"]
        directory = row["path"]
        by_name = {item.name: item for item in row["files"]}
        for name in ("hypotheses.jsonl.tmp", "score.json.tmp"):
            temp_path = by_name.get(name)
            if temp_path is not None:
                # The cache lease proves no live writer owns this temp. Drop
                # it; the previous atomic destination remains the checkpoint.
                temp_path.unlink()
        report_path = by_name.get("score.json")
        is_complete = False
        if report_path is not None:
            if report_path.stat().st_size > MAX_REPORT_BYTES:
                raise Refusal("result cache report exceeds its size budget")
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                raise Refusal("result cache report is malformed") from None
            if (not isinstance(report, dict) or report.get("schema") != SCHEMA
                    or report.get("cache_key") != key):
                raise Refusal("result cache report identity is invalid")
            is_complete = True
        row["completed"] = is_complete
        row["mtime_ns"] = (report_path.stat().st_mtime_ns if is_complete
                           else directory.stat().st_mtime_ns)
        if key != current_key and is_complete:
            completed.append(row)
    completed.sort(key=lambda row: (row["mtime_ns"], row["key"]), reverse=True)
    keep = {current_key}
    keep.update(row["key"] for row in completed[:MAX_RESULT_GENERATIONS - 1])
    for row in inventory:
        if row["key"] in keep:
            continue
        for item in row["files"]:
            item.unlink()
        row["path"].rmdir()

    kept = _result_cache_inventory(results_root)
    if len(kept) > MAX_RESULT_GENERATIONS:
        raise Refusal("result cache exceeded its generation ceiling")
    total_bytes = 0
    for row in kept:
        for item in row["files"]:
            if item.name.endswith(".tmp"):
                raise Refusal("stale atomic result temporary remains")
            size = item.stat().st_size
            if size > (MAX_JSONL_BYTES if item.name == "hypotheses.jsonl" else MAX_REPORT_BYTES):
                raise Refusal("result cache artifact exceeds its size budget")
            total_bytes += size
    if total_bytes > MAX_RESULT_CACHE_BYTES:
        raise Refusal("aggregate result cache exceeds its byte ceiling")
    return {"generations": len(kept), "bytes": total_bytes, "keys": sorted(row["key"] for row in kept)}


def _recover_identity_cache(cache_root: Path) -> None:
    identity_root = cache_root / IDENTITIES_DIRNAME
    if not identity_root.exists():
        identity_root.mkdir(parents=True, exist_ok=True)
        return
    if identity_root.is_symlink() or not identity_root.is_dir():
        raise Refusal("model identity cache is not a regular directory")
    _reject_reparse(identity_root, "model identity cache")
    for index, item in enumerate(identity_root.iterdir()):
        if index >= 16:
            raise Refusal("model identity cache exceeds its bounded inventory")
        _reject_reparse(item, "model identity cache artifact")
        if item.name == "ultra.json.tmp" and item.is_file():
            item.unlink()
        elif item.name == "ultra.json" and item.is_file():
            if item.stat().st_size > MAX_IDENTITY_BYTES:
                raise Refusal("model identity cache exceeds its size budget")
        elif re.fullmatch(r"[0-9a-f]{64}\.json", item.name) and item.is_file():
            # Retire W35 v1's metadata-keyed cache; it cannot prove content.
            item.unlink()
        elif re.fullmatch(r"[0-9a-f]{64}\.json\.tmp", item.name) and item.is_file():
            item.unlink()
        else:
            raise Refusal("model identity cache contains an unexpected artifact")


def _retire_legacy_result_cache(cache_root: Path) -> None:
    """Remove only bounded v1 result directories whose schema cannot be reused."""
    allowed_root_entries = {IDENTITIES_DIRNAME, RESULTS_DIRNAME, LOCK_FILENAME}
    legacy = []
    max_root_entries = len(allowed_root_entries) + MAX_RESULT_GENERATIONS + 1
    for index, item in enumerate(cache_root.iterdir()):
        if index >= max_root_entries:
            raise Refusal("private cache root exceeds its bounded inventory")
        if item.name in allowed_root_entries:
            continue
        if len(legacy) >= MAX_RESULT_GENERATIONS + 1:
            raise Refusal("legacy result cache exceeds its bounded inventory")
        if (not re.fullmatch(r"[0-9a-f]{64}", item.name)
                or item.is_symlink() or not item.is_dir()):
            raise Refusal("private cache root contains an unexpected legacy artifact")
        _reject_reparse(item, "legacy result cache generation")
        children = []
        for child in item.iterdir():
            if len(children) >= 4:
                raise Refusal("legacy result cache generation exceeds its inventory")
            children.append(child)
        for child in children:
            _reject_reparse(child, "legacy result cache artifact")
            if (child.name not in {"hypotheses.jsonl", "score.json",
                                   "hypotheses.jsonl.tmp", "score.json.tmp"}
                    or not child.is_file()):
                raise Refusal("legacy result cache contains an unexpected artifact")
        legacy.append((item, children))
    for directory, children in legacy:
        for child in children:
            child.unlink()
        directory.rmdir()


def _verify_manifest(manifest_path: Path, expected_sha256: str,
                     required_count: int = EXPECTED_SAMPLES, *,
                     enforce_pinned: bool = True, paced_hashes: bool = True):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256 or ""):
        raise Refusal("expected manifest SHA-256 is required")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise Refusal("pinned manifest is unavailable")
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise Refusal("manifest exceeds its size budget")
    raw = manifest_path.read_bytes()
    actual_sha = _sha(raw)
    if actual_sha != expected_sha256:
        raise Refusal("manifest SHA-256 mismatch")
    if enforce_pinned and (required_count != EXPECTED_SAMPLES
                           or expected_sha256 != PINNED_MANIFEST_SHA256):
        raise Refusal("only the pinned 20-row FLEURS cohort is accepted")
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
        if (not sample_id or sample_id in seen
                or not isinstance(audio_sha, str)
                or not re.fullmatch(r"[0-9a-f]{64}", audio_sha)
                or audio_bytes <= 0 or audio_bytes > MAX_AUDIO_BYTES
                or not isinstance(reference, str)
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
                rate = audio.getframerate()
                frames = audio.getnframes()
                channels = audio.getnchannels()
                sample_width = audio.getsampwidth()
        except (wave.Error, EOFError, OSError):
            raise Refusal("pinned audio WAV metadata is invalid") from None
        if rate != 16000 or frames <= 0 or channels != 1 or sample_width != 2:
            raise Refusal("FLEURS audio must be mono 16 kHz signed 16-bit PCM WAV")
        verified.append({
            "id": sample_id,
            "audio_path": audio_path,
            "audio_sha256": audio_sha,
            "audio_bytes": audio_bytes,
            "audio_s": frames / rate,
        })
    if len(seen) != required_count:
        raise Refusal("manifest IDs are not one-to-one")
    return manifest, verified, actual_sha


def _windows_file_usn(path: Path) -> int | None:
    """Read an NTFS per-file change token; None means callers must rehash bytes."""
    if os.name != "nt":
        return None
    handle = None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.argtypes = (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                ctypes.c_void_p)
        create_file.restype = ctypes.c_void_p
        device_io = kernel32.DeviceIoControl
        device_io.argtypes = (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
                              ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32,
                              ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p)
        device_io.restype = ctypes.c_int
        close_handle = kernel32.CloseHandle
        close_handle.argtypes = (ctypes.c_void_p,)
        close_handle.restype = ctypes.c_int
        handle = create_file(str(path), 0x80000080, 0x00000007, None, 3, 0x00000080, None)
        invalid = ctypes.c_void_p(-1).value
        if not handle or handle == invalid:
            return None
        # FSCTL_READ_FILE_USN_DATA with a V2-only version range. NTFS advances
        # this token for writes even when size and restored mtime are unchanged.
        input_version = ctypes.create_string_buffer(struct.pack("<HH", 2, 2))
        output = ctypes.create_string_buffer(4096)
        returned = ctypes.c_uint32()
        if not device_io(handle, 0x000900EB, input_version, len(input_version),
                         output, len(output), ctypes.byref(returned), None):
            return None
        if returned.value < 32 or struct.unpack_from("<H", output.raw, 4)[0] != 2:
            return None
        return struct.unpack_from("<q", output.raw, 24)[0]
    except (AttributeError, OSError, TypeError, ValueError, struct.error):
        return None
    finally:
        if handle:
            try:
                kernel32.CloseHandle(handle)
            except (UnboundLocalError, AttributeError, OSError):
                pass


def _file_fingerprint(path: Path) -> dict[str, int | None]:
    info = path.stat()
    file_id = int(getattr(info, "st_ino", 0))
    if file_id <= 0:
        raise Refusal("filesystem lacks stable model file identity")
    return {"size": int(info.st_size), "mtime_ns": int(info.st_mtime_ns),
            "ctime_ns": int(info.st_ctime_ns), "device": int(info.st_dev),
            "file_id": file_id, "usn": _windows_file_usn(path)}


def _model_identity(model_dir: Path, cache_root: Path) -> dict:
    if model_dir.is_symlink() or not model_dir.is_dir():
        raise Refusal("Ultra ONNX model directory is unavailable")
    _reject_reparse(model_dir, "Ultra ONNX model directory")
    files = []
    total_bytes = 0
    allowed = REQUIRED_MODEL_FILES | OPTIONAL_MODEL_FILES
    for item in sorted(model_dir.iterdir(), key=lambda entry: entry.name):
        _reject_reparse(item, "Ultra ONNX model asset")
        if not item.is_file():
            raise Refusal("Ultra ONNX model tree contains an unexpected directory")
        name = item.name
        is_sidecar = name.endswith(".onnx.data")
        if name not in allowed and not is_sidecar:
            raise Refusal("Ultra ONNX model tree contains an unexpected file")
        if is_sidecar and name[:-5] not in allowed:
            raise Refusal("Ultra ONNX external-data sidecar has no graph owner")
        fingerprint = _file_fingerprint(item)
        total_bytes += fingerprint["size"]
        if len(files) >= MAX_MODEL_FILES or total_bytes > MAX_MODEL_BYTES:
            raise Refusal("Ultra ONNX model tree exceeds its inventory budget")
        files.append({"name": name, "path": item, "fingerprint": fingerprint})
    found = {row["name"] for row in files}
    if not REQUIRED_MODEL_FILES.issubset(found):
        raise Refusal("Ultra ONNX model tree is incomplete")
    for row in files:
        if row["name"].endswith(".onnx.data"):
            owner = row["name"][:-5]
            if owner not in found:
                raise Refusal("Ultra ONNX external-data sidecar is orphaned")

    root_key = _sha(_canonical({
        "schema": MODEL_SCHEMA,
        "path": str(model_dir.resolve()).casefold(),
        "files": [(row["name"], row["fingerprint"]) for row in files],
    }))
    identity_path = cache_root / IDENTITIES_DIRNAME / "ultra.json"
    cached = None
    reliable_change_tokens = all(row["fingerprint"].get("usn") is not None for row in files)
    if reliable_change_tokens and identity_path.exists():
        if identity_path.is_symlink() or not identity_path.is_file():
            raise Refusal("Ultra model identity cache is not a regular file")
        if identity_path.stat().st_size > MAX_IDENTITY_BYTES:
            raise Refusal("Ultra model identity cache exceeds its size budget")
        try:
            cached = json.loads(identity_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise Refusal("Ultra model identity cache is malformed") from None
        if not isinstance(cached, dict):
            raise Refusal("Ultra model identity cache schema is invalid")
        if cached.get("schema") == MODEL_SCHEMA:
            if not isinstance(cached.get("by_name"), dict):
                raise Refusal("Ultra model identity cache schema is invalid")
            metadata_matches = (
                cached.get("root_key") == root_key
                and cached.get("files") == [
                    {"name": row["name"], "fingerprint": row["fingerprint"],
                     "sha256": cached.get("by_name", {}).get(row["name"])}
                    for row in files]
            )
            if metadata_matches:
                for row in files:
                    digest = cached["by_name"].get(row["name"])
                    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                        raise Refusal("Ultra model identity cache has an invalid content hash")
            else:
                # A valid model update invalidates the reuse token; it does
                # not invalidate the benchmark. Rehash the new content below.
                cached = None
        else:
            # Schema upgrades also require a fresh content hash.
            cached = None

    started = time.perf_counter()
    hashed_bytes = 0
    if cached is None:
        by_name = {}
        for row in files:
            digest, size = _hash_file(row["path"], paced=True)
            after = _file_fingerprint(row["path"])
            if (size != row["fingerprint"]["size"]
                    or after != row["fingerprint"]):
                raise Refusal("Ultra model asset changed while hashing")
            by_name[row["name"]] = digest
            hashed_bytes += size
        identity_files = [
            {"name": row["name"], "fingerprint": row["fingerprint"],
             "sha256": by_name[row["name"]]}
            for row in files
        ]
        cached = {"schema": MODEL_SCHEMA, "root_key": root_key,
                  "files": identity_files, "by_name": by_name}
        _atomic_write(identity_path, _canonical(cached) + b"\n", limit=MAX_IDENTITY_BYTES)
    content_sha = _sha(_canonical({
        "schema": MODEL_SCHEMA,
        "files": [(row["name"], row["fingerprint"]["size"],
                   cached["by_name"][row["name"]]) for row in files],
    }))
    return {"sha256": content_sha, "bytes": total_bytes, "files": len(files),
            "cache_hit": hashed_bytes == 0, "content_bytes_hashed": hashed_bytes,
            "identity_s": time.perf_counter() - started,
            "change_token_cache": reliable_change_tokens,
            "session_graphs": sorted(name for name in found
                                      if name in {"preprocessor.onnx", "encoder-model.onnx",
                                                  "decoder_joint-model.onnx", "vad-model.onnx"})}


def _code_identity(paths: dict[str, Path] | None = None) -> dict[str, str]:
    paths = {"runner": Path(__file__).resolve(),
             "worker": WORKER / "parakeet_ultra.py",
             "worker_bootstrap": WORKER / "sotto_worker.py",
             "scorer": SCORER_PATH} if paths is None else paths
    result = {}
    for label, path in paths.items():
        if not path.is_file():
            raise Refusal("benchmark source is unavailable")
        result[label] = _hash_file(path)[0]
    return result


def _load_scorer():
    spec = importlib.util.spec_from_file_location("sotto_ultra_fleurs_score", SCORER_PATH)
    if spec is None or spec.loader is None:
        raise Refusal("reference scorer is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_engine(engine, expected_graphs: set[str]) -> None:
    if (getattr(engine, "device", None) != "cuda"
            or getattr(engine, "frontend_device", None) != "cuda"
            or getattr(engine, "ort_device_readback", None) != "GPU"
            or getattr(engine, "cpu_ep_fallback_disabled", None) is not True
            or getattr(engine, "ort_intra_op_threads", None) != 1):
        raise Refusal("Ultra engine device/ORT policy readback is unsafe")
    providers = getattr(engine, "provider_readback", None)
    session_policy = getattr(engine, "session_policy_readback", None)
    thread_policy = getattr(engine, "thread_policy", None)
    if (not isinstance(providers, dict) or set(providers) != expected_graphs
            or not isinstance(session_policy, dict) or set(session_policy) != expected_graphs
            or not isinstance(thread_policy, dict)):
        raise Refusal("Ultra engine graph/session readbacks are incomplete")
    for name, registered in providers.items():
        row = session_policy[name]
        if (not isinstance(registered, (list, tuple)) or not registered
                or registered[0] != "CUDAExecutionProvider"
                or any(item not in ("CUDAExecutionProvider", "CPUExecutionProvider")
                       for item in registered)
                or not isinstance(row, dict)
                or row.get("provider_readback") != list(registered)
                or row.get("requested_providers") != ["CUDAExecutionProvider"]
                or row.get("disable_cpu_ep_fallback") != "1"
                or row.get("constructor_fallback_disabled") is not True
                or row.get("runtime_disable_invoked") is not True
                or row.get("runtime_fallback_disabled") is not True
                or row.get("runtime_fallback_readback") is not False
                or row.get("ort_device_readback") != "GPU"
                or row.get("intra_op_threads") != 1
                or row.get("inter_op_threads") != 1
                or row.get("use_per_session_threads") is not False):
            raise Refusal("Ultra graph fallback/device/thread readback is unsafe")
    if (thread_policy.get("ort_shared_pool_intra_op_threads") != 1
            or thread_policy.get("ort_shared_pool_inter_op_threads") != 1
            or thread_policy.get("ort_shared_global_pool_configured") is not True
            or any(os.environ.get(name) != "1" for name in THREAD_ENV)):
        raise Refusal("Ultra ORT thread-pool configuration is not one")


def _process_os_thread_count() -> int:
    """Read actual OS threads for this process; ORT pool sizes are not this count."""
    try:
        import psutil
        count = int(psutil.Process(os.getpid()).num_threads())
    except Exception as exc:
        raise Refusal("process OS thread census unavailable (%s)" % type(exc).__name__) from None
    if count <= 0:
        raise Refusal("process OS thread census returned an invalid count")
    return count


def _create_engine(model_dir: Path):
    for name in THREAD_ENV:
        os.environ[name] = "1"
    if str(WORKER) not in sys.path:
        sys.path.insert(0, str(WORKER))
    import parakeet_ultra
    return parakeet_ultra.OnnxBackend(model_dir, threads=1)


def _decode_wav(path: Path, expected_audio_s: float):
    try:
        with wave.open(str(path), "rb") as audio:
            if (audio.getframerate() != 16000 or audio.getnchannels() != 1
                    or audio.getsampwidth() != 2 or audio.getnframes() <= 0):
                raise Refusal("audio format differs from the validated FLEURS WAV")
            frames = audio.getnframes()
            raw = audio.readframes(frames)
    except (wave.Error, EOFError, OSError):
        raise Refusal("audio decode failed") from None
    if len(raw) != frames * 2:
        raise Refusal("audio WAV data is truncated")
    audio_s = frames / 16000.0
    if abs(audio_s - expected_audio_s) > 0.01:
        raise Refusal("decoded audio duration differs from its pinned metadata")
    import numpy as np
    pcm = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    return pcm, audio_s


def _validate_result_row(row: dict, expected: dict, cache_key: str) -> None:
    if (not isinstance(row, dict) or row.get("schema") != SCHEMA
            or row.get("completed") is not True or row.get("cache_key") != cache_key
            or row.get("id") != expected["id"]
            or row.get("audio_sha256") != expected["audio_sha256"]
            or row.get("audio_bytes") != expected["audio_bytes"]
            or row.get("audio_s") != expected["audio_s"]
            or not isinstance(row.get("text"), str)
            or _sha(row["text"].encode("utf-8")) != row.get("text_sha256")
            or row.get("state") not in ("done", "empty")):
        raise Refusal("cached completed hypothesis identity is invalid")
    if (row["state"] == "empty") != (row["text"].strip() == ""):
        raise Refusal("cached transcript state is invalid")
    if len(row["text"].encode("utf-8")) > 128 * 1024:
        raise Refusal("cached transcript row exceeds its private size budget")
    for key, allow_zero in (("decode_s", True), ("inference_s", False),
                            ("load_s", False), ("ready_s", False), ("audio_s", False)):
        value = row.get(key)
        if (not isinstance(value, (int, float)) or not math.isfinite(value)
                or value < 0 or (not allow_zero and value == 0)):
            raise Refusal("cached timing is invalid")
    for key in ("process_os_threads_before", "process_os_threads_ready",
                "process_os_threads_ceiling"):
        value = row.get(key)
        if not isinstance(value, int) or value <= 0:
            raise Refusal("cached process OS thread census is invalid")
    if (row["process_os_threads_ceiling"] != MAX_PROCESS_OS_THREADS
            or max(row["process_os_threads_before"], row["process_os_threads_ready"])
            > row["process_os_threads_ceiling"]):
        raise Refusal("cached process OS thread census exceeds its ceiling")


def _read_resume(path: Path, expected_rows: list[dict], cache_key: str) -> dict[str, dict]:
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_JSONL_BYTES:
        raise Refusal("private hypothesis cache is not a bounded regular file")
    by_id = {row["id"]: row for row in expected_rows}
    found = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if not line.strip():
                raise Refusal("private hypothesis cache contains a blank row")
            row = json.loads(line)
            sample_id = row.get("id") if isinstance(row, dict) else None
            if sample_id not in by_id or sample_id in found:
                raise Refusal("private hypothesis IDs are not one-to-one")
            _validate_result_row(row, by_id[sample_id], cache_key)
            found[sample_id] = row
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("private hypothesis cache is malformed") from None
    return found


def _write_hypotheses(path: Path, expected_rows: list[dict], rows: dict[str, dict]) -> None:
    ordered = [rows[row["id"]] for row in expected_rows if row["id"] in rows]
    raw = b"".join(_canonical(row) + b"\n" for row in ordered)
    _atomic_write(path, raw, limit=MAX_JSONL_BYTES)


def _execute(manifest_path: Path, rows_expected: list[dict], manifest_sha: str,
             model_identity: dict, code_identity: dict, cache_dir: Path,
             engine_factory, scorer, *, clock=time.perf_counter, decode_fn=None,
             thread_census_fn=_process_os_thread_count):
    cache_dir.mkdir(parents=True, exist_ok=True)
    if cache_dir.is_symlink():
        raise Refusal("content-addressed result directory is a symlink")
    hypotheses_path = cache_dir / "hypotheses.jsonl"
    report_path = cache_dir / "score.json"
    cache_key = cache_dir.name
    found = _read_resume(hypotheses_path, rows_expected, cache_key)
    hits = len(found)
    missing = [row for row in rows_expected if row["id"] not in found]
    if missing:
        try:
            process_threads_before = int(thread_census_fn())
        except Refusal:
            raise
        except Exception as exc:
            raise Refusal("process OS thread census failed (%s)" % type(exc).__name__) from None
        if process_threads_before <= 0 or process_threads_before > MAX_PROCESS_OS_THREADS:
            raise Refusal("process OS thread census exceeds its pre-load ceiling")
        load_started = clock()
        try:
            with open(os.devnull, "w", encoding="utf-8") as sink:
                with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                    engine = engine_factory()
        except Exception as exc:
            raise Refusal("Ultra engine creation failed (%s)" % type(exc).__name__) from None
        load_s = clock() - load_started
        expected_graphs = set(model_identity["session_graphs"])
        _validate_engine(engine, expected_graphs)
        try:
            process_threads_ready = int(thread_census_fn())
        except Refusal:
            raise
        except Exception as exc:
            raise Refusal("process OS thread census failed (%s)" % type(exc).__name__) from None
        if process_threads_ready <= 0 or process_threads_ready > MAX_PROCESS_OS_THREADS:
            raise Refusal("process OS thread census exceeds its pre-audio ceiling")
        ready_s = clock() - load_started
        if not all(math.isfinite(value) and value > 0 for value in (load_s, ready_s)):
            raise Refusal("Ultra load/readiness timing is invalid")
        for item in missing:
            started_decode = clock()
            try:
                with open(os.devnull, "w", encoding="utf-8") as sink:
                    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                        pcm, audio_s = (decode_fn or _decode_wav)(
                            item["audio_path"], item["audio_s"])
            except Refusal:
                raise
            except Exception as exc:
                raise Refusal("FLEURS audio decode failed (%s)" % type(exc).__name__) from None
            decode_s = clock() - started_decode
            if not math.isfinite(decode_s) or decode_s < 0:
                raise Refusal("audio decode timing is invalid")

            infer_started = clock()
            try:
                with open(os.devnull, "w", encoding="utf-8") as sink:
                    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                        result = engine.transcribe(pcm)
            except Exception as exc:
                raise Refusal("Ultra transcribe failed (%s)" % type(exc).__name__) from None
            inference_s = clock() - infer_started
            if (not isinstance(result, tuple) or len(result) != 2
                    or not isinstance(result[0], str)):
                raise Refusal("Ultra backend returned an invalid transcript result")
            text = result[0].strip()
            if len(text.encode("utf-8")) > 128 * 1024:
                raise Refusal("Ultra transcript exceeds its private row budget")
            if not math.isfinite(inference_s) or inference_s <= 0:
                raise Refusal("Ultra inference timing is invalid")
            _validate_engine(engine, expected_graphs)
            row = {
                "schema": SCHEMA, "completed": True, "cache_key": cache_key,
                "id": item["id"], "audio_sha256": item["audio_sha256"],
                "audio_bytes": item["audio_bytes"], "audio_s": audio_s,
                "decode_s": round(decode_s, 6),
                "inference_s": round(inference_s, 6),
                "load_s": round(load_s, 6), "ready_s": round(ready_s, 6),
                "process_os_threads_before": process_threads_before,
                "process_os_threads_ready": process_threads_ready,
                "process_os_threads_ceiling": MAX_PROCESS_OS_THREADS,
                "text": text, "text_sha256": _sha(text.encode("utf-8")),
                "state": "empty" if not text else "done",
            }
            _validate_result_row(row, item, cache_key)
            found[item["id"]] = row
            _write_hypotheses(hypotheses_path, rows_expected, found)
    if set(found) != {row["id"] for row in rows_expected}:
        raise Refusal("Ultra hypotheses do not cover the pinned FLEURS cohort")
    score = scorer.score(manifest_path, hypotheses_path,
                         "Parakeet Ultra ONNX CUDA via Sotto OnnxBackend", manifest_sha)
    first = next(iter(found.values()))
    decode_times = [row["decode_s"] for row in found.values()]
    score.update({
        "engine": MODEL_ROUTE,
        "model_load_s": first["load_s"],
        "ready_s": first["ready_s"],
        "audio_decode_s_total": round(sum(decode_times), 6),
        "audio_decode_s_p50": _percentile(decode_times, 0.50),
        "audio_decode_s_p95": _percentile(decode_times, 0.95),
        "process_os_threads_before_model_load": first["process_os_threads_before"],
        "process_os_threads_ready_before_audio": first["process_os_threads_ready"],
        "process_os_threads_ceiling": first["process_os_threads_ceiling"],
    })
    report = {
        "schema": SCHEMA, "cache_key": cache_key, "score": score,
        "model_identity": model_identity,
        "code_identity": code_identity,
        "hypotheses_sha256": _sha(hypotheses_path.read_bytes()),
        "provider_claim_scope": (
            "registered CUDA-first provider + CPU node fallback disabled; "
            "per-node placement is not instrumented"),
        "thread_policy": {
            "ort_pool_intra_op_threads": 1,
            "ort_pool_inter_op_threads": 1,
            "process_os_threads_before_model_load": first["process_os_threads_before"],
            "process_os_threads_ready_before_audio": first["process_os_threads_ready"],
            "process_os_thread_ceiling": first["process_os_threads_ceiling"],
        },
    }
    _atomic_write(report_path, _canonical(report) + b"\n", limit=MAX_REPORT_BYTES)
    return report, hits, len(missing)


def _percentile(values: list[float], q: float):
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lo, hi = math.floor(index), math.ceil(index)
    if lo == hi:
        return round(ordered[lo], 6)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (index - lo), 6)


def _runtime_identity():
    for distribution in ("onnxruntime-gpu", "onnxruntime"):
        try:
            return {"distribution": distribution,
                    "version": importlib.metadata.version(distribution)}
        except importlib.metadata.PackageNotFoundError:
            continue
    raise Refusal("ONNX Runtime distribution version is unavailable")


def _public_summary(report: dict, hits: int, executed: int, cache_dir: Path) -> str:
    score = report["score"]
    return json.dumps({
        "status": "complete", "dataset": score.get("dataset"),
        "samples": score.get("samples"), "coverage": score.get("coverage"),
        "manifest_sha256": score.get("manifest_sha256"),
        "hypotheses_sha256": report.get("hypotheses_sha256"),
        "model_sha256": report.get("model_identity", {}).get("sha256"),
        "model_bytes_hashed": report.get("model_identity", {}).get("content_bytes_hashed"),
        "model_identity_cache_hit": report.get("model_identity", {}).get("cache_hit"),
        "onnxruntime": report.get("runtime"),
        "provider_claim_scope": report.get("provider_claim_scope"),
        "wer": score.get("wer"), "cer_no_whitespace": score.get("cer_no_whitespace"),
        "rtf": score.get("rtf"), "model_load_s": score.get("model_load_s"),
        "ready_s": score.get("ready_s"),
        "inference_s_p50": score.get("inference_s_p50"),
        "inference_s_p95": score.get("inference_s_p95"),
        "inference_s_p99": score.get("inference_s_p99"),
        "thread_policy": report.get("thread_policy"),
        "audio_decode_s_p50": score.get("audio_decode_s_p50"),
        "audio_decode_s_p95": score.get("audio_decode_s_p95"),
        "cache_hits": hits, "samples_executed": executed,
        "cache_dir": str(cache_dir),
    }, ensure_ascii=False, sort_keys=True)


def _selftest_manifest(base: Path):
    records = []
    for sample_id, seed in (("a", 1), ("b", 2)):
        wav_path = base / (sample_id + ".wav")
        with wave.open(str(wav_path), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(16000)
            out.writeframes(bytes((seed, 0)) * 160)
        audio_sha, audio_bytes = _hash_file(wav_path)
        content_path = base / (audio_sha + ".wav")
        wav_path.replace(content_path)
        reference = "ULTRA_PRIVATE_SENTINEL"
        records.append({
            "id": sample_id, "audio_sha256": audio_sha,
            "audio_bytes": audio_bytes, "reference": reference,
            "reference_sha256": _sha(reference.encode("utf-8")),
        })
    sidecar_raw = b"synthetic FLEURS transcript sidecar\n"
    sidecar_sha = _sha(sidecar_raw)
    manifest = {"dataset": "synthetic FLEURS", "transcript_sha256": sidecar_sha,
                "records": records}
    manifest_path = base / "synthetic.manifest.json"
    manifest_path.write_bytes(_canonical(manifest))
    (base / (sidecar_sha + ".trans.txt")).write_bytes(sidecar_raw)
    return manifest_path, _sha(manifest_path.read_bytes())


def _selftest_engine(*, device="cuda", runtime_disabled=True, cpu_fallback="1",
                     provider="CUDAExecutionProvider", thread_count=1,
                     include_vad=False):
    graphs = ("preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx")
    if include_vad:
        graphs += ("vad-model.onnx",)
    provider_map = {name: [provider, "CPUExecutionProvider"] for name in graphs}
    policy = {name: {
        "provider_readback": provider_map[name],
        "requested_providers": ["CUDAExecutionProvider"],
        "disable_cpu_ep_fallback": cpu_fallback,
        "constructor_fallback_disabled": True,
        "runtime_disable_invoked": True,
        "runtime_fallback_disabled": runtime_disabled,
        "runtime_fallback_readback": not runtime_disabled,
        "ort_device_readback": "GPU" if device == "cuda" else "CPU",
        "intra_op_threads": thread_count, "inter_op_threads": 1,
        "use_per_session_threads": False,
    } for name in graphs}

    class FakeEngine:
        def __init__(self):
            self.device = device
            self.frontend_device = device
            self.ort_device_readback = "GPU" if device == "cuda" else "CPU"
            self.cpu_ep_fallback_disabled = cpu_fallback == "1"
            self.ort_intra_op_threads = thread_count
            self.provider_readback = provider_map
            self.session_policy_readback = policy
            self.thread_policy = {"ort_shared_pool_intra_op_threads": 1,
                                  "ort_shared_pool_inter_op_threads": 1,
                                  "ort_shared_global_pool_configured": True}
            self.calls = 0

        def transcribe(self, _pcm):
            self.calls += 1
            return "ULTRA_PRIVATE_SENTINEL", []

    return FakeEngine()


def selftest() -> None:
    forbidden = {"numpy", "soundfile", "onnxruntime", "torch", "parakeet_ultra", "sotto_worker"}
    if forbidden.intersection(sys.modules):
        raise Refusal("selftest began after an audio/model/GPU module import")
    agent_work = ROOT / ".agent-work"
    agent_work.mkdir(parents=True, exist_ok=True)
    if ROOT.drive.upper() != "H:" or agent_work.drive.upper() != "H:":
        raise Refusal("synthetic scratch must remain on H:")
    total_bytes = None
    with tempfile.TemporaryDirectory(prefix="fleurs-ultra-fake-", dir=agent_work) as temp_name:
        temp = Path(temp_name)
        manifest_path, manifest_sha = _selftest_manifest(temp)
        manifest, expected, actual_sha = _verify_manifest(
            manifest_path, manifest_sha, required_count=2,
            enforce_pinned=False, paced_hashes=False)
        if actual_sha != manifest_sha or manifest.get("dataset") != "synthetic FLEURS":
            raise Refusal("synthetic manifest verification failed")
        model_dir = temp / "parakeet-ultra-fake"
        model_dir.mkdir()
        for name in sorted(REQUIRED_MODEL_FILES | {"vad-model.onnx"}):
            (model_dir / name).write_bytes(("fake:" + name).encode("ascii"))
        cache_root = temp / "cache"
        _recover_identity_cache(cache_root)
        identity = _model_identity(model_dir, cache_root)
        identity_hit = _model_identity(model_dir, cache_root)
        if (identity_hit["sha256"] != identity["sha256"]
                or identity_hit["cache_hit"] != identity_hit["change_token_cache"]):
            raise Refusal("Ultra model identity did not use a trustworthy cache token")

        # A changed model must invalidate the cached fingerprint and rebuild
        # the identity instead of making the runner refuse permanently.
        changed_cache = temp / "changed-model-cache"
        changed_target = model_dir / "encoder-model.onnx"
        changed_original = changed_target.read_bytes()
        try:
            changed_target.write_bytes(bytes((byte ^ 1) for byte in changed_original))
            changed_identity = _model_identity(model_dir, changed_cache)
            if (changed_identity["sha256"] == identity["sha256"]
                    or changed_identity["cache_hit"]):
                raise Refusal("changed model did not trigger a fresh content identity")
        finally:
            changed_target.write_bytes(changed_original)
        restored_identity = _model_identity(model_dir, changed_cache)
        if (restored_identity["sha256"] != identity["sha256"]
                or restored_identity["cache_hit"]):
            raise Refusal("restored model bytes did not rebuild the content identity")

        # Adverse replay for Windows metadata semantics: hold every reported
        # metadata field constant, alter same-size content, and prove absent
        # change tokens force content hashing instead of a stale SHA hit.
        stable_cache = temp / "stable-metadata-cache"
        actual_fingerprint = _file_fingerprint
        stable_rows = {}

        def frozen_metadata(path):
            if path.name not in stable_rows:
                row = dict(actual_fingerprint(path))
                row["usn"] = None
                stable_rows[path.name] = row
            return dict(stable_rows[path.name])

        target = model_dir / "encoder-model.onnx"
        original = target.read_bytes()
        original_stat = target.stat()
        try:
            globals()["_file_fingerprint"] = frozen_metadata
            before_mutation = _model_identity(model_dir, stable_cache)
            target.write_bytes(bytes((byte ^ 1) for byte in original))
            os.utime(target, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            after_mutation = _model_identity(model_dir, stable_cache)
            if (before_mutation["sha256"] == after_mutation["sha256"]
                    or after_mutation["cache_hit"]
                    or after_mutation["change_token_cache"]):
                raise Refusal("same-size restored-mtime mutation reused stale model identity")
        finally:
            target.write_bytes(original)
            os.utime(target, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            globals()["_file_fingerprint"] = actual_fingerprint

        identity_paths = {}
        identity_source = temp / "code-identity"
        identity_source.mkdir()
        for label in ("runner", "worker", "worker_bootstrap", "scorer"):
            path = identity_source / (label + ".py")
            path.write_text("baseline:" + label, encoding="utf-8")
            identity_paths[label] = path
        code_before = _code_identity(identity_paths)
        identity_paths["worker_bootstrap"].write_text("changed:worker_bootstrap", encoding="utf-8")
        code_after = _code_identity(identity_paths)
        if code_before["worker_bootstrap"] == code_after["worker_bootstrap"]:
            raise Refusal("Sotto worker bootstrap was absent from code identity")

        scorer = _load_scorer()
        results_root = cache_root / RESULTS_DIRNAME
        key_a = "a" * 64
        result_a = results_root / key_a
        _maintain_result_cache(results_root, key_a)
        engine = _selftest_engine(include_vad="vad-model.onnx" in identity["session_graphs"])
        decode_calls = [0]

        def fake_decode(_path, audio_s):
            decode_calls[0] += 1
            return [0.0] * 160, audio_s

        factory_calls = [0]

        def valid_factory():
            factory_calls[0] += 1
            return engine

        stdout = []
        report, hits, executed = _execute(
            manifest_path, expected, manifest_sha, identity, _code_identity(),
            result_a, valid_factory, scorer, decode_fn=fake_decode,
            thread_census_fn=lambda: 12)
        stdout.append(_public_summary(report, hits, executed, result_a))
        if (engine.calls != 2 or decode_calls[0] != 2 or factory_calls[0] != 1
                or hits != 0 or executed != 2):
            raise Refusal("fake Ultra route did not run exactly once per FLEURS row")
        if (report["score"].get("coverage") != "complete"
                or report["score"].get("ready_s", 0) <= 0
                or report["score"].get("model_load_s", 0) <= 0
                or report["score"].get("inference_seconds", 0) <= 0):
            raise Refusal("load/readiness/inference metrics are incomplete")
        if "ULTRA_PRIVATE_SENTINEL" in "".join(stdout) or "ULTRA_PRIVATE_SENTINEL" in json.dumps(report):
            raise Refusal("private transcript text leaked into aggregate output")
        hypotheses = result_a / "hypotheses.jsonl"
        if "ULTRA_PRIVATE_SENTINEL" not in hypotheses.read_text(encoding="utf-8"):
            raise Refusal("private hypothesis artifact does not contain scorer inputs")
        if (report["thread_policy"]["ort_pool_intra_op_threads"] != 1
                or report["thread_policy"]["process_os_threads_before_model_load"] != 12
                or report["thread_policy"]["process_os_threads_ready_before_audio"] != 12):
            raise Refusal("ORT pool and process OS thread counts were not reported separately")
        _maintain_result_cache(results_root, key_a)

        def no_rebuild():
            raise Refusal("complete cache attempted to construct another Ultra engine")

        _, resumed_hits, resumed_executed = _execute(
            manifest_path, expected, manifest_sha, identity, _code_identity(),
            result_a, no_rebuild, scorer, decode_fn=fake_decode,
            thread_census_fn=lambda: 12)
        if resumed_hits != 2 or resumed_executed != 0 or factory_calls[0] != 1:
            raise Refusal("completed content-addressed hypotheses did not resume")

        key_b = "b" * 64
        _maintain_result_cache(results_root, key_b)
        engine_b = _selftest_engine(include_vad=True)
        _execute(manifest_path, expected, manifest_sha, identity, _code_identity(),
                 results_root / key_b, lambda: engine_b, scorer,
                 decode_fn=fake_decode, thread_census_fn=lambda: 12)
        _maintain_result_cache(results_root, key_b)
        if {row["key"] for row in _result_cache_inventory(results_root)} != {key_a, key_b}:
            raise Refusal("second cache generation did not retain only two generations")

        # Simulate a crash during the third generation: one atomic destination
        # is valid, temp siblings are partial, and a complete prior generation
        # must remain available for the next serialized execution.
        key_c = "c" * 64
        result_c = results_root / key_c
        result_c.mkdir()
        cached_a_rows = [json.loads(line) for line in hypotheses.read_text(encoding="utf-8").splitlines()]
        partial = dict(cached_a_rows[0])
        partial["cache_key"] = key_c
        _write_hypotheses(result_c / "hypotheses.jsonl", expected, {partial["id"]: partial})
        (result_c / "hypotheses.jsonl.tmp").write_bytes(b"interrupted atomic write")
        (result_c / "score.json.tmp").write_bytes(b"interrupted report")
        _maintain_result_cache(results_root, key_c)
        if ((result_c / "hypotheses.jsonl.tmp").exists()
                or (result_c / "score.json.tmp").exists()
                or not (results_root / key_b / "score.json").is_file()):
            raise Refusal("crash recovery did not preserve atomic destinations")
        engine_c = _selftest_engine(include_vad=True)
        _, crash_hits, crash_executed = _execute(
            manifest_path, expected, manifest_sha, identity, _code_identity(),
            result_c, lambda: engine_c, scorer, decode_fn=fake_decode,
            thread_census_fn=lambda: 12)
        _maintain_result_cache(results_root, key_c)
        inventory = _result_cache_inventory(results_root)
        retained = {row["key"] for row in inventory}
        total_retained = sum(path.stat().st_size for row in inventory for path in row["files"])
        if (crash_hits != 1 or crash_executed != 1 or retained != {key_b, key_c}
                or total_retained > MAX_RESULT_CACHE_BYTES):
            raise Refusal("bounded two-generation crash resume failed")

        bad_cases = (
            _selftest_engine(device="cpu", include_vad=True),
            _selftest_engine(cpu_fallback="0", include_vad=True),
            _selftest_engine(runtime_disabled=False, include_vad=True),
            _selftest_engine(provider="CPUExecutionProvider", include_vad=True),
            _selftest_engine(thread_count=2, include_vad=True),
            _selftest_engine(include_vad=False),
        )
        for index, bad in enumerate(bad_cases):
            calls = [0]

            def should_not_decode(_path, _audio_s):
                calls[0] += 1
                raise AssertionError("audio decoded before unsafe engine refusal")

            try:
                _execute(manifest_path, expected, manifest_sha, identity, _code_identity(),
                         temp / "refused" / str(index), lambda bad=bad: bad, scorer,
                         decode_fn=should_not_decode, thread_census_fn=lambda: 12)
            except Refusal:
                pass
            else:
                raise Refusal("unsafe Ultra engine was accepted")
            if calls[0] != 0:
                raise Refusal("unsafe Ultra engine was refused after audio decode")

        blocked_decode_calls = [0]

        def should_not_decode_for_thread_cap(_path, _audio_s):
            blocked_decode_calls[0] += 1
            raise AssertionError("audio decode reached before thread policy passed")

        factories_before_cap = factory_calls[0]
        decode_calls_before_cap = decode_calls[0]
        try:
            _execute(manifest_path, expected, manifest_sha, identity, _code_identity(),
                     temp / "thread-cap-before", valid_factory, scorer,
                     decode_fn=should_not_decode_for_thread_cap,
                     thread_census_fn=lambda: MAX_PROCESS_OS_THREADS + 1)
        except Refusal:
            pass
        else:
            raise Refusal("OS thread ceiling was not enforced before model load")
        if (blocked_decode_calls[0] != 0 or factory_calls[0] != factories_before_cap):
            raise Refusal("pre-load OS thread refusal reached model creation or audio decode")
        over_ready = iter((12, MAX_PROCESS_OS_THREADS + 1))
        try:
            _execute(manifest_path, expected, manifest_sha, identity, _code_identity(),
                     temp / "thread-cap-ready", valid_factory, scorer,
                     decode_fn=should_not_decode_for_thread_cap,
                     thread_census_fn=lambda: next(over_ready))
        except Refusal:
            pass
        else:
            raise Refusal("OS thread ceiling was not enforced before audio decode")
        if (blocked_decode_calls[0] != 0
                or factory_calls[0] != factories_before_cap + 1):
            raise Refusal("post-init OS thread refusal missed its before-audio boundary")
        if decode_calls[0] != decode_calls_before_cap:
            raise Refusal("OS thread refusal changed the completed baseline decode count")

        try:
            _require_h_path(Path("C:/outside/model"), "model directory", must_exist=False)
        except Refusal:
            pass
        else:
            raise Refusal("model directory outside H: was accepted")
        try:
            _verify_manifest(manifest_path, "0" * 64, required_count=2,
                             enforce_pinned=False, paced_hashes=False)
        except Refusal:
            pass
        else:
            raise Refusal("wrong manifest hash was accepted")

        saved = expected[0]["audio_path"].read_bytes()
        expected[0]["audio_path"].write_bytes(saved[:-1] + bytes((saved[-1] ^ 1,)))
        try:
            _verify_manifest(manifest_path, manifest_sha, required_count=2,
                             enforce_pinned=False, paced_hashes=False)
        except Refusal:
            pass
        else:
            raise Refusal("mutated audio bytes were accepted")
        expected[0]["audio_path"].write_bytes(saved)

        if forbidden.intersection(sys.modules):
            raise Refusal("fake selftest imported model/audio/GPU libraries")
        total_bytes = sum(path.stat().st_size for path in temp.rglob("*") if path.is_file())
        if total_bytes > MAX_CACHE_BYTES:
            raise Refusal("synthetic artifacts exceeded the 2 MiB ceiling")
    if temp.exists() or total_bytes is None or total_bytes > MAX_CACHE_BYTES:
        raise Refusal("synthetic scratch cleanup or size proof failed")
    print("SELFTEST PASS: metadata-restored model mutation, bootstrap code identity, late VAD session readback, graph-set refusal, two-generation crash-safe cache, OS-thread ceiling before audio, aggregate-only FLEURS resume, <=2MiB scratch")


def _run_locked(manifest_path: Path, model_dir: Path, cache_root: Path,
                expected: list[dict], manifest_sha: str) -> None:
    _retire_legacy_result_cache(cache_root)
    _recover_identity_cache(cache_root)
    model_identity = _model_identity(model_dir, cache_root)
    source_identity = _code_identity()
    runtime = _runtime_identity()
    identity = {
        "schema": SCHEMA,
        "manifest_sha256": manifest_sha,
        "audio": [(row["id"], row["audio_sha256"], row["audio_bytes"])
                  for row in expected],
        "model_sha256": model_identity["sha256"],
        "model_files": model_identity["files"],
        "model_bytes": model_identity["bytes"],
        "source_sha256": source_identity,
        "onnxruntime": runtime,
        "route": MODEL_ROUTE,
        "device": "CUDA only; CPU EP and Python fallback disabled",
        "ort_thread_pool_config": {"intra_op": 1, "inter_op": 1},
        "process_os_thread_ceiling": MAX_PROCESS_OS_THREADS,
    }
    cache_key = _sha(_canonical(identity))
    results_root = cache_root / RESULTS_DIRNAME
    _maintain_result_cache(results_root, cache_key)
    result_dir = _require_h_path(results_root / cache_key,
                                 "content-addressed result", must_exist=False)
    scorer = _load_scorer()
    report, cache_hits, executed = _execute(
        manifest_path, expected, manifest_sha, model_identity,
        source_identity, result_dir, lambda: _create_engine(model_dir), scorer)
    report["runtime"] = runtime
    report["model_identity"]["identity_s"] = round(model_identity["identity_s"], 6)
    report["model_identity"]["content_bytes_hashed"] = model_identity["content_bytes_hashed"]
    report["model_identity"]["cache_hit"] = model_identity["cache_hit"]
    _atomic_write(result_dir / "score.json", _canonical(report) + b"\n",
                  limit=MAX_REPORT_BYTES)
    _maintain_result_cache(results_root, cache_key)
    print(_public_summary(report, cache_hits, executed, result_dir))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true", help="run only model-free synthetic fakes")
    parser.add_argument("--expected-manifest-sha256", default=PINNED_MANIFEST_SHA256)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_DEFAULT)
    parser.add_argument("--model-dir", type=Path, default=MODEL_DEFAULT)
    parser.add_argument("--cache-root", type=Path, default=CACHE_DEFAULT)
    args = parser.parse_args(argv)
    try:
        if args.selftest:
            selftest()
            return 0
        if args.expected_manifest_sha256 != PINNED_MANIFEST_SHA256:
            raise Refusal("exact pinned FLEURS manifest SHA-256 is mandatory")
        if ROOT.drive.upper() != "H:":
            raise Refusal("runner checkout must be on H:")
        manifest_path = _require_h_path(args.manifest, "manifest", must_exist=True)
        model_dir = _require_h_path(args.model_dir, "Ultra model directory", must_exist=True)
        cache_root = _require_h_path(args.cache_root, "private cache", must_exist=False)
        manifest, expected, manifest_sha = _verify_manifest(
            manifest_path, args.expected_manifest_sha256)
        cache_root.mkdir(parents=True, exist_ok=True)
        with _cache_lease(cache_root):
            _run_locked(manifest_path, model_dir, cache_root, expected, manifest_sha)
        return 0
    except Refusal as exc:
        safe = re.sub(r"[^a-zA-Z0-9 _:-]", "", str(exc))[:120]
        print("REFUSED: " + safe, file=sys.stderr)
        return 2
    except Exception as exc:
        print("FAILED: " + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
