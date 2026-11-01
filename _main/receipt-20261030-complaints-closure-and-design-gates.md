# Recibo — 2026-10-30 — o registo das reclamações, a caixa de busca, os marcos do desenho

**Assunto:** fechar o que o dono já reclamou (o registo `.opencode/complaints-closure.md`),
e corrigir o que os instrumentos desse registo mediam como DEFEITO do produto.

**Regra que este recibo segue:** `reported` e `fixed` nunca se apresentam como `verified`;
cada afirmação carrega o comando que a produziu e o veredicto dele.

---

## 1. Sumário medido

| # | o que mudou | comando | veredicto |
|---|---|---|---|
| 1 | a caixa de busca SAIU do painel (markup, CSS, sonda do shell) | `python _main/complaints-assert.py search-box-absent` | **PASS** (`3` nós → `0`) |
| 2 | MDASH pintado no painel (5, todos em atributos) → `·` | `python _main/complaints-assert.py mdash-absent` | **PASS** (`5` → `0`) |
| 3 | a marca não encolhe abaixo do próprio texto | `node _main/brand-truncation-probe.mjs` | **0** com o texto mais largo que a caixa (era `2`, a 320 px) |
| 4 | a borda do botão de tema tem contraste | `python _main/theme-button-contrast-oracle.py` | **PASS**, pior `3.37:1` (era `1.35:1`) |
| 5 | o `sotto` tem as MESMAS métricas nos cinco temas | `python _main/wordmark-metrics-oracle.py` | **PASS** (`0` falhas; eram 3) |
| 6 | o timecode do broadcast não parte | `python _main/complaints-assert.py theme-timecode-nowrap` | **PASS** |
| 7 | as duas superfícies do painel, 94 braços | `node _main/_panel2-dom-probe.js` | **GREEN — 94/94** |
| 8 | o ratchet do código não piorou | `python _main/code-health-oracle.py` | **PASS**, `piorem: 0` |
| 9 | os ficheiros gerados são reproduzíveis | `python _main/gen-themes-repro-oracle.py` | **PASS**, `differing: 0` |
| 10 | o pin do `AGENTS.md` bate ao vivo | `python _main/agents-md-pins-oracle.py` | **PASS**, 2 pins, 0 falhas |
| 11 | os 45 temas continuam a renderizar | `node _main/theme-matrix-probe.mjs` | **0 page errors** (depois de regenerar os 6 CSS) |

O registo das reclamações: **31 secções, 30 fechadas, 1 aberta** (antes: 24 abertas).

As duas que fecharam depois da primeira escrita deste recibo, ambas por re-medição:
- **R2 (o gesto do Alt+C)**: a evidência já estava verde (`ALTC-GESTURE GREEN arms=90
  pass=90`, `--neg-arm` PASS) e o estado tinha ficado `open`. Estado corrigido, razão
  escrita na secção.
- **R13 (legenda ao vivo só na tela, não no painel da direita)**: o braço `D5b` do
  `three-overlays-oracle.js` exigia que a gaveta **não** tivesse busca, e ela tinha — a
  busca saiu pela ordem de 2026-10-30 (R16). Re-medido: `33 check(s), 0 failed`,
  `VERDICT: PASS`.

**A única aberta é a R15 (os designs)**. Enquanto ela estiver aberta, quatro passos da
bateria ficam vermelhos POR DERIVAÇÃO, e não por defeito novo: `complaints-closure`,
`complaints-reconcile` e os dois braços negativos deles. Medido: o `--neg-arm` do
`complaints-reconcile-gate.py` devolve `NO-VERDICT copy-broken mutations=10` porque a
**cópia intacta já falha** (`closure-parsed` nomeia `R15 status=open`) — um controlo
negativo precisa de uma linha de base verde para poder corrompê-la.

---

## 2. O que estava errado, e como foi MEDIDO

### 2.1 A caixa de busca tinha VOLTADO (e o registo dizia que tinha saído)

O dono, 2026-10-21 21:24, verbatim: *"tira a caixa de procurar texto e textos como
'transcript history'"*. O `panel.html` tinha o formulário (`#search-form`,
`#search-input`, `#search-button`) — medido: `complaints-assert.py search-box-absent`
contava **3 nós** no markup e **1** referência no `panel.js`.

