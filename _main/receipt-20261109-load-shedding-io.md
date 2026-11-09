# RECIBO - o IO de um oraculo desta casa (2026-11-09)

O watcher acusou duas vezes, a segunda com ordem do dono (*"acabou de acontecer stutter. culpa de
quem?"*): `python.exe(55392) = H:/sotto/_main/load-shedding-oracle.py --neg-arm`, **pico 184,1 MB/s**
no `I:`, 3 episodios em 60 min, 568 s de vida. As tres exigencias estao respondidas com numero.

## 0. O que a medicao REFUTOU no pedido

* **"184 MB/s e' carregamento repetido" (do modelo): nao e'.** Este oraculo nao carrega motor
  nenhum -- a ARM 14 le o `batch_queue.py` como TEXTO e as arms de carga usam um duble
  (`self.loads += 1`). **0 carregamentos por bateria**, positivo e negativo.
* **"o log parou as 12:54:40, 3 h sem escrita"**: nao parou. Medido no instante da leitura,
  `st_mtime` do `_main/webview-run.log` = **12:55:18, idade 0,0 min**, e a cauda traz
  `YOUTUBE_CDP_SOURCE state=attached` as 12:55:18. O log estava vivo quando a DM foi escrita.

O IO era outro, e cabe numa linha: o log do dono tem **70,6 MB** e o oraculo o lia INTEIRO sempre
que precisava de saber qual e' a instancia viva -- `shell_launches()` lia, `newest_shell_segment()`
lia outra vez, o escolhedor antigo lia uma terceira, e o `--neg-arm` executa o conjunto duas vezes.

## 1. A cura

Duas coisas, nesta ordem, porque a primeira sozinha **quase nao pegou**:

1. **memoizar** a leitura por `(caminho, mtime, tamanho)`. Medido: 4 119 -> **4 012 MB**. O log VIVO
   cresce entre duas chamadas, o `mtime` muda e o memo vence -- memoria nao era o problema.
2. **ler a CAUDA, nao o ficheiro**: `read_log(path, window_mb=4.0)` faz `seek` para
   `size - 4 MB`, alinhado ao comeco de uma linha. O que este oraculo precisa (quem e' a instancia
   viva) esta' nos ultimos KB. Um ficheiro menor que a janela e' lido inteiro, logo as fixtures das
   arms continuam exatas.

O contador vive no proprio ficheiro: com `SOTTO_LOG_READS=1` o processo imprime
`LOG_READS reads=.. memo_hits=.. mb=..`; positivo medido -- `reads=2 memo_hits=8 mb=4.0`.

## 2. Os numeros, antes e depois, mesmo comando e mesma sonda

| braco | rc | parede | pico | lido | escrito |
|---|---|---|---|---|---|
| ANTES, `--neg-arm` solto | 1 | 82,7 s | **140,1 MB/s** | **1 524 MB** | 48 MB |
| DEPOIS, `--neg-arm` solto | 1 | 82,5 s | **29,4 MB/s** | **475 MB** | 95 MB |
| ANTES, sob `watcher run --cpu 40 --single` | 15 (morto pela minha sonda) | 435,2 s | **145,9 MB/s** | **4 119 MB** | 89 MB |
| DEPOIS, sob `watcher run --cpu 40 --single` | 0 | **201,9 s** | **25,2 MB/s** | **478 MB** | 94 MB |

**3,2x menos lido e 4,8x menos pico** solto; **8,6x menos lido, 5,8x menos pico e 2,2x menos parede**
sob o tecto. Veredicto nos dois casos: `NEG-ARM PASS` (o mutante continua a derrubar o oraculo).
Positivo: `LOAD-SHEDDING GREEN -- arms=252 pass=252 fail=0` em 2,2 s (era 5,2 s).

Instrumento das quatro linhas: `python _main/shell-thread-cpu.py --io -- <comando>` (novo, §3).
Ficheiros das corridas: `_main/_cache/ls-neg-caged-after2.txt`, `_main/_cache/load-shedding-neg.out`.

## 3. O instrumento que faltava

`_main/shell-thread-cpu.py --io -- <cmd>`: amostra `psutil.io_counters()` da ARVORE a 0,2 s e publica
`IO-TREE rc=.. wall=..s peak=.. MB/s read=.. MB write=.. MB`. Ele mora no instrumento de CPU desta
familia (arvore = fios + IO), nao numa sonda nova; o `--neg-arm` dele continua 5/5.

Duas correcoes de instrumento, as duas medidas hoje: (a) o total e' `ultimo - primeiro` por pid, nao
a soma dos deltas -- a primeira versao devolveu **0 MB** para um processo que leu 70 MB, e um
instrumento que diz "nao houve IO" quando houve e' pior do que nao existir; (b) amostra de 0,5 s
nunca via um processo de 1 s de vida.

## 4. A CLASSE, varrida -- e o que NAO se mudou

Sete oraculos tocam o log vivo. Tres leem o ficheiro inteiro (`caption-budget` 1, `youtube-land` 2,
`time-to-first-caption` 1); os outros citam-no em comentario ou ja' usam `seek`.

Medi a janela curta nos dois primeiros e **elas nao pagam** -- os dados estao no lado errado do
ficheiro:

| marca | no ficheiro | nos ultimos 32 MB | nos ultimos 8 MB |
|---|---|---|---|
| `CAPTION_LAND` | 5 860 | (o 200o mais recente a **16,7 MB** do fim) | **0** |
| `CAPTION_PAINT_LAG` | 2 110 | **3** | **0** |

Uma janela de 8 MB transformava `youtube-land` de MENSURAVEL em `SKIPPED` -- cortar dados em
silencio e' pior do que ler devagar -- e uma escada de janelas crescentes custou **178 MB** contra os
116 MB do ficheiro inteiro. Os dois ficheiros foram **REVERTIDOS** (nao se entrega uma
nao-melhoria com mais codigo); o que fica e' a medida e a razao escrita aqui.

## 5. UM ERRO MEU, nomeado

Ao limpar as minhas corridas duplicadas eu filtrei `'watcher' in cmdline and 'run --cpu 40'` e matei
**tres processos que nao eram meus**: `12700`, `59064`, `61216` -- e o `61216` era
`python -m watcher run --cpu 40 -- python -m pytest -q H:/codeintel-worktrees/...`, o tecto de outra
lane. A regra da casa e' **um filtro de kill nomeia o ARTEFACTO**: daqui para a frente o filtro e'
`load-shedding-oracle.py` / `shell-thread-cpu.py --io`, nunca a palavra `watcher`.

## 6. As tres exigencias da DM

1. **"a bateria corre sob `python -m watcher run --cpu 40`"** -- a bateria principal ja' se
   re-executa dentro do tecto (`_main/_audit-verify-all.cmd`: o bloco do `CAGE` vive antes do
   `setlocal`, `SOTTO_BATTERY_NOCAGE=1` e' a saida, o sumario imprime `caged:`). O pid que o watcher
   matou **nao** veio da bateria: `grep -n load-shedding _main/_audit-verify-all.cmd` da' a linha
   2966, que corre o POSITIVO; nenhuma linha corre o `--neg-arm`. O `--neg-arm` e' corrida a mao --
   minha e da lane do `opencode` -- e as minhas passam a correr cagetadas (as medidas deste recibo
   foram feitas assim).
2. **"uma arma por vez, modelo carregado uma vez"** -- modelo: **0 carregamentos**. O que era
   repetido era a LEITURA: agora e' uma janela de 4 MB por processo, contada.
3. **"ficheiros em `H:/sotto/_main/_cache`"** -- e' onde estao as saidas desta rodada. Nada em
   `G:/Temp/opencode`.

## 7. O QUE NAO ESTA' VERIFICADO

* Nada disto foi visto na app do dono: o oraculo nao abre janela nem renderiza audio.
* O pico de 184,1 MB/s do watcher e o meu de 140-146 MB/s medem a mesma classe em instantes
  diferentes; o pico do watcher inclui o IO do proprio observador.
