"""Append a receipt to the shell's run log from a place cmd.exe cannot.

MEASURED 2026-10-12 (Lead, evidence in _main/receipt-20261012-runcmd-receipts.md):
cmd.exe's own `>>` append onto H:/sotto/_main/webview-run.log is REFUSED with
error 32 ("the file is already being used by another process") whenever the app
is running, which since the Windows autostart task (`schtasks /create /tn Sotto`,
logon trigger, registered 2026-10-12) is the normal state of the box. The same
probe in the same instant, app running:

    cmd /c "echo X >> _main/webview-run.log"   -> error 32, log +0 bytes
    python open("...","a").write("X
")        -> log +17 bytes

This helper lives BESIDE run.cmd in app/webview/ on purpose: the wrapper calls it
as "%HERE%run-cmd-log-append.py", and the gap arms of
_main/run-cmd-exit-oracle.py copy a TREE that carries app/webview/*.py but leaves
_main/ EMPTY -- a helper under _main/ is therefore absent in those copies and the
receipt is lost there (measured 2026-10-12: the G3 arm then found no HANG receipt).
So `run.cmd` writes its two receipts -- the pre-flight refusal (row G5) and the
HANG report (row G3) -- through this helper, which appends with the SAME primitive
python uses, and which therefore works whether or not the app is up.

Nothing is printed: the helper is meant to run under pythonw.exe, whose stdout is
None, so a `print()` is a no-op there (that is the reason run.cmd documents the
FILE as the receipt, not the screen).

Usage:
    run-cmd-log-append.py LOGFILE [--append-file PATH ...] [--line TEXT ...]

It exits 0 even when the append FAILS: a lost receipt must not turn a good launch
into a failed one. The reason goes to stderr, which under pythonw is nowhere.
"""
import io
import sys

def _append_file(path):
    """Return the file's text, or None when it cannot be read."""
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError as exc:
        sys.stderr.write("run-cmd-log-append: cannot read %s: %s\n" % (path, exc))
        return None

def main(argv):
    if not argv:
        sys.stderr.write("run-cmd-log-append: no log path given\n")
        return 2
    log = argv[0]
    pieces = []
    index = 1
    while index < len(argv):
        key = argv[index]
        if key == "--append-file" and index + 1 < len(argv):
            text = _append_file(argv[index + 1])
            if text is not None:
                if text and not text.endswith("\n"):
                    text += "\n"
                pieces.append(text)
            index += 2
        elif key == "--line" and index + 1 < len(argv):
            pieces.append(argv[index + 1] + "\n")
            index += 2
        else:
            sys.stderr.write("run-cmd-log-append: bad argument %r\n" % (key,))
            return 2
    text = "".join(pieces)
    if not text:
        return 0
    try:
        with io.open(log, "a", encoding="utf-8") as handle:
            handle.write(text)
    except OSError as exc:
        sys.stderr.write("run-cmd-log-append: cannot append to %s: %s\n" % (log, exc))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))