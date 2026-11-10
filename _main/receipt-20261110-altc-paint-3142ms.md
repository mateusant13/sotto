# Alt+C: os 3 142 ms entre o `HOTKEY_COALESCED` e a pintura do painel

Sessao do dono: `2026-11-10 09:33:51.565` (`_main/webview-run.log`).
Instrumento: `python _main/boot-interaction-oracle.py`.
Veredicto desta lane: **fixed, NOT verified** — o defeito esta' nomeado e o conserto
esta' no sitio, mas nenhuma sessao nova com este codigo foi aberta nesta arvore, e
`verified` sobre a sessao dele e' impossivel daqui (o log e' dele; nao se forja uma
sessao). O que NAO esta' medido esta' na ultima seccao.

---

## 1. O numero que se partiu, e onde se parte

```
HOTKEY_PRESSED role=panels count=1 accelerator=Alt+C thread=43620   09:34:13.049
HOTKEY_COALESCED presses=1 from=hidden/- to=visible/strip steps=1 transitions=1   09:34:13.054   (+5 ms)
HOTKEY_TOGGLE step=show surface=strip                               09:34:13.054
STRIP_HEIGHT from=148 to=40 source=css css_value=40 reason=posted-hotkey-cycle-strip   09:34:13.275  (+221)
STRIP_WIDTH from=None to=380 ... reason=posted-hotkey-cycle-strip    09:34:13.846   (+571)
WINDOW_GEOMETRY reason=strategic-panel-culled ...                    09:34:13.849
CAPTION_OVERLAY_THEME applied                                         09:34:13.834
WEBVIEW_CHILD shown=0 already=5 failed=0                             09:34:14.616  (+1167)
PANEL_CONTENT ... wait_ms=594.0 why=applied order=before-map         09:34:14.623  (declarou 250)
PAINT_ACK ack=false wait_ms=500.0 why=timeout                         09:34:15.211  (declarou 400)
PANEL_SHOWN ... content_ack=false wait_ms=500.0                      09:34:16.196
WINDOW_GEOMETRY reason=metrics-hotkey-cycle-strip (380x148 -> 380x40) 09:34:14.436  (segundo resize)
```

`PANEL_SHOWN` — `HOTKEY_COALESCED` = **3 142 ms**; o declarado e' `wait_ms=500`
e `content_wait_ms=594` (gate). Despacho medido: **5 ms**. Portanto o custo nao
esta' no hook nem no gesto: esta' no caminho do show.

### As linhas que gastam o tempo (todas em `app/webview/sotto_webview.py`, ANTES)

| # | linha (antes) | o que ela fazia no meio do show | custo no log dele |
|---|---|---|---|
| 1 | `_post_metrics_refresh()` — o `_worker` comeca com `self.refresh_strip_height(...)` sem espera (agora `:20247`) | **duas (3) idas ao UI thread** para re-medir a faixa, disparadas no INSTANTE da pressao, a competir com as perguntas do proprio show | `STRIP_HEIGHT` 13.275, `STRIP_WIDTH` 13.846, `WINDOW_GEOMETRY reason=metrics-…` **14.436** = um **segundo resize da janela** a meio do show |
| 2 | `content_gate(self, reason, surface=None)` (agora `:14510`) | orcamento **proprio** de 250 ms, independente do show | declarou 250, gastou **594** |
| 3 | `wait_paint_ack(self, seq, reason)` (agora `:14452`) | orcamento **proprio** de 400 ms, independente do show | declarou 400, gastou **500** |
| 4 | `_hotkey_resolve` -> `show_strip(reason)` / `show_side(reason)` (agora `:16330`, `:16427`, `:16518`) | nenhum relogio do show atravessava o caminho; `PANEL_SHOW_COST` existia so' no `show_panel`, que a tecla NAO usa | nenhum numero por pedaco em 3 142 ms |
| 5 | `_warm_paint` (agora `:16341`) | aquecia a pintura, mas **nao** os tres numeros que o primeiro Alt+C ia buscar a' pagina | o primeiro Alt+C de um processo pagava-os (linhas 1) |

