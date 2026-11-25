#!/usr/bin/env python3
# NO-BUG: o census CUDA do ORT a contradizer o provider listado pela sessao (medido 2026-11-17/23) -- trabalho de CAPACIDADE/observabilidade sobre um defeito medido, sem id no ledger
"""Model-free guard for Redux CUDA-only session creation and runtime failures.

The production constructor is exercised through ``open_onnx_sessions`` and the
reference decoder's ``InferenceSession`` calls, with a fake ORT. No ORT runtime,
model weights, audio, CUDA session, or GPU is loaded. The fake makes constructor
fallback and a later ``run()`` fallback independently observable.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
import types
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
              "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
sys.path.insert(0, str(WORKER))

REDUX_SOURCE = WORKER / "redux_live.py"
EAGER_GRAPHS = ("preprocessor.onnx", "encoder-model.onnx",
                "decoder_joint-model.onnx")
ALL_GRAPHS = EAGER_GRAPHS + ("vad-model.onnx",)
ORT_FAILURE_TEXT = "injected CUDA constructor failure"
RUN_FAILURE_TEXT = "injected CUDA run failure"
FALLBACK_ASSIGNMENT = 'kwargs["enable_fallback"] = False'
DISABLE_CALL = "                    disable_fallback()"


class FakeSessionOptions:
    def __init__(self):
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.execution_mode = None
        self.graph_optimization_level = None
        self.use_per_session_threads = True
        self.logid = ""
        self.log_severity_level = 2
        self.log_verbosity_level = 0
        self.optimized_model_filepath = ""
        self._config = {}

    def add_session_config_entry(self, key, value):
        self._config[key] = str(value)

    def get_session_config_entry(self, key):
        return self._config.get(key, "")


class FakeInput:
    name = "input_states_1"
    shape = (1, 1, 4)


class FakeNode:
    """One ORT graph node, as `get_provider_graph_assignment_info()` shows it."""

    def __init__(self, name, op_type):
        self.name = name
        self.op_type = op_type


class FakeSubgraph:
    """One EP assignment row: `ep_name` + `get_nodes()`."""

    def __init__(self, ep_name, nodes):
        self.ep_name = ep_name
        self._nodes = nodes

    def get_nodes(self):
        return list(self._nodes)


class FakeSession:
    def __init__(self, owner, providers, constructor_fallback, graph=None,
                 from_cache=False):
        self.owner = owner
        self.providers = list(providers)
        self.graph = graph
        self.from_cache = bool(from_cache)
        # Deliberately start enabled: disable_fallback() must protect run().
        self.runtime_fallback_enabled = True
        self.constructor_fallback = constructor_fallback
        self.disable_calls = 0

    def disable_fallback(self):
        self.disable_calls += 1
        self.runtime_fallback_enabled = False

    def get_providers(self):
        return list(self.providers)

    def get_inputs(self):
        return [FakeInput()]

    def get_provider_graph_assignment_info(self):
        """The census `worker/redux_live.py` requires before a session is used.

        The production loader attests every acoustic node against the pinned
        CPU-control map (`_read_node_assignment`); a fake without this method
        makes the POSITIVE arm fail with "readback is unavailable" and hides
        every guard behind it. The rows are built from the SAME pinned
        constants the loader checks, so a drift in the pinned census still
        fails the positive arm instead of being papered over here.
        """
        import redux_live as rl

        if self.from_cache:
            # MEASURED 2026-11-24 on ORT 1.30: an ORT-format initialization
            # skips the EP assignment callback, so the census is EMPTY. The
            # fake reproduces that fact, because it is the reason the cache is
            # refused; faking a populated census here would hide the defect.
            return []
        graph = self.graph
        if graph is None:
            raise RuntimeError("fake session has no graph identity")
        expected = rl.REDUX_GRAPH_NODE_COUNTS[graph]
        cpu_nodes = rl.REDUX_CONTROL_GRAPH_ALLOWLIST.get(graph, (None, {}))[1]
        cuda_count = expected - len(cpu_nodes)
        rows = [FakeSubgraph("CUDAExecutionProvider", [None] * cuda_count)]
        if cpu_nodes:
            rows.append(FakeSubgraph(
                "CPUExecutionProvider",
                [FakeNode(name, op_type) for name, op_type in cpu_nodes.items()]))
        return rows

    def run(self, *_args, **_kwargs):
        if not self.owner.run_fail:
            return []
        if self.runtime_fallback_enabled:
            self.owner.cpu_run_retries += 1
            return []
        raise RuntimeError(RUN_FAILURE_TEXT)


def make_reference(mode):
    """Return a decoder reference wired to a fake ORT implementation."""
    class FakeOrt:
        __version__ = "1.30.0"
        ExecutionMode = types.SimpleNamespace(ORT_SEQUENTIAL="sequential")
        GraphOptimizationLevel = types.SimpleNamespace(
            ORT_DISABLE_ALL="disable_all", ORT_ENABLE_ALL="enable_all")

        def __init__(self):
            self.calls = []
            self.sessions = []
            self.cpu_constructor_retries = 0
            self.cpu_run_retries = 0
            self.run_fail = False

        @staticmethod
        def SessionOptions():
            return FakeSessionOptions()

        def InferenceSession(self, path, sess_options=None, *args, **kwargs):
            # The production loader sets `logid` to the GRAPH BASENAME before
            # construction, and the cached `.ort` path does not carry it.
            graph = (str(getattr(sess_options, "logid", "") or "")
                     or Path(path).name)
            from_cache = str(path).lower().endswith(".ort")
            providers = [str(item[0] if isinstance(item, (tuple, list)) else item)
                         for item in kwargs.get("providers", ())]
            enable_fallback = kwargs.get("enable_fallback", 1)
            guard = sess_options.get_session_config_entry(
                "session.disable_cpu_ep_fallback")
            self.calls.append((graph, providers, guard, enable_fallback))
            optimized_path = str(
                getattr(sess_options, "optimized_model_filepath", "") or "")
            if optimized_path:
                Path(optimized_path).write_bytes(b"\x14\0\0\0ORTMfake")
            if "CUDAExecutionProvider" not in providers:
                self.cpu_constructor_retries += 1
                return FakeSession(self, ["CPUExecutionProvider"], enable_fallback,
                                   graph, from_cache=from_cache)
            if mode == "cuda-absent":
                raise RuntimeError(ORT_FAILURE_TEXT)
            if mode == "constructor-fallback" and enable_fallback:
                self.cpu_constructor_retries += 1
                return FakeSession(self, ["CPUExecutionProvider"], enable_fallback,
                                   graph, from_cache=from_cache)
            return FakeSession(
                self, ["CUDAExecutionProvider", "CPUExecutionProvider"],
                enable_fallback, graph, from_cache=from_cache)

    class FakeVocabulary:
        blank_id = 0

        def __init__(self, _path):
            pass

    class FakeBase:
        def speech_regions(self, _pcm):
            return []

    return types.SimpleNamespace(
        OnnxParakeet=FakeBase,
        Vocabulary=FakeVocabulary,
        ort=FakeOrt(),
    )


class ImmediateFuture:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def result(self):
        if self.error is not None:
            raise self.error
        return self.value

    def cancel(self):
        return False


class InlineExecutor:
    """Execute fake session jobs inline so the oracle creates no worker threads."""
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def submit(self, fn, *args, **kwargs):
        try:
            return ImmediateFuture(fn(*args, **kwargs))
        except BaseException as exc:  # Preserve the future's normal error surface.
            return ImmediateFuture(error=exc)


def make_model_dir(temp: Path):
    import json

    temp.mkdir(parents=True, exist_ok=True)
    if not (temp / "config.json").is_file():
        (temp / "config.json").write_text(json.dumps({
            "durations": [1], "vocab_size": 1, "max_tokens_per_step": 1,
            "encoder_frame_seconds": 0.02, "blank_token_id": 0,
        }), encoding="utf-8")
        (temp / "vocab.txt").write_text("<blk> 0\n", encoding="utf-8")
    for name in ALL_GRAPHS:
        if not (temp / name).is_file():
            (temp / name).write_bytes(b"fake-graph:" + name.encode("ascii"))
    return temp


def fake_hash_factory(rl):
    values = {
        "preprocessor.onnx": rl.REDUX_PREPROCESSOR_CONTROL_SHA256,
        "encoder-model.onnx": rl.REDUX_ENCODER_CONTROL_SHA256,
        "vad-model.onnx": rl.REDUX_VAD_CONTROL_SHA256,
    }
    original = rl._file_sha256

    def fake_hash(path):
        return values.get(Path(path).name) or original(path)

    return fake_hash


def open_fake_sessions(rl, mode, temp):
    """Exercise the production loader without ORT threads or real sessions."""
    reference = make_reference(mode)
    old_executor = rl.ThreadPoolExecutor
    old_hash = rl._file_sha256
    old_submit_hash = rl._submit_control_graph_hash
    old_hash_executor = rl._CONTROL_HASH_EXECUTOR
    rl.ThreadPoolExecutor = InlineExecutor
    rl._file_sha256 = fake_hash_factory(rl)
    rl._submit_control_graph_hash = lambda path: ImmediateFuture(
        (rl._file_sha256(path), 0.0))
    rl._CONTROL_HASH_EXECUTOR = None
    try:
        result = rl.open_onnx_sessions(
            reference, make_model_dir(temp), threads=1,
            provider_names=["CUDAExecutionProvider"], allow_cpu_fallback=False)
        # Exercise deferred VAD before restoring the scoped fake hash source.
        if result[0]._sotto_vad_exists:
            result[0].vad = result[0]._sotto_session_factory("vad-model.onnx")
            result[0]._sotto_vad_deferred = False
        return {"reference": reference, "result": result, "raised": None}
    except Exception as exc:  # The arms assert the specific refusal path.
        return {"reference": reference, "result": None, "raised": exc}
    finally:
        rl.ThreadPoolExecutor = old_executor
        rl._file_sha256 = old_hash
        rl._submit_control_graph_hash = old_submit_hash
        rl._CONTROL_HASH_EXECUTOR = old_hash_executor


def assert_calls_match_pinned_policy(calls, rl):
    """Every constructor call must carry the pinned provider/fallback policy.

    Shape/control graphs (`REDUX_CONTROL_GRAPH_ALLOWLIST`) add the CPU EP and
    set `disable_cpu_ep_fallback=0`; acoustic graphs stay CUDA-only with the
    fallback switch at "1". Both are created with `enable_fallback=False`, so a
    CUDA setup failure cannot silently retry on CPU.
    """
    for graph, providers, guard, enable_fallback in calls:
        control = graph in rl.REDUX_CONTROL_GRAPH_ALLOWLIST
        expected = (["CUDAExecutionProvider", "CPUExecutionProvider"] if control
                    else ["CUDAExecutionProvider"])
        assert providers == expected, (graph, providers)
        assert guard == ("0" if control else "1"), (graph, guard)
        assert enable_fallback == 0, (graph, enable_fallback)


def arm_cuda_success_and_run_failure(temp):
    import redux_live as rl

    out = open_fake_sessions(rl, "cuda-works", temp)
    assert out["raised"] is None, "CUDA fake failed: %r" % out["raised"]
    model, proxy, device, failure = out["result"]
    assert device == "cuda" and failure is None, (device, failure)

    # The helper above loads lazy VAD via the production closure without PCM.
    assert set(proxy.options_readback) == set(ALL_GRAPHS), proxy.options_readback
    assert set(proxy.runtime_fallback_readback) == set(ALL_GRAPHS), (
        proxy.runtime_fallback_readback)
    for name, row in proxy.options_readback.items():
        control = name in rl.REDUX_CONTROL_GRAPH_ALLOWLIST
        assert row["disable_cpu_ep_fallback"] == ("0" if control else "1"), (name, row)
        assert row["runtime_fallback_disabled"] is True, (name, row)
    # A CENSURA DE NOS TEM DE TER CORRIDO PARA TODOS OS GRAFOS (2026-11-23):
    # `_read_node_assignment` e' a admissao antes de usar um grafo neural. Um
    # fake sem `get_provider_graph_assignment_info()` fazia o POSITIVO falhar em
    # "readback is unavailable" e escondia todos os guardas atras dele.
    assert set(proxy.node_assignment_readback) == set(ALL_GRAPHS), (
        proxy.node_assignment_readback)
    assert int(proxy.node_assignment_readback["encoder-model.onnx"]["total_nodes"]) == (
        rl.REDUX_GRAPH_NODE_COUNTS["encoder-model.onnx"]), (
        proxy.node_assignment_readback["encoder-model.onnx"])

    calls = out["reference"].ort.calls
    assert {row[0] for row in calls} == set(ALL_GRAPHS), calls
    assert_calls_match_pinned_policy(calls, rl)
    sessions = [model.preprocessor, model.encoder, model.decoder_joint, model.vad]
    assert all(session.disable_calls == 1 for session in sessions), (
        [session.disable_calls for session in sessions])

    # Reopen the same fixture: the optimized cache must now be BYPASSED, not
    # served. MEASURED 2026-11-24: an ORT-format session publishes ZERO rows
    # from `get_provider_graph_assignment_info()`, so serving the cache makes
    # the next start die with "assignment readback is empty or unbounded" (the
    # owner's live log, 07:55). A bypassed cache is the only attested load.
    cached = open_fake_sessions(rl, "cuda-works", temp)
    assert cached["raised"] is None, cached["raised"]
    _cached_model, cached_proxy, _cached_device, _cached_failure = cached["result"]
    assert set(cached_proxy.node_assignment_readback) == set(ALL_GRAPHS), (
        cached_proxy.node_assignment_readback)
    assert all(cached_proxy.session_cache_readback.get(name, {}).get("mode")
               == "bypass-placement-attestation"
               for name in ("preprocessor.onnx", "encoder-model.onnx")), (
        cached_proxy.session_cache_readback)
    assert not (Path(temp) / rl.REDUX_ORT_CACHE_DIR).exists() or not any(
        (Path(temp) / rl.REDUX_ORT_CACHE_DIR).glob("*.ort")), (
        "a cache that cannot be attested was published again")
    assert_calls_match_pinned_policy(cached["reference"].ort.calls, rl)

    out["reference"].ort.run_fail = True
    for graph, session in zip(ALL_GRAPHS, sessions):
        try:
            session.run(None, {})
        except RuntimeError as exc:
            assert str(exc) == RUN_FAILURE_TEXT, (graph, exc)
        else:
            raise AssertionError("%s run failure was swallowed or retried" % graph)
    assert out["reference"].ort.cpu_run_retries == 0


def arm_cache_bypass_is_attestation_driven(temp):
    """Both directions of the cache refusal, with the measured ORT behaviour.

    MEASURED 2026-11-24 on ORT 1.30: an ORT-format session returns ZERO rows
    from `get_provider_graph_assignment_info()`. The loader's admission
    condition is that census, so the cache must be refused exactly when the
    session is required to publish it -- and only then.
    """
    import redux_live as rl

    reference = make_reference("cuda-works")
    model_dir = make_model_dir(temp)
    proxy = rl._ReduxControlOnlyOrtProxy(reference.ort, model_dir)
    providers = [("CUDAExecutionProvider", {}), ("CPUExecutionProvider", {})]
    graph = model_dir / "preprocessor.onnx"

    # The production proxy's SessionOptions() adds exactly this entry.
    attested = proxy.SessionOptions()
    attested.add_session_config_entry("session.disable_cpu_ep_fallback", "0")
    attested.add_session_config_entry("session.record_ep_graph_assignment_info", "1")
    attested.intra_op_num_threads = 1
    assert rl._placement_attestation_required(attested), (
        "the attested options lost the census requirement")
    assert proxy._cache_identity(graph, attested, providers) is None, (
        "an attested session was still allowed to serve the ORT cache")

    plain = FakeSessionOptions()
    plain.add_session_config_entry("session.disable_cpu_ep_fallback", "0")
    plain.intra_op_num_threads = 1
    assert not rl._placement_attestation_required(plain)
    assert proxy._cache_identity(graph, plain, providers) is not None, (
        "the cache refusal was not caused by the census requirement")

    from_cache = reference.ort.InferenceSession(
        str(graph) + ".ort", attested, providers=providers)
    assert from_cache.get_provider_graph_assignment_info() == [], (
        "the fake must reproduce ORT 1.30: an ORT-format load publishes no rows")


def arm_cuda_absent_refuses_cpu(temp):
    import redux_live as rl

    out = open_fake_sessions(rl, "cuda-absent", temp)
    assert out["raised"] is not None, "CUDA failure was accepted"
    assert ORT_FAILURE_TEXT in str(out["raised"]), out["raised"]
    calls = out["reference"].ort.calls
    assert calls, calls
    assert_calls_match_pinned_policy(calls, rl)
    assert out["reference"].ort.cpu_constructor_retries == 0, calls


def arm_cpu_routes_refused(temp):
    import redux_live as rl

    reference = make_reference("cuda-works")
    model_dir = make_model_dir(temp)
    for providers, allow_fallback in ((["CPUExecutionProvider"], False),
                                      (["CUDAExecutionProvider"], True)):
        try:
            rl.open_onnx_sessions(
                reference, model_dir, threads=1, provider_names=providers,
                allow_cpu_fallback=allow_fallback)
        except RuntimeError as exc:
            assert "CPU inference fallback disabled" in str(exc), exc
        else:
            raise AssertionError("CPU provider/fallback route was accepted")
    assert reference.ort.calls == [], reference.ort.calls


def load_mutant(mutated_source, suffix):
    name = "redux_live_%s" % suffix
    module = types.ModuleType(name)
    module.__file__ = str(REDUX_SOURCE)
    sys.modules[name] = module
    try:
        exec(compile(mutated_source, str(REDUX_SOURCE), "exec"), module.__dict__)
    except Exception:
        sys.modules.pop(name, None)
        raise
    return module


def arm_constructor_fallback_mutation(temp):
    source = REDUX_SOURCE.read_text(encoding="utf-8")
    assert source.count(FALLBACK_ASSIGNMENT) == 1, (
        "constructor fallback mutation anchor is not unique")
    mutant = load_mutant(source.replace(FALLBACK_ASSIGNMENT,
                                        'kwargs["enable_fallback"] = True'),
                         "constructor_fallback")
    out = open_fake_sessions(mutant, "constructor-fallback", temp)
    assert out["raised"] is not None, (
        "constructor fallback mutation was accepted by the production loader")
    assert "did not load CUDAExecutionProvider" in str(out["raised"]), out["raised"]
    assert out["reference"].ort.cpu_constructor_retries == len(EAGER_GRAPHS), (
        out["reference"].ort.calls)


def arm_run_fallback_mutation(temp):
    source = REDUX_SOURCE.read_text(encoding="utf-8")
    assert source.count(DISABLE_CALL) == 1, "run fallback mutation anchor is not unique"
    mutant = load_mutant(source.replace(DISABLE_CALL,
                                        "                    pass  # mutation: keep run fallback"),
                         "run_fallback")
    out = open_fake_sessions(mutant, "cuda-works", temp)
    assert out["raised"] is None, out["raised"]
    model, _proxy, _device, _failure = out["result"]
    out["reference"].ort.run_fail = True
    sessions = [model.preprocessor, model.encoder, model.decoder_joint]
    try:
        for session in sessions:
            session.run(None, {})
    except RuntimeError as exc:
        assert str(exc) == "Redux GPU-only session fallback guard did not read back disabled", (
            exc)
    else:
        if out["reference"].ort.cpu_run_retries:
            print("EXPECTED-RED -- disabling runtime fallback removed; fake CPU retry observed")
            return
        raise AssertionError("run fallback mutation escaped the fake failure arm")
    raise AssertionError("run fallback mutation was rejected for an unexpected reason")


def arm_node_readback_skipped_mutation(temp):
    """Removing the admission census must be observable, not silent.

    The positive arm requires `node_assignment_readback` for every graph; this
    mutant deletes the production call and the same assertion must go empty.
    """
    source = REDUX_SOURCE.read_text(encoding="utf-8")
    anchor = "            self._read_node_assignment(graph.name, session)\n"
    assert source.count(anchor) == 1, "node-assignment anchor is not unique"
    mutant = load_mutant(
        source.replace(anchor,
                       "            pass  # mutation: node census removed\n", 1),
        "no_node_readback")
    out = open_fake_sessions(mutant, "cuda-works", temp)
    assert out["raised"] is None, out["raised"]
    _model, proxy, _device, _failure = out["result"]
    assert set(proxy.node_assignment_readback) != set(ALL_GRAPHS), (
        "removing the node-assignment census was not caught by readback coverage")


def positive():
    scratch = ROOT / ".agent-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sotto-redux-cuda-fallback-",
                                     dir=scratch) as temp:
        root = Path(temp)
        arm_cuda_success_and_run_failure(root / "success")
        arm_cache_bypass_is_attestation_driven(root / "cache-bypass")
        arm_cuda_absent_refuses_cpu(root / "absent")
        arm_cpu_routes_refused(root / "cpu-routes")
    return 4


def negative():
    scratch = ROOT / ".agent-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="sotto-redux-cuda-fallback-neg-",
                                     dir=scratch) as temp:
        root = Path(temp)
        arm_constructor_fallback_mutation(root / "constructor")
        print("EXPECTED-RED -- constructor fallback mutation rejected before CPU inference")
        arm_run_fallback_mutation(root / "run")
        print("EXPECTED-RED -- run fallback mutation kept a CPU retry")
        arm_node_readback_skipped_mutation(root / "no-readback")
        print("EXPECTED-RED -- node-assignment census removal left readback empty")
    return 3


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true",
                        help="run positive fake coverage and targeted fallback mutations")
    parser.add_argument("--neg-arm", action="store_true",
                        help="run only targeted mutations; nonzero means caught")
    args = parser.parse_args()
    if args.neg_arm:
        caught = negative()
        print("NEG-ARM: PASS (%d/3 fallback+readback mutations caught)" % caught)
        return 1
    checked = positive()
    if checked != 4:
        raise AssertionError("positive coverage changed: %d" % checked)
    if threading.active_count() != 1:
        raise AssertionError("fake oracle exceeded one Python thread")
    if args.selftest:
        caught = negative()
        if caught != 3:
            raise AssertionError("fallback mutation coverage changed: %d" % caught)
        if threading.active_count() != 1:
            raise AssertionError("fallback mutation oracle exceeded one Python thread")
        print("SELFTEST: PASS (positive 4/4; constructor/run/readback mutations 3/3 caught)")
        return 0
    print("POSITIVE: PASS (GPU-only guards 4/4 incl. node census; cache refused "
          "when unattestable; CPU routes refused 2/2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
