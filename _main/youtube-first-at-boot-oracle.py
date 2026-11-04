"""Portao da PRIMEIRA LEGENDA DO YOUTUBE NO ARRANQUE.

    `_main/youtube-first-at-boot-oracle.py`

O DONO, 2026-11-04, verbatim (terceira vez no mesmo dia):

    *"é estupido 'carregando o modelo' e nao mostrar instantaneamente as
    legendas do youtube, assim que eu abro o app."*

O QUE ESTA' MEDIDO NO ARRANQUE DELE (pid 56116, `_main/webview-run.log`):

    12:15:15.349  CAPTION_OVERLAY_MODE native=true hwnd=379855006      <- a superficie esta' de pe'
    12:15:15.349  CAPTION_WINDOW_DEFERRED_APPLIED on=true
    12:15:15.352  CAPTION_PIPELINE_START reason=pre-webview
    12:15:15.363  YOUTUBE_CDP_BOOT_ATTACH attempt=1/3 ok=false reason=ambiguous port=9222 tabs=5
    12:15:15.887  BRIDGE_SPAWNED pid=13904                             <- o modelo comeca
    12:15:16.001  EXTERNAL_CAPTIONS_WATCH started=true
    12:15:16.816  CAPTION_PAINT instant=false text="carregando modelo…"  <- O QUE ELE VIU
    12:16:27.795  CAPTION_OVERLAY_PUSH count=50 text="macro and the thing is"

A superficie existia 1,5 s antes de qualquer linha, o Chrome tinha 5 abas e um
video a tocar, e a primeira coisa pintada foi o texto de estado do MODELO. O
defeito tem duas metades e o oraculo julga as duas:

  1. O TEXTO DE ESTADO NAO ENTRA POR CIMA DO PLAYER. Se uma faixa do player e'
     alcancavel (linhas no DOM, ou ja' pintada), `carregando modelo…` nao pinta;
  2. A ORDEM DO ARRANQUE. `cdp` -> `watcher` -> `worker`, e o worker NAO e'
     pre-condicao de nada que pinte.

AS ARMS (todas executam as FUNCOES REAIS; nenhuma reimplementa a regra)

  A1  sem-faixa-o-estado-e-honesto
      sem player nenhum, `SottoShell.on_worker_loading_text('carregando modelo…')`
      chega a' superficie. E' o caso (c) do ticket: a cura nao pode CALAR o
      estado honesto;
  A2  faixa-ao-vivo-recusa-o-estado                  (ticket (a))
      track presente (a foto da CDP traz linhas) e worker NAO pronto: a
      superficie NAO recebe `carregando modelo…`, e a linha do player chega
      pela cadeia REAL (`ExternalCaptionWatcher._tick` -> `SottoShell.
      external_caption` -> `push_caption_to_window` -> slot -> `_drain_caption_pending`
      -> `overlay.set_text`);
  A3  faixa-ao-vivo-worker-pronto-sem-duplo-pintar    (ticket (b))
      o mesmo com o worker CARREGADO, e a MESMA linha entregue duas vezes: a
      superficie recebe-a UMA vez (`_tick` deduplica por `last_line`);
  A4  sem-faixa-worker-pronto-igual                   (ticket (d))
      sem faixa, o gate nao depende do estado do worker: o texto de estado
      pinta outra vez, e dois textos distintos pintam os dois;
  A5  ordem-do-arranque                               (ticket (e))
      `start_caption_pipeline` REAL: a sequencia registada e'
      `cdp, watcher, worker`, a porta CDP JA' esta' aberta quando o observador
      arranca, e um `start_worker` que LEVANTA nao impede `cdp` nem `watcher`;
  A6  queda-da-faixa-uma-so-vez                       (ticket (f))
      uma faixa que pinta e desaparece: `_release` corre UMA vez
      (`EXTERNAL_CAPTIONS_RELEASED`=1, `on_external_captions_released`=1) e os
      ticks seguintes nao o repetem; depois disso o texto de estado volta a
      pintar (a superficie e' do ASR outra vez);
  A7  cinco-abas-uma-a-tocar                          (ticket (g))
      5 abas `watch`, 3 sem video/pausadas, uma a tocar ->
      `youtube_cdp_source.pick_playing` / `boot_attach` escolhem A QUE TOCA e
      publicam `pick=<videoId> why=playing`;
  A8  duas-a-tocar-decide-e-nao-tropeca               (ticket (h))
      duas a tocar -> `choose_playing` devolve o MESMO id em chamadas
      sucessivas, e o id ja' adotado (`sticky-last`) fica;
  A9  nenhuma-a-tocar-nunca-e-ambiguo                 (ticket (i))
      nenhuma a tocar -> `no-playing` (um facto) ou `sticky-last` (o ultimo
      adotado); o `boot_attach` NUNCA escreve `reason=ambiguous` tres vezes.

`--neg-arm` muta uma COPIA do shell (as tres mutacoes que o ticket pede) e exige
que a arm de cada uma caia: rc=1 com `NEG-ARM` quando apanha todas, rc=0 se uma
escapar (a convencao `red-as-expected` da bateria).

NADA AQUI ABRE JANELA, CHROME OU DISPOSITIVO DE AUDIO: o transporte da CDP e' um
`/json/list` de fotografia numa porta efemera, o WebSocket e' um objecto falso
com respostas JSON, e a "superficie" e' um objecto que guarda o que o overlay
receberia. O Chrome do dono nunca e' tocado.
"""

