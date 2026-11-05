"""A SEGUNDA FONTE da legenda do YouTube: a CDP do proprio Chrome.

PORQUE EXISTE (MEDIDO 2026-11-03, e e' o unico motivo)

Com a aba do YouTube em SEGUNDO PLANO, o Chrome deixa de expor a janela de
legenda na arvore de acessibilidade: o Sotto fica sem fonte nenhuma e a legenda
desaparece do ecra. A medicao que poe o piso no Chrome (e nao no Sotto):

  * 3 minutos com o instrumento TODO desligado: um `YOUTUBE_CAPTION` e depois
    nada; `YOUTUBE_PAINT_STALL seconds=25..61 why=no-painted-caption` uma vez por
    5 s, sem recuperar dentro do processo.
  * um cliente UIA NOVO, noutro processo, tambem veio vazio.

A CDP le a MESMA arvore do mesmo Chrome, mas pelo protocolo de depuracao: ela
devolve o que o player tem no DOM, com ou sem acessibilidade, e custa ~10 ms por
leitura (medido em `_main/_yt-cdp-probe.py`).

O QUE ESTE MODULO NAO FAZ

  * NAO ativa a aba, nao foca a janela, nao envia input: e' leitura.
  * NAO le aba nenhuma que nao seja do YouTube (`/watch`), e recusa-se a
    escolher quando ha' mais de um video aberto e o Sotto nao declarou qual le --
    `ambiguous`, e quem chama continua com a UIA.
  * NAO inventa linha: as linhas vem do `.caption-visual-line` do player, e os
    rectangulos de cada `.ytp-caption-segment`. E' a mesma geometria que a UIA
    le, pela mesma razao: a quebra de linha e' do player, nao nossa.

CONTRATO

    src = CdpCaptionSource(port=9222)
    src.start()
    snap = src.snapshot()        # {"stamp", "videoId", "title", "rows",
                                #  "items", "why"} ou None
    src.stop()

`rows` sao as LINHAS do player (texto), `items` os filhos com rectangulo (o
mesmo formato que `youtube_captions._painted_items` devolve). `snapshot()`
devolve `None` sem ligacao -- nunca levanta, nunca bloqueia a thread que chama.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request

#: Porta de depuracao que o Chrome do dono ja' tem aberta (medido 2026-11-03).
DEFAULT_PORT = 9222


def resolve_port(port=None):
    """A porta da CDP: o argumento, ou `SOTTO_YT_CDP_PORT`, ou a 9222.

    O override de ambiente existe por duas razoes medidas: a porta de depuracao
    do Chrome e' configuravel no atalho dele, e um oraculo tem de poder apontar
    a ligacao para um servidor de FOTOGRAFIA sem tocar no Chrome do dono --
    um controle que so' sabe falar com o browser real nao tem controle.
    """
    if port is not None:
        return int(port)
    env = os.environ.get("SOTTO_YT_CDP_PORT")
    if env and str(env).strip().isdigit():
        return int(str(env).strip())
    return int(DEFAULT_PORT)


#: Uma leitura a cada 80 ms. O custo medido de uma ida e volta com
#: `Runtime.evaluate` e' ~10 ms, e a legenda do player muda a cada 100-300 ms.
POLL_S = 0.08

#: Sem ninguem a pedir, a ligacao fecha-se passado isto (nao fica a gastar CPU
#: nem a segurar um socket quando o YouTube nao esta' a ser lido).
IDLE_STOP_S = 120.0
#: O passo da leitura CDP com o video PAUSADO (2026-11-05). Uma legenda nao muda
#: com o video parado; o custo de detetar o `play` e' este numero, e a primeira
#: cue chega depois dele de qualquer forma. Ver `_run`.
PAUSED_POLL_S = 0.5

#: Espera entre tentativas depois de uma falha, para nao bater a porta a 12 Hz
#: quando o Chrome esta' fechado.
RETRY_S = 2.0

#: O TECTO DA ESPERA ENTRE ATTEMPTS DE ATTACH (2026-11-05, MEDIDO na instancia
#: viva pid 20236). Com o browser SEM porta de depuracao o ciclo e'
#: `_connect` (ATTACH_PROBE_TIMEOUT_S = 1,5 s de um prazo destinado a falhar) +
#: `RETRY_S`: 43 % de um fio a bater a uma porta morta, medido no log como
#: `YOUTUBE_CDP_ATTACH_FAILED attempt=450 ... reason=probe-timeout ms=1500`
#: enquanto o processo ao lado tinha um socket em `SYN_SENT` para 127.0.0.1:9222
#: e NENHUM browser com `--remote-debugging-port=9222`. A espera dobra a cada
#: falha ate' aqui e volta a `RETRY_S` no primeiro attach que passa: o tecto e'
#: baixo de proposito, porque o custo de esperar demais e' a legenda do YouTube
#: chegar tarde quando o browser ABRE no meio da sessao.
ATTACH_RETRY_MAX_S = 8.0

#: O PRAZO DE UMA SONDA DE ATTACH (2026-11-04, MEDIDO). Contra uma porta
#: FECHADA nesta maquina um `/json/list` gasta 2,0 s de `URLError`; com o prazo
#: de 3 s do `list_targets` um ciclo de retry custava 4 s e o log de motivos
#: saia uma vez por ciclo, o que parece "nao tenta". 1,5 s e' acima da chamada
#: mais lenta ja' medida (1125 ms, sob carga) e abaixo do custo de uma porta
#: morta; o que passar disto esta' registado com o `ms=` de cada tentativa.
ATTACH_PROBE_TIMEOUT_S = 1.5

#: QUANTOS PRAZOS SEGUIDOS na mesma ligacao antes de a declarar MORTA
#: (2026-11-05). Um prazo e' pagina lenta; tres seguidos no mesmo socket sao um
#: cano partido, e esperar por ele nao traz foto nenhuma.
SLOW_STREAK_MAX = 3

_WATCH = "/watch"

#: O QUE O PLAYER DESENHOU, lido DENTRO da pagina (uma ida e volta).
#: `getBoundingClientRect` e' relativo a viewport -- e' o que serve, porque tudo
#: o que se faz com a geometria (agrupar por centro, ordenar por esquerda) e'
#: relativo. Sem `window.screenX/Y`: misturar coordenadas de ecra com as da UIA
#: nao acrescenta nada e so' cria duas origens no mesmo campo.
EXTRACT_JS = r"""
(() => {
  const m = /[?&]v=([\w-]{11})/.exec(location.href || '');
  const v = document.querySelector('video');
  const out = {videoId: m ? m[1] : '', title: document.title || '',
               rows: [], segs: [], why: 'no-window',
               t: v ? v.currentTime : null, paused: v ? v.paused : null,
               rs: v ? v.readyState : null,
               rate: v ? v.playbackRate : null};
  const box = document.querySelector('.ytp-caption-window-container');
  if (!box) return JSON.stringify(out);
  const all = Array.prototype.slice.call(
      box.querySelectorAll('.caption-visual-line'));
  const segs = Array.prototype.slice.call(
      box.querySelectorAll('.ytp-caption-segment'));
  out.segs = segs.map(function (s) { return (s.textContent || '').trim(); })
                 .filter(function (t) { return t.length > 0; });
  if (!all.length) { out.why = 'no-painted-caption'; return JSON.stringify(out); }
  // O CLIP E' DO `.caption-window` (MEDIDO 2026-11-03): `overflow: hidden`, e
  // as linhas que ROLARAM PARA FORA continuam no DOM. Sem este filtro le-se
  // historicidade que ninguem ve' -- foi o que fez uma medicao inteira comparar
  // as nossas 2 linhas com 9 linhas de historico do player.
  let clip = null;
  for (let el = all[0].parentElement; el; el = el.parentElement) {
    const cs = getComputedStyle(el);
    if (cs.overflow === 'hidden' || cs.overflowY === 'hidden') {
      clip = el.getBoundingClientRect();
      break;
    }
  }
  const visible = all.filter(function (line) {
    const r = line.getBoundingClientRect();
    const h = r.height || (r.bottom - r.top);
    if (!(h > 1)) return false;
    if (!clip) return true;
    const ov = Math.min(r.bottom, clip.bottom) - Math.max(r.top, clip.top);
    return ov >= 0.5 * h;          // meia linha dentro = linha mostrada
  });
  out.why = visible.length ? 'painted' : 'no-painted-caption';
  out.rows = visible.map(function (line) {
    const items = Array.prototype.slice.call(
        line.querySelectorAll('.ytp-caption-segment')).map(function (seg) {
      const b = seg.getBoundingClientRect();
      return {text: (seg.textContent || ''), left: b.left, top: b.top,
              right: b.right, bottom: b.bottom};
    }).filter(function (it) { return it.text.trim().length > 0; });
    return {text: (items.map(function (i) { return i.text; }).join(' ')
                    .replace(/\s+/g, ' ').trim()), items: items};
  }).filter(function (r) { return r.text.length > 0; });
  return JSON.stringify(out);
})()
"""


#: QUEM ESTA' A TOCAR, lido DENTRO de cada aba candidata (uma resposta curta).
#: A lista de abas (`/json/list`) diz que existe um `watch`; nao diz se alguem
#: esta' a ver. MEDIDO no arranque do dono, 2026-11-04 12:15:15: 5 abas (3
#: "outras") e o attach recusou `reason=ambiguous` TRES vezes e desistiu, com o
#: video a tocar numa delas -- a legenda que ele viu era o ASR.
PLAYING_JS = r"""
(() => {
  const m = /[?&]v=([\w-]{11})/.exec(location.href || '');
  const v = document.querySelector('video');
  return JSON.stringify({
    videoId: m ? m[1] : '',
    t: v ? v.currentTime : null,
    paused: v ? v.paused : null,
    ended: v ? v.ended : null,
    dur: (v && isFinite(v.duration)) ? v.duration : null,
    rs: v ? v.readyState : null,
    vis: document.visibilityState || ''
  });
})()
"""

#: Tecto de abas sondadas por decisao. Uma decisao de boot nao pode custar uma
#: conexao por aba de um browser com trinta.
MAX_PROBE_TABS = 6

#: O espaco entre as DUAS leituras de `currentTime`. 120 ms e' mais do que um
#: `Runtime.evaluate` (10 ms medidos) e menos do que qualquer cambio de cue; o
#: que interessa nao e' o valor, e' a DIFERENCA entre os dois.
PLAYING_GAP_S = 0.12

#: Uma decisao de "quem toca" nao se repete a cada pergunta: a lista de abas e'
#: pedida de 2 em 2 s pelo resolvedor de id, e uma sonda por aba a esse ritmo
#: seria trabalho emprestado. Reutiliza-se a escolha por este tempo.
PLAYING_PROBE_TTL_S = 10.0


def _ws_eval(conn, expr, msg_id=1):
    """Um `Runtime.evaluate` numa ligacao ja' aberta; o valor, ou None."""
    conn.send(json.dumps({"id": msg_id, "method": "Runtime.evaluate",
                          "params": {"expression": expr,
                                     "returnByValue": True}}))
    while True:                       # ignora eventos, espera o id pedido
        raw = conn.recv()
        if not raw:
            raise ValueError('recv vazio')
        msg = json.loads(raw)
        if msg.get("id") == msg_id:
            return ((msg.get("result") or {}).get("result") or {}).get("value")


