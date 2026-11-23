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
import queue
import threading
import time
import urllib.request


def _load_sibling(name):
    """Um modulo IRMAO carregado pelo CAMINHO, nunca por `import nome`."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), name + '.py')
    spec = importlib.util.spec_from_file_location('sotto_' + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


#: O MARCADOR DE FALA DO PLAYER NAO PASSA POR AQUI. Dono, verbatim (2026-11-08):
#: *"youtube escreve >> em algumas legendas. nao transmita iss pro sotto"*.
#:
#: O `>>` e' do PLAYER -- `&gt;&gt;` no DOM antes de descodificar, `>>` depois, e o
#: `\u203a\u203a` da faixa automatica -- e o caminho que alimenta o ecra hoje e'
#: ESTE (CDP); o da UIA ja' o tirava, e por isso ele via o simbolo so' em algumas
#: legendas. A lista de marcadores vive em `youtube_window.strip_speaker_markers`,
#: que e' o dono dela: duas listas divergiriam no primeiro marcador novo.
#:
#: CARREGADO PELO CAMINHO, NAO POR NOME. `from youtube_window import ...` so'
#: resolve com o diretorio da app no `sys.path`, e quem carrega este modulo nem
#: sempre o poe la' (medido: o oraculo carrega o ficheiro por `spec`, o import
#: levantava e um fallback local -- que so' tirava o marcador do INICIO -- deixava
#: o `>>` do MEIO da linha chegar ao ecra). Sem fallback duplicado.
strip_speaker_markers = _load_sibling('youtube_window').strip_speaker_markers

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

#: O PRAZO DE UMA LEITURA DEPOIS DA PRIMEIRA (2026-11-03, MEDIDO): uma aba em
#: SEGUNDO PLANO pode levar segundos a responder ao `Runtime.evaluate`, e a
#: ligacao NAO se fecha por isso -- o `_run` pergunta outra vez (ver `_slow`).
READ_TIMEOUT_S = 3.0

#: O PRAZO DO *PRIMEIRO* PEDIDO DE UMA LIGACAO NOVA -- CURTO DE PROPOSITO
#: (2026-11-11, MEDIDO). O handshake ja' provou que a porta responde, e uma
#: pagina VIVA responde ao `Runtime.evaluate` em ~10 ms (medido: a foto inteira
#: custa 10 ms). O que nao responde no primeiro pedido e' um alvo que nao e' o
#: jogador, e o dono paga isso como *"levou 3 segundos pra aparecer a legenda"*
#: (17:35:45.193 troca -> 56.396 attach -> 62.422 a primeira linha). Do segundo
#: pedido em diante vale `READ_TIMEOUT_S`: ai' a lentidao pode ser da pagina, e
#: nesse caso a ligacao fica.
FIRST_READ_TIMEOUT_S = 0.5

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
               rate: v ? v.playbackRate : null,
               // `ended` (2026-11-15): o shell le `snap['ended']` para decidir
               // `yt_cdp_ended` e esta chave NAO vinha neste payload desde que
               // ele existe -- `parse_snapshot` a descartava por ausencia, e
               // `yt_cdp_ended` era `False` para sempre. Medido pelo drill de
               // caos (S5, `T5 player_stopped reads an ended video as stopped`):
               // o DOM publicava `ended=true` e a decisao respondia False.
               // O `PLAYING_JS` ja' publicava; era este que faltava.
               ended: v ? v.ended : null};
  const box = document.querySelector('.ytp-caption-window-container');
  if (!box) return JSON.stringify(out);
  const all = Array.prototype.slice.call(
      box.querySelectorAll('.caption-visual-line'));
  const segs = Array.prototype.slice.call(
      box.querySelectorAll('.ytp-caption-segment'));
  // A JANELA DE AVISO NAO E' LEGENDA (MEDIDO 2026-11-14, log do dono): com a
  // faixa a ser servida o proprio YouTube abre uma janela DENTRO do mesmo
  // container dizendo `Ingl\u00eas` / `Clique em para configura\u00e7\u00f5es`,
  // e o extrator a lia como linha da fala -- ela FOI AO ECRA como legenda nossa
  // (`CAPTION_PAINT_SURFACE src=player rows=4 text="Ingl\u00eas\n...`,
  // :272633 do `_main/webview-run.log`). O que distingue a janela de controlete
  // nao e' o texto nem a classe da linha: e' ela carregar `svg`/`button` do
  // proprio YouTube, coisa que nenhuma linha de fala tem. Marca-se AQUI e o
  // parser puro (`parse_snapshot`) descarta -- duas medidas, e a segunda roda
  // sem Chrome.
  const isChrome = function (line) {
    let el = line.closest ? line.closest('.caption-window') : null;
    if (!el) {
      // Sem `.caption-window` no caminho (o YouTube muda nomes), a janela e' o
      // primeiro ancestral que ja' carrega controlete do proprio player. Tres
      // niveis bastam: a linha -> a caixa de fala -> a janela.
      el = line;
      for (let i = 0; i < 3 && el && el !== box; i++) el = el.parentElement;
    }
    if (!el) return false;
    return !!(el.querySelector('svg') || el.querySelector('button'));
  };
  const isChromeSeg = function (seg) {
    const l = seg.closest ? seg.closest('.caption-visual-line') : null;
    return !!(l && isChrome(l));
  };
  out.segs = segs.filter(function (s) { return !isChromeSeg(s); })
                 .map(function (s) { return (s.textContent || '').trim(); })
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
  // A JANELA DE AVISO NAO E' LEGENDA (MEDIDO 2026-11-14, log do dono): com a
  // faixa a ser servida o YouTube abre uma janela DENTRO do mesmo container
  // que diz `Ingl\u00eas` / `Clique em para configura\u00e7\u00f5es`, e o
  // extrator a lia como duas linhas da fala -- ela foi AO ECRA como legenda
  // nossa (`CAPTION_PAINT_SURFACE src=player rows=4 text="Ingl\u00eas\n...`).
  // O que a distingue nao e' texto nem classe de linha: e' o DESENHO da
  // janela, que carrega `svg`/`button` do controlete e nunca aparece numa
  // linha de fala. Marca-se a linha aqui e o parser puro descarta -- duas
  // medidas, e a segunda testavel sem Chrome.
  out.rows = visible.map(function (line) {
    const items = Array.prototype.slice.call(
        line.querySelectorAll('.ytp-caption-segment')).map(function (seg) {
      const b = seg.getBoundingClientRect();
      return {text: (seg.textContent || ''), left: b.left, top: b.top,
              right: b.right, bottom: b.bottom};
    }).filter(function (it) { return it.text.trim().length > 0; });
    return {text: (items.map(function (i) { return i.text; }).join(' ')
                    .replace(/\s+/g, ' ').trim()), items: items,
            chrome: isChrome(line)};
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
    vis: document.visibilityState || '',
    focus: (typeof document.hasFocus === 'function') ? document.hasFocus() : null
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
#: COM UMA ABA SO'. Com DUAS ou mais a escolha muda com um alt-tab (o dono,
#: 2026-11-06: *"se eu voltasse pro outro video, daria prioridade pro outro
#: video. se eu desse alt tab, ainda ficaria naquele ali"*), e 10 s de cache
#: eram 10 s de legenda do video errado: `PLAYING_PROBE_TTL_MULTI_S`.
PLAYING_PROBE_TTL_S = 10.0
PLAYING_PROBE_TTL_MULTI_S = 1.0

#: QUANTO CUSTA, NO MAXIMO, UMA SONDA DE "QUEM TOCA" (2026-11-09, MEDIDO).
#:
#: O DEFEITO: `YOUTUBE_TARGET_SLOW ms=1015 vid=guARjKjyFLY ttl_s=10
#: src=refresher` de 11 em 11 s no log do dono. O numero NAO era o `/json/list`
#: (medido nesta maquina, do processo de fora, com o Chrome do dono a correr:
#: `urllib /json/list median=3.2ms max=12.4ms bytes=25798`; `raw-tcp-connect
#: median=0.4ms`). Era `probe_tabs`: a aba E606035C da sessao do dono NAO
#: responde a `Runtime.evaluate` -- nem em 6,0 s (`WebSocketTimeoutException` a
#: 1003 ms com prazo 1,0 s; a 6000 ms com prazo 6,0 s; enquanto a aba viva
#: responde em 5-7 ms) -- e `_probe_one` esperava o prazo INTEIRO por ela. A
#: sonda corre em paralelo, logo o custo total era o da aba MORTA: ~1,0 s por
#: chamada. Nao e' a lista de abas; e' um renderer congelado.
#:
#: O orcamento e' de relogio, nao de socket: `websocket.create_connection` com
#: `timeout=1.0` mediu **5107 ms** uma vez sob carga (o prazo do argumento nao
#: cobre o handshake), portanto o que limita a sonda e' o `join` do chamador.
PROBE_TIMEOUT_S = 0.35
PROBE_BUDGET_S = 0.5
#: CUSTO A PARTIR DO QUAL A SONDA E' "CARO" -- e o cache estica (2026-11-09).
#: Com a sonda barata (`< 5 ms` medidos na aba viva) o cache de 1 s por duas
#: abas e' o que o alt-tab do dono pede. Com uma aba congelada a sonda custa o
#: orcamento inteiro, e repeti-la de 1 em 1 s queima 35 % de um nucleo para
#: devolver "nao respondeu". Nesse regime o cache vale `PLAYING_PROBE_SLOW_TTL_S`.
PROBE_SLOW_MS = 150.0
PLAYING_PROBE_SLOW_TTL_S = 5.0


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
            # `document.hasFocus()`: a UNICA testemunha que muda com um alt-tab
            # entre duas abas `watch` da mesma janela (2026-11-06). `None` (aba
            # antiga, duplo de teste) nao e' foco -- ver `tab_is_foreground`.
            'focused': second.get('focus'),
            'tab': tab}


#: THE PROBE WORKERS ARE REUSED, AND THE COST THEY REMOVED WAS MEASURED.
#: The `/json/list` refresher asks once per `PLAYING_PROBE_TTL*`, and each ask
#: used to pay one `Thread.start()` PER TAB. On this box an idle start costs
#: ~0.2 ms, but inside the owner's live shell -- dozens of threads, 82 % commit --
#: the probe's own log measured the OTHER regime: `YOUTUBE_PROBE_BUDGET
#: tabs_total=6 probed=2 done=0 abandoned=6 budget_ms=500`, i.e. two starts ate
#: the whole 500 ms budget and the remaining four tabs were never asked. The
#: pool pays the spawn cost ONCE per process (6 daemon workers, bounded), and a
#: probe cycle becomes `Queue.put` (microseconds) plus the sockets themselves.
#: A queued job whose call is already abandoned is DROPPED before opening a
#: socket, so a late caller's deadline does not buy probes nobody reads.
_PROBE_POOL_LOCK = threading.Lock()
_PROBE_POOL_JOBS = None


class _ProbeCall:
    """One `probe_tabs` call: results, progress, and the deadline wait."""

    def __init__(self, count):
        self.results = [None] * count
        self.pending = count
        self.started = 0
        self.abandoned = False
        self._cond = threading.Condition()

    def begin(self):
        with self._cond:
            self.started += 1

    def finish(self, idx, value):
        with self._cond:
            self.results[idx] = value
            self.pending -= 1
            self._cond.notify_all()

    def wait(self, deadline):
        with self._cond:
            while self.pending:
                if deadline is None:
                    self._cond.wait()
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                self._cond.wait(remaining)


def _probe_worker(jobs):
    while True:
        job = jobs.get()
        if job is None:
            return
        call, idx, tab, connect, timeout, gap_s = job
        if call.abandoned:
            continue
        call.begin()
        try:
            value = _probe_one(tab, connect, timeout, gap_s)
        except Exception:                         # noqa: BLE001
            value = None
        call.finish(idx, value)


def _probe_pool():
    """The process-wide probe workers, spawned on first use and reused."""
    global _PROBE_POOL_JOBS
    with _PROBE_POOL_LOCK:
        if _PROBE_POOL_JOBS is None:
            jobs = queue.Queue()
            for n in range(max(1, int(MAX_PROBE_TABS))):
                threading.Thread(target=_probe_worker, args=(jobs,),
                                 name='yt-probe-%d' % n, daemon=True).start()
            _PROBE_POOL_JOBS = jobs
        return _PROBE_POOL_JOBS


def probe_tabs(tabs, connect=None, timeout=1.0, gap_s=PLAYING_GAP_S,
               parallel=True, budget_s=None, log=None):
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

    O ORCAMENTO (`budget_s`) E' DE RELOGIO, NAO DE SOCKET (2026-11-09, MEDIDO).
    Cada fio de aba e' `daemon` e ninguem o junta depois do prazo: o resultado
    que nao chegou a tempo e' DESCARTADO e o chamador segue com o que tem. O
    `ThreadPoolExecutor` antigo nao servia -- o `with` faz `shutdown(wait=True)`
    no fim, ou seja o prazo era decorativo: uma aba congelada (a `E606035C` da
    sessao do dono nao responde a `Runtime.evaluate` nem em 6 s) segurava a
    funcao pelo `timeout` inteiro mesmo depois de o orcamento estourar. Fios
    soltos custam ~0,1 ms e morrem no prazo do proprio `recv`.
    """
    connect = connect or _default_connect()
    population = list(tabs or ())
    if not population:
        return []
    # A POPULACAO NAO E' O QUE CABE NUMA VAGA (MEDIDO 2026-11-12).
    # `list_targets` ja' entrega SO' abas `/watch`, e este laco cortava em
    # `[:MAX_PROBE_TABS]` ANTES de saber qual delas toca: com SETE abas `watch`
    # abertas -- o caso do dono, no proprio log desta arvore, `tabs=7` -- a
    # setima nunca era sondada, e a escolha caia numa aba parada vizinha. O
    # instrumento nao podia denunciar: `YOUTUBE_PROBE_BUDGET tabs=%d` imprimia
    # `len(items)`, ou seja o numero JA' CORTADO.
    #
    # Agora `MAX_PROBE_TABS` e' o tecto de SONDAS SIMULTANEAS, nao o da
    # populacao: as abas vao em VAGAS desse tamanho, e quem acaba a fila e' o
    # orcamento de RELOGIO (`budget_s`), que ja' existia. Duas vagas custam
    # ~2 x `gap_s` e caem dentro dos 0,5 s medidos do orcamento.
    items = population
    if not parallel or len(items) == 1:
        deadline_seq = (None if budget_s is None
                        else time.monotonic() + max(0.0, float(budget_s)))
        out = []
        for t in items:
            if deadline_seq is not None and time.monotonic() >= deadline_seq:
                break
            p = _probe_one(t, connect, timeout, gap_s)
            if p:
                out.append(p)
        return out
    # OS FIOS SAO REUTILIZADOS (2026-11-23, MEDIDO). Antes era um
    # `Thread.start()` POR ABA POR PERGUNTA, e o proprio log do dono mediu o
    # preco: `YOUTUBE_PROBE_BUDGET tabs_total=6 probed=2 done=0 abandoned=6
    # budget_ms=500` -- dois arranques comeram o orcamento e quatro abas nunca
    # foram perguntadas. Agora a pergunta e' `Queue.put` e quem trabalha sao os
    # `MAX_PROBE_TABS` fios do pool, que mantem o tecto de SONDAS SIMULTANEAS:
    # a vaga passa a custar a aba MAIS LENTA, nao o arranque de cada uma.
    deadline = (None if budget_s is None
                else time.monotonic() + max(0.0, float(budget_s)))
    jobs = _probe_pool()
    call = _ProbeCall(len(items))
    for idx, tab in enumerate(items):
        jobs.put((call, idx, tab, connect, timeout, gap_s))
    call.wait(deadline)
    with call._cond:
        started = call.started
        done = len(items) - call.pending
        results = list(call.results)
        if call.pending:
            # A PERGUNTA ACABOU: o que ainda esta' na fila nao abre socket, e o
            # que ja' correu tem o resultado descartado pelo chamador.
            call.abandoned = True
    late = len(items) - done
    # O NUMERO QUE DENUNCIA E' A DIFERENCA ENTRE A POPULACAO E O QUE FOI
    # TENTADO. Antes `tabs=` era `len(items)` -- o corte -- e essas duas abas
    # eram o mesmo numero: o log nao podia dizer que faltava alguem.
    if late and log is not None:
        try:
            log('YOUTUBE_PROBE_BUDGET tabs_total=%d probed=%d done=%d abandoned=%d '
                'waves=%d budget_ms=%.0f timeout_ms=%.0f'
                % (len(items), started, done, late,
                   (len(items) + max(1, int(MAX_PROBE_TABS)) - 1) // max(1, int(MAX_PROBE_TABS)),
                   float(budget_s) * 1000.0, float(timeout) * 1000.0))
        except Exception:                     # noqa: BLE001
            pass
    return [p for p in results if p]


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


