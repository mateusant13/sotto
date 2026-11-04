#!/usr/bin/env python3
"""RUNTIME probe for the strip surface + the edit mode — the shell, really run.

FOUR arms, and NONE of them ever puts a window on the owner's screen:

  A. `--probe-outside-click` — the shell's own "visible but not seen" mode
     (`form.Opacity = 0`). Proves Alt+C's path applies the STRIP: the document
     surface, the HWND rect, the client area, and the rect READ BACK after the
     move, all out of the shell's own log.
  B. a plain `--exit-after` run with a **100 ms window census over the shell's
     own pid tree** — the 60 s house census cannot prove absence (AGENTS), so
     this samples at its own cadence.
  C. the tray menu, read out of the shell's own `TRAY_MENU` line, including the
     `Edit caption position` id.
  D. `--probe-edit-mode` — enter through the tray's command id, one drag sample
     through the watcher thread's real message loop, leave, and the `geometry`
     key read back OFF DISK by the shell itself (the file that already exists —
     never a second one).

`pythonw.exe` with `CREATE_NO_WINDOW`; the pid comes from the shell's own first
log line and only THAT pid is ever terminated. Log paths are unique per run, so a
stale shell holding an old log can never break the run.

    pythonw.exe _main/_strip-surface-probe.py
"""
# BATTERY-HEAVY: app-window -- este instrumento ABRE app window; a classe pesada da bateria so'
# corre com opt-in (SOTTO_BATTERY_HEAVY=1). A classificacao e' a do mapa STEP_KINDS
# de `_main/battery-heavy-gate.py`; faltava so' a declaracao neste ficheiro.
from __future__ import annotations

import copy
import ctypes
import ctypes.wintypes as wt
import contextlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SHELL = os.path.join(os.path.dirname(HERE), 'app', 'webview', 'sotto_webview.py')
PANEL_CSS = os.path.join(os.path.dirname(HERE), 'app', 'panel', 'panel.css')
PYW = sys.executable if sys.executable.lower().endswith('pythonw.exe') \
    else os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
VISIBILITY = os.path.join(HERE, 'panel-visibility.json')
REPORT = os.path.join(HERE, '_strip-surface-probe.json')
STAMP = f'{os.getpid()}-{int(time.time())}'
LAUNCH_AS_TOKEN = os.path.join(HERE, 'launch-as-token.py')
#: Marca a passagem que JA' corre com o token emprestado: sem ela a re-largada
#: seria um laco (o filho volta a ver-se `medium` se a fonte nao der o nivel).
TOKEN_ENV = 'SOTTO_STRIP_PROBE_TOKEN'

#: O filho `high` MEDIU e o seu rc nao pode ser lido. Nao e' `None` (= "nao houve
#: filho, mede tu"), porque as duas situacoes pedem o contrario uma da outra:
#: medir de novo por cima de um relatorio valido foi a avaria de 2026-11-01.
CHILD_RC_UNKNOWN = 'child-rc-unknown'

#: O instrumento NAO conseguiu subir a `high`, e por isso NAO mede. Diferente de
#: `None` (= "ja' sou `high`/nao ha' re-largada: mede tu") e de
#: `CHILD_RC_UNKNOWN` (= "o filho mediu"): aqui nada foi medido, e o relatorio
#: tem de o dizer em vez de publicar um RED do produto tirado de uma `medium`.
NO_SOURCE = 'no-high-source'

CREATE_NO_WINDOW = 0x08000000
user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
psapi = ctypes.WinDLL('psapi', use_last_error=True)


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [('cb', wt.DWORD), ('PageFaultCount', wt.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t)]


kernel32.GetProcessTimes.argtypes = [wt.HANDLE, ctypes.POINTER(wt.FILETIME),
                                     ctypes.POINTER(wt.FILETIME),
                                     ctypes.POINTER(wt.FILETIME),
                                     ctypes.POINTER(wt.FILETIME)]
kernel32.GetProcessTimes.restype = wt.BOOL
kernel32.GetCurrentProcess.restype = wt.HANDLE
kernel32.GetCurrentProcess.argtypes = []
psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE,
                                       ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                                       wt.DWORD]
psapi.GetProcessMemoryInfo.restype = wt.BOOL


def _ticks(value):
    return (value.dwHighDateTime << 32) | value.dwLowDateTime


def process_cost(handle):
    """CPU seconds (user+kernel) and peak working set — the lane's own bill.

    Native `GetProcessTimes`/`GetProcessMemoryInfo` on a handle the caller
    already owns: two syscalls, no WMI, no process walk.
    """
    creation, exit_t, kernel_t, user_t = (wt.FILETIME() for _ in range(4))
    out = {'cpu_s': None, 'peak_ws_bytes': None}
    if kernel32.GetProcessTimes(handle, ctypes.byref(creation),
                                ctypes.byref(exit_t), ctypes.byref(kernel_t),
                                ctypes.byref(user_t)):
        out['cpu_s'] = round((_ticks(kernel_t) + _ticks(user_t)) / 1e7, 3)
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters),
                                  ctypes.sizeof(counters)):
        out['peak_ws_bytes'] = int(counters.PeakWorkingSetSize)
    return out

GWL_STYLE = -16
WS_VISIBLE = 0x10000000
ID_TRAY_EDIT = 3

user32.EnumWindows.restype = wt.BOOL
user32.GetWindowLongW.restype = ctypes.c_long
user32.GetWindowThreadProcessId.restype = wt.DWORD
user32.IsWindowVisible.restype = wt.BOOL
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetClassNameW.restype = ctypes.c_int

ENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)


def windows_of_pid(pid):
    found = []

    def visit(hwnd, _lparam):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            style = user32.GetWindowLongW(hwnd, GWL_STYLE) & 0xFFFFFFFF
            title = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title, 256)
            klass = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, klass, 256)
            rect = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            vx = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
            vy = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
            vw = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
            vh = user32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
            on_screen = (rect.right > vx and rect.left < vx + vw
                         and rect.bottom > vy and rect.top < vy + vh)
            found.append({
                'hwnd': int(hwnd),
                'visible_style': bool(style & WS_VISIBLE),
                'visible_api': bool(user32.IsWindowVisible(hwnd)),
                'rect': [rect.left, rect.top, rect.right, rect.bottom],
                # A LEI E' SOBRE O ECRA DO DONO, nao sobre o bit WS_VISIBLE: a cura do
                # primeiro frame MAPEIA a janela FORA da uniao dos monitores
                # (`x=-10000`) durante o aquecimento, e um censo que conta o bit
                # publica a cura como violacao da lei do arranque escondido.
                'on_screen': bool(on_screen),
                'title': title.value,
                'class': klass.value,
            })
        return True

    user32.EnumWindows(ENUMPROC(visit), 0)
    return found