def _as_obj(value):
    """O payload JSON de uma aba -> dict, ou None. Nao inventa nada."""
    if isinstance(value, dict):
        return value
    try:
        data = json.loads(value)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _default_connect():
    """O transporte real: `websocket-client`, o mesmo do leitor."""
    import websocket
    return websocket.create_connection


def _arm_timeout(conn, timeout):
    """Tecto de tempo na ligacao, quando o objecto o sabe receber.

    `settimeout` num objecto que nao e' um socket (um duplo de teste, um
    wrapper do `websocket-client`) nao e' motivo para nao ler a aba: devolve
    False e a leitura seguinte faz-se com o prazo do `pump`.
    """
    try:
        conn.settimeout(timeout)
    except (AttributeError, OSError, ValueError):
        return False
    return True


def _drop(conn):
    """Fecha a ligacao; uma que ja' se fechou sozinha nao e' um erro."""
    if conn is None:
        return None
    try:
        conn.close()
    except (AttributeError, OSError):
        return None
    return conn


def _probe_one(tab, connect, timeout, gap_s):
    """UMA aba, duas leituras. O dicionario da sonda, ou None.

    Separada de `probe_tabs` para as abas poderem ser sondadas EM PARALELO: o
    corpo e' exactamente o mesmo, um `try` por aba, e o `connect` recebido e' o
    que o chamador deu (nunca um cliente novo por aba).
    """
    try:
        url = str(tab.get('webSocketDebuggerUrl') or '')
    except AttributeError:
        return None
    if not url:
        return None
    conn = None
    try:
        conn = connect(url, timeout=timeout)
        _arm_timeout(conn, timeout)
        first = _as_obj(_ws_eval(conn, PLAYING_JS, 1))
        time.sleep(gap_s)
        second = _as_obj(_ws_eval(conn, PLAYING_JS, 2))
    except Exception:                             # noqa: BLE001
        return None
    finally:
        _drop(conn)
    if not second:
        return None
    t1 = _float(second.get('t'))
    t0 = _float((first or {}).get('t'))
    return {'videoId': str(second.get('videoId') or ''),
            'paused': second.get('paused'),
            'ended': second.get('ended'),
            't0': t0, 't1': t1,
            'advance': (None if (t0 is None or t1 is None) else t1 - t0),
            'dur': _float(second.get('dur')),
            'rs': second.get('rs'),
            'visible': str(second.get('vis') or ''),
            'tab': tab}


def probe_tabs(tabs, connect=None, timeout=1.0, gap_s=PLAYING_GAP_S,
               parallel=True):
    """Sonda cada aba `watch` UMA vez (duas leituras) e devolve os numeros.

    Cada aba custa uma ligacao curta e duas leituras; uma aba que nao responde
    e' descartada em silencio (o `except` por aba e' o ponto: um alvo morto nao
    pode impedir a decisao sobre os vivos). `advance` e' `currentTime` da
    segunda leitura menos o da primeira -- e' ele que separa "a tocar" de
    "parado", e nao a bandeira `paused`, que a pagina de segundo plano pode
    mentir.

    AS ABAS SAO SONDADAS AO MESMO TEMPO (2026-11-05). Medido no log do dono
    com o video a tocar: `EXTERNAL_CAPTIONS_READ_MS ms=8609.0 phases={'target':
    0.0, 'source': 8609.0, ...}` -- 8,6 s dentro de UMA leitura, porque cada aba
    que nao responde custa uma ligacao ate' ao prazo (`timeout=1.0`) e as seis
    eram somadas uma atras da outra. `choose_playing` ordena por `advance` e
    desempata pelo id (nunca pela posicao na lista), por isso a ORDEM das sondas
    nao decide nada: o resultado sai na ordem das abas, com as mortas fora,
    como antes. `parallel=False` existe para o braco que MEDE a diferenca.
    """
    connect = connect or _default_connect()
    items = []
    for tab in list(tabs or ())[:MAX_PROBE_TABS]:
        items.append(tab)
    if not items:
        return []
    if not parallel or len(items) == 1:
        return [p for p in (_probe_one(t, connect, timeout, gap_s)
                            for t in items) if p]
    # Um fio por aba, no maximo `MAX_PROBE_TABS`: o `gap_s` de cada uma corre em
    # paralelo com a ligacao das outras, e o custo total passa a ser o da aba
    # MAIS LENTA em vez da soma.
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(items),
                            thread_name_prefix='yt-probe') as pool:
        futures = [pool.submit(_probe_one, t, connect, timeout, gap_s)
                   for t in items]
        out = []
        for fut in futures:
            try:
                probe = fut.result()
            except Exception:                     # noqa: BLE001
                probe = None
            if probe:
                out.append(probe)
        return out


