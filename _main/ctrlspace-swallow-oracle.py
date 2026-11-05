#!/usr/bin/env python
# NO-BUG: instrumento da ordem do dono de 2026-11-05 -- o Ctrl+Space nao pode
# escrever um ESPACO nas outras apps, e em JOGO tem de ser a tecla do jogo.
"""ORACLE: Ctrl+Space TOMADO fora de jogo, DEVOLVIDO ao jogo.

ORDEM DO DONO, verbatim (2026-11-05):

    *"faz o control espaço nao inputar espaço pra outros apps. mas desativa isso
    em jogos. entao control espaço em um jogo pode sim apertar espaço. só que nao
    vai ter display de legenda, pra ter, tenho que dar alt c e ativar
    manualmente"*

AS DUAS METADES SAO UMA TABELA SO', e a tabela e' a coisa medida:

  * FORA DE JOGO: `RegisterHotKey` + `MOD_NOREPEAT` -> o Windows entrega
    `WM_HOTKEY` a' shell e NAO entrega a tecla a' janela em foco. E' a mecanica
    que impede o espaco de aparecer no que ele estiver a escrever, sem hook.
  * EM JOGO: `UnregisterHotKey` -> o jogo recebe o `Ctrl+Space` NATIVO (nao ha'
    `SendInput`, logo nao ha' o caso dos jogos com raw input) e a shell nao
    alterna a legenda -- *"nem on nem off"*. A legenda liga-se com o Alt+C.

O QUE ESTE ORACLE MEDE (e o que ele NAO mede: tecla fisica. Um `keybd_event`
mede o Windows e nao a app, e este repo proibe-o):

  A. a TABELA PURA (`gaming_mode.live_hotkey_plan`, a funcao REAL do ficheiro):
     os seis cantos -- jogo/nao, registado/nao, registo recusado.
  B. o FIO REAL (`LiveHotkeyThread`, extraido por `ast` do ficheiro que embarca e
     corrido com um `user32`-GRAVADOR): arranca em `swallow` (um
     `RegisterHotKey`, um `WM_HOTKEY` alterna UMA vez), a entrada em jogo DEVOLVE
     a tecla (`UnregisterHotKey`) e um `WM_HOTKEY` que chegue nesse modo NAO
     alterna nada; a saida do jogo volta a TOMAR; um registo recusado
     (`winerror=1409`) nao mente (`swallow=false`) nem alterna.
  C. a FIACAO no shell (`arm_hotkey_role` / `stop_hotkeys`): o papel `live`
     constroi o `LiveHotkeyThread` com o detector, o recuo observado leva
     `gate=`, e `stop` para o recuo.
  D. o LOG NAO VIRA ENXURADA: o pump relê o modo quatro vezes por segundo, e o
     numero de linhas `HOTKEY_LIVE_MODE` tem de ser o numero de TRANSICOES, nao o
     numero de voltas (a licao do `HOTKEY_OBSERVER_ALIVE`, 720 linhas/hora).

COMO NAO ABRIR NADA EM ECRA. O fio corre com fakes: `RegisterHotKey`,
`UnregisterHotKey`, `MsgWaitForMultipleObjects` e `PeekMessageW` sao de um
gravador -- nenhuma combinacao e' tomada, nenhuma janela e' tocada.

Uso:
    python _main/ctrlspace-swallow-oracle.py            -> rc 0 GREEN / rc 1 RED
    python _main/ctrlspace-swallow-oracle.py --neg-arm  -> muta COPIA(S) e exige RED
    SOTTO_ROOT=<arvore> ...                             -> julga outra arvore
"""
from __future__ import annotations

import ast
import importlib.util as _ilu
import io
import os
import shutil
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get('SOTTO_ROOT') or os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
GAMING = os.path.join(ROOT, 'app', 'webview', 'gaming_mode.py')

RESULTS = []


def check(name, ok, note=''):
    RESULTS.append((name, bool(ok), note))
    print('%-46s %s %s' % (name, 'PASS' if ok else 'FAIL', note), flush=True)
    return bool(ok)


def read(path):
    with io.open(path, encoding='utf-8', newline='') as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# A TABELA, DA FUNCAO REAL
