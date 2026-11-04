#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
# NO-BUG: instrumento de medicao (profiler de pilhas); nao desbloqueia um bug nomeado, responde "onde e que o tempo vai"
"""SOTTO-PROFILE -- o trace REAL das pilhas do Sotto (py-spy), nao um amostrador de sistema.

O QUE HAVIA, E PORQUE NAO CHEGAVA. `_main/sotto-perf-log.py` mede o MUNDO:
`sleep(25 ms)` slip (o stutter que o dono sente), CPU incl. interrupt/dpc, disco,
RAM, e a familia de processos atribuida pela ARVORE. Isso responde "o Sotto
atrapalha?" -- e nao responde "onde e que o Sotto gasta o tempo dele".

Para a segunda pergunta e preciso um perfilador de PILHAS. Este ficheiro usa
`py-spy` (0.4.2, ja instalado nesta maquina): le as pilhas do processo Python a
correr, a 100 Hz, sem carregar codigo no alvo e sem escrever gigabytes. Escolhi-o
em vez de ETW (`wpr.exe` existe, `wpa.exe` NAO existe nesta maquina, e um traco
de CPU com stacks enche varios GB com `I:` a 0,6 % livre) e em vez de `cProfile`
(que exigiria instrumentar o worker que o dono esta a usar).

O QUE MEDE:
  --attach --seconds 60   grava a familia do Sotto: pilhas colapsadas do worker e
                          da shell, e imprime as 10 molduras que mais tempo
                          proprio gastam (self time) em cada um
  --attach --dump         uma fotografia AGORA das pilhas de cada processo -- a
                          ferramenta certa para "o que e que ele estava a fazer
                          quando o meu rato travou"
  --spawn -- CMD ...      arranca CMD **sob o profiler** (modo spawn do py-spy) e
                          perfila-o do primeiro ao ultimo instante
  --selftest              prova que o instrumento ve pilhas de verdade: arranca
                          um filho com uma funcao de nome conhecido, grava-o, e
                          exige que esse nome apareca no topo

LIMITACAO MEDIDA, E NAO UMA DESCULPA (2026-10-23, esta maquina): o **attach
falha** com `Failed to get process executable name ... os error 31` quando o
chamador corre no contexto do servidor (o mesmo contexto em que a app sobe sem
painel: `TRAY_ICON_ADD winerror=5`, `WEBVIEW2_INIT_FAILED`). O **modo spawn
funciona** -- 395 amostras, pilhas com `ficheiro:linha`. Logo ha dois caminhos
honestos: `--spawn` para tudo o que se pode arrancar de proposito (o worker
offline com `--audio`), e `--attach` a partir de uma sessao interactiva para a
app do dono. Um profiler que nao se prova a si mesmo nao vale nada, e por isso o
`--selftest` usa o caminho que mede (spawn) e falha se nao vir a moldura certa.

NAO LANCA A APP por si: `--attach` liga-se ao que JA esta a correr; `--spawn`
arranca o comando que lhe for dado. Nao instala hook nem abre janela.

    python _main\\sotto-profile.py --selftest
    python _main\\sotto-profile.py --attach --dump
    python _main\\sotto-profile.py --attach --seconds 60
    python _main\\sotto-profile.py --spawn -- pythonw.exe worker\\sotto_worker.py --audio I:\\cc-tmp\\amostra.wav
"""
import argparse
import collections
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PY_SPY = r'C:\Program Files\Python311\Scripts\py-spy.exe'
TMP = os.environ.get('TMPDIR') or r'I:\cc-tmp'

# O ARTEFACTO, nunca uma palavra generica: o filtro nomeia os ficheiros que a app
# e o worker correm. "sotto" sozinho ja matou dois processos alheios.
SEEDS = ('sotto_webview.py', 'sotto_worker.py')
GUI_SHELL = 'sotto_webview.py'
LOG = os.path.join(REPO, '_main', 'webview-run.log')


def _psutil():
    import psutil
    return psutil


def _log_pids(tail_bytes=300000):
    """Os `pid=` do PROPRIO log da app.

    MEDIDO 2026-10-23: um processo lancado por `schtasks /it` vem com
    `CommandLine` VAZIO na consulta CIM (o shell nasceu com
    `TRAY_ICON_ADD ok=true`, `pid=51812`, e o censo por cmdline deu 0). E a
    mesma licao que ja estava escrita para as apps `start`-detached: semear o
    conjunto pelo `pid=` do log, nunca so pela tabela de processos.
    """
    pids = set()
    try:
        with open(LOG, 'rb') as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - tail_bytes))
            body = fh.read().decode('utf-8', 'replace')
    except OSError:
        return pids
    for m in re.finditer(r'(?:shell=webview2[^\n]*?\bpid=|BRIDGE_SPAWNED pid=)(\d+)',
                         body):
        pids.add(int(m.group(1)))
    return pids


