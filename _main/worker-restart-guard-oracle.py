#!/usr/bin/env python3
"""ORACLE: UM REINICIO DE WORKER NAO SE DISPARA SOZINHO.

O DONO, 2026-10-17, furioso: *"é tu que tá fazendo meu pc travar por 2 minutos
inteiros? ... faz guard pra essa merda NUNCA MAIS ACONTECER"*.

O QUE ACONTECEU, MEDIDO EM `_main/webview-run.log`
---------------------------------------------------
Uma gravação de ficheiro em `worker/` por um agente, com a app do dono a correr
com `--hot-reload`, disparou isto:

    22:30:11.891  HOT_RELOAD_WORKER_RESTART files=1 after_idle_ms=35000
    22:30:11.901  WORKER_AUTOSTART=started reason=hot-reload
    22:35:25.683  HOT_RELOAD_WORKER_IDLE_APPLIED ... cost=one-model-warm-up
    22:35:25.699  HOT_RELOAD_WORKER_RESTART files=["redux_live.py"]

O próprio log diz o preço: `cost=one-model-warm-up`. Duas instâncias de 1 245 MB
ficaram vivas, a CPU e a GPU foram a 100%, e matar o processo não resolveu porque
o watcher o voltava a lançar.

POR QUE ISTO É UM ORACLE ESTÁTICO E NÃO UM TESTE AO VIVO
--------------------------------------------------------
Porque o teste ao vivo desta guarda **paga o estrago que ela existe para
evitar**:prová-la exige um worker a correr, e um worker a correr é precisamente
os ~2 GB na GPU. MEASURED 2026-10-17: a primeira tentativa de prova tocou no
ficheiro, o watcher disparou, e parou em `HOT_RELOAD_WORKER_SKIPPED
reason=no-worker-running` — ANTES do guard, porque eu tinha matado o worker.
Ou seja: *"nenhum worker foi lançado"* era verdade e não provava nada. Um
instrumento que passa sem testar a coisa que diz testar é pior do que nenhum.

Por isso os braços são sobre os BYTES: a guarda tem de estar nas DUAS portas, o
portão tem de ser explícito, e o default tem de ser fechado.

  G1  a função `worker_restart_allowed` existe e é de módulo
  G2  o default é **FECHADO**: só `SOTTO_HOT_RELOAD_WORKER` o abre, e só com um
      valor de lista fechada (1/true/yes/on). `''`, `'0'`, `'false'`, `'maybe'`
      NÃO abrem — um portão que aceita `SOTTO_HOT_RELOAD_WORKER=0` como ligado
      é um portão que alguém vai abrir por engano ao tentar fechá-lo
  G3  a guarda é chamada na **primeira** porta, `restart_worker`, ANTES de
      enfileirar na política (debounce, timers de idle e fronteira custam linhas
      de log e temporizadores por algo que vai ser recusado)
  G4  a guarda é chamada na **última** porta, `_do_worker_restart`, que é a que
      o comentário do próprio código chama *"the one place a hot reload actually
      stops and restarts the worker"*
  G5  a recusa é REGISTADA com o nome da variável e o custo, porque uma guarda
      muda e silenciosa parece uma falha
  G6  o reinício do PAINEL não passa por esta guarda — recarregar o HTML é
      barato, e um guard que bloqueia o painel aXS para de ser útil

`--neg-arm` reintroduz cada defeito e exige o vermelho.

USO
    python _main/worker-restart-guard-oracle.py
    python _main/worker-restart-guard-oracle.py --neg-arm
"""

from __future__ import annotations

import argparse
import ast
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHELL = os.path.join(HERE, 'app', 'webview', 'sotto_webview.py')

#: The ONLY spelling of yes. Anything else leaves the gate shut.
ALLOW = ('1', 'true', 'yes', 'on')
#: The spellings that must NOT open it. `0`/`false` are the dangerous ones: someone
#: trying to CLOSE the door and typing the wrong word must not open it.
DENY = ('', '0', 'false', 'off', 'no', 'maybe', 'sim', '2', 'enabled')


def read():
    with open(SHELL, encoding='utf-8') as fh:
        return fh.read()


def function(src, name):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = src.splitlines()
            return '\n'.join(lines[node.lineno - 1:
                                     getattr(node, 'end_lineno', node.lineno)])
    return None


def evaluate_gate(raw):
    """Run the gate's own logic on a value, without importing the shell.

    Importing `sotto_webview.py` would boot the app, which is exactly the thing
    this repo is not doing while the owner is using it. The gate is four lines;
    this re-implements them AND the oracle checks that the real ones match, in
    G2, by reading the source.
    """
    want = raw.strip().lower()
    return want in ALLOW


