# Recibo — S7: carregamento só do essencial (lazy) + diagnóstico do stutter no arranque

Data: **2026-10-12** (America/Sao_Paulo). Lane: **S7**.
Ficheiros que ESTA lane escreveu: `app/webview/sotto_webview.py`, `app/panel/lazy-assets.js` (**novo**),
e este recibo. `app/panel/panel.html` **não foi tocado por mim** (é da lane S2) — ver §A.4.

---

## 0. Revisões medidas (AGENTS.md, regra 2 — todo o `file:line` abaixo é DESTA revisão)

| ficheiro | bytes | linhas | CRLF / bare LF | sha256 (16) |
|---|---|---|---|---|
| `app/panel/panel.html` | 61 579 | 1 064 | 1 064 / 0 | `33ED88B9E6F4D93A` |
| `app/panel/lazy-assets.js` (**novo**) | 13 423 | 291 | 291 / 0 | `3DA74BDEB2040B1F` |
| `app/webview/sotto_webview.py` | 477 839 | 9 350 | 9 350 / 0 | `CD00E071341E9BC3` |
| `worker/sotto_worker.py` | 330 701 | 6 261 | — | `BB0EEB907DC6E0FD` |
| `app/webview/hot_reload.py` | 25 473 | 613 | — | `6B5C235AD699C6C2` |

`panel.html` e `sotto_webview.py` **moveram-se durante esta lane** (o shell de 460 312 B / 9 065 linhas
para 477 839 B / 9 350 linhas; o painel de 56 537 B / 1 021 linhas para 61 579 B / 1 064 linhas).
Todas as âncoras abaixo foram **re-corridas na revisão final**, não herdadas.

---

# A. Carregamento só do essencial

## A.1 O que o painel carrega hoje, medido

Instrumento: `node` sobre os bytes de `panel.html` (população `<link rel=stylesheet>` + `<script src>`
em ordem de documento) + `statSync` por ficheiro. **20 recursos, todos antes de `</body>`.**

```
themes/fonts.css            27 971      caption-formulation.js   40 333
panel.css                  108 638      history-source.js         3 708
themes/theme-1.css          26 952      history-gallery.js        7 638
themes/theme-2.css          27 169      surface.js                4 425
themes/theme-3.css          27 302      themes/themes.js          9 854
themes/theme-4.css          26 235      themes/panel-designs.js   2 998
themes/theme-5.css          27 437      themes/zipc-panels.js     3 162
themes/zipc-panels.css      35 875      theme-switcher.js        43 405
                                        theme-tune.js            46 218
                                        panel.js                147 279
                                        letter-swap.js           19 233
                                        caption-float.js          4 965
assets = 640 797 B   +   panel.html 61 579 B   =   702 376 B
```

## A.2 O que ficou de fora, e porquê é seguro

Cinco ficheiros **continuam em disco** mas **já não estão no `panel.html`**:

| recurso | bytes | porquê é seguro adiar |
|---|---|---|
| `themes/cinematic.css` | 312 230 | 548 regras, **0 sem escopo** — todas `:root[data-theme^='cine-']` |
| `themes/panel-designs.css` | 128 716 | 570 regras, **0 sem escopo** |
| `skins/skins.js` | 812 978 | `window.SOTTO_SKINS`, lido UMA vez no parse por `skin-host.js` |
| `skin-host.js` | 22 712 | `panel.js` guarda todas as chamadas em `window.SottoSkin && .active` |
| `skin-layout.css` | 11 210 | 18 regras, **0 sem escopo** — todas sob `#skin`/`[data-skin]` |

**Total adiado: 1 287 846 B.** Invariante de segurança re-medido nesta revisão (instrumento: `node`,
comentários removidos e corpos `@keyframes` excluídos — os `to`/`50%` que um scanner ingénuo conta como
«sem escopo» são passos de keyframe, com escopo pelo NOME da animação): **0 membros sem escopo em todos**.

## A.3 Números antes/depois — e a atribuição honesta

```
painel ANTIGO (21 recursos, os 5 ligados eager)     1 893 803 B
painel ACTUAL (20 recursos, os 5 fora do documento)   702 376 B
RETIRADO DO ARRANQUE                                1 191 427 B  =  62.9 %
```

