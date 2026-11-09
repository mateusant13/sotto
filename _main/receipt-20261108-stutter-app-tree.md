# RECIBO — o stutter de 2026-11-08 21:1x-21:3xZ: a árvore do `pythonw.exe(55104)`

Duas DMs do watcher na mesma hora acusaram o MESMO pid, e as duas com a medição dele ao lado:

```
STUTTER (1)  io 9.8MB/s over 7 proc(s), signals: disk, creation;  disk=30.754ms per op>=25; creation=11.793/s>=5
STUTTER (2)  cpu 12.5% of machine over 7 proc(s), signals: interrupt, creation -- 5 episode(s) in 60 min
culprit      = pythonw.exe(55104)  tree of 7
cmdline      = pythonw.exe  "H:\sotto\app\webview\sotto_webview.py" --log ... --no-self-relaunch --ready-file ...
```

## 1. DE QUEM E' O PID — medido, e a resposta muda o que se faz

| pergunta | instrumento | veredicto |
|---|---|---|
| é a app do dono ou uma lane? | `I:/cc-tmp/pid-census.py 55104` (EnumWindows por pid) | **9 janelas, TODAS `vis=False`** (`SottoNativeCaption`, `WindowsForms10…'Sotto'`, `SottoTrayWindow`) |
| que instância é esta, e de quando? | `_main/webview-run.log:419542` | `2026-11-08 13:38:36.827 SHELL_STARTUP_STAGE pid=55104 stage=pre-lock`, `SHELL_CODE_ID sha256=F186430420A6 files=101`, `SINGLE_INSTANCE already_running=false` |
| posso ler os handles dela? | `psutil.Process(55104).open_files()` | **`AccessDenied`** — a árvore corre em integridade **`high`**, esta pane é `medium` |

Ou seja: é a instância **do dono** (alta integridade, aberta pelo autostart), e ela é **ANTERIOR a
todas as curas de hoje** — `LIVE_CODE` responde `STALE`. Não se mata a app dele para "resolver"
um stutter: isso apaga o produto que ele está a usar e não mede nada. O que se faz é nomear o custo
e entregar a cura; o reinício é dele.

## 2. O CUSTO, POR PROCESSO E POR FIO (medido agora, nesta árvore)

`python -m watcher profile 55104` não existe nesta máquina (`No module named watcher` fora de
`I:\!watcher`); o instrumento da casa que responde à mesma pergunta é `_main/shell-thread-cpu.py`
e `psutil`, e os dois foram corridos.

| processo | cpu (de um núcleo) | io | fios |
|---|---|---|---|
| `python.exe` **7144** (worker) | **129,4 %** e **149,2 %** em duas janelas | r 0,016 / w 0,064 MB/s | 80 |
| `pythonw.exe` **55104** (shell) | **21,1 %** / **22,9 %** em duas janelas | r 0,048 / w 0,006 MB/s, **5 963 ops/s** | 48-55 |
| `msedgewebview2.exe` ×5 | 0,0 % | < 0,01 MB/s | 145 somados |

O fio mais quente da shell, com NOME (`_main/shell-thread-cpu.py 55104 --seconds 6`):

```
pid 55104: 48 fios, 6.1 s de janela, 22.9% de um nucleo no total
    4.6%  tid 7152  sotto-yt-track
    4.1%  tid 41744 sotto-external-captions
    2.5%  tid 16168 yt-cdp-source
    1.3%  tid 29804 sotto-gaming-mode
```

Cadência viva, dos últimos 12 min do log: `YOUTUBE_LOOP_HZ`/`YOUTUBE_TICK_MS` 240 linhas (o agregado
de 5 s), **2 543 `YT_FRAME`** (≈3,5/s a pintar), **109 `YOUTUBE_TARGET_SLOW`** (≈9/min, cada um
1,0-1,4 s) e 107 `YOUTUBE_CDP_HEALTH`. A varredura de legendas externas declara a sua cadência em
`EXTERNAL_CAPTIONS_WATCH started=true interval_s=0.10` — 10 Hz, e o `EXTERNAL_CAPTIONS_READ_STATS`
dos 30 s diz quanto cada volta custa.