[INFERENCE] A divisao fina entre "fila do UI thread" e "o `_worker` postado" nao e'
medivel no log (os dois escrevem a mesma linha `reason=posted-…`): o que o log
PROVA e' a ordem (o `WINDOW_GEOMETRY reason=metrics-…` em 14.436 cai DENTRO do
intervalo do show) e o que o log PROVA por declaracao-e-resultado (gate 250->594,
ack 400->500).

---

## 2. O conserto (mesmo ficheiro, DEPOIS)

1. **Um orcamento so', `SHOW_BUDGET_MS`** — `:431` (`SHOW_BUDGET_S` em `:435`). O
   relogio nasce na linha que o oraculo usa como origem, `_hotkey_resolve`
   `:16330`, e atravessa `show_strip`/`show_side`/`show_panel` (`deadline=`) e,
   delas, `content_gate` e `wait_paint_ack`.
2. **`wait_paint_ack(..., deadline=None)`** `:14452` — recebe so' o que resta; sem
   orcamento **nao pergunta** e diz `why=show-budget-spent` (`:14475`). O ack nunca
   mais pode gastar 500 ms num show de 400.
3. **`content_gate(..., deadline=None)`** `:14510` — `budget = max(retry_min,
   min(250 ms, deadline - agora))` `:14557-14565`; a linha `PANEL_CONTENT` passou a
   publicar o orcamento REAL usado (`timeout_ms=%.1f`, antes imprimia a constante).
4. **`_post_metrics_refresh`** `:20247` — `time.sleep(PAINT_METRICS_DELAY_S)` =
   `:442` (0,35 s) antes das duas re-medicoes: as idas ao UI thread deixam de entrar
   na fila do show. O numero adoptado continua a chegar antes de o dono olhar.
5. **`PAINT_WARM_METRICS`** `:16395-16422` — `_warm_paint` (que corre no arranque,
   **com a janela fora do ecra**, `PAINT_WARM ... visible=false`) passa a preencher
   `strip_height_css`, `strip_width_dom` e `_strip_offset_cache` logo depois de a
   pagina ter pintado. O primeiro Alt+C deixa de pagar as tres leituras: o custo
   MUDOU DE SITIO, para o arranque, que e' exactamente a ordem do dono ("a
   performance … tem que comecar a partir do momento que o app abre").
6. **`PANEL_SHOW_COST` nas duas superficies da tecla** `:16499` (`mode=strip`),
   `:16583` (`mode=side`): `surf_ms arm_ms gate_ms map_ms ack_ms total_ms
   budget_ms`, escrito na linha ANTERIOR ao `PANEL_SHOWN` (o `total_ms` cobre o
   mesmo intervalo que o oraculo mede — um custo medido noutro ponto passaria a
   mentir por omissao). Antes so' o `show_panel` (bandeja / `--show`) tinha isto.

**Orcamento declarado: 400 ms** (`SHOW_BUDGET_MS`), o mesmo prazo que
`paint-live-show` ja' exige da pintura. Nao foi aumentado; o que passou a existir foi
um TECTO na SOMA (gate e ack recebem o que resta, nao cada um o seu tecto).

---

## 3. As armas, com o antes e o depois, verbatim

### 3.1 `python _main/boot-interaction-oracle.py` (o log dele, sessao antiga)

Antes e depois, IDENTICO — nao ha' sessao nova:

```
alt-c 1o: despacho                21484        5.0      400  PASS  to=visible/strip presses=1
alt-c 1o: pintura                 21489     3142.0      400  FAIL  content_ack=false wait_ms=500.0
alt-c pior total                  24835     5241.0      400  FAIL  cadeia #2, despacho 2215 + pintura 3026
ctrl+space primeiro toggle        20076      212.0      400  PASS  on=false
bandeja: pior menu_ms                 -     5063.0      200  FAIL  n=13 ok=0 em 13
arranque -> 1a legenda                -     1856.0    15000  PASS
VERDICT: FAIL -- medidas=6 falhas=3 nao-medidas=0
rc=1
```

A linha `bandeja` e' de outra lane (`TRAY_MENU_FOREGROUND`, do peer da bandeja), nao
desta.

### 3.2 A arma NOVA da pintura, `--paint-arm` (dois ficheiros de FORMA)

Ficheiros acrescentados (o pedido: a fixture vai para `_main/fixtures/`):

- `_main/fixtures/boot-interaction-altc-paint-slow.log` — a forma do log DELE:
  pintura 3 142 ms, `content_ack=false wait_ms=500`, sem `PANEL_SHOW_COST`.
- `_main/fixtures/boot-interaction-altc-paint-fast.log` — a forma CURADA: as cinco
  parcelas publicadas e `total_ms=364` (a soma das parcelas, `surf 44 + arm 96 +
  gate 48 + map 145 + ack 31`).
- a MUTACAO nao e' um terceiro ficheiro: `_uncure()` (`boot-interaction-oracle.py`)
  APAGA o `PANEL_SHOW_COST` do log curado e empurra o `PANEL_SHOWN` 3 142 ms para a
  frente do `HOTKEY_COALESCED` — "a cura desfeita".

`python _main/boot-interaction-oracle.py --paint-arm` (rc=1):

```
paint-arm RED fixture=boot-interaction-altc-paint-slow.log rc=1 verdict=FAIL alt-c 1o: pintura=3142.0 budget=400
paint-arm GREEN fixture=boot-interaction-altc-paint-fast.log rc=0 verdict=PASS alt-c 1o: pintura=364.0 budget=400
paint-arm MUTACAO fixture=mutacao-do-consero rc=1 verdict=FAIL alt-c 1o: pintura=3142.0
PAINT-ARM: PASS -- red=FAIL green=PASS mutacao=FAIL
```

A arma exige TRES coisas, e falha em qualquer uma: (a) a forma dele e' RED na linha
da pintura e acima de 400 ms; (b) a forma curada e' GREEN **e** publica
`PANEL_SHOW_COST` com as cinco parcelas cuja soma e' o `total_ms` (sem essa linha o
log e' o log ANTIGO, e um oraculo que o aceita nao mede o que foi curado); (c) a
mutacao da cura volta a RED.

### 3.2b A arma POSITIVA — `rc=0`, o log de forma CURADA

```
python _main/boot-interaction-oracle.py --log _main/fixtures/boot-interaction-altc-paint-fast.log
alt-c 1o: despacho                21484        5.0      400  PASS  to=visible/strip presses=1
alt-c 1o: pintura                 21489      364.0      400  PASS  content_ack=true wait_ms=31.0
alt-c pior total                  21484      369.0      400  PASS  cadeia #1, despacho 5 + pintura 364
ctrl+space primeiro toggle        20076      212.0      400  PASS  on=false
bandeja: pior menu_ms                 -       41.0      200  PASS  n=1 ok=0 em 0
arranque -> 1a legenda                -     1856.0    15000  PASS
VERDICT: PASS -- medidas=6 falhas=0 nao-medidas=0
rc=0
```

(O mesmo comando sobre o log DELE devolve rc=1 — sec. 3.1: a sessao antiga esta' no
log dele, e o instrumento nao a reescreve. As duas corridas lado a lado sao a prova
de que o red/green desta arma vem da FORMA do show, e nao de um numero escolhido.)

### 3.3 `python _main/boot-interaction-oracle.py --neg-arm` (rc=1 = pegou)