def tab_is_foreground(probe):
    """A ABA QUE ELE ESTA' A VER: visivel E com o foco do documento.

    `document.visibilityState === 'visible'` diz que a aba nao esta' escondida;
    `document.hasFocus()` diz que e' ELA (e nao a vizinha) que tem o foco. As
    duas, e nao uma: com duas abas `watch` abertas, a de tras tambem responde
    `visible` quando a janela do Chrome tem foco -- so' o foco separa as duas,
    e e' ele que muda num alt-tab (dono, 2026-11-06: *"se eu voltasse pro outro
    video, daria prioridade pro outro video"*).

    Um duplo de teste sem o campo devolve False: foco nao se inventa.
    """
    if not isinstance(probe, dict):
        return False
    return (str(probe.get('visible') or '') == 'visible'
            and probe.get('focused') is True)


def tab_is_playing(probe):
    """A aba esta' a ANDAR o `currentTime` (e nao esta' pausada/acabada)?."""
    if not isinstance(probe, dict):
        return False
    return (not probe.get('paused') and not probe.get('ended')
            and (_float(probe.get('advance')) or 0.0) > 0.0)


def player_stopped(snap):
    """O PLAYER NAO ESTA' A ANDAR? -- `paused`/`ended` do DOM, e so' eles.

    O DEFEITO (dono, 2026-11-06, verbatim): *"se eu pauso o video, a legenda do
    sotto continua por mais uns 2 segundos"*. Nenhuma janela de frescura nem o
    relogio do UIA sabem o que e' uma pausa; `video.paused` (e `video.ended`)
    sabem, porque sao a mesma bandeira que o player usa para parar o desenho.

    `None` (campo ausente: duplo de teste antigo) NAO e' pausa -- um payload que
    nao fala de pausa nao pode congelar a legenda por omissao.
    """
    if not isinstance(snap, dict):
        return False
    return snap.get('paused') is True or snap.get('ended') is True


def _revealed_text(row, t):
    """O prefixo da linha que os relogios das palavras ja' revelaram em `t`."""
    text = str(row.get("text") or "")
    words = [w for w in (row.get("words") or ()) if isinstance(w, dict)]
    if not words or t is None:
        return text
    count = 0
    for word in words:
        start = _float(word.get("start"))
        if start is not None and float(start) > float(t) + 1e-9:
            break
        count += 1
    if count >= len(words):
        return text
    return " ".join(str(w.get("text") or "") for w in words[:count]).strip()


def freeze_rows(rows, t):
    """As linhas que o overlay desenha PARADAS no instante `t` do player.

    PORQUE EXISTE (2026-11-06). O overlay revela o cue contra o relogio do
    proprio player (`caption_overlay._PlayerCue`: `t + (agora - at) * rate`) e
    nada nesse motor sabe o que e' uma pausa -- medido no log do dono: 13,8 s de
    `paused=True` com a linha a CRESCER (11 -> 14 palavras) e `paint_t` a andar
    +0,95 s. Um payload congelado resolve-o sem tocar no motor: `end=None`, sem
    relogio de palavras e sem tecto fazem `youtube_reveal.frame` desenhar o
    MESMO texto em qualquer instante, logo o relogio pode andar a' vontade que
    ele nao acrescenta uma palavra nem deixa a linha expirar.

    Palavras com `start > t` ainda nao foram mostradas: saem do payload.
    """
    out = []
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        start = _float(row.get("start"))
        if start is not None and t is not None and start > float(t) + 1e-9:
            continue
        text = _revealed_text(row, t)
        if not text:
            continue
        out.append({"index": row.get("index"), "text": text, "words": [],
                    "start": (start if start is not None else 0.0),
                    "end": None, "cap": None})
    return out


def declared_open(tabs, declared):
    """O video DECLARADO ainda esta' ABERTO? -- respondido pela LISTA de abas.

    Duas perguntas diferentes, e a diferenca e' o defeito de 17:46: a SONDA
    responde "esta aba tem jogador e responde agora"; a LISTA responde "a aba
    existe". Quando so' a segunda e' verdadeira, o alvo continua a ser o
    declarado -- nao ha' evidencia nenhuma de que o dono mudou de video.
    """
    vid = str(declared or '')
    if not vid:
        return False
    for tab in tabs or ():
        try:
            if vid in str(tab.get('url') or ''):
                return True
        except AttributeError:                    # noqa: PERF203
            continue
    return False