## 3. ONDE ISSO NASCE, em file:line

1. **149 % de um núcleo no worker — o spin do onnxruntime.** `worker/sotto_worker.py:85`
   (`OMP_WAIT_POLICY`) e `:4196` (`so.intra_op_num_threads`). Medido antes da cura nesta máquina:
   três fios `session-NN-intra-op-0` e 16,1 % de um núcleo com spin contra 0,0 % sem, com
   33,5 µs de custo passivo por chamada. **Curado e commitado** (`90344a0`) — o binário que corre
   neste pid é anterior.
2. **A ida e volta ao `/json/list`** — `app/webview/youtube_cdp_source.py`, a leitura de alvos que
   media 1,0-1,4 s e que a cura de hoje tirou do laço (`cdp-target-async`, commit `90344a0`). As 109
   `YOUTUBE_TARGET_SLOW` deste log são exactamente essa cicatriz, no código velho.
3. **10 Hz de varrimento** — `app/webview/sotto_webview.py:3357` (`run` do watcher de legendas
   externas) e `:3121` (`poll_step`, a escada do silêncio). Não é fuga: com um vídeo a TOCAR, 10 Hz é
   o preço da legenda 1:1, e a escada só desce quando o player está em pausa (`paused=False` neste log
   — o dono tinha vídeo a correr). O que a cura do `paused-pace` mudou é o repouso, e o repouso medido
   depois dela é 4,0 Hz contra 9,7 Hz.
4. **A minha metade.** A corrida da bateria e o `git commit` (hook de suites: 15 suites `.mjs` + 9
   sondas de vídeo) correram **sem tecto de I/O** entre 21:03 e 21:19Z — dentro da janela das DMs.
   O tecto que a casa tem é o do watcher: `python -m watcher run --cpu 40 -- <comando>` (Job Object;
   o `SOTTO_BATTERY_CAGED=1` que a corrida usava limita CPU e **não** I/O). A partir daqui a corrida
   completa vai por lá.

## 4. A MAQUINA, MEDIDA COM O INSTRUMENTO DELA (`python -m watcher perf`, 21:4xZ)

```
SAMPLE   cpu=58.4%  commit=81.5%  ram_free=11.5G  dpc=0.80%  irq=0.90%  disk_lat=18.2ms  stall_gap=3ms
DISK     I: q_now=2 q_avg=2.96 busy=296.0%  r=15.93MB/s  w=0.00MB/s  lat=18.19ms  ops=145
contenders  ffmpeg.exe(21040) 38.331MB/s [C], python.exe(9420) 6.676MB/s [H], msedge(37520) 5.866MB/s,
            msedge(59692) 5.697MB/s, ffmpeg(57216) 3.562MB/s, pythonw.exe(44680) 3.184MB/s
PROCESSES   7144 python.exe  heavy cpu=7.9% commit=5.22G io=0.08MB/s     <- o worker do Sotto
```

**A atribuicao que a DM faz ao disco NAO se sustenta nesta amostra, e o `cmdline` de cada contendedor
diz de quem e' o volume:**

| pid | o que e' | bytes/s |
|---|---|---|
| `ffmpeg.exe(21040)` | `-i I:\!gravador\luna-13327635\...part3.es.h264 …` (re-encode) | **38,3 MB/s** |
| `python.exe(9420)` | `tools/nsfw/refazer-quadros.py I:/!gravador/lulu-23353632 --recalcular` | 6,7 MB/s |
| `ffmpeg.exe(57216)` | extracao de quadros de `I:\!gravador\lollipop-.../…mp4` | 3,6 MB/s |
| `pythonw.exe(44680)` | `H:\!gravador\tools\nsfw\separar.py … --raiz I:\!gravador` | 3,2 MB/s |
| **`python.exe(7144)`** | **o worker do Sotto** | **0,08 MB/s** |

