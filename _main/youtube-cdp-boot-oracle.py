# NO-BUG: Portao do ARRANQUE da fonte YouTube (CDP) -- `_main/youtube-cdp-boot-oracle.py`.
"""Portao do ARRANQUE da fonte YouTube (CDP) -- `_main/youtube-cdp-boot-oracle.py`.

O DEFEITO QUE ESTE FICHEIRO PASSA A RECUSAR (MEDIDO no log do dono)

`H:/sotto/_main/webview-run.log` 10:56:04 -> 10:57:16, 61 linhas seguidas:

    YOUTUBE_TICK_MS avg=0 max=0 n=20 src='?' vid='MOZIBMBHK-8'
      cdp_age_ms=2413609 rows=0 why='cdp-fresh-skip'

com o Chrome aberto num video do YouTube. `src='?'` = nenhum ramo do laco
escreveu o diagnostico; `cdp_age_ms=2413609` = a idade foi congelada no instante
em que o ultimo ramo escreveu (40 minutos antes); `rows=0` = nada pintado. A
legenda no ecra era o ASR do audio do video, nao a faixa do player.

E o pedido de attach morava no primeiro tick do laco, que so' existe depois de
metade do arranque: `CAPTION_PIPELINE_START reason=pre-webview` as 10:06:36.483 e
`YOUTUBE_CDP_SOURCE state=attached` as 10:06:40.798.

AS ARMS (todas EXECUTAM as funcoes reais; nenhuma procura texto)

  A1 arranque-sem-painel -- `SottoShell.start_caption_pipeline('pre-webview')`
      REAL, sobre um objeto sem painel nenhum: a chamada tem de pedir o attach
      (`youtube_cdp_source.boot_attach` -> uma linha `YOUTUBE_CDP_BOOT_ATTACH
      ok=true`) e deixar na shell a fonte CDP viva. CONTROLE: `SOTTO_YT_CDP=0`
      -> nenhuma fonte criada, `skipped reason=SOTTO_YT_CDP=0`.
  A2 retry-limitado  -- `boot_attach` contra uma porta FECHADA: devolve
      `(False,'port-closed')`, escreve UMA linha por tentativa (3) e cada uma
      diz o motivo. CONTROLE: o mesmo `boot_attach` contra um `/json/list` de
      fotografia -> `(True,'only-tab')`, uma linha `ok=true`.
  A3 aba-navegou    -- o laco REAL (`CdpCaptionSource._run`) com um WebSocket de
      fotografia. A ADOCAO TEM DUAS REGRAS (2026-11-07) e um mundo so' as
      cobria uma a' outra; por isso a arm tem dois bracos, cada um a isolar a
      regra que decide: `aba-que-navegou` (o declarado ja' nao esta' em aba
      nenhuma -- exercita a QUEDA do id no `_choose`) e
      `aba-que-navegou/depois` (a aba a que nos ligamos NAVEGOU -> so'
      `adopt_decision(declared_closed)` decide, `sel=OLD`; e, com o declarado
      AINDA aberto e a janela em primeiro plano na aba nova, so' o desvio
      `attached-tab` decide, `sel=NEW`). CONTROLE: `OLD` ainda aberto e ligados
      a ele -> NAO adota, `_video_id` fica `OLD`, estado `wrong-video (NEW)`. O
      controle tem mutacao PROPRIA no `--neg-arm` (a adocao que ignora o
      declarado aberto tem de o derrubar): um controle que passa sob TODAS as
      mutacoes nunca esteve ancorado.
  A4 diagnostico     -- `ExternalCaptionWatcher._yt_diag_now()` (a funcao que a
      linha `YOUTUBE_TICK_MS` usa): com o dicionario de diagnostico VAZIO ou com
      `src='?'`, os cinco campos saem completos (`unattached`/`none`), e a IDADE
      e' lida AGORA da fonte, nao do valor congelado no dicionario. CONTROLE: uma
      fonte com foto de 1,5 s -> `cdp_age_ms=1500` (prova que a idade e' viva).
  A5 linha-completa  -- a linha do log usada pela shell tem `rows=%d` e nenhum
      `.get('src', '?')`/`.get('age', '?')`: o `?` deixou de ser um valor.

`--neg-arm` muta COPAS (seis mutacoes, cada uma no sitio que a sua arm julga,
incluindo a queda do id declarado e o `refuse` do controle) e
exige que AQUELE braco caia; rc=1 quando apanha todos -- e' a convencao
`red-as-expected` da bateria.

Sem Chrome, sem janela, sem audio: o transporte (HTTP `/json/list`, WebSocket) e'
uma fotografia local. O Chrome do dono nunca e' tocado por este oraculo.
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
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.abspath(os.path.join(HERE, "..", "app", "webview"))
MODULE = os.path.join(APP, "youtube_cdp_source.py")
SHELL = os.path.join(APP, "sotto_webview.py")

# A SHELL importa os irmaos por nome (`hot_reload`, `external_subs`): sem esta
# entrada, carregar uma COPIA dele noutra pasta morria em `ModuleNotFoundError`
# e nao havia controle possivel.
if APP not in sys.path:
    sys.path.insert(0, APP)

TAB_NEW = {"type": "page", "title": "Video novo",
           "url": "https://www.youtube.com/watch?v=NEWNEWNEWNE",
           "webSocketDebuggerUrl": "ws://127.0.0.1:1/devtools/page/NEW"}
TAB_OLD = {"type": "page", "title": "Video velho",
           "url": "https://www.youtube.com/watch?v=OLDOLDOLDOL",
           "webSocketDebuggerUrl": "ws://127.0.0.1:1/devtools/page/OLD"}
#: A MESMA PAGINA DE `TAB_OLD`, JA' NAVEGADA. Um alvo de DevTools nao muda de
#: `webSocketDebuggerUrl` quando o SPA navega; o URL e' que passa a dizer NEW.
#: E' o mundo `navigated` de `_adopt_world`: ligados ao OLD, a foto ja' e' NEW e
#: o `/json/list` ja' nao tem o OLD em sitio nenhum.
TAB_NAV = {"type": "page", "title": "Video novo",
           "url": "https://www.youtube.com/watch?v=NEWNEWNEWNE",
           "webSocketDebuggerUrl": "ws://127.0.0.1:1/devtools/page/OLD"}


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read(path):
    return io.open(path, encoding="utf-8", errors="replace").read()


class StubCdp:
    """Um `/json/list` de FOTOGRAFIA: uma lista de abas, zero Chrome.

    E' o unico pedaco falso de cada arm; o transporte e' o de verdade (HTTP
    local) e quem decide e' sempre a funcao de producao.
    """

    def __init__(self, tabs):
        outer = self
        self.tabs = list(tabs)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):                 # noqa: N802 (API do http.server)
                if not self.path.startswith("/json/list"):
                    self.send_error(404)
                    return
                body = json.dumps(outer.tabs).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_args):    # sem ruido no stdout do portao
                return

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = int(self.httpd.server_address[1])
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       name="stub-cdp", daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3.0)
        return False


def _closed_port():
    """Uma porta que ninguem esta' a ouvir -- sem abrir nada na tela."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


