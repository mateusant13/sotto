"""Small stdlib-only ONNX Runtime CUDA bootstrap shared by worker and sidecar.

Importing this module does not import torch, NumPy, sherpa-onnx or ORT. Call
``prepare_ort_runtime`` before importing ORT in a standalone process, or call
``preload_cuda_runtime(ort)`` when the caller already owns the imported module.
The CUDA EP device census, packaged-plugin registration and its post-registration
census are fail-closed: provider names alone never count as a CUDA device.
"""
from __future__ import annotations

import os
import sys


_DLL_DIR_HANDLES = []
MAX_NVIDIA_DIR_ENTRIES = 4096


def _nvidia_library_dirs(bases, max_entries=MAX_NVIDIA_DIR_ENTRIES):
    """Find bounded-depth NVIDIA DLL roots with a total entry budget."""
    candidates = []
    total_entries = 0
    seen_bases = set()
    for base in bases:
        base_key = os.path.normcase(os.path.abspath(os.fspath(base)))
        if base_key in seen_bases:
            continue
        seen_bases.add(base_key)
        nv_root = os.path.join(base, "nvidia")
        if not os.path.isdir(nv_root):
            continue
        pending = [(nv_root, 0)]
        while pending:
            current, depth = pending.pop()
            has_cuda_library = False
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        total_entries += 1
                        if total_entries > max_entries:
                            raise RuntimeError(
                                "cuda-dll-directory-entry-limit-exceeded "
                                "limit=%d observed=%d root=%s"
                                % (max_entries, total_entries, nv_root))
                        try:
                            is_dir = entry.is_dir(follow_symlinks=False)
                        except OSError:
                            continue
                        if is_dir:
                            if depth < 3:
                                pending.append((entry.path, depth + 1))
                        elif entry.name.lower().endswith((".dll", ".so")):
                            has_cuda_library = True
            except OSError:
                continue
            if has_cuda_library:
                candidates.append(current)
    return candidates


def add_cuda_dll_dirs(handles=None) -> None:
    """Expose CUDA/cuDNN DLL directories without importing torch."""
    if handles is None:
        handles = _DLL_DIR_HANDLES
    import site

    candidates = []
    try:
        import importlib.util

        spec = importlib.util.find_spec("torch")
        if spec is not None and spec.origin:
            candidates.append(os.path.join(os.path.dirname(spec.origin), "lib"))
    except Exception:  # noqa: BLE001 -- absent/incomplete optional torch install
        pass
    bases = []
    try:
        bases.extend(site.getsitepackages())
    except Exception:  # noqa: BLE001 -- embedded Python may not expose site dirs
        pass
    try:
        import sysconfig

        bases.append(sysconfig.get_paths()["purelib"])
    except Exception:  # noqa: BLE001 -- keep the remaining candidate paths
        pass
    candidates.extend(_nvidia_library_dirs(bases))
    for directory in candidates:
        if not os.path.isdir(directory):
            continue
        try:
            handles.append(os.add_dll_directory(directory))
        except (AttributeError, OSError):
            pass
        current_path = os.environ.get("PATH", "").split(os.pathsep)
        if directory not in current_path:
            os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")


def cuda_device_census(ort):
    """Return ``(True/False/None, bounded provider names)`` from ORT's EP API."""
    getter = getattr(ort, "get_ep_devices", None)
    if not callable(getter):
        return None, ()
    names = []
    registered = False
    try:
        for device in getter():
            raw_name = str(getattr(device, "ep_name", ""))
            if raw_name == "CUDAExecutionProvider":
                registered = True
            name = " ".join(raw_name.split())[:48].replace('"', "'")
            if name and name not in names and len(names) < 8:
                names.append(name)
    except Exception:  # noqa: BLE001 -- unknown census is not CUDA evidence
        return None, ()
    return registered, tuple(names)


def register_cuda_plugin_if_needed(ort) -> bool:
    """Register the packaged plugin only when the census lacks CUDA.

    Returns True only if this call added the CUDA device. A positive census is
    sufficient and does not require the optional registration API. Unknown
    census, or missing API/library when registration is necessary, refuses.
    """
    registered, device_names = cuda_device_census(ort)
    if registered is True:
        return False
    if registered is None:
        raise RuntimeError(
            "CUDA EP device census is unavailable; refusing explicit registration")

    providers_getter = getattr(ort, "get_available_providers", None)
    if not callable(providers_getter) or "CUDAExecutionProvider" not in list(
            providers_getter()):
        return False

    register = getattr(ort, "register_execution_provider_library", None)
    if not callable(register):
        raise RuntimeError(
            "CUDA EP device is missing and ORT exposes no plugin registration API")

    module_file = getattr(ort, "__file__", "")
    if not module_file:
        raise RuntimeError("CUDA EP plugin path cannot be resolved from ORT module")
    if os.name == "nt":
        library_name = "onnxruntime_providers_cuda.dll"
    elif sys.platform == "darwin":
        library_name = "libonnxruntime_providers_cuda.dylib"
    else:
        library_name = "libonnxruntime_providers_cuda.so"
    library_path = os.path.join(os.path.dirname(module_file), "capi", library_name)
    if not os.path.isfile(library_path):
        raise RuntimeError(
            "CUDA EP device is missing and packaged plugin library is absent")

    register("CUDAExecutionProvider", library_path)
    registered, device_names = cuda_device_census(ort)
    if registered is not True:
        raise RuntimeError(
            "explicit CUDA plugin registration did not expose a CUDA EP device "
            "(devices=%s)" % (",".join(device_names) or "none"))
    return True


def preload_dlls(ort=None):
    """Preload CUDA/cuDNN libraries without creating or querying a session."""
    if ort is None:
        import onnxruntime as ort
    preload = getattr(ort, "preload_dlls", None)
    if not callable(preload):
        raise RuntimeError(
            "GPU-only ASR requires onnxruntime.preload_dlls() before CUDA sessions")
    preload()
    return ort


def preload_cuda_runtime(ort=None) -> bool:
    """Preload CUDA/cuDNN, then register and re-census the packaged CUDA EP."""
    ort = preload_dlls(ort)
    register_cuda_plugin_if_needed(ort)
    return True


def prepare_ort_runtime(ort=None):
    """Prepare DLL lookup before ORT import, preload and require CUDA census."""
    add_cuda_dll_dirs()
    if ort is None:
        import onnxruntime as ort
    preload_cuda_runtime(ort)
    registered, names = cuda_device_census(ort)
    if registered is not True:
        raise RuntimeError(
            "GPU-only ASR requires a positive CUDA EP-device census (devices=%s)"
            % (",".join(names) or "none"))
    return ort
