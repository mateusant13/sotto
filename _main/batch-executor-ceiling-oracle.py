# NO-BUG: O LOTE NAO TINHA ORCAMENTO DE CPU -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""O ORCAMENTO DE CPU DO LACO DO LOTE -- medido a CORRER o executor real.

O FACTO MEDIDO (2026-11-08 23:2x, no dono, `_main/shell-thread-cpu.py 55104
--seconds 6 --top 8`):

  pid 55104: 48 threads, 48.4% de UM nucleo total
    36.0%  tid 10848  sotto-batch-executor

e o vigia da frota nomeou esse processo como a maior pressao de stutter (15
episodios/60 min). O laco (`BatchExecutor`, `app/webview/batch_queue.py`) nao e'
um spin: arranca UM filho por bloco e espera-o. O que faltava era um TECTO
DECLARADO -- o bloco seguinte comecava no instante em que o anterior acabava.

O QUE ESTE ORACULO JULGA (o laco REAL, sem parakeet e sem dispositivo de audio):

  1. `budget-converges`     -- o executor corre `run()` com um spawn FALSO cujo
                               filho dorme um tempo conhecido; a taxa de servico
                               medida entre blocos tem de ficar no orcamento
                               (`BATCH_CPU_BUDGET`) dentro de +-40 % relativo,
                               com >= 3 blocos; e o log tem de dizer os TRES
                               numeros (`used_ms=`, `budget=`, `rate=`).
  2. `level-yield-requeues` -- a carga a subir a meio de um bloco mata o filho e
                               devolve o bloco a' fila, sem contar como falha.
  3. `stop-leaves-no-child` -- um `stop()` a meio de um bloco termina o fio, mata
                               o filho e nao deixa o bloco `inflight`.
  4. `child-thread-ceiling` -- o filho arranca com o TECTO DE FIOS na env
                               (`OMP_NUM_THREADS` e as irmas BLAS) e o caminho
                               REAL de arranque (`_spawn_below_normal`) passa
                               essa env ao `Popen`.

`--neg-arm`: muta uma COPIA de `app/webview/batch_queue.py` para o laco NAO
esperar (`self._pace()` -> `pass`, o comportamento antigo) e exige o braco 1 a
falhar com a taxa a ~100 %. Um oraculo cujo mutante passa nao prova nada.

