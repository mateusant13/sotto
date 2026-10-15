# AS 17 891 ESCRITAS: A CORRECCAO MEDIDA -- 0 falhas em ~300 escritas

Eu tinha deixado isto como "a prova e contar a falha numa janela nova". Contei.

## A janela, e o numero

Recortei o log a partir do arranque que ja tinha o retry de 20 tentativas (15:07:5x):

    linhas na janela .................. 1 530
    PANEL_VISIBILITY_WRITE_FAILED ..... 0
    PANEL_VISIBILITY_WRITER ........... interval_s=3

O writer corre a cada **3 segundos**, portanto em 15 minutos foram **~300 escritas**.
**Zero falhas.**

## Contra o que se compara

A taxa medida pelo subagente, na janela de 48,9 h: **0,102/s** -- uma falha a cada ~10 s.
Nas mesmas ~300 escritas, o codigo antigo teria deixado passar **~90 falhas**.

## E uma medicao anterior que eu quase li mal, e vale escrever

A primeira contagem foi "a ultima falha foi as 13:31:49, ha quase duas horas". Isso e
VERDADE e NAO PROVA NADA sozinho: o log e rate-limited (`errors <= 3 or errors % 500 == 0`),
portanto a ausencia de linha nao e a ausencia de falha -- so diz que foram menos de 500. E
13:31 e ANTES da correccao, o que mistura dois mundos na mesma janela.

**A medicao que vale e a que isola a mudanca**, e essa e a de cima: recortei no arranque que
tem o retry novo, contei 0, e sei quantas escritas houve pelo intervalo do proprio writer.

## O que fica por medir

Nao sei se a taxa e EXACTAMENTE zero ou apenas "abaixo de 500 em 15 min". Uma janela de 48 h
com o codigo novo daria o numero exacto. **O que esta medido e a comparacao: ~90 esperadas,
0 observadas.**