# -- A1: o arranque pede o attach sem painel nenhum -------------------------

def _no_panel_shell(shell_mod):
    """A shell do arranque, SEM painel: subclasse da REAL, `__init__` nao corre.

    Subclasse e nao um dicionario de atributos: assim `start_caption_pipeline`
    e' o metodo de producao, ligado ao objeto, e nao uma chamada solta. Nao ha'
    `show_panel`, nao ha' WebView2, nao ha' argumentos -- se o pedido de attach
    dependesse de um evento de painel, nao teria como acontecer aqui.
    """

    class _NoPanelShell(shell_mod.SottoShell):
        def __init__(self):
            self._caption_pipeline_started = False
            self._yt_cdp_source = None
            self.args = None
            self.calls = []

        def _worker_autostart_reason(self, _args=None):
            return "declined"

        def start_external_caption_watcher(self):
            self.calls.append("watcher")
            return True

        def start_worker(self, reason):
            self.calls.append("worker:%s" % reason)
            return False

    return _NoPanelShell()


def _arm_boot(shell_mod, mod, port):
    """(ok, nota). Executa `start_caption_pipeline` REAL, sem painel."""
    old_port = os.environ.get("SOTTO_YT_CDP_PORT")
    os.environ["SOTTO_YT_CDP_PORT"] = str(port)
    lines = []
    old_log = shell_mod.log
    shell_mod.log = lines.append
    sh = _no_panel_shell(shell_mod)
    source = None
    try:
        shell_mod.SottoShell.start_caption_pipeline(sh, "pre-webview")
        source = getattr(sh, "_yt_cdp_source", None)
        asked = [ln for ln in lines
                 if "YOUTUBE_CDP_BOOT_ATTACH" in ln and "ok=true" in ln]
        alive = bool(source is not None and source is not False
                     and getattr(source, "_thread", None) is not None
                     and source._thread.is_alive())
        ok = (bool(asked) and alive and sh.calls == ["watcher", "worker:declined"]
              and all("panel" not in c for c in sh.calls))
        note = ("asked=%d alive=%s calls=%s %s"
                % (len(asked), alive, sh.calls, (asked or ["-"])[0][:96]))
        return ok, note
    finally:
        if source is not None and source is not False:
            try:
                source.stop()
                if getattr(source, "_thread", None) is not None:
                    source._thread.join(timeout=3.0)
            except Exception:                 # noqa: BLE001
                pass
        shell_mod.log = old_log
        if old_port is None:
            os.environ.pop("SOTTO_YT_CDP_PORT", None)
        else:
            os.environ["SOTTO_YT_CDP_PORT"] = old_port


