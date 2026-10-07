#!/usr/bin/env pythonw
"""oracle-02-asr.py -- the gate for `specs/02-asr.md` / `src/asr/`. BOTH COLOURS, ONE COMMAND.

House rule: an instrument that cannot say NO is worthless. So this oracle runs the product AND
two deliberately-broken copies of it, and the final verdict requires the product arms to be
GREEN and the controls to be RED:

  ARM-0  STATIC      constants + provenance + the registered artefact sizes (no model)
  ARM-A  PRODUCT     `python -m asr.transcribe` on plain-3600s.wav [900,1020), defaults
                     (silence, intra_op=4/inter_op=1) -> gates:
                       * threads intra=4 inter=1            (the measured knee, spec section 2)
                       * segment_mode == "silence"          (spec section 3)
                       * text sha256 == the registered 814-char reference (byte-identical)
                       * level: n_events == 10 x audio_s    (the 10 Hz wave contract, section 7)
                       * rss_peak_wset in [700, 1200] MB    (the measured 920-929 MB band)
                       * rtfx_steady >= 5.0                 (measured 8.74 quiet; loaded box lower)
  ARM-B  CONTROL     a COPY of src/asr with DEFAULT_SEGMENT_MODE reverted to "fixed" --
                     the text must COLLAPSE (ratio <= 0.50; the measured trap is 0.229).
  ARM-C  CONTROL     a COPY of src/asr with INTRA_OP_NUM_THREADS reverted to 1 -- the thread
                     contract must FAIL (reported intra=1).

Nothing outside H:\\aireplay is written; H:\\sotto is READ ONLY. No audio device is opened.
No visible window: this script is `pythonw`, every child is spawned with CREATE_NO_WINDOW and
stdout goes to a FILE, and a 100 ms census of the tracked pids' top-level windows runs the whole
time (the house 60 s census cannot see a short window).
"""

from __future__ import annotations

import ctypes
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(r"H:\aireplay")
SRC = ROOT / "src"
PY = r"C:\Program Files\Python311\python.exe"
CREATE_NO_WINDOW = 0x08000000
LOGDIR = ROOT / "_main" / "logs"
RUNDIR = ROOT / "_main" / "runs" / "asr02"
CTL = ROOT / "_main" / "_asr02-ctl"
WAV_LONG = Path(r"H:\sotto\_main\_redux-long\plain-3600s.wav")
REF_LONG = ROOT / "_main" / "runs" / "threads11" / "silence-t4-p1.txt"
MODEL_DIR = ROOT / "models" / "parakeet-tdt-0.6b-v3-onnx"

OFFSET, MAXS = 900.0, 120.0
REF_CHARS = 814
REF_SHA = "746dfd19eabd1644d37dd5dbc9df4d661926b50c99d8d94520f732404bbd81cf"
RSS_WSET_BAND = (700.0, 1200.0)
RTFX_STEADY_MIN = 5.0

LINES: list[str] = []


def say(m: str) -> None:
    LINES.append(m)


# ---------------------------------------------------------------------------------------
# the window census -- 100 ms, own cadence, over the pids we spawned
# ---------------------------------------------------------------------------------------

class WindowCensus(threading.Thread):
    def __init__(self, every: float = 0.1):
        super().__init__(daemon=True)
        self.every = every
        self.pids: set[int] = set()
        self.samples = 0
        self.hits = 0
        self.distinct: set[int] = set()
        self._stop = threading.Event()

    def track(self, pid: int) -> None:
        self.pids.add(int(pid))

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        user32 = ctypes.windll.user32
        EnumWindows = user32.EnumWindows
        cb = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        while not self._stop.is_set():
            self.samples += 1
            found: list[tuple[int, int, str]] = []

            def visit(hwnd, _lparam):
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value in self.pids and user32.IsWindowVisible(hwnd):
                    n = user32.GetWindowTextLengthW(hwnd)
                    buf = ctypes.create_unicode_buffer(n + 1)
                    user32.GetWindowTextW(hwnd, buf, n + 1)
                    found.append((pid.value, hwnd, buf.value))
                return True

            try:
                EnumWindows(cb(visit), None)
            except Exception:  # noqa: BLE001
                pass
            for pid, hwnd, title in found:
                self.hits += 1
                self.distinct.add(pid)
                say(f"ALERTA-JANELA pid={pid} hwnd={hwnd} title={title!r}")
            self._stop.wait(self.every)


