"""Is the stall the SEEK or the BUFFER? Three arms on the same live page.

A1 seek to 20 s -- inside the buffer already held ([0, 23.4]).
A2 seek to 60 s -- beyond it.
A3 no seek, just play 40 s -- does the buffer grow on its own?

Each arm prints currentTime, readyState, buffered end, networkState and
video.error, so the difference between "cannot fetch after seek" and "cannot
fetch at all" is a number, not a guess.
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

PORT = 9462
VID = sys.argv[1] if len(sys.argv) > 1 else "rS4VMlwf2qM"
STATE = """(function(){var v=document.querySelector('video');
  var b=v.buffered.length?[v.buffered.start(v.buffered.length-1),v.buffered.end(v.buffered.length-1)]:null;
  return {t:+v.currentTime.toFixed(2), rs:v.readyState, ns:v.networkState,
          paused:v.paused, buf:b, err:v.error?v.error.code+':'+v.error.message:null,
          bps:+(v.getVideoPlaybackQuality?v.getVideoPlaybackQuality().totalVideoFrames:0)};})()"""


def main():
    exe = next(b for b in BROWSERS if os.path.exists(b))
    prof = tempfile.mkdtemp(prefix="bufprobe-")
    p = subprocess.Popen([exe, "--remote-debugging-port=%d" % PORT, "--headless=new",
                          "--disable-gpu", "--mute-audio",
                          "--autoplay-policy=no-user-gesture-required",
                          "--no-first-run", "--no-default-browser-check",
                          "--user-data-dir=" + prof, "about:blank"])
    try:
        w, send, ev = cdp_connect(PORT)
        send("Page.enable"); send("Runtime.enable")
        send("Page.navigate", {"url": "https://www.youtube.com/watch?v=%s" % VID})
        for _ in range(60):
            time.sleep(0.5)
            if ev("(function(){var v=document.querySelector('video');return v&&v.readyState>=2;})()"):
                break
        print("loaded:", json.dumps(ev(STATE)))

        print("\n-- A3 first (no seek): does the buffer grow by itself? --")
        for i in range(8):
            time.sleep(2.0)
            print("   %2ds %s" % ((i + 1) * 2, json.dumps(ev(STATE))))

        print("\n-- A1: seek to 20 s (inside the buffer held) --")
        ev("(function(){document.querySelector('video').currentTime=20;return 1;})()")
        for i in range(5):
            time.sleep(1.0)
            print("   %ds %s" % (i + 1, json.dumps(ev(STATE))))

        print("\n-- A2: seek to 60 s (beyond the buffer) --")
        ev("(function(){document.querySelector('video').currentTime=60;return 1;})()")
        for i in range(10):
            time.sleep(1.0)
            print("   %ds %s" % (i + 1, json.dumps(ev(STATE))))

        print("\n-- A2b: after the stall, force load/play --")
        ev("(function(){var v=document.querySelector('video');v.load?v.load():0;v.play();return 1;})()")
        for i in range(5):
            time.sleep(1.0)
            print("   %ds %s" % (i + 1, json.dumps(ev(STATE))))

        print("\n-- A4: seekTo via player API, then read --")
        ez = ev("""(function(){var pl=document.getElementById('movie_player');
                if(!pl||!pl.seekTo)return 'no-api';pl.seekTo(300,true);return 'called';})()""")
        print("   seekTo:", ez)
        for i in range(8):
            time.sleep(1.0)
            print("   %ds %s" % (i + 1, json.dumps(ev(STATE))))
        w.close()
    finally:
        try:
            p.terminate(); p.wait(timeout=10)
        except Exception:
            pass
        shutil.rmtree(prof, ignore_errors=True)


main()
