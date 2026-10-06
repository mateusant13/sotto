"""BlankFramesRootCause — drive the decisive experiment. No window: pythonw + CREATE_NO_WINDOW."""
import os
import subprocess
import sys
import time

ROOT = r"H:\sotto"
PYW = r"C:\Program Files\Python311\pythonw.exe"
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
CFG = os.path.join(ROOT, "worker", "config.json")
CREATE_NO_WINDOW = 0x08000000

ARMS = [
    ("a_22050_full", "_main/bfrc_a_22050_full.wav"),
    ("a_22050_quiet", "_main/bfrc_a_22050_quiet.wav"),
    ("c_48000_full", "_main/bfrc_c_48000_full.wav"),
    ("c_48000_quiet", "_main/bfrc_c_48000_quiet.wav"),
    ("b_live", None),
]

only = sys.argv[1:] or [a[0] for a in ARMS]
for name, wav in ARMS:
    if name not in only:
        continue
    env = os.environ.copy()
    env.pop("SOTTO_AUDIO_FILE", None)
    if wav:
        env["SOTTO_AUDIO_FILE"] = os.path.join(ROOT, wav).replace("/", "\\")
    argv = [PYW, WORKER, "--config", CFG, "--stats-interval", "10"]
    if wav is None:
        argv += ["--max-seconds", "25"]
    out = open(os.path.join(ROOT, "_main", f"bfrc_{name}.jsonl"), "w", encoding="utf-8")
    errf = open(os.path.join(ROOT, "_main", f"bfrc_{name}.err"), "w", encoding="utf-8")
    t0 = time.time()
    p = subprocess.Popen(argv, cwd=ROOT, env=env, stdout=out, stderr=errf,
                         creationflags=CREATE_NO_WINDOW)
    try:
        rc = p.wait(timeout=180)
    except subprocess.TimeoutExpired:
        p.kill()
        rc = "TIMEOUT"
    out.close()
    errf.close()
    print(f"ARM {name}: rc={rc} wall={time.time()-t0:.1f}s audio_file={env.get('SOTTO_AUDIO_FILE')}")
