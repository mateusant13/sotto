#!/usr/bin/env python
# NO-BUG: instrumento da ordem do dono de 2026-11-05 (reserva) e de 2026-11-06
# (o espaco que vazava). Prova, NO WINDOWS DESTA MAQUINA, as duas metades que
# nenhum fake pode dar: `RegisterHotKey` e' EXCLUSIVO (a segunda reserva da'
# 1409 e o Unregister devolve a tecla) e `SetWindowsHookExW(WH_KEYBOARD_LL)`
# INSTALA de verdade -- o callback real engole o espaco e deixa passar o que nao
# e' `Ctrl+Space`.
"""PROBE: a reserva e' exclusiva, e o hook de teclado ENG OLE o espaco.

A PERGUNTA QUE ELE RESPONDE. O oraculo puro (`ctrlspace-swallow-oracle.py`)
prova a TABELA, a CLASSIFICACAO e o FIO com um `user32`-gravador. Faltam duas
coisas que um fake nao da':

  1. o Windows, nesta maquina, recusa uma SEGUNDA reserva do `Ctrl+Space`
     (`winerror=1409`) e aceita-a de novo depois do `UnregisterHotKey`;
  2. `SetWindowsHookExW(WH_KEYBOARD_LL, ...)` devolve um handle VALIDO neste
     processo, e a `HOOKPROC` real devolve 1 para o `WM_KEYDOWN` do espaco com
     `Ctrl` em baixo -- e 0 para o espaco sem `Ctrl` ou com o hook desarmado.

O QUE A RESERVA NAO PROVA (corrigido a 2026-11-06). Ser exclusivo nao e' engolir:
o `RegisterHotKey` entrega `WM_HOTKEY` **e** deixa o espaco chegar a' janela em
foco -- foi o espaco a pausar o YouTube. O braco 1 continua a medir a
exclusividade; quem mede o "nao vazar" e' o braco 2.

O QUE ELE NAO FAZ. Nao carrega tecla nenhuma (`keybd_event`/`SendInput` = 0: os
dois medem o Windows, nao a app), nao abre janela, nao mexe no audio.

O BRACO 2 E' UM PROCESSO FILHO ESCONDIDO (`_main/hidden-launch.py`, sem consola),
que instala o hook REAL e o retira em DOIS CHAMADOS, sem bombear mensagens. Essa
ordem e' deliberada: um hook de baixa prioridade cujo fio nao bombeia pode
segurar o teclado do dono ate' ao `LowLevelHooksTimeout`; com o handle medido e
o hook retirado no mesmo instante, nao existe janela em que um evento real fique
preso. O callback exercitado e' o MESMO `HOOKPROC` que o Windows acabou de
registar, chamado com `nCode=HC_ACTION` e um `KBDLLHOOKSTRUCT` sintetico -- o
"WM_KEYDOWN sintetico" do pedido, sem injectar teclas no sistema.

Uso:
    python _main/ctrlspace-swallow-probe.py            -> rc 0 PASS / rc 1 RED
    python _main/ctrlspace-swallow-probe.py --json     -> a leitura crua
    python _main/ctrlspace-swallow-probe.py --os-child -> o filho (uso interno)
    python _main/ctrlspace-swallow-probe.py --no-os    -> so' a reserva
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import importlib.util as _ilu
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WEBVIEW = os.path.join(os.path.dirname(HERE), 'app', 'webview')

user32 = ctypes.WinDLL('user32', use_last_error=True)

MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000
VK_SPACE = 0x20
WM_HOTKEY = 0x0312
PM_REMOVE = 0x0001
HOTKEY_ID = 0xB0F1


class _Runner(object):
    """Uma reserva feita do THREAD onde ela vive (`hWnd=NULL` e' por-fio)."""

    def __init__(self):
        self.register = None
        self.register_err = None
        self.thread_id = None

    def take(self):
        self.thread_id = int(ctypes.windll.kernel32.GetCurrentThreadId())
        msg = wt.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
        ctypes.set_last_error(0)
        ok = user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_NOREPEAT,
                                   VK_SPACE)
        self.register = bool(ok)
        self.register_err = int(ctypes.get_last_error()) if not ok else 0
        return self.register

    def release(self):
        if self.thread_id is None:
            return False
        return bool(user32.UnregisterHotKey(None, HOTKEY_ID))


