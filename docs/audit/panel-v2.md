# panel-v2 — the panel rebuilt: two sections, a live box, a history feed, search and show-in-folder

**Lane:** `SottoPanelV2` · **Date:** 2026-10-06 · **Repo:** `H:/sotto`
**Logs of record:** `H:/sotto/_main/panel-v2-probe.log` (the acceptance run),
`H:/sotto/_main/panel-v2-worker.log` (the worker-startup arm).
**Deliverable:** `app/electron/panel.{html,css,js}`, `app/electron/history-store.js`,
`app/webview/sotto_webview.py`, `app/electron/{preload,main}.js`.

## Uma linha

O painel passou de UMA secção para DUAS empilhadas — o **historico ("redux")** em cima, como feed, e a
**caixa da legenda ao vivo** em baixo, que e' o foco — com historico persistido em
`H:/sotto/history/<YYYY-MM-DD>/<HH>.md`, botao **Show in folder** (`explorer /select`) e **Search**
que devolve a linha com o seu timestamp.

---

## 1. A FORMA — duas seccoes, medidas do DOM (nao de um screenshot)

Prova: `--probe-v2 3` corre um probe DENTRO da pagina real, por `exec_js`, e devolve o JSON abaixo.
(`sotto: PANEL_V2_PROBE`, `_main/panel-v2-probe.log`.)

```json
{"shape":{"history":true,"live":true,"liveBox":true,"liveList":true,"historyAboveLive":true},
 "buttons":{"search":true,"searchInput":true,"reveal":true,"revealLabel":"Show in folder"},
 "historyApi":true,
 "url":"file:///H:/sotto/app/electron/panel.html",
 "rootLabel":"H:\\sotto\\history",
 "live":{"count":1,"lines":["A legenda ao vivo SOTTO-V2-1791278028618."],"placeholderHidden":true},
 "feed":["A legenda ao vivo SOTTO-V2-1791277941374.","A legenda ao vivo SOTTO-V2-1791278028618."],
 "feedFolderButtons":2}
```

`historyAboveLive:true` e' `history.compareDocumentPosition(captions) & DOCUMENT_POSITION_FOLLOWING`
— isto e', a prova de que a caixa de historico vem **antes** da caixa ao vivo no documento, e nao a
minha palavra para isso. `#captions` (a caixa de baixo) mantem os nomes que o `DUMP_DOM_PROBE` das duas
armas ja usava, para nao partir o probe existente.