**Atribuição, sem a inflacionar.** A remoção das cinco tags `<link>`/`<script>` do `panel.html` foi feita
pela lane S2 e está **committed** (`git status --porcelain -- app/panel` devolve vazio). O que ESTA lane
entrega é o que torna essa remoção **segura e reversível** — sem o loader e o gate, um tema `cine-*`
ficaria sem CSS nenhum, porque `theme-switcher.js` **nunca cria um `<link>`**: o mecanismo dele é uma
escrita de atributo e mais nada (`theme-switcher.js:846-850`, *«No stylesheet is created, fetched or
replaced here»*), e o cabeçalho dele declara *«All five stylesheets are linked at once»* (`:9`) —
premissa que o `panel.html` de hoje **já não satisfaz**.

## A.4 As linhas exactas pedidas ao `panel.html` (S2) — já aplicadas

Não escrevi no `panel.html`. As duas linhas que o desenho pedia **já lá estão**, postas pela S2:

- `panel.html:1034-1036` — comentário que declara `skins.js` *«ASKED, not eager: `lazy-assets.js`
  (injected before any of this parses) tags the skins the running theme needs and the shell gates the
  bytes on the ask.»*
- `panel.html:1055` — o mesmo para `skin-host.js`.

O loader **não** é uma tag no documento: é injectado pelo preload do shell
(`AddScriptToExecuteOnDocumentCreatedAsync`), que é a única posição que corre **antes** de qualquer
script da página — e é isso que lhe permite ver o `data-theme` que o switcher escreve.

## A.5 O gate do shell (o que torna o adiamento possível num `file://`)

O `panel.html` é servido **byte a byte** pelo carregador de ficheiros do Chromium; não há servidor HTTP
para segurar um recurso, e a CSP do painel (`script-src 'self'`, com `'unsafe-inline'` só para style)
proíbe injecção por `blob:`/`data:`. Por isso o shell intercepta os cinco pedidos e responde **200 com
corpo vazio** até a página pedir os bytes reais pelo bridge.

| peça | âncora (revisão 477 839 B) |
|---|---|
| `LAZY_ASSETS` (5 URLs) | `sotto_webview.py:113` |
| `LAZY_LOADER_JS` | `:120` |
| `class LazyAssetGate` | `:131` |
| `AddWebResourceRequestedFilter` ×5 | `:160` |
| `on_resource_requested` → 200 vazio | `:166-188` |
| `allow(url)` (idempotente, valida contra `LAZY_ASSETS`) | `:190-210` |
| `_bootstrap_js()` (preload = `BOOTSTRAP_JS` + loader) | `:3030` |
| `_install_bootstrap` chama `_bootstrap_js()` | `:4267`, uso em `:4286` |
| `_arm_lazy_gate()` chamado em `_on_core_ready` | `:4265` |
| `_arm_lazy_gate` (subscribe `WebResourceRequested`) | `:4290`, subscribe em `:4326` |
| handler do bridge `'lazy-asset'` → `_lazy_asset` | `:3527` / `:3628` |
| flag `--no-lazy` | `:8822` |

## A.6 Braço de controlo — o gate sabe dizer NÃO

`--check-args` corre o parser **sem lançar nada** (`sotto_webview.py:9156`, `help=argparse.SUPPRESS`):

```
python app/webview/sotto_webview.py --check-args                rc = 0
python app/webview/sotto_webview.py --check-args --no-lazy      rc = 0   <- aceite
python app/webview/sotto_webview.py --check-args --lazy         rc = 2   <- recusado
python app/webview/sotto_webview.py --check-args --bogus-flag   rc = 2   <- recusado
```

`--no-lazy` constrói o gate com `enabled=False` (`:4317-4320`): **não regista filtros e não se
subscreve**, portanto nenhum pedido é interceptado — é exactamente o comportamento de hoje.
O `--help` lista `[--no-lazy]`.

## A.7 DEFEITO ENCONTRADO E CORRIGIDO nesta lane

A primeira revisão do loader **só pedia os bytes do CSS**. O `loadSkinPair()` injectava
`skins/skins.js`, `skin-host.js` e `skin-layout.css` **sem `ask()`** — e como o gate responde a um URL
adiado que ninguém pediu com **corpo vazio**, o resultado era o pior dos dois mundos:
`cinematic.css` **chegava** (esse era pedido) e o skin **não montava** — um tema `cine-*` meio-aplicado.

Corrigido com três `ask()` antes de cada injecção (`lazy-assets.js:192`, `:200`, `:206`).
Teste funcional (harness `node` com DOM mockado, 4 casos, todos PASS):