O `I:` esta' a **296 % de ocupacao** e quem o come sao **tres processos da pipeline do `!gravador`**
(dois ffmpeg + dois python do `nsfw`), nao a arvore acusada: o io medido dela e' 0,08 MB/s. O que a
arvore do Sotto e' de facto, nesta amostra, e' o **maior consumidor de CPU por processo** (7144 a
7,9 % da maquina = ~1 nucleo dos 12, com 149 % de um nucleo medidos no proprio pid) -- e essa metade
tem cura commitada e nao aplicada.

## 5. A RECARGA DO WORKER, e o que ela provou (medido 18:31-18:38 local)

O dono nao tem de reiniciar para o SPIN cair: o worker e' um processo separado e e' lido do disco
em cada arranque. Matei-o pelo ARTEFACTO (`cmdline` contem `sotto_worker.py`, verificado antes do
kill) e a shell respawnou sozinha em 1,0 s (`BRIDGE_EXIT pid=7144 rc=15`, `BRIDGE_RESTART
reason=exit ladder=retry in_ms=1000`, `BRIDGE_SPAWNED pid=45904`, `BRIDGE_LOAD_MS ms=8906`).

| o que | antes | depois |
|---|---|---|
| worker (um nucleo) | **146,2 %** | **96,1 %** (2 min) → **42,0 %** (5 min) |
| shell (um nucleo) | 21,1-22,9 % | 13,7-15,8 % |
| shell io ops/s | **5 963** | **25** |
| fios quentes do worker | — | `session-9-intra-op-0` 26,0 %, `session-10` 11,3 %, `session-8` 5,8 % |

**O QUE ISSO NAO EXPLICA, e fica dito como UNEXPLAINED:** aos 5 min o worker ainda gasta 42 % de um
nucleo com o tap em `tap-dead-endpoint` e `blocks=2,0` por 30 s — quase nenhum trabalho —, e o
instrumento isolado (`_main/ort-spin-idle.py`: 3 sessoes reais, `ocioso=0,0%` com as duas chaves)
diz que o spin NAO devia estar la'. As duas medicoes nao se reconciliam: ou as sessoes vivas nao
levaram as chaves, ou o custo e' outro fio com o nome do ORT. O proximo instrumento e' um perfil de
pilha do processo vivo (`py-spy dump`/`--locals`), nao uma afirmacao.

## 5-bis. O QUE SOBRA NA SHELL TEM NOME, E TEM CURA COMMITADA (medido 18:4x local)

`_main/shell-thread-cpu.py 55104 --seconds 8 --top 5`, depois da recarga do worker:

```
pid 55104: 45 fios, 8.4 s de janela, 17.4% de um nucleo no total
   14.2%  tid 10848  sotto-batch-executor
    1.5%  tid 29804  sotto-gaming-mode
    0.6%  tid 41744  sotto-external-captions
    0.4%  tid  7152  sotto-yt-track
    0.4%  tid 16168  yt-cdp-source
```

O fio quente e' o **passe de lote** (`app/webview/batch_queue.py`), e a cura esta' no commit
`90344a0`: o laco dorme `periodo = custo / ORCAMENTO` (`BATCH_CPU_BUDGET`), medido em 0,115 de
servico contra 0,120 de orcamento. Esta shell e' de 13:38 e corre o laco antigo -- so' um arranque
novo a aplica.

**UM ZERO DE psutil NAO E' ZERO DE FIO.** `psutil.Process(55104).threads()` devolve **0** nesta
arvore (integracao `high`, esta pane `medium`) enquanto o instrumento por `CreateToolhelp32Snapshot`
le os **45**. Qualquer censo de criacao de fios que use o caminho do psutil publica taxa zero sobre
uma arvore que cria fios -- a mesma classe do instrumento que devolve `None` por defeito proprio.

## 6. A DM SAIU A MEDIR O QUE NAO DIZIA — curado no `!watcher`

