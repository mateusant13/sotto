#!/usr/bin/env python3
# NO-BUG: a mesma classe CUDA/ORT do caminho de stream do Nemotron, julgada com sessoes falsas -- trabalho de CAPACIDADE/observabilidade; o ledger nao tem id para ela
"""Model-free gate for the current Nemotron GPU-only session policy.

ORT can list CUDA in a session-provider readback while its device census reports
no CUDA device. A positive device census, disabled constructor retry, construction-
time CPU-node fallback guard, disabled Python `run()` fallback, and CUDA readback
from all three acoustic graphs are required. False or unknown census evidence
fails closed before graph session creation; CPU inference is never a fallback.
Fake ORT arms use tiny placeholder files and no model/audio/GPU. Negative
mutations remove each claimed guard and must be caught at its adverse arm.
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import types
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
              "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker"
sys.path.insert(0, str(WORKER))

WORKER_SOURCE = WORKER / "sotto_worker.py"
CUDA_RUNTIME_SOURCE = WORKER / "ort_cuda_runtime.py"

#: The runtime's own message, byte-for-byte as it reached the owner's log.
ORT_FAILURE_TEXT = (
    "[ONNXRuntimeError] : 1 : FAIL : This session contains graph nodes that are "
    "assigned to the default CPU EP, but fallback to CPU EP has been explicitly "
    "disabled by the user."
)
CPU_FAILURE_TEXT = (
    "[ONNXRuntimeError] : 1 : FAIL : CPU execution provider session creation "
    "failed (injected)"
)
GRAPHS = ("encoder.onnx", "decoder.onnx", "joint.onnx")
#: The mutant removes the positive CUDA-device-census requirement.
MUTANT_ANCHOR = (
    "    if registered is not True:\n"
    "        diagnostics = _asr_cuda_refusal_diagnostics(\n"
    "            ort, registered, device_names, cuda_preload_error)"
)
MUTANT_REPLACEMENT = "    if False:"
MUTANT_PRELOAD_ANCHOR = (
    '        diagnostics = _asr_cuda_refusal_diagnostics(\n'
    '            ort, registered, device_names, cuda_preload_error)'
)
MUTANT_PRELOAD_REPLACEMENT = '        diagnostics = ""'
PRELOAD_FAILURE_TEXT = "OSError: injected preload banner\ncontinued"
MUTANT_AUTO_CPU_ANCHOR = '    order = [p for p in req if p in available]\n'
MUTANT_AUTO_CPU_REPLACEMENT = (
    MUTANT_AUTO_CPU_ANCHOR
    + '    if auto and "CPUExecutionProvider" in available:\n'
    + '        order.append("CPUExecutionProvider")\n'
)
MUTANT_PLUGIN_REGISTER_ANCHOR = (
    "    _asr_register_cuda_plugin_if_needed(ort)\n"
    "    return True\n"
)
MUTANT_PLUGIN_REGISTER_REPLACEMENT = "    return True\n"
MUTANT_PLUGIN_RECHECK_ANCHOR = (
    "    registered, device_names = cuda_device_census(ort)\n"
    "    if registered is not True:\n"
    "        raise RuntimeError(\n"
    '            "explicit CUDA plugin registration did not expose a CUDA EP device "\n'
    '            "(devices=%s)" % (",".join(device_names) or "none"))\n'
)
MUTANT_PLUGIN_RECHECK_REPLACEMENT = "    return True\n"
MUTANT_RUNTIME_FALLBACK_ANCHOR = "    disable_fallback()\n"
MUTANT_RUNTIME_FALLBACK_REPLACEMENT = "    return session\n"
MUTANT_CONSTRUCTOR_FALLBACK_ANCHOR = "enable_fallback=0"
MUTANT_CONSTRUCTOR_FALLBACK_REPLACEMENT = "enable_fallback=1"


# ── the fakes ────────────────────────────────────────────────────────────────
class FakeSessionOptions:
    def __init__(self):
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.execution_mode = None
        self.graph_optimization_level = None
        self.log_severity_level = 3
        self.log_verbosity_level = 0
        self._config = {}

    def add_session_config_entry(self, key, value):
        self._config[key] = str(value)

    def get_session_config_entry(self, key):
        return self._config.get(key, "")


class FakeInput:
    name = "audio_signal"
    shape = (1, 128, 17)


class FakeSession:
    def __init__(self, providers):
        self._providers = list(providers)
        self.closed = False
        self._enable_fallback = True
        self.disable_fallback_calls = 0
        self.fallback_attempts = 0

    def get_providers(self):
        return list(self._providers)

    def get_inputs(self):
        return [FakeInput()]

    def close(self):
        self.closed = True

    def disable_fallback(self):
        self.disable_fallback_calls += 1
        self._enable_fallback = False

    def run(self, *_args, **_kwargs):
        """Model ORT's Python retry switch around an injected GPU run failure."""
        if self._enable_fallback:
            self.fallback_attempts += 1
            return ["cpu-fallback"]
        raise RuntimeError("injected CUDA run failure")


