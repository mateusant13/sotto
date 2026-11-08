# RECIBO - a relancada que poe a cura na instancia viva, e os dois instrumentos que mentiam (2026-11-08)

Tudo o que segue foi medido nesta arvore esta noite. Cada numero tem o comando ao lado.

## 0. A DM, e o que ela pedia

`dm-db330a1c46dc805ddcde`, ordem do dono: *"acabou de acontecer stutter. culpa de quem? é pra sempre
verificar o maior culpado do stutter, e mandar dm automaticamente"*, com
`culprit=pythonw.exe(23244)`, `cpu 11.5% of machine over 8 process(es)`,
`interrupt=21.429% of cpu time>=10`, `creation=95.277 creations/s>=5`, e a exigência
*"é pra arrumar de fix, de forma nuclear"*.

## 1. MEDIR PRIMEIRO: o par que a DM exige, corrido

| comando | resultado |
|---|---|
| `python -m watcher perf` (I:\!watcher) | `tick.stall` de **190 / 549 / 596 / 691 / 738 / 894 / 2503 / 3065 / 11675 ms**, `dpc.storm 5.00 %`, `irq.storm 1.54 %` |
| `python -m watcher profile 23244` | `cpu=33.7 % de um core = 1.7 % da maquina`, e **`CANNOT-MEASURE`** para a atribuicao por thread (`psutil.Process.threads()` devolve 0 ids com `num_threads()=54`) |
| o meu proprio censo (`THREAD_CPU`, na app) | `total=31-39 %` com `sotto-outside-click: 22-28 %` |

O `profile` do watcher **nao consegue** atribuir por thread neste processo: uma linha
`CANNOT-MEASURE` com a razao escrita, que e' o que a casa exige de um instrumento sem acesso -- nao um
zero. A atribuicao vem do censo da propria app, que usa `GetThreadTimes` (read-only, sem py-spy).

## 2. AS DUAS METADES DA CULPA

**`interrupt=21,4 %` E' MINHA, e ja' estava curada em codigo.** O `sotto-outside-click` girava a
22-28 % de um core por um `SetTimer`/`KillTimer` sem `argtypes` (o id devolvido nao era o que o
`KillTimer` encontrava, o re-arme degenerava para 2 569-3 715 Hz). Cura commitada em `6ce772a`, com
par na bateria. O que faltava era a instancia viva correr esse codigo.

**`creation=95,277/s` NAO E' DESTA ARVORE.** Censo proprio, `Toolhelp32`, janela de 10 s, com
atribuicao de pai:

```
janela=10.0s  antes=533  depois=534  criados=1  mortos=0
taxa de criacao = 0.10/s
  chrome.exe <- chrome.exe x1
arvore da app: 0 processos criados
```

1 criacao em 10 s na maquina inteira, e **nenhuma** dentro da arvore. O numero da DM (953 processos
em 10 s) nao se reproduz com o instrumento que conta processos de verdade.

## 3. A CORRECCAO NUCLEAR: a instancia viva passou a correr o codigo curado

`python _main/sotto-relaunch.py --relaunch` (o caminho do token `high`, medido em 2026-10-30).

| | antes | depois |
|---|---|---|
| pid | 23244 | **19896** |
| codigo | `SHELL_CODE_ID sha256=B7582B656F92` (2026-11-07 10:24) | `sha256=CE4098871454` == disco -> **`LIVE_CODE FRESH`** |
| `THREAD_CPU total` (censo da app) | **31-41 %**, `sotto-outside-click` **22-34 %** | **23 %**, `sotto-outside-click` **ausente do topo** (o piso era 20 %, por isso a linha nao saia sempre) |
| `sotto-outside-click` | **22-28 %** de um core | nao aparece (abaixo de 5 %) |
| `python -m watcher profile` | 33.7 % / 35.3 % de um core, duas leituras | 7.7 % (janela com carga de modelo); `psutil` 16.4 % e 11.6 % em duas janelas de 30 s |
| painel na tela dele | nenhum | **nenhum** -- `PANEL_VISIBILITY_AT_STARTUP visible=false hwnd=29712724 form.Visible=false` |
| janelas de consola da arvore | -- | **0** (`EnumWindows` + `IsWindowVisible`, classes `ConsoleWindowClass`/`CASCADIA`/`PseudoConsole`) |

