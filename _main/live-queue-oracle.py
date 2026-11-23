"""ORACLE: A FILA DE AUDIO VIVO NUNCA TRANSCREVE O PASSADO.

O DONO, 2026-10-30, verbatim:
    *"eu tenho audio tocando, com pessoa falando, e eu to vendo legenda LIGANDO
    dezenas de segundos depois. encontra a porra do gargalo e arruma. se um audio
    tem fala, e pra ter transcricao NA HORA. ACABOU. E' REGRA. LEI. COM PROVA."*

O DEFEITO, medido por leitura a 2026-10-30 (`worker/sotto_worker.py`):
    `audio_q = queue.Queue(maxsize=256)`  -> 25,6 s de audio a 100 ms por bloco
    `try: audio_q.put_nowait(block)` / `except queue.Full: queue_drops += 1`
O overflow deitava fora o bloco RECEM-CAPTURADO e deixava na fila os 25,6 s mais
ANTIGOS. O resultado nao e' "a legenda atrasa": e' a legenda do passado, uma
fila FIFO de audio que o consumidor ia transcrever em ordem.

A REGRA (novo `worker/live_queue.py`): tecto em SEGUNDOS, e quando ele passa e'
o bloco mais ANTIGO que sai. O audio de agora vale mais do que o de ha 2 s.

ARMS: a aritmetica do tecto, o comportamento real da `queue.Queue` ao encher,
o controle com a regra ANTIGA (`put_nowait` + drop do NOVO, que perde o agora),
o wiring no worker vivo e os totais exactos de blocos/amostras por motivo.

O CONTROLE NEGATIVO (`--neg-arm`) inverte a politica numa COPIA do modulo e exige
que o oraculo fique VERMELHO.

Exit codes: 0 PASS, 1 FAIL, 2 setup.
"""
# NO-BUG: instrumento da fila AO VIVO: nenhum bloco de audio pode ser perdido entre a captura e a transcricao; julga o modulo, nao o produto
from __future__ import annotations

import ast
import io
import os
import queue
import shutil
import sys
import threading
import tempfile
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
WORKER = os.path.join(REPO, "worker")
sys.path.insert(0, WORKER)

RESULTS = []


def arm(name, real, want):
    ok = real == want
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] arm: {name}")
    if not ok:
        print(f"       real = {real!r}\n       want = {want!r}")


def old_policy(q, block, cap):
    """A REGRA DE ANTES: deita fora o bloco NOVO quando a fila esta' cheia."""
    try:
        q.put_nowait(block)
        return 0
    except queue.Full:
        return 1


class AudioBlock:
    def __init__(self, samples):
        self.size = int(samples)


def queue_eviction_checks(LQ):
    """Exercise production queue policy and its fixed, per-reason accounting."""
    checks = []
    counters = {"queue_evicted": 0}
    q = queue.Queue()
    for _ in range(30):
        block = AudioBlock(100)
        evicted, dropped, samples = LQ.enqueue_live_detailed(q, block, 20)
        if evicted:
            LQ.record_eviction(counters, "live-2s-cap", evicted, samples)
    row = counters["queue_eviction_reasons"]["live-2s-cap"]
    checks.extend([
        ("2s-cap-evicts-exact-blocks", row["blocks"] == 10),
        ("2s-cap-evicts-exact-samples", row["samples"] == 1000),
        ("2s-cap-keeps-capacity-unchanged", q.qsize() == 20),
        ("aggregate-evictions-match-reasons", counters["queue_evicted"] == 10),
    ])

    first = {"queue_evicted": 0}
    LQ.record_eviction(first, "first-tap-unready", 1, 640)
    first_row = first["queue_eviction_reasons"]["first-tap-unready"]
    checks.extend([
        ("first-tap-stale-backlog-block-count", first_row["blocks"] == 1),
        ("first-tap-stale-backlog-sample-count", first_row["samples"] == 640),
    ])

    stale_q = queue.Queue()
    stale_q.put_nowait(AudioBlock(400))
    stale_q.put_nowait(AudioBlock(800))
    stale, stale_samples = LQ.discard_stale_generation(stale_q, AudioBlock(160))
    generation = {"queue_evicted": 0}
    LQ.record_eviction(generation, "device-change-stale-generation", stale, stale_samples)
    stale_row = generation["queue_eviction_reasons"]["device-change-stale-generation"]
    checks.extend([
        ("device-change-discards-current-and-stale-backlog", stale == 3 and stale_q.empty()),
        ("device-change-counts-exact-samples", stale_row["samples"] == 1360),
    ])
    return checks


def eviction_wiring_checks(worker_source):
    """Source gate: each real production discard site must name its reason."""
    needles = {
        "live-cap": 'record_eviction(counters, reason, evicted, evicted_samples)',
        "first-tap": 'record_eviction(counters, reason, 1, samples)',
        "device-change": 'record_eviction(counters, reason, zero, zero_samples)',
    }
    return {name: needle in worker_source for name, needle in needles.items()}


