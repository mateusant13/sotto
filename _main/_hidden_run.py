"""Run a child process with NO console window, capturing its stdout/stderr to a file.

House rule: never leave a visible console on the owner's screen.  `pythonw.exe` is
windowless but has `sys.stdout is None`, so it cannot be redirected from the shell;
`python.exe` gives real stdout but risks a console.  This launcher gets both:
CREATE_NO_WINDOW (0x08000000) plus explicit file handles.

  pythonw.exe _hidden_run.py --out <file> --exe <exe> -- [args...]
"""
import argparse, subprocess, sys

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--exe", required=True)
ap.add_argument("rest", nargs=argparse.REMAINDER)
a = ap.parse_args()

argv = [a.exe] + [x for x in a.rest if x != "--"]
CREATE_NO_WINDOW = 0x08000000

with open(a.out, "wb") as fh:
    p = subprocess.Popen(
        argv,
        stdout=fh,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )
    rc = p.wait()

sys.exit(rc)
