#!/usr/bin/env python
# NO-BUG: instrumento da resposta do Ctrl+Space com o ecra vazio e da idade do
# audio na pintura ao vivo (2026-11-11); nao corrige o produto, julga-o.
"""O CTRL+SPACE COM O ECRA VAZIO, E O AUDIO VELHO NA JANELA AO VIVO.

O DONO, verbatim: *"meu ctrl space nao fez nada assim que abri o sotto e vi ele
no icone da bandeja"*. MEDIDO no log dele (pid 49180):

    17:34:26.599  HOTKEY_PRESSED count=1
    17:34:26.619  LIVE_ENABLED on=true wanted=true        <- 20 ms, o gesto esta' certo
    ...            NADA no ecra ...
    17:36:02.422  EXTERNAL_CAPTION_SENT text="So, let's pour ourselves..."  <- 95,8 s

O aviso que existia (`model-loading` -> `carregando modelo…`) e' um EVENTO
unico, disparado as 17:34:26.5 enquanto `_caption_wanted` ainda era False: quando
o dono ligou, o evento ja' tinha passado e o ESTADO nunca foi lido.

A SEGUNDA METADE (mesma sessao): as 17:46:05.822 o shell pintou
`CAPTION_IN start=381.84 final=true tap_ms=None` -- audio de 17:41:04.7, 301 s
antes -- como se fosse ao vivo, e `tap_ms=None` nao deixava nada no shell saber.

O QUE ESTE ORACULO JULGA (9 arms, todas executam os METODOS REAIS do shell
extraidos por `ast` do ficheiro que esta' no disco, com um overlay e uma ponte
falsos):

  A1  ligar-com-ecra-vazio-diz-o-que-falta      <= 200 ms, `CAPTION_STATUS_SHOWN`
  A2  player-e-dono-da-superficie               nada pinta (o defeito de 2026-11-04)
  A3  a-primeira-legenda-verdadeira-retira      o texto de estado sai do ecra
  A4  sem-facto-nenhum-nada-pinta               estado desconhecido -> silencio
  A5  o-bloqueio-muda-e-o-texto-muda          1 linha por episodio, razao nova
  A6  a-testemunha-da-superficie               `CAPTION_PAINT_SURFACE src=player`
  A7  audio-velho-nao-pinta-mas-nao-se-perde  `LIVE_PAINT_REFUSED`, 1/episodio
  A8  audio-fresco-pinta-e-diz-a-superficie    `src=asr` e o texto no ecra
  A9  player-dono-nao-recebe-linha-velha      nenhum pixel do ASR em cima do player
  A10 desligar-responde                       `off` no ecra, 1 linha, timer leva-o
  A11 arranque-restaurado-fala                `on=true` do ficheiro arma o estado
  A12 as-tres-costuras-chamam-o-estado        `create_window` + 2x `start_worker`
  A13 carimbo-no-futuro-nao-e-fresco          `age_s < -250 ms` -> idade desconhecida
  A14 as-duas-tags-da-rota-vao-ao-log         `ENGINE_VISIBLE_TAGS` + prefixo escrito

`--neg-arm` muta uma COPIA do ficheiro real (14 mutacoes) e exige que cada uma
seja apanhada por pelo menos uma arm: rc=1 com `NEG-ARM: PASS (14/14)`, rc=0 se
uma escapar. Nada aqui abre janela, Chrome, audio ou escreve
`_main/caption-wanted.json`: `_post`/`exec_js_post`/`_caption_wanted_store` sao
costuras de AMBIENTE (o overlay falso e' o destino), nunca regras copiadas.

    python _main\\live-ack-oracle.py
    python _main\\live-ack-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app", "webview")
SHELL = os.path.join(APP, "sotto_webview.py")

if APP not in sys.path:
    sys.path.insert(0, APP)

#: O orcamento do dono: ligar -> um texto honesto no overlay (2026-11-11).
STATUS_BUDGET_MS = 200

#: As funcoes de modulo que as arms executam (as regras puras).
MODULE_FUNCS = (
    "player_track_owns",
    "live_paint_age_s",
    "live_paint_stale",
    "_measured_age",
    "_is_number",
    "caption_status_for",
    "_caption_replay_allowed",
)

#: As constantes de modulo que elas leem.
MODULE_CONSTS = ("PLAYER_TRACK_FRESH_S", "LIVE_PAINT_MAX_AGE_S",
                 "LIVE_PAINT_JITTER_S", "_SKIP", "CAPTION_STATUS_TEXT")

#: As constantes de CLASSE usadas pelo caminho (nao pelo `__init__`).
CLASS_CONSTS = ("CAPTION_STATUS_POLL_S", "CAPTION_BUDGET_MS", "CAPTION_REPLAY_MAX_S",
                # O PRAZO DO ACK DE DESLIGAR (2026-11-12): a arm A10 julga que ele
                # e' MENOR que o do silencio e que nunca e' o do silencio que arma.
                "CAPTION_STATUS_HIDE_S", "CAPTION_IDLE_HIDE_S")

#: Os metodos REAIS que as arms conduzem, na ordem em que a producao os chama.
CLASS_METHODS = (
    "_player_track_state",
    "player_track_owns_surface",
    "_caption_status_state",
    "_caption_status_now",
    "_caption_status_start",
    "_caption_status_stop",
    "_caption_status_tick",
    "_caption_status_queue",
    "_caption_status_withdraw",
    "_caption_status_loop",
    "_caption_off_ack",
    # O PRAZO DO ACK DE DESLIGAR (2026-11-12): `off` deixou de ser apagado pelo
    # temporizador de silencio. O corpo real e' conduzido pela arm A10.
    "_caption_status_hide",
    "_caption_idle_disarm",
    "_blank_caption_window",
    "_paint_caption_status",
    "_caption_paint_wake",
    "_caption_paint_loop",
    "_drain_caption_pending",
    "push_caption_to_window",
    "show_caption_window",
    "_set_live_enabled",
    "external_owner_refuses",
    "on_worker_caption",
)


# -- a leitura do produto ----------------------------------------------------

def read_source(path):
    with io.open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()

#: O PROPRIO DIRECTORIO NO `sys.path`: `_astcache` vive ao lado deste ficheiro, e um
#: import por nome so' resolve quando o directorio do SCRIPT esta' na lista -- verdade
#: ao correr `python _main\x.py`, mentira quando o oraculo e' importado por outro
#: instrumento (a sonda que mediu a distribuicao do max_gap foi assim que caiu num
#: `ModuleNotFoundError`, medido 2026-11-12).
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
#: A ARVORE POR CONTEUDO, LIDA UMA VEZ (2026-11-12, MEDIDO). Cada arm chama
#: `build(src)`, que chama `ast.parse` sobre as 26 774 linhas do shell: medido
#: **0,222 s** por parse, e o `--neg-arm` pagava-o ate' 14 vezes POR MUTANTE
#: (196 pares). Medido depois da cache: o passo `red-as-expected-live-ack` caiu
#: de 61,7 s para o custo de UMA leitura por conteudo. A chave e' o CONTEUDO, nao
#: o caminho, porque cada mutante e' um texto diferente com o mesmo nome de
#: ficheiro -- e a arvore de cada mutante e' parseada exactamente uma vez.
#: A cache vive em `_astcache` desde 2026-11-12: este ficheiro era a QUINTA copia
#: privada da mesma convencao (com `audio-back-detector`, `youtube-cdp-source`,
#: `altc-gesture`, `window-drag` e `gaming-hotkey`).
from _astcache import tree as _tree_of  # noqa: E402


def extract(src, where="<shell>"):
    """O produto -> (metodos reais, funcoes puras, constantes), por `ast`.

    Nao se importa o shell: extraem-se os NOS da arvore e compila-se so' o que
    cada arm conduz. Assim a mutacao de uma copia e' apanhada no corpo do metodo
    mutado, e nao por um efeito colateral do `import` do ficheiro inteiro.
    """
    tree = _tree_of(src, where)
    klass = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SottoShell":
            klass = node
            break
    if klass is None:
        raise SystemExit("EXTRACT-FAIL: SottoShell not found in %s" % where)
    methods = {}
    class_consts = []
    for item in klass.body:
        if isinstance(item, ast.FunctionDef):
            methods[item.name] = item
        elif isinstance(item, ast.Assign):
            names = [t.id for t in item.targets if isinstance(t, ast.Name)]
            if any(name in CLASS_CONSTS for name in names):
                class_consts.append(item)
    funcs = {n.name: n for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name in MODULE_FUNCS}
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in MODULE_CONSTS:
                    consts[target.id] = node
    missing = ([m for m in CLASS_METHODS if m not in methods]
               + [f for f in MODULE_FUNCS if f not in funcs]
               + [c for c in MODULE_CONSTS if c not in consts]
               + [c for c in CLASS_CONSTS
                  if not any(isinstance(t, ast.Name) and t.id == c
                             for node in class_consts for t in node.targets)])
    if missing:
        raise SystemExit("EXTRACT-FAIL: missing %s in %s" % (missing, where))
    return methods, funcs, consts, class_consts


#: O CODIGO COMPILADO POR CONTEUDO (2026-11-12, MEDIDO). O `build` e' chamado
#: ate' 110 vezes num `--neg-arm` (um por braco, por mutante) e o `compile` das
#: 26 774 linhas custa **0,103 s**: medido por `cProfile`, **13,2 s dos 36,3 s**
#: do passo eram esta mesma compilacao do MESMO texto. A cache devolve o object
#: code; o `exec` continua a correr por chamada, porque cada braco precisa do seu
#: `globs` (o `log` e' um `list.append` novo, e as costuras sao por instancia).
_COMPILE_CACHE = {}


def build(src, where="<shell>"):
    """Compila os nos extraidos num `HarnessShell` com costuras de ambiente."""
    methods, funcs, consts, class_consts = extract(src, where)
    body = list(class_consts) + [methods[name] for name in CLASS_METHODS]
    shell_cls = ast.ClassDef(name="HarnessShell",
                             bases=[ast.Name(id="Seams", ctx=ast.Load())],
                             keywords=[], body=body, decorator_list=[])
    module = ast.Module(
        body=list(consts.values()) + list(funcs.values()) + [shell_cls],
        type_ignores=[])
    ast.fix_missing_locations(module)
    lines = []
    globs = dict(Seams.GLOBALS)
    globs["log"] = lines.append
    globs["Seams"] = Seams
    key = (hashlib.sha256(src.encode("utf-8", "replace")).hexdigest(), where)
    code = _COMPILE_CACHE.get(key)
    if code is None:
        code = compile(module, where, "exec")
        _COMPILE_CACHE[key] = code
    exec(code, globs)
    return globs["HarnessShell"], lines


# -- a superficie: o que o overlay RECEBERIA ---------------------------------

class Overlay:
    """A janela da legenda como ESPIA -- guarda cada `set_text` com o instante."""

    def __init__(self):
        self.hwnd = 424242
        self.visible = False
        self._cv = threading.Condition()
        self.calls = []

    def set_work_area(self, *_a, **_k):
        return True

    def set_text(self, text, previous="", instant=False, cue=None, late_s=0.0):
        with self._cv:
            self.calls.append({"text": str(text or ""),
                               "instant": bool(instant),
                               "at": time.monotonic()})
            self._cv.notify_all()
        return True

    def show(self, on=True):
        with self._cv:
            self.visible = bool(on)
            self._cv.notify_all()
        return True

    def hide(self):
        with self._cv:
            self.visible = False
            self._cv.notify_all()
        return True

    def wait_calls(self, count, timeout):
        deadline = time.monotonic() + timeout
        with self._cv:
            while len(self.calls) < count:
                left = deadline - time.monotonic()
                if left <= 0:
                    return False
                self._cv.wait(left)
            return True

    def texts(self):
        with self._cv:
            return [c["text"] for c in self.calls]


class Bridge:
    """A `WorkerBridge` reduzida aos factos que o status e a idade leem."""

    def __init__(self, loaded=False, capturing=False, no_audio=False,
                 state="idle", capture_epoch=0.0, child="child"):
        self.loaded = bool(loaded)
        self.capturing = bool(capturing)
        self.no_audio = bool(no_audio)
        self.state = state
        self.capture_epoch = float(capture_epoch)
        self.child = child


class Watcher:
    """O `ExternalCaptionWatcher` reduzido aos factos do player."""

    def __init__(self, video_id="", rows=(), painted_at=0.0):
        self.yt_video_id = video_id
        self.yt_cdp_rows = list(rows or ())
        self.yt_live_paint_at = float(painted_at)
        self.yt_source_paused = False
        self._yt_cdp_source = None


class TrackThread:
    """O `YouTubeTrackThread` reduzido a' resposta `current(video_id)`."""

    def __init__(self, track=None, video_id=""):
        self._track = track
        self._for = video_id

    def current(self, video_id):
        return self._track if self._for and video_id == self._for else None


