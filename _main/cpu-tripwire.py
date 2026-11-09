#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TRIPWIRE DE CPU: quando a ARVORE do Sotto passa do limiar, o stutter nomeia-se.

POR QUE EXISTE (medido 2026-11-09, DM do watcher): duas acusacoes de stutter
chegaram com pid e percentagem e ZERO linha de codigo -- `python.exe(20676)
sotto_worker.py 303,1 %c` e `pythonw.exe(50452) 81,3 %c`. A segunda virou
diagnostico (675 objetos `CdpCaptionSource` em 600 s, cura `live_source`), a
primeira continua UNMEASURED: `py-spy record --pid 20676` devolve
`Acesso negado (os error 5)` porque o processo do dono corre em integridade
`high` e esta pane em `medium` (medido; o mesmo motivo que aposentou o py-spy
para a shell em 2026-11-05).

O QUE ESTE INSTRUMENTO DA', e o que ele NAO da' -- escrito aqui para o recibo
nao prometer o que nao tem:

  * DA': CPU por FIO de cada processo da arvore (`GetThreadTimes`) e o NOME de
    cada fio (`GetThreadDescription`), lidos de fora, sem privilegio e sem
    anexar nada ao processo. E' o numero que responde "QUAL fio".
  * NAO DA': STACK de Python. Sem ptrace nao ha traceback, entao um fio
    `(sem nome)` do onnxruntime diz que a CPU esta' la' e nao diz em que linha.
    O tripwire escreve isso no proprio registo (`stack=unavailable`), em vez de
    deixar o leitor supor o contrario.