def concurrent_eviction_checks(LQ):
    """Prove exact producer/consumer totals and lock-coherent snapshots."""
    counters = {
        "queue_evicted": 0,
        "queue_eviction_reasons": {
            reason: {"blocks": 0, "samples": 0}
            for reason in LQ.QUEUE_EVICTION_REASONS
        },
        "queue_eviction_lock": threading.Lock(),
    }
    start = threading.Barrier(3)
    failures = []

    def record_many(reason):
        try:
            start.wait(timeout=2)
            for _ in range(1000):
                LQ.record_eviction(counters, reason, 1, 640)
        except Exception as exc:  # noqa: BLE001 -- report setup/runtime failure
            failures.append(type(exc).__name__)

    producer = threading.Thread(target=record_many, args=("live-2s-cap",), daemon=True)
    consumer = threading.Thread(target=record_many, args=("first-tap-unready",), daemon=True)
    producer.start()
    consumer.start()
    start.wait(timeout=2)
    producer.join(timeout=3)
    consumer.join(timeout=3)
    completed = not producer.is_alive() and not consumer.is_alive() and not failures
    snapshot = LQ.eviction_snapshot(counters)
    exact = (
        completed
        and snapshot["blocks"] == 2000
        and snapshot["reasons"]["live-2s-cap"] == {"blocks": 1000, "samples": 640000}
        and snapshot["reasons"]["first-tap-unready"] == {"blocks": 1000, "samples": 640000}
    )

    # Hold the production lock and prove the receipt snapshot waits for it.
    class ObservedLock:
        def __init__(self):
            self.raw = threading.Lock()
            self.requested = threading.Event()

        def acquire(self):
            return self.raw.acquire()

        def release(self):
            self.raw.release()

        def __enter__(self):
            self.requested.set()
            self.raw.acquire()
            return self

        def __exit__(self, _type, _value, _traceback):
            self.raw.release()

    lock = ObservedLock()
    counters["queue_eviction_lock"] = lock
    entered = threading.Event()
    finished = threading.Event()
    observed = {}

    def take_snapshot():
        entered.set()
        observed.update(LQ.eviction_snapshot(counters))
        finished.set()

    lock.acquire()
    reader = threading.Thread(target=take_snapshot, daemon=True)
    reader.start()
    reader_started = entered.wait(1) and lock.requested.wait(1)
    blocked_by_writer_lock = reader_started and not finished.is_set()
    lock.release()
    reader.join(timeout=2)
    coherent = blocked_by_writer_lock and not reader.is_alive() and observed == snapshot
    return [
        ("producer-consumer-concurrent-counts-exact", exact),
        ("receipt-snapshot-shares-counter-lock", coherent),
    ]