class FakeOrt:
    """ORT 1.30-shaped: a provider can be LISTED while no device is registered."""

    def __init__(self, mode, cuda_device):
        # Keep this oracle independent of the installed ORT runtime and DLLs.
        # The production helper only needs these enum-shaped values for options.
        self.ExecutionMode = types.SimpleNamespace(ORT_SEQUENTIAL=0)
        self.GraphOptimizationLevel = types.SimpleNamespace(
            ORT_DISABLE_ALL=0, ORT_ENABLE_BASIC=1, ORT_ENABLE_ALL=2)
        self.__version__ = "1.30.0"
        self.__file__ = r"H:\fake\onnxruntime\__init__.py"
        self.mode = mode
        self.cuda_device = bool(cuda_device)
        self.calls = []
        self.census_calls = 0
        self.register_calls = []
        self.preload_calls = 0
        self.constructor_fallback_values = []
        self.constructor_fallback_attempts = 0

    def get_build_info(self):
        if self.mode in ("legacy-no-plugin-flag", "legacy-registration",
                         "registration-fails", "registration-no-device"):
            return "build metadata, private-build-marker=do-not-report"
        return "build metadata, cuda-plugin-ep=1, private-build-marker=do-not-report"

    def get_available_providers(self):
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]

    def preload_dlls(self):
        self.preload_calls += 1

    def register_execution_provider_library(self, name, path):
        self.register_calls.append((name, str(path)))
        if self.mode not in ("legacy-registration", "registration-no-device"):
            raise RuntimeError("injected CUDA plugin registration failure")
        if name != "CUDAExecutionProvider" or not Path(path).is_file():
            raise RuntimeError("CUDA plugin library was not the packaged DLL")
        if self.mode == "legacy-registration":
            self.cuda_device = True

    def get_ep_devices(self):
        self.census_calls += 1
        if self.mode == "census-unknown":
            raise RuntimeError("device census unavailable (injected)")
        devices = [types.SimpleNamespace(ep_name="CPUExecutionProvider")]
        if self.cuda_device:
            devices.append(types.SimpleNamespace(ep_name="CUDAExecutionProvider"))
        return devices

    def SessionOptions(self):
        return FakeSessionOptions()

    def InferenceSession(self, path, sess_options=None, providers=None,
                         enable_fallback=1):
        names = [str(item[0] if isinstance(item, (tuple, list)) else item)
                 for item in (providers or ())]
        self.constructor_fallback_values.append(enable_fallback)
        guard = (sess_options.get_session_config_entry(
            "session.disable_cpu_ep_fallback") if sess_options is not None else "")
        graph = Path(path).name
        self.calls.append((graph, list(names), guard))
        cuda = "CUDAExecutionProvider" in names
        if cuda:
            if self.mode == "constructor-fallback":
                if enable_fallback:
                    self.constructor_fallback_attempts += 1
                    # Model ORT constructor recovery before Python receives the
                    # session object; post-construction disable_fallback cannot undo this.
                    return FakeSession(["CPUExecutionProvider"])
                return FakeSession(["CUDAExecutionProvider", "CPUExecutionProvider"])
            if self.mode in ("cuda-works", "legacy-registration"):
                return FakeSession(["CUDAExecutionProvider", "CPUExecutionProvider"])
            if self.mode in ("cuda-absent", "cpu-also-fails"):
                raise RuntimeError(ORT_FAILURE_TEXT)
            if self.mode == "lying-readback":
                # Adverse case: device census says no CUDA while every session
                # lies by listing CUDA in provider readback.
                return FakeSession(["CUDAExecutionProvider",
                                    "CPUExecutionProvider"])
            if self.mode == "control-nodes":
                if guard == "1":
                    raise RuntimeError(ORT_FAILURE_TEXT)
                return FakeSession(["CUDAExecutionProvider", "CPUExecutionProvider"])
            if self.mode == "silent-fallback":
                if guard == "1":
                    raise RuntimeError(ORT_FAILURE_TEXT)
                return FakeSession(["CPUExecutionProvider"])
            raise AssertionError("unexpected CUDA mode %r" % (self.mode,))
        if names == ["CPUExecutionProvider"]:
            if self.mode == "cpu-also-fails":
                raise RuntimeError(CPU_FAILURE_TEXT)
            return FakeSession(["CPUExecutionProvider"])
        raise AssertionError("unexpected provider request: %r" % (names,))


