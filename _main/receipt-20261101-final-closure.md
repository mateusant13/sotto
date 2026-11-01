# Recibo — fecho do goal de 2026-11-01: a bateria verde, os falsificadores e o que fica por provar

Data: 2026-11-01, sessão do dono. HEAD no fim deste recibo: `b6c9999` (os commits
seguintes citam-se a si próprios).

Regra deste documento, a mesma dos anteriores: **`reported`/`fixed` nunca se
apresentam como `verified`**, e um passo em `SKIPPED` **não** é um portão que
passou. O que está abaixo leva o comando ao lado.

## 1. O que a bateria diz hoje, com o código do processo

```
SOTTO_BATTERY_HEAVY=1 cmd /c "_main\_audit-verify-all.cmd"
steps=183 gate=111 control=9 skipped=2 expect-red=61 missing=0 cached=113 failed=0
failed: -none-
exit-code: 0
BATTERY-VERDICT: GREEN WITH 2 SKIPPED
```

Um único `steps=` no registo (`grep -c '^steps=' = 1`), que é o que impede ler o
`rc` de um passo como se fosse o veredicto.

**Os dois saltados, e por que é honesto:**

| passo | razão medida | substituto que correu |
|---|---|---|
| `paint-live-show` | `nenhum Alt+C nesta sessão ainda` — o censo lê a instância VIVA do dono e ele não pressionou | `youtube-paint-first` + `red-as-expected-youtube-paint-first` (GREEN/RED-como-esperado), e o censo do `paint-first` que fechou a P3 |
| `hotkey-delivery` | `SKIP: held by the running Sotto shell` — `RegisterHotKey(Alt+C)` é global e a instância dele está viva com o hotkey tomado | `altc-first-caption`, `altc-gesture` e o falsificador do spam (abaixo) |

Nenhum dos dois pode ser fechado sem parar a app dele. Não a parei: ele está a
captar (`BRIDGE_STATUS_HELD state=capture-started`, log a crescer às 15:30).

## 2. O que mudou para a bateria deixar de mentir

### 2.1 `strip-surface-runtime`: o censo mede o ECRA, não o bit

Antes: `verdict RED` por **uma** asserção — `B 0 visible samples at a 100 ms
census`. A amostra era real e a leitura estava errada:

- **15:01:23.381** — a janela existe ON-SCREEN em `(1528,12)`;
- **15:01:23.387**, 6 ms depois — a própria shell escreve
  `PANEL_VISIBILITY_AT_STARTUP visible=false`.

É a "startup dance" que o WinForms faz nascer visível e a shell esconde. E a cura
do primeiro frame **mapeia** a janela fora da união dos monitores para aquecer, o
que um censo que conta `WS_VISIBLE` publica como violação da lei do arranque
escondido. O censo passa a classificar `on_screen` pela união dos monitores
(`SM_XVIRTUALSCREEN`…) e a contar só depois de a shell DECLARAR a janela escondida;
as amostras anteriores ficam **registadas** (`census_offscreen_samples`), nunca
apagadas.

Depois: `verdict GREEN`, 26 asserções, 0 falhas.

### 2.2 `strip-surface`: o instrumento ganhou o controlo que não tinha

26 asserções sem nenhum braço negativo. `--neg-arm` muta a LEITURA em três sítios
e exige três RED pelo **mesmo `judge()`** que publica o veredicto — as asserções
passaram a função pura, porque mutar o `checks` já calculado provaria só a
aritmética do `any()`. Medido: a primeira versão ficou com **2 mutantes
NOT-CAUGHT** (a derivação do censo vivia no braço, fora do `judge`) e passou a
`NEG-ARM cases=3 caught=3` depois de a derivação mudar para dentro do `judge`.

### 2.3 `strip-stats-*`: os dois passos mediam no lugar errado e acusavam a caixa

Antes: `SKIPPED - ... a pagina nunca ficou viva ... a caixa estava demasiado
carregada para medir` (35 s de espera). A razão era **falsa**: os registos dos
braços (40 linhas) têm `SHELL_STARTUP_STAGE stage=pre-lock` seguido de
`Microsoft.Web.WebView2.WinForms.WebView2.<InitCoreWebView2Async>d__25.MoveNext()`
— a pane larga a `medium` e o WebView2 não inicializa aí.

`_main/_high_relaunch.py` põe num sítio só o que `_strip-surface-probe.py` já
sabia (fonte `high` por `launch-as-token.py`, descoberta retentada, `SYNCHRONIZE|
QUERY` no handle do filho, o pai publica o rc do filho e não mede outra vez), e
`load_skip_reason` passa a NOMEAR a falha do WebView2 quando ela está na leitura.
A palavra "carregada" fica só para o caso de página viva e lenta, provado nos dois
sentidos: a leitura real do defeito nomeia a falha, e uma leitura sem falha
continua a dizer carga.

Um segundo defeito do mesmo passo: o filho criado por `CreateProcessAsUser` **não
herda o `stdout`** que a bateria redireccionou, e o passo publicava
`failed: ...=0` sem uma palavra do veredicto. O canal passou a ficheiro declarado
(`--child-out=`), que o pai imprime e apaga.

Depois:

```
STRIP-STATS VERDICT: GREEN - ... level=live bars=10 emits.stats=157 pushes=1 control_level=none ready_s(fed=0.906,unfed=1.082) deadline=30s
STRIP-LOG CONTROL PASS ratio=390.5x per_sample_lines=474 aggregated_lines=1 delivered=475 ready_s(per=1.017,agg=0.922) deadline=30s
```

