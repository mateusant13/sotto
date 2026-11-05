#!/usr/bin/env python
# -*- coding: utf-8 -*-
# NO-BUG: load-bg-window-oracle — o prazo da janela de fundo da carga, provado nas funcoes que embarcam; trabalho de CAPACIDADE nascido do recibo `_main/receipt-20261105-extrema.md` (lane SottoAudit3), que declara no seu §5.3 os tres bracos mas NAO tinha passo na bateria. Nao corresponde a nenhum id de `_main/bug-ledger.json` e e' declarado aqui em vez de inventar um.
"""O PRAZO DA JANELA DE FUNDO DA CARGA: o que fecha a janela, e o que a mantem aberta.

O QUE ESTE FICHEIRO JULGA, e nada mais. O recibo `_main/receipt-20261105-extrema.md`
mede o efeito (pior caso `load_s` 33,96 s -> 4,92 s) e declara tres bracos de
instrumento no seu §5.3: `SOTTO_LOAD_BG_MAX_S=-1` reproduz o comportamento antigo,
`0` desarma a janela, e a segunda chamada a `close` e' no-op. **Nenhum passo da
bateria executava esses tres bracos** -- um braco que so' existe na prosa nao e' um
braco. Este oraculo carrega `worker/sotto_worker.py` por caminho (`__main__` guardado,
`main()` NAO corre, nenhum peso carregado) e conduz as funcoes REAIS:

  _load_bg_cap_s            o prazo lido do ambiente, senao a constante
  _enter_load_background_mode  abre a janela e arma o timer
  _close_load_background_mode   fecha UMA vez, e diz quem fechou

AS ARMS:

  A1  sem `SOTTO_LOAD_BG_MAX_S` -> o prazo e' `LOAD_BG_MAX_S` (0,75 s hoje).
  A2  `SOTTO_LOAD_BG_MAX_S=0`   -> prazo 0, e o `_enter_` NAO abre a janela
      (`enter` devolve False). E' o braco "sem janela" do A/B.
  A3  `SOTTO_LOAD_BG_MAX_S=-1`  -> prazo negativo, e o `_enter_` abre SEM timer
      (a forma de 2026-10-23: janela ilimitada). E' o CONTROL0 do A/B.
  A4  `SOTTO_LOAD_BG_MAX_S=abc` -> nao explode, cai na constante, e diz no log.
  A5  o timer FECHA a janela e o `closed_by` diz `deadline` -- com um prazo real
      de 50 ms, nao com um mock do `threading.Timer`.
  A6  a segunda chamada a `close` e' NO-OP: o `closed_by` nao volta a ser escrito.

`--neg-arm` escreve uma COPIA do worker ao lado do original e exige que cada
mutacao derrube a SUA arm: (a) sem a guarda de idempotencia (A6 vermelho), (b) o
ambiente ignorado (A2/A3 vermelhos), (c) o timer nunca armado (A5 vermelho).
"""

from __future__ import annotations

import importlib.util
import io
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
NEG_COPY = os.path.join(ROOT, 'worker', '_neg-load-bg-copy.py')

for _d in (os.path.join(ROOT, 'worker'),):
    if _d not in sys.path:
        sys.path.insert(0, _d)


