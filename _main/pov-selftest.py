"""POV DO DONO, MEDIDO DE FORA -- sem tocar na tela dele e sem roubar-lhe a tecla.

PORQUE EXISTE (2026-11-01). O unico caminho para abrir o painel como USUARIO e' o `Alt+C` do
Windows, e o `Alt+C` do dono pertence a instancia dele. Ler o codigo nao responde a pergunta que
importa ("o que acontece quando ele aperta"), e uma lane nao pode apertar a tecla por ele.

O QUE ESTE INSTRUMENTO FAZ, e cada passo foi medido, nao suposto:

  1. arranca uma SEGUNDA instancia da app com `--mutex-name <privado>`, portanto com um lock que
     nao e' o do dono -- as duas coexistem, e o `SINGLE_INSTANCE_SKIPPED` no log prova-lo;
  2. da'-lhe uma tecla LIVRE (`--hotkey Alt+Shift+F12`), para que `RegisterHotKey` nao falhe com
     1409 e a app nao ponha a caixa modal de `HOTKEY_UNAVAILABLE` na tela dele;
  3. larga-a com o token de um processo `high` do proprio dono (`_main/launch-as-token.py`,
     fonte = `explorer.exe`), porque um filho desta pane corre a `medium` e mede
     `WEBVIEW2_INIT_FAILED 0x80010108` -- medido nesta sessao, duas vezes;
  4. le' o que a app escreveu (`SELFTEST arm=...`, `PANEL_SHOWN/HIDDEN`, `focus_stolen=...`) e
     imprime a sequencia. **Nao inventa um veredicto que o log nao da'.**

O QUE ELE NAO FAZ: nao chama `keybd_event`/`SendInput` (input sintetico mede o Windows, nao a app),
nao mata a instancia do dono, nao mostra nada na tela dele (`--show` nunca e' passado) e nao mexe
em ficheiro nenhum do produto.

USO
    python _main/pov-selftest.py --run            # arranca, mede e imprime a sequencia
    python _main/pov-selftest.py --run --keep     # nao mata a instancia no fim
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.environ.get('SOTTO_TMP') or r'I:\cc-tmp'
#: UM RUN POR TAG. Medido 2026-11-01 10:25: eu e uma lane corremos este instrumento
#: ao mesmo tempo em duas arvores diferentes e ambos escreveram o MESMO
#: `pov-selftest.log`; o reap de um matou a instancia do outro pelo nome da mutex
#: partilhada e as duas medicoes leram as linhas uma da outra. A tag separa log,
#: runner E mutex: `SOTTO_POV_TAG=lane-x python _main/pov-selftest.py --run`.
TAG = os.environ.get('SOTTO_POV_TAG') or 'main'
SELFTEST_LOG = os.path.join(TMP, 'pov-selftest-%s.log' % TAG)
SELFTEST_OUT = os.path.join(TMP, 'pov-selftest-%s.out' % TAG)
RUNNER = os.path.join(TMP, 'pov-selftest-run-%s.cmd' % TAG)

#: `--hotkey` tem de ser uma tecla que NINGUEM tem. Medido em 2026-10-07
#: (`_main/_audit-hotkey-probe.py`): Alt+F9 ja' estava tomado nesta caixa; Alt+Shift+F12 nao.
FREE_HOTKEY = 'Alt+Shift+F12'
#: A tecla da LEGENDA tambem e' desviada: a do dono (`Ctrl+Space`) e' exclusiva
#: do processo que a registou primeiro, e uma medicao que a apanhe rouba-lha.
FREE_LIVE_HOTKEY = 'Alt+Shift+F11'
MUTEX = 'SottoPovSelftest-%s' % TAG


def source_pid():
    """Um processo `high` do dono cujo token sabemos emprestar: `explorer.exe`."""
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
    ok = k32.Process32FirstW(snap, ctypes.byref(entry))
    found = []
    while ok:
        if str(entry.szExeFile).lower() == 'explorer.exe':
            found.append(int(entry.th32ProcessID))
        ok = k32.Process32NextW(snap, ctypes.byref(entry))
    k32.CloseHandle(snap)
    if not found:
        raise SystemExit('no explorer.exe on this box: nothing to borrow a token from')
    return found[-1]


def write_runner(exit_after):
    body = (
        '@echo off\r\n'
        'cd /d %s\r\n'
        'set SOTTO_LIVE_HOTKEY=%s\r\n'
        # `--no-self-relaunch`: medido em 2026-11-01 11:14 -- sem a bandeira o
        # `--exit-after` nao FECHA a medicao, ela RE-LANCA-SE como a instancia do
        # dono (pid 40064, viva 6 min depois dos 45 s pedidos, ja' sem a tag). Uma
        # medicao que se promove a app ocupa o mutex `Local\SottoShell` e o dono
        # fica sem conseguir abrir a dele.
        '"%s" "%s" --selftest --no-worker --no-self-relaunch --mutex-name %s --hotkey %s '
        '--exit-after %d --log "%s" > "%s" 2>&1\r\n'
        'echo RC=%%ERRORLEVEL%% >> "%s"\r\n'
    ) % (ROOT, FREE_LIVE_HOTKEY, sys.executable,
         os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py'),
         MUTEX, FREE_HOTKEY, exit_after, SELFTEST_LOG, SELFTEST_OUT, SELFTEST_OUT)
    with open(RUNNER, 'w', encoding='ascii', newline='') as fh:
        fh.write(body)
    return RUNNER


def launch(exit_after=45, wait=60.0):
    os.makedirs(TMP, exist_ok=True)
    for p in (SELFTEST_LOG, SELFTEST_OUT):
        try:
            os.remove(p)
        except OSError:
            pass
    write_runner(exit_after)
    pid = source_pid()
    cmd = [sys.executable, os.path.join(ROOT, '_main', 'launch-as-token.py'),
           str(pid), 'cmd.exe', '/c', RUNNER]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    print(proc.stdout.strip() or proc.stderr.strip())
    deadline = time.time() + wait
    while time.time() < deadline:
        if os.path.exists(SELFTEST_OUT) and 'RC=' in open(
                SELFTEST_OUT, 'r', encoding='utf-8', errors='replace').read():
            break
        time.sleep(1.0)
    return read_log()


def reap():
    """Mata as instâncias de MEDIÇÃO que sobreviveram ao run, e diz quantas.

    PORQUE EXISTE (medido 2026-11-01 10:24). Um run cujo `RC=` nunca chegou
    deixou o pid 38692 vivo durante oito minutos, com a `Ctrl+Space` registada
    por ele — e a app do dono, quando arrancou a seguir, escreveu
    `HOTKEY_REGISTER_FAILED role=live accelerator=Ctrl+Space winerror=1409` e
    ficou sem a tecla que ele pediu. Uma medição que sobrevive é uma fuga: ocupa
    a tecla global, a memória e o disco do dono.

    A identidade é a mutex PRIVADA no `CommandLine` (`--mutex-name`), nunca um
    nome de processo: o filtro por nome já matou dois processos alheios neste
    repo. O kill passa por `_main/sotto-relaunch.py`, que delega a um filho
    `high` (esta pane é `medium` e `taskkill` dá `Acesso negado`, medido).
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
            if '--mutex-name %s' % MUTEX in cmd and 'sotto_webview' in cmd:
                targets.append(proc.info['pid'])
        except Exception:  # noqa: BLE001 -- processo que morreu a meio da leitura
            continue
    if not targets:
        return killed
    spec = importlib.util.spec_from_file_location(
        'relaunch', os.path.join(ROOT, '_main', 'sotto-relaunch.py'))
    relaunch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(relaunch)
    for pid in targets:
        try:
            ok = bool(relaunch.kill(pid))
        except Exception as exc:  # noqa: BLE001
            print('reap: pid=%d falhou: %r' % (pid, exc))
            continue
        killed.append((pid, ok))
    return killed