class NullPolicy:
    def boundary(self, **_kwargs):
        return None


class Seams:
    """As costuras de AMBIENTE (nao da regra) de um shell parcial.

    `_post` corre o callable NO SITIO (nao ha' UI thread na arm); `exec_js_post`
    e `_caption_wanted_store` nao tocam em pagina nem em disco. Tudo o resto --
    decidir, enfileirar, pintar, logar -- e' o corpo real extraido do shell.
    """

    GLOBALS = {
        "json": json,
        "os": os,
        "time": time,
        "threading": threading,
        "text_normalize": type("TN", (), {
            "collapse_runs": staticmethod(lambda s: " ".join(str(s).split()))})(),
        "caption_lag_aged": staticmethod(
            lambda tap, counted: bool(tap) and tap != counted),
    }

    def __init__(self, overlay, bridge=None, watcher=None, track_thread=None):
        self.caption_overlay = overlay
        self.bridge = bridge
        self.external_caption_watcher = watcher
        self.youtube_track_thread = track_thread
        self.display = {"scaleFactor": 1.0}
        self._caption_wanted = False
        self._caption_window_shown = False
        self._overlay_pushes = 0
        self._source_epoch = 0
        self._caption_painted = ""
        self._caption_painted_at = 0.0
        self._last_caption_was_player = False
        self.external_captions_active = False
        self.external_lines = 0
        self._external_last_text = ""
        self._reload_policy = NullPolicy()
        self.tray = None
        self.visible = False
        self.yt_source_paused = False
        self.emitted = []
        self.js = []
        self.stored = []
        self._posts = 0

    # -- seams de ambiente --------------------------------------------------
    def work_area(self):
        return {"x": 0, "y": 0, "width": 1920, "height": 1080}

    def _post(self, fn):
        self._posts += 1
        fn()
        return True

    def exec_js_post(self, script):
        self.js.append(script)
        return True

    def emit(self, kind, payload=None):
        self.emitted.append((kind, payload))
        return True

    def emit_async(self, kind, payload=None):
        return self.emit(kind, payload)

    def _caption_wanted_store(self, on):
        self.stored.append(bool(on))

    def _arm_caption_idle_hide(self):
        # O TEMPORIZADOR DE SILENCIO E' COSTURA (2026-11-11): a arm do `off`
        # julga que ele foi ARMADO, nao espera 6 s por um Timer. O corpo real do
        # `_blank_caption_window` e' que apaga, e essa e' conduzida na arm.
        self.idle_armed = int(getattr(self, 'idle_armed', 0) or 0) + 1
        return True

    def _arm_caption_status_hide(self):
        # O PRAZO DO ACK DE DESLIGAR TAMBEM E' COSTURA (2026-11-12): o `off`
        # deixou de ser apagado pelo temporizador de silencio (6 s) e passou a
        # ter o DELE (0,5 s, `CAPTION_STATUS_HIDE_S`). A arm conta o
        # armamento; quem apaga o pixel e' `_caption_status_hide`, conduzido
        # aqui a mao para o julgamento nao esperar meio segundo por um Timer.
        self.status_armed = int(getattr(self, 'status_armed', 0) or 0) + 1
        return True

    def _caption_lag_note(self, *_a, **_k):
        return None


