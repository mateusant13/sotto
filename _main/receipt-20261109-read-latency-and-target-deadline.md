# RECIBO — a leitura da legenda que pagava 33 s no fio do laço, e a primeira pergunta do alvo

Data: 2026-11-09, 20:1x-20:5x (hora local). Árvore: `H:\sotto`.
Gatilho: DM do watcher (owner) a acusar a árvore de `pythonw.exe(27568)` — shell do Sotto — como
maior pressão medida no episódio de stutter (`cpu 8.2% of machine over 2 proc(s)`, sinais
`interrupt`, `creation`).

Tudo o que segue foi medido nesta árvore, hoje. Onde a linha diz `PASS`, o comando está ao lado.

## 1. O caminho que produzia a pressão — nomeado em ficheiro:linha

Duas metades, as duas no fio do LAÇO de leitura da legenda externa:

1. **`app/webview/sotto_webview.py:3703` (`_read` dentro do laço `ExternalCaptionWatcher`)**
   — o laço pedia 10 Hz (`INTERVAL_S = 0.10`) sem olhar ao que a leitura ANTERIOR tinha custado.
   A escada de silêncio/pausa existia (`poll_step`) mas só descia com o player parado ou sem
   leitura; uma leitura que custou 406 ms mantinha a cadência.
2. **`app/webview/youtube_cdp_source.py:1339-1341` (`target_video_id`)**
   — com o cache do alvo ainda vazio (nasce vazio em cada objeto novo), a resposta era
   `self._tid_refresh()`: um `/json/list` **SINCRONO no fio do chamador**. Com o Chrome do dono a
   100 %, essa chamada custou **33 s**.

## 2. O que o log do dono mediu (antes)

```
2026-11-09 19:31:00.804  EXTERNAL_CAPTIONS_READ_MS ms=33281.0
                         phases={'import': 0.0, 'target': 33281.0, 'source': 33281.0,
                                 'yt-in': 33281.0, 'cdp': 33281.0, 'vid': 33281.0,
                                 'youtube': 33281.0, 'end': 33281.0}
2026-11-09 19:31:00.913  EXTERNAL_CAPTIONS_READ_STATS n=453 mean_ms=88.0 p95_ms=46.0
                         max_ms=33281.0 interval_s=0.10
2026-11-09 19:50:32.967  EXTERNAL_CAPTIONS_READ_STATS n=548 mean_ms=0.3 p95_ms=0.0
                         max_ms=125.0 interval_s=0.10
2026-11-09 19:51:03.186  EXTERNAL_CAPTIONS_READ_STATS n=358 mean_ms=1.7 p95_ms=0.0
                         max_ms=406.0 interval_s=0.10
```
Contagens na janela 19:00-20:09 (`_main/webview-run.log`):
`UI_HUNG reason=caption-read-slow` = **5** (19:31:00, 19:42:23, 19:56:38 e dois antes), e
`UI_WATCHDOG_STRIKE` = **27**. O `UI_HUNG` só sai quando a leitura em voo passa de 3 s
(`sotto_webview.py:12536-12540`), ou seja: as leituras de 33 s **são** o motivo do despejo.

## 3. A cura — dois sítios, cada um com o seu juiz

**(a) `poll_step` desce com a leitura lenta** (`sotto_webview.py:3419-3449`):
`READ_SLOW_MS = 200.0`, `READ_SLOW_STEP_S = 0.25`, `READ_SLOW_HOLD_S = 1.0`. Uma leitura acima de
200 ms arma a espera de 1 s e o passo vai para 0,25 s (nunca acima do passo IDLE). O laço passa o
estado medido (`sotto_webview.py:3797-3800`) e publica a borda
`EXTERNAL_CAPTIONS_READ_PACED slow=.. last_ms=.. step_s=.. hold_s=..`; o agregado de 30 s passou a
imprimir `step_s=`, que é o passo APLICADO (antes imprimia a constante de configuração).

**(b) a primeira pergunta ao alvo tem prazo** (`youtube_cdp_source.py:921-927`, `1341-1374`):
`_TID_WAIT_S = 0.30`. Com a fonte LIGADA e o cache vazio, `target_video_id()` espera o fio
`yt-cdp-target` publicar por no máximo 0,30 s e devolve `''` (o `''` custa a varredura UIA de
94-109 ms — duas ordens de grandeza abaixo dos 33 s). A excepção é a fonte SEM ligação: aí o fio do
alvo está inerte por desenho, e a pergunta é paga por quem pergunta, uma vez, como sempre foi (é o
contrato que as arms STALE-ID e A5 julgam). Cada espera sem publicação nomeia-se:
`YOUTUBE_TARGET_UNPUBLISHED waits=.. wait_s=.. attached=..`.

