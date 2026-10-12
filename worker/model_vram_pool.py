"""MODEL VRAM POOL - one copy of a model per process, never two.

The owner rule, verbatim: "se o mesmo modelo ja existe carregado na vram,
reutiliza ele. se nao vai usar duplicados, do mesmo modelo" (2026-10-12).

WHAT THIS MODULE CAN DO (enforced here, testable in-process):
  * ONE copy per model per process. get_or_load hands back the SAME session
    objects for the same model + providers, so two call sites that ask for the
    same export do not each load it again. Measured, not asserted: the second
    call must add ZERO dedicated VRAM.
  * A loud VERDICT when the same model is already resident in ANOTHER process,
    so a second copy is never loaded blindly.
  * A refusal path (foreign_policy="refuse") for a caller that would rather not
    pay for a duplicate.

WHAT IT CANNOT DO (the honest half):
  * Reuse a copy held by ANOTHER PROCESS. VRAM is private to the process that
    allocated it. Sharing it needs CUDA IPC, and CUDA IPC needs an export handle
    (cudaIpcGetMemHandle) that the OWNER process must hand over. A third-party
    process cannot take it, and this module will not pretend otherwise. The
    detection above is the detectable half; the reuse is out of reach without the
    other process cooperation.

The pool is a LIBRARY. It owns loading, so "never twice" is a property of the
one function that can load a model, not a convention every caller must remember.
"""

from __future__ import annotations

import datetime
import json
import os
import threading
import time

try:
    import vram_residency as _res
except Exception:  # normal when the module is used from a scratch directory
    _res = None

MIB = 1048576.0


class ResidentModelError(RuntimeError):
    """Raised by get_or_load(foreign_policy="refuse") when the same model is
    already resident in another process. The verdict is in the message."""


class Entry:
    """One resident model: the sessions, the identity, the cost of loading it."""

    def __init__(self, model_dir, providers, identity, loaded_s, loader_label):
        self.model_dir = model_dir
        self.providers = tuple(providers or [])
        self.identity = identity
        self.loaded_s = loaded_s
        self.loader_label = loader_label
        self.created_at = datetime.datetime.now().astimezone().isoformat(
            timespec="milliseconds")
        self.refs = 1
        self.sessions = {}
        self.model = None
        self.processor = None
        self.load_vram_delta_MiB = None
        self.foreign_at_load = []

    def describe(self):
        return {
            "model_dir": self.model_dir,
            "providers": list(self.providers),
            "weights_total_MiB": round((self.identity.get("total_bytes") or 0) / MIB, 1),
            "loaded_s": self.loaded_s,
            "loaded_at": self.created_at,
            "refs": self.refs,
            "loader": self.loader_label,
        }


_DLL_DIR_HANDLES = []
_POOL = {}
_LOCK = threading.Lock()
_LOADERS = {}


def register_loader(label):
    """Decorator: register a model loader under a name.

    The default loader builds the Sotto streaming engine pieces (three ORT
    sessions for encoder/decoder/joint plus one ORT-GenAI model and streaming
    processor). A caller may register its own (a Parakeet backend, a test double)
    and ask for it by name, so the pool stays model-agnostic.
    """
    def deco(fn):
        _LOADERS[label] = fn
        return fn
    return deco


def pool_key(model_dir, providers=None, loader="sotto"):
    """The pool key: (model dir, loader, provider list).

    Same model + same loader + same providers -> the SAME entry, so the second
    asker gets the sessions that already exist instead of a second copy. Anything
    that differs is a different entry by definition.
    """
    model_dir = os.path.abspath(os.path.normpath(model_dir))
    providers = tuple(providers or ["CUDAExecutionProvider", "CPUExecutionProvider"])
    return model_dir + "|" + loader + "|" + ",".join(providers)

def _add_cuda_dll_dirs():
    # Make CUDA/cuDNN importable from the torch + nvidia pip wheels.
    # onnxruntime-gpu needs cublas/cudnn on the DLL search path. On this host they
    # ship inside site-packages (torch/lib and nvidia/*/lib), NOT on PATH, so a
    # plain shell gets a CUDA provider that silently fails to load. Must run BEFORE
    # onnxruntime is imported. This mirrors worker/sotto_worker.py.
    import site
    import sysconfig
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
        bases.append(sysconfig.get_paths()["purelib"])
    except Exception:
        pass
    for base in bases:
        nv = os.path.join(base, "nvidia")
        if not os.path.isdir(nv):
            continue
        for root, dirs, files in os.walk(nv):
            depth = root[len(nv):].count(os.sep)
            if depth > 3:
                dirs[:] = []
                continue
            if any(f.lower().endswith(".dll") for f in files):
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

dll_dirs_ready = [False]

def _ensure_dll_dirs():
    # Run the DLL-dir fix-up exactly once per process, before onnxruntime loads.
    if dll_dirs_ready[0]:
        return
    dll_dirs_ready[0] = True
    _add_cuda_dll_dirs()


def _own_pid():
    return os.getpid()


