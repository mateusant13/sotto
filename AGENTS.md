# Sotto — contexto do repo para todo agente e subagente
## Owner rule — ship work without paperwork drag (2026-10-31T02:59:01-03:00)
Keep useful behavior and its minimum proof/docs moving in the same fast delivery. Skip optional process artifacts when they cost more than the change. Before agent fan-out or disk-heavy builds/tests, use `fast-land-shared-artifacts`: measure total disk growth, share the sanctioned target/cache across lanes, and serialize instead of duplicating heavy artifacts when sharing is unsafe. This owner direction supersedes older process checklists that add optional work without protecting a concrete risk; keep only minimum proof for correctness, security, data integrity, or destructive work.

## Bend 2 — MANDATORY reference bundle, read before any load-bearing claim (owner, 2026-10-29)
`docs/bend/README.md` is the entry point (ported from consultgpt 2026-10-29, byte-identical copies,
sha256 in that file). Read it, then `docs/bend/BEND_PROOFS_REFERENCE.md`, then
`docs/bend/BEND_LAW_GUIDE.md`. The contract in one line: claims in `LAWS.bend`, proofs in
`PROOF.bend`, gate `bend PROOF.bend --verdict` in WSL `ubuntu-bend` (never `--check-only`), every
law with a negative control that must fail, every law mirrored to the real production function.
A **latency/sync budget is never a law** — it needs a measured falsifier; a law proves only the
ordering underneath it. The goal this bundle serves here: YouTube subtitles on screen, synced
≈1:1 with YouTube — `drift_ms` measured, never a boolean.
## Browser: agent-browser default.
Owner browser: authorized for task-needed authentication; follow this project's access scope.
## Herdr panes (mandatory)
Cap: one visible pane per canonical project across workspaces/worktrees. Create via `python I:/!manager/tools/herdr-visible-pane-budget.py workspace --cwd <root> --label <id>` only; unknown/already-present projects refuse. Reuse main pane; extra workers headless; no raw create/focus/move/close.

## Mandatory task-resolver and model routing
Use `.agents/skills/task-resolver/SKILL.md` for every non-trivial software task. At invocation, classify acceptance rows as mechanical or judgment-based and immediately implement/wire any missing task-relevant deterministic gate before dependent product edits. Follow `.agents/skills/task-resolver/references/model-routing.md`; model quota never idles or blocks a lane.

Transcrição em tempo real de QUALQUER áudio deste PC, mostrada como legendas num overlay global **Alt+C**.
Aceitação do dono, verbatim: *"e eu quero que o alt c mostre as transcricoes em tempo real, de qualquer
audio do meu pc. e legendas."*

> **Este ficheiro foi reduzido ao essencial em 2026-10-21.** O registo histórico completo (1301 linhas,
> 120 232 B) está em **`docs/AGENTS-archive-20261021.md`** — é lá que se procura a proveniência de um
> número antigo, não aqui. Em conflito, vale o arquivo **mais** a re-medição; este ficheiro carrega as
> REGRAS, não a história.


## ONDE ESTA O RESTO (este ficheiro e o indice; o detalhe vive em `docs/`)

| precisa de | le |
|---|---|
| `politica-youtube` | `docs/politica-youtube.md` |
| `hotkey-gestos` | `docs/hotkey-gestos.md` |
| `worker-lifecycle` | `docs/worker-lifecycle.md` |
| `bateria-e-portoes` | `docs/bateria-e-portoes.md` |
| `custo-medido` | `docs/custo-medido.md` |
| `mouse-e-input` | `docs/mouse-e-input.md` |
| `bug-hunt` | `docs/bug-hunt.md` |
| `factos-medidos` | `docs/factos-medidos.md` |
| `layout` | `docs/layout.md` |
| `output-grande` | `docs/output-grande.md` |
| `por-medir` | `docs/por-medir.md` |
| `regras-do-arquivo` | `docs/regras-do-arquivo.md` |
| `modelo-e-decode` | `docs/modelo-e-decode.md` |
| `protocolos-observabilidade` | `docs/protocolos-observabilidade.md` |
| `roadmap-observability` | `docs/roadmap-observability.md` |
| `deepinfer-o-que-transfere` | `docs/deepinfer-o-que-transfere.md` |



## ORDENS EM VIGOR — 2026-10-21 (quatro, do dono)

O detalhe medido de cada ordem vive nos docs. **Uma linha por ordem, e é isto que ninguém quebra:**

| # | a ordem | o que é lei | detalhe |
|---|---|---|---|
| 1 | track do YouTube na língua original | **en, pt-BR e espanhol: a LÍNGUA ORIGINAL, sem tradução em direcção nenhuma** (ordem de 2026-11-04: *"nao e pra traduzir entre ingles pt br e espanhol. nesses 3, é lingua original que da display"*); qualquer outra → inglês | `docs/politica-youtube.md` |
| 2 | Alt+C: o gesto é **medido**, não contado | 1 toque = painel de BAIXO · 2 toques = painel da DIREITA · **HOLD** = legenda ao vivo on/off (desligar é só DISPLAY: modelo e histórico continuam) | `docs/hotkey-gestos.md` |
| 3 | Parakeet é o segundo pass | ao vivo = nemotron só com painel aberto; fundo = Parakeet; retoma atrás de 4 guardas + piso de 45 s | `docs/worker-lifecycle.md` |
| 4 | testes lentos e pesados | cache por **conteúdo**, classe `heavy` nunca corre sem opt-in, **um passo saltado não é um portão que passou** | `docs/bateria-e-portoes.md` |
| 4-ter | o custo do Sotto | 10 processos, pico 1801 MB, worker 104 % de CPU com dois loads; parte do stutter **não** é do Sotto | `docs/custo-medido.md` |
| 5 | o rato não passa pelo Sotto | **nenhum** hook global de input existe em caminho nenhum (o `WH_MOUSE_LL` foi removido a 2026-10-30: um tick de 100 ms lê o foreground, 25 ms a arrastar), e mede-se **pela ausência** | `docs/mouse-e-input.md` |

## MODO BUG-HUNT - OBRIGATORIO PARA QUALQUER DEFEITO REPORTADO (2026-10-23)

Quando o dono reporta um defeito, o trabalho **e** bug-hunt. Protocolo completo (11 passos, contados em
2026-10-25 no `docs/bug-hunt.md`,
cada um com o portao que o recusa) em **`docs/bug-hunt.md`**. O resumo que basta para nao errar:

1. nomear o cluster e o impacto; 2. observado vs esperado, palavras dele verbatim; 3. reproduzir e
guardar a evidencia em FICHEIRO; 4. **uma hipotese + o que a refutaria**; 5. minimizar; 6. corrigir a
CLASSE e varrer os irmaos com a mesma sonda; 7. regressao no estilo certo; 8. provar o detector
(negativo derruba AQUELE braco); 9. cobertura por invocador; 10. replay + verificador != autor;
11. capsula de incidente + `recurrence-watch` com instrumento e janela.

**PASSO 0 — O PROCESSO E' O DA ARVORE?** Antes de julgar qualquer comportamento que ele relata:
`python _main/live-code-freshness-oracle.py --strict`. `STALE` = a app que ele carrega e' anterior ao
codigo; a primeira accao e' **reiniciar**, nao corrigir. `UNKNOWN` nao e' `FRESH`. Nascido de um erro
medido a 2026-10-30: ele carregava numa instancia de 01:12:39 (log com `HOTKEY_SINGLE`, etiqueta com
zero ocorrencias no fonte) enquanto quatro oraculos verdes julgavam FICHEIROS -- ver `docs/bug-hunt.md`.

**`reported` e `fixed` nunca se apresentam como `verified`.**

### MECANICA OBRIGATORIA PARA DEFEITO NAO-TRIVIAL (2026-10-24)

Para defeito **nao-trivial** (o sintoma nao aponta para a linha, ou a correccao pode esconder outra):
carregar a skill **`bug-hunt-sotto`** (`.opencode/skills/bug-hunt-sotto/SKILL.md`), que roteia ao
protocolo de **11 passos** (`docs/bug-hunt.md`, contados em 2026-10-25) e ao exemplo a copiar, `_main/caption-dup-repro.py`;
a mecanica de verificacao — **sete passos**: repro no invocador real, 3 a 5 hipoteses falsificaveis
antes das sondas, uma variavel por sonda, minimizar, replay diferencial, mutacao focal, um registo
unico — vive em `.opencode/skills/postmortem-sotto/SKILL.md` §Mecanica, com o que recusa cada um. Proporcional: para um typo, um numero ou uma linha, nada disto.

## DEPOIS DO INCIDENTE: POSTMORTEM — 2026-10-24

**Invocar `.opencode/skills/postmortem-sotto` (camada deste repo; metodo na canonica
`I:\!manager\.agents\skills\postmortem\SKILL.md`) quando o incidente estiver contido/resolvido, ou
depois de um quase-acidente apanhado.** Com o bug **ACTIVO** nao ha postmortem: fica-se no MODO
BUG-HUNT acima. Os passos, o tracker, o fecho mecanico e as recusas estao na skill — nao se repetem aqui.

## TRES REGRAS DO DONO, ESCRITAS COMO LEI (2026-11-04)

1. **NAO SE TRADUZ ENTRE INGLES, PT-BR E ESPANHOL.** Verbatim: *"nao e pra traduzir
   entre ingles pt br e espanhol. nesses 3, é lingua original que da display."* Um
   vídeo em qualquer um dos três sai **naquela língua**; não há tradução em direcção
   nenhuma entre eles. Só uma língua fora dos três (chinês, japonês, …) vai para
   **inglês**. O código já implementa isto em `app/webview/youtube_captions.py`
   (`UNTRANSLATED_LANGS = ('en', 'pt', 'es')`, com o verbatim de 2026-10-30) -- e a
   regra é dela, não uma preferência: um `pick` no menu dos 3 pontos que fosse traduzir
   um destes três é **clampado**, não honrado.
2. **O NVIDIA NEMOTRON NÃO É TEMPO REAL.** Ele é o motor de transcrição local e o
   atraso dele é medido, não hipotético: não se promete "ao vivo" a partir dele e
   não se desenha caminho que dependa de ele acompanhar o áudio. A legenda que chega
   ao ecrã em tempo real é a do **YouTube** (fonte externa) e, sem ela, a do motor
   local com o atraso que ele tiver -- dito assim, sem eufemismo.
3. **LEGENDA AO VIVO DESLIGADA NÃO É MODELO DESLIGADO.** Verbatim: *"se a legenda
   ao vivo ta desativada, nao signiifca q o modelo ta desativado. é o DISPLAY que ta
   desativado."* O `LIVE_ENABLED on=false` corta **o display**; o modelo continua
   carregado, a transcrição continua a correr e o histórico continua a ser escrito
   (é a mesma lei que o HOLD do Alt+C já carrega). Nenhum caminho pode desligar
   worker, modelo ou histórico a pretexto de "legenda ao vivo desligada".