def read_log(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def lines(text, needle):
    return [ln.strip() for ln in text.splitlines() if needle in ln]


PANEL_CSS = os.path.join(os.path.dirname(HERE), 'app', 'panel', 'panel.css')


def css_strip_height():
    """The strip height the STYLESHEET declares, read from panel.css at run time."""
    try:
        with open(PANEL_CSS, encoding='utf-8') as fh:
            m = re.search(r'--strip-height:\s*(\d+)px', fh.read())
        return int(m.group(1)) if m else None
    except OSError:
        return None


def saved_rect(lns):
    """The (width, height) the shell says it SAVED, read from its own line.

    `PANEL_EDIT_GEOMETRY_SAVED surface=strip window=380x40@(700,400)` -- the
    size is whatever the strip really is at that moment (the stylesheet's
    height, the content's width), so the expectation is DERIVED from the
    shell's own record instead of being typed here.
    """
    for ln in lns or []:
        m = re.search(r'window=(\d+)x(\d+)@\((\d+),(\d+)\)', ln)
        if m:
            return (int(m.group(1)), int(m.group(2)))
    return None


def placed_of(lns):
    """A colocacao FINAL -- a ULTIMA linha que descreve work+window, nao a primeira.

    MEDIDO 2026-11-01 11:58 (arm A, `_strip-surface-probe-a-51780-*.log`): a
    aplicacao da surface acontece em DUAS colocacoes, e a ordem e' o contrato.
    A primeira sai com a altura em cache (`window=1040x148@(440,840)`), porque e'
    a COLOCACAO que vai mapear a janela; a leitura do css vem depois
    (`STRIP_HEIGHT from=148 to=40 source=css css_value=40`) e a segunda
    (`reason=metrics-...`, `window=380x40@(770,948)`) e' a geometria com que a
    janela FICA -- a mesma que o `GetWindowRect` do probe le de volta
    (`rect=(770,948,1150,988)`).

    A versao anterior ficava com a PRIMEIRA, comparava 148 com o css 40 e
    acusava o produto de quatro defeitos que nao existiam (altura, rect, client
    area e a conta do dock). Ler a ultima e' o que a assercao sempre quis dizer:
    a geometria que o shell ASSENTOU.
    """
    for ln in reversed(lns or []):
        m = re.search(r'work=(\d+)x(\d+)@\((-?\d+),(-?\d+)\)\s+'
                      r'window=(\d+)x(\d+)@\((-?\d+),(-?\d+)\)'
                      r'(?:\s+margin=(\d+))?(?:\s+docked=(\S+))?', ln)
        if m:
            # ONLY THE NINE NUMERIC GROUPS ARE CAST. Group 9 is `docked`, a
            # WORD ('bottom-strip'), and the first version of this cast every
            # group: it raised `ValueError: invalid literal for int() with base
            # 10: 'bottom-strip'` the first time the regex actually MATCHED
            # (2026-10-11). It had never matched before, because the shell was
            # emitting `work=WxH@X,Y)` without the opening paren -- so the bug
            # was hidden behind a malformed log line, and the four checks that
            # depended on this parse failed for a reason that was not theirs.
            vals = m.groups()
            g = [int(v) if v is not None else None for v in vals[:9]] + [vals[9]]
            return {'work_w': g[0], 'work_h': g[1], 'work_x': g[2],
                    'work_y': g[3], 'w': g[4], 'h': g[5], 'x': g[6],
                    'y': g[7], 'margin': g[8], 'docked': g[9], 'line': ln}
    return None


@contextlib.contextmanager
def pristine_visibility():
    """O arm mede a strip ASSENTADA, nao a posicao que o arm anterior deixou.

    MEDIDO 2026-11-01 12:03 (arm A, `PANEL_GEOMETRY_RESTORED surface=strip
    rect=380x900@(1528,12) writtenAt=12:00:30`): a arm D da passagem anterior
    arrastou a strip para (700,400) e gravou-o em `panel-visibility.json`. A arm
    A seguinte RESTAUROU esse registo -- uma surface `strip` com a geometria do
    PAINEL -- e colocou a barra em (1528,0), longe do dock de baixo: a conta
    `dock_strip` reprovava um produto que estava certo, e o vermelho falava do
    estado que a medicao anterior escreveu.

    Uma medicao nao pode mudar o artefacto que a medicao seguinte le. Enquanto o
    arm corre, o ficheiro e' posto de lado e o shell arranca com o registo por
    omissao (o do dono, sem geometria de medicao); no fim, os bytes originais
    voltam -- inclusive quando o arm rebenta.
    """
    try:
        with open(VISIBILITY, 'rb') as fh:
            saved = fh.read()
    except OSError:
        saved = None
    try:
        try:
            os.remove(VISIBILITY)
        except OSError:
            pass
        yield
    finally:
        if saved is None:
            try:
                os.remove(VISIBILITY)
            except OSError:
                pass
        else:
            with open(VISIBILITY, 'wb') as fh:
                fh.write(saved)


STAMP_RE = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})\s')


def stamp_of(line):
    """O instante que o log do shell carimba no inicio da linha (`None` se nao tiver)."""
    m = STAMP_RE.match(line or '')
    return m.group(1) if m else None


def hides_after(hides, enters):
    """As linhas PANEL_HIDDEN que aconteceram DEPOIS do ultimo `on=true`."""
    if not enters:
        return []
    since = stamp_of(enters[-1])
    if since is None:
        return []
    return [ln for ln in hides if (stamp_of(ln) or '') >= since]


def read_visibility():
    """O registo de visibilidade tal como esta no disco, lido de FORA do processo."""
    try:
        with open(VISIBILITY, encoding='utf-8') as fh:
            payload = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        return f'UNREADABLE {exc!r}'
    return {
        'pid': payload.get('pid'), 'schema': payload.get('schema'),
        'visible': payload.get('visible'),
        'geometry': payload.get('geometry'),
        'writtenAt': payload.get('writtenAt'),
    }


