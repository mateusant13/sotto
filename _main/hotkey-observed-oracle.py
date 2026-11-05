# NO-BUG: A TECLA DA LEGENDA E' OBSERVADA, NUNCA TOMADA -- oraculo. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""A TECLA DA LEGENDA E' OBSERVADA, NUNCA TOMADA -- oraculo.

ORDEM DO DONO (2026-11-02), verbatim: *"control mais espaço é crouch e jump no
jogo. nao ta funcionando no jogo, por causa do sotto. faz os dois serem
possiveis"*.

O DEFEITO MEDIDO. `RegisterHotKey` TOMA a combinacao para o processo que a
registou: enquanto o Sotto vive, o `Ctrl+Space` nunca chega a outra janela. O
jogo do dono perdeu o crouch+jump.

O QUE ESTE ORACULO JULGA, com a leitura de estado INJECTADA (`key_state=`), que
e' o unico jeito de exercitar a borda sem tocar no teclado dele:

  1. uma pressao  -> UM disparo;
  2. segurada     -> ZERO disparos extra (a borda, nao o nivel);
  3. largar e pressionar outra vez -> o segundo disparo;
  4. so' um dos dois lados da combinacao -> ZERO;
  5. a classe NAO REGISTA (sem `RegisterHotKey` no corpo) e publica
     `HOTKEY_OBSERVED ... the_key_passes_through=true`;
  6. FIACAO: o papel `live` do `arm_hotkey_role` constroi a classe observada, e
     os PAINEIS continuam registados (um Alt+C tomado e' o que se quer ali);
  7. NEG-ARM: numa COPIA do ficheiro, o guarda `held` e' desligado e a arm 2 tem
     de cair -- um detractor que nao derruba o proprio braco nao prova nada.

USO:
    python _main/hotkey-observed-oracle.py            # arms 1-6
    python _main/hotkey-observed-oracle.py --neg-arm  # arm 7
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import os
import re
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WEBVIEW = os.path.join(ROOT, 'app', 'webview')


def load_shell(path=SHELL, name='sotto_webview_oracle_mod'):
    """O shell inteiro, por caminho: os irmaos vivem ao lado dele, nao no sys.path."""
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Clock(object):
    """Uma sequencia de estados de tecla, entregue um por leitura."""

    def __init__(self, states, per_iteration=1):
        """`per_iteration` = quantas LEITURAS uma volta do laco consome.

        ESTE NUMERO E' O QUE FALTAVA (medido 2026-11-03). A borda da combinacao
        le' um VK por VARIANTE (`Ctrl` = LCONTROL, RCONTROL e CONTROL) mais a
        tecla: `Ctrl+Space` consome **4** leituras por volta. O relogio antigo
        entregava um estado por LEITURA, logo a sequencia `[baixo, baixo,
        largado, largado]` descrevia uma volta e meia e a arm 3 acusava o
        produto (`release-then-press-again RED disparos=1`) por um desalinhado
        do instrumento -- medido: com um relogio por VOLTA o MESMO codigo dispara
        2 vezes. Um instrumento que inventa o defeito e' tao caro como um que o
        esconde.
        """
        self.states = list(states)
        self.per_iteration = max(1, int(per_iteration))
        self.i = 0
        self.calls = 0
        self.lock = threading.Lock()

    def __call__(self, vk):
        with self.lock:
            if self.i < len(self.states):
                state = self.states[self.i]
            else:
                state = self.states[-1] if self.states else set()
            self.calls += 1
            if self.calls % self.per_iteration == 0:
                self.i += 1
        return vk in state


def run_sequence(shell_mod, presses, poll_s=0.002, settle=0.05):
    """Poe a combinacao e conta os disparos, com a leitura injectada."""
    fired = []
    # Quantas leituras uma volta consome: vem da PROPRIA classe, para o numero
    # nao ser uma segunda verdade (um `+1` por variante de modificador novo
    # mudaria isto em silencio).
    _probe = shell_mod.PassiveHotkeyThread(
        'Ctrl+Space', lambda: None, log_fn=lambda line: None,
        key_state=lambda vk: False)
    per_iteration = sum(len(g) for g in _probe.key_groups) or 1
    clock = Clock(presses, per_iteration)
    thread = shell_mod.PassiveHotkeyThread(
        'Ctrl+Space', lambda: fired.append(time.monotonic()),
        log_fn=lambda line: None, poll_s=poll_s, key_state=clock)
    thread.start()
    deadline = time.monotonic() + max(0.4, len(presses) * poll_s * 4 + settle)
    while time.monotonic() < deadline:
        time.sleep(0.005)
    thread.stop()
    thread.join(2.0)
    return fired


def _wiring_arm(shell_mod):
    """(nome, ok, nota): o papel -> a CLASSE, medido na funcao que o faz."""
    made = []

    class _Recorder(object):
        registered = True
        register_failed = False
        register_error = 0

        def __init__(self, accelerator, callback, *a, **kw):
            self.accelerator = accelerator
            self.kw = kw
            made.append((type(self).__name__, kw.get('role')))

        def start(self):
            return self

        def wait_ready(self, _timeout=None):
            return True

        def stop(self):
            return None

        def join(self, _timeout=None):
            return None

    classes = {}
    for name in ('PassiveHotkeyThread', 'LiveHotkeyThread', 'HotkeyThread'):
        classes[name] = type(name, (_Recorder,), {})
    saved = {n: getattr(shell_mod, n, None) for n in classes}
    for n, cls in classes.items():
        setattr(shell_mod, n, cls)

    def _shell(gaming):
        s = type('S', (), {})()
        s.hotkey_live = lambda: None
        s.hotkey_pressed = lambda: None
        if gaming is not None:
            s.gaming = gaming
        return s

    _gaming = type('G', (), {'is_gaming': staticmethod(lambda: False)})()
    live_cls, panel_cls, fallback_cls = [], [], []
    try:
        shell_mod.arm_hotkey_role(_shell(_gaming), 'live', 'Ctrl+Space', [])
        shell_mod.arm_hotkey_role(_shell(_gaming), 'panels', 'Alt+C', [])
        live_cls = [c for c, r in made if r == 'live']
        panel_cls = [c for c, r in made if r == 'panels']
        made[:] = []
        shell_mod.arm_hotkey_role(_shell(None), 'live', 'Ctrl+Space', [])
        fallback_cls = [c for c, r in made if r == 'live']
    finally:
        for n, obj in saved.items():
            if obj is not None:
                setattr(shell_mod, n, obj)
    ok = (live_cls[:1] == ['LiveHotkeyThread']
          and panel_cls[:1] == ['HotkeyThread']
          and fallback_cls[:1] == ['PassiveHotkeyThread'])
    return ('wiring-by-role', ok,
            'live=%s panels=%s live-sem-detector=%s'
            % (live_cls[:1], panel_cls[:1], fallback_cls[:1]))


CTRL, SPACE = 0x11, 0x20


def arms(shell_mod):
    """Cada arm devolve `(nome, passou, nota)`."""
    out = []

    # 1. UMA PRESSAO = UM DISPARO. Dois ciclos de leitura com tudo em baixo e o
    # resto largado: a borda de descida dispara uma vez, e mais nada.
    fired = run_sequence(shell_mod, [{CTRL}, {CTRL, SPACE}, {CTRL, SPACE}, {CTRL}, set()])
    out.append(('one-press-one-shot', len(fired) == 1,
                'disparos=%d (esperado 1)' % len(fired)))

    # 2. SEGURADA NAO METRALHA. Doze leituras com a combinacao em baixo.
    held = [{CTRL, SPACE}] * 12 + [set()]
    fired = run_sequence(shell_mod, held)
    out.append(('held-fires-once', len(fired) == 1,
                'disparos=%d com 12 leituras em baixo (esperado 1)' % len(fired)))

    # 3. LARGAR E VOLTAR A PRESSIONAR = DOIS DISPAROS.
    twice = ([{CTRL, SPACE}] * 2 + [set()] * 2) * 2
    fired = run_sequence(shell_mod, twice)
    out.append(('release-then-press-again', len(fired) == 2,
                'disparos=%d (esperado 2)' % len(fired)))

    # 4. SO' UM LADO DA COMBINACAO NAO E' O GESTO.
    fired = run_sequence(shell_mod, [{CTRL}] * 8 + [set()])
    only_ctrl = len(fired)
    fired = run_sequence(shell_mod, [{SPACE}] * 8 + [set()])
    only_space = len(fired)
    out.append(('partial-combo-is-not-the-gesture',
                only_ctrl == 0 and only_space == 0,
                'ctrl-sozinho=%d space-sozinho=%d (esperado 0/0)'
                % (only_ctrl, only_space)))

    # 5. A CLASSE NAO TOMA A TECLA. Duas metades: o FONTE nao regista, e a linha
    #    que ela escreve ao armar diz que a tecla PASSA.
    text = io.open(SHELL, encoding='utf-8', errors='replace').read()
    start = text.index('class PassiveHotkeyThread')
    end = text.index('def arm_hotkey_role', start)
    body = text[start:end]
    registers = 'RegisterHotKey(' in body
    declared = 'the_key_passes_through=true' in body
    out.append(('does-not-register', (not registers) and declared,
                'RegisterHotKey=%s passes_through=%s' % (registers, declared)))

    # 6. FIACAO POR PAPEL, MEDIDA PELA FUNCAO REAL (2026-11-05).
    #
    # ESTA ARM LIA TEXTO (`if role == 'live':` seguido de `PassiveHotkeyThread(`)
    # e por isso mentia nos dois sentidos: ficou VERMELHA quando a ordem do dono
    # (`Ctrl+Space` = legenda, `Alt+C` = paineis) mudou o desenho -- `live` passou
    # a ser `LiveHotkeyThread` com detector de jogo e o `PassiveHotkeyThread` ficou
    # como RECUO -- sem que nada estivesse quebrado; e teria ficado VERDE com a
    # fiacao trocada desde que o texto casasse. O papel -> a classe e' uma decisao
    # que se EXECUTA: `arm_hotkey_role` real, com os tres threads substituidos por
    # registadores, zero `RegisterHotKey`, zero tecla tomada.
    out.append(_wiring_arm(shell_mod))

    # 7. A TECLA DE PEDRA RE-ARMA SOZINHA (2026-11-03). A evidencia do produto:
    #    `HOTKEY_PRESSED role=live count=1 source=observed` DUAS vezes na historia
    #    inteira do log do dono (03:22:19 e 04:56:26) e **nunca um `count=2`** --
    #    dentro de um arranque, a segunda pressao nunca disparou. A descida e'
    #    perdida com facilidade (o laco publicou `max_gap_ms=219`) e o `held`
    #    ficava `True` para sempre: a tecla morria ate' reiniciar a app.
    lines = []
    fired_stuck = []
    stuck_clock = Clock([{CTRL, SPACE}] * 4000)
    th = shell_mod.PassiveHotkeyThread(
        'Ctrl+Space', lambda: fired_stuck.append(1), log_fn=lines.append,
        poll_s=0.01, key_state=stuck_clock)
    th.start()
    time.sleep(3.4)
    th.stop()
    th.join(2.0)
    said = any('HOTKEY_STATE_STUCK' in l for l in lines)
    out.append(('stuck-key-rearms', len(fired_stuck) >= 2 and said,
                'disparos=%d stuck_log=%s (esperado >=2 e a linha)'
                % (len(fired_stuck), said)))
    return out


def neg_arm():
    """MUTACAO: sem o guarda `held`, o arm 2 tem de cair."""
    text = io.open(SHELL, encoding='utf-8', errors='replace').read()
    # A ANCORA ACOMPANHA A CURA (2026-11-04, terceira vez): o guarda le hoje
    # `if mods_ready and (fresh or (down and not held)):` -- as duas ancoras anteriores
    # (`if (down or fresh) and not held:` e `if not any(_v & 0x0001 ...)`) ficaram ausentes
    # e o braco negativo publicava 'ancora ausente' com rc=1, um rc que a bateria aceita
    # como se o mutante tivesse caido: o passo passava a provar NADA. O mutante e' o mesmo
    # (tira o `held`, o guarda metralha), e o --neg-arm exige a frase NEG-ARM no log.
    old = '            if mods_ready and (fresh or (down and not held)):'
    if old not in text:
        print('NEG-ARM: FAIL -- o corpo do guarda nao esta no ficheiro (ancora ausente)')
        return 1
    mutant = text.replace(old, '            if down:', 1)
    tmpdir = tempfile.mkdtemp(prefix='sotto-neg-hotkey-')
    path = os.path.join(tmpdir, 'sotto_webview.py')
    io.open(path, 'w', encoding='utf-8', newline='').write(mutant)
    try:
        module = load_shell(path, name='sotto_webview_oracle_mutant')
        held = [{CTRL, SPACE}] * 12 + [set()]
        fired = run_sequence(module, held)
    finally:
        try:
            os.remove(path)
            os.rmdir(tmpdir)
        except OSError:
            pass
    caught = len(fired) > 1
    print('NEG-ARM %-18s %s  disparos=%d (mutante sem `held` tem de metralhar)'
          % ('held-removed', 'PASS' if caught else 'FAIL', len(fired)))

    # MUTANTE 2: sem o re-armar da tecla de pedra, o arm 7 tem de cair.
    stuck_anchor = 'elif _now_loop - self._down_since >= 3.0:'
    if stuck_anchor not in text:
        print('NEG-ARM: FAIL -- a ancora do re-armar (tecla de pedra) nao esta no ficheiro')
        return 1
    mutant2 = text.replace(stuck_anchor, 'elif False:', 1)
    path2 = os.path.join(tmpdir, 'sotto_webview_stuck.py')
    io.open(path2, 'w', encoding='utf-8', newline='').write(mutant2)
    lines2 = []
    fired2 = []
    try:
        module2 = load_shell(path2, name='sotto_webview_oracle_mutant_stuck')
        th2 = module2.PassiveHotkeyThread(
            'Ctrl+Space', lambda: fired2.append(1), log_fn=lines2.append,
            poll_s=0.01, key_state=Clock([{CTRL, SPACE}] * 4000))
        th2.start()
        time.sleep(3.4)
        th2.stop()
        th2.join(2.0)
    finally:
        try:
            os.remove(path2)
        except OSError:
            pass
    caught2 = not (len(fired2) >= 2 and any('HOTKEY_STATE_STUCK' in l for l in lines2))
    print('NEG-ARM %-18s %s  disparos=%d (mutante sem re-armar tem de ficar em %d)'
          % ('stuck-no-rearm', 'PASS' if caught2 else 'FAIL', len(fired2), 1))
    caught = caught and caught2
    # A CONVENCAO DA BATERIA (2026-11-03): um `red-as-expected` declara rc=1.
    # "Apanhei todos os mutantes" E' o resultado VERMELHO que o `:expectred`
    # exige, senao o passo passa como se fosse um oraculo normal e o mutante
    # nunca e' recusado. rc=0 quando um mutante escapa (o passo fica vermelho
    # de verdade, e com a frase FAIL no log).
    return 1 if caught else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return neg_arm()
    module = load_shell()
    results = arms(module)
    bad = 0
    for name, ok, note in results:
        print('%-38s %s  %s' % (name, 'GREEN' if ok else 'RED', note))
        if not ok:
            bad += 1
    print('VERDICT: %s (%d/%d arms)' % ('PASS' if bad == 0 else 'FAIL',
                                        len(results) - bad, len(results)))
    return 0 if bad == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