def read_log():
    if not os.path.exists(SELFTEST_LOG):
        return {'exists': False, 'lines': []}
    with open(SELFTEST_LOG, 'r', encoding='utf-8', errors='replace') as fh:
        text = fh.read()
    return {'exists': True, 'text': text,
            'out': open(SELFTEST_OUT, encoding='utf-8', errors='replace').read()
            if os.path.exists(SELFTEST_OUT) else ''}


def summarise(log):
    text = log.get('text', '')
    arms = re.findall(r'SELFTEST (arm=[^\n]*)', text)
    sequence = re.findall(r'(PANEL_SHOWN[^\n]*|PANEL_HIDDEN[^\n]*)', text)
    broke = re.findall(r'SELFTEST (broken=[^\n]*)', text)
    rc = re.findall(r'SELFTEST (rc=-?\d+)', text)
    hk = re.findall(r'HOTKEY_REGISTERED[^\n]*', text)
    focus = re.findall(r'SELFTEST (focus_[^\n]*)', text)
    return {'hotkey': hk[:1], 'arms': arms, 'panels': sequence,
            'broken': broke, 'rc': rc, 'focus': focus,
            'out': log.get('out', '').strip().splitlines()[-1:]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', action='store_true')
    ap.add_argument('--wait', type=float, default=200.0)
    ap.add_argument('--exit-after', type=float, default=45.0)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    if not args.run:
        ap.print_help()
        return 2
    log = launch(exit_after=args.exit_after, wait=args.wait)
    reaped = reap()
    summary = summarise(log)
    summary['reaped'] = reaped
    if args.json:
        print(json.dumps(summary, indent=1, ensure_ascii=False))
        return 0
    print('\n== hotkey ==')
    for line in summary['hotkey'] or ['(no HOTKEY_REGISTERED line)']:
        print(' ', line[:150])
    print('\n== armas do selftest ==')
    for line in summary['arms'] or ['(none)']:
        print(' ', line[:150])
    print('\n== paineis (a sequencia que ele veria) ==')
    for line in summary['panels'] or ['(none)']:
        print(' ', line[:150])
    print('\n== foco ==')
    for line in summary['focus'] or ['(not measured)']:
        print(' ', line[:150])
    print('\n== veredicto do proprio selftest ==')
    for line in summary['broken'] or []:
        print('  BROKEN:', line[:150])
    print('  ', (summary['rc'] or ['(no SELFTEST rc line)'])[0])
    if summary['out']:
        print('  shell:', summary['out'][0])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
