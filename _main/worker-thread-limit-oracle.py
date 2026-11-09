# NO-BUG: o `--threads` do worker era INERTE (capacidade, nao um id do `_main/bug-ledger.json`).
"""O ORCAMENTO DE FIOS DO WORKER DE ASR -- e o `--threads` que nao fazia nada.

O FACTO MEDIDO (2026-11-09, no dono, `_main/shell-thread-cpu.py 43076 --seconds 10`):

  pid 43076: 77 fios, 10.1 s de janela, 59.6% de um nucleo no total
    32.3%  tid 49716  session-13-intra-op-0
    12.5%  tid 42840  session-12-intra-op-0
    11.1%  tid 16680  session-14-intra-op-0

(uma janela de 10 s na DM do watcher apanhou 159.5 %; as duas leituras sao a mesma
rajada em fases diferentes). O actor sao as sessoes do onnxruntime, e o worker
vivo corria `python -u worker/sotto_worker.py` -- sem flag nenhuma.

O DEFEITO. `--threads N` existia no CLI e nao mudava um fio do ORT:
`limit_threads()` usava `os.environ.setdefault`, e o `setdefault("OMP_NUM_THREADS",
"4")` do topo do modulo ja' tinha escrito "4". Resultado: `--threads 2` mudava
`MKL_NUM_THREADS` e deixava `OMP_NUM_THREADS` -- a unica variavel que `StreamAsr`
le' -- em 4. As tres sessoes abriam com 4 fios intra-op cada.

O QUE ESTE ORACULO JULGA (sem carregar modelo, sem abrir dispositivo, sem janela):

  A1 flag-overrides-default   `limit_threads(2)` poe OMP/MKL/OPENBLAS/NUMEXPR/VECLIB
                              a "2" mesmo com o default "4" ja' escrito. RED hoje.
  A2 auto-keeps-env           `limit_threads(0)` NAO pisa um `OMP_NUM_THREADS=6`
                              explicito -- o comportamento de antes fica igual.
  A3 precedence               `--threads` > ambiente > 4; ambiente invalido e'
                              DITO (`env-invalid`), nunca engolido.
  A4 session-options          `session_options(fake_ort, threads=2)` executa a
                              funcao REAL e poe intra=2 / inter=1.
  A5 streamasr-budget         `StreamAsr` le' o MESMO numero que `main()` resolveu
                              (`current_threads`), nao um segundo parser do env.
  A6 shell-argv-tail          `worker_argv_tail` emite `--threads N` DEPOIS do
                              script path, combina com `--speakers`, e `0` nao
                              emite flag nenhuma.
  A7 worker-accepts-flag      o worker REAL aceita o argv que a shell monta
                              (`python -u sotto_worker.py --threads 2 --help`).
  A8 shell-cli-contract       `--worker-threads` existe, e' `int`, default 2, e o
                              sitio de construcao da bridge usa `worker_argv_tail`.
  A9 engine-pool-cap          o motor de FUNDO (parakeet) aceita o mesmo knob e
                              NUNCA sobe acima do default medido (2).

`--neg-arm`: duas mutacoes em COPIA (nunca em HEAD), cada uma derruba o SEU braco:
  M1 `os.environ[var] = str(n)` -> `os.environ.setdefault(var, str(n))`  -> A1 RED
  M2 a linha `tail += ['--threads', str(threads)]` removida               -> A6 RED
Sai com rc=1 quando apanha (a convencao do `:expectred` da bateria), rc=0 quando
o mutante sobrevive, rc=2 em erro de setup.

Uso:
    python _main/worker-thread-limit-oracle.py
    python _main/worker-thread-limit-oracle.py --neg-arm
"""
from __future__ import annotations

