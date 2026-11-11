# NO-BUG: julga os dois predicados do censo e a memo do `code_identity`; nao liga o censo na shell nem baixa o piso de 20 %.
"""O oraculo do CENSO QUE NOMEIA A THREAD (shell, 2026-11-08).

O DEFEITO QUE ELE JULGA, medido nesta arvore a 00:14:

  * a instancia nova (pid 19896, codigo curado) ficou em **10-16 %** de um nucleo;
  * o censo da shell so' publica `THREAD_CPU` com o TOTAL >= 20 %, entao calou --
    e "nao ha' linha" nao diz QUAL thread gasta. Quem quisesse responder "o spin
    do `sotto-outside-click` voltou?" so' tinha um psutil de fora, por 30 s;
  * `SHELL_CODE_ID` era escrito UMA vez, no arranque. Numa instancia de 12 h o
    `_main/live-code-freshness-oracle.py` respondeu `UNKNOWN` porque o log rodou:
    o portao que existe para dizer STALE ficou cego quando a instancia envelhece.

O que ele EXECUTA e' o codigo real (`app/webview/sotto_webview.py`), pelos dois
predicados puros que a shell usa no caminho do censo:

  A1  total 19,9 / top 4,9 -> NAO publica (o silencio continua a existir)
  A2  total 19,9 / top 5,0 -> PUBLICA (uma thread passa o piso dela)
  A3  total 25,0 / top 0   -> PUBLICA (o piso antigo, intacto)
  A4  beat 9 -> nao, 10 -> sim, 20 -> sim
  A5  `_code_identity_memo()` == `code_identity()` e e' ESTAVEL entre chamadas
  A6  a segunda chamada custa < 5 ms (o sha256 de 99 ficheiros e' feito uma vez)

`--neg-arm` muta uma COPIA do shell: o piso da thread volta a 20 (A2 cai) e o
batimento passa a nunca acontecer (A4 cai). Um portao que nao cai com a cura
arrancada nao e' um portao.
"""
import argparse
import importlib.util
import io
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WEBVIEW = os.path.dirname(SHELL)


def load_shell(path=SHELL, name='sotto_webview_census_oracle'):
    """O modulo REAL (ou a copia mutada), importado do diretorio dele."""
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(module):
    results = []

    def arm(name, ok, detail=''):
        results.append((name, bool(ok), detail))

    arm('A1 19,9 % / top 4,9 % continua silencioso',
        module.census_should_publish(19.9, 4.9) is False)
    arm('A2 19,9 % / top 5,0 % PUBLICA',
        module.census_should_publish(19.9, 5.0) is True)
    arm('A3 total 25 % PUBLICA (piso antigo)',
        module.census_should_publish(25.0, 0.0) is True)
    arm('A4 batimento no 10.o e no 20.o censo',
        module.census_beat_due(9) is False and module.census_beat_due(10) is True
        and module.census_beat_due(20) is True,
        'beats 9/10/20 = %s/%s/%s' % (module.census_beat_due(9),
                                      module.census_beat_due(10),
                                      module.census_beat_due(20)))
    primeiro = module._code_identity_memo()
    t0 = time.time()
    segundo = module._code_identity_memo()
    dt_ms = (time.time() - t0) * 1000.0
    arm('A5 a identidade e` ESTAVEL entre chamadas',
        primeiro == segundo and 'sha256=' in primeiro, primeiro[:30])
    arm('A6 a segunda chamada e` memoizada (< 5 ms)', dt_ms < 5.0, '%.1f ms' % dt_ms)

    # A9-A11: a LINHA do censo (2026-11-08). O instrumento publicava so' as
    # janelas OCUPADAS, logo a serie dele e' uma amostra viesada: no mesmo
    # processo uma janela externa de 32 s mediu 5,5 % e o censo calou.
    arm('A9 abaixo do piso e sem batimento -> nenhuma linha',
        module.census_line(5.0, 4.0, [(4.0, 'a')]) is None)
    linha = module.census_line(5.0, 4.0, [(4.0, 'a')], beat=True)
    arm('A10 no batimento a linha sai e diz heartbeat=true',
        bool(linha) and 'heartbeat=true' in linha and 'total=5%' in linha,
        linha or 'sem linha')
    linha = module.census_line(25.0, 10.0, [(10.0, 'x'), (9.0, 'y')])
    arm('A11 acima do piso sai sem a etiqueta e nomeia as duas primeiras',
        bool(linha) and 'heartbeat' not in linha and 'x:10%' in linha and 'y:9%' in linha,
        linha or 'sem linha')

    for name, ok, detail in results:
        print('  %s %-42s %s' % ('OK  ' if ok else 'FAIL', name, detail))
    bad = [r for r in results if not r[1]]
    return len(results) - len(bad), len(results)


def neg_arm(tmpdir):
    src = io.open(SHELL, encoding='utf-8').read()
    # M1 pisos de volta (o piso unico de 20 %): A2 e A4 tem de cair.
    m1 = src.replace('CENSUS_THREAD_FLOOR = 5.0', 'CENSUS_THREAD_FLOOR = 20.0', 1)
    m1 = m1.replace('CENSUS_BEAT_EVERY = 10', 'CENSUS_BEAT_EVERY = 0', 1)
    # M2 o batimento nao publica (o vies de volta): A10 tem de cair.
    m2 = src.replace("    if not (census_should_publish(total, top_pct) or beat):",
                     "    if not census_should_publish(total, top_pct):", 1)
    caught = 0
    total = 0
    for label, mutated in (('pisos de volta', m1), ('batimento nao publica', m2)):
        total += 1
        if mutated == src:
            print('  ?    a mutacao NAO pegou: %s (ancora mudou)' % label)
            continue
        case = os.path.join(tmpdir, 'sotto_webview_mutant_%d.py' % total)
        io.open(case, 'w', encoding='utf-8').write(mutated)
        module = load_shell(case, 'sotto_webview_census_mutant_%d' % total)
        good, arms = run(module)
        if good < arms:
            caught += 1
        else:
            print('  ?    MUTANTE NAO APANHADO: %s (%d/%d)' % (label, good, arms))
    print('NEG-ARM: %s -- %d/%d mutantes apanhados'
          % ('PASS' if caught == total else 'FAIL', caught, total))
    return 1 if caught == total else 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--neg-arm', action='store_true')
    args = parser.parse_args(argv)
    tmpdir = tempfile.mkdtemp(prefix='census-instrument-')
    if args.neg_arm:
        return neg_arm(tmpdir)
    ok, total = run(load_shell())
    print('VERDICT: %s -- %d/%d arm(s)' % ('PASS' if ok == total else 'FAIL', ok, total))
    return 0 if ok == total else 1


if __name__ == '__main__':
    sys.exit(main())