```
[A] tema base theme-1      asked=[]                                   DOM vazio            PASS
[B] cine-north             asked=[cinematic.css, skins.js,            4 elementos na ordem
                                 skin-host.js, skin-layout.css]        certa                PASS
[C] theme-3                asked=[]                                   DOM vazio            PASS
[D] reload() x2 no mesmo tema   DOM idêntico antes/depois, asked=4 (sem duplicar)          PASS
```

A ordem provada em [B] é o contrato: `cinematic.css` → `skins.js` → (no load) `skin-host.js` →
(no load) `skin-layout.css`. `skins.js` tem de **executar** antes de `skin-host.js` **parsear**, porque
este lê `window.SOTTO_SKINS` uma vez no parse e nunca o relê.

## A.8 Limite conhecido desta entrega

**NÃO MEDIDO: nada disto foi visto a correr num WebView2 real.** O gate, o preload e o loader estão
verificados por leitura, `py_compile`, `node --check`, um harness `node` com DOM mockado e o parser de
argumentos — **nunca por um lançamento**. O que fica por provar, e só o Lead pode provar:
(a) que o `WebResourceRequested` dispara para os cinco URLs `file:///` com o filtro registado;
(b) que o `data-theme` que o switcher escreve chega ao `MutationObserver` do loader;
(c) que um tema `cine-*` fica **visualmente completo** (CSS + skin) depois do ask.
O §B.4 dá os comandos exactos.

---

# B. Stutter no arranque — análise estática e PLANO DE MEDIÇÃO

**Não há conclusão neste capítulo.** O dono proibiu lançar, e um stutter não se atribui por leitura de
código. O que segue separa **o que o código permite descartar** do **que só um lançamento decide**.

## B.1 O caminho de arranque, na ordem real (revisão 477 839 B)

```
main()                                    sotto_webview.py:9121
  apply_webview2_environment()            :9136   (knobs de ambiente ANTES da janela)
  shell = SottoShell(args)                :9292
  shell.create_window()                   :9293   -> EnsureCoreWebView2Async (WebView2 nasce aqui)
  arm_hotkey / hot_reload / tray          :9307-9325
  webview.start(icon=SOTTO_ICON)          :9344   -> loop de mensagens WinForms
        |
        +-- stage.html carrega -> _on_loaded()  :4350  -> bounce para panel.html (:4387)
        +-- panel.html carrega -> _on_loaded()  :4350
                20 recursos / 702 376 B parseados e compilados
                start_worker(worker_reason)     :4504   <-- AQUI nasce o worker
                  WorkerBridge.start()          :7724
                    _spawn()                    :7766
                      subprocess.Popen(...)     :7823   (CREATE_NO_WINDOW, :7819)
                        -> processo SEPARADO: 1 070 642 977 B de pesos, 33 ficheiros
                           StreamAsr.__init__            worker:505
                             3 x ort.InferenceSession    worker:551-553
```

## B.2 O que o código PERMITE descartar (com a âncora)

1. **O watcher NÃO varre `worker/models/`.** `hot_reload.py:291-294` chama
   `ReadDirectoryChangesW(self._handle, self._buf, BUFFER_BYTES, False, FILE_NOTIFY_CHANGE_ALL, ...)`
   — o 4.º argumento é `bWatchSubtree=False`, logo **não é recursivo** e fica no nível de topo de
   `panel/` e `worker/`. Não enumera os 33 ficheiros de 1 GB. **Descartado como fonte de stutter por
   enumeração de subárvore.**
2. **A spawn do worker não bloqueia a thread da UI.** É `subprocess.Popen` (`:7823`), não `run`/`wait`.
   O custo de 1 GB **não** está no caminho crítico do shell.
3. **O worker nasce DEPOIS de o painel carregar**, não antes: `_on_loaded` (`:4350`) só chama
   `start_worker` (`:4504`) depois de o documento ser o `panel.html`. Logo o carregamento do modelo
   **não** compete com o parse/compilagem dos 702 376 B do painel — compete com os **segundos
   seguintes**, já com o painel visível.
4. **`_add_cuda_dll_dirs` é limitado.** `worker:327`, chamado em `:4511`/`:4570`; o `os.walk(nv)`
   (`:362`) corta em `depth > 3` (`:363-366`) e só recolhe directórios que contenham DLL/SO. Não é uma
   varredura de disco aberta.
5. **O pump de legendas é limitado por construção.** `emit_async` mantém **um** post pendente por canal
   (substitui o payload em vez de enfileirar) — fechado em código a 2026-10-11, com oráculo e
   `--neg-arm` RED. **Mas isso só cobre o pump DEPOIS de haver worker e legendas**; não diz nada sobre
   os primeiros segundos.

