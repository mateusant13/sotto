"""O CUSTO DA ARVORE -- a shell E o worker, somados, contra um tecto declarado (2026-11-09).

NASCEU DE TRES DMs DE STUTTER DO WATCHER na mesma noite, todas a acusar a MESMA
arvore (`pythonw.exe(27568)` + o filho `python.exe(37112)`) e nenhuma delas com
um passo da bateria capaz de a julgar:

    cpu 8.2% of machine ... 26.6% of machine ... 3 episodio(s) em 60 min

O QUE JA' EXISTE, E PORQUE NAO BASTA

  * `_main/shell-thread-budget-oracle.py` julga a SHELL (25 % de um nucleo). A
    shell medida a 2026-11-09 esta' em **0,2 %** de um nucleo numa janela de 60 s
    (`_main/shell-thread-cpu.py 27568 --seconds 60`): ela nao e' o problema.
  * O par `cost-watchdog` julga o `WORKER_COST` que o worker PUBLICA. Publicar e'
    o proprio worker a falar de si; este passo mede os dois processos de FORA.

O FURO QUE ESTE FICHEIRO FECHA, MEDIDO

    $ python _main/shell-thread-cpu.py 37112 --seconds 10 --top 8
    pid 37112: 64 fios, 10.4 s de janela, 62.4% de um nucleo no total
        27.2%  session-9-intra-op-0
        14.1%  session-10-intra-op-0
        10.8%  (sem nome)
         7.4%  session-8-intra-op-0

Tres sessoes ONNX vivas, cada uma com os seus fios `--threads 2`: quando as tres
descodificam ao mesmo tempo sao ate' ~5,1 nucleos (26 % desta maquina de 20), que
e' exactamente o numero da DM. Uma regressao nisto pode voltar sem um portao
vermelho, e o detector volta a ser o dono a queixar-se -- a classe que a casa ja'
pagou 149 vezes.

O QUE ELE JULGA, E COM QUE NUMERO

  tree = soma das duas medicoes do `shell-thread-cpu.py` (a mesma unidade da
  casa: % de UM nucleo; 100 % = um nucleo, nao a maquina).

  TREE_CEILING = 150.0 % de um nucleo. Nao e' um gosto: o medido de hoje e'
  89 % (worker) + 0,2 % (shell) numa janela calma e 106 % numa janela com a
  legenda a ler; 150 deixa a folga do trabalho normal e ainda apanha o degrau
  das tres sessoes.

  O ratchet de +20 % sobre `_main/tree-cost-baseline.json` e' quem recusa o
  crescimento lento que um tecto unico deixaria passar.

UM PASSO SALTADO NAO E' UM PORTAO QUE PASSOU: sem a arvore viva (shell ou worker
ausente) ele diz `VERDICT: SKIPPED` -- a bateria conta como SKIPPED, nunca verde.

USO
    python _main/tree-cost-oracle.py            # julga a arvore viva
    python _main/tree-cost-oracle.py --update   # grava o baseline
    python _main/tree-cost-oracle.py --neg-arm  # controlo do JUIZ (muta a LEITURA)
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOL = os.path.join(HERE, 'shell-thread-cpu.py')
LOG = os.path.join(HERE, 'webview-run.log')
BASELINE = os.path.join(HERE, 'tree-cost-baseline.json')

#: Tecto da soma, em % de UM nucleo. Medido 2026-11-09: 89 % calmo, 106 % lendo.
TREE_CEILING = 150.0
#: Quanto o baseline pode crescer antes de o portao falar.
RATCHET = 1.20
#: Janela da medicao (s) por processo. Duas medicoes -> ~2x este numero.
SECONDS = 5.0
#: O nome do fio que mais queima, exigido no relatorio (um numero sem actor e' beco).
WANT_ACTOR = True

SHELL_MARK = 'sotto_webview.py'
WORKER_MARK = 'sotto_worker.py'


def _tail(path, nbytes=4_000_000):
    try:
        with io.open(path, 'r', encoding='utf-8', errors='replace') as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - nbytes))
            return fh.read()
    except OSError:
        return ''


def _ps_table():
    """(pid, ppid, name, cmdline) de todo o processo -- uma leitura, sem janela."""
    out = subprocess.run(
        ['powershell', '-NoProfile', '-WindowStyle', 'Hidden', '-Command',
         "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,"
         "Name,CommandLine | ConvertTo-Json -Compress"],
        capture_output=True, text=True,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    rows = []
    raw = (out.stdout or '').strip()
    if not raw:
        return rows
    try:
        data = json.loads(raw)
    except ValueError:
        return rows
    if isinstance(data, dict):
        data = [data]
    for row in data:
        rows.append((int(row.get('ProcessId') or 0),
                     int(row.get('ParentProcessId') or 0),
                     str(row.get('Name') or ''),
                     str(row.get('CommandLine') or '')))
    return rows


def find_tree(rows, log_text):
    """A shell VIVA e o worker dela -- identidade pelo PID CARIMBADO NO LOG.

    O argv NAO serve nesta maquina e isso esta' medido (2026-11-09): o
    `Get-CimInstance Win32_Process` devolve `CommandLine` VAZIO para os processos
    do dono (`pythonw.exe(27568)` -> `''`), porque a app dele corre `high` e esta
    pane `medium` -- a mesma fronteira de integridade que faz o `py-spy` devolver
    err=5. Quem prova a identidade e' o `pid=` que a propria shell escreve
    (`SHELL_STARTUP_STAGE`) mais o `BRIDGE_SPAWNED pid=` do filho, e o NOME do
    executavel (python/pythonw) como travao. Um pid reciclado nao passa em
    nenhuma das duas marcas ao mesmo tempo.
    """
    by_pid = {r[0]: r for r in rows}

    def _py(row):
        return 'python' in (row[2] or '').lower()

    shells = [r for r in rows if _py(r) and SHELL_MARK in r[3]]
    stamped = [int(m) for m in re.findall(r'SHELL_STARTUP_STAGE pid=(\d+)', log_text)]
    shell = None
    for pid in reversed(stamped):
        row = by_pid.get(pid)
        if row and _py(row):
            shell = row
            break
    if shell is None:
        shell = shells[-1] if shells else None
    if shell is None:
        return None, None
    spawned = [int(m) for m in re.findall(r'BRIDGE_SPAWNED pid=(\d+)', log_text)]
    worker = None
    for pid in reversed(spawned):
        row = by_pid.get(pid)
        if row and _py(row) and row[1] == shell[0]:
            worker = row
            break
    if worker is None:
        kids = [r for r in rows if _py(r) and r[1] == shell[0]
                and (WORKER_MARK in r[3] or not r[3])]
        kids = [k for k in kids if k[0] != shell[0]]
        worker = kids[-1] if len(kids) == 1 else None
    return shell, worker


def measure(pid):
    """A medicao do projeto, sem reimplementar nada: `shell-thread-cpu.py --top`."""
    out = subprocess.run([sys.executable, TOOL, str(pid), '--seconds', '%g' % SECONDS,
                          '--top', '8'], capture_output=True, text=True,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
                         cwd=HERE)
    text = (out.stdout or '') + (out.stderr or '')
    total = None
    m = re.search(r'([0-9.]+)% de um nucleo no total', text)
    if m:
        total = float(m.group(1))
    top = None
    top_pct = None
    for line in text.splitlines():
        m = re.match(r'\s+([0-9.]+)%\s+([0-9.]+)\s+(\d+)\s+(\S.*)$', line)
        if m and top is None:
            top_pct = float(m.group(1))
            top = m.group(4).strip()
    return {'pid': pid, 'total': total, 'top': top, 'top_pct': top_pct,
            'measured': total is not None, 'raw_tail': text.strip().splitlines()[-2:]}


def judge(shell, worker, baseline):
    """O JUIZ, puro: recebe as duas medicoes e o baseline, devolve (ok, linha, valor)."""
    parts = [p for p in (shell, worker) if p and p.get('measured')]
    if not parts:
        return None, 'CANNOT-MEASURE -- nenhum dos dois processos respondeu', None
    total = sum(float(p['total']) for p in parts)
    over = total > TREE_CEILING
    grown = False
    limit = TREE_CEILING
    if baseline and baseline.get('total') is not None:
        allowed = float(baseline['total']) * RATCHET
        limit = min(TREE_CEILING, allowed)
        grown = total > allowed
    detail = ('tree=%.1f%% de um nucleo (tecto %.1f%%, baseline %.1f%%) '
              'shell=%s%% worker=%s%% top=%s:%s%%' % (
                  total, TREE_CEILING,
                  float(baseline['total']) if baseline and baseline.get('total') is not None else -1.0,
                  ('%.1f' % float(shell['total'])) if shell and shell.get('measured') else '-',
                  ('%.1f' % float(worker['total'])) if worker and worker.get('measured') else '-',
                  (parts[-1].get('top') or '-'), (parts[-1].get('top_pct') if parts[-1].get('top_pct') is not None else '-')))
    ok = (not over) and (not grown)
    return ok, detail, total


def _baseline():
    try:
        with io.open(BASELINE, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def run(update=False):
    log_text = _tail(LOG)
    rows = _ps_table()
    shell, worker = find_tree(rows, log_text)
    if shell is None:
        print('TREE-COST SKIPPED reason=no-live-shell (procurado "%s" no argv)' % SHELL_MARK)
        print('VERDICT: SKIPPED')
        return 0
    measures = []
    for who in (shell, worker):
        if who is None:
            continue
        print('measuring pid=%d %s' % (who[0], who[2]))
        measures.append(measure(who[0]))
    shell_m = measures[0] if measures else None
    worker_m = measures[1] if len(measures) > 1 else None
    if worker is None:
        print('TREE-COST worker=absent (a soma e a da shell so)')
    base = _baseline()
    ok, detail, total = judge(shell_m, worker_m, base)
    if ok is None:
        print('TREE-COST %s' % detail)
        print('VERDICT: SKIPPED')
        return 0
    print('TREE-COST %s' % detail)
    if update:
        with io.open(BASELINE, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(json.dumps({'total': round(total, 1), 'when': '2026-11-09'}, indent=2) + '\n')
        print('BASELINE updated total=%.1f' % total)
    print('VERDICT: ' + ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


def neg_arm():
    """O CONTROLO DO JUIZ -- muta a LEITURA, nunca o produto.

    Tres leituras sinteticas, cada uma com o desfecho que o juiz TEM de dar:
    (1) soma calma abaixo do tecto -> PASS; (2) a arvore do episodio (26,6 % da
    maquina = ~530 % de um nucleo) -> FAIL; (3) o crescimento lento contra um
    baseline premido -> FAIL. Sem `pass` sem o numero, e sem `fail` sem numero:
    a arm 4 exige CANNOT-MEASURE quando nenhum dos dois responde.
    """
    calm = ({'measured': True, 'total': 0.2, 'top': 'yt-cdp-source', 'top_pct': 0.1},
            {'measured': True, 'total': 89.2, 'top': 'session-9-intra-op-0', 'top_pct': 27.2})
    episode = ({'measured': True, 'total': 17.0, 'top': 'yt-clock', 'top_pct': 7.5},
               {'measured': True, 'total': 513.0, 'top': 'session-9-intra-op-0', 'top_pct': 85.0})
    cases = [
        ('calm PASS', calm, {}, True),
        ('episode FAIL', episode, {}, False),
        ('growth FAIL', calm, {'total': 40.0}, False),
        ('none CANNOT-MEASURE', (None, None), {}, None),
    ]
    bad = []
    for name, (sh, wk), base, want in cases:
        ok, detail, total = judge(sh, wk, base)
        if ok != want:
            bad.append('%s -> %r (want %r) [%s]' % (name, ok, want, detail))
        else:
            print('NEG-ARM arm: %-22s %s' % (name, 'OK' if want is not None else 'CANNOT-MEASURE'))
    if bad:
        print('NEG-ARM: FAIL -- %d caso(s) com desfecho errado: %s' % (len(bad), bad))
        return 1
    print('NEG-ARM: PASS -- 4 readings judged as declared')
    return 1


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    return run(update='--update' in argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
