#!/usr/bin/env python3
"""Can THIS box register Alt+C right now — and which accelerators are free?

WHY: Alt+C is the app's ONLY control. `HotkeyThread.run` calls
`RegisterHotKey(NULL, id, MOD_ALT | MOD_NOREPEAT, 'C')` and, when that fails,
logs `HOTKEY_REGISTER_FAILED` and RETURNS — so the app is running, hidden, and
answers nothing. The owner sees a dead app with no message, because the whole
design is "nothing appears on screen until you ask". "Alt+C does nothing" is
therefore most likely this single call failing against a hotkey another program
already owns, and that is measurable in milliseconds.

WHAT IT DOES: for each candidate accelerator, register it on this thread exactly
the way the shell does (`hWnd=NULL`, `MOD_NOREPEAT`), record the result and
`GetLastError`, then UNREGISTER IMMEDIATELY. Nothing is left registered, no window
is created, no audio device is opened, and the whole run is a few hundred ms — the
only side effect is that the key is grabbed for microseconds at a time.

    cmd /c "python _main\\_audit-hotkey-probe.py > _main\\_audit-probe\\hotkey.log 2>&1"

Exit 0 always: this is a measurement. Read the table.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import importlib.util
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, '_audit-probe', 'hotkey.log')

user32 = ctypes.WinDLL('user32', use_last_error=True)

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
_HOTKEY_ID = 0x534F  # 'SO' — the shell's own id

#: `(label, modifiers, virtual-key)` — the shipped one first, then the fallbacks
#: a fix could take. Alt+Shift+<key> and Ctrl+Alt+<key> are the conventional
#: choices precisely because vendors grab the plain ones.
CANDIDATES = (
    ('Alt+C (SHIPPED)', MOD_ALT, ord('C')),
    ('Alt+Shift+C', MOD_ALT | MOD_SHIFT, ord('C')),
    ('Ctrl+Alt+C', MOD_CONTROL | MOD_ALT, ord('C')),
    ('Ctrl+Shift+C', MOD_CONTROL | MOD_SHIFT, ord('C')),
    ('Alt+S', MOD_ALT, ord('S')),
    ('Alt+Shift+S', MOD_ALT | MOD_SHIFT, ord('S')),
    ('Ctrl+Alt+S', MOD_CONTROL | MOD_ALT, ord('S')),
    ('Alt+F9', MOD_ALT, 0x78),
    ('Alt+Shift+F9', MOD_ALT | MOD_SHIFT, 0x78),
    ('Ctrl+Alt+L', MOD_CONTROL | MOD_ALT, ord('L')),
)

ERROR_ALREADY_REGISTERED = 1409

lines: list[str] = []


def say(msg: str) -> None:
    lines.append(msg)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(msg, flush=True)


def describe(err: int) -> str:
    if err == 0:
        return 'ok'
    if err == ERROR_ALREADY_REGISTERED:
        return 'ALREADY REGISTERED by another program (1409)'
    if err == 5:
        return 'ACCESS DENIED (5) — a lower-integrity or higher-integrity holder'
    if err == 1400:
        return 'INVALID WINDOW HANDLE (1400) — hWnd is not NULL here'
    return f'error {err}'


#: O acelerador que a app transporta. A pergunta deste instrumento e' sobre ELE.
SHIPPED_ACCEL = 'Alt+C'
SELECTOR = os.path.join(HERE, 'load-shedding-oracle.py')


def selector():
    """O escolhedor da instancia VIVA -- UM so' nesta casa, e nao um segundo.

    Vive em `_main/load-shedding-oracle.py` e o nome que ele EXPORTA e'
    `newest_shell_segment(log_path)`: recusa marcadores de medicao, largadas que
    perderam a mutex (`already_running=true`) e pids mortos, e diz no stdout qual
    escolheu. MEDIDO 2026-11-01 11:47: este ficheiro chamava
    `selector().find_live_instance()`, que NUNCA existiu la' --
    `AttributeError: module '...load-shedding-oracle.py' has no attribute
    'find_live_instance'`, e o passo `hotkey-registration` da bateria crashava
    em vez de medir. A regra nao se reescreve aqui: `live_instance()` aplica a
    unica que existe aos logs candidatos.
    """
    if SELECTOR in sys.modules:
        return sys.modules[SELECTOR]
    spec = importlib.util.spec_from_file_location(SELECTOR, SELECTOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[SELECTOR] = module
    spec.loader.exec_module(module)
    return module


def candidate_logs():
    """Os logs onde a instancia do DONO pode estar -- o desta arvore e o do repo principal.

    MEDIDO 2026-11-01 11:47 nesta worktree: o `_main/webview-run.log` dela nao tem
    UMA unica largada, e a instancia viva (pid 55448, `HOTKEY_REGISTERED role=panels
    accelerator=Alt+C register=true` as 11:47:41) so' aparece no log de `H:/sotto`,
    de onde a app arranca. Um escolhedor que so' olha o log da arvore em que corre
    responde "nenhuma instancia viva" numa caixa onde a app esta' a trabalhar.
    """
    root = str(selector().ROOT)
    logs = [os.path.join(root, '_main', 'webview-run.log')]
    try:
        common = subprocess.run(
            ['git', '-C', root, 'rev-parse', '--git-common-dir'],
            capture_output=True, text=True)
        if common.returncode == 0 and common.stdout.strip():
            gitdir = os.path.abspath(os.path.join(root, common.stdout.strip()))
            main_log = os.path.join(os.path.dirname(gitdir), '_main',
                                    'webview-run.log')
            if main_log not in logs:
                logs.append(main_log)
    except OSError:
        pass
    return logs


def live_instance():
    """`(log, pid, segmento)` da instancia viva, ou `(None, None, '')`.

    QUEM DECIDE E' `newest_shell_segment`, sem uma segunda regra: isto so' lhe
    entrega os ficheiros candidatos, na ordem em que a app pode estar neles.
    """
    for log in candidate_logs():
        pid, seg = selector().newest_shell_segment(log)
        if pid is not None:
            return log, pid, seg
    return None, None, ''


def live_sotto():
    """`(pid, sha, segmento)` da instancia VIVA, ou `(None, None, '')`.

    A VERSAO ANTERIOR lia o ficheiro INTEIRO linha a linha e ficava com o ULTIMO
    `SHELL_STARTUP_STAGE pid=` e o ULTIMO `SHELL_CODE_ID` -- que podem ser de
    largadas DIFERENTES, e tipicamente sao de uma medicao. Medido 2026-11-01 11:16
    (bateria): com a app do dono viva e a deter o Alt+C, a sonda escolheu o pid
    40064 de uma largada de medicao que ja' nao existia e acusou a app de nao ter
    registado a tecla. O pid, o codigo e o segmento passam a vir da MESMA largada.
    """
    log, pid, seg = live_instance()
    if pid is None:
        return None, None, ''
    pid = int(pid)
    sha = None
    for line in seg.splitlines():
        if 'SHELL_CODE_ID' in line and 'sha256=' in line:
            for token in line.split():
                if token.startswith('sha256='):
                    sha = token[7:]
            break
    print(f'  instancia viva: log={log} pid={pid} sha={sha}')
    return pid, sha, seg


def last_registration(segment):
    """A ultima linha de hotkey DESTA instancia (o segmento dela, nao o ficheiro).

    E a linha do acelerador que a app transporta -- nao "a ultima linha de hotkey
    do ficheiro", que era `role=live accelerator=Ctrl+Space` e por isso respondia
    `Alt+C` ausente com o Alt+C registado quatro linhas acima.
    """
    last = None
    for line in segment.splitlines():
        if ('HOTKEY_REGISTERED' in line or 'HOTKEY_REGISTER_FAILED' in line) \
                and f'accelerator={SHIPPED_ACCEL}' in line:
            last = line.rstrip()
    return last



def main() -> int:
    # The shell forces a message queue into existence before registering
    # (`PeekMessageW` on a thread that has never pumped is refused), so this probe
    # does the same or it would measure a different call.
    class MSG(ctypes.Structure):
        _fields_ = [('hwnd', wt.HWND), ('message', wt.UINT),
                    ('wParam', wt.WPARAM), ('lParam', wt.LPARAM),
                    ('time', wt.DWORD), ('pt_x', wt.LONG), ('pt_y', wt.LONG)]

    msg = MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)

    say('accelerator             register  GetLastError / meaning')
    say('----------------------  --------  -----------------------------')
    results = {}
    for label, mods, vk in CANDIDATES:
        ctypes.set_last_error(0)
        ok = bool(user32.RegisterHotKey(None, _HOTKEY_ID, mods | MOD_NOREPEAT, vk))
        err = ctypes.get_last_error()
        results[label] = ok
        say(f'{label:22s}  {"YES" if ok else "NO ":8s}  {describe(err)}')
        if ok:
            time.sleep(0.02)
            user32.UnregisterHotKey(None, _HOTKEY_ID)

    say('')
    shipped = results.get('Alt+C (SHIPPED)', False)
    if shipped:
        say('VERDICT: Alt+C IS REGISTRABLE on this box right now.')
        say('  So a dead Alt+C is NOT a taken key. Look next at the panel path:')
        say('  HOTKEY_REGISTERED in the log, PANEL_SHOWN on the keypress, and')
        say('  PANEL_VISIBILITY_* to see whether the window is ever MAPPED.')
    else:
        free = [k for k, v in results.items() if v and 'SHIPPED' not in k]
        holder, sha, segment = live_sotto()
        reg = last_registration(segment) or ''
        # A ARMADILHA QUE ISTO CORRIGE (medido 2026-10-30): com a app VIVA, o Alt+C esta'
        # tomado -- PELA PROPRIA APP. A sonda lia "outro programa tomou-o" e o passo da
        # bateria ficava vermelho para sempre, a acusar um defeito que nao existe. Quem
        # distingue e' o log: a instancia viva registou-o, e o pid esta' vivo.
        #
        # E A SEGUNDA ARMADILHA (medido 2026-11-01 11:16): a linha de registo tem de
        # ser do ACELERADOR DA APP e do SEGMENTO DESSA INSTANCIA. A versao anterior
        # procurava a ultima linha de hotkey do ficheiro inteiro -- que e'
        # `role=live accelerator=Ctrl+Space` -- e respondia "a app nao registou o Alt+C"
        # com o Alt+C registado quatro linhas acima.
        if holder and 'register=true' in reg:
            say('VERDICT: Alt+C IS HELD BY THE LIVE SOTTO ITSELF (pid=%d, code=%s).' % (holder, sha))
            say('  This probe registered nothing because the app in front of it owns the key.')
            say('  That is the NORMAL state with the app running -- not a defect, and not')
            say('  evidence for a stranger. Stop the app and re-run to test a third party.')
            say('  Log line: %s' % reg[-120:])
            # rc=0: com a app viva o normal E' ela deter a tecla. O passo da bateria so'
            # pode ficar vermelho quando o detentor NAO e' o Sotto (ver o fim desta funcao).
            return 0
        say('VERDICT: Alt+C IS TAKEN — another program owns MOD_ALT + C.')
        say('  THE APP CANNOT WORK AS SHIPPED ON THIS BOX: `HotkeyThread.run` logs')
        say('  HOTKEY_REGISTER_FAILED and returns, so Alt+C answers nothing and the')
        say('  owner is shown no message at all (the panel is hidden by design).')
        say(f'  Free alternatives measured just now: {free if free else "(none)"}')
        if holder:
            say('  (a Sotto pid=%d esta viva mas o SEGMENTO DELA nao diz'
                ' accelerator=%s register=true -- ultima linha de hotkey dessa'
                ' instancia: %r)' % (holder, SHIPPED_ACCEL, reg[-120:] or None))
        else:
            say('  (nenhuma largada nos logs candidatos e\' a instancia viva:'
                ' nem pid, nem mutex, nem ausencia de marcador de medicao)')
        return 1


if __name__ == '__main__':
    sys.exit(main())
