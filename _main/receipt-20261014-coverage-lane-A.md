# RECIBO -- LANE A: as lacunas do PAINEL e da LEGENDA (2026-10-14/15)

A ordem do dono, verbatim: *"cobre todo o restante"* -- fechar as 18 lacunas que
`py -3 _main/cobertura-oracle.py` mediu. Este recibo cobre as SEIS da lane A:
surface loop, botoes lane, caption line fidelity, caption overlay independence,
panel state write (atomic) e panel hide gate at startup.

**Nada foi lancado.** Nenhum shell, nenhum WebView2, nenhum worker, nenhum browser.
`TMPDIR=I:/cc-tmp`. A bateria imprime o seu proprio numero: `launches=0`.

---

## VERIFICACAO FINAL (os numeros)

| comando | antes | depois |
|---|---|---|
| `py -3 _main/cobertura-oracle.py` | **16/34 areas, 18 [GAP]**, rc=1 | **34/34, 0 [GAP]**, rc=0 |
| `node _main/instruments-battery.mjs` | 137 instrumentos, **136 rc=0, 1 rc=1** (`photo-scrim-census`, lane C) | **139 instrumentos, 138 rc=0, 1 rc=1** -- o MESMO vermelho da lane C, atribuido abaixo; **as 14 linhas das seis areas desta lane correm todas rc=0** |

As seis areas desta lane, uma a uma, no `cobertura-oracle` depois do trabalho:

```
  [ok]   JS<->Python surface loop guard                       <- surface-loop
  [ok]   buttons lane (size and visibility)                   <- botoes-lane
  [ok]   caption line fidelity                                <- caption-lines
  [ok]   caption overlay independence                         <- caption-independent
  [ok]   panel hide gate at startup                           <- panel-hidden-at-startup
  [ok]   panel state write (atomic)                           <- panel-state
```

---

## A1 -- JS<->Python SURFACE LOOP GUARD (a guarda que fechou o travamento, p99 264/s)

O defeito medido (audit 2026-10-13): **30 647 aplicacoes** do caminho de surface
contra **CINCO** transicoes reais de Alt+C; p50 102/s, p90 185/s, **p99 264/s**, max
294/s ao longo de 14 536 s. O shell ecoa a geometria em cada `set_panel_surface` e a
pagina re-corria o pipeline inteiro em cada eco. Nao havia instrumento nenhum para
isto -- foi escrito nesta lane, **nas duas metades**, porque a guarda existe nos dois
lados e um so lado nao fecha o loop.

### Metade SHELL -- `_main/surface-loop-oracle.py` (NOVO)

`14 273 B`, 338 linhas, sha256 `8677A8D14CCC99178B8B5EAB2EE2C718FFA32488896F44C8EBF04B154D94FB49`.

Instancia a CLASSE REAL e conduz a mensagem pelo fio real: importa
`app/webview/sotto_webview.py`, constroi um `SottoShell` real, embrulha-o no
`SottoHost` real e envia `SottoHost.dispatch(json)` com o mesmo payload que a pagina
envia (`{"kind": "panel-surface", "payload": {"surface": ..., "reason": ...}}`).
As costuras que tocam o SO (`exec_js`, `_apply_window_geometry`, a re-medicao do strip)
sao GRAVADAS, nao executadas; `log()` e capturado, por isso um verde silencioso e
impossivel.

```
py -3 _main/surface-loop-oracle.py            -> rc=0, 0.1 s, VERDICT: PASS 5/5
py -3 _main/surface-loop-oracle.py --neg-arm  -> rc=0, 0.2 s, 3/5 verdes, 2 RED
```