from __future__ import annotations

import argparse
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, "app", "webview")
SHELL = os.path.join(WEBVIEW, "sotto_webview.py")
MODULE = os.path.join(WEBVIEW, "youtube_cdp_source.py")

LOADING_TEXT = "carregando modelo\u2026"
PLAYER_LINES = ["Have you ever had to kill a man?", "No."]


def _read(path):
    with io.open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _eol(text, sample):
    """`text` com as MESMAS terminações de linha que `sample` (o shell e' CRLF).

    Uma mutacao que nao aplica e' um mutante que escapa -- e o `assert` abaixo
    de cada uma existe exactamente para isso.
    """
    crlf = "\r\n" in sample
    return text.replace("\n", "\r\n") if crlf else text


def _load(path, name):
    """Importa o ficheiro pelo CAMINHO (as copias mutadas tambem sao executadas)."""
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# -- a superficie: o que o overlay receberia, e nada mais -------------------

class Surface:
    """A janela da legenda como ESPIA: guarda cada `set_text` que recebe."""

    def __init__(self):
        self.hwnd = 424242
        self.visible = True
        self._lock = threading.Lock()
        self.calls = []

    def set_work_area(self, *_a, **_k):
        return True

    def set_text(self, text, previous="", instant=False, cue=None, late_s=0.0):
        with self._lock:
            self.calls.append({"text": str(text or ""),
                               "instant": bool(instant),
                               "cue": bool(cue),
                               "late_s": float(late_s or 0.0)})
        return True

    def show(self, on=True):
        return True

    def hide(self):
        return True

    def texts(self):
        with self._lock:
            return [c["text"] for c in self.calls]

    def count(self, wanted):
        return sum(1 for t in self.texts() if wanted in t)


class _NullPolicy:
    def boundary(self, **_kwargs):
        return None


class _SnapSource:
    """A FONTE CDP cuja foto JA' tem as linhas do player (o DOM as tinha)."""

    def __init__(self, rows, why="painted"):
        self.rows = list(rows or ())
        self.why = why
        self.stopped = False

    def snapshot(self, max_age=0.6):
        if not self.rows:
            return None
        return {"rows": list(self.rows), "videoId": "MOZIBMBHK-8",
                "t": 12.5, "why": self.why, "stamp": time.monotonic()}

    def snapshot_age(self):
        return 0.0

    def stats(self):
        return {"reads": 1, "errors": 0}

    def stop(self):
        self.stopped = True