def family():
    """{pid: (nome, cmdline_curta)} da arvore da app + do worker.

    Duas sementes: o `cmdline` (funciona quando o processo e nosso) **e** o
    `pid=` do log (funciona quando o `CommandLine` vem vazio). Semear so por um
    deles ja deu 0 processos para uma app saudavel.
    """
    ps = _psutil()
    seeds = []
    for p in ps.process_iter(['pid', 'cmdline']):
        try:
            cmd = ' '.join(p.info.get('cmdline') or [])
        except Exception:  # noqa: BLE001
            continue
        if any(s in cmd for s in SEEDS):
            seeds.append(p.info['pid'])
    seeds.extend(_log_pids())
    if not seeds:
        return {}
    out = {}
    for pid in seeds:
        try:
            proc = ps.Process(pid)
            name = proc.name()
        except Exception:  # noqa: BLE001
            continue
        try:
            kids = proc.children(recursive=True)
        except Exception:  # noqa: BLE001
            kids = []
        for p in [proc] + kids:
            try:
                cmd = ' '.join(p.cmdline())
            except Exception:  # noqa: BLE001
                cmd = ''
            # msedgewebview2 so conta se for FILHO de um processo nosso: os 38
            # da outra app nao sao do Sotto (licao do _strip-stats-log-probe).
            if p.pid in out:
                continue
            try:
                out[p.pid] = (p.name(), cmd[-120:])
            except Exception:  # noqa: BLE001
                out[p.pid] = (name, '')
    return out


def _py_spy(args, timeout=300):
    return subprocess.run([PY_SPY] + args, capture_output=True, text=True,
                          timeout=timeout, errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)


def dump(pid):
    r = _py_spy(['dump', '--pid', str(pid)], timeout=60)
    return (r.stdout or r.stderr or '').strip()


def record_raw(pid, seconds, rate):
    """Pilhas colapsadas: 'a;b;c 12' por linha (formato `raw` do py-spy).

    ATENCAO: `--output -` nao devolve o raw por stdout nesta build (0.4.2);
    escreve-se para um ficheiro e le-se. Medido em 2026-10-23.
    """
    out = os.path.join(TMP, 'spy-attach-%d.raw' % pid)
    r = _py_spy(['record', '--pid', str(pid), '--duration', str(int(seconds)),
                 '--rate', str(int(rate)), '--idle', '--format', 'raw',
                 '--output', out],
                timeout=int(seconds) + 120)
    body = ''
    if os.path.isfile(out):
        with open(out, encoding='utf-8', errors='replace') as fh:
            body = fh.read()
        try:
            os.remove(out)
        except OSError:
            pass
    # O py-spy desta build escreve o ERRO em stdout (medido 2026-10-23): devolver
    # so o stderr fazia uma falha de attach parecer "sem amostras", sem causa.
    return body, ((r.stdout or '') + (r.stderr or ''))


def record_spawn(cmd, rate, timeout=900):
    """Perfila um comando do principio ao fim (modo spawn: nao precisa de attach).

    Foi o caminho que FUNCIONOU nesta maquina -- ver a limitacao no topo.
    """
    out = os.path.join(TMP, 'spy-spawn-%d.raw' % os.getpid())
    r = subprocess.run([PY_SPY, 'record', '--format', 'raw', '--output', out,
                        '--rate', str(int(rate)), '--'] + list(cmd),
                       capture_output=True, text=True, timeout=timeout,
                       errors='replace', creationflags=subprocess.CREATE_NO_WINDOW)
    body = ''
    if os.path.isfile(out):
        with open(out, encoding='utf-8', errors='replace') as fh:
            body = fh.read()
        try:
            os.remove(out)
        except OSError:
            pass
    return body, ((r.stdout or '') + (r.stderr or ''))


def top_frames(collapsed, n=10):
    """As funcoes que mais tempo PROPRIO gastam (a folha da pilha)."""
    own = collections.Counter()
    total = 0
    for line in collapsed.splitlines():
        line = line.strip()
        if not line or ' ' not in line:
            continue
        stack, _, samples = line.rpartition(' ')
        try:
            samples = int(samples)
        except ValueError:
            continue
        total += samples
        leaf = stack.rsplit(';', 1)[-1].strip()
        own[leaf] += samples
    if not total:
        return total, []
    return total, [(f, c, 100.0 * c / total) for f, c in own.most_common(n)]


