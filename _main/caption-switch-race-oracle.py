# NO-BUG: O INTERRUPTOR DA LEGENDA E' LIDO NA PINTURA, NAO NO ENFILEIRAR (2026-11-05).
"""O INTERRUPTOR DA LEGENDA E' LIDO NA PINTURA, NAO NO ENFILEIRAR (2026-11-05).

MEDIDO na sessao viva do dono (pid 54040), verbatim: *"eu to vendo o botao do
sotto falando que a legenda ta off, mas ta on"*. O log dele, na mesma janela:

    16:15:38.096 HOTKEY_PRESSED role=live count=1 source=registered
    16:15:38.100 LIVE_ENABLED on=false wanted=false
    16:15:38.822 HOTKEY_PRESSED role=live count=2
    16:15:38.823 LIVE_ENABLED on=true  wanted=true
    ...                      (sete idas e voltas em 2,4 s)
    16:15:40.484 LIVE_ENABLED on=false wanted=false   <- o botao pinta OFF
    16:15:42.490 HOTKEY_PRESSED role=live count=8     <- ele "desbogou"

Sete passos alternados deixam o interruptor em OFF, e o botao pintou o que o
shell disse. O que nao obedeceu foi O ECRAN.

A CAUSA E' UMA CORRIDA ENTRE DUAS THREADS, e ela tem duas metades:
  * `push_caption_to_window` pergunta pela flag quando ENFILEIRA (thread do
    worker/produtor);
  * `_drain_caption_pending` pinta o slot na thread `sotto-caption-paint`.
Um texto aceito ANTES do desligar chega ao `_drain` DEPOIS do `ov.show(False)`
e chamava `ov.show(True)` sem perguntar nada: a janela volta com o interruptor
em OFF e nada a esconde outra vez.

O QUE ESTE ORACULO EXECUTA. `SottoShell._drain_caption_pending` e
`SottoShell.show_caption_window` REAIS, extraidas do arquivo por AST e
executadas com os globais injectados (`log`, `json`, `time`, `bisect`) sobre um
`self` falso com um overlay GRAVADOR. Nao e' uma copia: se a shell mudar a
funcao, este passo muda com ela.

BRACO NEGATIVO (`--neg-arm`): apaga o guarda numa COPIA do fonte e exige o
vermelho do arm A1.
"""
from __future__ import annotations

import ast
import bisect  # noqa: F401 -- global do `_drain` real
import io
import json
import sys
import time
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHELL = REPO / 'app' / 'webview' / 'sotto_webview.py'

CASES = []


def add(ok, label, detail=''):
    CASES.append((bool(ok), label, detail))
    print(('GREEN ' if ok else 'RED   ') + label + (('  ' + detail) if detail else ''))
    return bool(ok)


def verdict(name, rc_expected=0):
    passed = sum(1 for ok, _, _ in CASES if ok)
    failed = len(CASES) - passed
    print()
    if failed:
        print('%s VERMELHO -- arms=%d pass=%d fail=%d (rc=1)'
              % (name, len(CASES), passed, failed))
        return 1
    print('%s GREEN -- arms=%d pass=%d fail=%d (rc=%d)'
          % (name, len(CASES), passed, failed, rc_expected))
    return rc_expected