def _shell_class(shell_mod):
    """A shell REAL, com `__init__` fora (sem painel, sem WebView2, sem args)."""

    class _BootShell(shell_mod.SottoShell):
        def __init__(self, surface):
            self.caption_overlay = surface
            self._caption_wanted = True
            self._caption_window_shown = True
            self.visible = False
            self._overlay_pushes = 0
            self._source_epoch = 0
            self.display = {"scaleFactor": 1.0}
            self.external_caption_watcher = None
            self._yt_cdp_source = None
            self._player_frame_seen = False
            self.external_captions_active = False
            self.external_captions_available = False
            self.external_lines = 0
            self._external_last_text = ""
            self._reload_policy = _NullPolicy()
            self.emitted = []
            self.releases = 0
            self.bridge = None
            #: O que o `on_external_captions_released` REAL le' antes de correr:
            #: o evento de saida e o estado de estacionamento.
            self.exiting = threading.Event()
            self._external_parked = False

        # -- seams do ambiente (nao da regra) ---------------------------------
        def work_area(self):
            return {"x": 0, "y": 0, "width": 1920, "height": 1080}

        def emit(self, kind, payload=None):
            self.emitted.append((kind, payload))
            return True

        def emit_async(self, kind, payload=None):
            return self.emit(kind, payload)

        def _arm_caption_idle_hide(self):
            return False

        def _caption_lag_note(self, *_a, **_k):
            return None

        def on_external_captions_released(self):
            # CONTA e DELEGA: o corpo que limpa o epoch da superficie
            # (`shell._player_frame_seen`) e' o de producao, nao uma copia.
            self.releases += 1
            return shell_mod.SottoShell.on_external_captions_released(self)

    return _BootShell


def _boot_shell(shell_mod, source=None, bridge=None):
    surface = Surface()
    shell = _shell_class(shell_mod)(surface)
    watcher = shell_mod.ExternalCaptionWatcher(shell)
    watcher._yt_cdp_source = source
    shell.external_caption_watcher = watcher
    if source is not None:
        shell._yt_cdp_source = source
    if bridge is not None:
        shell.bridge = bridge
    return shell, watcher, surface


def _settle(seconds=0.6):
    """Deixa a thread REAL de pintura (`sotto-caption-paint`) fazer o seu turno."""
    end = time.monotonic() + float(seconds)
    while time.monotonic() < end:
        time.sleep(0.02)


class _LoadedBridge:
    """Um worker CARREGADO, para a arm que separa "pronto" de "a carregar"."""

    loaded = True


# -- A1: sem faixa, o estado honesto pinta ---------------------------------

def _arm_honest_state(shell_mod):
    shell, _w, surface = _boot_shell(shell_mod)
    painted = shell.on_worker_loading_text(LOADING_TEXT)
    _settle()
    texts = surface.texts()
    ok = (bool(painted) and LOADING_TEXT in "".join(texts)
          and not shell.player_track_owns_surface())
    return ok, "painted=%s surface=%r" % (painted, texts)


# -- A2: faixa presente + worker NAO pronto --------------------------------

def _arm_track_beats_loading(shell_mod):
    source = _SnapSource(PLAYER_LINES)
    shell, watcher, surface = _boot_shell(shell_mod, source=source)
    # A ORDEM DO ARRANQUE: o estado do modelo chega DEPOIS de a porta estar
    # aberta -- e a foto ja' traz as linhas do player.
    withheld = shell.on_worker_loading_text(LOADING_TEXT)
    _settle()
    after_loading = surface.texts()
    # ... e a linha do player chega pela cadeia real do observador.
    watcher._tick([("external:youtube:track", list(PLAYER_LINES))], True)
    _settle(1.0)
    texts = surface.texts()
    player_seen = any("kill a man" in t for t in texts)
    ok = (withheld is False
          and not any(LOADING_TEXT in t for t in texts)
          and not any(LOADING_TEXT in t for t in after_loading)
          and player_seen
          and shell.player_track_owns_surface())
    return ok, ("withheld=%s after_loading=%r surface=%r"
                % (withheld, after_loading, texts[-3:]))