## A LEI DA STACK (decidida pelo dono)
**nemotron streaming = motor LOCAL, só com o painel aberto. Parakeet Redux = motor GERAL/de fundo**
(batch sobre o áudio acumulado, leve em RAM). *"o nvidia é pro ao vivo, o parakeet redux é pro geral."*
E a correcção do dono de 2026-11-04 vale por cima dela: **o nemotron NÃO é tempo real** (regra 2
acima) — "pro ao vivo" quer dizer *o motor que corre enquanto o painel está aberto*, não *o motor que
acompanha o áudio*.

Escolha do motor de fundo pelo **preço em RAM**, não pelo nome: o ONNX int4 do Redux mede **615 MB** de
pico contra **3,90 GB** do ternário, com transcrição byte-idêntica.

**UM CANDIDATO JÁ' FOI MEDIDO E RECUSADO (2026-10-30): `ARK-ASR-0.6B`.** Não tem `pt` na lista de
línguas e **traduz** em vez de transcrever (no clipe pt-BR de 15 s saiu inglês, com erros); no en-US
gastou 31,25 s para 8,5 s de áudio (0,27×) com pico de 2358 MB, contra 1,25 s (6,83×) e 598 MB do
parakeet int4; e não faz ao vivo (janela de 30 s autorregressiva). Não integrar de novo sem um
checkpoint com português e sem tradução — `_main/receipt-20261030-ark-asr-vs-parakeet.md`,
`_main/engine-compare.py` para re-medir.

## PREMISSAS PROIBIDAS (retiradas pelo dono)
**O Sotto NÃO dá nomes a vozes e ninguém volta a propôr isso.** O objectivo da cadeia de falantes é
**separar o áudio para transcrever cada falante em separado**; *"quem falava quando"* não é o objectivo e
o DER **não** é métrica de aceitação. Verbatim: *"quem falava quando nao é importante, cara... sendo que é
só separar audio pra transcrever cada falante?"*

## HARD RULES para qualquer lane

- **A TELA DO DONO NAO E O MEU BANCO DE ENSAIO (2026-10-23; ordem verbatim, dada DUAS vezes).**
  `SOTTO_NEVER_ON_OWNER_SCREEN`. Ele disse: *"para de abrir essa merda na minha tela. tu vai
  resolver no teu ambiente ai sem encher o meu saco"*, e quando lhe mostrei que a app tem seams
  proprios, *"entao nunca mais faz isso. faz gates ou agents.md"*. Lei: **nenhuma lane lança a app
  de modo a que ela apareça no ecra dele** — nem com `--show`, nem por um harness que a passe por
  ele. Um painel visível é dele: espera pela palavra dele **naquela** sessão. E **nenhum evento
  sintético é evidência sobre a app**: `keybd_event`/`SendInput` medem o Windows — medido
  2026-10-23, os quatro `err=0` do pressionador e **zero** linhas no log do Sotto. O caminho de uma
  lane é o da app: `SOTTO_LANE_LAUNCH=1` + `_main/keepalive.py` (arranca **escondida**, é o estado
  em que ela escreve o `panel-state.json` e o log) e a leitura por
  `app/webview/panel_state.py --read` + `_main/webview-run.log`. Portão:
  `_main/lane-screen-gate.py` na bateria (+ braço negativo); a dívida anterior à regra — 13
  instrumentos com input sintético e 2 harnesses com `--show` — está **congelada** em
  `_main/lane-screen-baseline.json` e **não pode crescer**.

- **UMA LANE PODE LANÇAR A APP — MAS NÃO DESTA PANE (medido 2026-10-23, QUATRO mecanismos).**
  *(A regra acima passou a proibir a largada visível. O que segue não é permissão: é a medição de
  por que a largada DESTA pane falha, e ela continua toda verdadeira.)*
  O dono retirou a regra ("só o LEAD lança"), e a razão dela não era autoridade: era **medição**. Hoje
  voltei a medir e **corrigi duas conclusões minhas**, as duas por o instrumento estar errado:
  `IsInRole(Administrator) = True` **não** mede elevação (um admin com UAC dividido também dá `True`), e
  o WebView2 **não** falha "por o processo estar elevado". O que está medido, com o instrumento ao lado:
  1. **Integridade lida do SID** (`TokenIntegrityLevel`, não do texto do `whoami`): **pane = `medium`**;
     **os dois `explorer.exe` do dono = `high`** (pids 13692 e 48852). O desktop é `high`, a pane é `medium`.
  2. **Lançamento directo da pane** (filho `medium`, `Popen` com as flags do repo): arranca,
     `SINGLE_INSTANCE already_running=false`, `HOTKEY_REGISTERED=true` — e **`TRAY_ICON_ADD ok=false
     winerror=5`** + **`WEBVIEW2_INIT_FAILED 0x80010108 RPC_E_DISCONNECTED`**. Determinístico (três
     medições). É **UIPI**: um processo `medium` não fala com a taskbar/`high`.
  3. **`schtasks /it`:** `TRAY_ICON_ADD ok=true` (é só um ícone — **não é sinal de saúde**) e a app fica
     **SURDA**: o dono pressionou Alt+C e o log não teve **uma linha** de hotkey.
  4. **Token emprestado do Explorer** (`_main/launch-unelevated.py`): o filho **é** `high`, mas **nunca
     executa código** — `pythonw -c "open(...,'w').write(...)"` não escreveu ficheiro nenhum e o processo
     fica com **1 thread / 2 MB**. O `--selftest` da ferramenta passou a exigir **execução**, não só
     integridade, precisamente por causa disto.
  4-bis. **A CONCLUSAO "esta pane nao pode largar" ESTAVA ERRADA, e o erro era do INSTRUMENTO
     (medido 2026-10-30).** O `CreateProcessAsUser` nunca falhou: o pedido de token pedia
     `TOKEN_ADJUST_SESSIONID` (exige `SeTcbPrivilege`) e `TOKEN_ADJUST_DEFAULT`, e **cada um deles
     sozinho derruba o pedido inteiro com `err=5`** — logo parecia "sem acesso". Direito a direito
     contra o token da app viva: `DUPLICATE` ok, `DUP|QUERY` ok, `DUP|QUERY|ASSIGN_PRIMARY` ok,
     `+ADJUST_SESSIONID` err=5, `+ADJUST_DEFAULT` err=5. Com
     `DUPLICATE|QUERY|ASSIGN_PRIMARY` o filho corre no desktop dele e mede `S-1-16-12288` **high**
     (provado por execução: escreveu o próprio pid). A primitiva é **`_main/launch-as-token.py`**
     (`--selftest` exige execução **e** herança do nível; `--neg-arm` repõe o direito culpado e
     exige o `err=5` de volta), e é ela que `_main/sotto-relaunch.py --relaunch` usa **primeiro**,
     com a tarefa `\Sotto` só como recurso — sem instância viva não há token `high` para emprestar.
     O que continua fora de alcance, medido: abrir o token do **pid 4 (SYSTEM)** dá `err=5`, porque
     SYSTEM está **acima** de `high`; isso é o Windows, não uma permissão perdida.
  **O QUE ISSO MANDA FAZER:** o dono abre a app (duplo-clique) ou o autostart abre-a no logon. Uma lane
  **não** deixa uma instância partida a deter `Local\SottoShell`: uma instância velha faz as largadas
  seguintes morrerem em silêncio entre `SHELL_STARTUP_STAGE stage=pre-lock` e `SINGLE_INSTANCE` (medido:
  pids 53136 e 63392, zero linhas, porque `pythonw` não tem stderr), e **um filtro de kill nomeia o
  ARTEFACTO** — o `CommandLine` de um processo alheio vem **vazio**, logo a identidade prova-se pelo
  `pid=` do log + a hora de arranque, nunca pelo `CommandLine`.
- **O TRABALHO PESADO PEDE LICENCA A FROTA (2026-10-24).** Antes de um build, de uma bateria
  completa, de indexacao, de benchmark ou de campanha de mutacao: consultar o estado do gate central
  **`I:\!manager\tools\performance-gate.py`** e obter o **lease `heavy` exclusivo** dele. Com o gate
  **RED** (hoje: pressao de commit **92,5 %**) esses comandos **nao se largam** — continua-se por
  inspeccao de codigo, edicao de docs e diff estatico, que e onde este repo se resolve. Os
  governadores locais (Watcher, bateria) sao sinal **extra** e **nunca** autorizam trabalho pesado
  concorrente por fora do gate central. `unknown` tambem nao e `green`, e um skip nao e aprovacao.
- **Nunca deixar janela de consola visível.** Lançar python com `pythonw.exe` ou
  `creationflags 0x08000000|0x00000008`. Um censo de janelas corre a cada 60 s e loga `ALERTA-JANELA` com
  o pid. O painel também tem de ficar fora do ecrã sem Alt+C/`--show`.
- **NADA EM FOREGROUND — NEM O AGENTE, NEM UM SCRIPT DELE (ordem do dono, 2026-11-02).** Ele viu
  janelas a abrir e a desaparecer na secretária dele enquanto uma lane media, e a pergunta foi direta:
  *"para de abrir janela de terminal em foreground. é tu? ou um .vbs?"*, e logo *"anota no agents.md pra
  tu nunca mais fazer nada em foreground ou ter scripts q façam isso"*. A resposta medida: **era eu** —
  `cmd /c "_main\_audit-verify-all.cmd"` e `powershell -NoProfile -Command …` largados de dentro desta
  sessão alocam uma consola por invocação, que ele vê a piscar. **A LEI:** nenhum agente desta casa
  larga `cmd /c`, `powershell`, `.bat`, `.cmd` ou `start` sem esconder a janela — `cmd /c` vai por
  `_main/hidden-launch.py` (`run(argv)`, que põe `CREATE_NO_WINDOW` + `SW_HIDE`), `powershell` leva
  `-WindowStyle Hidden -NonInteractive`, e `python` leva `pythonw.exe` ou o `creationflags`. Os
  `Popen` do repo que largam `cmd`/`powershell`/`run.cmd` passam todos pelo mesmo helper; os portões
  são `_main/console-window-audit.py` (censo **AST** de cada sítio que larga um processo, o REGEX
  aposentado em 2026-11-04) e `_main/console-window-watch.py` (o vigia vivo), com a dívida anterior à
  regra **congelada** num baseline que não pode crescer (a mesma forma do `lane-screen-gate.py`), e o
  helper ele próprio julgado por `_main/hidden-launch-oracle.py` — que julga o **efeito** (filho sem
  consola, zero janelas de consola visíveis na árvore do filho), porque um portão de texto veria a
  bandeira presente mesmo quando ela está lá **duas vezes** e o `Popen` morre num `TypeError`.
  O detector de campo é o censo `ALERTA-JANELA` e o
  `powershell` com janela **não** é justificação: `-WindowStyle Hidden` custa uma palavra.