# ---------------------------------------------------------------------------
def load_gaming(path):
    spec = _ilu.spec_from_file_location('gaming_mode_probe_%d' % id(path), path)
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PLAN_CASES = [
    # (gaming, registered, register_failed, esperado)
    (False, False, False, 'take'),        # fora de jogo, livre -> TOMA
    (False, True, False, 'stay-free'),    # ja' tomado -> nada a fazer
    (True, True, False, 'give-back'),     # entrou em jogo -> DEVOLVE
    (True, False, False, 'stay-free'),    # em jogo e livre -> fica do jogo
    (False, False, True, 'stay-free'),    # registo recusado -> nao insiste
    (True, False, True, 'stay-free'),     # em jogo, recusado -> nada
]


def arm_plan(gaming_module, tag=''):
    mod = gaming_module
    ok_all = True
    for gaming, registered, failed, want in PLAN_CASES:
        got = mod.live_hotkey_plan(gaming, registered, failed)
        ok = got == want
        ok_all &= ok
        if not ok:
            check('A plan gaming=%s reg=%s failed=%s%s' % (
                gaming, registered, failed, tag), False,
                'want=%s got=%s' % (want, got))
    check('A tabela take/give-back (6 cantos)%s' % tag, ok_all,
          'funcao REAL gaming_mode.live_hotkey_plan')
    return ok_all


# ---------------------------------------------------------------------------
# O FIO REAL, COM UM user32-GRAVADOR
# ---------------------------------------------------------------------------
import ctypes as _ctypes


class FakeMsg(_ctypes.Structure):
    """Um `MSG` de verdade na forma: o fio faz `ctypes.byref(msg)` e le
    `msg.message`, logo um objecto Python simples nao serve -- `byref` recusa-o."""

    _fields_ = [('hwnd', _ctypes.c_void_p),
                ('message', _ctypes.c_uint),
                ('wParam', _ctypes.c_size_t),
                ('lParam', _ctypes.c_ssize_t),
                ('time', _ctypes.c_uint),
                ('pt', _ctypes.c_long * 2)]


class RecordingUser32(object):
    """Registra o que o fio PEDE e guarda os `WM_HOTKEY` que o sistema poria."""

    WM_HOTKEY = 0x0312

    def __init__(self, conflict=False):
        self.conflict = conflict
        self.register_calls = 0
        self.unregister_calls = 0
        self.registered_ids = set()
        self.queue = []
        self.posted = []
        self.wait_calls = 0
        self.last_error = 1409 if conflict else 0

    def RegisterHotKey(self, hwnd, ident, mods, vk):
        self.register_calls += 1
        assert (mods & 0x4000), 'MOD_NOREPEAT tem de estar posto'
        if self.conflict:
            return 0
        if ident in self.registered_ids:
            return 0
        self.registered_ids.add(ident)
        return 1

    def UnregisterHotKey(self, hwnd, ident):
        self.unregister_calls += 1
        self.registered_ids.discard(ident)
        return 1

    def PeekMessageW(self, msg_ptr, hwnd, lo, hi, flags):
        if not self.queue:
            return 0
        self.queue.pop(0)
        # O fio le `msg.message` do MSG que ELE criou: o gravador tem de escrever
        # no objecto que veio por `ctypes.byref` (senao nada chegaria a ninguem).
        obj = getattr(msg_ptr, '_obj', None)
        if obj is not None:
            obj.message = RecordingUser32.WM_HOTKEY
        return 1

    def MsgWaitForMultipleObjects(self, n, handles, wait_all, ms, mask):
        self.wait_calls += 1
        time.sleep(min(float(ms) / 1000.0, 0.02))
        return 0

    def PostThreadMessageW(self, tid, msg, w, l):
        self.posted.append((msg, w, l))
        return 1

    def press(self):
        self.queue.append(FakeMsg())


def class_node(source, name):
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    return None


class FakeKernel32(object):
    GetCurrentThreadId = staticmethod(lambda: 777)
    SetThreadPriority = staticmethod(lambda *a: 1)
    GetCurrentThread = staticmethod(lambda: -2)


def build_live_thread(shell_source, log_fn, user_fake):
    node = class_node(shell_source, 'LiveHotkeyThread')
    if node is None:
        return None
    namespace = {
        'threading': threading,
        'time': time,
        'user32': user_fake,
        'kernel32': FakeKernel32(),
        'MSG': FakeMsg,
        'PM_REMOVE': 0x0001,
        'WM_HOTKEY': RecordingUser32.WM_HOTKEY,
        'WM_APP': 0x8000,
        '_HOTKEY_ID': 0xB0F0,
        'MOD_NOREPEAT': 0x4000,
        'QS_ALLINPUT': 0x04FF,
        'LIVE_MODE_RECHECK_S': 0.001,
        'parse_accelerator': lambda acc: (0x0002, 0x20),
        'log': log_fn,
        '__builtins__': __builtins__,
    }
    namespace['ctypes'] = _ctypes
    exec(compile(ast.Module(body=[node], type_ignores=[]),
                 '<live-hotkey>', 'exec'), namespace)
    return namespace['LiveHotkeyThread']


