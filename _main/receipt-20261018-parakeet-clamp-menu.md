# Recibo — 2026-10-18, tarde

Onde cada afirmação vem de, e o que **não** foi medido.

Estado medido no fim: shell viva pid 37816, sem worker, `SOTTO_REDUX_LIVE=1`.
Bateria de portões: **0 falhas** em 16 oráculos Python + 5 Node + 3 braços
negativos. O único RED é `three-overlays-oracle.js` A5, **pré-existente** e
provado por `_main/a5-provenance.py` (mesma falha em `git show HEAD:`).

---

## 0. O BOTÃO DE TAMANHO ERA DECORATIVO — a maior descoberta da sessão

O dono falou em *"tamanho de letra inconsistente"*. O botão único já estava feito
ontem. **Não funcionava.**

**O inventário que o revelou** (`_main/caption-scale-coverage.js`, 363
declarações de `font-size` em 17 folhas):

| token | declarado | consumido |
|---|---|---|
| `--caption-size` | **1** (`panel.css:95`) | **1** (`panel.css:1280`) |
| `--size-caption` | **45** (8 folhas de tema) | **91** |

Duas fontes de verdade para o mesmo conceito. E o segundo número que mata:
**91 usos de `--size-caption`, ZERO multiplicados por `--caption-scale`**.

A cascata: `panel.css:1280` faz `calc(var(--caption-size) * var(--caption-scale))`,
mas os temas escrevem `.caption__text { font-size: var(--size-caption) }` com
especificidade (0,1,1) e chegam depois. **O botão escrevia a escala num sítio que
ninguém lia.**

**Medido no navegador** (`_main/caption-dial-effect.py`, `getComputedStyle` com a
escala forçada a 0,8 / 1,0 / 1,5 / 2,0), **antes**:

```
theme-1   16.5  16.5  16.5  16.5   ×1.00  *** NÃO MUDA ***
theme-2   10.5  10.5  10.5  10.5   ×1.00  *** NÃO MUDA ***
theme-3   14    14    14    14     ×1.00  *** NÃO MUDA ***
theme-4   15    15    15    15     ×1.00  *** NÃO MUDA ***
theme-5   13.5  13.5  13.5  13.5   ×1.00  *** NÃO MUDA ***
cine-cafe 12    15    22.5  30     ×2.50  move
```

Cinco de oito, incluindo o `theme-1` — que é o `data-theme` que o `panel.html`
traz e o *fallback* do `theme-switcher.js`.

**A cura, nos GERADORES (8 sítios, 5 geradores), nunca à mão:**
`gen_themes.py` ×3, `gen_zipc.py` ×2, `gen_cinematic.py` ×3, `cine_extra_c1.py` ×2,
`cine_extra_c2.py` ×2. O `max(13px, …)` do `cine` passou a
`max(13px * var(--caption-scale), …)`: **o piso também encolhe**, senão o dono
não conseguia descer abaixo de 13 px e havia um segundo mostrador invisível a
lutar contra o visível.

O `gen_themes.py` **recusou o build** a meio — *"consumes --caption-scale and
declares it nowhere"* — e estava certo. `--caption-scale` entrou na tabela
`CONSUMED_NOT_OWNED` com o valor `1`, que move zero pixels porque o `panel.js` o
escreve em estilo **inline** e isso ganha a `:root[data-theme]`.

**Depois** — as DUAS linhas que o dono vê ao mesmo tempo, a que se está a formar e
a já fechada:

```
theme-1    FORMING 27.8 -> 69.6  ×2.50   SETTLED 13.2 -> 33   ×2.50
theme-2..5                                          SETTLED        ×2.50
cine-cafe / blue-hour / reading-hour                                  ×2.50
```

**A proporção entre as duas mantém-se** (≈2,1:1 em ambos os extremos). O desenho
que diz "a linha fechada é um tamanho abaixo" continua verdadeiro, e agora o
botão move as duas juntas.

**O meu próprio instrumento estava errado primeiro.** A primeira versão lia
`querySelector('.caption__text')`, que devolve a **primeira** legenda do documento
— uma **fechada** — e estava a medir `.caption:not(.caption--provisional)`, que
`--size-closed` escreve cru. Ou seja: reportava "o botão está morto" pela regra
errada, e essa regra estava mesmo morta por outra razão. Passou a ler
`.caption--provisional .caption__text` e a linha fechada separadamente.