import ast
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
WORKER_DIR = os.path.join(ROOT, 'worker')
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
SHELL_DIR = os.path.join(ROOT, 'app', 'webview')
MAIN = os.path.join(ROOT, '_main')
LAUNCHER = os.path.join(MAIN, 'hidden-launch.py')
sys.path.insert(0, MAIN)
sys.path.insert(0, SHELL_DIR)
sys.path.insert(0, WORKER_DIR)

VARS = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
        "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")

RESULTS = []
_LOADS = [0]


def add(ok, name, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print('%-30s %s %s' % (name, 'GREEN' if ok else 'RED', detail))
    return bool(ok)


def load(path, prefix):
    _LOADS[0] += 1
    name = '%s_%d' % (prefix, _LOADS[0])
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def with_worker(path, env_omp, fn):
    """Run `fn(module)` with a CLEAN thread environment.

    O modulo le' o ambiente no IMPORT (`_ENV_OMP_AT_IMPORT`) e escreve-o no topo,
    por isso cada braco precisa de um ambiente proprio: um segundo load herdaria
    o "4" que o primeiro escreveu e a precedencia media o proprio teste.
    """
    saved = {k: os.environ.get(k) for k in VARS}
    try:
        for k in VARS:
            os.environ.pop(k, None)
        if env_omp is not None:
            os.environ['OMP_NUM_THREADS'] = env_omp
        return fn(load(path, 'sw_threads_under_test'))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ── the arms ────────────────────────────────────────────────────────────────
def arm_a1(path):
    def probe(mod):
        mod.limit_threads(2)
        got = {k: os.environ.get(k) for k in VARS}
        bad = {k: v for k, v in got.items() if v != '2'}
        return (not bad), ('all five = 2' if not bad else 'not 2: %r' % bad)
    return with_worker(path, None, probe)


def arm_a2(path):
    def probe(mod):
        mod.limit_threads(0)
        omp = os.environ.get('OMP_NUM_THREADS')
        n, src = mod.effective_threads(0)
        ok = (omp == '6' and n == 6 and src == 'env')
        return ok, 'OMP=%r effective=%r src=%s' % (omp, n, src)
    return with_worker(path, '6', probe)


def arm_a3(path):
    def probe(mod):
        got = [mod.effective_threads(0), mod.effective_threads(2)]
        ok_env = got[0] == (6, 'env')
        ok_flag = got[1] == (2, 'flag')
        return (ok_env and ok_flag), 'env=%r flag=%r' % (got[0], got[1])
    ok_env, detail_env = with_worker(path, '6', probe)
    ok_inv, detail_inv = with_worker(path, 'abc', lambda mod: (
        mod.effective_threads(0) == (4, 'env-invalid'),
        'invalid=%r' % (mod.effective_threads(0),)))
    ok_def, detail_def = with_worker(path, None, lambda mod: (
        mod.effective_threads(0) == (4, 'default'),
        'default=%r' % (mod.effective_threads(0),)))
    ok = ok_env and ok_inv and ok_def
    return ok, '%s | %s | %s' % (detail_env, detail_inv, detail_def)


class _FakeOptions:
    def __init__(self):
        self.intra_op_num_threads = 0
        self.inter_op_num_threads = 0
        self.graph_optimization_level = None

    def add_session_config_entry(self, *_a, **_k):
        pass


class _FakeOrt:
    GraphOptimizationLevel = type('G', (), {
        'ORT_ENABLE_BASIC': 'basic', 'ORT_ENABLE_ALL': 'all'})

    def SessionOptions(self):
        return _FakeOptions()


def arm_a4(path):
    def probe(mod):
        so = mod.session_options(_FakeOrt(), '', 2)
        ok = (so.intra_op_num_threads == 2 and so.inter_op_num_threads == 1)
        return ok, 'intra=%r inter=%r' % (so.intra_op_num_threads,
                                          so.inter_op_num_threads)
    return with_worker(path, None, probe)


def arm_a5(path):
    def probe(mod):
        mod._THREADS_EFFECTIVE = (2, 'flag')
        got_flag = mod.current_threads()
        mod._THREADS_EFFECTIVE = None
        got_env = mod.current_threads()
        ok = (got_flag == 2 and got_env == 4)
        return ok, 'flag=%r fallback=%r' % (got_flag, got_env)
    return with_worker(path, None, probe)


def arm_a6(shell_path):
    mod = load(shell_path, 'shell_threads_under_test')

    class A:
        def __init__(self, speakers=False, worker_threads=0):
            self.speakers = speakers
            self.worker_threads = worker_threads

    cases = [
        ('default-2', A(worker_threads=2), ['--threads', '2']),
        ('off', A(worker_threads=0), []),
        ('speakers+2', A(speakers=True, worker_threads=2),
         ['--speakers', '--threads', '2']),
        ('negative', A(worker_threads=-3), []),
    ]
    bad = []
    for name, args, want in cases:
        got = mod.worker_argv_tail(args)
        if got != want:
            bad.append('%s: %r != %r' % (name, got, want))
    return (not bad), ('4 cases' if not bad else '; '.join(bad))


def arm_a7(worker_path):
    launcher = load(LAUNCHER, 'hidden_launch_under_test')
    rc, out, err = launcher.run(
        [sys.executable, '-u', worker_path, '--threads', '2', '--help'],
        capture=True, timeout=120)
    ok = (rc == 0 and '--threads' in (out or ''))
    return ok, 'rc=%r help_has_flag=%r' % (rc, '--threads' in (out or ''))


def arm_a8(shell_path):
    tree = ast.parse(open(shell_path, encoding='utf-8').read())
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == 'add_argument' \
                and node.args and isinstance(node.args[0], ast.Constant) \
                and node.args[0].value == '--worker-threads':
            kw = {k.arg: k.value for k in node.keywords}
            found['default'] = getattr(kw.get('default'), 'value', None)
            found['type'] = getattr(kw.get('type'), 'id', None)
        if isinstance(fn, ast.Name) and fn.id == 'WorkerBridge':
            for k in node.keywords:
                if k.arg == 'extra_args':
                    found['extra_args'] = ast.unparse(k.value)
    ok = (found.get('default') == 2 and found.get('type') == 'int'
          and found.get('extra_args') == 'worker_argv_tail(self.args)')
    return ok, 'default=%r type=%r extra_args=%r' % (
        found.get('default'), found.get('type'), found.get('extra_args'))


def arm_a9():
    import engine_switch
    bad = []
    for given, want in ((None, 2), (1, 1), (2, 2), (9, 2)):
        sw = engine_switch.ReduxHiddenSwitch(
            enabled=False, reader=lambda: False, runner='nope',
            log_fn=lambda _m: None, engine_threads=given)
        got = getattr(sw.engine, 'threads', None)
        if got != want:
            bad.append('engine_threads=%r -> %r (want %r)' % (given, got, want))
    return (not bad), ('4 cases' if not bad else '; '.join(bad))


def arm_a10(shell_path):
    """O caminho REAL de spawn: `WorkerBridge._spawn` larga um worker de teste e
    o argv que o FILHO recebe e' lido do proprio filho.

    A7 prova que o worker aceita a flag; A6/A8 provam a lista. Este braco prova
    o que os tres nao provam juntos: que a flag chega DEPOIS do script path (o
    unico lugar em que o argparse do worker a ve) e que o argv e' o que a shell
    montou, nao uma reconstrucao de leitura.
    """
    mod = load(shell_path, 'shell_spawn_under_test')
    tmp = tempfile.mkdtemp(prefix='sw-threads-spawn-')
    stub = os.path.join(tmp, 'stub_worker.py')
    out = os.path.join(tmp, 'argv.json')
    open(stub, 'w', encoding='utf-8').write(
        "import json, os, sys\n"
        "open(os.environ['SOTTO_TEST_ARGV_FILE'], 'w').write(json.dumps(sys.argv))\n")
    os.environ['SOTTO_TEST_ARGV_FILE'] = out

    class A:
        speakers = False
        worker_threads = 2

    logs = []
    bridge = mod.WorkerBridge(
        command=sys.executable, worker_path=stub,
        log=lambda m: logs.append(m),
        extra_args=mod.worker_argv_tail(A()))
    try:
        bridge.start('oracle-a10')
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not os.path.exists(out):
            time.sleep(0.05)
        argv = []
        if os.path.exists(out):
            import json
            argv = json.load(open(out, encoding='utf-8'))
        ok = (argv[:3] == [stub, '--threads', '2'])
        return ok, 'child argv=%r' % (argv,)
    finally:
        try:
            bridge.stop('oracle-a10')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            os.environ.pop('SOTTO_TEST_ARGV_FILE', None)


ARMS = [
    ('A1 flag-overrides-default', lambda: arm_a1(WORKER)),
    ('A2 auto-keeps-env', lambda: arm_a2(WORKER)),
    ('A3 precedence', lambda: arm_a3(WORKER)),
    ('A4 session-options', lambda: arm_a4(WORKER)),
    ('A5 streamasr-budget', lambda: arm_a5(WORKER)),
    ('A6 shell-argv-tail', lambda: arm_a6(SHELL)),
    ('A7 worker-accepts-flag', lambda: arm_a7(WORKER)),
    ('A8 shell-cli-contract', lambda: arm_a8(SHELL)),
    ('A9 engine-pool-cap', arm_a9),
    ('A10 spawn-argv-end-to-end', lambda: arm_a10(SHELL)),
]


def run_positive():
    ok_all = True
    for name, fn in ARMS:
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001 -- um braco que estoura e' RED
            ok, detail = False, '%s: %s' % (type(exc).__name__, exc)
        ok_all = add(ok, name, detail) and ok_all
    return ok_all


# ── the mutants ─────────────────────────────────────────────────────────────
def mutate(src_path, dst_path, pairs):
    text = open(src_path, encoding='utf-8').read()
    for old, new in pairs:
        if old not in text:
            raise SystemExit('MUTATION IMPOSSIVEL: %r nao existe em %s'
                             % (old, src_path))
        text = text.replace(old, new, 1)
    open(dst_path, 'w', encoding='utf-8', newline='').write(text)
    return dst_path


def run_negative():
    tmp = tempfile.mkdtemp(prefix='sw-threads-neg-')
    try:
        worker_m = mutate(
            WORKER, os.path.join(tmp, 'sotto_worker.py'),
            [('os.environ[var] = str(n)',
              'os.environ.setdefault(var, str(n))')])
        shell_m = mutate(
            SHELL, os.path.join(tmp, 'sotto_webview.py'),
            [("tail += ['--threads', str(threads)]", "pass")])

        ok1, d1 = arm_a1(worker_m)
        ok6, d6 = arm_a6(shell_m)
        # O braco mutado tem de ficar RED; os irmaos tem de continuar GREEN.
        ok2, d2 = arm_a2(worker_m)
        caught = (not ok1) and (not ok6) and ok2
        add(caught, 'NEG-ARM M1+M2',
            'A1=%s A6=%s (A2 control=%s)' % (
                'RED' if not ok1 else 'GREEN', 'RED' if not ok6 else 'GREEN',
                'GREEN' if ok2 else 'RED'))
        print('  M1: %s' % d1)
        print('  M2: %s' % d6)
        if caught:
            print('NEG-ARM: PASS -- 2 mutants caught')
            return True
        print('NEG-ARM: FAIL -- a mutation survived')
        return False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    if '--neg-arm' in argv:
        return 1 if run_negative() else 0
    ok = run_positive()
    print('VERDICT: %s (%d/%d)' % ('PASS' if ok else 'FAIL',
                                   sum(1 for _n, o, _d in RESULTS if o),
                                   len(RESULTS)))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
