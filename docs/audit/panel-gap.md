# panel-gap — a lacuna do painel: AUDITADA, e ela NAO EXISTE

**Lane:** `SottoPanelGap` · **Date:** 2026-10-06 · **Repo:** `H:/sotto`
**Alvo:** `app/electron/panel.{html,css,js}` + leitura do contrato em `app/webview/sotto_webview.py`
**Logs de registo (desta corrida):** `_main/panel-gap-probe.log` (o `--probe-v2`, corrido por mim),
`_main/panel-gap-visibility.log` (o oraculo de visibilidade), `_main/_panel-gap-visibility.py` (o oraculo).
**Nada foi editado em `panel.html`, `panel.css`, `panel.js`, `sotto_webview.py` nem em `worker/`.**

## 0. Veredicto em uma linha

A premissa do brief e' **FALSA**, e a prova e' o proprio instrumento do brief:
`grep -c hist__folder app/electron/panel.html` = **0** e' VERDADE — e e' **vazio**, porque
`.hist__folder` e' um elemento **criado em runtime pelo `panel.js`** (`panel.js:367`,
`folder.className = 'hist__folder'`), e um nome gerado em JS **nunca pode** aparecer no HTML estatico.
Medido na pagina real: **36** botoes `.hist__folder`, **`search.marked:true`**, e a geometria de ambos
(24x18 e 165x34 px, `visibility:visible`, `opacity:1`). Nao ha' lacuna a fechar; ha' um instrumento de
auditoria errado, e isso esta' na §6 como RECOMENDACAO.

---

## 1. A AUDITORIA (o criterio) — o que o Python consulta vs o que o painel renderiza

Metodo: todo selector que `sotto_webview.py` passa a `getElementById`/`querySelector(All)`, contra o
`grep -c` do token em `panel.html` e `panel.js` (mesmo metodo do brief, o token nu). **O `panel.css` nao
conta elementos** — so estiliza — por isso nao prova presenca.

| selector (o Python consulta) | linha no `.py` | `panel.html` | `panel.js` | quem renderiza |
|---|---|---|---|---|
| `#panel` | 902 | 1 | 0 | html |
| `.panel__header` | 871 | 1 | 0 | html |
| `.wordmark` / `.wordmark__name` | 871-873 | 5 / 1 | 0 | html |
| `#clear-button` | 873 | 1 | 1 | html |
| `.status` / `#status` / `#status-text` | 873/920/910 | 1/1/1 | 0/0/1 | html |
| `#placeholder` | 927 | 5 | 15 | html |
| `.captions__placeholder-title` | 928 | 1 | 2 | html |
| `.captions__placeholder-body` | 929 | 1 | 2 | html |
| `#captions` / `#captions-body` | 955/961 | 1/1 | 1/1 | html |
| `#caption-list` | 936 | 1 | 1 | html |
| `#caption-list .caption__text` | 992 | **0** | 3 | **js** (`makeCaption`) |
| `#history` | 954 | 20 | 70 | html |
| `#history-root` | 998 | 1 | 1 | html |
| `#history-status` | 1014 | 1 | 1 | html |
| `#history-list` | 989-1013 | 1 | 1 | html |
| `#history-list .hist__text` | 996 | **0** | 3 | **js** (`makeRow`) |
| `#history-list .hist__folder` | 997 | **0** | 1 | **js** (`makeRow:367`) |
| `#history-list .hist` | 1011 | 0 | 1 (`li.className='hist'`) | **js** |
| `#history-list mark` | 1013 | 0 | 1 (`document.createElement('mark')`) | **js** |
| `#search-form` / `#search-input` / `#search-button` | 989/970/969 | 1/1/1 | 1/1/1 | html |
| `#reveal-button` | 971 | 2 | 1 | html |

**Leitura da tabela:** dos 24 selectores que o Python consulta, **21 sao HTML estatico** e **5 sao
gerados pelo `panel.js`** (`.caption__text`, `.hist__text`, `.hist__folder`, `.hist`, `mark`) — a lista
inteira esta' coberta. Nenhum selector consultado pelo Python falta por completo.
(`.hist` e `mark` nao dao um `grep -c` limpo em HTML porque sao substrings de `history`/`wordmark`; por
isso a coluna diz o literal que o `panel.js` cria.)

### Onde `reveal_in_folder` vive (o contrato, "so para ler")