def file_tap_flow_checks(LQ, worker_source):
    """Run the actual FileTap pump method through the real bounded queue policy."""
    import ast

    try:
        tree = ast.parse(worker_source)
        tap_class = next(node for node in tree.body
                         if isinstance(node, ast.ClassDef) and node.name == "FileTap")
        pump_node = next(node for node in tap_class.body
                         if isinstance(node, ast.FunctionDef) and node.name == "_pump")
        finite_node = next(node for node in tree.body
                           if isinstance(node, ast.FunctionDef)
                           and node.name == "finite_file_tap_state")
        pump_source = textwrap.dedent(ast.get_source_segment(worker_source, pump_node))
        finite_source = ast.get_source_segment(worker_source, finite_node)
    except Exception as exc:  # noqa: BLE001 -- missing source seam is a red control
        return [("actual-FileTap-EOF-source-available", type(exc).__name__, "available")]

    class FakeBlock:
        def __init__(self, start, stop):
            self.start = int(start)
            self.stop = int(stop)
            self.size = max(0, self.stop - self.start)

    class FakePcm:
        size = 190400

        def __getitem__(self, section):
            start = int(section.start or 0)
            stop = min(int(section.stop or self.size), self.size)
            return FakeBlock(start, stop)

    class FakeNumpy:
        float32 = object()

        @staticmethod
        def ascontiguousarray(block, dtype=None):
            return block

    class FakeClock:
        def __init__(self):
            self.now = 0.0
            self.pace_calls = 0
            self.on_pace = None

        def monotonic(self):
            return self.now

        def sleep(self, seconds):
            self.now += float(seconds)
            self.pace_calls += 1
            if self.on_pace is not None:
                self.on_pace()

    clock = FakeClock()
    eof_events = []
    q = queue.Queue(maxsize=256)
    callback_blocks = []
    consumed_blocks = []
    evictions = {"queue_evicted": 0, "queue_eviction_reasons": {}}
    dropped = 0
    max_depth = 0

    class FakeStop:
        @staticmethod
        def is_set():
            return False

    class FakeStream:
        _stop = FakeStop()

    class TapShim:
        def __init__(self):
            self.pcm = FakePcm()
            self.np = FakeNumpy()
            self.on_block = self._on_block
            self.block = 640
            self.block_ms = 40
            self.once = True
            self.done = threading.Event()
            self.stream = FakeStream()
            self.rate = 16000

        def _on_block(self, block):
            nonlocal dropped, max_depth
            callback_blocks.append((block.start, block.stop))
            evicted, new_drops, evicted_samples = LQ.enqueue_live_detailed(
                q, block, LQ.max_blocks(40))
            dropped += new_drops
            if evicted:
                LQ.record_eviction(evictions, "live-2s-cap", evicted, evicted_samples)
            max_depth = max(max_depth, q.qsize())

        def consume_one(self):
            block, empty = LQ.dequeue_live(q, timeout=0)
            if not empty:
                consumed_blocks.append(block)

    tap = TapShim()
    namespace = {
        "FileTap": TapShim,
        "time": clock,
        "emit": lambda **row: eof_events.append(row),
    }
    exec(compile(pump_source, "<FileTap._pump source>", "exec"), namespace)
    exec(compile(finite_source, "<finite_file_tap_state source>", "exec"), namespace)
    # `_pump` itself is the parsed production method and gets the same callback
    # object as a stream; only timing and the downstream consumer are synthetic.
    namespace["FileTap"]._pump = namespace["_pump"]
    def consume_scheduled_block():
        if len(callback_blocks) > 16:
            tap.consume_one()
    clock.on_pace = consume_scheduled_block
    namespace["FileTap"]._pump(tap)

    # A fake consumer starts after a 16-block open/dispatch delay, then keeps up
    # at one dequeue per scheduled 40 ms tick. This creates a bounded queue
    # backlog without pausing, speeding, or looping the one-shot source.
    # `_pump` already ran; consume the 17-block tail at 20 ms per block so the
    # EOF-to-drained bound is checked independently of a model.
    queued_at_eof = q.qsize()
    drain_state_before = namespace["finite_file_tap_state"](tap, False)
    drain_elapsed_s = 0.0
    while True:
        block, empty = LQ.dequeue_live(q, timeout=0)
        if empty:
            break
        consumed_blocks.append(block)
        drain_elapsed_s += 0.020
    consumed = consumed_blocks
    source_samples = sum(stop - start for start, stop in callback_blocks)
    consumed_samples = sum(block.size for block in consumed)
    continuous = (
        bool(callback_blocks) and callback_blocks[0][0] == 0
        and callback_blocks[-1][1] == FakePcm.size
        and all(left[1] == right[0]
                for left, right in zip(callback_blocks, callback_blocks[1:]))
    )
    consumed_contiguous = (
        bool(consumed) and consumed[0].start == 0
        and consumed[-1].stop == FakePcm.size
        and all(left.stop == right.start for left, right in zip(consumed, consumed[1:]))
    )
    expected_audio_s = FakePcm.size / 16000.0
    no_false_rotation = (
        [row.get("state") for row in eof_events] == ["file-tap-eof"]
        and tap.done.is_set()
        and drain_state_before == "drain"
        and namespace["finite_file_tap_state"](tap, True) == "complete"
    )
    drain_mutant_source = finite_source.replace(
        'return "complete" if file_drained else "drain"',
        'return "monitor"', 1)
    mutant_namespace = {"FileTap": TapShim}
    exec(compile(drain_mutant_source, "<mutated finite_file_tap_state>", "exec"),
         mutant_namespace)
    watchdog_mutant_caught = (
        drain_mutant_source != finite_source
        and mutant_namespace["finite_file_tap_state"](tap, False) != "drain"
    )
    return [
        ("actual-FileTap-callbacks-298-of-298", len(callback_blocks), 298),
        ("actual-FileTap-samples-contiguous-and-nonrepeating", continuous, True),
        ("actual-live-queue-consumes-298-of-298-blocks", len(consumed), 298),
        ("actual-live-queue-consumes-all-190400-samples", consumed_samples, 190400),
        ("actual-live-queue-consumes-contiguous-source-order", consumed_contiguous, True),
        ("actual-2s-cap-no-evictions-or-drops", (evictions["queue_evicted"], dropped), (0, 0)),
        ("actual-FileTap-max-depth-stays-under-50-block-cap", max_depth <= 50, True),
        ("actual-FileTap-cadence-does-not-stretch-or-loop",
         abs(expected_audio_s - clock.now) <= 0.040 and clock.pace_calls == 297, True),
        ("actual-FileTap-simulated-scheduled-seconds", round(clock.now, 3), 11.88),
        ("actual-FileTap-EOF-reports-exact-source-samples",
         (eof_events[-1].get("samples"), eof_events[-1].get("mode")), (190400, "once")),
        ("actual-FileTap-buffered-tail-blocks", queued_at_eof, 17),
        ("actual-FileTap-EOF-drain-simulated-ms", round(drain_elapsed_s * 1000, 3), 340.0),
        ("actual-FileTap-EOF-drain-at-most-606ms", drain_elapsed_s <= 0.606, True),
        ("actual-FileTap-drain-does-not-falsely-rotate", no_false_rotation, True),
        ("production-asr-consumer-uses-dequeue-helper",
         "_live_queue.dequeue_live(audio_q, timeout=0.25)" in worker_source, True),
        ("file-tap-EOF-watchdog-reopen-mutant-is-detected", watchdog_mutant_caught, True),
    ]


