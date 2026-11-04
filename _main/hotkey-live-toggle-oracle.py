#!/usr/bin/env python
# NO-BUG: instrumento da lane HotkeyLatency (2026-11-03) -- mede o interruptor do
# Ctrl+Space executando o codigo que corre, com o UI thread INJECTADO. Nao abre
# janela, nao toca em ctypes, nao lanca o app vivo, nao escreve log de produto.
"""ORACLE: Ctrl+Space -- a legenda ao vivo comuta QUANDO ELE CARREGA NA TECLA.

A EVIDENCIA QUE ESTE INSTRUMENTO JULGA (`_main/webview-run.log`, sessao do dono):

    02:45:13.955 HOTKEY_PRESSED role=panels count=1 accelerator=Alt+C
    02:45:19.219 LIVE_ENABLED on=true wanted=true panel_closed=false
    02:45:24.645 HOTKEY_PRESSED role=live count=1 source=observed
    02:45:24.646 HOTKEY_LIVE_STEP caption_on=false
    02:45:51.919 LIVE_ENABLED on=false wanted=false panel_closed=false

Duas coisas estao medidas nesse recorte e nenhuma delas e' o pump:

  (1) A ACCAO SAI FORA DE TEMPO. A decisao e' instantanea (1 ms: `HOTKEY_LIVE_STEP`
      as 24.646), mas o `LIVE_ENABLED` da MESMA pressao so' aparece as 51.919 --
      **27,3 s** depois, dentro de um `UI_WATCHDOG_STRIKE`/`RECOVERED` de 27 s.
      A causa e' `show_caption_window`: `self.window.evaluate_js(...)` bloqueia em
      `semaphore.acquire()` SEM limite (`webview/platforms/edgechromium.py:160`)
      ate' o UI thread correr o script. Todo o interruptor -- inclusive a linha do
      log e a thread do hotkey -- esperava pelo trabalho de UI.

  (2) O INTERRUPTOR LIA A INTENCAO, NAO O ECRA -- E DEPOIS LEU O ECRA DEMAIS
      (corrigido a 2026-11-04, e este oraculo passou a julgar a regra nova).
      `_caption_wanted` comecava a `True` em cada arranque
      (`CAPTION_WANTED_RESTORED on=true from=...01:05:14`) com a janela
      ESCONDIDA; a primeira pressao, entao, "ligava" um interruptor ja' ligado e
      DESLIGAVA a legenda. A cura de 2026-11-03 foi ler `_caption_window_shown`
      -- e ela criou o defeito OPOSTO, medido no log dele a 2026-11-04:

        04:49:43.435 HOTKEY_LIVE_STEP caption_on=true shown=false wanted=true
        04:49:50.374 HOTKEY_LIVE_STEP caption_on=true shown=false wanted=true

      duas presses seguidas (292 e 293) LIGANDO. O cao de guarda de silencio
      tinha apagado a janela (`CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s
      wanted=true`, epoch 39), e apagar os pixels NAO desliga o interruptor do
      dono -- o contrato do blank e' que a proxima legenda volte sem tocar em
      nada. Com a leitura de `shown`, depois de um blank o Ctrl+Space nunca mais
      desligava. A regra final: a TECLA comuta `_caption_wanted` (o que o dono
      possui); `shown` fica na linha do log como DIAGNOSTICO. A mentira do
      arranque vive agora onde ela nasce: a restauracao PEDE a janela
      (`_caption_show_pending` -> `CAPTION_WINDOW_DEFERRED_APPLIED`).

BRACOS (a lista e' impressa no arranque; `--neg-arm` corre os mutantes e exige RED):

  (a) arranque: a restauracao pede a janela; `wanted=true` + janela apagada ->
      a pressao DESLIGA o interruptor
  (b) legenda a' vista -> a pressao DESLIGA
  (c) legenda apagada por silencio (`shown=false`, `wanted=true`) -> a pressao
      DESLIGA (e `wanted=false` -> LIGA, para a arm nao ser tautologica)
  (d) UI thread PARADO -> a decisao nao espera: `LIVE_ENABLED` sai antes de
      qualquer callable postado correr, e a pressao devolve em < 50 ms
  (e) o caminho do interruptor nao chama `evaluate_js` (a primitiva que bloqueia)
  (f) duas pressoes com o UI parado -> duas comutacoes, cada uma lendo o estado
      NOVO (nada de `caption_on` repetido por leitura velha)
  (g) a marca do painel sai por POST (`exec_js_post`), na ordem, e o chamador segue
  (h) o EVENTO injectado na `PassiveHotkeyThread` REAL (borda de descida) chega ao
      interruptor: um toque = uma comutacao, segurado = nenhuma repeticao
  (i) Alt+C (role=panels) nao toca na legenda -- a semantica das duas teclas fica
  (j) a persistencia (`caption-wanted.json`) grava o estado NOVO
  (k) um `show()` que rebenta nao perde o estado nem mata a pressao
  (l) estrutural: `show_caption_window` nao tem `evaluate_js`, e `_set_live_enabled`
      escreve `LIVE_ENABLED` ANTES de chamar a janela (ordem no AST, nao no texto)

Uso:
    python _main/hotkey-live-toggle-oracle.py            -> rc 0 GREEN / rc 1 RED
    python _main/hotkey-live-toggle-oracle.py --neg-arm  -> muta uma COPIA e exige RED
    SOTTO_ROOT=<arvore> ...                              -> julga outra arvore
"""
from __future__ import annotations

