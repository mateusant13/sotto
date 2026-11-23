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

   This table is historical cost evidence, not an allowed execution mode.
   Sotto now requires CUDA for every Redux neural path and refuses CPU requests.

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
from contextlib import ExitStack, contextmanager
from concurrent.futures import ThreadPoolExecutor
import hashlib
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

# Hash pins and exact CPU node maps for the preprocessor, encoder, and VAD.
# Together these allow only measured shape/control operators on CPU; neural
# nodes remain on CUDA and every graph is checked through ORT node readback.
REDUX_PREPROCESSOR_CONTROL_SHA256 = (
    "3de5742f5780fc8615c1d883a2a60e28621ff13d2e20d24d76e94b9e4168445f"
)
REDUX_PREPROCESSOR_CONTROL_ORT_VERSION = "1.30.0"
REDUX_PREPROCESSOR_CONTROL_NODES = {
    "node_sym_size_int_21": "Squeeze",
    "node_floordiv": "Div",
    "node_add_100": "Add",
}
REDUX_ENCODER_CONTROL_SHA256 = (
    "ade2c65c188776b3662db620a553ab82ac7e9ca11a7be6b696bcc5190f75382e"
)
REDUX_ENCODER_CONTROL_NODES = {
    "node_Concat_153": "Concat",
    "node_Concat_184": "Concat",
    "node_Concat_191": "Concat",
    "node_Concat_342": "Concat",
    "node_Concat_387": "Concat",
    "node_Concat_394": "Concat",
    "node_Concat_420": "Concat",
    "node_Concat_467": "Concat",
    "node_Reshape_151": "Reshape",
    "node_Reshape_188": "Reshape",
    "node_add_152": "Add",
    "node_add_38": "Add",
    "node_add_39": "Add",
    "node_add_8393": "Add",
    "node_add_93": "Add",
    "node_floordiv": "Div",
    "node_floordiv_1": "Div",
    "node_floordiv_2": "Div",
    "node_mul_6234": "Mul",
    "node_neg": "Neg",
    "node_sym_size_int_318": "Squeeze",
}
REDUX_VAD_CONTROL_SHA256 = (
    "18dfbe344307f9eda4735d4da1fe1cd6e3be27055a6c25b4a4a2e6fe0bffde50"
)
REDUX_VAD_CONTROL_NODES = {
    "node_Concat_153": "Concat",
    "node_Reshape_151": "Reshape",
    "node_add_152": "Add",
    "node_add_38": "Add",
    "node_add_39": "Add",
    "node_add_93": "Add",
    "node_floordiv": "Div",
    "node_floordiv_1": "Div",
    "node_floordiv_2": "Div",
    "node_sym_size_int_28": "Squeeze",
}
REDUX_CONTROL_GRAPH_ALLOWLIST = {
    "preprocessor.onnx": (REDUX_PREPROCESSOR_CONTROL_SHA256,
                          REDUX_PREPROCESSOR_CONTROL_NODES),
    "encoder-model.onnx": (REDUX_ENCODER_CONTROL_SHA256,
                            REDUX_ENCODER_CONTROL_NODES),
    "vad-model.onnx": (REDUX_VAD_CONTROL_SHA256, REDUX_VAD_CONTROL_NODES),
}
REDUX_GRAPH_NODE_COUNTS = {
    "preprocessor.onnx": 55,
    # ORT 1.30 get_provider_graph_assignment_info() measured 1,713 assignments,
    # 75 more CUDA assignments than the former expectation. The exact pinned
    # CPU-control map remains 21 nodes; pin the observed EP census.
    "encoder-model.onnx": 1713,
    "decoder_joint-model.onnx": 51,
    "vad-model.onnx": 101,
}
REDUX_PINNED_CONTROL_PROVIDER_COUNTS = {
    "preprocessor.onnx": {"CUDAExecutionProvider": 52, "CPUExecutionProvider": 3},
    "encoder-model.onnx": {"CUDAExecutionProvider": 1692, "CPUExecutionProvider": 21},
    "decoder_joint-model.onnx": {"CUDAExecutionProvider": 51},
    "vad-model.onnx": {"CUDAExecutionProvider": 91, "CPUExecutionProvider": 10},
}
_CPU_FALLBACK_KEY = "session.disable_cpu_ep_fallback"
SESSION_FAILURE_TRACE_ENV = "SOTTO_REDUX_ORT_SESSION_FAILURE_TRACE"
SESSION_FAILURE_TRACE_GRAPHS = frozenset({
    "preprocessor.onnx", "encoder-model.onnx",
    "decoder_joint-model.onnx", "vad-model.onnx",
})
CORE_SESSION_WORKERS = 3
CONTROL_HASH_WORKERS = 1
REDUX_ORT_CACHE_GRAPHS = frozenset({
    "preprocessor.onnx", "encoder-model.onnx",
})
REDUX_ORT_CACHE_SCHEMA = 3
REDUX_ORT_CACHE_DIR = ".sotto-ort-cache"
_ORT_GLOBAL_POOL_LOCK = threading.Lock()
_ORT_GLOBAL_POOL_CONFIG = None
_CONTROL_HASH_EXECUTOR_LOCK = threading.Lock()
_CONTROL_HASH_EXECUTOR = None
_NUMERIC_THREAD_ENV = (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"
)

# ── the GPU-only execution policy ─────────────────────────────────────────────
#: CUDA is the sole neural provider. The three pinned shape/control graphs
#: explicitly add CPU EP and must pass exact per-node readback before use.
GPU_PROVIDERS = ("CUDAExecutionProvider",)
CONTROL_GRAPH_PROVIDERS = ("CUDAExecutionProvider", "CPUExecutionProvider")


def _graph_provider_entries(graph_name: str, providers):
    """Register CPU EP only for the three hash-pinned shape/control graphs."""
    provider_entries = list(providers or ())
    identity = _ReduxControlOnlyOrtProxy._provider_identity(provider_entries)
    names = [row["name"] for row in identity]
    if names != ["CUDAExecutionProvider"]:
        raise RuntimeError("Redux graph requested providers are not the pinned route")
    if graph_name in REDUX_CONTROL_GRAPH_ALLOWLIST:
        return provider_entries + ["CPUExecutionProvider"]
    return provider_entries


def _reference_session_providers(graph_name: str, providers, cache_loader=None):
    """Pass raw providers through the guarded proxy, pre-expanding only direct cache loads.

    Normal session construction enters ``_ReduxControlOnlyOrtProxy.InferenceSession``,
    which performs the allowlisted CPU-EP expansion itself. The optimized-cache
    callback calls the proxy's guarded ``_run_session`` directly, so that branch
    needs the expanded list here.
    """
    if cache_loader is not None and graph_name in REDUX_ORT_CACHE_GRAPHS:
        return _graph_provider_entries(graph_name, providers)
    return list(providers or ())


def _reference_session_readback_names(graph_name: str, requested_providers,
                                      cache_loader=None) -> list[str]:
    """Return the provider list that the guarded ORT proxy must read back.

    The reference adapter passes raw CUDA entries to ordinary InferenceSession
    calls; the proxy adds the pinned CPU shape/control EP there. Direct optimized
    cache callbacks bypass InferenceSession, so their adapter input is already
    expanded and must not be expanded a second time.
    """
    if cache_loader is not None and graph_name in REDUX_ORT_CACHE_GRAPHS:
        effective = list(requested_providers or ())
    else:
        effective = _graph_provider_entries(graph_name, requested_providers)
    return [row["name"] for row in _ReduxControlOnlyOrtProxy._provider_identity(
        effective)]


def _reference_session_provider_readback_matches(
        graph_name: str, requested_providers, cache_loader,
        actual_provider_entries) -> bool:
    """Compare proxy readback to the effective, once-expanded graph request."""
    expected_names = _reference_session_readback_names(
        graph_name, requested_providers, cache_loader)
    if not isinstance(actual_provider_entries, (list, tuple)):
        return False
    actual_names = []
    for item in actual_provider_entries:
        if isinstance(item, dict):
            name = item.get("name")
        elif isinstance(item, (tuple, list)):
            name = item[0] if item else None
        else:
            name = item
        if not isinstance(name, str) or not name:
            return False
        actual_names.append(name)
    return actual_names == expected_names


def _set_numeric_thread_environment(threads: int) -> int:
    """Set one thread per numerical pool before importing numerical libraries."""
    effective = max(1, int(threads or 1))
    for name in _NUMERIC_THREAD_ENV:
        os.environ[name] = str(effective)
    return effective


def _file_sha256(path: Path) -> str:
    """Hash an allowlisted ONNX graph without copying it into process memory."""
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _timed_control_graph_hash(path: Path) -> tuple[str, float]:
    started = time.perf_counter()
    return _file_sha256(path), time.perf_counter() - started


def _submit_control_graph_hash(path: Path):
    """Hash inline when the route has no helper-pool budget; otherwise submit."""
    global _CONTROL_HASH_EXECUTOR
    if CONTROL_HASH_WORKERS <= 0:
        return _timed_control_graph_hash(Path(path))
    with _CONTROL_HASH_EXECUTOR_LOCK:
        if _CONTROL_HASH_EXECUTOR is None:
            _CONTROL_HASH_EXECUTOR = ThreadPoolExecutor(
                max_workers=CONTROL_HASH_WORKERS,
                thread_name_prefix="redux-integrity-hash",
            )
        executor = _CONTROL_HASH_EXECUTOR
    return executor.submit(_timed_control_graph_hash, Path(path))


def _resolve_control_graph_hash(result):
    """Resolve either the inline digest tuple or a bounded helper future."""
    return result.result() if callable(getattr(result, "result", None)) else result


def _load_core_sessions(core_names, loader, cache_loader=None):
    """Load core sessions serially when helper budget is zero, else bounded parallel."""
    names = tuple(core_names)
    if CORE_SESSION_WORKERS <= 0:
        return {name: loader(name, cache_loader) for name in names}
    with ThreadPoolExecutor(max_workers=CORE_SESSION_WORKERS,
                            thread_name_prefix="redux-ort-load") as pool:
        pending = {name: pool.submit(loader, name, cache_loader) for name in names}
        return {name: future.result() for name, future in pending.items()}


@contextmanager
def _try_exclusive_cache_lock(lock_path: Path):
    """Serialize cache publication across worker processes without a child process."""
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        try:
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            yield False
            return
        try:
            yield True
        finally:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)


def _configure_shared_ort_pools(ort_module, threads: int) -> tuple[int, int]:
    """Create one bounded ORT pool shared by the four Redux graph sessions."""
    global _ORT_GLOBAL_POOL_CONFIG
    desired = (max(1, int(threads)), 1)
    with _ORT_GLOBAL_POOL_LOCK:
        if _ORT_GLOBAL_POOL_CONFIG is not None:
            if _ORT_GLOBAL_POOL_CONFIG != desired:
                raise RuntimeError(
                    "Redux ORT global thread pools already configured as %r, requested %r"
                    % (_ORT_GLOBAL_POOL_CONFIG, desired)
                )
            return desired
        setter = getattr(ort_module, "set_global_thread_pool_sizes", None)
        if not callable(setter):
            raise RuntimeError("installed ORT lacks the shared global thread-pool API")
        setter(intra_op_num_threads=desired[0], inter_op_num_threads=desired[1])
        _ORT_GLOBAL_POOL_CONFIG = desired
    return desired


def _expected_session_readback_graphs(model_dir: Path,
                                      node_assignment_trace: bool) -> frozenset[str]:
    """Keep normal startup core-only; diagnostic startup also attests existing VAD."""
    core = frozenset((
        "preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx"
    ))
    vad_exists = (Path(model_dir) / "vad-model.onnx").is_file()
    if node_assignment_trace and not vad_exists:
        raise RuntimeError("Redux node-assignment trace requires the pinned VAD graph")
    return core | {"vad-model.onnx"} if node_assignment_trace else core