# ── A ESPERA (`PendingAudio`): o audio que nenhum motor leu ──────────────────
#: Quantos blocos de 100 ms a corrida empurra. 100 blocos = 10 s de audio, e a
#: RAM da espera e' posta a 1 s: a corrida TEM de passar pelo spool para o
#: oraculo medir a ordem a atravessar a fronteira RAM/disco.
PENDING_BLOCKS = 100
PENDING_BLOCK = 1600
PENDING_RAM_S = 1.0


def pending_checks(LQ, tmp, tag=""):
    """Os arms da ESPERA, executaveis contra o modulo REAL e contra um MUTANTE.

    Cada bloco leva um valor distinto (`i + 1`) para a ORDEM ser verificavel e
    nao descrita: uma espera que devolva os blocos baralhados devolve outra frase.
    """
    import numpy as np

    out = []

    def chk(name, real, want):
        out.append((real == want, tag + name, real, want))

    spool = os.path.join(tmp, "spool")
    pend = LQ.PendingAudio(rate=16000, ram_s=PENDING_RAM_S, spool_dir=spool,
                           log=lambda _m: None)
    for i in range(PENDING_BLOCKS):
        pend.add((np.full(PENDING_BLOCK, i + 1, dtype=np.float32)))
    counts = pend.counts()
    chk("a espera recebeu todos os blocos", counts["blocks_in"], PENDING_BLOCKS)
    chk("o audio esperado e' o que entrou (10 s)", counts["seconds"],
        round(PENDING_BLOCKS * PENDING_BLOCK / 16000.0, 3))
    chk("o transbordo foi para o DISCO, nao para o lixo", counts["spilled_blocks"] > 0, True)
    chk("nada foi deitado fora (`dropped`)", counts["dropped"], 0)
    chk("ainda nada foi entregue (`blocks_out`)", counts["blocks_out"], 0)
    chk("todos os blocos continuam a espera (RAM + disco)",
        counts["held_blocks"], PENDING_BLOCKS)

    held, samples = pend.take_all()
    chk("a entrega devolve TODOS os blocos", len(held), PENDING_BLOCKS)
    chk("a entrega devolve TODAS as amostras", samples, PENDING_BLOCKS * PENDING_BLOCK)
    chk("a ordem e' a de CHEGADA, a atravessar a RAM e o disco",
        [int(b[0]) for b in held], list(range(1, PENDING_BLOCKS + 1)))
    after = pend.counts()
    chk("depois da entrega a espera esta' a ZERO (drena)",
        (after["seconds"], after["held_blocks"]), (0.0, 0))
    chk("contagem: entradas == saidas", after["blocks_in"], after["blocks_out"])
    chk("contagem: saidas == blocos recebidos", after["blocks_out"], PENDING_BLOCKS)
    chk("o spool nao fica no disco depois de entregue",
        [n for n in (os.listdir(spool) if os.path.isdir(spool) else [])], [])

    # -- a DEVOLUCAO: o que foi tirado e nao transcrito volta para a FRENTE --
    back = LQ.PendingAudio(rate=16000, ram_s=PENDING_RAM_S, spool_dir=spool,
                           log=lambda _m: None)
    for i in range(5):
        back.add(np.full(PENDING_BLOCK, i + 1, dtype=np.float32))
    taken, _n = back.take_all()
    kept = back.requeue(taken[2:])
    again, _n2 = back.take_all()
    chk("a devolucao poe os blocos outra vez a espera", kept, 3)
    chk("e a ordem da devolucao e' a mesma (bloco 3 primeiro)",
        [int(b[0]) for b in again], [3, 4, 5])
    chk("a devolucao nao inventa entradas nem saidas",
        (back.counts()["blocks_in"], back.counts()["blocks_out"]), (5, 5))
    chk("e nada foi perdido no caminho de ida e volta", back.counts()["dropped"], 0)
    return out


