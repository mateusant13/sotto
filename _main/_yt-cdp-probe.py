"""Le' a legenda do player pela CDP, SEM focar a aba e SEM tocar em mais nada.

PORQUE ESTE FICHEIRO EXISTE (2026-11-03):

  * `agent-browser ... tab t5` TROUXE a aba do YouTube para a frente na janela
    do dono -- ele: *"para de focar o navegador. roda ele no background"*.
  * a alternativa do CLI (sessao presa a' aba) leu, minutos depois, a pagina em
    que a aba tinha navegado -- `pixeldrain.com` -- e as 34 leituras seguintes
    foram de uma pagina que NAO e' do YouTube. Ele: *"tu SO TEM permissao de
    listar paginas que sao do youtube"*.

A REGRA E' MECANICA AQUI: `GET /json/list` da' as abas; o filtro aceita SO'
`youtube.com`/`youtu.be`; sem alvo elegivel o leitor devolve `NO-YT-TAB` e nao
abre ligacao nenhuma. Uma aba que nao seja do YouTube nunca e' lida, nem para
diagnostico -- so' o numero delas e' contado.

Nao ha `Target.activateTarget` em sitio nenhum: `Runtime.evaluate` no alvo nao
muda o foco, nao da' play e nao toca no volume.
"""
from __future__ import annotations

import json
import re
import urllib.request

import websocket  # websocket-client

CDP = 'http://127.0.0.1:9222'
YT = re.compile(r'^https?://(www\.|m\.|music\.)?(youtube\.com|youtu\.be)(/|$)')

PROBE = """(() => {
  try {
    const v = document.querySelector('video');
    const segs = Array.from(document.querySelectorAll('.ytp-caption-segment'))
      .map(e => e.textContent.trim()).filter(Boolean);
    return JSON.stringify({url: location.href.slice(0, 120), hasVideo: !!v,
      t: v ? Math.round(v.currentTime*1000)/1000 : null,
      paused: v ? v.paused : null, muted: v ? v.muted : null, rows: segs});
  } catch (e) { return JSON.stringify({error: String(e)}); }
})()"""


def targets(timeout=6.0):
    """(abas do YouTube, numero de abas de outra coisa) -- sem ler as outras."""
    with urllib.request.urlopen(CDP + '/json/list', timeout=timeout) as handle:
        data = json.load(handle)
    yt = []
    other = 0
    for tab in data or ():
        if tab.get('type') != 'page':
            continue
        url = str(tab.get('url') or '')
        if YT.match(url):
            yt.append(tab)
        else:
            other += 1
    return yt, other


def probe(timeout=10.0):
    """O estado do player: dict, ou {'error': 'NO-YT-TAB'}."""
    try:
        yt, other = targets()
    except Exception as exc:  # noqa: BLE001
        return {'error': 'CDP %r' % (exc,), 'other_tabs': None}
    watch = [t for t in yt if '/watch' in str(t.get('url') or '')]
    pick = (watch or yt or [None])[0]
    if pick is None:
        return {'error': 'NO-YT-TAB', 'youtube_tabs': 0, 'other_tabs': other}
    ws_url = pick.get('webSocketDebuggerUrl')
    if not ws_url:
        return {'error': 'NO-WS-URL', 'youtube_tabs': len(yt),
                'other_tabs': other}
    try:
        conn = websocket.create_connection(ws_url, timeout=timeout)
    except Exception as exc:  # noqa: BLE001
        return {'error': 'WS %r' % (exc,), 'youtube_tabs': len(yt),
                'other_tabs': other}
    try:
        conn.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate',
                              'params': {'expression': PROBE,
                                         'returnByValue': True}}))
        while True:
            msg = json.loads(conn.recv())
            if msg.get('id') == 1:
                break
        value = (msg.get('result') or {}).get('result', {}).get('value')
        out = json.loads(value) if isinstance(value, str) else {'error': 'NO-VALUE'}
    except Exception as exc:  # noqa: BLE001
        return {'error': 'EVAL %r' % (exc,), 'youtube_tabs': len(yt),
                'other_tabs': other}
    finally:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
    out['youtube_tabs'] = len(yt)
    out['other_tabs'] = other
    return out


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False, indent=2))