**E o buraco no portão anterior:** `font-dial-oracle.js` verifica que o botão
existe, que cicla e que nunca se desliga. Nunca verificou que a letra **muda**.
Um portão que descreve o botão e não o efeito.

### A pergunta que vem a seguir: letra grande corta o painel?

Renderizei as quatro paragens (`_main/dial-extremes-shot.py`). A **2.0**, a
legenda viva fica a 69,55 px e **"ENQUANTO" aparece cortada na margem direita**.

Duas leituras possíveis e uma diferença de produto: ou o texto não quebra e o
`.panel` corta-o (`overflow: hidden`, `panel.css:198`), ou é o clamp de 492 px
a enganar outra vez. **Um PNG não separa as duas.**

A separação é `el.scrollWidth > el.clientWidth`: uma propriedade do elemento e
do seu conteúdo, à prova do clamp — o clamp muda a *largura* da caixa, não muda
se um texto cabe nela. E é a pergunta certa, porque o dono tem as **duas linhas
ao mesmo tempo**: a que se está a formar e a já fechada.

Primeira corrida: `box=638 ... fits` em todos os casos. **Verdadeiro e
irrelevante** — 638 px é o layout de 492. Tive de repetir com a caixa forçada aos
380 do dono antes de dizer alguma coisa.

**Reconciliação com a queixa de ontem.** Ontem o dono mandou partir palavras
(*"Hierarchical / communicatio / n"*) e eu pus `break-word` + `hyphens: auto`.
Hoje, com letra grande, é esse mesmo `break-word` que impede o texto de **sair
da caixa**. A tensão é real e a escolha é: **uma palavra partida ou uma palavra
cortada.** A segunda é pior — metade de um glifo não é legível, e o dono vira-a
para o lado e perde o sentido. A primeira quebra-se com o hífen que o
`hyphens: auto` põe. Mantém-se o `break-word`.

---

**O problema, medido.** `SOTTO_REDUX_LIVE=1` vivia no ambiente do processo
`pythonw` 37816 e nada mais. `HKCU\Environment`, `HKLM\...\Environment` e o
ambiente do processo pai: **todos vazios**. `_child_env` faz
`dict(os.environ)` (`sotto_webview.py:10316`), e `run.cmd` não põe nada — um
duplo-clique amanhã criaria uma shell nova, sem a flag, e o motor pedido pelo
dono não arrancaria.

**A primeira tentativa estava errada e o portão disse-o.** Gravei
`HKCU\Environment\SOTTO_REDUX_LIVE=1` e enviei `WM_SETTINGCHANGE` (a chamada
devolveu `ok=1`). Depois tentei *prová-lo*: uma sonda via
`Shell.Application.ShellExecute` respondeu com `Path=` a apontar para o
**PowerShell**, ou seja, criou o processo no meu contexto e não provava nada
sobre o Explorer. Um `.bat` aberto pelo shell chocou `InvokeVerb` e derrubou o pwsh
(`0xC0000409`); abri-lo mostraria uma janela de consola, que a regra proíbe.
**Conclusão honesta: não há, aqui, instrumento que veja o que o Explorer vai
passar ao próximo duplo-clique.**

**Onde o default foi parar, e porquê não noutro sítio.** Primeiro no
`_child_env` — e `app-target-oracle.py` ARM e foi **RED**:
*"the env is byte-identical to the pre-existing contract: os.environ +
SOTTO_CAPTURE_MODE, nothing else"*. O portão está certo: uma bridge que começa a
acrescentar chaves é como aparece uma segunda tabela. Revertido.

Ficou no **`run.cmd`**, antes do `start`:

```bat
if not defined SOTTO_REDUX_LIVE set "SOTTO_REDUX_LIVE=1"
```

Isto é verificável sem confiar em nada externo, e é o caminho que o dono usa
("Double-click it"). `SOTTO_REDUX_LIVE=0` no ambiente ganha, porque a linha só
fornece valor quando não há nenhum — e "0" é o off explícito do próprio worker
(`redux_live_settings`, `sotto_worker.py:3464-3470`).