# -- A3: faixa presente + worker pronto, sem pintura dupla -----------------

def _arm_track_worker_ready(shell_mod):
    source = _SnapSource(PLAYER_LINES)
    shell, watcher, surface = _boot_shell(shell_mod, source=source,
                                          bridge=_LoadedBridge())
    withheld = shell.on_worker_loading_text(LOADING_TEXT)
    _settle()
    for _ in range(2):                       # a MESMA linha duas vezes
        watcher._tick([("external:youtube:track", list(PLAYER_LINES))], True)
    _settle(1.0)
    texts = surface.texts()
    ok = (withheld is False
          and not any(LOADING_TEXT in t for t in texts)
          and sum(1 for t in texts if "kill a man" in t) == 1)
    return ok, "withheld=%s player_paints=%d surface=%r" % (
        withheld, sum(1 for t in texts if "kill a man" in t), texts)


# -- A4: sem faixa e worker pronto -> igual ao caso sem worker -------------

def _arm_no_track_ready(shell_mod):
    shell, _w, surface = _boot_shell(shell_mod, bridge=_LoadedBridge())
    shell.on_worker_loading_text("Starting worker... (sotto_worker.py)")
    _settle()
    shell.on_worker_loading_text(LOADING_TEXT)
    _settle()
    texts = surface.texts()
    ok = (any("Starting worker" in t for t in texts)
          and any(LOADING_TEXT in t for t in texts))
    return ok, "surface=%r" % (texts,)


# -- A5: a ordem do arranque -----------------------------------------------

class _StubCdp:
    """Um `/json/list` de fotografia (uma aba `watch`), zero Chrome."""

    def __init__(self, tabs):
        from http.server import BaseHTTPRequestHandler, HTTPServer
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

            def log_message(self, *_args):
                return

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.port = int(self.httpd.server_address[1])
        self.thread = threading.Thread(target=self.httpd.serve_forever,
                                       name="stub-cdp-boot", daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3.0)
        return False


def _watch_tab(video_id, ws_suffix):
    return {"type": "page",
            "url": "https://www.youtube.com/watch?v=%s" % video_id,
            "title": "video %s" % video_id,
            "webSocketDebuggerUrl": "ws://127.0.0.1:1/devtools/page/%s"
                                    % ws_suffix}


