"""CAPTION-DUP-REPRO -- o laco que reproduz, minimiza e prova a duplicacao de legenda (B5).

PORQUE EXISTE
-------------
O dono, verbatim: *"coisa duplicada"*, *"a frase era maior, foi sumindo"*. A duplicacao ja foi
medida e ja foi curada em DOIS sitios diferentes, e essa e a razao de este ficheiro existir:

  * painel  -> `youtube_window.collapse_growth` (colapsa a MESMA frase e o crescimento dela)
  * historico -> `SottoShell.history_append` (recusa a linha IGUAL a ultima; `HISTORY_DUPLICATE_SKIPPED`)

Antes disto, a prova era um script em `I:\\cc-tmp` -- efemero, nao commitado, e por isso nao era um
laco: quem viesse a seguir repetia a experiencia em vez de correr um comando. Este ficheiro e o laco.

O QUE FAZ (quatro fases, uma so invocacao)
------------------------------------------
1. `--scan`      mede a duplicacao no historico REAL do dono (impacto quantificado, nao estimado).
2. `--minimize`  delta-debug sobre um par real: tira uma das duas linhas e exige que a duplicacao
                 DESAPARECA. Se continuar a haver duplicacao sem uma delas, o par nao era minimo.
3. `--replay`    corre o INVOCADOR REAL (`SottoShell.history_append`, o metodo da classe, com um
                 duplo que so substitui o caminho e a proveniencia) sobre cinco casos e conta as
                 linhas que ficam no ficheiro.
4. `--neg-arm`   MUTACAO: tira a guarda (`_history_last_body` -> None) e exige que o replay fique
                 VERMELHO. Se o mutante passar, o laco nao apanha o defeito e o laco esta errado.
5. `--panel`     a OUTRA camada: `youtube_window.collapse_growth` (o *"a frase era maior, foi
                 sumindo"*), com o seu proprio mutante -- a identidade, que e o mundo de antes.

Duas camadas, duas funcoes, dois mutantes: o store recusa a linha IGUAL, o painel colapsa a que
CRESCE. Um laco que so exercitasse uma delas estaria a chamar "curado" a metade do problema.

INVOCADOR
---------
    python H:\\sotto\\_main\\caption-dup-repro.py            # tudo, veredicto unico
    python H:\\sotto\\_main\\caption-dup-repro.py --scan      # so o impacto medido
    python H:\\sotto\\_main\\caption-dup-repro.py --neg-arm    # so a prova do detector

rc 0 = PASS (todas as fases pedidas), rc 1 = FAIL (inclui "nao ha historico para medir").

NAO ESCREVE FORA DO TEMP. Nao levanta a app. Nao toca em `history/` (so le).
"""

import argparse
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HISTORY = os.path.join(ROOT, 'history')
WEBVIEW = os.path.join(ROOT, 'app', 'webview')

# `- [HH:MM:SS] frase <!-- route=... -->` -- a forma escrita por `history_append`.
LINE = re.compile(r'^- \[(\d{2}:\d{2}:\d{2})\] (.*?)(?:\s*<!--.*?-->)?\s*$')


def norm(line):
    """A frase de uma linha do historico, sem hora e sem proveniencia."""
    match = LINE.match(line.rstrip('\r\n'))
    if not match:
        return None
    return (match.group(2) or '').strip()


def read_lines(path):
    """[(numero_de_linha, frase)] de um ficheiro do historico."""
    out = []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as handle:
            for number, raw in enumerate(handle, 1):
                body = norm(raw)
                if body:
                    out.append((number, body))
    except OSError as exc:
        print('  AVISO nao consegui ler %s: %r' % (path, exc))
    return out


