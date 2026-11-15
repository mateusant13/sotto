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

# ── O FEED DO PAINEL DIREITO (2026-11-14) ───────────────────────────────────
# Dono, verbatim: *"e o historico ta COMPLETAMENTE patetico. parece que NAO SABE
# de jeito nenhum como e' a logica de dar append ou simplesmente mostrar no
# historico as legendas ... falas cortadas, frases nao entram, tudo aleatorio ou
# quebrado"*. As tres coisas que ele viu, medidas no arquivo dele e no log
# (`python _main/_history-classify.py`), e o que cada uma e' no codigo:
#
#  1. FRASE QUE ENTRA DUAS VEZES. A lista tem DUAS estradas para a mesma linha:
#     o `history_tail` que o painel pede no arranque e os commits ao vivo. A
#     cauda e' assincrona; tudo o que fecha DURANTE a leitura nao esta' na
#     resposta, e a resposta ja' contem o que o commit ao vivo acabou de pintar.
#     `historyEntries = entries` fazia as duas coisas: apagava as linhas que
#     chegaram entretanto e duplicava as que estavam nas duas estradas.
#  2. FRASE QUE NAO ENTRA. A mesma substituicao, do outro lado: a linha viva
#     apagada pela leitura que resolveu depois.
#  3. FRASE NO LUGAR ERRADO. `replaceFeedRow` reescrevia a ULTIMA `<li>`; com
#     `action='replace_at'` (a fusao dos dois motores reescreveu uma linha do
#     MEIO do ficheiro) isso pintava o texto de um momento em cima de outra
#     frase -- as duas trocadas no ecra, o ficheiro certo.
#
# O predicado destas tres e' PURO e mora em duas funcoes de `panel.js`
# (`feedKey`, `mergeHistoryTail`), logo e' testavel da mesma forma que
# `isPrefixExtension`: extract + `node`, sem navegador.
FEED_ARMS = [
    # (rotulo, gravado, ao_vivo, linhas_esperadas, texto_final_esperado)
    ('a cauda nao apaga a linha que chegou durante a leitura',
     [{'date': 'd', 'time': '20:10:01', 'text': 'primeira.'},
      {'date': 'd', 'time': '20:10:02', 'text': 'segunda.'}],
     [{'date': 'd', 'time': '20:10:09', 'text': 'a que fechou durante a leitura.'}],
     3, None),
    ('a mesma linha nas duas estradas e UMA linha, e fica o texto maior',
     [{'date': 'd', 'time': '20:10:02', 'text': 'a mesma'}],
     [{'date': 'd', 'time': '20:10:02', 'text': 'a mesma frase completa.'}],
     1, 'a mesma frase completa.'),
    ('linha de recurso (sem dia) nao se funde com nada',
     [{'date': 'd', 'time': '20:10:02', 'text': 'do disco.'}],
     [{'time': '20:10:02', 'text': 'sem dia.'}],
     2, None),
    ('gravado vazio + ao vivo = so o ao vivo', [], [{'date': 'd', 'time': '1:1:1', 'text': 'x'}], 1, None),
    # A HORA SO' NAO E' NOME: o `HH:MM:SS` de hoje e o de ontem sao iguais, e a
    # cauda pode trazer os dois dias (a janela de 400 linhas atravessa a meia-
    # noite). Sem o dia na chave, uma fala de ontem FUNDE com a de hoje.
    ('a mesma hora em dias diferentes sao DUAS linhas',
     [{'date': '2026-11-13', 'time': '23:59:59', 'text': 'ontem.'}],
     [{'date': '2026-11-14', 'time': '23:59:59', 'text': 'hoje.'}],
     2, None),
]

FEED_DRIVER = """
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
eval(src);
let ok = 0;
for (const [label, stored, live, wantRows, wantText] of cases) {
  const merged = mergeHistoryTail(stored, live);
  const good = merged.length === wantRows
    && (wantText === null || merged.some((e) => e.text === wantText));
  if (good) { ok += 1; console.log('PASS ' + label); }
  else { console.log('FAIL ' + label + ' rows=' + merged.length + ' text=' + JSON.stringify(merged.map((e) => e.text))); }
}
console.log('FEED-ARMS ' + ok + '/' + cases.length);
process.exit(ok === cases.length ? 0 : 1);
"""


def run_feed_arms(src):
    import json
    tmp = Path(tempfile.mkdtemp(prefix='prefix-row-feed-'))
    try:
        body = extract_function(src, 'feedKey') + '\n' + extract_function(src, 'longerOf') \
            + '\n' + extract_function(src, 'mergeHistoryTail')
        (tmp / 'fn.js').write_text(body, encoding='utf-8')
        (tmp / 'cases.json').write_text(json.dumps(FEED_ARMS), encoding='utf-8')
        (tmp / 'drv.js').write_text(FEED_DRIVER, encoding='utf-8')
        proc = subprocess.run([NODE, str(tmp / 'drv.js'), str(tmp / 'fn.js'), str(tmp / 'cases.json')],
                              capture_output=True, text=True, encoding='utf-8', errors='replace',
                              timeout=120, creationflags=CREATE_NO_WINDOW,
                              startupinfo=_hidden_startupinfo())
        return proc.returncode, (proc.stdout or '') + (proc.stderr or '')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def strip_js_comments(src):
    """Comentarios fora, porque o codigo CITA a forma antiga ao explica-la.

    MEDIDO (2026-11-14): a primeira versao deste teste dava FAIL no codigo novo
    porque a explicacao da cura diz, em prosa, `historyEntries = entries` -- o
    instrumento estava a julgar o comentario que documenta o defeito.
    """
    src = re.sub(r'/\*.*?\*/', ' ', src, flags=re.S)
    # `[^\n]*` e nao `[^\\n]*`: a primeira versao excluia a LETRA n e nunca
    # chegava ao fim da linha (o codigo seguinte era comido pelo comentario).
    return re.sub(r'(?<!:)//[^\n]*', '', src)