def _arm_boot_order(shell_mod, port):
    """A ordem REAL do pipeline, com o pedido CDP REAL contra uma foto."""
    events = []

    class _PipeShell(shell_mod.SottoShell):
        def __init__(self):
            self._caption_pipeline_started = False
            self._yt_cdp_source = None
            self.args = None
            self.events = events
            self.source_at_watcher = None
            self.worker_error_logged = False

        def _worker_autostart_reason(self, _args=None):
            # `declined` porque o `VramGuard` nao pertence a esta arm -- o
            # worker dela LEVANTA de proposito, e um guarda a ler `_vram_parked`
            # de uma shell de fotografia so' poria ruido no resultado.
            return "declined"

        def _yt_cdp_boot_attach(self):
            events.append("cdp")
            return shell_mod.SottoShell._yt_cdp_boot_attach(self)

        def start_external_caption_watcher(self):
            self.source_at_watcher = bool(getattr(self, "_yt_cdp_source", None))
            events.append("watcher")
            return True

        def start_worker(self, reason):
            events.append("worker")
            raise RuntimeError("fotografia: o worker nao pode ser pre-condicao")

        def start(self, *_a, **_k):           # VramGuard nao corre aqui
            return False

    old_port = os.environ.get("SOTTO_YT_CDP_PORT")
    old_cdp = os.environ.get("SOTTO_YT_CDP")
    os.environ["SOTTO_YT_CDP_PORT"] = str(port)
    os.environ.pop("SOTTO_YT_CDP", None)
    lines = []
    old_log = shell_mod.log
    shell_mod.log = lines.append
    sh = _PipeShell()
    source = None
    try:
        shell_mod.SottoShell.start_caption_pipeline(sh, "pre-webview")
        source = getattr(sh, "_yt_cdp_source", None)
        fails = [ln for ln in lines if "CAPTION_PIPELINE_STEP_FAILED step=worker" in ln]
        order_log = [ln for ln in lines if "CAPTION_PIPELINE_ORDER" in ln]
        ok = (events == ["cdp", "watcher", "worker"]
              and bool(sh.source_at_watcher)
              and bool(fails)
              and bool(order_log)
              and "steps=cdp,watcher,worker" in order_log[0]
              and bool(source is not None and source is not False))
        return ok, ("events=%s source_at_watcher=%s worker_fail_logged=%s %r"
                    % (events, sh.source_at_watcher, bool(fails),
                       (order_log or ["-"])[0][:80]))
    finally:
        shell_mod.log = old_log
        if source is not None and source is not False:
            try:
                source.stop()
                if getattr(source, "_thread", None) is not None:
                    source._thread.join(timeout=3.0)
            except Exception:                 # noqa: BLE001
                pass
        if old_port is None:
            os.environ.pop("SOTTO_YT_CDP_PORT", None)
        else:
            os.environ["SOTTO_YT_CDP_PORT"] = old_port
        if old_cdp is None:
            os.environ.pop("SOTTO_YT_CDP", None)
        else:
            os.environ["SOTTO_YT_CDP"] = old_cdp


# -- A6: a faixa desaparece -> UMA queda, e o estado volta -----------------

def _arm_track_goes_away(shell_mod):
    """Uma faixa que pinta e desaparece: UMA queda, e o estado volta."""
    source = _SnapSource(PLAYER_LINES)
    shell, watcher, surface = _boot_shell(shell_mod, source=source)
    watcher._tick([("external:youtube:track", list(PLAYER_LINES))], True)
    _settle(1.0)
    if not any("kill a man" in t for t in surface.texts()):
        return False, "setup: a linha do player nao chegou (%r)" % (surface.texts(),)
    # A FAIXA DESAPARECE: o DOM deixa de ter linhas (a foto fica vazia) e o
    # observador publica a queda pela porta de producao (`no-track`).
    source.rows = []
    lines = []
    old_log = shell_mod.log
    shell_mod.log = lines.append
    try:
        # A QUEDA DE PRODUCAO: o laco do observador encontra o silencio depois
        # de `YT_RELEASE_S` e solta o player UMA vez -- nas leituras seguintes,
        # e no `no-track` urgente que chega depois, ja' nao ha' transicao.
        watcher.last_seen = time.monotonic() - (watcher.YT_RELEASE_S + 1.0)
        watcher._tick([], True)
        watcher._tick([], True)
        watcher._tick([], True)
        watcher._release("youtube-no-track")
        watcher._release("youtube-no-track")
    finally:
        shell_mod.log = old_log
    releases = sum(1 for ln in lines if "EXTERNAL_CAPTIONS_RELEASED" in ln)
    # ... e depois da queda o estado honesto volta a ter direito ao ecra. A
    # janela de 2 s do `_yt_owner_until` (a guarda que impede o ASR de pintar
    # por cima do player) tem de fechar primeiro: ela e' sobre QUEM PINTA, nao
    # sobre o estado, e o proximo `model-loading` real chega bem depois dela.
    _settle(2.1)
    shell.on_worker_loading_text(LOADING_TEXT)
    _settle()
    back = sum(1 for t in surface.texts() if LOADING_TEXT in t)
    ok = (releases == 1 and shell.releases == 1 and back == 1
          and not shell.player_track_owns_surface())
    return ok, ("releases=%d shell_releases=%d loading_after=%d owns=%s"
                % (releases, shell.releases, back,
                   shell.player_track_owns_surface()))


# -- A7/A8/A9: a escolha da aba --------------------------------------------

