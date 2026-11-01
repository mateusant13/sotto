"""THE PROBE: the panel's first frame, read by the RENDERER, not by PrintWindow.

THE INSTRUMENT, and why it is not the census's. The census's instrument asks
the WINDOW to paint itself: `PrintWindow(PW_RENDERFULLCONTENT)` -> `WM_PRINT`
-> the target's own wndproc -> a BGRA buffer the census classifies. This probe
asks the WEBVIEW2 RENDERER for its own composited output, over the Chrome
DevTools Protocol (`Page.captureScreenshot` / `Page.startScreencast`). Those
pixels are produced by the WebView2's own compositor: no `PrintWindow`, no
`WM_PRINT`, no DWM redirection surface, no `GetDIBits` of a window DC. The
classifier is different too -- distinct colours plus per-channel standard
deviation over the DECODED image, not a strided BGRA sample.

THE SUBJECT (mode=app). A PRIVATE instance of the REAL shell
(`app/webview/sotto_webview.py`), built as a variant copy in the shell's own
directory (the shell imports its siblings by module name, so the copy has to
live next to the original), with the census's own driver injected: it calls
`show_strip` / `show_side` -- the PRODUCTION show path -- three times, and
nothing else. `--mutex-name <private>` and `--no-worker` keep the owner's
live instance untouched.

THE CONTROLS (mode=control-blank / control-content). The SAME reader and the
SAME classifier over a WebView2 page this script owns: one flat colour versus
one with content. An instrument that cannot report "blank" is not an
instrument, so these run FIRST and their result is in the reading.

THE CDP PORT. Measured on this box, at the OWNER's integrity:
  COREWEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS -> the port does NOT open
  webview.settings['REMOTE_DEBUGGING_PORT'] -> the port DOES open
So the variant sets pywebview's own setting, in the COPY only. The product's
code is never edited.

THE SAFETY. Every window this script makes is at x=-10000 with
`SW_SHOWNOACTIVATE`; the app's own `_warm_paint` parks the instance off the
virtual screen before the show; the CDP port is bound to 127.0.0.1.

RUN:  python _main/_falsify/cdp-probe-app.py --mode app --tag cured --port 9333
"""
from __future__ import annotations

import argparse
import base64
import datetime
import io
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
VARIANT_DIR = os.path.join(ROOT, 'app', 'webview')
TMP = r'I:\cc-tmp'

_SELFTEST_ANCHOR = 'self.run_selftest()'
_MAIN_ANCHOR = "if __name__ == '__main__':"
_DRIVER_CALL = 'paint_census_drive(self)'

_CDP_ANCHOR = "    webview.start(icon=SOTTO_ICON)"
_CDP_REPLACEMENT = (
    "    try:\n"
    "        import webview as _wv\n"
    "        _wv.settings['REMOTE_DEBUGGING_PORT'] = int(\n"
    "            os.environ.get('FALSIFY_CDP_PORT', '9333'))\n"
    "        log('CDP_PROBE port=%s armed' %\n"
    "            os.environ.get('FALSIFY_CDP_PORT', '?'))\n"
    "    except Exception as exc:  # noqa: BLE001\n"
    "        log('CDP_PROBE arm FAILED error=%r' % (exc,))\n"
    "    webview.start(icon=SOTTO_ICON)")

DRIVER_SRC = '''
def paint_census_drive(shell):
    """THE DRIVER: the production show path, three times, and out.

    The SAME calls the census's driver makes -- `set_panel_surface` (the
    document half) then `show_strip` / `show_side` (the window half) --
    because the question is about THAT path and not about a proxy for it.
    """
    try:
        time.sleep(1.0)
        shell.hide_panel('census-baseline')
        steps = (('strip', 'census-1'), ('panel', 'census-2'),
                 ('strip', 'census-3'))
        for surface, reason in steps:
            time.sleep(0.7)
            log('CENSUS_DRIVER show=%s surface=%s' % (reason, surface))
            try:
                shell.set_panel_surface(surface, reason + '-warm')
                log('CENSUS_DRIVER warmed surface=%s' % (surface,))
                time.sleep(0.6)
            except Exception as exc:  # noqa: BLE001
                log('CENSUS_DRIVER warm FAILED error=%r' % (exc,))
            if surface == 'strip':
                shell.show_strip(reason)
            else:
                shell.show_side(reason)
            time.sleep(1.6)
            log('CENSUS_DRIVER hide=%s' % reason)
            shell.hide_panel('census-hide-' + reason)
        log('CENSUS_DRIVER done shows=%d' % len(steps))
    except Exception as exc:  # noqa: BLE001
        log('CENSUS_DRIVER FAILED error=%r' % (exc,))
    finally:
        shell.request_exit(0, reason='census-driver')

'''

