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
                              a "2" mesmo com o default "4" ja' escrito.
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
  A10 spawn-argv-end-to-end   o filho REAL da bridge recebe `--threads 2` no argv.
  A11 resolve-threads-real    `resolve_threads(2)` (a funcao que o `main()` chama)
                              deixa `current_threads()==2` e as cinco variaveis.
  A12 warm-default-agrees     o default de `warm_engine.py --threads` e o da shell
                              sao o MESMO numero.
  A13 streamasr-reader        `StreamAsr` abre as sessoes com `current_threads()`.
  A14 warm-main-applies       `apply_thread_budget` EXECUTADO com o worker real
                              deixa `current_threads()==2`, e o `main()` do motor
                              chama esse helper e entrega `threads=applied`.
  A15 threads-line-is-live-visible  `ENGINE_VISIBLE_TAGS` (AST) contem
                              `WORKER_THREADS`, o worker ESCREVE a linha e o
                              `_pump` publica por `startswith(ENGINE_VISIBLE_TAGS)`
                              -- o numero efectivo deixa de ser ilegivel ao vivo.

`--neg-arm`: nove mutacoes em COPIA (nunca em HEAD), cada uma derruba o SEU braco:
  M1 `os.environ[var] = str(n)` -> `os.environ.setdefault(var, str(n))`  -> A1 RED
  M2 a linha `tail += ['--threads', str(threads)]` removida               -> A6 RED
  M3 `min(int(engine_threads),` -> `max(...)`                             -> A9 RED
  M4 `_THREADS_EFFECTIVE = effective_threads(n)` -> `= None`              -> A11 RED
  M5 `WORKER_THREADS_DEFAULT = 2` -> `= 4`                                -> A12 RED
  M6 `_threads = current_threads()` -> `_threads = 4`                     -> A13 RED
  M7 `threads=applied` -> `threads=None`                                  -> A14 RED
  M8 `resolve_threads` -> `limit_threads` no helper                       -> A14 RED
  M9 o `main()` do motor chama `limit_threads` em vez do helper           -> A14 RED
  M10 a tag `WORKER_THREADS` sai de `ENGINE_VISIBLE_TAGS`                  -> A15 RED
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
ENGINE = os.path.join(ROOT, 'worker', 'engine_switch.py')
WARM = os.path.join(ROOT, 'app', 'webview', 'warm_engine.py')
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


def arm_a15(shell_path, worker_path):
    """A TAG QUE TORNA O NUMERO LEGIVEL AO VIVO (2026-11-09).

    O orcamento efectivo nasce no stderr do worker (`WORKER_THREADS threads=...
    source=...`), e o stderr so' e' publicado na CAUDA DA MORTE. Uma tag em
    `ENGINE_VISIBLE_TAGS` faz o `_pump` copiar a linha para o log enquanto o
    worker corre -- e' a diferenca entre "o numero existe" e "o numero pode ser
    lido sem matar o worker". Julgado por AST, nao por `grep`: um comentario que
    cite a tag nao pode fazer este braco passar.
    """
    src = open(shell_path, encoding='utf-8', errors='replace').read()
    tags = None
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == 'ENGINE_VISIBLE_TAGS'
                   for t in node.targets):
            continue
        try:
            tags = list(ast.literal_eval(node.value))
        except Exception:                                          # noqa: BLE001
            tags = None
    writer_src = open(worker_path, encoding='utf-8', errors='replace').read()
    publish = 'line.startswith(ENGINE_VISIBLE_TAGS)' in src
    # O CONJUNTO QUE TEM DE ESTAR LEGIVEL, cada um com o seu porque': o orcamento de
    # fios (`WORKER_THREADS`), o ARMAMENTO do passe de fundo (`REDUX_SWITCH armed=`) e o
    # proprio passe (`REDUX_BATCH_KICK`). Os dois ultimos entraram em 2026-11-09 depois
    # de a medicao mostrar que a linha do armamento existia e morria na cauda da morte
    # (21 ocorrencias no log vivo, todas dentro de `stderr_tail=[...]`).
    # As duas tags do passe de fundo NAO nascem no `sotto_worker.py`: o armamento e o
    # proprio passe vivem no `engine_switch.py` (que o worker importa), por isso o
    # escritor e' a UNIAO dos dois -- ler so' o worker faz este braco acusar quem esta'
    # certo, que e' a classe de erro que um portao paga caro para cometer.
    writer_src += open(ENGINE, encoding='utf-8', errors='replace').read()
    required = (('WORKER_THREADS', 'WORKER_THREADS'),
                ('REDUX_SWITCH', 'REDUX_SWITCH armed'),
                ('REDUX_BATCH_KICK', 'REDUX_BATCH_KICK'))
    missing = [tag for tag, needle in required
               if tag not in (tags or []) or needle not in writer_src]
    ok = bool(tags) and not missing and publish
    return ok, 'tags=%r missing=%r publish=%s' % (tags, missing, publish)


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