## 4. Os juízes, corridos agora

```
$ python _main/paused-pace-oracle.py
13/13 arms green
VERDICT: PASS                                      (rc=0)
$ python _main/paused-pace-oracle.py --neg-arm
NEG-ARM PASS -- 2 arm(s) RED, A2 entre elas=True            (mutante 1: a pausa desarmada)
NEG-ARM M2 PASS -- 3 arm(s) RED, A4-bis entre elas=True     (mutante 2: a escada lenta apagada)
                                                    (rc=1 — a convenção da casa)

$ python _main/youtube-cdp-slow-oracle.py
7/7 arms green
VERDICT: PASS                                      (rc=0)
$ python _main/youtube-cdp-slow-oracle.py --neg-arm
NEG-ARM: PASS -- 7 arms, 5 mutants, every judged arm RED   (rc=1)
```
A arm nova **A6 pergunta-ligada-tem-prazo** mede o contrato: fonte ligada, `list_targets` que dorme
3 s, `target_video_id()` devolve `''` em **0,31 s** (primeira corrida) / **1,17 s** (com o módulo
carregado e a máquina ocupada) e **o fio do chamador não aparece** entre os que pagaram
(`quem_pagou=['yt-cdp-target']`).

Arm nova **A4-bis/A4-ter/A4-quater/A4-quinquies** (paused-pace) e **A5-bis** (o laço PASSA o quinto
argumento — sem isso a escada existiria e ninguém a usaria).

Correção de instrumento que a wiring obrigou: `poll_step_from` extraía SÓ a função, e a escada
depende de constantes de módulo — o oráculo morria num `NameError` (um instrumento que não corre não
mede). Agora as constantes `READ_SLOW_*` viajam com a função.

## 5. A árvore AGORA, medida com os instrumentos do projeto

```
$ python -m watcher profile 27568            (I:\!watcher)
PROFILE pid=27568 (pythonw.exe) window=9.03s cpu=16.6% of one core = 0.17 cores
        = 0.8% of the machine (20 logical cores) threads_seen=64 unattributed=0.0s

$ python _main/shell-thread-cpu.py 27568 --seconds 12 --top 10
pid 27568: 63 fios, 12.3 s de janela, 16.9% de um nucleo no total
calibracao: processo mediu 18.4% no mesmo intervalo -> razao 0.92
     pct    cpu_s     tid  nome
    7.5%     0.92   40444  yt-clock
    1.9%     0.23   40052  sotto-worker-stdout
    1.9%     0.23   46236  (sem nome)
    1.4%     0.17   33952  sotto-external-captions
    1.0%     0.12   20396  sotto-gaming-mode
    0.3%     0.03   21172  yt-cdp-source
```
O `yt-clock` (`sotto_webview.py:6151-6176`) é intermitente, não constante: três janelas de 6 s na
mesma instância deram **0,0 % / 1,5 % / 12,4 %** com o fio a 5,7 % na terceira — é a amostra UIA de
recurso (`_yc.player_time`, 391-1375 ms cada) a disparar quando a foto CDP está velha, não um laço a
queimar sempre. Não foi cortado hoje: cortá-lo exige medir quantas amostras disparam por minuto, e o
número que existe é o de 2 janelas.

`python -m watcher perf` na mesma janela: `cpu=100.0% commit=65.0% dpc=0.75% irq=3.75%
disk_lat=51.3ms` (volume `I:` q_avg=0.51, busy=50.7 %, lat=51.33 ms) e o maior CPU do censo é
**`python.exe(5968)` `deteccaoaudiodoppler`, 26.5 %, commit 1.69 GB** — não é esta árvore.

## 6. O QUE NÃO ESTÁ VERIFICADO

* O `after` do processo VIVO é **UNMEASURED**: a shell em execução (pid 27568, arrancada 18:59:28)
  carrega o código `sha256=83E8F056FB47` (`SHELL_CODE_ID` no log), anterior às duas curas. A primeira
  linha `EXTERNAL_CAPTIONS_READ_PACED` e o primeiro `step_s=` no agregado são a prova, e só existem
  depois de ele reiniciar a app.
* Nada disto foi visto na tela do dono; os oráculos correm sem janela, sem áudio e sem Chrome.
* O `yt-clock` (7,5 % de um núcleo quando dispara) fica **nomeado e não cortado** — cortá-lo sem o
  número de amostras por minuto seria o palpite que esta casa recusa.

## 7. Trapalhada declarada

O `shell-thread-cpu.py` na primeira tentativa leu `pid 49480` e respondeu
`sem fios para o pid 49480`: esse pid já tinha fechado. O shell vivo é o **27568**, identificado pelo
próprio log (`SHELL_STARTUP_STAGE pid=27568 stage=pre-lock`).
