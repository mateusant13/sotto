# AS 17 891 ESCRITAS QUE FALHAVAM -- o retry existia e era curto demais

## O numero, e quem o mediu

O subagente do caminho `emit`, num instrumento proprio e sobre a janela de log de 48,9 h:

    PANEL_VISIBILITY_WRITE_FAILED   17 891 ocorrencias
    0,102/s  --  UMA A CADA ~10 SEGUNDOS
    sempre PermissionError(13) em H:\sotto\_main\panel-visibility.json

## O que ja estava feito, e porque nao chegava

`panel_state.write_atomic` JA retentava, e o comentario dizia por palavras o que se
passa:

    os.replace fails with PermissionError(13) while the other writer holds the target
    open -- measured at 1 145 063 occurrences

Os dois escritores sao o writer periodico do shell e o **worker, que sonda o ficheiro**.
Enquanto um o tem aberto, o `os.replace` do outro e recusado pelo Windows.

**Mas o orcamento era de 6 tentativas** -- 0,02 a 0,12 s de espera, ~0,42 s no total -- e
17 891 falhas dizem que a contencao dura mais que isso. **A correccao certa nao era
inventar um mecanismo: era alargar um que ja existia e estava subdimensionado.**

## A mudanca

    6 tentativas  ->  20 tentativas
    espera: min(0,1, 0,02*(n+1))  -- CAPADA

O cap importa: sem ele a progressao linear levava a ultima tentativa a 0,4 s e o pior
caso a ~4,2 s. Com o cap sao ~1,9 s no pior caso -- e isto corre numa thread propria
(`sotto-panel-visibility`), portanto nao prende a UI.

**Uma escrita atrasada vale mais do que uma escrita perdida.**

## O que isto NAO prova, e digo-o

**Nao medi a taxa depois da mudanca.** A previsao e que quase todas as 17 891 passem a
ser escritas atrasadas; a prova e contar `PANEL_VISIBILITY_WRITE_FAILED` numa janela
nova e comparar com os 0,102/s de agora. Fica nomeado como o que falta -- e e barato.

E fica tambem dito o que o subagente NAO conseguiu fechar: o `_arm_silence` que cria uma
thread do sistema por cada linha do worker (251 us contra 3,4 us = 98,7% da linha, mas
so 0,21-0,31% de um core), e o driver que come 28-32% de um core em DPC com o Sotto
FECHADO -- que continua a ser, de longe, a maior perda de performance desta maquina.
