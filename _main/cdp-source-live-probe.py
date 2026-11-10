# -*- coding: utf-8 -*-
"""MEDE A FONTE CDP NOVA CONTRA O CHROME VIVO DO DONO -- SO' LEITURA.

Nao cria alvo nenhum, nao navega, nao fecha aba nenhuma, nao traz janela para
a frente: o unico I/O e' `GET /json/list` e o WebSocket que a propria fonte
abre para avaliar o estado da aba (`Runtime.evaluate` de leitura).

Colunas que o recibo usa:
  list_ms        -- `/json/list` cru (HTTP), 20 amostras
  cold_ms        -- `target_video_id()` na primeira chamada, com a fonte
                    arrancada agora (o caminho do tick frio)
  warm_*         -- `target_video_id()` com a foto quente (o que o tick paga)
  refresh_probe  -- o que o fio `yt-cdp-target` paga ao re-escolher COM sonda
  refresh_noprobe-- a mesma re-escolha SEM sonda (o caminho novo do tick frio)

Uso:  python _main/cdp-source-live-probe.py [porta] [amostras]
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.abspath(os.path.join(HERE, os.pardir, 'app', 'webview'))
if APP not in sys.path:
    sys.path.insert(0, APP)

import youtube_cdp_source as cdp  # noqa: E402


def _ms(t0):
    return (time.perf_counter() - t0) * 1000.0


def _pct(values, q):
    ordered = sorted(values)
    if not ordered:
        return 0.0
    idx = min(len(ordered) - 1, int(round((len(ordered) - 1) * q)))
    return ordered[idx]


def _list(port):
    url = 'http://127.0.0.1:%d/json/list' % port
    with urllib.request.urlopen(url, timeout=3.0) as resp:
        raw = resp.read()
    return json.loads(raw.decode('utf-8', 'replace')), len(raw)


def _sig(tabs):
    return sorted((str(t.get('id') or ''), str(t.get('url') or ''),
                   str(t.get('title') or '')) for t in tabs or ())


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9222
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    before, _ = _list(port)
    print('tabs_before=%d watch=%d' % (
        len(before),
        sum(1 for t in before if 'youtube.com/watch' in str(t.get('url')))))
    for tab in before:
        if 'youtube.com/watch' in str(tab.get('url')):
            print('  youtube_target id=%s title=%r' % (tab.get('id'),
                                                       str(tab.get('title'))[:60]))

    times = []
    for _ in range(n):
        t0 = time.perf_counter()
        _list(port)
        times.append(_ms(t0))
    print('list_ms n=%d min=%.1f median=%.1f p95=%.1f max=%.1f'
          % (len(times), min(times), _pct(times, 0.5), _pct(times, 0.95),
             max(times)))

    logs = []
    src = cdp.CdpCaptionSource(port=port, log=logs.append)
    try:
        t0 = time.monotonic()
        src.start()
        start_ms = _ms(t0)
        t0 = time.monotonic()
        cold = src.target_video_id()
        cold_ms = _ms(t0)

        deadline = time.monotonic() + 5.0
        warm = []
        while time.monotonic() < deadline:
            if src.snapshot(max_age=1.0) is not None:
                break
            time.sleep(0.01)
        for _ in range(200):
            t0 = time.monotonic()
            src.target_video_id()
            warm.append(_ms(t0))
        warm.sort()

        t0 = time.monotonic()
        picked = src._tid_refresh(probe=False)
        noprobe_ms = _ms(t0)
        t0 = time.monotonic()
        probed = src._tid_refresh(probe=True)
        probe_ms = _ms(t0)
        print('source start_ms=%.1f cold_ms=%.1f cold_vid=%r'
              % (start_ms, cold_ms, cold))
        print('tick target_video_id n=%d median=%.3f p95=%.3f max=%.3f'
              % (len(warm), _pct(warm, 0.5), _pct(warm, 0.95), max(warm)))
        print('refresh_noprobe_ms=%.1f pick=%r refresh_probe_ms=%.1f pick=%r'
              % (noprobe_ms, (picked or '')[:40], probe_ms,
                 (probed or '')[:40]))
    finally:
        try:
            src.stop()
        except Exception:                    # noqa: BLE001
            pass
    after, _ = _list(port)
    same = _sig(before) == _sig(after)
    print('tabs_after=%d unchanged=%s' % (len(after), same))
    for line in logs:
        print('  LOG', line)
    return 0 if same else 2


if __name__ == '__main__':
    raise SystemExit(main())