CONTRATO DA BATERIA (o mesmo do `batch-queue-drain-oracle`): o braco negativo
sai com rc=1 quando APANHA o mutante (e' o que o `:expectred` verifica), rc=0
quando o mutante sobrevive.
"""
import importlib.util
import json
import inspect
import io
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
MODULE = os.path.join(WEBVIEW, 'batch_queue.py')
sys.path.insert(0, WEBVIEW)

#: O trabalho do filho falso, por bloco. Pequeno de proposito: com o orcamento
#: de 12 % um ciclo e' `0.08 / 0.12 = 0.67 s`, logo 4 blocos medem-se em ~2 s.
WORK_S = 0.08

TOLERANCE = 0.40

RESULTS = []


def add(ok, name, detail=''):
    RESULTS.append((name, bool(ok), detail))
    print('%-34s %s %s' % (name, 'GREEN' if ok else 'RED', detail))
    return bool(ok)


def load_module(path):
    spec = importlib.util.spec_from_file_location('bq_ceiling_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def wait_for(predicate, timeout, step=0.02):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(step)
    return False


class FakeChild(object):
    """O filho do executor sem parakeet: dorme o trabalho que o braco manda.

    `communicate(timeout)` imita o contrato do `subprocess.Popen`: levanta
    `TimeoutExpired` enquanto o trabalho nao acabou, e devolve a linha JSON que o
    driver devolveria quando acaba. `hang=True` e' um filho que nunca acaba --
    e' assim que o ceder e o stop sao medidos.
    """

    def __init__(self, work_s=0.0, hang=False, ids=()):
        self.work_s = float(work_s)
        self.hang = bool(hang)
        # O FILHO REAL respondE um `result` por `id` (o executor passa `--ids`). Um
        # falso que devolvesse UMA linha para um lote de oito blocos nao poderia ser
        # atribuido -- desde 2026-11-12 o executor recusa marcar `done` o bloco cujo
        # resultado nao veio, por isso o falso tem de falar o mesmo contrato.
        self.ids = [str(i) for i in ids]
        self.out = '\n'.join(
            json.dumps({'type': 'result', 'text': 'ok', 'id': i}) for i in self.ids
        ) + ('\n' if self.ids else '{"type":"result","text":"ok"}\n')
        self.returncode = None
        self.killed = False
        self.started = None
        self.finished = None
        self.polls = 0
        self.on_poll = None

    def communicate(self, timeout=None):
        if self.started is None:
            self.started = time.monotonic()
        if self.killed:
            self.returncode = -9
            return '', ''
        if self.hang:
            self.polls += 1
            if self.on_poll is not None:
                self.on_poll(self)
            time.sleep(min(0.02, float(timeout or 0.02)))
            if self.killed:
                self.returncode = -9
                return '', ''
            raise subprocess.TimeoutExpired('batch-child', timeout)
        remaining = self.work_s - (time.monotonic() - self.started)
        if remaining <= 0:
            self.finished = time.monotonic()
            self.returncode = 0
            return self.out, ''
        time.sleep(min(remaining, float(timeout or remaining)))
        if self.killed:
            self.returncode = -9
            return '', ''
        if time.monotonic() - self.started >= self.work_s:
            self.finished = time.monotonic()
            self.returncode = 0
            return self.out, ''
        raise subprocess.TimeoutExpired('batch-child', timeout)

    def kill(self):
        self.killed = True


def make_executor(mod, path, level='leve', work_s=0.0, hang=False):
    """Um executor REAL, com spawn falso e a adopcao presa ao directorio do braco.

    A adopcao e' presa aqui pela mesma razao que o `batch-queue-drain-oracle`
    documenta: com `adopt_roots=None` a primeira volta adoptava os spools REAIS
    de `TMPDIR` e o braco media trabalho de outra sessao.
    """
    box = {'level': level, 'kids': [], 'cmds': [], 'logs': []}
    queue = mod.BatchQueue(path=path, log_fn=lambda _m: None)

    def spawn(cmd):
        box['cmds'].append(list(cmd))
        ids = []
        if '--ids' in cmd:
            ids = [i for i in str(cmd[cmd.index('--ids') + 1]).split(',') if i]
        child = FakeChild(work_s=work_s, hang=hang, ids=ids)
        box['kids'].append(child)
        return child

    spool = os.path.join(path, 'spool')
    os.makedirs(spool, exist_ok=True)
    ex = mod.BatchExecutor(queue=queue, log_fn=box['logs'].append,
                           level_fn=lambda: box['level'], spawn=spawn,
                           poll_s=0.05, child_poll_s=0.02,
                           yield_backoff_s=0.0,
                           adopt_every_s=3600.0, adopt_roots=[spool])
    return ex, queue, box


def enqueue(mod, queue, count=1, seconds=0.5):
    raw = b'\x00\x00\x00\x00' * int(16000 * seconds)
    return [queue.enqueue_f32(raw, source='oracle-ceiling') for _ in range(count)]


def arm_budget(mod, path, blocks=None):
    """(1) A TAXA DE SERVICO CONVERGE PARA O ORCAMENTO -- medido no laco real.

    A medida e' EXTERNA ao executor: para cada par de FILHOS consecutivos,
    `duracao_do_filho / intervalo_ate_o_proximo`. E' a definicao de duty cycle e
    nao depende de o executor se auto-reportar.

    A unidade e' o FILHO, e nao o bloco, desde 2026-11-12: um filho passou a servir
    ate' `MAX_BLOCKS_PER_CHILD` blocos com UMA carga do motor (a cura do io de
    `162,4 MB/s` medido no dono). Por isso a populacao e' dimensionada em BLOCOS
    para produzir varios FILHOS -- `4 * MAX_BLOCKS_PER_CHILD + 1` da' cinco --, e um
    oraculo que fixasse `blocks=4` mediria um laco de um filho so' e chamaria isso
    de taxa de servico.
    """
    if blocks is None:
        blocks = 4 * int(getattr(mod, 'MAX_BLOCKS_PER_CHILD', 1)) + 1
    ex, queue, box = make_executor(mod, path, work_s=WORK_S)
    enqueue(mod, queue, blocks)
    ex.start()
    try:
        done = wait_for(lambda: queue.stats()['done'] >= blocks, 25.0)
    finally:
        ex.stop()
        ex.join(5.0)
    kids = [k for k in box['kids'] if k.started is not None and k.finished]
    duties = []
    for first, nxt in zip(kids, kids[1:]):
        span = nxt.started - first.started
        if span > 0:
            duties.append((first.finished - first.started) / span)
    budget = float(mod.BATCH_CPU_BUDGET)
    mean = sum(duties) / len(duties) if duties else 0.0
    rel = abs(mean - budget) / budget if budget else 99.0
    add(done and len(kids) >= 3 and len(duties) >= 3,
        'budget: o laco correu >= 3 blocos',
        'done=%d kids=%d intervalos=%d' % (queue.stats()['done'], len(kids),
                                           len(duties)))
    add(duties and rel <= TOLERANCE,
        'budget: a taxa de servico fica no orcamento (+-40%)',
        'medida=%.3f orcamento=%.3f rel=%.0f%% amostras=%s'
        % (mean, budget, rel * 100.0,
           ','.join('%.3f' % d for d in duties[:5])))
    says = [line for line in box['logs'] if line.startswith('BATCH_CPU_BUDGET')]
    add(bool(says) and all(tag in says[-1] for tag in
                           ('used_ms=', 'budget=', 'rate=')),
        'budget: o log diz os tres numeros',
        says[-1] if says else 'sem linha BATCH_CPU_BUDGET')
    as_dict = ex.as_dict()
    add(abs(float(as_dict.get('duty') or 0.0) - budget) <= 0.02
        and float(as_dict.get('budget') or 0.0) == budget,
        'budget: a contabilidade interna do executor fecha no orcamento',
        'as_dict duty=%s budget=%s' % (as_dict.get('duty'),
                                       as_dict.get('budget')))
    return mean


def arm_yield(mod, path):
    """(2) O CEDER CONTINUA: o filho morre e o bloco volta a' fila."""
    ex, queue, box = make_executor(mod, path, level='leve', hang=True)
    manifest = enqueue(mod, queue, 1)[0]
    entry_id = str(manifest['id'])

    def rise(child):
        if child.polls >= 3:
            box['level'] = 'alta'

    def spawn(cmd):
        child = FakeChild(hang=True)
        child.on_poll = rise
        box['kids'].append(child)
        box['cmds'].append(list(cmd))
        return child

    ex._spawn = spawn
    state, detail = ex.step()
    entry = [e for e in queue.entries if e['id'] == entry_id][0]
    kid = box['kids'][-1] if box['kids'] else None
    add(state == 'yield' and ex.yields == 1,
        'yield: a carga a subir a meio faz CEDER',
        'state=%s detail=%s yields=%d' % (state, detail, ex.yields))
    add(kid is not None and kid.killed,
        'yield: o filho do lote e MORTO',
        'killed=%s' % (getattr(kid, 'killed', None),))
    add(entry['state'] == 'queued' and int(entry.get('attempts') or 0) == 0,
        'yield: o bloco volta a fila e o ceder nao conta como falha',
        'state=%s attempts=%s' % (entry['state'], entry.get('attempts')))
    add(queue.stats()['pending_s'] > 0,
        'yield: o audio continua na fila',
        'pending_s=%s' % queue.stats()['pending_s'])