class _FakeConn:
    """Uma ligacao CDP falsa: entrega as respostas que lhe foram dadas."""

    def __init__(self, frames):
        self.frames = list(frames)

    def send(self, _data):
        return None

    def recv(self):
        if not self.frames:
            raise ValueError("sem resposta")
        return self.frames.pop(0)

    def settimeout(self, _timeout):
        return None

    def close(self):
        return None


def _resp(seq, video_id, t, paused=False, ended=False):
    payload = json.dumps({"videoId": video_id, "t": t, "paused": paused,
                          "ended": ended, "dur": 600.0, "vis": "visible"})
    return json.dumps({"id": seq,
                       "result": {"result": {"value": payload}}})


def _make_connect(table):
    """`connect(url)` -> uma ligacao com as DUAS leituras daquela aba.

    `table[url] == (video_id, t0, paused, ended, t1)`: a primeira leitura
    devolve `t0` e a segunda `t1`, que e' como `probe_tabs` mede o avanco do
    `currentTime` -- a unica prova de "a tocar" que nao depende da bandeira
    `paused` de uma aba em segundo plano.
    """

    def connect(url, timeout=None, **_kwargs):  # noqa: ANN001
        if url not in table:
            raise OSError("sem aba nesta fotografia: %s" % url)
        vid, t0, paused, ended, t1 = table[url]
        frames = [_resp(1, vid, t0, paused=paused, ended=ended),
                  _resp(2, vid, t1, paused=paused, ended=ended)]
        return _FakeConn(frames)

    return connect


def _arm_pick_playing(mod):
    """5 abas `watch`, 3 sem video/pausadas, uma a tocar."""
    tabs = [_watch_tab("aaaaaaaaaaa", "aaaaaaaaaaa"),
            _watch_tab("bbbbbbbbbbb", "bbbbbbbbbbb"),
            _watch_tab("ccccccccccc", "ccccccccccc"),
            _watch_tab("ddddddddddd", "ddddddddddd"),
            _watch_tab("PLAYINGPLAY", "PLAYINGPLAY")]
    table = {
        # 3 junk: sem id / pausadas
        "ws://127.0.0.1:1/devtools/page/aaaaaaaaaaa": ("", 0.0, True, False, 0.0),
        "ws://127.0.0.1:1/devtools/page/bbbbbbbbbbb": ("bbbbbbbbbbb", 10.0, True, False, 10.0),
        "ws://127.0.0.1:1/devtools/page/ccccccccccc": ("ccccccccccc", 20.0, False, True, 20.0),
        "ws://127.0.0.1:1/devtools/page/ddddddddddd": ("ddddddddddd", 30.0, True, False, 30.0),
        # a que toca: currentTime a ANDAR entre as duas leituras
        "ws://127.0.0.1:1/devtools/page/PLAYINGPLAY": ("PLAYINGPLAY", 40.0, False, False, 40.5),
    }
    connect = _make_connect(table)
    tab, vid, why = mod.pick_playing(tabs, "", connect=connect, gap_s=0.0)
    picked = str((tab or {}).get("webSocketDebuggerUrl") or "")
    logs = []
    with _StubCdp(tabs) as stub:
        ok_boot, boot_why = mod.boot_attach(port=stub.port, attempts=1,
                                            delay=0, log=logs.append,
                                            sleep=lambda _s: None,
                                            connect=connect)
    boot_line = " ".join(ln for ln in logs if "YOUTUBE_CDP_BOOT_ATTACH" in ln)
    ok = (vid == "PLAYINGPLAY" and why == "playing"
          and "PLAYINGPLAY" in picked
          and ok_boot is True and boot_why == "playing"
          and "pick=PLAYINGPLAY" in boot_line
          and "why=playing" in boot_line)
    return ok, ("pick=%s why=%s boot=%s/%s %r"
                % (vid, why, ok_boot, boot_why, boot_line[:120]))


