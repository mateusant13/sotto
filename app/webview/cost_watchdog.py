"""O CUSTO SEM TRABALHO: quando o worker queima CPU e nao produz linha nenhuma.

NASCIDO DE UMA MEDICAO, 2026-11-09. O watcher mediu, ao vivo, o worker do dono
(`worker/sotto_worker.py`, pid 20676, 232 min de vida): **270,6 %c** -- 2,7 nucleos --
com `rows=0` no log dele, 6 176 s de CPU acumulada, e o dono sentiu a travada.
O watcher matou o worker, o painel respawnou sozinho, e com a arvore assentada o
mesmo instrumento mediu **1,2 %c**: fator 240. A conclusao que sobra e' a regra:

    CUSTO SEM TRABALHO NAO E' TRABALHO -- E' O STUTTER.

Duas coisas faltavam e este modulo entrega as duas:

1. **O NUMERO, DATADO.** O worker publica `WORKER_COST` a cada tick de stats
   (`cpu_s`, `cpu_pct_avg`, `rows`, `rows_per_min`, `cpu_s_per_row`), e a shell
   journaliza uma linha por minuto. Sem serie, "o worker degradou" e' inferencia;
   com serie, e' uma data.

2. **A DECISAO DE REINICIAR.** Um worker que gasta CPU e nao entrega linha nao tem
   como se curar sozinho: o que cura e' um arranque novo lendo o codigo do disco
   (foi exactamente isso que baixou 270,6 %c para 1,2 %c). A decisao e' pura e mora
   aqui, para poder ser julgada por um oraculo em vez de vivida.

O QUE ESTE MODULO NAO FAZ: nao mata, nao larga processo, nao fala com o bridge. Ele
devolve um PLANO (`{'restart': bool, 'why': ...}`) e quem executa e' a shell, pelo
caminho que ja' existe e ja' tem oraculo (`SottoShell.revive_worker`).
"""
from __future__ import annotations

#: CPU por cima disto, SEM linha produzida, comeca a contar para o reinicio.
#: Os tres numeros que o justificam, medidos nesta maquina: worker ocioso e saudavel
#: **0,4-1,2 %c**; worker transcrevendo **100-150 %c** (com `rows>0`, logo nao conta);
#: worker degradado **270,6 %c com `rows=0`**. 60 %c fica acima de qualquer repouso
#: medido e abaixo do defeito por um fator de 4.
BUSY_PCT = 60.0

#: Quantos ticks de stats seguidos (o worker publica a cada `--stats-interval`, 10 s
#: por omissao) de "CPU alta e zero linha" antes de reiniciar. 18 ticks = 3 minutos:
#: um chunk de 560 ms e uma recarga de modelo de 8-26 s cabem folgados dentro disso,
#: logo um pico curto nunca reinicia nada.
STALL_TICKS = 18

#: Piso entre dois reinicios deste vigia. Uma recarga custa 1,4-2,1 GB de RSS e
#: 2,0-8,3 s de stall (medido, `docs/audit/load-churn.md`); 10 min e' ~70x o stall.
FLOOR_S = 600.0

#: Tecto por hora: se um worker novo tambem degrada em 10 min, reiniciar de novo nao
#: arranja nada -- e' o codigo que esta' caro. O vigia para e diz por que.
MAX_PER_HOUR = 3


def plan(fields, streak, now, last_restart_at, restarts_hour):
    """A decisao de reiniciar, como FUNCAO PURA.

    `fields`   -- os campos da linha `WORKER_COST` (strings, como o worker os
                  imprime; `cpu_pct_avg` e `rows` sao os que importam).
    `streak`   -- quantos ticks seguidos ja' satisfizeram a condicao (o chamador
                  guarda o contador; ele proprio vem de `advance`).
    `now`      -- relogio monotonico do chamador.
    `last_restart_at` -- quando este vigia reiniciou pela ultima vez (0.0 = nunca).
    `restarts_hour`   -- quantos reinicios o vigia ja' fez na hora corrente.

    Devolve `{'restart': bool, 'why': str, 'streak': int}`. Um campo ilegivel NAO
    zera a serie nem a cumpre: `why` diz qual dos dois, porque "o worker parou de
    publicar" e "o worker esta' barato" sao coisas diferentes.
    """
    try:
        pct = float(fields.get('cpu_pct_avg'))
    except (TypeError, ValueError):
        return {'restart': False, 'why': 'sem-cpu-legivel', 'streak': streak}
    try:
        rows = int(float(fields.get('rows')))
    except (TypeError, ValueError):
        return {'restart': False, 'why': 'sem-rows-legivel', 'streak': streak}
    # A PERGUNTA E' "PRODUZIU LINHA NESTE TICK?", nao "produziu alguma vez?". O worker
    # publica as duas: `rows` e' cumulativo e `rows_since_tick` e' o delta. Um worker
    # que fez 1 768 linhas e depois passou 4 h a queimar CPU sem mais nenhuma tem
    # `rows>0` e esta' TAO degradado como o que nunca comecou -- foi o primeiro que
    # o dono sentiu (pid 20676). O cumulativo so' serve de recurso quando o campo do
    # delta nao veio.
    if 'rows_since_tick' in fields:
        try:
            produced = int(float(fields.get('rows_since_tick')))
        except (TypeError, ValueError):
            return {'restart': False, 'why': 'sem-delta-legivel', 'streak': streak}
        busy = pct >= BUSY_PCT and produced == 0
    else:
        busy = pct >= BUSY_PCT and rows == 0
    streak = streak + 1 if busy else 0
    if not busy:
        return {'restart': False, 'why': 'trabalha-ou-repousa', 'streak': streak}
    if streak < STALL_TICKS:
        return {'restart': False, 'why': 'ainda-abaixo-do-limiar', 'streak': streak}
    if last_restart_at and (now - last_restart_at) < FLOOR_S:
        return {'restart': False, 'why': 'piso', 'streak': streak}
    if restarts_hour >= MAX_PER_HOUR:
        return {'restart': False, 'why': 'tecto-por-hora', 'streak': streak}
    return {'restart': True,
            'why': 'cpu-sem-linha',
            'streak': streak}


def busy_rows(fields):
    """`{'pct': float|None, 'rows': int|None}` -- so' para o log, nunca para decidir."""
    pct = rows = None
    try:
        pct = float(fields.get('cpu_pct_avg'))
    except (TypeError, ValueError):
        pass
    try:
        rows = int(float(fields.get('rows')))
    except (TypeError, ValueError):
        pass
    return {'pct': pct, 'rows': rows}
