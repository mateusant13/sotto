#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Make the LANE'S OWN hidden Chrome play a YouTube video, or refuse by name.

No owner in the loop: never port 9222, never his profile, never his tab. The
only owner-free session source is a cookie jar the caller supplies:
  * Netscape ``cookies.txt`` (tab separated: domain, flag, path, secure,
    expiry, name, value), or
  * JSON, either a Playwright-style ``{"cookies": [...]}`` or a bare list of
    cookie objects.
Cookie VALUES are neither printed nor logged: only file paths and the NAMES
of the credential variables (SID / SAPISID) appear in the output.

MANUAL ONE-TIME LOGIN (by a human, in the lane profile, never the owner's):

    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" ^
      --user-data-dir=I:\\cc-tmp\\sotto-lane-chrome ^
      --no-first-run --no-default-browser-check ^
      https://accounts.google.com/ServiceLogin

Log in there once, export the resulting cookies to a Netscape or JSON jar,
then run this instrument with ``--cookies <that jar>``. This script deletes
only the exact throwaway profile directory it created itself; an existing
``--profile`` supplied by the caller is never deleted.

The verdict belongs to the player's own API: getPlayerResponse() status, the
<video> readyState/currentTime, and the caption-track list.

  py -3 _main/yt-lane-session.py --video TGOe1w8m5OU
  py -3 _main/yt-lane-session.py --cookies I:\\cc-tmp\\lane-cookies.json

Codes: 0 = playback witnessed; 1 = teardown defect; 2 = usage; 3 = CANNOT-MEASURE.
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import shutil
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, replace

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

def _hidden_launch():
    """`hidden-launch.py` tem hifen no nome: importa-se por CAMINHO."""
    path = os.path.join(HERE, 'hidden-launch.py')
    spec = importlib.util.spec_from_file_location('sotto_hidden_launch', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hidden_launch = _hidden_launch()
_freeze_spec = importlib.util.spec_from_file_location(
    'sotto_yt_live_freeze_drive', os.path.join(HERE, 'yt-live-freeze-drive.py'))
freeze = importlib.util.module_from_spec(_freeze_spec)
_freeze_spec.loader.exec_module(freeze)
_eval, _targets = freeze._eval, freeze._targets  # reuse, no second CDP client

import websocket  # noqa: E402

CHROME = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
PROFILE_PARENT = r'I:\cc-tmp'
PROFILE_PREFIX = 'sotto-lane-chrome'
DEFAULT_PORT = 9340
DEFAULT_VIDEO = 'TGOe1w8m5OU'
COOKIE_DOMAINS = ('youtube.com', 'google.com', 'googleusercontent.com',
                  'youtube-nocookie.com', 'googlevideo.com', 'doubleclick.net')

#: The same shape the browser probe returns and the oracle's fake player
#: returns. One reader owns the verdict: ``snapshot_from_player`` -> ``judge``.
PLAY_PROBE_JS = (
    "(()=>{var v=document.querySelector('video'),"
    "mp=document.getElementById('movie_player'),"
    "pr=(mp&&mp.getPlayerResponse)?mp.getPlayerResponse():null,"
    "ps=pr&&pr.playabilityStatus?pr.playabilityStatus:{},"
    "cc=pr&&pr.captions&&pr.captions.playerCaptionsTracklistRenderer,"
    "tracks=cc&&cc.captionTracks?cc.captionTracks:[],"
    "fmts=pr&&pr.streamingData&&pr.streamingData.adaptiveFormats?pr.streamingData.adaptiveFormats:[];"
    "return JSON.stringify({status:ps.status||null,reason:ps.reason||'',"
    "rs:v?v.readyState:0,t_ms:v?Math.round((v.currentTime||0)*1000):0,"
    "caps:tracks.length,fmts:fmts.length,"
    "vid:(new URLSearchParams(location.search)).get('v'),"
    "title:document.title})})()"
)


@dataclass(frozen=True)
class Snapshot:
    status: object = None
    ready_state: int = 0
    t0_ms: int = 0
    t1_ms: int = 0
    caption_tracks: int = 0
    formats: int = 0
    video_id: str = ''


@dataclass(frozen=True)
class Outcome:
    kind: str
    why: str = ''
    ready: int = 0
    played_ms: int = 0
    caption_tracks: int = 0
    delta_ms: int = 0
    detail: str = ''

    @property
    def rc(self) -> int:
        return 0 if self.kind == 'OK' else 3

    def line(self) -> str:
        if self.kind == 'OK':
            return ('LANE-YT OK readyState=%d already_played_ms=%d '
                    'caption_tracks=%d delta_ms=%d' %
                    (self.ready, self.played_ms, self.caption_tracks, self.delta_ms))
        extra = (' ' + self.detail) if self.detail else ''
        return 'LANE-YT CANNOT-MEASURE why=%s%s' % (self.why, extra)


def refuse(why, **detail):
    return Outcome('CANNOT-MEASURE', why=why,
                   detail=' '.join('%s=%s' % (k, detail[k]) for k in sorted(detail)))


def snapshot_from_player(player, t0_ms=None):
    """The single reader: a CDP dict or a fake player with getPlayerResponse()."""
    if isinstance(player, dict):
        status = player.get('status')
        ready = int(player.get('rs') or 0)
        now = int(player.get('t_ms') or 0)
        caps = int(player.get('caps') or 0)
        fmts = int(player.get('fmts') or 0)
        vid = str(player.get('vid') or '')
    else:
        pr = player.getPlayerResponse() or {}
        status = (pr.get('playabilityStatus') or {}).get('status')
        video = getattr(player, 'video', None)
        ready = int(getattr(video, 'readyState', 0) or 0)
        now = int(round(float(getattr(video, 'currentTime', 0) or 0) * 1000))
        cc = ((pr.get('captions') or {}).get('playerCaptionsTracklistRenderer') or {})
        caps = len(cc.get('captionTracks') or [])
        fmts = len(((pr.get('streamingData') or {}).get('adaptiveFormats') or []))
        vid = ''
    return Snapshot(status=status, ready_state=ready,
                    t0_ms=now if t0_ms is None else int(t0_ms), t1_ms=now,
                    caption_tracks=caps, formats=fmts, video_id=vid)


def judge(snapshot, threshold_ms=250):
    """Pure. readyState 0 and a static clock are never playback."""
    if not snapshot.status:
        return refuse('no-player')
    if snapshot.status == 'LOGIN_REQUIRED':
        return refuse('login-required', status=snapshot.status)
    if snapshot.status != 'OK':
        return refuse('cdn-error', status=snapshot.status)
    if snapshot.ready_state < 2:
        return refuse('no-media', readyState=snapshot.ready_state)
    delta = int(snapshot.t1_ms) - int(snapshot.t0_ms)
    if delta < int(threshold_ms):
        return refuse('not-playing', delta_ms=delta, readyState=snapshot.ready_state)
    if snapshot.caption_tracks < 1:
        return refuse('no-caption-track', caption_tracks=snapshot.caption_tracks)
    return Outcome('OK', ready=snapshot.ready_state, played_ms=int(snapshot.t0_ms),
                   caption_tracks=snapshot.caption_tracks, delta_ms=delta)


def with_session_context(outcome, has_session):
    """A signed-out LOGIN_REQUIRED is named no-session, not a CDN failure."""
    if not has_session and outcome.why == 'login-required':
        return replace(outcome, why='no-session')
    return outcome


def parse_cookies(path):
    """Return (cdp cookies, credential NAMES, format). Never returns a log line."""
    with io.open(path, 'r', encoding='utf-8-sig', errors='replace') as fh:
        text = fh.read()
    rows = []
    if text.lstrip().startswith(('[', '{')):
        obj = json.loads(text)
        rows = (obj.get('cookies') if isinstance(obj, dict) else obj) or []
        fmt = 'json'
    else:
        for line in text.splitlines():
            if not line or line.startswith('#'):
                continue
            parts = line.rstrip('\r\n').split('\t')
            if len(parts) < 7:
                continue
            domain, _flag, cpath, secure, expiry, name, value = parts[:7]
            rows.append({'domain': domain, 'path': cpath,
                         'secure': secure.strip().lower() in ('true', '1', 'yes'),
                         'expiry': expiry, 'name': name, 'value': value})
        fmt = 'netscape'
    cookies, names = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get('name') or '').strip()
        if not name:
            continue
        names.add(name)
        domain = str(row.get('domain') or '').lstrip('.').lower()
        if domain and not any(domain == d or domain.endswith('.' + d)
                              for d in COOKIE_DOMAINS):
            continue
        cookie = {'name': name, 'value': str(row.get('value') or ''),
                  'domain': ('.' + domain) if domain else None,
                  'path': str(row.get('path') or '/') or '/',
                  'secure': bool(row.get('secure', False)),
                  'httpOnly': bool(row.get('httpOnly', False))}
        expiry = row.get('expirationDate', row.get('expiry'))
        try:
            expiry = float(expiry)
            if expiry > 0:
                cookie['expirationDate'] = expiry
        except (TypeError, ValueError):
            pass
        cookies.append(cookie)
    return cookies, names, fmt


def port_answers(port, timeout=0.8):
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/json/version' % port,
                                    timeout=timeout) as fh:
            json.load(fh)
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False