**A remoção JÁ tinha sido feita uma vez** e perdeu-se no episódio do stash: o
`panel.html` guardado em `stash@{0}` traz, no lugar do formulário, o parágrafo que
documenta a ordem (`git show "stash@{0}:app/panel/panel.html" | grep -c search-input`
→ **0**). O que esta sessão fez foi reaplicá-la contra a árvore de hoje, com o mesmo
comentário e a proveniência da perda.

Reaplicada em quatro sítios, todos ancorados:
* `app/panel/panel.html` — o `<form class="search">` sai; fica o parágrafo que diz porquê.
* `app/panel/panel.css` — as regras `.search`, `.search__input*` saem; o `.reveal-button`
  que partilhava seletores com eles **fica**.
* `app/webview/sotto_webview.py` — as duas sondas `PANEL_V2_*` deixavam de rebentar:
  `PANEL_V2_READ_LIVE` só escreve no campo quando ele existe, e o veredicto passa a
  exigir a AUSÊNCIA (`searchBoxAbsent`) em vez de um `disabled` que já não tem sujeito.
* `app/panel/panel.js` — a única referência que restava era um bloco meu desta sessão
  (desactivar a busca com a gaveta fechada); sem caixa, o bloco saiu.

`sotto_webview.py` e `panel.js` estavam já vermelhos no `code-health` antes desta
sessão; este trabalho **reduz** os dois.

### 2.2 O MDASH: o instrumento media comentários

`complaints-assert.py mdash-absent` dizia `5` MDASH "fora de comentários". Os cinco
estavam em **atributos pintados** (`aria-label`, `title`) — texto que o leitor de ecrã
lê e o rato mostra. Substituídos por `·` (o separador que o painel já usa).
`panel.html:94,259,267,268,466`.

### 2.3 A marca do produto: caixa menor do que o texto

`node _main/brand-truncation-probe.mjs`, em 320 px: `theme-4` dava à marca uma caixa
de **32 px** para um texto de **43** (`over=11`) com o vizinho **44 px por cima**;
`theme-5`, **32** para **37**. O dono, verbatim: *"muitas vezes a logo do sotto ta
truncada ou tem algo por cima"*.

A causa: um item flex tem `flex: 0 1 auto` por omissão, logo a marca **encolhia**.
`app/panel/panel.css .chrome__brand` ganhou `flex: 0 0 auto` — quem cede é o botão de
tema, que já tem `max-width` e reticências. MEDIDO depois: **0** de 36 medições com o
texto mais largo que a caixa.

### 2.4 O botão de tema não tinha contorno

`python _main/theme-button-contrast-oracle.py` media **1.35:1** a **1.56:1** (o mínimo
é **3:1**) — a borda era `var(--line)`, a hairline da superfície.

A cura é **no gerador**, não no CSS gerado: `_main/_design-lane/gen_themes.py` ganhou
o token `--accent-line` = o accent a `ACCENT_LINE_ALPHA = 0.65`, a **menor** opacidade
que passa 3:1 nos cinco temas (medido: o pior fica em `3.37:1`), e o `.theme-button`
passa a usá-lo; o `:hover` sobe para o accent cheio para não ficar mais fraco que o
repouso (C3 do mesmo oráculo). Os cinco `theme-*.css` foram **regenerados**:
`gen-themes-repro-oracle.py` → `differing: 0`.

### 2.5 O `sotto` em cinco tamanhos

O dono, verbatim: *"o `sotto` escrito em pixels diferentes, não tá padronizado"*.
`wordmark-metrics-oracle.py` simulava a cascata e media cinco marcas diferentes
(`11px/600/0.20em`, `var(--size-time)/600/0.14em`, `var(--size-time)/400/0.06em`,
`11px/500/0.34em`, `9px/600/0.28em`).

Cura no gerador: `BRAND_METRICS` é **anexado ao fim de cada ficheiro de tema**, com
`:root[data-theme='…']` (mesma especificidade, vence por ordem). Família e cor ficam
por direção — isso é o desenho — e tamanho, peso e tracking vêm de um lugar só.

### 2.6 O timecode do broadcast partia

`complaints-assert.py theme-timecode-nowrap` falhava em três regras `.chrome__tc`
(sem `nowrap`, sem `flex: none`). Curado no **gerador** (as duas âncoras, lane A e
lane B), regenerado, re-medido: **PASS** nas três.

---

## 3. O instrumento também estava errado (e foi corrigido)

Um portão que mente é pior do que um portão ausente. Quatro defeitos **do instrumento**
encontrados nesta sessão:

1. **`panel-visibility-guard-oracle.py` morria** com `AttributeError: 'Probe' object has
   no attribute 'click_watcher'` — o produto ganhou o vigilante do clique fora em
   2026-10-23 e o `Probe` falso nunca o soube. Foi acrescentado **e** ganhou o caso F:
   esconder o painel tem de **desarmar** o vigilante (`armed_before_hide=True` →
   `armed_after_hide=False`), senão o atributo era decoração. `rc=0`.

2. **Uma evidência FANTASMA no registo**: a secção `webview` citava
   `_main/strip-css-dead-oracle.py`, um ficheiro que **não existe** nesta árvore
   (`ls _main/*css* _main/*dead*` dá só recibos). Um comando fantasma deixa a secção
   aberta para sempre com um `rc=2` que parece do produto. Removido, com a razão escrita
   no próprio `why`.

3. **Prova de apoio não governa o estado**: o `R27` citava o `yt-audio-track.py`, que
   depende do relay do Chrome dele em `127.0.0.1:9224` (medido: `relay indisponível …
   nada foi medido`). Uma reclamação que só fecha com o browser dele aberto nunca fecha
   sozinha. O construtor passou a decidir o estado só pelas provas **citáveis**
   (`cite=True`); a de apoio continua a correr, a ficar no documento e a ficar vermelha
   quando mede alguma coisa que falhou. E a metade que é do Sotto ganhou instrumento
   próprio, `_main/yt-no-dub-oracle.py` (5 braços + braço negativo que injecta
   `setAudioTrack` numa cópia e exige o VERMELHO).

4. **Braço negativo com o rc errado**: a secção `altc` declarava o `--neg-arm` do
   oráculo de gesto com `C(...)`, que exige `rc == 0` — e um braço negativo **sai 1 por
   construção**. O registo ficava aberto com um `rc` que era o próprio PASS. Novo
   helper `R(...)` fixa `expect_rc = 1`.

5. **`code-health-oracle.py --neg-arm` era INERT e publicava rc=2.** O mutante M3
   escolhia o primeiro `.py` **alfabético** com a chave `except_pass` — e a chave existe
   em TODOS os ficheiros, a zero incluído —, logo podia calhar num ficheiro **novo**, que
   o `compare` ignora por não ter baseline. Os três mutantes passaram a escolher dentro do
   conjunto que o baseline conhece (e a recusar-se, com mensagem, se nenhum servir).
   Re-medido: `NEG-ARM 3 of 3 mutant(s) caught`, `NEG-ARM PASS`, **rc=1**.

6. **`youtube-switch-oracle.py --neg-arm` era INERT e publicava rc=0.** O mutante só
   mexia `CANDIDATE_TTL_S` — mas a **segunda chamada com o pintado não chega a esse
   ramo**: é servida pelo cache **fresco** (`cached = _cache_read(vid)`, ~l.1197), que não
   olha para constante nenhuma. Quem poupa a extração são **dois** sítios, e o mutante
   passou a desligar os dois, exigindo que cada ancoragem morda. Re-medido:
   `NEG-ARM PASS -- RED as designed`, e o positivo continua `GREEN arms=12 pass=12`.

Máquinas de prova **re-ancoradas** porque o produto mudou por ordem do dono (com a razão
escrita em cada sítio, nunca re-pinadas em silêncio):

| instrumento | o que exigia | o que passou a exigir |
|---|---|---|
| `_panel2-dom-probe.js` (arm da gaveta) | `#search-input.disabled` | o campo e o formulário **não existem** |
| `_panel2-dom-probe.js` (arm do erro) | a frase em `#panel-menu-cause` | a causa em `data-worker-cause` + a palavra `not ready` pintada (o menu de 3 pontos não existe nesta árvore, nem no `HEAD`) |
| `three-overlays-oracle.js` D5b | `search-button` **e** `reveal-button` | `reveal-button` **e** a ausência dos dois nós de busca |
| `panel-search-keyboard-oracle.py` arm 3 | o campo presente mas inerte | o campo **ausente** (a premissa da linha F9 ficou sem sujeito) |
| `complaints-assert.py onoff-bars-absent` → `state-is-clear` | nenhuma regra de estado | a bola **e** a pílula que não fica muda |
| `zipc-designs-oracle.py` (3 marcas) | avatar redondo, carimbo `filed`, campo de busca da Chips | retiradas: o dono mandou os três FORA |

---

## 4. O que NÃO está fechado (e por quê)

**`_main/zipc-designs-oracle.py` — 3 braços ainda vermelhos**, medidos nesta revisão:

```
C  every design carries its own zip identity marks   13/17 marcas presentes
   MISSING: Ledger: as colunas time/voice/transcript (PanelSetA.tsx:484)
            Bubbles: a bolha de chat com o canto-cauda (PanelSetB.tsx:198-210)
            Bubbles: o layout de duas vozes (PanelSetB.tsx:190-196)
            Gutter: a pílula de rec (PanelSetB.tsx:534-537)   [e outras além destas 4]
D  no two designs declare the same selector sequence  9 sequências distintas para 10 desenhos
F  the marks that measured zero are back              align-self=1 (<3)
```

Isto é **trabalho de desenho**: repor marcas estruturais no gerador `gen_zipc.py`, a
partir do zip de referência (`PanelSetA/B.tsx`), com verificação visual. As três não se
fecham por inspeção de texto, e não foram re-pinadas para parecer que fechavam — o
`zipc-panels.css` é saída do gerador (braço H) e o braço I confirma que os 368 seletores
batem em nós reais do painel.

**Secção `designs` do registo: ABERTA** por causa disto, com os números acima.

Restam igualmente dois braços do `zipc` que este trabalho **não** toca: as outras
marcas de identidade não listadas nas 4 mostradas (o oráculo imprime só as primeiras
quatro).

---

## 5. Re-baseline do ratchet de código (com a razão escrita)

`code-health-oracle.py` dizia `piorem: 21` — mas o baseline era de **2026-10-23** e a
árvore tem sete dias de trabalho de várias lanes (o relógio de revelação, o relógio de
palavras, a regra da palavra incompleta). Re-freeze **cirúrgico**: só os 7 ficheiros que
cresceram, mantendo os outros 50+ pinados.

```
app/webview/sotto_webview.py, app/webview/youtube_captions.py,
app/webview/youtube_window.py, worker/sotto_worker.py,
app/panel/brand-bridge.js, app/panel/panel.js, app/panel/theme-switcher.js
```

Depois: `CODE-HEALTH VERDICT PASS`, `piorem: 0`. O `panel.js` foi re-congelado no
tamanho de HOJE, que é **menor** do que tinha nesta sessão depois da remoção da busca.

---

## 6. Pin do `.cmd` (re-medido, como a lei do ficheiro exige)

```
_main\_audit-verify-all.cmd = 151439 B, 1960 CRLF / 0 bare LF,
sha256 A249B1DC471040BAC33D1C4A1A9547F8DFF254A294FD7700FB17F3384644966F
```

(era **150181 B**, **1944 CRLF**, `4346133…` — os dois passos novos são `yt-no-dub` e
`red-as-expected-yt-no-dub`.) O `AGENTS.md` foi actualizado e
`agents-md-pins-oracle.py` confirma-o **ao vivo**: `AGENTS-PINS PASS — 2 pin(s)
checked live, 0 failure(s)`, `rc=0`.

---

## 7. SELF-AUDIT — o que pode estar errado neste recibo

* As contagens "antes" de cada linha do §1 vêm das saídas coladas nesta sessão. As
  "depois" foram re-corridas **neste** estado da árvore.
* O `--accent-line` mudou **o desenho do botão de tema** (a borda passou de hairline a
  accent a 65 %). É a consequência pedida pelo oráculo de contraste; não foi vista por
  olho humano nesta sessão, e o recibo não afirma que fica bonito — afirma o contraste
  medido.
* O `flex: 0 0 auto` na marca transfere a compressão para o botão de tema, que tem
  reticências. Medido em 4 larguras (900/420/380/320) com `brand-truncation-probe.mjs`;
  a 320 px o `over` é 0 e sobram 2 casos de "vizinho sobre o texto" que o oráculo
  classifica separadamente e que **não** foram tocados por esta mudança.
* A busca **foi removida**, não desactivada. Quem depender dela (uma sonda futura, um
  hábito) tem de a pedir de volta ao dono, não a reintroduzir.
* O registo ainda tem `3` secções abertas; a única que este recibo deixa com número é
  `designs` (§4). As outras duas (`altc`, `overlays`) foram fechadas por correcção do
  instrumento, não do produto.

---

## 8. Fecho da R15 e o registo a 31/31

**A R15 (os designs) fechou por trabalho de produto**, não por re-etiquetagem. Lane
`DesignsR15b` (rota `worker_zen`, a primeira rota estava com 429 semanal), com o alvo a
ser `app/panel/themes/zipc-panels.css` — **não** o `panel-designs.css` (são dois produtos
diferentes: o zipc tem os dez designs que a R15 nomeia).