def pairs(lines):
    """Os pares consecutivos em que a segunda linha REPETE, CONTINUA ou SOBREPOE a primeira.

    TRES relacoes, medidas em separado de proposito -- ja se confundiram uma com a outra:

    * `igual`        -- a frase e a MESMA. E esta que o `history_append` recusa.
    * `crescimento`  -- a nova COMECA pela anterior (ou a anterior pela nova): `'O radio'` ->
      `'O radio Segunda'`. E esta que o `collapse_growth` colapsa.
    * `sobreposicao` -- uma frase CONTEM a outra, sem ser prefixo: a janela deslizante do ASR
      (`'Residents need an alternative route'` a aparecer no fim de uma linha e no principio da
      seguinte). Nao e duplicacao exacta; e o mesmo texto pintado duas vezes.

    O numero antigo de "517 de 2077 linhas" nao foi medido com nenhuma destas tres regras
    declaradas -- por isso este instrumento conta as tres e nao herda o numero.
    """
    found = []
    for (n1, a), (n2, b) in zip(lines, lines[1:]):
        if a == b:
            found.append(('igual', n1, a, n2, b))
        elif b.startswith(a) or a.startswith(b):
            found.append(('crescimento', n1, a, n2, b))
        elif a in b or b in a:
            found.append(('sobreposicao', n1, a, n2, b))
    return found


def history_files(paths):
    if paths:
        out = []
        for path in paths:
            if os.path.isdir(path):
                for name in sorted(os.listdir(path)):
                    if name.endswith('.md'):
                        out.append(os.path.join(path, name))
            elif os.path.isfile(path):
                out.append(path)
        return out
    out = []
    if not os.path.isdir(HISTORY):
        return out
    for day in sorted(os.listdir(HISTORY)):
        folder = os.path.join(HISTORY, day)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name.endswith('.md'):
                out.append(os.path.join(folder, name))
    return out


def phase_scan(paths):
    """FASE 1 -- impacto medido no historico real."""
    print('== FASE 1: impacto no historico real ==')
    files = history_files(paths)
    if not files:
        print('  FAIL nenhum ficheiro de historico para medir')
        return None
    total = 0
    counts = {'igual': 0, 'crescimento': 0, 'sobreposicao': 0}
    worst = None
    examples = []
    for path in files:
        lines = read_lines(path)
        total += len(lines)
        found = pairs(lines)
        for kind, n1, a, n2, b in found:
            counts[kind] += 1
            if len(examples) < 3:
                examples.append((os.path.relpath(path, ROOT), n1, a, n2, b))
        if worst is None or len(found) > worst[1]:
            worst = (path, len(found), found)
    print('  ficheiros=%d  linhas=%d  iguais=%d  crescimento=%d  sobreposicao=%d'
          % (len(files), total, counts['igual'], counts['crescimento'], counts['sobreposicao']))
    for rel, n1, a, n2, b in examples:
        print('  ex. %s:%d/%d' % (rel, n1, n2))
        print('      - %s' % a[:96])
        print('      + %s' % b[:96])
    if worst is None or not worst[2]:
        print('  (nenhum par repetido no historico de hoje -- o impacto medido e 0)')
        return None
    print('  pior ficheiro: %s (%d pares)' % (os.path.relpath(worst[0], ROOT), worst[1]))
    if counts['igual']:
        print('  NOTA: estes %d pares ja estao GRAVADOS -- a guarda do `history_append` e para a'
              % counts['igual'])
        print('        FRENTE (recusa a proxima linha igual); nao reescreve o passado. Voltar a')
        print('        ver o mesmo numero neste ficheiro e o esperado, nao e a cura a falhar.')
    return {'total': total, 'counts': counts, 'worst': worst}


def phase_minimize(scan):
    """FASE 2 -- minimizar: o par real, e a prova de que e minimo."""
    print('== FASE 2: minimizar o par que reproduz ==')
    if not scan or not scan['worst'][2]:
        print('  SKIP sem par duplicado para minimizar')
        return None
    kind, n1, a, n2, b = scan['worst'][2][0]
    pair = [(n1, a), (n2, b)]
    if not pairs(pair):
        print('  FAIL o par escolhido nao reproduz')
        return False
    # delta-debug: tirar uma das duas linhas TEM de matar a reproducao.
    for drop in (0, 1):
        rest = [pair[1]] if drop == 0 else [pair[0]]
        if pairs(rest):
            print('  FAIL com uma so linha ainda reproduz (o par nao e minimo)')
            return False
    print('  par minimo (%s):' % kind)
    print('      1. %s' % a[:96])
    print('      2. %s' % b[:96])
    print('  tirar qualquer uma das duas -> 0 pares  (minimo provado)')
    return True