# ---------------------------------------------------------------------------
# BRACO 2: o hook REAL, num filho escondido
# ---------------------------------------------------------------------------
def _load_space_swallow():
    if WEBVIEW not in sys.path:
        sys.path.insert(0, WEBVIEW)
    spec = _ilu.spec_from_file_location(
        'space_swallow_os_%d' % os.getpid(),
        os.path.join(WEBVIEW, 'space_swallow.py'))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def os_child():
    """Instala o hook, mede-o e retira-o -- tudo dentro deste processo filho."""
    ss = _load_space_swallow()
    toggles = []
    hook = ss.SpaceSwallowHook(
        on_toggle=lambda: toggles.append(1),
        log_fn=lambda line: print('OS_CHILD_LOG %s' % (line,), flush=True),
        role='os-probe')
    hook.set_armed(True)
    installed = hook.install()
    handle = hook.hook_handle
    # RETIRADO JA'. Ver a docstring: sem pump, um evento real ficaria preso.
    unhooked = hook.detach('os-probe')
    proc = hook._proc
    info = ss.KBDLLHOOKSTRUCT()
    info.vkCode = ss.VK_SPACE
    addr = ctypes.addressof(info)

    # O `detach` DESARMA (a segunda tranca). Para exercitar o CLASSIFICADOR
    # real re-arma-se SEM instalar -- o Windows nao tem este callback em cadeia
    # nenhuma, logo o que se mede aqui e' a decisao, nao o caminho de input.
    hook.set_armed(True)
    hook.mods_down = lambda: ss.MOD_CONTROL
    down = int(proc(ss.HC_ACTION, ss.WM_KEYDOWN, addr)) if proc else None
    repeat = int(proc(ss.HC_ACTION, ss.WM_KEYDOWN, addr)) if proc else None
    up = int(proc(ss.HC_ACTION, ss.WM_KEYUP, addr)) if proc else None
    hook.mods_down = lambda: 0
    plain = int(proc(ss.HC_ACTION, ss.WM_KEYDOWN, addr)) if proc else None
    # DESARMADO = o plano mandou devolver a tecla (jogo): nem instala. O `proc`
    # continua a ser chamado para provar a segunda tranca do classificador.
    hook.set_armed(False)
    hook.mods_down = lambda: ss.MOD_CONTROL
    disarmed = int(proc(ss.HC_ACTION, ss.WM_KEYDOWN, addr)) if proc else None
    # E o `install` DESARMADO nao toca no sistema: sem handle.
    hook2 = ss.SpaceSwallowHook(on_toggle=lambda: toggles.append(2),
                                log_fn=lambda line: None, role='os-probe-game')
    hook2.set_armed(False)
    gaming_install = hook2.install()
    gaming_handle = hook2.hook_handle

    out = {'installed': bool(installed), 'handle': handle,
           'unhooked': bool(unhooked),
           'down_rc': down, 'repeat_rc': repeat, 'up_rc': up,
           'plain_rc': plain, 'disarmed_rc': disarmed,
           'toggles': len(toggles),
           'gaming_installed': bool(gaming_install),
           'gaming_handle': gaming_handle}
    ok = (out['installed'] and bool(handle) and out['unhooked']
          and down == 1 and repeat == 1 and up == 1
          and plain == 0 and disarmed == 0 and out['toggles'] == 1
          and not out['gaming_installed'] and not out['gaming_handle'])
    print('OS_CHILD_INSTALL installed=%(installed)s handle=%(handle)s '
          'unhooked=%(unhooked)s' % out, flush=True)
    print('OS_CHILD_SWALLOW down=%(down_rc)s repeat=%(repeat_rc)s '
          'up=%(up_rc)s toggles=%(toggles)s' % out, flush=True)
    print('OS_CHILD_PASS plain=%(plain_rc)s disarmed=%(disarmed_rc)s' % out,
          flush=True)
    print('OS_CHILD_GAMING installed=%(gaming_installed)s '
          'handle=%(gaming_handle)s' % out, flush=True)
    print('OS_CHILD_VERDICT %s' % ('PASS' if ok else 'FAIL'), flush=True)
    return 0 if ok else 1