def arm_stop(mod, path):
    """(3) UM STOP NAO DEIXA FILHO VIVO, e nao perde o bloco."""
    ex, queue, box = make_executor(mod, path, hang=True)
    manifest = enqueue(mod, queue, 1)[0]
    entry_id = str(manifest['id'])
    ex.start()
    try:
        started = wait_for(lambda: bool(box['kids'])
                           and box['kids'][-1].started is not None, 5.0)
        ex.stop()
        ex.join(5.0)
    finally:
        ex.stop()
        ex.join(5.0)
    kid = box['kids'][-1] if box['kids'] else None
    entry = [e for e in queue.entries if e['id'] == entry_id][0]
    add(started and not ex.is_alive(),
        'stop: o fio do executor termina',
        'arrancou=%s vivo=%s' % (started, ex.is_alive()))
    add(kid is not None and kid.killed and getattr(ex, '_child', None) is None,
        'stop: nenhum filho fica vivo',
        'killed=%s _child=%r' % (getattr(kid, 'killed', None),
                                 getattr(ex, '_child', None)))
    add(entry['state'] == 'queued' and queue.stats()['inflight'] == 0,
        'stop: o bloco volta a fila (nada fica inflight)',
        'state=%s inflight=%d' % (entry['state'], queue.stats()['inflight']))


