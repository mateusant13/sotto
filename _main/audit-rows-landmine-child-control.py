# =============================================================================
# audit-rows-landmine-child-control.py -- ONE instrument for FOUR open register
# rows that are all the same Windows landmine: a parent that believes it
# controls a child it does not.
#
#   #5   console-census.py passes CREATE_NO_WINDOW|DETACHED_PROCESS -> a 0-byte
#        channel with rc 0, so python_pids() is blind
#   #34  wait(timeout=) with no handler in 3 oracles -> orphan child, handles
#        never closed
#   #35  run-live-hidden.py: the same, plus a DEAD DETACHED_PROCESS constant
#   #62  subprocess.run(timeout=) around the multi-process electron.exe may not
#        be a ceiling [INFERENCE]
#
# Two kinds of evidence, both measured HERE:
#   (1) BYTES -- what the named files contain today (the flag literal, the
#       missing TimeoutExpired handler, the dead constant, the call sites);
#   (2) MECHANISM -- the same failure reproduced in-process with harmless
#       pythonw.exe children: a console host under those exact creationflags,
#       and a two-level process tree put under wait(timeout=).
#
# NOTHING of the product is launched: no shell, no worker, no device, no
# electron. The children are pythonw sleepers and one powershell.exe
# process-table query, all with CREATE_NO_WINDOW so no console is ever shown,
# and every pid this instrument starts is killed before it returns.
#
# EVERY arm must FLIP on a MUTANT of its subject under %TEMP%.
#
# Usage:  py -3 _main/audit-rows-landmine-child-control.py [--neg-arm] [--verbose]
# =============================================================================
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
CENSUS = os.path.join(ROOT, '_main', '_probe', 'console-census.py')
RUN_HIDDEN = os.path.join(ROOT, '_main', 'run-live-hidden.py')
#: row #62's own subject: the electron launcher that wraps subprocess.run in a
#: timeout. Read ONLY -- running it would launch electron, which is forbidden.
RUN_ELECTRON = os.path.join(ROOT, '_main', '_run-hidden.py')
ORACLES = ('device-silence-oracle.py', 'panel-exit3-oracle.py',
           'panel-startup-visibility-oracle.py')
PS = r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008
PYW = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
if not os.path.exists(PYW):
    PYW = sys.executable

VERBOSE = False


def say(message):
    print(message, flush=True)