def _control_boot_off(shell_mod, port):
    """CONTROLE de A1: a porta desligada por ambiente -> nada e' pedido."""
    old = os.environ.get("SOTTO_YT_CDP")
    os.environ["SOTTO_YT_CDP"] = "0"
    old_port = os.environ.get("SOTTO_YT_CDP_PORT")
    os.environ["SOTTO_YT_CDP_PORT"] = str(port)
    lines = []
    old_log = shell_mod.log
    shell_mod.log = lines.append
    sh = _no_panel_shell(shell_mod)
    try:
        shell_mod.SottoShell.start_caption_pipeline(sh, "pre-webview")
        created = getattr(sh, "_yt_cdp_source", None)
        skipped = [ln for ln in lines if "skipped reason=SOTTO_YT_CDP=0" in ln]
        # O controle PEDE o contrario da arm: sem fonte e UMA linha que diz
        # porque. Se mesmo desligada a shell criasse a fonte, a arm passaria por
        # outro motivo e nao estaria a medir o pedido do arranque.
        return (created is None and len(skipped) == 1), \
            "created=%r skipped=%d %r" % (created, len(skipped),
                                          (skipped or ["-"])[0][:80])
    finally:
        shell_mod.log = old_log
        if old is None:
            os.environ.pop("SOTTO_YT_CDP", None)
        else:
            os.environ["SOTTO_YT_CDP"] = old
        if old_port is None:
            os.environ.pop("SOTTO_YT_CDP_PORT", None)
        else:
            os.environ["SOTTO_YT_CDP_PORT"] = old_port


# -- A2: retry limitado, um motivo por tentativa ----------------------------

def _dial_verdict(port):
    """O QUE ESTE SISTEMA FAZ com um porto onde ninguem ouve -- medido, nao suposto.

    A arm julgava `why == "port-closed"` como literal, e esse motivo era
    INALCANCAVEL nesta maquina: medido 2026-11-05 com um instrumento independente
    (um `socket.create_connection` cru ao mesmo porto), SEIS de seis portos
    devolvem `TimeoutError` a 400 ms -- nem `bind+close` nem um listener que
    FECHOU produzem RST aqui (tres de tres cada). O Windows desta caixa NAO
    responde a um SYN de loopback sem listener, logo o motivo honesto que o
    modulo pode publicar e' `probe-timeout`, e a arm reprovava um oraculo por uma
    propriedade do hospedeiro. Agora a arm pergunta ao hospedeiro qual dos dois
    mundos e' o dele e exige do modulo EXACTAMENTE aquele motivo: continua a
    apanhar um mutante que colapse os dois nomes, e deixa de inventar um.
    """
    try:
        c = socket.create_connection(("127.0.0.1", int(port)), timeout=0.4)
        c.close()
        return "accepted", "a porta ACEITA ligacao"
    except ConnectionRefusedError:
        return "refused", "port-closed"
    except (TimeoutError, socket.timeout):
        return "dropped", "probe-timeout"
    except OSError as exc:
        return "dropped", "probe-timeout"


