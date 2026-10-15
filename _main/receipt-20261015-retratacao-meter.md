# RETRACC AO: OS 10 252 EVENTOS/S EG O FALSO -- sao 10,00 Hz

Eu escrevi, ao dono e em dois recibos:

    BRIDGE_METER count=307556 in_window_s=30.0  ->  10 252 eventos por segundo

**E FALSO, e o erro e meu.** O subagente do caminho `emit` foi ver a linha por dentro e
mediu o que a cerca:

    anterior  count=307255  in_window_s=30.4
    A LINHA    count=307556  in_window_s=30.0
    seguinte  count=307853  in_window_s=30.0
    delta = 301 eventos em 30,0 s  =  10,033 eventos/s

**`count` e o cumulativo `self.meters`, posto UMA vez no `SottoShell.__init__` e nunca
reiniciado por worker.** Dividir um acumulado pela janela nao da uma taxa -- da um numero
que parece plausivel e nao e nada. A cadencia real, p50 sobre 2 014 intervalos, e **10,00
Hz**, que e exactamente o `METER_HZ=10.0` de desenho.

## Porque e que isto importa mais do que a correccao do numero

**Eu estava a perseguir um fantasma, e com o dono atras.** Escrevi-lhe "10 252/s" duas
vezes e sugeri-o como o hot path a investigar. Um unico passo -- ler a linha ANTERIOR e a
SEGUINTE e subtrair -- teria mostrado o erro. **Um contador cumulativo a fingir de taxa e
a mesma classe de erro que um print tirado ha tres horas: mede o que ja passou, nao o que
esta a acontecer.**

Fica escrito aqui para nao voltar a aparecer num recibo nem numa ordem de trabalho.

## As taxas REAIS, medias pelo subagente na janela de log 2026-10-13 13:53 .. 2026-10-15 14:48

    meter  10,00 Hz   (p90 10,00, max 11,40)   <- o valor de desenho, nao 10 mil
    stats   0,10 Hz
    caption p50 1,23 / p90 1,80 / max 2,83
    status  p50 0,27 / p90 0,40 / max 1,00

E o custo em processo, por evento, medido (nao estimado):

    log() 3,9-5,0 us | emit(caption) 2,0-3,3 us | emit_async quente 0,35 / frio 10,7-19,5 us
    _consume(linha meter) 1,6 us | _meter 0,4 us | _consume(caption) 1,5 us
    _pump por linha SEM _arm_silence 3,4 us | COM ela 251,5 us

## O caminho mais quente do shell, NOMEADO -- e a ressalva honesta ao lado

**`WorkerBridge._arm_silence()`** (`sotto_webview.py`), chamado UMA VEZ POR LINHA JSONL do
stdout do worker. Cada chamada cria **UMA THREAD DO SISTEMA** (`threading.Timer(...).start()`)
e cancela a anterior.

    251,52 us por linha com ela  vs  3,39 us sem ela   =  248,13 us = 98,7% da linha

E a ressalva que o proprio subagente poe, e que eu subscrevo: **o agregado e pequeno.** A
12,3 linhas/s, o `_pump` inteiro e 0,21-0,31% de um core. **Nenhum canal do shell passa de
0,31% de um core.** O caminho mais quente esta nomeado e NAO e a perda de performance.

## E o que sobra, com o Sotto FORA

O shell medido: **1,406% de um core**. O instrumento do subagente explica 0,21-0,31%.
**O resto nao esta atribuido.** E a medida que decide continua a ser a que eu fiz: com ZERO
processos do Sotto, o `System` (DPC/ISR) fica a **28-32% de um core**. **A perda nao esta
no Sotto -- esta no kernel.**

## Um defeito real que o subagente achou de lado, e vale a pena

`PANEL_VISIBILITY_WRITE_FAILED` aparece **17 891 vezes** na janela de 48,9 h -- **uma
escrita que falha a cada ~10 s**, sempre `PermissionError(13)` em
`H:\sotto\_main\panel-visibility.json`. Nao e o hot path, mas e um defeito com nome e
numero, e fica registado para ser fechado.