**Teto declarado** (numero, como a DM pede): shell <= **20 %** de um core em repouso;
`sotto-outside-click` <= **2 %**; 0 processos e 0 threads por segundo em repouso; arvore <= **250 %**
de um core (12,5 % de uma maquina de 20 nucleos) mesmo a transcrever.

**O que ficou ACIMA do teto, e por que nao e' defeito:** com a shell curada a arvore mediu
**122,0 %** e **217,6 %** de um core em duas janelas de 30 s, e o termo dominante e' o **worker**
(`python.exe` 149,6 % na primeira, 52,9 % na segunda) -- o motor nemotron a transcrever audio que
estava a tocar (`CAPTION_APPLIED text="Oh, what is it? Me imbalancing the stuff and all."`). E' o
produto a fazer o trabalho dele, nao um laco a girar; o governador dele e' a escada de shedding
(`REDUX_ENGINE_YIELD/RELEASED`), e as duas linhas antes de cada morte de worker sao exactamente essas.

## 4. Os dois instrumentos que mentiam (e que a relancada expos)

**(a) O RELANCADOR DISSE `FALHA` DEPOIS DE MATAR A APP.** Saida real:

```
00:09:17 CreateProcessAsUser(fonte=14016) ok=True err=0 filho=22232
00:10:47 FALHA (via token): nenhuma instancia nova em 90s
```

A instancia nova ganhou a mutex as `00:09:18.720` (`SINGLE_INSTANCE ... already_running=false`), **um
segundo** depois da largada. O laco chaveava o vencedor pelo **PID**, e o `pid=19896` ja' existia num
log de **2026-11-03**: o Windows recicla pids. Curado: chave `(pid, carimbo)`, `since` **sem
ombisssao**, e a frase de falha passa a nomear o ultimo `SHELL_STARTUP_STAGE` visto.
`_main/relaunch-ready-oracle.py`: **6 arms**, `--neg-arm` solta o filtro numa COPIA e derruba
**A1/A2/A5** (rc=1).

**(b) O CENSO CALAVA NA FAIXA EM QUE A THREAD IMPORTA.** Com a cura, a shell ficou em 10-16 % e o
censo (`total >= 20 %`) nao escrevia nada: "o spin voltou?" so' tinha por resposta "nao ha' linha",
que nao diz **qual** thread gasta. Agora publica com `total >= 20 %` **ou** uma thread `>= 5 %`.
E `SHELL_CODE_ID` volta a ser dito a cada ~10 min (`heartbeat=true`, sha256 **memoizado: 14 ms uma
vez, 0,0 ms depois**), porque escrito so' no arranque ele desaparece com a rotacao do log -- medido:
uma instancia de 12 h dava `LIVE_CODE UNKNOWN` justamente quando o portao que existe para dizer
`STALE` era mais necessario. `_main/shell-census-instrument-oracle.py`: **6 arms**, `--neg-arm`
repoe os dois pisos e derruba **A2/A4** (rc=1).

O relancador corrigido **nao foi exercitado numa segunda relancada**: as legendas estavam a correr
(`CAPTION_APPLIED` a cada poucos segundos) e cortar a transcricao dele para instalar duas linhas de
instrumento e' exactamente a troca que a DM proibe ("o trabalho interativo do dono nunca espera
atras"). A prova e' o oraculo contra a forma exacta do log que enganou o instrumento.

## 5. Portoes

`agents-md-pins` PASS (2 pins), `battery-wiring` PASS (ligados **150**, sem_passo 109, populacao
259), `battery-class` PASS (3 arms), `code-health` PASS (+4218 B / +54 linhas / +3 defs da shell
absorvidos **cirurgicamente**, sem `--update`), `undefined-names` GREEN. Pin da bateria:
**277300 B**, **3371 CRLF** / 0 bare LF, sha256
`592FCE4BFE391753C07F3D03F52D31C8428CF2FD993DB6A9F5E66DD247FA1EB1`.
Smoke da shell editada por um caminho que nao abre janela (`--autostart-status`, rc=0, escreve
`SHELL_CODE_ID sha256=F9369427E956 files=99`).