def _import_shell():
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    import sotto_webview  # noqa: PLC0415 -- import tardio: so o replay precisa da classe
    return sotto_webview


class _silent_log(object):
    """Silencia o `log` do shell enquanto o instrumento corre.

    Um instrumento nao pode escrever no artefacto que mede: cada corrida deixava
    `HISTORY_APPEND path="I:\\cc-tmp\\..."` no `_main/webview-run.log`, que e exactamente o ficheiro
    onde se le a evidencia a seguir. Evidencia falsa e pior do que evidencia nenhuma.
    """

    def __init__(self, module):
        self.module = module
        self.saved = None

    def __enter__(self):
        self.saved = getattr(self.module, 'log', None)
        if self.saved is not None:
            self.module.log = lambda *args, **kwargs: None
        return self

    def __exit__(self, *exc):
        if self.saved is not None:
            self.module.log = self.saved
        return False


CHECK = {
    # nome: (texto, opcoes, deve_entrar_no_ficheiro?)
    'primeira':            ('Seems more expensive than using Opus 55.', {'route': 'final'}, True),
    'igual_seguida':       ('Seems more expensive than using Opus 55.', {'route': 'final'}, False),
    'frase_diferente':     ('Outra frase.', {'route': 'final'}, True),
    'igual_apos_outra':    ('Seems more expensive than using Opus 55.', {'route': 'final'}, True),
    'vazia':               ('   ', {'route': 'final'}, False),
    'provisional':         ('rascunho', {'route': 'provisional-draft'}, False),
}


def _run_checks(module):
    """Corre os seis casos no invocador REAL. Devolve (ok, linhas_no_ficheiro, detalhe)."""
    shell_cls = module.SottoShell
    folder = tempfile.mkdtemp(prefix='caption-dup-')
    path = os.path.join(folder, '12.md')

    class Double(object):
        def _history_path_for(self, now):
            return path

        def _history_last_body(self, p):
            return shell_cls._history_last_body(p)

        def _history_provenance(self, options):
            return ' <!-- route=final start=1 reason=ok -->'

    double = Double()
    detail = []
    with _silent_log(module):
        for name, (text, options, should_enter) in CHECK.items():
            entry = shell_cls.history_append(double, text, options)
            entered = entry is not None
            detail.append((name, entered, should_enter))
    ok = all(entered == should for _n, entered, should in detail)
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            written = [l for l in handle.read().split('\n') if l.strip()]
    except OSError:
        written = []
    return ok, written, detail


def phase_replay():
    """FASE 3 -- o invocador real, seis casos, e a contagem no ficheiro."""
    print('== FASE 3: replay no invocador real (SottoShell.history_append) ==')
    module = _import_shell()
    ok, written, detail = _run_checks(module)
    for name, entered, should in detail:
        mark = 'ok  ' if entered == should else 'FAIL'
        print('  %s %-18s entrou=%-5s esperado=%s' % (mark, name, entered, should))
    expected = sum(1 for _n, _e, s in detail if s)
    print('  linhas escritas=%d  esperadas=%d' % (len(written), expected))
    if len(written) != expected:
        ok = False
    print('  PASS' if ok else '  FAIL')
    return ok


def phase_neg_arm():
    """FASE 4 -- mutacao: sem a guarda, o replay TEM de ficar vermelho."""
    print('== FASE 4: braco negativo (mutante sem guarda) ==')
    module = _import_shell()
    shell_cls = module.SottoShell
    original = shell_cls.__dict__.get('_history_last_body')
    try:
        shell_cls._history_last_body = staticmethod(lambda path: None)
        ok, written, _detail = _run_checks(module)
    finally:
        if original is not None:
            shell_cls._history_last_body = original
    caught = not ok
    print('  com o mutante: replay %s (esperado: VERMELHO)' % ('PASSOU' if ok else 'FICOU VERMELHO'))
    print('  linhas escritas com o mutante=%d' % len(written))
    if caught:
        print('  NEG-ARM PASS -- o laco apanha a duplicacao quando a guarda desaparece')
        return True
    print('  NEG-ARM FAIL -- o laco e cego: ficou verde sem a guarda')
    return False


