"""ESCONDER O PAINEL NAO APAGA A LEGENDA AO VIVO (2026-11-05).

MEDIDO na sessao viva do dono (pid 57600): tres
`CAPTION_WINDOW_BLANKED reason=panel-hidden epoch=3/4/5 wanted=true` em vinte e
um segundos -- 06:04:58, 06:05:03, 06:05:19 -- um por Alt+C. Ele reportou o
sintoma como *"parece que ela do nada para de dar display ou funcionar
aleatoriamente"*: cada ciclo de painel apagava a legenda e ela so' voltava na
proxima linha, e `_blank_caption_window` ainda esvaziava `_external_last_text` e
subia `_source_epoch`, o que atirava fora o dedup do YouTube a cada toque.

A LEI (AGENTS.md, regra 3, verbatim do dono): *"se a legenda ao vivo ta
desativada, nao significa q o modelo ta desativado. e' o DISPLAY que ta
desativado"* -- e o inverso tambem vale: esconder o PAINEL nao e' desligar a
LEGENDA. O painel e' uma janela; a legenda ao vivo e' outra.

O QUE ESTE ORACULO EXECUTA. A funcao `SottoShell.hide_panel` REAL, extraida do
arquivo por AST e executada com os globais do sistema injectados (`hide_window`,
`window_visible`, `log`) sobre um `self` falso com o overlay gravador. Nao e' uma
copia: se a shell mudar a funcao, este passo muda com ela.

BRACO NEGATIVO (`--neg-arm`): devolve o `_blank_caption_window('panel-hidden')`
incondicional numa COPIA do fonte e exige o vermelho do arm A.
"""
from __future__ import annotations

import ast
import io
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHELL = REPO / 'app' / 'webview' / 'sotto_webview.py'


def extract_hide_panel(src: str) -> str:
    """O texto-fonte EXATO de `SottoShell.hide_panel`, por AST."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'SottoShell':
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and member.name == 'hide_panel':
                    lines = src.splitlines(keepends=True)
                    body = lines[member.lineno - 1:member.end_lineno]
                    indent = ' ' * member.col_offset
                    # O metodo vem indentado dentro da classe; exec'ado no topo
                    # ele precisa de sair do nivel da classe sem perder o corpo.
                    return ''.join(
                        line[len(indent):] if line.startswith(indent) else line
                        for line in body
                    )
    raise SystemExit('SottoShell.hide_panel nao existe no fonte')


class Recorder:
    """O overlay e o `_blank_caption_window`, gravando o que lhes fazem."""

    def __init__(self):
        self.blanks = []
        self.overlay_calls = []

    def blank(self, reason):
        self.blanks.append(reason)


def build_shell(fn_src, recorder):
    logs = []
    namespace = {
        'hide_window': lambda hwnd: recorder.overlay_calls.append(('hide_window', hwnd)),
        'window_visible': lambda hwnd: False,
        'log': lambda msg: logs.append(str(msg)),
        '__builtins__': __builtins__,
    }
    exec(compile(fn_src, '<hide-panel>', 'exec'), namespace)
    hide_panel = namespace['hide_panel']
    published = []
    shell = types.SimpleNamespace(
        hwnd=4242,
        visible=True,
        click_watcher=types.SimpleNamespace(armed=True),
        caption_overlay=types.SimpleNamespace(),
        _blank_caption_window=recorder.blank,
        # O `hide_panel` publica a visibilidade e' por isso que o worker sabe se
        # volta ao caminho do stream (a "stack law"); aqui e' um gravador.
        publish_panel_visibility=lambda reason: published.append(reason),
    )
    shell.published = published
    return shell, hide_panel, logs


def arm_a(src):
    """Com a legenda AO VIVO ligada, esconder o painel nao toca na legenda."""
    rec = Recorder()
    shell, fn, logs = build_shell(extract_hide_panel(src), rec)
    shell._caption_wanted = True
    shell._source_epoch = 7
    fn(shell, 'hotkey')
    kept_line = any('CAPTION_WINDOW_KEPT' in m for m in logs)
    return {
        'ok': not rec.blanks and shell._source_epoch == 7 and kept_line,
        'blanks': list(rec.blanks),
        'epoch': shell._source_epoch,
        'kept_line': kept_line,
        'log': logs[-1] if logs else '',
    }


def arm_b(src):
    """Com a legenda DESLIGADA, esconder o painel limpa o ecra como sempre."""
    rec = Recorder()
    shell, fn, logs = build_shell(extract_hide_panel(src), rec)
    shell._caption_wanted = False
    fn(shell, 'hotkey')
    return {'ok': rec.blanks == ['panel-hidden'], 'blanks': list(rec.blanks)}


def run(src):
    a = arm_a(src)
    b = arm_b(src)
    print('[%s] A legenda AO VIVO sobrevive ao Alt+C  blanks=%s epoch=%s kept=%s'
          % ('PASS' if a['ok'] else 'FAIL', a['blanks'], a['epoch'], a['kept_line']))
    print('       %s' % a['log'])
    print('[%s] com a legenda DESLIGADA o ecra limpa  blanks=%s'
          % ('PASS' if b['ok'] else 'FAIL', b['blanks']))
    return a['ok'] and b['ok']


def main(argv):
    src = io.open(SHELL, encoding='utf-8').read()
    if '--neg-arm' not in argv:
        ok = run(src)
        print('caption-kept-on-hide-oracle: %s' % ('PASS' if ok else 'FAIL'))
        return 0 if ok else 1

    # O MUTANTE: o `_blank_caption_window('panel-hidden')` volta a ser a unica
    # coisa que a funcao faz, como era antes da cura.
    import re
    # A ANCORA E' O SITIO, NAO A FORMA. A primeira versao deste braco mutou o
    # PRIMEIRO `if not getattr(` do ficheiro -- que nao e' esta guarda -- e deu
    # `0/1 recusado` sobre um fonte que ela nao tocou. Agora o alvo e' a linha da
    # guarda dentro do `hide_panel` e mais nada.
    guard = "if getattr(self, '_caption_wanted', False):"
    if src.count(guard) != 1:
        print('NEG-ARM IMPOSSIVEL: a guarda aparece %d vez(es) no fonte' % src.count(guard))
        return 2
    mutated = src.replace(guard, "if False:  # mutante: a guarda desarmada", 1)
    if mutated == src:
        print('NEG-ARM IMPOSSIVEL: a ancora da guarda nao esta no fonte')
        return 2
    run(mutated)
    caught = not arm_a(mutated)['ok']
    print('NEG-ARM: %s -- %d/1 mutante(s) recusado(s)'
          % ('PASS' if caught else 'FAIL', 1 if caught else 0))
    return 1 if caught else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