# -- a extracao: o texto-fonte EXATO do metodo, por AST ----------------------
def extract_method(src: str, name: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'SottoShell':
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == name:
                    lines = src.splitlines(keepends=True)
                    body = lines[member.lineno - 1:member.end_lineno]
                    indent = ' ' * member.col_offset
                    return ''.join(
                        line[len(indent):] if line.startswith(indent) else line
                        for line in body
                    )
    raise SystemExit('SottoShell.%s nao existe no fonte' % name)


class Overlay:
    """O overlay gravador: diz o que lhe fazem, nao desenha nada."""

    def __init__(self):
        self.hwnd = 777
        self.calls = []

    def set_work_area(self, *a, **k):
        self.calls.append(('set_work_area',))

    def set_text(self, *a, **k):
        self.calls.append(('set_text', a[0] if a else k.get('text')))

    def show(self, on=True):
        self.calls.append(('show', bool(on)))
        return True

    def hide(self):
        self.calls.append(('hide',))


def build(fn_src, extra_globals=None):
    logs = []
    namespace = {
        'log': lambda msg: logs.append(str(msg)),
        '_ORACLE_LOGS': logs,
        'json': json,
        'time': time,
        'bisect': bisect,
        '__builtins__': __builtins__,
    }
    namespace.update(extra_globals or {})
    exec(compile(fn_src, '<shell-method>', 'exec'), namespace)
    return namespace, logs


def shell_for(namespace, overlay):
    """Um `self` minimo com tudo o que as duas funcoes leem."""
    posted = []

    def _post(fn):
        posted.append(fn)
        return True

    state = types.SimpleNamespace(
        caption_overlay=overlay,
        display={'scaleFactor': 1.0},
        work_area=lambda: {'width': 1920, 'height': 1080, 'left': 0, 'top': 0},
        _post=_post,
        exec_js_post=lambda js: True,
        _caption_pending=None,
        _caption_pending_instant=False,
        _caption_pending_cue=None,
        _caption_coalesced=0,
        _caption_drain_posted=False,
        _caption_ages=None,
        _caption_ordered=None,
        _caption_over_win=0,
        _caption_held_win=0,
        _caption_live_win=0,
        _caption_notes=0,
        _caption_lag_blown=0,
        _caption_hold=0,
        _caption_window_shown=False,
        _caption_wanted=False,
        _source_epoch=3,
        _overlay_pushes=0,
        _caption_painted='',
        _caption_pending_tap_ms=None,
        CAPTION_BUDGET_MS=1500,
        CAPTION_HOLD_BAND_MS=(1490, 1520),
        CAPTION_REPLAY_MAX_S=2.0,
    )
    for name, fn in namespace.items():
        if callable(fn) and name.startswith('_') is False:
            setattr(state, name, fn)
    # os metodos extraidos precisam de resolver `self.<metodo>` para eles proprios
    for name in ('_drain_caption_pending', 'show_caption_window', '_caption_lag_sample'):
        if name in namespace:
            setattr(state, name, namespace[name])
    state._posted = posted
    # o `self` falso nao tem acesso directo ao `log` do namespace; guardamo-lo
    if '_ORACLE_LOGS' in namespace:
        state._oracle_logs = namespace['_ORACLE_LOGS']
    return state


# -- os arms ----------------------------------------------------------------
def arms(src):
    drain_src = extract_method(src, '_drain_caption_pending')
    window_src = extract_method(src, 'show_caption_window')
    namespace, _ = build(drain_src)
    ns2, _ = build(window_src)
    namespace.update({k: v for k, v in ns2.items() if k.startswith('show_caption_window')})

    # A1: o interruptor em OFF -- nada pinta, e a linha diz por que
    ov = Overlay()
    sh = shell_for(namespace, ov)
    sh._caption_wanted = False
    sh._caption_pending = (time.time() - 0.05, 'a legenda que ele desligou', '', 3)
    namespace['_drain_caption_pending'](sh)
    shows = [c for c in ov.calls if c[0] == 'show']
    add(not shows,
        'A1 interruptor OFF: o `_drain` NAO chama `ov.show`',
        'calls=%r' % (ov.calls,))
    add(sh._caption_pending is None,
        'A1b o slot foi consumido (nao fica armado para depois)',
        'pending=%r' % (sh._caption_pending,))

    # A2: o interruptor em ON -- a MESMA funcao pinta (o guarda nao e' um muro)
    ov2 = Overlay()
    sh2 = shell_for(namespace, ov2)
    sh2._caption_wanted = True
    sh2._caption_pending = (time.time() - 0.05, 'uma legenda viva', '', 3)
    namespace['_drain_caption_pending'](sh2)
    texts = [c for c in ov2.calls if c[0] == 'set_text']
    shows2 = [c for c in ov2.calls if c[0] == 'show']
    add(bool(texts) and texts[0][1] == 'uma legenda viva',
        'A2 interruptor ON: o `_drain` pinta o texto do slot',
        'calls=%r' % (ov2.calls[:4],))
    add(bool(shows2) and shows2[0][1] is True,
        'A2b interruptor ON: e mostra a janela', 'shows=%r' % (shows2,))

    # A3: desligar mata o slot
    ov3 = Overlay()
    sh3 = shell_for(namespace, ov3)
    sh3._caption_pending = (time.time(), 'texto enfileirado antes do OFF', '', 3)
    ns2['show_caption_window'](sh3, False)
    add(sh3._caption_pending is None,
        'A3 `show_caption_window(False)` limpa o slot pendente',
        'pending=%r' % (sh3._caption_pending,))
    add(any(c[0] == 'show' and c[1] is False for c in ov3.calls) or bool(sh3._posted),
        'A3b e esconde a janela (por post, que e o caminho do UI thread)',
        'calls=%r posted=%d' % (ov3.calls, len(sh3._posted)))

    # A4: ligar NAO limpa o slot -- a cura nao pode virar "liga e perde linha"
    ov4 = Overlay()
    sh4 = shell_for(namespace, ov4)
    sh4._caption_wanted = True
    ns2['show_caption_window'](sh4, True)
    add(any(c[0] == 'show' and c[1] is True for c in ov4.calls) or bool(sh4._posted),
        'A4 `show_caption_window(True)` mostra',
        'calls=%r posted=%d' % (ov4.calls, len(sh4._posted)))

    # -- LIGAR NAO ESPERA A PROXIMA LINHA (2026-11-05) ---------------------
    # MEDIDO no uso dele: desligar 20 s e religar custava 1-1,5 s de ecra vazio;
    # desligar e religar em seguida era INSTANTANEO -- porque havia uma linha
    # fresca para pintar. O `on` tem de devolver a linha que ja' estava la'.
    enable_src = extract_method(src, '_set_live_enabled')
    ns3, _ = build(enable_src)
    for kind, age_s, want_replay in (('fresca', 0.4, True), ('historia', 9.0, False)):
        ov5 = Overlay()
        sh5 = shell_for(ns3, ov5)
        replayed = []
        shown = []
        sh5.show_caption_window = lambda on, _s=shown: _s.append(bool(on))
        sh5.push_caption_to_window = (
            lambda text, previous=None, credits=None, instant=False, _r=replayed:
            _r.append((text, instant)))
        sh5._caption_wanted_store = lambda on: None
        sh5._caption_painted = 'a linha que ja estava no ecra'
        sh5._caption_painted_at = time.time() - age_s
        # o `_set_live_enabled` tem um `except` que engole tudo: se ele falhar,
        # os arms abaixo leem "nao pintou" e a causa real fica invisivel.
        _logs = sh5.__dict__.setdefault('_oracle_logs', [])
        ns3['_set_live_enabled'](sh5, {'on': True})
        add(not any('LIVE_ENABLED_FAILED' in m for m in _logs),
            'A5c o interruptor nao falhou (o `except` nao esconde uma excepcao)',
            'logs=%r' % (_logs[-1:],))
        if want_replay:
            add(bool(replayed) and replayed[0][0] == 'a linha que ja estava no ecra'
                and replayed[0][1] is True,
                'A5 ligar com linha %s (%.1f s): devolve-a ao ecra no instante do clique'
                % (kind, age_s), 'replays=%r' % (replayed,))
        else:
            add(not replayed,
                'A6 ligar com linha %s (%.0f s): NAO pinta historia' % (kind, age_s),
                'replays=%r' % (replayed,))
        add(bool(shown) and shown[0] is True,
            'A5b/A6b o `show` da janela acontece nos dois casos',
            'shown=%r' % (shown,))
    return namespace, ns2


def neg_arm(src):
    """Apaga o guarda do interruptor numa COPIA e exige o arm A1 vermelho."""
    # A ANCORA E' A LINHA INTEIRA, COM A INDENTACAO DO METODO (2026-11-05).
    # A primeira versao procurava o `if` com a indentacao do TOPO e dava
    # `NEG-ARM IMPOSSIVEL` sobre um fonte correto -- um braco negativo que nao
    # encontra a ancora nao e' um braco negativo, e' um skip disfarcado.
    lines = src.splitlines(keepends=True)
    hit = [i for i, line in enumerate(lines)
           if line.strip() == "if not getattr(self, '_caption_wanted', False):"
           and 'CAPTION_DROP_SWITCH' in lines[min(i + 1, len(lines) - 1)]]
    if len(hit) != 1:
        print('NEG-ARM IMPOSSIVEL -- o guarda aparece %d vez(es) no fonte' % len(hit))
        return 2
    i = hit[0]
    indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    lines[i] = indent + 'if False:  # MUTANT: o guarda apagado\n'
    mutated = ''.join(lines)
    if mutated == src:
        print('NEG-ARM IMPOSSIVEL -- a mutacao nao mudou nada')
        return 2
    global CASES
    CASES = []
    drain_src = extract_method(mutated, '_drain_caption_pending')
    namespace, _ = build(drain_src)
    ov = Overlay()
    sh = shell_for(namespace, ov)
    sh._caption_wanted = False
    sh._caption_pending = (time.time() - 0.05, 'a legenda que ele desligou', '', 3)
    namespace['_drain_caption_pending'](sh)
    shows = [c for c in ov.calls if c[0] == 'show']
    r1 = add(bool(shows), 'NEG A1 com o guarda apagado: a janela VOLTA com a flag OFF',
             'calls=%r' % (ov.calls[:4],))
    # o mutante NAO pode deixar a linha do guarda: o log e' a segunda testemunha
    r2 = add(not any('CAPTION_DROP_SWITCH' in m for m in _),
             'NEG o log do guarda desaparece com a mutacao')
    caught = r1 and r2
    print()
    if caught:
        print('NEG-ARM: PASS -- a saida do arm A1 depende do guarda')
        print('NEG-ARM PASS -- RED as designed')
        return 1
    print('NEG-ARM: FAIL -- o mutante nao derrubou o arm A1')
    return 0



if __name__ == '__main__':
    src = io.open(SHELL, encoding='utf-8', newline='').read()
    if '--neg-arm' in sys.argv:
        raise SystemExit(neg_arm(src))
    arms(src)
    raise SystemExit(verdict('CAPTION-SWITCH-RACE'))