def phase_panel():
    """FASE 5 -- a camada do PAINEL: o `collapse_growth`, que cura o "foi sumindo".

    Sao DUAS camadas curadas por funcoes diferentes, e confundi-las ja custou uma sessao:
    o store (`history_append`) recusa a linha IGUAL; o painel (`collapse_growth`) colapsa a que
    CRESCE. A queixa do dono tem as duas metades -- *"coisa duplicada"* e *"a frase era maior, foi
    sumindo"* -- por isso o laco tem de exercitar as duas.
    """
    print('== FASE 5: camada do painel (youtube_window.collapse_growth) ==')
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    import youtube_window  # noqa: PLC0415 -- import tardio, so esta fase precisa

    trio = ['O radio', 'O radio Segunda', 'O radio Segunda Os']
    got = youtube_window.collapse_growth(trio)
    ok_grow = list(got) == ['O radio Segunda Os']
    print('  crescimento   : %d linhas -> %r  %s' % (len(trio), got, 'ok' if ok_grow else 'FAIL'))

    legit = youtube_window.collapse_growth(['What?', '>> What?'])
    ok_legit = list(legit) == ['What?', '>> What?']
    print('  duas vivas    : %r  %s' % (legit, 'ok' if ok_legit else 'FAIL'))

    # Mutacao: a identidade e o mundo de antes da cura. O trio tem de voltar a 3 linhas.
    original = youtube_window.collapse_growth
    try:
        youtube_window.collapse_growth = lambda lines: [
            str(l).strip() for l in (lines or ()) if str(l).strip()]
        mutant = youtube_window.collapse_growth(trio)
    finally:
        youtube_window.collapse_growth = original
    caught = list(mutant) != ['O radio Segunda Os']
    print('  com o mutante : %d linhas -> %s'
          % (len(mutant), 'VERMELHO (esperado)' if caught else 'PASSOU -- o laco e cego'))
    if not caught:
        print('  NEG-ARM FAIL -- o laco nao ve o crescimento')
    return ok_grow and ok_legit and caught


def main(argv):
    # A consola deste PC e cp1252 e o historico tem acentos: sem isto o instrumento morre a meio da
    # medicao -- que e o pior sitio para morrer (ja mediu, ainda nao disse).
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        pass

    parser = argparse.ArgumentParser(description='Reproduz/minimiza/prova a duplicacao de legenda (B5).')
    parser.add_argument('--scan', action='store_true', help='so a fase 1 (impacto medido)')
    parser.add_argument('--minimize', action='store_true', help='so a fase 2 (delta-debug)')
    parser.add_argument('--replay', action='store_true', help='so a fase 3 (invocador real)')
    parser.add_argument('--neg-arm', dest='neg_arm', action='store_true', help='so a fase 4 (mutante)')
    parser.add_argument('--panel', action='store_true', help='so a fase 5 (camada do painel)')
    parser.add_argument('paths', nargs='*', help='ficheiros/pastas de historico (por omissao history/)')
    args = parser.parse_args(argv)

    only = args.scan or args.minimize or args.replay or args.neg_arm or args.panel
    results = {}
    scan = None

    # A minimizacao precisa do par REAL que a fase 1 achou; com `--minimize` sozinho, mede-se primeiro
    # (e leitura, nao muda nada) para nao minimizar um caso inventado.
    if (not only or args.scan or args.minimize) and not args.replay and not args.neg_arm:
        scan = phase_scan(args.paths)
        results['scan'] = scan is not None
    if not only or args.minimize:
        results['minimize'] = phase_minimize(scan)
    if not only or args.replay:
        results['replay'] = phase_replay()
    if not only or args.neg_arm:
        results['neg_arm'] = phase_neg_arm()
    if not only or args.panel:
        results['panel'] = phase_panel()

    bad = [name for name, value in results.items() if value is False]
    skipped = [name for name, value in results.items() if value is None]
    print()
    if bad:
        print('CAPTION-DUP-VERDICT FAIL  fases=%d  falharam=%s  saltadas=%s'
              % (len(results), ','.join(bad), ','.join(skipped) or '0'))
        return 1
    print('CAPTION-DUP-VERDICT PASS  fases=%d  falharam=0  saltadas=%s  (um passo saltado nao e um portao que passou)'
          % (len(results), ','.join(skipped) or '0'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