def make_model_dir(root: Path, graphs=GRAPHS) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for name in graphs:
        (root / name).write_bytes(b"fixture")
    return root


SHARE = {"total": 2, "live": 2, "small": 1, "batch": 2}


def run_arm(mode: str, cuda_device: bool, temp: Path, providers=None, emulated=None,
            cuda_preload_error: str = ""):
    module = emulated or __import__("sotto_worker")
    ort = FakeOrt(mode, cuda_device)
    logs = []
    model_dir = make_model_dir(temp)
    try:
        result = module.open_asr_sessions(
            ort, str(model_dir), (providers if providers is not None
                                  else ["CUDAExecutionProvider"]),
            ab="", share=dict(SHARE), log=logs.append,
            cuda_preload_error=cuda_preload_error)
    except Exception as exc:  # noqa: BLE001 -- the arm decides what a raise means
        return {"raised": exc, "logs": logs, "ort": ort, "result": None}
    return {"raised": None, "logs": logs, "ort": ort, "result": result}


# ── the arms ─────────────────────────────────────────────────────────────────
def arm_cuda_absent(temp: Path) -> None:
    out = run_arm("cuda-absent", False, temp)
    assert out["raised"] is not None, "missing CUDA device was accepted"
    assert "census=cuda-missing" in str(out["raised"]), out["raised"]
    assert out["ort"].calls == [], out["ort"].calls
    assert out["logs"] == [], out["logs"]


def run_choose_providers(requested, available, emulated=None):
    module = emulated or __import__("sotto_worker")
    fake = types.ModuleType("onnxruntime")
    fake.get_available_providers = lambda: list(available)
    prior = sys.modules.get("onnxruntime")
    sys.modules["onnxruntime"] = fake
    try:
        return module.choose_providers(requested)
    finally:
        if prior is None:
            sys.modules.pop("onnxruntime", None)
        else:
            sys.modules["onnxruntime"] = prior


def arm_auto_cuda_only(_temp: Path, emulated=None) -> None:
    providers, available, _note, _probe = run_choose_providers(
        "auto", ["CUDAExecutionProvider", "CPUExecutionProvider"],
        emulated=emulated)
    assert available == ["CUDAExecutionProvider", "CPUExecutionProvider"], available
    assert providers == ["CUDAExecutionProvider"], (
        "auto selected a non-CUDA provider or mixed list: %r" % (providers,))


def arm_auto_cpu_only(temp: Path, emulated=None) -> None:
    providers, _available, _note, _probe = run_choose_providers(
        "auto", ["CPUExecutionProvider"], emulated=emulated)
    assert providers == [], "auto requested CPU when CUDA was absent: %r" % (providers,)
    out = run_arm("cuda-absent", False, temp, providers=providers,
                  emulated=emulated)
    assert out["raised"] is not None, "empty GPU request was accepted"
    assert "requires CUDAExecutionProvider exclusively" in str(out["raised"]), out["raised"]
    assert out["ort"].calls == [], out["ort"].calls


def arm_cuda_works(temp: Path, emulated=None) -> None:
    out = run_arm("cuda-works", True, temp, emulated=emulated)
    assert out["raised"] is None, out["raised"]
    assert out["logs"] == [], (
        "a working GPU printed a degradation line: %r" % (out["logs"],))
    res = out["result"]
    assert res["device"] == "cuda", res["device"]
    assert res["cpu_ep_fallback_disabled"] is True, res
    assert res["runtime_fallback_disabled"] is True, res
    assert res["gpu_failure"] is None, res["gpu_failure"]
    assert res["providers"][0] == "CUDAExecutionProvider", res["providers"]
    for graph, actual in res["readback"].items():
        assert "CUDAExecutionProvider" in actual, (graph, actual)
    assert [(names, guard) for _graph, names, guard in out["ort"].calls] == [
        (["CUDAExecutionProvider"], "1")] * 3, out["ort"].calls
    for graph, session in res["sessions"].items():
        try:
            session.run()
        except RuntimeError as exc:
            assert "injected CUDA run failure" in str(exc), exc
        else:
            raise AssertionError(
                "runtime fallback remained enabled after run error for %s" % graph)
        assert session.disable_fallback_calls == 1, (graph, session.disable_fallback_calls)
        assert session.fallback_attempts == 0, (graph, session.fallback_attempts)
        assert session._enable_fallback is False, graph
    assert out["ort"].constructor_fallback_values == [0, 0, 0], (
        out["ort"].constructor_fallback_values)
    assert res["load_phases_s"]["sessions_total"] >= 0.0, res["load_phases_s"]