def _arm_two_playing(mod):
    """Duas a tocar: decide, e nao tropeca entre leituras."""
    probes = [{"videoId": "AAAAAAAAAAA", "t0": 1.0, "t1": 1.6, "paused": False,
               "ended": False, "advance": 0.6},
              {"videoId": "BBBBBBBBBBB", "t0": 5.0, "t1": 5.4, "paused": False,
               "ended": False, "advance": 0.4}]
    first = mod.choose_playing(probes, "")
    second = mod.choose_playing(probes, "")
    sticky = mod.choose_playing(probes, "BBBBBBBBBBB")
    sticky_again = mod.choose_playing(probes, "BBBBBBBBBBB")
    ok = (first == second and first[0] == "AAAAAAAAAAA"
          and first[1] == "playing"
          and sticky == sticky_again == ("BBBBBBBBBBB", "sticky-last"))
    return ok, "first=%r second=%r sticky=%r" % (first, second, sticky)


def _arm_none_playing(mod):
    """Nenhuma a tocar: `no-playing` ou `sticky-last`, nunca `ambiguous`."""
    tabs = [_watch_tab("aaaaaaaaaaa", "aaaaaaaaaaa"),
            _watch_tab("bbbbbbbbbbb", "bbbbbbbbbbb")]
    table = {
        "ws://127.0.0.1:1/devtools/page/aaaaaaaaaaa": ("aaaaaaaaaaa", 10.0, True, False, 10.0),
        "ws://127.0.0.1:1/devtools/page/bbbbbbbbbbb": ("bbbbbbbbbbb", 20.0, True, False, 20.0),
    }
    connect = _make_connect(table)
    _tab, vid, why = mod.pick_playing(tabs, "", connect=connect, gap_s=0.0)
    _tab2, vid2, why2 = mod.pick_playing(tabs, "bbbbbbbbbbb",
                                        connect=connect, gap_s=0.0)
    logs = []
    with _StubCdp(tabs) as stub:
        ok_boot, reason = mod.boot_attach(port=stub.port, attempts=3, delay=0,
                                          log=logs.append,
                                          sleep=lambda _s: None,
                                          connect=connect)
    told = [ln for ln in logs if "YOUTUBE_CDP_BOOT_ATTACH" in ln]
    ok = (vid == "" and why == "no-playing"
          and vid2 == "bbbbbbbbbbb" and why2 == "sticky-last"
          and ok_boot is False and reason == "no-playing"
          and len(told) == 3
          and not any("ambiguous" in ln for ln in told))
    return ok, ("none=%r sticky=%r boot=(%s,%s) told=%d"
                % ((vid, why), (vid2, why2), ok_boot, reason, len(told)))


# -- as arms ----------------------------------------------------------------

def arms(shell_path=SHELL, module_path=MODULE, port_holder=None):
    shell_mod = _load(shell_path, "sotto_shell_first_boot_%d"
                      % (int(time.monotonic() * 1000) % 100000))
    mod = _load(module_path, "yt_cdp_first_boot_%d"
                % (int(time.monotonic() * 1000) % 100000))
    out = []
    ok, note = _arm_honest_state(shell_mod)
    out.append(("sem-faixa-o-estado-e-honesto", ok, note))
    ok, note = _arm_track_beats_loading(shell_mod)
    out.append(("faixa-ao-vivo-recusa-o-estado", ok, note))
    ok, note = _arm_track_worker_ready(shell_mod)
    out.append(("faixa-ao-vivo-worker-pronto-sem-duplo-pintar", ok, note))
    ok, note = _arm_no_track_ready(shell_mod)
    out.append(("sem-faixa-worker-pronto-igual", ok, note))
    with _StubCdp([_watch_tab("MOZIBMBHK-8", "boot")]) as stub:
        ok, note = _arm_boot_order(shell_mod, stub.port)
    out.append(("ordem-do-arranque", ok, note))
    ok, note = _arm_track_goes_away(shell_mod)
    out.append(("queda-da-faixa-uma-so-vez", ok, note))
    ok, note = _arm_pick_playing(mod)
    out.append(("cinco-abas-uma-a-tocar", ok, note))
    ok, note = _arm_two_playing(mod)
    out.append(("duas-a-tocar-decide-e-nao-tropeca", ok, note))
    ok, note = _arm_none_playing(mod)
    out.append(("nenhuma-a-tocar-nunca-e-ambiguo", ok, note))
    del port_holder
    return out