- **UM CONTROLO DE INSTRUMENTO NUNCA ABRE JANELA (ordem do dono, 2026-11-04: *"PARA DE MOSTRA
  POP UP"*).** Provei o vigia de consolas largando um `cmd.exe` sem flags de propósito, para o
  detector ter algo para ver — e o que ele viu foi uma janela do Windows Terminal a abrir no ecrã
  dele. O controlo provou o instrumento **e** violou a lei, e a lei ganha. **A MECÂNICA:** o
  controlo corre **puro** — alimenta a função de classificação com uma fotografia FALSA e exige que
  ela seja nomeada (`--neg-arm` em `_main/console-window-watch.py`, 5/5 casos, zero processos e
  zero pixéis). A medição no ecrã faz-se **UMA vez**, com o resultado colado no recibo/commentário,
  e não se repete: um instrumento cujo positivo só sabe falar por uma janela real não tem controlo
  que se possa correr — tem uma fotografia.
### O PORTÃO DAS JANELAS: DUAS PROVAS, CÓDIGO E ECRÃ (2026-11-04)
Um `subprocess` sem `CREATE_NO_WINDOW` herda a consola do pai e **não** abre janela — por isso um
agente que corre de um terminal nunca vê o defeito e o dono, que corre a app em `pythonw`, vê-o
todos os dias. Duas provas, porque uma só mente:

- **CÓDIGO — `_main/console-window-audit.py`.** Censo AST de **1139 ficheiros** (`.py`, `.js`,
  `.mjs`) que resolve o `creationflags`/`startupinfo` **no escopo** (`creationflags=flags` de um
  parâmetro, `=0x08000000 if os.name=='nt' else 0`). Medido hoje: `WINDOW 0`, `NO-FLAG 0`,
  `STRING 0`, `GUARD-EXTERNAL 4` (os quatro verificados à mão: passam `CREATE_NO_WINDOW` do
  chamador), `SCRIPT 313` (`.cmd/.bat/.ps1` — quem os chama é que é o sítio), `USER-GESTURE 2` (o
  *reveal in folder* que o dono clica), `PARSE 0`. Duas correções de instrumento no mesmo dia: a
  detecção de `os.system`/`os.popen` estava **cega** (`ast.dump(Name(id='os'))` não termina em
  `id='os'`) e o grupo do regex de JS lia `child_process.` opcional como nome da função. O
  `--neg-arm` larga um `os.system` num ficheiro temporário e **tem** de dar rc=1.
- **ECRÃ — `_main/console-window-watch.py`.** Larga o alvo com `CREATE_NO_WINDOW` (a condição do
  dono, não a confortável) e observa `EnumWindows` a **40 ms** mais `SetWinEventHook`, porque no
  Windows 11 a consola pode ser `ConsoleWindowClass`, `CASCADIA_HOSTING_WINDOW_CLASS` (Windows
  Terminal como host por omissão) ou `PseudoConsoleWindow`; um censo de uma só classe mente.
  Medido: `--run` dos três oráculos de canal/landmine → **PASS, 0 janelas**. Uma consola que o
  pai não tem aparece em **1,6 s** com três janelas (a medição única citada acima).
- **NENHUM SCRIPT ABRE NADA NA TELA DELE — NEM POP-UP, NEM DIÁLOGO, NEM NAVEGADOR (ordem do dono,
  2026-11-04, verbatim: *"nao faz nenhum script existente ou novo abrir coisa na minha tela tipo pop
  up"*).** A regra de 2026-11-02 proibia a janela de consola em FOREGROUND; esta proíbe a outra metade
  que faltava: uma janela que o dono **vê**. Fica proibido, em todo o código deste repo (produto,
  instrumento, oráculo, braço negativo, harness) e para toda a frota:
  `webbrowser.open*`, `os.startfile`, `tkinter`/`Tk()`/`Toplevel()`, `MessageBoxW/A`,
  `ShellExecute*`, `pywebview.create_confirmation_dialog`/`create_file_dialog`,
  `subprocess` a largar `start`/`explorer`/`mshta`/`rundll32`/`control`/`ms-settings:`/um URL, e no
  JS `window.open(`/`alert(`/`confirm(`/`prompt(`/`shell.openExternal(`.
  O que **pode** abrir: a janela do **próprio Sotto** (painel, overlay, `stage`) — é o produto.
  **O que fazer em vez disso:** escrever o resultado num ficheiro (`out://`, `runs/`, `_main/*.log`) e
  dizer o caminho; um instrumento que precisa de resposta pergunta por ficheiro e volta a ler o
  ficheiro, nunca por caixa de diálogo.
  **Portão:** `_main/owner-screen-gate.py` (987 ficheiros de produto lidos por `ast`/JS sem
  comentários, **0** achados, `--neg-arm` rc=1 a apanhar o mutante que abre um browser), na bateria
  com o seu `red-as-expected-owner-screen`. A dívida anterior à regra vive congelada em
  `_main/owner-screen-baseline.json` e **não pode crescer**.
  Nota que já custou: um dos incidentes antigos deste repo foi um `messagebox` MODAL na tela dele
  (`HOTKEY_UNAVAILABLE alert=messagebox`, a app hangada até ser morta) — o portão existe para essa
  classe, não para uma hipótese.

- **NADA ABRE NA TELA DELE — NEM UM SCRIPT EXISTENTE, NEM UM NOVO (ordem do dono, 2026-11-04).**
  Verbatin: *"nao faz nenhum script existente ou novo abrir coisa na minha tela tipo pop up"*. A
  regra de 2026-11-02 tratava das consolas do AGENTE; esta fecha as do PRODUTO: um `Popen` sem
  `CREATE_NO_WINDOW`, um `powershell` sem `-WindowStyle Hidden`, um `.bat`/`.cmd` largado, um
  `start`, um `os.startfile`, um `webbrowser.open`, um `subprocess` que abre uma janela de
  consola — todos sao pop-up na tela dele. Portoes que EXISTEM: `_main/console-window-audit.py`
  (censo do codigo, `CONSOLE-AUDIT VERDICT PASS -- 0 sitio(s) que abrem janela`, medido
  2026-11-04), `_main/hidden-launch-oracle.py` (4 arms: o helper nao abre janela e espera o
  filho) e `_main/lane-screen-gate.py` (`SOTTO_NEVER_ON_OWNER_SCREEN`, PASS com a divida antiga
  congelada). **O `console-window-gate.py` que esta regra citava nunca existiu nesta arvore** — o
  proprio `.cmd` (:320) o diz; um portao que so' existe na prosa foi a licao de 2026-11-04. Uma
  janela que aparece e
  desaparece em 100 ms continua a ser uma janela na tela dele: o detector de campo e' o censo
  `ALERTA-JANELA` de 60 s, e um pop-up nao se justifica com "foi rapido".

- **Um filtro de kill nomeia o ARTEFACTO**, nunca uma palavra genérica: `sotto_worker\.py`,
  `sotto_webview\.py`, o caminho do exe webview/electron. Filtrar `sotto` já matou dois processos alheios.
- **Áudio de teste é MUDO.** Qualquer teste que renderize áudio usa `_main/mute-audio.py --mute/--unmute`
  (portão: `_main/mute-audio-oracle.py`, 21/21 arms, 8/8 mutantes). A recusa antiga (comparar com o
  endpoint default e sair rc=4) **continua**; o mute acrescenta-se.
- **E MUDAR A DEFAULT NAO BASTA (medido 2026-11-02, 13:1x).** O dono ouviu áudio de teste com o
  `mute-audio.py --mute` aplicado: o `feed_cable` do `device-silence` renderiza para
  `CABLE Input (VB-Audio Virtual Cable)` e o VoiceMeeter encaminha isso para uma saída de HARDWARE que
  **não** é a default — a default era o `VoiceMeeter Input`. O `--mute` muta **um** papel; não prova
  nada sobre o que ele ouve. Censo read-only: `python _main/mute-audio.py --status-all` (41 endpoints
  nesta máquina). Custo de errar: mutei a máquina inteira dele para calar o teste e devolvi 21 endpoints
  à mão; ele reparou, e com razão. **Um instrumento que RENDERIZA áudio (ARM3 do `device-silence`,
  `feed_cable`, o oráculo do mute) não corre numa lane desta máquina**; só correm os que LÊEM — log,
  DOM, unit arms, e os que importam o shell sem abrir dispositivo.
- **O ÁUDIO DO DONO NÃO SE TOCA — NUNCA (ordem verbatim, 2026-11-02: *"nunca mais roda nada que vai
  mutar meu audio ou resetar ele e fazer mutar. acabou de mutar. arruma"*).** A regra anterior dizia
  quem PODE renderizar; esta diz o que **nenhum** agente pode: **mutar, desmutar, zerar volume, mudar a
  default, reiniciar o endpoint ou "repor" o estado de áudio dele**. É `MUST NOT` para toda a frota,
  inclusive para um passo de bateria que a lane larga — medido: a bateria correu `device-silence`/
  `mute-audio-oracle` e o resultado foi ele a ouvir a máquina calada sem pedir. **A MECÂNICA:** todo
  instrumento que ESCREVE num endpoint (`mute-audio.py` sem argumentos de leitura, `--mute`, `--unmute`,
  `executar`/`repor`/`reset` do `device-silence`, qualquer `SetMute`/`SetVolume`) passa a exigir
  `SOTTO_OWNER_AUDIO_OK=1` no ambiente, com recusa `rc=9` e a frase `recusa: audio do dono` quando a
  flag falta; o portão é `_main/owner-audio-gate.py` e o braço negativo larga o instrumento **sem** a
  flag e exige a recusa. E no painel/harness: **ler** é sempre livre (`--status-all`), **escrever** é
  dele. Uma lane que precise de áudio mudo: pede ao dono, não muda o dele.
- **`TMPDIR` = `I:\cc-tmp`.** `G:` enche e mata lanes com ENOSPC.
- **Caminhos nativos `H:\`.** `./node_modules/.bin/electron` não executa (rc=127). E não lançar esse
  binário como app: o Electron está MORTO.
- **Pesos e `history/` vivem só em `H:\sotto`** (`worker/models/` e `history/` são git-ignored, estão
  ausentes de qualquer worktree). Testar/medir sempre em `H:\sotto`; "ausente do worktree" nunca é prova
  de ausência.
- **Lanes editam só os seus ficheiros** (mapa de ownership no brief de dispatch).
- **Nunca fazer grep a `AGENTS.md`/ficheiros de contexto** — são auto-carregados.
- **UI em movimento (scroll, render provisório) não se toca sem instrumento:** `PANEL_STATE_PROBE`
  publica `live.scroll` porque `count` não prova posição.

## REGRAS PARA MANTER O ARQUIVO VERDADEIRO

As oito regras (cada uma custou trabalho refeito) estao em **`docs/regras-do-arquivo.md`**.
A primeira e a que mais se esquece: **"o grep deu ZERO" e uma afirmacao com prazo de
validade - re-correr antes de repetir, e colar os numeros de HOJE.**

## LAYOUT

A tabela de ficheiros e o que cada um e: **`docs/layout.md`**.

**PIN do `run.cmd --help` (medido 2026-11-04 08:4x):** re-measured 2026-11-04 the output is 7538 B, 116 lines, 116 CRLF / 0 bare LF, rc 0, sha256
`D93CFCF13E95BDF3138FF88A1A30C3EFB3B910126DD6267B514FC1F29648D82A`.
(Este número substitui o de 7281 B / 112 linhas: quatro linhas novas no `--help` desde 2026-11-01.) O portão do pin é
`_main/agents-md-pins-oracle.py`: se o `--help` mudar, este número muda, e o gate obriga a re-medir **aqui**.
(Re-medido 2026-11-01 depois das três lanes que tocaram o `run.cmd` — hotkey, load e youtube; era
7061 B / 109 linhas, o número de 2026-10-21.)
(Re-medido 2026-10-30 quando a bandeira `--no-self-relaunch` entrou no shell: era 6934 B / 107 linhas.
A bandeira existe porque o dono nao quer aprovar nada para ver codigo novo -- ver `app/webview/shell_relaunch.py`.)
(O número vai **sem asteriscos**: o braço negativo do portão muta o número com um padrão que exige
`the output is ` seguido dos dígitos — com o `**` do markdown o padrão não pega e o portão perde o
seu braço negativo.)


## ANTES DE TOCAR EM `worker/`
Ler **`docs/model-specs/README.md`** — parâmetros normativos (`blank_id: 13087`,
`max_symbols_per_step: 10`, `chunk_samples: 8960`), contrato de decode, tabela de lang-ids, VAD. **Não
inventar uma convenção de decode** — esse erro já foi cometido uma vez.

## DESVIOS CONHECIDOS DO SPEC

Todos corrigidos; ficam como regra. Tabela completa em **`docs/modelo-e-decode.md`**.

## FACTOS MEDIDOS - ANTES DE AFIRMAR UM NUMERO, LE `docs/factos-medidos.md`

120 linhas nao vazias de medicoes com instrumento e data (contadas em 2026-10-25; o ficheiro tem
123 linhas, as outras sao vazias. Eram 119 quando este numero nasceu). As que mais custam quando esquecidas:

- **O painel no arranque esta numa CONTRADICAO que ninguem resolveu** (reposta 2026-10-24: a
  condensagem de 748 -> 205 linhas de 2026-10-21 apagou esta nota e o portao
  `panel-flash-contradiction-oracle.py` ficou vermelho, como devia). Dois lados do mesmo instrumento:
  o censo de 25 ms mede `live` 0/20 com a janela mapeada (4/20 sem a cura).
  o bullet histórico do mesmo instrumento mede 18/20 e 88/130 amostras visiveis.
  É **NÃO reconciliada** -- e ninguem escolhe um lado antes de acreditar num dos dois. Instrumento:
  `_main/panel-startup-flash-census.py`. (`run.cmd` cita ainda um terceiro numero do mesmo
  instrumento, 11 de 20, tambem por reconciliar -- esta e a razao de a nota viver no AGENTS.md e nao
  so em `docs/`.)

- **A legenda que o dono VE e a NATIVA** (`caption_overlay.py`), nao o `caption.html`: corrigir CSS
  em `app/panel/` **nao chega ao ecra** nessa via.
- **A transicao carrega so a linha que o worker FECHOU** (`route=final`); `provisional-draft` e a
  legenda ao vivo e NAO entra no historico.
- **`app/panel/history-store.js` nao esta na pagina servida**; o escritor real e
  `sotto_webview.py history_append` com a sua propria tupla de rotas.
- **A maquina do dono esta degradada** (I: 0,4 % livre, 722 processos): um arranque custa 53-127 ms.
  Parte do stutter nao e do Sotto.
- **A duplicacao no historico dele, medida 2026-10-24** com `_main/caption-dup-repro.py` (10 ficheiros,
  2077 linhas): **79 iguais consecutivas**, **0** de crescimento por prefixo, **6** de sobreposicao
  (janela deslizante). O numero antigo "517 de 2077" **nao se reproduz** com nenhuma destas tres
  relacoes e fica retirado. Re-mede-se com um comando, nao com uma citacao.
- **`app/_legacy-electron/` e MORTO**, e `app/package.json` anuncia uma toolchain morta (npm aqui nao).

## OUTPUT GRANDE

Limite `max_lines: 600` / `max_bytes: 24576`; o bypass `__notrunc__`; o tecto de 512 KB.
Detalhe completo em **`docs/output-grande.md`**.

## A BATERIA

Duas baterias: **`_main\_audit-verify-all.cmd`** (principal) e **`instruments-battery.mjs`**
(segunda; o header diz `Launches NOTHING`). Como correr, o que cada classe significa
(`record`/`control`/`expect-red`), o cache por conteudo, a classe `heavy` e o veredicto:
**`docs/bateria-e-portoes.md`**.

**O exit code E o veredicto.** Ler `BATTERY-VERDICT` + exit code, nunca o `rc` de um passo nem a
ultima linha, e confirmar que so ha UM `steps=`. **Um passo saltado nao e um portao que passou.**

- **PIN do ficheiro (medido 2026-11-04, 10:4x):** `_main\_audit-verify-all.cmd` = **207323 B**,
  **2594 CRLF** / 0 bare LF, sha256 `6D35879EFFCABF78F703C469D2F0F142A7C3BD4CC0C62B2E5EE62CDEF42D4917`.
  (Mil duzentos e quarenta e quatro bytes depois do pin de 206079 B: os dois passos de
  `line-closed` -- a linha que o worker FECHOU nao espera o prazo de 1500 ms, e o
  seu braco negativo -- com onze linhas de comentario e seis de passo.)
  (O pin de 206079 B substituiu o de 204847 B com os dois passos de `tap-first-block`.)
  (Este pin substitui o de 198855 B / 2491 CRLF, DEPOIS dos dois passos do `webview2-args-scope`
  (+ `red-as-expected-webview2-args-scope`): o `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS` herdado do
  processo que larga a app abria um porto de depuracao em TODAS as janelas WebView2 dela e fazia o
  MESMO binario comportar-se diferente na sessao do dono (sem o valor) e na de uma lane (com ele).
  A shell passou a REMOVER o valor herdado (`app\webview\webview2_args.py`, chamado dentro de
  `apply_webview2_environment`), com `--cdp-port N` / `SOTTO_CDP_PORT=N` para uma sessao de
  depuracao explicita, e o oraculo executa a funcao REAL num processo com o ambiente envenenado:
  12 arms + 3 mutantes. O pin anterior substituia o de 197671 B / 2476 CRLF, DEPOIS de tres passos
  da RECUPERACAO DE ENERGIA
  E SESSAO: `power-recovery` (28 arms: `classify`/`plan`/entrega, incluindo uma janela real desta
  maquina a receber um `WM_POWERBROADCAST` de verdade), o seu `red-as-expected-*` (3 mutantes) e
  `power-recovery-live` (classe `heavy`: larga a app escondida, entrega `WM_POWERBROADCAST` e
  `WM_WTSSESSION_CHANGE` ao WndProc REAL e exige as linhas `POWER_RESUME` -- medido 9/9).
  Nascido de um buraco medido: `grep` de `WM_POWERBROADCAST|WM_WTSSESSION_CHANGE|
  WTSRegisterSessionNotification` em `app/webview/sotto_webview.py` devolvia ZERO.)
  (Este pin substitui o de 196865 B / 2466 CRLF, DEPOIS de mais dois passos: `topmost-keepalive` --
  o laco de 2 s que devolve `WS_EX_TOPMOST` a uma janela que o perdeu, copiado do RE de 2026-11-04
  (Perssua e Handy) -- e o seu `red-as-expected-*`. Os dois `always`: leem `app\webview\topmost_keepalive.py`,
  que muda a cada edicao. Medido ao vivo nesta sessao: `TOPMOST_KEEPALIVE_STARTED hwnd=1713376
  interval_s=2.0` e ZERO `TOPMOST_REASSERT` em 4 minutos -- o laco nao gasta USER32 quando o bit esta' la'.)
  (Este pin substitui o de 196003 B / 2456 CRLF, DEPOIS de mais dois passos: `youtube-rate` --
  o `playbackRate` no relogio interpolado da legenda (a 2x o video andava o dobro e a palavra
  chegava tarde) e o atraso de leitura que agora tem NOME (7 arms) -- e
  `click-through-applied` -- o bit de hit-test que passa a ser LIDO de volta e insistido com
  `SWP_FRAMECHANGED` quando o Windows o recusa, copiado do Perssua/Live-Subtitles (5 arms),
  cada um com o seu braco negativo. O `code-health` absorve o crescimento declarado.)
  (Este pin substitui o de 195043 B / 2444 CRLF, DEPOIS de o `:fastskip` passar a registar o log na
  lista de skips declarados. Defeito medido por um run completo de 2026-11-04: o
  `skip-verdict-guard` acusou `1 of 25 step log(s) carry an undeclared skip verdict` para
  `hotkey-delivery`, `paint-live-show` e `youtube-land` -- os tres SAO classe `heavy` e foram
  saltados nesse run, mas `:skipped` registava `SKIPLOGS` e o ramo `:fastskip` nao, por isso o log
  velho (que diz `VERDICT: SKIPPED` desde a ultima vez que correu) ficava sem declaracao ao lado e
  o guarda lia-o como um passo que mente. As duas linhas novas sao a MESMA instrucao que `:skipped`
  ja tinha: `for %%F in ("%~3") do set "SKIPLOGS=!SKIPLOGS!%%~nxF,"`.)
  (Este pin substitui o de 195043 B / 2444 CRLF, DEPOIS do par `worker-churn` +
  `red-as-expected-worker-churn`, que fecham o LACO DE RECARGA medido no log vivo de 2026-11-04:
  `BRIDGE_SILENT ms=30000 pid=26440` as 03:20:13 matou um worker que estava QUIETO porque um tap
  aberto sobre uma maquina quieta nao escreve nada por desenho (`endpoint-idle` ->
  `stop.wait(0.1)`, e `WORKER_STATS` nao conta enquanto `blocks` nao avanca); e `BRIDGE_EXIT rc=0`
  as 03:22:41 respawnou as 03:22:43 -- **2,0 s**, ou seja 1,9 GB de modelo recarregado para um
  worker que terminou por vontade propria. O worker publica agora `WORKER_ALIVE` a partir do
  PROPRIO laco (prova de progresso: cala-se quando o laco trava, para o cao de guarda nao ficar
  decorativo) e uma saida limpa tem piso de 20 s (`CLEAN_EXIT_FLOOR_MS`). O oraculo corre o
  `WorkerBridge._schedule_restart` REAL com um `threading.Timer` falso (arm 1 = 20000 ms com piso,
  arm 2 = 1000 ms sem ele), a regra do LEITOR `line.startswith(PROGRESS_TAGS)` sobre a linha que o
  worker escreve de facto (arm 3: o batimento conta, `BRIDGE_METER` nao) e o `progress()` do worker
  REAL (arm 4); `--neg-arm` muta o piso numa copia do shell e o `progress` numa copia do worker e
  exigem as duas arms RED.)
  **A ARMADILHA QUE CUSTOU A TARDE, escrita para nao se repetir:** o bloco de stderr do
  `_pump` termina num `continue`, e uma copia do ramo colocada DEPOIS dele e' inalcancavel.
  Medido: duas instancias carregaram a cura (o worker batia `seq=516 phase=window`, provado
  com o `py-spy`, e o `stderr_tail` mostrava as linhas) e NENHUM `BRIDGE_ALIVE` saiu; o py-spy
  `--locals` no fio `sotto-worker-stderr` mostrou a ultima linha processada a ser o batimento,
  o que localizou o `continue`. O ramo vive agora DENTRO do bloco, antes do `continue`.
  (O pin de 193503 B / 2427 CRLF veio do par `hotkey-live-edge` +
  `red-as-expected-hotkey-live-edge`: o dono reportou *"control espaco nao ta funcionando"* e
  *"funciona so' de vez em quando"*, e o log vivo mediu `HOTKEY_OBSERVER_ALIVE max_gap_ms=281..609`
  contra um toque de 120-200 ms -- o toque caia inteiro entre duas voltas. A cura le o bit 0 de
  `GetAsyncKeyState` (a borda que o Windows guarda), sem hook global; o oraculo corre o observador
  REAL com `key_state` injectado e o negativo tira o bit 0 de uma COPIA e exige `presses=0`.)
  (Este pin substitui o de 190395 B / 2389 CRLF, DEPOIS do par `emit-prewebview` +
  `red-as-expected-emit-prewebview`: quando o WebView2 NAO inicializa (`WEBVIEW2_INIT_FAILED`
  `0x80010108`, medido 02:48:24 numa instancia propria) o `core` fica a `None` e cada amostra
  do medidor escrevia um `WARN POSTED_CALLABLE_FAILED ... 'NoneType' object has no attribute
  'ExecuteScriptAsync'` -- **541 linhas em ~60 s** com a legenda do YouTube a CHEGAR e a nunca
  poder ser pintada. O oraculo corre o `emit_async` REAL (50 pushes sem pagina => UMA linha
  `EMIT_ASYNC_PREWEBVIEW` e zero excepcoes; com pagina o payload mais novo TEM de sair) e o
  negativo desliga a CONDICAO numa COPIA e exige a arm vermelha com `AttributeError`.)
  (Este pin substitui o de 188724 B / 2367 CRLF, DEPOIS do par `hidden-launch` +
  `red-as-expected-hidden-launch`: `_main/hidden-launch.py` e' o unico caminho que larga um
  filho nesta arvore -- `cmd`, `powershell`, `.cmd` e `python` passam todos por ele -- e
  `run()`/`popen()` passavam `creationflags=` DUAS vezes ao `Popen`, logo `run(['cmd','/c',
  r'_main\_audit-verify-all.cmd'])` morria num `TypeError` ANTES de arrancar o filho e NENHUM
  passo corria: foi exactamente o que aconteceu a primeira tentativa de corrida desta sessao.
  O oraculo julga o EFEITO no sistema operativo (o filho diz `GetConsoleWindow()==0`, o censo
  nao ve' NENHUMA janela de consola visivel na arvore do filho, e `run` espera: 3 s de filho
  => >=3 s) e o `--neg-arm` repoe o `TypeError` numa COPIA e exige as QUATRO arms vermelhas
  com rc=1 -- medido `4 / 4`.)
  (Este pin substitui o de 188128 B / 2361 CRLF, DEPOIS de o `console-window-gate` de REGEX ser
  aposentado e trocado por tres passos: `console-window-audit` (censo **AST** de 1139 ficheiros
  que resolve o `creationflags` NO ESCOPO -- `WINDOW 0 / NO-FLAG 0 / STRING 0 /
  GUARD-EXTERNAL 4 / SCRIPT 313 / PARSE 0`), o seu `red-as-expected` (rc=1 ao apanhar um
  `os.system` temporario) e `red-as-expected-console-window-watch` (controlo **puro** do vigia
  de ecra: 5/5 casos, nenhum processo e nenhuma janela). Duas correccoes de INSTRUMENTO vieram
  com a troca: a deteccao de `os.system`/`os.popen` estava **cega** (`ast.dump(Name(id='os'))`
  nao termina em `id='os'`) e o regex de JS lia o `child_process.` opcional como nome da
  funcao -- dai o censo ser AST e nao regex.)
  (Este pin substitui o de 187060 B / 2349 CRLF, DEPOIS do par `emit-pipe-dead` +
  `red-as-expected-emit-pipe-dead`: o `emit` do worker deixou de levar traceback quando o pai fecha o
  cano -- medido no log do dono, `BRIDGE_DEATH_CAUSE OSError: [Errno 22] Invalid argument` com
  `rc=1 deaths=1 kind=error` e uma recarga de 14-26 s por um erro que nao existe. 5 arms verdes no
  positivo, 4 vermelhas no `--neg-arm`.)
  (Este pin substitui o de 186207 B / 2339 CRLF, DEPOIS do par `job-object` +
  `red-as-expected-job-object`: o job object kill-on-close que faz a ARVORE morrer com a shell.
  Medido antes da cura: um `taskkill /T /F` deixava quatro `msedgewebview2.exe` orfaos a deter o
  mutex, e as largadas seguintes abortavam em 20 s; medido depois, a arvore de 8 processos morre
  sozinha (`da arvore ANTIGA ainda vivos: NENHUM`). Os dois bracos: positivo (o filho morre com o pai)
  e negativo (sem job o filho SOBREVIVE), ambos verdes.)
  (Este pin substitui o de 185176 B / 2328 CRLF, DEPOIS do par `owner-screen` +
  `red-as-expected-owner-screen`: o portao que recusa qualquer script abrir janela no ecra do dono --
  ordem verbatim de 2026-11-04, *"nao faz nenhum script existente ou novo abrir coisa na minha tela
  tipo pop up"*. 987 ficheiros de produto lidos, **0** achados, `--neg-arm` rc=1.)
  (Este pin substitui o de 184217 B / 2319 CRLF, DEPOIS do par `yt-target-stale` +
  `red-as-expected-yt-target-stale`: o oraculo do ALVO MORTO, nascido do defeito medido no browser do
  dono -- o id declarado `m_bJQ4G1Ht8` ficou **164 linhas** no log com a unica aba de video aberta a
  mostrar outro video, porque `pick_target` filtra as abas por esse id e, sem foto, o id tambem nunca
  se curava. 7 arms; o `--neg-arm` derruba quatro (STALE-TARGET, STALE-ID, CONNECT, SOURCE-NAME).)
  (Este pin substitui o de 182965 B / 2306 CRLF, DEPOIS do par `caption-lag-budget` +
  `red-as-expected-caption-lag-budget`: a idade do AUDIO que esta' no ecra (`tap_ms` do worker ->
  `CAPTION_PAINT_LAG audio_ms=` na pintura), com o orcamento de 1500 ms a gritar
  `CAPTION_BUDGET_BLOWN`. Nasceu da pergunta do dono, verbatim: *"tu nao tem a porra de um teste
  ou log que mostra a discrepancia entre audio detectado e display na tela? nao tem nada que grita
  que o budget de ter mostrado ja passou do ponto?"* -- nao tinha: o `CAPTION_OVERLAY_LAG` media a
  FILA (0-300 ms) e nao o audio, e o log nem levava `start`/`end`/`final`. Medido na sessao dele
  (pid 4992, 17:17:59-17:18:03): cinco legendas distintas entraram em 4 s e o painel publicou UMA
  linha com as cinco encadeadas -- sem numero nenhum no log a dizer de que instante era aquele
  audio. O braco negativo roda DOIS mutantes (orcamento de 10**9 e `tap_ms` que nao viaja).)
  (Este pin substitui o de 177560 B / 2246 CRLF, DEPOIS dos sete oraculos de 2026-11-03 entrarem com
  o seu braco negativo (`async-track-fetch`, `batch-queue-drain`, `hotkey-live-toggle`,
  `loading-placeholder`, `youtube-land` -- skip-capable, le o log vivo -- `youtube-land-replay`,
  `yt-loop-uia`). Duas CORRECCOES DE INSTRUMENTO vieram com eles: a ancora do `yt-loop-uia` citava
  `return [], False` e a cura devolve hoje `return '', _src, True`, o que dava `NEG-ARM IMPOSSIVEL`
  com rc=2; e cinco `--neg-arm` saiam 0 ao apanhar o mutante, quando o `:expectred` exige rc=1.
  O `battery-wiring-oracle` passou a casar o basename inteiro -- media `name in line` e contava
  `der-oracle.py` como ligado dentro de `loading-placeholder-oracle.py`.)
  (Este pin substitui o de 176391 B / 2233 CRLF, DEPOIS dos dois passos do `caption-cumulative`:
  medido no log VIVO do dono (pid 18156, 11:45) que o motor do painel CONCATENAVA a mesma linha
  quando o `start` nao chegava -- ele leu `Ig u a galera ig u a galera do a esquerda ig u a galera
  do a esquerda tava gravando.` com o worker a mandar as tres versoes cumulativas limpas. O
  oraculo empurra as quatro formas pelo motor REAL (sem meta, com meta, frase nova, repeticao
  exacta) e o braco negativo apaga a cura numa COPIA e exige o braco A vermelho, devolvendo
  exactamente a linha errada do dono.)
  (Este pin substitui o de 173418 B, DEPOIS de o `battery-wiring-oracle` recusar TRES
  oraculos escritos e fora da bateria -- `caption-producer`, `caption-style` e
  `hotkey-observed` -- e de os tres passos entrarem com o seu `red-as-expected`.
  Os tres `--neg-arm` respondiam rc=0 e passavam a rc=1, que e' a convencao da
  casa: o negativo devolve 1 quando apanha os mutantes, senao o passo passa como
  um oraculo normal e o mutante nunca e' recusado. Ligados: 82 -> 85.)
  (Este pin substitui o de 171635 B, DEPOIS do par `youtube-cdp-source` + o seu
  `red-as-expected`: com a aba do YouTube em segundo plano o Chrome para de expor a
  legenda na arvore de acessibilidade (medido 2026-11-03: 3 minutos com um UNICO
  `YOUTUBE_CAPTION`), e a fonte passou a ser o DOM do player pela CDP -- 10 ms, as
  linhas do `.caption-visual-line`, e o `video.currentTime` no mesmo snapshot. O
  portao executa as decisoes reais de `app\webview\youtube_cdp_source.py` (7 arms) e
  o `--neg-arm` derruba cada uma numa COPIA do modulo (3/3). A arm que proibe
  `Emulation.setFocusEmulationEnabled` nasceu de uma medicao lado a lado: 2-5 ms
  sem ele, 108 ms de mediana e 5 s de p90 com ele.)
  (Este pin substitui o de 170272 B, DEPOIS do par `youtube-verbatim` + o seu
  `red-as-expected`: as tres imagens do dono de 2026-11-02 sao o mesmo caminho --
  *"sotto devia ta copiando 1:1 sem truncar palavras"*, a linha que se construia ao
  longo do cue em vez de aparecer no timing do YouTube, e o ecra vazio com o player
  a desenhar duas linhas. O ramo pintado devolve agora as LINHAS do player
  (`youtube_window.painted_lines`), sem a janela por relogio de palavra que cortava
  em `cap = min(pintado, relogio)` -- dai a meia palavra e o cue anterior
  empilhado por baixo do actual. O braco negativo corta a ultima palavra numa
  COPIA e derruba tres arms.)
  (Este pin substitui o de 166642 B / 2134 CRLF, DEPOIS das tres portas que nasceram das ordens
  dele de 2026-11-02 — `console-window-gate` (+neg: nenhuma chamada nova a `cmd`/`powershell`/`.cmd`
  sem `CREATE_NO_WINDOW`; a divida anterior ficou congelada em `_main/console-window-baseline.json`,
  hoje **0**), `owner-audio-gate` (+neg: escrever num endpoint exige `SOTTO_OWNER_AUDIO_OK=1`, senao
  `rc=9` com `recusa: audio do dono`; o journal escreve o volume ANTERIOR antes de o sobrescrever e
  `--repair` devolve-o) e `worker-providers` (+neg: um CUDA **disponivel e nao escolhido** e' o
  fallback silencioso medido hoje — 10,75x com CUDA contra 2,27x em CPU). Os passos de audio
  (`mute-audio`, `device-silence` e o seu negativo) passaram a `:skipped`: sem a bandeira do dono
  dizem `VERDICT: SKIPPED` e a bateria conta-os como SKIPPED, nunca como verde.
  O pin anterior, de 166642 B / 2134 CRLF, substituiu o de 165353 B / 2118 CRLF, DEPOIS dos dois passos do `tap-silent-desktop`:
  a escada de dispositivos abriu **12 clientes WASAPI em 3 minutos** com o desktop em silencio
  (sessao viva pid 4404, `device-rotated reason=flat` a cada 15 s, sempre `peak=0.0`), e cada
  abertura e' um hitch no motor de audio que o dono partilha. `silent_desktop_hold` pergunta ao
  medidor VIVO no fim da janela plana e, quando ninguem esta' a tocar em endpoint nenhum,
  ESTENDE a mesma tap (6 s -> 12 -> 24 -> 48 -> 60 de tecto) em vez de a fechar e reabrir. O
  oraculo executa a funcao real com 8 arms e mais 6 bracos de fiacao; o `--neg-arm` desliga a
  guarda numa COPIA ao lado do original e exige os arms 1-2 vermelhos. `{}` do medidor nunca e'
  "sem sinal": mantem o comportamento anterior. Texto unico porque o portao do pin le um so'.)
  (Este pin substitui o de 164144 B, DEPOIS dos dois passos do `rss-trend`: o worker publica
  `rss_mb` em cada `WORKER_STATS` e a shell so' o guardava na cauda da morte -- o numero
  existia exactamente quando ja' nao havia o que medir, e "leak" era uma afirmacao sem
  medida. Agora a shell escreve `BRIDGE_RSS rss_mb=.. blocks=..` uma vez por minuto e o
  passo julga a FORMA da serie (fuga linear = FLAG; aquecimento que assenta = ok; dente de
  serra = ok; serie curta = UNKNOWN, nunca verde). O negativo poe o limiar em 1e9 e a arm da
  fuga tem de cair.)
  (Este pin substitui o de 162703 B, DEPOIS dos dois passos do `silence-kill`: das 10
  `BRIDGE_SILENT` anomalas do log do dono, **9** sao seguidas no mesmo pid do `BRIDGE_EXIT`
  `rc=1` que o `TerminateProcess` do proprio shell devolve, e o `_wait` publicava-o como
  `BRIDGE_DEATH kind=error` -- painel vermelho e recarga contada como falha num worker que
  transcrevia. O caso de 19:36:40 tinha `CAPTION_APPLIED count=200` 0,4 s antes: o `blocks`
  congela dentro de um lote longo e o cao de guarda mata quem trabalha. Agora o kill publica
  `BRIDGE_KILLED` + `killed=true`, e `REDUX_BATCH_KICK`/`REDUX_ENGINE_DONE`/`REDUX_MODE`
  contam como progresso. Cinco arms + dois mutantes (marca do kill, PROGRESS_TAGS).)
  (Este pin substitui o de 22:5x, 161422 B / 2073 CRLF, DEPOIS dos dois passos do `death-cause`:
  a morte de um worker `rc=1` custa uma recarga de 14-26 s, e a cauda de stderr que o
  `BRIDGE_DEATH` publicava tinha TRES linhas -- `WORKER_STATS` + `REDUX_BATCH_KICK` -- com o
  traceback de fora: medido 2026-11-02 na sessao do dono a jogar, duas mortes (19:22:29 e
  19:36:40) ficaram indiagnosticaveis. Agora a cauda guarda 40 linhas e a morte publica
  `BRIDGE_DEATH_CAUSE <excecao>`. O braco negativo repoe `STDERR_TAIL_MAX = 3` numa COPIA e
  derruba a arm da retencao.)
  (Este pin substitui o de 19:1x, 158822 B / 2043 CRLF, DEPOIS de QUATRO passos novos desta noite:
  `caption-seam-dedup` + `red-as-expected-caption-seam-dedup` e `agc-peak-ceiling` +
  `red-as-expected-agc-peak-ceiling`. Os dois nasceram da MESMA medicao no caminho VIVO sobre 30 s do
  loopback `VoiceMeeter Input` do dono (`SOTTO_FILE_TAP`): o `WORKER_STATS` publicava
  `peak_out=1.000000` em TODOS os ticks com ganhos ate +23,5 dB -- o `np.clip` DEPOIS do ganho, ou seja
  topos achatados -- e a linha saia `tem umas tem umas youtuber` porque o chunk N+1 re-decodifica o rabo
  do N. O carry do predictor NAO se desliga: medido no MESMO audio, sem ele o run inteiro morre para
  `Caram Tem`, logo a cura do seam e` de TEXTO, em `join_fragments`. Braco negativo do teto: desarma
  `if g > g_ceiling` num TOKEN numa copia do worker e da` RED com `peak_out=1.0000`; o do dedup poe
  `SEAM_REPEAT_MIN_WORDS = 1` e derruba a arm que protege a fala (`nao nao` tem de sobreviver).)
  (Este pin substitui o de 03:1x, 157244 B / 2027 CRLF, DEPOIS dos dois passos do
  `reveal-park` e do seu `red-as-expected`: o dono reportou, na sessao dele, *"transcricao
  ao vivo nao ta funcionando"* e *"a animacao da legenda que e' copiada do youtube ta errada
  ... reaplicando a animacao atual"*. O log dele mediu as duas: `BRIDGE_STOP
  reason=external-captions` as 18:52:13 com `spawns=1` ate' ao fim (8 min sem microfone) e 18
  `YOUTUBE_CAPTION` todas `why=painted-other-track` com o relogio do UIA a saltar de segundo em
  segundo. Cinco arms + tres mutantes, cada um a derrubar o SEU braco.)
  (Este pin substitui o de 01:1x, 156033 B / 2011 CRLF, DEPOIS dos dois passos do `nemotron-weights`
  e do seu `red-as-expected`: a 2026-11-01 16:28 o `worker/models/` foi esvaziado e o worker morreu no
  arranque com `model dir not found`, e nada na bateria perguntava se o motor AO VIVO tinha pesos. Os
  dois leem o `genai_config.json` REAL e exigem os tres numeros normativos (`blank_id=13087`,
  `chunk_samples=8960`, `max_symbols_per_step=10`) e os tamanhos dos grafos; o braco negativo muta o
  `chunk_samples` numa COPIA e exige o RED. Nenhum dos dois faz rede: um portao que descarrega e um
  portao que falha offline. Repor e' `python _main/fetch-nemotron.py`, com a revisao fixada.)
  (Este pin substitui o de 16:5x, 155976 B / 2011 CRLF, DEPOIS de a linha do `redux-transcript-path`
  passar de `:record` para `:expectred`: declarada com `:record`, um passo que EXIGE rc=1 contava
  como passo normal a espera de 0 e a bateria publicava-o em `failed` -- e o `state-page` tinha
  razao ao dizer `sem :expectred declarado`. Com `:expectred` a mesma linha exige rc=1 E a frase
  `NEG-ARM: PASS` no log. Ver `_main/receipt-20261101-batch-transcript-path.md`.)
  (Este pin substitui o de 15:3x, 154856 B / 1999 CRLF, DEPOIS dos dois passos do
  `redux-transcript-path`: o oraculo que executa as tres metades do caminho da linha do
  BATCH ate ao disco (a decisao `transcriptRoute`, o call site `recordHistory` e o escritor
  `_history_provenance`) e o `red-as-expected` que exige os quatro mutantes RED. Nasceu do
  defeito medido: o motor de batch emite `{type,text,start,end,producer:'redux'}` sem `route`
  e sem `final` (`worker/redux_batch.py:185`) e o choke point recusava-a uma instrucao ANTES
  da guarda que a aceita — 2084 linhas na loja, **zero** `route=batch`.)
  (Este pin substitui o de 14:0x, 153624 B / 1985 CRLF, DEPOIS dos dois passos do
  `stall-under-load`: o oraculo que julga as janelas de carga da sessao VIVA
  (`BRIDGE_SPAWN` -> `BRIDGE_LOAD_MS`) e recusa um unico `UI_THREAD_STALL` dentro delas.
  Medido na sessao de 13:5x: 4 janelas, 0 estalos. O terceiro braco do `--neg-arm` e' de
  ESPECIFICIDADE -- um estalo FORA da janela nao pode ser contado.)
  (Este pin substitui o de 12:5x, 150261 B / 1950 CRLF, DEPOIS do merge da lane do
  dispositivo/silencio -- dois passos novos, `device-silence` e o seu negativo, que julgam o
  endpoint que ABRE e nao entrega um bloco: o worker saia rc=0 e agora sai 3 com
  `no-callback-blocks`.)
  (Este pin substitui o de 12:4x, 148889 B / 1936 CRLF, DEPOIS dos dois passos do
  `paint-live-show` -- o oraculo que le o log da instancia VIVA do dono e exige `paint_ack=true`
  e `wait_ms<=400` em cada `PANEL_SHOWN`; sem show desde o arranque ele diz `VERDICT: SKIPPED`
  e o passo skip-capable conta-o como SKIPPED, nunca como verde. `--neg-arm` medido
  `cases=3 caught=3`. O MESMO certificado se aplica ao caminho pelo qual o ficheiro se editou:
  `open(..., 'w')` sem `newline=''` na LEITURA converte CRLF em LF e deixa 1950 LF soltos.)
  (Este pin substitui o de 2026-11-01 11:0x, 146485 B / 1910 CRLF, DEPOIS dos tres passos do
  PRIMEIRO FRAME do painel: `panel-paint-first-measure` (classe `heavy`, larga a instancia privada
  do censo e grava `_main\_cache\panel-paint-first.json`), `panel-paint-first` (re-julga essa
  leitura pela mesma funcao `verdict()` do censo, sem largar nada) e
  `red-as-expected-panel-paint-first` (quatro mutacoes de uma leitura limpa, todas tem de ser
  recusadas). Medido nessa corrida: `cured [0,0,0]` / `uncured [19,0,0] first_content 325,0 ms`
  / controles `54` e `0`; `--neg-arm` deu `NEG-ARM cases=4 caught=4`.
  (**Pin de `_main/_audit-verify-all.cmd`, medido 2026-11-01 15:3x: 154856 B, 1999 CRLF / 0 bare LF,
  sha256 `F4DC0090...EBDA8B`**,
  depois do passo `red-as-expected-strip-surface` (14 linhas: 10 de comentario e 4 de passo).
  O passo nasceu `always` e o portao `battery-class-oracle` deu RED com razao -- o comando nomeia
  o proprio largador da app, e a classe e' lida do COMANDO; afrouxar o portao para este caso seria
  o gate a servir o passo. Passou a `heavy` (as corridas que o exercitam correm com
  `SOTTO_BATTERY_HEAVY=1`), e o `--neg-arm` do proprio portao da' rc=1.
  O instrumento `_strip-surface-probe.py` julgava 26 assercoes sem NENHUM controlo: o
  `--neg-arm` le o relatorio da corrida anterior, muta a LEITURA em tres sitios e exige os tres
  RED pelo mesmo `judge()` que publica o veredicto — mutar o `checks` ja' calculado provaria so'
  a aritmetica do `any()`, medido: nasceu com dois mutantes NOT-CAUGHT e passou a 3/3 depois de a
  derivacao do censo mudar para dentro do `judge`. E o censo do arranque passou a medir o ECRA
  (`on_screen` pela uniao dos monitores) e nao o bit `WS_VISIBLE`: medido 15:01:23.381, a janela
  existe em (1528,12) **6 ms ANTES** do seu proprio `PANEL_VISIBILITY_AT_STARTUP visible=false` as
  15:01:23.387 — a "startup dance" que a shell ja' registava — e um censo que conta o bit publica
  a cura do primeiro frame como violacao da lei do arranque escondido. As amostras anteriores a'
  declaracao ficam REGISTADAS no relatorio, nunca apagadas.)
  O pin anterior era o de 2026-11-01 11:0x, 146485 B / 1910 CRLF, sha256 `52d9d6ee...ffe611`,
  DEPOIS dos dois passos do portao `undefined-names`; e o de 2026-10-30 12:5x era
  145028 B / 1894 CRLF, sha256 `6D2F4EA8...ACC221`.)
  (O pin de 2026-11-01 12:2x, 148354 B / 1931 CRLF, sha256 `23626cf4...58369`, foi o de dois
  passos do contrato dispositivo/silencio: `device-silence` e `red-as-expected-device-silence`
  (21 linhas: 15 de comentario e 6 de passo). Nasceu de um defeito medido ao vivo: um endpoint
  que ABRE e nao entrega um unico bloco de callback saia com rc=0 -- o unico valor que todo
  chamador le' como sucesso; agora sai 3 com `no-callback-blocks`, e o mesmo ficheiro exige a
  shell a pintar `no-audio`.)
  DEPOIS dos dois passos do portao novo `undefined-names` (+ `red-as-expected-undefined-names`,
  16 linhas: 9 de comentario e 7 de passo). O portao nasceu de um defeito medido duas vezes
  no mesmo dia em producao: o worker morreu no arranque com `NameError: name
  'REDUX_LIVE_DEFAULT' is not defined` e o caminho do DESPEJO chamava `slice_blocks` quando o
  nome e' `_slice_blocks` — nenhum `py_compile` e nenhum import da bateria os apanha.)
  (Este pin substitui o de 151485 B DEPOIS de o ficheiro ter sido truncado a 0 B por um
  `io.open(p,'wb')` que levantou no `write()` — o truncate acontece antes do erro. A recuperacao:
  `git show HEAD` (115 passos) + os 28 passos que `_cache/battery-steps.json` provava que existiam,
  cada um reconstruido com o comando PROVADO pelo rc do registo (`_main/_battery-restore-steps.py`).
  O que esta medido hoje: **171 passos declarados, 169 no registo, 0 em falta**.
  A reconstrucao declarou os passos novos como `always` e dois deles -- `shell-relaunch` e o seu
  negativo -- EXERCITAM o auto-relancamento: o log da app tem dois `SHELL_STARTUP_STAGE` (pids 8992
  as 12:07:05 e 33300 as 12:09:12) nascidos nos dois minutos em que a bateria correu. Passaram a
  `heavy` e o portao novo `_main/battery-class-oracle.py` recusa qualquer passo `always` cujo
  comando nomeie um largador da app (3 arms + `--neg-arm`, ambos verdes).
  Era 151485 B / 1960 CRLF antes disso.
  (Era 151439 B antes de as duas etapas do `load-shedding` passarem a nomear `worker\sotto_worker.py`
  nas dependencias: as arms 6-7 do oraculo executam o LEITOR e o DECISOR reais desse ficheiro, e uma
  dependencia que nao o nomeia deixaria a etapa em cache a descrever um worker que ja' mudou.
  A bateria a seguir mediu **steps=164, failed=1** (`code-health`, o ratchet dos dois ficheiros
  onde a ordem aterrou). Era **29** falhas no inicio da sessao.)
  (O run de 11:5x que esta nota citava como `failed: -none-` **NAO E' EVIDENCIA**: a `.cmd` foi
  truncada a 0 B as 12:0x e todos os runs depois disso correram outro ficheiro. O run que conta e'
  o de 2026-10-30 13:3x, com a `.cmd` reconstruida: **steps=171 gate=100 control=8 skipped=9
  expect-red=54 missing=0, failed: -none-, exit-code 0, BATTERY-VERDICT: GREEN WITH 9 SKIPPED**
  (os 9 sao a classe HEAVY, que nao corre sem `SOTTO_BATTERY_HEAVY=1`).
  Recibo: `_main/receipt-20261030-battery-restore-and-gates.md`.)
  (Era 148686 B / 1928 CRLF antes dos dois passos do `ladder-signal` -- a escada de dispositivos do
  worker passa a perguntar ao medidor VIVO em cada rotacao, e a guarda de som impede o
  auto-relancamento de reiniciar a app com audio a tocar. Nasceu da queixa do dono de 2026-10-30,
  verbatim: *"por que a merda do meu audio ainda some? arruam caralho"*, medida em 3 060 linhas
  `device-rotated reason=flat` e num painel a dizer `No audio to transcribe` com o sinal noutro
  endpoint.)
  (Era 147736 B / 1917 CRLF antes do passo `state-page-write`: a pagina e' GERADA e o `--check`
  compara as celulas dela com o registo VIVO, logo um ficheiro de dias antes reprova sempre --
  medido, `cells-match-record` 107 celulas e tres passos que a pagina ainda nao conhecia. O par
  passou a ser `--write` e DEPOIS `--check`, no fim da `.cmd`, com as deps do escritor a NAO
  nomearem `docs\state-generated.md` (esse e' o que ele ESCREVE).)
  (Era 147313 B / 1910 CRLF antes de o par `state-page` + `red-as-expected-state-page` ser MOVIDO para
  o FIM da `.cmd`: ele compara os passos DECLARADOS (159) com os REGISTADOS em `_cache\battery-steps.json`,
  e a correr em `:550` acusava de ausentes tres passos que ainda nao tinham chegado a vez --
  medido, `ausentes=['shell-relaunch','red-as-expected-shell-relaunch','live-code-freshness']`.
  Um passo que descreve a corrida corre DEPOIS dela.)
  (Era 147313 B / 1910 CRLF antes dos dois passos do `headphone-cut` — o instrumento que junta o
  canal do Windows (`IMMNotificationClient`, via `pycaw` em `_main/_libs`) com as linhas de audio do
  `webview-run.log` e diz QUEM cortou, e o `--neg-arm` que prova que uma janela vazia NAO acusa
  ninguem: `desconhecido` nunca e' inocencia. Os dois `always` porque leem o log vivo e o estado do
  dispositivo, que mudam a cada segundo.)
  (Era 146335 B / 1898 CRLF antes dos dois passos de `launch-as-token` +
  `red-as-expected-launch-as-token`: o `--selftest` que larga um filho com o token de um processo
  ja' `high` e exige que ele EXECUTE e HERDE o nivel da fonte, e o braco negativo que repoe
  `TOKEN_ADJUST_SESSIONID` no pedido e tem de voltar a `err=5`. Os dois `always` porque leem a
  integridade viva da maquina.)
  (Era 140391 B / 1831 CRLF antes dos quatro passos de 2026-10-30 -- `word-clock`,
  `red-as-expected-word-clock`, `youtube-switch` e `red-as-expected-youtube-switch`: a revelacao
  palavra a palavra medido contra o relogio do proprio YouTube, o fade da linha nova, e o custo da
  troca de faixa contado com uma rede FALSA (duas extracoes de yt-dlp -> 27 s de ecra vazio, medido
  no log dele as 04:40:02; agora uma).)
  (Era 140255 B / 1827 CRLF antes de os passos `search-twin-parity` e
  `red-as-expected-search-twin-parity` serem APOSENTADOS: o segundo motor da busca, em
  JavaScript, NAO EXISTE na arvore -- `grep -rn soundex --include=*.js .` da' **0** ficheiros,
  a versao com `const SOUNDEX` so' vive no indice do `stash@{0}` (commit 3120551, nunca em
  HEAD), e o painel chama `historyApi.search` do SHELL (`panel.js:3309,3323`), que e' a unica
  implementacao. O passo positivo estava vermelho por desenho (`SOUNDEX table not found`) e o
  negativo publicava rc=0 ao MESMO tempo -- dois vereditos sobre um ficheiro que nao tem o que
  o oraculo julga. A busca continua provada por `search-oracle.py` e
  `panel-search-keyboard-oracle.py`; um segundo motor pede um portao novo.)
  (Era 139081 B / 1813 CRLF antes do par `load-shedding` + `red-as-expected-load-shedding` --
  o SHEDDING POR CARGA (ordem do dono, 2026-10-30 cumprida): `alta` desliga o nemotron e deixa o
  parakeet, `muito-alta` desliga os dois, e a TABELA nao tem nivel nenhum que largue o AUDIO, que e'
  sempre "fica para processar depois". O oraculo le a tabela e a histerese do modulo (26 arms) e le,
  na CLASSE do shell, que a accao esta' DESARMADA por omissao -- medido: o worker nao tem canal de
  controlo (`sotto_worker.py` nao le' stdin), por isso o unico lever para o nemotron leva o parakeet
  tambem; ligar isso automaticamente a partir de um limiar nao calibrado na maquina do dono seria
  desligar a transcricao por causa de um build. `SOTTO_LOAD_SHED_ACT=1` arma; sem ele o monitor
  escreve `LOAD_SHEDDING level=.. commit_pct=..` a cada mudanca de nivel e nao toca em nada.)
  (Era 137701 B / 1797 CRLF antes do par `altc-first-caption` + `red-as-expected-altc-first-caption`:
  a linha de aceitacao do Alt+C passou a medir a **ACCAO** do gesto (`LIVE_ENABLED`/`PANEL_SHOWN`)
  contra 1500 ms, e nao "pressao -> pintura de texto". MEDIDO na sessao real de 2026-10-30
  (`pid 33288`): **264 ms**. O ficheiro antigo emparelhava uma pressao de **2026-10-15** com uma
  pintura de **2026-10-30** -- quinze dias e um arranque de shell pelo meio -- e publicava
  **57 105 ms** contra os 1500 ms; o numero era do INSTRUMENTO. O custo de carregar o motor
  (54 s medidos) passou a ser INFORMACAO desse passo e nunca portao.)
  (Era 137532 B / 1797 CRLF antes do par `altc-gesture` + `red-as-expected-altc-gesture`, que
  SUBSTITUI os tres passos do contrato antigo do Alt+C (`hotkey-cycle`, `hotkey-gesture`,
  `hotkey-triple`): os ficheiros foram apagados porque mediam 1/2/3 pressoes dentro de uma janela,
  que o dono aposentou em 2026-10-30 com *"1 tap = painel de baixo, 2 taps = painel da direita,
  HOLD = legenda ao vivo on/off"*. O numero do gesto passou a viver so' em
  `app/webview/hotkey_gesture.py` e o shell le-o por `hotkey_numbers()`.)
  (Era 135712 B / 1777 CRLF antes dos dois passos do `youtube-monotonic` — a
  legenda que NAO RECUA no tempo: `youtube_monotonic.decide` + o replay do log
  real (regra antiga recua 157 vezes, pior 310,68 s; regra nova 0) e o
  `red-as-expected-youtube-monotonic`. Nasceu da queixa do dono de 2026-10-30:
  *"a legenda nao ta sincronizada direito. e parece que repete a legenda de
  instantes atras no ao vivo, depois desbuga, e mostra ao vivo"*.)
  (Era 133826 B / 1753 CRLF antes dos dois passos do `youtube-sotto-drift` —
  o NOSSO overlay contra o PLAYER, em `drift_ms`: `drift_sotto_ms` = -125.0 ms
  (mediana -74.0), `drift_player_ms` = +125.0 ms.)
  (Era 133171 B / 1746 CRLF antes do passo `red-as-expected-incomplete-word` — o braco
  negativo que DESLIGA a regra no ficheiro vivo e tem de dar RED.)
  (Era 132069 B / 1728 CRLF antes do passo `incomplete-word` — a palavra que ainda nao esta
  provada nao vai para o ecra, owner 2026-10-30: *"faz sotto identificar palavras que ainda nao
  estao completas e nao dar display ... 'so' sem esperar virar 'sou'. em qualquer lingua"*.)
  (Era 130522 B / 1713 CRLF antes dos dois passos do `bend-laws-model` + `red-as-expected-bend-laws-model` —
  o modelo Python das leis, que e uma AMOSTRA e nao uma prova, e por isso traz o seu braco negativo.)
  (Era 130522 B / 1713 CRLF antes dos quatro passos do YouTube 1:1 — `youtube-reveal`,
  `red-as-expected-youtube-reveal`, `youtube-rows`, `red-as-expected-youtube-rows`, `youtube-drift`,
  `red-as-expected-youtube-drift` e `bend-laws` — e antes de as dependencias do passo `bend-laws`
  passarem a nomear os onze `NEGATIVE_*.bend`: uma dependencia que nao os nomeia deixaria o passo
  em cache a descrever um conjunto de controlos que ja mudou.)
  (Era 122461 B / 1611 CRLF antes dos dois passos do `receipt-provenance` — o portao da proveniencia
  de ROTA: um recibo declara a rota que **correu**, medida por `providerID=` + `session=ses_...`, e nao
  a rota que a politica sonda primeiro. Nascido do defeito medido 2026-10-26: o recibo do lane dizia
  `OpenCode Go 1` e o processo que o escreveu corria em `opencode-go-3`.)
  (Era 120706 B / 1593 CRLF antes de as dependencias do passo `youtube-1to1` passarem a incluir
  `app\webview\sotto_webview.py`: a arm `reveal-wired` le o caminho vivo desse ficheiro, e uma
  dependencia que nao o nomeia deixaria a arm em cache a descrever um shell que ja mudou.)
  (Era 120510 B / 1591 CRLF antes de o comentario do passo `youtube-1to1` deixar de dizer que o
  positivo era vermelho por desenho: em 2026-10-26 o cue passou a carregar o `tOffsetMs` do
  payload e o prefixo revelado bate em 677/677 amostras — palavras, quebras e timing ja batiam.
  Era 118761 B / 1574 CRLF antes do check do 1:1 — `_main/youtube-1to1-oracle.py` e o seu braco
  negativo `red-as-expected-youtube-1to1`: 9 linhas de comentario e 8 de passo, os dois `always`
  porque leem o payload em `_main\fixtures` e a cache em `_cache`, e o passo POSITIVO esteve
  vermelho por desenho ate essa correcao (`word-reveal-1to1`: 69 segmentos com `tOffsetMs` no
  payload, 0 offsets nos cues servidos) — o vermelho era o defeito do dono, nao uma regressao.
  Era 116990 B / 1558 CRLF antes do P3.2 `_main\complaints-reconcile-gate.py`, a reconciliacao das
  duas listas de reclamacoes do dono, e o seu braco negativo `red-as-expected-complaints-reconcile`:
  7 linhas de comentario e 6 de passo, os dois `always` porque a populacao inclui o corpus em
  `I:\!manager\...`, que o `_stepcache` nao consegue fingerprintar por viver fora do repo — um
  resultado em cache descreveria um corpus que ja mudou. O pin anterior era 116990 B / 1558 CRLF,
  antes do P3.1 — `_main\battery-wiring-oracle.py`, o ratchet do wiring, e o
  seu braço negativo `red-as-expected-battery-wiring`: 7 linhas de comentário e 6 de passo. O baseline
  tem tecto **124** pinado no código e a população usa os **mesmos cinco globs** do
  `tooling-intent-oracle.py`, para não haver duas definições de "oráculo de enforcement"; o *wiring* é
  lido das linhas `call :step` da própria `.cmd`. O pin anterior era 115613 B / 1544 CRLF, antes do
  P0.2 — `_main\sotto-state-page.py`, a página de estado gerada, e o
  seu braço negativo `red-as-expected-state-page`: 8 linhas de comentário e 6 de passo. Os dois passos
  são `always` **de propósito**: as verificações leem a evidência viva (`_cache\battery-steps.json` e
  `_main\_audit-verify\*.log`), e um resultado em cache descreveria um estado que já não existe; custo
  medido 2026-10-25, 3,49 s. O pin anterior era 114291 B / 1530 CRLF, antes dos dois portões de
  2026-10-25 07:04 — `task-resolver-gate` e `claims-date`,
  cada um com o seu `red-as-expected-*`: 31 linhas (15 de comentário e 16 de passo) e dois portões que
  provam, um, que o mandato do task-resolver é mecanismo, e o outro, que nenhuma afirmação numérica
  deste ficheiro vive sem data. O pin anterior era
  110748 B / 1491 CRLF antes do passo `caption-dup-repro` — o laco do B5: 4 linhas de comentario
  e 4 de passo, e a prova do detector vive **dentro** do passo (fase 4), por isso nao ha um
  `red-as-expected-*` separado. Era 108675 B / 1464 CRLF antes do portão `lane-screen-gate` e do seu braço negativo
  `red-as-expected-lane-screen-gate` — a lei `SOTTO_NEVER_ON_OWNER_SCREEN`: 14 linhas de comentário
  e 8 de passo, e o detector lê **código** e não comentários, para não castigar quem documenta a
  regra; era 106254 B / 1435 CRLF antes dos portões `external-resume` e `code-health` e dos seus braços
  negativos; era 104966 B / 1420 CRLF antes do `tooling-intent`; era 102238 B / 1388 CRLF antes dos
  portões `seam-coverage` e `bug-ledger`; era 100866 B / 1373 CRLF antes do `exception-hygiene`; era
  99622 B / 1358 CRLF antes do `input-path`. Ver §5, §5-bis, MODO BUG-HUNT e `docs/quality-protocol.md`.)
  (Era 98209 B / 1343 CRLF antes do portão `youtube-foreign-paint` e do seu braço negativo
  `red-as-expected-youtube-foreign-paint` — 15 linhas de comentário + 8 de passo, e o
  comentário do opt-in que diz por que a linha lê o VALOR e não a existência —
  `if not "%SOTTO_BATTERY_HEAVY%"=="1"` — e a linha `heavymode:` do sumário, que passou a
  ler o valor pela mesma razão: com `defined`, um `SOTTO_BATTERY_HEAVY=0` (o que o censo põe)
  anunciava `heavymode: ON` e corria os pesados. O mutante **M5** do portão existe
  exactamente para essa linha não voltar.) O `.cmd` tinha 95344 B / 1310 CRLF antes do
  **portão do open/close**, do **modo rápido/incremental**, do **`fast-skip` nos passos
  skip-capable**, do **portão das bordas** (`border-radius-gate` + o seu braço negativo
  `red-as-expected-border-radius-gate`) e da **CLASSE PESADA + a PRIORIDADE
  `BelowNormal`** (ver §4-bis) e o portão dela (`battery-heavy-gate` +
  `red-as-expected-battery-heavy-gate`). O portão do pin é
  `_main/agents-md-pins-oracle.py` - se o `.cmd` mudar, o número muda, e o gate
  obriga a re-medir **aqui** em vez de deixar um número velho.

## POR MEDIR / NAO ATRIBUIdo

O que esta declarado e nao medido (e por isso nao se afirma): **`docs/por-medir.md`**.
**`verified` continua impossivel de uma lane** - sem verificador independente e sem corrida real
da app; o ledger imprime `FIXED, NOT VERIFIED`.

## COMO APROFUNDAR
`docs/AGENTS-archive-20261021.md` (a história completa, com os números verbatim) ·
`docs/shell-contract.md` · `docs/model-specs/README.md` · `docs/audit/` · `_main/receipt-*.md`
(cada correcção traz o seu recibo: instrumento, braço negativo, pin).

## Owner amendment — worker model routing (2026-10-25)

Agent/reviewer fallback (mandatory): free routes first; then DeepSeek V4.1 Flash through OpenCode Go 1–6 in order, then MiniMax M3.1 through provider `minimax` only. Group similar review tickets; after free reviewers exhaust, use one paid reviewer per distinct subject. Model quota never leaves a lane idle or blocked; reroute and keep other work moving. Full rules: `.agents/skills/task-resolver/references/model-routing.md`.

## Owner amendment — paid worker time budgets (2026-10-25)

Paid DeepSeek and MiniMax lanes use task-sized ceilings, not work quotas: allow at least 300 seconds to first output and 1,800 seconds wall time by default, longer for broader tasks. The live performance lease must outlast the wall ceiling plus cancellation/cleanup margin. If a heavy-process lease cannot cover a task, split the heavy work and continue non-heavy/independent items; never idle or mark the lane blocked for model/lease exhaustion. A timeout triggers route/liveness diagnosis and retry; it does not erase work or prove provider failure.