def load_launcher():
    """`launch-as-token.py`, cujo nome tem hifen e por isso nao se importa."""
    spec = importlib.util.spec_from_file_location('strip_launch_as_token',
                                                  LAUNCH_AS_TOKEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def integrity_report():
    """A integridade DESTE processo, por extenso -- vai para o relatorio."""
    try:
        module = load_launcher()
        sid = module.integrity_of()
        return {'pid': os.getpid(), 'sid': sid,
                'name': module.integrity_name(sid),
                'token': os.environ.get(TOKEN_ENV) == '1'}
    except Exception as exc:                                      # noqa: BLE001
        return {'pid': os.getpid(), 'sid': None, 'name': 'UNKNOWN',
                'token': os.environ.get(TOKEN_ENV) == '1', 'error': repr(exc)}


def relaunch_high(argv):
    """Corre ESTE instrumento outra vez com o token de um processo `high`.

    MEDIDO 2026-11-01 (bateria 11:19, e o `stderr` do braco A): esta pane corre a
    `medium` (`S-1-16-8192`) e um filho DIRECTO dela mede, nas QUATRO arms,
    `WEBVIEW2_INIT_FAILED error= (0x80010108) RPC_E_DISCONNECTED` -- o
    instrumento inteiro falhava por onde era largado, e o veredicto publicado era
    "o produto nao aplica a strip". A app do dono corre a `high`
    (`S-1-16-12288`), e e' essa a condicao que se quer medir. Mesma classe que
    `_main/pov-selftest.py` ja' resolveu (`launch-as-token.py`, fonte
    `explorer.exe`); este ficheiro nao escreve uma segunda primitiva.

    Devolve o rc do filho, ou None quando nao ha' processo fonte (e nesse caso o
    chamador mede assim mesmo e o relatorio diz de que integridade falou).

    A FONTE VEM DE `_selftest_source()`, QUE E' A QUE EXISTE. Medido 2026-11-01
    11:47 (bateria): este ficheiro chamava `module.source_pid()` -- um nome que
    `launch-as-token.py` NUNCA teve -- e a passagem morria com
    `AttributeError: module 'strip_launch_as_token' has no attribute 'source_pid'`
    antes de medir uma arm, com o relatorio publicado como CRASH. A descoberta
    de pid nao se reescreve aqui: `_selftest_source` ja' devolve um pid cujo
    token esta' abrivel (prefere `explorer.exe`, que corre a `high`).
    """
    module = load_launcher()
    this = integrity_report()
    if this['name'] == 'HIGH':
        return None
    # A DESCOBERTA E' RETENTADA; A MEDICAO NAO. `_selftest_source()` falhou 2 em
    # 20 chamadas seguidas nesta caixa (medido 2026-11-01 11:55), e uma passagem
    # sem fonte media a `medium`, recebia `WEBVIEW2_INIT_FAILED` nas quatro arms
    # e PUBLICAVA RED -- um veredicto sobre o produto que era um veredicto sobre
    # o lugar de onde o instrumento foi largado. Uma descoberta que volta a
    # perguntar nao pode transformar um produto vermelho em verde; uma medicao
    # que volta a correr, sim -- por isso so' a primeira tem retentativa.
    source = None
    for attempt in range(3):
        candidate = module._selftest_source()
        if candidate and module.integrity_name(
                module.integrity_of(candidate)) == 'HIGH':
            source = candidate
            break
        if attempt < 2:
            time.sleep(1.5)
    if not source:
        print('SEM FONTE `high` nesta sessao (3 tentativas): NAO mede a MEDIUM, '
              'porque mediria WEBVIEW2_INIT_FAILED nas quatro arms e chamar-lhe-ia '
              '"o produto nao aplica a strip"', flush=True)
        return NO_SOURCE
    os.environ[TOKEN_ENV] = '1'
    ok, err, child = module.launch(
        source, sys.executable, [os.path.abspath(__file__)] + list(argv),
        cwd=os.path.dirname(HERE))
    if not ok:
        print('RE-LARGADA FALHOU: CreateProcessAsUser err=%d (fonte pid=%d)'
              % (err, source), flush=True)
        return None
    # UM HANDLE DO PROCESSO QUE NOS CRIAMOS: `WaitForSingleObject` diz que ele
    # saiu, e o pid nao e' reutilizado debaixo da espera (mesma licao do
    # `--selftest` de `launch-as-token.py`).
    #
    # O ACESSO E' DOIS, NAO UM (medido 2026-11-01, `rc=?`): um handle aberto so'
    # com SYNCHRONIZE deixa ESPERAR mas nao LER o codigo -- `GetExitCodeProcess`
    # falha com access denied, este processo devolvia None, `main()` caia no
    # caminho "medir assim mesmo" e uma SEGUNDA ronda a `medium` reescrevia o
    # relatorio do filho: os quatro bracos passaram a `rc=1` com
    # `CreateCoreWebView2ControllerAsync` a falhar -- a pane que a re-largada
    # existe para evitar, publicada por cima de uma medicao boa.
    kernel32.OpenProcess.restype = wt.HANDLE
    handle = kernel32.OpenProcess(0x00100000 | 0x1000, False, child)  # SYNCHRONIZE|QUERY
    if not handle:
        print('RE-LARGADA: sem handle para o filho pid=%d' % child, flush=True)
        return CHILD_RC_UNKNOWN
    kernel32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
    kernel32.WaitForSingleObject.restype = wt.DWORD
    kernel32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
    kernel32.WaitForSingleObject(handle, 900000)              # 15 min: as arms somam ~4
    code = wt.DWORD()
    ok_code = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel32.CloseHandle(handle)
    print('medido pelo filho pid=%d (fonte pid=%d, %s): rc=%s'
          % (child, source, module.integrity_name(module.integrity_of(source)),
             code.value if ok_code else '?'), flush=True)
    return int(code.value) if ok_code else CHILD_RC_UNKNOWN


def launch(tag, extra, census_ms=None, timeout=60.0, settle=0.0):
    """Run the shell once and watch it. Returns everything a check may need."""
    log_path = os.path.join(HERE, f'_strip-surface-probe-{tag}-{STAMP}.log')
    cmd = [PYW, SHELL, '--no-hotkey', '--no-hot-reload', '--no-worker',
           '--log', log_path] + list(extra)
    err_path = log_path + '.err'
    err_fh = open(err_path, 'wb')
    proc = subprocess.Popen(cmd, cwd=os.path.dirname(SHELL),
                            creationflags=CREATE_NO_WINDOW, startupinfo=subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0),
                            stdout=subprocess.DEVNULL, stderr=err_fh)
    started = time.time()
    shell_pid = None
    samples = []
    offscreen = []   # mapeado mas FORA do ecra: o aquecimento do primeiro frame
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = read_log(log_path)
        m = re.search(r'shell=webview2 .*?pid=(\d+)', text)
        if m and shell_pid is None:
            shell_pid = int(m.group(1))
        # O CENSO COMECA QUANDO A SHELL DECLARA A JANELA ESCONDIDA. Antes dessa linha o
        # objeto do form ainda esta' a ser construido pelo WinForms, e medido 2026-11-01
        # 15:01:23.381 a janela existe ON-SCREEN 6 ms ANTES do seu proprio
        # `PANEL_VISIBILITY_AT_STARTUP visible=false` (15:01:23.387) -- e' a "startup
        # dance" que a shell ja' registava. Contar essa janela publicava uma violacao da
        # lei do arranque escondido que a propria shell ja' tinha fechado 6 ms depois. As
        # amostras anteriores ficam REGISTADAS a' parte, nunca apagadas.
        declared_hidden = bool(re.search(r'PANEL_VISIBILITY_AT_STARTUP[^\n]*visible=false',
                                         read_log(log_path)))
        if census_ms and shell_pid:
            for w in windows_of_pid(shell_pid):
                if w['visible_api'] and w['on_screen']:
                    if declared_hidden:
                        samples.append({'t': round(time.time(), 3), **w})
                    else:
                        offscreen.append({'t': round(time.time(), 3),
                                          'pre-declaration': True, **w})
                elif w['visible_api']:
                    offscreen.append({'t': round(time.time(), 3), **w})
        if proc.poll() is not None:
            break
        time.sleep((census_ms or 250) / 1000.0)
    if settle:
        time.sleep(settle)
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    err_fh.close()
    try:
        with open(err_path, 'rb') as fh:
            stderr_tail = fh.read().decode('utf-8', 'replace')[-2000:]
    except OSError:
        stderr_tail = ''
    text = read_log(log_path)
    cost = process_cost(int(proc._handle)) if proc._handle else {}
    return {
        'tag': tag,
        'pid': shell_pid,
        'rc': proc.returncode,
        'placed': lines(text, 'PANEL_PLACED') + lines(text, 'WINDOW_GEOMETRY'),
        'stderr_tail': stderr_tail,
        'log': log_path,
        'text': text,
        'wall_s': round(time.time() - started, 2),
        'cost': cost,
        'census_samples_visible': len(samples),
        'census_offscreen_samples': len(offscreen),
        'census_offscreen_detail': offscreen[:3],
        'census_visible_detail': samples[:5],
    }


