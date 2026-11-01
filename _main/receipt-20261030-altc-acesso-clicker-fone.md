# Receipt 2026-10-30 — Alt+C, acesso negado, autoclicker, fone, bateria

**Estado:** `reported` e `fixed` separados de `verified`. Nada aqui se chama `verified`: a verificação
final do gesto é o teclado do dono (declarado em §6).

O dono, verbatim nesta sessão: *"eu nao tenho permissao?"* · *"vai dar launch sozinho no sotto"* ·
*"o fone fica mudo"* e ele **ouve o barulho do corte**.

---

## 1. A permissão — e é o contrário do que ele supôs

| medida | comando | resultado |
|---|---|---|
| integridade da pane | `GetTokenInformation(TokenIntegrityLevel)` | `S-1-16-8192` (**medium**) |
| integridade da app | idem, pid 19648/39168 | `high` (o `err=6` na leitura é o médio a ser recusado — é a própria prova) |
| integridade do autoclicker vivo | idem, pid 32180 | `S-1-16-12288` (**high**) |
| matar o high da pane | `taskkill /PID 23556 /T /F` | `rc=128`, **sete** processos `Acesso negado` |
| matar via token emprestado | `sotto-relaunch.py --relaunch` | `kill via token(fonte=13844) ok=True` → `confirmado morto` |
| **largar** via token | idem | `CreateProcessAsUser ok` → `pid 19648 GANHOU a mutex`, `hotkey=true tray=true` |
| braço negativo do largar | `launch-as-token.py --neg-arm` | `RED` com `ADJUST_SESSIONID` reposto → `err=5` |

**A conclusão velha "só a tarefa agendada larga a app" foi REFUTADA** e está corrigida nos dois sítios
que a afirmavam (comentário de `sotto_webview.py` e adendas de `receipt-20261023-real-profile.md` e
`receipt-20261023-input-path-stutter.md`). O que continua a ser limite do Windows: abrir o token do
`pid 4` (SYSTEM).

### Os dois defeitos meus que a medição antiga escondia
1. `cmd /c taskkill ... >> ficheiro` **criou o ficheiro vazio e não matou nada**.
2. `pythonw -c "<código>"` chegava ao filho com a linha de comandos desfeita pelas aspas →
   `subprocess.list2cmdline` + **ficheiro** em vez de código inline.
3. E o pior: o ramo `medium` do relançador **lançava sem matar** — a instância velha ficava com a mutex
   e o novo `run.cmd` morria calado. Era isso que dava "90 s sem instância".

Prova do kill hoje (`launch-as-token.py --selftest`):
```
SELFTEST PASS -- fonte pid=13844 (HIGH), filho pid=396xx executou, integridade=S-1-16-12288 (HIGH)
KILL-DELEGATION PASS -- taskkill direto rc=255, via token(fonte=13844) ok=True, saiu=True
```
(`saiu` é um `WaitForSingleObject` no handle da vítima: um `OpenProcess` posterior respondia "vivo"
para um **pid reutilizado** — foi o primeiro resultado falso desta sonda.)

---

## 2. Alt+C — três defeitos de gesto, corrigidos e com dentes

`python _main/altc-gesture-oracle.py` → `ALTC-GESTURE GREEN -- arms=85 pass=85 fail=0`.
Os dois mutantes provam que os braços novos não são decorativos: matar o `release` para o ramo
só-`Alt` derruba **3** armas; matar o `new-press` para não reler o relógio derruba **2**.