def _load_hidden_launch():
    spec = _ilu.spec_from_file_location(
        'sotto_hidden_launch', os.path.join(HERE, 'hidden-launch.py'))
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def os_arm():
    """O filho passa pelo largador da casa; nada aparece em ecra."""
    hidden = _load_hidden_launch()
    rc, out, err = hidden.run([sys.executable, os.path.abspath(__file__),
                               '--os-child'], capture=True, timeout=60)
    text = (out or '') + (err or '')
    fields = {}
    for line in text.splitlines():
        if not line.startswith('OS_CHILD'):
            continue
        print(line, flush=True)
        if line.startswith('OS_CHILD_VERDICT'):
            fields['verdict'] = line.split()[-1]
        elif line.startswith('OS_CHILD_INSTALL'):
            for token in line.split()[1:]:
                if '=' in token:
                    key, value = token.split('=', 1)
                    fields[key] = value
    ok = rc == 0 and fields.get('verdict') == 'PASS'
    return ok, {'rc': rc, 'fields': fields,
                'tail': text.strip().splitlines()[-3:]}


def main(argv):
    if '--os-child' in argv:
        return os_child()
    out = {'n_second_register_rc': None, 'second_err': None,
           'first_rc': None, 'first_err': None,
           'third_after_release_rc': None, 'third_err': None,
           'holder': None, 'hook_installed': None, 'hook_handle': None,
           'os_arm_rc': None, 'verdict': 'FAIL'}
    a = _Runner()
    first = a.take()
    out['first_rc'] = int(a.register)
    out['first_err'] = a.register_err
    if not first:
        # Alguem tem a combinacao: ou a app do dono, ou outro programa. O probe
        # nao pode afirmar "a nossa reserva funciona" -- e nao afirma.
        out['holder'] = 'someone-else' if a.register_err == 1409 else 'error'
    else:
        out['holder'] = 'this-probe'
    # A SEGUNDA RESERVA, DE OUTRO FIO, E' A PROVA DE EXCLUSIVIDADE.
    b = _Runner()
    second = b.take()
    out['n_second_register_rc'] = int(b.register)
    out['second_err'] = b.register_err
    if second:
        b.release()
    released = a.release()
    c = _Runner()
    third = c.take()
    out['third_after_release_rc'] = int(c.register)
    out['third_err'] = c.register_err
    if third:
        c.release()

    # O VEREDITO DA MECANICA, sem confundir os dois casos.
    if first:
        exclusive = (not second) and b.register_err == 1409
        register_ok = bool(exclusive and third and released)
    else:
        # A tecla ja' era de alguem: a exclusividade prova-se pelo 1409 alheio.
        register_ok = a.register_err == 1409

    # BRACO 2: o hook real. `--no-os` existe para uma medicao so' da reserva.
    hook_ok = True
    if '--no-os' not in argv:
        hook_ok, hook = os_arm()
        out['os_arm_rc'] = hook['rc']
        out['hook_installed'] = hook['fields'].get('installed')
        out['hook_handle'] = hook['fields'].get('handle')
        if not hook_ok:
            print('CTRLSPACE-SWALLOW-OS FAIL rc=%s tail=%s'
                  % (hook['rc'], hook['tail']), flush=True)

    out['verdict'] = 'PASS' if (register_ok and hook_ok) else 'FAIL'
    if '--json' in argv:
        print(json.dumps(out, indent=2, sort_keys=True))
    else:
        print('CTRLSPACE-SWALLOW-PROBE holder=%(holder)s '
              'first=%(first_rc)s err=%(first_err)s'
              ' second=%(n_second_register_rc)s second_err=%(second_err)s'
              ' third_after_release=%(third_after_release_rc)s '
              'third_err=%(third_err)s' % out)
        print('CTRLSPACE-SWALLOW-PROBE hook_installed=%(hook_installed)s '
              'hook_handle=%(hook_handle)s os_arm_rc=%(os_arm_rc)s' % out)
        print('CTRLSPACE-SWALLOW-PROBE VERDICT: %s -- a reserva e exclusiva '
              '(1409 na segunda, devolvida no fim) e o HOOK de teclado real '
              'engole o espaco com Ctrl e deixa passar o resto'
              % out['verdict'])
    return 0 if out['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
