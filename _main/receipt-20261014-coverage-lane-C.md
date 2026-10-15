# RECIBO -- LANE C: as lacunas dos TEMAS e do HOTKEY

Data: 2026-10-14/15 (America/Sao_Paulo). Lane C. **Nada foi lancado**: nenhum shell,
worker, WebView2, browser ou janela. `TMPDIR=I:/cc-tmp` em todos os comandos.

## 0. A RESPOSTA CURTA, COM OS NUMEROS

| comando | antes (2026-10-14) | agora (2026-10-15) |
|---|---|---|
| `py -3 _main/cobertura-oracle.py` | `COVERAGE 16/34`, **18 [GAP]**, rc=1 | `COVERAGE 34/34`, **0 gap(s)**, **rc=0**, `VERDICT: PASS` |
| `node _main/instruments-battery.mjs` | -- | `SUMMARY: 130/130 instrument(s) rc=0; failed=0; launches=0`, **rc=0** |

**AS DUAS VERIFICACOES FINAIS OBRIGATORIAS PASSAM.** O numero de `[GAP]` desceu de **18
para 0**, e a bateria dá `rc=0` com o total a subir de **119 para 130** linhas.

A linha do tempo, medida (importa, porque as lanes correm em paralelo e um numero sem hora
mente):

| momento | cobertura | bateria |
|---|---|---|
| inicio desta lane | 16/34, 18 gaps | -- |
| depois das minhas 6 areas | 30/34, 4 gaps | 118/119, `failed=1` (a unica falha era o cobertura-oracle) |
| depois de as lanes irmaos fecharem as ultimas 4 | **34/34, 0 gaps, rc=0** | **130/130, failed=0, rc=0** |

As 4 areas que ainda faltavam quando escrevi a primeira versao deste recibo
(`wrapper pre-flight`, `panel hide gate at startup`, `JS<->Python surface loop guard`,
`log flood census`) **nao sao desta lane e nao foram tocadas por mim**: os instrumentos
ja existiam em disco e as lanes donas deles acrescentaram as linhas. Nao os corri -- dois
deles trazem assinatura de lancamento (`pythonw` / `run.cmd` / `sotto_webview`) e o meu
brief proibe lancar.

As **6 lacunas desta lane estao TODAS fechadas** e todas as 6 aparecem `[ok]` no
cobertura-oracle: `hotkey / Alt+C cycle`, `theme chrome (footer labels)`,
`theme switching`, `themes: design fidelity (zip)`,
`themes: light census`, `fonts fidelity`.

**A UNICA FALHA DA BATERIA ERA O PROPRIO COBERTURA-ORACLE**, e era das OUTRAS
lanes. Medido a meio da sessao: das 119 linhas, 118 davam `rc=0` -- incluindo as 16 que eu
acrescentei -- e a unica `rc=1` era a linha `cobertura: 34 areas`, vermelha porque restavam
4 areas **que nao sao desta lane**. Os 4 instrumentos **ja existiam em disco**; faltava so a
linha na bateria:

| area que faltava | instrumento que ja existia | bytes |
|---|---|---|
| wrapper pre-flight (run.cmd exit) | `_main/run-cmd-exit-oracle.py` | 63 811 |
| panel hide gate at startup | `_main/panel-hidden-at-startup-oracle.py` | 43 210 |
| JS<->Python surface loop guard | `_main/surface-loop-oracle.py` | 14 273 |
| log flood census | `_main/log-flood-census.py` | 13 594 |

NAO acrescentei essas linhas e NAO corri esses oráculos: duas delas
(`run-cmd-exit`, `panel-hidden-at-startup`) trazem assinatura de lancamento
(`pythonw` / `run.cmd` / `sotto_webview`) e o meu brief proibe lancar. **As lanes donas
delas fecharam-nas durante esta sessao**, e a ultima medicao (acima) ja as mostra `[ok]`.

---

## C1. hotkey / Alt+C cycle -- o codigo morto do `panel_mode`

**Instrumento (NOVO):** `_main/hotkey-cycle-oracle.py` -- 17 131 B, 419 linhas,
sha256 `7A6E2D838B66BAFD…`.