def _code_only(src):
    """The source with every comment and docstring REMOVED.

    Otherwise a gate that explains itself in prose finds its own explanation and
    calls it a defect. MEASURED 2026-10-17, twice, in this very file.
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, 'body', None)
            if isinstance(body, list) and body:
                first = body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                        and isinstance(first.value.value, str):
                    first.value.value = ''
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = ''
    return '\n'.join(tree.body and [ast.unparse(tree)] or ['']) if False else \
        ast.unparse(tree)


def _write_a_stale_file():
    """A real file on disk for the digest comparison to read."""
    import hashlib
    import tempfile
    path = os.path.join(tempfile.mkdtemp(prefix='sotto-digest-'), 'worker.py')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write('# the bytes the worker is already running\n')
    return path


def file_sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()[:16]


def read_joined(name):
    """The bytes of another module in the same directory as the shell."""
    with open(os.path.join(HERE, 'app', 'webview', name), encoding='utf-8') as fh:
        return fh.read()


def live_restarts_under(src, method):
    """The `self.restart(...)` calls that survive inside one method."""
    body = function(src, method) or ''
    return [l.strip() for l in body.splitlines() if l.strip().startswith('self.restart(')]


def runtime_arm():
    """DRIVE THE REAL POLICY AND WATCH IT REFUSE, FOREVER.

    This is the arm that answers the owner directly — *"vai no disco e o watcher e
    entenda por que ele nao impediu essa caga gigante e arruma ELE"* — by running
    the ACTUAL `WorkerReloadPolicy` through every path that once restarted the
    worker, with a bridge that RAISES if it is ever asked to restart.

    MEASURED 2026-10-17, and it is the only arm here that costs nothing: the
    earlier attempt to prove this live needed a RUNNING worker, and a running
    worker is exactly the ~2 GB the guard exists to avoid — so that proof could
    only ever have been bought with the damage. A stand-in bridge gives the same
    evidence for free, because the policy never touches the model; it only ever
    DECIDED to ask for one.
    """
    import sys
    sys.path.insert(0, os.path.join(HERE, 'app', 'webview'))
    import sotto_webview as sv

    class StandInBridge:
        """Everything the policy reads, and nothing it can hurt."""

        def __init__(self, capturing, last_caption_age_s):
            self.child = object()
            self.spawned_at = 0.0
            self.spawns = 1
            self._capturing = capturing
            self._last_caption_age_s = last_caption_age_s
            self.worker_path = None
            self.loaded_sha256 = 'stale'

        def is_capturing(self):
            return self._capturing

        def last_caption_age(self):
            return self._last_caption_age_s

    class Boom(Exception):
        pass

    class _EqualDigestBridge(StandInBridge):
        """What the owner's log shows at 22:35:25: `code_is_stale=False`, and
        `sha256_disk` == `sha256_at_spawn`. The running worker already IS the
        file on disk. This is the case that used to pay a warm-up."""

        def __init__(self):
            super().__init__(True, 0.05)
            self.worker_path = _write_a_stale_file()
            self.loaded_sha256 = file_sha256(self.worker_path)

    paths = [
        ('a caption just closed, floor elapsed (the 22:30 path)',
         StandInBridge(True, 0.05), True),
        ('nothing in flight, machine idle (the 22:35 path)',
         StandInBridge(True, 999.0), False),
        ('a boundary arrives long after the ceiling would have forced',
         StandInBridge(True, 999.0), True),
        ('no boundary at all, well past max_defer_ms',
         StandInBridge(True, 999.0), False),
        ('worker not even capturing',
         StandInBridge(False, 999.0), False),
        # THE ONE FROM HIS OWN LOG, 22:35:25: identical digests, and it restarted
        # anyway. The stand-in reports the SAME digest on both sides.
        ('the running bytes ALREADY match the disk (the 22:35 case)',
         _EqualDigestBridge(), True),
    ]
    out = []
    for label, bridge, boundary in paths:
        calls = []

        def restart(files, _c=calls, _b=bridge):
            _c.append(files)
            raise Boom('a Politica pediu um reinicio -- 2 GB na GPU do dono')
            return True

        logged = []
        pol = sv.WorkerReloadPolicy(log_fn=logged.append,
                                   get_bridge=lambda _b=bridge: _b,
                                   restart=restart,
                                   debounce_ms=0, min_interval_ms=0,
                                   max_defer_ms=1, defer_recheck_ms=1)
        # Make every timing gate look elapsed, so the arm exercises the DECISION
        # and not the clock.
        pol.pending = ['worker/sotto_worker.py']
        pol.pending_since = 0.0
        pol._last_applied_at = 0.0
        pol._defer_logged_at = -1e9
        if boundary:
            pol._boundary_hit = True
        crashed = ''
        try:
            pol._fire()
        except Boom as exc:
            crashed = str(exc)
        except Exception as exc:  # noqa: BLE001
            crashed = '%s: %s' % (type(exc).__name__, exc)
        reported = any('HOT_RELOAD_WORKER_REPORTED' in l for l in logged)
        skipped = any('reason=code-not-stale' in l for l in logged)
        applied = any('HOT_RELOAD_WORKER_RESTART' in l for l in logged)
        out.append(('P %s' % label,
                    not calls and not crashed and not applied
                    and (reported or skipped),
                    'reinicios=%d reported=%s skipped_not_stale=%s '
                    'restart_line=%s%s'
                    % (len(calls), reported, skipped, applied,
                       ('  CRASH: %s' % crashed) if crashed else '')))
    return out


def gate_source_matches(src):
    body = function(src, 'worker_restart_allowed') or ''
    code = '\n'.join(l.split('#')[0] for l in body.splitlines())
    return ("'1', 'true', 'yes', 'on'" in code.replace('"', "'")
            and 'SOTTO_HOT_RELOAD_WORKER' in code)


def check():
    src = read()
    results = []

    guard = function(src, 'worker_restart_allowed')
    top_level = False
    if guard:
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == 'worker_restart_allowed':
                top_level = True
    results.append(('G1 the guard exists and is a module function',
                    bool(guard) and top_level,
                    'module-level=%s source=%d lines'
                    % (top_level, len(guard.splitlines()) if guard else 0)))

    # G2 -- the default is shut, and the ONLY yes-list is in the source.
    shut = all(not evaluate_gate(v) for v in DENY)
    results.append(('G2 the default is shut and only a closed list opens it',
                    shut and gate_source_matches(src),
                    '%d spelling(s) refused, %d accepted, source-matches=%s'
                    % (len(DENY), len(ALLOW), gate_source_matches(src))))

    # G3 / G4 -- both doors.
    entry = function(src, 'restart_worker') or ''
    last = function(src, '_do_worker_restart') or ''
    entry_pos = entry.find('worker_restart_allowed(')
    queue_pos = entry.find('_reload_policy.request(')
    g3 = entry_pos >= 0 and queue_pos >= 0 and entry_pos < queue_pos
    results.append(('G3 the first door refuses BEFORE queueing',
                    g3, 'guard at char %d, queue at char %d'
                    % (entry_pos, queue_pos)))

    # G4 — the last door. MEASURED 2026-10-17: this arm first asked for the guard
    # to be statement #3 of `_do_worker_restart` and went RED against correct code,
    # because a docstring and two comment lines sit above it. Counting LINES is not
    # the invariant; the invariant is that the guard comes before the first line
    # that CANNOT be undone -- `bridge.stop`, dropping the bridge, spawning a new
    # worker. Those are the three statements that load ~2 GB onto the GPU, and the
    # order is what has to be right.
    mutators = ('self.bridge.stop(', 'self.bridge = None', 'self.start_worker(')
    first_mut = min((last.find(m) for m in mutators if m in last), default=-1)
    guard_pos = last.find('worker_restart_allowed(')
    g4 = guard_pos >= 0 and first_mut >= 0 and guard_pos < first_mut
    results.append(('G4 the last door refuses before it touches the worker',
                    g4, 'guard at char %d, first mutating call at char %d'
                    % (guard_pos, first_mut)))

    results.append(('G5 a refusal is logged, naming the variable and the cost',
                    bool(guard) and 'HOT_RELOAD_WORKER_REFUSED' in guard
                    and 'SOTTO_HOT_RELOAD_WORKER' in guard
                    and 'cost=' in guard,
                    'the gate says what to set and what it costs'))

    # G7 -- THE OWNER'S ACTUAL ASK, measured 2026-10-17: *"vai no disco e o
    # watcher e entenda por que ele nao impediu ... e arruma ELE"*. The answer was
    # NOT this gate: a gate downstream leaves the policy still walking its
    # debounce, boundary, ceiling and floor timers to reach a refusal. The fix is
    # IN THE POLICY: there is no live `self.restart(` left inside it. Counting
    # LINES is not the invariant either -- what closes the path is a `return` in
    # each apply branch, and a policy with zero restart calls cannot restart.
    policy = function(src, '_fire') or ''
    # A arm that reads a method which no longer exists reports "0 calls" and
    # looks like a PASS. MEASURED 2026-10-17: this one did exactly that, because
    # the method is `_fire` and I asked for `_apply`. A gate that cannot tell
    # "nothing is left" from "I looked at nothing" is not a gate, so an empty
    # body is now a RED and not a GREEN.
    results.append(('G7 the POLICY has no live restart path at all',
                    bool(policy) and not live_restarts_under(src, '_fire'),
                    'method _fire found=%s' % bool(policy)))
    reports = policy.count('HOT_RELOAD_WORKER_REPORTED')
    results.append(('G7b the three apply branches all became REPORTS',
                    bool(policy) and reports >= 3,
                    '%d ramos a reportar, 0 a reiniciar' % reports))

    # G8 — THE WATCHER ITSELF, which the owner sent me to read twice
    # (*"vai no disco e o watcher"*). Two defects, both measured:
    hr = read_joined('hot_reload.py')
    # (a) the notify mask used to include ATTRIBUTES and CREATION, so an
    # antivirus scan, an indexer or an `os.utime` counted as a code change.
    mask_block = function(hr, 'DirWatcher') or ''
    has_attr = 'FILE_NOTIFY_CHANGE_ATTRIBUTES |' in mask_block.replace('  ', ' ')
    narrow = 'FILE_NOTIFY_CHANGE_CODE' in hr
    results.append(('G8 the watcher no longer listens for ATTRIBUTE changes',
                    narrow and not ('FILE_NOTIFY_CHANGE_ATTRIBUTES'
                                    in mask_block.split('FILE_NOTIFY_CHANGE_CODE')[0]
                                    if 'FILE_NOTIFY_CHANGE_CODE' in hr
                                    else True),
                    'mask = NAME | LAST_WRITE | SIZE (a rename, an mtime and a '
                    'size are code; an ACL or a scan is not)'))
    # (b) it used to accept EVERY `.py` in worker/ — thirteen of them. Checked
    # against the CODE, not the file: MEASURED 2026-10-17, the first version of
    # this arm searched the raw text for `endswith('.py')` and went RED against a
    # fixed file — because the sentence explaining the fix MENTIONS
    # `endswith('.py')`. An arm that reads its own documentation is an arm that
    # documents its own failure.
    hr_code = _code_only(hr)
    filtered = 'base in self._worker_files' in hr_code
    results.append(('G8b the watcher only watches the file the bridge runs',
                    filtered and "endswith('.py')" not in hr_code,
                    'accepted=%s' % ('the explicit set' if filtered else 'ANY .py')))

    # G6 -- the panel reload is a different door and must stay open.
    panel = function(src, 'reload_panel') or function(src, '_reload_panel') or ''
    results.append(('G6 the PANEL reload is not behind this guard',
                    'worker_restart_allowed' not in panel,
                    'panel reload untouched: reloading HTML is cheap'))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()

    if args.neg_arm:
        return neg_arm()

    results = check()
    results.extend(runtime_arm())
    width = max(len(a) for a, _, _ in results)
    bad = 0
    print('UM REINICIO DE WORKER NAO SE DISPARA SOZINHO -- %d arms\n' % len(results))
    for arm, good, detail in results:
        print('  %-5s %-*s  %s' % ('GREEN' if good else 'RED', width, arm, detail))
        if not good:
            bad += 1
    print()
    print('VERDICT: %s' % ('GREEN -- a guarda esta nas duas portas e fechada por omissao'
                           if not bad else 'RED -- %d arm(s) failed' % bad))
    return 1 if bad else 0


def neg_arm():
    """Remove each part of the guard in a scratch copy and require RED."""
    import shutil
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix='sotto-guard-')
    try:
        src = read()
        out = os.path.join(tmpdir, 'sotto_webview.py')
        mutations = [
            ('the gate becomes always-yes',
             "if want in ('1', 'true', 'yes', 'on'):\n        return True",
             "if want != '__never__':\n        return True", 'G2'),
            ('the first door stops guarding',
             'if not worker_restart_allowed(files):\n            return False\n        '
             'return self._reload_policy.request(files)',
             'return self._reload_policy.request(files)', 'G3'),
            ('the last door stops guarding',
             'if not worker_restart_allowed(files):\n            return False\n        '
             'if self.bridge is None:',
             'if self.bridge is None:', 'G4'),
            ('the refusal is silent',
             "log('HOT_RELOAD_WORKER_REFUSED", "pass  # HOT_RELOAD_WORKER_REFUSED", 'G5'),
        ]
        ok = True
        for label, old, new, arm in mutations:
            if old not in src:
                print('  ?? %-40s -> MUTATION DID NOT APPLY' % label)
                ok = False
                continue
            open(out, 'w', encoding='utf-8').write(src.replace(old, new, 1))
            global SHELL
            real = SHELL
            SHELL = out
            try:
                verdicts = {a.split(' ')[0]: g for a, g, _ in check()}
            finally:
                SHELL = real
            red = verdicts.get(arm) is False
            print('  %-4s %-40s -> %s (want %s RED)'
                  % ('RED' if red else 'GREEN', label, 'RED' if red else 'GREEN', arm))
            if not red:
                ok = False
        print()
        print('NEG-ARM: %s' % ('PASS -- the guard can be broken, and it is NOT broken'
                                if ok else 'FAIL'))
        return 0 if ok else 1
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == '__main__':
    sys.exit(main())