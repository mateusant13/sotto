"""THE REAL LAUNCH GATE — the shipped shell, the shipped panel, no fixtures.

The brief's own command, verbatim: the app's documented launch with
`--dump-dom --dump-dom-wait 10 --no-hotkey --no-hot-reload --exit-after 45`, and
the verdict is whether the shell's own `BRIDGE_GATE` line says GREEN.

WHY `--no-hotkey` IS NOT OPTIONAL: Alt+C is the app's only control, so a probe
launch that registers it answers the owner's keypress with its own panel. WHY
`--with-worker` IS NOT PASSED: this arm measures the PANEL, and the shell's own
`measurement-flag` suppression keeps the ~2 GB model load and the audio tap out
of it. WHY the shell is spawned through `spawn_hidden`: a visible console on the
owner's screen is a defect this repo has already been bitten by twice, and a
window census samples once per 60 s — too slowly to prove absence.
"""
import os
import re
import subprocess
import sys
import time

ROOT = r"H:\sotto"
WEBVIEW = os.path.join(ROOT, "app", "webview")
PYW = r"C:\Program Files\Python311\pythonw.exe"
CREATE_NO_WINDOW = 0x08000000

log = os.path.join(ROOT, "_main", "panel-per-theme-launch.log")
dom = os.path.join(ROOT, "_main", "panel-per-theme-launch.dom.html")

argv = [PYW, os.path.join(WEBVIEW, "sotto_webview.py"),
        "--dump-dom", "--dump-dom-wait", "10",
        "--no-hotkey", "--no-hot-reload",
        "--exit-after", "45",
        "--log", log]

print("argv=%r" % (argv,))
p = subprocess.Popen(argv, cwd=WEBVIEW, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=CREATE_NO_WINDOW)
deadline = time.time() + 120
rc = None
while time.time() < deadline:
    rc = p.poll()
    if rc is not None:
        break
    time.sleep(1)
if rc is None:
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("TIMEOUT: the shell did not exit within 120 s")
print("shell rc=%s after %.1fs" % (rc, 120 - (deadline - time.time())))

text = ""
for path in (log,):
    if os.path.exists(path):
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()

gates = [l for l in text.splitlines() if "BRIDGE_GATE" in l]
for g in gates[-4:]:
    print(g.strip()[:300])
if not gates:
    print("NO BRIDGE_GATE LINE — the shell did not reach its own panel gate")

# The DOM dump, if the shell wrote one, is checked for the three things this lane
# changed: the HUD gone, no advertised shortcut, and the four controls on top.
domfile = None
for cand in os.listdir(os.path.join(ROOT, "_main")):
    if cand.startswith("dump") and cand.endswith(".html"):
        domfile = os.path.join(ROOT, "_main", cand)
if domfile:
    with open(domfile, encoding="utf-8", errors="replace") as fh:
        d = fh.read()
    print("DOM dump: %s (%d bytes)" % (os.path.basename(domfile), len(d)))
    print("  id=\"hud\" present            : %s" % ('id="hud"' in d))
    print("  'Alt+C' anywhere             : %s" % (bool(re.search(r"alt\s*\+\s*c", d, re.I))))
    print("  panel-pause-button present   : %s" % ('id="panel-pause-button"' in d))
    print("  caption-list present         : %s" % ('id="caption-list"' in d))
    print("  caption-formulation.js loaded: %s" % ('caption-formulation.js' in d))
print("GATE: %s" % ("GREEN" if any("BRIDGE_GATE=GREEN" in g for g in gates) else "RED"))