def arm_constructor_fallback_disabled(temp: Path, emulated=None) -> None:
    out = run_arm("constructor-fallback", True, temp, emulated=emulated)
    assert out["raised"] is None, (
        "CUDA constructor fallback was not disabled: %s" % out["raised"])
    assert out["ort"].constructor_fallback_values == [0, 0, 0], (
        out["ort"].constructor_fallback_values)
    assert out["ort"].constructor_fallback_attempts == 0, (
        out["ort"].constructor_fallback_attempts)
    assert all("CUDAExecutionProvider" in names
               for names in out["result"]["readback"].values()), out["result"]["readback"]


def arm_cuda_probe_fallback_disabled(_temp: Path) -> None:
    module = __import__("sotto_worker")
    ort = FakeOrt("cuda-works", True)
    probe = module._asr_cuda_probe(
        ort, {"joint": "joint.onnx"}, ["CUDAExecutionProvider"],
        ab="", share=dict(SHARE))
    assert probe["ok"] is True, probe
    assert probe["runtime_fallback_disabled"] is True, probe
    assert probe["readback"] and "CUDAExecutionProvider" in probe["readback"], probe
    assert ort.calls == [("joint.onnx", ["CUDAExecutionProvider"], "1")], ort.calls
    assert ort.constructor_fallback_values == [0], ort.constructor_fallback_values
    assert ort.constructor_fallback_attempts == 0, ort.constructor_fallback_attempts
    session = probe["session"]
    try:
        session.run()
    except RuntimeError as exc:
        assert "injected CUDA run failure" in str(exc), exc
    else:
        raise AssertionError(
            "runtime fallback remained enabled after CUDA probe run error")
    assert session.disable_fallback_calls == 1, session.disable_fallback_calls
    assert session.fallback_attempts == 0, session.fallback_attempts
    assert session._enable_fallback is False


def _fake_plugin_ort(temp: Path, mode: str) -> FakeOrt:
    ort = FakeOrt(mode, False)
    capi = temp / "fake-ort" / "onnxruntime" / "capi"
    capi.mkdir(parents=True)
    dll_name = ("onnxruntime_providers_cuda.dll" if os.name == "nt"
                else "libonnxruntime_providers_cuda.so")
    (capi / dll_name).write_bytes(b"fake provider library")
    ort.__file__ = str(capi.parent / "__init__.py")
    return ort


def arm_legacy_plugin_registration(temp: Path, emulated=None) -> None:
    module = emulated or __import__("sotto_worker")
    ort = _fake_plugin_ort(temp, "legacy-registration")
    module._preload_cuda_runtime(ort)
    try:
        result = module.open_asr_sessions(
            ort, str(make_model_dir(temp / "model")), ["CUDAExecutionProvider"],
            share=dict(SHARE), log=lambda _line: None)
    except Exception as exc:  # noqa: BLE001 -- keep the target assertion explicit
        raise AssertionError(
            "unmarked ORT CUDA plugin was not registered before its device census: %s"
            % exc) from exc
    assert len(ort.register_calls) == 1, ort.register_calls
    assert ort.register_calls[0][0] == "CUDAExecutionProvider", ort.register_calls
    assert ort.preload_calls == 1, ort.preload_calls
    assert result["cpu_ep_fallback_disabled"] is True, result
    assert len(result["readback"]) == 3, result["readback"]
    assert all("CUDAExecutionProvider" in names
               for names in result["readback"].values()), result
    assert [(names, guard) for _graph, names, guard in ort.calls] == [
        (["CUDAExecutionProvider"], "1")] * 3, ort.calls


def arm_plugin_registration_failure(temp: Path) -> None:
    module = __import__("sotto_worker")
    ort = _fake_plugin_ort(temp, "registration-fails")
    try:
        module._preload_cuda_runtime(ort)
    except Exception as exc:  # noqa: BLE001 -- target failure path is the assertion
        preload_error = "%s: %s" % (type(exc).__name__, exc)
    else:
        raise AssertionError("a failed CUDA plugin registration was reported as loaded")
    try:
        module.open_asr_sessions(
            ort, str(make_model_dir(temp / "model")), ["CUDAExecutionProvider"],
            share=dict(SHARE), log=lambda _line: None,
            cuda_preload_error=preload_error)
    except RuntimeError as exc:
        detail = str(exc)
        assert "census=cuda-missing" in detail, detail
        assert "injected CUDA plugin registration failure" in detail, detail
        assert ort.calls == [], ort.calls
    else:
        raise AssertionError("session creation proceeded after plugin registration failure")