Instancia a **classe REAL** `SottoShell` de `app/webview/sotto_webview.py`
(`object.__new__`, a mesma tecnica que `_main/emit-queue-bound-oracle.py` ja
provou neste ficheiro: sem `__init__`, sem janela, sem lock) e conduz o ciclo pelos
metodos REAIS `hotkey_pressed` -> `show_strip` / `show_side` /
`hide_panel`. O estado da janela **nao e uma variavel que o oráculo escreve a cada
pressao**: os falsos `hide_window` / `foreground_unlock` /
`window_visible` movem um HWND falso partilhado, portanto o ramo que
`hotkey_pressed` toma e decidido pelo estado que as CHAMADAS DO PROPRIO SHELL
deixaram -- o que uma janela real faz.

5 armas: (1) o ciclo; (2) o campo escrito; (3) o nome de superficie e REAL; (4) sem relogio
(medido no **AST dos 5 metodos**, nao num grep: as palavras sobrevivem nas docstrings onde
explicam o que foi apagado); (5) `toggle_panel` decide pela janela VIVA.

**Braco negativo:** `--neg-arm`, **3 mutantes** em copias CRLF-exactas sob
`$TMPDIR`. Cada ancora e verificada com `count == 1` antes de ser usada -- um
controlo que nao encontra o proprio alvo diz `CONTROL IS DEAD` em vez de remendar a
linha errada (regra N2). O ficheiro e lido com `newline=''` (o shell e CRLF puro:
10097 CRLF / **0 bare LF**), sem o qual todas as ancoras falhavam em silencio.

**Prova de que diz NAO** (`py -3 _main/hotkey-cycle-oracle.py --neg-arm` -> `rc=0`,
`VERDICT: PASS`):

* **M1 -- O DEFEITO ANTIGO, EXACTAMENTE (o campo nunca escrito).** `panel_mode` deixa
  de ser escrito em `show_strip` E em `show_side`. Resultado medido, e e a
  reproducao da medicao do dono:
  `panel_mode after 6 presses = ['strip','strip','strip','strip','strip','strip']` e
  `the painted order is ['strip','side','side','side','side','side']` -- a 3.a
  pressao repinta o painel LATERAL e `hide_window` e chamado **0 vezes**. O dono mediu
  10 pressoes, 10 `PANEL_SHOWN … mode=side` e UM `PANEL_HIDDEN` em todo o log.
* **M2** -- `set_panel_surface('panel')` volta a ser o literal `'side'`
  (o defeito de 2026-10-12): RED em `ARM 3` (o nome nao esta em
  `SURFACE_NAMES`).
* **M3** -- o terceiro ramo do ciclo fica inalcancavel: RED em `ARM 1`.

**Controlo positivo:** a mesma corrida sem mutacao -> `rc=0`, `VERDICT: PASS`.

---

## C2. theme chrome (footer labels) -- o historico / em curso que o dono mandou tirar

**Instrumento (NOVO):** `_main/panel-chrome-gate.py` -- 16 645 B, 391 linhas,
sha256 `9FE568BD425BE82C…`.

O `_main/_panel-chrome-arm.py` (41 353 B) e o instrumento COMPLETO desta area e
**lanca o Chromium headless** -- por isso nao pode correr na bateria, e uma area cujo unico
gate nao corre e uma area sem gate, que e exactamente o que o cobertura-oracle dizia. Este
ficheiro e a METADE ESTATICA: o mesmo contrato, lido dos bytes, **sem lancar browser**.

6 armas: (A) a ordem do dono -- `HISTÓRICO` e `EM CURSO` so podem sobreviver
dentro de um comentario HTML e `tele` nao tem bloco de rodape nenhum; (B) as outras
QUATRO direccoes mantem o seu (um gate que so verificasse a remocao passaria num painel SEM
rodape nenhum); (C) o CSS gerado concorda -- 0 regras `chrome--tele[…foot]` em todas
as folhas, >=1 para cada uma das outras quatro, na folha dona E em `panel-designs.css`;
(D) o gerador concorda (`gen_themes.py`: 0 regras `tele` de rodape);
(E) o contrato de classe intacto (`chrome` + `chrome--<direccao>`) e os cinco
blocos de cabecalho presentes; (F) nenhuma leitura inventada dos mockups.