| arm | shipped | mutante (guarda apagada na copia) |
|---|---|---|
| A APPLY | `applied=1`, 1 linha `PANEL_SURFACE` | `applied=1` (a transicao real nao e suprimida) |
| B ECHO | 200 ecos -> **as 200 repeticoes somaram 0**; `exec_js=4` em 202 mensagens | 200 ecos -> **somaram 201**; `applications=203`; `exec_js=406` |
| C GENUINE | `strip->panel applied=1`; mesma surface, reason novo: `applied=1` | idem (a guarda nao e supressao) |
| D REFUSAL | `nonsense` -> `applied=0`, 1 `PANEL_SURFACE_REFUSED` | idem |
| E FIX-POINT | 200 rondas do loop -> **cresceu 0** | 200 rondas -> **cresceu 200** |

**A prova de que diz NAO:** o braco negativo apaga a idempotencia de uma COPIA
(ancora exacta; o oraculo RECUSA construir o mutante se a ancora nao aparecer
exactamente 1 vez), e as duas armas que a guarda ganha ficam RED. Taxa medida
in-process: 71 411-99 698 ecos/s, contra os 264/s que travavam a maquina -- o numero
que importa e 200 ecos -> 1 aplicacao, e 203 com a guarda fora.

### Metade PAGINA -- `_main/surface-loop-panel-oracle.js` (NOVO)

`20 338 B`, 432 linhas, sha256 `C8AA1DD8909E46EFF75C1DB561FB93D02A08803A115E57726AF57EA339E4D89B`.

jsdom sobre o documento REAL: `panel.html` + `panel.css` + `caption-float.css` + a
lista de scripts do proprio documento (**13 scripts, 0 erros**), com um bridge que
responde a um `setPanelSurface` como o shell responde (poe a surface E ecoa a
geometria -- o eco e a segunda metade do loop; um stub que o omitisse estaria a testar
um loop que nao existe). O contador e o **trafego do loop**: os asks pagina->shell,
que e a metrica do proprio audit (30 647).

```
node _main/surface-loop-panel-oracle.js            -> rc=0, 1.4 s, VERDICT: PASS 6/6
node _main/surface-loop-panel-oracle.js --neg-arm  -> rc=0, 3.0 s, M1 5/6 RED, M2 5/6 RED
```

| arm | shipped | M1 (surface.js sem a guarda de mudanca) | M2 (panel.js sem `after !== before`) |
|---|---|---|---|
| A GENUINE-SWITCH | `pageAsks=2`, surface=`strip` | RED (`capped=1`) | RED (`capped=1`) |
| B ECHO-STORM | **0 asks em 200 ecos** | RED: **200 asks em 200 ecos** | RED: **200 asks em 200 ecos** |
| C PAGE-REASK | 0 asks, `capped=0` | RED `capped=1` | RED `capped=1` |
| D REFUSAL | 0 asks, surface intacta | RED | RED |
| E FIX-POINT | **0 asks, `capped=0`, em 200 rondas** | RED `capped=1` | RED `capped=1` |

A arm A mede **2** asks numa transicao real, e isso e o produto a funcionar: `panel.js`
`applyFloat` (:2338) e `caption-float.js` `setFloat` (:243) pedem ambos a strip. O que a
guarda impede e a REPETICAO, nunca a transicao.

**A prova de que diz NAO:** os dois mutantes sao copias do `app/panel` real (copia
RECURSIVA -- `themes/` incluido) com UMA guarda apagada cada, e ambos ficam 5/6 RED. O
runaway e CONTADO, nao sofrido: o stub tem um tecto de profundidade e um disjuntor, e
todas as armas exigem `capped === 0` -- sem isso o mutante pendurava o oraculo em vez de
o fazer RED (medido: 300 s de timeout na primeira versao).

---

## A2 -- BUTTONS LANE (size e visibilidade) -- O ORACULO JA EXISTIA; REGISTADO

`_main/botoes-lane-oracle.js`, `15 568 B`, sha256 `67410870E085B1B2...`, le os BYTES de
`panel.html`/`panel.css`/`strip-drag.js` (nenhum browser).

```
node _main/botoes-lane-oracle.js            -> rc=0, 0.1 s, 34 check(s), 0 failed, VERDICT: PASS
node _main/botoes-lane-oracle.js --neg-arm  -> rc=0, 39.3 s, 8/8 mutantes RED
```

