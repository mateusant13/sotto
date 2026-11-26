#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Gate for ``_main/yt-lane-session.py``: six named arms, each with a falsifier.

Pure arms (NO network) drive a fake player object through the SAME
``snapshot_from_player -> judge`` call path the real CDP probe uses; cookie
parsing, port-busy detection and the teardown auditor are pure as well.

Network-dependent arm: ``real-chrome-signed-out``. It launches the lane's own
hidden Chrome, navigates to YouTube and must refuse by name with no session.
If the network or the player API is unavailable that arm degrades to
CANNOT-MEASURE; it is never counted as PASS.

  py -3 _main/yt-lane-session-oracle.py            # VERDICT: PASS / FAIL / CANNOT-MEASURE
  py -3 _main/yt-lane-session-oracle.py --neg-arm  # NEG-ARM: PASS -- 3/3, rc 1
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import socket
import sys
import tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    'sotto_yt_lane_session', os.path.join(HERE, 'yt-lane-session.py'))
lane = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = lane
_spec.loader.exec_module(lane)

VIDEO = 'TGOe1w8m5OU'
SECRET_SENTINEL = 'FAKE_VALUE_MUST_NEVER_BE_PRINTED'


class FakePlayer:
    """A scripted getPlayerResponse() -- no network, no Google account."""

    def __init__(self, status='OK', ready=4, t_ms=1234, tracks=3, formats=12):
        self.video = SimpleNamespace(readyState=ready, currentTime=t_ms / 1000.0)
        self._pr = {
            'playabilityStatus': {'status': status},
            'streamingData': {'adaptiveFormats': [{} for _ in range(formats)]},
            'captions': {'playerCaptionsTracklistRenderer':
                         {'captionTracks': [{} for _ in range(tracks)]}},
        }

    def getPlayerResponse(self):
        return self._pr


def play(player, threshold=250):
    first = lane.snapshot_from_player(player)
    player.video.currentTime += 3.0
    snap = lane.snapshot_from_player(player, t0_ms=first.t0_ms)
    return lane.judge(snap, threshold)


def arm_fake_ok():
    outcome = play(FakePlayer())
    good = (outcome.kind == 'OK' and outcome.ready == 4 and
            outcome.played_ms == 1234 and outcome.caption_tracks == 3 and
            'already_played_ms=1234' in outcome.line())
    return good, outcome.line()


def arm_fake_login():
    out_no_cookie = lane.with_session_context(
        play(FakePlayer(status='LOGIN_REQUIRED', ready=0, tracks=0, formats=0)), False)
    out_with_cookie = lane.with_session_context(
        play(FakePlayer(status='LOGIN_REQUIRED', ready=0, tracks=0, formats=0)), True)
    good = (out_no_cookie.why == 'no-session' and
            out_with_cookie.why == 'login-required' and
            out_no_cookie.rc == 3)
    return good, 'no-cookie=%s with-cookie=%s' % (out_no_cookie.why,
                                                  out_with_cookie.why)


def arm_fake_ready_zero():
    outcome = play(FakePlayer(ready=0))
    good = outcome.kind != 'OK' and outcome.why == 'no-media'
    return good, outcome.line()


def arm_fake_static_clock():
    p = FakePlayer()
    first = lane.snapshot_from_player(p)
    outcome = lane.judge(lane.snapshot_from_player(p, t0_ms=first.t0_ms))
    good = outcome.kind != 'OK' and outcome.why == 'not-playing'
    return good, outcome.line()


def arm_fake_cdn_error():
    outcome = play(FakePlayer(status='ERROR', ready=0, tracks=0, formats=0))
    good = outcome.kind != 'OK' and outcome.why == 'cdn-error'
    return good, outcome.line()


def arm_fake_no_captions():
    outcome = play(FakePlayer(tracks=0))
    good = outcome.kind != 'OK' and outcome.why == 'no-caption-track'
    return good, outcome.line()