**Braco negativo:** `--neg-arm`, **3 mutantes** em copias sob `$TMPDIR`.
**Prova de que diz NAO** (`rc=0`, `VERDICT: PASS (every mutant RED=True)`):

* **M1** (os dois spans `tele` de volta) -> RED em `ARM A`:
  `"HISTÓRICO" is still LIVE markup`, `"EM CURSO" is still LIVE markup`,
  `the tele direction still carries 2 footer block(s): ['start','end']`.
* **M2** (`class="chrome` -> `class="chrome-off`, 42 blocos) -> RED em
  `ARM B`: as quatro direccoes perdem o rodape. E a MESMA mutacao que o
  `_panel-chrome-arm.py --neg-arm` chama `markup`.
* **M3** (uma regra `chrome--tele[…foot]` de volta em `theme-1.css`) -> RED
  em `ARM C`: `theme-1.css still carries 1 chrome--tele footer rule(s)`.

**Controlo positivo:** `control: the shipped panel is GREEN (0 failure(s))`.

**O que isto NAO cobre**, dito e nao implicado: le BYTES, portanto nao ve uma regra que
existe mas perde a cascata, nem um no escondido por `display:none` noutro sitio, nem
nada que o browser sintetize. Para isso existe o `_panel-chrome-arm.py`; os dois sao
complementos, nao rivais.

---

## C3. theme switching -- trocar de tema

**Instrumento (NOVO):** `_main/theme-switch-oracle.js` -- 25 801 B, 611 linhas,
sha256 `5688CAA7C96405B3…`.

Carrega o **modulo REAL** `app/panel/theme-switcher.js` (48 089 B) contra um
documento falso, tal como o `_main/theme-preview-oracle.js` ja faz. Nada lancado.
`require` e construido com `createRequire(import.meta.url)` (o oráculo e ESM, o
modulo e CommonJS) e `global.window` e instalado ANTES do `require@@: o modulo le
`window` UMA vez, no load, e sem isso carregava com `root === null`.

8 armas: (1) a troca e UMA escrita de atributo; (2) o ciclo e um ANEL que dá a volta (as
pontas da lista nao sao uma parede); (3) um nome desconhecido e RECUSADO -- uma troca
meio-aplicada e pior que nenhuma; (4) a troca nao toca em mais nada (nao chega a ponte do
shell, nao escreve texto em nenhum elemento); (5) cada entrada do manifesto tem um scope no
CSS gerado, senao a troca muda o atributo e nao pinta nada; (6) a escolha guardada volta
depois de um restart; (7) a persistencia e defensiva (`localStorage` a lancar, como
`file://` no WebView2); (8) `mount()` e idempotente.

**Braco negativo:** `--neg-arm`, **3 mutantes**. **Prova de que diz NAO**
(`rc=0`, `VERDICT: PASS (every mutant RED=true)`), cada mutante RED na arma
que e dele:

* **M1** (a escrita do atributo removida) -> `ARM 1`:
  `set() wrote the attribute 0 time(s), expected exactly 1`.
* **M2** (a recusa do nome desconhecido removida) -> `ARM 3`:
  `an unknown name was ACCEPTED and returned`.
* **M3** (a escrita na store removida) -> `ARM 6`:
  `after a restart the document wears "theme-1", expected "theme-5"`.

**Controlo positivo dentro do mesmo comando:** `control: the shipped module is GREEN
(0 failure(s))` -- um modulo que falhasse TUDO nao passaria por controlo.

**Dois defeitos do MEU instrumento, apanhados e corrigidos aqui** (regra N5, um vermelho
nunca fica sem atribuicao): (a) dois mutantes partilhavam um directorio de rascunho e o
`require` faz cache por caminho, portanto o segundo re-corria os bytes do PRIMEIRO --
agora cada mount tem directorio proprio; (b) as armas liam um `doc@@ global que o mount
seguinte substituia -- agora cada arma le `m.doc@@, o documento daquele modulo.