def tail_merge_ok(src):
    """A cauda ENTRA na lista; nao a substitui, e `replace_at` nao pinta a ultima.

    Sem isto, as FEED-ARMS provavam que `mergeHistoryTail` sabe fundir duas
    listas -- e o painel podia continuar a chamar `historyEntries = entries`.
    """
    src = strip_js_comments(src)
    if not re.search(r'function applyHistoryTail\(entries\)', src):
        return False, '`applyHistoryTail` nao existe: a cauda nao tem um unico dono'
    call = re.search(r'historyEntries = mergeHistoryTail\(entries, historyEntries\);', src)
    if not call:
        return False, 'o unico escritor da cauda nao chama `mergeHistoryTail`'
    if re.search(r'historyEntries = entries', src):
        return False, 'ha um `historyEntries = entries` (a cauda ainda substitui a lista)'
    if '.tail(HISTORY_LOAD)' not in src:
        return False, 'a cauda deixou de ser pedida ao shell'
    # `replaceFeedRow` tem de casar pela chave da linha, nao por posicao.
    try:
        body = extract_function(src, 'replaceFeedRow')
    except SystemExit as exc:
        return False, str(exc)
    if 'dataset.historyKey' not in body:
        return False, '`replaceFeedRow` nao casa a linha por `data-history-key` (reescreve a ultima)'
    if 'feedKey(entry)' not in body:
        return False, '`replaceFeedRow` nao usa a identidade das duas estradas'
    # E a chave tem de ser gravada na linha, senao o casamento nunca acontece.
    if 'historyKey' not in extract_function(src, 'makeRow'):
        return False, '`makeRow` nao grava `data-history-key` (a chave e\' letra morta)'
    return True, 'cauda fundida por `feedKey`, `replace_at` reescreve a linha nomeada'


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
    # ── O FEED DO PAINEL DIREITO (2026-11-14) ──────────────────────────────
    frc, fout = run_feed_arms(src)
    sys.stdout.write(fout)
    ok_tail, why_tail = tail_merge_ok(src)
    print('[%s] feed owner: %s' % ('PASS' if ok_tail else 'FAIL', why_tail))

    if not neg:
        verdict = 'PASS' if (rc == 0 and ok_call and frc == 0 and ok_tail) else 'FAIL'
        print('panel-prefix-row-oracle: %s (arms=%d, call_site=%s, feed_arms=%d, feed_owner=%s)'
              % (verdict, len(ARMS), ok_call, len(FEED_ARMS), ok_tail))
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
    # Os mutantes do FEED devolvem os bytes da forma antiga. O `caught` do feed
    # e' medido em separado (arms do predicado OU o dono da cauda), porque um
    # deles tem de derrubar o `tail_merge_ok`, nao as FEED-ARMS.
    feed_mutants = []
    feed_mutants.append((
        'a cauda substitui a lista outra vez',
        src.replace('  historyEntries = mergeHistoryTail(entries, historyEntries);',
                    '  historyEntries = entries; /* NEG-ARM feed-1 */', 1)))
    feed_mutants.append((
        'a chave da linha ignora a data (a mesma hora em dois dias funde-se)',
        src.replace("  return `${entry.path || ''}\\u0000${date}\\u0000${time}`;",
                    "  return `${entry.path || ''}\\u0000${time}`; /* NEG-ARM feed-2 */", 1)))
    feed_mutants.append((
        'a mesma linha nas duas estradas fica com o texto mais CURTO',
        src.replace('  return lb > la ? b : a;', '  return lb > la ? a : b; /* NEG-ARM feed-3 */', 1)))
    feed_mutants.append((
        'replaceFeedRow volta a reescrever a ultima linha',
        src.replace('  const key = feedKey(entry);\n  let target = null;',
                    '  const key = null; /* NEG-ARM feed-4 */\n  let target = null;', 1)))

    for label, mutated in feed_mutants:
        if mutated == src:
            print('MUTANTE IMPOSSIVEL (o texto-ancora mudou): %s' % label)
            return 2
        mfrc, mfout = run_feed_arms(mutated)
        mtok, _ = tail_merge_ok(mutated)
        total += 1
        hit = mfrc != 0 or not mtok
        caught += 1 if hit else 0
        print('[%s] mutante do feed: %s (feed_arms_rc=%d feed_owner=%s)'
              % ('CAUGHT' if hit else 'NOT-CAUGHT', label, mfrc, mtok))

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
    # O RC DA CASA: um braco negativo que APANHOU todos os mutantes sai **1**
    # (AGENTS.md: "`--neg-arm` que sai 1 quando apanha o mutante"), e o
    # `call :step red-as-expected-panel-prefix-row 1` do audit e' quem o exige.
    # Verificado em 2026-11-14: positivo rc=0, negativo rc=1.
    return 1 if caught == total else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