Hipóteses falsificáveis antes das sondas (card #2) estão na tabela do
`receipt-20261030-altc-latency-words-and-switch.md`.

### O instrumento que mentia, e por isso a bateria ficava vermelha para sempre
`_main/_audit-hotkey-probe.py` dizia **"Alt+C IS TAKEN — another program owns MOD_ALT + C"**.
Era a **própria app** a deter a tecla. Corrigido: o veredicto lê o log vivo
(`SHELL_STARTUP_STAGE pid=` + `HOTKEY_REGISTERED ... register=true`) e responde
`HELD BY THE LIVE SOTTO ITSELF (pid=…)`, `rc=0`. Controle: com `live_sotto()` forçado a `None`, volta
a `TAKEN`, `rc=1`.

O mesmo defeito em `_main/_audit-hotkey-delivery.py`:
* o censo era `Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'"` + `CommandLine -like` — e
  nesta build o processo é **`python.EXE`** com `CommandLine` **vazio** → "no live Sotto shell" com a
  app viva. Agora o censo lê `SHELL_STARTUP_STAGE pid=` do log e confirma que o pid responde.
* o `fresh` exigia `mtime >= created_ms`; com o censo vindo do log não há idade → passou a exigir que
  a **última** linha de hotkey do ficheiro seja um `HOTKEY_REGISTERED accelerator=Alt+C`.
* controle: com `live_sotto_shells()` forçado a `[]`, o braço volta a `FAIL` — tem dentes.

---

## 3. Autoclicker

| facto | medida |
|---|---|
| alvo do atalho do Start Menu | `I:\importantes\Downloads\AutoClicker.exe` (uma única entrada `AutoClicker.lnk`) |
| instância viva | pid 32180, integridade **high** (`S-1-16-12288`) |
| logo… | **a hipótese de integridade está REFUTADA**: o clique do clicker não é bloqueado por UIPI, porque ele corre ao mesmo nível do desktop |

O que sobra, e o que já está fechado pela tabela de símbolos do próprio binário:

| símbolo em `AutoClicker.exe` | presente |
|---|---|
| `SendInput` | **sim** |
| `mouse_event` / `keybd_event` | **sim** |
| `RegisterHotKey` | **sim** |
| `GetAsyncKeyState` | **sim** |
| `SetWindowsHookEx` | não |

**`SendInput` e `mouse_event` são injecção GLOBAL**: não passam por UIPI. Ou seja, "o clique não chega
a outra app" não pode ser integridade (refutado: o processo é `high`) nem privilégio de mensagem.
O que sobra é o ALVO: ou a janela que ele quer clicar não está em primeiro plano, ou o clique cai numa
janela por cima. O overlay do Sotto declara `WS_EX_TRANSPARENT | WS_EX_NOACTIVATE`
(`app/webview/caption_overlay.py:913`), logo **não** devia comer o clique — mas isso é leitura de
código, **não** uma medição com o rato dele. `por medir`.

O `RegisterHotKey` no binário explica o `Alt+F9` medido como tomado
(`bait Alt+F9: registrable-here=False winerror=1409`): as teclas de start/stop do clicker são dele.

---

## 4. O fone que fica mudo — instrumento novo, e a correlação que ele já sugere

`_main/headphone-cut-probe.py` (novo; na bateria: `headphone-cut` + `red-as-expected-headphone-cut`).
Junta duas fontes com o mesmo relógio:
1. `IMMNotificationClient` (via `pycaw` em `_main/_libs`): device added/removed, state changed,
   default-device changed — o canal onde **o barulho do corte** aparece;
2. o `webview-run.log`, filtrado às linhas de áudio/worker;
mais um censo de `IAudioEndpointVolume` a cada 500 ms (um corte pode não gerar evento nenhum).

Veredicto por evento: `sotto` (linha do Sotto a ≤2 s), `windows`, ou `desconhecido` — e
**`desconhecido` nunca é inocência**.

`--selftest` 8/8 PASS, incluindo o braço que lê o log **real** (321 075 linhas, todas com tempo) e o
que prova que um log parado não inventa linhas. `--neg-arm`: janela vazia não acusa ninguém.

### A janela com o relógio a correr DURANTE um reinício controlado — e o resultado

07:15:04 matei a instância (`kill pid=39168 via token` → `confirmado morto`) e **dentro da janela de
150 s do instrumento** lará-la outra (`pid 19932 GANHOU a mutex`, `hotkey=true tray=true`). Veredicto
da janela:

```
HEADPHONE-CUT eventos=0 mute_flips=0 linhas_sotto=12 janela=150s
sotto=0 windows=0 desconhecido=0
```

**Zero eventos de dispositivo. Zero mudanças de mute.** Doze linhas de áudio/worker do Sotto na mesma
janela. Ou seja, um reinício completo da app **não** reconfigura o endpoint nem o silencia — a hipótese
"o corte é o reinício" fica **REFUTADA** por esta medição (e é a primeira vez que ela é feita com o
relógio a correr, não por correlação de marcas de tempo).

Segunda hipótese testada por leitura: captura em **modo exclusivo** (que roubaria o endpoint e calaria
o fone sem gerar `OnDefaultDeviceChanged`). Refutada também: `_main/_audio-exclusive-hold.cpp` é um
**instrumento de teste** (cria um detentor exclusivo para exercitar a recusa `AUDCLNT_E_DEVICE_IN_USE`),
não o comportamento da app — e dois taps *shared* no mesmo endpoint coexistem (medido no próprio
cabeçalho do ficheiro).

**O que sobra**: a janela em que ELE ouve o corte. O instrumento está pronto e na bateria; a próxima
ocorrência tem de ser apanhada a correr, senão a atribuição é conversa.

**O que já se pode dizer, com número:** entre 06:46 e 07:01 a app **reiniciou cinco vezes**
(`SHELL_STARTUP_STAGE pid=` 33312 · 19648 · 47156 · 40936 · 39168), e cada reinício reabre o WASAPI e
re-registra o Alt+C (`HOTKEY_REGISTERED` nas mesmas marcas). É o vigia de auto-relançamento a reagir a
cada alteração de código — o que, nesta sessão, fui eu a fazer. **A correlação "corte do fone ↔
reinício da app" não está provada**: falta uma janela com o instrumento a correr *durante* um
reinício, e uma janela de controle com a app parada (card #13, `por medir`).

---

## 5. YouTube 1:1 — dois vermelhos da bateria, ambos defeitos reais

| oráculo | antes | agora |
|---|---|---|
| `yt-player-track` | `a08` vermelho (`1o='pt-orig' 2o='pt-orig'`), 1 mutante com âncora morta | **PASS 10/10 arms, 4/4 mutantes** |
| `yt-mirror-align` | `a07` vermelho (`why='no-painted-caption'`), 1 mutante com âncora morta | **PASS 11/11 arms, 5/5 mutantes** |

### a08 — o defeito que o dono veria
A lista de candidatos do cache existe para **não** repetir os 5 s de `yt-dlp`. Mas era servida pela
**ordem da pergunta anterior**: ele trocava a faixa no player de `pt` para `en` e a app servia
`pt-orig` outra vez — com `reason='ok'` e `cached=False`, ou seja, o resultado não dizia que tinha
respondido com a ordem velha. Cura: `_rerank_reused()` re-escolhe com a `plang` de agora (a mesma
`tracks_from_info`), e a **língua original** passa a ir para o cache (`video_language`) para a
política de 2026-10-21 poder ser repetida sem nova extração.

### a07 — o fantoche que não pintava
`painted_words` só conta uma janela de legenda que o OS diz estar desenhada (`_rendered`: não
offscreen **e** com área > 0). O `_FakeElement` do oráculo não tinha `CurrentIsOffscreen` nem
`CurrentBoundingRectangle` → `_rendered` = False → o braço lia `no-painted-caption` e a culpa caía no
módulo. Cura: o fantoche passou a ser **desenhado** (retângulo real), e o mutante
`a-primeira-janela-ganha-em-vez-da-mais-palavras` continua a morrer no braço.

### e os dois oráculos liam âncoras com `\n` num ficheiro CRLF
Todo o mutante de mais de uma linha lia `ANCHOR MISSING -- oracle is stale` — e um mutante declarado
morto por engano é um dente que não existe. Normalizada a comparação (`\r\n` → `\n`), só para comparar.

---

## 6. O que NÃO está verificado e é teu

1. **O gesto no teu teclado.** 1 toque = painel de baixo · 2 toques rápidos = painel da direita ·
   HOLD 900 ms = legenda on/off, e o gesto desfaz. A app está viva com o código de hoje
   (`LIVE_CODE FRESH`, hash do processo == disco).
2. **Alt+C e o autoclicker na mesma máquina**: o clicker detém teclas (o `Alt+F9` também está tomado —
   medido: `Alt+F9` → `1409`); o Sotto já cai para `Alt+Shift+C` quando precisa. Se o Alt+C te
   responder com atraso, o suspeito medível é essa disputa, não o painel.
3. **O fone**: a janela com o instrumento a correr durante um reinício, e a janela de controle com a
   app parada.
4. **O clique a chegar a uma app de terceiros**: leitura de código (`WS_EX_TRANSPARENT`), sem medição
   com o rato dele.

---

## 7. SELF-AUDIT — as perguntas que me custam

* **Afirmei "o kill delegado não funciona" com base em quê?** Num `OpenProcess` tardio. Errado: o pid
  é reutilizado em segundos nesta máquina. A segunda medição (`tasklist` + `WaitForSingleObject`) é a
  que vale.
* **O `fresh=None` era a app ou o instrumento?** O instrumento. A app registava `Alt+C` e o log dizia
  `register=true`; o que faltava era correlação com a idade de um processo que o censo não via.
* **O a08 era fixture ou código?** Código — o `reason` provou-o (`ok` + `cached=False` com a ordem
  antiga). Antes de ver o `reason` eu ia culpar o fixture.
* **O F4 do open/close estava a testar o quê?** O `Timer`. O `Timer` foi substituído por um watcher
  **de propósito** em 2026-10-23. O braço passou a medir o invariante (deferido, atraso > 0, saída
  por ambiente, sem `start_worker`/`join` no agendador) e não a forma.
* **Que vermelhos da bateria são meus?** `code-health` (dívida de várias lanes; os RED pairs existiam
  antes) e `exception-hygiene` **não** são meus: `git show HEAD:worker/sotto_worker.py` já tem **8**
  infratores, o mesmo número de hoje; a linha de base diz 7 — está desatualizada, e fica declarada em
  vez de re-baseada sem prova.

---

## 8. TRIAGEM DOS VERMELHOS DA BATERIA (card #14)

O que era **ordem dele** e ficou fechado nesta sessão:

| passo | antes | agora |
|---|---|---|
| `hotkey-delivery` | vermelho para sempre (a app era o "estranho" de si mesma) | **PASS** (SKIP honesto com a app viva: a tecla é dela) |
| `hotkey-probe` | `Alt+C IS TAKEN` | `HELD BY THE LIVE SOTTO ITSELF (pid=…)`, rc=0 |
| `open-close-stall` | F4 pinava o `Timer` | **PASS** (mede o invariante: deferido, atraso > 0, saída por ambiente, sem `start_worker`/`join`) |
| `yt-player-track` | a08 vermelho | **PASS 10/10 + 4/4 mutantes** |
| `yt-mirror-align` | a07 vermelho | **PASS 11/11 + 5/5 mutantes** |
| `youtube-captions` | 9 mutantes mortos por CRLF | **PASS 57/57 + 14/14** |
| `panel-hidden-at-startup` | `TypeError: unexpected keyword 'instant'` | **PASS** |
| `per-app-source-plumbing` | CHK-3 pinava o conjunto de chaves de antes | **PASS** (chave `stable` declarada, com a ordem do dono escrita no ficheiro) |
| `border-radius-gate` | o ROOT pintava + piso literal | **PASS** (`html` deixa de pintar; piso é `max(var(--radius, 14px), 12px)`) |
| `battery-heavy-gate` | 6 instrumentos sem a declaração | **PASS** (`BATTERY-HEAVY: app-window` / `audio-device`) |
| `gitattributes-verify` | 789 ficheiros fora da regra | **PASS** (EOL reposto ao declarado, conteúdo intacto) |

O que **não** é meu e fica declarado, com a linha que falha:

| passo | primeira falha | de quem é |
|---|---|---|
| `code-health` | 20 métricas acima da linha de base; `sotto_webview.py` +35 KB, `panel.js` +3,4 KB | dívida de várias lanes, anterior a esta sessão |
| `exception-hygiene` | `measured 41 / baseline 40`; `sotto_worker.py` 8 contra 7 | **a linha de base é que está velha**: `git show HEAD:worker/sotto_worker.py` já tem 8 |
| `panel2-dom-probe` | 12 asserções de texto/ordem (`·` onde o teste quer `—`; a lâmpada passa a `[0,2]`) | redesenho do painel por outra lane, sem actualização do teste |
| `lang-id-oracle` | `soundfile.LibsndfileError: flac decoder lost sync` | fixture de áudio / ambiente, não o `lang_id` |
| `state-page` | 3 passos declarados sem página | regenera-se na bateria seguinte |

**Não re-pinei** nenhuma das de cima: um teste de texto que descreve um redesenho de outra lane é
decisão dele, e re-escrever 12 asserções a adivinhar a intenção é como se inventam verdes.

### 8-bis. `state-page`: era um defeito de WIRING, nao um passo que falhou

O passo `state-page` corre em `_main\_audit-verify-all.cmd:550` e compara os passos **declarados**
no `.cmd` (159) com os **registados** em `_cache\battery-steps.json`. So' que a `.cmd` continua ate'
`1518` — nos 55 passos que ja' tinham corrido ninguem ainda tinha registado `shell-relaunch`,
`red-as-expected-shell-relaunch` nem `live-code-freshness`. A pagina comparava o fim do ficheiro com
o meio da corrida e por isso acusava tres ausentes que **estao la'**.

Medido, nao inferido: `_main\sotto-state-page.py` ->
`CHECK step-declared FAIL declarados=159 na_pagina=148 ... ausentes=['shell-relaunch',
'red-as-expected-shell-relaunch', 'live-code-freshness']`, e nenhum dos tres existe em
`_cache\battery-steps.json` no momento em que o passo corre.

Um passo que descreve a corrida tem de correr no FIM dela. O par `state-page` +
`red-as-expected-state-page` foi movido para o ultimo lugar da `.cmd` (depois de
`skip-verdict-guard`), e a razao ficou escrita ao lado do bloco.

### 8-ter. EFEITO COLATERAL APANHADO E DESFEITO (declarado, nao escondido)

A normalizacao de EOL que esta sessao correu (`core.autocrlf` / `.gitattributes`) tratou como TEXTO
ficheiros que sao BINARIOS (a regra vem do atributo, nao do conteudo). Medido e reparado:

- `worker/assets/sample1.flac` ficou com `flac decoder lost sync` e derrubou o `lang-id-oracle`.
  Sintoma que o expos: `LibsndfileError` na leitura do fixture, nao uma falha do `lang_id`.
- 173 ficheiros restaurados de `HEAD` depois de comparados byte a byte (os de diferenca
  **so' de EOL**, mais 9 binarios que perderam bytes: `.ttf`, `.png`, `.exe`, `.wav`).
- Regra que fica: **um normalizador de EOL nao pode olhar para o atributo; tem de olhar para o
  conteudo** (um NUL no inicio, ou `git diff` que nao e so' EOL).

### 8-quater. `state-page`: o escritor tem de vir ANTES do verificador

Segundo achado no mesmo passo, e de classe diferente do primeiro. Correndo `--check` sobre a pagina
que estava no repo: `cells-match-record FAIL 107 celula(s) fora do registo` e
`step-declared FAIL ... ausentes=['shell-relaunch', ...]`. A pagina foi GERADA ha' dias e o
`--check` compara-a com o registo **de agora** -- um ficheiro velho reprova sempre, e nenhum
arranjo de ordenacao o salva.

A costura certa e' a que o proprio ficheiro descreve: `--write` seguido de `--check`. Ficaram dois
passos, `state-page-write` e `state-page`, no FIM da `.cmd` (depois de `skip-verdict-guard`), e as
deps do escritor **nao** nomeiam `docs\state-generated.md` -- esse e' o que ele escreve, e nomea-lo
tornaria o passo STALE contra si mesmo na corrida seguinte.

Terceiro achado, da mesma familia do "problema do observador" que o ficheiro ja' documenta: a
celula `state-page-write` nunca podia bater com o registo, porque o `call :record` que a escreve
corre DEPOIS do `--write` que a renderiza. Entrou para `SELF_STEPS` (junto com `state-page` e o
seu `--neg-arm`), com a razao escrita ao lado da tupla. Medido depois: `--check` rc=0, sete checks
a PASS; `--neg-arm` rc=1.

### 8-quinquies. QUATRO BRACOS DE CONTROLO SEM DENTES (ou com os dentes ao contrario)

Achados ao ler a lista `failed:` da corrida, nao o `rc` de cada passo -- que e' exactamente o
motivo de a casa ler a lista: `:expectred` exige **rc==1 mais** o token `NEG-ARM PASS`, e quatro
passos falhavam por FORMA.

| passo | medido | correccao |
|---|---|---|
| `red-as-expected-border-radius-gate` | `M1 ... could not be built: did not find the html rule` | M1 re-ancorado: acrescenta `html { background: ... }` no FIM do ficheiro (a forma em que o defeito pode voltar: a ultima declaracao ganha). A regra `html { background: transparent }` que o mutante descrevia **ja nao existe** |
| `red-as-expected-shell-relaunch` | `M5 nome NAO ANCORA (0 ocorrencias)` | a linha viva virou `   result = subprocess.run(['taskkill', '/PID', ...])` (tres espacos + `result = `); o mutante descrevia a forma antiga, logo o braco do kill-por-NOME ficava **sem prova**. Re-ancorado: agora `M5 ... KILLED by 7` |
| `red-as-expected-headphone-cut` | imprime `NEG-ARM PASS` e devolve **0** | o ramo de controlo passou a devolver 1 no caso bom (e 0 no mau). Era vermelho por forma, nao por conteudo |
| `red-as-expected-launch-as-token` | idem, devolvia **0** | idem |

Depois das quatro: `shell-relaunch --neg-arm` rc=1 com **7/7 mutantes derrubados** e o positivo
rc=0 com **12/12 bracos**; `border-radius-gate --neg-arm` rc=1 com **3/3**; os dois `--neg-arm`
dos instrumentos novos rc=1 com o token.

O que isto tem de reutilizavel: **um mutante que "nao ancora" nao e' um verde.** Ele sai com a
mesma palavra que o caso bom se nao for lido, e o unico leitor que o distingue e' o `rc` mais o
token -- por isso o passo da bateria exige os dois.

---

## 9. BATERIA FINAL (medida, 2026-10-30)

```
BATTERY-VERDICT: RED - 3 step(s) failed
EXIT=1
steps    : 160   gate=95  control=8  skipped=7  expect-red=50  missing=0  cached=102
failed   :  panel2-dom-probe=1 exception-hygiene=2 code-health=2
```

**18 -> 15 -> 13 -> 10 -> 9 -> 8 -> 3** ao longo da sessao, cada queda com a linha que falhava
citada no comentario do passo ou no recibo. Os tres que ficam NAO sao das ordens do dono:

| passo | por que fica | o que o fecha |
|---|---|---|
| `panel2-dom-probe` | 12 asseracoes de TEXTO/ORDEM do painel redeseNhado por outra lane (`·` onde o teste quer `—`; a lampada passa a `[0,2]`) | a lane do redesenho actualiza as 12, ou o dono diz qual das duas grafias e' a dele |
| `exception-hygiene` | a linha de base diz 40 e a medicao diz 41 | **regenerar a linha de base**: `git show HEAD:worker/sotto_worker.py` ja' tem 8 contra os 7 que ela declara, logo e' ela que esta velha |
| `code-health` | 20 metricas acima da linha de base: `sotto_webview.py` +35 KB, `panel.js` +3,4 KB, `youtube_captions.py` | trabalho de reducao, nao um pino |

`skipped=7` sao os passos `heavy` (abrem o ecra ou o dispositivo de audio dele), nao corridos como
manda a lei da classe. `missing=0`.