`sotto_webview.py:1811` — existe, e o que constroi foi medido pelo oraculo ja' em `panel-v2.md §3`:
`explorer /select,"<ficheiro>"` / `explorer "<pasta>"`, ambos `CREATE_NO_WINDOW`, caminho fora da raiz
**recusado**. Nesta corrida o proprio probe voltou a exercitar a guarda:
`WARN REVEAL_REFUSED ... reason=outside-history-root` e `WARN REVEAL_MISSING`, com
`revealGuard:{"outside":false,"missing":false}`.

---

## 2. O PROBE REAL — o criterio de aceitacao, corrido por mim

Comando (sem worker, sem hotkey — nao rouba o `Alt+C` do dono, nao reinicia worker):

```
"C:/Program Files/Python311/pythonw.exe" app/webview/sotto_webview.py --no-hotkey --probe-v2 3 \
  --log I:/!manager/state/tmp/panel-gap-probe.log
```

Resultado (log de registo `_main/panel-gap-probe.log`, `EXIT=0`):

```
sotto: PANEL_V2_GATE=GREEN
PANEL_V2_PROBE {"shape":{"history":true,"historyAboveLive":true,"live":true,"liveBox":true,"liveList":true},
 "buttons":{"reveal":true,"revealLabel":"Show in folder","search":true,"searchInput":true},
 "historyApi":true,"rootLabel":"H:\\sotto\\history",
 "feedFolderButtons":36,                                   <-- 36 botoes "mostrar na pasta" RENDERIZADOS
 "search":{"hits":1,"folderButtons":1,"marked":true,      <-- o <mark> da pesquisa APARECE
           "note":"1 match for “SOTTO-V2-1791279367136”",
           "texts":["A legenda ao vivo SOTTO-V2-1791279367136."]},
 "revealGuard":{"outside":false,"missing":false}}
```

`feedFolderButtons:36` **e** `search.marked:true` **e** `search.folderButtons:1` — os dois elementos que o
brief diz faltarem estao', medidos, no DOM da pagina real. **O elemento `#history-list mark` responde ao
selector do Python `:1013` pelo caminho real (a pesquisa foi conduzida pela UI, `requestSubmit()`).**

---

## 3. A MEDICAO QUE O `grep` NAO PODE DAR — geometria (fecha o "esta' no DOM mas invisivel")

