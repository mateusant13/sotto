#!/usr/bin/env python3
"""O PROBE DO STALL DO BRIDGE -- mede `exec_js TIMEOUT` numa instancia PRIVADA.

PORQUE EXISTE. `exec_js TIMEOUT after 10.0s` aparece 515 vezes no log do dono
(`_main/webview-run.log`, `grep -c`). A linha nao diz onde o tempo foi, e ha'
tres donos possiveis com correccoes opostas: o UI thread nao correu o callable,
o renderer nao respondeu, ou a continuacao .NET nao entrou em Python. Este probe
existe para produzir o NUMERO e o CENSO no mesmo trafego, antes e depois da
correccao.

O QUE FAZ, e cada passo e' medido:
  1. arranca uma instancia com `--mutex-name` PRIVADA (a do dono fica intocada) e
     `--log` proprio, com o token de um processo `high` do dono
     (`_main/launch-as-token.py`): um filho desta pane nasce `medium` e mede
     `WEBVIEW2_INIT_FAILED 0x80010108`;
  2. aponta `--worker` ao `_main/bridge-caption-feeder.py`, que escreve legendas
     e status ao ritmo de producao -- o microfone desta maquina esta' mudo,
     portanto uma instancia real mediria um sistema OCIOSO;
  3. `SOTTO_BRIDGE_CENSUS=1` liga o censo dentro do shell
     (`_main/bridge-census.py`): no instante do estouro ele escreve
     `BRIDGE_CENSUS` + uma linha por thread com a stack Python;
  4. le' o log e conta: `exec_js TIMEOUT`, `UI_THREAD_STALL`, censos, e
     legendas entregues.

O QUE NAO FAZ. Nao passa `--show` (nada aparece na tela do dono), nao mata a
instancia dele, nao toca em nenhum ficheiro do produto, e mata a PROPRIA
instancia no fim pela identidade da mutex privada.

USO
    python _main/bridge-stall-probe.py --run --seconds 300
    python _main/bridge-stall-probe.py --run --seconds 600 --tag after
    python _main/bridge-stall-probe.py --tree H:/sotto-wt/goal-bridge --tag x
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = os.environ.get('SOTTO_TMP') or r'I:\cc-tmp'
FREE_HOTKEY = 'Alt+Shift+F12'      # medido livre nesta caixa (pov-selftest)
FREE_LIVE_HOTKEY = 'Alt+Shift+F11'


def paths(tag):
    return {
        'log': os.path.join(TMP, 'bridge-%s.log' % tag),
        'out': os.path.join(TMP, 'bridge-%s.out' % tag),
        'cmd': os.path.join(TMP, 'bridge-%s.cmd' % tag),
        'mutex': 'SottoBridgeProbe-%s' % tag,
    }


def source_pid():
    """Um processo `high` do dono cujo token emprestamos: `explorer.exe`."""
    import ctypes
    import ctypes.wintypes as wt
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wt.HANDLE

    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD),
                    ('th32ProcessID', wt.DWORD), ('th32DefaultHeapID', ctypes.c_void_p),
                    ('th32ModuleID', wt.DWORD), ('cntThreads', wt.DWORD),
                    ('th32ParentProcessID', wt.DWORD), ('pcPriClassBase', ctypes.c_long),
                    ('dwFlags', wt.DWORD), ('szExeFile', ctypes.c_wchar * 260)]

    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    entry = Entry()
    entry.dwSize = ctypes.sizeof(Entry)
    found = []
    ok = k32.Process32FirstW(snap, ctypes.byref(entry))
    while ok:
        if str(entry.szExeFile).lower() == 'explorer.exe':
            found.append(int(entry.th32ProcessID))
        ok = k32.Process32NextW(snap, ctypes.byref(entry))
    k32.CloseHandle(snap)
    if not found:
        raise SystemExit('no explorer.exe: nothing to borrow a token from')
    return found[-1]


def write_runner(tree, p, seconds, census, feeder):
    """O runner .cmd da instancia de MEDICAO.

    `--no-lazy` NAO e' um detalhe: com o gate ligado (o comportamento do dono) a
    pagina do painel so' carrega quando ele pede o painel, e o log da primeira
    tentativa provou-o -- `PANEL_LAZY_GATE_ARMED registered=5` e DEPOIS NADA, nem
    `PRELOAD_ACTIVE` nem `BRIDGE_SPAWNED`, porque nao ha' pagina para receber um
    `emit`. Medir o canal do `emit` exige a pagina carregada; `--no-lazy` e' o
    braco de controlo que o proprio shell declara (`PANEL_LAZY_GATE_DISABLED`).

    `--with-worker` tambem, e pela razao oposta: `--exit-after` e' um FLAG DE
    MEDICAO, portanto o shell recusa o worker sozinho
    (`WORKER_AUTOSTART=declined reason=measurement-flag(--exit-after)`, medido no
    primeiro run deste probe: zero legendas, zero status). `--with-worker` e'
    autoritativo na tabela de `_worker_autostart_reason` e aponta ao feeder, nao
    ao modelo de ~2 GB.

    `--no-self-relaunch` tambem: o watcher de disco relanca a instancia quando
    um ficheiro de `app/webview` muda, e uma medicao que se auto-relanca a meio
    mede o relancamento -- medido aqui, 2026-11-01: um `py_compile` meu durante o
    run produziu `RC=1` e o log parou a meio.
    """
    body = (
        '@echo off\r\n'
        'cd /d %(tree)s\r\n'
        'set SOTTO_LIVE_HOTKEY=%(live)s\r\n'
        'set SOTTO_BRIDGE_CENSUS=%(census)s\r\n'
        'set SOTTO_NO_SELF_RELAUNCH=1\r\n'
        'set SOTTO_FEED_INTERVAL_MS=300\r\n'
        'set SOTTO_FEED_STATUS_S=4\r\n'
        '"%(py)s" "%(app)s" --mutex-name %(mutex)s --hotkey %(hotkey)s '
        '--worker "%(feeder)s" --with-worker --no-tray --no-lazy '
        '--no-self-relaunch --exit-after %(sec)d --log "%(log)s" '
        '> "%(out)s" 2>&1\r\n'
        'echo RC=%%ERRORLEVEL%% >> "%(out)s"\r\n'
    ) % {'tree': tree, 'live': FREE_LIVE_HOTKEY, 'census': census,
         'py': sys.executable,
         'app': os.path.join(tree, 'app', 'webview', 'sotto_webview.py'),
         'mutex': p['mutex'], 'hotkey': FREE_HOTKEY, 'feeder': feeder,
         'sec': int(seconds) + 20, 'log': p['log'], 'out': p['out']}
    with open(p['cmd'], 'w', encoding='ascii', newline='') as fh:
        fh.write(body)
    return p['cmd']


def burn(count):
    """`count` processos a CPU com prioridade BELOW_NORMAL, contidos e curtos.

    PORQUE. A leitura do repo e' que "the LOAD is the TRIGGER; the CODE is the
    FREEZE" (`UI_MARSHAL_TIMEOUT_S`), e o log do dono mostra os estouros dentro
    de janelas de carga (carregamento do modelo, 45 temas a correr em Edge
    headless). Medir a correccao num sistema OCIOSO mediria o sistema ocioso.

    O que isto NAO e': carga no PC do dono. Prioridade BELOW_NORMAL, um processo
    por core a MENOS do que o numero de cores, e o Windows cede a qualquer coisa
    que ele use. Os processos sao filhos deste probe e morrem com ele.
    """
    import ctypes
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    loop = 'while True: pass'
    procs = []
    for _ in range(max(0, int(count))):
        proc = subprocess.Popen([sys.executable, '-c', loop], creationflags=flags, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
        try:
            # BELOW_NORMAL_PRIORITY_CLASS = 0x4000
            ctypes.windll.kernel32.SetPriorityClass(
                int(proc._handle), 0x4000)  # noqa: SLF001 -- um handle e' o que ha'
        except Exception:  # noqa: BLE001 -- a prioridade e' cortesia, nao correccao
            pass
        procs.append(proc)
    return procs


def tree_artifacts(tree, mutex):
    """Os ficheiros da ARVORE que uma instancia de medicao escreve dela propria.

    MEDIDO 2026-11-01: um run deixou `_main/panel-visibility.json` modificado
    (o `PanelVisibilityWriter` escreve-o no repo, nao ao lado da mutex) e dois
    `_main/panel-state.<mutex>.json` novos. Um instrumento que deixa o repo sujo
    faz o proximo leitor achar que o produto mudou. Devolve o que e' preciso para
    repor: o conteudo anterior do ficheiro de visibilidade (ou None) e a lista de
    ficheiros de estado a apagar.
    """
    path = os.path.join(tree, '_main', 'panel-visibility.json')
    try:
        with open(path, 'rb') as fh:
            before = fh.read()
    except OSError:
        before = None
    return {'visibility': path, 'before': before,
            'state': os.path.join(tree, '_main', 'panel-state.%s.json' % mutex)}


def restore_tree_artifacts(snap):
    """Repoe o que `tree_artifacts` fotografou. Nunca lanca."""
    out = {'visibility': 'absent', 'state': 'absent'}
    try:
        if snap['before'] is None:
            if os.path.exists(snap['visibility']):
                os.remove(snap['visibility'])
                out['visibility'] = 'removed'
        else:
            with open(snap['visibility'], 'rb') as fh:
                same = fh.read() == snap['before']
            if not same:
                with open(snap['visibility'], 'wb') as fh:
                    fh.write(snap['before'])
                out['visibility'] = 'restored'
            else:
                out['visibility'] = 'unchanged'
    except OSError as exc:
        out['visibility'] = 'failed: %r' % (exc,)
    try:
        if os.path.exists(snap['state']):
            os.remove(snap['state'])
            out['state'] = 'removed'
    except OSError as exc:
        out['state'] = 'failed: %r' % (exc,)
    return out


def reap(mutex):
    """Mata as instancias MEDIDAS que sobreviveram -- pela mutex privada.

    Uma medicao que sobrevive ocupa a tecla global e a memoria do dono; a
    identidade e' o `--mutex-name` no `CommandLine`, nunca um nome de processo
    (o filtro por nome ja' matou processos alheios neste repo).
    """
    killed = []
    try:
        import psutil
    except ImportError:
        return killed
    targets = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if (proc.info['name'] or '').lower() not in ('python.exe', 'pythonw.exe'):
                continue
            cmd = ' '.join(proc.info['cmdline'] or [])
            if ('--mutex-name %s' % mutex) in cmd and 'sotto_webview' in cmd:
                targets.append(proc.info['pid'])
        except Exception:  # noqa: BLE001
            continue
    if not targets:
        return killed
    spec = importlib.util.spec_from_file_location(
        'relaunch', os.path.join(HERE, 'sotto-relaunch.py'))
    relaunch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(relaunch)
    for pid in targets:
        try:
            killed.append((pid, bool(relaunch.kill(pid))))
        except Exception as exc:  # noqa: BLE001
            killed.append((pid, 'failed: %r' % exc))
    return killed


def launch(tree, p, seconds, census, feeder):
    os.makedirs(TMP, exist_ok=True)
    for key in ('log', 'out'):
        try:
            os.remove(p[key])
        except OSError:
            pass
    write_runner(tree, p, seconds, census, feeder)
    cmd = [sys.executable, os.path.join(HERE, 'launch-as-token.py'),
           str(source_pid()), 'cmd.exe', '/c', p['cmd']]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
    return (proc.stdout or '').strip() or (proc.stderr or '').strip()


def wait_done(p, seconds):
    """Espera pelo fim do run, com uma janela de progresso legivel."""
    deadline = time.time() + seconds + 60
    while time.time() < deadline:
        if os.path.exists(p['out']):
            try:
                if 'RC=' in open(p['out'], encoding='utf-8', errors='replace').read():
                    return True
            except OSError:
                pass
        time.sleep(2.0)
    return False


COUNT_RE = {
    'exec_js_timeout': r'WARN exec_js TIMEOUT',
    'exec_js_stall': r'WARN exec_js STALL',
    'ui_thread_stall': r'UI_THREAD_STALL',
    'census': r'BRIDGE_CENSUS ',
    'census_thread': r'BRIDGE_CENSUS_THREAD ',
    'captions': r'BRIDGE_CAPTION_SENT',
    'stats_pushes': r'BRIDGE_STATS_PUSH',
    'census_on': r'BRIDGE_CENSUS_ON',
    'census_failed': r'BRIDGE_CENSUS_FAILED',
}


def read(p):
    try:
        with open(p['log'], encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def summarise(text):
    out = {}
    for name, pat in COUNT_RE.items():
        out[name] = len(re.findall(pat, text))
    out['timeout_scripts'] = sorted(set(
        re.findall(r'exec_js TIMEOUT after [0-9.]+s script=(.{0,70})', text)))
    return out


def census_blocks(text):
    """Cada censo: a linha `BRIDGE_CENSUS` e as threads que a seguem."""
    blocks = []
    cur = None
    for line in text.splitlines():
        if 'BRIDGE_CENSUS ' in line:
            cur = [line.split('BRIDGE_CENSUS ', 1)[-1]]
            blocks.append(cur)
        elif 'BRIDGE_CENSUS_THREAD ' in line and cur is not None:
            cur.append(line.split('BRIDGE_CENSUS_THREAD ', 1)[-1])
        elif 'BRIDGE_CENSUS ' not in line:
            cur = None if not line.strip() else cur
    return blocks


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--tree', default=ROOT)
    ap.add_argument('--tag', default='bridge1')
    ap.add_argument('--seconds', type=float, default=300.0)
    ap.add_argument('--census', default='1')
    ap.add_argument('--census-blocks', type=int, default=4,
                    help='quantos censos completos imprimir')
    ap.add_argument('--burn', type=int, default=0,
                    help='processos de carga a CPU (BELOW_NORMAL) durante o run')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--keep', action='store_true', help='nao mata no fim')
    args = ap.parse_args(argv)

    tree = os.path.abspath(args.tree).replace('\\', '/')
    feeder = os.path.join(tree, '_main', 'bridge-caption-feeder.py')
    p = paths(args.tag)
    if not args.run:
        print('dry: tree=%s feeder=%s log=%s mutex=%s'
              % (tree, feeder, p['log'], p['mutex']))
        print('     census=%s seconds=%g' % (args.census, args.seconds))
        return 0
    if not os.path.exists(feeder):
        raise SystemExit('sem feeder em %s' % feeder)
    print('LAUNCH tree=%s log=%s mutex=%s census=%s seconds=%g burn=%d'
          % (tree, p['log'], p['mutex'], args.census, args.seconds, args.burn))
    snap = tree_artifacts(tree, p['mutex'])
    print('LAUNCH_OUT %s' % launch(tree, p, args.seconds, args.census, feeder))
    burners = burn(args.burn) if args.burn else []
    if burners:
        print('BURN procs=%d priority=below-normal pid=%s'
              % (len(burners), ','.join(str(b.pid) for b in burners)))
    try:
        done = wait_done(p, args.seconds)
    finally:
        for proc in burners:
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
    text = read(p)
    s = summarise(text)
    blocks = census_blocks(text)
    if not args.keep:
        s['reaped'] = reap(p['mutex'])
    s['tree_artifacts'] = restore_tree_artifacts(snap)
    s['done'] = done
    s['log_bytes'] = len(text)
    s['census_blocks'] = len(blocks)
    if args.json:
        print(json.dumps({'summary': s}, indent=2, default=str))
    else:
        print('DONE=%s log_bytes=%d' % (done, len(text)))
        for k in ('exec_js_timeout', 'exec_js_stall', 'ui_thread_stall',
                  'census', 'census_on', 'census_failed', 'captions',
                  'stats_pushes', 'reaped', 'tree_artifacts'):
            print('  %-16s %s' % (k, s.get(k)))
        for script in s['timeout_scripts']:
            print('  TIMEOUT_SCRIPT %s' % script)
        for block in blocks[:max(0, args.census_blocks)]:
            print('--- CENSO ---')
            for line in block:
                print('  ' + line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