import ast
import importlib.util as _ilu
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SOTTO_ROOT") or HERE.parent).resolve()
SHELL = ROOT / "app" / "webview" / "sotto_webview.py"
GESTURE = ROOT / "app" / "webview" / "hotkey_gesture.py"
EXIT_PASS, EXIT_FAIL = 0, 1

rows: list[tuple[bool, str, str]] = []
LOG: list[str] = []

ARM_LIST = (
    "(a) arranque wanted=true + janela escondida -> 1a pressao LIGA",
    "(b) legenda a' vista -> a pressao DESLIGA",
    "(c) legenda apagada por silencio -> a pressao LIGA (muda o ecra)",
    "(d) UI parado -> LIVE_ENABLED sai antes do trabalho de UI, < 50 ms",
    "(e) nenhum evaluate_js no caminho do interruptor",
    "(f) duas pressoes com UI parado -> duas comutacoes com estado novo",
    "(g) marca do painel por POST, na ordem, sem esperar",
    "(h) evento injectado na PassiveHotkeyThread real -> 1 toque = 1 comutacao",
    "(i) Alt+C nao toca na legenda",
    "(j) caption-wanted.json grava o estado novo",
    "(k) um show() que rebenta nao perde o estado",
    "(l) estrutural: sem evaluate_js; LIVE_ENABLED antes da janela",
)


def add(ok: bool, name: str, detail: str = "") -> bool:
    rows.append((bool(ok), name, detail))
    print(f"  {'GREEN' if ok else 'RED  '} {name}" + (f"  {detail}" if detail else ""))
    return bool(ok)


def log(message, *a, **k):  # o `log` do shell, capturado por braco
    LOG.append(str(message))


def warn(message, *a, **k):
    LOG.append('WARN ' + str(message))


# ---------------------------------------------------------------------------
# Extracao do proprio ficheiro: e' o que corre, nao a minha transcricao
# ---------------------------------------------------------------------------
def _cls(source: str, cls_name: str):
    tree = ast.parse(source)
    return next((n for n in tree.body
                 if isinstance(n, ast.ClassDef) and n.name == cls_name), None)


def class_methods(source: str, cls_name: str, names) -> dict:
    cls = _cls(source, cls_name)
    out = {}
    for node in (cls.body if cls else []):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            out[node.name] = ast.get_source_segment(source, node) or ""
    return out


def class_names(source: str, cls_name: str) -> set:
    cls = _cls(source, cls_name)
    return {n.name for n in (cls.body if cls else []) if isinstance(n, ast.FunctionDef)}


def module_const(source: str, name: str):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    return None