def is_real_player(probe):
    """A aba tem um JOGADOR com linha temporal? -- medido, nao suposto.

    MEDIDO 2026-11-05 14:0x no Chrome do dono, seis abas `watch` abertas:

        ieTgYlbWjMM  paused=True   t=539.98  rs=4   linhas do player: 2
        CXvncR7v66o  paused=True   t=25.00   rs=4   (legenda DESLIGADA, cc=false)
        ea20SBGR8ao  paused=True   t=978.15  rs=4   linhas do player: 1
        ICGa6m4E_cA  paused=False  t=0.0     rs=0   nenhuma
        LHxOG65r12w  paused=False  t=0.0     rs=0   nenhuma
        oUIt-EqN3j0  paused=False  t=0.0     rs=0   nenhuma

    As tres ultimas sao abas DESCARTADAS pelo Chrome: nao ha' media, logo nao ha'
    legenda nenhuma para ler -- e `paused=false`, que a regra antiga lia como
    "a tocar", e' o que uma aba sem video responde. Era exactamente assim que o
    Sotto ficou 221 leituras preso em `ICGa6m4E_cA` com `why=no-painted-caption`
    e o dono a ver o ASR no ecra: *"o youtube nao ta 1:1. ta usando a legenda dos
    modelos"*. `dur` nao serve de discriminador: veio `None` nas SEIS.

    O que separa e' a LINHA TEMPORAL: um jogador real tem `currentTime > 0` ou
    avancou entre as duas leituras. `rs` (readyState) e' a segunda testemunha
    quando o campo chega (o `EXTRACT_JS` do laco publica-o; a sonda passou a
    publica-lo tambem).
    """
    if not isinstance(probe, dict):
        return False
    if probe.get('rs') == 0:
        return False
    t1 = _float(probe.get('t1'))
    adv = _float(probe.get('advance')) or 0.0
    return bool((t1 or 0.0) > 0.0 or adv > 0.0)


def choose_target(probes, previous='', window_title='', declared=''):
    """(video_id, porque) -- QUE ABA, decidido pela evidencia de cada uma.

    O dono, verbatim (2026-11-05): *"dumb picking then. do it properly. do it
    the best design. should attach to current tab or last tab"*, e depois *"or
    better then that"*. A ordem abaixo e' a melhor que a medicao sustenta, e
    cada degrau tem a sua testemunha -- nao ha' `ambiguous` que dure:

      0. **`no-player`** quando NENHUMA aba tem jogador (`is_real_player`).
         Melhor nao responder do que prender-se a uma aba descartada.
      1. **`window-title`** -- a ABA QUE ELE ESTA' A VER: o titulo da janela em
         primeiro plano casa com o titulo da aba (exacto, depois parcial). E' a
         testemunha mais directa do "current tab", e vem do Win32 sem custo.
      2. **`declared`** -- o id que o shell declarou, AGORA VERIFICADO: so' vale
         se a aba dele tiver jogador.
      3. **`playing`** -- o que AVANCOU o `currentTime` entre as duas leituras
         (o video que ele esta' a ouvir). Desempate pelo id, que e' estavel.
      4. **`sticky-last`** -- o ultimo adotado, se ainda tiver jogador. Duas abas
         a tocar nao podem fazer o ecra trocar sozinho.
      5. **`only-player`** / **`paused-loaded`** -- ele poe o video EM PAUSA (as
         tres abas reais de hoje estavam): a linha pintada de um video pausado
         ainda e' a legenda do YouTube, e e' melhor do que a de outro video.
         Entre varios pausados fica o de linha temporal mais avancada.
    """
    usable = [p for p in (probes or ()) if is_real_player(p)
              and str(p.get('videoId') or '')]
    if not usable:
        return '', 'no-player'
    prev = str(previous or '')
    want = str(window_title or '').strip().lower()
    if want:
        exact = [p for p in usable
                 if str(p.get('videoId') or '')
                 and str((p.get('tab') or {}).get('title') or '').strip().lower() == want]
        if len(exact) == 1:
            return str(exact[0]['videoId']), 'window-title'
        partial = [p for p in usable
                   if (str((p.get('tab') or {}).get('title') or '').strip().lower()
                       and str((p.get('tab') or {}).get('title') or ''
                               ).strip().lower() in want)]
        if len(partial) == 1:
            return str(partial[0]['videoId']), 'window-title-partial'
    live = [p for p in usable
            if not p.get('paused') and not p.get('ended')
            and (_float(p.get('advance')) or 0.0) > 0.0]
    if live:
        # O JA' ADOTADO QUE AINDA TOCA FICA (2026-10-30, mantido em 2026-11-05
        # pela ordem do dono -- *"current tab or last tab"*). Duas abas a tocar
        # ao mesmo tempo (picture-in-picture, dois separadores) nao podem fazer
        # o ecra trocar de video sozinho: um ecra que alterna e' pior do que um
        # ecra parado. MEDIDO pela arm `duas-a-tocar-decide-e-nao-tropeca`, que
        # ficou vermelha quando `playing` passou a' frente de `sticky-last`.
        if prev and any(str(p.get('videoId') or '') == prev for p in live):
            return prev, 'sticky-last'
        live.sort(key=lambda p: (-(_float(p.get('advance')) or 0.0),
                                 str(p.get('videoId') or '')))
        return str(live[0]['videoId']), 'playing'
    if declared:
        for p in usable:
            if str(p.get('videoId') or '') == str(declared):
                return str(declared), 'declared'
    # O DECLARADO VEM DEPOIS DO QUE TOCA (2026-11-05). O id que o shell
    # declara e' uma CRENCA, e ja' se mediu errada duas vezes (164 leituras
    # presas num `m_bJQ4G1Ht8` que nao estava aberto; hoje 221 leituras numa
    # aba DESCARTADA). Um `currentTime` a andar e' evidencia; a crenca do
    # shell so' decide quando nao ha' nada a tocar -- e mesmo entao so' se
    # a aba dele tiver jogador (`usable`).

    if prev and any(str(p.get('videoId') or '') == prev for p in usable):
        return prev, 'sticky-last'
    if len(usable) == 1:
        return str(usable[0]['videoId']), 'only-player'
    usable.sort(key=lambda p: (-(_float(p.get('t1')) or 0.0),
                               str(p.get('videoId') or '')))
    return str(usable[0]['videoId']), 'paused-loaded'


def choose_playing(probes, previous=''):
    """Compatibilidade: a regra antiga era "quem toca".

    Fica como um `choose_target` sem janela nem id declarado -- os chamadores e
    os oraculos antigos continuam a executar a MESMA funcao, com a correccao de
    que uma aba descartada nunca entra na lista (`is_real_player`). O nome antigo
    nao decide nada a mais: `choose_target` e' o dono da regra.
    """
    return choose_target(probes, previous)


def pick_playing(tabs, previous='', connect=None, timeout=1.0,
                 gap_s=PLAYING_GAP_S, window_title='', declared=''):
    """(aba, video_id, porque) -- a aba com jogador, ou `(None, '', motivo)`.

    UMA sonda por aba (duas leituras em paralelo, ~1,3 s no pior caso) responde
    a pergunta inteira, e a resposta vem de `choose_target`. Quem chama guarda o
    resultado por `PLAYING_PROBE_TTL_S`: enquanto a escolha vale, a sonda nao se
    repete e o custo e' zero.
    """
    probes = probe_tabs(tabs, connect=connect, timeout=timeout, gap_s=gap_s)
    vid, why = choose_target(probes, previous, window_title, declared)
    if not vid:
        return None, '', why
    for p in probes:
        if str(p.get('videoId') or '') == vid:
            return p.get('tab'), vid, why
    return None, '', why