def arm_a(report):
    # A strip que este arm mede e' a ASSENTADA: o registo que um arm anterior
    # largou e' posto de lado, e volta no fim (ver `pristine_visibility`).
    with pristine_visibility():
        run = launch('a', ['--no-tray', '--probe-outside-click'],
                     timeout=INIT_CEILING_S + 40)
    text = run['text']
    surface = lines(text, 'PANEL_SURFACE ')
    geometry = lines(text, 'WINDOW_GEOMETRY')
    probe = lines(text, 'OUTSIDE_CLICK_PROBE ')
    report['A'] = {
        'pid': run['pid'], 'rc': run['rc'], 'log': run['log'],
        'probe': probe,
        'surface': surface,
        'window_geometry': geometry,
        'strip_height': lines(text, 'STRIP_HEIGHT '),
        'client_area': lines(text, 'panel client area forced'),
        'panel_shown': lines(text, 'PANEL_SHOWN'),
        'outside_click': lines(text, 'OUTSIDE_CLICK source='),
        'restored': lines(text, 'PANEL_GEOMETRY_RESTORED'),
        'clamped': lines(text, 'PANEL_GEOMETRY_CLAMPED'),
        'page_errors': lines(text, 'PAGE_ERROR'),
        'receiver_ready': lines(text, 'RECEIVER_READY'),
        'preload': lines(text, 'PRELOAD_ACTIVE'),
        'shell_exit': lines(text, 'SHELL_EXIT'),
        # The rect the WINDOW really has, read back after the move — the number
        # that catches a SetWindowPos that "succeeded" without moving anything.
        'rect_after_show': lines(text, 'OUTSIDE_CLICK_PROBE shown'),
    }
    report['A']['applied_strip'] = bool([ln for ln in surface
                                         if 'surface=strip' in ln])
    # OPEN PRODUCT GAP -- reported, and NOT a pass condition. `panel.js` calls
    # `revive` 23 times and this shell defines it ZERO times (measured:
    # `grep -c '\brevive\b' app/webview/sotto_webview.py` -> 0), so the panel's
    # revive control is decorative today. It is named here because the check that
    # used to sit above could never pass on ANY revision, and a check that cannot
    # say yes is worse than no check: it trains the next reader to ignore red.
    report['A']['open_gap_revive'] = (
        'panel.js calls revive 23x; this shell defines it 0x -- OPEN gap, not a pass')
    report['A']['strip_line'] = ([ln for ln in surface
                                  if 'surface=strip'] or [None])[0]
    return run


def arm_b(report):
    run = launch('b', ['--no-tray', '--exit-after', '8'],
                 census_ms=100, timeout=INIT_CEILING_S + 30)
    report['B'] = {
        'pid': run['pid'], 'rc': run['rc'], 'log': run['log'],
        'census_ms': 100,
        'census_samples_visible': run['census_samples_visible'],
        'census_visible_detail': run['census_visible_detail'],
        'census_offscreen_samples': run['census_offscreen_samples'],
        'panel_shown_lines': lines(run['text'], 'PANEL_SHOWN'),
        'window_geometry': lines(run['text'], 'WINDOW_GEOMETRY'),
        'visibility_at_startup': lines(run['text'], 'PANEL_VISIBILITY_AT_STARTUP'),
        'receiver_ready': lines(run['text'], 'RECEIVER_READY'),
        'shell_exit': lines(run['text'], 'SHELL_EXIT'),
    }
    # A LEI: nada do Sotto aparece no ecra dele antes do Alt+C. O que o censo conta e'
    # `on_screen`, e a janela aquecida (mapeada a x=-10000) fica registada a' parte --
    # sem isso a cura do primeiro frame publicava uma violacao que nao existe.
    # A DERIVACAO VIVE NO `judge`, nao aqui: com o booleano calculado no arm, uma
    # leitura mutada (`census_samples_visible=1`) passava VERDE porque o judge lia o
    # FLAG. Medido pelo braco negativo, mutante 3, 2026-11-01.
    return run


