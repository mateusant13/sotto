# NO-BUG: 14 arms sobre a funcao REAL `text_normalize` e 5 mutacoes; nao corrige a geracao do texto nem o que o motor escreve no historico.
"""O oraculo da CORRIDA do motor: 14 arms sobre a funcao REAL + 5 mutacoes.

O defeito, medido em 2026-11-11 no arquivo do dono (22 ficheiros, 1302 linhas):
`come come come come come come come come come come come, come domain expansion`
e `Watch just watch watch watch watch watch everybody watch ...` chegaram ao ecra
e ao historico. A funcao que os corta vive em `app/webview/text_normalize.py` e
NAO e' reimplementada aqui: o oraculo importa a real e a chama. As duas metades
que so' o FONTE da shell pode provar (a fiacao nos dois sitios, e o caminho do
PLAYER intocado) sao lidas por `ast`, nunca por `grep`.

Uso:
    python _main/text-normalize-oracle.py            # -> VERDICT: PASS (14/14)
    python _main/text-normalize-oracle.py --neg-arm  # -> NEG-ARM: PASS (5/5), rc=1
"""
from __future__ import annotations

import ast
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))

import text_normalize  # noqa: E402  (a funcao que o produto usa)
import text_normalize as tn  # noqa: E402

SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
HISTORY = os.path.join(ROOT, 'history')

OK = []
BAD = []


def arm(name, ok, detail=''):
    (OK if ok else BAD).append(name)
    print(f'{"PASS" if ok else "FAIL"} {name} {detail}'.rstrip())


def _src(path=SHELL):
    with io.open(path, encoding='utf-8', newline='') as fh:
        return fh.read()