def arm_a9(module=None):
    if module is None:
        import engine_switch as module
    bad = []
    for given, want in ((None, 2), (1, 1), (2, 2), (9, 2)):
        sw = module.ReduxHiddenSwitch(
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


def arm_a11(path):
    """`resolve_threads` -- o que o `main()` faz, chamado de verdade.

    O furo que este braco fecha (revisao independente, 2026-11-09): a resolucao
    vivia inline no `main()` e NENHUM arm a alcancava; apagar a atribuicao
    deixava 10/10 verdes. Aqui o valor e' lido de `current_threads()`, que e' o
    que o `StreamAsr` le' para abrir as sessoes.
    """
    def probe(mod):
        got = mod.resolve_threads(2)
        seen = mod.current_threads()
        env = {k: os.environ.get(k) for k in VARS}
        bad = {k: v for k, v in env.items() if v != '2'}
        ok = (got == (2, 'flag') and seen == 2 and not bad)
        return ok, 'resolve=%r current=%r env_bad=%r' % (got, seen, bad)
    ok_flag, d_flag = with_worker(path, None, probe)
    ok_auto, d_auto = with_worker(path, None, lambda mod: (
        mod.resolve_threads(0) == (4, 'default') and mod.current_threads() == 4,
        'auto=%r' % (mod.resolve_threads(0),)))
    return (ok_flag and ok_auto), '%s | %s' % (d_flag, d_auto)


def arm_a12(shell_path, warm_path=None):
    """O default do MOTOR DE AQUECIMENTO e o da shell sao o MESMO numero.

    Duas declaracoes (o processo do motor nasce antes da shell e constroi as
    sessoes que o `attach` entrega), um numero so': este arm e' o que impede a
    divergencia silenciosa -- o defeito que a revisao independente achou no
    `warm_engine.py` (sessoes a 4 enquanto a shell pedia 2).
    """
    def default_of(path, flag):
        """O default literal de `--flag`, resolvendo uma constante do MESMO ficheiro."""
        tree = ast.parse(open(path, encoding='utf-8').read())
        consts = {}
        for node in tree.body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                    and isinstance(node.value, ast.Constant):
                name = getattr(node.targets[0], 'id', None)
                if name:
                    consts[name] = node.value.value
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == 'add_argument'):
                continue
            if not (node.args and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == flag):
                continue
            kw = {k.arg: k.value for k in node.keywords}
            val = kw.get('default')
            if isinstance(val, ast.Constant):
                return val.value
            if isinstance(val, ast.Name):
                return consts.get(val.id, '<%s>' % val.id)
            return None
        return None

    shell_def = default_of(shell_path, '--worker-threads')
    warm_def = default_of(warm_path or WARM, '--threads')
    ok = (shell_def == 2 and warm_def == shell_def)
    return ok, 'shell=%r warm_engine=%r' % (shell_def, warm_def)


def arm_a13(path):
    """`StreamAsr` abre as sessoes com `current_threads()`, nao com um segundo parser.

    Leitura de AST porque construir `StreamAsr` de verdade custa 1,9 GB de pesos;
    o que este arm protege e' a FIACAO (o valor lido), e o A4 ja' prova que
    `session_options` honra o numero que recebe.
    """
    tree = ast.parse(open(path, encoding='utf-8').read())
    hit = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'StreamAsr':
            for sub in ast.walk(node):
                if isinstance(sub, ast.Assign) and len(sub.targets) == 1:
                    tgt = sub.targets[0]
                    if getattr(tgt, 'id', None) == '_threads' and \
                            isinstance(sub.value, ast.Call) and \
                            getattr(sub.value.func, 'id', None) == 'current_threads':
                        hit.append(sub.lineno)
    return bool(hit), 'StreamAsr _threads = current_threads() at %r' % (hit,)