def sha256_file(path):
    with open(path, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest().upper()


def line_of(text, anchor):
    index = text.find(anchor)
    if index < 0:
        return 0
    return text.count('\n', 0, index) + 1


def read(path):
    with open(path, encoding='utf-8', newline='') as handle:
        return handle.read()


# ---------------------------------------------------------------------------
# mutants: a LIST of literal replacements, each anchored exactly once
# ---------------------------------------------------------------------------
MUTANTS = {
    # #5 -- THE MUTANT NOW GOES THE OTHER WAY (2026-10-11): the live census was FIXED
    # (DETACHED_PROCESS dropped, measured 0 rows -> 14 rows), so this mutant puts the flag
    # BACK and reproduces the blindness instead of simulating the cure.
    'm5-census-broken-flags': (CENSUS, [
        ('creationflags=0x08000000)',
         'creationflags=0x08000000 | 0x00000008)')]),
    # #34 -- the oracle kills the TREE it started when its ceiling expires.
    'm34-tree-kill-on-timeout': (os.path.join(ROOT, '_main',
                                              'panel-exit3-oracle.py'), [
        ('    rc = proc.wait(timeout=400)\n',
         '    try:\n'
         '        rc = proc.wait(timeout=400)\n'
         '    except subprocess.TimeoutExpired:\n'
         '        subprocess.run(["taskkill", "/F", "/T", "/PID",\n'
         '                        str(proc.pid)], capture_output=True,\n'
         '                       creationflags=0x08000000)\n'
         '        raise\n')]),
    # #62 -- the electron launcher gains a handler that kills the TREE. Two
    # literal replacements: the call is wrapped, and the handler is inserted
    # before the first use of p. Inside the parentheses the continuation lines
    # keep their indentation, so the mutant stays valid Python.
    'm62-electron-tree-kill': (RUN_ELECTRON, [
        ('    p = subprocess.run(\n'
         '        cmd,\n',
         '    try:\n'
         '        p = subprocess.run(\n'
         '        cmd,\n'),
        ('    sys.stdout.write(p.stdout)\n',
         '    except subprocess.TimeoutExpired:\n'
         '        subprocess.run(["taskkill", "/F", "/T", "/PID", str(0)],\n'
         '                       capture_output=True, creationflags=FLAGS)\n'
         '        raise\n'
         '    sys.stdout.write(p.stdout)\n')]),
    # #35 -- run-live-hidden.py loses the dead constant and gains the handler.
    'm35-constant-removed-handler-added': (RUN_HIDDEN, [
        ('DETACHED_PROCESS = 0x00000008\n', ''),
        ('    rc = proc.wait(timeout=300)\n',
         '    try:\n'
         '        rc = proc.wait(timeout=300)\n'
         '    except subprocess.TimeoutExpired:\n'
         '        subprocess.run(["taskkill", "/F", "/T", "/PID",\n'
         '                        str(proc.pid)], capture_output=True,\n'
         '                       creationflags=0x08000000)\n'
         '        rc = None\n')]),
}


def make_mutant(key, directory):
    """Write the mutant copy. Returns (path, [replacement descriptions])."""
    subject, replacements = MUTANTS[key]
    source = read(subject)
    newline = '\r\n' if '\r\n' in source else '\n'
    notes = []
    for old, new in replacements:
        old_n = old.replace('\n', newline)
        new_n = new.replace('\n', newline)
        count = source.count(old_n)
        if count != 1:
            say('SETUP ERROR: an anchor of ' + key + ' appears ' + str(count)
                + ' time(s) in ' + subject + ' (wanted exactly 1)')
            raise SystemExit(2)
        source = source.replace(old_n, new_n, 1)
        notes.append(str(len(old_n)) + ' B -> ' + str(len(new_n)) + ' B')
    path = os.path.join(directory, key + '__' + os.path.basename(subject))
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(source)
    return path, notes


# ---------------------------------------------------------------------------
# bytes half
# ---------------------------------------------------------------------------
def flag_expression(text):
    """The creationflags expression python_pids() passes, evaluated."""
    marker = 'creationflags='
    index = text.find(marker, text.find('def python_pids'))
    if index < 0:
        return None, ''
    end = text.find(')', index)
    expression = text[index + len(marker):end].strip()
    value = eval(expression, {'__builtins__': {}},          # noqa: S307
                 {'CREATE_NO_WINDOW': CREATE_NO_WINDOW,
                  'DETACHED_PROCESS': DETACHED_PROCESS})
    return int(value), expression


def timeout_census(path):
    text = read(path)
    sites = []
    for pattern in ('.wait(timeout=', 'subprocess.run(', 'timeout='):
        start = 0
        while True:
            index = text.find(pattern, start)
            if index < 0:
                break
            line = text.count('\n', 0, index) + 1
            sites.append({'line': line, 'pattern': pattern,
                          'text': text.split('\n')[line - 1].strip()[:78]})
            start = index + 1
    return {'timeout_expired_handlers': text.count('TimeoutExpired'),
            'wait_timeout_sites': [entry for entry in sites
                                   if entry['pattern'] == '.wait(timeout='],
            'timeout_sites': len([e for e in sites if e['pattern'] == 'timeout='])}


# ---------------------------------------------------------------------------
# mechanism half -- real, harmless children
# ---------------------------------------------------------------------------
def alive(pid):
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                     wintypes.DWORD]
    handle = kernel32.OpenProcess(0x1000, False, int(pid))
    if not handle:
        return False
    code = wintypes.DWORD()
    ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
    kernel32.CloseHandle(handle)
    return bool(ok) and code.value == 259      # STILL_ACTIVE


def kill_tree(pid):
    if pid:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)],
                       capture_output=True, creationflags=CREATE_NO_WINDOW)


