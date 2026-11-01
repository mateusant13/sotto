"""A FILA DE AUDIO VIVO: o bloco mais NOVO entra, o mais VELHO sai.

O DONO, 2026-10-30, verbatim:
    *"eu tenho audio tocando, com pessoa falando, e eu to vendo legenda LIGANDO
    dezenas de segundos depois. encontra a porra do gargalo e arruma. se um audio
    tem fala, e pra ter transcricao NA HORA. ACABOU. E' REGRA. LEI. COM PROVA."*

O DEFEITO, por leitura (`worker/sotto_worker.py`, corrigido 2026-10-30): a
`audio_q` nasce com `maxsize=256` -- a 100 ms por bloco sao **25,6 s de audio** --
e o overflow fazia `except queue.Full: counters["queue_drops"] += 1`, deitando
fora o bloco RECEM-CAPTURADO. O pior dos dois mundos: perdia-se o audio do
instante E ficavam na fila os 25,6 s mais antigos, que o consumidor ia
transcrever em ordem, um a um. Uma fila assim nao atrasa a legenda por acaso:
ela E o atraso.

A REGRA. A fila tem um tecto em SEGUNDOS (`LIVE_QUEUE_MAX_S`), nao em numero de
blocos, porque 256 blocos significa coisas diferentes em cada taxa de captura.
Quando ela passa do tecto, o bloco mais ANTIGO sai para entrar o novo: o audio
que chega agora vale mais do que o audio de ha dois segundos, e uma legenda que
reproduz o passado e' pior do que uma legenda que perdeu um instante -- o
instante perdido o dono nem sabe que existiu.

Nada aqui abre dispositivo, janela ou modelo: e' fila, e por isso e' medida por
oraculo sem tocar na app.
"""
from __future__ import annotations

#: O teto de audio vivo na fila, em segundos.
LIVE_QUEUE_MAX_S = 2.0


def max_blocks(block_ms, cap_s=LIVE_QUEUE_MAX_S):
    """Quantos blocos cabem em `cap_s` segundos."""
    try:
        ms = int(block_ms)
    except (TypeError, ValueError):
        ms = 100
    return max(2, int(float(cap_s) * 1000.0 / max(1, ms)))


def enqueue_live(q, block, cap):
    """Enfileira o bloco mais NOVO; se a fila estiver cheia, deita fora o VELHO.

    `cap` e' o numero maximo de blocos (ver `max_blocks`). Uma fila com
    `maxsize=0` (ilimitada) e' tratada como sem tecto de blocos, mas o tecto em
    segundos continua a valer: o chamador passa `cap` de qualquer forma.

    Devolve `(evicted, dropped)` para o chamador contar o que aconteceu:
    `evicted` = blocos VELHOS que sairam para o novo entrar; `dropped` = o novo
    nao entrou (corrida com o consumidor, fila fechada).
    """
    evicted = 0
    dropped = 0
    try:
        while q.qsize() >= max(1, int(cap)):
            try:
                q.get_nowait()
                evicted += 1
            except Exception:  # noqa: BLE001 -- fila esvaziada por outro lado
                break
        q.put_nowait(block)
    except Exception:  # noqa: BLE001 -- corrida com o consumidor nao pode matar o tap
        dropped += 1
    return evicted, dropped