Os oito mutantes, um por arm, todos RED: M1 botao live apagado (4 checks), M2 estado OFF
sem a sua palavra, M3 o label de legenda do painel da direita de volta, M4 hide deixa de
ser o controlo mais a direita, M5 o pointerdown do drag apagado, M6 o link do
`caption-float.css` apagado, M7 a strip volta a mostrar a caixa de legenda, M8 o botao
Linhar removido volta.

A linha verde ja tinha sido posta pela lane C enquanto eu trabalhava; a linha do BRACO
NEGATIVO (`botoes lane neg 8/8 RED`) foi posta por mim, porque sem ela a area corria na
porta so com a cor verde.

---

## A3 -- CAPTION LINE FIDELITY (a legenda e a linha que o worker fechou) -- JA EXISTIA; REGISTADO

`_main/caption-lines-oracle.py`, `11 248 B`, sha256 `BF5C48B689190916...`. Importa o
modulo REAL (`worker/sotto_worker.py`) e conduz a `LineFormer` real.

```
py -3 _main/caption-lines-oracle.py  -> rc=0, 0.2 s, caption-lines-oracle: 12 PASS / 0 FAIL (12 arms)
```

Cada arma carrega o seu proprio CONTROL -- o emissor pre-mudanca (`_PassThrough`),
re-implementado no ficheiro -- e o control TEM de diferir, ou a arma nao conta. Exemplos
medidos: arm 7 (`partial=false`) real `["going along the road"]` vs control
`["going","along","the road"]`; arm 8 `start` real `[0.0,0.0,0.0]` vs control
`[0.0,0.5,1.0]`; **arm 11** -- o fecho publicado OUT OF BAND, uma vez, marcado `final`
(`take_closed()`), que e exactamente "a linha que o worker fechou" -- real
`(["held","held back"], ["held back"], [True])` vs control `(..., [], [])`.

**A prova de que diz NAO:** em todas as 12 armas o control e obrigado a diferir; uma arma
cujo control concorde nao conta como verde (o ficheiro imprime `must differ: NO` quando
isso acontece). A linha na bateria (`caption lines fidelity`) foi posta pela lane C.

---

## A4 -- CAPTION OVERLAY INDEPENDENCE (a legenda nao pode depender do painel) -- JA EXISTIA; REGISTADO

Dois instrumentos, ambos ja escritos, ambos agora com linha:

```
node _main/three-overlays-oracle.js            -> rc=0, 0.2 s, 32 check(s), 0 failed, VERDICT: PASS
node _main/three-overlays-oracle.js --neg-arm  -> rc=0, 0.4 s, 10 mutantes RED, NEG-ARM VERDICT: PASS
node _main/caption-independent-oracle.js       -> rc=0, 1.6 s, 49 check(s), 0 failed, VERDICT: PASS
node _main/caption-independent-oracle.js --neg-arm -> rc=0, 61.8 s, 8 mutantes RED
```

`three-overlays-oracle.js` (`22 887 B`, sha256 `C896289FFEB2E9AB...`) le os bytes do
painel; os seus mutantes vao de 1 a 4 checks RED cada (ex.: N3 `.history` volta a
aparecer na strip; N5 a strip volta a encolher para a pill `max-content`; N9 o botao LIVE
deixa de chamar `applyFloat`). `caption-independent-oracle.js` (`36 404 B`, sha256
`FA88AAA9FC1DF274...`) e o gate mais pesado -- pinta a overlay com NENHUM painel no
documento (jsdom) e tem 8 mutantes.

**NAO MEDIDO / custo declarado:** o braco negativo do `caption-independent` (61.8 s) NAO
esta na bateria; o default (1.6 s) esta. A area fica com dois instrumentos verdes e um
braco negativo (o do `three-overlays`, 0.4 s) a correr na porta.

---

