"""Model-free positive and negative controls for Parakeet Ultra GPU-only policy."""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))

import parakeet_ultra


def _caught(label, call):
    try:
        call()
    except RuntimeError as exc:
        print("PASS %s (%s)" % (label, str(exc)))
        return True
    print("FAIL %s (invalid GPU policy accepted)" % label)
    return False


class _FakeOptions:
    def __init__(self, cpu_ep="1", threads=1):
        self.entries = {"session.disable_cpu_ep_fallback": cpu_ep}
        self.intra_op_num_threads = threads
        self.inter_op_num_threads = 0
        self.execution_mode = None
        self.use_per_session_threads = True

    def get_session_config_entry(self, name):
        return self.entries.get(name)

    def add_session_config_entry(self, name, value):
        self.entries[name] = value


class _FakeSession:
    def __init__(self, providers, *, disable_noop=False):
        self._providers = list(providers)
        self._enable_fallback = True
        self.disable_noop = disable_noop
        self.cpu_retry = False

    def disable_fallback(self):
        if not self.disable_noop:
            self._enable_fallback = False

    def get_providers(self):
        return list(self._providers)

    def run(self, *_args, **_kwargs):
        if self._enable_fallback:
            self.cpu_retry = True
            return "cpu-retried"
        raise RuntimeError("fake CUDA run failure")


class _FakeOrt:
    def __init__(self, *, constructor_fails=False, disable_noop=False):
        self.constructor_fails = constructor_fails
        self.disable_noop = disable_noop
        self.calls = []
        self.cpu_retries = 0
        self.pool_sizes = []
        self.force_cpu_vad = False
        self.SessionOptions = lambda: _FakeOptions()
        self.ExecutionMode = type("ExecutionMode", (), {"ORT_SEQUENTIAL": "sequential"})

    def get_device(self):
        return "GPU"

    def set_global_thread_pool_sizes(self, **kwargs):
        self.pool_sizes.append(kwargs)

    def InferenceSession(self, path, options=None, *args, **kwargs):
        enable_fallback = kwargs.get("enable_fallback", 1)
        providers = kwargs.get("providers", ())
        self.calls.append({"path": str(path), "enable_fallback": enable_fallback,
                           "providers": providers})
        if self.constructor_fails:
            if enable_fallback:
                self.cpu_retries += 1
                return _FakeSession(["CPUExecutionProvider"])
            raise RuntimeError("fake CUDA constructor failure")
        actual = (["CPUExecutionProvider"] if self.force_cpu_vad
                  and str(path).endswith("vad-model.onnx")
                  else ["CUDAExecutionProvider", "CPUExecutionProvider"])
        return _FakeSession(actual, disable_noop=self.disable_noop)


def _fake_engine_factory(ort, *, disable_cpu_ep_fallback="1", threads=1):
    names = ("preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx")
    sessions = {}
    for name in names:
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.add_session_config_entry("session.disable_cpu_ep_fallback", disable_cpu_ep_fallback)
        sessions[name] = ort.InferenceSession(
            name, options, providers=["CUDAExecutionProvider"])
    return type("FakeAdapter", (), {
        "provider_readback": {name: session.get_providers()
                              for name, session in sessions.items()},
        "cpu_ep_fallback_disabled": disable_cpu_ep_fallback == "1",
        "sessions": sessions,
    })()


def _fake_graph_session(ort, name, *, cpu_ep="1", threads=1, providers=None):
    options = ort.SessionOptions()
    options.intra_op_num_threads = threads
    options.add_session_config_entry("session.disable_cpu_ep_fallback", cpu_ep)
    return ort.InferenceSession(name, options,
                                providers=providers or ["CUDAExecutionProvider"])


def _policy_row(providers, *, cpu_ep="1", runtime_disabled=True, device="GPU"):
    return {
        "provider_readback": list(providers),
        "requested_providers": ["CUDAExecutionProvider"],
        "disable_cpu_ep_fallback": cpu_ep,
        "constructor_fallback_disabled": True,
        "runtime_disable_invoked": True,
        "runtime_fallback_disabled": runtime_disabled,
        "runtime_fallback_readback": not runtime_disabled,
        "ort_device_readback": device,
        "intra_op_threads": 1,
        "inter_op_threads": 1,
        "use_per_session_threads": False,
    }