def _arm_retry(mod):
    port = _closed_port()
    verdict, expected = _dial_verdict(port)
    lines = []
    t0 = time.monotonic()
    ok, why = mod.boot_attach(port=port, attempts=3, delay=0,
                              log=lines.append, sleep=lambda _s: None)
    took_ms = (time.monotonic() - t0) * 1000.0
    fails = [ln for ln in lines if "ok=false" in ln]
    good = (ok is False and why == expected
            and verdict != "accepted"
            and len(lines) == 3 and len(fails) == 3
            and all(("reason=%s" % expected) in ln for ln in fails)
            and "attempt=3/3" in fails[-1]
            # LIMITADO: tres tentativas de um porto que ninguem ouve nao podem
            # custar o arranque. O tecto e' generoso (3 s) porque o prazo do
            # dial nesta caixa e' 400 ms por tentativa.
            and took_ms < 3000.0)
    return good, "host=%s ok=%r why=%s lines=%d took_ms=%.0f last=%r" % (
        verdict, ok, why, len(lines), took_ms, (lines or ["-"])[-1][:80])


def _control_retry_attached(mod):
    """CONTROLE de A2: o MESMO `boot_attach` com uma aba a' vista -> ok=true."""
    with StubCdp([TAB_OLD]) as stub:
        lines = []
        ok, why = mod.boot_attach(port=stub.port, attempts=3, delay=0,
                                  log=lines.append, sleep=lambda _s: None)
        good = (ok is True and why in ("only-tab", "named", "window-title")
                and len(lines) == 1 and "ok=true" in lines[0])
        return good, "ok=%r why=%s lines=%d" % (ok, why, len(lines))


# -- A3: a aba que navegou e' adotada --------------------------------------

PAYLOAD_NEW = json.dumps({
    "videoId": "NEWNEWNEWNE", "title": "Video novo", "why": "painted",
    "rows": [{"text": "ola mundo", "items": [
        {"text": "ola", "left": 1, "top": 1, "right": 9, "bottom": 9},
        {"text": "mundo", "left": 12, "top": 1, "right": 30, "bottom": 9}]}]})


class _FakeConn:
    """Um WebSocket CDP de FOTOGRAFIA: responde sempre com a mesma pagina."""

    def __init__(self, payload):
        self.payload = payload
        self.sent = 0
        self.last_id = 1

    def send(self, data):
        # O ID E' ECOADO (medido 2026-11-05). A sonda de "quem esta' a tocar"
        # passou a pedir `Runtime.evaluate` com IDs proprios, e este fake respondia
        # sempre `id=1`: o laco `while True` do `_ws_eval` esperava um id que nunca
        # chegava e GIRAVA PARA SEMPRE -- o passo nao escrevia linha nenhuma, dava
        # FAIL e a bateria o cortava no prazo (240 s). Um fake que responde a uma
        # pergunta que ninguem fez e' a forma mais barata de testar nada.
        self.sent += 1
        try:
            self.last_id = json.loads(data).get("id", self.last_id)
        except (TypeError, ValueError):
            pass

    def recv(self):
        return json.dumps({"id": self.last_id,
                           "result": {"result": {"value": self.payload}}})

    def settimeout(self, _t):
        return

    def close(self):
        return


class _FakeWebsocket:
    def __init__(self, payload):
        self.conn = _FakeConn(payload)

    def create_connection(self, _url, timeout=None):
        return self.conn