def load_worker(path: str, name: str):
    """O worker REAL, carregado por caminho; `main()` nao corre (`__name__`)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def verdicts(mod) -> dict:
    """Conduz as funcoes reais. Cada arm e' um facto, nao uma opiniao."""
    res: dict = {}

    # A1 -- a constante e' o default.
    os.environ.pop('SOTTO_LOAD_BG_MAX_S', None)
    res['A1_default_is_constant'] = (
        mod._load_bg_cap_s() == mod.LOAD_BG_MAX_S and mod.LOAD_BG_MAX_S > 0)

    # A2 -- `0` desarma: prazo zero E a janela nao abre. O contrato do
    # `_enter_load_background_mode` e' uma PALAVRA, nao um booleano -- medido
    # ao correr: devolve 'no-background(disabled)' em vez de False, e a primeira
    # versao desta arm comparava com False e dava FAIL no original. A arm estava
    # errada, nao o worker.
    os.environ['SOTTO_LOAD_BG_MAX_S'] = '0'
    cap0 = mod._load_bg_cap_s()
    entered0 = mod._enter_load_background_mode()
    mod._close_load_background_mode('arm-a2')
    res['A2_zero_disables'] = (cap0 == 0.0
                               and entered0 == 'no-background(disabled)')

    # A3 -- negativo e' o `sem prazo`: abre, e SEM timer.
    os.environ['SOTTO_LOAD_BG_MAX_S'] = '-1'
    capn = mod._load_bg_cap_s()
    enteredn = mod._enter_load_background_mode()
    timer_n = mod._LOAD_BG_WINDOW.get('timer')
    res['A3_negative_opens_without_timer'] = (
        capn < 0 and enteredn == 'background' and timer_n is None)
    mod._close_load_background_mode('arm-a3')

    # A4 -- lixo no ambiente cai na constante, e o caminho nao explode.
    os.environ['SOTTO_LOAD_BG_MAX_S'] = 'abc'
    res['A4_garbage_falls_back'] = (mod._load_bg_cap_s() == mod.LOAD_BG_MAX_S)

    # A5 -- o TIMER fecha a janela. Prazo de 50 ms, nao um mock.
    os.environ['SOTTO_LOAD_BG_MAX_S'] = '0.05'
    entered5 = mod._enter_load_background_mode()
    deadline = time.time() + 2.0
    while time.time() < deadline and mod._LOAD_BG_WINDOW.get('open'):
        time.sleep(0.01)
    res['A5_deadline_closes'] = (
        entered5 == 'background' and mod._LOAD_BG_WINDOW.get('open') is False
        and mod._LOAD_BG_WINDOW.get('closed_by') == 'deadline')
    closed_by = mod._LOAD_BG_WINDOW.get('closed_by')

    # A6 -- fechar duas vezes nao reescreve quem fechou.
    os.environ.pop('SOTTO_LOAD_BG_MAX_S', None)
    mod._enter_load_background_mode()
    mod._close_load_background_mode('first')
    again = mod._close_load_background_mode('second')
    res['A6_close_is_idempotent'] = (
        again is None and mod._LOAD_BG_WINDOW.get('closed_by') == 'first')

    res['_closed_by_routed_by'] = closed_by
    return res


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    neg = '--neg-arm' in argv
    # O ORIGINAL carrega-se SEMPRE: no modo negativo as mutacoes sao COPIA e o
    # ponto de partida tem de ser o ficheiro que embarca (a primeira versao
    # carregava a copia primeiro, que ainda nao existia -> FileNotFoundError).
    try:
        mod = load_worker(WORKER, 'sotto_worker_lb')
    except Exception as exc:  # noqa: BLE001
        print('VERDICT: FAIL worker nao carregou: %r' % (exc,))
        return 1

    if neg:
        return neg_arm(mod)

    res = verdicts(mod)
    closed = res.pop('_closed_by_routed_by', None)
    fail = [k for k, v in res.items() if not v]
    for key in sorted(res):
        print('  %-34s %s' % (key, 'PASS' if res[key] else 'FAIL'))
    print('  %-34s %r' % ('(A5 closed_by)', closed))
    print('VERDICT: %s' % ('PASS' if not fail else 'FAIL ' + ','.join(fail)))
    return 0 if not fail else 1


def _mutate(src: str, kind: str) -> str:
    if kind == 'idempotence':
        return src.replace(
            "    if not _LOAD_BG_WINDOW['open']:\n        return None\n", '', 1)
    if kind == 'env_ignored':
        return src.replace(
            "    raw = os.environ.get('SOTTO_LOAD_BG_MAX_S')",
            "    raw = None", 1)
    if kind == 'timer_never_armed':
        return re.sub(r"(\n        t = threading\.Timer\([^\n]*\n)", "\n        t = None\n",
                      src, count=1)
    raise SystemExit('mutacao desconhecida %r' % (kind,))


def neg_arm(mod) -> int:
    """Cada mutacao tem de derrubar a SUA arm, numa COPIA ao lado do original."""
    # O ficheiro que embarca esta' em CRLF: as ancoras das mutacoes sao escritas
    # em LF, e a primeira versao desta funcao lia com `newline=''` e nao achava a
    # ancora da idempotencia (a mutacao ficava INERTE e o braco contava 2 de 3).
    src = io.open(WORKER, encoding='utf-8', newline='').read().replace('\r\n', '\n')
    base = verdicts(mod)
    base_fail = [k for k, v in base.items() if not v and not k.startswith('_')]
    if base_fail:
        print('NEG-ARM: IMPOSSIVEL -- o original ja falha %s' % base_fail)
        return 2
    cases = caught = 0
    for kind in ('idempotence', 'env_ignored', 'timer_never_armed'):
        mutated = _mutate(src, kind)
        if mutated == src:
            print('MUTANT %-20s ANCORA NAO ACHADA (mutacao inerte)' % kind)
            continue
        cases += 1
        io.open(NEG_COPY, 'w', encoding='utf-8', newline='').write(mutated)
        try:
            m2 = load_worker(NEG_COPY, 'sotto_worker_neg_%s' % kind)
            out = verdicts(m2)
        except Exception as exc:  # noqa: BLE001
            print('MUTANT %-20s CAUGHT (explodiu: %r)' % (kind, exc))
            caught += 1
            continue
        broken = [k for k, v in out.items() if not v and not k.startswith('_')]
        if broken:
            caught += 1
            print('MUTANT %-20s CAUGHT por %s' % (kind, ','.join(broken)))
        else:
            print('MUTANT %-20s NOT-CAUGHT' % kind)
    try:
        os.remove(NEG_COPY)
    except OSError:
        pass
    print('NEG-ARM SUMMARY cases=%d caught=%d' % (cases, caught))
    ok = cases == 3 and caught == cases
    print('NEG-ARM: %s' % ('PASS' if ok else 'FAIL'))
    return 1 if ok else 0


if __name__ == '__main__':
    sys.exit(main())