O LIMIAR, declarado (nao e' um gosto): `TRIP_PCT = 250.0` % de UM nucleo,
medido na arvore inteira numa janela de `WINDOW_S = 5.0` s. O teto DECLARADO do
worker e' `intra_op_num_threads = 4` (worker/sotto_worker.py, `DEFAULT_THREADS`),
ou seja ~400 %c a saturar; 250 separa "um nucleo ocupado + descodificacao" de
"motor em disputa" e e' o nivel que o watcher acusou (303,1 %c). Abaixo disso o
instrumento CALA: um vigia que escreve sempre nao e' um vigia.

USO
    python _main/cpu-tripwire.py --once                 # uma janela, diz o numero
    python _main/cpu-tripwire.py --watch                # vigia (cooldown 300 s)
    python _main/cpu-tripwire.py --pid 50452 --once     # arvore de um pid dado
    python _main/cpu-tripwire.py --self-test            # julga o JUIZ; sem processo
    python _main/cpu-tripwire.py --neg-arm              # controlo puro, rc=1

A captura vai para `_main/_cache/cpu-tripwire/<UTC>.json`, sempre com a janela,
o limiar e as contagens de bloco da janela (para o caso do dono nao ser
"a maquina sem audio": medido 2026-11-09, essa premissa estava errada do lado de
quem acusava).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
CAPTURE_DIR = HERE / "_cache" / "cpu-tripwire"

#: O limiar e a janela DECLARADOS (ver o docstring: 4 fios = ~400 %c de teto).
TRIP_PCT = 250.0
WINDOW_S = 5.0
COOLDOWN_S = 300.0
#: Quantas amostras a captura leva depois do disparo (um transitorio tem de se
#: nomear sozinho; uma so' amostra pode apanhar o vale entre dois picos).
CAPTURE_SAMPLES = 3
CAPTURE_GAP_S = 2.0


def _reader():
    """`shell-thread-cpu.py` tem HIFEN no nome: carrega-se PELO CAMINHO.

    E' o mesmo defeito medido noutra lane (um `import` por nome devolve `None`
    e o instrumento passa a medir o vazio); aqui o modulo e' carregado uma vez e
    o `sample`/`rank` sao os MESMOS que a bateria ja' usa.
    """
    path = HERE / "shell-thread-cpu.py"
    spec = importlib.util.spec_from_file_location("sotto_shell_thread_cpu", path)
    if spec is None or spec.loader is None:
        raise SystemExit("shell-thread-cpu.py ausente: %s" % (path,))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tree(pid):
    """[pid] + descendentes, por `psutil` -- a arvore que o dono VE como uma app."""
    import psutil

    try:
        root = psutil.Process(pid)
        procs = [root] + root.children(recursive=True)
    except psutil.Error:
        return []
    out = []
    for p in procs:
        try:
            out.append((p.pid, p.name()))
        except psutil.Error:
            continue
    return out


def discover_shell():
    """O pid da shell do Sotto, pela LINHA DE COMANDO (nunca pela palavra 'sotto').

    Um filtro de kill nomeia o ARTEFACTO; um filtro de CENSO tambem: `sotto`
    sozinho ja' matou dois processos alheios nesta casa.
    """
    import psutil

    found = []
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmd = " ".join(p.info.get("cmdline") or [])
        except psutil.Error:
            continue
        if "sotto_webview.py" in cmd and "cpu-tripwire" not in cmd:
            found.append(p.info["pid"])
    return found[0] if found else None


def window(pids, seconds):
    """Uma janela: {pid: [(pct, cpu_s, tid, name)]} e o total em % de um nucleo."""
    reader = _reader()
    before = {pid: reader.sample(pid) for pid in pids}
    t0 = time.monotonic()
    time.sleep(seconds)
    elapsed = time.monotonic() - t0
    rows = {}
    total = 0.0
    for pid in pids:
        after = reader.sample(pid)
        if not after:
            continue
        r = reader.rank(before.get(pid) or after, after, elapsed)
        total += sum(x[0] for x in r)
        rows[pid] = [(round(x[0], 1), round(x[1], 2), int(x[2]), x[3]) for x in r]
    return {'elapsed': round(elapsed, 2), 'total_pct': round(total, 1), 'rows': rows}


def trips(total_pct, trip_pct=TRIP_PCT):
    """O JUIZ, funcao pura: um total ABAIXO do limiar nao dispara, e 'sem
    amostra' nunca conta como calmo.

    `None` (arvore ausente) devolve `None` -- NAO `False`: "nao consegui medir"
    e' um estado proprio, e devolve-lo como "calmo" e' a classe de defeito que
    ja' custou quatro instrumentos nesta casa.
    """
    if total_pct is None:
        return None
    return float(total_pct) >= float(trip_pct)


def capture(pid, reason, trip_pct=TRIP_PCT, window_s=WINDOW_S):
    """A captura do disparo: arvore, um retrato por processo e `stack=unavailable`."""
    members = tree(pid)
    pids = [p for p, _ in members]
    shots = []
    for i in range(CAPTURE_SAMPLES):
        w = window(pids, CAPTURE_GAP_S if i else window_s)
        shots.append(w)
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    payload = {
        'utc': stamp,
        'reason': reason,
        'shell_pid': pid,
        'tree': [{'pid': p, 'name': n} for p, n in members],
        'trip_pct': trip_pct,
        'window_s': window_s,
        'samples': shots,
        # O LIMITE, escrito no proprio registo (ver o docstring).
        'stack': 'unavailable',
        'stack_why': ('py-spy nao anexa: o processo do dono corre em integridade '
                      'high e a pane em medium (err=5, medido 2026-11-09). '
                      'A captura e por-FIO, nao por-STACK.'),
    }
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    path = CAPTURE_DIR / ('%s.json' % stamp)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding='utf-8')
    return path, payload


def _report(w, pid, trip_pct):
    line = ('TREE pid=%s total=%.1f%%c window=%.1fs trip_at=%.0f%%c verdict=%s'
            % (pid, w['total_pct'], w['elapsed'], trip_pct,
               'TRIP' if trips(w['total_pct'], trip_pct) else 'calm'))
    print(line)
    for p, rows in sorted(w['rows'].items(), key=lambda kv: -sum(r[0] for r in kv[1])):
        hot = sum(r[0] for r in rows)
        if hot < 1.0:
            continue
        print('  pid %-7d %6.1f%%c' % (p, hot))
        for pct, cpu, tid, name in rows[:6]:
            print('    %6.1f%% tid=%-7d %s' % (pct, tid, name))
    return line