## A5 -- PANEL STATE WRITE (ATOMIC) -- o temp fixo que dava 1 145 063 falhas

`_main/panel-state-atomic-oracle.py` (NOVO), `20 443 B`, 472 linhas, sha256
`FAD28F40CAB55A94AB7E3AD48D5BBE248E9775EA2E8B7232129364F769443A33`.

Carrega o modulo REAL `app/webview/panel_state.py` por caminho e conduz o `write_atomic`
real e a classe real `PanelStateWriter` contra um alvo de scratch. As duas costuras sao
instrumentos, nao atalhos: o `open` do modulo e embrulhado para CAPTURAR o caminho
temporario de cada escrita, e o `os` do modulo e trocado por um shim que faz o
`os.replace` falhar QUANDO EU QUISER -- e assim que a tempestade de PermissionError que o
audit mediu e reproduzida de forma determinista.

```
py -3 _main/panel-state-atomic-oracle.py            -> rc=0, 6.4 s, 9/9 verdes, VERDICT: PASS
py -3 _main/panel-state-atomic-oracle.py --neg-arm  -> rc=0, 19.4 s, M1 3/9 RED, M2 2/9 RED
```

| check | medido no shipped | com a cura removida |
|---|---|---|
| S1 nome do temp | `tmp = '%s.%d.%d.tmp' % (path, os.getpid(), threading.get_ident())` | M1: `tmp = path + '.tmp'` -> **RED** |
| S2 retry | loop limitado que apanha `PermissionError` | M2: um `os.replace` nu -> **RED** |
| S3 irmao + fsync | `dirname(abspath(path))` e `os.fsync` antes do rename | -- |
| B1 | JSON valido, 0 `.tmp` deixados | -- |
| B2 | 2 threads -> 2 nomes DIFERENTES (`...37576.41196.tmp` vs `...37576.35132.tmp`) | M1: os DOIS capturam `panel-state.json.tmp` -> **RED** |
| B3 | 100 escritas / 4 threads: **0 leituras truncadas** (11 917 parses, 30 leituras ocupadas) | M1: **557 leituras NAO parseaveis**, 31 escritas falhadas -> **RED** |
| B4 | 2 recusas -> `attempts=3`, ficheiro landa com `sequence=99` | M2: `attempts=1`, levanta PermissionError, nada landa -> **RED** |
| B5 | rename impossivel -> levanta E remove o temp | -- |
| B6 | 2 `PanelStateWriter` REAIS no mesmo caminho: ambos landam, schema ok | -- |

**A prova de que diz NAO:** as duas metades da cura sao removidas, uma de cada vez, de uma
copia (ancora exacta; o oraculo recusa construir o mutante se a ancora nao aparecer 1
vez), e cada uma deixa o oraculo RED: 3/9 e 2/9.

**O QUE B3 NAO AFIRMA, medido:** o retry e LIMITADO (6 tentativas), por isso sob contenda
uma escrita ainda pode perder-se -- medido **2 de 100** no shipped contra 31 e 42 de 100
nos mutantes. O invariante que B3 afirma e o estrutural: um leitor nunca ve MEIO dump (0
truncadas shipped vs 557 no mutante). Uma leitura recusada enquanto um rename esta em voo
(30-33) e contada e reportada: uma leitura OCUPADA nao e uma leitura parcial.

---

## A6 -- PANEL HIDE GATE AT STARTUP -- o gate que impede o painel de aparecer sozinho

`_main/panel-hidden-at-startup-oracle.py`, `43 210 B`, 998 linhas, sha256
`2E7936CB74B2D1E0ABE7251C314E3846D1F9D7053D5D298B09F21FE185C66521` (depois da reparacao
desta lane).

### O que eu encontrei: o oraculo nao estava so por registar -- estava MORTO

Contra o shell vivo, o oraculo morria no PRIMEIRO `Show()` do pywebview:

```
  File "H:\sotto\app\webview\sotto_webview.py", line 4496, in guarded_show
    self.panel_show_refused += 1
AttributeError: 'SottoShell' object has no attribute 'panel_show_refused'
```

O harness constroi o `SottoShell` com `__new__` e semeia os atributos a mao; o shell
ganhou `_gate_form_show`/`panel_show_refused` em 2026-10-07 e o harness nunca acompanhou.
Um oraculo que morre nao e um oraculo: esta area estava duplamente descoberta (sem linha E
sem instrumento a correr).

### A reparacao (edicoes de string exacta, `py_compile` depois de cada uma)

* semeados, tal como o `__init__` real os semeia: `panel_show_refused=0`, `surface='panel'`,
  `surface_applied='panel'`, `panel_mode='strip'`, `panel_visibility=None`,
  `click_watcher=None`;
* `FakeArgs` passa a responder `False` a qualquer flag nao semeada e a REGISTAR o nome -- e
  imprime no fim (`FAKEARGS invented ... none`, medido), por isso o stub nunca e silencioso
  sobre o que inventou;
* `_arm_lazy_gate` em stub (subscreve `WebResourceRequested` no CoreWebView2 e le
  `args.no_lazy`; nao e a decisao de visibilidade).

### Os numeros

```
py -3 _main/panel-hidden-at-startup-oracle.py  -> rc=0, 2.5 s, ORACLE GREEN failures=0
```

* **144 decisoes** de visibilidade (6 cenarios x 3 timings de inicializacao x 8 repeticoes);
* ARMED-ONCE: `NavigationStarting handlers=2` (1 do pywebview + 1 do shell), `visibility_armed=True`;
* WIRING W1-W5 verdes (a guarda e alcancavel de `_on_before_show` SEM passar por
  `CoreWebView2InitializationCompleted`);
* **MUTATION arm** -- a prova de que diz NAO, dentro do proprio ficheiro: `arm-line-deleted`
  (2 falhas de wiring), `guard-never-installed` (3), `pre-fix-shape` (2), todas `caught`; e
  `ticket-repro` `immune` como CONTROL -- o oraculo sabe dizer NAO e sabe distinguir o
  defeito do bilhete do que nao e defeito.

A linha na bateria (`panel hide gate at startup (headless, 4 mutants)`) foi posta pela lane
B, que o mediu DEPOIS da reparacao (144 decisoes, 4 mutantes, rc=0).

---

## RETRACOES E CORRECOES FEITAS DENTRO DESTA LANE (F6: o que nao foi medido diz-se)

1. `surface-loop-panel-oracle.js`: a primeira versao do cabecalho afirmava que o mutante
   M2 (`panel.js`) era INERTE. **Medido: 5/6 RED.** A afirmacao foi retirada no proprio
   ficheiro -- `setSurface()` chama `applySurface()` ele mesmo, portanto a guarda que ele
   perdeu e a que travava o eco. **As duas metades da guarda da pagina sao load-bearing.**
2. O mesmo ficheiro: as duas primeiras versoes do CONTADOR atribuiam o ask da pagina ao
   driver (chave errada). Corrigido para contar pelo despacho do eco; a arm A mede entao
   `pageAsks=2`.
3. O mesmo ficheiro: a primeira copia do mutante era PLANA e nao levava `themes/` -- todos
   os mutantes ficavam RED por um script em falta. Isso e um RED FALSO e foi corrigido
   (copia recursiva) antes de aceitar o resultado.
4. `panel-state-atomic-oracle.py`: o S1 da primeira versao fazia grep ao ficheiro inteiro
   por `path + '.tmp'` e dava **RED FALSO** -- o proprio docstring do shipped CITA essa
   string para explicar porque nao a usa. S1/S2 passaram a ler a AST.
5. O mesmo ficheiro: B3 afirmava "todas as escritas passam", mais forte do que a medicao (o
   retry e limitado: 2 de 100 perdidas sob contenda). Corrigido para o invariante
   estrutural, com o residual REPORTADO.
