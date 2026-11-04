"""
Sotto — the WebView2 shell.

This REPLACES the Electron shell (app/_legacy-electron/main.js) as the app's window,
and it is a replacement, not a rewrite of the panel: panel.html / panel.css /
panel.js are loaded byte-for-byte from app/panel/, unmodified. The only
thing this file owns is the surface they talk to — the `window.sotto` object —
and that surface is a line-for-line port of app/_legacy-electron/preload.js.

  preload.js  ->  WebView2 equivalent
  ---------------------------------------------------------------------
  contextBridge.exposeInMainWorld  ->  CoreWebView2.
                                       AddScriptToExecuteOnDocumentCreatedAsync
  ipcRenderer.on  ->  ExecuteScriptAsync(window.__sotto_emit(...))
  ipcRenderer.send -> chrome.webview.postMessage -> pywebview's own WebMessage
                                       pump -> js_bridge_call -> dispatch()
  ipcRenderer.invoke -> the same channel plus a reply id

`AddScriptToExecuteOnDocumentCreatedAsync` is the exact analogue of Electron's
`preload:` webPreference: it runs in the page's main world before any page
script, on every navigation, so panel.js sees `window.sotto` already defined
when it runs at the bottom of <body>. That is why the panel needed no edit —
and panel.js's own "Preload bridge missing" branch is the receipt when it
fails (see `--dump-dom`, which asserts that string is absent).

Geometry is a port of main.js::dockRight, and the `--dump-dom` probe is the
SAME probe text main.js runs, so the two arms' numbers can be diffed.

Deliberate divergences from the Electron arm, all named in
docs/webview-shell-20261006.md:
  * MOD_NOREPEAT on the hotkey, so holding Alt+C does not machine-gun the panel.
  * No `setVisibleOnAllWorkspaces` equivalent (WebView2/WinForms has none).
  * The worker's cosmetic state-name map (worker-bridge.js STATE_MAP) is not
    ported; raw worker states pass through, and the two status INVARIANTS that
    protect the panel (never empty, never "no audio") are.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import math          # search: edit budgets are ceil(ratio * len)
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata  # search: folding the diacritics off
from datetime import datetime

import hot_reload
import panel_focus as _panel_focus
import bridge_census as _bridge_census_mod
from code_identity import code_identity as _code_identity
import panel_state


# ── O INSTRUMENTO DO SELFTEST VIVE EM `app/webview/selftest_instrument.py` ───
# `--selftest` e `--probe-reload` sao MEDICOES, e o instrumento que as faz vivia
# dentro deste ficheiro -- que esta' debaixo do ratchet estrutural
# (`_main/code-health-oracle.py`). Ver o cabecalho do modulo ao lado. Os nomes sao
# os MESMOS de proposito: `sotto_webview.selftest_broken`, `.run_selftest`,
# `.foreground_window`, `.window_pid`, `.probe_reload` e os `SELFTEST_*` continuam
# a existir para quem os le' de fora (a largada e os oraculos
# `selftest-focus`/`altc-first-caption`), por isso a lista abaixo e' a superficie
# historica deste modulo e nao "imports por usar".
import selftest_instrument
from selftest_instrument import (  # noqa: F401 -- superficie historica do shell
    SELFTEST_COLD_WINDOW_S, SELFTEST_PRESS_WINDOW_S, SELFTEST_STEP_BUDGET_MS,
    SELFTEST_STEP_WINDOW_S, foreground_window, run_selftest, selftest_broken,
    window_pid)

# ── AS TRES STRUCTS WIN32 PURAS VIVEM EM `app/webview/win32_types.py` ────────
# `RECT`, `POINT` e `CURSORINFO` sao `ctypes.Structure` sem logica, e o ratchet
# conta CLASSES por ficheiro: com a leitura de pointer lock o shell passou de 25
# para 26 e o tecto nao se sobe -- extrai-se. Os nomes sao os MESMOS.
from win32_types import CURSORINFO, POINT, RECT


HERE = os.path.dirname(os.path.abspath(__file__))
#: The panel UI. Read-only for this shell: these are the app's own panel files
#: and they are the contract, not ours to change.
PANEL_DIR = os.path.normpath(os.path.join(HERE, os.pardir, 'panel'))
PANEL_HTML = os.path.join(PANEL_DIR, 'panel.html')
#: A LEGENDA TEM PAGINA PROPRIA. Ver o cabecalho de `caption.html` -- a legenda era
#: empilhada dentro da janela da barra, e uma janela partilhada nao consegue pousa-la no
#: fundo da TELA. Esta pagina e carregada por uma SEGUNDA janela pywebview.
CAPTION_HTML = os.path.join(PANEL_DIR, 'caption.html')
#: An empty page the shell opens FIRST, so the preload is registered before the
#: panel is ever parsed. See stage.html for why the ordering needs buying.
STAGE_HTML = os.path.join(HERE, 'stage.html')
#: WHICH TRANSCRIBER THE APP RUNS. ** THIS IS STILL `sotto_worker.py`, AND ON
#: 2026-10-18 I CHANGED IT TO `redux_live.py` AND REVERTED IT WITHIN MINUTES. **
#:
#: The revert is the finding, so it is written down rather than edited away.
#: `redux_live.py` speaks the same wire contract and is 586 MB against 1 988 MB,
#: so on the contract alone it looked like a safe default. It is not: the shell
#: builds the worker's command line from the worker's OWN flags, and the two
#: parsers are not the same. Measured, diffing every `add_argument`:
#:
#:     shared (5):   config device max-seconds stats-interval threads
#:     worker-only (24): --target-pid --selftest --tap-peak-floor --tap-window
#:                        --lang-id --panel-visibility --meter-hz --max-chunks
#:                        --redux-live --redux-live-engine --redux-live-threads
#:                        --redux-live-keep --redux-live-min-audio
#:                        --redux-live-deadline --redux-batch --redux-when-hidden
#:                        --redux-min-free-mb --redux-runner-timeout ... and more
#:
#: Pointing the default at `redux_live.py` would have handed that program a
#: `--target-pid` it does not define, and argparse exits 2 on an unknown flag:
#: no captions at all, on the per-app capture path, on the selftest path, and
#: on every tuning flag the shell forwards. **A smaller model is not a drop-in
#: replacement for the process.**
#:
#: THE REAL ANSWER, which is in the 24: `sotto_worker.py` ALREADY HOSTS THE
#: PARAKEEP. `--redux-live` and `--redux-live-engine` are the worker's own
#: switches for it. So the owner's real question -- *"por que tu nao
#: simplesmente swapa as legendas pelas mais precisas, sem o usuario nem
#: notar?"* -- has an answer that does not touch this constant at all: the
#: ENGINE changes, the PROCESS does not.
#:
#: HOW TO GO BACK: `SOTTO_WORKER=sotto_worker.py`, or `--worker <path>`.
DEFAULT_WORKER_PATH = os.path.normpath(
    os.path.join(HERE, os.pardir, os.pardir, 'worker', 'sotto_worker.py')
)


def file_url(path):
    """`file:///C:/...` — an explicit file URL, like Electron's loadFile().

    Passing a bare path to pywebview does NOT open the file: `_resolve_url`
    sees a local path and silently starts pywebview's own HTTP server over it
    (window.py:277-280), so the panel arrived as
    `http://127.0.0.1:23602/electron/panel.html` and, because that server was
    started with only the staging file in its route table, it answered
    `Error: 404 Not Found` — measured, with the probe reporting
    `hasPanelElement: false`. An explicit `file://` URL skips the server
    entirely, which is also what the Electron arm did.
    """
    return 'file:///' + os.path.abspath(path).replace('\\', '/')

# --- geometry constants — the port of main.js:39-50 -------------------------
PANEL_WIDTH = 380
PANEL_HEIGHT = 900
PANEL_MARGIN = 12
#: The strip's own bottom gap. 12 px glued the bar to the taskbar and the owner
#: reported it "spawnando muito abaixo"; 44 px leaves air under the caption bar.
STRIP_MARGIN = 44
PANEL_MAX_WORK_FRACTION = 0.34
MAX_CAPTIONS = 200

# --- the deferred-asset gate -----------------------------------------------
# Owner's order, 2026-10-12, verbatim: "o sotto nao deve carregar tudo de uma vez,
# apenas o essential". These five resources are NOT on the critical path of the
# first caption, so the shell answers each with an EMPTY body until the page asks
# for the real bytes over the bridge (`lazy-asset`). The loader that asks is
# app/panel/lazy-assets.js, appended to BOOTSTRAP_JS below, which reads the SAME
# three theme sources theme-switcher.js reads (localStorage, then the document's
# own data-theme, then the manifest fallback) — because the WebView2 user-data-dir
# is persistent, a theme picked in an earlier session can be the theme of this one.
#
# WHY EACH IS SAFE TO DEFER (scopes measured on disk, not assumed):
#   themes/cinematic.css    312 230 B  every rule scoped :root[data-theme^='cine-']
#   themes/panel-designs.css 128 716 B  every rule scoped :root[data-theme='pd-*']
#   skins/skins.js           812 978 B  window.SOTTO_SKINS, read ONCE at parse time
#                                       by skin-host.js -> the pair is deferred
#                                       together, in this order, never reversed.
#   skin-host.js              22 712 B  every panel.js call site is guarded by
#                                       window.SottoSkin && .active.
#   skin-layout.css           11 210 B  rules gated on body[data-skin].
# Deferred total: 1 287 846 B of the 1 821 083 B asset payload (70.7 %).
LAZY_ASSETS = (
    'themes/cinematic.css',
    'themes/panel-designs.css',
    'skins/skins.js',
    'skin-host.js',
    'skin-layout.css',
)
LAZY_LOADER_JS = os.path.join(PANEL_DIR, 'lazy-assets.js')


def _lazy_asset_path(rel):
    return os.path.join(PANEL_DIR, rel.replace('/', os.sep))


def _lazy_asset_url(rel):
    return file_url(_lazy_asset_path(rel))


class LazyAssetGate(object):
    """Serve an EMPTY body for a deferred URL until the page asks for the real one.

    The gate is a SET, not a flag: each URL is allowed independently, because a
    `cine-*` theme needs `themes/cinematic.css` and the skin pair but NOT
    `themes/panel-designs.css`, and a `pd-*` theme needs only the last of the
    three. The page's `lazy-asset` message is the only writer; the resource
    handler is the only reader, and it never lets an un-asked request through to
    the disk.
    """

    def __init__(self, core, enabled=True):
        from Microsoft.Web.WebView2.Core import (
            CoreWebView2WebResourceContext,
            CoreWebView2WebResourceRequestedEventArgs,
        )
        self._core = core
        self._enabled = bool(enabled)
        self._allowed = set()
        self._urls = set(_lazy_asset_url(r) for r in LAZY_ASSETS)
        self._ctx = CoreWebView2WebResourceContext.All
        self._args_type = CoreWebView2WebResourceRequestedEventArgs
        self.registered = 0
        if self._enabled:
            self._register()

    def _register(self):
        for rel in LAZY_ASSETS:
            try:
                self._core.AddWebResourceRequestedFilter(
                    _lazy_asset_url(rel), self._ctx)
                self.registered += 1
            except Exception as exc:
                log(f'PANEL_LAZY_FILTER_FAILED url={rel} error={exc!r}')

    def on_resource_requested(self, sender, args):
        """The WebResourceRequested handler. Runs on the UI thread."""
        if not self._enabled:
            return
        try:
            uri = args.Request.Uri
        except Exception:
            return
        if uri not in self._urls:
            return
        if uri in self._allowed:
            return  # the page has asked: let it reach the disk
        response = self._make_empty_response(uri)
        if response is None:
            # FAIL OPEN, AND THIS IS THE IMPORTANT HALF. A gate that cannot
            # serve its empty body must NEVER block the asset: the owner's
            # panel is worth more than the deferred bytes, and an interception
            # that cannot answer is a broken panel waiting to happen.
            self._allowed.add(uri)
            log(f'PANEL_LAZY_FAIL_OPEN url={uri} why=no-response')
            return
        try:
            args.Response = response
            log(f'PANEL_LAZY_EMPTY url={uri}')
        except Exception as exc:
            self._allowed.add(uri)
            log(f'PANEL_LAZY_FAIL_OPEN url={uri} why=assign error={exc!r}')

    def _make_empty_response(self, uri):
        """An empty 200 for `uri`, or `None` when this WebView2 cannot build one.

        MEASURED FAILURE THIS EXISTS FOR, on the owner's own box: EVERY one of
        the 116 gate firings in `_main/webview-run.log` logged

            PANEL_LAZY_EMPTY_FAILED url=.../themes/panel-designs.css
            error=AttributeError("'CoreWebView2' object has no attribute
            'CreateWebResourceResponse'")

        so the gate never served a single empty body. `CreateWebResourceResponse`
        is a method of `CoreWebView2Environment`, not of `CoreWebView2`; the
        property that reaches it from the CoreWebView2 is `Environment`. The old
        call is kept as a second candidate so a host where the first name is
        absent still works, and `None` is a real answer the caller acts on.
        """
        from System.IO import MemoryStream
        headers = ('Content-Type: ' + _lazy_mime(uri) + '\r\n'
                   'Content-Length: 0\r\n')
        candidates = []
        env = getattr(self._core, 'Environment', None)
        if env is not None:
            candidates.append((env, 'core.Environment'))
        candidates.append((self._core, 'core'))
        why = 'no candidate'
        for obj, how in candidates:
            maker = getattr(obj, 'CreateWebResourceResponse', None)
            if maker is None:
                why = f'{how} has no CreateWebResourceResponse'
                continue
            try:
                return maker(MemoryStream(), 200, 'OK', headers)
            except Exception as exc:  # noqa: BLE001
                why = f'{how} raised {exc!r}'
        log(f'PANEL_LAZY_RESPONSE_UNAVAILABLE url={uri} why={why}')
        return None

    def allow(self, url):
        """Mark one deferred URL as wanted by the page. Idempotent."""
        if not self._enabled:
            return False
        if not isinstance(url, str):
            return False
        # Accept both the bare relative path and the full file:// URL.
        rel = url.replace('\\', '/')
        if rel.startswith('file:///'):
            rel = rel[len('file:///'):].replace('/', os.sep)
            if os.path.isabs(rel):
                rel = os.path.relpath(rel, PANEL_DIR)
        rel = rel.replace(os.sep, '/')
        if rel not in LAZY_ASSETS:
            return False
        full = _lazy_asset_url(rel)
        if full in self._allowed:
            return False
        self._allowed.add(full)
        log(f'PANEL_LAZY_ALLOW url={rel}')
        return True

    def close(self):
        self._allowed.clear()


def _lazy_mime(uri):
    if uri.endswith('.css'):
        return 'text/css'
    if uri.endswith('.js'):
        return 'text/javascript'
    return 'application/octet-stream'


# --- the panel AS TEXT: one JSON dump a reader opens with `read` ------------
# Owner's order, 2026-10-06, verbatim: "faz uma versao do sotto ou painel que tu
# pode ver sem precisar da visao". Until now the panel's state was only knowable
# through a screen capture, and a capture needs vision and is limited in time.
# The dump is written from state the shell ALREADY holds — the bridge's own
# counters, the panel's own live box read over the existing `exec_js` seam, and
# the `WORKER_STATS` line the bridge already reads off the worker's stderr — so
# it is a READ channel, not a second pipeline. Nothing the owner sees changes.
REPO_ROOT = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir))
PANEL_STATE_PATH = os.path.join(REPO_ROOT, '_main', 'panel-state.json')
#: The on-demand trigger: create this file and the next tick dumps immediately
#: (`py app/webview/panel_state.py --request`).
PANEL_STATE_REQUEST = PANEL_STATE_PATH + '.request'
PANEL_STATE_INTERVAL_S = 2.0

# --- THE UI MARSHALLING BOUNDS (2026-10-20) --------------------------------
# MEASURED 2026-10-20 on the OWNER'S OWN log (`I:\cc-tmp\sotto-012524.log`,
# the app launched at 01:25:24): 93 `UI_THREAD_STALL begin-invoke not run in
# 10 s` and 68 `exec_js TIMEOUT after 10.0s` -- ALL of them inside ONE 50 s
# window (01:55:30 -> 01:56:20), while a design lane was rendering 45 themes
# with headless Edge. The LOAD is the TRIGGER; the CODE is the FREEZE.
#
# THE CHAIN, read in the code: `panel.js` pulls `getStats()` every 1000 ms ->
# `_stats()` -> `reply_stats()` -> `exec_js()` (SYNCHRONOUS, 10 s budget) ->
# `_ui()` -> `form.BeginInvoke` + `done.wait(10)`. A busy UI thread therefore
# did not only delay the stats: it HELD the pump thread -- the one that
# carries the captions -- for 10 s at a time, 93 times.
UI_MARSHAL_TIMEOUT_S = 10.0      # the DEFAULT budget of `_ui` (unchanged)
#: THE TRANSPARENCY HACK'S WAIT (2026-10-21). The hack marshals `form.Show()`
#: onto the UI thread, and the caller is the HOTKEY thread -- the thread that
#: owns the owner's ONLY control. `_ui`'s default budget is TEN SECONDS, so a
#: busy UI thread turned an Alt+C into a ten-second wait for a window that was
#: already on its way: the owner's *"abrir o sotto trava"*. A quarter of a
#: second is enough when the UI thread is idle (the common case); when it is
#: not, the hack is POSTED instead of waited for (see `transparency_hack`).
TRANSPARENCY_HACK_WAIT_S = 0.25
#: ── THE PAINT ACK (2026-11-01), e o defeito que ele fecha ───────────────────
#: O dono, verbatim: *"o painel dar show, nao deve carregar o background e
#: mostrar, e depois carregar a ui ou algo assim."* Um `ShowWindow` de user32
#: mapeia o FORM; nada nessa chamada pergunta a' PAGINA se ela tem uma frame
#: para apresentar. Isto pergunta: `window.__sotto_paint(seq)` arma DOIS
#: `requestAnimationFrame`s e so' depois escreve `window.__sotto_paint_ack = seq`.
#: DOIS porque o primeiro callback corre ANTES de o estilo/layout/paint daquela
#: frame estar commitado -- o segundo e' o primeiro tick que corre DEPOIS de um
#: paint ter sido apresentado.
#:
#: A ESPERA E' LIMITADA E FALHA ABERTA. Uma pagina cujo rAF nunca corre (uma
#: janela ESCONDIDA e' travada pelo compositor nesta maquina) nao pode custar ao
#: dono um Alt+C que nao faz nada: passados `PAINT_ACK_TIMEOUT_MS` o show
#: prossegue e a linha diz `paint_ack=false`, para o log nunca afirmar uma espera
#: que nao aconteceu. O veredicto de que a primeira frame tem conteudo e' do
#: instrumento (`_main/panel-paint-first-census.py`), nao desta linha.
#:
#: 60 -> 400 ms EM 2026-11-01, e o numero e' MEDIDO: o MESMO caminho acusou o
#: primeiro ack frio em **187 ms** no `side` e **47 ms** no `strip` (16/0 ms
#: quentes). A 60 ms a cura valia 28 ms: a espera terminava antes de a pagina
#: responder. 400 ms fica ao dobro dos 187 ms e longe dos 1500 ms do gesto
#: (`_main/altc-first-caption-oracle.py`). O ack NAO e' a cura inteira, so' a
#: parte que a pagina pode confirmar -- o custo da PRIMEIRA pintura e' pago em
#: `_warm_paint`, porque ele nao aparece em frame nenhuma antes de o dono ver.
PAINT_ACK_TIMEOUT_MS = 400
#: O AQUECIMENTO DA PRIMEIRA PINTURA (2026-11-01): 2x os **325 ms** medidos,
#: pagos no ARRANQUE com a janela fora do ecra -- o dono nao espera por ele. O
#: porque completo, com a medicao, esta' em `_warm_paint`.
PAINT_WARM_SETTLE_S = 0.6
#: `SM_XVIRTUALSCREEN`/`SM_YVIRTUALSCREEN` (winuser.h): a janela do aquecimento
#: tem de ficar fora da UNIAO dos monitores, nao so' fora do principal.
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
#: 6 ms entre leituras: o grao do rAF e' uma frame (~16 ms), portanto um poll
#: mais apertado so' gasta idas ao UI thread.
PAINT_ACK_POLL_S = 0.006
#: TODO `exec_js` aqui e' limitado por ISTO, nao pelos 10 s por omissao: o
#: chamador e' a thread da hotkey, e um UI thread preso tem de custar centenas de
#: ms no pior caso -- a mesma licao de `TRANSPARENCY_HACK_WAIT_S`.
PAINT_ACK_JS_TIMEOUT_S = 0.25

#: O global da pagina. Instalado por nos (o shell nao edita `app/panel/**`: ha'
#: outro lane dono desses ficheiros) e idempotente, para um segundo show nao
#: reinstalar nada.
PAINT_ACK_ARM_JS = (
    '(function (seq) {'
    '  if (typeof window.__sotto_paint !== "function") {'
    '    window.__sotto_paint_ack = 0;'
    '    window.__sotto_paint = function (s) {'
    '      var fire = function () { window.__sotto_paint_ack = s; };'
    '      if (typeof requestAnimationFrame === "function") {'
    '        requestAnimationFrame(function () { requestAnimationFrame(fire); });'
    '      } else { setTimeout(fire, 0); }'
    '    };'
    '  }'
    '  window.__sotto_paint(seq);'
    '  return String(document.visibilityState || "?");'
    '})(__SEQ__)')
PAINT_ACK_READ_JS = 'String(window.__sotto_paint_ack === __SEQ__ ? 1 : 0)'
#: THE EXIT'S DESTROY WAIT (2026-10-21). The window destroy is COSMETIC: the
#: shell calls `os._exit` right after, so the window dies either way. Waiting
#: three seconds for it is three seconds the tray thread is not answering the
#: owner -- the same *"fechar o sotto trava"*. A quarter of a second is enough
#: to let the destroy start.
QUIT_DESTROY_WAIT_S = 0.25
#: QUANTO DEPOIS DO ARRANQUE O WORKER E' PRE-CARREGADO. ZERO desde 2026-10-30:
#: o dono, verbatim, *"a porra da legenda ao vivo levou uns 20 segundos pra
#: comecar a mostrar. nao era pra essa merda estar carregada desde sempre e
#: mostrar IMEDIATAMENTE?"*. Medido no log vivo: `WORKER_PRELOAD start
#: waited_s=20.0` (e 26 e 76 noutras largadas, por causa da espera pelo dono
#: quieto). O preload correa em segundo plano, a prioridade BELOW_NORMAL do
#: worker; o custo de o fazer cedo e' o arranque, e o custo de o adiar e' a
#: legenda nao existir quando ele pede.
WORKER_PRELOAD_DELAY_S = 0.0
#: A ESPERA PELO DONO QUIETO SO' VALE COM ATRASO EXPLICITO. Foi a cura de
#: 2026-10-23 (*"abrir ou fechar ele faz meu pc travar PRA CARALHO"*), e em
#: 2026-10-30 passou a ser o problema: com `delay_s=0` o preload arranca JA', e
#: estes dois numeros so' se aplicam quando alguem passa um atraso.
WORKER_PRELOAD_IDLE_S = 6.0
WORKER_PRELOAD_MAX_WAIT_S = 120.0
WORKER_PRELOAD_POLL_S = 2.0
PANEL_STATE_JS_TIMEOUT_S = 1.0   # the DIAGNOSTIC's budget: a dump is not the product
STATS_REPLY_MAX_PENDING = 64     # the bound on the replies waiting for the UI thread
#: O TETO DE UMA NOTIFICACAO (2026-11-01). Ver `emit`: as tres chamadas de
#: `emit` do produto sao NOTIFICACOES (ninguem le o valor), e todas corriam pelo
#: `exec_js` SINCRONO com o orcamento por omissao de 10 s. Um post nao tem
#: orcamento nenhum: ou entra na fila do UI thread ou nao entra, e as duas coisas
#: ficam escritas no log.
BRIDGE_NOTIFY_POSTED = True


def _bridge_census():
    return _bridge_census_mod.census(log, warn, REPO_ROOT)


def _task_bits(box, done):
    return _bridge_census_mod.task_bits(box, done)


class NoAnswer(dict):
    """`exec_js`/`_ui` did NOT get an answer -- and it says WHY.

    A `dict`, so `json.dumps` of it WORKS (the probes log the value as JSON
    and a plain object would raise), and FALSY, so every `if value:` check in
    the shell behaves exactly as it did when the answer was a bare `None`.

    It is NOT `None`, and that is the whole point. Measured 2026-10-20: 93
    `UI_THREAD_STALL` warnings inside a 50 s window, and every reader
    downstream saw a bare `None` -- the probe logged `PANEL_STATS_PROBE null`
    with no reason, so "the panel answered null" and "the panel never
    answered" were the SAME observation. This says which one it was.

    Keys: `reason`, `requested`, `timeout`, `detail`.
    """

    __slots__ = ()

    def __init__(self, reason, requested=None, timeout=None, detail=None):
        super().__init__(reason=reason, requested=requested,
                         timeout=timeout, detail=detail)

    def __bool__(self):
        return False

    def __repr__(self):
        return '<no-answer reason=%s requested=%r timeout=%s>' % (
            self.get('reason'), self.get('requested'), self.get('timeout'))

# --- THE PANEL'S VISIBILITY, as a file the WORKER can poll -------------------
# THE STACK LAW (owner, 2026-10-07, verbatim): *"o nvidia é pro ao vivo, o
# parakeet redux é pro geral. o ao vivo só acontece quando o painel ta aberto.
# quando ta fechado, o redux entra, e vira um transcritor LEVE ao contrario do
# nvidia."* The streaming engine must work only while the panel is OPEN; when it
# is CLOSED the batch engine takes over. The worker is a SEPARATE PROCESS, so
# "is the panel open" has to cross a process boundary. This file is that
# crossing, and it is the ONLY thing added here.
#
# WHY A FILE, AND NOT A MESSAGE. The worker speaks one channel: JSONL on ITS
# stdout. There is no worker->shell input pipe, and adding one would make
# "visibility" a second protocol with its own framing, its own ack and its own
# silent failure mode. A file the worker only READS cannot be corrupted by the
# worker, and a reader that misses a tick reads the CURRENT truth instead of a
# queued event that was already stale when it was queued.
#
# WHY `visible` IS MEASURED AND NOT INTENDED. It is `window_visible(hwnd)` —
# the same `IsWindowVisible` the hotkey path decides from and the cheap
# `--selftest` two-state check asserts — never "we called hide". A stale
# intention is exactly the defect class this repo has been bitten by twice
# (`PANEL_VISIBILITY_CACHE_STALE`, and the panel that was on screen while
# `PANEL_VISIBILITY_AT_STARTUP` said `visible=false`).
#
# THE AGE IS NOT SELF-REPORTED, for the reason `panel_state.py` spells out: a
# producer that dies cannot update a number inside the file it stopped writing.
# `writtenAtEpoch` + `staleAfterSeconds` let a reader REFUSE a dead shell's
# answer, and the worker's fail-safe is to treat missing/stale as
# `visible=true` (i.e. KEEP STREAMING) — because the alternative, obeying a
# stale `visible:false`, is the one failure the HARD RULE in AGENTS.md forbids:
# zero transcription while the owner is not looking.
PANEL_VISIBILITY_PATH = os.path.join(
    REPO_ROOT, '_main', 'panel-visibility.json')
PANEL_VISIBILITY_INTERVAL_S = 3.0
#: Bumped when a field is renamed or removed, so a reader refuses a shape it
#: does not know instead of reading a wrong number.
PANEL_VISIBILITY_SCHEMA = 'sotto.panel-visibility/1'

# --- the transcript history (the "redux"), on disk --------------------------
# The panel's TOP section is the accumulated transcript; the BOTTOM box is the
# live stream. History is written to `<root>/<YYYY-MM-DD>/<HH>.md` — a 24 h
# folder with one file per hour, appended as captions commit — so the owner can
# find his own data in the file manager and a search can walk it cheaply.
# The default root is the repo's own `history/` (H:/sotto/history): the owner
# asked for the data to live under H:/sotto. SOTTO_HISTORY_ROOT overrides it.
HISTORY_ROOT = os.path.normpath(
    os.environ.get('SOTTO_HISTORY_ROOT')
    or os.path.join(HERE, os.pardir, os.pardir, 'history'))
#: One history line: `- [HH:MM:SS] text`. Markdown-readable AND parseable.
HISTORY_LINE_RE = re.compile(r'^-\s+\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$')
HISTORY_DAY_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
#: The provenance the WRITER stamps on the end of a line (M8). It is an HTML
#: comment, so a Markdown reader shows the sentence and nothing else, and every
#: reader of the FILE strips it before treating the rest as text.
HISTORY_TAIL_RE = re.compile(r'\s*<!--.*?-->\s*$')
#: The vocabulary `_history_provenance` is allowed to write. A route outside it
#: is not written at all: a marker nobody can interpret is worse than none.
HISTORY_ROUTES = ('final', 'provisional-draft', 'batch')
#: `batch` is the CANONICAL (parakeet) pass's own name (2026-11-01). The batch
#: engine emits no `final` flag (`worker/redux_batch.py:185`), so its lines had no
#: route the store would print, and the panel's choke point refused them one
#: statement before the producer guard. The word is `batch` and not `final` on
#: purpose: `route=final` means the LIVE worker's second pass closed the line, and
#: a batch line wearing it would forge the very field an audit reads to tell the
#: two sources apart. See `app/panel/history-source.js:transcriptRoute`.
#: The route SOURCES `_history_provenance` is allowed to write as `src=` — WHICH
#: branch decided the route. `'fallback'` is the one the de-landing produced
#: SILENTLY: a line that reached the transcript ONLY because the renderer's
#: `routeFor` else-half manufactured `final` when the worker stamped no route at
#: all (P1 `4fb5b25380cbc8269977e22e`). Outside this list nothing is written.
#: The Node twin is `ROUTE_SOURCES` in `app/panel/history-store.js` -- and that
#: twin is NOT on the shipped page: `panel.html` loads eleven scripts and none of
#: them is `history-store.js` (measured 2026-10-11), so THIS tuple is the one the
#: owner's transcript actually passes through and the Node one is read only by
#: oracles. BOTH were missing `'worker-stamped-producer'` until 2026-10-11 -- the
#: token `caption-formulation.js routeSourceFor` returns for a line that DECLARES
#: a producer while no worker `final` vote decided the route -- so such a line was
#: written with NO `src=` marker at all: provenance thinner than the decision that
#: produced it. The list must equal the declared set, in both twins.
HISTORY_ROUTE_SOURCES = ('worker-stamped', 'worker-stamped-producer', 'panel-deadline', 'fallback')

# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH. The owner asked, 2026-10-18: make the history search FIND things --
# *"quando eu procurar uma coisa no historico, eu quero que ele ache"*.
#
# WHAT IT WAS, and why that is not search but string equality:
#     needle = str(query or '').strip().lower()
#     if needle in entry['text'].lower():
# One `in`, byte for byte, no accents, no typos, no sounds. Measured on this box's
# own store (211 341 B over 11 files, 2 days): typing `maca` cannot find `maçã`,
# `cabeleireiro` cannot find `cabeleireira`, and `fales` cannot find `falés`. The
# owner does not type the way a machine compares.
#
# THREE LAYERS, IN THIS ORDER, AND THE ORDER IS THE PRODUCT:
#   0  LITERAL   the query, accents folded, is a substring. Ranked first, always,
#                and it is the ONLY layer that can return the whole query as a
#                phrase. A fix that demoted this would be a regression wearing a
#                feature's clothes.
#   1  PHONETIC  every query word has a SOUNDEX twin somewhere in the entry. This
#                is the layer that finds the word the owner MEANT.
#   2  FUZZY     every query word is within a bounded edit distance of some word in
#                the entry -- typos, one letter dropped, one doubled.
#
# EVERY LAYER AFTER 0 IS ALL-WORDS, NOT ANY-WORD. That is the difference between a
# search and a slot machine: with any-word semantics, the query `o preco do acucar`
# would return every entry containing `o`, which on a two-day store is nearly all of
# them. All-words makes the later layers able to SAY NO, and a layer that cannot say
# no is not a ranking, it is noise with a rank attached.
#
# EDIT DISTANCE IS PER WORD, NEVER OVER THE WHOLE SENTENCE. Over the sentence the
# threshold would have to grow with the sentence, so a 90-character line would
# tolerate ~30 edits and match everything; over a word the threshold stays at
# 0.34 x len and a 5-letter word tolerates 2.
#
# The pt-BR fold is not a nicety, it is the bug: the store is Portuguese and the
# keyboard often is not, so `maçã` has to be reachable from `maca`.
# ═══════════════════════════════════════════════════════════════════════════════

#: The share of a word's length that may be wrong and still count as the same word.
#: 0.34 is the ratio used throughout this repo's fuzz gates. A 3-letter word gets
#: ceil(1.02) = 2 -- which is too generous, so words shorter than 4 are excluded
#: from layer 2 entirely rather than half-matched (see `_FUZZY_MIN_WORD`).
SEARCH_FUZZ_RATIO = 0.34
#: Below this length an edit budget of 1 makes almost every short word match every
#: other short word, so short words are LITERAL-ONLY.
FUZZY_MIN_WORD = 4
#: Hard ceiling, whatever the ratio asks for: no word is ever allowed more than
#: this many edits. `ceil(0.34 * 9) = 4` on a long word is already four typos.
SEARCH_MAX_EDITS = 2


def search_fold(text):
    """Lowercase and strip diacritics: `Maçã`/`MACA`/`maçá` all fold to `maca`.

    NFD splits the base letter from its combining mark, and combining marks are
    dropped. `ç` and `ã` and `õ` all become their base letter, which is what a
    pt-BR search wants: the owner does not type tildes.
    """
    decomposed = unicodedata.normalize('NFD', str(text or ''))
    stripped = ''.join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower()


#: Soundex, folded to ASCII by `search_fold` first. Standard grouping:
#: bfpv->1  cgjkqsxz->2  dt->3  l->4  mn->5  r->6, vowels and h/w do not code.
SEARCH_SOUNDEX = {
    **{c: '1' for c in 'bfpv'},
    **{c: '2' for c in 'cgjkqsxz'},
    **{c: '3' for c in 'dt'},
    'l': '4',
    **{c: '5' for c in 'mn'},
    'r': '6',
}


def search_soundex(word):
    """A 4-character sound key for `word`, or `''` if it has no letters.

    Collisions are expected and fine: this is layer 1 of 3, it only ADDS candidates
    after the literal layer has already failed, and every candidate it adds must
    still satisfy all-words. A pt-BR owner searching `casa`/`casso`/`caza` landing
    in the same bucket is the feature, not a bug -- what would be a bug is the
    bucket being allowed to ANSWER, which only layer 0 does.
    """
    letters = ''.join(ch for ch in search_fold(word) if ch.isalpha() and ch.isascii())
    if not letters:
        return ''
    first = letters[0]
    codes = []
    previous = SEARCH_SOUNDEX.get(first, '')
    for ch in letters[1:]:
        code = SEARCH_SOUNDEX.get(ch, '')
        if code and code != previous:
            codes.append(code)
        if ch not in 'hw':          # h and w are transparent, they do not reset
            previous = code
    return (first.upper() + ''.join(codes) + '000')[:4]


def search_edits(word):
    """The edit budget for `word`: `ceil(ratio * len)`, capped twice.

    Capped at `FUZZY_MIN_WORD - 1` for short words and at `SEARCH_MAX_EDITS`
    always. Returns 0 for anything shorter than `FUZZY_MIN_WORD`, which sends it
    to the literal layer and out of the fuzzy one.
    """
    n = len(word)
    if n < FUZZY_MIN_WORD:
        return 0
    return min(SEARCH_MAX_EDITS, int(math.ceil(SEARCH_FUZZ_RATIO * n)))


def bounded_levenshtein(a, b, cap):
    """Edit distance between `a` and `b`, or None if it exceeds `cap`.

    Two-row DP with a row minimum early exit: the moment a whole row costs more than
    `cap` no later row can come back under it, so the scan stops. Without that, a
    mistyped 40-character query against a short entry costs the full table.
    """
    if a == b:
        return 0
    if abs(len(a) - len(b)) > cap:
        return None
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        # The early exit must read the row's MINIMUM, not its label. Seeding
        # `row_min = i` and never updating it made the scan give up on the third
        # row for any word of 7+ letters, so `mercado`/`merdado` -- one substitution,
        # distance 1 -- came back as None and the fuzzy layer was dead on exactly
        # the long words it exists for. The rule still holds: the minimum of a row
        # is a lower bound on the distance of every later row.
        if min(current) > cap:
            return None
        previous = current
    return previous[-1] if previous[-1] <= cap else None


def search_match_rank(text, folded_query, query_words):
    """Which layer, if any, `text` matches. 0/1/2, or -1 for no match.

    Layer 0 short-circuits on the folded substring. Layers 1 and 2 both require
    EVERY query word to be accounted for by SOME word of the entry, which is what
    makes them able to reject.

    Note the shape of the phonetic test: `all(search_soundex(w) == key for w in
    query_words)` would demand that every query word sound like every OTHER one --
    correct only for a single-word query, and silently wrong for anything longer.
    The test that is actually meant is `each query word's key is present among the
    entry's keys`.
    """
    folded_text = search_fold(text)
    if not folded_query:
        return -1                    # an empty query matches nothing, not everything
    if folded_query in folded_text:
        return 0
    words = folded_text.split()
    if not words:
        return -1
    query_keys = [search_soundex(w) for w in query_words]
    entry_keys = {search_soundex(x) for x in words}
    # Layer 1 — every query word's SOUND is somewhere in the entry.
    if query_keys and all(k and k in entry_keys for k in query_keys):
        return 1
    # Layer 2 — every query word is a bounded typo of some entry word.
    for qw in query_words:
        budget = search_edits(qw)
        if budget <= 0:
            if qw not in words:
                return -1
            continue
        if not any(bounded_levenshtein(qw, w, budget) is not None for w in words):
            return -1
    return 2

#: `explorer` for "show in folder" must never open a console window.
CREATE_NO_WINDOW = 0x08000000

#: Capture shape. PortAudio's BLOCKING read API does not work on this host, so
#: the worker is told to use the callback shape — same default as
#: worker-bridge.js DEFAULT_CAPTURE_MODE.
DEFAULT_CAPTURE_MODE = 'callback'

# --- worker-bridge.js invariants, kept because they protect the panel -------
FALSE_AUDIO_ABSENT_RE = re.compile(
    r'\bwait(?:ing)?\s+for\s+audio\b|\bno\s+audio\b', re.IGNORECASE)
CAPTURE_NOT_STARTED = (
    'Capture not started - the worker has not opened the audio device'
)
FAILURE_WORDS_RE = re.compile(
    r'error|fail|fatal|dead|stopped|crash|denied|missing', re.IGNORECASE)

# --- the worker's OWN vocabulary, and how the panel must paint it -----------
# The reference arm decides this in `app/_legacy-electron/worker-bridge.js`'s STATE_MAP:
# there `device_exhausted` is `kind: 'error'` and `device_rotated` is not. This
# shell never ported that table (it says so in `_readable`) and classified every
# state with FAILURE_WORDS_RE alone — an English prose list that contains none
# of this worker's failure states (`error`, `device-exhausted`, `silent-device`)
# and cannot see the verdict carried inside `done`. Measured consequence: a
# worker that died of a silent device was painted with the same NEUTRAL styling
# as warm-up, so the panel showed a healthy-looking app while nothing could ever
# transcribe. The DECISION is what gets ported here, not the prose.
WORKER_ERROR_STATES = frozenset({
    'error',             # any stage: model-load, device, open-stream, chunk
    'device-exhausted',  # every candidate tap was flat
    'silent-device',     # a tap ran a full window below the peak floor (exit 3)
})
#: `done` is neutral only while the run's OWN verdict says captions came out.
HEALTHY_DONE_VERDICTS = frozenset({'captions-emitted'})
#: States that report a worker still WARMING UP. They must not paint over a
#: death the panel is already showing: the shell restarts a dead worker
#: automatically, so the first thing after every exit 3 is `model-loading`, and
#: a panel that takes that at face value reports a healthy app in a death loop.
WORKER_WARMUP_STATES = frozenset({
    'boot', 'model-loading', 'model-loaded', 'device', 'capture-started',
    'device-rotated', 'selftest-start',
})
#: The ONE state that means an audio stream is OPEN (sotto_worker.py:2139 emits
#: `capture-started` on every tap attempt, whether or not it later proves flat).
#: From that line on the worker is mid-stream, and a hot reload must not restart
#: it under the owner's feet.
WORKER_CAPTURING_STATES = frozenset({'capture-started'})

# --- the worker's OWN verdict about the audio, and what the silence timer owes it
# A missing caption is NOT evidence of a fault. An IDLE DESKTOP produces digital
# silence BY DESIGN: measured by this repo's own idle-floor probe, the loopback of
# the default render endpoint carries peak=0.000000 over three independent 6 s
# captures (`_main/sdr_idlefloor.out`). So a worker whose taps are all flat is
# telling the truth about a quiet machine, and the ONLY thing the shell may do
# with that truth is show it.
#
# MEASURED DEFECT this replaces (lane SottoTapRestartLoop, live run
# `_main/_live_owner3.log`): the 15 s no-output watchdog killed and respawned the
# worker 8 times in ONE run (`BRIDGE_SILENT` x8, `spawns=10`), each respawn
# reloading a ~2.4 GB model (the worker's own `rss_mb=2413-2418`), because a
# caption is the only thing that lifted the timer and a quiet desktop can never
# produce one. The loop could not converge: there was never a caption to lift it,
# and never would be while nothing was rendering.
#
# The criterion is the WORKER'S OWN VERDICT, never the absence of a caption.
# These two sets are that verdict as the worker writes it: as a `status.state`
# (the device ladder's own conclusion) and as the `verdict` carried inside `done`.
WORKER_NO_AUDIO_STATES = frozenset({
    'silent-device',         # a tap ran a full window below the peak floor (exit 3)
    'device-exhausted',      # every candidate tap was flat
    'no-speech-in-capture',  # the tap carried signal and none of it was speech
    'music-only-capture',    # the endpoint is carrying non-speech
})
#: The same conclusion, carried by the run's `done` line. `captions-emitted` is
#: deliberately absent: it is the one verdict that says speech DID come out.
#: (`silent-capture` lives HERE and not above: verified against
#: worker/sotto_worker.py, it is a `verdict=`, never a `state=`.)
WORKER_NO_AUDIO_VERDICTS = frozenset({
    'silent-device', 'all-candidate-taps-flat', 'silent-capture',
    'no-callback-blocks', 'resample-produced-nothing',
    'buffer-never-reached-chunk-size', 'captions-all-music-gated',
    'captured-signal-has-no-speech',
})
#: The UI state the shell paints when the silence is the worker's own no-audio
#: verdict. Named, so the panel says WHAT is true instead of "Worker silent".
NO_AUDIO_STATE = 'no-audio'

# --- the worker's OWN counters line, read for the text dump -----------------
# `worker/sotto_worker.py` writes `WORKER_STATS tag=tick|final ...` on STDERR
# (`stats_line()`, every `--stats-interval` seconds, default 10). The bridge
# already reads that stream for its stderr tail — those lines were being DROPPED
# after three, so `peak` and `nonzero_blocks` were unreachable from outside the
# process. This parses the same line the bridge already sees; it starts no
# process and reads no other file.
WORKER_STATS_RE = re.compile(r'^WORKER_STATS\s+tag=(\S+)\s*(.*)$')

#: The worker's heartbeat cadence: `--stats-interval` default in
#: `worker/sotto_worker.py` (10 s), published as `WORKER_STATS tag=tick` on
#: stderr. It is the only periodic signal the worker emits, which is why the
#: no-progress watchdog counts it (see `WorkerBridge._note_progress`).
WORKER_STATS_INTERVAL_S = 10.0
#: The no-progress window. MEASURED, not guessed. The old 15000 ms was armed on
#: STDOUT alone, i.e. on CAPTIONS, and a real conversation's commit-to-commit
#: gap is routinely longer than that: the owner's own log
#: (`_main/webview-run.log`, 2026-10-06) commits lines 62 s, 62 s and 56 s
#: apart while the worker is transcribing normally — so the watchdog was
#: killing a healthy worker and paying a ~2.4 GB model reload each time.
#: It is now armed on ANY progress (a stdout line, or an ADVANCING worker
#: heartbeat), so the window only has to exceed the heartbeat: 3 x 10 s leaves
#: room for a stalled main loop (the worker runs inference on the same thread
#: that ticks) while still catching a worker that truly stops in 30 s.
#: `_main/restart-30s-oracle.py` asserts the relation mechanically against
#: `worker/sotto_worker.py`, because the two numbers live in two files.
WORKER_SILENCE_MS = 30000
#: O CARREGAMENTO TEM JANELA PROPRIA (S7). O `WORKER_SILENCE_MS` arma no spawn e,
#: num arranque a frio, expirava a meio do load: `BRIDGE_SILENT ms=30000` entre
#: `model-loading` e `model-loaded`, worker saudavel morto, load pago outra vez
#: (log dele de 2026-10-12). Antes do `model-loaded` a janela e'
#: `BRIDGE_SILENT_LOADING` -- silencio e' a DEFINICAO de carregar -- e o tecto de
#: 180 s e' o limite do dono (*"faz o model sair de load apos 3 minutos"*,
#: docs/audit/load-churn.md): ~40x um load quente e ~6x o pior load frio medido.
WORKER_LOAD_SILENCE_MS = 180000


#: As linhas de stderr que provam que o worker esta VIVO a trabalhar. `WORKER_STATS` so'
#: conta quando `blocks` AVANCA (`_note_progress`); num lote longo ele congela -- e o
#: worker era morto por isso.
PROGRESS_TAGS = ('REDUX_BATCH_KICK', 'REDUX_ENGINE_DONE', 'REDUX_MODE')
#: Quantas linhas de stderr a morte PUBLICA. Eram TRES, e tres escondem a causa:
#: medido 2026-11-02, o worker morreu duas vezes `rc=1` (19:22:29, 19:36:40) e a
#: cauda era `WORKER_STATS` + `REDUX_BATCH_KICK` -- o traceback ficou de fora.
STDERR_TAIL_MAX = 40
#: Tecto DURO da janela de carga (2026-11-03). A janela conta silencio, mas um
#: worker que fala SEM NUNCA carregar tambem nao pode viver para sempre: sob
#: contencao o load medido foi de 10 s a 147 s, entao 15 min e' a fronteira
#: entre "carrega devagar" e "esta' preso".
WORKER_LOAD_HARD_CEILING_MS = 900_000.0


def parse_worker_stats(line):
    """`{'tag': 'tick'|'final', 'fields': {...}, 'line': ...}` or None.

    Values stay STRINGS exactly as the worker printed them: a reader that wants
    `peak` as a float can convert it, and a value the worker never printed stays
    absent instead of becoming a zero this file invented.
    """
    match = WORKER_STATS_RE.match(str(line).strip())
    if not match:
        return None
    fields = {}
    for token in match.group(2).split():
        if '=' in token:
            key, value = token.split('=', 1)
            fields[key] = value
    return {'tag': match.group(1), 'fields': fields,
            'line': str(line).strip()}

# ── hot reload of the WORKER: debounce + guard + floor ──────────────────────
#: Trailing debounce on worker reload requests. `hot_reload.DEBOUNCE_MS` is 250
#: ms of quiet — the WATCHER's window — and it is BELOW the cadence of a
#: cross-lane editing burst: five lanes each saving every 1-3 s reach 250 ms of
#: quiet between consecutive saves, so every save flushed and every flush
#: restarted the worker (the churn this fixes). 2 s of quiet coalesces one
#: lane's save-storm while staying responsive.
WORKER_RELOAD_DEBOUNCE_MS = 2000
#: The owner's rule, verbatim: the model must not leave load "super rapido -
#: faz o model sair de load apos 3 minutos". There is NO idle-unload here to
#: configure (see docs/audit/load-churn.md): the churn was reloads, and a TTL
#: would ADD them. What 180 s bounds instead is the RELOAD RATE. Measured cost
#: of ONE load on this box: 2.0-8.3 s of stall and 1.4-2.1 GB RSS
#: (`worker/runs/*.jsonl`, the `model-loaded` line), so 180 s is ~20x the stall
#: it bounds and the model cannot cycle faster than the owner asked.
WORKER_RELOAD_MIN_INTERVAL_MS = 180000
# The capture guard has no exit of its own: is_capturing() goes false only when
# the worker STOPS, and a worker with audio to transcribe keeps capturing. So a
# held reload needs a CEILING -- after this long it applies even with no
# boundary -- plus a cadence for re-checking the wait it is holding.
WORKER_RELOAD_MAX_DEFER_MS = 25000
WORKER_RELOAD_DEFER_RECHECK_MS = 10000
# A held reload is a STATE, not an event: log it at most this often.
WORKER_RELOAD_DEFER_LOG_MS = 30000
#: Fixed field order, so two runs' bodies diff by VALUE and not by shape.
STATUS_BODY_FIELDS = ('stage', 'detail', 'verdict', 'device', 'api', 'peak',
                      'peak_floor', 'blocks', 'window_s', 'captions', 'tokens',
                      'chunks', 'rotations', 'reason', 'rate')
STATUS_BODY_MAX = 400

def _reap_child(child):
    """Wait for a killed worker OFF the caller's thread, then discard it.

    Used by `WorkerBridge.stop`. The wait is what reaps the OS process handle;
    doing it on the shell's UI or tray thread is what made quitting take up to
    five seconds against a 2 GB child.
    """
    try:
        child.wait(timeout=5)
    except Exception:  # noqa: BLE001
        pass


#: O TOKEN DE ESTADO PAGA UM `stat`, NAO UMA LEITURA. Medido 2026-11-01 pela
#: lane de perfil: `code_state_log` corre no tick de 2 s e chamava
#: `file_sha256(SHELL_PATH)` mais o do worker -- 414 911 B relidos a cada tick,
#: 1,30 ms por tick, 43 200 vezes por dia, e foi essa a frame que o watchdog
#: apanhou. A chave e' `(caminho, mtime_ns, tamanho)`: qualquer escrita muda o
#: `mtime` do NTFS (resolucao de 100 ns) ou o tamanho. Um ficheiro reescrito no
#: MESMO tick de `mtime` com o MESMO tamanho devolveria o digest antigo -- para
#: um token de staleness isso e' um alvo que se move em ~100 ns, e um digest de
#: seguranca nunca passa por aqui.
_SHA_CACHE = {}


def file_sha256(path):
    """First 16 hex chars of a file's SHA-256, or None if it cannot be read.

    A SHORT digest on purpose: it is a staleness token compared against another
    token from this same function, never a security claim, and it is the width
    the reference implementation used so log lines stay comparable.
    """
    try:
        stat = os.stat(path)
        key = (path, stat.st_mtime_ns, stat.st_size)
        hit = _SHA_CACHE.get(key)
        if hit is not None:
            return hit
        digest = hashlib.sha256()
        with open(path, 'rb') as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b''):
                digest.update(chunk)
        out = digest.hexdigest()[:16]
        if len(_SHA_CACHE) > 64:  # o conjunto de ficheiros vigiados e' pequeno
            _SHA_CACHE.clear()
        _SHA_CACHE[key] = out
        return out
    except OSError:
        return None


# The shell's own bytes, hashed ONCE at import: the answer to "is the code I am
# running the code on disk" cannot be re-read later without the answer changing
# under the reader. reloadable is False because a shell cannot re-read itself in
# place -- the panel can, the worker can, the shell needs a restart.
SHELL_PATH = os.path.abspath(__file__)
SHELL_SHA256_AT_IMPORT = file_sha256(SHELL_PATH)


def worker_status_kind(state, message):
    """'error' | 'no-audio' | 'busy' for ONE worker status line.

    By the reference arm's rule, plus the calm state (owner, 2026-10-14): a
    no-audio verdict is its OWN kind and the test for it comes FIRST, because
    WORKER_NO_AUDIO_STATES overlaps WORKER_ERROR_STATES and the error test would
    otherwise swallow it back into red.

    Either test alone gets a real case wrong — the state is what this worker
    names itself, and the verdict is the only thing that can tell a `done` that
    produced speech from a `done` that produced nothing.
    """
    state = str(state or '')
    # ── THE NO-AUDIO VERDICT IS NOT A FAULT (owner, 2026-10-14) ─────────────
    # CHECKED FIRST, and that order is load-bearing: the no-audio states are a
    # SUBSET of WORKER_ERROR_STATES (the worker's own terminal vocabulary), so
    # testing the error set first would swallow them back into red -- measured
    # in this lane's own oracle run, where the calm branch sat behind it and
    # `silent-device` still painted 'error'.
    # The routing law of this file says it in as many words: "a live run that
    # reads silence is usually CORRECT BEHAVIOUR, not a regression" -- with
    # nothing routed into a virtual cable EVERY loopback reads digital silence
    # (measured: peak=0.000000 over three 6 s captures, the idle-floor probe's
    # own output file). The worker's own verdict for that case is
    # `silent-device` / `device-exhausted` / a `done` carrying one of
    # WORKER_NO_AUDIO_VERDICTS, and painting it the same RED as a model-load
    # failure or a device that would not OPEN is what put "Silent audio
    # device" in front of the owner on every cold start with a quiet desktop
    # and had him reading it as "coisa nao carregada" -- he complained,
    # verbatim (2026-10-14): "sotto ta reclamando de coisa nao carregada, com
    # erro vermelho". Nothing is hidden by this: the worker's OWN sentence
    # (device, api, peak, floor) still travels, the state still HOLDS across
    # the automatic restart, and a caption still clears it. What changes is
    # only the colour of a fact that is not a fault. The 2026-10-06 decision
    # that painted these RED was right about the swallow it fixed (a death
    # must never look like warm-up) and wrong about the colour it chose for
    # the no-audio half: on this host the no-audio verdict is the NORMAL
    # answer of a working app to a quiet machine.
    if state in WORKER_NO_AUDIO_STATES:
        return 'no-audio'
    if state in WORKER_ERROR_STATES:
        return 'error'
    if state == 'done':
        # POSITIVE form, and the `verdict and` guard that used to stand here was
        # the swallow one level down: with it, a `done` carrying NO verdict (or
        # an empty one) failed the test, fell through to FAILURE_WORDS_RE, which
        # does not contain the word `done`, and the panel painted a bare "done"
        # as a healthy finish -- a worker that never said it transcribed, shown
        # as the one state that means it did. The contract is positive: only a
        # verdict that SAYS captions came out is benign; an UNKNOWN word and an
        # ABSENT word are both "this worker did not tell us it worked".
        verdict = str((message or {}).get('verdict') or '').strip()
        # The SAME split, carried by the run's `done` line: a no-audio verdict
        # is the worker reporting a quiet endpoint, not a broken worker. An
        # ABSENT or UNKNOWN verdict is still an error -- "this worker did not
        # tell us it worked" is a failure, and that half of the contract is
        # untouched.
        if verdict in WORKER_NO_AUDIO_VERDICTS:
            return 'no-audio'
        if verdict not in HEALTHY_DONE_VERDICTS:
            return 'error'
    return 'error' if FAILURE_WORDS_RE.search(state) else 'busy'


#: OS CODIGOS DE AUDIO DO WINDOWS QUE O DONO JA VIU NA TELA, TRADUZIDOS.
#:
#: Ele, verbatim 2026-10-15: *"que nojeira e essa mano? ate quando tu vai fazer essas coisas?"*,
#: sobre a linha que o painel pintava:
#:
#:     Worker error at open-stream - WasapiError: Initialize(SHARED|LOOPBACK) failed:
#:     <no description> (0x8889000A)
#:
#: **Um codigo hexadecimal na tela do dono nao e um diagnostico, e um segredo.** Ele ja tinha
#: mandado arrumar isto em 2026-10-14: *"sotto ta reclamando de coisa nao carregada, com erro
#: vermelho. arruma"*. A causa por tras do `0x8889000A` e conhecida e tem UMA acao que resolve:
#: o dispositivo esta ocupado. Dizer isso, e dizer o que fazer, e o minimo.
#:
#: O detalhe CRU continua a ir para o LOG -- `BRIDGE_STATUS_ERROR` guarda-o inteiro -- portanto
#: nada se perde para quem estiver a diagnosticar. O que muda e o que o dono LE.
HRESULT_AUDIO_READINGS = {
    '0x88890001': 'The audio device was not initialised. Press Alt+C to try again.',
    '0x88890004': ('The audio device disappeared (unplugged or disabled). '
                   'Choose another device and press Alt+C.'),
    '0x88890008': ('That audio device does not support the format Sotto needs. '
                   'Choose another device and press Alt+C.'),
    '0x8889000A': ('The audio device is already in use by another program, so Sotto '
                   'could not open it. Close whatever is holding it -- or choose '
                   'another device -- and press Alt+C.'),
    '0x8889000B': 'That audio buffer size is not supported by this device.',
    '0x88890010': ('No audio device is available at all. Check that an output is '
                   'enabled in Windows sound settings, then press Alt+C.'),
}


def human_audio_error(detail):
    """A frase humana para um erro de audio do Windows, ou None se nao o conhecermos.

    Procura o codigo em hexadecimal no detalhe CRU e devolve a leitura da tabela. Devolver
    None e deliberado: um erro que nao esta na tabela continua a ser mostrado como veio,
    porque inventar uma explicacao para um codigo desconhecido e pior do que o codigo.
    """
    if not detail:
        return None
    texto = str(detail).upper()
    for codigo, leitura in HRESULT_AUDIO_READINGS.items():
        if codigo.upper() in texto:
            return leitura
    return None


def worker_status_text(state, message, readable):
    """The footer line for ONE worker status: the worker's OWN cause, not a token.

    A bare `silent-device` in the footer is the swallow this exists to remove.
    The prose is kept clear of FALSE_AUDIO_ABSENT_RE on purpose: `_status`
    rewrites any "no audio" claim to CAPTURE_NOT_STARTED and forces the kind to
    busy, which would take a device failure and paint it as warm-up.
    """
    message = message or {}
    if state == 'done':
        # BOTH non-healthy kinds carry the verdict WORD: an error because that is
        # the worker's own cause, and a no-audio verdict for exactly the same
        # reason -- the calm state must still say what the worker concluded
        # ("Worker finished on silent-device"), not a bare 'done'. Only the
        # HEALTHY finish (or a `busy` kind) gets the neutral readable line.
        if worker_status_kind(state, message) in ('error', 'no-audio'):
            verdict = str(message.get('verdict') or '').strip()
            if not verdict:
                # An absent verdict must not be rendered as the f-string of a
                # missing key ("Worker finished on None"), and it must not read
                # as a neutral end: the panel is saying the worker stopped
                # without saying it transcribed.
                return ('Worker finished on an UNKNOWN verdict - the worker '
                        'never said it transcribed')
            return f'Worker finished on {verdict}'
        return readable
    if state not in WORKER_ERROR_STATES:
        # A ESCADA GASTA E UMA ESPERA, NAO UMA FALHA (dono, 2026-10-17, verbatim:
        # *"o painel ta com erro vermelho. ta falando que 'audio device is in use'
        # sendo q nao e pra acontecer nunca e nem depender disso"*).
        #
        # O worker emite este estado quando percorreu a escada inteira e nenhum
        # endpoint estava livre AGORA. A app esta de pe, o shell relanca o worker e
        # a escada recomeca: e a app a ESPERAR. O `detail` ja vem neutro do worker
        # (ver o comentario do lado do `emit`), portanto nao ha HRESULT para
        # traduzir, mas mesmo que houvesse esta linha e a ultima: `human_audio_error`
        # nao deve conseguir transformar uma espera na frase que o dono mandou tirar.
        if state == 'audio-endpoint-unavailable':
            return ('No audio endpoint was free - Sotto keeps looking')
        return readable
    device = str(message.get('device') or '').strip()
    api = str(message.get('api') or '').strip()
    peak = message.get('peak')
    floor = message.get('peak_floor')
    stage = str(message.get('stage') or '').strip()
    detail = str(message.get('detail') or '').strip()
    if state == 'silent-device':
        where = f'{device} [{api}]' if device and api else (device or 'the tap')
        if peak is not None and floor is not None:
            return f'Silent audio device - {where} peaked {peak} < floor {floor}'
        return f'Silent audio device - {where} delivered no signal'
    if state == 'device-exhausted':
        return ('Audio tap carried no signal - every candidate device was flat')
    if stage and detail:
        # A TRADUCAO, ANTES DA LINHA CRUA. Ver `HRESULT_AUDIO_READINGS`: o dono ja viu
        # `WasapiError ... (0x8889000A)` na tela e chamou-lhe *"nojeira"*. Um codigo de erro
        # do Windows nao lhe diz nada, e a acao que resolve -- fechar quem segura o
        # dispositivo -- nao esta escrita em lado nenhum do hexadecimal.
        legivel = human_audio_error(detail)
        if legivel:
            return f'Sotto could not start listening - {legivel}'
        return f'Worker error at {stage} - {detail}'
    if detail:
        # F6 -- o mesmo orfao do corpo, no rodape: um codigo DESCONHECIDO continua a passar
        # cru de proposito (nao se inventa explicacao), mas um codigo CONHECIDO que chegue
        # por este caminho tambem tem de ser lido. */
        legivel = human_audio_error(detail)
        if legivel:
            return f'Sotto could not start listening - {legivel}'
        return f'Worker error - {detail}'
    if stage:
        return f'Worker error at {stage}'
    return readable


def worker_status_body(state, message):
    """The placeholder body for a worker status: the fields that explain it.

    The panel's own warm-up copy is what fills this area otherwise, and a panel
    whose headline says "warming up" while the worker is dead is the same lie as
    a neutral footer line.
    """
    message = message or {}
    parts = []
    for key in STATUS_BODY_FIELDS:
        value = message.get(key)
        if value is None or value == '':
            continue
        # F6 -- A TRADUCAO VALE AQUI TAMBEM, e nao valia. MEDIDO pelo audit dos dialogos
        # (2026-10-15), com a captura na mao: o CORPO do placeholder pintava
        #
        #     stage=capture-open detail=WasapiError: AUDCLNT_E_DEVICE_IN_USE (0x8889000A)
        #     device=Alto-falantes api=MME peak=0.000122
        #
        # -- **o hexadecimal CRU, na tela do dono.** A tabela `HRESULT_AUDIO_READINGS` so
        # estava ligada ao RODAPE (`worker_status_text`), e este irmao ao lado junta os campos
        # como vieram. Era isto o *"que nojeira e essa mano"* que ele fotografou.
        if key == 'detail':
            legivel = human_audio_error(value)
            if legivel:
                parts.append(f'{key}={legivel}')
                continue
        parts.append(f'{key}={value}')
    return ' '.join(parts)[:STATUS_BODY_MAX]

# ===========================================================================
# logging — stdout lines are the acceptance artefact
# ===========================================================================

_LOG_LOCK = threading.Lock()
#: A memoria do `log_repeat` (chave -> (ultimo texto, quando)).
_LOG_REPEAT = {}
_LOG_FILE = None
_LOG_QUEUE = None      # the mirror lines, one per log() call
_LOG_WRITER = None     # the ONE thread that owns the file



def _open_log(path):
    global _LOG_FILE, _LOG_QUEUE, _LOG_WRITER
    if path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        # THE LOG GREW WITHOUT BOUND. MEASURED 2026-10-13: _main/webview-run.log reached
        # **727.5 MB**, and simply READING it to check the app's own state blew a 300 s
        # deadline -- the instrument for the app became the slowest thing about it, and
        # every launch appended to it for ever.
        #
        # This runs BEFORE the append open, because on Windows the app holds the file and
        # it cannot be rotated from outside while the shell is alive.
        #
        # IT KEEPS THE TAIL AND DISCARDS THE REST, and the first version of this comment
        # claimed the opposite -- it said the remainder was "moved aside to <log>.1 rather
        # than discarded, so a user who wants the history still has it". THE CODE DOES NOT
        # DO THAT: it writes the TAIL into `<log>.1` and then `os.replace`s it onto the
        # log, so the OLD content is gone and no `.1` survives. MEASURED IN PRODUCTION
        # 2026-10-13 14:46: `LOG_ROTATED from=847859845 B kept=16777081 B cap=64 MB`, and
        # `_main/webview-run.log.1` does not exist.
        #
        # The BEHAVIOUR is the one intended -- bounded file, newest lines kept -- but the
        # claim was false and is corrected here rather than left to be quoted.
        #
        # A failure here is swallowed on purpose -- a log that cannot be rotated must never
        # stop the app from starting, and the append below still works either way.
        try:
            cap_mb = int(os.environ.get('SOTTO_LOG_CAP_MB', '64'))
            keep_mb = int(os.environ.get('SOTTO_LOG_KEEP_MB', '16'))
            if cap_mb > 0 and os.path.getsize(path) > cap_mb * 1024 * 1024:
                keep = max(1, keep_mb) * 1024 * 1024
                with open(path, 'rb') as fh:
                    fh.seek(0, os.SEEK_END)
                    size = fh.tell()
                    fh.seek(max(0, size - keep), os.SEEK_SET)
                    tail = fh.read()
                # start on a line boundary, so the kept file does not open mid-line
                cut = tail.find(b'\n')
                if 0 <= cut < len(tail) - 1:
                    tail = tail[cut + 1:]
                with open(path + '.1', 'wb') as fh:
                    fh.write(tail)
                os.replace(path + '.1', path)
                with open(path, 'a', encoding='utf-8') as fh:
                    fh.write('sotto: LOG_ROTATED from=%d B kept=%d B cap=%d MB\n'
                             % (size, len(tail), cap_mb))
        except Exception:
            pass
        _LOG_FILE = open(path, 'a', encoding='utf-8', buffering=1)
        # THE FROZEN MIRROR GETS ITS OWN THREAD -- this is the freeze fix.
        # `log()` used to write AND flush the file inline, on whatever thread
        # called it. For the WH_MOUSE_LL click hook that thread is WINDOWS' OWN
        # MOUSE INPUT PATH: measured by _main/hook-cost-oracle.py, one click
        # costs mean 3.31 ms, p99 38.29 ms, worst 768 ms with the mirror inline
        # against 0.005 / 0.018 / 0.736 ms without it, at the measured cadence
        # of 11.82 clicks a minute. The pointer for the whole desktop waits for
        # that write. So the caller queues the line and never waits for a disk.
        _LOG_QUEUE = queue.SimpleQueue()
        _LOG_WRITER = threading.Thread(target=_log_writer, name='sotto-log',
                                       daemon=True)
        _LOG_WRITER.start()


def _log_writer():
    """The ONE thread that owns the --log file. Nobody else writes it.

    The file and the queue are bound HERE, at thread start, and never re-read
    from the module globals: a writer that re-read them each iteration can
    observe a reset (or a None mid-teardown) and die, and a dead writer makes
    the WHOLE --log mirror disappear with no other symptom -- lines still get
    queued, nothing gets written, the run log simply stops. Same reason the
    loop is wrapped whole: an exception in the write path must not take the
    thread down with it.
    """
    q = _LOG_QUEUE
    fh = _LOG_FILE
    while True:
        try:
            line = q.get()
            if line is None:
                return
            fh.write(line + '\n')
            fh.flush()
        except Exception:  # noqa: BLE001 -- a dead mirror must not kill the app
            try:
                print(f'{_stamp()} sotto: LOG_MIRROR_DIED {type(line).__name__}',
                      flush=True)
            except Exception:  # noqa: BLE001
                pass
            return


def _log_drain(timeout_s=2.0):
    """Stop the writer, giving the ALREADY queued lines their disk time.

    Called on the exit path: `os._exit` does not wait for a daemon thread, and
    a SHELL_EXIT line that never lands would take its own evidence with it.
    """
    if _LOG_QUEUE is None:
        return
    _LOG_QUEUE.put(None)
    if _LOG_WRITER is not None:
        _LOG_WRITER.join(timeout_s)


def _stamp() -> str:
    """The hour a `sotto: ` line now carries: `2026-10-12 12:26:03.123`.

    THE DEFECT THIS CLOSES. Every `sotto:` line was untimed, so the log could say
    what happened and never when. The cold-boot model load this front was opened
    for was invisible in the one artefact that records it: `model-loading` and the
    `BRIDGE_SILENT ms=30000` that followed it carried no distance, so "how long
    does the load take" had no answer in the log at all, and the stutter the
    owner reports at startup could not be attributed to a phase.

    LEADING, not trailing, for two reasons. A log line reads time-first, which
    is what makes the file comparable with every other clock on this box
    (`Get-Process .StartTime`, the Task Scheduler history, the Event Log): the
    measurement this front needs is the distance between a shell line and a
    worker line taken tens of seconds apart. And the `sotto: ` tag keeps its
    exact position and spelling - every consumer of these lines in this repo
    reads them by substring or by `split('sotto: ', 1)[-1]` (measured across
    `_main/`, `app/`, `worker/`: 7 such consumers, 0 regex anchors on the tag),
    so the tag keeps matching while the hour is added in front of it.
    """
    now = datetime.now()
    return now.strftime('%Y-%m-%d %H:%M:%S.') + f'{now.microsecond // 1000:03d}'


#: Os ficheiros que decidem o COMPORTAMENTO desta shell. A lista e' explicita e
#: curta de proposito: um `glob` sobre `app/webview/` faria o numero mudar por
#: causa de um ficheiro que o processo nem carrega, e um numero que muda por
#: engano treina quem o le a ignora-lo. Cada um destes e' carregado ao vivo no
#: caminho que o dono usa (o painel, a legenda, o YouTube, o gesto).
#: Os ficheiros que a etiqueta cobre vivem em `code_identity` (uma definicao so'); o shell
#: re-exporta-os porque o `_main/live-code-freshness-oracle.py` os le' daqui.
from code_identity import _CODE_ID_FILES, _CODE_ID_GLOBS  # noqa: F401


def code_identity():
    """`sha256=<12 hex> files=<n> ...` -- o codigo que ESTE processo carregou."""
    return _code_identity(os.path.dirname(os.path.abspath(__file__)))


def log(message: str) -> None:
    """One `sotto: ` prefixed line on stdout, mirrored to --log when asked.

    The Electron arm logs the same way (main.js:56), so the two run logs read
    alike and a claim in the receipt can be checked without watching the screen.
    The stamp is prepended by `_stamp` rather than here, so `warn()` and every
    other caller inherits it without a second code path.
    """
    line = f'{_stamp()} sotto: {message}'
    with _LOG_LOCK:
        print(line, flush=True)
        if _LOG_FILE is not None:
            _LOG_QUEUE.put(line)


def log_repeat(key: str, message: str, every_s: float = 300.0) -> None:
    """UM `log` QUE NAO CUSTA UM FICHEIRO (2026-11-03).

    MEDIDO: um arranque deste shell escreveu **382** linhas
    `HOTKEY_OBSERVER_ALIVE`, 720 por hora, num ficheiro que so' roda aos 64 MB;
    e o `YOUTUBE_TICK_MS` fazia o mesmo a cada 5 s com o `n=` CONGELADO (49, 49,
    49 ...) -- um numero que nao muda, escrito para sempre. O ficheiro do dono
    chegou aos **54 MB** nesta sessao.

    A regra: a linha SAI na primeira vez e sempre que o TEXTO MUDA (o que
    interessa: `n` cresceu, a media subiu); repetida e igual, sai de
    `every_s` em `every_s`. Nada e' escondido: o nome do que ficou silencioso
    vai para o log na primeira ocorrencia, e o batimento lento continua a
    provar que o laco vive.
    """
    now = time.monotonic()
    last = _LOG_REPEAT.get(key)
    if last is None or last[0] != message or now - last[1] >= every_s:
        _LOG_REPEAT[key] = (message, now)
        log(message)


def warn(message: str) -> None:
    log(f'WARN {message}')


# O ARRANQUE ESTA' COMPLETO? -- UMA PERGUNTA, UM DONO (2026-11-03, MEDIDO).
# `run.cmd` roda `--wait-ready <ficheiro>` e APAGA o ficheiro a seguir
# (`del /q` no fim). A shell, porem, usava esse MESMO ficheiro como a sua
# propria resposta a "ja arranquei?" -- no `sotto-panel-stall` e no
# `STARTUP_NOT_READY`. Medido no arranque de 05:19:43 (pid 492):
# `mark_launch_ready` as 05:19:51, o `del` do run.cmd logo depois, e a
# partir dali a app passou a achar que NAO tinha arrancado --
# `PANEL_NAV_STALL s=12 -> re-empurrar a navegacao` (um `load_url` a mais
# na pagina que ja' estava carregada), `STARTUP_NOT_READY s=15`, e as
# 05:20:10 um `PANEL_NAV_STALL_FINAL s=25` que chamou `_complete_startup`
# OUTRA VEZ (daí o segundo `WORKER_AUTOSTART`). O ficheiro e' do
# largador; o estado de arranque e' da app.
_STARTUP_READY = {'done': False}


def _prune_stale_ready_files(directory, keep='', max_age_s=86400.0):
    """Os `ready-*.txt` que ficaram de largadas abortadas (2026-11-03).

    MEDIDO nesta box: **64** ficheiros em `_main/`, o mais antigo de 2026-10-07.
    O `run.cmd` apaga o seu no fim da espera, logo os que sobram sao de
    largadas que morreram antes disso -- lixo que cresce a cada falha e que o
    dono paga em espaco. Apaga so' o PADRAO, so' o que passou de um dia, e
    nunca o ficheiro desta propria largada.
    """
    try:
        now = time.time()
        keep = os.path.abspath(keep) if keep else ''
        for name in os.listdir(directory):
            if not (name.startswith('ready-') and name.endswith('.txt')):
                continue
            full = os.path.abspath(os.path.join(directory, name))
            if keep and full == keep:
                continue
            try:
                if now - os.path.getmtime(full) > max_age_s:
                    os.remove(full)
            except OSError:
                pass
    except OSError:
        pass


def startup_is_ready(path=None) -> bool:
    """Ja' arrancou? Em processo primeiro, ficheiro do largador depois.

    O ficheiro continua a ser aceito porque um arranque DIRECTO (sem
    `run.cmd`) nao tem `--ready-file`, e ha' quem o crie a' mao.
    """
    if _STARTUP_READY['done']:
        return True
    if not path:
        return False
    try:
        return os.path.exists(path)
    except Exception:                 # noqa: BLE001
        return False


def mark_launch_ready(path) -> bool:
    """run.cmd's readiness handshake (gap G3): touch `path` once the app is up.

    `run.cmd` `start`s the app detached, so the wrapper can never see any status
    after the spawn -- measured 2026-10-06 a launch logged `STAGING_LOADED` and
    then hung, and `run.cmd` still answered 0 (docs/audit/launch-entry.md §3/§4).
    The wrapper now hands a FRESH path here (`--ready-file`) and waits for it,
    bounded: the file appearing is "the app came up", the bound expiring is a
    HANG and the wrapper exits non-zero. A direct launch (no flag) is a no-op.
    A failure to write it is a WARN, not an exit: the app is up either way, and
    the wrapper's bound is the thing that reports the miss.
    """
    if not path:
        return False
    try:
        directory = os.path.dirname(os.path.abspath(path))
        if directory:
            os.makedirs(directory, exist_ok=True)
            _prune_stale_ready_files(directory, keep=os.path.abspath(path))
        with open(path, 'w', encoding='utf-8') as f:
            f.write(f'ready pid={os.getpid()}\n')
        return True
    except OSError as exc:  # noqa: BLE001 -- must not take the app down
        warn(f'READY_FILE_FAILED path={path} {exc!r}')
        return False


def wait_ready_file(path, timeout_s: float) -> int:
    """run.cmd's bounded half of G3: poll `path` until it exists, or give up.

    Returns 0 the moment the app has touched the file (it is up), 4 when
    `timeout_s` elapses without it (a HANG -- the app was started and did not
    come up), which is the non-zero the wrapper passes on. The bound is read
    from `SOTTO_READY_BOUND` by the caller so a test can shorten it; the default
    is the wrapper's own.
    """
    deadline = time.time() + max(0.0, timeout_s)
    while True:
        if os.path.exists(path):
            return 0
        if time.time() >= deadline:
            return 4
        time.sleep(0.1)


# ===========================================================================
# geometry — the port of main.js::dockRight
# ===========================================================================


def dock_right(work, width=PANEL_WIDTH, height=PANEL_HEIGHT,
               margin=PANEL_MARGIN, dock='right'):
    """Dock a panel to the right edge of `work`, vertically centred.

    Kept a pure function for the same reason main.js keeps it pure: the output
    is contained in the work area whatever the work area is, including
    degenerate rectangles. `work` is `{'x','y','width','height'}` in DIP.
    """
    want_width = width if isinstance(width, (int, float)) else PANEL_WIDTH
    want_height = height if isinstance(height, (int, float)) else PANEL_HEIGHT
    want_margin = margin if isinstance(margin, (int, float)) else PANEL_MARGIN
    w = max(0, work['width'])
    h = max(0, work['height'])

    # A margin that leaves the panel no room to live in is a margin that
    # shrinks before anything else does.
    m = max(0, min(want_margin, w / 8, h / 8))
    # A panel wider than its share of the work area is a mistake, not a layout.
    panel_width = min(want_width, max(0, w * PANEL_MAX_WORK_FRACTION))
    panel_height = min(want_height, max(0, h - 2 * m))

    x = work['x'] + w - panel_width - m
    # TOP-DOCKED, NOT VERTICALLY CENTRED (owner, 2026-10-17: *"o painel de baixo
    # esta muito embaixo, tem que ser mais pra cima"*). The old line was
    #     y = work['y'] + round((h - panel_height) / 2)
    # which, with `panel_height = min(900, h - 2*m)`, left the panel's top edge
    # half a screen below the top of the work area -- which is what the owner
    # means by "too low".
    #
    # THE NEW FORMULA, exactly:  y = work['y'] + m
    # -- the SAME `m` the right edge already uses (`max(0, min(margin, w/8, h/8))`,
    # :1008), so the panel hangs PANEL_MARGIN (12) from the top and from the right
    # and nothing else about the width changes. Containment is arithmetic, not a
    # hope: `panel_height` is clamped to `h - 2*m` (:1011), so
    # `work['y'] + m + panel_height <= work['y'] + h - m`, and both clamps below
    # (`max(work['y'], ...)`, then `min(..., work['y'] + h - height)`) still run, so
    # a short or offset monitor can never push the panel out of its work area.
    y = work['y'] + m

    geometry = {
        'workX': work['x'],
        'workY': work['y'],
        'workWidth': w,
        'workHeight': h,
        'x': max(work['x'], round(x)),
        'y': max(work['y'], round(y)),
        'width': max(1, round(panel_width)),
        'height': max(1, round(panel_height)),
        'margin': m,
        'docked': dock,
        # WHICH SURFACE this geometry is — see `dock_strip` for the measurement
        # that put it here.
        'surface': 'panel',
    }

    # Containment is an invariant, not a hope: clamp back into the work area.
    geometry['x'] = min(geometry['x'], work['x'] + w - geometry['width'])
    geometry['y'] = min(geometry['y'], work['y'] + h - geometry['height'])
    return geometry


def summary(g) -> str:
    """One line for the startup receipt — the same shape as main.js summary()."""
    return (
        f"docked={g['docked']} "
        f"work={g['workWidth']}x{g['workHeight']}@({g['workX']},{g['workY']}) "
        f"window={g['width']}x{g['height']}@({g['x']},{g['y']}) "
        f"margin={g['margin']}"
    )


# ===========================================================================
# Win32 — work area, DPI, extended styles, the hotkey
# ===========================================================================

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
shell32 = ctypes.WinDLL('shell32', use_last_error=True)

MONITOR_DEFAULTTOPRIMARY = 0x00000001

GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
#: What WinForms' `Form.CreateParams` sets while `ShowInTaskbar` is true and the
#: form has no owner — and it BEATS `WS_EX_TOOLWINDOW`, putting the panel in the
#: taskbar. Measured set on this shell's hwnd; see `reassert_taskbar_ex_style`.
WS_EX_APPWINDOW = 0x00040000
WS_EX_CONTROLPARENT = 0x00010000

SW_SHOWNOACTIVATE = 4
SW_HIDE = 0
SW_SHOW = 5
SW_RESTORE = 9
HWND_TOPMOST = -1
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010


#: AS DUAS HOTKEYS DO SOTTO (ordem do dono, 2026-11-01):
#:
#:     Alt+C       UMA pressao = UM passo do ciclo dos paineis (alterna show/hide)
#:     Ctrl+Space  UMA pressao = a legenda ao vivo liga/desliga
#:
#: NAO HA RELOGIO NENHUM NESTE CAMINHO, e e' isso que faz o gesto funcionar com o
#: Alt fisicamente em baixo e o C martelado: sem janela de toques e sem medicao de
#: duracao, nao ha nada que o Alt preso possa estragar. O que saiu com o contrato
#: de 2026-10-30 (1 toque = faixa, 2 toques = lado, HOLD = legenda):
#: `HOTKEY_HOLD_MS`, `HOTKEY_TAP_WINDOW_MS`, `HOLD_CEILING_MS`, `is_hold`,
#: `resolve_taps`, o `_tick`/`_finish_measure`/`_measuring`/`fake_hold_ms` do
#: `HotkeyThread`, o `on_hold` e o `hotkey_hold`. `_main/altc-gesture-oracle.py`
#: guarda a ausencia deles.
#:
#: A HISTORIA do gesto e as seis regras de prioridade estao em
#: `docs/hotkey-gestos.md` e `docs/hotkey-altc-full-audit.md`. As TECLAS (fabrica,
#: vocabulario e o ciclo) vivem em `hotkey_gesture.py`, um so', lidos por
#: `hotkey_numbers()`: nao se repetem aqui, porque uma segunda copia envelhece
#: sozinha.


#: (O PISO `EXTERNAL_RESUME_MIN_S` SAIU A 2026-11-03 COM O PROCESSO.) Ele limitava
#: a frequencia de `start_worker` porque cada um custava uma carga de modelo --
#: medido 2026-10-18, duas cargas em 2 min 52 s. O release passou a limpar um
#: PEDIDO num ficheiro (`park`), que nao custa nada: manter o piso era o unico
#: defeito que sobrava, e com ele o motor ficava largado ate' 45 s depois de o
#: player parar. Ver `_main/external-resume-oracle.py`.

#: QUANTO TEMPO UM CAPTION DO PLAYER TEM DE DURAR ANTES DE O TRABALHADOR SER
#: ESTACIONADO (2026-11-02). O estacionamento existe para libertar a VRAM enquanto
#: o YouTube serve a linha, mas ele MATA o worker -- e matar/reabrir um cliente
#: WASAPI e' um hitch no motor de audio que o dono partilha com o video. MEDIDO na
#: sessao dele: 10 `EXTERNAL_CAPTIONS_WORKER_PARKED` e 10 `_RESUMED` desde as
#: 20:00, e ele ouviu isso como o audio a sumir (*"ja nao mandei tu parar de mutar
#: do nada meu audio?"*). O piso e' o mesmo raciocinio do `RELEASE_S`: a cadencia
#: e' do player, nao nossa -- uma janela curta de legenda nao pode custar um load.
EXTERNAL_PARK_DELAY_S = 20.0

#: Bottom-strip geometry: wide and short, bottom-centred. The 1040x150 comes
#: from the strip-surface measurements (height read from `--strip-height` in
#: the CSS, never hard-coded); STRIP_HEIGHT_FALLBACK exists only so a missing
#: CSS value still leaves a usable strip, and every use is logged.
STRIP_WIDTH = 1040
STRIP_HEIGHT = 150
STRIP_HEIGHT_FALLBACK = 148
STRIP_WIDTH_MAX = 1040
STRIP_WIDTH_MIN = 480
STRIP_WIDTH_FRACTION = 0.62
#: The CSS custom property that IS the strip's height (`panel.css:52`).
#: Told to the page the moment the SHELL moves the strip window. panel.html:1093
#: has the page stop applying its own CSS transform once this is set, because a
#: page transform plus a window move would add up to twice the drag.
STRIP_MOVED_JS = ("(function () { if (document.body) {"
                  " document.body.setAttribute('data-strip-moved', '1'); }"
                  " return true; })()")
STRIP_HEIGHT_CSS_VAR = '--strip-height'
FLOAT_HEIGHT_CSS_VAR = '--float-height'   # the floated caption's window height
STRIP_BOTTOM_MARGIN = 48
#: THE LOG BUDGET OF THE STATS FEED. `on_worker_stats` fires once per worker
#: `WORKER_STATS` line, and that line is a METER sample — the worker may publish
#: it at tens of Hz. A log line per sample is an unbounded log, and an unbounded
#: log is how a feature gets turned off to keep the file quiet (it happened: the
#: worker's meter default was set to zero). So the push logs its FIRST sample and
#: then at most one line per this many seconds, each carrying the count it stands
#: for. The PANEL is still fed at the worker's own cadence — only the LOG is
#: aggregated.
STATS_LOG_INTERVAL_S = 30.0

#: THE WAVE. `worker/sotto_worker.py:3591` emits `{"type":"meter","peak":…,
#: "blocks":…}` once per meter window (10 Hz by default) and its `peak` is the
#: peak OF THAT WINDOW, while the `WORKER_STATS` line on stderr carries the
#: RUNNING MAXIMUM of the whole run. A wave drawn from a running maximum is a
#: staircase that only rises and then flattens — that IS the defect the owner
#: reported ("as ondas que crescem e diminuem nao ta funcionando"). So a fresh
#: meter sample WINS over the stats line, and the two are never mixed.
METER_FRESH_S = 2.0
#: The meter path used to fall into the unknown-kind `else`, which logged
#: `BRIDGE_UNKNOWN type='meter'` PER SAMPLE — measured 35 B × 10 Hz ≈ 20.5 KB/min
#: with no end. The DATA is not throttled (that mistake was made once already, on
#: the worker side): only this log line is, on the same budget as the push.
METER_LOG_INTERVAL_S = 30.0

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
#: A mensagem com que `HotkeyThread.stop` ACORDA o pump: `WaitMessage` dorme ate'
#: chegar algo a' fila, e um `Event` do `threading` nao o acorda.
WM_APP = 0x8000
#: `PeekMessageW` flag -- take the message out of the queue.
PM_REMOVE = 0x0001
#: O bit do Win32 de cada nome de modificador que `hotkey_gesture` aceita. A ABI
#: fica deste lado; o VOCABULARIO das teclas fica do lado puro, num sitio so'.
_MOD_BITS = {'alt': MOD_ALT, 'ctrl': MOD_CONTROL, 'shift': MOD_SHIFT,
             'win': MOD_WIN}
#: O botao esquerdo do rato, lido pelo `OutsideClickWatcher` para saber se um
#: arrasto de edit mode esta' em curso. Sem hook, isto e' a unica fonte.
VK_LBUTTON = 0x01

_HOTKEY_ID = 0xB0F0  # any id will do; this one is ours and is not a window id


class MSG(ctypes.Structure):
    _fields_ = [('hwnd', wt.HWND), ('message', ctypes.c_uint),
                ('wParam', ctypes.c_ulonglong), ('lParam', ctypes.c_longlong),
                ('time', ctypes.c_uint), ('pt', ctypes.c_long * 2)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_ulong), ('rcMonitor', RECT),
                ('rcWork', RECT), ('dwFlags', ctypes.c_ulong)]


def dpi_scale() -> float:
    """Physical pixels per DIP for this process.

    pywebview marks the process System-DPI-aware (winforms.py:820), so one DIP
    is `dpi/96` physical pixels and the work area has to be divided back before
    it is compared with Electron's DIP numbers. On this host it is 1.0 (Electron
    logged scaleFactor=1), which is why the two arms agree.
    """
    try:
        dpi = user32.GetDpiForSystem()
    except AttributeError:  # pragma: no cover - pre-1607 Windows
        return 1.0
    return (dpi / 96.0) if dpi else 1.0


MONITOR_DEFAULTTONEAREST = 0x00000002


def _monitor_scale(handle) -> float:
    """Per-monitor DPI, falling back to the process DPI when shcore refuses.

    `dpi_scale()` is the SYSTEM DPI (GetDpiForSystem). On a two-monitor desk
    with different scaling that number is right for exactly one of them, so a
    window docked to the other monitor lands at the wrong physical size. The
    owner's report (2026-10-17) is that every panel spawns in the wrong place
    and "em diferentes monitores faria pior ainda"; this is that defect.
    """
    try:
        shcore = ctypes.WinDLL('shcore', use_last_error=True)
        shcore.GetDpiForMonitor.argtypes = [
            ctypes.c_void_p, ctypes.c_int,
            ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint)]
        shcore.GetDpiForMonitor.restype = ctypes.c_long
        dx = ctypes.c_uint(0)
        dy = ctypes.c_uint(0)
        if shcore.GetDpiForMonitor(handle, 0, ctypes.byref(dx),
                                   ctypes.byref(dy)) == 0 and dx.value:
            return dx.value / 96.0
    except Exception:  # noqa: BLE001
        pass
    return dpi_scale()


def _display_for_monitor(handle) -> dict:
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(handle, ctypes.byref(mi)):
        raise ctypes.WinError(ctypes.get_last_error())
    scale = _monitor_scale(handle)

    def as_rect(r):
        return {
            'x': round(r.left / scale),
            'y': round(r.top / scale),
            'width': round((r.right - r.left) / scale),
            'height': round((r.bottom - r.top) / scale),
        }

    return {
        'handle': handle,
        'bounds': as_rect(mi.rcMonitor),
        'workArea': as_rect(mi.rcWork),
        'scaleFactor': scale,
    }


def primary_display() -> dict:
    """Primary display bounds + work area, in DIP, the shape Electron reports."""
    handle = user32.MonitorFromPoint(POINT(0, 0), MONITOR_DEFAULTTOPRIMARY)
    return _display_for_monitor(handle)


def target_display() -> dict:
    """The monitor the OWNER is looking at: the one under the mouse pointer.

    Alt+C is pressed while looking at a screen, and the panel belongs on THAT
    screen. The old code always used `MonitorFromPoint(POINT(0,0))`, i.e. the
    primary monitor, so on a multi-monitor desk every panel opened on the
    primary no matter where the owner was.
    """
    # First the monitor of the FOREGROUND window: Alt+C is pressed while the
    # owner is watching/using another app, and that app's screen is the target.
    # When Sotto itself is foreground, fall back to the mouse, then primary.
    try:
        user32.GetForegroundWindow.restype = wt.HWND
        user32.MonitorFromWindow.argtypes = [wt.HWND, wt.DWORD]
        user32.MonitorFromWindow.restype = ctypes.c_void_p
    except Exception:  # noqa: BLE001
        pass
    try:
        fg = user32.GetForegroundWindow()
        if fg:
            b = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(fg, b, 256)
            if not b.value.strip().lower().startswith('sotto'):
                handle = user32.MonitorFromWindow(fg, MONITOR_DEFAULTTONEAREST)
                if handle:
                    return _display_for_monitor(handle)
    except Exception:  # noqa: BLE001
        pass
    pt = POINT()
    try:
        if user32.GetCursorPos(ctypes.byref(pt)):
            handle = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
            return _display_for_monitor(handle)
    except Exception:  # noqa: BLE001
        pass
    return primary_display()


def set_ex_style(hwnd, add=0, remove=0) -> int:
    """Toggle extended styles on the panel HWND and return the new value."""
    current = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    updated = (current | add) & ~remove
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, updated)
    return updated


class VramGuard(threading.Thread):
    """PARK THE WORKER WHEN ANOTHER APP NEEDS THE GPU (owner, 2026-10-17).

    Owner, verbatim: *"se tem qualquer processo que quer usar vram, deviamos
    tirar os modelos da vram, tipo um jogo pesado... nem q fazer o modelo ser
    descarregado da vram"*.

    The worker owns a CUDA context and ~1.8 GB of VRAM. A game that wants most
    of the 16 GB cannot get it while that context lives, and "paused but still
    loaded" does NOT release it. This thread samples NVML's device free memory;
    when it stays below LOW_MB it kills the worker (TerminateProcess releases
    the CUDA context with the process), and when free memory stays above
    RESUME_MB it starts it again. Killing rather than a soft pause is deliberate:
    a soft pause keeps the allocation, which is the thing the game needs.
    """

    INTERVAL_S = 3.0
    LOW_MB = 1200.0
    RESUME_MB = 2400.0
    STREAK = 2

    def __init__(self, shell):
        super().__init__(name='sotto-vram-guard', daemon=True)
        self.shell = shell
        self.stop_event = threading.Event()
        self.low = 0
        self.high = 0
        self.parked = 0
        self.resumed = 0

    def stop(self):
        self.stop_event.set()

    def run(self):
        try:
            import pynvml
            pynvml.nvmlInit()
        except Exception as exc:  # noqa: BLE001
            log(f'VRAM_GUARD_UNAVAILABLE error={exc!r}')
            return
        log(f'VRAM_GUARD started=true interval_s={self.INTERVAL_S} '
            f'low_mb={self.LOW_MB} resume_mb={self.RESUME_MB}')
        try:
            while not self.stop_event.is_set():
                try:
                    free = min(
                        pynvml.nvmlDeviceGetMemoryInfo(
                            pynvml.nvmlDeviceGetHandleByIndex(i)).free / (1024.0 * 1024.0)
                        for i in range(pynvml.nvmlDeviceGetCount()))
                except Exception as exc:  # noqa: BLE001
                    if self.low == 0:
                        log(f'VRAM_GUARD_READ_FAILED error={exc!r}')
                    free = None
                if free is not None:
                    bridge = getattr(self.shell, 'bridge', None)
                    running = (bridge is not None
                               and getattr(bridge, 'child', None) is not None)
                    # A WORKER THAT IS STILL LOADING ITS OWN MODEL CANNOT BE
                    # THE REASON THE VRAM IS LOW -- IT IS THE VRAM.
                    # MEASURED 2026-10-20, on the owner's own box: the worker
                    # started at 00:43:05 and the guard parked it 3 s later
                    # with `free_mb=365`, because the model load itself had
                    # taken the VRAM (the worker's VRAM delta was MEASURED on
                    # 2026-10-21 at **1175-1703 MiB** -- the "~9.7 GB" that this
                    # comment used to claim was NOT reproduced and is not a
                    # justification of anything). The guard then resumed it,
                    # the new worker loaded the model, the VRAM fell again, and
                    # the treadmill repeated -- each turn a model load and a
                    # ~1.2 GB spike for the owner, and the last turn left the
                    # worker DEAD (no resume), which is the empty panel.
                    #
                    # THE GUARD'S PURPOSE (owner, 2026-10-17, verbatim:
                    # *"se tem qualquer processo que quer usar vram, deviamos
                    # tirar os modelos da vram, tipo um jogo pesado"*) is
                    # ANOTHER APP. A game that takes the VRAM during the
                    # load is still served: the moment the model is up, the
                    # free memory is low again and the guard parks the worker.
                    loaded = bool(getattr(bridge, 'loaded', False))
                    if running and loaded and free < self.LOW_MB:
                        self.low += 1
                        self.high = 0
                        if self.low >= self.STREAK:
                            self.low = 0
                            if self.shell.park_worker_for_vram(free):
                                self.parked += 1
                    elif self.shell._vram_parked and free >= self.RESUME_MB:
                        self.high += 1
                        self.low = 0
                        if self.high >= self.STREAK:
                            self.high = 0
                            if self.shell.resume_after_vram(free):
                                self.resumed += 1
                    else:
                        self.low = 0
                        self.high = 0
                # A ESPERA E' DESTE LACO (2026-11-03, MEDIDO DUAS VEZES).
                # Aqui esteve, por um patch mal ancorado, um bloco de espera
                # FORA do `while` -- o `while` ficou sem espera nenhuma e este
                # thread passou a gastar **97 % de um nucleo** (`THREAD_CPU
                # total=101% top=sotto-vram-guard:97%`, tres amostras de 30 s
                # seguidas no pid 36568), a perguntar a' NVML em ciclo fechado.
                # Medido antes disso: a shell inteira em 102 % de um nucleo com a
                # app em repouso, e o culpado so' apareceu quando o censo por
                # NOME de thread passou a existir.
                self.stop_event.wait(self.INTERVAL_S)
        finally:
            try:
                pynvml.nvmlShutdown()
            except Exception:  # noqa: BLE001
                pass
            log(f'VRAM_GUARD stopped=true parked={self.parked} '
                f'resumed={self.resumed}')


class YouTubeTrackThread(threading.Thread):
    """The REAL caption track of the YouTube video being watched.

    WHY A THREAD OF ITS OWN. `yt_dlp`'s metadata call for ONE video took
    **5.0 s** (MEASURED 2026-10-19: `extract_info` with `skip_download`,
    no media downloaded). The caption reader polls every 0.30 s, so blocking
    it would freeze the reader for 5 s on every new video -- and the owner
    would watch the last line repeat while the fetch ran.

    WHAT IT ANSWERS. One question: "what is this video's own caption
    track?". The answer is one of the four states of `youtube_captions`
    (`has-track` / `no-track` / `no-cue-in-window` / `time-unknown`). It does
    NOT decide what the caption box shows -- that is the watcher's job, and
    the rule is the owner's: the track REPLACES the live caption while it
    has something to say, and the live caption (the ASR) is the BASE and is
    never stopped by the absence of a track.

    THE RETRY. A failed extract is NOT a verdict about the video --
    `youtube_captions.fetch_track` says so and does not cache it -- so it is
    retried, but not every 300 ms: `REFRESH_S` between two attempts, and
    the module decides for itself when a refused payload is worth
    asking for again.
    """

    #: HOW OFTEN THE TRACK IS ASKED FOR AGAIN. `youtube_captions` caches a
    #: REFUSED payload for `PAYLOAD_RETRY_TTL_S` (60 s -- MEASURED 2026-10-19:
    #: YouTube answers HTTP 429 to the automatic track of the video the owner
    #: was watching) and retries the payload WITHOUT repeating the 5 s
    #: extract. That retry only fires if somebody calls `fetch_track` again
    #: after the TTL, so the thread RE-ASKS every `REFRESH_S` (30 s). The
    #: call itself is a disk read while the cache is warm.
    REFRESH_S = 30.0
    #: How often the thread looks for work.
    POLL_S = 0.20
    #: HOW OFTEN the track is searched AGAIN by the painted words. The
    #: search costs an extract (MEASURED 5.0 s), and a video can carry a
    #: hundred automatic translations; so after a search that found nothing
    #: the next one waits this long. MEASURED 2026-10-20: the owner's own
    #: video was found on the FIRST search (the third candidate), and the
    #: state "the paint does not match the served track" is SHORT -- it is
    #: a video changing, or the player changing its own caption language.
    #: While it lasts the app shows nothing, so the wait is 20 s and not
    #: 300 s.
    PAINT_SEARCH_RETRY_S = 20.0

    def __init__(self, shell):
        super().__init__(name='sotto-yt-track', daemon=True)
        self.shell = shell
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.want = ''          # the video id we are asked about
        self.inflight = ''      # the id being fetched right now
        self.done_for = ''      # the id we last finished (ok or failed)
        self.track = None       # the last result
        self.track_for = ''     # the id `track` belongs to
        self.next_fetch_at = 0.0
        self.fetches = 0
        self.failures = 0
        #: The words the player is painting RIGHT NOW, and the video they
        #: belong to. They are the QUESTION that decides the track.
        self.painted = None
        self.painted_for = ''
        #: The video we last searched BY PAINT, and when.
        self.paint_search_for = ''
        self.paint_search_at = 0.0
        #: THE QUESTION LAST ASKED, not the tick: the loop re-sends the same
        #: painted words 20 times a second, and re-sending them is not a new
        #: question. Without this key every tick re-armed the fetch.
        self.paint_key = ''
        self.paint_key_for = ''
        #: HOW THE LOOP SIDE COSTS NOTHING IS A NUMBER: asks, and the slow
        #: ones written to the log. A tick that waits for the network shows up
        #: here as a millisecond count, not as a frozen caption.
        self.polls = 0
        self.ask_slow_at = 0.0
        #: A fetch whose video nobody asks about anymore. It is not published
        #: as THE track, and it does not arm the next window.
        self.dropped = 0

    @staticmethod
    def _paint_key(painted):
        """The painted words as ONE key, or '' when there is no paint."""
        if not painted:
            return ''
        return ' '.join(str(w) for w in painted)[:200]

    def request(self, video_id, painted=None):
        """Ask for this video's track -- FIRE AND FORGET. NEVER blocks.

        Returns the track when one is ALREADY here for this video, and None
        otherwise. It does NOT call `fetch_track` and does NOT wait for the
        thread: the caller is the caption loop, and its tick IS the caption's
        latency. MEASURED 2026-11-03 in the owner's own log
        (`_main/webview-run.log`): `EXTERNAL_CAPTIONS_READ_MS ms=46766.0
        phases={'target': 0.0, 'source': 0.0}` immediately before
        `YOUTUBE_TRACK_READY video_id=... cues=1083`, then `ms=62234.0`. A
        46 s tick whose two cheap phases are both named is the `yt-dlp` of the
        track running INSIDE the loop.

        `painted` is the list of words the player is painting RIGHT NOW. It
        is the QUESTION that decides the track: the track the player shows
        is the one whose cues HOLD those words. MEASURED 2026-10-20 on the
        owner's own video: the player painted `en-orig` while the language
        preference would have served `pt-orig` -- Portuguese against
        English, in the owner's own comparison.

        NO DUPLICATE FETCH: the same video with the SAME painted words is the
        same question, and it is asked once per `REFRESH_S` (and once per
        `PAINT_SEARCH_RETRY_S` when the words CHANGE). A NEW video supersedes
        the old one -- see `_fetch`.
        """
        t0 = time.monotonic()
        vid = str(video_id or '')
        key = self._paint_key(painted)
        now = time.monotonic()
        with self.lock:
            new_video = vid != self.want
            if vid != self.track_for:
                # A NEW video: ask for it NOW, not in up to `REFRESH_S`.
                self.next_fetch_at = 0.0
            self.want = vid
            if painted:
                self.painted = list(painted)
                self.painted_for = vid
                if key != self.paint_key or vid != self.paint_key_for:
                    # A NEW QUESTION for the track: the player is painting
                    # words the track we have does not hold, so the track we
                    # have is the WRONG one. Ask again NOW -- and not more
                    # than once every `PAINT_SEARCH_RETRY_S`.
                    self.paint_key = key
                    self.paint_key_for = vid
                    if (self.paint_search_for != vid
                            or (now - self.paint_search_at)
                            > self.PAINT_SEARCH_RETRY_S):
                        self.paint_search_for = vid
                        self.paint_search_at = now
                        self.next_fetch_at = 0.0
            track = self.track if self.track_for == vid else None
        self.polls += 1
        ms = (time.monotonic() - t0) * 1000.0
        if ms > 5.0 and (time.monotonic() - self.ask_slow_at) > 5.0:
            self.ask_slow_at = time.monotonic()
            log('YOUTUBE_TRACK_ASK_MS ms=%.1f vid=%s polls=%d new=%s'
                % (ms, vid, self.polls, int(bool(new_video))))
        return track

    def current(self, video_id):
        """The track of this video, if it is the one we already have."""
        with self.lock:
            if self.track_for == str(video_id or ''):
                return self.track
        return None

    def run(self):
        while not self.stop_event.is_set():
            with self.lock:
                want = self.want
                busy = self.inflight
                due = time.monotonic() >= self.next_fetch_at
            if want and want != busy and due:
                self._fetch(want)
            self.stop_event.wait(self.POLL_S)
        log('YOUTUBE_TRACK_THREAD stopped=true fetches=%d failures=%d'
            % (self.fetches, self.failures))

    def _fetch(self, video_id):
        with self.lock:
            self.inflight = video_id
            paint = self.painted if self.painted_for == video_id else None
        track = None
        error = None
        try:
            import youtube_captions
            track = youtube_captions.fetch_track(video_id, painted=paint)
        except Exception as exc:  # noqa: BLE001
            error = exc
        with self.lock:
            self.inflight = ''
            self.done_for = video_id
            self.fetches += 1
            failed = track is None or (
                isinstance(track, dict) and track.get('reason') == 'extract-failed')
            if failed:
                self.failures += 1
            # A NEW VIDEO SUPERSEDES THE OLD ONE (2026-11-03). The owner
            # alternates between videos all the time, and a fetch lands
            # seconds later. Two rules, and both are about the LOOP never
            # waiting: the result of a video nobody is asking about anymore
            # is NOT published as THE track, and -- the measured part -- it
            # does NOT arm the `REFRESH_S` window that would make the NEW
            # video wait behind it. Before this, a 5 s fetch for video A
            # finishing after the owner switched to B made B wait 30 s, with
            # the box empty and the ASR parked.
            superseded = self.want != video_id
            if superseded:
                self.dropped += 1
                self.next_fetch_at = 0.0
            else:
                self.track = track
                self.track_for = video_id
                # The NEXT ask is `REFRESH_S` away, so the module's own retry
                # of a refused payload (60 s) can happen.
                self.next_fetch_at = time.monotonic() + self.REFRESH_S
        if superseded:
            log('YOUTUBE_TRACK_DROPPED video_id=%s reason=superseded want=%s '
                'fetches=%d dropped=%d'
                % (video_id, self.want, self.fetches, self.dropped))
            return
        if error is not None:
            log(f'YOUTUBE_TRACK_FETCH_FAILED video_id={video_id} error={error!r}')
            return
        if track is None:
            log(f'YOUTUBE_TRACK_FETCH_FAILED video_id={video_id} error=no-result')
            return
        log('YOUTUBE_TRACK_READY video_id=%s state=%s cues=%d lang=%s '
            'source=%s reason=%s error=%s cached=%s'
            % (video_id, track.get('state'), len(track.get('cues') or ()),
               track.get('lang'), track.get('source'), track.get('reason'),
               track.get('error'), bool(track.get('cached'))))
        # HOW THE TRACK WAS CHOSEN. `painted` means the player's own words
        # are IN it; `painted-no-match` means no candidate held them and
        # this one is a FALLBACK. Neither is ever silent.
        log('YOUTUBE_TRACK_PAINT video_id=%s source=%s cue=%s match=%s '
            'painted_words=%s'
            % (video_id, track.get('player_source') or '-',
               (track.get('paint_cue')
                if track.get('paint_cue') is not None else '-'),
               '1' if track.get('player_match') else '0',
               len(paint) if paint else 0))


def _yt_mark(owner, phase):
    """Marca a fase em ms desde o inicio da LEITURA (2026-11-03).

    Existe por um `EXTERNAL_CAPTIONS_READ_MS ms=58516.0` medido nesta sessao: uma
    leitura de 58 s sem nome de fase. Um numero assim sem nome e' um beco.
    """
    try:
        start = getattr(owner, '_yt_phase_start', None)
        if start is None:
            owner._yt_phase_start = time.monotonic()
            start = owner._yt_phase_start
        phases = getattr(owner, '_yt_phases', None)
        if phases is None or getattr(owner, '_yt_phase_start', None) != start:
            phases = {}
            owner._yt_phases = phases
        phases[phase] = round((time.monotonic() - start) * 1000.0, 1)
    except Exception:  # noqa: BLE001
        pass


#: Instante zero para os marcos `WEBVIEW_NAV t=` (2026-11-03).
_WEBVIEW_T0 = time.monotonic()


class ExternalCaptionWatcher(threading.Thread):
    #: A FOTO DO DOM do tick em curso (`None` = nao ha'). Declarada aqui para
    #: NENHUM caminho a ler antes de alguem a escrever: medido 2026-11-03,
    #: `YOUTUBE_PAINT_READ_FAILED error=AttributeError("'ExternalCaptionWatcher'
    #: object has no attribute 'yt_cdp_rows'")` a cada arranque.
    yt_cdp_rows = None
    """READ THE CAPTIONS A PLAYER ALREADY SHOWS (owner, 2026-10-17).

    YouTube and Stremio (Electron) render their subtitles as UI Automation Text
    elements at the bottom of their player. Those captions are already
    synchronised by the player itself, so this thread does not download,
    parse or clock anything: it reads the line the player is painting and hands
    it to the panel as a caption event.

    MEASURED 2026-10-17: a YouTube video in Chrome exposed `'>> So'`, `' the'`,
    `' Akali'`, ... at y=942..1001 inside a 1920x1080 player, and the address
    bar's ValuePattern was `youtube.com/watch?v=...`.

    It is OPTIONAL and fail-open: no comtypes/UIA, a non-video foreground
    window, or a read error simply produces nothing, and the ASR engine is
    untouched.
    """

    #: A LEITURA E' A LATENCIA DA LEGENDA (2026-11-02). Era 0,30 s, e com a
    #: varredura da arvore por tick a leitura custava 650-3500 ms -- o numero
    #: nunca chegava a valer, porque quem mandava era o custo. Depois dos caches
    #: (janela da legenda, relogio em thread propria, cache do `player_source`)
    #: a leitura caiu para 16-125 ms MEDIDOS, e o intervalo passa a ser ele.
    #: NAO E' UMA ESPERA OCIOSA, E' O RESTO DO ORCAMENTO (2026-11-03). A
    #: leitura da pintura custa 62-110 ms MEDIDOS nesta box (`UIA`,
    #: 12-18 filhos por cue), e o laco esperava mais 120 ms em cima dela: o
    #: periodo real ficava em ~200-230 ms e o ATRASO medido contra o player
    #: (instrumento `_main/_yt-live-latency.py`, 45 s a tocar) saiu com mediana
    #: 318 ms. O alvo e' o player: o resto do orcamento passa a ser 40 ms, para
    #: o periodo ficar so' o custo da leitura.
    #: 40 ms DE RESTO ERA 108 % DE UM NUCLEO (2026-11-03, MEDIDO). O laco roda
    #: a `leitura + INTERVAL_S`; com a leitura em ~50 ms (UIA sobre a janela do
    #: Chrome), o periodo real ficou em ~90 ms e `YOUTUBE_TICK_MS n=` contou
    #: **100 ticks a cada 5 s (20 Hz)**, com 95,6 % de um nucleo numa unica
    #: thread (`GetThreadTimes` no pid 28044, 5 s de amostra). A legenda nao
    #: precisa de 20 Hz: os cues do YouTube mudam a cada ~2 s, o `_tick` custa
    #: 0 ms, e a revelacao palavra-a-palavra interpola localmente a `RENDER_S`
    #: (60 ms) entre duas leituras -- nenhum chamada Win32 nesse caminho. 10 Hz
    #: e' o dobro da cadencia de desenho e dez vezes a do player.
    INTERVAL_S = 0.10
    #: Sem player nenhum, 4 Hz. Ver o comment do `wait` no fim do `run`. Ate'
    #: 2026-11-03 esta constante era LETRA MORTA: o `wait` do laco pedia
    #: sempre `INTERVAL_S`, e o laco perguntava 10x/s a janela em primeiro
    #: plano com o player fechado (o same defeito da familia do `VramGuard`,
    #: que tinha a espera FORA do laco).
    IDLE_INTERVAL_S = 0.25
    #: A cadencia do DESENHO da legenda do YouTube, entre leituras do UIA. 60 ms
    #: e' mais fino do que o espaco entre palavras do payload (medido: 0, 240,
    #: 400 ms) e grosso o bastante para nao gastar CPU: recompza texto ja'
    #: conhecido, sem uma unica chamada ao Windows.
    RENDER_S = 0.06
    #: A line that has not changed for this long is closed even if the player
    #: has not moved on yet (the panel's own hold timer is the fallback).
    STABLE_FINAL_S = 1.6
    #: No caption for this long = the player stopped showing them; give the
    #: microphone back to the ASR engine.
    RELEASE_S = 1.8
    #: THE SAME RULE FOR THE YOUTUBE REAL TRACK, AND MUCH LONGER. A caption
    #: track has gaps between the cues, and the player's clock can be
    #: unreadable for a while; a 1.8 s release would then cost a model load
    #: (MEASURED 11.6 s, 1 218 MB resident) every few seconds. MEASURED
    #: 2026-10-19: the real track's `RELEASE_S` is the gap between two cues
    #: of the same video, and the owner must not see the microphone go and
    #: come while the video plays.
    YT_RELEASE_S = 30.0

    def __init__(self, shell):
        super().__init__(name='sotto-external-captions', daemon=True)
        self.shell = shell
        self.stop_event = threading.Event()
        self.last_line = ''
        self.last_rows = []
        self.last_source = ''
        self.last_change = 0.0
        self.last_seen = 0.0
        self.finalized = False
        self.failures = 0
        self.reads = 0
        #: The video window we last read captions from. When the owner presses
        #: Alt+C, Sotto becomes foreground and YouTube no longer is; keeping the
        #: handle lets us keep reading the player BEHIND the panel.
        self.target_hwnd = 0
        #: THE YOUTUBE REAL TRACK (2026-10-19). The video we are watching, the
        #: cue we last showed, and why we have nothing to show.
        self.yt_video_id = ''
        self.yt_cue = ''
        self.yt_reason = ''
        #: When the player's clock last could not be read (the player may be
        #: gone). 0 = the clock is readable. MEASURED 2026-10-20: with the
        #: video PAUSED the clock reads fine and the cue is there, so this
        #: stays 0 and the worker is NOT released; a player that disappeared
        #: is a different fact.
        self.yt_no_clock_since = 0.0
        #: THE LAST ALIGNMENT between the player's painted words and the
        #: served track. It is the app's knowledge of WHERE THE VIDEO IS,
        #: and it is what tells a FROZEN clock from a real one.
        self.yt_hit = None
        #: Why the last read of the painted caption ended the way it did. The
        #: log line is written when it CHANGES, so a state that is never
        #: written is not a state that never happened.
        self.yt_paint_why = ''
        #: O ULTIMO INSTANTE usado quando o player pinta OUTRA faixa (uma traducao), e a
        #: chave das palavras que ele pintava nesse instante. E o que separa um relogio que
        #: anda de um relogio congelado: com a pintura a mudar e o relogio parado, o relogio
        #: esta congelado e nada e mostrado. MEDIDO 2026-10-23 (ver `painted-other-track`).
        self.yt_foreign_t = None
        self.yt_foreign_key = ''
        #: O CHAO DO TEMPO (2026-10-30) -- o inicio da cue mais avancada ja'
        #: servida, e a ultima leitura do relogio. Ver `youtube_monotonic.py`
        #: para a regra e para as 129 linhas de `webview-run.log` que a
        #: motivaram (a dona viu a legenda *"repetir o instante de tras"*).
        self.yt_serve_floor = None
        self.yt_held_logged = None
        #: The last line we wrote to the log. THE DECISION IS WRITTEN ONCE
        #: PER CHANGE, not once per poll: a line per poll is noise, and a
        #: decision that is never written is a decision nobody can check.
        self.yt_caption_logged = ''

    def stop(self):
        self.stop_event.set()

    def replay(self):
        """Emit the CURRENT player line again (a panel just became visible)."""
        self.last_line = ''
        self.last_rows = []
        self.finalized = False
        self.last_change = 0.0

    def run(self):
        try:
            import external_subs
            UIA, uia = external_subs._uia()
        except Exception as exc:  # noqa: BLE001
            log(f'EXTERNAL_CAPTIONS_UNAVAILABLE error={exc!r}')
            return
        log('EXTERNAL_CAPTIONS_WATCH started=true interval_s=%.2f' % self.INTERVAL_S)
        while not self.stop_event.is_set():
            try:
                # A LEITURA E' O RELOGIO (2026-11-02). Medido no dono: a varredura
                # da arvore do Chrome inteira por tick punha as decisoes a 1,6-3 s
                # de distancia e o ecra um cue atras. Este numero existe para a
                # proxima regressao ser apanhada por um numero, nao por um olho.
                _t_read = time.monotonic()
                self._yt_phase_start = _t_read
                self._yt_phases = {}
                got, yt_mode = self._read(uia, UIA)
                self.reads += 1
                _ms = (time.monotonic() - _t_read) * 1000.0
                if _ms > 40.0:
                    _now = time.monotonic()
                    if _now - getattr(self, "read_slow_logged", 0.0) > 5.0:
                        self.read_slow_logged = _now
                        log('EXTERNAL_CAPTIONS_READ_MS ms=%.1f phases=%s'
                            % (_ms, getattr(self, '_yt_phases', {})))
            except Exception as exc:  # noqa: BLE001
                self.failures += 1
                if self.failures <= 3:
                    log(f'EXTERNAL_CAPTIONS_READ_FAILED error={exc!r}')
                got, yt_mode = [], False
            _t_tick = time.monotonic()
            try:
                self._tick(got, yt_mode)
            except Exception as exc:  # noqa: BLE001
                self.failures += 1
                if self.failures <= 3:
                    log(f'EXTERNAL_CAPTIONS_TICK_FAILED error={exc!r}')
            self._yt_prof("tick", _t_tick)
            # SEM PLAYER, 10 Hz E' CARGA EMPRESTADA AO JOGO DO DONO
            # (2026-11-03, MEDIDO). Com o player fechado o laco continuava a
            # perguntar 10x/s -- `YOUTUBE_TICK_MS avg=0 max=0 n=49` congelado e
            # 0,1 s de `INTERVAL_S` --, e cada volta resolve a JANELA EM PRIMEIRO
            # PLANO (`GetForegroundWindow` + titulo) para concluir que nao ha'
            # player nenhum. O dono joga com o Sotto a viver: enquanto nao houver
            # leitura de player ha' 5 s, o passo desce para 0,5 s; a primeira
            # leitura que traga qualquer coisa devolve o passo normal, e o custo
            # de detetar um video novo sobe 0,4 s -- que o proprio carregamento
            # do video ja' paga.
            if got or yt_mode:
                self._idle_since = 0.0
            elif not getattr(self, '_idle_since', 0.0):
                self._idle_since = time.monotonic()
            _idle_for = (time.monotonic() - self._idle_since
                         if getattr(self, '_idle_since', 0.0) else 0.0)
            _step = (self.IDLE_INTERVAL_S if _idle_for >= 5.0
                     else self.INTERVAL_S)
            # O CUSTO DO DESENHO TAMBEM E' UM NUMERO (2026-11-03). Com a leitura
            # ja' barata (17 Hz medidos) o laco caiu para 0,5-5 Hz noutros
            # momentos: o que sobra e' `_tick`, que pinta a janela. Sem esta
            # medida a proxima optimizacao seria um palpite.
            try:
                _tk = (time.monotonic() - _t_tick) * 1000.0
                _agg = getattr(self, '_yt_tick_agg', None)
                if _agg is None:
                    _agg = self._yt_tick_agg = [0, 0.0, 0.0, time.monotonic()]
                _agg[0] += 1
                _agg[1] += _tk
                _agg[2] = max(_agg[2], _tk)
                if time.monotonic() - _agg[3] >= 5.0:
                    # Com o player minimizado (ou sem player) este agregado
                    # congela em `n=49, avg=0` e era escrito de 5 em 5 s para
                    # sempre. `log_repeat`: sai quando o numero MUDA.
                    # A DECISAO DO LACO E' UM NUMERO TAMBEM (2026-11-03). Sem
                    # isto, "nao pinta nada" nao tinha endereco: medido nesta
                    # sessao, o laco a 4 Hz com `EXTERNAL_CAPTIONS_READ_MS`
                    # AUSENTE (leitura <40 ms) e nenhuma linha -- ou seja o
                    # caminho saia CEDO e nada dizia por onde.
                    _dgs = getattr(self, '_yt_diag', {})
                    log_repeat('youtube-tick',
                               'YOUTUBE_TICK_MS avg=%.0f max=%.0f n=%d'
                               ' src=%r vid=%r cdp_age_ms=%s rows=%s why=%r'
                               % (_agg[1] / _agg[0], _agg[2], _agg[0],
                                  _dgs.get('src', '?'), _dgs.get('vid', ''),
                                  _dgs.get('age', '?'), _dgs.get('rows', '?'),
                                  _dgs.get('why', '')))
                    _agg[0] = 0
                    _agg[1] = 0.0
                    _agg[2] = 0.0
                    _agg[3] = time.monotonic()
            except Exception:                 # noqa: BLE001
                pass
            # A PALAVRA A PALAVRA NAO CABE NUM INTERVALO DE 300 ms (2026-10-30).
            # O UIA custa, e por isso continua a ser lido a cada `INTERVAL_S`;
            # o que estava caro era o DESENHO. Entre duas leituras o relogio do
            # player e' avancado localmente a partir do ancora da ultima leitura
            # e a linha e' recomposta a `RENDER_S` -- nenhuma chamada Win32, so'
            # `revealed_text` sobre as palavras que ja' se conhecem. Sem isto, o
            # unico instante em que o ecra podia mudar era o do UIA, e uma frase
            # de quatro palavras entrava de uma vez.
            # UM DONO POR VEZ NO ECRA (2026-11-02). Aqui, entre duas leituras,
            # um SEGUNDO produtor (`yt_live_frame`) recompunha a linha a partir da
            # FAIXA e de um relogio interpolado, enquanto a leitura seguinte punha a
            # linha PINTADA pelo player. Os dois alternavam a cada 60-120 ms e o dono
            # viu exactamente isso: *"ficam sumindo e aperecendo ou trocando a atual e
            # a antiga ao mesmo tempo"*. MEDIDO na auditoria: 59 oscilacoes em 13,2 s,
            # com A/B/A/B nos quadros. Quando a PINTURA esta a fornecer a linha, ela e'
            # o unico produtor; o re-render da faixa volta so' se a pintura parar.
            painted_now = (time.monotonic()
                           - getattr(self, "yt_live_paint_at", 0.0)) < 2.0
            if yt_mode and not painted_now:
                deadline = time.monotonic() + self.INTERVAL_S
                while not self.stop_event.is_set():
                    left = deadline - time.monotonic()
                    if left <= 0:
                        break
                    self.stop_event.wait(min(self.RENDER_S, left))
                    if self.stop_event.is_set():
                        break
                    try:
                        frame = self.yt_live_frame()
                    except Exception as exc:  # noqa: BLE001
                        frame = None
                        if self.failures <= 3:
                            log(f'EXTERNAL_CAPTIONS_FRAME_FAILED error={exc!r}')
                    if frame:
                        try:
                            self._tick([frame], True)
                        except Exception as exc:  # noqa: BLE001
                            if self.failures <= 3:
                                log(f'EXTERNAL_CAPTIONS_TICK_FAILED error={exc!r}')
                continue
            self.stop_event.wait(_step)
        self._release('stopped')
        log(f'EXTERNAL_CAPTIONS_WATCH stopped=true reads={self.reads} '
            f'failures={self.failures}')

    def _yt_source_by_title(self, title):
        """A fonte desta janela, decidida por TITULO contra a fonte CDP.

        `document.title` (CDP) contra o titulo da janela (Win32). Devolve a
        URL do video quando os dois casam, e `None` quando nao casa ou quando
        a porta CDP ainda nao tem foto -- aí o chamador segue o caminho antigo.
        MEDIDO 2026-11-03: os 1,5-34 s do laco da legenda estavam TODOS em
        chamadas UIA; nenhuma delas e' precisa para saber que uma janela do
        Chrome esta' a mostrar YouTube.
        """
        src = getattr(self, '_yt_cdp_source', None)
        if src is None:
            return None
        try:
            snap = src.snapshot(max_age=3.0)
        except Exception:                 # noqa: BLE001
            return None
        if not snap:
            return None
        vid = str(snap.get('videoId') or '')
        if not vid:
            return None
        doc = str(snap.get('title') or '').strip().lower()
        win = str(title or '').strip().lower()
        if doc and win and (doc[:40] in win or win[:40] in doc):
            return 'https://www.youtube.com/watch?v=' + vid
        if 'youtube' in win:
            return 'https://www.youtube.com/watch?v=' + vid
        return None

    def _yt_src_resolver_start(self):
        """A thread que responde "que fonte e' esta janela" SEM prender o laco.

        Nasceu de uma medicao no dono (2026-11-03): `phases={'source': 11094.0}`
        num `EXTERNAL_CAPTIONS_READ_MS ms=11094.0` -- onze segundos com a legenda
        congelada enquanto o YouTube seguia. `player_source` e' UIA e pode bloquear
        por segundos quando o Chrome esta' ocupado; o desenho nao pode depender
        disso. Esta thread pergunta de 2 em 2 s e publica em `_yt_src_cache`.
        """
        if getattr(self, '_yt_src_thread', None) is not None:
            return
        import threading as _th

        def _loop():
            try:
                import external_subs as _ext
                UIA2, uia2 = _ext._uia()
            except Exception:                 # noqa: BLE001
                return
            while not self.stop_event.is_set():
                hwnd = int(getattr(self, 'target_hwnd', 0) or 0)
                if hwnd:
                    # O TITULO DECIDE, A ARVORE NAO (2026-11-03). Ver
                    # `_yt_source_by_title`: a mesma pergunta respondida por Win32.
                    src = None
                    try:
                        _t = _ext._window_title(hwnd)
                    except Exception:         # noqa: BLE001
                        _t = ''
                    if _t:
                        src = self._yt_source_by_title(_t)
                        if src is None and getattr(self, '_yt_cdp_source', None) is None:
                            try:
                                src = _ext.player_source(hwnd, uia2, UIA2) or ''
                            except Exception: # noqa: BLE001
                                src = None
                    if src is not None:
                        self._yt_src_cache = (hwnd, src, time.monotonic())
                self.stop_event.wait(2.0)

        self._yt_src_thread = _th.Thread(target=_loop, name='yt-src-resolver',
                                         daemon=True)
        self._yt_src_thread.start()

    def _read(self, uia, UIA):
        # MARCA DE ENTRADA PARA O VIGIA DE LEITURA LENTA (2026-11-03). MEDIDO: a
        # instancia do dono ficou 60 s sem um unico tick e sem uma linha de log --
        # o laco estava dentro de uma leitura e nao havia prova de ONDE. Este
        # campo, lido por `SottoShell._slow_read_monitor`, faz um despejo de
        # pilhas quando a leitura passa de `SLOW_READ_S`. Diagnostico nao cobra
        # nada: e' uma escrita de um float.
        self._in_read_since = time.monotonic()
        try:
            return self._read_inner(uia, UIA)
        finally:
            self._in_read_since = 0.0

    SLOW_READ_S = 3.0

    def _read_inner(self, uia, UIA):
        """What the caption box should show, and whether it is the real track.

        THE YOUTUBE BRANCH IS NOT THE PAGE. MEASURED 2026-10-19 in the
        owner's own log (`_main/webview-run.log`, his session at 19:14): the
        lines that reached the caption box from a YouTube page were
        `Oferta sujeita aos termos. Cancele quando quiser.`, `há 4 sem.` and
        `Thre's a small problem .` -- the PAGE's own text, not the video's
        caption. The owner, verbatim: *"youtube ta mostrando texto burro da
        pagina inves da porra da legenda/transcriptino de um video"*.

        So for a YouTube window the page reader is NOT consulted, and the
        video's OWN caption track is used instead. The page reader stays for
        Stremio, where the player PAINTS the caption -- there the page IS
        the caption.

        RETURNS `(got, yt_mode)`.
        """
        import external_subs
        _t_all = time.monotonic()
        hwnd = self._target_window(uia, UIA)
        _yt_mark(self, 'target')
        self._yt_prof("target", _t_all)
        if not hwnd:
            return [], False
        _t_src = time.monotonic()
        # QUEM E' A FONTE NAO SE PERGUNTA 20x POR SEGUNDO (2026-11-03, MEDIDO).
        # `player_source` le' o URL da janela pela arvore de acessibilidade e
        # custa 60-140 ms -- e uma vez nesta sessao **6,8 s**
        # (`EXTERNAL_CAPTIONS_READ_MS ms=6797.0`), tempo em que a legenda inteira
        # parou. A resposta so' muda quando muda a JANELA `hwnd` (que e' barato de
        # ler) ou quando a pagina navega -- e a navegacao invalida a foto da CDP,
        # logo `_yt_snap_video()` deixa de responder e voltamos a perguntar.
        source = ''
        _cache = getattr(self, '_yt_src_cache', None)
        if _cache and time.monotonic() - _cache[2] <= 6.0:
            source = _cache[1]
        # A PERGUNTA A' ARVORE DE ACESSIBILIDADE NAO BLOQUEIA O DESENHO (2026-11-03).
        # MEDIDO no dono, com o video a tocar: `EXTERNAL_CAPTIONS_READ_MS
        # ms=11094.0 phases={'source': 11094.0}` -- e o ecra ficou com a linha
        # congelada enquanto o YouTube seguia (a imagem dele: o Sotto parado numa
        # frase que o player ainda nem tinha mostrado). O cache so' valia 2 s e so'
        # com a foto frescoa; quando a foto envelhecia (a fonte empurrada pela
        # propria espera) o laco pagava a chamada inteira e voltava a empurrar. Agora
        # quem pergunta e' uma thread propria (`_yt_src_resolver`), e este laco le'
        # a ultima resposta. Uma resposta de 6 s atras ainda diz a VERDADE sobre
        # quem e' a fonte: janela que muda de player muda de hwnd, e o resolver
        # re-pergunta de 2 em 2 s.
        if _cache is None:
            source = ''
        self._yt_src_resolver_start()
        loc = source
        # A PORTA DA CDP E' IDENTIDADE, NAO SUSPEITA (2026-11-03): com o Chrome
        # atras de outra janela o resolver respondia '' e o laco caia na varredura
        # generica (1,1 s por volta). Uma aba `youtube.com/watch` e' prova
        # positiva, independente de quem esta' em primeiro plano.
        if not source:
            _cdp_src = getattr(self, '_yt_cdp_source', None)
            if _cdp_src and _cdp_src is not False:
                # A LISTA DE ABAS E' HTTP, NAO WEBSOCKET (2026-11-03): a foto
                # depende do `Runtime.evaluate`, que numa aba em segundo plano
                # fica `slow (WebSocketTimeoutException)`; `/json/list` responde
                # sempre, e `youtube.com/watch?v=` ali e' a prova da fonte.
                try:
                    _tabvid = _cdp_src.target_video_id()
                except Exception:             # noqa: BLE001
                    _tabvid = ''
                if _tabvid:
                    source = 'external:youtube'
                    if _tabvid != getattr(self, 'yt_video_id', ''):
                        _yt_mark(self, 'source-tab')
                    loc = source
                    log_repeat('YOUTUBE_SOURCE_BY_CDP',
                               'YOUTUBE_SOURCE_BY_CDP video_id=%s'
                               % _tabvid, every_s=60.0)
        # DUAS FORMAS DO MESMO NOME (2026-11-03, MEDIDO AO VIVO). O resolvedor
        # publica `_yt_source_by_title`, que devolve a URL
        # (`https://www.youtube.com/watch?v=...`), e o ramo do YouTube compara com
        # `'external:youtube'`. Com a porta CDP ligada, essa URL era o valor
        # unico: o ramo do YouTube NAO rodava, e a varredura generica tambem nao
        # (a foto estava fresca) -- medido nesta sessao,
        # `YOUTUBE_TICK_MS src='https://www.youtube.com/watch?v=Rgx8dpiPwpA'
        # why='cdp-fresh-skip'` a 4 Hz, com tres linhas pintadas no player e NADA
        # no Sotto. A URL e' a mesma afirmacao; passa a ter o mesmo nome.
        if source and 'youtube.com/watch' in str(source):
            source = 'external:youtube'
        _yt_mark(self, 'source')
        loc = source
        self._yt_prof("source", _t_src)
        if source == 'external:youtube':
            if os.environ.get("SOTTO_YT_CPROFILE") == "1":
                import cProfile, pstats
                _prof = cProfile.Profile()
                _prof.enable()
            try:
                lines, urgent = self._youtube(hwnd, uia, UIA)
                # A FASE QUE NAO TINHA NOME (2026-11-03). `EXTERNAL_CAPTIONS_READ_MS
                # ms=1250.0 phases={'target': 109.0, 'source': 109.0}`: o unico
                # numero grande era o TOTAL, e a diferenca caia toda dentro desta
                # chamada sem um marco que a partisse. `youtube` fecha a conta.
                _yt_mark(self, 'youtube')
                self._yt_prof("youtube", _t_src)
                # UM PRODUTOR POR VEZ (2026-11-03, MEDIDO). Quando a leitura
                # forneceu linhas, o re-render da faixa a 60 ms tem de CALAR: os
                # dois alternavam no mesmo ecra (log: `src=...track` e
                # `src=...liveframe` a cada 150 ms, com janelas diferentes), que e'
                # o defeito que o dono descreveu como *"trocando a atual e a antiga
                # ao mesmo tempo"*. O liveframe passa a ser so' o que preenche um
                # silencio de leitura.
                if lines:
                    self.yt_live_paint_at = time.monotonic()
            finally:
                if os.environ.get("SOTTO_YT_CPROFILE") == "1":
                    _prof.disable()
                    self._yt_calls = int(getattr(self, "_yt_calls", 0)) + 1
                    if self._yt_calls % 20 == 1:
                        try:
                            with open(os.path.join(os.path.dirname(__file__), "..", "..",
                                                     "_main", "_yt-cprofile.txt"), "w") as _fh:
                                pstats.Stats(_prof, stream=_fh).sort_stats(
                                    "cumulative").print_stats(28)
                        except Exception:  # noqa: BLE001
                            pass
            if urgent:
                # NO TRACK: the ASR is the base and it comes back NOW. The
                # owner's rule, verbatim: *"se for um video sem legenda, vaio
                # transcrever ao vivo igual."*
                self._release('youtube-no-track')
            return lines, True
        # A PORTA CDP ABERTA NAO CAI NA LEITURA GENERICA DA PAGINA (2026-11-03).
        # MEDIDO com o despejo novo (`caption-read-slow`): o laco passou 24 s em
        # `external_subs.caption_lines(hwnd, uia, UIA)` -- a varredura UIA da
        # PAGINA inteira, que e' a rede para players que nao sao Chrome. Com a
        # porta aberta o YouTube ja' tem um leitor proprio e esta' varredura so'
        # compra segundos: o tick devolve nada e a foto seguinte (80 ms) desenha.
        _cdp = getattr(self, '_yt_cdp_source', None)
        if _cdp and _cdp is not False:
            # ... MAS UMA PORTA MUDA NAO DEIXA O ECRA VAZIO (2026-11-03).
            # MEDIDO: `YOUTUBE_CDP_HEALTH age=None ... reads=0` por mais de um
            # minuto com a fonte `attached` -- uma ligacao que nunca publica.
            # Com a leitura generica desligada isso era 1 frame em 70 s: o dono
            # ficava sem legenda nenhuma. Muda ha' 8 s, a rede volta.
            try:
                _age = _cdp.snapshot_age()
            except Exception:                 # noqa: BLE001
                _age = None
            self._yt_diag = {'src': loc or '?', 'vid': getattr(self, 'yt_video_id', ''),
                             'age': ('%.0f' % (_age * 1000.0)) if _age is not None else 'None',
                             'rows': len(getattr(self, 'yt_cdp_rows', None) or []),
                             'why': 'cdp-fresh-skip'}
            if _age is not None and _age <= 8.0:
                return [], False
        # A VARREDURA DA PAGINA INTEIRA E' PARA QUEM PINTA A LEGENDA NA PAGINA
        # (2026-11-03, MEDIDO AO VIVO — e' a queixa do dono, verbatim: *"uma
        # porra de extrair legenda do youtube e dar display na minha tela nao
        # era pra ser nem o minimo de pesado"*).
        #
        # O QUE ESTAVA A ACONTECER (pid 49892, 10:41; Chrome aberto, nada a
        # tocar, painel fechado): cada leitura varria a arvore UIA da PAGINA
        # inteira — 55 ms de CPU MEDIDOS (`external_subs.caption_lines` sobre a
        # janela do Chrome: 62 / 31 / 16 ms em tres chamadas seguidas) — quatro
        # vezes por segundo, para concluir que nao ha legenda nenhuma numa
        # pagina que nao e' um player. Custo medido: `EXTERNAL_CAPTIONS_READ_MS
        # ms=765..1547` sem parar e **22 % de um nucleo** na shell em REPOUSO.
        #
        # A varredura existe por UMA razao: players que PINTAM a legenda na
        # propria pagina (Stremio/Electron). Isso e' uma IDENTIDADE POSITIVA, e
        # `player_source` ja' a devolve — entao a varredura passa a exigir essa
        # identidade em vez de acontecer por omissao. Fonte desconhecida (toda a
        # janela que nao e' player) nao paga nada; a rede fica a uma varredura de
        # 5 em 5 s, que e' o tecto do atraso para um pintor que o catalogo ainda
        # nao conheca.
        if source != 'external:stremio':
            _now = time.monotonic()
            if _now - getattr(self, '_page_scan_at', 0.0) < 5.0:
                self._page_scan_skipped = int(getattr(self, '_page_scan_skipped', 0)) + 1
                return [], False
            self._page_scan_at = _now
            self._page_scan_scanned = int(getattr(self, '_page_scan_scanned', 0)) + 1
            log_repeat('PAGE_SCAN_NET',
                       'PAGE_SCAN_NET source=%r scanned=%d skipped=%d why=a varredura '
                       'da pagina e so para quem pinta a legenda na pagina (Stremio); '
                       'o resto nao paga 55 ms'
                       % (source, self._page_scan_scanned,
                          int(getattr(self, '_page_scan_skipped', 0))), 60.0)
        return external_subs.caption_lines(hwnd, uia, UIA), False

    def _target_window(self, uia, UIA):
        """The window we read: the foreground player, or the one we had.

        THE FOREGROUND WINDOW IS ONLY ADOPTED IF IT IS A PLAYER. A window
        that is not a player must not steal the handle, or alt-tabbing to
        the editor would drop the captions; the window we were reading is
        remembered so the captions do not vanish the moment the owner
        presses Alt+C (Sotto becomes foreground) or switches to another app.
        """
        # UM ALVO FIXO PARA A LANE MEDIR SEM TOCAR NO ECRA DO DONO (2026-11-03).
        # `SOTTO_YT_TARGET_HWND` existe SO' para instrumento: sem ela o
        # comportamento e' exactamente o de antes (a janela em primeiro plano,
        # ou a que ja' se lia). Uma lane que precisa de medir o caminho do
        # YouTube nao pode depender de o Chrome estar em primeiro plano.
        _forced = os.environ.get('SOTTO_YT_TARGET_HWND', '').strip()
        if _forced:
            try:
                # O RESOLVEDOR DE FONTE LE' `target_hwnd` (2026-11-03): sem
                # esta linha o alvo fixo devolvia o hwnd mas a thread que
                # pergunta "que fonte e' esta janela" ficava com 0 e nunca
                # respondia -- medido, `cdp: []` e nenhum `YOUTUBE_CDP_SOURCE`
                # num arranque com alvo fixo.
                self.target_hwnd = int(_forced, 0)
                return self.target_hwnd
            except ValueError:
                pass
        import external_subs
        # O ALVO NAO SE REDECIDE 25x POR SEGUNDO (2026-11-03, MEDIDO).
        # `EXTERNAL_CAPTIONS_READ_MS phases={'target': 47..172}` repetido: a
        # leitura da janela e' de microssegundos, mas DECIDIR A FONTE custa
        # 46-63 ms. Uma pergunta que so' muda quando muda a janela nao precisa
        # da resposta a cada 40 ms: 200 ms de validade e' mais rapido do que
        # qualquer olho distingue uma troca de janela.
        _tc = getattr(self, '_target_cache', None)
        if _tc and time.monotonic() - _tc[0] <= 0.2:
            return _tc[1]
        fg = int(ctypes.windll.user32.GetForegroundWindow() or 0)
        if fg:
            try:
                title = str(external_subs._window_title(fg) or '').strip().lower()
            except Exception:
                title = ''
            if not title.startswith('sotto'):
                # O VEREDICTO "ESTA JANELA E' UM PLAYER" FICA 2 s (2026-11-03,
                # MEDIDO). Perguntar isto a' arvore de acessibilidade em cada um
                # dos ~20 ticks custa 60-140 ms e uma vez custou **6,8 s**
                # (`EXTERNAL_CAPTIONS_READ_MS ms=6797.0`): seis segundos em que a
                # legenda nao mudou porque o laco estava preso a' espera do Chrome.
                # A chave e' (janela, titulo) -- ambos lidos por Win32 em
                # microssegundos, e navegar muda o titulo.
                _fc = getattr(self, '_yt_fg_cache', None)
                # SEIS SEGUNDOS, NAO DOIS (2026-11-03). MEDIDO no dono:
                # `EXTERNAL_CAPTIONS_READ_MS ms=1579.0 phases={'target': 1579.0}`
                # repetido -- a chamada UIA levou 1,6 s e, com um cache de 2 s, o
                # laco pagava-a a cada dois segundos, ou seja metade do tempo com a
                # legenda parada enquanto ela ja' estava no ecra. A chave e'
                # (janela, TITULO): navegar muda o titulo em microssegundos, logo o
                # cache longo nao atrasa uma troca de video -- so' deixa de
                # re-perguntar o que ainda nao mudou.
                _fast = self._yt_source_by_title(title)
                if _fast is None:
                    # UMA FOTO VELHA DA CDP DIZ MAIS DO QUE A UIA (2026-11-03):
                    # o cache do veredicto expirava a cada 6 s e o laco pagava
                    # 1,4 s de UIA (0,4 Hz). A porta ligada a uma aba do YouTube
                    # nao muda por a foto envelhecer.
                    _cdp_src = getattr(self, '_yt_cdp_source', None)
                    if _cdp_src and _cdp_src is not False:
                        try:
                            _old = _cdp_src.snapshot(max_age=30.0)
                        except Exception:     # noqa: BLE001
                            _old = None
                        if _old and _old.get('videoId'):
                            _fast = ('https://www.youtube.com/watch?v='
                                     + str(_old.get('videoId')))
                if _fast is not None:
                    # A JANELA E' O PLAYER SEM PERGUNTAR A' ARVORE (2026-11-03).
                    # A fonte CDP ja' sabe o titulo do documento e o id do video;
                    # comparar o titulo da janela (Win32, microssegundos) com o
                    # do documento dispensa a chamada UIA que mediu 1,5 s, 6,8 s
                    # e um dia 34 s. A UIA fica so' para quando a porta CDP nao
                    # existe.
                    src = _fast
                    self._yt_fg_cache = (fg, title, src, time.monotonic())
                elif (_fc and _fc[0] == fg and _fc[1] == title
                        and time.monotonic() - _fc[3] <= 6.0):
                    src = _fc[2]
                else:
                    # A ARVORE DE ACESSIBILIDADE NAO SE ABRE POR QUALQUER JANELA
                    # (2026-11-03, MEDIDO). `player_source` so' pode responder
                    # "player" por TITULO (precisa de um browser) ou por URL
                    # (que aqui ainda nao existe): as duas provas se decidem
                    # com o titulo e o NOME DO PROCESSO, ambos Win32 em
                    # microssegundos. Perguntar a' UIA primeiro custou 29 s numa
                    # unica leitura (`EXTERNAL_CAPTIONS_READ_MS ms=28953.0
                    # phases={'target': 28953.0}`) -- e esses 29 s NAO SAO SO'
                    # DO LEITOR: a chamada COM segura o GIL, e o observador do
                    # Ctrl+Space, que roda a 25 ms, ficou 29,3 s sem correr
                    # (`HOTKEY_OBSERVER_ALIVE max_gap_ms=29266`), logo as
                    # pressoes do dono nesse intervalo nao existiram para a app.
                    # O jogo dele, o editor e o Explorer nao tem "youtube" nem
                    # "stremio" no titulo nem no nome: a UIA nunca e' chamada.
                    try:
                        _proc = external_subs._process_name(fg)
                    except Exception:
                        _proc = ''
                    _tl = str(title or '').lower()
                    if ('youtube' in _tl or 'stremio' in _tl
                            or 'stremio' in str(_proc or '').lower()
                            or not _proc):
                        # `not _proc` = nao se sabe quem e' a janela: ai a
                        # pergunta cara volta a ser feita, porque uma janela
                        # desconhecida pode ser um player que a CDP nao ve.
                        try:
                            src = external_subs.player_source(fg, uia, UIA)
                        except Exception:
                            src = ''
                    else:
                        src = ''
                    self._yt_fg_cache = (fg, title, src, time.monotonic())
                if src:
                    self.target_hwnd = fg
                    self._target_cache = (time.monotonic(), fg)
        if not self.target_hwnd or not ctypes.windll.user32.IsWindow(
                wt.HWND(self.target_hwnd)):
            # NO WINDOW IN THE FOREGROUND (or the one we had is gone). The
            # video window may still be OPEN, just behind another one.
            # MEASURED 2026-10-20: the owner's YouTube window was open and
            # findable by title while the foreground was a different Chrome
            # tab, and the caption only started after he clicked his
            # browser. The reader looks for a player among the OPEN windows
            # so the caption does not depend on where he is looking.
            try:
                found = external_subs.find_player_window()
            except Exception:
                found = 0
            if found:
                self.target_hwnd = int(found)
        if self.target_hwnd and ctypes.windll.user32.IsWindow(
                wt.HWND(self.target_hwnd)):
            # A RESPOSTA FICA EM CACHE, VENHA DE ONDE VIER (2026-11-03,
            # MEDIDO). `_target_cache` so' era escrito no ramo "a janela em
            # primeiro plano E' o player"; com o JOGO em primeiro plano e a
            # janela do YouTube lembrada, a funcao refazia a decisao inteira
            # (titulo, fonte CDP, `find_player_window`) em CADA tick de 40 ms --
            # `EXTERNAL_CAPTIONS_READ_MS phases={'target': 47..63}` repetido, e
            # o laco externo a gastar **95,6 % de um nucleo** (medido por
            # `GetThreadTimes` no pid 28044, 5 s de amostra: uma thread em
            # 95,6 %, as outras abaixo de 8 %). O cache de 200 ms e' o MESMO
            # numero do ramo de cima, com a MESMA razao: a janela nao muda a
            # 25 Hz.
            self._target_cache = (time.monotonic(), int(self.target_hwnd))
            return int(self.target_hwnd)
        self.target_hwnd = 0
        return 0

    def _yt_rows(self, painted, hwnd=None, uia=None, UIA=None):
        _t0 = time.monotonic()
        try:
            return self._yt_rows_impl(painted, hwnd=hwnd, uia=uia, UIA=UIA)
        finally:
            self._yt_prof("rows", _t0)

    #: QUANTO TEMPO UMA MUDANCA DE LINHAS TEM DE SE AGUENTAR (2026-11-02). A caixa
    #: do player tem 2-3 linhas e ele ROLA a mais antiga para fora enquanto a nova
    #: cresce; nesse instante ele desenha 3 linhas e volta a 2. MEDIDO no log do
    #: dono (auditoria de 23:07): 3<->2 a cada 60-500 ms com a MESMA ultima linha,
    #: e e' isso que ele chama *"ficando sumindo e aperecendo"*. Crescer e'
    #: imediato (e' o que o player esta a escrever); ENCOLHER ou ROLAR espera.
    ROWS_SETTLE_S = 0.28

    def _yt_rows_is_player_step(self, rows, shown):
        """A mudanca e' o PROPRIO passo do player (escrever, rolar, largar)?

        MEDIDO 2026-11-03 contra a legenda viva (instrumento
        `_main/_yt-live-latency.py`, 45 s a tocar, video `I5NztYu4HL8`):
        53 mudancas de linhas no player, 6 reproduzidas, 47 perdidas, 23 quadros
        do Sotto com texto que o player ja' tinha deixado para tras. A histerese
        de 280 ms e' metade desse numero: um ROLAR legitimo -- o player empurra
        a linha velha para fora e a nova cresce -- ficava retido, e o ecra
        mostrava o instante anterior enquanto o player ja' estava no seguinte.

        Os tres passos que o player faz, e que agora passam NO MESMO tick:
          * **cresceu**: mesma cabeca, a ultima linha alonga-se;
          * **rolou**: as linhas subiram uma posicao (a primeira saiu da caixa)
            e a ultima cresceu;
          * **largou o fim**: as linhas de cima ficaram e a ultima saiu.
        O que continua a esperar 280 ms e' so' uma mudanca que nao e' nenhum
        destes -- uma permuta ou um encolher do MEIO, que nao e' um passo do
        player e por isso pode ser um quadro transitorio da leitura.
        """
        rows = list(rows or ())
        shown = list(shown or ())
        if not rows or not shown:
            return False
        count = len(rows)
        # escrever: cabeca igual, ultima linha alonga-se
        if (count == len(shown) and rows[:-1] == shown[:-1]
                and rows[-1].startswith(shown[-1])):
            return True
        # rolar: as de baixo subiram uma posicao e a primeira saiu da caixa. A
        # linha nova pode CONTINUAR a que estava (`startswith`) ou ser um cue
        # novo -- as duas sao o passo do player; o que nao passa e' uma cabeca
        # que nao casa, que so' pode ser um quadro transitorio da leitura.
        if count <= len(shown) and rows[:-1] == shown[1:count]:
            return True
        # largar o fim: as de cima ficaram
        if count < len(shown) and rows == shown[:count]:
            return True
        return False

    def _yt_rows_settle(self, rows):
        """Histerese das LINHAS: um passo do player passa ja', o resto insiste.

        A regra, medida em 2026-11-02 contra o log:
          * as linhas CRESCERAM (a ultima e' um alongamento da que estava) -> adoptar
            no mesmo tick, porque e' o player a escrever;
          * qualquer outra mudanca (rolar a velha para fora, 3 -> 2, 2 -> 1) -> so'
            depois de `ROWS_SETTLE_S` com a MESMA proposta. Um quadro transitorio
            do player nao chega ao ecra dele.

        E o que mudou em 2026-11-03: o ROLAR e o LARGAR tambem sao passos do
        player, e nao quadros transitorios da leitura -- ver
        `_yt_rows_is_player_step` para a medicao que o obrigou.
        """
        rows = [str(r) for r in (rows or ()) if str(r).strip()]
        shown = getattr(self, "yt_rows_shown", None)
        if shown is None or rows == shown:
            self.yt_rows_shown = rows
            self.yt_rows_pending = None
            return rows
        if self._yt_rows_is_player_step(rows, shown):
            self.yt_rows_shown = rows
            self.yt_rows_pending = None
            return rows
        pending = getattr(self, "yt_rows_pending", None)
        now = time.monotonic()
        if pending is None or pending[0] != rows:
            self.yt_rows_pending = (rows, now)
            return list(shown)
        if now - pending[1] >= self.ROWS_SETTLE_S:
            self.yt_rows_shown = rows
            self.yt_rows_pending = None
            return rows
        return list(shown)

    def _yt_rows_impl(self, painted, hwnd=None, uia=None, UIA=None):
        """As linhas a desenhar: o que o player pintou, NAS LINHAS dele.

        UMA FONTE, UMA FOTO (2026-11-02). Aqui havia DUAS leituras -- nomes no
        tick e os rects numa segunda chamada quando o texto mudava -- e o desenho
        saia de duas fotos diferentes: *"ficam sumindo e aperecendo ou trocando a
        atual e a antiga ao mesmo tempo"*, verbatim do dono. Agora `_youtube_painted`
        faz UMA leitura (nomes + rects, reaproveitando o rect de cada filho que nao
        mudou) e esta funcao so' traduz ESSA foto em linhas.
        """
        _t0 = time.monotonic()
        try:
            cdp_rows = getattr(self, 'yt_cdp_rows', None)
            if cdp_rows is not None:
                # A FOTO DA CDP E' A DO PLAYER, LINHA A LINHA (2026-11-03): nao se
                # reagrupa e nao se retem. A histerese de 280 ms existe para
                # esconder TRANSITORIOS DA NOSSA LEITURA; um quadro que veio do DOM
                # do player e' o que ele esta' a mostrar, inclusive a rolagem.
                self.yt_cdp_rows = None
                self.yt_live_paint_at = time.monotonic()
                return list(cdp_rows)
            import youtube_window as _ytw
            rows = _ytw.painted_rows(painted, getattr(self, 'yt_paint_items', None))
            if os.environ.get("SOTTO_YT_PROFILE") == "1" and painted and not rows:
                self._yt_prof("rows-empty", _t0, "painted=%r items=%r"
                              % (painted[:6], (getattr(self, "yt_paint_items", None) or [])[:3]))
            settled = self._yt_rows_settle(rows)
            if settled:
                self.yt_live_paint_at = time.monotonic()
            if os.environ.get("SOTTO_YT_PROFILE") == "1" and settled != rows:
                self._yt_prof("rows-hold", _t0, "cand=%r shown=%r" % (rows, settled))
            return settled
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_PAINT_ROWS_FAILED error={exc!r}')
            return []

    def _yt_words_pool(self, track, t=None):
        """As palavras da faixa servida, uma vez por faixa (nao por tick).

        O laco de pintura corre a cada ~60 ms: varrer 1436 cues por tick seria
        trabalho a mais no fio da shell. A faixa e' um objecto novo quando muda
        (`youtube_track_thread` reconstroi), por isso a identidade basta como
        chave -- nunca um `id` reciclado nem uma data de cache.
        """
        cached = getattr(self, '_yt_pool', None)
        if cached and cached[0] is track:
            return cached[1]
        try:
            import youtube_window as _ytw
            pool = _ytw.track_words(track.get('cues') or ())
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_WORDS_POOL_FAILED error={exc!r}')
            pool = set()
        self._yt_pool = (track, pool)
        return pool

    def _youtube_painted(self, hwnd, uia, UIA):
        """The words the player is painting RIGHT NOW -> [] when there are none.

        READ-ONLY: it opens nothing, clicks nothing, moves nothing.

        The reason is logged when it CHANGES, so "the captions are off" is
        never confused with "the player is between cues".
        """
        try:
            import youtube_captions
            _t0 = time.monotonic()
            # SEM RECTS NO TICK (2026-11-02): cada rect e' uma chamada fora do
            # processo, e uma cue tem 12-18 filhos -- MEDIDO 62-125 ms por leitura,
            # que era o relogio da legenda. O rect e' lido quando o TEXTO MUDA
            # (`_yt_rows`), nao em cada tick.
            # UMA FOTO POR TICK, COM OS RECTS DELA (2026-11-02). O dono viu a
            # legenda *"flickando"*, *"sumindo e aperecendo ou trocando a atual e a
            # antiga ao mesmo tempo"*: a leitura barata (so' nomes) montava as linhas
            # com os RECTS do tick anterior, e o desenho alternava entre duas
            # geometrias.
            #
            # E O RECT NAO SE REAPROVEITA DE OUTRA FOTO (2026-11-03). O
            # reaproveitamento por indice existia para poupar 4 ms por filho e
            # custou a 1:1: numa ROLAGEM o player mantem as mesmas palavras em
            # indices diferentes, a palavra que sobreviveu no mesmo indice ja'
            # mudou de LINHA, e `rows_from_items` agrupava pelo `left` com a
            # geometria do instante anterior -- palavras certas, ordem trocada.
            # MEDIDO com `_main/_yt-live-latency.py`: 20 de 32 quadros errados
            # desse tipo. Agora cada leitura traz os rects DELA, so' os dela.
            # A CDP E' A FONTE PRIMARIA QUANDO EXISTE (2026-11-03, MEDIDO).
            # A leitura pela arvore de acessibilidade custa 62-110 ms por tick e
            # le o que o Chrome EXPOE -- inclusive o no' antigo e o novo enquanto
            # a cue vira, que e' a origem medida das linhas `['a', 'a a resposta
            # em cima do Sniper']`. A CDP lê o DOM do player: 10 ms, as linhas
            # que ele tem, e sem nos fantasmas. A UIA continua a ser a rede:
            # quando a porta nao responde, o caminho antigo corre igual.
            snap = self._yt_cdp_snapshot(hwnd, uia, UIA,
                                        declared=getattr(self, 'yt_video_id', '') or None)
            if snap is not None:
                # AS LINHAS VEM PRONTAS DO DOM (2026-11-03). O `.caption-visual-line`
                # E' a linha que o player desenhou: reagrupar por `mid` so' pode
                # estragar -- e estragou, medido: `['a affliction ali ja' pronto ali
                # do']` onde o player tem `['a larocache. affliction ali tem ja'
                # pronto uma rift']`. Com o snapshot a decisao de quebra de linha
                # deixa de ser nossa.
                self.yt_cdp_rows = list(snap['rows'])
                # `words` SAO PALAVRAS nos dois caminhos (2026-11-03). A arvore
                # de acessibilidade expoe um no' por PALAVRA; o DOM expoe um por
                # LINHA (`ytp-caption-segment`). Alinhamento e revelacao contam
                # palavras, por isso a linha parte-se aqui -- senao o mesmo
                # instante tinha 20 'palavras' por uma fonte e 2 pela outra, e o
                # desenho alternava entre as duas geometrias.
                got = {'words': [w for line in snap['rows'] for w in line.split()],
                       'items': snap['items'], 'why': 'cdp'}
            elif getattr(self, '_yt_cdp_source', None) is not None:
                # A PORTA ESTA' ABERTA MAS A FOTO AINDA NAO CHEGOU (2026-11-03).
                # MEDIDO no dono: `EXTERNAL_CAPTIONS_READ_MS ms=18921.0
                # phases={'painted': 17843.0}` no primeiro tick depois de a fonte
                # CDP ficar `attached` -- a foto da'None enquanto aquece, o ramo
                # antigo caia na arvore de acessibilidade e a leitura de palavras
                # levou DEZASSETE SEGUNDOS com o video em pausa (pagina calma, e a
                # chamada UIA prende na mesma). Com a porta aberta a UIA ja' nao e'
                # a rede: as linhas do ultimo snapshot continuam validas e a foto
                # seguinte chega em 80 ms.
                got = {'words': [w for line in (getattr(self, 'yt_cdp_rows', None) or [])
                                 for w in line.split()],
                       'items': [], 'why': 'cdp-stale'}
                # UM APAGAO DE 40 s TEM DE DIZER PORQUE (2026-11-03). MEDIDO no
                # log do dono: as linhas do YT_FRAME saltam de 03:11:32 para
                # 03:12:12 com o video a andar -- 40 s de ecra parado e nada no
                # log que nomeie a causa. Esta linha publica, de 2 em 2 s, a
                # IDADE da foto e o que a fonte diz de si mesma.
                _h = time.monotonic()
                if _h - getattr(self, '_yt_stale_logged', 0.0) > 2.0:
                    self._yt_stale_logged = _h
                    _src = getattr(self, '_yt_cdp_source', None)
                    _age = None
                    try:
                        _age = round(_src.snapshot_age(), 2)
                    except Exception:         # noqa: BLE001
                        pass
                    _st = {}
                    try:
                        _st = _src.stats()
                    except Exception:         # noqa: BLE001
                        pass
                    log('YOUTUBE_CDP_HEALTH age=%s stats=%r' % (_age, _st))
            else:
                self.yt_cdp_rows = None
                got = youtube_captions.painted_words(uia, UIA, hwnd=hwnd,
                                                     with_rect=True)
            if got and got.get("items"):
                self.yt_paint_items = got["items"]
            self._yt_prof("paint", _t0)
            if os.environ.get("SOTTO_YT_PROFILE") == "1":
                self._yt_prof("words", _t0, "why=%s n=%d words=%r"
                              % (got.get("why") if isinstance(got, dict) else "?",
                                 len((got or {}).get("words") or ()),
                                 ((got or {}).get("words") or [])[:14]))
            # A LEITURA E' O RELOGIO DA LEGENDA (2026-11-02). MEDIDO no log do
            # dono antes do cache da janela: decisoes de pintura a 1,6-3 s de
            # distancia, porque cada leitura varria a arvore do Chrome inteira.
            # Este numero e' o que prova a cura -- um log que so' aparece quando
            # doi', e no maximo a cada 5 s.
            _ms = (time.monotonic() - _t0) * 1000.0
            if _ms > 50.0:
                _now = time.monotonic()
                if _now - getattr(self, 'yt_read_slow_logged', 0.0) > 5.0:
                    self.yt_read_slow_logged = _now
                    log('YOUTUBE_PAINT_READ_MS ms=%.1f' % _ms)
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_PAINT_READ_FAILED error={exc!r}')
            return []
        words = got.get('words') or []
        # OS RECTS SÃO A QUEBRA DE LINHA DO PLAYER (2026-11-02): guardam-se aqui
        # para `_yt_rows` compor as MESMAS linhas que ele desenhou, sem re-quebrar.
        self.yt_paint_items = got.get('items') or []
        why = str(got.get('why') or '')
        if why != self.yt_paint_why:
            self.yt_paint_why = why
            log(f'YOUTUBE_PAINT_STATE why={why} words={len(words)}')
        # A LEGENDA PODE PARAR COM O PLAYER A PINTAR (2026-11-03, MEDIDO).
        # Durante uma medicao, o video tocava (`CDP` com `rows` preenchidas) e
        # a arvore de acessibilidade do Chrome deixou de expor os filhos da
        # janela de legenda: 4 minutos sem um unico `YOUTUBE_CAPTION` e sem uma
        # unica linha de log a dizer porque -- a leitura continuava a 62-110 ms,
        # vazia. Um cliente UIA NOVO, noutro processo, tambem veio vazio, o que
        # poe o piso no Chrome e nao no Sotto. O que faltava era o NOME da
        # paragem: esta linha diz ha' quanto tempo a pintura esta' vazia, uma
        # vez por 5 s, e o silencio deixa de ser um estado nao escrito.
        _now = time.monotonic()
        if words:
            self.yt_paint_stall_since = None
        elif why.startswith('no-painted-caption'):
            since = getattr(self, 'yt_paint_stall_since', None)
            if since is None:
                self.yt_paint_stall_since = _now
            elif _now - getattr(self, 'yt_paint_stall_logged', 0.0) > 5.0:
                self.yt_paint_stall_logged = _now
                log('YOUTUBE_PAINT_STALL seconds=%.1f why=%s'
                    % (_now - since, why))
        return words

    def _yt_cdp_ensure(self, declared=None):
        """A fonte CDP viva, criada AQUI e nao escondida no leitor da foto.

        MEDIDO 2026-11-03, no banco `_main/yt-read-live-bench.py`: a fonte so'
        nascia dentro de `_yt_cdp_snapshot`, que so' corre DEPOIS de o id do
        video ser lido -- e o id era lido pela ARVORE (94-109 ms num tick bom,
        dezenas de segundos num mau). Quando a varredura UIA falhava, o
        `_youtube` saia em `no-video-id` e a porta CDP nunca chegava a abrir:
        o caminho barato existia e nao era alcancavel. Agora a porta abre
        primeiro e o id vem dela.
        """
        if os.environ.get('SOTTO_YT_CDP', '1') == '0':
            return None
        source = getattr(self, '_yt_cdp_source', None)
        if source is False:
            return None
        if source is not None:
            if declared:
                try:
                    source.set_video_id(declared)
                except Exception:             # noqa: BLE001
                    pass
            return source
        try:
            import youtube_cdp_source
        except Exception as exc:  # noqa: BLE001
            log('YOUTUBE_CDP_SOURCE import_failed=%r' % (exc,))
            self._yt_cdp_source = False
            return None
        source = youtube_cdp_source.CdpCaptionSource(log=log)
        self._yt_cdp_source = source
        if declared:
            try:
                source.set_video_id(declared)
            except Exception:                 # noqa: BLE001
                pass
        try:
            source.start()
        except Exception as exc:  # noqa: BLE001
            log('YOUTUBE_CDP_SOURCE start_failed=%r' % (exc,))
            self._yt_cdp_source = False
            return None
        return source

    def _yt_cdp_snapshot(self, hwnd, uia, UIA, declared=None):
        """A legenda do player pela CDP do Chrome, quando a arvore nao a tem.

        Devolve o snapshot (`rows`/`items`) ou None. Recusa-se a ler quando a
        aba da CDP mostra OUTRO video que nao o que o Sotto declarou ler: com
        duas abas `watch` abertas isso seria mostrar a legenda de um video no
        ecra do outro -- o erro que a `open_socket(video_id=)` do instrumento
        ja' cometeu uma vez em 2026-11-03 e que deu um veredicto inteiro errado.
        """
        if os.environ.get('SOTTO_YT_CDP', '1') == '0':
            return None
        source = self._yt_cdp_ensure()
        if not source:
            return None
        # O ID JA' FOI LIDO NESTE TICK, UM ANDAR ACIMA (2026-11-03, MEDIDO).
        # `_youtube` pergunta-o primeiro e guarda-o em `self.yt_video_id`; reler
        # aqui a' arvore de acessibilidade era um segundo preco de 94-109 ms por
        # tick -- medido `phases={'vid': 109.0, 'declared': 109.0, 'painted':
        # 109.0}`, ou seja a MESMA leitura a ser paga duas vezes, e com a maquina
        # a 69% o laco caia de 21 Hz para 1,2 Hz (`YOUTUBE_LOOP_HZ`).
        declared = declared if declared is not None else ''
        if not declared:
            # COM A PORTA CDP ABERTA, O ID NAO SE PERGUNTA A' ARVORE (2026-11-03).
            # MEDIDO -- e este e' o 46 s: `EXTERNAL_CAPTIONS_READ_MS ms=46766.0`
            # com `phases={'target': 0.0, 'source': 0.0}` e o despejo a mostrar a
            # paragem dentro de `_youtube_video_id` (`edit_values`, 94-109 ms num
            # tick bom, dezenas de segundos num mau). Sem `declared` a funcao
            # abaixo ia perguntar; o id vem da FOTO no tick seguinte (80 ms).
            # Um tick sem desenho nao e' um tick perdido; um tick de 46 s e'.
            declared = ''
        _yt_mark(self, 'declared')
        # COM DUAS ABAS ABERTAS, SO' A DO VIDEO QUE ELE LE' (medido 2026-11-03:
        # `list_targets` devolve 2 `watch` nesta maquina). Sem o id, o modulo
        # responde `ambiguous` e nao se adivinha.
        try:
            source.set_video_id(declared)
        except Exception:  # noqa: BLE001
            pass
        # UMA FOTO COM 1,2 s AINDA SERVE: a cue do player fica no ecra mais
        # tempo do que isso, e recusar aos 0,6 s so' fazia piscar entre a CDP
        # e a arvore de acessibilidade (medido 2026-11-03: `why=cdp` e
        # `why=painted` alternados a cada segundo).
        snap = source.snapshot(max_age=1.2)
        _yt_mark(self, 'snap')
        # A CADENCIA DO TUBO INTEIRO E' UM NUMERO (2026-11-03). O dono ve' a
        # legenda a saltar linhas, e a resposta nao pode ser um palpite: esta
        # linha diz, de 5 em 5 s, quantos ticks o laco fez, em quantos havia
        # foto fresca, a idade MEDIA dessa foto e o que a fonte acumulou.
        # `none` alto com `src_reads` a subir = a foto a ser recusada por velha;
        # `ticks` baixo = o laco empurrado por outra coisa.
        try:
            _st = getattr(self, '_yt_rate', None)
            if _st is None:
                _st = self._yt_rate = {'t0': time.monotonic(), 'ticks': 0,
                                       'ok': 0, 'none': 0, 'age': 0.0}
            _st['ticks'] += 1
            if snap is not None:
                _st['ok'] += 1
                _st['age'] += time.monotonic() - snap['stamp']
            else:
                _st['none'] += 1
            _dt = time.monotonic() - _st['t0']
            if _dt >= 5.0:
                log('YOUTUBE_LOOP_HZ ticks=%d ok=%d none=%d age_ms=%.0f hz=%.1f '
                    'src_reads=%s src_errs=%s'
                    % (_st['ticks'], _st['ok'], _st['none'],
                       1000.0 * (_st['age'] / _st['ok'] if _st['ok'] else 0.0),
                       _st['ticks'] / _dt,
                       getattr(source, '_reads', None),
                       getattr(source, '_errors', None)))
                _st['t0'] = time.monotonic()
                _st['ticks'] = _st['ok'] = _st['none'] = 0
                _st['age'] = 0.0
        except Exception:                     # noqa: BLE001
            pass
        if snap is not None:
            # O RELOGIO DO PLAYER VEM NO MESMO SNAPSHOT (2026-11-03): `t` e'
            # `video.currentTime`, medido a avancar 56,9 s em 57 s de relogio de
            # parede enquanto o DOM da legenda estava CONGELADO -- e' a unica
            # leitura que continua verdadeira com a aba escondida.
            self.yt_cdp_clock = (float(snap.get('t')), time.monotonic()) \
                if snap.get('t') is not None else None
            # VIDEO EM PAUSA NAO E' SILENCIO (2026-11-03, MEDIDO): com o player
            # parado em `t=34.571` o YouTube continua a mostrar a legenda, e o
            # Sotto apagava a dele aos 6 s (`CAPTION_WINDOW_BLANKED
            # reason=no-caption-for-6.0s`) -- o ecra ficava vazio ao lado de um
            # video que tem a frase escrita.
            self.yt_cdp_paused = bool(snap.get('paused')) \
                if snap.get('paused') is not None else False
            # O ESPELHO NA SHELL: quem arma o apagar por inatividade e' a shell,
            # noutro objeto (`SottoShell._caption_idle_hide`). Sem este espelho o
            # guarda ficava no objeto errado e o ecra apagava na mesma.
            shell = getattr(self, 'shell', None)
            if shell is not None:
                shell.yt_source_paused = self.yt_cdp_paused
        if snap is None or not snap.get('items'):
            return None
        seen = snap.get('videoId') or ''
        if declared and seen and declared != seen:
            stamp = getattr(self, 'yt_cdp_mismatch_logged', None)
            if stamp != (declared, seen):
                self.yt_cdp_mismatch_logged = (declared, seen)
                log('YOUTUBE_CDP_SOURCE refused=video-mismatch declared=%s seen=%s'
                    % (declared, seen))
            return None
        return snap
    def _yt_clock_agrees(self, t):
        """Is the clock INSIDE the cue the player was painting?

        MEASURED 2026-10-20 on the owner's own Chrome: the seek bar's
        RangeValue AND the player's own clock text are FROZEN -- +0.00 s in
        8.35 s of wall clock, while the painted line advanced +8.96 s in the
        track. The clock read t=2.0 while the video was at t=530.

        So the clock is only TRUSTED when the last alignment says the video
        IS there. A line from another minute is worse than no line. With no
        alignment yet there is nothing to compare with, and the clock is
        used -- it is all there is.
        """
        hit = self.yt_hit
        if not hit:
            return True
        cue = hit.get('cue') or {}
        try:
            start = float(cue.get('start'))
            end = float(cue.get('end'))
        except (TypeError, ValueError):
            return True
        return (start - 2.0) <= float(t) <= (end + 2.0)

    def _yt_decide(self, now_t):
        """O instante que pode ser servido -- o relogio nunca recua.

        A decisao inteira (e as 129 linhas medidas que a motivaram) vive em
        `youtube_monotonic.decide`. Aqui so' se' guarda o resultado.
        """
        try:
            import youtube_monotonic
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_MONOTONIC_FAILED error={exc!r}')
            return now_t
        before = self.yt_serve_floor
        served, floor = youtube_monotonic.decide(now_t, before)
        # `held` e' a ASSINATURA do defeito: a leitura do relogio atras do chao.
        # Nao se pode medir por `served` -- com a regra viva `served` E' o chao,
        # e a condicao nunca dispararia (log morto).
        held = (now_t is not None and before is not None
                and float(now_t) < float(before) - 0.05)
        if held and now_t != self.yt_held_logged:
            log('YOUTUBE_CLOCK_HELD t=%.2f served=%.2f floor=%.2f'
                % (float(now_t), float(served), float(before)))
            self.yt_held_logged = now_t
        self.yt_serve_floor = floor
        return served

    def _yt_advance(self, position):
        """O chao sobe para uma posicao JA' servida (o ramo pintado)."""
        try:
            import youtube_monotonic
            self.yt_serve_floor = youtube_monotonic.advance(
                self.yt_serve_floor, position)
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_MONOTONIC_FAILED error={exc!r}')
        return self.yt_serve_floor

    #: QUANTO TEMPO UMA FOTO DA CDP AINDA DIZ "O DOM DO PLAYER E' A FONTE"
    #: (2026-11-03). E' a MESMA janela que a leitura ja' usa
    #: (`_yt_cdp_snapshot` -> `snapshot(max_age=1.2)`), e e' medida no
    #: PROPRIO snapshot (`stamp`), nao num proxy: `yt_live_paint_at` sobe com
    #: qualquer produtor de linhas e por isso nao diz QUEM as produziu.
    DOM_FRESH_S = 1.2

    def _yt_dom_is_source(self):
        """O DOM do player esta' a entregar as linhas AGORA?

        A pergunta que decide se a faixa e' pedida. MEDIDO 2026-11-03: pedir a
        faixa e' um `yt-dlp` (segundos, um subprocesso por video) mais uma
        leitura UIA; enquanto o DOM entrega as linhas, as duas sao trabalho que
        nao muda um pixel.

        A FRESCURA E' A DO SNAPSHOT (o instante em que a CDP leu o DOM), e nao a
        do ultimo desenho: uma foto recente SEM linhas NAO conta como fonte --
        um video sem legenda tem de continuar a pedir a faixa, senao o `no-track`
        nunca chega e o ASR nunca recebe a caixa de volta (a regra do dono:
        *"se for um video sem legenda, vai transcrever ao vivo igual"*).
        """
        source = getattr(self, '_yt_cdp_source', None)
        if not source or source is False:
            return False
        try:
            snap = source.snapshot(max_age=self.DOM_FRESH_S)
        except Exception:                 # noqa: BLE001
            return False
        if not snap or not snap.get('rows'):
            return False
        try:
            return (time.monotonic() - float(snap['stamp'])) <= self.DOM_FRESH_S
        except Exception:                 # noqa: BLE001
            return False

    def _yt_track_poll(self, thread, vid, painted):
        """O pedido da faixa: FIRE AND FORGET, e o DOM decide se ele existe.

        A UNICA entrada do laco da legenda nesta thread. Duas regras:

          * DOM PRIMARIO -- com o snapshot fresco a trazer linhas, a faixa NAO
            se pede; le-se so' o que ja' chegou;
          * NUNCA BLOQUEIA -- `thread.request` so' escreve o pedido e devolve o
            que estiver PRONTO; quem corre o `yt-dlp` e' a thread dela.
            MEDIDO 2026-11-03 no log do dono: 46 766 ms e 62 234 ms num tick,
            com `YOUTUBE_TRACK_READY cues=1083` logo a seguir.
        """
        if thread is None:
            return None
        dom = self._yt_dom_is_source()
        try:
            if dom:
                track = thread.current(vid)
                why = 'dom'
            else:
                track = thread.request(vid, painted=painted)
                why = 'paint' if painted else 'pending'
        except Exception as exc:          # noqa: BLE001
            log(f'YOUTUBE_TRACK_POLL_FAILED video_id={vid} error={exc!r}')
            return None
        # A PERGUNTA ESCRITA UMA VEZ POR MUDANCA: "porque e' que a faixa nao se
        # pediu" nao pode ser um estado nao escrito.
        if why != getattr(self, 'yt_ask_why', ''):
            self.yt_ask_why = why
            log('YOUTUBE_TRACK_ASK why=%s video_id=%s ready=%s dom_fresh=%.1fs'
                % (why, vid, '0' if track is None else '1', self.DOM_FRESH_S))
        return track

    def _youtube(self, hwnd, uia, UIA):
        """The YouTube video's OWN caption track, AT THE INSTANT THE PLAYER
        IS SHOWING IT.

        RETURNS `([(source, [line])], urgent)`:
          * the first is the REAL caption -- one line -- or `[]`;
          * `urgent` is True when the ASR must be given back NOW, because the
            video has NO caption track.

        THE SOURCE IS THE PLAYER'S OWN PAINTED LINE. MEASURED 2026-10-20 on
        the owner's own Chrome, on the video he was watching: the player's
        caption window holds the words it is painting, one UIA child per
        word, and those words CHANGE while the video plays. The two things
        the app used to ask the UIA for were BOTH wrong there:

          * the SEEK BAR AND THE PLAYER'S CLOCK TEXT ARE FROZEN: +0.00 s in
            8.35 s of wall clock, while the painted line advanced +8.96 s in
            the track. The clock the app read (t=2.0) was eight minutes away
            from the truth (t=530);
          * the caption window exposes NO language (0 of 448 elements have
            UIA 30007), so the app fell back to the language preference and
            served `pt-orig` while the player painted `en-orig` -- the owner
            would have compared Portuguese against English.

        So the line is the painted one, and the track is the one that HOLDS
        it (`youtube_captions.align_painted`). The clock is then not read at
        all on that path, and the poll gets CHEAPER: 106.5 ms of clock
        against 92.7 ms of paint (MEASURED).

        THE "NOTHING TO SHOW" CASES, AND WHAT EACH ONE MEANS:
          * `no-video-id`   -- we cannot read which video this is. The page
            text is not a caption, so the ASR keeps the box.
          * `track-pending` -- the first fetch is a network call (MEASURED
            5.0 s). Until it lands there is no caption, and the ASR keeps
            the box.
          * `painted-other-track` -- the player is painting words that are
            not in the track we have, so the track we have is the WRONG one.
            The search is asked again WITH those words; until it lands the
            ASR stays parked (the video HAS captions).
          * `clock-stale`   -- the clock does not agree with the line the
            player was painting, so it is frozen: no line is shown rather
            than a line from another minute.
          * `no-cue`        -- a gap between the cues, or a clock we cannot
            read. The player shows nothing here either. The ASR is only
            given back after a LONG silence (`YT_RELEASE_S`): a caption
            track blinks, and every blink would cost a model load
            (MEASURED 11.6 s, 1 218 MB resident).
        """
        vid, _src, _wait = self._yt_identify(hwnd, uia, UIA)
        if _wait:
            return [], False
        if not vid:
            return [], self._yt_forget('no-video-id', urgent=False)
        if vid != self.yt_video_id:
            self._yt_switch_video(vid, _src)
        reply = self._yt_cdp_fast_lines(hwnd, uia, UIA, vid)
        if reply is not None:
            return reply
        thread = getattr(self.shell, 'youtube_track_thread', None)
        _yt_mark(self, 'thread')
        if thread is None:
            return [], self._yt_forget('no-track-thread', urgent=False)
        # THE WORDS THE PLAYER IS PAINTING. They ARE YouTube's own caption.
        _t_yt = time.monotonic()
        self._ensure_clock_sampler()
        painted = self._youtube_painted(hwnd, uia, UIA)
        _yt_mark(self, 'painted')
        reply = self._yt_cdp_lines(vid)
        if reply is not None:
            return reply
        # O PEDIDO DA FAIXA: `_yt_track_poll` decide, nao bloqueia, e o DOM do
        # player decide se ele existe -- o porque' medido esta' no docstring dela
        # (46 766 ms e 62 234 ms num tick eram o `yt-dlp` a correr DENTRO do laco).
        track = self._yt_track_poll(thread, vid, painted)
        _yt_mark(self, 'track')
        if track is None:
            return self._yt_untracked_lines(hwnd, uia, UIA, painted)
        if track.get('state') != 'has-track':
            reason = track.get('reason') or track.get('state') or 'unknown'
            return [], self._yt_forget('no-track:%s' % reason, urgent=True)
        if painted:
            reply = self._yt_painted_lines_match(hwnd, uia, UIA, track, painted, vid)
            if reply is None:
                reply = self._yt_aligned_painted(hwnd, uia, UIA, track, painted, vid)
            if reply is not None:
                return reply
            now_t = self._youtube_time(hwnd, uia, UIA, track.get('duration'))
            key = ' '.join(str(w) for w in painted)[:120]
            moved = (now_t is not None
                     and (self.yt_foreign_t is None
                          or abs(float(now_t) - float(self.yt_foreign_t)) > 0.05))
            if now_t is not None and (moved or key == self.yt_foreign_key):
                self.yt_foreign_t, self.yt_foreign_key = float(now_t), key
                # O RELOGIO NAO RECUA O ECRA (2026-10-30). `now_t` passa a ser
                # o instante autorizado por `youtube_monotonic.decide`: nunca
                # atras do chao, excepto quando o PROPRIO relogio recuou (seek).
                # MEDIDO: 129 das 2126 linhas de `webview-run.log` recuavam --
                # ate' 359 s -- e era isto que o dono via como *"repete a
                # legenda de instantes atras"*.
                now_t = self._yt_decide(now_t)
                # O RELOGIO FINO NESTE RAMO TAMBEM (2026-11-02). MEDIDO na sessao
                # do dono (pid 18676): 18 YOUTUBE_CAPTION, todas
                # why=painted-other-track, e o relogio do UIA a saltar de segundo em
                # segundo -- o ancora so' existia no ramo `painted`, logo a frase
                # entrava de uma vez. Prova: _main/reveal-park-oracle.py A1/A2.
                self._yt_anchor = (float(now_t), time.monotonic())
                self._yt_track = track
                reply = self._yt_clock_cue(track, now_t, vid)
            else:
                reply = None
            if reply is not None:
                return reply
            return self._yt_no_clock_lines(hwnd, uia, UIA, track, painted, vid)
        return self._yt_clock_lines(hwnd, uia, UIA, track, vid)

    def _yt_identify(self, hwnd, uia, UIA):
        """QUAL e' o video, e a porta da CDP ja' leu a resposta?

        A IDENTIDADE VEM DA FONTE QUE JA' ESTA' LIDA (2026-11-03, MEDIDO). A
        varredura dos `Edit` do Chrome custa 94-109 ms por tick, e o snapshot da
        CDP ja' traz o `videoId` da pagina que ele esta' a ler. Perguntar a'
        arvore de acessibilidade quando a resposta ja' esta' na mao era 90% da
        leitura (`phases={'vid': 109.0, 'painted': 109.0}`). A UIA continua a ser
        a fonte quando nao ha snapshot -- sem CDP, sem resposta.

        Devolve `(vid, src, wait)`. `wait=True` e' "a foto seguinte traz o id":
        a porta esta' viva e o id ja' e' conhecido, portanto nao se paga a
        varredura dos `Edit` neste tick.
        """
        vid = ''
        # A PORTA ABRE ANTES DE SE PERGUNTAR O ID (2026-11-03). Ver
        # `_yt_cdp_ensure`: o id vem da foto, e a foto so' existe com a porta
        # aberta. A ordem antiga tornava o caminho barato inalcancavel.
        _yt_mark(self, 'yt-in')
        _src = self._yt_cdp_ensure(getattr(self, 'yt_video_id', '') or None)
        _yt_mark(self, 'cdp')
        if _src and _src is not False:
            # DUAS ABAS `watch`: O TITULO DA JANELA DECIDE (2026-11-03).
            # MEDIDO: `YOUTUBE_CDP_SOURCE state=ambiguous` enquanto a legenda
            # nao andava. O titulo vem do Win32 em microssegundos.
            try:
                _src.set_window_title(external_subs._window_title(hwnd))
            except Exception:                 # noqa: BLE001
                pass
        if _src and _src is not False:
            try:
                _early = _src.snapshot(max_age=1.5)
            except Exception:  # noqa: BLE001
                _early = None
            if _early:
                vid = str(_early.get('videoId') or '')
        if not vid:
            # A ARVORE SO' RESPONDE QUANDO NAO HA' FOTO NENHUMA PARA VIR (2026-11-03).
            # Com a fonte CDP viva o id chega na foto seguinte (~80 ms); a varredura
            # UIA dos `Edit` e' de 94-109 ms num tick bom e foi a dona dos 46 s e
            # 62 s medidos na sessao do dono. Sem foto, espera-se o tick seguinte.
            # UMA VEZ, PARA A PORTA SABER QUE ABA E' A NOSSA (2026-11-03).
            # MEDIDO: com DUAS abas `watch` abertas a fonte responde
            # `state=ambiguous` e nunca produz foto -- e sem id nunca ha' foto.
            # O id que a arvore da' nesta primeira leitura e' o que a fonte passa
            # a usar (`set_video_id`); a partir daí a arvore nao volta a ser
            # perguntada, porque `yt_video_id` ja' existe.
            if _src and _src is not False and not getattr(self, 'yt_video_id', ''):
                # O ID SAI DA ABA ESCOLHIDA PELO TITULO DA JANELA (2026-11-03).
                # MEDIDO: com TRES abas `watch` a fonte ficou
                # `stats={'reads': 0, 'note': 'ambiguous'}` por minutos e a
                # legenda parou. A arvore (UIA) era o unico caminho para o id e
                # e' ela que custa 46-109 ms por tick. Aqui o id vem do URL da
                # aba que o titulo da JANELA ja' identifica -- sem arvore.
                try:
                    vid = _src.target_video_id() or ''
                except Exception:         # noqa: BLE001
                    vid = ''
            if _src and _src is not False and getattr(self, 'yt_video_id', ''):
                # O ID DECLARADO PODE ESTAR MORTO (2026-11-03): uma vez
                # guardado nunca era reperguntado e o `pick_target` filtra as
                # abas por ele -- aba fechada, laco preso (164 linhas de
                # `m_bJQ4G1Ht8` com outra aba a tocar). A ABA MANDA; o custo e'
                # um HTTP em cache de 2 s. Ver docs/youtube-source-identity.md.
                try:
                    _tid = _src.target_video_id() or ''
                except Exception:             # noqa: BLE001
                    _tid = ''
                if _tid and _tid != getattr(self, 'yt_video_id', ''):
                    log('YOUTUBE_TARGET_REBOUND was=%s now=%s why=aba'
                        % (getattr(self, 'yt_video_id', '') or '-', _tid))
                    self._yt_switch_video(_tid, _src)
                _yt_mark(self, 'vid')
                return '', _src, True
            vid = self._youtube_video_id(hwnd, uia, UIA)
        _yt_mark(self, 'vid')
        return vid, _src, False

    def _yt_switch_video(self, vid, src):
        """TROCAR DE VIDEO NAO DEIXA A LINHA DO ANTERIOR NO ECRA (2026-11-03).

        O dono alterna entre videos a toda a hora; a primeira leitura do novo
        chega numa foto (dezenas de ms), mas ate' la' o que esta' no ecra e' a
        ultima linha do OUTRO video -- duas legendas, uma delas falsa. A
        janela apaga-se aqui e a linha nova entra assim que houver.
        """
        self.yt_video_id = vid
        # A PORTA PASSA A SABER QUAL ABA E' A NOSSA (2026-11-03). MEDIDO:
        # `YOUTUBE_CDP_SOURCE state=ambiguous` -- com duas abas `watch`
        # abertas a fonte nao escolhe e a foto nunca chega; e foi este
        # idioma que a ordem antiga (id primeiro, porta depois) escondia.
        if src and src is not False:
            try:
                src.set_video_id(vid)
            except Exception:         # noqa: BLE001
                pass
        self.yt_cue = ''
        self._yt_switch_at = time.monotonic()
        # O APAGAR DA JANELA MORA NA SHELL, NAO AQUI (2026-11-03). MEDIDO com
        # o oraculo `_main/yt-loop-uia-oracle.py`: `self._blank_caption_window`
        # nao existe neste objecto -- a chamada levantava `AttributeError` a
        # cada troca de video, ou seja o ramo que devia limpar a linha do
        # video ANTERIOR morria antes de a limpar (e a linha antiga ficava no
        # ecra, que e' o defeito que este ramo existe para evitar).
        _bw = getattr(getattr(self, 'shell', None), '_blank_caption_window', None)
        if _bw is not None:
            try:
                _bw('video-changed')
            except Exception:             # noqa: BLE001
                pass
        # A ULTIMA LINHA PINTADA era do video ANTERIOR. It cannot be
        # the line of this one, and it is what the clock is compared
        # with, so it goes with the video.
        self.yt_hit = None
        # UM VIDEO NOVO NAO HERDA NADA (2026-10-30): cada campo por-video era
        # uma forma de a legenda do anterior voltar ao ecra.
        self.yt_serve_floor = None
        self.yt_foreign_t = None
        self.yt_foreign_key = ''
        self._yt_anchor = None
        self._yt_track = None
        self.last_line = ''
        self.last_rows = []
        self.finalized = False
        self._caption_pending = None
        blank = getattr(getattr(self, 'shell', None), '_blank_caption_window', None)
        if blank is not None:
            blank('video-changed')
        log(f'YOUTUBE_VIDEO_CHANGED video_id={vid}')

    def _yt_cdp_fast_lines(self, hwnd, uia, UIA, vid):
        """O CAMINHO BARATO VEM PRIMEIRO (2026-11-03), e decide sozinho.

        MEDIDO no dono: o laco pagou 46 s e 62 s num tick
        (`EXTERNAL_CAPTIONS_READ_MS ms=46766.0`), e o custo era o que vinha
        DEPOIS daqui: a leitura UIA das palavras (`phases={'painted':
        17843.0}`) e o `yt-dlp` da faixa. Quando a CDP entrega as linhas do DOM
        do player, essas linhas SAO a legenda: nao ha' nada a alinhar, nada a
        pedir, nada a perguntar a' arvore. Este caminho e' o que faz o tick
        custar ~20 ms em vez de dezenas de segundos.

        Devolve a resposta, ou `None` quando nao ha' linhas na foto.
        """
        _snap_fast = self._yt_cdp_snapshot(hwnd, uia, UIA, declared=vid or None)
        _yt_mark(self, 'fast-snap')
        if _snap_fast and _snap_fast.get('rows'):
            self.yt_cdp_rows = list(_snap_fast['rows'])
            if _snap_fast.get('items'):
                self.yt_paint_items = _snap_fast['items']
            _yt_mark(self, 'thread')
            _fast_rows = self._yt_rows(None, hwnd=hwnd, uia=uia, UIA=UIA)
            _yt_mark(self, 'fast-rows')
            if _fast_rows:
                self.yt_reason = 'cdp-lines'
                self.yt_cue = ' '.join(_fast_rows)
                return [('external:youtube:track', _fast_rows)], False
            return [], False
        return None

    def _yt_cdp_lines(self, vid):
        """A LINHA DO PLAYER PASSA A' FRENTE DE TUDO (2026-11-03).

        Quando a CDP entrega as linhas que o player TEM no DOM, essas linhas SAO
        a legenda: nao se alinha com a faixa, nao se espera cue, nao se
        re-quebra. MEDIDO nesta sessao: com a faixa a' frente o ecra ficou 60 s
        sem uma unica linha (`CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s`)
        enquanto o player pintava duas; e o alinhamento prendia-se em `cue=1114`
        minutos depois de o video a ter passado. O que o player desenha e' o 1:1,
        por definicao -- `_youtube_painted` ja' leu isso.

        Devolve a resposta, ou `None` quando a foto nao trouxe linhas.
        """
        cdp_rows = list(getattr(self, 'yt_cdp_rows', None) or ())
        if not cdp_rows:
            return None
        self.yt_cdp_rows = None
        self.yt_reason = 'cdp-lines'
        # A TROCA DE VIDEO TEM UM NUMERO (2026-11-03). O dono alterna entre
        # videos e pediu para eu saber como isso se comporta: daqui sai
        # `YOUTUBE_SWITCH_FIRST_FRAME ms=..` -- do instante em que o id mudou
        # ate' a primeira linha do video NOVO no ecra. Sem este numero, uma
        # troca lenta volta a ser uma impressao.
        _sw = getattr(self, '_yt_switch_at', None)
        if _sw is not None:
            self._yt_switch_at = None
            log('YOUTUBE_SWITCH_FIRST_FRAME ms=%.0f video_id=%s rows=%d'
                % ((time.monotonic() - _sw) * 1000.0, vid, len(cdp_rows)))
        self.yt_cue = ' '.join(cdp_rows)
        self.yt_foreign_t = None
        if self.yt_cue != self.yt_caption_logged:
            self.yt_caption_logged = self.yt_cue
            log('YOUTUBE_CAPTION video_id=%s track=- lines=%d ratio=1.00 '
                'text=%r why=cdp-lines' % (vid, len(cdp_rows), self.yt_cue[:90]))
        return [('external:youtube:track', cdp_rows)], False

    def _yt_untracked_lines(self, hwnd, uia, UIA, painted):
        """AS PALAVRAS DO PLAYER ANTES DO TRACK. OWNER, 2026-10-22 09:35.

        verbatim: *"tu so viu carregar a pagina depois de varios segundos de ja
        ter carregado? arruma isso."* A causa era de DESENHO, nao de velocidade:
        a leitura das palavras pintadas (UI Automation) e barata e ja estava feita
        aqui em cima, mas a linha so era emitida depois de o track chegar -- e o
        extract mede segundos. Estas palavras SAO o texto que o YouTube esta a
        desenhar, logo sao 1:1 por construcao; o track substitui-as quando chega,
        com a janela de duas linhas e o timing. Sem palavras, nada e inventado:
        a linha fica vazia e o motivo continua `track-pending`.
        """
        try:
            import youtube_window
            paint_text = youtube_window.paint_line(painted)
        except Exception as exc:  # noqa: BLE001
            log(f"YOUTUBE_PAINT_LINE_FAILED error={exc!r}")
            paint_text = ""
        # AS LINHAS, NAO A LINHA COLADA (2026-11-02). `paint_line` junta
        # `['>> Nossa.', '>> ta segurando essa wave,']` num texto so', e o
        # overlay re-quebra onde quer -- o dono viu exactamente isso. O que o
        # player desenha sao DUAS linhas, e sao essas que saem.
        try:
            lines_now = self._yt_rows(painted, hwnd, uia, UIA)
        except Exception:  # noqa: BLE001
            lines_now = []
        if lines_now:
            self.yt_reason = "painted-untracked"
            self.yt_cue = " ".join(lines_now)
            return [("external:youtube:track", lines_now)], False
        if paint_text:
            self.yt_reason = "painted-untracked"
            self.yt_cue = paint_text
            return [("external:youtube:track", [paint_text])], False
        return [], self._yt_forget('track-pending', urgent=False)

    def _yt_painted_lines_match(self, hwnd, uia, UIA, track, painted, vid):
        """A FAIXA MANUAL DESENHA LINHAS INTEIRAS, E `align_painted` PROCURA
        PALAVRAS (2026-11-02).

        MEDIDO nesta box no arranque de 22:16:47, com o player a pintar
        `>> Nossa.` num video `lang=pt-orig`:
          `YOUTUBE_TRACK_PAINT source=painted-no-match cue=- match=0
           painted_words=5`
        Os filhos da janela de legenda sao LINHAS, nao palavras, portanto o
        alinhamento nunca casa -- e o ecra passava a ser servido pelo RELOGIO.
        E' dai' que vinham as tres imagens do dono: a linha a construir-se,
        meia palavra cortada e o cue anterior empilhado. Quando o player
        desenha linhas inteiras E elas pertencem a faixa servida, a copia
        directa (mesmo texto, mesmo instante) substitui a janela.

        Devolve a resposta, ou `None` quando as linhas nao pertencem a faixa.
        """
        lines_now = []
        try:
            import youtube_window as _ytw
            lines_now = self._yt_rows(painted, hwnd, uia, UIA)
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_PAINT_ROWS_FAILED error={exc!r}')
        if lines_now and any(len(line.split()) >= 2 for line in lines_now):
            t_probe = None
            try:
                t_probe = self._youtube_time(hwnd, uia, UIA,
                                             track.get('duration'))
            except Exception as exc:  # noqa: BLE001
                log(f'YOUTUBE_PLAYED_T_FAILED error={exc!r}')
            pool = self._yt_words_pool(track, t_probe)
            try:
                same = _ytw.match_ratio(lines_now, pool)
            except Exception as exc:  # noqa: BLE001
                log(f'YOUTUBE_PAINT_MATCH_FAILED error={exc!r}')
                same = {'ok': False, 'ratio': 0.0}
            if same.get('ok'):
                self.yt_foreign_t = None
                self.yt_cue = ' '.join(lines_now)
                self.yt_reason = 'painted-lines'
                if t_probe is not None:
                    self._yt_anchor = (float(t_probe), time.monotonic())
                    self._yt_track = track
                if self.yt_cue != self.yt_caption_logged:
                    self.yt_caption_logged = self.yt_cue
                    log('YOUTUBE_CAPTION video_id=%s track=%s lines=%s '
                        'ratio=%.2f text=%r why=painted-lines'
                        % (vid, track.get('lang') or '-', len(lines_now),
                           float(same.get('ratio') or 0.0), self.yt_cue[:90]))
                return [('external:youtube:track', lines_now)], False
        return None

    def _yt_aligned_painted(self, hwnd, uia, UIA, track, painted, vid):
        """A PINTURA ALINHA COM O CUE DA FAIXA SERVIDA -- e essa e' a linha.

        E' o caminho 1:1 de sempre: `align_painted` diz QUAL cue o player esta'
        a pintar, a ancora passa a ser o relogio do proprio player (a 60 ms,
        `yt_live_frame`), e o texto servido sao as LINHAS que ele desenha, nao a
        janela re-quebrada a partir da faixa.

        Devolve a resposta, ou `None` quando a pintura nao casou com a faixa
        (o ramo de outro track decide entao pelo relogio).
        """
        hit = None
        try:
            import youtube_captions
            _t_align = time.monotonic()
            hit = youtube_captions.align_painted(track.get('cues') or (),
                                                  painted)
            self._yt_prof("align", _t_align)
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_PAINT_ALIGN_FAILED video_id={vid} error={exc!r}')
        if not hit and painted:
            # A MEDICAO QUE FALTAVA (2026-11-02). `match=0` com a faixa certa
            # foi medido tres vezes nesta box e nao dizia PORQUE: agora o log
            # traz as palavras pintadas e as primeiras palavras das cues, uma
            # vez por texto, para a divergencia ser lida e nao adivinhada.
            key = ' '.join(str(w) for w in painted)[:120]
            if key != getattr(self, 'yt_miss_logged', ''):
                self.yt_miss_logged = key
                first = []
                for cue in (track.get('cues') or ())[:3]:
                    first.extend(str(cue.get('text') or '').split()[:8])
                log('YOUTUBE_ALIGN_MISS video_id=%s painted=%r cue0=%r'
                    % (vid, list(painted)[:6], first[:8]))
        if hit:
            text = str(hit.get('text') or '').strip()
            if text:
                self.yt_hit = hit
                self.yt_foreign_t = None
                self.yt_cue = text
                self.yt_reason = 'painted'
                # A PINTURA E' O RELOGIO MAIS ADIANTADO QUE EXISTE: e' o
                # que o player esta' a desenhar agora. O chao sobe com ela,
                # e e' isso que impede o relogio atrasado de recuar o ecra.
                self._yt_advance((hit.get('cue') or {}).get('start'))
                # THE DECISION, WRITTEN. This is the line the owner can
                # compare with the screen: the cue of the track the
                # player is painting, at the instant it is painting it.
                if text != self.yt_caption_logged:
                    self.yt_caption_logged = text
                    log('YOUTUBE_CAPTION video_id=%s cue=%s t=%s '
                        'track=%s words=%s text=%r'
                        % (vid, hit.get('index'),
                           hit.get('cue', {}).get('start'),
                           track.get('lang') or '-', hit.get('exact'),
                           text[:90]))
                # A JANELA REVELADA PELAS PALAVRAS QUE O PLAYER PINTOU
                # (2026-10-29). MEDIDO: este ramo montava a janela com o
                # INICIO DO CUE (`hit.cue.start + 0.001`), e `revealed_lines`
                # corta a linha pelos relogios das palavras -- logo SO a
                # primeira palavra passava, e a linha NUNCA crescia no ecra.
                # O relogio certo aqui sao as PALAVRAS QUE O PLAYER JA
                # PINTOU: elas sao o prefixo revelado do cue, palavra a
                # palavra, 1:1 por construcao. Ver `youtube_reveal.py`.
                # O RELOGIO DO PROPRIO PLAYER, e nao so' a pintura, para
                # cortar a linha na PALAVRA (2026-10-30, ver
                # `youtube_reveal.word_clock_count`). Este `t` e' tambem o
                # ANCORA da recomposicao a 60 ms: `yt_live_frame` avanca-o
                # com `monotonic()` entre leituras do UIA, por isso as
                # palavras seguintes aparecem uma a uma sem custar uma
                # leitura de acessibilidade por palavra.
                played_t = None
                try:
                    played_t = self._youtube_time(hwnd, uia, UIA,
                                                  track.get('duration'))
                except Exception as exc:  # noqa: BLE001
                    log(f'YOUTUBE_PLAYED_T_FAILED error={exc!r}')
                if played_t is not None:
                    self._yt_anchor = (float(played_t), time.monotonic())
                    self._yt_track = track
                else:
                    self._yt_anchor = None
                # O TEXTO QUE O PLAYER DESENHA E' A LEGENDA (2026-11-02, ordem
                # do dono: *"sotto devia ta copiando 1:1 sem truncar palavras"*).
                # Aqui estava `window_by_paint`, que re-quebra a partir do track e
                # corta em `cap = min(pintado, relogio_de_palavra)`: dai' vem a linha
                # que se CONSTR OI ao longo do cue, a meia palavra (`Yamato ja' d`) e
                # a janela que empilha o cue anterior por baixo do actual -- as tres
                # coisas que ele fotografou. As linhas pintadas JA' SAO o texto do
                # YouTube, uma por linha: saem inteiras, no instante em que mudam.
                try:
                    import youtube_window
                    lines = self._yt_rows(painted, hwnd, uia, UIA)
                except Exception as exc:  # noqa: BLE001
                    log(f'YOUTUBE_PAINT_ROWS_FAILED error={exc!r}')
                    lines = []
                return [('external:youtube:track', lines or [text])], False
        return None

    def _yt_clock_cue(self, track, now_t, vid):
        """THE PLAYER IS PAINTING ANOTHER TRACK -- AND THE OWNER WAS LEFT WITH NOTHING.

        MEDIDO 2026-10-23 (`_main/yt-1to1-live-compare.py`, Edge proprio, video
        WdaHAGRBB6s): o player pinta `pt`, a TRADUCAO automatica, enquanto a politica
        serve `en-orig`. As palavras pintadas nunca estao na faixa servida, logo o
        `align_painted` nao tem o que alinhar -- e a app devolvia NADA, para sempre.
        Nao era lentidao: era um beco sem saida, e o ASR tomava o lugar do YouTube (é
        isso que o dono chamou *"a legenda do youtube ta completamente bugada"*).

        A SAIDA NAO E SEGUIR A TRADUCAO (proibido: *"para de traduzir pra pt br do
        ingles e do espanhol"*). E o RELOGIO do player dizer onde o video esta e
        desenhar-se a cue da faixa SERVIDA nesse instante. O relogio so e usado
        enquanto ANDA: o congelado e medido (lia t=2.0 com o video a 530), e a prova
        do congelamento e uma PINTURA QUE MUDA COM O RELOGIO PARADO. Quem chama ja'
        verificou que ele ANDA ou que a pintura nao mudou com ele parado.

        Devolve a resposta, ou `None` quando nao ha' cue nesse instante -- e
        entao quem decide e' o ramo que pinta as linhas do player
        (`_yt_no_clock_lines`).
        """
        cue = None
        try:
            import youtube_captions
            cue = youtube_captions.cue_at(track.get('cues') or (), now_t)
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_CUE_LOOKUP_FAILED video_id={vid} error={exc!r}')
        text = str((cue or {}).get('text') or '').strip()
        if not text:
            return None
        self.yt_cue = text
        self.yt_reason = 'painted-other-track:clock'
        self._yt_advance((cue or {}).get('start'))
        if text != self.yt_caption_logged:
            self.yt_caption_logged = text
            log('YOUTUBE_CAPTION video_id=%s cue=%s t=%s track=%s '
                'text=%r why=painted-other-track'
                % (vid, (cue or {}).get('start'), round(now_t, 2),
                   track.get('lang') or '-', text[:90]))
        return [('external:youtube:track',
                 self._yt_lines(track, now_t) or [text])], False

    def _yt_no_clock_lines(self, hwnd, uia, UIA, track, painted, vid):
        """O RAMO QUE DEIXAVA O ECRA VAZIO COM O PLAYER A DESENHAR (2026-11-02,
        terceira imagem do dono: duas linhas no YouTube, nada no Sotto).

        Cai aqui quando o track servido nao alinha E o relogio do player nao deu
        um instante -- ai' o unico texto verdadeiro que existe e' o que o player
        esta' a desenhar. Nao se inventa, nao se atrasa: pinta-se.
        """
        try:
            import youtube_window as _ytw
            lines_now = self._yt_rows(painted, hwnd, uia, UIA)
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_PAINT_ROWS_FAILED error={exc!r}')
            lines_now = []
        if lines_now:
            self.yt_reason = 'painted-no-clock'
            self.yt_cue = ' '.join(lines_now)
            if self.yt_cue != self.yt_caption_logged:
                self.yt_caption_logged = self.yt_cue
                log('YOUTUBE_CAPTION video_id=%s track=%s lines=%s text=%r '
                    'why=painted-no-clock'
                    % (vid, track.get('lang') or '-', len(lines_now),
                       self.yt_cue[:90]))
            return [('external:youtube:track', lines_now)], False
        return [], self._yt_forget('painted-other-track', urgent=False)

    def _yt_clock_lines(self, hwnd, uia, UIA, track, vid):
        """SEM LINHA PINTADA: ou a legenda esta' desligada, ou o player esta'
        entre cues. Entao o relogio e' o unico relogio que existe -- mas so' se
        confia nele quando o ultimo alinhamento concorda com ele.
        """
        t = self._youtube_time(hwnd, uia, UIA, track.get('duration'))
        if t is None:
            # THE CLOCK CANNOT BE READ: the player may be gone. The ASR is
            # given back after a LONG silence, not immediately -- a page that
            # is slow to answer the UIA is not a dead player. MEASURED
            # 2026-10-20: the owner's video was PAUSED (`t=1241.0` fixed
            # across three reads, the clock reading "20 Minutos 41 Segundos
            # de 21 Minutos 55 Segundos"), the clock WAS readable, and the
            # caption was on screen. A paused video is not a dead player.
            now = time.monotonic()
            if not self.yt_no_clock_since:
                self.yt_no_clock_since = now
            overdue = (now - self.yt_no_clock_since) >= self.YT_RELEASE_S
            return [], self._yt_forget('clock-unreadable', urgent=overdue)
        if not self._yt_clock_agrees(t):
            # THE CLOCK IS FROZEN. MEASURED 2026-10-20: it read t=2.0 for
            # eight minutes while the video was at t=530. A line from
            # another minute is worse than no line at all -- so the LAST
            # line the player was painting is shown instead: that is the
            # app's best knowledge of where the video is.
            stale = str((self.yt_hit or {}).get('text') or '').strip()
            if stale:
                self.yt_cue = stale
                self.yt_reason = 'clock-stale-last-cue'
                return [('external:youtube:track', [stale])], False
            return [], self._yt_forget('clock-stale', urgent=False)
        self.yt_no_clock_since = 0.0
        # O MESMO RELOGIO, O MESMO PERIGO -- classe varrida em 2026-10-30. Este
        # ramo tambem escolhe a cue por um relogio. `_yt_clock_agrees` ja' recusa
        # um congelamento GRANDE contra a ultima pintura; o chao fecha o resto,
        # para nao haver duas regras de tempo diferentes no mesmo ficheiro.
        t = self._yt_decide(t)
        # O MESMO ANCORA NESTE RAMO (2026-11-02, ver acima; provado em A5 do
        # `_main/reveal-park-oracle.py`).
        self._yt_anchor = (float(t), time.monotonic())
        self._yt_track = track
        cue = None
        try:
            import youtube_captions
            cue = youtube_captions.cue_at(track.get('cues') or (), t)
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_CUE_LOOKUP_FAILED video_id={vid} error={exc!r}')
        text = str((cue or {}).get('text') or '').strip()
        if not text:
            # A GAP between the cues: the player shows nothing here either,
            # and the ASR STAYS parked -- the track still owns the caption.
            return [], self._yt_forget('no-cue', urgent=False)
        self.yt_cue = text
        self.yt_reason = 'has-cue'
        self._yt_advance((cue or {}).get('start'))
        return [('external:youtube:track',
                 self._yt_lines(track, t) or [text])], False

    YT_ANCHOR_MAX_S = 3.0

    def yt_live_frame(self):
        """A linha do YouTube agora, entre duas leituras do UIA.

        O relogio avanca com `monotonic()` a partir do ancora da ultima leitura
        (`_youtube` grava-o quando le' o relogio do player). O ancora EXPIRA: um
        video pausado ha' cinco segundos nao pode continuar a revelar palavras
        por inercia -- se o UIA parou de responder, o ecra congela onde esta',
        que e' o honesto, em vez de inventar uma revelacao que ninguem viu.
        """
        anchor = getattr(self, '_yt_anchor', None)
        track = getattr(self, '_yt_track', None)
        if not anchor or not track:
            return None
        base_t, base_mono = anchor
        elapsed = time.monotonic() - base_mono
        if elapsed < 0 or elapsed > self.YT_ANCHOR_MAX_S:
            return None
        lines = self._yt_lines(track, base_t + elapsed)
        if not lines:
            return None
        # UMA ETIQUETA PROPRIA (2026-11-02): com `src=external:youtube:track`
        # aqui tambem, um quadro da FAIXA e um quadro da PINTURA eram
        # indistinguiveis no log -- e a auditoria nao podia nomear o produtor.
        return ('external:youtube:liveframe', lines)

    def _yt_cue_payload(self):
        """O cue do player COM O RELOGIO DELE, para a janela nativa (2026-11-03).

        PORQUE E' QUE ISTO EXISTE. O overlay tem desde hoje um motor que revela
        palavra a palavra contra o relogio do PROPRIO player (`caption_overlay.
        _PlayerCue`), mas o payload que ele recebia era so' texto: sem `cue` ele
        desenha o cue inteiro no instante da chegada. MEDIDO no log do dono: o
        relogio do UIA salta de segundo em segundo, portanto a frase entrava de
        uma vez e ficava parada -- o oposto de 1:1.

        O PAR QUE O OVERLAY QUER e' (instante do video, monotonic da leitura), e
        `_yt_anchor` ja' e' exactamente isso `(t, monotonic)`, gravado nos tres
        ramos do `_tick` que servem um cue. As `rows` seguem a forma de
        `youtube_reveal.rows_from_cues`, com cada palavra no seu `tOffsetMs`.

        A JANELA E' CURTA DE PROPOSITO: a faixa de um video longo tem milhares
        de cues e o overlay so' precisa dos vizinhos do instante lido; mandar a
        faixa toda por cue seria pagar o payload inteiro a cada segundo.
        """
        anchor = getattr(self, '_yt_anchor', None)
        track = getattr(self, '_yt_track', None)
        if not anchor or not track:
            return None
        try:
            base_t, base_mono = float(anchor[0]), float(anchor[1])
        except Exception:                 # noqa: BLE001
            return None
        try:
            import youtube_reveal
            rows = youtube_reveal.rows_from_cues(track.get('cues') or ())
        except Exception as exc:          # noqa: BLE001
            log('YOUTUBE_CUE_PAYLOAD_FAILED error=%r' % (exc,))
            return None
        rows = [r for r in rows
                if (r.get('end') is None or float(r['end']) >= base_t - 1.0)
                and float(r.get('start') or 0.0) <= base_t + 3.0]
        if not rows:
            return None
        return {'rows': rows, 't': base_t, 'at': base_mono}

    def _yt_lines(self, track, t):
        """As linhas que o YouTube desenha em `t` -- DUAS, nao uma.

        O DONO, 2026-10-22: *"e tambem ter o display 1:1 … igual o youtube"*.
        O payload do YouTube declara a janela em `wpWinPositions[1]`
        (`rcRows: 2`, `ccCols: 40`) e mediu-se duas linhas vivas ao mesmo tempo em
        **94 %** de um video de 33,8 s. O caminho vivo devolvia `[text]`, um cue so,
        e por isso o ecra do Sotto nunca podia igualar o do YouTube mesmo com a
        tabela certa. `youtube_window.live_lines` e a regra; `cue_at` fica como
        ultimo recurso para uma track sem cues sobrepostos.
        """
        cues = track.get('cues') or ()
        try:
            import youtube_window
            # A REVELACAO PALAVRA-A-PALAVRA (2026-10-26). `revealed_lines` e a MESMA
            # janela de `live_lines`, com cada linha cortada no relogio do proprio
            # YouTube (`tOffsetMs` no cue). O dono, verbatim: *"e pra surgir palavras,
            # quebrar linhas, usar o timing de nova linha ou nao, igual o youtube."*
            # Cue sem relogio devolve o texto inteiro -- nunca uma revelacao inventada.
            lines = youtube_window.revealed_lines(cues, t, 2)
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_WINDOW_FAILED error={exc!r}')
            lines = []
        if lines:
            # B5 (dono: *"coisa duplicada"*): a regra e os casos medidos vivem em
            # `youtube_window.collapse_growth`, onde sao testaveis sem a app.
            return youtube_window.collapse_growth(lines)
        try:
            import youtube_captions
            one = youtube_captions.cue_at(cues, t)
        except Exception:  # noqa: BLE001
            one = None
        text = str((one or {}).get('text') or '').strip()
        return [text] if text else []

    def _yt_forget(self, reason, urgent=False):
        """The real track has nothing for us right now."""
        if reason != self.yt_reason:
            self.yt_reason = reason
            log(f'YOUTUBE_TRACK_STATE reason={reason} urgent={str(urgent).lower()}')
        if self.yt_cue:
            self.yt_cue = ''
        # NADA PARA MOSTRAR TIRA OS PIXELS (dono, 2026-10-30: *"e' pra limpar o
        # display e comecar a dar display na legenda atual"*).
        blank = getattr(self, '_blank_caption_window', None)
        if blank is not None:
            blank('yt-forget:%s' % reason)
        return urgent

    #: Quanto tempo o id do video vale sem ser lido outra vez (ver _youtube_video_id).
    #: 30 s, com invalidação pelo TÍTULO da janela: navegar muda o titulo do
    #: YouTube, e mesmo sem mudar, meio minuto de cache nao esconde um video novo.
    YT_VIDEO_TTL_S = 30.0

    def _youtube_video_id(self, hwnd, uia, UIA):
        """The 11-character id of the video playing in this window, or ""."""
        if not hwnd:
            return ''
        try:
            import external_subs
            import youtube_captions
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_CAPTIONS_UNAVAILABLE error={exc!r}')
            return ''
        # O VIDEO ID NAO MUDA A CADA TICK, E LER A BARRA DE ENDERECO CUSTA CARO.
        # MEDIDO com cProfile em 2026-11-02 23:13 (`_main/_yt-cprofile.txt`): de
        # 124 ms de `_youtube`, **119 ms** eram `external_subs.edit_values` -- a
        # varredura dos controlos Edit do Chrome para achar a barra de endereco.
        # Ela e' o que sobrava dos 109-500 ms do laco; o desenho custa 16 ms. O id
        # fica em cache por janela e so' volta a ser lido quando o TITULO muda (uma
        # navegacao muda o titulo do YouTube) ou quando o TTL expira.
        key = int(hwnd or 0)
        try:
            import external_subs as _ext
            title = _ext._window_title(hwnd)
        except Exception:  # noqa: BLE001
            title = ""
        # O CACHE VALE PELO TITULO, NAO PELO HWND (2026-11-03, MEDIDO). O `hwnd`
        # aqui e' o da janela em primeiro plano, que muda de tick para tick quando
        # o dono toca em qualquer sitio; com o hwnd na chave o cache nunca servia e
        # CADA tick pagava a varredura dos `Edit` do Chrome -- medido no log desta
        # sessao: `phases={'declared': 156.0, 'painted': 172.0}`, ou seja, o id era
        # 90% da leitura, e uma vez `10281.0` (dez segundos!) com o desenho a
        # espera. O titulo do YouTube muda quando se navega, que e' exactamente a
        # unica coisa que invalida o id.
        cached = getattr(self, "_yt_vid_cache", None)
        if cached and time.monotonic() - cached[3] <= self.YT_VIDEO_TTL_S:
            # O TITULO VAZIO NAO INVALIDA NADA (2026-11-03, MEDIDO). O `hwnd` e' o
            # da janela em PRIMEIRO PLANO, e ela alterna: um tick le' o titulo do
            # Chrome, o seguinte le' "" porque quem esta' a frente e' outra janela.
            # Com o titulo na comparacao, os dois ticks escreviam caches um do
            # outro e CADA UM pagava a varredura dos `Edit` (94 ms medidos,
            # `YOUTUBE_VID_SCAN ms=94.0 hits=1`). Titulo vazio = "nao sei se mudou":
            # vale o ultimo id por 5 s; um titulo DIFERENTE e' navegacao e varre.
            if not title:
                if time.monotonic() - cached[3] <= 5.0:
                    return cached[2]
            elif cached[1] == title:
                return cached[2]
        # A FALHA TAMBEM SE LEMBRA (2026-11-03). Sem isto, uma janela em que a
        # varredura NAO acha id (a barra de endereco escondida, outro perfil do
        # Chrome) pagava o preco inteiro a cada tick, para sempre. Meio segundo de
        # memoria da falha e' invisivel para um video e corta o custo por 8.
        miss = getattr(self, "_yt_vid_miss", None)
        if miss and miss[0] == title and time.monotonic() - miss[1] <= 0.5:
            return ''
        _scan_t = time.monotonic()
        try:
            values = external_subs.edit_values(hwnd, uia, UIA)
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_EDIT_VALUES_FAILED error={exc!r}')
            return ''
        # QUEM PAGA A VARREDURA, E DE QUE TITULO (2026-11-03): o cache vale pelo
        # titulo, e sem esta linha um `declared` caro e' indistinguivel de um
        # titulo que muda a cada tick.
        if time.monotonic() - getattr(self, '_yt_vid_scan_logged', 0.0) > 5.0:
            self._yt_vid_scan_logged = time.monotonic()
            log('YOUTUBE_VID_SCAN ms=%.1f hwnd=%s title=%r hits=%d'
                % ((time.monotonic() - _scan_t) * 1000.0, key, title[:60],
                   len(values or [])))
        for value in values:
            try:
                vid = youtube_captions.video_id_from_url(value)
            except Exception:
                vid = None
            if vid:
                self._yt_vid_cache = (key, title, vid, time.monotonic())
                return vid
        self._yt_vid_miss = (title, time.monotonic())
        return ''

    def _yt_prof(self, stage, t0, detail=""):
        """`YT_PROF stage=.. ms=..` -- so' com `SOTTO_YT_PROFILE=1`.

        O GARGALO DEVE SER UM NUMERO, NAO UMA SUSPEITA (2026-11-02). A leitura
        do laco externo custava 0,4-1,2 s por tick no dono e tres caches
        sucessivos nao a moveram: cada estagio mede-se aqui, e o que sobra e'
        o que ainda nao foi instrumentado.
        """
        if os.environ.get("SOTTO_YT_PROFILE") != "1":
            return
        try:
            import youtube_captions as _ycp
            if _ycp.PROF_HOOK is None:
                _ycp.PROF_HOOK = log
        except Exception:  # noqa: BLE001
            return
        try:
            log('YT_PROF stage=%s ms=%.1f%s' % (stage, (time.monotonic() - t0) * 1000.0, (' '+detail) if detail else ''))
        except Exception:  # noqa: BLE001
            pass

    def _ensure_clock_sampler(self):
        """O RELOGIO DO PLAYER NAO PODE SER O TICK (2026-11-02).

        MEDIDO no dono, com o video a tocar: o desenho custa 47-172 ms, mas a
        leitura do relogio custava 391-1375 ms (a busca por ControlType=Text
        percorre a arvore do Chrome inteira), e o laco externo e' SERIAL: cada
        leitura de relogio empurra a leitura da legenda. Com o relogio numa
        thread propria a cadencia do desenho passa a depender so' do que ele
        custa, e o instante continua a ser medido -- cada amostra tem a sua
        hora, e `_youtube_time` interpola entre amostras (o erro maximo e' o
        passo da amostra, nao um numero inventado).
        """
        if getattr(self, "_yt_clock_thread", None) is not None:
            return
        self._yt_clock_lock = threading.Lock()
        self._yt_clock_last = None  # (t, monotonic)
        self._yt_clock_dur = None

        def _loop():
            try:
                import external_subs
                import youtube_captions as _yc
                UIA2, uia2 = external_subs._uia()
            except Exception as exc:  # noqa: BLE001
                log(f'YOUTUBE_CLOCK_UNAVAILABLE error={exc!r}')
                return
            log('YOUTUBE_CLOCK_STARTED interval_s=0.40')
            while not self.stop_event.is_set():
                hwnd = int(getattr(self, "target_hwnd", 0) or 0)
                # COM A CDP A LER O RELOGIO, ESTA AMOSTRA E' SO' DESPERDICIO
                # (2026-11-03, MEDIDO). `player_time` e' UIA: 391-1375 ms por
                # amostra (o comentario abaixo ja' dizia), e o `video.currentTime`
                # chega a 12 Hz no snapshot da fonte, a 2-5 ms. Pior: esta thread
                # era um dos clientes UIA que apareceram PRESOS no `UI_HUNG_FRAME`
                # (`youtube_captions.player_time_detail`), e um cliente UIA preso
                # arrasta o renderer do Chrome. Com foto fresca, nao se pergunta.
                if hwnd and self._yt_snap_video() is None:
                    try:
                        _t0 = time.monotonic()
                        t = _yc.player_time(uia2, UIA2, hwnd,
                                            duration=self._yt_clock_dur)
                        self._yt_prof("clock-sample", _t0)
                        if t is not None:
                            with self._yt_clock_lock:
                                prev = self._yt_clock_last
                                self._yt_clock_prev = prev
                                self._yt_clock_last = (float(t), time.monotonic())
                    except Exception:  # noqa: BLE001
                        pass
                self.stop_event.wait(0.40)

        self._yt_clock_thread = threading.Thread(
            target=_loop, name="yt-clock", daemon=True)
        self._yt_clock_thread.start()

    def _yt_snap_video(self):
        """O id do video da foto MAIS RECENTE, ou None. Sem custo de UIA.

        Existe para o laco poder responder "ainda estou a ler este video do
        YouTube" sem voltar a perguntar a' arvore de acessibilidade (60-140 ms,
        e uma vez 6,8 s nesta maquina). Quem consome isto re-pergunta quando o
        resultado e' None -- e e' None exactamente quando a pagina muda.
        """
        src = getattr(self, '_yt_cdp_source', None)
        if not src or src is False:
            return None
        try:
            snap = src.snapshot(max_age=1.5)
        except Exception:                     # noqa: BLE001
            return None
        if not snap:
            return None
        return str(snap.get('videoId') or '') or None

    def _youtube_time(self, hwnd, uia, UIA, duration):
        """Where the video is, in seconds -- or None when it is not known.

        None is NOT "the video is paused": it is "we do not know", and the
        caller keeps the ASR running.
        """
        self._yt_clock_dur = duration
        # O RELOGIO DA CDP PRIMEIRO (2026-11-03, MEDIDO): `video.currentTime` pela
        # CDP e' o MESMO relogio do player, custa 2-5 ms e continua a andar com a
        # aba escondida -- 56,9 s em 57 s de relogio de parede enquanto o DOM da
        # legenda estava congelado. O caminho por UIA le' o texto do relogio na
        # arvore de acessibilidade, que nessa mesma janela nao atualizava.
        cdp_clock = getattr(self, 'yt_cdp_clock', None)
        if cdp_clock is not None:
            base_t, base_mono = cdp_clock
            age = time.monotonic() - base_mono
            # EXTRAPOLA NO MAXIMO 0,5 s: um renderer adiado por 3 s nao pode
            # empurrar a legenda 3 s para a frente do que se ve'.
            if 0.0 <= age <= 2.0:
                self._yt_clock_last = (float(base_t), time.monotonic())
                return float(base_t) + min(age, 0.5)
        last = getattr(self, "_yt_clock_last", None)
        if last is not None:
            age = time.monotonic() - last[1]
            if 0.0 <= age <= 2.0:
                prev = getattr(self, "_yt_clock_prev", None)
                # PARADO NAO ANDA (medido: 700.0 quatro vezes seguidas com o
                # video em pausa). Duas amostras separadas >= 0.3 s com o MESMO
                # instante significam "ninguem se mexeu": interpolar punha a
                # legenda 1-2 s a frente do que o player desenha.
                if prev is not None and (last[1] - prev[1]) >= 0.3 and abs(last[0] - prev[0]) < 0.05:
                    return last[0]
                return last[0] + age
        _t0 = time.monotonic()
        _t = None
        try:
            import youtube_captions
            _t = youtube_captions.player_time(uia, UIA, hwnd,
                                              duration=duration)
            if _t is not None:
                self._yt_clock_last = (float(_t), time.monotonic())
            return _t
        except Exception as exc:  # noqa: BLE001
            log(f'YOUTUBE_TIME_FAILED error={exc!r}')
            return None
        finally:
            self._yt_prof("time", _t0, "hwnd=%s t=%s" % (hwnd, _t))

    def _tick(self, got, yt_mode=False):
        now = time.monotonic()
        # O QUADRO QUE O ECRA RECEBERIA, DESENHADO OU NAO (2026-11-02).
        # `EXTERNAL_CAPTION_DRAWN` so' existe com o overlay LIGADO, e o dono
        # desligou-o; uma auditoria que so' mede com a legenda ligada nao pode
        # julgar a CADEIA. Esta linha e' o que o `_main/caption-frame-audit.py`
        # le, e ela custa uma comparacao de strings: diz o que o `_tick` decidiu,
        # com o produtor ao lado (`src=`).
        if got:
            source, lines = got[0]
            if str(source).startswith("external:youtube"):
                # A JANELA EM QUE O PLAYER MANDA (ver `push_caption_to_window`).
                #
                # NO SHELL, E NAO AQUI (medido 2026-11-03). A guarda que impede o
                # ASR de pintar por cima do player le' `self._yt_owner_until` no
                # `SottoShell` (`push_caption_to_window`, campo lido em exactamente
                # UM sitio); este `_tick` pertence ao `ExternalCaptionWatcher`, e
                # escrevia o carimbo no WATCHER. Resultado: o shell lia sempre
                # `0.0`, a guarda nunca disparava, e a frase do ASR continuava a
                # substituir a linha do YouTube -- que e' o defeito que o dono
                # fotografou em 2026-11-03 ("duas legendas diferentes no mesmo
                # ecra") e cuja cura estava escrita e desligada por um `self`.
                # O `self.shell` e' a ponte que este mesmo `_tick` ja' usa para
                # entregar a linha (`self.shell.external_caption(...)`).
                shell = getattr(self, "shell", None)
                if shell is not None:
                    try:
                        shell._yt_owner_until = time.monotonic() + 2.0
                    except Exception:                            # noqa: BLE001
                        log("YT_OWNER_STAMP_FAILED error=AttributeError")
            _rows_now = list(lines or ())
            _key = '\u2028'.join(_rows_now)
            if _key != getattr(self, "yt_frame_key", None):
                self.yt_frame_key = _key
                log('YT_FRAME src=%s rows=%d lines=%r'
                    % (source, len(_rows_now), _rows_now))
            line = lines[-1] if lines else ''
            # THE PLAYER'S WINDOW IS ROWS, NOT ONE LINE (2026-10-29). `lines`
            # is one cue per row (youtube_reveal.window_by_paint); taking only
            # `lines[-1]` was the measured reason a row YouTube draws never
            # reached the overlay. Non-YouTube readers keep the single line.
            rows = list(lines) if (yt_mode and lines) else None
            if line:
                self.last_seen = now
                self.shell.external_captions_available = True
                if line != self.last_line or (rows or []) != self.last_rows:
                    if self.last_line and not self.finalized:
                        self.shell.external_caption(self.last_line, self.last_source,
                                                    final=True, instant=bool(yt_mode),
                                                    rows=self.last_rows,
                                                    cue=self._yt_cue_payload())
                    self.last_line = line
                    self.last_source = source
                    self.last_rows = rows or []
                    self.last_change = now
                    self.finalized = False
                    self.shell.external_caption(line, source, final=False,
                                               instant=bool(yt_mode), rows=rows,
                                               cue=self._yt_cue_payload())
                elif not self.finalized and now - self.last_change >= self.STABLE_FINAL_S:
                    self.shell.external_caption(line, source, final=True,
                                               instant=bool(yt_mode), rows=rows,
                                               cue=self._yt_cue_payload())
                    self.finalized = True
                return
        # THE SILENCE ONLY RELEASES FOR THE PAGE READER. That reader knows
        # the player stopped only when the PAGE stops having text. The REAL
        # TRACK knows better: the track is still valid, the clock is still
        # readable, and the cue is there -- the video is PAUSED, and a paused
        # video is not a dead player. MEASURED 2026-10-20: with the release
        # on a timer, every 30 s of paused video cost the owner a 1.2 GB
        # model load. On the real-track path the VALIDITY of the track
        # decides, and the track's validity is judged in `_youtube`.
        if (not yt_mode and self.last_line
                and (now - self.last_seen) >= self.RELEASE_S):
            self._release('no-caption')
        # A FAIXA NAO PINTA NADA: O MICROFONE VOLTA (2026-11-02). MEDIDO no dono:
        # BRIDGE_STOP reason=external-captions as 18:52:13, spawns=1 ate' ao fim --
        # 8 min sem transcricao ao vivo enquanto o ramo do YouTube so' APAGAVA a
        # janela. A prova e' A3/A4 de `_main/reveal-park-oracle.py`.
        elif yt_mode and not self.last_line and self.last_seen:
            # O silencio do YouTube e' LONGO por desenho: entre duas cues ha' buracos
            # de 6 a 16 s medidos, e um piso curto poria o micro em treadmill.
            if (now - self.last_seen) >= self.YT_RELEASE_S:
                self._release('yt-no-line')

    def _release(self, reason):
        if self.last_line:
            if not self.finalized:
                self.shell.external_caption(self.last_line, self.last_source, final=True)
            log(f'EXTERNAL_CAPTIONS_RELEASED reason={reason}')
            self.last_line = ''
            self.last_rows = []
            self.last_source = ''
            self.finalized = False
        self.shell.external_captions_active = False
        self.shell.external_captions_available = False
        # O PISO DO ESTACIONAMENTO COMECA DE NOVO a cada janela (2026-11-02): um
        # video que volta a servir linhas abre uma janela nova, e o worker so' e'
        # estacionado depois do mesmo rato -- nunca "herdado" da janela anterior.
        self.shell._external_since = None
        self.shell._external_park_deferred_logged = False
        try:
            self.shell.on_external_captions_released()
        except Exception as exc:  # noqa: BLE001
            log(f'EXTERNAL_CAPTIONS_RESUME_FAILED error={exc!r}')


#: `SetLayeredWindowAttributes` flags. LWA_COLORKEY makes ONE RGB value fully
#: transparent; LWA_ALPHA would make the whole window translucent, which is a
#: different effect and would dim the caption text too.
LWA_COLORKEY = 0x00000001


def set_layered_color_key(hwnd, colorref: int) -> bool:
    """Make `colorref` (0x00BBGGRR) fully transparent on a LAYERED window.

    WHY THIS EXISTS AND NOT JUST `form.TransparencyKey`: WinForms applies the
    key only to a window that already carries `WS_EX_LAYERED`, and the caption
    WebView2
    caption window was created without that style -- the layered bit was added
    later, only after the key had already been set. The
    result on the owner's screen (2026-10-17: *"qualquer tentativa de deixar um
    background transparente simplesmente deixa tudo rosa"*) is the page's own
    `#ff00ff` key colour painted as a solid PINK slab: the key existed on the
    form before the layered bit did, and the composition never had a reason to
    punch it out.

    Calling the Win32 primitive directly, AFTER `WS_EX_LAYERED` is in place, is
    deterministic: the colour key is matched against the composited window,
    which is exactly the surface WebView2 paints into.
    """
    try:
        user32.SetLayeredWindowAttributes.argtypes = [
            wt.HWND, ctypes.c_uint32, ctypes.c_ubyte, ctypes.c_uint32]
        user32.SetLayeredWindowAttributes.restype = ctypes.c_bool
        ok = user32.SetLayeredWindowAttributes(
            hwnd, ctypes.c_uint32(colorref), ctypes.c_ubyte(0),
            ctypes.c_uint32(LWA_COLORKEY))
        return bool(ok)
    except Exception:  # noqa: BLE001
        return False


def make_click_through(hwnd, enabled: bool) -> int:
    """WS_EX_TRANSPARENT on/off — the Win32 spelling of click-through.

    Electron spells this `setIgnoreMouseEvents(true, {forward: true})`.
    WebView2 has no equivalent and WinForms has none either, but the extended
    style is what that call ultimately sets, and it still lets mouse *move*
    events reach the page, which is how the page asks for interactivity over
    its own controls.
    """
    if enabled:
        return set_ex_style(hwnd, add=WS_EX_TRANSPARENT)
    return set_ex_style(hwnd, remove=WS_EX_TRANSPARENT)


#: The WebView2 child window's class prefix. Every WebView2 host on Windows uses
#: it, pywebview's WinForms/EdgeChromium backend included; it is the HWND whose
#: surface actually holds the page.
WEBVIEW_CHILD_CLASS = 'Chrome_WidgetWin'


#: WS_VISIBLE, the one style bit that means "this window maps itself when its
#: parent maps". `IsWindowVisible` returns the AND of that bit over the window
#: and every ancestor, so it answers FALSE for a child whose parent is hidden —
#: measured on this box (2026-10-09): `ShowWindow(child)` on a hidden parent
#: sets WS_VISIBLE on the child while `IsWindowVisible` stays FALSE until the
#: parent is mapped. Reading the style bit directly is the only way to classify
#: a child BEFORE the form is shown, which is exactly what the P0 reordering
#: below needs.
WS_VISIBLE = 0x10000000
GWL_STYLE = -16


def hudson_style_bit(hwnd) -> bool:
    """True when THIS window carries WS_VISIBLE, parent state irrelevant.

    The honest pre-map channel: a child can carry WS_VISIBLE and still report
    `IsWindowVisible() == False` purely because its parent is hidden, so a
    census taken before the map would call that child `failed`. Reading the
    style bit on the child alone cannot make that mistake.
    """
    try:
        style = user32.GetWindowLongW(wt.HWND(hwnd), GWL_STYLE)
        return bool(style & WS_VISIBLE)
    except Exception:  # noqa: BLE001 -- a dead hwnd must not raise here
        return False


def webview_child_hwnds(hwnd) -> list:
    """Every WebView2 HWND under this top-level window, children AND grandchildren.

    `EnumWindows` CANNOT answer this: it lists TOP-LEVEL windows only, and the
    WebView2 HWND is a child of the shell's form. Measured 2026-10-09 — the
    first attempt at this census used `EnumWindows`, found only the form and
    the 1x1 GDI+ hook, and concluded "there is no WebView2 child", which was a
    false negative produced by the instrument. The two levels are walked because
    pywebview interposes its own `WindowsForms10` host between the form and the
    browser window.
    """
    found = []

    def _note(h, level):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(wt.HWND(h), buf, 256)
        if buf.value.startswith(WEBVIEW_CHILD_CLASS):
            found.append((int(h), level))

    def _kid(k, _lp):
        _note(k, 1)

        def _grand(g, _l2):
            _note(g, 2)
            return True

        user32.EnumChildWindows(
            wt.HWND(k),
            ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)(_grand),
            0)
        return True

    user32.EnumChildWindows(
        wt.HWND(hwnd),
        ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)(_kid),
        0)
    return found


def show_webview_children(hwnd) -> dict:
    """Show the WebView2 child HWNDs — WHILE the form is still hidden.

    WHY THE ORDER MATTERS (the P0 of the whole session): the owner pressed
    Alt+C and saw a solid-colour strip, then the UI ONE FRAME LATER, and his
    words for it were "como se fosse realmente renderizando um apos o
    outro". A user32 `ShowWindow` of the FORM maps the window immediately,
    and WinForms then creates the first frame from the FORM's own background
    before the browser child has anything painted. So the child must already
    carry WS_VISIBLE when the map lands — that is what showing it before the
    map buys, and it is the only part of the sequence this function owns.

    ── WHY THIS EXISTS, MEASURED 2026-10-09 ───────────────────────────────────
    The owner reported the app as a blank WHITE slab and kept being told the
    DOM, the CSS and the computed backgrounds were fine — all of which was true
    and all of which was beside the point. A child-window census taken during
    Alt+C (`EnumChildWindows`, two levels deep) shows the actual state:

        form (WindowsForms10...)  vis=True   1040x150 @ (440,870)
          Chrome_WidgetWin_0      vis=False  1040x150 @ (440,870)

    The WebView2 HWND is HIDDEN while the shell's own WinForms form is VISIBLE,
    so what reaches the screen is the FORM's background — the WinForms default,
    WHITE — and the panel is behind it, painted and correct, unpainted to the
    eye.

    The mechanism is the startup-flash cure itself: `_gate_form_show` REFUSES
    pywebview's `form.Show()` at navigation start, because that call maps a
    transparent window the owner never asked for. But pywebview shows the
    WebView2 child TOGETHER with the form, so refusing it also left the child
    hidden. The shell then maps the FORM with raw user32 (`SW_SHOWNOACTIVATE`
    in `show_panel`, `SW_SHOW+FOREGROUND` in `show_strip`/`show_side`), which
    shows the form and nothing else. On the `--show` path the gate ALLOWS the
    show (`show_requested=True`), so pywebview shows both and that path has
    always painted — which is exactly why every "does it paint?" probe run with
    `--show` came back GREEN while the owner's own Alt+C came back white.

    The fix is to show the child explicitly, after the form. `SW_SHOWNOACTIVATE`
    so the overlay still never steals focus, which is the invariant
    `show_panel`'s comment above is protecting.

    Returns a dict so a caller logs ONE line and a test can assert the pair
    without a WebView2 present (`shown` is empty when there is no window).
    """
    shown, already, missing = [], [], []
    # WHICH CHANNEL CLASSIFIES THE ANSWER. `IsWindowVisible` answers FALSE
    # for a child whose PARENT is hidden, because it checks WS_VISIBLE on the
    # window AND every ancestor (measured on this box, 2026-10-09) — so it
    # reports "hidden" for a child that in fact carries WS_VISIBLE and paints
    # the instant the form is mapped. `hudson_style_bit` reads the child's OWN
    # state instead, which is the only honest channel while the form is hidden.
    parent_visible = window_visible(hwnd)

    def _visible(child_hwnd):
        if parent_visible:
            return bool(user32.IsWindowVisible(wt.HWND(child_hwnd)))
        return hudson_style_bit(child_hwnd)

    for child_hwnd, level in webview_child_hwnds(hwnd):
        if _visible(child_hwnd):
            already.append(child_hwnd)
            continue
        user32.ShowWindow(wt.HWND(child_hwnd), SW_SHOWNOACTIVATE)
        if _visible(child_hwnd):
            shown.append(child_hwnd)
        else:
            missing.append(child_hwnd)
    return {'shown': shown, 'already': already, 'failed': missing}


def transparency_hack(shell) -> bool:
    """Re-run the compositing call pywebview would have made for us.

    ── AND THE COMPOSITING HACK, WHICH IS NOT OPTIONAL ───────────────────────
    # pywebview makes a transparent WebView2 composite with exactly one call:
    # `platforms/edgechromium.py:347-349`, inside `on_navigation_start` --
    #   if self.pywebview_window.transparent:
    #       self.form.Show()
    #       self.form.Activate()
    # There is no other mechanism. Our `_gate_form_show` shadows `form.Show`
    # with `guarded_show`, which returns WITHOUT mapping unless
    # `self.args.show or self.visible or opacity < 1.0` -- so in every launch
    # that is not `--show` the hack is REFUSED on every navigation, and the
    # WebView2 never composites. The page is otherwise perfectly alive: the
    # bridge answers, `panel.js` runs, the CSS is computed, captions arrive.
    # What reaches the glass is the FORM's own background, which is why the
    # owner saw a single flat block where the panel should be.
    #
    # `--show` always worked because `args.show` makes the guard allow the call,
    # and that is the whole explanation for why every `--show` probe measured
    # "PAINTED, 65 distinct colours" while the owner's own Alt+C measured one
    # colour. The instrument was not wrong; it was measuring the other path.
    #
    # So when the shell maps the panel it must run the same call. `Activate()`
    # is deliberately NOT repeated: it would take focus from whatever the owner
    # is typing into, and `Show()` is the half that composites.
    """
    # ── AND THE COMPOSITING HACK, WHICH IS NOT OPTIONAL ──────────────────────────────────────────
    form_show = None
    form = None
    hacked = False
    if shell is not None:
        form = getattr(shell, 'form', None)
        if form is None:
            try:
                form = shell._form()
            except Exception:
                form = None
    if form is not None:
        try:
            form_show = form.Show
        except Exception:
            form_show = None
    if form_show is not None:
        # The guard reads `shell.visible`, so the honest way to ask it for
        # permission is to BE visible for the duration of the call.
        previous_visible = bool(getattr(shell, 'visible', False))
        shell.visible = True
        hacked = False
        try:
            # ON THE UI THREAD, NOT THIS ONE. `form.Show()` fires
            # `NavigationStarting`, which touches `CoreWebView2Controller`, and
            # that class raises `InvalidOperationException('CoreWebView2Controller
            # members can only be accessed from the UI thread')` from the hotkey
            # thread. MEASURED: the first version of this call ran on the
            # caller's thread and logged exactly that exception, so the hack
            # never ran and the panel stayed a solid block.
            ui = getattr(shell, '_ui', None)
            post = getattr(shell, '_post', None)
            if ui is not None:
                # THE WAIT IS SHORT AND THE FALLBACK IS A POST (2026-10-21).
                # The caller here is the HOTKEY thread -- the thread that owns
                # the owner's ONLY control -- and `_ui`'s default budget is
                # TEN SECONDS (`UI_MARSHAL_TIMEOUT_S`). A busy UI thread
                # therefore made an Alt+C wait ten seconds for a window that
                # was already on its way: the owner's *"abrir o sotto trava"*.
                # So: wait a quarter of a second for the composite, and if the
                # UI thread did not take it, POST it (fire-and-forget, on the
                # UI thread, where it has to run anyway) and return. The
                # composite still happens; the control thread stops waiting.
                answer = ui(form_show, TRANSPARENCY_HACK_WAIT_S)
                if isinstance(answer, NoAnswer):
                    if post is not None and post(form_show):
                        log('FORM_SHOW_TRANSPARENCY_HACK posted '
                            '(the UI thread was busy; the composite runs '
                            'when it breathes) wait_s=%s'
                            % TRANSPARENCY_HACK_WAIT_S)
                    else:
                        log('FORM_SHOW_TRANSPARENCY_HACK_DEFERRED '
                            'wait_s=%s reason=no-post' % TRANSPARENCY_HACK_WAIT_S)
                hacked = True
            else:
                form_show()
                hacked = True
        except Exception as exc:  # noqa: BLE001 -- a failed map must not kill
            # the owner's only control.
            log(f'FORM_SHOW_TRANSPARENCY_HACK_FAILED error={exc!r}')
            hacked = False
        finally:
            shell.visible = previous_visible
        if hacked:
            log("FORM_SHOW_TRANSPARENCY_HACK ran (pywebview edgechromium.py:348 "
                "re-run on the owner's ask, on the UI thread) - this is what "
                "makes a transparent WebView2 composite")
    return hacked


def ensure_webview_shown(hwnd, shell=None) -> dict:
    """Child-show THEN hack, and nothing in between — see both halves.

    The composed form kept for every caller that logs one line. Each half is
    a real function so a caller that must order them around something else
    (the P0: show the children before the map, hack after) can, and so a
    test can drive them one at a time. `ensure_webview_shown` alone has the
    OLD order — child-show inside the map — which is exactly the order the
    owner reported; prefer `show_webview_children` + `transparency_hack` in
    the deliberate sequence.
    """
    result = show_webview_children(hwnd)
    if shell is None:
        result['transparency_hack'] = False
        return result
    result['transparency_hack'] = transparency_hack(shell)
    return result


# The `OFFSCREEN = -32000` cure was REMOVED 2026-10-06 (see create_window):
# a window created off-screen never finishes the WebView2 panel navigation, so
# `_on_loaded` never runs and the shell HANGS. Do not reintroduce it.


def show_without_activating(hwnd) -> bool:
    return bool(user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE))


def hide_window(hwnd) -> bool:
    return bool(user32.ShowWindow(hwnd, SW_HIDE))


def window_visible(hwnd) -> bool:
    return bool(user32.IsWindowVisible(hwnd))


def set_topmost(hwnd) -> bool:
    """Uma so' implementacao: a chamada Win32 vive em `panel_focus`."""
    return _panel_focus.set_topmost(hwnd)


#: Exact Win32 signatures for the calls the strip lane makes. `SetWindowPos`
#: without declared argtypes fails SILENTLY with `last_error=1400` (measured,
#: strip-surface): `HWND_TOPMOST=-1` must travel as a 64-bit HWND, not a
#: 32-bit int default. Every call below goes through these, never bare.
user32.ShowWindow.restype = wt.BOOL
user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
user32.IsWindowVisible.restype = wt.BOOL
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
user32.SetWindowPos.restype = wt.BOOL
user32.SetWindowPos.argtypes = [wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                                ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.SetForegroundWindow.restype = wt.BOOL
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.AttachThreadInput.restype = wt.BOOL
user32.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
user32.BringWindowToTop.restype = wt.BOOL
user32.BringWindowToTop.argtypes = [wt.HWND]


#: `SetWindowPos` insert-after for "move me, keep my Z order". `HWND_TOPMOST`
#: re-asserts topmost (the strip must stay above the game); `HWND_TOP` (0) is
#: for geometry moves that must NOT change the Z slot.
HWND_TOP = 0
SWP_SHOWWINDOW = 0x0040


def pointer_lock_state():
    """O app em primeiro plano tem o rato preso? -- a politica vive em `panel_focus`."""
    return _panel_focus.pointer_lock_state(log=log)


def foreground_unlock(hwnd):
    """Mapa o painel e diz o que fez ao primeiro plano (ver `panel_focus`)."""
    return _panel_focus.foreground_unlock(hwnd, log=log)


def strip_geometry(work, height=STRIP_HEIGHT_FALLBACK, dock='bottom-centre'):
    """The bottom-centre caption band, CONTAINED in `work` (DIP).

    Kept a pure function for the same reason `dock_right` is: the output is
    inside the work area whatever the work area is, including degenerate
    rectangles and a work area shorter than the band.
    """
    w = max(0, work['width'])
    h = max(0, work['height'])
    want_height = int(height) if isinstance(height, (int, float)) \
        else STRIP_HEIGHT_FALLBACK

    band_width = min(STRIP_WIDTH_MAX,
                     max(STRIP_WIDTH_MIN, round(w * STRIP_WIDTH_FRACTION)))
    band_width = min(band_width, w)
    band_height = max(1, min(want_height, h))

    x = work['x'] + (w - band_width) // 2
    y = work['y'] + h - band_height - STRIP_BOTTOM_MARGIN

    geometry = {
        'workX': work['x'],
        'workY': work['y'],
        'workWidth': w,
        'workHeight': h,
        'x': max(work['x'], round(x)),
        'y': max(work['y'], round(y)),
        'width': max(1, round(band_width)),
        'height': band_height,
        'margin': STRIP_BOTTOM_MARGIN,
        'docked': dock,
    }
    # Containment is an invariant, not a hope — the same rule `dock_right` keeps.
    geometry['x'] = min(geometry['x'], work['x'] + w - geometry['width'])
    geometry['y'] = min(geometry['y'], work['y'] + h - geometry['height'])
    return geometry
def clamp_geometry(rect, work):
    """Fit a SAVED rect into the CURRENT work area; say whether it moved.

    This is the honest answer to "the resolution changed" — which was NOT
    measured for this lane and must not be invented. A saved rect is kept when
    it still fits, and is moved/resized into the work area when it does not; the
    caller logs the difference so a moved window is never a silent surprise.
    """
    w = max(0, work['width'])
    h = max(0, work['height'])
    want_width = max(1, min(int(rect.get('width') or 1), max(1, w)))
    want_height = max(1, min(int(rect.get('height') or 1), max(1, h)))
    x = max(work['x'], min(int(rect.get('x') or work['x']),
                          work['x'] + w - want_width))
    y = max(work['y'], min(int(rect.get('y') or work['y']),
                          work['y'] + h - want_height))
    clamped = {
        'workX': work['x'], 'workY': work['y'],
        'workWidth': w, 'workHeight': h,
        'x': x, 'y': y, 'width': want_width, 'height': want_height,
        'margin': 0, 'docked': str(rect.get('docked') or 'saved'),
    }
    moved = (x != int(rect.get('x') or x) or y != int(rect.get('y') or y)
             or want_width != int(rect.get('width') or want_width)
             or want_height != int(rect.get('height') or want_height))
    return clamped, moved
#: THE PLAYER'S OWN LEADING MARKERS. MEASURED 2026-10-18 on this box's own
#: log: 25 of the 219 `EXTERNAL_CAPTION_SENT` lines began with `>>`, and 31 of the
#: 9 937 painted captions carried it -- `">> That's all that."`, `">> Oh, oh my"`.
#: Two chevrons read as a doubled mark, which is the stray "2" the owner reported
#: verbatim ("ainda ta aparecendo um '2' do nada na legenda").
#:
#: Everything here is stripped from the FRONT of a line and only there. A
#: chevron inside a sentence is a real character and stays; `>` is not decoration.
LEAD_MARKER_RE = re.compile(
    r"^\s*(?:[>\u00bb\u203a]+\s*|\[\s*(?:music|aplausos?|risos?|riso|"
    r"s(?:om|ound)\s*effects?|sil(?:e|\u00e7ncia|encio)\s*)\]\s*|"
    r"[-\u2013\u2014]\s+)+")


def clean_external_text(text):
    """One player cue, with its leading marker removed. Never raises.

    A line that is ONLY a marker becomes the empty string, and `external_caption`
    drops it: a caption window that paints nothing is correct, a caption window
    that paints `">>"` is the bug.
    """
    try:
        raw = str(text or '')
    except Exception:  # noqa: BLE001
        return ''
    if not raw.strip():
        return ''
    try:
        return LEAD_MARKER_RE.sub('', raw).strip()
    except Exception:  # noqa: BLE001
        return raw.strip()


def extends_previous(old, new):
    """Is `new` the same sentence as `old`, with more words?

    THE PLAYER'S CUE IS CUMULATIVE, and that is the whole finding. Consecutive
    `EXTERNAL_CAPTION_SENT` lines from one video:

        "So, with the eyes of a nation"
        "So, with the eyes of a nation on them,"
        "FURIA seized their moment."
        "FURIA seized their moment. They run"

    Each cue repeats the previous one and adds a few words. Case is ignored
    because the player's own capitalisation drifts mid-sentence, and the
    comparison is on WORDS, so a trailing full stop or a missing space does not
    read as a new sentence.
    """
    try:
        o = str(old or '').split()
        n = str(new or '').split()
    except Exception:  # noqa: BLE001
        return False
    if not o or not n:
        return False
    if len(n) < len(o):
        return False
    return [w.lower() for w in o] == [w.lower() for w in n[:len(o)]]


#: The surfaces the ONE document can wear. The names are `app/panel/surface.js`'s
#: (`SURFACES`), and this shell refuses anything else instead of guessing.
SURFACE_NAMES = ('strip', 'panel')
def normalise_surface_name(name):
    """`'strip'`/`'panel'` from what a caller actually sent, else None.

    Mirrors `surface.js:39-46` on purpose, including its tolerance for the
    CSS-ish spellings a shell might copy out of the stylesheet
    (`surface--strip`, `surface-strip`). A name this file does not know is
    REFUSED — never silently treated as the panel, because a caller that sent
    `'strip '` and got a 900 px window would read as a layout bug.
    """
    value = str(name if name is not None else '').strip().lower()
    value = re.sub(r'^surface-+', '', value)
    return value if value in SURFACE_NAMES else None
def dock_strip(work, width=STRIP_WIDTH, height=STRIP_HEIGHT,
               margin=STRIP_MARGIN):
    """Dock a wide short strip to the bottom centre of `work`.

    The twin of `dock_right`: same pure-function contract (output contained
    in the work area whatever it is), same DIP units. `STRIP_HEIGHT` is the
    measured strip height; when the caller passes a non-number (panel asked
    for a height the CSS did not provide) the fallback is used and the use
    is logged by the caller. The strip never takes more than the full width
    minus margins, and never leaves the work area.
    """
    want_width = width if isinstance(width, (int, float)) else STRIP_WIDTH
    want_height = height if isinstance(height, (int, float)) else STRIP_HEIGHT
    if not isinstance(height, (int, float)):
        log(f'STRIP_HEIGHT_FALLBACK used={STRIP_HEIGHT_FALLBACK}')
        want_height = STRIP_HEIGHT_FALLBACK
    w = max(0, work['width'])
    h = max(0, work['height'])
    m = max(0, min(margin if isinstance(margin, (int, float)) else PANEL_MARGIN,
                   w / 8, h / 8))
    strip_width = min(want_width, max(0, w - 2 * m))
    strip_height = min(want_height, max(0, h - 2 * m))
    x = work['x'] + round((w - strip_width) / 2)
    y = work['y'] + h - strip_height - m
    geometry = {
        'workX': work['x'],
        'workY': work['y'],
        'workWidth': w,
        'workHeight': h,
        'x': max(work['x'], round(x)),
        'y': max(work['y'], round(y)),
        'width': max(1, round(strip_width)),
        'height': max(1, round(strip_height)),
        'margin': m,
        'docked': 'bottom-strip',
        # WHICH SURFACE this geometry is. Measured 2026-10-09: the shell resized
        # to 1040x150 on Alt+C while the document still wore
        # `data-surface="panel"` (DOMDUMP printed `body=1040x150 surface=panel`),
        # so the panel's own grid crushed `.captions` to zero height and
        # `.stripbar` never left `display:none`. It travels WITH the geometry so
        # `send_geometry` stays the plain one-line emitter it always was.
        'surface': 'strip',
    }
    geometry['x'] = min(geometry['x'], work['x'] + w - geometry['width'])
    geometry['y'] = min(geometry['y'], work['y'] + h - geometry['height'])
    return geometry


# ===========================================================================
# THE WINDOW'S FACE — the icon and the identity the taskbar groups by
#
# The owner's report, 2026-10-08, verbatim: "eu tambem nao gosto que aparece um
# icone de python quando eu aperto o painel". He is describing the truth: this
# shell runs under `pythonw.exe`, and pywebview's WinForms backend, when it is
# given no icon, copies the icon out of `sys.executable` into the form
# (`webview/platforms/winforms.py:243-251`):
#
#     if _state['icon'] and os.path.isfile(_state['icon']):
#         self.Icon = Icon(_state['icon'])
#     else:
#         icon_handle = windll.shell32.ExtractIconW(handle, sys.executable, 0)
#         ...
#
# `sys.executable` under `pythonw.exe` is the Python interpreter, so the panel
# presented the PYTHON icon in the taskbar and in Alt+Tab. pywebview's own
# docstring calls the `icon=` parameter "Supported only on GTK/QT"
# (`webview/__init__.py:205`); the WinForms backend reads it anyway, and that is
# the seam used here.
#
# The identity is the second half: `SetCurrentProcessExplicitAppUserModelID`
# stops Windows from grouping this process with every other pythonw.exe on the
# box under the Python icon. Both are read back and logged, never assumed.
# ===========================================================================

SOTTO_ICON = os.path.join(HERE, 'sotto.ico')
# O PERFIL DO WEBVIEW2 NAO PODE SER TEMPORARIO (2026-11-03). pywebview faz
# `tempfile.TemporaryDirectory().name` a cada largada quando o modo e' privado
# (winforms.py:757), e apaga-o no fim. Medido nesta maquina: centenas de
# `G:\Temp\tmp*\EBWebView` (4-67 MB cada) e uma pagina LOCAL de 700 KB a
# levar 11-25 s a ficar pronta -- cada arranque paga o perfil a frio.
SOTTO_CACHE = os.path.join(os.path.dirname(os.path.dirname(HERE)), '_cache')
SOTTO_APP_USER_MODEL_ID = 'sotto.overlay'

WM_GETICON = 0x007F
WM_SETICON = 0x0080
ICON_SMALL = 0
ICON_BIG = 1
ICON_SMALL2 = 2
GCLP_HICON = -14
GCLP_HICONSM = -34

user32.SendMessageW.restype = ctypes.c_ssize_t
user32.SendMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t,
                                ctypes.c_ssize_t]
user32.GetClassLongPtrW.restype = ctypes.c_ssize_t
user32.GetClassLongPtrW.argtypes = [wt.HWND, ctypes.c_int]
# `restype = ctypes.HRESULT` makes ctypes RAISE on a failing HRESULT, which
# turned the honest BEFORE answer (`E_NOT_SET`) into an exception; a plain
# `c_long` lets the code report the status instead of catching it.
shell32.GetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
shell32.GetCurrentProcessExplicitAppUserModelID.argtypes = [
    ctypes.POINTER(ctypes.c_wchar_p)]
shell32.SetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
shell32.SetCurrentProcessExplicitAppUserModelID.argtypes = [wt.LPCWSTR]


def process_app_user_model_id() -> dict:
    """This process' OWN AppUserModelID, read back from shell32.

    `GetCurrentProcessExplicitAppUserModelID` answers `E_NOT_SET`
    (`0x80070490`) when nothing has set one — which is the honest BEFORE value,
    not `None` dressed up as a failure.
    """
    try:
        ptr = ctypes.c_wchar_p()
        hr = shell32.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(ptr))
    except Exception as exc:  # noqa: BLE001 - a read must never kill a launch
        return {'ok': False, 'hr': None, 'value': None,
                'error': type(exc).__name__}
    if hr != 0:
        return {'ok': False, 'hr': hr & 0xFFFFFFFF, 'value': None}
    return {'ok': True, 'hr': 0, 'value': ptr.value}


def window_icon_snapshot(hwnd) -> dict:
    """What the WINDOW says its icon is: `WM_GETICON` + the class icon.

    Both are read, because they are different channels and only one of them is
    what `WM_SETICON` writes. Read from the window, never from the intent.
    """
    if not hwnd:
        return {'hwnd': None}
    return {
        'hwnd': int(hwnd),
        'wm_geticon_small': int(user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL, 0) or 0),
        'wm_geticon_big': int(user32.SendMessageW(hwnd, WM_GETICON, ICON_BIG, 0) or 0),
        'wm_geticon_small2': int(user32.SendMessageW(hwnd, WM_GETICON, ICON_SMALL2, 0) or 0),
        'class_hicon': int(user32.GetClassLongPtrW(hwnd, GCLP_HICON) or 0),
        'class_hiconsm': int(user32.GetClassLongPtrW(hwnd, GCLP_HICONSM) or 0),
    }


def form_icon_pixels(form) -> str:
    """The PIXELS of `form.Icon`, hashed in-process.

    This is the instrument that makes "the window carries the Python icon" a
    comparison of bytes instead of a non-zero handle: an HICON read out of
    another process cannot be drawn (GDI handles are process-local), so the
    hash has to be taken where the icon lives.
    """
    try:
        import hashlib
        icon = getattr(form, 'Icon', None)
        if icon is None:
            return 'absent'
        bmp = icon.ToBitmap()
        w, h = int(bmp.Width), int(bmp.Height)
        data = bytearray()
        for y in range(h):
            for x in range(w):
                c = bmp.GetPixel(x, y)
                data.extend((c.R, c.G, c.B, c.A))
        bmp.Dispose()
        return f'{w}x{h}:' + hashlib.sha256(bytes(data)).hexdigest()[:16]
    except Exception as exc:  # noqa: BLE001
        return f'ERR:{type(exc).__name__}'


def icon_source(form) -> str:
    """Where the icon ON the form came from: pywebview's own `_state['icon']`,
    or the `sys.executable` fallback that is the defect."""
    try:
        import webview
        path = (getattr(webview, '_state', None) or {}).get('icon')
    except Exception:  # noqa: BLE001
        path = None
    if path and os.path.isfile(path):
        return f'file:{path}'
    return f'pythonw-fallback:{sys.executable}'


def icon_file_sha256(path: str = SOTTO_ICON) -> str:
    """The sha256 of the icon FILE, so the in-process pixel hash can be tied to
    the exact bytes the shell loaded (the probe hashes the same file)."""
    try:
        import hashlib
        with open(path, 'rb') as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:16]
    except Exception as exc:  # noqa: BLE001
        return f'ERR:{type(exc).__name__}'


def window_icon_report(form, hwnd) -> str:
    snap = window_icon_snapshot(hwnd)
    return (f"WINDOW_ICON source={icon_source(form)} "
            f"file={SOTTO_ICON} file_exists={str(os.path.isfile(SOTTO_ICON)).lower()} "
            f"file_sha256={icon_file_sha256()} "
            f"form_icon={form_icon_pixels(form)} "
            f"wm_geticon_small={snap.get('wm_geticon_small')} "
            f"wm_geticon_big={snap.get('wm_geticon_big')} "
            f"wm_geticon_small2={snap.get('wm_geticon_small2')} "
            f"class_hicon={snap.get('class_hicon')} "
            f"class_hiconsm={snap.get('class_hiconsm')} "
            f"image={sys.executable}")


def set_process_app_user_model_id(value: str = SOTTO_APP_USER_MODEL_ID) -> dict:
    """THE FIX, first half: give the process its own identity.

    Windows groups taskbar buttons by AppUserModelID, and a process that has
    none is grouped by its EXECUTABLE — so this shell was grouped with every
    other `pythonw.exe` on the box, under the Python icon. This must run EARLY,
    before any window exists, because the identity is read when the taskbar
    button is created.
    """
    try:
        hr = shell32.SetCurrentProcessExplicitAppUserModelID(value)
    except Exception as exc:  # noqa: BLE001
        return {'set': False, 'value': None, 'hr': None,
                'error': type(exc).__name__}
    return {'set': hr == 0, 'value': value if hr == 0 else None,
            'hr': hr & 0xFFFFFFFF}


def apply_window_icon(form, hwnd, path: str = SOTTO_ICON) -> dict:
    """THE FIX, second half: the window's own icon.

    Two channels, because they answer different questions and Windows reads
    both: the WinForms `Icon` property (which .NET pushes with `WM_SETICON` for
    ICON_BIG and ICON_SMALL) and three explicit `WM_SETICON` sends — including
    **ICON_SMALL2**, the one the taskbar and Alt+Tab actually read and the one
    .NET's own setter never sends.

    The HICON must outlive the call: `WM_SETICON` stores the HANDLE, not a copy,
    so the `Icon` object is kept on the form (`_sotto_icon`) as well as in the
    form's own `Icon` property.
    """
    result = {'applied': False, 'path': path, 'reason': None, 'handle': None}
    if not path or not os.path.isfile(path):
        result['reason'] = 'icon-file-missing'
        return result
    try:
        from System.Drawing import Icon as DrawingIcon
        icon = DrawingIcon(path)
    except Exception as exc:  # noqa: BLE001
        result['reason'] = f'load-failed:{type(exc).__name__}'
        return result
    try:
        form.Icon = icon
        try:
            form._sotto_icon = icon
        except Exception:  # noqa: BLE001 - a .NET object may refuse attributes
            pass
        handle = int(icon.Handle.ToInt64())
        if hwnd:
            for which in (ICON_BIG, ICON_SMALL, ICON_SMALL2):
                user32.SendMessageW(hwnd, WM_SETICON, which, handle)
        result['applied'] = True
        result['handle'] = handle
    except Exception as exc:  # noqa: BLE001
        result['reason'] = f'apply-failed:{type(exc).__name__}:{exc}'
    return result


def reassert_taskbar_ex_style(hwnd, where: str) -> dict:
    """Re-apply the taskbar/focus bits the shell asked for and WinForms wiped.

    MEASURED BEFORE THE FIX (`_main/no-python-icon-before.json`): at
    `PANEL_VISIBILITY_AT_STARTUP` the ex-style was
    `WS_EX_APPWINDOW|WS_EX_CONTROLPARENT|WS_EX_TOPMOST` — **no
    `WS_EX_TOOLWINDOW`** — although the shell had logged setting it a few lines
    earlier. WinForms re-applies `Form.CreateParams` (which sets
    `WS_EX_APPWINDOW` while `ShowInTaskbar` is true and there is no owner) when
    pywebview's startup `Opacity`/`Show`/`Hide` dance recreates the handle, and
    that wipes every bit added by `SetWindowLong`. `WS_EX_APPWINDOW` is the one
    that puts the panel in the taskbar, which is the surface the owner was
    looking at when he reported the Python icon.
    """
    if not hwnd:
        return {'hwnd': None}
    before = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
    after = set_ex_style(hwnd, add=WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                         remove=WS_EX_APPWINDOW)
    state = {
        'where': where, 'before': before, 'after': int(after),
        'toolwindow': bool(int(after) & WS_EX_TOOLWINDOW),
        'appwindow': bool(int(after) & WS_EX_APPWINDOW),
    }
    log(f"PANEL_EXSTYLE_REASSERT where={where} "
        f"before=0x{before:08x} after=0x{int(after):08x} "
        f"toolwindow={str(state['toolwindow']).lower()} "
        f"appwindow={str(state['appwindow']).lower()}")
    return state


def parse_accelerator(accelerator: str):
    """'Alt+C' -> (MOD_ALT, ord('C')); 'Ctrl+Space' -> (MOD_CONTROL, 0x20).

    O VOCABULARIO DAS TECLAS NAO VIVE AQUI. `hotkey_gesture.parse_accelerator`
    conhece os nomes dos modificadores e das teclas (incluindo `Space`), e e' o
    MESMO parser com que `hotkey_settings` valida o ficheiro do dono -- duas
    tabelas de teclas seriam duas verdades, e a segunda envelhece sozinha. Aqui
    so' se traduz o NOME no bit do Win32 (`_MOD_BITS`): a ABI fica deste lado.
    """
    names, vk = hotkey_numbers().parse_accelerator(accelerator)
    mods = 0
    for name in names:
        mods |= _MOD_BITS[name]
    return mods, vk


def hotkey_numbers():
    """As teclas e o ciclo, do UNICO sitio onde eles vivem (`hotkey_gesture.py`).

    Uma tecla de fabrica redefinida aqui seria uma SEGUNDA verdade, e duas
    verdades divergem -- este repo ja pagou essa factura (`code-health` a medir
    dois "oraculos de enforcement" com definicoes diferentes). O import e'
    tardio pela mesma razao dos outros modulos deste ficheiro: `app/webview`
    pode nao estar no `sys.path` quando o modulo e' carregado como script.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import hotkey_gesture
    return hotkey_gesture


def hotkey_config():
    """O estado das teclas (`hotkey_settings.py`): a escolha do dono, lida do disco."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import hotkey_settings
    return hotkey_settings


class HotkeyThread(threading.Thread):
    """UMA tecla global, no seu proprio thread e na sua propria fila de mensagens.

    RegisterHotKey(hWnd=NULL, ...) associates the hotkey with the CALLING
    THREAD and posts WM_HOTKEY to that thread's queue, so the toggle works
    whether or not any Sotto window exists, is visible, or has focus — which is
    the whole point of the hotkey (main.js:29-31 says the same). Running it on a
    private queue also means the WebView2 UI loop cannot starve it, and nothing
    here calls Activate/SetForegroundWindow, so it cannot steal focus.

    UMA PRESSAO = UM CALLBACK. `MOD_NOREPEAT` faz o sistema entregar UM
    `WM_HOTKEY` por pressao enquanto a tecla estiver em baixo -- e' o que impede
    um Alt+C segurado de metralhar os paineis sozinho. O gesto nao le' relogio
    nenhum: nao ha duracao, nao ha janela de toques, nao ha estado por pressao.
    O que resta aqui e' entrega, e ela e' IMEDIATA.

    O PUMP NAO TRABALHA. `_on_press` chama o callback do shell, que so' poem um
    pedido numa FILA (o trabalho de janela corre no worker dessa fila) e volta --
    por isso este thread esta' sempre pronto para a proxima pressao, mesmo com o
    Alt fisicamente em baixo. Ocioso dorme em `WaitMessage` (0 % de CPU, entrega
    instantanea); antes fazia 100 voltas por segundo a medir a duracao de uma
    tecla que ja' nao se mede.
    """

    def __init__(self, accelerator: str, on_hotkey, log_fn=log, role='panels',
                 register=True):
        super().__init__(name=f'sotto-hotkey-{role}', daemon=True)
        self.accelerator = accelerator
        self.role = role
        #: `False` = thread de SONDA (`--selftest`): tem fila e tem pump, mas NAO
        #: toma a tecla do dono. Ver a docstring de `simulate_press`.
        self.register = bool(register)
        self.modifiers, self.vk = parse_accelerator(accelerator)
        self.on_hotkey = on_hotkey
        self.log_fn = log_fn
        self.registered = False
        self.register_error = None
        self.thread_id = None
        self.pressed = 0
        #: Voltas do laco -- o batimento publica este numero para que
        #: "a tecla nao respondeu" nunca mais seja um adjectivo.
        self.loops = 0
        #: NAO se chama `_stop`: esse nome e' o metodo interno de
        #: `threading.Thread`, e sombrea-lo tornava `HotkeyThread.join()` um
        #: `TypeError: 'Event' object is not callable` (medido 2026-11-01 num
        #: probe directo). `_stop_requested` e' so' nosso.
        self._stop_requested = threading.Event()
        self._ready = threading.Event()

    def run(self):
        self.thread_id = int(kernel32.GetCurrentThreadId())
        # Force the queue into existence: RegisterHotKey against the current
        # thread is refused when the thread has never pumped a message.
        msg = MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

        if self.register and not user32.RegisterHotKey(
                None, _HOTKEY_ID, self.modifiers | MOD_NOREPEAT, self.vk):
            self.register_error = ctypes.get_last_error()
            self.log_fn(f'HOTKEY_REGISTER_FAILED role={self.role} '
                        f'accelerator={self.accelerator} '
                        f'winerror={self.register_error}')
            # O PUMP CONTINUA. Antes esta funcao fazia `return`: a fila morria com
            # o registo e `simulate_press` deixava de ter onde entregar. Uma tecla
            # tomada por outro programa nao e' razao para o thread nao existir.
            self._ready.set()
        elif self.register:
            self.registered = True
            # A LINHA DIZ O CONTRATO VIGENTE. A etiqueta antiga
            # (`gesture=taps1|taps2|hold`) descrevia um gesto que ja' nao existe, e
            # uma etiqueta velha ja' custou uma sessao de diagnostico errado: o log
            # e' o que o dono le'.
            self.log_fn(f'HOTKEY_REGISTERED role={self.role} '
                        f'accelerator={self.accelerator} register=true '
                        f'gesture=one-press-one-step mod_norepeat=true '
                        f'thread={self.thread_id}')
            self._ready.set()
        else:
            self.log_fn(f'HOTKEY_PROBE role={self.role} '
                        f'accelerator={self.accelerator} register=false '
                        f'thread={self.thread_id} '
                        '(measurement launch: the owner keeps his key)')
            self._ready.set()

        while not self._stop_requested.is_set():
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_HOTKEY:
                    self._on_press()
                continue
            # OCIOSO = DORMIR. `WaitMessage` devolve no instante em que o sistema
            # poe um `WM_HOTKEY` na fila: nao ha sonda periodica, logo nao ha
            # leitura de teclado em repouso e nao ha custo de CPU. `stop` acorda
            # este sono com um `WM_APP` (`PostThreadMessageW`).
            user32.WaitMessage()

        # UNREGISTER NO THREAD QUE REGISTOU. `UnregisterHotKey(NULL, id)` e' da
        # fila do thread que chama; chamado do thread principal nao desligava
        # nada, e a tecla ficava viva ate' o processo morrer.
        if self.registered:
            user32.UnregisterHotKey(None, _HOTKEY_ID)
            self.registered = False

    def _on_press(self):
        """Um `WM_HOTKEY`: entrega AGORA. Nao mede, nao espera, nao lembra nada."""
        self.pressed += 1
        # CK -- O CONTADOR DA CHEGADA (2026-10-16): a pergunta era se a tecla
        # chegou ao shell. Continua a ser a prova de entrega, agora com o papel e
        # a tecla na linha: duas hotkeys, dois contadores.
        self.log_fn(f'HOTKEY_PRESSED role={self.role} count={self.pressed} '
                    f'accelerator={self.accelerator} thread={self.thread_id}')
        try:
            self.on_hotkey()
        except Exception as exc:  # a toggle must never kill the pump
            self.log_fn(f'HOTKEY_HANDLER_FAILED role={self.role} error={exc!r}')

    def stop(self):
        """Pede ao pump que saia e ACORDA-o: um `Event` nao tira ninguem de `WaitMessage`."""
        self._stop_requested.set()
        if self.thread_id is not None:
            try:
                user32.PostThreadMessageW(self.thread_id, WM_APP, 0, 0)
            except Exception as exc:  # noqa: BLE001 -- sair nao pode falhar
                self.log_fn(f'HOTKEY_STOP_WAKE_FAILED role={self.role} '
                            f'error={exc!r}')

    def wait_ready(self, timeout=5.0) -> bool:
        return self._ready.wait(timeout)

    def simulate_press(self) -> bool:
        """Post a real WM_HOTKEY to this thread's queue.

        This exercises the registration's own delivery path — the same queue
        the OS writes to — which is what makes the two-state toggle evidence
        real rather than a direct call to the toggle function.

        SO' PRECISA DA FILA, NAO DO REGISTO (2026-11-01). Num largamento de
        MEDICAO (`--selftest`) as teclas globais nao sao tomadas -- o dono tem
        as dele -- e o `HotkeyThread` de sonda (`register=False`) existe
        precisamente para esta prova: o `WM_HOTKEY` que se poe aqui e' o MESMO
        que o sistema poria, e quem o entrega e' o pump verdadeiro.
        """
        if self.thread_id is None:
            return False
        return bool(user32.PostThreadMessageW(self.thread_id, WM_HOTKEY,
                                              _HOTKEY_ID, 0))


# ===========================================================================
# Alt+C IS THE ONLY CONTROL — so its failure modes get first-class code
# ===========================================================================
#: Tried IN ORDER when the requested accelerator is already owned by another
#: program. `Alt+Shift+<key>` and `Ctrl+Alt+<key>` are the conventional choices
#: precisely because vendors grab the plain ones: on this box `Alt+F9` is already
#: taken (measured 2026-10-07 by `_main/_audit-hotkey-probe.py`, which is also the
#: instrument that proves `Alt+C` itself is FREE here — so a dead Alt+C was never
#: a taken key, and the owner's "Alt+C does nothing" had to be found downstream:
#: a second shell, or a panel path).
HOTKEY_FALLBACKS = ('Alt+Shift+C', 'Ctrl+Alt+C', 'Ctrl+Shift+C')

MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000

#: `CreateMutexW`'s handle, kept for the process lifetime on purpose: the kernel
#: releases it when this process dies, which is what makes "already running" a
#: fact with no stale lock to age out.
_SINGLE_INSTANCE = {'handle': None}

#: The one name the shipped app uses. A DIFFERENT name is a private lock, and it
#: is deliberately not excused by the measurement flags (see `main`).
DEFAULT_MUTEX_NAME = 'Local\\SottoShell'


#: VK de cada nome de modificador que o parser aceita. O Windows tem um VK
#: GENERICO por modificador (0x10/0x11/0x12) que responde a esquerda e a direita.
_MODIFIER_VK = {'ctrl': 0x11, 'alt': 0x12, 'shift': 0x10, 'win': 0x5B}

#: Os VK LATERAIS dos mesmos modificadores (2026-11-03). O generico responde
#: em quase todo o teclado, mas ha' teclados e remappers que so' publicam o
#: esquerdo/direito -- e o sintoma e' indistinguivel de uma tecla morta: o
#: observador corre, le' 0, e nunca dispara. Ler os tres e aceitar QUALQUER
#: deles custa duas leituras e remove a duvida inteira.
_MODIFIER_VARIANTS = {'ctrl': (0xA2, 0xA3), 'shift': (0xA0, 0xA1),
                      'alt': (0xA4, 0xA5), 'win': (0x5B, 0x5C)}

#: `SOTTO_HOTKEY_TRACE=1` escreve a BORDA do estado das teclas observadas.
#: Existe porque "carreguei e nao aconteceu nada" precisa de um numero: com
#: isto ligado, o log mostra o que o processo VIU, nao o que se esperava.
_HOTKEY_TRACE = os.environ.get('SOTTO_HOTKEY_TRACE', '') == '1'


class PassiveHotkeyThread(threading.Thread):
    """A TECLA DA LEGENDA **OBSERVADA**, NUNCA TOMADA (ordem do dono, 2026-11-02).

    O QUE ESTAVA MEDIDO E ERRADO. `RegisterHotKey` TOMA a combinacao para o
    processo que a registou: com o Sotto a viver, o `Ctrl+Space` deixa de chegar
    a qualquer outra janela. O dono joga com *"control mais espaço é crouch e
    jump no jogo"* e o jogo nunca o recebeu -- *"nao ta funcionando no jogo, por
    causa do sotto"*.

    O QUE ESTA CLASSE FAZ. Le o ESTADO das teclas (`GetAsyncKeyState`, que nao
    consome nada) a cada `POLL_S` e dispara na BORDA de descida da combinacao:
    o jogo recebe o `Ctrl+Space` inteiro porque o Windows entrega a tecla a quem
    tem o foco e aqui ninguem a intercepta. O toque continua a ser UM: a tecla
    tem de ser largada antes de disparar outra vez.

    CUSTO: uma leitura de estado por modificador + uma da tecla, 40 vezes por
    segundo. `GetAsyncKeyState` e' uma chamada de microssegundos, nao uma
    mensagem: medido neste host, um laco de 4 teclas a 40 Hz fica abaixo de
    0,1 % de um core.
    """

    POLL_S = 0.025

    def __init__(self, accelerator: str, on_hotkey, log_fn=log, role='live',
                 poll_s=None, key_state=None):
        super().__init__(name=f'sotto-hotkey-{role}', daemon=True)
        self.accelerator = accelerator
        self.role = role
        self.on_hotkey = on_hotkey
        self.log_fn = log_fn
        self.modifiers, self.vk = parse_accelerator(accelerator)
        self.poll_s = float(poll_s or self.POLL_S)
        self.registered = True
        self.register_error = None
        self.thread_id = None
        self.pressed = 0
        #: Voltas do laco. O batimento publica ESTE numero: `loops=` a subir
        #: e' a prova de que o observador corre, e `max_gap_ms=` diz se a
        #: volta foi estrangulada. Sem ele, uma tecla morta e um observador
        #: morto escrevem a mesma coisa no log: nada.
        self.loops = 0
        self._stop_requested = threading.Event()
        self._ready = threading.Event()
        #: `key_state(vk) -> bool` -- o oraculo injecta uma sequencia falsa; o
        #: processo vivo le o estado real. A leitura e' a UNICA coisa trocavel: a
        #: borda, o nao-repetir e a chamada do callback sao o que se mede.
        self.key_state = key_state
        #: Os VK desta combinacao: os modificadores nomeados + a tecla.
        # UM GRUPO POR TECLA NOMEADA: basta QUALQUER VK do grupo estar em baixo.
        self.key_groups = []
        for name in str(accelerator).split('+'):
            name = name.strip().lower()
            if name in _MODIFIER_VK:
                _group = [int(_MODIFIER_VK[name])]
                for _extra in _MODIFIER_VARIANTS.get(name, ()):
                    if int(_extra) not in _group:
                        _group.append(int(_extra))
                self.key_groups.append(tuple(_group))
        self.key_groups.append((int(self.vk),))
        self.keys = [g[0] for g in self.key_groups]

    def run(self):
        self.thread_id = int(kernel32.GetCurrentThreadId())
        self.log_fn(f'HOTKEY_OBSERVED role={self.role} '
                    f'accelerator={self.accelerator} register=false '
                    f'the_key_passes_through=true poll_ms={int(self.poll_s * 1000)}')
        self._ready.set()
        if self.key_state is not None:
            def get_state(vk):
                return 0x8000 if self.key_state(int(vk)) else 0
        else:
            get_state = user32.GetAsyncKeyState
        # O OBSERVADOR DIZ QUE ESTA' VIVO, E DIZ QUANDO PARA (2026-11-03).
        # MEDIDO: o dono carregou em Ctrl+Space e o log do shell nao teve
        # UMA linha `HOTKEY_PRESSED role=live` -- nem pressao, nem falha.
        # Um observador silencioso e' indistinguivel de uma tecla morta, e
        # as duas tambem sao indistinguiveis de uma tecla que ele nao
        # carregou. Este batimento resolve a duvida com um numero: o contador
        # de voltas cresce? a volta ficou presa?
        self.log_fn('HOTKEY_OBSERVER_KEYS role=%s groups=%s'
                    % (self.role, [[hex(int(v)) for v in g]
                                   for g in self.key_groups]))
        _beats = 0
        _last_beat = time.monotonic()
        _last_loop = time.monotonic()
        held = False
        while not self._stop_requested.is_set():
            _now_loop = time.monotonic()
            self._wake_gap = max(float(getattr(self, '_wake_gap', 0.0)),
                                 _now_loop - _last_loop)
            _last_loop = _now_loop
            # O BATIMENTO NAO E' UM RELOGIO (2026-11-03, MEDIDO). A primeira
            # versao escrevia de 5 em 5 s para sempre: num ficheiro de log que
            # so' roda aos 64 MB (`LOG_ROTATED cap=64 MB`), o observador de uma
            # tecla que ninguem esta' a carregar produzia **720 linhas por hora** --
            # medido neste repo, 54 MB de `_main/webview-run.log` e 382 destas
            # linhas num unico arranque. As duas informacoes que o batimento
            # carrega continuam a sair: (a) vive nos primeiros 30 s, seis
            # batimentos, que e' o que RESPONDE a "a tecla esta' viva?" depois
            # de um arranque; (b) uma VOLTA PRESA (`max_gap_ms > 200`) sai
            # imediatamente, porque essa e' a noticia e um batimento liso nao
            # e'. Depois disso, de 5 em 5 minutos.
            _gap_ms = round(getattr(self, '_wake_gap', 0.0) * 1000.0)
            _due = (_beats < 6 and _now_loop - _last_beat >= 5.0) or \
                   (_now_loop - _last_beat >= 300.0)
            if _due or _gap_ms > 200:
                _beats += 1
                self.log_fn('HOTKEY_OBSERVER_ALIVE role=%s beats=%d '
                            'loops=%d max_gap_ms=%d'
                            % (self.role, _beats, self.loops, _gap_ms))
                self._wake_gap = 0.0
                _last_beat = _now_loop
            self.loops += 1
            down = True
            for _group in self.key_groups:
                if not any(int(get_state(int(vk))) & 0x8000
                           for vk in _group):
                    down = False
                    break
            if _HOTKEY_TRACE and getattr(self, '_trace', None) != down:
                self._trace = down
                self.log_fn('HOTKEY_TRACE role=%s down=%s groups=%s'
                            % (self.role, str(down).lower(),
                               [[hex(int(v)) for v in g]
                                for g in self.key_groups]))
            if down and not held:
                held = True
                try:
                    self.pressed += 1
                    # A MESMA ETIQUETA DO REGISTADO, e o `source`: o
                    # `altc-first-caption-oracle.py` emparelha `HOTKEY_PRESSED
                    # role=live` com a ACCAO, e uma tecla observada tem de ser
                    # julgada pelo mesmo instrumento que a registada.
                    self.log_fn(f'HOTKEY_PRESSED role={self.role} '
                                f'count={self.pressed} source=observed')
                    self.on_hotkey()
                except Exception as exc:  # noqa: BLE001 -- um passo perdido nao mata o observador
                    self.log_fn(f'HOTKEY_GESTURE_FAILED kind=live error={exc!r}')
            elif not down and held:
                held = False
                self._down_since = 0.0
            # A TECLA DE PEDRA (2026-11-03, MEDIDO). O log do dono tem
            # `HOTKEY_PRESSED role=live count=1 source=observed` DUAS vezes na
            # historia inteira do ficheiro (03:22:19 e 04:56:26) e **nunca um
            # `count=2`**: dentro de um arranque, a segunda pressao nunca
            # disparou. A borda de DESCIDA e' perdida com facilidade -- o laco
            # ja' publicou `max_gap_ms=219` (o shell a queimar um nucleo inteiro
            # no `VramGuard`, medido hoje: 102 %) -- e o `held` fica `True` para
            # sempre: a tecla morre ate' reiniciar a app. Uma tecla que ninguem
            # esta' a segurar nao fica em baixo 3 s: passado esse tempo o latch
            # RE-ARMA e o log diz que re-armou, em vez de ficar mudo.
            if held:
                if not getattr(self, '_down_since', 0.0):
                    self._down_since = _now_loop
                elif _now_loop - self._down_since >= 3.0:
                    self.log_fn('HOTKEY_STATE_STUCK role=%s seconds=3.0 repinned=true'
                                % self.role)
                    held = False
                    self._down_since = 0.0
            self._stop_requested.wait(self.poll_s)

    def wait_ready(self, timeout=None):
        self._ready.wait(timeout)
        return bool(self.registered)

    def stop(self):
        self._stop_requested.set()

#: O JOB OBJECT QUE MATA A ARVORE (2026-11-04). Guardado aqui para o HANDLE
#: sobreviver: fechar o ultimo handle do job e' o que dispara o kill, e um handle
#: recolhido pelo GC mataria os filhos em qualquer momento.
_JOB = {'handle': None}


#: Um estouro de UI tem pilha completa de 10 em 10 min; os do meio, uma linha.
UI_HUNG_DUMP_EVERY_S = 600.0


def _hold_kill_on_close_job():
    """Poe ESTE processo (e os filhos que ele criar) num job kill-on-close.

    MEDIDO 2026-11-04: tres arvores `msedgewebview2.exe` orfas de instancias
    mortas, ~390 MB, nesta maquina. O filho herda a pertenca ao job quando e'
    criado DEPOIS da atribuicao, e o Windows mata tudo quando o ultimo handle do
    job fecha -- inclusive num `TerminateProcess` do shell, quando nenhum codigo
    Python corre.

    Nao e' fatal: se a maquina ja' tem este processo num job que proibe
    breakaway (uma sessao de CI, um sandbox), `AssignProcessToJobObject` devolve
    erro e a app continua como antes -- a diferenca fica escrita no log, nunca
    silenciosa.
    """
    if _JOB.get('handle'):
        return True
    try:
        class _IO_COUNTERS(ctypes.Structure):
            _fields_ = [('ReadOperationCount', ctypes.c_ulonglong),
                        ('WriteOperationCount', ctypes.c_ulonglong),
                        ('OtherOperationCount', ctypes.c_ulonglong),
                        ('ReadTransferCount', ctypes.c_ulonglong),
                        ('WriteTransferCount', ctypes.c_ulonglong),
                        ('OtherTransferCount', ctypes.c_ulonglong)]

        class _BASIC(ctypes.Structure):
            _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                        ('PerJobUserTimeLimit', ctypes.c_int64),
                        ('LimitFlags', wt.DWORD),
                        ('MinimumWorkingSetSize', ctypes.c_size_t),
                        ('MaximumWorkingSetSize', ctypes.c_size_t),
                        ('ActiveProcessLimit', wt.DWORD),
                        ('Affinity', ctypes.c_size_t),
                        ('PriorityClass', wt.DWORD),
                        ('SchedulingClass', wt.DWORD)]

        class _EXTENDED(ctypes.Structure):
            _fields_ = [('BasicLimitInformation', _BASIC),
                        ('IoInfo', _IO_COUNTERS),
                        ('ProcessMemoryLimit', ctypes.c_size_t),
                        ('JobMemoryLimit', ctypes.c_size_t),
                        ('PeakProcessMemoryUsed', ctypes.c_size_t),
                        ('PeakJobMemoryUsed', ctypes.c_size_t)]

        kernel32.CreateJobObjectW.restype = wt.HANDLE
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            log('SHELL_JOB_FAILED stage=create winerror=%d' % ctypes.get_last_error())
            return False
        JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
        info = _EXTENDED()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        ok = kernel32.SetInformationJobObject(
            wt.HANDLE(job), 9, ctypes.byref(info), ctypes.sizeof(info))
        if not ok:
            log('SHELL_JOB_FAILED stage=limits winerror=%d' % ctypes.get_last_error())
            return False
        # O HANDLE DE `GetCurrentProcess` E' PSEUDO (-1): sem `argtypes` o ctypes
        # recusa-o ("int too long to convert") e o job nunca fica armado.
        kernel32.GetCurrentProcess.restype = wt.HANDLE
        kernel32.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wt.BOOL
        proc = wt.HANDLE(kernel32.GetCurrentProcess())
        ok = kernel32.AssignProcessToJobObject(wt.HANDLE(job), proc)
        if not ok:
            err = ctypes.get_last_error()
            log('SHELL_JOB_FAILED stage=assign winerror=%d (a arvore nao morre '
                'sozinha: este processo ja\' esta\' num job que recusa)' % err)
            kernel32.CloseHandle(wt.HANDLE(job))
            return False
        _JOB['handle'] = job
        log('SHELL_JOB_ARMED pid=%d kill_on_close=true' % os.getpid())
        return True
    except Exception as exc:  # noqa: BLE001 -- nunca custa o arranque da app
        log('SHELL_JOB_FAILED stage=exception error=%r' % (exc,))
        return False


def take_single_instance_lock(name=DEFAULT_MUTEX_NAME) -> bool:
    """True when THIS process is the one Sotto shell for this session.

    Alt+C is a GLOBAL key with exactly one owner: a second shell cannot register
    it (`RegisterHotKey` → 1409) and, without this guard, kept running with a dead
    hotkey and an invisible window of its own — so the owner's Alt+C answered the
    FIRST instance, which is how a stale panel that no longer updates looks
    exactly like a broken hotkey. With autostart (`HKCU\\...\\Run`) and a manual
    double-click arriving in the same login, that collision stops being
    hypothetical.

    A FAILED `CreateMutexW` returns True (proceed) and says so: refusing to start
    because a lock could not be created would be worse than a rare double shell.
    """
    try:
        kernel32.CreateMutexW.restype = wt.HANDLE
        handle = kernel32.CreateMutexW(None, False, name)
    except Exception as exc:  # noqa: BLE001 -- never cost the app a start
        log(f'SINGLE_INSTANCE_MUTEX_FAILED error={exc!r}')
        return True
    if not handle:
        log(f'SINGLE_INSTANCE_MUTEX_FAILED winerror={ctypes.get_last_error()}')
        return True
    _SINGLE_INSTANCE['handle'] = handle
    exists = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
    log(f'SINGLE_INSTANCE name={name} already_running={str(exists).lower()}')
    return not exists


#: The flags that make a launch a MEASUREMENT of the panel/shell rather than the
#: app, and therefore give it a DERIVED lock name instead of `Local\SottoShell`.
#: Read from `args` by attribute; `--exit-after` is a FLOAT (0.0 = off) and the
#: rest are booleans/ints, so truthiness is correct for all of them. The label is
#: built from EVERY flag present, so two probes with different shapes keep
#: different locks (they may run together) while two IDENTICAL ones collide (they
#: may not stack model loads).
_MEASUREMENT_LOCK_FLAGS = (
    ('dump_dom', 'dump-dom'),
    ('selftest', 'selftest'),
    ('memory', 'memory'),
    ('no_hotkey', 'no-hotkey'),
    ('probe_v2', 'probe-v2'),
    ('exit_after', 'exit-after'),
)


def measurement_lock_name(args) -> str:
    """The lock a MEASUREMENT launch takes: same exclusivity, its own name.

    Never the APP's name: a probe refused because the owner's app is up is the
    failure that once bricked the whole instrument set (measured 2026-10-07).
    Never the EMPTY lock either: taking none let several probe launches stack
    panels, tray icons and worker model loads, which is the owner's report
    ("Sotto opened more than once and froze the PC"). So the lock is TAKEN by
    every launch; only the NAME differs from the app's.
    """
    parts = [name for attr, name in _MEASUREMENT_LOCK_FLAGS
             if getattr(args, attr, False)]
    label = '.'.join(parts) if parts else 'probe'
    return DEFAULT_MUTEX_NAME + '.m.' + label.replace('-', '_')


# ===========================================================================
# THE TRAY — the app's face and its Quit, where the owner asked for them
#
# Owner, 2026-10-08, verbatim: "tira o botao de quit sotto do painel. só tem q
# quit no icon do system tray". THE TRAY DID NOT EXIST: measured on 2026-10-08,
# `grep -rn 'pystray|NotifyIcon|Shell_NotifyIcon|QSystemTrayIcon' app/` returns
# ZERO matches. So the Quit had to be BUILT before it could be moved, or the
# owner would have been left with no way to close the app but the task manager.
#
# It is plain Win32 `Shell_NotifyIconW` on a MESSAGE-ONLY window owned by its own
# thread — no new dependency, and the icon is the one already generated for the
# window (`SOTTO_ICON`), not a second one.
#
# WHY ITS OWN THREAD AND ITS OWN WINDOW: the notification-area callback arrives
# as a message, so something has to pump. The hotkey thread cannot be borrowed
# (it exists only when a hotkey was registered — a `--no-hotkey` run has none),
# and the WebView2 UI loop is not ours to post into. One daemon thread with one
# `GetMessageW` loop is the whole cost.
# ===========================================================================

WM_APP = 0x8000
WM_TRAY_CALLBACK = WM_APP + 1
WM_TRAY_STOP = WM_APP + 2
WM_COMMAND = 0x0111
WM_RBUTTONUP = 0x0205
WM_LBUTTONUP = 0x0202
WM_DESTROY = 0x0002

# ===========================================================================

#: SEM `WH_MOUSE_LL` (removido a 2026-10-30, ordem do dono: *"se esses hooks sao
#: burros ou desnecessarios, remove"*). O que os dois trabalhos dele eram, e o
#: que os substitui SEM interceptar input do sistema:
#:
#:   1. fechar o painel com um clique fora -> o FOREGROUND. O painel e' uma
#:      janela; quando o dono clica noutra coisa, o foreground deixa de ser a
#:      nossa. Uma leitura de `GetForegroundWindow()` a cada `POLL_MS_VISIBLE`
#:      responde o mesmo e nao poe um unico evento do rato a passar por Python.
#:   2. arrastar a faixa em edit mode -> `GetCursorPos()` + `GetAsyncKeyState`,
#:      a `POLL_MS_DRAG`, SO' enquanto o botao esta' em baixo. O arrasto normal
#:      do painel ja' nao usava o hook: `_begin_window_drag` entra no loop de
#:      movimento do Windows (`WM_NCLBUTTONDOWN`/`HTCAPTION`).
#:
#: PORQUE E' QUE O HOOK SAIU. Medido 2026-10-23: um `WH_MOUSE_LL` poe TODOS os
#: eventos do rato da maquina (1000/s num rato de 1000 Hz) a passar pelo callback
#: Python desta thread antes de chegarem a quem quer que seja -- o dono descreveu
#: como *"MEU MOUSE TA TRAVANDO DEMAIS"*. E medido 2026-10-30: o hook estava
#: `uninstalled reason=not-armed` enquanto o autoclicker dele falhava, por isso
#: NAO era a causa -- mas um mecanismo que so' serve para adivinhar "o rato esta'
#: fora da minha janela" nao tem direito a esse preco.
HC_ACTION = 0
WM_LBUTTONDOWN, WM_RBUTTONDOWN = 0x0201, 0x0204
WM_MBUTTONDOWN, WM_XBUTTONDOWN = 0x0207, 0x020B
WM_MOUSEMOVE = 0x0200
WM_QUIT = 0x0012
WM_PROBE_CLICK = WM_APP + 9
#: EDIT MODE's drag sample: the hook proc POSTS this to its own thread instead of
#: moving the window inside the hook. The hook proc must return immediately — it
#: runs on the hook thread and a slow one stalls the pointer SYSTEM-WIDE — so the
#: `SetWindowPos` happens in the message loop, which is also where the rate is
#: bounded (`EDIT_DRAG_MIN_INTERVAL_MS`).
WM_EDIT_DRAG = WM_APP + 10
#: O tick do vigilante, pedido a ESTA thread (`SetTimer`), nunca a um hook.
WM_TIMER = 0x0113
_POLL_TIMER_ID = 1
#: Com o painel visivel: e' o intervalo em que o foreground e' re-lido. 100 ms e'
#: o mesmo orcamento que um popover do Windows leva a reagir a um clique fora, e
#: e' uma chamada de sistema por tick -- nao ha tensao nenhuma em 10 Hz.
POLL_MS_VISIBLE = 100
#: Com um arrasto em curso: `GetCursorPos` a 40 Hz, que e' a taxa a que o
#: `SetWindowPos` do `edit_drag_to` corre (o tecto continua a ser
#: `EDIT_DRAG_MIN_INTERVAL_MS`).
POLL_MS_DRAG = 25

#: A few pixels of slack on the rect test: a click on the panel's own edge is
#: still a click on the panel, and the owner cannot aim to the pixel.
CLICK_OUTSIDE_SLACK = 2

#: The drag's ceiling: at most one `SetWindowPos` per this many ms (20 Hz). The
#: receipt's design says it plainly — moving the NATIVE window per frame is the
#: short path to flicker (`docs/release-and-overlay-plan.md:75-78`), so the drag
#: is a low-frequency move, not a smooth one.
EDIT_DRAG_MIN_INTERVAL_MS = 50


user32.GetWindowRect.argtypes = [wt.HWND, ctypes.c_void_p]
user32.GetForegroundWindow.restype = wt.HWND
user32.PostThreadMessageW.restype = wt.BOOL
user32.PostThreadMessageW.argtypes = [wt.DWORD, ctypes.c_uint, ctypes.c_size_t,
                                      ctypes.c_ssize_t]
user32.GetCurrentThreadId = None  # NOT in user32; see kernel32 below
kernel32.GetCurrentThreadId.restype = wt.DWORD
kernel32.GetCurrentThreadId.argtypes = []
user32.WindowFromPoint.restype = wt.HWND
user32.WindowFromPoint.argtypes = [POINT]

class OutsideClickWatcher(threading.Thread):
    """Fecha o painel quando o dono clica FORA dele — sem hook nenhum.

    DESENHO (reescrito a 2026-10-30). Este objecto guardava um `WH_MOUSE_LL`
    global enquanto o painel estava visivel. O dono mandou retira-lo -- *"se
    esses hooks sao burros ou desnecessarios, remove"* -- e a medicao diz que ele
    tinha razao no custo: um hook de baixa prioridade poe **todos** os eventos do
    rato da maquina (1000/s num rato de 1000 Hz) a passar pelo callback Python
    desta thread antes de chegarem a quem quer que seja. Foi esse o
    *"MEU MOUSE TA TRAVANDO DEMAIS"* de 2026-10-23.

    O QUE ELE FAZIA, E COM QUE SE FAZ AGORA (nenhum passo intercepta input):

      * fechar com um clique fora -> o FOREGROUND. Quando o dono clica noutra
        coisa, `GetForegroundWindow()` deixa de ser a nossa janela (ou uma que
        nos possuimos). Lido a cada `POLL_MS_VISIBLE` (100 ms), so' enquanto o
        painel esta' visivel.
      * arrastar a faixa em edit mode -> `GetCursorPos()` + `GetAsyncKeyState`,
        a `POLL_MS_DRAG`, so' enquanto o botao esquerdo esta' em baixo. O
        arrasto NORMAL do painel nunca usou isto: `_begin_window_drag` entra no
        loop de movimento do proprio Windows.

    A DECISAO E' A MESMA. `_consider` continua a ser a unica funcao que decide
    fechar, com a cadeia de guardas que ja' tinha (a sair, edit mode, nao armado,
    painel nao visivel, dentro do rect, janela nossa) -- e o `--probe` continua a
    exercita-la pela mesma via (`WM_PROBE_CLICK`). O que mudou foi QUEM LHE DIZ
    QUE HOUVE UM CLIQUE: antes o sistema, evento a evento; agora esta thread,
    quatro vezes por segundo, e so' quando o foreground muda de dono.
    """

    def __init__(self, shell):
        super().__init__(name='sotto-outside-click', daemon=True)
        self.shell = shell
        self.thread_id = None
        self._ready = threading.Event()
        self.decisions = []
        self._armed = False
        self._edit_mode = False
        self._dragging = False
        self._last_drag_post = 0.0
        self.drag_samples = 0
        self._last_fg = None
        self.polls = 0
        #: Quando o show armou este vigia: foreground que mude nos primeiros
        #: 250 ms e do show (`PANEL_SHOWN` .724 -> `PANEL_HIDDEN` .736, 2026-11-02).
        self._armed_at = 0.0

    # `armed`/`edit_mode` sao PROPRIEDADES: quem os escreve (o `show_panel` e o
    # item de tray do edit mode) nao precisa de saber que a escrita tem de mexer
    # no ritmo do tick. Um campo simples deixaria o timer a correr para sempre.
    @property
    def armed(self):
        return self._armed

    @armed.setter
    def armed(self, value):
        self._armed = bool(value)
        self._apply_timer()

    @property
    def edit_mode(self):
        return self._edit_mode

    @edit_mode.setter
    def edit_mode(self, value):
        self._edit_mode = bool(value)
        self._apply_timer()

    def _wants_poll(self):
        """So' ha o que vigiar com o painel visivel ou a arrastar."""
        return bool(self._armed or self._edit_mode)

    def _interval_ms(self):
        return POLL_MS_DRAG if self._edit_mode else POLL_MS_VISIBLE

    def _apply_timer(self):
        """Pede a ESTA thread (a dona do timer) o ritmo que o estado pede."""
        if not self.thread_id:
            return False
        try:
            user32.PostThreadMessageW(self.thread_id, WM_TIMER, 0, 0)
            return True
        except Exception:  # noqa: BLE001
            return False

    def start(self, timeout=5.0) -> bool:
        super().start()
        self._ready.wait(timeout)
        # O QUE ESTE `True` QUER DIZER AGORA: a thread do loop esta viva e pode
        # por o tick a correr quando o painel aparecer. NAO quer dizer "esta a
        # vigiar" -- de proposito, porque vigiar com o painel escondido era o
        # defeito.
        return self.is_alive()

    def stop(self, reason='stop'):
        # `stop` e um caminho de encerramento: nao vale a pena pedir ao loop que
        # se sincronize -- a thread vai sair. Desarma e mata o tick aqui.
        self._armed = False
        self._edit_mode = False
        if self.thread_id:
            try:
                user32.KillTimer(None, _POLL_TIMER_ID)
            except Exception:  # noqa: BLE001
                pass
        if self.thread_id:
            try:
                user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
            except Exception:  # noqa: BLE001
                pass
        if self.is_alive() and self is not threading.current_thread():
            self.join(2)
        log(f'OUTSIDE_CLICK_STOP reason={reason}')

    # -- o tick ------------------------------------------------------------
    def run(self):
        """`run`, NOT `_run`: this class IS a Thread, and `Thread.start()` calls
        `self.run()`. Named `_run` it silently did NOTHING — the thread exited at
        once, `_ready` was never set, and the shell sat for the full 5 s timeout
        before reporting `OUTSIDE_CLICK_UNAVAILABLE`. Measured 2026-10-08. (The
        tray class can use `_run` because it is not a Thread; it passes `_run` as
        a `target`.)"""
        try:
            self.thread_id = int(kernel32.GetCurrentThreadId())
            # O TICK NAO CORRE AQUI: `SetTimer` e' pedido quando -- e se -- o
            # painel aparecer. Um vigilante a 10 Hz com o painel escondido seria
            # o mesmo desperdicio que o hook era, so' sem o custo do rato.
            self._ready.set()
            if self._wants_poll():
                self._restart_timer()
            else:
                log('OUTSIDE_CLICK_POLL deferred reason=panel-hidden '
                    f'thread={self.thread_id}')
            msg = MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_TIMER:
                    # `armed`/`edit_mode` mudaram noutra thread: o ritmo muda
                    # aqui, que e' a thread que possui o timer. Depois o mesmo
                    # tick faz o trabalho -- nao ha dois caminhos.
                    self._restart_timer()
                    self._poll()
                elif msg.message == WM_PROBE_CLICK:
                    # The MEASUREMENT path: the same decision function the poll
                    # calls, on the same thread, reached through this thread's
                    # real message loop. What is NOT exercised is the OS moving
                    # the foreground.
                    x, y = _unpack_point(msg.wParam)
                    self._consider(x, y, WM_LBUTTONDOWN, source='probe')
                elif msg.message == WM_EDIT_DRAG:
                    # A amostra de arrasto. O movimento da janela acontece AQUI,
                    # fora do tick, para o tick nunca bloquear.
                    x, y = _unpack_point(msg.wParam)
                    self.shell.edit_drag_to(x, y, persist=bool(msg.lParam))
                else:
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
        except Exception as exc:  # noqa: BLE001 -- a watcher must not kill the app
            warn(f'OUTSIDE_CLICK_POLL_FAILED {type(exc).__name__}: {exc}')
            self._ready.set()
        finally:
            log('OUTSIDE_CLICK_LOOP_EXIT')

    def _restart_timer(self):
        """Re-arma o tick com o intervalo que o estado pede, ou mata-o."""
        try:
            user32.KillTimer(None, _POLL_TIMER_ID)
        except Exception:  # noqa: BLE001
            pass
        if not self._wants_poll():
            self._last_fg = None
            return False
        user32.SetTimer(None, _POLL_TIMER_ID, int(self._interval_ms()), None)
        return True

    def _poll(self):
        """Um tick: ou segue o arrasto, ou pergunta ao foreground quem manda.

        NUNCA lanca: um erro aqui mataria o vigilante e o painel deixaria de
        fechar por clique fora, sem ninguem saber.
        """
        self.polls += 1
        try:
            if self._edit_mode:
                self._poll_drag()
                return
            if not self._armed:
                return
            hwnd = self.shell.hwnd
            if not hwnd or not window_visible(hwnd):
                return
            fg = int(user32.GetForegroundWindow() or 0)
            if not fg or _window_is_ours(fg):
                self._last_fg = fg
                return
            was = self._last_fg
            self._last_fg = fg
            if self._armed_at and (time.monotonic() - self._armed_at) < 0.25:
                return     # o show e dono dos seus primeiros 12 ms (medido)
            if was == fg:
                # JA' ERA DE OUTRA JANELA no tick anterior: a mudanca de
                # foreground JA' disparou o fecho. Um segundo tick nao e' um
                # segundo clique.
                return
            point = POINT()
            user32.GetCursorPos(ctypes.byref(point))
            self._consider(int(point.x), int(point.y), WM_LBUTTONDOWN,
                           source='foreground')
        except Exception as exc:  # noqa: BLE001
            log('OUTSIDE_CLICK_POLL_ERROR error=%r' % (exc,))

    def _poll_drag(self):
        """EDIT MODE: o botao esquerdo em baixo e' o arrasto.

        `GetAsyncKeyState(VK_LBUTTON)` e' a UNICA forma de saber que o botao esta'
        em baixo sem um hook -- e e' o mesmo mecanismo que o `HotkeyThread` usa
        para medir a duracao do Alt. `edit_grab` e' o deslocamento entre o cursor
        e a janela no instante da pega, exactamente como antes.
        """
        down = bool(user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000)
        point = POINT()
        user32.GetCursorPos(ctypes.byref(point))
        x, y = int(point.x), int(point.y)
        hwnd = self.shell.hwnd
        if down and not self._dragging:
            if hwnd and _point_in_window(hwnd, x, y):
                rect = RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                self.shell.edit_grab = (x - rect.left, y - rect.top)
                self._dragging = True
                self._last_drag_post = 0.0
                log(f'PANEL_EDIT_DRAG start point=({x},{y}) '
                    f'grab={self.shell.edit_grab}')
            return
        if down and self._dragging:
            now = time.monotonic() * 1000.0
            if now - self._last_drag_post < EDIT_DRAG_MIN_INTERVAL_MS:
                return
            self._last_drag_post = now
            self.drag_samples += 1
            user32.PostThreadMessageW(self.thread_id, WM_EDIT_DRAG,
                                      _pack_point(x, y), 0)
            return
        if self._dragging and not down:
            self._dragging = False
            user32.PostThreadMessageW(self.thread_id, WM_EDIT_DRAG,
                                      _pack_point(x, y), 1)

    # -- the decision ------------------------------------------------------
    def _consider(self, x, y, message, source='hook'):
        """Returns True when this click closed the panel."""
        shell = self.shell
        reason = None
        hwnd = shell.hwnd
        if shell.exiting.is_set():
            reason = 'exiting'
        elif self.edit_mode:
            # The owner is POSITIONING the band. An outside click while edit mode
            # is on must not put the window away — the first missed grab would end
            # the edit he just asked for, and the tray item is the way out.
            reason = 'edit-mode'
        elif not self.armed:
            reason = 'not-armed'          # the startup navigations
        elif not hwnd or not window_visible(hwnd):
            reason = 'panel-not-visible'  # MEASURED, never the cache
        elif _point_in_window(hwnd, x, y):
            reason = 'inside'
        elif _window_is_ours(user32.WindowFromPoint(POINT(x, y))):
            reason = 'our-own-window'     # the tray menu, a dialog
        if reason is not None:
            self._record(x, y, source, reason, closed=False)
            return False
        self._record(x, y, source, 'outside', closed=True)
        shell.hide_panel('click-outside')
        return True

    def _record(self, x, y, source, reason, closed):
        # O RING EM MEMORIA E SEMPRE. O LOG NAO.
        #
        # MEDIDO 2026-10-17: esta linha escrevia no ficheiro de log **toda** vez
        # que `reason is not None`, e `reason` e tambem 'panel-not-visible' e
        # 'inside' -- ou seja, UM CLIQUE EM QUALQUER SITIO DO TEU ECRÃ, com o
        # painel escondido, escrevia uma linha. O ficheiro carries:
        #
        #     73 420 linhas OUTSIDE_CLICK
        #     crescimento medido: 3 185 B em 5 s = ~640 B/s = ~55 MB/dia
        #
        # E ISTO E UM INSTRUMENTO QUEIMADO, nao so um ficheiro grande: este log e
        # onde se mede `LIVE_ENABLED`, `STRIP_HEIGHT` e `PANEL_SURFACE`, ou seja as
        # provas de que o botao da legenda nao abre nada. Enterrar a evidencia
        # num ruido de 640 B/s para o painel ja estar escondido nao tem razao de
        # ser: 'o painel nao estava avel' NAO E UMA DECISAO, e a ausencia de uma.
        #
        # A REGRA: o log regista DECISOES (`closed=true`, ou uma janela que estava
        # mesmo avel e o clique caiu fora dela). O resto conta-se e viaja na
        # proxima linha real -- o numero nao se perde, so nao ocupa o ficheiro a
        # 640 B/s.
        self._idle_clicks = getattr(self, '_idle_clicks', 0) + 1
        entry = {'x': x, 'y': y, 'source': source, 'decision': reason,
                 'closed': closed}
        self.decisions.append(entry)
        del self.decisions[:-20]
        visible = bool(self.shell.hwnd and window_visible(self.shell.hwnd))
        idle = self._idle_clicks
        self._idle_clicks = 0
        if not closed and not self.armed and not visible:
            return          # nada a decidir, nada a escrever
        log(f'OUTSIDE_CLICK source={source} point=({x},{y}) '
            f'decision={reason} closed={str(closed).lower()} '
            f'armed={str(self.armed).lower()} '
            f'visible={str(visible).lower()}'
            + (f' ignored_since_last={idle}' if idle else ''))

def _unpack_point(packed):
    """One integer carries both coordinates: x in the low 16 bits, y above."""
    value = int(packed)
    x = value & 0xFFFF
    y = (value >> 16) & 0xFFFF
    if x >= 0x8000:
        x -= 0x10000
    if y >= 0x8000:
        y -= 0x10000
    return x, y


def _pack_point(x, y):
    return (int(x) & 0xFFFF) | ((int(y) & 0xFFFF) << 16)


def _window_is_ours(hwnd) -> bool:
    """True when `hwnd` belongs to THIS process (our menu, our dialog).

    REPOSTO 2026-11-01: o nome era usado em dois sítios (`ClickWatcher._poll`, na
    recusa de contar o próprio painel como "outra janela", e
    `click_outside_reason`, na razão `our-own-window`), e a definição
    DESAPARECEU numa fusão de ramos que a traziam de lados diferentes -- nenhum
    dos dois lados a continha depois da resolução. Nada a apanhou: compila
    (é um nome, não um símbolo), e o `NameError` só nasce no tick em que a
    função corre. Foi encontrado por um varrimento de nomes indefinidos
    (`_main/undefined-names-oracle.py`), não pelo compilador nem pela bateria.
    """
    if not hwnd:
        return False
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(wt.HWND(hwnd), ctypes.byref(pid))
    return int(pid.value) == os.getpid()


def _point_in_window(hwnd, x, y) -> bool:
    rect = RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return False
    return (rect.left - CLICK_OUTSIDE_SLACK <= x <= rect.right + CLICK_OUTSIDE_SLACK
            and rect.top - CLICK_OUTSIDE_SLACK <= y <= rect.bottom + CLICK_OUTSIDE_SLACK)

NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x01, 0x02, 0x04
NIF_INFO = 0x10                  # balloon tip: informs without blocking
MF_STRING, MF_SEPARATOR = 0x0000, 0x0800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x0002, 0x0100
HWND_MESSAGE = -3

TRAY_ID = 0xB0F1              # any uid; this one is ours
ID_TRAY_OPEN = 1              # "Open panel"
ID_TRAY_QUIT = 2              # "Quit Sotto" — the one the owner named
#: "Edit caption position" — the edit mode's ONLY entrance (owner's lane brief:
#: now that the tray exists it is the obvious home, and it is impossible to
#: trigger by accident while reading a caption). A 4th id, so the two shipped
#: items keep their numbers and the tray probe's `[2]='Quit Sotto'` lookup works.
ID_TRAY_EDIT = 3
TRAY_WINDOW_CLASS = 'SottoTrayWindow'
TRAY_TIP = 'Sotto — Alt+C shows the captions'

# Argtypes for the tray's own calls. Without them ctypes converts a Python int
# to a 32-bit C int and an HWND/HICON above 2**31 raises OverflowError.
user32.RegisterClassExW.restype = wt.WORD
user32.RegisterClassExW.argtypes = [ctypes.c_void_p]
user32.CreateWindowExW.restype = wt.HWND
user32.CreateWindowExW.argtypes = [wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, wt.HWND, wt.HMENU,
                                   wt.HINSTANCE, ctypes.c_void_p]
user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t,
                                  ctypes.c_ssize_t]
user32.GetMessageW.restype = ctypes.c_int
user32.GetMessageW.argtypes = [ctypes.c_void_p, wt.HWND, ctypes.c_uint,
                               ctypes.c_uint]
user32.TranslateMessage.argtypes = [ctypes.c_void_p]
user32.DispatchMessageW.restype = ctypes.c_ssize_t
user32.DispatchMessageW.argtypes = [ctypes.c_void_p]
user32.PostQuitMessage.argtypes = [ctypes.c_int]
user32.PostMessageW.restype = wt.BOOL
user32.PostMessageW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t,
                                ctypes.c_ssize_t]
user32.CreatePopupMenu.restype = wt.HMENU
user32.AppendMenuW.restype = wt.BOOL
user32.AppendMenuW.argtypes = [wt.HMENU, ctypes.c_uint, ctypes.c_size_t,
                               wt.LPCWSTR]
user32.TrackPopupMenu.restype = ctypes.c_int
user32.TrackPopupMenu.argtypes = [wt.HMENU, ctypes.c_uint, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wt.HWND,
                                  ctypes.c_void_p]
user32.DestroyMenu.restype = wt.BOOL
user32.DestroyMenu.argtypes = [wt.HMENU]
user32.GetMenuItemCount.restype = ctypes.c_int
user32.GetMenuItemCount.argtypes = [wt.HMENU]
user32.GetMenuItemID.restype = ctypes.c_uint
user32.GetMenuItemID.argtypes = [wt.HMENU, ctypes.c_int]
user32.GetMenuStringW.restype = ctypes.c_int
user32.GetMenuStringW.argtypes = [wt.HMENU, ctypes.c_uint, wt.LPWSTR,
                                  ctypes.c_int, ctypes.c_uint]
user32.GetCursorPos.argtypes = [ctypes.c_void_p]
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.LoadImageW.restype = wt.HANDLE
user32.LoadImageW.argtypes = [wt.HINSTANCE, wt.LPCWSTR, ctypes.c_uint,
                              ctypes.c_int, ctypes.c_int, ctypes.c_uint]
user32.DestroyIcon.argtypes = [wt.HICON]
kernel32.GetModuleHandleW.restype = wt.HMODULE
kernel32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
shell32.Shell_NotifyIconW.restype = wt.BOOL
shell32.Shell_NotifyIconW.argtypes = [wt.DWORD, ctypes.c_void_p]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ('cbSize', wt.DWORD), ('hWnd', wt.HWND), ('uID', ctypes.c_uint),
        ('uFlags', ctypes.c_uint), ('uCallbackMessage', ctypes.c_uint),
        ('hIcon', wt.HICON), ('szTip', wt.WCHAR * 128),
        ('dwState', wt.DWORD), ('dwStateMask', wt.DWORD),
        ('szInfo', wt.WCHAR * 256), ('uVersion', ctypes.c_uint),
        ('szInfoTitle', wt.WCHAR * 64), ('dwInfoFlags', wt.DWORD),
        ('guidItem', ctypes.c_byte * 16), ('hBalloonIcon', wt.HICON),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint), ('style', ctypes.c_uint),
        ('lpfnWndProc', ctypes.c_void_p), ('cbClsExtra', ctypes.c_int),
        ('cbWndExtra', ctypes.c_int), ('hInstance', wt.HINSTANCE),
        ('hIcon', wt.HICON), ('hCursor', ctypes.c_void_p),
        ('hbrBackground', ctypes.c_void_p), ('lpszMenuName', wt.LPCWSTR),
        ('lpszClassName', wt.LPCWSTR), ('hIconSm', wt.HICON),
    ]


class TrayIcon:
    """A notification-area icon with a real context menu.

    `on_command` is called with the menu id, from the tray thread. The menu is
    built with `TPM_RETURNCMD` and the chosen id is then posted back as a REAL
    `WM_COMMAND`, so the probe can drive the same handler the menu drives
    (`PostMessageW(tray_hwnd, WM_COMMAND, ID_TRAY_QUIT, 0)`) instead of a test
    hook that bypasses it.
    """

    def __init__(self, icon_path, on_command, log_fn, warn_fn):
        self.icon_path = icon_path
        self.on_command = on_command
        self.log = log_fn
        self.warn = warn_fn
        self.hwnd = None
        self.hicon = None
        self.menu = None
        self._thread = None
        self._ready = threading.Event()
        self._added = False
        self._wndproc = None
        self._failed = None
        self._taskbar_created_msg = None

    # -- lifecycle ---------------------------------------------------------
    def start(self, timeout=5.0) -> bool:
        self._thread = threading.Thread(target=self._run, name='sotto-tray',
                                        daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        # The window existing is NOT proof the icon was added: `_run` returns
        # early when `_add` fails, leaving `hwnd` set but `_ready` unset. Report
        # the truth (icon added), not the window handle.
        return bool(self._ready.is_set() and self._added and self.hwnd)

    def stop(self, reason='stop'):
        if self.hwnd:
            try:
                self._delete()
                user32.PostMessageW(self.hwnd, WM_TRAY_STOP, 0, 0)
            except Exception:  # noqa: BLE001
                pass
        # NEVER JOIN THE CURRENT THREAD. The Quit is handled ON this thread (the
        # menu command arrives as a message), so `join` on it raised
        # `RuntimeError: cannot join current thread` — measured 2026-10-08, and
        # it left the shell ALIVE with its worker after the owner had asked it to
        # close: an app that will not quit is worse than one that will not start.
        # `PostQuitMessage` above ends the loop, so the thread stops by itself.
        if (self._thread is not None and self._thread.is_alive()
                and self._thread is not threading.current_thread()):
            self._thread.join(2)
        self.log(f'TRAY_STOP reason={reason} hwnd={self.hwnd}')

    # -- the icon ----------------------------------------------------------
    def _nid(self):
        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = TRAY_ID
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAY_CALLBACK
        nid.hIcon = self.hicon
        nid.szTip = TRAY_TIP
        return nid

    def _add(self):
        nid = self._nid()
        ok = bool(shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)))
        err = ctypes.get_last_error()
        self.log(f'TRAY_ICON_ADD ok={str(ok).lower()} uid={TRAY_ID} '
                 f'cbSize={nid.cbSize} hicon={self.hicon} '
                 f'icon={self.icon_path} winerror={err}')
        return ok

    def _modify(self):
        nid = self._nid()
        ok = bool(shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)))
        err = ctypes.get_last_error()
        self.log(f'TRAY_ICON_MODIFY ok={str(ok).lower()} uid={TRAY_ID} '
                 f'winerror={err}')
        return ok

    def _delete(self):
        nid = self._nid()
        ok = bool(shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid)))
        self.log(f'TRAY_ICON_DELETE ok={str(ok).lower()} uid={TRAY_ID}')
        return ok

    def balloon(self, title, text, info_flags=0x1):
        """A NON-MODAL notice, in the notification area.

        OWNER, 2026-10-22 09:17, verbatim: *"para de mostrar erro. e gritar."*
        A modal `MessageBoxW` is the loudest thing Windows can put on his screen and
        it BLOCKS until dismissed, so it is exactly what that order forbids. The tray
        balloon says the same thing, is dismissed by itself and steals no focus (this
        shell never takes focus by design). The caller keeps the full text in the log,
        so nothing becomes unfalsifiable.

        `info_flags` defaults to NIIF_INFO (0x1). NIIF_ERROR is deliberately NOT used:
        an unavailable hotkey is not an error to shout about.
        """
        if not (self._added and self.hwnd):
            return False
        nid = self._nid()
        nid.uFlags = NIF_INFO
        nid.szInfoTitle = (title or '')[:63]
        nid.szInfo = (text or '')[:255]
        nid.dwInfoFlags = info_flags
        ok = bool(shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid)))
        self.log(f'TRAY_BALLOON ok={str(ok).lower()} uid={TRAY_ID} '
                 f'winerror={ctypes.get_last_error()}')
        return ok

    # -- the thread --------------------------------------------------------
    def _run(self):
        try:
            self._create_window()
            if not self._load_icon():
                return
            added = self._add()
            if not added:
                # A stale icon from a dead instance (or a transient explorer
                # hiccup) can make NIM_ADD fail even though the (hwnd, uid) is
                # ours. Clear any stale entry, then re-add; fall back to MODIFY
                # if the icon is already present. This is what makes the icon
                # appear even when a previous run did not clean up.
                self._delete()
                time.sleep(0.3)
                added = self._add()
            if not added:
                added = self._modify()
            if not added:
                self._failed = 'Shell_NotifyIcon ADD/MODIFY failed'
                self.warn(f'TRAY_UNAVAILABLE the notification-area icon did not '
                          f'come up (add+modify both failed); the app keeps '
                          f'running and Alt+C still works, but the Quit has no '
                          f'home (error={self._failed})')
                return
            self._added = True
            # The menu is BUILT AND LOGGED at startup, so its Quit item (id and
            # text) is on the record without anyone having to right-click. It is
            # destroyed here and rebuilt when it is actually drawn.
            user32.DestroyMenu(self._build_menu())
            self.menu = None
            self._ready.set()
            self._pump()
        except Exception as exc:  # noqa: BLE001 -- a tray must not kill the app
            self._failed = f'{type(exc).__name__}: {exc}'
            self.warn(f'TRAY_FAILED error={self._failed}')
            self._ready.set()
        finally:
            if self.hicon:
                user32.DestroyIcon(self.hicon)
                self.hicon = None

    def _load_icon(self) -> bool:
        """The SAME .ico the window wears — `LoadImageW` from the file."""
        if not self.icon_path or not os.path.isfile(self.icon_path):
            self.warn(f'TRAY_ICON_MISSING path={self.icon_path}')
            return False
        IMAGE_ICON, LR_LOADFROMFILE, LR_DEFAULTSIZE = 1, 0x0010, 0x0040
        handle = user32.LoadImageW(None, self.icon_path, IMAGE_ICON,
                                  16, 16, LR_LOADFROMFILE)
        if not handle:
            self.warn(f'TRAY_ICON_LOAD_FAILED path={self.icon_path} '
                      f'winerror={ctypes.get_last_error()}')
            return False
        self.hicon = handle
        return True

    def _create_window(self):
        hinst = kernel32.GetModuleHandleW(None)
        self._wndproc = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND,
                                           ctypes.c_uint, ctypes.c_size_t,
                                           ctypes.c_ssize_t)(self._on_message)
        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.lpszClassName = TRAY_WINDOW_CLASS
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS is fine (a restart)
                raise OSError(err, 'RegisterClassExW')
        hwnd = user32.CreateWindowExW(0, TRAY_WINDOW_CLASS, '', 0, 0, 0, 0, 0,
                                      HWND_MESSAGE, None, hinst, None)
        if not hwnd:
            raise OSError(ctypes.get_last_error(), 'CreateWindowExW')
        self.hwnd = int(hwnd)
        try:
            user32.RegisterWindowMessageW.restype = wt.UINT
            user32.RegisterWindowMessageW.argtypes = [wt.LPCWSTR]
            self._taskbar_created_msg = int(user32.RegisterWindowMessageW(
                'TaskbarCreated'))
        except Exception:  # noqa: BLE001
            self._taskbar_created_msg = 0
        self.log(f'TRAY_WINDOW created=true hwnd={self.hwnd} '
                 f'class={TRAY_WINDOW_CLASS} message_only=true '
                 f'taskbar_created_msg={self._taskbar_created_msg}')

    def _on_message(self, hwnd, msg, wparam, lparam):
        if (getattr(self, '_taskbar_created_msg', 0)
                and msg == self._taskbar_created_msg):
            try:
                self._delete()
                if not self._add():
                    self._modify()
                self.log('TRAY_READDED reason=taskbar-created')
            except Exception as exc:  # noqa: BLE001
                self.warn(f'TRAY_READD_FAILED {type(exc).__name__}: {exc}')
            return 0
        if msg == WM_TRAY_CALLBACK:
            if lparam in (WM_RBUTTONUP, WM_LBUTTONUP):
                self._show_menu()
            return 0
        if msg == WM_COMMAND:
            command = int(wparam) & 0xFFFF
            self.log(f'TRAY_COMMAND id={command}')
            try:
                self.on_command(command)
            except Exception as exc:  # noqa: BLE001
                self.warn(f'TRAY_COMMAND_FAILED id={command} '
                          f'{type(exc).__name__}: {exc}')
            return 0
        if msg == WM_TRAY_STOP:
            user32.PostQuitMessage(0)
            return 0
        if msg == WM_DESTROY:
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_menu(self):
        menu = self._build_menu()
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        # SetForegroundWindow is what makes the menu dismiss correctly when the
        # owner clicks elsewhere; without it the menu can be left orphaned.
        user32.SetForegroundWindow(wt.HWND(self.hwnd))
        command = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD,
                                        pt.x, pt.y, 0, wt.HWND(self.hwnd),
                                        None)
        user32.DestroyMenu(menu)
        self.menu = None
        if command:
            # A REAL WM_COMMAND, so the menu and the probe take one path.
            user32.PostMessageW(wt.HWND(self.hwnd), WM_COMMAND, command, 0)

    def _build_menu(self):
        """Built, LOGGED, and then drawn — so the log proves every item exists
        (its id and its text) without anyone having to click.

        THREE items now, and the two shipped ids keep their numbers: `[1]` Open
        panel (the FULL panel — Alt+C is what opens the strip), `[3]` Edit
        caption position, `[2]` Quit Sotto. `_main/tray-quit-probe.py` finds the
        Quit by its TEXT (`[2]='Quit Sotto'`), so a new item cannot break it.
        """
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, MF_STRING, ID_TRAY_OPEN, 'Open panel')
        user32.AppendMenuW(menu, MF_STRING, ID_TRAY_EDIT,
                           'Edit caption position')
        user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
        user32.AppendMenuW(menu, MF_STRING, ID_TRAY_QUIT, 'Quit Sotto')
        self.menu = int(menu)
        items = menu_items(menu)
        self.log('TRAY_MENU ' + ' '.join(
            f"[{i['id']}]={i['text']!r}" if i['id'] else '[sep]'
            for i in items))
        return menu

    def _pump(self):
        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        self.log('TRAY_LOOP_EXIT')


def menu_items(menu) -> list:
    """The items of an HMENU, as Windows has them — id and text."""
    count = user32.GetMenuItemCount(menu)
    items = []
    buf = ctypes.create_unicode_buffer(128)
    for index in range(count):
        ident = user32.GetMenuItemID(menu, index)
        user32.GetMenuStringW(menu, index, buf, 128, 0x0400)  # MF_BYPOSITION
        items.append({'index': index, 'id': int(ident),
                      'text': buf.value if ident else ''})
    return items


def warn_hotkey_unavailable(requested: str, tried, tray=None) -> None:
    """The app's ONLY control could not be registered: say it QUIETLY, once.

    THE HISTORY MATTERS, because this function has now been decided TWICE and the
    second decision is the one that stands:

      2026-10-07 -- the shipped behaviour was one log line and nothing on screen, so
                    an app whose hotkey was taken stayed running, hidden, with its
                    only control dead. The cure was a modal `MessageBoxW`.
      2026-10-22 09:17 -- the owner, verbatim: *"para de mostrar erro. e gritar."*
                    A modal error box is the loudest thing this shell can put on his
                    screen and it blocks until dismissed. So the modal is GONE and the
                    channel is a tray balloon (`TrayIcon.balloon`): it informs, it
                    dismisses itself, it steals no focus.

    What does NOT come back is the original defect: the message is still SHOWN (as a
    balloon) and the full text is still in the log (`HOTKEY_UNAVAILABLE`), so "the app
    is running and I cannot open it" remains falsifiable from the owner's side. When
    there is no tray to speak through, the log is the only channel and it says so
    (`HOTKEY_ALERT_SHOWN shown=false channel=log-only`).
    """
    lines = ', '.join(f'{a} (winerror={err})' for a, err in tried) or f'{requested}'
    title = 'Sotto - key already taken'
    text = ('Alt+C is owned by another program, so the panel cannot be opened with '
            f'the keyboard. Sotto is still running and transcribing. Keys tried: '
            f'{lines}. Fix: close the other program, or start with run.cmd '
            '--hotkey Alt+Shift+C')
    log('HOTKEY_UNAVAILABLE alert=balloon tried=' + json.dumps([a for a, _ in tried]))
    shown = False
    if tray is not None:
        try:
            shown = bool(tray.balloon(title, text))
        except Exception as exc:  # noqa: BLE001 -- a warning must not kill a run
            log(f'HOTKEY_ALERT_FAILED error={exc!r}')
    log('HOTKEY_ALERT_SHOWN shown=%s channel=%s'
        % (str(shown).lower(), 'balloon' if shown else 'log-only'))


def arm_hotkey(shell, requested: str):
    """Arma AS DUAS hotkeys e devolve o thread dos PAINEIS (ou None).

    Ordem do dono, 2026-11-01: *"bota o padrao como control espaco. e os painels
    deixa alt c"*. Duas teclas, dois threads, dois `RegisterHotKey` -- cada uma
    com a sua fila, por isso uma tecla presa nunca atrasa a outra.

    A TECLA DA LEGENDA VEM DO FICHEIRO DO DONO (`hotkey_settings.accelerators`),
    e o valor de fabrica (`hotkey_gesture.LIVE_ACCELERATOR`) e' o que ele pediu.
    A dos PAINEIS e' a que o comando pediu (`--hotkey`, fabrica `Alt+C`).

    PORQUE E' QUE OS PAINEIS TEM CADEIA DE FALLBACK E A LEGENDA NAO. O Alt+C e'
    o unico controlo que abre a app: se estiver tomado (outro programa), uma
    segunda escolha transforma uma app inutilizavel numa app com outra tecla. A
    legenda ao vivo tem o botao LIVE do painel como caminho alternativo, por isso
    a tecla dela falhar e' um recuo, nao um brick -- e inventar uma cadeia para
    ela seria uma segunda tecla que ninguem pediu.
    """
    panels = arm_hotkey_role(shell, 'panels', requested, HOTKEY_FALLBACKS)
    #: UMA MEDIÇÃO NÃO PODE SENTAR-SE NA TECLA DELE. Medido 2026-11-01 10:14:30:
    #: uma instância largada para medir pediu `Ctrl+Space`, a app do dono já a
    #: tinha, e o log dela ficou com `HOTKEY_REGISTER_FAILED role=live
    #: winerror=1409` — a tecla do dono e' exclusiva do processo que a registou
    #: primeiro, e o inverso também e' verdade (uma medição que a apanhe primeiro
    #: deixa a app dele sem ela). A variável de ambiente é o mesmo caminho que o
    #: `--hotkey` já abre para os painéis, e ausente não muda nada.
    override = os.environ.get('SOTTO_LIVE_HOTKEY')
    if override:
        live = override
    else:
        try:
            live = hotkey_config().accelerators()['live']
        except Exception as exc:  # noqa: BLE001 -- a fabrica e' sempre uma resposta
            log(f'HOTKEY_LIVE_CONFIG_FAILED error={exc!r} '
                f'default={hotkey_numbers().LIVE_ACCELERATOR}')
            live = hotkey_numbers().LIVE_ACCELERATOR
    shell.live_hotkey = arm_hotkey_role(shell, 'live', live, ())
    return panels


def arm_hotkey_role(shell, role: str, requested: str, fallbacks):
    """Regista `requested` (e a cadeia `fallbacks`) para `role`; devolve o thread."""
    order = [requested] + [a for a in fallbacks if a != requested]
    tried = []
    callback = (lambda: shell.hotkey_live()) if role == 'live' else (
        lambda: shell.hotkey_pressed())
    for accelerator in order:
        try:
            # A LEGENDA E' OBSERVADA, O PAINEL E' REGISTADO (2026-11-02).
            # `RegisterHotKey` TOMA a combinacao: com o Sotto vivo o `Ctrl+Space`
            # nunca chegava ao jogo do dono -- *"control mais espaço é crouch e
            # jump no jogo... nao ta funcionando, por causa do sotto"*. O gesto da
            # legenda le o ESTADO das teclas e deixa a tecla passar; o Alt+C
            # continua registado porque, ali, ser tomado e' o que se quer.
            if role == 'live':
                thread = PassiveHotkeyThread(accelerator, callback, role=role)
            else:
                thread = HotkeyThread(accelerator, callback, role=role)
        except ValueError as exc:
            # Uma tecla que o parser recusa nao chega a `RegisterHotKey`: e' um
            # recado, e a cadeia continua (nos paineis) ou fica sem tecla (na
            # legenda, com o botao do painel no lugar).
            log(f'HOTKEY_ACCELERATOR_REFUSED role={role} '
                f'accelerator={accelerator!r} error={exc!r}')
            tried.append((accelerator, 'refused'))
            continue
        thread.start()
        thread.wait_ready(5)
        if thread.registered:
            if accelerator != requested:
                warn(f'HOTKEY_FALLBACK role={role} requested={requested} '
                     f'using={accelerator} '
                     'reason=requested-owned-by-another-program')
            return thread
        tried.append((accelerator, thread.register_error))
        log(f'HOTKEY_TRY_FAILED role={role} accelerator={accelerator} '
            f'winerror={thread.register_error}')
    if role == 'live':
        log(f'HOTKEY_LIVE_UNAVAILABLE accelerator={requested} '
            f'tried={json.dumps([a for a, _ in tried])} '
            'the panel LIVE button still toggles the caption')
        return None
    warn_hotkey_unavailable(requested, tried, getattr(shell, 'tray', None))
    return None


# ===========================================================================
# start with Windows (HKCU\...\Run) — the owner asked for "iniciar com o windows"
# ===========================================================================
#: The Run value's name: what the owner sees in Task Manager → Startup.
AUTOSTART_VALUE_NAME = 'Sotto'
AUTOSTART_RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'


def autostart_command() -> str:
    """The command Windows should run at login — `pythonw.exe`, never cmd.exe.

    `run.cmd` cannot be the target: a `.cmd` is a console program, so Windows
    would flash a console window at every login, and this project forbids console
    windows on the owner's screen (measured: a stray `python` console was named by
    the house census and complained about twice). `pythonw.exe` is a GUI-subsystem
    binary: no console, no window, and the shell then does exactly what a
    double-click does — including starting the worker (F1).

    Both paths are QUOTED because `C:\\Program Files\\...` contains a space, and
    the log is passed so an autostart that fails leaves a receipt in the same file
    every other launch writes to.
    """
    pythonw = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
    if not os.path.exists(pythonw):
        pythonw = sys.executable  # a machine with no pythonw: still better than cmd
    shell = os.path.join(HERE, 'sotto_webview.py')
    log_path = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir,
                                             '_main', 'webview-run.log'))
    return f'"{pythonw}" "{shell}" --log "{log_path}"'


def autostart_install() -> int:
    """Write the Run value. Idempotent; prints what it wrote."""
    import winreg  # local: keep this module importable on a box without winreg

    command = autostart_command()
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, AUTOSTART_RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, AUTOSTART_VALUE_NAME, 0, winreg.REG_SZ,
                              command)
    except OSError as exc:
        print(f'sotto: AUTOSTART_INSTALL_FAILED {exc!r}')
        return 1
    print(f'sotto: AUTOSTART_INSTALLED name={AUTOSTART_VALUE_NAME}')
    print(f'sotto:   HKCU\\{AUTOSTART_RUN_KEY}\\{AUTOSTART_VALUE_NAME} = {command}')
    print('sotto: it starts hidden at login and waits for Alt+C; nothing appears '
          'until you ask.')
    print('sotto: to undo it:  run.cmd --uninstall-autostart')
    log(f'AUTOSTART_INSTALLED command={json.dumps(command)}')
    return 0


def autostart_uninstall() -> int:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, AUTOSTART_VALUE_NAME)
    except FileNotFoundError:
        print('sotto: AUTOSTART_NOT_INSTALLED (nothing to remove)')
        log('AUTOSTART_UNINSTALL name=absent')
        return 0
    except OSError as exc:
        print(f'sotto: AUTOSTART_UNINSTALL_FAILED {exc!r}')
        return 1
    print(f'sotto: AUTOSTART_REMOVED name={AUTOSTART_VALUE_NAME}')
    log('AUTOSTART_REMOVED')
    return 0


def autostart_status() -> int:
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_RUN_KEY, 0,
                            winreg.KEY_QUERY_VALUE) as key:
            value, _ = winreg.QueryValueEx(key, AUTOSTART_VALUE_NAME)
    except FileNotFoundError:
        print('sotto: AUTOSTART=off (no Run value)')
        return 1
    except OSError as exc:
        print(f'sotto: AUTOSTART_STATUS_FAILED {exc!r}')
        return 2
    matches = os.path.normcase(value) == os.path.normcase(autostart_command())
    print(f'sotto: AUTOSTART=on  value={value}')
    print(f'sotto:   matches this checkout: {matches}  '
          f'(expected: {autostart_command()})')
    return 0 if matches else 3


# ===========================================================================
# the page bridge — the port of app/_legacy-electron/preload.js
# ===========================================================================

#: Injected into the page's main world before any page script, on every
#: navigation. This is `preload.js` with its Electron transport swapped for
#: WebView2's, and its API surface IDENTICAL: same method names, same argument
#: order, same callback shape, same constants.
BOOTSTRAP_JS = r"""
(function () {
  'use strict';
  if (window.sotto) return;   // a second injection must not replace a live bridge

  var subs = { caption: [], 'external-caption': [], status: [], geometry: [], stats: [] };
  var queue = [];
  var infoSeq = 0;
  var infoPending = {};
  // THE STATS ROUND-TRIP (ported 2026-10-11 from the 55c422b reference, its
  // lines 2336-2349 + 2227-2233). Measured gap in the live shell: Python
  // `reply_stats` already calls `window.__sotto_stats(id, json)` (this file,
  // `reply_stats`) and `emit_async('stats', ...)` already pushes -- but the
  // page defined NO `__sotto_stats`, NO `getStats` and NO `onStats`, and
  // `subs` had no `stats` topic, so every push went into `subs[kind] || []`
  // and every poll had nothing to resolve. The meter therefore stayed at the
  // floor with the whole channel apparently present on the Python side.
  var statsSeq = 0;
  var statsPending = {};

  function emit(kind, payload) {
    var list = subs[kind] || [];
    for (var i = 0; i < list.length; i++) {
      try { list[i](payload); }
      catch (err) {
        console.error('sotto: a ' + kind + ' listener threw: ' +
          (err && err.message ? err.message : err));
      }
    }
  }

  function channelOpen() {
    return !!(window.pywebview && window.pywebview._returnValuesCallbacks &&
              window.chrome && window.chrome.webview);
  }

  function wire(kind, payload) {
    // Three rules, all measured against pywebview 6.2.1 on this host:
    //  1. The message is an ARRAY. Its pump does
    //     `func_name, func_param, value_id = json.loads(get_WebMessageAsJson())`
    //     (edgechromium.py:244); posting a string hands it one long string and
    //     it raises "too many values to unpack (expected 3)".
    //  2. The middle slot is `JSON.stringify(arguments)` — an ARRAY of
    //     POSITIONAL arguments, because pywebview then does
    //     `func(*func_params)` (util.py:255). Posting a bare object made Python
    //     unpack its KEYS: `ready({captions, placeholder, hasBridge})` arrived
    //     as three positional strings ("SottoHost.dispatch() takes 2
    //     positional arguments but 3 were given").
    //  3. Each element is encoded ONCE. pywebview json.loads()s the slot and
    //     hands the element to Python as-is, so the element must already be
    //     the STRING `dispatch` expects. Encoding the object twice handed
    //     Python a dict instead ("the JSON object must be str, bytes or
    //     bytearray, not dict").
    return ['dispatch',
            JSON.stringify([JSON.stringify({ kind: kind, payload: payload })]),
            '0'];
  }

  function post(kind, payload) {
    var message = wire(kind, payload);
    if (!channelOpen()) { queue.push(message); return; }
    window.chrome.webview.postMessage(message);
  }

  function ensureSink() {
    // pywebview answers every message it dispatched by calling
    // `_returnValuesCallbacks[funcName][valueId]` (util.py:264-266). That slot
    // is normally created by `_createApi` when the page calls the api THROUGH
    // pywebview; we post on the raw channel, so nothing created it and every
    // message raised
    // "window.pywebview._returnValuesCallbacks.dispatch.0 is not a function".
    // This host has no synchronous return values to hand back — main -> page
    // is ExecuteScriptAsync and page -> main is fire-and-forget — so a sink
    // that drops the value is the whole truthfulness of the situation.
    var slots = window.pywebview._returnValuesCallbacks;
    if (!slots.dispatch) slots.dispatch = {};
    if (typeof slots.dispatch['0'] !== 'function') {
      slots.dispatch['0'] = function (returnObj) {
        if (returnObj && returnObj.isError) {
          console.error('sotto: host dispatch returned an error: ' +
            returnObj.value);
        }
      };
    }
  }

  function flush() {
    if (!channelOpen()) return false;
    ensureSink();
    while (queue.length) window.chrome.webview.postMessage(queue.shift());
    return true;
  }

  // `bridge.ready()` is called while panel.js is still parsing, long before
  // pywebview has injected its api. Buffering until the channel opens is what
  // lets panel.js run unmodified instead of being special-cased.
  window.addEventListener('pywebviewready', flush);
  if (!flush()) setInterval(flush, 50);

  function normalise(text, meta) {
    if (text == null) return null;
    var value = String(text).replace(/\s+/g, ' ').trim();
    if (value === '') return null;
    return { text: value, meta: (meta && typeof meta === 'object') ? meta : {} };
  }

  // A COUNT OF WHAT ARRIVED, per kind (reference 2227-2233). The panel's
  // level meter is fed BOTH by a poll and by this push, so a reader that only
  // saw `data-level=live` could not tell a working push from a poll doing all
  // the work. `_main/_strip-stats-probe.py` reads this counter and requires
  // the PUSH to have landed more than once.
  window.__sotto_emit = function (kind, json) {
    var payload = null;
    try { payload = JSON.parse(json); } catch (err) { payload = null; }
    window.__sotto_emit.counts[kind] = (window.__sotto_emit.counts[kind] || 0) + 1;
    emit(kind, payload);
  };
  window.__sotto_emit.counts = {};
  // `__sotto_emit` fala com os SUBSCRITORES DA PAGINA (`emit`), nao com o Python.
  // Um medidor que chega antes de `panel.js` nao tem subscritor nenhum: o
  // resultado dele morria aqui. Este e' o caminho que ENTREGA (`post`), exposto
  // com nome por isso mesmo -- 2026-11-04, medido: o perfil de arranque ficou
  // 24 h a recolher e a descartar (0 `PANEL_BOOT_PROFILE` em 469 587 linhas).
  window.__sotto_post = function (kind, payload) { post(kind, payload); };

  window.__sotto_info = function (id, json) {
    var resolve = infoPending[id];
    if (!resolve) return;
    delete infoPending[id];
    try { resolve(JSON.parse(json)); } catch (err) { resolve({ error: String(err) }); }
  };

  // Same id round-trip as `__sotto_info`, for `getStats`. Without this the
  // shell's own `window.__sotto_stats(...)` call is a silent no-op and the
  // Promise from `getStats()` never resolves -- which is exactly what the
  // owner's log showed: 595 BRIDGE_STATS_REPLY lines and a dead meter.
  window.__sotto_stats = function (id, json) {
    var resolve = statsPending[id];
    if (!resolve) return;
    delete statsPending[id];
    try { resolve(JSON.parse(json)); } catch (err) { resolve({ error: String(err) }); }
  };

  // The history store round-trip. Same shape as getInfo's id round-trip, so
  // `history.tail()`/`search()`/`append()` really resolve with disk data
  // instead of handing back a synchronous guess.
  var histSeq = 0;
  var histPending = {};
  window.__sotto_history = function (id, json) {
    var resolve = histPending[id];
    if (!resolve) return;
    delete histPending[id];
    try { resolve(JSON.parse(json)); } catch (err) { resolve({ error: String(err) }); }
  };
  function historyCall(kind, payload) {
    return new Promise(function (resolve) {
      var id = 'h' + (++histSeq);
      histPending[id] = resolve;
      var msg = payload || {};
      msg.id = id;
      post(kind, msg);
    });
  }

  function subscribe(kind, callback) {
    if (typeof callback !== 'function') return function () {};
    subs[kind].push(callback);
    return function () {
      var i = subs[kind].indexOf(callback);
      if (i >= 0) subs[kind].splice(i, 1);
    };
  }

  window.sotto = {
    pushCaption: function (text, meta) {
      var caption = normalise(text, meta);
      if (!caption) return false;
      post('caption-observed', caption);
      emit('caption', caption);
      return true;
    },

    setStatus: function (text) {
      var value = String(text == null ? '' : text);
      post('status-observed', { text: value });
      emit('status', value);
      return true;
    },

    onCaption: function (cb) { return subscribe('caption', cb); },
    // THE PLAYER'S OWN CAPTIONS (YouTube/Stremio). A separate channel because
    // each line REPLACES the live box instead of joining the ASR hypothesis.
    onExternalCaption: function (cb) { return subscribe('external-caption', cb); },
    onStatus: function (cb) { return subscribe('status', cb); },
    onGeometry: function (cb) { return subscribe('geometry', cb); },
    onStats: function (cb) { return subscribe('stats', cb); },

    hide: function () { post('hide', null); },
    toggle: function () { post('toggle', null); },
    quit: function () { post('quit', null); },

    // THE REPAIR CONTROL (panel.js:2045). reviveSupported() (:2007) gates the
    // status click on typeof bridge.revive === 'function', so this entry is
    // what turns the panel's only recovery path from a dead click into a
    // request the shell answers (SottoShell.revive_worker).
    revive: function (reason) {
      post('revive', { reason: String(reason == null ? 'panel' : reason) });
    },

    setPointerInteractive: function (active) {
      post('pointer', { active: Boolean(active) });
    },

    // Strip lane: panel asks the shell for click-through chrome while it
    // keeps painting captions. Documented shell message `sotto:transparency`
    // with `{ on: bool }`. No-op honest when the shell has no window yet.
    setTransparency: function (on) {
      post('transparency', { on: Boolean(on) });
    },

    // THE MISSING CHANNEL, AND IT IS WHY THE DEFERRED ASSETS NEVER LOADED.
    //
    // MEASURED 2026-10-13. `lazy-assets.js:144` asks for a deferred asset with
    //     if (s && typeof s.dispatch === 'function') { s.dispatch('lazy-asset', ...); return; }
    //     if (window.pywebview && window.pywebview.api && window.pywebview.api.dispatch) { ... }
    // and `window.sotto.dispatch` DID NOT EXIST -- grep over this file returned ZERO.
    // So the loader fell through to `window.pywebview.api.dispatch`, which is NOT the
    // channel this shell listens on: `post()` (:2805-2808) publishes on
    // `window.chrome.webview.postMessage`. RESULT, measured on a `cine-cellar` theme:
    //     PANEL_LAZY_ALLOW 0    the page NEVER asked
    //     PANEL_LAZY_EMPTY 4    the gate answered 4 requests with EMPTY 200s
    // so `cinematic.css`, `panel-designs.css`, `skins/skins.js`, `skin-host.js` and
    // `skin-layout.css` loaded as EMPTY BODIES. The designs and their fonts never
    // arrived, which is the owner's *"pouquissimas fontes"* and *"varios designs
    // estao bugados"* -- measured, not guessed.
    //
    // ONE LINE, and it is the same class of defect as `setStripOffset` below: this
    // object is hand-written, not generated from the Python API, so a method the page
    // probes for has to be declared here or the probe is false and the caller skips it
    // in silence.
    dispatch: function (kind, payload) {
      post(String(kind == null ? '' : kind), payload == null ? null : payload);
      return true;
    },

    // THE OWNER'S STRIP DRAG (panel.html:1087). `window.sotto` is THIS object,
    // hand-written here and not generated from the Python API, so without this
    // entry the page's `typeof bridge.setStripOffset === 'function'` probe is
    // FALSE and the whole shell half is skipped in silence -- the bar then moves
    // only INSIDE the window, which after the content-width fix is exactly the
    // pill, so it cannot move at all. `x`/`y` are CUMULATIVE DIP from the dock,
    // not deltas; `phase` is `"move"` during the drag and `"end"` on release.
    setStripOffset: function (x, y, phase) {
      post('setStripOffset', {
        x: Number(x) || 0,
        y: Number(y) || 0,
        phase: String(phase == null ? 'move' : phase),
      });
    },

    // THE NATIVE WINDOW DRAG (2026-10-17). ONE call per drag: the shell enters
    // Windows' own modal move loop (`ReleaseCapture` + `WM_NCLBUTTONDOWN` /
    // `HTCAPTION`) and persists the final rect when the owner releases the
    // mouse. There is no per-move message and no per-move `SetWindowPos`, which
    // is what the old JS drag was made of -- see `strip-drag.js`.
    beginWindowDrag: function (surface) {
      post('beginWindowDrag', { surface: surface == null ? '' : String(surface) });
    },

    // THE LIVE PILL (2026-10-17). It existed in the page but the shell had no
    // method, so `applyLiveEnabled` painted it `aria-disabled` and its own
    // title said the switch could not reach the engine. The shell now owns the
    // second window: `true` shows the independent caption overlay, `false`
    // hides it. Resolved synchronously because the visibility change is local.
    setLiveEnabled: function (on) {
      var want = !!on;
      post('setLiveEnabled', { on: want });
      return Promise.resolve({ liveEnabled: want });
    },

    // THE TRANSLATION TARGET (owner, 2026-10-21). The 3-dot menu's selector sends
    // the chosen language here; `''` means the DEFAULT POLICY (English for every
    // video, Spanish stays Spanish). A non-empty code forces that target for
    // EVERY video. The shell stores it and the caption fetcher reads it.
    setTranslationTarget: function (lang) {
      var want = String(lang == null ? '' : lang);
      post('translation-target', { lang: want });
      return Promise.resolve({ lang: want });
    },

    // PAUSE = UNLOAD (owner, 2026-10-17). The panel's pause controls have
    // always called `bridge.pause()`; the shell never had it, so the dialog
    // said "este shell ainda não consegue pausar". The shell now stops the
    // worker (which releases the CUDA context and its VRAM) and keeps the
    // process paused until the owner revives it.
    pause: function (payload) {
      post('pause', payload || {});
      return Promise.resolve({ paused: true, text: 'Paused - engines unloaded' });
    },

    // preload.js resolves a Promise here (ipcRenderer.invoke). The WebView2
    // transport has no invoke, so the id round-trip below is what makes this a
    // real resolved Promise rather than a synchronous object.
    getInfo: function () {
      return new Promise(function (resolve) {
        var id = 'i' + (++infoSeq);
        infoPending[id] = resolve;
        post('info', { id: id });
      });
    },

    // THE PANEL'S OWN PULL, once a second (`panel.js:2478`). The numbers are
    // the worker's own counters, whitelisted by `stats()`; a field the worker
    // did not print stays ABSENT rather than arriving as a zero this shell
    // invented.
    getStats: function () {
      return new Promise(function (resolve) {
        var id = 's' + (++statsSeq);
        statsPending[id] = resolve;
        post('stats', { id: id });
      });
    },

    // ── THE SURFACE CONTRACT (the shell resizes; the page only wears it) ─────
    // `app/panel/panel.js:1239-1243` calls THIS member and nothing else:
    //
    //     bridge.setPanelSurface('panel', reason)
    //
    // Its absence is not cosmetic. Without it `openFullPanel` falls through to
    // `panel.js:1245-1247` — "switch the layout here ... The strip is NOT short
    // until the window is" — so the strip's own "Open panel" button left the
    // window strip-sized. The shell answers by setting the document surface
    // (`window.SottoSurfaces.set`, the API `surface.js` defines) AND moving the
    // HWND to that surface's geometry, in the same breath.
    setPanelSurface: function (surface, reason) {
      post('panel-surface', {
        surface: String(surface == null ? '' : surface),
        reason: String(reason == null ? '' : reason)
      });
      return true;
    },
    captionApplied: function (text) {
      post('caption-applied', { text: String(text == null ? '' : text) });
    },
    statusApplied: function (text) {
      post('status-applied', { text: String(text == null ? '' : text) });
    },
    ready: function (payload) { post('renderer-ready', payload || {}); },
    clearApplied: function (remaining) {
      post('caption-cleared', { remaining: Number(remaining) || 0 });
    },

    // The transcript history ("redux"). The SHELL owns the disk: it names the
    // file, appends the line, reads it back and reveals it in the file manager.
    // `append` resolves with the entry as written (real path included), so the
    // panel never has to guess the folder layout.
    history: {
      append: function (text, meta) {
        return historyCall('history-append',
          { text: String(text == null ? '' : text), meta: meta || {} });
      },
      tail: function (limit) {
        return historyCall('history-tail', { limit: Number(limit) || 400 });
      },
      search: function (query, limit) {
        return historyCall('history-search',
          { query: String(query == null ? '' : query), limit: Number(limit) || 200 });
      },
      root: function () { return historyCall('history-root', {}); },
      reveal: function (path) {
        post('history-reveal', { path: String(path == null ? '' : path) });
      }
    },

    HOTKEY: 'Alt+C',
    platform: 'win32'
  };

  // ── PAGE ERRORS MUST REACH THE LOG, OR A BROKEN PANEL LOOKS LIKE A QUIET ONE ──
  // Measured 2026-10-07, on the owner's screen with a video playing: the worker
  // transcribed for 20+ s at peak 0.44 and the shell logged thousands of
  // `BRIDGE_CAPTION_SENT delivered=true` lines, while the panel kept showing
  // "Starting the worker" and `#caption-list` stayed `display:none`. NOTHING in
  // the log said why: a throw inside panel.js is invisible to Python, because
  // `evaluate_js` reports the CALL, not the page's own JavaScript. This hook runs
  // from document start (before the panel's scripts), so an init-time throw — the
  // case that silently kills every subscription — is reported with its source
  // position and stack.
  function reportPageError(detail) {
    // A BARE resource event is not a panel error: a favicon or stylesheet that
    // 404s fires `error` with no message, no position and no stack, and reporting
    // it would put a fake `PAGE_ERROR` in every launch's log — which is how a
    // word that matters gets trained out of the next reader. Only a real script
    // error (message, position or stack) is reported.
    if (!detail.text || (detail.text === 'error' && !detail.source && !detail.stack)) return;
    try { post('page-error', detail); } catch (e) { /* nothing left to report with */ }
  }
  window.addEventListener('error', function (event) {
    reportPageError({
      text: String((event && (event.message || (event.error && event.error.message))) || 'error'),
      source: String((event && event.filename) || ''),
      line: Number((event && event.lineno) || 0),
      col: Number((event && event.colno) || 0),
      stack: String((event && event.error && event.error.stack) || '')
    });
  }, true);
  window.addEventListener('unhandledrejection', function (event) {
    var reason = event && event.reason;
    reportPageError({
      text: 'unhandledrejection: ' + String((reason && reason.message) || reason || ''),
      source: 'promise',
      line: 0,
      col: 0,
      stack: String((reason && reason.stack) || '')
    });
  });
})();
"""


#: O MEDIDOR DO ARRANQUE DA PAGINA (2026-11-03). Corre no MESMO mundo e no MESMO
#: instante que o resto do preload (antes do primeiro script da pagina), porque
#: a pergunta e' "quem segurou o parser 25 s" e um medidor que chega depois so'
#: ve o que aconteceu depois. Nao desenha, nao toca no DOM, nao muda nada: observa
#: longtasks e marcos e manda UMA linha pela ponte que a pagina ja' usa.
BOOT_PROFILE_JS = r"""
;(() => {
  if (window.__sottoBootProfile) { return; }
  window.__sottoBootProfile = true;

  try {
    const t0 = performance.now();
    const marks = [];
    const mark = (n) => { try { marks.push([n, Math.round(performance.now())]); } catch (e) {} };
    const long = [];
    try {
      new PerformanceObserver((list) => {
        for (const e of list.getEntries()) { long.push(Math.round(e.duration)); }
      }).observe({ entryTypes: ['longtask'] });
    } catch (e) {}
    document.addEventListener('DOMContentLoaded', () => mark('dom'), { once: true });
    window.__sottoBootSent = {};
    const send = (phase) => {
      // DUAS FASES, DUAS LINHAS (2026-11-04). A guarda era um booleano: a
      // primeira chamada (no inicio do documento, sem numero nenhum) fechava
      // a porta e a leitura RICA -- `firstPaint`, `dcl`, os recursos mais
      // lentos -- nunca saia. `marks=[["load",18]]` foi o que se leu.
      if (window.__sottoBootSent[phase]) { return; }
      window.__sottoBootSent[phase] = true;
      try {
        mark(phase);
        const nav = (performance.getEntriesByType('navigation') || [])[0] || {};
        const res = (performance.getEntriesByType('resource') || [])
          .map((r) => [String(r.name).split('/').pop().split('?')[0],
                       Math.round(r.duration), Math.round(r.responseEnd)])
          .sort((a, b) => b[1] - a[1]).slice(0, 10);
        const fp = (performance.getEntriesByName('first-paint') || [])[0] || {};
        const box = {
          phase: phase,
          marks: marks, longtasks: long.slice(0, 15),
          slowest: res,
          firstPaint: Math.round(fp.startTime || 0),
          domInteractive: Math.round(nav.domInteractive || 0),
          dcl: Math.round(nav.domContentLoadedEventEnd || 0),
          loadEvent: Math.round(nav.loadEventEnd || 0),
        };
        // O CANAL DESTA CASA, NAO O DO PYWEBVIEW (2026-11-04, MEDIDO).
        // `window.pywebview.api.dispatch` NAO EXISTE aqui: a ponte e'
        // `chrome.webview.postMessage` e o bootstrap ja' publica
        // `window.__sotto_emit` por cima dela. O medidor ficou 24 h a
        // recolher e a descartar o proprio resultado -- `PANEL_BOOT_PROFILE`
        // nao aparece UMA vez no log de 469 587 linhas. Um instrumento que
        // coleta e nao publica e' pior do que nenhum.
        const wire = window.__sotto_post;
        if (typeof wire === 'function') {
          wire('boot-profile', JSON.stringify(box));
          return;
        }
        const api = window.pywebview && window.pywebview.api;
        if (api && api.dispatch) {
          api.dispatch(JSON.stringify({ kind: 'boot-profile', payload: box }));
        } else {
          setTimeout(send, 250);
        }
      } catch (e) {}
    };
    // DUAS SAIDAS, DE PROPOSITO (2026-11-04): uma no instante em que este
    // script corre -- se o canal ainda nao abriu, o `post` do bootstrap
    // ENFILEIRA e o `pywebviewready` descarrega -- e outra no `load`. Se nem a
    // primeira nem a segunda chegam ao log, o medidor nao tem canal e nao
    // pode continuar a fingir que mede.
    try { send('early'); } catch (e) {}
    window.addEventListener('load', () => { try { send('load'); } catch (e) {} }, { once: true });
    setTimeout(() => { try { send('late'); } catch (e) {} }, 30000);
  } catch (e) {}
})();
"""

def sweep_stale_webview_profiles(min_age_s=5400.0):
    """Apaga os perfis WebView2 que as largadas MORTAS deixaram em `%TEMP%`.

    Medido 2026-11-03 nesta maquina: **centenas** de `%TEMP%\\tmp*\\EBWebView`
    (4-67 MB cada), de todos os arranques que foram mortos a meio. O pywebview
    so' apaga o seu diretorio temporario numa saida limpa (`clear_user_data`),
    e um kill nunca e' uma saida limpa. E' o espaco em disco desperdicado que o
    dono nomeou como inadmissivel.

    A IDADE E' A GUARDA: um perfil com menos de `min_age_s` pode ter dono vivo
    (uma sonda, uma lane), e apagar o perfil de um processo a correr parte-o.
    Devolve `(dirs, bytes)` para o registo.
    """
    import glob as _glob
    import shutil as _shutil
    now = time.time()
    dirs = 0
    freed = 0
    home = os.environ.get('TEMP') or os.environ.get('TMP') or ''
    if not home:
        return 0, 0
    for webview_dir in _glob.glob(os.path.join(home, 'tmp*', 'EBWebView')):
        try:
            if now - os.path.getmtime(webview_dir) < min_age_s:
                continue
            size = 0
            for root, _subdirs, files in os.walk(webview_dir):
                for name in files:
                    try:
                        size += os.path.getsize(os.path.join(root, name))
                    except OSError:
                        pass
            parent = os.path.dirname(webview_dir)
            _shutil.rmtree(parent, ignore_errors=True)
            if not os.path.exists(parent):
                dirs += 1
                freed += size
        except OSError:
            continue
    return dirs, freed

def _bootstrap_js():
    """BOOTSTRAP_JS + the deferred-asset loader, read from disk at import time.

    The loader is a SEPARATE FILE (app/panel/lazy-assets.js) so the panel's own
    directory stays the single source of truth for it and it can be linted and
    measured without editing this shell. It is appended, never inlined: the
    loader must run in the SAME world as the preload, before any page script.
    """
    try:
        with open(LAZY_LOADER_JS, 'r', encoding='utf-8') as fh:
            loader = fh.read()
    except OSError as exc:
        log(f'PANEL_LAZY_LOADER_READ_FAILED error={exc!r}')
        return BOOTSTRAP_JS
    return BOOTSTRAP_JS + "\n" + loader + "\n" + BOOT_PROFILE_JS


#: The `--dump-dom` probe. This is main.js:273-290 VERBATIM, so the two arms
#: print the same keys in the same order and the lines diff directly.
DUMP_DOM_PROBE = r"""
(() => {
  const sels = ['html', 'body', '#panel', '.panel__header', '.wordmark', '.captions', '#placeholder',
                '#caption-list', '.status', '.wordmark__name', '#clear-button', '#status',
                '.stripbar', '.captions__body'];
  const out = { viewport: [innerWidth, innerHeight],
                zoom: (window.devicePixelRatio || 1),
                body: [document.body.scrollWidth, document.body.scrollHeight],
                sheets: document.styleSheets.length, els: {},
                // WHICH SURFACE the document is actually wearing, and whether a
                // skin is still recorded on it. Both decide whether the strip
                // paints at all: `data-skin` is set by `skin-host.js` when a
                // skin mounts and removed only when it UNMOUNTS, so it survives
                // the shell's own surface switch - and a skin rule that is not
                // surface-scoped strips the strip's slab and hides its captions
                // while `#skin` is hidden there. Measured 2026-10-09 as a 100%
                // white strip; every DOMDump before this key printed "the DOM is
                // fine" while it was blank.
                surface: (document.body && document.body.dataset) ? (document.body.dataset.surface || null) : null,
                skin: !!(document.body && document.body.hasAttribute('data-skin')) };
  for (const s of sels) {
    const el = document.querySelector(s);
    if (!el) { out.els[s] = null; continue; }
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    out.els[s] = { rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
                   color: cs.color, display: cs.display, position: cs.position,
                   visibility: cs.visibility, opacity: cs.opacity,
                   // THE RENDER PROTECTION'S OWN EVIDENCE (owner, 2026-10-09).
                   // The window is WS_EX_LAYERED, so anything the page does not
                   // paint shows the compositor's default - WHITE. Every prior
                   // DOMDump reported only color/display/position, i.e. NOT the
                   // one property that decides whether the panel is white, and
                   // the owner was told the DOM was fine while he was looking at
                   // a blank slab. Additive on purpose: no key above was removed,
                   // so the two arms still diff on the keys they already shared.
                   bgc: cs.backgroundColor, bgi: cs.backgroundImage.slice(0, 160) };
  }
  /* THE CONTROL CLUSTER AGAINST THE PANEL'S OWN RIGHT EDGE. Added 2026-10-18.
   *
   * WHY IT IS HERE AND NOT IN A PROBE SCRIPT. Every measurement of "does the
   * header fit" taken outside this shell has been wrong on this box: headless
   * Edge clamps the layout viewport to 492px in BOTH --screenshot and --dump-dom
   * (measured 2026-10-18: `--headless=new` and `--headless=old` produce
   * BYTE-IDENTICAL 62 570-byte PNGs at `--window-size=380,900`, and the outline
   * probe reports `header r=478` in a 380-wide PNG, i.e. the 492 layout cropped
   * to 380). `shot.py`'s docstring claims --screenshot is exempt; on this
   * machine it is not. Only the WebView2 window the shell actually creates has
   * the owner's 380px, and this is the only place that asks.
   *
   * WHAT IT ANSWERS. One number per control: how far its RIGHT edge is past the
   * panel's right edge. `.panel__controls` is `flex: 0 1 auto` and the cluster
   * is 250px of six fixed-width buttons inside a 352px header row, so whether
   * the last ones are reachable is a fact, not a style opinion -- and on
   * 2026-10-18 the answer was that Hide, Pause and the caption-size button were
   * past the edge, which is three controls the owner cannot click.
   *
   * ADDITIVE, like `bgc` above: no key above is removed, so the two arms still
   * diff on the keys they already shared. */
  out.controls = (function () {
    const panel = document.querySelector('main.panel');
    const right = panel ? panel.getBoundingClientRect().right : innerWidth;
    const ctl = document.querySelector('.panel__controls');
    const list = [];
    const btns = document.querySelectorAll('.panel__controls button');
    for (let i = 0; i < btns.length; i += 1) {
      const b = btns[i];
      const r = b.getBoundingClientRect();
      const cs = getComputedStyle(b);
      list.push({ id: b.id || null,
                  left: Math.round(r.left), right: Math.round(r.right),
                  w: Math.round(r.width),
                  past_by: Math.round(Math.max(0, r.right - right)),
                  onscreen: r.right <= right + 0.5 && r.left >= -0.5,
                  display: cs.display, visibility: cs.visibility });
    }
    return { panel_right: Math.round(right), viewport_w: innerWidth,
             cluster: ctl ? (function () {
               const r = ctl.getBoundingClientRect();
               const cs = getComputedStyle(ctl);
               return { left: Math.round(r.left), right: Math.round(r.right),
                        w: Math.round(r.width), computed_w: cs.width,
                        flex: cs.flex, min_width: cs.minWidth,
                        justify_self: cs.justifySelf };
             })() : null,
             buttons: list };
  })();
  return out;
})()
"""

#: The assertion that the bridge really was installed before panel.js ran.
#: panel.js:34 writes this exact sentence when `window.sotto` is undefined, so
#: its ABSENCE is a positive receipt that no injection race was lost.
BRIDGE_PROBE = r"""
(() => {
  const missing = document.body.textContent.indexOf('Preload bridge missing') >= 0;
  return {
    hasSotto: typeof window.sotto === 'object' && window.sotto !== null,
    // Which document is this, really? A probe that reports "the bridge is
    // there" while measuring a page with no `#panel` in it is a probe lying by
    // omission, so the document's own identity travels with the verdict.
    url: location.href,
    title: document.title,
    readyState: document.readyState,
    hasPanelElement: !!document.getElementById('panel'),
    // `setStripOffset` is in the list because the page's drag probes for it with
    // `typeof bridge.setStripOffset === 'function'` and SILENTLY skips the shell
    // half when it is absent (panel.html:1126). A probe that does not name the
    // method cannot report it missing, so the count is the live receipt.
    methods: ['pushCaption', 'setStatus', 'onCaption', 'onExternalCaption', 'onStatus', 'onGeometry',
              'hide', 'toggle', 'quit', 'setPointerInteractive', 'getInfo',
              'captionApplied', 'statusApplied', 'ready', 'clearApplied',
              'setStripOffset', 'beginWindowDrag', 'setLiveEnabled', 'pause']
              .filter((m) => typeof window.sotto[m] === 'function'),
    hotkey: window.sotto ? window.sotto.HOTKEY : null,
    platform: window.sotto ? window.sotto.platform : null,
    panelSaidBridgeMissing: missing,
    statusText: (document.getElementById('status-text') || {}).textContent || '',

    // WHAT THE PANEL SHOWS, not what the shell intended to send it. The
    // `statusText` above is the footer line; the two class flags are how the
    // panel paints severity (`status--error` is the red one), and the
    // placeholder block is the headline the owner reads before any caption
    // exists. A dump that carries only the text cannot tell "the panel showed
    // a dead worker" from "the panel showed the word `done` in a neutral
    // colour", which is a distinction this shell has already been wrong about.
    status: (() => {
      const s = document.getElementById('status');
      return { text: (document.getElementById('status-text') || {}).textContent || '',
               // THE WORKER'S OWN CAUSE (owner, 2026-10-21). The panel shows only
               // `ready` / `not ready`; the cause moved into the 3-dot menu
               // (`#panel-menu-cause`, mirrored on `documentElement.dataset.workerCause`).
               // A dump that reads only `text` above can no longer see the device,
               // so the cause is published HERE too.
               cause: (document.getElementById('panel-menu-cause') || {}).textContent
                      || (document.documentElement.dataset ? document.documentElement.dataset.workerCause : '')
                      || '',
               className: s ? String(s.className) : null,
               error: !!(s && s.classList.contains('status--error')),
               live: !!(s && s.classList.contains('status--live')),
               noAudio: !!(s && s.classList.contains('status--noaudio')) };
    })(),
    placeholder: (() => {
      const ph = document.getElementById('placeholder');
      const t = document.querySelector('.captions__placeholder-title');
      const b = document.querySelector('.captions__placeholder-body');
      return { hidden: ph ? !!ph.hidden : null,
               warming: !!(ph && ph.classList.contains('captions__placeholder--warming')),
               title: (t || {}).textContent || '',
               body: (b || {}).textContent || '' };
    })(),
    captions: (() => {
      const l = document.getElementById('caption-list');
      return { count: l ? l.childElementCount : -1, hidden: l ? !!l.hidden : null };
    })()
  };
})()
"""

#: The v2 acceptance probes. `exec_js` here does NOT await a returned Promise
#: (measured 2026-10-06: an async IIFE came back as `{}`), so the probe is split
#: into three SYNCHRONOUS reads that the shell sequences with real waits. The
#: waits are the point: the caption has to survive the formulation hold
#: (COMMIT_MAX_HOLD_MS = 1500 ms) before it commits and is written, and the
#: search is a bridge round-trip. `__STAMP__` is replaced by the shell with a
#: unique token, so the caption, its history line and the search that finds it
#: are tied together by one string instead of by timing luck.
PANEL_V2_INJECT = r"""
(() => {
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  const history = document.getElementById('history');
  const captions = document.getElementById('captions');
  const out = {
    url: location.href,
    shape: {
      history: !!history,
      live: !!captions,
      liveBox: !!document.getElementById('captions-body'),
      liveList: !!document.getElementById('caption-list'),
      // LIVE comes FIRST and the transcript drawer follows it (the live box is
      // the product and takes the space; see `panel.html`'s own comment on the
      // section order). This arm used to assert the OPPOSITE — `historyAboveLive`
      // — and the panel reorder of 2026-10-07 (F2/D1: a transcript that cannot
      // fill is collapsed UNDER the captions) would have made a stale arm RED
      // for the right change. `captions` precedes `history`, so history FOLLOWS.
      liveAboveHistory: !!(history && captions &&
        (captions.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING)),
    },
    buttons: {
      // A CAIXA DE BUSCA NAO EXISTE MAIS: o dono pediu-a fora em 2026-10-21 21:24
      // (*"tira a caixa de procurar texto"*) e ela saiu do markup em 2026-10-30. As
      // duas bandeiras passam a ser a AUSENCIA, e o veredicto abaixo exige-a -- uma
      // sonda que continuasse a exigir o formulario estaria a pedir de volta o que
      // ele recusou.
      search: !!document.getElementById('search-button'),
      searchInput: !!document.getElementById('search-input'),
      reveal: !!document.getElementById('reveal-button'),
      revealLabel: txt(document.getElementById('reveal-button')).trim(),
    },
    historyApi: !!(window.sotto && window.sotto.history &&
      typeof window.sotto.history.tail === 'function' &&
      typeof window.sotto.history.search === 'function' &&
      typeof window.sotto.history.reveal === 'function'),
  };
  return out;
})()
"""

PANEL_V2_READ_LIVE = r"""
(() => {
  const qa = (s) => Array.from(document.querySelectorAll(s));
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  // O CAMPO SAIU (2026-10-30). A leitura continua a correr e a devolver a mesma
  // forma: `searchInputDisabled` passa a ser lido como "nao ha campo nenhum", que e'
  // o estado que o dono pediu -- e um `requestSubmit` de um formulario ausente
  // rebentava a sonda inteira (medido: `TypeError: input is null`).
  const input = document.getElementById('search-input');
  const form = document.getElementById('search-form');
  if (input && form) {
    input.value = '__STAMP__';
    form.requestSubmit();
  }
  return {
    live: {
      lines: qa('#caption-list .caption__text').map((e) => e.textContent),
      count: (document.getElementById('caption-list') || {}).childElementCount,
      placeholderHidden: !!(document.getElementById('placeholder') || {}).hidden,
      // The panel DISABLES the search input while no canonical producer exists
      // (nothing could match, and a search box that cannot work is a promise
      // with no backend). Read here so the transcript arm below can require the
      // honest state instead of inventing a hit.
      searchBoxAbsent: !document.getElementById('search-input'),
      searchInputDisabled: !!(document.getElementById('search-input') || {}).disabled,
    },
    feed: qa('#history-list .hist__text').map((e) => e.textContent),
    feedFolderButtons: qa('#history-list .hist__folder').length,
    rootLabel: txt(document.getElementById('history-root')).trim(),
    searched: true,
  };
})()
"""

PANEL_V2_READ_SEARCH = r"""
(() => {
  const q = (s) => document.querySelector(s);
  const qa = (s) => Array.from(document.querySelectorAll(s));
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  return {
    search: {
      hits: qa('#history-list .hist').length,
      texts: qa('#history-list .hist__text').map((e) => e.textContent),
      marked: !!q('#history-list mark'),
      note: txt(document.getElementById('history-status')).trim(),
      folderButtons: qa('#history-list .hist__folder').length,
    },
  };
})()
"""

#: The panel's LIVE box and footer, read back as TEXT — the read a screenshot
#: makes, in text. It reports each line's own state (provisional vs committed),
#: which is the one thing the shell cannot know from the IPC receipts alone: a
#: provisional line is rewritten in place by `panel.js` and never leaves the DOM.
PANEL_STATE_PROBE = r"""
(() => {
  const txt = (el) => (el && el.textContent ? el.textContent : '');
  const list = document.getElementById('caption-list');
  const status = document.getElementById('status');
  const lines = list ? Array.from(list.children).map((li) => {
    const body = li.querySelector('.caption__text');
    return {
      text: body ? body.textContent : txt(li),
      provisional: li.classList.contains('caption--provisional'),
      latest: li.classList.contains('caption--latest'),
    };
  }) : null;
  const ph = document.getElementById('placeholder');
  const pt = document.querySelector('.captions__placeholder-title');
  const pb = document.querySelector('.captions__placeholder-body');
  return {
    url: location.href,
    live: {
      count: list ? list.childElementCount : -1,
      lines: lines,
      provisionalCount: lines
        ? lines.filter((line) => line.provisional).length : -1,
      hint: txt(document.getElementById('captions-hint')).trim(),
      hidden: list ? !!list.hidden : null,
      // THE FOLLOW, AS THREE NUMBERS. The owner's report was *"a transcricao nao
      // ta dando auto scroll no painel"* and no existing field could confirm or
      // refute it: `count` says how many lines exist, not whether the newest one
      // is on screen. `atBottom` is the exact predicate the panel's own follow
      // rule uses, read from the element that actually scrolls
      // (`#captions-body`, whose CSS is `overflow-y: auto`).
      scroll: (() => {
        const box = document.getElementById('captions-body');
        if (!box) return null;
        const scrollTop = box.scrollTop;
        const scrollHeight = box.scrollHeight;
        const clientHeight = box.clientHeight;
        return {
          top: scrollTop,
          height: scrollHeight,
          client: clientHeight,
          atBottom: (scrollHeight - scrollTop - clientHeight) < 48,
          overflowing: scrollHeight > clientHeight + 4,
        };
      })(),
    },
    status: {
      text: txt(document.getElementById('status-text')).trim(),
      kind: status
        ? (status.classList.contains('status--error') ? 'error'
          : status.classList.contains('status--live') ? 'live' : 'busy')
        : null,
    },
    placeholder: {
      hidden: ph ? !!ph.hidden : null,
      title: txt(pt).trim(),
      body: txt(pb).trim(),
    },
  };
})()
"""


class PanelVisibilityWriter:
    """Publish "is the panel on screen" to a file, on every transition AND on a
    cadence. The worker polls it; nothing else consumes it.

    THE CONTRACT (frozen shape — the worker's reader is built against it):

        {
          "schema": "sotto.panel-visibility/1",
          "visible": <bool>,        # window_visible(hwnd), MEASURED
          "since_ms": <int>,        # epoch ms at which THIS state began
          "age_ms": <int>,          # ms this state had lasted AT WRITE (0.0-style
                                    # "age at write": the authoritative duration is
                                    # `now_ms - since_ms`, computed by the READER)
          "pid": <int>,             # the SHELL's pid — the producer
          "reason": "<str>",        # the transition that opened this state
          "transitions": <int>,     # counted, so "it switched" is a number
          "writtenAt": "<iso>",
          "writtenAtEpoch": <float>,
          "staleAfterSeconds": <float>
        }

    WHY BOTH `since_ms` AND `age_ms`. The worker's question is "hidden for longer
    than N seconds". `since_ms` answers it absolutely and survives a reader that
    samples late; `age_ms` is the same fact as of the write and is what a human
    reading the file wants. A single field would have to be one of the two, and
    every reader downstream would have to guess which — the ambiguity that made a
    previous generation of this repo's probes disagree with each other.

    WHY A THREAD. The transition writes come from the UI thread (`show_panel`/
    `hide_panel`) and MUST NOT wait on a file. The cadence write runs here, every
    `interval_s`, re-reading the live window: that is what turns a map/unmap that
    happened WITHOUT going through `show_panel`/`hide_panel` — pywebview's own
    navigation-time `Show`, `_reassert_hidden`, a hot reload — into a recorded
    transition instead of a silent divergence between the file and the screen.
    """

    def __init__(self, path, observe, log=lambda _m: None,
                 interval_s=PANEL_VISIBILITY_INTERVAL_S, extra=None,
                 shed_provider=None, park_provider=None):
        self.path = path
        #: `observe()` -> bool, read LIVE from the window at call time.
        self.observe = observe
        self.log = log
        self.interval_s = max(0.5, float(interval_s))
        #: `extra()` -> dict merged into every payload. It carries the `geometry`
        #: key the EDIT mode persists (see `SottoShell.geometry_snapshot`). Kept
        #: a callback rather than a dict so the file always names the rect the
        #: window has AT THE WRITE, not the one it had when this object was built.
        self.extra = extra
        #: `shed_provider()` -> the shed level (`leve`/`alta`/`muito-alta`), or
        #: None. Callback for the same reason as `extra`: the level CHANGES at
        #: runtime and the file must name the level at the write.
        self.shed_provider = shed_provider
        #: `park_provider()` -> o motivo do ESTACIONAMENTO DO MOTOR
        #: (`captions`/`vram`) ou None. ORDEM DO DONO, 2026-11-03, verbatim:
        #: *"tu nao consegue fazer o sotto se conectar ao audio atual inves de
        #: ficar matando o audio toda hora?"* -- estacionar o worker por causa
        #: das legendas do player MATAVA o processo, e com ele o cliente
        #: WASAPI, e o audio dele piscava. Agora o pedido viaja por este
        #: ficheiro e o worker LARGA O MOTOR, nao a captura: um processo, um
        #: cliente de audio, nenhum blink.
        self.park_provider = park_provider
        self.visible = None
        self.since_ms = None
        self.reason = 'boot'
        self.transitions = 0
        self.writes = 0
        self.errors = 0
        self._stop = threading.Event()
        self._thread = None

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> bool:
        if self._thread is not None:
            return False
        # Order matters for a reader grepping this log: the ANNOUNCEMENT (which
        # names the path a reader must open) comes first, then the boot dump —
        # the same order `PanelStateWriter.start()` uses. The thread is started
        # LAST so the boot dump is deterministically the first write and the first
        # transition line carries `reason=boot` rather than a cadence tick's
        # `poll`.
        self.log(f'PANEL_VISIBILITY_WRITER path={self.path} '
                 f'interval_s={self.interval_s}')
        self.write('boot')
        self._thread = threading.Thread(target=self._loop,
                                        name='sotto-panel-visibility',
                                        daemon=True)
        self._thread.start()
        return True

    def stop(self, reason='stop') -> None:
        self._stop.set()
        self.log(f'PANEL_VISIBILITY_WRITER_STOP reason={reason} '
                 f'writes={self.writes} transitions={self.transitions} '
                 f'errors={self.errors}')

    def _loop(self) -> None:
        while False:
            # Reason `poll`: this state was reached without a show/hide call, or
            # the call's write already happened and this is the same state — the
            # writer only logs a transition when the VALUE moved, so a steady
            # panel produces no transition lines at all.
            self.write('poll')

    # -- one publication ---------------------------------------------------
    def write(self, reason='poll', visible=None) -> bool:
        observed = bool(self.observe()) if visible is None else bool(visible)
        now_ms = int(time.time() * 1000)
        if self.visible is None:
            # The FIRST write is a transition: the state the panel came up in is
            # a fact worth exactly one line, and it is the one a reader needs to
            # know how long the run has been in it.
            self.visible = observed
            self.since_ms = now_ms
            self.reason = reason
            self.transitions += 1
            self._log_transition(reason)
        elif observed != self.visible:
            self.visible = observed
            self.since_ms = now_ms
            self.reason = reason
            self.transitions += 1
            self._log_transition(reason)
        payload = {
            'schema': PANEL_VISIBILITY_SCHEMA,
            'visible': self.visible,
            'since_ms': self.since_ms,
            'age_ms': now_ms - self.since_ms,
            'pid': os.getpid(),
            'reason': self.reason,
            'transitions': self.transitions,
            'writtenAt': panel_state.now_iso(),
            'writtenAtEpoch': round(time.time(), 3),
            'ageSecondsNote': (
                'age_ms is the age AT WRITE; the authoritative duration is '
                '(now_ms - since_ms) and is computed by the READER'),
            'staleAfterSeconds': round(max(self.interval_s * 3.0, 5.0), 2),
        }
        # THE SHEDDING LEVEL TRAVELS IN THIS FILE (ordem do dono, 2026-10-30:
        # *"alta: desliga nemotron, so parakeet; muito alta: desliga parakeet
        # tambem"*). This is ADDITIVE on the same frozen shape -- no field renamed,
        # no field removed -- and it is the channel that made the owner's order
        # possible at all: the worker ALREADY polls this file, so the shell needs
        # no new IPC to say "stop the live engine and keep the batch one".
        # A provider that raises publishes NOTHING (the worker's reader then
        # falls back to `leve`), because a level invented by the shell would
        # silence a transcriber on a machine that is fine.
        try:
            level = self.shed_provider() if self.shed_provider is not None else None
        except Exception as exc:  # noqa: BLE001 -- the file must still land
            level = None
            self.log('PANEL_VISIBILITY_SHED_FAILED error=%r' % (exc,))
        if isinstance(level, str) and level:
            payload['shed'] = level
        # O ESTACIONAMENTO DO MOTOR TAMBEM VIAJA AQUI (2026-11-03). Additive no
        # mesmo contrato congelado: o leitor do worker ignora chaves que nao
        # conhece, e esta e' o pedido que substitui o `bridge.stop()`.
        try:
            park = self.park_provider() if self.park_provider is not None else None
        except Exception as exc:  # noqa: BLE001 -- the file must still land
            park = None
            self.log('PANEL_VISIBILITY_PARK_FAILED error=%r' % (exc,))
        if isinstance(park, str) and park:
            payload['park'] = park
        # THE `geometry` KEY — additive, and it is why the edit mode does NOT get
        # a second file. `schema` stays `sotto.panel-visibility/1`: no field was
        # renamed or removed, and the worker's `PanelVisibilityReader` reads
        # `visible`/`writtenAtEpoch`/`staleAfterSeconds` and ignores every other
        # key (read, not assumed), so an extra key cannot change what the worker
        # does. A SECOND file could: the shell would write one and the worker's
        # poll would read the other, and nothing would say which was authoritative.
        if self.extra is not None:
            try:
                extra = self.extra()
            except Exception as exc:  # noqa: BLE001 -- the file must still land
                extra = None
                self.log(f'PANEL_VISIBILITY_EXTRA_FAILED error={exc!r}')
            if isinstance(extra, dict):
                payload['geometry'] = extra
        try:
            panel_state.write_atomic(self.path, payload)
        except Exception as exc:
            self.errors += 1
            # RATE LIMITED, AND IT IS THE FLOOD FIX. MEASURED 2026-10-13: this single
            # line fired **1 145 063 times** -- 197.7 MB of an 808.6 MB log, 62-83% of
            # the failures inside the surface loop and only 1-2 an hour outside it.
            # The COUNT was already kept in `self.errors`; what was unbounded was the
            # LOGGING. The first few are logged in full because they are the ones that
            # diagnose a cold start, and after that one line per 500 carries the running
            # total -- so a reader still sees that it is failing, and how often, without
            # the file growing by a megabyte a minute to say so.
            if self.errors <= 3 or self.errors % 500 == 0:
                self.log(f'PANEL_VISIBILITY_WRITE_FAILED path={self.path} '
                         f'errors={self.errors} error={exc!r}')
            return False
        self.writes += 1
        return True

    def _log_transition(self, reason) -> None:
        # ONE line per transition, in the shape a reader greps for. `reason` is
        # the CALLER's word (`hotkey`, `--show`, `hot-reload`, `navigation`,
        # `page`, `boot`) or `poll` when the window moved without a call — a
        # distinction that matters: `poll` means the file is the ONLY record the
        # transition happened, which is precisely when a silent divergence
        # would otherwise go unnoticed.
        self.log(f'PANEL_VISIBILITY_MODE '
                 f'visible={str(bool(self.visible)).lower()} reason={reason} '
                 f'transitions={self.transitions} since_ms={self.since_ms}')


class SottoHost:
    """The Python side of `window.sotto` — the js_api pywebview exposes.

    ONE public method, `dispatch`, carries every page->host message. That is
    deliberate: `chrome.webview.postMessage` is available from document start
    (pywebview's own `window.pywebview.api` is NOT — it only exists after the
    page finishes loading), and speaking pywebview's own wire format means the
    host reuses pywebview's WebMessage pump instead of racing a second handler
    onto the same event.
    """

    def __init__(self, shell):
        # PRIVATE on purpose. pywebview walks every public attribute of the
        # js_api (util.py:190-206) and recurses into objects that are not
        # callable, so a public `self.shell` sends it from SottoHost into
        # SottoShell into the pywebview Window into the WinForms Form and from
        # there into the whole .NET object graph — measured as
        # `maximum recursion depth exceeded while calling a Python object` on
        # `shell.form.Controls.Owner.DefaultFont.FontFamily...`. An attribute
        # whose name starts with `_` is skipped before it is even read.
        self._shell = shell

    def dispatch(self, wire):
        """`wire` is the JSON string the page sent as the pywebview func_param."""
        try:
            message = json.loads(wire)
        except (TypeError, ValueError) as exc:
            log(f'BRIDGE_BAD_MESSAGE error={exc!r}')
            return
        if not isinstance(message, dict):
            log(f'BRIDGE_BAD_MESSAGE shape={type(message).__name__}')
            return

        kind = message.get('kind')
        payload = message.get('payload')
        # UM KIND MAU CUSTA SO' O PROPRIO KIND. Medido 2026-10-13: o mapa era um dict
        # literal, e um valor que levantava (`self._set_strip_offset`, metodo da shell e nao
        # do host) matava o `.get(kind)` de TODOS os kinds -- canal pagina->shell morto 2,5 h,
        # invisivel porque a excepcao ia para o logger do pywebview. A TABELA PASSOU A
        # GUARDAR NOMES: `_resolve_handler_map` resolve um a um com `getattr` e um que nao
        # resolve e' SALTA e DIZ-SE (`BRIDGE_HANDLER_MAP_FAILED kind=... name=... error=...`),
        # e o kind cai em `BRIDGE_UNKNOWN_KIND` uma linha depois. As entradas que nao podem
        # ser nome desta classe -- `hide`, `toggle`, `quit` chamam `self._shell.<m>('page')`
        # e deitam fora o payload -- levam `('shell-call', method, reason)`; os dois
        # `setStripOffset` levam `('shell', method)`. O `try/except` abaixo e' a REDE DE ULTIMO
        # RECURSO, nao a cura: a isolacao por kind e' o laco, e a arm do portao prova-o.
        try:
            table = {
            'caption-observed': ('host', '_caption_observed'),
            'status-observed': ('host', '_status_observed'),
            'caption-applied': ('host', '_caption_applied'),
            'status-applied': ('host', '_status_applied'),
            'caption-cleared': ('host', '_caption_cleared'),
            # THE DESIGN THE PANEL IS WEARING, pushed by `brand-bridge.js` the
            # moment the theme (or the caption scale, or a webfont) changes.
            # WITHOUT THIS ENTRY the panel re-skins and the overlay keeps the
            # default Segoe UI caption: two products on one screen.
            'brand-tokens': ('host', '_brand_tokens'),
            'boot-profile': ('host', '_boot_profile'),
            'renderer-ready': ('host', '_renderer_ready'),
            'page-error': ('host', '_page_error'),
            'pointer': ('host', '_pointer'),
            'transparency': ('host', '_transparency'),
            'sotto:transparency': ('host', '_transparency'),
            # The owner's strip drag (panel.html:1087). Without this entry the
            # page's `bridge.setStripOffset(...)` is `undefined`, the typeof probe
            # skips it, and the bar can only ever move INSIDE the window -- which
            # after the content-width fix is exactly the pill, so it cannot move
            # at all. The shell half is what puts it on the screen.
            # THE RECEIVER IS THE SHELL, AND GETTING IT WRONG KILLED EVERY
            # MESSAGE OF EVERY KIND. MEASURED 2026-10-13: this entry read
            # `self._set_strip_offset`, which is a SottoShell method (:7005) and
            # NOT a member of this class -- and a dict LITERAL evaluates every
            # value, so the AttributeError fired while BUILDING the map, before
            # `.get(kind)` ran. `SottoHost.dispatch` therefore died for EVERY
            # page->shell message: the deferred-asset ask (PANEL_LAZY_ALLOW 0),
            # panel.js's `ready()` (RECEIVER_READY 0, 298 of them in the log all
            # from BEFORE the commit that introduced this line) and every probe
            # kind. It surfaced ONLY in pywebview's own logger (`[pywebview]
            # Traceback ... AttributeError: 'SottoHost' object has no attribute
            # '_set_strip_offset'`, 35 of them in one 16 s probe arm) -- the
            # shell's own log stayed silent and looked healthy. Introduced by
            # 7fcd97e (2026-10-12 22:26); the last RECEIVER_READY on disk is
            # 2026-10-12 22:12:54. It is a ('shell', ...) entry for that reason:
            # the name is resolved against `self._shell`, and if it ever stops
            # resolving, THESE two kinds die and say so BY NAME.
            'setStripOffset': ('shell', '_set_strip_offset'),
            'sotto:setStripOffset': ('shell', '_set_strip_offset'),
            # THE NATIVE DRAG (2026-10-17). The page sends ONE of these per
            # gesture; the shell blocks in Windows' move loop and persists the
            # result. Entry shape is a name on the SHELL, like the one above.
            'beginWindowDrag': ('shell', '_begin_window_drag'),
            'sotto:beginWindowDrag': ('shell', '_begin_window_drag'),
            # THE LIVE PILL's own switch. The page's `applyLiveEnabled` probes
            # for `bridge.setLiveEnabled` to decide whether the control is real;
            # before this entry it was not, so the button said so in its title.
            'setLiveEnabled': ('shell', '_set_live_enabled'),
            'sotto:setLiveEnabled': ('shell', '_set_live_enabled'),
            # THE TRANSLATION TARGET (owner, 2026-10-21): the 3-dot menu's selector.
            'translation-target': ('host', '_translation_target'),
            # PAUSE = UNLOAD (2026-10-17). One entry, one method on the shell.
            'pause': ('shell', '_pause_shell'),
            'sotto:pause': ('shell', '_pause_shell'),
            'history-append': ('host', '_history_append'),
            'history-tail': ('host', '_history_tail'),
            'history-search': ('host', '_history_search'),
            'history-root': ('host', '_history_root'),
            'history-reveal': ('host', '_history_reveal'),
            # These three were lambdas (`lambda p: self._shell.x('page')`). They
            # cannot be a name on this class, so they carry the method AND the
            # fixed reason: the page's payload is dropped, exactly as the lambda
            # dropped it, and the shell method is resolved HERE -- so a missing
            # one is a named, isolated entry instead of a call-time surprise.
            'hide': ('shell-call', 'hide_panel', 'page'),
            'toggle': ('shell-call', 'toggle_panel', 'page'),
            'quit': ('shell-call', 'quit', 'page'),
            # The panel's repair control (panel.js:2045). Without this entry
            # the page's post('revive', ...) landed in BRIDGE_UNKNOWN_KIND and
            # the click died there.
            'revive': ('host', '_revive'),
            'info': ('host', '_info'),
            'panel-surface': ('host', '_panel_surface'),
            # The pull half of the stats channel: without this entry the
            # page's `post('stats', ...)` lands in BRIDGE_UNKNOWN_KIND and the
            # Promise never resolves.
            'stats': ('host', '_stats'),
            # The deferred-asset loader's only channel: it asks for the real
            # bytes of one deferred URL, and the shell lets that one through.
            'lazy-asset': ('host', '_lazy_asset'),
            }
        except Exception as exc:  # noqa: BLE001 -- a map that cannot build
            log(f'BRIDGE_HANDLER_MAP_FAILED error={exc!r} -- EVERY page->shell '
                'message is dead until this is fixed')
            table = {}
        handler = self._resolve_handler_map(table).get(kind)
        if handler is None:
            log(f'BRIDGE_UNKNOWN_KIND kind={kind!r}')
            return
        try:
            handler(payload)
        except Exception as exc:  # a page callback must not kill the host
            log(f'BRIDGE_HANDLER_FAILED kind={kind} error={exc!r}')

    def _resolve_handler_map(self, table):
        """Resolve the NAME -> NAME table, ONE ENTRY AT A TIME.

        THIS is the per-kind isolation. MEASURED 2026-10-13: the map was a dict
        literal of VALUES, so one entry naming a method this class does not have
        raised while the map was being BUILT and `dispatch` died for EVERY kind
        for two and a half hours. Each entry here gets its own try/except: the
        bad one is skipped, NAMES ITSELF in this shell's own log, and every
        other kind keeps dispatching.
        """
        resolved = {}
        for kind, spec in table.items():
            name = spec[1] if isinstance(spec, tuple) and len(spec) > 1 else spec
            try:
                resolved[kind] = self._resolve_handler(spec)
            except Exception as exc:  # noqa: BLE001 -- one dead kind, not all
                log(f'BRIDGE_HANDLER_MAP_FAILED kind={kind!r} name={name!r} '
                    f'error={exc!r} -- THIS kind is dead; every other kind is not')
        return resolved

    def _resolve_handler(self, spec):
        """ONE table entry -> callable: ('host'|'shell', name), or
        ('shell-call', name, fixed_reason) for the three that call the shell.

        The name is looked up with `getattr(..., None)` and the CALLABLE test is
        what refuses it, so a missing name raises HERE -- inside the caller's
        per-entry try/except -- and never escapes into `dispatch`'s map build.
        """
        where, name = spec[0], spec[1]
        if where == 'host':
            owner = self
        elif where in ('shell', 'shell-call'):
            owner = self._shell
        else:
            raise ValueError(f'unknown handler source {where!r}')
        target = getattr(owner, name, None)
        if not callable(target):
            raise AttributeError(f'{type(owner).__name__}.{name} is not callable')
        if where == 'shell-call':
            # The three that used to be `lambda p: self._shell.<method>('page')`:
            # the shell method takes the FIXED reason and the page's payload is
            # dropped, exactly as the lambda dropped it.
            reason = spec[2]
            return lambda payload, _target=target, _reason=reason: _target(_reason)
        return target

    # -- receipts ----------------------------------------------------------
    def _caption_observed(self, payload):
        self._shell.note_caption_observed(payload)

    def _status_observed(self, payload):
        self._shell.note_status_observed((payload or {}).get('text', ''))

    def _revive(self, payload):
        """The panel's repair control: kill the worker, respawn it.

        panel.js:2013 revivePipeline posts bridge.revive('panel-status')
        (:2045) and the SHELL does the killing and respawning (panel.js:1968).
        That shell half did not exist -- grep -n revive over app/webview/
        returned ZERO -- so reviveSupported() (:2007) was false on every launch
        and the panel's ONLY recovery from a stalled pipeline answered "This
        shell cannot restart the pipeline (no bridge.revive())". The decision
        lives in SottoShell.revive_worker; this is the transport.
        """
        self._shell.revive_worker((payload or {}).get('reason') or 'page')

    def _page_error(self, payload):
        """A THROW INSIDE THE PANEL, on the record.

        The panel's errors used to be unobservable from Python: `evaluate_js`
        reports the CALL, so a `TypeError` inside `panel.js` left the shell
        logging healthy `BRIDGE_CAPTION_SENT delivered=true` lines while the
        owner looked at a panel frozen on its placeholder. This is the channel
        that names it — with position and stack, because "the panel is broken" is
        not actionable and "panel.js:187 TypeError: bridge.onCaption is not a
        function" is. Kept at warning level: the app keeps running, but a page
        that threw is the reason nothing on screen is moving.
        """
        payload = payload or {}
        warn(f'PAGE_ERROR text={json.dumps(str(payload.get("text", "")))} '
             f'at={payload.get("source") or "?"}:{payload.get("line") or 0}:'
             f'{payload.get("col") or 0} '
             f'stack={json.dumps(str(payload.get("stack", ""))[:400])}')

    def _caption_applied(self, payload):
        text = (payload or {}).get('text', '')
        self._shell.caption_log.append(text)
        del self._shell.caption_log[:-MAX_CAPTIONS]
        # ── O PIXEL, COM A IDADE DO AUDIO (2026-11-03) ──────────────────────
        # O painel confirma que APLICOU a linha; este e' o instante do ecra
        # nesta maquina. A idade do audio sai daqui e nao do `tap_ms` da
        # chegada: entre os dois ha' a formulacao, a ponte e a pintura do DOM.
        shell = self._shell
        tap = getattr(shell, '_last_push_tap_ms', None)
        # O TAP E' DE UMA PINTURA SO' (2026-11-04). A `final` chega sem
        # `tap_ms` e herdava o da ultima parcial: medido `audio_ms=166615` num
        # audio de 3 s, `p90=45402`, `over=109` de 200.
        shell._last_push_tap_ms = None
        _is_final = bool(getattr(shell, '_last_push_final', False))
        sent_at = getattr(shell, '_last_push_at', None)
        audio_ms = (int(time.time() * 1000.0) - int(tap)) if tap else None
        queue_ms = int((time.time() - sent_at) * 1000) if sent_at else None
        # A LINHA FECHADA NAO ENTRA NA SERIE AO VIVO (2026-11-04): o `tap_ms` de
        # uma `final` e' o do INICIO dela, logo mede a DURACAO da frase.
        if audio_ms is not None and not _is_final:
            shell._caption_lag_note(
                audio_ms, queue_ms=queue_ms, kind='partial')
        log(f'CAPTION_APPLIED text={json.dumps(text)} '
            f'count={len(self._shell.caption_log)}'
            f' kind={"final" if _is_final else "partial"}'
            + (f' aged_kind=final-close' if _is_final
               else f' aged_kind={"hold-expired" if (queue_ms is not None and shell.CAPTION_HOLD_BAND_MS[0] <= int(queue_ms) <= shell.CAPTION_HOLD_BAND_MS[1]) else "transport"}'
               if audio_ms is not None else '')
            + (f' audio_ms={audio_ms} queue_ms={queue_ms}'
               f' budget_ms={shell.CAPTION_BUDGET_MS}'
               f' over={str(audio_ms > shell.CAPTION_BUDGET_MS).lower()}'
               if audio_ms is not None else ''))
        # A LINHA `final` NAO ESTOURA O ORCAMENTO (2026-11-04, MEDIDO).
        # `audio_ms` sai do `tap_ms` da linha, e uma linha fechada carrega o tap
        # do INICIO dela: medido `CAPTION_IN ... final=true ... age_ms=13494`
        # com `CAPTION_PAINT_LAG over=true blown=36` -- trinta e seis estouros
        # seguidos que eram a DURACAO da frase, nao atraso do ecra. O numero
        # continua no log (`aged_kind=final-close`), o veredicto nao o conta.
        if (audio_ms is not None and audio_ms > shell.CAPTION_BUDGET_MS
                and not getattr(shell, '_last_push_final', False)):
            log(f'CAPTION_BUDGET_BLOWN audio_ms={audio_ms} '
                f'budget_ms={shell.CAPTION_BUDGET_MS} '
                f'queue_ms={queue_ms} blown={shell._caption_lag_blown} '
                f'path=panel text={json.dumps(text[:60])}')

    def _status_applied(self, payload):
        # SO' NA MUDANCA (2026-11-04). O painel confirma o status a cada
        # repintura e a linha saia sempre: medido `STATUS_APPLIED` a cada 4 s no
        # log do dono (26 317 linhas). O que interessa e' "o painel aplicou ESTE
        # texto", e um texto igual ja' foi respondido. A primeira e a mudanca
        # saem; o silencio das outras prova que nada mudou.
        text = (payload or {}).get('text', '')
        if getattr(self, '_status_applied_last', None) == text:
            self._status_applied_quiet = getattr(
                self, '_status_applied_quiet', 0) + 1
            return
        quiet = getattr(self, '_status_applied_quiet', 0)
        self._status_applied_quiet = 0
        self._status_applied_last = text
        log(f'STATUS_APPLIED text={json.dumps(text)}'
            + (f' repetidas_silenciadas={quiet}' if quiet else ''))

    def _translation_target(self, payload):
        """The 3-dot menu's translation pick reached the shell. `lang == ''` clears it;
        a code is RECORDED and the policy decides -- since 2026-10-30
        `youtube_captions._target_langs` CLAMPS a pick that would translate an en/pt/es
        video, or another language into anything but English. The log says what was
        picked; the screen gets the rule. One fact, on that module.
        """
        code = str((payload or {}).get('lang') or '').strip().lower()
        try:
            import youtube_captions
            applied = youtube_captions.set_target_language(code)
        except Exception as exc:  # noqa: BLE001
            log(f'TRANSLATION_TARGET_FAILED code={json.dumps(code)} error={exc!r}')
            return
        log(f'TRANSLATION_TARGET code={json.dumps(code)} applied={json.dumps(applied)}')

    def _caption_cleared(self, payload):
        remaining = (payload or {}).get('remaining', 0)
        self._shell.caption_log.clear()
        log(f'CAPTIONS_CLEARED remaining={remaining}')

    def _brand_tokens(self, payload):
        """Wear the panel's measured design on the NATIVE overlay.

        The panel measures its own forming row and posts the resolved values
        (`brand-bridge.js`). This receiver keeps the LAST payload so an overlay
        created later than the first push -- the normal boot order -- still
        starts branded instead of defaulting to Segoe UI until the next theme
        change. A payload that is not a dict is treated as "no design", which
        restores the pre-brand overlay rather than raising.
        """
        theme = payload if isinstance(payload, dict) else {}
        self._brand_tokens_last = dict(theme)
        overlay = getattr(self, 'caption_overlay', None)
        if overlay is None:
            log('CAPTION_OVERLAY_THEME_DEFERRED reason=no-overlay '
                'theme=%r' % (theme.get('theme') or '-'))
            return
        # O DESIGN DO PAINEL NAO MANDA NA LEGENDA (ordem do dono, 2026-11-03,
        # verbatim: *"ESSE ESTILO DE LEGENDA E' DO YOUTUBE. NAO SOTTO."*). O
        # payload continua a ser GUARDADO (`_brand_tokens_last`) porque o painel
        # o usa; a janela da legenda veste SEMPRE o estilo do player, e o log diz
        # de onde veio a recusa para o desvio nao passar silencioso.
        try:
            import overlay_paint
            applied = overlay.set_theme(overlay_paint._THEME_DEFAULT)
        except Exception as exc:  # noqa: BLE001 -- a design must not kill captions
            log(f'CAPTION_OVERLAY_THEME_FAILED error={exc!r}')
            return
        log('CAPTION_OVERLAY_THEME_APPLIED theme=%s font=%s live=%.1f '
            'brand=%s plate=%s fade=%s'
            % (applied.get('theme') or '-', applied.get('fontFamily'),
               applied.get('livePx') or 0.0, theme.get('theme') or '-',
               'yes' if applied.get('plate') else 'no',
               'yes' if getattr(overlay, 'FADE_ON', False) else 'no'))

    def _boot_profile(self, payload):
        """ONDE OS 25 S DA PAGINA SAO GASTOS, medido DENTRO do renderer.

        Medido 2026-11-03: `WEBVIEW_NAV start` -> `WEBVIEW_NAV dom` = 25 s para
        uma pagina LOCAL de 700 KB, e o event `DOMContentLoaded` e' do proprio
        Chromium: alguem esta' segurando o parser. O `_bootstrap_js` instala um
        `PerformanceObserver` de longtask antes do primeiro byte de pagina e manda
        o resultado por `dispatch` no `load`; esta linha e' a unica saida dele.
        """
        payload = payload or {}
        try:
            log('PANEL_BOOT_PROFILE %s' % json.dumps(payload)[:1200])
            self._shell._panel_boot_profile = payload
        except Exception as exc:  # noqa: BLE001
            log('PANEL_BOOT_PROFILE_FAILED error=%r' % (exc,))

    def _renderer_ready(self, payload):
        payload = payload or {}
        placeholder = re.sub(r'\s+', ' ', str(payload.get('placeholder', ''))).strip()
        log(f'RECEIVER_READY captions={payload.get("captions", 0)} '
            f'hasBridge={bool(payload.get("hasBridge"))} '
            f'placeholder={json.dumps(placeholder[:80])}')
        self._shell.renderer_ready.set()

    def _pointer(self, payload):
        self._shell.set_pointer_interactive(bool((payload or {}).get('active')))

    def _transparency(self, payload):
        self._shell.set_transparency(bool((payload or {}).get('on')))

    def _info(self, payload):
        info_id = (payload or {}).get('id', '')
        self._shell.reply_info(info_id, self._shell.info())
    def _panel_surface(self, payload):
        """`bridge.setPanelSurface(surface, reason)` — the member this shell owed.

        (CHAMADORES: `panel.js:1239-1243` para abrir o painel cheio a partir do strip,
        E `caption-float.js:243` para o estado do overlay. A versao anterior deste
        docstring dizia que o `panel.js` era o UNICO, e era falso.)
        """
        # ESTE DOCSTRING ESTAVA VELHO e fica corrigido: ele diz que o `panel.js:1239-1243`
        # e o UNICO chamador, e `caption-float.js:243` tambem chama -- e chama com a razao
        # que interessa aqui.
        payload = payload or {}
        reason = payload.get('reason') or 'page'
        # A JANELA DA LEGENDA TEM UMA PORTA E SO UMA: `_set_live_enabled`, o botao LIVE.
        #
        # Aqui havia, ate 2026-10-17, uma SEGUNDA porta --
        # `if reason in ('float-on', 'float-off'): show_caption_window(...)` -- que
        # levantava a janela da legenda a partir de uma mudanca de SUPERFICIE. Ela
        # existia porque `caption-float.js:243` mandava `setPanelSurface('strip',
        # 'float-on')` ao proprio `setFloat`, e o objectivo pedia *"ligar/desligar
        # pelo botao live"*. As DUAS portas foram cortadas no mesmo dia, pelo
        # mesmo dono e a mesma medicao (a janela a crescer 40 -> 220 px num clique,
        # log de 2026-10-17). Hoje `grep -rn 'float-on' app/` so encontra isto e
        # comentarios: nenhuma linha viva manda a razao. Fica a porta unica, e uma
        # superficie ja nao decide se ha legenda no ecra -- o dono decide.
        self._shell.set_panel_surface(payload.get('surface'), reason)

    def _stats(self, payload):
        '''The panel's own `getStats()` pull, answered on the same id
        round-trip as `info` -- so the panel gets a resolved Promise rather
        than a synchronous guess, and the log can tell a PULL from a PUSH.
        '''
        stats_id = (payload or {}).get('id', '')
        self._shell.reply_stats(stats_id, self._shell.stats())

    def _lazy_asset(self, payload):
        """The deferred-asset loader's ask: let ONE URL reach the disk.

        lazy-assets.js calls this the moment it decides a theme needs a resource
        the shell is holding back. The gate is a SET, so a second ask for the same
        URL is a no-op and an ask for a URL outside LAZY_ASSETS is refused (the
        page cannot widen its own allowance). The reply is synchronous and carries
        no data: the page's own <script>/<link> element is what waits for the
        bytes, so there is nothing to return.
        """
        url = (payload or {}).get('url')
        # THE GATE LIVES ON THE SHELL, AND THE ASK WAS LOOKING FOR IT HERE.
        # MEASURED 2026-10-13 on a fixed channel: the ask ARRIVES (four
        # `PANEL_LAZY_ASK_REFUSED reason=no-gate` lines) and is refused because
        # `_lazy_gate` is set by `SottoShell._arm_lazy_gate` (:4462/:4465/:4473)
        # and never existed on `SottoHost` -- `getattr(self, ...)` here could
        # only ever return None. This is the SECOND defect on the same path: the
        # first (`'setStripOffset': self._set_strip_offset`, fixed the same day)
        # killed every page->shell message at the dispatch map, so this one was
        # unobservable -- `PANEL_LAZY_ASK_REFUSED` read 0, not because the ask was
        # refused, but because it never got this far.
        gate = getattr(self._shell, '_lazy_gate', None)
        if gate is None:
            log(f'PANEL_LAZY_ASK_REFUSED reason=no-gate url={url!r}')
            return
        if not gate.allow(url):
            log(f'PANEL_LAZY_ASK_REFUSED reason=not-deferred url={url!r}')

    # -- history (the "redux" store) ---------------------------------------
    def _history_reply(self, payload, result):
        history_id = (payload or {}).get('id', '')
        if history_id:
            self._shell.reply_history(history_id, result)

    def _history_append(self, payload):
        payload = payload or {}
        entry = self._shell.history_append(
            payload.get('text', ''), payload.get('meta'))
        self._history_reply(payload, {'entry': entry})

    def _history_tail(self, payload):
        payload = payload or {}
        self._history_reply(
            payload, self._shell.history_tail(int(payload.get('limit') or 400)))

    def _history_search(self, payload):
        payload = payload or {}
        self._history_reply(payload, self._shell.history_search(
            payload.get('query', ''), int(payload.get('limit') or 200)))

    def _history_root(self, payload):
        self._history_reply(payload or {}, self._shell.history_root())

    def _history_reveal(self, payload):
        self._shell.reveal_in_folder((payload or {}).get('path'))


# ===========================================================================
# the shell
# ===========================================================================


#: How many hits each layer may contribute, as a fraction of `limit`.
#:
#: NOT EQUAL ON PURPOSE, and the numbers come from a measurement rather than a taste.
#: On this box's own store -- 2 077 lines over 11 files -- the phonetic layer returns
#: 172 candidates for `maca`, 94 for `audio`, 72 for `preco`. That is not a bug in
#: Soundex; it is Soundex colliding with Portuguese: `maca`, `mais`, `faca` and `massa`
#: are all M200, and "mais" is the most common word in the language. The layer is
#: correct -- those words DO sound alike -- but a layer that can contribute 185 of a
#: 2077-line result is a layer that drowns the answer if it is given the same budget as
#: the literal one. So the loose layers get a fraction, and the fraction is the
#: product decision: literal answers the question, phonetic suggests, fuzzy stumbles.
SEARCH_LAYER_CAPS = (1.0, 0.25, 0.05)
#: A loose layer may never be floored into uselessness: below these, the fractions
#: above would return nothing and the layers would be dead code.
SEARCH_LAYER_MIN = (1, 8, 4)


def search_layer_cap(rank, limit):
    """The cap for layer `rank` at `limit`. Integer, never below `SEARCH_LAYER_MIN`.

    MODULE LEVEL, and that is load-bearing. An earlier draft of this session put it
    inside `class SottoShell`, immediately above `history_search`, and re-indented
    that method back to four spaces -- which made Python read it as a NESTED `def`
    inside `search_layer_cap`, so every remaining method of the class (`reply_history`
    through `_do_worker_restart`) silently became part of that one function body.
    The module still PARSED -- nothing about that is a syntax error -- and the shell
    died at startup with `AttributeError: 'SottoShell' object has no attribute
    '_do_worker_restart'`, which names a symptom four thousand lines away from the
    mistake. `_class-map.py` below is the instrument that found it: it reports each
    top-level node's line span, and `search_layer_cap 6461..9497` is not a span any
    author would have written.
    """
    fraction, floor = SEARCH_LAYER_CAPS[rank], SEARCH_LAYER_MIN[rank]
    return max(floor, int(math.floor(limit * fraction)))


class SottoShell:
    def __init__(self, args):
        self.args = args
        #: O `tap_ms` da ultima linha EMPURRADA (2026-11-03): o pixel do painel
        #: mede a idade do audio contra ele em `_caption_applied`.
        self._last_push_tap_ms = None
        self._last_push_at = 0.0
        #: A SERIE de idades do audio ate' ao pixel e o contador de estouros
        #: (2026-11-03). Criados AQUI e nao pregicadamente: medido no log dele
        #: (17:38:35) um `BRIDGE_HANDLER_FAILED kind=caption-applied`
        #: `AttributeError: _caption_lag_blown` -- o primeiro ack estourava o
        #: orcamento antes de a serie existir, e a excepcao comia a linha do log
        #: exactamente no caso que interessa.
        self._caption_ages = []
        self._caption_lag_blown = 0
        self.window = None            # pywebview Window
        self.form = None              # pywebview's WinForms BrowserForm
        self.webview2 = None          # the WebView2 control
        self.core = None              # CoreWebView2
        self.hwnd = None
        self.staged = False   # have we navigated from stage.html to the panel
        self.geometry = None
        self.display = None
        self.visible = False
        #: The owner explicitly paused and unloaded the engines. Opening the
        #: panel again must NOT silently reload them; the status click revives.
        self._paused = False
        # True once the "hide unless the owner asked" guard is subscribed to the
        # control's NavigationStarting. It is the precondition of the panel being
        # hidden at startup, and it is armed in `_on_before_show` — see
        # `_arm_visibility_invariant`.
        self.visibility_armed = False
        # True once pywebview's OWN mapping call (`form.Show()`) has been
        # refused at the form instance — see `_gate_form_show`. Counts the maps
        # refused, so "the gate is on the shipped path" is a number in the log
        # and not a claim.
        self.panel_show_refused = 0
        self.pointer_interactive = False
        self.transparent = False   # panel-requested click-through (captions stay)
        #: Where the panel lives when shown: 'strip' (bottom, the default) or
        #: 'side' (the right panel). THIS IS THE ONLY INPUT the Alt+C cycle needs
        #: besides whether the window is up: hidden -> strip -> side -> hidden.
        #: `_last_hotkey_press` used to live next to it, as the double-press
        #: stamp; it is deleted with the window it fed (owner, 2026-10-13).
        self.panel_mode = 'strip'
        self.caption_log = []
        #: The strip's height is the STYLESHEET's (`panel.css:52`
        #: `--strip-height: 150px`), read at runtime by
        #: `refresh_strip_height()`; `strip_height_css` is the last value read
        #: from the page and `strip_height_extra` the runtime addition on top of
        #: it. `strip_height` is the sum — what the window is actually sized to.
        #: Changed at runtime with `set_strip_height()`.
        self.strip_height_css = None
        self.strip_height_extra = 0
        self.strip_height = STRIP_HEIGHT_FALLBACK
        #: The strip's CONTENT width, measured in the page (the pill's own
        #: rendered box). `None` until read, and `None` on purpose while the
        #: caption is floated. See `strip_width_from_dom()` for the defect this
        #: exists to kill: `STRIP_WIDTH = 1040` fixed the WINDOW while the pill
        #: inside was `max-content`, and the form paints every pixel the page
        #: does not with opaque `#0B0F14` -- the owner's solid slab.
        self.strip_width_dom = None
        #: Where the strip was DOCKED before the owner dragged it, in DIP. The
        #: page reports a CUMULATIVE offset from the dock (panel.html:1083), so
        #: the shell needs the base it is cumulative FROM. Recorded on every
        #: strip application, never by the drag itself.
        self._strip_dock_base = None
        # ── THE TWO SURFACES (owner, 2026-10-08) ─────────────────────────────
        #: The surface the owner's control opens. `'strip'` — the SHORT caption
        #: band at the bottom, horizontally centred — because
        #: `app/panel/surface.js:6-8` records the decision that Alt+C must NOT
        #: open the whole 380x900 panel. `--show` is the exception: it is the
        #: developer's "panel up now" and stays the FULL panel, byte for byte.
        self.surface = 'strip'
        #: The surface the WINDOW currently wears. The window is CREATED at the
        #: docked-panel geometry (`create_window`), so this starts as `'panel'`
        #: and the first Alt+C is what moves it to the strip — while it is still
        #: hidden, which is the only moment a `SetWindowPos` cannot flicker.
        self.surface_applied = 'panel'
        #: The rect an EDIT session saved, read back from the `geometry` key of
        #: `_main/panel-visibility.json` at startup and re-written on every edit.
        #: `None` means "never edited" — the computed default stands.
        self.saved_geometry = None
        #: True while the owner is positioning the caption band (tray menu
        #: `Edit caption position`). See `set_edit_mode`.
        self.edit_mode = False
        self.edit_moves = 0
        #: The cursor's offset from the window origin, captured when the drag
        #: started, so the band follows the pointer instead of jumping to it.
        self.edit_grab = None
        self.last_status = ''
        self.bridge_installed = None  # None until measured, True/False after
        self.renderer_ready = threading.Event()
        self.exiting = threading.Event()
        self.bridge = None            # WorkerBridge
        #: The panel's repair control, in flight (revive_worker). A second
        #: click is refused while this is set: the ~0.5 s the dying child takes
        #: is exactly the window a double click lands in.
        self._revive_lock = threading.Lock()
        self._revive_thread = None
        # A file change in `worker/` does NOT restart the worker directly: it
        # is queued and the policy decides (debounce, mid-stream guard, 180 s
        # floor). See WorkerReloadPolicy and docs/audit/load-churn.md.
        self._reload_policy = WorkerReloadPolicy(
            log_fn=log,
            get_bridge=lambda: self.bridge,
            restart=self._do_worker_restart,
        )
        self.hotkey = None
        #: A segunda tecla global: a legenda ao vivo (Ctrl+Space por fabrica).
        #: Thread propria, fila propria -- ver `arm_hotkey`.
        self.live_hotkey = None
        self.tray = None
        self.click_watcher = None
        self.hot_reload = None       # hot_reload.HotReload
        #: THE PLAYER'S OWN CAPTIONS (2026-10-17): YouTube/Stremio already paint
        #: their subtitles, so the shell reads them through UI Automation. While
        #: this is true the ASR captions are suppressed and the worker is parked
        #: (its VRAM is not needed for captions that already exist).
        self.external_captions_active = False
        self.external_captions_available = False
        self.external_caption_watcher = None
        #: THE YOUTUBE REAL TRACK (2026-10-19). Its own thread, because
        #: `yt_dlp`'s metadata call took 5.0 s (MEASURED) and the caption
        #: reader polls every 0.30 s.
        self.youtube_track_thread = None
        self._external_parked = False
        self._vram_parked = False
        self.external_suppressed = 0
        self.external_lines = 0
        self._overlay_pushes = 0
        self.vram_guard = None
        #: The panel AS TEXT: the periodic dump writer (panel_state.py). None
        #: until the panel's first load, which is when the DOM can be read.
        self.panel_state = None
        #: THE VISIBILITY CHANNEL (PanelVisibilityWriter). Armed at the same
        #: moment as `panel_state` and BEFORE the worker can be spawned, because
        #: the worker's mode switch polls this file: a worker that starts while
        #: the file does not exist yet would read "unknown" and — by the
        #: fail-safe — stream, which is the correct default but is NOT the
        #: honest answer once the file exists.
        self.panel_visibility = None
        self.reload_count = 0        # how many panel re-navigations have run
        #: Counters for the stats channel: a reply is the panel's POLL being
        #: answered, a push is the worker's own counters being forwarded.
        self.stats_replies = 0
        self.stats_pushes = 0
        #: Log aggregation for the per-sample push: the LAST count that was
        #: logged and when. One line per `STATS_LOG_INTERVAL_S` at most, so a
        #: tens-of-Hz meter cannot grow the log without bound.
        self.stats_logged = 0
        self.stats_logged_at = 0.0
        #: THE WAVE's own push counter. `stats_pushes` counts the pushes driven by
        #: the worker's stderr `WORKER_STATS` line; this counts the pushes driven
        #: by its stdout `meter` events. Both travel in `SHELL_EXIT`, because the
        #: push LOG prints once per interval and could never prove a 10 Hz feed.
        self.meter_pushes = 0
        #: THE BOUND ON THE UI QUEUE. `emit_async` pushes a whole state per
        #: sample; without a pending latch the WinForms queue grew WITH THE FEED
        #: (43 pushes/s measured) and a page that could not drain it stalled the
        #: UI thread. One pending post per channel is that bound; the payload kept
        #: is the LATEST, which is all the panel reads (see `emit_async`).
        self._emit_lock = threading.Lock()
        self._emit_pending = {}
        # THE STATS-REPLY CHANNEL (2026-10-20): the ids waiting for the UI
        # thread, the ones pushed out of the way, and whether a post is
        # already pending. The REPLY is a POST -- see `reply_stats`.
        self._stats_reply_lock = threading.Lock()
        self._stats_reply_pending = []
        self._stats_reply_evicted = []
        self._stats_reply_posted = False
        self._stats_reply_payload = '""'
        # THE PANEL-STATE DOM READ (2026-10-20): the last value, its age, and
        # whether a newer read is on the way. AT MOST ONE read outstanding.
        self._panel_dom_lock = threading.Lock()
        self._panel_dom_value = None
        self._panel_dom_at = 0.0
        self._panel_dom_pending = False
        self._panel_dom_reason = ''
        self._panel_dom_detail = None
        self.startup_done = False    # startup actions run once per process
        self.startup_visible = None  # None until the window is measured
        self._exit_code = 0

    # -- geometry ----------------------------------------------------------
    def compute_geometry(self):
        self.display = primary_display()
        self.geometry = dock_right(self.display['workArea'])
        return self.geometry

    # -- window ------------------------------------------------------------
    def create_window(self):
        import webview  # imported late: it loads the WinForms assemblies

        geometry = self.compute_geometry()
        self.restore_saved_geometry()
        # Open on the staging page, not the panel. pywebview loads the URL from
        # its own CoreWebView2InitializationCompleted handler, which is
        # subscribed BEFORE the host's, so a preload registered from the host's
        # handler is registered after the panel's navigation is already in
        # flight — measured as `PRELOAD_ACTIVE hasSotto=false` on the first
        # parse. Staging buys one navigation of ordering so the panel's FIRST
        # parse already has the bridge. See stage.html.
        url = file_url(STAGE_HTML)

        log('panel window created frame=false transparent=' +
            str(not self.args.opaque).lower() +
            ' alwaysOnTop=true skipTaskbar=true resizable=false '
            'show=false focusable=false engine=WebView2/pywebview')
        log(f'panel geometry: {summary(geometry)}')
        log('primary display bounds=' + json.dumps(self.display['bounds']) +
            ' workArea=' + json.dumps(self.display['workArea']) +
            f" scaleFactor={self.display['scaleFactor']}")

        self.window = webview.create_window(
            title='Sotto',
            url=url,
            # NOT `icon=` HERE. `icon` is a parameter of `webview.start()`
            # (`webview/__init__.py:179`, applied to `_state['icon']` at :221-222)
            # and `create_window` (:309) does not accept it: passing it here
            # raised `TypeError` INSIDE `create_window`, which on pythonw.exe
            # (stdout and stderr both None) is a SILENT death — measured, the
            # run stopped at `panel geometry:` with no traceback and no window.
            # The icon is passed to `start()` below.
            js_api=SottoHost(self),
            width=geometry['width'],
            height=geometry['height'],
            # THE MINIMUM, ON PURPOSE. pywebview's own default is
            # `min_size = (200, 100)` (webview/window.py:92), applied as
            # `form.MinimumSize` (webview/platforms/winforms.py:210-212),
            # and the shell resizes THIS SAME window to 380x40 when the
            # caption floats out of the strip (measured in the log:
            # "PANEL_SURFACE surface=strip reason=float-off window=380x40").
            # With the default minimum that resize was clamped to 380x100 --
            # a window 60 px taller than the shell asked for. MEASURED in a
            # bare hidden WinForms form: min(200,100) -> 380x100;
            # min(0,0) -> 380x40; min(200,40) -> 380x40.
            # 40 is the height the shell itself uses for the floated
            # caption; 200 is below the narrowest geometry in use.
            min_size=(200, 40),
            # CREATED AT ITS REAL GEOMETRY. An off-screen creation
            # (`x=OFFSCREEN, y=OFFSCREEN`, OFFSCREEN=-32000) was tried
            # 2026-10-06 as the flash cure and MEASURED BROKEN: WebView2 does
            # not complete the stage->panel navigation for a window parked at
            # -32000, so `_on_loaded` never fires and the shell HANGS before
            # the panel loads (measured, no --exit-after, 9 s: log stops at
            # `STAGING_LOADED`, no `PRELOAD_ACTIVE`, no `RECEIVER_READY`). It
            # also broke the `--exit-after` probes the same way. Do not
            # reintroduce it. The startup flash is handled by `_reassert_hidden`
            # on `NavigationStarting`.
            x=geometry['x'],
            y=geometry['y'],
            frameless=True,
            transparent=not self.args.opaque,
            on_top=True,
            resizable=False,
            easy_drag=False,
            hidden=True,
            # pywebview takes a hex TRIPLET, so the transparent case is carried
            # by `transparent=True` (which sets the WebView2 default background
            # to Transparent), not by an 8-digit colour here.
            **({} if self.args.opaque else {'background_color': '#0b0f14'}),
            text_select=False,
        )
        # ══════════════════════════════════════════════════════════════════════════════
        # A SEGUNDA JANELA: A LEGENDA. Owner, 2026-10-15, verbatim -- *"a porra da
        # legenda, e pra ser independente do painel, nao acoplado"* e *"essa legenda ao
        # vivo deveria aparecer no MEIO EM BAIXO da minha tela, igual eu ja falei DEZENAS
        # DE VEZES nessa sessao"*. O pedido de origem, [860]: *"the live subtitles in the
        # BOTTOM AND MIDDLE of the screen"*.
        #
        # PORQUE UMA JANELA E NAO CSS: a legenda vivia DENTRO desta janela, empilhada
        # debaixo da barra (`panel.css`: "The two overlays share one window, so they are
        # STACKED"). Um caixote partilhado nao consegue pousar a legenda no fundo da TELA
        # e ao mesmo tempo ter a barra no topo dele -- e era por isso que o print do dono
        # mostrava o painel E a legenda, o *"duas coisa sobrepostas"* que ele descreveu.
        # Duas janelas nao se podem sobrepor uma a outra; o problema deixa de existir por
        # construcao, nao por regra de CSS.
        #
        # ONDE: no fundo-centro do WORKAREA -- o retangulo que exclui a barra de tarefas,
        # para ela nao ficar por baixo. Larga (ate 900) e baixa, porque o zip poe a
        # legenda numa faixa larga por cima do video, nao numa coluna.
        #
        # SO A LEGENDA: `caption.html` e a pagina propria; nada do painel entra aqui.
        # Sem fundo (transparent), sem moldura, sem scrollbar.
        #
        # ESCONDIDA A NASCENCA e mostrada pelo botao live. `on_top` para ficar por cima do
        # que estiver em ecra; o `hidden=True` e o que impede o flash no arranque.
        # ══════════════════════════════════════════════════════════════════════════════
        wa = self.display.get('workArea') or self.display.get('bounds')
        cap_w = max(360, min(900, int(wa['width']) - 80))
        cap_h = 170
        cap_x = int(wa['x']) + (int(wa['width']) - cap_w) // 2
        cap_y = int(wa['y']) + int(wa['height']) - cap_h - 48
        # THE FLOATING CAPTION IS A NATIVE LAYERED WINDOW, NOT A WEBVIEW2.
        # WebView2 is an opaque child inside pywebview's WinForms host; no
        # parent colour key can key its pixels (WebView2Feedback #118), and
        # pywebview documents `transparent` as unsupported on Windows. A
        # Win32 layered window with `UpdateLayeredWindow` is the supported
        # per-pixel-alpha path. The panel and strip stay WebView2/HTML/CSS.
        self.caption_overlay = None
        # The last design the page measured, kept so the overlay can be created
        # after the first push and still be branded on its first paint.
        self._brand_tokens_last = getattr(self, '_brand_tokens_last', None)
        # THE OWNER'S SWITCH, AND IT IS NOT THE SAME FACT AS "A WINDOW IS UP".
        # Owner 2026-10-17, verbatim: *"ao clicar no botao de legenda, nao deve
        # abrir qualquer coisa. e pra ativar a legenda, na minha tela, sem
        # background, sem estar conectada a qualquer painel."* So the caption is
        # OFF until he turns it on: before this flag, every caption line pushed the
        # window up by itself (`push_caption_to_window`, measured live as
        # `CAPTION_OVERLAY_PUSH count=1 visible=true hwnd=1775132` with no click
        # anywhere in the log) and the button was decoration. The page paints its
        # own `aria-pressed` from this flag, so the switch and the words cannot
        # disagree. `_caption_window_shown` stays the OTHER fact — whether pixels
        # are on screen right now — because silence must be able to blank the
        # overlay without switching the owner off.
        # O INTERRUPTOR SOBREVIVE AO ARRANQUE (2026-11-03). Ele liga a legenda
        # com um HOLD; um reinicio do shell nao e' um pedido para a desligar, e
        # ate' aqui CADA relancamento voltava ao `False` -- medido hoje em tres
        # relancamentos seguidos, com o dono a ver a legenda desaparecer sem ter
        # tocado em nada. Ficheiro de estado, e so' isso: quem desligar com o
        # mesmo HOLD grava `false` e a janela nao volta.
        self._caption_wanted = self._caption_wanted_restored()
        try:
            import caption_overlay
            self.caption_overlay = caption_overlay.NativeCaptionOverlay(log=log)
            self.caption_overlay.set_work_area(
                wa, self.display.get('scaleFactor') or 1.0)
            if True:
                try:
                    import overlay_paint as _op
                    self.caption_overlay.set_theme(_op._THEME_DEFAULT)
                    log('CAPTION_OVERLAY_THEME_REPLAYED theme=youtube brand=%r'
                        % (((self._brand_tokens_last or {}) or {}).get('theme') or '-'))
                except Exception as exc:  # noqa: BLE001
                    log(f'CAPTION_OVERLAY_THEME_REPLAY_FAILED error={exc!r}')
            log(f'CAPTION_OVERLAY_MODE native=true hwnd='
                f'{self.caption_overlay.hwnd} work={wa["width"]}x{wa["height"]}')
            # A PRESSAO QUE CHEGOU CEDO E' HONRADA AQUI (2026-11-03).
            pending = getattr(self, '_caption_show_pending', None)
            if pending is not None:
                self._caption_show_pending = None
                log('CAPTION_WINDOW_DEFERRED_APPLIED on=%s'
                    % str(bool(pending)).lower())
                self._caption_window_shown = bool(pending)
                self.caption_overlay.show(bool(pending))
        except Exception as exc:  # noqa: BLE001
            log(f'CAPTION_OVERLAY_MODE_FAILED error={exc!r}')

        self._caption_window_w = cap_w
        self._caption_window_h = cap_h
        self._caption_window_x = cap_x
        self._caption_window_y = cap_y
        # DO NOT clear `self.window.transparent` here. Tried 2026-10-06 and
        # MEASURED WRONG: pywebview's navigation `Show()` (edgechromium.py:347,
        # gated by `transparent`) is what makes a transparent WebView2 actually
        # LOAD; clearing the flag makes the stage->panel navigation never
        # complete, so `_on_loaded` never fires and the shell HANGS (measured
        # `_main/_flash-live-0.log`: stops at `STAGING_LOADED`, rc=-999, never
        # reaches PANEL_VISIBILITY_ON_SCREEN). Transparency must stay on.
        # The startup flash is NOT handled by an off-screen creation position:
        # there is NO off-screen creation left in this file (measured 2026-10-11:
        # six OFFSCREEN mentions in prose, zero executable; the constant was
        # REMOVED 2026-10-06, see :1010). It is handled by `_gate_form_show`
        # (installed from `_on_before_show`), which REFUSES pywebview's own
        # full-opacity `Show()` until somebody asked for the panel; the cure and
        # its measurements are in `_main/receipt-20261007-panel-startup-flash.md`.
        # This sentence pointed at the off-screen position until 2026-10-11, and
        # it sent readers looking for code that is not there.
        self.window.events.before_show += self._on_before_show
        self.window.events.loaded += self._on_loaded
        self.window.events.closing += self._on_closing
        return self.window

    # ── O CAO-DE-GUARDA DA THREAD DE UI (2026-10-23) ──────────────────────────
    # O dono, verbatim: *"o sotto travou. nao deve travar nunca. faça isso
    # acontecer. a ui dele tambem, a legenda e o painel de baixo, tao congelados
    # na minha tela enchendo o saco"*.
    #
    # MEDIDO na sessao das 22:32 (pid 68572): a app estava a mostrar legendas
    # (`CAPTION_APPLIED text="We explain everything there."`) e, depois do
    # `FORM_SHOW_TRANSPARENCY_HACK ... on the UI thread`, o log PAROU em
    # 22:32:56.566 e as DUAS janelas -- `class=SottoNativeCaption` e
    # `class=WindowsForms10.Window...` -- ficaram congeladas no ecra ate o
    # processo ser morto a mao. A causa e uma so: a thread de UI parou, e o
    # painel, a legenda (`CAPTION_OVERLAY_PUSH ... post=ui`) e os escritores de
    # estado dependem todos dela.
    #
    # Este cao-de-guarda NAO depende de o codigo da app cooperar. `SendMessage`
    # com `SMTO_ABORTIFHUNG` e a definicao do Windows de "esta janela responde?";
    # quando dois pedidos seguidos nao voltam, a UI esta presa de facto. Antes de
    # sair, DESPEJA A PILHA DE TODAS AS THREADS -- e a unica prova que diz a
    # LINHA do bloqueio em vez de "travou". Sair e deliberado e e a garantia que
    # o dono pediu: uma app congelada nunca fica no ecra.
    #
    # NAO conta golpes antes da primeira resposta: um arranque em que a UI ainda
    # nao bombeou (WebView2 a inicializar) nao e um congelamento, e matar a app
    # por isso seria trocar um defeito por outro.
    UI_WATCHDOG_POLL_S = 5.0
    # MEDIDO 2026-11-03, na maquina do dono com os projectos dele a correr:
    # a app MORREU duas vezes sozinha (`UI_WATCHDOG_EXIT code=9`) e o despejo
    # mostrava a MainThread dentro do bootstrap do pywebview
    # (`webview/platforms/winforms.py`, `thread.Join(500)`) -- ou seja, o
    # watchdog matou uma app que o Windows estava a atrasar, nao uma que tinha
    # um impasse nosso. 4 s num nucleo com 69 % de CPU e tres projectos a
    # competir nao sao impasse: sao fila. Os limites passam a 6 s e tres golpes
    # (15 s sem bombear) e, quando a pilha do UI nao tem NENHUM frame nosso,
    # o limite sobe para seis golpes: um despejo sem codigo nosso dentro nao e'
    # prova de impasse nosso.
    UI_WATCHDOG_TIMEOUT_MS = 6000
    UI_WATCHDOG_STRIKES = 3
    UI_WATCHDOG_STRIKES_FOREIGN = 6

    def _ui_stack_is_foreign(self):
        """A pilha do UI tem algum frame NOSSO?

        MEDIDO 2026-11-03: os despejos que precederam um `UI_WATCHDOG_EXIT
        code=9` mostravam a MainThread em `webview.start -> create_window ->
        thread.Join(500)`. Uma app que nao bombeia porque o Windows nao lhe da'
        CPU nao e' uma app presa; matar essa deixa o dono sem legenda a meio do
        video. Conta-se impasse so' quando a pilha tem um frame de
        `sotto_webview.py` que nao seja o `main` do arranque.
        """
        try:
            frame = sys._current_frames().get(threading.main_thread().ident)
            ours = 0
            while frame is not None:
                name = str(frame.f_code.co_filename or '')
                if (name.endswith('sotto_webview.py')
                        and frame.f_code.co_name != 'main'):
                    ours += 1
                frame = frame.f_back
            return ours == 0
        except Exception:              # noqa: BLE001
            return False

    def _thread_cpu_census(self, window_s=5.0, log_it=True):
        """QUEM GASTA O NUCLEO -- por NOME, nao por tid (2026-11-03).

        MEDIDO: a shell viva (pid 6040) gastava **102 % de um nucleo** em repouso,
        e o instrumento que existia so' sabia dizer `tid 39712 94,8 %`. Um `tid`
        nao se le: `UI_HUNG_THREAD` escreve `ident=`, e em CPython no Windows esse
        `ident` E' o tid nativo (`PyThread_get_thread_ident` devolve
        `GetCurrentThreadId`), logo a tabela `threading.enumerate()` e' o mapa
        tid->nome que faltava.

        `GetThreadTimes` e' read-only e funciona de medium para high (medido);
        nao precisa de py-spy nem de administrador. Sem delta entre duas
        amostras nao ha' numero, por isso a primeira chamada so' guarda a base.
        """
        try:
            import ctypes as _ct
            from ctypes import wintypes as _wt
            k32 = _ct.windll.kernel32
            names = {t.ident: t.name for t in threading.enumerate() if t.ident}
            if not names:
                return []

            def _ticks(tid):
                h = k32.OpenThread(0x0800, False, int(tid))  # QUERY_LIMITED
                if not h:
                    return None
                try:
                    c = _wt.FILETIME(); e = _wt.FILETIME()
                    k = _wt.FILETIME(); u = _wt.FILETIME()
                    if not k32.GetThreadTimes(h, _ct.byref(c), _ct.byref(e),
                                              _ct.byref(k), _ct.byref(u)):
                        return None
                    ft = lambda f: (f.dwHighDateTime << 32) | f.dwLowDateTime  # noqa: E731
                    return ft(k) + ft(u)
                finally:
                    k32.CloseHandle(h)

            now = time.monotonic()
            cur = {tid: _ticks(tid) for tid in names}
            base = getattr(self, '_cpu_census_base', None)
            self._cpu_census_base = (now, cur)
            if not base:
                return []
            t0, prev = base
            span = max(1e-3, now - t0)
            rows = []
            for tid, ticks in cur.items():
                if ticks is None or prev.get(tid) is None:
                    continue
                rows.append(((ticks - prev[tid]) / 1e7 / span * 100.0,
                             names.get(tid, 'tid-%s' % tid)))
            rows.sort(reverse=True)
            if log_it and rows:
                total = sum(r[0] for r in rows)
                if total >= 20.0:
                    log('THREAD_CPU total=%.0f%% top=%s'
                        % (total, ' '.join('%s:%.0f%%' % (n, p)
                                           for p, n in rows[:4])))
            return rows
        except Exception:                 # noqa: BLE001
            return []

    def _start_thread_cpu_census(self, every_s=60.0):
        """Publica `THREAD_CPU` de minuto a minuto (silencioso abaixo de 20 %)."""
        if getattr(self, '_cpu_census_thread', None) is not None:
            return
        if os.environ.get('SOTTO_NO_CPU_CENSUS', '').strip() == '1':
            log('THREAD_CPU_CENSUS disabled=env')
            return

        def _loop():
            self._thread_cpu_census(log_it=False)   # a base
            while True:
                time.sleep(every_s)
                self._thread_cpu_census()

        self._cpu_census_thread = threading.Thread(
            target=_loop, name='sotto-thread-cpu', daemon=True)
        self._cpu_census_thread.start()

    def _dump_thread_stacks(self, reason):
        """A pilha da thread que trava, e so' ela: a prova, sem o volume.

        MEDIDO 2026-11-04: este dump escrevia a pilha de TODAS as threads, uma
        linha por frame -- 280 linhas por estouro e **23 194** linhas
        `UI_HUNG_FRAME` no log do dono. O que se pergunta a` pilha e' QUAL
        thread esta' presa, e a resposta esta' na thread principal: as outras
        vao cortadas (2, e caladas quando nao tem frame util). Um estouro por
        `UI_HUNG_DUMP_EVERY_S` (600) tem pilha completa; os do meio contam-se
        numa linha so'.
        """
        import traceback
        now = time.monotonic()
        last = getattr(self, '_ui_hung_dump_at', 0.0)
        compact = (now - last) < UI_HUNG_DUMP_EVERY_S
        self._ui_hung_dump_at = now
        frames = sys._current_frames()
        main_ident = None
        try:
            main_ident = threading.main_thread().ident
        except Exception:                 # noqa: BLE001
            main_ident = None
        log('UI_HUNG reason=%s threads=%d compact=%s'
            % (reason, threading.active_count(), str(compact).lower()))
        if compact:
            return
        main_thread = threading.main_thread() if main_ident else None
        # A PRINCIPAL PRIMEIRO, sempre; as outras duas so' como contexto.
        ordered = ([main_thread] if main_thread is not None else []) + [
            t for t in threading.enumerate() if t is not main_thread][:2]
        for thread in ordered:
            frame = frames.get(thread.ident)
            log('UI_HUNG_THREAD name=%s ident=%s daemon=%s'
                % (thread.name, thread.ident, thread.daemon))
            if frame is None:
                log('UI_HUNG_FRAME <sem frame>')
                continue
            stack = traceback.format_stack(frame)[-14:]
            for chunk in stack:
                for line in chunk.rstrip().splitlines():
                    log('UI_HUNG_FRAME ' + line.strip()[:160])

    def _start_ui_watchdog(self):
        if getattr(self, '_ui_watchdog_started', False):
            return
        hwnd = self.hwnd
        if not hwnd:
            log('UI_WATCHDOG_SKIPPED reason=no-hwnd')
            return
        self._ui_watchdog_started = True
        log('UI_WATCHDOG_STARTED hwnd=%s poll_s=%s timeout_ms=%s strikes=%s'
            % (hwnd, self.UI_WATCHDOG_POLL_S, self.UI_WATCHDOG_TIMEOUT_MS,
               self.UI_WATCHDOG_STRIKES))
        send = user32.SendMessageTimeoutW
        send.restype = ctypes.c_size_t
        send.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t,
                         ctypes.c_ssize_t, ctypes.c_uint, ctypes.c_uint,
                         ctypes.POINTER(ctypes.c_size_t)]
        SMTO_ABORTIFHUNG = 0x0002
        WM_NULL = 0x0000

        def loop():
            answered_once = False
            strikes = 0
            while True:
                time.sleep(self.UI_WATCHDOG_POLL_S)
                result = ctypes.c_size_t(0)
                try:
                    got = send(ctypes.c_void_p(hwnd), WM_NULL, 0, 0,
                               SMTO_ABORTIFHUNG, self.UI_WATCHDOG_TIMEOUT_MS,
                               ctypes.byref(result))
                except Exception as exc:  # noqa: BLE001
                    log('UI_WATCHDOG_ERROR error=%r' % (exc,))
                    continue
                if got:
                    answered_once = True
                    if strikes:
                        log('UI_WATCHDOG_RECOVERED strikes=%d' % strikes)
                    strikes = 0
                    continue
                if not answered_once:
                    log('UI_WATCHDOG_NOANSWER_BEFORE_FIRST reason=startup')
                    continue
                strikes += 1
                log('UI_WATCHDOG_STRIKE strike=%d hwnd=%s err=%s'
                    % (strikes, hwnd, ctypes.get_last_error()))
                if strikes < self.UI_WATCHDOG_STRIKES:
                    continue
                if strikes < self.UI_WATCHDOG_STRIKES_FOREIGN and self._ui_stack_is_foreign():
                    log('UI_WATCHDOG_BUSY strike=%d reason=sem-codigo-nosso-na-pilha'
                        % strikes)
                    continue
                # A UI esta presa de facto: dizer ONDE, e sair para nao deixar
                # uma janela congelada no ecra do dono.
                self._dump_thread_stacks('ui-thread-not-responding')
                log('UI_WATCHDOG_EXIT code=9 -- a UI estava presa; a sair para '
                    'nao deixar janelas congeladas no ecra')
                try:
                    sys.stdout.flush()
                    sys.stderr.flush()
                except Exception as exc:  # noqa: BLE001
                    log('UI_WATCHDOG_FLUSH_FAILED error=%r' % (exc,))
                time.sleep(0.3)
                os._exit(9)

        self._ui_watchdog = threading.Thread(target=loop, name='sotto-ui-watchdog',
                                             daemon=True)
        self._ui_watchdog.start()
        self._start_slow_read_monitor()

    def _start_slow_read_monitor(self):
        """Despeja pilhas quando a LEITURA DA LEGENDA passa do limite.

        Nasceu da medicao de 2026-11-03: a instancia do dono ficou 60 s sem um
        tick e sem uma linha no log, e nao havia forma de saber em QUE chamada o
        laco estava -- o `_dump_thread_stacks` so' corria quando a UI ficava
        surda, e a UI estava viva. Este vigia olha para o marcador que
        `ExternalCaptionWatcher._read` escreve e, uma vez por episodio, despeja
        a pilha de todas as threads (uma vez, nao a cada 2 s).
        """
        if getattr(self, '_slow_read_thread', None) is not None:
            return

        def loop():
            dumped_for = 0.0
            while True:
                time.sleep(2.0)
                w = getattr(self, 'external_caption_watcher', None)
                since = float(getattr(w, '_in_read_since', 0.0) or 0.0) if w else 0.0
                if not since:
                    dumped_for = 0.0
                    continue
                if since == dumped_for:
                    continue
                if time.monotonic() - since < 3.0:
                    continue
                dumped_for = since
                try:
                    self._dump_thread_stacks('caption-read-slow')
                except Exception:             # noqa: BLE001
                    pass

        self._slow_read_thread = threading.Thread(target=loop,
                                                 name='sotto-slow-read',
                                                 daemon=True)
        self._slow_read_thread.start()

        # QUEM GASTA O NUCLEO, POR NOME (2026-11-03). O `THREAD_CPU` do
        # minuto seguinte e' o instrumento que transforma "a app e' pesada"
        # num nome de thread e uma percentagem.
        self._start_thread_cpu_census(every_s=30.0)

        # SHEDDING POR CARGA (owner, 2026-10-30) e a ACCAO que lhe da' um lever
        # (owner, 2026-11-03): *"os modelos entram e saem conforme a carga do
        # sistema, e o audio nao processado e' processado sozinho quando a carga
        # libera -- SEM NUNCA TRAVAR A MAQUINA DO DONO"*.
        #
        # O NIVEL ARMA O MODO, NAO MATA O PROCESSO. Medido 2026-11-03: o audio so'
        # existe DENTRO do worker (quem abre o endpoint e' o `sotto_worker.py`);
        # matar o worker para libertar a VRAM para a captura no intervalo. O lever
        # e' o `shed` que o worker JA' poll: `alta` poe-no em batch (larga o
        # nemotron), `muito-alta` larga os dois e o audio continua a ser capturado
        # e acumulado. Toda a decisao (piso, histerese, sustentacao) vive em
        # `load_shedding.py`; a fila e o executor, em `batch_queue.py`.
        #
        # `SOTTO_LOAD_SHED=0` desliga a medicao (e o `shed` deixa de ser escrito);
        # `SOTTO_LOAD_SHED_ACT=0` desarma so' a accao.
        if os.environ.get('SOTTO_LOAD_SHED') != '0':
            # O LOG FICA FORA DO GUARD DO ARRANQUE: medido 2026-10-30 10:56:55,
            # a linha `STARTED` lia o `armed` retirado e, no MESMO `try`, desarmou
            # a funcionalidade toda: diagnostico nao derruba a coisa.
            try:
                # O MONITOR NAO ARRANCA O LACO DELE. Ele mede so' o commit;
                # `open_action` mede commit E CPU e fica com o estado e o
                # publicador dele, para haver UM escritor e UM numero no ficheiro.
                monitor = LoadSheddingMonitor(self)
                self._load_shedding = monitor
                self._load_action = load_shedding().open_action(
                    self, monitor=monitor, log_fn=log)
            except Exception as exc:  # noqa: BLE001 -- nunca impede a app de subir
                log('LOAD_SHEDDING_START_FAILED error=%r' % (exc,))
            else:
                try:
                    log('LOAD_SHEDDING_STARTED interval_s=%.0f canal=shed'
                        % LoadSheddingMonitor.INTERVAL_S)
                    state = self._load_action.as_dict()
                    log('LOAD_ACTION_STARTED armed=%s floor_s=%.0f samples=%d'
                        ' queue=%s'
                        % (str(state.get('armed')).lower(),
                           float(state.get('floor_s') or 0.0),
                           int(state.get('samples_required') or 0),
                           (state.get('batch') or {}).get('queue', {}).get('dir', '-')))
                except Exception as exc:  # noqa: BLE001 -- uma linha nao desarma nada
                    log('LOAD_ACTION_LOG_FAILED error=%r' % (exc,))

    def _form(self):
        return getattr(self.window, 'native', None)

    def _on_before_show(self):
        """The earliest hook that exists: the WinForms form is built and
        EnsureCoreWebView2Async has been *called* but has not completed."""
        form = self._form()
        if form is None:
            return
        self.form = form
        try:
            self.hwnd = int(form.Handle.ToInt64())
        except Exception:
            self.hwnd = None
        self.webview2 = form.webview
        # O cao-de-guarda da thread de UI: começa aqui porque e aqui que o
        # painel passa a ter HWND. Ver `_start_ui_watchdog`.
        self._start_ui_watchdog()

        # ── THE FORM'S OWN BACKGROUND IS THE FAILURE-MODE COLOUR ──────────────
        # The panel is a transparent WinForms form: pywebview sets
        # `SupportsTransparentBackColor` and the WebView2's
        # `DefaultBackgroundColor = Color.Transparent`
        # (platforms/winforms.py:289-290), and sets `self.BackColor` ONLY in the
        # non-transparent branch (:291-292). So a transparent form keeps .NET's
        # DEFAULT -- measured 2026-10-09 as `rgb(240,240,240)`, i.e.
        # `SystemColors.Control`.
        #
        # That default is what the owner stares at. When the WebView2 path fails
        # to composite -- and it does, measurably: `Chrome_WidgetWin_0` hidden,
        # `PrintWindow` on it returning a single black colour, and the browser
        # view sitting on `about:blank` -- the form is all there is, and the
        # overlay shows a WHITE slab instead of the dark one the CSS describes.
        # The page itself is correct in that state: `body.bgc =
        # rgba(11,15,20,0.98)` with 10 stylesheets and `surface=strip`.
        #
        # So the form is given the slab's colour too. It is NOT a second design
        # and it is not decoration: it is the colour of the thing the owner sees
        # when the WebView2 does not paint. When the page paints, the WebView2
        # covers the form completely and this value is never seen.
        # CORRECTED 2026-10-12, owner verbatim: *"eu to vendo div com cor solida
        # inves de invisivel"*. The dark slab above is STILL A SLAB. It was the
        # lesser of two evils against .NET's white `SystemColors.Control`, but
        # the owner asked for NEITHER: the caption overlay is meant to float over
        # whatever is on screen with nothing behind it. pywebview already sets
        # `SupportsTransparentBackColor` on this form (platforms/winforms.py:289),
        # so `Color.Transparent` is legal here and every pixel the page does not
        # paint shows the DESKTOP instead of a colour.
        #
        # The failure mode is now "you see through the window", which is the
        # correct failure mode for an overlay and strictly better than a slab in
        # the wrong colour. `--opaque` still gets the dark slab, because that flag
        # exists to give up transparency on purpose.
        try:
            from System.Drawing import Color as _DrawColor  # noqa: F401
            if self.args.opaque:
                form.BackColor = _DrawColor.FromArgb(0xFF, 0x0B, 0x0F, 0x14)
                log('FORM_BACKCOLOR set=#0B0F14 reason=--opaque')
            else:
                form.BackColor = _DrawColor.Transparent
                log('FORM_BACKCOLOR set=transparent reason=overlay-not-a-slab '
                    'cure=SupportsTransparentBackColor')
        except Exception as exc:  # noqa: BLE001
            log(f'FORM_BACKCOLOR_FAILED error={exc!r}')

        # MEASUREMENT, and it changes nothing: what icon the form is carrying
        # and what the window answers for `WM_GETICON`. pywebview has already
        # run `BrowserForm.__init__` (winforms.py:773 runs before the
        # `before_show` at :775), so this reads the icon pywebview CHOSE.
        log(window_icon_report(form, self.hwnd))
        # ...and then the fix, on the same handle: the WinForms `Icon` property
        # plus three explicit `WM_SETICON` sends. Logged with its own read-back
        # so the two lines can be compared.
        _icon = apply_window_icon(form, self.hwnd)
        log(f"WINDOW_ICON_APPLIED applied={str(_icon['applied']).lower()} "
            f"path={_icon['path']} handle={_icon['handle']} "
            f"reason={_icon['reason']}")
        log(window_icon_report(form, self.hwnd))

        # THE MAPPING CALL IS REFUSED HERE. pywebview maps this form itself on
        # EVERY navigation start (`platforms/edgechromium.py:345-349`):
        #
        #     if self.pywebview_window.transparent:
        #         self.form.Show()
        #         self.form.Activate()
        #
        # `transparent` is ON by default in this shell (`--opaque` is the only
        # way off), so that call undoes `hidden=True` — and it is a call the
        # shell does not make and cannot order against. `_reassert_hidden`
        # (subscribed to the same event, right after) SHORTENS the window that
        # call maps; it cannot prevent the map, because the two run in the same
        # dispatch but the map is what the dispatch is doing. Measured by
        # `_main/panel-startup-flash-census.py` at a 25 ms cadence: the form was
        # WS_VISIBLE and NOT alpha-occluded in 1 of 6 launches even with the
        # re-assert in place. See `_gate_form_show`.
        self._gate_form_show(form)

        # The panel never takes focus and never sits in the taskbar; in Win32
        # both are extended styles, not window flags.
        hwnd = self.hwnd
        if hwnd:
            # ── `WS_EX_LAYERED` IS OPT-IN AND OFF BY DEFAULT, MEASURED ─────────
            # It was unconditional until 2026-10-09, and it is the reason the
            # strip composites WHITE. `MicrosoftEdge/WebView2Feedback#118` is the
            # upstream receipt: a user set `WS_EX_LAYERED` + `LWA_COLORKEY` on
            # the HWND embedding WebView2 and "That did not work (works fine
            # however on the window before webivew2 is embedded)", while
            # `LWA_ALPHA` on the same HWND did work. A layered window is
            # composited by DWM from a redirection surface, and a WebView2 child
            # HWND in WINDOWED hosting is composited on its own layer — the two
            # do not meet. The page parses, the CSS applies (both measured), and
            # the surface still comes out blank: `WindowFromPoint` names Sotto's
            # own `Chrome_WidgetWin_1` while the pixels are white, and the same
            # happens with `--opaque`.
            #
            # Nothing in this shell calls `SetLayeredWindowAttributes`, so the
            # flag bought no per-pixel alpha to begin with — it only broke the
            # compositing. Transparency is the WebView2's job
            # (`DefaultBackgroundColor = Color.Transparent`, which pywebview
            # sets at edgechromium.py:113-114) and the rounded corners are the
            # page's own `border-radius`.
            styles = WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TRANSPARENT
            if str(os.environ.get('SOTTO_LAYERED') or '').strip().lower() \
                    in ('1', 'true', 'yes', 'on'):
                cap_styles |= WS_EX_LAYERED
                log('panel WS_EX_LAYERED kept by SOTTO_LAYERED=1 '
                    '(measured harmful: strip composites white)')
            set_ex_style(hwnd, add=styles)
            log('panel setAlwaysOnTop(floating) ok '
                'style=WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE|WS_EX_TRANSPARENT'
                + ('|WS_EX_LAYERED' if styles & WS_EX_LAYERED else ''))
            log('panel setFocusable(false) ok (WS_EX_NOACTIVATE)')
            log('panel setIgnoreMouseEvents(true, forward) ok (WS_EX_TRANSPARENT)')
            log('panel setVisibleOnAllWorkspaces SKIPPED - no WebView2/WinForms '
                'equivalent exists')

        self._fit_client_area(form)
        # THE VISIBILITY INVARIANT IS ARMED HERE, NOT IN `_on_core_ready`.
        # See `_arm_visibility_invariant` for why the two are separate
        # subscriptions; TICKET-55a4ab4b157bdd26bb9629c7 is what it costs to
        # let one registration be a side effect of the other.
        self._ui(self._arm_visibility_invariant)
        self._ui(self._subscribe_core_ready)
        # The startup-visibility probe is POSTED, never called from here:
        # before_show fires BEFORE pywebview's own Show();Hide() dance
        # (winforms.py:775 is this event; :777-782 is the dance), so a call at
        # this point would read a window that has not been created yet. Posted,
        # it runs on the UI thread the moment create() returns -- i.e. at the
        # state the owner would actually get.
        self._post(self._measure_startup_visibility)

    def _fit_client_area(self, form):
        """Make the CLIENT area exactly the docked panel size.

        pywebview sets `Form.Size` (winforms.py:209) while the form still has
        the default Sizable border, and only later switches to `None` for
        `frameless=True` (winforms.py:269-271). The WebView2 child is then
        sized to the client area computed under the OLD border, so the panel
        laid out at 364x861 inside a 380x900 window — measured, and the reason
        the DOMDUMP viewport disagreed with the Electron arm. Setting
        `ClientSize` after the border change pins the client area to the
        geometry the shell actually promised.
        """
        from System.Drawing import Size
        from System.Windows.Forms import DockStyle

        scale = self.display['scaleFactor']
        want_w = int(self.geometry['width'] * scale)
        want_h = int(self.geometry['height'] * scale)
        form.ClientSize = Size(want_w, want_h)
        self.webview2.Dock = DockStyle.Fill
        log(f'panel client area forced to {want_w}x{want_h} '
            f'(window {self.geometry["width"]}x{self.geometry["height"]})')

    def _measure_startup_visibility(self):
        """Is the panel ON THE OWNER'S SCREEN the moment the window exists?

        One line, and it is a MEASUREMENT, not a claim: `visible` is
        `IsWindowVisible(hwnd)` — the same channel the house window census
        reads (`Get-Process … .MainWindowHandle`, which .NET computes with
        `IsWindowVisible` + `GW_OWNER == 0`), so the log line and the census
        can be held against each other.

        WHY IT IS POSTED. pywebview's `hidden=True` branch (winforms.py:777-782)
        runs `Opacity=0; Show(); Hide(); Opacity=1`, so the form IS WS_VISIBLE
        for the span of one Show/Hide pair — measured in `_main/_dance-probe.py`
        with a bare WinForms form: visible=True between the two statements and
        False again after `Hide()` and after `Opacity=1`. A call placed in
        `_on_before_show` would read the state BEFORE that dance; posted, this
        runs after `create()` returns, which is the state the owner gets.

        `--show` is the app's own way to come up visible, so a `visible=true`
        there is the expected answer, not a defect — the line states the fact
        either way and never argues.
        """
        hwnd = self.hwnd
        visible = window_visible(hwnd) if hwnd else False
        self.startup_visible = visible
        form = self._form()
        try:
            form_visible = str(bool(form.Visible)).lower()
            opacity = form.Opacity
        except Exception:
            form_visible, opacity = 'unknown', 'unknown'
        log(f'PANEL_VISIBILITY_AT_STARTUP visible={str(visible).lower()} '
            f'hwnd={hwnd} form.Visible={form_visible} opacity={opacity} '
            f'show_requested={str(bool(self.args.show)).lower()}')
        # The ex-style the shell asked for in `_on_before_show` does NOT survive
        # pywebview's startup dance — measured, see `reassert_taskbar_ex_style`.
        # This is the first moment after that dance, so it is where the bits are
        # put back.
        self.ex_style = reassert_taskbar_ex_style(hwnd, 'post-startup-dance')
        log(window_icon_report(form, hwnd))

    def _measure_on_screen_visibility(self, where):
        """The panel's state ONCE THE STARTUP SEQUENCE HAS SETTLED.

        `PANEL_VISIBILITY_AT_STARTUP` reads the window pywebview's `hidden=True`
        dance leaves behind, and that dance does leave it hidden — measured, and
        reproducible in `_main/_dance-probe.py` with a bare WinForms form. It is
        therefore NOT the whole answer, and on its own it is the log that looks
        clean while the owner has a window on his screen:

            pywebview SHOWS the form again on EVERY navigation start when the
            window is transparent (edgechromium.py:345-349 —
            `if transparent: self.form.Show()`), and this shell navigates twice
            (stage.html, then the panel). `transparent` is ON by default
            (`--opaque` turns it off), so the panel came up ON SCREEN while
            `run.cmd` promises "start hidden".

        This line reads the state the owner actually gets, after the panel has
        loaded, in the same channel as the line above.
        """
        hwnd = self.hwnd
        visible = window_visible(hwnd) if hwnd else False
        log(f'PANEL_VISIBILITY_ON_SCREEN visible={str(visible).lower()} '
            f'where={where} hwnd={hwnd} '
            f'panel_shown={str(bool(self.visible)).lower()} '
            f'show_requested={str(bool(self.args.show)).lower()}')

    def _subscribe_core_ready(self):
        """Subscribe with `+=`, the only form pythonnet accepts for an event.

        Measured, both alternatives refused:
          * `add_CoreWebView2InitializationCompleted(fn)` ->
            "'method' value cannot be converted to System.EventHandler`1[...]"
          * `setattr(control, 'CoreWebView2InitializationCompleted', fn)` ->
            "TypeError: cannot set event attributes"
        pythonnet implements `obj.Event += handler` by returning a wrapper
        from the event GETTER and mutating that, so the statement form is the
        real API. It cannot live inside a lambda, hence this method.
        """
        self.webview2.CoreWebView2InitializationCompleted += self._on_core_ready

    def _gate_form_show(self, form):
        """Refuse pywebview's own mapping call unless the owner asked.

        THE DEFECT THIS CLOSES. `Show` is a `System.Windows.Forms.Form` method,
        but pywebview calls it from PYTHON — `self.form.Show()`
        (`platforms/edgechromium.py:348`) — so an attribute set on the INSTANCE
        shadows it for exactly that call and nothing else. Measured:
        `_main/_pythonnet-show-shadow-test.py` → `instance: base.Show() ->
        INSTANCE-GATED`, with `type(base).Show` still the CLR method.

        WHY A GATE HERE AND NOT ANOTHER NET. Every previous cure re-hid the
        window AFTER pywebview mapped it, so the window was mapped and the only
        question was how long. This refuses the map itself. It changes NO
        subscription, which matters: `_main/panel-hidden-at-startup-oracle.py`
        asserts `NavigationStarting handlers=2 (1 pywebview + 1 shell)`, and
        that assertion keeps its exact meaning.

        WHY IT CANNOT COST THE OWNER THE PANEL. The shell has its OWN way to map
        the window — `show_panel` → `user32.ShowWindow(SW_SHOWNOACTIVATE)` — and
        BOTH user paths take it: Alt+C (`toggle_panel` → `show_panel`) and
        `--show` (`_on_loaded` → `self.show_panel('startup')`). Neither path
        calls `form.Show()`, so neither is refused.

        WHY THE CREATION DANCE IS STILL ALLOWED. pywebview's `hidden=True`
        branch (`platforms/winforms.py:777-781`) runs `Opacity=0; Show(); Hide();
        Opacity=1`. At that moment the form is FULLY TRANSPARENT, so its map is
        invisible by construction (the house already accepts this class: the
        `--opaque` arm's only catches are `alpha=0`, AGENTS.md). Refusing it
        would change the state the shipped app has always started in for no
        measured gain, so it is let through — the test is `Opacity < 1.0`, read
        from the form itself, not a shell flag that could drift out of step.
        """
        original = form.Show

        def guarded_show():
            try:
                opacity = float(form.Opacity)
            except Exception:
                opacity = 1.0
            if self.args.show or self.visible or opacity < 1.0:
                return original()
            self.panel_show_refused += 1
            log(f'PANEL_SHOW_REFUSED reason=not-asked opacity={opacity} '
                f'show_requested={str(bool(self.args.show)).lower()} '
                f'panel_shown={str(bool(self.visible)).lower()} '
                f'count={self.panel_show_refused} '
                'cure=_gate_form_show source=edgechromium.py:348')
            return None

        # An instance attribute shadows the CLR method for a PYTHON-side call
        # (measured, see the docstring). The delegate pywebview subscribed is a
        # method of ITS object and is untouched.
        form.Show = guarded_show
        log('PANEL_SHOW_GATE installed=true method=BrowserForm.Show '
            'refuses=map-at-full-opacity-unless-asked')

    def _arm_visibility_invariant(self):
        """Subscribe the hide-unless-asked guard, ONCE, as its own act.

        THE INVARIANT. pywebview asks for a transparent window and, on EVERY
        navigation, un-hides it itself: `if self.pywebview_window.transparent:
        self.form.Show(); self.form.Activate()`
        (edgechromium.py:346-349). That hack is load-bearing — clearing
        `transparent` stops the page loading at all (measured, see
        `create_window`) — so the shell's only defence is to re-hide the window
        immediately afterwards. `_on_navigation_start` is that defence, and its
        REGISTRATION is the entire invariant: with it absent the panel sits on
        the owner's desk while every internal flag still says "hidden".

        WHY IT IS ARMED HERE AND NOT IN `_on_core_ready`. Reading the installed
        pywebview (`platforms/edgechromium.py`, `platforms/winforms.py`):

          * `winforms.py:773` builds the form; `EdgeChrome.__init__` subscribes
            pywebview's handlers and calls `EnsureCoreWebView2Async(None)`
            (`edgechromium.py:101-102`, `:120`) — async, result discarded. The
            CONTROL exists; CoreWebView2 does not.
          * `winforms.py:775` fires `before_show`. This is therefore the last
            point that provably precedes EVERY navigation.
          * navigation #1 is raised from INSIDE the initialization-completed
            dispatch: `on_webview_ready` is what calls `load_url`
            (`edgechromium.py:305-311`), and pywebview subscribed that handler
            BEFORE the shell's `_on_core_ready`.

        So arming from `_on_core_ready` is a registration that is not merely
        late — it is registered by a callback the shell does not control, and
        when that callback does not arrive, `NavigationStarting` has no handler
        and nothing re-hides the window. That is the whole of
        TICKET-55a4ab4b157bdd26bb9629c7: the cure was reachable only through
        an unrelated subscription, so deleting one line left the panel visible
        while `py_compile` stayed at rc=0. Arming here removes the dependency;
        it also covers navigation #1, which the old registration could not.

        The guard is a precondition, not a best-effort: a control that is not
        there is a RAISE (this method runs before any navigation can, so the
        control must exist), never a silent return.
        `_main/panel-hidden-at-startup-oracle.py` holds the invariant by
        construction and fails if this registration ever stops being on the
        shipped path.
        """
        if self.visibility_armed:
            return
        if self.webview2 is None:
            raise RuntimeError(
                'PANEL_VISIBILITY_INVARIANT cannot be armed: no WebView2 '
                'control. Every navigation would be shown by pywebview with '
                'nothing to re-hide it.')
        # `+=` cannot live in a lambda (see `_subscribe_core_ready`), which is
        # why this is a method and not an inline statement.
        self.webview2.NavigationStarting += self._on_navigation_start
        self.visibility_armed = True
        log('PANEL_VISIBILITY_INVARIANT armed=true where=before_show '
            f'hwnd={self.hwnd}')

    def _on_core_ready(self, sender, args):
        """CoreWebView2 exists: install the preload-equivalent.

        Registration is per-ENVIRONMENT, not per-page, so registering while the
        staging page is the current document covers the panel's navigation too.

        IT NO LONGER SUBSCRIBES `NavigationStarting`. That registration was
        moved to `_arm_visibility_invariant`, called from `_on_before_show`,
        on 2026-10-06 for TICKET-55a4ab4b157bdd26bb9629c7. The reasoning it
        recorded here was correct about WHY the guard must sit on the
        CONTROL's `NavigationStarting` and not the CoreWebView2's — pywebview
        subscribes the same control event in `EdgeChrome.__init__`
        (edgechromium.py:102) and .NET raises handlers in subscription order,
        so pywebview's `form.Show()` (edgechromium.py:346-349) runs first and
        this handler runs immediately after it in the same dispatch; on a
        different forward the order is a race, and the re-assert was measured
        losing it and leaving the panel on screen. The error was the WORD
        "before the first page is loaded": this handler does not run before the
        first page is loaded, because navigation #1 is raised from inside this
        very dispatch (pywebview's `on_webview_ready` calls `load_url`,
        edgechromium.py:305-311). Keeping the registration here made the cure
        conditional on this callback arriving at all.
        """
        if not args.IsSuccess:
            log(f'WEBVIEW2_INIT_FAILED error={args.InitializationException}')
            return
        self.core = sender.CoreWebView2
        self._webview_timeline()
        self._install_bootstrap('initialization-completed')
        self._arm_lazy_gate()

    def _webview_timeline(self):
        """QUANDO e' que o WebView2 faz o que diz que faz (2026-11-03).

        MEDIDO: `PRELOAD_INSTALLED` as 03:48:48.8 e `STAGING_SEEN` as 03:49:16.3
        -- 27,5 s entre a janela existir e o `loaded` da pagina de staging, e mais
        25 s ate' o painel carregar. Sem estes marcos a proxima pergunta era um
        palpite sobre o WebView2. Cada linha leva `t=` em ms desde o arranque do
        processo, para o numero ser comparavel entre corridas.
        """
        try:
            core = self.core
            def _ms():
                return (time.monotonic() - _WEBVIEW_T0) * 1000.0

            def _nav_start(sender, args):
                log('WEBVIEW_NAV start t=%.0f uri=%s'
                    % (_ms(), str(getattr(args, 'Uri', ''))[-46:]))

            def _nav_done(sender, args):
                log('WEBVIEW_NAV done t=%.0f success=%s'
                    % (_ms(), str(getattr(args, 'IsSuccess', '?'))))

            def _dom_ready(sender, args):
                log('WEBVIEW_NAV dom t=%.0f' % _ms())

            core.NavigationStarting += _nav_start
            core.NavigationCompleted += _nav_done
            core.DOMContentLoaded += _dom_ready
            log('WEBVIEW_NAV subscribed t=%.0f' % _ms())
        except Exception as exc:              # noqa: BLE001
            log('WEBVIEW_NAV_SUBSCRIBE_FAILED error=%r' % (exc,))

    def _install_bootstrap(self, where):
        """Register the preload on the CoreWebView2, on the UI thread.

        `AddScriptToExecuteOnDocumentCreatedAsync` returns `Task[String]` in
        this binding, NOT an `IAsyncOperation`: reaching for `.Completed` on it
        raises `'Task[String]' object has no attribute 'Completed'`, which is
        exactly what the first run of this shell printed. The completion idiom
        is `ContinueWith(Action[Task[String]](...))`, which is also what
        pywebview itself uses for ExecuteScriptAsync
        (platforms/edgechromium.py:154-155).
        """
        from System import Action, String
        from System.Threading.Tasks import Task

        def _done(task):
            log(f'PRELOAD_INSTALLED where={where} status={task.Status}')

        def _add():
            self.core.AddScriptToExecuteOnDocumentCreatedAsync(
                _bootstrap_js()).ContinueWith(Action[Task[String]](_done))

        self._ui(_add)

    def _arm_lazy_gate(self):
        """Register the deferred-asset gate, on the UI thread.

        The gate is what makes `defer` possible AT ALL on a `file://` document.
        panel.html is served byte-for-byte by Chromium's file loader (see
        `file_url`), there is no HTTP server to hold an asset back, and the panel's
        CSP (`script-src 'self'` with `'unsafe-inline'` granted to style ONLY)
        forbids the blob:/data: script injection a loader could otherwise use. So
        the shell intercepts the five deferred subresource requests itself and
        answers each with an EMPTY body until the page's own loader has asked for
        the real bytes over the bridge.

        `--no-lazy` is the CONTROL ARM: with it the gate registers nothing and
        every deferred URL reaches the disk, which is exactly today's behaviour.
        The measurement harness runs both arms; if the before/after bytes do not
        move, the gate is vacuous and the harness must say so.

        The handler is subscribed to the CoreWebView2's `WebResourceRequested`,
        so it runs on the UI thread and MUST NOT call `_ui` (that would deadlock:
        the delegate it posts can only run after this handler returns). It touches
        only an in-memory set and a MemoryStream, so it is safe there.
        """
        if getattr(self, '_lazy_gate', None) is not None:
            return
        if self.core is None:
            log('PANEL_LAZY_GATE_SKIPPED reason=no-core')
            return
        if self.args.no_lazy:
            log('PANEL_LAZY_GATE_DISABLED reason=--no-lazy')
            self._lazy_gate = LazyAssetGate(self.core, enabled=False)
            return
        gate = LazyAssetGate(self.core, enabled=True)
        self._lazy_gate = gate
        if gate.registered != len(LAZY_ASSETS):
            log(f'PANEL_LAZY_GATE_PARTIAL registered={gate.registered} want={len(LAZY_ASSETS)}')
        try:
            self.core.WebResourceRequested += gate.on_resource_requested
            log(f'PANEL_LAZY_GATE_ARMED registered={gate.registered} urls={len(LAZY_ASSETS)}')
        except Exception as exc:
            log(f'PANEL_LAZY_GATE_ARM_FAILED error={exc!r}')
            self._lazy_gate = None

    def _current_document(self):
        """WHAT document the WebView2 is actually showing, or None if unknown.

        The shell must never infer this from a Python-side flag: the flag and the
        document are two different things, and every inference from the flag has
        been wrong at least once. `stage.html` is an EMPTY document (see its own
        header: "This page never paints anything"), so a window left sitting on
        it is a pure white slab — which is exactly the defect the owner reported
        as *"vejo os dois paineis branco"*.
        """
        try:
            url = self.window.get_current_url()
        except Exception as exc:  # noqa: BLE001 -- a missing answer must not
            # raise inside a load handler and take the navigation with it.
            log(f'CURRENT_URL_FAILED error={exc!r}')
            return None
        return (url or '').replace('\\', '/')

    def _arm_panel_stall_watch(self):
        """UM CARREGAMENTO QUE NAO VOLTA NAO VIRA UMA APP MORTA (2026-11-03).

        MEDIDO tres vezes nesta sessao: `STAGING_SEEN` -> `STAGING_LOADED` ->
        `PANEL_SHOW_REFUSED count=2` e mais NADA; `STARTUP_NOT_READY s=15/30/60`
        com a app sem laco de legendas, sem worker e sem hotkeys. O `load_url` do
        painel simplesmente nao voltava, e o `_on_loaded` do painel nunca corria.
        Aqui: 12 s sem o ficheiro de prontidao -> re-empurra a navegacao (e'
        idempotente); 25 s -> completa o arranque (worker, legendas, hotkeys) com
        a pagina do painel ainda pendurada, porque a legenda nao depende dela.
        """
        if getattr(self, '_panel_stall_armed', False):
            return
        self._panel_stall_armed = True

        def _watch():
            path = getattr(self.args, 'ready_file', None)
            def _ready():
                # O FICHEIRO E' DO LARGADOR E ELE APAGA-O (2026-11-03);
                # `startup_is_ready` pergunta primeiro a ESTE processo.
                return startup_is_ready(path)
            time.sleep(12.0)
            if _ready():
                return
            log('PANEL_NAV_STALL s=12 -> re-empurrar a navegacao')
            try:
                self.window.load_url(file_url(PANEL_HTML))
            except Exception as exc:          # noqa: BLE001
                log('PANEL_NAV_RETRY_FAILED error=%r' % (exc,))
            time.sleep(13.0)
            if _ready():
                return
            log('PANEL_NAV_STALL_FINAL s=25 -> completar o arranque sem o painel')
            try:
                self._complete_startup()
            except Exception as exc:          # noqa: BLE001
                log('PANEL_NAV_COMPLETE_FAILED error=%r' % (exc,))

        threading.Thread(target=_watch, name='sotto-panel-stall',
                         daemon=True).start()

    def _complete_startup(self):
        """O QUE "A APP ARRANCOU" QUER DIZER, NUM SO SITIO (2026-11-03).

        Era o fim de `_on_loaded`. Extraido porque um `load_url` que nao volta
        NAO pode deixar a app sem legenda: medido tres vezes hoje
        (`STARTUP_NOT_READY s=15/30/60`, `STAGING_LOADED` e mais nada), o
        carregamento do painel ficou preso e o laco das legendas nunca
        arrancou. O vigia do painel chama ESTE caminho, entao a app sobe com o
        que precisa mesmo que a pagina do painel fique pendurada.
        """
        _STARTUP_READY['done'] = True
        mark_launch_ready(self.args.ready_file)

        # Startup actions run ONCE per process, not once per navigation. A hot
        # reload re-enters this function; without this guard `--with-worker`
        # would spawn a SECOND worker and `--selftest` would run twice, so a
        # panel save would quietly multiply the thing the panel is for.
        if not self.startup_done:
            self.startup_done = True
            self.send_geometry()
            if self.surface_applied == 'strip':
                h_moved = self.refresh_strip_height('hot-reload')
                w_moved = self.refresh_strip_width('hot-reload')
                if h_moved or w_moved:
                    self._apply_window_geometry(self.geometry_for('strip'),
                                                reason='strip-height-hot-reload')
            # The panel AS TEXT. Armed here — once the panel document (not the
            # staging page) has loaded — so the DOM read has something to read.
            # See panel_state.py and docs/audit/painel-texto.md.
            self.start_panel_state()
            # THE VISIBILITY CHANNEL — armed BEFORE `start_worker` below, in
            # this same block, so a worker spawned on this launch always finds
            # the file. The order is the point: see `self.panel_visibility`.
            self.start_panel_visibility()
            # AS LEGENDAS E O WORKER -- IDEMPOTENTE (2026-11-03). O main()
            # ja' as arranca antes do `webview.start()`; esta chamada serve o
            # caminho em que a janela nasce tarde, e nao faz nada duas vezes.
            self.start_caption_pipeline('panel-ready')
            # THE FIRST PRESENT IS PAID HERE, OFF THE SCREEN -- see
            # `_warm_paint`. It must be BEFORE any show, or the first Alt+C
            # pays it with the window on screen (measured: 19 blank frames).
            self._warm_paint('startup')
            if self.args.show:
                self.show_panel('startup', surface='panel')
            self._measure_on_screen_visibility('startup')
            if self.args.probe_edit_mode:
                log('PANEL_EDIT_PROBE_ARMED s=2.0')
                timer = threading.Timer(2.0, self.run_edit_mode_probe)
                timer.daemon = True
                timer.start()
            # -- F1: o worker arranca por OMISSAO (o fluxo e' agora opt-OUT).
            # Ordem, do mais explicito ao menos, e o motivo vai no log
            # (`WORKER_AUTOSTART started/declined reason=…`):
            #   1. --with-worker  -> 'with-worker' (autoritativo)
            #   2. --no-worker    -> 'no-worker'
            #   3. SOTTO_NO_WORKER=1 -> 'env'
            #   4. flag de MEDICAO (--dump-dom, --selftest, --memory,
            #      --no-hotkey, --exit-after) -> 'measurement-flag(..)': essas
            #      corridas pagariam ~2 GB de modelo e abririam um tap sem precisar.
            #   5. resto          -> 'default'
            # A tabela vive em `_worker_autostart_reason` (assertivel sem WebView2).
            worker_reason = self._worker_autostart_reason(self.args)
            # EVERY path goes through `start_worker`, so a refusal takes the
            # SAME `WORKER_AUTOSTART=declined reason=…` line a silent failure
            # does and no reader has to learn a second shape. `start_worker`
            # declines by itself when a bridge already exists, and nothing
            # added here takes `self._lock`.
            #
            # THE DEFAULT IS NOW DEFERRED (owner, 2026-10-17: *"abrir ou fechar
            # o sotto causa um travamento muito forte no meu pc"*). Spawning the
            # worker here means the app's own launch pays a ~750 MB weight read
            # plus a CUDA context and ~2 GB of RSS before the desktop settles.
            # Nothing is being transcribed before the panel is opened, so the
            # load now happens on FIRST OPEN (see `show_panel`), at below-normal
            # priority, with lazy CUDA kernels. Explicit/measurement paths are
            # untouched: `--with-worker` still starts here, and a measurement
            # flag still declines.
            if worker_reason == 'default':
                if getattr(self, 'bridge', None) is not None:
                    log('WORKER_AUTOSTART=started reason=default by=startup-show')
                else:
                    # THE PRELOAD (owner, 2026-10-21: *"abrir ou fechar o
                    # sotto trava pra caralho meu pc"*). The worker used to
                    # wait for the FIRST PANEL OPEN, which meant the model
                    # loaded WHILE THE OWNER WAS WATCHING: MEASURED 36.9 s
                    # from the spawn to the worker ready on the owner's own
                    # log (`BRIDGE_LOAD_MS ms=36968 ... worker_load_s=32.59`),
                    # so the panel he had just opened sat there with no
                    # captions for the best part of a minute.
                    #
                    # THE PRELOAD MOVES THAT WAIT TO WHERE THE OWNER IS NOT
                    # WAITING: the app's start, in the background, at the
                    # worker's BELOW_NORMAL priority. The launch stays light
                    # (the timer fires after a delay, not during the window
                    # paint), and by the time he presses Alt+C the model is
                    # there. `SOTTO_NO_PRELOAD=1` puts the old behaviour
                    # back; a MEASUREMENT launch never preloads (those
                    # reasons are not 'default' and they never reach here).
                    self._schedule_preload_worker()
            else:
                self.start_worker(worker_reason)
            # -- D3: no worker means the panel must say so ------------------
            # The panel's shipped footer says "Idle · no audio source", which
            # claims the machine has no audio -- measured false (there IS audio;
            # what is missing is the PROCESS). Without F1 cured, no status ever
            # arrived either, so the claim stood for the whole session. One
            # status now, through the same path every worker status takes, so
            # both the placeholder and the footer stop claiming a wait that
            # cannot end -- and it NAMES THE FLAG, because "no worker" with the
            # flag in hand is a decision the owner can undo in one argument.
            #
            # Only the two opt-outs and a measurement flag get it: the panel the
            # owner reads must not claim a wait when the shell KNOWS there is no
            # worker. The sentence NAMES THE FLAG, because "no worker" with the
            # flag in hand is a decision he can undo in one argument -- "no audio
            # source" never said that.
            off_message = self._worker_off_message(worker_reason)
            if off_message:
                text, info = off_message
                self.apply_panel_state(text, 'error', info)
            # O PRAZO E' DO PROCESSO, NAO DO QUE ELE ESTA' A FAZER
            # (2026-11-03, MEDIDO). Este `if` vivia no FIM do despacho, depois
            # de `run_selftest()`: uma instancia largada com `--exit-after 45`
            # ficou **1 h 50 min** viva (pid 35348, `--mutex-name
            # SottoPovSelftest-altc-first-caption-59452`) porque o selftest
            # nunca voltou -- o `BRIDGE_STATS_REPLY` de 60 em 60 s e' o unico
            # sinal que ela deu. O prazo tem de ser ARMADO ANTES do trabalho,
            # ou um trabalho que nao acaba e' um prazo que nao existe. Custou
            # 245 MB (shell + o seu WebView2) durante quase duas horas.
            if self.args.exit_after:
                timer = threading.Timer(self.args.exit_after,
                                        self.request_exit, args=(0,))
                timer.daemon = True
                timer.start()
                # E a REDE: se o desligamento educado tambem ficar preso (tray,
                # bridge, WebView2), o processo sai a' forca. Uma sonda que nao
                # morre e' pior do que uma sonda que sai sem despedida.
                hard = threading.Timer(self.args.exit_after + 15.0,
                                       os._exit, args=(0,))
                hard.daemon = True
                hard.start()

            if self.args.probe_stats:
                # Long enough for the panel's own 1000 ms poll to have run
                # several times against a worker that published WORKER_STATS.
                wait = self.args.probe_stats_wait
                log(f'PANEL_STATS_PROBE_ARMED s={wait}')
                timer = threading.Timer(wait, self.run_stats_probe)
                timer.daemon = True
                timer.start()
            if self.args.probe_v2 > 0:
                timer = threading.Timer(self.args.probe_v2,
                                        self.run_panel_v2_probe)
                timer.daemon = True
                timer.start()
                log(f'PANEL_V2_PROBE_WAIT s={self.args.probe_v2}')
            elif self.args.dump_dom:
                # `--dump-dom-wait` is the difference between measuring the
                # panel and measuring the panel's STARTUP. A worker that will
                # die of a silent device spends its first seconds alive, so a
                # probe taken at t=0 photographs the warm-up and reports it as
                # the answer — which is how "the code is surfaced on the panel"
                # gets asserted without ever having seen the code.
                if self.args.dump_dom_wait > 0:
                    timer = threading.Timer(self.args.dump_dom_wait,
                                            self.run_dump_dom)
                    timer.daemon = True
                    timer.start()
                    log(f'DOMDUMP_WAIT s={self.args.dump_dom_wait}')
                else:
                    self.run_dump_dom()
            elif self.args.selftest:
                self.run_selftest()
            if self.args.probe_outside_click:
                # A short beat so the panel document has settled before the
                # three decisions are driven.
                log('OUTSIDE_CLICK_PROBE_ARMED s=2.0')
                timer = threading.Timer(2.0, self.run_outside_click_probe)
                timer.daemon = True
                timer.start()
            if self.args.memory and not self.args.memory_wait:
                self.run_memory()
            return

        # A re-navigation (hot reload): re-send geometry and keep whatever
        # visibility the owner had. The hotkey is registered by THIS process,
        # so re-navigating the page cannot lose Alt+C.
        self.send_geometry()
        log(f'HOT_RELOAD_APPLIED reload={self.reload_count} '
            f'visible={str(self.visible).lower()} '
            f'hotkey_still_registered='
            f'{str(bool(self.hotkey and self.hotkey.registered)).lower()}')
        # ── NO RE-SHOW HERE. REMOVED ON PURPOSE (2026-10-07) ──────────────────
        # This was `if self.visible: self.show_panel('hot-reload')`. The owner
        # reported *"eu to tentando tirar ele da minha tela e ele respawna"*, and
        # this call is the respawn: every time a lane saved a file under
        # `app/panel/**` the shell re-navigated and RE-MAPPED the panel — a
        # second path to the very map `_gate_form_show` exists to refuse, running
        # AFTER the navigation where nothing can order against it.
        #
        # It is also unnecessary. pywebview re-maps the form on every navigation
        # start and the gate refuses that; a window that was VISIBLE is still
        # visible after a re-navigation (the content re-renders by itself), and a
        # window that was HIDDEN must stay hidden. So the correct action is:
        # assert the state the owner chose, and never the opposite.
        #
        # NOTE FOR WHOEVER READS THE F5 RECEIPT: the machine proof of the staging
        # bounce used to include a `PANEL_SHOWN reason=hot-reload` line. That line
        # no longer appears — by design. The reload is still proved by
        # `HOT_RELOAD_APPLIED reload=N` plus the panel loading the real document
        # (the `panel-state.json` `url` and a non-negative `live.count`).
        if not self.visible:
            self._reassert_hidden()
            log('HOT_RELOAD_KEPT_HIDDEN reason=owner-had-it-hidden '
                f'reload={self.reload_count}')

    def _on_loaded(self):
        """pywebview has injected its api and a page has finished loading."""
        if self.core is None:
            # `loaded` is set from a pywebview worker thread (util.py:232), and
            # CoreWebView2 is UI-thread-affine: reading it directly raises
            # "CoreWebView2 can only be accessed from the UI thread".
            def _grab():
                if self.webview2 is not None and \
                        self.webview2.CoreWebView2 is not None:
                    return self.webview2.CoreWebView2
                return None
            grabbed = self._ui(_grab)
            # A STALL IS NOT A CORE (2026-10-20): `_ui` answers a stall with
            # a `NoAnswer`, and that must not become `self.core` -- the next
            # `ExecuteScriptAsync` would raise on a dict instead of on a
            # missing core.
            self.core = None if isinstance(grabbed, NoAnswer) else grabbed

        # ── THE BOUNCE IS DECIDED BY THE DOCUMENT, NOT BY A FLAG ───────────────
        # `stage.html` is empty, so landing on it and stopping is the white
        # slab the owner reported. Until now the decision was `if not
        # self.staged`, and `self.staged` is a Python boolean that a re-entrant
        # load can set in the wrong order: a hot reload flips it to False, the
        # in-flight panel load's handler then sets it back to True, and when
        # stage.html's own handler runs it sees True, believes the document is
        # the panel, and never bounces. The window then shows an empty page
        # forever. MEASURED 2026-10-09: after Alt+C the WebView2's own window
        # title read `stage.html — [InPrivate]` (the panel's title is `Sotto`),
        # and the strip composited 100% white with `WindowFromPoint` naming
        # Sotto's own child HWND and the desktop at 2% light.
        #
        # Asking the document which document it is removes the whole class: the
        # bounce is idempotent, so a repeated or reordered load converges on the
        # panel instead of depending on the flag happening to be right.
        here = self._current_document()
        on_stage = bool(here) and here.endswith('/stage.html')
        if on_stage:
            log(f'STAGING_SEEN document=stage.html -> bouncing to panel '
                f'staged={str(self.staged).lower()}')
            self.staged = True
            log(f'STAGING_LOADED core={"yes" if self.core else "no"} -> '
                f'navigating to panel {PANEL_HTML}')
            self.window.load_url(file_url(PANEL_HTML))
            self._arm_panel_stall_watch()
            return
        if here and not here.endswith('/panel.html'):
            # A document we do not know (an error page, a redirect): never treat
            # it as the panel, and send it home. Without this the shell would
            # silently adopt whatever Chromium decided to show.
            log(f'UNKNOWN_DOCUMENT url={here[:160]} -> bouncing to panel')
            self.window.load_url(file_url(PANEL_HTML))
            return
        if not self.staged:
            # Only reachable when the URL is unavailable AND the flag says we
            # have not bounced yet — the original path, kept for the case where
            # `get_current_url` has nothing to say.
            self.staged = True
            log('STAGING_LOADED (flag path, no url) -> navigating to panel '
                f'{PANEL_HTML}')
            self.window.load_url(file_url(PANEL_HTML))
            return
        # NOTE: `_move_into_place` (the OFFSCREEN cure) was removed 2026-10-06:
        # creating the window at -32000 broke the panel load, and its move-back
        # left the panel VISIBLE at startup (measured: PANEL_VISIBILITY_ON_SCREEN
        # visible=true). Geometry is fixed at creation instead.
        probe = self.exec_js(BRIDGE_PROBE)
        if probe and probe.get('hasSotto'):
            self.bridge_installed = True
            log(f'PRELOAD_ACTIVE hasSotto=true '
                f'methods={len(probe.get("methods", []))} '
                f'hotkey={probe.get("hotkey")} '
                f'platform={probe.get("platform")}')
        else:
            # Lost the race, or the script was rejected. Register it now and
            # reload: registration is persistent, so the SECOND parse has it.
            self.bridge_installed = False
            log('PRELOAD_ACTIVE hasSotto=false - reinstalling and reloading once')
            self._install_bootstrap('post-load-repair')
            self._ui(lambda: self.core.Reload())

        # G3: the panel navigation has just completed. That is exactly the
        # boundary the 2026-10-06 hang never crossed -- it logged
        # `STAGING_LOADED`, its `load_url(panel)` never came back, there was no
        # `PRELOAD_ACTIVE`, and run.cmd still answered 0 (launch-entry.md §3/§4).
        # run.cmd's bounded wait keys on this file (see mark_launch_ready); the
        # file appearing is the wrapper's "the app came up".
        self._complete_startup()

    def _on_closing(self):
        if self.bridge is not None:
            self.bridge.stop('closing')
        self.stop_hotkeys()
        if self.external_caption_watcher is not None:
            self.external_caption_watcher.stop()
        if self.vram_guard is not None:
            self.vram_guard.stop()
        if getattr(self, 'caption_overlay', None) is not None:
            try:
                self.caption_overlay.destroy()
            except Exception:  # noqa: BLE001
                pass
        self.stop_hot_reload('closing')
        # The diarizer dies with the SHELL, not with the worker. The worker is
        # restarted constantly by its own ladder (measured: 88 deaths in 17
        # minutes); killing a 277 MB model on every restart would be the exact
        # churn the owner complained about, and the payload the worker reads is
        # only 30 s fresh anyway, so a diarizer that outlives one restart costs
        # nothing and a diarizer that dies with it costs a reload.
        _sidecar = getattr(self, '_speaker_sidecar', None)
        if _sidecar is not None:
            _sidecar.stop('shell-closing')
        _watch = getattr(self, '_multivoice_watch', None)
        if _watch is not None:
            _watch.stop('shell-closing')
        log('SHELL_CLOSING')

    # -- UI thread marshalling --------------------------------------------
    def _ui(self, fn, timeout=UI_MARSHAL_TIMEOUT_S):
        """Run `fn` on the thread that owns the WebView2 control.

        CoreWebView2 members must be called from the UI thread; the worker
        reader thread and the hotkey thread are not it. pywebview marshals only
        its own form operations, so the host does it for itself.

        `timeout` is the budget for the marshalling wait, and it is the SAME
        clock the caller asked for (2026-10-20) -- see `exec_js`. A stall
        returns a `NoAnswer`, never a silent `None`.
        """
        from System import Func, Type  # pythonnet, loaded by pywebview

        form = self.form or self._form()
        if form is None:
            return None
        if form.InvokeRequired:
            done = threading.Event()
            box = {}

            def run():
                try:
                    box['value'] = fn()
                except Exception as exc:  # surfaced to the caller below
                    box['error'] = exc
                finally:
                    done.set()

            form.BeginInvoke(Func[Type](run))
            # THE BUDGET IS A PARAMETER (2026-10-20). It used to be a hard-coded
            # 10 s INSIDE this method, so a caller that asked `exec_js` for 5 s
            # waited 10 s HERE and then another 5 s THERE -- 15 s to learn that
            # a 5 s question had timed out. The caller and this method now
            # share ONE clock.
            if not done.wait(timeout):
                name = str(getattr(fn, '__name__', fn))
                warn('UI_THREAD_STALL begin-invoke not run in %gs fn=%s'
                     % (timeout, name))
                # THE STALL IS A VALUE, NOT A SILENT `None`. A SILENT `return
                # None` here is how a stalled UI thread became a VACUOUS
                # result in the instruments: `exec_js` then sees None, the
                # probe logs `PANEL_STATS_PROBE null`, and the check that read
                # the value fails with no reason attached to it. Measured
                # 2026-10-11: a worker publishing 43 stats pushes/s left the
                # posted callable unrun for the whole 10 s and NOTHING in the
                # log said so. Measured 2026-10-20 on the owner's own log: 93
                # of these inside ONE 50 s window, and every reader
                # downstream STILL could not tell "answered null" from
                # "never answered".
                return NoAnswer('ui-thread-stall', name, timeout)
            if 'error' in box:
                raise box['error']
            return box.get('value')
        return fn()

    def _post(self, fn):
        """Queue `fn` on the UI thread and DO NOT wait for it.

        `_ui` waits, so it must never be used from inside a UI-thread callback:
        the delegate it posts can only run once the callback that posted it has
        returned, and `_ui` would sit on `done.wait(10)` while holding the very
        thread that has to run it. This is the fire-and-forget twin, for the
        case where the POINT is to run after the current UI message ends.

        THE CALLABLE IS WRAPPED, and that is not decoration. `BeginInvoke` runs
        it on the UI thread, so anything it raises is an UNHANDLED exception in
        the message loop: WinForms answers that with
        `System.Windows.Forms.ThreadExceptionDialog` — a VISIBLE window, which
        this repo forbids, on the owner's screen, for a defect nobody asked to
        see. Measured 2026-10-08: a `NameError` in a posted callable produced
        neither a log line nor a crash, and the run looked healthy. A failure
        here is a log line, never a dialog.
        """
        from System import Func, Type  # pythonnet, loaded by pywebview

        form = self.form or self._form()
        if form is None:
            return False

        def guarded():
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                warn(f'POSTED_CALLABLE_FAILED fn={getattr(fn, "__name__", fn)} '
                     f'{type(exc).__name__}: {exc}')

        form.BeginInvoke(Func[Type](guarded))
        return True

    # -- JS execution ------------------------------------------------------
    def exec_js(self, script, timeout=10.0):
        """Evaluate `script` in the page and return its JSON-decoded value.

        Same idiom as pywebview's own evaluate_js
        (platforms/edgechromium.py:152-159): the call is made through the
        control's `Invoke` so it runs on the UI thread, and completion arrives
        on a `ContinueWith(Action[Task[String]])`. `.Completed` does not exist
        on a `Task[String]` in this binding.

        NO ANSWER IS NOT `None` (2026-10-20). Every way this can fail to get
        an answer -- the UI thread never ran the callable, the task did not
        finish, the task faulted -- returns a `NoAnswer`: FALSY (so `if value:`
        is unchanged) and JSON-serialisable (so a probe can log it), and it
        carries the REASON and WHAT WAS ASKED. Measured on the owner's own log
        (2026-10-20): 68 `exec_js TIMEOUT after 10.0s` and 93
        `UI_THREAD_STALL` inside one 50 s window, and the reader could not
        tell a null answer from no answer.
        """
        from System import Action, Func, Object, String
        from System.Threading.Tasks import Task

        box = {}
        done = threading.Event()

        def _complete(task):
            try:
                if task.IsFaulted:
                    box['error'] = repr(task.Exception)
                else:
                    box['json'] = task.Result
            except Exception as exc:
                box['error'] = repr(exc)
            finally:
                done.set()

        def _start():
            # `box['task']` existe para o CENSO, nao para o caminho: o
            # `Task.Status` e' o unico campo que separa "o renderer nunca
            # devolveu nada" de "o JS respondeu e a continuacao .NET nao entrou
            # em Python" -- ver `_task_bits` e `_main/bridge-census.py`.
            box['task'] = self.core.ExecuteScriptAsync(script)
            box['task'].ContinueWith(Action[Task[String]](_complete))

        def _run():
            self.webview2.Invoke(Func[Object](_start))

        # ONE BUDGET, NOT TWO (2026-10-20). The marshalling wait (`_ui`) and
        # the task wait were TWO separate waits, each up to `timeout`: a
        # question that timed out held the caller for 2x `timeout` -- 20 s for
        # the 10 s default `reply_stats` used, on the pump thread. The
        # deadline is computed ONCE and the two waits SHARE it.
        deadline = time.monotonic() + float(timeout)
        census = _bridge_census()
        token = census.call(script, timeout) if census is not None else None
        marshalled = None
        t_marshal = time.monotonic()
        try:
            marshalled = self._ui(_run, timeout=timeout)
        except Exception as exc:
            box['error'] = repr(exc)
            done.set()
        if token is not None:
            census.phase(token, 'marshal',
                        (time.monotonic() - t_marshal) * 1000.0)

        if isinstance(marshalled, NoAnswer):
            # THE UI THREAD NEVER RAN IT. The script is still QUEUED on the
            # form, so the answer may arrive later -- but the caller is NOT
            # going to wait for it, and the REASON is on the record.
            warn(f'exec_js STALL reason=ui-thread-stall timeout={timeout}s '
                 f'script={script[:90]!r}')
            if token is not None:
                census.no_answer(token, _task_bits(box, done))
            return marshalled

        left = deadline - time.monotonic()
        if left <= 0 or not done.wait(left):
            warn(f'exec_js TIMEOUT after {timeout}s script={script[:90]!r}')
            if token is not None:
                token['task_ms'] = round(
                    (time.monotonic() - t_marshal) * 1000.0, 1)
                census.no_answer(token, _task_bits(box, done))
            return NoAnswer('exec-js-timeout', script[:90], timeout)

        if 'error' in box:
            warn(f'exec_js failed: {box["error"]}')
            if token is not None:
                census.no_answer(token, _task_bits(box, done))
            return NoAnswer('exec-js-error', script[:90], timeout, box['error'])
        if token is not None:
            census.answer(token)
        try:
            return json.loads(box.get('json', 'null'))
        except ValueError:
            return box.get('json')

    def emit(self, kind, payload) -> bool:
        """main -> page: `emit(kind, payload)` -- POSTED, so it never waits.

        ── O QUE ESTAVA MEDIDO, e e' o defeito ────────────────────────────────
        Isto era `self.exec_js(...)`: um round trip SINCRONO com o orcamento por
        omissao de 10,0 s. As TRES chamadas de `emit` do produto -- `status`
        (`send_status`), `geometry` (`send_geometry`) e `external-caption` --
        descartam o valor de retorno: sao NOTIFICACOES. Nenhuma delas tem uma
        resposta que use, e todas correm em threads que o dono sente:

          * `status` sai do pump do worker, a MESMA thread que carrega as
            legendas (`on_worker_status` -> `_status` -> `apply_panel_state`);
          * `geometry` sai da thread da hotkey, no Alt+C;
          * `external-caption` sai da thread da faixa do YouTube.

        Medido no log vivo (`_main/webview-run.log`): **515**
        `WARN exec_js TIMEOUT after 10.0s` (`grep -c`), e nos dois ultimos
        2026-11-01 10:33:17 / 10:35:05 o script que estourou e'
        `window.__sotto_emit("status", ...)`. Em cada um desses, a thread
        chamadora ficou PRESA 10 s para entregar uma frase ao painel -- e a
        linha seguinte do log (`STATUS_APPLIED`) so' aparece 10 s depois. O
        painel nao congelava: quem congelava era o emissor.

        PORQUE UM POST NAO TEM ORCAMENTO. `_post` e' `BeginInvoke`: ou entra na
        fila do UI thread, ou nao entra -- e as duas coisas ficam escritas. A
        ORDEM em relacao aos outros scripts postados mantem-se (mesma fila), e
        a ordem entre duas notificacoes diferentes nunca foi garantida
        (`emit_async` ja' o documenta); o painel e' funcao pura do ultimo
        estado que viu.

        DEVOLVE `False` quando o form ainda nao existe. Isso NAO e' silencio:
        e' a linha `EMIT_DROPPED` abaixo, que e' o que o pedido desta lane
        exige -- uma legenda/status perdido e' uma linha de log, nunca um
        bloqueio.
        """
        posted = self.emit_nowait(kind, payload)
        if not posted:
            # UM STATUS ANTES DO FORM NAO SE PERDE -- ESPERA (2026-11-03,
            # MEDIDO). O pipeline de legendas arranca ANTES do WebView2 (`de
            # proposito`, para a legenda nao esperar o painel), e o mesmo
            # arranque publica `Starting worker...`, `boot`, `model-loading`.
            # Todos esses `emit` caiam aqui e o painel abria sem eles: o dono
            # via o painel aparecer e so' depois receber estado -- a familia
            # exacta do "carrega o background e depois a ui" que ele recusa.
            # Agora o ULTIMO valor de cada `kind` fica guardado (so' o ultimo:
            # o painel e' funcao do estado, nao de um historico) e e' entregue
            # no primeiro `emit` que passar. Tecto de 8 kinds, para um caminho
            # sem form nunca virar memoria retida.
            q = getattr(self, '_emit_pending', None)
            if q is None:
                q = self._emit_pending = {}
            if len(q) >= 8 and kind not in q:
                q.pop(next(iter(q)), None)
            q[kind] = payload
            warn(f'EMIT_DROPPED kind={json.dumps(str(kind))} '
                 f'reason=no-form queued=true '
                 f'payload={json.dumps(payload, separators=(",", ":"))[:120]!r}')
        else:
            q = getattr(self, '_emit_pending', None)
            if q:
                self._emit_pending = {}
                for _kind, _payload in q.items():
                    self.emit_nowait(_kind, _payload)
                log('EMIT_FLUSHED kinds=%d after-first-post=%s'
                    % (len(q), json.dumps(str(kind))))
        return posted

    def exec_js_post(self, script) -> bool:
        """Run `script` in the page and return IMMEDIATELY -- fire and forget.

        ── MEDIDO 2026-11-01, e e' o defeito do dono ──────────────────────────
        A primeira exibicao do painel custava **12,07 s**, e **10,0** deles eram
        UM `exec_js TIMEOUT`: `window.__sotto_emit("geometry", …)` nao respondia
        enquanto o UI thread tratava do show, e o show inteiro ficava atras dessa
        espera (`WARN exec_js TIMEOUT after 10.0s` -> `PANEL_SURFACE` ->
        `PANEL_SHOWN` na linha seguinte, no mesmo instante). O dono chamou-lhe
        *"carregar o background e mostrar, e depois carregar a ui"* com razao:
        metade do atraso era o shell a esperar por uma resposta a uma NOTIFICACAO.

        Uma notificacao nao tem resposta que se use. `ExecuteScriptAsync` e'
        arrancado no UI thread e a task NAO e' esperada, portanto nada aqui pode
        segurar a thread que mapeia a janela. Vai por `_post` (`BeginInvoke`), o
        que mantem a ORDEM em relacao a todos os outros scripts postados.
        """
        def _run():
            try:
                self.core.ExecuteScriptAsync(script)
                return True
            except Exception as exc:  # noqa: BLE001 -- uma mensagem perdida nao mata um show
                warn(f'exec_js_post failed: {exc!r}')
                return False
        try:
            return bool(self._post(_run))
        except ModuleNotFoundError as exc:
            # ANTES DO WEBVIEW2 NAO HA' PAGINA (2026-11-03). O pipeline de
            # legendas passou a arrancar antes do `webview.start` -- de
            # proposito, para a legenda nao esperar o painel --, e nesse
            # instante `pythonnet` ainda nao tem `System` carregado: o
            # `BeginInvoke` rebenta com `No module named 'System'`. Uma
            # notificacao sem pagina nao e' um defeito, e' cedo de mais;
            # fica UMA linha, nao um WARN por cada emit.
            if not getattr(self, '_js_prewebview_logged', False):
                self._js_prewebview_logged = True
                log('EXEC_JS_DEFERRED reason=no-form yet (%s)' % (exc,))
            return False
        except Exception as exc:  # noqa: BLE001
            warn(f'exec_js_post POST failed: {exc!r}')
            return False

    def emit_nowait(self, kind, payload) -> bool:
        """The ONE place that builds a `__sotto_emit` script and POSTS it.

        `emit` is this plus the `EMIT_DROPPED` line (2026-11-01: it no longer
        waits — see `emit`); `send_geometry(post=True)` is this on the show path.
        Returns False when the post could not be queued (no form yet).
        """
        return self.exec_js_post('window.__sotto_emit(' +
                                 json.dumps(kind) + ',' +
                                 json.dumps(json.dumps(payload)) + ')')

    def arm_paint_ack(self, reason) -> int:
        """Arm the page's PAINT ACK and return its ticket. NEVER WAITS.

        O mapa de uma janela e' user32 e nao pergunta nada a' pagina; este ack e'
        a pergunta. `PAINT_ACK_ARM_JS` instala `window.__sotto_paint` (idempotente,
        porque `app/panel/**` tem outro dono) e arma os DOIS `requestAnimationFrame`s
        que escrevem `window.__sotto_paint_ack = seq` depois de um paint.

        O ARM e' POSTADO pela razao medida em `exec_js_post`: um show que espera
        por um script nao e' um show, e' uma espera.
        """
        seq = int(getattr(self, '_paint_ack_seq', 0)) + 1
        self._paint_ack_seq = seq
        posted = self.exec_js_post(PAINT_ACK_ARM_JS.replace('__SEQ__', str(seq)))
        log(f'PAINT_ACK_ARM seq={seq} posted={str(posted).lower()} reason={reason}')
        return seq if posted else 0

    def wait_paint_ack(self, seq, reason) -> dict:
        """Espera, LIMITADA, pela frame que a pagina armou. Falha sempre aberta.

        `paint_ack=false` e' um FACTO medido, nunca uma razao para deixar o painel
        sem se ver: passados `PAINT_ACK_TIMEOUT_MS` de tempo de PAREDE o show
        segue. Uma leitura que nao responde (`NoAnswer`) TERMINA a espera em vez de
        repetir -- sem resposta do `exec_js` significa UI thread ocupado, que e'
        exactamente o momento em que este codigo tem de sair da frente do dono.
        """
        out = {'ack': False, 'wait_ms': 0.0, 'why': 'arm-not-posted'}
        if not seq:
            log(f'PAINT_ACK ack=false wait_ms=0 seq=0 reason={reason} '
                f'why={out["why"]} timeout_ms={PAINT_ACK_TIMEOUT_MS}')
            return out
        script = PAINT_ACK_READ_JS.replace('__SEQ__', str(seq))
        t0 = time.monotonic()
        deadline = t0 + (PAINT_ACK_TIMEOUT_MS / 1000.0)
        out['why'] = 'timeout'
        while True:
            left = deadline - time.monotonic()
            answer = self.exec_js(
                script, timeout=max(0.05, min(left, PAINT_ACK_JS_TIMEOUT_S)))
            if isinstance(answer, NoAnswer):
                out['why'] = 'ui-thread-busy'
                break
            if str(answer) == '1':
                out['ack'] = True
                out['why'] = 'painted'
                break
            left = deadline - time.monotonic()
            if left <= 0:
                break
            time.sleep(min(PAINT_ACK_POLL_S, left))
        out['wait_ms'] = round((time.monotonic() - t0) * 1000.0, 1)
        log('PAINT_ACK ack=%s wait_ms=%s seq=%s reason=%s why=%s timeout_ms=%s'
            % (str(out['ack']).lower(), out['wait_ms'], seq, reason,
               out['why'], PAINT_ACK_TIMEOUT_MS))
        return out

    def send_status(self, text, kind=''):
        """Status wire: `{'text': <str>, 'kind': <str>}` — F8 + D3, frozen.

        `docs/audit/auditoria-completa-20261007.md` F8: the bridge already HAS
        the severity (`WorkerBridge` classifies every worker status) and the
        panel threw it away and re-classified the sentence with a regex, so two
        classifiers decided one status and the panel's guess is the one the
        owner sees. The kind now travels WITH the text, as an OBJECT, through
        the existing `emit('status', …)` path — one source of truth. The object
        is plain JSON-serializable strings and nothing more; `panel.js` (other
        lane) reads `.kind` when it is there and falls back to the sentence.
        The page side tolerates a bare string too, so a stale shell cannot
        break a panel that has already been updated.
        """
        self.last_status = text
        self.emit('status', {'text': str(text), 'kind': str(kind or '')})

    def send_geometry(self, post=False):
        """Tell the page where the window is.

        `post=True` is for the show path: the call becomes fire-and-forget
        (`exec_js_post`) instead of a 10,0 s-capable wait. The measured receipt
        is in `exec_js_post` -- this is the exact emit that timed out for 10,0 s
        inside one Alt+C on 2026-11-01.
        """
        if post:
            return self.emit_nowait('geometry', self.geometry)
        self.emit('geometry', self.geometry)

    # -- panel state -------------------------------------------------------
    def apply_panel_state(self, text, kind='busy', info=None):
        """main.js::applyPanelState — the footer line AND the placeholder.

        panel.html ships the placeholder hardcoded as "Waiting for audio", which
        on this host is a claim that is measured false, so the headline has to
        follow the real state. Done with the same class names panel.js already
        queries, which is what lets the panel files stay untouched.
        """
        line = str(text or '').strip()
        if not line:
            log('bridge status rejected: empty text would leave the stale line '
                'in place')
            return False

        # The SAME kind travels to the page twice, deliberately: in the status
        # object (`send_status`, which `panel.js` reads) and in the placeholder
        # write below, which is the shell's own direct paint of the severity.
        # One value, both readers — see `send_status` for why the panel must not
        # re-classify the sentence with a regex.
        self.send_status(line, kind)
        info = info or {}
        title = str(info.get('title') or '')
        body = str(info.get('body') or '')
        script = (
            '(() => {'
            '  const title = ' + json.dumps(title) + ';'
            '  const body = ' + json.dumps(body) + ';'
            '  const kind = ' + json.dumps(kind) + ';'
            "  const t = document.querySelector('.captions__placeholder-title');"
            "  const b = document.querySelector('.captions__placeholder-body');"
            '  if (t && title) t.textContent = title;'
            '  if (b && body) b.textContent = body;'
            "  const s = document.getElementById('status');"
            "  if (s) { s.classList.toggle('status--live', kind === 'live');"
            "           s.classList.toggle('status--error', kind === 'error');"
            "           s.classList.toggle('status--noaudio', kind === 'no-audio'); }"
            "  return t ? t.textContent : '';"
            '})()')
        # POSTED, NOT AWAITED (2026-11-01). Esta era a SEGUNDA metade do mesmo
        # defeito: `apply_panel_state` fazia `send_status` (`emit`, sincrono) e
        # DEPOIS este `exec_js`, sincrono, com 10 s cada -- ate' 20 s de pump do
        # worker por um status. O valor lido era usado para UMA linha de log
        # (`PLACEHOLDER_APPLIED title=`), e' o que a medição mostrou: 29
        # `exec_js TIMEOUT` com o script `const title = ""; const body = ""` no
        # log do dono. Uma escrita que compra uma linha de log nao pode custar
        # 10 s da thread que carrega as legendas -- a linha passa a dizer o que
        # se ESCREVEU (`posted=true`), que e' um facto do mesmo tamanho.
        posted = self.exec_js_post(script)
        if posted:
            if title:
                log(f'PLACEHOLDER_APPLIED title={json.dumps(title)} posted=true')
        else:
            warn(f'PLACEHOLDER_DROPPED title={json.dumps(title)} reason=no-form')
        return True

    def note_caption_observed(self, payload):
        payload = payload or {}
        log(f'CAPTION_OBSERVED text={json.dumps(str(payload.get("text", "")))}')

    def note_status_observed(self, text):
        log(f'STATUS_OBSERVED text={json.dumps(str(text))}')

    # -- the panel as TEXT -------------------------------------------------
    def panel_state_snapshot(self, reason='periodic'):
        """Everything the panel shows NOW, as plain data — see panel_state.py.

        Called by the writer thread every `PANEL_STATE_INTERVAL_S` and on the
        request sentinel. The DOM half is read over the SAME `exec_js` seam the
        probes use — the read a screenshot makes, in text — and the worker half
        is the bridge's own already-held state. Nothing here starts a process or
        a window, and nothing here changes what the owner sees.
        """
        # THE DOM READ IS A POST, NOT A ROUND TRIP (2026-10-20). It used to
        # be `exec_js(PANEL_STATE_PROBE, timeout=5.0)`, and `exec_js` waits on
        # the UI thread: a busy UI thread held the WRITER for 5 s there and
        # another 10 s inside `_ui` (two waits, one budget -- the bug fixed
        # above), and the callable it posted stayed QUEUED on the form, so a
        # dump every 2 s grew the WinForms queue for as long as the UI thread
        # was busy.
        #
        # Now the read is a POST with AT MOST ONE outstanding: while a read is
        # in flight the next dump does not post another one, and the dump
        # reports the LAST value it has, with its age and whether a newer one
        # is on the way. The FILE keeps being written every 2 s -- the dump is
        # not sacrificed, it stops being able to TRAVA.
        if self.core is not None:
            self._request_panel_dom()
        lock = getattr(self, '_panel_dom_lock', None)
        if lock is None:
            lock = self._panel_dom_lock = threading.Lock()
        with lock:
            dom = getattr(self, '_panel_dom_value', None)
            dom_at = getattr(self, '_panel_dom_at', 0.0)
            dom_pending = getattr(self, '_panel_dom_pending', False)
            dom_reason = getattr(self, '_panel_dom_reason', '')
            dom_detail = getattr(self, '_panel_dom_detail', None)
        dom_age = (time.monotonic() - dom_at) if dom_at else None
        bridge = self.bridge
        worker = bridge.snapshot() if bridge is not None else None
        # THE STATUS OBJECT, not just its text. `panel.js:2896-2903` blanks
        # `#status-text` for every state that is not an error (the owner ruled
        # 2026-10-08, verbatim: "tira o 'receiving captions'. deixa so um icone
        # dinamico"), so on the live path the text is '' and the ONLY signal that
        # captions are arriving is the `status--live` class on `#status` --
        # which the probe already reports as `kind` and which this line used to
        # throw away. Reading the text alone made the literal
        # 'Receiving captions' test below DEAD on the live path, so the
        # precedence fell through to the worker's no-audio latch and the panel
        # named itself `no-audio` while captions were demonstrably flowing
        # (measured live 2026-10-12: namedState="no-audio" in the same write as
        # panel.live.count=201 and panel.status={"kind":"live","text":""}).
        panel_status_obj = (dom or {}).get('status') or {}
        panel_status = panel_status_obj.get('text')
        panel_kind = panel_status_obj.get('kind')
        return {
            'namedState': self._named_panel_state(worker, panel_status, panel_kind),
            'panel': dom,
            # WHY the DOM half is what it is: its age, whether a newer read is
            # on the way, and the reason of the last failure. A dump that
            # cannot say this is a dump that lies about being fresh.
            'panelDom': {
                'ageSeconds': round(dom_age, 3) if dom_age is not None else None,
                'pending': dom_pending,
                'reason': dom_reason,
                'detail': dom_detail,
            },
            'shell': {
                'visible': self.visible,
                'hotkey': self.args.hotkey,
                'rendererReady': self.renderer_ready.is_set(),
                'bridgeInstalled': self.bridge_installed,
                'lastStatus': self.last_status,
                'captionLogCount': len(self.caption_log),
                'reloadCount': self.reload_count,
                'workerPath': self.args.worker,
                'log': getattr(_LOG_FILE, 'name', None),
                'hotReload': self.hot_reload is not None,
            },
            # The visibility channel, as data, beside the two facts it is built
            # from: `shell.visible` (the window, this instant) and the file the
            # worker polls. A reader comparing them can see the channel drift or
            # refuse it; a reader that trusts only the file cannot.
            'panelVisibility': self.panel_visibility_snapshot(),
            # Is the RUNNING code the code on disk? Both files, as data, with
            # the digest the worker was spawned from -- the question a reader
            # cannot answer from the file alone.
            'code': self._reload_policy.state(),
                'meterPushes': self.meter_pushes,
                'statsPushes': self.stats_pushes,
            'worker': worker,
        }

    def _request_panel_dom(self):
        """Ask the page for the panel's DOM -- WITHOUT waiting for it.

        Returns True when a read was POSTED, False when one is already in
        flight (or the form is gone). AT MOST ONE read is outstanding, ever:
        that is the bound the DIAGNOSTIC channel needs, and the product does
        not.
        """
        lock = getattr(self, '_panel_dom_lock', None)
        if lock is None:
            lock = self._panel_dom_lock = threading.Lock()
        with lock:
            if getattr(self, '_panel_dom_pending', False):
                return False
            self._panel_dom_pending = True
        try:
            queued = self._post(self._read_panel_dom)
        except BaseException:
            with lock:
                self._panel_dom_pending = False
            raise
        if queued is False:
            with lock:
                self._panel_dom_pending = False
            return False
        return True

    def _read_panel_dom(self):
        """Read the panel's DOM ON THE UI THREAD, and keep the result."""
        from System import Action, Func, Object, String
        from System.Threading.Tasks import Task

        def _complete(task):
            value = None
            reason = ''
            detail = None
            try:
                if task.IsFaulted:
                    reason = 'exec-js-error'
                    detail = repr(task.Exception)
                else:
                    value = json.loads(task.Result)
            except Exception as exc:  # noqa: BLE001
                reason = 'exec-js-error'
                detail = repr(exc)
            lock = getattr(self, '_panel_dom_lock', None)
            if lock is None:
                lock = self._panel_dom_lock = threading.Lock()
            with lock:
                self._panel_dom_value = value
                self._panel_dom_at = time.monotonic()
                self._panel_dom_pending = False
                self._panel_dom_reason = reason
                self._panel_dom_detail = detail

        try:
            self.webview2.Invoke(Func[Object](
                lambda: self.core.ExecuteScriptAsync(PANEL_STATE_PROBE).ContinueWith(
                    Action[Task[String]](_complete))))
        except Exception as exc:  # noqa: BLE001
            lock = getattr(self, '_panel_dom_lock', None)
            if lock is None:
                lock = self._panel_dom_lock = threading.Lock()
            with lock:
                self._panel_dom_pending = False
                self._panel_dom_reason = 'exec-js-error'
                self._panel_dom_detail = repr(exc)
            warn(f'PANEL_STATE_DOM_FAILED error={exc!r}')

    @staticmethod
    def _named_panel_state(worker, panel_status, panel_kind=None):
        """One name for "what is the panel showing", by a STATED precedence.

        The panel's OWN footer wins while it is live — `panel.js` writes
        `Receiving captions` the moment a caption commits — because that is the
        sentence the owner reads. Below it fall the worker's failure vocabulary,
        then the bridge's own no-audio verdict. `no-worker` is a real state, not
        an empty string: a panel with no bridge is not the same panel as one
        holding a quiet worker.
        """
        # TWO LIVE SIGNALS, because the sentence is no longer one of
        # them. `panel.js:2896-2903` writes
        # `setStatus('Receiving captions', 'live')` and then BLANKS
        # `#status-text`, because the healthy state is an ICON and not a
        # phrase (owner, 2026-10-08). So the literal comparison below is kept
        # for a panel that still paints the phrase, and `kind == 'live'` is
        # the one that actually fires: it is the `status--live` class
        # `panel.js:2907` puts on `#status` the instant a caption commits,
        # and it is what `PANEL_STATE_PROBE` already reports.
        if panel_status == 'Receiving captions' or panel_kind == 'live':
            return 'receiving'
        if worker is None:
            return 'no-worker'
        pending = worker.get('pendingError') or {}
        if pending.get('state'):
            return str(pending['state'])
        state = str(worker.get('state') or '')
        if state in WORKER_ERROR_STATES:
            return state
        if worker.get('noAudio'):
            return NO_AUDIO_STATE
        return state or 'idle'

    def start_panel_visibility(self):
        """Arm the visibility channel. Idempotent per process.

        The observer is the WINDOW, read at call time: `window_visible(hwnd)` is
        the same `IsWindowVisible` every other visibility decision in this file
        is built from, so the file and the screen cannot disagree by
        construction. When there is no window yet the answer is False and the
        first real window is a transition — which is exactly the fact the worker
        needs (nothing on screen yet => nothing to go live for).
        """
        if self.panel_visibility is not None:
            return False
        self.panel_visibility = PanelVisibilityWriter(
            path=PANEL_VISIBILITY_PATH,
            observe=self.observe_panel_visible,
            log=log,
            interval_s=PANEL_VISIBILITY_INTERVAL_S,
            extra=self.geometry_snapshot,
            shed_provider=self.shedding_level,
            park_provider=self.engine_park_reason,
        )
        return self.panel_visibility.start()

    def observe_panel_visible(self) -> bool:
        """The LIVE answer: is the panel window on screen right now?"""
        hwnd = self.hwnd
        return bool(window_visible(hwnd)) if hwnd else False

    def publish_panel_visibility(self, reason):
        """Record a visibility transition the moment it happens.

        Called from the SHOW/HIDE calls themselves, so the file changes within
        the same instant as the window rather than up to `interval_s` later: a
        worker that is being switched by this file must not be told "hidden" a
        tick after the owner pressed Alt+C. Silent when the arm was never made
        (a measurement run that never loaded the panel) — the cadence writer is
        the only other writer, and it takes the same path.
        """
        writer = self.panel_visibility
        if writer is None:
            return False
        return writer.write(reason)

    def panel_visibility_snapshot(self):
        """The channel as DATA, for the panel-state dump and for probes."""
        writer = self.panel_visibility
        if writer is None:
            return None
        return {
            'path': PANEL_VISIBILITY_PATH,
            'visible': writer.visible,
            'since_ms': writer.since_ms,
            'reason': writer.reason,
            'transitions': writer.transitions,
            'writes': writer.writes,
            'errors': writer.errors,
        }

    def isolated_state_path(self, path):
        """`path` with the process's private mutex in it, for MEASUREMENT runs.

        MEDIDO 2026-11-01: uma instância largada com `--mutex-name SottoPovSelftest`
        (o caminho sancionado para medir o POV sem tocar na app do dono) escreveu
        `PANEL_STATE_WRITER path=H:\\sotto\\_main\\panel-state.json` e publicou
        `producerPid=46144` no MESMO ficheiro que a instância dele usa. Uma
        medição nao pode sobrescrever o estado vivo da app -- o dono lê esse
        ficheiro e o worker decide por ele. O lock privado já isola o processo;
        o estado agora isola-se com ele, no mesmo nome, e o log diz `isolated=true`
        para o leitor saber qual dos dois ficheiros está a ler.

        A instância normal (mutex por omissão) devolve o caminho de sempre,
        byte a byte: nenhum instrumento existente muda de sítio.
        """
        mutex = str(getattr(self.args, 'mutex_name', '') or '')
        if not mutex or mutex == DEFAULT_MUTEX_NAME:
            return path
        stem, ext = os.path.splitext(path)
        safe = re.sub(r'[^A-Za-z0-9_.-]', '_', mutex)
        return '%s.%s%s' % (stem, safe, ext)

    def start_panel_state(self):
        """Arm the periodic + on-request dump. Idempotent per process."""
        if self.panel_state is not None:
            return False
        path = self.isolated_state_path(PANEL_STATE_PATH)
        self.panel_state = panel_state.PanelStateWriter(
            path=path,
            request_path=path + '.request',
            snapshot=self.panel_state_snapshot,
            log=log,
            interval_s=PANEL_STATE_INTERVAL_S,
        )
        return self.panel_state.start()

    # -- history: the "redux" store, on disk --------------------------------
    # Layout: `<root>/<YYYY-MM-DD>/<HH>.md` — a 24 h folder, one file per hour,
    # appended as captions commit. The shell owns the path (the panel is handed
    # the entry back), so the folder convention lives in exactly one place.
    def history_root(self):
        """The history store's root, and whether a canonical producer exists.

        FROZEN SHAPE (other lanes read it): `{'root': <path>,
        'canonicalProducer': None}`.

        `canonicalProducer` is `None` because of the audit's **F2**
        (`docs/audit/auditoria-completa-20261007.md`): `app/panel/
        history-source.js:51` accepts a canonical line only when its meta
        carries `producer === 'redux'`, and NO engine in this repo ever stamps
        `producer` — the live path builds its meta with three literal keys
        (`caption-formulation.js:408`), and the batch engine that could stamp it
        (Parakeet Redux) is neither on disk nor called. So the transcript cannot
        fill: the feed is decorative and the search has nothing to search. The
        shell says so HERE, as data, instead of the panel inferring it from an
        empty list; `panel.js` (other lane) uses it to collapse the feed and
        disable the search. It becomes a producer NAME only if a production
        call site starts stamping one.
        """
        return {'root': HISTORY_ROOT, 'canonicalProducer': None}

    def _history_path_for(self, when):
        return os.path.join(
            HISTORY_ROOT,
            time.strftime('%Y-%m-%d', when),
            time.strftime('%H', when) + '.md',
        )

    @staticmethod
    def _history_provenance(options):
        """The `<!-- route=… start=… reason=… -->` suffix for one line (M8).

        WHY IT EXISTS: `formulate()` appends terminal punctuation to every line
        the renderer commits, so a fragment the panel abandoned after 1500 ms
        and a sentence the worker actually closed were byte-identical in this
        file. The route is what tells them apart; `start` is the worker's own
        line identity (`worker/sotto_worker.py:_event`), so a line here can be
        lined up with the worker's `start=` in its JSONL, and `reason` is the
        rule that fired at the instant of the write.

        It is written ON the line, and NOT into `entry['text']`: the feed and
        the search show the sentence, the file carries the provenance.
        """
        if not isinstance(options, dict):
            return ''
        route = str(options.get('route') or '').strip()
        if route not in HISTORY_ROUTES:
            return ''
        parts = [f'route={route}']
        start = options.get('start')
        if isinstance(start, (int, float)) and not isinstance(start, bool):
            parts.append(f'start={float(start):.2f}')
        # WHICH branch decided the route (M9). Written AFTER `start=` so every
        # existing `route=… start=…` reader keeps its capture. `src=fallback`
        # is the de-landing announcing itself (P1 `4fb5b25380cbc8269977e22e`).
        src = str(options.get('routeSource') or '').strip()
        if src in HISTORY_ROUTE_SOURCES:
            parts.append(f'src={src}')
        reason = re.sub(r'\s+', ' ', str(options.get('reason') or '')).strip()
        if reason:
            parts.append(f'reason={reason}')
        return ' <!-- ' + ' '.join(parts) + ' -->'

    @staticmethod
    def _history_last_body(path):
        """O `text` da ULTIMA linha do ficheiro, sem hora e sem proveniencia.

        A linha gravada e `- [HH:MM:SS] frase <!-- route=... -->` (ver
        `_history_provenance`). Para comparar frases, e preciso tirar as duas
        pontas -- senao duas linhas iguais nunca seriam iguais.
        """
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                last = None
                for line in handle:
                    if line.strip():
                        last = line.rstrip('\r\n')
        except OSError:
            return None
        if not last:
            return None
        body = re.sub(r'\s*<!--.*?-->\s*$', '', last)
        match = re.match(r'^- \[\d{2}:\d{2}:\d{2}\] (.*)$', body)
        return (match.group(1) if match else body).strip()

    def history_append(self, text, options=None):
        """Append ONE committed caption. Returns the entry as written, or None."""
        body = re.sub(r'\s+', ' ', str(text or '')).strip()
        if not body:
            return None
        # HISTORICO-VS-REDUX GUARD — OWNER 2026-10-06: the transcript carries
        # ONLY a line the WORKER closed (`route=final`). The panel already
        # declines a `provisional-draft` (panel.js `recordHistory`); this is the
        # same invariant at the store, so no other caller can put the LIVE
        # caption in the owner's transcript. The LIVE caption stays in the box.
        # See docs/audit/historico-vs-redux.md.
        if isinstance(options, dict) and str(options.get('route') or '').strip() == 'provisional-draft':
            return None
        now = time.localtime()
        path = self._history_path_for(now)
        # B5 (dono, verbatim: *"coisa duplicada"*): a MESMA linha nao entra duas
        # vezes seguidas. Medido no painel de 2026-10-23: `live.count=2` com duas
        # `[committed]` identicas -- `'Seems more expensive than using Opus 55.'`.
        # Compara-se so com a ULTIMA linha do ficheiro: uma frase repetida horas
        # depois e outra frase, e continua a entrar.
        if self._history_last_body(path) == body:
            log('HISTORY_DUPLICATE_SKIPPED time=%s bytes=%d'
                % (time.strftime('%H:%M:%S'), len(body.encode('utf-8'))))
            return None
        entry = {
            'date': time.strftime('%Y-%m-%d', now),
            'hour': time.strftime('%H', now),
            'time': time.strftime('%H:%M:%S', now),
            'text': body,
            'path': path,
        }
        provenance = self._history_provenance(options)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'a', encoding='utf-8') as handle:
                handle.write(f'- [{entry["time"]}] {body}{provenance}\n')
        except OSError as exc:  # noqa: BLE001 -- a write miss must not kill the app
            warn(f'HISTORY_APPEND_FAILED path={json.dumps(path)} error={exc!r}')
            return None
        log(f'HISTORY_APPEND path={json.dumps(path)} time={entry["time"]} '
            f'bytes={len(body.encode("utf-8"))}')
        return entry

    def _history_files(self):
        """Every hour file under the root, OLDEST first: [(date, hour, path)]."""
        out = []
        try:
            days = sorted(name for name in os.listdir(HISTORY_ROOT)
                          if HISTORY_DAY_RE.match(name))
        except OSError:
            return out
        for day in days:
            folder = os.path.join(HISTORY_ROOT, day)
            try:
                hours = sorted(name for name in os.listdir(folder)
                               if name.endswith('.md'))
            except OSError:
                continue
            for name in hours:
                out.append((day, name[:-3], os.path.join(folder, name)))
        return out

    def _history_read(self, path):
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                return handle.read().splitlines()
        except OSError as exc:  # noqa: BLE001 -- an unreadable hour is skipped
            warn(f'HISTORY_READ_FAILED path={json.dumps(path)} error={exc!r}')
            return []

    def _history_entries(self):
        """NEWEST-first stream of entries. Reverse file order AND line order, so
        a `tail()` really returns the last N written, not the first N of the
        newest file."""
        for day, hour, path in reversed(self._history_files()):
            for line in reversed(self._history_read(path)):
                match = HISTORY_LINE_RE.match(line)
                if match:
                    # The provenance comment is the FILE's, not the feed's:
                    # strip it so search and the feed still see the sentence
                    # (M8 — see `_history_provenance`).
                    yield {'date': day, 'hour': hour, 'time': match.group(1),
                           'text': HISTORY_TAIL_RE.sub('', match.group(2)).strip(),
                           'path': path}

    def history_tail(self, limit=400):
        limit = max(1, int(limit))
        entries = []
        for entry in self._history_entries():
            entries.append(entry)
            if len(entries) >= limit:
                break
        entries.reverse()  # back to oldest-first for the feed
        return {'entries': entries, 'root': HISTORY_ROOT}

    def history_search(self, query, limit=200):
        """THE SEARCH. Owner, 2026-10-18: *"eu quero que ele ache"*.

        WAS, in full:
            needle = str(query or '').strip().lower()
            if needle in entry['text'].lower():

        That is byte equality with a fold the pt-BR keyboard does not perform, and
        it is why the owner had stopped trusting the box. The three layers live at
        module scope above (`search_match_rank`), so an oracle can call the
        predicate without standing up the whole shell.

        RANKING IS THE FEATURE. Three buckets, filled in ONE pass over the stream,
        then concatenated: literal, then phonetic, then fuzzy. Within a bucket the
        newest-first order of `_history_entries()` is preserved, so a typo'd query
        does not bury the newest true match under the oldest.

        EACH BUCKET IS CAPPED SEPARATELY, AND NOT AT THE SAME NUMBER. See
        `SEARCH_LAYER_CAPS`: the phonetic layer returns 172 candidates for `maca` on
        this box's own 2 077-line store, because `mais`/`faca`/`massa` are all M200
        next to `maca`. Capping the merged list at `limit` (as an earlier draft did)
        let that flood push the literal hits off the end -- a search that hides its
        own best answer once the store gets noisy. Caps are per layer, applied in
        stream order, so the newest `limit` literals always survive and the loose
        layers can only ever add a bounded tail.

        `match` is carried on each hit so the UI can say WHY a line matched instead
        of presenting a fuzzy guess with the same confidence as an exact phrase.
        """
        folded_query = search_fold(query).strip()
        query_words = folded_query.split()
        cap = max(1, int(limit))
        caps = [search_layer_cap(r, cap) for r in (0, 1, 2)]
        buckets = ([], [], [])     # 0 literal, 1 phonetic, 2 fuzzy
        if query_words:
            for entry in self._history_entries():
                rank = search_match_rank(entry['text'], folded_query, query_words)
                if rank < 0:
                    continue
                bucket = buckets[rank]
                if len(bucket) < caps[rank]:
                    bucket.append(dict(entry, match=('literal', 'phonetic', 'fuzzy')[rank]))
                if all(len(b) >= c for b, c in zip(buckets, caps)):
                    # Every bucket is at its own cap: no later entry can enter the
                    # result set at ANY rank, because buckets fill in stream order.
                    break
        hits = buckets[0] + buckets[1] + buckets[2]
        return {'query': query, 'hits': hits, 'root': HISTORY_ROOT}

    def reply_history(self, history_id, payload):
        self.exec_js(f'window.__sotto_history({json.dumps(history_id)}, '
                     f'{json.dumps(json.dumps(payload))})')

    def reveal_in_folder(self, path):
        """Open the OS file manager at the entry's FILE, or at the root.

        `explorer /select,"<file>"` for a file, `explorer "<dir>"` for a folder.
        CREATE_NO_WINDOW is mandatory: a helper that flashes a console on the
        owner's desktop is the exact defect this house refuses. A path outside
        the history root is REFUSED rather than opened — a reveal that can be
        pointed anywhere is a foot-gun, even from a trusted page.
        """
        raw = str(path or '').strip().strip('"')
        root_real = os.path.abspath(HISTORY_ROOT)
        if raw:
            target = os.path.abspath(raw)
            # Compare CASE-INSENSITIVELY (normcase) but keep the ORIGINAL case
            # for the command and the log: Explorer is case-insensitive, and a
            # lower-cased path in the receipt reads like a different folder.
            root_key = os.path.normcase(root_real)
            key = os.path.normcase(target)
            if key != root_key and not key.startswith(root_key + os.sep):
                warn(f'REVEAL_REFUSED path={json.dumps(raw)} '
                     f'reason=outside-history-root')
                return False
        else:
            target = root_real
        if not os.path.exists(target):
            warn(f'REVEAL_MISSING path={json.dumps(target)}')
            return False
        is_file = os.path.isfile(target)
        shown = os.path.normpath(target)
        command = (f'explorer /select,"{shown}"' if is_file
                   else f'explorer "{shown}"')
        try:
            subprocess.Popen(command, creationflags=CREATE_NO_WINDOW)
        except OSError as exc:  # noqa: BLE001 -- report, never crash the panel
            warn(f'REVEAL_FAILED path={json.dumps(shown)} error={exc!r}')
            return False
        log(f'REVEAL_IN_FOLDER path={json.dumps(shown)} select={str(is_file).lower()}')
        return True

    # -- pointer -----------------------------------------------------------
    def set_pointer_interactive(self, active):
        """Interactive while the mouse is over a control; click-through after.

        F9 (`docs/audit/auditoria-completa-20261007.md`, `sotto_webview.py:
        1474-1476`): `_on_before_show` puts `WS_EX_NOACTIVATE` on the window and
        `show_panel` shows it with `SW_SHOWNOACTIVATE`, which is RIGHT for
        appearance -- Alt+C must not steal focus from whatever the owner is
        typing into. It was WRONG for the interactive state: a `WS_EX_NOACTIVATE`
        window is not brought to the foreground by a click either, so the panel
        could never take keyboard focus at all and its `<input type="search"
        id="search-input">` could never receive a character -- typing with the
        panel in front sent the keys to the app BEHIND it. Both bits are now
        cleared on entry and restored on leave, so the only moment the panel can
        be activated is the moment the owner has his mouse on one of its
        controls. `show_panel`'s `SW_SHOWNOACTIVATE` is untouched: appearing
        still steals nothing.
        """
        if self.hwnd is None:
            return False
        click_through = not active
        # `noactivate` is the flag the page-side drive reads back; it is False
        # exactly while the pointer is over a control. Both calls take the
        # same value on Windows' side (`& ~flag` and `| flag`), so this is one
        # state change expressed in two styles, never two competing ones.
        try:
            if active:
                set_ex_style(self.hwnd, remove=WS_EX_NOACTIVATE)
            else:
                set_ex_style(self.hwnd, add=WS_EX_NOACTIVATE)
        except Exception as exc:  # noqa: BLE001 -- report, never kill the panel
            log(f'POINTER_INTERACTIVE_STYLE_FAILED error={exc!r}')
        make_click_through(self.hwnd, click_through)
        self.pointer_interactive = bool(active)
        log(f'POINTER_INTERACTIVE active={str(bool(active)).lower()} '
            f'click_through={str(click_through).lower()} '
            f'noactivate={str(not active).lower()}')
        return True

    # -- show / hide -------------------------------------------------------
    def _on_navigation_start(self, sender, args):
        """The panel is about to navigate: pywebview is about to SHOW it.

        `edgechromium.py:345-349` does, on every navigation start:

            if self.pywebview_window.transparent:
                self.form.Show()
                self.form.Activate()

        That hack is what makes a transparent WebView2 window paint at all
        ("no idea why this works"), and it is TRANSPARENT-BY-DEFAULT here, so
        it silently undoes `hidden=True`: measured 2026-10-06, the panel came
        up on screen with `PANEL_VISIBILITY_AT_STARTUP visible=false` (the
        `hidden` dance did leave it hidden) and `PANEL_VISIBILITY_ON_SCREEN
        visible=true`, on the owner's desktop, while `run.cmd` promises "start
        hidden". The census named the pid: `_main/panel-startup-visibility.log`.

        The hack is left alone — it is load-bearing — and the shell's own
        INTENT is re-asserted right after it, TWICE:

          * synchronously, which is the tight one: .NET raises the handlers of
            one event in subscription order and pywebview subscribed while the
            form was being built, so this handler runs AFTER its Show() and
            closes the window inside the same dispatch;
          * and POSTED, which is the one that cannot be wrong: the posted
            delegate runs once every handler of this event has returned, so it
            covers the other order too.

        MEASURED 2026-10-06: this pair is NOT the cure. `_main/
        panel-startup-flash-census.py` samples the shell's OWN pid tree every
        25 ms over 20 launches, and with BOTH halves in place the window was
        still caught on screen in **11 of 20 launches, longest 57.7 ms**. The
        pair SHORTENS the flash; it does not close it, because both halves run
        on a DIFFERENT event than the `Show()` they are undoing.

        The OFF-SCREEN creation that was meant to CLOSE it (`x=OFFSCREEN`,
        `OFFSCREEN = -32000`) was tried and REMOVED the same day: a window
        created at -32000 never finishes the WebView2 panel navigation, so the
        shell hung after STAGING_LOADED, `PRELOAD_ACTIVE`/`WORKER_AUTOSTART`
        were never reached and the app produced NOTHING — the flash was traded
        for a dead app, and the move-back left the panel VISIBLE at startup
        anyway (`PANEL_VISIBILITY_ON_SCREEN visible=true`). See the note in
        So this handler is the SECOND net, not the first: it hides the window
        the instant a navigation Shows it, and it does nothing when the owner
        asked for the panel (`--show`, or Alt+C).

        CORRECTED 2026-10-07. This paragraph used to end "It SHORTENS the flash;
        it does not close it", and that was measured true of the re-assert
        ALONE. The map itself is now refused before it happens: `_gate_form_show`
        (installed from `_on_before_show`) replaces the form INSTANCE's `Show`
        with a guard, so pywebview's `self.form.Show()` at full opacity never
        runs unless the owner asked. Measured by
        `_main/panel-startup-flash-census.py` at a 25 ms cadence, N=20 per arm:
        `_main/receipt-20261007-panel-startup-flash.md`. The closed form is kept
        because it is still the only net if the gate is ever removed, and
        because a `Show` from anywhere OTHER than that Python call would still
        be caught here.
        """
        if self.args.show or self.visible:
            return
        self._reassert_hidden()
        self._post(self._reassert_hidden)

    def _reassert_hidden(self):
        """Put the panel away if nobody asked for it, and say so in the log."""
        hwnd = self.hwnd
        if not hwnd or self.args.show or self.visible:
            return
        if not window_visible(hwnd):
            return
        hide_window(hwnd)
        log(f'PANEL_VISIBILITY_REASSERTED reason=navigation '
            f'visible={str(window_visible(hwnd)).lower()}')
        # A hide the owner did NOT ask for is still a hide, and the worker's
        # stack law is about the screen, not about intent. Published here so the
        # file cannot lag the window on this path either; the cadence writer
        # would otherwise catch it up to `interval_s` later.
        self.publish_panel_visibility('reassert-hidden')

    def _start_deferred_worker(self, source):
        """Start the worker the FIRST time any panel is actually on screen.

        THE ALT+C PATH DOES NOT CALL `show_panel`: `hotkey_pressed` cycles
        through `show_strip` -> `show_side` -> `hide_panel`, and each of those
        maps the window itself. A start hook placed only in `show_panel` was
        therefore never reached by the owner's key -- MEASURED 2026-10-17:
        `HOTKEY_PRESSED count=4` and `PANEL_SHOWN` in the log, and ZERO
        `WORKER_AUTOSTART`. This one helper is called by all three show paths.

        It starts ONLY for reason `default`: `--with-worker` already spawned
        at load, and a measurement flag must stay worker-free.
        """
        if getattr(self, 'bridge', None) is not None:
            return False
        # THE SHOW PATH MUST NOT DIE ON A MISSING FLAG. Alt+C is the owner's
        # ONLY control, and these three flags are read in the SAME `if` as the
        # defensive `getattr(self, '_paused', False)` that was already there.
        # Read them the same way: a flag that is not there is False, never an
        # AttributeError on the one key the owner presses.
        _ext_active = getattr(self, 'external_captions_active', False)
        if (getattr(self, '_paused', False) or _ext_active
                or getattr(self, 'external_captions_available', False)
                or getattr(self, '_vram_parked', False)):
            log(f'WORKER_PANEL_START_SKIPPED source={source} '
                f'paused={str(getattr(self, "_paused", False)).lower()} '
                f'external={str(_ext_active).lower()}')
            return False
        try:
            reason = self._worker_autostart_reason(self.args)
        except Exception as exc:  # noqa: BLE001
            log(f'WORKER_PANEL_START_FAILED source={source} error={exc!r}')
            return False
        log(f'WORKER_PANEL_START source={source} reason={reason}')
        if reason != 'default':
            return False
        try:
            return self.start_worker('panel-open')
        except Exception as exc:  # noqa: BLE001
            log(f'WORKER_PANEL_START_FAILED source={source} error={exc!r}')
            return False

    def show_panel(self, reason, surface=None):
        if self.hwnd is None:
            return False
        # O ALT+C VOLTA A TENTAR -- ver `no_audio_restart_cap`. O shell para de reiniciar
        # um worker que morre por SILENCIO, porque recarregar 1 GB de modelo nao arranja
        # uma rotagem. Sem este reset o dono ficava sem caminho de volta; com ele, mostrar
        # o painel e a forma de dizer "tenta outra vez".
        try:
            if getattr(self, 'bridge', None) is not None:
                self.bridge.no_audio_restarts = 0
        except Exception as exc:  # noqa: BLE001
            # O RESET QUE ABRE A VOLTA AO DONO. O Alt+C existe para dar
            # caminho de volta a um worker que morreu em silencio; engolida a
            # falha, o Alt+C deixa de fazer isso e ninguem diz porquê.
            log(f'BRIDGE_NO_AUDIO_RESET_FAILED error={exc!r}')
        want = surface or self.surface
        if want != self.surface_applied:
            # `present=True`: THE SHOW PATH READS NOTHING FROM THE PAGE. Measured
            # 2026-11-01: one press spent 1,75 s in a pill-width read and 10,0 s in
            # the geometry emit, because `exec_js` waits on the very UI thread that
            # has to map this window. See `set_panel_surface` and `exec_js_post`.
            self.set_panel_surface(want, reason, present=True)
        # The same `panel_mode` bookkeeping the hotkey paths do, for the shows
        # that arrive another way (`--show`, the tray, `toggle_panel` from the
        # page): the cycle reads this field on the next Alt+C whatever brought
        # the panel up.
        self.panel_mode = 'strip' if want == 'strip' else 'side'
        set_topmost(self.hwnd)
        # ── THE P0 ORDER: children FIRST, then the map ──────────────────────
        # The owner, verbatim: he pressed Alt+C, saw a solid-colour strip for
        # a frame, then the UI. A user32 show of the FORM maps the window now,
        # and the first frame is the FORM's own background before the browser
        # child has painted anything — so the children must already carry
        # WS_VISIBLE when the map lands. `SW_SHOWNOACTIVATE` on a child whose
        # parent is hidden sets WS_VISIBLE and paints nothing (measured:
        # `IsWindowVisible` stays FALSE until the parent is mapped, which is
        # why `show_webview_children` classifies by the style bit and not by
        # `IsWindowVisible`).
        wv = show_webview_children(self.hwnd)
        log(f'WEBVIEW_CHILD shown={len(wv["shown"])} '
            f'already={len(wv["already"])} failed={len(wv["failed"])}')
        # ── THE PAINT ACK: ARMED BEFORE THE MAP, AWAITED AFTER IT ───────────
        # The owner, verbatim: *"o painel dar show, nao deve carregar o
        # background e mostrar, e depois carregar a ui"*. The map below is a
        # user32 call that asks the page NOTHING; the ack is the question, and
        # `wait_paint_ack` is the only place that waits for its answer.
        #
        # It is awaited AFTER the map on purpose, and this is measured, not
        # preferred: while the FORM is hidden its WebView2 does not produce
        # frames on this box, and a script sent to it did not answer for 10,0 s
        # (`WARN exec_js TIMEOUT after 10.0s` at 2026-11-01 10:14:49, the line
        # Main measured inside the owner's 12,07 s first show). So the ARM is
        # posted without waiting, the map lands, and the wait happens where an
        # answer is actually possible -- bounded by `PAINT_ACK_TIMEOUT_MS`,
        # failing open, never holding the map.
        ack_seq = self.arm_paint_ack(reason)
        # SW_SHOWNOACTIVATE, not Show(): the panel must never take focus away
        # from whatever the owner is typing into (main.js: `focusable=false`).
        show_without_activating(self.hwnd)
        # ...and the compositing hack, which is the OTHER thing that has to
        # happen for a transparent WebView2. See `transparency_hack`; it is
        # deliberately AFTER the map because it re-runs pywebview's own
        # navigation-time `form.Show()`.
        transparency_hack(self)
        ack = self.wait_paint_ack(ack_seq, reason)
        self.visible = window_visible(self.hwnd)
        # THE DEFERRED DEFAULT WORKER STARTS HERE (2026-10-17). The launch is
        # light on purpose; the first time the panel is actually on screen is
        # the first moment a caption can be seen, so it is the honest moment to
        # pay the model load. `start_worker` refuses when a bridge already
        # exists, so every later Alt+C is a no-op here.
        self._start_deferred_worker('show-panel')
        if (getattr(self, 'external_captions_available', False)
                and self.external_caption_watcher is not None):
            self.external_caption_watcher.replay()
        # ARMED HERE, and only here: the watcher can close the panel from now on,
        # which is what keeps the two startup navigations from closing anything
        # (the panel is hidden then, so the visible-guard already refuses, and
        # this makes it explicit rather than incidental).
        if self.click_watcher is not None and self.visible:
            self.click_watcher.armed = True
            self.click_watcher._armed_at = time.monotonic()
        log(f'PANEL_SHOWN reason={reason} hwnd={self.hwnd} '
            f'visible={str(self.visible).lower()} '
            f'show=SW_SHOWNOACTIVATE focus_stolen=false '
            f'paint_ack={str(ack["ack"]).lower()} wait_ms={ack["wait_ms"]}')
        # The worker goes back to STREAMING on this line — see the stack law at
        # `PANEL_VISIBILITY_PATH`. `self.visible` is the MEASURED value above,
        # so a Show that silently failed publishes "still hidden" and the worker
        # stays on the batch path rather than switching to a panel nobody can
        # see.
        self.publish_panel_visibility(reason)
        return True

    def hide_panel(self, reason):
        if self.hwnd is None:
            return False
        hide_window(self.hwnd)
        # O VIGILANTE SAI COM O PAINEL (2026-10-23; e o mesmo argumento para o
        # tick de 2026-10-30). Enquanto o painel esta escondido nao ha nada para
        # "fechar com um clique fora", logo nao ha razao nenhuma para uma leitura
        # de foreground a 10 Hz. Ver `OutsideClickWatcher`.
        if self.click_watcher is not None:
            self.click_watcher.armed = False
        self.visible = window_visible(self.hwnd)
        log(f'PANEL_HIDDEN reason={reason} '
            f'visible={str(self.visible).lower()}')
        self.publish_panel_visibility(reason)
        # ESCONDER O PAINEL JA NAO DESLIGA A LEGENDA. A frase do dono que esta linha
        # executava -- *"quando eu quero ou nao"* -- e' a do interruptor, nao a do painel:
        # em 2026-10-17 ele sharpenou-a, verbatim, *"sem estar conectada a qualquer
        # painel. ela e' livre na minha tela, um overlay"*. Esconder o painel e' uma
        # accao sobre o painel; matar a legenda com ela era a legenda a estar LIGADA ao
        # painel, que e' exactamente o que ele proibiu. O que se tira sao os PIXELS
        # (`_blank_caption_window`, que nao escreve `data-caption-window`), e a legenda
        # volta a aparecer na proxima linha sem ninguem tocar em nada.
        self._blank_caption_window('panel-hidden')
        return True

    def toggle_panel(self, reason):
        """Show if hidden, hide if shown — decided by the WINDOW, not by a cache.

        `self.visible` is only updated when THIS object shows or hides the panel,
        and two other paths map or unmap the window behind its back: pywebview's
        own navigation-time `form.Show()` (gated) and `_reassert_hidden`. A stale
        `True` makes the owner's first Alt+C a no-op HIDE of a panel he cannot
        see — i.e. "Alt+C does nothing" until he presses it twice, and the log
        blames `reason=hotkey` in both directions. One `IsWindowVisible` removes
        the whole class; it is also what the cheap `--selftest` two-state check
        reads, so the two can no longer disagree.
        """
        live = window_visible(self.hwnd) if self.hwnd else False
        if live != self.visible:
            log(f'PANEL_VISIBILITY_CACHE_STALE cached={str(self.visible).lower()} '
                f'live={str(live).lower()} decided_by=window')
        self.visible = live
        return (self.hide_panel(reason) if live else self.show_panel(
            reason, surface='strip' if reason == 'hotkey' else None))

    # -- Alt+C: UM passo do ciclo dos paineis; Ctrl+Space: a legenda AO VIVO ----
    def hotkey_pressed(self):
        """Alt+C: UMA pressao = UM passo do ciclo dos paineis. IMEDIATO.

        ORDEM DO DONO, verbatim (2026-11-01): *"faz os paineis alternarem mesmo
        se eu deixar alt apertado o tempo inteiro e spammando c. alterna entre
        show e hide."*

        O CONTRATO ANTERIOR (2026-10-30) distinguia 1 toque de 2 toques dentro de
        uma janela de 400 ms e media a DURACAO da segurada (`GetAsyncKeyState`)
        para decidir se era um HOLD. Medido no log dele: pressao -> `PANEL_SHOWN`
        = **460 ms**, dos quais **8 ms** eram trabalho real -- 87 % da latencia
        era o nosso proprio adiamento, e o limiar partia o gesto ao meio quando o
        Alt ficava em baixo. O gesto de hoje nao pergunta NADA sobre o tempo:
        cada `WM_HOTKEY` e' um passo.

        A ACCAO NAO CORRE NESTA THREAD. `hotkey_pressed` e' chamado pelo
        `HotkeyThread`, que e' a thread do `RegisterHotKey`: trabalho de janela
        ali bloqueia o proprio pump que entrega a proxima pressao. Por isso o
        pedido vai para um worker proprio, em FILA -- um hop sem espera e sem
        inversao de ordem entre duas pressoes seguidas.
        """
        return self._hotkey_dispatch('panels')

    def stop_hotkeys(self):
        """Desliga as DUAS teclas globais (as duas, sempre: uma so' ficava viva)."""
        for name in ('hotkey', 'live_hotkey'):
            thread = getattr(self, name, None)
            if thread is None:
                continue
            try:
                thread.stop()
            except Exception as exc:  # noqa: BLE001 -- sair nao pode falhar
                log(f'HOTKEY_STOP_FAILED thread={name} error={exc!r}')

    def hotkey_live(self):
        """Ctrl+Space: UMA pressao = a legenda ao vivo liga/desliga. SO' O DISPLAY.

        Ordem do dono (2026-11-01): *"modifica a legenda ao vivo hotkey. bota o
        padrao como control espaco"*. A tecla vem de `hotkey_settings` (fabrica
        `hotkey_gesture.LIVE_ACCELERATOR`) e e' armada por `arm_hotkey`.

        Sai pela MESMA fila que o Alt+C, e nao por uma segunda: as duas teclas
        mantem a ordem em que ele as carregou (um Ctrl+Space entre dois Alt+C
        nao pode chegar ao ecra antes do primeiro).
        """
        return self._hotkey_dispatch('live')

    def _hotkey_dispatch(self, kind):
        """Manda o passo ao worker AGORA (nunca corre na thread do hotkey)."""
        try:
            q = getattr(self, '_hotkey_queue', None)
            if q is None:
                import queue as _queue
                q = self._hotkey_queue = _queue.Queue()
            worker = getattr(self, '_hotkey_worker', None)
            if worker is None or not worker.is_alive():
                worker = threading.Thread(target=self._hotkey_worker_loop,
                                          name='sotto-hotkey-steps', daemon=True)
                self._hotkey_worker = worker
                worker.start()
            q.put(str(kind))
            return True
        except Exception as exc:  # noqa: BLE001 -- um passo perdido nao pode matar o pump
            log(f'HOTKEY_GESTURE_FAILED kind={kind} error={exc!r}')
            return False

    def _hotkey_worker_loop(self):
        """A fila dos passos: FIFO, para duas pressoes nao se atropelarem."""
        q = self._hotkey_queue
        while True:
            kind = q.get()
            try:
                self._hotkey_resolve(kind)
            except Exception as exc:  # noqa: BLE001
                log(f'HOTKEY_HANDLER_FAILED kind={kind} error={exc!r}')

    def _hotkey_resolve(self, kind):
        """UM passo: o painel avanca no ciclo, ou a legenda comuta. Nunca os dois.

        A decisao le' o que a JANELA mede (`window_visible`) e o que ela VESTE
        (`surface_applied`), nunca uma intencao: um `show` que falhou deixou o
        painel escondido, e o ciclo tem de continuar de onde o dono esta' a ver.
        A regra inteira esta' em `hotkey_gesture.next_surface`, e o oraculo
        executa este corpo a partir do ficheiro que corre.
        """
        if str(kind) == 'live':
            # A DECISAO LE' O QUE ESTA' NO ECRA, NAO O QUE ELE PEDIU (2026-11-03).
            # Medido na sessao do dono (`_main/webview-run.log`, 02:45:13-02:45:52):
            # o interruptor restaurado do arranque (`CAPTION_WANTED_RESTORED on=true`)
            # e o botao LIVE deixaram `_caption_wanted` a `True` com a janela
            # ESCONDIDA -- entao a primeira pressao de Ctrl+Space, a unica coisa que
            # ele fez, "ligava" um interruptor que ja' estava ligado e desligava a
            # legenda. A tecla e' um INTERRUPTOR DO QUE ELE VE (o mesmo facto que o
            # lamp do painel pinta, `data-caption-window`), e o que ele ve' e'
            # `_caption_window_shown`: uma pressao muda SEMPRE o ecra.
            # O QUE CONTA COMO "NO ECRA" E' O QUE A JANELA MEDE (2026-11-03).
            # A cache dizia `mostrada` apos um pedido, e no arranque o pedido
            # vem RESTAURADO (`CAPTION_WANTED_RESTORED on=true`): a primeira
            # pressao do dono ESCONDIA uma janela que ele talvez nunca tenha
            # visto, e a leitura dele foi *"to apertando control espaco e nao ta
            # ligando"*. O painel ja' resolve isto assim (`window_visible`,
            # "a MEDICAO ao vivo, e nao a cache"); o overlay passa a usar a
            # mesma regra. Sem janela para medir (oraculo), fica a cache.
            shown = bool(getattr(self, '_caption_window_shown', False))
            _ov = getattr(self, 'caption_overlay', None)
            if _ov is not None and getattr(_ov, 'hwnd', None):
                try:
                    shown = bool(window_visible(_ov.hwnd))
                except Exception as exc:  # noqa: BLE001 -- sem leitura, cache
                    log(f'CAPTION_VISIBLE_READ_FAILED error={exc!r}')
            on = not shown
            log(f'HOTKEY_LIVE_STEP caption_on={str(on).lower()} '
                f'shown={str(shown).lower()} '
                f'wanted={str(bool(getattr(self, "_caption_wanted", False))).lower()}')
            return self._set_live_enabled({'on': on})
        # A MEDICAO AO VIVO, e nao a cache: duas outras vias mapeiam e desmapeiam
        # a janela sem passar por aqui (a `form.Show()` da navegacao, gateada, e
        # o `_reassert_hidden`), e uma cache com `True` fazia o primeiro Alt+C
        # ser um HIDE de um painel que ele nao ve. Ver `toggle_panel`.
        try:
            alive = window_visible(self.hwnd) if self.hwnd else False
        except Exception as exc:  # noqa: BLE001 -- sem leitura, fica o que se sabe
            log(f'HOTKEY_VISIBLE_READ_FAILED error={exc!r}')
            alive = bool(getattr(self, 'visible', False))
        if alive != bool(getattr(self, 'visible', False)):
            log(f'PANEL_VISIBILITY_CACHE_STALE cached={str(self.visible).lower()} '
                f'live={str(alive).lower()} decided_by=window')
        self.visible = alive
        shown = str(getattr(self, 'surface_applied', '') or '')
        try:
            nxt = hotkey_numbers().next_surface(alive, shown)
        except Exception as exc:  # noqa: BLE001 -- sem a regra, a faixa
            log(f'HOTKEY_GESTURE_FAILED error={exc!r}')
            nxt = 'strip'
        if nxt is None:
            log(f'HOTKEY_TOGGLE step=hide surface={shown or "-"}')
            return self.hide_panel('hotkey-toggle')
        log(f'HOTKEY_TOGGLE step=show surface={nxt}')
        if nxt == 'panel':
            return self.show_side('hotkey-cycle-side')
        return self.show_strip('hotkey-cycle-strip')

    def _warm_paint(self, reason='startup'):
        """Pay the page's FIRST presented frame OFF the owner's screen.

        ── MEDIDO 2026-11-01, e e' o defeito que sobrava ──────────────────────
        A primeira frame que a pagina apresenta traz so' o fundo dela e a UI
        chega 270-325 ms depois (censo: `blank_frames=19`, `first_content_ms=325`,
        `first frame std=0.0 mean=18`); TODOS os shows seguintes sao
        content-first. Logo o custo e' da primeira apresentacao do processo, e
        esperar por ele dentro de um show e' esperar com a janela a' vista -- o
        que o dono proibiu. Paga-se UMA vez, aqui, com a janela MAPEADA (e' isso
        que faz a pagina pintar) no rect que o show vai usar, mas FORA do ecra
        virtual: o rect acaba antes da borda da uniao dos monitores, logo a
        interseccao e' vazia e o dono nao ve pixel nenhum -- e o censo concorda,
        porque so' conta frame `window_onscreen`.

        O rect VOLTA ao lugar ainda escondido, e o show seguinte MAPEIA ali': e'
        um mapa novo numa janela ja' quente, nao um MOVIMENTO da janela quente
        (medido: mover a janela mapeada custa os mesmos ~270 ms que a cura
        existe para remover).

        Nao ha' sinal do compositor para esperar, portanto a espera e' o pior
        caso MEDIDO (`PAINT_WARM_SETTLE_S`), o que so' custa no arranque. O ack
        da pagina e' lido primeiro e o `wait_ms` fica no log: se a pagina nao
        responder, o aquecimento falha ABERTO, como todo o resto desta cura.
        """
        hwnd = self.hwnd
        geometry = self.geometry
        if not hwnd or not isinstance(geometry, dict):
            log(f'PAINT_WARM reason={reason} ran=false why=no-hwnd-or-geometry')
            return False
        scale = (self.display or {}).get('scaleFactor') or 1.0
        size = (int(geometry['width'] * scale), int(geometry['height'] * scale))
        # FORA DO ECRA VIRTUAL, POR INTEIRO: o rect acaba antes da borda da
        # uniao dos monitores, portanto a interseccao e' vazia
        # (`window_onscreen=false` no censo).
        warm_x = user32.GetSystemMetrics(SM_XVIRTUALSCREEN) - size[0] - 16
        warm_y = user32.GetSystemMetrics(SM_YVIRTUALSCREEN) - size[1] - 16
        user32.SetWindowPos(hwnd, HWND_TOPMOST, warm_x, warm_y,
                            size[0], size[1], SWP_NOACTIVATE)
        seq = self.arm_paint_ack(reason)
        show_without_activating(hwnd)
        ack = self.wait_paint_ack(seq, reason)
        time.sleep(PAINT_WARM_SETTLE_S)
        hide_window(hwnd)
        # E O RECT VOLTA AO QUE O SHOW VAI USAR, ainda escondido: um show que
        # encontre a superficie ja' aplicada nao torna a colocar a janela.
        user32.SetWindowPos(
            hwnd, HWND_TOPMOST,
            int(geometry['x'] * scale), int(geometry['y'] * scale),
            size[0], size[1], SWP_NOACTIVATE)
        log(f'PAINT_WARM reason={reason} ran=true size={size[0]}x{size[1]} '
            f'ack={str(ack["ack"]).lower()} ack_wait_ms={ack["wait_ms"]} '
            f'settle_s={PAINT_WARM_SETTLE_S} '
            f'visible={str(window_visible(hwnd)).lower()}')
        return bool(ack['ack'])

    def show_strip(self, reason):
        """Show the bottom strip, and take the foreground ONLY to free a lock.

        The activation contract this used to promise ("Alt+C always activates
        the panel") is now MEASURED per press instead of assumed: see
        `foreground_unlock` and `pointer_lock_state`. A press with no pointer
        lock maps the strip with `SW_SHOWNOACTIVATE` and leaves the owner's
        typing caret alone -- that is the whole of
        *"vinte Alt+C nao roubam o que ele esta' a escrever"*.
        """
        if self.hwnd is None:
            return False
        # Geometry only — nothing here maps the window; the map is below, off
        # the screen. And `present=True`, because everything below is on the
        # path to a MAP: the page is not read and is not waited for (see
        # `exec_js_post`).
        self.set_panel_surface('strip', reason, present=True)
        # AND SAY WHICH PANEL IS UP: `hotkey_pressed` is a three-state cycle
        # (HIDDEN -> STRIP -> SIDE -> HIDDEN) decided on `self.panel_mode`, whose
        # OTHER writer was the dead `place_panel`. Without this line the SECOND
        # Alt+C repainted the side panel forever instead of hiding (owner,
        # 2026-10-14: ten presses, all `mode=side`, one `PANEL_HIDDEN` in the
        # whole log). The window state is read from `window_visible` below; this
        # line records only WHICH surface is up, on the show itself.
        self.panel_mode = 'strip'
        # Children FIRST, so the first frame the owner sees is already the
        # panel: a user32 show of the FORM maps it NOW, and the first frame of a
        # mapped form is the FORM's own background. Measured 2026-10-09 by the
        # owner's own eyes — a strip, then the UI one frame later.
        wv = show_webview_children(self.hwnd)
        log(f'WEBVIEW_CHILD shown={len(wv["shown"])} '
            f'already={len(wv["already"])} failed={len(wv["failed"])}')
        # THE ACK, ARMED BEFORE THE MAP AND AWAITED AFTER IT — see `show_panel`
        # for the measured reason (a hidden WebView2 on this box does not answer
        # a script for 10,0 s, so a pre-map wait is a pre-map stall).
        ack_seq = self.arm_paint_ack(reason)
        # THEN the map: `SW_SHOWNOACTIVATE`, and `SW_SHOW+SetForegroundWindow`
        # only when the foreground app holds a POINTER LOCK. See
        # `foreground_unlock`; the old unconditional activation is the defect
        # that stole the owner's caret on every press.
        fg = foreground_unlock(self.hwnd)
        # And the compositing hack AFTER the map — see `transparency_hack`.
        transparency_hack(self)
        ack = self.wait_paint_ack(ack_seq, reason)
        self.visible = window_visible(self.hwnd)
        self._start_deferred_worker('show-strip')
        if (getattr(self, 'external_captions_available', False)
                and self.external_caption_watcher is not None):
            self.external_caption_watcher.replay()
        log(f'PANEL_SHOWN reason={reason} mode=strip hwnd={self.hwnd} '
            f'visible={str(self.visible).lower()} '
            f'show={fg.get("show")} focus={fg.get("reason")} '
            f'paint_ack={str(ack["ack"]).lower()} wait_ms={ack["wait_ms"]}')
        self.publish_panel_visibility(reason)
        return True

    def show_side(self, reason):
        """Show the RIGHT side panel — the cycle's second step.

        Same map contract as `show_strip`, including the focus gate: the
        foreground is taken ONLY when the foreground app holds a pointer lock
        (`foreground_unlock`). The only difference is the geometry: `dock_right`
        instead of `dock_strip`. Kept as its own method (not a
        `show_panel(mode)` flag) so the `mode=` field in the log tells which
        geometry the owner is looking at.

        IT IS NO LONGER "THE DOUBLE-PRESS PATH" (2026-10-13): the double-press
        window is deleted and this is simply what the SECOND Alt+C does, from the
        strip, at any speed. See `hotkey_pressed`.
        """
        if self.hwnd is None:
            return False
        # Geometry only — the map is below, off the screen.
        #
        # CORRECTED 2026-10-12, AND THIS IS THE OWNER'S Alt+C BUG. This line
        # passed the literal `'side'`, and `'side'` IS NOT A SURFACE NAME:
        # `SURFACE_NAMES = ('strip', 'panel')` (:1479) and `normalise_surface_name`
        # (:1480) returns None for anything else BY DESIGN. So every double-press
        # logged `WARN PANEL_SURFACE_REFUSED surface="side" reason="hotkey-double"`
        # and returned False BEFORE computing any geometry: the window was mapped
        # with the STRIP's rect and the STRIP's document surface. That is exactly
        # the owner's report -- two presses showed the strip and never the right
        # panel -- and the `if not live` guard fixed earlier was necessary but not
        # sufficient. The surface the right panel wears is `'panel'`.
        self.set_panel_surface('panel', reason, present=True)
        # WHICH PANEL IS UP — see `show_strip` for the measured defect. The
        # cycle's third arm is `panel_mode == 'side'`, and that word is what
        # makes the next Alt+C HIDE. Without it the side panel is where the
        # cycle stops.
        self.panel_mode = 'side'
        # Children FIRST — same P0 reason as `show_panel` and `show_strip`: a
        # raw user32 show of the FORM leaves `Chrome_WidgetWin_0` hidden and the
        # panel a flat colour for one frame. Measured 2026-10-09.
        wv = show_webview_children(self.hwnd)
        log(f'WEBVIEW_CHILD shown={len(wv["shown"])} '
            f'already={len(wv["already"])} failed={len(wv["failed"])}')
        # THE ACK, ARMED BEFORE THE MAP AND AWAITED AFTER IT — `show_panel`.
        ack_seq = self.arm_paint_ack(reason)
        # THEN the map: no activation unless a POINTER LOCK needs freeing.
        fg = foreground_unlock(self.hwnd)
        transparency_hack(self)
        ack = self.wait_paint_ack(ack_seq, reason)
        self.visible = window_visible(self.hwnd)
        self._start_deferred_worker('show-side')
        if (getattr(self, 'external_captions_available', False)
                and self.external_caption_watcher is not None):
            self.external_caption_watcher.replay()
        log(f'PANEL_SHOWN reason={reason} mode=side hwnd={self.hwnd} '
            f'visible={str(self.visible).lower()} '
            f'show={fg.get("show")} focus={fg.get("reason")} '
            f'paint_ack={str(ack["ack"]).lower()} wait_ms={ack["wait_ms"]}')
        self.publish_panel_visibility(reason)
        return True

    def set_transparency(self, on):
        """Honor the panel's `sotto:transparency {on: bool}` request.

        ON = shell chrome goes click-through (`WS_EX_TRANSPARENT`, the same
        style `set_pointer_interactive` drives) while the page keeps painting
        captions; OFF restores hit-testing. The page owns the pixels — the
        shell only moves the one style bit — so this is a log line and a style
        call, never a layout change. `TRANSPARENCY_ON/OFF` is the greppable
        receipt the dispatch map promises even when the panel never asks.

        Idempotent: the LIVE bit is read first, so a request for the state
        the window is already in applies nothing and logs nothing — the
        "one line each, no spam" half of the contract. The live bit is read
        rather than `self.transparent` on purpose: `set_pointer_interactive`
        moves the SAME bit, so the cached flag alone cannot say what the
        window is actually doing right now.
        """
        state = 'ON' if on else 'OFF'
        if self.hwnd is None:
            log(f'TRANSPARENCY_{state} pending=no-hwnd')
            return False
        want = bool(on)
        live = bool(user32.GetWindowLongW(self.hwnd, GWL_EXSTYLE)
                    & WS_EX_TRANSPARENT)
        if live == want:
            self.transparent = want
            return True
        try:
            make_click_through(self.hwnd, want)
        except Exception as exc:  # noqa: BLE001 -- report, never kill the page
            log(f'TRANSPARENCY_{state}_FAILED error={exc!r}')
            return False
        self.transparent = want
        log(f'TRANSPARENCY_{state} '
            f'click_through={str(want).lower()} captions=kept')
        return True

    # -- page -> host handlers --------------------------------------------
    def info(self):
        return {
            'hotkey': self.args.hotkey,
            'versions': {'shell': 'webview2/pywebview',
                         'python': sys.version.split()[0]},
            'geometry': self.geometry,
            'visible': self.visible,
            'rendererReady': self.renderer_ready.is_set(),
            'panel': PANEL_HTML,
        }

    def reply_info(self, info_id, payload):
        self.exec_js(f'window.__sotto_info({json.dumps(info_id)}, '
                     f'{json.dumps(json.dumps(payload))})')

    def quit(self, reason):
        self.request_exit(0, reason=reason)

    # -- tray --------------------------------------------------------------
    def start_tray(self) -> bool:
        """The icon in the notification area, and its Quit.

        Owner, 2026-10-08: *"tira o botao de quit sotto do painel. só tem q quit
        no icon do system tray"* — so this is now the ONLY way to close the app,
        and a tray that fails to appear would leave him with the task manager.
        It therefore says so LOUDLY (`TRAY_FAILED`) instead of being a silent
        missing feature.
        """
        self.tray = TrayIcon(SOTTO_ICON, self.tray_command, log, warn)
        ok = self.tray.start()
        if not ok:
            warn('TRAY_UNAVAILABLE the notification-area icon did not come up; '
                 'the app keeps running and Alt+C still works, but the Quit '
                 f'has no home (error={self.tray._failed})')
        return ok

    def tray_command(self, command):
        if command == ID_TRAY_QUIT:
            log('TRAY_QUIT requested=true')
            self.request_exit(0, reason='tray-quit')
        elif command == ID_TRAY_OPEN:
            # THE FULL PANEL, because that is what the item says. Alt+C is what
            # opens the SHORT strip (`surface.js:6-8`); the tray is the owner's
            # deliberate way to the whole column, and the strip's own "Open
            # panel" button takes the same road through
            # `bridge.setPanelSurface('panel')`.
            log('TRAY_OPEN requested=true surface=panel')
            live = window_visible(self.hwnd) if self.hwnd else False
            if live and self.surface == 'panel':
                self.hide_panel('tray')
            else:
                self.show_panel('tray', surface='panel')
        elif command == ID_TRAY_EDIT:
            log('TRAY_EDIT requested=true')
            self.set_edit_mode(not self.edit_mode, 'tray')

    def request_exit(self, code=0, reason='requested'):
        if self.exiting.is_set():
            return
        self.exiting.set()
        self._exit_code = code
        # The tray goes FIRST: `os._exit` at the end of this method would leave
        # the icon in the notification area as a ghost the owner cannot dismiss
        # (it would still be there, pointing at a dead window).
        if self.tray is not None:
            self.tray.stop('exit')
        if self.bridge is not None:
            self.bridge.stop('exit')
        _sidecar_exit = getattr(self, '_speaker_sidecar', None)
        if _sidecar_exit is not None:
            _sidecar_exit.stop('shell-exit')
        _watch_exit = getattr(self, '_multivoice_watch', None)
        if _watch_exit is not None:
            _watch_exit.stop('shell-exit')
        self.stop_hotkeys()
        if self.panel_state is not None:
            self.panel_state.stop('exit')
        if self.panel_visibility is not None:
            # A last write, so a worker still polling during the shell's exit
            # reads a FRESH answer rather than a stale one: this is the write
            # that turns "the shell is gone" into "the worker stops believing
            # me" via `staleAfterSeconds`, instead of the worker obeying the
            # last state it happens to hold.
            self.panel_visibility.write('exit')
            self.panel_visibility.stop('exit')
        self.stop_hot_reload('exit')
        # `window.destroy()` marshals a Close() onto the UI thread and WAITS
        # for it. With a live worker streaming statuses, each status is an
        # ExecuteScriptAsync on that same thread, so the queue can be deep
        # enough that a synchronous destroy outlives the exit timer it was
        # called from — measured: `--with-worker --exit-after 30` never printed
        # SHELL_EXIT and had to be killed. Closing is cosmetic here (os._exit
        # follows immediately), so it runs on its own thread and is capped.
        if self.window is not None:
            def _close():
                try:
                    self.window.destroy()
                except Exception:
                    pass
            closer = threading.Thread(target=_close, name='sotto-close',
                                      daemon=True)
            closer.start()
            # THE WAIT IS SHORT (2026-10-21). The destroy is cosmetic -- the
            # `os._exit` below kills the window anyway -- so three seconds of
            # a frozen tray thread bought nothing and WAS the owner's
            # *"fechar o sotto trava"*. A quarter of a second lets the destroy
            # start and then the shell leaves.
            closer.join(QUIT_DESTROY_WAIT_S)
        # The stats totals travel with the exit line: the push is logged at most
        # once per `STATS_LOG_INTERVAL_S`, so a short run's log would otherwise
        # never show how many samples the feed actually carried. One line, at the
        # end, and it is the number `_main/_strip-stats-log-probe.py` reads to
        # prove the feed was DELIVERED while the log stayed small.
        log(f'SHELL_EXIT rc={code} reason={reason} '
            f'statsPushes={self.stats_pushes} statsReplies={self.stats_replies} '
            f'meterPushes={self.meter_pushes}')
        sys.stdout.flush()
        _log_drain()          # the queued mirror lines land before we go
        os._exit(code)

    # -- worker ------------------------------------------------------------
    @staticmethod
    def _worker_off_message(reason):
        """D3: the honest sentence for a shell with NO worker, or None.

        `panel.html:189` ships `Idle · no audio source`, and D3 of
        `docs/audit/auditoria-completa-20261007.md` names it for what it is: a
        FALSE claim. There is audio on this box (measured, `_main/listen-probe.py`
        and the routing law); what is missing is the PROCESS. With F1 cured the
        shell knows exactly why there is no worker, so it says so.

        Naming the flag is the point: "no worker" with the flag in hand is a
        decision the owner (or a lane) can undo in one argument, and
        `reason` is the same string the launch logged, so the log line and the
        painted sentence cannot disagree.

        Returns `(text, info)` for `apply_panel_state`, or `None` for a reason
        that must NOT paint anything: `with-worker` and `default` have a worker,
        and a measurement run (`measurement-flag(…)`) keeps the NEUTRAL panel its
        instrument is measuring -- a status fired into an instrument's DOM would
        be the shell changing the thing under measurement.
        """
        if reason == 'no-worker':
            sent_by = '--no-worker'
        elif reason == 'env':
            sent_by = 'SOTTO_NO_WORKER=1'
        elif reason.startswith('measurement-flag('):
            sent_by = reason[len('measurement-flag('):-1]
        else:
            return None
        return (
            f'No transcription worker is running (started with {sent_by})',
            {'title': 'No worker · captions are impossible',
             'body': f'This shell was started with {sent_by}, so no audio is '
                     'being captured. Start it without that flag (run.cmd, the '
                     'documented entry) to transcribe.'},
        )

    @staticmethod
    def _worker_autostart_reason(args, env=None):
        """F1: should the worker auto-start, and WHY — as one of five strings.

        `docs/audit/auditoria-completa-20261007.md` F1: the documented launch
        (`run.cmd`) started no worker at all, so Alt+C opened a panel claiming to
        wait for audio with no capture process in existence. The worker now
        starts by DEFAULT; the flag is the OPT-OUT.

        The return value is the `reason=` field of the
        `WORKER_AUTOSTART=started|declined reason=…` line, and `'default'` is the
        only value that starts it:

          `'with-worker'`      the flag was passed — AUTHORITATIVE, so a lane or
                               a script that wants the worker in a measurement
                               keeps working
          `'no-worker'`        `--no-worker`: shell only
          `'env'`              `SOTTO_NO_WORKER=1` in the environment
          `'measurement-flag(…)'` a mode that measures the panel or the shell,
                               not transcription: `--dump-dom`, `--selftest`,
                               `--memory`, `--no-hotkey` (the shell's own help
                               calls it "for MEASUREMENT runs", and a real run
                               cannot work without Alt+C) and `--exit-after` (a
                               bound for a BOUNDED probe run). Without this, a
                               plain probe launch would pay a ~2 GB model load
                               and open an audio tap on every arm.
          `'default'`          nothing said otherwise — start it

        Precedence is the order above, most explicit first. Checked against every
        call site that needs a worker FOR REAL: `_main/_app-drive.py`
        (`--with-worker --probe-v2`), `_main/_live-launch.py` (`--with-worker`)
        and a plain double-click (no flags) — none relies on `--exit-after`
        alone. Factored out of `_on_loaded` so the rule is assertable without a
        WebView2 (see `_main/_lane1-worker-default-arms.py`).
        """
        if getattr(args, 'with_worker', False):
            return 'with-worker'
        if getattr(args, 'no_worker', False):
            return 'no-worker'
        env = os.environ if env is None else env
        if str(env.get('SOTTO_NO_WORKER') or '').strip() == '1':
            return 'env'
        # `--exit-after` is a FLOAT (0.0 = off) and the rest are `store_true`;
        # truthiness is correct for both and keeps this one readable table.
        for flag, name in (('dump_dom', '--dump-dom'),
                           ('selftest', '--selftest'),
                           ('memory', '--memory'),
                           ('no_hotkey', '--no-hotkey'),
                           ('exit_after', '--exit-after'),
                           # A stats probe must not pay a ~2 GB model load:
                           # without this entry a bare --probe-stats run falls
                           # through to reason=default and STARTS the worker.
                           ('probe_stats', '--probe-stats'),
                           ('probe_outside_click',
                            '--probe-outside-click'),
                           ('probe_edit_mode', '--probe-edit-mode')):
            if getattr(args, flag, False):
                return f'measurement-flag({name})'
        return 'default'

    #: The reasons that may SPAWN a worker. Everything else is the decline half of
    #: `_worker_autostart_reason`, which NAMES why; this tuple is what makes the
    #: name binding. `hot-reload` is here because a file change must restart the
    #: worker it already had (the reload policy decides WHEN, not whether).
    START_REASONS = ('default', 'with-worker', 'hot-reload', 'revive',
                     # The deferred default's own reason: the first time the
                     # panel is actually on screen (2026-10-17).
                     'panel-open',
                     # THE PRELOAD (2026-10-21): the app's start, in the
                     # background, so the model is ready BEFORE the owner
                     # presses Alt+C. See `_schedule_preload_worker`.
                     'preload',
                     # The player stopped supplying its own captions.
                     'external-end',
                     # The GPU became free after a game/video demanded it.
                     'vram-resume')

    def _schedule_preload_worker(self, delay_s=None):
        """Load the model in the BACKGROUND, before the owner asks for it.

        THE OWNER'S COMPLAINT, verbatim (2026-10-21, and this is the twentieth
        time it is said): *"abrir ou fechar o sotto trava pra caralho meu pc"*.
        THE MEASUREMENT BEHIND IT: the panel opens, the worker is spawned, and
        the model takes 36.9 s to be ready (the owner's own log:
        `BRIDGE_LOAD_MS ms=36968 ... worker_load_s=32.59`), so the panel he
        just opened shows nothing for the best part of a minute -- and the
        machine is busy the whole time.

        THE FIX IS NOT A FASTER LOAD. The load's phases are timed now
        (`load_phases_s`): the three ONNX sessions cost 1.74-2.09 s and the
        whole load is 6.5-10.6 s on a quiet machine and 36-49 s on a busy one.
        The cost is the machine, and the cure for "the machine is busy" is to
        NOT ASK THE MACHINE AT THE MOMENT THE OWNER IS WATCHING.

        SO: the app's start schedules the load, a delay later, in the
        background, at the worker's BELOW_NORMAL priority. The launch stays
        light (nothing happens during the window's first paint), the login
        absorbs it, and the first Alt+C finds the model ready.

        `SOTTO_NO_PRELOAD=1` puts the old behaviour back (the worker waits for
        the first panel open), and a MEASUREMENT launch never preloads: those
        reasons are not 'default' and they never reach this call.
        """
        if str(os.environ.get('SOTTO_NO_PRELOAD') or '').strip() == '1':
            log('WORKER_PRELOAD declined reason=env SOTTO_NO_PRELOAD=1 '
                'start=first-panel-open')
            return False
        if delay_s is None:
            delay_s = WORKER_PRELOAD_DELAY_S
        try:
            delay_s = max(0.0, float(delay_s))
        except (TypeError, ValueError):
            delay_s = WORKER_PRELOAD_DELAY_S
        # UM WATCHER, NAO UM TIMER (2026-10-23). Um `Timer` dispara ao segundo 20 e
        # nao sabe o que o dono esta a fazer; o watcher espera que ele pare. O
        # `_preload_timer` fica com a thread para o caso de alguem a querer cancelar.
        watcher = threading.Thread(target=self._preload_when_idle, args=(delay_s,),
                                   name='sotto-worker-preload', daemon=True)
        self._preload_timer = watcher
        watcher.start()
        log(f'WORKER_PRELOAD scheduled delay_s={delay_s} idle_s={WORKER_PRELOAD_IDLE_S} '
            f'ceiling_s={WORKER_PRELOAD_MAX_WAIT_S}')
        return True

    def _owner_idle_s(self):
        """Segundos desde o ultimo input do dono (rato/teclado), ou None.

        `GetLastInputInfo` e a fonte do Windows para "ha quanto tempo o utilizador
        nao mexe em nada" -- e e a unica que responde a pergunta certa: o preload
        nao pode competir com o dono. Devolve None quando nao se consegue ler (a
        chamada seguinte trata None como "nao sei" e usa o tecto).
        """
        if os.name != 'nt':
            return None
        try:
            import ctypes
            from ctypes import wintypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]

            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                return None
            now = ctypes.windll.kernel32.GetTickCount()
            # Os dois sao DWORD e dao a volta a cada 49,7 dias: a mascara faz a
            # diferenca certa tambem quando o contador passa por zero.
            return max(0.0, ((int(now) - int(info.dwTime)) & 0xFFFFFFFF) / 1000.0)
        except Exception as exc:  # noqa: BLE001
            log(f'WORKER_PRELOAD idle-read-failed error={exc!r}')
            return None

    def _preload_when_idle(self, delay_s):
        """O corpo do agendamento: esperar pelo dono quieto, com tecto."""
        t0 = time.time()
        try:
            base = max(0.0, float(delay_s))
        except (TypeError, ValueError):
            base = WORKER_PRELOAD_DELAY_S
        ceiling = t0 + base + WORKER_PRELOAD_MAX_WAIT_S
        while time.time() < ceiling:
            if getattr(self, 'bridge', None) is not None:
                log('WORKER_PRELOAD skipped reason=worker-already-running')
                return False
            waited = time.time() - t0
            idle = self._owner_idle_s()
            # `base <= 0.0` NAO DISPENSA O DONO QUIETO (2026-11-03). MEDIDO:
            # `WORKER_PRELOAD start waited_s=0.0 owner_idle_s=3.1` -- com
            # `delay_s=0` a condicao de inatividade era curto-circuitada e o
            # modelo comecava a carregar (36-49 s numa maquina ocupada) tres
            # segundos depois do ultimo input, com o dono a ver um video.
            if waited >= base and (idle is None or idle >= WORKER_PRELOAD_IDLE_S):
                if self._external_caption_owns_screen():
                    log('WORKER_PRELOAD skipped reason=external-captions-on-screen '
                        'waited_s=%.1f' % waited)
                    return False
                log('WORKER_PRELOAD start waited_s=%.1f owner_idle_s=%s'
                    % (waited, 'unknown' if idle is None else '%.1f' % idle))
                return self._preload_worker()
            time.sleep(WORKER_PRELOAD_POLL_S)
        log('WORKER_PRELOAD start waited_s=%.1f reason=idle-ceiling'
            % (time.time() - t0,))
        return self._preload_worker()

    def _external_caption_owns_screen(self):
        """O ecra esta' a mostrar a legenda do PLAYER? (60 s de recencia)

        Existe para o preload do modelo nao competir com o que o dono esta' a ver.
        MEDIDO 2026-11-03, na sessao dele: `WORKER_PROVIDERS selected=CUDA...` as
        02:42:01 e a legenda PARADA 46 s -- as duas linhas do player ja'
        desenhadas, nada de novo ate' o watchdog bater. O carregamento do modelo
        custa 6,5-10,6 s numa maquina quieta e 36-49 s numa ocupada, e enquanto
        ele corre quem paga o atraso e' a legenda. Quando o YouTube esta' a
        fornecer a legenda, o ASR nao e' preciso: nao se carrega.
        """
        # O ESTADO VIVE NO WATCHER, NAO NA SHELL (2026-11-03). MEDIDO: o gate
        # correu e devolveu False com o dono a ver um video porque lia
        # `self.yt_live_paint_at`/`self._yt_cdp_source` da SHELL, e esses campos
        # sao do `ExternalCaptionWatcher`. Um gate que le o objecto errado e'
        # um gate desligado -- e o preload arrancou 26,6 s depois do arranque.
        _w = getattr(self, 'external_caption_watcher', None)
        try:
            _at = float(getattr(_w, 'yt_live_paint_at', 0.0) or 0.0)
            if _at and (time.monotonic() - _at) <= 60.0:
                return True
            if (getattr(_w, 'yt_cdp_rows', None)
                    and getattr(_w, 'yt_source_paused', False)):
                return True
            if (getattr(_w, '_yt_cdp_source', None)
                    and getattr(_w, 'yt_video_id', '')):
                return True
            # ANTES DA PRIMEIRA LINHA TAMBEM CONTA (2026-11-03). MEDIDO: as
            # 02:50:06 o preload arrancou 1 s depois de a app subir, com a fonte
            # CDP JA' `attached` e o dono a ver um video -- `_external_caption_
            # `owns_screen` so' olhava para quem ja' tinha PINTADO, e a primeira
            # linha chega depois do preload. Basta haver um video lido e a porta
            # aberta: o dono esta' a ver YouTube, o ASR nao e' preciso.
        except Exception:                 # noqa: BLE001
            return False
        return False

    def _preload_worker(self):
        """The preload's body: start the worker, unless there is no reason to."""
        if getattr(self, 'bridge', None) is not None:
            log('WORKER_PRELOAD skipped reason=worker-already-running')
            return False
        if self._external_caption_owns_screen():
            log('WORKER_PRELOAD skipped reason=external-captions-on-screen '
                '-- o ASR nao e\' preciso enquanto o player pinta')
            return False
        started = self.start_worker('preload')
        log(f'WORKER_PRELOAD done started={str(started).lower()}')
        return bool(started)

    def start_caption_pipeline(self, reason):
        """LEGENDA E WORKER NAO ESPERAM PELO WEBVIEW2 (2026-11-03).

        MEDIDO nesta maquina: `AddScriptToExecuteOnDocumentCreatedAsync` leva
        11,6 s, a navegacao do staging fica `done` aos 13,4 s e o evento
        `loaded` do painel chega 35 s depois disso -- e o worker, o observador
        das legendas e a legenda nativa so' arrancavam DEPOIS disso, dentro de
        `_complete_startup`. Resultado medido no dono: Ctrl+Space as 03:22:19
        com `LIVE_ENABLED on=true` e NADA no ecra, porque metade do pipeline
        ainda nao existia. A legenda nao depende da pagina do painel: o overlay
        e' uma janela Win32 nativa e o worker e' um processo a parte.
        """
        if getattr(self, '_caption_pipeline_started', False):
            return False
        self._caption_pipeline_started = True
        log('CAPTION_PIPELINE_START reason=%s' % reason)
        for step, call in (
                ('watcher', lambda: self.start_external_caption_watcher()),
                ('worker', lambda: self.start_worker(
                    self._worker_autostart_reason(self.args))),
        ):
            try:
                call()
            except Exception as exc:          # noqa: BLE001
                log('CAPTION_PIPELINE_STEP_FAILED step=%s error=%r' % (step, exc))
        try:
            if self._worker_autostart_reason(self.args) in ('default', 'with-worker'):
                self.vram_guard = VramGuard(self)
                self.vram_guard.start()
        except Exception as exc:              # noqa: BLE001
            log('VRAM_GUARD_START_FAILED error=%r' % (exc,))
        return True

    def start_worker(self, reason):
        if reason not in self.START_REASONS:
            # ── THE RULE'S BINDING HALF, AND IT WAS MISSING UNTIL NOW ─────────
            # `_worker_autostart_reason` was computed at the call site and then
            # DISCARDED: this method started a worker for any reason string, so a
            # `--dump-dom` / `--selftest` / `--memory` / `--no-hotkey` /
            # `--exit-after` launch paid a ~2 GB model load (the exact cost the
            # suppression set exists to avoid), and the D3 path told the panel
            # "No transcription worker is running (started with --dump-dom)"
            # WHILE a worker was loading. Both instruments that passed — the
            # 15-arm rule probe and the adversary lane's 22-arm sweep — test the
            # RULE, so neither could see the wiring; it was found by reading this
            # call site on 2026-10-07. `_main/_audit-worker-start-wiring.py` now
            # gates precisely this pair.
            log(f'WORKER_AUTOSTART=declined reason={reason} by=start_worker')
            return False
        # ── THE ORPHAN GUARD (owner, 2026-10-21) ────────────────────────────
        # `os._exit` does NOT kill a child process, so a worker spawned AFTER
        # the shell decided to quit SURVIVES the app: it loads 1.2 GB of model
        # and runs the capture ladder on a machine whose app is already closed.
        # That is not a theory -- it is the owner's own log: at 20:50:50.070,
        # 0.65 s before `SHELL_EXIT`, `EXTERNAL_CAPTIONS_WORKER_RESUMED
        # reason=player-stopped` started a second worker, and the orphan's
        # `BRIDGE_LOAD_MS ms=67969` (68 s from the spawn) is the machine the
        # owner was complaining about. The owner, verbatim: *"abrir ou fechar o
        # sotto, principalemnte fechar, trava pra caralho meu pc"*.
        #
        # THE FIX IS HERE, NOT IN THE CALLERS. One path (`on_external_captions_
        # released`) learned this the hard way; the OTHER spawn paths -- the
        # panel opening, the VRAM resume, the revive -- could still race the
        # exit. A worker is a CHILD of this shell: if the shell is dying, no
        # child may be born.
        exiting = getattr(self, 'exiting', None)
        if exiting is not None and exiting.is_set():
            log(f'WORKER_AUTOSTART=declined reason={reason} '
                'by=start_worker cause=shell-exiting')
            return False
        if self.bridge is not None:
            return False
        # ── THE PER-APP TAP, OPT-IN -- AND AN UNRESOLVED TARGET REFUSES ──────
        # `--app-target` / `SOTTO_APP_TARGET` asks the worker for ONE app's
        # process tree. It is resolved HERE, once, immediately before the bridge
        # that carries it is built; nothing above this line changed.
        # AN UNRESOLVED NAME MUST NOT FALL BACK TO THE ENDPOINT MIX: that would
        # transcribe EVERY app while the owner believes he is reading one, which
        # is the exact failure a silent default would hide. So it declines in the
        # SAME shape every other refusal uses (`WORKER_AUTOSTART=declined
        # reason=...`) and paints the panel through the SAME error path the
        # missing-worker case uses (`apply_panel_state(text, 'error', info)`,
        # the call `_worker_off_message`'s site makes), then returns False
        # WITHOUT constructing a bridge -- so no child process is created.
        target_pid = None
        target_value, target_source = app_target_request(self.args)
        if target_value is not None:
            log(f'APP_TARGET value={json.dumps(target_value)} '
                f'source={target_source}')
            target_pid, candidates = resolve_app_target(target_value)
            if target_pid is None:
                log(f'APP_TARGET_UNRESOLVED value={json.dumps(target_value)} '
                    f'reason=no-process')
                self.apply_panel_state(
                    f'App target not found - {target_value}', 'error',
                    {'title': 'App target not found',
                     'body': f'No running process matches {target_value!r}, so '
                             'the per-app tap has nothing to aim at. No worker '
                             'was started: the endpoint mix would transcribe '
                             'every app instead of the one you named.'})
                log('WORKER_AUTOSTART=declined reason=app-target-unresolved '
                    'by=start_worker')
                return False
            log(f'APP_TARGET_RESOLVED value={json.dumps(target_value)} '
                f'chose={target_pid} candidates='
                + ','.join(str(pid) for pid in candidates))
        self.bridge = WorkerBridge(
            command=self.args.python,
            worker_path=self.args.worker,
            device=self.args.device,
            capture_mode=self.args.capture or DEFAULT_CAPTURE_MODE,
            log=log,
            on_caption=self.on_worker_caption,
            on_status=self.on_worker_status,
            on_stats=self.on_worker_stats,
            on_meter=self.on_worker_meter,
            # A espera do modelo (30-38 s medidos) vai para a janela da legenda.
            on_loading_text=self.push_caption_to_window,
            target_pid=target_pid,
            # MEASURED: este parametro faltava. O --speakers chegava
            # ao SIDECAR mas nunca ao WORKER, que e' quem o consome -- e o
            # _main/sidecar-wiring-oracle.py arm 2 foi a RED exactamente por
            # isso. Um diarizador a correr e a bridge sem o flag que consome o
            # seu ficheiro e' o peor dos dois mundos: 207 MB e zero atribuicao.
            extra_args=(['--speakers'] if getattr(self.args, 'speakers', False)
                         else None),
        )
        log(f'WORKER_PATH {self.args.worker}')
        log(f'WORKER_COMMAND {self.args.python}')
        started = self.bridge.start(reason)
        log(f'WORKER_AUTOSTART={"started" if started else "declined"} '
            f'reason={reason}')
        if started:
            self.code_state_log(f'worker-started-{reason}')
            # UM WORKER NOVO E' UMA FONTE NOVA (2026-10-30). O audio que este
            # processo vai transcrever nao e' o do anterior: um texto enfileirado
            # antes do arranque pertence a outro audio e nao pode pintar.
            self._source_epoch = int(getattr(self, '_source_epoch', 0)) + 1
            self._caption_pending = None
            log(f'SOURCE_EPOCH n={self._source_epoch} reason=worker-started-{reason}')
            # THE SIDECAR RIDES THE WORKER'S LIFETIME, AND ONLY WHEN THE WORKER
            # ACTUALLY STARTED. Starting it on a declined worker would leave a
            # 277 MB diarizer running against nobody, which is the failure the
            # `WORKER_AUTOSTART=declined` path exists to prevent.
            if getattr(self.args, 'speakers', False) \
                    or getattr(self.args, 'speakers_cheap', False):
                sidecar = self.speaker_sidecar()
                if sidecar.start(reason) and getattr(self.args, 'speakers_cheap', False) \
                        and not getattr(self.args, 'speakers', False):
                    # Only when the sidecar ACTUALLY started: a reader polling a
                    # file nobody writes is a thread that reports "quiet" forever,
                    # which reads exactly like "the detector ran and saw nothing".
                    self.multivoice_watch().start(reason)
        return started

    def speaker_sidecar(self):
        """The one sidecar object, created on first use.

        Lazy so that a shell that never asks for voices never constructs it,
        and so `stop` sites can call this without a None check.
        """
        sidecar = getattr(self, '_speaker_sidecar', None)
        if sidecar is None:
            # FASE A vs FASE B. `--speakers` is the full attribution and keeps
            # a byte-identical argv; `--speakers-cheap` only answers "were two
            # voices talking at the same time?" and pays 90,3 MB instead of
            # 135,4 MB. If BOTH are asked for, the full attribution wins: it
            # already contains the segmentation model, so the cheap watch would
            # be a second model doing a subset of its work.
            tail = []
            if not getattr(self.args, 'speakers', False) \
                    and getattr(self.args, 'speakers_cheap', False):
                tail = ['--watch-only']
                save = getattr(self.args, 'save_voice_clips', '') or ''
                if save:
                    # ONLY reachable with the cheap arm. Writing the owner's own
                    # call audio to disk is not a default anybody should inherit
                    # by accident, so it is empty unless asked for BY NAME.
                    tail += ['--watch-save', save]
            sidecar = SpeakerSidecar(
                command=getattr(self.args, 'python', None),
                log=log,
                extra_args=tail)
            self._speaker_sidecar = sidecar
            # FASE A's CONSUMER. Without this the watch payload would be written
            # by nobody's reader, and a detection nobody reads decides nothing.
            # Only for the cheap arm: `--speakers` is the full attribution and
            # has its own path for everything it knows.
            if tail:
                self._multivoice_watch = MultiVoiceWatch(log=log)
        return sidecar

    def multivoice_watch(self):
        """The Fase A reader, created on first use, never None."""
        watch = getattr(self, '_multivoice_watch', None)
        if watch is None:
            watch = MultiVoiceWatch(log=log)
            self._multivoice_watch = watch
        return watch

    #: The exact sentence the panel is painted with while a revive runs.
    #: ARM S of _main/revive-pipeline-oracle.py compares it literally.
    REVIVE_PAINT = 'Restarting the pipeline…'

    def revive_worker(self, caller='panel-status'):
        """The panel's repair control, answered.

        app/panel/panel.js wires the footer status as a repair control: one
        click asks the shell to kill the worker and respawn it (revivePipeline
        at :2013 -> bridge.revive('panel-status') at :2045). The shell half was
        never written, so on every launch the control reported itself
        unsupported and the owner's only recovery from a stalled pipeline was a
        dead click. A worker that has FROZEN mid-stream -- the measured Alt+C
        failure of 2026-10-11, where the tap's blocks stopped arriving while the
        process stayed alive -- is exactly what this control is for.

        The ORDER is the contract, and ARM S of _main/revive-pipeline-oracle.py
        measures every step of it:
          1. the reload timers stop FIRST -- a reload boundary landing in the
             middle of this would fight the restart;
          2. the old child stops with reason='revive';
          3. the two latches about THAT child are dropped: pending_error is the
             sticky death the panel keeps painting until a caption proves
             recovery, and no_audio is a verdict about the child just killed --
             carried over it would paint the fresh worker as deaf before it had
             opened a device;
          4. start_worker('revive') respawns.

        Returns True if the request was accepted, False if one is already in
        flight. The refusal is logged, never silent.
        """
        with self._revive_lock:
            if self._revive_thread is not None:
                log(f'REVIVE_REFUSED reason=already-in-flight caller={caller}')
                return False
            if self._external_parked:
                # THE PLAYER IS SUPPLYING THE CAPTION. The worker is parked
                # ON PURPOSE, so a repair would undo the parking and start a
                # model load for a caption that already exists. MEASURED
                # 2026-10-20: `REVIVE_REQUESTED caller=panel-status
                # had_bridge=false` 47 s after `EXTERNAL_CAPTIONS_WORKER_
                # PARKED source=external:youtube:track` -- and the cycle
                # (load, park, load, park) started again.
                log('REVIVE_REFUSED reason=player-supplies-caption '
                    'caller=%s' % caller)
                return False
            self._revive_thread = threading.Thread(
                target=self._do_revive, args=(caller,),
                name='sotto-revive', daemon=True)
        # THE IMMEDIATE PAINT, BEFORE THE THREAD. A repair control that looks
        # dead for the half second the child takes to die trains the owner to
        # click it again -- and the second click is the one that gets refused.
        self.apply_panel_state(self.REVIVE_PAINT, 'busy')
        self._revive_thread.start()
        return True

    def _do_revive(self, caller):
        """The worker half of the repair control. See revive_worker."""
        try:
            bridge = self.bridge
            pid = getattr(getattr(bridge, 'child', None), 'pid', None)
            log(f'REVIVE_REQUESTED caller={caller} '
                f'had_bridge={str(bridge is not None).lower()} pid={pid}')
            self._reload_policy.stop()
            self._paused = False
            self._external_parked = False
            self._vram_parked = False
            if bridge is not None:
                bridge.stop('revive')
                bridge.pending_error = None
                bridge.no_audio = False
                bridge.no_audio_evidence = None
                bridge.no_audio_evidence_at = 0.0
                self.bridge = None
                log('REVIVE_CLEARED pending_error=None no_audio=False')
            started = self.start_worker('revive')
            new_pid = getattr(getattr(self.bridge, 'child', None), 'pid', None)
            log(f'REVIVE_DONE caller={caller} started={str(started).lower()} '
                f'pid={new_pid}')
        except Exception as exc:  # a repair control must not kill the shell
            log(f'REVIVE_FAILED caller={caller} error={exc!r}')
        finally:
            with self._revive_lock:
                self._revive_thread = None

    #: SEGUNDOS SEM LEGENDA NOVA ANTES DE A JANELA SUMIR SOZINHA. O dono: a legenda
    #: fica o tempo inteiro. Cada push rearma; sem fala nova, esconde.
    CAPTION_IDLE_HIDE_S = 6.0

    def _arm_caption_idle_hide(self):
        """Rearma o temporizador que esconde a legenda sem fala nova.

        Cada legenda empurrada rearma; se NENHUMA chegar em CAPTION_IDLE_HIDE_S, a
        janela esconde e o painel volta a mostrar a legenda dele (via show(False), que
        escreve data-caption-window=off). A sequencia impede que um temporizador
        velho esconda uma legenda nova.
        """
        import threading as _threading
        try:
            prev = getattr(self, '_caption_idle_timer', None)
            if prev is not None:
                try:
                    prev.cancel()
                except Exception:
                    pass
            seq = int(getattr(self, '_caption_idle_seq', 0) or 0) + 1
            self._caption_idle_seq = seq
            timer = _threading.Timer(float(self.CAPTION_IDLE_HIDE_S), self._caption_idle_hide, args=(seq,))
            timer.daemon = True
            self._caption_idle_timer = timer
            timer.start()
        except Exception as exc:  # noqa: BLE001
            try:
                log(f'CAPTION_IDLE_ARM_FAILED error={exc!r}')
            except Exception:
                pass

    def _blank_caption_window(self, reason):
        """TIRA OS PIXELS sem desligar o interruptor do dono.

        MEDIDO 2026-10-17, o defeito que isto corrige, no log:
            21:43:36.719  PANEL_SURFACE surface=strip reason=float-on window=380x220@(770,812)
            21:43:51.360  CAPTION_WINDOW_IDLE_HIDDEN after_s=6.0 reason=no-caption
            21:43:51.362  STRIP_HEIGHT from=220 to=40 reason=surface-strip-float-off
            21:43:51.376  PANEL_SURFACE surface=strip reason=float-off window=380x40@(770,992)

        Seis segundos sem legenda e o botao DESLIGAVA-SE SOZINHO: o
        `_caption_idle_hide` chamava `show_caption_window(False)`, que escreve
        `data-caption-window="off"`, e a pagina -- que pinta o `aria-pressed` a
        partir desse atributo -- voltava a off. O dono nunca tinha tocado no botao
        e mesmo assim a barra cresce e caia sozinha.

        Sao DOIS factos e nao um: o interruptor e dele, a janela e um pixel. O
        silencio limpa o pixel; a proxima legenda volta a escreve-lo sem tocar em
        nada. E `hide_panel` usa a MESMA funcao: esconder o painel ja nao pode
        matar a legenda, porque uma legenda "conectada a um painel" era
        exactamente o que ele proibiu.

        NAO escreve `data-caption-window`, e por isso o botao fica como o dono o
        deixou."""
        ov = getattr(self, 'caption_overlay', None)
        if ov is None:
            # UMA PRESSAO DURANTE O ARRANQUE NAO SE PERDE (2026-11-03).
            # MEDIDO no dono: Ctrl+Space as 03:22:19.842 com
            # `LIVE_ENABLED on=true` e NADA no ecra -- o overlay nativo ainda
            # nao existia, a chamada devolvia False e o pedido morria ali.
            # Agora fica guardado e e' aplicado no instante em que a janela
            # passa a existir.
            self._caption_show_pending = bool(on)
            log('CAPTION_WINDOW_DEFERRED on=%s reason=no-overlay-yet'
                % str(bool(on)).lower())
            return False
        self._caption_window_shown = False
        # A FONTE MUDOU: o slot e' do instante ANTERIOR (dono, 2026-10-30).
        self._source_epoch = int(getattr(self, '_source_epoch', 0)) + 1
        self._caption_pending = None
        self._external_last_text = ''   # a fonte mudou: nada herda a frase velha
        def _blank():
            # O TEXTO GUARDADO TAMBEM VAI (2026-10-30). `show(False)` so' esconde
            # a janela: o `text`/`previous` do overlay continuavam la', e o
            # proximo `show(True)` REPINTAVA a legenda velha -- a cadeia
            # video-novo -> blank -> HOLD -> legenda antiga volta.
            ov.hide()
            ov.show(False)
        try:
            self._post(_blank)
        except Exception:  # noqa: BLE001
            pass
        log(f'CAPTION_WINDOW_BLANKED reason={reason} '
            f'epoch={self._source_epoch} wanted='
            f'{str(bool(getattr(self, "_caption_wanted", False))).lower()}')
        return True

    def _caption_idle_hide(self, seq):
        """Esconde a janela se NENHUMA legenda chegou depois de armar (stale-safe)."""
        try:
            if int(getattr(self, '_caption_idle_seq', 0) or 0) != int(seq):
                return
            if not getattr(self, '_caption_window_shown', False):
                return
            # VIDEO EM PAUSA SEGURA A LINHA DO PLAYER (2026-11-03). MEDIDO na
            # sessao do dono: `paused=true` em t=697, as duas linhas do player
            # ainda na janela, e o cao de guarda publicou
            # `CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s` -- a legenda
            # desaparecia da tela com o video parado a mostra-la. Em pausa nao
            # chega nada de novo de NINGUEM, logo ausencia de legenda nao e'
            # ausencia de conteudo: re-arma e nao apaga.
            if (getattr(self, 'yt_source_paused', False)
                    and getattr(self, '_last_caption_was_player', False)):
                self._arm_caption_idle_hide()
                return
            self._blank_caption_window('no-caption-for-%ss' % (self.CAPTION_IDLE_HIDE_S,))
        except Exception as exc:  # noqa: BLE001
            try:
                log(f'CAPTION_WINDOW_IDLE_HIDE_FAILED error={exc!r}')
            except Exception:
                pass


    #: O ORCAMENTO DO ECRa, EM MILISSEGUNDOS (2026-11-03). Do instante em que o
    #: audio que a linha descreve acabou ate' ao pixel. NAO e' um numero de
    #: gosto: o worker entrega um bloco de 560 ms e o decode de um bloco custa
    #: 120-400 ms nesta maquina, logo um orcamento abaixo de ~1 s esta' a pedir
    #: ao decode que nao corra. 1500 ms e' o mesmo numero da aceitacao do Alt+C
    #: (1,5 s para a primeira legenda), para nao haver duas reguas no repo --
    #: e o passo que o le' diz quantas vezes ele estourou, em vez de decidir se
    #: a legenda "parece" atrasada.
    CAPTION_BUDGET_MS = 1500

    #: A BANDA DO SEGURA INTENCIONAL (2026-11-03). MEDIDO tres vezes na sessao
    #: do dono (17:43:02, 17:43:11, 17:40:47): `queue_ms=1504`, sempre. O painel
    #: segura a cauda da linha ate' `COMMIT_MAX_HOLD_MS` (1500 ms,
    #: `caption-formulation.js:150`) quando nao chega fragmento novo -- ou seja,
    #: quando o audio ficou em silencio. O numero existe para o log distinguir
    #: "o ecra esta' atrasado" de "o painel estava a esperar, de proposito".
    CAPTION_HOLD_BAND_MS = (1490, 1520)

    def _caption_lag_note(self, audio_ms, queue_ms=0, kind='partial'):
        """Guarda a idade de UMA legenda pintada e publica o resumo da janela.

        O resumo existe porque uma linha por legenda responde "esta linha estava
        atrasada?", e o dono pergunta "o Sotto esta' atrasado?" -- que e' uma
        pergunta sobre a SERIE. A cada 25 amostras sai
        `CAPTION_LAG_STATS n=.. p50=.. p90=.. max=.. over=..` com o orcamento
        ao lado, que e' o que faz um log passar a gritar sozinho.
        """
        # A JANELA LEVA O SEGURA JUNTO (medido 2026-11-04). `over` e `held` eram
        # CONTADORES DE VIDA publicados na MESMA linha de uma janela de 200
        # amostras: a sessao do dono lia `n=200 p50=182 p90=1645 max=23844
        # over=162 held=119`, que se le' como "81 % estouraram" quando 162 era
        # o acumulado desde o arranque. Serie e acumulado na mesma frase e' o
        # mesmo defeito de instrumento que ja' custou dois numeros errados aqui.
        # `over`/`held` ficam (ha' quem os leia); a JANELA publica `over_win`
        # e `held_win`, que sao os que respondem "como esta' agora".
        low, high = self.CAPTION_HOLD_BAND_MS
        held = queue_ms is not None and low <= int(queue_ms) <= high
        if held:
            self._caption_hold = int(getattr(self, '_caption_hold', 0)) + 1
        # SO' A LINHA AO VIVO JULGA O ORCAMENTO (medido 2026-11-04). Uma linha
        # `final` descreve audio que acabou segundos antes por construcao: a
        # sessao do dono (608 pinturas) tinha `p90=14140 max=166615` e **41 %**
        # de estouros, mas as amostras grandes eram TODAS `kind=final`
        # (`CAPTION_APPLIED text="Can you hear me? Mmm." kind=final audio_ms=166615`)
        # e a via viva mede `p50=581 ms`. Contar as duas na mesma regua e' o
        # mesmo erro que publicar acumulado ao lado de serie. O numero continua
        # no log (`kind=`), o veredicto nao o conta.
        live = (kind == 'partial')
        blown = live and audio_ms > self.CAPTION_BUDGET_MS
        if blown:
            self._caption_lag_blown = int(getattr(self, '_caption_lag_blown', 0)) + 1
        ages = getattr(self, '_caption_ages', None)
        if ages is None:
            ages = self._caption_ages = []
        ages.append((int(audio_ms), bool(held), bool(blown), live))
        del ages[:-200]
        if len(ages) % 25 == 0:
            ordered = sorted(a for a, _h, _b, _l in ages)
            n = len(ordered)
            over_win = sum(1 for _a, _h, b, _l in ages if b)
            held_win = sum(1 for _a, h, _b, _l in ages if h)
            live_win = sum(1 for _a, _h, _b, lv in ages if lv)

            def pct(p):
                return ordered[min(n - 1, int(round(p * (n - 1))))]

            log(f'CAPTION_LAG_STATS n={n} p50={pct(0.5)} p90={pct(0.9)} '
                f'max={ordered[-1]} over={self._caption_lag_blown} '
                f'held={int(getattr(self, "_caption_hold", 0))} '
                f'over_win={over_win} held_win={held_win} live_win={live_win} '
                f'budget_ms={self.CAPTION_BUDGET_MS}')

    def _drain_caption_pending(self):
        """Pinta o que esta' no slot. Corre na thread `sotto-caption-paint`."""
        ov = getattr(self, 'caption_overlay', None)
        if ov is None:
            return
        instant = bool(getattr(self, '_caption_pending_instant', False))
        # O CUE DO PLAYER VIAJA AO LADO DO TEXTO (2026-11-03). `caption_overlay`
        # ganhou o motor que revela palavra a palavra NO RELOGIO DO YOUTUBE
        # (`_PlayerCue`), mas ate' aqui o shell chamava `set_text(text, prev,
        # instant)` -- sem `cue=` o overlay recebe `instant=True` e desenha o
        # cue INTEIRO no instante da chegada, que e' exactamente o defeito que o
        # dono descreve. O slot segue o mesmo caminho do `instant`.
        cue = getattr(self, '_caption_pending_cue', None)
        self._caption_drain_posted = False
        pending = getattr(self, '_caption_pending', None)
        coalesced = int(getattr(self, '_caption_coalesced', 0))
        if pending is None:
            return
        enqueued, new_text, new_prev, epoch = pending
        self._caption_pending = None
        # UM TEXTO DE EPOCH GASTO NAO PINTA -- e' o jumpscare (2026-10-30).
        cur = int(getattr(self, '_source_epoch', 0))
        if epoch != cur:
            log(f'CAPTION_DROP_EPOCH enq={epoch} cur={cur} '
                f'text={json.dumps((new_text or "")[:60])}')
            return
        age_ms = int((time.time() - enqueued) * 1000)
        try:
            ov.set_work_area(self.work_area(),
                             (self.display or {}).get('scaleFactor') or 1.0)
            ov.set_text(new_text, new_prev, instant, cue=cue)
            ov.show(True)
            self._overlay_pushes += 1
            # O INSTANTE DA PRIMEIRA PINTURA (2026-10-26). A linha de aceitacao
            # "Alt+C -> legenda no ecra em 1,5 s" nao tinha instrumento: a PRESSao
            # esta no log desde sempre (`HOTKEY_PRESSED`, com o carimbo de tempo de
            # `log()`), mas a PINTURA so aparecia em `count=1/50/500` e nas linhas
            # `CAPTION_OVERLAY_LAG` -- logo a segunda legenda da sessao nao deixava
            # rasto nenhum, e nao havia como medir diferenca nenhuma. Esta linha sai
            # UMA vez por legenda que NASCE (texto vazio -> texto), que e exactamente
            # o evento que o dono ve, com o `instant` do caminho (o YouTube entrega o
            # prefixo ja revelado) e o hwnd. Nao muda o desenho: escreve no log.
            was_blank = not (getattr(self, '_caption_painted', '') or '').strip()
            self._caption_painted = new_text or ''
            if was_blank and (new_text or '').strip():
                log(f'CAPTION_PAINT instant={str(bool(instant)).lower()} '
                    f'hwnd={ov.hwnd} text={json.dumps(new_text[:60])}')
            if age_ms >= 100:
                log(f'CAPTION_OVERLAY_LAG age_ms={age_ms} '
                    f'count={self._overlay_pushes} '
                    f'text={json.dumps(new_text[:60])}')
            # ── A DISCREPANCIA ENTRE O AUDIO E O ECRa (2026-11-03) ─────────
            # ORDEM DO DONO, verbatim: *"tu nao tem a porra de um teste ou log
            # que mostra a discrepancia entre audio detectado e display na tela?
            # nao tem nada que grita que o budget de ter mostrado ja passou do
            # ponto?"* -- nao tinha. O `CAPTION_OVERLAY_LAG` mede a FILA (do
            # enfileirar ao pintar), e a fila era o menor dos dois atrasos: o
            # audio que a linha descreve ja' podia ter acabado segundos antes.
            # `tap_ms` e' o instante de parede em que o bloco que FECHOU a linha
            # entrou no worker; a diferenca ate' aqui e' a idade do audio que o
            # dono esta' a ler. Uma linha por legenda pintada, com o veredicto.
            _tap = getattr(self, '_caption_pending_tap_ms', None)
            if _tap:
                audio_ms = int(time.time() * 1000.0) - int(_tap)
                self._caption_lag_note(
                    audio_ms, queue_ms=age_ms,
                    kind='final' if getattr(self, '_last_push_final', False)
                    else 'partial')
                log(f'CAPTION_PAINT_LAG audio_ms={audio_ms} queue_ms={age_ms} '
                    f'budget_ms={self.CAPTION_BUDGET_MS} '
                    f'over={str(audio_ms > self.CAPTION_BUDGET_MS).lower()} '
                    f'coalesced={coalesced} '
                    f'text={json.dumps(new_text[:60])}')
                if audio_ms > self.CAPTION_BUDGET_MS:
                    # O GRITO. Uma linha propria para que um `grep BASTAO`
                    # responda a pergunta "quantas vezes o orcamento estourou?"
                    # sem ler o resto.
                    log(f'CAPTION_BUDGET_BLOWN audio_ms={audio_ms} '
                        f'budget_ms={self.CAPTION_BUDGET_MS} '
                        f'queue_ms={age_ms} blown={self._caption_lag_blown} '
                        f'text={json.dumps(new_text[:60])}')
            if self._overlay_pushes in (1, 50, 500):
                log(f'CAPTION_OVERLAY_PUSH count={self._overlay_pushes} '
                    f'visible={str(ov.visible).lower()} hwnd={ov.hwnd} '
                    f'text={json.dumps(new_text[:60])}')
            if coalesced:
                # NENHUMA FALA DESAPARECE EM SILENCIO (2026-11-03): o slot e'
                # um so' e a chegada seguinte o substitui -- juntar e' a cura,
                # mas o numero tem de aparecer. `coalesced=2` diz que DUAS
                # chegadas distintas se juntaram nesta pintura; `text` mostra
                # exactamente o que o dono leu.
                self._caption_coalesced = 0
                log(f'CAPTION_COALESCE coalesced={coalesced} '
                    f'audio_ms={int(time.time() * 1000.0) - int(_tap or 0)} '
                    f'text={json.dumps(new_text[:120])}')
        except Exception as exc:  # noqa: BLE001
            log(f'CAPTION_OVERLAY_PUSH_FAILED error={exc!r}')

    def _caption_paint_wake(self):
        """Acorda a thread que pinta a legenda (cria-a na primeira vez)."""
        ev = getattr(self, '_caption_event', None)
        if ev is None:
            ev = self._caption_event = threading.Event()
            threading.Thread(target=self._caption_paint_loop,
                             name='sotto-caption-paint', daemon=True).start()
        ev.set()

    def _caption_paint_loop(self):
        """UM slot, UMA thread: pinta sempre o texto MAIS RECENTE.

        O `_drain` ja' e' dono do slot (`_caption_pending`), por isso a
        regra de "nunca um texto velho" nao muda -- muda so' QUEM a corre.
        Uma excepcao aqui nao pode matar a thread: sem ela a legenda nunca
        mais pinta, e um silencio e' pior do que uma linha feia.
        """
        ev = self._caption_event
        while True:
            ev.wait(0.5)
            ev.clear()
            self._caption_drain_posted = False
            try:
                self._drain_caption_pending()
            except Exception as exc:  # noqa: BLE001
                try:
                    log('CAPTION_PAINT_FAILED error=%r' % (exc,))
                except Exception:
                    pass

    def push_caption_to_window(self, text, previous=None, credits=None, instant=False,
                               cue=None, rows=None, tap_ms=None):
        """A legenda para a JANELA PROPRIA. Silencioso se ela ainda nao existir."""
        ov = getattr(self, 'caption_overlay', None)
        if ov is None:
            return False
        # THE PLAYER'S ROWS TRAVEL AS ONE TEXT, ONE PER LINE (2026-10-29).
        # `caption_overlay._layout` sees the '\n' and draws them AS GIVEN --
        # it never calls `caption_wrap` on this channel. The trailing
        # terminator marks even a ONE-row window as pre-broken, so a lone
        # long row cannot be re-wrapped at a word YouTube did not break at.
        # A LEGENDA DO PLAYER MANDA NA TELA, E O ASR NAO LHE PASSA POR CIMA
        # (2026-11-03). MEDIDO na sessao do dono, 00:01:41-00:01:46: o ASR
        # aplicou `"Pra conseguir."` no overlay AS 00:01:42.891 e o YouTube so
        # comecou a pintar as 00:01:44.868 -- logo durante dois segundos e meio
        # a janela mostrava uma frase que o player NAO estava a mostrar. Foi
        # isso que ele fotografou: duas legendas diferentes no mesmo ecra.
        # A regra: enquanto o player estiver a fornecer linhas (janela de 2 s
        # desde a ultima leitura externa boa), o caminho do ASR NAO empurra
        # nada. `rows=` e `instant=True` sao o caminho do player e passam.
        self._last_caption_was_player = rows is not None
        if rows is None and not instant:
            owned_until = float(getattr(self, "_yt_owner_until", 0.0) or 0.0)
            if time.monotonic() < owned_until:
                self._asr_dropped = int(getattr(self, "_asr_dropped", 0)) + 1
                if self._asr_dropped in (1, 10, 50, 200) or self._asr_dropped % 500 == 0:
                    log("CAPTION_OVERLAY_DROP reason=external-captions "
                        "dropped=%d text=%s"
                        % (self._asr_dropped, json.dumps(str(text or "")[:60])))
                return False
        if rows:
            import youtube_reveal
            text = youtube_reveal.rows_text(rows)
            # A rows window is ALREADY the player's painted frame: it must
            # never reveal again (the engine would re-time a window the player
            # already revealed).
            instant = True
        # O INTERRUPTOR DO DONO E A CONDICAO. Sem isto cada linha levantava a
        # janela sozinha -- medido no log de 2026-10-17: `CAPTION_OVERLAY_PUSH
        # count=1 visible=true hwnd=1775132` sem nenhum clique no botao -- e o
        # proprio texto capturado chegava ("15 mil ha 8 h", o contador de
        # visualizacoes do YouTube), que nao e legenda nenhuma. Ele pediu que o
        # botao seja o que liga isto; enquanto ele nao ligar, a janela nao existe.
        if not getattr(self, '_caption_wanted', False):
            return False
        self._caption_window_shown = True
        # ── A LEGENDA NAO ESPERA NA FILA DA UI (2026-10-23) ────────────────
        # O dono, verbatim: *"mas ta ate fora de sync, porra"*.
        #
        # MEDIDO na sessao das 22:32 (pid 68572): dois
        # `CAPTION_OVERLAY_PUSH_ENTER ... post=ui` (22:32:46.109 e
        # 22:32:47.484) NUNCA tiveram o `CAPTION_OVERLAY_PUSH` correspondente --
        # o texto entrou na fila da thread de UI e nao foi pintado, enquanto o
        # player continuava a andar. A fila E o atraso: cada item leva o texto
        # do instante em que foi ENFILEIRADO, e a UI pinta-os por ordem.
        #
        # Cura: UM so slot. O push novo SOBRESCREVE o que ainda nao foi pintado
        # e a thread de UI pinta sempre o MAIS RECENTE -- nunca um texto velho.
        # Fica um unico `_post` em voo; os seguintes so substituem o slot.
        # A idade vai para o log (`CAPTION_OVERLAY_LAG age_ms=`), para o desvio
        # deixar de ser impressao e passar a ser numero.
        #
        # A trava do `_post` em voo TEM VALIDADE (`2 s`): se um post se perder,
        # sem isto a legenda nunca mais voltava a ser pintada -- trocava-se um
        # atraso por um silencio.
        now = time.time()
        text = text or ''
        previous = previous or ''
        # NAO SE DEITA FALA FORA (2026-11-03). O slot e' UM so' e a chegada
        # seguinte SOBRESCREVE a que ainda nao foi pintada -- o que esta' certo
        # contra o atraso e ERRADO contra o conteudo. MEDIDO na sessao do dono
        # (pid 4992, 17:17:59-17:18:03): cinco `CAPTION_IN` distintos em 4 s e
        # UMA linha publicada com os cinco encadeados; no caminho do YouTube a
        # mesma janela perdia as linhas interiores. Duas linhas DISTINTAS que
        # chegam antes do pixel agora ENGROSSAM uma a outra; uma linha nova que
        # ja' CONTEM a pendente (a re-emissao cumulativa) substitui-a, que e' o
        # caso em que juntar duplicaria.
        # A JANELA DO PLAYER NUNCA SE JUNTA A' ANTERIOR (medido 2026-11-04).
        # A regra de juntar existe para a HIPOTESE do ASR, que cresce e cujo
        # pedaco antigo pode nao estar contido no novo. A janela do player NAO
        # e' uma hipotese: o YouTube ja' decidiu o que esta' no ecra, e duas
        # janelas consecutivas de um cue a rolar sao DIFERENTES por desenho --
        # `['Have you ever had to kill a man?','No.']` seguida de
        # `['No.','Then this sword']` juntava as duas e o overlay pintava
        # QUATRO linhas, com uma linha costurada (`Then No.`). Medido com
        # `_main/youtube-land-replay-oracle.py` sobre as 16 amostras gravadas:
        # 11/16 amostras certas, 16 pinturas para 16 amostras com o texto
        # ERRADO. A janela e' autoridade -- substitui.
        _is_player_window = rows is not None
        _pending = getattr(self, '_caption_pending', None)
        _coalesced = 0
        if _pending and not _is_player_window:
            _old = (_pending[1] or '').strip()
            _new = text.strip()
            if _old and _new and _old != _new and _old not in _new:
                text = _old + ' ' + text
                _coalesced = int(getattr(self, '_caption_coalesced', 0)) + 1
                self._caption_coalesced = _coalesced
                _old_tap = getattr(self, '_caption_pending_tap_ms', None)
                if _old_tap and tap_ms:
                    tap_ms = min(int(_old_tap), int(tap_ms))
            elif _old and _new and _old == _new:
                # REPETICAO EXACTA da mesma linha: nao ha' nada a juntar.
                _coalesced = int(getattr(self, '_caption_coalesced', 0)) + 0
        self._caption_pending = (now, text, previous,
                                 int(getattr(self, '_source_epoch', 0)))
        # O `instant` VIVE NO SLOT (2026-11-03): a pintura deixou de ser
        # uma closure para ser uma thread propria, e um caminho que
        # depende de uma variavel local de OUTRA funcao nao sobrevive a
        # essa mudanca.
        self._caption_pending_instant = bool(instant)
        #: O cue com o relogio do player (`youtube_reveal.rows_from_cues` + `t`
        #: + `at`), ao lado do `instant`. `None` = nao ha' relogio e o texto
        #: viaja sozinho, como antes.
        self._caption_pending_cue = cue
        #: QUANDO O AUDIO DESTA LINHA ACABOU, no relogio de parede (2026-11-03).
        #: Vem do worker (`tap_ms`) e atravessa o slot como o `instant` e o `cue`:
        #: a idade que interessa ao dono nao e' a da FILA, e' a do AUDIO -- e sem
        #: este campo a janela pintava sem saber de que instante era o que pinta.
        self._caption_pending_tap_ms = tap_ms
        dbg = self._overlay_pushes < 3
        if dbg:
            # A ETIQUETA ACOMPANHA O MECANISMO (2026-11-03): a pintura deixou de
            # ser um `_post` para a thread de UI, e uma etiqueta `post=ui` num
            # log que ja' pinta noutra thread e' uma pista FALSA para quem
            # diagnosticar.
            log(f'CAPTION_OVERLAY_PUSH_ENTER ov={ov.hwnd} '
                f'thread=caption-paint')
        in_flight = (getattr(self, '_caption_drain_posted', False)
                     and (now - getattr(self, '_caption_drain_posted_at', 0.0)) < 2.0)
        if in_flight:
            # Ja ha um push em voo: o slot foi substituido e a UI vai pintar o
            # texto NOVO quando chegar. Nao se enfileira mais nada.
            self._arm_caption_idle_hide()
            return True
        self._caption_drain_posted = True
        self._caption_drain_posted_at = now
        try:
            # A PINTURA NAO MORA NA THREAD DE UI (2026-11-03, MEDIDO).
            # `CAPTION_OVERLAY_PUSH_ENTER 04:50:41.528` -> `CAPTION_PAINT
            # 04:50:42.645`: 1,1 s de atraso porque o `_post` espera que a
            # thread de UI esteja livre, e ela passa MINUTOS dentro da
            # navegacao do WebView2 (`WEBVIEW_NAV start -> dom` = 25 s
            # medidos). O overlay e' uma janela Win32 com thread propria
            # (`caption_overlay._thread_main`), logo a pintura nao precisa
            # de pywebview para nada. Uma thread so' para a legenda corta
            # a ultima dependencia entre a legenda e o painel.
            self._caption_paint_wake()
        except Exception as exc:  # noqa: BLE001
            # A THREAD NAO PODE SER A UNICA SAIDA: se ela nao arrancar,
            # este processo pinta no sitio onde pintava antes.
            log('CAPTION_PAINT_THREAD_FAILED error=%r' % (exc,))
            self._caption_drain_posted = False
            self._drain_caption_pending()
        self._arm_caption_idle_hide()
        return True

    def _fit_caption_window(self, needed):
        """Obsolete: the native overlay sizes itself to the text it renders."""
        return False

    def show_caption_window(self, on):
        """Mostra ou esconde a janela da legenda, e diz o estado a pagina."""
        ov = getattr(self, 'caption_overlay', None)
        if ov is None:
            return False
        try:
            if on:
                self._caption_window_shown = True

                def _show():
                    ov.set_work_area(self.work_area(),
                                     (self.display or {}).get('scaleFactor') or 1.0)
                    ov.show(True)

                self._post(_show)
            else:
                self._caption_window_shown = False
                self._post(lambda: ov.show(False))
            # E O PAINEL ESCONDE A LEGENDA DELE -- MAS SO QUANDO ESTA JANELA ESTA MESMO
            # A MOSTRAR. O dono pediu a legenda INDEPENDENTE do painel (*"nao acoplado"*),
            # e sem isto as duas apareciam ao mesmo tempo. Ao mesmo tempo, isto e a REDE:
            # enquanto a janela nova nao estiver confirmada por ele, o `data-caption-window`
            # so e escrito DEPOIS de o `show()` ter corrido, portanto se a janela falhar a
            # legenda do painel fica onde estava -- ele nunca fica sem legenda nenhuma.
            #
            # UM `exec_js` POR TRANSICAO, nao por legenda: o atributo vive no documento do
            # painel e a folha que o le e a `zip-overlay.css`, que e a ultima a carregar.
            #
            # E NAO ESPERA PELA RESPOSTA (2026-11-03). Era `self.window.evaluate_js`,
            # que bloqueia em `semaphore.acquire()` sem limite
            # (`webview/platforms/edgechromium.py:160 `) ate' o UI thread correr o
            # script -- medido na sessao do dono: a pressao das 02:45:24.645 so'
            # deixou `LIVE_ENABLED on=false` as 02:45:51.919, **27,3 s** depois,
            # dentro de um `UI_WATCHDOG_STRIKE`/`RECOVERED` de 27 s. O interruptor
            # inteiro ficava atras do trabalho de UI que nao e' dele. `exec_js_post`
            # e' o mesmo caminho que `emit`/`arm_paint_ack` ja' usam: `BeginInvoke`,
            # ordem preservada, e o chamador SEGUE.
            try:
                posted = self.exec_js_post(
                    'document.documentElement.setAttribute('
                    '"data-caption-window", %s)' % ('"on"' if on else '"off"'))
                if not posted:
                    log(f'CAPTION_WINDOW_PANEL_MARK_FAILED on={on} '
                        'reason=no-post posted=false')
            except Exception as exc2:  # noqa: BLE001
                log(f'CAPTION_WINDOW_PANEL_MARK_FAILED on={on} error={exc2!r}')
            return True
        except Exception as exc:  # noqa: BLE001
            log(f'CAPTION_WINDOW_SHOW_FAILED on={on} error={exc!r}')
            return False

    def on_worker_caption(self, text, meta):
        # A LINHA DE UM WORKER MORTO NAO PINTA NO NOVO (troca de PROCESSO).
        bridge = getattr(self, 'bridge', None)
        # THE PLAYER'S OWN CAPTIONS WIN WHILE THEY EXIST (owner, 2026-10-17).
        # A YouTube/Stremio line is already synchronised by the player; mixing
        # the ASR hypothesis into the same row would produce two half-lines.
        source = ''
        if isinstance(meta, dict):
            source = str(meta.get('source') or '')
        if self.external_captions_active and not source.startswith('external:'):
            self.external_suppressed += 1
            if self.external_suppressed in (1, 100, 1000):
                log(f'EXTERNAL_CAPTIONS_ASR_SUPPRESSED count={self.external_suppressed}')
            return
        # `emit_async`, NAO `emit`: `emit` espera pela pagina (ate' 10 s) na thread
        # que le' o stdout do worker -- a pagina ocupada atrasava a LEITURA.
        self.emit_async('caption', {'text': text, 'meta': meta})
        # O INSTANTE DO AUDIO QUE ACABOU DE SEGUIR PARA O ECRa (2026-11-03).
        # A PINTURA NESTA MAQUINA E' O PAINEL (o overlay nativo responde
        # `CAPTION_OVERLAY_THEME_DEFERRED reason=no-overlay`), logo o pixel
        # acontece em `_caption_applied`, do outro lado da ponte. Sem guardar
        # aqui o `tap_ms` que saiu, o lado do painel nao tem contra o que medir
        # a idade e o orcamento nao tem como estourar.
        _meta = meta if isinstance(meta, dict) else {}
        #: A LINHA ESTA' FECHADA? (2026-11-03). Uma linha `final` so' fecha quando
        #: o worker a FECHA, e com o audio em silencio a cauda fecha minutos
        #: depois -- medido 59,9 s as 17:39:38 (desktop mudo). Sem esta etiqueta
        #: o mesmo numero mistura "o ecra esta' atrasado" com "a linha acabou de
        #: fechar", que sao perguntas diferentes.
        self._last_push_final = bool(_meta.get('final'))
        self._last_push_tap_ms = _meta.get('tap_ms') or self._last_push_tap_ms
        self._last_push_at = time.time()
        # AMOSTRADO (2026-11-04): esta linha saia a CADA push -- 51 553 no log
        # do dono -- e o que um leitor procura nela e' "a ponte entregou?", que
        # um em cada 20 responde igual. O `final` de uma linha sai sempre: e' o
        # fecho, e um fecho que falta e' um defeito.
        self._caption_sent_count = getattr(self, '_caption_sent_count', 0) + 1
        if _meta.get('final') or self._caption_sent_count == 1 or (
                self._caption_sent_count % 20 == 0):
            log(f'BRIDGE_CAPTION_SENT delivered=async n={self._caption_sent_count} '
                f'final={str(bool(_meta.get("final"))).lower()} '
                f'text={json.dumps(text)}')
        # ── O CONTRATO DO AUDIO, NO LOG (2026-11-03) ──────────────────────
        # ORDEM DO DONO: *"tu nao tem a porra de um teste ou log que mostra a
        # discrepancia entre audio detectado e display na tela?"*. O log tinha
        # SO' o texto -- nem `start`, nem `end`, nem `final`, nem `tap_ms`. Sem
        # eles, "a legenda esta' atrasada" era impossivel de provar e de refutar:
        # nao havia um campo com que comparar. Esta linha e' o contrato inteiro
        # que o worker manda, na chegada, com a idade do audio ja' calculada.
        _m = meta if isinstance(meta, dict) else {}
        _tap = _m.get('tap_ms')
        _age_ms = None
        if _tap:
            try:
                _age_ms = int(time.time() * 1000.0) - int(_tap)
            except (TypeError, ValueError):
                _age_ms = None
        log('CAPTION_IN start=%s end=%s final=%s stable=%s tap_ms=%s age_ms=%s '
            'text=%s'
            % (_m.get('start'), _m.get('end'),
               str(bool(_m.get('final'))).lower(),
               str(bool(_m.get('stable'))).lower(),
               _tap, _age_ms, json.dumps(text[:60])))
        if _age_ms is not None and _age_ms > self.CAPTION_BUDGET_MS:
            # A MESMA REGUA NA CHEGADA: se o audio ja' chegava velho, o defeito
            # e' do worker/e do tap, nao do desenho -- e o log tem de dizer QUAL
            # das duas metades estourou.
            log(f'CAPTION_ARRIVAL_BLOWN age_ms={_age_ms} '
                f'budget_ms={self.CAPTION_BUDGET_MS} '
                f'text={json.dumps(text[:60])}')
        # E A JANELA PROPRIA DA LEGENDA RECEBE O MESMO TEXTO. O dono: *"a legenda ao vivo
        # deveria aparecer no MEIO EM BAIXO da minha tela"*. Uma janela propria e a unica
        # forma de ela pousar no fundo da TELA sem a barra no topo do mesmo caixote.
        if bridge is None or getattr(self, 'bridge', None) is bridge:
            self.push_caption_to_window(text, tap_ms=_tap)
        else:
            log('BRIDGE_CAPTION_DROP_SUPERSEDED reason=bridge-changed '
                f'text={json.dumps(text[:60])}')
        # A CLOSED line is the boundary a held reload waits for: the worker has
        # just committed a sentence, so restarting here does not cut the caption
        # the owner is reading. final is the worker's own word for a closed line.
        if isinstance(meta, dict) and meta.get('final') is True:
            self._reload_policy.boundary(closed=True, why='closed-line')

    def external_caption(self, text, source, final=False, instant=False, rows=None,
                        cue=None):
        """One line read from the PLAYER's own captions (YouTube/Stremio).

        THE OWNER'S TWO COMPLAINTS, 2026-10-18, both fixed HERE because this is
        the one place every external line passes through: the panel and the
        caption's own window are both fed from the line below, so a fix in the
        reader or in the page would fix only half of what he sees.

        THE STRAY "2" -- *"ainda ta aparecendo um '2' do nada na legenda"*. It is
        the PLAYER's own `>>`, measured: 25 of 219 sent lines and 31 of 9 937
        painted captions carried it. `clean_external_text` removes a leading
        marker and nothing else.

        THE FRAGMENTATION -- *"a legenda que passa do youtube pro sotto ... nao ta
        funcionando"*. It is not that the player sends fragments; the player's cue
        is CUMULATIVE, each one repeating the last and adding a few words, and
        every one of them arrived `final=true` (213 of 219). Closing each one as a
        sentence is what produced `"Responsible for the most ridiculous."` -- a
        capital and a full stop in the middle of a clause. So `final` is now
        DECIDED FROM THE TEXT: a cue that extends the previous one is a FORMING
        line whatever the player claims, and only a cue that does not extend it
        closes the line. That is the same split the ASR path already has.
        """
        text = clean_external_text(text)
        if not text:
            return False
        # EACH ROW IS CLEANED LIKE A LINE, not only the first: the `>>` marker
        # is per cue (measured on the 16 recorded samples: cue 1..N each carry
        # it), and `clean_external_text` only strips at the FRONT of what it
        # is given. The panel still gets the last line; the native overlay
        # gets the whole window.
        if rows:
            rows = [row for row in (clean_external_text(x) for x in rows) if row]
        prev = str(getattr(self, '_external_last_text', '') or '')
        if extends_previous(prev, text):
            final = False
        self._external_last_text = text
        # Only when the owner is actually looking at Sotto. While the panel is
        # hidden there is nothing to replace, and painting a second subtitle
        # over YouTube would be worse than doing nothing.
        if not (self.visible or getattr(self, '_caption_window_shown', False)):
            return False
        self.external_lines += 1
        if self.external_lines in (1, 50, 500) or final:
            log(f'EXTERNAL_CAPTION_SENT count={self.external_lines} '
                f'source={source} final={str(bool(final)).lower()} '
                f'text={json.dumps(text[:60])}')
        if not self.external_captions_active:
            self.external_captions_active = True
            self._external_since = time.monotonic()
        # O ESTACIONAMENTO ESPERA (2026-11-02): a primeira linha do player NAO mata
        # o worker. Ver `EXTERNAL_PARK_DELAY_S`.
        self._park_worker_when_settled(source)
        now = time.monotonic()
        meta = {
            'start': round(now, 2),
            'end': round(now + 0.01, 2),
            'chunk_start': round(now, 2),
            'chunks': [[round(now, 2), round(now + 0.01, 2), text]],
            'final': bool(final),
            'source': str(source or 'external:player'),
        }
        # A DEDICATED CHANNEL: the player's line must REPLACE the live box, not
        # be joined to the previous hypothesis. The panel handles this kind by
        # resetting the engine for that source, ingesting exactly one line and,
        # on `final`, committing it. MEASURED 2026-10-17: feeding it through
        # the ASR `caption` kind produced "previous. previous. current." in the
        # history, because the engine appends a new partial before its hold
        # timer commits the previous one.
        self.emit('external-caption', {'text': text, 'meta': meta})
        # O QUE CHEGOU AO ECRA, e nao so' o que se decidiu (2026-11-02). As tres
        # imagens do dono nao distinguiam "decidimos mal" de "pintamos mal": este
        # registo fecha essa separacao -- `rows` e' o numero de LINHAS enviadas ao
        # overlay e `lines` o texto de cada uma. Loga na mudanca, nunca por tick.
        _rows_for_log = list(rows or [text])
        _key = '\u2028'.join(_rows_for_log)
        if _key != getattr(self, '_external_rows_logged', ''):
            self._external_rows_logged = _key
            log('EXTERNAL_CAPTION_DRAWN rows=%d lines=%r'
                % (len(_rows_for_log), [r[:70] for r in _rows_for_log]))
        self.push_caption_to_window(text, instant=instant, rows=rows, cue=cue)
        if final:
            self._reload_policy.boundary(closed=True, why='external-line')
        return True

    def _park_worker_when_settled(self, source):
        """Estaciona o worker so' quando o player ja' serve linhas ha' um rato.

        MEDIDO 2026-11-02 na sessao do dono: 10 paragens e 10 recargas desde as
        20:00 -- cada uma mata e reabre um cliente WASAPI, e o audio dele pisca.
        Uma janela curta de legenda nao pode custar isso; so' um video a servir
        captions de forma continuada justifica libertar a VRAM.
        """
        since = getattr(self, '_external_since', None)
        if not since:
            self._external_since = time.monotonic()
            since = self._external_since
        age = time.monotonic() - float(since)
        if age < EXTERNAL_PARK_DELAY_S:
            if not getattr(self, '_external_park_deferred_logged', False):
                self._external_park_deferred_logged = True
                log('EXTERNAL_CAPTIONS_PARK_DEFERRED age_s=%.1f min_s=%.0f'
                    % (age, EXTERNAL_PARK_DELAY_S))
            return False
        return self._park_worker_for_external(source)

    def engine_park_reason(self):
        """O pedido de estacionamento publicado no `panel-visibility.json`."""
        return getattr(self, '_engine_park', None)

    def set_engine_park(self, reason):
        """Pede ao worker que LARGUE O MOTOR, sem matar o processo.

        ORDEM DO DONO, 2026-11-03, verbatim: *"tu nao consegue fazer o sotto se
        conectar ao audio atual inves de ficar matando o audio toda hora?"*.
        `bridge.stop()` matava o processo e com ele o cliente WASAPI -- a cada
        paragem o audio DELE piscava, e a volta custava 14-26 s de recarga. O
        pedido viaja no ficheiro que o worker JA' sonda (uma chave additive), e
        o worker larga o nemotron na thread do lote: um processo, um cliente de
        audio, nenhum blink.
        """
        reason = reason if isinstance(reason, str) and reason else None
        if getattr(self, '_engine_park', None) == reason:
            return False
        self._engine_park = reason
        try:
            log(f'ENGINE_PARK reason={reason or "off"}')
            self.publish_panel_visibility(f'engine-park-{reason or "off"}')
        except Exception as exc:  # noqa: BLE001 -- nunca derruba o caminho
            log(f'ENGINE_PARK_FAILED reason={reason or "off"} error={exc!r}')
        return True

    def _park_worker_for_external(self, source):
        """Larga o MOTOR AO VIVO enquanto o player fornece as legendas.

        O PROCESSO FICA. E' a diferenca que o dono pediu: o modelo e' o que
        custa VRAM, e o cliente de audio dele e' o que ele ouve a piscar.
        """
        if self._paused or self._external_parked:
            return False
        bridge = getattr(self, 'bridge', None)
        if bridge is None or getattr(bridge, 'child', None) is None:
            return False
        self._external_parked = True
        self.set_engine_park('captions')
        log(f'EXTERNAL_CAPTIONS_ENGINE_PARKED source={source} '
            f'pid={getattr(bridge.child, "pid", None)} '
            f'mode=engine-not-process')
        return True

    def park_worker_for_vram(self, free_mb):
        """Free the worker's CUDA context because another app needs the GPU."""
        if self._paused or self._external_parked or self._vram_parked:
            return False
        bridge = getattr(self, 'bridge', None)
        if bridge is None or getattr(bridge, 'child', None) is None:
            return False
        pid = getattr(bridge.child, 'pid', None)
        log(f'VRAM_GUARD_PARKING free_mb={free_mb:.0f} pid={pid} '
            f'mode=engine-not-process')
        # A GPU E' O MOTIVO LEGITIMO DE LARGAR O MOTOR (ordem do dono,
        # 2026-11-03) -- mas largar o MOTOR nao pede matar o PROCESSO, e era o
        # processo que levava o cliente WASAPI com ele. `vram` larga os dois
        # motores dentro do worker e deixa a captura e o audio acumulado.
        self._vram_parked = True
        self.set_engine_park('vram')
        self.apply_panel_state(
            'Paused - GPU in use by another app', 'idle',
            {'title': 'GPU busy',
             'body': 'Another application needs the GPU, so the transcription '
                     'engines were unloaded to free their VRAM. They reload when '
                     'the GPU is free again.'})
        return True

    def resume_after_vram(self, free_mb):
        """The GPU is free again: reload the engines if a panel is on screen."""
        if not self._vram_parked or self._paused:
            return False
        self._vram_parked = False
        if not (self.visible or getattr(self, '_caption_window_shown', False)):
            return False
        log(f'VRAM_GUARD_RESUMING free_mb={free_mb:.0f} mode=engine-not-process')
        if self.engine_park_reason() in ('vram', None):
            self.set_engine_park(None)
        return True

    def on_external_captions_released(self):
        """The player stopped showing captions: give the microphone back.

        THIS PATH WAS THE TREADMILL. MEASURED 2026-10-18, in the owner's own
        log: `WORKER_AUTOSTART=started reason=external-end` at 01:18:23 and again
        at 01:21:15 -- two fresh model loads three minutes apart, 1 245 MB
        resident, each followed by the device ladder spinning. `start_worker` is
        a DIRECT spawn, so calling it from here bypassed `WorkerReloadPolicy`
        entirely, and with it the `no_audio_backoff` (15 s base, doubling, 5 min
        ceiling) that exists for precisely the "there is no audio" case.

        The trigger is a UI element, not audio: the external reader polls every
        0.30 s and this fires whenever the player's caption node disappears for
        `RELEASE_S`. A player that blinks its caption layer therefore costs a
        full model load, and the cadence is the player's, not ours.

        THE SHELL IS DYING: DO NOT BRING THE WORKER BACK. Owner, 2026-10-20,
        verbatim: *"abrir ou fechar o sotto, principalemnte fechar, trava pra
        caralho meu pc. arruma."* -- and the owner's own log says why, with a
        number: at 20:50:50.070, 0.65 s before `SHELL_EXIT`, this very method
        logged `EXTERNAL_CAPTIONS_WORKER_RESUMED reason=player-stopped`. That
        worker was an ORPHAN: `os._exit` does not kill a child process, so
        after the app had closed a second worker loaded 1.2 GB of model and
        ran the capture ladder -- which BLOCKS for ~59 s on the owner's
        Bluetooth headset (MEASURED: `BRIDGE_LOAD_MS ms=67969` with
        `worker_load_s=8.75`, i.e. 68 s from the spawn of which 8.75 s is the
        model). The microphone does not come back because the app is gone; it
        comes back because the app is still there.
        """
        if self.exiting.is_set():
            log('EXTERNAL_CAPTIONS_WORKER_RESUME_SKIPPED reason=shell-exiting')
            return False
        if not self._external_parked:
            return False
        self._external_parked = False
        if self._paused:
            return False
        if not (self.visible or getattr(self, '_caption_window_shown', False)):
            return False
        # O PISO DE 45 s SAIU COM O PROCESSO (2026-11-03). Ele existia porque o
        # gatilho e' um elemento de UI (poll de 0,30 s) e cada `start_worker`
        # custava uma carga de modelo. Limpar um PEDIDO num ficheiro nao custa
        # nada: o throttle passou a ser o unico defeito que sobrava -- com ele o
        # motor ficava largado ate' 45 s DEPOIS de o player parar.
        now = time.monotonic()
        self._last_external_resume = now
        # O MOTOR VOLTA, O PROCESSO NUNCA SAIU (2026-11-03): o pedido de
        # estacionamento e' limpo e o worker recarrega o ao vivo sozinho.
        # SO' O PEDIDO DELE: os dois motivos dividem um campo, e a GPU (que
        # pode ter pedido o motor enquanto o player falava) nao e' libertada
        # por um release de legendas.
        if self.engine_park_reason() == 'captions':
            self.set_engine_park(None)
        log('EXTERNAL_CAPTIONS_ENGINE_RESUMED reason=player-stopped '
            'mode=engine-not-process')
        return True

    #: THE FLAGS THAT MAKE A RUN A MEASUREMENT. A measurement measures the
    #: PANEL or the SHELL -- its geometry, its edit mode, its outside click.
    #: It does NOT measure the player's captions, and `--no-hotkey` is the
    #: shell's OWN name for it: the help says "for MEASUREMENT runs", and a
    #: real run cannot work without Alt+C.
    MEASUREMENT_FLAGS = ('dump_dom', 'selftest', 'memory', 'no_hotkey',
                         'exit_after', 'probe_stats', 'probe_outside_click',
                         'probe_edit_mode')

    def _is_measurement_run(self, args=None):
        """The measurement flag this run carries, or '' for a normal run."""
        args = args if args is not None else getattr(self, 'args', None)
        for name in self.MEASUREMENT_FLAGS:
            if getattr(args, name, False):
                return name
        return ''

    def start_external_caption_watcher(self):
        """Start the UIA reader once per process (normal runs only)."""
        if self.external_caption_watcher is not None:
            return False
        # A MEDICAO NAO MEDE AS LEGENDAS DO PLAYER. MEASURED 2026-10-20: the
        # arm D of `_main/_strip-surface-probe.py` launched the shell with
        # `--probe-edit-mode --exit-after 25`; the reader adopted the OWNER's
        # YouTube window, started painting the caption lines, and that work
        # starved the UI thread -- the edit probe (a 2 s timer) NEVER RAN and
        # the arm died on its 70 s timeout. The same arm with the reader off
        # ran the whole sequence and exited clean (`SHELL_EXIT rc=0
        # reason=probe-edit-mode`).
        #
        # It is not only the arm: a measurement shell has no business
        # polling the owner's browser three times a second.
        measurement = self._is_measurement_run()
        if measurement:
            log(f'EXTERNAL_CAPTIONS_SKIPPED reason=measurement-run({measurement})')
            return False
        # THE EXTERNAL READER IS NOT THE WORKER. MEASURED 2026-10-18: launched
        # with SOTTO_NO_WORKER=1 the log said
        #   `EXTERNAL_CAPTIONS_SKIPPED reason=env`
        # because this gate used to ask the WORKER's autostart reason. Reading the
        # captions a player already shows costs NO model, NO audio device and NO
        # VRAM -- it is one UIA query every 300 ms against a window that is
        # already on screen. Tying it to the worker therefore switched OFF the
        # one caption path that still works with no worker at all, which is the
        # path the owner was testing (YouTube) when this was found.
        #
        # Its own switch is SOTTO_NO_EXTERNAL=1 and nothing else. If you ever want
        # it back under the worker flag, the reason must be the OTHER way round:
        # `--no-worker` must never imply "no captions at all".
        if os.environ.get('SOTTO_NO_EXTERNAL') == '1':
            log('EXTERNAL_CAPTIONS_SKIPPED reason=SOTTO_NO_EXTERNAL=1')
            return False
        self.external_caption_watcher = ExternalCaptionWatcher(self)
        self.external_caption_watcher.start()
        # THE REAL TRACK, ON ITS OWN THREAD. It answers one question -- what
        # is this video's own caption track -- and the watcher decides what
        # the caption box shows.
        if self.youtube_track_thread is None:
            self.youtube_track_thread = YouTubeTrackThread(self)
            self.youtube_track_thread.start()
        return True

    def start_click_watcher(self) -> bool:
        """Arm the outside-click watcher (see `OutsideClickWatcher`).

        O QUE `True` SIGNIFICA AQUI (mudou em 2026-10-23): a THREAD do loop esta
        viva. O `WH_MOUSE_LL` instala-se na primeira vez que o painel aparecer
        (`armed`), e sai quando ele se esconde. O aviso de falha fala da thread,
        nao do hook, porque e isso que este passo pode verificar.
        """
        self.click_watcher = OutsideClickWatcher(self)
        ok = self.click_watcher.start()
        if not ok:
            warn('OUTSIDE_CLICK_UNAVAILABLE the watcher thread did not start; '
                 'the panel still opens and closes with Alt+C')
        return ok

    def run_outside_click_probe(self):
        """MEASUREMENT for the outside-click cure — the three cases, in order.

        The panel is made VISIBLE BUT NOT SEEN with `form.Opacity = 0`, which is
        the mechanism pywebview's OWN startup dance uses to map a window
        invisibly (`winforms.py:777-781`) — so `IsWindowVisible(hwnd)` is TRUE
        (the guard the decision actually reads) while nothing reaches the owner's
        screen. `--show` is NOT used.

        The three decisions are driven through the watcher thread's REAL message
        loop (`PostThreadMessageW`), so what is exercised is the decision
        function, the guards, the thread and `hide_panel` — everything except the
        OS delivering a physical click to the hook.
        """
        form = self._form()
        if form is None or self.click_watcher is None:
            log('OUTSIDE_CLICK_PROBE unavailable form_or_watcher=false')
            return
        try:
            form.Opacity = 0.0
        except Exception as exc:  # noqa: BLE001
            log(f'OUTSIDE_CLICK_PROBE opacity_failed={type(exc).__name__}: {exc}')
            return
        log('OUTSIDE_CLICK_PROBE begin opacity=0 visible_but_not_seen=true')
        rect = RECT()
        # (1) BEFORE ARMING — the two startup navigations.
        self.click_watcher._consider(0, 0, WM_LBUTTONDOWN, source='probe-startup')
        # (2) SHOWN, then a click OUTSIDE the rect.
        self.show_panel('probe-outside-click')
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        log(f'OUTSIDE_CLICK_PROBE shown visible={str(window_visible(self.hwnd)).lower()} '
            f'armed={str(self.click_watcher.armed).lower()} '
            f'rect=({rect.left},{rect.top},{rect.right},{rect.bottom})')
        outside_x, outside_y = rect.left - 20, rect.top + 10
        user32.PostThreadMessageW(self.click_watcher.thread_id, WM_PROBE_CLICK,
                                  _pack_point(outside_x, outside_y), 0)
        time.sleep(1.0)
        log(f'OUTSIDE_CLICK_PROBE after_outside_click '
            f'visible={str(window_visible(self.hwnd)).lower()}')
        # (3) SHOWN again, then a click INSIDE the rect.
        self.show_panel('probe-inside-click')
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        inside_x = (rect.left + rect.right) // 2
        inside_y = (rect.top + rect.bottom) // 2
        user32.PostThreadMessageW(self.click_watcher.thread_id, WM_PROBE_CLICK,
                                  _pack_point(inside_x, inside_y), 0)
        time.sleep(1.0)
        log(f'OUTSIDE_CLICK_PROBE after_inside_click '
            f'visible={str(window_visible(self.hwnd)).lower()}')
        self.request_exit(0, reason='probe-outside-click')
    def set_edit_mode(self, enabled, reason='tray'):
        """Turn the caption band's position editor on or off.

        ENTERED FROM THE TRAY ONLY. The owner's brief: `Edit caption position` is
        "the obvious home now that the tray exists, and it is impossible to
        trigger by accident while reading a caption" — no always-visible chrome
        on the panel, no hotkey.

        WHY THE EX-STYLES CHANGE. A panel that is click-through
        (`WS_EX_TRANSPARENT`) and never activates (`WS_EX_NOACTIVATE`) cannot be
        grabbed or receive a drag: those two bits are exactly what makes Alt+C
        usable over a film, so they are lifted for the duration of the edit and
        put back on the way out. `make_click_through(hwnd, False)` is the existing
        helper, and the NOACTIVATE bit is cleared with the same `set_ex_style` the
        pointer-interactive path uses.
        """
        enabled = bool(enabled)
        if enabled == self.edit_mode:
            return False
        hwnd = self.hwnd
        if hwnd is None:
            warn(f'PANEL_EDIT_MODE_REFUSED on={enabled} reason={reason} '
                 'no_window=true')
            return False
        self.edit_mode = enabled
        if enabled:
            # ARMADO ANTES DO SHOW (medido 2026-11-02): o show custa o paint ack
            # (156 ms) e, armado depois, a faixa ficava visivel com o vigia a ler
            # `edit_mode=false` -- `PANEL_SHOWN` .307, `PANEL_HIDDEN` .311.
            if self.click_watcher is not None:
                # The watcher's own thread reads this; it also STOPS closing the
                # panel on an outside click while the owner is positioning it.
                self.click_watcher.edit_mode = True
            else:
                # The drag is CARRIED by the watcher thread (it already owns the
                # mouse hook and a message loop), so a run without it can enter
                # edit mode and move nothing. Say so instead of leaving the owner
                # with a band that will not follow the pointer.
                warn('PANEL_EDIT_MODE_NO_DRAG the outside-click watcher is not '
                     'running (--no-click-outside), so the band cannot be '
                     'dragged; the tray item still toggles the mode')
            # The band has to be ON SCREEN to be positioned — and the strip is
            # what the owner is positioning, so the show path applies it (and
            # does the resize while the window is still hidden).
            if not window_visible(hwnd):
                self.show_panel(f'edit-{reason}')
            try:
                make_click_through(hwnd, False)
                set_ex_style(hwnd, remove=WS_EX_NOACTIVATE)
            except Exception as exc:  # noqa: BLE001 -- report, never kill the app
                warn(f'PANEL_EDIT_MODE_STYLE_FAILED error={exc!r}')
            self.edit_moves = 0
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            log(f'PANEL_EDIT_MODE on=true reason={reason} surface={self.surface} '
                f'click_through=false noactivate=false '
                f'rect=({rect.left},{rect.top},{rect.right},{rect.bottom}) '
                'hint=drag_the_band')
        else:
            try:
                make_click_through(hwnd, True)
                set_ex_style(hwnd, add=WS_EX_NOACTIVATE)
            except Exception as exc:  # noqa: BLE001
                warn(f'PANEL_EDIT_MODE_STYLE_FAILED error={exc!r}')
            if self.click_watcher is not None:
                self.click_watcher.edit_mode = False
            # The rect the window ended on is the one to restore next launch.
            self.saved_geometry = self.geometry_snapshot()
            self.publish_panel_visibility('edit-off')
            log(f'PANEL_EDIT_MODE on=false reason={reason} '
                f'moves={self.edit_moves} '
                f'geometry={self.saved_geometry} click_through=true '
                'noactivate=true')
        return True
    def _drag_refused(self, why, x, y):
        """DIZ PORQUE E QUE UM ARRASTO NAO SE MOVEU -- e nao o diz mil vezes por segundo.

        O dono, 2026-10-15: *"a porra de arrastar a janela e completamente travado"*. Os
        tres caminhos de recusa do `edit_drag_to` eram `return False` MUDOS: nenhum escrevia
        no log, portanto "esta travado" nao deixava rasto nenhum para se ler. Um caminho que
        falha em silencio e um caminho que nao se pode diagnosticar.

        Rate-limited a UMA linha por segundo: isto corre a 20 amostras por segundo, e uma
        linha por amostra afogaria o log que se quer ler. A primeira recusa escreve SEMPRE,
        porque a primeira e a que explica o que se passou.
        """
        now = time.monotonic()
        last = getattr(self, '_last_drag_refusal', None)
        if last is not None and (now - last[1]) < 1.0 and why == last[0]:
            return
        self._last_drag_refusal = (why, now)
        log(f'PANEL_EDIT_DRAG_REFUSED why={why} point=({int(x)},{int(y)}) '
            f'edit_mode={str(self.edit_mode).lower()} '
            f'moves={getattr(self, "edit_moves", 0)}')

    def edit_drag_to(self, x, y, persist=False):
        """One drag sample, applied at a LOW frequency (see the watcher).

        Called from the outside-click watcher's MESSAGE LOOP, never from inside
        its hook procedure: a slow hook stalls the pointer system-wide. The move
        itself is a bare `SetWindowPos` with `SWP_NOSIZE` — no client-area work
        (a MOVE does not change the client area) and no `exec_js` — so the loop
        stays responsive. The heavier half (the client-area re-fit) is POSTED,
        and the file write happens only when the drag ENDS.
        """
        if not self.edit_mode:
            self._drag_refused('not-edit-mode', x, y)
            return False
        geometry = dict(self.geometry or {})
        width = int(geometry.get('width') or 0)
        height = int(geometry.get('height') or 0)
        if width <= 0 or height <= 0:
            self._drag_refused('geometry-has-no-size w=%d h=%d' % (width, height), x, y)
            return False
        grab = self.edit_grab or (0, 0)
        work = self.work_area()
        nx = max(work['x'], min(int(x) - int(grab[0]),
                               work['x'] + work['width'] - width))
        ny = max(work['y'], min(int(y) - int(grab[1]),
                               work['y'] + work['height'] - height))
        moved = (nx != int(geometry.get('x') or 0)
                 or ny != int(geometry.get('y') or 0))
        if moved:
            geometry['x'] = nx
            geometry['y'] = ny
            geometry['docked'] = 'edited'
            self.geometry = geometry
            scale = (self.display or {}).get('scaleFactor') or 1.0
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST,
                                int(nx * scale), int(ny * scale), 0, 0,
                                SWP_NOSIZE | SWP_NOACTIVATE)
            self.edit_moves += 1
        if persist:
            self.saved_geometry = self.geometry_snapshot()
            # Fire-and-forget: the client area is re-pinned once the drag ends,
            # never from inside the hook thread's message loop.
            self._post(lambda: self._fit_client_area(self._form()))
            self.publish_panel_visibility('edit-move')
            log(f'PANEL_EDIT_GEOMETRY_SAVED surface={self.surface_applied} '
                f'window={width}x{height}@({nx},{ny}) moves={self.edit_moves} '
                f'work={work["width"]}x{work["height"]}@({work["x"]},{work["y"]})')
        return moved
    def run_edit_mode_probe(self):
        """MEASUREMENT for the EDIT MODE — the whole path, window never seen.

        The panel is made VISIBLE BUT NOT SEEN with `form.Opacity = 0`, the very
        mechanism pywebview's own startup dance uses to map a window invisibly
        (`winforms.py:777-781`): `IsWindowVisible(hwnd)` is TRUE — the guard every
        decision here reads — while nothing reaches the owner's screen. `--show`
        is NOT used, and NO physical mouse is moved: the drag sample is posted
        through the watcher thread's REAL message loop (`PostThreadMessageW`),
        which is the exact path the hook procedure posts to, so what is exercised
        is the hook's own route minus the OS delivering a physical move.

        IT CANNOT HANG, and that is a rule earned here: a probe whose exception
        escapes a `threading.Timer` callback dies with a traceback on a stderr
        that `pythonw` does not have, leaving a HIDDEN SHELL ALIVE forever (the
        probe that launched it then kills it and reports an empty arm). So the
        steps are wrapped: any raise is written INTO THE LOG, and the exit is in a
        `finally`.
        """
        try:
            self._edit_mode_probe_steps()
        except Exception:  # noqa: BLE001
            import traceback
            log('PANEL_EDIT_PROBE FAILED '
                + traceback.format_exc().replace('\n', ' | '))
        finally:
            self.request_exit(0, reason='probe-edit-mode')
    def _edit_mode_probe_steps(self):
        form = self._form()
        if form is None:
            log('PANEL_EDIT_PROBE unavailable form=false')
            return
        try:
            form.Opacity = 0.0
        except Exception as exc:  # noqa: BLE001
            log(f'PANEL_EDIT_PROBE opacity_failed={type(exc).__name__}: {exc}')
            return
        log('PANEL_EDIT_PROBE begin opacity=0 visible_but_not_seen=true')
        # (1) ENTER through the tray's OWN command id — the real entrance, and
        #     the same handler the menu's `WM_COMMAND` reaches.
        self.tray_command(ID_TRAY_EDIT)
        rect = RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(rect))
        log(f'PANEL_EDIT_PROBE after_enter visible={str(window_visible(self.hwnd)).lower()} '
            f'edit_mode={str(self.edit_mode).lower()} '
            f'rect=({rect.left},{rect.top},{rect.right},{rect.bottom})')
        # (1b) AN OUTSIDE CLICK WHILE EDITING MUST NOT PUT THE BAND AWAY. Driven
        #      through the watcher's own decision function, which is the same one
        #      the hook calls — the first missed grab must not end the edit.
        if self.click_watcher is not None:
            closed = self.click_watcher._consider(5, 5, WM_LBUTTONDOWN,
                                                 source='probe-edit-outside')
            log('PANEL_EDIT_PROBE outside_click_while_editing closed='
                f'{str(bool(closed)).lower()} '
                f'visible={str(window_visible(self.hwnd)).lower()} '
                f'decision={(self.click_watcher.decisions[-1] or {}).get("decision")}')
        # (2) ONE DRAG SAMPLE. `edit_grab` is None because no physical
        #     button-down happened, so `edit_drag_to` moves the band's ORIGIN to
        #     the point — the decisions under test are the move, the clamp and the
        #     persist, not the grab offset (which only the hook sets).
        target_x, target_y = 700, 400
        if self.click_watcher is not None and self.click_watcher.thread_id:
            log(f'PANEL_EDIT_PROBE drag from=({rect.left},{rect.top}) '
                f'to=({target_x},{target_y})')
            user32.PostThreadMessageW(self.click_watcher.thread_id, WM_EDIT_DRAG,
                                      _pack_point(target_x, target_y), 1)
            time.sleep(1.0)
        else:
            log('PANEL_EDIT_PROBE drag_skipped watcher=false')
        # (2b) THE KEY, READ BACK OFF DISK FROM INSIDE THIS PROCESS. The file is
        #      shared with a possibly-running older shell that rewrites it every
        #      `interval_s`, so an OUTSIDE reader can lose the race; read here, a
        #      millisecond after the write, it cannot be raced away.
        try:
            with open(PANEL_VISIBILITY_PATH, encoding='utf-8') as fh:
                on_disk = json.load(fh)
            log('PANEL_EDIT_PROBE file_geometry='
                + json.dumps(on_disk.get('geometry'))
                + ' file_pid=' + str(on_disk.get('pid'))
                + ' file_schema=' + json.dumps(on_disk.get('schema'))
                + ' file_visible=' + json.dumps(on_disk.get('visible')))
        except Exception as exc:  # noqa: BLE001
            log(f'PANEL_EDIT_PROBE file_read_failed error={exc!r}')
        # (3) LEAVE through the same id, which is what persists and puts the two
        #     ex-styles back.
        self.tray_command(ID_TRAY_EDIT)
        log('PANEL_EDIT_PROBE after_leave edit_mode='
            f'{str(self.edit_mode).lower()} saved={json.dumps(self.saved_geometry)}')
        self.request_exit(0, reason='probe-edit-mode')
    def stats(self):
        """The worker's OWN counters, whitelisted to what the panel reads.

        THE SHAPE IS THE PANEL'S, NOT THIS FILE'S. The level consumer takes
        `pushLevel(peak, blocks)` (`panel.js:2564`, `LEVEL.blocks` set at `:2584`);
        the "behind" chip reads `queue_drops` and `rate` (`panel.js:2688-2689`,
        painted at `:2700`, declared at `:2539`) — and those two this shell does
        NOT compute, and must NOT invent, because a fabricated `rate` would light
        a chip about a lag nobody measured.

        THE PAYLOAD IS `{peak, blocks}` PLUS the `tag` stamped on purpose at `:5941`
        (the worker's tick) and `:5927` (the meter path): copying only peak/blocks
        THREW THE TAG AWAY, which is the defect row F4/F1 was opened for. So the
        payload of an idle shell is `{tag: 'stats'}` and never `{}`.

        RE-MEASURED 2026-10-12 (AGENTS.md rule 2): this comment cited `panel.js:1702-1710`
        and `:1738-1740`, and BOTH are stale — `:1738-1740` is `wireSurfaces()`, not the
        chip. Gate: `_main/_strip-surface-oracle.py` pins the payload shape and
        `_main/rtf-cpu-attribution-oracle.py` arm 4 reads this claim. Re-run the grep
        before citing a line here.

        TWO SOURCES, ONE SHAPE, AND THE WAVE WINS WHILE IT IS FRESH:

        * `{"type":"meter","peak":…,"blocks":…}` on STDOUT, once per meter window
          (10 Hz by default) — `peak` is the peak OF THAT WINDOW, and this is what
          a wave must be drawn from;
        * the `WORKER_STATS` line on STDERR, once per its own interval — `peak`
          there is the RUNNING MAXIMUM of the whole run, and a wave drawn from a
          running maximum is a staircase that only rises and then flattens. That
          IS the defect the owner reported.

        So a meter sample younger than `METER_FRESH_S` supplies the payload and
        the stats line is not consulted at all: the two are NEVER MIXED, because
        a window peak next to a run-maximum `blocks` would be two different
        pictures of one measurement. With no meter (the worker's `--meter-hz 0`,
        or an older worker) the behaviour is exactly what it was.

        `last_worker_stats` is `{'tag', 'fields', 'line'}` (`parse_worker_stats`)
        and the numbers live in `fields` as the STRINGS the worker printed. A
        field the worker did not print stays ABSENT: `panel.js:1641` refuses a
        non-finite peak, so absent means "no measurement", never a zero.
        """
        meter = getattr(self.bridge, 'last_meter', None) \
            if self.bridge is not None else None
        if isinstance(meter, dict) and (
                time.monotonic() - float(meter.get('at') or 0.0)) <= METER_FRESH_S:
            payload = {}
            # WHICH SOURCE (row #38, 2026-10-11): a fresh meter tick and the 10 s
            # WORKER_STATS running maximum are different measurements with the same
            # two keys, and the panel could not tell them apart.
            payload['tag'] = 'meter'
            for key in ('peak', 'blocks'):
                value = meter.get(key)
                if value is not None:
                    payload[key] = float(value)
            return payload
        raw = getattr(self.bridge, 'last_worker_stats', None) \
            if self.bridge is not None else None
        fields = raw.get('fields') if isinstance(raw, dict) else None
        payload = {}
        # THE WORKER'S OWN TAG (row #38, 2026-10-11): its WORKER_STATS line carries
        # `tag=tick|final`, and copying only peak/blocks threw that away -- so a
        # mid-run tick and the run total arrived at the panel wearing the same face.
        # 'stats' is the fallback for a line that declares no tag at all.
        payload['tag'] = (fields.get('tag') if isinstance(fields, dict) else None) or 'stats'
        if isinstance(fields, dict):
            # `queue_drops` IS WHITELISTED HERE, and it is a MEASUREMENT, not an invention.
            # MEASURED 2026-10-13 by the trade-off audit: worker/sotto_worker.py:4949 prints
            # `queue_drops=` on EVERY WORKER_STATS line, and `parse_worker_stats` keeps EVERY
            # `key=value` token in `fields`. The shell was already HOLDING this number and
            # filtering it out -- which is why the panel's "behind" chip (panel.js) has a
            # branch that has NEVER been able to fire: it was waiting on a field this file
            # was dropping.
            #
            # `rate` STAYS OUT, and that is not the same kind of omission: nothing here
            # computes a rate, and the comment above is right that inventing one would
            # light a chip about a lag nobody measured. A dropped-by-the-worker key stays
            # ABSENT (never zero) so the panel keeps treating absent as "no measurement".
            for key in ('peak', 'blocks', 'queue_drops'):
                value = fields.get(key)
                if value is None:
                    continue
                try:
                    payload[key] = float(value)
                except (TypeError, ValueError):
                    continue
        return payload
    def reply_stats(self, stats_id, payload):
        """The panel's `getStats()` pull, ANSWERED -- without holding the caller.

        MEASURED 2026-10-20 (the owner's own log, `I:\cc-tmp\sotto-012524.log`):
        93 `UI_THREAD_STALL begin-invoke not run in 10 s` and 68 `exec_js
        TIMEOUT after 10.0s`, ALL of them inside ONE 50 s window. The chain was
        `panel.js` -> `_stats()` -> `reply_stats()` -> `exec_js()` (SYNCHRONOUS,
        10 s budget) -> `_ui()` -> `form.BeginInvoke` + `done.wait(10)`. Every
        pull was a SYNCHRONOUS round trip through the UI thread, and the thread
        that made it is the PUMP thread -- the one that carries the captions. A
        busy UI thread therefore delayed the CAPTIONS, 93 times.

        THE FIX IS THE ONE `emit_async` ALREADY HOLDS (2026-10-11): the reply
        is a POST, not a round trip, and the number of POSTED callables is
        BOUNDED at ONE per channel whatever the pull rate is.

        BUT A REPLY IS NOT A PUSH, AND THAT IS THE WHOLE DIFFERENCE. `emit_async`
        may REPLACE the pending payload, because its payload is a whole state
        and the panel is a pure function of the last one it saw. A REPLY is the
        ANSWER to an id: every id asked a question, and a question that is not
        answered leaves the panel's Promise pending FOREVER (`statsPending[id]`
        in the shell's own injected JS, `__sotto_stats` resolves ONE id). So
        the pending slot here is a LIST of ids, and the ids ACCUMULATE while
        the CALLABLES do not.

        THE BOUND: `STATS_REPLY_MAX_PENDING` ids wait for the UI thread. Past
        that, the OLDEST id is moved aside -- and it is still ANSWERED, with
        the NEWEST payload: the payload is a whole state, so the newest state
        is a TRUE answer to an older question. An id that is never answered
        leaks one entry in the page's `statsPending` map, and the page is not
        mine to fix.
        """
        # LOGGED, not silent: the panel's own poll (`panel.js:1722`, every 1000 ms)
        # is the only way to tell "the member exists" from "the member is ANSWERED".
        # The first reply and then every 60th — one line a minute at the panel's
        # cadence, so the log stays readable while the channel stays visible.
        self.stats_replies += 1
        if self.stats_replies == 1 or self.stats_replies % 60 == 0:
            log(f'BRIDGE_STATS_REPLY id={stats_id} count={self.stats_replies} '
                f'payload={json.dumps(payload, separators=(",", ":"))}')

        payload_json = json.dumps(json.dumps(payload))
        lock = getattr(self, '_stats_reply_lock', None)
        if lock is None:
            lock = self._stats_reply_lock = threading.Lock()
        with lock:
            pending = getattr(self, '_stats_reply_pending', None)
            if pending is None:
                pending = self._stats_reply_pending = []
            evicted = getattr(self, '_stats_reply_evicted', None)
            if evicted is None:
                evicted = self._stats_reply_evicted = []
            if len(pending) >= STATS_REPLY_MAX_PENDING:
                oldest = pending.pop(0)
                evicted.append(oldest)
                if len(evicted) > STATS_REPLY_MAX_PENDING:
                    dropped = evicted.pop(0)
                    log(f'STATS_REPLY_DROPPED id={dropped} '
                        f'reason=reply-queue-overflow pending={len(pending)} '
                        f'evicted={len(evicted)}')
            pending.append(stats_id)
            self._stats_reply_payload = payload_json
            already = getattr(self, '_stats_reply_posted', False)
            self._stats_reply_posted = True

        if already:
            # A POST IS ALREADY PENDING and it will carry this id too. Nothing
            # new is posted: THAT is the bound.
            return True

        try:
            queued = self._post(self._drain_stats_replies)
        except BaseException:
            with lock:
                self._stats_reply_posted = False
            raise
        if queued is False:
            # `_post` DROPS the callable when the form does not exist yet. The
            # slot must not stick on that answer -- a stats channel that goes
            # permanently silent is a worse failure than the queue this bound
            # exists to fix.
            with lock:
                self._stats_reply_posted = False
                pending.clear()
                evicted.clear()
            return False
        return True

    def _drain_stats_replies(self):
        """Deliver the pending replies. Runs ON THE UI THREAD.

        EVERY id is answered, with the NEWEST payload: the payload is a whole
        state, so the newest state answers an older question truthfully, and
        the panel's Promise resolves either way.
        """
        from System import Action, Func, Object, String
        from System.Threading.Tasks import Task

        def _complete(task):
            try:
                if task.IsFaulted:
                    warn(f'stats reply failed: {task.Exception!r}')
            except Exception as exc:  # noqa: BLE001
                warn(f'stats reply failed: {exc!r}')

        lock = getattr(self, '_stats_reply_lock', None)
        if lock is None:
            return
        with lock:
            pending = getattr(self, '_stats_reply_pending', [])
            evicted = getattr(self, '_stats_reply_evicted', [])
            ids = list(pending) + list(evicted)
            pending.clear()
            evicted.clear()
            self._stats_reply_posted = False
            payload_json = getattr(self, '_stats_reply_payload', '""')
        if not ids:
            return
        for stats_id in ids:
            script = ('window.__sotto_stats(' + json.dumps(stats_id) + ','
                      + payload_json + ')')
            try:
                self.webview2.Invoke(Func[Object](
                    lambda s=script: self.core.ExecuteScriptAsync(s).ContinueWith(
                        Action[Task[String]](_complete))))
            except Exception as exc:  # noqa: BLE001
                warn(f'STATS_REPLY_FAILED id={stats_id} error={exc!r}')
    def on_worker_stats(self, parsed):
        """PUSH half of the stats channel: the worker just published counters.

        Same payload as `stats()` — one shape for the pull and the push, so the
        panel cannot receive two different pictures of one measurement.

        TWO RULES, both learned the hard way:

        * **NO LOG LINE PER SAMPLE.** The meter is a per-sample feed (the worker
          may publish tens of Hz), and a line per sample is a log that grows
          without bound — that flood is why the worker's meter default was once
          turned OFF, i.e. a feature was disabled to keep a log quiet. This logs
          the FIRST push and then at most ONE line per `STATS_LOG_INTERVAL_S`,
          carrying the number of pushes it stands for. The bytes-per-minute
          before/after are in `_main/receipt-strip-surface.md`.
        * **NO WAITING.** The push is `emit_async` — the pump thread that calls
          this is the same one that carries captions, and a blocking round trip
          per meter sample would delay them.
        """
        payload = self.stats()
        self.stats_pushes += 1
        self._stats_log_maybe(payload)
        self.emit_async('stats', payload)
    def _stats_log_maybe(self, payload):
        """At most one `BRIDGE_STATS_PUSH` line per interval, with a count."""
        now = time.monotonic()
        first = self.stats_logged == 0
        due = (now - self.stats_logged_at) >= STATS_LOG_INTERVAL_S
        if not (first or due):
            return
        window = 0.0 if first else now - self.stats_logged_at
        log(f'BRIDGE_STATS_PUSH count={self.stats_pushes} '
            f'in_window_s={round(window, 1)} '
            f'rate_hz={round((self.stats_pushes - self.stats_logged) / window, 2) if window > 0 else "first"} '
            f'payload={json.dumps(payload, separators=(",", ":"))}')
        self.stats_logged = self.stats_pushes
        self.stats_logged_at = now
    def on_worker_meter(self, sample):
        """PUSH half of the WAVE: the worker closed a meter window.

        Called from the bridge's stdout pump — the SAME thread that carries the
        captions — once per window (10 Hz by default). Two rules, both already
        learned on the stats push next door:

        * **NO WAITING**: `emit_async`, so a slow page cannot delay a caption.
        * **NO LOG LINE PER SAMPLE**: the bridge logs `BRIDGE_METER` on its own
          budget (first sample, then one per `METER_LOG_INTERVAL_S`); this half
          logs NOTHING per sample, and its count travels in `SHELL_EXIT` as
          `meterPushes=`. A line here would re-create exactly the 20.5 KB/min
          flood that the meter's own branch removed.

        The payload is `stats()`, not the raw sample: it is the SAME shape the
        poll returns, so the push and the pull cannot disagree — and because a
        fresh meter sample is what `stats()` reads first, the payload IS this
        window's `{peak, blocks}`.
        """
        self.meter_pushes += 1
        self.emit_async('stats', self.stats())
    def emit_async(self, kind, payload):
        """`emit` WITH A LATCH — for a per-sample feed.

        The difference to `emit` is no longer the wait (2026-11-01: `emit` is a
        post too, see its docstring) but the COLLAPSE: a pending payload is
        replaced instead of queueing a second callable, so a feed at tens of Hz
        cannot grow the UI thread's queue with the feed. The stats channel is
        the feed: the worker may publish a meter sample at tens of Hz, and the
        pump thread delivers captions on the same thread that reads the worker's
        stderr, so an unlatched push per sample would delay the captions
        themselves. Measured on this host before either existed: a blocking push
        per sample stalled that thread outright.

        So this posts the script with `_post` (`BeginInvoke`, no wait) and drops
        the resulting `Task`. Ordering between two `emit_async` calls is not
        guaranteed, and does not need to be: each one carries a WHOLE payload, and
        the panel's `pushLevel` is a pure function of the last one it saw.

        AND THAT SENTENCE IS THE LICENCE FOR THE BOUND BELOW: a push that arrives
        while another is still queued REPLACES the queued payload instead of
        queueing a second callable. Measured 2026-10-11: the worker publishes 43
        stats pushes/s, the pump thread posts one callable per push, and a page
        that cannot drain that fast let the WinForms queue grow WITH THE FEED --
        the unbounded-queue risk the owner's freeze report put on the table. With
        the latch the queue holds at most ONE stats callable, and what it carries
        is always the newest state. The behaviour a caller can rely on is
        unchanged: the last payload pushed is the one that reaches the page.
        """
        try:
            lock, pending = self._emit_lock, self._emit_pending
        except AttributeError:  # a probe-built shell that never ran __init__
            lock = self._emit_lock = threading.Lock()
            pending = self._emit_pending = {}
        with lock:
            already = kind in pending
            pending[kind] = payload
        if already:
            return

        from System import Action, Func, Object, String
        from System.Threading.Tasks import Task

        def _complete(task):
            try:
                if task.IsFaulted:
                    warn(f'emit_async failed: {task.Exception!r}')
            except Exception as exc:  # noqa: BLE001
                warn(f'emit_async failed: {exc!r}')

        def _run():
            # POP AT RUN TIME, not at call time: this is what collapses N pushes
            # into the ONE script carrying the newest payload.
            with lock:
                latest = pending.pop(kind, None)
            if latest is None:
                return
            # SEM PAGINA NAO HA' O QUE NOTIFICAR -- E NAO E' UMA EXCEPCAO POR
            # AMOSTRA (2026-11-04, MEDIDO). O pipeline de legendas arranca ANTES
            # do WebView2, de proposito (`emit` documenta-o), e o feed de `stats`
            # publica a cada amostra do medidor. Com `core` a `None` este `_run`
            # fazia `self.core.ExecuteScriptAsync` dentro do `Invoke`, o WinForms
            # devolvia o `AttributeError` a' thread que postou, e o `guarded()`
            # do `_post` escrevia um `WARN POSTED_CALLABLE_FAILED` por amostra.
            # Medido numa instancia propria (pid 42340, escondida, 2026-11-04
            # 02:48:2x..02:49:24): **541** linhas em ~60 s
            # (`grep -c POSTED_CALLABLE_FAILED`) e a legenda do YouTube a CHEGAR
            # (`CAPTION_IN`) sem nunca poder ser pintada. Uma linha so', na forma
            # que o `exec_js_post` ja' usa para o irmao pre-`pythonnet`; o
            # payload e' DESCARTADO -- o painel e' funcao do ultimo estado que
            # viu e a proxima amostra reabre o latch.
            if self.core is None or self.webview2 is None:
                if not getattr(self, '_emit_async_prewebview_logged', False):
                    self._emit_async_prewebview_logged = True
                    log('EMIT_ASYNC_PREWEBVIEW kind=%s reason=no-core '
                        '(uma linha; as seguintes sao descartadas ate a '
                        'pagina existir)' % json.dumps(kind))
                return
            script = ('window.__sotto_emit(' + json.dumps(kind) + ','
                      + json.dumps(json.dumps(latest)) + ')')
            self.webview2.Invoke(Func[Object](
                lambda: self.core.ExecuteScriptAsync(script).ContinueWith(
                    Action[Task[String]](_complete))))

        # `_post`, NOT `_ui`: the docstring above promised "no wait", but `_ui`
        # WAITS on its BeginInvoke for up to 10 s. At the measured 43 pushes/s the
        # pump thread -- the SAME thread that carries the captions -- sat in that
        # wait while the UI thread drained the queue. `_post` is the
        # fire-and-forget twin and guards the callable against a ThreadException
        # dialog. Measured 2026-10-11 (`_strip-stats-probe.json`, fed arm: the
        # page probe returned null after a 20 s stall).
        try:
            queued = self._post(_run)
        except BaseException:
            with lock:
                pending.pop(kind, None)
            raise
        if queued is False:
            # `_post` DROPS the callable when the form does not exist yet (it
            # returns False for exactly that case). Releasing the slot is what
            # keeps the latch from sticking forever: a stats channel that never
            # pushes again would be a worse failure than the queue this bound
            # exists to fix.
            with lock:
                pending.pop(kind, None)

    def work_area(self):
        """The WORK area of the display this shell lays out in, in DIP.

        `primary_display()` is the one source: `MonitorFromPoint(POINT(0,0),
        MONITOR_DEFAULTTOPRIMARY)` — the PRIMARY monitor, the same one the docked
        panel has always used. On this box there is exactly ONE monitor
        (`_main/_strip-work-area-probe.ps1`: `monitors=1`, `work=[0,0 1920x1032]`,
        DPI 96), so "which monitor does the strip open on" cannot be measured
        here and is NOT guessed at: it opens on the primary, like the panel, and
        the multi-monitor case is disclosed as unmeasured in
        `_main/receipt-strip-surface.md`.
        """
        # RE-READ THE MONITOR ON EVERY LAYOUT, not once at startup: the owner
        # may move the mouse to another screen between two Alt+C presses, and
        # the panel must follow. `target_display` is the mouse's monitor;
        # fallback keeps a stale cache rather than refusing to lay out.
        try:
            display = target_display()
        except Exception:  # noqa: BLE001
            display = self.display or primary_display()
        self.display = display
        return display['workArea']
    def geometry_for(self, surface):
        """The rect `surface` wants, in the CURRENT work area.

        A saved (edited) rect wins over the computed default, and is clamped into
        the work area — the honest answer to a resolution change, which this lane
        did NOT measure. The clamp says so in the log when it MOVES anything, so
        a window the owner placed is never silently relocated.
        """
        work = self.work_area()
        saved = self.saved_geometry
        # A SAVED STRIP RECT KEEPS THE OWNER'S PLACEMENT, NEVER ITS HEIGHT.
        # Measured: the saved rect in _main/panel-visibility.json (geometry.surface=strip,
        # 1040x100) beat the stylesheet's own --strip-height/--float-height, so the floated
        # caption the owner asked for could never reach 220px. The stylesheet is the single
        # source of truth for this number (strip_height_from_css :6495); a saved rect is a
        # placement, and a placement cannot outlive a resize of the thing it places.
        if (surface == 'strip' and isinstance(saved, dict)
                and saved.get('surface') == 'strip'):
            live = self.strip_height
            if int(saved.get('height') or 0) != int(live):
                bottom = int(saved.get('workY') or 0) + int(saved.get('workHeight') or 0)
                saved = dict(saved)
                saved['height'] = int(live)
                saved['y'] = bottom - int(live)
                saved['docked'] = 'bottom-strip'
                log('STRIP_RECT_HEIGHT from_saved=%s to_css=%s reason=%s'
                    % (saved.get('height'), int(live), 'geometry-strip-live'))
        # THE SAME RULE FOR THE WIDTH, AND IT IS THE OWNER'S SOLID SLAB.
        # The saved strip rect is 1040 wide (STRIP_WIDTH) while
        # `body[data-surface="strip"] .panel` is `max-content` -- a small pill --
        # and the form paints every pixel the page does not with opaque #0B0F14.
        # The width is the CONTENT's now, exactly as the height already was.
        if surface == 'strip':
            live_w = self.strip_width_live()
            if live_w is not None:
                want_w = int(live_w)
                old_w = int(saved.get('width') or 0) if isinstance(saved, dict) else 0
                if old_w != want_w:
                    saved = dict(saved) if isinstance(saved, dict) else {}
                    saved['width'] = want_w
                    work_w = int(work.get('width') or 0)
                    work_x = int(work.get('x') or 0)
                    # A SLAB IS RE-CENTRED; A PLACEMENT THE OWNER MADE IS KEPT.
                    slab = (old_w <= 0 or old_w == STRIP_WIDTH
                            or old_w >= int(work_w * 0.9))
                    if slab:
                        saved['x'] = work_x + round((work_w - want_w) / 2)
                    else:
                        saved['x'] = max(work_x, min(int(saved.get('x') or 0),
                                                     work_x + work_w - want_w))
                    saved['docked'] = 'bottom-strip'
                    saved.setdefault('surface', 'strip')
                    saved.setdefault('height', int(self.strip_height))
                    saved.setdefault('y', int(work.get('y') or 0)
                                     + int(work.get('height') or 0)
                                     - int(self.strip_height))
                    log(f'STRIP_RECT_WIDTH from_saved={old_w} to_content={want_w} '
                        f'recentred={bool(slab)}')
        if isinstance(saved, dict) and saved.get('surface') == surface:
            geometry, moved = clamp_geometry(saved, work)
            if moved:
                log('PANEL_GEOMETRY_CLAMPED '
                    f'surface={surface} '
                    f'was={saved.get("width")}x{saved.get("height")}'
                    f'@({saved.get("x")},{saved.get("y")}) '
                    f'now={geometry["width"]}x{geometry["height"]}'
                    f'@({geometry["x"]},{geometry["y"]}) '
                    f'work={geometry["workWidth"]}x{geometry["workHeight"]}'
                    f'@({geometry["workX"]},{geometry["workY"]})')
            return geometry
        if surface == 'strip':
            return dock_strip(work, width=self.strip_width_live(),
                              height=self.strip_height)
        return dock_right(work)
    def strip_height_from_css(self):
        """The strip's height, READ OUT OF THE STYLESHEET. `None` if unavailable.

        The panel lane's rule, and it is the right one: the CSS is the SINGLE
        source of truth for this number (`panel.css:52`, with `:1060` deriving the
        content floor from it), so the shell must not carry a second copy. The
        property is read off `document.documentElement` — `:root` is where it is
        declared — and its `"150px"` is parsed to a number. Anything that is not a
        positive finite pixel value answers `None` and the caller falls back, with
        the fallback logged.
        """
        # THE SCRIPT WAS SYNTACTICALLY BROKEN, AND I BROKE IT. Measured
        # 2026-10-12: `STRIP_HEIGHT source=fallback value=148 ... why=css-unavailable`
        # on EVERY surface application, i.e. the window was sized by
        # STRIP_HEIGHT_FALLBACK and never by the stylesheet. The cause was this
        # string: the `flo` line was spliced BETWEEN `const v =
        # getComputedStyle(document.documentElement)` and its `.getPropertyValue`,
        # producing `const v = getComputedStyle(...)const flo = ...` -- a
        # SyntaxError -- plus a second `const v` and a stray `})()`. A script that
        # cannot parse returns nothing, so the read "failed" quietly every time and
        # the strip stayed 148 px while `panel.css` says `--strip-height: 40px`.
        # Built as ONE valid statement chain now, and the probe measures it.
        script = ("(() => {"
                  "const de = document.documentElement;"
                  "if (!de) return null;"
                  "const flo = de.getAttribute('data-float') === 'on';"
                  "const v = getComputedStyle(de)"
                  f".getPropertyValue(flo ? '{FLOAT_HEIGHT_CSS_VAR}' : '{STRIP_HEIGHT_CSS_VAR}');"
                  "return v === null || v === undefined ? null : String(v).trim();"
                  "})()")
        try:
            raw = self.exec_js(script)
        except Exception as exc:  # noqa: BLE001
            log(f'STRIP_HEIGHT_CSS_FAILED error={exc!r}')
            return None
        if not isinstance(raw, str) or not raw:
            return None
        text = raw.strip().lower()
        if text.endswith('px'):
            text = text[:-2].strip()
        try:
            value = float(text)
        except ValueError:
            log(f'STRIP_HEIGHT_CSS_UNPARSED raw={json.dumps(raw)}')
            return None
        if not (value > 0) or value != value or value > 2000:
            log(f'STRIP_HEIGHT_CSS_UNUSABLE raw={json.dumps(raw)}')
            return None
        return value
    def strip_width_from_dom(self):
        """The strip's CONTENT width, measured in the page. `None` if unavailable.

        THE SOLID SLAB, AND WHY THIS EXISTS. Measured 2026-10-12, owner verbatim:
        *"eu to vendo div com cor solida inves de invisivel"*. The strip WINDOW was
        `STRIP_WIDTH = 1040` wide while `body[data-surface="strip"] .panel` is
        `width: max-content` -- a small pill -- and the shell paints every pixel the
        page does not with the form's opaque `#0B0F14` (:3929). A 1040-wide window
        holding a ~400px pill IS a solid colour slab, with the real bottom panel
        sitting in the middle of it: exactly what the owner described.

        So the width is read from the thing that HAS it: the pill's own rendered
        box. `max-content` is INTRINSIC, so the measurement does not depend on the
        window's width and cannot feed back into it.

        While the caption is floated (`data-float="on"`) this answers `None` ON
        PURPOSE: the floated caption is `left:0; right:0` inside the window and
        needs the room, so the caller keeps the wide dock. It also answers `None`
        before the page has laid out, so a cold read never collapses the window.
        """
        script = ("(() => {"
                  "const de = document.documentElement;"
                  "if (!de) return null;"
                  "if (de.getAttribute('data-float') === 'on') return null;"
                  "const el = document.querySelector('.panel');"
                  "if (!el || !el.getBoundingClientRect) return null;"
                  "const r = el.getBoundingClientRect();"
                  "if (!r || !(r.width > 0)) return null;"
                  "return String(Math.ceil(r.width));"
                  "})()")
        try:
            raw = self.exec_js(script)
        except Exception as exc:  # noqa: BLE001
            log(f'STRIP_WIDTH_DOM_FAILED error={exc!r}')
            return None
        if not isinstance(raw, str) or not raw:
            return None
        text = raw.strip().lower()
        if text.endswith('px'):
            text = text[:-2].strip()
        try:
            value = float(text)
        except ValueError:
            log(f'STRIP_WIDTH_DOM_UNPARSED raw={json.dumps(raw)}')
            return None
        if not (value > 0) or value != value or value > 20000:
            log(f'STRIP_WIDTH_DOM_UNUSABLE raw={json.dumps(raw)}')
            return None
        return value

    def strip_width_live(self):
        """The cached live content width, or `None`. See `strip_width_from_dom`."""
        value = self.strip_width_dom
        if not isinstance(value, (int, float)) or not (value > 0):
            return None
        return int(round(value))

    def refresh_strip_width(self, reason='surface-strip'):
        """Re-measure the pill and adopt it, once per real change.

        The twin of `refresh_strip_height`: the reading is cached, so the
        geometry path never calls into the page, and a theme change (which moves
        the pill's width) is adopted on the next strip application. Returns True
        when the number moved.
        """
        value = self.strip_width_from_dom()
        if value is None:
            if self.strip_width_dom is None:
                log(f'STRIP_WIDTH source=fallback value={STRIP_WIDTH} '
                    f'reason={reason} why=content-unavailable')
            return False
        value = int(round(value))
        if value == self.strip_width_dom:
            return False
        was = self.strip_width_dom
        self.strip_width_dom = value
        log(f'STRIP_WIDTH from={was} to={value} source=content reason={reason}')
        return True
    def set_strip_height(self, height, reason='runtime'):
        """Change the strip's height AT RUNTIME and re-derive the window.

        The height is the STYLESHEET's (`panel.css:52`), so this does not replace
        it: it records an ADDITION on top of it (`strip_height_extra`), which is
        how a future reveal can grow the band without a second copy of the base
        number. Nothing calls it today. Returns True when the number moved.
        """
        try:
            value = int(height)
        except (TypeError, ValueError):
            warn(f'STRIP_HEIGHT_REFUSED value={height!r} reason={reason}')
            return False
        value = max(48, min(value, 2000))
        base = self.strip_height_css if self.strip_height_css is not None \
            else STRIP_HEIGHT_FALLBACK
        if value == self.strip_height:
            return False
        log(f'STRIP_HEIGHT from={self.strip_height} to={value} source=override '
            f'base={base} extra={value - base} reason={reason}')
        self.strip_height_extra = value - base
        self.strip_height = value
        if self.surface == 'strip':
            self.set_panel_surface('strip', f'height-{reason}')
        return True
    def set_panel_surface(self, surface, reason='page', present=False):
        """`bridge.setPanelSurface(surface, reason)` — layout AND window, together.

        `present=True` means "this call is on the path to a MAP": the show is
        about to happen and the page's answers cannot be waited for (measured
        2026-11-01: the pill width read took 1,75 s and the geometry emit 10,0 s
        on ONE press, both because `exec_js` waits on a UI thread that is busy
        mapping the window). In that mode NOTHING here reads the page: the cached
        metrics are used, the page messages are POSTED, and the re-measure is
        posted for right after the show. Same pixels, no wait.

        THE MEMBER THIS SHELL OWED THE PANEL. Before it existed, `grep -n
        'surface|SottoSurfaces|strip' app/webview/sotto_webview.py` matched 37
        lines and NOT ONE was an implementation of this call, so
        `panel.js:1241`'s test failed and `openFullPanel` fell through to
        `panel.js:1245-1247` — switch the layout, leave the window strip-sized.

        The two halves are ONE action on purpose. Setting the attribute alone
        gives a 380x900 column wearing strip CSS; resizing alone gives a strip
        window wearing panel CSS. Order: the DOCUMENT first (`exec_js` waits for
        the script), then the HWND, so the window never shows one surface's
        stylesheet at the other surface's size.
        """
        name = normalise_surface_name(surface)
        if name is None:
            warn(f'PANEL_SURFACE_REFUSED surface={json.dumps(str(surface))} '
                 f'reason={reason}')
            return False
        # THE SECOND HALF OF THE LOOP, AND IT BELONGS HERE AS WELL AS IN THE PAGE.
        #
        # MEASURED 2026-10-13 by the shell audit: in the log tail, 30 647 applications
        # carried reason strip-float-off against FIVE real hotkey transitions -- 6129 to 1
        # repeated work over real transitions. The surface path is 78.5% of the log BYTES,
        # 98.2% counting the write failures, and the whole rest of the app -- worker,
        # captions, tray, autostart -- is 1.85%.
        #
        # `panel.js:1913` got its guard today, which closes the loop from the page side.
        # This is the SHELL side, on purpose: if the page guard were the only thing
        # between this app and that loop, the next regression would be worse than the one
        # just fixed -- and today's bounded retry in write_atomic measures 482 ms per
        # failed write, which at the loop's own rate would be ~15 s of sleep per second.
        #
        # IDEMPOTENT ON (name, reason): a repeated call that asks for the surface the
        # window is ALREADY on, for the SAME reason, does nothing and says so by
        # returning True. A genuine transition changes the name; a genuine re-apply
        # (hotkey, --show, hot-reload, navigation) changes the reason. Neither is
        # suppressed. The first call of a run has no previous reason, so it always runs.
        prev = (self.surface, getattr(self, '_surface_reason', None))
        self.surface = name
        self._surface_reason = reason
        if prev[0] == name and prev[1] == reason:
            return True
        self.surface_applied = name
        if name == 'strip':
            # THE STYLESHEET DECIDES THE HEIGHT (`panel.css:52`), and this is the
            # moment it matters: the page is loaded by the time a surface is
            # applied, so the read answers with the real number instead of a copy
            # kept in this file.
            if present:
                # NOT ON THE SHOW PATH. These two reads cost 1,75 s on one press
                # (measured 2026-11-01, `STRIP_WIDTH from=None to=380` at 47.815
                # and `WINDOW_GEOMETRY` at 49.566): `exec_js` waits on the SAME UI
                # thread that is about to map the window. So the cached numbers go
                # into this geometry and the re-measure is POSTED for right after.
                self._post_metrics_refresh(name, reason)
            else:
                self.refresh_strip_height(f'surface-{reason}')
                self.refresh_strip_width(f'surface-{reason}')
        script = ('(function () { if (window.SottoSurfaces) { '
                  'window.SottoSurfaces.set(' + json.dumps(name) + '); '
                  'return window.SottoSurfaces.current(); } return null; })()')
        # THE DOCUMENT'S ANSWER IS A LOG FIELD, NEVER A GATE. It is read only when
        # nothing is waiting on this call; on the show path it is POSTED and the
        # line says `document_surface=posted`.
        if present:
            applied = 'posted' if self.exec_js_post(script) else None
        else:
            applied = self.exec_js(script)
        geometry = self.geometry_for(name)
        if name == 'strip':
            # THE DOCK BASE, AND THE OWNER'S DRAG RESTORED FROM THE PAGE.
            # The page paints the saved offset as a CSS transform, but it cannot
            # move the WINDOW, so without this the bar would be pushed out of a
            # window that is now exactly the pill. The offset is read from the
            # page (its localStorage is the record) and the shell moves the
            # window, then tells the page to stop transforming so the two do not
            # add up.
            self._strip_dock_base = (int(geometry['x']), int(geometry['y']))
            # THE CACHED OFFSET ON THE SHOW PATH -- see `_strip_offset_from_page`
            # for the record and `_set_strip_offset` for the writer: the drag
            # itself keeps the cache current, so a show only pays for the read
            # when the cache has never been filled.
            offset = self._strip_offset()
            if offset != (0, 0):
                geometry = self._strip_offset_geometry(geometry, offset)
                if present:
                    self.exec_js_post(STRIP_MOVED_JS)
                else:
                    self.exec_js(STRIP_MOVED_JS)
                log(f'STRIP_DRAG_RESTORED offset={offset} '
                    f'to=({geometry["x"]},{geometry["y"]})')
        self._apply_window_geometry(geometry, reason=f'surface-{name}',
                                    present=present)
        self.surface_applied = name
        log(f'PANEL_SURFACE surface={name} reason={reason} '
            f'document_surface={json.dumps(applied)} '
            f'window={geometry["width"]}x{geometry["height"]}'
            f'@({geometry["x"]},{geometry["y"]}) '
            f'docked={geometry["docked"]} '
            f'edit_mode={str(self.edit_mode).lower()}')
        self.publish_panel_visibility(f'surface-{name}')
        return True
    def _strip_offset(self):
        """O offset do drag: da CACHE; so' le' da pagina quando a cache esta' vazia.

        A cache e' escrita pelo proprio drag (`_set_strip_offset`), que JA' sabe o
        offset -- portanto depois do primeiro drag uma exibicao nunca paga uma
        leitura. Sem cache (processo recem-arrancado) a leitura acontece aqui, e um
        `NoAnswer` devolve `(0, 0)`: o dock e' o fallback honesto.
        """
        cached = getattr(self, '_strip_offset_cache', None)
        if cached is None:
            try:
                cached = self._strip_offset_from_page()
            except Exception as exc:  # noqa: BLE001
                log(f'STRIP_OFFSET_CACHE_FAILED error={exc!r}')
                cached = (0, 0)
            self._strip_offset_cache = cached
        return cached

    def _post_metrics_refresh(self, name, reason):
        """Re-measure the strip's metrics OFF the show path, and adopt them.

        PORQUE UMA THREAD E NAO `_post`: `refresh_strip_*` chamam `exec_js`, que
        espera por um `BeginInvoke` no UI thread -- chamado DE DENTRO do UI thread
        (o que `_post` faz) isso e' o deadlock que `_post` documenta. Uma thread
        propria marshala como a thread da hotkey sempre marshallou, e nao segura
        nem o show nem o UI thread.

        Se os numeros MUDARAM e a janela ainda veste esta superficie, a geometria e'
        reaplicada -- e' o unico custo: um ajuste pequeno (um nudge) na PRIMEIRA
        faixa de um processo, quando a cache ainda nao existia. A alternativa era
        1,75 s de espera em cada pressao.
        """
        def _worker():
            try:
                moved = self.refresh_strip_height(f'posted-{reason}')
                moved = self.refresh_strip_width(f'posted-{reason}') or moved
                if moved and name == 'strip' and self.hwnd \
                        and self.surface_applied == 'strip':
                    self._apply_window_geometry(self.geometry_for('strip'),
                                                reason=f'metrics-{reason}')
            except Exception as exc:  # noqa: BLE001 -- nunca matar o show
                warn(f'STRIP_METRICS_REFRESH_FAILED reason={reason} error={exc!r}')
        try:
            t = threading.Thread(target=_worker, name='sotto-strip-metrics',
                                 daemon=True)
            t.start()
            return True
        except Exception as exc:  # noqa: BLE001
            warn(f'STRIP_METRICS_REFRESH_POST_FAILED reason={reason} error={exc!r}')
            return False

    def _strip_offset_from_page(self):
        """The owner's strip drag offset, READ OUT OF THE PAGE. `(0, 0)` if none.

        `localStorage['sotto:strip-offset']` is `{"x": int, "y": int, "v": 1}`
        (panel.html:1083): the CUMULATIVE offset in DIP from the docked position.
        The page owns the record and the shell reads it, so there is exactly one
        copy of the number. Anything unparsable answers `(0, 0)` -- a bar at the
        dock is the honest fallback for a record that cannot be read."""
        script = ("(() => { try {"
                  "const raw = window.localStorage.getItem('sotto:strip-offset');"
                  "if (!raw) return null;"
                  "const v = JSON.parse(raw);"
                  "if (!v || typeof v !== 'object') return null;"
                  "return String(Math.round(Number(v.x) || 0)) + ','"
                  "     + String(Math.round(Number(v.y) || 0));"
                  "} catch (err) { return null; } })()")
        try:
            raw = self.exec_js(script)
        except Exception as exc:  # noqa: BLE001
            log(f'STRIP_OFFSET_READ_FAILED error={exc!r}')
            return (0, 0)
        if not isinstance(raw, str) or ',' not in raw:
            return (0, 0)
        a, _, b = raw.partition(',')
        try:
            return (int(float(a)), int(float(b)))
        except ValueError:
            log(f'STRIP_OFFSET_UNPARSED raw={json.dumps(raw)}')
            return (0, 0)

    def _strip_offset_geometry(self, geometry, offset):
        """`geometry` shifted by `offset` and CLAMPED into the work area."""
        work = self.work_area()
        width = int(geometry.get('width') or 0)
        height = int(geometry.get('height') or 0)
        g = dict(geometry)
        g['x'] = max(work['x'], min(int(geometry.get('x') or 0) + int(offset[0]),
                                    work['x'] + work['width'] - width))
        g['y'] = max(work['y'], min(int(geometry.get('y') or 0) + int(offset[1]),
                                    work['y'] + work['height'] - height))
        g['docked'] = 'strip-dragged'
        return g

    def _set_strip_offset(self, payload):
        """The page's strip drag: move the WINDOW by the offset it reports.

        The offset is CUMULATIVE from the dock, so this never accumulates a
        delta -- `_strip_dock_base` is the fixed origin. The move is a bare
        `SetWindowPos` with `SWP_NOSIZE`, the same shape as `edit_drag_to`, and
        the geometry is persisted only when the drag ENDS."""
        payload = payload or {}
        try:
            dx = int(round(float(payload.get('x') or 0)))
            dy = int(round(float(payload.get('y') or 0)))
        except (TypeError, ValueError):
            log(f'STRIP_DRAG_REFUSED why=unparsable payload={payload!r}')
            return
        phase = str(payload.get('phase') or 'move')
        # O DRAG E' A FONTE VIVA DO OFFSET: ver `_strip_offset`, que o le' da cache
        # no show. Sem isto, cada exibicao teria de ler `localStorage` -- uma ida
        # ao UI thread no caminho do show, que e' o que `exec_js_post` existe para
        # tirar de la'.
        self._strip_offset_cache = (dx, dy)
        if self.hwnd is None:
            return
        if self.surface_applied != 'strip':
            log(f'STRIP_DRAG_REFUSED why=not-strip surface={self.surface_applied}')
            return
        base = self._strip_dock_base
        if base is None:
            geometry = dict(self.geometry or {})
            base = (int(geometry.get('x') or 0), int(geometry.get('y') or 0))
            self._strip_dock_base = base
        geometry = dict(self.geometry or {})
        width = int(geometry.get('width') or 0)
        height = int(geometry.get('height') or 0)
        if width <= 0 or height <= 0:
            return
        work = self.work_area()
        nx = max(work['x'], min(base[0] + dx, work['x'] + work['width'] - width))
        ny = max(work['y'], min(base[1] + dy, work['y'] + work['height'] - height))
        geometry['x'] = nx
        geometry['y'] = ny
        geometry['docked'] = 'strip-dragged'
        self.geometry = geometry
        scale = (self.display or {}).get('scaleFactor') or 1.0
        try:
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST,
                                int(nx * scale), int(ny * scale), 0, 0,
                                SWP_NOSIZE | SWP_NOACTIVATE)
        except Exception as exc:  # noqa: BLE001
            log(f'STRIP_DRAG_MOVE_FAILED error={exc!r}')
            return
        # The page stops transforming once the WINDOW moves, or the two add up.
        #
        # ONCE PER DRAG, NOT ONCE PER MOVE. MEASURED 2026-10-13 by the audit lane: one
        # real drag produced 277 moves in 1.86 s -- about 149 a second -- and this was a
        # SYNCHRONOUS `ExecuteScriptAsync` round trip on every one of them. The script it
        # runs only sets `data-strip-moved` to '1', which is IDEMPOTENT: after the first
        # call it can change nothing. The sibling path `edit_drag_to` refuses to call
        # `exec_js` at all, in its own words "so the loop stays responsive".
        #
        # It is NOT removed, because the comment above is a real reason: the page must
        # stop transforming once the window moves. It is sent on the FIRST move of a drag
        # and the flag is cleared on `end`, so the next drag gets it again. The flag is
        # read with getattr so this needs no init site and cannot break an older object.
        if not getattr(self, '_strip_moved_sent', False):
            self.exec_js(STRIP_MOVED_JS)
            self._strip_moved_sent = True
        if phase == 'end':
            self._strip_moved_sent = False
            self.saved_geometry = self.geometry_snapshot()
            self.publish_panel_visibility('strip-drag')
        log(f'STRIP_DRAG phase={phase} offset=({dx},{dy}) to=({nx},{ny}) '
            f'base={base} work={work["width"]}x{work["height"]}')

    #: Windows' "start a caption drag" message pair. `WM_NCLBUTTONDOWN` with
    #: `HTCAPTION` puts the window manager in its OWN modal move loop: the mouse
    #: is tracked by Windows, not by the page, so there is no per-move bridge
    #: message and no per-move `SetWindowPos`.
    WM_NCLBUTTONDOWN = 0x00A1
    HTCAPTION = 2

    def _begin_window_drag(self, payload):
        """ONE native drag for the panel header or the bottom strip.

        Owner, 2026-10-17: *"mover os paineis e extremamente ruim e nao
        otimizado, parece q foi implementado completamente errado."* The old
        path moved the window from a JS `pointermove` at up to ~150 samples a
        second, every one of them a bridge hop plus a `SetWindowPos` plus a log
        line. This enters `DefWindowProc`'s move loop instead: `SendMessageW`
        blocks until the owner releases the mouse, and the window follows the
        cursor at compositor speed with zero page involvement.

        The final rect is read after the loop returns, clamped into the work
        area, and persisted exactly once -- the same `geometry`/_main/
        panel-visibility.json contract the edit-mode drag uses.
        """
        payload = payload or {}
        surface = str(payload.get('surface') or self.surface_applied or 'panel')
        if surface not in ('panel', 'strip'):
            surface = self.surface_applied or 'panel'
        hwnd = self.hwnd
        if not hwnd:
            log(f'WINDOW_DRAG_REFUSED why=no-hwnd surface={surface}')
            return
        log(f'WINDOW_DRAG_BEGIN surface={surface} hwnd={hwnd}')
        try:
            user32.ReleaseCapture()
            # The return value is 0 for this message (DefWindowProc), so it is
            # deliberately not tested: the observable result is the rect below.
            user32.SendMessageW(hwnd, self.WM_NCLBUTTONDOWN, self.HTCAPTION, 0)
        except Exception as exc:  # noqa: BLE001
            log(f'WINDOW_DRAG_FAILED surface={surface} error={exc!r}')
            return
        self._persist_dragged_geometry(hwnd, surface)

    def _persist_dragged_geometry(self, hwnd, surface):
        """Read the rect the native loop left, clamp it, and persist it ONCE."""
        rect = RECT()
        try:
            if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                log(f'WINDOW_DRAG_RECT_FAILED surface={surface} '
                    f'last_error={ctypes.get_last_error()}')
                return
        except Exception as exc:  # noqa: BLE001
            log(f'WINDOW_DRAG_RECT_FAILED surface={surface} error={exc!r}')
            return
        # The drop may be on another monitor: refresh the target (and therefore
        # its scale factor) BEFORE converting the physical rect to DIP.
        work = self.work_area()
        scale = (self.display or {}).get('scaleFactor') or 1.0
        width = max(0, int(round((rect.right - rect.left) / scale)))
        height = max(0, int(round((rect.bottom - rect.top) / scale)))
        if width <= 0 or height <= 0:
            log(f'WINDOW_DRAG_RECT_EMPTY surface={surface} '
                f'rect=({rect.left},{rect.top},{rect.right},{rect.bottom})')
            return
        x = int(round(rect.left / scale))
        y = int(round(rect.top / scale))
        clamped_x = max(work['x'], min(x, work['x'] + work['width'] - width))
        clamped_y = max(work['y'], min(y, work['y'] + work['height'] - height))
        # A drag that ran past an edge is pulled back, so the window can never
        # be left unreachable. One `SetWindowPos`, only when the clamp moved it.
        if (clamped_x, clamped_y) != (x, y):
            try:
                user32.SetWindowPos(hwnd, HWND_TOPMOST,
                                    int(clamped_x * scale), int(clamped_y * scale),
                                    0, 0, SWP_NOSIZE | SWP_NOACTIVATE)
            except Exception as exc:  # noqa: BLE001
                log(f'WINDOW_DRAG_CLAMP_FAILED surface={surface} error={exc!r}')
        geometry = dict(self.geometry or {})
        geometry.update({
            'surface': self.surface_applied,
            'x': clamped_x,
            'y': clamped_y,
            'width': width,
            'height': height,
            'docked': 'window-drag',
            'workWidth': work['width'],
            'workHeight': work['height'],
        })
        self.geometry = geometry
        self.saved_geometry = self.geometry_snapshot()
        self.publish_panel_visibility('window-drag')
        log(f'WINDOW_DRAG_DONE surface={surface} to=({clamped_x},{clamped_y}) '
            f'size={width}x{height} from=({x},{y})')

    CAPTION_WANTED_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), '_main', 'caption-wanted.json')

    def _caption_wanted_restored(self):
        """O estado do interruptor da legenda, como ficou da ultima sessao."""
        try:
            # `io` NAO E' IMPORTADO NESTE FICHEIRO (medido 2026-11-03: o
            # `NameError` caia no `except` e a restauracao devolvia False em
            # SILENCIO -- o interruptor nunca voltava). `open` do builtin.
            with open(self.CAPTION_WANTED_PATH, encoding='utf-8') as handle:
                data = json.load(handle)
            on = bool(data.get('on'))
            log('CAPTION_WANTED_RESTORED on=%s from=%s'
                % (str(on).lower(), data.get('at') or '-'))
            return on
        except Exception:  # noqa: BLE001 -- ausente e' o normal da primeira vez
            return False

    def _caption_wanted_store(self, on):
        """Grava o interruptor. Falhar nao pode derrubar o gesto do dono."""
        try:
            import datetime
            tmp = self.CAPTION_WANTED_PATH + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as handle:
                json.dump({'on': bool(on),
                           'at': datetime.datetime.now().isoformat(timespec='seconds')},
                          handle)
            os.replace(tmp, self.CAPTION_WANTED_PATH)
        except Exception as exc:  # noqa: BLE001
            log(f'CAPTION_WANTED_STORE_FAILED error={exc!r}')

    def _set_live_enabled(self, payload):
        """O interruptor do botao LIVE: mostra/esconde a janela da legenda.

        ISTO E UM INTERRUPTOR DO DONO, NAO UM IMPULSO. `_caption_wanted` fica
        True ate ele voltar a clicar; e `push_caption_to_window` so escreve na
        janela quando a flag esta ligada. Antes, cada linha de legenda levantava a
        janela por si (sem clique nenhum no log) e o botao so pintava.

        `show_caption_window(on)` continua a ser quem mostra/esconde e quem escreve
        `data-caption-window` -- a pagina pinta o botao a partir desse atributo.

        O PANEL NAO SE FECHA. A regra de 2026-10-17 ("ligar a legenda esconde o
        painel") foi TROCADA pelo dono a 2026-10-19, verbatim: *"clicar pra
        ligar a legenda pelo painel do alt c nao deve fechar o painel. com o painel
        aberto, usar alt c uma vez nao deve fechar o painel. deve ligar ou desligar
        a legenda mesmo com qualquer dos paineis abertos."*

        O QUE SE VIA, e porque o dono escrevia que o Alt+C "nao ta ligando ou
        desligando bem": um Alt+C com o painel aberto LIGAVA a legenda E FECHAVA
        o painel. Duas accoes num gesto, e a segunda apagava a prova da primeira.
        O interruptor e um interruptor: liga, desliga, e nao mexe no painel.

        `show_caption_window(on)` continua a ser quem mostra/esconde a janela
        NATIVA da legenda e quem escreve `data-caption-window` -- a pagina pinta o
        botao e o indicador a partir desse atributo. O que mudou foi so o
        `hide_panel('caption-on')` que accompanyava, que nao existe mais.

        A JANELA NATIVA E SEPARADA DO PAINEL, e por isso os dois podem estar
        visiveis ao mesmo tempo: a legenda e um overlay livre na tela do dono
        ("sem estar conectada a qualquer painel", owner, 2026-10-17), e o painel
        e onde se liga e desliga. Fechar um por causa do outro era o defeito."""
        on = bool((payload or {}).get('on'))
        try:
            self._caption_wanted = on
            self._caption_wanted_store(on)
            # A LINHA DO INTERRUPTOR SAI NO INSTANTE DA DECISAO, NAO NO FIM DO
            # TRABALHO DE UI (2026-11-03). Medido no log do dono: a pressao das
            # 02:45:24.645 so' deixou `LIVE_ENABLED on=false` as 02:45:51.919 --
            # 27,3 s -- porque a linha vinha DEPOIS de `show_caption_window`, que
            # esperava pelo UI thread. Resultado: as linhas do log ficavam fora de
            # ordem em relacao as accoes (`on=true` das 19.219 e' do botao LIVE,
            # nao de uma tecla: nao ha pressao `role=live` antes das 24.645), e o
            # instrumento de aceitacao (`_main/altc-first-caption-oracle.py`)
            # media a espera, nao o gesto. A ACCAO e' o que se mede primeiro; o
            # que a janela demora a fazer vem depois e diz-se por si.
            log(f'LIVE_ENABLED on={str(on).lower()} wanted={str(on).lower()} '
                f'panel_closed=false')
            # O PANEL NAO SE FECHA -- ver a docstring: a ordem de 2026-10-19
            # trocou a de 2026-10-17, e o `hide_panel('caption-on')` que vivia
            # aqui era a causa do "o alt c nao ta ligando ou desligando bem".
            self.show_caption_window(on)
        except Exception as exc:  # noqa: BLE001
            log(f'LIVE_ENABLED_FAILED on={str(on).lower()} error={exc!r}')

    def _pause_shell(self, payload):
        """PAUSE = UNLOAD the worker, freeing its CUDA context and VRAM."""
        reason = str((payload or {}).get('reason') or 'panel')
        bridge = getattr(self, 'bridge', None)
        if bridge is None or getattr(bridge, 'child', None) is None:
            self._paused = True
            log(f'WORKER_PAUSED reason={reason} already=true')
            self.apply_panel_state(
                'Paused - engines unloaded', 'idle',
                {'title': 'Paused',
                 'body': 'The live and background engines are unloaded. Click the '
                         'status to reload them.'})
            return {'paused': True, 'text': 'Paused - engines unloaded'}
        pid = getattr(bridge.child, 'pid', None)
        bridge.stop('pause')
        self.bridge = None
        self._paused = True
        self._external_parked = False
        log(f'WORKER_PAUSED reason={reason} pid={pid}')
        self.apply_panel_state(
            'Paused - engines unloaded', 'idle',
            {'title': 'Paused',
             'body': 'The live and background engines are unloaded, so their VRAM '
                     'is free. Click the status to reload them.'})
        return {'paused': True, 'text': 'Paused - engines unloaded'}

    def _apply_window_geometry(self, geometry, reason='surface', present=False):
        """Move/resize the NATIVE window, then pin the client area to it.

        ONE call per surface change and one per edit-mode drag sample — never per
        frame. `docs/release-and-overlay-plan.md:75-78` is the warning this obeys:
        moving the native window every frame is the short path to flicker.

        `present=True` is the show path, and there the two PAGE steps at the end
        are POSTED instead of waited for: `_ui`'s default budget is 10,0 s
        (`UI_MARSHAL_TIMEOUT_S`) and `send_geometry` is exactly the
        `window.__sotto_emit("geometry", …)` that cost the owner 10,0 s of one
        press (2026-11-01). The window is already at the right rect when they run;
        both only make the DOCUMENT agree, and the document can wait for a frame.
        """
        self.geometry = geometry
        hwnd = self.hwnd
        scale = (self.display or {}).get('scaleFactor') or 1.0
        if hwnd:
            ctypes.set_last_error(0)
            ok = user32.SetWindowPos(
                hwnd, HWND_TOPMOST,
                int(geometry['x'] * scale), int(geometry['y'] * scale),
                int(geometry['width'] * scale), int(geometry['height'] * scale),
                SWP_NOACTIVATE)
            # The ERROR CODE, not just the boolean: measured on this host,
            # `ok=false` with the size applied and the position NOT — which is
            # only diagnosable from the code (`1400` = ERROR_INVALID_WINDOW_HANDLE
            # is what a mis-marshalled `HWND_TOPMOST` produces).
            log(f'WINDOW_GEOMETRY reason={reason} ok={str(bool(ok)).lower()} '
                f'last_error={ctypes.get_last_error()} '
                f'work={geometry.get("workWidth")}x{geometry.get("workHeight")}'
                f'@({geometry.get("workX")},{geometry.get("workY")}) '
                f'window={geometry["width"]}x{geometry["height"]}'
                f'@({geometry["x"]},{geometry["y"]}) '
                f'margin={geometry.get("margin")} '
                f'docked={geometry["docked"]} '
                f'visible={str(window_visible(hwnd)).lower()}')
        # The CLIENT area is forced after every resize, for the reason
        # `_fit_client_area` documents: pywebview sizes the WebView2 child to the
        # client area computed under the OLD border, so a resize without this
        # leaves the document laid out at the previous size.
        #
        # ON THE SHOW PATH IT IS POSTED, NOT AWAITED. `_fit_client_area` is a
        # UI-thread call and `_ui` waits up to `UI_MARSHAL_TIMEOUT_S` (10,0 s)
        # for that thread -- which, during a show, is the thread doing the map.
        if present:
            try:
                self._post(lambda: self._fit_client_area(self._form()))
            except Exception as exc:  # noqa: BLE001 -- report, never kill the show
                warn(f'WINDOW_GEOMETRY_CLIENT_POST_FAILED reason={reason} '
                     f'error={exc!r}')
            self.send_geometry(post=True)
            return
        try:
            self._ui(lambda: self._fit_client_area(self._form()))
        except Exception as exc:  # noqa: BLE001 -- report, never kill the panel
            warn(f'WINDOW_GEOMETRY_CLIENT_FAILED reason={reason} error={exc!r}')
        self.send_geometry()
    def shedding_level(self):
        """O nivel de shedding que o WORKER tem de obedecer, ou None.

        Lido do monitor VIVO (`LoadSheddingMonitor.state.level`), nunca de uma
        copia: o nivel muda enquanto a app corre e e' o ficheiro da visibilidade
        que o leva ao worker (`PanelVisibilityWriter` -> `shed`). None (monitor
        ainda nao existe, ou `SOTTO_LOAD_SHED=0`) significa que a chave `shed`
        NAO e' escrita -- o worker fica com o comportamento que sempre teve.
        """
        monitor = getattr(self, '_load_shedding', None)
        if monitor is None:
            return None
        try:
            return str(monitor.state.level)
        except Exception:  # noqa: BLE001 -- um nivel ilegivel nao e' um nivel
            return None

    def geometry_snapshot(self):
        """The rect to PERSIST, in the shape the `geometry` key carries.

        The surface is the one the WINDOW wears (`surface_applied`), never the
        one the owner's next Alt+C will ask for: at startup the window is at the
        docked-panel rect while `self.surface` already says `'strip'`, and
        labelling that rect `strip` would teach the restore path to open the
        strip at the panel's size.
        """
        geometry = self.geometry
        if not isinstance(geometry, dict):
            return None
        return {
            'surface': self.surface_applied,
            'x': int(geometry.get('x') or 0),
            'y': int(geometry.get('y') or 0),
            'width': int(geometry.get('width') or 0),
            'height': int(geometry.get('height') or 0),
            'docked': str(geometry.get('docked') or ''),
            'workWidth': int(geometry.get('workWidth') or 0),
            'workHeight': int(geometry.get('workHeight') or 0),
        }
    def restore_saved_geometry(self):
        """Read the `geometry` key the last edit wrote, and CLAMP it.

        ONE FILE, NOT TWO. `_main/panel-visibility.json` already exists and is
        written by `PanelVisibilityWriter`; a second file would let the shell and
        the worker's poll disagree about which one is authoritative. The key is
        additive: `schema` stays `sotto.panel-visibility/1` because no field was
        renamed or removed, and the worker's reader (`PanelVisibilityReader`)
        reads `visible`/`writtenAtEpoch`/`staleAfterSeconds` and ignores the rest
        — verified by reading it, not assumed.

        The clamp happens HERE, once, so the log carries the move exactly once
        instead of on every show.
        """
        try:
            with open(PANEL_VISIBILITY_PATH, encoding='utf-8') as fh:
                payload = json.load(fh)
        except FileNotFoundError:
            return None
        except Exception as exc:  # noqa: BLE001 -- a bad file is not a crash
            warn(f'PANEL_GEOMETRY_RESTORE_FAILED path={PANEL_VISIBILITY_PATH} '
                 f'error={exc!r}')
            return None
        rect = payload.get('geometry') if isinstance(payload, dict) else None
        if not isinstance(rect, dict):
            return None
        name = normalise_surface_name(rect.get('surface'))
        if name is None:
            warn('PANEL_GEOMETRY_RESTORE_REFUSED '
                 f'surface={json.dumps(str(rect.get("surface")))}')
            return None
        geometry, moved = clamp_geometry(rect, self.work_area())
        self.saved_geometry = {
            'surface': name, 'x': geometry['x'], 'y': geometry['y'],
            'width': geometry['width'], 'height': geometry['height'],
            'docked': geometry['docked'],
        }
        log('PANEL_GEOMETRY_RESTORED '
            f'surface={name} '
            f'rect={geometry["width"]}x{geometry["height"]}'
            f'@({geometry["x"]},{geometry["y"]}) '
            f'writtenAt={payload.get("writtenAt")} '
            f'clamped={str(moved).lower()}')
        if moved:
            log('PANEL_GEOMETRY_CLAMPED '
                f'surface={name} '
                f'was={rect.get("width")}x{rect.get("height")}'
                f'@({rect.get("x")},{rect.get("y")}) '
                f'now={geometry["width"]}x{geometry["height"]}'
                f'@({geometry["x"]},{geometry["y"]}) '
                f'work={geometry["workWidth"]}x{geometry["workHeight"]}'
                f'@({geometry["workX"]},{geometry["workY"]})')
        return self.saved_geometry
    def refresh_strip_height(self, reason='surface-strip'):
        """Re-read the stylesheet's height and adopt it, once per real change.

        `self.strip_height_extra` is the runtime ADDITION (0 today — nothing calls
        `set_strip_height`, because the hover reveal is the panel lane's CSS). So
        the window height is `css + extra`, and a theme edit moves the window on
        the next strip application. Returns True when the number moved.
        """
        value = self.strip_height_from_css()
        if value is None:
            if self.strip_height_css is None:
                log(f'STRIP_HEIGHT source=fallback '
                    f'value={self.strip_height} reason={reason} '
                    f'why=css-unavailable')
            return False
        value = int(round(value))
        if value == self.strip_height_css:
            return False
        was = self.strip_height
        self.strip_height_css = value
        self.strip_height = value + self.strip_height_extra
        log(f'STRIP_HEIGHT from={was} to={self.strip_height} source=css '
            f'css_value={value} extra={self.strip_height_extra} reason={reason}')
        return True
    def on_worker_status(self, text, kind, info):
        self.apply_panel_state(text, kind, info)
        # A status line is the boundary signal: an exit/`done`/`error` closes
        # the capture guard, so a reload held mid-stream can land here.
        self._reload_policy.boundary(why='status')

    def code_state_log(self, reason):
        """One line: is the running code the code on disk? Both files, one word."""
        try:
            state = self._reload_policy.state()
        except Exception as exc:
            # A staleness read must never be the reason the shell stops.
            warn(f'CODE_STATE_UNAVAILABLE reason={reason} error={exc!r}')
            return
        worker = state.get('worker') or {}
        shell = state.get('shell') or {}
        log(f'CODE_STATE reason={reason} '
            f'worker_disk={worker.get("disk")} '
            f'worker_loaded={worker.get("loaded")} '
            f'worker_stale={worker.get("stale")} '
            f'shell_disk={shell.get("disk")} '
            f'shell_loaded={shell.get("loaded")} '
            f'shell_stale={shell.get("stale")}')

    # -- hot reload --------------------------------------------------------
    # `hot_reload.py` watches and debounces; WHAT a reload means is decided
    # here, because only this object knows about the CoreWebView2 and the
    # bridge. The Electron arm splits it the same way (hot-reload.js watches,
    # main.js reloads) — same shape, different engine.
    def start_hot_reload(self):
        self.hot_reload = hot_reload.HotReload(
            log=log,
            on_panel_assets_changed=self.reload_panel_assets,
            on_worker_changed=self.restart_worker,
            panel_dir=PANEL_DIR,
            worker_dir=os.path.dirname(os.path.abspath(self.args.worker)),
        )
        return self.hot_reload.start()

    def reload_panel_assets(self, files):
        """Re-navigate the live page, in place, without a new window.

        THE MECHANISM IS THE STAGING BOUNCE, and it is not a cache-busting
        trick: this re-runs `stage.html` -> `panel.html`, the SAME navigation
        pair that brings the panel up at startup and is therefore already known
        to land on the real document. `_on_loaded` sees `staged == False`, does
        the staging navigation, and on the next load takes the panel branch and
        its `HOT_RELOAD_APPLIED` half; the `startup_done` guard keeps the
        once-per-process startup actions (geometry is re-sent by that branch,
        the worker is NOT respawned, `--selftest` does not run twice) from
        running again. The document that arrives is a fresh parse of the fresh
        bytes, which is what a `file://` stylesheet gets no guarantee of.

        WHY THE OLD MECHANISM WAS WRONG — `docs/audit/auditoria-completa-
        20261007.md` F5, measured and reproduced twice on 2026-10-06. It built

            url = file_url(PANEL_HTML) + f'?sotto_hr={self.reload_count}'

        i.e. a QUERY STRING on a `file://` URL, and `?` is not a legal Windows
        filename character, so the navigation failed and the pane landed on
        `chrome-error://chromewebdata/` — Chromium's OWN error page. The
        receipts are `_main/panel-state.json` reading `panel.url =
        chrome-error://chromewebdata/` with `panel.live.count = -1`, which is
        `PANEL_STATE_PROBE`'s sentinel for `#caption-list` ABSENT. The feature
        therefore destroyed the thing it exists to refresh: after any panel-file
        edit the panel stopped painting, the owner's transcript stopped growing
        with it, and only a shell restart brought it back. Any cache-busting
        that changes the URL of a `file://` document is out for the same reason.

        The hotkey belongs to THIS process, not to the page, so a re-navigation
        cannot lose Alt+C. It is re-read anyway and a loss is logged, because a
        hot reload that silently eats the only way to open the panel is the
        failure the owner would notice first.
        """
        if self.core is None or self.window is None:
            log(f'HOT_RELOAD_PANEL_SKIPPED files={json.dumps(files)} '
                'reason=no-core')
            return False
        self.reload_count += 1
        # `self.staged`, NOT `self._staged`: `_on_loaded` reads the public one to
        # decide whether the current document is the staging page. Setting a
        # misspelled twin here looked correct and did nothing, so the reload
        # re-ran the staging navigation and the panel came up on stage.html.
        # It is set to False (NOT True, as the old code did): False is what
        # makes `_on_loaded` perform the staging bounce instead of treating
        # stage.html as if it were already the panel.
        self.staged = False

        def _go():
            self.window.load_url(file_url(STAGE_HTML))

        try:
            self._ui(_go)
        except Exception as exc:
            log(f'HOT_RELOAD_PANEL_THREW files={json.dumps(files)} '
                f'error={exc!r}')
            return False
        log(f'HOT_RELOAD_PANEL_DONE files={json.dumps(files)} '
            f'reload={self.reload_count} hotkey={self.args.hotkey}')
        return True

    def restart_worker(self, files):
        """Queue a worker reload. The POLICY decides if and when it may run.

        The old body restarted on the spot, which is the churn the owner saw:
        with five lanes editing `worker/sotto_worker.py` all morning and a
        250 ms watcher window that ends between their saves, every save cost a
        full worker respawn — i.e. a model load (2.0-8.3 s, 1.4-2.1 GB, measured
        in `worker/runs/*.jsonl`). The reload is now debounced, and it is HELD
        while a capture stream is open. See `WorkerReloadPolicy`.
        """
        if self.bridge is None:
            log(f'HOT_RELOAD_WORKER_SKIPPED files={json.dumps(files)} '
                'reason=no-worker-running')
            return False
        # THE FIRST DOOR: do not even QUEUE it. Policy, debounce, idle timers and
        # the boundary all run before the last door, and each of them costs the
        # owner a log line and a timer for something that is now refused.
        if not worker_restart_allowed(files):
            return False
        return self._reload_policy.request(files)

    def _do_worker_restart(self, files):
        """The one place a hot reload actually stops and restarts the worker."""
        # THE LAST DOOR. Everything upstream can be edited by accident; this
        # cannot be argued with. Default OFF — see `worker_restart_allowed`.
        if not worker_restart_allowed(files):
            return False
        if self.bridge is None:
            return False
        self.bridge.stop('hot-reload')
        self.bridge = None
        started = self.start_worker('hot-reload')
        log(f'HOT_RELOAD_WORKER_RESTART files={json.dumps(files)} '
            f'spawns={self.bridge.spawns if self.bridge else 0} '
            f'started={str(started).lower()}')
        return started

    def stop_hot_reload(self, reason):
        if self.hot_reload is not None:
            self.hot_reload.stop(reason)
        self._reload_policy.stop()

    # -- probes ------------------------------------------------------------
    def run_dump_dom(self):
        """The Electron arm's --dump-dom: same probe, same line shape.

        Unlike the Electron arm this does NOT show the window: the dump measures
        the DOM, not a pixel surface, and a measurement run must not put a window
        on the owner's screen (main.js has to show it only because capturePage()
        needs a drawable surface).
        """
        dump = self.exec_js(DUMP_DOM_PROBE)
        if not dump:
            # THE REASON, NOT A BARE "nothing" (2026-10-20): a `NoAnswer`
            # says WHICH kind of nothing it was.
            reason = dump.get('reason') if isinstance(dump, NoAnswer) else 'empty'
            log(f'DOMDUMP failed: probe returned nothing reason={reason}')
            self.request_exit(3, reason='dump-dom-failed')
            return
        log('DOMDUMP ' + json.dumps(dump, separators=(',', ':')))
        probe = self.exec_js(BRIDGE_PROBE) or {}
        log('BRIDGEPROBE ' + json.dumps(probe, separators=(',', ':')))

        # The gate has to survive a page that is NOT the panel. It once passed
        # vacuously: `panelSaidBridgeMissing` is the ABSENCE of a string in the
        # body, and a 404 page has no body text at all — so an earlier run
        # printed `hasSotto=true panelSaidBridgeMissing=false` while the URL was
        # `http://127.0.0.1:23602/electron/panel.html` returning
        # "Error: 404 Not Found" with no `#panel` anywhere. Three conditions,
        # all required, so the panel must be the document that answered.
        failures = []
        if probe.get('panelSaidBridgeMissing'):
            failures.append('panel-reported-missing-preload')
        if not probe.get('hasPanelElement'):
            failures.append('no-#panel-element')
        if not str(probe.get('url') or '').endswith('panel.html'):
            failures.append(f"wrong-document={probe.get('url')}")
        if not probe.get('hasSotto'):
            failures.append('window.sotto-absent')
        if (dump.get('els') or {}).get('#panel') is None:
            failures.append('domdump-#panel-null')

        if failures:
            log('BRIDGE_GATE=RED reasons=' + ','.join(failures))
            self.request_exit(3, reason='bridge-gate-red')
            return
        log('BRIDGE_GATE=GREEN hasPanelElement=true url=' +
            f"{probe.get('url')} panelSaidBridgeMissing=false")
        self.request_exit(0, reason='dump-dom')

    def run_panel_v2_probe(self):
        """PROVE the v2 panel end to end, from the page itself.

        Three SYNCHRONOUS reads over the REAL page and the REAL bridge, spaced
        by real waits: inject a caption through `window.sotto.pushCaption` (the
        channel the worker drives), let the formulation hold expire, read the
        live box and the feed, drive a UI search, then read the search results.
        The disk half is read back through the shell's OWN store, so the feed
        and the file on disk are checked by two independent paths tied to the
        same unique token.
        """
        stamp = 'SOTTO-V2-' + str(int(time.time() * 1000))
        injected = self.exec_js(PANEL_V2_INJECT) or {}
        # The LIVE caption is driven through the REAL worker path — the very
        # `on_worker_caption` the WorkerBridge calls — so this exercises
        # worker -> shell -> emit('caption') -> preload -> panel.js -> live box
        # -> history -> disk, not a shortcut around the bridge.
        caption = 'A legenda ao vivo ' + stamp + '.'
        self.on_worker_caption(caption, {'start': 0, 'end': 2})
        time.sleep(3.0)  # COMMIT_MAX_HOLD_MS (1500) + the append round-trip
        live = self.exec_js(PANEL_V2_READ_LIVE.replace('__STAMP__', stamp)) or {}
        time.sleep(1.5)  # the search round-trip
        search = self.exec_js(PANEL_V2_READ_SEARCH) or {}

        tail = self.history_tail(5)
        search_api = self.history_search(stamp, 5)

        # The reveal guard, exercised WITHOUT opening a window: a path outside
        # the history root must be REFUSED and a missing path must be reported.
        # The success case is a real `explorer` spawn (what the button does) and
        # is deliberately NOT run here — it would put a File Explorer window on
        # the owner's desktop.
        out_reveal = {
            'outside': self.reveal_in_folder(
                os.path.join(HISTORY_ROOT, os.pardir, 'sotto_webview.py')),
            'missing': self.reveal_in_folder(
                os.path.join(HISTORY_ROOT, '1999-01-01', '00.md')),
        }

        out = dict(injected)
        out.update(live)
        out.update(search)
        out['stamp'] = stamp
        out['tail'] = tail
        out['searchApi'] = search_api
        out['revealGuard'] = out_reveal

        shape = out.get('shape') or {}
        buttons = out.get('buttons') or {}
        livebox = out.get('live') or {}
        results = out.get('search') or {}
        feed_hit = any(stamp in str(t) for t in (out.get('feed') or []))
        disk_hit = any(stamp in str(e.get('text', ''))
                       for e in (tail.get('entries') or []))
        api_hit = bool((search_api.get('hits') or []))

        # ── THE TRANSCRIPT HALF IS CONDITIONAL, AND NAMES THE BRANCH IT TOOK ──
        # The four arms below (`feed_hit`, `results.hits > 0`, `disk_hit`,
        # `api_hit`) are the ORIGINAL ones, and they can only pass while a
        # canonical producer exists: the transcript accepts a line only if
        # `meta.producer` is literally `redux` (`history-source.js:51,61-63`) and
        # NOTHING in this repo stamps that field, so today the feed is empty and
        # the disk takes no line (audit F2; `_main/history-producer-gate.js`
        # measures exactly this and names it `no-producer-in-tree`).
        #
        # Kept as an unconditional conjunction, this probe was a gate that could
        # not say yes: `--probe-v2` would exit 3 on a panel that is WORKING, and
        # the exit would be read as the panel being broken. So the arm branches on
        # the capability the shell itself publishes (`history_root()`'s
        # `canonicalProducer`), asserts the HONEST state of each branch, and
        # reports which one it took in `transcriptBranch` — a green here always
        # means "the panel did what the pipeline allows", never "the transcript
        # works".
        canonical = self.history_root().get('canonicalProducer')
        if canonical:
            transcript_ok = bool(feed_hit and results.get('hits', 0) > 0
                                 and disk_hit and api_hit)
        else:
            # Nothing can fill it: the honest expectations are an EMPTY feed, an
            # EMPTY disk, a search that found nothing — and a search INPUT the
            # panel has disabled, because a search box that cannot match is worse
            # than no search box.
            transcript_ok = bool(
                not feed_hit and not disk_hit and not api_hit
                and results.get('hits', 0) == 0
                # A CAIXA NAO EXISTE (ordem de 2026-10-21, aplicada em 2026-10-30):
                # o ramo honesto deixou de ser "desactivada" e passou a ser "ausente".
                and livebox.get('searchBoxAbsent')
            )
        out['transcriptBranch'] = 'canonical' if canonical else 'no-producer-in-tree'
        out['transcriptOk'] = transcript_ok

        out['ok'] = bool(
            shape.get('history') and shape.get('live')
            and shape.get('liveAboveHistory') and shape.get('liveBox')
            and not buttons.get('search') and not buttons.get('searchInput')
            and buttons.get('reveal')
            and out.get('historyApi')
            and livebox.get('count', 0) > 0
            and transcript_ok
            and out_reveal['outside'] is False
            and out_reveal['missing'] is False
        )
        log('PANEL_V2_PROBE ' + json.dumps(out, separators=(',', ':'),
                                           ensure_ascii=False))
        log(f'PANEL_V2_GATE={"GREEN" if out["ok"] else "RED"}')
        self.request_exit(0 if out['ok'] else 3, reason='panel-v2-probe')
        return out

    def run_stats_probe(self):
        '''MEASUREMENT for the STATS CHANNEL -- read out of the panel's OWN DOM.

        Ported 2026-10-11 from the 55c422b reference (its lines 5349-5376).
        `getStats`/`onStats` are the two members the shell owed the panel; a
        text presence check would pass on a member that is never ANSWERED, so
        this reads the CONSEQUENCE: the meter bars' inline `--meter-h` and
        `body.dataset.level`, after the panel's own 1000 ms poll has run
        against a worker that published WORKER_STATS. No window: `exec_js`
        needs no mapped surface, and `--show` is not passed.
        '''
        # NOTE: no comment syntax that swallows the rest of a line inside this
        # script -- it is ONE line of JS once concatenated.
        script = (
            '(() => ({'
            ' level: document.body.dataset.level || null,'
            ' bars: Array.from(document.querySelectorAll(' + chr(39) + '.chrome__meter i' + chr(39) + '))'
            '.map((b) => b.style.getPropertyValue(' + chr(39) + '--meter-h' + chr(39) + ')),'
            ' have: document.querySelectorAll(' + chr(39) + '.chrome__meter i' + chr(39) + ').length,'
            ' emits: (window.__sotto_emit && window.__sotto_emit.counts) || null'
            '}))()')
        try:
            value = self.exec_js(script)
        except Exception as exc:  # noqa: BLE001
            value = {'probe_failed': repr(exc)}
        log('PANEL_STATS_PROBE ' + json.dumps(value, separators=(',', ':')))
        self.request_exit(0, reason='probe-stats')

    def run_memory(self):
        report = memory_report()
        log('MEMORY ' + json.dumps(report, separators=(',', ':')))
        return report

    def run_selftest(self):
        """O instrumento do Alt+C: ver `selftest_instrument.run_selftest`.

        O metodo fica porque quem chama e' a LARGADA (`--selftest`), e o
        instrumento nao pode importar o shell de volta: as pecas do produto que
        ele mede entram por PARAMETRO -- `HotkeyThread`, as duas tabelas de
        teclas, `window_visible`, `pointer_lock_state` e o `log`.
        """
        return run_selftest(
            self, log=log, HotkeyThread=HotkeyThread,
            hotkey_numbers=hotkey_numbers, hotkey_config=hotkey_config,
            window_visible=window_visible,
            pointer_lock_state=pointer_lock_state)


# ===========================================================================
# the worker bridge — the port of app/_legacy-electron/worker-bridge.js
# ===========================================================================


class WorkerReloadPolicy:
    """Decide whether a settled worker-file change MAY restart the worker.

    The watcher (hot_reload.py) decides WHEN a burst of edits has settled; this
    object decides whether that settled burst is allowed to cost a worker
    restart -- and, when it is not, that it is QUEUED rather than dropped.
    Three rules, applied in this order:

      1. DEBOUNCE -- a trailing window (WORKER_RELOAD_DEBOUNCE_MS) coalesces a
         burst of saves from several lanes into ONE request.
      2. GUARD -- a worker that is TRANSCRIBING is never restarted under the
         owner's feet. `is_capturing()` alone was ONE flag for TWO different
         workers -- one mid-sentence, and one merely holding a stream open -- and
         on a host with nothing routed into the cable the second is the NORMAL
         state. So the guard held a worker the owner was not watching, and the
         ceiling then forced the reload anyway: MEASURED in the owner's own log,
         max_defer_ms=25000 but waited_ms=32046, i.e. the deferral bought nothing
         and cost a 32 s stall plus a warm-up. The state the owner is watching is
         a CAPTION IN FLIGHT: the guard holds while last_caption_at is younger
         than max_defer_ms, and a worker with nothing in flight is applied at once
         (HOT_RELOAD_WORKER_IDLE_APPLIED). A held reload lands at the next
         boundary: either a natural respawn already re-read the file, or the
         reload is applied here.
      3. FLOOR -- the model may not be reloaded more often than
         WORKER_RELOAD_MIN_INTERVAL_MS, because every reload costs a warm-up.

    WHY A HELD RELOAD NEEDS A CEILING. The guard's exit cannot be
    is_capturing() becoming false on its own: that happens when the worker
    stops, and a worker with audio to transcribe keeps capturing. A guard whose
    only exit is that state is therefore an UNBOUNDED deferral -- a request
    DEFERRED at every check and APPLIED at none, which is indistinguishable
    from a dropped one. Two things close it:

      * boundary(closed=True) -- the worker committed a line, so the live
        caption is at a sentence end rather than mid-word. This is the one
        signal that passes the capture guard while capture stays open. It is
        raised by on_worker_caption on a final:true caption.
      * WORKER_RELOAD_MAX_DEFER_MS -- the fallback for a stretch that closes no
          line at all. After this long the reload is FORCED even with no boundary,
          because a stale running worker is worse than one warm-up. The deferral
          re-arms with the REMAINDER when that is shorter than the re-check, so
          this ceiling is a DEADLINE and not a hint: it used to be observed one
          whole re-check late, which is how 25000 really meant 32046.

    The FLOOR applies AFTER both: it bounds the RATE of reloads, which is the
    owner's rule, and it is never a reason to wait for one. So the decision
    order is boundary -> ceiling -> floor, and every outcome is one log line
    carrying the numbers that produced it (waited_ms, max_defer_ms, left_ms)
    plus the two digests that say whether the running code is stale at all.

    state() answers the other half of the question -- not "may I restart" but
    "is the running worker the file on disk" -- as data, for the panel-state
    snapshot and for the log.
    """

    def __init__(self, log_fn, get_bridge, restart,
                 debounce_ms=WORKER_RELOAD_DEBOUNCE_MS,
                 min_interval_ms=WORKER_RELOAD_MIN_INTERVAL_MS,
                 max_defer_ms=WORKER_RELOAD_MAX_DEFER_MS,
                 defer_recheck_ms=WORKER_RELOAD_DEFER_RECHECK_MS):
        self.log = log_fn
        self.get_bridge = get_bridge
        self.restart = restart
        self.debounce_ms = debounce_ms
        self.min_interval_ms = min_interval_ms
        self.max_defer_ms = max_defer_ms
        self.defer_recheck_ms = defer_recheck_ms
        self.pending = None
        self.pending_since = 0.0
        # Set by a CLOSED-LINE boundary: the one signal that passes the capture
        # guard. Cleared with pending, so it can never outlive its request.
        self._boundary_hit = False
        # Throttle for the held-state line: a held reload is a STATE, not an
        # event, and one line per re-check would be thousands of lines.
        self._defer_logged_at = 0.0
        self._timer = None
        self._last_applied_at = 0.0
        self._stopped = False

    def request(self, files):
        """Queue a settled burst. True if it is now the pending one."""
        if self._stopped:
            return False
        self.pending = list(files)
        self.pending_since = time.monotonic()
        self._boundary_hit = False
        self._defer_logged_at = 0.0
        self._arm(self.debounce_ms)
        self.log(f'HOT_RELOAD_WORKER_QUEUED files={len(self.pending)} '
                 f'debounce_ms={self.debounce_ms} '
                 f'min_interval_ms={self.min_interval_ms} '
                 f'max_defer_ms={self.max_defer_ms}')
        return True

    def boundary(self, closed=False, why='status'):
        """A moment where a restart is least disruptive. closed = a closed line.

        A closed=True boundary passes the capture guard on purpose: the worker
        has just committed a line, so the caption the owner is reading is not
        cut mid-word. Every other caller only re-arms the wait, which is what
        keeps a held reload re-checking its own guard.
        """
        if self._stopped or self.pending is None:
            return
        bridge = self.get_bridge()
        if bridge is not None and bridge.is_capturing() and not closed:
            return
        if closed:
            self._boundary_hit = True
            waited_ms = int((time.monotonic() - self.pending_since) * 1000)
            self.log(f'HOT_RELOAD_WORKER_BOUNDARY reason={why} '
                     f'files={len(self.pending)} waited_ms={waited_ms}')
        self._arm(self.debounce_ms)

    def stop(self):
        self._stopped = True
        self.pending = None
        self._boundary_hit = False
        timer = self._timer
        if timer is not None:
            timer.cancel()
            self._timer = None

    def state(self):
        """Is the RUNNING code the code on disk? Two files, two answers.

        loaded for the worker is the digest taken when the child was spawned, so
        it answers "what is running"; disk answers "what is on disk now". They
        differ exactly when a restart is owed. The shell can only report itself:
        it cannot re-read its own code in place, so reloadable is False and the
        reader is told to restart rather than offered a reload that would not
        happen.
        """
        bridge = self.get_bridge()
        worker = {'path': None, 'disk': None, 'loaded': None, 'stale': False}
        if bridge is not None:
            path = getattr(bridge, 'worker_path', None)
            disk = file_sha256(path) if path else None
            loaded = getattr(bridge, 'loaded_sha256', None)
            worker = {
                'path': path,
                'disk': disk,
                'loaded': loaded,
                'stale': bool(disk and loaded and disk != loaded),
            }
        shell_disk = file_sha256(SHELL_PATH)
        pending_ms = None
        if self.pending is not None:
            pending_ms = int((time.monotonic() - self.pending_since) * 1000)
        return {
            'worker': worker,
            'shell': {
                'path': SHELL_PATH,
                'disk': shell_disk,
                'loaded': SHELL_SHA256_AT_IMPORT,
                'stale': bool(shell_disk and SHELL_SHA256_AT_IMPORT
                              and shell_disk != SHELL_SHA256_AT_IMPORT),
                'reloadable': False,
                'restart_hint': 'a shell change needs a shell restart',
            },
            'pending': list(self.pending) if self.pending is not None else None,
            'pending_ms': pending_ms,
            'max_defer_ms': self.max_defer_ms,
        }

    def _arm(self, delay_ms):
        if self._stopped:
            return
        timer = self._timer
        if timer is not None:
            timer.cancel()
        self._timer = threading.Timer(max(0.0, delay_ms / 1000.0), self._fire)
        self._timer.daemon = True
        self._timer.start()

    def _fire(self):
        """The one place the three rules are weighed, in order."""
        if self._stopped or self.pending is None:
            return
        files = self.pending
        bridge = self.get_bridge()
        if bridge is None:
            # No worker to restart: the request is satisfied by not existing.
            self.pending = None
            self._boundary_hit = False
            self.log(f'HOT_RELOAD_WORKER_SKIPPED files={len(files)} '
                     'reason=no-worker-running')
            return

        # ── THE ANSWER THE POLICY WAS ALREADY COMPUTING AND IGNORING ────────
        # O DONO, 2026-10-17, furioso: *"é tu que tá fazendo meu pc travar por 2
        # minutos inteiros? ... faz guard pra essa merda NUNCA MAIS ACONTECER"*, e
        # depois *"vai no disco e o watcher e entenda por que ele nao impediu essa
        # caga gigante e arruma ELE"*.
        #
        # ESTA É A PROVA, E ESTÁ NO LOG DELE, ÀS 22:35:25:
        #
        #   HOT_RELOAD_WORKER_IDLE_APPLIED files=1 reason=no-caption-in-25000ms
        #   code_is_stale=False
        #   sha256_disk=582b860b3ffe61c4 sha256_at_spawn=582b860b3ffe61c4
        #   cost=one-model-warm-up
        #
        # **OS DOIS DIGESTS SÃO IDÊNTICOS.** O worker já corria exactamente os
        # bytes que estavam no disco. A política PERGUNTOU se o código estava
        # velho — `code_is_stale` — recebeu `False` — e reiniciou na mesma, e
        # pagou um warm-up de ~2 GB na GPU do dono por bytes que já eram os
        # dele.
        #
        # Não foi o watcher. O watcher (`hot_reload.py`) só decide QUANDO um
        # estouro de edições assentou, e fez isso bem. Não foi o tecto, nem o
        # debounce, nem o floor. Foi esta política, que tem o campo
        # `code_is_stale` em todas as suas linhas de log — o que prova que alguém
        # o calculava — e o tratava como um facto a reportar, nunca como uma
        # condição a respeitar. Um digest que se imprime e não se obedece não é
        # um digest; é decoração.
        #
        # AGORA É UMA CONDIÇÃO. E é a primeira de todas, porque é a mais barata
        # e a mais verdadeira: não há nada a aplicar.
        disk_digest, loaded_digest = self._digests(bridge)
        if disk_digest and loaded_digest and disk_digest == loaded_digest:
            self.pending = None
            self._boundary_hit = False
            self.log(
                f'HOT_RELOAD_WORKER_SKIPPED files={len(files)} '
                f'reason=code-not-stale code_is_stale=False '
                f'sha256_disk={disk_digest} sha256_at_spawn={loaded_digest} '
                f'waited_ms={int((time.monotonic() - self.pending_since) * 1000)} '
                '-- o worker ja corre estes bytes; nao ha nada a aplicar, e '
                'aplicar nada nao custa 2 GB')
            return

        waited_ms = int((time.monotonic() - self.pending_since) * 1000)
        capturing = bool(bridge.is_capturing())
        # RULE 2 and its ceiling. boundary was raised by a closed line; forced
        # is the ceiling for a stretch that closes none. The digests are logged
        # on both paths because the useful question is never "did it restart"
        # but "was the running code stale when it did".
        boundary = self._boundary_hit
        # -- THE SECOND FACT (added 2026-10-12) ------------------------------
        # `is_capturing()` is ONE flag for TWO different workers: one that is
        # TRANSCRIBING, and one that merely has a stream OPEN. The guard exists
        # to avoid cutting the caption the owner is READING, so only the first
        # is under his feet -- and on this box the second is the measured
        # normal (a tap that is open and delivering nothing, because nothing is
        # routed into it). MEASURED in the owner's own log, this revision:
        # pid 11584, 4 940 captions, then a worker-file edit -- the guard
        # DEFERRED at every check and the ceiling FORCED the reload anyway,
        # `max_defer_ms=25000` but `waited_ms=32046`. The deferral bought
        # NOTHING and cost a 32 s stall of the capture pipeline plus a model
        # warm-up. A worker that has produced no caption within the ceiling has
        # NOTHING in flight, so there is no boundary worth waiting for: an idle
        # endpoint will never produce one. Hold only while a caption is RECENT.
        last_caption_at = getattr(bridge, 'last_caption_at', None)
        now_s = time.monotonic()
        if last_caption_at is None:
            # A bridge that cannot report the second fact is assumed to be in the
            # PROTECTED state: the guard's failure mode must always be "do NOT
            # restart". (The shell's own StandInBridge is exactly such a bridge,
            # and its guard arm asserts this hold without carrying a clock.)
            transcribing = True
        else:
            last_caption_at = float(last_caption_at)
            transcribing = bool(
                last_caption_at > 0.0
                and (now_s - last_caption_at) * 1000.0 < self.max_defer_ms)
        forced = capturing and not boundary and waited_ms >= self.max_defer_ms
        if capturing and not boundary and not forced and transcribing:
            now = time.monotonic()
            if now - self._defer_logged_at >= WORKER_RELOAD_DEFER_LOG_MS / 1000.0:
                self._defer_logged_at = now
                disk, loaded = self._digests(bridge)
                self.log(
                    f'HOT_RELOAD_WORKER_DEFERRED files={len(files)} '
                    f'reason=capturing waited_ms={waited_ms} '
                    f'max_defer_ms={self.max_defer_ms} '
                    f'code_is_stale={bool(disk and loaded and disk != loaded)} '
                    f'sha256_disk={disk} sha256_at_spawn={loaded} '
                    'applies_at=next-closed-line-or-ceiling')
            # THE CEILING IS A DEADLINE, NOT A HINT. This check only runs when
            # the timer fires, so arming a FULL re-check past the ceiling made
            # `max_defer_ms=25000` really mean 32 046 ms (measured). Arm the
            # REMAINDER whenever it is shorter than the re-check.
            self._arm(min(self.defer_recheck_ms,
                          max(0, self.max_defer_ms - waited_ms)))
            return
        if capturing and not boundary and not forced and not transcribing:
            # ── UM FICHEIRO MUDOU NAO REINICIA O WORKER. SO' UM RELATORIO. ────
            # O dono, 2026-10-17: *"é tu que tá fazendo meu pc travar por 2 minutos
            # inteiros? ... faz guard pra essa merda NUNCA MAIS ACONTECER"*. O preco, do
            # proprio log: `HOT_RELOAD_WORKER_RESTART after_idle_ms=35000` e
            # `HOT_RELOAD_WORKER_IDLE_APPLIED cost=one-model-warm-up`, DUAS vezes. A
            # `WorkerReloadPolicy` acreditava (na sua docstring) que "a stale running
            # worker is worse than one warm-up"; hoje nao existe caminho de "um ficheiro
            # mudou" para "reiniciar". O codigo fica desatualizado a espera de uma
            # PESSOA -- e quem paga a warm-up e ela. (Narrativa: docs/worker-lifecycle.md.)
            disk, loaded = self._digests(bridge)
            idle_ms = (int((now_s - last_caption_at) * 1000)
                       if last_caption_at > 0.0 else None)
            self.log(
                f'HOT_RELOAD_WORKER_REPORTED files={len(files)} '
                f'reason=code-changed-not-applied '
                f'waited_ms={waited_ms} idle_ms={idle_ms} '
                f'code_is_stale={bool(disk and loaded and disk != loaded)} '
                f'sha256_disk={disk} sha256_at_spawn={loaded} '
                'action=none -- o worker continua a correr; aplicar o codigo '
                'novo custa ~2 GB na GPU e e uma decisao de quem esta a usar a '
                'maquina, nao de um ficheiro que mudou')
            self.pending = None
            self._boundary_hit = False
            return
        if forced:
            # O TETO QUE FORÇAVA. Nao força mais nada.
            disk, loaded = self._digests(bridge)
            self.log(
                f'HOT_RELOAD_WORKER_REPORTED files={len(files)} '
                f'reason=ceiling-reached-nothing-forced '
                f'waited_ms={waited_ms} '
                f'code_is_stale={bool(disk and loaded and disk != loaded)} '
                f'sha256_disk={disk} sha256_at_spawn={loaded} '
                'action=none -- ha 25 s que este ceiling "forçava" o reinicio, '
                'ou seja, no momento em que a maquina esta mais quieta')
            self.pending = None
            self._boundary_hit = False
            return
        if boundary and capturing:
            self.log(f'HOT_RELOAD_WORKER_BOUNDARY_APPLIED files={len(files)} '
                     f'reason=closed-line waited_ms={waited_ms}')
        # A respawn that happened AFTER this request was queued already re-read
        # the file, so it satisfied the request: restarting again would pay a
        # second warm-up for the same bytes. STRICTLY after -- spawned_at is a
        # coarse monotonic stamp, and a respawn in the same tick as the queue
        # would otherwise be credited with re-reading a file it never saw.
        spawned_at = float(getattr(bridge, 'spawned_at', 0.0) or 0.0)
        if bridge.child is None or spawned_at > self.pending_since:
            disk, loaded = self._digests(bridge)
            self.pending = None
            self._boundary_hit = False
            self.log(
                f'HOT_RELOAD_WORKER_APPLIED_AT_BOUNDARY files={len(files)} '
                'reason=respawn-reread-file '
                f'pid={getattr(bridge.child, "pid", None)} '
                f'sha256_at_spawn={loaded}')
            return
        # RULE 3, the floor -- a RATE bound, applied after the guard and the
        # ceiling have both decided that this reload may happen at all.
        if self._last_applied_at <= 0.0:
            self._last_applied_at = spawned_at or time.monotonic()
        left_ms = self.min_interval_ms - int(
            (time.monotonic() - self._last_applied_at) * 1000)
        if left_ms > 0:
            disk, loaded = self._digests(bridge)
            self.log(
                f'HOT_RELOAD_WORKER_COOLDOWN files={len(files)} '
                f'left_ms={left_ms} min_interval_ms={self.min_interval_ms} '
                f'waited_ms={waited_ms} '
                f'code_is_stale={bool(disk and loaded and disk != loaded)} '
                f'sha256_disk={disk} sha256_at_spawn={loaded} '
                'applies_when=floor-elapses')
            self._arm(left_ms)
            return
        self.pending = None
        self._boundary_hit = False
        # O ULTIMO CAMINHO. Fechei-o tambem, e nao por excesso de zelo: era o
        # unico que restava, e era o que disparou as 22:30:11
        # (`after_idle_ms=35000`), quando uma legenda fechou e o floor ja tinha
        # passado. Uma legenda a fechar e' o MOMENTO EM QUE O DONO ESTA A LER. E'
        # precisamente ai que nao se pode ir buscar 2 GB ao GPU.
        disk, loaded = self._digests(bridge)
        self._last_applied_at = time.monotonic()
        self.log(f'HOT_RELOAD_WORKER_REPORTED files={len(files)} '
                 f'reason=boundary-reached-not-applied '
                 f'after_idle_ms={waited_ms} waited_ms={waited_ms} '
                 f'code_is_stale={bool(disk and loaded and disk != loaded)} '
                 f'sha256_disk={disk} sha256_at_spawn={loaded} '
                 'action=none -- uma legenda fechou, ou seja, o dono esta a ler; '
                 'ir buscar ~2 GB ao GPU aqui e' ' o que lhe aconteceu a ele')
        self._arm(self.min_interval_ms)

    # ── THE GUARD: A WORKER RESTART LOADS ~2 GB ONTO THE OWNER'S GPU ────────
    #
    # O DONO, 2026-10-17, furioso: *"é tu que tá fazendo meu pc travar por 2
    # minutos inteiros?"*. SIM. E não foi um teste: foi ESTA linha. Medido no
    # log, duas vezes, seis minutos apartadas:
    #
    #   22:30:11.891  HOT_RELOAD_WORKER_RESTART files=1 after_idle_ms=35000
    #   22:30:11.901  WORKER_AUTOSTART=started reason=hot-reload
    #   22:35:25.683  HOT_RELOAD_WORKER_IDLE_APPLIED ... cost=one-model-warm-up
    #   22:35:25.699  HOT_RELOAD_WORKER_RESTART files=["redux_live.py"]
    #
    # A causa foi uma gravação de ficheiro em `worker/` por um agente, com a app
    # do dono a correr com `--hot-reload`: o watcher viu a mudança e foi buscar um
    # NEMOTRON NOVO. O proprio log diz o preco: `cost=one-model-warm-up`. Duas
    # instâncias de 1 245 MB ficaram vivas e o PC ficou a 100% de CPU e GPU.
    #
    # **O GUARD É DE PRODUTO E NÃO É UMA PROMESSA.** Um aviso numa lista de
    # regras não impede ninguém: o mesmo estrago acontece a qualquer agente, a
    # qualquer IDE, e a qualquer `git checkout`. Por isso o reinicio do worker
    # deixou de ser automatico. Para acontecer, alguem tem de o PEDIR:
    #
    #     SOTTO_HOT_RELOAD_WORKER=1
    #
    # Sem isso, o watcher continua a detectar e a registar — o registo e o
    # diagnostico, e nao o disparo — e o worker que esta a correr fica como
    # esta. Uma mudanca no codigo passa a custar um F5, nao dois minutos de
    # maquina a qualquer.
    def _worker_restart_allowed(self, files):
        return worker_restart_allowed(files)

    @staticmethod
    def _digests(bridge):
        """The two digests a decision line carries, read in one place."""
        path = getattr(bridge, 'worker_path', None)
        disk = file_sha256(path) if path else None
        loaded = getattr(bridge, 'loaded_sha256', None)
        return disk, loaded


def worker_restart_allowed(files=None):
    """MAY A WORKER HOT-RELOAD ACTUALLY RESPAWN THE WORKER? DEFAULT: NO.

    O DONO, 2026-10-17, furioso: *"é tu que tá fazendo meu pc travar por 2
    minutos inteiros?"*. SIM. E não foi um teste: foi esta decisão. Medido no
    log, duas vezes, seis minutos apartadas:

      22:30:11.891  HOT_RELOAD_WORKER_RESTART files=1 after_idle_ms=35000
      22:30:11.901  WORKER_AUTOSTART=started reason=hot-reload
      22:35:25.683  HOT_RELOAD_WORKER_IDLE_APPLIED ... cost=one-model-warm-up
      22:35:25.699  HOT_RELOAD_WORKER_RESTART files=["redux_live.py"]

    A causa foi UMA GRAVAÇÃO de ficheiro em `worker/` por um agente, com a app do
    dono a correr com `--hot-reload`: o watcher viu a mudança e foi buscar um
    NEMOTRON NOVO. O próprio log diz o preço — `cost=one-model-warm-up`. Duas
    instâncias de 1 245 MB ficaram vivas, o PC foi a 100% de CPU e GPU, e matar o
    processo não resolveu porque o watcher o voltava a lançar.

    **O GUARD É DE PRODUTO E NÃO É UMA PROMESSA.** Uma regra numa lista não
    impede ninguém: o mesmo estrago acontece a qualquer agente, a qualquer IDE e
    a qualquer `git checkout`. Por isso o reinício deixou de ser automático. Para
    acontecer, alguém tem de o PEDIR:

        SOTTO_HOT_RELOAD_WORKER=1

    Sem isso o watcher continua a DETECTAR e a REGISTAR — o registo é o
    diagnóstico, não o disparo — e o worker que está a correr fica como está. Uma
    mudança no código passa a custar um reinício pedido, não dois minutos de
    máquina a qualquer.
    """
    want = os.environ.get('SOTTO_HOT_RELOAD_WORKER', '').strip().lower()
    if want in ('1', 'true', 'yes', 'on'):
        return True
    log('HOT_RELOAD_WORKER_REFUSED files=%s gate=SOTTO_HOT_RELOAD_WORKER '
        'cost=one-model-warm-up (~2 GB on the GPU on this host) '
        'set=SOTTO_HOT_RELOAD_WORKER=1 to allow it -- the running worker is left '
        'alone' % (json.dumps(files) if files is not None else '[]'))
    return False


class SpeakerSidecar:
    """The diarizer, as its OWN process, beside the worker.

    WHY A SEPARATE PROCESS AND NOT PART OF THE WORKER. The worker already loads
    1.2-2 GB of ASR; the diarizer is another 277 MB and ~1,4x realtime of CPU on
    this box. The worker's own `--speakers` (added 2026-10-18) reads
    `_main/diar-live.json` through `speaker_bridge.py` and REFUSES a payload that
    is absent, stale past 30 s, partial or unreadable. So the attribution can go
    quiet without taking transcription with it -- which is the fail-safe the
    whole chain is built on, and it only holds if the two lifetimes are
    separate.

    WHAT IT MAY NOT DO, and both are this repo's standing rules:

      * OPEN A CONSOLE WINDOW. `CREATE_NO_WINDOW`, always. The owner has been
        shown a stray console by this house more than once.
      * LIFT THE WORKER OFF THE FLOOR. `BELOW_NORMAL_PRIORITY_CLASS`, like the
        worker itself: the owner has said *"PARA DE FAZER MEU PC TRAVAR"*.

    IT TOUCHES NOTHING OF THE WORKER'S. No env key, no argv, no restart ladder.
    `_main/app-target-oracle.py` ARM e holds the worker's env contract and this
    class exists so that adding a feature does not have to break it.
    """

    def __init__(self, command=None, sidecar_path=None, log=log, extra_args=None):
        self.command = command or default_python()
        self.sidecar_path = sidecar_path or default_speaker_sidecar_path()
        self.log = log
        #: ARGV TAIL FOR THE SIDECAR. Empty list means byte-identical argv to
        #: what shipped, which is what the `--speakers` path must keep doing.
        #: Only the FASE A path sets it, to `['--watch-only']`.
        self.extra_args = list(extra_args or [])
        self.child = None
        self.reason = None

    @property
    def running(self):
        return self.child is not None and self.child.poll() is None

    def start(self, reason):
        if self.child is not None:
            return False
        if not os.path.isfile(self.sidecar_path):
            # LOUDLY, and without taking the worker down with it: captions with
            # no voices are the designed fail-safe, a dead app is not.
            self.log(f'SIDECAR_MISSING path={self.sidecar_path} '
                     f'reason={reason} by=SpeakerSidecar.start')
            return False
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) \
            if os.name == 'nt' else 0
        if os.name == 'nt':
            flags |= 0x00004000          # BELOW_NORMAL_PRIORITY_CLASS
        try:
            argv = [self.command, self.sidecar_path] + list(self.extra_args)
            self.child = subprocess.Popen(
                argv,
                cwd=os.path.dirname(self.sidecar_path) or os.getcwd(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=flags,
            )
        except Exception as exc:                                   # noqa: BLE001
            self.child = None
            self.log(f'SIDECAR_SPAWN_FAILED error={exc!r} reason={reason}')
            return False
        self.reason = reason
        self.log(f'SIDECAR_SPAWNED pid={self.child.pid} '
                 f'path={self.sidecar_path} reason={reason} '
                 f'argv={json.dumps([self.command, self.sidecar_path] + list(self.extra_args))}')
        # O pipe so deixa de encher se alguem o le. Sem isto o sidecar
        # trava a meio de uma call (medido: ~10 min) e a atribuicao
        # desliga sem alarme.
        self._start_drain(self.child)
        return True

    def _start_drain(self, child):
        """LER o que o sidecar diz, ou o pipe enche e o sidecar trava.

        MEDIDO 2026-10-19, e nao suspeitado. `start` faz `stdout=PIPE`
        sem ligar leitor nenhum; o `WorkerBridge` liga um por stream em 11006
        desde sempre. O grep na shell confirma: entre 10313 e 10440, `stdout`
        so aparecia no `PIPE` e no `STDOUT`.

        O CUSTO MEDIDO, com a configuracao exacta deste `Popen` e NINGUEM a
        ler: o filho escreve **3480 B** e trava. O sidecar escreve uma linha
        de 58 B por tick de 10 s (`DEFAULT_EVERY_S`), 5,8 B/s -- 3480/5,8 sao
        **~10 minutos de call**. Passados 10 min o sidecar bloqueava a
        escrever, deixava de publicar, e a ponte via o payload envelhecer e
        devolvia `None`: a atribuicao desligava SO, sem erro e sem alarme.
        Nenhum portao o apanhou, porque todos correm `watch_tick` no
        processo -- nunca atraves do pipe.

        VAO TUDO PARA O LOG, e nao se deita nada fora. O log nao e' consola:
        `run.cmd` lanca com `pythonw.exe --log`, e o `print()` do `log()` e'
        no-op sem stdout. 3600 linhas/hora sao ~200 KB num ficheiro. Um dreno
        que engolisse o diagnostico do sidecar seria a mesma mentira que uma
        excepcao engolida, so que mais lenta.

        O filho e' passado EXPLICITAMENTE, e nao lido de `self.child` dentro
        da thread: um sidecar morto pode ainda estar a drenar enquanto
        `self.child` ja aponta para o substituto, e uma linha com o pid
        ERRADO e' um numero sem dono.
        """
        # `getattr`, e nao `child.stdout`: um filho que NAO tem atributo
        # `stdout` levantava AttributeError AQUI, dentro de start() -- e
        # um dreno nunca pode ser a raza de o sidecar nao arrancar.
        # MEDIDO 2026-10-19: `sidecar-wiring-oracle` rebentou com
        # traceback exacto por isto (`AttributeError: '_FakePopen' object
        # has no attribute 'stdout'`), que e' o portao a fazer o que
        # existe para fazer. Este ramo tambem nao e' silencioso: diz no
        # log que nao ha nada para drenar, em vez de fingir que drenou.
        stream = getattr(child, 'stdout', None)
        if stream is None:
            self.log('SIDECAR_DRAIN_SKIPPED reason=filho-sem-stdout-legivel'
                     ' pid=%s' % getattr(child, 'pid', '?'))
            return False

        def drain():
            try:
                for line in iter(stream.readline, ''):
                    self.log('SIDECAR %s' % line.rstrip('\r\n'))
            except Exception as exc:                                   # noqa: BLE001
                self.log(f'SIDECAR_DRAIN_FAILED error={exc!r}')
            finally:
                try:
                    stream.close()
                except Exception:                                       # noqa: BLE001
                    pass

        threading.Thread(target=drain, name='speaker-sidecar-drain',
                         daemon=True).start()
        return True

    def stop(self, reason):
        """Terminate the child, naming it. NEVER a bare kill on a generic word:
        the AGENTS.md rule about kill filters is the same rule -- this names the
        PROCESS OBJECT, which is the safe form of the same thing."""
        child, self.child = self.child, None
        if child is None:
            return False
        try:
            child.terminate()
            try:
                child.wait(timeout=5)
            except Exception:                                       # noqa: BLE001
                child.kill()
        except Exception as exc:                                   # noqa: BLE001
            self.log(f'SIDECAR_STOP_FAILED error={exc!r} reason={reason}')
            return False
        self.log(f'SIDECAR_STOPPED pid={child.pid} reason={reason}')
        return True


def _evicted_note(payload):
    """O que a fila FIFO perdeu de audio do dono, em uma frase -- ou nada.

    Este e' o UNICO sitio onde o dono fica a saber. O payload traz o numero
    desde que a retencao passou a contar o que apaga; se o watcher o ignora,
    o audio continua a desaparecer em silencio -- agora com um campo
    correcto num ficheiro que ninguem le.

    Devolve a string VAZIA e nao '0 apagados': uma janela sem eviccao e' o
    caso normal e nao merece uma linha mais longa do que ja e'.
    """
    try:
        lost = int(payload.get("clips_evicted") or 0)
    except (TypeError, ValueError, AttributeError):
        return ""
    if lost <= 0:
        return ""
    kept = int(payload.get("clips_saved") or 0)
    return (" AUDIO_PERDIDO=%d (a fila encheu: %d apagado(s),"
            " %d guardado(s) nesta janela)"
            % (lost, lost, kept))


class MultiVoiceWatch:
    """FASE A: o que o sidecar `--watch-only` viu, lido aqui e registado.

    PORQUE ISTO EXISTE
    ------------------
    Sem este leitor, `--speakers-cheap` escrevia `_main/diar-watch.json` e nao
    acontecia mais nada: um sinal sem consumidor nao decide nada, e o dono pediu
    exactamente uma DETECCAO que lhe permitisse decidir mais tarde. Este e' o
    consumidor, e ele e' deliberadamente pequeno: **regista**, nao decide.

    O QUE ELE NAO FAZ
    ------------------
    Nao escreve no painel. Nao acrescenta um numero a lado da legenda -- o dono
    tirou um numero visivel duas vezes, e `_main/panel-voice-dot-oracle.js` e' o
    portao que garante que o painel nao ganha texto. Nao lanca a separacao de
    vozes: QUANDO isso e' seguro para o PC do dono e' uma politica dele, e
    adivinha-la aqui seria a forma mais rapida de voltar a fazer-lhe o PC heavier
    sem ele pedir.

    O QUE ELE LE
    -------------
    `speaker_bridge.watch_payload_if_fresh`, que exige a chave `multivoice` e
    RECUSA um payload que traga `segments`. Um ficheiro trocado por engano, ou um
    payload de fala no sitio errado, da `None` -- e `None` significa "nada a
    dizer", nunca "zero vozes".
    """

    #: HOW OFTEN. The sidecar publishes a window every 10 s, so a 4 s poll sees
    #: every window and costs a stat() four times a second.
    POLL_S = 4.0

    def __init__(self, path=None, poll_s=None, log=log):
        self.path = path or speaker_watch_payload_path()
        self.poll_s = float(poll_s or self.POLL_S)
        self.log = log
        self.thread = None
        self._stop = threading.Event()
        self._last_key = None

    def poll_once(self):
        """One read. Returns the short form, or None when there is nothing new.

        Returning only on CHANGE is what keeps a 4-hour call from producing
        3600 identical log lines.
        """
        try:
            bridge = _speaker_bridge()
            payload = bridge.watch_payload_if_fresh(self.path)
        except Exception as exc:                                   # noqa: BLE001
            self.log(f'WATCH_READ_FAILED error={exc!r}')
            return None
        if payload is None:
            return None
        state = bridge.multivoice(payload)
        key = (state.get("written_at"), state.get("n_spans"),
               state.get("multivoice_s"))
        if key == self._last_key:
            return None
        first = self._last_key is None
        self._last_key = key
        if not state.get("multivoice"):
            # MEASURED BUG, found by `_main/speaker-watch-oracle.py`: this used to
            # log on ANY change, so a quiet window that followed a busy one was
            # recorded as `WATCH_MULTIVOICE spans=0` -- a loud line for a window
            # in which nothing overlapped. A log that cries wolf on quiet is
            # worse than no log, because the reader stops believing it.
            if first:
                # The first read after start-up says "the detector is alive and
                # has not seen two voices yet". That is worth one line: it
                # separates "running and quiet" from "never ran".
                self.log('WATCH_ALIVE multivoice_s=0.0')
            return state
        self.log('WATCH_MULTIVOICE spans=%s seconds=%.2f%s'
                 % (state.get("n_spans"), state.get("multivoice_s", 0.0),
                    _evicted_note(payload)))
        return state

    def start(self, reason):
        if self.thread is not None:
            return False
        self._stop.clear()

        def loop():
            while not self._stop.is_set():
                try:
                    self.poll_once()
                except Exception as exc:                           # noqa: BLE001
                    self.log(f'WATCH_LOOP_FAILED error={exc!r}')
                self._stop.wait(self.poll_s)

        self.thread = threading.Thread(target=loop, name='multivoice-watch',
                                       daemon=True)
        self.thread.start()
        self.log(f'WATCH_STARTED path={self.path} every={self.poll_s:.0f}s '
                 f'reason={reason}')
        return True

    def stop(self, reason):
        thread, self.thread = self.thread, None
        self._stop.set()
        if thread is not None:
            thread.join(timeout=2.0)
        self.log(f'WATCH_STOPPED reason={reason}')
        return True


class WorkerBridge:
    """Spawns worker/sotto_worker.py and turns its JSONL into panel events.

    The contract is the worker's, not this shell's: one JSON object per line on
    stdout, `{"type":"caption","text":...}` and `{"type":"status","state":...}`
    (sotto_worker.py:6-7). Everything else here is the same policy the Electron
    bridge runs: the device travels ONLY when the owner named one, a missing
    worker names the WORKER rather than the shell's ENOENT, an empty status is
    refused, and a status that asserts audio is absent is falsified — because
    the system tap on this host measures CAPTURED, so that sentence would be a
    lie with a fix attached to it.
    """

    def __init__(self, command, worker_path, device=None,
                 capture_mode=DEFAULT_CAPTURE_MODE, log=log,
                 on_caption=None, on_status=None, on_stats=None,
                 on_meter=None,
                 silence_ms=WORKER_SILENCE_MS,
                 load_silence_ms=WORKER_LOAD_SILENCE_MS,
                 backoff_base=1000, backoff_max=30000,
                 no_audio_backoff_base=15000,
                 no_audio_backoff_max=300000,
   no_audio_restart_cap=3,
        #: O TECTO. O dono, verbatim (AGENTS.md): *"o worker morre e recarrega ~1 GB de
        #: modelo 88 vezes em 17 minutos (exit 3 a cada 2,5 min). arruma"*. NUNCA FOI
        #: ARRUMADO: medido 2026-10-15 no log dele, `deaths=6 spawns=7` e cada arranque
        #: custa `BRIDGE_LOAD_MS ms=36547` -- 36 SEGUNDOS a ler ~1 GB de disco. A escada
        #: de espera ja existia (15 s a 300 s), mas por muito que espere ela NUNCA PARA:
        #: ao fim de cada espera volta a carregar o modelo inteiro, para sempre, porque
        #: um veredicto `silent-device` diz que a ROTAGEM esta errada e recarregar um
        #: modelo nao arranja rotagem nenhuma. **Esse churn e o stutter do dono.**
        #:
        #: Depois de tantas mortes seguidas por silencio, o shell PARA e diz o que fazer.
        #: O Alt+C volta a tentar (ver `show_panel`), portanto nao ha beco sem saida.
                 target_pid=None, extra_args=None, on_loading_text=None):
        self.command = command or default_python()
        self.worker_path = worker_path
        #: ARGV TAIL. The per-voice attribution is `--speakers`, and it reaches
        #: the worker in ARGV and NOT in the environment -- deliberately:
        #: `_main/app-target-oracle.py` ARM e holds the env contract ("os.environ
        #: + SOTTO_CAPTURE_MODE, nothing else"), and adding a key there turns that
        #: arm RED, which is the gate being right. The worker's `--speakers` is a
        #: real flag it already declares; the shell's job is to pass it.
        #:
        #: Empty tuple by default, so every bridge built without this parameter
        #: spawns the EXACT argv it always did: `[command, worker_path]`.
        self.extra_args = tuple(extra_args or ())
        self.device = device if isinstance(device, str) and device.strip() else None
        self.capture_mode = capture_mode
        #: THE PER-APP TAP, opt-in: the pid of the ONE app whose process tree the
        #: worker must tap, or None for the endpoint mix (the behaviour every run
        #: had before this parameter existed). It travels to the child in the
        #: ENVIRONMENT -- `_child_env` is the whole contract, and it is where
        #: the "absent means byte-identical env" promise is kept. The worker owns
        #: the refusal for a pid that is not alive (sotto_worker.py,
        #: `_plp_pid_state`); this shell only resolves NAMES (see
        #: `resolve_app_target`).
        self.target_pid = target_pid
        self.log = log
        self.on_caption = on_caption or (lambda text, meta: None)
        self.on_status = on_status or (lambda text, kind, info: None)
        #: The stats PUSH. Defaulted to a no-op like the other two, so a bridge
        #: built without it (a probe, the electron-era arm) is byte-identical.
        self.on_stats = on_stats or (lambda parsed: None)
        #: THE WAVE. Defaulted to a no-op like the other three, so a bridge built
        #: without it (a probe, the electron-era arm) behaves as before.
        self.on_meter = on_meter or (lambda sample: None)
        #: A ESPERA. A ponte nao pinta: quem pinta e' a shell.
        self.on_loading_text = on_loading_text or (lambda text: None)
        self.silence_ms = silence_ms
        #: THE LOAD WINDOW, and the answer to "may I kill a silent child yet?".
        #: While `loaded` is False the watchdog owes the child this much quiet,
        #: measured from the spawn (see `WORKER_LOAD_SILENCE_MS`).
        self.load_silence_ms = load_silence_ms
        self.backoff_base = backoff_base
        self.backoff_max = backoff_max
        # A NO-AUDIO DEATH IS NOT A FAILURE AND MUST NOT BE TIME-PRICED LIKE ONE.
        # MEASURED 2026-10-14 on the owner log: 88 deaths and 88 model reloads in 17
        # minutes -- one every ~12 s -- each reload pulling ~1 GB back into memory,
        # while the worker was doing exactly what it was built to do: it opened a
        # device and heard digital silence, which this repo own routing law says is
        # the CORRECT answer of a working app on an idle desktop. This program is
        # going to be used by thousands of people and the default state of nearly
        # all of them is NOTHING ROUTED YET. A hot loop that reloads a gigabyte for
        # every one of them is a broken program, not a working one.
        #
        # So a no-audio death gets its own much slower ladder -- 15 s growing to
        # 5 min -- and its own counter that a REAL failure does not touch. A user who
        # routes audio later is transcribed the moment the slow ladder comes round,
        # and until then the machine is quiet instead of thrashing.
        self.no_audio_backoff_base = no_audio_backoff_base
        self.no_audio_backoff_max = no_audio_backoff_max
        self.no_audio_restart_cap = no_audio_restart_cap
        self.no_audio_restarts = 0

        self.child = None
        self.state = 'idle'
        #: True once THIS child has published `model-loaded`. THE GATE the silence
        #: watchdog reads: before it, a silent worker is a LOADING worker, and
        #: killing it is the S7 defect (see `WORKER_LOAD_SILENCE_MS`). Per child,
        #: so a restart's warm-up is judged on its own evidence.
        self.loaded = False
        #: The shell's own measurement of the load - spawn to `model-loaded`, in
        #: ms - logged as `BRIDGE_LOAD_MS` so a boot's load phase is readable
        #: from the log alone. Zero until the child publishes the state.
        self.load_ms = 0.0
        self.restarts = 0
        self.spawns = 0
        self.captions = 0
        # WHEN the last caption arrived, not just how many. The reload guard
        # holds a worker that is TRANSCRIBING; without a clock it could only ask
        # whether a stream was open, which is a different question (see
        # WorkerReloadPolicy._fire).
        self.last_caption_at = 0.0
        self.statuses = 0
        self.malformed = 0
        self.stopped = False
        self.last_exit = None
        #: True from the `capture-started` status until the child stops/exits.
        #: This is the guard's input: a worker with an OPEN capture stream must
        #: not be restarted by a file change (owner: "o modelo loading ta toda
        #: hora saindo de load").
        self.capturing = False
        #: Monotonic time of the last spawn, so a queued reload can tell whether
        #: a natural respawn already re-read the file (WorkerReloadPolicy).
        # The digest of the file this child was started from: the answer to
        # "is the running worker the code on disk" cannot be re-derived later.
        self.loaded_sha256 = None
        self.spawned_at = 0.0
        # The last failure this worker reported, and the death the panel is
        # currently obliged to keep showing. `pending_error` is set by a
        # non-zero exit and cleared only by a CAPTION: a restart that has
        # produced no caption has proved nothing, so it must not clear it.
        self.last_error = None
        #: The last NO-AUDIO verdict this worker reported (the calm twin of
        #: `last_error`). The two are mutually exclusive -- each is cleared
        #: when the other is written -- so "the most recent verdict" is a
        #: one-field answer and `_wait` cannot read a stale red over a fresh
        #: no-audio (or the reverse).
        self.last_no_audio = None
        self.pending_error = None
        #: True once THIS child has published its own verdict that the audio it
        #: opened carries nothing to transcribe (see WORKER_NO_AUDIO_STATES /
        #: WORKER_NO_AUDIO_VERDICTS). Reset on every spawn, because the verdict
        #: is a fact about the CHILD that measured it, not about the shell. Read
        #: by `_on_silence`: a child that has said this is quiet because the
        #: machine is quiet, so the watchdog re-arms instead of killing it.
        self.no_audio = False
        #: What the child said, verbatim, for the log and for the UI state.
        self.no_audio_evidence = None
        #: When that evidence was MEASURED (monotonic), so a replay can be aged
        #: instead of being presented as a current measurement. Zero = never set.
        # THE ASSIGNMENT WAS MISSING (the comment above outlived the line it
        # described). Measured 2026-10-11: `panel_state_snapshot` died with
        # `AttributeError: 'WorkerBridge' object has no attribute
        # 'no_audio_evidence_at'` -- `PANEL_STATE_SNAPSHOT_FAILED reason=periodic`
        # in every run where no no-audio evidence was ever published, i.e. the
        # HEALTHY case stopped writing `_main/panel-state.json`. The readers at
        # `panel_state()` and `_on_silence` test it for TRUTHINESS, so the value
        # the comment names is 0.0.
        self.no_audio_evidence_at = 0.0
        self.deaths = 0
        #: TRUE entre o `terminate()` do proprio shell e o `_wait` que o ve morrer.
        #: Sem isto um HOMICIDIO era publicado como morte: medido no log do dono, 9 das
        #: 10 silencias anomalas sao seguidas do `rc=1` que o `TerminateProcess` devolve,
        #: e o `BRIDGE_DEATH kind=error` pintava o painel de vermelho num worker saudavel.
        self.killed = False
        self._rss_at = 0.0
        self.stderr_tail = []
        #: The last `WORKER_STATS` line the worker printed on stderr, parsed.
        #: That stream is the ONLY place `peak`/`nonzero_blocks` are published,
        #: and this bridge already reads it (for `stderr_tail`) — the line was
        #: dropped after three, which is why those numbers were unreachable from
        #: outside the process. Kept whole for the panel-state text dump.
        self.last_worker_stats = None
        #: THE WAVE. `{"type":"meter","peak":<window peak>,"blocks":<blocks in
        #: the window>}`, published by the worker once per meter window (10 Hz by
        #: default). `peak` here is the peak OF THAT WINDOW — the stats line above
        #: carries the RUNNING MAXIMUM — so this is the value the panel's wave
        #: must be drawn from, and `stats()` prefers it while it is fresh.
        self.last_meter = None
        self.meters = 0
        self._meter_logged = 0
        self._meter_logged_at = 0.0
        #: The last status that NAMED an endpoint (`device`, `capture-started`,
        #: `device-rotated`, `device-exhausted`, `silent-device`). The panel shows
        #: the device inside a human sentence; the raw fields are kept here so the
        #: dump can say WHICH endpoint is tapped without parsing prose.
        self.last_device_status = None
        #: The highest `blocks=` the CURRENT child has published in a
        #: `WORKER_STATS` line. The watchdog is armed against NO PROGRESS, and
        #: this counter advancing IS progress (see `_note_progress`). Reset per
        #: child: the counter starts again at 0, so a value left over from the
        #: dead process would suppress every re-arm of the new one.
        self._progress_blocks = None
        self._silence_timer = None
        self._restart_timer = None
        self._lock = threading.Lock()
        # ROW #14 (2026-10-11): while this lock is held, a status emitted from here
        # reaches the SHELL's callback, and that callback talks to the page (`exec_js`,
        # up to four round-trips of 10 s each). Holding the lock across that meant
        # Alt+C's start/stop waited on a page that may be busy -- the owner's freeze.
        # Emissions made INSIDE the lock are queued here and flushed the moment it is
        # released: their ORDER is kept (the lock is what serialised them) and the
        # LOCK is dropped instead of the message.
        self._lock_depth = 0
        self._pending_status = []

    class _LockScope:
        """`with self._locked():` -- the lock, with its status emissions deferred."""

        def __init__(self, bridge):
            self._bridge = bridge

        def __enter__(self):
            self._bridge._lock.acquire()
            self._bridge._lock_depth += 1
            return self

        def __exit__(self, *_exc):
            bridge = self._bridge
            bridge._lock_depth -= 1
            flush = bridge._lock_depth == 0
            bridge._lock.release()
            if flush:
                pending, bridge._pending_status = bridge._pending_status, []
                for args in pending:
                    bridge._status(*args)
            return False

    def _locked(self):
        """The plain `self._lock` releases FIRST and emits after (row #14)."""
        return WorkerBridge._LockScope(self)

    # -- state -------------------------------------------------------------
    def is_capturing(self):
        """True while an audio stream is open on the worker.

        Read by `WorkerReloadPolicy` WITHOUT the lock: it is a single boolean
        read, and taking the lock here would deadlock `_spawn` (which calls
        `_arm_silence` with the lock held and must stay lock-free on its way
        out — see the note there).
        """
        return bool(self.capturing) and self.child is not None

    def snapshot(self):
        """The bridge's OWN state as plain data, for the panel-state text dump.

        Read-only and cheap: it copies fields this object already holds and does
        NOT measure anything (no `peak` is computed here, no process is asked).
        `peak`/`nonzero_blocks` come from the worker's own `WORKER_STATS` line,
        which `_pump` already read off stderr.
        """
        child = self.child
        current = child.pid if child is not None else None
        stats = self.last_worker_stats
        device = self.last_device_status
        return {
            'state': self.state,
            'capturing': bool(self.capturing),
            'childPid': current,
            'spawns': self.spawns,
            'restarts': self.restarts,
            'deaths': self.deaths,
            'captions': self.captions,
            'statuses': self.statuses,
            'malformed': self.malformed,
            'lastExit': self.last_exit,
            'noAudio': bool(self.no_audio),
            'noAudioEvidence': self.no_audio_evidence,
            'noAudioEvidenceAgeS': (
                round(time.monotonic() - self.no_audio_evidence_at, 1)
                if self.no_audio_evidence_at else None),
            'pendingError': self.pending_error,
            'lastError': self.last_error,
            # `*Current` is the honest half of keeping a dead child's number
            # around: False means the line was published by a child this bridge
            # has already replaced, and it says so instead of looking live.
            'device': device,
            'deviceCurrent': bool(device) and device.get('childPid') == current,
            'workerStats': stats,
            'workerStatsCurrent': bool(stats) and stats.get('childPid') == current,
            'stderrTail': list(self.stderr_tail[-3:]),
        }

    # -- status ------------------------------------------------------------
    def _status(self, text, kind='busy', info=None):
        value = str(text if text is not None else '').strip()
        if value == '':
            value = 'Worker status unavailable'
            kind = 'error'
        elif FALSE_AUDIO_ABSENT_RE.search(value) and self.captions == 0:
            # ONLY while NO caption has ever arrived (row #11, 2026-10-11). After one,
            # this text is a REAL regression: rewriting it into "capture not
            # started" showed the owner the shell's own guess and hid the worker's
            # error, on the one channel that displays the worker's cause.
            self.log(f'BRIDGE_STATUS_FALSIFIED text={json.dumps(value)}')
            value = CAPTURE_NOT_STARTED
            kind = 'busy'
        if self._lock_depth:
            # INSIDE THE LOCK (row #14): queue it; `_LockScope.__exit__` flushes it
            # after the release, so the shell's callback never runs with the lock held.
            self._pending_status.append((value, kind, info or {}))
            return value
        self.on_status(value, kind, info or {})
        return value

    def _bridge_status(self, text, kind, placeholder, state):
        self.state = state
        self._status(text, kind, placeholder)

    # -- lifecycle ---------------------------------------------------------
    def start(self, reason='start'):
        with self._locked():
            if self.stopped or self.child:
                return False
            self.log(
                f'BRIDGE_START reason={reason} command={self.command} '
                f'worker={self.worker_path} '
                f'device={"auto" if self.device is None else json.dumps(self.device)} '
                f'capture={self.capture_mode}')
            self._bridge_status(
                f'Starting worker... ({os.path.basename(self.worker_path)})',
                'busy',
                {'title': 'Starting the worker',
                 'body': 'The transcription worker is being launched. No audio '
                         'is being read yet.'},
                'starting')
            # The spawn's OWN result (row #13): `return True` reported the REQUEST.
            return self._spawn() is not None

    def _child_env(self):
        """The child's WHOLE environment contract, in one place.

        Factored out of `_spawn` so it is assertable WITHOUT spawning
        anything (`_main/app-target-oracle.py` builds bridges in-process and
        compares the dicts -- the same reason `_worker_autostart_reason` was
        factored out of `_on_loaded`). The device and the capture mode already
        travelled this way; the per-app target joins them HERE, and ONLY when it
        was asked for: a bridge built without `target_pid` produces the
        byte-identical environment it produced before the parameter existed.
        """
        env = dict(os.environ)
        # THE FREEZE CURES LIVE IN THE WORKER, NOT HERE (2026-10-17). Its own
        # `CUDA_MODULE_LOADING=LAZY` / `OMP_NUM_THREADS=4` defaults are set at
        # module scope before onnxruntime is imported, so they apply to every
        # way the worker can be launched. `_main/app-target-oracle.py` pins this
        # dict to `os.environ + SOTTO_CAPTURE_MODE` (+ the target pid), and that
        # contract is worth keeping.
        env['PYTHONUNBUFFERED'] = '1'
        env['SOTTO_CAPTURE_MODE'] = self.capture_mode
        if self.device is not None:
            env['SOTTO_AUDIO_DEVICE'] = self.device
        #: OPT-IN: `SOTTO_TARGET_PID` appears ONLY when a target was resolved.
        #: The worker reads it as the per-app tap (sotto_worker.py,
        #: `--target-pid` / `SOTTO_TARGET_PID`); absent, its candidate ladder
        #: is the endpoint mix, unchanged.
        if self.target_pid is not None:
            env['SOTTO_TARGET_PID'] = str(self.target_pid)
        return env

    def _spawn(self):
        # The missing-file check is not an optimisation: spawning a nonexistent
        # path fails asynchronously and reports a message that names the shell,
        # not the worker. This names the worker, which is the whole point.
        if not os.path.exists(self.worker_path):
            self.log(f'BRIDGE_WORKER_MISSING path={self.worker_path}')
            self._bridge_status(
                f'Worker not found - {self.worker_path} does not exist', 'error',
                {'title': 'Worker not found',
                 'body': 'The shell found no worker entrypoint at the path it '
                         'was given.'},
                'missing')
            self._schedule_restart('missing')
            return

        self.state = 'spawning'
        self.spawns += 1
        # UM `model-loading` SO' VALE ANTES DO PRIMEIRO `model-loaded` DESTE
        # FILHO (2026-11-03, MEDIDO). O worker volta a publicar
        # `model-loading` depois de o modelo ja' estar carregado (recarga,
        # rotacao de dispositivo) e cada um desses republicava o placeholder
        # ATRAVES do `push_caption_to_window` -- ou seja, a janela da legenda
        # trocava a legenda por `carregando modelo…`. Medido ao vivo
        # (pid 8168): `CAPTION_OVERLAY_PUSH count=50 text="carregando modelo…"`
        # 5 min DEPOIS de `BRIDGE_LOAD_MS`, com `CAPTION_APPLIED count=1..49`
        # entre os dois. O portao do primeiro `model-loaded` do filho fecha-o.
        # `stderr_tail` explains THIS death, so it is reset per child. The last
        # stats line and the last device are NOT cleared: each is stamped with
        # the pid that published it (`childPid`), so the snapshot can say whether
        # the number belongs to the live child or to the one that just died,
        # instead of showing a null that hides both.
        self.stderr_tail = []
        # A freshly spawned worker has no open stream yet; the guard re-opens
        # when its `capture-started` line arrives. `spawned_at` lets a queued
        # reload tell whether this respawn already re-read the file.
        self.capturing = False
        # A new child has declared nothing yet: the previous child's `silent-
        # device` is evidence about the OLD process, and letting it survive the
        # respawn would blind the watchdog for the new one.
        self.no_audio = False
        # The two verdict slots go with it. They are what `_wait` reads to
        # choose the colour of THIS child's death, so a stale one would paint a
        # fresh unexplained crash in the colour of the child before it -- and the
        # dangerous direction is the calm slot: a crash with no verdict left MUST
        # be red. `pending_error` (the hold) is NOT reset here: it is cleared
        # only by a caption, by design.
        self.last_error = None
        self.last_no_audio = None
        self.no_audio_evidence = None
        #: When that evidence was MEASURED (monotonic), so a replay can be aged
        #: instead of being presented as a current measurement. Zero = never set.
        # The new child has not loaded anything yet: the load window is armed from
        # the spawn, and a `loaded`/`load_ms` left over from the dead child would
        # tell the watchdog the load it is watching has already happened.
        self.loaded = False
        self.load_ms = 0.0
        # Reset WITH the evidence it ages: an age measured from the dead child
        # would age the new child's silence from the old process's clock.
        self.no_audio_evidence_at = 0.0
        # The new child's `blocks=` counter starts again at 0 (see
        # `_progress_blocks`): carrying the dead process's last value over would
        # make every heartbeat look like a repeat and blind the watchdog.
        self._progress_blocks = None
        self.spawned_at = time.monotonic()
        #: Quando este filho FALOU pela ultima vez (2026-11-03). A janela de
        #: carga passou a medir SILENCIO, nao idade: um worker que ainda esta'
        #: a carregar (35 s, 147 s sob contencao) publica linhas no stdout,
        #: e matar quem progride custa a carga inteira outra vez.
        self.last_progress_at = self.spawned_at

        # The WHOLE env contract lives in `_child_env`, so it can be asserted
        # without spawning anything (see its docstring). Nothing else in this
        # method was touched when the per-app target was added.
        env = self._child_env()

        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) \
            if os.name == 'nt' else 0
        if os.name == 'nt':
            # BELOW_NORMAL_PRIORITY_CLASS. The worker is a background
            # transcriber; it must never outrank the desktop while it reads a
            # gigabyte of weights or runs a burst of inference. MEASURED
            # 2026-10-17: the cold start is ~4.6 s and the process peaks at
            # ~2 GB RSS, which is exactly the window the owner reported as a
            # freeze. Below-normal keeps the shell, the browser and Explorer
            # responsive through it.
            creationflags |= 0x00004000

        try:
            # `-u` NAO E' ESTILO: E' A LATENCIA DA LEGENDA (2026-11-03,
            # MEDIDO). O worker escreve JSONL no stdout e o stdout de um pipe
            # e' BUFFERIZADO POR BLOCOS (8 KB): sem `-u` a linha de uma
            # legenda fica presa no buffer do proprio filho ate' o buffer
            # encher. Medido nesta sessao: o worker publicou
            # `model-loaded load_s=11.66` e o shell so' a leu em
            # `BRIDGE_LOAD_MS ms=120859` -- 109 s de linha parada num pipe.
            # O `PYTHONUNBUFFERED=1` do `_child_env` cobre o mesmo buraco para
            # qualquer lancamento que nao passe por este argv.
            argv = [self.command, '-u', self.worker_path] \
                + list(self.extra_args)
            self.child = subprocess.Popen(
                argv,
                cwd=os.path.dirname(self.worker_path) or os.getcwd(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                creationflags=creationflags,
            )
        except Exception as exc:
            self.child = None
            self.log(f'BRIDGE_SPAWN_FAILED error={exc!r}')
            self._bridge_status(
                f'Worker could not start - {exc}', 'error',
                {'title': 'Worker could not start',
                 'body': 'The shell tried to launch the worker and the '
                         'interpreter refused.'},
                'error')
            self._schedule_restart('spawn-failed')
            return

        self.log(f'BRIDGE_SPAWNED pid={self.child.pid} '
                 # O ARGV QUE CORREU, nao o que se pensa que correu: esta
                 # linha reconstruia a lista sem o `-u` e o log passou a
                 # descrever um processo diferente do que existe.
                 f'argv={json.dumps(argv)} '
                 f'SOTTO_CAPTURE_MODE={self.capture_mode} '
                 'SOTTO_AUDIO_DEVICE=' +
                 (self.device if self.device is not None else '(unset)'))

        # Recorded AFTER a successful spawn: state() compares this against the
        # file on disk, so it must describe the bytes the child actually loaded.
        self.loaded_sha256 = file_sha256(self.worker_path)

        for stream, name in ((self.child.stdout, 'stdout'),
                             (self.child.stderr, 'stderr')):
            # The child is passed EXPLICITLY rather than read from `self.child`
            # inside the thread: a dead worker's pipe can still be draining while
            # `self.child` already points at its replacement, and a WORKER_STATS
            # line stamped with the WRONG pid is an unattributable number.
            threading.Thread(target=self._pump, args=(stream, name, self.child),
                             name=f'sotto-worker-{name}', daemon=True).start()
        threading.Thread(target=self._wait, name='sotto-worker-wait',
                         daemon=True).start()

        self._arm_silence()
        # REPORTED (row #13, 2026-10-11): `_spawn` used to fall out with None on
        # EVERY path, so no caller could tell a spawned worker from a refused one.
        # The two failure paths above still return None; `start()` reads this.
        return self.child

    def stop(self, reason='stop'):
        with self._locked():
            if self.stopped:
                return False
            self.stopped = True
            self._cancel_timers()
            child, self.child = self.child, None
            self.capturing = False
        if child is not None:
            self.log(f'BRIDGE_STOP reason={reason} pid={child.pid}')
            # NEVER BLOCK THE CALLER ON A DYING WORKER. `terminate()` on Windows
            # is `TerminateProcess`, but the old `wait(timeout=5)` then made the
            # shell's UI/tray thread sit for up to five seconds while a 2 GB
            # process was torn down -- the "fechar o sotto trava o PC" the owner
            # reported on 2026-10-17. Kill it, reap in a daemon thread, and let
            # the caller return immediately.
            try:
                child.kill()
            except Exception as exc:  # noqa: BLE001
                try:
                    child.terminate()
                except Exception as exc2:  # noqa: BLE001
                    # A WORKER THAT SURVIVES THE KILL IS A CAPTURE THAT
                    # CONTINUES. `stop()` answers True ("parou") while a 2 GB
                    # process may still be holding the device and writing
                    # captions. SAY SO: a falha silenciosa aqui e' o "fechei o
                    # Sotto e o worker continuou a correr" que ninguem consegue
                    # diagnosticar de fora.
                    self.log(f'BRIDGE_KILL_FAILED pid={child.pid} '
                             f'kill={exc!r} terminate={exc2!r}')
            try:
                reaper = threading.Thread(
                    target=lambda c=child: _reap_child(c),
                    name='sotto-worker-reap', daemon=True)
                reaper.start()
            except Exception as exc:  # noqa: BLE001
                # O processo ja morreu; ninguem o vai recolher. E' um handle
                # vazado, e um vazamento que pertence ao log.
                self.log(f'BRIDGE_REAPER_FAILED pid={child.pid} error={exc!r}')
            return True
        # SAYS SO (row #42, 2026-10-11): returning False silently left whatever the
        # panel was showing standing -- symmetric with `start()`, which always tells
        # the panel what it asked for.
        self.log(f'BRIDGE_STOP reason={reason} pid=none')
        self._bridge_status(
            'Nothing to stop - no worker is running',
            'busy',
            {'title': 'No worker running',
             'body': 'The stop request arrived when no transcription worker was '
                     'running.'},
            'idle')
        return False

    # -- stdout ------------------------------------------------------------
    def _pump(self, stream, name, child=None):
        # A reader thread that dies takes the worker's WHOLE output channel with
        # it, and `except Exception: pass` made that indistinguishable from a
        # worker that said nothing: the run then logs `statuses=0` and the panel
        # shows only a bare exit code. Measured on this box: a live run logged
        # `statuses=0` on every one of 8 worker cycles while stderr arrived
        # normally. Two lines of logging is the difference between that being
        # diagnosable and being invisible.
        if stream is None:
            self.log(f'BRIDGE_PUMP_NULL stream={name} - the child has no pipe '
                     'on this stream, so nothing can ever be read from it')
            return
        try:
            for line in stream:
                # QUALQUER LINHA E' PROGRESSO (2026-11-03, ver `_on_silence`).
                self.last_progress_at = time.monotonic()
                if name == 'stderr':
                    # O ONNX Runtime escreve em WIDESTRING: lido byte a byte vira
                    # `\u0000\u001b\u0000[` (medido 19:00:24) e a mensagem fica ilegivel.
                    if '\x00' in line:
                        line = line[:len(line) & ~1]
                        line = line.encode('latin-1', 'ignore').decode('utf-16-le', 'ignore')
                    # O LOTE A CORRER TAMBEM E' PROGRESSO: um `BRIDGE_SILENT` as 19:36:40
                    # matou um worker que tinha entregue legenda 1,9 s antes; o `blocks`
                    # congelado (o lote segura o laco) foi o que pareceu um travao.
                    if line.startswith(PROGRESS_TAGS):
                        self._arm_silence()
                    self.stderr_tail.append(line.rstrip())
                    # 3 linhas escondiam a causa (2026-11-02: duas mortes `rc=1` com
                    # `WORKER_STATS` no lugar do traceback, que vem ANTES).
                    del self.stderr_tail[:-STDERR_TAIL_MAX]
                    # The worker's own counters line, kept whole (see
                    # `last_worker_stats`): the text dump reads `peak` and
                    # `nonzero_blocks` from here, not from a new measurement.
                    if line.startswith('WORKER_STATS'):
                        parsed = parse_worker_stats(line)
                        if parsed is not None:
                            if child is not None:
                                parsed['childPid'] = child.pid
                            self.last_worker_stats = parsed
                            # The PUSH half of `getStats`/`onStats`: the panel's
                            # level meter is fed from the same parsed line the
                            # panel-state dump reads, so the two cannot disagree.
                            # GUARDED, and that is load-bearing: this runs inside
                            # the stderr reader's `try`, whose `except` logs
                            # BRIDGE_PUMP_DIED and ENDS THE STREAM — a raise here
                            # would take the worker's whole stderr channel (and
                            # the watchdog's heartbeat) down with it.
                            try:
                                self.on_stats(parsed)
                            except Exception as exc:  # noqa: BLE001
                                self.log(f'BRIDGE_STATS_CALLBACK_FAILED '
                                         f'error={exc!r}')
                            # The heartbeat is PROGRESS. Re-arming here is the
                            # whole cure: this stream used to `continue` before
                            # `_arm_silence`, so the one periodic signal the
                            # worker publishes never reached the watchdog.
                            self._note_progress(parsed)
                            # A MEMORIA PUBLICADA: uma linha por minuto. Sem serie nao ha'
                            # como provar nem refutar uma fuga -- o `rss_mb` so' aparecia na
                            # cauda da morte, ou seja exactamente quando ja' nao havia o que medir.
                            if time.monotonic() - self._rss_at >= 60.0:
                                self._rss_at = time.monotonic()
                                _f = parsed.get('fields') or {}
                                self.log('BRIDGE_RSS rss_mb=%s blocks=%s' % (
                                    _f.get('rss_mb', '-'), _f.get('blocks', '-')))
                    continue
                text = line.strip()
                if text:
                    self._consume(text, child)
                # AFTER the consume, not before (S7): the window is a function of
                # the phase the line just PUBLISHED. `model-loaded` turns the
                # watchdog back to `WORKER_SILENCE_MS`, and re-arming first would
                # leave the child on the remainder of its load ceiling.
                self._arm_silence()
        except Exception as exc:
            self.log(f'BRIDGE_PUMP_DIED stream={name} error={exc!r}')
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _meter(self, message, child=None):
        """THE WAVE: one `{peak, blocks}` WINDOW from the worker's own meter.

        The shape is the worker's (`sotto_worker.py:3591`,
        `emit(type="meter", **level)` where `level` is `{"peak","blocks"}`), and
        it is deliberately the SAME two fields the stats payload carries: the
        panel has one consumer (`panel.js:1640` `pushLevel`) and must never be
        handed two different pictures of one measurement.

        WHY IT IS A BRANCH OF ITS OWN. Without it this line fell through to the
        unknown-kind `else`, which logs `BRIDGE_UNKNOWN type='meter'` PER SAMPLE
        — measured 35 B × 10 Hz ≈ **20.5 KB/min with no end**. The cure is NOT to
        stop publishing the meter (that exact mistake was made once already, on
        the worker side, where the meter default was set to zero to keep the log
        quiet): the LOG is what gets a budget, and the data keeps flowing.

        The `peak` here is the peak of THIS WINDOW; the `WORKER_STATS` line on
        stderr carries the RUNNING MAXIMUM of the whole run. A wave drawn from a
        running maximum is a staircase that only rises and then flattens — which
        is the defect the owner reported — so `SottoShell.stats()` prefers this
        sample while it is fresh.
        """
        self.meters += 1
        sample = {'at': time.monotonic()}
        for key in ('peak', 'blocks'):
            value = message.get(key)
            if value is None:
                continue
            try:
                sample[key] = float(value)
            except (TypeError, ValueError):
                self.malformed += 1
        if child is not None:
            sample['childPid'] = child.pid
        self.last_meter = sample
        now = sample['at']
        if self._meter_logged == 0 or (
                (now - self._meter_logged_at) >= METER_LOG_INTERVAL_S):
            self.log(f'BRIDGE_METER count={self.meters} '
                     f'in_window_s='
                     f'{round(0.0 if self._meter_logged == 0 else now - self._meter_logged_at, 1)} '
                     f'sample=' + json.dumps(
                         {k: v for k, v in sample.items() if k != 'at'},
                         separators=(',', ':')))
            self._meter_logged = self.meters
            self._meter_logged_at = now
        try:
            self.on_meter(sample)
        except Exception as exc:
            # A panel-side failure must not take the pump thread down with it:
            # that thread also carries the CAPTIONS.
            self.log(f'BRIDGE_METER_CALLBACK_FAILED error={exc!r}')
    def _consume(self, line, child=None):
        try:
            message = json.loads(line)
        except ValueError:
            self.malformed += 1
            self.log(f'BRIDGE_MALFORMED line={json.dumps(line[:200])}')
            return
        if not isinstance(message, dict):
            self.malformed += 1
            return

        # CASE-NORMALISED, like the JS twin (row #40, 2026-10-11): worker-bridge.js:691
        # reads `String(message.type || '').toLowerCase()` before it branches, and the
        # shell compared the raw string -- so the SAME line was a caption to the panel
        # language and a malformed drop here. This is the whole rule the JS arm applies
        # (measured: no separator replacement anywhere in that file), so it is the whole
        # rule applied here; anything else would be a second, invented vocabulary.
        kind = str(message.get('type') or '').lower()
        if kind == 'caption':
            text = message.get('text')
            if not text:
                # '' IS NOT A CAPTION (row #12, 2026-10-11): the test was
                # `is None`, so an empty string counted as a caption -- and a
                # caption is the ONLY thing that lifts the death hold, so a worker
                # emitting nothing proved itself alive.
                self.malformed += 1
                return
            meta = {k: v for k, v in message.items()
                    if k not in ('type', 'text')}
            self.captions += 1
            self.last_caption_at = time.monotonic()
            # A caption is the ONLY proof that the current worker is really
            # transcribing, so it is the only thing allowed to lift a death the
            # panel is showing. Anything else (a restart's warm-up status) has
            # proved nothing yet.
            if self.pending_error is not None:
                self.log(f'BRIDGE_DEATH_LIFTED reason=caption captions={self.captions}')
                self.pending_error = None
            # E UM VEREDICTO DE SILENCIO TAMBEM CAI (2026-10-30). O dono: *"por que a
            # merda do meu audio ainda some? arruam caralho"* -- e o estado do painel
            # nesta maquina provava-o ao contrario do log: `namedState=no-audio`,
            # `panel.status='not ready'`, com `live.count=1` e a legenda
            # `'fuve da |'` no ecra. `no_audio` nascia de uma janela `reason=flat`
            # (que significa "nada transcrevivel NESTA janela", nao "o dispositivo
            # esta' mudo") e ficava PRESO para a vida do filho: o painel dizia-lhe
            # que o audio dele sumiu enquanto o texto dele aparecia.
            # Uma legenda e' a unica prova de que o tap esta' a transcrever -- a
            # mesma regra que ja' levanta a morte (`pending_error`, acima) -- por isso
            # e' ela, e so' ela, que limpa este veredicto. Uma linha por episodio.
            if self.no_audio:
                self.log('NO_AUDIO_CLEARED reason=caption captions=%d evidence=%s'
                         % (self.captions, json.dumps(self.no_audio_evidence)))
                self.no_audio = False
                self.no_audio_evidence = None
                self.no_audio_evidence_at = None
            self.on_caption(str(text), meta)
        elif kind == 'meter':
            self._meter(message, child)
        elif kind == 'status':
            self.statuses += 1
            state = str(message.get('state') or '')
            if state:
                self.state = state
            # O DONO NAO FICA A OLHAR PARA O VAZIO: enquanto o modelo carrega
            # (30-38 s medidos a 2026-10-30) a janela da legenda diz que carrega.
            # O painel nao serve para isto -- `setStatus` esconde a frase.
            if state == 'model-loading' and not self.loaded:
                # A ponte AVISA, nao pinta: `push_caption_to_window` nao existe
                # na `WorkerBridge` (AttributeError medido, panel-exit3-oracle).
                # SO' ANTES do primeiro `model-loaded` deste filho: um
                # `model-loading` atrasado apagava a legenda (ver `_spawn`).
                self.on_loading_text('carregando modelo…')
            # O GRAFO QUE CORRE TEM DE APARECER NO LOG (medido 2026-11-02). O worker
            # decide os providers no arranque (`stage=providers`) e ate' hoje o log
            # da shell so' guardava o ESTADO, nunca o payload -- por isso "o Sotto
            # esta' na GPU?" nao se respondia pelo log dele: eu tive de carregar o
            # modelo num probe a parte e medir 10,75x contra 2,27x em CPU. Uma linha
            # com os providers ESCOLHIDOS e os DISPONIVEIS fecha essa pergunta com
            # um grep, e o `onaudio`/`worker-providers` oracle julga-a.
            if state == 'boot' and str(message.get('stage') or '') == 'providers':
                sel = message.get('providers_selected') or []
                avail = message.get('providers_available') or []
                self.log('WORKER_PROVIDERS selected=%s available=%s note=%s cuda_probe=%s'
                         % (','.join(str(x) for x in sel),
                            ','.join(str(x) for x in avail),
                            str(message.get('note') or '')[:80],
                            str(message.get('cuda_probe_model') or '')))
            if state == 'model-loaded':
                        # THE LOAD IS OVER, and this shell now says how long it took.
                # `load_s` is the WORKER's own measurement of the same span
                # (`worker/sotto_worker.py`, `StreamAsr.load_s`); `BRIDGE_LOAD_MS`
                # is the shell's, from the spawn, so one boot log carries both
                # and the two can be compared instead of assumed equal. This is
                # also the line that turns the watchdog's window back to
                # `WORKER_SILENCE_MS` (`_silence_window`).
                self.loaded = True
                self.load_ms = (time.monotonic() - self.spawned_at) * 1000.0
                if self.child is not None:
                    self.log(f'BRIDGE_LOAD_MS ms={round(self.load_ms)} '
                             f'pid={self.child.pid} '
                             f'worker_load_s={message.get("load_s")}')
            if message.get('device'):
                # Remember WHICH endpoint this child is on. `device` names the
                # first candidate (with the full `candidates` list); a rotation
                # names the one it moved to. Kept as raw fields so the dump can
                # name the endpoint being tapped without parsing the sentence.
                self.last_device_status = {
                    'state': state,
                    'device': message.get('device'),
                    'api': message.get('api'),
                    'peak': message.get('peak'),
                    'reason': message.get('reason'),
                    'candidates': message.get('candidates'),
                }
                if child is not None:
                    self.last_device_status['childPid'] = child.pid
            # The worker's own answer to "is there anything to transcribe?".
            # Remembered per child (reset in `_spawn`) and read by `_on_silence`
            # so the watchdog stops treating "a quiet desktop" as "a jammed
            # worker" -- see WORKER_NO_AUDIO_STATES.
            evidence = self._no_audio_evidence(state, message)
            if evidence is not None:
                self.no_audio = True
                self.no_audio_evidence = evidence
                self.no_audio_evidence_at = time.monotonic()
            # The guard's input, kept where the state is READ, not inferred
            # later: `capture-started` opens the guard, and a terminal state or
            # the child's exit closes it. See `WorkerReloadPolicy`.
            if state in WORKER_CAPTURING_STATES:
                self.capturing = True
            elif state in WORKER_ERROR_STATES or state in ('done',
                                                           'selftest-done'):
                self.capturing = False
            info = {k: v for k, v in message.items() if k not in ('type', 'state')}
            title = info.pop('title', None)
            body = info.pop('body', None)
            reason = info.pop('reason', None)
            severity = info.pop('level', None)
            if severity != 'error':
                severity = worker_status_kind(state, message)
            text = worker_status_text(state, message,
                                      self._readable(state, reason))
            if severity == 'error':
                # Remembered, so the automatic restart that follows cannot paint
                # its warm-up over a death the owner has not been shown yet.
                # ONE verdict slot: a no-audio verdict that arrives later
                # REPLACES the failure, and vice versa, so `_wait` reads the
                # worker's most recent word rather than a stale colour.
                self.last_error = {'state': state, 'text': text,
                                   'body': body or worker_status_body(state, message)}
                self.last_no_audio = None
                self.log(f'BRIDGE_STATUS_ERROR state={json.dumps(state)} '
                         f'kind={severity} text={json.dumps(text)}')
            elif severity == 'no-audio':
                # The calm twin: the worker's OWN no-audio verdict, kept the
                # same way (state, sentence, body) so the restart that follows
                # cannot warm its way over it, and logged with its own line
                # name so a reader never mistakes it for a fault.
                self.last_no_audio = {'state': state, 'text': text,
                                      'body': body or worker_status_body(state, message)}
                self.last_error = None
                self.log(f'BRIDGE_STATUS_NOAUDIO state={json.dumps(state)} '
                         f'kind=no-audio text={json.dumps(text)}')
            elif self.pending_error is not None and state in WORKER_WARMUP_STATES:
                # A restart re-emits model-loading/model-loaded/capture-started
                # every cycle. Painting those over a pending death is how the
                # panel came to show a healthy app while the worker was dying in
                # a loop, so they are logged and held instead.
                self.log(f'BRIDGE_STATUS_HELD state={json.dumps(state)} '
                         f'behind={json.dumps(self.pending_error["state"])}')
                return
            if severity == 'error':
                if not body:
                    body = (self.last_error or {}).get('body') or ''
                if not title:
                    title = 'Not transcribing'
            elif severity == 'no-audio':
                # The calm headline, the worker's own cause under it. NOT
                # 'Not transcribing': that title is the red one's, and this
                # state is the healthy-app/no-audio answer.
                if not body:
                    body = (self.last_no_audio or {}).get('body') or ''
                if not title:
                    title = 'No audio to transcribe'
            self._status(text, severity, {'title': title, 'body': body})
        else:
            self.malformed += 1
            self.log(f'BRIDGE_UNKNOWN type={kind!r}')

    def _readable(self, state, reason):
        """Say the state in words without pretending to a map we did not port.

        The Electron bridge renders worker states through STATE_MAP. That table
        is a cosmetic dictionary in another file and is NOT ported here; a raw
        state token is shown verbatim rather than guessed at, which is a fact
        instead of an invention.
        """
        return f'{state} ({reason})' if reason else state

    # -- supervision -------------------------------------------------------
    def _arm_silence(self):
        """Re-arm the no-output watchdog.

        MUST NOT take `self._lock`. `_spawn` is called from `start()` WITH the
        lock held and arms this watchdog on its way out, so a lock-taking body
        deadlocks the caller against itself — `threading.Lock` is not
        reentrant. Measured on this box (`_main/exit3-armB1.log`): the shell
        hung there, `start()` never returned, so `run.cmd --with-worker` never
        armed `--exit-after`, never ran its `--dump-dom` probe, and its stdout
        reader thread blocked before its first line. That is why a live run
        logged `BRIDGE_EXIT ... statuses=0` on all eight worker cycles and the
        panel could only ever show the bare `Worker stopped (exit 3)`.

        No lock is needed here: `_on_silence` re-checks `self.stopped`, so the
        worst case of a race with `stop()` is a timer that fires and returns.
        """
        if self.stopped:
            return
        if self._silence_timer is not None:
            self._silence_timer.cancel()
        timer = threading.Timer(self._silence_window(), self._on_silence)
        timer.daemon = True
        self._silence_timer = timer
        timer.start()

    def _silence_window(self) -> float:
        """The no-output window for the child's CURRENT phase, in seconds.

        TWO WINDOWS, because a silent worker and a LOADING worker are different
        facts. Before `model-loaded` the worker is obliged to be quiet - the load
        reads a gigabyte of weights and copies them to the VRAM and says nothing
        while it does - so the window it gets is the load ceiling, measured from
        the spawn and shrinking as the load runs. After `model-loaded` the worker
        is obliged to be WORKING, and a worker that goes mute has stopped
        transcribing, so it gets `WORKER_SILENCE_MS`.

        A single longer window for both phases would either kill the cold boot or
        let a jammed worker keep its caption channel for five minutes; the phase
        is the only thing that tells the two apart.
        """
        if self.loaded or not self.spawned_at:
            return self.silence_ms / 1000.0
        elapsed_ms = (time.monotonic() - self.spawned_at) * 1000.0
        return max(1.0, (self.load_silence_ms - elapsed_ms) / 1000.0)

    def _note_progress(self, stats):
        """The worker's own heartbeat counts as PROGRESS; re-arm the watchdog.

        MUST NOT take `self._lock` — it is called from the pump thread, and the
        same rule as `_arm_silence` applies.

        THE DEFECT THIS CLOSES, measured in the owner's own log
        (`_main/webview-run.log`, 2026-10-06, `pid=4312`/`pid=47056`): the only
        PERIODIC signal the worker publishes is `WORKER_STATS tag=tick` on
        STDERR (`--stats-interval`, 10 s), and it carries the ADVANCING
        `blocks=` counter — the worker's own proof that it is still consuming
        audio. `_pump` re-armed the watchdog for STDOUT lines only, so that
        proof was invisible: 15 s without a CAPTION killed a worker that was
        transcribing (`BRIDGE_RESTART reason=silent`, 33 times in that log;
        `captions=29` on the very pid that was killed), and every respawn paid
        a ~2.4 GB model reload before it could caption again.

        The counter must ADVANCE. Otherwise a worker that reprints its last
        line forever — a wedged loop — would buy itself an eternal reprieve and
        the watchdog would stop being a watchdog.
        """
        try:
            blocks = int((stats.get('fields') or {}).get('blocks', ''))
        except (TypeError, ValueError):
            return
        if self._progress_blocks is not None and blocks <= self._progress_blocks:
            return
        self._progress_blocks = blocks
        self._arm_silence()

    def _cancel_timers(self):
        for name in ('_silence_timer', '_restart_timer'):
            timer = getattr(self, name, None)
            if timer is not None:
                timer.cancel()
                setattr(self, name, None)

    def _no_audio_evidence(self, state, message):
        """The worker's OWN sentence that there is nothing to transcribe.

        Returns the sentence (for the log) or None. Three shapes, all of them a
        measurement the WORKER made about the ENDPOINT -- never an inference the
        shell draws from a caption that did not arrive:

          * `device-rotated` with `reason=flat`: the per-candidate row the ladder
            writes on its way out of a window that produced NO CAPTION. The
            worker's word is `flat`, but it is NOT "below the peak floor" —
            measured on this box, a live idle run rotated with
            `peak=0.465216` against `floor=0.002`
            (`_main/_tap-restart-live-after.log`): the tap heard something and
            the model found nothing to transcribe in the window
            (sotto_worker.py:2163 settles only on a CAPTION). So the row means
            "this candidate carried nothing I could transcribe, moving on" —
            the ladder accounting for the silence, candidate after candidate,
            which is exactly what an idle desktop produces.
            `open-failed` is deliberately NOT included: a device that could not
            be OPENED is a fault, not a measurement of the audio.
          * a terminal device state (`silent-device`, `device-exhausted`,
            `silent-capture`, `no-speech-in-capture`, `music-only-capture`).
          * a `done` whose verdict is one of WORKER_NO_AUDIO_VERDICTS. An absent
            or unknown verdict is NOT evidence of no audio, so it does not count.
        """
        message = message or {}
        if state == 'device-rotated':
            if str(message.get('reason') or '') == 'flat':
                return (f'device-rotated reason=flat '
                        f'peak={message.get("peak")} '
                        f'floor={message.get("peak_floor")}')
            return None
        if state == 'tap-silent-desktop':
            # O WORKER DISSE QUE A MAQUINA ESTA' CALADA (2026-11-03). Sem
            # esta linha, uma morte DEPOIS desta declaracao virava
            # `kind=error` -> escada `retry` (1 s, 2 s, 8 s...) e cada
            # volta RECARREGA o modelo: medido nesta sessao, 04:07-04:17,
            # tres cargas de 35-56 s para trinta e poucos segundos de
            # silencio de desktop. A declaracao do proprio worker ja' e' a
            # sentenca; o que falta e' a escada certa (minutos) e o tecto.
            return (f'tap-silent-desktop '
                    f'window_s={message.get("window_s")} '
                    f'endpoints={message.get("endpoints")} '
                    f'peak={message.get("peak")}')
        if state == 'done':
            verdict = str(message.get('verdict') or '').strip()
            if verdict and verdict in WORKER_NO_AUDIO_VERDICTS:
                return f'done verdict={verdict}'
            return None
        if state in WORKER_NO_AUDIO_STATES:
            return f'state={state}'
        return None

    def _on_silence(self):
        if self.stopped or self.child is None:
            return
        if self.no_audio:
            # BENIGN, and the fix for this lane's defect. The worker has already
            # published its own verdict that the tap carries nothing to
            # transcribe, and a tap that carries nothing produces NOTHING on
            # stdout by design -- so this quiet is the CORRECT behaviour on a
            # quiet machine, not a jam. Killing it here is what produced 8
            # `BRIDGE_SILENT` and `spawns=10` in ONE live run, each respawn
            # reloading a ~2.4 GB model, with no caption able to ever break the
            # cycle (owner's brief: "o loop nunca converge").
            #
            # Nothing is killed. The state is NAMED so the panel says what is
            # true, and the timer is re-armed so the watchdog keeps watching --
            # it must still catch a child that wedges AFTER saying this.
            age_s = (round(time.monotonic() - self.no_audio_evidence_at, 1)
                     if self.no_audio_evidence_at else None)
            self.log(f'BRIDGE_SILENT_BENIGN ms={self.silence_ms} '
                     f'pid={self.child.pid} state={NO_AUDIO_STATE} '
                     f'because={json.dumps(self.no_audio_evidence)}'
                     f' evidence_age_s={age_s} restarts={self.restarts}')
            if self.pending_error is None:
                # Only when no death is on screen: a real exit outranks a benign
                # quiet, and painting a status over it is the swallow this file
                # already fights (see `pending_error`).
                self._bridge_status(
                    'Audio tap silent - nothing to transcribe', 'busy',
                    {'title': 'No audio to transcribe',
                     'body': ('The worker\'s device ladder found nothing it '
                              'could transcribe in the window it tapped, '
                              'candidate after candidate, and said so itself ('
                              + str(self.no_audio_evidence or 'no evidence')
                              + (', measured %ss ago' % age_s if age_s is not None
                                 else '')
                              + '). reason=flat means "nothing transcribable in '
                              'this window", NOT "below the peak floor": the '
                              'peak can be loud (music, a call on another '
                              'endpoint) and the model still finds no speech. '
                              'The worker keeps listening; it is not restarted.'),
                     'evidence': self.no_audio_evidence,
                     'evidenceAgeS': age_s},
                    NO_AUDIO_STATE)
            else:
                self.log(f'BRIDGE_SILENT_BENIGN_HELD state={NO_AUDIO_STATE} '
                         f'behind={json.dumps(self.pending_error["state"])}')
            self._arm_silence()
            return
        # -- THE LOAD WINDOW (S7) ---------------------------------------------
        # Silence while `model-loaded` has not arrived is the load, not a jam.
        # The cold boot is exactly this case and it is not rare: the Windows
        # autostart task puts the app's load on the worst minute of the day, with
        # a cold file cache, a Defender pass over the same gigabyte and
        # Chromium's own GPU process starting next door - so the load that takes
        # 3.4 s warm outlives the 30 s window cold. Killing it there is what
        # cost the owner ~1 minute of transcription on EVERY boot and made the
        # app load the model twice in the first minute.
        #
        # Nothing is killed and nothing is painted: the panel is already showing
        # `model-loading`, which is the truth. The watchdog RE-ARMS, so a child
        # that loads in 45 s is never touched - and the ceiling above is still
        # enforced, because a worker that hangs inside its load is the one jam
        # this watchdog exists for.
        if not self.loaded:
            elapsed_ms = ((time.monotonic() - self.spawned_at) * 1000.0
                          if self.spawned_at else 0.0)
            quiet_ms = ((time.monotonic()
                        - getattr(self, 'last_progress_at', self.spawned_at))
                        * 1000.0)
            if (quiet_ms < self.load_silence_ms
                    or elapsed_ms < WORKER_LOAD_HARD_CEILING_MS * 0.5):
                # UMA LINHA POR CARGA, NAO UMA POR SEGUNDO (2026-11-03).
                # MEDIDO: um load de 206 s escreveu 115 destas linhas, uma
                # por segundo, cada uma com um fsync no log de 50 MB. O
                # vigia re-arma de 1 em 1 s; a carga e' uma so', e o
                # espaco tambem e' um sinal (mudanca de fase).
                _now_load = time.monotonic()
                if _now_load - getattr(self, '_load_line_at', 0.0) < 15.0:
                    self._arm_silence()
                    return
                self._load_line_at = _now_load
                self.log(f'BRIDGE_SILENT_LOADING ms={round(quiet_ms)} '
                         f'pid={self.child.pid} '
                         f'total_ms={round(elapsed_ms)} '
                         f'window_ms={self.load_silence_ms} '
                         'because=model-not-loaded')
                self._arm_silence()
                return
            self.log(f'BRIDGE_SILENT_LOAD_TIMEOUT ms={round(elapsed_ms)} '
                     f'pid={self.child.pid} window_ms={self.load_silence_ms} '
                     'because=model-never-loaded')
            self._status('Worker is still loading the model', 'error',
                         {'title': 'Model load timeout',
                          'body': f'The worker did not report `model-loaded` '
                                  f'within the load window of '
                                  f'{round(self.load_silence_ms / 1000)} s.'})
            self._kill_and_restart('load-timeout')
            return
        # -- END THE LOAD WINDOW (S7) -----------------------------------------
        # ANOMALOUS. The tap was open (or had declared itself) and then went
        # mute WITHOUT the worker ever saying what the audio was: that is the
        # jam this watchdog exists for, and it still restarts.
        self.log(f'BRIDGE_SILENT ms={self.silence_ms} pid={self.child.pid}')
        self._status('Worker is running but has said nothing', 'error',
                     {'title': 'Worker silent',
                      'body': 'The worker process is alive and produced no '
                              'output within the silence window.'})
        self._kill_and_restart('silent')

    def _wait(self):
        child = self.child
        if child is None:
            return
        rc = child.wait()
        self.last_exit = rc
        killed, self.killed = self.killed, False
        self.log(f'BRIDGE_EXIT pid={child.pid} rc={rc} killed={killed} '
                 f'spawns={self.spawns} '
                 f'captions={self.captions} statuses={self.statuses} '
                 f'malformed={self.malformed} '
                 f'stderr_tail={json.dumps(self.stderr_tail[-STDERR_TAIL_MAX:])}')
        _exc = next((l.strip()[:200] for l in reversed(self.stderr_tail)
                     if l[:1] not in (" ", "\t")
                     and ("Error" in l or "Exception" in l)), None)
        if _exc:
            self.log(f'BRIDGE_DEATH_CAUSE {_exc}')
        self.child = None
        self.capturing = False
        if killed:
            # O SHELL MATOU-O (janela de silencio, timeout de load): o `rc=1` e
            # o `TerminateProcess` do Windows, nao a sentenca do worker. Publique-se
            # como o que e', e NAO como `BRIDGE_DEATH kind=error` + recarga contada
            # como falha: o `_kill_and_restart` ja' agendou a volta, com a razao dele.
            self.log(f'BRIDGE_KILLED pid={child.pid} rc={rc} '
                     'why=the-shell-terminated-it')
            return
        if self.stopped:
            return
        # The stderr tail is the worker's own sentence about its own death
        # (`SILENT-DEVICE ... peak=... < floor=...`); the reference arm keeps
        # three lines "to explain a death on the status line" and this shell
        # kept them only in its log, which is not where the owner looks.
        stderr_note = ' | '.join(self.stderr_tail[-2:])[:240]
        if rc != 0:
            # A non-zero exit is a DEATH, not a pause. The panel is obliged to
            # keep saying so through the automatic restart, because the restart's
            # warm-up statuses say nothing about whether the death will repeat.
            self.deaths += 1
            # WHICH death the worker reported, not what the exit code suggests:
            # the verdict ladder makes exit 3 the no-audio conclusion
            # (`done.verdict == "silent-device"` iff `exit == 3`), so a run that
            # ended on the worker's own no-audio word paints the CALM state and
            # the worker's sentence -- the owner read the red exit line as the
            # app being broken when the machine was simply quiet. A crash with
            # NO verdict still paints red: the slot below is only calm when the
            # worker said so itself.
            self.pending_error = self.last_error or self.last_no_audio or {
                'state': 'exit', 'text': f'worker exit {rc}', 'body': ''}
            # CALM only when the WORKER SAID SO ITSELF: the no-audio slot set
            # and no error slot set. A crash that published NO verdict at all
            # (the fallback dict above) is RED -- "the worker did not tell us
            # what happened" is a failure, and it must never borrow the calm
            # colour of the verdict before it.
            death_kind = ('no-audio'
                          if (self.last_error is None
                              and self.last_no_audio is not None)
                          else 'error')
            text = f'Worker stopped (exit {rc}) - {self.pending_error["text"]}'
        else:
            self.pending_error = None
            death_kind = 'error'
            text = f'Worker stopped (exit {rc})'
        if self.pending_error is not None:
            self.log(f'BRIDGE_DEATH rc={rc} deaths={self.deaths} '
                     f'kind={death_kind} '
                     f'last={json.dumps(self.pending_error["text"])} '
                     f'stderr_tail={json.dumps(self.stderr_tail[-2:])}')
        self._status(text, death_kind,
                     {'title': ('Worker stopped' if death_kind == 'error'
                                else 'No audio to transcribe'),
                      'body': ' '.join(x for x in (
                          ((self.last_error or {}).get('body')
                           or (self.last_no_audio or {}).get('body'))
                          if rc != 0 else '',
                          stderr_note,
                          'A restart is scheduled. Captions stay off until the '
                          'worker reports a caption.') if x)})
        self._schedule_restart('exit', no_audio=(death_kind == 'no-audio'))

    def _kill_and_restart(self, reason):
        child, self.child = self.child, None
        self.killed = child is not None
        if child is not None:
            try:
                child.terminate()
            except Exception as exc:  # noqa: BLE001
                # UM WORKER QUE SOBREVIVE AO TERMINATE E' UM SEGUNDO
                # TRABALHADOR A CAPTAR: o restart agenda-se a seguir, e dois
                # captadores no mesmo dispositivo ao mesmo tempo e' a falha
                # mais difícil de ver que existe.
                self.log(f'BRIDGE_TERMINATE_FAILED pid={child.pid} error={exc!r}')
        self._schedule_restart(reason)

    def _schedule_restart(self, reason, no_audio=False):
        if self.stopped:
            return
        # The two ladders. A REAL failure prices itself in seconds and doubles every
        # time; a no-audio death -- the worker doing its job on a machine with nothing
        # routed yet -- prices itself in minutes and has its own counter, so a genuine
        # break is still answered fast and an unrouted desktop is answered slowly.
        # O TECTO. Ver `no_audio_restart_cap`: depois de tantas mortes seguidas por
        # silencio, REINICIAR NAO PODE ARRANJAR NADA -- um veredicto de dispositivo
        # silencioso diz que a ROTAGEM esta errada, e recarregar 1 GB de modelo nao
        # mexe numa rotagem. So custa 36 s de disco, RAM e GPU a cada volta. Para.
        if self.no_audio_restarts >= self.no_audio_restart_cap:
            self.log(f'BRIDGE_RESTART_SUPPRESSED reason={reason} ladder=no-audio '
                     f'no_audio_restarts={self.no_audio_restarts} '
                     f'cap={self.no_audio_restart_cap} '
                     'why=restarting-cannot-fix-a-routing-problem '
                     'resume=press-Alt+C')
            self._arm_audio_resume(reason)
            self.pending_error = {
                'state': NO_AUDIO_STATE,
                'text': ('Nada foi roteado para o Sotto, e o Sotto parou de '
                         'recarregar o modelo para nao queimar o PC. Confere a '
                         'rotagem (VoiceMeeter / som do Windows) e aperta Alt+C, '
                         'que ele tenta de novo.'),
            }
            return
        if no_audio:
            delay = min(self.no_audio_backoff_max,
                        self.no_audio_backoff_base * (2 ** self.no_audio_restarts))
            self.no_audio_restarts += 1
            ladder = 'no-audio'
        else:
            delay = min(self.backoff_max, self.backoff_base * (2 ** self.restarts))
            self.restarts += 1
            ladder = 'retry'
        self.log(f'BRIDGE_RESTART reason={reason} ladder={ladder} in_ms={delay} '
                 f'restart={self.restarts}')
        timer = threading.Timer(delay / 1000.0, self._restart)
        timer.daemon = True
        # CANCEL BEFORE OVERWRITING (row #15, 2026-10-11): overwriting the handle
        # left the previous timer ARMED and unreachable, so two restarts could
        # fire for one death -- and `_cancel_timers()` could no longer reach the
        # first one at all.
        if self._restart_timer is not None:
            try:
                self._restart_timer.cancel()
            except Exception as exc:  # noqa: BLE001
                # O TIMER ANTIGO PODE SOBREVIVER AO CANCELAMENTO -- e um timer
                # armado e inalcancavel e' EXACTAMENTE o bug que a row #15
                # (2026-10-11) removeu: dois reinicios para uma morte. O
                # cancelamento e' o cure; engoli-lo devolve o bug calado.
                self.log(f'BRIDGE_RESTART_TIMER_CANCEL_FAILED error={exc!r}')
        self._restart_timer = timer
        timer.start()

    def _arm_audio_resume(self, reason):
        """O DESKTOP CALADO NAO PODE DEIXAR O WORKER MORTO PARA SEMPRE.

        Medido 2026-11-03: a escada de no-audio acaba por parar (com razao --
        recarregar o modelo nao arranja uma rotagem errada), e ate' agora a
        unica forma de ele voltar era o dono apertar Alt+C. Isto devolve a
        volta ao unico sinal que importa: alguem comecou a tocar ALGUMA COISA
        (`audio_playing.playing`, que so' LE os medidores dos endpoints).
        Uma sonda de 3 s por volta, uma lista de dispositivos por sonda; sai
        no primeiro som e nao toca em mais nada.
        """
        if getattr(self, '_audio_resume_armed', False) or self.stopped:
            return
        self._audio_resume_armed = True

        def _watch():
            try:
                import audio_playing
            except Exception as exc:  # noqa: BLE001
                self.log(f'BRIDGE_RESUME_UNAVAILABLE error={exc!r}')
                self._audio_resume_armed = False
                return
            while not self.stopped:
                time.sleep(3.0)
                try:
                    if not audio_playing.playing():
                        continue
                except Exception:  # noqa: BLE001
                    continue
                self.log('BRIDGE_RESUME_AUDIO reason=audio-detected '
                         f'after={reason}')
                with self._locked():
                    if self.stopped or self.child is not None:
                        self._audio_resume_armed = False
                        return
                    self.no_audio_restarts = 0
                    self.state = 'restarting'
                    self._spawn()
                self._audio_resume_armed = False
                return

        threading.Thread(target=_watch, name='sotto-audio-resume',
                         daemon=True).start()

    def _restart(self):
        # THE LOCK (row #43, 2026-10-11): this path set the state and spawned with no
        # lock, so it could interleave with `start()`/`stop()` -- the two callers that
        # hold it -- and resurrect a worker the owner had just stopped. `_spawn()`
        # itself takes no lock (measured: `start()` holds it across `_spawn()`), so
        # taking it here cannot deadlock.
        with self._locked():
            if self.stopped or self.child is not None:
                return
            self.state = 'restarting'
            self._spawn()


def default_python() -> str:
    """`python` when it resolves, else the interpreter running this shell.

    worker-bridge.js hardcodes 'python'. This host reports which one it used
    rather than failing with an ENOENT the owner then has to decode.
    """
    return shutil.which('python') or sys.executable


def default_speaker_sidecar_path():
    """`worker/speaker_sidecar.py`, next to the worker, resolved from THIS file.

    The shell lives at `app/webview/`; the worker at `worker/`. Resolving from
    `__file__` rather than the CWD means a `start`-detached launch -- whose CWD
    is wherever the double-click happened -- still finds it. That is not
    hypothetical: `run.cmd` does `cd /d "%~dp0"` before `start`, and the Windows
    autostart task (2026-10-12) does not.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(
        os.path.join(here, os.pardir, os.pardir, 'worker', 'speaker_sidecar.py'))


def speaker_watch_payload_path():
    """`_main/diar-watch.json`, resolved the SAME way, from `__file__`.

    A different file from `_main/diar-live.json` on purpose. The two are written
    by the two arms of the sidecar and read by two different readers with two
    different required keys; sharing one path would make "which model ran?" a
    question the reader could not answer.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(
        os.path.join(here, os.pardir, os.pardir, '_main', 'diar-watch.json'))


def _speaker_bridge():
    """`worker/speaker_bridge.py`, imported the first time Fase A needs it.

    LAZY on purpose. The bridge is a worker-side module, and the shell runs on a
    machine that is already loading a ~2,4 GB ASR model; pulling `worker/` onto
    `sys.path` at import time would change start-up for every run, including the
    ones that never ask for voices. A shell that never enables Fase A never pays
    for it.
    """
    global _SPEAKER_BRIDGE
    if _SPEAKER_BRIDGE is not None:
        return _SPEAKER_BRIDGE
    here = os.path.dirname(os.path.abspath(__file__))
    worker = os.path.normpath(
        os.path.join(here, os.pardir, os.pardir, 'worker'))
    if worker not in sys.path:
        sys.path.insert(0, worker)
    import speaker_bridge                                           # noqa: PLC0415
    _SPEAKER_BRIDGE = speaker_bridge
    return _SPEAKER_BRIDGE


_SPEAKER_BRIDGE = None


# ===========================================================================
# memory
# ===========================================================================


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [('cb', ctypes.c_ulong),
                ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]


def rss_mb(pid: int):
    """Working set of `pid` in MB, measured with GetProcessMemoryInfo."""
    psapi = ctypes.WinDLL('psapi', use_last_error=True)
    kernel32.OpenProcess.restype = wt.HANDLE
    handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)  # QUERY+VM_READ
    if not handle:
        return None
    try:
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters),
                                          counters.cb):
            return None
        return counters.WorkingSetSize / (1024.0 * 1024.0)
    finally:
        kernel32.CloseHandle(handle)


TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_ulong), ('cntUsage', ctypes.c_ulong),
                ('th32ProcessID', ctypes.c_ulong),
                ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', ctypes.c_ulong),
                ('cntThreads', ctypes.c_ulong),
                ('th32ParentProcessID', ctypes.c_ulong),
                ('pcPriClassBase', ctypes.c_long), ('dwFlags', ctypes.c_ulong),
                ('szExeFile', ctypes.c_wchar * 260)]


def _process_table():
    """Every (pid, ppid, exe) on the machine, from the Toolhelp snapshot.

    Not `wmic`: on this host `wmic` is not on PATH
    (`wmic process ... ` -> `error: command not found: wmic`, measured), so a
    wmic-based census would report an empty child list and quietly understate
    the memory. This reads the same fact from the kernel.
    """
    kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
    kernel32.Process32FirstW.argtypes = [wt.HANDLE,
                                          ctypes.POINTER(PROCESSENTRY32W)]
    kernel32.Process32NextW.argtypes = [wt.HANDLE,
                                         ctypes.POINTER(PROCESSENTRY32W)]
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == wt.HANDLE(-1).value or not snapshot:
        return []
    rows = []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            rows.append((int(entry.th32ProcessID),
                         int(entry.th32ParentProcessID),
                         entry.szExeFile))
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return rows


def child_processes(parent_pid: int):
    """[(pid, depth, exe)] for every DESCENDANT of `parent_pid`.

    Descendants, not just direct children: the first version counted direct
    children only and measured 210.9 MB, but WebView2's browser process
    spawns its own renderer/gpu/utility children, so that number was a floor,
    not a total. A shell comparison that flatters itself by stopping one level
    up is not a comparison. BFS over the same kernel snapshot, so the cost is
    one pass.
    """
    rows = _process_table()
    by_parent = {}
    for pid, ppid, exe in rows:
        by_parent.setdefault(ppid, []).append((pid, exe))
    out, frontier, depth = [], [parent_pid], 1
    while frontier:
        nxt = []
        for parent in frontier:
            # not the direct-child variant: the tree has to be walked whole
            for pid, exe in by_parent.get(parent, ()):
                out.append((pid, depth, exe))
                nxt.append(pid)
        frontier = nxt
        depth += 1
    return out


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [('dwLength', wt.DWORD),
                ('dwMemoryLoad', wt.DWORD),
                ('ullTotalPhys', ctypes.c_ulonglong),
                ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong),
                ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong),
                ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]


def commit_pct():
    """A pressao de COMMIT do sistema, em percentagem -- o sinal do shedding.

    E' o mesmo sinal que o gate central (`performance-gate.py`) usa como
    `commit-pct`, e de proposito: dois numeros diferentes para "a maquina esta
    carregada" seriam duas verdades. `None` quando o Windows nao responde --
    `None` NAO e' zero, e o shedding trata-o como "nao sei" e nao desliga nada.
    """
    try:
        status = _MemoryStatusEx()
        status.dwLength = ctypes.sizeof(_MemoryStatusEx)
        if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        total = float(status.ullTotalPageFile or 0)
        if total <= 0:
            return None
        used = total - float(status.ullAvailPageFile or 0)
        return max(0.0, min(100.0, used / total * 100.0))
    except Exception:  # noqa: BLE001 -- uma leitura falhada e' "nao sei"
        return None


def load_shedding():
    """O modulo da decisao, importado como os outros deste ficheiro."""
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import load_shedding as module
    return module


class LoadSheddingMonitor(threading.Thread):
    """Le a pressao da maquina e diz que motores correm -- por omissao, SO' DIZ.

    ORDEM DO DONO (2026-10-30): *"alta: desliga nemotron, so parakeet; muito alta:
    desliga parakeet tambem. AUDIO SEMPRE fica para processar depois"*.

    O CANAL EXISTE, E NAO FOI PRECISO INVENTAR UM. Medido em 2026-10-30: o worker
    JA' le' `_main/panel-visibility.json` a cada bloco (o interruptor do Redux),
    e o campo `shed` viaja nesse mesmo ficheiro. Logo o shell nao precisa de IPC
    nenhum para dizer "para o AO VIVO e deixa o batch": escreve o nivel e o
    worker obedece em `ReduxSwitch.tick` (`alta` -> `batch`, `muito-alta` ->
    `shed`, com o audio a ficar na fila).

    PORQUE E' QUE A ACCAO COARSA SAIU. O lever antigo (`_pause_shell`) DESCARREGA
    os dois motores -- obedecia ao contrario de *"alta: desliga nemotron, so
    parakeet"* -- e ainda por cima perdia o audio que estava a acumular, contra
    *"AUDIO SEMPRE fica para processar depois"*. Com o canal do ficheiro, parar
    tudo deixou de ser um lever e passou a ser um dano: `SOTTO_LOAD_SHED_ACT`
    fica RETIRADO (ver `docs/`), e o unico interruptor que sobra e'
    `SOTTO_LOAD_SHED=0`, que desliga a MEDICAO.

    O log continua a ser o que calibra: `LOAD_SHEDDING level=.. commit=..` da' a
    distribuicao real da maquina dele.
    """

    INTERVAL_S = 5.0

    def __init__(self, shell, log_fn=log):
        super().__init__(name='sotto-load-shedding', daemon=True)
        self.shell = shell
        self.log_fn = log_fn
        self.state = load_shedding().LoadShedding()
        self._stop = threading.Event()

    def step(self, reading):
        """Uma amostra. Devolve o dict do estado vigente, para o oraculo."""
        module = load_shedding()
        level, changed, why = self.state.observe(reading)
        if changed:
            self.log_fn('LOAD_SHEDDING level=%s commit_pct=%s stopped=%s why=%s'
                        % (level, 'n/a' if reading is None else '%.1f' % float(reading),
                           ','.join(self.state.stopped()) or 'nenhum', why))
            # A ACCAO E' O FICHEIRO: `PanelVisibilityWriter` le' este estado por
            # `SottoShell.shedding_level()` e poe `shed=<level>` no payload que o
            # worker ja' poll. Publicar aqui nao chega -- o escritor corre no seu
            # proprio ritmo -- por isso o nivel e' pedido JA' uma publicacao, para
            # a mudanca nao esperar o intervalo inteiro.
            self._publish()
        return self.state.as_dict()

    def _publish(self):
        """Publica o nivel AGORA, no ficheiro que o worker le'.

        Uma falha aqui nao pode derrubar o monitor (e' um thread daemon que corre
        para sempre): o nivel seguinte volta a tentar.
        """
        writer = getattr(self.shell, 'panel_visibility', None)
        if writer is None or not hasattr(writer, 'write'):
            return False
        try:
            writer.write('load-shedding')
            return True
        except Exception as exc:  # noqa: BLE001
            self.log_fn('LOAD_SHEDDING_PUBLISH_FAILED error=%r' % (exc,))
            return False

    def run(self):
        while not self._stop.is_set():
            reading = commit_pct()
            self.step(reading)
            self._stop.wait(self.INTERVAL_S)

    def stop(self):
        self._stop.set()


def memory_report():
    """This host's RSS plus every WebView2 descendant process, in MB.

    The Electron arm's 213.9 MB is `electron.exe`, which is a BROWSER PROCESS
    with its own renderer/gpu children; a like-for-like number has to include
    the WebView2 tree or it would flatter this shell. Both the host alone and
    the tree total are reported so neither number can be quoted alone.
    """
    me = os.getpid()
    host = rss_mb(me) or 0.0
    kids = []
    for pid, depth, exe in sorted(child_processes(me)):
        mb = rss_mb(pid)
        if mb is None:
            continue
        kids.append({'pid': pid, 'name': exe, 'depth': depth,
                     'rss_mb': round(mb, 1)})
    child_total = sum(k['rss_mb'] for k in kids)
    return {
        'host_pid': me,
        'host_rss_mb': round(host, 1),
        'webview_tree': kids,
        'webview_tree_rss_mb': round(child_total, 1),
        'total_rss_mb': round(host + child_total, 1),
    }


# ===========================================================================
# the per-app target
# ===========================================================================
#
# The WORKER has been able to tap ONE process tree since 2026-10-11
# (`--target-pid` / `SOTTO_TARGET_PID`, `ProcessLoopbackTap`), and every
# caption it emits carries the additive `source` field (`proc:<pid>`). What
# was missing is the APP side: `grep -n target_pid app/webview/sotto_webview.py`
# returned ZERO matches, so the capability existed and was unreachable -- the
# same defect class as a factored rule nothing calls. These two functions are
# the reachable path, and the flag that drives them is opt-in: with no
# `--app-target` and no `SOTTO_APP_TARGET`, nothing below runs.


def resolve_app_target(value):
    """`--app-target` -> the pid to tap, plus every pid the rule considered.

    Returns `(pid, candidates)`:

      * `value` is all digits and > 0 -> `(that pid, [that pid])`. The pid
        is ACCEPTED as given: whether it is still alive is the WORKER's refusal
        to make (sotto_worker.py, `_plp_pid_state` -> `state="error"
        stage="target-pid"`), not this shell's -- this function never opens
        the process, so a stale pid cannot make the shell wrong about it.
      * anything else is an IMAGE NAME, matched case-insensitively against
        `szExeFile` over the LIVE process table.
      * TREE-ROOT RULE: of the matches, only those whose PARENT is not itself a
        match survive. That is what makes `--app-target chrome.exe` mean the
        BROWSER process: the tap is opened with INCLUDE_TARGET_PROCESS_TREE, so
        the renderers' audio arrives with it, while aiming at a renderer pid
        alone would tap one renderer's share and miss the rest.
        `candidates` is the sorted root list, and the LOWEST pid is chosen
        when several roots remain.
      * no match -> `(None, [])`. The caller must REFUSE loudly (see
        `SottoShell.start_worker`): falling back to the endpoint mix would
        transcribe EVERY app while the owner believes he is reading one.

    The table is read with ctypes (`CreateToolhelp32Snapshot` /
    `Process32FirstW` / `Process32NextW`) through `_process_table`, the walk
    this module already had for the memory report. NO WMI, NO subprocess, NO
    psutil: one kernel handle, closed before this returns.
    """
    raw = str(value if value is not None else '').strip()
    if raw == '':
        return None, []
    if raw.isdigit():
        pid = int(raw)
        if pid > 0:
            return pid, [pid]
        return None, []
    wanted = raw.casefold()
    matches = [(pid, parent) for pid, parent, exe in _process_table()
               if str(exe).casefold() == wanted]
    if not matches:
        return None, []
    matched_pids = {pid for pid, _parent in matches}
    roots = sorted(pid for pid, parent in matches if parent not in matched_pids)
    if not roots:
        # A cycle cannot exist in a real process tree, but an empty root list
        # must never become "tap the whole endpoint": fall back to the LOWEST
        # match, which is still one app.
        roots = sorted(matched_pids)
    return roots[0], roots


def app_target_request(args, env=None):
    """The requested per-app tap and WHERE it came from: flag > env > none.

    Returns `(value, source)`, one of:

      `('1234', 'flag')`        --app-target 1234
      `('chrome.exe', 'env')`    SOTTO_APP_TARGET=chrome.exe, no flag
      `(None, None)`             neither: the worker taps the endpoint mix,
                                   exactly as it does today.

    `env` is a parameter, not a read of `os.environ`, so the precedence is
    assertable in-process (`_main/app-target-oracle.py`, arm f).
    """
    raw = getattr(args, 'app_target', None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), 'flag'
    env = os.environ if env is None else env
    raw = str(env.get('SOTTO_APP_TARGET') or '').strip()
    if raw:
        return raw, 'env'
    return None, None


# ===========================================================================
# CLI
# ===========================================================================


def parse_args(argv):
    parser = argparse.ArgumentParser(
        prog='sotto-webview',
        description='The Sotto panel, hosted by WebView2 (pywebview).')
    parser.add_argument('--show', action='store_true',
                        help='show the panel at startup instead of waiting '
                             'for Alt+C')
    parser.add_argument('--hotkey', default='Alt+C',
                        help='the PANELS global key (default: Alt+C). One press = '
                             'one step of the panel cycle. The live-caption key is '
                             'the owner\'s, persisted in _main/hotkey-settings.json '
                             '(factory: Ctrl+Space). If another program already owns '
                             'the panels key the shell tries '
                             + ' / '.join(HOTKEY_FALLBACKS)
                             + ' and logs which one won (HOTKEY_FALLBACK)')
    parser.add_argument('--no-hotkey', action='store_true',
                        help='do not register the global hotkey. A MEASUREMENT '
                             'run must use this: Alt+C is the app\'s only '
                             'control, and a probe that owns it shows the '
                             "owner its own panel when he presses his key")
    parser.add_argument('--install-autostart', action='store_true',
                        help='make Windows start Sotto at login (HKCU\\...\\Run, '
                             'pointing at pythonw.exe so no console appears), '
                             'then exit')
    parser.add_argument('--uninstall-autostart', action='store_true',
                        help='remove that autostart entry, then exit')
    parser.add_argument('--autostart-status', action='store_true',
                        help='print whether autostart is installed and whether it '
                             'still points at THIS checkout, then exit')
    parser.add_argument('--worker', default=DEFAULT_WORKER_PATH,
                        help='worker entrypoint to spawn')
    parser.add_argument('--python', default=None,
                        help='interpreter for the worker (default: `python`, '
                             'else this interpreter)')
    parser.add_argument('--device', default=None,
                        help='audio device. PASSED ONLY WHEN SET: the worker '
                             'resolves the tap itself by default')
    parser.add_argument('--capture', default=None,
                        help=f'capture mode (default: {DEFAULT_CAPTURE_MODE})')
    #: THE PER-APP TAP, OPT-IN. The worker has been able to tap ONE process
    #: tree since 2026-10-11 (`--target-pid` / `SOTTO_TARGET_PID`) but nothing
    #: in this shell ever passed it, so the capability was unreachable from the
    #: app. The pid travels in the ENVIRONMENT (`WorkerBridge._child_env`),
    #: never in argv: `_spawn` builds `[command, worker_path]`, and the
    #: device and the capture mode already travel that way.
    #: NOT in the measurement-flag suppression set of `_worker_autostart_reason`:
    #: this flag names a TARGET, not a measurement, so `--dump-dom --app-target X`
    #: still suppresses the worker through `--dump-dom` (the flag is parsed
    #: and logged, and no worker is spawned) -- which is what that set is for.
    parser.add_argument('--app-target', default=None, metavar='PID|IMAGE',
                        help='tap ONE app instead of the endpoint mix: a pid or '
                             'an image name (e.g. chrome.exe). A NAME is resolved '
                             "to the app's TREE ROOT -- the per-app tap follows "
                             'the whole process tree, so a renderer pid alone is '
                             'the wrong thing to aim at. An unresolvable target '
                             'starts NO worker (the endpoint mix would transcribe '
                             'every app instead of the one you named). '
                             'SOTTO_APP_TARGET also sets it; the flag wins. '
                             'WITHOUT it the worker taps the endpoint mix, '
                             'exactly as today')
    #: F1 (docs/audit/auditoria-completa-20261007.md): the worker starts BY
    #: DEFAULT. Until 2026-10-07 `start_worker` was reachable only under
    #: `if self.args.with_worker:`, and `run.cmd` -- the entry the owner
    #: double-clicks -- never passed it: 32 shell starts in `_main/webview-run.log`,
    #: 10 with a worker and every one of them `reason=with-worker`. So Alt+C on
    #: the documented path opened a panel that said "Waiting for audio" forever,
    #: with no transcription process in existence. The opt-OUT is now the flag.
    parser.add_argument('--no-worker', action='store_true',
                        help='do NOT start the worker: the shell only. The '
                             'worker starts by default (F1); this is the '
                             'opt-out, for a shell-only run')
    #: An ALIAS, kept for the lane instruments that pass it (`_main/_app-drive.py`,
    #: `_main/_live-launch.py`) and for `--help` compatibility: it is accepted,
    #: it does not change behaviour, and it can no longer be the REASON a run has
    #: a worker. Precedence with `--no-worker` is stated in `_on_loaded`.
    parser.add_argument('--with-worker', action='store_true',
                        help='start the worker at launch. Alias: the worker '
                             'already starts by default (F1), so this flag now '
                             'only FORCES the worker where an automatic '
                             'opt-out would decline it -- see --no-worker')
    #: PER-VOICE ATTRIBUTION. Off by default, because it costs a second model
    #: (277 MB) and ~1,4x realtime of CPU on this box -- a cost nobody should
    #: pay for a feature they did not ask for. What it does, end to end:
    #: this shell ALSO starts `worker/speaker_sidecar.py`, which taps the same
    #: WASAPI loopback, diarizes into `_main/diar-live.json`, and the worker
    #: reads that file per caption (`speaker_bridge.py`) and stamps ONE `source`
    #: PER VOICE on each line. The panel already renders one forming row per
    #: `source` and paints a coloured dot per voice (`panel.js` `applyVoice`), so
    #: nothing else in the app changes shape.
    #:
    #: WHY IT IS A SHELL FLAG AND NOT A WORKER-ONLY ONE: the worker alone would
    #: read a file nobody writes. Measured end to end on the owner's own Discord
    #: call (`_main/_sidecar-replay-real.py`): the real chain over 60 s of real
    #: audio gives 2 global voice slots, which is the 2 people who were talking.
    parser.add_argument('--speakers', action='store_true',
                        help='ATTRIBUTE EACH LINE TO ITS SPEAKER. Also starts '
                             'the diarizer sidecar (a second model). WITHOUT IT '
                             'every line carries the device source and the rows '
                             'are not separated by voice. NOTE the ~277 MB here '
                             'is `speaker_bridge.py:12`, a figure measured on the '
                             'STANDALONE diarizer process; two 2026-10-18 runs on '
                             'the same box, different processes, measured '
                             '207 MB for the real sidecar and 135,4 MB for a '
                             'minimal child that loads the same two models '
                             '(`_main/_watch-rss-probe.py`). None of the three '
                             'is this process, so none of them is quoted here. '
                             '--speakers-cheap quotes its own, and that one IS '
                             'measured for what it starts.')
    #: FASE A. Answers ONE question -- "were two voices talking at the same
    #: time?" -- and nothing else. It starts the SAME sidecar process with
    #: `--watch-only`, which loads the 5,7 MB segmentation model and NOT the
    #: 37,8 MB embeddings one, so it can stay on when the full attribution must
    #: not. MEASURED on this box (`_main/multivoice-oracle.py` 13/13,
    #: `_main/_watch-rss-probe.py`): RTF 0,0097 vs 0,503 of the full pipeline
    #: (52x cheaper), RSS 90,3 MB vs 135,4 MB, F1 0,932 on a 100 % overlap
    #: built from known offsets with zero false alarm on the same voice doubled.
    #:
    #: IT GIVES NO NAMES AND NO `source`. It writes `_main/diar-watch.json`,
    #: which has NO `segments` key, and `speaker_bridge.payload_if_fresh`
    #: returns `None` for such a payload -- so the caption path cannot mistake
    #: "nao medido" for "medido: zero vozes". That property is a check, not a
    #: comment: `_main/speaker-watch-oracle.py` (22/22).
    #:
    #: WHY IT IS A SEPARATE FLAG AND NOT A MODE OF `--speakers`: the owner's ask
    #: (2026-10-18) was to keep DETECTING while separating LATER. If the cheap
    #: watch only existed as a mode of the expensive flag, it could not be on
    #: when the expensive one is off, which is the whole point.
    parser.add_argument('--speakers-cheap', action='store_true',
                        help='only DETECT that several voices were talking at '
                             'once (Fase A, ~90 MB). Does not name voices and '
                             'does not stamp them on the lines; that is '
                             '--speakers. Keep this on and use --speakers when '
                             'it is safe to separate them')
    #: Keeps the FLAGGED audio, which is the only way "process the voices later"
    #: can mean anything. MEASURED: the sidecar's RingBuffer is in memory and
    #: slides -- a window is freed 10 s after it is seen, so the detection
    #: survives and the audio does not (`_main/_phase-a-retention-probe.py`).
    #: One 16 kHz mono WAV per flagged span (2-7 s each, 2 s of context), named
    #: with the absolute instant, FIFO-capped at 256 MB. Then
    #: `_main/multivoice-offline.py` separates the voices on those clips.
    #:
    #: EMPTY BY DEFAULT, on purpose. This writes the owner's own call audio to
    #: disk, and that is not something an app should start doing because nobody
    #: thought to type a flag.
    parser.add_argument('--save-voice-clips', default='', metavar='DIR',
                        help='with --speakers-cheap: keep the audio where two '
                             'voices overlapped, so the voices can be '
                             'separated LATER (needs '
                             '_main/multivoice-offline.py). Empty = keep '
                             'nothing')
    parser.add_argument('--dump-dom', action='store_true',
                        help="measure the panel with the Electron arm's probe "
                             'and exit')
    parser.add_argument('--dump-dom-wait', type=float, default=0.0,
                        help='seconds to wait before the --dump-dom probe, so '
                             'the dump can measure a state that only exists '
                             'after the worker has run (0 = measure at startup, '
                             'unchanged)')
    parser.add_argument('--probe-v2', type=float, default=0.0, metavar='SECONDS',
                        help='after SECONDS, run the panel-v2 acceptance probe: '
                             '(two sections, live caption, history on disk, '
                             'search) and exit 0 GREEN / 3 RED')
    #: MEASUREMENT: the stats channel, read out of the panel's OWN DOM.
    #: Suppressed: a probe, not a user flag.
    parser.add_argument('--probe-stats', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--probe-stats-wait', type=float, default=8.0,
                        help=argparse.SUPPRESS)
    parser.add_argument('--opaque', action='store_true',
                        help='force an opaque window, to A/B transparency')
    parser.add_argument('--selftest', action='store_true',
                        help='prove the hotkey registers and toggles, then exit')
    parser.add_argument('--memory', action='store_true',
                        help='print the host RSS in MB')
    parser.add_argument('--memory-wait', type=float, default=0.0,
                        help='seconds to let the page settle before measuring')
    #: Alt+C closes when the owner clicks outside. ON by default (the owner asked
    #: for it); this turns it off for an arm that must not install a mouse hook.
    parser.add_argument('--no-click-outside', action='store_true',
                        help='do not close the panel when clicking outside it')
    #: MEASUREMENT: the three outside-click cases with the panel visible but not
    #: seen (`form.Opacity = 0`), then exit. Never `--show`.
    parser.add_argument('--probe-outside-click', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--probe-edit-mode', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--exit-after', type=float, default=0.0,
                        help='quit on a wall clock, so an acceptance run ends '
                             'by itself')
    parser.add_argument('--no-hot-reload', action='store_true',
                        help='do not watch panel assets / worker sources (this is the default)')
    parser.add_argument('--hot-reload', action='store_true',
                        help='watch panel assets / worker sources and reload in place; a DEVELOPMENT feature, OFF by default because each reload re-parses the panel and re-creates the renderer on the machine the owner is using')
    #: The deferred-asset gate's CONTROL ARM. With it the shell registers no
    #: WebResourceRequested filter and every deferred URL reaches the disk, which
    #: is byte-for-byte today's behaviour. The measurement harness runs the gate
    #: arm and this arm and diffs the two; if they do not differ, the gate is
    #: VACUOUS and the harness must report that instead of a saving.
    parser.add_argument('--no-lazy', action='store_true',
                        help='serve every panel asset normally (no deferral)')
    parser.add_argument('--probe-reload', action='store_true',
                        help='prove the worker hot-reload guard: touch the '
                             'worker file while a capture is open and print '
                             'the restart count (starts no window)')
    parser.add_argument('--log', default=None, help='mirror stdout here')
    #: The notification-area icon (the ONLY Quit, since the owner asked for the
    #: panel's button to go). It is ON by default; this turns it off for an arm
    #: that must not touch the owner's notification area at all.
    parser.add_argument('--no-tray', action='store_true',
                        help='start without the notification-area icon')
    #: O vigia que se senta de novo (ver `shell_relaunch.arm`). LIGADO por omissao:
    #: o dono nao quer aprovar nada para ver um codigo novo no ecra (2026-10-30).
    #: Desliga-se com esta bandeira ou com `SOTTO_NO_SELF_RELAUNCH=1`, e as duas dizem
    #: no log PORQUE foi desligado.
    parser.add_argument('--no-self-relaunch', action='store_true',
                        help='never relaunch this app by itself when its code changes')
    #: The single-instance mutex name. The default is the shipped one; a private
    #: name is how a probe proves the lock is RELEASED on Quit without colliding
    #: with the owner's own running app (which holds the default).
    parser.add_argument('--mutex-name', default=DEFAULT_MUTEX_NAME,
                        help=argparse.SUPPRESS)
    #: run.cmd's pre-flight switch. SUPPRESS keeps it out of `--help`, so the
    #: usage printed by `run.cmd --help` is byte-for-byte the one it printed
    #: before this mode existed (it is the wrapper's, not the user's, flag).
    parser.add_argument('--check-args', action='store_true',
                        help=argparse.SUPPRESS)
    #: run.cmd's readiness handshake (gap G3). The wrapper `start`s the app
    #: DETACHED, so a hang after the spawn is invisible to it; it hands a FRESH
    #: path here and waits for it, bounded (the file appearing is "the app came
    #: up", the bound expiring is a HANG). SUPPRESS: it is the wrapper's flag,
    #: not a user flag, and `--help` must stay byte-for-byte as it was.
    parser.add_argument('--ready-file', default=None,
                        help=argparse.SUPPRESS)
    #: run.cmd's bounded readiness poll (the other half of G3). A MODE: it takes
    #: a path, waits for the app to touch it, and exits 0/4. It is the wrapper's
    #: flag, so it stays out of `--help`.
    parser.add_argument('--wait-ready', default=None, metavar='PATH',
                        help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def pywebview_version():
    try:
        import importlib.metadata as md
        return md.version('pywebview')
    except Exception:
        return 'unknown'


def _preflight_refuse(args, message: str, code: int) -> int:
    """Record a pre-flight refusal where the caller can still see it, and return
    the code the wrapper passes on.

    The pre-flight runs under pythonw.exe, whose stdout/stderr are None, so the
    interpreter's own message is discarded and the exit code is the whole
    contract the wrapper can read. The reason is mirrored to `--log` when the
    caller gave one (appending, like every other line) and printed when there is
    a console (a direct run). This opens no window and starts nothing.
    """
    if getattr(args, 'log', None):
        _open_log(args.log)
    log(message)
    return code


def probe_reload():
    """O instrumento do reload, montado com as pecas DESTE modulo.

    Ver `selftest_instrument.probe_reload`: a politica e as duas constantes
    viajam por parametro para o instrumento nao importar o shell de volta.
    """
    return selftest_instrument.probe_reload(
        WorkerReloadPolicy=WorkerReloadPolicy,
        WORKER_RELOAD_MIN_INTERVAL_MS=WORKER_RELOAD_MIN_INTERVAL_MS,
        WORKER_RELOAD_DEBOUNCE_MS=WORKER_RELOAD_DEBOUNCE_MS)


#: ── THE WEBVIEW2 COMPOSITION KNOBS, AND WHY THEY ARE SET HERE ────────────────
#:
#: O BRANCO entre o HWND mapeado e o primeiro pixel NAO e' CSS nosso: o pywebview usa
#: WINDOWED hosting (um `Chrome_WidgetWin` filho criado por `CreateCoreWebView2Controller`)
#: e o DWM compoe esse filho na sua propria camada -- logo `WS_EX_LAYERED`/`LWA_COLORKEY`
#: no pai nao chegam ao conteudo. Documentado e medido: MicrosoftEdge/WebView2Feedback#118
#: (`LWA_COLORKEY` "did not work", `LWA_ALPHA` sim; a resposta da Microsoft foi "no plans to
#: further support keying out a specific color"), unoplatform/uno#22694 (o mesmo estouro em
#: show/hide/recreate como "a fundamental limitation of the Win32 HWND composition model")
#: e a doc do `DefaultBackgroundColor` (o default e' BRANCO, e "just setting the color by
#: property can still leave the app with a white flicker ... setting the color via
#: environment variable solves this issue").
#:
#: Por isso as duas constantes abaixo sao ENV VARS -- a unica forma honrada no PRIMEIRO
#: frame -- e tem de ser postas ANTES de o ambiente WebView2 existir, ou seja antes de
#: `webview.start()`. O pywebview ja' poe `DefaultBackgroundColor = Color.Transparent`
#: (`webview/platforms/edgechromium.py:113-114`), o que cobre a propriedade e nao o frame 1.

WEBVIEW2_BG_TRANSPARENT = '00000000'          # AA=00 → fully transparent
#: Window-to-Visual hosting: "a developer experience nearly identical to Windowed
#: hosting, but ... content is output to a Visual that is hosted in an HWND
#: rather than to the window directly". It sounds like the fix for the white.
#: It is NOT, on this box — MEASURED 2026-10-09, both arms, same shell, same
#: Alt+C, same child-window census:
#:
#:   windowed (this default)        child vis=True   composited DARK 100%
#:   window_to_visual (forced)      child vis=True   composited LIGHT 100%
#:
#: So the hosting mode is OFF by default and the knob exists only so a future
#: runtime can be A/B'd on this box without editing this file. The white was
#: never a hosting-mode problem; it was `Chrome_WidgetWin_0` left hidden, which
#: `ensure_webview_shown` fixes on the windowed path.
WEBVIEW2_WINDOW_TO_VISUAL = 'COREWEBVIEW2_HOSTING_MODE_WINDOW_TO_VISUAL'
WEBVIEW2_WINDOW_TO_VISUAL_DEFAULT = False


def apply_webview2_environment(argv=None):
    """Set the two knobs above, FIRST-COME-FIRST-KEPT, and report what happened.

    An explicit environment value ALWAYS wins over ours, so an operator who
    measured a different answer on this box can override us without editing
    this file. `SOTTO_WEBVIEW_WINDOW_TO_VISUAL=0` is the escape hatch for the
    one knob that changes behaviour rather than only removing a flash: if the
    runtime on some host rejects the mode, the app must still start, and it must
    say in the log which mode it actually asked for.

    Returns a dict, so the caller logs one line and a test can assert the pair
    without a WebView2 being present.
    """
    args = argv or sys.argv[1:]
    # There is no `--webview-window-to-visual` flag: the switch is the
    # environment variable, read here so the decision lives in ONE place.
    wanted = os.environ.get('SOTTO_WEBVIEW_WINDOW_TO_VISUAL', '').strip().lower()
    if wanted in ('0', 'false', 'no', 'off', 'windowed'):
        use_w2v, why = False, 'SOTTO_WEBVIEW_WINDOW_TO_VISUAL=%s' % wanted
    elif os.environ.get('COREWEBVIEW2_FORCED_HOSTING_MODE'):
        use_w2v = os.environ['COREWEBVIEW2_FORCED_HOSTING_MODE'] == WEBVIEW2_WINDOW_TO_VISUAL
        why = 'COREWEBVIEW2_FORCED_HOSTING_MODE already set to %r' % \
            os.environ['COREWEBVIEW2_FORCED_HOSTING_MODE']
    else:
        use_w2v = WEBVIEW2_WINDOW_TO_VISUAL_DEFAULT
        why = ('shell default (measured: windowed composites DARK, '
               'window_to_visual composites LIGHT on this box)'
               if not use_w2v else 'shell default')

    had_bg = 'WEBVIEW2_DEFAULT_BACKGROUND_COLOR' in os.environ
    if not had_bg:
        os.environ['WEBVIEW2_DEFAULT_BACKGROUND_COLOR'] = WEBVIEW2_BG_TRANSPARENT

    had_mode = 'COREWEBVIEW2_FORCED_HOSTING_MODE' in os.environ
    if use_w2v and not had_mode:
        os.environ['COREWEBVIEW2_FORCED_HOSTING_MODE'] = WEBVIEW2_WINDOW_TO_VISUAL

    return {
        'bg': WEBVIEW2_BG_TRANSPARENT, 'bg_overridden': had_bg,
        'window_to_visual': use_w2v, 'reason': why,
        'mode_overridden': had_mode,
    }


def _start_startup_stack_watch(args):
    """Se o arranque nao chegar ao READY, diz ONDE esta' preso.

    MEDIDO 2026-11-03 (duas vezes seguidas, 03:04:48 e 03:06:23): a app subia
    ate' `PANEL_SHOW_REFUSED count=2` e parava -- nenhuma linha depois, nenhum
    despejo de pilhas, e o `run.cmd` respondia `HANG rc=4 by=run.cmd-readiness`.
    O vigia de UI so' existe depois do arranque, e a partir desta pane nao se
    pode anexar (`py-spy`: acesso negado -- a app corre acima dela), logo um
    arranque preso era indiagnosticavel. Este thread e' a resposta: 15 s e 30 s
    depois do processo nascer, se o ficheiro de READY nao existir, despeja a
    pilha de TODAS as threads no log. Custa um sleep quando corre bem.
    """
    path = getattr(args, 'ready_file', None)
    if not path or getattr(args, 'wait_ready', None):
        return
    import faulthandler

    def loop():
        started = time.monotonic()
        for at in (15.0, 30.0, 60.0):
            nap = at - (time.monotonic() - started)
            if nap > 0:
                time.sleep(nap)
            if startup_is_ready(path):
                return
            try:
                log('STARTUP_NOT_READY s=%.0f threads=%d'
                    % (at, threading.active_count()))
                # O DESPEJO TEM DE IR PARA UM FICHEIRO (2026-11-03). Uma shell
                # lancada por `pythonw` tem `sys.stderr is None`, e o
                # `dump_traceback()` sem `file=` nao escreve NADA: medido, tres
                # `STARTUP_NOT_READY` (15/30/60 s) sem uma linha de stack.
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       '..', '..', '_main',
                                       '_startup-stacks.log'), 'a') as _fh:
                    _fh.write('\n=== STARTUP_NOT_READY s=%.0f pid=%d ===\n'
                              % (at, os.getpid()))
                    faulthandler.dump_traceback(file=_fh, all_threads=True)
            except Exception:             # noqa: BLE001
                return

    threading.Thread(target=loop, name='sotto-startup-watch',
                     daemon=True).start()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    _start_startup_stack_watch(args)

    # O PRAZO DE UMA SONDA E' DO PROCESSO (2026-11-03, MEDIDO DUAS VEZES).
    # `--exit-after` era armado no despacho de probes, ou seja DEPOIS do
    # arranque inteiro; dois caminhos de arranque nao chegam la': um
    # `run_selftest()` que nao volta (pid 35348, 1 h 50 min vivo, 245 MB) e um
    # arranque que morre em `WEBVIEW2_INIT_FAILED` (reproduzido hoje numa
    # instancia `--exit-after 8`, que continuou viva). Uma sonda que nao morre
    # e' um recurso emprestado para sempre. Aqui e' o primeiro instante em que
    # as flags existem: o relogio comeca, e o resto do arranque pode falhar a'
    # vontade sem deixar um processo a viver.
    if getattr(args, 'exit_after', 0):
        def _hard_exit():
            os._exit(0)
        threading.Timer(float(args.exit_after) + 15.0, _hard_exit).start()
        threading.Timer(float(args.exit_after), _hard_exit).start()

    # ── THE ENVIRONMENT IS SET HERE, BEFORE ANY WINDOW EXISTS ────────────────
    # `WEBVIEW2_DEFAULT_BACKGROUND_COLOR` is read by WebView2 the moment its
    # environment is created, and the environment is created by
    # `EnsureCoreWebView2Async`, which `create_window()` reaches at line 6188 —
    # ~50 lines BEFORE `webview.start()`. An earlier revision set the two knobs
    # immediately before `start()`, i.e. AFTER the environment already existed,
    # so they were silently ignored for that run. Microsoft's own note is the
    # reason the variable form matters at all: "just setting the color by
    # property can still leave the app with a white flicker before the
    # DefaultBackgroundColor property takes effect. Setting the color via
    # environment variable solves this issue" — but only if it is set first.
    wv = apply_webview2_environment()
    log('WEBVIEW2_ENV background=%s%s window_to_visual=%s reason=%s%s'
        % (wv['bg'], ' (env already set)' if wv['bg_overridden'] else '',
           str(wv['window_to_visual']).lower(), wv['reason'],
           ' (env already set)' if wv['mode_overridden'] else ''))

    if args.wait_ready:
        # ---- run.cmd's bounded readiness poll: the other half of G3 ---------
        # `run.cmd` `start`s the app DETACHED, so it can never see a hang after
        # the spawn -- measured 2026-10-06 a launch logged STAGING_LOADED and
        # stopped, and the wrapper still answered 0 (launch-entry.md §3/§4). It
        # hands a FRESH path to the app (`--ready-file`) and calls THIS mode,
        # which waits, bounded, for the app to touch it: 0 = up, 4 = HANG.
        # pythonw keeps it windowless; nothing is opened, logged or started.
        try:
            bound = float(os.environ.get('SOTTO_READY_BOUND', '30'))
        except ValueError:
            bound = 30.0
        return wait_ready_file(args.wait_ready, bound)

    if args.check_args:
        # ---- run.cmd's PRE-FLIGHT: the one mode that STARTS NOTHING ----------
        # `start` in run.cmd detaches the app, so the wrapper never sees the
        # interpreter's status. Measured 2026-10-06 (lane SottoRunCmdEntry):
        # `run.cmd --bogus-flag` returned rc=0 with no log bytes, no shell line
        # and no process -- argparse exits 2 on pythonw.exe, whose stdout is
        # None, and `start` reports only its OWN success, so a rejected flag
        # answered as success. The wrapper runs THIS first and spawns the app
        # only when it returns 0: the list is validated by the shell's own
        # parser, one flag table, and a second copy in batch cannot drift.
        #
        # Reaching here means parse_args ACCEPTED the list (a rejected one exits
        # 2 from parse_args above, before this line -- that status is the one
        # the wrapper passes on).
        #
        # G1: the panel must be present. This return USED to happen before the
        #     panel check further down (:2483), so with app/panel/panel.html
        #     missing `run.cmd` exited 0 while a real launch exited 3 -- the
        #     same "failure answering as success" the pre-flight exists to
        #     close (docs/audit/launch-entry.md, §2 G1).
        if not os.path.exists(PANEL_HTML):
            return _preflight_refuse(args,
                                     f'PANEL_MISSING path={PANEL_HTML}', 3)
        # G2: `import webview` is late (the WinForms assemblies it loads must not
        #     be imported before the UI loop exists), so an ImportError surfaced
        #     as the process' rc=1 only AFTER `run.cmd` had already answered 0.
        #     Import it HERE, where the wrapper is still listening, and pass the
        #     same status a real launch would exit with.
        try:
            import webview  # noqa: F401
        except Exception as exc:  # noqa: BLE001 -- any import failure is G2
            return _preflight_refuse(
                args,
                f'PYWEBVIEW_IMPORT_FAILED {type(exc).__name__}: {exc}', 1)
        return 0

    if args.probe_reload:
        # ---- the reload-guard proof: starts NO window and NO worker ----------
        # It only touches real files and drives the real watcher + policy, so it
        # is safe under pythonw and prints its own verdict to the log/console.
        return probe_reload()

    _open_log(args.log)
    log(f'shell=webview2 pywebview={pywebview_version()} '
        f'python={sys.version.split()[0]} pid={os.getpid()}')
    _aumid_set = set_process_app_user_model_id()
    _aumid = process_app_user_model_id()
    log(f"APP_USER_MODEL_ID value={_aumid['value']} ok={str(_aumid['ok']).lower()} "
        f"hr={_aumid['hr']} set={str(_aumid_set['set']).lower()} "
        f"set_hr={_aumid_set['hr']} image={sys.executable}")

    if not os.path.exists(PANEL_HTML):
        log(f'PANEL_MISSING path={PANEL_HTML}')
        return 3

    # ── A SILENT DEATH IS UNFALSIFIABLE (measured 2026-10-14) ────────────────
    # A second launch (pid 18772, 20:16:36.257) logged its banner and the
    # APP_USER_MODEL_ID line and then NOTHING, ever: no SINGLE_INSTANCE line,
    # no window, no hotkey, no worker, gone by the next process census. Every
    # step in this stretch logs its own failure EXCEPT an exception, and under
    # pythonw.exe an exception has nowhere to print. The owner's "abrir o sotto
    # causa travamento" needs the receipt, not a guess: name the stage reached,
    # and catch the exception so the next occurrence exits 3 WITH a log line
    # instead of vanishing between two lines.
    log(f'SHELL_STARTUP_STAGE pid={os.getpid()} stage=pre-lock '
        f'python={args.python or default_python()} '
        f'panel={str(os.path.exists(PANEL_HTML)).lower()}')
    # ── A IDENTIDADE DO CODIGO QUE ESTE PROCESSO VAI CORRER (2026-10-30) ────
    # Medido na pele do dono: ele carregou Alt+C numa instancia de 01:12:39
    # e o log dessa instancia escrevia `HOTKEY_SINGLE` -- uma etiqueta que o
    # fonte JA' NAO SABE ESCREVER (zero ocorrencias). O gesto novo estava no
    # disco e a app a correr era a de antes; quatro oraculos verdes nao viam
    # nada, porque julgam FICHEIROS e ele carrega num PROCESSO.
    #
    # Esta linha e' o unico fio entre os dois: o processo diz, ao arrancar, o
    # sha256 exacto do codigo que carregou. `_main/live-code-freshness-oracle.py`
    # compara-o com o do disco e responde STALE/FRESH -- sem ele, a unica forma
    # de saber a idade do que o dono carrega e' comparar etiquetas de log a mao.
    log(f'SHELL_CODE_ID %s' % code_identity())
    args.python = args.python or default_python()

    # ── the three autostart modes print and exit: no window, no worker ───────
    # They are here (and not before `_open_log`) so the receipt of what was
    # written to the registry lands in the same run log as everything else.
    if args.install_autostart:
        return autostart_install()
    if args.uninstall_autostart:
        return autostart_uninstall()
    if args.autostart_status:
        return autostart_status()

    # ── ONE SHELL AT A TIME — THE LOCK IS NEVER SKIPPED ──────────────────────
    # The DEFAULT mutex (`Local\SottoShell`) belongs to the owner's APP and is
    # what makes it single-instance: a second app is refused HERE, before any
    # window, tray icon or worker exists. It also protects the GLOBAL HOTKEY,
    # the one genuinely exclusive resource (a second shell cannot register it:
    # `RegisterHotKey` → 1409, and the owner's Alt+C then answers the first,
    # possibly stale, instance).
    #
    # A MEASUREMENT run must not be refused by the APP's lock — refusing probes
    # while the owner's app is up is exactly what bricked every instrument in
    # the repo once (measured 2026-10-07: `SINGLE_INSTANCE already_running=true`
    # on a `--dump-dom` dump). So a measurement launch takes a DERIVED lock of
    # its own instead of taking NOTHING: the app stays single-instance, and two
    # IDENTICAL probe launches (same flags) can no longer stack panels, tray
    # icons and worker model loads — the owner's report (several Sotto icons,
    # the PC freezing). Different probes carry different flags and so different
    # lock names; they still run side by side. The HOTKEY is the only thing a
    # measurement run skips.
    lock_name = args.mutex_name
    lock_excuse = None
    # A PRIVATE mutex name is not the one the owner's app holds, so there is
    # nothing to collide with and taking it is safe even in a measurement run —
    # which is what makes "the Quit releases the lock" a measurement instead of
    # an argument from OS behaviour. It is taken as-is, and it is NOT excused.
    if args.mutex_name != DEFAULT_MUTEX_NAME:
        pass
    elif args.no_hotkey:
        lock_excuse = '--no-hotkey'
    elif args.dump_dom:
        lock_excuse = '--dump-dom'
    elif args.selftest:
        lock_excuse = '--selftest'
    elif args.memory:
        lock_excuse = '--memory'
    elif args.probe_v2 > 0:
        lock_excuse = '--probe-v2'
    if lock_excuse:
        lock_name = measurement_lock_name(args)
        if not take_single_instance_lock(lock_name):
            log(f'SINGLE_INSTANCE_MEASURE_BUSY name={lock_name} '
                f'reason={lock_excuse} — an identical measurement launch is '
                'already running; not stacking another one')
            return 0
        log(f'SINGLE_INSTANCE_SKIPPED reason={lock_excuse} '
            f'default={DEFAULT_MUTEX_NAME} took={lock_name} '
            '(the DEFAULT lock is left to the app; a private measurement lock '
            'is TAKEN and the hotkey is skipped)')
    elif not take_single_instance_lock(lock_name):
        warn('Sotto is already running in this session: this launch will not show '
             'anything. Press Alt+C for the running panel, or close it with the '
             'panel\'s Quit button before starting another one.')
        return 0

    # A MEASUREMENT LAUNCH MUST NOT FIGHT THE OWNER'S APP FOR Alt+C. The line
    # above PROMISES exactly that ("a measurement run registers no global
    # hotkey") and, until 2026-10-11, only promised it: --dump-dom, --selftest,
    # --memory and --probe-v2 skipped the LOCK and still armed the chain, so a
    # probe started while the owner's app was up lost all four keys and put a
    # MODAL messagebox on the owner's screen. Measured, same box, same revision:
    # the shell logged HOTKEY_UNAVAILABLE alert=messagebox tried=[...] and then
    # never reached STAGING_SEEN -- it hung until it was killed
    # (I:\cc-tmp\wedge-fresh.log, 4,510 B, 42 lines, last line PRELOAD_INSTALLED;
    # its healthy twin I:\cc-tmp\try1.log, SAME flags plus --no-hotkey, reaches
    # RECEIVER_READY and SHELL_EXIT in under 40 s). A private --mutex-name is NOT
    # coerced: that run skips no lock and may legitimately measure the hotkey.
    # A ARVORE MORRE COM A SHELL -- OU FICA A PAGAR (2026-11-04, MEDIDO).
    # Censo desta maquina, app viva: **25** processos `msedgewebview2.exe` em
    # **750 MB**, de **QUATRO** arvores -- tres delas de instancias que ja' nao
    # existiam, cada uma com o seu browser+gpu+renderer+utility. Um shell morto
    # a` force nao leva os filhos consigo: o Windows nao faz isso por omissao.
    # Um JOB OBJECT com KILL_ON_JOB_CLOSE e' o mecanismo que o faz pelo sistema,
    # sem depender de nenhum caminho de saida do Python (que nao corre num kill).
    _hold_kill_on_close_job()

    hotkey_off = '--no-hotkey' if args.no_hotkey else None
    if lock_excuse and not args.no_hotkey:
        hotkey_off = f'measurement-flag({lock_excuse})'
        args.no_hotkey = True
    shell = SottoShell(args)
    shell.create_window()

    # The hotkey lives on its own thread with its own message queue, so it is
    # registered before the UI loop exists and cannot be starved by it.
    # `--no-hotkey` is for MEASUREMENT runs: a probe that takes Alt+C steals the
    # one control the app has, and answers the owner's keypress with its own
    # panel (measured: two PANEL_SHOWN reason=hotkey lines during a probe run).
    if args.no_hotkey:
        log(f'HOTKEY_DISABLED reason={hotkey_off or "--no-hotkey"}')
    else:
        # The chain lives in `arm_hotkey`: the requested key, then
        # `HOTKEY_FALLBACKS`, then — if every one is owned by another program —
        # a dialog on a daemon thread, because a hidden app with a dead hotkey
        # and no message is indistinguishable from a broken app.
        shell.hotkey = arm_hotkey(shell, args.hotkey)
        # A LEGENDA ARRANCA AQUI, NAO DEPOIS DO WEBVIEW2 (2026-11-03):
        # o overlay e' nativo e o worker e' outro processo -- nenhum dos dois
        # precisa da pagina do painel para existir.
        try:
            shell.start_caption_pipeline('pre-webview')
        except Exception as exc:          # noqa: BLE001
            warn('caption pipeline could not start early: %r' % (exc,))
        # O WEBVIEW2 ESPERA O MODELO, NAO O CONTRARIO (2026-11-03, MEDIDO).
        # Lançar o WebView2 ao mesmo tempo que o worker carrega faz o
        # worker pagar a factura: medido nesta sessao, o modelo ficou
        # pronto em `load_s=11.99` e o shell so' viu a linha 61 s depois
        # (`BRIDGE_LOAD_MS ms=61297`), porque as threads do shell nao
        # corriam enquanto o WebView2 arrancava (722 processos, 92,5% de
        # commit). A legenda e' o produto; o painel e' opcional e ja'
        # arrancava escondido. Entao: espera o modelo, com tecto, e so'
        # depois entrega a maquina ao WebView2. Tecto obrigatorio -- uma
        # app sem painel e' o defeito que se estava a evitar.
        try:
            # DEFAULT ZERO (2026-11-03, MEDIDO): o `run.cmd` tem um portao de
            # prontidao e chamou `HANG rc=4 by=run.cmd-readiness` a um arranque
            # que so' estava a espERAR pelo modelo antes de abrir a pagina -- a
            # app ficou sem painel e o dono sem nada. A espera nao comprou nada
            # medivel (o modelo demora o mesmo; o WebView2 nao e' o culpado),
            # logo fica opt-in para quem a quiser medir.
            _wait_model = float(os.environ.get('SOTTO_WEBVIEW_AFTER_LOAD_S',
                                               '0'))
        except ValueError:
            _wait_model = 25.0
        if _wait_model > 0 and getattr(shell, 'bridge', None) is not None:
            _t0 = time.monotonic()
            _loaded = False
            while time.monotonic() - _t0 < _wait_model:
                if getattr(shell.bridge, 'loaded', False):
                    _loaded = True
                    break
                time.sleep(0.05)
            log('SHELL_WEBVIEW_AFTER_LOAD loaded=%s waited_ms=%d '
                'ceiling_ms=%d'
                % (str(_loaded).lower(),
                   round((time.monotonic() - _t0) * 1000.0),
                   round(_wait_model * 1000.0)))

    # HOT RELOAD IS OFF BY DEFAULT, AND IT WAS ON -- WHICH IS THE FREEZE. MEASURED
    # 2026-10-15 on the owner own log: `HOT_RELOAD_EVENT kind=panel file=panel.css`
    # -> `HOT_RELOAD_FLUSH` -> `HOT_RELOAD_PANEL_DONE reload=10` -> `HOT_RELOAD_APPLIED`,
    # five times in seven minutes, each one at the exact second a panel asset was
    # written. And the reload is not cheap: the panel re-parses thirteen scripts,
    # re-builds its DOM and re-creates the WebView2 renderer, ON THE MACHINE THE OWNER
    # IS USING. He said it six ways over three days -- *"quando sotto abre ou fecha, o
    # pc trava"*, *"abrir ou fechar o sotto causa travamento no meu pc"*, *"por que
    # fechar o sotto ainda trava meu sistema?"* -- and the steady state was never the
    # problem: measured the same day, the whole app is 266 MB and 4.2 percent of one
    # core, with the worker transcribing. The spike is the RELOAD.
    #
    # THIS IS A DEVELOPMENT FEATURE AND IT WAS ARMED IN PRODUCTION. `run.cmd` passes no
    # flag, so every edit to `panel.html`, `panel.css` or `panel.js` -- by a lane, by a
    # generator run, by anyone -- reached into the owner running app and reloaded his
    # panel. A user of this program has no editor open on it and will never want that.
    #
    # SO THE DEFAULT FLIPS: `--hot-reload` opts IN, and `--no-hot-reload` still works so
    # every existing script and oracle that passes it keeps its meaning. The banner line
    # names the reason either way, so the log still says which it was.
    if args.hot_reload:
        if not shell.start_hot_reload():
            warn('hot reload could not arm its watchers; the app still runs')
    elif args.no_hot_reload:
        log('HOT_RELOAD_DISABLED reason=--no-hot-reload')
    else:
        log('HOT_RELOAD_DISABLED reason=off-by-default (a development feature; pass '
            '--hot-reload to arm it)')

    # O RELANCAMENTO PROPRIO. A app vigia o PROPRIO codigo e, quando ele muda, senta-se
    # de novo pela tarefa do dono (`SottoRelaunch`). A conclusao de 2026-10-30 ("e' a
    # UNICA largada capaz") foi REFUTADA: o token de um processo `high` emprestado
    # (`_main/launch-as-token.py`) larga um filho `high` que executa e ganha a mutex.
    #
    # PORQUE ELE NAO DANCA: verbatim, 2026-10-30 -- *"vai dar launch sozinho no sotto. e
    # eu nao quero que essa merda precise de mim aprovando nada"*. A alternativa era
    # pedir-lhe para fechar e abrir a app, e isso e' o que ele recusou.
    #
    # ORDEM DAS GUARDAS: so' relanca ocioso (sem legenda no ecra), depois de FLOOR_S de
    # vida, com a mudanca quieta STABLE_S, e no maximo CAP_PER_HOUR por hora. Uma
    # excepcao no vigia NUNCA custa o arranque (a mesma regra do hot reload).
    if args.no_self_relaunch or os.environ.get('SOTTO_NO_SELF_RELAUNCH') == '1':
        log('SHELL_RELAUNCH_DISABLED reason=%s' %
            ('--no-self-relaunch' if args.no_self_relaunch else 'env'))
    else:
        try:
            import shell_relaunch
            shell_relaunch.arm(shell, log)
        except Exception as exc:  # noqa: BLE001 - nao pode custar o arranque
            warn('self relaunch could not arm its watcher: %r' % (exc,))

    # THE TRAY. Last of the three, for the same reason as the others: it must not
    # be able to cost the app its start, and it is the only home the Quit has.
    if args.no_tray:
        log('TRAY_DISABLED reason=--no-tray')
    else:
        shell.start_tray()
    # The outside-click watcher, last for the same reason as the rest: a hook that
    # fails to install must not cost the app its start.
    if args.no_click_outside:
        log('OUTSIDE_CLICK_DISABLED reason=--no-click-outside')
    else:
        shell.start_click_watcher()

    if args.memory and args.memory_wait:
        threading.Timer(args.memory_wait, shell.run_memory).start()

    import webview  # noqa: F401 -- imported for its side effects only; the real
    # call is `webview.start(...)` below. The environment was already applied at
    # the top of main(), before `create_window()` built the WebView2: the knobs
    # are read when the environment is created, not when the loop starts.
    # `start(icon=...)` stores it in `_state['icon']`, which the WinForms backend
    # reads when it builds the form (`platforms/winforms.py:243-244`) — despite
    # its own docstring claiming the parameter is "Supported only on GTK/QT"
    # (`webview/__init__.py:205`). Without it the backend copies the icon out of
    # `sys.executable`, i.e. `pythonw.exe`, i.e. THE PYTHON ICON, which is the
    # owner's report. `apply_window_icon` (from `_on_before_show`) re-applies it
    # with an explicit `WM_SETICON`, ICON_SMALL2 included.
    # PERFIL PERSISTENTE SO' PARA A APP, NUNCA PARA UMA SONDA. Uma sonda
    # (`--dump-dom`/`--selftest`/`--memory`/`--probe-v2`/`--no-hotkey`, ou uma
    # mutex privada) larga uma SEGUNDA instancia ao lado da do dono; dois
    # processos nao partilham o mesmo `EBWebView` (o segundo nao arranca o
    # WebView2). Por isso o perfil e' da APP e o efemero fica nas sondas.
    if not lock_excuse:
        def _sweep():
            try:
                dirs, freed = sweep_stale_webview_profiles()
                log('WEBVIEW2_PROFILE_SWEEP dirs=%d mb=%.1f'
                    % (dirs, freed / (1024.0 * 1024.0)))
            except Exception as exc:  # noqa: BLE001
                log('WEBVIEW2_PROFILE_SWEEP_FAILED error=%r' % (exc,))
        threading.Thread(target=_sweep, name='sotto-profile-sweep',
                         daemon=True).start()
    # PERFIL POR LARGADA, E O LIXO VARRIDO (2026-11-03, MEDIDO). Um perfil
    # PARTILHADO entre largadas foi tentado e medido no mesmo dia: com o
    # processo anterior ainda a morrer, o WebView2 do novo arranque bate em
    # `0x800700AA Recurso solicitado em uso` e a app sobe SEM PAGINA
    # (`WEBVIEW2_INIT_FAILED`, medido 04:31:48) -- e os `msedgewebview2.exe`
    # sobrevivem ao kill do shell, portanto o hazard nao desaparece sozinho.
    # E nao pagava: o perfil a quente nao mudou os 25 s do painel (03:59 e
    # 04:28 deram o mesmo numero). Fica o perfil efemero do pywebview, e o que
    # se ganha e' a VARREDURA: cada largada morta deixava 4-67 MB em
    # `%TEMP%\tmp*\EBWebView` para sempre (centenas deles nesta maquina).
    log('WEBVIEW2_PROFILE ephemeral reason=%s'
        % (lock_excuse or ('mutex:' + str(args.mutex_name))
           if (lock_excuse or args.mutex_name != DEFAULT_MUTEX_NAME)
           else 'per-launch'))
    webview.start(icon=SOTTO_ICON)
    return shell._exit_code


if __name__ == '__main__':
    sys.exit(main())