def spool_checks(LQ, alive, tag=""):
    """Os arms dos SPOOLS IRMAOS, contra o modulo REAL e contra um MUTANTE.

    O defeito que estes arms fecham foi medido em 2026-11-05: cinco directorios
    `sotto-pending-audio-<pid>` de pids mortos, 51,9 MB, em `G:/Temp` -- a
    limpeza de arranque varria os FICHEIROS DE DENTRO do directorio que o proprio
    run acabara de criar, e nunca via os irmaos. Por isso a arm central e' um PAR:
    o irmao MORTO sai e o VIVO fica, no mesmo varrimento.
    """
    out = []

    def chk(name, real, want):
        out.append((real == want, tag + name, real, want))

    root = tempfile.mkdtemp(prefix="live-queue-spools-")
    try:
        def mk(pid, payload=4096):
            d = os.path.join(root, LQ.SPOOL_DIR_PREFIX + str(pid))
            os.makedirs(d, exist_ok=True)
            fh = io.open(os.path.join(d, "pending-%d-000.f32" % pid), "wb")
            fh.write(b"\0" * payload)
            fh.close()
            return d

        morto = mk(41001)
        vivo = mk(41002, 8192)
        eu = mk(41003)
        outro = os.path.join(root, "um-directorio-qualquer")
        os.makedirs(outro, exist_ok=True)
        here = os.path.join(root, LQ.SPOOL_DIR_PREFIX + "41999")
        dirs, files, freed = LQ.sweep_sibling_spools(
            here, keep_pid=41003,
            alive=lambda p: bool(alive(p)), log=lambda _m: None)
        chk("o spool de um pid MORTO e' removido", os.path.isdir(morto), False)
        chk("o spool de um pid VIVO fica", os.path.isdir(vivo), True)
        chk("o spool do proprio processo fica (keep_pid)", os.path.isdir(eu), True)
        chk("um irmao que nao e' spool nao e' tocado", os.path.isdir(outro), True)
        chk("o varrimento conta so' o que removeu", (dirs, files, freed), (1, 1, 4096))
        # um segundo varrimento nao inventa trabalho: nada de pid morto ficou
        chk("o segundo varrimento nao remove nada",
            LQ.sweep_sibling_spools(here, keep_pid=41003, alive=alive,
                                    log=lambda _m: None)[0], 0)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return out


def wiring_checks(tag=""):
    """`probe_and_spool` REMOVE os irmaos -- e nao varre o spool do dono."""
    out = []

    def chk(name, real, want):
        out.append((real == want, tag + name, real, want))

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "engine_policy_probe", os.path.join(WORKER, "engine_policy.py"))
    pol = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pol)
    tmp = tempfile.mkdtemp(prefix="live-queue-wiring-")
    custom = tempfile.mkdtemp(prefix="live-queue-custom-")
    saved = (os.environ.get("TEMP"), os.environ.get("TMP"), os.environ.get("TMPDIR"),
             os.environ.get("SOTTO_REDUX_SPOOL_DIR"), tempfile.tempdir)
    try:
        stale = os.path.join(tmp, "sotto-pending-audio-45999")
        os.makedirs(stale, exist_ok=True)
        fh = io.open(os.path.join(stale, "pending-45999-000.f32"), "wb")
        fh.write(b"\0" * 1024)
        fh.close()
        for key in ("TEMP", "TMP", "TMPDIR"):
            os.environ[key] = tmp
        os.environ.pop("SOTTO_REDUX_SPOOL_DIR", None)
        tempfile.tempdir = None
        pol._LIVE_QUEUE_CACHE.update({"module": None, "path": None})
        _probe, spool = pol.probe_and_spool(os.path.join(REPO, "app", "webview",
                                                         "load_shedding.py"), None)
        chk("o spool do run nasce no temp", os.path.dirname(spool), os.path.normpath(tmp))
        chk("o irmao MORTO foi removido pelo ARRANQUE", os.path.isdir(stale), False)

        # o directorio do DONO nao e' varrido
        stale2 = os.path.join(custom, "sotto-pending-audio-45998")
        os.makedirs(stale2, exist_ok=True)
        os.environ["SOTTO_REDUX_SPOOL_DIR"] = custom
        pol._LIVE_QUEUE_CACHE.update({"module": None, "path": None})
        _probe2, spool2 = pol.probe_and_spool(os.path.join(REPO, "app", "webview",
                                                           "load_shedding.py"), None)
        chk("SOTTO_REDUX_SPOOL_DIR manda no sitio do spool",
            os.path.normpath(spool2), os.path.normpath(custom))
        chk("o spool do DONO nao e' varrido", os.path.isdir(stale2), True)
    finally:
        for key, value in zip(("TEMP", "TMP", "TMPDIR", "SOTTO_REDUX_SPOOL_DIR",
                               "tempdir"), saved):
            if key == "tempdir":
                tempfile.tempdir = value
            elif value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(custom, ignore_errors=True)
    return out