---

## C4. themes: design fidelity (zip) -- REGISTADOS, nao reescritos

Os tres oráculos **ja existiam** e nao foram tocados. O que faltava era a PORTA. Registados
na bateria com o braco negativo ao lado de cada um:

| instrumento | corrida | resultado medido |
|---|---|---|
| `_main/cine-themes-oracle.py` | `--neg-arm` | `rc=0`, `NEG-ARM VERDICT: PASS -- 8 mutant(s), 0 wrong, 0 inert, control GREEN` |
| `_main/cinematic-designs-oracle.py` | `--neg-arm` | `rc=0`, `NEG-ARM VERDICT: PASS -- 6 mutant(s), 0 wrong, 0 inert, control GREEN` |
| `_main/zipc-designs-oracle.py` | `--neg-arm` | `rc=0`, `NEG-ARM VERDICT: PASS -- 6 mutant(s), 0 wrong, 0 inert, control GREEN` |

As tres corridas sem `--neg-arm` também dão `VERDICT: PASS`, e as tres
`--neg-arm` imprimem `CONTROL GREEN failed=none` -- portanto cada uma diz
NAO e nenhuma delas e decorativa. Total: **20 mutantes** entre as tres.

---

## C5. themes: light census -- nenhum tema branco

**Instrumento (JA EXISTIA, registado com `--gate`):**
`_main/theme-lightness-census.py`. Medido: `themes measured: 45`,
`LIGHT (luminance >= 0.50): 0`, `GATE: GREEN -- no theme ships a light panel`,
`rc=0`. O limiar 0.50 e o MESMO que `gen_cinematic.py` já usa
(`panel_is_light()`): um censo com outra linha discutiria com a coisa que mede.

**O que faltava era o BRACO NEGATIVO**, e ele faltava por uma razao estrutural: o censo tinha
o `PANEL` fixo no codigo, portanto so sabia dizer VERDE -- um gate sem forma de o
apontar a um mutante e um gate que nao se pode mostrar a dizer NAO. Duas edicoes pequenas e
aditivas (nao uma reescrita):