def _push_node(src):
    """O `push_caption_to_window` REAL, por ast (a shell tem 22k linhas)."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'push_caption_to_window':
            return node, ast.get_source_segment(src, node) or ''
    return None, ''


def _history_order(src):
    """As POSICOES de `collapse_runs`, `is_filler_line` e `close_line` no metodo
    REAL `_history_entries`, por `ast` -- a ordem e' o invariante, e o `--neg-arm`
    re-mede esta mesma funcao sobre um fonte mutado."""
    hist = ''
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name == '_history_entries':
            hist = ast.get_source_segment(src, node) or ''
    return hist.find('collapse_runs('), hist.find('is_filler_line('), hist.find('close_line(')


def run():
    cr = text_normalize.collapse_runs

    # ── A1: a corrida medida no arquivo do dono ────────────────────────────
    a1 = cr('Bro yeah you can come come come come come come come come come come '
            'come, come domain expansion with me')
    arm('A1-corrida-de-11-vira-uma',
        a1.count('come') == 2 and 'domain expansion' in a1, repr(a1[:60]))

    # ── A2: DUAS corridas na mesma linha (o caso `watch`) ──────────────────
    a2 = cr('Watch just watch watch watch watch watch everybody watch hold your '
            'breath watch watch watch watch close.')
    arm('A2-duas-corridas-na-mesma-linha',
        a2 == 'Watch just watch everybody watch hold your breath watch close.', repr(a2))

    # ── A3/A4: a pontuacao QUEBRA a corrida -- dialogo nao se toca ─────────
    for name, text in (('A3-virgula-protege-no', 'No, no, no!'),
                       ('A4-virgula-protege-pt', 'N\u00e3o, n\u00e3o, n\u00e3o.')):
        arm(name, cr(text) == text, repr(cr(text)))

    # ── A5/A6: enfase sobrevive ate' TRES, cai na corrida de 4 ─────────────
    # (A arm tem de medir o numero em que a regra difere: com o tecto geral de 3
    #  um par sobrevive nos DOIS lados e o mutante M2 passava -- medido.)
    arm('A5-enfase-tres-sobrevive', cr('Still super super super niche.') == 'Still super super super niche.',
        repr(cr('Still super super super niche.')))
    arm('A6-enfase-corrida-de-4-cai',
        cr('super super super super') == 'super', repr(cr('super super super super')))

    # ── A7: ponto de frase nao e' virgula (o relogio separou, nao o motor) ─
    arm('A7-ponto-final-nao-quebra', cr('Yeah. Yeah.') == 'Yeah. Yeah.')

    # ── A8: a marca terminal do fim da corrida VEM junto ───────────────────
    arm('A8-marca-terminal-preservada', cr('Come come come come.') == 'Come.',
        repr(cr('Come come come come.')))

    # ── A9/A10: sem corrida devolve o MESMO objecto, e vazio devolve vazio ─
    same = 'uma frase normal, sem repeticao nenhuma aqui'
    arm('A9-sem-corrida-devolve-o-mesmo-objecto', cr(same) is same)
    arm('A10-vazio-devolve-vazio', cr('') == '' and cr('a b') == 'a b')

    # ── A14: idempotente ───────────────────────────────────────────────────
    once = cr('come come come come today')
    arm('A14-idempotente', cr(once) == once, repr(once))

    # ── A11: fiacao NOS DOIS SITIOS, lida por ast ──────────────────────────
    src = _src()
    calls = 0
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'collapse_runs'):
            calls += 1
    imports = any(isinstance(n, ast.Import) and any(a.name == 'text_normalize' for a in n.names)
                  for n in ast.walk(ast.parse(src)))
    arm('A11-fiacao-dos-dois-sitios', imports and calls == 2, f'import={imports} chamadas={calls}')

    # ── A12: o caminho do PLAYER nao e' reescrito (a guarda `rows is None`) ─
    _node, push = _push_node(src)
    reads_rows = bool(re.search(r'\brows\s+is\s+None\b|\brows\s+is\s+not\s+None\b', push))
    arm('A12-player-intocado-so-no-caminho-do-asr', reads_rows and 'collapse_runs(text)' in push)

    # ── A15: a ORDEM no caminho de leitura -- a corrida cai ANTES do fecho ─
    # (Se o fecho corresse primeiro, o ponto seria decidido sobre um texto que
    #  ainda tem a corrida. A ordem e' o invariante; o `continue` do
    #  preenchimento tem de vir DEPOIS da corrida, senao `Mmm Mmm Mmm.` nunca
    #  chega a ser so' preenchimento.)
    pos_c, pos_f, pos_l = _history_order(src)
    arm('A15-corrida-antes-do-fecho-e-do-preenchimento',
        0 <= pos_c < pos_f and 0 <= pos_c < pos_l and pos_f >= 0,
        f'collapse={pos_c} filler={pos_f} close={pos_l}')

    # ── A16: o preenchimento e' a LINHA inteira, nunca a palavra solta ─────
    arm('A16-preenchimento-e-a-linha-inteira',
        tn.is_filler_line('Mmm Mmm.') and tn.is_filler_line('Mmm')
        and not tn.is_filler_line('Mmm, mas eu vou.')
        and not tn.is_filler_line('Oh.') and not tn.is_filler_line(''))

    # ── A17: o padrao e' o MESMO do motor (duas regras, um numero) ────────
    noise_path = os.path.join(ROOT, 'worker', 'caption_noise.py')
    with io.open(noise_path, encoding='utf-8') as fh:
        noise_src = fh.read()
    # O literal do motor pode vir entre aspas simples OU duplas -- medido: ele
    # usa duplas, e a primeira versao desta arm so' lia simples e dizia AUSENTE.
    m = re.search("_NOISE_WORD\\s*=\\s*re\\.compile\\(r([\"'])(.*?)\\1", noise_src)
    arm('A17-padrao-igual-ao-do-motor',
        bool(m) and m.group(2) == tn._FILLER.pattern, (m.group(2) if m else 'AUSENTE'))

    # ── A13: a invariante que torna a cura segura, no arquivo REAL dele ────
    lines = []
    if os.path.isdir(HISTORY):
        pre = re.compile(r'^-\s*\[[0-9:]{5,8}\]\s*')
        cmt = re.compile(r'<!--.*?-->', re.S)
        for day in sorted(os.listdir(HISTORY)):
            d = os.path.join(HISTORY, day)
            if not os.path.isdir(d):
                continue
            for name in sorted(os.listdir(d)):
                if not name.endswith('.md'):
                    continue
                try:
                    fh = io.open(os.path.join(d, name), encoding='utf-8', errors='replace')
                except OSError:
                    continue
                with fh:
                    for ln in fh:
                        s = pre.sub('', cmt.sub('', ln.rstrip('\n'))).strip()
                        if s and not s.startswith('#'):
                            lines.append(s)
    if not lines:
        print('SKIP A13-arquivo-real-dele (sem history/ nesta arvore -- nao e PASS)')
    else:
        grown = lost = 0
        for s in lines:
            out = cr(s)
            if len(out.split()) > len(s.split()):
                grown += 1
            if s[-1:] in '.!?\u2026' and out[-1:] not in '.!?\u2026':
                lost += 1
        cured = sum(1 for s in lines if cr(s) != s)
        arm('A13-arquivo-real-nada-cresce-nem-perde-marca', grown == 0 and lost == 0,
            f'linhas={len(lines)} curadas={cured} cresceu={grown} perdeu_marca={lost}')


def neg_arm():
    """As 5 mutacoes, cada uma numa COPIA (o produto nao se toca)."""
    path = os.path.join(ROOT, 'app', 'webview', 'text_normalize.py')
    with io.open(path, encoding='utf-8', newline='') as fh:
        good = fh.read()
    mutants = [
        ('M1-MIN_RUN-2-apaga-pares-legitimos', 'MIN_RUN = 3', 'MIN_RUN = 2',
         'A7-ponto-final-nao-quebra'),
        ('M2-enfase-sem-tecto-proprio', 'limit = 4 if', 'limit = 3 if',
         'A5-enfase-tres-sobrevive'),
        ('M3-pontuacao-nao-quebra-a-corrida', "return bool(_BREAKS.search(tail)) or right[:1] in ',;:'",
         'return False', 'A3-virgula-protege-no'),
        ('M4-marca-terminal-perdida', 'parts[i][1] + last[len(_bare(last)):]', 'parts[i][1]',
         'A8-marca-terminal-preservada'),
        ('M5-a-corrida-nao-cai', 'if run >= limit:', 'if False:',
         'A1-corrida-de-11-vira-uma'),
        ('M6-preenchimento-nunca-detectado', 'return bool(words) and all(', 'return False and all(',
         'A16-preenchimento-e-a-linha-inteira'),
    ]
    # M7 mexe no FONTE da shell, nao no modulo: a ordem dos dois passos no
    # caminho de leitura. Uma copia, nunca o ficheiro do produto.
    shell_mutants = [
        ('M7-filler-antes-da-corrida',
         'A15-corrida-antes-do-fecho-e-do-preenchimento'),
    ]
    caught = 0
    for name, old, new, expect in mutants:
        if old not in good:
            print(f'NOT-CAUGHT {name} (ancora ausente: {old!r})')
            continue
        mod = good.replace(old, new, 1)
        ns = {'__name__': 'text_normalize_mutated'}
        exec(compile(mod, path + '<mutant>', 'exec'), ns)  # noqa: S102 (copia em memoria)
        cr = ns['collapse_runs']
        isf = ns.get('is_filler_line', lambda _t: False)
        # Cada mutante e' julgado pelo SEU braco.
        fails = {
            'A1-corrida-de-11-vira-uma': cr('come come come come come come come').strip().count('come') != 1,
            'A3-virgula-protege-no': cr('No, no, no!') != 'No, no, no!',
            'A5-enfase-tres-sobrevive': cr('Still super super super niche.') != 'Still super super super niche.',
            'A7-ponto-final-nao-quebra': cr('Yeah. Yeah.') != 'Yeah. Yeah.',
            'A8-marca-terminal-preservada': cr('Come come come come.') != 'Come.',
            'A16-preenchimento-e-a-linha-inteira': isf('Mmm Mmm.') is False,
        }[expect]
        if fails:
            caught += 1
            print(f'CAUGHT {name} -- derruba {expect}')
        else:
            print(f'NOT-CAUGHT {name} -- {expect} continuou verde')

    # O mutante do FONTE: trocar a linha do `is_filler_line` para ANTES do
    # `collapse_runs` no metodo real tem de derrubar o A15.
    with io.open(SHELL, encoding='utf-8', newline='') as fh:
        shell_src = fh.read()
    # A ANCORA CARREGA O EOL DO PROPRIO FICHEIRO (medido 2026-11-12). O shell
    # e' CRLF e este oraculo lia com `newline=''`, entao um `block` escrito com
    # `\n` nunca casava: o mutante do FONTE respondia `NOT-CAUGHT (ancora do
    # fonte ausente)` em toda corrida e o `--neg-arm` ficava em 6/7 com rc=0 --
    # o passo `red-as-expected-text-normalize` publicava `CONTROL FAILED` sobre
    # um controlo que era CEGO, nao sobre o produto. A ordem que ele vigia e' a
    # mesma; o que muda e' o separador vir do ficheiro.
    _seol = '\r\n' if '\r\n' in shell_src else '\n'
    block = _seol.join([
        '                    text = text_normalize.collapse_runs(text)',
        '                    if text_normalize.is_filler_line(text):',
        '                        continue',
    ]) + _seol
    swapped = _seol.join([
        '                    if text_normalize.is_filler_line(text):',
        '                        continue',
        '                    text = text_normalize.collapse_runs(text)',
    ]) + _seol
    name, expect = shell_mutants[0]
    c_before, f_before, _ = _history_order(shell_src)
    if block in shell_src and c_before < f_before:
        c_after, f_after, _ = _history_order(shell_src.replace(block, swapped, 1))
        if not (c_after < f_after):
            caught += 1
            print(f'CAUGHT {name} -- derruba {expect}')
        else:
            print(f'NOT-CAUGHT {name} -- {expect} continuou verde')
    else:
        print(f'NOT-CAUGHT {name} (ancora do fonte ausente)')
    total_mutants = len(mutants) + len(shell_mutants)
    print(f'NEG-ARM: {"PASS" if caught == total_mutants else "FAIL"} -- {caught}/{total_mutants} mutantes apanhados')
    return 1 if caught == total_mutants else 0


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    run()
    total = len(OK) + len(BAD)
    print(f'VERDICT: {"PASS" if not BAD else "FAIL"} ({len(OK)}/{total})')
    return 0 if not BAD else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
