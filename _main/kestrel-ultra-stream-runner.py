#!/usr/bin/env python3
"""Replay the pinned PT-BR cohort through Kestrel's stateful Ultra PCM stream.

The runner is deliberately offline: it requires an existing pinned HF snapshot,
sets HF_HUB_OFFLINE before importing Kestrel, and suppresses Kestrel Photon
telemetry through a no-op reporter. Captured PCM is paced by a separate producer
into a bounded queue; it is never paced by sleeping inside the yielded iterator.
Hypotheses stay in a private content-addressed H: cache. Public output is metrics
and hashes only.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import ctypes
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import logging
import math
import os
import queue
import re
import stat
import struct
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
PINNED_MODEL = "moondream/parakeet-ultra"
PINNED_MODEL_COMMIT = "73175eb7aeb0d82f1e2a6b53b3aabc10a90bcd0b"
PINNED_MANIFEST_SHA256 = "b74b61db926bee40ba21ab385264b0e8cbc89d4d10f93a4c51bcb54e95f3033c"
MANIFEST_DEFAULT = ROOT / ".agent-work/asr-cache/fleurs/pt_br" / (PINNED_MANIFEST_SHA256 + ".manifest.json")
CACHE_DEFAULT = ROOT / ".agent-work/asr-cache/kestrel-ultra-stream"
SCORER_PATH = ROOT / "_main/asr-reference-score.py"
EXPECTED_ROWS = 20
SAMPLE_RATE = 16_000
CHUNK_SECONDS = 0.560
CHUNK_FRAMES = 8_960
QUEUE_BLOCKS = 16
MAX_CHUNK_LATE_S = 0.100
SCHEMA = "sotto-kestrel-ultra-stateful-stream-v1"
MODEL_SCHEMA = "sotto-kestrel-ultra-content-v1"
IDENTITY_DIR = "model-identities"
RESULTS_DIR = "results"
LOCK_NAME = ".runner.lock"
MAX_MANIFEST_BYTES = 1 * 1024 * 1024
MAX_JSONL_BYTES = 1 * 1024 * 1024
MAX_REPORT_BYTES = 128 * 1024
MAX_IDENTITY_BYTES = 64 * 1024
MAX_CACHE_BYTES = 2 * 1024 * 1024
MAX_MODEL_BYTES = 2_000_000_000
MAX_AUDIO_BYTES = 32 * 1024 * 1024
MAX_UPDATE_EVENTS = 256
MAX_RESULT_GENERATIONS = 2
MAX_RESULT_CACHE_BYTES = 3 * 1024 * 1024
HASH_READ_BYTES_PER_SECOND = 4 * 1024 * 1024
THREAD_ENV = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
KESTREL_SOURCES = (
    "__init__.py",
    "config.py",
    "engine/__init__.py",
    "engine/_types.py",
    "engine/core.py",
    "engine/handle.py",
    "model_download.py",
    "models/registry.py",
    "models/asr/audio.py",
    "models/asr/contract.py",
    "models/asr/features.py",
    "models/asr/live.py",
    "models/asr/longform.py",
    "models/parakeet_tdt/contract.py",
    "models/parakeet_tdt/features.py",
    "models/parakeet_tdt/longform.py",
    "models/parakeet_tdt/metadata.py",
    "models/parakeet_tdt/registration.py",
    "models/parakeet_tdt/runtime.py",
    "models/parakeet_tdt/weights.py",
    "photon.py",
)
MODEL_FILES = ("config.json", "tokenizer.json", "model.safetensors")

# Establish numerical-library ceilings before Kestrel/Torch can be imported.
for _thread_env in THREAD_ENV:
    os.environ[_thread_env] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
sys.dont_write_bytecode = True


class Refusal(RuntimeError):
    """A safe, expected fail-closed refusal with no embedded user data."""


class CaptureOverflow(Refusal):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _hash_file(path: Path, *, paced: bool = False) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    started = time.perf_counter()
    with path.open("rb", buffering=0) as stream:
        while True:
            block = stream.read(256 * 1024)
            if not block:
                break
            size += len(block)
            digest.update(block)
            if paced:
                remaining = size / HASH_READ_BYTES_PER_SECOND - (time.perf_counter() - started)
                if remaining > 0:
                    time.sleep(remaining)
    return digest.hexdigest(), size


def _under(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((str(path.resolve()).casefold(),
                                   str(root.resolve()).casefold())) == str(root.resolve()).casefold()
    except (OSError, ValueError):
        return False


def _require_h_path(value: str | Path, label: str, *, must_exist: bool,
                    within_project: bool = True) -> Path:
    path = Path(value).expanduser()
    try:
        resolved = path.resolve(strict=must_exist)
    except OSError:
        raise Refusal(label + " is unavailable") from None
    if resolved.drive.upper() != "H:":
        raise Refusal(label + " must resolve on H:")
    if within_project and not _under(resolved, ROOT):
        raise Refusal(label + " must stay inside the Sotto project")
    if path.is_symlink() or resolved.is_symlink():
        raise Refusal(label + " cannot be a symlink")
    return resolved


def _reject_reparse(path: Path, label: str) -> None:
    try:
        info = path.lstat()
    except OSError:
        raise Refusal(label + " is unavailable") from None
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & reparse):
        raise Refusal(label + " cannot be a link or reparse point")


def _file_usn(path: Path) -> int | None:
    """Read NTFS's change token when available; never require it off NTFS."""
    if os.name != "nt":
        return None
    handle = None
    try:
        create_file = ctypes.windll.kernel32.CreateFileW
        create_file.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                ctypes.c_void_p]
        create_file.restype = ctypes.c_void_p
        handle = create_file(str(path), 0x80000080, 0x00000007, None, 3, 0x00000080, None)
        if not handle or handle == ctypes.c_void_p(-1).value:
            return None
        input_version = ctypes.create_string_buffer(struct.pack("<HH", 2, 2))
        output = ctypes.create_string_buffer(4096)
        returned = ctypes.c_uint32()
        ok = ctypes.windll.kernel32.DeviceIoControl(
            handle, 0x000900EB, input_version, len(input_version), output,
            len(output), ctypes.byref(returned), None)
        if not ok or returned.value < 32 or struct.unpack_from("<H", output.raw, 4)[0] != 2:
            return None
        return struct.unpack_from("<q", output.raw, 24)[0]
    except (AttributeError, OSError, TypeError, ValueError, struct.error):
        return None
    finally:
        if handle and handle != ctypes.c_void_p(-1).value:
            try:
                ctypes.windll.kernel32.CloseHandle(handle)
            except (AttributeError, OSError):
                pass


def _fingerprint(path: Path) -> dict[str, int | None]:
    info = path.stat()
    file_id = int(getattr(info, "st_ino", 0))
    if file_id <= 0:
        raise Refusal("filesystem does not expose stable model-file identity")
    return {"size": int(info.st_size), "mtime_ns": int(info.st_mtime_ns),
            "ctime_ns": int(info.st_ctime_ns), "device": int(info.st_dev),
            "file_id": file_id, "usn": _file_usn(path)}


