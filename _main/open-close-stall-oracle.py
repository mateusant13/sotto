"""THE OPEN/CLOSE STALL GATE (owner, 2026-10-21, the twentieth time).

The owner, verbatim: *"eu, de novo, pela vigesima vez, vou mandar tu resolver
os travamentos que acontecem quando fechamos o sotto ou abrimos o sotto"*.

WHAT THIS GATE JUDGES IS FILES, so it belongs in the battery. It does NOT
launch the app, the worker, a WebView2 or a window: it reads the two sources
that carry the open/close path and asserts the FIVE facts that are the
measured causes of the stutter. Each fact names the measurement that found it.

  F1  THE ORPHAN GUARD. `os._exit` does not kill a child, so a worker spawned
      after the shell decided to quit SURVIVES the app and loads 1.2 GB of
      model on a machine whose app is already closed. MEASURED on the owner's
      own log: at 20:50:50.070, 0.65 s before `SHELL_EXIT`,
      `EXTERNAL_CAPTIONS_WORKER_RESUMED` started a second worker, whose
      `BRIDGE_LOAD_MS ms=67969` is 68 s of a busy machine. The guard has to be
      in `start_worker` ITSELF -- one path learned it the hard way, the others
      (the panel open, the VRAM resume, the revive) could still race the exit.

  F2  THE SHOW MUST NOT BLOCK THE CONTROL THREAD. The transparency hack
      marshals `form.Show()` onto the UI thread with `_ui`, whose DEFAULT
      budget is TEN SECONDS, and the caller is the HOTKEY thread -- the owner's
      only control. The wait is now bounded (`TRANSPARENCY_HACK_WAIT_S`) and
      falls back to a POST, so a busy UI thread cannot turn an Alt+C into a
      ten-second wait.

  F3  THE EXIT MUST NOT BLOCK THE TRAY THREAD. The window destroy is
      cosmetic (`os._exit` follows), and waiting three seconds for it was
      three seconds the owner was not answered. The wait is now
      `QUIT_DESTROY_WAIT_S`.

  F4  THE MODEL MUST BE READY BEFORE THE OWNER ASKS. The panel used to open
      and then sit there for the 36.9 s the model took to load (the owner's
      own log: `BRIDGE_LOAD_MS ms=36968 ... worker_load_s=32.59`). The
      preload schedules the load at the app's start, in the background, at the
      worker's BELOW_NORMAL priority -- and the reason 'preload' has to be in
      `START_REASONS`, or `start_worker` declines it and the preload is a
      comment.

  F5  THE GPU ARENA MUST NOT EAT THE CARD. The worker is started WITHOUT
      provider options, so onnxruntime's defaults apply:
      `arena_extend_strategy=kNextPowerOfTwo` (every GPU allocation rounds UP
      to the next power of two) and `gpu_mem_limit` UNLIMITED. The options
      travel with the provider names (`provider_entries`).

EVERY FACT IS STRUCTURAL (AST), NOT A SUBSTRING: a substring fact can be
satisfied by a COMMENT that mentions the right words, and the first version
of this gate was exactly that mistake -- its own mutants came back INERT.

THE NEGATIVE ARM IS A COPY, NOT A COMMENT (`--neg-arm`). Each mutant is a COPY
of the sources with ONE fact broken, and the gate has to go RED on it. A
mutant that changes nothing is INERT and is reported as the failure it is.

NOTHING IS LAUNCHED: no shell, no worker, no WebView2, no window.

Usage:
  py -3 _main/open-close-stall-oracle.py             the live sources
  py -3 _main/open-close-stall-oracle.py --neg-arm   the mutants, must be RED
                                                      (rc=1 BY DESIGN, "NEG-ARM PASS")
"""
from __future__ import annotations

import argparse
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')
WORKER = os.path.join(REPO, 'worker', 'sotto_worker.py')