Contar nos do DOM nao prova *renderizado*: um no `display:none` tambem conta. Fiz um oraculo
(`_main/_panel-gap-visibility.py`) que embrulha `request_exit` e, no instante em que o probe vai sair
(a lista esta' entao em estado de RESULTADO DE PESQUISA), mede `getBoundingClientRect` + `getComputedStyle`
do primeiro `.hist__folder` e do primeiro `mark`, **com a linha `.hist` como CONTROLE** (se o controle
fosse de tamanho zero, o instrumento estaria a medir uma janela que nunca fez layout, e o oraculo diria isso).

Corrida (`_main/panel-gap-visibility.log`, `EXIT=0`, `PANEL_V2_GATE=GREEN`):

```json
PANEL_GAP_VISIBILITY {"rows":1,"folders":1,"marks":1,"listClientH":266,"listScrollTop":0,
 "controlRow":{"w":348,"h":44,"x":15,"y":143,"display":"grid","opacity":"1","visibility":"visible"},
 "folder":{"w":24,"h":18,"x":332,"y":148,"display":"block","opacity":"1","visibility":"visible","text":"📁"},
 "mark":{"w":165,"h":34,"x":79,"y":148,"display":"inline","opacity":"1","visibility":"visible",
         "text":"SOTTO-V2-1791279454876"}}
```

- CONTROLE `348x44` → o instrumento mede uma janela que fez layout. Instrumento valido.
- `folder` **24x18**, `display:block`, `visibility:visible`, `opacity:1`, texto `📁` → LAYOUT E VISIVEL.
- `mark` **165x34**, `display:inline`, `visibility:visible`, `opacity:1`, texto = o token → LAYOUT E VISIVEL.
- `listScrollTop:0` com a linha em `y=143` dentro de `listClientH:266` → dentro da area visivel da lista.

**Nao abriu janela:** o censo da casa leu `visiveis=14 alarmSet=0` em `09:33:22Z,09:34:22Z,09:35:22Z,
09:36:22Z,09:37:22Z,09:38:22Z` (as minhas duas corridas caem em `09:36:07Z` e `09:37:36Z`) e
`ALERTA-JANELA.*09:3` = 0. O painel arranca invisivel e o probe nunca chama `show_panel`.

---

## 4. ANTES / DEPOIS MEDIDO

| medida | ANTES (o instrumento do brief) | DEPOIS (esta auditoria) | editado? |
|---|---|---|---|
| `grep -c hist__folder app/electron/panel.html` | 0 | 0 | **nao** — e' 0 por construcao |
| `.hist__folder` no DOM (probe) | (nao medido pelo brief) | **36** | nao |
| `.hist__folder` visivel (rect) | (nao medido) | **24x18, visible** | nao |
| `search.marked` (probe) | (nao medido pelo brief) | **true** | nao |
| `mark` visivel (rect) | (nao medido) | **165x34, visible** | nao |
| `PANEL_V2_GATE` | n/a | **GREEN** | nao |

O "Depois" **e' igual ao "Antes" porque nao havia defeito**: a unica mudanca e' no INSTRUMENTO
(de `grep` contra HTML estatico para medicao de DOM+geometria na pagina viva).

---

## 5. O QUE FICOU DELIBERADAMENTE POR FAZER (e por que)

1. **Nao renderizei um botao `.hist__folder` no `panel.html`.** O `panel.js:367` ja' o cria por linha, com
   `title`/`aria-label`/handler de clique proprios e o `entry.path` correcto. Escrever tambem no HTML
   criaria **duas fontes de verdade** para o mesmo elemento — o anti-padrao que a casa recusa. E' a
   "edicao para satisfazer um `grep`", nao para satisfazer o dono.
2. **Nao mexi no `<mark>`.** `makeRow(entry, hitQuery)` (`panel.js:355-359`) ja' parte o texto em
   `highlight()` e insere `<mark>` no primeiro match; o probe confirma `marked:true`.
3. **Nao editei `sotto_webview.py`.** O brief manda-o ler "so para ler o contrato". Logo o furo do gate
   (§6/R1) fica REPORTADO, nao landado — mandar-me fecha-lo seria editar o alvo que me foi vedado.
4. **Nao toquei em `worker/` nem reiniciei o worker.** As duas corridas usam `--no-hotkey` e **sem**
   `--with-worker`; o probe conduz a legenda por `on_worker_caption`, o mesmo caminho que o `WorkerBridge`
   usa, sem arrancar um worker de ~2.4 GB.

---

## 6. RECOMENDACOES (nao edicoes — o brief manda escrever, nao aplicar)

**R1 — o gate e' MAIS FRACO do que a evidencia que imprime (a causa-raiz desta auditoria).**
`run_panel_v2_probe` (`sotto_webview.py:2255-2270`) calcula `out['ok']` sem
`results.get('marked')`, sem `results.get('folderButtons',0) > 0` e sem
`(out.get('feedFolderButtons') or 0) > 0`. Esses campos **sao impressos e nao sao assertados**: o gate
fica GREEN mesmo que o botao de pasta e o `<mark>` desaparecam. Foi por isso que um `grep` no HTML teve
de decidir por ele — e decidiu errado. Fecho mecanico sugerido (o input que tem de o deixar RED: apagar
`folder.className = 'hist__folder'` de `panel.js:367`):

```
# no out['ok'] do probe:
  and (out.get('feedFolderButtons') or 0) > 0
  and results.get('marked') is True
  and results.get('folderButtons', 0) > 0
```

**R2 — um `grep` contra `panel.html` como criterio de RENDERIZACAO e' um instrumento invalido.**
Metade dos nos deste painel nasce em JS. Quem auditar este ficheiro deve medir o DOM (probe) ou marcar
claramente `panel.html` como *estrutura*, nao como *inventario de elementos renderizados*. Sugestao barata:
um comentario no topo do `panel.html` a nomear os selectors que o `panel.js` cria
(`.caption__text`, `.hist`, `.hist__text`, `.hist__folder`, `.hist__time`, `.history__empty`, `mark`).

**R3 — o botao "Show in folder" a ABRIR o Explorer nunca foi disparado** (`panel-v2.md §7` tambem o diz):
o mecanismo e' medido ate' ao `explorer /select,...` com `CREATE_NO_WINDOW`, o clique final nao, porque
abriria uma janela no ecra do dono. Nao e' uma lacuna de renderizacao; e' uma fronteira deliberada.

---

**R1 esta' FILADO** (a observacao e' duravel, nao so' prosa): ticket `d4972cd7f9b119746bf9bc85`
em `I:/!manager/state/tickets/tickets.jsonl` — com o repro mecanico que eu corri
(`py -3 -c "... print([k for k in ['feedFolderButtons','marked','folderButtons'] if k in out_ok_block])"` -> `[]`).
O dono do sitio e' o probe em `sotto_webview.py`; o brief proibia-me edita-lo, por isso a cura fica
com quem o sustentar.

## SELF-AUDIT

**1. protocolos em falta** — Senti falta, e nao segui, o `read-before-concluding` no PRIMEIRO movimento: li
`grep -c hist__folder = 0` no brief e **estive a ponto** de tratar isso como lacuna medida. O que me travou
foi ler o `panel.js` antes do `panel.html`. Diferente: para toda a classe "elemento X falta", o primeiro
passo devia ser **ler o ficheiro que CRIA elementos** (`panel.js`) e so' depois o HTML — ou, melhor, correr
logo o probe. Tambem faltou um protocolo para "premissa do brief e' falsa": nao ha' um caminho escrito para
*devolver* um brief sem landar nada, e foi o que este trabalho fez.

**2. verificacao adicional** — Corri-a: o oraculo de geometria (§3), que fecha o furo "esta' no DOM mas
invisivel" que o `grep` e o proprio probe nao fecham, com CONTROLE positivo. O que aumentaria mais a
confianca era um **teste de MUTACAO**: apagar `folder.className = 'hist__folder'` num checkout temporario e
provar que (a) o probe continua GREEN hoje (o furo do R1, provado) e (b) o `ok` proposto vira RED. Custo:
~1 min e dois `--probe-v2`; **nao corrido** porque exige editar `panel.js`, que o brief proibe.

**3. checkboxes novas (mecanicas)** —
(a) `grep -c <classe> panel.html` **nunca** pode ser usado como prova de ausencia sem um
`grep -c <classe> panel.js` ao lado: se `js > 0`, o 0 do HTML e' esperado. Comando:
`for t in $(python - <<... extrai os selectors do .py...); do echo "$t $(grep -c $t panel.html) $(grep -c $t panel.js)"; done`
— o 0/1 do `hist__folder` e' o caso de ouro.
(b) Todo o gate de aceitacao que **imprime** um campo tem de o **assertar** no `ok`; um campo
`X":N` no log sem `X` no `ok` e' evidencia ornamental (`PANEL_V2_PROBE` imprimia `feedFolderButtons` e
`marked` e nao os assertava).
(c) `pythonw.exe ... --probe-v2 3` tem de acabar com `PANEL_V2_GATE=GREEN` **e** com o censo de janelas
plano na janela do minuto (`grep "JANELAS ts=" state/progress/window-census.log | tail -2`) — prova que
uma corrida de aceitacao nao piscou janela.

