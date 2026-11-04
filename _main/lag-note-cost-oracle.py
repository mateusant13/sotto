#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: `_caption_lag_note` custava 27 us por legenda, 83 % do caminho de aplicacao -- defeito de CPU medido, nao um id do `_main/bug-ledger.json`.
"""O CUSTO DE `_caption_lag_note` -- e a SERIE que ele publica, campo a campo.

PORQUE ESTE ORACULO EXISTE. O recibo `_main/receipt-20261104-profiling.md` §b
mediu, com cProfile sobre as funcoes REAIS, **27,1 us por legenda** para aplicar
uma legenda no shell, dos quais **83 %** estavam dentro de `_caption_lag_note`
(1 005 000 iteracoes de gerador em 5 000 legendas = 201 por legenda). A causa
era o guarda de amostragem: `len(ages) % 25 == 0` e' SEMPRE verdadeiro com a
janela cheia (`200 % 25 == 0`), logo a janela de 200 amostras era re-ordenada e
re-somada em TODAS as legendas.

O QUE ELE JULGA (o codigo REAL do `SottoShell`, nao uma copia da regra):

  1. `cost-under-budget` -- o custo por legenda, medido no relogio, tem de
     caber no orcamento de 4x (6,75 us) sobre os 27,1 us do recibo. O numero
     medido sai no stdout: um "-0,2 us" nao passa por aqui.
  2. `cost-flat-with-full-window` -- o custo NAO pode crescer quando a janela
     enche. Mede o mesmo numero com a janela a 20 amostras e a 200; a razao
     tem de ser <= 2. E' esta arm que nomeia a CLASSE do defeito: um resumo
     proporcional a janela falha aqui mesmo que o absoluto passe.
  3. `series-fields-exact` -- as nove chaves publicadas
     (`n p50 p90 max over held over_win held_win live_win budget_ms`) sao
     comparadas com uma reimplementacao INDEPENDENTE das regras (janela de
     200, percentil `round(p*(n-1))`, `held` na banda, `blown` so' na via
     viva) sobre as mesmas amostras. O resumo incremental tem de dar o MESMO
     numero que a janela ordenada a mao -- senao o log mente mais depressa.
  4. `series-published-every-25` -- 200 legendas publicam exactamente 8 linhas
     (25, 50, ... 200), como o desenho sempre disse. Antes eram 200.
  5. `series-window-is-200` -- depois de encher, `n` fica em 200 e o `max` e' o
     da 200.a amostra mais recente: a janela desliza, nao cresce.

`--neg-arm`: muta uma COPIA de `app/webview/sotto_webview.py` e exige que cada
mutante derrube a SUA arm -- rc=1 quando apanha todos:
  * `sort-per-caption` -- o guarda volta a ordenar a janela em cada legenda
    (a forma do defeito original) -> `cost-under-budget` VERMELHA;
  * `held-win-zero` -- um campo da serie publicado como constante -> `series-
    fields-exact` VERMELHA;
  * `window-never-drops` -- a janela deixa de deslizar -> `series-window-is-200`
    VERMELHA;
  * `ordered-never-evicts` -- a janela ordenada acumula -> `series-fields-exact`
    VERMELHA.

Sem janela, sem worker, sem audio, sem rede: `object.__new__` no `SottoShell`
real (nao corre `__init__`, logo nada abre) e `log` trocado por um colector.
"""
import importlib.util
import io
import os
import random
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')

#: O orcamento de 4x sobre os 27,1 us medidos no recibo do profiler.
BUDGET_US = 6.75
#: Janela e banda, lidas do proprio shell quando o modulo carrega.
WINDOW = 200
PUBLISH_EVERY = 25


def load_shell(path, name):
    sys.path.insert(0, WEBVIEW)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class Collector(object):
    def __init__(self):
        self.lines = []

    def __call__(self, message, *_a, **_k):
        self.lines.append(str(message))

    def take(self, needle):
        hits = [l for l in self.lines if needle in l]
        return hits[-1] if hits else None

    def count(self, needle):
        return sum(1 for l in self.lines if needle in l)


def make_shell(mod):
    """O `SottoShell` REAL, sem `__init__`: nenhuma janela, nenhum argv."""
    shell = object.__new__(mod.SottoShell)
    shell.caption_log = []
    shell._caption_ages = []
    shell._caption_lag_blown = 0
    shell._caption_hold = 0
    return shell


def field(line, key):
    for token in (line or '').split():
        if token.startswith(key + '='):
            raw = token[len(key) + 1:]
            try:
                return float(raw)
            except ValueError:
                return raw
    return None