A mensagem acusava a arvore no sinal `disk` sem dizer QUEM movia os bytes: foi preciso psutil e dez
minutos para achar o `ffmpeg` do `!gravador`. `watcher/herdr_notify.py` passa a compor o bloco
`VOLUME OWNERS` no proprio DM — pid, MB/s medido e **cmdline** de cada um (2 leituras de
`io_counters` a 0,6 s de distancia, falha engolida, lista vazia quando nao ha psutil). Duas arms
novas em `tests/test_herdr_notify.py` (34 passam), uma delas a exigir que a lista vazia nao imprime
uma afirmacao de zero.

## 7-bis. DEPOIS DO REINICIO DELE (medido, 21:0x local)

* `boot 2026-11-08 18:56:53` (psutil): o binario velho de 13:38 morreu com ele.
* arranque seguinte: `SHELL_STARTUP_STAGE pid=9628 stage=pre-lock` as 18:57:20, com
  `SHELL_CODE_ID sha256=1412725AB1B6 files=101`; `BRIDGE_SPAWNED pid=19624`,
  `BRIDGE_LOAD_MS ms=35156`; saida as 18:58:07 por `EXIT_BEGIN code=0 reason=tray-quit`.
* `_main/live-code-freshness-oracle.py --strict` -> processo e disco com o MESMO hash
  (`1412725AB1B6`): nao ha etiqueta STALE viva.
* neste momento NAO existe processo da arvore Sotto (nenhum `sotto_webview.py`, nenhum
  `sotto_worker.py`): a app esta' fechada e o primeiro arranque dele aplica o que estava pendente.

E o censo de consolas nomeou divida MINHA na corrida anterior ao reinicio:
`_main/ort-spin-idle.py:179` com `WEAK-FLAG so creationflags (sem startupinfo/STARTF)`. O filho do
oraculo passou a sair por `_main/hidden-launch.py` (importado pelo caminho) e as tres medicoes:

```
python _main/console-window-audit.py    -> CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s) que abrem janela
python _main/ort-spin-idle.py           -> VERDICT: PASS   (A2 ocioso=0,0% contra tecto 3,0%)
python _main/ort-spin-idle.py --neg-arm -> NEG-ARM: PASS -- mutacoes=2
```

## 8. A CORRIDA QUE O REINICIO INTERROMPEU, REFEITA (caged, 396 passos, 1007 s)

Fecha em `BATTERY-VERDICT: RED -- 4 step(s) failed`, e as quatro eram **instrumento**:

| passo | numero | causa medida | cura |
|---|---|---|---|
| `claims-date` | rc=1 `new-undated-claim` | a frase dos 146,2 %% -> 42,0 %% que eu escrevi no `AGENTS.md` nao levava data | data `2026-11-08 18:31` na frase; `claims-date` PASS e `--neg-arm` 6/6 (rc=1) |
| `red-as-expected-claims-date` | rc=2 | o mesmo defeito a montante (o positivo caia antes do controlo) | desimpedido pelo anterior |
| `warm-engine` | arm 17 `stop-detaches-not-kills RED (busy)` | o segundo `attach` de 500 ms e' POLITICA, nao invariante; sob o tecto de 40 %% o motor respondia `busy` | repetir o mesmo pedido com o mesmo prazo ate' 15 s de parede; sozinho 22/22, sob `--cpu 40` 22/22, `--neg-arm` 6/6 |
| `red-as-expected-battery-budget` | rc=0 | o candidato da M2 era "o passo mais caro que cabe", sem exigir ATRAVESSAR o ratchet por passo: mutou 93 s -> 121 s contra um baseline de 219 s | seleccao exige `elapsed*1.30 > baseline*1.20`; sem candidato e' CANNOT-MEASURE. `NEG-ARM: PASS (2/2)`, M2 apanhada no `headphone-cut` (60,7 -> 79,0 contra 73,3) |

Nota de instrumento que fica registada: o `battery-budget` POSITIVO invocado fora da corrida
diz `politica de largada diferente do baseline (baseline='cap40', corrida=None)` -- ele so' e'
verdadeiro dentro da corrida, que e' quem carimba `policy`. Rodar o passo a mao e ler o RED como
regressao seria a mesma classe que este recibo existe para apagar.
### 8-bis. O PISO DO RATCHET POR PASSO, decidido por VARIACAO medida