def self_test():
    """Prova que o instrumento ve pilhas de verdade -- contra um filho conhecido.

    Usa o caminho que MEDIU (spawn): o attach falha neste contexto com erro 31,
    e um selftest que usa o caminho partido nao prova nada sobre o que funciona.
    """
    code = (
        'import time\n'
        'def surely_the_burning_frame():\n'
        '    t = time.time()\n'
        '    while time.time() - t < 4.0:\n'
        '        sum(i*i for i in range(2000))\n'
        'surely_the_burning_frame()\n'
    )
    raw, err = record_spawn([sys.executable, '-c', code], 100, timeout=180)
    total, top = top_frames(raw, 5)
    names = [f for f, _, _ in top]
    hit = any('surely_the_burning_frame' in f for f in names)
    print('amostras=%d | top=%s' % (total, names[:3]))
    if not total:
        print('py-spy disse: %s' % (err.strip().splitlines()[:3],))
    print('SOTTO-PROFILE SELFTEST %s' % ('PASS' if hit and total else 'FAIL'))
    return 0 if (hit and total) else 2


def report(seconds, rate):
    fam = family()
    if not fam:
        print('a familia do Sotto NAO esta a correr (0 processos com %s).'
              % ' / '.join(SEEDS))
        print('este instrumento NAO lanca a app (HARD RULE: so o LEAD lanca).')
        return 4
    print('familia: %d processo(s)' % len(fam))
    for pid, (name, cmd) in sorted(fam.items()):
        print('  pid=%-7d %-22s %s' % (pid, name, cmd))
    ps = _psutil()
    for pid, (name, cmd) in sorted(fam.items()):
        try:
            p = ps.Process(pid)
            cpu = p.cpu_percent(interval=0.3)
            rss = p.memory_info().rss / (1024 * 1024)
            priv = getattr(p.memory_info(), 'private', 0) / (1024 * 1024)
        except Exception:  # noqa: BLE001
            continue
        print()
        print('=== pid=%d %s | cpu=%.1f%% rss=%.1f MB private=%.1f MB'
              % (pid, name, cpu, rss, priv))
        if 'python' not in name.lower():
            continue
        raw, err = record_raw(pid, seconds, rate)
        total, top = top_frames(raw, 10)
        if not total:
            print('  sem amostras (%s)' % (err.strip().splitlines()[:1] or 'sem stderr'))
            continue
        print('  %d amostras a %d Hz durante %d s -- tempo PROPRIO por moldura:'
              % (total, rate, seconds))
        for frame, count, pct in top:
            print('   %5.1f%%  %6d  %s' % (pct, count, frame))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--attach', action='store_true',
                    help='perfila a familia do Sotto que JA esta a correr')
    ap.add_argument('--dump', action='store_true',
                    help='uma fotografia das pilhas agora (sem gravar)')
    ap.add_argument('--seconds', type=int, default=45)
    ap.add_argument('--rate', type=int, default=100)
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--out', default='',
                    help='escreve tambem o relatorio neste ficheiro')
    ap.add_argument('--spawn', action='store_true',
                    help='arranca e perfila um comando (-- <cmd ...>)')
    ap.add_argument('cmd', nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:  # noqa: BLE001
        pass
    if args.out:
        # Um relatorio lançado por `schtasks` nao tem consola: o ficheiro E o canal.
        class _Tee(object):
            def __init__(self, path):
                self.fh = open(path, 'w', encoding='utf-8', newline='\n')

            def write(self, s):
                self.fh.write(s)
                self.fh.flush()

            def flush(self):
                self.fh.flush()

        sys.stdout = _Tee(args.out)
    if args.selftest:
        return self_test()
    if args.spawn:
        cmd = list(args.cmd)
        while cmd and cmd[0] in ('--',):
            cmd.pop(0)
        if not cmd:
            print('--spawn precisa do comando: --spawn -- <cmd> [args]')
            return 2
        print('a perfilar (spawn, %d Hz): %s' % (max(10, args.rate), ' '.join(cmd)))
        raw, err = record_spawn(cmd, max(10, args.rate))
        total, top = top_frames(raw, 12)
        for line in err.strip().splitlines()[-3:]:
            print('  py-spy: %s' % line)
        if not total:
            print('SOTTO-PROFILE VERDICT FAIL (0 amostras)')
            return 2
        print('%d amostras -- tempo PROPRIO por moldura:' % total)
        for frame, count, pct in top:
            print('  %5.1f%%  %6d  %s' % (pct, count, frame))
        print('SOTTO-PROFILE VERDICT PASS')
        return 0
    if not os.path.isfile(PY_SPY):
        print('py-spy nao esta em %s' % PY_SPY)
        return 2
    if args.dump or not args.seconds:
        fam = family()
        if not fam:
            print('a familia do Sotto nao esta a correr -- nada para fotografar')
            return 4
        for pid, (name, _cmd) in sorted(fam.items()):
            if 'python' not in name.lower():
                continue
            print('=== pid=%d %s ===' % (pid, name))
            print(dump(pid))
        return 0
    if args.attach:
        return report(max(3, args.seconds), max(10, args.rate))
    ap.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
