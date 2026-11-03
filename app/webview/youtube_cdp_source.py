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
import threading
import time
import urllib.request

#: Porta de depuracao que o Chrome do dono ja' tem aberta (medido 2026-11-03).
DEFAULT_PORT = 9222

#: Uma leitura a cada 80 ms. O custo medido de uma ida e volta com
#: `Runtime.evaluate` e' ~10 ms, e a legenda do player muda a cada 100-300 ms.
POLL_S = 0.08

#: Sem ninguem a pedir, a ligacao fecha-se passado isto (nao fica a gastar CPU
#: nem a segurar um socket quando o YouTube nao esta' a ser lido).
IDLE_STOP_S = 120.0

#: Espera entre tentativas depois de uma falha, para nao bater a porta a 12 Hz
#: quando o Chrome esta' fechado.
RETRY_S = 2.0

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
               t: v ? v.currentTime : null, paused: v ? v.paused : null};
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


def pick_target(tabs, video_id=""):
    """(aba, motivo). Uma aba so'; `ambiguous` quando nao se pode decidir."""
    if video_id:
        named = [t for t in tabs if video_id in str(t.get("url") or "")]
        if named:
            return named[0], "named"
        return None, "video-not-open"
    if not tabs:
        return None, "no-youtube-tab"
    if len(tabs) > 1:
        return None, "ambiguous"
    return tabs[0], "only-tab"


class CdpCaptionSource:
    """Le as linhas que o player desenha, em segundo plano, pela CDP.

    Uma thread, uma ligacao, uma leitura a cada `poll_s`. `snapshot()` e' barato
    e nunca bloqueia: devolve a ultima foto boa (ou None). Tudo o que pode falhar
    (porta fechada, aba fechada, Chrome a reabrir) esta' dentro da thread, e a
    aplicacao simplesmente continua com a UIA.
    """

    def __init__(self, port=DEFAULT_PORT, poll_s=POLL_S, log=None):
        self.port = int(port)
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

    # -- ciclo de vida ----------------------------------------------------
    def set_video_id(self, video_id):
        """Qual video o Sotto DECLARA ler. Com mais de uma aba aberta, so' esta."""
        self._video_id = str(video_id or "")

    def start(self):
        if self._thread is not None and self._thread.is_alive():
            return self
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="yt-cdp-source",
                                        daemon=True)
        self._thread.start()
        return self

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
                conn = self._connect(websocket)
                if conn is None:
                    self._stop.wait(RETRY_S)
                    continue
            t0 = time.monotonic()
            try:
                conn.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                      "params": {"expression": EXTRACT_JS,
                                                 "returnByValue": True}}))
                payload = None
                while True:                       # ignora eventos, espera o id
                    msg = json.loads(conn.recv())
                    if msg.get("id") == 1:
                        payload = ((msg.get("result") or {})
                                   .get("result") or {}).get("value")
                        break
                snap = parse_snapshot(payload)
                if snap is None:
                    raise ValueError("payload sem forma")
                # A ABA PODE NAVEGAR DEPOIS DE NOS LIGARMOS A ELA (2026-11-03,
                # MEDIDO: 7 abas do YouTube abertas, a ligacao presa numa e o
                # Sotto a ler outro video -- `refused=video-mismatch
                # declared=vwiIPjpksEU seen=NBCM_ZoWZo8`). Ler a aba errada e' o
                # unico erro que poe a legenda de um video no ecra de outro: a
                # ligacao cai e a proxima escolhe pelo ID.
                if (self._video_id and snap.get("videoId")
                        and snap["videoId"] != self._video_id):
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
            spent = time.monotonic() - t0
            self._stop.wait(max(0.0, self.poll_s - spent))
        if conn is not None:
            try:
                conn.close()
            except Exception:                     # noqa: BLE001
                pass

    def _connect(self, websocket):
        try:
            tabs, _others = list_targets(self.port)
        except Exception as exc:                  # noqa: BLE001
            self._error(exc)
            self._publish(None, "port-closed")
            return None
        target, why = pick_target(tabs, self._video_id)
        if target is None:
            self._publish(None, why)
            return None
        url = target.get("webSocketDebuggerUrl")
        if not url:
            self._publish(None, "no-ws-url")
            return None
        try:
            return websocket.create_connection(url, timeout=15.0)
        except Exception as exc:                  # noqa: BLE001
            self._error(exc)
            self._publish(None, "ws-failed")
            return None