def arm_registration_silent_no_device(temp: Path, emulated=None) -> None:
    """A successful registration call must still prove a CUDA device appeared."""
    module = emulated or __import__("sotto_worker")
    ort = _fake_plugin_ort(temp, "registration-no-device")
    try:
        module._preload_cuda_runtime(ort)
    except RuntimeError as exc:
        preload_error = "%s: %s" % (type(exc).__name__, exc)
    else:
        raise AssertionError(
            "plugin registration returned normally without exposing CUDA")
    assert "explicit CUDA plugin registration did not expose" in preload_error, preload_error
    assert len(ort.register_calls) == 1, ort.register_calls
    assert ort.preload_calls == 1, ort.preload_calls
    assert ort.calls == [], ort.calls
    try:
        module.open_asr_sessions(
            ort, str(make_model_dir(temp / "model")), ["CUDAExecutionProvider"],
            share=dict(SHARE), log=lambda _line: None,
            cuda_preload_error=preload_error)
    except RuntimeError as exc:
        assert "Nemotron GPU-only policy refused" in str(exc), exc
        assert ort.census_calls == 3, ort.census_calls
        assert ort.calls == [], ort.calls
    else:
        raise AssertionError(
            "CPU-only post-registration census reached graph session creation")


def arm_control_nodes(temp: Path) -> None:
    out = run_arm("control-nodes", True, temp)
    assert out["raised"] is not None, "unsupported CPU control nodes were relaxed"
    assert ORT_FAILURE_TEXT in str(out["raised"]), out["raised"]
    assert out["ort"].calls == [("encoder.onnx", ["CUDAExecutionProvider"], "1")], out["ort"].calls


def arm_lying_readback(temp: Path, emulated=None) -> None:
    """A CUDA provider list cannot override a negative device census."""
    out = run_arm("lying-readback", False, temp, emulated=emulated)
    assert out["raised"] is not None, "lying CUDA readback was accepted"
    assert "census=cuda-missing" in str(out["raised"]), out["raised"]
    assert "ep_devices=CPUExecutionProvider" in str(out["raised"]), out["raised"]
    assert out["ort"].calls == [], out["ort"].calls


def arm_explicit_cpu(temp: Path) -> None:
    out = run_arm("cuda-absent", False, temp, providers=["CPUExecutionProvider"])
    assert out["raised"] is not None, "explicit CPU request was accepted"
    assert "requires CUDAExecutionProvider exclusively" in str(out["raised"]), out["raised"]
    assert out["ort"].calls == [], out["ort"].calls


def arm_missing_graph(temp: Path) -> None:
    make_model_dir(temp)
    (temp / "decoder.onnx").unlink()
    try:
        module = __import__("sotto_worker")
        module.open_asr_sessions(FakeOrt("cuda-absent", False), str(temp),
                                 ["CUDAExecutionProvider"], ab="",
                                 share=dict(SHARE), log=lambda _l: None)
    except RuntimeError as exc:
        assert "missing graph(s)" in str(exc), exc
        assert "decoder.onnx" in str(exc), exc
        return
    raise AssertionError("a model with no decoder.onnx did not raise")


def arm_cuda_unknown_fails_closed(temp: Path) -> None:
    out = run_arm("census-unknown", False, temp)
    assert out["raised"] is not None, "an unavailable CUDA device census was accepted"
    assert "census=unknown" in str(out["raised"]), out["raised"]
    assert "ep_devices=none" in str(out["raised"]), out["raised"]
    assert out["ort"].calls == [], out["ort"].calls


def arm_preload_failure_reported(temp: Path, emulated=None) -> None:
    out = run_arm("cuda-absent", False, temp, emulated=emulated,
                  cuda_preload_error=PRELOAD_FAILURE_TEXT)
    assert out["raised"] is not None, "preload failure bypassed the CUDA census guard"
    detail = str(out["raised"])
    for expected in (
            "ort_file=H:\\fake\\onnxruntime\\__init__.py",
            "plugin_ep=1",
            "providers=CUDAExecutionProvider,CPUExecutionProvider",
            "census=cuda-missing",
            "ep_devices=CPUExecutionProvider",
            "cuda_preload_error=OSError: injected preload banner continued"):
        assert expected in detail, "GPU refusal diagnostic missing %r: %s" % (
            expected, detail)
    assert len("RuntimeError: " + detail) <= 350, detail
    assert "private-build-marker" not in detail, detail
    assert "\n" not in detail, "preload failure escaped the one-line sanitizer"
    assert out["ort"].calls == [], out["ort"].calls
    assert out["ort"].census_calls == 1, out["ort"].census_calls
    assert out["logs"] == [], out["logs"]


