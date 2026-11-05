# O disco desta maquina paga 2,6 s de fila num unico transfer -- e o gate central ve'-o como um pico

**Data:** 2026-11-05 06:3x-06:5x (horario local da maquina do dono)
**Ordem que isto serve:** *"o PC inteiro trava: herdr, os terminais dentro dele, o
chrome, tudo ao mesmo tempo"* (P1 do plano de 2026-11-05).
**Instrumentos:** `_main/disk-who-probe.py` (atribuicao por processo) e a leitura de
latencia do proprio gate central (`I:/!manager/tools/performance-gate.py`,
`read_disk_latency`), com o `--cross-check` do probe a comparar as duas rulers.

## O que foi medido

| janela | amostras | p50 | p95 | p99 | max | >100 ms | >250 ms | >500 ms |
|---|---|---|---|---|---|---|---|---|
| 201 s, 250 ms por amostra | 333 | 15,0 ms | 290,9 ms | 1149,3 ms | 2675,6 ms | 48 (14,4 %) | 23 | 10 |

Leituras que falharam (o `powershell` do gate estourou o teto de 12 s): **2 de 335**.
Isso tambem e' dado: sob a propria carga que ele mede, o instrumento do gate as vezes
nao responde, e um `UNKNOWN` do gate nao e' disco saudavel.

O estado do gate na mesma hora alternou: as 06:3x `RED
disk-latency-sustained=418.8ms`; minutos depois `GREEN` com `disk-latency-max=1033.6ms
on 1 of 2 samples, not sustained`. Isto e' a MESMA verdade vista por duas janelas: um
pico de 1 s nao e' "sustentado" para o gate, e e' exactamente o que o dono sente.

## Quem paga (nao ha' um unico culpado)

Medido as 06:3x com 489 processos lidos, 0 ilegiveis, queue media 10,3, latencia 17,0 ms
-- **VERDICT: SPREAD**, top 8 somam ~13 MB/s:

| pid | processo | io MB/s | share |
|---|---|---|---|
| 28212 | python (pytest do **vodrip**, sobre `archive.db-wal`) | 4,14 | 24,8 % |
| 6672 | droid.exe | 2,42 | 14,6 % |
| 49468 | msedgewebview2 renderer (**Sotto**) | 2,12 | 12,7 % |
| 34048 | msedgewebview2 gpu (**Sotto**) | 2,04 | 12,3 % |
| 47552 | msedge.exe | 1,29 | 7,7 % |
| 4176 | svchost.exe | 1,13 | 6,8 % |
| 42724 | msedge.exe | 0,79 | 4,7 % |
| 8804 | ffmpeg (vodrip, a escrever `audio.wav` de um VOD da Twitch) | 0,75 | 4,5 % |

## O que NAO e' (medido, para nao se repetir a hipotese)

- **O cache do WebView2 do Sotto nao cresce.** `G:\Temp\tmp5lot7ufm\EBWebView`: **70,5 MB
  / 242 ficheiros** antes e depois de 45 s -- **0,00 MB/s**. Os 2-3 MB/s que o
  `psutil` atribui ao renderer **nao sao ficheiros** (sao commit/paginas), logo nao ha'
  aqui "espaco em disco desperdicado" para limpar.
- Os dois maiores escritores **nao sao o Sotto**: sao lanes do repo `vodrip` (um pytest
  sobre o `archive.db-wal` e um `ffmpeg` a transcrever um VOD). `G:\Temp` tem ~4,0 GB de
  scratch `vodrip-*`; 10 directorios `vodrip-shardtest-scope-*` estao parados ha mais de
  1 h e **nenhum processo vivo os segura** (medido com `open_files`).

## O que isto NAO prova

1. **Nao prova que o Sotto causa o freeze.** Prova o contrario do que era mais facil
   afirmar: ele e' o 3.o e 4.o termo, atras de duas lanes de outro repo.
2. **Nao prova que a fila (queue 9-10) e' a causa da latencia** -- so' que elas coexistem.
   Um disco HDD com I/O pequeno e aleatorio produz fila alta com poucos MB/s; um SSD nao.
   Qual dos dois esta' nesta maquina **nao foi medido aqui**.
3. A janela de 30 min do `freeze-census-long` continua a correr para apanhar o evento em
   vez de o esperar; ela mede o ATRASO do proprio tick, que e' a testemunha do freeze.

## Duas correccoes de instrumento, no mesmo ficheiro

