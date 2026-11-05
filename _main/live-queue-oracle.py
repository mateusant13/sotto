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

ARMS (9): a aritmetica do tecto, o comportamento real da `queue.Queue` ao encher,
o controle com a regra ANTIGA (`put_nowait` + drop do NOVO, que perde o agora),
o wiring no worker vivo (AST) e o contador publicado.

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
import tempfile

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
        before = "        if is_alive(pid):\n            continue\n"
        mutant = text.replace(before, "        # MUTANTE: sem a pergunta de liveness\n")
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
    arm("o worker chama `live_queue.enqueue_live`",
        "_live_queue.enqueue_live(" in src, True)
    arm("o `put_nowait(block)` cru (regra antiga) ja' NAO esta' no on_block",
        "audio_q.put_nowait(block)" in src, False)
    arm("o worker publica o contador `queue_evicted`",
        'counters["queue_evicted"]' in src, True)

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