def wait_port(port, want, timeout):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_answers(port) == want:
            return True
        time.sleep(0.25)
    return port_answers(port) == want


def cdp(ws, method, params, mid):
    """A CDP DOMAIN call (the imported _eval is a Runtime.evaluate call)."""
    ws.send(json.dumps({'id': mid, 'method': method, 'params': params}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == mid:
            if 'error' in msg:
                raise RuntimeError('%s: %s' % (method, msg['error'].get('message')))
            return msg.get('result', {})


def connect_page(port):
    tabs = [t for t in _targets(port) if t.get('type') == 'page']
    if not tabs:
        return None, None
    tab = tabs[0]
    ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=20)
    return ws, tab


def profile_pids(profile):
    """Only processes whose OWN command line contains this exact profile path."""
    import psutil
    out = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info.get('cmdline') or [])
            name = (proc.info.get('name') or '').lower()
        except psutil.Error:
            continue
        if 'chrome' in name and profile in cmdline:
            out.append(proc)
    return out


def audit_teardown(pid, survivors):
    """Pure: a teardown that leaves the launched pid is a defect, never PASS."""
    leftover = sorted(int(p) for p in survivors)
    return (not leftover), leftover


def teardown(proc, profile, created, err_path):
    pid = proc.pid
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass
    exited = proc.poll() is not None
    # Chrome children carry the SAME exact --user-data-dir. Kill by that exact
    # path, never by a generic chrome.exe name filter, never a wildcard.
    for child in profile_pids(profile):
        try:
            child.kill()
            child.wait(timeout=3)
        except Exception:
            pass
    survivors = [p.info['pid'] for p in profile_pids(profile)]
    removed = False
    if created:
        shutil.rmtree(profile, ignore_errors=True)
        removed = not os.path.exists(profile)
    if not survivors and os.path.isfile(err_path):
        try:
            os.remove(err_path)
        except OSError:
            pass
    return exited, survivors, removed