def console_channel(flags, label):
    """Run the census own powershell query under flags, count the bytes."""
    script = ('Get-CimInstance Win32_Process | '
              'Where-Object { $_.Name -match ' + repr('^(python|pythonw)[.]exe$')
              + ' } | ForEach-Object { "$($_.ProcessId)|$($_.Name)|'
              '$($_.CommandLine)" }')
    out = subprocess.run([PS, '-NoProfile', '-NonInteractive', '-Command',
                          script], capture_output=True, text=True,
                         creationflags=flags, timeout=180)
    rows = [line for line in out.stdout.splitlines() if line.strip()]
    return {'label': label, 'flags': hex(flags), 'rc': out.returncode,
            'stdout_bytes': len(out.stdout.encode('utf-8', 'replace')),
            'stderr_bytes': len(out.stderr.encode('utf-8', 'replace')),
            'rows': len(rows)}


def tree_under_timeout(handle_timeout):
    """A 2-level tree under wait(timeout=2). What survived, and where."""
    marker = os.path.join(tempfile.gettempdir(),
                          'sotto-audit-row34-grandchild-%d.txt' % os.getpid())
    if os.path.exists(marker):
        os.remove(marker)
    grand = 'import time; time.sleep(90)'
    child = ('import subprocess, sys, time\n'
             'p = subprocess.Popen([%r, "-c", %r], stdin=subprocess.DEVNULL,\n'
             '                     stdout=subprocess.DEVNULL, '
             'stderr=subprocess.DEVNULL)\n'
             'open(%r, "w").write(str(p.pid))\n'
             'time.sleep(90)\n' % (PYW, grand, marker))
    proc = subprocess.Popen([PYW, '-c', child], stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=CREATE_NO_WINDOW)
    grandchild = None
    deadline = time.time() + 20
    while time.time() < deadline:
        if os.path.exists(marker):
            try:
                grandchild = int(read(marker).strip())
                break
            except ValueError:
                pass
        time.sleep(0.2)
    expired = False
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        expired = True
        if handle_timeout:
            kill_tree(proc.pid)
        else:
            proc.kill()
            proc.wait(timeout=10)
    time.sleep(0.6)
    result = {
        'grandchild_pid': grandchild,
        'timeout_expired': expired,
        'direct_child_alive_after_timeout': alive(proc.pid),
        'grandchild_alive_after_timeout': bool(grandchild) and alive(grandchild),
        'handler': 'taskkill /F /T on the child' if handle_timeout
                   else 'none (Popen.kill of the direct child only)',
    }
    if grandchild and alive(grandchild):
        kill_tree(grandchild)
        time.sleep(0.4)
        result['grandchild_alive_after_cleanup'] = alive(grandchild)
    else:
        result['grandchild_alive_after_cleanup'] = False
    if os.path.exists(marker):
        os.remove(marker)
    return result


def mechanism():
    """Measured ONCE per process; every arm and every colour reads these."""
    live_flags, live_expression = flag_expression(read(CENSUS))
    directory = tempfile.mkdtemp(prefix='sotto-audit-landmine-probe-')
    mutant_path, _notes = make_mutant('m5-census-broken-flags', directory)
    mutant_flags, mutant_expression = flag_expression(read(mutant_path))
    return {
        'census_flags_expression': live_expression,
        'census_flags_value': hex(live_flags) if live_flags else None,
        'mutant_flags_expression': mutant_expression,
        'channel_live_flags': console_channel(live_flags, 'file flags'),
        'channel_mutant_flags': console_channel(mutant_flags, 'mutant flags'),
        'channel_create_no_window': console_channel(CREATE_NO_WINDOW,
                                                    'CREATE_NO_WINDOW alone'),
        'timeout_no_handler': tree_under_timeout(False),
        'timeout_with_tree_kill': tree_under_timeout(True),
    }


# ---------------------------------------------------------------------------
# arms -- each reads the context: {'census', 'run_hidden', 'mechanism'}
# ---------------------------------------------------------------------------
def arm_r5(ctx):
    flags, expression = flag_expression(read(ctx['census']))
    channel = (ctx['mechanism']['channel_live_flags']
               if ctx['census'] == CENSUS
               else ctx['mechanism']['channel_mutant_flags'])
    return {
        'file': ctx['census'],
        'flag_expression': expression,
        'flag_value': hex(flags) if flags else None,
        'flag_line': (line_of(read(ctx['census']),
                              'creationflags=' + expression + ')')
                      if expression else 0),
        'channel_under_file_flags': channel,
        'channel_under_create_no_window':
            ctx['mechanism']['channel_create_no_window'],
        'blind_channel': bool(channel['stdout_bytes'] == 0
                              and channel['rc'] == 0),
    }