class _ReduxControlOnlyOrtProxy:
    """Build pinned CPU-control graphs while keeping neural nodes on CUDA."""

    def __init__(self, ort_module, model_dir: Path, gpu_only: bool = True,
                 optimized_cache: bool = True):
        self._gpu_only = bool(gpu_only)
        self._optimized_cache = bool(optimized_cache)
        self._ort = ort_module
        self._model_dir = Path(model_dir).resolve()
        self._allowlisted_paths = {
            name: (self._model_dir / name).resolve()
            for name in REDUX_CONTROL_GRAPH_ALLOWLIST
        }
        self._validated = set()
        self.control_hash_readback = {}
        self.session_cache_readback = {}
        self.options_readback = {}
        self.runtime_fallback_readback = {}
        self.node_assignment_readback = {}
        self.node_assignment_readback_s = 0.0
        self._thread_sampler = None
        self._thread_trace_lock = threading.Lock()

    def __getattr__(self, name):
        return getattr(self._ort, name)

    def SessionOptions(self):
        """Use shared process pools and avoid idle spinning on control nodes."""
        options = self._ort.SessionOptions()
        options.inter_op_num_threads = 1
        options.execution_mode = self._ort.ExecutionMode.ORT_SEQUENTIAL
        options.use_per_session_threads = False
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        options.add_session_config_entry("session.inter_op.allow_spinning", "0")
        # Placement evidence is an admission condition before a neural graph is
        # used. Keep the expensive INFO log switch separately opt-in below.
        options.add_session_config_entry(
            "session.record_ep_graph_assignment_info", "1")
        return options

    def _read_node_assignment(self, graph_name: str, session) -> None:
        """Attest every acoustic node against the pinned CPU-control map."""
        def session_readback_context():
            options = self.options_readback.get(graph_name, {})
            input_format = options.get("session_input_format")
            if (not isinstance(input_format, str)
                    or input_format not in {"onnx", "ort"}):
                input_format = None
            optimized_output = options.get("optimized_model_output")
            if not isinstance(optimized_output, bool):
                optimized_output = None
            return input_format, optimized_output

        expected_total = REDUX_GRAPH_NODE_COUNTS.get(graph_name)
        expected_cpu_nodes = REDUX_CONTROL_GRAPH_ALLOWLIST.get(
            graph_name, (None, {}))[1]
        expected_providers = REDUX_PINNED_CONTROL_PROVIDER_COUNTS.get(graph_name)
        get_assignments = getattr(session, "get_provider_graph_assignment_info", None)
        if not callable(get_assignments):
            raise RuntimeError("Redux ORT graph/node assignment readback is unavailable")
        try:
            assignments = get_assignments()
        except Exception as exc:
            raise RuntimeError(
                "Redux ORT graph/node assignment readback failed for %s"
                % graph_name) from exc
        if (not isinstance(assignments, (list, tuple)) or not assignments
                or len(assignments) > 4096):
            if not isinstance(assignments, (list, tuple)):
                readback_state, readback_rows = "invalid-type", None
            elif not assignments:
                readback_state, readback_rows = "empty", 0
            else:
                readback_state, readback_rows = "oversized", 4097
            session_input_format, optimized_model_output = session_readback_context()
            expected_provider_counts = (
                expected_providers if isinstance(expected_providers, dict) else None)
            error = RuntimeError(
                "Redux ORT graph/node assignment readback is empty or unbounded")
            error.sotto_node_assignment_diagnostic = {
                "graph": graph_name,
                "trace_enabled": (
                    os.environ.get("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE") == "1"),
                "readback_state": readback_state,
                "assignment_rows": readback_rows,
                "session_input_format": session_input_format,
                "optimized_model_output": optimized_model_output,
                "actual_total": None,
                "expected_total": expected_total,
                "actual_providers": None,
                "expected_providers": expected_provider_counts,
                "actual_cpu_nodes": None,
                "expected_cpu_nodes": len(expected_cpu_nodes),
                "missing_cpu_nodes": None,
                "extra_cpu_nodes": None,
                "changed_cpu_ops": None,
                "examples": [],
                "examples_truncated": False,
            }
            raise error
        providers = {}
        cpu_nodes = {}
        total_nodes = 0
        for subgraph in assignments:
            provider = getattr(subgraph, "ep_name", None)
            get_nodes = getattr(subgraph, "get_nodes", None)
            if (not isinstance(provider, str) or not provider or len(provider) > 80
                    or not callable(get_nodes)):
                raise RuntimeError(
                    "Redux ORT graph/node assignment record is incomplete")
            try:
                nodes = list(get_nodes())
                count = len(nodes)
            except Exception as exc:
                raise RuntimeError(
                    "Redux ORT graph/node assignment node count is unavailable") from exc
            if (not isinstance(count, int) or isinstance(count, bool) or count < 0
                    or count > 1_000_000 or total_nodes + count > 1_000_000):
                raise RuntimeError(
                    "Redux ORT graph/node assignment node bound exceeded")
            providers[provider] = providers.get(provider, 0) + count
            total_nodes += count
            if provider == "CPUExecutionProvider":
                for node in nodes:
                    name = getattr(node, "name", None)
                    op_type = getattr(node, "op_type", None)
                    if (not isinstance(name, str) or not name or len(name) > 256
                            or not isinstance(op_type, str) or not op_type
                            or len(op_type) > 80 or name in cpu_nodes):
                        raise RuntimeError(
                            "Redux CPU control-node identity is incomplete or duplicated")
                    cpu_nodes[name] = op_type
        if (expected_total is None or expected_providers is None
                or total_nodes != expected_total
                or sum(providers.values()) != total_nodes
                or providers != expected_providers
                or cpu_nodes != expected_cpu_nodes):
            expected_names = set(expected_cpu_nodes)
            matched_names = expected_names.intersection(cpu_nodes)
            missing_names = expected_names.difference(cpu_nodes)
            changed_cpu = [
                name for name in matched_names
                if cpu_nodes[name] != expected_cpu_nodes[name]
            ]
            missing_cpu_count = len(missing_names)
            extra_cpu_count = max(0, len(cpu_nodes) - len(matched_names))
            examples = []
            for name in sorted(missing_names):
                if len(examples) >= 4:
                    break
                examples.append("missing:%s:%s" % (
                    name, expected_cpu_nodes[name]))
            if len(examples) < 4:
                for name, op_type in cpu_nodes.items():
                    if name not in expected_names:
                        examples.append("extra:%s:%s" % (name, op_type))
                        if len(examples) >= 4:
                            break
            for name in changed_cpu:
                if len(examples) >= 4:
                    break
                examples.append("op:%s:%s>%s" % (
                    name, expected_cpu_nodes[name], cpu_nodes[name]))
            known_providers = {
                name: providers[name] for name in (
                    "CUDAExecutionProvider", "CPUExecutionProvider")
                if name in providers}
            other_providers = sum(
                count for name, count in providers.items()
                if name not in known_providers)
            if other_providers:
                known_providers["OtherExecutionProviders"] = other_providers
            expected_provider_counts = (
                expected_providers if isinstance(expected_providers, dict) else {})
            session_input_format, optimized_model_output = session_readback_context()
            assignment_diagnostic = {
                "graph": graph_name,
                "trace_enabled": (
                    os.environ.get("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE") == "1"),
                "readback_state": "populated",
                "assignment_rows": len(assignments),
                "session_input_format": session_input_format,
                "optimized_model_output": optimized_model_output,
                "actual_total": total_nodes,
                "expected_total": expected_total,
                "actual_providers": dict(sorted(known_providers.items())),
                "expected_providers": dict(sorted(
                    expected_provider_counts.items())),
                "actual_cpu_nodes": len(cpu_nodes),
                "expected_cpu_nodes": len(expected_cpu_nodes),
                "missing_cpu_nodes": missing_cpu_count,
                "extra_cpu_nodes": extra_cpu_count,
                "changed_cpu_ops": len(changed_cpu),
                "examples": examples,
                "examples_truncated": (
                    missing_cpu_count + extra_cpu_count + len(changed_cpu)
                    > len(examples)),
            }
            error = RuntimeError(
                "Redux acoustic graph has unpinned CPU, unknown, or missing nodes: %s"
                % graph_name)
            if assignment_diagnostic is not None:
                error.sotto_node_assignment_diagnostic = assignment_diagnostic
            raise error
        self.node_assignment_readback[graph_name] = {
            "providers": dict(sorted(providers.items())),
            "cpu_nodes": dict(sorted(cpu_nodes.items())),
            "total_nodes": total_nodes,
            "method": "get_provider_graph_assignment_info",
        }

    @staticmethod
    def _provider_identity(providers):
        normalized = []
        for item in providers or ():
            if isinstance(item, (tuple, list)):
                name = str(item[0])
                options = item[1] if len(item) > 1 and isinstance(item[1], dict) else {}
            else:
                name, options = str(item), {}
            normalized.append({
                "name": name,
                "options": {str(key): str(value)
                            for key, value in sorted(options.items())},
            })
        return normalized

    def _cache_paths(self, graph: Path):
        root = self._model_dir / REDUX_ORT_CACHE_DIR
        stem = graph.stem
        return root / (stem + ".ort"), root / (stem + ".json"), root / (stem + ".lock")

    def _cache_identity(self, graph: Path, sess_options, providers):
        if (not self._optimized_cache or not self._gpu_only
                or graph.name not in REDUX_ORT_CACHE_GRAPHS):
            return None
        control = REDUX_CONTROL_GRAPH_ALLOWLIST.get(graph.name)
        expected_fallback = "0" if control is not None else "1"
        if sess_options.get_session_config_entry(_CPU_FALLBACK_KEY) != expected_fallback:
            return None
        provider_identity = self._provider_identity(providers)
        if [item["name"] for item in provider_identity] != list(CONTROL_GRAPH_PROVIDERS):
            return None
        try:
            source_stat = graph.stat()
        except OSError:
            return None
        optimization = (
            "ORT_DISABLE_ALL" if graph.name in {
                "preprocessor.onnx", "encoder-model.onnx"
            } else getattr(sess_options.graph_optimization_level, "name",
                           str(sess_options.graph_optimization_level))
        )
        identity = {
            "schema": REDUX_ORT_CACHE_SCHEMA,
            "graph": graph.name,
            "source_sha256": control[0],
            "source_bytes": int(source_stat.st_size),
            "source_mtime_ns": int(source_stat.st_mtime_ns),
            "onnxruntime": str(getattr(self._ort, "__version__", "unknown")),
            "providers": provider_identity,
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", ""),
            "host": os.environ.get("COMPUTERNAME", ""),
            "options": {
                "graph_optimization_level": optimization,
                "intra_op_threads": int(sess_options.intra_op_num_threads),
                "inter_op_threads": int(sess_options.inter_op_num_threads),
                "sequential": sess_options.execution_mode
                == self._ort.ExecutionMode.ORT_SEQUENTIAL,
                "cpu_ep_fallback_key": expected_fallback,
                "node_assignment_trace": sess_options.get_session_config_entry(
                    "session.record_ep_graph_assignment_info"),
                "enable_runtime_fallback": False,
                "post_create_disable_fallback": True,
            },
        }
        fingerprint = hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        return identity, fingerprint

    def _cache_candidate(self, graph: Path, sess_options, providers):
        identity_and_key = self._cache_identity(graph, sess_options, providers)
        if identity_and_key is None:
            return None
        identity, fingerprint = identity_and_key
        cache_path, manifest_path, lock_path = self._cache_paths(graph)
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            cache_stat = cache_path.stat()
        except (OSError, ValueError, TypeError):
            return None
        expected_cache_sha = manifest.get("cache_sha256")
        if (manifest.get("identity") != identity
                or manifest.get("fingerprint") != fingerprint
                or not isinstance(expected_cache_sha, str)
                or len(expected_cache_sha) != 64
                or manifest.get("cache_bytes") != cache_stat.st_size
                or manifest.get("cache_mtime_ns") != cache_stat.st_mtime_ns
                or cache_stat.st_size <= 0):
            return None
        return {
            "identity": identity,
            "fingerprint": fingerprint,
            "cache_path": cache_path,
            "manifest_path": manifest_path,
            "lock_path": lock_path,
            "cache_sha256": expected_cache_sha,
        }

    def _publish_ort_cache(self, graph: Path, temp_path: Path,
                           identity, fingerprint):
        cache_path, manifest_path, _lock_path = self._cache_paths(graph)
        if not temp_path.is_file() or temp_path.stat().st_size <= 0:
            return None
        cache_sha256 = _file_sha256(temp_path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(temp_path), str(cache_path))
        cache_stat = cache_path.stat()
        manifest = {
            "schema": REDUX_ORT_CACHE_SCHEMA,
            "identity": identity,
            "fingerprint": fingerprint,
            "cache_sha256": cache_sha256,
            "cache_bytes": int(cache_stat.st_size),
            "cache_mtime_ns": int(cache_stat.st_mtime_ns),
        }
        manifest_tmp = manifest_path.with_name(manifest_path.name + ".tmp")
        manifest_tmp.write_text(json.dumps(
            manifest, sort_keys=True, separators=(",", ":")
        ), encoding="utf-8")
        os.replace(str(manifest_tmp), str(manifest_path))
        return cache_sha256, cache_path.stat().st_size

    @staticmethod
    def _trace_marker(edge: str, graph_name: str, elapsed_ms: int | None = None) -> None:
        if os.environ.get("SOTTO_REDUX_ORT_NODE_TRACE") == "1":
            try:
                suffix = (" elapsed_ms=%d" % max(0, int(elapsed_ms))
                          if elapsed_ms is not None else "")
                os.write(2, ("SOTTO_ORT_GRAPH_%s %s%s\n"
                             % (edge, graph_name, suffix)).encode("ascii"))
            except OSError:
                pass

    @staticmethod
    def _session_failure_marker(edge: str, graph_name: str) -> None:
        """Emit an opt-in graph-basename marker around ORT session creation."""
        if os.environ.get(SESSION_FAILURE_TRACE_ENV) != "1":
            return
        if edge not in {"BEGIN", "FAIL", "END"}:
            return
        basename = Path(graph_name).name
        if basename not in SESSION_FAILURE_TRACE_GRAPHS:
            return
        try:
            os.write(
                2,
                ("SOTTO_REDUX_ORT_SESSION_%s graph=%s\n"
                 % (edge, basename)).encode("ascii"),
            )
        except OSError:
            pass

    @staticmethod
    def _thread_start_modules(tids):
        """Resolve Windows thread start addresses to their owning DLLs (diagnostic only)."""
        if os.name != "nt":
            return {}
        import ctypes
        import ntpath

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
        kernel32.OpenThread.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        kernel32.OpenThread.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_int
        kernel32.GetModuleHandleExW.argtypes = [
            ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)
        ]
        kernel32.GetModuleHandleExW.restype = ctypes.c_int
        kernel32.GetModuleFileNameW.argtypes = [
            ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32
        ]
        kernel32.GetModuleFileNameW.restype = ctypes.c_uint32
        ntdll.NtQueryInformationThread.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.c_void_p
        ]
        ntdll.NtQueryInformationThread.restype = ctypes.c_long
        result = {}
        for tid in tids:
            handle = kernel32.OpenThread(0x0040 | 0x0800, 0, int(tid))
            if not handle:
                result[int(tid)] = "unavailable"
                continue
            try:
                start = ctypes.c_void_p()
                status = ntdll.NtQueryInformationThread(
                    handle, 9, ctypes.byref(start), ctypes.sizeof(start), None
                )
                if status < 0 or not start.value:
                    result[int(tid)] = "unavailable"
                    continue
                module = ctypes.c_void_p()
                if not kernel32.GetModuleHandleExW(
                        0x00000004 | 0x00000002, start, ctypes.byref(module)):
                    result[int(tid)] = "unmapped"
                    continue
                buffer = ctypes.create_unicode_buffer(32768)
                length = kernel32.GetModuleFileNameW(module, buffer, len(buffer))
                result[int(tid)] = (
                    ntpath.basename(buffer.value).lower() if length else "unmapped"
                )
            finally:
                kernel32.CloseHandle(handle)
        return result

    def _trace_thread_census(self, edge: str, graph_name: str,
                             elapsed_ms: int = 0) -> None:
        if os.environ.get("SOTTO_REDUX_ORT_NODE_TRACE") != "1":
            return
        try:
            with self._thread_trace_lock:
                if self._thread_sampler is None:
                    import importlib.util

                    sampler_path = Path(REPO) / "_main" / "shell-thread-cpu.py"
                    spec = importlib.util.spec_from_file_location(
                        "sotto_redux_thread_census", sampler_path)
                    if spec is None or spec.loader is None:
                        raise RuntimeError("named-thread instrument unavailable")
                    self._thread_sampler = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(self._thread_sampler)
                sampler = self._thread_sampler
            # Toolhelp enumeration and module lookup can take long enough to
            # serialize CUDA session creation. Protect only one-time import;
            # snapshots and origin resolution are independent per graph.
            rows = sampler.sample(os.getpid())
            origins = (self._thread_start_modules(rows)
                       if edge == "END" else {})
            encoded = ";".join(
                "%d:%s@%s" % (
                    int(tid), (str(name).strip() or "(unnamed)").replace(" ", "_"),
                    origins.get(int(tid), "not-sampled"),
                )
                for tid, (_cpu_s, name) in sorted(rows.items())
            )
            line = ("SOTTO_ORT_THREADS_%s graph=%s count=%d elapsed_ms=%d tids=%s\n" % (
                edge, graph_name, len(rows), max(0, int(elapsed_ms)), encoded))
        except Exception as exc:  # noqa: BLE001
            line = "SOTTO_ORT_THREADS_ERROR graph=%s error=%s\n" % (
                graph_name, type(exc).__name__)
        try:
            os.write(2, line.encode("ascii", errors="replace"))
        except OSError:
            pass

    def _run_session(self, graph, sess_options, *args, session_path=None,
                     optimized_output=None, verified_bytes=None, **kwargs):
        requested_entries = self._provider_identity(kwargs.get("providers"))
        requested_names = [item["name"] for item in requested_entries]
        is_control_graph = graph.name in REDUX_CONTROL_GRAPH_ALLOWLIST
        expected_names = (list(CONTROL_GRAPH_PROVIDERS) if is_control_graph
                          else ["CUDAExecutionProvider"])
        expected_fallback = "0" if is_control_graph else "1"
        if (requested_names != expected_names
                or sess_options.get_session_config_entry(_CPU_FALLBACK_KEY)
                != expected_fallback):
            raise RuntimeError(
                "Redux graph provider/fallback configuration is not the pinned policy")
        original_optimization = sess_options.graph_optimization_level
        original_optimized_filepath = getattr(
            sess_options, "optimized_model_filepath", "")
        sess_options.logid = graph.name
        if graph.name in {"preprocessor.onnx", "encoder-model.onnx"}:
            # Cold-start experiments showed the preprocessor's full rewrite
            # pass adds startup work without helping the hot decode loop. Keep
            # the decoder optimized for steady-state throughput; disable only
            # these two graph rewrites and measure both readiness and output.
            sess_options.graph_optimization_level = (
                self._ort.GraphOptimizationLevel.ORT_DISABLE_ALL
            )
        try:
            node_assignment_trace = (
                sess_options.get_session_config_entry(
                    "session.record_ep_graph_assignment_info") == "1")
        except Exception:
            node_assignment_trace = False
        self.options_readback[graph.name] = {
            "intra_op_threads": int(sess_options.intra_op_num_threads),
            "inter_op_threads": int(sess_options.inter_op_num_threads),
            "use_per_session_threads": bool(sess_options.use_per_session_threads),
            "execution_mode_sequential": (
                sess_options.execution_mode == self._ort.ExecutionMode.ORT_SEQUENTIAL
            ),
            "intra_op_spinning": sess_options.get_session_config_entry(
                "session.intra_op.allow_spinning"),
            "inter_op_spinning": sess_options.get_session_config_entry(
                "session.inter_op.allow_spinning"),
            "disable_cpu_ep_fallback": sess_options.get_session_config_entry(
                _CPU_FALLBACK_KEY),
            "requested_provider_entries": self._provider_identity(
                kwargs.get("providers")),
            "requested_provider_names": [item["name"] for item in
                                          self._provider_identity(
                                              kwargs.get("providers"))],
            "graph_optimization_level": getattr(
                sess_options.graph_optimization_level, "name",
                str(sess_options.graph_optimization_level)),
            "logid": str(sess_options.logid),
            "session_input_format": (
                "ort" if Path(session_path or graph).suffix.lower() == ".ort"
                else "onnx"),
            "optimized_model_output": bool(optimized_output),
            "node_assignment_trace": node_assignment_trace,
        }
        try:
            if optimized_output is not None:
                sess_options.optimized_model_filepath = str(optimized_output)
            if self._gpu_only:
                # This Python-level switch is separate from
                # session.disable_cpu_ep_fallback. Set it before construction:
                # ORT can otherwise catch a CUDA setup error and retry on CPU.
                kwargs["enable_fallback"] = False
            session = self._ort.InferenceSession(
                str(session_path or graph) if verified_bytes is None else verified_bytes,
                sess_options, *args, **kwargs
            )
            if self._gpu_only:
                disable_fallback = getattr(session, "disable_fallback", None)
                if not callable(disable_fallback):
                    raise RuntimeError(
                        "Redux GPU-only ORT session lacks disable_fallback()"
                    )
                try:
                    disable_fallback()
                except Exception as exc:
                    raise RuntimeError(
                        "Redux GPU-only ORT runtime fallback could not be disabled "
                        "for %s" % graph.name
                    ) from exc
                self.runtime_fallback_readback[graph.name] = True
                self.options_readback[graph.name]["runtime_fallback_disabled"] = True
            assignment_started = time.perf_counter()
            self._read_node_assignment(graph.name, session)
            self.node_assignment_readback_s += time.perf_counter() - assignment_started
            return session
        finally:
            sess_options.graph_optimization_level = original_optimization
            if optimized_output is not None:
                sess_options.optimized_model_filepath = original_optimized_filepath

    def InferenceSession(self, path, sess_options=None, *args, **kwargs):
        graph = Path(path).resolve()
        started = time.perf_counter()
        self._trace_marker("BEGIN", graph.name)
        self._session_failure_marker("BEGIN", graph.name)
        try:
            return self._create_session(
                graph, sess_options, *args, **kwargs
            )
        except Exception:
            self._session_failure_marker("FAIL", graph.name)
            raise
        finally:
            self._session_failure_marker("END", graph.name)
            self._trace_marker(
                "END", graph.name,
                int((time.perf_counter() - started) * 1000),
            )

    def _create_session(self, graph, sess_options=None, *args, **kwargs):
        if sess_options is None:
            raise RuntimeError("Redux GPU-only policy requires explicit SessionOptions")
        if os.environ.get("SOTTO_REDUX_ORT_ASSIGNMENT_TRACE") == "1":
            # Node assignment logs are synchronous and can distort startup
            # measurements. Graph timing markers use a separate, low-cost flag.
            sess_options.log_severity_level = 1
            sess_options.log_verbosity_level = 0
        if not self._gpu_only:
            raise RuntimeError("Redux acoustic sessions require the CUDA provider")
        control_spec = REDUX_CONTROL_GRAPH_ALLOWLIST.get(graph.name)
        expected_path = self._allowlisted_paths.get(graph.name)
        if control_spec is not None and graph != expected_path:
            raise RuntimeError("Redux CPU control exception requires the exact pinned graph path")
        requested = kwargs.get("providers")
        if requested is None:
            raise RuntimeError("Redux graph provider request is missing")
        providers = _graph_provider_entries(graph.name, requested)
        kwargs["providers"] = providers
        expected_fallback = "0" if control_spec is not None else "1"
        if sess_options.get_session_config_entry(_CPU_FALLBACK_KEY) != expected_fallback:
            sess_options.add_session_config_entry(
                _CPU_FALLBACK_KEY, expected_fallback)
        if control_spec is None or graph != expected_path:
            return self._run_session(graph, sess_options, *args, **kwargs)

        expected_sha, _expected_nodes = control_spec
        actual_version = str(getattr(self._ort, "__version__", "unknown"))
        if actual_version != REDUX_PREPROCESSOR_CONTROL_ORT_VERSION:
            raise RuntimeError(
                "Redux graph integrity policy was measured with ORT %s, "
                "not %s" % (REDUX_PREPROCESSOR_CONTROL_ORT_VERSION, actual_version)
            )
        if os.environ.get("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE") == "1":
            # ORT 1.30's ORT-format initialization skips the EP assignment
            # callback. Placement traces must therefore use the pinned source
            # ONNX bytes and must not build/publish an optimized cache either.
            self.session_cache_readback[graph.name] = {
                "mode": "trace-source-bypass",
                "verified_before_session_return": False,
            }
            return self._source_control_session(
                graph, sess_options, expected_sha, None, *args, **kwargs)
        identity_and_key = self._cache_identity(
            graph, sess_options, kwargs.get("providers"))
        if identity_and_key is None:
            return self._source_control_session(
                graph, sess_options, expected_sha, None, *args, **kwargs)
        identity, fingerprint = identity_and_key
        _cache_path, _manifest_path, lock_path = self._cache_paths(graph)
        with _try_exclusive_cache_lock(lock_path) as locked:
            if not locked:
                self.session_cache_readback[graph.name] = {
                    "mode": "lock-busy",
                    "fingerprint": fingerprint,
                    "verified_before_session_return": False,
                }
                return self._source_control_session(
                    graph, sess_options, expected_sha, None, *args, **kwargs)
            candidate = self._cache_candidate(
                graph, sess_options, kwargs.get("providers"))
            if candidate is not None:
                try:
                    return self._cached_control_session(
                        graph, sess_options, candidate, *args, **kwargs)
                except Exception as exc:
                    self._invalidate_cache_candidate(candidate)
                    return self._source_control_session(
                        graph, sess_options, expected_sha,
                        (identity, fingerprint, type(exc).__name__),
                        *args, **kwargs)
            return self._source_control_session(
                graph, sess_options, expected_sha,
                (identity, fingerprint, None), *args, **kwargs)

    @staticmethod
    def _cache_temp_path(cache_path: Path) -> Path:
        return cache_path.with_name(cache_path.stem + ".building.ort")

    @staticmethod
    def _invalidate_cache_candidate(candidate):
        for invalid_path in (candidate["cache_path"], candidate["manifest_path"]):
            try:
                invalid_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _source_control_session(self, graph, sess_options, expected_sha,
                                cache_build, *args, **kwargs):
        hash_future = _submit_control_graph_hash(graph)
        identity = fingerprint = cache_error = None
        temp_path = None
        if cache_build is not None:
            identity, fingerprint, cache_error = cache_build
            cache_path, _manifest_path, _lock_path = self._cache_paths(graph)
            temp_path = self._cache_temp_path(cache_path)
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                temp_path = None
        try:
            session = self._run_session(
                graph, sess_options, *args,
                optimized_output=temp_path if identity is not None else None,
                **kwargs)
            actual_sha, hash_elapsed_s = _resolve_control_graph_hash(hash_future)
            if actual_sha != expected_sha:
                raise RuntimeError(
                    "Redux %s pinned graph hash differs: sha256=%s"
                    % (graph.name, actual_sha)
                )
            self._validated.add(graph.name)
            self.control_hash_readback[graph.name] = {
                "sha256": actual_sha,
                "elapsed_ms": int(hash_elapsed_s * 1000),
                "verified_before_session_return": True,
                "verification": "source-sha256",
            }
            if identity is not None and temp_path is not None:
                try:
                    published = self._publish_ort_cache(
                        graph, temp_path, identity, fingerprint)
                except OSError as exc:
                    published = None
                    cache_error = "%s errno=%s" % (
                        type(exc).__name__, getattr(exc, "errno", None))
                if published is None:
                    self.session_cache_readback[graph.name] = {
                        "mode": "build-unavailable",
                        "fingerprint": fingerprint,
                        "verified_before_session_return": False,
                        "reason": cache_error or "ORT did not write a nonempty cache",
                    }
                else:
                    cache_sha256, cache_bytes = published
                    self.session_cache_readback[graph.name] = {
                        "mode": "built",
                        "fingerprint": fingerprint,
                        "cache_sha256": cache_sha256,
                        "cache_bytes": cache_bytes,
                        "verified_before_session_return": True,
                    }
                    self.control_hash_readback[graph.name][
                        "cache_sha256"] = cache_sha256
            elif identity is not None:
                self.session_cache_readback[graph.name] = {
                    "mode": "build-unavailable",
                    "fingerprint": fingerprint,
                    "verified_before_session_return": False,
                    "reason": cache_error or "unable to prepare cache temporary file",
                }
            return session
        except BaseException:
            cancel = getattr(hash_future, "cancel", None)
            if callable(cancel):
                cancel()
            raise
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _cached_control_session(self, graph, sess_options, candidate,
                                *args, **kwargs):
        cache_path = candidate["cache_path"]
        if graph.name == "preprocessor.onnx":
            cache_sha, before_s = _timed_control_graph_hash(cache_path)
            if cache_sha != candidate["cache_sha256"]:
                raise RuntimeError("optimized ORT cache digest changed before load")
            session = self._run_session(
                graph, sess_options, *args, session_path=cache_path, **kwargs)
            actual_sha, after_s = _timed_control_graph_hash(cache_path)
            return self._accept_cached_session(
                graph, sess_options, candidate, session, actual_sha, before_s + after_s,
                kwargs.get("providers"))
        hash_future = _submit_control_graph_hash(cache_path)
        try:
            session = self._run_session(
                graph, sess_options, *args, session_path=cache_path, **kwargs)
            actual_sha, hash_elapsed_s = _resolve_control_graph_hash(hash_future)
            return self._accept_cached_session(
                graph, sess_options, candidate, session, actual_sha, hash_elapsed_s,
                kwargs.get("providers"))
        except BaseException:
            cancel = getattr(hash_future, "cancel", None)
            if callable(cancel):
                cancel()
            raise

    def _accept_cached_session(self, graph, sess_options, candidate, session,
                               actual_sha, hash_elapsed_s, providers):
        if actual_sha != candidate["cache_sha256"]:
            raise RuntimeError("optimized ORT cache digest changed")
        current = self._cache_identity(graph, sess_options, providers)
        if current != (candidate["identity"], candidate["fingerprint"]):
            raise RuntimeError("optimized ORT cache source identity changed during load")
        self._validated.add(graph.name)
        self.session_cache_readback[graph.name] = {
            "mode": "hit",
            "fingerprint": candidate["fingerprint"],
            "cache_sha256": actual_sha,
            "cache_bytes": candidate["cache_path"].stat().st_size,
            "verified_before_session_return": True,
        }
        self.control_hash_readback[graph.name] = {
            "sha256": candidate["identity"]["source_sha256"],
            "elapsed_ms": int(hash_elapsed_s * 1000),
            "verified_before_session_return": True,
            "verification": "source-stat-and-ort-cache-sha256",
            "cache_sha256": actual_sha,
        }
        return session

    def load_preflight_cache_pair(self, make_options, providers, load_all):
        """Test both byte-pinned caches before starting any core session."""
        if os.environ.get("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE") == "1":
            return None
        if str(self._ort.__version__) != REDUX_PREPROCESSOR_CONTROL_ORT_VERSION:
            return None
        staged = {}
        timings = {}
        staged_bytes = 0
        with ExitStack() as locks:
            for name in ("preprocessor.onnx", "encoder-model.onnx"):
                graph = self._allowlisted_paths[name]
                options = make_options(name)
                if options.get_session_config_entry(_CPU_FALLBACK_KEY) != "0":
                    options.add_session_config_entry(_CPU_FALLBACK_KEY, "0")
                graph_providers = _graph_provider_entries(name, providers)
                started = time.perf_counter()
                if not locks.enter_context(_try_exclusive_cache_lock(self._cache_paths(graph)[2])):
                    return None
                lock_s = time.perf_counter() - started
                candidate = self._cache_candidate(graph, options, graph_providers)
                if candidate is None:
                    return None
                path = candidate["cache_path"]
                read_started = time.perf_counter()
                size = path.stat().st_size
                if not 0 < size <= 343_000_000 - staged_bytes:
                    raise RuntimeError("optimized ORT cache is out of byte budget: %s" % name)
                with path.open("rb") as stream:
                    data = stream.read(size + 1)
                read_s = time.perf_counter() - read_started
                hash_started = time.perf_counter()
                if (len(data) != size
                        or hashlib.sha256(data).hexdigest() != candidate["cache_sha256"]):
                    self._invalidate_cache_candidate(candidate)
                    return None
                if data[4:8] != b"ORTM":
                    self._invalidate_cache_candidate(candidate)
                    return None
                timings[name] = {"cache_bytes": len(data), "lock_s": lock_s,
                                 "pre_read_s": read_s, "pre_hash_s": time.perf_counter() - hash_started}
                staged[name] = (graph, options, candidate, data)
                staged_bytes += len(data)

            def load_verified(name, graph_providers=None):
                graph, options, candidate, data = staged[name]
                if graph_providers is None:
                    graph_providers = _graph_provider_entries(name, providers)
                started = time.perf_counter()
                timings[name]["session_queue_s"] = started - submit_started
                self._trace_marker("BEGIN", name)
                try:
                    return self._run_session(graph, options, session_path=candidate["cache_path"],
                                             verified_bytes=data, providers=graph_providers,
                                             enable_fallback=False)
                finally:
                    elapsed_s = time.perf_counter() - started
                    timings[name]["session_s"] = elapsed_s
                    self._trace_marker("END", name, int(elapsed_s * 1000))

            submit_started = time.perf_counter()
            loaded = load_all(load_verified)
            for name, (graph, options, candidate, verified_bytes) in staged.items():
                try:
                    if candidate["cache_path"].stat().st_size != len(verified_bytes):
                        raise RuntimeError("optimized ORT cache size changed during load")
                    actual_sha, post_s = _timed_control_graph_hash(candidate["cache_path"])
                    self._accept_cached_session(graph, options, candidate, loaded[name], actual_sha,
                                                post_s,
                                                _graph_provider_entries(name, providers))
                except Exception:
                    loaded.clear()
                    self._invalidate_cache_candidate(candidate)
                    raise
                timings[name]["postcheck_s"] = post_s
                self.session_cache_readback[name]["preflight_timings"] = timings[name]
            return loaded