def arm_long_preload_diagnostic(_temp: Path, emulated=None) -> None:
    """Keep census and device facts visible with the full preload-error budget."""
    module = emulated or __import__("sotto_worker")
    ort = FakeOrt("legacy-no-plugin-flag", False)
    preload_error = "P" * 80
    detail = module._asr_cuda_refusal_diagnostics(
        ort, False, ("CPUExecutionProvider",), preload_error)
    assert len(preload_error) == 80, len(preload_error)
    assert len(detail) <= 280, len(detail)
    assert "census=cuda-missing" in detail, detail
    assert "ep_devices=CPUExecutionProvider" in detail, detail


def arm_plugin_flag_absent(temp: Path) -> None:
    out = run_arm("legacy-no-plugin-flag", False, temp)
    assert out["raised"] is not None, "an absent plugin build flag bypassed the census guard"
    detail = str(out["raised"])
    assert "plugin_ep=absent" in detail, detail
    assert "census=cuda-missing" in detail, detail
    assert out["ort"].calls == [], out["ort"].calls


def positive() -> int:
    checks = 0
    with tempfile.TemporaryDirectory(prefix="sotto-stream-asr-gpu-") as temp:
        root = Path(temp)
        for index, arm in enumerate((
                arm_auto_cuda_only, arm_auto_cpu_only,
                arm_cuda_works, arm_cuda_absent, arm_lying_readback,
                arm_cuda_unknown_fails_closed, arm_control_nodes,
                arm_explicit_cpu, arm_missing_graph, arm_preload_failure_reported,
                arm_cuda_probe_fallback_disabled,
                arm_constructor_fallback_disabled,
                arm_long_preload_diagnostic,
                arm_legacy_plugin_registration, arm_plugin_registration_failure,
                arm_plugin_flag_absent, arm_registration_silent_no_device)):
            where = root / ("arm-%d" % index)
            where.mkdir()
            arm(where)
            checks += 1
    return checks


# ── the negative arm removes the required device census ─────────────────────
def mutant_module():
    source = WORKER_SOURCE.read_text(encoding="utf-8")
    if source.count(MUTANT_ANCHOR) != 1:
        raise AssertionError(
            "the mutant anchor is not unique in worker/sotto_worker.py (%d hits)"
            % source.count(MUTANT_ANCHOR))
    mutated = source.replace(MUTANT_ANCHOR, MUTANT_REPLACEMENT)
    module = types.ModuleType("sotto_worker_no_device_census")
    module.__file__ = str(WORKER_SOURCE)
    exec(compile(mutated, str(WORKER_SOURCE), "exec"), module.__dict__)  # noqa: S102
    return module


def preload_diagnostic_mutant_module():
    source = WORKER_SOURCE.read_text(encoding="utf-8")
    if source.count(MUTANT_PRELOAD_ANCHOR) != 1:
        raise AssertionError(
            "the preload diagnostic mutant anchor is not unique (%d hits)"
            % source.count(MUTANT_PRELOAD_ANCHOR))
    mutated = source.replace(MUTANT_PRELOAD_ANCHOR, MUTANT_PRELOAD_REPLACEMENT)
    module = types.ModuleType("sotto_worker_no_preload_diagnostic")
    module.__file__ = str(WORKER_SOURCE)
    exec(compile(mutated, str(WORKER_SOURCE), "exec"), module.__dict__)  # noqa: S102
    return module


def auto_cpu_mutant_module():
    source = WORKER_SOURCE.read_text(encoding="utf-8")
    if source.count(MUTANT_AUTO_CPU_ANCHOR) != 1:
        raise AssertionError(
            "the auto CPU-route mutant anchor is not unique (%d hits)"
            % source.count(MUTANT_AUTO_CPU_ANCHOR))
    mutated = source.replace(MUTANT_AUTO_CPU_ANCHOR, MUTANT_AUTO_CPU_REPLACEMENT)
    module = types.ModuleType("sotto_worker_auto_cpu_route")
    module.__file__ = str(WORKER_SOURCE)
    exec(compile(mutated, str(WORKER_SOURCE), "exec"), module.__dict__)  # noqa: S102
    return module