```
PASS G a sessao rapida tem de dar PASS (rc=0, esperado 0)
PASS R1 Alt+C a 2000 ms tem de dar FAIL (rc=1, esperado 1)
PASS R2 Ctrl+Space a 900 ms tem de dar FAIL (rc=1, esperado 1)
PASS R3 bandeja a 800 ms tem de dar FAIL (rc=1, esperado 1)
PASS R4 primeira legenda a 40 s tem de dar FAIL (rc=1, esperado 1)
PASS R5 um log sem sessao tem de dar SKIPPED (rc=3) (rc=3, esperado 3)
...
PASS R6 pintura dos ficheiros de forma tem de pegar red+mutacao (rc=1, esperado 1)
NEG-ARM: PASS -- 7/7 casos
rc=1
```

### 3.4 `python _main/paint-live-show-oracle.py` (o outro instrumento do show)

Sobre o log dele: **rc=0**, e o veredicto e' SKIPPED porque o processo vivo e' de
codigo ANTERIOR (`LIVE_CODE STALE`):

```
PAINT-LIVE processo=STALE (LIVE_CODE STALE log=H:\sotto\_main\webview-run.log)
PAINT-LIVE arranque=2026-11-10 09:33:51.565 warm=1 ack=1 conteudo=2 conteudo_ack=0 shows=2 max_wait_ms=500.0 max_content_wait_ms=594.0 ...
PAINT-LIVE VERDICT: SKIPPED (processo STALE -- a evidencia e' do codigo anterior; o proximo arranque a julga)
rc=0
```

Sobre a forma curada (o ficheiro verde), que e' a arma positiva desse instrumento,
**PASS/rc=0** com `max_wait_ms=31.0`, `max_content_wait_ms=48.0` (o tecto dele e'
400):

```
PAINT-LIVE ... conteudo_ack=1 shows=1 max_wait_ms=31.0 max_content_wait_ms=48.0 total_p50_ms=79.0 ...
PAINT-LIVE VERDICT: GREEN
rc=0
```

E o `--neg-arm` dele: **19/19, PASS, rc=1**. Isto EXPOS uma coisa que este conserto
partiu e que ficou consertada: `_source_map_first()` procurava a linha
`content = self.content_gate(reason, self.surface_applied)` LITERAL; como a chamada
passou a levar `deadline=deadline`, o mutante deixou de encontrar a linha, ficou
igual ao original e o braco publicava `GREEN NOT-CAUGHT` (19 casos, 18 apanhados —
medido). O mutante passou a seguir a chamada por PADRAO
(`paint-live-show-oracle.py:459-488`), e a classe voltou a estar coberta:

```
  fonte-mapa-antes-do-gate           -> RED      RED-as-required  show_panel: o mapa (`show_without_activating(self.hwnd)`) vem ANTES do gate -- a janela ap
NEG-ARM cases=19 caught=19
NEG-ARM PASS
rc=1
```

---

## 4. O que NAO esta' medido (a lacuna, sem enfeite)

- **Nenhuma sessao nova com este codigo foi aberta.** O `3 142 -> ?` do primeiro
  Alt+C numa app recem-aberta NAO foi observado; a prova e' aritmetica + de forma:
  a soma do show passa a ser limitada por um unico relogio de 400 ms, e as tres
  leituras que ele pagava passaram para o arranque.
- **O custo que MUDOU DE SITIO nao foi cronometrado**: `PAINT_WARM_METRICS` paga
  `refresh_strip_height` + `refresh_strip_width` + `_strip_offset` no arranque
  (`PAINT_WARM ... visible=false`), a seguir ao ack da primeira pintura. Quantos ms
  isso acrescenta ao arranque desta maquina esta' por medir; e' trabalho FORA do
  ecra, e o dono nao espera por ele, mas "nao e' zero" nao esta' quantificado.
- **A divisao fina dos 2,6 s fora das esperas declaradas** (UI-thread queue vs. o
  `_worker` postado) e' `[INFERENCE]`; o log prova a ordem e a sobre-duracao de cada
  espera, nao a atribuicao ao microssegundo.