# -- o negativo -------------------------------------------------------------

def neg_arm():
    """Tres mutacoes numa COPIA do shell; cada uma derruba a SUA arm."""
    tmp = tempfile.mkdtemp(prefix="yt-first-boot-neg-")
    try:
        src = _read(SHELL)
        results = []

        def cut(text):
            return _eol(text, src)

        # 1) O TEXTO DE ESTADO PASSA POR CIMA DA FAIXA (a cura desligada).
        mut = os.path.join(tmp, "shell_sem_portao.py")
        body = src.replace(cut("        if owned:\n"),
                           cut("        if False:\n"), 1)
        io.open(mut, "w", encoding="utf-8", newline="").write(body)
        got = dict((n, ok) for n, ok, _ in arms(shell_path=mut))
        results.append(("o-estado-por-cima-da-faixa",
                        not got.get("faixa-ao-vivo-recusa-o-estado", True)))

        # 2) O OBSERVADOR SO' ARRANCA DEPOIS DO WORKER (a ordem antiga).
        mut2 = os.path.join(tmp, "shell_ordem_antiga.py")
        body2 = src.replace(cut("        steps = (\n"
            "            ('cdp', _cdp_step),\n"
            "            ('watcher', lambda: self.start_external_caption_watcher()),\n"
            "            ('worker', lambda: self.start_worker(\n"
            "                self._worker_autostart_reason(self.args))),\n"
            "        )"),
            cut("        steps = (\n"
            "            ('cdp', _cdp_step),\n"
            "            ('worker', lambda: self.start_worker(\n"
            "                self._worker_autostart_reason(self.args))),\n"
            "            ('watcher', lambda: self.start_external_caption_watcher()),\n"
            "        )"), 1)
        assert body2 != src, "a mutacao da ordem nao aplicou"
        io.open(mut2, "w", encoding="utf-8", newline="").write(body2)
        got2 = dict((n, ok) for n, ok, _ in arms(shell_path=mut2))
        results.append(("observador-depois-do-worker",
                        not got2.get("ordem-do-arranque", True)))

        # 3) A QUEDA DISPARA A CADA TICK (o flicker loop).
        mut3 = os.path.join(tmp, "shell_queda_cadencia.py")
        body3 = src.replace(
            cut("        if self._released_for_silence and not had_line:\n"
                "            return False\n"), "", 1)
        assert body3 != src, "a mutacao da queda nao aplicou"
        io.open(mut3, "w", encoding="utf-8", newline="").write(body3)
        got3 = dict((n, ok) for n, ok, _ in arms(shell_path=mut3))
        results.append(("queda-dispara-duas-vezes",
                        not got3.get("queda-da-faixa-uma-so-vez", True)))
        return results
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)
    if args.neg_arm:
        results = neg_arm()
        bad = 0
        for name, caught in results:
            print("NEG-ARM %-32s %s"
                  % (name, "CAUGHT" if caught else "NOT-CAUGHT"))
            bad += 0 if caught else 1
        print("NEG-ARM: %s (%d/%d mutantes apanhados)"
              % ("PASS" if not bad else "FAIL", len(results) - bad, len(results)))
        return 1 if not bad else 0
    results = arms()
    failed = 0
    for name, ok, note in results:
        print("%-42s %s  %s" % (name, "PASS" if ok else "FAIL", note))
        failed += 0 if ok else 1
    print("YOUTUBE-FIRST-AT-BOOT VERDICT: %s (%d/%d)"
          % ("PASS" if not failed else "FAIL",
             len(results) - failed, len(results)))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