def make(src, overlay=None, bridge=None, watcher=None, track_thread=None):
    cls, lines = build(src)
    overlay = overlay if overlay is not None else Overlay()
    return cls(overlay, bridge, watcher, track_thread), overlay, lines


# -- as arms ----------------------------------------------------------------

def _status_lines(lines, reason=None):
    out = []
    for line in lines:
        if not line.startswith("CAPTION_STATUS_SHOWN "):
            continue
        fields = dict(re.findall(r"(\w+)=(\S+)", line))
        if reason is None or fields.get("reason") == reason:
            out.append(fields)
    return out


def _surface_lines(lines):
    out = []
    for line in lines:
        if line.startswith("CAPTION_PAINT_SURFACE "):
            out.append(dict(re.findall(r"(\w+)=(\S+)", line)))
    return out


def arm_a1(src):
    """Ligar com o ecra vazio -> um texto honesto em <= 200 ms."""
    shell, ov, lines = make(src, bridge=Bridge(loaded=False, state="model-loading"))
    t0 = time.monotonic()
    shell._set_live_enabled({"on": True})
    got = ov.wait_calls(1, STATUS_BUDGET_MS / 1000.0)
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    shown = _status_lines(lines)
    ok = bool(got and shown and shown[0].get("reason") == "model-loading"
              and int(shown[0].get("ms", "999999")) <= STATUS_BUDGET_MS
              and elapsed_ms <= STATUS_BUDGET_MS
              and ov.texts()[:1] == ["carregando modelo\u2026"])
    shell._caption_status_stop()
    return ok, "ms=%.1f logged_ms=%s reason=%s" % (
        elapsed_ms,
        shown[0].get("ms") if shown else "-",
        shown[0].get("reason") if shown else "-")