class FakeLog(object):
    def __init__(self):
        self.lines = []
        self._lock = threading.Lock()

    def __call__(self, message, *a, **k):
        with self._lock:
            self.lines.append(str(message))

    def has(self, needle):
        return any(needle in line for line in self.lines)

    def count(self, needle):
        return sum(1 for line in self.lines if needle in line)


def settle(thread, loops=6):
    deadline = time.time() + 3.0
    start = thread.loops
    while time.time() < deadline and thread.loops < start + loops:
        time.sleep(0.01)


def arm_thread(shell_source, gaming_module, tag=''):
    """B: o fio REAL, com o modo mudado por fora (como o detector faz)."""
    import sys as _sys
    saved = _sys.modules.get('gaming_mode')
    _sys.modules['gaming_mode'] = gaming_module
    ok = True
    try:
        state = {'gaming': False}
        log = FakeLog()
        user = RecordingUser32()
        ours = 0

        def on_hotkey():
            state['toggles'] = state.get('toggles', 0) + 1

        cls = build_live_thread(shell_source, log, user)
        if cls is None:
            check('B classe LiveHotkeyThread existe%s' % tag, False, 'ausente')
            return False
        state['toggles'] = 0
        thread = cls('Ctrl+Space', on_hotkey,
                     gaming_fn=lambda: state['gaming'], log_fn=log)
        thread.start()
        thread.wait_ready(2.0)
        ok &= check('B1 fora de jogo TOMA a tecla%s' % tag,
                    thread.registered and user.register_calls == 1,
                    'registered=%s register_calls=%d mode=%s'
                    % (thread.registered, user.register_calls, thread.mode))
        user.press()
        settle(thread, 4)
        ok &= check('B2 um WM_HOTKEY alterna UMA vez%s' % tag,
                    state['toggles'] == 1,
                    'toggles=%d' % state['toggles'])

        # entra em jogo: a tecla tem de VOLTAR ao jogo antes de qualquer pressao
        state['gaming'] = True
        settle(thread, 4)
        ok &= check('B3 entrada em jogo DEVOLVE a tecla%s' % tag,
                    (not thread.registered) and user.unregister_calls >= 1
                    and thread.mode == 'passthrough',
                    'registered=%s unregister_calls=%d mode=%s'
                    % (thread.registered, user.unregister_calls, thread.mode))
        before = state['toggles']
        user.press()
        settle(thread, 4)
        ok &= check('B4 em jogo NAO alterna nada%s' % tag,
                    state['toggles'] == before,
                    'toggles=%d->%d' % (before, state['toggles']))

        # sai do jogo: volta a TOMAR
        state['gaming'] = False
        settle(thread, 4)
        ok &= check('B5 saida do jogo volta a TOMAR%s' % tag,
                    thread.registered and thread.mode == 'swallow'
                    and user.register_calls == 2,
                    'registered=%s register_calls=%d'
                    % (thread.registered, user.register_calls))

        # D: uma linha por transicao, nunca por volta
        modes = log.count('HOTKEY_LIVE_MODE')
        loops = thread.loops
        ok &= check('D log por TRANSICAO, nao por volta%s' % tag,
                    modes <= 3 and loops >= 8,
                    'linhas_mode=%d voltas=%d' % (modes, loops))

        thread.stop()
        thread.join(2.0)
        ok &= check('B6 stop DEVOLVE a tecla%s' % tag,
                    not thread.registered and user.unregister_calls >= 2,
                    'registered=%s unregister_calls=%d'
                    % (thread.registered, user.unregister_calls))

        # B7: o registo recusado nao mente
        log2 = FakeLog()
        user2 = RecordingUser32(conflict=True)
        # A CLASSE CARREGA O GRAVADOR DENTRO DAS SUAS GLOBAIS: reconstrui-la com o
        # gravador do braco, senao o `RegisterHotKey` do conflito ia para o
        # gravador do braco anterior e o braco media o objecto errado.
        cls2 = build_live_thread(shell_source, log2, user2)
        thread2 = cls2('Ctrl+Space', on_hotkey,
                       gaming_fn=lambda: False, log_fn=log2)
        thread2.start()
        thread2.wait_ready(2.0)
        settle(thread2, 3)
        ok &= check('B7 registo recusado (1409) diz swallow=false%s' % tag,
                    (not thread2.registered) and thread2.register_failed
                    and log2.has('HOTKEY_LIVE_REGISTER_FAILED')
                    and log2.has('swallow=false'),
                    'register_error=%s lines=%d'
                    % (thread2.register_error, len(log2.lines)))
        thread2.stop()
        thread2.join(2.0)
    finally:
        if saved is not None:
            _sys.modules['gaming_mode'] = saved
        else:
            _sys.modules.pop('gaming_mode', None)
    return ok


