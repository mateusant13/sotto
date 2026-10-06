"""Read-only census: which python/pythonw processes are alive, and their cmdlines.

Written for the SottoFlatEndpointNaApp measurement (2026-10-06) because this box
has no `wmic` (removed) and `tasklist` gives no command line. Nothing is started,
signalled or killed here.
"""
import subprocess
import sys

_PS = (
    "Get-CimInstance Win32_Process | "
    "Where-Object { $_.Name -eq 'pythonw.exe' -or $_.Name -eq 'python.exe' } | "
    "Select-Object ProcessId,Name,CommandLine | "
    "ForEach-Object { \"{0}|{1}|{2}\" -f $_.ProcessId,$_.Name,$_.CommandLine }"
)

r = subprocess.run(
    ["powershell", "-NoProfile", "-NonInteractive", "-Command", _PS],
    capture_output=True,
)
out = r.stdout.decode("cp850", "replace")
for line in out.splitlines():
    line = line.strip()
    if not line:
        continue
    parts = line.split("|", 2)
    if len(parts) == 3:
        pid, name, cmd = parts
        print("%-7s %-11s %s" % (pid, name, cmd))
    else:
        print("RAW:", line)
if r.returncode != 0:
    sys.stderr.write(r.stderr.decode("cp850", "replace"))