def def_node(source: str, name: str):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def load_module(name: str, path: Path):
    spec = _ilu.spec_from_file_location(name, str(path))
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# O UI thread e a janela: INJECTADOS. Postar nao corre nada; `evaluate_js`
# BLOQUEIA (e' o que ele faz de verdade) e aqui RECUSA-SE em vez de pendurar.
# ---------------------------------------------------------------------------
class FakeUI:
    """`_post` = `BeginInvoke`: entra na fila, o chamador SEGUE."""

    def __init__(self, run_now=False):
        self.queue: list = []
        self.ran = 0
        self.run_now = bool(run_now)

    def post(self, fn):
        # O `_post` do shell embrulha o callable (`guarded`): o que ele levanta e'
        # uma LINHA (`POSTED_CALLABLE_FAILED`), nunca um dialogo do WinForms nem
        # uma excepcao no chamador. O fake faz o mesmo -- senao o braco (k)
        # estaria a julgar um caminho que a producao nao tem.
        def guarded():
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                warn(f'POSTED_CALLABLE_FAILED fn={getattr(fn, "__name__", fn)} '
                     f'{type(exc).__name__}: {exc}')
        self.queue.append(guarded)
        if self.run_now:
            self.drain()
        return True

    def drain(self):
        while self.queue:
            fn = self.queue.pop(0)
            self.ran += 1
            fn()


class BlockingWindow:
    """`window.evaluate_js`: o caminho que espera 27 s. Aqui ele DENUNCIA-SE."""

    def __init__(self):
        self.calls: list = []

    def evaluate_js(self, script, *a, **k):
        self.calls.append(script)
        raise RuntimeError('ui-thread blocked: evaluate_js waits for a semaphore '
                           'that a stalled message loop never releases')


class FakeCore:
    def __init__(self):
        self.scripts: list = []

    def ExecuteScriptAsync(self, script):
        self.scripts.append(script)
        return script


class FakeOverlay:
    def __init__(self, explode=False):
        self.shown: list = []
        self.explode = bool(explode)

    def set_work_area(self, wa, scale=1.0):
        return True

    def show(self, on):
        if self.explode:
            raise RuntimeError('overlay show failed (simulated)')
        self.shown.append(bool(on))
        return True


def build_methods(source: str, shell_path: Path) -> dict:
    """Os corpos REAIS de `SottoShell`, exec'd contra um `self` falso."""
    wanted = ("_hotkey_resolve", "_set_live_enabled", "show_caption_window",
              "_caption_wanted_store", "exec_js_post")
    bodies = class_methods(source, "SottoShell", wanted)
    if len(bodies) != len(wanted):
        return {}
    gesture = load_module("hotkey_gesture_probe", GESTURE)
    namespace = {
        "log": log,
        "warn": warn,
        "json": json,
        "os": os,
        "time": time,
        "window_visible": lambda hwnd: bool(SCREEN['visible']),
        "hotkey_numbers": lambda: gesture,
    }
    module = ast.Module(body=[ast.parse(bodies[name]).body[0] for name in wanted],
                        type_ignores=[])
    exec(compile(module, "<sotto-shell-toggle>", "exec"), namespace)
    return namespace


SCREEN = {'visible': False}


class Shell:
    """So' o que os cinco metodos tocam. Nenhuma chamada Win32."""

    def __init__(self, methods, ui, *, wanted=False, shown=False, overlay=True,
                 explode=False, store_path=None):
        self._caption_wanted = bool(wanted)
        self._caption_window_shown = bool(shown)
        self.CAPTION_WANTED_PATH = str(store_path or _tmp_state())
        self.caption_overlay = FakeOverlay(explode) if overlay else None
        self.display = {'scaleFactor': 1.0}
        self.core = FakeCore()
        self.window = BlockingWindow()
        self.ui = ui
        # Alt+C (role=panels) precisa destes tres; o braco (i) so' os usa.
        self.hwnd = 4242
        self.visible = False
        self.surface_applied = 'strip'
        for name in ("_hotkey_resolve", "_set_live_enabled", "show_caption_window",
                     "_caption_wanted_store", "exec_js_post"):
            setattr(self, name, types.MethodType(methods[name], self))

    def _post(self, fn):
        return self.ui.post(fn)

    def work_area(self):
        return {'x': 0, 'y': 0, 'width': 100, 'height': 100}

    # -- o ciclo dos paineis (Alt+C), falso no que e' janela ------------------
    def show_strip(self, reason):
        self.visible = True
        SCREEN['visible'] = True
        self.surface_applied = 'strip'
        return 'strip'

    def show_side(self, reason):
        self.visible = True
        SCREEN['visible'] = True
        self.surface_applied = 'panel'
        return 'panel'

    def hide_panel(self, reason):
        self.visible = False
        SCREEN['visible'] = False
        return True