**Prova: `_main/redux-live-default-oracle.py`, 9/9 + 8/8, `--neg-arm` 4/4.**
O braço L2 corre um `cmd.exe` **real** sobre a linha real do ficheiro — ler a
linha não prova o que o cmd faz com ela.

**O que NÃO está provado:** que o motor carregue e transcreva. Isso exige
inferência a correr e o dono não está cá. O que está provado é que a flag
**chega** ao worker.

---

## 1. O PARAKETE MORRIA NO PROXIMO run.cmd -- e agora nao

(A seccao segue abaixo do ponto 0; ver o ficheiro na ordem numerada.)

## 2. O CLAMP DE 492 px — e o defeito que ele quase me fez "consertar"

`shot.py` afirmava no seu docstring que o clamp de 492 px *"não se aplica"* ao
`--screenshot`. **Não se aplica.**

Medido: `--headless=new` e `--headless=old` devolvem PNGs **byte-idênticos de
62 570 B**; forçar `html{width:380px}` move o body e o header mas as caixas dos
controlos ficam na geometria de 492; e o contorno por botão/reportou
`header r=478` dentro de um PNG de 380 — que é 492 − 14, o layout de 492
**recortado**.

A leitura óbvia desse número é um transbordo de cabeçalho a corrigir no
produto: Hide, Pausa e o tamanho da legenda 34–98 px fora da janela.

**Não existe.** Perguntado no único sítio com o viewport do dono —
`sotto_webview.py --dump-dom`, a janela WebView2 real, sem clamp:

```
viewport 380x900 · panel_right 380 · cluster [116..366] w=250
theme-button      right=350  past_by=0  onscreen=True
theme-chevron     right=382  past_by=0  onscreen=True
font-scale-button right=414  past_by=0  onscreen=True
tune-button       right=256  past_by=0  onscreen=True
panel-pause-button right=446 past_by=0  onscreen=True
hide-button       right=366  past_by=0  onscreen=True
```

Correções: a frase do docstring do `shot.py` está **retractada e reescrita**; o
`AGENTS.md` ganhou o **ponto 4** na secção "Keeping THIS file true"; e o
`--dump-dom` ganhou uma chave `controls` que imprime `viewport_w` ao lado de
cada número, para os dois instrumentos não poderem ser lidos como um.

`--dump-dom` não mostra janela (`:9226-2229`) e não arranca worker
(`measurement-flag`), por isso é barato.

---

## 3. MENU DE PERSONALIZAR SIMPLES — 17 → 3

**Renderizei-o antes de lhe tocar** (`_main/tune-menu-shot.py`). Era 17 linhas
em duas colunas dentro de 352 px, cada uma a repetir "do tema" ao lado do label
e com o seu próprio ↺: mais chrome que conteúdo.

Ficaram **três**, escolhidas pelo registo do dono (uma série de remoções: *"tira
o botao de transcript"*, *"barras LIMPAS"*, *"1 botao de tamanho em vez de 2"*,
*"nao fala alt c no painel"*):

| fica | porque |
|---|---|
| `fontSans` — Fonte | que letra é; maior efeito isolated |
| `weightCaption` — Peso ao vivo | legibilidade é o produto |
| `accent` — Cor de destaque | um clique, inequívoco, e arrasta `--theme-swatch`/`--line` |

**`sizeCaption` é o único proibido**, e é a decisão mais importante: o painel
**já tem** o `#font-scale-button`, com 13 paragens e uma única fonte de
verdade (`--caption-scale`). Duas portas para um número é a forma exacta do
defeito que o dono reclamou.

**O que saiu NÃO se perdeu.** `FIELDS` não foi tocado: `declarationsFor`,
`allTokens`, `baseline` e `resetTheme` continuam a andar pelos 17, um valor
guardado num campo escondido continua a ser aplicado, e a nota debaixo do
título conta `Object.keys(settingsFor(name))` — o mapa **guardado**, não as
linhas desenhadas. Pôr um id de volta é uma linha.

**De bónus:** `.tune-body` passou de `1fr 1fr` para
`repeat(auto-fit, minmax(min(100%, 240px), 1fr))`. A terceira linha ficava
sozinha numa célula com um buraco ao lado; e a coluna única deixou de cortar o
select da fonte ("Barlow Condensed —" → "Barlow Condensed — teleprompter").