def _control_policy_selftest() -> int:
    """Model-free positive, refusal, and restoration checks for the policy."""

    import onnxruntime as ort

    class FakeSessionOptions:
        def __init__(self):
            self.intra_op_num_threads = 0
            self.inter_op_num_threads = 0
            self.execution_mode = ort.ExecutionMode.ORT_PARALLEL
            self.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self.use_per_session_threads = True
            self.log_severity_level = 2
            self.log_verbosity_level = 0
            self.optimized_model_filepath = ""
            self._config = {}

        def add_session_config_entry(self, key, value):
            self._config[key] = str(value)

        def get_session_config_entry(self, key):
            return self._config.get(key, "")

    class FakeNode:
        def __init__(self, name, op_type):
            self.name = name
            self.op_type = op_type

    class FakeSubgraph:
        def __init__(self, ep_name, nodes):
            self.ep_name = ep_name
            self._nodes = nodes

        def get_nodes(self):
            return list(self._nodes)

    class FakeSession:
        def __init__(self, owner, graph_name):
            self.owner = owner
            self.graph_name = graph_name
            self.runtime_fallback_disabled = False

        def disable_fallback(self):
            self.owner.disable_calls += 1
            self.runtime_fallback_disabled = True

        def get_providers(self):
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]

        def get_inputs(self):
            return []

        def get_provider_graph_assignment_info(self):
            return self.owner.assignment_for(self.graph_name)

        def run(self, *_args, **_kwargs):
            if self.owner.run_fail:
                if not self.runtime_fallback_disabled:
                    self.owner.cpu_run_retries += 1
                    return None
                raise RuntimeError("injected CUDA run failure")
            return None

    class FakeOrt:
        def __init__(self):
            self.calls = []
            self.provider_calls = []
            self.paths = []
            self.log_settings = []
            self.runtime_calls = []
            self.sessions = []
            self.disable_calls = 0
            self.cpu_run_retries = 0
            self.run_fail = False
            self.fail = False
            self.on_session = None
            self.assignment_override = {}

        def SessionOptions(self):
            return FakeSessionOptions()

        def __getattr__(self, name):
            return getattr(ort, name)

        def assignment_for(self, graph_name):
            if graph_name in self.assignment_override:
                return self.assignment_override[graph_name]
            expected = REDUX_GRAPH_NODE_COUNTS[graph_name]
            cpu_nodes = REDUX_CONTROL_GRAPH_ALLOWLIST.get(graph_name, (None, {}))[1]
            cuda_count = expected - len(cpu_nodes)
            rows = [FakeSubgraph(
                "CUDAExecutionProvider",
                [FakeNode("cuda_%s_%d" % (graph_name, index), "Identity")
                 for index in range(cuda_count)],
            )]
            if cpu_nodes:
                rows.append(FakeSubgraph(
                    "CPUExecutionProvider",
                    [FakeNode(name, op_type)
                     for name, op_type in sorted(cpu_nodes.items())],
                ))
            return rows

        def InferenceSession(self, path, sess_options=None, *args, **kwargs):
            value = sess_options.get_session_config_entry(_CPU_FALLBACK_KEY)
            name = (str(sess_options.logid)
                    if isinstance(path, bytes) or Path(path).suffix.lower() == ".ort"
                    else Path(path).name)
            self.calls.append((name, value, isinstance(path, bytes)))
            self.provider_calls.append((name, [item[0] if isinstance(item, tuple)
                                               else item for item in
                                               kwargs.get("providers", [])]))
            self.runtime_calls.append((name, kwargs.get("enable_fallback", None)))
            self.paths.append(str(path))
            self.log_settings.append((
                name, sess_options.log_severity_level, sess_options.log_verbosity_level
            ))
            optimized_path = str(getattr(sess_options, "optimized_model_filepath", "") or "")
            if optimized_path:
                Path(optimized_path).write_bytes(
                    b"\x14\0\0\0ORTM" + Path(path).name.encode("ascii"))
            if self.on_session is not None:
                self.on_session(path)
            if self.fail:
                raise RuntimeError("injected session creation failure")
            session = FakeSession(self, name)
            self.sessions.append(session)
            return session

    fake = FakeOrt()
    proxy = _ReduxControlOnlyOrtProxy(
        fake, Path(DEFAULT_ONNX_DIR), optimized_cache=False)
    preprocessor = Path(DEFAULT_ONNX_DIR) / "preprocessor.onnx"
    encoder = Path(DEFAULT_ONNX_DIR) / "encoder-model.onnx"
    decoder = Path(DEFAULT_ONNX_DIR) / "decoder_joint-model.onnx"
    vad = Path(DEFAULT_ONNX_DIR) / "vad-model.onnx"
    original_hash = _file_sha256
    control_hashes = {name: spec[0]
                      for name, spec in REDUX_CONTROL_GRAPH_ALLOWLIST.items()}

    def selftest_hash(path):
        if Path(path).name in control_hashes:
            return control_hashes[Path(path).name]
        return original_hash(path)

    def strict_options(owner):
        options = owner.SessionOptions()
        options.intra_op_num_threads = 1
        options.use_per_session_threads = False
        options.add_session_config_entry(_CPU_FALLBACK_KEY, "1")
        return options

    globals()["_file_sha256"] = selftest_hash
    try:
        real_options = ort.SessionOptions()
        real_options.inter_op_num_threads = 1
        real_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        real_options.use_per_session_threads = False
        real_options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        real_options.add_session_config_entry("session.inter_op.allow_spinning", "0")
        real_options.add_session_config_entry(_CPU_FALLBACK_KEY, "1")
        if (real_options.inter_op_num_threads != 1
                or real_options.execution_mode != ort.ExecutionMode.ORT_SEQUENTIAL
                or real_options.use_per_session_threads is not False
                or real_options.get_session_config_entry(
                    "session.intra_op.allow_spinning") != "0"
                or real_options.get_session_config_entry(
                    "session.inter_op.allow_spinning") != "0"
                or real_options.get_session_config_entry(_CPU_FALLBACK_KEY) != "1"):
            raise AssertionError("installed ORT SessionOptions API did not retain settings")
        opts = strict_options(proxy)
        prior_failure_trace = os.environ.get(SESSION_FAILURE_TRACE_ENV)
        prior_node_trace = os.environ.pop("SOTTO_REDUX_ORT_NODE_TRACE", None)
        prior_assignment_trace = os.environ.pop(
            "SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE", None)
        original_os_write = os.write
        session_markers = []

        def capture_session_marker(fd, payload):
            if fd == 2 and payload.startswith(b"SOTTO_REDUX_ORT_SESSION_"):
                session_markers.append(payload.decode("ascii"))
                return len(payload)
            return original_os_write(fd, payload)

        os.environ[SESSION_FAILURE_TRACE_ENV] = "1"
        os.write = capture_session_marker
        try:
            proxy.InferenceSession(preprocessor, opts, providers=["CUDAExecutionProvider"])
            proxy.InferenceSession(encoder, opts, providers=["CUDAExecutionProvider"])
            proxy.InferenceSession(decoder, opts, providers=["CUDAExecutionProvider"])
            proxy.InferenceSession(vad, opts, providers=["CUDAExecutionProvider"])
            expected_markers = [
                "SOTTO_REDUX_ORT_SESSION_BEGIN graph=preprocessor.onnx\n",
                "SOTTO_REDUX_ORT_SESSION_END graph=preprocessor.onnx\n",
                "SOTTO_REDUX_ORT_SESSION_BEGIN graph=encoder-model.onnx\n",
                "SOTTO_REDUX_ORT_SESSION_END graph=encoder-model.onnx\n",
                "SOTTO_REDUX_ORT_SESSION_BEGIN graph=decoder_joint-model.onnx\n",
                "SOTTO_REDUX_ORT_SESSION_END graph=decoder_joint-model.onnx\n",
                "SOTTO_REDUX_ORT_SESSION_BEGIN graph=vad-model.onnx\n",
                "SOTTO_REDUX_ORT_SESSION_END graph=vad-model.onnx\n",
            ]
            if session_markers != expected_markers:
                raise AssertionError(
                    "successful ORT session markers leaked a path or missed a graph"
                )
            proxy._session_failure_marker("BEGIN", "private.onnx")
            proxy._session_failure_marker("BEGIN", ("x" * 1024) + ".onnx")
            if session_markers != expected_markers:
                raise AssertionError(
                    "unknown ORT graph name escaped the bounded marker allowlist"
                )
            if opts.get_session_config_entry(_CPU_FALLBACK_KEY) != "0":
                raise AssertionError("pinned control graph CPU provider config changed")
            if fake.calls != [("preprocessor.onnx", "0", False),
                              ("encoder-model.onnx", "0", False),
                              ("decoder_joint-model.onnx", "1", False),
                              ("vad-model.onnx", "0", False)]:
                raise AssertionError("graph path/hash or per-graph CPU policy differs")
            if fake.provider_calls != [
                    ("preprocessor.onnx", list(CONTROL_GRAPH_PROVIDERS)),
                    ("encoder-model.onnx", list(CONTROL_GRAPH_PROVIDERS)),
                    ("decoder_joint-model.onnx", ["CUDAExecutionProvider"]),
                    ("vad-model.onnx", list(CONTROL_GRAPH_PROVIDERS))]:
                raise AssertionError("CPU EP was not requested only for pinned control graphs")
            if (fake.runtime_calls != [(name, False) for name, *_ in fake.calls]
                    or fake.disable_calls != len(fake.calls)
                    or len(proxy.runtime_fallback_readback) != len(fake.calls)
                    or any(row.get("runtime_fallback_disabled") is not True
                           for row in proxy.options_readback.values())):
                raise AssertionError(
                    "GPU sessions did not disable constructor and run-time fallback"
                )

            os.environ.pop(SESSION_FAILURE_TRACE_ENV, None)
            proxy.InferenceSession(
                decoder, strict_options(proxy),
                providers=["CUDAExecutionProvider"])
            if session_markers != expected_markers:
                raise AssertionError("ORT session marker emitted without opt-in")
            os.environ[SESSION_FAILURE_TRACE_ENV] = "1"

            fake.fail = True
            try:
                proxy.InferenceSession(
                    encoder, strict_options(proxy),
                    providers=["CUDAExecutionProvider"])
            except RuntimeError as exc:
                if str(exc) != "injected session creation failure":
                    raise
            else:
                raise AssertionError("injected ORT session creation failure did not propagate")
            fake.fail = False
            expected_markers.extend([
                "SOTTO_REDUX_ORT_SESSION_BEGIN graph=encoder-model.onnx\n",
                "SOTTO_REDUX_ORT_SESSION_FAIL graph=encoder-model.onnx\n",
                "SOTTO_REDUX_ORT_SESSION_END graph=encoder-model.onnx\n",
            ])
            if session_markers != expected_markers:
                raise AssertionError(
                    "failed ORT session markers contain data beyond the graph basename"
                )
        finally:
            os.write = original_os_write
            if prior_failure_trace is None:
                os.environ.pop(SESSION_FAILURE_TRACE_ENV, None)
            else:
                os.environ[SESSION_FAILURE_TRACE_ENV] = prior_failure_trace
            if prior_node_trace is not None:
                os.environ["SOTTO_REDUX_ORT_NODE_TRACE"] = prior_node_trace
            if prior_assignment_trace is not None:
                os.environ["SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"] = (
                    prior_assignment_trace)
        fake.run_fail = True
        for session in fake.sessions:
            try:
                session.run(None, {})
            except RuntimeError as exc:
                if str(exc) != "injected CUDA run failure":
                    raise
            else:
                raise AssertionError("injected GPU run failure did not propagate")
        if fake.cpu_run_retries:
            raise AssertionError("GPU run failure retried through the CPU EP")
        fake.run_fail = False
        if (set(proxy.control_hash_readback) != set(control_hashes)
                or any(row.get("verified_before_session_return") is not True
                       or len(row.get("sha256", "")) != 64
                       for row in proxy.control_hash_readback.values())):
            raise AssertionError("control graph hashes were not verified before return")
        prior_assignment_trace = os.environ.get("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE")
        os.environ["SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"] = "1"
        try:
            for session in fake.sessions[:4]:
                proxy._read_node_assignment(session.graph_name, session)
            if set(proxy.node_assignment_readback) != {
                    "preprocessor.onnx", "encoder-model.onnx",
                    "decoder_joint-model.onnx", "vad-model.onnx"}:
                raise AssertionError("synthetic exact control-node maps were not accepted")

            def must_refuse_assignment(graph_name, rows, readback=None):
                bad_fake = FakeOrt()
                bad_fake.assignment_override[graph_name] = rows
                bad_proxy = _ReduxControlOnlyOrtProxy(
                    bad_fake, Path(DEFAULT_ONNX_DIR), optimized_cache=False)
                bad_proxy.options_readback[graph_name] = {
                    "session_input_format": "onnx",
                    "optimized_model_output": False,
                }
                if readback is not None:
                    bad_proxy.options_readback[graph_name] = readback
                try:
                    bad_proxy._read_node_assignment(
                        graph_name, FakeSession(bad_fake, graph_name))
                except RuntimeError as exc:
                    return getattr(
                        exc, "sotto_node_assignment_diagnostic", None)
                raise AssertionError("invalid provider/node map passed: %s" % graph_name)

            encoder_rows = fake.assignment_for("encoder-model.onnx")
            cuda_row, cpu_row = encoder_rows
            extra_cpu_diagnostic = must_refuse_assignment(
                "encoder-model.onnx", encoder_rows + [
                FakeSubgraph("CPUExecutionProvider", [FakeNode("added_cpu", "Add")])])
            if (not isinstance(extra_cpu_diagnostic, dict)
                    or extra_cpu_diagnostic.get("graph") != "encoder-model.onnx"
                    or extra_cpu_diagnostic.get("trace_enabled") is not True
                    or extra_cpu_diagnostic.get("readback_state") != "populated"
                    or extra_cpu_diagnostic.get("assignment_rows")
                    != len(encoder_rows) + 1
                    or extra_cpu_diagnostic.get("actual_total")
                    != REDUX_GRAPH_NODE_COUNTS["encoder-model.onnx"] + 1
                    or extra_cpu_diagnostic.get("extra_cpu_nodes") != 1
                    or extra_cpu_diagnostic.get("examples")
                    != ["extra:added_cpu:Add"]):
                raise AssertionError(
                    "bounded placement refusal detail was not attached to its exception")
            empty_readback_diagnostic = must_refuse_assignment(
                "preprocessor.onnx", [], {
                    "session_input_format": "ort",
                    "optimized_model_output": False,
                })
            if (not isinstance(empty_readback_diagnostic, dict)
                    or empty_readback_diagnostic.get("readback_state") != "empty"
                    or empty_readback_diagnostic.get("assignment_rows") != 0
                    or empty_readback_diagnostic.get("session_input_format") != "ort"
                    or empty_readback_diagnostic.get("optimized_model_output") is not False
                    or empty_readback_diagnostic.get("actual_total") is not None):
                raise AssertionError(
                    "empty assignment readback lost its bounded source-format detail")
            prior_assignment_trace = os.environ.pop(
                "SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE", None)
            try:
                no_trace_diagnostic = must_refuse_assignment(
                    "encoder-model.onnx", encoder_rows + [
                        FakeSubgraph(
                            "CPUExecutionProvider",
                            [FakeNode("added_cpu", "Add")])])
                if (not isinstance(no_trace_diagnostic, dict)
                        or no_trace_diagnostic.get("trace_enabled") is not False
                        or no_trace_diagnostic.get("extra_cpu_nodes") != 1):
                    raise AssertionError(
                        "placement refusal detail depended on the trace flag")
            finally:
                os.environ["SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"] = "1"
            substituted = [FakeSubgraph(cuda_row.ep_name, cuda_row.get_nodes()),
                           FakeSubgraph(cpu_row.ep_name, [
                               FakeNode("substituted_cpu", node.op_type)
                               for node in cpu_row.get_nodes()])]
            must_refuse_assignment("encoder-model.onnx", substituted)
            changed_op = [FakeSubgraph(cuda_row.ep_name, cuda_row.get_nodes()),
                          FakeSubgraph(cpu_row.ep_name, [
                              FakeNode(node.name,
                                       "Identity" if index == 0 else node.op_type)
                              for index, node in enumerate(cpu_row.get_nodes())])]
            must_refuse_assignment("encoder-model.onnx", changed_op)
            must_refuse_assignment("encoder-model.onnx", [])
            decoder_cuda = fake.assignment_for("decoder_joint-model.onnx")[0]
            must_refuse_assignment("decoder_joint-model.onnx", [
                FakeSubgraph("CUDAExecutionProvider", decoder_cuda.get_nodes()[:-1]),
                FakeSubgraph("CPUExecutionProvider", [FakeNode("decoder_cpu", "Add")]),
            ])
        finally:
            if prior_assignment_trace is None:
                os.environ.pop("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE", None)
            else:
                os.environ["SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"] = (
                    prior_assignment_trace)
        if set(proxy.options_readback) != {name for name, *_ in fake.calls}:
            raise AssertionError("per-graph SessionOptions readback was incomplete")
        for row in proxy.options_readback.values():
            if (row["intra_op_threads"] != 1 or row["inter_op_threads"] != 1
                    or row["use_per_session_threads"] is not False
                    or row["execution_mode_sequential"] is not True
                    or row["intra_op_spinning"] != "0"
                    or row["inter_op_spinning"] != "0"):
                raise AssertionError("bounded ORT SessionOptions did not read back")
        expected_optimization = {
            "preprocessor.onnx": "ORT_DISABLE_ALL",
            "encoder-model.onnx": "ORT_DISABLE_ALL",
            "decoder_joint-model.onnx": "ORT_ENABLE_ALL",
            "vad-model.onnx": "ORT_ENABLE_ALL",
        }
        if {name: row["graph_optimization_level"]
                for name, row in proxy.options_readback.items()} != expected_optimization:
            raise AssertionError("per-graph ORT optimization levels differ")
        if opts.graph_optimization_level != ort.GraphOptimizationLevel.ORT_ENABLE_ALL:
            raise AssertionError("encoder optimization override was not restored")

        prior_node_trace = os.environ.get("SOTTO_REDUX_ORT_NODE_TRACE")
        prior_assignment_trace = os.environ.get("SOTTO_REDUX_ORT_ASSIGNMENT_TRACE")
        try:
            os.environ["SOTTO_REDUX_ORT_NODE_TRACE"] = "1"
            os.environ.pop("SOTTO_REDUX_ORT_ASSIGNMENT_TRACE", None)
            diagnostic_fake = FakeOrt()
            diagnostic_proxy = _ReduxControlOnlyOrtProxy(
                diagnostic_fake, Path(DEFAULT_ONNX_DIR), optimized_cache=False
            )
            diagnostic_proxy._create_session(
                decoder, strict_options(diagnostic_proxy),
                providers=["CUDAExecutionProvider"]
            )
            if diagnostic_fake.log_settings != [("decoder_joint-model.onnx", 2, 0)]:
                raise AssertionError(
                    "graph timing markers unexpectedly enabled synchronous ORT INFO logs"
                )
            os.environ["SOTTO_REDUX_ORT_ASSIGNMENT_TRACE"] = "1"
            diagnostic_proxy._create_session(
                decoder, strict_options(diagnostic_proxy),
                providers=["CUDAExecutionProvider"]
            )
            if diagnostic_fake.log_settings[-1] != ("decoder_joint-model.onnx", 1, 0):
                raise AssertionError("explicit node-assignment trace did not enable ORT INFO logs")
        finally:
            if prior_node_trace is None:
                os.environ.pop("SOTTO_REDUX_ORT_NODE_TRACE", None)
            else:
                os.environ["SOTTO_REDUX_ORT_NODE_TRACE"] = prior_node_trace
            if prior_assignment_trace is None:
                os.environ.pop("SOTTO_REDUX_ORT_ASSIGNMENT_TRACE", None)
            else:
                os.environ["SOTTO_REDUX_ORT_ASSIGNMENT_TRACE"] = prior_assignment_trace

        strict_opts = strict_options(proxy)
        try:
            proxy.InferenceSession(decoder, strict_opts,
                                  providers=["CUDAExecutionProvider",
                                             "CPUExecutionProvider"])
        except RuntimeError as exc:
            if "pinned route" not in str(exc):
                raise
        else:
            raise AssertionError("neural graph accepted explicit CPU EP placement")

        original_allowlist = REDUX_CONTROL_GRAPH_ALLOWLIST
        try:
            altered = dict(original_allowlist)
            altered["preprocessor.onnx"] = ("0" * 64,
                                            original_allowlist["preprocessor.onnx"][1])
            globals()["REDUX_CONTROL_GRAPH_ALLOWLIST"] = altered
            wrong_pre = _ReduxControlOnlyOrtProxy(
                fake, Path(DEFAULT_ONNX_DIR), optimized_cache=False)
            try:
                wrong_pre.InferenceSession(
                    preprocessor, strict_options(wrong_pre),
                    providers=["CUDAExecutionProvider"])
            except RuntimeError as exc:
                if "pinned graph hash differs" not in str(exc):
                    raise
            else:
                raise AssertionError("unrecognized preprocessor graph passed hash guard")
        finally:
            globals()["REDUX_CONTROL_GRAPH_ALLOWLIST"] = original_allowlist

        original_allowlist = REDUX_CONTROL_GRAPH_ALLOWLIST
        try:
            altered = dict(original_allowlist)
            altered["vad-model.onnx"] = ("0" * 64,
                                         original_allowlist["vad-model.onnx"][1])
            globals()["REDUX_CONTROL_GRAPH_ALLOWLIST"] = altered
            wrong_vad = _ReduxControlOnlyOrtProxy(
                fake, Path(DEFAULT_ONNX_DIR), optimized_cache=False)
            try:
                wrong_vad.InferenceSession(
                    vad, strict_options(wrong_vad),
                    providers=["CUDAExecutionProvider"])
            except RuntimeError as exc:
                if "pinned graph hash differs" not in str(exc):
                    raise
            else:
                raise AssertionError("unrecognized VAD graph passed hash guard")
        finally:
            globals()["REDUX_CONTROL_GRAPH_ALLOWLIST"] = original_allowlist

        original_allowlist = REDUX_CONTROL_GRAPH_ALLOWLIST
        try:
            altered = dict(original_allowlist)
            altered["encoder-model.onnx"] = ("0" * 64,
                                             original_allowlist["encoder-model.onnx"][1])
            globals()["REDUX_CONTROL_GRAPH_ALLOWLIST"] = altered
            wrong_encoder = _ReduxControlOnlyOrtProxy(
                fake, Path(DEFAULT_ONNX_DIR), optimized_cache=False)
            try:
                wrong_encoder.InferenceSession(
                    encoder, strict_options(wrong_encoder),
                    providers=["CUDAExecutionProvider"])
            except RuntimeError as exc:
                if "pinned graph hash differs" not in str(exc):
                    raise
            else:
                raise AssertionError("unrecognized encoder graph passed hash guard")
        finally:
            globals()["REDUX_CONTROL_GRAPH_ALLOWLIST"] = original_allowlist

        original_version = fake.__version__
        try:
            fake.__version__ = "0.0-test"
            wrong_runtime = _ReduxControlOnlyOrtProxy(
                fake, Path(DEFAULT_ONNX_DIR), optimized_cache=False)
            try:
                wrong_runtime.InferenceSession(
                    preprocessor, strict_options(wrong_runtime),
                    providers=["CUDAExecutionProvider"])
            except RuntimeError as exc:
                if "measured with ORT" not in str(exc):
                    raise
            else:
                raise AssertionError("unmeasured ORT runtime passed graph guard")
        finally:
            fake.__version__ = original_version

        fake.fail = True
        try:
            fail_opts = strict_options(proxy)
            proxy.InferenceSession(preprocessor, fail_opts,
                                   providers=["CUDAExecutionProvider"])
        except RuntimeError as exc:
            if str(exc) != "injected session creation failure":
                raise
        else:
            raise AssertionError("injected ORT session failure was not propagated")
        if fail_opts.get_session_config_entry(_CPU_FALLBACK_KEY) != "0":
            raise AssertionError("pinned control graph CPU provider config changed after failure")

        hash_started = threading.Event()
        hash_finished = threading.Event()
        hash_release = threading.Event()
        session_started = threading.Event()
        call_finished = threading.Event()
        overlap_fake = FakeOrt()
        overlap_fake.on_session = lambda _path: session_started.set()
        overlap_proxy = _ReduxControlOnlyOrtProxy(
            overlap_fake, Path(DEFAULT_ONNX_DIR), optimized_cache=False
        )
        overlap_result = []
        overlap_error = []

        def slow_encoder_hash(path):
            if Path(path).name != "encoder-model.onnx":
                return selftest_hash(path)
            hash_started.set()
            if not hash_release.wait(timeout=4):
                raise RuntimeError("overlap selftest did not release the hash")
            hash_finished.set()
            return control_hashes["encoder-model.onnx"]

        def load_encoder_for_overlap():
            try:
                overlap_result.append(overlap_proxy.InferenceSession(
                    encoder, strict_options(overlap_proxy),
                    providers=["CUDAExecutionProvider"]))
            except BaseException as exc:  # noqa: BLE001
                overlap_error.append(exc)
            finally:
                call_finished.set()

        globals()["_file_sha256"] = slow_encoder_hash
        overlap_thread = threading.Thread(
            target=load_encoder_for_overlap,
            name="redux-hash-overlap-selftest", daemon=True)
        overlap_thread.start()
        hash_observed = hash_started.wait(timeout=2)
        session_during_hash = (
            session_started.wait(timeout=2) and not hash_finished.is_set()
        )
        blocked_until_hash = not call_finished.is_set()
        hash_release.set()
        overlap_thread.join(timeout=4)
        globals()["_file_sha256"] = selftest_hash
        if (not hash_observed or not session_during_hash or not blocked_until_hash
                or overlap_thread.is_alive() or overlap_error or len(overlap_result) != 1):
            raise AssertionError(
                "integrity hash must overlap session construction and gate session return"
            )

        import tempfile
        with tempfile.TemporaryDirectory(
                prefix="redux-ort-cache-selftest-",
                dir=Path(REPO) / ".agent-work") as root:
            cache_test_trace_mode = os.environ.pop(
                "SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE", None)
            cache_root = Path(root)
            cache_graph = cache_root / "preprocessor.onnx"
            cache_graph.write_bytes(b"model-source")
            cache_fake = FakeOrt()
            cache_proxy = _ReduxControlOnlyOrtProxy(cache_fake, cache_root)
            cache_proxy.InferenceSession(
                cache_graph, strict_options(cache_proxy),
                providers=["CUDAExecutionProvider"])
            built = cache_proxy.session_cache_readback.get("preprocessor.onnx", {})
            if built.get("mode") != "built" or not built.get(
                    "verified_before_session_return"):
                raise AssertionError(
                    "CUDA source session did not publish a verified ORT cache: "
                    "mode=%s reason=%s" % (
                        built.get("mode", "missing"),
                        built.get("reason", "none")))
            cache_path, _manifest_path, _lock_path = cache_proxy._cache_paths(cache_graph)
            if not cache_path.is_file() or cache_fake.paths != [str(cache_graph)]:
                raise AssertionError("ORT cache build did not use the pinned ONNX source")

            prior_trace_mode = os.environ.get(
                "SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE")
            try:
                for trace_value in (None, "0", "other"):
                    if trace_value is None:
                        os.environ.pop("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE", None)
                    else:
                        os.environ["SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"] = trace_value
                    hit_fake = FakeOrt()
                    hit_proxy = _ReduxControlOnlyOrtProxy(hit_fake, cache_root)
                    hit_proxy.InferenceSession(
                        cache_graph, strict_options(hit_proxy),
                        providers=["CUDAExecutionProvider"])
                    hit = hit_proxy.session_cache_readback.get(
                        "preprocessor.onnx", {})
                    if (hit.get("mode") != "hit"
                            or hit_fake.paths != [str(cache_path)]
                            or not hit.get("verified_before_session_return")):
                        raise AssertionError(
                            "trace value %r changed normal CUDA ORT cache hit" % trace_value)
            finally:
                if prior_trace_mode is None:
                    os.environ.pop("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE", None)
                else:
                    os.environ["SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"] = prior_trace_mode

            prior_trace_mode = os.environ.get(
                "SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE")
            try:
                os.environ["SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"] = "1"
                trace_fake = FakeOrt()
                trace_proxy = _ReduxControlOnlyOrtProxy(
                    trace_fake, Path(DEFAULT_ONNX_DIR))
                trace_source = trace_proxy._allowlisted_paths["preprocessor.onnx"]
                trace_session = trace_proxy.InferenceSession(
                    trace_source, strict_options(trace_proxy),
                    providers=["CUDAExecutionProvider"])
                trace_hash = trace_proxy.control_hash_readback.get(
                    "preprocessor.onnx", {})
                trace_map = trace_proxy.node_assignment_readback.get(
                    "preprocessor.onnx", {})
                trace_options = trace_proxy.options_readback.get(
                    "preprocessor.onnx", {})
                if (trace_fake.paths != [str(trace_source)]
                        or not trace_session
                        or trace_options.get("session_input_format") != "onnx"
                        or trace_options.get("optimized_model_output") is not False
                        or trace_hash.get("verified_before_session_return") is not True
                        or trace_hash.get("sha256") != control_hashes["preprocessor.onnx"]
                        or not trace_map):
                    raise AssertionError(
                        "trace placement session did not verify source ONNX/hash/node map")
                pair_fake_trace = FakeOrt()
                pair_trace = _ReduxControlOnlyOrtProxy(pair_fake_trace, cache_root)
                pair_load_calls = []
                if pair_trace.load_preflight_cache_pair(
                        lambda _: strict_options(pair_trace),
                        ["CUDAExecutionProvider"],
                        lambda _loader: pair_load_calls.append(True)) is not None:
                    raise AssertionError("trace mode returned a preflight cache pair")
                if pair_fake_trace.paths or pair_load_calls:
                    raise AssertionError(
                        "trace mode opened an ORT pair or called preflight load_all")
            finally:
                if prior_trace_mode is None:
                    os.environ.pop("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE", None)
                else:
                    os.environ["SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"] = prior_trace_mode

            cache_stat = cache_path.stat()
            damaged = bytearray(cache_path.read_bytes())
            damaged[0] ^= 1
            cache_path.write_bytes(damaged)
            os.utime(cache_path, ns=(cache_stat.st_atime_ns, cache_stat.st_mtime_ns))
            repair_fake = FakeOrt()
            repair_proxy = _ReduxControlOnlyOrtProxy(repair_fake, cache_root)
            repair_proxy.InferenceSession(
                cache_graph, strict_options(repair_proxy),
                providers=["CUDAExecutionProvider"])
            repaired = repair_proxy.session_cache_readback.get("preprocessor.onnx", {})
            if (repair_fake.paths != [str(cache_graph)]
                    or repaired.get("mode") != "built"
                    or not repaired.get("verified_before_session_return")):
                raise AssertionError(
                    "same-size cache corruption with restored mtime was not rejected and rebuilt"
                )

            class MutatingCacheOrt(FakeOrt):
                def InferenceSession(self, path, sess_options=None, *args, **kwargs):
                    session = super().InferenceSession(path, sess_options, *args, **kwargs)
                    if Path(path) == cache_path:
                        current_stat = cache_path.stat()
                        cache_path.write_bytes(damaged)
                        os.utime(cache_path, ns=(current_stat.st_atime_ns, current_stat.st_mtime_ns))
                    return session

            during_load = MutatingCacheOrt()
            during_proxy = _ReduxControlOnlyOrtProxy(during_load, cache_root)
            during_proxy.InferenceSession(
                cache_graph, strict_options(during_proxy), providers=["CUDAExecutionProvider"])
            if (during_load.paths != [str(cache_path), str(cache_graph)]
                    or during_proxy.session_cache_readback["preprocessor.onnx"]["mode"] != "built"):
                raise AssertionError("cache mutation during construction was returned to the consumer")

            encoder_graph = cache_root / "encoder-model.onnx"
            encoder_graph.write_bytes(b"encoder-source")
            cuda = ["CUDAExecutionProvider"]
            cache_proxy.InferenceSession(encoder_graph, strict_options(cache_proxy), providers=cuda)
            encoder_cache, encoder_manifest, _ = cache_proxy._cache_paths(encoder_graph)
            payloads = {graph.name: path.read_bytes()
                        for graph, path in ((cache_graph, cache_path), (encoder_graph, encoder_cache))}

            class ByteCacheOrt(FakeOrt):
                def InferenceSession(self, payload, options, **kwargs):
                    if payload != payloads[options.logid]:
                        raise AssertionError("ORT did not receive the exact verified payload")
                    self.paths.append(options.logid)
                    self.runtime_calls.append((
                        options.logid, kwargs.get("enable_fallback", None)))
                    session = FakeSession(self, options.logid)
                    self.sessions.append(session)
                    return session

            pair_fake = ByteCacheOrt()
            pair = _ReduxControlOnlyOrtProxy(pair_fake, cache_root)

            def load_pair(loader):
                return {name: loader(name) for name in payloads}

            moved_manifest = encoder_manifest.with_suffix(".missing")
            encoder_manifest.rename(moved_manifest)
            if pair.load_preflight_cache_pair(lambda _: strict_options(pair), cuda, load_pair) is not None or pair_fake.paths:
                raise AssertionError("a missing cache half must not start an ORT session")
            moved_manifest.rename(encoder_manifest)

            encoder_stat = encoder_cache.stat()
            saved_manifest = encoder_manifest.read_bytes()
            unsupported = payloads[encoder_graph.name].replace(b"ORTM", b"NONE", 1)
            unsupported_manifest = json.loads(saved_manifest)
            unsupported_manifest["cache_sha256"] = hashlib.sha256(unsupported).hexdigest()
            encoder_cache.write_bytes(unsupported)
            os.utime(encoder_cache, ns=(encoder_stat.st_atime_ns, encoder_stat.st_mtime_ns))
            encoder_manifest.write_text(json.dumps(unsupported_manifest), encoding="utf-8")
            if pair.load_preflight_cache_pair(lambda _: strict_options(pair), cuda, load_pair) is not None or pair_fake.paths:
                raise AssertionError("unsupported cache format reached an ORT session")
            encoder_manifest.write_bytes(saved_manifest)
            encoder_cache.write_bytes(b"x" + payloads[encoder_graph.name][1:])
            os.utime(encoder_cache, ns=(encoder_stat.st_atime_ns, encoder_stat.st_mtime_ns))
            if pair.load_preflight_cache_pair(lambda _: strict_options(pair), cuda, load_pair) is not None or pair_fake.paths:
                raise AssertionError("corrupt second cache passed preflight")
            encoder_cache.write_bytes(payloads[encoder_graph.name])
            encoder_manifest.write_bytes(saved_manifest)
            os.utime(encoder_cache, ns=(encoder_stat.st_atime_ns, encoder_stat.st_mtime_ns))

            def mutate_during_pair(loader):
                loaded = load_pair(loader)
                encoder_cache.write_bytes(b"x" + payloads[encoder_graph.name][1:])
                os.utime(encoder_cache, ns=(encoder_stat.st_atime_ns, encoder_stat.st_mtime_ns))
                return loaded

            try:
                pair.load_preflight_cache_pair(lambda _: strict_options(pair), cuda, mutate_during_pair)
                raise AssertionError("corruption during pair load was returned to the consumer")
            except RuntimeError as exc:
                if "digest changed" not in str(exc):
                    raise
            encoder_cache.write_bytes(payloads[encoder_graph.name])
            encoder_manifest.write_bytes(saved_manifest)
            os.utime(encoder_cache, ns=(encoder_stat.st_atime_ns, encoder_stat.st_mtime_ns))
            if set(pair.load_preflight_cache_pair(lambda _: strict_options(pair), cuda, load_pair)) != set(payloads):
                raise AssertionError("valid cache pair did not return its verified sessions")

            _cache_path, blocked_manifest, _lock_path = cache_proxy._cache_paths(
                cache_graph)
            cache_path.unlink(missing_ok=True)
            blocked_manifest.unlink(missing_ok=True)
            blocked_temp = cache_proxy._cache_temp_path(cache_path)
            blocked_temp.mkdir(parents=True)
            blocked_fake = FakeOrt()
            blocked_proxy = _ReduxControlOnlyOrtProxy(blocked_fake, cache_root)
            blocked_proxy.InferenceSession(
                cache_graph, strict_options(blocked_proxy),
                providers=["CUDAExecutionProvider"])
            unavailable = blocked_proxy.session_cache_readback.get(
                "preprocessor.onnx", {})
            if (blocked_fake.paths != [str(cache_graph)]
                    or unavailable.get("mode") != "build-unavailable"
                    or unavailable.get("verified_before_session_return") is not False
                    or not unavailable.get("reason")):
                raise AssertionError(
                    "blocked cache temp path must be reported without changing source-session behavior"
                )

            cpu_proxy = _ReduxControlOnlyOrtProxy(
                FakeOrt(), cache_root, gpu_only=False)
            cpu_identity = cpu_proxy._cache_identity(
                cache_graph, strict_options(cpu_proxy), ["CUDAExecutionProvider"])
            if cpu_identity is not None:
                raise AssertionError("optimized CUDA cache was exposed to a CPU engine")
            if cache_test_trace_mode is not None:
                os.environ["SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"] = (
                    cache_test_trace_mode)
    finally:
        globals()["_file_sha256"] = original_hash

    original_pool_config = _ORT_GLOBAL_POOL_CONFIG
    try:
        globals()["_ORT_GLOBAL_POOL_CONFIG"] = None
        pool_calls = []

        class FakePoolApi:
            @staticmethod
            def set_global_thread_pool_sizes(**kwargs):
                pool_calls.append(kwargs)

        if _configure_shared_ort_pools(FakePoolApi, 2) != (2, 1):
            raise AssertionError("shared ORT pool dimensions differ")
        if _configure_shared_ort_pools(FakePoolApi, 2) != (2, 1) or len(pool_calls) != 1:
            raise AssertionError("shared ORT pools were configured more than once")
        try:
            _configure_shared_ort_pools(FakePoolApi, 1)
        except RuntimeError as exc:
            if "already configured" not in str(exc):
                raise
        else:
            raise AssertionError("shared ORT pool accepted a conflicting thread budget")
    finally:
        globals()["_ORT_GLOBAL_POOL_CONFIG"] = original_pool_config

    if not _session_readback_graphs_selftest():
        raise AssertionError("core-versus-diagnostic Redux graph set differs")
    prior_node_assignment_trace = os.environ.pop(
        "SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE", None)
    try:
        lazy_vad_ok = _parallel_lazy_vad_selftest()
    finally:
        if prior_node_assignment_trace is not None:
            os.environ["SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE"] = (
                prior_node_assignment_trace)
    if not lazy_vad_ok:
        raise AssertionError("bounded parallel core load or lazy VAD behavior differs")
    if not _serial_helper_budget_selftest():
        raise AssertionError("zero-worker budget did not run hashing and session loads synchronously")
    if not _parallel_trace_sampler_selftest():
        raise AssertionError("diagnostic thread sampling serialized concurrent graph starts")

    cuda_only = ["CUDAExecutionProvider"]
    cache_marker = object()
    if (_reference_session_providers("preprocessor.onnx", cuda_only)
            != cuda_only
            or _reference_session_providers(
                "preprocessor.onnx", cuda_only, cache_marker)
            != list(CONTROL_GRAPH_PROVIDERS)
            or _reference_session_providers(
                "decoder_joint-model.onnx", cuda_only, cache_marker)
            != cuda_only):
        raise AssertionError(
            "Redux reference dispatch double-expanded providers before the ORT proxy"
        )
    for graph_name in REDUX_CONTROL_GRAPH_ALLOWLIST:
        ordinary_request = _reference_session_providers(graph_name, cuda_only)
        ordinary_expected = _reference_session_readback_names(
            graph_name, ordinary_request)
        raw_names = [row["name"] for row in
                     _ReduxControlOnlyOrtProxy._provider_identity(ordinary_request)]
        if (ordinary_expected != list(CONTROL_GRAPH_PROVIDERS)
                or ordinary_expected == raw_names
                or not _reference_session_provider_readback_matches(
                    graph_name, ordinary_request, None,
                    list(CONTROL_GRAPH_PROVIDERS))
                or _reference_session_provider_readback_matches(
                    graph_name, ordinary_request, None, raw_names)):
            raise AssertionError(
                "Redux ordinary session readback must include the proxy's one control-EP expansion"
            )
        cache_request = _reference_session_providers(
            graph_name, cuda_only, cache_marker)
        cache_expected = _reference_session_readback_names(
            graph_name, cache_request, cache_marker)
        if (cache_expected != list(CONTROL_GRAPH_PROVIDERS)
                or not _reference_session_provider_readback_matches(
                    graph_name, cache_request, cache_marker,
                    list(CONTROL_GRAPH_PROVIDERS))
                or _reference_session_provider_readback_matches(
                    graph_name, cache_request, cache_marker,
                    ["CUDAExecutionProvider"])):
            raise AssertionError(
                "Redux direct cache readback must preserve its already-expanded provider list"
            )
        if ordinary_expected == raw_names or cache_expected == [
                "CUDAExecutionProvider"]:
            raise AssertionError(
                "Redux provider readback accepted the stale raw-only policy expectation"
            )
    decoder_names = _reference_session_readback_names(
        "decoder_joint-model.onnx", cuda_only)
    if (decoder_names != ["CUDAExecutionProvider"]
            or not _reference_session_provider_readback_matches(
                "decoder_joint-model.onnx", cuda_only, None, cuda_only)
            or _reference_session_provider_readback_matches(
                "decoder_joint-model.onnx", cuda_only, None,
                list(CONTROL_GRAPH_PROVIDERS))):
        raise AssertionError("Redux decoder readback must remain CUDA-only")
    already_expanded = _graph_provider_entries("preprocessor.onnx", cuda_only)
    try:
        _graph_provider_entries("preprocessor.onnx", already_expanded)
    except RuntimeError:
        pass
    else:
        raise AssertionError(
            "Redux proxy accepted the adverse double-expanded control-provider request"
        )

    print("REDUX_CONTROL_POLICY PASS neural_cuda=1 pinned_shape_control_cpu=1 "
          "runtime_fallback_disabled=1 graph_hash_refusal=3 ort_version_refusal=1 shared_pool_once=1 "
          "bounded_options=1 preprocessor_encoder_disable_all=1 restore_options=1 "
          "restore_on_error=1 parallel_core_sessions=1 lazy_vad=1 provider_dispatch=1 "
          "provider_readback=1 "
          "nonblocking_trace_sampling=1 integrity_hash_overlap=1")
    return 0