def arm_a2(src):
    """O player e' dono da superficie -> NADA de texto de estado.

    O caso e' o de 2026-11-04: o player TEM linhas no DOM (e acabou de pintar) e
    o modelo ainda carrega. O `caption_status_for` saudavel devolve None pela
    posse do player; sem essa guarda a escada cairia em `model-loading` e o texto
    de estado ia por cima da linha do YouTube -- o defeito que o dono fotografou.
    """
    watcher = Watcher(video_id="vid-1", rows=["line one"],
                      painted_at=time.monotonic())
    shell, ov, lines = make(src, bridge=Bridge(loaded=False), watcher=watcher)
    shell._set_live_enabled({"on": True})
    time.sleep(0.15)
    ok = not _status_lines(lines) and not ov.calls
    shell._caption_status_stop()
    return ok, "status=%d paints=%d" % (len(_status_lines(lines)), len(ov.calls))


def arm_a3(src):
    """A primeira legenda verdadeira RETIRA o texto de estado."""
    shell, ov, lines = make(src, bridge=Bridge(loaded=False))
    shell._set_live_enabled({"on": True})
    first = ov.wait_calls(1, STATUS_BUDGET_MS / 1000.0)
    shell.on_worker_caption("hello there", {"start": 1.0, "final": False,
                                            "tap_ms": int(time.time() * 1000.0)})
    painted = ov.wait_calls(2, 0.5)
    time.sleep(0.05)
    cleared = [l for l in lines if l.startswith("CAPTION_STATUS_CLEARED reason=")]
    # O tique seguinte NAO pode apagar a legenda
    before = len(ov.calls)
    shell._caption_status_tick()
    time.sleep(0.05)
    ok = bool(first and painted
              and ov.texts()[1] == "hello there"
              and shell._caption_status_reason == ""
              and len(cleared) == 1
              and ov.visible
              and len(ov.calls) == before)
    shell._caption_status_stop()
    return ok, "paints=%d cleared=%d reason=%r" % (
        len(ov.calls), len(cleared), shell._caption_status_reason)


def arm_a4(src):
    """Estado desconhecido (sem ponte, sem faixa, sem linha) -> silencio."""
    shell, ov, lines = make(src)
    shell._set_live_enabled({"on": True})
    time.sleep(0.15)
    ok = not _status_lines(lines) and not ov.calls
    shell._caption_status_stop()
    return ok, "status=%d paints=%d" % (len(_status_lines(lines)), len(ov.calls))


def arm_a5(src):
    """O bloqueio muda (carrega -> ouve) -> uma linha por episodio, razao nova."""
    bridge = Bridge(loaded=False)
    shell, ov, lines = make(src, bridge=bridge)
    shell._set_live_enabled({"on": True})
    ov.wait_calls(1, STATUS_BUDGET_MS / 1000.0)
    bridge.loaded = True
    bridge.capturing = True
    shell._caption_status_tick()
    ov.wait_calls(2, 0.3)
    shell._caption_status_tick()          # mesmo estado: nao e' um episodio novo
    time.sleep(0.1)
    shown = _status_lines(lines)
    reasons = [s.get("reason") for s in shown]
    ok = reasons == ["model-loading", "waiting-first-line"]
    shell._caption_status_stop()
    return ok, "reasons=%s" % (reasons,)


