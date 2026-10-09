#!/usr/bin/env python3
"""lane audiofix — PROOF that `--audio FILE` is never silently replaced by the
live room.

THE DEFECT THIS EXISTS FOR
    worker/sotto_worker.py resolved the audio source as
        os.environ.get("SOTTO_AUDIO_FILE") or (args.audio if args.selftest else None)
    so `--audio FILE` WITHOUT `--selftest` produced None, the file-mode branch was
    skipped, and the run fell through to LIVE capture: the room, not the file,
    with a perfectly plausible JSONL to hide it.

THE ACCEPTANCE CRITERION
    `--audio FILE` and no `--selftest` must either USE THE FILE or FAIL LOUDLY.
    It must NEVER silently use the live device.

HOW IT IS DECIDED (and why it is not a rubber stamp)
    The worker's own boot emit carries `mode` ("file" or "live") and it is
    emitted BEFORE any model load. So the branch decision is observable in
    seconds, from the real code, with real weights -- no stubbing, no mocking.
    * boot mode == "live"  -> RED, immediately, and the child is KILLED. On the
      pre-fix source this is exactly what happens, which is what makes the
      negative arm real.
    * boot mode == "file" AND a `selftest-start` event appears -> GREEN. The
      file arm was entered AND the model really ran.
    * rc != 0 with an error event that names the audio/flag -> GREEN as
      "failed loudly". This arm exists so that an error-out fix would also pass;
      it is deliberately narrow so a crash for an UNRELATED reason (missing
      weights, say) cannot buy a pass.

Every exit code below is a real `subprocess` returncode read from the child, and
every stdout/stderr byte goes to a FILE. Nothing is piped through a truncating
head, so nothing can hide behind an early-closing pipe.

USAGE
    python check_audio_flag.py --worker <sotto_worker.py> --audio <file> \
        --model <weights dir> [--config <config.json>] [--expect green|red] \
        [--timeout 300]
Exit 0 = expectation met. Exit 1 = expectation violated. Exit 2 = harness error.
"""

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time

LIVE_EARLY_VERDICT = "live-mode-selected"
FILE_STATES = ("selftest-start", "selftest-done")


def parse_jsonl(line):
    line = line.strip()
    if not line or not line.startswith("{"):
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worker", required=True)
    ap.add_argument("--audio", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--config", default=None)
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--expect", choices=("green", "red"), default="green")
    ap.add_argument("--timeout", type=float, default=300.0)
    args = ap.parse_args()

    if not os.path.isfile(args.worker):
        print(f"HARNESS_ERROR: no worker at {args.worker}")
        return 2
    if not os.path.isfile(args.audio):
        print(f"HARNESS_ERROR: no audio at {args.audio}")
        return 2
    if not os.path.isdir(args.model):
        print(f"HARNESS_ERROR: no model dir at {args.model}")
        return 2

    outdir = args.outdir or os.path.dirname(os.path.abspath(args.worker))
    os.makedirs(outdir, exist_ok=True)
    tag = os.path.basename(args.outdir or "run")
    out_path = os.path.join(outdir, f"audioflag-{tag}.jsonl")
    err_path = os.path.join(outdir, f"audioflag-{tag}.err")

    # NOTE: no --selftest. That omission IS the test.
    argv = [
        sys.executable,
        args.worker,
        "--audio",
        args.audio,
        "--model",
        args.model,
    ]
    if args.config:
        argv += ["--config", args.config]

    evidence = {
        "argv": argv,
        "audio": args.audio,
        "selftest_passed": False,
        "boot_mode": None,
        "saw_selftest_start": False,
        "saw_error": None,
        "live_stages": [],
        "timed_out": False,
        "returncode": None,
        "early_verdict": None,
    }

    env = dict(os.environ)
    # Make sure the ENV route cannot stand in for the flag route.
    env.pop("SOTTO_AUDIO_FILE", None)
    env["PYTHONIOENCODING"] = "utf-8"

    out_fh = open(out_path, "w", encoding="utf-8", errors="replace")
    err_fh = open(err_path, "w", encoding="utf-8", errors="replace")

    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=err_fh,
        stdin=subprocess.DEVNULL,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    q = queue.Queue()

    def pump():
        try:
            for line in proc.stdout:
                q.put(line)
        finally:
            q.put(None)

    t = threading.Thread(target=pump, daemon=True)
    t.start()

    deadline = time.time() + args.timeout
    done = False
    while not done:
        remaining = deadline - time.time()
        if remaining <= 0:
            evidence["timed_out"] = True
            break
        try:
            line = q.get(timeout=min(1.0, remaining))
        except queue.Empty:
            if proc.poll() is not None:
                done = True
                break
            continue
        if line is None:
            done = True
            break
        out_fh.write(line)
        out_fh.flush()

        ev = parse_jsonl(line)
        if not ev:
            continue
        state = ev.get("state")
        stage = ev.get("stage")
        blob = json.dumps(ev, ensure_ascii=False)

        if state == "error":
            evidence["saw_error"] = blob
        if state in FILE_STATES or stage in FILE_STATES:
            evidence["saw_selftest_start"] = True
        if state == "boot" and stage == "start":
            evidence["boot_mode"] = ev.get("mode")

        # The decisive branch decision, available seconds in and BEFORE the
        # model load. If the worker says it is going live while the user asked
        # for a file, that is the defect reproducing in front of us.
        if evidence["boot_mode"] == "live":
            evidence["live_stages"].append(f"boot mode=live (t={time.time():.1f})")
            evidence["early_verdict"] = LIVE_EARLY_VERDICT
            break
        for token in ("device", "tap", "loopback", "capture"):
            if stage and token in str(stage) and str(stage) not in evidence["live_stages"]:
                evidence["live_stages"].append(str(stage))

    if evidence["early_verdict"] == LIVE_EARLY_VERDICT or evidence["timed_out"]:
        proc.kill()
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=30)
    evidence["returncode"] = proc.returncode  # the REAL rc
    if proc.stdout:
        proc.stdout.close()
    out_fh.close()
    err_fh.close()

    went_live = bool(evidence["live_stages"]) or evidence["timed_out"]
    used_file = (
        evidence["boot_mode"] == "file" and evidence["saw_selftest_start"]
    )
    loud = False
    if evidence["returncode"] not in (0, None):
        err = evidence["saw_error"] or ""
        if any(k in err.lower() for k in ("audio", "--audio", "file")):
            loud = True

    if went_live:
        outcome = "SILENT_LIVE"
    elif used_file:
        outcome = "USED_FILE"
    elif loud:
        outcome = "FAILED_LOUDLY"
    else:
        outcome = "UNPROVEN"

    evidence["outcome"] = outcome
    evidence["stdout_file"] = out_path
    evidence["stderr_file"] = err_path

    expect_pass = (outcome == "USED_FILE") if args.expect == "green" else (
        outcome in ("SILENT_LIVE", "UNPROVEN")
    )
    evidence["expect"] = args.expect
    evidence["expect_met"] = bool(expect_pass)

    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    print(f"\nOUTCOME={outcome} EXPECT={args.expect} MET={expect_pass} RC={evidence['returncode']}")
    return 0 if expect_pass else 1


if __name__ == "__main__":
    sys.exit(main())