- **O segundo resize** (`WINDOW_GEOMETRY reason=metrics-hotkey-cycle-strip`, 14.436)
  deixa de acontecer por construcao (a cache vem quente do arranque e
  `refresh_strip_*` devolve `False` quando o numero nao mudou), mas tambem nao foi
  observado a desaparecer numa sessao nova.
- `python _main/paint-live-show-oracle.py` sobre o log vivo responde rc=0 por
  SKIPPED (processo STALE), nao por PASS. Um PASS real exige um arranque novo.

## VOLUME: o commit desta cura foi recusado pelo DISCO, e o evac foi revertido

Medido, nao inferido, com o mesmo `shutil.disk_usage('H:/')` nas duas pontas:

| quando | H: livre | o que aconteceu |
|---|---|---|
| 2026-11-10 ~14:0xZ | **0.000 GiB** | `git commit` morreu em `fatal: sha1 file 'H:/sotto/.git/index.lock' write error. Out of diskspace`; na mesma janela o `run-all` recusou `compose-probe` e `keyframe-shape-probe` com `instant replay refused` |
| ~14:5xZ | **18.26 GiB** | medido de novo, sem eu ter apagado nada de ninguem |

O evac de emergencia (113 MiB: `_main/_tmp-panel-noreveal` + `_main/_design-lane` movidos para
`I:\cc-tmp\sotto-evac-20261110\`) foi **REVERTIDO**: o `_design-lane` nao e' copia temporaria -- o
`shots-delta-oracle` LE-O (`_main\shots-delta.py`, `_main\intake-shots.py`) e o
`_border-radius-probe.py` poe-no no `sys.path`. Movê-lo teria partido dois passos da bateria para
poupar 86 MiB. Verificado depois de devolver os dois directorios:
`python _main\shots-delta-oracle.py` -> `VERDICT: PASS  arms 19/19  mutants 11/11`, rc=0.

**A atribuicao do volume, para a afirmacao "o disco esta' cheio" nao virar folclore.** Walk
completo de `H:\` por directorio de topo (`os.scandir`, 2026-11-10): **487.84 GiB** andados.
Os maiores nao sao deste projecto: `@@@@IA` 87.97 GiB · `jcode-target-gnu` **86.96 GiB** (um
directorio de build) · `Riot Games` 50.67 · `SteamLibrary` 36.32 · `env` 27.98 ·
`VOD.RIP-data` 20.46 · `codeintel` 19.96 · `deteccaoaudiodoppler` 19.00 · `ComfyUI` 16.96.
`H:\sotto` = **8.74 GiB** (`.git` 4.79 · `_main` 2.21 · `worker` 1.21).

O que isto muda na afirmacao: um commit meu **pode** morrer por ENOSPC num volume que nao e'
meu, e o sintoma aparece em DOIS sitios que parecem do produto (`instant replay refused` no
portao, `index.lock` no git). A regra que fica: ler o `disk_usage` do volume ANTES de acusar um
instrumento, e nunca apagar evidencia de outro projecto para passar um commit.

**O que o vaivem custou, dito inteiro.** O primeiro `mv` de ida e volta do `_tmp-panel-noreveal`
perdeu os ficheiros IGNORADOS daquela copia (`node_modules`, ~2 674 ficheiros / ~20 MiB); o
conteudo versionado foi recuperado do indice e esta' **inteiro**: `git ls-files` = 88, em disco =
88, `git status` do caminho = 0 entradas. Nada de `_design-lane` se perdeu (3 129 ficheiros) e o
seu oraculo da' PASS. Licao curta: **um `mv` entre volumes nao e' atomico** -- um directorio que
interessa ao repo nao se evacua para "ganhar espaco", porque `git checkout` devolve o que e'
versionado e NAO devolve o que e' ignorado.