# ---------------------------------------------------------------------------
# C: a FIACAO
# ---------------------------------------------------------------------------
def arm_wiring(shell_source, tag=''):
    ok = True
    role = None
    try:
        tree = ast.parse(shell_source)
    except SyntaxError as exc:
        check('C shell parseia%s' % tag, False, repr(exc))
        return False
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'arm_hotkey_role':
            role = ast.get_source_segment(shell_source, node) or ''
    ok &= check('C1 arm_hotkey_role existe%s' % tag, bool(role))
    if not role:
        return False
    # C2 E' AST, NAO TEXTO (2026-11-05). Um `grep` do ramo nao distingue "com o
    # detector constroi o fio que TOMA a tecla" de "constroi-o sempre": o mutante
    # que troca `if _gaming is None:` por `if True:` continua a ter as duas
    # palavras no mesmo ramo, e o texto dava-lhe verde. O que se exige e' a
    # ESTRUTURA: o `If` do teste `_gaming is None` tem no `orelse` a chamada a
    # `LiveHotkeyThread(... gaming_fn=...)` e no `body` o observador.
    live_call = None
    none_body = None
    for node in ast.walk(ast.parse(shell_source)):
        if not isinstance(node, ast.If):
            continue
        # O TESTE E' LIDO DA ARVORE, NAO DO TEXTO (2026-11-05). A primeira versao
        # pedia `get_source_segment` para cada `If` do ficheiro: essa funcao
        # parte a FONTE INTEIRA em linhas a cada chamada, e um shell de 21 mil
        # linhas tem milhares de `If` -- medido **155 s por mutante** contra 1 s
        # do oraculo inteiro. A `Compare(_gaming is None)` ve-se nos nos.
        _test = node.test
        _is_gaming_none = (
            isinstance(_test, ast.Compare)
            and isinstance(_test.left, ast.Name) and _test.left.id == '_gaming'
            and len(_test.ops) == 1 and isinstance(_test.ops[0], ast.Is)
            and len(_test.comparators) == 1
            and isinstance(_test.comparators[0], ast.Constant)
            and _test.comparators[0].value is None)
        if not _is_gaming_none:
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                fname = getattr(sub.func, 'id', getattr(sub.func, 'attr', ''))
                if fname == 'LiveHotkeyThread':
                    live_call = sub
        none_body = node.body
        break
    live_kwargs = set()
    if live_call is not None:
        live_kwargs = {k.arg for k in live_call.keywords if k.arg}
    body_names = set()
    for sub in (none_body or []):
        for inner in ast.walk(sub):
            if isinstance(inner, ast.Call):
                fname = getattr(inner.func, 'id', getattr(inner.func, 'attr', ''))
                body_names.add(fname)
    ok &= check('C2 o detector-presente constroi LiveHotkeyThread(gaming_fn=)%s' % tag,
                live_call is not None and 'gaming_fn' in live_kwargs)
    ok &= check('C2b sem detector fica o OBSERVADOR%s' % tag,
                'PassiveHotkeyThread' in body_names)
    ok &= check('C3 o recuo observado leva gate=%s' % tag,
                'gate=' in role and 'PassiveHotkeyThread' in role)
    obs = None
    stop_body = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'PassiveHotkeyThread':
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == '__init__':
                    obs = ast.get_source_segment(shell_source, sub) or ''
        if isinstance(node, ast.ClassDef) and node.name == 'LiveHotkeyThread':
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef) and sub.name == 'stop':
                    stop_body = ast.get_source_segment(shell_source, sub) or ''
    ok &= check('C4 o observador aceita gate%s' % tag,
                bool(obs) and 'gate' in obs)
    ok &= check('C5 stop do fio para o recuo%s' % tag,
                bool(stop_body) and 'fallback' in stop_body)
    return ok


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------
def run(root=None, tag=''):
    shell_path = os.path.join(root, 'app', 'webview', 'sotto_webview.py') if root else SHELL
    gaming_path = os.path.join(root, 'app', 'webview', 'gaming_mode.py') if root else GAMING
    shell_source = read(shell_path)
    gaming_module = load_gaming(gaming_path)
    ok = arm_plan(gaming_module, tag)
    ok &= arm_wiring(shell_source, tag)
    ok &= arm_thread(shell_source, gaming_module, tag)
    return ok


