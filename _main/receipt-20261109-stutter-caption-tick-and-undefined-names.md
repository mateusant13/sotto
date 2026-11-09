# RECIBO — o fio quente que a DM de stutter nomeou, e a classe que o deixou passar

Medido nesta máquina, hoje (2026-11-09). Dois DMs independentes acusaram a mesma árvore
(`watcher` 15:28, `w12:p7` 15:3x), e ambos apontavam **um** fio: `tid=20408`, 12,81 s de
20,7 s de janela.

## 1. O culpado, nomeado

| medida | instrumento | valor |
|---|---|---|
| processo vivo ANTES | `_main/shell-thread-cpu.py` e `shell-thread-budget-oracle` | `pid=50452 total=102,2 % de um núcleo`, `sotto-caption-tick tid=20408 = 86,3 %` |
| idade do código dele | `live-code-freshness-oracle.py --strict` | `STALE`, `pid=50452 started=08:14:03`, **17 ficheiros** com mtime posterior |
| processo vivo DEPOIS | `_main/shell-thread-cpu.py 33676 --seconds 8 --top 8` | `pid=33676: 48 fios, 13,0 % de um núcleo no total`; o fio mais quente é `sotto-yt-track` a 5,3 % |

O fio chama-se `sotto-caption-tick` (`app/webview/caption_overlay.py`, `_arm_tick`/`_tick_loop`).
A instância do dono corria o código **anterior** à cura do orçamento de pintura: o laço pedia um
quadro a cada `word_fade.FRAME_S` sem olhar ao custo, e a pintura custa **11,6 ms p50** no tamanho
real da caixa — um piso de ~69–100 % de um núcleo por construção. O código do disco já tinha a
regra: `periodo = custo / CAPTION_FRAME_BUDGET` com `CAPTION_FRAME_BUDGET = 0,40`
(`_limit_by_paint`), e é essa a diferença entre 102,2 % e 13,0 %.

**A cura é a instância nova, não um patch novo.** O que faltava era o processo ler o disco:
`_main/sotto-relaunch.py --relaunch --tag "watcher-dm-16bb006e"` matou o pid 50452 (identidade
pelo mutex do próprio log) e largou `runner=run.cmd` com o token de 13676; o pid **33676** ganhou
a mutex às 15:34:59 e a etiqueta dele é `88A0ED7098DB`, a do disco.

## 2. O que a instância nova mostrou em 15 segundos de vida

```
YOUTUBE_PAINT_READ_FAILED error=NameError("name 'source' is not defined")   x ~15 em 2 s
```
`app/webview/sotto_webview.py`, ramo da foto VELHA (`cdp-stale`): `self._yt_health_tick(source, …)`
usava um nome que é **parâmetro de outra função** do mesmo ficheiro. A excepção era engolida pelo
`except` exterior **antes** de entregar `got`, portanto enquanto o snapshot aquecia nenhuma linha
chegava ao ecrã — e o log escrevia uma linha por tick (10 Hz = 10 escritas/s).

**Porque nenhum portão o viu:** `_main/undefined-names-oracle.py` resolvia nomes por **ficheiro**
("definido em qualquer escopo"), aproximação declarada no próprio docstring. `source` existe como
parâmetro de outra função, logo contava como definido. O mesmo instrumento, agora por **escopo**
(`symtable`, a semântica do CPython), apanhou **dois** nomes no ficheiro:

1. `source` (acima);
2. `external_subs._window_title(hwnd)` em `_yt_identify` — módulo **nunca importado naquele escopo**
   (o ficheiro importa-o localmente em 3494, 3778 e 4039). O `except: pass` engolia-o, e a cura do
   desempate de **duas abas `watch`** que aquela linha existe para fazer **nunca corria**
   (`YOUTUBE_CDP_SOURCE state=ambiguous` era o sintoma documentado).

Depois das duas curas: varredura escopada = **0 nomes** nos 19 ficheiros de produção.

## 3. Custo no caminho do arrasto (mesma classe, outro sítio)

`_set_strip_offset` fazia `log(...)` **por movimento** — medido antes, 277 movimentos em 1,86 s
(~149/s), e cada `log()` escreve no stdout **e** enfileira para o ficheiro. Agora: uma linha na
primeira amostra e uma no `end`, com `moves=` (o número que interessa). O oráculo do arrasto mede
`A7 zero-log-por-amostra` (0 linhas / 67 amostras).

## 4. Portões — medidos, com o braço negativo

| portão | resultado |
|---|---|
| `caption-overlay-theme-oracle.py` | `VERDICT: PASS (9/9)`; `--neg-arm` **4/4** mutantes (`criacao-veste-o-desenho` incluído) |
| `panel-history-wheel-probe.mjs` | `PROBE GREEN` (W2 1:1, W3 rajada ×6,86, W4 pressão do meio); `--neg-arm` **3/3 RED** |
| `undefined-names-oracle.py` | `GREEN — 19 ficheiros, 0 nomes`; `--neg-arm` **3 mutantes** (nome não importado, parâmetro de outra função, módulo sem import) |
| `window-drag-oracle.py` | `VERDICT: PASS (9/9)`; `--neg-arm` `PASS` |
| `agents-md-pins-oracle.py` | `PASS — 2 pin(s) checked live` |
| `battery-wiring-oracle.py` | `PASS checks=7 fail=0` — `ligados=170 sem_passo=109 populacao=279` |
| `battery-record-pairing-oracle.py` | `PASS — 419 passos, 419 nomes com registo, 0 achados` |
| `battery-class-oracle.py` | `PASS — arms=3 fail=0` |

## 5. O que NÃO está provado

- **A taxa do arrasto numa máquina carregada.** `A6 taxa-entregue` media 222,2 Hz (RED) e 239,9 Hz
  (GREEN) no mesmo minuto, com a caixa a 81 % de CPU. O piso passou a **200 Hz** com a razão escrita
  no código: o braço existe para apanhar a regressão de 60 Hz, não o escalonador do Windows.
- **A metade `insufficient-integrity` da DM.** O watcher não consegue despromover esta árvore
  (`winerror 5`) porque a app corre a integridade `high`. A alternativa (a) da DM — relançar
  NÃO-elevada — está medida como impossível nesta caixa: um filho `medium` falha
  `WEBVIEW2_INIT_FAILED 0x80010108` e `TRAY_ICON_ADD winerror=5`. Fica registado, não corrigido.
- **A tela do dono.** O painel não foi aberto por esta lane; `verified` continua a exigir a mão dele.
