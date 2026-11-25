#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# NO-BUG: instrumento (2026-11-25) que compara o config efetivo com o que o repo declara -- le ficheiros e funcoes puras, nao corrige o produto nem abre dispositivo
"""ORACLE for the three slice-3 config-truth defects (2026-11-25).

THE THREE CLAIMS UNDER JUDGEMENT
  A  `worker/config.json:audio.device` is EMPTY; the device is chosen by the
     universal ladder (WASAPI loopback -> name heuristic -> explicit override),
     not by a virtual-cable name pinned in a file that ships to ordinary PCs.
  B  `use_denoise` is a LIVE switch: ONE call site in StreamAsr.run_chunk, after
     the speech/music gate and before the mel window/Silero VAD. With the key
     false the PCM reaching `self.sp.process` is BYTE-IDENTICAL to a worker
     with the denoise module disabled; with the key true that PCM changes.
  C  `worker/qwen_summary.py` is an orphan: zero references under worker/ and
     app/ after its deletion (the only old hit was a hot_reload COMMENT).

ARMS (all over the real files, no re-implementation of the seam)
  A  the shipped JSON + the ladder markers in the real worker source.
  B  the REAL `StreamAsr.run_chunk`, driven with a fake `self` whose `sp.process`
     records the PCM at the boundary and raises a private sentinel: false vs
     module-disabled must be equal, true must differ. No model, no device.
     `--config` is set per arm so the helper reads the same config main() reads.
  C  a file census over the real worker/ and app/ trees.

`--neg-arm` plants three mutants (a pinned cable device, a run_chunk with the
denoise call removed, a temp tree with the qwen file and a hot_reload hit) and
requires EVERY arm to go RED. House convention: rc 1 is the expected result of
a red-as-expected negative arm. Exit codes: 0 PASS, 1 RED, 2 setup error.
No window, no audio endpoint, no model load: pure file reads and NumPy.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
WORKER = os.path.join(REPO, "worker")
CONFIG = os.path.join(WORKER, "config.json")
WORKER_PY = os.path.join(WORKER, "sotto_worker.py")

if WORKER not in sys.path:
    sys.path.insert(0, WORKER)

import numpy as np  # noqa: E402

_MISSING = object()


class _Stop(Exception):
    """Private boundary sentinel: `sp.process` is the first PCM consumer."""


class _Recorder:
    def __init__(self):
        self.pcm = None

    def process(self, pcm):
        self.pcm = np.asarray(pcm).tobytes()
        raise _Stop()


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def load_worker(source):
    """Execute the given worker source under a probe name, no __main__ block."""
    ns = {"__name__": "_config_truth_probe", "__file__": WORKER_PY}
    exec(compile(source, WORKER_PY, "exec"), ns)  # noqa: S102 - own source
    return ns["StreamAsr"]


def probe_pcm(worker_cls, cfg_path, disable_module=False):
    """Bytes the mel window receives for one chunk, with a given config arm."""
    fake = SimpleNamespace(np=np, gate=None, sp=_Recorder())
    rng = np.random.default_rng(20261125)
    tone = np.sin(np.arange(8960, dtype=np.float64) * 0.037) * 0.04
    pcm = (tone + rng.standard_normal(8960) * 0.01).astype(np.float32)
    saved_argv = list(sys.argv)
    saved_module = sys.modules.get("denoise", _MISSING)
    try:
        sys.argv = [WORKER_PY, "--config", cfg_path]
        if disable_module:
            sys.modules["denoise"] = None       # import in run_chunk must fail closed
        try:
            worker_cls.run_chunk(fake, pcm, speech=True, account=False)
        except _Stop:
            pass
        return fake.sp.pcm
    finally:
        sys.argv[:] = saved_argv
        if saved_module is _MISSING:
            sys.modules.pop("denoise", None)
        else:
            sys.modules["denoise"] = saved_module


def check_device(cfg, cfg_text, worker_src):
    findings = []
    audio = cfg.get("audio") or {}
    if audio.get("device") != "":
        findings.append("DEVICE PINNED: audio.device=%r, not empty" % (audio.get("device"),))
    if audio.get("preferred_devices") != []:
        findings.append("DEVICE PINNED: preferred_devices=%r" % (audio.get("preferred_devices"),))
    pinned = json.dumps(audio.get("device")) + json.dumps(audio.get("preferred_devices"))
    lowered = pinned.lower()
    for marker in ("cable input", "voicemeeter", "stereo mix"):
        if marker in lowered:
            findings.append("DEVICE NAME PINNED IN CONFIG VALUE: %r" % (marker,))
    if "DELIBERATELY EMPTY" not in cfg_text:
        findings.append("DEVICE COMMENT no longer says DELIBERATELY EMPTY")
    for marker in ("loopback_device_specs", "SOTTO_AUDIO_DEVICE"):
        if marker not in worker_src:
            findings.append("LADDER MISSING: %s not in worker source" % (marker,))
    return findings


def check_denoise(worker_src, cfg_false_path, cfg_true_path):
    findings = []
    i_gate = worker_src.find("if speech is None:")
    i_call = worker_src.find("if self.denoiser is not None:")
    i_mel = worker_src.find("feats = self.sp.process(pcm_chunk)")
    if not (0 <= i_gate < i_call < i_mel):
        findings.append("CALL SITE OUT OF ORDER: gate=%d denoise=%d mel=%d"
                        % (i_gate, i_call, i_mel))
    if "gate_for_worker_config(TARGET_SR)" not in worker_src:
        findings.append("CONFIG WIRING MISSING: no gate_for_worker_config() call site")
    cls = load_worker(worker_src)
    p_false = probe_pcm(cls, cfg_false_path)
    p_off = probe_pcm(cls, cfg_false_path, disable_module=True)
    p_true = probe_pcm(cls, cfg_true_path)
    if p_false is None or p_off is None or p_true is None:
        findings.append("BOUNDARY PROBE did not reach sp.process")
        return findings
    if p_false != p_off:
        findings.append("FALSE NOT BYTE-IDENTICAL: %d bytes differ from module-disabled"
                        % sum(a != b for a, b in zip(p_false, p_off)))
    else:
        print("  false arm == module-disabled arm: %d bytes, sha256-prefix equal" % len(p_false))
    if p_true == p_false:
        findings.append("TRUE DID NOT CHANGE PCM: true arm == false arm")
    else:
        a = np.frombuffer(p_false, np.float32)
        b = np.frombuffer(p_true, np.float32)
        print("  true arm changed PCM: max|delta|=%.6f over %d samples"
              % (float(np.max(np.abs(a - b))), a.size))
    return findings


def check_qwen(root):
    findings = []
    qpath = os.path.join(root, "worker", "qwen_summary.py")
    if os.path.isfile(qpath):
        findings.append("ORPHAN FILE PRESENT: worker/qwen_summary.py")
    refs = []
    for sub in ("worker", "app"):
        base = os.path.join(root, sub)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in ("__pycache__", ".git")]
            for fn in filenames:
                if not fn.endswith((".py", ".js", ".json", ".md", ".html", ".css")):
                    continue
                path = os.path.join(dirpath, fn)
                if os.path.abspath(path) == os.path.abspath(qpath):
                    continue
                for n, line in enumerate(_read(path).splitlines(), 1):
                    if "qwen_summary" in line:
                        refs.append("%s:%d" % (os.path.relpath(path, root), n))
    if refs:
        findings.append("ORPHAN REFERENCE(S): " + ", ".join(refs))
    else:
        print("  qwen census: zero references under worker/ and app/")
    return findings


def report(findings):
    for line in findings:
        print("  RED:", line)
    if not findings:
        print("  ok")
    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args()
    if not os.path.isfile(CONFIG) or not os.path.isfile(WORKER_PY):
        print("setup error: missing config or worker source")
        return 2

    cfg = json.loads(_read(CONFIG))
    cfg_text = _read(CONFIG)
    src = _read(WORKER_PY)

    with tempfile.TemporaryDirectory(prefix="config-truth-") as tmp:
        false_cfg = json.loads(json.dumps(cfg))
        false_cfg["use_denoise"] = False
        true_cfg = json.loads(json.dumps(cfg))
        true_cfg["use_denoise"] = True
        false_path = os.path.join(tmp, "config-false.json")
        true_path = os.path.join(tmp, "config-true.json")
        for path, obj in ((false_path, false_cfg), (true_path, true_cfg)):
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(obj, fh)

        if not args.neg_arm:
            print("== A device is empty; the ladder decides ==")
            findings_a = report(check_device(cfg, cfg_text, src))
            print("== B denoise wired, false == byte-identical, true changes PCM ==")
            findings_b = report(check_denoise(src, false_path, true_path))
            print("== C qwen orphan removed with no references ==")
            findings_c = report(check_qwen(REPO))
            findings = findings_a + findings_b + findings_c
            for line in findings:
                print("RED:", line)
            print("VERDICT:", "RED" if findings else "PASS")
            return 1 if findings else 0

        print("== NEG ARM: every planted mutant must go RED ==")
        bad_cfg = json.loads(json.dumps(cfg))
        bad_cfg["audio"]["device"] = "CABLE Input (VB-Audio Virtual Cable)"
        bad_text = cfg_text.replace('"device": ""',
                                    '"device": "CABLE Input (VB-Audio Virtual Cable)"')
        mutants = [
            ("A pinned device", check_device(bad_cfg, bad_text, src)),
            ("B denoise call removed", check_denoise(
                src.replace("pcm_chunk = self.denoiser.process(pcm_chunk)",
                            "_mutant_noop = None"),
                false_path, true_path)),
        ]
        mroot = os.path.join(tmp, "tree")
        os.makedirs(os.path.join(mroot, "worker"))
        os.makedirs(os.path.join(mroot, "app", "webview"))
        with open(os.path.join(mroot, "worker", "qwen_summary.py"), "w", encoding="utf-8") as fh:
            fh.write("qwen_summary\n")
        with open(os.path.join(mroot, "app", "webview", "hot_reload.py"), "w",
                  encoding="utf-8") as fh:
            fh.write("# qwen_summary\n")
        mutants.append(("C qwen restored", check_qwen(mroot)))
        red_count = 0
        for name, findings in mutants:
            print("  %-26s %s" % (name, "RED" if findings else "GREEN (WRONG)"))
            for line in findings:
                print("    RED:", line)
            red_count += bool(findings)
        all_red = red_count == len(mutants)
        print("VERDICT: %s (neg-arm: %d/%d arms RED)"
              % ("RED" if all_red else "PASS - NEG ARM FAILED TO REDDEN",
                 red_count, len(mutants)))
        return 1 if all_red else 0


if __name__ == "__main__":
    sys.exit(main())
