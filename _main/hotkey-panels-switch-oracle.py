# NO-BUG: The Alt+C switch in the tray menu arms, disarms and SURVIVES a restart.
"""The Alt+C switch in the tray menu arms, disarms and SURVIVES a restart.

OWNER, 2026-11-07, verbatim: *"faz um botao 'desativar atalho alt c' no click
direito do icon do sotto"*, and one message later *"e claro, é ativar e
desativar"*.

WHAT A SWITCH CAN GET WRONG, and each one is an arm below:

  1. it does not come back after a restart (the flag is not written, or a second
     writer drops it) -- a button that lies the next morning;
  2. it is too fragile: a corrupt or truncated settings file makes the app open
     with NO hotkey at all, and the hotkey is the only control that opens it;
  3. it reads as "off" for anything that is not the exact literal `false`
     (0, "false", null) -- the refusal has to be asymmetric: off needs someone
     to have written it, on needs only silence;
  4. the ARMING path ignores the flag (`arm_hotkey(panels=True)` hard-wired), so
     the switch works until the next start and then the key is back.

THE FILE IS THE REAL ONE (`app/webview/hotkey_settings.py`), driven on a
TEMPORARY path: the owner's `_main/hotkey-settings.json` is never touched.

  python _main/hotkey-panels-switch-oracle.py             # positive arms
  python _main/hotkey-panels-switch-oracle.py --neg-arm   # mutants, rc=1 when caught
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile

SHELL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..',
                         'app', 'webview')
SHELL = os.path.join(SHELL_DIR, 'sotto_webview.py')
SETTINGS = os.path.join(SHELL_DIR, 'hotkey_settings.py')


def load(path, name='mod_under_test'):
    import importlib.util
    if SHELL_DIR not in sys.path:
        sys.path.insert(0, SHELL_DIR)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _settings(module_path=None):
    path = module_path or SETTINGS
    mod = load(path, 'hotkey_settings_under_test')
    return mod


def _read_json(path):
    """The file as a dict, or {} when a mutant never wrote it."""
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def judge(settings) -> list:
    checks = []
    root = tempfile.mkdtemp(prefix='sotto-hotkey-switch-')
    file = os.path.join(root, 'hotkey-settings.json')

    # ARM 1 -- no file at all is "armed": silence is not an order to disarm.
    checks.append(('absent_file_means_armed',
                   settings.panels_enabled(file) is True,
                   f'enabled={settings.panels_enabled(file)!r}'))

    # ARM 2 -- the switch writes, and the write is re-read from DISK (the module
    # caches by mtime, so a stale cache would answer here).
    saved = settings.set_panels_enabled(False, file)
    settings._CACHE['stamp'] = None
    settings._CACHE['value'] = None
    on_disk = _read_json(file)
    checks.append(('disarm_writes_false_to_disk',
                   saved.get('ok') is True
                   and on_disk.get(settings.PANELS_ENABLED_KEY) is False,
                   f'saved={saved} disk={on_disk}'))
    checks.append(('disarm_reads_back_as_disarmed',
                   settings.panels_enabled(file) is False,
                   f'enabled={settings.panels_enabled(file)!r}'))

    # ARM 3 -- A SECOND WRITER MUST NOT EAT THE FLAG. `write()` exists to store
    # keybindings; a payload built from zero dropped `panels_enabled`, so the
    # owner disarmed Alt+C, changed the live key, and Alt+C came back alone.
    settings.write({'live': settings.DEFAULTS[settings.LIVE_KEY]}, file)
    settings._CACHE['stamp'] = None
    settings._CACHE['value'] = None
    after = _read_json(file)
    checks.append(('changing_a_key_keeps_the_switch_off',
                   after.get(settings.PANELS_ENABLED_KEY) is False
                   and settings.panels_enabled(file) is False,
                   f'disk={after}'))

    # ARM 4 -- arm again, from the same path.
    settings.set_panels_enabled(True, file)
    checks.append(('arm_reads_back_as_armed',
                   settings.panels_enabled(file) is True,
                   f'enabled={settings.panels_enabled(file)!r}'))

    # ARM 5 -- ONLY the literal `false` disarms. A file that says 0, "false" or
    # null is not an order; the hotkey is the only way into the panel.
    for value in (0, 'false', None, [], {}):
        io.open(file, 'w', encoding='utf-8').write(json.dumps(
            {settings.PANELS_ENABLED_KEY: value}))
        got = settings.panels_enabled(file)
        checks.append((f'not_off_for_{value!r}', got is True, f'enabled={got!r}'))

    # ARM 6 -- a CORRUPT file opens ARMED, and the key bindings fall back to the
    # factory value instead of raising through the start-up path.
    io.open(file, 'w', encoding='utf-8').write('{not json')
    got = settings.panels_enabled(file)
    keys = settings.accelerators(file)
    checks.append(('corrupt_file_opens_armed',
                   got is True and keys == dict(settings.DEFAULTS),
                   f'enabled={got!r} keys={keys}'))

    return checks


def judge_wiring(shell) -> list:
    """The two call sites: the START-UP gate and the TOGGLE handler.

    Both are driven with `arm_hotkey_role` replaced by a RECORDER -- a real
    registration here would take `Ctrl+Space` (and `Alt+C`) from the owner's own
    app, which is exactly the class of damage an oracle must not do.
    """
    checks = []
    calls = []
    logs = []

    def recorder(shell_obj, role, requested, fallbacks):
        calls.append((role, requested))
        return {'thread': role}

    real_role = shell.arm_hotkey_role
    real_log = shell.log
    shell.arm_hotkey_role = recorder
    shell.log = logs.append
    try:
        # ARM 7 -- the switch is READ at start-up, and a disarmed file means the
        # panels key is never registered while the live key still is.
        calls.clear()
        logs.clear()
        holder = type('H', (), {})()
        shell.arm_hotkey(holder, 'Alt+C', panels=False)
        checks.append(('startup_skips_panels_when_disarmed',
                       [c[0] for c in calls] == ['live'],
                       f'calls={calls}'))
        checks.append(('startup_says_why_the_key_is_off',
                       any('HOTKEY_PANELS_DISABLED' in line for line in logs),
                       f'log={logs}'))

        # ARM 8 -- and an armed file still registers it.
        calls.clear()
        shell.arm_hotkey(holder, 'Alt+C', panels=True)
        checks.append(('startup_arms_panels_when_armed',
                       [c[0] for c in calls] == ['panels', 'live'],
                       f'calls={calls}'))

        # ARM 9 -- the handler arms, disarms, PERSISTS and refreshes the menu.
        # The object is a bare `SottoShell` (no window, no WebView2) so the real
        # methods run without a second app. The two collaborators at the edges
        # are replaced: `arm_hotkey` (a stub thread, never a real registration)
        # and `hotkey_config` (a settings module pointed at a TEMPORARY file --
        # an oracle that writes `_main/hotkey-settings.json` would disarm the
        # owner's own key as a side effect of being run).
        root = tempfile.mkdtemp(prefix='sotto-hotkey-toggle-')
        tmp_file = os.path.join(root, 'hotkey-settings.json')
        real_cfg = shell.hotkey_config
        real_arm = shell.arm_hotkey
        writes = []

        class _Cfg:
            def accelerators(self):
                return dict(settings_ref[0].DEFAULTS)

            def panels_enabled(self):
                return settings_ref[0].panels_enabled(tmp_file)

            def set_panels_enabled(self, flag):
                writes.append(flag)
                return settings_ref[0].set_panels_enabled(flag, tmp_file)

        settings_ref = [_settings()]

        def _arm_stub(shell_obj, requested, panels=True):
            return _ThreadStub()

        shell.arm_hotkey = _arm_stub
        shell.hotkey_config = lambda: _Cfg()
        try:
            shell_obj = object.__new__(shell.SottoShell)
            shell_obj.hotkey = None
            shell_obj._hotkey_requested = 'Alt+C'
            shell_obj.live_hotkey = None
            refreshed = []
            shell_obj.tray = type('T', (), {'refresh_menu':
                                            lambda self, why='state':
                                            refreshed.append(why)})()
            armed = shell_obj.toggle_panels_hotkey()
            first = dict(armed)
            disarmed = shell_obj.toggle_panels_hotkey()
        finally:
            shell.hotkey_config = real_cfg
            shell.arm_hotkey = real_arm
        checks.append(('toggle_arms_then_disarms',
                       first.get('enabled') is True and disarmed.get('enabled') is False,
                       f'armed={first} disarmed={disarmed}'))
        checks.append(('toggle_persists_both_directions',
                       writes == [True, False],
                       f'writes={writes} disk_enabled='
                       f'{settings_ref[0].panels_enabled(tmp_file)}'))
        checks.append(('toggle_refreshes_the_menu_each_time',
                       refreshed == ['hotkey-toggle', 'hotkey-toggle'],
                       f'refreshed={refreshed}'))
    finally:
        shell.arm_hotkey_role = real_role
        shell.log = real_log
    return checks


class _ThreadStub:
    """A registered, alive hotkey thread, with the two things `stop` needs."""

    accelerator = 'Alt+C'
    registered = True

    def is_alive(self):
        return True

    def stop(self):
        self.stopped = True


def compact(checks):
    return [(name, bool(ok), detail) for name, ok, detail in checks]


def neg_arm() -> int:
    src = io.open(SETTINGS, encoding='utf-8', newline='').read()
    crlf = '\r\n' in src
    flat = src.replace('\r\n', '\n')
    shell_src = io.open(SHELL, encoding='utf-8', newline='').read()
    shell_crlf = '\r\n' in shell_src
    shell_flat = shell_src.replace('\r\n', '\n')

    mutants = [
        ('switch_never_reads_false', flat,
         ("    payload = _read_payload(path) or {}\n"
          "    return payload.get(PANELS_ENABLED_KEY) is not False\n"),
         ("    payload = _read_payload(path) or {}\n"
          "    return True\n"),
         ['disarm_reads_back_as_disarmed']),
        ('switch_write_drops_the_flag', flat,
         "        out = dict(result)\n        out[PANELS_ENABLED_KEY] = panels_enabled(path)\n",
         "        out = dict(result)\n",
         ['changing_a_key_keeps_the_switch_off']),
        ('set_panels_enabled_does_not_write', flat,
         "        panel_state.write_atomic(path or PATH, out)\n",
         "        pass\n",
         ['disarm_writes_false_to_disk']),
    ]
    caught = 0
    total = 0
    for name, src_text, before, after, must_fail in mutants:
        total += 1
        if before not in src_text:
            print(f'MUTANT NOT APPLICABLE {name}: anchor not found')
            continue
        path = os.path.join(SHELL_DIR, 'hotkey_settings__mutant.py')
        mutated = src_text.replace(before, after, 1)
        if crlf:
            mutated = mutated.replace('\n', '\r\n')
        io.open(path, 'w', encoding='utf-8', newline='').write(mutated)
        try:
            checks = {n: (n, o, d) for n, o, d in compact(judge(_settings(path)))}
        finally:
            sys.modules.pop('hotkey_settings_under_test', None)
            try:
                os.remove(path)
            except OSError:
                pass
        bad = [n for n in must_fail if not checks.get(n, (n, True, ''))[1]]
        ok = len(bad) == len(must_fail)
        caught += int(ok)
        print(f'MUTANT {name}: {"CAUGHT" if ok else "NOT-CAUGHT"} arms={must_fail} '
              f'detail={bad}')

    # the arming gate, mutated in the SHELL
    total += 1
    anchor = "    if panels:\n        panels_thread = arm_hotkey_role("
    if anchor not in shell_flat:
        print('MUTANT NOT APPLICABLE gate_ignored: anchor not found')
    else:
        path = os.path.join(SHELL_DIR, 'sotto_webview__mutant_switch.py')
        mutated = shell_flat.replace(anchor, "    if True:\n        panels_thread = arm_hotkey_role(", 1)
        if shell_crlf:
            mutated = mutated.replace('\n', '\r\n')
        io.open(path, 'w', encoding='utf-8', newline='').write(mutated)
        try:
            shell_mod = load(path, 'shell_under_test')
        finally:
            sys.modules.pop('shell_under_test', None)
            try:
                os.remove(path)
            except OSError:
                pass
        checks = {n: (n, o, d) for n, o, d in compact(judge_wiring(shell_mod))}
        bad = [n for n in ('startup_skips_panels_when_disarmed',)
               if not checks.get(n, (n, True, ''))[1]]
        ok = len(bad) == 1
        caught += int(ok)
        print(f'MUTANT gate_ignored: {"CAUGHT" if ok else "NOT-CAUGHT"} '
              f'arms={bad}')

    print(f'NEG-ARM SUMMARY cases={total} caught={caught}')
    print('NEG-ARM: PASS' if caught == total else 'NEG-ARM: FAIL')
    return 1 if caught == total else 0


def main() -> int:
    checks = compact(judge(_settings()))
    checks += compact(judge_wiring(load(SHELL, 'shell_under_test')))
    failed = [c for c in checks if not c[1]]
    for name, ok, detail in checks:
        print(f'ARM {"PASS" if ok else "FAIL"} {name} {detail}')
    print(f'CHECK arms={len(checks)} failed={len(failed)}')
    print('VERDICT: PASS' if not failed else 'VERDICT: FAIL')
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(neg_arm() if '--neg-arm' in sys.argv else main())