def arm_a6(src):
    """A via do PLAYER deixa UMA testemunha por pintura, com `ms` >= 0."""
    shell, ov, lines = make(src)
    shell._caption_wanted = True
    rows = ["Have you ever had to kill a man?", "No."]
    shell.push_caption_to_window("Have you ever had to kill a man? No.",
                                 instant=True, rows=rows)
    painted = ov.wait_calls(1, 0.5)
    time.sleep(0.05)
    surface = _surface_lines(lines)
    ok = bool(painted and len(surface) == 1
              and surface[0].get("src") == "player"
              and surface[0].get("rows") == "2"
              and int(surface[0].get("ms", "-1")) >= 0
              and "epoch" in surface[0])
    shell._caption_status_stop()
    return ok, "surface=%s" % (surface,)


def _stale_meta(start, capture_epoch):
    return {"start": start, "final": True,
            "tap_ms": None,
            "producer": "live"}


def arm_a7(src):
    """Audio velho: nao pinta, NAO se perde (vai ao historico), 1 linha/episodio."""
    epoch = time.time() - 400.0
    bridge = Bridge(loaded=True, capturing=True, capture_epoch=epoch)
    shell, ov, lines = make(src, bridge=bridge)
    shell._caption_wanted = True
    shell.on_worker_caption("five minutes old", _stale_meta(301.0, epoch))
    shell.on_worker_caption("five minutes old, again", _stale_meta(302.0, epoch))
    time.sleep(0.1)
    refused = [l for l in lines if l.startswith("LIVE_PAINT_REFUSED ")]
    history = [e for e in shell.emitted if e[0] == "caption"]
    ok = (len(refused) == 1 and not ov.calls and len(history) == 2
          and "reason=stale" in refused[0])
    shell._caption_status_stop()
    return ok, "refused=%d paints=%d history=%d" % (
        len(refused), len(ov.calls), len(history))


def arm_a8(src):
    """Audio fresco: pinta, e diz QUAL superficie pintou (`src=asr`)."""
    epoch = time.time() - 400.0
    bridge = Bridge(loaded=True, capturing=True, capture_epoch=epoch)
    shell, ov, lines = make(src, bridge=bridge)
    shell._caption_wanted = True
    shell.on_worker_caption("live line", _stale_meta(399.0, epoch))
    painted = ov.wait_calls(1, 0.5)
    time.sleep(0.05)
    surface = _surface_lines(lines)
    ok = bool(painted and ov.texts() == ["live line"]
              and len(surface) == 1 and surface[0].get("src") == "asr"
              and surface[0].get("rows") == "0")
    shell._caption_status_stop()
    return ok, "paints=%d surface=%s" % (len(ov.calls), surface)


def arm_a9(src):
    """Player dono + linha velha do ASR: nenhum pixel do ASR em cima do player."""
    epoch = time.time() - 400.0
    watcher = Watcher(video_id="vid-1", rows=["player line"],
                      painted_at=time.monotonic())
    bridge = Bridge(loaded=True, capturing=True, capture_epoch=epoch)
    shell, ov, lines = make(src, bridge=bridge, watcher=watcher,
                            track_thread=TrackThread(
                                {"state": "has-track", "cues": [1]}, "vid-1"))
    shell._caption_wanted = True
    shell.on_worker_caption("stale asr", _stale_meta(301.0, epoch))
    time.sleep(0.1)
    refused = [l for l in lines if l.startswith("LIVE_PAINT_REFUSED ")]
    ok = bool(not ov.calls and len(refused) == 1
              and "player=true" in refused[0])
    shell._caption_status_stop()
    return ok, "paints=%d refused=%d" % (len(ov.calls), len(refused))


