# NO-BUG: O MURO DE PREFIXOS NAO VOLTA: uma linha que so' cresce ocupa UMA linha.
"""O MURO DE PREFIXOS NAO VOLTA: uma linha que so' cresce ocupa UMA linha.

MEDIDO na tela do dono em 2026-11-05, 06:07:33-06:07:42 (`chrome_x2fLWzDdxI.png`),
verbatim do que ele chamou de *"historico completamente patetico"*: nove `<li>`
para a MESMA frase, cada uma com mais palavras que a anterior --

    Run to like max two max, three, but.
    Run to like max two max, three, but running max.
    Run to like max two max, three, but running max two max one.
    ...

A causa e' a identidade da linha: `rowIdentity(source, start)` devolve `null`
sem `start`, `committedByStart` nunca mapeia essa linha, e `addCaption`
APENDAVA em cada commit. O painel ja' substitui no lugar quando a identidade
existe ("REPLACE IN PLACE -- the owner's rule"); a cura e' a mesma regra para o
caso sem identidade: se o texto novo CONTINUA o da ultima linha do mesmo
`source`, e' a mesma frase a crescer.

POR QUE UM ORACULO E NAO UM DOM PROBE. A regra vive dentro de `addCaption`, que
precisa de DOM, e o harness (`_main/_audit-render/panel-harness.html`) e' uma
pagina ESTATICA: nao ha canal para injetar commits. O predicado, porem, e' puro
e o arquivo e' JS que o navegador le' tal e qual -- entao este oraculo EXTRAI a
funcao inteira de `app/panel/panel.js` e a executa no `node`. Nao e' uma copia:
se o painel mudar a regra, este passo muda com ele.

Denunciado tambem o que o predicado NAO pode tocar: a chamada so' existe no ramo
`identity === null`. Duas linhas que o worker identificou por `start` nunca se
fundem aqui -- fundir duas delas apagaria uma frase que ele disse.
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PANEL = REPO / 'app' / 'panel' / 'panel.js'
# A LEI DAS JANELAS (AGENTS.md): o par INTEIRO, nao so' o bit. Medido a
# 2026-11-04 no ecra do dono: `creationflags` SOZINHO pintou uma janela quando
# o pai nao tinha consola -- o censo `console-window-audit.py` chama a isso
# WEAK-FLAG e recusa. O `startupinfo` com `STARTF_USESHOWWINDOW`/`SW_HIDE` e'
# a outra metade (o que `_main/hidden-launch.py` faz por toda a arvore).
CREATE_NO_WINDOW = 0x08000000


def _hidden_startupinfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0          # SW_HIDE
    return si
NODE = 'node'


def extract_function(src, name):
    """`function NAME(...) {` ... a chave que a fecha, por contagem."""
    start = src.index('function %s(' % name)
    i = src.index('{', start)
    depth = 0
    while i < len(src):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise SystemExit('unterminated function %s' % name)


ARMS = [
    # (rotulo, anterior, novo, esperado)
    ('a frase que cresce sem pontuacao (o caso do dono)', 'Run to like max two max, three, but.',
     'Run to like max two max, three, but running max.', True),
    ('a mesma frase que cresce de novo', 'Run to like max two max, three, but running max.',
     'Run to like max two max, three, but running max two max one.', True),
    ('o fecho posto pelo worker nao quebra a continuacao', "Sorry you could really I'm just I gave you like.",
     "Sorry you could really I'm just I gave you like you gave.", True),
    ('texto igual e o mesmo texto', 'a', 'a', True),
    ('frases DIFERENTES ficam em linhas diferentes', 'Points two max one at.',
     'Run to like max two max', False),
    ('o "The same." e o "the same" NAO se fundem (caixa e outra frase)',
     'The same.', 'the same', False),
    ('linha vazia nao funde nada', '', 'x', False),
]

CALL = re.compile(r'if\s*\(\s*!\s*existing\s*&&\s*identity\s*===\s*null\s*\)')

NODE_DRIVER = """
const fs = require('fs');
const fn = fs.readFileSync(process.argv[2], 'utf8');
const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
eval(fn);
let ok = 0;
for (const [label, prev, next, want] of cases) {
  const got = isPrefixExtension(prev, next);
  if (got === want) { ok += 1; console.log('PASS ' + label); }
  else { console.log('FAIL ' + label + ' real=' + got + ' want=' + want); }
}
console.log('ARMS ' + ok + '/' + cases.length);
process.exit(ok === cases.length ? 0 : 1);
"""


def run_arms(fn_src):
    import json
    tmp = Path(tempfile.mkdtemp(prefix='prefix-row-'))
    try:
        (tmp / 'fn.js').write_text(fn_src, encoding='utf-8')
        (tmp / 'cases.json').write_text(json.dumps(ARMS), encoding='utf-8')
        (tmp / 'drv.js').write_text(NODE_DRIVER, encoding='utf-8')
        proc = subprocess.run([NODE, str(tmp / 'drv.js'), str(tmp / 'fn.js'), str(tmp / 'cases.json')],
                              capture_output=True, text=True, encoding='utf-8', errors='replace',
                              timeout=120, creationflags=CREATE_NO_WINDOW,
                              startupinfo=_hidden_startupinfo())
        return proc.returncode, (proc.stdout or '') + (proc.stderr or '')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def call_site_ok(src):
    """A chamada so' no ramo sem identidade, sobre uma JANELA do mesmo source.

    A janela e' a parte que o dono pagou (2026-11-05): com UMA linha comparada,
    o `final` de uma frase que chega depois de a seguinte abrir encontra a linha
    errada e a lista ganha a duplicata `A,B,A` -- medido, 51 de 200 linhas na
    tela dele. Logo o ramo tem de varrer mais do que a ultima linha.
    """
    if not CALL.search(src):
        return False, 'a chamada nao esta no ramo `identity === null`'
    tail_start = src.index('if (!existing && identity === null)')
    tail = src[tail_start:tail_start + 700]
    if 'isPrefixExtension(' not in tail:
        return False, 'o ramo nao chama isPrefixExtension'
    if 'recentRowsForSource(' not in tail:
        return False, 'o ramo nao compara contra uma JANELA de linhas do mesmo source'
    if 'DEDUPE_WINDOW' not in tail:
        return False, 'a janela nao e\' nomeada (`DEDUPE_WINDOW`)' 
    m = re.search(r'const DEDUPE_WINDOW\s*=\s*(\d+)', src)
    if not m or int(m.group(1)) < 2:
        return False, 'DEDUPE_WINDOW < 2: a janela de uma linha e\' o defeito medido' 
    if not re.search(r'function recentRowsForSource\(source, n\)', src):
        return False, '`recentRowsForSource(source, n)` nao existe' 
    if not re.search(r'if \(have === want\) out\.push\(row\)', src):
        return False, '`recentRowsForSource` nao filtra pelo source da linha'
    return True, 'janela de %s linhas, no ramo sem identidade, limitada ao source' % m.group(1)


def main(argv):
    src = PANEL.read_text(encoding='utf-8', errors='replace')
    neg = '--neg-arm' in argv
    rc, out = run_arms(extract_function(src, 'isPrefixExtension'))
    sys.stdout.write(out)
    ok_call, why = call_site_ok(src)
    print('[%s] call site: %s' % ('PASS' if ok_call else 'FAIL', why))

    if not neg:
        verdict = 'PASS' if (rc == 0 and ok_call) else 'FAIL'
        print('panel-prefix-row-oracle: %s (arms=%d, call_site=%s)' % (verdict, len(ARMS), ok_call))
        return 0 if verdict == 'PASS' else 1

    # O BRACO NEGATIVO: mutila o predicado numa COPIA e exige o vermelho naquele
    # arm. Sem isto, "7/7" prova a aritmetica do `===`, nao a regra.
    caught = 0
    total = 0
    mutants = []

    m1 = src.replace('if (i === shorter.length - 1) {', 'if (false && i === shorter.length - 1) {')
    mutants.append(('sem a tolerancia de pontuacao', m1))
    m2 = src.replace("for (const row of recentRowsForSource(source, DEDUPE_WINDOW)) {",
                     "for (const row of []) {")
    mutants.append(('de volta a UMA linha (sem janela)', m2))
    m3 = src.replace("if (have === want) out.push(row);", "out.push(row);")
    mutants.append(('sem o filtro de source na janela', m3))
    m4 = src.replace("const DEDUPE_WINDOW = 8;", "const DEDUPE_WINDOW = 1;")
    mutants.append(('janela de uma linha, o numero do defeito', m4))

    for label, mutated in mutants:
        if mutated == src:
            print('MUTANTE IMPOSSIVEL (o texto-ancora mudou): %s' % label)
            return 2
        mrc, mout = run_arms(extract_function(mutated, 'isPrefixExtension'))
        mcall, _ = call_site_ok(mutated)
        total += 1
        # O mutante 1 tem de derrubar um ARM; os 2 e 3 tem de derrubar o CALL SITE.
        caught_by_arms = mrc != 0
        caught_by_call = not mcall
        hit = caught_by_arms or caught_by_call
        caught += 1 if hit else 0
        print('[%s] mutante: %s (arms_rc=%d call_site=%s)'
              % ('CAUGHT' if hit else 'NOT-CAUGHT', label, mrc, mcall))
    print('NEG-ARM: %s -- %d/%d mutante(s) recusado(s)'
          % ('PASS' if caught == total else 'FAIL', caught, total))
    return 1 if caught == total else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
