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
      fotografia: o video declarado (`OLD`) desapareceu da lista de abas e a foto
      traz `NEW` -> `_video_id` passa a `NEW` e o estado diz
      `adopted:OLD->NEW`. CONTROLE: `OLD` ainda aberto -> NAO adota, `_video_id`
      fica `OLD`, estado `wrong-video (NEW)`. O controle tem mutacao PROPRIA no
      `--neg-arm` (a adocao que ignora o declarado aberto tem de o derrubar):
      um controle que passa sob TODAS as mutacoes nunca esteve ancorado.
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

def _arm_retry(mod):
    port = _closed_port()
    lines = []
    ok, why = mod.boot_attach(port=port, attempts=3, delay=0,
                              log=lines.append, sleep=lambda _s: None)
    fails = [ln for ln in lines if "ok=false" in ln]
    good = (ok is False and why == "port-closed" and len(lines) == 3
            and len(fails) == 3
            and all("reason=port-closed" in ln for ln in fails)
            and "attempt=3/3" in fails[-1])
    return good, "ok=%r why=%s lines=%d last=%r" % (
        ok, why, len(lines), (lines or ["-"])[-1][:96])


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


def _arm_adopt(mod, declared_open):
    """(ok, nota): o laco REAL, com o id declarado aberto ou ja' fechado."""
    old_tabs = mod.list_targets
    # A LISTA DE ABAS E' FOTOGRAFIA (o transporte), a decisao e' do produto: no
    # caso da adocao a aba que navegou e' a UNICA aberta (o video declarado ja'
    # nao esta' em sitio nenhum); no controle as duas estao abertas e o dono
    # apontou para a declarada.
    tabs = [TAB_OLD, TAB_NEW] if declared_open else [TAB_NEW]
    mod.list_targets = lambda port=None, timeout=3.0: (list(tabs), 0)
    fake = _FakeWebsocket(PAYLOAD_NEW)
    old_ws = sys.modules.get("websocket")
    sys.modules["websocket"] = fake
    lines = []
    source = mod.CdpCaptionSource(port=_closed_port(), log=lines.append)
    source.set_video_id("OLDOLDOLDOL")
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
        if declared_open:
            adopted = [ln for ln in lines if "adopted:" in ln]
            good = (source._video_id == "OLDOLDOLDOL" and not adopted
                    and any("wrong-video (NEWNEWNEWNE)" in ln for ln in lines))
            note = "vid=%s adopted=%d %r" % (source._video_id, len(adopted),
                                             (lines or ["-"])[-1][:80])
            return good, note
        good = (source._video_id == "NEWNEWNEWNE"
                and any("adopted:OLDOLDOLDOL->NEWNEWNEWNE" in ln
                        for ln in lines))
        return good, "vid=%s %r" % (source._video_id, (lines or ["-"])[-1][:96])
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
    def __init__(self, age):
        self.age = age

    def snapshot_age(self):
        return self.age


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
    good = (empty == ("unattached", "", "none", 0, "no-frame")
            and qmark[0] == "external:youtube" and qmark[1] == "VID12345678"
            and qmark[2] == "1500" and qmark[3] == 2
            and none_age[2] == "none"
            and "?" not in (empty + qmark + none_age))
    return good, "empty=%r qmark=%r none_age=%r" % (empty, qmark, none_age)


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
    ok, note = _arm_adopt(mod, declared_open=False)
    out.append(("aba-que-navegou", ok, note))
    ok, note = _arm_adopt(mod, declared_open=True)
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
        mod2 = os.path.join(tmp, "sem_adocao.py")
        io.open(mod2, "w", encoding="utf-8", newline="").write(
            _mutate(mod_src, "    if not declared_open:\n"
                             "        return 'adopt', 'declared-closed'",
                    "    if False:\n"
                    "        return 'adopt', 'declared-closed'"))
        got = dict((n, ok) for n, ok, _ in arms(module_path=mod2))
        results.append(("aba-que-navegou", not got.get("aba-que-navegou", True)))

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