def stream(n, seed=5):
    """Idades no feitio do log do dono: p50 ~300 ms, cauda de 10 % a estourar."""
    rnd = random.Random(seed)
    out = []
    for i in range(n):
        if rnd.random() < 0.10:
            age = rnd.randint(1500, 60000)
        else:
            age = max(1, int(rnd.gauss(300, 200)) + 30)
        queue = 1504 if i % 19 == 0 else rnd.randint(0, 90)
        kind = 'final' if i % 31 == 0 else 'partial'
        out.append((age, queue, kind))
    return out


def cost_us(shell, samples, repeat=4):
    """Melhor de `repeat` passagens -- o relogio e' o mesmo antes e depois."""
    note = mod_method(shell)
    best = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        for age, queue, kind in samples:
            note(age, queue_ms=queue, kind=kind)
        dt = time.perf_counter() - t0
        best = dt if best is None else min(best, dt)
    return best / len(samples) * 1e6


def mod_method(shell):
    return shell._note


def arm_cost(mod, log):
    shell = make_shell(mod)
    shell._note = mod.SottoShell._caption_lag_note.__get__(shell, type(shell))
    samples = stream(6000)
    # aquece a JIT das listas e enche a janela antes de medir
    for age, queue, kind in samples[:400]:
        shell._note(age, queue_ms=queue, kind=kind)
    us = cost_us(shell, samples)
    return us <= BUDGET_US, ('%.3f us/legenda (orcamento %.2f, recibo 27.1)'
                             % (us, BUDGET_US))


def arm_flat(mod, log):
    small = make_shell(mod)
    small._note = mod.SottoShell._caption_lag_note.__get__(small, type(small))
    full = make_shell(mod)
    full._note = mod.SottoShell._caption_lag_note.__get__(full, type(full))
    feed = stream(400)
    for age, queue, kind in feed[:20]:
        small._note(age, queue_ms=queue, kind=kind)
    for age, queue, kind in feed:
        full._note(age, queue_ms=queue, kind=kind)
    probe = stream(4000, seed=9)
    us_small = cost_us(small, probe)
    us_full = cost_us(full, probe)
    ratio = us_full / us_small if us_small else 99.0
    return ratio <= 2.0, ('janela 20=%.3f us  janela 200=%.3f us  razao=%.2fx'
                          % (us_small, us_full, ratio))


def expected_stats(samples):
    """Reimplementacao INDEPENDENTE da regra publicada (nao importa a do shell)."""
    window = []
    blown_total = 0
    held_total = 0
    for age, queue, kind in samples:
        live = kind == 'partial'
        held = 1490 <= int(queue) <= 1520
        blown = live and age > 1500
        if held:
            held_total += 1
        if blown:
            blown_total += 1
        window.append((int(age), held, blown, live))
        del window[:-WINDOW]
    ordered = sorted(a for a, _h, _b, _l in window)
    n = len(ordered)

    def pct(p):
        return ordered[min(n - 1, int(round(p * (n - 1))))]

    return {
        'n': n, 'p50': pct(0.5), 'p90': pct(0.9), 'max': ordered[-1],
        'over': blown_total, 'held': held_total,
        'over_win': sum(1 for _a, _h, b, _l in window if b),
        'held_win': sum(1 for _a, h, _b, _l in window if h),
        'live_win': sum(1 for _a, _h, _b, lv in window if lv),
        'budget_ms': 1500,
    }


def arm_series_exact(mod, log):
    shell = make_shell(mod)
    shell._note = mod.SottoShell._caption_lag_note.__get__(shell, type(shell))
    samples = stream(275, seed=21)
    for age, queue, kind in samples:
        shell._note(age, queue_ms=queue, kind=kind)
    line = log.take('CAPTION_LAG_STATS')
    if line is None:
        return False, 'CAPTION_LAG_STATS AUSENTE'
    want = expected_stats(samples)
    bad = []
    for key, value in want.items():
        got = field(line, key)
        if got is None or abs(float(got) - float(value)) > 1e-9:
            bad.append('%s esperado=%s obtido=%s' % (key, value, got))
    return not bad, (('todos os %d campos iguais a janela a mao' % len(want))
                     if not bad else '; '.join(bad)[:200])


def arm_cadence(mod, log):
    shell = make_shell(mod)
    shell._note = mod.SottoShell._caption_lag_note.__get__(shell, type(shell))
    log.lines[:] = []
    samples = stream(WINDOW, seed=4)
    for age, queue, kind in samples:
        shell._note(age, queue_ms=queue, kind=kind)
    pubs = log.count('CAPTION_LAG_STATS')
    ns = [field(l, 'n') for l in log.lines if 'CAPTION_LAG_STATS' in l]
    want = WINDOW // PUBLISH_EVERY
    ok = pubs == want and ns == [float(PUBLISH_EVERY * (i + 1))
                                 for i in range(want)]
    return ok, ('%d linha(s) para %d legendas (esperado %d), n=%s'
                % (pubs, WINDOW, want, int(ns[-1]) if ns else 'AUSENTE'))


