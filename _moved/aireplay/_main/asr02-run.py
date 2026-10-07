#!/usr/bin/env pythonw
"""asr02-run.py -- drive the product CLI headlessly and record the reproduction.

Never a visible window: this script is `pythonw`, and every child is spawned with
CREATE_NO_WINDOW and its stdout redirected to a FILE (never a pipe, never a console).
It never opens an audio device (wav files only) and writes nothing outside H:\\aireplay.

Stages (argv, default all): smoke repro parity regress
  smoke    `python -m asr.transcribe` on the 8.5 s EN clip -- NDJSON contract + `--json` contract
  repro    the headline run: plain-3600s.wav [900,1020), silence, intra_op=4, `--json --phases`
  parity   `python -m asr.parity --arm en-8s --arm pt-15s` (the TERNARY oracle arms)
  regress  the same-engine regression lock, compared from the produced text (no model run)
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"H:\aireplay")
SRC = ROOT / "src"
PY = r"C:\Program Files\Python311\python.exe"
CREATE_NO_WINDOW = 0x08000000
LOGDIR = ROOT / "_main" / "logs"
RUNDIR = ROOT / "_main" / "runs" / "asr02"
SOTTO = Path(r"H:\sotto")
WAV_LONG = SOTTO / "_main" / "_redux-long" / "plain-3600s.wav"
WAV_EN = SOTTO / "_main" / "_redux-long" / "src-en-8s.wav"
REF_LONG = ROOT / "_main" / "runs" / "threads11" / "silence-t4-p1.txt"

LINES: list[str] = []


def say(msg: str) -> None:
    LINES.append(msg)


def run(argv: list[str], log: Path, cwd: Path = SRC, timeout: int = 1800,
        err_log: Path | None = None) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    with open(log, "w", encoding="utf-8") as fh:
        err = open(err_log, "w", encoding="utf-8") if err_log else subprocess.STDOUT
        try:
            proc = subprocess.Popen(argv, stdout=fh, stderr=err, cwd=str(cwd),
                                    creationflags=CREATE_NO_WINDOW)
            try:
                rc = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                rc = -9
        finally:
            if err_log:
                err.close()
    say(f"$ {' '.join(argv)}  -> rc={rc} in {time.perf_counter() - t0:.1f}s  log={log}")
    return rc


def read_ndjson(log: Path) -> list[dict]:
    events = []
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def stage_smoke() -> dict:
    out = {}
    log1 = LOGDIR / "asr02-smoke-en.ndjson"
    rc1 = run([PY, "-m", "asr.transcribe", "--wav", str(WAV_EN), "--label", "smoke-en"], log1)
    ev1 = read_ndjson(log1)
    kinds = [e.get("type") for e in ev1]
    done = next((e for e in ev1 if e.get("type") == "done"), None)
    out["ndjson"] = {
        "rc": rc1, "n_lines": len(ev1), "kinds": kinds,
        "n_level": kinds.count("level"), "n_segment": kinds.count("segment"),
        "done_last": bool(kinds) and kinds[-1] == "done",
        "level_hz": done["level"]["hz"] if done else None,
        "audio_s": done["audio_s"] if done else None,
        "text": done["text"] if done else None,
        "threads": done["threads"] if done else None,
        "rss_peak_wset_mb": done["rss_peak_wset_mb"] if done else None,
        "cpu_infer_median_pct": done["cpu_median_pct"] if done else None,
        "cpu_infer_max_pct": done["cpu_max_pct"] if done else None,
        "cpu_load_median_pct": done["cpu_load_median_pct"] if done else None,
        "cpu_load_max_pct": done["cpu_load_max_pct"] if done else None,
        "rtfx_steady": done["rtfx_steady"] if done else None,
    }
    log2 = LOGDIR / "asr02-smoke-en-json.out"
    rc2 = run([PY, "-m", "asr.transcribe", "--wav", str(WAV_EN), "--json", "--level", "off",
               "--label", "smoke-en-json"], log2, err_log=LOGDIR / "asr02-smoke-en-json.err")
    body = [ln for ln in log2.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    one = None
    if len(body) == 1:
        try:
            one = json.loads(body[0])
        except json.JSONDecodeError:
            one = None
    out["json"] = {"rc": rc2, "n_stdout_lines": len(body), "parsed": one is not None,
                   "type": (one or {}).get("type"), "chars": len((one or {}).get("text", "")),
                   "first_line_bytes": len(body[0].encode()) if body else 0}
    say(f"[smoke] ndjson events={out['ndjson']['n_lines']} levels={out['ndjson']['n_level']} "
        f"done_last={out['ndjson']['done_last']} | --json lines={out['json']['n_stdout_lines']} "
        f"parsed={out['json']['parsed']}")
    return out


def stage_repro() -> dict:
    RUNDIR.mkdir(parents=True, exist_ok=True)
    log = LOGDIR / "asr02-repro-slice900-1020.out"
    text_file = RUNDIR / "repro-silence-t4.txt"
    rc = run([PY, "-m", "asr.transcribe", "--wav", str(WAV_LONG), "--offset-s", "900",
              "--max-s", "120", "--json", "--phases", "--out-text", str(text_file),
              "--label", "repro-900-1020-silence-t4"], log)
    events = read_ndjson(log)
    done = next((e for e in events if e.get("type") == "done"), None)
    if done is None:
        say(f"[repro] NO done object (rc={rc}) -- see {log}")
        return {"rc": rc, "error": "no done object"}
    (RUNDIR / "repro-silence-t4.json").write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
    ref = REF_LONG.read_text(encoding="utf-8")
    # the reference FILE carries a trailing newline; the transcript does not
    same = done["text"].strip() == ref.strip()
    say(f"[repro] rc={rc} segs={done['n_segments']} audio={done['audio_s']}s "
        f"rtfx(steady/infer/slice)={done['rtfx_steady']}/{done['rtfx_infer']}/{done['rtfx_slice']} "
        f"rss(load/peak/wset)={done['rss_after_load_mb']}/{done['rss_peak_mb']}/{done['rss_peak_wset_mb']}MB "
        f"cpu(med/max)={done['cpu_median_pct']}/{done['cpu_max_pct']}% "
        f"level={done['level']['n_events']}@{done['level']['hz']}Hz threads={done['threads']['intra']}/"
        f"{done['threads']['inter']} chars={len(done['text'])} text==reference:{same}")
    return {"rc": rc, "done": done, "text_matches_reference": same,
            "reference_chars": len(ref.strip())}


def stage_parity() -> dict:
    RUNDIR.mkdir(parents=True, exist_ok=True)
    log = LOGDIR / "asr02-parity-ternary.out"
    js = RUNDIR / "parity-ternary.json"
    rc = run([PY, "-m", "asr.parity", "--arm", "en-8s", "--arm", "pt-15s", "--json", str(js)], log)
    say(f"[parity] rc={rc} (0 = every arm met its expectation) -- {log}")
    return {"rc": rc, "json": str(js)}


def stage_regress() -> dict:
    RUNDIR.mkdir(parents=True, exist_ok=True)
    hyp = RUNDIR / "repro-silence-t4.txt"
    if not hyp.exists():
        say("[regress] no reproduction text yet -- run the repro stage first")
        return {"rc": None, "error": "missing hyp"}
    log = LOGDIR / "asr02-parity-long-regression.out"
    js = RUNDIR / "parity-long-regression.json"
    rc = run([PY, "-m", "asr.parity", "--wav", str(WAV_LONG), "--oracle", str(REF_LONG),
              "--kind", "regression", "--offset-s", "900", "--max-s", "120",
              "--hyp", str(hyp), "--json", str(js)], log)
    say(f"[regress] rc={rc} (compares the produced text, no model run) -- {log}")
    return {"rc": rc, "json": str(js)}


def main() -> int:
    RUNDIR.mkdir(parents=True, exist_ok=True)
    stages = sys.argv[1:] or ["smoke", "repro", "parity", "regress"]
    summary: dict = {"stages": {}, "started": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if "smoke" in stages:
        summary["stages"]["smoke"] = stage_smoke()
    if "repro" in stages:
        summary["stages"]["repro"] = stage_repro()
    if "parity" in stages:
        summary["stages"]["parity"] = stage_parity()
    if "regress" in stages:
        summary["stages"]["regress"] = stage_regress()
    summary["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (RUNDIR / "run-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str),
                                             encoding="utf-8")
    return 0


if __name__ == "__main__":
    LOGDIR.mkdir(parents=True, exist_ok=True)
    try:
        rc = main()
    except Exception:  # noqa: BLE001
        import traceback
        rc = 3
        LINES.append("EXCEPTION\n" + traceback.format_exc())
    (LOGDIR / "asr02-run.log").write_text("\n".join(LINES) + f"\nRUN-RC {rc}\n", encoding="utf-8")
    raise SystemExit(rc)
