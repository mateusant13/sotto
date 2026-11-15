"""Does the post-seek fetch stall come from headless backgrounding?

Compares four browser flag sets on the same seek-to-60:
 A  baseline headless
 B  + --disable-background-timer-throttling --disable-renderer-backgrounding
    --disable-backgrounding-occluded-windows --disable-features=...
 C  B + windowed-but-offscreen (no headless), muted
 D  B + `--autoplay-policy` + a 2 s wait after seek, then play

A stall that survives all four is not throttling: it is the page refusing to
fetch in this environment, and the lab must then take its audio from a source
that can actually seek.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import BROWSERS, cdp_connect  # noqa: E402

VID = sys.argv[1] if len(sys.argv) > 1 else "rS4VMlwf2qM"
STATE = """(function(){var v=document.querySelector('video');
  var b=v.buffered.length?[+v.buffered.start(v.buffered.length-1).toFixed(1),+v.buffered.end(v.buffered.length-1).toFixed(1)]:null;
  return {t:+v.currentTime.toFixed(2), rs:v.readyState, ns:v.networkState, buf:b};})()"""

THROTTLE = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows", "--disable-ipc-flooding-protection",
            "--disable-features=CalculateNativeWinOcclusion,IntensiveWakeUpThrottling"]


def arm(tag, extra, headless=True, port=9470, target=60):
    exe = next(b for b in BROWSERS if os.path.exists(b))
    prof = tempfile.mkdtemp(prefix="arm-%s-" % tag)
    args = [exe, "--remote-debugging-port=%d" % port,
            "--autoplay-policy=no-user-gesture-required",
            "--no-first-run", "--no-default-browser-check", "--mute-audio",
            "--user-data-dir=" + prof] + list(extra)
    if headless:
        args += ["--headless=new", "--disable-gpu"]
    else:
        args += ["--window-position=-4000,-4000", "--window-size=800,500"]
    p = subprocess.Popen(args + ["about:blank"])
    try:
        w, send, ev = cdp_connect(port)
        send("Page.enable"); send("Runtime.enable")
        send("Page.navigate", {"url": "https://www.youtube.com/watch?v=%s" % VID})
        for _ in range(60):
            time.sleep(0.5)
            if ev("(function(){var v=document.querySelector('video');return v&&v.readyState>=2;})()"):
                break
        time.sleep(6)
        before = ev(STATE)
        ev("(function(){document.querySelector('video').currentTime=%d;return 1;})()" % target)
        rows = []
        for _ in range(10):
            time.sleep(1.0)
            rows.append(ev(STATE))
        ok = any((r.get("rs") or 0) >= 2 for r in rows)
        print("%-6s headless=%-5s seek->%d  before=%s  after10s=%s  RECOVERED=%s"
              % (tag, headless, target, json.dumps(before), json.dumps(rows[-1]), ok))
        w.close()
        return ok
    finally:
        try:
            p.terminate(); p.wait(timeout=10)
        except Exception:
            pass
        shutil.rmtree(prof, ignore_errors=True)


print("A baseline headless       :", arm("A", [], port=9470))
print("B + throttle flags        :", arm("B", THROTTLE, port=9471))
print("C headed offscreen         :", arm("C", THROTTLE, headless=False, port=9472))
print("D + wait, seek then play   :", arm("D", THROTTLE, port=9473))