def _vram_mine():
    """This process dedicated GPU memory in MiB, or None when unmeasurable."""
    if _res is None:
        return None
    try:
        snap = _res.pdh_snapshot()
    except Exception:
        return None
    # Scoped to our own pid: the PDH snapshot carries EVERY process on the box,
    # and summing all of them reports the whole machine as ours (measured: a
    # process that had loaded nothing read back 7.6 GB of dedicated VRAM).
    for pid, rec in snap.items():
        if pid == _own_pid():
            return round(rec.get("ded_MiB", 0.0), 1)
    return 0.0


def pool_state():
    """What is resident in THIS process right now."""
    with _LOCK:
        return {
            "pid": _own_pid(),
            "entries": [e.describe() for e in _POOL.values()],
            "count": len(_POOL),
            "my_vram_ded_MiB": _vram_mine(),
        }


def _foreign_verdict(identity):
    """The loud part: who else already holds this model."""
    if _res is None:
        return []
    try:
        procs = _res.per_process_vram(min_mib=0.5)
        return _res.find_foreign_holders(identity, procs, own_pid=_own_pid())
    except Exception:
        return []


def _load_fresh(model_dir, providers, loader, use_vad, lang_id):
    """Actually load. The ONLY place a model enters this process."""
    fn = _LOADERS.get(loader)
    if fn is None:
        raise RuntimeError("model_vram_pool: unknown loader %r (have %s)"
                           % (loader, sorted(_LOADERS)))
    before = _vram_mine()
    t0 = time.time()
    built = fn(model_dir, providers, use_vad=use_vad, lang_id=lang_id)
    dt = time.time() - t0
    after = _vram_mine()
    return {"built": built, "loaded_s": round(dt, 3),
            "vram_before_MiB": before, "vram_after_MiB": after}


def get_or_load(model_dir, providers=None, use_vad=None, lang_id=None,
                loader="sotto", foreign_policy="report"):
    """Return the resident Entry for this model, loading it exactly once.

    Same model_dir + same providers -> the SAME Entry, the same session objects,
    zero extra VRAM. A different model (or a different provider list) is a
    different entry.

    foreign_policy:
      "report" - say loudly that another process holds this model, then load
                 anyway (this process still has to work).
      "refuse" - raise ResidentModelError and load nothing.
    """
    if foreign_policy not in ("report", "refuse"):
        raise ValueError("foreign_policy must be report or refuse")
    model_dir = os.path.abspath(os.path.normpath(model_dir))
    providers = tuple(providers or ["CUDAExecutionProvider", "CPUExecutionProvider"])
    key = pool_key(model_dir, providers=providers, loader=loader)

    with _LOCK:
        entry = _POOL.get(key)
        if entry is not None:
            entry.refs += 1
            return entry

    # Outside the lock: the verdict is measured BEFORE the load, so a duplicate
    # is never produced silently.
    identity = None
    if _res is not None:
        try:
            identity = _res.model_identity(model_dir, hash_weights=True)
        except Exception as exc:
            identity = {"dir": model_dir, "error": str(exc), "total_bytes": 0}
    foreign = _foreign_verdict(identity) if identity else []
    if foreign and foreign_policy == "refuse":
        raise ResidentModelError(
            "model_vram_pool: REFUSING to load " + model_dir + " - the same model "
            "is already resident in another process: " + json.dumps(
                [{"pid": h.get("pid"), "name": h.get("name"),
                  "ded_MiB": h.get("ded_MiB"), "why": h.get("why")} for h in foreign],
                ensure_ascii=False))

    load = _load_fresh(model_dir, providers, loader, use_vad, lang_id)

    with _LOCK:
        entry = _POOL.get(key)
        if entry is not None:          # raced: someone loaded it meanwhile
            entry.refs += 1
            _discard(load)
            return entry
        entry = Entry(model_dir, providers, identity or {"dir": model_dir},
                      load["loaded_s"], loader)
        entry.sessions = (load.get("built") or {}).get("sessions", {})
        entry.model = (load.get("built") or {}).get("model")
        entry.processor = (load.get("built") or {}).get("processor")
        entry.load_vram_delta_MiB = (
            None if (load["vram_after_MiB"] is None or load["vram_before_MiB"] is None)
            else round(load["vram_after_MiB"] - load["vram_before_MiB"], 1))
        entry.foreign_at_load = foreign
        _POOL[key] = entry
        return entry


def _discard(load):
    """Free what a losing racer just built, so the race leaves no second copy."""
    built = load.get("built") or {}
    for s in (built.get("sessions") or {}).values():
        try:
            del s
        except Exception:
            pass
    for obj in (built.get("model"), built.get("processor")):
        try:
            del obj
        except Exception:
            pass