_STATE_DIR = {'path': None}


def _tmp_state() -> str:
    if _STATE_DIR['path'] is None:
        _STATE_DIR['path'] = tempfile.mkdtemp(prefix='sotto-toggle-')
    return os.path.join(_STATE_DIR['path'], 'caption-wanted.json')


def press(shell, kind='live'):
    """O EVENTO, injectado: o mesmo `kind` que `hotkey_live()` poe na fila."""
    return shell._hotkey_resolve(kind)


def live_lines():
    return [line for line in LOG if line.startswith('LIVE_ENABLED ')
            or line.startswith('LIVE_ENABLED_FAILED ')]


def steps():
    return [line for line in LOG if line.startswith('HOTKEY_LIVE_STEP ')]


# ---------------------------------------------------------------------------
# Braco (h): a PassiveHotkeyThread REAL, com o estado das teclas injectado
# ---------------------------------------------------------------------------
def module_literals(source: str) -> dict:
    """Todas as constantes LITERAIS do modulo -- o chao do namespace extraido.

    MEDIDO 2026-11-03: extrair a CLASSE de um ficheiro de 6000 linhas e injectar
    so' as duas constantes que o autor do oraculo se lembrou deixa o braco a
    morrer com `NameError` a primeira vez que o shell ganha uma terceira
    (`_MODIFIER_VARIANTS`, `_HOTKEY_TRACE`...). Na segunda vez ja' nao e' azar: e'
    o oraculo a correr atras da forma do ficheiro. Este chao pesca TODAS as
    atribuicoes de valor literal de uma vez, e o que for injectado por cima
    continua a ganhar.
    """
    out = {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return out
    for node in tree.body:
        if isinstance(node, ast.Assign):
            try:
                value = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            try:
                out[node.target.id] = ast.literal_eval(node.value)
            except (ValueError, SyntaxError, AttributeError):
                continue
    # SEGUNDA PASSAGEM: uma constante que nao e' literal mas e' INOFENSIVA de
    # avaliar (`os.environ.get('SOTTO_HOTKEY_TRACE','') == '1'`) e' avaliada num
    # namespace com `os`/`sys` -- senao o braco volta a morrer com `NameError`
    # na proxima constante que o shell ganhar.
    env = {"os": os, "sys": sys, "__builtins__": __builtins__}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if not names or all(n in out for n in names):
            continue
        try:
            exec(compile(ast.Module(body=[node], type_ignores=[]),
                         "<consts>", "exec"), env)
        except Exception:                                        # noqa: BLE001
            continue
        for name in names:
            if name in env:
                out[name] = env[name]
    return out


def passive_thread(source: str, gesture, frames, on_hotkey, log_fn):
    """`PassiveHotkeyThread` do ficheiro, alimentada por uma sequencia de frames.

    O laco le' o estado das teclas uma vez por volta e chama
    `self._stop_requested.wait(poll_s)` no fim de cada volta -- por isso a
    SEQUENCIA avanca no `wait()`, e cada leitura de tecla devolve o frame
    corrente. E' a unica coisa injectada: a borda, o nao-repetir e a chamada do
    callback sao os do ficheiro.
    """
    cls = _cls(source, "PassiveHotkeyThread")
    if cls is None:
        return None
    namespace = module_literals(source)
    namespace.update({
        "threading": threading,
        # OS NOMES DE MODULO QUE O CORPO LE' (2026-11-03): o `run` do
        # `PassiveHotkeyThread` chama `time.monotonic()`; sem ele o braco
        # morria com `NameError` e o gesto nao era medido nenhuma vez.
        "time": time,
        "kernel32": type('K', (), {'GetCurrentThreadId': staticmethod(lambda: 1)})(),
        "user32": type('U', (), {'GetAsyncKeyState': staticmethod(lambda vk: 0)})(),
        # AS TABELAS DE VK SAIRAM DO SHELL (2026-11-04): o `__init__` do
        # observador le' `hotkey_numbers()` (o modulo do gesto) para o VK
        # generico e os laterais. Extrair so' a classe deixava esse nome
        # indefinido e o oraculo caia com `NameError` em vez de medir.
        "hotkey_numbers": lambda: gesture,
        "parse_accelerator": gesture.parse_accelerator,
        "log": log,
        "warn": warn,
    })
    module = ast.Module(body=[cls], type_ignores=[])
    exec(compile(module, "<sotto-passive-hotkey>", "exec"), namespace)
    cls = namespace["PassiveHotkeyThread"]

    class Clock:
        def __init__(self):
            self.frame = 0
            self.polls = 0

        def is_set(self):
            return self.frame >= len(frames)

        def wait(self, timeout=None):
            self.frame += 1
            self.polls += 1
            return self.is_set()

    clock = Clock()

    def key_state(vk):
        frame = frames[min(clock.frame, len(frames) - 1)]
        return bool(frame.get(int(vk)))

    thread = cls(gesture.LIVE_ACCELERATOR, on_hotkey, log_fn=log_fn,
                 key_state=key_state, poll_s=0.0)
    thread._stop_requested = clock
    thread.run()
    return thread


# ---------------------------------------------------------------------------
# Veredicto
# ---------------------------------------------------------------------------
def verdict(name: str) -> int:
    passed = sum(1 for ok, _, _ in rows if ok)
    total = len(rows)
    failed = total - passed
    for ok, label, detail in rows:
        if not ok:
            print(f"FALHA: {label}" + (f"  -- {detail}" if detail else ""))
    print(f"\n{name} {'GREEN' if not failed else 'VERMELHO'} -- "
          f"arms={total} pass={passed} fail={failed} "
          f"(rc={EXIT_PASS if not failed else EXIT_FAIL})")
    return EXIT_PASS if not failed else EXIT_FAIL


def run(shell_path: Path) -> int:
    if not shell_path.exists():
        print(f"VERDICT: FAIL -- {shell_path} ausente")
        return EXIT_FAIL
    print("BRACOS JULGADOS:")
    for line in ARM_LIST:
        print(f"  {line}")
    rows.clear()
    LOG.clear()

    source = shell_path.read_text(encoding='utf-8')
    gesture = load_module("hotkey_gesture_probe2", GESTURE)
    methods = build_methods(source, shell_path)
    if not methods:
        print("VERDICT: FAIL -- nao consegui extrair os metodos do shell")
        return EXIT_FAIL

    # -- (a) arranque: o interruptor restaurado PEDE a janela ------------------
    print("\nARM (a) -- a restauracao pede os pixels, e o interruptor e' a verdade")
    # A mentira do arranque deixou de viver no gesto e passou a viver no sitio
    # dela: a restauracao PEDE a janela (`_caption_show_pending`), aplicada no
    # instante em que o overlay existe. `shown=false` com `wanted=true` deixa de
    # significar "o dono nao ve" e passa a significar "a janela foi APAGADA
    # pelo cao de guarda", que e' um facto sobre PIXELS, nao sobre o interruptor.
    add('self._caption_show_pending = True' in source
        and 'if self._caption_wanted:' in source,
        "a restauracao de `_caption_wanted` pede a janela (pendente aplicado)",
        "CAPTION_WINDOW_DEFERRED_APPLIED path")
    LOG.clear()
    shell = Shell(methods, FakeUI(), wanted=True, shown=False)
    press(shell)
    add(not shell._caption_wanted and not shell._caption_window_shown,
        "wanted=true + janela apagada -> a pressao DESLIGA o interruptor",
        f"wanted={shell._caption_wanted} shown={shell._caption_window_shown}")
    add(any('caption_on=false' in line for line in steps()),
        "HOTKEY_LIVE_STEP diz caption_on=false",
        str(steps()[-1:]))

    # -- (b) legenda a' vista --------------------------------------------------
    print("\nARM (b) -- com ela a' vista, a pressao desliga")
    LOG.clear()
    shell = Shell(methods, FakeUI(run_now=True), wanted=True, shown=True)
    press(shell)
    add(not shell._caption_wanted and not shell._caption_window_shown,
        "shown=true -> a pressao DESLIGA",
        f"wanted={shell._caption_wanted} shown={shell._caption_window_shown}")
    add(shell.caption_overlay.shown == [False],
        "o overlay recebeu show(False)", str(shell.caption_overlay.shown))

    # -- (c) apagada por silencio ---------------------------------------------
    print("\nARM (c) -- blanked: os pixels sao um facto, o interruptor e' do dono")
    # MEDIDO no log do dono, 2026-11-04 04:49:43.435 e 04:49:50.374 (presses 292
    # e 293): `HOTKEY_LIVE_STEP caption_on=true shown=false wanted=true` DUAS
    # vezes. O cao de guarda tinha acabado de apagar a janela
    # (`CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s wanted=true`, epoch 39)
    # e o interruptor dele continuava LIGADO -- o contrato do blank e' esse ("a
    # proxima legenda volta a escreve-lo sem tocar em nada"). Ler `shown` aqui
    # fazia o Ctrl+Space LIGAR para sempre: nunca mais desligava.
    LOG.clear()
    shell = Shell(methods, FakeUI(run_now=True), wanted=True, shown=False)
    press(shell)
    add(not shell._caption_wanted and not shell._caption_window_shown,
        "shown=false com wanted=true (blanked) -> a pressao DESLIGA",
        f"wanted={shell._caption_wanted} shown={shell._caption_window_shown}")
    add(shell.caption_overlay.shown == [False],
        "o overlay recebeu show(False)", str(shell.caption_overlay.shown))
    # E O OUTRO LADO: wanted=false -> LIGA e o overlay mostra.
    LOG.clear()
    shell = Shell(methods, FakeUI(run_now=True), wanted=False, shown=False)
    press(shell)
    add(shell._caption_wanted and shell.caption_overlay.shown == [True],
        "wanted=false -> a pressao LIGA e o overlay recebe show(True)",
        f"wanted={shell._caption_wanted} shown={shell.caption_overlay.shown}")

    # -- (d) UI thread PARADO --------------------------------------------------
    print("\nARM (d) -- o UI parado nao pode ser a latencia do gesto")
    LOG.clear()
    ui = FakeUI(run_now=False)
    shell = Shell(methods, ui, wanted=False, shown=False)
    started = time.monotonic()
    press(shell)
    elapsed_ms = (time.monotonic() - started) * 1000.0
    add(elapsed_ms < 50.0, "a pressao devolve em < 50 ms com o UI parado",
        f"elapsed_ms={elapsed_ms:.1f}")
    add(ui.ran == 0, "nenhum callable postado tinha corrido na decisao",
        f"ran={ui.ran} queued={len(ui.queue)}")
    add(live_lines() and live_lines()[0].startswith('LIVE_ENABLED on=true '),
        "LIVE_ENABLED saiu NA DECISAO (antes do trabalho de UI)",
        str(live_lines()[:1]))
    add(shell._caption_window_shown and shell._caption_wanted,
        "o estado ja' comutou quando a pressao voltou",
        f"wanted={shell._caption_wanted} shown={shell._caption_window_shown}")

    # -- (e) a primitiva que bloqueia nao esta no caminho ----------------------
    print("\nARM (e) -- evaluate_js nao e' o caminho do interruptor")
    add(shell.window.calls == [],
        "window.evaluate_js nunca foi chamado", str(shell.window.calls))

    # -- (f) duas pressoes com o UI parado ------------------------------------
    print("\nARM (f) -- duas pressoes seguidas, UI ainda parado")
    LOG.clear()
    ui = FakeUI(run_now=False)
    shell = Shell(methods, ui, wanted=False, shown=False)
    press(shell)
    press(shell)
    marks = [line for line in steps()]
    add(len(marks) == 2 and 'caption_on=true' in marks[0]
        and 'caption_on=false' in marks[1],
        "as duas pressoes comutam para lados OPOSTOS (estado novo, nao cache)",
        str(marks))
    add(not shell._caption_window_shown and not shell._caption_wanted,
        "depois de dois toques o estado voltou ao inicio",
        f"wanted={shell._caption_wanted} shown={shell._caption_window_shown}")
    add(ui.ran == 0, "as duas decisoes sairam com o UI ainda parado",
        f"ran={ui.ran} queued={len(ui.queue)}")

    # -- (g) a marca do painel, por POST --------------------------------------
    print("\nARM (g) -- a pagina e' avisada por POST, na ordem")
    LOG.clear()
    ui = FakeUI(run_now=False)
    shell = Shell(methods, ui, wanted=False, shown=False)
    press(shell)
    press(shell)
    queued = len(ui.queue)
    ui.drain()
    scripts = shell.core.scripts
    add(queued == 4, "2 transicoes -> 2 shows + 2 marcas postados",
        f"queued={queued}")
    marks = [s for s in scripts if 'data-caption-window' in s]
    add(len(marks) == 2 and '"on"' in marks[0] and '"off"' in marks[1],
        "as marcas dizem on e depois off, na ordem das pressoes", str(marks))

    # -- (h) o evento injectado na PassiveHotkeyThread real -------------------
    print("\nARM (h) -- o evento vem da thread REAL, com a tecla injectada")
    LOG.clear()
    ui = FakeUI(run_now=False)
    shell = Shell(methods, ui, wanted=False, shown=False)
    CTRL, SPACE = 0x11, 0x20
    frames = ([{CTRL: True, SPACE: True}] +            # toque: borda de descida
              [{CTRL: True, SPACE: True}] * 20 +       # segurado: 20 voltas
              [{CTRL: False, SPACE: False}] * 3 +      # larga
              [{CTRL: True, SPACE: True}] * 2 +        # segundo toque
              [{CTRL: True, SPACE: False}] * 3)
    thread = passive_thread(source, gesture, frames,
                            lambda: press(shell, 'live'), log)
    add(thread is not None, "a classe PassiveHotkeyThread foi extraida do ficheiro")
    add(thread is not None and thread.pressed == 2,
        "dois toques -> dois eventos (a segurada nao repete)",
        f"pressed={getattr(thread, 'pressed', '-')}")
    add(len(live_lines()) == 2 and 'on=true' in live_lines()[0]
        and 'on=false' in live_lines()[1],
        "cada toque comutou a legenda uma vez, para lados opostos",
        str(live_lines()))

    # -- (i) Alt+C nao mexe na legenda ---------------------------------------
    print("\nARM (i) -- Alt+C continua a ser so' dos paineis")
    LOG.clear()
    SCREEN['visible'] = False
    shell = Shell(methods, FakeUI(run_now=True), wanted=False, shown=False)
    press(shell, 'panels')
    add(live_lines() == [] and steps() == [],
        "role=panels nao escreve LIVE_ENABLED nem HOTKEY_LIVE_STEP", str(LOG[-2:]))
    add(shell.visible, "o painel apareceu (o ciclo segue o seu caminho)")

    # -- (j) a persistencia ----------------------------------------------------
    print("\nARM (j) -- o interruptor sobrevive ao arranque")
    LOG.clear()
    path = os.path.join(tempfile.mkdtemp(prefix='sotto-toggle-store-'),
                        'caption-wanted.json')
    shell = Shell(methods, FakeUI(run_now=True), wanted=False, shown=False,
                  store_path=path)
    press(shell)
    stored = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else None
    add(bool(stored) and stored.get('on') is True,
        "caption-wanted.json gravou on=true", str(stored))
    press(shell)
    stored = json.load(open(path, encoding='utf-8'))
    add(stored.get('on') is False, "e a pressao seguinte gravou on=false", str(stored))

    # -- (k) um show() que rebenta -------------------------------------------
    print("\nARM (k) -- a janela falhar nao pode perder o interruptor")
    LOG.clear()
    shell = Shell(methods, FakeUI(run_now=True), wanted=False, shown=False,
                  explode=True)
    raised = None
    try:
        press(shell)
    except Exception as exc:  # noqa: BLE001
        raised = exc
    add(raised is None, "a pressao nao levanta com o show() a rebentar", repr(raised))
    add(shell._caption_wanted and shell._caption_window_shown,
        "o estado comutou na mesma", f"wanted={shell._caption_wanted}")
    add(any('POSTED_CALLABLE_FAILED' in line for line in LOG),
        "a falha foi DITA (POSTED_CALLABLE_FAILED), nao silenciada", str(LOG[-2:]))

    # -- (l) estrutural: a ordem no AST, nao no texto ------------------------
    print("\nARM (l) -- estrutural: a primitiva que bloqueia e a ordem do log")
    show_src = class_methods(source, "SottoShell", ("show_caption_window",))[
        'show_caption_window']
    add('evaluate_js' not in _code(show_src),
        "show_caption_window nao chama evaluate_js")
    add('exec_js_post' in _code(show_src), "show_caption_window usa exec_js_post")
    set_src = class_methods(source, "SottoShell", ("_set_live_enabled",))[
        '_set_live_enabled']
    add(_call_order(set_src, 'log', 'show_caption_window') == 'before',
        "LIVE_ENABLED sai ANTES de show_caption_window no codigo que corre",
        _call_order(set_src, 'log', 'show_caption_window'))
    resolve_src = class_methods(source, "SottoShell", ("_hotkey_resolve",))[
        '_hotkey_resolve']
    add('_caption_window_shown' in _code(resolve_src),
        "o interruptor le' o que o DONO possui (_caption_wanted)")

    return verdict("hotkey-live-toggle")


def _code(src: str) -> str:
    """O corpo SEM docstring -- o que o metodo FAZ, nao o que ele diz."""
    node = ast.parse(src).body[0]
    body = list(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:] or [ast.Pass()]
    return "\n".join(ast.unparse(n) for n in body)


def _call_order(src: str, first: str, second: str) -> str:
    """`before`/`after`/`absent` -- posicao de chamada no corpo executado."""
    node = ast.parse(src).body[0]
    seen = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Call):
            name = ast.unparse(sub.func)
            if name.endswith(first) or name.endswith(second):
                seen.append((sub.lineno, sub.col_offset,
                             'first' if name.endswith(first) else 'second'))
    seen.sort()
    marks = [tag for _, _, tag in seen]
    if 'first' not in marks or 'second' not in marks:
        return 'absent'
    return 'before' if marks.index('first') < marks.index('second') else 'after'