def positive() -> int:
    checks = 0
    assert parakeet_ultra.require_cuda_device("cuda", True) == "cuda"
    checks += 1
    ort = _FakeOrt()
    adapter, session_policy, device, thread_policy = parakeet_ultra.construct_onnx_with_gpu_guard(
        ort, lambda guarded_ort: _fake_engine_factory(guarded_ort),
        expected_ort_intra_op_threads=1)
    late_vad = _fake_graph_session(adapter._sotto_ort_proxy, "vad-model.onnx")
    adapter.sessions["vad-model.onnx"] = late_vad
    if ("vad-model.onnx" not in adapter.provider_readback
            or "vad-model.onnx" not in adapter.session_policy_readback):
        raise AssertionError("late VAD session was not included in live readback mappings")
    if device != "GPU":
        raise AssertionError("ORT device readback was not preserved")
    parakeet_ultra.require_cuda_onnx_policy(
        adapter.provider_readback, adapter.cpu_ep_fallback_disabled,
        session_policy, thread_policy, {
            "preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx", "vad-model.onnx"})
    checks += 1
    if (len(ort.calls) != 4 or ort.pool_sizes != [{"intra_op_num_threads": 1,
                                                   "inter_op_num_threads": 1}]
            or any(call["enable_fallback"] != 0 for call in ort.calls)
            or set(session_policy) != set(adapter.provider_readback)
            or any(row.get("runtime_fallback_disabled") is not True
                   or row.get("disable_cpu_ep_fallback") != "1"
                   or row.get("provider_readback", [None])[0] != "CUDAExecutionProvider"
                   for row in session_policy.values())):
        raise AssertionError("GPU session construction/readback guard did not close all graphs")
    for session in adapter.sessions.values():
        try:
            session.run()
        except RuntimeError:
            pass
        else:
            raise AssertionError("disabled runtime fallback swallowed a fake run failure")
        if session.cpu_retry:
            raise AssertionError("disabled runtime fallback retried on CPU")
    checks += 1
    try:
        parakeet_ultra.require_cuda_onnx_policy(
            {name: adapter.provider_readback[name] for name in (
                "preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx")},
            adapter.cpu_ep_fallback_disabled,
            {name: session_policy[name] for name in (
                "preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx")},
            thread_policy,
            {"preprocessor.onnx", "encoder-model.onnx", "decoder_joint-model.onnx", "vad-model.onnx"})
    except RuntimeError:
        pass
    else:
        raise AssertionError("core-only readback concealed a missing VAD graph")
    checks += 1
    failing_ort = _FakeOrt(constructor_fails=True)
    try:
        parakeet_ultra.construct_onnx_with_gpu_guard(
            failing_ort, lambda guarded_ort: _fake_engine_factory(guarded_ort),
            expected_ort_intra_op_threads=1)
    except RuntimeError:
        if failing_ort.cpu_retries != 0 or not failing_ort.calls or failing_ort.calls[0]["enable_fallback"] != 0:
            raise AssertionError("failed CUDA constructor retried on CPU")
    else:
        raise AssertionError("fake CUDA constructor failure was accepted")
    checks += 1
    return checks


