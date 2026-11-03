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

import io
import json
import os
import re
import urllib.request

import websocket  # websocket-client

HERE = os.path.dirname(os.path.abspath(__file__))

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

def open_socket(timeout=10.0, video_id=None):
    """(ws, erro) para a aba do video -- sem ativar a aba.

    `video_id` ESCOLHE A ABA (2026-11-03). Com duas abas do YouTube abertas o
    leitor agarrava a primeira `watch` que aparecesse e media um video que o
    Sotto NAO estava a ler: o veredicto saiu todo errado -- 68 mudancas do
    player contra 0 quadros do Sotto, porque as duas abas mostravam videos
    diferentes. O id vem do log do proprio Sotto (`YOUTUBE_CAPTION
    video_id=`), que e' a declaracao de qual video ele le.
    """
    try:
        yt, _other = targets()
    except Exception as exc:  # noqa: BLE001
        return None, 'CDP %r' % (exc,)
    watch = [t for t in yt if '/watch' in str(t.get('url') or '')]
    if video_id:
        named = [t for t in watch if video_id in str(t.get('url') or '')]
        if not named:
            return None, 'VIDEO-%s-NOT-OPEN' % video_id
        watch = named
    pick = (watch or yt or [None])[0]
    if pick is None:
        return None, 'NO-YT-TAB'
    try:
        return websocket.create_connection(pick['webSocketDebuggerUrl'],
                                           timeout=timeout), None
    except Exception as exc:  # noqa: BLE001
        return None, 'WS %r' % (exc,)



#: As linhas que o player esta' MESMO a mostrar, e o silencio re-afirmado.
#: O DOM guarda um terceiro segmento a sair da caixa durante a transicao
#: (medido 2026-11-03: `n_all=3` com `n_inside=2` em 690 ms) -- um leitor que
#: conta filhos do DOM le 3 linhas onde o ecra mostra 2.
SILENT_PROBE = """(() => {
  const cl = s => String(s||'').replace(/\\s+/g,' ').trim();
  try {
    const v = document.querySelector('video');
    if (!v) return JSON.stringify({error: 'no-video'});
    v.muted = true; v.volume = 0;
    if (v.paused) { try { v.play(); } catch (e) {} }
    const win = document.querySelector('.caption-window');
    const wr = win ? win.getBoundingClientRect() : null;
    const segs = [];
    for (const e of document.querySelectorAll('.ytp-caption-segment')) {
      const text = cl(e.textContent);
      if (!text) continue;
      const r = e.getBoundingClientRect();
      const st = getComputedStyle(e);
      if (st.visibility === 'hidden' || parseFloat(st.opacity || '1') < 0.25) continue;
      if (wr && (r.top < wr.top - 3 || r.bottom > wr.bottom + 3)) continue;
      segs.push(text);
    }
    return JSON.stringify({url: location.href.slice(0, 120),
      t: Math.round(v.currentTime*1000)/1000, paused: v.paused,
      muted: v.muted, vol: v.volume, rows: segs});
  } catch (e) { return JSON.stringify({error: String(e)}); }
})()"""


def review(ws, counter, js, extra=()):
    """Uma avaliacao com `SILENT_PROBE` e as instrucoes de visibilidade.

    `Page.setWebLifecycleState(active)` e `Emulation.setFocusEmulationEnabled`
    existem por um defeito MEDIDO em 2026-11-03: com a aba do YouTube em
    segundo plano o video continua a avancar mas o player DEIXA de pintar a
    legenda -- 90 s de reprodutividade deram `rows=[]` em todas as 219
    amostras. Nao era o Sotto: era o instrumento a ler uma pagina congelada.
    """
    for method, params in extra:
        counter[0] += 1
        ws.send(json.dumps({'id': counter[0], 'method': method,
                            'params': params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get('id') == counter[0]:
                break
    counter[0] += 1
    ws.send(json.dumps({'id': counter[0], 'method': 'Runtime.evaluate',
                        'params': {'expression': js, 'returnByValue': True,
                                   'userGesture': True}}))
    while True:
        msg = json.loads(ws.recv())
        if msg.get('id') == counter[0]:
            break
    value = (msg.get('result') or {}).get('result', {}).get('value')
    try:
        return json.loads(value) if isinstance(value, str) else {}
    except Exception:  # noqa: BLE001
        return {}


#: O `cl` do navegador colapsa espacos como o nosso `norm`.
BROWSER_HELPERS = "const cl = s => String(s||'').replace(/\\s+/g,' ').trim();"

def sottos_video_id(log_path=None):
    """O `video_id` que o Sotto declara ler, lido do PROPRIO log dele."""
    log_path = log_path or os.path.join(HERE, 'webview-run.log')
    pattern = re.compile(r'YOUTUBE_CAPTION video_id=(\S+)')
    found = None
    try:
        with io.open(log_path, encoding='utf-8', errors='replace') as handle:
            for line in handle:
                match = pattern.search(line)
                if match:
                    found = match.group(1)
    except OSError:
        return None
    return found