def _parallel_lazy_vad_selftest() -> bool:
    """Exercise session concurrency and VAD deferral without loading any model."""
    import tempfile

    class FakeOptions:
        def __init__(self):
            self.entries = {}

        def add_session_config_entry(self, key, value):
            self.entries[str(key)] = str(value)

        def get_session_config_entry(self, key):
            return self.entries.get(str(key), "")

    class FakeInput:
        name = "input_states_1"
        shape = (1, 1, 4)

    class FakeSession:
        def __init__(self, name):
            self.name = name

        @staticmethod
        def get_providers():
            return ["CUDAExecutionProvider", "CPUExecutionProvider"]

        @staticmethod
        def get_inputs():
            return [FakeInput()]

    class FakeOrt:
        def __init__(self):
            self.barrier = threading.Barrier(CORE_SESSION_WORKERS)
            self.sessions = []
            self.lock = threading.Lock()

        @staticmethod
        def SessionOptions():
            return FakeOptions()

        def InferenceSession(self, path, options, providers=None):
            name = Path(path).name
            # Match the production proxy boundary: the adapter passes raw CUDA;
            # the proxy applies the one allowlisted control-graph expansion.
            providers = _graph_provider_entries(name, providers)
            expected_providers = (list(CONTROL_GRAPH_PROVIDERS)
                                  if name in REDUX_CONTROL_GRAPH_ALLOWLIST
                                  else ["CUDAExecutionProvider"])
            if providers != expected_providers:
                raise AssertionError("fake loader provider request differs by graph policy")
            expected_fallback = (
                "0" if name in REDUX_CONTROL_GRAPH_ALLOWLIST else "1")
            if options.get_session_config_entry(_CPU_FALLBACK_KEY) != expected_fallback:
                options.add_session_config_entry(_CPU_FALLBACK_KEY, expected_fallback)
            if options.get_session_config_entry(_CPU_FALLBACK_KEY) != expected_fallback:
                raise AssertionError("fake proxy fallback policy differs by graph")
            if name != "vad-model.onnx":
                self.barrier.wait(timeout=2)
            with self.lock:
                self.sessions.append(name)
            return FakeSession(name)

    class FakeVocabulary:
        blank_id = 0

        def __init__(self, _path):
            return None

    class FakeBase:
        def speech_regions(self, _pcm):
            return [(0.0, 1.0)] if self.vad is not None else []

    class FakeReference:
        OnnxParakeet = FakeBase
        Vocabulary = FakeVocabulary
        ort = FakeOrt()

    with tempfile.TemporaryDirectory(
            prefix="sotto-redux-loader-selftest",
            dir=Path(REPO) / ".agent-work") as temp:
        root = Path(temp)
        (root / "config.json").write_text(json.dumps({
            "durations": [1], "vocab_size": 1, "max_tokens_per_step": 1,
            "encoder_frame_seconds": 0.02, "blank_token_id": 0,
        }), encoding="utf-8")
        (root / "vocab.txt").write_text("<blk> 0\n", encoding="utf-8")
        for name in ("preprocessor.onnx", "encoder-model.onnx",
                     "decoder_joint-model.onnx", "vad-model.onnx"):
            (root / name).write_bytes(b"fixture")
        model = _build_sotto_onnx_parakeet(
            FakeReference, root, threads=1, providers=["CUDAExecutionProvider"]
        )
        if (model.vad is not None
                or set(model.provider_readback) != {
                    "preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx"
                }
                or len(FakeReference.ort.sessions) != CORE_SESSION_WORKERS):
            return False
        if model.speech_regions([0.0] * 32000) != [(0.0, 1.0)]:
            return False
        return (model.vad is not None
                and FakeReference.ort.sessions.count("vad-model.onnx") == 1
                and len(model.provider_readback) == 4)