def arm_r34(ctx):
    per_file = {}
    for name in ORACLES:
        path = ctx['oracles'].get(name, os.path.join(ROOT, '_main', name))
        entry = timeout_census(path)
        entry['file'] = path
        entry['unhandled_wait'] = bool(
            entry['wait_timeout_sites']
            and entry['timeout_expired_handlers'] == 0)
        per_file[name] = entry
    mechanism_no_handler = ctx['mechanism']['timeout_no_handler']
    cured = ctx['mechanism']['timeout_with_tree_kill']
    return {
        'per_file': per_file,
        'handlers_total': sum(e['timeout_expired_handlers']
                              for e in per_file.values()),
        'timeout_no_handler': mechanism_no_handler,
        'timeout_with_tree_kill': cured,
        'orphan_possible': bool(mechanism_no_handler['timeout_expired']
                                and not mechanism_no_handler[
                                    'direct_child_alive_after_timeout']
                                and mechanism_no_handler[
                                    'grandchild_alive_after_timeout']),
        'all_wait_sites_unhandled': all(e['unhandled_wait']
                                         for e in per_file.values()
                                         if e['wait_timeout_sites']),
    }


def arm_r35(ctx):
    text = read(ctx['run_hidden'])
    return {
        'file': ctx['run_hidden'],
        'detached_process_occurrences': text.count('DETACHED_PROCESS'),
        'detached_process_line': line_of(text, 'DETACHED_PROCESS'),
        'timeout_expired_handlers': text.count('TimeoutExpired'),
        'wait_timeout_line': line_of(text, '.wait(timeout='),
        'creationflags_line': line_of(text, 'creationflags='),
        'dead_constant_and_unhandled': bool(
            text.count('DETACHED_PROCESS') == 1
            and text.count('TimeoutExpired') == 0),
    }


def arm_r62(ctx):
    text = read(ctx['run_electron'])
    mechanism_no_handler = ctx['mechanism']['timeout_no_handler']
    cured = ctx['mechanism']['timeout_with_tree_kill']
    confirmed = bool(mechanism_no_handler['grandchild_alive_after_timeout']
                     and not cured['grandchild_alive_after_timeout'])
    return {
        'file': ctx['run_electron'],
        'subprocess_run_timeout_used': ('subprocess.run(' in text
                                        and 'timeout=' in text),
        'mechanism_no_handler': mechanism_no_handler,
        'mechanism_tree_kill': cured,
        'mechanism_confirmed': confirmed,
        'electron_instantiation_measured': False,
        'electron_gap': ('launching electron.exe (or the shell) is forbidden by '
                         'the owner order of 2026-10-11 AND the binary is '
                         'declared DEAD (AGENTS.md corrections 2), so the TREE '
                         'SHAPE of electron is measured nowhere here'),
        'mechanism_confirmed_unhandled': bool(
            confirmed and text.count('TimeoutExpired') == 0),
    }


ARMS = ('r5', 'r34', 'r35', 'r62')
MEASURE = {'r5': arm_r5, 'r34': arm_r34, 'r35': arm_r35, 'r62': arm_r62}
DEFECT_KEY = {'r5': 'blind_channel',
              'r34': 'orphan_possible_and_all_unhandled',
              'r35': 'dead_constant_and_unhandled',
              'r62': 'mechanism_confirmed_unhandled'}