def arm_a14(warm_path=None):
    """O motor APLICA o orcamento pelo dono unico, e o `StreamAsr` le' esse numero.

    Duas metades, porque uma so' mente:
    (a) `apply_thread_budget` e' EXECUTADA com o worker real: o numero que o
        `StreamAsr` le' (`current_threads`) tem de ser o pedido. `limit_threads`
        sozinho escreve o ambiente e deixa `current_threads()` em 4 -- medido
        2026-11-09, e era o estado do ficheiro quando este braco nasceu;
    (b) o `main()` tem de chamar o helper e entregar `threads=applied` ao
        `WarmEngine` (AST: subir o motor de verdade abre pipe, mutex e pid file).
    """
    tree = ast.parse(open(warm_path or WARM, encoding='utf-8').read())
    calls_helper = None
    handed = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == 'main':
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                        and sub.func.id == 'apply_thread_budget':
                    calls_helper = sub.lineno
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                        and sub.func.id == 'WarmEngine':
                    for k in sub.keywords:
                        if k.arg == 'threads':
                            handed = ast.unparse(k.value)

    def probe(mod):
        warm_mod = load(warm_path or WARM, 'warm_engine_under_test')
        helper = getattr(warm_mod, 'apply_thread_budget', None)
        if helper is None:
            return False, 'apply_thread_budget ausente'
        got = helper(mod, 2)
        seen = mod.current_threads()
        auto = helper(mod, 0)
        ok = (got == 2 and seen == 2 and auto is None)
        return ok, 'applied=%r current=%r auto=%r' % (got, seen, auto)

    ok_exec, detail = with_worker(WORKER, None, probe)
    ok_wire = calls_helper is not None and handed == 'applied'
    return (ok_exec and ok_wire), 'exec=%s (%s) helper@%r threads=%r' % (
        ok_exec, detail, calls_helper, handed)



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
    ('A11 resolve-threads-real', lambda: arm_a11(WORKER)),
    ('A12 warm-default-agrees', lambda: arm_a12(SHELL)),
    ('A13 streamasr-reader', lambda: arm_a13(WORKER)),
    ('A14 warm-main-applies', lambda: arm_a14(WARM)),
    ('A15 threads-line-is-live-visible', lambda: arm_a15(SHELL, WORKER)),
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

        engine_m = mutate(
            ENGINE, os.path.join(tmp, 'engine_switch.py'),
            [('min(int(engine_threads),', 'max(int(engine_threads),')])
        worker_m4 = mutate(
            WORKER, os.path.join(tmp, 'sotto_worker_m4.py'),
            [('_THREADS_EFFECTIVE = effective_threads(n)',
              '_THREADS_EFFECTIVE = None')])
        warm_m5 = mutate(
            WARM, os.path.join(tmp, 'warm_engine.py'),
            [('WORKER_THREADS_DEFAULT = 2', 'WORKER_THREADS_DEFAULT = 4')])
        worker_m6 = mutate(
            WORKER, os.path.join(tmp, 'sotto_worker_m6.py'),
            [('_threads = current_threads()', '_threads = 4')])
        warm_m7 = mutate(
            WARM, os.path.join(tmp, 'warm_engine_m7.py'),
            [('                        threads=applied)', '                        threads=None)')])
        warm_m8 = mutate(
            WARM, os.path.join(tmp, 'warm_engine_m8.py'),
            [('return int(worker.resolve_threads(int(threads))[0])',
              'worker.limit_threads(int(threads)); return int(threads)')])
        shell_m10 = mutate(
            SHELL, os.path.join(tmp, 'sotto_webview_m10.py'),
            [("'REDUX_SHEDDING', 'WORKER_THREADS',", "'REDUX_SHEDDING',")])
        shell_m11 = mutate(
            SHELL, os.path.join(tmp, 'sotto_webview_m11.py'),
            [("'WORKER_THREADS',\n                       'REDUX_SWITCH',",
              "'WORKER_THREADS',")])
        warm_m9 = mutate(
            WARM, os.path.join(tmp, 'warm_engine_m9.py'),
            [('applied = apply_thread_budget(import_worker(args.root), args.threads)',
              'applied = import_worker(args.root).limit_threads(args.threads)')])

        def caught(fn, *a):
            """Um mutante que FAZ O BRACO EXPLODIR tambem foi apanhado."""
            try:
                ok, detail = fn(*a)
            except Exception as exc:  # noqa: BLE001 -- mutante que estoura = RED
                return True, 'raised %s: %s' % (type(exc).__name__, exc)
            return (not ok), detail

        c1, d1 = caught(arm_a1, worker_m)
        c6, d6 = caught(arm_a6, shell_m)
        c9, d9 = caught(arm_a9, load(engine_m, 'engine_switch_mutated'))
        c11, d11 = caught(arm_a11, worker_m4)
        c12, d12 = caught(arm_a12, shell_m, warm_m5)
        c13, d13 = caught(arm_a13, worker_m6)
        c14, d14 = caught(arm_a14, warm_m7)
        c14b, d14b = caught(arm_a14, warm_m8)
        c14c, d14c = caught(arm_a14, warm_m9)
        c15, d15 = caught(arm_a15, shell_m10, WORKER)
        c15b, d15b = caught(arm_a15, shell_m11, WORKER)
        # O braco mutado tem de ficar RED; os irmaos tem de continuar GREEN.
        ok2, d2 = arm_a2(worker_m)
        ok_all = c1 and c6 and c9 and c11 and c12 and c13 and c14 \
            and c14b and c14c and c15 and c15b and ok2
        add(ok_all, 'NEG-ARM M1..M11',
            'A1=%s A6=%s A9=%s A11=%s A12=%s A13=%s A14=%s/%s/%s A15=%s (A2 control=%s)' % (
                'RED' if c1 else 'GREEN', 'RED' if c6 else 'GREEN',
                'RED' if c9 else 'GREEN', 'RED' if c11 else 'GREEN',
                'RED' if c12 else 'GREEN', 'RED' if c13 else 'GREEN',
                'RED' if c14 else 'GREEN', 'RED' if c14b else 'GREEN',
                'RED' if c14c else 'GREEN', 'RED' if c15 else 'GREEN',
                'GREEN' if ok2 else 'RED'))
        for tag, detail in (('M1', d1), ('M2', d6), ('M3', d9),
                            ('M4', d11), ('M5', d12), ('M6', d13),
                            ('M7', d14), ('M8', d14b), ('M9', d14c),
                            ('M10', d15), ('M11', d15b)):
            print('  %s: %s' % (tag, detail))
        if ok_all:
            print('NEG-ARM: PASS -- 11 mutants caught')
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