6. `panel-hidden-at-startup-oracle.py`: a reparacao do harness nao mudou nenhuma decisao do
   produto -- mudou o que o harness SEMEIA, para o objeto falso ter os campos que o codigo
   shipped le.

---

## O VERMELHO QUE NAO E DESTA LANE (N5: nenhum vermelho fica sem atribuicao)

A primeira corrida completa da bateria nesta lane deu **136/137 rc=0**, com UM vermelho:

```
rc=1 !!! photo scrim: 25 themes   VERDICT: FAIL -- these photographs show through enough to compete with the caption
```

Atribuicao medida: `_main/photo-scrim-census.py` esta **modificado na working tree**
(`git status --porcelain` -> ` M _main/photo-scrim-census.py`), e o ultimo commit que lhe
toca e `3927398 O PARSER CORRIGIDO, E O NUMERO VERDADEIRO: 11 temas com scrim 0.62-0.72`. A
corrida isolada imprime `PHOTO-SCRIM 14/25 theme(s) read as a scene; 11 competing` --
exactamente os 11 temas que a mensagem de commit dessa lane nomeia. E trabalho EM VOO de
outra lane (temas/design), no ficheiro dela; **nao foi tocado por mim** e fica para o dono
da area. As 14 linhas que cobrem as seis areas desta lane correm todas rc=0 na corrida final.

---

## NAO MEDIDO (declarado, para nao ser lido mais largo do que e)

* Nada foi lancado: nenhum shell, WebView2, worker ou browser. As perguntas "o que o
  WebView2 pinta" e "o round-trip real pelo bridge" continuam NAO MEDIDAS.
* A metade JS mede os asks da pagina em jsdom, com um stub que imita a resposta do shell; o
  shell real nao foi exercitado por esta via.
* O braco negativo do `caption-independent-oracle.js` (61.8 s) nao esta na bateria.
* A afirmacao de cobertura do `cobertura-oracle` e de INVENTARIO (o nome do instrumento
  aparece na bateria). O token `panel-state` ja casava, antes desta lane, com a linha do
  `panel-state-guard-gate.js` -- que gateia OUTRA propriedade. Foi por isso que o instrumento
  do dump atomico foi escrito e registado, em vez de se aceitar o token.

---

## FICHEIROS DESTA LANE (nomeados; nada de `git add -A`)

| ficheiro | estado | bytes | sha256 (16) |
|---|---|---|---|
| `_main/surface-loop-oracle.py` | NOVO | 14 273 | `8677A8D14CCC9917` |
| `_main/surface-loop-panel-oracle.js` | NOVO | 20 338 | `C8AA1DD8909E46EF` |
| `_main/panel-state-atomic-oracle.py` | NOVO | 20 443 | `FAD28F40CAB55A94` |
| `_main/panel-hidden-at-startup-oracle.py` | EDITADO (harness) | 43 210 | `2E7936CB74B2D1E0` |
| `_main/instruments-battery.mjs` | EDITADO (8 linhas novas) | 17 463 | `7EFEFA4CF3FDE490` |

`app/panel/` e `app/webview/` NAO foram tocados: o `git status --porcelain` desta lane lista
apenas os cinco ficheiros acima (`M` nos dois editados, `??` nos tres novos).

## COMANDOS (para o Lead; nada aqui lanca a app)

```
py -3 _main/cobertura-oracle.py                     # 34/34, 0 GAP, rc=0
node _main/instruments-battery.mjs                  # o total e o rc no topo deste recibo
py -3 _main/surface-loop-oracle.py --neg-arm        # 3/5 verdes, 2 RED
node _main/surface-loop-panel-oracle.js --neg-arm   # M1 5/6 RED, M2 5/6 RED
py -3 _main/panel-state-atomic-oracle.py --neg-arm  # M1 3/9 RED, M2 2/9 RED
py -3 _main/panel-hidden-at-startup-oracle.py       # ORACLE GREEN failures=0
```