def _adopt_world(mod, kind):
    """UM mundo de adopcao. (ok, nota): o laco REAL, com UMA regra no comando.

    PORQUE TRES MUNDOS (MEDIDO 2026-11-07). A arm tinha UM mundo -- o declarado
    OLD fora da lista e so' a aba NEW a' vista --, e nesse mundo DUAS regras de
    producao adoptam a mesma foto:

      * `adopt_decision(..., declared_open=False)` -> `declared-closed`
        (`youtube_cdp_source.py:920`);
      * o desvio `attached-tab` do `_run`, que aceita a foto quando ela vem da
        aba que a SONDA escolheu (`_selected_video_id == snap.videoId`).

    Ligados a' unica aba NEW, `_selected_video_id` ja' e' NEW, logo o desvio
    adoptava por cima. A mutacao que apaga `declared-closed` ficava VERDE -- o
    `--neg-arm` media a regra errada. Cada mundo abaixo elimina uma das duas:

      `stale-list`   -- so' a aba NEW em `/json/list` (o declarado nao esta' em
                        aba nenhuma). Exercita a QUEDA do id declarado no
                        `_choose` (`stale-declared:`), sem a qual o laco nao
                        chega a ligar-se a nada e nao ha' foto nenhuma.
      `navigated`    -- a aba a que NOS LIGAMOS navegou: o `/json/list` passa a
                        dizer NEW (mesmo alvo/ws do OLD) e a foto ja' e' NEW,
                        mas `_selected_video_id` FICA `OLD` (foi escolhido no
                        attach). O desvio `attached-tab` exige
                        `_selected_video_id == foto` e por isso esta' FORA:
                        so' `adopt_decision(..., declared_closed=...)` adopta.
      `attached-tab` -- o declarado OLD AINDA esta' aberto (logo
                        `declared-closed` esta' FORA) e a janela em primeiro
                        plano resolve a aba NEW, a que estamos ligados: so' o
                        desvio `attached-tab` adopta.
      `control`      -- declarado AINDA aberto e ligados a ele: a foto NEW tem
                        de ser RECUSADA (`wrong-video (NEW)`).
    """
    old_tabs = mod.list_targets
    state = {"n": 0}
    if kind == "stale-list":
        # A LISTA E' FOTOGRAFIA (transporte); a decisao e' do produto. O video
        # declarado ja' nao esta' em sitio nenhum: so' a aba NEW.
        def tabs_now(port=None, timeout=3.0):
            return ([TAB_NEW], 0)
    elif kind == "navigated":
        # A PRIMEIRA leitura e' o attach (ainda OLD); a partir da segunda --
        # `_declared_closed` -- a mesma pagina ja' diz NEW.
        def tabs_now(port=None, timeout=3.0):
            state["n"] += 1
            return ([TAB_OLD] if state["n"] == 1 else [TAB_NAV]), 0
    else:                                     # `attached-tab` e `control`
        def tabs_now(port=None, timeout=3.0):
            return ([TAB_OLD, TAB_NEW], 0)
    mod.list_targets = tabs_now
    fake = _FakeWebsocket(PAYLOAD_NEW)
    old_ws = sys.modules.get("websocket")
    sys.modules["websocket"] = fake
    lines = []
    source = mod.CdpCaptionSource(port=_closed_port(), log=lines.append)
    source.set_video_id("OLDOLDOLDOL")
    if kind == "attached-tab":
        # O TITULO DA JANELA EM PRIMEIRO PLANO e' o que resolve a aba NEW com o
        # OLD ainda aberto (a ordem do `pick_target`, `window-title`).
        source.set_window_title("Video novo")
    source._last_use = time.monotonic()
    source.start()
    try:
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            source.snapshot()                 # o pedido que a mantem viva
            if source._video_id != "OLDOLDOLDOL":
                break
            if any("wrong-video" in ln for ln in lines):
                break
            time.sleep(0.02)
        adopted = [ln for ln in lines if "adopted:" in ln]
        selected = source.selected_video_id()
        if kind == "control":
            good = (source._video_id == "OLDOLDOLDOL" and not adopted
                    and any("wrong-video (NEWNEWNEWNE)" in ln for ln in lines))
        elif kind == "navigated":
            # `selected == OLD` EXCLUI o desvio `attached-tab` (que exige
            # `selected == foto`): se a arm fica verde, foi o `declared-closed`.
            good = (source._video_id == "NEWNEWNEWNE"
                    and any("adopted:OLDOLDOLDOL->NEWNEWNEWNE" in ln
                            for ln in lines)
                    and selected == "OLDOLDOLDOL")
        elif kind == "attached-tab":
            # `declared-closed` NAO pode ter decidido: o OLD esta' na lista, o
            # predicado da producao diz "aberto". `selected == foto` e' o que o
            # desvio exige.
            good = (source._video_id == "NEWNEWNEWNE"
                    and any("adopted:OLDOLDOLDOL->NEWNEWNEWNE" in ln
                            for ln in lines)
                    and selected == "NEWNEWNEWNE"
                    and any("OLDOLDOLDOL" in str(t.get("url") or "")
                            for t in tabs_now()[0]))
        else:                                 # `stale-list`
            good = (source._video_id == "NEWNEWNEWNE"
                    and any("adopted:OLDOLDOLDOL->NEWNEWNEWNE" in ln
                            for ln in lines))
        return good, "vid=%s sel=%s adopted=%d %r" % (
            source._video_id, selected, len(adopted),
            (lines or ["-"])[-1][:96])
    finally:
        source.stop()
        if source._thread is not None:
            source._thread.join(timeout=3.0)
        mod.list_targets = old_tabs
        if old_ws is None:
            sys.modules.pop("websocket", None)
        else:
            sys.modules["websocket"] = old_ws


