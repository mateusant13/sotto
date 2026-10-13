"""Test the REAL _open_log rotation, in process, without launching the shell."""
import importlib.util
import os
import sys

ROOT = r'H:/sotto'
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
TMP = r'I:/cc-tmp/rot-test.log'

sys.path.insert(0, os.path.dirname(SHELL))
spec = importlib.util.spec_from_file_location('swrot', SHELL)
mod = importlib.util.module_from_spec(spec)
sys.modules["swrot"] = mod
try:
    spec.loader.exec_module(mod)
except Exception as e:
    print('IMPORT FALHOU: ' + repr(e)[:200])
    raise SystemExit(2)
print('import ok')

# a 3 MB file, cap 1 MB, keep 1 MB -> must rotate
if os.path.exists(TMP):
    os.remove(TMP)
line = (b"x" * 99) + b"\n"
with open(TMP, "wb") as fh:
    for i in range(30000):
        fh.write(line)
before = os.path.getsize(TMP)
print('antes: %d B' % before)

os.environ["SOTTO_LOG_CAP_MB"] = "1"
os.environ["SOTTO_LOG_KEEP_MB"] = "1"
mod._open_log(TMP)
after = os.path.getsize(TMP)
print('depois: %d B' % after)
rotated = after < before
print('ROTOU: ' + str(rotated))
with open(TMP, "rb") as fh:
    head = fh.read(80)
print('primeiros bytes: ' + repr(head[:40]))
print('primeira linha inteira (sem fragmento): ' + str(head.startswith(b'x' * 99 + b'\n') or head.startswith(b'sotto: LOG_ROTATED')))
if mod._LOG_FILE:
    mod._LOG_FILE.close()
print('VERDICT: ' + ('PASS' if rotated else 'FAIL'))