"""Throwaway check: what command would `reveal_in_folder` SPAWN, without spawning.

Monkeypatches subprocess.Popen in the imported shell module, then calls the
REAL `SottoShell.reveal_in_folder` for the three cases. Nothing is opened.
"""
import importlib.util
import os
import subprocess
import sys
import types

SHELL = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'app', 'webview', 'sotto_webview.py')
sys.path.insert(0, os.path.dirname(os.path.abspath(SHELL)))
spec = importlib.util.spec_from_file_location('sotto_webview', SHELL)
mod = importlib.util.module_from_spec(spec)
sys.modules['sotto_webview'] = mod
spec.loader.exec_module(mod)

captured = []


def fake_popen(command, **kwargs):
    captured.append({'command': command, 'creationflags': kwargs.get('creationflags')})
    return types.SimpleNamespace()


mod.subprocess.Popen = fake_popen
shell = mod.SottoShell(types.SimpleNamespace())

root = mod.HISTORY_ROOT
real_file = None
for day, hour, path in mod.SottoShell._history_files(shell):
    real_file = path
if real_file is None:
    print('NO-HISTORY-FILE — cannot test the /select case')
    sys.exit(2)

results = {
    'root': shell.reveal_in_folder(None),
    'file': shell.reveal_in_folder(real_file),
    'outside': shell.reveal_in_folder(os.path.join(root, os.pardir, 'sotto_webview.py')),
    'missing': shell.reveal_in_folder(os.path.join(root, '1999-01-01', '00.md')),
}
print('RETURNS', results)
print('SPAWNS', len(captured))
for c in captured:
    print('CMD', repr(c['command']), 'CREATE_NO_WINDOW', c['creationflags'] == 0x08000000)

ok = (
    results['root'] is True and results['file'] is True
    and results['outside'] is False and results['missing'] is False
    and len(captured) == 2
    and captured[0]['command'] == f'explorer "{os.path.normpath(os.path.abspath(root))}"'
    and captured[1]['command'] == f'explorer /select,"{os.path.normpath(os.path.abspath(real_file))}"'
    and all(c['creationflags'] == 0x08000000 for c in captured)
)
print('REVEAL_CHECK=' + ('GREEN' if ok else 'RED'))
sys.exit(0 if ok else 3)
