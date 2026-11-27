"""The REAL `_open_log` rotation, in process, in both directions.

What it refuses
---------------
1. A log that GROWS past its cap because the rotation silently did nothing
   (the whole point of the cap: measured 2026-10-13, `webview-run.log`
   reached 727.5 MB and reading it to check the shell blew a 300 s deadline).
2. A rotation FAILURE that leaves no trace. Swallowed as `except: pass`, the
   log keeps growing with nothing on disk naming the reason, and the volume
   the owner's data lives on is what fills -- a silent, unbounded resource.
   The failure must be COUNTED (`LOG_ROTATE_FAILURES`) and MARKED
   (`LOG_ROTATE_FAILED`) by the handle the app opens anyway.
3. A kept file that starts mid-line.

`--neg-arm` mutation-tests the oracle itself: two broken copies of the REAL
function must each turn this oracle RED, or the arms above are decoration.

rc law: arms all green -> 0. `--neg-arm`: every mutant caught -> 1 (a mutant
that stays green -> 0, because then the oracle cannot say no).

Nothing here launches the shell, opens a window or touches an audio device.
"""
import importlib.util
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
TMPDIR = os.environ.get('SOTTO_TMP_DIR') or tempfile.mkdtemp(prefix='sotto-rot-')
#: the shell imports its own siblings by bare name (`hot_reload`), so its own
#: directory has to be importable before it is exec'd -- the fallback clause the
#: other oracles in this tree already carry.
sys.path.insert(0, os.path.dirname(SHELL))

_LINE = (b'x' * 99) + b'\n'

MUTANTS = (
    # name, old, new, the arm that must go RED
    ('silent-except',
     '        except Exception as exc:  # noqa: BLE001 -- counted below, never fatal\r\n'
     '            rotate_failed = exc\r\n',
     '        except Exception:  # noqa: BLE001\r\n'
     '            pass\r\n',
     'a-failure-is-counted-and-marked'),
    ('mid-line-keep',
     "                cut = tail.find(b'\\n')\r\n"
     '                if 0 <= cut < len(tail) - 1:\r\n'
     '                    tail = tail[cut + 1:]\r\n',
     '',
     'rotation-keeps-whole-lines'),
)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def build(mod):
    """3 MB of whole lines, cap 1 MB, keep 1 MB -- it has to rotate."""
    path = os.path.join(TMPDIR, 'rot-%s.log' % mod.__name__)
    for p in (path, path + '.1'):
        if os.path.exists(p):
            os.remove(p)
    with open(path, 'wb') as fh:
        for _ in range(30000):
            fh.write(_LINE)
    return path


def arm_rotates(mod):
    problems = []
    path = build(mod)
    before = os.path.getsize(path)
    os.environ['SOTTO_LOG_CAP_MB'] = '1'
    os.environ['SOTTO_LOG_KEEP_MB'] = '1'
    mod._LOG_FILE = None
    try:
        mod._open_log(path)
        after = os.path.getsize(path)
        if after >= before:
            problems.append('the log did not rotate: %d B -> %d B' % (before, after))
        with open(path, 'rb') as fh:
            body = fh.read()
        # THE MARKER IS APPENDED, so it lives at the TAIL -- the kept content
        # is what the reader opens first. Asserting it at the head would be an
        # oracle that cannot pass on correct code (measured 2026-11-27).
        if b'sotto: LOG_ROTATED' not in body:
            problems.append('no LOG_ROTATED marker anywhere in the rotated log')
    finally:
        if mod._LOG_FILE is not None:
            mod._LOG_FILE.close()
            mod._LOG_FILE = None
    return problems


def arm_keeps_whole_lines(mod):
    problems = []
    path = build(mod)
    os.environ['SOTTO_LOG_CAP_MB'] = '1'
    os.environ['SOTTO_LOG_KEEP_MB'] = '1'
    mod._LOG_FILE = None
    try:
        mod._open_log(path)
        with open(path, 'rb') as fh:
            first = fh.readline()
        if first != _LINE:
            problems.append('the kept file starts mid-line: %r' % first[:40])
    finally:
        if mod._LOG_FILE is not None:
            mod._LOG_FILE.close()
            mod._LOG_FILE = None
    return problems


