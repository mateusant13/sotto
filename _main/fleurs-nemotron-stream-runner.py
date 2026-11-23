#!/usr/bin/env python3
"""Replay the pinned FLEURS pt-BR cohort through Sotto's CUDA-only stream path.

Only aggregate timing/coverage is printed. Private scorer-compatible hypotheses
stay in the H: content-addressed cache. The default invocation refuses until the
caller approves the derived three-session ORT intra-op pool total.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import math
import os
import re
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
WORKER_DIR = ROOT / "worker"
MANIFEST_DEFAULT = ROOT / ".agent-work/asr-cache/fleurs/pt_br/b74b61db926bee40ba21ab385264b0e8cbc89d4d10f93a4c51bcb54e95f3033c.manifest.json"
MODEL_DEFAULT = WORKER_DIR / "models/nemotron-3.5-asr-ptbr-onnx-int4"
DEFAULT_CACHE = ROOT / ".agent-work/asr-cache/fleurs-nemotron"
SCORER_PATH = ROOT / "_main/asr-reference-score.py"
PINNED_MANIFEST_SHA256 = "b74b61db926bee40ba21ab385264b0e8cbc89d4d10f93a4c51bcb54e95f3033c"
PINNED_MODEL_REVISION = "8364d9e2dd9da23789b480bdbba9e423717e42ee"
PINNED_MODEL_TREE_SHA256 = "d66b9896e1c6c56e54551f27241c5023ccf13ef86e72f0c58e61ac4add625ac4"
PINNED_MODEL_LFS_SHA256 = {
    "decoder.onnx": "6a9f608dcbab71ebd81ffa4c198e82a5b6bb10f1c1830a94c752c5f543454df3",
    "decoder.onnx.data": "e5fd55cbeeb268f9d383e2ee72735b9fbbb13aea4bc7cd38cb73b8e16f1366c7",
    "encoder.onnx": "0b05217594ec0bda442e43a90a298ac2471a3bdcea9b169de34214e61a730e17",
    "encoder.onnx.data": "2f27295855aeb99ab1f8cd2254418d9ad7a087ea8dbe85f5596b4d887ea7d630",
    "joint.onnx": "e2c7d2fa40a243bf82eaca36c15698c52129de9361d2875d7f223f67fcd9482d",
    "joint.onnx.data": "2e0fb1c060f3777a1a76e78d5589dd54f01505a06dffbd2588e315508b402c12",
    "silero_vad.onnx": "a4a068cd6cf1ea8355b84327595838ca748ec29a25bc91fc82e6c299ccdc5808",
}
EXPECTED_SAMPLES = 20
EXPECTED_AUDIO_BYTES = 8_385_520
EXPECTED_REFERENCES = 450
TARGET_SR = 16_000
CHUNK_SAMPLES = 8_960
CUDA_PROVIDER = "CUDAExecutionProvider"
MODEL_LINEAGE = "Nemotron PT-BR fine-tune of the cache-aware streaming model"
THREAD_ENV = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
              "NUMEXPR_NUM_THREADS", "ORT_INTRA_OP_NUM_THREADS",
              "ORT_INTER_OP_NUM_THREADS", "SOTTO_SMALL_GRAPH_THREADS")
MAX_MANIFEST_BYTES = 1 * 1024 * 1024
MAX_AUDIO_BYTES = 9 * 1024 * 1024
MAX_COHORT_AUDIO_BYTES = EXPECTED_AUDIO_BYTES
MAX_TRANSCRIPT_SIDECAR_BYTES = 2 * 1024 * 1024
MAX_HYPOTHESIS_BYTES = 1 * 1024 * 1024
MAX_CACHE_BYTES = 2 * 1024 * 1024
MAX_ROW_TEXT_BYTES = 256 * 1024
MAX_MODEL_FILES = 64
MAX_MODEL_BYTES = 1_000_000_000
MAX_MODEL_RECEIPT_BYTES = 64 * 1024
MAX_MODEL_FILE_HASH_BYTES = MAX_MODEL_BYTES
MAX_RESULT_CACHE_FILES = 5
MAX_RESULT_CACHE_BYTES = MAX_RESULT_CACHE_FILES * MAX_HYPOTHESIS_BYTES
MAX_CACHE_DIR_ENTRIES = 4096
MAX_PROCESS_TID_SCAN = 16384
MAX_RUNTIME_MODULE_METADATA_BYTES = 16 * 1024
MAX_RUNTIME_BUILD_INFO_CHARS = 4096
MAX_RUNTIME_NATIVE_FILES = 32
MAX_RUNTIME_MODULES = 32768
HASH_READ_BYTES_PER_SECOND = 4 * 1024 * 1024
SCHEMA = "sotto-fleurs-nemotron-stream-cuda-v6"
MODEL_TREE = ".cache/huggingface/trees/" + PINNED_MODEL_REVISION + ".json"
MODEL_RECEIPT = "nemotron-model-content-" + PINNED_MODEL_REVISION + ".json"

# Apply the process-wide caps before any project, numeric, audio, or ORT import.
for _env_name in THREAD_ENV:
    os.environ[_env_name] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ.setdefault("CUDA_MODULE_LOADING", "LAZY")
# This runner is explicitly the diagnostic arm: ORT records graph assignment
# before session creation. Its startup/latency results must not be published as
# production-mode latency.
os.environ["SOTTO_ORT_NODE_TRACE"] = "1"
sys.dont_write_bytecode = True
RUNNER_ENTRY = time.perf_counter()


class Refusal(RuntimeError):
    """A bounded, transcript-safe precondition or route refusal."""


def _safe_exception_site(exc: BaseException) -> str:
    """Describe the failing code site without emitting exception arguments."""
    tb = exc.__traceback__
    while tb is not None and tb.tb_next is not None:
        tb = tb.tb_next
    if tb is None:
        return "unknown-site"
    code = tb.tb_frame.f_code
    filename = Path(code.co_filename).name
    function = code.co_name
    label = "%s:%d in %s" % (filename, tb.tb_lineno, function)
    attribute = getattr(exc, "name", None)
    if isinstance(attribute, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", attribute):
        label += " attribute=" + attribute
    return label


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash_file(path: Path, *, max_bytes: int, pace: bool = False) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    started = time.perf_counter()
    with path.open("rb", buffering=0) as stream:
        while True:
            block = stream.read(256 * 1024)
            if not block:
                break
            size += len(block)
            if size > max_bytes:
                raise Refusal("hashed input exceeds its byte budget")
            digest.update(block)
            if pace:
                target = size / HASH_READ_BYTES_PER_SECOND
                wait_s = target - (time.perf_counter() - started)
                if wait_s > 0:
                    time.sleep(wait_s)
    return digest.hexdigest(), size


def _model_file_signature(path: Path):
    """Cheap Windows identity/change receipt; st_ctime is creation time there."""
    if os.name != "nt":
        raise Refusal("model content cache requires Windows change-time support")
    try:
        import ctypes
        import ctypes.wintypes as wt

        class _FileBasicInfo(ctypes.Structure):
            _fields_ = [("CreationTime", ctypes.c_longlong),
                        ("LastAccessTime", ctypes.c_longlong),
                        ("LastWriteTime", ctypes.c_longlong),
                        ("ChangeTime", ctypes.c_longlong),
                        ("FileAttributes", wt.DWORD)]

        class _FileIdInfo(ctypes.Structure):
            _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong),
                        ("FileId", ctypes.c_ubyte * 16)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = wt.HANDLE
        kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD,
                                         ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
        kernel32.GetFileInformationByHandleEx.restype = wt.BOOL
        kernel32.GetFileInformationByHandleEx.argtypes = [
            wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
        kernel32.CloseHandle.restype = wt.BOOL
        kernel32.CloseHandle.argtypes = [wt.HANDLE]
        handle = kernel32.CreateFileW(str(path), 0x80, 0x7, None, 3, 0x80, None)
        invalid = ctypes.c_void_p(-1).value
        if not handle or ctypes.cast(handle, ctypes.c_void_p).value == invalid:
            raise OSError("file identity handle unavailable")
        try:
            basic, file_id = _FileBasicInfo(), _FileIdInfo()
            if not kernel32.GetFileInformationByHandleEx(
                    handle, 0, ctypes.byref(basic), ctypes.sizeof(basic)):
                raise OSError("file change-time unavailable")
            if not kernel32.GetFileInformationByHandleEx(
                    handle, 18, ctypes.byref(file_id), ctypes.sizeof(file_id)):
                raise OSError("file ID unavailable")
            stat = path.stat()
            return {"size": int(stat.st_size), "mtime_ns": int(stat.st_mtime_ns),
                    "change_time_100ns": int(basic.ChangeTime),
                    "volume_serial": int(file_id.VolumeSerialNumber),
                    "file_id": bytes(file_id.FileId).hex()}
        finally:
            kernel32.CloseHandle(handle)
    except Refusal:
        raise
    except Exception:
        raise Refusal("file identity/change-time readback failed closed") from None


def _digest_model_file(path: Path, *, max_bytes: int):
    """One-time SHA-256 and Git-blob verification without retaining model bytes."""
    try:
        size_hint = path.stat().st_size
    except OSError:
        raise Refusal("pinned model file could not be statted") from None
    if size_hint < 0 or size_hint > max_bytes:
        raise Refusal("pinned model file exceeds its hash budget")
    sha256 = hashlib.sha256()
    git_sha1 = hashlib.sha1(("blob %d\0" % size_hint).encode("ascii"))
    size = 0
    try:
        with path.open("rb", buffering=0) as stream:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                size += len(block)
                if size > max_bytes or size > size_hint:
                    raise Refusal("pinned model file changed during its content hash")
                sha256.update(block)
                git_sha1.update(block)
    except Refusal:
        raise
    except OSError:
        raise Refusal("pinned model file content hash failed") from None
    if size != size_hint:
        raise Refusal("pinned model file changed during its content hash")
    return {"sha256": sha256.hexdigest(), "git_blob_sha1": git_sha1.hexdigest(),
            "size": size}


def _reuse_cached_model_digest(cached, signature, *, pinned_lfs, expected_blob):
    """Reuse only an expected digest bound to the exact size/mtime/change-time/file ID."""
    if (not isinstance(cached, dict) or cached.get("signature") != signature
            or not isinstance(cached.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", cached["sha256"])
            or not isinstance(cached.get("git_blob_sha1"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", cached["git_blob_sha1"])):
        return None
    if pinned_lfs:
        return cached if cached["sha256"] == pinned_lfs else None
    return cached if cached["git_blob_sha1"] == expected_blob else None


def _atomic_bytes(path: Path, body: bytes, *, max_bytes: int):
    if len(body) > max_bytes:
        raise Refusal("bounded cache receipt exceeds its byte budget")
    path = _safe_child(ROOT / ".agent-work/asr-cache", path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise Refusal("bounded cache receipt path is a symlink")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".fleurs-nemotron-", suffix=".tmp",
                                         dir=path.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        temp_path = None
    except OSError:
        raise Refusal("bounded H: cache receipt write failed") from None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def _read_hashed_bytes(path: Path, *, max_bytes: int, pace: bool = False):
    """Read once, hash, and retain a small pinned WAV so decode uses same bytes."""
    digest = hashlib.sha256()
    data = bytearray()
    started = time.perf_counter()
    with path.open("rb", buffering=0) as stream:
        while True:
            block = stream.read(256 * 1024)
            if not block:
                break
            data.extend(block)
            if len(data) > max_bytes:
                raise Refusal("hashed input exceeds its byte budget")
            digest.update(block)
            if pace:
                target = len(data) / HASH_READ_BYTES_PER_SECOND
                wait_s = target - (time.perf_counter() - started)
                if wait_s > 0:
                    time.sleep(wait_s)
    return digest.hexdigest(), bytes(data)


def _safe_child(root: Path, candidate: Path) -> Path:
    if candidate.is_symlink():
        raise Refusal("symbolic-link paths are not accepted")
    root = root.resolve()
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        raise Refusal("path is outside the permitted H: workspace") from None
    if candidate.drive.upper() != "H:":
        raise Refusal("all benchmark artifacts must stay on H:")
    return candidate


def _verify_manifest(manifest_path: Path, expected_sha256: str):
    if expected_sha256 != PINNED_MANIFEST_SHA256:
        raise Refusal("only the pinned FLEURS manifest is accepted")
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise Refusal("pinned manifest is unavailable")
    manifest_path = _safe_child(ROOT / ".agent-work/asr-cache/fleurs/pt_br",
                                manifest_path)
    if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
        raise Refusal("pinned manifest exceeds its size budget")
    raw = manifest_path.read_bytes()
    if len(raw) > MAX_MANIFEST_BYTES or _sha(raw) != expected_sha256:
        raise Refusal("pinned manifest SHA-256 or size mismatch")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("pinned manifest is not valid JSON") from None
    if (not isinstance(manifest, dict)
            or manifest.get("dataset") != "Google FLEURS pt_br test"
            or manifest.get("source_repo") != "FluidInference/fleurs-full"
            or manifest.get("revision") != "1cca811bb8ea4d370345f108f00518167040282c"
            or manifest.get("audio_count") != EXPECTED_SAMPLES
            or manifest.get("audio_bytes") != EXPECTED_AUDIO_BYTES):
        raise Refusal("pinned FLEURS cohort metadata mismatch")
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_SAMPLES:
        raise Refusal("pinned FLEURS cohort size mismatch")

    sidecar_sha = manifest.get("transcript_sha256")
    if not isinstance(sidecar_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sidecar_sha):
        raise Refusal("pinned reference sidecar identity is invalid")
    sidecar = manifest_path.with_name(sidecar_sha + ".trans.txt")
    if sidecar.is_symlink() or not sidecar.is_file():
        raise Refusal("pinned reference sidecar is unavailable")
    if sidecar.stat().st_size > MAX_TRANSCRIPT_SIDECAR_BYTES:
        raise Refusal("pinned reference sidecar exceeds its size budget")
    actual_sidecar_sha, _ = _hash_file(sidecar, max_bytes=MAX_TRANSCRIPT_SIDECAR_BYTES)
    if actual_sidecar_sha != sidecar_sha:
        raise Refusal("pinned reference sidecar SHA-256 mismatch")

    seen = set()
    verified = []
    total_audio = 0
    ref_word_count = 0
    for record in records:
        if not isinstance(record, dict):
            raise Refusal("pinned manifest row is invalid")
        sample_id = record.get("id")
        audio_sha = record.get("audio_sha256")
        ref_sha = record.get("reference_sha256")
        reference = record.get("reference")
        try:
            audio_bytes = int(record.get("audio_bytes", 0))
        except (TypeError, ValueError, OverflowError):
            raise Refusal("pinned audio size is invalid") from None
        if (not isinstance(sample_id, str) or not sample_id or sample_id in seen
                or not isinstance(audio_sha, str)
                or not re.fullmatch(r"[0-9a-f]{64}", audio_sha)
                or not isinstance(reference, str)
                or not isinstance(ref_sha, str)
                or _sha(reference.encode("utf-8")) != ref_sha
                or audio_bytes <= 0 or audio_bytes > MAX_AUDIO_BYTES):
            raise Refusal("pinned manifest row identity is invalid")
        seen.add(sample_id)
        ref_word_count += int(record.get("reference_words", 0))
        audio_path = manifest_path.with_name(audio_sha + ".wav")
        if audio_path.is_symlink() or not audio_path.is_file():
            raise Refusal("pinned WAV is unavailable")
        actual_sha, audio_raw = _read_hashed_bytes(audio_path, max_bytes=MAX_AUDIO_BYTES,
                                                    pace=True)
        actual_bytes = len(audio_raw)
        if actual_sha != audio_sha or actual_bytes != audio_bytes:
            raise Refusal("pinned WAV content mismatch")
        try:
            with wave.open(io.BytesIO(audio_raw), "rb") as audio:
                rate = audio.getframerate()
                frames = audio.getnframes()
                channels = audio.getnchannels()
                if rate <= 0 or frames <= 0 or channels <= 0 or channels > 8:
                    raise Refusal("pinned WAV metadata is invalid")
                audio_s = frames / rate
        except (wave.Error, EOFError, OSError):
            raise Refusal("pinned WAV metadata is invalid") from None
        if not math.isfinite(audio_s) or audio_s <= 0:
            raise Refusal("pinned WAV duration is invalid")
        verified.append({"id": sample_id, "audio_path": audio_path,
                         "audio_sha256": audio_sha, "audio_bytes": audio_bytes,
                         "audio_s": audio_s,
                         "_verified_audio_bytes": audio_raw})
        total_audio += audio_bytes
    if (len(seen) != EXPECTED_SAMPLES or total_audio != EXPECTED_AUDIO_BYTES
            or ref_word_count != EXPECTED_REFERENCES):
        raise Refusal("pinned FLEURS cohort totals mismatch")
    if total_audio > MAX_COHORT_AUDIO_BYTES:
        raise Refusal("pinned WAV bytes exceed the bounded in-memory cohort budget")
    return verified, _sha(raw), sidecar_sha


def _model_identity(model_dir: Path, cache_dir: Path):
    """Bind the run to verified model bytes; reuse hashes only while file identity is stable."""
    model_dir = _safe_child(WORKER_DIR / "models", model_dir)
    if model_dir.is_symlink() or not model_dir.is_dir():
        raise Refusal("pinned Nemotron model directory is unavailable")
    tree_path = model_dir / MODEL_TREE
    if tree_path.is_symlink() or not tree_path.is_file():
        raise Refusal("pinned Hugging Face model tree is unavailable")
    tree_raw = tree_path.read_bytes()
    if len(tree_raw) > MAX_MANIFEST_BYTES:
        raise Refusal("pinned model tree exceeds its size budget")
    tree_sha = _sha(tree_raw)
    if tree_sha != PINNED_MODEL_TREE_SHA256:
        raise Refusal("pinned Nemotron tree manifest SHA-256 mismatch")
    try:
        tree = json.loads(tree_raw.decode("utf-8"))
        files = tree.get("files") if isinstance(tree, dict) else None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("pinned model tree is not valid JSON") from None
    if not isinstance(files, dict) or not files or len(files) > MAX_MODEL_FILES:
        raise Refusal("pinned model file inventory is invalid")
    if len(tree_path.stem) != 40 or tree_path.stem != PINNED_MODEL_REVISION:
        raise Refusal("pinned Nemotron revision mismatch")
    if set(files) != {".gitattributes", "README.md", "audio_processor_config.json",
                      "decoder.onnx", "decoder.onnx.data", "genai_config.json",
                      "encoder.onnx", "encoder.onnx.data", "joint.onnx",
                      "joint.onnx.data", "model_config.json", "silero_vad.onnx",
                      "tokenizer.json", "tokenizer_config.json", "vocab.txt"}:
        raise Refusal("pinned Nemotron file inventory differs from the selected revision")

    expected_names = set(files) | {"encoder.cuda-mask.onnx"}
    try:
        actual_names = {item.name for item in model_dir.iterdir() if item.is_file()}
    except OSError:
        raise Refusal("Nemotron model file inventory could not be read") from None
    if actual_names != expected_names:
        raise Refusal("Nemotron model file inventory changed")

    receipt_path = _safe_child(ROOT / ".agent-work/asr-cache", cache_dir / MODEL_RECEIPT)
    previous = None
    if receipt_path.exists():
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise Refusal("model content receipt is not a regular H: file")
        try:
            raw_receipt = receipt_path.read_bytes()
            if len(raw_receipt) > MAX_MODEL_RECEIPT_BYTES:
                raise ValueError
            previous = json.loads(raw_receipt.decode("utf-8"))
            if not isinstance(previous, dict):
                raise ValueError
            receipt_digest = previous.pop("_receipt_sha256", None)
            if (not isinstance(previous, dict)
                    or set(previous) != {"schema", "revision", "tree_sha256", "files"}
                    or receipt_digest != _sha(_canonical(previous))
                    or previous.get("schema") != "sotto-model-content-v1"
                    or previous.get("revision") != PINNED_MODEL_REVISION
                    or previous.get("tree_sha256") != tree_sha
                    or not isinstance(previous.get("files"), dict)):
                raise ValueError
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
            raise Refusal("model content receipt is invalid") from None

    file_receipts = {}
    fingerprint_files = []
    total = 0
    hashed_files = 0
    hashed_bytes = 0
    planned = {}
    planned_hash_bytes = 0
    for name in sorted(files):
        if Path(name).name != name or name in (".", ".."):
            raise Refusal("pinned model tree contains an unsafe path")
        path = model_dir / name
        if path.is_symlink() or not path.is_file():
            raise Refusal("pinned model file is unavailable")
        try:
            tree_entry = files[name]
            if not isinstance(tree_entry, dict):
                raise ValueError
            expected_size = int(tree_entry["size"])
            expected_blob = tree_entry["blob_id"]
            expected_lfs = tree_entry.get("lfs_sha256")
        except (KeyError, TypeError, ValueError):
            raise Refusal("pinned model file metadata is invalid") from None
        try:
            actual_size = path.stat().st_size
        except OSError:
            raise Refusal("Nemotron model file could not be statted") from None
        if (expected_size < 0 or not isinstance(expected_blob, str)
                or not re.fullmatch(r"[0-9a-f]{40}", expected_blob)
                or actual_size != expected_size):
            raise Refusal("Nemotron model file changed from the cached revision")
        pinned_lfs = PINNED_MODEL_LFS_SHA256.get(name)
        if expected_lfs != pinned_lfs:
            raise Refusal("pinned Nemotron LFS digest differs from the selected revision")
        try:
            signature = _model_file_signature(path)
        except Refusal:
            raise
        if signature["size"] != expected_size:
            raise Refusal("Nemotron file size changed during identity census")
        cached = (previous.get("files", {}).get(name)
                  if isinstance(previous, dict) else None)
        content = _reuse_cached_model_digest(
            cached, signature, pinned_lfs=pinned_lfs, expected_blob=expected_blob)
        if content is None:
            planned_hash_bytes += expected_size
        planned[name] = {"path": path, "size": expected_size, "blob": expected_blob,
                         "lfs": pinned_lfs, "signature": signature,
                         "content": content}
    print("MODEL_HASH_PLAN files=%d cache_hits=%d hash_files=%d hash_bytes=%d "
          "max_bytes=%d receipt=H-content-addressed"
          % (len(files), len(files) - sum(item["content"] is not None
                                           for item in planned.values()),
             sum(item["content"] is None for item in planned.values()),
             planned_hash_bytes, MAX_MODEL_BYTES))
    hash_started = time.perf_counter()
    for name in sorted(planned):
        item = planned[name]
        path, expected_size = item["path"], item["size"]
        expected_blob, pinned_lfs = item["blob"], item["lfs"]
        signature, content = item["signature"], item["content"]
        if content is None:
            content = _digest_model_file(path, max_bytes=MAX_MODEL_FILE_HASH_BYTES)
            if content["size"] != expected_size:
                raise Refusal("Nemotron model file size mismatch during content hash")
            if pinned_lfs:
                if content["sha256"] != pinned_lfs:
                    raise Refusal("Nemotron model content differs from pinned LFS SHA-256")
            elif content["git_blob_sha1"] != expected_blob:
                raise Refusal("Nemotron model content differs from pinned Git blob ID")
            hashed_files += 1
            hashed_bytes += content["size"]
            after_signature = _model_file_signature(path)
            if after_signature != signature:
                raise Refusal("Nemotron model file changed during content verification")
        file_receipts[name] = {"sha256": content["sha256"],
                               "git_blob_sha1": content["git_blob_sha1"],
                               "signature": signature}
        total += expected_size
        fingerprint_files.append({"name": name, "size": expected_size,
                                  "sha256": content["sha256"]})
    if total > MAX_MODEL_BYTES:
        raise Refusal("Nemotron model inventory exceeds its byte budget")

    cuda_mask_path = model_dir / "encoder.cuda-mask.onnx"
    cuda_mask_sha, cuda_mask_bytes = _hash_file(cuda_mask_path, max_bytes=8 * 1024 * 1024)
    if cuda_mask_bytes != 2_677_588:
        raise Refusal("CUDA-mask encoder identity is invalid")
    fingerprint_files.append({"name": "encoder.cuda-mask.onnx", "size": cuda_mask_bytes,
                              "sha256": cuda_mask_sha})

    receipt_body = {"schema": "sotto-model-content-v1", "revision": PINNED_MODEL_REVISION,
                    "tree_sha256": tree_sha, "files": file_receipts}
    receipt_bytes = _canonical(dict(receipt_body,
                                    _receipt_sha256=_sha(_canonical(receipt_body))))
    if previous is None or previous.get("files") != file_receipts:
        _atomic_bytes(receipt_path, receipt_bytes, max_bytes=MAX_MODEL_RECEIPT_BYTES)
    hash_elapsed_s = max(0.0, time.perf_counter() - hash_started)
    identity = {
        "lineage": MODEL_LINEAGE,
        "acoustic_graphs": ["encoder", "decoder", "joint"],
        "revision": PINNED_MODEL_REVISION,
        "tree_sha256": tree_sha,
        "content_sha256": _sha(_canonical(fingerprint_files)),
        "files": len(fingerprint_files),
        "bytes": total + cuda_mask_bytes,
        "method": "pinned HF tree + verified Git/LFS content hashes + Windows ChangeTime/FileId cache",
    }
    identity["fingerprint"] = _sha(_canonical(identity))
    identity["hash_cache"] = {"hashed_files": hashed_files, "cached_files": len(files) - hashed_files,
                              "hashed_bytes": hashed_bytes,
                              "hash_elapsed_s": round(hash_elapsed_s, 6)}
    return identity


def _code_identity():
    paths = {
        "runner": Path(__file__).resolve(),
        "worker": WORKER_DIR / "sotto_worker.py",
        "node_assignment_helper": WORKER_DIR / "asr_node_assignment.py",
        "ort_cuda_runtime": WORKER_DIR / "ort_cuda_runtime.py",
        "engine_switch": WORKER_DIR / "engine_switch.py",
        "lang_prompt": WORKER_DIR / "lang_prompt.py",
        "scorer": SCORER_PATH,
    }
    result = {}
    for label, path in paths.items():
        if not path.is_file() or path.is_symlink():
            raise Refusal("benchmark source identity is unavailable")
        result[label] = _hash_file(path, max_bytes=8 * 1024 * 1024)[0]
    return result


def _runtime_versions():
    result = {"python": sys.version.split()[0]}
    for distribution in ("numpy", "soundfile", "onnxruntime-gpu",
                         "onnxruntime", "onnxruntime-genai"):
        try:
            result[distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            result[distribution] = None
    if not result.get("numpy") or not result.get("soundfile"):
        raise Refusal("required audio/numeric package versions are unavailable")
    _require_gpu_runtime_package_choice(result)
    if not result.get("onnxruntime-genai"):
        raise Refusal("ONNX Runtime GenAI package version is unavailable")
    return result


def _module_file(module, label):
    raw = getattr(module, "__file__", None)
    if not isinstance(raw, str) or not raw or len(raw) > 4096:
        raise Refusal(label + " imported module path is unavailable")
    path = Path(raw)
    if path.is_symlink() or not path.is_file():
        raise Refusal(label + " imported module file is not a regular file")
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        raise Refusal(label + " imported module path cannot be resolved") from None
    return resolved


def _module_spec_file(name, label):
    """Resolve a top-level module without importing its Python or native code."""
    try:
        spec = importlib.util.find_spec(name)
    except Exception:
        raise Refusal(label + " import path lookup failed") from None
    if spec is None or not isinstance(spec.origin, str) or not spec.origin:
        raise Refusal(label + " import path is unavailable")
    path = Path(spec.origin)
    if path.is_symlink() or not path.is_file():
        raise Refusal(label + " import path is not a regular file")
    try:
        return path.resolve(strict=True)
    except OSError:
        raise Refusal(label + " import path cannot be resolved") from None


def _onnxruntime_module_identity(module, expected_file, expected_version):
    """Bind the loaded ORT module to the GPU distribution and its native build."""
    module_file = _module_file(module, "ONNX Runtime")
    try:
        expected_file = Path(expected_file).resolve(strict=True)
    except OSError:
        raise Refusal("onnxruntime-gpu package module path is unavailable") from None
    if module_file != expected_file:
        raise Refusal("imported ONNX Runtime path is not the onnxruntime-gpu package")
    version = getattr(module, "__version__", None)
    if not isinstance(version, str) or not version or version != expected_version:
        raise Refusal("imported ONNX Runtime version differs from onnxruntime-gpu")
    get_build_info = getattr(module, "get_build_info", None)
    if not callable(get_build_info):
        raise Refusal("imported ONNX Runtime has no native build identity API")
    try:
        build_info = get_build_info()
    except Exception:
        raise Refusal("imported ONNX Runtime native build identity failed") from None
    if (not isinstance(build_info, str) or not build_info
            or len(build_info.encode("utf-8")) > MAX_RUNTIME_BUILD_INFO_CHARS):
        raise Refusal("imported ONNX Runtime native build identity is invalid")
    get_available_providers = getattr(module, "get_available_providers", None)
    if not callable(get_available_providers):
        raise Refusal("imported ONNX Runtime has no provider availability readback")
    _require_cuda_provider_available(get_available_providers())
    return {"module_file": str(module_file), "version": version,
            "ort_native_build_info": build_info,
            "build_info_source": "onnxruntime.get_build_info"}


def _genai_source_identity(init_path, expected_version):
    """Read bounded package version constants without importing ORT-GenAI."""
    init_path = Path(init_path)
    if init_path.is_symlink() or not init_path.is_file():
        raise Refusal("ORT-GenAI package source is unavailable")
    try:
        raw = init_path.read_bytes()
    except OSError:
        raise Refusal("ORT-GenAI package source cannot be read") from None
    if not raw or len(raw) > MAX_RUNTIME_MODULE_METADATA_BYTES:
        raise Refusal("ORT-GenAI package source exceeds its metadata bound")
    try:
        source = raw.decode("utf-8")
        module_file = str(init_path.resolve(strict=True))
    except (UnicodeError, OSError):
        raise Refusal("ORT-GenAI package source identity is invalid") from None
    constants = {}
    for name in ("__version__", "__commit__", "__id__"):
        match = re.search(r"(?m)^" + name + r"\s*=\s*(['\"])([^'\"\r\n]{1,256})\1\s*$",
                          source)
        if match:
            constants[name] = match.group(2)
    version = constants.get("__version__")
    if not isinstance(version, str) or not version or version != expected_version:
        raise Refusal("ORT-GenAI source version differs from its installed distribution")
    return {"module_file": module_file, "version": version,
            "commit": constants.get("__commit__"), "package_id": constants.get("__id__"),
            "source_sha256": _sha(raw)}


def _actual_genai_module_identity(module, expected_version):
    identity = _genai_source_identity(
        _module_file(module, "ORT-GenAI"), expected_version)
    for attr, key in (("__version__", "version"), ("__commit__", "commit"),
                      ("__id__", "package_id")):
        if getattr(module, attr, None) != identity.get(key):
            raise Refusal("actual imported ORT-GenAI module identity is inconsistent")
    return identity


def _expected_native_extension(package, label):
    native_files = package.get("native_files") if isinstance(package, dict) else None
    extensions = [Path(item["file"]).resolve() for item in native_files
                  if isinstance(item, dict) and isinstance(item.get("file"), str)
                  and Path(item["file"]).suffix.lower() == ".pyd"] if isinstance(
                      native_files, list) else []
    if len(extensions) != 1:
        raise Refusal(label + " package must contain exactly one native Python extension")
    return extensions[0]


def _loaded_native_extension(package, label, modules):
    expected = _expected_native_extension(package, label)
    expected_key = os.path.normcase(str(expected))
    loaded_paths = set()
    for module in modules:
        raw = getattr(module, "__file__", None)
        if not isinstance(raw, str) or len(raw) > 4096:
            continue
        path = Path(raw)
        if path.name.casefold() != expected.name.casefold():
            continue
        try:
            resolved = path.resolve()
        except OSError:
            raise Refusal(label + " loaded native extension path cannot be resolved") from None
        loaded_paths.add(os.path.normcase(str(resolved)))
    if loaded_paths != {expected_key}:
        raise Refusal(label + " loaded native extension differs from the pinned package file")
    return str(expected)


def _loaded_runtime_extensions(ort_module, genai_module, package_identity,
                               *, modules=None):
    if not _runtime_package_identity_shape_valid(package_identity):
        raise Refusal("runtime package identity is malformed before extension readback")
    if modules is None:
        if len(sys.modules) > MAX_RUNTIME_MODULES:
            raise Refusal("loaded Python module table exceeds its bounded extension census")
        modules = list(sys.modules.values())
    else:
        modules = list(modules)
        if len(modules) > MAX_RUNTIME_MODULES:
            raise Refusal("loaded Python module table exceeds its bounded extension census")
    modules.extend((ort_module, genai_module))
    return {
        "onnxruntime": _loaded_native_extension(
            package_identity["onnxruntime"], "ONNX Runtime", modules),
        "onnxruntime_genai": _loaded_native_extension(
            package_identity["onnxruntime_genai"], "ORT-GenAI", modules),
    }


def _native_package_file_identity(package_dir, label, *, require_cuda_provider=False,
                                  require_native_module_prefix=None,
                                  require_cuda_genai=False):
    package_dir = Path(package_dir)
    if package_dir.is_symlink() or not package_dir.is_dir():
        raise Refusal(label + " native package directory is unavailable")
    paths = []
    for pattern in ("*.dll", "*.pyd"):
        for path in package_dir.glob(pattern):
            if len(paths) >= MAX_RUNTIME_NATIVE_FILES:
                raise Refusal(label + " native package file set exceeds its bound")
            if path.is_symlink() or not path.is_file():
                raise Refusal(label + " native package contains a non-regular file")
            paths.append(path)
    paths.sort(key=lambda path: path.name.lower())
    names = {path.name.lower() for path in paths}
    if not paths:
        raise Refusal(label + " native package files are unavailable")
    if require_cuda_provider and "onnxruntime_providers_cuda.dll" not in names:
        raise Refusal("onnxruntime-gpu CUDA provider binary is unavailable")
    if require_native_module_prefix and not any(
            name.startswith(require_native_module_prefix) and name.endswith(".pyd")
            for name in names):
        raise Refusal(label + " native Python module is unavailable")
    if require_cuda_genai and "onnxruntime-genai-cuda.dll" not in names:
        raise Refusal("ORT-GenAI CUDA binary is unavailable")
    result = []
    for path in paths:
        try:
            module_file = path.resolve(strict=True)
        except OSError:
            raise Refusal(label + " native package file path cannot be resolved") from None
        result.append({"file": str(module_file), "signature": _model_file_signature(module_file)})
    return result


def _verify_native_package_file_identity(identity):
    if not isinstance(identity, dict):
        raise Refusal("runtime package file identity is unavailable")
    for package in (identity.get("onnxruntime"), identity.get("onnxruntime_genai")):
        if not isinstance(package, dict) or not isinstance(package.get("native_files"), list):
            raise Refusal("runtime package native file set is incomplete")
        module_signature = package.get("module_signature")
        if module_signature is not None:
            module_path = Path(package.get("module_file", ""))
            if (module_path.is_symlink() or not module_path.is_file()
                    or _model_file_signature(module_path) != module_signature):
                raise Refusal("runtime package module file changed after preflight")
        if not package["native_files"] or len(package["native_files"]) > MAX_RUNTIME_NATIVE_FILES:
            raise Refusal("runtime package native file set exceeds its bound")
        for item in package["native_files"]:
            if (not isinstance(item, dict) or set(item) != {"file", "signature"}
                    or not isinstance(item.get("file"), str)
                    or len(item["file"]) > 4096):
                raise Refusal("runtime package native file identity is malformed")
            path = Path(item["file"])
            if path.is_symlink() or not path.is_file():
                raise Refusal("runtime package native file is missing or not regular")
            if _model_file_signature(path) != item.get("signature"):
                raise Refusal("runtime package native file changed after preflight")


def _expected_genai_package_identity(worker, runtime_versions):
    runtime_dir = Path(worker.HERE) / "models/.sotto-runtime/genai-cuda"
    bundled_init = runtime_dir / "onnxruntime_genai/__init__.py"
    bundled_package = runtime_dir / "onnxruntime_genai"
    bundled_cuda = bundled_package / "onnxruntime-genai-cuda.dll"
    worker_inserts_bundle = bundled_cuda.is_file() and str(runtime_dir) not in sys.path
    if worker_inserts_bundle:
        init_path = bundled_init
        package_dir = bundled_package
    else:
        init_path = _module_spec_file("onnxruntime_genai", "ORT-GenAI")
        package_dir = init_path.parent
    identity = _genai_source_identity(init_path, runtime_versions["onnxruntime-genai"])
    identity["native_files"] = _native_package_file_identity(
        package_dir, "ORT-GenAI", require_native_module_prefix="onnxruntime_genai",
        require_cuda_genai=package_dir == bundled_package)
    return identity


def _actual_runtime_module_identity(ort_module, genai_module,
                                    expected_runtime_package_identity):
    """Read actual loaded module identities and compare them before audio decode."""
    if not _runtime_package_identity_shape_valid(expected_runtime_package_identity):
        raise Refusal("preflight runtime package identity is malformed")
    expected_ort = expected_runtime_package_identity.get("onnxruntime")
    expected_genai = expected_runtime_package_identity.get("onnxruntime_genai")
    if not isinstance(expected_ort, dict) or not isinstance(expected_genai, dict):
        raise Refusal("preflight runtime module identity is incomplete")
    _verify_native_package_file_identity(expected_runtime_package_identity)
    actual_ort = _onnxruntime_module_identity(
        ort_module, expected_ort.get("module_file"), expected_ort.get("version"))
    if genai_module is None:
        raise Refusal("StreamAsr did not retain its imported ORT-GenAI module")
    actual_genai = _actual_genai_module_identity(
        genai_module, expected_genai.get("version"))
    expected_genai_module = {key: expected_genai.get(key) for key in
                             ("module_file", "version", "commit", "package_id", "source_sha256")}
    if (actual_ort["module_file"] != expected_ort.get("module_file")
            or actual_ort["version"] != expected_ort.get("version")
            or actual_genai != expected_genai_module):
        raise Refusal("actual imported runtime modules differ from the run identity")
    native_extensions = _loaded_runtime_extensions(
        ort_module, genai_module, expected_runtime_package_identity)
    actual_ort["native_extension_file"] = native_extensions["onnxruntime"]
    actual_genai["native_extension_file"] = native_extensions["onnxruntime_genai"]
    return {"onnxruntime": actual_ort, "onnxruntime_genai": actual_genai}


def _runtime_identity_shape_valid(identity):
    if not isinstance(identity, dict) or set(identity) != {"onnxruntime", "onnxruntime_genai"}:
        return False
    ort = identity.get("onnxruntime")
    genai = identity.get("onnxruntime_genai")
    if not isinstance(ort, dict) or set(ort) != {
            "module_file", "version", "ort_native_build_info", "build_info_source",
            "native_extension_file"}:
        return False
    if not isinstance(genai, dict) or set(genai) != {
            "module_file", "version", "commit", "package_id", "source_sha256",
            "native_extension_file"}:
        return False
    for module in (ort, genai):
        if (not isinstance(module.get("module_file"), str)
                or not module["module_file"] or len(module["module_file"]) > 4096
                or not Path(module["module_file"]).is_absolute()
                or not isinstance(module.get("version"), str)
                or not module["version"] or len(module["version"]) > 128):
            return False
        extension_file = module.get("native_extension_file")
        if (not isinstance(extension_file, str) or not extension_file
                or len(extension_file) > 4096 or not Path(extension_file).is_absolute()
                or Path(extension_file).suffix.lower() != ".pyd"):
            return False
    if (not isinstance(ort.get("ort_native_build_info"), str)
            or not ort["ort_native_build_info"]
            or len(ort["ort_native_build_info"].encode("utf-8"))
            > MAX_RUNTIME_BUILD_INFO_CHARS
            or ort.get("build_info_source") != "onnxruntime.get_build_info"):
        return False
    for key in ("commit", "package_id"):
        if genai.get(key) is not None and (
                not isinstance(genai[key], str) or len(genai[key]) > 256):
            return False
    return (isinstance(genai.get("source_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", genai["source_sha256"]) is not None)


def _runtime_package_identity_shape_valid(identity):
    if not isinstance(identity, dict) or set(identity) != {"onnxruntime", "onnxruntime_genai"}:
        return False
    ort = identity.get("onnxruntime")
    genai = identity.get("onnxruntime_genai")
    if (not isinstance(ort, dict)
            or set(ort) != {"module_file", "version", "module_signature", "native_files"}
            or not isinstance(genai, dict)
            or set(genai) != {"module_file", "version", "commit", "package_id",
                              "source_sha256", "native_files"}):
        return False
    ort_signature = ort.get("module_signature")
    if (not isinstance(ort_signature, dict)
            or set(ort_signature) != {"size", "mtime_ns", "change_time_100ns",
                                      "volume_serial", "file_id"}
            or any(not isinstance(ort_signature.get(key), int)
                   or isinstance(ort_signature.get(key), bool)
                   for key in ("size", "mtime_ns", "change_time_100ns", "volume_serial"))
            or not isinstance(ort_signature.get("file_id"), str)
            or not re.fullmatch(r"[0-9a-f]{32}", ort_signature["file_id"])):
        return False
    for package in (ort, genai):
        if (not isinstance(package.get("module_file"), str)
                or not package["module_file"] or len(package["module_file"]) > 4096
                or not Path(package["module_file"]).is_absolute()
                or not isinstance(package.get("version"), str)
                or not package["version"] or len(package["version"]) > 128
                or not isinstance(package.get("native_files"), list)
                or not package["native_files"]
                or len(package["native_files"]) > MAX_RUNTIME_NATIVE_FILES):
            return False
        for item in package["native_files"]:
            signature = item.get("signature") if isinstance(item, dict) else None
            if (not isinstance(item, dict) or set(item) != {"file", "signature"}
                    or not isinstance(item.get("file"), str)
                    or len(item["file"]) > 4096
                    or not Path(item["file"]).is_absolute()
                    or not isinstance(signature, dict)
                    or set(signature) != {"size", "mtime_ns", "change_time_100ns",
                                          "volume_serial", "file_id"}
                    or any(not isinstance(signature.get(key), int)
                           or isinstance(signature.get(key), bool)
                           for key in ("size", "mtime_ns", "change_time_100ns",
                                       "volume_serial"))
                    or not isinstance(signature.get("file_id"), str)
                    or not re.fullmatch(r"[0-9a-f]{32}", signature["file_id"])):
                return False
        if sum(Path(item["file"]).suffix.lower() == ".pyd"
               for item in package["native_files"]) != 1:
            return False
    if any(genai.get(key) is not None
           and (not isinstance(genai[key], str) or len(genai[key]) > 256)
           for key in ("commit", "package_id")):
        return False
    return (isinstance(genai.get("source_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", genai["source_sha256"]) is not None)


def _runtime_identities_bind(module_identity, package_identity):
    if (not _runtime_identity_shape_valid(module_identity)
            or not _runtime_package_identity_shape_valid(package_identity)):
        return False
    loaded_ort = module_identity["onnxruntime"]
    expected_ort = package_identity["onnxruntime"]
    if (loaded_ort["module_file"] != expected_ort["module_file"]
            or loaded_ort["version"] != expected_ort["version"]):
        return False
    try:
        if os.path.normcase(loaded_ort["native_extension_file"]) != os.path.normcase(
                str(_expected_native_extension(expected_ort, "ONNX Runtime"))):
            return False
    except Refusal:
        return False
    loaded_genai = module_identity["onnxruntime_genai"]
    expected_genai = package_identity["onnxruntime_genai"]
    if not all(loaded_genai.get(key) == expected_genai.get(key) for key in
               ("module_file", "version", "commit", "package_id", "source_sha256")):
        return False
    try:
        return os.path.normcase(loaded_genai["native_extension_file"]) == os.path.normcase(
            str(_expected_native_extension(expected_genai, "ORT-GenAI")))
    except Refusal:
        return False


def _preflight_runtime_package_identity(worker, runtime_versions):
    """Bind cache keys to exact installed paths, versions, and native file identities."""
    try:
        ort_dist = importlib.metadata.distribution("onnxruntime-gpu")
        ort_file = Path(ort_dist.locate_file("onnxruntime/__init__.py"))
    except importlib.metadata.PackageNotFoundError:
        raise Refusal("GPU ONNX Runtime package module path is unavailable") from None
    if ort_file.is_symlink() or not ort_file.is_file():
        raise Refusal("onnxruntime-gpu module file is unavailable")
    try:
        ort_file = ort_file.resolve(strict=True)
    except OSError:
        raise Refusal("onnxruntime-gpu module path cannot be resolved") from None
    _require_gpu_ort_module_path(
        _module_spec_file("onnxruntime", "ONNX Runtime"), ort_file)
    try:
        ort_module = importlib.import_module("onnxruntime")
    except Exception:
        raise Refusal("GPU ONNX Runtime native import failed after CUDA DLL setup") from None
    # CPU and GPU wheels may share package paths and Python metadata hashes.
    # Require the loaded native build to expose CUDA; production sessions and
    # graph assignments are checked again before any audio is decoded.
    _onnxruntime_module_identity(
        ort_module, ort_file, runtime_versions.get("onnxruntime-gpu"))
    ort_identity = {"module_file": str(ort_file),
                    "version": runtime_versions.get("onnxruntime-gpu"),
                    "module_signature": _model_file_signature(ort_file),
                    "native_files": _native_package_file_identity(
                        ort_file.parent / "capi", "onnxruntime-gpu",
                        require_cuda_provider=True,
                        require_native_module_prefix="onnxruntime_pybind11_state")}
    genai_identity = _expected_genai_package_identity(worker, runtime_versions)
    result = {"onnxruntime": ort_identity, "onnxruntime_genai": genai_identity}
    if not _runtime_package_identity_shape_valid(result):
        raise Refusal("preflight runtime package identity is malformed")
    _verify_native_package_file_identity(result)
    return result


def _require_gpu_runtime_package_choice(versions):
    if not isinstance(versions, dict) or not versions.get("onnxruntime-gpu"):
        raise Refusal("CUDA benchmark requires the onnxruntime-gpu package")


def _require_gpu_ort_module_path(imported_path, gpu_package_path):
    """Allow the shared wheel path; native CUDA availability is checked after import."""
    try:
        imported = Path(imported_path).resolve(strict=True)
        expected = Path(gpu_package_path).resolve(strict=True)
    except OSError:
        raise Refusal("resolved ONNX Runtime module path is unavailable") from None
    if imported != expected:
        raise Refusal("ONNX Runtime import resolution differs from onnxruntime-gpu")


def _require_cuda_provider_available(providers):
    if (not isinstance(providers, (list, tuple))
            or not all(isinstance(item, str) and item for item in providers)
            or CUDA_PROVIDER not in providers):
        raise Refusal("imported ONNX Runtime native build does not expose CUDA")


def _pool_plan(worker, requested_threads: int):
    resolved = worker.resolve_threads(requested_threads)
    try:
        budget = int(resolved[0])
        share = worker.asr_budget(budget)
        encoder = int(share["live"])
        small = int(share["small"])
        sessions = 3
        total_intra = encoder + (2 * small)
        if (budget != requested_threads or int(share["total"]) != budget
                or min(encoder, small) < 1 or total_intra < 1):
            raise ValueError
    except (TypeError, ValueError, KeyError, IndexError):
        raise Refusal("could not derive the production ORT pool plan") from None
    return {"process_budget_requested": budget, "encoder_intra": encoder,
            "small_intra": small, "ort_sessions": sessions,
            "ort_intra_aggregate": total_intra,
            "batch_intra": int(share["batch"])}


def _require_pool_approval(pool, approved):
    if approved is None:
        raise Refusal("explicit --approved-ort-pool-threads is required")
    if approved != pool.get("ort_intra_aggregate"):
        raise Refusal("approved ORT pool total does not match the production plan")


def _normalize_runtime_environment():
    """Pin effective session/load knobs and hash the remaining CUDA/ORT env surface."""
    load_ab = os.environ.get("SOTTO_LOAD_AB", "").strip().lower()
    if len(load_ab) > 128:
        raise Refusal("SOTTO_LOAD_AB exceeds its bounded value length")
    os.environ["SOTTO_LOAD_AB"] = load_ab

    cpu_spec = os.environ.get("SOTTO_GENAI_CPUS", "").strip().replace(";", ",")
    cpu_ids = set()
    if cpu_spec:
        for part in cpu_spec.split(","):
            part = part.strip()
            if not part:
                raise Refusal("SOTTO_GENAI_CPUS contains an empty CPU selector")
            try:
                if "-" in part:
                    if part.count("-") != 1:
                        raise ValueError
                    low, high = map(int, part.split("-", 1))
                    if low < 0 or high < low or high >= 64 or high - low >= 64:
                        raise ValueError
                    cpu_ids.update(range(low, high + 1))
                else:
                    cpu_id = int(part)
                    if cpu_id < 0 or cpu_id >= 64:
                        raise ValueError
                    cpu_ids.add(cpu_id)
            except ValueError:
                raise Refusal("SOTTO_GENAI_CPUS must name bounded Windows CPU indexes") from None
            if len(cpu_ids) > 64:
                raise Refusal("SOTTO_GENAI_CPUS exceeds its 64-CPU bound")
    genai_cpus = ",".join(str(cpu_id) for cpu_id in sorted(cpu_ids))
    os.environ["SOTTO_GENAI_CPUS"] = genai_cpus

    try:
        cuda_mem_limit = int(os.environ.get("SOTTO_CUDA_MEM_LIMIT_MB", "0"))
    except (TypeError, ValueError):
        cuda_mem_limit = 0  # worker's documented fallback
    if cuda_mem_limit < 0 or cuda_mem_limit > 1_048_576:
        raise Refusal("SOTTO_CUDA_MEM_LIMIT_MB is outside its accepted bound")
    os.environ["SOTTO_CUDA_MEM_LIMIT_MB"] = str(cuda_mem_limit)
    cuda_arena = os.environ.get("SOTTO_CUDA_ARENA", "").strip() or "kSameAsRequested"
    cudnn_search = os.environ.get("SOTTO_CUDNN_ALGO_SEARCH", "").strip() or "EXHAUSTIVE"
    if len(cuda_arena) > 128 or len(cudnn_search) > 128:
        raise Refusal("CUDA provider option value exceeds its bounded length")
    os.environ["SOTTO_CUDA_ARENA"] = cuda_arena
    os.environ["SOTTO_CUDNN_ALGO_SEARCH"] = cudnn_search

    module_loading = os.environ.get("CUDA_MODULE_LOADING", "LAZY").strip().upper()
    if module_loading not in ("LAZY", "EAGER"):
        raise Refusal("CUDA_MODULE_LOADING must be LAZY or EAGER")
    os.environ["CUDA_MODULE_LOADING"] = module_loading
    visible_devices = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip()
    device_order = os.environ.get("CUDA_DEVICE_ORDER", "").strip().upper()
    if device_order and device_order not in ("FASTEST_FIRST", "PCI_BUS_ID"):
        raise Refusal("CUDA_DEVICE_ORDER is not a recognized value")
    if "CUDA_VISIBLE_DEVICES" in os.environ:
        os.environ["CUDA_VISIBLE_DEVICES"] = visible_devices
    if device_order:
        os.environ["CUDA_DEVICE_ORDER"] = device_order
    os.environ["SOTTO_ORT_NODE_TRACE"] = "1"

    env_surface = {}
    prefixes = ("CUDA_", "ORT_", "OMP_", "MKL_", "OPENBLAS_", "NUMEXPR_")
    for name, value in os.environ.items():
        if name.startswith(prefixes):
            if len(env_surface) >= 256 or len(value) > 2048:
                raise Refusal("CUDA/ORT environment surface exceeds its bounded inventory")
            env_surface[name] = value
    env_surface["PATH_SHA256"] = _sha(os.environ.get("PATH", "").encode("utf-8"))
    effective = {
        "sotto_load_ab": load_ab,
        "sotto_genai_cpus": genai_cpus,
        "sotto_ort_node_trace": "1",
        "sotto_cuda_mem_limit_mb": cuda_mem_limit,
        "sotto_cuda_arena": cuda_arena,
        "sotto_cudnn_algo_search": cudnn_search,
        "cuda_module_loading": module_loading,
        "cuda_visible_devices": visible_devices,
        "cuda_device_order": device_order or None,
        "thread_env": {name: os.environ.get(name, "") for name in THREAD_ENV},
        "ambient_cuda_ort_env_sha256": _sha(_canonical(env_surface)),
    }
    effective["fingerprint"] = _sha(_canonical(effective))
    return effective


class _SafeSink:
    """Discard arbitrary worker text; retain only bounded numeric plan facts."""
    _POOL = re.compile(
        r"^WORKER_THREAD_PLAN encoder=(\d+) small=(\d+) sessions=(\d+) "
        r"total_intra=(\d+) budget_total=(\d+) budget_batch=(\d+)$")
    # The worker's legacy WORKER_GENAI_THREADS label is printed by
    # cap_genai_threads() after genai_thread_ids() matches every process TID
    # whose description contains "intra-op". Preserve the count without
    # inferring which runtime owns those threads.
    _ORT_THREAD_IDS = re.compile(
        r"^WORKER_GENAI_THREADS threads=(\d+) pinned=(\d+) cpus=([^ ]+).*$")

    def __init__(self):
        self._lock = threading.Lock()
        self._tail = ""
        self.pool_plan = None
        self.ort_intra_op_tids = None

    def write(self, value):
        if not isinstance(value, str):
            value = str(value)
        with self._lock:
            joined = (self._tail + value)[-4096:]
            lines = joined.split("\n")
            self._tail = lines.pop()[-512:]
            for line in lines:
                clean = line.strip()
                match = self._POOL.fullmatch(clean)
                if match:
                    names = ("encoder_intra", "small_intra", "ort_sessions",
                             "ort_intra_aggregate", "process_budget_requested", "batch_intra")
                    self.pool_plan = dict(zip(names, map(int, match.groups())))
                    continue
                match = self._ORT_THREAD_IDS.fullmatch(clean)
                if match:
                    self.ort_intra_op_tids = int(match.group(1))
        return len(value)

    def flush(self):
        return None

    def isatty(self):
        return False


def _normalized_graph_assignments(assignments):
    expected_graphs = {"encoder", "decoder", "joint"}
    if not isinstance(assignments, dict) or set(assignments) != expected_graphs:
        raise Refusal("Nemotron per-graph node assignment readback is incomplete")
    normalized = {}
    for graph in sorted(expected_graphs):
        info = assignments[graph]
        if not isinstance(info, dict) or info.get("method") != "get_provider_graph_assignment_info":
            raise Refusal("Nemotron node assignment method/readback is unavailable")
        providers = info.get("providers")
        total = info.get("total_nodes")
        if (not isinstance(providers, dict) or not providers or len(providers) > 32
                or not isinstance(total, int) or isinstance(total, bool)
                or total < 1 or total > 1_000_000):
            raise Refusal("Nemotron graph node assignment counts are invalid")
        if any(not isinstance(name, str) or not name or len(name) > 80
               or not isinstance(count, int) or isinstance(count, bool)
               or count < 0 or count > 1_000_000 for name, count in providers.items()):
            raise Refusal("Nemotron graph provider assignment counts are invalid")
        if (sum(providers.values()) != total
                or set(name for name, count in providers.items() if count > 0)
                != {CUDA_PROVIDER}):
            raise Refusal("Nemotron graph contains CPU/unknown or unassigned nodes")
        normalized[graph] = {"providers": {CUDA_PROVIDER: providers[CUDA_PROVIDER]},
                             "total_nodes": total,
                             "method": "get_provider_graph_assignment_info"}
    return normalized


def _route_facts(asr, expected_plan, expected_runtime_package_identity):
    providers = getattr(asr, "session_providers", None)
    expected_graphs = {"encoder", "decoder", "joint"}
    if not isinstance(providers, dict) or set(providers) != expected_graphs:
        raise Refusal("Nemotron acoustic graph readback set is incomplete")
    if getattr(asr, "providers_requested", None) != [CUDA_PROVIDER]:
        raise Refusal("Nemotron provider request is not CUDA-only")
    if str(getattr(asr, "device", "")).lower() != "cuda":
        raise Refusal("Nemotron device census is not CUDA")
    if not bool(getattr(asr, "cpu_ep_fallback_disabled", False)):
        raise Refusal("Nemotron CPU EP fallback is not disabled")
    if not bool(getattr(asr, "runtime_fallback_disabled", False)):
        raise Refusal("Nemotron runtime fallback is not disabled")
    for graph, actual in providers.items():
        if not isinstance(actual, (tuple, list)) or CUDA_PROVIDER not in actual:
            raise Refusal("Nemotron graph lacks CUDA provider readback")
    if str(getattr(asr, "genai_device_type", "")).lower() not in ("cuda", "gpu"):
        raise Refusal("Nemotron GenAI frontend is not CUDA")
    if bool(getattr(asr, "use_vad", True)):
        raise Refusal("FLEURS utterance path unexpectedly enabled VAD")
    graph_assignments = _normalized_graph_assignments(
        getattr(asr, "graph_assignment_info", None))
    runtime_identity = _actual_runtime_module_identity(
        getattr(asr, "ort", None), getattr(asr, "genai_module", None),
        expected_runtime_package_identity)
    facts = {
        "device": "cuda",
        # Registered provider readback is retained separately and is never
        # interpreted as evidence of actual node placement.
        "registered_graph_providers": {name: list(providers[name])
                                        for name in sorted(providers)},
        "graph_assignment": graph_assignments,
        "cpu_ep_fallback": "disabled",
        "runtime_fallback": "disabled",
        "genai_device": str(asr.genai_device_type).lower(),
        "ort_pool_plan": dict(expected_plan),
        "runtime_module_identity": runtime_identity,
        "runtime_package_identity": expected_runtime_package_identity,
    }
    return facts


def _check_pool_readback(actual, expected, approved):
    if not isinstance(actual, dict):
        raise Refusal("worker did not report its ORT pool plan")
    fields = ("encoder_intra", "small_intra", "ort_sessions", "ort_intra_aggregate",
              "process_budget_requested", "batch_intra")
    if any(actual.get(key) != expected.get(key) for key in fields):
        raise Refusal("worker ORT pool readback differs from preflight plan")
    if actual.get("ort_intra_aggregate") != approved:
        raise Refusal("worker ORT pool total differs from explicit approval")


def _current_process_tids():
    """Count this process's OS TIDs from a bounded Windows snapshot."""
    if os.name != "nt":
        raise Refusal("cannot measure current process TIDs on this platform")
    try:
        import ctypes
        import ctypes.wintypes as wt

        class _ThreadEntry32(ctypes.Structure):
            _fields_ = [("dwSize", wt.DWORD), ("cntUsage", wt.DWORD),
                        ("th32ThreadID", wt.DWORD), ("th32OwnerProcessID", wt.DWORD),
                        ("tpBasePri", ctypes.c_long), ("tpDeltaPri", ctypes.c_long),
                        ("dwFlags", wt.DWORD)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
        kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
        kernel32.Thread32First.restype = wt.BOOL
        kernel32.Thread32First.argtypes = [wt.HANDLE, ctypes.POINTER(_ThreadEntry32)]
        kernel32.Thread32Next.restype = wt.BOOL
        kernel32.Thread32Next.argtypes = [wt.HANDLE, ctypes.POINTER(_ThreadEntry32)]
        kernel32.GetCurrentProcessId.restype = wt.DWORD
        kernel32.CloseHandle.restype = wt.BOOL
        kernel32.CloseHandle.argtypes = [wt.HANDLE]

        snapshot = kernel32.CreateToolhelp32Snapshot(0x4, 0)  # TH32CS_SNAPTHREAD
        invalid = ctypes.c_void_p(-1).value
        if not snapshot or ctypes.cast(snapshot, ctypes.c_void_p).value == invalid:
            raise OSError("thread snapshot unavailable")
        try:
            entry = _ThreadEntry32()
            entry.dwSize = ctypes.sizeof(_ThreadEntry32)
            process_id = int(kernel32.GetCurrentProcessId())
            count = 0
            scanned = 0
            ok = bool(kernel32.Thread32First(snapshot, ctypes.byref(entry)))
            while ok:
                scanned += 1
                if scanned > MAX_PROCESS_TID_SCAN:
                    raise Refusal("process TID census exceeded its scan bound")
                if int(entry.th32OwnerProcessID) == process_id:
                    count += 1
                ok = bool(kernel32.Thread32Next(snapshot, ctypes.byref(entry)))
            if count < 1:
                raise Refusal("current process TID census was empty")
            return count, scanned
        finally:
            kernel32.CloseHandle(snapshot)
    except Refusal:
        raise
    except Exception:
        raise Refusal("current process TID census failed closed") from None


def _require_thread_budget(ort_intra_op_tids, process_tids, approved_process_tids):
    """Gate one post-load sample; it is not a peak-thread measurement."""
    if (not isinstance(approved_process_tids, int)
            or isinstance(approved_process_tids, bool) or approved_process_tids < 1):
        raise Refusal("explicit positive --approved-process-tids is required")
    for value in (ort_intra_op_tids, process_tids):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise Refusal("named ORT intra-op/process TID readback is unavailable")
    if ort_intra_op_tids > approved_process_tids:
        raise Refusal("named ORT intra-op TIDs %d exceed approved process TID budget %d"
                      % (ort_intra_op_tids, approved_process_tids))
    if process_tids < ort_intra_op_tids:
        raise Refusal("named ORT intra-op TID count exceeds total process TID count")
    if process_tids < 1:
        raise Refusal("current process TID census is empty")
    if process_tids > approved_process_tids:
        raise Refusal("process TIDs %d exceed approved process TID budget %d"
                      % (process_tids, approved_process_tids))
    return {"named_ort_intra_op_tids": ort_intra_op_tids,
            "process_tids": process_tids,
            "approved_process_tids": approved_process_tids,
            "sampling_phase": "post_model_and_frontend_ready_not_peak"}


def _percentile(values, q):
    if not values:
        return None
    values = sorted(float(value) for value in values)
    pos = (len(values) - 1) * q
    low, high = math.floor(pos), math.ceil(pos)
    if low == high:
        return round(values[low], 6)
    return round(values[low] + (values[high] - values[low]) * (pos - low), 6)


def _valid_number(value, *, minimum=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(value) or value < minimum:
        return None
    return value


def _cached_number(value, *, minimum=0.0):
    """Accept only JSON numeric scalars for integrity-checked cache metrics."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return _valid_number(value, minimum=minimum)


def _validate_row(row, sample, run_key):
    if not isinstance(row, dict) or row.get("_run_key") != run_key:
        raise Refusal("cached hypothesis row belongs to another run")
    if row.get("id") != sample["id"] or row.get("audio_sha256") != sample["audio_sha256"]:
        raise Refusal("cached hypothesis row has a different input identity")
    text = row.get("text")
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_ROW_TEXT_BYTES:
        raise Refusal("cached hypothesis text is invalid")
    if row.get("_text_sha256") != _sha(text.encode("utf-8")):
        raise Refusal("cached hypothesis text digest mismatch")
    if _cached_number(row.get("audio_s"), minimum=1e-8) is None:
        raise Refusal("cached hypothesis duration is invalid")
    if abs(float(row["audio_s"]) - sample["audio_s"]) > 0.01:
        raise Refusal("cached hypothesis duration disagrees with the pinned WAV")
    if _cached_number(row.get("inference_s")) is None:
        raise Refusal("cached hypothesis timing is invalid")
    chunks = row.get("_chunk_stats")
    audio_samples = row.get("_audio_samples_16k")
    if (not isinstance(audio_samples, int) or isinstance(audio_samples, bool)
            or audio_samples <= 0):
        raise Refusal("cached resampled audio length is invalid")
    if not isinstance(chunks, list) or not chunks:
        raise Refusal("cached chunk metrics are invalid")
    for chunk in chunks:
        if (not isinstance(chunk, dict)
                or _cached_number(chunk.get("inference_s")) is None
                or _cached_number(chunk.get("line_event_s")) is None
                or _cached_number(chunk.get("audio_s"), minimum=1e-8) is None
                or _cached_number(chunk.get("rtf")) is None):
            raise Refusal("cached chunk timing is invalid")
    expected_chunks = math.ceil(audio_samples / CHUNK_SAMPLES)
    chunk_inference = sum(float(chunk["inference_s"]) for chunk in chunks)
    if (len(chunks) != expected_chunks
            or abs(chunk_inference - float(row["inference_s"])) > 0.01):
        raise Refusal("cached chunk coverage or inference sum is invalid")
    first_event_fields = (
        "_first_nonempty_asr_chunk_finish_s", "_first_nonempty_asr_chunk_added_s",
        "_first_nonempty_visible_line_event_finish_s",
        "_first_nonempty_visible_line_event_added_s",
    )
    if not set(first_event_fields).issubset(row):
        raise Refusal("cached row lacks its first-result metric identities")
    if any(row[field] is not None and _cached_number(row[field]) is None
           for field in first_event_fields):
        raise Refusal("cached first-result timing is invalid")
    route = row.get("_route")
    graph_providers = (route.get("registered_graph_providers")
                       if isinstance(route, dict) else None)
    if (not isinstance(route, dict) or route.get("device") != "cuda"
            or route.get("cpu_ep_fallback") != "disabled"
            or route.get("runtime_fallback") != "disabled"
            or route.get("assignment_model_identity") != route.get("model_identity")
            or route.get("sampling_phase") != "post_model_and_frontend_ready_not_peak"
            or not isinstance(route.get("model_identity"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", route.get("model_identity", ""))
            or not isinstance(graph_providers, dict)
            or set(graph_providers) != {"encoder", "decoder", "joint"}
            or not _runtime_identity_shape_valid(route.get("runtime_module_identity"))
            or not _runtime_package_identity_shape_valid(
                route.get("runtime_package_identity"))
            or not _runtime_identities_bind(route.get("runtime_module_identity"),
                                            route.get("runtime_package_identity"))):
        raise Refusal("cached row lacks its CUDA-only route receipt")
    if any(CUDA_PROVIDER not in graph_providers.get(graph, ())
           for graph in ("encoder", "decoder", "joint")):
        raise Refusal("cached row has a graph without CUDA provider registration")
    _normalized_graph_assignments(route.get("graph_assignment"))
    _require_thread_budget(route.get("named_ort_intra_op_tids"), route.get("process_tids"),
                           route.get("approved_process_tids"))
    digest = row.get("_row_sha256")
    without_digest = dict(row)
    without_digest.pop("_row_sha256", None)
    if digest != _sha(_canonical(without_digest)):
        raise Refusal("cached hypothesis row digest mismatch")
    return row


def _load_resume(path: Path, samples, run_key: str,
                 expected_runtime_package_identity=None):
    if not path.exists():
        return {}
    if path.is_symlink() or not path.is_file():
        raise Refusal("content-addressed result path is not a regular file")
    raw = path.read_bytes()
    if len(raw) > MAX_HYPOTHESIS_BYTES:
        raise Refusal("content-addressed results exceed the cache budget")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        raise Refusal("content-addressed results are not UTF-8") from None
    by_id = {sample["id"]: sample for sample in samples}
    rows = {}
    for line in lines:
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            raise Refusal("content-addressed result row is malformed") from None
        if not isinstance(row, dict) or row.get("id") not in by_id or row["id"] in rows:
            raise Refusal("content-addressed result cohort is invalid")
        validated = _validate_row(row, by_id[row["id"]], run_key)
        if (expected_runtime_package_identity is not None
                and validated.get("_route", {}).get("runtime_package_identity")
                != expected_runtime_package_identity):
            raise Refusal("cached runtime package files differ from this process")
        if rows and (validated.get("_route", {}).get("runtime_module_identity")
                     != next(iter(rows.values())).get("_route", {}).get(
                         "runtime_module_identity")):
            raise Refusal("cached cohort contains more than one imported runtime build")
        rows[row["id"]] = validated
    if expected_runtime_package_identity is not None:
        _verify_native_package_file_identity(expected_runtime_package_identity)
    return rows


def _atomic_save(path: Path, rows):
    body = b"".join(_canonical(rows[sample_id]) + b"\n"
                    for sample_id in sorted(rows))
    if len(body) > MAX_HYPOTHESIS_BYTES:
        raise Refusal("hypothesis JSONL exceeds its size budget")
    if (len(body) * 2) > MAX_CACHE_BYTES:
        raise Refusal("temporary plus final cache writes exceed 2 MiB")
    path.parent.mkdir(parents=True, exist_ok=True)
    path = _safe_child(ROOT / ".agent-work/asr-cache", path)
    if path.exists() and path.is_symlink():
        raise Refusal("content-addressed result path is a symlink")
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".fleurs-nemotron-", suffix=".tmp",
                                         dir=path.parent, delete=False) as stream:
            temp_path = Path(stream.name)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except OSError:
                pass


def _prune_result_cache(cache_dir: Path, current_path: Path):
    """Retain at most five runner-owned JSONL result files; leave other files alone."""
    cache_dir = _safe_child(ROOT / ".agent-work/asr-cache", cache_dir)
    current_path = _safe_child(cache_dir, current_path)
    if (not re.fullmatch(r"nemotron-stream-[0-9a-f]{64}\.jsonl", current_path.name)
            or current_path.is_symlink()):
        raise Refusal("current result path is not a safe runner-owned JSONL")
    if not cache_dir.exists():
        return {"files": 0, "bytes": 0, "pruned": 0}
    owned = []
    try:
        with os.scandir(cache_dir) as entries:
            for index, entry in enumerate(entries, start=1):
                if index > MAX_CACHE_DIR_ENTRIES:
                    raise Refusal("result cache directory exceeds its bounded entry scan")
                if not re.fullmatch(r"nemotron-stream-[0-9a-f]{64}\.jsonl", entry.name):
                    continue
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    raise Refusal("runner-owned result cache contains a non-regular path")
                stat = entry.stat(follow_symlinks=False)
                if stat.st_size < 0 or stat.st_size > MAX_HYPOTHESIS_BYTES:
                    raise Refusal("runner-owned result cache file exceeds its byte bound")
                owned.append((entry.name, int(stat.st_mtime_ns), int(stat.st_size),
                              Path(entry.path)))
    except Refusal:
        raise
    except OSError:
        raise Refusal("bounded result cache inventory failed") from None

    current = next((item for item in owned if item[0] == current_path.name), None)
    if current_path.exists() and current is None:
        raise Refusal("current result file is absent from its cache inventory")
    reservation_bytes = current[2] if current else MAX_HYPOTHESIS_BYTES
    retained = [current] if current else []
    retained_bytes = reservation_bytes
    reserved_slots = 0 if current else 1
    others = sorted((item for item in owned if item[0] != current_path.name),
                    key=lambda item: (item[1], item[0]), reverse=True)
    for item in others:
        if (len(retained) + reserved_slots + 1 > MAX_RESULT_CACHE_FILES
                or retained_bytes + item[2] > MAX_RESULT_CACHE_BYTES):
            continue
        retained.append(item)
        retained_bytes += item[2]
    keep_names = {item[0] for item in retained}
    pruned = 0
    for name, _mtime, _size, path in owned:
        if name in keep_names:
            continue
        if path.is_symlink():
            raise Refusal("runner-owned result cache changed during retention")
        try:
            path.unlink()
        except OSError:
            raise Refusal("bounded result retention could not remove an owned old result") from None
        pruned += 1
    actual_bytes = sum(item[2] for item in retained)
    if current is None:
        actual_bytes -= reservation_bytes
    return {"files": len(retained), "bytes": max(0, actual_bytes), "pruned": pruned}


def _decode_audio(sample, worker):
    """Only called after route and pool gates. Decode a verified pinned WAV."""
    try:
        import numpy as np
        import soundfile as sf
    except ImportError:
        raise Refusal("GPU benchmark audio decoder dependencies are unavailable") from None
    try:
        raw = sample.get("_verified_audio_bytes")
        if not isinstance(raw, bytes) or len(raw) != sample.get("audio_bytes"):
            raise Refusal("verified in-memory WAV bytes are unavailable")
        data, source_rate = sf.read(io.BytesIO(raw), dtype="float32", always_2d=True)
    except Exception:
        raise Refusal("verified WAV could not be decoded") from None
    if data.ndim != 2 or data.shape[0] < 1 or data.shape[1] < 1:
        raise Refusal("verified WAV decode returned an invalid shape")
    mono = data[:, 0] if data.shape[1] == 1 else data.mean(axis=1, dtype=np.float32)
    pcm = worker.resample_to_16k(mono, int(source_rate))
    if (getattr(pcm, "dtype", None) is None or len(pcm) < 1
            or not np.isfinite(pcm).all()):
        raise Refusal("verified WAV resample is invalid")
    return np.ascontiguousarray(pcm, dtype=np.float32)


def _collect_final_events(events, output):
    for event in events:
        if event.get("final"):
            text = event.get("text")
            if isinstance(text, str) and text.strip():
                output.append(text.strip())


def _collect_final(worker, events, output):
    _collect_final_events(worker.line_events(events), output)


def _transcribe_one(sample, asr, worker, route, decode_audio=_decode_audio):
    try:
        pcm = decode_audio(sample, worker)
    except Refusal:
        raise
    except Exception as exc:
        raise Refusal("verified FLEURS audio decode failed (%s)" %
                      type(exc).__name__) from None
    chunk = int(asr.chunk)
    if chunk != CHUNK_SAMPLES:
        raise Refusal("StreamAsr chunk size is not the pinned 560 ms size")
    if abs((len(pcm) / TARGET_SR) - sample["audio_s"]) > 0.02:
        raise Refusal("decoded WAV duration differs from the pinned metadata")
    total_chunks = (len(pcm) + chunk - 1) // chunk
    if total_chunks <= 0:
        raise Refusal("verified WAV contains no complete stream chunk")
    former = worker.LineFormer(min_chars=1, emit_partial=True)
    final_lines = []
    chunk_stats = []
    total_inference = 0.0
    finish_s = 0.0
    first_asr_chunk_finish_s = None
    first_asr_chunk_added_s = None
    first_visible_line_finish_s = None
    first_visible_line_added_s = None
    for index in range(total_chunks):
        start = index * chunk
        stop = min(start + chunk, len(pcm))
        valid = pcm[start:stop]
        np = sys.modules.get("numpy")
        if (np is None or not callable(getattr(np, "zeros", None))
                or not hasattr(np, "float32")):
            raise Refusal("verified NumPy chunk buffer factory is unavailable")
        pcm_chunk = np.zeros(chunk, dtype=np.float32)
        pcm_chunk[:len(valid)] = valid
        chunk_audio_s = len(valid) / TARGET_SR
        end_s = min((index + 1) * chunk / TARGET_SR, sample["audio_s"])
        t0 = time.perf_counter()
        try:
            text, _token_count = asr.run_chunk(pcm_chunk)
        except Refusal:
            raise
        except Exception as exc:
            raise Refusal("Nemotron stream chunk %d failed (%s)" %
                          (index, type(exc).__name__)) from None
        inference_s = max(0.0, time.perf_counter() - t0)
        total_inference += inference_s
        paced_start_s = max(finish_s, end_s)
        asr_chunk_finish_s = paced_start_s + inference_s
        push_started = time.perf_counter()
        try:
            push_events = worker.line_events(former.push(
                text, start / TARGET_SR, end_s, continues=asr.chunk_continues))
        except Refusal:
            raise
        except Exception as exc:
            raise Refusal("Nemotron line event %d failed (%s)" %
                          (index, type(exc).__name__)) from None
        push_elapsed_s = max(0.0, time.perf_counter() - push_started)
        _collect_final_events(push_events, final_lines)
        visible_line_event = any(
            isinstance(event.get("text"), str) and event["text"].strip()
            for event in push_events)
        visible_finish_s = asr_chunk_finish_s + push_elapsed_s
        if not (text or "").strip():
            _collect_final(worker, former.publish_on_silence(end_s), final_lines)
        _collect_final(worker, former.take_closed(), final_lines)
        finish_s = paced_start_s + max(0.0, time.perf_counter() - t0)

        # ASR output is available after run_chunk; the visible event is available
        # only after production line_events(former.push(...)) has returned.
        # Both use modeled 560 ms arrivals, not live microphone/UI timing.
        first_nonempty_asr_chunk = bool((text or "").strip())
        if first_nonempty_asr_chunk and first_asr_chunk_finish_s is None:
            first_asr_chunk_finish_s = asr_chunk_finish_s
            first_asr_chunk_added_s = max(0.0, asr_chunk_finish_s - end_s)
        if visible_line_event and first_visible_line_finish_s is None:
            first_visible_line_finish_s = visible_finish_s
            first_visible_line_added_s = max(0.0, visible_finish_s - end_s)
        chunk_stats.append({"index": index, "audio_s": round(chunk_audio_s, 6),
                            "inference_s": round(inference_s, 6),
                            "line_event_s": round(push_elapsed_s, 6),
                            "rtf": round(inference_s / chunk_audio_s, 6),
                            "first_nonempty_asr_chunk": first_nonempty_asr_chunk,
                            "first_nonempty_visible_line_event": visible_line_event,
                            "paced_added_latency_s": round(max(0.0, finish_s - end_s), 6)})
    _collect_final(worker, former.flush(), final_lines)
    _collect_final(worker, former.take_closed(), final_lines)
    text = " ".join(final_lines).strip()
    if len(text.encode("utf-8")) > MAX_ROW_TEXT_BYTES:
        raise Refusal("hypothesis exceeds the private row text budget")
    row = {
        "id": sample["id"], "text": text,
        "audio_sha256": sample["audio_sha256"],
        "audio_s": round(sample["audio_s"], 6),
        "inference_s": round(total_inference, 6),
        "_text_sha256": _sha(text.encode("utf-8")),
        "_run_key": None,
        "_route": route,
        "_audio_samples_16k": len(pcm),
        "_chunk_stats": chunk_stats,
        "_first_nonempty_asr_chunk_finish_s": (None if first_asr_chunk_finish_s is None
                                                else round(first_asr_chunk_finish_s, 6)),
        "_first_nonempty_asr_chunk_added_s": (None if first_asr_chunk_added_s is None
                                              else round(first_asr_chunk_added_s, 6)),
        "_first_nonempty_visible_line_event_finish_s": (
            None if first_visible_line_finish_s is None
            else round(first_visible_line_finish_s, 6)),
        "_first_nonempty_visible_line_event_added_s": (
            None if first_visible_line_added_s is None
            else round(first_visible_line_added_s, 6)),
    }
    return row


def _process_pending(samples, rows, run_key, asr, worker, route, result_path,
                     decode_audio=_decode_audio):
    # The actual consumer readbacks are checked once, before the first decode.
    actual_route = _route_facts(asr, route["ort_pool_plan"],
                                route["runtime_package_identity"])
    for field in ("device", "registered_graph_providers", "graph_assignment",
                  "cpu_ep_fallback", "runtime_fallback", "genai_device",
                  "runtime_module_identity", "runtime_package_identity"):
        if route.get(field) != actual_route.get(field):
            raise Refusal("cached route differs from the live StreamAsr readback")
    if (route.get("assignment_model_identity") != route.get("model_identity")
            or not isinstance(route.get("model_identity"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", route.get("model_identity", ""))):
        raise Refusal("graph assignment is not bound to the pinned model identity")
    _require_thread_budget(route.get("named_ort_intra_op_tids"), route.get("process_tids"),
                           route.get("approved_process_tids"))
    if int(getattr(asr, "chunk", 0)) != CHUNK_SAMPLES:
        raise Refusal("StreamAsr chunk size is not the pinned 560 ms size")
    session_signature = tuple(id(getattr(asr, name, None))
                              for name in ("enc", "dec", "joint"))
    if any(value == id(None) for value in session_signature):
        raise Refusal("StreamAsr did not retain its three acoustic sessions")
    started_any = False
    for sample in samples:
        if sample["id"] in rows:
            continue
        if started_any:
            asr.reset_stream_state()
            asr.reset_frontend()
            if tuple(id(getattr(asr, name, None))
                     for name in ("enc", "dec", "joint")) != session_signature:
                raise Refusal("StreamAsr sessions changed between utterances")
        row = _transcribe_one(sample, asr, worker, route, decode_audio=decode_audio)
        row["_run_key"] = run_key
        row["_row_sha256"] = _sha(_canonical(row))
        if not {"id", "text", "audio_sha256", "audio_s", "inference_s"}.issubset(row):
            raise Refusal("hypothesis row is not scorer-compatible")
        _validate_row(row, sample, run_key)
        rows[sample["id"]] = row
        _atomic_save(result_path, rows)
        started_any = True
    return rows


def _metrics(rows, samples, *, cache_hit: bool, startup: dict, pool: dict):
    chunks = [chunk for sample in samples for chunk in rows[sample["id"]]["_chunk_stats"]]
    first_asr_finish = [row["_first_nonempty_asr_chunk_finish_s"] for row in rows.values()
                        if row.get("_first_nonempty_asr_chunk_finish_s") is not None]
    first_asr_added = [row["_first_nonempty_asr_chunk_added_s"] for row in rows.values()
                       if row.get("_first_nonempty_asr_chunk_added_s") is not None]
    first_visible_finish = [row["_first_nonempty_visible_line_event_finish_s"]
                            for row in rows.values()
                            if row.get("_first_nonempty_visible_line_event_finish_s") is not None]
    first_visible_added = [row["_first_nonempty_visible_line_event_added_s"]
                           for row in rows.values()
                           if row.get("_first_nonempty_visible_line_event_added_s") is not None]
    total_audio = sum(float(rows[s["id"]]["audio_s"]) for s in samples
                      if s["id"] in rows)
    total_inference = sum(float(rows[s["id"]]["inference_s"]) for s in samples
                          if s["id"] in rows)
    expected_chunks = sum(math.ceil(rows[s["id"]]["_audio_samples_16k"] / CHUNK_SAMPLES)
                          for s in samples if s["id"] in rows)
    return {
        "schema": SCHEMA,
        "model_lineage": startup.get("model_lineage", MODEL_LINEAGE),
        "cache_hit": bool(cache_hit),
        "latency_mode": "diagnostic-node-assignment-trace",
        "production_latency_comparable": False,
        "samples_completed": len(rows),
        "samples_expected": len(samples),
        "sample_coverage": round(len(rows) / len(samples), 6) if samples else 0.0,
        "chunks_completed": len(chunks),
        "chunks_expected": expected_chunks,
        "chunk_coverage": round(len(chunks) / expected_chunks, 6) if expected_chunks else 0.0,
        "audio_s": round(total_audio, 6),
        "inference_s": round(total_inference, 6),
        "aggregate_rtf": (round(total_inference / total_audio, 6) if total_audio else None),
        "chunk_inference_s_p50_p95_p99": [_percentile([c["inference_s"] for c in chunks], q)
                                           for q in (0.50, 0.95, 0.99)],
        "chunk_rtf_p50_p95_p99": [_percentile([c["rtf"] for c in chunks], q)
                                   for q in (0.50, 0.95, 0.99)],
        "paced_added_latency_s_p50_p95_p99": [_percentile(
            [c["paced_added_latency_s"] for c in chunks], q) for q in (0.50, 0.95, 0.99)],
        "first_nonempty_asr_chunk_finish_s_p50_p95_p99": [
            _percentile(first_asr_finish, q) for q in (0.50, 0.95, 0.99)],
        "first_nonempty_asr_chunk_added_s_p50_p95_p99": [
            _percentile(first_asr_added, q) for q in (0.50, 0.95, 0.99)],
        "first_nonempty_asr_chunk_samples": len(first_asr_finish),
        "first_nonempty_visible_line_event_finish_s_p50_p95_p99": [
            _percentile(first_visible_finish, q) for q in (0.50, 0.95, 0.99)],
        "first_nonempty_visible_line_event_added_s_p50_p95_p99": [
            _percentile(first_visible_added, q) for q in (0.50, 0.95, 0.99)],
        "first_nonempty_visible_line_event_samples": len(first_visible_finish),
        "startup": startup,
        "ort_pool_plan": pool,
        "thread_counts": {
            "named_ort_intra_op_tids": rows[samples[0]["id"]]["_route"]["named_ort_intra_op_tids"],
            "process_tids": rows[samples[0]["id"]]["_route"]["process_tids"],
            "approved_process_tids": rows[samples[0]["id"]]["_route"]["approved_process_tids"],
            "sampling_phase": rows[samples[0]["id"]]["_route"]["sampling_phase"],
        } if samples and samples[0]["id"] in rows else None,
        "first_nonempty_method": (
            "modeled 560 ms paced arrivals; ASR-chunk time ends at run_chunk, visible-line time ends "
            "after production line_events(former.push(...)); no live capture or UI paint"),
    }


def _summary_line(metrics, result_path, run_key):
    # Transcript text never crosses this output boundary.
    payload = dict(metrics)
    payload["run_key"] = run_key
    payload["hypotheses_path"] = str(result_path)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _run_real(args):
    script_started = RUNNER_ENTRY
    if args.approved_ort_pool_threads is None:
        raise Refusal("explicit --approved-ort-pool-threads is required")
    if args.approved_process_tids is None:
        raise Refusal("explicit --approved-process-tids is required")
    if args.approved_process_tids < 1:
        raise Refusal("--approved-process-tids must be positive")
    effective_environment = _normalize_runtime_environment()
    runtime_versions = _runtime_versions()
    manifest_path = Path(args.manifest)
    model_dir = Path(args.model_dir)
    cache_dir = _safe_child(ROOT / ".agent-work/asr-cache", Path(args.cache_dir))

    # `worker` sets the exact production plan; the environment is pinned before
    # this import. Its three acoustic graphs remain one shared serialized engine
    # plan, but their actual ORT pools are counted separately here.
    import_started = time.perf_counter()
    runtime_package_identity = None
    runtime_identity_prepare_s = None
    startup_stage = "worker-import"
    try:
        with contextlib.redirect_stdout(_SafeSink()), contextlib.redirect_stderr(_SafeSink()):
            from worker import sotto_worker as worker
            if any(name in sys.modules for name in ("onnxruntime", "onnxruntime_genai")):
                raise Refusal("ORT was imported before CUDA DLL search paths")
            pool = _pool_plan(worker, args.threads)
            startup_stage = "cuda-dll-setup"
            dll_dirs_started = time.perf_counter()
            worker._add_cuda_dll_dirs()
            cuda_dll_dirs_s = time.perf_counter() - dll_dirs_started
            worker_import_s = time.perf_counter() - import_started
            startup_stage = "cuda-runtime-preflight"
            identity_started = time.perf_counter()
            runtime_package_identity = _preflight_runtime_package_identity(
                worker, runtime_versions)
            runtime_identity_prepare_s = time.perf_counter() - identity_started
    except Refusal:
        raise
    except Exception as exc:
        raise Refusal("production startup failed at %s (%s)" %
                      (startup_stage, type(exc).__name__)) from None
    worker_import_offset_s = time.perf_counter() - script_started
    print("ORT_POOL_PLAN planned=true " + json.dumps(pool, sort_keys=True,
                                                     separators=(",", ":")))
    _require_pool_approval(pool, args.approved_ort_pool_threads)

    samples, manifest_sha, transcript_sha = _verify_manifest(
        manifest_path, args.expected_manifest_sha256)
    model_identity = _model_identity(model_dir, cache_dir)
    code_identity = _code_identity()

    params = {
        "schema": SCHEMA, "manifest_sha256": manifest_sha,
        "transcript_sidecar_sha256": transcript_sha,
        "audio": [(s["id"], s["audio_sha256"], s["audio_bytes"]) for s in samples],
        "model": model_identity["fingerprint"], "source": code_identity,
        "runtime_versions": runtime_versions,
        "runtime_package_identity": runtime_package_identity,
        "runtime_environment": effective_environment,
        "threads": args.threads, "approved_ort_pool_threads": args.approved_ort_pool_threads,
        "approved_process_tids": args.approved_process_tids,
        "pool": pool, "chunk_samples": CHUNK_SAMPLES, "target_sr": TARGET_SR,
        "lang_id": "pt-BR", "provider": CUDA_PROVIDER, "vad": False,
        "diagnostic_node_assignment_trace": True,
        "model_lineage": MODEL_LINEAGE,
    }
    run_key = _sha(_canonical(params))
    result_path = _safe_child(cache_dir, cache_dir / ("nemotron-stream-" + run_key + ".jsonl"))
    rows = {} if args.no_resume else _load_resume(
        result_path, samples, run_key,
        expected_runtime_package_identity=runtime_package_identity)
    cache_retention = _prune_result_cache(cache_dir, result_path)
    if len(rows) == len(samples):
        cached_runtime_identity = rows[samples[0]["id"]]["_route"]["runtime_module_identity"]
        startup = {"runner_entry_to_worker_import_s": round(worker_import_offset_s, 6),
                   "worker_import_s": round(worker_import_s, 6),
                   "model_ready_s": None, "cuda_preload_s": None,
                   "cuda_dll_dirs_s": round(cuda_dll_dirs_s, 6),
                   "runtime_identity_prepare_s": round(runtime_identity_prepare_s, 6),
                   "runtime_package_identity": runtime_package_identity,
                   "runtime_module_identity": cached_runtime_identity,
                   "route_attestation_s": None,
                   "runtime_module_identity_status": "actual imported build from cached rows; current module/native file IDs/change times match",
                   "frontend_ready_s": None, "source": "cached prior run",
                   "model_identity_hash_cache": model_identity.get("hash_cache"),
                   "model_lineage": MODEL_LINEAGE,
                   "latency_mode": "diagnostic-node-assignment-trace"}
        metrics = _metrics(rows, samples, cache_hit=True, startup=startup, pool=pool)
        metrics["result_cache_retention"] = cache_retention
        print(_summary_line(metrics, result_path, run_key))
        return 0

    # Model tree hashing can take long enough for an installed runtime package
    # to be updated between native preflight and StreamAsr construction.
    _verify_native_package_file_identity(runtime_package_identity)
    process_tids_before_model_load, system_threads_scanned_before_model = (
        _current_process_tids())
    if process_tids_before_model_load > args.approved_process_tids:
        raise Refusal("pre-model process TIDs %d exceed approved process TID budget %d"
                      % (process_tids_before_model_load, args.approved_process_tids))
    print("THREAD_COUNTS phase=pre_model process_tids=%d approved_process_tids=%d "
          "system_threads_scanned=%d"
          % (process_tids_before_model_load, args.approved_process_tids,
             system_threads_scanned_before_model))
    model_started = time.perf_counter()
    sink_out, sink_err = _SafeSink(), _SafeSink()
    public_out = sys.stdout
    try:
        with contextlib.redirect_stdout(sink_out), contextlib.redirect_stderr(sink_err):
            worker.resolve_threads(args.threads)
            asr = worker.StreamAsr(str(model_dir), providers=[CUDA_PROVIDER],
                                   use_vad=False, lang_id="pt-BR")
            model_construct_s = time.perf_counter() - model_started
            model_ready_s = time.perf_counter() - script_started
            asr.start_frontend()
            _ = asr.sp
            frontend_ready_s = time.perf_counter() - script_started
            actual_pool = sink_err.pool_plan or sink_out.pool_plan
            _check_pool_readback(actual_pool, pool, args.approved_ort_pool_threads)
            public_out.write("ORT_POOL_PLAN verified=true " + json.dumps(
                actual_pool, sort_keys=True, separators=(",", ":")) + "\n")
            public_out.flush()
            route_attestation_started = time.perf_counter()
            route = _route_facts(asr, pool, runtime_package_identity)
            route_attestation_s = time.perf_counter() - route_attestation_started
            runtime_module_identity = route["runtime_module_identity"]
            for cached_row in rows.values():
                if (cached_row["_route"].get("runtime_module_identity") != runtime_module_identity
                        or cached_row["_route"].get("runtime_package_identity")
                        != runtime_package_identity):
                    raise Refusal("resumed rows belong to a different imported runtime build")
            ort_intra_op_tids = sink_err.ort_intra_op_tids
            if ort_intra_op_tids is None:
                ort_intra_op_tids = sink_out.ort_intra_op_tids
            if not isinstance(ort_intra_op_tids, int) or ort_intra_op_tids < 0:
                raise Refusal("worker did not report named ORT intra-op TIDs")
            route["named_ort_intra_op_tids_readback"] = ort_intra_op_tids
            route["ort_pool_approved"] = args.approved_ort_pool_threads
            process_tids, system_threads_scanned_post_model = _current_process_tids()
            public_out.write(
                "THREAD_COUNTS observed_phase=post_model_and_frontend_ready_not_peak "
                "named_ort_intra_op_tids=%d process_tids=%d approved_process_tids=%d "
                "system_threads_scanned=%d\n"
                % (ort_intra_op_tids, process_tids, args.approved_process_tids,
                   system_threads_scanned_post_model))
            public_out.flush()
            thread_counts = _require_thread_budget(ort_intra_op_tids, process_tids,
                                                   args.approved_process_tids)
            route.update(thread_counts)
            route["model_revision"] = model_identity["revision"]
            route["model_identity"] = model_identity["fingerprint"]
            route["assignment_model_identity"] = model_identity["fingerprint"]
            startup = {
                "runner_entry_to_worker_import_s": round(worker_import_offset_s, 6),
                "worker_import_s": round(worker_import_s, 6),
                "cuda_dll_dirs_s": round(cuda_dll_dirs_s, 6),
                "runtime_identity_prepare_s": round(runtime_identity_prepare_s, 6),
                "route_attestation_s": round(route_attestation_s, 6),
                "cuda_preload_s": _cuda_preload_duration(getattr(worker, "_BOOT_PROF", {})),
                "cuda_preload_ready_offset_s": _safe_timing(
                    getattr(worker, "_BOOT_PROF", {}).get("ort_cuda_dlls_preload")),
                "model_ready_s": round(model_ready_s, 6),
                "model_construct_s": round(model_construct_s, 6),
                "session_phases_s": getattr(asr, "load_phases_s", None),
                "frontend_ready_s": round(frontend_ready_s, 6),
                "ort_cuda_dlls_preloaded": bool(getattr(asr, "ort_cuda_dlls_preloaded", False)),
                "named_ort_intra_op_tids_readback": ort_intra_op_tids,
                "process_tids_readback": thread_counts["process_tids"],
                "process_tids_before_model_load": process_tids_before_model_load,
                "system_threads_scanned_before_model_load": system_threads_scanned_before_model,
                "system_threads_scanned_post_model": system_threads_scanned_post_model,
                "approved_process_tids": thread_counts["approved_process_tids"],
                "thread_count_sampling_phase": thread_counts["sampling_phase"],
                "runtime_versions": runtime_versions,
                "runtime_module_identity_sha256": _sha(_canonical(runtime_module_identity)),
                "runtime_package_identity_sha256": _sha(_canonical(runtime_package_identity)),
                "runtime_packages": sorted(runtime_package_identity),
                "runtime_module_identity_status": "actual imported ORT and ORT-GenAI verified before audio decode",
                "runtime_environment_fingerprint": effective_environment["fingerprint"],
                "model_identity_hash_cache_entries": len(model_identity.get("hash_cache") or {}),
                "model_lineage": MODEL_LINEAGE,
                "latency_mode": "diagnostic-node-assignment-trace",
            }
            public_out.write("ASR_READY " + json.dumps(
                startup, sort_keys=True, separators=(",", ":")) + "\n")
            public_out.write(
                "THREAD_PLAN verified=true ort_intra_aggregate=%d named_ort_intra_op_tids=%d env_threads=1\n"
                % (pool["ort_intra_aggregate"], ort_intra_op_tids))
            public_out.write(
                "THREAD_BUDGET admitted=true named_ort_intra_op_tids=%d process_tids=%d approved_process_tids=%d\n"
                % (thread_counts["named_ort_intra_op_tids"], thread_counts["process_tids"],
                   thread_counts["approved_process_tids"]))
            public_out.flush()
        try:
            with contextlib.redirect_stdout(sink_out), contextlib.redirect_stderr(sink_err):
                rows = _process_pending(samples, rows, run_key, asr, worker, route,
                                        result_path)
        except Refusal:
            raise
        except Exception as exc:
            raise Refusal("Nemotron stream row/cache handling failed (%s at %s)" %
                          (type(exc).__name__, _safe_exception_site(exc))) from None
            del asr
    except Refusal:
        raise
    except Exception:
        raise Refusal("CUDA-only StreamAsr FLEURS replay failed closed") from None
    # Startup timings are output-only; each result row is content-addressed by
    # model/code/cohort/config and carries the per-sample acoustic timings.
    cache_retention = _prune_result_cache(cache_dir, result_path)
    metrics = _metrics(rows, samples, cache_hit=False, startup=startup, pool=pool)
    metrics["result_cache_retention"] = cache_retention
    print(_summary_line(metrics, result_path, run_key))
    return 0


def _safe_timing(value):
    value = _valid_number(value)
    return None if value is None else round(value, 6)


def _cuda_preload_duration(marks):
    if not isinstance(marks, dict):
        return None
    start = _valid_number(marks.get("ort_import"))
    end = _valid_number(marks.get("ort_cuda_dlls_preload"))
    if start is None or end is None or end < start:
        return None
    return round(end - start, 6)


def _selftest():
    """Synthetic only: no worker/ORT/audio/model/GPU imports or files outside H:."""
    import tempfile
    import types
    import io
    import importlib.util

    if not sys.path or os.path.normcase(sys.path[0]) != os.path.normcase(str(ROOT)):
        raise AssertionError("runner did not put its project root first on sys.path")
    if any(os.environ.get(name) != "1" for name in THREAD_ENV):
        raise AssertionError("selftest thread environment is not pinned to one")
    if any(name in sys.modules for name in
           ("worker.sotto_worker", "onnxruntime", "onnxruntime_genai", "soundfile", "numpy")):
        raise AssertionError("selftest unexpectedly imported a model/audio runtime")

    try:
        object()._safe_probe_attribute
    except AttributeError as exc:
        diagnostic = _safe_exception_site(exc)
    else:
        raise AssertionError("safe failure-site fixture did not fail")
    if (Path(diagnostic.split(":", 1)[0]).name != Path(__file__).name
            or "attribute=_safe_probe_attribute" not in diagnostic
            or "object at" in diagnostic):
        raise AssertionError("safe failure-site diagnostic is incomplete or leaks repr")

    helper_spec = importlib.util.spec_from_file_location(
        "_sotto_asr_node_assignment_fake", WORKER_DIR / "asr_node_assignment.py")
    if helper_spec is None or helper_spec.loader is None:
        raise AssertionError("dependency-free node assignment helper is unavailable")
    assignment_helper = importlib.util.module_from_spec(helper_spec)
    helper_spec.loader.exec_module(assignment_helper)

    class FakeAssignment:
        def __init__(self, provider, node_count=1):
            self.ep_name = provider
            self._node_count = node_count

        def get_nodes(self):
            class _SizedNodes:
                def __len__(inner_self):
                    return self._node_count
            return _SizedNodes()

    class FakeAssignmentSession:
        def __init__(self, assignments):
            self._assignments = assignments

        def get_provider_graph_assignment_info(self):
            return self._assignments

    positive_sessions = {name: FakeAssignmentSession([FakeAssignment(CUDA_PROVIDER, 3)])
                         for name in ("encoder", "decoder", "joint")}
    collected = assignment_helper.collect_graph_assignment_facts(positive_sessions)
    assert collected["encoder"]["providers"] == {CUDA_PROVIDER: 3}
    assert collected["joint"]["total_nodes"] == 3
    assert set(_normalized_graph_assignments(collected)) == {"encoder", "decoder", "joint"}
    assignment_helper_refusals = 0
    for bad_sessions in (
            {name: FakeAssignmentSession([FakeAssignment(CUDA_PROVIDER)])
             for name in ("encoder", "decoder")},
            {name: FakeAssignmentSession([])
             for name in ("encoder", "decoder", "joint")},
            {**positive_sessions, "joint": FakeAssignmentSession(
                [FakeAssignment(CUDA_PROVIDER), FakeAssignment("CPUExecutionProvider")])},
            {**positive_sessions, "joint": FakeAssignmentSession(
                [FakeAssignment(CUDA_PROVIDER), FakeAssignment("UnknownExecutionProvider")])},
            {**positive_sessions, "joint": FakeAssignmentSession(
                [FakeAssignment(CUDA_PROVIDER, 1_000_001)])},
            {**positive_sessions, "joint": FakeAssignmentSession(
                [FakeAssignment(CUDA_PROVIDER)] * (assignment_helper.MAX_ASSIGNMENT_SUBGRAPHS + 1))}):
        try:
            assignment_helper.collect_graph_assignment_facts(bad_sessions)
            _normalized_graph_assignments(
                assignment_helper.collect_graph_assignment_facts(bad_sessions))
        except (RuntimeError, Refusal):
            assignment_helper_refusals += 1
        else:
            raise AssertionError("adverse graph assignment was accepted")

    code_identity = _code_identity()
    assert {"ort_cuda_runtime", "node_assignment_helper"}.issubset(code_identity)
    _require_gpu_runtime_package_choice({"onnxruntime-gpu": "1.30.0",
                                         "onnxruntime": None})
    # Both distribution records can coexist in the environment; the safety
    # property is that Python resolves the import to the GPU package itself.
    _require_gpu_runtime_package_choice({"onnxruntime-gpu": "1.30.0",
                                         "onnxruntime": "1.30.0"})
    runtime_package_refusals = 0
    for versions in ({"onnxruntime-gpu": None, "onnxruntime": "1.30.0"},
                     {"onnxruntime-gpu": None, "onnxruntime": None}):
        try:
            _require_gpu_runtime_package_choice(versions)
        except Refusal:
            runtime_package_refusals += 1
    assert runtime_package_refusals == 2
    runner_path = Path(__file__).resolve()
    worker_path = (WORKER_DIR / "sotto_worker.py").resolve()
    _require_gpu_ort_module_path(runner_path, runner_path)
    gpu_module_path_refusals = 0
    for imported_path, gpu_path in ((worker_path, runner_path),
                                    (runner_path, worker_path),
                                    (runner_path, runner_path.parent / "missing-ort-init.py")):
        try:
            _require_gpu_ort_module_path(imported_path, gpu_path)
        except Refusal:
            gpu_module_path_refusals += 1
    assert gpu_module_path_refusals == 3

    fake_ort_build = "synthetic ORT CUDA build identity; no provider/session probe"
    fake_ort_module = types.SimpleNamespace(
        __file__=str(Path(__file__).resolve()), __version__="1.30.0",
        get_build_info=lambda: fake_ort_build,
        get_available_providers=lambda: [CUDA_PROVIDER, "CPUExecutionProvider"])
    fake_ort_identity = _onnxruntime_module_identity(
        fake_ort_module, Path(__file__).resolve(), "1.30.0")
    runtime_identity_refusals = 0
    for module, expected_file, expected_version in (
            (fake_ort_module, WORKER_DIR / "sotto_worker.py", "1.30.0"),
            (fake_ort_module, Path(__file__).resolve(), "1.29.0"),
            (types.SimpleNamespace(__file__=str(Path(__file__).resolve()),
                                   __version__="1.30.0",
                                   get_build_info=lambda: fake_ort_build,
                                   get_available_providers=lambda: ["CPUExecutionProvider"]),
             Path(__file__).resolve(), "1.30.0"),
            (types.SimpleNamespace(__file__=str(Path(__file__).resolve()),
                                   __version__="1.30.0"),
             Path(__file__).resolve(), "1.30.0"),
            (types.SimpleNamespace(__file__=str(Path(__file__).resolve()),
                                   __version__="1.30.0",
                                   get_build_info=lambda: "b" *
                                   (MAX_RUNTIME_MODULE_METADATA_BYTES + 1)),
             Path(__file__).resolve(), "1.30.0")):
        try:
            _onnxruntime_module_identity(module, expected_file, expected_version)
        except Refusal:
            runtime_identity_refusals += 1
    assert runtime_identity_refusals == 5
    cuda_provider_refusals = 0
    for providers in ([CUDA_PROVIDER, "CPUExecutionProvider"],
                      ["CPUExecutionProvider"], None):
        try:
            _require_cuda_provider_available(providers)
        except Refusal:
            cuda_provider_refusals += 1
    assert cuda_provider_refusals == 2

    fake_genai_file = WORKER_DIR / "models/.sotto-runtime/genai-cuda/onnxruntime_genai/__init__.py"
    fake_genai_identity = _genai_source_identity(fake_genai_file, "0.17.1")
    fake_genai_module = types.SimpleNamespace(
        __file__=str(fake_genai_file), __version__=fake_genai_identity["version"],
        __commit__=fake_genai_identity["commit"], __id__=fake_genai_identity["package_id"])
    assert _actual_genai_module_identity(fake_genai_module, "0.17.1") == fake_genai_identity
    try:
        _actual_genai_module_identity(types.SimpleNamespace(
            __file__=str(fake_genai_file), __version__="0.0.0",
            __commit__=fake_genai_identity["commit"], __id__=fake_genai_identity["package_id"]),
            "0.17.1")
    except Refusal:
        runtime_identity_refusals += 1
    else:
        raise AssertionError("mismatched imported ORT-GenAI version was accepted")
    assert runtime_identity_refusals == 6
    cache_root = ROOT / ".agent-work/asr-cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    runtime_native_temp = tempfile.TemporaryDirectory(
        prefix="fleurs-runtime-native-selftest-", dir=str(cache_root))
    runtime_native_root = Path(runtime_native_temp.name)
    fake_ort_native = runtime_native_root / "onnxruntime_pybind11_state.pyd"
    fake_genai_native = runtime_native_root / "onnxruntime_genai.cp311-win_amd64.pyd"
    fake_ort_native.write_bytes(b"synthetic ORT native module; never loaded")
    fake_genai_native.write_bytes(b"synthetic GenAI native module; never loaded")
    fake_ort_native_module_key = "_sotto_selftest_ort_native_module"
    fake_genai_native_module_key = "_sotto_selftest_genai_native_module"
    if fake_ort_native_module_key in sys.modules or fake_genai_native_module_key in sys.modules:
        raise AssertionError("synthetic native module key already exists")
    sys.modules[fake_ort_native_module_key] = types.SimpleNamespace(
        __file__=str(fake_ort_native))
    sys.modules[fake_genai_native_module_key] = types.SimpleNamespace(
        __file__=str(fake_genai_native))
    runner_file = Path(__file__).resolve()
    fake_runtime_package_identity = {
        "onnxruntime": {"module_file": str(runner_file), "version": "1.30.0",
                        "module_signature": _model_file_signature(runner_file),
                        "native_files": [{"file": str(fake_ort_native),
                                          "signature": _model_file_signature(fake_ort_native)}]},
        "onnxruntime_genai": dict(fake_genai_identity, native_files=[
            {"file": str(fake_genai_native),
             "signature": _model_file_signature(fake_genai_native)}]),
    }
    fake_runtime_identity = _actual_runtime_module_identity(
        fake_ort_module, fake_genai_module, fake_runtime_package_identity)
    assert _runtime_package_identity_shape_valid(fake_runtime_package_identity)
    assert _runtime_identities_bind(fake_runtime_identity, fake_runtime_package_identity)
    fake_runtime_identity_mutant = {name: dict(value)
                                    for name, value in fake_runtime_identity.items()}
    fake_runtime_identity_mutant["onnxruntime_genai"] = dict(
        fake_runtime_identity["onnxruntime_genai"])
    fake_runtime_identity_mutant["onnxruntime_genai"]["module_file"] = str(runner_file)
    assert not _runtime_identities_bind(fake_runtime_identity_mutant,
                                        fake_runtime_package_identity)
    wrong_native_root = runtime_native_root / "wrong"
    wrong_native_root.mkdir()
    wrong_ort_native = wrong_native_root / fake_ort_native.name
    wrong_ort_native.write_bytes(b"different synthetic module; never loaded")
    good_native_module = sys.modules.pop(fake_ort_native_module_key)
    sys.modules[fake_ort_native_module_key] = types.SimpleNamespace(
        __file__=str(wrong_ort_native))
    try:
        _actual_runtime_module_identity(
            fake_ort_module, fake_genai_module, fake_runtime_package_identity)
    except Refusal:
        pass
    else:
        raise AssertionError("mismatched loaded ORT extension path was accepted")
    finally:
        sys.modules[fake_ort_native_module_key] = good_native_module
    runtime_extension_refusals = 1

    # Exercise a same-size atomic weight replacement with the old mtime.
    with tempfile.TemporaryDirectory(prefix="fleurs-model-identity-selftest-",
                                     dir=str(cache_root)) as identity_temp:
        fake_weight = Path(identity_temp) / "fake-weight.bin"
        replacement_weight = Path(identity_temp) / "replacement-weight.bin"
        fake_weight.write_bytes(b"abc123")
        before_signature = _model_file_signature(fake_weight)
        first_digest = _digest_model_file(fake_weight, max_bytes=1024)
        cached_digest = dict(first_digest, signature=before_signature)
        assert _reuse_cached_model_digest(
            cached_digest, before_signature, pinned_lfs=first_digest["sha256"],
            expected_blob=first_digest["git_blob_sha1"]) == cached_digest
        replacement_weight.write_bytes(b"xyz789")
        os.utime(replacement_weight, ns=(replacement_weight.stat().st_atime_ns,
                                         before_signature["mtime_ns"]))
        os.replace(replacement_weight, fake_weight)
        changed_signature = _model_file_signature(fake_weight)
        assert changed_signature["size"] == before_signature["size"]
        assert changed_signature["mtime_ns"] == before_signature["mtime_ns"]
        assert changed_signature["file_id"] != before_signature["file_id"]
        assert _reuse_cached_model_digest(
            cached_digest, changed_signature, pinned_lfs=first_digest["sha256"],
            expected_blob=first_digest["git_blob_sha1"]) is None
        changed_digest = _digest_model_file(fake_weight, max_bytes=1024)
        assert changed_digest["sha256"] != first_digest["sha256"]

    env_keys = ("SOTTO_LOAD_AB", "SOTTO_GENAI_CPUS", "SOTTO_CUDA_MEM_LIMIT_MB",
                "SOTTO_CUDA_ARENA", "SOTTO_CUDNN_ALGO_SEARCH", "CUDA_MODULE_LOADING",
                "CUDA_VISIBLE_DEVICES", "CUDA_DEVICE_ORDER")
    prior_env = {name: os.environ.get(name) for name in env_keys}
    try:
        os.environ.update({"SOTTO_LOAD_AB": " FULL ", "SOTTO_GENAI_CPUS": "0,1;2-3",
                           "SOTTO_CUDA_MEM_LIMIT_MB": "0", "SOTTO_CUDA_ARENA": "",
                           "SOTTO_CUDNN_ALGO_SEARCH": "", "CUDA_MODULE_LOADING": "LAZY",
                           "CUDA_VISIBLE_DEVICES": " 0 ", "CUDA_DEVICE_ORDER": "pci_bus_id"})
        env_a = _normalize_runtime_environment()
        assert env_a["sotto_load_ab"] == "full"
        assert env_a["sotto_genai_cpus"] == "0,1,2,3"
        os.environ["SOTTO_GENAI_CPUS"] = "0-3"
        env_b = _normalize_runtime_environment()
        assert env_a["fingerprint"] == env_b["fingerprint"]
        os.environ["SOTTO_LOAD_AB"] = "bytes full"
        env_c = _normalize_runtime_environment()
        assert env_c["fingerprint"] != env_b["fingerprint"]
        env_refusal = 0
        os.environ["SOTTO_GENAI_CPUS"] = "0-64"
        try:
            _normalize_runtime_environment()
        except Refusal:
            env_refusal = 1
        assert env_refusal == 1
    finally:
        for name, value in prior_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    retention_refusals = 0
    with tempfile.TemporaryDirectory(prefix="fleurs-cache-retention-selftest-",
                                     dir=str(cache_root)) as retention_temp:
        retention_dir = Path(retention_temp)
        current_cache = retention_dir / ("nemotron-stream-" + "f" * 64 + ".jsonl")
        other_paths = []
        for index in range(7):
            path = retention_dir / ("nemotron-stream-%064x.jsonl" % index)
            path.write_bytes(b"x")
            os.utime(path, ns=(index + 1, index + 1))
            other_paths.append(path)
        unrelated = retention_dir / "do-not-prune.txt"
        unrelated.write_text("owned by another cache user", encoding="utf-8")
        retention = _prune_result_cache(retention_dir, current_cache)
        assert retention["pruned"] == 3 and len(list(retention_dir.glob("nemotron-stream-*.jsonl"))) == 4
        current_cache.write_bytes(b"x")
        retention = _prune_result_cache(retention_dir, current_cache)
        assert retention["files"] == 5 and current_cache.exists() and unrelated.exists()
        malformed = retention_dir / ("nemotron-stream-" + "a" * 64 + ".jsonl")
        malformed.mkdir()
        try:
            _prune_result_cache(retention_dir, current_cache)
        except Refusal:
            retention_refusals = 1
        assert retention_refusals == 1 and unrelated.exists()

    class FakeVector(list):
        pass

    class FakeNumpy:
        float32 = "float32"

        @staticmethod
        def zeros(count, dtype=None):
            return FakeVector([0.0] * count)

    if "numpy" in sys.modules:
        raise AssertionError("selftest imported NumPy before the synthetic decode route")
    fake_numpy_module = types.ModuleType("numpy")
    fake_numpy_module.zeros = FakeNumpy.zeros
    fake_numpy_module.float32 = FakeNumpy.float32
    sys.modules["numpy"] = fake_numpy_module

    class FakeFormer:
        def __init__(self, **_kwargs):
            self.parts = []

        def push(self, text, *_args, **_kwargs):
            if text:
                self.parts.append(text)
                return [{"text": " ".join(self.parts), "final": False}]
            return []

        def publish_on_silence(self, *_args):
            return []

        def take_closed(self):
            return []

        def flush(self):
            if not self.parts:
                return []
            text = " ".join(self.parts)
            self.parts = []
            return [{"text": text, "final": True}]

    class FakeFormerWithoutVisibleEvents(FakeFormer):
        def push(self, text, *_args, **_kwargs):
            if text:
                self.parts.append(text)
            return []

    class FakeAsr:
        def __init__(self, good=True):
            self.chunk = CHUNK_SAMPLES
            self.enc, self.dec, self.joint = object(), object(), object()
            self.chunk_continues = False
            self.device = "cuda" if good else "cpu"
            self.ort = fake_ort_module
            self.genai_module = fake_genai_module
            self.providers_requested = [CUDA_PROVIDER]
            self.session_providers = {name: [CUDA_PROVIDER] for name in ("encoder", "decoder", "joint")}
            self.graph_assignment_info = {
                name: {"providers": {CUDA_PROVIDER: 1}, "total_nodes": 1,
                       "method": "get_provider_graph_assignment_info"}
                for name in ("encoder", "decoder", "joint")}
            self.cpu_ep_fallback_disabled = True
            self.runtime_fallback_disabled = True
            self.genai_device_type = "cuda"
            self.use_vad = False
            self.resets = 0
            self.frontend_resets = 0
            self.chunk_calls = 0

        def run_chunk(self, _chunk):
            self.chunk_calls += 1
            return ("TRANSCRIPT_SENTINEL" if self.chunk_calls % 2 else ""), 1

        def reset_stream_state(self):
            self.resets += 1

        def reset_frontend(self):
            self.frontend_resets += 1

    fake_worker = types.SimpleNamespace(LineFormer=FakeFormer,
                                        line_events=lambda events: list(events or ()))
    plan = {"ort_pool_plan": {"process_budget_requested": 1, "encoder_intra": 1,
                              "small_intra": 1, "ort_sessions": 3,
                              "ort_intra_aggregate": 3, "batch_intra": 1}}
    route = {"device": "cuda", "registered_graph_providers": {
             name: [CUDA_PROVIDER] for name in ("encoder", "decoder", "joint")},
             "graph_assignment": {name: {"providers": {CUDA_PROVIDER: 1},
                                          "total_nodes": 1,
                                          "method": "get_provider_graph_assignment_info"}
                                  for name in ("encoder", "decoder", "joint")},
             "cpu_ep_fallback": "disabled", "runtime_fallback": "disabled",
             "genai_device": "cuda", "ort_pool_plan": plan["ort_pool_plan"],
             "runtime_module_identity": fake_runtime_identity,
             "runtime_package_identity": fake_runtime_package_identity,
             "model_identity": "f" * 64, "assignment_model_identity": "f" * 64,
             "named_ort_intra_op_tids": 1, "process_tids": 5,
             "approved_process_tids": 8,
             "sampling_phase": "post_model_and_frontend_ready_not_peak"}
    samples = [
        {"id": "fleurs_000", "audio_sha256": "a" * 64, "audio_s": 9_000 / TARGET_SR,
         "audio_path": Path("fake-000.wav")},
        {"id": "fleurs_001", "audio_sha256": "b" * 64, "audio_s": 9_000 / TARGET_SR,
         "audio_path": Path("fake-001.wav")},
    ]
    decoded = {"count": 0}

    def fake_decode(_path, _worker):
        decoded["count"] += 1
        return FakeVector([0.0] * 9_000)

    (ROOT / ".agent-work/asr-cache").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fleurs-nemotron-selftest-",
                                     dir=str(ROOT / ".agent-work/asr-cache")) as temp:
        cache_path = Path(temp) / "fake.jsonl"
        asr = FakeAsr()
        rows = _process_pending(samples, {}, "f" * 64, asr, fake_worker, route,
                               cache_path, decode_audio=fake_decode)
        assert len(rows) == 2 and decoded["count"] == 2
        assert asr.chunk_calls == 4 and asr.resets == 1 and asr.frontend_resets == 1
        assert all(row["text"] == "TRANSCRIPT_SENTINEL" for row in rows.values())
        assert all(row["_first_nonempty_asr_chunk_finish_s"] is not None
                   for row in rows.values())
        assert all(row["_first_nonempty_visible_line_event_finish_s"] is not None
                   for row in rows.values())
        saved_raw = cache_path.read_text(encoding="utf-8")
        assert "TRANSCRIPT_SENTINEL" in saved_raw
        resumed = _load_resume(cache_path, samples, "f" * 64,
                               expected_runtime_package_identity=fake_runtime_package_identity)
        mismatched_runtime_package = dict(fake_runtime_package_identity)
        mismatched_runtime_package["onnxruntime_genai"] = dict(
            fake_runtime_package_identity["onnxruntime_genai"], version="0.0.0")
        try:
            _load_resume(cache_path, samples, "f" * 64,
                         expected_runtime_package_identity=mismatched_runtime_package)
        except Refusal:
            pass
        else:
            raise AssertionError("cached runtime package identity mutation was accepted")
        second = FakeAsr()
        _process_pending(samples, resumed, "f" * 64, second, fake_worker, route,
                         cache_path, decode_audio=fake_decode)
        assert decoded["count"] == 2 and second.chunk_calls == 0
        assert second.resets == 0 and second.frontend_resets == 0

        no_visible_worker = types.SimpleNamespace(
            LineFormer=FakeFormerWithoutVisibleEvents,
            line_events=lambda events: list(events or ()))
        no_visible_path = Path(temp) / "no-visible.jsonl"
        no_visible_rows = _process_pending(
            samples[:1], {}, "e" * 64, FakeAsr(), no_visible_worker, route,
            no_visible_path, decode_audio=fake_decode)
        no_visible_row = no_visible_rows["fleurs_000"]
        assert no_visible_row["_first_nonempty_asr_chunk_finish_s"] is not None
        assert no_visible_row["_first_nonempty_visible_line_event_finish_s"] is None

        # Each adverse registration/assignment route fails before WAV decode.
        route_refusals = 0
        decode_suppressed = 0
        for field, bad in (("device", "cpu"), ("cpu_ep_fallback_disabled", False),
                           ("runtime_fallback_disabled", False)):
            adverse = FakeAsr()
            setattr(adverse, field, bad)
            before = decoded["count"]
            try:
                _process_pending(samples[:1], {}, "f" * 64, adverse, fake_worker,
                                 route, cache_path, decode_audio=fake_decode)
            except Refusal:
                route_refusals += 1
            else:
                raise AssertionError("adverse route was accepted")
            assert decoded["count"] == before
            decode_suppressed += 1

        adverse = FakeAsr()
        adverse.genai_module = types.SimpleNamespace(
            __file__=str(fake_genai_file), __version__="0.0.0",
            __commit__=fake_genai_identity["commit"],
            __id__=fake_genai_identity["package_id"])
        before = decoded["count"]
        try:
            _process_pending(samples[:1], {}, "f" * 64, adverse, fake_worker,
                             route, cache_path, decode_audio=fake_decode)
        except Refusal:
            route_refusals += 1
        else:
            raise AssertionError("stale ORT-GenAI module identity reached audio decode")
        assert decoded["count"] == before
        decode_suppressed += 1

        adverse_route = dict(route)
        adverse_package = {name: dict(package)
                           for name, package in fake_runtime_package_identity.items()}
        adverse_package["onnxruntime"]["native_files"] = [dict(item) for item in
            fake_runtime_package_identity["onnxruntime"]["native_files"]]
        adverse_package["onnxruntime"]["native_files"][0]["signature"] = dict(
            adverse_package["onnxruntime"]["native_files"][0]["signature"])
        adverse_package["onnxruntime"]["native_files"][0]["signature"]["mtime_ns"] += 1
        adverse_route["runtime_package_identity"] = adverse_package
        before = decoded["count"]
        try:
            _process_pending(samples[:1], {}, "f" * 64, FakeAsr(), fake_worker,
                             adverse_route, cache_path, decode_audio=fake_decode)
        except Refusal:
            route_refusals += 1
        else:
            raise AssertionError("changed native runtime file identity reached audio decode")
        assert decoded["count"] == before
        decode_suppressed += 1

        adverse = FakeAsr()
        adverse.session_providers["joint"] = ["CPUExecutionProvider"]
        before = decoded["count"]
        try:
            _process_pending(samples[:1], {}, "f" * 64, adverse, fake_worker,
                             route, cache_path, decode_audio=fake_decode)
        except Refusal:
            route_refusals += 1
        else:
            raise AssertionError("graph without CUDA readback was accepted")
        assert decoded["count"] == before
        decode_suppressed += 1

        assignment_mutants = []
        absent_trace = FakeAsr()
        absent_trace.graph_assignment_info = None
        assignment_mutants.append(("trace absent", absent_trace))
        incomplete_assignment = FakeAsr()
        incomplete_assignment.graph_assignment_info.pop("joint")
        assignment_mutants.append(("incomplete graph set", incomplete_assignment))
        cpu_assignment = FakeAsr()
        cpu_assignment.graph_assignment_info["joint"] = {
            "providers": {CUDA_PROVIDER: 1, "CPUExecutionProvider": 1},
            "total_nodes": 2, "method": "get_provider_graph_assignment_info"}
        assignment_mutants.append(("CPU node assignment", cpu_assignment))
        unknown_assignment = FakeAsr()
        unknown_assignment.graph_assignment_info["joint"] = {
            "providers": {CUDA_PROVIDER: 1, "UnknownExecutionProvider": 1},
            "total_nodes": 2, "method": "get_provider_graph_assignment_info"}
        assignment_mutants.append(("unknown node assignment", unknown_assignment))
        overbound_assignment = FakeAsr()
        overbound_assignment.graph_assignment_info["joint"] = {
            "providers": {CUDA_PROVIDER: 1_000_001}, "total_nodes": 1_000_001,
            "method": "get_provider_graph_assignment_info"}
        assignment_mutants.append(("assignment count bound", overbound_assignment))
        incomplete_session = FakeAsr()
        incomplete_session.session_providers.pop("joint")
        assignment_mutants.append(("incomplete session set", incomplete_session))
        for _label, adverse in assignment_mutants:
            before = decoded["count"]
            try:
                _process_pending(samples[:1], {}, "f" * 64, adverse, fake_worker,
                                 route, cache_path, decode_audio=fake_decode)
            except Refusal:
                route_refusals += 1
            else:
                raise AssertionError("adverse node assignment reached audio decode")
            assert decoded["count"] == before
            decode_suppressed += 1

        thread_refusals = 0
        for ort_intra_op_tids, process_tids, approved in ((17, 20, 16), (2, 17, 16),
                                                          (None, 6, 16), (1, 5, None)):
            before = decoded["count"]
            try:
                counts = _require_thread_budget(ort_intra_op_tids, process_tids, approved)
                admitted_route = dict(route, **counts)
                _process_pending(samples[:1], {}, "f" * 64, FakeAsr(), fake_worker,
                                 admitted_route, cache_path, decode_audio=fake_decode)
            except Refusal:
                thread_refusals += 1
            else:
                raise AssertionError("unapproved TID count reached the decode boundary")
            assert decoded["count"] == before
            decode_suppressed += 1

        # Cache identity/digest and transcript output redaction are separate.
        bad_rows = dict(resumed)
        bad_rows["fleurs_000"] = dict(bad_rows["fleurs_000"], _text_sha256="0" * 64)
        try:
            _validate_row(bad_rows["fleurs_000"], samples[0], "f" * 64)
        except Refusal:
            pass
        else:
            raise AssertionError("text digest mutation was accepted")
        timing_type_mutations = []
        timing_type_mutations.append(dict(resumed["fleurs_000"], audio_s=True))
        timing_type_mutations.append(dict(resumed["fleurs_000"], inference_s="1.0"))
        bad_chunk_types = dict(resumed["fleurs_000"])
        bad_chunk_types["_chunk_stats"] = [dict(chunk)
                                             for chunk in bad_chunk_types["_chunk_stats"]]
        bad_chunk_types["_chunk_stats"][0]["line_event_s"] = True
        timing_type_mutations.append(bad_chunk_types)
        timing_type_mutations.append(dict(
            resumed["fleurs_000"], _first_nonempty_asr_chunk_finish_s="0.1"))
        timing_type_refusals = 0
        for bad_row in timing_type_mutations:
            try:
                _validate_row(bad_row, samples[0], "f" * 64)
            except Refusal:
                timing_type_refusals += 1
            else:
                raise AssertionError("non-numeric cached timing scalar was accepted")
        assert timing_type_refusals == len(timing_type_mutations)
        captured = io.StringIO()
        metrics = _metrics(rows, samples, cache_hit=False, startup={},
                           pool=plan["ort_pool_plan"])
        assert metrics["first_nonempty_asr_chunk_samples"] == 2
        assert metrics["first_nonempty_visible_line_event_samples"] == 2
        with contextlib.redirect_stdout(captured):
            print(_summary_line(metrics, cache_path, "f" * 64))
        assert "TRANSCRIPT_SENTINEL" not in captured.getvalue()
        assert "TRANSCRIPT_SENTINEL" not in repr(metrics)

    fake_plan = {"process_budget_requested": 1, "encoder_intra": 1,
                 "small_intra": 1, "ort_sessions": 3,
                 "ort_intra_aggregate": 3, "batch_intra": 1}
    planner = types.SimpleNamespace(
        resolve_threads=lambda count: (count, "flag"),
        asr_budget=lambda count: {"total": count, "live": count,
                                  "small": 1, "batch": count})
    assert _pool_plan(planner, 1) == fake_plan
    _require_pool_approval(fake_plan, 3)
    pool_approval_refusals = 0
    for approval in (None, 2):
        try:
            _require_pool_approval(fake_plan, approval)
        except Refusal:
            pool_approval_refusals += 1
        else:
            raise AssertionError("unapproved ORT aggregate was accepted")
    actual_plan = dict(fake_plan, ort_intra_aggregate=2)
    try:
        _check_pool_readback(actual_plan, fake_plan, 3)
    except Refusal:
        pass
    else:
        raise AssertionError("mismatched actual pool readback was accepted")
    _check_pool_readback(fake_plan, fake_plan, 3)

    # The worker-output sink keeps numeric facts and discards transcript text.
    sink = _SafeSink()
    sink.write("TRANSCRIPT_SENTINEL\n")
    sink.write("WORKER_THREAD_PLAN encoder=1 small=1 sessions=3 total_intra=3 budget_total=1 budget_batch=1\n")
    sink.write("WORKER_GENAI_THREADS threads=1 pinned=0 cpus=none\n")
    assert sink.pool_plan["ort_intra_aggregate"] == 3 and sink.ort_intra_op_tids == 1
    assert "TRANSCRIPT_SENTINEL" not in repr((sink.pool_plan, sink.ort_intra_op_tids))
    sys.modules.pop(fake_ort_native_module_key, None)
    sys.modules.pop(fake_genai_native_module_key, None)
    if sys.modules.pop("numpy", None) is not fake_numpy_module:
        raise AssertionError("synthetic NumPy route changed module identity")
    runtime_native_temp.cleanup()
    print("SELFTEST PASS planner=1/1 pool_preflight=1/1 pool_approval_refusal=%d/2 "
          "pool_readback=1/2 route_positive=1/1 route_refusal=%d/12 "
          "thread_budget_refusal=%d/4 decode_suppressed=%d/16 "
          "node_assignment_helper=1/1 node_assignment_refusal=%d/6 "
          "gpu_ort_package_choice=2/2 gpu_ort_package_refusal=%d/2 "
          "gpu_ort_import_path=1/1 gpu_ort_import_path_refusal=%d/3 "
          "gpu_provider_available=1/1 gpu_provider_refusal=%d/2 "
          "runtime_module_identity=1/1 runtime_module_refusal=%d/6 "
          "runtime_identity_binding=2/2 runtime_extension_refusal=%d/1 "
          "row_numeric_type_refusal=%d/4 "
          "runtime_package_cache_refusal=1/1 native_file_change_refusal=1/1 "
          "model_content_change_with_restored_mtime=1/1 runtime_env_normalization=1/1 "
          "runtime_env_refusal=%d/1 bounded_result_retention=1/1 retention_refusal=%d/1 "
          "source_identity=1/1 "
          "first_asr_chunk_metric=2/2 first_visible_line_event=2/2 "
          "first_visible_separate_from_asr_chunk=1/1 "
          "state_reset=1/1 session_reuse=1/1 resume=1/1 row_integrity=1/1 "
          "output_redaction=1/1 no_runtime_imports=1/1"
          % (pool_approval_refusals, route_refusals, thread_refusals,
             decode_suppressed, assignment_helper_refusals, runtime_package_refusals,
             gpu_module_path_refusals,
             cuda_provider_refusals,
             runtime_identity_refusals, runtime_extension_refusals,
             timing_type_refusals,
             env_refusal,
             retention_refusals))
    return 0


def _parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--manifest", default=str(MANIFEST_DEFAULT))
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument("--model-dir", default=str(MODEL_DEFAULT))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    parser.add_argument("--threads", type=int, default=1, choices=(1,))
    parser.add_argument("--approved-ort-pool-threads", type=int)
    parser.add_argument("--approved-process-tids", type=int)
    parser.add_argument("--no-resume", action="store_true")
    return parser


def main(argv=None):
    args = _parser().parse_args(argv)
    try:
        if args.selftest:
            return _selftest()
        if not args.expected_manifest_sha256:
            raise Refusal("--expected-manifest-sha256 is required")
        return _run_real(args)
    except Refusal as exc:
        print("REFUSED " + str(exc), file=sys.stderr)
        return 2
    except Exception:
        print("REFUSED unexpected failure; no transcript or exception text emitted", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