def plugin_registration_mutant_module():
    source = WORKER_SOURCE.read_text(encoding="utf-8")
    if source.count(MUTANT_PLUGIN_REGISTER_ANCHOR) != 1:
        raise AssertionError(
            "the CUDA plugin registration anchor is not unique (%d hits)"
            % source.count(MUTANT_PLUGIN_REGISTER_ANCHOR))
    mutated = source.replace(MUTANT_PLUGIN_REGISTER_ANCHOR,
                             MUTANT_PLUGIN_REGISTER_REPLACEMENT)
    module = types.ModuleType("sotto_worker_without_cuda_plugin_registration")
    module.__file__ = str(WORKER_SOURCE)
    exec(compile(mutated, str(WORKER_SOURCE), "exec"), module.__dict__)  # noqa: S102
    return module


def plugin_recheck_mutant_module():
    source = CUDA_RUNTIME_SOURCE.read_text(encoding="utf-8")
    if source.count(MUTANT_PLUGIN_RECHECK_ANCHOR) != 1:
        raise AssertionError(
            "the shared helper post-registration census anchor is not unique (%d hits)"
            % source.count(MUTANT_PLUGIN_RECHECK_ANCHOR))
    mutated = source.replace(MUTANT_PLUGIN_RECHECK_ANCHOR,
                             MUTANT_PLUGIN_RECHECK_REPLACEMENT)
    module = types.ModuleType("ort_cuda_runtime")
    module.__file__ = str(CUDA_RUNTIME_SOURCE)
    exec(compile(mutated, str(CUDA_RUNTIME_SOURCE), "exec"), module.__dict__)  # noqa: S102
    return module


def runtime_fallback_mutant_module():
    source = WORKER_SOURCE.read_text(encoding="utf-8")
    if source.count(MUTANT_RUNTIME_FALLBACK_ANCHOR) != 1:
        raise AssertionError(
            "the runtime-fallback mutation anchor is not unique (%d hits)"
            % source.count(MUTANT_RUNTIME_FALLBACK_ANCHOR))
    mutated = source.replace(MUTANT_RUNTIME_FALLBACK_ANCHOR,
                             MUTANT_RUNTIME_FALLBACK_REPLACEMENT)
    module = types.ModuleType("sotto_worker_runtime_fallback_enabled")
    module.__file__ = str(WORKER_SOURCE)
    exec(compile(mutated, str(WORKER_SOURCE), "exec"), module.__dict__)  # noqa: S102
    return module


def constructor_fallback_mutant_module():
    source = WORKER_SOURCE.read_text(encoding="utf-8")
    if source.count(MUTANT_CONSTRUCTOR_FALLBACK_ANCHOR) != 2:
        raise AssertionError(
            "expected both production constructor fallback guards, found %d"
            % source.count(MUTANT_CONSTRUCTOR_FALLBACK_ANCHOR))
    mutated = source.replace(MUTANT_CONSTRUCTOR_FALLBACK_ANCHOR,
                             MUTANT_CONSTRUCTOR_FALLBACK_REPLACEMENT)
    module = types.ModuleType("sotto_worker_constructor_fallback_enabled")
    module.__file__ = str(WORKER_SOURCE)
    exec(compile(mutated, str(WORKER_SOURCE), "exec"), module.__dict__)  # noqa: S102
    return module