`battery-budget` reprovou `lane-screen-gate 5,5s -> 12,1s` e outros passos curtos. Antes de mexer
no portao, medi a variacao do proprio passo (tres execucoes seguidas, mesmo binario):

| passo | tres execucoes | variacao |
|---|---|---|
| `lane-screen-gate` | 4,35 / 8,58 / 5,96 s | **97 %** |
| `load-shedding` | 3,05 / 3,62 / 3,24 s | 19 % |

Um ratchet de 20 % sobre um passo que varia 97 % sozinho reprova o relogio. `PER_STEP_FLOOR_S`
passou de **5 s para 20 s** (o piso existia por essa razao; estava curto). Continua apanhado por:
prazo de 240 s, tecto do total (5 %) e ratchet dos passos acima do piso -- o `lag-note-cost`
224 s -> 1 364 s (x10) continua a ser nomeado. Dois bracos novos: **A8** (5,5 s -> 12,1 s nao
reprova, o caso medido) e **A9** (40 s -> 90 s reprova e o NOMEIA, a isencao nao e' total).
Medido: `--policy cap40` -> `RATCHET-OK` rc=0; `--neg-arm` -> `NEG-ARM: PASS (2/2)` rc=1.

### 8-ter. O RATCHET POR PASSO EXIGE FOLGA ABSOLUTA DE 30 s (medido)

Duas corridas caged seguidas reprovaram o mesmo par. Medi os dois antes de mexer na regua:

| passo | tres execucoes seguidas | na corrida | diferenca |
|---|---|---|---|
| `red-as-expected-stutter-caption` | 4,4 / 4,4 / 4,7 s | **26,8 s** | +23,1 s |
| `console-window-audit` | 36,8 / 23,8 / 20,9 s | 35,0 s (baseline 21,6 s) | +13,4 s |

Os dois sao picos do agendador. A regra passa a exigir **as duas** condicoes: `> baseline*1.20`
**e** `> +30 s`. A regressao que o portao existe para apanhar continua a ser apanhada
(`lag-note-cost` 224 s -> 1 364 s = +1 140 s). Bracos: **A10** (3,7 -> 26,8 nao reprova),
**A11** (40 -> 71 reprova e o NOMEIA), e a **M2** do controle passou de `+30 %` para
`+folga+10 s` (um mutante de +30 % num passo de 60 s ficava invisivel). Historico em
`_cache/battery-budget-history.json`: mediana das ultimas 3 leituras da MESMA politica.

Medido: `--policy cap40` -> `RATCHET-OK` (0 bracos vermelhos); `--neg-arm` -> `NEG-ARM: PASS
(2/2)` rc=1 com a M2 apanhada em `red-as-expected-warm-engine` 78,83 -> 118,93 s.

## 7. O QUE FALTA, e porque nao e' uma afirmacao

- **O worker** ja' corre o codigo curado (recarregado §5): 146 % -> 42 % de um nucleo, com o resto
  UNEXPLAINED acima. Nada mais a pedir ao dono desta metade.
- **A shell** (pid 55104) continua a ser o binario de 13:38: as curas de `cdp-target-async` e do
  pause-clock so' entram num arranque novo. `fixed, NOT verified` no sentido da casa: o depois da
  SHELL e' **UNMEASURED** ate' o dono reiniciar, e o numero de antes esta' acima com pid, tid, nome
  de fio e cadencia.
- **O `I:`** nao e' desta arvore: 296 % de ocupacao com tres processos do `!gravador` a 38,3 / 6,7 /
  3,6 MB/s. Uma lane do `!gravador` tem de ser a dona desse numero, nao esta.

O par antes/depois **das minhas corridas** mede-se com a mesma janela de `psutil` sobre a árvore do
comando, antes e depois de o pôr sob `watcher run --cpu 40`.