def run_negative_mutants(LQ_PATH):
    """DOIS mutantes plausiveis, cada um tem de derrubar os arms da ESPERA.

    (a) o DEFEITO ANTIGO, outra vez: ao passar da RAM, deitar fora o bloco mais
        ANTIGO (`pop(0)`) em vez de o escrever no disco;
    (b) a fila FECHADA CEDO: `take_all` devolve so' o primeiro bloco e o resto
        fica para tras -- o "drena para zero" deixa de ser verdade e o audio
        transcrito e' uma fraccao do capturado.
    """
    reds = []
    mutants = {
        "drop-oldest-over-ram": (
            "                head = self._ram[0]\n"
            "                if not self._spill_locked(head):",
            "                head = self._ram[0]\n"
            "                self._ram.pop(0)\n"
            "                self._ram_samples -= int(getattr(head, 'size', 0))\n"
            "                continue\n"
            "                if not self._spill_locked(head):"),
        "take_all-closes-early": (
            "            held.extend(ram)",
            "            held = held[:1]\n            ram = ram[:0]\n"
            "            self._ram_samples = 0\n            held.extend(ram)"),
    }
    for name, (before, after) in mutants.items():
        tmp = tempfile.mkdtemp(prefix="live-queue-neg-")
        try:
            text = io.open(LQ_PATH, encoding="utf-8").read()
            mutant = text.replace(before, after)
            if mutant == text:
                print(f"[FAIL] neg-arm({name}): nao consegui mutar o alvo")
                reds.append(False)
                continue
            io.open(os.path.join(tmp, "live_queue.py"), "w", encoding="utf-8").write(mutant)
            sys.path.insert(0, tmp)
            for name_mod in [m for m in list(sys.modules) if m == "live_queue"]:
                del sys.modules[name_mod]
            import live_queue as MUT
            try:
                failed = [c for c in pending_checks(MUT, tmp, tag=f"{name}: ") if not c[0]]
            except Exception as exc:  # noqa: BLE001 -- um mutante que rebenta E' red
                failed = [("", f"{name}: rebentou ({type(exc).__name__}: {exc})", None, None)]
            red = bool(failed)
            print(f"[{'PASS' if red else 'FAIL'}] neg-arm({name}): o mutante derruba "
                  f"{len(failed)} arm(s) da espera (1o: {failed[0][1] if failed else '--'})")
            reds.append(red)
        finally:
            if tmp in sys.path:
                sys.path.remove(tmp)
            for name_mod in [m for m in list(sys.modules) if m == "live_queue"]:
                del sys.modules[name_mod]
            shutil.rmtree(tmp, ignore_errors=True)
    # (c) O MUTANTE DOS IRMAOS: sem a pergunta "o pid ainda existe?", o varrimento
    # apaga o spool de um worker VIVO -- que e' audio do dono a caminho do parakeet.
    # Uma remocao so' pode ser segura se a guarda for a que a autoriza.
    tmp = tempfile.mkdtemp(prefix="live-queue-neg-spool-")
    try:
        text = io.open(LQ_PATH, encoding="utf-8").read()
        # A GUARDA CRESCEU (medido 2026-11-05): era `if is_alive(pid):` e hoje e'
        # `if pid is None or pid == keep or is_alive(pid):`. O mutante antigo
        # deixou de casar, o `--neg-arm` dizia "nao consegui mutar o alvo" e
        # devolvia rc=2 -- um instrumento partido a falar de si mesmo em vez de
        # julgar o alvo. O mutante tira a PERGUNTA DE LIVENESS e mantem o resto.
        before = "        if pid is None or pid == keep or is_alive(pid):\n"
        mutant = text.replace(before,
                              "        if pid is None or pid == keep:\n"
                              "            # MUTANTE: sem a pergunta de liveness\n")
        if mutant == text:
            print("[FAIL] neg-arm(spool-sem-liveness): nao consegui mutar o alvo")
            reds.append(False)
        else:
            io.open(os.path.join(tmp, "live_queue.py"), "w", encoding="utf-8").write(mutant)
            sys.path.insert(0, tmp)
            for name_mod in [m for m in list(sys.modules) if m == "live_queue"]:
                del sys.modules[name_mod]
            import live_queue as MUT
            try:
                failed = [c for c in spool_checks(
                    MUT, lambda p: p == 41002, tag="spool-sem-liveness: ") if not c[0]]
            except Exception as exc:  # noqa: BLE001
                failed = [("", f"rebentou ({type(exc).__name__}: {exc})", None, None)]
            red = bool(failed)
            print(f"[{'PASS' if red else 'FAIL'}] neg-arm(spool-sem-liveness): o mutante "
                  f"derruba {len(failed)} arm(s) (1o: {failed[0][1] if failed else '--'})")
            reds.append(red)
    finally:
        # O `remove` no `finally` rebentava quando o mutante nao chegava a ser
        # escrito (o ramo que faz `reds.append(False)` e continua): o caminho
        # nunca tinha entrado em sys.path e o ValueError matava o passo inteiro,
        # escondendo os outros mutantes. Medido 2026-11-05.
        if tmp in sys.path:
            sys.path.remove(tmp)
        for name_mod in [m for m in list(sys.modules) if m == "live_queue"]:
            del sys.modules[name_mod]
        shutil.rmtree(tmp, ignore_errors=True)
    return reds