# ---------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------

def run(argv: list[str], log: Path, cwd: Path = SRC, timeout: int = 900,
        census: WindowCensus | None = None) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", encoding="utf-8") as fh:
        proc = subprocess.Popen(argv, stdout=fh, stderr=subprocess.STDOUT, cwd=str(cwd),
                                creationflags=CREATE_NO_WINDOW)
        if census is not None:
            census.track(proc.pid)
        try:
            return proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            return -9


def last_json(log: Path) -> dict | None:
    for line in reversed(log.read_text(encoding="utf-8", errors="replace").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def make_broken_copy(name: str, pattern: str, replacement: str) -> tuple[Path, int]:
    """Copy src/asr, rewrite EXACTLY ONE constant in constants.py. Returns (root, n_subs).

    The copy lives two levels under the repo root, so its repo-relative MODEL_DIR would point
    inside the control directory -- the caller passes the real --model-dir explicitly. That is
    the ONLY difference between the control and the product.
    """
    root = CTL / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    shutil.copytree(SRC / "asr", root / "asr", ignore=shutil.ignore_patterns("__pycache__"))
    const = root / "asr" / "constants.py"
    body = const.read_text(encoding="utf-8")
    n = body.count(pattern)
    if n == 1:
        const.write_text(body.replace(pattern, replacement), encoding="utf-8")
    say(f"[ctl:{name}] copy at {root} -- pattern {pattern!r} occurrences={n}")
    return root, n


# ---------------------------------------------------------------------------------------
# arms
# ---------------------------------------------------------------------------------------

def arm_static() -> dict:
    sys.path.insert(0, str(SRC))
    from asr import constants as C

    gates = {
        "intra_is_4": C.INTRA_OP_NUM_THREADS == 4,
        "inter_is_1": C.INTER_OP_NUM_THREADS == 1,
        "default_mode_silence": C.DEFAULT_SEGMENT_MODE == "silence",
        "level_hz_10": C.BLOCK_MS == 100 and C.LEVEL_HZ == 10,
        "max_seg_15": C.MAX_SEGMENT_S == 15.0,
        "min_silence_030": C.MIN_SILENCE_S == 0.30,
        "pad_010": C.PAD_S == 0.10,
        "encoder_share_095": C.ENCODER_SHARE_MIN == 0.95,
        "fixed_grid_ratio_0229": C.FIXED_GRID_RATIO == 0.229,
        "provenance_present": all(C.PROVENANCE.values()) and len(C.PROVENANCE) >= 15,
        "model_files_registered": all(
            (C.MODEL_DIR / n).exists() and (C.MODEL_DIR / n).stat().st_size == s
            for n, s in C.MODEL_FILE_SIZES.items()
        ),
    }
    say(f"[ARM-0 static] {gates}")
    return {"arm": "ARM-0", "kind": "static", "gates": gates, "ok": all(gates.values())}


def arm_product(census: WindowCensus) -> dict:
    log = LOGDIR / "oracle-02-armA-product.out"
    text_file = RUNDIR / "oracle-armA-text.txt"
    RUNDIR.mkdir(parents=True, exist_ok=True)
    argv = [PY, "-m", "asr.transcribe", "--wav", str(WAV_LONG), "--offset-s", str(OFFSET),
            "--max-s", str(MAXS), "--json", "--out-text", str(text_file), "--label", "oracle-A"]
    t0 = time.perf_counter()
    rc = run(argv, log, census=census)
    wall = time.perf_counter() - t0
    done = last_json(log) or {}
    text = text_file.read_text(encoding="utf-8") if text_file.exists() else ""
    import hashlib
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    th = done.get("threads", {})
    level = done.get("level", {})
    gates = {
        "rc_0": rc == 0,
        "threads_intra_4": th.get("intra") == 4,
        "threads_inter_1": th.get("inter") == 1,
        "cpu_provider_only": all(p == ["CPUExecutionProvider"] for p in th.get("session_providers", []))
                               and bool(th.get("session_providers")),
        "segment_mode_silence": done.get("segment_mode") == "silence",
        "segments_11": done.get("n_segments") == 11,
        "text_chars_814": len(text) == REF_CHARS,
        "text_sha_reference": sha == REF_SHA,
        "level_hz_10": level.get("hz") == 10.0,
        "level_events_10hz": level.get("n_events") == int(round(done.get("audio_s", 0) * 10)),
        "rss_wset_in_band": RSS_WSET_BAND[0] <= (done.get("rss_peak_wset_mb") or 0) <= RSS_WSET_BAND[1],
        "rtfx_steady_ge_5": (done.get("rtfx_steady") or 0) >= RTFX_STEADY_MIN,
    }
    say(f"[ARM-A product] rc={rc} wall={wall:.1f}s segs={done.get('n_segments')} "
        f"threads={th.get('intra')}/{th.get('inter')} chars={len(text)} sha={sha[:12]} "
        f"level={level.get('n_events')}@{level.get('hz')}Hz rss_wset={done.get('rss_peak_wset_mb')}MB "
        f"rtfx_steady={done.get('rtfx_steady')} cpu_med={done.get('cpu_median_pct')}%")
    say(f"[ARM-A gates] {gates}")
    return {"arm": "ARM-A", "kind": "product", "rc": rc, "wall_s": round(wall, 1), "gates": gates,
            "ok": all(gates.values()), "metrics": {k: done.get(k) for k in (
                "n_segments", "seg_median_s", "seg_max_s", "audio_s", "audio_processed_s", "load_s",
                "infer_s", "rtfx_infer", "rtfx_steady", "rtfx_slice", "rss_after_load_mb",
                "rss_peak_mb", "rss_peak_wset_mb", "cpu_median_pct", "cpu_max_pct",
                "cpu_load_median_pct", "cpu_load_max_pct")}, "level": level, "threads": th,
            "text_sha256": sha, "text_chars": len(text), "text": text}


def arm_control_fixed(census: WindowCensus) -> dict:
    root, n = make_broken_copy("fixed", "DEFAULT_SEGMENT_MODE = MODE_SILENCE",
                               "DEFAULT_SEGMENT_MODE = MODE_FIXED")
    log = LOGDIR / "oracle-02-armB-fixed.out"
    text_file = RUNDIR / "oracle-armB-text.txt"
    argv = [PY, "-m", "asr.transcribe", "--wav", str(WAV_LONG), "--offset-s", str(OFFSET),
            "--max-s", str(MAXS), "--json", "--out-text", str(text_file), "--label", "oracle-B-fixed",
            "--model-dir", str(MODEL_DIR)]
    rc = run(argv, log, cwd=root, census=census)
    done = last_json(log) or {}
    text = text_file.read_text(encoding="utf-8") if text_file.exists() else ""
    ref = REF_LONG.read_text(encoding="utf-8")
    from asr.parity import compare_texts

    cmp = compare_texts(ref, text)
    r = cmp["ratio"]
    gates = {
        "one_substitution": n == 1,
        "copy_ran": rc == 0,
        "mode_reported_fixed": done.get("segment_mode") == "fixed",
        "grid_is_12x10s": done.get("n_segments") == 12,
        # the control MUST lose the text: the grid cuts mid-word (05-onnx-asr.md:105)
        "text_collapsed_le_0.85": r <= 0.85,
        "text_not_identical": not cmp["exact"] and cmp["char_diff_blocks"] > 0,
        "collapsed_toward_measured_0.229": 0.05 <= r <= 0.60,
    }
    say(f"[ARM-B control fixed-grid] rc={rc} mode={done.get('segment_mode')} segs={done.get('n_segments')} "
        f"ratio={r} char-diffs={cmp['char_diff_blocks']} word-diffs={cmp['word_diff_blocks']} "
        f"(registered trap 0.229 vs the SIBLING CAPTIONS; here vs the 814-char silence reference) "
        f"chars ref/hyp={cmp['chars_ref']}/{cmp['chars_hyp']}")
    say(f"[ARM-B gates] {gates}")
    return {"arm": "ARM-B", "kind": "control-fixed-grid", "rc": rc, "ratio": r,
            "char_diff_blocks": cmp["char_diff_blocks"], "word_diff_blocks": cmp["word_diff_blocks"],
            "gates": gates, "ok": all(gates.values()), "text_head": text[:200]}


def arm_control_threads(census: WindowCensus) -> dict:
    root, n = make_broken_copy("threads", "INTRA_OP_NUM_THREADS = 4", "INTRA_OP_NUM_THREADS = 1")
    log = LOGDIR / "oracle-02-armC-threads.out"
    argv = [PY, "-m", "asr.transcribe", "--wav", str(WAV_LONG), "--offset-s", str(OFFSET),
            "--max-s", "40", "--json", "--label", "oracle-C-threads",
            "--model-dir", str(MODEL_DIR)]
    rc = run(argv, log, cwd=root, census=census)
    done = last_json(log) or {}
    th = done.get("threads", {})
    gates = {
        "one_substitution": n == 1,
        "copy_ran": rc == 0,
        "reverted_pin_visible": th.get("intra") == 1,
        "contract_violated": th.get("intra") != 4,  # the product's gate must be able to say NO
    }
    say(f"[ARM-C control thread-pin reverted] rc={rc} reported intra={th.get('intra')} "
        f"inter={th.get('inter')} -> the product contract (intra==4) is VIOLATED")
    say(f"[ARM-C gates] {gates}")
    return {"arm": "ARM-C", "kind": "control-thread-pin", "rc": rc, "reported": th,
            "gates": gates, "ok": all(gates.values())}


def main() -> int:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    RUNDIR.mkdir(parents=True, exist_ok=True)
    census = WindowCensus(0.1)
    census.start()
    say(f"oracle-02-asr start {time.strftime('%Y-%m-%dT%H:%M:%S')} "
        f"wav={WAV_LONG} [{OFFSET},{OFFSET + MAXS})")
    say(f"tracking pids: oracle={__import__('os').getpid()}")

    results = []
    results.append(arm_static())
    results.append(arm_product(census))
    results.append(arm_control_fixed(census))
    results.append(arm_control_threads(census))
    census.stop()
    time.sleep(0.3)

    product_ok = all(r["ok"] for r in results if r["kind"] in ("static", "product"))
    controls_red = all(r["ok"] for r in results if r["kind"].startswith("control"))
    census_ok = census.hits == 0
    say(f"census: samples={census.samples} every_ms=100 visible_hits={census.hits} "
        f"distinct_pids={len(census.distinct)}")
    say(f"product_arms_green={product_ok} controls_red_as_expected={controls_red} "
        f"census_no_visible_window={census_ok}")
    verdict = "PASS" if (product_ok and controls_red and census_ok) else "FAIL"
    say(f"ORACLE-02-ASR VERDICT: {verdict}")

    summary = {
        "verdict": verdict,
        "product_arms_green": product_ok,
        "controls_red_as_expected": controls_red,
        "census": {"samples": census.samples, "every_ms": 100, "visible_hits": census.hits,
                   "distinct_pids": len(census.distinct)},
        "arms": results,
        "log": LINES,
    }
    (RUNDIR / "oracle-02-asr.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                               encoding="utf-8")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    try:
        rc = main()
    except Exception:  # noqa: BLE001
        import traceback
        rc = 3
        LINES.append("EXCEPTION\n" + traceback.format_exc())
    (LOGDIR / "oracle-02-asr.log").write_text("\n".join(LINES) + f"\nORACLE-RC {rc}\n", encoding="utf-8")
    raise SystemExit(rc)
