"""SWEEP DOS ENDPOINTS DE AUDIO -- qual deles traz SOM, e quanto custa descobrir.

O DONO, 2026-10-30, verbatim:
    *"eu tenho audio tocando, com pessoa falando, e eu to vendo legenda LIGANDO
    dezenas de segundos depois. encontra a porra do gargalo e arruma. se um audio
    tem fala, e pra ter transcricao NA HORA. ACABOU. E' REGRA. LEI. COM PROVA."*

O QUE ESTE INSTRUMENTO MEDE
---------------------------
O ladder do worker abre UM endpoint de cada vez e so' o abandona depois de o
achar silencioso (`ROTATION_*`). O custo de descobrir o endpoint certo e' o
produto (numero de rotacoes x tempo por rotacao), e ele paga-se ANTES da
primeira legenda. Medido no log do dono hoje: `ROTATION_CEILING reached
rotations=8 captions=0` em 117 s, e a primeira legenda 5,5 min depois do
arranque.

Este instrumento faz o SWEEP DE FORA: abre cada candidato do MESMO ladder,
le' `SWEEP_MS` de audio, e publica o pico. Nada e' escrito no sistema, nada e'
tocado no worker vivo, nenhuma janela e' aberta (python puro + PortAudio).

O QUE ELE NAO FAZ
-----------------
Nao decide nada: nao escolhe endpoint, nao escreve config, nao toca em
`worker/`. O veredicto e' uma tabela e um numero (`sweep_ms`), e a decisao de
como usa'-los e' de quem le'.

Exit codes: 0 houve pelo menos um endpoint com som, 3 nenhum (maquina em
silencio agora -- nao e' falha do instrumento), 2 erro de setup.
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(REPO, "worker"))

SWEEP_MS = int(os.environ.get("SOTTO_SWEEP_MS", "400"))


def main() -> int:
    import numpy as np

    import sotto_worker as W

    t0 = time.time()
    try:
        cands = W.device_candidates()
    except Exception as exc:  # noqa: BLE001 -- sem lista nao ha sweep
        print(f"SETUP-FAIL device_candidates: {exc!r}", file=sys.stderr)
        return 2
    rows = []
    for i, dev in enumerate(cands):
        peak = 0.0
        blocks = 0
        err = ""
        boxes = []

        def on_block(block, _b=boxes):
            _b.append(float(np.max(np.abs(block))) if getattr(block, "size", 0) else 0.0)

        tap = None
        a = time.time()
        try:
            tap = W.LoopbackTap(dev, on_block, block_ms=20)
            tap.stream.start()
            deadline = time.time() + SWEEP_MS / 1000.0
            while time.time() < deadline:
                time.sleep(0.02)
            if boxes:
                peak = max(boxes)
                blocks = len(boxes)
        except Exception as exc:  # noqa: BLE001 -- um candidato que nao abre e' um dado
            err = f"{type(exc).__name__}: {exc}"
        finally:
            try:
                if tap is not None:
                    tap.stream.stop()
                    tap.stream.close()
            except Exception:  # noqa: BLE001
                pass
        cost_ms = (time.time() - a) * 1000.0
        rows.append({
            "i": i,
            "name": str(dev.get("name"))[:60],
            "rung": dev.get("rung"),
            "peak": round(peak, 6),
            "blocks": blocks,
            "cost_ms": round(cost_ms, 1),
            "error": err,
        })
    total = (time.time() - t0) * 1000.0
    audible = [r for r in rows if r["peak"] >= 0.002]
    print(json.dumps({"sweep_ms": SWEEP_MS, "candidates": len(rows),
                      "total_ms": round(total, 1), "audible": len(audible)},
                     ensure_ascii=False))
    for r in rows:
        mark = "SOM" if r["peak"] >= 0.002 else ("ERRO" if r["error"] else "mudo")
        print(f"  [{mark:4s}] i={r['i']:<2d} rung={r['rung']} peak={r['peak']:.6f} "
              f"blocks={r['blocks']} cost_ms={r['cost_ms']} {r['name']} "
              f"{r['error'][:60]}")
    if audible:
        best = max(audible, key=lambda r: r["peak"])
        print(f"SWEEP VERDICT: {len(audible)} endpoint(s) com som; o mais forte e' "
              f"i={best['i']} ({best['name']}) peak={best['peak']:.6f}  "
              f"sweep_total_ms={total:.0f}")
        return 0
    print("SWEEP VERDICT: nenhum endpoint com som agora (maquina em silencio)")
    return 3


if __name__ == "__main__":
    sys.exit(main())