def parse_snapshot(payload, now=None):
    """A resposta JSON da pagina -> o formato publico, ou None se nao presta.

    Puro e testavel sem Chrome: e' aqui que se decide o que conta como linha.
    `rows` e `items` sao reconstruidos do payload e nao se confia em nada que nao
    tenha texto -- uma linha sem filhos nao e' uma linha.
    """
    try:
        data = json.loads(payload)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    rows = []
    items = []
    for line in data.get("rows") or ():
        if not isinstance(line, dict):
            continue
        text = " ".join(str(line.get("text") or "").split())
        if not text:
            continue
        kids = []
        for kid in line.get("items") or ():
            if not isinstance(kid, dict):
                continue
            body = " ".join(str(kid.get("text") or "").split())
            if not body:
                continue
            try:
                item = {"text": body,
                        "left": int(float(kid.get("left") or 0)),
                        "top": int(float(kid.get("top") or 0)),
                        "right": int(float(kid.get("right") or 0)),
                        "bottom": int(float(kid.get("bottom") or 0))}
            except (TypeError, ValueError):
                continue
            kids.append(item)
        if not kids:
            continue
        rows.append(text)
        items.extend(kids)
    segs = [" ".join(str(x).split()) for x in (data.get("segs") or ())
            if str(x or "").strip()]
    return {"stamp": float(now if now is not None else time.monotonic()),
            "segs": segs,
            "videoId": str(data.get("videoId") or ""),
            "t": (_float(data.get("t"))),
            "paused": (None if data.get("paused") is None else bool(data.get("paused"))),
            "rate": _float(data.get("rate")),
            # O JOGADOR EXISTE NESTA ABA? (2026-11-05) `rs` e' o `readyState` do
            # `<video>`: 0 = nenhuma media carregada, que e' o que uma aba
            # DESCARTADA pelo Chrome responde. O laco usa este campo para NAO
            # ficar preso numa aba sem jogador (medido: 221 leituras em
            # `ICGa6m4E_cA`, `rs=0`, zero linhas, e o ASR no ecra do dono).
            "rs": data.get("rs"),
            "title": str(data.get("title") or ""),
            "rows": rows, "items": items,
            "why": str(data.get("why") or ("painted" if rows else "no-painted-caption"))}