def arm_a10(src):
    """DESLIGAR responde: `off` no ecra, UMA linha, e o silencio leva-o.

    O caso real do dono: a legenda estava PERSISTIDA ligada, o modelo carregava,
    o ecra estava vazio; o Ctrl+Space fez ON -> OFF. Sem este aviso a tecla nao
    muda um pixel e parece nao fazer nada.
    """
    shell, ov, lines = make(src, bridge=Bridge(loaded=False, state="model-loading"))
    shell._caption_wanted = True            # restaurado do ficheiro
    shell._caption_window_shown = False     # e nada no ecra
    t0 = time.monotonic()
    shell._set_live_enabled({"on": False})
    got = ov.wait_calls(1, STATUS_BUDGET_MS / 1000.0)
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    shown = _status_lines(lines, "off")
    painted = [t for t in ov.texts() if t.endswith("desligada")]
    # O PRAZO DO ACK, E NAO O DO SILENCIO (2026-11-12): o `off` arma
    # `_arm_caption_status_hide` (0,5 s) e nunca `_arm_caption_idle_hide` (6 s) --
    # encolher aquele 6.0 apagaria a linha do player meio segundo depois de ele
    # parar de a mudar. `idle_armed` continua medido e tem de ficar em ZERO.
    armed = int(getattr(shell, "status_armed", 0) or 0)
    idle_armed = int(getattr(shell, "idle_armed", 0) or 0)
    live_off = shell._caption_wanted is False
    visible = bool(ov.visible)
    # O PRAZO DELE E' QUEM TIRA O TEXTO (conduzido aqui: a arm nao dorme 0,5 s).
    shell._caption_status_hide(int(getattr(shell, "_caption_status_hide_seq", 0) or 0),
                               getattr(shell, "_caption_status_hide_at", 0.0))
    shell._blank_caption_window("no-caption-for-6.0s")
    cleared = bool(not ov.visible and not shell._caption_window_shown
                   and not str(shell._caption_status_reason or ""))
    # LIGAR OUTRA VEZ TROCA O AVISO PELO BLOQUEIO -- e DESARMA o timer do `off`,
    # senao o temporizador antigo apagava o bloqueio verdadeiro 6 s depois.
    shell._set_live_enabled({"on": True})
    time.sleep(0.05)
    swapped = [t for t in ov.texts() if t.endswith("modelo\u2026")]
    off_lines = len(_status_lines(lines, "off"))
    disarmed = int(getattr(shell, "_caption_idle_seq", 0) or 0) >= 1
    ok = bool(got and painted and len(shown) == 1 and armed == 1 and idle_armed == 0
              and float(shell.CAPTION_STATUS_HIDE_S) < float(shell.CAPTION_IDLE_HIDE_S)
              and live_off
              and visible and cleared and swapped and off_lines == 1 and disarmed
              and int(shown[0].get("ms", "999999")) <= STATUS_BUDGET_MS
              and elapsed_ms <= STATUS_BUDGET_MS)
    return ok, ("ms=%.1f shown=%d status_armed=%d idle_armed=%d visible=%s "
                "cleared=%s swapped=%s disarmed=%s" % (
                    elapsed_ms, len(shown), armed, idle_armed, visible, cleared,
                    bool(swapped), disarmed))


def arm_a11(src):
    """Arranque com `on=true` restaurado: o bloqueio fala SEM a primeira tecla.

    A metade (b) e' a nao-regressao de A2: a MESMA chamada de arranque, com um
    player saudavel a pintar, tem de continuar em silencio.
    """
    shell, ov, lines = make(src, bridge=Bridge(loaded=False, state="model-loading"))
    shell._caption_wanted = True            # o ficheiro tinha `on=true`
    t0 = time.monotonic()
    shell._caption_status_start()           # o que `create_window`/`start_worker` chamam
    got = ov.wait_calls(1, STATUS_BUDGET_MS / 1000.0)
    elapsed_ms = (time.monotonic() - t0) * 1000.0
    shown = _status_lines(lines)
    speaks = bool(got and len(shown) == 1
                  and shown[0].get("reason") == "model-loading")
    watcher = Watcher(video_id="vid-1", rows=["player line"],
                      painted_at=time.monotonic())
    shell2, ov2, lines2 = make(src, bridge=Bridge(loaded=False), watcher=watcher)
    shell2._caption_wanted = True
    shell2._caption_status_start()
    time.sleep(0.12)
    quiet = not _status_lines(lines2) and not ov2.calls
    shell._caption_status_stop()
    shell2._caption_status_stop()
    return bool(speaks and quiet), (
        "boot_status=%s ms=%.1f player_quiet=%s" % (
            [s.get("reason") for s in shown], elapsed_ms, quiet))


def arm_a12(src):
    """As TRES costuras do arranque chamam o estado (senao nada disto corre)."""
    methods, _funcs, _consts, _class_consts = extract(src)
    problems = []
    # (metodo, chamada, MINIMO): o `start_worker` tem DUAS costuras (worker
    # aquecido e carga fria); exigir so' uma deixava a outra sem pin.
    for name, needle, want in (("start_worker", "_caption_status_start()", 2),
                               ("create_window", "_caption_status_start()", 1),
                               ("_set_live_enabled", "_caption_off_ack()", 1)):
        node = methods.get(name)
        body = ast.get_source_segment(src, node) if node is not None else ""
        have = (body or "").count(needle)
        if have < want:
            problems.append("%s(%d<%d)" % (name, have, want))
    return not problems, "missing=%s" % (problems or "none")


WORKER_ROUTE = os.path.join(ROOT, "worker", "live_route.py")


def worker_clock_jitter_ms(path=None):
    """O piso de relogio declarado pelo WORKER, lido do ficheiro (fonte unica)."""
    tree = ast.parse(read_source(path or WORKER_ROUTE))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "CLOCK_JITTER_MS":
                    return float(ast.literal_eval(node.value))
    return None