def arm_env(mod, path):
    """(4) O TECTO DE FIOS VIAJA NA ENV DO FILHO -- os dois caminhos."""
    want = str(int(mod.BATCH_CHILD_THREADS))
    env = mod.child_env()
    add(all(env.get(key) == want for key in mod.THREAD_ENV_KEYS),
        'env: o filho leva o tecto de fios em todas as chaves',
        ','.join('%s=%s' % (key, env.get(key)) for key in mod.THREAD_ENV_KEYS))

    # O CAMINHO REAL DE ARRANQUE: e' o `Popen` que recebe a env, nao um dicionario
    # que o oraculo construiu ao lado. Sem isto, um `_spawn_below_normal` que
    # esquecesse a env passaria neste braco.
    captured = {}
    real_popen = mod.subprocess.Popen

    class _Recorder(object):
        returncode = 0

        def communicate(self, timeout=None):
            return '', ''

        def kill(self):
            pass

    def fake_popen(cmd, **kwargs):
        captured['cmd'] = list(cmd)
        captured['env'] = kwargs.get('env')
        captured['kwargs'] = kwargs
        return _Recorder()

    mod.subprocess.Popen = fake_popen
    try:
        mod._spawn_below_normal([sys.executable, '-c', 'pass'])
    finally:
        mod.subprocess.Popen = real_popen
    launched = captured.get('env') or {}
    add(launched.get('OMP_NUM_THREADS') == want,
        'env: `_spawn_below_normal` passa o tecto ao Popen',
        'OMP_NUM_THREADS=%s quer=%s' % (launched.get('OMP_NUM_THREADS'), want))
    add(bool(captured.get('cmd')) and captured['kwargs'].get('env') is not None,
        'env: o arranque continua a passar cmd e env (nao so a env)',
        'cmd=%r' % (captured.get('cmd'),))

    # O DRIVER: o mesmo numero chega ao `load_backend` (torch.set_num_threads /
    # onnxruntime), em vez de um literal repetido no `--threads`.
    default_threads = inspect.signature(
        mod.transcribe_payload).parameters['threads'].default
    add(default_threads is None,
        'env: `transcribe_payload` deriva os fios da env e nao de um literal',
        'threads=%r' % (default_threads,))
    saved = os.environ.get('OMP_NUM_THREADS')
    os.environ['OMP_NUM_THREADS'] = '3'
    try:
        seen = mod._env_threads()
    finally:
        if saved is None:
            os.environ.pop('OMP_NUM_THREADS', None)
        else:
            os.environ['OMP_NUM_THREADS'] = saved
    add(seen == 3, 'env: a env manda sobre a constante no driver',
        '_env_threads()=%r' % (seen,))

    ex, _queue, _box = make_executor(mod, path)
    add(ex.child_env.get('OMP_NUM_THREADS') == want
        and float(ex.budget) == float(mod.BATCH_CPU_BUDGET),
        'env: o executor de producao leva env e orcamento declarados',
        'OMP=%s budget=%s' % (ex.child_env.get('OMP_NUM_THREADS'), ex.budget))