#: The control pages: the SAME WebView2 stack, one flat colour versus content.
CONTROL_PAGES = {
    'control-blank': (
        "<html><body style='margin:0;background:#202020;width:100%;height:100%'>"
        "<div style='width:100%;height:100%;background:#202020'></div></body></html>"),
    'control-content': (
        "<html><body style='margin:0;background:#202020'>"
        "<div style='width:200px;height:90px;background:#e0e0e0'></div>"
        "<div style='width:120px;height:60px;background:#3060a0'></div>"
        "<div style='width:60px;height:30px;background:#20a050'></div>"
        "<script>window.__ready=1;</script></body></html>"),
}


_PROBE_LOG = None


def say(*a):
    line = ' '.join(str(x) for x in a)
    try:
        print(line, flush=True)
    except Exception:
        pass
    if _PROBE_LOG:
        try:
            with open(_PROBE_LOG, 'a', encoding='utf-8') as fh:
                fh.write(line + '\n')
        except OSError:
            pass


def read_text(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def build_variant(tag, uncured_rev='41e7bc6^'):
    if tag == 'cured':
        text = read_text(SHELL)
    else:
        proc = subprocess.run(['git', '-C', ROOT, 'show',
                               '%s:app/webview/sotto_webview.py' % uncured_rev],
                              capture_output=True, text=True)
        if proc.returncode != 0 or not proc.stdout:
            raise SystemExit('variant %s: git show failed: %s'
                             % (tag, (proc.stderr or '').strip()[:200]))
        if 'arm_paint_ack' in proc.stdout:
            raise SystemExit('variant %s: already has the cure -- refusing' % tag)
        text = proc.stdout
    for name, anchor in (('selftest', _SELFTEST_ANCHOR),
                         ('main', _MAIN_ANCHOR),
                         ('cdp', _CDP_ANCHOR)):
        if text.count(anchor) != 1:
            raise SystemExit('variant %s: %s anchor count=%d -- refusing'
                             % (tag, name, text.count(anchor)))
    out = text.replace(_SELFTEST_ANCHOR, _DRIVER_CALL, 1)
    out = out.replace(_MAIN_ANCHOR, DRIVER_SRC + _MAIN_ANCHOR, 1)
    out = out.replace(_CDP_ANCHOR, _CDP_REPLACEMENT, 1)
    path = os.path.join(VARIANT_DIR, '_falsify-cdp-%s-sotto_webview.py' % tag)
    with open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(out)
    built = read_text(path)
    if _DRIVER_CALL not in built or 'def paint_census_drive' not in built \
            or 'REMOTE_DEBUGGING_PORT' not in built:
        os.remove(path)
        raise SystemExit('variant %s: the driver/CDP arm did not land -- refusing'
                         % tag)
    return path


def classify_png(data):
    """Distinct colours + per-channel std over the DECODED image.

    NOT the census's rule (that one is a strided BGRA sample with
    BLANK_STD_MAX=2.5). A blank frame has almost no distinct colours; a
    content frame has many. Both numbers are reported so a reader can apply
    either threshold.
    """
    from PIL import Image
    img = Image.open(io.BytesIO(data)).convert('RGB')
    colours = img.getcolors(maxcolors=1 << 20)
    distinct = len(colours) if colours is not None else '>1M'
    px = list(img.getdata())
    if not px:
        return {'distinct': 0, 'rgb_std': 0.0, 'size': list(img.size),
                'empty': True}
    step = max(1, len(px) // 4096)
    sample = px[::step]
    n = len(sample)
    means = [sum(c[i] for c in sample) / n for i in range(3)]
    stds = [(sum((c[i] - means[i]) ** 2 for c in sample) / n) ** 0.5
            for i in range(3)]
    std = (stds[0] ** 2 + stds[1] ** 2 + stds[2] ** 2) ** 0.5
    return {'distinct': distinct, 'rgb_std': round(std, 3),
            'per_channel': [round(s, 3) for s in stds],
            'mean': [round(m, 1) for m in means],
            'size': list(img.size), 'empty': False}


class Renderer:
    """A CDP session on the WebView2's page."""

    def __init__(self, port):
        self.port = port
        self.ws = None
        self.cid = 0

    def attach(self, timeout=50):
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        'http://127.0.0.1:%d/json/list' % self.port,
                        timeout=5) as resp:
                    targets = json.loads(resp.read().decode('utf-8', 'replace'))
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(0.4)
                continue
            for t in targets:
                if t.get('type') == 'page' and t.get('webSocketDebuggerUrl'):
                    import websocket
                    self.ws = websocket.create_connection(
                        t['webSocketDebuggerUrl'], timeout=30)
                    return True
            last = 'no page target yet'
            time.sleep(0.4)
        self.last_error = last
        return False

    def cmd(self, method, params=None, timeout=20):
        self.cid += 1
        mine = self.cid
        self.ws.send(json.dumps({'id': mine, 'method': method,
                                 'params': params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = json.loads(self.ws.recv())
            except Exception:
                continue
            if msg.get('id') == mine:
                return msg
        return None

    def shot(self):
        res = self.cmd('Page.captureScreenshot', {'format': 'png'})
        if not res or 'result' not in res:
            return None
        return base64.b64decode(res['result']['data'])

    def eval(self, expr):
        res = self.cmd('Runtime.evaluate',
                       {'expression': expr, 'returnByValue': True})
        try:
            return res['result']['result'].get('value')
        except Exception:
            return None


#: The page's own state, read at the same instant as the pixels: is the panel
#: DOCUMENT loaded, and which surface is it showing?
STATE_JS = (
    "JSON.stringify({url: location.href.slice(0,120),"
    "ready: document.readyState,"
    "surface: (document.documentElement.getAttribute('data-surface')||''),"
    "float: (document.documentElement.getAttribute('data-float')||''),"
    "bodyKids: document.body ? document.body.children.length : -1,"
    "vis: document.visibilityState})")


def shoot_loop(renderer, stop_at, out, jsonl=None):
    """Capture the renderer's own output as fast as it answers."""
    n = 0
    misses = 0
    while time.time() < stop_at:
        t0 = time.time()
        png = renderer.shot()
        t1 = time.time()
        if png is None:
            misses += 1
            if misses in (1, 5, 20):
                say('SHOT MISS #%d at t=%.2f' % (misses, t0))
            time.sleep(0.05)
            continue
        try:
            c = classify_png(png)
        except Exception as exc:  # noqa: BLE001
            c = {'error': repr(exc)}
        c['i'] = n
        c['t0'] = round(t0, 6)
        c['t1'] = round(t1, 6)
        out.append(c)
        if jsonl:
            try:
                with open(jsonl, 'a', encoding='utf-8') as fh:
                    fh.write(json.dumps(c, default=str) + '\n')
            except OSError:
                pass
        n += 1
    return out


def parse_log_times(log_path, tz_offset_s):
    """PANEL_SHOWN / PANEL_HIDDEN lines -> epoch seconds."""
    text = read_text(log_path)
    out = []
    for line in text.splitlines():
        m = re.match(r'(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})'
                     r' sotto: (PANEL_SHOWN|PANEL_HIDDEN|PAINT_WARM)'
                     r'[^\n]*?reason=(\S+)', line)
        if not m:
            continue
        date, hh, mm, ss, ms, kind, reason = m.groups()
        try:
            dt = datetime.datetime.strptime('%s %s:%s:%s.%s'
                                             % (date, hh, mm, ss, ms),
                                             '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            continue
        epoch = dt.timestamp() + tz_offset_s
        out.append({'kind': kind, 'reason': reason, 'epoch': epoch,
                    'line': line[:200]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', default='app',
                    choices=('app', 'control-blank', 'control-content'))
    ap.add_argument('--tag', default='cured', choices=('cured', 'uncured'))
    ap.add_argument('--port', type=int, default=9333)
    ap.add_argument('--seconds', type=float, default=26.0)
    ap.add_argument('--settle', type=float, default=0.0)
    ap.add_argument('--out', default=os.path.join(TMP, '_falsify', 'cdp-probe.json'))
    ap.add_argument('--log', default=os.path.join(TMP, '_falsify', 'cdp-probe.log'))
    args = ap.parse_args()

    global _PROBE_LOG
    _PROBE_LOG = args.out + '.probe.log'
    try:
        os.remove(_PROBE_LOG)
    except OSError:
        pass
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    # The offset between the app log's local timestamps and epoch seconds.
    tz_offset_s = -time.timezone

    variant = None
    env = dict(os.environ)
    env['FALSIFY_CDP_PORT'] = str(args.port)
    env['PYWEBVIEW_LOG'] = 'ERROR'
    env.pop('COREWEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS', None)

    log_path = args.log
    out_path = args.out + '.stdout'
    for p in (log_path, out_path):
        try:
            os.remove(p)
        except OSError:
            pass
    out = open(out_path, 'w', encoding='utf-8', errors='replace')

    if args.mode == 'app':
        variant = build_variant(args.tag)
        say('variant=%s' % variant)
        cmd = [sys.executable, variant, '--selftest', '--no-worker',
               '--mutex-name', 'SottoFalsifyCdpProbe-%s' % args.tag,
               '--hotkey', 'Alt+Shift+C',
               '--exit-after', '%g' % float(args.seconds),
               '--log', log_path]
    else:
        html = CONTROL_PAGES[args.mode]
        child = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '_cdp-control-child.py')
        with open(child, 'w', encoding='utf-8') as fh:
            fh.write(
                "import os, webview\n"
                "webview.settings['REMOTE_DEBUGGING_PORT'] = int("
                "os.environ.get('FALSIFY_CDP_PORT','9333'))\n"
                "HTML = %r\n"
                "w = webview.create_window('ctl', html=HTML, width=380, height=140,\n"
                "                          x=-10000, y=-10000, frameless=True, hidden=True)\n"
                "webview.start()\n" % html)
        cmd = [sys.executable, child]

    try:
        proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT,
                                cwd=ROOT, env=env, creationflags=0x08000000)
    except Exception as exc:
        say('SPAWN FAILED %r' % (exc,))
        raise
    say('pid=%d mode=%s tag=%s' % (proc.pid, args.mode, args.tag))

    say('ATTACHING port=%d' % args.port)
    renderer = Renderer(args.port)
    attached = renderer.attach(timeout=50)
    say('ATTACHED=%s err=%s' % (attached, getattr(renderer, 'last_error', None)))
    reading = {'mode': args.mode, 'tag': args.tag, 'attached': attached,
               'port': args.port, 'pid': proc.pid, 'tz_offset_s': tz_offset_s}
    if attached:
        say('PAGE_ENABLE %s' % json.dumps(renderer.cmd('Page.enable'))[:120])
        # The page may still be LOADING when the port opens: a screenshot of a
        # page mid-load does not answer. Settle, then read the page's own
        # state so "the renderer is not ready" is a fact, not a guess.
        if args.settle:
            time.sleep(args.settle)
        say('SETTLE state=%s' % json.dumps(renderer.eval(STATE_JS))[:300])
        shots = []
        stop_at = time.time() + args.seconds
        jsonl = args.out + '.frames.jsonl'
        try:
            os.remove(jsonl)
        except OSError:
            pass
        th = threading.Thread(target=shoot_loop,
                              args=(renderer, stop_at, shots, jsonl), daemon=True)
        th.start()
        th.join(timeout=args.seconds + 15)
        say('SHOTS=%d' % len(shots))
        reading['frame_count'] = len(shots)
        reading['frames'] = shots
        if args.mode == 'app':
            reading['state'] = renderer.eval(STATE_JS)
    try:
        proc.wait(timeout=20)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    out.close()
    if variant:
        try:
            os.remove(variant)
        except OSError:
            pass
    if args.mode == 'app':
        reading['log_events'] = parse_log_times(log_path, tz_offset_s)
        reading['log_path'] = log_path
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(reading, fh, indent=1, default=str)
    say('READING %s frames=%s' % (args.out, reading.get('frame_count')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