def launch(profile, port, err_path):
    if not os.path.isfile(CHROME):
        return None
    cmd = [CHROME, '--headless=new', '--user-data-dir=' + profile,
           '--remote-debugging-port=%d' % port,
           '--remote-debugging-address=127.0.0.1', '--mute-audio',
           '--autoplay-policy=no-user-gesture-required', '--no-first-run',
           '--no-default-browser-check', '--disable-background-timer-throttling',
           '--disable-renderer-backgrounding',
           '--disable-backgrounding-occluded-windows', '--window-size=1280,720',
           'about:blank']
    err = open(err_path, 'wb')
    try:
        proc = hidden_launch.popen(
            cmd, stdout=err, stderr=err,
            creationflags=hidden_launch.CREATE_NO_WINDOW,
            startupinfo=hidden_launch._startupinfo())
    finally:
        err.close()
    return proc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--video', default=DEFAULT_VIDEO)
    ap.add_argument('--cookies', help='Netscape cookies.txt or JSON storage state')
    ap.add_argument('--port', type=int, default=DEFAULT_PORT)
    ap.add_argument('--profile', help='exact lane profile dir; never the owner\'s')
    ap.add_argument('--window', type=float, default=3.0,
                    help='seconds between the two currentTime samples')
    ap.add_argument('--threshold-ms', type=int, default=250)
    args = ap.parse_args(argv)
    if args.window <= 0 or args.threshold_ms <= 0:
        print('LANE-YT usage error: --window and --threshold-ms must be > 0')
        return 2

    port = args.port
    if port in (9222,):
        print('LANE-YT CANNOT-MEASURE why=owner-port-refused port=%d' % port)
        return 3
    if port_answers(port):
        print('LANE-YT CANNOT-MEASURE why=port-busy port=%d (nothing launched)' % port)
        return 3

    profile = args.profile or os.path.join(
        PROFILE_PARENT, '%s-%d' % (PROFILE_PREFIX, os.getpid()))
    created = not os.path.exists(profile)
    if created:
        try:
            os.makedirs(profile, exist_ok=False)
        except OSError as exc:
            print('LANE-YT CANNOT-MEASURE why=profile-error path=%s errno=%s'
                  % (profile, type(exc).__name__))
            return 3
    err_path = os.path.join(HERE, '_lane-session-chrome-%d.err' % os.getpid())
    print('LANE-YT profile=%s port=%d' % (profile, port))

    proc = launch(profile, port, err_path)
    if proc is None:
        print('LANE-YT CANNOT-MEASURE why=browser-missing path=%s' % CHROME)
        if created:
            shutil.rmtree(profile, ignore_errors=True)
        return 3

    rc, outcome = 3, None
    try:
        if not wait_port(port, True, 20.0):
            print('LANE-YT CANNOT-MEASURE why=browser-launch-failed stderr=%s'
                  % err_path)
        else:
            ws, _tab = None, None
            for _attempt in range(10):
                ws, _tab = connect_page(port)
                if ws is not None:
                    break
                time.sleep(0.5)
            if ws is None:
                print('LANE-YT CANNOT-MEASURE why=no-player (no page target)')
            else:
                try:
                    cdp(ws, 'Network.enable', {}, 1)
                    names = set()
                    fmt, count = 'none', 0
                    cookies = []
                    if args.cookies:
                        try:
                            cookies, names, fmt = parse_cookies(args.cookies)
                        except (OSError, ValueError, TypeError) as exc:
                            print('LANE-YT CANNOT-MEASURE why=cookie-file-invalid '
                                  'path=%s error=%s' % (args.cookies,
                                                        type(exc).__name__))
                            ws.close()
                            return 3
                        count = len(cookies)
                        cdp(ws, 'Network.setCookies', {'cookies': cookies}, 2)
                    stored = cdp(ws, 'Network.getAllCookies', {}, 3).get('cookies') or []
                    names.update(str(c.get('name') or '') for c in stored)
                    has_session = 'SID' in names or 'SAPISID' in names
                    print('LANE-YT session cookie_file=%s format=%s cookies=%d '
                          'SID=%s SAPISID=%s' %
                          (args.cookies or 'none', fmt, count,
                           'present' if 'SID' in names else 'absent',
                           'present' if 'SAPISID' in names else 'absent'))
                    url = 'https://www.youtube.com/watch?v=%s' % args.video
                    cdp(ws, 'Page.navigate', {'url': url}, 4)
                    deadline = time.time() + 30.0
                    title = ''
                    while time.time() < deadline:
                        title = str(_eval(ws, 'document.title', 5) or '')
                        if title:
                            break
                        time.sleep(0.5)
                    first = None
                    deadline = time.time() + 25.0
                    while time.time() < deadline:
                        first = json.loads(_eval(ws, PLAY_PROBE_JS, 6) or '{}')
                        if first.get('status'):
                            break
                        time.sleep(0.5)
                    time.sleep(args.window)
                    second = json.loads(_eval(ws, PLAY_PROBE_JS, 7) or '{}')
                    snap = snapshot_from_player(second, t0_ms=(first or {}).get('t_ms'))
                    print('LANE-YT player status=%s readyState=%s caption_tracks=%s '
                          'formats=%s video=%s title=%s' %
                          (snap.status, snap.ready_state, snap.caption_tracks,
                           snap.formats, snap.video_id, str(title)[:60]))
                    outcome = with_session_context(
                        judge(snap, args.threshold_ms), has_session)
                    print(outcome.line())
                    rc = outcome.rc
                finally:
                    ws.close()
    except Exception as exc:  # a refusal is still a refusal, never a crash
        print('LANE-YT CANNOT-MEASURE why=internal error=%s' % type(exc).__name__)
        rc = 3
    finally:
        exited, survivors, removed = teardown(proc, profile, created, err_path)
        clean, leftover = audit_teardown(proc.pid, survivors)
        print('LANE-YT teardown pid=%d exited=%d lane_chrome_left=%d '
              'profile_removed=%d profile=%s' %
              (proc.pid, 1 if exited else 0, len(survivors),
               1 if removed else 0, profile))
        if not clean or not exited or (created and not removed):
            print('LANE-YT FAIL why=teardown-leak survivors=%s'
                  % ','.join(str(x) for x in leftover))
            rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main())