def _serial_helper_budget_selftest() -> bool:
    """Prove the benchmark's zero-worker mode uses the caller thread only."""
    original_core = CORE_SESSION_WORKERS
    original_hash = CONTROL_HASH_WORKERS
    original_timed_hash = _timed_control_graph_hash
    try:
        globals()["CORE_SESSION_WORKERS"] = 0
        globals()["CONTROL_HASH_WORKERS"] = 0
        loader = globals().get("_load_core_sessions")
        if not callable(loader):
            return False
        caller_tid = threading.get_native_id()
        load_tids = []

        def fake_load(name, _cache_loader):
            load_tids.append(threading.get_native_id())
            return name

        loaded = loader(("a", "b", "c"), fake_load)
        if loaded != {"a": "a", "b": "b", "c": "c"}:
            return False
        if load_tids != [caller_tid, caller_tid, caller_tid]:
            return False

        hash_tids = []

        def fake_hash(path):
            hash_tids.append(threading.get_native_id())
            return Path(path).name, 0.0

        globals()["_timed_control_graph_hash"] = fake_hash
        result = _submit_control_graph_hash(Path("fixture.onnx"))
        if result != ("fixture.onnx", 0.0):
            return False
        if hash_tids != [caller_tid]:
            return False

        sequence = []
        globals()["_timed_control_graph_hash"] = lambda _path: (
            sequence.append("hash") or ("digest", 0.0))
        proxy = object.__new__(_ReduxControlOnlyOrtProxy)
        proxy._validated = set()
        proxy.control_hash_readback = {}
        proxy.session_cache_readback = {}
        proxy._run_session = lambda *_args, **_kwargs: (
            sequence.append("session") or object())
        graph = Path("encoder-model.onnx")
        proxy._source_control_session(
            graph, object(), "digest", None, providers=["CUDAExecutionProvider"])
        return sequence == ["hash", "session"]
    finally:
        globals()["CORE_SESSION_WORKERS"] = original_core
        globals()["CONTROL_HASH_WORKERS"] = original_hash
        globals()["_timed_control_graph_hash"] = original_timed_hash


