#!/usr/bin/env pythonw
"""asr02-selftest.py -- the model-free checks for src/asr (no inference, no audio device).

Proves, without loading the model:
  1. the package imports and every module compiles;
  2. the silence splitter reproduces the RECORDED segment boundaries of
     `_main/runs/threads11/silence-t4-p1.json` on the registered slice [900, 1020) -- the
     splitter is deterministic and model-free, so this is a byte-level regression target;
  3. the 10 Hz level emitter emits exactly 10 events per audio second, keeps its event under
     the byte budget, attacks instantly and releases exponentially, and holds 128 points;
  4. the constants carry provenance and the model dir holds the registered file sizes.

Run with pythonw.exe (no console, no window); it writes `_main/logs/asr02-selftest.json`.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

ROOT = Path(r"H:\aireplay")
sys.path.insert(0, str(ROOT / "src"))

OUT = ROOT / "_main" / "logs" / "asr02-selftest.json"
LOG = ROOT / "_main" / "logs" / "asr02-selftest.log"
LINES: list[str] = []


def say(msg: str) -> None:
    LINES.append(msg)


def main() -> int:
    results: dict = {"checks": [], "ok": True}

    def check(name: str, ok: bool, detail: str = "") -> None:
        results["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            results["ok"] = False
        say(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")

    from asr import constants as C

    # pin the budget BEFORE numpy loads its thread pool (the selftest is not exempt)
    from asr.engine import pin_thread_env

    pinned = pin_thread_env(C.INTRA_OP_NUM_THREADS)
    say(f"[info] pinned {pinned}")
    results["pinned_env"] = pinned

    # -- 4. constants + artefact -------------------------------------------------------
    missing = [k for k in C.PROVENANCE if not C.PROVENANCE[k]]
    check("provenance-present", not missing, f"{len(C.PROVENANCE)} entries, missing={missing}")
    check("thread-knee", C.INTRA_OP_NUM_THREADS == 4 and C.INTER_OP_NUM_THREADS == 1,
          f"intra={C.INTRA_OP_NUM_THREADS} inter={C.INTER_OP_NUM_THREADS}")
    check("default-mode-is-silence", C.DEFAULT_SEGMENT_MODE == "silence",
          f"default={C.DEFAULT_SEGMENT_MODE!r} control={C.CONTROL_SEGMENT_MODE!r}")
    check("level-hz", C.BLOCK_MS == 100 and C.LEVEL_HZ == 10, f"block_ms={C.BLOCK_MS} hz={C.LEVEL_HZ}")
    bad = []
    for name, size in C.MODEL_FILE_SIZES.items():
        p = C.MODEL_DIR / name
        got = p.stat().st_size if p.exists() else -1
        if got != size:
            bad.append(f"{name}: {got} != {size}")
    check("model-files-sizes", not bad, f"total={sum(C.MODEL_FILE_SIZES.values())} B; {bad}")
    results["model_dir"] = str(C.MODEL_DIR)

    # -- 2. the splitter against the recorded boundaries --------------------------------
    from asr.audio import read_slice, wav_info
    from asr.segment import segments_fixed, segments_for_mode, segments_silence

    wav = C.SOTTO_REDUX_LONG / "plain-3600s.wav"
    ref_json = C.REGISTERED_REFERENCE_DIR / "silence-t4-p1.json"
    ref = json.loads(ref_json.read_text(encoding="utf-8"))
    info = wav_info(wav)
    x = read_slice(wav, 900.0, 120.0)
    segs = segments_silence(x)
    rec = [(round(s["start"], 3), round(s["end"], 3)) for s in ref["segments"]]
    mine = [(round(900.0 + a, 3), round(900.0 + b, 3)) for a, b in segs]
    check("splitter-count", len(mine) == len(rec) == C.PARITY_LONG_SEGMENTS,
          f"mine={len(mine)} recorded={len(rec)} registered={C.PARITY_LONG_SEGMENTS}")
    worst = 0.0
    if len(mine) == len(rec):
        for (a1, b1), (a2, b2) in zip(mine, rec):
            worst = max(worst, abs(a1 - a2), abs(b1 - b2))
    check("splitter-boundaries", worst <= 0.0015, f"max |delta| = {worst:.6f} s")
    results["segments_mine"] = mine
    results["segments_recorded"] = rec
    results["wav_format"] = info.as_dict()

    fx = segments_fixed(len(x) / 16000.0, 10.0)
    check("fixed-grid-control", len(fx) == 12 and all(round(b - a, 3) == 10.0 for a, b in fx),
          f"{len(fx)} x 10.0 s (CONTROL only; ratio 0.229 measured)")
    # the dispatch must key on the LITERAL mode names: a copy whose DEFAULT was flipped to
    # "fixed" once ran the SILENCE splitter while reporting mode="fixed" (caught by the oracle)
    check("mode-dispatch-is-literal",
          len(segments_for_mode(x, "fixed")) == 12 and len(segments_for_mode(x, "silence")) == 11,
          f"fixed={len(segments_for_mode(x, 'fixed'))} silence={len(segments_for_mode(x, 'silence'))}")

    # -- 3. the level emitter ----------------------------------------------------------
    from asr.level import LevelEmitter, compact_json

    import numpy as np

    sr = 16000
    tone = 0.8 * np.sin(2 * np.pi * 1000.0 * np.arange(sr * 3) / sr).astype(np.float32)
    quiet = (0.0005 * np.sin(2 * np.pi * 200.0 * np.arange(sr * 2) / sr)).astype(np.float32)
    sig = np.concatenate([tone, quiet])
    events: list[dict] = []
    em = LevelEmitter(sink=events.append, sample_rate=sr)
    for i in range(0, len(sig), 1600):
        em.feed(sig[i : i + 1600])
    em.close()
    n_expect = int(round(len(sig) / sr * C.LEVEL_HZ))
    check("level-cadence", em.n_events == n_expect == len(events),
          f"events={em.n_events} expected={n_expect} (audio {len(sig) / sr:.1f}s at {C.LEVEL_HZ} Hz)")
    sizes = [len(compact_json(e).encode("utf-8")) for e in events]
    check("level-event-budget", max(sizes) <= C.LEVEL_MAX_EVENT_BYTES,
          f"max={max(sizes)} B budget={C.LEVEL_MAX_EVENT_BYTES} B (mean {sum(sizes) / len(sizes):.1f} B)")
    check("level-keys", tuple(events[0].keys()) == ("type", *C.LEVEL_KEYS),
          f"keys={tuple(events[0].keys())}")
    peak_tone = max(e["p"] for e in events[:30])
    peak_quiet = max(e["p"] for e in events[30:])
    check("level-windowed-not-runmax", peak_quiet < 0.01 < peak_tone,
          f"peak during tone={peak_tone} during quiet={peak_quiet} (a run max could only rise)")
    tail = [e["e"] for e in events[31:]]
    check("level-release", tail and tail[-1] < tail[0] * 0.05 and all(b <= a for a, b in zip(tail, tail[1:])),
          f"envelope {tail[0]} -> {tail[-1]} (instant attack, exponential release)")
    check("level-history", em.history.maxlen == C.LEVEL_HISTORY
          and len(em.history) == min(em.n_events, C.LEVEL_HISTORY),
          f"maxlen={em.history.maxlen} points={len(em.history)} = {C.LEVEL_HISTORY / C.LEVEL_HZ:.1f} s ring")
    results["level"] = em.summary()
    results["level_examples"] = events[:3] + events[30:33]

    # -- 1. import surface -------------------------------------------------------------
    import asr  # noqa: F401
    from asr import parity, runner  # noqa: F401
    from asr.transcribe import build_parser  # noqa: F401

    parser = build_parser()
    ns = parser.parse_args(["--wav", "x.wav"])
    check("cli-defaults", ns.segment_mode == "silence" and ns.threads == 4 and ns.level == "on"
          and ns.json is False, f"mode={ns.segment_mode} threads={ns.threads} level={ns.level} json={ns.json}")
    check("parity-arms", sorted(parity.ARMS) == ["en-8s", "long", "long-fixed", "pt-15s"],
          f"arms={sorted(parity.ARMS)}")
    check("parity-control-expects-red", parity.ARMS["long-fixed"]["expect"] == "red",
          f"expect={parity.ARMS['long-fixed']['expect']}")
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        rc = main()
    except Exception:  # noqa: BLE001
        rc = 3
        LINES.append("EXCEPTION\n" + traceback.format_exc())
    LOG.write_text("\n".join(LINES) + f"\nSELFTEST-RC {rc}\n", encoding="utf-8")
    try:
        data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    except Exception:  # noqa: BLE001
        data = {}
    data["rc"] = rc
    data["log"] = LINES
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    raise SystemExit(rc)
