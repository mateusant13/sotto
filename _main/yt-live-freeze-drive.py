#!/usr/bin/env python
"""Drive the REAL YouTube player through CDP and demand the product's own receipts.

Uma lane nao encena a app na tela do dono (AGENTS.md, `SOTTO_NEVER_ON_OWNER_SCREEN`),
logo nao ha clique humano: o que este instrumento faz e' a accao que o produto mede
-- `pauseVideo`/`playVideo`/`seekTo` no player verdadeiro -- e depois exige que o
SHELL a testemunhe no log dele. A accao e' real; o veredicto e' do produto.

  py -3 _main/yt-live-freeze-drive.py                     # plano completo (~4 min)
  py -3 _main/yt-live-freeze-drive.py --fast              # mesmo plano, esperas a 1/4
  py -3 _main/yt-live-freeze-drive.py --plan pause-only   # um passo, para depurar
  py -3 _main/yt-live-freeze-drive.py --selftest          # juiz puro, sem browser

Recusa por nome (rc 3) quando nao pode medir: nenhuma aba `/watch`, nenhum video
tocando no arranque (o player pausado nao produz evento) ou nenhum `t=` no log.

Codes: 0 = todos os passos testemunhados; 1 = um passo ficou sem recibo;
2 = erro de uso; 3 = CANNOT-MEASURE.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
LOG_DEFAULT = os.path.join(HERE, 'webview-run.log')

#: A ESCADA. Cada passo diz o que PEDE ao player e a linha que o shell tem de
#: escrever depois -- a accao sem recibo e' o defeito que este instrumento procura.
#: (espera_s, accao, parametro, rotulo, padrao_do_recibo)
PLAN = (
    (0.0, 'play', None, 'PLAY', r'YOUTUBE_POLL_PACED paused=False'),
    (18.0, 'pause', 2.5, 'PAUSE-2.5S', r'YOUTUBE_PAUSE_(PROVEN|UNWITNESSED|DISAGREED)'),
    (0.0, 'resume', None, 'RESUME', r'YOUTUBE_PAUSE_RESUMED|YOUTUBE_POLL_PACED paused=False'),
    (20.0, 'seek-back', 6.0, 'SEEK-BACK-6S', r'YOUTUBE_SEEK_RESYNC'),
    (22.0, 'pause', 4.0, 'PAUSE-4S', r'YOUTUBE_PAUSE_(PROVEN|UNWITNESSED|DISAGREED)'),
    (0.0, 'resume', None, 'RESUME-2', r'YOUTUBE_PAUSE_RESUMED|YOUTUBE_POLL_PACED paused=False'),
    (20.0, 'seek-fwd', 10.0, 'SEEK-FWD-10S', r'YOUTUBE_SEEK_RESYNC'),
    (40.0, 'idle', None, 'SETTLE', r'YOUTUBE_TICK_MS'),
)

PLANS = {'full': PLAN, 'pause-only': PLAN[:2]}

PROBE_JS = ("(()=>{var v=document.querySelector('video'),mp=document.getElementById('movie_player');"
            "return JSON.stringify({t:v?+v.currentTime.toFixed(3):null,paused:v?v.paused:null,"
            "st:(mp&&mp.getPlayerState)?mp.getPlayerState():null,rs:v?v.readyState:null,"
            "muted:v?v.muted:null})})()")

MUTE_JS = ("(()=>{var v=document.querySelector('video');"
           "if(v&&!v.__sottoMuted){Object.defineProperty(v,'muted',{configurable:true,"
           "get:function(){return true},set:function(){}});"
           "Object.defineProperty(v,'volume',{configurable:true,"
           "get:function(){return 0},set:function(){}});v.__sottoMuted=1;}"
           "return 'muted'})()")


def act_js(action, param):
    """O JS de cada accao -- a API do PROPRIO player, nao o elemento cru."""
    if action == 'pause':
        return "(()=>{var mp=document.getElementById('movie_player');mp.pauseVideo();return 'pause'})()"
    if action in ('play', 'resume'):
        return "(()=>{var mp=document.getElementById('movie_player');mp.playVideo();return 'play'})()"
    if action == 'seek-back':
        return ("(()=>{var mp=document.getElementById('movie_player'),v=document.querySelector('video');"
                "var target=Math.max(0,v.currentTime-%s);mp.seekTo(target,true);"
                "return 'seek-back '+target.toFixed(2)})()" % param)
    if action == 'seek-fwd':
        return ("(()=>{var mp=document.getElementById('movie_player'),v=document.querySelector('video');"
                "var target=v.currentTime+%s;mp.seekTo(target,true);"
                "return 'seek-fwd '+target.toFixed(2)})()" % param)
    return "'idle'"


# --------------------------------------------------------------- o juiz ---
TS_LINE_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})\.(\d{3}) ')


def line_epoch(line):
    """O carimbo da propria linha, em segundos. `None` se nao houver carimbo."""
    found = TS_LINE_RE.match(line)
    if not found:
        return None
    year, month, day, hour, minute, sec, msec = (int(x) for x in found.groups())
    try:
        base = time.mktime((year, month, day, hour, minute, sec, 0, 0, -1))
    except (OverflowError, ValueError):
        return None
    return base + msec / 1000.0


def judge(steps, log_lines):
    """Puro: cada passo tem de achar o SEU padrao, numa linha NASCIDA depois dele.

    `steps` = [(label, pattern, start_wall)] -- `start_wall` e' o relogio local no
    instante em que o passo comecou. Um recibo de ANTES do passo nao prova nada: e'
    o defeito classico de julgar um log inteiro e chamar-lhe uma medicao.
    """
    stamped = [(line_epoch(line), line) for line in log_lines]
    out = []
    for label, pattern, start_wall in steps:
        found = ''
        rx = re.compile(pattern)
        for epoch, line in stamped:
            if epoch is None or epoch < start_wall:
                continue
            if rx.search(line):
                found = line.strip()[:150]
                break
        out.append((label, bool(found), found))
    return all(ok for _, ok, _ in out), out


def selftest():
    """Tres direccoes: recibo presente passa, ausente recusa, ANTERIOR nao conta."""
    t0 = time.mktime((2026, 11, 26, 3, 0, 0, 0, 0, -1))

    def line(offset, body):
        clock = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(t0 + offset))
        return clock + '.000 ' + body

    good = [line(1, 'YOUTUBE_PAUSE_PROVEN witness=flag+clock-static t=10.0 vid=A'),
            line(3, 'YOUTUBE_PAUSE_RESUMED witness=clock-moved t=12.0 vid=A'),
            line(5, 'YOUTUBE_SEEK_RESYNC was=20.0 now=14.0 why=back vid=A')]
    bad = [line(1, 'YOUTUBE_TICK_MS rows=2'),
           line(2, 'CAPTION_PAINT_SURFACE rows=2 text="a"')]
    steps = [('PAUSE', r'YOUTUBE_PAUSE_(PROVEN|UNWITNESSED|DISAGREED)', t0),
             ('RESUME', r'YOUTUBE_PAUSE_RESUMED', t0 + 2),
             ('SEEK', r'YOUTUBE_SEEK_RESYNC', t0 + 4)]
    stale = [('PAUSE', r'YOUTUBE_PAUSE_PROVEN', t0 + 10)]
    ok_good, _ = judge(steps, good)
    ok_bad, _ = judge(steps, bad)
    ok_stale, _ = judge(stale, good)
    print('SELFTEST recibo-presente   -> %s' % ('PASS' if ok_good else 'FAIL'))
    print('SELFTEST recibo-ausente    -> %s' % ('REFUSED' if not ok_bad else 'FALSE-GREEN'))
    print('SELFTEST recibo-ANTERIOR   -> %s' % ('REFUSED' if not ok_stale else 'FALSE-GREEN'))
    return 0 if (ok_good and not ok_bad and not ok_stale) else 1


# ------------------------------------------------------------- o browser ---
def _targets(port):
    with urllib.request.urlopen('http://127.0.0.1:%d/json/list' % port, timeout=3) as fh:
        return json.load(fh)


def _connect(port):
    import websocket
    tabs = [t for t in _targets(port) if t.get('type') == 'page' and '/watch' in (t.get('url') or '')]
    if not tabs:
        return None, None
    tab = tabs[0]
    ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=20)
    return ws, tab


def _eval(ws, expr, mid):
    ws.send(json.dumps({'id': mid, 'method': 'Runtime.evaluate',
                        'params': {'expression': expr, 'returnByValue': True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == mid:
            res = msg.get('result', {})
            if 'exceptionDetails' in res:
                return 'EXC ' + json.dumps(res['exceptionDetails'])[:160]
            return res.get('result', {}).get('value')


def _log_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _log_lines(path, offset):
    text = ''
    try:
        with io.open(path, 'r', encoding='utf-8', errors='replace') as fh:
            fh.seek(offset)
            text = fh.read()
    except OSError:
        return [], offset
    return text.splitlines(), offset + len(text.encode('utf-8', 'replace'))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=9222)
    ap.add_argument('--log', default=LOG_DEFAULT)
    ap.add_argument('--plan', default='full', choices=sorted(PLANS))
    ap.add_argument('--fast', action='store_true', help='esperas a 1/4, para depurar')
    ap.add_argument('--settle', type=float, default=6.0,
                    help='segundos a esperar o recibo de cada passo')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()

    ws, tab = _connect(args.port)
    if ws is None:
        print('LIVE-DRIVE CANNOT-MEASURE reason=no-watch-tab port=%d' % args.port)
        return 3
    print('TAB %s | %s' % ((tab.get('title') or '')[:56], (tab.get('url') or '')[:60]))
    print('MUTE %s' % _eval(ws, MUTE_JS, 1))
    state = json.loads(_eval(ws, PROBE_JS, 2))
    print('STATE %s' % json.dumps(state))
    if state.get('paused') is not False:
        print('LIVE-DRIVE CANNOT-MEASURE reason=not-playing paused=%s '
              '(o player parado nao produz evento)' % state.get('paused'))
        ws.close()
        return 3

    rows = []
    for wait_s, action, param, label, pattern in PLANS[args.plan]:
        if wait_s:
            time.sleep(wait_s / 4.0 if args.fast else wait_s)
        before = json.loads(_eval(ws, PROBE_JS, 10))
        started = time.time()
        said = _eval(ws, act_js(action, param), 11)
        if action == 'pause':
            time.sleep(param if not args.fast else param / 4.0)
            held = json.loads(_eval(ws, PROBE_JS, 12))
            print('STEP %-12s %-10s paused=%s t=%s' % (label, said, held.get('paused'), held.get('t')))
        else:
            time.sleep(min(args.settle, 2.0))
            after_state = json.loads(_eval(ws, PROBE_JS, 12))
            print('STEP %-12s %-22s t %s -> %s paused=%s'
                  % (label, said, before.get('t'), after_state.get('t'), after_state.get('paused')))
        rows.append((label, pattern, started))
        time.sleep(args.settle)
    # O JULGAMENTO LE O LOG DA JANELA INTEIRA, uma vez, e cada recibo tem de ser
    # de uma linha NASCIDA depois do passo que o pediu.
    lines, _ = _log_lines(args.log, 0)
    window = lines[-400000:]
    ok, judged = judge(rows, window)
    for label, good, evidence in judged:
        print('  %-5s %-12s %s' % ('PASS' if good else 'MISS', label,
                                   evidence or 'sem recibo no log'))
    ws.close()
    print('LIVE-DRIVE VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