def negative() -> int:
    cases = [
        ("cpu-device-refused", lambda: parakeet_ultra.require_cuda_device("cpu", True)),
        ("auto-fallback-refused", lambda: parakeet_ultra.require_cuda_device("auto", False)),
        ("cuda-unavailable-refused", lambda: parakeet_ultra.require_cuda_device("cuda", False)),
        ("missing-readback-refused", lambda: parakeet_ultra.require_cuda_onnx_policy({}, True)),
        ("cpu-graph-refused", lambda: parakeet_ultra.require_cuda_onnx_policy(
            {"encoder.onnx": ["CPUExecutionProvider"]}, True,
            {"encoder.onnx": _policy_row(["CPUExecutionProvider"])})),
        ("fallback-enabled-refused", lambda: parakeet_ultra.require_cuda_onnx_policy(
            {"encoder.onnx": ["CUDAExecutionProvider"]}, False)),
        ("ort-cpu-device-refused", lambda: _cpu_ort_refusal()),
        ("constructor-cpu-retry-refused", lambda: _constructor_fallback_mutant()),
        ("runtime-fallback-readback-refused", lambda: _runtime_fallback_noop()),
        ("late-vad-cpu-refused", lambda: _late_vad_cpu_refusal()),
        ("missing-session-policy-refused", lambda: parakeet_ultra.require_cuda_onnx_policy(
            {"encoder.onnx": ["CUDAExecutionProvider"]}, True,
            session_policy_readback=None)),
    ]
    caught = sum(1 for label, call in cases if _caught(label, call))
    photon_script = str(ROOT / "_main" / "_cache" / "ultra-photon-measure.py")
    original_argv = sys.argv[:]
    for label, argv in (
        ("photon-cpu-cli-refused-before-model", [photon_script, "--device", "cpu", "--allow-heavy"]),
        ("photon-heavy-cli-refused-without-optin", [photon_script, "--device", "cuda"]),
    ):
        sys.argv = argv
        try:
            runpy.run_path(photon_script, run_name="__main__")
            print("FAIL %s (unsafe invocation accepted)" % label)
        except SystemExit as exc:
            ok = int(exc.code or 0) == 2
            print(("PASS " if ok else "FAIL ") + label + " (exit=%s)" % exc.code)
            caught += int(ok)
    sys.argv = original_argv
    total = len(cases) + 2
    print("NEG-ARM PASS" if caught == total else "NEG-ARM FAIL")
    return 1 if caught == total else 0


def _constructor_fallback_mutant():
    """Model the old constructor path: omitted enable_fallback silently retries CPU."""
    ort = _FakeOrt(constructor_fails=True)
    session = ort.InferenceSession(
        "encoder-model.onnx", _FakeOptions(), providers=["CUDAExecutionProvider"])
    if ort.cpu_retries != 1 or session.get_providers()[0] != "CPUExecutionProvider":
        raise AssertionError("fake did not reproduce constructor CPU retry")
    parakeet_ultra.require_cuda_onnx_policy(
        {"encoder-model.onnx": session.get_providers()}, True,
        session_policy_readback={"encoder-model.onnx": _policy_row(
            session.get_providers(), cpu_ep="1")},
        thread_policy={"ort_shared_pool_intra_op_threads": 1,
                       "ort_shared_pool_inter_op_threads": 1,
                       "ort_shared_global_pool_configured": True})


def _cpu_ort_refusal():
    class CpuOrt(_FakeOrt):
        def get_device(self):
            return "CPU"
    ort = CpuOrt()
    parakeet_ultra.construct_onnx_with_gpu_guard(
        ort, lambda guarded_ort: _fake_engine_factory(guarded_ort))


def _runtime_fallback_noop():
    ort = _FakeOrt(disable_noop=True)
    parakeet_ultra.construct_onnx_with_gpu_guard(
        ort, lambda guarded_ort: _fake_engine_factory(guarded_ort))


def _late_vad_cpu_refusal():
    ort = _FakeOrt()
    adapter, _, _, _ = parakeet_ultra.construct_onnx_with_gpu_guard(
        ort, lambda guarded_ort: _fake_engine_factory(guarded_ort))
    ort.force_cpu_vad = True
    _fake_graph_session(adapter._sotto_ort_proxy, "vad-model.onnx")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neg-arm", action="store_true")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.neg_arm:
        return negative()
    try:
        checks = positive()
        if checks != 5:
            raise AssertionError("positive coverage changed: %d" % checks)
        if args.selftest:
            neg_rc = negative()
            if neg_rc == 1:
                print("SELFTEST: PASS (positive 5/5; late VAD readback and fallback mutants caught)")
                return 0
            return 1
    except Exception as exc:
        print("VERDICT: FAIL (%s: %s)" % (type(exc).__name__, exc))
        return 1
    print("VERDICT: PASS (5/5) fake sessions only; no model/audio/ORT/CUDA load")
    return 0


if __name__ == "__main__":
    sys.exit(main())