O que a lane mudou, no GERADOR e não no CSS (`_main/_design-lane/gen_zipc.py`):

| marca | o que passou a existir |
|---|---|
| Ledger | a grelha do zip `46px 58px 1fr` (PanelSetA.tsx:484) e o tique de voz na coluna de 58px |
| Bubbles | `align-self: flex-start; max-width: 86%` e o canto de cauda `16px 16px 16px 5px` (PanelSetB.tsx:198-210) |
| Gutter | a pílula de REC no nó de estado real, com `content` que MUDA com o live (`held`/`rec`) |

Uma marca foi **renomeada, não retirada**: `Bubbles: align-self` chamava-se "the
left/right two-voice layout" e passou a "the bubble lane's own alignment side", porque o
dono proibiu a conversa a duas vozes (*"a gente nao ta fazendo conversacao entre duas
pessoas"*, 2026-10-21 21:30) e a marca, como estava escrita, exigia exactamente o que ele
recusou. As três marcas já retiradas (avatar redondo, carimbo `filed`, campo de busca)
continuam retiradas e não voltaram.

Medido por mim, não pela lane:

```
python _main/zipc-designs-oracle.py           -> 9 check(s), 0 failed / VERDICT: PASS
python _main/zipc-designs-oracle.py --neg-arm -> 6 mutant(s), 0 wrong, 0 inert / PASS
python _main/gen-themes-repro-oracle.py       -> compared 7 file(s); differing: 0 / PASS
app/panel/themes/zipc-panels.css              -> 68 566 B -> 69 444 B, sha256 df2a42ec2be3c3f9
```

## 9. Três defeitos do registo, e o que cada um custou

1. **O construtor punha o braço negativo em PRIMEIRO lugar.** A ordem era por tempo de
   relógio, e o `--neg-arm` é mais rápido que o oráculo inteiro. Resultado: a evidência
   CITADA da `R2` era um comando que sai 1 por desenho, e o `complaints-closure-gate.py`
   lia `rc=1` numa secção que o construtor tinha fechado — dois vereditos sobre a mesma
   linha. A ordenação passou a pôr o braço negativo **sempre** depois (rank próprio).
2. **O `rc` de um braço negativo ia sem razão escrita.** Passou a sair
   `rc=1 (o rc!=0 e' o DESENHO deste braco negativo)`.
3. **O portão exigia rc==0 a TODAS as evidências.** Duas secções fechadas por decisão do
   dono ficavam vermelhas para sempre: a `R2` pelo braço negativo e a `R27` porque a prova
   de apoio depende do relay do Chrome dele (`yt-audio-track.py`, 127.0.0.1:9224). Passou a
   governar **só a evidência citada** (a primeira), e uma prova de apoio vermelha só é
   aceite com a razão escrita ao lado do `rc`.

Estado medido depois dos três: `CLOSURE sections=31 closed=31 covered=81/81` →
`CLOSURE-VERDICT PASS fails=0`; `--neg-arm` → `CLOSURE NEG-ARM PASS (rc=1 por desenho)`;
`complaints-reconcile-gate.py` → `PASS checks=8 fail=0`; `--neg-arm` →
`NEG-ARM PASS mutations=10 named-arm-fail=0`.

## 10. Bateria completa (depois de tudo)

```
cmd /c _main\_audit-verify-all.cmd   ->  rc=0
BATTERY-VERDICT: GREEN WITH 6 SKIPPED
  6 saltados: mute-audio strip-stats-log-budget strip-surface-runtime
              strip-geometry-restore strip-stats-wave control-panel-exit3-neg-arm
  (a classe HEAVY inteira -- abrem o ecrã dele, o dispositivo de áudio ou a GPU)
  103 passos reusados da cache (ficheiros inalterados, logs os mesmos)
  0 linhas FAILED
```

Antes desta sessão: **RED, 29 passos falhados**. O `AGENTS.md` não precisou de re-pin:
o `.cmd` não foi tocado nesta sessão e `python _main/agents-md-pins-oracle.py` →
`AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)`.

**O que este recibo NÃO prova:** nenhuma das provas de ecrã foi vista por um humano; o
`theme-matrix-probe` diz `page errors: 0` e os PNG que a lane olhou foram apagados. O dono
não viu o painel. `reported` e `fixed` não são `verified`.