# -- A4: o diagnostico nunca sai `?` ---------------------------------------

class _AgeSource:
    def __init__(self, age, rows=None):
        self.age = age
        self.rows = rows

    def snapshot_age(self):
        return self.age

    def snapshot(self, max_age=0.6):
        if self.rows is None:
            return None
        return {"rows": list(self.rows)}


def _arm_diag(shell_mod):
    watcher = shell_mod.ExternalCaptionWatcher(None)
    watcher._yt_diag = {}
    watcher.yt_video_id = ""
    watcher._yt_cdp_source = None
    empty = watcher._yt_diag_now()
    watcher._yt_diag = {"src": "?", "vid": "VID12345678", "age": "?",
                        "rows": 99, "why": ""}
    watcher._yt_cdp_source = _AgeSource(1.5)
    watcher.yt_cdp_rows = ["a", "b"]
    qmark = watcher._yt_diag_now()
    watcher._yt_cdp_source = _AgeSource(None)
    watcher.yt_video_id = "VID12345678"
    none_age = watcher._yt_diag_now()
    # A SEXTA ARM (2026-11-05): o numero de linhas vem da FOTO, nao do campo de
    # passagem. MEDIDO no log da instancia viva: 331 ticks seguidos com
    # `rows=0 why='painted'` enquanto o player pintava `>> wait`, porque
    # `yt_cdp_rows` e' consumido no proprio tick (`_yt_rows_impl` -> None). As
    # duas armas abaixo exigem o CONTRARIO uma da outra, de proposito: com foto
    # manda a foto (3), sem foto manda o campo (2).
    watcher._yt_cdp_source = _AgeSource(0.1, rows=["x", "y", "z"])
    watcher.yt_cdp_rows = None
    with_snap = watcher._yt_diag_now()
    watcher._yt_cdp_source = _AgeSource(0.1)
    watcher.yt_cdp_rows = ["a", "b"]
    no_snap = watcher._yt_diag_now()
    good = (empty == ("unattached", "", "none", 0, "no-frame")
            and qmark[0] == "external:youtube" and qmark[1] == "VID12345678"
            and qmark[2] == "1500" and qmark[3] == 2
            and none_age[2] == "none"
            and with_snap[3] == 3 and no_snap[3] == 2
            and "?" not in (empty + qmark + none_age + with_snap + no_snap))
    return good, ("empty=%r qmark=%r none_age=%r with_snap=%r no_snap=%r"
                  % (empty, qmark, none_age, with_snap, no_snap))


def _arm_line(shell_text):
    ok = ("src=%r vid=%r cdp_age_ms=%s rows=%d why=%r" in shell_text
          and "_dgs.get('src', '?')" not in shell_text
          and "_dgs.get('age', '?')" not in shell_text)
    return ok, "format=%s qmark_defaults=%s" % (
        "src=%r vid=%r cdp_age_ms=%s rows=%d why=%r" in shell_text,
        "_dgs.get('src', '?')" in shell_text)


# -- as arms ---------------------------------------------------------------

def arms(shell_path=SHELL, module_path=MODULE):
    mod = _load(module_path, "yt_cdp_boot_under_test")
    shell_mod = _load(shell_path,
                      "sotto_shell_under_test_%d"
                      % (int(time.monotonic() * 1000) % 100000))
    out = []
    with StubCdp([TAB_OLD]) as stub:
        ok, note = _arm_boot(shell_mod, mod, stub.port)
        out.append(("arranque-sem-painel", ok, note))
        ok, note = _control_boot_off(shell_mod, stub.port)
        out.append(("controle-porta-desligada", ok, note))
    ok, note = _arm_retry(mod)
    out.append(("retry-limitado", ok, note))
    ok, note = _control_retry_attached(mod)
    out.append(("controle-retry-ligado", ok, note))
    ok, note = _adopt_world(mod, "stale-list")
    out.append(("aba-que-navegou", ok, note))
    # A ADOCAO TEM DUAS REGRAS (2026-11-07). Num mundo so' elas cobriam-se uma
    # a' outra e a mutacao de `declared-closed` ficava verde; aqui cada metade
    # diz qual decidiu (`sel=`), e a arm so' passa se AS DUAS decidirem:
    # `navigated` (so' a regra mutada pode) e `attached-tab` (so' o desvio
    # pode). Uma remocao de qualquer das duas poem esta arm vermelha.
    ok_nav, note_nav = _adopt_world(mod, "navigated")
    ok_att, note_att = _adopt_world(mod, "attached-tab")
    out.append(("aba-que-navegou/depois", ok_nav and ok_att,
                "navigated[%s] attached[%s]" % (note_nav, note_att)))
    ok, note = _adopt_world(mod, "control")
    out.append(("controle-aba-ainda-aberta", ok, note))
    ok, note = _arm_diag(shell_mod)
    out.append(("diagnostico-sem-interrogacao", ok, note))
    ok, note = _arm_line(_read(shell_path))
    out.append(("linha-do-log-completa", ok, note))
    return out