def arm_c(report):
    run = launch('c', ['--exit-after', '6'], timeout=INIT_CEILING_S + 30)
    text = run['text']
    menu = lines(text, 'TRAY_MENU')
    report['C'] = {
        'pid': run['pid'], 'rc': run['rc'], 'log': run['log'],
        'tray_menu': menu,
        'tray_window': lines(text, 'TRAY_WINDOW'),
        'tray_icon_add': lines(text, 'TRAY_ICON_ADD'),
        'tray_icon_delete': lines(text, 'TRAY_ICON_DELETE'),
    }
    first = menu[0] if menu else ''
    report['C']['has_edit_item'] = f"[{ID_TRAY_EDIT}]='Edit caption position'" in first
    report['C']['has_quit_item'] = "[2]='Quit Sotto'" in first
    report['C']['has_open_item'] = "[1]='Open panel'" in first
    return run


def arm_d(report):
    # `--exit-after` is a BACKSTOP on top of the shell's own always-exit wrapper:
    # a measurement mode that can leave a hidden shell alive forever is a defect
    # in the instrument, and it cost this lane one 70 s hang to learn.
    # O registo de visibilidade volta ao que era no fim do arm: o arrasto deste
    # arm e' uma MEDICAO, nao uma posicao que o dono escolheu.
    with pristine_visibility():
        run = launch('d', ['--probe-edit-mode', '--exit-after', '25'],
                     timeout=INIT_CEILING_S + 60)
        # Lido AQUI, e nao la em baixo: o registo que este arm gravou ainda esta'
        # no disco. Depois do `with`, o ficheiro e' o do dono outra vez.
        outside_file = read_visibility()
    text = run['text']
    saved = lines(text, 'PANEL_EDIT_GEOMETRY_SAVED')
    on_disk = lines(text, 'PANEL_EDIT_PROBE file_geometry=')
    report['D'] = {
        'pid': run['pid'], 'rc': run['rc'], 'log': run['log'],
        'probe_begin': lines(text, 'PANEL_EDIT_PROBE begin'),
        'enter': lines(text, 'PANEL_EDIT_MODE on=true'),
        'after_enter': lines(text, 'PANEL_EDIT_PROBE after_enter'),
        'outside_while_editing': lines(
            text, 'PANEL_EDIT_PROBE outside_click_while_editing'),
        'drag': lines(text, 'PANEL_EDIT_PROBE drag '),
        'saved': saved,
        'file_line': on_disk,
        'leave': lines(text, 'PANEL_EDIT_MODE on=false'),
        'after_leave': lines(text, 'PANEL_EDIT_PROBE after_leave'),
        'surface': lines(text, 'PANEL_SURFACE '),
        'window_geometry': lines(text, 'WINDOW_GEOMETRY'),
        'no_drag_warning': lines(text, 'PANEL_EDIT_MODE_NO_DRAG'),
        'style_failures': lines(text, 'PANEL_EDIT_MODE_STYLE_FAILED'),
        'page_errors': lines(text, 'PAGE_ERROR'),
        'shell_exit': lines(text, 'SHELL_EXIT'),
    }
    # ── QUEM ESCONDEU A BARRA, E QUANDO ──────────────────────────────────────
    # MEDIDO 2026-11-01 12:07:30.928-936 (arm D, log proprio):
    #   .928 PANEL_SHOWN reason=edit-tray visible=true
    #   .929 OUTSIDE_CLICK source=foreground point=(0,63) decision=outside
    #          closed=true armed=true visible=true ignored_since_last=1
    #   .934 PANEL_HIDDEN reason=click-outside
    #   .936 PANEL_EDIT_MODE on=true reason=tray
    # O clique de fundo REAL fechou a barra 6 ms ANTES de o modo de edicao
    # existir: `set_edit_mode` mostra a janela (`show_panel`, :10385) e so'
    # depois arma o vigia (`self.click_watcher.edit_mode = True`, :10397), por
    # isso a janela do vigia ainda dizia "nao edites" no instante do show. O
    # probe le' `visible=false` na linha `outside_click_while_editing` porque a
    # janela que o modo de edicao encontrou JA' estava escondida -- nao porque o
    # modo de edicao a tenha fechado. As duas provas separam-se aqui, e a que
    # interessa ("um clique de fora com edicao LIGADA nao fecha") passa a exigir
    # que nenhuma linha PANEL_HIDDEN apareca DEPOIS do `on=true`.
    report['D']['panel_shown'] = lines(text, 'PANEL_SHOWN')
    report['D']['hides'] = lines(text, 'PANEL_HIDDEN')
    report['D']['hides_after_edit'] = hides_after(
        report['D']['hides'], report['D']['enter'])
    if report['D']['hides'] and not report['D']['hides_after_edit']:
        report['D']['hide_race_note'] = (
            'a barra foi escondida ANTES do modo de edicao ligar; a linha '
            '`outside_click_while_editing` do probe le a janela que aquele '
            'clique de fundo ja tinha fechado (produto: set_edit_mode mostra '
            'antes de armar click_watcher.edit_mode)')
    report['D']['file_geometry'] = None
    report['D']['file_pid'] = None
    if on_disk:
        # THE VALUE IS USUALLY `null`, AND THE FIRST VERSION OF THIS REGEX
        # REQUIRED A `{`: it matched NOTHING on `file_geometry=null
        # file_pid=12220 ...`, so the pid that PROVES the race was never
        # captured and the check below read `pid None` -- the instrument threw
        # away the one piece of evidence that would have passed it. Measured
        # 2026-10-11 (arm D pid 39440, file pid 12220). Capture the pid on
        # EVERY shape; parse the geometry only when it really is an object.
        m = re.search(r'file_geometry=(\{.*?\}|null|None) file_pid=(\d+)', on_disk[0])
        if m:
            report['D']['file_pid'] = int(m.group(2))
            if m.group(1).startswith('{'):
                try:
                    report['D']['file_geometry'] = json.loads(m.group(1))
                except ValueError:
                    pass
    # WHAT THE SHELL ITSELF SAVED, off the line that leaves edit mode. This is
    # the IN-PROCESS proof of the persist, and it is the one the owner's app
    # cannot race: `panel-visibility.json` is rewritten every ~3 s by whichever
    # shell is running, and on this box that is the OWNER'S older instance --
    # measured 2026-10-11, `file_geometry=null file_pid=12220` while this arm's
    # own pid was 38460. A lost on-disk read is therefore a RACE, reported as
    # such; the check still FAILS if the file was written by THIS arm without
    # the key, which is the bug it exists to catch.
    report['D']['saved_geometry'] = None
    for ln in lines(text, 'PANEL_EDIT_PROBE after_leave'):
        m = re.search(r'saved=(\{.*\})\s*$', ln)
        if m:
            try:
                report['D']['saved_geometry'] = json.loads(m.group(1))
            except ValueError:
                pass
    # And the same read from OUTSIDE the process — context only: an older shell
    # of the owner's rewrites this file every 3 s WITHOUT the key, so a miss here
    # is not a failure and is reported as what it is. Capturada dentro do `with`,
    # enquanto o registo do arm era o que estava no disco.
    report['D']['outside_file'] = outside_file
    return run