def read(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        return fh.read()


def const_value(text, name):
    """The value of a module-level constant, as a number, or None."""
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    try:
                        return float(ast.literal_eval(node.value))
                    except (ValueError, TypeError):
                        return None
    return None


def start_reasons(text):
    """The `START_REASONS` tuple, read by AST.

    NOT by regex: the tuple carries comments with parentheses in it, and a
    `\\(([^)]*)\\)` stops at the first `)` -- which silently truncated the
    list before the reason this gate cares about. A gate that cannot read the
    product is a gate that cannot say no.
    """
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'START_REASONS':
                    try:
                        return [ast.literal_eval(el) for el in node.value.elts]
                    except Exception:  # noqa: BLE001
                        return []
    return []


def _func_node(text, name):
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name == name:
            return node
    return None


def _has_call(node, name):
    """Is there a call whose LAST name is `name` inside `node`?

    The last name, not the whole dotted path: the product writes
    `exiting.is_set()` and `threading.Timer(...)`, and a gate that demands
    the full path would call correct code broken.
    """
    if node is None:
        return False
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if isinstance(func, ast.Attribute):
            parts = []
            cur = func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            if name in parts or '.'.join(reversed(parts)) == name:
                return True
        elif isinstance(func, ast.Name) and func.id == name:
            return True
    return False


def _has_attr(node, attr):
    """Is there an attribute ACCESS named `attr` inside `node`?

    (`getattr(shell, '_post', None)` is an attribute access by name in the
    source; the call it produces is named `post`.)
    """
    if node is None:
        return False
    for sub in ast.walk(node):
        if isinstance(sub, ast.Attribute) and sub.attr == attr:
            return True
        if isinstance(sub, ast.Constant) and sub.value == attr:
            return True
    return False


def _arg_is_name(call, index, name):
    if call is None or len(call.args) <= index:
        return False
    return isinstance(call.args[index], ast.Name) and call.args[index].id == name


def _returns_false_in(node):
    for sub in ast.walk(node):
        if isinstance(sub, ast.Return):
            value = sub.value
            if isinstance(value, ast.Constant) and value.value is False:
                return True
            if isinstance(value, ast.Name) and value.id == 'False':
                return True
    return False


def check_facts(shell_text, worker_text):
    """The five facts. Returns [(fact_id, ok, why)] -- the WHY is the receipt."""
    facts = []

    # F1 -- the orphan guard, inside `start_worker` itself.
    start_node = _func_node(shell_text, 'start_worker')
    guard = False
    if start_node is not None:
        for node in ast.walk(start_node):
            if isinstance(node, ast.If) and _has_call(node, 'is_set') \
                    and _returns_false_in(node):
                guard = True
    facts.append((
        'F1 orphan guard in start_worker', guard,
        'start_worker must TEST an is_set() and return False there: '
        'os._exit does not kill a child, so a worker spawned after the '
        'shell decided to quit SURVIVES the app (the 2026-10-20 orphan: '
        '68 s of a busy machine after the app closed)'))

    # F2 -- the show's wait is bounded and falls back to a post.
    wait = const_value(shell_text, 'TRANSPARENCY_HACK_WAIT_S')
    hack_node = _func_node(shell_text, 'transparency_hack')
    bounded = False
    if hack_node is not None:
        for node in ast.walk(hack_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == 'ui' \
                    and _arg_is_name(node, 1, 'TRANSPARENCY_HACK_WAIT_S'):
                bounded = True
        bounded = (bounded and _has_attr(hack_node, '_post')
                   and wait is not None and 0 < wait <= 1.0)
    facts.append((
        'F2 the show does not block the control thread', bounded,
        'the transparency hack must call ui(form_show, TRANSPARENCY_HACK_'
        'WAIT_S) with the budget at most 1 s, and must have a _post '
        'fallback: the hotkey thread is the owner\'s only control and '
        '_ui\'s default is TEN SECONDS'))

    # F3 -- the exit's destroy wait is bounded.
    quit_wait = const_value(shell_text, 'QUIT_DESTROY_WAIT_S')
    exit_node = _func_node(shell_text, 'request_exit')
    bounded = False
    if exit_node is not None:
        for node in ast.walk(exit_node):
            if isinstance(node, ast.Call) \
                    and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == 'join' \
                    and _arg_is_name(node, 0, 'QUIT_DESTROY_WAIT_S'):
                bounded = True
        bounded = bounded and quit_wait is not None and 0 < quit_wait <= 0.5
    facts.append((
        'F3 the exit does not block the tray thread', bounded,
        'the destroy is cosmetic (os._exit follows): the join must be '
        'QUIT_DESTROY_WAIT_S and that budget at most half a second, not '
        'the old three seconds'))

    # F4 -- the preload is scheduled, delayed and ALLOWED.
    delay = const_value(shell_text, 'WORKER_PRELOAD_DELAY_S')
    schedule_node = _func_node(shell_text, '_schedule_preload_worker')
    body_node = _func_node(shell_text, '_preload_worker')
    reasons = start_reasons(shell_text)
    schedule_src = (ast.get_source_segment(shell_text, schedule_node) or '') \
        if schedule_node is not None else ''
    calls_preload = False
    if body_node is not None:
        for node in ast.walk(body_node):
            if isinstance(node, ast.Call) \
                    and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == 'start_worker' and node.args \
                    and isinstance(node.args[0], ast.Constant) \
                    and node.args[0].value == 'preload':
                calls_preload = True
    # UM TIMER FOI TROCADO POR UM WATCHER EM 2026-10-23, DE PROPOSITO (o `Timer` disparava
    # aos 20 s e nao sabia o que o dono estava a fazer; o watcher espera que ele pare).
    # Este braco pinava o TIMER e por isso acusava o codigo de hoje -- um braco que mede a
    # FORMA e nao o invariante. O invariante e': (a) ha' um atraso positivo, (b) o corpo
    # nao corre no chamador, (c) ha' saida por ambiente, (d) o motivo 'preload' e' aceite.
    deferred = (_has_call(schedule_node, 'Timer')
                or _has_call(schedule_node, 'Thread'))
    # (b) o que NAO pode acontecer: o agendador chamar `start_worker` as direitas (era uma
    # carga de ~2 GB a bloquear arranque) ou juntar-se a' thread (era o mesmo bloqueio).
    synchronous = any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in ('start_worker', 'join')
        for node in ast.walk(schedule_node)) if schedule_node is not None else True
    # ATENCAO 2026-10-30: O ATRASO PASSOU A SER ZERO, por ordem do dono
    # (*"a porra da legenda ao vivo levou uns 20 segundos pra comecar a mostrar.
    # nao era pra essa merda estar carregada desde sempre e mostrar
    # IMEDIATAMENTE?"*). O braco pinava `delay > 0`, que era a cura de 2026-10-23
    # para a queixa OPOSTA -- mede a FORMA de uma versao, nao o invariante. O
    # invariante que sobrevive aos dois dias: o preload e' DEFERIDO (nunca corre no
    # chamador), tem escape por ambiente, e a espera pelo dono quieto CONTINUA
    # escrita para quem passar um atraso (`base <= 0.0 or idle >= IDLE_S`).
    idle_gate = ('idle >= WORKER_PRELOAD_IDLE_S' in
                 (ast.get_source_segment(shell_text, _func_node(shell_text, '_preload_when_idle'))
                  or ''))
    ok = (delay is not None and delay >= 0 and idle_gate
          and schedule_node is not None and body_node is not None
          and 'SOTTO_NO_PRELOAD' in schedule_src
          and deferred and not synchronous
          and 'preload' in reasons
          and calls_preload)
    facts.append((
        'F4 the model is ready before the owner asks', ok,
        'the preload must be DEFERRED (a Timer, or the idle watcher thread), carry a '
        'NON-NEGATIVE delay whose idle gate still exists, be opt-out-able by '
        'SOTTO_NO_PRELOAD, never run in the caller (no start_worker/join in the '
        'scheduler), and use the reason \'preload\' -- '
        'which `start_worker` only accepts if it is in START_REASONS'))

    # F5 -- the CUDA EP's options travel with the provider names.
    options_node = _func_node(worker_text, 'cuda_provider_options')
    entries_node = _func_node(worker_text, 'provider_entries')
    ok = False
    if options_node is not None and entries_node is not None:
        entries_src = ast.get_source_segment(worker_text, entries_node) or ''
        # THE DICT'S VALUES, BY AST: the DOCSTRING mentions kNextPowerOfTwo
        # (that is the point of the comment) and a substring test would read
        # the EXPLANATION as the defect.
        carries = False
        arena_is_name = False
        for d in [n for n in ast.walk(options_node) if isinstance(n, ast.Dict)]:
            keys = [k.value for k in d.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            if 'arena_extend_strategy' in keys:
                carries = True
                for k, v in zip(d.keys, d.values):
                    if isinstance(k, ast.Constant) \
                            and k.value == 'arena_extend_strategy':
                        arena_is_name = isinstance(v, ast.Name)
        # `gpu_mem_limit` may be a dict key OR a subscript assignment (the
        # product sets it only when the limit is positive) -- both are the
        # key being PRESENT.
        carries = carries and _has_attr(options_node, 'gpu_mem_limit')
        # the default the NAME resolves to must be the one that does not round
        # every allocation up to the next power of two
        default_ok = False
        for node in ast.walk(options_node):
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.targets[0], ast.Name) \
                    and node.targets[0].id == 'arena':
                for sub in ast.walk(node.value):
                    if isinstance(sub, ast.Constant) \
                            and sub.value == 'kSameAsRequested':
                        default_ok = True
        ok = (carries and arena_is_name and default_ok
              and 'CUDAExecutionProvider' in entries_src
              and 'cuda_provider_options()' in entries_src)
    facts.append((
        'F5 the GPU arena does not eat the card', ok,
        'the worker must pass the CUDA EP\'s options (the arena rounds every '
        'allocation up to the next power of two by default, and the memory '
        'limit is unlimited)'))

    return facts


def verdict(facts):
    bad = [f for f in facts if not f[1]]
    for fact_id, ok, why in facts:
        print('%-46s %s' % (fact_id, 'PASS' if ok else '** FAIL **'))
        if not ok:
            print('    why: %s' % why)
    return len(bad) == 0


# ── the negative arm: the mutants ────────────────────────────────────────────
#: (name, file, old, new). Each breaks ONE fact.
MUTANTS = [
    ('M1 the orphan guard is removed', 'shell',
     "        if exiting is not None and exiting.is_set():",
     "        if False:"),
    ('M2 the show waits the full ten seconds again', 'shell',
     'answer = ui(form_show, TRANSPARENCY_HACK_WAIT_S)',
     'answer = ui(form_show, 10.0)'),
    ('M3 the exit waits three seconds again', 'shell',
     'closer.join(QUIT_DESTROY_WAIT_S)',
     'closer.join(3)'),
    ('M4 the preload reason is not allowed', 'shell',
     "                     'preload',",
     "                     'preload-not-allowed',"),
    ('M5 the GPU arena is left to the default', 'worker',
     '        "arena_extend_strategy": arena,',
     '        "arena_extend_strategy": "kNextPowerOfTwo",'),
]


def run_neg_arm():
    shell_text = read(SHELL)
    worker_text = read(WORKER)
    print('NEG-ARM the mutants must go RED')
    caught = 0
    for name, target, old, new in MUTANTS:
        s_text, w_text = shell_text, worker_text
        if target == 'shell':
            if old not in s_text:
                print('NEG-ARM %-46s ** ANCHOR GONE **' % name)
                continue
            s_text = s_text.replace(old, new, 1)
        else:
            if old not in w_text:
                print('NEG-ARM %-46s ** ANCHOR GONE **' % name)
                continue
            w_text = w_text.replace(old, new, 1)
        facts = check_facts(s_text, w_text)
        if verdict(facts):
            print('NEG-ARM %-46s ** INERT: the mutant changed nothing **' % name)
            continue
        print('NEG-ARM %-46s RED as expected' % name)
        caught += 1
    print('NEG-ARM %d of %d mutant(s) caught' % (caught, len(MUTANTS)))
    if caught == len(MUTANTS):
        print('NEG-ARM PASS')
        return 1      # rc=1 BY DESIGN: the defect was found
    print('VERDICT: FAIL -- %d mutant(s) were inert or unnoticed'
          % (len(MUTANTS) - caught))
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true',
                    help='run the controls: the mutants must go RED')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return run_neg_arm()
    facts = check_facts(read(SHELL), read(WORKER))
    ok = verdict(facts)
    print('VERDICT: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
