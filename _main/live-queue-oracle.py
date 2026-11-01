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
            shutil.rmtree(tmp, ignore_errors=True)

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
