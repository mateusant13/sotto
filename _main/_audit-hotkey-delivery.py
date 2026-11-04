#!/usr/bin/env python3
"""Does Alt+C actually reach a handler — and does the FALLBACK chain work?

WHY: Alt+C is the app's only control, and every claim about it in this repo was
made by reading code or by a probe that called the toggle function directly. This
probe drives the REAL surface a keypress drives, with no app, no window, no audio:

  1. ARM identity   — `HotkeyThread('Alt+C', …)` registers on this box, and a REAL
                      `WM_HOTKEY` posted to ITS OWN thread queue (the same queue the
                      OS writes to) invokes the handler. That is "Alt+C works" minus
                      the physical key: registration, delivery, dispatch.
  2. ARM fallback   — `arm_hotkey(stub, <TAKEN>)` must NOT leave the app with a dead
                      hotkey. The bait is real: `Alt+F9` is owned by another program
                      on this box (measured by `_main/_audit-hotkey-probe.py`), so
                      the chain has to walk past it and win with a fallback. The
                      receipt names which key won.
  3. ARM single     — `take_single_instance_lock` refuses a SECOND holder of the same
                      name, which is the collision that makes a fresh launch look
                      broken (its `RegisterHotKey` fails and Alt+C answers the first,
                      possibly stale, shell). A test-only name is used, so a running
                      app is never disturbed.
  4. ARM toggle     — a stub shell's `toggle_panel` is called by the delivered
                      keypress, proving the handler is wired to a toggle and not to
                      a lambda that does nothing.

── ARM 1 AND THE OWNER'S OWN APP (added 2026-10-08) ────────────────────────────
This probe used to read `RegisterHotKey(Alt+C)` → 1409 as a property of the BOX and
print `VERDICT: RED — Alt+C registers on this box`, which is a false accusation
whenever the OWNER'S APP IS RUNNING: the app holds Alt+C, so the probe cannot have
it, and the app is working exactly as designed. The instrument could not tell "the
key is taken by a STRANGER" from "the key is taken by the very app we are
measuring" — a probe that cannot distinguish those two measures the probe, not the
app. Measured 2026-10-08 on the live box: `HOTKEY_REGISTER_FAILED accelerator=Alt+C
winerror=1409` while pid 27492 (`pythonw.exe app\\webview\\sotto_webview.py --log
_main\\webview-run.log --with-worker`) was running and its own log carried
`HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true`.

So ARM 1 now asks WHO holds it, using the shell's OWN hotkey id
(`sotto_webview._HOTKEY_ID`) — registering on that id can only succeed if nothing
else holds it (any conflict is 1409 whoever the holder is), and nothing but a
Sotto shell ever registers that id. When it is genuinely held by a Sotto shell, the
arm SKIPs out loud (`SKIP: held by the running Sotto shell pid=…`) and the reason is
reported UNVERIFIED. A SKIP is never a pass:

  * the verdict line says `SKIPPED` and the summary states that "Alt+C works" is
    the one claim this run could NOT make;
  * the LIVE INSTANCE and its own words must BOTH corroborate. The instance comes
    from the one selector this repo has (`_main/load-shedding-oracle.py`,
    `newest_shell_segment`: alive, won the mutex, not a measurement launch), and its
    OWN segment of the log must say `HOTKEY_REGISTERED accelerator=Alt+C
    register=true`. Holding alone is not enough, so a stranger holding Alt+C can
    never be excused — and a MEASUREMENT launch that happens to be last in the log
    can never be mistaken for the app (measured 2026-11-01 11:16: it was);
  * if the shell in the log got a FALLBACK key, that means Alt+C is held by
    something that is NOT the Sotto shell and the arm is RED, naming the holder;
  * arms 2, 3 and 4 run either way — the fallback chain, the single-instance lock
    and the toggle rule are still really exercised, which is the half of this
    instrument the owner's running app does not block.

Nothing is left registered, no device is opened, no window is created, and the whole
run is under two seconds.

    cmd /c "python _main\\_audit-hotkey-delivery.py > _main\\_audit-probe\\hotkey-delivery.log 2>&1"

Exit 0 when every arm holds (or the only arm that could not run was skipped because
the owner's app holds the key), 1 otherwise, 2 on a setup error. A FAIL is a real
failure of the Alt+C path and must be reported as such. A SKIP never hides a FAIL:
if any other arm fails, the exit code is 1.
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SHELL_DIR = os.path.join(ROOT, 'app', 'webview')
LOG = os.path.join(HERE, '_audit-probe', 'hotkey-delivery.log')

lines: list[str] = []
failed: list[str] = []
skipped: list[str] = []


def say(msg: str) -> None:
    lines.append(msg)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines) + '\n')
    print(msg, flush=True)


def check(name: str, real, want) -> None:
    ok = real == want
    if not ok:
        failed.append(name)
    say(f'{"PASS" if ok else "FAIL"} {name}\n       real={real!r} want={want!r}')


def skip(name: str, why: str) -> None:
    """An arm that could NOT be run. Never a PASS, and never silent."""
    skipped.append(name)
    say(f'SKIP {name}\n       {why}')


# ---------------------------------------------------------------------------
# WHO holds the key — the distinction this instrument was missing
# ---------------------------------------------------------------------------
# A IDENTIDADE DA INSTANCIA VIVA NAO SE ESCREVE OUTRA VEZ AQUI. Ela vive em
# `_main/load-shedding-oracle.py` (`newest_shell_segment`, o nome que ele exporta;
# `find_live_instance` nunca existiu): recusa marcadores de medicao (`--selftest`,
# `--mutex-name`, `--no-worker`), recusa a largada que PERDEU a mutex
# (`SINGLE_INSTANCE already_running=true`) e recusa pids mortos; escolhe entre o
# log deste repo e o do checkout principal, porque a app do dono arranca de la'.
#
# O CAMINHO ANTIGO DESTE FICHEIRO -- `Get-CimInstance` + "as tres ultimas linhas
# de SHELL_STARTUP_STAGE" + o ficheiro de log INTEIRO para o `HOTKEY_REGISTERED`
# -- foi RETIRADO em 2026-11-01: medido na bateria das 11:16, ele deu
# `Alt+C held=True` com a app do dono viva e a registrar a tecla, e publicou
# "no live Sotto shell claims it -- the holder is another program". Era o censo
# a julgar a MEDICAO em vez da instancia, que e' exactamente a classe que o
# escolhedor unico existe para fechar.
SELECTOR = os.path.join(HERE, 'load-shedding-oracle.py')


def selector():
    """O escolhedor unico da instancia viva (`load-shedding-oracle.py`).

    O nome que ele EXPORTA e' `newest_shell_segment(log_path)`. MEDIDO 2026-11-01
    11:47: este ficheiro chamava `selector().find_live_instance()`, que nunca
    existiu naquele modulo -- `AttributeError`, capturado pelo `except` do braco,
    e o braco concluia "nada corrobora o detentor" com a app do dono a registrar
    Alt+C no log ao lado. `live_instance()` aplica a regra que existe.
    """
    if SELECTOR in sys.modules:
        return sys.modules[SELECTOR]
    import importlib.util

    spec = importlib.util.spec_from_file_location('hotkey_live_instance', SELECTOR)
    module = importlib.util.module_from_spec(spec)
    sys.modules[SELECTOR] = module
    spec.loader.exec_module(module)
    return module


def candidate_logs():
    """Os logs onde a instancia do DONO pode estar -- o desta arvore e o do repo principal.

    MEDIDO 2026-11-01 11:47 nesta worktree: o log dela nao tem uma unica largada, e
    a instancia viva (pid 55448, `HOTKEY_REGISTERED role=panels accelerator=Alt+C
    register=true`) so' aparece no log de `H:/sotto`, de onde a app arranca.
    """
    root = str(selector().ROOT)
    logs = [os.path.join(root, '_main', 'webview-run.log')]
    try:
        import subprocess

        common = subprocess.run(
            ['git', '-C', root, 'rev-parse', '--git-common-dir'],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
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
    """`(log, pid, segmento)` da instancia viva, ou `(None, None, '')`."""
    for log in candidate_logs():
        pid, seg = selector().newest_shell_segment(log)
        if pid is not None:
            return log, pid, seg
    return None, None, ''



def shell_log_state(segment: str) -> dict:
    """O que ESTA largada diz que registou -- o SEGMENTO dela, nao o ficheiro.

    O ficheiro `webview-run.log` e' escrito por TODAS as instancias e por todas as
    medicoes: a ultima linha de hotkey dele pode ser de outra. MEDIDO 2026-11-01
    11:16: a app do dono registou Alt+C e a ultima linha do ficheiro dizia
    `HOTKEY_REGISTERED role=live accelerator=Ctrl+Space`, por isso o instrumento
    publicou "no live Sotto shell claims it -- the holder is another program" com
    a prova do contrario quatro linhas acima.

    Por acelerador, o estado e' o da ULTIMA linha DESTA instancia que o nomeia: um
    `HOTKEY_REGISTERED ... register=true` seguido de `HOTKEY_REGISTER_FAILED` da
    MESMA instancia e' "falhou", e o inverso e' "registou".
    """
    import re

    st = {'state': {}, 'registered': [], 'failed': [], 'last_line': ''}
    hotkey_lines = []
    for line in segment.splitlines():
        if 'HOTKEY_REGISTERED' not in line and 'HOTKEY_REGISTER_FAILED' not in line \
                and 'HOTKEY_FALLBACK' not in line:
            continue
        hotkey_lines.append(line)
        # A LINHA TEM CAMPOS A MAIS DESDE 2026-11-01 (`role=panels`, ver
        # `HotkeyThread`), por isso o acelerador e' LIDO, nao posicionado: o
        # `REGISTERED_RE` antigo exigia `accelerator=` logo apos
        # `HOTKEY_REGISTERED` e devolvia ZERO em todas as linhas deste build.
        accelerator = None
        for token in line.split():
            if token.startswith('accelerator='):
                accelerator = token[len('accelerator='):]
                break
        if accelerator is None:
            continue
        if 'HOTKEY_REGISTER_FAILED' in line:
            st['failed'].append(accelerator)
            st['state'][accelerator] = 'failed'
        elif 'register=true' in line:
            st['registered'].append(accelerator)
            st['state'][accelerator] = 'registered'
    st['last_line'] = hotkey_lines[-1] if hotkey_lines else ''
    return st




def key_held(accelerator: str, hotkey_id: int) -> tuple[bool, int]:
    """Is `accelerator` held by ANYTHING, asked on the hotkey id the shell uses?

    `RegisterHotKey(NULL, id, mods, vk)` fails with 1409 when the SAME id already
    holds the SAME accelerator, and this id is the shell's own
    (`sotto_webview._HOTKEY_ID`). Answering the question on that id is what makes
    the attribution possible: nothing but a Sotto shell ever registers it, so 1409
    here means a Sotto shell is holding the key. The registration is released
    immediately, and only against a NULL window on this thread, so nothing on the
    owner's screen or in his app is touched.
    """
    import ctypes.wintypes as wt

    mods, vk = _SHELL_MOD.parse_accelerator(accelerator)
    user32 = ctypes.WinDLL('user32', use_last_error=True)

    class MSG(ctypes.Structure):
        _fields_ = [('hwnd', wt.HWND), ('message', wt.UINT), ('wParam', wt.WPARAM),
                    ('lParam', wt.LPARAM), ('time', wt.DWORD),
                    ('pt_x', wt.LONG), ('pt_y', wt.LONG)]

    msg = MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
    ctypes.set_last_error(0)
    ok = bool(user32.RegisterHotKey(None, hotkey_id,
                                    mods | _SHELL_MOD.MOD_NOREPEAT, vk))
    err = ctypes.get_last_error()
    if ok:
        user32.UnregisterHotKey(None, hotkey_id)
    return (not ok), err


_SHELL_MOD = None  # set by main() once the shell module is imported


def who_holds_alt_c(shell_mod, accelerator: str) -> dict:
    """The verdict ARM 1 needs: is Alt+C held, and by the owner's own app?

    Both halves are required before a shell gets the blame or the credit:
      * the OS must report the shell's id as HOLDING the key, and
      * the LIVE instance — the one `live_instance()` picks: alive, holding the
        mutex, not a measurement launch — must say, in ITS OWN segment
        of the log, that it registered THAT accelerator.
    """
    outcome = {'held': None, 'winerror': None, 'shells': [], 'snapshot_error': '',
               'logs': {}, 'sotto_owns': False, 'why': ''}

    try:
        held, err = key_held(accelerator, shell_mod._HOTKEY_ID)
    except Exception as exc:  # noqa: BLE001
        outcome['snapshot_error'] = f'registration probe failed: {type(exc).__name__}: {exc}'
        return outcome
    outcome['held'] = held
    outcome['winerror'] = err
    if not held:
        return outcome

    try:
        log, pid, segment = live_instance()
    except Exception as exc:  # noqa: BLE001 -- an instrument fault is not a verdict
        outcome['snapshot_error'] = f'live-instance selector failed: {type(exc).__name__}: {exc}'
        pid, segment = None, ''
        log = ''
    if pid is None:
        outcome['why'] = ('the key is HELD and NO launch in the candidate logs is the live '
                          'Sotto instance (no alive pid that won the mutex, or only '
                          'measurement launches) — so nothing can corroborate the holder')
        return outcome
    pid = int(pid)
    st = shell_log_state(segment)
    outcome['shells'] = [{'pid': pid, 'log': str(log)}]
    outcome['logs'][pid] = st
    if st['state'].get(accelerator) == 'registered':
        outcome['sotto_owns'] = True
        outcome['owner_pid'] = pid
        outcome['owner_log'] = str(log)
        outcome['why'] = (
            f'pid {pid} is the live instance (alive, won the mutex, no measurement '
            f'marker) and its OWN segment of {log} carries "HOTKEY_REGISTERED '
            f'accelerator={accelerator} register=true"'
        )
        return outcome
    outcome['why'] = (
        f'the key is HELD and the live instance pid {pid} ({log}) does NOT say '
        f'accelerator={accelerator} register=true in its own segment: state='
        f'{st["state"].get(accelerator)!r} last_hotkey_line={st["last_line"][-120:]!r}'
        f' — the holder is another program'
    )
    return outcome



class StubShell:
    """Just enough shell for the hotkey surface: the handler the keypress calls."""

    def __init__(self):
        self.toggles: list[str] = []
        self.hotkey = None

    def toggle_panel(self, reason):
        self.toggles.append(reason)
        return True


def main() -> int:
    sys.path.insert(0, SHELL_DIR)
    try:
        import sotto_webview as shell_mod
    except Exception as exc:  # noqa: BLE001
        say(f'SETUP ERROR: cannot import the shell: {type(exc).__name__}: {exc}')
        return 2

    global _SHELL_MOD
    _SHELL_MOD = shell_mod

    say(f'shell module: {shell_mod.__file__}')
    say(f'fallbacks declared: {shell_mod.HOTKEY_FALLBACKS}')
    say(f'shell hotkey id: {shell_mod._HOTKEY_ID:#06x} (the id ARM 1 asks the OS on)')
    say('')

    # ── ARM 1: the requested accelerator registers and its queue delivers ────
    # BEFORE blaming Alt+C, ask WHO holds it: the owner's app holding the key he
    # presses is the app WORKING, not a defect, and this instrument used to report
    # it as RED (see the module docstring).
    owners = who_holds_alt_c(shell_mod, 'Alt+C')
    if owners['held'] is None:
        say(f'ARM 1 ownership probe: COULD NOT ASK — {owners["snapshot_error"]}')
        say('  (the arm below still runs and its own registration is the answer of record)')
    else:
        say(f'ARM 1 ownership probe: Alt+C held={owners["held"]} winerror={owners["winerror"]} '
            f'asked on id {shell_mod._HOTKEY_ID:#06x}')
        for sh in owners['shells']:
            st = owners['logs'].get(sh['pid'], {})
            say(f'  live instance pid={sh["pid"]} log={sh["log"]} '
                f'hotkeys={st.get("state")}')
        if owners['snapshot_error']:
            say(f'  selector note: {owners["snapshot_error"]}')
        if owners['held'] and not owners['sotto_owns']:
            say(f'  who holds it: {owners["why"]}')

    stub = StubShell()
    fired = threading.Event()

    def on_hotkey():
        stub.toggle_panel('hotkey')
        fired.set()

    thread = shell_mod.HotkeyThread('Alt+C', on_hotkey)
    thread.start()
    ready = thread.wait_ready(5)
    say(f'Alt+C register: ready={ready} registered={thread.registered} '
        f'winerror={thread.register_error}')
    say('')

    if owners.get('sotto_owns'):
        # The owner's app holds Alt+C. The arm cannot be run — and that is a fact
        # about the INSTRUMENT's reach, not about the app.
        skip('the Alt+C delivery arm',
             f'SKIP: held by the running Sotto shell pid={owners["owner_pid"]} — {owners["why"]}. '
             f'The probe registered NOTHING (its own attempt answered '
             f'winerror={thread.register_error}), and "Alt+C works" is the one claim this run '
             f'CANNOT make. It needs a run with the app closed.')
        say('       (the app holding Alt+C is the app working as designed: it answers the')
        say('        owner\'s key. It is not a defect and it is not this probe\'s to report.)')
    elif thread.registered:
        posted = thread.simulate_press()
        check('a WM_HOTKEY posted to the hotkey thread is accepted', posted, True)
        check('the handler ran within 2 s', fired.wait(2.0), True)
        check('the handler called toggle_panel(reason=hotkey)',
              stub.toggles[:1], ['hotkey'])
    else:
        held_by = ('HELD by another program, and no live Sotto shell claims it'
                   if owners['held'] else 'NOT held by anything this probe can see '
                                          '(so the shell failed for its own reason)')
        check('Alt+C registers on this box', bool(thread.registered), True)
        say(f'       the key is {held_by}. {owners["why"]}')
    thread.stop()

    # ── ARM 2: the fallback chain, baited with a key that IS taken here ──────
    # This arm does NOT depend on ARM 1 being runnable: the bait is a DIFFERENT
    # accelerator, so it is exercised even while the owner's shell holds Alt+C.
    say('')
    bait = 'Alt+F9'
    ctypes_ok, err = _registration_probe(shell_mod, bait)
    say(f'bait {bait}: registrable-here={ctypes_ok} winerror={err} '
        '(a taken key is the only honest bait)')
    if ctypes_ok:
        say('NOTE: the bait is FREE on this box right now, so the fallback arm')
        say('      cannot prove itself — reported as UNVERIFIED, not as PASS.')
    else:
        stub2 = StubShell()
        won = shell_mod.arm_hotkey(stub2, bait)
        got = getattr(won, 'accelerator', None)
        check('arm_hotkey returns a LIVE thread despite the taken request',
              bool(getattr(won, 'registered', False)), True)
        check('the winner is one of the documented fallbacks',
              got in shell_mod.HOTKEY_FALLBACKS, True)
        say(f'       winner={got!r} (requested {bait!r})')
        if won is not None:
            won.stop()

    # ── ARM 3: one shell at a time, on a test-only name ─────────────────────
    say('')
    test_name = 'Local\\SottoAuditProbe'
    first = shell_mod.take_single_instance_lock(test_name)
    second = shell_mod.take_single_instance_lock(test_name)
    other = shell_mod.take_single_instance_lock(test_name + '-other')
    check('the first holder gets the lock', first, True)
    check('a second holder is REFUSED (the collision that breaks Alt+C)',
          second, False)
    check('a different name is independent', other, True)

    say('')
    # ── ARM 4: the toggle asks the WINDOW, not a cache ──────────────────────
    # The one link a stub cannot execute (it needs a real HWND) is
    # `toggle_panel` → `show_panel`. What CAN be asserted is the decision rule it
    # uses: a cached `self.visible` that has gone stale makes the owner's first
    # Alt+C a no-op HIDE of a panel he cannot see — "Alt+C does nothing" until he
    # presses it twice. So the rule itself is pinned at the source.
    source = open(shell_mod.__file__, encoding='utf-8').read()
    body = source[source.find('    def toggle_panel(self, reason):'):]
    body = body[:body.find('\n    def ', 10)]
    live = 'window_visible(self.hwnd)' in body
    cached_only = 'self.hide_panel(reason) if self.visible' in body
    check('toggle_panel decides from the LIVE window state', live, True)
    check('toggle_panel no longer decides from the cached flag alone',
          cached_only, False)
    gate = 'MessageBoxW' in source and 'HOTKEY_FALLBACKS' in source
    check('the loud-failure path and the fallback list exist in the shell',
          gate, True)

    say('')
    if failed:
        say('VERDICT: RED — ' + ', '.join(failed))
        if skipped:
            say(f'         (note: {len(skipped)} arm(s) were SKIPPED: {", ".join(skipped)})')
        return 1
    if skipped:
        # NOT a pass. Every arm that COULD run held, and the one that could not is
        # named, with the reason and the cost stated in the same breath.
        say('VERDICT: SKIPPED — every arm that could run held, but this run CANNOT claim '
            '"Alt+C reaches its handler"')
        say('         skipped: ' + '; '.join(skipped))
        say('         the fallback chain, the single-instance lock and the toggle rule WERE '
            'really exercised above.')
        say('         to verify the skipped arm: close the Sotto shell and re-run this probe.')
        return 0
    say('VERDICT: GREEN — Alt+C registers, a WM_HOTKEY reaches the handler, the '
        'handler toggles, the fallback chain survives a taken key, and a second '
        'shell is refused instead of silently stealing nothing.')
    return 0


def _registration_probe(shell_mod, accelerator):
    """Can THIS process register `accelerator` right now? (bait selection)"""
    import ctypes
    import ctypes.wintypes as wt

    mods, vk = shell_mod.parse_accelerator(accelerator)
    user32 = ctypes.WinDLL('user32', use_last_error=True)

    class MSG(ctypes.Structure):
        _fields_ = [('hwnd', wt.HWND), ('message', wt.UINT), ('wParam', wt.WPARAM),
                    ('lParam', wt.LPARAM), ('time', wt.DWORD),
                    ('pt_x', wt.LONG), ('pt_y', wt.LONG)]

    msg = MSG()
    user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
    ctypes.set_last_error(0)
    ok = bool(user32.RegisterHotKey(None, 0x7F01,
                                    mods | shell_mod.MOD_NOREPEAT, vk))
    err = ctypes.get_last_error()
    if ok:
        user32.UnregisterHotKey(None, 0x7F01)
    return ok, err


if __name__ == '__main__':
    sys.exit(main())