def choose_target(probes, previous='', window_title='', declared='',
                  declared_open=False):
    """(video_id, porque) -- QUE ABA, decidido pela evidencia de cada uma.

    O dono, verbatim (2026-11-05): *"dumb picking then. do it properly. do it
    the best design. should attach to current tab or last tab"*, e depois *"or
    better then that"*. A ordem abaixo e' a melhor que a medicao sustenta, e
    cada degrau tem a sua testemunha -- nao ha' `ambiguous` que dure:

      0. **`no-player`** quando NENHUMA aba tem jogador (`is_real_player`).
         Melhor nao responder do que prender-se a uma aba descartada.
      1. **`foreground`** -- A ABA EM PRIMEIRO PLANO (`tab_is_foreground`:
         `visibilityState === 'visible'` E `document.hasFocus()`), com
         preferencia pela que tambem TOCA (`tab_is_playing`). E' a unica
         testemunha que muda num alt-tab, e a ordem do dono (2026-11-06),
         verbatim: *"abrir outro video e ter os dois tocando ao mesmo tempo,
         ainda continua o ultimo video, inves de dar prioridade ao novo. e
         obviamente, se eu voltasse pro outro video, daria prioridade pro outro
         video."* Com DUAS abas a tocar, o foco decide; voltar ao outro video
         devolve-lhe a prioridade na leitura seguinte. Um video pausado em
         primeiro plano TAMBEM manda (pausar o que ele esta' a ver nao pode
         entregar o ecra ao video de tras).
      2. **`window-title`** -- o titulo da janela em primeiro plano casa com o
         titulo da aba (exacto, depois parcial). E' a testemunha do "current
         tab" quando o Chrome NAO tem o foco (o foco do documento e' False nas
         duas abas) -- ali o titulo da janela e' a ultima aba activa.
      3. **`playing`** -- o que AVANCOU o `currentTime` entre as duas leituras
         (o video que ele esta' a ouvir). Desempate pelo id, que e' estavel.
      4. **`declared`** -- o id que o shell declarou, AGORA VERIFICADO: so' vale
         se a aba dele tiver jogador.
      5. **`sticky-last`** -- o ultimo adotado, se ainda tiver jogador. Duas abas
         a tocar nao podem fazer o ecra trocar sozinho.
      6. **`keep-declared`** -- o id declarado continua ABERTO (`declared_open`,
         resposta da lista de abas) e a sonda nao o viu; nao ha' evidencia de
         troca de video, so' de um socket que nao respondeu. O picker NAO adota
         outra aba: devolve o declarado. MEDIDO (log do dono, 2026-11-11 17:46):
         `17:46:02.951 slow (ConnectionAbortedError)` -> `17:46:03.513
         YOUTUBE_TARGET pick=JM1gEnmaUao why=paused-loaded declared=zEgthOmOrc0
         tabs=7` -> `17:46:05.039 adopted:zEgthOmOrc0->JM1gEnmaUao` -> `17:46:05.108
         CAPTION_WINDOW_BLANKED reason=video-changed` e o ASR a pintar 714 ms
         depois. Uma queda de socket virou TROCA DE VIDEO com sete abas abertas.
      7. **`only-player`** / **`paused-loaded`** -- ele poe o video EM PAUSA (as
         tres abas reais de hoje estavam): a linha pintada de um video pausado
         ainda e' a legenda do YouTube, e e' melhor do que a de outro video.
         Entre varios pausados fica o de linha temporal mais avancada. NUNCA
         acima de um video A TOCAR: `paused` e' a razao por que a leitura PASSA,
         nao a razao para trocar o que o dono ve.
    """
    usable = [p for p in (probes or ()) if is_real_player(p)
              and str(p.get('videoId') or '')]
    if not usable:
        return '', 'no-player'
    prev = str(previous or '')
    # 1. A ABA EM PRIMEIRO PLANO MANDA (2026-11-06). Preferencia pela que TOCA,
    #    depois pelo `advance`/`t1`/id -- nunca pela ordem da lista.
    front = [p for p in usable if tab_is_foreground(p)]
    if front:
        pool = [p for p in front if tab_is_playing(p)] or front
        pool.sort(key=lambda p: (0 if tab_is_playing(p) else 1,
                                 -(_float(p.get('advance')) or 0.0),
                                 -(_float(p.get('t1')) or 0.0),
                                 str(p.get('videoId') or '')))
        return str(pool[0]['videoId']), 'foreground'
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
    live = [p for p in usable if tab_is_playing(p)]
    if live:
        # O JA' ADOTADO QUE AINDA TOCA FICA (2026-10-30, mantido em 2026-11-05
        # pela ordem do dono -- *"current tab or last tab"*). Duas abas a tocar
        # ao mesmo tempo (picture-in-picture, dois separadores) nao podem fazer
        # o ecra trocar de video sozinho: um ecra que alterna e' pior do que um
        # ecra parado. MEDIDO pela arm `duas-a-tocar-decide-e-nao-tropeca`, que
        # ficou vermelha quando `playing` passou a' frente de `sticky-last`.
        # O PRIMEIRO PLANO fica ACIMA disto (degrau 1), e e' essa a mudanca de
        # 2026-11-06: sem foco declarado nada muda.
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

    # O DECLARADO ESTA' ABERTO E A SONDA NAO O VIU -> `keep` (2026-11-11, MEDIDO).
    # As tres saidas abaixo sao as que nao tem evidencia nenhuma de troca de
    # video: `sticky-last`, `only-player` e `paused-loaded` escolhem por
    # ELIMINACAO. Uma queda de socket (`ConnectionAbortedError`) nao e' evidencia;
    # com sete abas abertas ela escolheu um video pausado e o ecra apagou para
    # mostrar outro. O declarado continua a ser o alvo ate' haver testemunha.
    if declared and declared_open:
        return str(declared), 'keep-declared'
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
                 gap_s=PLAYING_GAP_S, window_title='', declared='',
                 budget_s=None, log=None):
    """(aba, video_id, porque) -- a aba com jogador, ou `(None, '', motivo)`.

    UMA sonda por aba (duas leituras em paralelo, ~1,3 s no pior caso) responde
    a pergunta inteira, e a resposta vem de `choose_target`. Quem chama guarda o
    resultado por `PLAYING_PROBE_TTL_S`: enquanto a escolha vale, a sonda nao se
    repete e o custo e' zero.

    `budget_s` (2026-11-09) e' o tecto de RELOGIO repassado a `probe_tabs`;
    `log` leva o veredicto `YOUTUBE_PROBE_BUDGET` quando uma aba e' abandonada.
    """
    probes = probe_tabs(tabs, connect=connect, timeout=timeout, gap_s=gap_s,
                        budget_s=budget_s, log=log)
    vid, why = choose_target(probes, previous, window_title, declared,
                             declared_open=declared_open(tabs, declared))
    if not vid:
        return None, '', why
    if why == 'keep-declared':
        # A ABA VEM DA LISTA, NAO DA SONDA -- a sonda nao a viu (2026-11-11).
        # `keep` e' "continua este video": quem diz que a aba existe e' o URL dela
        # na lista de abas, e o `pick_target` ja' sabe procura-lo por id.
        named, _named_why = pick_target(tabs, vid, '')
        return named, vid, why
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
        # A JANELA DE AVISO NAO E' FALA (2026-11-14). O extrator marca a linha
        # que vive numa janela com controlete (`svg`/`button`); `Ingl\u00eas` /
        # `Clique em para configura\u00e7\u00f5es` sao o TEXTO DE ESTADO do
        # player, nao a legenda. MEDIDO no log do dono: esses dois iam pintados
        # como linhas nossas.
        if line.get("chrome"):
            continue
        text = strip_speaker_markers(line.get("text"))
        if not text:
            continue
        kids = []
        for kid in line.get("items") or ():
            if not isinstance(kid, dict):
                continue
            body = strip_speaker_markers(kid.get("text"))
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
    segs = [m for m in (strip_speaker_markers(x) for x in (data.get("segs") or ()))
            if m]
    # `why` NAO PODE DIZER `painted` COM ZERO LINHAS (2026-11-14). Quando o
    # unico conteudo da caixa e' a janela de aviso do player, o extrator responde
    # `painted` e o parser descarta tudo -- e o log passava a afirmar uma pintura
    # que nao existe, que e' o tipo de linha que faz a proxima medicao olhar para
    # o lado errado. O nome honesto do estado e' o mesmo de uma caixa vazia.
    why = str(data.get("why") or ("painted" if rows else "no-painted-caption"))
    if why == "painted" and not rows:
        why = "no-painted-caption"
    return {"stamp": float(now if now is not None else time.monotonic()),
            "segs": segs,
            "videoId": str(data.get("videoId") or ""),
            "t": (_float(data.get("t"))),
            "paused": (None if data.get("paused") is None else bool(data.get("paused"))),
            # `ended` (2026-11-15): o shell le' este campo (linha ~5461) e ele
            # nunca chegava aqui -- `EXTRACT_JS` nao o publicava, entao a chave
            # estava sempre ausente e `yt_cdp_ended` era `False` por construcao.
            # Ausencia continua a ser ausencia (`None`), nunca um `False`
            # inventado: um payload velho nao afirma que o video acabou.
            "ended": (None if data.get("ended") is None else bool(data.get("ended"))),
            "rate": _float(data.get("rate")),
            # O JOGADOR EXISTE NESTA ABA? (2026-11-05) `rs` e' o `readyState` do
            # `<video>`: 0 = nenhuma media carregada, que e' o que uma aba
            # DESCARTADA pelo Chrome responde. O laco usa este campo para NAO
            # ficar preso numa aba sem jogador (medido: 221 leituras em
            # `ICGa6m4E_cA`, `rs=0`, zero linhas, e o ASR no ecra do dono).
            "rs": data.get("rs"),
            "title": str(data.get("title") or ""),
            "rows": rows, "items": items,
            "why": why}


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
    a ver. O id continua a ser a chave mais forte para a ABERTURA de uma aba
    nomeada; o titulo resolve o caso comum sem custo nenhum, e so' o que sobra
    fica `ambiguous`.

    A ORDEM MUDOU A 2026-11-06: o TITULO DA JANELA VEM ANTES DO ID DECLARADO.
    O dono: *"abrir outro video ... inves de dar prioridade ao novo"*. MEDIDO no
    log dele: `YOUTUBE_TARGET pick=tnBpieBy2GY why=declared declared=tnBpieBy2GY
    tabs=2` -- com duas abas abertas, o id declarado nunca deixava a testemunha
    do alt-tab (o titulo) correr. O id declarado e' uma CRENCA; o titulo da
    janela em primeiro plano e' o que ele esta' a ver. Se o titulo casar com uma
    aba, e' essa; o id so' decide quando o titulo nao decide.
    """
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
    if video_id:
        named = [t for t in tabs if video_id in str(t.get("url") or "")]
        if named:
            return named[0], "named"
        return None, "video-not-open"
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
#: QUANTO TEMPO O ID ESCOLHIDO VALE (2026-11-06). Era 2 s, e 2 s eram 2 s de
#: legenda do video ANTERIOR depois de abrir outro: o dono, verbatim: *"abrir
#: outro video ... ainda continua o ultimo video, inves de dar prioridade ao
#: novo"*. O `/json/list` e' HTTP local (~10 ms medidos) e a sonda por aba ja'
#: tem cache propria (`PLAYING_PROBE_TTL_*`), portanto meio segundo de cache e'
#: o que o "imediato" do dono custa. Uma chamada lenta estica para
#: `_TID_SLOW_TTL_S` (ver abaixo), e nada muda na porta morta.
_TID_TTL_S = 0.5
#: O PRAZO DA PRIMEIRA PERGUNTA (2026-11-09). A leitura do laco espera o fio
#: `yt-cdp-target` publicar, mas nao para sempre: medido no log do dono,
#: `EXTERNAL_CAPTIONS_READ_MS ms=33281.0 phases={'target': 33281.0}` com o
#: Chrome a 100 % -- o cache vazio respondia com um `/json/list` SINCRONO no fio
#: do laco. Este numero e' o que o laco aceita perder em vez disso.
_TID_WAIT_S = 0.30
#: O TECTO DA PERGUNTA FEITA SEM LIGACAO (2026-11-09, MEDIDO). `target_video_id`
#: e' chamada pelo laco da legenda; sem ligacao a resposta e' so' "ha' uma aba
#: `watch`?" (`list_targets`, 1,5-13 ms medidos) e NAO a sonda de WebSocket. O
#: prazo de 100 ms e' folga para a criacao do fio e para um `/json/list` sob
#: carga; o que passar disso devolve '' e a linha `YOUTUBE_TARGET_STALE` diz por
#: que. Um laco de legenda nao espera 1 s por uma resposta que pode ser ''.
_TID_INLINE_WAIT_S = 0.10
#: A LINHA DE IDADE DO ID: uma por cada `_TARGET_STALE_LOG_S` enquanto o valor
#: estiver atrasado (o dobro da cadencia prometida).
_TARGET_STALE_LOG_S = 5.0
#: O NOME DO FIO QUE PAGA A PERGUNTA (2026-11-08). Nomeado porque
#: `_main/shell-thread-cpu.py` atribui CPU por nome de fio, e porque o recibo
#: desta mudanca tem de poder dizer ONDE o `/json/list` lento corre: se ele
#: voltar a aparecer num `EXTERNAL_CAPTIONS_READ_MS`, o culpado nao e' este fio.
_TID_THREAD_NAME = "yt-cdp-target"

#: QUANTAS VEZES POR MINUTO AS LINHAS DE ESTADO SE REPETEM SEM MUDAR NADA.
#: MEDIDO 2026-11-09 (DM do watcher, stutter 50452): 64,7 MB de log com
#: `YOUTUBE_TARGET ... why=declared` e `YOUTUBE_CDP_SOURCE state=attached` a
#: repetirem-se ~1,4x por segundo cada -- 6 513 e 6 511 linhas nos ultimos 2 MB,
#: 16 linhas/s em rajada. A informacao nao muda: `_choose` escrevia o motivo da
#: ESCOLHA no mesmo campo `_note` que `_publish` usa para o estado da FONTE, e o
#: vaivem `attached` -> `declared` -> `attached` publicava duas linhas por volta
#: que nao diziam nada de novo. O estado passa a sair na MUDANCA, com um
#: batimento lento para o oraculo poder provar que a fonte ainda respira.
_STATE_HEARTBEAT_S = 60.0

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


def rows_for(snap, vid):
    """A foto em maos ja' tem LINHAS do video `vid`? -- a evidencia que dispensa
    o damp de confirmacao.

    E' a pergunta que o `rebind_verdict` faz e que a shell nao tem como fazer
    sozinha: `rows` so' existe dentro da foto da CDP. Uma linha do player e'
    evidencia de que aquela aba esta' a pintar AQUELE video -- nao e' uma
    leitura de instrumento a confirmar.
    """
    if not isinstance(snap, dict) or not vid:
        return False
    if str(snap.get("videoId") or "") != str(vid):
        return False
    return bool(snap.get("rows") or ())


def rebind_verdict(declared, candidate, armed, age_s, confirm_s, snap=None):
    """(acao, porque) -- quando o damp de `confirm_s` pode ser dispensado.

    O DEFEITO MEDIDO (log do dono, 2026-11-11 17:35, troca de aba as 45.193):
    `YOUTUBE_TARGET_REBIND_ARMED ... confirm_s=1.5` as 45.296 e doze
    `YOUTUBE_TARGET_REBIND_DAMPED` ate' `YOUTUBE_TARGET_REBOUND` as 46.837 --
    **1,541 s** entre o alvo novo ser conhecido e a shell acreditar nele. Na
    mesma sessao, 17:46:05.721 -> 10.203, o mesmo damp custou 4,482 s (1,5 s
    dele de espera e o resto de laco preso em 15 tentativas de attach).

    O damp existe por uma razao medida (2026-11-09): com duas abas `watch`
    abertas o `target_video_id` OSCILA, e cada oscilacao apagava a legenda. Mas
    uma oscilacao nao traz linhas: quando o player JA' esta' a pintar o
    candidato (`rows_for(snap, candidate)`), ele nao e' uma leitura de
    instrumento a confirmar, e' o alvo -- e a primeira cue dele nao pode pagar
    1,5 s de desconfianca.

    `acao` em `clear` | `armed` | `adopt` | `damped`, exactamente as quatro
    decisoes que o bloco inline de `sotto_webview._yt_identify` toma hoje:
    `clear` mata o candidato, `armed` arma-o agora, `adopt` troca de video neste
    tick, `damped` espera. Pura de proposito: a shell so' obedece, e
    `_main/youtube-first-cue-oracle.py` executa ESTA funcao.
    """
    declared = str(declared or '')
    candidate = str(candidate or '')
    if not candidate or candidate == declared:
        return 'clear', 'no-candidate'
    if rows_for(snap, candidate):
        return 'adopt', 'rows-ready'
    if candidate != str(armed or ''):
        return 'armed', 'new-candidate'
    if float(age_s or 0.0) >= float(confirm_s or 0.0):
        return 'adopt', 'confirmed'
    return 'damped', 'confirming'


#: UMA FONTE VIVA POR PROCESSO -- e a razao e' medida (2026-11-09).
#:
#: No log do dono, numa janela de 600 s: `YOUTUBE_CDP_SOURCE state=attached`
#: **675 vezes** e `YOUTUBE_TARGET pick=...` **712 vezes**, todas identicas, a
#: ~1,1/s. As duas linhas sao deduplicadas DENTRO do objeto (`_publish` compara
#: `self._note`, `_log_target` compara `self._target_text`), logo 675 copias da
#: mesma linha significam 675 OBJETOS: algo constroi uma `CdpCaptionSource` por
#: volta, cada uma a arrancar dois fios (`_run` + `_tid_run`) e a pagar a
#: `/json/list` do arranque. O custo apareceu no stutter de 11:5x (o watcher
#: mediu 81,3 %c na shell python; o worker era outro caminho).
#:
#: O registo resolve na ORIGEM, nao no sintoma: uma fonte viva e' devolvida a
#: quem a pede, em vez de nascer uma segunda. E' o mesmo contrato que o
#: `_yt_cdp_ensure` ja' tentava cumprir com `self._yt_cdp_source`, mas aquele
#: memo morre com o objeto que o guarda (o watcher e a shell sao dois).
_LIVE_LOCK = threading.Lock()
_LIVE_SOURCE = None


def live_source(factory, log=None):
    """A fonte viva do processo; cria uma so' com `factory` quando nao ha'.

    `factory` e' chamado DENTRO do lock e so' quando e' preciso -- o chamador
    passa `lambda: CdpCaptionSource(log=log)`, portanto uma segunda construcao
    nunca acontece por descuido.
    """
    global _LIVE_SOURCE
    with _LIVE_LOCK:
        src = _LIVE_SOURCE
        if src is not None:
            return src
        src = factory()
        _LIVE_SOURCE = src
        return src


def live_source_clear(src=None):
    """Esquecer a fonte -- so' quando ela morreu mesmo (stop/falha de arranque)."""
    global _LIVE_SOURCE
    with _LIVE_LOCK:
        if src is None or _LIVE_SOURCE is src:
            _LIVE_SOURCE = None


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
        #: O MOTIVO DA ESCOLHA DE ABA, separado do estado da FONTE (2026-11-09):
        #: os dois viviam no mesmo campo e o vaivem publicava duas linhas por
        #: volta que nao diziam nada de novo.
        self._choice_note = ""
        self._note_log_t = 0.0
        self._target_text = None
        self._target_log_t = 0.0
        self._reads = 0
        self._errors = 0
        self._last_error = ""
        self._video_id = ""
        #: QUEM TOCA ja' foi decidido (2026-11-04): o id da escolha por
        #: `choose_playing`, para `sticky-last` na leitura seguinte, e a hora
        #: dessa escolha (a sonda por aba e' cara e tem TTL).
        self._playing_pick = ""
        self._playing_pick_cache = None
        #: A ABA ESCOLHIDA NESTE INSTANTE (2026-11-06). `_tab_key` e' a
        #: identidade da ligacao (o ws da aba) e `_selected_video_id` o video
        #: dela: uma troca de aba zera a foto publicada (ver `_adopt_tab`), para
        #: a legenda do video anterior nunca ser servida como a do novo.
        self._tab_key = ""
        self._selected_video_id = ""
        #: A IDENTIDADE DA ABA, CONTADA (2026-11-11). `_adopt_tab` incrementa
        #: `_epoch` quando a aba escolhida muda e o socket guarda o epoch com que
        #: foi aberto (`_sock_epoch`): um socket de OUTRA aba nao esta' lento nem
        #: morto, esta' a falar do video errado -- ver `_stale_socket`.
        self._epoch = 0
        self._sock_epoch = 0
        #: O SOCKET VIVO, para o REFRESCADOR o poder fechar (2026-11-11). E' o
        #: unico objecto que atravessa os dois fios de proposito: `_run` e' quem
        #: o abre, `_adopt_tab` quem o fecha quando a aba que ele serve deixa de
        #: ser a escolhida (ver o comentario la').
        self._conn = None
        #: O VIDEO DAS LINHAS PUBLICADAS E A ABA ONDE FOI LIDO (2026-11-11):
        #: `stats()['snap_vid']` responde "de que video sao estas linhas?" com a
        #: foto, e `video_change_evidence` compara a aba do id anterior para a
        #: shell nao chamar TROCA DE VIDEO a uma troca de aba.
        self._snap_vid = ""
        self._snap_vid_tab = ""
        self._change_vid = ""
        self._change_evidence = ""
        #: O titulo da janela que o dono esta' a ver. Com duas abas `watch`, e'
        #: isto -- nao o id -- que decide qual delas ler (`pick_target`).
        self._window_title = ""
        #: O ALVO PUBLICADO PELO FIO (2026-11-08): `(hora, video_id)` e a
        #: cadencia corrente (`_TID_TTL_S`, ou `_TID_SLOW_TTL_S` depois de uma
        #: chamada lenta). `target_video_id()` so' LE' isto -- quem paga o
        #: `/json/list` e' `_tid_run`, fora do laco de leitura.
        self._tid_cache = None
        self._tid_ttl = _TID_TTL_S
        self._tid_thread = None
        self._tid_refreshes = 0
        #: O PEDIDO DE UMA VEZ QUE O LACO PODE ENTREGAR AO REFRESCADOR (2026-11-09):
        #: `(Event, holder)` ou None, e o `Event` que o acorda do `wait`.
        self._tid_inline_job = None
        self._tid_wake = threading.Event()
        self._tid_inline_at = 0.0
        self._tid_stale_at = 0.0
        self._snap_stale_at = 0.0

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
        # O FIO DO ALVO ARRANCA COM A FONTE (2026-11-08) e para no `stop()`
        # dela: um fio por fonte, sem fugas. Ele fica INERTE (zero pedidos) ate'
        # `_run` marcar a ligacao -- uma fonte que nunca ligou nao arranca
        # trabalho nenhum, so' existe a espera.
        self._stop.clear()
        self._tid_wake.clear()
        self._tid_start()
        if self._thread is not None and self._thread.is_alive():
            return self
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

    def _log_target(self, text):
        """`YOUTUBE_TARGET` so' quando a ESCOLHA muda (ou no batimento lento).

        MEDIDO 2026-11-09: 6 513 linhas `pick=... why=declared declared=...` nos
        ultimos 2 MB do log do dono, identicas. A escolha de aba e' um estado --
        o mesmo id, o mesmo motivo, as mesmas abas -- e repeti-la 8 vezes por
        segundo custa I/O e esconde a linha que importa. A primeira escolha sai
        sempre; depois so' a mudanca, mais uma por minuto para o oraculo poder
        provar que a fonte ainda respira.
        """
        now = time.monotonic()
        if (text == self._target_text
                and now - self._target_log_t < _STATE_HEARTBEAT_S):
            return
        self._target_text = text
        self._target_log_t = now
        self._log(text)

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
            self._choice_note = str(why)
            self._adopt_tab(tab, vid)
            self._log_target('YOUTUBE_TARGET pick=%s why=%s declared=%s tabs=%d'
                             % (vid or '-', why, self._video_id or '-',
                                len(tabs or ())))
            return tab, why
        target, why2 = pick_target(tabs, self._video_id, self._window_title)
        if target is not None:
            self._choice_note = 'probe:%s fallback:%s' % (why, why2)
            self._adopt_tab(target, video_id_from_url(target.get('url') or ''))
            self._log_target('YOUTUBE_TARGET fallback pick=%s why=%s probe=%s tabs=%d'
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
            self._choice_note = why
            self._adopt_tab(target, video_id_from_url(target.get('url') or ''))
            self._log_target('YOUTUBE_TARGET stale pick=%s why=%s declared=%s tabs=%d'
                             % (video_id_from_url(target.get('url') or '') or '-',
                                why, self._video_id or '-', len(tabs or ())))
            return target, why
        self._choice_note = str(why or why2)
        return None, self._choice_note

    def _playing_pick_for(self, tabs):
        """(aba, id, motivo) da escolha por 'a tocar', com cache curta.

        Uma escolha feita ha' menos de `PLAYING_PROBE_TTL_S` e que ainda esteja
        na lista de abas vale sem sonda nenhuma -- o resolvedor de id pergunta a
        lista de 2 em 2 s e uma sonda por aba a esse ritmo seria trabalho
        emprestado ao dono (a queixa e' sempre a mesma: o PC a travar).

        A CACHE TEM UMA CHAVE ALEM DO TEMPO (2026-11-06): a ASSINATURA da lista
        de abas. Uma aba NOVA invalida a escolha na hora, e com duas ou mais
        abas o TTL cai para `PLAYING_PROBE_TTL_MULTI_S` (1 s) para um alt-tab
        devolver a prioridade dentro de uma leitura -- sem isto a legenda ficava
        ate' 10 s no video anterior (`YOUTUBE_TARGET ... why=declared tabs=2`).
        """
        now = time.monotonic()
        sig = tuple(sorted(str((t or {}).get('url') or '') for t in (tabs or ())))
        ttl = (PLAYING_PROBE_TTL_S if len(sig) <= 1
               else PLAYING_PROBE_TTL_MULTI_S)
        cached = getattr(self, '_playing_pick_cache', None)
        if cached and len(cached) >= 4 and cached[3] == sig:
            # O TTL VIAJA COM A ESCOLHA (2026-11-09): uma sonda que custou o
            # orcamento inteiro (aba congelada) nao se repete de 1 em 1 s.
            _ttl = cached[4] if len(cached) >= 5 else ttl
            if now - cached[0] < _ttl:
                _vid = cached[1]
                if _vid:
                    for tab in tabs or ():
                        if _vid in str(tab.get('url') or ''):
                            return tab, _vid, cached[2]
        t0 = time.monotonic()
        try:
            tab, vid, why = pick_playing(
                tabs, getattr(self, '_playing_pick', '') or '',
                connect=getattr(self, '_probe_connect', None),
                timeout=PROBE_TIMEOUT_S, budget_s=PROBE_BUDGET_S,
                log=self._log,
                window_title=getattr(self, '_window_title', '') or '',
                declared=getattr(self, '_video_id', '') or '')
        except Exception as exc:              # noqa: BLE001
            self._log('YOUTUBE_PLAYING_PICK_FAILED error=%r' % (exc,))
            return None, '', 'probe-failed'
        # A SONDA CARA NAO SE REPETE DE 1 EM 1 s (2026-11-09, MEDIDO): com uma
        # aba congelada cada sonda custa o orcamento inteiro e a evidencia nao
        # muda (o renderer continua sem responder). Nesse regime o cache vale
        # `PLAYING_PROBE_SLOW_TTL_S`; uma sonda barata continua a valer 1 s por
        # duas abas, que e' o contrato do alt-tab.
        _cost_ms = (time.monotonic() - t0) * 1000.0
        _ttl = (PLAYING_PROBE_SLOW_TTL_S if _cost_ms > PROBE_SLOW_MS else ttl)
        self._playing_pick_cache = (now, vid, why, sig, _ttl)
        self._probe_cost_ms = _cost_ms
        return tab, vid, why

    def selected_video_id(self):
        """O id do video da aba que a SONDA escolheu por ultimo ('' sem escolha).

        Existe para o laco da shell distinguir duas coisas que o campo `videoId`
        da foto nao distingue: "a foto e' de outro video porque a minha crenca
        envelheceu" (`seen == selected` -> adotar) e "a foto e' de outro video
        porque estou ligado a aba errada" (`refuse`).
        """
        return str(getattr(self, '_selected_video_id', '') or '')

    def _adopt_tab(self, tab, vid):
        """A ABA MUDOU -> NADA DA ANTERIOR PODE SER SERVIDO (2026-11-06).

        Um primeiro plano de outro video tem de ser imediato E limpo. A foto
        publicada era do video anterior e `snapshot()` a devolveria ate' a
        primeira leitura da aba nova -- ou seja a legenda de um video no ecra de
        outro, que e' o único erro que `adopt_decision` existe para impedir.
        `_selected_video_id` e' o que a shell usa para aceitar a foto nova.
        """
        if not isinstance(tab, dict):
            return
        key = str(tab.get('webSocketDebuggerUrl') or
                  video_id_from_url(tab.get('url') or '') or '')
        if not key:
            return
        old = str(getattr(self, '_tab_key', '') or '')
        if key != old:
            with self._lock:
                self._snap = None
            # A TROCA DE ABA INVALIDA O SOCKET (2026-11-11, MEDIDO). Quem
            # descobre a troca e' ESTE metodo, chamado pelo refrescador ou pelo
            # `_connect`; quem esta' preso num `recv` do socket antigo e' o
            # `_run`. O contador e' o unico sinal que atravessa os dois fios sem
            # partilhar o socket: `_run` compara-o com o epoch com que abriu a
            # ligacao (`_sock_epoch`) e re-liga na primeira volta.
            self._epoch = int(getattr(self, '_epoch', 0)) + 1
            self._log('YOUTUBE_CDP_TAB_SWITCH from=%s to=%s vid=%s'
                      % (old.rsplit('/', 1)[-1] or '-',
                         key.rsplit('/', 1)[-1] or '-', vid or '-'))
            # E O SOCKET DA ABA ANTIGA FECHA-SE AQUI (2026-11-11, MEDIDO). O
            # epoch sozinho so' vale na volta SEGUINTE do `_run`; se o `_run`
            # estiver DENTRO do `recv` (que e' onde ele passa 3 s), essa volta
            # so' chega depois do prazo. MEDIDO no log: a troca das 17:35:45.193
            # e o primeiro prazo as 47.914 -- 2,72 s de um `recv` a esperar por
            # uma aba que ja' nao era a escolhida. `close()` de outro fio faz o
            # `recv` levantar JÁ, e o ramo `_slow` re-liga no primeiro erro.
            _conn = getattr(self, '_conn', None)
            self._conn = None
            self._hard_close(_conn)
        self._tab_key = key
        self._selected_video_id = str(vid or '')

    def stop(self):
        self._stop.set()
        # O REFRESCADOR ACORDA PARA MORRER (2026-11-09): sem isto ele dorme o
        # `wait(0.25)` do ramo sem ligacao antes de ver o `_stop`.
        self._tid_wake.set()

    def _recheck_target(self):
        """A LISTA AINDA DIZ QUE O ALVO E' O NOSSO? -- perguntado no 1o prazo.

        O EPOCH E' SO' TAO NOVO QUANTO O REFRESCADOR (2026-11-11, MEDIDO). A
        troca de aba das 17:35:45.193 foi vista pelo refrescador (0,5 s de
        cadencia) e o `_adopt_tab` fechou o socket -- mas quando o refrescador
        NAO ve' a troca (titulo igual, duas abas do mesmo canal), o epoch nao
        muda e o `_run` espera os tres prazos do `slow-dead` mais `RETRY_S`:
        8,482 s no log, com a lista de abas a 1,0-1,4 s de distancia (HTTP).

        A pergunta e' barata e NAO sonda jogador nenhum (`pick_target` decide
        por URL/id/titulo): se a aba escolhida agora nao e' a que este socket
        serve, adota-se e re-liga-se JÁ. Um socket que nao responde e cuja aba
        mudou nao esta' lento -- esta' a falar do video errado.
        """
        try:
            tabs, _others = list_targets(self.port,
                                         timeout=ATTACH_PROBE_TIMEOUT_S)
        except Exception as exc:                  # noqa: BLE001
            self._error(exc)
            return False
        title = str(getattr(self, '_window_title', '') or '')
        target, _why = pick_target(tabs, str(getattr(self, '_video_id', '') or ''),
                                   title)
        if target is None and tabs:
            target, _why = pick_target(tabs, '', title)
        if not isinstance(target, dict):
            return False
        key = str(target.get('webSocketDebuggerUrl') or '')
        if not key or key == str(getattr(self, '_tab_key', '') or ''):
            return False
        vid = video_id_from_url(target.get('url') or '')
        self._adopt_tab(target, vid)
        self._publish(None, 'target-moved (%s)' % (vid or '-'))
        return True

    def _stale_socket(self):
        """O socket em maos aponta para uma aba que ja' nao e' a escolhida?

        A TROCA DE ABA INVALIDA O SOCKET -- NAO E' UMA PAGINA LENTA (2026-11-11,
        MEDIDO). Quem descobre a troca e' `_adopt_tab` (pelo refrescador, ou pelo
        `_connect`), e o socket antigo nao tem como responder pelo alvo: ele fala
        da aba anterior. MEDIDO no log do dono, troca as 17:35:45.193 conhecida
        pelo refrescador (`YOUTUBE_CDP_TAB_SWITCH`), `_run` continuou ligado a'
        aba antiga, o primeiro prazo saiu as 47.914, o terceiro as 54.018
        (`slow-dead`), mais 2,0 s de `RETRY_S` ate' ao `ATTACH_OK` as 56.396 --
        **11,2 s** desde a troca, com o alvo ja' conhecido e zero leituras dele.

        O segundo defeito da mesma causa, 17:46: `ConnectionAbortedError` num
        socket que ficara' para tras, e a foto dele (outro video) publicada como
        se fosse a do alvo -- o `YOUTUBE_TICK_MS` passou minutos a nomear
        `zEgthOmOrc0` com as linhas a virem de outro sitio.
        """
        return int(getattr(self, '_sock_epoch', 0) or 0) != int(
            getattr(self, '_epoch', 0) or 0)

    def snap_vid(self):
        """O `videoId` da ULTIMA foto publicada -- o video das LINHAS em maos.

        Existe porque `YOUTUBE_TICK_MS`/`YOUTUBE_CDP_HEALTH` nomeavam o video de
        um ramo antigo (`vid='zEgthOmOrc0'` com `YT_FRAME
        src=external:youtube:track` a pintar outro). A resposta certa para "de
        que video sao estas linhas?" esta' na foto, nao no ultimo `_yt_diag`.
        """
        return str(getattr(self, '_snap_vid', '') or '')

    def video_change_evidence(self, vid):
        """Como o video `vid` apareceu: `same-tab` | `tab-switch` | `none`.

        `YOUTUBE_VIDEO_CHANGED` so' pode sair com evidencia de troca de video --
        e trocar de ABA nao e' trocar de video (2026-11-11, MEDIDO): com sete
        abas abertas o picker adotou `JM1gEnmaUao` (`why=paused-loaded`), a shell
        aceitou-o e imprimiu `YOUTUBE_VIDEO_CHANGED video_id=JM1gEnmaUao` com o
        dono a ver outro video -- a adocao FABRICOU a mudanca que depois
        reportou. Aqui a evidencia fica do lado que a tem: a foto que publicou o
        id anterior e a aba em que ela foi lida.
        """
        cur = str(vid or '')
        if not cur or cur != str(getattr(self, '_change_vid', '') or ''):
            return 'none'
        return str(getattr(self, '_change_evidence', '') or 'none')

    def _note_video(self, snap):
        """A evidencia da troca de video, gravada no instante da publicacao.

        `same-tab` quando o id ANTERIOR foi lido na mesma aba (`_tab_key`), que
        e' a navegacao real (`/watch?v=` novo no mesmo separador); `tab-switch`
        quando a aba mudou pelo caminho. Grava-se junto com a foto para a shell
        nao ter de reconstruir isto a partir de dois campos que ja' mudaram.
        """
        vid = str((snap or {}).get('videoId') or '')
        if not vid or vid == str(getattr(self, '_snap_vid', '') or ''):
            return
        _prev_tab = str(getattr(self, '_snap_vid_tab', '') or '')
        self._snap_vid = vid
        self._snap_vid_tab = str(getattr(self, '_tab_key', '') or '')
        self._change_vid = vid
        self._change_evidence = (
            'same-tab' if (_prev_tab and _prev_tab == self._snap_vid_tab)
            else 'tab-switch')

    def stats(self):
        with self._lock:
            return {"reads": self._reads, "errors": self._errors,
                    "last_error": self._last_error, "note": self._note,
                    "choice": self._choice_note, "snap_vid": self.snap_vid(),
                    #: O EPOCH DA ABA (2026-11-11): um valor novo significa "a aba
                    # escolhida mudou". A shell usa-o para nao segurar o passo do
                    # laco (`READ_SLOW_HOLD_S`) em cima de um alvo recem-chegado.
                    "epoch": int(getattr(self, '_epoch', 0) or 0)}

    # -- leitura ----------------------------------------------------------
    def snapshot(self, max_age=0.6):
        """A ultima foto, se for RECENTE. Sem foto recente devolve None."""
        self._last_use = time.monotonic()
        with self._lock:
            snap = self._snap
        if snap is None:
            return None
        _age = time.monotonic() - snap["stamp"]
        if _age > max_age:
            # A FOTO QUE EXISTE E NAO SERVE TEM NOME (2026-11-09, MEDIDO).
            # 8,3 s de leitura no log do dono (`phases={'target': 8281.0}`) sao
            # o caminho UIA que o shell paga quando esta funcao devolve None --
            # `_yt_source_by_title(max_age=3.0)` desiste, o veredicto da janela
            # expira e `external_subs.player_source` (UIA) e' chamado com o
            # Chrome a 100 %. A idade da foto e' a causa que faltava no log.
            now = time.monotonic()
            if now - getattr(self, '_snap_stale_at', 0.0) >= _TARGET_STALE_LOG_S:
                self._snap_stale_at = now
                self._log('YOUTUBE_SNAPSHOT_STALE age_ms=%.0f max_age_ms=%.0f '
                          'note=%s' % (_age * 1000.0, float(max_age) * 1000.0,
                                       self._note or '-'))
            return None
        return snap

    def target_video_id(self):
        """O id da aba que `pick_target` escolheu -- LIDO DA MEMORIA (2026-11-08).

        E' a resposta que o caso de TRES abas `watch` pedia (medido 2026-11-03:
        `stats={'reads': 0, 'note': 'ambiguous'}` por minutos, e a legenda parada,
        enquanto a fonte esperava um id que ninguem lhe dava). O id sai do URL da
        aba escolhida pelo TITULO DA JANELA -- nada de UIA, nada de varrer a
        arvore.

        O QUE MUDOU A 2026-11-08 (MEDIDO na instancia viva pid 42572, este log):
        `EXTERNAL_CAPTIONS_READ_MS ms=1281.0 phases={'cdp': 15.0, 'vid':
        1281.0}` -- a volta inteira cabia entre o `cdp` e o `vid`, e o unico
        trabalho ali era `list_targets` (`/json/list`, 1000-1400 ms no Chrome
        carregado do dono). De ~10 em ~10 s o laco nao produzia um unico quadro
        durante mais de um segundo. Agora a pergunta e' paga pelo FIO
        `yt-cdp-target` (`_tid_run`), que publica `(hora, id)` em `_tid_cache`;
        aqui resta uma leitura de memoria, sem I/O e sem bloqueio.

        A IDADE E' LIMITADA, E ONDE: o fio publica a cada `_tid_ttl` (`_TID_TTL_S`
        = 0,5 s; esticado para `_TID_SLOW_TTL_S` = 10 s depois de uma chamada
        lenta) e um `urlopen` nao passa do seu proprio prazo (`list_targets`,
        3,0 s). Logo o id devolvido tem no maximo `cadencia + ms da chamada`:
        <= 1,9 s no caminho normal (0,5 s + 1,4 s medidos) e <= 11,4 s no
        regime lento. A troca de video chega ao shell dentro dessa janela, pela
        linha `YOUTUBE_TARGET_REBOUND` que ja' existia.

        UMA FONTE SEM VALOR PUBLICADO AINDA (o primeiro pedido, ou um duplo de
        teste que nunca chamou `start()` -- braco STALE-ID de
        `_main/yt-target-stale-oracle.py`) responde-se aqui, uma vez: um ''
        faria o shell pagar a varredura UIA de 94-109 ms, que e' a doenca que
        este caminho existe para evitar. `_tid_refresh` grava o cache mesmo
        quando a resposta e' '' (porta morta), logo um segundo pedido nunca
        volta a fazer I/O: a partir da primeira publicacao toda a chamada e'
        leitura de memoria.
        """
        now = time.monotonic()
        # SEM LIGACAO RECENTE NAO HA' ALVO A SONDAR (2026-11-05, MEDIDO na
        # instancia viva pid 20236). Com o browser sem porta de depuracao esta
        # chamada gastava **2000 ms** de 10 em 10 s -- o log diz
        # `YOUTUBE_TARGET_SLOW ms=2000 vid=- ttl_s=10` em serie -- para
        # perguntar a um porto morto que abas existem, e a resposta nao podia
        # ser outra. A falha de attach ja' e' um facto datado (`_attach_log`):
        # enquanto ela for recente e nao houver ligacao, a resposta e' de graca.
        # NADA DE CACHE AQUI: a hora da falha e' o unico estado, e escrever um
        # '' no cache faria a primeira leitura depois de a porta voltar a
        # responder devolver o vazio antigo.
        _failed = getattr(self, '_attach_failed_at', None)
        if (_failed is not None and not getattr(self, '_attached', False)
                and now - _failed < 30.0):
            return ''
        cached = getattr(self, '_tid_cache', None)
        if cached is not None:
            # A IDADE E' UM FACTO, NAO UM SILENCIO (2026-11-09). O valor sai da
            # memoria em microssegundos -- mas um valor que o refrescador devia
            # ter substituido e nao substituiu e' uma testemunha que faltava: foi
            # por nao haver linha nenhuma que 94 s de foto velha passaram por
            # `cdp_age_ms=94484` sem nome. O limite e' o DOBRO da cadencia
            # prometida (uma volta perdida), e a linha e' limitada a uma por
            # `_TARGET_STALE_LOG_S` para nao virar o log que ela denuncia.
            self._tid_stale_note(now - cached[0])
            return cached[1]
        # A PRIMEIRA PERGUNTA ESPERA -- COM PRAZO (2026-11-09, MEDIDO).
        # `EXTERNAL_CAPTIONS_READ_MS ms=33281.0 phases={'target': 33281.0, ...}`
        # no log do dono, as 19:31, repetido as 19:42 e as 19:56: a leitura
        # INTEIRA presa em `target`, porque o cache nasce vazio em cada objeto
        # novo e a resposta era `self._tid_refresh()` -- um `/json/list` pago no
        # fio do LACO, com o Chrome dele a 100 % de um nucleo. Trinta e tres
        # segundos de laco entregues a' contencao do browser, e a thread da UI a
        # nao responder (`UI_HUNG reason=caption-read-slow`, 5 vezes na noite).
        #
        # A EXCECAO E' A FONTE QUE NAO PODE PUBLICAR: sem ligacao o fio
        # `yt-cdp-target` fica INERTE por desenho (ele nao faz um pedido antes de
        # `_run` marcar `_attached`), logo esperar por ele aqui seria esperar por
        # quem nao vai falar -- e um porto morto responde depressa. Nesse caso a
        # pergunta e' paga por quem pergunta, uma vez, como sempre foi (arms
        # STALE-ID do `yt-target-stale-oracle` e A5 do `youtube-cdp-slow-oracle`
        # julgam exactamente isto).
        # A FONTE QUE NAO PODE PUBLICAR NAO PODE PRENDER O LACO (2026-11-09,
        # MEDIDO). O texto acima deixava `self._tid_refresh()` -- a pergunta
        # INTEIRA, com a sonda de "quem toca" (`probe_tabs`, um prazo por aba)
        # -- correr no fio do CHAMADOR. No log do dono isso e'
        # `EXTERNAL_CAPTIONS_READ_MS ms=1000.0 phases={'target': 16.0,
        # 'source': 1000.0}` as 21:17:53: 984 ms dentro de `target_video_id`,
        # numa leitura, com a fonte momentaneamente desligada (ciclo
        # `slow-dead`). A pergunta agora corre num fio `yt-cdp-inline` proprio,
        # com `_TID_INLINE_WAIT_S` de tecto, e NUNCA sonda WebSocket: sem
        # ligacao nao ha' `_run` para ler a aba, e a resposta que interessa ao
        # chamador e' so' "ha' uma aba `watch`?" -- `list_targets` + `pick_target`.
        _was_alive = (self._tid_thread is not None
                      and self._tid_thread.is_alive())
        self._tid_start()
        if not getattr(self, '_attached', False):
            if not _was_alive:
                # A FONTE QUE NUNCA ARRANCOU (2026-11-09, MEDIDO pelo
                # `yt-target-stale-oracle`): um objecto recem-construido, um
                # duplo de teste -- o chamador quer a resposta AGORA e nao ha'
                # fio nenhum para a entregar. A pergunta e' BARATA por desenho
                # (`probe=False`: lista + URL/titulo, sem WebSocket), e o unico
                # I/O e' o `/json/list` local medido em 1,5-13 ms. O caminho do
                # APP nunca cai aqui: `live_source` devolve uma fonte ja'
                # arrancada.
                try:
                    return self._tid_refresh(probe=False)
                except Exception:             # noqa: BLE001
                    return ''
            return self._tid_inline()
        _until = time.monotonic() + _TID_WAIT_S
        while time.monotonic() < _until:
            cached = getattr(self, '_tid_cache', None)
            if cached is not None:
                return cached[1]
            self._stop.wait(0.02)
        self._tid_waits = int(getattr(self, '_tid_waits', 0)) + 1
        if self._tid_waits in (1, 10, 100) or self._tid_waits % 500 == 0:
            self._log('YOUTUBE_TARGET_UNPUBLISHED waits=%d wait_s=%.2f '
                      'attached=%s' % (self._tid_waits, _TID_WAIT_S,
                                       bool(getattr(self, '_attached', False))))
        return ''

    # -- a idade do id e a pergunta sem ligacao ---------------------------
    def _tid_stale_note(self, age_s):
        """A IDADE DO ID, quando ela passa do que o refrescador prometeu.

        `age_s` e' o tempo desde a ultima publicacao. O refrescador publica a
        cada `_tid_ttl`; duas cadencias sem uma linha nova significa que ele
        esta' preso (aba congelada, `list_targets` a estourar, o fio morto), e
        o valor que o laco esta' a servir e' mais velho do que o contrato. Sai
        no maximo uma linha por `_TARGET_STALE_LOG_S` -- medir nao pode custar
        o log que se esta' a tentar salvar.
        """
        try:
            ttl = float(getattr(self, '_tid_ttl', _TID_TTL_S) or _TID_TTL_S)
            if age_s <= ttl * 2.0:
                return
            now = time.monotonic()
            if now - getattr(self, '_tid_stale_at', 0.0) < _TARGET_STALE_LOG_S:
                return
            self._tid_stale_at = now
            self._log('YOUTUBE_TARGET_STALE age_ms=%.0f ttl_s=%.1f attached=%s '
                      'refreshes=%d' % (age_s * 1000.0, ttl,
                                        bool(getattr(self, '_attached', False)),
                                        int(getattr(self, '_tid_refreshes', 0))))
        except Exception:                     # noqa: BLE001
            pass

    def _tid_inline(self):
        """UMA pergunta SEM LIGACAO, com tecto de relogio, fora do fio do laco.

        Sem `_run` a ler uma aba, a unica pergunta que tem resposta e' a LISTA
        (`list_targets`): ha' um `youtube.com/watch`? O `pick_target` decide com
        o URL/titulo, sem sondar WebSocket nenhum -- a sonda custa um prazo por
        aba e sem ligacao nao ha' foto para ela desbloquear.

        A PERGUNTA E' ENTREGUE AO FIO `yt-cdp-target` (2026-11-09, MEDIDO).
        Um fio novo por chamada parecia inofensivo, mas `Thread.start()` espera
        o fio ARRANCAR: medido neste oraculo, 240-340 ms numa maquina carregada
        -- ou seja o "tecto de 100 ms" era decorativo. O refrescador ja' existe
        e esta' vivo; ele atende o pedido, e o chamador espera num `Event` com
        prazo (`Event.wait(0.1)` acorda no instante). O pedido e' UM de cada
        vez (`_tid_inline_job`): o laco pode chamar isto 10 vezes por segundo e
        o Chrome leva, no maximo, uma `/json/list` de cada vez. O resultado
        passa pelo MESMO cache (`_tid_refresh(probe=False)` o escreve), logo a
        chamada seguinte e' leitura de memoria.
        """
        now = time.monotonic()
        if getattr(self, '_tid_inline_job', None) is not None:
            return ''
        if now - getattr(self, '_tid_inline_at', 0.0) < 0.05:
            return ''
        self._tid_inline_at = now
        done = threading.Event()
        holder = {}
        self._tid_inline_job = (done, holder)
        try:
            self._tid_wake.set()          # acorda o refrescador do `wait`
            if done.wait(_TID_INLINE_WAIT_S):
                return str(holder.get('vid') or '')
            # O VEREDICTO DA ESPERA: o chamador nao soube, e a linha diz isso.
            self._log('YOUTUBE_TARGET_INLINE_TIMEOUT wait_s=%.2f '
                      'attach_failed=%s'
                      % (_TID_INLINE_WAIT_S,
                         getattr(self, '_attach_failed_at', None) is not None))
            return ''
        finally:
            # O PEDIDO E' UM SO': se o refrescador ainda nao o pegou, ele morre
            # aqui em vez de pagar uma pergunta que ja' ninguem espera.
            self._tid_inline_job = None


    # -- o fio do alvo ----------------------------------------------------
    def _tid_start(self):
        """Um fio do alvo por fonte, e nunca dois."""
        if self._tid_thread is not None and self._tid_thread.is_alive():
            return
        self._tid_thread = threading.Thread(target=self._tid_run,
                                            name=_TID_THREAD_NAME, daemon=True)
        self._tid_thread.start()

    def _tid_run(self):
        """O REFRESCADOR: paga o `/json/list` FORA do laco de leitura.

        A CADENCIA E' A QUE O CACHE JA' TINHA (`_TID_TTL_S`, esticada para
        `_TID_SLOW_TTL_S` por `_tid_refresh`): o numero de pedidos ao Chrome
        nao mudou -- mudou o fio que os paga. Ele morre com `_stop` (`stop()`
        da fonte), logo nao ha' fio a sobreviver ao objeto.

        SEM LIGACAO NAO HA' O QUE PERGUNTAR: enquanto `_run` nao marcar a fonte
        como ligada este fio nao faz um unico pedido -- uma fonte que nunca
        ligou nao arranca trabalho nenhum -- e uma falha de attach recente
        (`_attach_failed_at`) suspende-o pela mesma janela de 30 s que
        `target_video_id` usa para nao sondar uma porta morta.
        """
        while not self._stop.is_set():
            # O PEDIDO DE UMA VEZ (2026-11-09): `target_video_id` sem ligacao
            # entrega aqui a pergunta -- sem `_attached` o laco abaixo ficaria
            # inerte e o chamador esperaria por quem nao ia falar. O pedido e'
            # atendido ANTES de qualquer guarda, porque e' ele que acorda o fio.
            job = getattr(self, '_tid_inline_job', None)
            if job is not None:
                self._tid_inline_job = None
                done, holder = job
                try:
                    holder['vid'] = self._tid_refresh(probe=False)
                except Exception as exc:  # noqa: BLE001
                    self._error(exc)
                    holder['vid'] = ''
                finally:
                    done.set()
                continue
            _failed = getattr(self, '_attach_failed_at', None)
            if not getattr(self, '_attached', False) or (
                    _failed is not None
                    and time.monotonic() - _failed < 30.0):
                # ACORDADO PELO PEDIDO, NAO PELO RELOGIO: sem este `Event` o
                # pedido esperava ate' 250 ms do `wait` -- metade do tecto que
                # `_TID_INLINE_WAIT_S` promete ao laco.
                self._tid_wake.wait(0.25)
                self._tid_wake.clear()
                continue
            try:
                self._tid_refresh()
            except Exception as exc:      # noqa: BLE001
                self._error(exc)
            self._stop.wait(max(0.1, float(
                getattr(self, '_tid_ttl', _TID_TTL_S) or _TID_TTL_S)))

    def _tid_refresh(self, probe=True):
        """UMA pergunta a' `/json/list`, publicada. Devolve o id publicado.

        E' o corpo que a 2026-11-08 vivia DENTRO de `target_video_id`, com o
        mesmo `_choose`, o mesmo cache e o mesmo sinal de lentidao -- so' que
        agora corre no fio do alvo. `YOUTUBE_TARGET_SLOW` continua a sair com
        os mesmos campos (`ms`, `vid`, `ttl_s`), acrescido de `src=refresher`:
        e' a testemunha de que a chamada lenta foi paga AQUI e nao no laco.

        `probe=False` e' a pergunta SEM LIGACAO (2026-11-09): so' a lista e o
        URL/titulo, nenhuma sonda de WebSocket, porque sem `_run` nao ha' foto
        a desbloquear. E' o que `_tid_inline` paga no fio dele.
        """
        vid = ''
        t0 = time.monotonic()
        try:
            tabs, _others = list_targets(
                self.port, timeout=(3.0 if probe else ATTACH_PROBE_TIMEOUT_S))
            if probe:
                target, why = self._choose(tabs)
            else:
                target, why = pick_target(tabs, self._video_id,
                                          self._window_title)
                if target is None and self._video_id:
                    # O ID DECLARADO NAO ESTA' ABERTO: QUEM MANDA SAO AS ABAS
                    # (a mesma queda do `_choose`, 2026-11-04 -- sem ela o
                    # objecto recem-construido responde '' e o shell paga a
                    # varredura UIA). Sem sonda nao ha' "aba errada" a temer:
                    # a escolha e' URL/titulo.
                    target, why = pick_target(tabs, '', self._window_title)
                    if target is not None:
                        why = 'stale-declared:' + str(why)
                if target is not None:
                    self._choice_note = 'inline:%s' % why
                    self._adopt_tab(target,
                                    video_id_from_url(target.get('url') or ''))
                    self._log_target(
                        'YOUTUBE_TARGET inline pick=%s why=%s tabs=%d'
                        % (video_id_from_url(target.get('url') or '') or '-',
                           why, len(tabs or ())))
            if target is None:
                self._choice_note = str(why)
            if target is not None:
                vid = video_id_from_url(target.get('url') or '')
        except Exception:                 # noqa: BLE001
            vid = ''
        # A CHAMADA QUE COMIA O TICK (2026-11-03, MEDIDO): `EXTERNAL_CAPTIONS_READ_MS`
        # publicou `phases={'vid': 1125.0}` com todas as outras a 0,0 -- um
        # `/json/list` de 1,1 s dentro do laco de leitura, e o laco perde os
        # quadros que caem nessa janela. A aba do dono troca de video de vez em
        # quando, nunca 12 vezes por minuto: quando a chamada passa de
        # `_TID_SLOW_MS`, a cadencia estica para `_TID_SLOW_TTL_S` e o custo vai
        # ao log.
        cost_ms = (time.monotonic() - t0) * 1000.0
        if cost_ms > _TID_SLOW_MS:
            self._tid_ttl = _TID_SLOW_TTL_S
            self._log('YOUTUBE_TARGET_SLOW ms=%.0f vid=%s ttl_s=%.0f '
                      'src=%s'
                      % (cost_ms, vid or '-', _TID_SLOW_TTL_S,
                         'refresher' if probe else 'inline'))
        else:
            self._tid_ttl = _TID_TTL_S
        self._tid_cache = (time.monotonic(), vid)
        self._tid_refreshes = int(getattr(self, '_tid_refreshes', 0)) + 1
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
                # A EVIDENCIA DA TROCA E' GRAVADA COM A FOTO (2026-11-11): quem
                # pergunta depois (`video_change_evidence`) nao tem como saber em
                # que aba o id anterior foi lido -- a aba ja' pode ter mudado.
                self._note_video(snap)
            if note is None:
                return
            now = time.monotonic()
            unchanged = note == self._note
            due = now - self._note_log_t >= _STATE_HEARTBEAT_S
            self._note = note
            if unchanged and not due:
                # A MESMA linha, 8 vezes por segundo, nao e' um estado: e' o laco
                # a escrever que nao mudou nada (medido 2026-11-09, 16 linhas/s).
                return
            self._note_log_t = now
            self._log("YOUTUBE_CDP_SOURCE state=%s" % note)

    def _error(self, exc):
        with self._lock:
            self._errors += 1
            self._last_error = "%s: %s" % (type(exc).__name__, exc)

    # -- a thread ---------------------------------------------------------
    def _hard_close(self, conn):
        """Fecha o socket de OUTRO fio, e acorda um `recv` preso nele.

        `close()` de outro fio NAO acorda um `recv` bloqueado em todas as
        plataformas; `abort()` (shutdown do socket) acorda. Quando o cliente nao
        tem `abort` -- ou ele falha -- o `close` e' o que ha', e o prazo do
        primeiro pedido (`FIRST_READ_TIMEOUT_S`) e' o que limita o estrago.
        """
        if conn is None:
            return
        abort = getattr(conn, 'abort', None)
        if abort is not None:
            try:
                abort()
                return
            except Exception:                 # noqa: BLE001
                pass
        try:
            conn.close()
        except Exception:                     # noqa: BLE001
            pass

    def _drop_conn(self, conn):
        """Fecha o socket e esquece-o -- o campo que o refrescador tambem ve'.

        `_run` e' o unico que ABRE ligacoes; `_adopt_tab` (noutro fio) e' o unico
        que as pode fechar antes do prazo (ver o comentario la'). Os dois passam
        por aqui para `self._conn` nunca apontar para um socket ja' fechado.
        """
        if conn is not None:
            self._hard_close(conn)
            if getattr(self, '_conn', None) is conn:
                self._conn = None
        return None

    def _run(self):
        try:
            import websocket            # websocket-client
        except Exception as exc:        # noqa: BLE001
            self._publish(None, "no-websocket-client (%s)" % type(exc).__name__)
            return
        conn = None
        while not self._stop.is_set():
            if conn is not None and self._stale_socket():
                # A ABA MUDOU DEBAIXO DESTE SOCKET (2026-11-11). Nao ha' nada a
                # perguntar-lhe: ele esta' ligado a' aba ANTERIOR. Fecha e re-liga
                # JA -- sem prazo, sem `RETRY_S`, sem passar pelos tres prazos do
                # `slow-dead`: o prazo de 3 s que sobra e' o do socket que a troca
                # apanhou a meio do `recv` (ver o ramo `_slow`).
                conn = self._drop_conn(conn)
                self._publish(None, 'tab-stale (aba trocada)')
                continue
            if time.monotonic() - self._last_use > IDLE_STOP_S:
                if conn is not None:
                    conn = self._drop_conn(conn)
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
                # O EPOCH COM QUE ESTE SOCKET NASCEU (2026-11-11): `_connect`
                # passou por `_choose`, que pode ter mudado de aba -- o socket e'
                # da aba escolhida AGORA, e e' este o numero que `_stale_socket`
                # compara depois.
                self._sock_epoch = int(getattr(self, '_epoch', 0) or 0)
                self._conn = conn
                #: A PROXIMA LEITURA E' A PRIMEIRA DESTA LIGACAO (2026-11-11):
                #: ver `FIRST_READ_TIMEOUT_S`. Cada attach re-arma o prazo curto.
                _first_read = True
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
                try:
                    conn.settimeout(FIRST_READ_TIMEOUT_S if _first_read
                                    else READ_TIMEOUT_S)
                except Exception:                 # noqa: BLE001
                    pass
                _first_read = False
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
                    if self._stale_socket():
                        # UM PRAZO NUM SOCKET DE OUTRA ABA NAO E' LENTIDAO
                        # (2026-11-11, MEDIDO). A aba trocou enquanto este
                        # `recv` esperava; esperar por mais dois prazos e por
                        # `RETRY_S` atrasava a primeira cue da aba nova em 8,5 s
                        # (17:35:47.914 -> 56.396). Re-liga no PRIMEIRO prazo.
                        self._slow_streak = 0
                        conn = self._drop_conn(conn)
                        self._publish(None, 'tab-stale (%s, 1 prazo)'
                                      % type(_slow).__name__)
                        continue
                    if (int(getattr(self, '_slow_streak', 0) or 0) == 0
                            and self._recheck_target()):
                        # A LISTA MUDOU E O EPOCH NAO (2026-11-11): um prazo
                        # chegou para saber que este socket nao serve o alvo.
                        self._slow_streak = 0
                        conn = self._drop_conn(conn)
                        continue
                    self._publish(None, 'slow (%s)' % type(_slow).__name__)
                    self._slow_streak = int(getattr(self, '_slow_streak', 0)) + 1
                    if self._slow_streak >= SLOW_STREAK_MAX:
                        # TRES PRAZOS SEGUIDOS NAO SAO "LENTA", SAO "MORTA": o
                        # mesmo socket nunca respondeu tres vezes. Fecha e
                        # re-liga, em vez de perguntar eternamente a um cano
                        # partido.
                        self._slow_streak = 0
                        conn = self._drop_conn(conn)
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
                if self._stale_socket():
                    # A FOTO E' DE OUTRA ABA (2026-11-11, MEDIDO). A troca
                    # aconteceu DURANTE este `recv`: publicar esta foto seria
                    # servir o video anterior/errado (17:46: `state=adopted:
                    # zEgthOmOrc0->JM1gEnmaUao` a partir de um socket abandonado),
                    # e a shell aceita-a porque o `_selected_video_id` do momento
                    # da troca ja' aponta para a aba nova. Descartar e re-ligar:
                    # a primeira foto legitima chega ~1 evaluate depois.
                    conn = self._drop_conn(conn)
                    self._publish(None, 'tab-stale (%s descartada)'
                                  % (snap.get("videoId") or '-'))
                    continue
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
                    conn = self._drop_conn(conn)
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
                # A ABA A QUE ESTAMOS LIGADOS E' AUTORIDADE (2026-11-06). O
                # `adopt_decision` protege contra ler a ABA ERRADA; quando a foto
                # vem da aba que a SONDA escolheu (`selected_video_id`), nao ha'
                # aba errada -- ha' uma crenca (`_video_id`) que envelheceu. Sem
                # isto, com duas abas o dono muda o foco para a nova, a fonte
                # escolhe-a, e `_run` recusa a foto dela porque o id declarado
                # (o video antigo, ainda aberto) continua "aberto": a legenda do
                # novo video nunca chega. A troca de estado e' limpa por
                # `_adopt_tab` (foto publicada zerada).
                if (_action == 'refuse'
                        and str(snap.get("videoId") or '')
                        == str(getattr(self, '_selected_video_id', '') or '')):
                    _action, _because = 'adopt', 'attached-tab'
                if _action == 'adopt':
                    _old = self._video_id
                    self._video_id = str(snap["videoId"])
                    self._playing_pick = self._video_id
                    self._playing_pick_cache = None
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
                    conn = self._drop_conn(conn)
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
                conn = self._drop_conn(conn)
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
                # PAUSA/PLAY RE-ESCOLHE A ABA (2026-11-06). O dono alterna entre
                # dois videos e pausa um deles: o que TOCA passa a ser o outro,
                # e uma escolha em cache nao pode sobreviver a essa mudanca.
                self._playing_pick_cache = None
                self._log('YOUTUBE_CDP_PACED paused=%s poll_s=%.2f'
                          % (_paused, _wait))
            if self._stale_socket():
                # O `paused` DESTA FOTO E' DO VIDEO ANTERIOR (2026-11-11). A aba
                # trocou durante a leitura: `PAUSED_POLL_S` (0,5 s) seria meio
                # segundo parado antes de ler a aba nova, e a primeira cue dela
                # ja' chega depois do attach. O passo nao se aplica a um alvo
                # novo -- a volta seguinte e' a que fecha e re-liga.
                _wait = 0.0
            self._stop.wait(max(0.0, _wait - spent))
        self._drop_conn(conn)

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
            conn.settimeout(READ_TIMEOUT_S)
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