def _session_readback_graphs_selftest() -> bool:
    """Check core-only production and four-graph diagnostic expectations without weights."""
    import tempfile

    core = frozenset((
        "preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx"
    ))
    with tempfile.TemporaryDirectory(
            prefix="sotto-redux-graph-set-selftest",
            dir=Path(REPO) / ".agent-work") as temp:
        root = Path(temp)
        if _expected_session_readback_graphs(root, False) != core:
            return False
        try:
            _expected_session_readback_graphs(root, True)
        except RuntimeError:
            pass
        else:
            return False
        (root / "vad-model.onnx").write_bytes(b"synthetic marker")
        if _expected_session_readback_graphs(root, False) != core:
            return False
        expected_diagnostic = core | {"vad-model.onnx"}
        return _expected_session_readback_graphs(root, True) == expected_diagnostic


def _parallel_trace_sampler_selftest() -> bool:
    """Ensure diagnostic snapshots cannot serialize concurrent graph loads."""
    class BarrierSampler:
        def __init__(self):
            self.barrier = threading.Barrier(3)
            self.lock = threading.Lock()
            self.completed = 0
            self.failed = False

        def sample(self, _pid):
            try:
                self.barrier.wait(timeout=2)
            except threading.BrokenBarrierError:
                self.failed = True
            with self.lock:
                self.completed += 1
            tid = threading.get_native_id()
            return {tid: (0.0, "trace-selftest")}

    proxy = object.__new__(_ReduxControlOnlyOrtProxy)
    proxy._thread_sampler = BarrierSampler()
    proxy._thread_trace_lock = threading.Lock()
    proxy._thread_start_modules = lambda rows: {
        tid: "selftest.dll" for tid in rows
    }
    prior = os.environ.get("SOTTO_REDUX_ORT_NODE_TRACE")
    os.environ["SOTTO_REDUX_ORT_NODE_TRACE"] = "1"
    try:
        with ThreadPoolExecutor(max_workers=3,
                                thread_name_prefix="redux-trace-selftest") as pool:
            calls = (
                ("END", "preprocessor.onnx"),
                ("BEGIN", "encoder-model.onnx"),
                ("END", "decoder_joint-model.onnx"),
            )
            futures = [pool.submit(proxy._trace_thread_census, edge, graph)
                       for edge, graph in calls]
            for future in futures:
                future.result(timeout=3)
    finally:
        if prior is None:
            os.environ.pop("SOTTO_REDUX_ORT_NODE_TRACE", None)
        else:
            os.environ["SOTTO_REDUX_ORT_NODE_TRACE"] = prior
    return (proxy._thread_sampler.completed == 3
            and not proxy._thread_sampler.failed)

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
#: Hard ceiling on captured audio waiting behind decode. Under overload, the
#: oldest pending samples are discarded and counted so freshness and loss are
#: explicit instead of letting memory/backlog grow for the process lifetime.
DEFAULT_PENDING_AUDIO_S = 30.0
MAX_PENDING_AUDIO_S = 120.0

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
def _build_sotto_onnx_parakeet(reference, model_dir: Path, threads: int, providers,
                               gpu_only: bool = True):
    """Build core graphs concurrently and defer VAD until long audio needs it.

    Neural nodes are CUDA-only. CPU EP is registered only for the three exact
    hash-pinned shape/control graphs and checked against each graph's node map.
    """
    if not gpu_only:
        raise RuntimeError("Redux acoustic sessions require the CUDA provider")
    base = reference.OnnxParakeet
    expected = ["CUDAExecutionProvider"]

    class SottoOnnxParakeet(base):
        def __init__(self, model_dir, threads=None, providers=None):
            model_dir = Path(model_dir)
            config = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
            self.durations = list(config["durations"])
            self.vocab_size = int(config["vocab_size"])
            self.max_symbols_per_step = int(config["max_tokens_per_step"])
            self.frame_seconds = float(config["encoder_frame_seconds"])
            self.vocab = reference.Vocabulary(model_dir / "vocab.txt")
            self.blank_id = int(config.get("blank_token_id", self.vocab.blank_id))
            provider_names = [
                str(item[0] if isinstance(item, (tuple, list)) else item)
                for item in (providers or [])
            ]
            if provider_names != expected:
                raise RuntimeError(
                    "Redux ONNX %s policy requires exactly %s; got %r"
                    % ("GPU-only" if gpu_only else "CPU-fallback",
                       expected[0], provider_names)
                )
            self.cpu_ep_fallback_disabled = True
            self.provider_readback = {}
            ort_module = reference.ort

            def make_options(name):
                options = ort_module.SessionOptions()
                if threads:
                    options.intra_op_num_threads = int(threads)
                options.logid = name
                options.add_session_config_entry(
                    _CPU_FALLBACK_KEY,
                    "0" if name in REDUX_CONTROL_GRAPH_ALLOWLIST else "1")
                return options

            def session(name, cache_loader=None):
                requested_providers = _reference_session_providers(
                    name, providers, cache_loader)
                if cache_loader is not None and name in REDUX_ORT_CACHE_GRAPHS:
                    sess = cache_loader(name, requested_providers)
                else:
                    sess = ort_module.InferenceSession(
                        str(model_dir / name), make_options(name),
                        providers=requested_providers)
                if gpu_only and isinstance(ort_module, _ReduxControlOnlyOrtProxy):
                    option_readback = getattr(ort_module, "options_readback", {})
                    row = option_readback.get(name, {})
                    expected_fallback = (
                        "0" if name in REDUX_CONTROL_GRAPH_ALLOWLIST else "1")
                    if (row.get("disable_cpu_ep_fallback") != expected_fallback
                            or not _reference_session_provider_readback_matches(
                                name, requested_providers, cache_loader,
                                row.get("requested_provider_entries", []))
                            or row.get("runtime_fallback_disabled") is not True):
                        raise RuntimeError(
                            "Redux graph provider/fallback policy did not read back "
                            "disabled for %s: %r" % (name, row)
                        )
                actual = list(sess.get_providers())
                if (expected[0] not in actual
                        or any(provider not in ("CUDAExecutionProvider",
                                                "CPUExecutionProvider")
                               for provider in actual)):
                    raise RuntimeError(
                        "Redux ONNX GPU-only policy: %s did not load %s; providers=%r"
                        % (name, expected[0], actual)
                    )
                self.provider_readback[name] = actual
                return sess

            core_names = (
                "preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx"
            )
            def load_all(cache_loader=None):
                return _load_core_sessions(core_names, session, cache_loader)

            loaded = (ort_module.load_preflight_cache_pair(make_options, providers, load_all)
                      if isinstance(ort_module, _ReduxControlOnlyOrtProxy) else None)
            if loaded is None:
                loaded = load_all()
            self.preprocessor = loaded["preprocessor.onnx"]
            self.encoder = loaded["encoder-model.onnx"]
            self.decoder_joint = loaded["decoder_joint-model.onnx"]
            self._sotto_session_factory = session
            self._sotto_vad_exists = (model_dir / "vad-model.onnx").is_file()
            self._sotto_vad_deferred = self._sotto_vad_exists
            self._sotto_vad_lock = threading.Lock()
            self.vad = None
            state_shape = next(
                item.shape for item in self.decoder_joint.get_inputs()
                if item.name == "input_states_1"
            )
            self.state_shape = (int(state_shape[0]), 1, int(state_shape[2]))
            if (os.environ.get("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE") == "1"
                    and self._sotto_vad_deferred):
                # The benchmark must attest every acoustic graph before it
                # starts decoding any sample, including the normally lazy VAD.
                self.vad = self._sotto_session_factory("vad-model.onnx")
                self._sotto_vad_deferred = False

        def speech_regions(self, pcm):
            if self.vad is None and self._sotto_vad_deferred:
                with self._sotto_vad_lock:
                    if self.vad is None:
                        self.vad = self._sotto_session_factory("vad-model.onnx")
                        self._sotto_vad_deferred = False
            return super().speech_regions(pcm)

    return SottoOnnxParakeet(
        model_dir, threads=threads, providers=providers
    )


def _open_onnx_once(reference, model_path: Path, threads: int, provider_names,
                    entries, gpu_only: bool):
    """One CUDA build attempt through the guarded reference ORT proxy."""
    proxy = _ReduxControlOnlyOrtProxy(reference.ort, model_path, gpu_only=gpu_only)
    original_ort = reference.ort
    reference.ort = proxy
    try:
        model = _build_sotto_onnx_parakeet(
            reference, model_path, threads=threads, providers=entries,
            gpu_only=gpu_only)
    finally:
        reference.ort = original_ort
    return model, proxy