1. `--panel <dir>` -- mede uma COPIA, religando os globais `PANEL`/`THEMES`.
   (O `global` tem de vir ANTES de ler `PANEL` no `default@@ do argumento: o
   `py_compile` apanhou o `SyntaxError` e eu corrigi.)
2. `--neg-arm` -- corre **ESTE FICHEIRO DUAS VEZES, em dois PROCESSOS**: uma na arvore
   embarcada (tem de dar VERDE) e uma na copia (tem de dar VERMELHO). Dois processos, nao duas
   chamadas, porque um controlo que partilha o processo que produziu o verde herda o estado
   dele -- e a afirmacao toda aqui e que o gate distingue as duas arvores.

A injectcao e o proprio token `--bg-slab` do tema, substituido dentro do bloco
`:root[data-theme='theme-1']` dele -- e o token a que
`painted_background()`recorre para a camada base, portanto a copia compoe mesmo
branco em vez de se afirmar que compoe.

**Prova de que diz NAO** (`py -3 _main/theme-lightness-census.py --neg-arm` -> `rc=0`):

    NEG-ARM injected: theme-1 --bg-slab #060708 -> #ffffff  (I:/cc-tmp\lightness-neg\themes\theme-1.css)
    NEG-ARM shipped tree : rc=0 GREEN
    NEG-ARM injected copy: rc=1 RED as required
            LIGHT (luminance >= 0.50): 1 ['theme-1']
            GATE: RED -- 1 theme(s) still ship a light panel
    VERDICT: PASS  (control GREEN=True, injected RED=True)

---

## C6. fonts fidelity -- as fontes do .zip

**Instrumento (JA EXISTIA, corrigido e registado):**
`_main/fonts-fidelity-oracle.mjs` -- agora 19 375 B, 394 linhas,
sha256 `4969D54B91C2DBD3…`.

**O oráculo estava VERMELHO na arvore embarcada, e o vermelho era DELE, nao do produto.**
Medido antes da correccao: `ARM A zip families=18 not-on-disk-or-not-declared=2`,
com dois RED:

    RED Apple Color Emoji onDisk=false declared=false  <- cinematic-transcription-app-designs/index.html (--font-*)
    RED Liberation Mono   onDisk=false declared=false  <- cinematic-transcription-app-designs (1)/index.html (--font-*)

**A causa, medida nos bytes:** `primaryFamily()` tira o primeiro nome **ENTRE
ASPAS** de uma pilha. Isso esta certo para a pilha propria de um design
(`'Fraunces','Georgia',serif`) e ERRADO para uma generica: o `--font-sans` /
`--font-mono` por defeito do Tailwind, dentro do `dist/index.html`
construido de um zip, cita SO os fallbacks --

    --font-sans: ui-sans-serif,system-ui,sans-serif,"Apple Color Emoji",…
    --font-mono: ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",…

-- portanto o primeiro nome entre aspas e uma fonte do SISTEMA OPERATIVO. O `ARM A`
exigia entao que embarcassemos a `Apple Color Emoji` (da Apple, proprietaria,
nao-embarcavel) e a `Liberation Mono`. Nenhuma das duas pilhas nomeia uma tipografia
de design.

**A correccao e estreita:** percorrer a pilha, saltar palavras-chave genericas de CSS e fontes
do SO, e devolver a PRIMEIRA entrada que sobra; uma pilha feita so dessas nao pede NADA.
Cada salto e IMPRESSO, para uma familia nao poder ser descartada em silencio:

    ARM A  zip families=16  not-on-disk-or-not-declared=0  stacks-naming-no-design-face=12
           skip … --font-* stack names only generic/OS faces: ui-sans-serif,system-ui,sans-serif,"Apple Color Emoji",…
           skip … --font-* stack names only generic/OS faces: 300
           …

**16 familias** -- exactamente as 16 que o `_main/receipt-fonts.md` já tinha medido
por outra via. Os pedidos ao Google Fonts sao lidos independentemente, portanto uma face real
nomeada numa pilha continua a ser verificada. Restantes armas depois da correccao:
`ARM B @font-face=70 broken-src=0 not-swap=0`, `ARM C … with no exact @font-face=0`,
`ARM D theme scopes=35 caption-face misses=0` -> `VERDICT: PASS (A=true B=true C=true D=true)`.

**Braco negativo** (`node _main/fonts-fidelity-oracle.mjs --neg-arm` -> `rc=0`):
apaga da COPIA todos os `@font-face` da familia de legenda do primeiro scope
(`Barlow Condensed`, a face de legenda de `theme-1`): `71 -> 67`
faces, e o resultado e

    ARM C … with no exact @font-face=2
    ARM D  theme scopes=35  caption-face misses=2
    NEG-ARM verdict: RED as required
    VERDICT: PASS  (control GREEN=true, injected RED=true)

---

## 3. O QUE ENTROU NA BATERIA (16 linhas, as duas cores de cada lacuna)

Em `_main/instruments-battery.mjs` (agora 14 528 B, 203 linhas, 202 CRLF / **0 bare
LF**, sha256 `8D293B35422A174C…`):

    ['_main/hotkey-cycle-oracle.py', 'Alt+C cycle strip->side->hide'],
    ['_main/hotkey-cycle-oracle.py --neg-arm', 'Alt+C cycle neg (3 mutants)'],
    ['_main/panel-chrome-gate.py', 'panel chrome: footer labels, no browser'],
    ['_main/panel-chrome-gate.py --neg-arm', 'panel chrome neg (3 mutants)'],
    ['_main/theme-lightness-census.py --neg-arm', 'no white theme: neg (white injected)'],
    ['_main/cine-themes-oracle.py --neg-arm', 'cine themes neg (8 mutants)'],
    ['_main/cinematic-designs-oracle.py --neg-arm', 'cinematic designs neg (6)'],
    ['_main/zipc-designs-oracle.py --neg-arm', 'zipc designs neg (6)'],
    ['_main/theme-switch-oracle.js', 'theme switching: ONE attribute write'],
    ['_main/theme-switch-oracle.js --neg-arm', 'theme switching neg (3 mutants)'],
    ['_main/fonts-fidelity-oracle.mjs', 'fonts fidelity (the .zip faces)'],
    ['_main/fonts-fidelity-oracle.mjs --neg-arm', 'fonts fidelity neg (face deleted)'],

(As 4 linhas de `--gate` / sem `--neg-arm` de `theme-lightness`,
`cine-themes`, `cinematic-designs` e `zipc-designs` já tinham
entrado por outra mao durante esta sessao; eu acrescentei o PAR, porque um oráculo que so
corre numa cor nao distingue a cura da ausencia de teste.)

**Nenhuma linha da bateria lanca nada**: medido no fim da corrida,
`launches=0`.

---

## 4. PINS (2026-10-15, medidos com `node@@ sobre os bytes + `crypto`)

