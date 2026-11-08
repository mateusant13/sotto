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
| `THREAD_CPU total` (censo da app) | **31-39 %** | **0 linhas** = abaixo do piso de publicacao |
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

## 6. O QUE NAO ESTA' MEDIDO

* **A instancia viva (19896) ficou STALE de novo** pelos dois instrumentos da seccao 4(b): eles nao
  mudam comportamento, mas o `sha256` do disco ja' nao e' o que ela carregou. Entram no proximo
  arranque; o `live-code-freshness-oracle` diz `STALE` e nomeia o `pid` -- e' a verdade, e e' o
  proprio portao a funcionar.
* **A causa do `tick.stall` de 11 675 ms** do `watcher perf` nao esta' atribuida. As amostras do
  proprio watcher apontam `dpc=0.71-5.00 %` e `-> python.exe (pid 44176)` (o amostrador), nao a
  arvore da app; sem `profile` por thread (que o watcher declara impossivel neste processo) fica
  UNMEASURED, e nao se afirma que e' da app.
* **A primeira metade da relancada custou 45 s** (4 pids ainda vivos, duas tentativas de kill): o
  `kill` por token devolveu `ok=False` em cinco alvos de oito antes de conseguir. E' o mesmo caminho
  que o `launch-as-token` ja' documenta; nao foi investigado nesta rodada.