**4. review por outro subagente** — **sim-com-escopo**: (i) a tabela §1 — um reviewer que re-derive a lista
de selectors do `.py` por `grep` em vez de a aceitar; (ii) a §3 — que re-corra
`_main/_panel-gap-visibility.py` noutra maquina/estado e confirme rect != 0 com o CONTROLE != 0;
(iii) a §6/R1 — que verifique, lendo `sotto_webview.py:2255-2270`, que `feedFolderButtons` e `marked`
nao entram no `ok`. Nao o pedi antes de fechar porque o oraculo de geometria com controlo e' o proprio
review mecanico, e o resultado quero em cima da mesa.

**5. gate-doubt:**
- **verde-de-verdade**: `PANEL_V2_GATE=GREEN` correu **duas vezes nesta sessao, na build actual**, por mim
  (`_main/panel-gap-probe.log`, `_main/panel-gap-visibility.log`), com token unico por corrida
  (`SOTTO-V2-1791279367136`, `SOTTO-V2-1791279454876`) ligando legenda->feed->disco->API. **Onde podia
  estar vacuo, e nao esta':** o `ok` NAO asserta `feedFolderButtons`/`marked` (furo R1) — mas as DUAS
  assercoes que eu invoquei (`folders:1`/`marks:1` com rect != 0) vem do **meu** oraculo, que exige
  `controlRow.w>0`, logo nao pode passar por construcao com a janela sem layout. Nao ha' artefacto stale:
  as duas corridas sao desta sessao e os logs foram copiados para `_main/` no fim.