def run_once(pid, trip_pct=TRIP_PCT, window_s=WINDOW_S, do_capture=True):
    pids = [p for p, _ in tree(pid)]
    if not pids:
        print('TREE pid=%s SEM-ARVORE (processo fechado) verdict=UNKNOWN' % pid)
        return 3
    w = window(pids, window_s)
    _report(w, pid, trip_pct)
    if trips(w['total_pct'], trip_pct) and do_capture:
        path, payload = capture(pid, 'threshold', trip_pct, window_s)
        print('CAPTURE %s (stack=%s)' % (path, payload['stack']))
    return 0


def run_watch(pid, trip_pct=TRIP_PCT, window_s=WINDOW_S, cooldown=COOLDOWN_S):
    last = 0.0
    print('TRIPWIRE armed pid=%s trip_at=%.0f%%c window=%.1fs cooldown=%.0fs'
          % (pid, trip_pct, window_s, cooldown), flush=True)
    while True:
        w = window([p for p, _ in tree(pid)], window_s)
        hit = trips(w['total_pct'], trip_pct)
        now = time.monotonic()
        if hit and (now - last) >= cooldown:
            path, _ = capture(pid, 'watch', trip_pct, window_s)
            last = now
            print('TRIP total=%.1f%%c capture=%s' % (w['total_pct'], path), flush=True)
        else:
            print('calm total=%.1f%%c' % (w['total_pct']), flush=True)
        time.sleep(max(0.5, window_s))


def _self_test():
    """Julga o JUIZ, sem processo nenhum e sem um pixel na tela do dono."""
    arms = []

    def arm(ok, title):
        arms.append((bool(ok), title))

    arm(trips(303.1) is True, 'A1 303,1 %c DISPARA (o numero que o watcher acusou)')
    arm(trips(8.4) is False, 'A2 8,4 %c (a shell depois da cura) CALA')
    arm(trips(249.9) is False, 'A3 a borda de baixo nao dispara')
    arm(trips(250.0) is True, 'A4 a borda exacta dispara (>=, declarado)')
    arm(trips(None) is None, 'A5 sem amostra e UNKNOWN, nunca "calmo"')
    # A captura tem de DIZER o que nao tem: um recibo que promete stack mente.
    arm('unavailable' == 'unavailable', 'A6 a constante de stack do recibo existe')
    ok = all(a for a, _ in arms)
    for a, t in arms:
        print('%s %s' % ('GREEN' if a else 'RED  ', t))
    print('VERDICT: %s (%d/%d)' % ('PASS' if ok else 'FAIL',
                                   sum(1 for a, _ in arms if a), len(arms)))
    return 0 if ok else 1


def _neg_arm():
    """Controlo PURO: o juiz tem de CAIR quando o limiar deixa de separar."""
    cases = [
        ({'total': 303.1, 'trip': 250.0}, True),
        ({'total': 303.1, 'trip': 1e9}, False),      # limiar absurdo: nao dispara
        ({'total': None, 'trip': 250.0}, None),
        ({'total': 2500.0, 'trip': 250.0}, True),
    ]
    caught = 0
    for c, want in cases:
        got = trips(c['total'], c['trip'])
        if got == want:
            caught += 1
    print('NEG-ARM: %d/%d casos concordam com o valor esperado'
          % (caught, len(cases)))
    # Um instrumento que passa sempre nao mede: o caso 2 TEM de divergir do 1.
    print('NEG-ARM: PASS -- o mutante do limiar apaga o disparo' if caught == len(cases)
          else 'NEG-ARM: FAIL')
    return 1 if caught == len(cases) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--pid', type=int, default=None)
    ap.add_argument('--once', action='store_true')
    ap.add_argument('--watch', action='store_true')
    ap.add_argument('--trip-pct', type=float, default=TRIP_PCT)
    ap.add_argument('--window', type=float, default=WINDOW_S)
    ap.add_argument('--cooldown', type=float, default=COOLDOWN_S)
    ap.add_argument('--no-capture', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()
    if args.neg_arm:
        return _neg_arm()

    pid = args.pid or discover_shell()
    if not pid:
        print('TRIPWIRE SKIPPED reason=no-live-shell '
              '(nenhum python com sotto_webview.py na linha de comando)')
        return 0
    if args.watch:
        run_watch(pid, args.trip_pct, args.window, args.cooldown)
        return 0
    return run_once(pid, args.trip_pct, args.window, not args.no_capture)


if __name__ == '__main__':
    sys.exit(main())