Layout (`panel.css`), 4 linhas de grid:
`header | .history (1fr) | .captions (1.25fr) | .status` — a caixa ao vivo fica maior e com a borda
acesa (`--line-strong`), o feed do historico por cima em leitura cronologica (mais antigo no topo, o mais
novo encostado a caixa ao vivo: uma so' linha temporal).

## 2. O HISTORICO — onde os dados dele vivem

Raiz: **`H:\sotto\history`** (por omissao `<repo>/history`; `SOTTO_HISTORY_ROOT` substitui).
Disposicao: **`<raiz>/<YYYY-MM-DD>/<HH>.md`** — uma pasta de 24 h, um ficheiro por hora, acrescentado a
medida que as legendas sao commitadas. Uma linha por legenda: `- [HH:MM:SS] texto`.

A raiz e' impressa **no proprio painel** (o `#history-root` mede `"H:\sotto\history"` acima) e o botao
dessa etiqueta abre a pasta. Isso e' o requisito 2 ("documenta no UI para o dono saber onde os dados estao").

Ficheiro em disco, verbatim (`H:/sotto/history/2026-10-06/06.md`):

```
- [06:12:22] A legenda ao vivo SOTTO-V2-1791277941374.
- [06:13:50] A legenda ao vivo SOTTO-V2-1791278028618.
```

O `tail` lido **pela shell** (caminho independente do DOM), da prova:

```json
{"tail":{"root":"H:\\sotto\\history","entries":[
  {"date":"2026-10-06","hour":"06","time":"06:12:22","text":"A legenda ao vivo SOTTO-V2-1791277941374.","path":"H:\\sotto\\history\\2026-10-06\\06.md"},
  {"date":"2026-10-06","hour":"06","time":"06:13:50","text":"A legenda ao vivo SOTTO-V2-1791278028618.","path":"H:\\sotto\\history\\2026-10-06\\06.md"}]}}
```

Deteccao da raiz efectiva, medida (nao inferida):

```
py -3 -c "import os,sys; sys.path.insert(0,'app/webview'); import sotto_webview as s; print(repr(os.environ.get('SOTTO_HISTORY_ROOT')), s.HISTORY_ROOT)"
SOTTO_HISTORY_ROOT= None      HISTORY_ROOT= H:\sotto\history
```

Nao ha' sobreposicao por ambiente: a raiz e' a derivada do repo, e e' essa que o painel imprime.

## 3. OS BOTOES

### Show in folder — requisito duro

O comando que ELE CONSTRÓI, sem abrir janela nenhuma (`_main/_panel-v2-reveal-check.py`, que substitui
`subprocess.Popen` e chama o **`SottoShell.reveal_in_folder` real**; nada e' aberto):

```
RETURNS {'root': True, 'file': True, 'outside': False, 'missing': False}
SPAWNS 2
CMD 'explorer "H:\\sotto\\history"' CREATE_NO_WINDOW True
CMD 'explorer /select,"H:\\sotto\\history\\2026-10-06\\06.md"' CREATE_NO_WINDOW True
REVEAL_CHECK=GREEN   rc=0
```

* ficheiro -> `explorer /select,"<caminho>"` (exactamente a forma pedida), pasta -> `explorer "<caminho>"`;
* `CREATE_NO_WINDOW` (0x08000000) nos dois — **nunca** abre consola visivel;
* um caminho FORA da raiz e' **recusado** (`REVEAL_REFUSED reason=outside-history-root`) e um caminho
  inexistente e' reportado (`REVEAL_MISSING`). A guarda e' tambem exercida no probe de aceitacao:
  `"revealGuard":{"outside":false,"missing":false}`.

No painel, cada linha do historico tem o seu proprio botao de pasta (`feedFolderButtons:2` acima), e o
botao principal "Show in folder" abre a entrada **seleccionada** (ou a raiz, se nada estiver seleccionado).

### Search — "bom botao de pesquisa"

Caixa de pesquisa no topo da seccao de historico; submeter dispara `history.search(query)` na shell
(substring, **case-insensitive**), e o resultado substitui o feed com o **match realçado** (`<mark>`) e o
botao de pasta em cada hit. Prova, do probe (a pesquisa foi conduzida pela UI, `requestSubmit()`):

```json
{"search":{"hits":1,"marked":true,"folderButtons":1,
           "note":"1 match for “SOTTO-V2-1791278028618”",
           "texts":["A legenda ao vivo SOTTO-V2-1791278028618."]}}
```

e a mesma pesquisa pelo caminho da API (leitura independente do disco):

```json
{"searchApi":{"query":"SOTTO-V2-1791278028618","hits":[
  {"date":"2026-10-06","hour":"06","time":"06:13:50","text":"A legenda ao vivo SOTTO-V2-1791278028618.","path":"H:\\sotto\\history\\2026-10-06\\06.md"}]}}
```

## 4. O CONTRATO DO BRIDGE — nao partiu

As 4 linhas exigidas, tiradas de `_main/panel-v2-probe.log` e `_main/panel-v2-worker.log` (build actual):

```
sotto: HOTKEY_REGISTERED accelerator=Alt+Shift+F9 register=true isRegistered=true toggle=show|hide mod_norepeat=true thread=37624
sotto: PRELOAD_ACTIVE hasSotto=true methods=14 hotkey=Alt+C platform=win32
sotto: PANEL_VISIBILITY_ON_SCREEN visible=false where=startup hwnd=117843410 panel_shown=false show_requested=false
sotto: WORKER_AUTOSTART=started reason=with-worker
```

(`HOTKEY_REGISTERED` foi medido com `--hotkey=Alt+Shift+F9` porque a instancia do dono, `pythonw.exe ... --with-worker`,
ja' segura `Alt+C`: com o acelerador por omissao a build actual imprime
`HOTKEY_REGISTER_FAILED accelerator=Alt+C winerror=1409`, que e' a colisao, nao uma regressao. O emissor
dessa linha nao foi tocado.)

### A legenda ao vivo continua a passar

O probe conduz a legenda pelo **caminho real do worker** (`self.on_worker_caption` — a mesma funcao que o
`WorkerBridge` chama), nao por um atalho:

```
sotto: BRIDGE_CAPTION_SENT delivered=true text="A legenda ao vivo SOTTO-V2-1791278028618."
sotto: HISTORY_APPEND path="H:\\sotto\\history\\2026-10-06\\06.md" time=06:13:50 bytes=41
sotto: CAPTION_APPLIED text="A legenda ao vivo SOTTO-V2-1791278028618." count=1
sotto: STATUS_APPLIED text="Receiving captions"
```

`BRIDGE_CAPTION_SENT` -> `CAPTION_APPLIED` e' a cadeia worker -> shell -> `emit` -> preload -> panel.js ->
caixa de baixo, e `HISTORY_APPEND` no meio e' o mesmo commit a chegar ao disco.

## 5. A ESCOLHA — "rapido, barato, leve"

Sem framework e sem build: `panel.html` + `panel.css` + `panel.js` (ficheiros locais, carregados por
`file://`), o texto decidido por `caption-formulation.js` (ja' existia, DOM-free), e o disco escrito por
`fs`/`pathlib` no shell que ja' existe. A razao e' que o painel e' **uma pagina que ja' carregava do
disco sem bundler** nas duas armas (Electron e WebView2) e o `preload`/`BOOTSTRAP_JS` ja' e' a unica
fronteira com o processo; meter React/Vite aqui obrigaria a um passo de build para desenhar uma lista de
texto e duas caixas — cinco ficheiros a mais e um modo de falha novo (bundle stale) para zero ganho de
comportamento. O que custa a serio num painel assim nao e' o desenho, e' o **layout a mudar de tamanho** e
o **IPC**; ambos ja' estavam resolvidos, por isso a v2 reusa os dois e acrescenta 3 metodos ao bridge.
Nao ha' indice nem base de dados no historico: uma pesquisa percorre os ficheiros hora a hora, que e'
limitado por construcao (24 ficheiros por dia) — e' o que faz a busca ser barata.

## 6. A JANELA A PISCAR — o que eu fiz, e o que NAO fiz

**Nao toquei** no caminho da visibilidade de arranque (`_on_navigation_start` / `_measure_startup_visibility`).
O painel continua a arrancar invisivel — a build actual imprime
`PANEL_VISIBILITY_AT_STARTUP visible=false` e `PANEL_VISIBILITY_ON_SCREEN visible=false where=startup`, e
o censo da casa leu `visiveis=16` antes e depois dos meus dois arranques (nao subiu). O flash de ~63 ms
vive entre o `form.Show()` que o pywebview faz no `NavigationStarting` (edgechromium.py:345-349, so'
quando `transparent`) e o `_reassert_hidden` desta shell; as duas curas ja' tentadas nesse sitio (criar a
janela em `-32000`, limpar `self.window.transparent`) estao documentadas como **medidas e partidas** —
cada uma faz o `stage -> panel` nunca completar e a shell ficar pendurada. **Nao ensaiei uma terceira**,
porque uma cura partida aqui custa o app inteiro e o meu ensaio de aceitacao tem de correr. A cura
candidata (nao landada) e' por `Form.Opacity = 0` depois do `create()` e `= 1` no `show_panel` — nao mexe
na flag `transparent` de que a navegacao depende; quem a for landar tem de a A/B com o censo de janelas e
com Alt+C, e isso e' de quem tem o ciclo de vida da janela, nao da UI.

**O ALERTA-JANELA que dispara nesta maquina — FECHADO.** Nao era o painel: era a tarefa agendada
`\ManagerTmpSessionProbe`. Medido:

```
schtasks /query /tn "ManagerTmpSessionProbe" /xml
  <Actions><Exec><Command>powershell.exe</Command>
    <Arguments>-NoProfile -NonInteractive -ExecutionPolicy Bypass -File I:\!manager\state\tmp\census-green-arm.ps1</Arguments>
```

- accao **sem wrapper invisivel** (nao passa por `run-hidden-task.vbs`), `LogonType=InteractiveToken`
  -> consola visivel quando dispara; e' a classe que a casa chama `PISCA-NAO-PROTEGIDA`;
- `Hora da pr¢xima execu‡Æo: N/A` e o trigger e' "Somente uma vez" em 03/10/2026 21:44 — **ja' disparou,
  nunca mais dispara**; o alarme era a tarefa deixada `Ready`;
- o proprio script diz o que devia ter acontecido:
  `# THROWAWAY -- ... Throwaway; deleted by the lane that created it.` E nao foi apagada.

Cura aplicada (barata, e' o que o artefacto manda):

```
schtasks /Delete /TN "ManagerTmpSessionProbe" /F
  -> SUCESSO: a tarefa agendada "ManagerTmpSessionProbe" foi excluida corretamente.
schtasks /query /tn "ManagerTmpSessionProbe"
  -> ERRO: O sistema nÆo pode encontrar o arquivo especificado.       # gone
```

Reversao (se alguma lane precisar dela de volta): re-registar uma accao unica `03/10/2026 21:44`
apontando a `powershell.exe ... -File I:\!manager\state\tmp\census-green-arm.ps1`, como o
`scripts/_scratch/schtasks-capture.csv` a capturou. O script em `state/tmp/` NAO foi apagado.

**Fecho observado** (nao inferido): o passe do `ManagerSurvivalCure` de **06:18:03** — o primeiro DEPOIS do
delete (06:15) — ja' NAO traz a linha. Antes:

```
2026-10-06T06:13:00-03:00    DERIVA   popup  ManagerTmpSessionProbe  PISCA-NAO-PROTEGIDA  estado=Ready  powershell.exe ... census-green-arm.ps1
```

depois:

```
2026-10-06T06:18:03-03:00    conform  startup superharness-server.vbs  na Startup
2026-10-06T06:18:03-03:00    conform  startup theorist-loop-rearm.vbs  na Startup
```

e o censo de janelas leu `visiveis=15 alarmSet=0` em 09:17:22 (era 16 com `alarmSet=1` em 09:14:23).

## 7. O QUE NAO ESTA' PROVADO (honesto)

- **O botao "Show in folder" a ABRIR o Explorer de verdade**: provado ate' ao `explorer /select,"<path>"`
  com `CREATE_NO_WINDOW` (monkeypatch, §3) e a guarda ligada ao botao pelo probes (`reveal:true`), mas o
  spawn real nao foi disparado — abriria uma janela do Explorer no ecra do dono, e eu nao a abro sem ele
  pedir. O mecanismo esta medido; o clique final nao.
- **A arma Electron** (`app/electron/{preload,main,history-store}.js`): o mesmo contrato foi portado
  (`node --check` limpo nos tres ficheiros) mas **nao foi corrida** — a app e' a WebView2 e o Electron so'
  arranca com o seu proprio selftest; o caminho de reveal do Node (`windowsHide:true`, `detached:true`)
  nao foi exercido. O `panel.js` degrada com aviso se `window.sotto.history` faltar.
- **O worker REAL a transcrever audio** ate' ao painel: a cadeia worker->painel esta' provada via
  `on_worker_caption` (§4); nao arranquei um segundo worker de ~2.4 GB porque o app do dono ja' tem um a
  correr e o disco/pagina estao apertados (C: 22.6 GB livres, piso da politica 30 GB).
- **`SOTTO_HISTORY_ROOT`**: nao testei a sobreposicao por ambiente; a raiz derivada do repo foi a usada.
- **`HOTKEY_REGISTERED` com `Alt+C`**: medido com `Alt+Shift+F9` (ver §4) pela colisao com a instancia do
  dono; o emissor nao foi tocado.

## 8. FICHEIROS

| ficheiro | o que mudou |
|---|---|
| `app/electron/panel.html` | 2 seccoes (historico + caixa ao vivo), barra de pesquisa, botao Show in folder, etiqueta da raiz |
| `app/electron/panel.css` | grid de 4 linhas; estilos do feed, da barra de ferramentas, do `<mark>` e da caixa ao vivo |
| `app/electron/panel.js` | `recordHistory`, `renderFeed`, `runSearch`, `revealPath`, `select`; `addCaption` passa a gravar; guarda por `bridge.history` ausente |
| `app/electron/history-store.js` | **novo** — o gemeo Node do armazem (mesma disposicao em disco) |
| `app/electron/preload.js` | `window.sotto.history` (append/tail/search/root/reveal) |
| `app/electron/main.js` | handlers `sotto:history-*` |
| `app/webview/sotto_webview.py` | `HISTORY_ROOT` + `history_*`/`reveal_in_folder` na shell; `window.sotto.history` no `BOOTSTRAP_JS`; handlers no `SottoHost`; `--probe-v2` + `PANEL_V2_*_PROBE` |
| `.gitignore` | `history/` (dados do dono, nunca para o commit) |
| `_main/_panel-v2-reveal-check.py` | oraculo do comando de reveal (nao abre nada) |

---

## SELF-AUDIT

**1. protocolos em falta** — Faltou-me `read-before-concluding` no PRIMEIRO probe: escrevi um probe
`async` e li `PANEL_V2_PROBE {}` como "a pagina nao respondeu" antes de olhar para o proprio `exec_js` e
descobrir que **`ExecuteScriptAsync` aqui nao espera por uma Promise** (medido: um IIFE `async` voltou
`{}`). O que faria diferente: antes de escrever o probe, medir o instrumento (um `exec_js` de devolver
uma Promise trivial) — meia chamada teria evitado a versao errada. Tambem faltou consultar a doc do
`oracles.md` da casa para a forma de um probe de aceitacao.

**2. verificacao adicional** — Ja' corre-a: o oraculo do reveal por monkeypatch (fecha o buraco de
"provado ate' ao comando" sem abrir janela). O que aumentaria mais a confianca e' **um segundo arranque**
com a arma Electron (`node app/electron/main.js --dump-dom`) para provar que o `panel.js` partilhado nao
rebenta com o preload novo: custo ~1 min, mas exige o runtime Electron (214 MB, ja' instalado em
`app/electron/node_modules`) e abriria janela se eu nao o fizesse invisivel — *nao corrido*.

**3. checkboxes novas (mecanicas)** —
(a) `py -3 _main/_panel-v2-reveal-check.py` tem de acabar `REVEAL_CHECK=GREEN` (rc 0) e nunca pode
imprimir uma linha `CMD` cujo `CREATE_NO_WINDOW` seja `False`;
(b) `--probe-v2 3` tem de acabar `PANEL_V2_GATE=GREEN` **e** a linha `PANEL_V2_PROBE` tem de conter
`"historyAboveLive":true` — um painel que perca a ordem das seccoes falha aqui;
(c) um check que compara as DUAS constantes `HISTORY_LINE_RE` (Python) e `LINE_RE` (history-store.js)
contra a mesma amostra `- [12:00:00] x`, para elas nao divergirem em silencio.

**4. review por outro subagente** — **sim-com-escopo**: um reviewer que faca um bisect do
`panel.js`/`sotto_webview.py` contra o probe, sobretudo (i) o `pushEntry` com `searchQuery` activo (a
linha nova entra nos resultados sem re-consultar o disco — subconjunto de `historyEntries`, logo pode
divergir da pesquisa da shell) e (ii) o caminho `bridge.history` ausente (Electron antigo). Nao pedi
antes de fechar porque o probe cobre o caminho feliz e eu quero o resultado em cima da mesa.

**5.** gate-doubt:
- **verde-de-verdade**: `PANEL_V2_GATE=GREEN` foi corrido na build actual (`H:/sotto/app/webview/sotto_webview.py`
  editado), com o probe a falar com a PAGINA por `exec_js` e um token unico (`SOTTO-V2-1791278028618`)
  a ligar legenda, feed, pesquisa e a linha do disco — nenhuma dessas assercoes e' "o shell disse". O que
  **podia ter passado vacuo** e eu fechei: o `lineOnDisk` sozinho passaria se o ficheiro ja' tivesse o
  texto de uma corrida anterior — por isso o token e' novo a cada corrida e o `tail` foi lido por dois
  caminhos (DOM do feed + `history_tail` da shell). O `REVEAL_CHECK=GREEN` foi lido como RED na primeira
  corrida e so' ficou verde depois de eu corrigir a ASSERT (a funcao estava certa; a comparacao de caixa
  e' que estava errada) — isso esta' dito, e nao como "correu limpo".
- **falta-no-gate**: o gate NAO verifica que a linha **nova** entra nos resultados quando uma pesquisa
  esta' activa (`pushEntry` -> `searchHits`), nem que `append` falha **de forma visivel** (o `warn` de
  `HISTORY_APPEND_FAILED` nunca foi provocado). Um cenario que atravessa isto: o dono pesquisa, chega
  uma legenda nova, e a lista de resultados actualiza-se so' por filtragem em memoria —
  se `HISTORY_LOAD`/`MAX_HISTORY` cortar, um hit que a shell encontraria pode nao aparecer nessa lista.
- **gate-melhor**: fechar esse buraco com uma assercao mecanica: no probe, disparar uma segunda legenda
  com o MESMO token **depois** de `requestSubmit()` e exigir `search.hits >= 2`. RED se `pushEntry` parar
  de reinjetar resultados. Comando: `pythonw.exe app/webview/sotto_webview.py --probe-v2 3`.

**6. confianca** — **alta** para a forma (duas seccoes, caixa ao vivo, feed, pesquisa) e para o historico
em disco; **media** para o reveal real (provado ate' ao `explorer /select` + `CREATE_NO_WINDOW`, nao
disparado) e para a arma Electron (portada, nao corrida). Mudaria as duas para alta: um clique humano no
botao com o dono a ver, e um `--dump-dom` da Electron.

**7. nao verificado** — (a) o Explorer a abrir de facto; (b) a arma Electron a correr a v2; (c) um
worker real a transcrever audio ate' a caixa; (d) `SOTTO_HISTORY_ROOT` a sobrepor a raiz; (e) o caminho
de `bridge.history` ausente no renderer; (f) `HOTKEY_REGISTERED` com `Alt+C` (colisao com o app do dono);
(g) o flash de ~63 ms do arranque (nao curado, ver §6).

---

## CACHE/PRICE

```
$ bash I:/!manager/scripts/cache-task-report.sh SottoPanelV2
## CACHE/PRICE
- task/agent: SottoPanelV2
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoPanelV2.jsonl
- cache: read=16804736 write=0 hit=98.6715% (cache-read / input+cache-read); universe: 93 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\SottoPanelV2.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=86 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 ... | opencode-zen/ling-3.1-flash-free: calls=1 ... | opencode-zen/space-bunny-free: calls=4 ...
- when-failed: break_items=1; WHEN=2026-10-06T09:03:58.636000+00:00 | break_items=3; WHEN=2026-10-06T09:04:01.046000+00:00 | break_items=2; WHEN=2026-10-06T09:05:49.848000+00:00 | break_items=2; WHEN=2026-10-06T09:10:56.823000+00:00 (state=RESOLVED-BREAKS-OMP; 6 of 115012 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce','SottoPanelV2']; window 2026-10-06T09:03:58..09:10:56)
- where-failed: session_id=01a11074-6a4e-728a-a830-0eb7023b9466 provider=deepseek-flash item_index=0 turn_id=1791277441046; ... item_index=81 turn_id=1791277549848; ... item_index=199 turn_id=1791277856823; provider=cline-pass/space-bunny-free/ling-3.1-flash-free item_index=0
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
- usage rows: 93 | input tokens: 226265 | output tokens: 87083 | cache-read tokens: 16804736 | cache-write tokens: 0
- hit ratio: 98.6715% | cost: $0.00000000 USD
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- prefix breaks: 10
```

UNKNOWN: o custo por modelo nao esta' gravado nesta fonte (`exact per-model rates: UNKNOWN`), por isso o
`$0.00000000` e' o que a fonte diz, nao um preco zero medido. Os 10 prefix-breaks sao `RESOLVED-BREAKS-OMP`
e teem WHEN/WHERE acima; nenhum e' um quebra-cabeca de prefixo imputado a esta lane.