def neg_arm():
    """A COPIA sem a espera do orcamento: o braco 1 TEM de falhar.

    E' o comportamento ANTIGO (o laco comeca o bloco seguinte assim que o
    anterior acaba), reposto por uma linha. Se o braco continuar verde sem ela,
    ele nao mede a espera -- mede outra coisa.
    """
    tmp = tempfile.mkdtemp(prefix='bq-ceiling-neg-')
    try:
        src = io.open(MODULE, encoding='utf-8').read()
        old = ('            if state in (\'done\', \'failed\'):\n'
               '                self._pace()\n')
        if old not in src:
            print('NEG-ARM: IMPOSSIVEL -- a chamada `self._pace()` nao esta no '
                  'laco do `run()` (o texto mudou)')
            return 1
        copy = os.path.join(tmp, 'batch_queue_mutant_no_pace.py')
        with io.open(copy, 'w', encoding='utf-8', newline='') as handle:
            handle.write(src.replace(
                old, '            if state in (\'done\', \'failed\'):\n'
                     '                pass  # MUTANTE: sem espera de orcamento\n', 1))
        mod = load_module(copy)
        path = os.path.join(tmp, 'queue')
        os.makedirs(path, exist_ok=True)
        print('MUTANT sem-espera: o laco volta a dormir 0 (o defeito antigo)')
        mean = arm_budget(mod, path)
        caught = not all(ok for _name, ok, _detail in RESULTS)
        print('NEG-ARM taxa_medida=%.3f orcamento=%.3f %s'
              % (mean, float(mod.BATCH_CPU_BUDGET),
                 'APANHADO' if caught else 'SOBREVIVEU'))
        print('NEG-ARM: %s' % ('PASS' if caught else 'FAIL'))
        return 1 if caught else 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    if '--neg-arm' in sys.argv:
        return neg_arm()
    base = tempfile.mkdtemp(prefix='bq-ceiling-oracle-')
    mod = load_module(MODULE)
    try:
        add(isinstance(getattr(mod, 'BATCH_CPU_BUDGET', None), float)
            and 0.0 < float(mod.BATCH_CPU_BUDGET) < 1.0,
            'budget: o orcamento e um numero declarado',
            'BATCH_CPU_BUDGET=%r' % (getattr(mod, 'BATCH_CPU_BUDGET', None),))
        add(isinstance(getattr(mod, 'BATCH_CHILD_THREADS', None), int)
            and int(mod.BATCH_CHILD_THREADS) >= 1,
            'env: o tecto de fios e um inteiro declarado',
            'BATCH_CHILD_THREADS=%r'
            % (getattr(mod, 'BATCH_CHILD_THREADS', None),))
        for index, fn in enumerate((arm_budget, arm_yield, arm_stop)):
            path = os.path.join(base, 'q%d' % index)
            os.makedirs(path, exist_ok=True)
            fn(mod, path)
        env_path = os.path.join(base, 'qenv')
        os.makedirs(env_path, exist_ok=True)
        arm_env(mod, env_path)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    bad = [name for name, ok, _detail in RESULTS if not ok]
    print('VERDICT: %s (%d/%d)'
          % ('PASS' if not bad else 'FAIL', len(RESULTS) - len(bad),
             len(RESULTS)))
    return 0 if not bad else 1


if __name__ == '__main__':
    raise SystemExit(main())