def open_onnx_sessions(reference, model_path: Path, threads: int, provider_names,
                       allow_cpu_fallback: bool = False, log=None,
                       provider_entries=None):
    """Open Redux with CUDA neural placement and pinned CPU control-node exceptions."""
    if tuple(provider_names) != GPU_PROVIDERS or allow_cpu_fallback:
        raise RuntimeError("Redux requires CUDA with CPU inference fallback disabled")
    entries_for = provider_entries or (lambda names: list(names))
    model, proxy = _open_onnx_once(
        reference, model_path, threads, provider_names,
        entries_for(list(provider_names)), True)
    return model, proxy, "cuda", None


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

    def __init__(self, model_dir: str, threads: int = 1, providers=None,
                 log=None, allow_cpu_fallback: bool = False):
        # THE MODEL DIRECTORY FIRST. MEASURED 2026-10-17: this loader put only
        # `ONNX_REFERENCE_DIR` on sys.path, and the export ships its OWN
        # `transcribe.py` inside the model directory, so a correct, complete
        # download still died with `ModuleNotFoundError: No module named
        # 'transcribe'` -- state="error", stage="model". The reference directory
        # stays as the fallback for the layout where the three small files were
        # split out, and it is tried SECOND so a stale copy there can never shadow
        # the one that ships with the weights it belongs to.
        threads = _set_numeric_thread_environment(threads)
        model_path = Path(model_dir)
        for candidate in (str(model_path), ONNX_REFERENCE_DIR):
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
        # Register the CUDA runtime DLL directories before the export imports
        # ONNX Runtime. This is the same ordered setup used by the Nemotron
        # worker; a missing CUDA runtime must fail, never fall back to CPU.
        import sotto_worker as _worker

        _worker._add_cuda_dll_dirs()
        self.cuda_dlls_preloaded = _worker._preload_cuda_runtime()
        import transcribe as reference

        # The reference implementation takes a Path and divides it
        # (`model_dir / "config.json"`); handing it the CLI's str is a TypeError,
        # measured. Convert once, here.
        if not (model_path / "encoder-model.onnx").is_file():
            raise SystemExit(
                f"redux_live: no ONNX export in {model_path}\n"
                f"  fetch AND verify it (measured 2026-10-17: 7 s on this box,\n"
                f"  416 MB, revision 1c285ba78d6f1880803f65355133a5ad3559a407):\n"
                f"    python _main\\fetch-parakeet.py"
            )
        self._ref = reference
        # Share one process-bounded ORT pool across core and deferred sessions.
        _configure_shared_ort_pools(reference.ort, threads)
        # Neural nodes use CUDA; the exact hash-pinned preprocessor, encoder,
        # and VAD maps permit their measured shape/control nodes on CPU.
        # Decoder/joint remains requested and attested as CUDA-only.
        provider_names = [
            str(item[0] if isinstance(item, (tuple, list)) else item)
            for item in (providers or GPU_PROVIDERS)
        ]
        self._model, proxy, self.device, self.gpu_failure = open_onnx_sessions(
            reference, model_path, threads, provider_names,
            allow_cpu_fallback=allow_cpu_fallback, log=log,
            provider_entries=_worker.provider_entries,
        )
        self.model_dir = str(model_path)
        self.threads = threads
        self.provider_readback = self._model.provider_readback
        self.node_assignment_readback = proxy.node_assignment_readback
        self.control_hash_readback = proxy.control_hash_readback
        self.session_cache_readback = proxy.session_cache_readback
        options_readback = proxy.options_readback
        node_assignment_trace = (
            os.environ.get("SOTTO_REDUX_ORT_NODE_ASSIGNMENT_TRACE") == "1")
        if set(options_readback) != set(self.provider_readback):
            raise RuntimeError("Redux ORT option readback graph set differs")
        expected_graphs = _expected_session_readback_graphs(
            model_path, node_assignment_trace)
        if set(options_readback) != expected_graphs:
            raise RuntimeError("Redux eager session graph set differs: %r"
                               % sorted(options_readback))
        if set(self.node_assignment_readback) != set(options_readback):
            raise RuntimeError("Redux graph/node placement readback set differs")
        if (node_assignment_trace
                and set(self.node_assignment_readback) != expected_graphs):
            raise RuntimeError("Redux diagnostic graph/node readback set differs: %r"
                               % sorted(self.node_assignment_readback))
        if self.device == "cuda":
            expected_fallback = {
                "preprocessor.onnx": "0",
                "encoder-model.onnx": "0",
                "decoder_joint-model.onnx": "1",
                "vad-model.onnx": "0",
            }
        else:
            raise RuntimeError(
                "Redux acoustic inference must not return a CPU execution device"
            )
        for graph, row in options_readback.items():
            expected_provider_names = (
                list(CONTROL_GRAPH_PROVIDERS)
                if graph in REDUX_CONTROL_GRAPH_ALLOWLIST
                else ["CUDAExecutionProvider"])
            if (row.get("intra_op_threads") != threads
                    or row.get("inter_op_threads") != 1
                    or row.get("use_per_session_threads") is not False
                    or row.get("execution_mode_sequential") is not True
                    or row.get("intra_op_spinning") != "0"
                    or row.get("inter_op_spinning") != "0"
                    or row.get("disable_cpu_ep_fallback") != expected_fallback.get(graph)
                    or row.get("requested_provider_names") != expected_provider_names
                    or row.get("node_assignment_trace") is not True
                    or (self.device == "cuda"
                        and row.get("runtime_fallback_disabled") is not True)):
                raise RuntimeError(
                    "Redux ORT bounded thread/%s option readback differs for %s: %r"
                    % ("GPU" if self.device == "cuda" else "CPU", graph, row)
                )
        self.cpu_execution_policy = (
            "neural-cuda;pinned-shape-control-cpu")
        self.thread_policy = {
            "ort_global_intra_op_threads": threads,
            "ort_global_inter_op_threads": 1,
            "process_pool_budget": {
                "ort_intra_op": threads,
                "ort_inter_op": 1,
                "core_session_loader": max(0, int(CORE_SESSION_WORKERS)),
                "integrity_hash": max(0, int(CONTROL_HASH_WORKERS)),
                "configured_total": (threads + 1
                                      + max(0, int(CORE_SESSION_WORKERS))
                                      + max(0, int(CONTROL_HASH_WORKERS))),
                "scope": "configured pools; OS thread IDs are not inferred",
            },
            "helper_execution_readback": {
                "core_session_loader": ("caller-thread" if CORE_SESSION_WORKERS <= 0
                                         else "thread-pool"),
                "integrity_hash": ("caller-thread" if CONTROL_HASH_WORKERS <= 0
                                   else "thread-pool"),
                "integrity_hash_executor_created": _CONTROL_HASH_EXECUTOR is not None,
            },
            "ort_shared_global_pool": True,
            "ort_per_session_pools": False,
            "core_session_loader_workers": CORE_SESSION_WORKERS,
            "integrity_hash_workers": CONTROL_HASH_WORKERS,
            "control_hash_readback": dict(self.control_hash_readback),
            "session_cache_readback": dict(self.session_cache_readback),
            "ort_intra_op_per_session": threads,
            "ort_intra_op_sessions": len(self.provider_readback),
            "ort_intra_op_total": threads,
            "ort_inter_op_per_session": 1,
            "ort_inter_op_sessions": len(self.provider_readback),
            "ort_inter_op_total": 1,
            "ort_execution_mode": "ORT_SEQUENTIAL",
            "ort_spinning": False,
            "session_options_readback": options_readback,
            "runtime_fallback_readback": proxy.runtime_fallback_readback,
            "node_assignment_trace": (
                bool(proxy.node_assignment_readback)),
            "node_assignment_readback": proxy.node_assignment_readback,
            "node_assignment_readback_s": float(proxy.node_assignment_readback_s),
            "environment": {name: os.environ.get(name) for name in _NUMERIC_THREAD_ENV},
        }

    def transcribe(self, pcm):
        result = self._model.transcribe(pcm, "segment")
        loaded = len(self.provider_readback)
        self.thread_policy["ort_intra_op_sessions"] = loaded
        self.thread_policy["ort_inter_op_sessions"] = loaded
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

    def __init__(self, model_dir: str, threads: int = 0, device: str = "cuda"):
        import numpy as np

        import redux_batch

        if str(device).strip().lower() != "cuda":
            raise RuntimeError("Redux GPU-only policy requires device='cuda'; got %r" % device)
        self._np = np
        self._batch = redux_batch
        # redux_batch.load_runtime does `model_dir / "config.json"` and is typed
        # `model_dir: Path`; handing it the CLI's str is a TypeError ("unsupported
        # operand type(s) for /: 'str' and 'str'", measured 2026-10-08 on the
        # --engine ternary arm). Convert once, here -- the same cure OnnxBackend
        # needed.
        model_path = Path(model_dir)
        self.model_dir = str(model_path)
        self.device = device
        self._runtime = redux_batch.load_runtime(model_path, device=device)
        actual_device = str(getattr(getattr(self._runtime, "device", None), "type", "")).lower()
        if actual_device != "cuda":
            raise RuntimeError("Redux Photon expected CUDA runtime, got %r" % actual_device)
        self._threads = threads

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


def load_backend(engine: str, onnx_dir: str, ternary_dir: str, threads: int, device: str,
                 log=None, allow_cpu_fallback: bool = False):
    """Open Redux with the requested CUDA device; acoustic CPU fallback is refused.

    `allow_cpu_fallback` remains as a compatibility argument for older callers,
    but any true value is rejected by :func:`open_onnx_sessions` before session
    construction.
    """
    started = time.perf_counter()
    if str(device).strip().lower() != "cuda":
        raise RuntimeError("Redux GPU-only policy requires device='cuda'; got %r" % device)
    if engine == "onnx":
        backend = OnnxBackend(onnx_dir, threads=threads, log=log,
                              allow_cpu_fallback=allow_cpu_fallback)
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
        self.rate = worker.TARGET_SR
        self.source_rate_set = False
        self.pending_audio_s = float(getattr(args, "pending_audio_s", DEFAULT_PENDING_AUDIO_S))
        if not 0.0 < self.pending_audio_s <= MAX_PENDING_AUDIO_S:
            raise ValueError("pending_audio_s must be in (0, %.1f]" % MAX_PENDING_AUDIO_S)
        self.pending_cap_samples = max(1, int(round(self.pending_audio_s * self.rate)))
        self.pending_samples = 0
        self.pending_peak_s = 0.0
        self.pending_dropped_samples = 0
        self.pending_drop_events = 0
        self.seg = LiveSegmenter(
            window_s=args.window_s, gap_s=args.gap_s,
            min_window_s=args.min_window_s, max_line_chars=args.max_line_chars,
            vad=not args.no_vad,
            gain=(None if args.no_agc else worker.AutoGain()),
        )
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
        block_samples = int(getattr(block, "size", 0))
        if block_samples <= 0:
            return
        with self.lock:
            self.pending.append(block)
            self.pending_samples += block_samples
            self.blocks += 1
            self.samples += block_samples
            if block.size:
                self.peak = max(self.peak, float(abs(block).max()))
            dropped = self._trim_pending_locked()
            if dropped:
                self.pending_drop_events += 1
            if self.source_rate_set:
                self.pending_peak_s = max(
                    self.pending_peak_s,
                    self.pending_samples / float(max(1, self.rate)),
                )

    def _discard_pending_locked(self, samples):
        """Discard exactly `samples` from the queue front; caller holds lock."""
        remaining = max(0, int(samples))
        dropped = 0
        while remaining and self.pending:
            oldest = self.pending.popleft()
            size = int(getattr(oldest, "size", 0))
            take = min(size, remaining)
            dropped += take
            remaining -= take
            self.pending_samples -= take
            if take < size:
                self.pending.appendleft(oldest[take:].copy())
        self.pending_dropped_samples += dropped
        return dropped

    def _trim_pending_locked(self):
        """Enforce the duration cap, evicting oldest pending audio first."""
        excess = max(0, self.pending_samples - self.pending_cap_samples)
        return self._discard_pending_locked(excess) if excess else 0

    def set_source_rate(self, rate):
        """Set the tap's source rate and keep the queue cap expressed in seconds."""
        rate = int(rate or self.worker.TARGET_SR)
        if rate <= 0:
            raise ValueError("source sample rate must be positive")
        with self.lock:
            self.rate = rate
            self.pending_cap_samples = max(1, int(round(self.pending_audio_s * rate)))
            dropped = self._trim_pending_locked()
            if dropped:
                self.pending_drop_events += 1
            current_s = self.pending_samples / float(rate)
            self.pending_peak_s = (current_s if not self.source_rate_set else
                                  max(self.pending_peak_s, current_s))
            self.source_rate_set = True

    def _restore_pending_front(self, blocks):
        """Restore an older unconsumed prefix ahead of concurrently queued audio."""
        if not blocks:
            return
        with self.lock:
            self.pending.extendleft(reversed(blocks))
            self.pending_samples += sum(int(getattr(block, "size", 0)) for block in blocks)
            dropped = self._trim_pending_locked()
            if dropped:
                self.pending_drop_events += 1

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
            self.pending_samples = 0
        if not blocks:
            return 0
        np = self.np
        room = None
        if limit:
            room = int(float(limit) * self.worker.TARGET_SR) - self.seg.seg_samples
            if room <= 0:
                self._restore_pending_front(blocks)
                return 0
            # Select only enough source-rate samples for this window. This keeps
            # a large backlog from being concatenated/resampled just to discard
            # its tail, and leaves any remainder in its original sample rate.
            source_limit = room if self.rate == self.worker.TARGET_SR else int(
                room * self.rate / self.worker.TARGET_SR)
            if source_limit <= 0:
                self._restore_pending_front(blocks)
                return 0
            selected = []
            remainder = []
            remaining = source_limit
            for index, block in enumerate(blocks):
                size = int(getattr(block, "size", 0))
                if remaining <= 0:
                    remainder = blocks[index:]
                    break
                if size <= remaining:
                    selected.append(block)
                    remaining -= size
                else:
                    selected.append(block[:remaining])
                    remainder = [block[remaining:]] + blocks[index + 1:]
                    remaining = 0
                    break
            blocks = selected
            if remainder:
                self._restore_pending_front(remainder)
        joined = np.concatenate(blocks) if len(blocks) > 1 else blocks[0]
        if self.rate != self.worker.TARGET_SR:
            joined = self.worker.resample_to_16k(joined, self.rate)
        if room is not None and joined.size > room:
            # Defensive against a future resampler whose output-length rounding
            # differs from the current worker implementation.
            raise RuntimeError("resampler exceeded the live window sample cap")
        self.seg.feed(joined)
        return int(joined.size)

    def backlog_s(self):
        """Audio received but not yet in the open line -- the honest queue depth."""
        with self.lock:
            return self.pending_samples / float(max(1, self.rate))

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
            f"pending_cap_s={self.pending_audio_s:.1f} pending_peak_s={self.pending_peak_s:.2f} "
            f"pending_drop_events={self.pending_drop_events} "
            f"pending_dropped_s={self.pending_dropped_samples / float(max(1, self.rate)):.2f} "
            f"mean_compute_s={sum(computes) / len(computes):.2f} "
            f"max_compute_s={max(computes):.2f}" if computes else
            f"LIVE_STATS passes=0 captions=0 blocks={self.blocks} "
            f"audio_s={self.seg.audio_s:.1f} backlog_s={self.backlog_s():.2f} "
            f"peak={self.peak:.6f} overruns=0 pending_cap_s={self.pending_audio_s:.1f} "
            f"pending_peak_s={self.pending_peak_s:.2f} "
            f"pending_drop_events={self.pending_drop_events} "
            f"pending_dropped_s={self.pending_dropped_samples / float(max(1, self.rate)):.2f}"
        )

    def flush(self):
        """End of stream: publish the open line as a CLOSED one.

        NO limit here -- this is the end, so everything queued is decoded. The
        tail is flushed in window-sized pieces so the last line is not a 30 s
        window, which would cost far more than the rest of the run together.
        """
        max_flush_passes = max(1, int(self.pending_audio_s / max(0.01, self.seg.window_s)) + 2)
        for _ in range(max_flush_passes):
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
    run.set_source_rate(getattr(tap, "rate", worker.TARGET_SR))
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
    run.set_source_rate(worker.TARGET_SR)
    # FileTap owns a pump THREAD and does nothing until it is started -- measured:
    # without this call the run reported blocks=0 for its whole length and exited
    # with verdict `no-captions`, i.e. a silent, green-looking failure.
    tap.stream.start()
    run.tap, run.device = tap, {"name": f"file:{os.path.basename(args.wav)}"}
    emit(type="status", state="capture-started", device=run.device["name"],
         api=None, rung="file", rate=run.rate, block=tap.block)
    err(f"file tap: {args.wav} ({tap.pcm.size / worker.TARGET_SR:.1f} s), "
        f"no audio device opened")
    thread = threading.Thread(target=run.decode_loop, name="redux-live-decode", daemon=True)
    thread.start()
    next_stats = time.monotonic() + args.stats_interval
    try:
        while not run.stop.is_set() and not tap.done.is_set():
            now = time.monotonic()
            if args.max_seconds and (now - run.started) >= args.max_seconds:
                break
            if now >= next_stats:
                err(run.stats_line())
                next_stats = now + args.stats_interval
            if tap.once:
                tap.done.wait(0.1)
            else:
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
    parser.add_argument("--pending-audio-s", type=float, default=DEFAULT_PENDING_AUDIO_S,
                        help=f"maximum queued audio before oldest samples are dropped "
                             f"(default {DEFAULT_PENDING_AUDIO_S}; max {MAX_PENDING_AUDIO_S})")
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
    parser.add_argument("--photon-device", default="cuda", choices=("cuda",),
                        help="GPU device for Redux inference (CPU inference is disabled)")
    parser.add_argument("--threads", type=int, default=1,
                        help="intra-op threads per ONNX session (default 1; zero is clamped to 1)")
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
    parser.add_argument("--control-policy-selftest", action="store_true",
                        help="exercise Redux GPU/control-node policy without loading a model")
    args = parser.parse_args(argv)
    if args.control_policy_selftest:
        return _control_policy_selftest()
    args.threads = _set_numeric_thread_environment(args.threads)
    if not 0.0 < args.pending_audio_s <= MAX_PENDING_AUDIO_S:
        parser.error("--pending-audio-s must be in (0, %.1f]" % MAX_PENDING_AUDIO_S)

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
    emit(type="status", state="redux-gpu-policy", engine=engine,
         device=backend.device,
         gpu_unavailable=getattr(backend, "gpu_failure", None),
         ort_cuda_graphs=(sum(1 for providers in backend.provider_readback.values()
                              if "CUDAExecutionProvider" in providers)
                          if hasattr(backend, "provider_readback") else 0),
         ort_graphs=(len(backend.provider_readback)
                     if hasattr(backend, "provider_readback") else 0),
         provider_readback=(";".join(
             "%s=%s" % (name, "|".join(providers))
             for name, providers in sorted(backend.provider_readback.items()))
             if hasattr(backend, "provider_readback") else "photon-device=cuda"),
         cpu_execution_policy=getattr(backend, "cpu_execution_policy", "disabled"),
         thread_policy=getattr(backend, "thread_policy", {
             "photon_threads": getattr(backend, "threads", None)}))
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
         pending_audio_cap_s=run.pending_audio_s,
         pending_audio_peak_s=round(run.pending_peak_s, 2),
         pending_drop_events=run.pending_drop_events,
         pending_dropped_s=round(run.pending_dropped_samples / float(max(1, run.rate)), 2),
         audio_s=round(run.seg.audio_s, 2), peak=round(run.peak, 6),
         blocks=run.blocks, device=(run.device or {}).get("name"),
         ledger=run.ledger, denials=run.denials,
         rss_mb=round(rss_mb(), 1), peak_rss_mb=round(peak_rss_mb(), 1),
         worker_revision=revision)
    err(run.stats_line())
    err(f"redux_live: done verdict={verdict} rc={rc} captions={run.captions} "
        f"finals={run.finals} peak_rss={peak_rss_mb():.1f} MB")
    return rc


