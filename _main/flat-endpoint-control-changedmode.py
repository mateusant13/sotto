"""CONTROL: what would happen if RPC_E_CHANGED_MODE were treated as a hard error?

The card and the first draft of the sibling oracle both read "keep the negative
HRESULTs as errors" literally, which makes RPC_E_CHANGED_MODE (0x80010106) fatal.
This control runs the REAL worker against a variant module built from the FIXED
source with exactly that one change, so the answer is a measurement and not an
opinion.

Why it matters: `RPC_E_CHANGED_MODE` means "COM is already running on this thread
in ANOTHER apartment". It is the state the worker's ladder thread is in on this
box, because `device_candidates()` imports sounddevice and calls
`sd.query_devices()` before rung (a) is probed, and that leaves the thread in an
STA. With the mode treated as fatal, `loopback_device_spec()` swallows the
exception and rung (a) is never even OFFERED, so the ladder falls back to the four
PortAudio candidates that carry digital silence -- which is precisely the defect
this lane exists to remove.

    py -3 _main/flat-endpoint-control-changedmode.py -- --max-seconds 45 --tap-window 5

Everything after `--` is passed to the worker unchanged.
"""
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "worker", "wasapi_loopback.py")
VARIANT_DIR = os.path.join(HERE, "_cmfatal-changedmode")

MARKER = "        return COM_ALREADY"
REPLACEMENT = (
    "        raise WasapiError(\"CoInitializeEx failed: %s\" % _fmt(hr))  "
    "# CONTROL: the negative HRESULT is fatal\n"
)


def build_variant():
    src = io.open(SRC, encoding="utf-8").read()
    n = src.count(MARKER)
    if n != 1:
        print("REFUSING: marker %r occurs %d times in %s (expected exactly 1)"
              % (MARKER.strip(), n, SRC))
        return None
    if not os.path.isdir(VARIANT_DIR):
        os.makedirs(VARIANT_DIR)
    out = os.path.join(VARIANT_DIR, "wasapi_loopback.py")
    io.open(out, "w", encoding="utf-8", newline="\n").write(src.replace(MARKER, REPLACEMENT))
    return out


def main():
    av = sys.argv[1:]
    if av and av[0] == "--":
        av = av[1:]
    variant = build_variant()
    if variant is None:
        return 2
    print("variant (changed-mode fatal): %s" % variant)
    # The variant dir goes FIRST, so the worker's own `import wasapi_loopback`
    # resolves to it; `worker/` still resolves everything else the worker needs.
    driver = (
        "import os,sys\n"
        "sys.path.insert(0, %r)\n"
        "sys.path.insert(0, %r)\n"
        "sys.argv = ['sotto_worker.py'] + %r\n"
        "import sotto_worker\n"
        "sys.exit(sotto_worker.main())\n"
        % (os.path.join(ROOT, "worker"), VARIANT_DIR, av)
    )
    cwd = ROOT
    proc = subprocess.run(
        [sys.executable, "-c", driver],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    sys.stdout.write(proc.stdout.decode("utf-8", "replace"))
    sys.stdout.flush()
    sys.stderr.write(proc.stderr.decode("utf-8", "replace"))
    sys.stderr.flush()
    print("WORKER_RC=%d" % proc.returncode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