MUTANTS = []


def mutate(path, old, new, label):
    src = read(path)
    # A ANCORA ESCREVE-SE COM `\n`; O FICHEIRO DESTA CASA E' CRLF. Traduzir a
    # ancora pelo newline do alvo e' o que impede um mutante "impossivel" que na
    # verdade e' uma ancora escrita noutra convencao (licao do `paint-live-show`).
    nl = '\r\n' if '\r\n' in src else '\n'
    if nl != '\n':
        old = old.replace('\n', nl)
        new = new.replace('\n', nl)
    if old not in src:
        raise SystemExit('MUTACAO IMPOSSIVEL: %s -- ancora ausente' % label)
    with io.open(path, 'w', encoding='utf-8', newline='') as fh:
        fh.write(src.replace(old, new, 1))


def neg_arm():
    tmp = tempfile.mkdtemp(prefix='sotto-ctrlspace-neg-')
    caught = 0
    try:
        for label, apply in _MUTATORS:
            tree = os.path.join(tmp, label)
            os.makedirs(os.path.join(tree, 'app', 'webview'))
            for name in ('sotto_webview.py', 'gaming_mode.py'):
                shutil.copy2(os.path.join(ROOT, 'app', 'webview', name),
                             os.path.join(tree, 'app', 'webview', name))
            apply(os.path.join(tree, 'app', 'webview'))
            global RESULTS
            saved = RESULTS
            RESULTS = []
            import contextlib
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    ok = run(tree, tag=' [%s]' % label)
            except SystemExit:
                raise
            except Exception as exc:  # noqa: BLE001 -- um mutante que rebenta e' RED
                ok = False
                buf.write('EXCEPTION %r\n' % (exc,))
            RESULTS = saved
            if not ok:
                caught += 1
                print('NEG-ARM %-38s RED' % label, flush=True)
            else:
                failed = [n for n, ok_, _ in RESULTS if not ok_]
                print('NEG-ARM %-38s NOT-CAUGHT arms=%s' % (label, failed or 'all'),
                      flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('NEG-ARM: %s (%d/%d mutantes apanhados)'
          % ('PASS' if caught == len(_MUTATORS) else 'FAIL', caught, len(_MUTATORS)))
    return 1 if caught == len(_MUTATORS) else 0


def _m1(webview_dir):
    # a tabela deixa de devolver a tecla ao jogo
    mutate(os.path.join(webview_dir, 'gaming_mode.py'),
           "    if gaming:\n        return 'give-back' if registered else 'stay-free'",
           "    if gaming:\n        return 'take' if not registered else 'stay-free'",
           'plano-nao-devolve-a-tecla')


def _m2(webview_dir):
    # o fio ignora a tabela e toma a tecla sempre que pode
    p = os.path.join(webview_dir, 'sotto_webview.py')
    mutate(p, "        if plan == 'take':", "        if True:", 'fio-toma-sempre')


def _m3(webview_dir):
    # a fiacao perde o detector: papel live volta ao observador
    p = os.path.join(webview_dir, 'sotto_webview.py')
    mutate(p, "                if _gaming is None:", "                if True:",
           'sem-detector' )


def _m4(webview_dir):
    # o log volta a publicar em cada volta (enxurrada)
    p = os.path.join(webview_dir, 'sotto_webview.py')
    mutate(p, "        if self.mode != getattr(self, '_published_mode', None):",
           "        if True:", 'log-por-volta')


_MUTATORS = [
    ('plano-nao-devolve-a-tecla', _m1),
    ('fio-toma-sempre', _m2),
    ('ficacao-sem-detector', _m3),
    ('log-por-volta', _m4),
]


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    ok = run(None, tag='')
    print('CTRLSPACE-SWALLOW VERDICT: %s (%d/%d)'
          % ('PASS' if ok else 'FAIL',
             sum(1 for _, ok_, _ in RESULTS if ok_), len(RESULTS)))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