- A primeira versao do `disk-who-probe.py` lia `AvgDisksecPerTransfer` como SEGUNDOS e
  publicou `latency_ms=981746603000.0`. O campo e' um `PERF_AVERAGE_TIMER` em ticks de
  100 ns que so' significa contra o seu `_Base`: `(t1-t0)/(b1-b0)`. O `--cross-check`
  compara agora com `read_disk_latency` do gate; o criterio e' de **formula** (10x ou
  200 ms) e nao de igualdade, porque as duas leituras cobrem intervalos consecutivos e a
  latencia vai de 0,07 a 418 ms na mesma maquina.
- O controle de formula media "bateu" com 2x de tolerancia e dava FAIL em 29,6 ms contra
  10,4 ms; medido que era variancia normal entre janelas vizinhas, o criterio passou a
  10x/200 ms -- e o que ele guarda e' o erro de FORMULA, que aparece com ordens de
  grandeza.

## O TERMO DOMINANTE, medido depois disso: o volume **I:**, um HDD

Geometria da maquina (`Get-PhysicalDisk`, 2026-11-05):

| disco | modelo | tipo | volumes |
|---|---|---|---|
| 5 | XPG GAMMIX S70 BLADE | **SSD NVMe** | C:, H: |
| 4 | XPG GAMMIX S11 Pro | **SSD NVMe** | G: |
| 3 | ST4000DM004-2U9104 | **HDD SATA** | **I:** |
| 1 | WDC WD10EZEX | HDD SATA | D: |
| 0 | ST3500312CS | HDD SATA | E: |
| 2 | KINGSTON SA400S37240G | SSD SATA | F: |

Latencia e fila POR DISCO (`python _main/disk-who-probe.py --per-disk 45`, 45 s):

| disco | fila | transferencias | latencia |
|---|---|---|---|
| **3 I:** | **5,00** | 2 383 | **41,4 ms** |
| `_Total` | 5,00 | 9 788 | 10,6 ms |
| 5 H: C: | 0,00 | 6 624 | 0,7 ms |
| 4 G: | 0,00 | 781 | 0,3 ms |
| 0 E: / 1 D: / 2 F: | 0,00 | 0 | 0,0 ms |

**Toda a fila desta maquina esta' no I:.** Os dois NVMe's onde vivem o repo (`H:`) e o scratch
(`G:`) estao a sub-milissegundo com fila zero. O I: e' onde vivem `I:/!manager`, o estado e o
lease do gate central, os worktrees (`I:/wt`) e a sessao dos agentes -- ou seja, **o HDD e' o
disco de TODA a infra-estrutura da frota**, e e' ele que paga 41 ms por transferencia e 5 de fila.

Isso explica o sintoma exacto que o dono descreveu (*"herdr, os terminais dentro dele, o chrome"*):
o herdr e os terminais leem estado do I:, e um pico de 1 s nesse HDD congela-os **a todos ao mesmo
tempo**, enquanto os NVMe's nao mostram nada.

**Consequencia para o gate central:** ele amostra `_Total` (`Win32_PerfRawData_PerfDisk_PhysicalDisk`,
`Name='_Total'`), que mistura um HDD lento com dois NVMe rapidos no mesmo numero. Um burst no I:
aparece como "o disco da maquina esta' a 418 ms" -- verdadeiro para o I:, falso para o resto. Uma
leitura por disco seria mais util ao dono **e** mais honesta: hoje o gate pode ficar RED por causa
de um volume que o Sotto nem usa.

## A armadilha do modo por disco (e porque ele RECUSA em vez de arredondar)

Na primeira leitura por instancia (60 s), o `3 I:` publicou **latencia -6,0 ms** com fila 4,5. Um
delta negativo de `AvgDisksecPerTransfer`/`_Base`: nas instancias o WMI pode reiniciar o par entre
duas leituras. O modo `--per-disk` devolve `n/a` com `why='delta-invertido'` e publica a FILA
sempre -- a fila nao depende de delta e foi ela que identificou o disco. `None` nunca e' 0.

## Proximo passo que isto habilita

Antes de cortar qualquer termo, medir **qual volume** paga a latencia e a sua
**geometria** (HDD x SSD, 512e x 4Kn, profundidade de fila suportada). Sem isso, "cortar
o termo dominante" escolhe entre 13 MB/s de MB/s e 10 de fila -- e escolhe mal.

Agora com nome: **tirar do I: o que nao precisa de estado la'** (worktrees, caches de build, scratch
de lane) e/ou **declarar o I: como o disco lento que ele e'** para que o gate central leia por disco
em vez de `_Total`. Nenhuma das duas e' mudanca do Sotto, e as duas custam menos do que qualquer
micro-optimizacao do Sotto -- o Sotto e' o 3.o/4.o termo de 13 MB/s, nao a fila.
