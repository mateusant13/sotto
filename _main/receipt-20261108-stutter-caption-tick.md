# RECIBO — o stutter tem nome, fio e linha (2026-11-08)

DM do watcher: *"STUTTER (owner): pythonw.exe(42572) is the top measured culprit — 24 episode(s)
in 60 min"*. Ordem do dono por cima dela, verbatim: *"é pra sempre verificar o maior culpado do
stutter, e mandar dm automaticamente"*, e *"é pra arrumar de fix, de forma nuclear"*.

Este recibo responde ao que a DM exige: o **pid**, o **fio**, a **linha** e o **antes/depois** — ou a
declaração exacta do que NÃO foi medido.

## 1. O culpado, por instrumento externo (não por opinião)

```
$ python _main/shell-thread-budget-oracle.py
SHELL-THREAD-BUDGET pid=42572 total=103.4% ceiling=25% thread_ceiling=15%
     93.6%   48064  sotto-caption-tick
      4.9%   37364  sotto-external-captions
      2.1%   40908  yt-cdp-source
      1.8%   44100  sotto-batch-executor
...
$ python _main/shell-thread-budget-oracle.py     (segunda amostra, minutos depois)
SHELL-THREAD-BUDGET pid=42572 total=103.7% ... 90.5%  48064  sotto-caption-tick
```

`total` é **% de UM núcleo**. O instrumento é `_main/shell-thread-cpu.py` (Toolhelp32Snapshot +
`GetThreadTimes`, exacto por fio; o `py-spy` não anexa a esta shell — medido 2026-11-05).

Reprodutível em duas amostras, com o **mesmo tid**. Isto é o stutter: um fio a queimar um núcleo
inteiro enquanto a legenda anima.

`python -m watcher profile 42572` dá `cpu=33.5% of one core` numa janela de 8 s — **não** contradiz:
a atribuição por fio do `watcher` não está disponível neste processo (`psutil.threads()` devolve 0
ids com `num_threads()=53`), e a janela apanhou um período em que o fio não estava a 100 %.

## 2. O que a DM afirma e NÃO se reproduz

A DM diz `io 10.9MB/s over 9 process(es)`. Medido agora, no mesmo pid e na mesma árvore, com
`psutil.io_counters` em duas amostras separadas por 6 s:

```
TOTAL tree write=0.036 MB/s read=0.022 MB/s
```

O I/O da árvore é **trivial** (76-84 chamadas/s de escrita, kilobytes). O stutter de hoje é **CPU**,
não disco. A linha da DM que se confirma é o pid e a classe de sinal (`interrupt`), não o número de
MB/s.

## 3. A linha: `app/webview/caption_overlay.py` — o periodo do quadro

**O QUE O PROCESSO VIVO CORRE (verificado, não suposto).** `git show 7ec728d^:app/webview/word_fade.py`
dá `FRAME_S = 1.0 / 60.0` e `git show 7ec728d^:app/webview/caption_overlay.py` dá **zero** ocorrências
de `_limit_by_paint`: a instância arrancada às 04:01:44 pede **60 Hz** e não tem limite nenhum por
custo. Com a pintura medida em **11,6 ms p95 / 6,7 ms p50**, o piso é 11,6/16,7 = **69 %** de um
núcleo — e o fio mede 93 % porque ainda lê o arrasto e o relógio no mesmo ciclo.

**A SEGUNDA METADE, que ainda não está viva.** A cura de 240 Hz escrita às 07:2x (`7ec728d`) pôs o
período **igual** ao custo medido (`cost * 1.02`). Isso é o mesmo defeito na forma pior: um laço que
dorme exactamente o tempo que trabalha gasta **100 % de um núcleo por construção**, e a 60 Hz ele
teria passado de 69 % para 100 %.

**A CURA, nesta árvore:** `caption_overlay.py:81` declara `CAPTION_FRAME_BUDGET = 0.40` e `:857`
calcula `floor = cost / CAPTION_FRAME_BUDGET` — a pintura ocupa no máximo **40 % de um núcleo**, e a
taxa sobe quando o quadro fica barato (a ordem do dono):

| custo da pintura | período | taxa | CPU da pintura |
|---|---|---|---|
| 11,6 ms (hoje) | 29,0 ms | 34 Hz | **40 %** (vivo: 93 %) |
| 4,0 ms | 10,0 ms | 100 Hz | 40 % |
| 2,0 ms (com a cache da lane de pintura) | 5,0 ms | 200 Hz | 40 % |