def _float(value):
    """Um numero do payload, ou None. Nunca inventa zero."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _probe_reason(exc):
    """O NOME HONESTO de uma falha do `/json/list` (2026-11-05, MEDIDO).

    O laco desta maquina dizia `state=port-closed` para QUALQUER excecao da
    sonda -- inclusive um `urlopen` que estourou o prazo de 1,5 s porque a
    maquina estava carregada. Medido na instancia viva (pid 41764, 17:52):
    `port-closed` -> `attached` -> `slow (WebSocketTimeoutException)` ->
    `reconnect (ValueError)` -> `port-closed` a cada ~10 s, com a legenda do
    YouTube a ficar sem leitura nos intervalos. A porta NAO estava fechada: um
    `/json/list` que nao responde a tempo e' `probe-timeout`, e um erro de
    protocolo e' `probe-failed (<Name>)`. So' a recusa de ligacao e' a porta.
    """
    if isinstance(exc, ConnectionRefusedError):
        return "port-closed"
    reason = getattr(exc, "reason", None)
    for cand in (exc, reason):
        name = type(cand).__name__
        if name in ("timeout", "TimeoutError", "socket.timeout"):
            return "probe-timeout"
    return "probe-failed (%s)" % type(exc).__name__


def list_targets(port=DEFAULT_PORT, timeout=3.0):
    """As abas do YouTube e quantas outras existem -- sem ler as outras."""
    with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % int(port),
                                timeout=timeout) as handle:
        data = json.load(handle)
    youtube = []
    others = 0
    for tab in data or ():
        if tab.get("type") != "page":
            continue
        url = str(tab.get("url") or "")
        if _WATCH in url:
            youtube.append(tab)
        elif "youtube.com" in url:
            continue          # a home, um resultado: nao tem legenda de video
        else:
            others += 1
    return youtube, others


def foreground_source(hwnd, tab_video_id):
    """A fonte da legenda no arranque: com ou SEM jogador em primeiro plano.

    MEDIDO na sessao do dono de 2026-11-04, 09:57:24 -> 09:58:29: o laco das
    legendas externas perguntava a JANELA em primeiro plano primeiro, e sem
    jogador nenhum fazia `return` ali mesmo. Resultado no log dele:
    `YOUTUBE_TICK_MS src='?' vid='' cdp_age_ms=? rows=? why=''` durante os
    65 s inteiros, com o Chrome aberto num video do YouTube -- a legenda que
    ele viu era o ASR, nao a faixa do player, e o dono descreveu o defeito
    como *"nao ta acontecendo nada"*. Uma aba `youtube.com/watch` na lista da
    CDP e' prova POSITIVA de que ha um player a ser lido, e essa prova nao
    depende de quem esta' em primeiro plano: `/json/list` e' HTTP.

    Devolve `'external:youtube:foreground'` quando a janela foi resolvida,
    `'external:youtube'` quando so' a aba prova a fonte, e `''` quando nem uma
    nem outra -- nesse caso quem pinta a legenda continua a ser o ASR.
    """
    if hwnd:
        return 'external:youtube:foreground'
    return 'external:youtube' if str(tab_video_id or '').strip() else ''


def pick_target(tabs, video_id="", window_title=""):
    """(aba, motivo). Uma aba so'; `ambiguous` quando nao se pode decidir.

    COM DUAS ABAS `watch` ABERTAS (MEDIDO 2026-11-03 na maquina do dono,
    `state=ambiguous` enquanto a legenda esteve parada) a escolha NAO precisa
    de id nenhum: o titulo da JANELA em primeiro plano esta' o tempo todo na
    mao do chamador (Win32, microssegundos) e diz qual daquelas abas ele esta'
    a ver. O id continua a ser a chave mais forte; o titulo resolve o caso
    comum sem custo nenhum, e so' o que sobra fica `ambiguous`.
    """
    if video_id:
        named = [t for t in tabs if video_id in str(t.get("url") or "")]
        if named:
            return named[0], "named"
        return None, "video-not-open"
    if not tabs:
        return None, "no-youtube-tab"
    want = str(window_title or "").strip().lower()
    if want:
        exact = [t for t in tabs
                 if str(t.get("title") or "").strip().lower() == want]
        if len(exact) == 1:
            return exact[0], "window-title"
        partial = [t for t in tabs
                   if str(t.get("title") or "").strip().lower()
                   and str(t.get("title") or "").strip().lower() in want]
        if len(partial) == 1:
            return partial[0], "window-title-partial"
    if len(tabs) > 1:
        return None, "ambiguous"
    return tabs[0], "only-tab"


#: O ARRANQUE PEDE A LIGACAO, E PEDE-A COM TECTO (2026-11-04). Medido no log
#: do dono: a app subiu as 10:06:36 e a porta so' ficou `attached` as 10:06:40
#: -- nao por o Chrome estar fechado, mas porque o pedido de attach morava no
#: PRIMEIRO TICK do laco da legenda, que por sua vez so' existia depois de o
#: WebView2 arrancar. As tentativas sao POUCAS e CURTAS (ver abaixo); quem nao
#: conseguiu continua a tentar dentro da thread (`RETRY_S`), agora com o motivo
#: escrito a cada tentativa.
#: TRES tentativas curtas, nao quatro longas (MEDIDO 2026-11-04): um
#: `/json/list` contra uma porta FECHADA gasta 2,0 s de `URLError` nesta maquina,
#: e quatro dessas mais as esperas seguravam o arranque ~10 s -- o remedio a
#: fazer o mesmo estrago que a doenca. Com 0,4 s de prazo por sonda o pior caso
#: e' ~1,45 s; o Chrome que ainda esta' a abrir a porta e' recuperado pela thread
#: (`RETRY_S`), que agora diz o motivo de cada tentativa.
BOOT_ATTACH_ATTEMPTS = 3
BOOT_ATTACH_DELAY_S = 0.25
BOOT_ATTACH_TIMEOUT_S = 0.4


def video_id_from_url(url):
    """O `v=` de um URL de `watch` -- `''` quando nao ha' nenhum.

    Uma funcao e nao um par de `split` em cada sitio: o dono le `video_id=` no
    log de attach e o numero tem de ser o MESMO que a foto publica.
    """
    text = str(url or "")
    if "v=" not in text:
        return ""
    return text.split("v=", 1)[1].split("&", 1)[0]


def boot_attach(port=None, attempts=BOOT_ATTACH_ATTEMPTS,
                delay=BOOT_ATTACH_DELAY_S, log=None, sleep=None,
                timeout=BOOT_ATTACH_TIMEOUT_S, previous='', connect=None):
    """(ok, motivo) -- pede a ligacao a' aba do YouTube no ARRANQUE, com tecto.

    A pergunta e' a MESMA do laco (`list_targets` + `pick_target`), feita aqui
    sem janela em primeiro plano, sem evento de painel e sem esperar por tick
    nenhum: `/json/list` e' HTTP. Cada tentativa escreve UMA linha -- a que
    falhou com o motivo dela --, para que "nao ligou" deixe de ser um silencio
    e passe a ser um numero (`YOUTUBE_CDP_BOOT_ATTACH`).

    E QUANDO A LISTA NAO DECIDE, QUEM DECIDE E' O VIDEO A TOCAR (2026-11-04).
    MEDIDO no arranque do dono, 12:15:15: 5 abas, `pick_target` sem id e sem
    titulo de janela -> `reason=ambiguous` nas TRES tentativas ->
    `YOUTUBE_CDP_BOOT_ATTACH_DEFERRED`, e o ecra mostrou `carregando modelo…`
    com o video a tocar numa daquelas abas. `pick_playing` sonda as abas e
    escolhe a que tem `currentTime` a andar (`choose_playing`), com
    `sticky-last` para o id ja' adotado; so' `no-playing` quando nenhuma toca,
    e essa e' uma resposta, nao um `ambiguous` repetido.

    `ok` diz que ha' uma aba `watch` com `webSocketDebuggerUrl` para onde a
    thread se pode ligar; nao abre o WebSocket (isso e' `CdpCaptionSource`).
    """
    log = log or (lambda _m: None)
    sleep = sleep or time.sleep
    port = resolve_port(port)
    reason = "not-tried"
    for attempt in range(1, max(1, int(attempts)) + 1):
        t0 = time.monotonic()
        target = None
        _pick = ""
        _picked_why = ""
        try:
            tabs, others = list_targets(port, timeout=timeout)
        except Exception as exc:              # noqa: BLE001
            reason = _probe_reason(exc)
            _extra = "err=%s" % type(exc).__name__
        else:
            _extra = "tabs=%d others=%d" % (len(tabs), others)
            target, reason = pick_target(tabs, "", "")
            if target is None:
                # A LISTA NAO DECIDE -> O VIDEO A TOCAR DECIDE.
                target, _pick, _picked_why = pick_playing(
                    tabs, previous, connect=connect, timeout=timeout)
                if target is not None:
                    reason = _picked_why or "playing"
                else:
                    reason = "no-playing"
            if target is not None and not target.get("webSocketDebuggerUrl"):
                target, reason = None, "no-ws-url"
        ms = (time.monotonic() - t0) * 1000.0
        if target is not None:
            log("YOUTUBE_CDP_BOOT_ATTACH attempt=%d/%d ok=true reason=%s "
                "pick=%s why=%s port=%d ms=%.0f %s"
                % (attempt, attempts, reason, _pick or '-',
                   _picked_why or '-', port, ms, _extra))
            return True, reason
        log("YOUTUBE_CDP_BOOT_ATTACH attempt=%d/%d ok=false reason=%s "
            "pick=%s why=%s port=%d ms=%.0f %s"
            % (attempt, attempts, reason, '-', _picked_why or '-', port, ms,
               _extra))
        if attempt < max(1, int(attempts)):
            sleep(delay)
    return False, reason


# O CUSTO DE PERGUNTAR A ABA. Medido 2026-11-03: um `/json/list` de 1125 ms
# dentro do laco de leitura; trocar de video e' raro, perder quadros nao e'.
_TID_SLOW_MS = 500.0
_TID_SLOW_TTL_S = 10.0

def adopt_decision(declared, seen, declared_open):
    """O ID DECLARADO FILTRA A ESCOLHA DA ABA, NAO A LEITURA (2026-11-04).

    Devolve `(acao, porque)` com `acao` em `same` | `adopt` | `refuse`:

      `same`   -- nada a decidir: sem id declarado, ou a foto e' do proprio id.
      `adopt`  -- a foto e' de OUTRO video E o declarado nao esta' aberto: a aba
                  navegou e quem manda e' ela. MEDIDO no log do dono, 10:16:17:
                  `wrong-video (vDmjw-c_R2k)` -> `state=ambiguous` -> **13 min
                  sem uma linha** (`YOUTUBE_TICK_MS src='?' rows=0
                  cdp_age_ms=789250`) com a faixa do player a pintar na pagina.
      `refuse` -- a foto e' de outro video E o declarado AINDA esta' aberto: ha'
                  duas abas e o dono apontou para uma -- ler a outra e' o unico
                  erro que poe a legenda de um video no ecra de outro.

    Pura de proposito: `_main/youtube-cdp-source-oracle.py` executa ESTA funcao
    e o laco limit-se a obedecer, para a regra poder ser provada sem Chrome.
    """
    declared = str(declared or '')
    seen = str(seen or '')
    if not declared or not seen:
        return 'same', 'no-declared'
    if seen == declared:
        return 'same', 'same-video'
    if not declared_open:
        return 'adopt', 'declared-closed'
    return 'refuse', 'wrong-video'


class CdpCaptionSource:
    """Le as linhas que o player desenha, em segundo plano, pela CDP.

    Uma thread, uma ligacao, uma leitura a cada `poll_s`. `snapshot()` e' barato
    e nunca bloqueia: devolve a ultima foto boa (ou None). Tudo o que pode falhar
    (porta fechada, aba fechada, Chrome a reabrir) esta' dentro da thread, e a
    aplicacao simplesmente continua com a UIA.
    """

    def __init__(self, port=None, poll_s=POLL_S, log=None):
        self.port = resolve_port(port)
        self.poll_s = float(poll_s)
        self._log = log or (lambda _m: None)
        self._lock = threading.Lock()
        self._snap = None
        self._last_use = 0.0
        self._stop = threading.Event()
        self._thread = None
        self._note = ""
        self._reads = 0
        self._errors = 0
        self._last_error = ""
        self._video_id = ""
        #: QUEM TOCA ja' foi decidido (2026-11-04): o id da escolha por
        #: `choose_playing`, para `sticky-last` na leitura seguinte, e a hora
        #: dessa escolha (a sonda por aba e' cara e tem TTL).
        self._playing_pick = ""
        self._playing_pick_cache = None
        #: O titulo da janela que o dono esta' a ver. Com duas abas `watch`, e'
        #: isto -- nao o id -- que decide qual delas ler (`pick_target`).
        self._window_title = ""

        #: Ha' ligacao CDP agora? Decide a espera entre tentativas; e a IDADE da
        #: ultima falha de attach e' o que impede `target_video_id` de gastar a
        #: sonda de alvos contra uma porta morta. Ver `_run`/`_connect`.
        self._attached = False
        self._retry_s = RETRY_S
        self._attach_failed_at = None

    # -- ciclo de vida ----------------------------------------------------
    def set_video_id(self, video_id):
        """Qual video o Sotto DECLARA ler. Com mais de uma aba aberta, so' esta."""
        self._video_id = str(video_id or "")

    def set_window_title(self, title):
        """Qual janela o dono esta' a ver (o que resolve duas abas `watch`)."""
        self._window_title = str(title or "")

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return self
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="yt-cdp-source",
                                        daemon=True)
        self._thread.start()
        return self

    def _declared_closed(self):
        """True quando o video DECLARADO nao esta' em aba `watch` nenhuma.

        A pergunta tem de ser respondida pela LISTA de abas (HTTP, barato) e nao
        pela foto: a foto e' o que estava a envelhecer quando o laco ficou preso.
        Falha de leitura devolve False -- "nao consegui ver" nunca e' "nao esta'
        aberto", porque adotar o id errado e' por a legenda de um video no ecra
        de outro (o unico erro que `_choose` existe para impedir).
        """
        vid = str(getattr(self, '_video_id', '') or '')
        if not vid:
            return False
        try:
            tabs, _others = list_targets(self.port)
        except Exception:                 # noqa: BLE001
            return False
        for tab in tabs or ():
            try:
                url = str(tab.get('url') or '')
            except Exception:             # noqa: BLE001
                continue
            if vid in url:
                return False
        return True

    def _choose(self, tabs):
        """(aba, motivo) -- A SONDA DECIDE, e a lista de URLs so' desempata.

        O DEFEITO MEDIDO (2026-11-05 14:0x) que este metodo tinha: a escolha era
        a URL primeiro -- `video_id in url` --, e o id declarado apontava para
        `ICGa6m4E_cA`, uma aba DESCARTADA pelo Chrome (`rs=0`, `t=0`, sem media
        nenhuma). A sonda so' era consultada DEPOIS de a escolha por URL falhar,
        por isso nunca era: 221 leituras com `why=no-painted-caption` e o dono a
        ver a legenda do MODELO no ecra -- *"o youtube nao ta 1:1. ta usando a
        legenda dos modelos"*.

        Agora a evidencia vem primeiro (`choose_target`: janela em primeiro
        plano -> id declarado COM jogador -> a tocar -> ultimo adotado ->
        pausado carregado) e uma aba sem linha temporal e' descartada por
        `is_real_player`, seja qual for o URL. O custo continua rate-limited
        (`PLAYING_PROBE_TTL_S`): uma sonda por TTL, zero enquanto a escolha vale.

        A lista de URLs fica como ULTIMO recurso -- quando a sonda nao responde
        (porta fechada, aba muda), `pick_target` ainda pode nomear uma aba, e uma
        tentativa vale mais do que nenhuma.
        """
        tab, vid, why = self._playing_pick_for(tabs)
        if tab is not None:
            self._playing_pick = vid or self._playing_pick
            self._note = str(why)
            self._log('YOUTUBE_TARGET pick=%s why=%s declared=%s tabs=%d'
                      % (vid or '-', why, self._video_id or '-', len(tabs or ())))
            return tab, why
        target, why2 = pick_target(tabs, self._video_id, self._window_title)
        if target is not None:
            self._note = 'probe:%s fallback:%s' % (why, why2)
            self._log('YOUTUBE_TARGET fallback pick=%s why=%s probe=%s tabs=%d'
                      % (video_id_from_url(target.get('url') or '') or '-',
                         why2, why, len(tabs or ())))
            return target, why2
        # O ID DECLARADO NAO ESTA' ABERTO: QUEM MANDA SAO AS ABAS (2026-11-04).
        # Sem esta queda o laco fecha-se em si mesmo -- o id filtra a escolha,
        # sem escolha nao ha' foto, e sem foto o id nunca se cura. Medido: 164
        # linhas com `source=other-video` e 13 min de ecra vazio.
        if target is None and self._video_id:
            target, why = pick_target(tabs, '', self._window_title)
            if target is not None:
                why = 'stale-declared:' + str(why)
        if target is not None:
            self._note = why
            self._log('YOUTUBE_TARGET stale pick=%s why=%s declared=%s tabs=%d'
                      % (video_id_from_url(target.get('url') or '') or '-',
                         why, self._video_id or '-', len(tabs or ())))
            return target, why
        self._note = str(why or why2)
        return None, self._note

    def _playing_pick_for(self, tabs):
        """(aba, id, motivo) da escolha por 'a tocar', com cache curta.

        Uma escolha feita ha' menos de `PLAYING_PROBE_TTL_S` e que ainda esteja
        na lista de abas vale sem sonda nenhuma -- o resolvedor de id pergunta a
        lista de 2 em 2 s e uma sonda por aba a esse ritmo seria trabalho
        emprestado ao dono (a queixa e' sempre a mesma: o PC a travar).
        """
        now = time.monotonic()
        cached = getattr(self, '_playing_pick_cache', None)
        if cached and now - cached[0] < PLAYING_PROBE_TTL_S:
            _vid = cached[1]
            if _vid:
                for tab in tabs or ():
                    if _vid in str(tab.get('url') or ''):
                        return tab, _vid, cached[2]
        try:
            tab, vid, why = pick_playing(
                tabs, getattr(self, '_playing_pick', '') or '',
                connect=getattr(self, '_probe_connect', None),
                window_title=getattr(self, '_window_title', '') or '',
                declared=getattr(self, '_video_id', '') or '')
        except Exception as exc:              # noqa: BLE001
            self._log('YOUTUBE_PLAYING_PICK_FAILED error=%r' % (exc,))
            return None, '', 'probe-failed'
        self._playing_pick_cache = (now, vid, why)
        return tab, vid, why

    def stop(self):
        self._stop.set()

    def stats(self):
        with self._lock:
            return {"reads": self._reads, "errors": self._errors,
                    "last_error": self._last_error, "note": self._note}

    # -- leitura ----------------------------------------------------------
    def snapshot(self, max_age=0.6):
        """A ultima foto, se for RECENTE. Sem foto recente devolve None."""
        self._last_use = time.monotonic()
        with self._lock:
            snap = self._snap
        if snap is None:
            return None
        if time.monotonic() - snap["stamp"] > max_age:
            return None
        return snap

    def target_video_id(self):
        """O id da aba que `pick_target` escolhe AGORA ("" se nao decidir).

        E' a resposta que o caso de TRES abas `watch` pedia (medido 2026-11-03:
        `stats={'reads': 0, 'note': 'ambiguous'}` por minutos, e a legenda parada,
        enquanto a fonte esperava um id que ninguem lhe dava). O id sai do URL da
        aba escolhida pelo TITULO DA JANELA -- nada de UIA, nada de varrer a
        arvore. Uma chamada HTTP por `cache_s`, nao por tick.
        """
        now = time.monotonic()
        # SEM LIGACAO RECENTE NAO HA' ALVO A SONDAR (2026-11-05, MEDIDO na
        # instancia viva pid 20236). Com o browser sem porta de depuracao esta
        # chamada gastava **2000 ms** de 10 em 10 s -- o log diz
        # `YOUTUBE_TARGET_SLOW ms=2000 vid=- ttl_s=10` em serie -- para
        # perguntar a um porto morto que abas existem, e a resposta nao podia
        # ser outra. A falha de attach ja' e' um facto datado (`_attach_log`):
        # enquanto ela for recente e nao houver ligacao, a resposta e' de graca.
        # Uma fonte sem fio (`_run` nunca correu -- duplos de teste) nao tem
        # hora de falha e segue o caminho antigo, sem mudanca de comportamento.
        _failed = getattr(self, '_attach_failed_at', None)
        if (_failed is not None and not getattr(self, '_attached', False)
                and now - _failed < 30.0):
            # NADA DE CACHE AQUI: a hora da falha e' o unico estado, e escrever
            # um '' no cache de 2 s faria a primeira leitura depois de a porta
            # voltar a responder devolver o vazio antigo.
            return ''
        ttl = float(getattr(self, '_tid_ttl', 2.0) or 2.0)
        cached = getattr(self, '_tid_cache', None)
        if cached and now - cached[0] < ttl:
            return cached[1]
        vid = ''
        t0 = time.monotonic()
        try:
            tabs, _others = list_targets(self.port)
            target, why = self._choose(tabs)
            if target is None:
                self._note = str(why)
            if target is not None:
                url = str(target.get('url') or '')
                if 'v=' in url:
                    vid = url.split('v=', 1)[1].split('&', 1)[0]
        except Exception:                 # noqa: BLE001
            vid = ''
        # A CHAMADA QUE COME O TICK (2026-11-03, MEDIDO): `EXTERNAL_CAPTIONS_READ_MS`
        # publicou `phases={'vid': 1125.0}` com todas as outras a 0,0 -- um
        # `/json/list` de 1,1 s dentro do laco de leitura, e o laco perde os
        # quadros que caem nessa janela. A aba do dono troca de video de vez em
        # quando, nunca 12 vezes por minuto: quando a chamada passa de
        # `_TID_SLOW_MS`, o cache estica para `_TID_SLOW_TTL_S` e o custo vai ao log.
        cost_ms = (time.monotonic() - t0) * 1000.0
        if cost_ms > _TID_SLOW_MS:
            self._tid_ttl = _TID_SLOW_TTL_S
            self._log('YOUTUBE_TARGET_SLOW ms=%.0f vid=%s ttl_s=%.0f'
                      % (cost_ms, vid or '-', _TID_SLOW_TTL_S))
        else:
            self._tid_ttl = 2.0
        self._tid_cache = (now, vid)
        return vid

    def snapshot_age(self):
        """Quantos segundos tem a foto em maos (`None` = nao ha' foto nenhuma).

        Existe porque um APAGAO nao se diagnostica por ausencia de linhas: medido
        2026-11-03 no log do dono, 40 s sem `YT_FRAME` com o video a andar, e nada
        que dissesse se a culpa era da foto velha ou de outra coisa.
        """
        with self._lock:
            snap = self._snap
        if snap is None:
            return None
        return time.monotonic() - snap["stamp"]

    def _publish(self, snap, note=None):
        with self._lock:
            if snap is not None:
                self._snap = snap
                self._reads += 1
            if note is not None and note != self._note:
                self._note = note
                self._log("YOUTUBE_CDP_SOURCE state=%s" % note)

    def _error(self, exc):
        with self._lock:
            self._errors += 1
            self._last_error = "%s: %s" % (type(exc).__name__, exc)

    # -- a thread ---------------------------------------------------------
    def _run(self):
        try:
            import websocket            # websocket-client
        except Exception as exc:        # noqa: BLE001
            self._publish(None, "no-websocket-client (%s)" % type(exc).__name__)
            return
        conn = None
        while not self._stop.is_set():
            if time.monotonic() - self._last_use > IDLE_STOP_S:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:   # noqa: BLE001
                        pass
                    conn = None
                    self._publish(None, "idle-closed")
                self._stop.wait(1.0)
                continue
            if conn is None:
                self._attached = False
                conn = self._connect(websocket)
                if conn is None:
                    # A ESPERA DOBRA ATE' ATTACH_RETRY_MAX_S (2026-11-05). Cada
                    # falha custou ATTACH_PROBE_TIMEOUT_S de um prazo que nao
                    # podia dar outra coisa enquanto nenhum browser expunha a
                    # porta; repetir a 3,5 s e' 43 % de um fio a fazer nada.
                    _wait = float(getattr(self, '_retry_s', RETRY_S) or RETRY_S)
                    self._stop.wait(_wait)
                    self._retry_s = min(ATTACH_RETRY_MAX_S, _wait * 2.0)
                    continue
                self._attached = True
                self._retry_s = RETRY_S
                self._attach_failed_at = None
            t0 = time.monotonic()
            try:
                # O ID DE CADA PEDIDO E' UNICO (2026-11-05, MEDIDO). Com o id
                # fixo em 1, a resposta de um pedido cujo `recv` estourou o
                # prazo era aceite no tick seguinte como se fosse a deste --
                # uma foto de um segundo antes publicada como se fosse agora.
                # com um id que cresce, a resposta atrasada cai no descarte
                # abaixo e a foto publicada e' sempre a do pedido corrente.
                self._msg_id = int(getattr(self, '_msg_id', 0)) + 1
                _want = self._msg_id
                conn.send(json.dumps({"id": _want, "method": "Runtime.evaluate",
                                      "params": {"expression": EXTRACT_JS,
                                                 "returnByValue": True}}))
                payload = None
                _slow = None
                while True:                       # ignora eventos, espera o id
                    # UMA RESPOSTA ATRASADA NAO E' LIGACAO MORTA (2026-11-03,
                    # MEDIDO no dono: com 1 s de prazo a fonte respondia
                    # `slow (WebSocketTimeoutException)` -> `reconnect` ->
                    # `attached` a cada 3 s, ou seja re-ligava ao Chrome
                    # eternamente e nunca publicava foto). A pagina de uma aba em
                    # SEGUNDO PLANO pode levar segundos a responder ao
                    # `Runtime.evaluate`: a ligacao fica, o tick seguinte
                    # pergunta outra vez, e o estado diz que a pagina esta'
                    # lenta -- nao que a porta fechou.
                    #
                    # E O `break` QUE SEGUIA O PRAZO ANULAVA ISSO (2026-11-05,
                    # MEDIDO na instancia viva, pid 41764): `break` deixava
                    # `payload=None`, `parse_snapshot(None)` devolvia None,
                    # `raise ValueError("payload sem forma")` e a guarda de
                    # timeout do `except` exterior -- que existe exatamente para
                    # NAO fechar a ligacao -- nunca era alcancada, porque o
                    # `ValueError` nao e' um timeout. A sequencia no log da app
                    # era `slow (WebSocketTimeoutException)` -> `reconnect
                    # (ValueError)` -> `port-closed` -> `attached` a cada ~10 s,
                    # com a legenda do YouTube sem leitura nos intervalos.
                    try:
                        raw = conn.recv()
                    except Exception as exc:          # noqa: BLE001
                        _slow = exc
                        break
                    if not raw:
                        raise ValueError('recv vazio')
                    msg = json.loads(raw)
                    if msg.get("id") == _want:
                        payload = ((msg.get("result") or {})
                                   .get("result") or {}).get("value")
                        break
                    # RESPOSTA DE UM PEDIDO ANTERIOR: descarta e espera a deste.
                if _slow is not None:
                    self._publish(None, 'slow (%s)' % type(_slow).__name__)
                    self._slow_streak = int(getattr(self, '_slow_streak', 0)) + 1
                    if self._slow_streak >= SLOW_STREAK_MAX:
                        # TRES PRAZOS SEGUIDOS NAO SAO "LENTA", SAO "MORTA": o
                        # mesmo socket nunca respondeu tres vezes. Fecha e
                        # re-liga, em vez de perguntar eternamente a um cano
                        # partido.
                        self._slow_streak = 0
                        try:
                            conn.close()
                        except Exception:             # noqa: BLE001
                            pass
                        conn = None
                        self._publish(None, 'slow-dead (%d prazos)'
                                      % SLOW_STREAK_MAX)
                        self._stop.wait(RETRY_S)
                        continue
                    self._stop.wait(min(0.05, self.poll_s))
                    continue
                self._slow_streak = 0
                snap = parse_snapshot(payload)
                if snap is None:
                    raise ValueError("payload sem forma")
                if snap.get("rs") == 0:
                    # A ABA NAO TEM JOGADOR (2026-11-05, MEDIDO). `rs=0` e' o
                    # `readyState` de um `<video>` sem media: e' o que uma aba
                    # DESCARTADA pelo Chrome responde. Preso nela, o laco leu
                    # **221 vezes** `why=no-painted-caption` em `ICGa6m4E_cA`
                    # (`t=0`, `paused=false` -- o `paused=false` de uma aba sem
                    # video e' o que fazia a regra antiga chamar-lhe "a tocar")
                    # enquanto o dono via a legenda do MODELO. A ligacao cai, a
                    # cache da escolha e' limpa e a proxima passa pela sonda.
                    self._publish(None, "dead-tab (%s)" % (snap.get("videoId") or '-'))
                    self._log('YOUTUBE_CDP_DEAD_TAB video_id=%s rs=0 -- aba sem '
                              'media; a escolha volta a sonda'
                              % (snap.get("videoId") or '-'))
                    self._playing_pick_cache = None
                    try:
                        conn.close()
                    except Exception:             # noqa: BLE001
                        pass
                    conn = None
                    self._stop.wait(max(0.4, float(RETRY_S) / 3.0))
                    continue
                # A ABA PODE NAVEGAR DEPOIS DE NOS LIGARMOS A ELA (2026-11-03,
                # MEDIDO: 7 abas do YouTube abertas, a ligacao presa numa e o
                # Sotto a ler outro video -- `refused=video-mismatch
                # declared=vwiIPjpksEU seen=NBCM_ZoWZo8`). Ler a aba errada e' o
                # unico erro que poe a legenda de um video no ecra de outro: a
                # ligacao cai e a proxima escolhe pelo ID.
                _action, _because = adopt_decision(
                    self._video_id, snap.get("videoId"),
                    (not self._declared_closed()) if self._video_id else True)
                if _action == 'adopt':
                    _old = self._video_id
                    self._video_id = str(snap["videoId"])
                    self._publish(snap, "adopted:%s->%s" % (_old, self._video_id))
                    self._switch_fails = 0
                    continue
                if _action == 'refuse':
                    # A ABA NAVEGOU E O VIDEO DECLARADO JA' NAO EXISTE (2026-11-04).
                    # MEDIDO no log do dono: 10:16:17 `wrong-video (vDmjw-c_R2k)`
                    # seguido de `state=ambiguous`, e a partir dali **13 minutos
                    # sem uma linha** (`YOUTUBE_TICK_MS src='?' rows=0
                    # cdp_age_ms=789250`), porque `_choose` procurava um id que
                    # ja' nao estava em aba nenhuma. O ecra ficou a cargo do ASR
                    # com o player a pintar a faixa dele. A regra certa: o id
                    # declarado filtra a ESCOLHA de aba, nao a leitura -- se ele
                    # nao esta' aberto, quem manda e' a aba a que ja' estamos
                    # ligados, e o id passa a ser dela.
                    self._publish(None, "wrong-video (%s)" % snap["videoId"])
                    try:
                        conn.close()
                    except Exception:                 # noqa: BLE001
                        pass
                    conn = None
                    # TROCAR DE VIDEO NAO ESPERA 2 s (2026-11-03). O dono alterna
                    # entre videos e a legenda tem de aparecer no novo dentro de
                    # uma foto, nao de um ciclo de retry: o id ja' e' conhecido,
                    # logo a proxima escolha e' imediata. O contador impede o
                    # laco apertado quando o id nao existe em aba nenhuma (ele
                    # ainda nao navegou, ou mudou de janela).
                    self._switch_fails = getattr(self, '_switch_fails', 0) + 1
                    if self._switch_fails > 3:
                        self._switch_fails = 0
                        self._stop.wait(RETRY_S)
                    continue
                self._switch_fails = 0
                self._publish(snap, "attached")
            except Exception as exc:              # noqa: BLE001
                self._error(exc)
                # UM TIMEOUT NAO DERRUBA A LIGACAO (2026-11-03, MEDIDO). A aba
                # escondida leva o renderer a adiar um `Runtime.evaluate` por
                # segundos; fechar o socket e reabrir custava mais 2 s e um novo
                # attach -- e a medicao mostrou recusas a cada ~13 s. Espera-se o
                # proximo turno na MESMA ligacao.
                if isinstance(exc, Exception) and type(exc).__name__ in (
                        'WebSocketTimeoutException', 'TimeoutError', 'timeout'):
                    self._publish(None, "slow (%s)" % type(exc).__name__)
                    continue
                try:
                    conn.close()
                except Exception:                 # noqa: BLE001
                    pass
                conn = None
                self._publish(None, "reconnect (%s)" % type(exc).__name__)
                self._stop.wait(RETRY_S)
                continue
            # PAUSA NAO PRECISA DA CADENCIA NORMAL (2026-11-05). MEDIDO nesta
            # maquina com o `_main/shell-thread-cpu.py` e o fio agora NOMEADO:
            # `yt-cdp-source` era o termo DOMINANTE da shell em repouso -- 4,4 %
            # de 8,4 % de um nucleo, so' ele. A legenda nao muda com o video
            # parado, e a deteccao do `play` so' custa `PAUSED_POLL_S` (0,5 s),
            # que a primeira cue ja' paga. O passo volta ao normal assim que a
            # foto disser que o video anda.
            spent = time.monotonic() - t0
            _paused = bool(snap.get('paused')) if isinstance(snap, dict) else False
            _wait = max(self.poll_s, PAUSED_POLL_S) if _paused else self.poll_s
            if _paused != getattr(self, '_paced_logged', None):
                self._paced_logged = _paused
                self._log('YOUTUBE_CDP_PACED paused=%s poll_s=%.2f'
                          % (_paused, _wait))
            self._stop.wait(max(0.0, _wait - spent))
        if conn is not None:
            try:
                conn.close()
            except Exception:                     # noqa: BLE001
                pass

    #: O MOTIVO DE CADA TENTATIVA DE ATTACH, ESCRITO (2026-11-04). `_publish`
    #: so' fala quando o estado MUDA, e por isso o dono leu 40 minutos de
    #: `src='?'` sem uma linha que dissesse "a porta nao abriu". Uma tentativa
    #: falhada e' um facto por si; as primeiras `_ATTACH_LOG_N` saem todas, e
    #: depois disso so' uma em cada `_ATTACH_LOG_EVERY` -- o Chrome pode ficar
    #: fechado a tarde inteira e o log nao pode pagar 30 linhas por minuto.
    _ATTACH_LOG_N = 20
    _ATTACH_LOG_EVERY = 50

    def _attach_log(self, attempt, ok, reason, ms=0.0, extra=''):
        # O CHOKE POINT DE TODA A TENTATIVA (2026-11-05): as tres saidas de falha
        # de `_connect` passam todas por aqui, logo a hora da ultima falha vive
        # num so' sitio. `target_video_id` le-a para nao sondar alvos contra uma
        # porta que acabou de nao responder.
        self._attach_failed_at = None if ok else time.monotonic()
        if attempt > self._ATTACH_LOG_N and attempt % self._ATTACH_LOG_EVERY:
            return
        self._log('YOUTUBE_CDP_ATTACH_%s attempt=%d ok=%s reason=%s port=%d '
                  'ms=%.0f %s'
                  % ('OK' if ok else 'FAILED', attempt, str(bool(ok)).lower(),
                     reason, self.port, ms, extra))

    def _connect(self, websocket):
        self._attach_tries = int(getattr(self, '_attach_tries', 0)) + 1
        _n = self._attach_tries
        _t0 = time.monotonic()
        try:
            tabs, _others = list_targets(self.port,
                                         timeout=ATTACH_PROBE_TIMEOUT_S)
        except Exception as exc:                  # noqa: BLE001
            self._error(exc)
            _why = _probe_reason(exc)
            self._publish(None, _why)
            self._attach_log(_n, False, _why,
                             (time.monotonic() - _t0) * 1000.0,
                             'err=%s' % type(exc).__name__)
            return None
        target, why = self._choose(tabs)
        if target is None:
            self._publish(None, why)
            self._attach_log(_n, False, why, (time.monotonic() - _t0) * 1000.0,
                             'tabs=%d' % len(tabs))
            return None
        url = target.get("webSocketDebuggerUrl")
        if not url:
            self._publish(None, "no-ws-url")
            self._attach_log(_n, False, "no-ws-url",
                             (time.monotonic() - _t0) * 1000.0)
            return None
        try:
            conn = websocket.create_connection(url, timeout=15.0)
            # A RESPOSTA TAMBEM TEM PRAZO (2026-11-03, MEDIDO NO DONO).
            # `create_connection(timeout=15.0)` so' limita o HANDSHAKE: o `recv`
            # do laco herdava esse valor e, quando a resposta nao vinha -- a
            # pagina parada em segundo plano, ou outro cliente CDP a segurar o
            # mesmo alvo --, a thread ficava DENTRO do `recv` com a foto a
            # envelhecer. MEDIDO: `YOUTUBE_CDP_HEALTH stats={'reads': 1,
            # 'errors': 0}` enquanto o laco respondia `YOUTUBE_PAINT_STATE
            # why=cdp-stale` -- uma leitura, depois silencio, e o `EXTERNAL_
            # CAPTIONS_READ_MS` a pagar 1 s de varredura a cada volta porque a
            # fonte deixava de ser reconhecida. Um segundo e' mais do que a
            # leitura inteira (10 ms medidos); o que passa disso e' ligacao
            # morta, e trata-se como tal.
            conn.settimeout(3.0)
            self._attach_log(_n, True, why, (time.monotonic() - _t0) * 1000.0,
                             'pick=%s' % (video_id_from_url(
                                 target.get("url") or "") or '-'))
            return conn
        except Exception as exc:                  # noqa: BLE001
            self._error(exc)
            self._publish(None, "ws-failed")
            self._attach_log(_n, False, "ws-failed",
                             (time.monotonic() - _t0) * 1000.0,
                             'err=%s' % type(exc).__name__)
            return None