# ── THE OVERLAY: a second pass POR CIMA of every line the live engine closes ──
# ANCHOR: redux_live_overlay -- referenced by worker/sotto_worker.py and by
# _main/redux-live-overlay-oracle.py
#
# OWNER 2026-10-12, verbatim: *"nemotron a transcrever ao vivo e o parakeet
# redux POR CIMA de tudo o que é falado ao vivo, porque tem maior qualidade."*
#
# This is the second half of the stack law. The live engine stays nemotron --
# it paints the provisional rows the owner reads while he speaks -- and the
# Redux pass runs OVER the lines that engine CLOSES, per the owner's
# *"o historico nao e pra ser NUNCA o historico do live nvidia. e pra ser do
# parakeet redux"* (`app/panel/panel.js`). It is NOT a new model, NOT a new
# process and NOT a second writer of the panel's bytes: it reuses the backends
# and the RSS helpers already measured in this file and emits the JSONL
# `worker/sotto_worker.py` already emits.
#
# WHY THE LIVE FINAL IS HELD AND NOT DUPLICATED -- the whole design in one
# paragraph, and it is a PANEL-SIDE fact, measured in
# `_main/redux-live-overlay-oracle.py` by driving the REAL
# `app/panel/caption-formulation.js`: `ingest` stamps `emittedEnd` ONLY inside
# `commit()`, so while a line is still growing `emittedEnd` stays null and the
# re-cover branch (`start === emittedStart && start < emittedEnd`) cannot fire.
# A late event carrying the line's own `start` then takes the PLAIN path and the
# panel's hypothesis is that event's WHOLE text. Publish the live `final` first
# and that `commit()` stamps `emittedEnd`, so the Redux line is read as a
# RE-COVER and its words are trimmed by `agreedPrefixLength` against the live
# words -- the live words stay, the Redux ones after them are dropped, and the
# transcript loses the better version. Holding the live final and publishing
# exactly ONE line per segment is what makes the Redux text land WHOLE.
#
# WHAT IT COSTS, and why it is default-OFF: the measured ONNX int4 numbers in
# this file's docstring (1.05 s load, 1.05-1.36 s per 5 s window, 615 MB peak
# RSS, 128% of one core at threads=2) are for a standalone run. As an overlay
# they are paid IN ADDITION to the live ASR decode on the same box, so the arm
# is opt-in (`--redux-live` / `SOTTO_REDUX_LIVE=1`) and both receipts carry it.
REDUX_LIVE_MODEL_DEFAULT = "parakeet-redux"


class ReduxLiveOverlay:
    """A second pass POR CIMA of every line the live engine closes.

    PURE-ISH: it owns a rolling slice of PCM, one worker thread and a FIFO. The
    ASR thread hands it audio (`accept`) and the closed-line events
    (`hold_live_final`), and takes back the events to publish (`drain`). The
    decode itself is the INJECTED `backend`, so an oracle can drive the real
    control flow with a fake engine and learn exactly what a real run emits.

    THE EVENT IT EMITS carries the line's OWN identity -- `start`, and `source`
    when the live engine has one -- plus `producer` (the existing `PRODUCER`),
    `producerModel`, `route` and `final: true`, which are the batch arm's own
    keys (`worker/sotto_worker.py` `_run_runner`). No field is invented: that is
    the shape `app/panel/history-source.js` `CANONICAL_PRODUCER` and
    `caption-formulation.js committedProducer` / `routeSourceFor` already read.

    THE HOLD IS SAFE BECAUSE IT IS NEVER LOST. For every line it took, `drain()`
    eventually returns exactly ONE event: the Redux line when the pass answered,
    and the live line, byte for byte, when it did not (no retained audio, an
    empty decode, a raised exception, the deadline, a full queue, or `stop`).
    """

    def __init__(self, backend, *, producer=PRODUCER, producer_model=None, log=None,
                 sr=16000, keep_s=None, silence_s=0.25, deadline_s=None,
                 max_queue=6, tick_s=0.1, thread_factory=None, armed=True):
        import numpy as np

        self._np = np
        self.backend = backend
        self.producer = str(producer or PRODUCER)
        self.producer_model = str(producer_model or REDUX_LIVE_MODEL_DEFAULT)
        self._log = log if callable(log) else (lambda message: None)
        self.sr = max(8000, int(sr))
        self.silence_s = max(0.0, float(silence_s))
        self.deadline_s = float(deadline_s) if deadline_s else 0.0
        self.max_queue = max(1, int(max_queue))
        self.tick_s = min(1.0, max(0.01, float(tick_s)))
        self.thread_factory = thread_factory
        # THE GUARD, both colours of one measurement. `armed=False` (or a
        # `backend` of None) makes `hold_live_final` return False for every
        # line, which is the pre-overlay behaviour byte for byte. The oracle's
        # neg-arm removes the CALLER that consults it, not this line.
        self.armed = bool(armed) and backend is not None

        # How much PCM is retained. It is the ONE number that decides whether a
        # line can still be answered: a segment whose start has already fallen
        # out of this window ships as the live text. 90 s of 16 kHz float32 is
        # 5.5 MB, and the buffer is a deque of blocks trimmed on every feed, so
        # it never grows past this.
        self.keep_s = float(keep_s) if keep_s else 90.0
        self.keep_samples = max(self.sr, int(self.keep_s * self.sr))

        self._lock = threading.Lock()
        self._buf = deque()          # 16 kHz blocks, oldest first
        self._buf_samples = 0
        self._fed_samples = 0        # absolute samples ever accepted
        self._base_samples = 0       # absolute index of the first retained sample
        self._queue = deque()        # segments awaiting a decode, oldest first
        self._out = deque()          # events ready to publish
        self._inflight = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._worker = None

        # -- counters: what the overlay DID, never what a model would do -------
        self.segments = 0        # live finals taken over
        self.returned = 0        # events drain() gave back
        self.redux_lines = 0     # ... of those, the Redux text shipped
        self.fallbacks = 0       # ... of those, the live text shipped instead
        self.failures = 0        # decode raised
        self.expired = 0         # ... of those, the deadline forced the fallback
        self.overflow = 0        # live finals not accepted at all (queue full)
        self.decodes_s = []      # per-segment wall seconds -- the COST
        self.audio_s = 0.0       # audio seconds handed to the backend
        self.rss_before_mb = -1.0
        self.rss_after_mb = -1.0
        self.refusals = {}       # reason -> count, so a refusal is never silent
        self.started = False
        self.stopped = False

    def _note(self, message):
        self._log(message)

    # -- audio in ------------------------------------------------------------
    def accept(self, pcm):
        """One 16 kHz block from the ASR thread.

        The lock is held for a list append and a bounded trim -- NEVER across a
        decode -- so a slow Redux pass can never stall the audio path.
        """
        block = self._np.ascontiguousarray(pcm, dtype=self._np.float32).reshape(-1)
        if block.size == 0:
            return 0
        with self._lock:
            self._buf.append(block)
            self._buf_samples += int(block.size)
            self._fed_samples += int(block.size)
            self._trim_locked()
            return int(block.size)

    def _trim_locked(self):
        """Drop PCM older than `keep_s`. A single block alone may exceed the
        cap; it is CUT rather than held whole, so memory stays the promise."""
        while self._buf_samples > self.keep_samples and len(self._buf) > 1:
            head = self._buf[0]
            if head.size >= self._buf_samples - self.keep_samples:
                break
            self._buf.popleft()
            self._buf_samples -= int(head.size)
            self._base_samples += int(head.size)
        if self._buf_samples > self.keep_samples and self._buf:
            head = self._buf[0]
            drop = self._buf_samples - self.keep_samples
            if drop >= head.size:
                self._buf.popleft()
                self._buf_samples -= int(head.size)
                self._base_samples += int(head.size)
            else:
                self._buf[0] = head[drop:]
                self._buf_samples -= int(drop)
                self._base_samples += int(drop)

    def _window_locked(self, start_s, end_s):
        """The PCM covering [start_s, end_s], or None when retention passed it.

        `start`/`end` are the live event's own audio seconds and therefore the
        same clock `accept` was fed on: absolute sample = second * `sr`. A line
        whose OPENING has already been trimmed is refused rather than answered
        with half a segment -- half a segment is a different sentence.
        """
        if start_s is None:
            return None
        try:
            a = int(round(float(start_s) * self.sr))
            b = (self._fed_samples if end_s is None
                 else int(round(float(end_s) * self.sr)))
        except (TypeError, ValueError):
            return None
        if a < self._base_samples or b <= a:
            return None
        i0 = a - self._base_samples
        i1 = min(b - self._base_samples, self._buf_samples)
        if i1 <= i0:
            return None
        out = self._np.zeros(i1 - i0, dtype=self._np.float32)
        pos = 0
        for block in self._buf:
            n = int(block.size)
            if pos + n <= i0:
                pos += n
                continue
            lo = max(0, i0 - pos)
            hi = min(n, i1 - pos)
            if hi > lo:
                out[(pos + lo - i0):(pos + hi - i0)] = block[lo:hi]
            pos += n
            if pos >= i1:
                break
        return out

    # -- the live line in ------------------------------------------------------
    def hold_live_final(self, event):
        """Take ownership of ONE closed live line.

        False -- publish `event` unchanged -- when the overlay is not armed, not
        started, already stopped; when this is not a `final` caption; when it
        carries no text or no usable audio position; when its audio is no longer
        retained or is shorter than `silence_s`; or when the queue is full.
        True otherwise, and then the overlay will publish exactly one line for
        this segment.

        EVERY FALSE CASE IS THE HONEST ONE: an overlay that never armed costs a
        run nothing, and a line it cannot answer is published as it was.
        """
        if not self.armed or not isinstance(event, dict):
            return False
        if event.get("type") != "caption":
            return False
        if event.get("final") is not True:
            return False
        text = str(event.get("text") or "").strip()
        if not text:
            return False
        start = event.get("start")
        if isinstance(start, bool) or not isinstance(start, (int, float)):
            return False
        with self._lock:
            if not self.started or self.stopped:
                return False
            pcm = self._window_locked(start, event.get("end"))
            if pcm is None:
                self._refuse("audio-not-retained")
                return False
            if pcm.size < int(self.silence_s * self.sr):
                self._refuse("segment-too-short")
                return False
            # The bound counts the segment being decoded too:
            # `max_queue` is how many segments the overlay holds at once, not
            # how many it accepts while a decode is already running.
            in_flight = 1 if self._inflight is not None else 0
            if len(self._queue) + in_flight >= self.max_queue:
                self.overflow += 1
                self._refuse("queue-full")
                return False
            self._queue.append({
                "queued_at": time.time(),
                "start": start,
                "end": event.get("end"),
                "text": text,
                "source": event.get("source"),
                "pcm": pcm,
                # kept WHOLE so the fallback IS the live line, byte for byte
                "event": event,
            })
            self.segments += 1
        self._wake.set()
        return True

    def _refuse(self, reason):
        self.refusals[reason] = self.refusals.get(reason, 0) + 1

    # -- events out ------------------------------------------------------------
    def drain(self):
        """The events to publish now, in capture order. Never partial text."""
        with self._lock:
            if not self._out:
                return []
            out = list(self._out)
            self._out.clear()
            self.returned += len(out)
            return out

    def start(self):
        """Start the decode thread. Idempotent; a caller that never starts it
        publishes every live line, because `hold_live_final` refuses."""
        with self._lock:
            if self.started or self.stopped:
                return None
            self.started = True
            self.rss_before_mb = rss_mb()

        def default(target, name):
            return threading.Thread(target=target, name=name, daemon=True)

        make = self.thread_factory or default
        self._worker = make(self._loop, "redux-live")
        self._worker.start()
        return self._worker

    def _loop(self):
        """One segment at a time, in capture order.

        The wake event doubles as the watchdog tick: a segment that outruns
        `deadline_s` becomes the live-text fallback even while nothing else is
        queued, because a held line must never wait as long as a stuck decode.
        """
        while not self._stop.is_set():
            self._wake.wait(self.tick_s)
            self._wake.clear()
            with self._lock:
                self._expire_locked(time.time())
                item = self._queue.popleft() if self._queue else None
            if item is not None:
                self._decode(item)
        with self._lock:
            self._flush_locked("stop")

    def _expire_locked(self, now):
        if not self.deadline_s:
            return
        keep = deque()
        while self._queue:
            item = self._queue.popleft()
            if now - item["queued_at"] >= self.deadline_s:
                self._out.append(self._release(item))
                self.expired += 1
                self._note(
                    f"REDUX_LIVE_EXPIRED start={item['start']} "
                    f"deadline_s={self.deadline_s} -- the live line shipped instead")
            else:
                keep.append(item)
        self._queue.extend(keep)

    def _flush_locked(self, why):
        """Release everything still held, as the live text. Only reached from
        `stop()`, and only for work that never got a decode.

        ORDER MATTERS: the in-flight segment was captured FIRST, so it is
        released first. Releasing the queue first would publish line N+1
        before line N and scramble the transcript's order.
        """
        if self._inflight is not None:
            self._out.append(self._release(self._inflight))
            self._inflight = None
        while self._queue:
            self._out.append(self._release(self._queue.popleft()))

    def _release(self, item):
        """The live line, unchanged, plus the counter and the note that say the
        Redux pass did NOT answer this one.

        The marker is what makes a release IDEMPOTENT: `stop()` releases the
        in-flight segment and then that decode finishes a moment later, and
        without the marker the same line would be published twice.
        """
        item["released"] = True
        self.fallbacks += 1
        return dict(item["event"])

    def _decode(self, item):
        """ONE segment, ONE backend call. The PCM snapshot was taken under the
        lock in `hold_live_final` and the decode runs OUTSIDE it, so the audio
        path never waits on the model."""
        self._inflight = item
        wall = None
        text = ""
        error = None
        try:
            started = time.perf_counter()
            result = self.backend.transcribe(item["pcm"])
            wall = time.perf_counter() - started
            text = result[0] if isinstance(result, (tuple, list)) else result
            text = "" if text is None else str(text).strip()
        except Exception as exc:                     # reported, never re-raised
            error = exc
        finally:
            self._inflight = None
        # Already released by a concurrent `stop()`/`_expire_locked` -- the
        # decode finished after the line was given back, so its result is
        # dropped rather than published a second time.
        if item.get("released"):
            return
        if error is not None:
            with self._lock:
                self.failures += 1
                self._out.append(self._release(item))
            self._note(f"REDUX_LIVE_DECODE_FAILED start={item['start']} "
                       f"reason={type(error).__name__} error={error!r} -- "
                       f"the live line shipped instead")
            return
        seconds = item["pcm"].size / float(self.sr)
        # A decode that outran its deadline is released as the live text: the
        # line is already late, and a late Redux line is worse than the live
        # one the owner can read now.
        if self.deadline_s and wall > self.deadline_s:
            with self._lock:
                self.expired += 1
                self._out.append(self._release(item))
            self._note(f"REDUX_LIVE_EXPIRED start={item['start']} "
                       f"decode_s={round(wall, 3)} deadline_s={self.deadline_s} "
                       f"-- the live line shipped instead")
            return
        if self.stopped:
            with self._lock:
                self._out.append(self._release(item))
            return
        with self._lock:
            self.decodes_s.append(round(wall, 3))
            self.audio_s += seconds
            self.rss_after_mb = rss_mb()
            if not text:
                self._out.append(self._release(item))
                self._refuse("empty-text")
                return
            event = {
                "type": "caption",
                "text": text,
                "start": item["start"],
                "end": item["end"],
                "final": True,
                "producer": self.producer,
                "producerModel": self.producer_model,
                "route": "redux-live",
            }
            if item["source"] is not None:
                event["source"] = item["source"]
            self.redux_lines += 1
            self._out.append(event)
        self._note(f"REDUX_LIVE_LINE start={item['start']} "
                   f"decode_s={round(wall, 3)} audio_s={round(seconds, 2)} "
                   f"chars={len(text)}")

    def stop(self, timeout_s=15.0):
        """End of stream: release every held line as the live text, so the panel
        never waits on an overlay that is gone."""
        with self._lock:
            already = self.stopped
            self.stopped = True
            self._flush_locked("stop")
        self._stop.set()
        self._wake.set()
        if already or self._worker is None:
            return
        try:
            self._worker.join(timeout=timeout_s)
        except RuntimeError:
            pass

    # -- measurement -----------------------------------------------------------
    def stats(self):
        """The overlay's own numbers, for the run's stats block."""
        decodes = self.decodes_s[-64:]
        return {
            "reduxLive": True,
            "reduxLiveArmed": self.armed,
            "reduxLiveSegments": self.segments,
            "reduxLiveLines": self.redux_lines,
            "reduxLiveFallbacks": self.fallbacks,
            "reduxLiveFailures": self.failures,
            "reduxLiveExpired": self.expired,
            "reduxLiveOverflow": self.overflow,
            "reduxLiveDecodeMeanS": (round(sum(decodes) / len(decodes), 3)
                                     if decodes else None),
            "reduxLiveDecodeMaxS": (round(max(decodes), 3) if decodes else None),
            "reduxLiveAudioS": round(self.audio_s, 2),
            "reduxLiveRssMb": round(self.rss_after_mb, 1),
        }

    def stats_line(self):
        row = dict(self.stats())
        for key, value in row.items():
            if value is None:
                row[key] = "n/a"
        return ("REDUX_LIVE armed=%(reduxLiveArmed)s "
                "segments=%(reduxLiveSegments)d lines=%(reduxLiveLines)d "
                "fallbacks=%(reduxLiveFallbacks)d failures=%(reduxLiveFailures)d "
                "expired=%(reduxLiveExpired)d overflow=%(reduxLiveOverflow)d "
                "decode_mean_s=%(reduxLiveDecodeMeanS)s "
                "decode_max_s=%(reduxLiveDecodeMaxS)s audio_s=%(reduxLiveAudioS)s "
                "rss_mb=%(reduxLiveRssMb)s" % row)


if __name__ == "__main__":
    sys.exit(main())
