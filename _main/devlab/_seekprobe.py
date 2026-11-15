"""Why does `video.currentTime = 60` not take on this YouTube page?

Measures the seek primitive itself: seekable ranges, the playhead before and
after a programmatic seek, whether `seeked` fires, and whether an ad/duration
state explains it. Headless, silent (nothing is connected to any endpoint).
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

PORT = 9461
VID = sys.argv[1] if len(sys.argv) > 1 else "rS4VMlwf2qM"


def main():
    exe = next(b for b in BROWSERS if os.path.exists(b))
    prof = tempfile.mkdtemp(prefix="seekprobe-")
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
        print("state:", json.dumps(ev("""(function(){var v=document.querySelector('video');
          return {rs:v.readyState,dur:v.duration,t:v.currentTime,paused:v.paused,
                  nSeekable:v.seekable.length,
                  seekable:(function(){var a=[];for(var i=0;i<v.seekable.length;i++)a.push([v.seekable.start(i),v.seekable.end(i)]);return a;})(),
                  buffered:(function(){var a=[];for(var i=0;i<v.buffered.length;i++)a.push([v.buffered.start(i),v.buffered.end(i)]);return a;})()};})()""")))
        print("ad showing:", ev("!!document.querySelector('.ad-showing')"))
        print("--- now seek to 60 and watch ---")
        ev("""(()=>{window.__seeks=[];var v=document.querySelector('video');
                v.addEventListener('seeked',()=>window.__seeks.push(['seeked',v.currentTime]));
                v.addEventListener('seeking',()=>window.__seeks.push(['seeking',v.currentTime]));
                v.currentTime=60; return v.currentTime;})()""")
        for i in range(10):
            time.sleep(1.0)
            print("  t=%5.2f paused=%s rs=%s events=%s" % (
                ev("document.querySelector('video').currentTime"),
                ev("document.querySelector('video').paused"),
                ev("document.querySelector('video').readyState"),
                json.dumps(ev("window.__seeks"))[-120:]))
        print("--- variant: seek by setting then explicitly play ---")
        ev("""(()=>{var v=document.querySelector('video');v.currentTime=60;v.play();return 1;})()""")
        for i in range(6):
            time.sleep(1.0)
            print("  t=%5.2f paused=%s" % (ev("document.querySelector('video').currentTime"),
                                           ev("document.querySelector('video').paused")))
        print("--- variant: use YouTube player API ---")
        print("  has player:", ev("!!(document.getElementById('movie_player')||document.querySelector('#movie_player'))"))
        ev("""(()=>{var pl=document.getElementById('movie_player');
                if(pl&&pl.seekTo){pl.seekTo(120,true);return 'seekTo-called';}return 'no-player-api';})()""")
        for i in range(6):
            time.sleep(1.0)
            print("  t=%5.2f" % ev("document.querySelector('video').currentTime"))
        w.close()
    finally:
        try:
            p.terminate(); p.wait(timeout=10)
        except Exception:
            pass
        shutil.rmtree(prof, ignore_errors=True)


main()
