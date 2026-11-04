# NO-BUG: A FILA CRESCE POR FORA -- o executor tem de ver o que outro processo enfileirou. -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""A FILA CRESCE POR FORA -- o executor tem de ver o que outro processo enfileirou.

O DEFEITO MEDIDO (2026-11-03, instancia viva pid 41760):

  `BATCH_QUEUE_STARTED dir=I:\\cc-tmp\\sotto-batch-queue poll_s=10`
  um bloco enfileirado por OUTRO processo (`enqueue_f32` -> manifesto + `.f32`
  no MESMO directorio) ficou `queued` para sempre, com o nivel em `leve` e o
  `next_entry()` de uma instancia nova a devolve-lo. Causa: `BatchQueue.refresh()`
  so' corria no `__init__`, logo o laco do executor comparava um retrato do
  arranque com uma pasta que ja' tinha mudado -- e um bloco que ninguem ve' e'
  audio perdido, exactamente o audio que o spool do worker larga quando larga o
  modelo.

O QUE ESTE ORACULO JULGA (o executor REAL, sem dispositivo de audio, sem parakeet):

  1. `foreign-enqueue-is-picked-up` -- executado, transcrito (`done`) e UMA vez.
  2. `no-work-stays-idle`            -- sem bloco, nenhum filho (o `refresh` nao
                                       inventa trabalho).
  3. `level-above-leve-does-not-run` -- com `alta`, o bloco NAO corre.
  4. `inflight-recovers-once`        -- um `inflight` de um processo morto volta a
                                       `queued` e corre UMA vez, nunca duas.