ROW_OF = {
    'r5': 'audit #5 (windows-landmines.md F1): console-census.py passes '
          'CREATE_NO_WINDOW|DETACHED_PROCESS -> 0 bytes rc 0, python_pids() blind',
    'r34': 'audit #34 (windows-landmines.md F2): wait(timeout=) with no handler '
           'in 3 oracles -> orphan child',
    'r35': 'audit #35 (windows-landmines.md F3): run-live-hidden.py '
           'wait(timeout=) unhandled + a DEAD DETACHED_PROCESS constant',
    'r62': 'audit #62 (windows-landmines.md F4): subprocess.run(timeout=) around '
           'the multi-process electron.exe may not be a ceiling [INFERENCE]',
}
#: THE LIVE VALUES, in one place: derived r5 -> False on 2026-10-11, when the census
#: flags were fixed in the probe (measured: 0x08000000 alone -> 14 pid rows, 0x08000008
#: -> 0 rows with rc 0). Every other arm keeps the defect the sweep measured.
LIVE_DEFECT = {'r5': False, 'r34': True, 'r35': True, 'r62': True}

#: arm -> (the mutant that must flip it, its value under that mutant)
MUTANT_OF = {'r5': ('m5-census-broken-flags', True),
             'r34': ('m34-tree-kill-on-timeout', False),
             'r35': ('m35-constant-removed-handler-added', False),
             'r62': ('m62-electron-tree-kill', False)}
MUTANT_ORDER = ('m5-census-broken-flags', 'm34-tree-kill-on-timeout',
                'm35-constant-removed-handler-added', 'm62-electron-tree-kill')

MECHANISM = {}


def context_for(mutant_key, directory):
    paths = {'census': CENSUS, 'run_hidden': RUN_HIDDEN,
             'run_electron': RUN_ELECTRON,
             'oracles': {name: os.path.join(ROOT, '_main', name)
                         for name in ORACLES}}
    paths['notes'] = {}
    if mutant_key:
        subject, _replacements = MUTANTS[mutant_key]
        path, note_list = make_mutant(mutant_key, directory)
        paths['notes'] = {'replacements': note_list, 'wrote': path}
        # Each subject has its OWN slot: mutating one file must never move
        # another arm's subject.
        if subject == CENSUS:
            paths['census'] = path
        elif subject == RUN_ELECTRON:
            paths['run_electron'] = path
        elif subject == RUN_HIDDEN:
            paths['run_hidden'] = path
        else:
            base = os.path.basename(path)
            for name in list(paths['oracles']):
                if base.endswith(name):
                    paths['oracles'][name] = path
    paths['mechanism'] = MECHANISM
    return paths


def run_all(ctx):
    results = {}
    for name in ARMS:
        try:
            results[name] = MEASURE[name](ctx)
        except Exception as exc:  # noqa: BLE001
            results[name] = {'ERROR': type(exc).__name__ + ': ' + str(exc)}
    r34 = results.get('r34') or {}
    if 'ERROR' not in r34:
        r34['orphan_possible_and_all_unhandled'] = bool(
            r34.get('orphan_possible') and r34.get('all_wait_sites_unhandled'))
    return results


def report(label, results, expected):
    say('')
    say('== ' + label)
    matched = True
    for name in ARMS:
        got = results[name]
        defect = got.get(DEFECT_KEY[name])
        defect = defect if isinstance(defect, bool) else None
        ok = (defect is expected[name])
        matched = matched and ok
        wanted = 'DEFECT-PRESENT' if expected[name] else 'DEFECT-REFUTED'
        seen = 'DEFECT-PRESENT' if defect else 'DEFECT-REFUTED'
        say('  ARM ' + name + '  ' + seen.ljust(15) + ' want=' + wanted.ljust(15)
            + ('OK' if ok else 'WRONG COLOUR') + '  ' + ROW_OF[name])
        if name == 'r34':
            slim = {k: v for k, v in got.items() if k != 'per_file'}
            say('      measured: ' + json.dumps(slim, default=str))
            say('      files   : ' + json.dumps(got.get('per_file'), default=str))
        else:
            say('      measured: ' + json.dumps(got, default=str))
    return matched