def main() -> int:
    import live_queue as LQ

    arm("tecto de 2 s a 100 ms = 20 blocos", LQ.max_blocks(100), 20)
    arm("tecto de 2 s a 10 ms = 200 blocos", LQ.max_blocks(10), 200)
    arm("block_ms invalido nao rebenta (cai para 100 ms)", LQ.max_blocks("xx"), 20)

    q = queue.Queue()
    for i in range(30):
        LQ.enqueue_live(q, i, 20)
    nucleo = []
    while not q.empty():
        nucleo.append(q.get_nowait())
    arm("fila com 30 blocos e tecto 20 fica com 20", len(nucleo), 20)
    arm("o bloco que FICA e' o mais NOVO (29 presente)", 29 in nucleo, True)
    arm("o bloco mais ANTIGO saiu (0 ausente)", 0 in nucleo, False)
    arm("a ordem relativa dos que ficam e' a de chegada", nucleo, list(range(10, 30)))

    # O CONTROLE: a politica antiga com a MESMA fila cheia perde o bloco NOVO.
    q2 = queue.Queue(maxsize=20)
    for i in range(20):
        old_policy(q2, i, 20)
    perdido = old_policy(q2, 999, 20)
    restante = []
    while not q2.empty():
        restante.append(q2.get_nowait())
    arm("CONTROLE (regra antiga): o bloco NOVO e' o que se perde",
        (perdido, 999 in restante), (1, False))
    arm("CONTROLE (regra antiga): a fila guarda os ANTIGOS (0 la' esta)",
        0 in restante, True)

    # O WIRING no worker vivo: quem manda e' a politica nova.
    src = io.open(os.path.join(WORKER, "sotto_worker.py"), encoding="utf-8").read()
    arm("o worker chama `live_queue.enqueue_live_detailed`",
        "_live_queue.enqueue_live_detailed(" in src, True)
    arm("o `put_nowait(block)` cru (regra antiga) ja' NAO esta' no on_block",
        "audio_q.put_nowait(block)" in src, False)
    arm("o worker publica o contador agregado `queue_evicted`",
        'queue_evicted=eviction_stats["blocks"]' in src
        and "_live_queue.eviction_snapshot(counters)" in src, True)
    for name, passed in queue_eviction_checks(LQ):
        arm(name, passed, True)
    for name, passed in concurrent_eviction_checks(LQ):
        arm(name, passed, True)
    eviction_wiring = eviction_wiring_checks(src)
    for name in ("live-cap", "first-tap", "device-change"):
        arm("production source accounts " + name + " eviction reason",
            eviction_wiring[name], True)
    for name, real, want in file_tap_flow_checks(LQ, src):
        arm(name, real, want)

    # ── A ESPERA: o audio capturado com NADA carregado ───────────────────────
    # A ordem do dono de 2026-11-01 nao deixa margem: *"processa qualquer audio
    # nao processado, com o parakeet"*. Estes arms executam o `PendingAudio`
    # REAL e exigem o que a palavra "qualquer" significa: N entra, N sai, 0
    # deitados fora, e a espera a ZERO quando o motor a le'.
    tmp_wait = tempfile.mkdtemp(prefix="live-queue-wait-")
    try:
        for ok, name, real, want in pending_checks(LQ, tmp_wait):
            arm(name, real, want)
        # -- OS SPOOLS IRMAOS: o disco que os runs anteriores deixaram ---------
        # Medido 2026-11-05: 5 directorios de pids mortos, 51,9 MB, em `G:/Temp`.
        arm("a limpeza olha para os IRMAOS, nao so' para dentro do seu directorio",
            hasattr(LQ, "sweep_sibling_spools"), True)
        arm("o varrimento conhece o NOME do directorio de spool",
            getattr(LQ, "SPOOL_DIR_PREFIX", None), "sotto-pending-audio-")
        for ok, name, real, want in spool_checks(
                LQ, lambda p: p == 41002):
            arm(name, real, want)
        for ok, name, real, want in wiring_checks():
            arm(name, real, want)
        # a pergunta de liveness, contra o SO de verdade: o proprio pid vive e um
        # pid que nao existe (acima de qualquer limite desta caixa) nao vive.
        arm("`_pid_alive` diz VIVO do proprio processo", LQ._pid_alive(os.getpid()), True)
        arm("`_pid_alive` diz MORTO de um pid inexistente", LQ._pid_alive(3999999), False)
    finally:
        shutil.rmtree(tmp_wait, ignore_errors=True)

    # O WIRING do worker para a espera: o acumulador antigo (que TRIMAVA) ja'
    # nao pode existir. Um `REDUX_BUFFER_TRIMMED` de volta seria audio do dono a
    # desaparecer com uma linha de log a dizer que aconteceu.
    #
    # A CLASSE DO INTERRUPTOR VIVE EM `worker/engine_switch.py` DESDE A EXTRACCAO
    # (o ratchet estrutural mede o ficheiro mais longo e a funcao mais longa), e
    # `add_audio` -- quem acumula -- foi com ela. O que se exige e' o numero
    # publicado e o bloco guardado, nao o sitio onde esta' escrito: por isso estes
    # dois arms leem o PAR, como o arm dos campos ja' lia o `engine_policy.py`.
    extra = os.path.join(WORKER, "engine_switch.py")
    extra_src = io.open(extra, encoding="utf-8").read() if os.path.exists(extra) else ""
    arm("o acumulador que TRIMAVA o audio ja' nao esta' no worker",
        "REDUX_BUFFER_TRIMMED" in src or "REDUX_BUFFER_TRIMMED" in extra_src, False)
    arm("o worker acumula na `PendingAudio` (RAM -> disco)",
        "self.pending.add(block)" in src or "self.pending.add(block)" in extra_src, True)
    # OS CAMPOS SAO ESCRITOS EM `worker/engine_policy.py` desde a extraccao (o
    # `done` do worker chama `_policy.done_fields`): o arm le' os DOIS ficheiros,
    # porque o que se exige e' o numero publicado, nao o sitio onde esta' escrito.
    fields = os.path.join(WORKER, "engine_policy.py")
    field_src = io.open(fields, encoding="utf-8").read() if os.path.exists(fields) else ""
    arm("o worker publica entradas e saidas do audio que esperou",
        ("reduxAudioIn" in src or "reduxAudioIn" in field_src)
        and ("reduxAudioOut" in src or "reduxAudioOut" in field_src), True)

    if "--neg-arm" in sys.argv[1:]:
        tmp = tempfile.mkdtemp(prefix="live-queue-")
        try:
            mod = io.open(os.path.join(WORKER, "live_queue.py"), encoding="utf-8").read()
            mutado = mod.replace(
                "        while q.qsize() >= max(1, int(cap)):",
                "        while False:  # MUTANTE: sem eviccao")
            io.open(os.path.join(tmp, "live_queue.py"), "w", encoding="utf-8").write(mutado)
            sys.path.insert(0, tmp)
            for m in [m for m in list(sys.modules) if m == "live_queue"]:
                del sys.modules[m]
            import live_queue as MUT
            qm = queue.Queue()
            for i in range(30):
                MUT.enqueue_live(qm, i, 5)
            ficou = []
            while not qm.empty():
                ficou.append(qm.get_nowait())
            # com o mutante a fila cresce sem tecto: o critério de aceitacao falha.
            red = len(ficou) != 5
            print(f"[{'PASS' if red else 'FAIL'}] neg-arm: o mutante (sem eviccao) derruba "
                  f"o criterio -- fila final={len(ficou)} (esperado != 5)")
            RESULTS.append(red)
        finally:
            sys.path.remove(tmp)
            for m in [m for m in list(sys.modules) if m == "live_queue"]:
                del sys.modules[m]
            shutil.rmtree(tmp, ignore_errors=True)
        # One independent source mutation per production eviction detector.
        # Each removes exactly that call site's reason-specific accounting.
        worker_source = io.open(os.path.join(WORKER, "sotto_worker.py"), encoding="utf-8").read()
        mutations = {
            "live-cap": 'record_eviction(counters, reason, evicted, evicted_samples)',
            "first-tap": 'record_eviction(counters, reason, 1, samples)',
            "device-change": 'record_eviction(counters, reason, zero, zero_samples)',
        }
        for name, needle in mutations.items():
            mutant_source = worker_source.replace(needle, "# MUTANT: attribution omitted", 1)
            caught = (mutant_source != worker_source
                      and not eviction_wiring_checks(mutant_source)[name])
            print(f"[{'PASS' if caught else 'FAIL'}] neg-arm({name}-eviction-accounting): "
                  "single missing counter is detected")
            RESULTS.append(caught)
        # E os dois mutantes da ESPERA -- um que PERDE um bloco, outro que FECHA a
        # fila cedo. Sem eles, os arms da espera seriam os unicos deste oraculo
        # que nada derruba, e um arm que nada derruba nao mede nada.
        RESULTS.extend(run_negative_mutants(os.path.join(WORKER, "live_queue.py")))

    fail = RESULTS.count(False)
    print(f"\nLIVE-QUEUE {'VERDICT PASS' if fail == 0 else 'VERDICT RED'} "
          f"-- arms={len(RESULTS)} fail={fail}")
    if "--neg-arm" in sys.argv[1:]:
        print("LIVE-QUEUE NEG-ARM PASS -- RED as designed" if fail == 0
              else "LIVE-QUEUE NEG-ARM FAIL")
    # rc=1 POR DESENHO -- MAS SO' NO BRACO NEGATIVO (ver stale-display-oracle.py).
    # MEDIDO 2026-10-30: a primeira versao devolvia 1 tambem no run NORMAL, e o
    # `:step` positivo da bateria registava VERDICT PASS com rc=1 -- um verde que o
    # portao lia como falha. O run normal responde 0/2, o negativo responde 1/2.
    if "--neg-arm" in sys.argv[1:]:
        return 1 if fail == 0 else 2
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