def negative_control() -> int:
    caught = 0
    mutant = mutant_module()
    with tempfile.TemporaryDirectory(prefix="sotto-stream-asr-neg-") as temp:
        try:
            arm_lying_readback(Path(temp), emulated=mutant)
        except AssertionError as exc:
            if "lying CUDA readback was accepted" not in str(exc):
                print("NEG-ARM FAIL -- wrong mutation detector: %s" % exc)
                return 0
            caught += 1
        else:
            print("NEG-ARM FAIL -- removing the census guard stayed green")
            return 0
    mutant = preload_diagnostic_mutant_module()
    with tempfile.TemporaryDirectory(prefix="sotto-preload-diagnostic-neg-") as temp:
        try:
            arm_preload_failure_reported(Path(temp), emulated=mutant)
        except AssertionError as exc:
            if "GPU refusal diagnostic missing" not in str(exc):
                print("NEG-ARM FAIL -- wrong preload diagnostic detector: %s" % exc)
                return 0
            caught += 1
        else:
            print("NEG-ARM FAIL -- removing the preload diagnostic stayed green")
            return 0
    mutant = auto_cpu_mutant_module()
    try:
        arm_auto_cuda_only(Path(tempfile.gettempdir()), emulated=mutant)
    except AssertionError as exc:
        if "auto selected a non-CUDA provider" not in str(exc):
            print("NEG-ARM FAIL -- wrong auto-route mutation detector: %s" % exc)
            return 0
        caught += 1
    else:
        print("NEG-ARM FAIL -- restoring the CPU auto-provider stayed green")
        return 0
    mutant = plugin_registration_mutant_module()
    with tempfile.TemporaryDirectory(prefix="sotto-cuda-registration-neg-") as temp:
        try:
            arm_legacy_plugin_registration(Path(temp), emulated=mutant)
        except Exception as exc:  # noqa: BLE001 -- expected missing-registration assertion
            if "unmarked ORT CUDA plugin" not in str(exc):
                print("NEG-ARM FAIL -- wrong plugin-registration mutation detector: %s" % exc)
                return 0
            caught += 1
        else:
            print("NEG-ARM FAIL -- removing CUDA plugin registration stayed green")
            return 0
    mutant = plugin_recheck_mutant_module()
    with tempfile.TemporaryDirectory(prefix="sotto-cuda-post-registration-neg-") as temp:
        prior_runtime = sys.modules.get("ort_cuda_runtime")
        sys.modules["ort_cuda_runtime"] = mutant
        try:
            arm_registration_silent_no_device(Path(temp))
        except AssertionError as exc:
            if "plugin registration returned normally without exposing CUDA" not in str(exc):
                print("NEG-ARM FAIL -- wrong post-registration census detector: %s" % exc)
                return 0
            caught += 1
        else:
            print("NEG-ARM FAIL -- removing the post-registration census stayed green")
            return 0
        finally:
            if prior_runtime is None:
                sys.modules.pop("ort_cuda_runtime", None)
            else:
                sys.modules["ort_cuda_runtime"] = prior_runtime
    mutant = runtime_fallback_mutant_module()
    with tempfile.TemporaryDirectory(prefix="sotto-runtime-fallback-neg-") as temp:
        try:
            arm_cuda_works(Path(temp), emulated=mutant)
        except AssertionError as exc:
            if "runtime fallback remained enabled after run error" not in str(exc):
                print("NEG-ARM FAIL -- wrong runtime-fallback mutation detector: %s" % exc)
                return 0
            caught += 1
        else:
            print("NEG-ARM FAIL -- restoring runtime fallback stayed green")
            return 0
    mutant = constructor_fallback_mutant_module()
    with tempfile.TemporaryDirectory(prefix="sotto-constructor-fallback-neg-") as temp:
        try:
            arm_constructor_fallback_disabled(Path(temp), emulated=mutant)
        except AssertionError as exc:
            if "CUDA constructor fallback was not disabled" not in str(exc):
                print("NEG-ARM FAIL -- wrong constructor-fallback mutation detector: %s" % exc)
                return 0
            caught += 1
        else:
            print("NEG-ARM FAIL -- restoring constructor fallback stayed green")
            return 0
    if caught == 7:
        print("NEG-ARM PASS -- census, diagnostic, auto-route, registration, post-registration census, runtime-fallback, and constructor-fallback mutations caught (7/7)")
        return 1
    print("NEG-ARM FAIL -- only %d/7 regressions caught" % caught)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neg-arm", action="store_true")
    parser.add_argument("--census-lie-only", action="store_true")
    parser.add_argument("--legacy-registration-only", action="store_true")
    parser.add_argument("--selftest", action="store_true",
                        help="run the positive arms and the negative control in-process")
    args = parser.parse_args()
    try:
        if args.neg_arm:
            return negative_control()
        if args.census_lie_only:
            with tempfile.TemporaryDirectory(prefix="sotto-cuda-census-lie-") as temp:
                arm_lying_readback(Path(temp))
            print("CENSUS-LIE: PASS (false device census rejected before session)")
            return 0
        if args.legacy_registration_only:
            with tempfile.TemporaryDirectory(prefix="sotto-cuda-registration-red-") as temp:
                arm_legacy_plugin_registration(Path(temp))
            print("LEGACY CUDA REGISTRATION: PASS")
            return 0
        checks = positive()
        if checks != 17:
            raise AssertionError("positive coverage changed: %d" % checks)
        if args.selftest:
            neg_rc = negative_control()
            if neg_rc == 1:
                if "onnxruntime" in sys.modules:
                    raise AssertionError("fake selftest imported ONNX Runtime")
                print("SELFTEST: PASS (positive 17/17; all seven adverse mutations caught)")
                return 0
            print("SELFTEST: FAIL (negative_rc=%d)" % neg_rc)
            return 1
    except Exception as exc:  # noqa: BLE001
        print("VERDICT: FAIL (%s: %s)" % (type(exc).__name__, exc))
        return 1
    print("VERDICT: PASS (17/17 fake ORT; no ORT runtime, model, audio, or GPU)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