Ambos medidos por filho `HIGH` (fonte `pid=14040`), rc=0.

## 3. Falsificadores independentes (P7 #30)

Os três claims da cabeça. Instrumento **diferente** do autor em todos, controlo
negativo da mesma forma em todos, um veredicto por recibo.

| claim | recibo | veredicto | o que o atacou |
|---|---|---|---|
| o painel pinta antes de aparecer | `_main/receipt-falsify-paint-first.md` | `NOT-REFUTED`, com a cláusula de que o instrumento dele não fecha dito como tal | compositor do WebView2 por CDP (nunca `PrintWindow`), 230 frames |
| Alt apertado + `c` spammado alterna | `_main/_falsify/hotkey-spam-alternation.md` | `NOT-REFUTED` | cadeia de produção real (`HotkeyThread` → `WM_HOTKEY` → … → `hide_panel`), 22 braços |
| o parakeet drena o áudio em atraso | `_main/_falsify/parakeet-drain.md` | `NOT-REFUTED` | conjuntos de entrada/saída reconstruídos por contagem própria, 5 braços controlados |

Números que importam, com o que os produziu:

- **spam**: `prod-n10 ... flips=10/10 posted=10 delivered=10 gas_reads=0`,
  `visible_sequence=['show','hide',...]`; expectativa invertida → RED; janela de
  toques mutada → RED (`flips=2/10`); e a **árvore pré-cura de verdade**
  (`git archive 38ab1d6`) dá `['show','show','hide',...]` — dois `show` seguidos,
  que é exactamente o defeito que a frase do dono existe para matar.
- **dreno**: `ARM 1` (shed → carga liberta) `reduxAudioIn=543 reduxAudioOut=543
  reduxAudioSpooled=0 reduxAudioDropped=0`, `left_s=0.0`, 19 linhas do parakeet a
  cobrir 54,30 s sem lacuna; `ARM 5` prova o "recarrega sozinho" (`loads=1` →
  `RELEASED` → `loads=2`); `ARM 2` (a carga NUNCA liberta) fica RED com 16,9 s
  ainda presos; registos forjados de três maneiras → RED nas três.

## 4. O que NÃO está provado — dito, não escondido

1. **Nada disto é o teclado do dono.** O driver posta `WM_HOTKEY` e o "Alt+C"
   dele foi medido noutros instrumentos; o input sintético não é evidência sobre a
   app (`docs/hotkey-gestos.md`).
2. **A janela é falsa no braço do spam**, logo mede-se a CADEIA DE DECISÃO, não
   os píxeis. Um mapa recusado pelo Windows mudaria a série; medir isso pede uma
   janela real, que a lei `SOTTO_NEVER_ON_OWNER_SCREEN` proíbe a uma lane.
3. **O texto do parakeet nunca aparece atribuído no transcrito.** Contagem minha,
   corrigindo o campo do recibo do falsificador (que procurou `producer=redux`,
   que o store não escreve): `route=final` **1571**, `route=provisional-draft`
   **11**, `src=worker-stamped` **12**, rota de lote **0**. O dreno está provado; a
   entrega ao histórico NÃO está. O portão que o falsificador propôs é RED por
   construção e não serve; o correcto conta `route=`/`src=` e exige uma linha de
   lote — e a decisão de qual escritor cria essa rota fica aberta.
4. **`paint-live-show` e `hotkey-delivery` saltados** (ver §1). Nenhum é verde.

## 5. Pinos re-medidos

- `_main/_audit-verify-all.cmd`: **154856 B, 1999 CRLF / 0 bare LF**,
  sha256 `F4DC0090E395CDA88589EC0D357573FF28A547AF805E6C590EBB544100EBDA8B`
  (`python _main/agents-md-pins-oracle.py` → `PASS`, e o `--neg-arm` → `CONTROL PASS`).
- `run.cmd --help`: **7281 B, 112 linhas, 112 CRLF / 0 bare**, rc 0, sha256
  `0F1E61994DFBAA170A52D5131F5CB19DDBB388620B3F64458D13BD55066CFBA1`.

## 6. Disco

| o quê | antes | depois |
|---|---|---|
| worktrees do goal (`goal-anim`, `goal-battery`, `goal-green`, `goal-noblank`) | 121 + 133 + 141 + 120 MB | removidas (todas merged; os 11 mockups não commitados da `goal-anim` foram preservados e commitados: 787 KB) |
| scratch do falsificador do dreno | 45 MB | apagado; instrumento preservado em `_main/_falsify/drain-driver/` (83 KB) |
| `_py311/` (CPython 3.11 vendido, não rastreado, criado hoje às 06:06 por uma lane já morta) | 14,59 GB em 103 370 ficheiros | **apagado** — nada na árvore o nomeia por caminho (`grep -rln "_py311"` só dá a linha do roadmap, onde já estava declarado "fora do índice"), e os instrumentos do repo correm no `C:\Program Files\Python311`. Um `pip install` recria o que fizer falta. |
| livre agora | — | C 24,3 GB · G 37,5 GB · **H 31,5 GB** · I 59,5 GB |

**`_moved/aireplay` = 2,6 GB** de um repo VIZINHO (`aireplay`, + `_moved/aireplay-wt`
31 MB) parqueado dentro do `H:/sotto` sem estar no índice. É o maior desperdício que
sobra, e **não o apaguei**: não é uma árvore deste repo nem deste goal, e apagar o
trabalho de outro projecto não é decisão de lane. Fica nomeado para o dono decidir.

As 16 worktrees que ficam **não são deste goal** (lanes pré-existentes de outras
sessões); metade tem árvore suja e não se tocam sem o dono.