| ficheiro | bytes | linhas | CRLF / bare LF | sha256 |
|---|---|---|---|---|
| `_main/hotkey-cycle-oracle.py` (NOVO) | 17 131 | 419 | 0 / 418 | `7A6E2D838B66BAFD…` |
| `_main/panel-chrome-gate.py` (NOVO) | 16 645 | 391 | 0 / 390 | `9FE568BD425BE82C…` |
| `_main/theme-switch-oracle.js` (NOVO) | 25 801 | 611 | 0 / 610 | `5688CAA7C96405B3…` |
| `_main/fonts-fidelity-oracle.mjs` (EDITADO) | 19 375 | 394 | 0 / 393 | `4969D54B91C2DBD3…` |
| `_main/theme-lightness-census.py` (EDITADO) | 17 869 | 453 | 0 / 452 | `E8C75D2375868D5B…` |
| `_main/instruments-battery.mjs` (EDITADO) | 14 528 | 203 | 202 / 0 | `8D293B35422A174C…` |
| `app/webview/sotto_webview.py` (SO LIDO) | 524 312 | 10 098 | 10 097 / 0 | `D888D0CBF1D65880…` |
| `app/panel/theme-switcher.js` (SO LIDO) | 48 089 | 1 095 | 1 094 / 0 | `4E68D6E002819170…` |

Os oráculos novos sao LF (ficheiros novos, criados por mim); os ficheiros do PRODUTO que
editei nao existem -- **nao editei um unico byte de `app/`**. Os mutantes sao escritos
em `$TMPDIR` e removidos no fim.

---

## 5. O QUE NAO FOI MEDIDO (regra F6)

* **Nada disto prova o que o WebView2 real PINTA.** As 6 areas foram medidas em bytes, em
  processo, ou por import da classe/modulo reais. A metade pintada de C2 continua a ser do
  `_main/_panel-chrome-arm.py`, que **lanca o Chromium** e por isso nao corre na
  bateria -- nao o corri, e o meu gate declara essa fronteira em vez de a esconder.
* **O ciclo do Alt+C nao foi medido num teclado real.** A prova e a classe real a decidir sobre
  um HWND falso movido pelas suas proprias chamadas; nao ha registo de um `WM_HOTKEY`
  verdadeiro.
* **Nao reabri a contradicao do AGENTS.md** sobre o painel aparecer no arranque (18/20 a 25 ms
  vs 0/20): essa area e a `panel-hidden-at-startup`, nao e desta lane.
* **Nao medi as 4 areas das outras lanes** que fecharam a cobertura: `run-cmd-exit`,
  `panel-hidden-at-startup`, `surface-loop`, `log-flood`. O `rc=0` da bateria inclui-as,
  mas quem as correu foram as lanes donas; o que eu medi delas e a MEMBERSHIP, nao o
  comportamento.
* **A bateria foi corrida duas vezes**: a primeira deu `118/119` (a unica falha era o
  cobertura-oracle, por causa das 4 areas ainda abertas) e a segunda, depois de as lanes
  irmaos fecharem as ultimas, deu `130/130 failed=0 rc=0`. Os dois numeros estao no §0
  com a hora, porque um numero sem hora e um numero que mente.