def _atomic_write(path: Path, raw: bytes, *, limit: int) -> None:
    if len(raw) > limit:
        raise Refusal("private artifact exceeds its size budget")
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_reparse(path.parent, "private output directory")
    if path.exists() or path.is_symlink():
        _reject_reparse(path, "private output file")
    temp = path.with_name(path.name + ".tmp")
    if temp.exists() or temp.is_symlink():
        raise Refusal("stale private temporary file exists")
    try:
        with temp.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        os.replace(temp, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if temp.exists():
            temp.unlink()


@contextlib.contextmanager
def _cache_lease(cache_root: Path):
    path = cache_root / LOCK_NAME
    if path.is_symlink():
        raise Refusal("cache lock cannot be a symlink")
    try:
        with path.open("a+b") as stream:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (ImportError, OSError):
                raise Refusal("another runner owns the private cache") from None
            try:
                yield
            finally:
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    except Refusal:
        raise
    except OSError:
        raise Refusal("private cache lock is unavailable") from None


def _validate_manifest(path: Path, expected_sha256: str, *, hash_audio: bool) -> tuple[dict, list[dict], str]:
    path = _require_h_path(path, "manifest", must_exist=True)
    _reject_reparse(path, "manifest")
    if path.name != PINNED_MANIFEST_SHA256 + ".manifest.json":
        raise Refusal("manifest filename is not the pinned cohort")
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise Refusal("manifest exceeds its byte budget")
    raw = path.read_bytes()
    manifest_sha = _sha(raw)
    if expected_sha256 != PINNED_MANIFEST_SHA256 or manifest_sha != PINNED_MANIFEST_SHA256:
        raise Refusal("manifest hash does not match the pinned FLEURS cohort")
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Refusal("manifest JSON is invalid") from None
    records = manifest.get("records") if isinstance(manifest, dict) else None
    if not isinstance(records, list) or len(records) != EXPECTED_ROWS:
        raise Refusal("manifest does not contain the pinned 20 rows")
    rows = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise Refusal("manifest row schema is invalid")
        sample_id = record.get("id")
        audio_sha = record.get("audio_sha256")
        audio_bytes = record.get("audio_bytes")
        reference = record.get("reference")
        if (not isinstance(sample_id, str) or not sample_id or sample_id in seen
                or not isinstance(audio_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", audio_sha)
                or type(audio_bytes) is not int or audio_bytes <= 0
                or audio_bytes > MAX_AUDIO_BYTES or not isinstance(reference, str)):
            raise Refusal("manifest row identity is invalid")
        reference_sha = record.get("reference_sha256")
        if not isinstance(reference_sha, str) or _sha(reference.encode("utf-8")) != reference_sha:
            raise Refusal("manifest reference identity is invalid")
        audio_path = path.parent / (audio_sha + ".wav")
        if audio_path.parent.resolve() != path.parent.resolve() or audio_path.is_symlink():
            raise Refusal("manifest audio path escapes the pinned cache")
        _reject_reparse(audio_path, "manifest audio")
        info = audio_path.stat()
        if info.st_size != audio_bytes:
            raise Refusal("audio byte size disagrees with the manifest")
        if hash_audio:
            actual_sha, actual_size = _hash_file(audio_path)
            if actual_sha != audio_sha or actual_size != audio_bytes:
                raise Refusal("audio bytes disagree with the pinned manifest")
        rows.append({"id": sample_id, "audio_sha256": audio_sha,
                     "audio_bytes": audio_bytes, "audio_path": audio_path,
                     "audio_signature": _fingerprint(audio_path),
                     "reference": reference})
        seen.add(sample_id)
    sidecar_sha = manifest.get("transcript_sha256")
    if not isinstance(sidecar_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sidecar_sha):
        raise Refusal("manifest transcript-sidecar identity is invalid")
    sidecar = path.with_name(sidecar_sha + ".trans.txt")
    _reject_reparse(sidecar, "reference sidecar")
    actual_sidecar_sha, _ = _hash_file(sidecar)
    if actual_sidecar_sha != sidecar_sha:
        raise Refusal("reference sidecar hash does not match the manifest")
    return manifest, rows, manifest_sha


def _validate_model_dir(model_dir: str | Path, commit: str) -> tuple[Path, list[Path]]:
    if commit != PINNED_MODEL_COMMIT:
        raise Refusal("Ultra commit does not match the pinned local snapshot")
    path = Path(model_dir).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        raise Refusal("pinned Ultra snapshot is unavailable") from None
    if resolved.name != PINNED_MODEL_COMMIT or not resolved.is_dir() or path.is_symlink():
        raise Refusal("model directory is not the pinned snapshot")
    if resolved.drive.upper() in {"", "\\\\"} or str(resolved).startswith("\\\\"):
        raise Refusal("model snapshot must be a local filesystem directory")
    _reject_reparse(resolved, "model snapshot")
    files = []
    total = 0
    for name in MODEL_FILES:
        item = resolved / name
        if not item.is_file():
            raise Refusal("pinned Ultra snapshot is incomplete")
        target = item.resolve(strict=True)
        if str(target).startswith("\\\\"):
            raise Refusal("model artifact resolves to a network path")
        if not target.is_file():
            raise Refusal("model artifact target is not a regular file")
        total += item.stat().st_size
        if total > MAX_MODEL_BYTES:
            raise Refusal("pinned Ultra snapshot exceeds its byte budget")
        files.append(item)
    return resolved, files


def _model_identity(model_dir: Path, files: list[Path], cache_root: Path,
                    *, hash_file: Callable = _hash_file,
                    fingerprint: Callable = _fingerprint) -> dict:
    fingerprints = [{"name": path.name, "fingerprint": fingerprint(path)} for path in files]
    # A IDENTIDADE SO' SE REAPROVEITA COM PROVA DE QUE O BYTE NAO MUDOU (2026-11-23).
    # A revisao independente de 2026-11-21 levantou a pergunta certa -- "copiar so' o
    # SHA antigo nao protege contra mudanca do ficheiro" -- e a resposta que o codigo
    # ja' tinha e' o `usn` do NTFS (avanca em TODA a escrita) somado a
    # size+mtime+ctime+file_id; o que faltava era o caso em que o volume NAO devolve
    # `usn` (`_file_usn` devolve None): aí o fingerprint e' so' de metadados, e
    # reaproveitar o hash seria copiar um SHA sem prova. Sem `usn` em TODOS os
    # ficheiros, o receipt em cache e' ignorado e a identidade e' RE-MEDIDA.
    reuse_ok = all(row["fingerprint"].get("usn") for row in fingerprints)
    root_key = _sha(_canonical({"schema": MODEL_SCHEMA, "commit": PINNED_MODEL_COMMIT,
                                "path": str(model_dir.resolve()).casefold(),
                                "files": fingerprints}))
    identity_root = cache_root / IDENTITY_DIR
    identity_root.mkdir(parents=True, exist_ok=True)
    _reject_reparse(identity_root, "model identity cache")
    identity_path = identity_root / (PINNED_MODEL_COMMIT + ".json")
    cached = None
    if reuse_ok and identity_path.exists():
        _reject_reparse(identity_path, "model identity receipt")
        if identity_path.stat().st_size > MAX_IDENTITY_BYTES:
            raise Refusal("model identity receipt exceeds its size budget")
        try:
            cached = json.loads(identity_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise Refusal("model identity receipt is malformed") from None
        if not isinstance(cached, dict) or cached.get("schema") != MODEL_SCHEMA:
            raise Refusal("model identity receipt schema is invalid")
        if cached.get("root_key") != root_key:
            cached = None
        else:
            for item in fingerprints:
                digest = (cached.get("by_name") or {}).get(item["name"])
                if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise Refusal("model identity receipt lacks content hashes")
    started = time.perf_counter()
    bytes_hashed = 0
    if cached is None:
        by_name = {}
        for row, path in zip(fingerprints, files, strict=True):
            digest, size = hash_file(path, paced=True)
            if size != row["fingerprint"]["size"] or fingerprint(path) != row["fingerprint"]:
                raise Refusal("Ultra model artifact changed while hashing")
            by_name[path.name] = digest
            bytes_hashed += size
        cached = {"schema": MODEL_SCHEMA, "root_key": root_key, "by_name": by_name}
        _atomic_write(identity_path, _canonical(cached) + b"\n", limit=MAX_IDENTITY_BYTES)
    content_sha = _sha(_canonical({"schema": MODEL_SCHEMA, "commit": PINNED_MODEL_COMMIT,
                                   "files": [(row["name"], row["fingerprint"]["size"],
                                              cached["by_name"][row["name"]])
                                             for row in fingerprints]}))
    return {"commit": PINNED_MODEL_COMMIT, "sha256": content_sha,
            "bytes": sum(row["fingerprint"]["size"] for row in fingerprints),
            "files": len(files), "cache_hit": bytes_hashed == 0,
            "bytes_hashed": bytes_hashed, "identity_s": round(time.perf_counter() - started, 6),
            "identity_basis": "usn+metadata" if reuse_ok else "rehash",
            "signatures": fingerprints}


def _source_identity(*, kestrel_root: Path | None = None,
                     package_version: str | None = None) -> dict:
    runner_sha, runner_bytes = _hash_file(Path(__file__).resolve())
    scorer_sha, scorer_bytes = _hash_file(SCORER_PATH)
    rows = [{"path": Path(__file__).name, "sha256": runner_sha, "bytes": runner_bytes},
            {"path": SCORER_PATH.name, "sha256": scorer_sha, "bytes": scorer_bytes}]
    if kestrel_root is None:
        try:
            dist = importlib.metadata.distribution("kestrel")
            package_version = dist.version
            kestrel_root = Path(dist.locate_file("kestrel")).resolve(strict=True)
        except (importlib.metadata.PackageNotFoundError, OSError):
            raise Refusal("installed Kestrel package metadata is unavailable") from None
    if package_version != "0.9.1":
        raise Refusal("installed Kestrel version is not the reviewed 0.9.1 API")
    for relative in KESTREL_SOURCES:
        source = kestrel_root / relative
        if not source.is_file() or source.is_symlink():
            raise Refusal("installed Kestrel source identity is incomplete")
        digest, size = _hash_file(source)
        rows.append({"path": "kestrel/" + relative.replace("\\", "/"),
                     "sha256": digest, "bytes": size})
    runtime_versions = {}
    for distribution_name in ("torch", "numpy", "safetensors", "huggingface-hub"):
        try:
            runtime_versions[distribution_name] = importlib.metadata.version(distribution_name)
        except importlib.metadata.PackageNotFoundError:
            raise Refusal("a required Kestrel runtime distribution is unavailable") from None
    result = {"kestrel_version": package_version,
              "runtime_distributions": runtime_versions, "files": rows}
    result["sha256"] = _sha(_canonical(result))
    return result


def _verify_imported_kestrel(kestrel_root: Path, expected_source: dict) -> None:
    for name in ("kestrel", "kestrel.config", "kestrel.engine", "kestrel.engine.core",
                 "kestrel.engine.handle", "kestrel.models.parakeet_tdt.runtime",
                 "kestrel.models.parakeet_tdt.longform", "kestrel.models.parakeet_tdt.weights"):
        module = sys.modules.get(name)
        path = getattr(module, "__file__", None) if module is not None else None
        if not path or not _under(Path(path), kestrel_root):
            raise Refusal("loaded Kestrel module path differs from its installed package")
    for row in expected_source["files"]:
        if row["path"].startswith("kestrel/"):
            path = kestrel_root / row["path"][len("kestrel/"):]
            digest, size = _hash_file(path)
            if digest != row["sha256"] or size != row["bytes"]:
                raise Refusal("Kestrel source changed during initialization")


def _process_info(psutil_module: Any = None) -> dict:
    data = {"pid": os.getpid(), "python_threads": threading.active_count(),
            "process_tids": None, "rss_bytes": None}
    if psutil_module is None:
        try:
            import psutil as psutil_module
        except ImportError:
            return data
    try:
        process = psutil_module.Process(os.getpid())
        data["process_tids"] = int(process.num_threads())
        data["rss_bytes"] = int(process.memory_info().rss)
    except Exception:
        raise Refusal("process resource readback is unavailable") from None
    return data


def _gpu_readback(torch_module: Any, engine: Any) -> dict:
    try:
        if not bool(torch_module.cuda.is_available()):
            raise Refusal("CUDA is unavailable")
        current_index = int(torch_module.cuda.current_device())
        runtime = engine._runtimes[PINNED_MODEL]
        device = runtime.device
        if getattr(device, "type", None) != "cuda" or int(getattr(device, "index", current_index) or 0) != current_index:
            raise Refusal("Kestrel runtime did not read back the selected CUDA device")
        model = runtime.model
        tensor_devices = []
        for tensor in list(model.parameters()) + list(model.buffers()):
            tensor_devices.append((tensor.device.type, tensor.device.index))
        if not tensor_devices or any(kind != "cuda" or (index is not None and index != current_index)
                                      for kind, index in tensor_devices):
            raise Refusal("Ultra parameters or buffers are not wholly on CUDA")
        properties = torch_module.cuda.get_device_properties(current_index)
        free_bytes, total_bytes = torch_module.cuda.mem_get_info(current_index)
        return {"device": f"cuda:{current_index}", "name": str(properties.name),
                "total_bytes": int(total_bytes), "free_bytes": int(free_bytes),
                "allocated_bytes": int(torch_module.cuda.memory_allocated(current_index)),
                "reserved_bytes": int(torch_module.cuda.memory_reserved(current_index)),
                "parameter_tensors": len(tensor_devices)}
    except Refusal:
        raise
    except Exception:
        raise Refusal("CUDA or model-device readback failed") from None


class _NoopPhotonReporter:
    """Avoid Kestrel's external Photon telemetry; it does not affect inference."""
    def record_success(self, **_kwargs: Any) -> None:
        return None

    def record_error(self, **_kwargs: Any) -> None:
        return None

    async def shutdown(self) -> None:
        return None


class _DiscardOutput:
    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False


@contextlib.contextmanager
def _quiet_external_output():
    """Prevent third-party logs from copying hypothesis text to public streams."""
    previous_disable = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        with contextlib.redirect_stdout(_DiscardOutput()), contextlib.redirect_stderr(_DiscardOutput()):
            yield
    finally:
        logging.disable(previous_disable)


def _load_engine(api: Any = None) -> tuple[Any, Any, Any, Path, dict, float]:
    """Load exactly one Kestrel Ultra engine, with a verified CUDA readback."""
    started = time.perf_counter()
    if api is None:
        try:
            from kestrel.config import RuntimeConfig
            from kestrel.engine import InferenceEngine
            import torch
        except Exception:
            raise Refusal("Kestrel or Torch import failed") from None
        api = {"RuntimeConfig": RuntimeConfig, "InferenceEngine": InferenceEngine, "torch": torch}
    runtime_config_type = api["RuntimeConfig"]
    engine_type = api["InferenceEngine"]
    torch_module = api["torch"]
    if not bool(torch_module.cuda.is_available()):
        raise Refusal("CUDA is unavailable before model construction")
    config = runtime_config_type(model=PINNED_MODEL,
                                 model_path=api["model_dir"],
                                 device="cuda:0", dtype=torch_module.float16,
                                 max_batch_size=1, single_pass_batch_capacity=1,
                                 service_name="sotto-asr-bench")
    engine = engine_type(config)
    # Kestrel 0.9.1 has no telemetry disable knob. The sentinel only replaces
    # record/flush plumbing; model construction and the public capability path
    # are unchanged.
    engine._photon_reporter = _NoopPhotonReporter()
    return engine, torch_module, config, api.get("kestrel_root"), api.get("source_identity"), started


async def _start_engine(api: Any, model_dir: Path, source_identity: dict,
                        kestrel_root: Path) -> tuple[Any, Any, dict, float]:
    api = dict(api)
    api.update(model_dir=model_dir, source_identity=source_identity, kestrel_root=kestrel_root)
    engine, torch_module, _config, _root, _src, started = _load_engine(api)
    with _quiet_external_output():
        await engine._ensure_started()
    if api.get("verify_imports", True):
        _verify_imported_kestrel(kestrel_root, source_identity)
    gpu = _gpu_readback(torch_module, engine)
    ready_s = time.perf_counter() - started
    return engine, torch_module, gpu, ready_s


def _decode_pcm(path: Path, np_module: Any = None) -> tuple[Any, float]:
    if np_module is None:
        try:
            import numpy as np_module
        except ImportError:
            raise Refusal("NumPy import failed after CUDA admission") from None
    try:
        with wave.open(str(path), "rb") as stream:
            if (stream.getnchannels() != 1 or stream.getsampwidth() != 2
                    or stream.getframerate() != SAMPLE_RATE or stream.getcomptype() != "NONE"):
                raise Refusal("FLEURS WAV is not mono 16 kHz signed PCM16")
            frames = stream.getnframes()
            if frames <= 0 or frames > SAMPLE_RATE * 180:
                raise Refusal("FLEURS WAV duration is outside the runner bound")
            raw = stream.readframes(frames)
        samples = np_module.frombuffer(raw, dtype="<i2").astype(np_module.float32)
        samples *= 1.0 / 32768.0
        duration = len(samples) / SAMPLE_RATE
        if not math.isfinite(duration) or duration <= 0:
            raise Refusal("decoded FLEURS duration is invalid")
        return samples, duration
    except Refusal:
        raise
    except Exception:
        raise Refusal("pinned WAV decode failed") from None


class PacedPcmSource:
    """A live-like async iterator backed by a bounded independent producer."""
    def __init__(self, pcm: Any, *, clock: Callable[[], float] = time.perf_counter,
                 sleep: Callable[[float], Any] = asyncio.sleep,
                 queue_factory: Callable = lambda: queue.Queue(maxsize=QUEUE_BLOCKS),
                 chunk_frames: int = CHUNK_FRAMES, interval_s: float = CHUNK_SECONDS,
                 max_late_s: float = MAX_CHUNK_LATE_S, threaded: bool = True,
                 thread_wait: Callable[[float], bool] | None = None,
                 thread_factory: Callable = threading.Thread):
        self.pcm = pcm
        self.clock = clock
        self.sleep = sleep
        self.queue = queue_factory()
        self.chunk_frames = chunk_frames
        self.interval_s = interval_s
        self.max_late_s = max_late_s
        self.threaded = threaded
        self.thread_wait = thread_wait
        self.thread_factory = thread_factory
        self.chunk_count = (len(pcm) + chunk_frames - 1) // chunk_frames
        self.capture_start: float | None = None
        self.capture_frames = 0
        self.consumed_frames = 0
        self.queue_high_water = 0
        self.overflow_count = 0
        self.deadline_late_count = 0
        self.max_deadline_late_s = 0.0
        self.producer_error: BaseException | None = None
        self.producer_done: asyncio.Task | None = None
        self.producer_thread: threading.Thread | None = None
        self.stop_event = threading.Event()

    def _record_chunk(self, index: int, observed: float) -> None:
        start = index * self.chunk_frames
        end = min(len(self.pcm), start + self.chunk_frames)
        try:
            self.queue.put_nowait((self.pcm[start:end], end - start, observed))
        except (asyncio.QueueFull, queue.Full):
            self.overflow_count += 1
            raise CaptureOverflow("simulated capture queue overflowed") from None
        self.capture_frames += end - start
        self.queue_high_water = max(self.queue_high_water, self.queue.qsize())

    def _produce_thread(self) -> None:
        assert self.capture_start is not None
        try:
            for index in range(self.chunk_count):
                deadline = self.capture_start + (index + 1) * self.interval_s
                wait = self.thread_wait or self.stop_event.wait
                if wait(max(0.0, deadline - self.clock())):
                    return
                observed = self.clock()
                late = max(0.0, observed - deadline)
                self.max_deadline_late_s = max(self.max_deadline_late_s, late)
                if late > self.max_late_s:
                    self.deadline_late_count += 1
                    raise Refusal("simulated PCM producer missed its wall-clock deadline")
                self._record_chunk(index, observed)
        except BaseException as exc:
            self.producer_error = exc

    async def _produce_async(self) -> None:
        assert self.capture_start is not None
        try:
            for index in range(self.chunk_count):
                deadline = self.capture_start + (index + 1) * self.interval_s
                await self.sleep(max(0.0, deadline - self.clock()))
                observed = self.clock()
                late = max(0.0, observed - deadline)
                self.max_deadline_late_s = max(self.max_deadline_late_s, late)
                if late > self.max_late_s:
                    self.deadline_late_count += 1
                    raise Refusal("simulated PCM producer missed its wall-clock deadline")
                self._record_chunk(index, observed)
        except BaseException as exc:
            self.producer_error = exc
            if isinstance(exc, asyncio.CancelledError):
                raise

    async def __aiter__(self):
        if self.producer_done is not None or self.producer_thread is not None:
            raise Refusal("PCM source is single-use")
        self.capture_start = self.clock()
        if self.threaded:
            self.producer_thread = self.thread_factory(
                target=self._produce_thread, name="kestrel-ultra-pcm-capture", daemon=True)
            self.producer_thread.start()
        else:
            self.producer_done = asyncio.create_task(self._produce_async())
        try:
            for _ in range(self.chunk_count):
                item = None
                while item is None:
                    if self.producer_error is not None:
                        raise self._producer_refusal()
                    try:
                        item = self.queue.get_nowait()
                    except (asyncio.QueueEmpty, queue.Empty):
                        producer_finished = (
                            self.producer_done.done() if self.producer_done is not None
                            else (self.producer_thread is None or not self.producer_thread.is_alive()))
                        if producer_finished:
                            if self.producer_error is not None:
                                raise self._producer_refusal()
                            raise Refusal("PCM producer ended before delivering all chunks")
                        await asyncio.sleep(0.001)
                payload, frames, _captured_at = item
                if self.producer_error is not None:
                    raise self._producer_refusal()
                self.consumed_frames += frames
                yield payload
            if self.producer_done is not None:
                await self.producer_done
            while self.producer_thread is not None and self.producer_thread.is_alive():
                await asyncio.sleep(0.001)
            if self.producer_error is not None:
                raise self._producer_refusal()
        finally:
            if self.producer_done is not None and not self.producer_done.done():
                self.producer_done.cancel()
                await asyncio.gather(self.producer_done, return_exceptions=True)
            if self.producer_thread is not None and self.producer_thread.is_alive():
                self.stop_event.set()
                while self.producer_thread.is_alive():
                    await asyncio.sleep(0.001)

    def _producer_refusal(self) -> Refusal:
        if isinstance(self.producer_error, CaptureOverflow):
            return CaptureOverflow("simulated capture queue overflowed")
        if isinstance(self.producer_error, Refusal):
            return Refusal(str(self.producer_error))
        return Refusal("simulated PCM producer failed")

    def metrics(self) -> dict:
        return {"chunk_count": self.chunk_count,
                "captured_audio_s": round(self.capture_frames / SAMPLE_RATE, 6),
                "consumed_audio_s": round(self.consumed_frames / SAMPLE_RATE, 6),
                "queue_high_water": self.queue_high_water,
                "queue_capacity": QUEUE_BLOCKS,
                "capture_overflows": self.overflow_count,
                "deadline_late_chunks": self.deadline_late_count,
                "max_deadline_late_s": round(self.max_deadline_late_s, 6)}


def _quantiles(values: list[float]) -> dict:
    ordered = sorted(float(value) for value in values if math.isfinite(float(value)))
    if not ordered:
        return {"p50": None, "p95": None, "p99": None}
    def at(q: float) -> float:
        pos = (len(ordered) - 1) * q
        lo, hi = math.floor(pos), math.ceil(pos)
        return ordered[lo] if lo == hi else ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)
    return {key: round(at(q), 6) for key, q in (("p50", 0.50), ("p95", 0.95), ("p99", 0.99))}


async def _collect_stream(handle: Any, source: PacedPcmSource, *,
                          clock: Callable[[], float] = time.perf_counter) -> tuple[str, dict]:
    assert source.pcm is not None
    started = clock()
    try:
        with _quiet_external_output():
            stream = await handle.transcribe(audio=source, sample_rate=SAMPLE_RATE,
                                             stream=True, timestamps="segment")
    except Exception:
        raise Refusal("Kestrel transcribe(stream=True) failed to start") from None
    events: list[dict] = []
    previous_event_at: float | None = None
    first_update_s: float | None = None
    first_nonempty_s: float | None = None
    try:
        with _quiet_external_output():
            async for update in stream:
                if len(events) >= MAX_UPDATE_EVENTS:
                    raise Refusal("Kestrel emitted more than the bounded update limit")
                now = clock()
                output = getattr(update, "output", None)
                if not isinstance(output, dict):
                    raise Refusal("Kestrel emitted an invalid update shape")
                text = output.get("text", "")
                if not isinstance(text, str):
                    raise Refusal("Kestrel update text has an invalid type")
                if first_update_s is None:
                    first_update_s = now - started
                if text.strip() and first_nonempty_s is None:
                    first_nonempty_s = now - started
                completed = output.get("completed_seconds")
                total = output.get("total_seconds")
                event = {"at_s": now - started,
                         "text_nonempty": bool(text.strip()),
                         "text_sha256": _sha(text.encode("utf-8")),
                         "completed_seconds": float(completed) if isinstance(completed, (int, float)) else None,
                         "total_seconds": float(total) if isinstance(total, (int, float)) else None}
                if previous_event_at is not None:
                    event["gap_s"] = max(0.0, now - previous_event_at)
                events.append(event)
                previous_event_at = now
            result = await stream.result()
    except Refusal:
        close = getattr(stream, "aclose", None)
        if callable(close):
            await close()
        raise
    except Exception:
        close = getattr(stream, "aclose", None)
        if callable(close):
            try:
                await close()
            except Exception:
                pass
        raise Refusal("Kestrel streaming invocation failed") from None
    final_output = getattr(result, "output", None)
    if not isinstance(final_output, dict) or not isinstance(final_output.get("text"), str):
        raise Refusal("Kestrel final result shape is invalid")
    text = final_output["text"]
    finished = clock()
    update_times = [row["at_s"] for row in events]
    gaps = [row["gap_s"] for row in events if "gap_s" in row]
    capture_start = source.capture_start if source.capture_start is not None else started
    metrics = {
        "stream_wall_s": round(finished - started, 6),
        "first_update_s": round(first_update_s, 6) if first_update_s is not None else None,
        "first_nonempty_update_s": round(first_nonempty_s, 6) if first_nonempty_s is not None else None,
        "update_count": len(events),
        "update_gap_s": _quantiles(gaps),
        "updates": events,
        "capture_start_offset_s": round(capture_start - started, 6),
        **source.metrics(),
    }
    return text, metrics


def _run_key(manifest_sha: str, model_identity: dict, source_identity: dict,
             rows: list[dict]) -> str:
    value = {"schema": SCHEMA, "model": PINNED_MODEL,
             "model_commit": PINNED_MODEL_COMMIT,
             "model_sha256": model_identity["sha256"],
             "source_sha256": source_identity["sha256"],
             "manifest_sha256": manifest_sha,
             "audio": [(row["id"], row["audio_sha256"], row["audio_bytes"])
                       for row in rows],
             "stream": {"sample_rate": SAMPLE_RATE, "chunk_seconds": CHUNK_SECONDS,
                        "chunk_frames": CHUNK_FRAMES, "queue_blocks": QUEUE_BLOCKS,
                        "max_chunk_late_s": MAX_CHUNK_LATE_S,
                        "device": "cuda:0", "dtype": "float16",
             "decode_path": "auto", "cuda_graphs": True,
             "producer": "separate-thread-absolute-deadline-v1"}}
    return _sha(_canonical(value))


def _validate_result_row(row: Any, expected: dict, cache_key: str) -> None:
    if (not isinstance(row, dict) or row.get("schema") != SCHEMA
            or row.get("completed") is not True or row.get("cache_key") != cache_key
            or row.get("id") != expected["id"]
            or row.get("audio_sha256") != expected["audio_sha256"]
            or not isinstance(row.get("text"), str)
            or row.get("text_sha256") != _sha(row["text"].encode("utf-8"))):
        raise Refusal("cached hypothesis identity is invalid")
    metrics = row.get("stream_metrics")
    if not isinstance(metrics, dict):
        raise Refusal("cached streaming metrics are missing")
    for key in ("stream_wall_s", "captured_audio_s", "consumed_audio_s"):
        value = metrics.get(key)
        if type(value) not in (int, float) or not math.isfinite(float(value)) or value < 0:
            raise Refusal("cached timing metric is invalid")


def _read_resume(path: Path, expected_rows: list[dict], cache_key: str) -> dict[str, dict]:
    if not path.exists():
        return {}
    _reject_reparse(path, "private hypothesis cache")
    if path.stat().st_size > MAX_JSONL_BYTES:
        raise Refusal("private hypotheses exceed their size budget")
    raw = path.read_bytes()
    expected = {row["id"]: row for row in expected_rows}
    found: dict[str, dict] = {}
    valid_end = 0
    pieces = raw.splitlines(keepends=True)
    for index, piece in enumerate(pieces):
        complete_line = piece.endswith(b"\n")
        if not complete_line and index == len(pieces) - 1:
            break  # crash-torn last append; preserve every prior complete row
        if not complete_line:
            raise Refusal("private hypotheses contain a malformed line")
        try:
            row = json.loads(piece.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise Refusal("private hypothesis row is invalid") from None
        sample_id = row.get("id") if isinstance(row, dict) else None
        if sample_id not in expected or sample_id in found:
            raise Refusal("private hypothesis sample set is invalid")
        _validate_result_row(row, expected[sample_id], cache_key)
        found[sample_id] = row
        valid_end += len(piece)
    if valid_end != len(raw):
        _atomic_write(path, raw[:valid_end], limit=MAX_JSONL_BYTES)
    return found


def _append_row(path: Path, row: dict) -> None:
    raw = _canonical(row) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    _reject_reparse(path.parent, "private cache directory")
    if path.exists():
        _reject_reparse(path, "private hypotheses")
        if path.stat().st_size + len(raw) > MAX_JSONL_BYTES:
            raise Refusal("private hypotheses exceed their size budget")
    try:
        with path.open("ab") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        raise Refusal("private hypothesis write failed") from None


def _cache_inventory(results_root: Path) -> list[dict]:
    if not results_root.exists():
        results_root.mkdir(parents=True, exist_ok=True)
        return []
    _reject_reparse(results_root, "result cache root")
    rows = []
    for index, directory in enumerate(results_root.iterdir()):
        if index >= MAX_RESULT_GENERATIONS + 1:
            raise Refusal("result cache inventory exceeds its bound")
        if not re.fullmatch(r"[0-9a-f]{64}", directory.name) or directory.is_symlink() or not directory.is_dir():
            raise Refusal("result cache contains an unexpected entry")
        _reject_reparse(directory, "result cache generation")
        files = []
        for item in directory.iterdir():
            if len(files) >= 5:
                raise Refusal("result cache generation exceeds its file bound")
            _reject_reparse(item, "result cache artifact")
            if item.name not in {"hypotheses.jsonl", "ready.json", "report.json",
                                 "hypotheses.jsonl.tmp", "ready.json.tmp", "report.json.tmp"} or not item.is_file():
                raise Refusal("result cache contains an unexpected artifact")
            files.append(item)
        rows.append({"key": directory.name, "path": directory, "files": files})
    return rows


def _maintain_cache(results_root: Path, current: str) -> dict:
    inventory = _cache_inventory(results_root)
    complete = []
    for row in inventory:
        by_name = {path.name: path for path in row["files"]}
        for temporary in ("hypotheses.jsonl.tmp", "ready.json.tmp", "report.json.tmp"):
            if temporary in by_name:
                by_name[temporary].unlink()
        report_path = by_name.get("report.json")
        row["completed"] = False
        row["mtime_ns"] = row["path"].stat().st_mtime_ns
        if report_path:
            if report_path.stat().st_size > MAX_REPORT_BYTES:
                raise Refusal("cached report exceeds its size budget")
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                raise Refusal("cached report is invalid") from None
            if not isinstance(report, dict) or report.get("schema") != SCHEMA or report.get("cache_key") != row["key"]:
                raise Refusal("cached report identity is invalid")
            row["completed"] = True
            row["mtime_ns"] = report_path.stat().st_mtime_ns
        if row["key"] != current and row["completed"]:
            complete.append(row)
    complete.sort(key=lambda item: (item["mtime_ns"], item["key"]), reverse=True)
    keep = {current}
    keep.update(item["key"] for item in complete[:MAX_RESULT_GENERATIONS - 1])
    for row in inventory:
        if row["key"] in keep:
            continue
        for item in row["files"]:
            item.unlink()
        row["path"].rmdir()
    kept = _cache_inventory(results_root)
    total = 0
    for row in kept:
        if len(row["files"]) > 3:
            raise Refusal("result cache generation has too many artifacts")
        for item in row["files"]:
            if item.name.endswith(".tmp"):
                raise Refusal("stale cache temporary remains")
            limit = MAX_JSONL_BYTES if item.name == "hypotheses.jsonl" else MAX_REPORT_BYTES
            size = item.stat().st_size
            if size > limit:
                raise Refusal("result cache artifact exceeds its size budget")
            total += size
    if total > MAX_RESULT_CACHE_BYTES or sum(1 for _ in kept) > MAX_RESULT_GENERATIONS:
        raise Refusal("result cache exceeds its aggregate bound")
    return {"generations": len(kept), "bytes": total}


def _score(hypotheses_path: Path, manifest_path: Path) -> dict:
    try:
        spec = importlib.util.spec_from_file_location("_sotto_asr_reference_score", SCORER_PATH)
        if spec is None or spec.loader is None:
            raise Refusal("reference scorer cannot be loaded")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.score(manifest_path, hypotheses_path, PINNED_MODEL,
                            PINNED_MANIFEST_SHA256)
    except Refusal:
        raise
    except Exception:
        raise Refusal("reference scorer rejected the private hypotheses") from None


def _aggregate_rows(rows: list[dict], model_ready_s: float, gpu: dict,
                    process_info: dict, scorer: dict, cache_key: str,
                    *, cache_hit: bool) -> dict:
    metrics = [row["stream_metrics"] for row in rows]
    first = [m["first_update_s"] for m in metrics if m.get("first_update_s") is not None]
    first_text = [m["first_nonempty_update_s"] for m in metrics if m.get("first_nonempty_update_s") is not None]
    walls = [m["stream_wall_s"] for m in metrics]
    captured = sum(float(m["captured_audio_s"]) for m in metrics)
    consumed = sum(float(m["consumed_audio_s"]) for m in metrics)
    all_gaps = [float(event["gap_s"]) for m in metrics for event in m["updates"] if "gap_s" in event]
    return {"schema": SCHEMA, "cache_key": cache_key, "model": PINNED_MODEL,
            "model_commit": PINNED_MODEL_COMMIT,
            "manifest_sha256": PINNED_MANIFEST_SHA256, "samples": len(rows),
            "coverage": "complete", "cache_hit": cache_hit,
            "model_ready_s": round(float(model_ready_s), 6),
            "first_emitted_update_s": _quantiles(first),
            "first_nonempty_update_s": _quantiles(first_text),
            "stream_wall_s": _quantiles(walls), "update_gap_s": _quantiles(all_gaps),
            "captured_audio_s": round(captured, 6), "consumed_audio_s": round(consumed, 6),
            "capture_queue_high_water": max((int(m["queue_high_water"]) for m in metrics), default=0),
            "capture_queue_capacity": QUEUE_BLOCKS,
            "capture_overflows": sum(int(m["capture_overflows"]) for m in metrics),
            "deadline_late_chunks": sum(int(m["deadline_late_chunks"]) for m in metrics),
            "gpu": gpu, "process": process_info,
            "wer": scorer.get("wer"), "cer_no_whitespace": scorer.get("cer_no_whitespace"),
            "word_edits": scorer.get("word_edits"), "reference_words": scorer.get("reference_words"),
            "hypotheses_sha256": scorer.get("hypotheses_sha256"),
            "scorer_cache_key": scorer.get("cache_key")}


def _public_report(report: dict) -> dict:
    def number(value: Any) -> int | float | None:
        if type(value) not in (int, float) or not math.isfinite(float(value)) or value < 0:
            return None
        return value

    def summary(value: Any) -> dict | None:
        if not isinstance(value, dict):
            return None
        clean = {key: number(value.get(key)) for key in ("p50", "p95", "p99")}
        return clean if all(value.get(key) is None or clean[key] is not None
                            for key in ("p50", "p95", "p99")) else None

    if not isinstance(report, dict):
        raise Refusal("public report shape is invalid")
    cache_key = report.get("cache_key")
    if not isinstance(cache_key, str) or not re.fullmatch(r"[0-9a-f]{64}", cache_key):
        raise Refusal("public report identity is invalid")
    public = {"schema": SCHEMA, "cache_key": cache_key, "model": PINNED_MODEL,
              "model_commit": PINNED_MODEL_COMMIT,
              "manifest_sha256": PINNED_MANIFEST_SHA256}
    samples = report.get("samples")
    if type(samples) is int and 0 <= samples <= EXPECTED_ROWS:
        public["samples"] = samples
    if report.get("coverage") == "complete":
        public["coverage"] = "complete"
    if type(report.get("cache_hit")) is bool:
        public["cache_hit"] = report["cache_hit"]
    for key in ("model_ready_s", "captured_audio_s", "consumed_audio_s", "wer",
                "cer_no_whitespace"):
        clean = number(report.get(key))
        if clean is not None:
            public[key] = clean
    for key in ("first_emitted_update_s", "first_nonempty_update_s",
                "stream_wall_s", "update_gap_s"):
        clean = summary(report.get(key))
        if clean is not None:
            public[key] = clean
    for key in ("capture_queue_high_water", "capture_queue_capacity", "capture_overflows",
                "deadline_late_chunks", "word_edits", "reference_words"):
        value = report.get(key)
        if type(value) is int and 0 <= value <= 10_000_000:
            public[key] = value
    for key in ("hypotheses_sha256", "scorer_cache_key"):
        value = report.get(key)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value):
            public[key] = value
    gpu = report.get("gpu")
    if isinstance(gpu, dict):
        device = gpu.get("device")
        gpu_public = {"device": device} if isinstance(device, str) and re.fullmatch(r"cuda:\d+", device) else {}
        for key in ("total_bytes", "free_bytes", "allocated_bytes", "reserved_bytes", "parameter_tensors"):
            value = gpu.get(key)
            if type(value) is int and 0 <= value <= 10**15:
                gpu_public[key] = value
        if gpu_public:
            public["gpu"] = gpu_public
    process = report.get("process")
    if isinstance(process, dict):
        process_public = {}
        for key in ("pid", "python_threads", "process_tids", "rss_bytes"):
            value = process.get(key)
            if value is None and key in {"process_tids", "rss_bytes"}:
                process_public[key] = None
            elif type(value) is int and 0 <= value <= 10**15:
                process_public[key] = value
        if process_public:
            public["process"] = process_public
    return public


async def _run_rows(handle: Any, rows: list[dict], found: dict[str, dict],
                    hypotheses_path: Path, model_ready_s: float,
                    process_info: dict, gpu: dict, cache_key: str,
                    *, decode_audio: Callable = _decode_pcm,
                    clock: Callable[[], float] = time.perf_counter,
                    source_factory: Callable = PacedPcmSource) -> dict:
    completed = dict(found)
    for expected in rows:
        if expected["id"] in completed:
            continue
        pcm, audio_s = decode_audio(expected["audio_path"])
        source = source_factory(pcm, clock=clock)
        text, stream_metrics = await _collect_stream(handle, source, clock=clock)
        if (source.capture_frames != len(pcm) or source.consumed_frames != len(pcm)
                or source.overflow_count or source.deadline_late_count
                or source.queue_high_water > QUEUE_BLOCKS):
            raise Refusal("paced capture did not deliver the complete WAV")
        after = _fingerprint(expected["audio_path"])
        if after != expected["audio_signature"]:
            raise Refusal("pinned WAV changed during streaming inference")
        stream_metrics["audio_s"] = round(audio_s, 6)
        stream_metrics["rtf_paced_wall"] = round(stream_metrics["stream_wall_s"] / audio_s, 6)
        row = {"schema": SCHEMA, "completed": True, "cache_key": cache_key,
               "id": expected["id"], "audio_sha256": expected["audio_sha256"],
               "text": text, "text_sha256": _sha(text.encode("utf-8")),
               "stream_metrics": stream_metrics}
        _validate_result_row(row, expected, cache_key)
        _append_row(hypotheses_path, row)
        completed[expected["id"]] = row
    return {"schema": SCHEMA, "cache_key": cache_key, "rows": [completed[row["id"]] for row in rows],
            "model_ready_s": model_ready_s, "process": process_info, "gpu": gpu}


async def _execute_engine_rows(deps: dict, model_dir: Path, source_identity: dict,
                               rows: list[dict], found: dict[str, dict],
                               hypotheses_path: Path, cache_key: str) -> dict:
    engine, _torch_module, gpu, model_ready_s = await _start_engine(
        deps["api"], model_dir, source_identity, deps["kestrel_root"])
    try:
        handle = engine.model(PINNED_MODEL)
        process_info = _process_info(deps.get("psutil"))
        _atomic_write(hypotheses_path.parent / "ready.json",
                      _canonical({"cache_key": cache_key, "model_ready_s": model_ready_s,
                                  "gpu": gpu}) + b"\n",
                      limit=MAX_REPORT_BYTES)
        return await _run_rows(handle, rows, found, hypotheses_path,
                               model_ready_s, process_info, gpu, cache_key,
                               decode_audio=deps.get("decode_audio", _decode_pcm),
                               clock=deps.get("clock", time.perf_counter),
                               source_factory=deps.get("source_factory", PacedPcmSource))
    finally:
        try:
            with _quiet_external_output():
                await engine.shutdown()
        except Exception:
            pass


def _engine_report_inputs(result: dict) -> tuple[list, float, dict, dict]:
    """O que o ramo de CACHE FRIO agrega, lido do resultado do motor.

    Existia aqui um `UnboundLocalError` (encontrado pela revisao independente em
    2026-11-21, no dia em que esta lane parou): `model_ready_s`, `gpu` e
    `process_info` eram atribuidos SO' no ramo de retomada, e o ramo de cache frio
    agregava com esses nomes -- ou seja o caminho que ainda nao tinha nada em
    cache morria antes de escrever o relatorio que ele existe para produzir. Um
    nome que so' um ramo atribui nao e' um valor: a leitura passa a ser DESTE
    ponto, que recusa uma resultado incompleto em vez de estourar.
    """
    if not isinstance(result, dict):
        raise Refusal("engine result is not an object")
    rows = result.get("rows")
    model_ready_s = result.get("model_ready_s")
    gpu = result.get("gpu")
    process_info = result.get("process")
    if not isinstance(rows, list) or not rows:
        raise Refusal("engine result carries no rows")
    if type(model_ready_s) not in (float, int) or not math.isfinite(float(model_ready_s)) or model_ready_s < 0:
        raise Refusal("engine result carries no model-ready receipt")
    if not isinstance(gpu, dict) or gpu.get("device") != "cuda:0":
        raise Refusal("engine result does not name the CUDA device")
    if not isinstance(process_info, dict):
        raise Refusal("engine result carries no process receipt")
    return rows, float(model_ready_s), gpu, process_info


def run(args: argparse.Namespace, *, dependencies: dict | None = None) -> dict:
    manifest_path = _require_h_path(args.manifest, "manifest", must_exist=True)
    cache_root = _require_h_path(args.cache_root, "cache root", must_exist=False)
    cache_root.mkdir(parents=True, exist_ok=True)
    _reject_reparse(cache_root, "cache root")
    model_dir, model_files = _validate_model_dir(args.model_dir, args.model_commit)
    manifest, rows, manifest_sha = _validate_manifest(
        manifest_path, args.expected_manifest_sha256, hash_audio=True)
    source_identity = _source_identity()
    model_identity = _model_identity(model_dir, model_files, cache_root)
    cache_key = _run_key(manifest_sha, model_identity, source_identity, rows)
    results_root = cache_root / RESULTS_DIR
    result_dir = results_root / cache_key
    result_dir.mkdir(parents=True, exist_ok=True)
    _reject_reparse(result_dir, "result cache directory")
    hypotheses_path = result_dir / "hypotheses.jsonl"
    report_path = result_dir / "report.json"
    with _cache_lease(cache_root):
        _maintain_cache(results_root, cache_key)
        if report_path.exists():
            _reject_reparse(report_path, "cached report")
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                raise Refusal("cached report is invalid") from None
            if (not isinstance(report, dict) or report.get("schema") != SCHEMA
                    or report.get("cache_key") != cache_key or report.get("coverage") != "complete"):
                raise Refusal("cached report does not match the current run identity")
            print(json.dumps(_public_report(report), sort_keys=True, ensure_ascii=False))
            return report
        found = _read_resume(hypotheses_path, rows, cache_key)
        if len(found) == len(rows):
            ready_path = result_dir / "ready.json"
            if not ready_path.is_file():
                raise Refusal("completed hypotheses lack their model-ready receipt")
            process_info = _process_info((dependencies or {}).get("psutil"))
            try:
                ready = json.loads(ready_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                raise Refusal("cached model-ready receipt is invalid") from None
            if not isinstance(ready, dict):
                raise Refusal("cached model-ready receipt is invalid")
            model_ready_s = ready.get("model_ready_s")
            gpu = ready.get("gpu")
            if (ready.get("cache_key") != cache_key
                    or type(model_ready_s) not in (float, int)
                    or not math.isfinite(float(model_ready_s)) or model_ready_s < 0
                    or not isinstance(gpu, dict) or gpu.get("device") != "cuda:0"):
                raise Refusal("cached model-ready receipt identity is invalid")
            all_rows = [found[row["id"]] for row in rows]
            scorer_result = _score(hypotheses_path, manifest_path)
            report = _aggregate_rows(all_rows, model_ready_s, gpu, process_info,
                                     scorer_result, cache_key, cache_hit=True)
            _atomic_write(report_path, _canonical(report) + b"\n", limit=MAX_REPORT_BYTES)
            _maintain_cache(results_root, cache_key)
            print(json.dumps(_public_report(report), sort_keys=True, ensure_ascii=False))
            return report

        deps = dependencies
        if deps is None:
            deps = _prepare_runtime(model_dir, source_identity)
        result = asyncio.run(_execute_engine_rows(deps, model_dir, source_identity,
                                                  rows, found, hypotheses_path, cache_key))
        all_rows, model_ready_s, gpu, process_info = _engine_report_inputs(result)
        scorer_result = _score(hypotheses_path, manifest_path)
        report = _aggregate_rows(all_rows, model_ready_s, gpu, process_info,
                                 scorer_result, cache_key, cache_hit=False)
        _atomic_write(report_path, _canonical(report) + b"\n", limit=MAX_REPORT_BYTES)
        _maintain_cache(results_root, cache_key)
        print(json.dumps(_public_report(report), sort_keys=True, ensure_ascii=False))
        return report


def _prepare_runtime(model_dir: Path, source_identity: dict) -> dict:
    """Import CUDA/Kestrel only after all pins, local paths, and WAV hashes pass."""
    try:
        dist = importlib.metadata.distribution("kestrel")
        root = Path(dist.locate_file("kestrel")).resolve(strict=True)
        version = dist.version
    except (importlib.metadata.PackageNotFoundError, OSError):
        raise Refusal("Kestrel package metadata is unavailable") from None
    if version != "0.9.1":
        raise Refusal("installed Kestrel version differs from the reviewed route")
    expected = _source_identity(kestrel_root=root, package_version=version)
    if expected["sha256"] != source_identity["sha256"]:
        raise Refusal("Kestrel source identity changed before import")
    before = _process_info()
    if before["process_tids"] is None:
        raise Refusal("OS process-thread census is unavailable")
    try:
        import torch
    except Exception:
        raise Refusal("Torch import failed") from None
    if not bool(torch.cuda.is_available()):
        raise Refusal("CUDA is unavailable before Kestrel import")
    try:
        from huggingface_hub import constants as hf_constants
    except Exception:
        raise Refusal("Hugging Face offline controls are unavailable") from None
    if not bool(getattr(hf_constants, "HF_HUB_OFFLINE", False)):
        raise Refusal("Hugging Face library did not retain offline mode")
    try:
        import kestrel
        from kestrel.config import RuntimeConfig
        from kestrel.engine import InferenceEngine
    except Exception:
        raise Refusal("Kestrel import failed") from None
    if not _under(Path(kestrel.__file__), root):
        raise Refusal("imported Kestrel package path does not match its distribution")
    try:
        import kestrel.model_download as model_download
    except Exception:
        raise Refusal("Kestrel offline loader module is unavailable") from None
    if os.environ.get("HF_HUB_OFFLINE") != "1":
        raise Refusal("Hugging Face offline mode was not retained")
    if os.environ.get("HF_HUB_DISABLE_TELEMETRY") != "1":
        raise Refusal("Hugging Face telemetry disable was not retained")
    return {"api": {"RuntimeConfig": RuntimeConfig, "InferenceEngine": InferenceEngine,
                     "torch": torch, "model_dir": model_dir},
            "kestrel_root": root, "source_identity": expected,
            "model_download": model_download}


def _selftest() -> None:
    # This branch is model-free: only stdlib, small synthetic WAV fixtures, and
    # injected fake Kestrel/GPU/clock objects are used. It must not import Kestrel.
    manifest, _rows, actual = _validate_manifest(MANIFEST_DEFAULT,
                                                PINNED_MANIFEST_SHA256,
                                                hash_audio=False)
    assert actual == PINNED_MANIFEST_SHA256 and len(manifest["records"]) == EXPECTED_ROWS
    try:
        _validate_manifest(MANIFEST_DEFAULT, "0" * 64, hash_audio=False)
    except Refusal:
        pass
    else:
        raise AssertionError("wrong pinned manifest hash was accepted")

    with tempfile.TemporaryDirectory(prefix="kestrel-ultra-stream-selftest-",
                                     dir=Path(__file__).resolve().parent) as temp_name:
        temp = Path(temp_name)
        fake_model = temp / PINNED_MODEL_COMMIT
        fake_model.mkdir()
        for name, content in (("config.json", b"{}"), ("tokenizer.json", b"{}"),
                              ("model.safetensors", b"fake-weights")):
            (fake_model / name).write_bytes(content)
        resolved, files = _validate_model_dir(fake_model, PINNED_MODEL_COMMIT)
        assert resolved == fake_model.resolve() and len(files) == 3
        for bad_commit in ("0" * 40, PINNED_MODEL_COMMIT + "x"):
            try:
                _validate_model_dir(fake_model, bad_commit)
            except Refusal:
                pass
            else:
                raise AssertionError("wrong model commit was accepted")
        incomplete = temp / ("0" * 40)
        incomplete.mkdir()
        try:
            _validate_model_dir(incomplete, PINNED_MODEL_COMMIT)
        except Refusal:
            pass
        else:
            raise AssertionError("missing local snapshot was accepted")

        class FakeDevice:
            type = "cuda"
            index = 0

        class FakeTensor:
            device = FakeDevice()

        class FakeModel:
            def parameters(self):
                return [FakeTensor()]
            def buffers(self):
                return [FakeTensor()]

        class FakeRuntime:
            device = FakeDevice()
            model = FakeModel()

        class FakeCuda:
            @staticmethod
            def is_available(): return True
            @staticmethod
            def current_device(): return 0
            @staticmethod
            def get_device_properties(_index):
                return type("Props", (), {"name": "fake-gpu"})()
            @staticmethod
            def mem_get_info(_index): return 1000, 2000
            @staticmethod
            def memory_allocated(_index): return 100
            @staticmethod
            def memory_reserved(_index): return 200

        class FakeTorch:
            cuda = FakeCuda()
            float16 = object()

        class FakeEngine:
            def __init__(self, _config):
                self._runtimes = {PINNED_MODEL: FakeRuntime()}

        good_route = _gpu_readback(FakeTorch(), FakeEngine(None))
        assert good_route["device"] == "cuda:0" and good_route["parameter_tensors"] == 2

        class CpuRuntime(FakeRuntime):
            class device:
                type = "cpu"
                index = None

        class CpuEngine:
            _runtimes = {PINNED_MODEL: CpuRuntime()}

        try:
            _gpu_readback(FakeTorch(), CpuEngine())
        except Refusal:
            pass
        else:
            raise AssertionError("CPU runtime was accepted")
        no_cuda = type("NoCuda", (), {"cuda": type("Cuda", (), {
            "is_available": staticmethod(lambda: False)})()})
        try:
            _gpu_readback(no_cuda, FakeEngine(None))
        except Refusal:
            pass
        else:
            raise AssertionError("CUDA-unavailable route was accepted")

        config_calls = []
        class FakeConfig:
            def __init__(self, **kwargs):
                config_calls.append(kwargs)
                self.kwargs = kwargs

        class FakeConstructEngine(FakeEngine):
            def __init__(self, config):
                super().__init__(config)
                self.config = config

        fake_api = {"RuntimeConfig": FakeConfig, "InferenceEngine": FakeConstructEngine,
                    "torch": FakeTorch, "model_dir": fake_model,
                    "source_identity": {"sha256": "0" * 64},
                    "kestrel_root": temp}
        constructed, _torch, config, _root, _source, _started = _load_engine(fake_api)
        assert config_calls and config_calls[0]["model_path"] == fake_model
        assert config_calls[0]["device"] == "cuda:0"
        assert isinstance(constructed._photon_reporter, _NoopPhotonReporter)
        assert os.environ.get("HF_HUB_OFFLINE") == "1"

        class FakeClock:
            def __init__(self): self.now = 10.0
            def __call__(self): return self.now
            async def sleep(self, seconds):
                self.now += seconds
                await asyncio.sleep(0)
            def advance(self, seconds): self.now += seconds

        fake_pcm = memoryview(bytearray(3 * CHUNK_FRAMES * 2)).cast("h")

        class InlineFakeThread:
            def __init__(self, *, target, **_kwargs):
                self.target = target
                self.running = False
            def start(self):
                self.running = True
                try:
                    self.target()
                finally:
                    self.running = False
            def is_alive(self): return self.running

        # Exercise the real threaded-producer wiring and absolute-deadline
        # logic without creating an OS thread or waiting in real time.
        producer_clock = FakeClock()
        thread_source = PacedPcmSource(
            fake_pcm, clock=producer_clock,
            thread_wait=lambda seconds: (producer_clock.advance(seconds), False)[1],
            thread_factory=InlineFakeThread)
        async def drain_thread_source():
            return [chunk async for chunk in thread_source]
        captured = asyncio.run(drain_thread_source())
        assert len(captured) == 3
        assert thread_source.capture_frames == thread_source.consumed_frames == 3 * CHUNK_FRAMES
        assert abs(producer_clock() - (10.0 + 3 * CHUNK_SECONDS)) < 1e-9

        clock = FakeClock()
        source = PacedPcmSource(fake_pcm, clock=clock,
                                sleep=clock.sleep,
                                threaded=False)
        async def drain_source():
            chunks = []
            async for chunk in source:
                chunks.append(chunk)
            return chunks
        chunks = asyncio.run(drain_source())
        assert len(chunks) == 3
        assert source.capture_frames == source.consumed_frames == 3 * CHUNK_FRAMES
        assert source.queue_high_water <= 3 and source.overflow_count == 0

        full_queue = asyncio.Queue(maxsize=2)
        overflow_clock = FakeClock()
        overflow_source = PacedPcmSource(fake_pcm, clock=overflow_clock,
                                         queue_factory=lambda: full_queue,
                                         thread_wait=lambda seconds: (overflow_clock.advance(seconds), False)[1],
                                         thread_factory=InlineFakeThread)
        # The inline fake producer fills before the consumer resumes; overflow
        # must remain a hard refusal on the real async-iterator path.
        async def drain_overflow_source():
            return [chunk async for chunk in overflow_source]
        try:
            asyncio.run(drain_overflow_source())
        except Refusal:
            pass
        else:
            raise AssertionError("threaded producer queue overflow was accepted")
        assert overflow_source.overflow_count == 1

        class FakeUpdate:
            def __init__(self, text): self.output = {"text": text, "completed_seconds": 2.0,
                                                       "total_seconds": 4.0}

        class FakeResult:
            output = {"text": "TRANSCRIPT_SENTINEL exact final words"}

        class FakeStream:
            def __init__(self, _source, fake_clock):
                self.source = _source
                self.clock = fake_clock
                self._result = FakeResult()
            def __aiter__(self): return self._events()
            async def _events(self):
                async for _chunk in self.source:
                    if self.source.consumed_frames in (2 * CHUNK_FRAMES, 3 * CHUNK_FRAMES):
                        self.clock.now += 0.04
                        yield FakeUpdate("TRANSCRIPT_SENTINEL partial")
            async def result(self): return self._result
            async def aclose(self): return None

        class FakeHandle:
            def __init__(self, fake_clock): self.clock = fake_clock
            async def transcribe(self, **prompt):
                assert prompt["sample_rate"] == SAMPLE_RATE and prompt["stream"] is True
                return FakeStream(prompt["audio"], self.clock)

        clock2 = FakeClock()
        source2 = PacedPcmSource(fake_pcm, clock=clock2,
                                 sleep=clock2.sleep, threaded=False)
        text, metrics = asyncio.run(_collect_stream(FakeHandle(clock2), source2, clock=clock2))
        assert "TRANSCRIPT_SENTINEL" in text
        assert metrics["update_count"] == 2 and metrics["first_nonempty_update_s"] is not None
        assert metrics["queue_high_water"] <= QUEUE_BLOCKS
        assert metrics["captured_audio_s"] == metrics["consumed_audio_s"] == round(3 * CHUNK_SECONDS, 6)
        assert metrics["first_nonempty_update_s"] >= 2 * CHUNK_SECONDS
        assert metrics["stream_wall_s"] >= metrics["first_nonempty_update_s"]

        key_a = _run_key(PINNED_MANIFEST_SHA256,
                         {"sha256": "a" * 64}, {"sha256": "b" * 64},
                         [{"id": "x", "audio_sha256": "c" * 64, "audio_bytes": 1}])
        assert key_a == _run_key(PINNED_MANIFEST_SHA256,
                                 {"sha256": "a" * 64}, {"sha256": "b" * 64},
                                 [{"id": "x", "audio_sha256": "c" * 64, "audio_bytes": 1}])
        assert key_a != _run_key(PINNED_MANIFEST_SHA256,
                                 {"sha256": "d" * 64}, {"sha256": "b" * 64},
                                 [{"id": "x", "audio_sha256": "c" * 64, "audio_bytes": 1}])
        assert key_a != _run_key(PINNED_MANIFEST_SHA256,
                                 {"sha256": "a" * 64}, {"sha256": "b" * 64},
                                 [{"id": "x", "audio_sha256": "e" * 64, "audio_bytes": 1}])
        expected = {"id": "x", "audio_sha256": "c" * 64}
        fake_row = {"schema": SCHEMA, "completed": True, "cache_key": key_a,
                    "id": "x", "audio_sha256": "c" * 64,
                    "text": "TRANSCRIPT_SENTINEL private hypothesis",
                    "text_sha256": _sha(b"TRANSCRIPT_SENTINEL private hypothesis"),
                    "stream_metrics": {"stream_wall_s": 1.0,
                                       "captured_audio_s": 0.56,
                                       "consumed_audio_s": 0.56}}
        _validate_result_row(fake_row, expected, key_a)
        hypotheses = temp / "hypotheses.jsonl"
        _append_row(hypotheses, fake_row)
        resumed = _read_resume(hypotheses, [expected], key_a)
        assert resumed["x"]["text"] == fake_row["text"]
        try:
            _read_resume(hypotheses, [expected], "f" * 64)
        except Refusal:
            pass
        else:
            raise AssertionError("resume accepted a changed model/run key")

        public = {"schema": SCHEMA, "cache_key": key_a, "model": PINNED_MODEL,
                  "manifest_sha256": PINNED_MANIFEST_SHA256, "samples": 1,
                  "coverage": "complete", "cache_hit": False,
                  "model_ready_s": 1.0, "first_emitted_update_s": _quantiles([1.0]),
                  "first_nonempty_update_s": {"p50": "TRANSCRIPT_SENTINEL",
                                               "p95": None, "p99": None},
                  "gpu": {"device": "cuda:0", "text": "TRANSCRIPT_SENTINEL"},
                  "process": {"pid": 1, "text": "TRANSCRIPT_SENTINEL"},
                  "wer": 0.0, "hypotheses_sha256": "f" * 64}
        public_raw = json.dumps(_public_report(public), sort_keys=True)
        assert "TRANSCRIPT_SENTINEL" not in public_raw and "text" not in _public_report(public)
        # O RAMO DE CACHE FRIO (2026-11-23): os quatro valores vem do resultado do
        # motor, e um resultado sem o recibo e' RECUSADO em vez de estourar num
        # `UnboundLocalError` que nem nomeia o caminho.
        fake_engine = {"rows": [fake_row], "model_ready_s": 1.5,
                       "gpu": {"device": "cuda:0"}, "process": {"pid": 1}}
        got_rows, got_ready, got_gpu, got_proc = _engine_report_inputs(fake_engine)
        assert got_rows == [fake_row] and got_ready == 1.5
        assert got_gpu["device"] == "cuda:0" and got_proc["pid"] == 1
        for broken, why in (({"rows": [fake_row]}, "model-ready"),
                            ({"rows": [fake_row], "model_ready_s": 1.0}, "device"),
                            ({"rows": [fake_row], "model_ready_s": 1.0,
                              "gpu": {"device": "cpu"}}, "cuda"),
                            ({"rows": [], "model_ready_s": 1.0,
                              "gpu": {"device": "cuda:0"}, "process": {}}, "rows"),
                            ({"rows": [fake_row], "model_ready_s": 1.0,
                              "gpu": {"device": "cuda:0"}}, "process")):
            try:
                _engine_report_inputs(broken)
            except Refusal:
                pass
            else:
                raise AssertionError("cold-cache aggregate accepted a result without %s" % why)
        # A IDENTIDADE DO MODELO, sem modelo: com `usn` o receipt e' reaproveitado;
        # sem `usn` ele e' IGNORADO e o conteudo e' re-medido (nunca um SHA copiado
        # sem prova de que o byte nao mudou).
        ident_root = temp / "ident"
        fake_files = [temp / "a.bin", temp / "b.bin"]
        calls = {"n": 0}
        def _fake_hash(path, *, paced=False):
            calls["n"] += 1
            return ("%064x" % (calls["n"] + 900)), 10
        fp_usn = lambda _p: {"size": 10, "mtime_ns": 1, "ctime_ns": 1,
                             "device": 1, "file_id": 7, "usn": 4242}
        fp_nousn = lambda _p: {"size": 10, "mtime_ns": 1, "ctime_ns": 1,
                               "device": 1, "file_id": 7, "usn": None}
        ident1 = _model_identity(temp / "m", fake_files, ident_root,
                                 hash_file=_fake_hash, fingerprint=fp_usn)
        assert ident1["cache_hit"] is False and ident1["bytes_hashed"] == 20
        assert ident1["identity_basis"] == "usn+metadata"
        ident2 = _model_identity(temp / "m", fake_files, ident_root,
                                 hash_file=_fake_hash, fingerprint=fp_usn)
        assert ident2["cache_hit"] is True and ident2["sha256"] == ident1["sha256"]
        before = calls["n"]
        ident3 = _model_identity(temp / "m", fake_files, ident_root,
                                 hash_file=_fake_hash, fingerprint=fp_nousn)
        assert calls["n"] == before + 2, "sem usn a identidade TEM de ser re-medida"
        assert ident3["cache_hit"] is False and ident3["identity_basis"] == "rehash"
        if "kestrel" in sys.modules:
            raise AssertionError("model-free selftest imported Kestrel")
    print("KESTREL_ULTRA_STREAM_SELFTEST PASS manifest/model-pin/cuda/no-download/queue/updates/resume/redaction")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_DEFAULT)
    parser.add_argument("--expected-manifest-sha256", default=PINNED_MANIFEST_SHA256)
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument("--model-commit", default=PINNED_MODEL_COMMIT)
    parser.add_argument("--cache-root", type=Path, default=CACHE_DEFAULT)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.selftest:
        try:
            _selftest()
            return 0
        except Exception as exc:
            # Never echo exception strings: they can contain prompt or transcript data.
            print(json.dumps({"verdict": "FAIL", "type": type(exc).__name__}, sort_keys=True))
            return 1
    if args.model_dir is None:
        print(json.dumps({"verdict": "REFUSE", "reason": "--model-dir is required"}))
        return 2
    try:
        run(args)
        return 0
    except Refusal as exc:
        print(json.dumps({"verdict": "REFUSE", "reason": str(exc)}, sort_keys=True))
        return 2
    except Exception as exc:
        print(json.dumps({"verdict": "NO-VERDICT", "type": type(exc).__name__}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