def arm_a13(src):
    """Carimbo no FUTURO -> idade DESCONHECIDA, e o piso e' o numero do worker.

    `max(0.0, negativo)` dizia "fresco" com um instrumento que nao ve' o audio;
    a casa ja' pagou esta lei (medicao ausente nunca e' afirmacao). O texto
    continua a pintar -- idade desconhecida NAO e' recusa --, mas nao afirma
    frescura, e o piso nao pode divergir de `worker/live_route.CLOCK_JITTER_MS`.
    """
    _methods, funcs, consts, _class_consts = extract(src)
    ns = {}
    module = ast.Module(body=list(consts.values()) + list(funcs.values()),
                        type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, "<shell-funcs>", "exec"), ns)
    age = ns["live_paint_age_s"]
    stale = ns["live_paint_stale"]
    now = time.time()
    future_s = age({"age_s": -5.0}, now=now)
    near_zero = age({"age_s": -0.05}, now=now)
    real = age({"age_s": 2.0}, now=now)
    garbage = age({"age_s": "x", "tap_ms": (now - 3.0) * 1000.0}, now=now)
    back_start = age({"start": 500.0}, capture_epoch=now + 100.0, now=now)
    floor = float(ns.get("LIVE_PAINT_JITTER_S") or 0.0)
    worker = worker_clock_jitter_ms()
    same_floor = bool(worker and abs(floor * 1000.0 - worker) < 1e-9)
    # A LINHA NAO SE PERDE: idade desconhecida pinta (nao e' uma recusa).
    shell, ov, lines = make(src, bridge=Bridge(loaded=True, capturing=True))
    shell._caption_wanted = True
    shell.on_worker_caption("future stamp",
                            {"age_s": -5.0, "final": True, "producer": "live"})
    painted = ov.wait_calls(1, 0.5)
    refused = [l for l in lines if l.startswith("LIVE_PAINT_REFUSED ")]
    shell._caption_status_stop()
    ok = bool(future_s is None and near_zero == 0.0 and real == 2.0
              and garbage is not None and abs(garbage - 3.0) < 0.05
              and back_start is None and same_floor
              and not stale(future_s)
              and painted and ov.texts()[:1] == ["future stamp"] and not refused)
    return ok, "future=%r near=%r real=%r garbage=%r back_start=%r floor=%r ms" % (
        future_s, near_zero, real,
        None if garbage is None else round(garbage, 3), back_start,
        floor * 1000.0)


def arm_a14(src):
    """As linhas da rota viva chegam ao LOG: tag publicada E tag escrita.

    O publisher da shell e' `line.startswith(ENGINE_VISIBLE_TAGS)`: uma linha
    que nao comeca por uma destas tags morre no `stderr_tail` e so' aparece na
    cauda da morte -- a classe medida em 2026-11-10 (`WORKER_BOOT_PROF`).
    """
    tree = ast.parse(src)
    tags = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "ENGINE_VISIBLE_TAGS"
                for t in node.targets):
            try:
                tags = [str(v) for v in ast.literal_eval(node.value)]
            except (ValueError, SyntaxError):
                tags = None
    published = tuple(tags or ())
    worker_src = read_source(os.path.join(ROOT, "worker", "live_route.py"))
    shapes = {
        "LIVE_ROUTE_REFUSED": "LIVE_ROUTE_REFUSED reason=",
        "LIVE_ROUTE_UNKNOWN_AGE": "LIVE_ROUTE_UNKNOWN_AGE producer=",
    }
    problems = []
    for tag, shape in shapes.items():
        if tag not in published:
            problems.append("%s(unpublished)" % tag)
        if shape not in worker_src:
            problems.append("%s(unwritten)" % tag)
        if not shape.startswith(published):
            problems.append("%s(no-prefix-match)" % tag)
    return not problems, "problems=%s" % (problems or "none")


ARMS = (
    ("A1 status-within-200ms", arm_a1),
    ("A2 player-owns-surface", arm_a2),
    ("A3 first-caption-clears", arm_a3),
    ("A4 unknown-says-nothing", arm_a4),
    ("A5 blocker-change-repaints", arm_a5),
    ("A6 surface-witness-player", arm_a6),
    ("A7 stale-refused-keeps-text", arm_a7),
    ("A8 fresh-paints-asr", arm_a8),
    ("A9 player-owns-stale-noop", arm_a9),
    ("A10 off-acks", arm_a10),
    ("A11 boot-restored-acks", arm_a11),
    ("A12 boot-wiring", arm_a12),
    ("A13 future-stamp-not-fresh", arm_a13),
    ("A14 route-tags-published", arm_a14),
)


def run_arms(src, verbose=True):
    failures = []
    for label, arm in ARMS:
        try:
            ok, note = arm(src)
        except Exception as exc:            # noqa: BLE001
            ok, note = False, "raised %s: %s" % (type(exc).__name__, exc)
        if verbose:
            print("%-32s %s  %s" % (label, "PASS" if ok else "FAIL", note))
        if not ok:
            failures.append("%s -- %s" % (label, note))
    return failures


# -- o braco negativo: mutacoes reais, apanhadas por arm ---------------------