`--neg-arm`: muta uma COPIA de `app/webview/batch_queue.py` para `_refresh_queue`
ser um no-op e exige o arm 1 a falhar (sem pickup). Um oraculo cujo mutante passa
nao prova nada.
"""
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
MODULE = os.path.join(WEBVIEW, 'batch_queue.py')
sys.path.insert(0, WEBVIEW)


def load_module(path):
    spec = importlib.util.spec_from_file_location('bq_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeChild(object):
    """O filho do executor, sem parakeet: devolve a linha JSON que o driver devolve."""

    def __init__(self, out):
        self.out = out
        self.returncode = None
        self.killed = False

    def communicate(self, timeout=None):
        self.returncode = 0
        return self.out, ''

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.returncode


def make_executor(mod, path, level='leve', spawns=None, poll_s=0.2):
    queue = mod.BatchQueue(path=path, log_fn=lambda _m: None)
    spawns = spawns if spawns is not None else []

    def spawn(cmd):
        spawns.append(list(cmd))
        return FakeChild('{"type":"caption","text":"ok"}\n'
                         '{"type":"result","text":"ok"}\n')

    # A ADOPCAO APONTA PARA O DIRECTORIO DESTE BRACO. Sem isto o executor
    # adoptava os spools REAIS de `TMPDIR` na primeira volta (`_last_adopt`
    # arranca em 0.0) e um braco com a fila vazia via `spawns=1`; foi medido
    # antes desta porta existir.
    spool = os.path.join(path, 'spool')
    os.makedirs(spool, exist_ok=True)
    ex = mod.BatchExecutor(queue=queue, log_fn=lambda _m: None,
                           level_fn=lambda: level, spawn=spawn, poll_s=poll_s,
                           child_poll_s=0.2, adopt_every_s=3600.0,
                           adopt_roots=[spool])
    return ex, queue, spawns


def wait_for(predicate, timeout=6.0, step=0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(step)
    return False


def enqueue_foreign(mod, path, seconds=0.5):
    """Outro processo: uma instancia SEPARADA do BatchQueue (o worker faz assim)."""
    other = mod.BatchQueue(path=path, log_fn=lambda _m: None)
    raw = b'\x00\x00\x00\x00' * int(16000 * seconds)
    return other.enqueue_f32(raw, source='foreign-probe')


def arm_foreign_pickup(mod, path):
    ex, queue, spawns = make_executor(mod, path)
    ex.start()
    try:
        manifest = enqueue_foreign(mod, path)
        if manifest is None:
            return False, 'o enfileiramento falhou'
        ok = wait_for(lambda: bool(spawns) and queue.stats()['done'] >= 1, 6.0)
        expected = os.path.basename(queue.payload_path(str(manifest['id'])))
        used = [c[-2] if len(c) > 1 else '' for c in spawns]
        named = any(str(expected) in str(x) for x in used) or any(
            str(manifest['id']) in str(x) for x in spawns)
        return bool(ok and named and len(spawns) == 1), (
            'pickup=%s spawns=%d done=%d manifesto_no_comando=%s'
            % (ok, len(spawns), queue.stats()['done'], named))
    finally:
        ex.stop()


def arm_no_work(mod, path):
    ex, queue, spawns = make_executor(mod, path)
    ex.start()
    try:
        time.sleep(1.0)
        return (not spawns and queue.stats()['queued'] == 0), (
            'spawns=%d' % len(spawns))
    finally:
        ex.stop()


def arm_level_blocks(mod, path):
    ex, queue, spawns = make_executor(mod, path, level='alta')
    ex.start()
    try:
        enqueue_foreign(mod, path)
        time.sleep(1.2)
        return (not spawns and queue.stats()['queued'] == 1), (
            'spawns=%d queued=%d' % (len(spawns), queue.stats()['queued']))
    finally:
        ex.stop()


def arm_inflight_once(mod, path):
    """Um `inflight` de um processo morto: recuperado e corrido UMA vez."""
    ex, queue, spawns = make_executor(mod, path)
    manifest = enqueue_foreign(mod, path)
    if manifest is None:
        return False, 'o enfileiramento falhou'
    queue.claim(str(manifest['id']))          # morre a meio: fica `inflight`
    ex.start()
    try:
        ok = wait_for(lambda: queue.stats()['done'] >= 1, 6.0)
        time.sleep(0.6)                       # se fosse correr duas vezes, seria agora
        return bool(ok and len(spawns) == 1), (
            'done=%d spawns=%d %s' % (queue.stats()['done'], len(spawns),
                                      'ok' if ok else 'nao recuperou'))
    finally:
        ex.stop()


def arm_run_loop_adopts(mod, path):
    """O LACO REAL (`run()`) corre a ADOPCAO, e nao so' o `step()`.

    O DEFEITO QUE ESTE BRACO EXISTE PARA APANHAR (medido no dono, 2026-11-03,
    pid 4992): `run()` chamava `self.queue.adopt_dead_spools(self.adopt_roots)`
    e `__init__` nunca atribuia `self.adopt_roots`. O `AttributeError` cai no
    `try` do laco ANTES do `step()`, portanto (a) a adopcao nunca acontecia --
    o audio que um worker morto largou ficava sem transcricao para sempre -- e
    (b) a volta em que ele caia perdia um passo da fila.

    Nenhum braco apanhava isto porque todos chamavam `step()` directamente: o
    defeito vivia entre o `__init__` e o `run()`, e um oraculo que nunca corre o
    `run()` nao ve' um campo que so' o `run()` le'.
    """
    ex, queue, spawns = make_executor(mod, path)
    # Um spool MORTO no directorio que a adopcao aponta: e' a unica forma de
    # provar que a chamada ACONTECEU (sem isto, um `adopt_roots` a `None`
    # devolveria 0 e o braco passaria por ausencia).
    # O SPOOL TEM A FORMA QUE A ADOPCAO PROCURA (2026-11-03): o directorio
    # leva o pid no NOME (`sotto-pending-audio-<pid>`), os ficheiros comecam por
    # `pending-` e acabam em `.f32`, e a idade tem de passar `ADOPT_MIN_AGE_S`
    # -- sem isto o braco mede uma pasta que a regra REALMENTE ignora e grita
    # falso. O pid 999999 nao existe (`_pid_alive` devolve False).
    # O CAMPO E' LIDO COM `getattr` E A AUSENCIA E' UM RED, nao um traceback: no
    # mutante (`self.adopt_roots` nunca atribuido) este braco tem de dar RED com
    # o nome do defeito, e nao rebentar o oraculo.
    if getattr(ex, 'adopt_roots', None) is None:
        return False, ('adopt_roots nunca e atribuido no __init__ -- o `run()` '
                       'leria um campo que nao existe')
    spool = os.path.join(path, mod.SPOOL_DIR_PREFIX + '999999')
    os.makedirs(spool, exist_ok=True)
    full = os.path.join(spool, mod.SPOOL_FILE_GLOB + '0001' + mod.SPOOL_SUFFIX)
    with io.open(full, 'wb') as handle:
        handle.write(b'\x00\x00\x00\x00' * 6400)
    old = time.time() - (mod.ADOPT_MIN_AGE_S + 30.0)
    os.utime(full, (old, old))
    # ESTE braco aponta a adopcao ao SEU directorio (a forma do nome importa).
    ex.adopt_roots = [spool]
    errors = []
    ex.log = lambda m: errors.append(m)
    ex.adopt_every_s = 0.0          # a primeira volta do laco adopta
    ex.start()
    try:
        got = wait_for(lambda: queue.stats()['queued'] + queue.stats()['done'] > 0,
                       timeout=6.0)
        # SO' O ERRO CONTA: `BATCH_EXEC_DONE`/`BATCH_EXEC_START` sao log normal --
        # um braco que trata log normal como falha mede a verbosidade do modulo.
        failures = [m for m in errors if 'BATCH_EXEC_ERROR' in m]
        ok = got and not failures
        st = queue.stats()
        return ok, ('queued=%d inflight=%d done=%d failed=%d errors=%r'
                    % (st['queued'], st['inflight'], st['done'],
                       st['failed'], failures[:2]))
    finally:
        ex.stop()


def neg_arm_mutant():
    """A COPIA com o `refresh` desligado: o arm 1 tem de FALHAR."""
    tmp = tempfile.mkdtemp(prefix='bq-neg-')
    try:
        src = io.open(MODULE, encoding='utf-8').read()
        old = '    def _refresh_queue(self):'
        if old not in src:
            return None, 'o mutante nao encontrou `_refresh_queue` -- o detector nao serve'
        mutated = src.replace(
            old,
            '    def _refresh_queue(self):\n        return  # MUTANTE: sem releitura\n',
            1)
        copy = os.path.join(tmp, 'batch_queue_mutant.py')
        with io.open(copy, 'w', encoding='utf-8', newline='') as handle:
            handle.write(mutated)
        mod = load_module(copy)
        path = os.path.join(tmp, 'queue')
        os.makedirs(path, exist_ok=True)
        ok, detail = arm_foreign_pickup(mod, path)
        return (not ok), detail
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def neg_arm_adopt_field():
    """A COPIA sem a atribuicao de `adopt_roots`: o braco do laco tem de FALHAR.

    O MESMO DEFEITO DE PRODUCAO, posto de volta: uma linha (`self.adopt_roots =
    adopt_roots`) apagada numa copia. Se o braco 5 continuar verde sem ela, ele
    nao mede o campo -- mede outra coisa.
    """
    tmp = tempfile.mkdtemp(prefix='bq-neg-adopt-')
    try:
        src = io.open(MODULE, encoding='utf-8').read()
        old = '        self.adopt_roots = adopt_roots'
        if old not in src:
            return None, 'o mutante nao encontrou `self.adopt_roots = adopt_roots`'
        mutated = src.replace(old, '        pass  # MUTANTE: campo nunca atribuido', 1)
        copy = os.path.join(tmp, 'batch_queue_mutant_adopt.py')
        with io.open(copy, 'w', encoding='utf-8', newline='') as handle:
            handle.write(mutated)
        mod = load_module(copy)
        path = os.path.join(tmp, 'queue')
        os.makedirs(path, exist_ok=True)
        ok, detail = arm_run_loop_adopts(mod, path)
        return (not ok), detail
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    base = tempfile.mkdtemp(prefix='bq-oracle-')
    mod = load_module(MODULE)
    results = []
    try:
        arms = (('foreign-enqueue-is-picked-up', arm_foreign_pickup),
                ('no-work-stays-idle', arm_no_work),
                ('level-above-leve-does-not-run', arm_level_blocks),
                ('inflight-recovers-once', arm_inflight_once),
                ('run-loop-adopts-dead-spool', arm_run_loop_adopts))
        for index, (name, fn) in enumerate(arms):
            path = os.path.join(base, 'q%d' % index)
            os.makedirs(path, exist_ok=True)
            ok, detail = fn(mod, path)
            results.append((name, ok, detail))
            print('%-32s %s %s' % (name, 'GREEN' if ok else 'RED', detail))
    finally:
        shutil.rmtree(base, ignore_errors=True)

    if '--neg-arm' in sys.argv:
        caught, detail = neg_arm_mutant()
        if caught is None:
            print('NEG-ARM      FAIL %s' % detail)
            return 1
        print('NEG-ARM refresh-desligado %s %s'
              % ('GREEN (o defeito volta)' if caught else 'FAIL', detail))
        caught2, detail2 = neg_arm_adopt_field()
        if caught2 is None:
            print('NEG-ARM      FAIL %s' % detail2)
            return 1
        print('NEG-ARM adopt-roots-apagado %s %s'
              % ('GREEN (o defeito volta)' if caught2 else 'FAIL', detail2))
        caught = bool(caught) and bool(caught2)
        bad = [n for n, ok, _ in results if not ok]
        # CONTRATO DA BATERIA: rc=1 = o mutante foi apanhado.
        print('NEG-ARM: %s' % ('PASS' if (caught and not bad) else 'FAIL'))
        return 1 if (caught and not bad) else 0

    bad = [n for n, ok, _ in results if not ok]
    print('VERDICT: %s (%d/%d arms)'
          % ('PASS' if not bad else 'FAIL', len(results) - len(bad), len(results)))
    return 0 if not bad else 1


if __name__ == '__main__':
    raise SystemExit(main())