def main(argv=None):
    global VERBOSE, MECHANISM
    parser = argparse.ArgumentParser(
        description='Four open audit rows that are all a parent that does not '
                    'control its child: measured on the bytes AND reproduced '
                    'in-process with harmless children.')
    parser.add_argument('--neg-arm', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    parsed = parser.parse_args(argv)
    VERBOSE = parsed.verbose

    say('audit-rows-landmine-child-control -- four open rows, one instrument')
    say('subjects   : ' + CENSUS)
    say('             ' + RUN_HIDDEN)
    for name in ORACLES:
        say('             ' + os.path.join(ROOT, '_main', name))
    say('launches   : NOTHING of the product (no shell, no worker, no device, '
        'no electron). Children are pythonw sleepers and one powershell.exe '
        'process-table query, all CREATE_NO_WINDOW, all killed before exit.')
    say('             ' + RUN_ELECTRON + '  (row #62 subject, read only)')
    say('bytes      : census ' + str(os.path.getsize(CENSUS)) + ' B sha256 '
        + sha256_file(CENSUS)[:16] + ' | run-live-hidden '
        + str(os.path.getsize(RUN_HIDDEN)) + ' B sha256 '
        + sha256_file(RUN_HIDDEN)[:16])
    say('note       : the powershell filter is written with the character class '
        '[.] instead of a backslash escape, so this instrument source carries '
        'no nested-quote trap; the predicate is the same one the census builds')

    MECHANISM = mechanism()
    say('')
    say('mechanism (measured with harmless children, this box, this run):')
    for key in ('channel_live_flags', 'channel_mutant_flags',
                'channel_create_no_window', 'timeout_no_handler',
                'timeout_with_tree_kill'):
        say('  ' + key.ljust(24) + ': '
            + json.dumps(MECHANISM[key], default=str))
    say('  census flags expression : ' + MECHANISM['census_flags_expression']
        + ' (= ' + str(MECHANISM['census_flags_value']) + ')')

    directory = tempfile.mkdtemp(prefix='sotto-audit-landmine-mutants-')
    say('')
    say('mutants    : ' + directory)
    for key in MUTANT_ORDER:
        subject, replacements = MUTANTS[key]
        path, notes = make_mutant(key, directory)
        say('  ' + os.path.basename(path).ljust(54) + ' '
            + str(os.path.getsize(path)) + ' B sha256 '
            + sha256_file(path)[:16] + '  (' + str(len(replacements))
            + ' literal replacement(s), subject ' + os.path.basename(subject)
            + ')')

    verdicts = []
    live_present = []
    live_measured = False
    if not parsed.neg_arm:
        results = run_all(context_for(None, directory))
        live_measured = True
        # RECORDED, not asserted: the closing line used to say "4/4 landmines
        # reproduced" as a FIXED string and went stale the day r5 was fixed (2026-10-11).
        live_present = [name for name in ARMS
                        if results[name].get(DEFECT_KEY[name]) is True]
        expected = {name: LIVE_DEFECT[name] for name in ARMS}
        ok = report('LIVE -- every arm must read what the ARM declares',
                    results, expected)
        verdicts.append(('live', ok))

    for key in MUTANT_ORDER:
        results = run_all(context_for(key, directory))
        expected = {name: (MUTANT_OF[name][1] if MUTANT_OF[name][0] == key
                           else LIVE_DEFECT[name]) for name in ARMS}
        ok = report('MUTANT ' + key + ' -- its own arm(s) must FLIP',
                    results, expected)
        verdicts.append((key, ok))

    say('')
    failed = [label for label, ok in verdicts if not ok]
    if failed:
        say('VERDICT: FAIL  (' + str(len(verdicts) - len(failed)) + '/'
            + str(len(verdicts)) + ' labels matched; wrong: ' + str(failed) + ')')
        return 1
    if not live_measured:
        live_text = ('live NOT probed in this mode (--neg-arm), so no live set is '
                     'claimed')
    elif live_present:
        live_text = (str(len(live_present)) + ' of ' + str(len(ARMS))
                     + ' landmines still reproduced on this box ('
                     + ', '.join(live_present) + '); the rest are FIXED')
    else:
        live_text = 'all ' + str(len(ARMS)) + ' landmines FIXED on this box'
    say('VERDICT: PASS  live: ' + live_text + '; ' + str(len(MUTANT_ORDER)) + '/'
        + str(len(MUTANT_ORDER)) + ' mutants flipped their own arm(s)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