def arm_failure_is_counted_and_marked(mod):
    """A rotation that CANNOT happen: `<log>.1` is a directory.

    That is a genuine failure of the real code path -- nothing here patches
    `os` or the function under test.
    """
    problems = []
    path = build(mod)
    blocker = path + '.1'
    os.makedirs(blocker, exist_ok=True)
    os.environ['SOTTO_LOG_CAP_MB'] = '1'
    os.environ['SOTTO_LOG_KEEP_MB'] = '1'
    mod._LOG_FILE = None
    before = int(getattr(mod, '_LOG_ROTATE_FAILURES', 0))
    try:
        mod._open_log(path)
        if not os.path.exists(path):
            problems.append('the append handle was not opened after a failed rotation')
        else:
            with open(path, 'rb') as fh:
                body = fh.read()
            if b'LOG_ROTATE_FAILED' not in body:
                problems.append('a failed rotation left NO marker: the log is now '
                                'growing past its cap silently')
        after = int(getattr(mod, '_LOG_ROTATE_FAILURES', 0))
        if after != before + 1:
            problems.append('a failed rotation was not counted: %d -> %d'
                            % (before, after))
    finally:
        if mod._LOG_FILE is not None:
            mod._LOG_FILE.close()
            mod._LOG_FILE = None
        shutil.rmtree(blocker, ignore_errors=True)
    return problems


ARMS = (
    ('rotation-keeps-whole-lines', 'a 3 MB log past a 1 MB cap keeps whole lines', arm_keeps_whole_lines),
    ('rotation-happens', 'the file shrinks and carries LOG_ROTATED', arm_rotates),
    ('a-failure-is-counted-and-marked', 'a rotation that cannot happen is counted and named', arm_failure_is_counted_and_marked),
)


def run_arms(mod, tag):
    failures = []
    done = []
    for name, what, fn in ARMS:
        try:
            problems = fn(mod)
        except Exception as exc:  # noqa: BLE001 -- a setup error is not a RED
            problems = ['the arm could not run: %r' % (exc,)]
        if problems:
            failures.append('%s %s' % (tag, name))
            print('   FAIL %-32s %s' % (name, what))
            for p in problems:
                print('        ' + p)
        else:
            done.append(name)
            print('   PASS %-32s %s' % (name, what))
    return done, failures


def neg_arm(shell_text):
    caught = 0
    for name, old, new, victim in MUTANTS:
        if shell_text.count(old) != 1:
            print('   SETUP-ERROR %-20s anchor count=%d (the mutant cannot be '
                  'built -- NOT counted as caught)' % (name, shell_text.count(old)))
            continue
        path = os.path.join(TMPDIR, 'mut-%s.py' % name)
        with open(path, 'wb') as fh:
            fh.write(shell_text.replace(old, new).encode('utf-8'))
        try:
            mod = load(path, 'swrot_mut_%s' % name.replace('-', '_'))
        except Exception as exc:  # noqa: BLE001
            print('   SETUP-ERROR %-20s the broken copy did not import: %r' % (name, exc))
            continue
        try:
            red = bool(arm_failure_is_counted_and_marked(mod)) if victim == 'a-failure-is-counted-and-marked' \
                else bool(arm_keeps_whole_lines(mod))
        finally:
            if mod._LOG_FILE is not None:
                try:
                    mod._LOG_FILE.close()
                except Exception:
                    pass
                mod._LOG_FILE = None
            os.remove(path)
        if red:
            caught += 1
            print('   RED   %-20s %s -> %s' % (name, victim, 'caught'))
        else:
            print('   GREEN %-20s %s stayed green -- the oracle cannot say no'
                  % (name, victim))
    print('MUTANTS: %d/%d caught' % (caught, len(MUTANTS)))
    return caught == len(MUTANTS)


def main(argv):
    neg = '--neg-arm' in argv
    try:
        mod = load(SHELL, 'swrot')
    except Exception as exc:  # noqa: BLE001
        print('IMPORT FALHOU: %r' % (exc,))
        return 2
    if neg:
        with open(SHELL, 'rb') as fh:
            shell_text = fh.read().decode('utf-8')
        ok = neg_arm(shell_text)
        print('NEG-ARM: ' + ('PASS' if ok else 'FAIL'))
        return 1 if ok else 0
    _done, failures = run_arms(mod, 'REAL')
    print('VERDICT: ' + ('FAIL' if failures else 'PASS'))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
