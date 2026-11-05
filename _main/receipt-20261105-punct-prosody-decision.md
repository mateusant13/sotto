# Decisao — pontuacao a partir da prosodia NAO se liga agora (2026-11-05)

A pergunta estava aberta como "#61 Wire punct from prosody?" desde que
`worker/punctuation_prosody.py` aterrou: o modulo existe, tem 189 linhas, um
recibo de medicao (`_main/receipt-20261105-punct-from-prosody.md`) e um oraculo
(`_main/punct-prosody-oracle.py`), e mesmo assim **nenhum sitio o chama**.

## A DECISAO

**Nao ligar.** O modulo fica como esta' — puro, sem I/O, identidade sem
evidencia de audio — e nao entra no caminho da legenda.

## A RAZAO, medida e nao escolhida

O contrato de entrada do modulo e' `pauses[i]` = o silencio, em ms, DEPOIS do
i-esimo token de `text` (`len(pauses) == len(tokens) - 1`). Ou seja ele precisa
de **tempo por palavra**.

O worker desta arvore nao o tem:

    grep -n "t_offset|tOffset|token_time|word_time|timestamps|offsets" worker/sotto_worker.py   ->  0 linhas
    grep -rn "pauses=" worker/*.py app/webview/*.py (fora do proprio modulo)                  ->  0 chamadores

O decode e' por chunk (`chunk_samples=8960`, `frames` por chunk), e o resultado
de um chunk e' uma string de texto — nenhuma palavra carrega um indice de frame.
Sem esse indice, uma lane que "ligasse" o modulo teria de **inventar** a
distribuicao das palavras ao longo do chunk, e a convencao inventada seria
exactamente o que o `AGENTS.md` proibe ("Nao inventar uma convencao de decode —
esse erro ja' foi cometido uma vez").

## O QUE DESBLOQUEIA A DECISAO (ordem)

1. O decode passar a emitir, por token, o indice de frame (ou a duracao) —
   mudanca no caminho do decode, com o spec do modelo ao lado, nunca por
   estimativa.
2. Um fixture com as pausas REAIS conhecidas (audio + texto + marcas) para
   julgar precisao e recall do que sai.
3. So' entao o `pauses` e' construido no worker e o modulo deixa de ser
   identidade.

Ate la', o modulo nao custa nada: nao esta' no caminho da legenda, nao carrega
modelo, e o oraculo dele continua a provar que a decisao de pontuacao e' pura e
que a entrada degenerada e' identidade.