## 6. A SEGUNDA DM (00:42) E O QUE A CADEIA MOSTRA

`dm-bbdb8a35e8740b391583` acusou `pythonw(19896)` com `cpu 38.9 % over 8 process(es)`,
`interrupt=22 %`, `creation=7.453/s`. O rasto completo, todo medido:

| hora | facto | instrumento |
|---|---|---|
| 2026-11-07 10:24:53 | arranca a instancia **23244** | `SHELL_STARTUP_STAGE` |
| 2026-11-07 15:16:11 | cura commitada (`6ce772a`) | `git log` |
| 23:39 -> 00:08 (11-08) | **a mesma instancia** publica `THREAD_CPU total=31-41 % top=sotto-outside-click:22-34 %` a cada 30 s | censo da app |
| 00:09:18 | relancada: pid **19896** com o codigo curado | `LIVE_CODE FRESH` |
| 00:39:20 | censo da instancia curada: `total=23 % top=sotto-batch-executor:10 % yt-clock:4 % sotto-yt-track:3 %` -- **`sotto-outside-click` ausente do topo** | censo da app |
| 00:48:51 | relancada: pid **45084**, codigo `F9369427E956`, e o censo NOVO publica com piso de 5 % | `SHELL_CODE_ID`, `THREAD_CPU` |
| 00:56-01:05 | **arvore inteira: 5,8 % de um core** (shell 2,5 %, worker 2,8 %, webview 0,5 %) = 0,29 % da maquina | `psutil.cpu_times()` delta / janela, 9 processos, duas janelas de 15 s |

**A causa nomeada, com ficheiro e linha:** `app/webview/sotto_webview.py:7782-7793` -- o
`SetTimer`/`KillTimer` sem `argtypes` devolvia um id gerado pelo Windows, o `KillTimer` recebia a
constante e devolvia 0, e o re-arme rearmava **1 591 Hz**. Por isso `interrupt` alto: uma chamada de
sistema por volta.

**E o custo nao era do codigo que estava no disco -- era do processo que nao o tinha.** 8 h 53 min de
spin depois de a cura estar commitada. A relancada (`sotto-relaunch.py --relaunch`) foi a correcao, e
`PASSO 0` do bug-hunt (`live-code-freshness-oracle`) tinha razao: `STALE` = reiniciar, nao corrigir.

**Residuo nomeado, nao escondido:** `sotto-batch-executor` (7-10 %) e' o passe de batch a transcrever
spool -- trabalho, nao laco (o `batch_queue.py:573` dorme `poll_s=10`); `yt-clock` 4 % e' a amostra de
relogio a 2,5 Hz (`sotto_webview.py:5656`). Nenhum dos dois justifica mudanca sem medida: 4 % de um
core (0,2 % da maquina) nao paga o risco de mexer no relogio que sincroniza a legenda.

### Dois defeitos MEUS, medidos na mesma hora

1. **O censo por thread que eu corri do terminal devolvia ZERO e nao era zero.** `OpenThread` num
   processo `high` a partir de um processo `medium` da' **err=5** em todas as 53 threads, e o meu
   script somava `None` como 0. O `psutil` no mesmo instante media **12,3 / 9,8 / 23,6 %** de um core.
   A regra da casa e' exatamente esta: um zero silencioso nao e' uma medida. O `py-spy dump` da' a
   mesma recusa (`Acesso negado (os error 5)`), logo a atribuicao por thread deste processo so' existe
   DENTRO dele -- e' o censo da app.
