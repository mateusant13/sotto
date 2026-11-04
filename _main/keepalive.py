import os, subprocess, sys, time

# LANE KEEPALIVE -- mantem a accao da tarefa VIVA enquanto a app existir, para o
# job object nao fechar e nao suspender a app (medido 2026-10-23: 34/34 threads
# Suspended quando a accao terminava).
#
# REGRA (AGENTS.md, marcador SOTTO_NEVER_ON_OWNER_SCREEN): nunca `--show`.
# O painel nasce com o Alt+C do dono, ou com a palavra dele NA SESSAO. Este
# harness arranca a app ESCONDIDA, que e o estado em que ela escreve o
# `panel-state.json` e o log -- e e por esses dois ficheiros que uma lane mede.
#
# Opt-in: sem SOTTO_LANE_LAUNCH=1 este ficheiro nao faz nada.

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lane-launch.log')


def w(msg):
    try:
        with open(LOG, 'a', encoding='utf-8') as fh:
            fh.write('%s %s\n' % (time.strftime('%H:%M:%S'), msg))
    except OSError:
        pass


if os.environ.get('SOTTO_LANE_LAUNCH') != '1':
    w('recusado: SOTTO_LANE_LAUNCH != 1 (ver AGENTS.md, SOTTO_NEVER_ON_OWNER_SCREEN)')
    sys.exit(0)

w('keepalive start pid=%d' % os.getpid())
# CREATE_NO_WINDOW (0x08000000): sem ele o `cmd.exe` filho ALOCA uma consola e o
# dono ve a janela. Ordem dele, 2026-11-02: nada em foreground. Portao:
# `_main/console-window-gate.py`.
subprocess.Popen(['cmd.exe', '/c', 'Sotto.cmd'], cwd=r'H:\sotto',
                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                 stderr=subprocess.DEVNULL, close_fds=True,
                 creationflags=0x08000000, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0))
w('Sotto.cmd lancado sem a bandeira de mostrar; a manter a tarefa viva enquanto a app existir')

try:
    import psutil
except Exception as exc:
    w('sem psutil (%r) -- a dormir 600 s' % (exc,))
    time.sleep(600)
    raise SystemExit(0)

seen = False
deadline = time.time() + 3600
while time.time() < deadline:
    alive = False
    for proc in psutil.process_iter(['cmdline']):
        try:
            if 'sotto_webview.py' in ' '.join(proc.info['cmdline'] or []):
                alive = True
                break
        except Exception:
            continue
    if alive:
        seen = True
    elif seen:
        w('a app morreu -- keepalive sai')
        break
    time.sleep(5)
w('keepalive fim')