Exercitado sobre a função REAL extraída por `ast` (cinco casos, incluindo `cost=0` e um pedido de
0,5 s que não pode ser encurtado), e sobre o **laço real** com o custo real (`caption-tick-thread`
A10: fração de núcleo 0,27 com o orçamento a 0,40). A linha do log passou a dizer
`CAPTION_FRAME_LIMIT want_hz=240 paint_ms=11.60 budget=0.40 rate_hz=34`.

## 4. As outras duas pernas, medidas no mesmo minuto (lanes despachadas)

| perna | evidência | onde | quem |
|---|---|---|---|
| pintura caríssima por quadro | 11,6 ms p95 de `_premultiplied_bitmap`; `THREAD_CPU top=sotto-caption-paint:10%` | `app/webview/overlay_paint.py:654`, `:733-739` (`GraphicsPath.AddString` por linha por quadro) | lane `PaintCostNuclear` |
| 1,0-1,4 s de bloqueio na leitura | `EXTERNAL_CAPTIONS_READ_MS ms=1281.0 phases={'cdp':15.0,'vid':1281.0}` e `YOUTUBE_TARGET_SLOW ms=1015..1375` | `app/webview/youtube_cdp_source.py:1188 target_video_id` → `list_targets(port)` dentro do laço a 19 Hz | lane `CdpTargetAsync` |

## 5. O PORTÃO que faltava (a razão de isto ter chegado ao dono e não a mim)

Os dois instrumentos existiam e **nenhum passo da bateria os chamava**:
`_main/shell-thread-cpu.py` tinha `--neg-arm` e zero chamadores; `THREAD_CPU` era lido à mão.
Novo: **`_main/shell-thread-budget-oracle.py`**

- julga a shell VIVA: total ≤ **25 %** de um núcleo, um fio ≤ **15 %**, o fio mais quente tem de ter
  **nome**, e um ratchet de **+20 %** sobre `_main/shell-thread-budget-baseline.json`;
- sem shell viva imprime `VERDICT: SKIPPED` — um passo saltado nunca é um portão que passou;
- `--neg-arm` mede o **juiz**, sem abrir janela: 6/6 (M0 controlo positivo + total acima do tecto +
  fio acima do tecto + fio sem nome + crescimento sobre baseline + leitura ausente nunca verde).

**Medido agora, na instância dele: `VERDICT: FAIL`** — que é o veredicto certo para o estado atual e
o que prova que o portão fala. O baseline é escrito depois do primeiro arranque dele com esta cura
(`--update`), e a partir daí é o ratchet que recusa o regresso.

## 6. O QUE NÃO ESTÁ MEDIDO

- **A prova no processo dele.** A instância viva (pid 42572, arrancada 04:01:44) corre código
  ANTERIOR a esta cura — medido, não suposto: `live-code-freshness-oracle --strict` diz `STALE` e
  `git show 7ec728d^` prova que ela não tem `_limit_by_paint` nem `FRAME_S = 1/240` —, e detém o
  mutex `Local\SottoShell`. Largar outra aborta em `SINGLE_INSTANCE` e matar a dele está proibido.
  A prova é o **primeiro arranque dele**: esperado `sotto-caption-tick` ≤ 40 % sustentado,
  `CAPTION_FRAME_LIMIT paint_ms=11.6 budget=0.40 rate_hz≈34`, subindo para ≈200 Hz quando a cache
  da lane de pintura entrar.
- **A atribuição por fio do `watcher`** (`profile`) — indisponível neste processo; os números por
  fio deste recibo vêm do instrumento da casa.
- **Os 24 episódios da DM** não foram correlacionados um a um com janelas do log; a correlação
  feita é de estado (o fio a 93 % no instante da medição), não de série temporal.

## 7. Tecto declarado (a DM pede um número)

| recurso | tecto | como se prova |
|---|---|---|
| pintura da legenda | **40 %** de um núcleo (`CAPTION_FRAME_BUDGET`) | `CAPTION_FRAME_LIMIT budget=0.40` no log, e o portão acima |
| shell inteira | **25 %** de um núcleo (total) | `shell-thread-budget-oracle.py` |
| um único fio | **15 %** de um núcleo | idem |
| trabalho pesado de qualquer lane | `python -m watcher run --cpu 40 -- <cmd>` | o job object do watcher |

## 8. A fratura que este recibo fecha

O dono já reclamou de stutter 149 vezes em 14 dias (contadas nos transcripts em
`H:/pi-agent/sessions/`), e o padrão é o mesmo: **um instrumento existe, ninguém o lê, e a primeira
medição é a queixa dele**. A regra que fica (e a primeira frase do recibo): um culpado de stutter
só conta como arrumado com **pid + fio + linha** e o número antes/depois — três dos quatro são
exigíveis sem a tela dele; o quarto é o primeiro arranque.