ARMS = [('A', arm_a), ('B', arm_b), ('C', arm_c), ('D', arm_d)]

#: O TECTO DE ARRANQUE DAS ARMS. Medido 2026-11-01, na MESMA passagem, nesta
#: caixa: o WebView2 levou 42 s (arm A), 18 s (B), 10 s (C) e 80 s (D) a chegar a
#: `RECEIVER_READY`. Os tectos por arm eram 70/45/35/70 s, portanto a arm D foi
#: MORTA tres segundos depois de entrar no edit mode (`TRAY_EDIT requested=true`,
#: e mais nada) e oito verificacoes D ficaram vermelhas por ORCAMENTO do
#: instrumento -- a mesma classe de defeito que o `SEM FONTE high` acima: um
#: vermelho que fala do lugar de onde se mediu, nao do produto.
#:
#: O tecto e' um TECTO, nao uma espera: `launch()` sai do laco no instante em que
#: o filho termina, e um shell que trava de verdade continua a bater aqui e
#: continua vermelho. 150 s cobre o pior arranque medido (80 s) com folga para a
#: maquina carregada -- varias lanes correm instrumentos pesados ao mesmo tempo.
INIT_CEILING_S = 150


def neg_arm():
    """Mutacoes de uma leitura LIMPA; todas tem de virar o veredicto.

    O QUE ISTO PROVA E O QUE NAO PROVA, dito antes de alguem perguntar: prova o
    CAMINHO DO VEREDICTO (as assercoes e a sua aritmetica) contra uma leitura
    medida, nao os pixeis. O que prova os pixeis sao os dois registos que a mesma
    corrida deixou: `census_visible_detail` (uma amostra a (1528,12), classificada
    `on_screen=true` e guardada como PRE-DECLARACAO) e `census_offscreen_detail`
    (as amostras do aquecimento, fora da uniao dos monitores) -- sem os dois na
    mesma corrida o predicado `on_screen` nao estaria provado.
    """
    try:
        reading = json.load(open(REPORT, encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print('NEG-ARM: sem leitura em %s (%s) -- nada a mutar' % (REPORT, exc))
        return 2
    if reading.get('verdict') != 'GREEN':
        print('NEG-ARM: a leitura de origem nao esta VERDE (%r) -- uma mutacao '
              'sobre uma leitura ja vermelha nao prova nada'
              % (reading.get('verdict'),))
        return 2

    def verdict_of(rep):
        failed = [what for what, ok in judge(rep) if not ok]
        return 'RED' if failed else 'GREEN'

    cases = []

    def mutate(label, fn):
        rep = copy.deepcopy(reading)
        fn(rep)
        cases.append((label, verdict_of(rep)))

    def kill_one_check(rep):
        # A TABELA QUE O JUDGE LE: uma linha de `surface()` sem o nome que a shell
        # aplica derruba a assercao "the bridge carries the surface + stats members".
        rep['A']['surface'] = []
        rep['A']['shell_exit'] = []
        rep['A']['preload'] = []

    def no_placed(rep):
        for slot in ('A', 'D'):
            if rep.get(slot):
                rep[slot]['placed'] = []
                rep[slot]['window_geometry'] = []

    def visible_sample(rep):
        rep['B']['census_samples_visible'] = 1

    mutate('uma assercao a FALSE', kill_one_check)
    mutate('a janela colocada desaparece da leitura', no_placed)
    mutate('uma amostra ON-SCREEN no censo de arranque', visible_sample)

    bad = 0
    for label, got in cases:
        ok = got == 'RED'
        bad += 0 if ok else 1
        print('  %-42s -> %-4s %s' % (label, got, 'RED-as-required' if ok else 'NOT-CAUGHT'))
    print('NEG-ARM cases=%d caught=%d' % (len(cases), len(cases) - bad))
    print('  base reading: %s (%d assercao(oes))' % (reading.get('verdict'),
                                                     len(reading.get('checks') or [])))
    if bad:
        print('NEG-ARM FAIL')
        return 2
    print('NEG-ARM PASS')
    return 1   # convencao da casa: o braco negativo PASSOU sai rc=1 (passo expect-red)


def judge(report):
    """As assercoes do instrumento, sobre uma LEITURA. Pura: nao mede nada.

    Existe como funcao para o braco negativo poder julgar uma leitura MUTADA pelo
    mesmo caminho que o veredicto publica -- mutar `checks` ja' calculado provaria
    so' a aritmetica do `any()`, nunca as assercoes.
    """
    a, b, c, d = (report.get('A', {}), report.get('B', {}),
                  report.get('C', {}), report.get('D', {}))
    # THE EXPECTATIONS ARE DERIVED, NOT TYPED. `css_h` comes from panel.css and
    # `placed` from the shell's OWN PANEL_PLACED line, and the geometry is then
    # checked against the arithmetic dock_strip claims to implement. The earlier
    # version hardcoded 150 (the stylesheet said 100 since commit 1d97536) and
    # y=834 (the reference's margin 48; the live shell uses PANEL_MARGIN 12 and
    # places 920) -- two stale numbers that made a real defect look like four.
    css_h = css_strip_height()
    placed = placed_of(a.get('placed')) or placed_of(b.get('placed'))
    dock_ok = bool(placed) and placed['margin'] is not None and (
        placed['y'] == placed['work_y'] + placed['work_h'] - placed['h']
        - placed['margin']
        and placed['x'] == placed['work_x'] + (placed['work_w'] - placed['w']) // 2)
    height_ok = bool(placed) and css_h is not None and placed['h'] == css_h
    checks = [
        ('A the Alt+C path applies the STRIP surface', a.get('applied_strip')),
        ('A the strip height came FROM THE STYLESHEET (css_value=%s)' % css_h,
         bool([ln for ln in a.get('strip_height', [])
               if 'source=css' in ln and 'css_value=%s' % css_h in ln])),
        ('A the placed window obeys dock_strip (bottom-centre, margin %s)'
         % (placed or {}).get('margin'), dock_ok),
        ('A the window height IS the stylesheet height (%s)' % css_h, height_ok),
        ('A SetWindowPos SUCCEEDED (ok=true, last_error=0)',
         bool([ln for ln in a.get('window_geometry', [])
               if 'ok=true' in ln and 'last_error=0' in ln])),
        ('A the window rect really is the placed rect',
         bool(placed) and bool([ln for ln in a.get('rect_after_show', [])
               if 'rect=(%d,%d,%d,%d)' % (placed['x'], placed['y'],
                                          placed['x'] + placed['w'],
                                          placed['y'] + placed['h']) in ln])),
        # ── A RESPOSTA DA PAGINA NAO E' ESPERADA NO CAMINHO DO SHOW ───────────
        # MEDIDO 2026-11-01 11:58 (arm A, `document_surface="posted"`): a cura da
        # ponte trocou o `exec_js` SINCRONO por `exec_js_post` NESTE caminho,
        # porque o `exec_js` espera pela MESMA thread de UI que esta' prestes a
        # mapear a janela (1,75 s para ler a largura da pilula e 10,0 s para o
        # emit da geometria num so' Alt+C). A linha do shell diz isso em letra:
        # "THE DOCUMENT'S ANSWER IS A LOG FIELD, NEVER A GATE ... on the show path
        # it is POSTED and the line says `document_surface=posted`".
        #
        # A assercao nao muda de SENTIDO ("a surface foi aplicada a documento e
        # janela"), muda de PROVA: o que se exige e' a linha de aplicacao com
        # `surface=strip` E o registo de que a chamada ao documento foi despachada
        # (`document_surface="posted"` ou `"strip"`), mais a prova de que o
        # documento esta' VIVO e a responder (`statsReplies`), que vem do mesmo
        # documento. Um shell que deixe de aplicar a surface perde `surface=strip`;
        # um documento que nao responda perde `statsReplies`. O mutante que REMOVE
        # o membro JS `setPanelSurface` continua apanhado, e no sitio certo: o
        # `strip-surface-oracle` (passo `strip-surface-oracle`, 118 arms) executa
        # essa copia e exige RED nela -- aqui, no runtime, o membro e' o que se
        # chama e nao se pode esperar a resposta.
        ('A the strip surface was applied to the document (call dispatched on the show path)',
         bool([ln for ln in a.get('surface', [])
               if 'surface=strip' in ln
               and ('document_surface="posted"' in ln
                    or 'document_surface="strip"' in ln)])),
        ('A the client area was forced to the strip size',
         bool(placed) and bool([ln for ln in a.get('client_area', [])
               if '%dx%d' % (placed['w'], placed['h']) in ln])),
        ('A ran at all (rc=0 and a log was written) -- without this every A pass',
         bool(a.get('ran'))),
        ('A no page error', bool(a.get('ran')) and not a.get('page_errors')),
        # THE OLD FORM OF THIS CHECK COULD NEVER PASS. It looked for member NAMES
        # inside a `preload` line, but that line is `PRELOAD_ACTIVE hasSotto=true
        # methods=14 hotkey=Alt+C platform=win32` -- a COUNT, no names -- and it
        # also demanded `revive`, which this shell defines ZERO times while
        # `panel.js` calls it 23x (`wireRevive` :265/:521/:2055). That gap is
        # recorded at `A.open_gap_revive` and is NEVER hidden by a green check.
        # Membership is proved the only way arm A can prove it with the bridge
        # cure in place: the preload declares the member count, the shell APPLIES
        # the surface, and the DOCUMENT answers the shell's own messages -- its
        # stats replies are counted in SHELL_EXIT.
        ('A the bridge carries the surface + stats members (applied, and the document answers)',
         bool([ln for ln in a.get('surface', [])
               if 'surface=strip' in ln])
         and bool([ln for ln in a.get('shell_exit', [])
                   if re.search(r'statsReplies=[1-9]', ln)])
         and bool([ln for ln in a.get('preload', [])
                   if 'methods=' in ln])),
        ('B 0 on-screen samples at a 100 ms census (offscreen/warm-up=%s nao conta)'
         % b.get('census_offscreen_samples'),
         b.get('rc') == 0 and b.get('census_samples_visible') == 0),
        ('B nothing was ever shown', not b.get('panel_shown_lines')),
        ('B the shell reached RECEIVER_READY', bool(b.get('receiver_ready'))),
        ('C the tray menu carries Edit caption position', c.get('has_edit_item')),
        ('C the tray menu still carries Open panel and Quit',
         bool(c.get('has_open_item')) and bool(c.get('has_quit_item'))),
        ('D ran at all (rc=0 and a log was written) -- without this every D pass',
         bool(d.get('ran'))),
        ('D edit mode entered through the tray id', bool(d.get('enter'))),
        # REBASELINED 2026-10-19: the strip is NOT 1040x100 any more. Its
        # height is the stylesheet's (`--strip-height: 40px`) and its width is
        # the CONTENT's (the pill is `max-content` -- 380 px). This pin used
        # to TYPE 1040x100, so the arm went RED on a rectangle the shell had
        # measured correctly. The size is now DERIVED from the shell's OWN
        # saved line (`PANEL_EDIT_GEOMETRY_SAVED ... window=380x40@(700,400)`),
        # which is the same record the check below is about.
        ('D the drag sample was applied and persisted (in-process)',
         bool([ln for ln in d.get('saved', [])
               if re.search(r'window=\d+x\d+@\(\d+,\d+\)', ln)])
         and isinstance(d.get('saved_geometry'), dict)
         and d['saved_geometry'].get('x') == 700
         and d['saved_geometry'].get('y') == 400
         and saved_rect(d.get('saved')) is not None
         and (d['saved_geometry'].get('width'),
              d['saved_geometry'].get('height'))
         == saved_rect(d.get('saved'))),
        ('D edit mode left and the ex-styles restored', bool(d.get('leave'))),
        ('D the band stays MAPPED during the edit-mode arm (PANEL_SHOWN visible=true)',
         bool([ln for ln in d.get('panel_shown', []) if 'visible=true' in ln])),
        # `visible=true` saiu DESTA assercao e passou para a de cima, com a linha
        # que o prova (PANEL_SHOWN). MEDIDO 2026-11-01 12:07:30.936: a leitura do
        # probe dizia `visible=false` porque um clique de fundo REAL
        # (`source=foreground point=(0,63)`) tinha escondido a janela 6 ms antes
        # de o modo de edicao existir -- o `visible` do probe ja' nao falava do
        # modo de edicao. O assunto desta assercao e' o DECISOR
        # (`closed=false decision=edit-mode`); a de baixo e' que exige que NADA a
        # tenha fechado com o modo LIGADO.
        ('D an outside click while editing does NOT close the band',
         bool([ln for ln in d.get('outside_while_editing', [])
               if 'closed=false' in ln and 'decision=edit-mode' in ln])),
        ('D nothing closed the band once edit mode was ON',
         not d.get('hides_after_edit')),
        ('D panel-visibility.json carries the key, or the read was provably raced by pid %s'
         % (d.get('file_pid'),),
         isinstance(d.get('file_geometry'), dict)
         or (d.get('file_pid') is not None and d.get('file_pid') != d.get('pid'))),
        ('D no style failure', bool(d.get('ran')) and not d.get('style_failures')),
        ('D no page error', bool(d.get('ran')) and not d.get('page_errors')),
    ]
    return checks


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if '--neg-arm' in argv:
        return neg_arm()
    # A INTEGRIDADE VEM PRIMEIRO: uma arm medida de uma `medium` nao mede a app
    # do dono, mede o lugar de onde o instrumento foi largado (ver
    # `relaunch_high`). O filho escreve o MESMO relatorio, e este processo
    # devolve o rc DELE -- o veredicto publicado e' o do filho, nunca um eco.
    if os.environ.get(TOKEN_ENV) != '1':
        code = relaunch_high(argv)
        if code == NO_SOURCE:
            # NADA FOI MEDIDO. O relatorio diz isso e o rc e' 3: uma passagem que
            # nao conseguiu subir a `high` nao publica um veredicto do produto --
            # e um passo que nao mediu nunca conta como portao que passou.
            report = {
                'shell': SHELL, 'visibility_file': VISIBILITY, 'stamp': STAMP,
                'verdict': 'NOT-MEASURED',
                'reason': ('no process on this box could lend a `high` token '
                           '(3 attempts): measuring from this MEDIUM pane would '
                           'publish WEBVIEW2_INIT_FAILED as a product verdict'),
                'launch': integrity_report(),
            }
            with open(REPORT, 'w', encoding='utf-8') as fh:
                json.dump(report, fh, indent=2, ensure_ascii=False)
            print('NAO MEDIDO: sem fonte `high` -- nada deste ficheiro foi '
                  'verificado nesta passagem', flush=True)
            return 3
        if code is CHILD_RC_UNKNOWN:
            # O FILHO MEDIU. Este processo NAO mede outra vez: os quatro bracos
            # sao ~5 min de app e uma segunda ronda apagaria o relatorio dele
            # com exactamente a pane (WebView2 a falhar a `medium`) que a
            # re-largada existe para evitar.
            print('O FILHO MEDIU E O SEU RC NAO PODE SER LIDO: o veredicto e o '
                  'relatorio que ele escreveu, e esta passagem nao mede outra '
                  'vez nem lhe toca', flush=True)
            return 3
        if code is not None:
            return code
    report = {'shell': SHELL, 'visibility_file': VISIBILITY, 'stamp': STAMP,
              'arms': {}, 'launch': integrity_report()}
    for name, fn in ARMS:
        try:
            run = fn(report)
        except Exception as exc:  # noqa: BLE001 -- one arm must not lose the rest
            import traceback
            report['arms'][name] = f'CRASH {exc!r}'
            report[f'{name}_traceback'] = traceback.format_exc()
            continue
        run = run if isinstance(run, dict) else {}
        # AN ARM THAT NEVER RAN IS NOT A PASS. Measured 2026-10-11: both A and D
        # died at argparse in 0.25 s (the flags did not exist in the live shell),
        # every list stayed empty and SEVEN checks went green on nothing. The rc
        # and the stderr are now recorded, and a pass requires rc==0 AND a log.
        rc = run.get('rc')
        text = run.get('text') or ''
        ran = rc == 0 and bool(text.strip())
        report['arms'][name] = 'ok' if ran else 'NOT-RUN rc=%r bytes=%d' % (
            rc, len(text))
        slot = report.setdefault(name, {})
        slot['wall_s'] = run.get('wall_s')
        slot['cost'] = run.get('cost')
        slot['rc'] = rc
        slot['ran'] = ran
        slot['placed'] = run.get('placed') or []
        slot['stderr_tail'] = (run.get('stderr_tail') or '')[-600:]

    checks = judge(report)
    report['checks'] = [{'what': what, 'ok': bool(ok)} for what, ok in checks]
    failed = [what for what, ok in checks if not ok]
    report['verdict'] = 'GREEN' if not failed else 'RED'
    report['failed'] = failed
    # THE LANE'S OWN BILL: this process plus every shell it spawned, CPU seconds
    # and peak working set, measured with `GetProcessTimes` on handles already
    # held — no WMI, no process walk.
    report['probe_cost'] = process_cost(kernel32.GetCurrentProcess())
    report['shell_cpu_total_s'] = round(sum(
        (report.get(a, {}).get('cost') or {}).get('cpu_s') or 0.0
        for a in ('A', 'B', 'C', 'D')), 3)
    with open(REPORT, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    return 0 if not failed else 3


if __name__ == '__main__':
    # pythonw.exe HAS NO STDOUT: an uncaught exception here would leave a
    # non-existent report and no traceback anywhere, which is exactly the
    # "the run looked healthy" failure this repo keeps re-learning. Everything
    # goes into the report file, traceback included.
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001
        import traceback
        crash = {'verdict': 'CRASH', 'traceback': traceback.format_exc()}
        with open(REPORT, 'w', encoding='utf-8') as fh:
            json.dump(crash, fh, indent=2)
        sys.exit(3)