## B.3 O que NÃO se pode descartar por leitura

- **Criação do WebView2.** `create_window()` (`:9293`) levanta `msedgewebview2.exe` (browser, GPU,
  network service, renderer) — vários processos e uma sessão COM. É o único candidato **antes** de
  qualquer worker, e nada no código o torna barato.
- **O carregamento do modelo.** 1 070 642 977 B lidos do disco + 3 `InferenceSession` + init CUDA
  (`worker:551-553`), com `OMP_NUM_THREADS` default **8** (`worker:547`). Um burst de ~1 GB de leitura e
  8 threads é exactamente a forma de um stutter de sistema.
- **A concorrência dos dois.** O worker nasce enquanto o WebView2 ainda está a estabilizar (processos,
  shaders, primeira composição). Nenhum dos dois isolado explica necessariamente o que o dono sente.

## B.4 PLANO DE MEDIÇÃO — os comandos são do Lead

O dono escreveu: *«acho que é o sotto que causa um stutter quando inicia no meu pc, acho. investiga
apenas se ELE faz isso, se nao faz, ignora.»* O plano tem de conseguir responder **NÃO**.

### Desenho: 3 braços, mesma máquina, mesma sessão

| braço | comando | o que isola |
|---|---|---|
| **A — completo** | `H:\sotto\app\webview\run.cmd` | o que o dono corre |
| **B — só shell** | `H:\sotto\app\webview\run.cmd --no-worker` | tira o modelo (1 GB / 8 threads) |
| **C — sem adiamento** | `H:\sotto\app\webview\run.cmd --no-lazy` | tira o gate (controlo do §A) |

Todos com `TMPDIR=I:\cc-tmp` posto ANTES. Nenhum deixa janela visível (`run.cmd` arranca escondido e o
gate de `Show` está montado).

### Amostragem por segundo, primeiros 30 s

`Get-Counter -ListSet 'Process'` **falha nesta máquina** — usar `Win32_PerfFormattedData_PerfProc_Process`.
E o `Get-CimInstance` **inline devolve vazio**: tem de correr de um **ficheiro `.ps1`** (não posso
escrevê-lo — esta lane só pode escrever 3 ficheiros; fica aqui a fonte para o Lead gravar):

```powershell
# _main\_s7-stutter-sample.ps1   (gravar e correr:  pwsh -File _main\_s7-stutter-sample.ps1)
$ErrorActionPreference='Stop'
$secs = 30
$rows = @()
for ($i=0; $i -lt $secs; $i++) {
  $t = Get-Date -Format 'HH:mm:ss.fff'
  # processos do Sotto, por nome de artefacto (NUNCA a palavra 'sotto' sozinha)
  $procs = Get-CimInstance Win32_Process |
           Where-Object { $_.CommandLine -match 'sotto_webview\.py|sotto_worker\.py' }
  $wv = @(Get-Process msedgewebview2 -ErrorAction SilentlyContinue).Count
  $cpu = 0.0; $ws = 0L
  foreach ($p in $procs) {
    $perf = Get-CimInstance Win32_PerfFormattedData_PerfProc_Process |
            Where-Object { $_.IDProcess -eq $p.ProcessId }
    if ($perf) { $cpu += [double]$perf.PercentProcessorTime }
    try { $ws += (Get-Process -Id $p.ProcessId -ErrorAction Stop).WorkingSet64 } catch {}
  }
  # IO de disco do sistema: o burst de 1 GB tem de aparecer aqui
  $disk = (Get-CimInstance Win32_PerfFormattedData_PerfDisk_LogicalDisk |
           Where-Object { $_.Name -eq '_Total' }).DiskReadBytesPerSec
  $rows += [pscustomobject]@{
    t=$t; sotto_procs=$procs.Count; wv_procs=$wv; cpu_pct=[math]::Round($cpu,1);
    ws_mb=[math]::Round($ws/1MB,0); disk_read_mb=[math]::Round($disk/1MB,1) }
  Start-Sleep -Milliseconds 1000
}
$rows | Format-Table -AutoSize
$rows | Export-Csv -NoTypeInformation -Encoding UTF8 I:\cc-tmp\s7-stutter.csv
```

Correr o sampler **em paralelo** com cada braço, e arrancar o braço ~2 s depois de o sampler começar
(para haver linha de base antes do lançamento).