# ---------------------------------------------------------------------------
# --neg-arm: muta uma COPIA e exige RED
# ---------------------------------------------------------------------------
MUTANTS = (
    ("le-a-intencao",
     "            shown = bool(getattr(self, '_caption_window_shown', False))",
     "            shown = bool(getattr(self, '_caption_wanted', False))",
     "o interruptor volta a ler `_caption_wanted` (a intencao, nao o ecra)"),
    ("espera-pelo-ui",
     "                posted = self.exec_js_post(",
     "                posted = self.window.evaluate_js(",
     "a marca do painel volta a `evaluate_js` (bloqueia no UI thread)"),
    ("log-no-fim",
     "            log(f'LIVE_ENABLED on={str(on).lower()} wanted={str(on).lower()} '\n"
     "                f'panel_closed=false')\n",
     "            pass\n",
     "LIVE_ENABLED deixa de sair na decisao"),
)


def _mutate(webview: Path, old: str, new: str):
    target = webview / "sotto_webview.py"
    text = target.read_text(encoding='utf-8')
    if old not in text:
        return None
    target.write_text(text.replace(old, new, 1), encoding='utf-8')
    return True


def neg_arm() -> int:
    failures = 0
    ok_arms = 0
    for name, old, new, note in MUTANTS:
        tmp = Path(tempfile.mkdtemp(prefix='hotkey-toggle-neg-'))
        try:
            webview = tmp / "app" / "webview"
            webview.mkdir(parents=True)
            shutil.copy2(SHELL, webview / "sotto_webview.py")
            shutil.copy2(GESTURE, webview / "hotkey_gesture.py")
            if _mutate(webview, old, new) is None:
                print(f"NEG-ARM {name}: nao consegui mutar (o texto mudou)")
                failures += 1
                continue
            print(f"\n=== NEG-ARM {name}: {note}")
            rc = run(webview / "sotto_webview.py")
            if rc == EXIT_FAIL:
                print(f"NEG-ARM {name} PASS -- RED as designed")
                ok_arms += 1
            else:
                print(f"NEG-ARM {name} FAIL -- o oraculo NAO ve a regressao")
                failures += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print()
    if failures or ok_arms != len(MUTANTS):
        print(f"NEG-ARM FAIL -- {ok_arms}/{len(MUTANTS)} mutantes dados como RED")
        return EXIT_PASS
    print(f"NEG-ARM PASS -- RED as designed: {ok_arms} mutantes derrubam o oraculo")
    return EXIT_FAIL


def main(argv) -> int:
    if "--neg-arm" in argv:
        return neg_arm()
    return run(SHELL)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
