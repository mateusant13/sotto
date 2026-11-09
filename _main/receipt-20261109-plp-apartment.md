# RECIBO — o apartamento COM do tap por processo (2026-11-09)

## 1. O defeito, e como apareceu

O card #12 da lane (`DISCORD-AO-VIVO`) tinha o tap POR PROCESSO a abrir e a medir `PLP_START hr=0`.
Ao remede-lo para o `--target-name`, a sonda de aceitação respondeu **ZERO blocos com o tap
ABERTO** (`PLP_OPEN_OK hr=0`, `pump_exited=False`), e o worker chamou a isso `no-callback-blocks`.
Uma sonda directa, com o tap aberto na MAIN thread, entregou **39 blocos em 4 s** — ou seja, o
mesmo código entregava ou não entregava conforme QUEM abria.

## 2. A hipótese, e a refutação do que a vizinhança dizia

Hipótese: *os ponteiros COM pertencem ao apartamento que os criou; o `plp-capture` os lê de fora.*

Duas medições que a separam de "o dispositivo está mudo":

| braço | forma | blocos |
|---|---|---|
| directo, main thread | open + pump no mesmo fio | **75 em 4 s** |
| tap num fio, fio PARADO 3 s | open num fio, pump noutro, fio de abertura vivo | **71 em 3 s** |
| tap num fio, fio SAI | `_open_tap_bounded` (o caminho de PRODUÇÃO) | **0** |
| o mesmo, 2 s depois de o fio sair | — | **71 (parou no instante da saída)** |

Quarta linha é a prova: os blocos param exactamente quando o fio que abriu morre. Sintoma irmão
medido na mesma sessão: `OSError: exception: access violation` dentro do `GetBuffer`.

E o que isso custava em produção: `_open_tap_bounded` abre o tap num fio e deixa-o sair, logo o
caminho inteiro que a escada usa entregava zero blocos e o veredicto publicado era
`no-callback-blocks` ("nenhum bloco chegou") num tap que estava aberto.

## 3. A cura

`worker/sotto_worker.py`, classe `ProcessLoopbackTap`:

* `_start` cria **UM** fio dono (`plp-owner`) que faz `_com_init` → `_open` → pump →
  Stop/release/COM (`_teardown_on_owner`), e **espera** o desfecho do open por evento
  (`_opened` / `_open_error`) porque a escada decide por ele — um open que falha não pode virar
  "dispositivo mudo".
* `_open` deixou de arrancar o `plp-capture`.
* `stop()`/`close()` deixaram de tocar nos ponteiros de fora: pedem, e esperam o fio dono.

## 4. Medido depois

| instrumento | comando | resultado |
|---|---|---|
| caminho de produção | `_open_tap_bounded` + 3 s | **74 blocos**, `pump_exited=False`, `hr=0` |
| worker real | `python worker/sotto_worker.py --target-name Discord.exe --max-seconds 8` | **168 blocos em 6 s**, `peak=0.0`, veredicto **`silent-device`** |
| oráculo | `python _main/process-target-oracle.py` | `PASS (22/22)` |
| negativo | `python _main/process-target-oracle.py --neg-arm` | `7/7` mutantes apanhados, **rc=1** |

O veredicto do worker mudou de `no-callback-blocks` para `silent-device`: o Discord estava sem som
na janela da medição, e **silêncio digital com a captura viva é um facto diferente de captura
morta** — era exactamente a distinção que o defeito apagava.

## 5. O instrumento, e onde ele falhou antes de servir

`_main/process-target-oracle.py` ganhou A10-A14 (a FORMA do fio dono por `ast` + o EFEITO pelo
caminho de produção, com `SKIP` declarado quando não há programa alvo vivo). O `--neg-arm` muta
quatro vezes o worker:

1. pump volta a ser um fio separado dentro de `_open` → **A10**
2. COM volta a ser inicializado em `_start` → **A12**
3. `_start` deixa de esperar o `_opened.wait` → **A11**
4. teardown sai do `finally` → **A13**

**Duas lições de instrumento, ambas pagas nesta rodada:**

* A primeira A13 só exigia o nome `_teardown_on_owner` em qualquer sítio de `_owner_loop` — e o
  mutante que apagava o `finally` passava, porque o ramo de EXCEÇÃO também o chama. Um negativo
  que não cai é um portão que não mede: agora a arm exige a chamada no `finalbody` do `Try`.
* A primeira A11b era `"Thread" in texts[...] is False`, que **em Python é uma comparação
  encadeada** e avalia sempre falso: a arm reprovava código CORRECTO. Corrigida para julgar a
  chamada de construção (`spawns_thread`).

## 6. O que NÃO está verificado

* `verified` continua a exigir uma corrida real da app na mão do dono. Aqui está `fixed, measured`.
* O áudio de uma CALL real: na janela desta medição o Discord não renderizava som (`peak=0.0`), e
  `silent-device` é o veredicto honesto — não "funciona".