def _mutate(src, old, new):
    """O texto com UMA substituicao -- e' ERRO se a ancora nao existir.

    `str.replace` de um texto ausente e' um no-op silencioso: a "mutacao" seria
    o codigo ORIGINAL, e o braco cairia (ou nao) por outro motivo sem que o
    `CAUGHT` deixasse de se imprimir. Cada mutacao seguinte diz o que julga;
    esta funcao garante que o que ela julga ainda esta' la' para ser mutado.
    """
    if src.count(old) != 1:
        raise AssertionError("mutacao sem ancora unica (%d ocorrencias): %r"
                             % (src.count(old), old[:60]))
    return src.replace(old, new, 1)


def neg_arm():
    """Seis mutacoes, cada uma no sitio que a SUA arm julga.

    As duas ultimas ancoram as regras que o incidente do `vid=OLDOLDOLDOL`
    exercita: (5) a QUEDA do id declarado quando ele ja' nao esta' aberto -- a
    linha cuja perda em `888a3ae` fez o laco fechar-se em si mesmo --, e (6) o
    `refuse` do CONTROLE, que sem mutacao propria ficava verde por construcao
    (passava mesmo com a adocao mutada em 3).
    """
    tmp = tempfile.mkdtemp(prefix="yt-cdp-boot-neg-")
    try:
        # O IRMAO VEM JUNTO (medido 2026-11-08): `youtube_cdp_source` carrega
        # `youtube_window` PELO CAMINHO do proprio ficheiro (`_load_sibling`,
        # :50); os mutantes 2 e 3 sao copias DESTE modulo num diretorio
        # temporario e sem o irmao ao lado o carregamento morria em
        # `FileNotFoundError` -- `--neg-arm` sem medicao e sem a frase
        # `NEG-ARM`, que e' exactamente o que a corrida de 05:0x mostrou.
        shutil.copyfile(os.path.join(APP or os.path.dirname(MODULE), "youtube_window.py"),
                        os.path.join(tmp, "youtube_window.py"))
        results = []
        mod_src = _read(MODULE)
        shell_src = _read(SHELL)

        # 1) O ARRANQUE DEIXA DE PEDIR O ATTACH (o codigo de antes de hoje).
        shell_mut = os.path.join(tmp, "shell_sem_arranque.py")
        io.open(shell_mut, "w", encoding="utf-8", newline="").write(
            _mutate(shell_src, "            self._yt_cdp_boot_attach()\n",
                    "            pass\n"))
        got = dict((n, ok) for n, ok, _ in arms(shell_path=shell_mut))
        results.append(("arranque-sem-painel", not got.get("arranque-sem-painel", True)))

        # 2) O RETRY DEIXA DE SER LIMITADO (uma tentativa so').
        mod1 = os.path.join(tmp, "retry_unico.py")
        io.open(mod1, "w", encoding="utf-8", newline="").write(
            _mutate(mod_src,
                    "    for attempt in range(1, max(1, int(attempts)) + 1):",
                    "    for attempt in range(1, 2):"))
        got = dict((n, ok) for n, ok, _ in arms(module_path=mod1))
        results.append(("retry-limitado", not got.get("retry-limitado", True)))

        # 3) A ABA QUE NAVEGOU DEIXA DE SER ADOTADA (o laco preso por 13 min).
        #    MUTADO 2026-11-07: esta mutacao apaga `declared-closed` e a ANTIGA
        #    arm ficava verde, porque o desvio `attached-tab` do `_run` aceitava
        #    a mesma foto (`sel=NEWNEWNEWNE`). O mundo `navigated` escolhe a aba
        #    no attach (`sel=OLD`) e a mesma pagina passa a dizer NEW: o desvio
        #    esta' fora e so' a regra mutada pode adoptar.
        mod2 = os.path.join(tmp, "sem_adocao.py")
        io.open(mod2, "w", encoding="utf-8", newline="").write(
            _mutate(mod_src, "    if not declared_open:\n"
                             "        return 'adopt', 'declared-closed'",
                    "    if False:\n"
                    "        return 'adopt', 'declared-closed'"))
        got = dict((n, ok) for n, ok, _ in arms(module_path=mod2))
        results.append(("aba-que-navegou/depois",
                        not got.get("aba-que-navegou/depois", True)))

        # 4) O DIAGNOSTICO VOLTA A PODER SAIR `?` (o `src='?'` medido).
        shell_mut2 = os.path.join(tmp, "shell_diag_interrogacao.py")
        io.open(shell_mut2, "w", encoding="utf-8", newline="").write(
            _mutate(shell_src, "        if not src or src == '?':\n",
                    "        if False:\n"))
        got = dict((n, ok) for n, ok, _ in arms(shell_path=shell_mut2))
        results.append(("diagnostico-sem-interrogacao",
                        not got.get("diagnostico-sem-interrogacao", True)))

        # 5) O ID DECLARADO QUE JA' NAO ESTA' ABERTO DEIXA DE SER ULTRAPASSADO.
        #    E' a linha do `_choose` cuja ausencia em `888a3ae` produziu o
        #    sintoma medido (`aba-que-navegou -- vid=OLDOLDOLDOL`, zero linhas):
        #    sem a queda, o id filtra a escolha, sem escolha nao ha' foto, e sem
        #    foto o id nunca se cura.
        mod3 = os.path.join(tmp, "sem_queda_declarado.py")
        io.open(mod3, "w", encoding="utf-8", newline="").write(
            _mutate(mod_src,
                    "        if target is None and self._video_id:\n"
                    "            target, why = pick_target(tabs, '', self._window_title)",
                    "        if False:\n"
                    "            target, why = pick_target(tabs, '', self._window_title)"))
        got = dict((n, ok) for n, ok, _ in arms(module_path=mod3))
        results.append(("aba-que-navegou/queda",
                        not got.get("aba-que-navegou", True)))

        # 6) O CONTROLE: a adocao deixa de olhar para o declarado aberto, e a
        #    aba que o dono apontou seria trocada pelo video da foto. O braco
        #    TEM de cair -- e' o unico sitio que diz que "ainda aberto" pesa.
        mod4 = os.path.join(tmp, "adota_sempre.py")
        io.open(mod4, "w", encoding="utf-8", newline="").write(
            _mutate(mod_src, "    if not declared_open:\n"
                             "        return 'adopt', 'declared-closed'",
                    "    if True:\n"
                    "        return 'adopt', 'declared-closed'"))
        got = dict((n, ok) for n, ok, _ in arms(module_path=mod4))
        results.append(("controle-aba-ainda-aberta",
                        not got.get("controle-aba-ainda-aberta", True)))
        return results
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    args = parser.parse_args(argv)
    if args.neg_arm:
        results = neg_arm()
        bad = 0
        for name, caught in results:
            print("NEG-ARM %-30s %s" % (name, "CAUGHT" if caught else "NOT-CAUGHT"))
            bad += 0 if caught else 1
        print("NEG-ARM VERDICT: %s (%d/%d)"
              % ("PASS" if not bad else "FAIL", len(results) - bad, len(results)))
        # CONVENCAO DA BATERIA: um `red-as-expected` declara rc=1.
        return 1 if not bad else 0
    bad = 0
    rows = arms()
    for name, ok, note in rows:
        print("%-32s %s  %s" % (name, "PASS" if ok else "FAIL", note))
        bad += 0 if ok else 1
    print("VERDICT: %s (%d/%d)"
          % ("PASS" if not bad else "FAIL", len(rows) - bad, len(rows)))
    # A SONDA SAI A FORCA DEPOIS DO VEREDICTO (medido 2026-11-05). O veredicto era
    # impresso e o processo ficava preso num fio do modulo que ela exercita: o passo
    # gastou 21,6 min uma vez e 240 s (o prazo da bateria) na corrida de hoje, sempre
    # DEPOIS de ja' ter dito o resultado. Um instrumento que nao sai nao entrega
    # veredicto nenhum -- a linha acima e' a evidencia, e o teclado do processo morto
    # nao muda a resposta.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0 if not bad else 1)


if __name__ == "__main__":
    raise SystemExit(main())