- **falta-no-gate**: o gate NAO verifica (a) que `.hist__folder` / `mark` **existem** (R1), nem (b) que
  estao **visiveis** (contagem de nos, nao geometria — o meu oraculo e' que fecha). Cenario que atravessa
  isto: uma mudanca futura poe `.hist__folder{display:none}` no CSS para "limpar" a lista — o probe
  continua GREEN e o botao fica invisivel para o dono. O mesmo com `mark{opacity:0}`.
- **gate-melhor**: (i) as 3 assercoes do R1 no `out['ok']`; (ii) juntar ao probe uma leitura de geometria
  como a minha (`folder.w>0 && getComputedStyle(folder).visibility==='visible'`). Input que tem de o deixar
  RED: `panel.css` com `.hist__folder{display:none}` → hoje GREEN (falha), com o gate-melhor RED.

**6. confianca** — **alta** para o veredicto "nao ha' lacuna": DOM (36 botoes), o proprio instrumento do
brief (0 no HTML, 1 no JS), CSS sem `display:none`, e geometria com controlo positivo (24x18 visible)
concordam, por tres caminhos independentes. O que a mudaria: **um** teste de mutacao (§2) que provasse que
o gate actual deixaria passar a remocao do botao — e' a unica afirmacao do R1 que fica por prova directa.

**7. nao verificado** —
- a mutacao do R1 (apagar `folder.className = 'hist__folder'` e ver o gate continuar GREEN): nao corrida —
  exigiria editar `panel.js`, proibido pelo brief. Fica como falsificador do R1.
- o clique real no botao a abrir o Explorer (fronteira deliberada; abriria janela).
- a arma Electron (`app/electron/main.js`/`preload.js`/`history-store.js`): o probe e' da arma WebView2;
  o renderer e' o MESMO `panel.js`, mas nao o corri sob Electron.
- o worker REAL a transcrever ate' ao painel (nao arranquei 2.4 GB; a cadeia esta' provada via
  `on_worker_caption`).

---

## CACHE/PRICE

Fonte: `bash I:/!manager/scripts/cache-task-report.sh SottoPanelGap` (saida VERBATIM):

```
## CACHE/PRICE
- task/agent: SottoPanelGap
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoPanelGap.jsonl
- cache: read=3692288 write=0 hit=96.8022% (cache-read / input+cache-read); universe: 44 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoPanelGap.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-3/deepseek-flash: calls=39 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-3/deepseek-flash $0.00000000; opencode-go-4/space-bunny-free $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 44…
- when-failed: break_items=1; WHEN=2026-10-06T09:34:48.376000+00:00 | break_items=3; WHEN=2026-10-06T09:34:49.084000+00:00 | break_items=2; WHEN=2026-10-06T09:36:49.211000+00:00 (state=RESOLVED-BREAKS-OMP; population: 3 of 115601 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoPanelGap']; window: 2026-10-06T09:34:48.376000+00:00..2026-10-06T09:36:49.211000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11090-b753-76c3-9210-89f3919ad86a provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791279288376 | session_id=01a11090-b753-76c3-9210-89f3919ad86a provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791279289084 | session_id=01a11090-b753-76c3-9210-89f3919ad86a provider=deepseek-flash model=deepseek-flash item_index=98; turn_id=1791279409211 (state=RESOLVED-BREAKS-OMP; population: 3 of 115601 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoPanelGap']; window: 2026-10-06T09:34:48.376000+00:00..2026-10-06T09:36:49.211000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T09:40:11.765750+00:00
- usage rows: 44
- model + route: opencode-go-3/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/space-bunny-free
- input tokens: 121973
- output tokens: 30619
- cache-read tokens: 3692288
- cache-write tokens: 0
- hit ratio: 96.8022% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 6 (state=RESOLVED-BREAKS-OMP; population: 3 of 115601 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoPanelGap']; window: 2026-10-06T09:34:48.376000+00:00..2026-10-06T09:36:49.211000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T09:34:48.376000+00:00; WHERE session_id=01a11090-b753-76c3-9210-89f3919ad86a provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791279288376
  - break_items=3; WHEN=2026-10-06T09:34:49.084000+00:00; WHERE session_id=01a11090-b753-76c3-9210-89f3919ad86a provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791279289084
  - break_items=2; WHEN=2026-10-06T09:36:49.211000+00:00; WHERE session_id=01a11090-b753-76c3-9210-89f3919ad86a provider=deepseek-flash model=deepseek-flash item_index=98; turn_id=1791279409211
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

`when_failed`/`where_failed` presentes acima, com WHEN e WHERE. `price` le-se `$0.00000000` **com fonte**
(`message.usage.cost.total` no JSONL) e as tarifas por modelo vem `UNKNOWN — not recorded in this source`;
nao escrevo zero-sem-fonte.
