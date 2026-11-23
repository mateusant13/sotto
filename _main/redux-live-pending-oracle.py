#!/usr/bin/env python3
# NO-BUG: o tecto de duracao e a contabilidade de descarte da fila ao vivo do Redux -- trabalho de CAPACIDADE/observabilidade, sem id no `_main/bug-ledger.json`
"""Model-free gate for the Redux live queue duration cap and drop accounting."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))

import numpy as np
from types import SimpleNamespace
import redux_live


class FakeWorker:
    TARGET_SR = 16000

    @staticmethod
    def resample_to_16k(pcm, rate):
        rate = int(rate)
        if rate == FakeWorker.TARGET_SR:
            return pcm
        size = int(pcm.size * FakeWorker.TARGET_SR / rate)
        return np.zeros(size, dtype=np.float32)


class FakeBackend:
    name = "fake-no-inference"

    def transcribe(self, _pcm):
        raise AssertionError("the queue gate must never invoke inference")


def make_run(cap_s=2.0):
    args = SimpleNamespace(
        pending_audio_s=cap_s,
        window_s=2.0,
        gap_s=0.7,
        min_window_s=0.5,
        max_line_chars=88,
        no_vad=True,
        no_agc=True,
        step_s=0.5,
    )
    run = redux_live.LiveRun(FakeBackend(), args, FakeWorker(), {})
    run.set_source_rate(FakeWorker.TARGET_SR)
    return run


def require_cap(run):
    if run.pending_samples > run.pending_cap_samples:
        raise AssertionError("pending samples exceed configured duration cap")


def positive():
    checks = 0

    run = make_run(2.0)
    run.on_block(np.full(16000, 1.0, dtype=np.float32))
    require_cap(run)
    assert run.backlog_s() == 1.0 and run.pending_drop_events == 0
    assert run.pending_peak_s == 1.0
    checks += 1

    run = make_run(2.0)
    run.on_block(np.full(20000, 1.0, dtype=np.float32))
    run.on_block(np.full(20000, 2.0, dtype=np.float32))
    require_cap(run)
    pending = np.concatenate(tuple(run.pending))
    assert pending.size == 32000
    assert np.all(pending[:12000] == 1.0) and np.all(pending[12000:] == 2.0)
    assert run.pending_dropped_samples == 8000 and run.pending_drop_events == 1
    assert run.backlog_s() == 2.0
    checks += 1

    run = make_run(2.0)
    oversized = np.arange(48000, dtype=np.float32)
    run.on_block(oversized)
    require_cap(run)
    pending = np.concatenate(tuple(run.pending))
    assert pending.size == 32000 and np.array_equal(pending, oversized[-32000:])
    assert run.pending_dropped_samples == 16000 and run.pending_drop_events == 1
    checks += 1

    run = make_run(2.0)
    source = np.arange(16000, dtype=np.float32)
    run.on_block(source)
    consumed = run._drain_pending(limit=0.5)
    require_cap(run)
    assert consumed == 8000 and run.seg.seg_samples == 8000
    assert run.pending_samples == 8000 and run.backlog_s() == 0.5
    assert np.array_equal(np.concatenate(tuple(run.pending)), source[8000:])
    checks += 1

    run = make_run(2.0)
    run.set_source_rate(48000)
    source = np.arange(144000, dtype=np.float32)
    run.on_block(source)
    require_cap(run)
    pending = np.concatenate(tuple(run.pending))
    assert run.pending_cap_samples == 96000 and run.backlog_s() == 2.0
    assert pending.size == 96000 and np.array_equal(pending, source[-96000:])
    assert run.pending_dropped_samples == 48000 and run.pending_drop_events == 1
    checks += 1

    run = make_run(2.0)
    run.set_source_rate(48000)
    source = np.arange(96000, dtype=np.float32)
    run.on_block(source)
    consumed = run._drain_pending(limit=1.0)
    require_cap(run)
    assert consumed == 16000 and run.seg.seg_samples == 16000
    assert run.pending_samples == 48000 and run.backlog_s() == 1.0
    assert np.array_equal(np.concatenate(tuple(run.pending)), source[48000:])
    checks += 1

    stats = run.stats_line()
    assert "pending_cap_s=2.0" in stats
    assert "pending_drop_events=0" in stats
    checks += 1

    return checks


def negative_control():
    run = make_run(1.0)
    run._trim_pending_locked = lambda: 0
    run.on_block(np.ones(32000, dtype=np.float32))
    try:
        require_cap(run)
    except AssertionError as exc:
        print("NEG-ARM PASS -- disabled cap detected: %s" % exc)
        return 1
    print("NEG-ARM FAIL -- disabled cap escaped the bound check")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--neg-arm", action="store_true")
    parser.add_argument("--selftest", action="store_true",
                        help="run positive and negative controls in this process")
    args = parser.parse_args()
    try:
        if args.neg_arm:
            return negative_control()
        checks = positive()
        if args.selftest:
            neg_rc = negative_control()
            if checks == 7 and neg_rc == 1:
                print("SELFTEST: PASS (positive 7/7; negative control caught cap removal)")
                return 0
            print("SELFTEST: FAIL (positive=%d; negative_rc=%d)" % (checks, neg_rc))
            return 1
    except Exception as exc:
        print("VERDICT: FAIL (%s: %s)" % (type(exc).__name__, exc))
        return 1
    print("VERDICT: PASS (%d/7) no model load, no inference" % checks)
    return 0 if checks == 7 else 1


if __name__ == "__main__":
    raise SystemExit(main())