**Portão `_main/tune-simple-menu-oracle.js`: 11/11, `--neg-arm` 5/5.**

---

## 4. `#strip-theme-button` — comentários que mentiam, e CSS morto

Medido: **zero** `id="strip-theme-button"` no markup, **zero** ocorrências em
`panel.js`, e as 4 em `panel.css` eram todas comentários. O botão foi removido
pelo dono (o registo primário `panel.html:751` diz **2026-10-12**, com a frase
verbatim dele).

Oito comentários continuavam a descrevê-lo como vivo: 4 no HTML, 4 no CSS. **Diziam
correctamente que tinha sido removido; seis diziam que existia.** Corrigidos —
agora cada um ou diz a verdade ou remete para o registo.

**CSS morto encontrado:** `panel.css:2773` `.strip-button--theme` e `:2777`
`.strip-theme__swatch` estilizavam um botão inexistente. Apagados. Um inventário
de 2026-10-09 (`_rects-20261009-inventory.txt`) mostrava-os **vivos**, 85,2 × 26
px — o que prova que eram Reachability e não herança.

**Portão `_main/strip-css-dead-oracle.py`: 7/7, `--neg-arm` 4/4.** Testa os dois
lados: nenhum selector vivo para um control apagado, **e** nenhum comentário que
nomeie um control apagado sem dizer que foi apagado.

---

## 5. Um erro meu que vale registar

Ao corrigir a data de remoção, usei um `-replace` **global** em dois ficheiros de
produto. Tinha **6 ocorrências legítimas de 2026-10-14** sobre remoções *outras* e
todas passaram a 2026-10-12. Seis datas de factos sem relação passaram a mentir.
Revertidas uma a uma (`_main/_revert-20261014-dates.py`, 6/6) e confirmado por
`git diff` que só sobraram as minhas linhas.

**É a razão pela qual a doutrina deste repo é patch por número de linha e não
substituição de texto.** Um `-replace` global não sabe o que é contexto — e eu
sabia disso e fiz-me assim mesmo.

---

## Erros meus que os instrumentos apanharam hoje

Vale mais registar isto do que os acertos:

1. Quase "corrigi" um transbordo de cabeçalho que **não existia** (clamp 492).
2. Quase pus o default no `_child_env`; o `app-target-oracle` ARM e foi RED.
3. O `edit` pôs o `run.cmd` em **CRLF** — que é o defeito que o próprio ficheiro
   documenta em `:157-168`. Reposto a LF (0 CRLF / 274 bare LF, como o `HEAD`).
4. `echo VALUE=[SOTTO_REDUX_LIVE]` sem `%…%` imprimia a string literal; dois
   braços falharam por uma razão que nada tinha a ver com a linha testada.
5. O oráculo do menu só via que os loops diziam "menu", não **de onde** `menu`
   vinha — e o mutante `var menu = FIELDS` passou por ele.
6. Conte 15 campos olhando o PNG (eram 17) e retractei um comentário que estava
   **certo**.
7. Escrevi `id="strip-theme-button"` dentro do meu próprio comentário, e o oráculo
   apanhou-se a si.
8. `os.walk` entrou em `_fonts`/`node_modules`: **1051** folhas em vez de 17.
9. Um mutante com `.replace()` numa âncora inexistente era o ficheiro vivo, e
   reportou "SURVIVED" — indistinguível de um gate cego.
10. `UnicodeEncodeError` cp1252 ao imprimir uma falha.
11. Dois exit codes invertidos no `--neg-arm` (PASS devolvia 1).

---

## NÃO MEDIDO (e porquê)

- **Que o Parakeet carregue e transcreva** — exige inferência pesada sem o dono
  cá. O que está provado é que a flag chega ao worker.
- **Que a herança do `HKCU\Environment` chegue pelo Explorer** — sem instrumento
  nesta máquina. Resolvido por não depender dela: o default vive no `run.cmd`.
- **A borda, o Alt+C e os designs do 3.º zip, vistos pelos olhos do dono** — são
  juízos de pixel num ecrã que ninguém está a ver. O que tenho é o oráculo
  (`no-frame` 5/5), a captura, e o gesto medido (`hotkey-gesture-oracle`).