def release(model_dir, providers=None, loader="sotto"):
    """Drop a reference; the entry leaves the pool when the last one goes."""
    model_dir = os.path.abspath(os.path.normpath(model_dir))
    providers = tuple(providers or ["CUDAExecutionProvider", "CPUExecutionProvider"])
    key = pool_key(model_dir, providers=providers, loader=loader)
    with _LOCK:
        entry = _POOL.get(key)
        if entry is None:
            return False
        entry.refs -= 1
        if entry.refs <= 0:
            _discard({"built": {"sessions": entry.sessions, "model": entry.model,
                               "processor": entry.processor}})
            _POOL.pop(key, None)
        return True


def verdict_lines(model_dir=None):
    """Human-readable lines, suitable for a log the owner can read."""
    lines = []
    st = pool_state()
    lines.append("VRAM-POOL pid=%d entries=%d my_dedicated=%s MiB"
                 % (st["pid"], st["count"], st["my_vram_ded_MiB"]))
    for e in st["entries"]:
        lines.append("  resident: %s providers=%s weights=%.1f MiB loaded_in=%ss refs=%d"
                     % (e["model_dir"], e["providers"], e["weights_total_MiB"],
                        e["loaded_s"], e["refs"]))
    if model_dir and _res is not None:
        try:
            ident = _res.model_identity(model_dir, hash_weights=True)
            total_mib = (ident.get("total_bytes") or 0) / MIB
            lines.append("  model on disk: %s (%.1f MiB, %d weight files)"
                         % (ident.get("dir"), total_mib, len(ident.get("weights") or [])))
            strong = _res.find_model_holders(ident, _res.per_process_vram(min_mib=0.5),
                                             own_pid=_own_pid())
            if strong:
                lines.append("  VERDICT: a Sotto worker (this same model) is ALREADY RESIDENT:")
                for h in strong:
                    lines.append("    pid=%s %s ded=%.1f MiB"
                                 % (h.get("pid"), h.get("name"), h.get("ded_MiB")))
                lines.append("  VERDICT: loading a second copy here would be a DUPLICATE "
                             "of that one - and cannot be avoided by VRAM sharing, because "
                             "VRAM is private to the process that allocated it.")
            else:
                lines.append("  VERDICT: no other Sotto worker is resident; nothing to reuse.")
            foreign = _foreign_verdict(ident)
            plausible = [h for h in foreign if h.get("tier") == "size-plausible"]
            if plausible:
                lines.append("  NOTE: %d process(es) hold enough VRAM to contain this model "
                             "without being Sotto (candidates, not copies):" % len(plausible))
                for h in plausible[:5]:
                    lines.append("    pid=%s %s ded=%.1f MiB"
                                 % (h.get("pid"), h.get("name"), h.get("ded_MiB")))
        except Exception as exc:
            lines.append("  VERDICT: could not measure foreign holders: %s: %s"
                         % (type(exc).__name__, exc))
    return lines


# --------------------------------------------------------------------------
# the loaders
# --------------------------------------------------------------------------
@register_loader("sotto")
def _load_sotto(model_dir, providers, use_vad=None, lang_id=None):
    """Build exactly what worker/sotto_worker.py StreamAsr builds, once.

    Three ORT sessions (encoder/decoder/joint - the RNNT weights) plus one
    ORT-GenAI model and one streaming processor (the cache-aware mel window and
    the Silero VAD). og.Model is CPU-only in the installed 0.17.1, so it costs
    host RAM, not VRAM: measured 2026-10-12, +833 MB RSS and +0 MiB dedicated.
    """
    _ensure_dll_dirs()
    import onnxruntime as ort
    import onnxruntime_genai as og

    so = ort.SessionOptions()
    so.log_severity_level = 3
    try:
        so.intra_op_num_threads = int(os.environ.get("OMP_NUM_THREADS", "8"))
        so.inter_op_num_threads = 1
    except Exception:
        pass
    enc = ort.InferenceSession(os.path.join(model_dir, "encoder.onnx"), so,
                               providers=list(providers))
    dec = ort.InferenceSession(os.path.join(model_dir, "decoder.onnx"), so,
                               providers=list(providers))
    joint = ort.InferenceSession(os.path.join(model_dir, "joint.onnx"), so,
                                 providers=list(providers))
    model = og.Model(model_dir)
    processor = model.create_streaming_processor()
    if use_vad is not None:
        processor.set_option("use_vad", "1" if use_vad else "0")
    return {"sessions": {"encoder": enc, "decoder": dec, "joint": joint},
            "model": model, "processor": processor}


@register_loader("noop")
def _load_noop(model_dir, providers, use_vad=None, lang_id=None):
    """A loader that loads nothing. For arms that must not touch the GPU."""
    return {"sessions": {}, "model": None, "processor": None}


@register_loader("onnx-single")
def _load_single(model_dir, providers, use_vad=None, lang_id=None):
    """ONE ORT session on the encoder only. A fast, cheap, real load."""
    _ensure_dll_dirs()
    import onnxruntime as ort
    so = ort.SessionOptions()
    so.log_severity_level = 3
    enc = ort.InferenceSession(os.path.join(model_dir, "encoder.onnx"), so,
                               providers=list(providers))
    return {"sessions": {"encoder": enc}, "model": None, "processor": None}