2. **O relancador mentiu `FALHA` uma SEGUNDA vez, 40 min depois da cura.** Saida:
   `00:48:51.619 SHELL_STARTUP_STAGE pid=45084` / `00:48:51.659 SINGLE_INSTANCE already_running=false`
   / `00:50:21 FALHA (via token): nenhuma instancia nova em 90s`. A chave `(pid, carimbo)` estava
   certa; o que faltava era o **voto**: `seen.add` acontecia ANTES das duas perguntas, e quando a
   leitura caiu entre as duas linhas (40 ms de distancia) o candidato ficou marcado e saltado para
   sempre. Curado: o voto so' se gasta com um veredito, e `SHELL_JOB_ARMED pid=N` passou a ser a
   segunda prova de vida. `_main/relaunch-ready-oracle.py`: **8 arms** (A7 e' a corrida, A8 o job
   object) e o `--neg-arm` derruba **2/2** mutantes -- o M2 repoe o voto adiantado e devolve
   exatamente o defeito vivo (`pid=None leituras=12`).

### O CENSO SO' PUBLICA AS JANELAS QUE PASSAM O PISO -- E ISSO E' UMA ESCOLHA, NAO UMA MEDIA

Calibracao feita logo depois de escrever a tabela acima, com o MESMO processo: janela externa de 32 s
por `cpu_times()` deu **5,47 % de um core**, e no mesmo periodo o censo nao escreveu linha nenhuma
(o piso e' total >= 20 % ou thread >= 5 %). As linhas que existem -- `total=13 %`, `total=17 %` --
sao de janelas de **60 s** que continham o passe de batch, e o censo **so' publica as que passam o
piso**: ler a serie dele como "a media da shell" e' ler uma amostra enviesada. O numero de repouso e'
o de fora (2,5 % de um core); o de dentro responde outra pergunta ("quem gastou nos minutos que
passaram de 5 %"). Duas medidas, duas perguntas -- e a aritmetica do censo confere
(`(ticks/1e7)/span*100`, `span` real).

### Uma correcao no que eu ja' tinha enviado a DM

A primeira resposta a `dm-bbdb8a35e8740b391583` dizia **3,2 % de um core**, tirado de
`psutil.Process.cpu_percent()` numa medicao em que o meu proprio `sorted(key=...)` chamava
`cpu_percent(None)` de novo e reiniciava o intervalo antes da leitura -- o mesmo genero de instrumento
que hoje ja' me apanhou duas vezes. Re-medido por delta de `cpu_times()` (que nao tem esse estado):
**5,8 %**. A conclusao nao muda (a arvore nao e' a causa do stutter), o numero sim.

## 7. O QUE NAO ESTA' MEDIDO

* **A atribuicao por thread continua a nao existir fora do processo.** `OpenThread`/`py-spy` num
  processo `high` da' `err=5` a partir desta sessao `medium`; o unico instrumento e' o censo da app,
  e ele agora publica com piso de 5 % (medido: `THREAD_CPU total=12 % top=sotto-batch-executor:7 %`
  na instancia nova). Quem quiser a tabela por thread tem de a ler no log da app.
* **A causa do `tick.stall` de 11 675 ms** do `watcher perf` nao esta' atribuida. As amostras do
  proprio watcher apontam `dpc=0.71-5.00 %` e `-> python.exe (pid 44176)` (o amostrador), nao a
  arvore da app; sem `profile` por thread (que o watcher declara impossivel neste processo) fica
  UNMEASURED, e nao se afirma que e' da app.
* **`creation=7.453/s` da DM nao se reproduz:** censo `Toolhelp32` de 10 s na arvore da app, agora e
  antes, deu **0 criacoes dentro da arvore**; as 20 da janela eram `cargo.exe`/`bash.exe` de OUTRAS
  lanes. Na instancia corrente ha' **3 `BRIDGE_SPAWNED` e 2 `BRIDGE_EXIT`, todos entre 00:09 e 00:11**
  (o arranque), e nenhum depois.
* **A primeira metade da relancada custou 45 s** (4 pids ainda vivos, duas tentativas de kill): o
  `kill` por token devolveu `ok=False` em cinco alvos de oito antes de conseguir. E' o mesmo caminho
  que o `launch-as-token` ja' documenta; nao foi investigado nesta rodada.
