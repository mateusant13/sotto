"""ORACLE for the verdict-word vs exit-code contract in `worker/sotto_worker.py`.

THE DEFECT THIS PINS (localised before the fix, in `main()`):
the top-level `done` verdict tested the DEVICE-SELECTION outcome first:

    if outcome in ("all-flat", "open-failed"):
        verdict = "all-candidate-taps-flat"
    elif ran_but_silent:
        verdict = "silent-device"

`ran_but_silent` is `bool(silent_rows) and not proved_alive["any"]` and the exit
code is `return 3 if ran_but_silent else 0`. When BOTH conditions hold in the
same run, the run emitted `state="silent-device"` (the loud status line), returned
exit 3, and yet its own `done` said `all-candidate-taps-flat`. The word and the
code disagreed INSIDE ONE RUN. Measured on disk before the fix:
`worker/runs/exit3-armB-worker.jsonl` -- `done` verdict "all-candidate-taps-flat",
device_outcome "all-flat", beside a silent-device status with blocks=34.

THE FIX is the ORDER (no vocabulary renamed): `ran_but_silent` -- the MEASURED,
device-attributable fact and the exact predicate the exit code is built from -- is
tested FIRST, so the word can no longer diverge from the code.

TWO ARMS, ONE COMMAND, and they cannot both pass by accident:

  GREEN  the REAL worker. Reproduces BOTH conditions in one run (a device that
         OPENED, ran a real window below the peak floor, and the ladder ended
         `all-flat`) and asserts the word AGREES with the exit code:
             rc == 3  AND  done.verdict == "silent-device"  AND  a silent-device
             status was emitted  AND  done.device_outcome in (all-flat, open-failed).

  RED    a COPY of the worker with the PRE-FIX ORDER restored (nothing else
         touched). The oracle builds the mutant TEXTUALLY and FAILS if it cannot
         find the branch to swap -- so the red arm can never pass vacuously.
         Asserts the contradiction is reproduced: rc == 3 (unchanged) while
         done.verdict != "silent-device" (i.e. "all-candidate-taps-flat"),
         with the silent-device status still present. If the mutant does NOT
         show the contradiction, the oracle is not discriminating -> FAIL.

  BLUE   the no-data case: the same silent device, stopped BELOW
         TAP_SILENT_BLOCKS. Must STILL say "all-candidate-taps-flat" with exit
         0 and NO silent-device status -- the fix reordered the branch, it did
         not rename a word out of existence.

GREEN + RED + BLUE together mean: the oracle reads the word, reads the code, the
reverted order makes it go red on the very input that reproduces both conditions,
and the OTHER word still lives for the input that does not.

BOTH CONDITIONS, cheaply and deterministically: `--device <silent endpoint>` makes
the first candidate rung C; `--max-chunks N` stops the run MID-WINDOW, so `outcome`
keeps its initial value "all-flat" (the rotation loop breaks on `stop.is_set()`
before it can set "explicit-flat"), while the candidate has already delivered
blocks below the floor. That is exactly (all-flat) AND (a silent row).

Usage: py -3 _main/verdict-order-oracle.py            (windowless: CREATE_NO_WINDOW)
Exit 0 = PASS, 1 = FAIL.  Every spawned worker is pythonw-free but created with
CREATE_NO_WINDOW alone -- it never puts a console window on the owner's screen.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKER_DIR = os.path.normpath(os.path.join(HERE, "..", "worker"))
WORKER = os.path.join(WORKER_DIR, "sotto_worker.py")
CONFIG = os.path.join(WORKER_DIR, "config.json")
RUNS = os.path.join(WORKER_DIR, "runs")
MUTANT = os.path.join(RUNS, "_verdict-order-mutant.py")

CREATE_NO_WINDOW = 0x08000000
MAX_CHUNKS = 8  # ~4.5 s of audio at 10 blocks/s -> ~45 blocks, >= TAP_SILENT_BLOCKS (20)
NO_DATA_CHUNKS = 1  # ~0.56 s -> ~5 blocks, BELOW TAP_SILENT_BLOCKS (20): the no-data case
WALL_TIMEOUT_S = 120

# The branch AS FIXED (word-consistent order) and AS IT WAS (pre-fix order).
FIXED_BRANCH = (
    '    if ran_but_silent:\n'
    '        verdict = "silent-device"\n'
    '    elif outcome in ("all-flat", "open-failed"):\n'
    '        verdict = "all-candidate-taps-flat"\n'
)
PREFIX_BRANCH = (
    '    if outcome in ("all-flat", "open-failed"):\n'
    '        verdict = "all-candidate-taps-flat"\n'
    '    elif ran_but_silent:\n'
    '        verdict = "silent-device"\n'
)

# A silent-loopback endpoint this box has measured at ~0.000122 peak. Tried in
# order; the first one that actually exists is used. If none exists the oracle
# FAILS loudly (it cannot reproduce the precondition) instead of passing green.
SILENT_CANDIDATES = [
    "Mapeador de som da Microsoft - Input",
    "CABLE Output (VB-Audio Virtual Cable)",
    "VoiceMeeter Output (VB-Audio Vo",
    "Mixagem estéreo (Realtek HD Audio Stereo input)",
]


def pick_silent_device() -> str | None:
    import sounddevice as sd

    names = [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
    for cand in SILENT_CANDIDATES:
        low = cand.lower()
        for n in names:
            if low in n.lower():
                return cand
    return None


def model_dir_abs() -> str:
    with open(CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    d = cfg.get("model", {}).get("dir")
    if not d:
        return os.path.join(WORKER_DIR, "models", "nemotron-3.5-asr-streaming-0.6b-int8")
    return d if os.path.isabs(d) else os.path.join(WORKER_DIR, d)


def build_mutant() -> tuple[bool, str]:
    """Return (ok, reason). Writes a copy of the worker with the PRE-FIX order."""
    with open(WORKER, encoding="utf-8") as f:
        src = f.read()
    n = src.count(FIXED_BRANCH)
    if n != 1:
        return False, (
            f"could not find the fixed verdict branch exactly once in the worker "
            f"(found {n}); the oracle cannot build its red arm"
        )
    mutant_src = src.replace(FIXED_BRANCH, PREFIX_BRANCH)
    if mutant_src == src or PREFIX_BRANCH not in mutant_src:
        return False, "mutant build produced no change"
    os.makedirs(RUNS, exist_ok=True)
    with open(MUTANT, "w", encoding="utf-8") as f:
        f.write(mutant_src)
    return True, ""


def run_worker(script: str, out_path: str, device: str, model_dir: str,
               max_chunks: int = MAX_CHUNKS) -> dict:
    out = open(out_path, "wb")
    errf = open(out_path + ".err", "wb")
    env = dict(os.environ)
    # The worker inserts ITS OWN dir into sys.path for lang_prompt/wasapi_loopback;
    # for the mutant that dir is runs/, so put the real worker dir on PYTHONPATH.
    env["PYTHONPATH"] = WORKER_DIR + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [
            sys.executable, script,
            "--config", CONFIG,
            "--model", model_dir,
            "--device", device,
            "--max-chunks", str(max_chunks),
            "--tap-window", "60",
        ],
        stdout=out, stderr=errf, stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW, cwd=WORKER_DIR, env=env,
    )
    try:
        rc = proc.wait(timeout=WALL_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        proc.kill()
        rc = proc.wait()
    out.close()
    errf.close()

    raw_lines, statuses = [], []
    with open(out_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            if o.get("type") == "status":
                statuses.append(o)
                if o.get("state") in ("silent-device", "device-exhausted", "done"):
                    raw_lines.append(line)
    done = next((o for o in statuses if o.get("state") == "done"), {})
    silent = next((o for o in statuses if o.get("state") == "silent-device"), None)
    return {"rc": rc, "done": done, "silent": silent, "all_status": statuses,
            "raw_lines": raw_lines}


def main() -> int:
    failures: list[str] = []
    os.makedirs(RUNS, exist_ok=True)

    device = pick_silent_device()
    if device is None:
        print(json.dumps({"oracle": "verdict-order", "verdict": "FAIL",
                          "failures": ["no silent-loopback input device found; cannot "
                                       "reproduce the both-hold precondition"]}))
        return 1
    model_dir = model_dir_abs()

    # ── GREEN: the real worker. Both conditions in one run, word MUST match code.
    g = run_worker(WORKER, os.path.join(RUNS, "verdict-order-green.jsonl"), device, model_dir)
    g_done = g["done"]
    g_verdict = g_done.get("verdict")
    g_outcome = g_done.get("device_outcome")
    g_rc = g["rc"]
    print(json.dumps({
        "arm": "green-real-worker",
        "rc": g_rc,
        "done_verdict": g_verdict,
        "silent_status_verdict": (g["silent"] or {}).get("verdict"),
        "device_outcome": g_outcome,
        "proved_alive": g_done.get("proved_alive"),
        "device": (g["silent"] or {}).get("device"),
        "peak": (g["silent"] or {}).get("peak"),
        "blocks": (g["silent"] or {}).get("blocks"),
        "both_conditions_hold": bool(g_rc == 3 and g["silent"] is not None
                                     and g_outcome in ("all-flat", "open-failed")),
        "word_matches_code": (g_verdict == "silent-device") == (g_rc == 3),
        "lines": g["raw_lines"],
    }, ensure_ascii=False), flush=True)

    if g["silent"] is None:
        failures.append("GREEN: no silent-device status emitted; both-hold precondition not met")
    if g_outcome not in ("all-flat", "open-failed"):
        failures.append(f"GREEN: device_outcome={g_outcome!r}, both-hold precondition (all-flat/open-failed) not met")
    if g_rc != 3:
        failures.append(f"GREEN: expected exit 3 (a measured silent device), got {g_rc}")
    if g_verdict != "silent-device":
        failures.append(f"GREEN: done verdict was {g_verdict!r}, expected 'silent-device'")
    if (g["silent"] or {}).get("blocks", 0) < 20:
        failures.append(f"GREEN: silent verdict on only {(g['silent'] or {}).get('blocks')} blocks; not a real window")

    # ── RED: a COPY with the pre-fix order. Must reproduce the contradiction.
    ok, why = build_mutant()
    if not ok:
        failures.append(f"RED: {why}")
        mutant_result = None
    else:
        r = run_worker(MUTANT, os.path.join(RUNS, "verdict-order-red.jsonl"), device, model_dir)
        r_done = r["done"]
        r_verdict = r_done.get("verdict")
        r_outcome = r_done.get("device_outcome")
        r_rc = r["rc"]
        contradiction = (r_rc == 3 and r["silent"] is not None
                         and r_verdict != "silent-device")
        print(json.dumps({
            "arm": "red-prefix-order-mutant",
            "rc": r_rc,
            "done_verdict": r_verdict,
            "silent_status_verdict": (r["silent"] or {}).get("verdict"),
            "device_outcome": r_outcome,
            "both_conditions_hold": bool(r_rc == 3 and r["silent"] is not None
                                         and r_outcome in ("all-flat", "open-failed")),
            "word_matches_code": (r_verdict == "silent-device") == (r_rc == 3),
            "contradiction_reproduced": contradiction,
            "lines": r["raw_lines"],
        }, ensure_ascii=False), flush=True)

        if r["silent"] is None:
            failures.append("RED: mutant emitted no silent-device status; both conditions did not hold")
        if r_rc != 3:
            failures.append(f"RED: mutant exit was {r_rc}, expected 3 (exit code is not what changed)")
        if not contradiction:
            failures.append(
                f"RED: mutant did NOT reproduce the contradiction (rc={r_rc}, verdict={r_verdict!r}); "
                "the oracle is not discriminating")
        mutant_result = r

    # ── BLUE: the no-data case. The fix must NOT swallow the other word: a
    # candidate that stayed flat without reaching TAP_SILENT_BLOCKS is NOT a
    # silent device, and the vocabulary must survive. --max-chunks 1 stops
    # before 20 blocks, so no silent row exists, ran_but_silent is false, and
    # the run must STILL say all-candidate-taps-flat with exit 0 and NO
    # silent-device status.
    nd = run_worker(WORKER, os.path.join(RUNS, "verdict-order-blue.jsonl"), device, model_dir,
                    max_chunks=NO_DATA_CHUNKS)
    nd_done = nd["done"]
    print(json.dumps({
        "arm": "blue-no-data-must-not-be-silent",
        "rc": nd["rc"],
        "done_verdict": nd_done.get("verdict"),
        "device_outcome": nd_done.get("device_outcome"),
        "blocks": nd_done.get("blocks"),
        "silent_status_present": nd["silent"] is not None,
    }, ensure_ascii=False), flush=True)
    if nd["silent"] is not None:
        failures.append("BLUE: a run below TAP_SILENT_BLOCKS emitted a silent-device status")
    if nd_done.get("verdict") != "all-candidate-taps-flat":
        failures.append(f"BLUE: expected 'all-candidate-taps-flat' (no-data), got {nd_done.get('verdict')!r}")
    if nd["rc"] != 0:
        failures.append(f"BLUE: expected exit 0 (no measured silent device), got {nd['rc']}")

    # The oracle's own verdict: GREEN proves word==code, RED proves a reverted
    # order makes it RED, BLUE proves the other word still exists.
    print(json.dumps({
        "oracle": "verdict-order",
        "device": device,
        "green_word_matches_code": (g["done"].get("verdict") == "silent-device") == (g["rc"] == 3),
        "red_contradiction": bool(mutant_result and mutant_result["rc"] == 3
                                  and (mutant_result["done"].get("verdict") != "silent-device")),
        "blue_no_data_word": nd_done.get("verdict"),
        "verdict": "PASS" if not failures else "FAIL",
        "failures": failures,
    }, ensure_ascii=False), flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