def arm_window(mod, log):
    shell = make_shell(mod)
    shell._note = mod.SottoShell._caption_lag_note.__get__(shell, type(shell))
    log.lines[:] = []
    # 475 amostras de idade CRESCENTE: com a janela a deslizar, o maximo e' o
    # das ultimas 200 e o `n` fica em 200 -- uma janela que nao desliza cresce.
    # 475 publica na ultima amostra (475 % 25 == 0), logo o maximo publicado e'
    # o da amostra mais recente.
    samples = [(1000 + i, 5, 'partial') for i in range(475)]
    for age, queue, kind in samples:
        shell._note(age, queue_ms=queue, kind=kind)
    line = log.take('CAPTION_LAG_STATS')
    if line is None:
        return False, 'CAPTION_LAG_STATS AUSENTE'
    n = field(line, 'n')
    mx = field(line, 'max')
    want_max = float(1000 + 474)
    ok = n == float(WINDOW) and mx == want_max
    return ok, ('n=%s max=%s (esperado n=%d max=%d)'
                % (int(n or 0), int(mx or 0), WINDOW, int(want_max)))


ARMS = (
    ('cost-under-budget', arm_cost),
    ('cost-flat-with-full-window', arm_flat),
    ('series-fields-exact', arm_series_exact),
    ('series-published-every-25', arm_cadence),
    ('series-window-is-200', arm_window),
)


def run_arms(mod, label):
    log = Collector()
    mod.log = log
    rows = []
    for name, fn in ARMS:
        log.lines[:] = []
        try:
            ok, detail = fn(mod, log)
        except Exception as exc:                       # noqa: BLE001
            ok, detail = False, 'EXCECAO %r' % (exc,)
        rows.append((name, bool(ok), str(detail)[:200]))
        print('%-28s %s %s' % (name, 'PASS' if ok else 'RED',
                               str(detail)[:180]))
    return rows


def main(argv):
    neg = '--neg-arm' in argv
    mod = load_shell(SHELL, 'sotto_shell_lagcost')
    if not neg:
        rows = run_arms(mod, 'real')
        bad = [n for n, ok, _ in rows if not ok]
        print('VERDICT: %s (%d/%d arms)'
              % ('PASS' if not bad else 'FAIL', len(rows) - len(bad), len(rows)))
        return 0 if not bad else 1

    tmpdir = tempfile.mkdtemp(prefix='lag-cost-neg-')
    try:
        src = io.open(SHELL, encoding='utf-8').read()
        mutants = (
            ('sort-per-caption',
             '        if self._caption_notes % 25 == 0:\n',
             '        if True:\n'
             '            ordered = sorted(s[0] for s in ages)\n',
             {'cost-under-budget'}),
            ('held-win-zero',
             '                f\'held_win={self._caption_held_win} \'',
             '                f\'held_win=0 \'',
             {'series-fields-exact'}),
            ('window-never-drops',
             '        if len(ages) > 200:',
             '        if len(ages) > 20000:',
             {'series-window-is-200'}),
            ('ordered-never-evicts',
             '            del ordered[bisect.bisect_left(ordered, dropped[0])]',
             '            pass',
             {'series-fields-exact'}),
        )
        total = 0
        caught = 0
        for why, needle, replacement, expect in mutants:
            mutated = src.replace(needle, replacement, 1)
            if mutated == src:
                print('NEG-ARM IMPOSSIVEL: ancora ausente para %r' % (needle,))
                return 2
            path = os.path.join(tmpdir, 'shell_%s.py' % why.replace('-', '_'))
            with io.open(path, 'w', encoding='utf-8', newline='\n') as handle:
                handle.write(mutated)
            print('=== mutante: %s' % why)
            mutant = load_shell(path, 'sotto_shell_neg_%s'
                                % why.replace('-', '_'))
            rows = run_arms(mutant, why)
            red = {n for n, ok, _ in rows if not ok}
            missed = expect - red
            total += 1
            if not missed:
                caught += 1
            print('mutante %-24s %s (vermelhas: %s)'
                  % (why, 'APANHADO' if not missed else 'PASSOU',
                     ', '.join(sorted(red)) or 'nenhuma'))
        print('NEG-ARM: %s (%d/%d mutantes apanhados)'
              % ('PASS' if caught == total else 'FAIL', caught, total))
        return 1 if caught == total else 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