MUTANTS = (
    ("toggle-does-not-arm-status",
     "                self._caption_status_start()\n"
     "            else:\n",
     "                pass  # MUTANT\n"
     "            else:\n"),
    ("status-ignores-player-owner",
     "    if state.get('player_owns') or state.get('painted_recent'):\n"
     "        return None\n",
     "    if state.get('painted_recent'):\n"
     "        return None\n"),
    ("caption-does-not-clear-status",
     "            if str(getattr(self, '_caption_status_reason', '') or ''):\n",
     "            if False:  # MUTANT\n"),
    ("unknown-state-guesses",
     "    if state.get('bridge') and state.get('loaded') and state.get('capturing'):\n"
     "        return 'waiting-first-line'\n"
     "    return None\n",
     "    if state.get('bridge') and state.get('loaded') and state.get('capturing'):\n"
     "        return 'waiting-first-line'\n"
     "    return 'model-loading'\n"),
    ("surface-witness-renames-field",
     "            log('CAPTION_PAINT_SURFACE src=%s rows=%d text=%s ms=%d epoch=%d'\n",
     "            log('CAPTION_PAINT_SURFACE srcz=%s rows=%d text=%s ms=%d epoch=%d'\n"),
    ("stale-gate-disabled",
     "        _refused = live_paint_stale(_audio_age_s)\n",
     "        _refused = False  # MUTANT\n"),
    ("stream-clock-age-zeroed",
     "        measured = _measured_age(now - (epoch + float(start))) \\\n"
     "            if _is_number(start) else _SKIP\n",
     "        measured = 0.0  # MUTANT\n"),
    ("future-age-clamped-to-fresh",
     "    if delta < -LIVE_PAINT_JITTER_S:\n"
     "        return None\n",
     "    if False:  # MUTANT\n"
     "        return None\n"),
    ("off-ack-silent",
     "                self._caption_off_ack()\n",
     "                pass  # MUTANT\n"),
    # O ACK DE DESLIGAR JA' NAO ARMA O TEMPORIZADOR DE SILENCIO (2026-11-12):
    # ele tem prazo PROPRIO (`_arm_caption_status_hide`, 0,5 s). Este mutante
    # tira o armamento que o caminho REAL faz hoje; o antigo nao casava com
    # linha nenhuma (`MUTATION-NOT-APPLIED hits=0`) e um mutante que nao se
    # aplica nao prova nada.
    ("off-ack-not-status-armed",
     "                self._arm_caption_status_hide()\n",
     "                pass  # MUTANT\n"),
    ("boot-deferred-arming-removed",
     "                if pending:\n"
     "                    self._caption_status_start()\n",
     "                if pending:\n"
     "                    pass  # MUTANT\n"),
    ("cold-worker-arming-removed",
     "            # O ARRANQUE RESTAURADO TAMBEM RESPONDE (2026-11-11): a ponte\n"
     "            # existe agora, portanto o bloqueio (modelo a carregar, sem audio)\n"
     "            # ja' tem nome. Uma vez por episodio; o player saudavel cala-o.\n"
     "            if getattr(self, '_caption_wanted', False):\n"
     "                self._caption_status_start()\n",
     "            pass  # MUTANT\n"),
    ("status-does-not-disarm-off-timer",
     "            self._caption_idle_disarm()\n"
     "            return True\n",
     "            pass  # MUTANT\n"
     "            return True\n"),
    ("route-refused-tag-unpublished",
     "                       'LIVE_ROUTE_REFUSED', 'LIVE_ROUTE_UNKNOWN_AGE')",
     "                       'LIVE_ROUTE_REFUSED')"),
)


def first_failure(src):
    """A PRIMEIRA arm que cai (o braco negativo nao precisa das nove)."""
    for label, arm in ARMS:
        try:
            ok, note = arm(src)
        except Exception as exc:            # noqa: BLE001
            ok, note = False, "raised %s: %s" % (type(exc).__name__, exc)
        if not ok:
            return "%s -- %s" % (label, note)
    return ""


def neg_arm(src):
    caught = 0
    print("NEG-ARM: %d mutacoes, copia em memoria do ficheiro real\n" % len(MUTANTS))
    # A ANCORA ACOMPANHA A CONVENCAO DE FIM DE LINHA DO FICHEIRO (medido 2026-11-12):
    # `sotto_webview.py` e' CRLF e as ancoras estao escritas com LF, por isso
    # TREZE das catorze mutacoes respondiam `MUTATION-NOT-APPLIED (hits=0)` e o
    # negativo publicava `FAIL (1/14)` -- um controlo em que 13 bracos nao
    # chegam a correr nao prova nada, e o passo `red-as-expected-live-ack`
    # (que exige a frase `NEG-ARM: PASS`) estava RED. Aqui a ancora e' tentada
    # nas DUAS formas, e o `hits` reportado e' o da forma que aplicou.
    for name, old, new in MUTANTS:
        hits = src.count(old)
        if hits != 1:
            alt_old = old.replace('\n', '\r\n')
            alt_new = new.replace('\n', '\r\n')
            if src.count(alt_old) == 1:
                old, new, hits = alt_old, alt_new, 1
        if hits != 1:
            print("%-36s MUTATION-NOT-APPLIED (hits=%d)" % (name, hits))
            continue
        mutant = src.replace(old, new)
        failure = first_failure(mutant)
        caught += 1 if failure else 0
        print("%-36s %s  %s" % (name, "CAUGHT" if failure else "ESCAPED",
                                failure.split(" -- ")[0] if failure else "-"))
    total = len(MUTANTS)
    print("")
    if caught == total:
        print("NEG-ARM: PASS (%d/%d)" % (caught, total))
        return 1
    print("NEG-ARM: FAIL (%d/%d)" % (caught, total))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shell", default=SHELL, help="o ficheiro do shell")
    parser.add_argument("--neg-arm", action="store_true",
                        help="muta uma copia e exige que as arms a apanhem")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)
    src = read_source(args.shell)
    if args.neg_arm:
        return neg_arm(src)
    failures = run_arms(src, verbose=not args.quiet)
    total = len(ARMS)
    passed = total - len(failures)
    print("")
    if passed == total:
        print("VERDICT: PASS (%d/%d)" % (passed, total))
        return 0
    print("VERDICT: FAIL (%d/%d)" % (passed, total))
    for item in failures:
        print("  - %s" % item)
    return 1


if __name__ == "__main__":
    sys.exit(main())