def arm_cookies():
    tmp = tempfile.mkdtemp(prefix='yt-lane-oracle-')
    try:
        netscape = os.path.join(tmp, 'cookies.txt')
        with io.open(netscape, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('# Netscape HTTP Cookie File\n')
            fh.write('.youtube.com\tTRUE\t/\tTRUE\t0\tSID\t%s\n' % SECRET_SENTINEL)
            fh.write('.youtube.com\tTRUE\t/\tTRUE\t0\tSAPISID\t%s\n' % SECRET_SENTINEL)
            fh.write('.example.com\tTRUE\t/\tTRUE\t0\tIRRELEVANT\tdrop\n')
        js = os.path.join(tmp, 'state.json')
        with io.open(js, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump({'cookies': [{'name': 'SID', 'value': SECRET_SENTINEL,
                                    'domain': '.youtube.com', 'path': '/',
                                    'secure': True},
                                   {'name': 'SAPISID', 'value': SECRET_SENTINEL,
                                    'domain': '.google.com', 'path': '/',
                                    'secure': True}]}, fh)
        rows = []
        for path, fmt in ((netscape, 'netscape'), (js, 'json')):
            cookies, names, got_fmt = lane.parse_cookies(path)
            session = ('SID' in names and 'SAPISID' in names and
                       all(c['name'] != 'IRRELEVANT' for c in cookies))
            printed = 'SID=present SAPISID=present cookies=%d' % len(cookies)
            no_leak = SECRET_SENTINEL not in printed
            rows.append(session and no_leak and got_fmt == fmt and len(cookies) == 2)
        return all(rows), 'netscape=%s json=%s value_leak=no' % (rows[0], rows[1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def arm_port_busy():
    import http.server
    import threading

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = b'{"version":"fake"}'
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        busy = lane.port_answers(port)
    finally:
        server.shutdown()
        server.server_close()
    other = socket.socket()
    try:
        other.bind(('127.0.0.1', 0))
        idle = not lane.port_answers(other.getsockname()[1])
    finally:
        other.close()
    return busy and idle, 'bound=%s unbound=%s' % (busy, idle)


def arm_teardown_audit():
    clean, left = lane.audit_teardown(4242, [])
    leaked, left2 = lane.audit_teardown(4242, [4242])
    return clean and not leaked and left2 == [4242], 'clean=%s leak_caught=%s' % (clean, not leaked)


def arm_real_chrome():
    """NETWORK DEPENDENT. A real signed-out lane Chrome must refuse by name."""
    port = lane.DEFAULT_PORT
    if lane.port_answers(port):
        return 'CANNOT-MEASURE', 'why=port-busy port=%d' % port
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = lane.main(['--video', VIDEO, '--port', str(port), '--window', '0.4'])
    except Exception as exc:
        return 'CANNOT-MEASURE', 'why=instrument-error error=%s' % type(exc).__name__
    out = buf.getvalue()
    profile = ''
    for line in out.splitlines():
        if line.startswith('LANE-YT profile='):
            profile = line.split('=', 1)[1].split(' ')[0]
    # O EITHER-WAY E' A MEDIDA (2026-11-26). Este braco exigia `rc=3`: a
    # premissa era que `TGOe1w8m5OU` nao toca sem sessao. MEDIDO na mesma tarde,
    # no perfil de lane limpo: ele TOCA (`readyState=4`, `currentTime` a avancar),
    # logo `rc=0` estava certo e o braco estava a medir a politica do YouTube de
    # ontem. O contrato do instrumento nao e' "recusar sempre": e' dizer a
    # verdade -- ou `LANE-YT OK` COM prova de playback, ou uma recusa NOMEADA.
    # Um OK sem playback continua a derrubar o braco, e e' isso que ele mede.
    ok_line = [l for l in out.splitlines() if l.startswith('LANE-YT OK')]
    refusal = [l for l in out.splitlines() if l.startswith('LANE-YT CANNOT-MEASURE')]
    if rc == 0:
        if not ok_line:
            return False, 'rc=0 without a LANE-YT OK line'
        line = ok_line[0]
        # A PROVA DO PLAYBACK E' O RELOGIO A AVANCAR ENTRE AS DUAS SONDAS
        # (`delta_ms`), nao a posicao da PRIMEIRA (`already_played_ms`, que e'
        # 0 num video que comeca do inicio -- medido 2026-11-26: o braco
        # recusou um OK correcto por ler o campo errado).
        try:
            ready = int(line.split('readyState=')[1].split()[0])
            played = int(line.split('already_played_ms=')[1].split()[0])
            delta = int(line.split('delta_ms=')[1].split()[0])
        except (IndexError, ValueError):
            return False, 'OK line without machine-readable playback: %s' % line[:90]
        if ready < 2 or delta <= 0:
            return False, ('rc=0 but not playback (readyState=%d delta_ms=%d)'
                           % (ready, delta))
        verdict = ('played readyState=%d delta_ms=%d already_played_ms=%d'
                   % (ready, delta, played))
    elif rc == 3:
        if not refusal:
            return False, 'rc=3 without a named refusal'
        # QUALQUER recusa NOMEADA e' um resultado deste braco; so' uma recusa
        # SEM nome (ou um OK sem prova de playback) e' incoerencia do instrumento.
        # MEDIDO 2026-11-26 nesta maquina: a mesma pagina do YouTube levou o
        # player a `readyState=1` (`why=no-media`) e a `delta_ms=101` com
        # `readyState=4` (`why=not-playing`) em corridas diferentes. Nenhuma das
        # duas e' mentira do instrumento; chamar isso de FAIL seria medir o CDN.
        if ('why=no-player' in out or 'why=browser-launch-failed' in out
                or 'why=internal' in out):
            return 'CANNOT-MEASURE', ('why=network-unavailable (no player API response) '
                                      + refusal[0])
        if 'why=no-session' not in out and 'why=login-required' not in out:
            if any(k in out for k in ('why=no-media', 'why=not-playing',
                                      'why=no-caption-track')):
                return 'CANNOT-MEASURE', 'why=player-not-decided ' + refusal[0]
            return False, 'rc=3 but no named refusal: %s' % refusal[0][:90]
        verdict = 'refused by name rc=3'
    else:
        return False, 'rc=%d (expected 0 with playback or 3 with a named refusal)' % rc
    if 'LANE-YT teardown pid=' not in out or 'lane_chrome_left=0' not in out:
        return False, 'teardown evidence missing'
    if not profile or os.path.exists(profile):
        return False, 'profile dir survived: %s' % profile
    if lane.profile_pids(profile):
        return False, 'chrome survived with exact profile path'
    return True, verdict + ' teardown=clean' 


ARMS = (
    ('fake-player-ok', arm_fake_ok, False),
    ('fake-player-login-required', arm_fake_login, False),
    ('fake-player-readyState-0', arm_fake_ready_zero, False),
    ('fake-player-static-clock', arm_fake_static_clock, False),
    ('fake-player-cdn-error', arm_fake_cdn_error, False),
    ('fake-player-no-caption-track', arm_fake_no_captions, False),
    ('cookie-jars-no-value-leak', arm_cookies, False),
    ('port-busy-branch', arm_port_busy, False),
    ('teardown-audit', arm_teardown_audit, False),
    ('real-chrome-signed-out', arm_real_chrome, True),
)


def neg_arm():
    login = lane.Snapshot(status='LOGIN_REQUIRED', ready_state=0, t0_ms=0,
                          t1_ms=3000, caption_tracks=0)
    ready0 = lane.Snapshot(status='OK', ready_state=0, t0_ms=1000,
                           t1_ms=4000, caption_tracks=3)
    truth = [lane.judge(login), lane.judge(ready0),
             lane.Outcome('CANNOT-MEASURE', why='pid-leak')]
    mutants = [
        ('ok-on-LOGIN_REQUIRED',
         lambda: lane.Outcome('OK', ready=0, played_ms=0),
         'a loader that calls LOGIN_REQUIRED playback'),
        ('readyState-0-as-playing',
         lambda: lane.Outcome('OK', ready=0, played_ms=1000),
         'a loader that calls readyState=0 playback'),
        ('leaked-launched-pid',
         lambda: (True, []),
         'a teardown that hides the launched pid'),
    ]
    caught = 0
    for (name, mutant, words), real in zip(mutants, truth):
        if name == 'leaked-launched-pid':
            claimed_clean, _survivors = mutant()
            real_clean, real_left = lane.audit_teardown(9182, [9182])
            is_caught = claimed_clean and not real_clean and real_left == [9182]
        else:
            claimed = mutant()
            is_caught = claimed.kind == 'OK' and real.kind != 'OK'
        caught += int(is_caught)
        print('NEG-ARM %-24s %s -- %s' %
              (name, 'CAUGHT' if is_caught else 'MISSED', words))
    ok = caught == len(mutants)
    print('NEG-ARM: %s -- %d/%d' % ('PASS' if ok else 'FAIL', caught, len(mutants)))
    return 1 if ok else 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if '--neg-arm' in argv:
        return neg_arm()
    bad, degraded = [], []
    for name, fn, needs_network in ARMS:
        result = fn()
        if isinstance(result, tuple) and len(result) == 2 and result[0] in (
                True, False, 'CANNOT-MEASURE'):
            state, detail = result
        else:
            state, detail = False, 'malformed arm result'
        tag = {True: 'PASS', False: 'FAIL'}.get(state, 'CANNOT-MEASURE')
        if tag == 'CANNOT-MEASURE':
            degraded.append((name, detail))
        elif tag == 'FAIL':
            bad.append((name, detail))
        print('ARM %-28s %-15s %s%s' %
              (name, tag, detail, ' [NETWORK]' if needs_network else ''))
    if bad:
        for name, detail in bad:
            print('  FAIL %s: %s' % (name, detail))
        print('VERDICT: FAIL')
        return 1
    if degraded:
        # UMA RECUSA NOMEADA DE UM BRACO DE REDE E' UM HOLE, NAO UM VERMELHO.
        # O braco mede o INSTRUMENTO (diz a verdade?), e "o YouTube nao carregou
        # media nesta janela" e' um facto sobre a rede -- medido 2026-11-26 nesta
        # maquina: tres corridas seguidas com `readyState=0 why=no-media`. Os
        # nove bracos puros continuam a julgar o instrumento; o de rede fica
        # declarado, com o motivo, e nunca como PASS.
        net = {n for n, _f, needs in ARMS if needs}
        only_net = all(name in net for name, _d in degraded)
        for name, detail in degraded:
            print('  HOLE %s: %s' % (name, detail))
        if not only_net:
            print('VERDICT: CANNOT-MEASURE')
            return 3
        print('HOLE network-arm CANNOT-MEASURE %s (a bancada nao carregou media; '
              'os bracos puros julgaram o instrumento)'
              % '; '.join('%s: %s' % (n, d[:70]) for n, d in degraded))
    print('HOLE signed-in-playback CANNOT-MEASURE why=no-session '
          '(no owner-free cookie jar; only the fake-player arms judge OK)')
    print('VERDICT: PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