### A regra de decisão, escrita ANTES de ver os números

- Se a saturação aparecer no braço **B (`--no-worker`)** → **é o shell/WebView2**, não o modelo.
- Se **B** for limpo e **A** saturar → **é o carregamento do modelo do worker** (a assinatura: leitura de
  disco a subir para ~1 GB acumulados e `cpu_pct` a bater no tecto durante o mesmo intervalo).
- Se **A** e **B** forem ambos limpos e o dono continuar a sentir o stutter → **o Sotto não é a causa**;
  pela ordem do dono, **ignora-se** e o trabalho pára aqui.
- **C vs A** é o controlo do §A: se os bytes do arranque não se moverem entre os dois, o gate é vazio e
  **este recibo tem de o dizer**.

### O que a mudança do §A já tira do arranque

Para um tema `cine-*` (25 dos 30 temas do manifesto), o painel antigo parseava 1 861 506 B antes da
primeira legenda; hoje parseia 702 376 B e os outros **1 159 130 B (62.3 %)** só chegam quando o tema
os pede. Para os cinco temas do dono (`theme-1..5`) o arranque é **idêntico** — nada é adiado, e é por
isso que o braço base **não** mostra diferença nenhuma entre A e C.

## B.5 UNMEASURED — a lista, sem a maquilhar

1. **Nenhum lançamento foi feito por esta lane.** Não há um único número de CPU, disco ou tempo de
   arranque medido com o Sotto a correr. O §B.4 é um plano, não um resultado.
2. **A causa do stutter continua NÃO ATRIBUÍDA.** O §B.2 remove candidatos (watcher não-recursivo,
   spawn não-bloqueante, ordem worker-depois-do-painel); não nomeia o culpado.
3. **Não sei qual tema o dono usa.** O ganho de 62.3 % só se aplica a `cine-*`; se ele vive em
   `theme-1`, o §A não lhe muda o arranque. `localStorage` num WebView2 `file://` pode não persistir —
   e o user-data-dir do dono foi visto como `G:\Temp\tmpud8lmmpq\EBWebView` (temporário) numa corrida
   e `%APPDATA%\pywebview` (persistente) é o default do pywebview. **Contradição não resolvida** — e é
   ela que decide se o tema sobrevive entre sessões. O desenho do loader é seguro nos dois casos
   (lê o store, depois o atributo, depois o `fallback` do manifesto), mas o *valor* é desconhecido.
4. **A arm `pd-*` do loader é código morto hoje.** O manifesto tem 30 entradas: 5 `theme-N` + 25
   `cine-*`. **Não existe nenhum tema `pd-*`** e nenhum tema aponta para `themes/panel-designs.css`
   (128 716 B em disco, referenciado por nada). Fica no `NEEDS` porque é inofensivo e cobre a forma
   caso ela volte — mas **não é um ganho medido**, e não deve ser contado como tal.
5. **O comentário do `theme-switcher.js:285-288` está STALE** e contradiz o `panel.html` de hoje:
   afirma *«the eight theme stylesheets the document links are 601 922 B / 3 149 rule blocks»* e
   justifica com isso que *«the CSS is ALL parsed and registered at load»*. O documento **já não liga**
   `cinematic.css` nem `panel-designs.css`. Não toquei no ficheiro (não é meu); fica registado porque
   quem o ler a seguir vai acreditar numa premissa falsa sobre o arranque.
6. **O `--no-lazy` não foi corrido a valer**, só o parser (`--check-args`). Que o gate desligado sirva
   os bytes do disco é leitura de código (`:4317-4320` + `:168-169`), não observação.

---

## C. O que fica feito, em uma linha cada

- **A** — `app/panel/lazy-assets.js` (13 423 B) + gate no `sotto_webview.py`: cinco recursos
  (**1 287 846 B**) saem do arranque; o arranque do painel passou de **1 893 803 B** para
  **702 376 B** (**−1 191 427 B = 62.9 %**), com **0 membros de regra sem escopo** nos ficheiros
  adiados e um braço de controlo (`--no-lazy`) que o parser aceita e que desliga o gate.
- **A (defeito)** — o loader pedia o CSS e **não** pedia o skin; corrigido com três `ask()`;
  4/4 casos do harness passam, incluindo idempotência sob `reload()` duplo.
- **B** — o caminho de arranque está lido e ancorado na revisão actual; **nenhuma causa está atribuída**
  e o plano do §B.4 é executável pelo Lead com uma regra de decisão escrita **antes** dos números.
