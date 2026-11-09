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

### USAR O NAVEGADOR E O YOUTUBE SEM APARECER NA TELA DELE (medido 2026-11-04)

Ordem dele, verbatim: *"tu pode usar meu youtube e meu navegador. só que dessa vez, no background. nao
me atrapalhando. quando descobrir como fazer no background, anota no agents.md"*.

**O metodo, e por que ele e' este:** `agent-browser` ja' e' **headless por omissao**, e no Windows um
Chrome headless largado pelo CLI **corre num desktop privado** (`skills get core --full`: "locally
launched headless Chrome uses a private desktop to prevent visible desktop rectangles"). Nao ha janela:
nao ha o que esconder, e nao ha `--headed` em caminho nenhum desta casa.

MEDIDO, nao lido: censo das janelas `Chrome_WidgetWin_1` VISIVEIS antes e depois de uma sessao headless
que abriu o YouTube — **4 e 4, o mesmo conjunto** (as dele: Twitch, ChatGPT, Discord, VS Code), e
`document.title` da sessao deu o titulo real do video (`MOZIBMBHK-8`). A sessao tambem nao pode ser o
`chrome` dele: nomes de sessao separados, um por tarefa.

```bash
S=$(agent-browser session id --scope worktree --prefix yt-evidence)
agent-browser open "https://www.youtube.com/watch?v=<id>" --session "$S"
agent-browser eval "document.title" --session "$S"
# as linhas pintadas vem do DOM do player, a mesma fonte que app/webview/youtube_cdp_source.py le:
agent-browser eval "(()=>{const c=document.querySelectorAll('.ytp-caption-segment');return c.length?c[c.length-1].textContent.slice(0,90):'no-captions'})()" --session "$S"
agent-browser close --session "$S"
```

Tres avisos que custaram medicao:
- **`no-captions` antes de o video tocar** nao e' ausencia de legenda: sem play nao ha cue. Um
  `eval` que devolve `no-captions` diz isso e mais nada.
- **O perfil dele NAO se copia.** A skill do `agent-browser` e' explicita ("do not copy a browser
  profile"), e uma copia do perfil e' uma sessao autenticada a passear por um disco que enche. Para
  uma pagina que exige o login dele, a via e' `--auto-connect --pin-tab` sobre o Chrome que ja' esta'
  aberto (nao abre janela; confirmar `title`+URL do tab exacto antes de agir), nunca uma copia.
- **Nao navegar num tab dele.** `--auto-connect` sem `--pin-tab` no tab certo mexe na sessao que ele
  esta' a usar. Se o tab necessario nao estiver la', o caminho e' a sessao headless propria.
## Herdr: cross-project coordination only, never the default
Default is to stay in the current harness (this session, this worktree). Use Herdr only when coordination genuinely spans canonical projects -- a decision or artifact another project's lane must receive. Ordinary project work must not create/focus/move/close a pane, and must not rewrite this file's routing/instructions; a routing edit needs an explicit owner request or a real cross-project need. When Herdr is genuinely needed: cap one visible pane per canonical project across workspaces/worktrees; create via `python I:/!manager/tools/herdr-visible-pane-budget.py workspace --cwd <root> --label <id>` only; unknown/already-present projects refuse; reuse the main pane; extra workers headless; no raw create/focus/move/close.

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
| 1 | track do YouTube na língua original | **en, pt-BR e espanhol: a LÍNGUA ORIGINAL, sem tradução em direcção nenhuma** (ordem de 2026-11-04: *"nao e pra traduzir entre ingles pt br e espanhol. nesses 3, é lingua original que da display"*); **qualquer outra → a língua ESCOLHIDA, default pt-BR** (ordem de 2026-11-08: *"mas pra traduzir o resto pra linguagem que eu escolhi pro sotto. que no caso é pt br"*), persistida em `_main/caption-settings.json` | `docs/politica-youtube.md` |
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

**A CURA JA' ESTA' NO FICHEIRO NAO E' A CURA JA' ESTA' NO PROCESSO (medido 2026-11-08).** Uma DM
de stutter acusou a arvore dele as 21:1x e a cura do spin do onnxruntime, commitada as 21:08,
estava a ser julgada num worker arrancado as 13:38 -- 149 % de um nucleo a correr codigo velho. Duas
coisas, e a segunda nao e' dele:

* **O WORKER nao precisa da mao dele.** E' um processo separado lido do disco em cada arranque: mata-se
  pelo ARTEFACTO (`cmdline` contem `sotto_worker.py`, verificado ANTES do kill -- um filtro de kill
  nomeia o artefacto, nunca a palavra) e a shell respawna sozinha em **1,0 s** (`BRIDGE_EXIT rc=15` ->
  `BRIDGE_RESTART reason=exit ladder=retry in_ms=1000` -> `BRIDGE_SPAWNED` + `BRIDGE_LOAD_MS ms=8906`).
  Medido na mesma instancia em 2026-11-08 18:31: **146,2 % -> 42,0 % de um nucleo** e o io da shell **5 963 -> 25 ops/s** (e, depois de assentar, 3,6 %).
  A prova e' `_main/shell-thread-cpu.py <pid> --seconds 8 --top 8` antes e depois, com pid e tid.
* **A SHELL so' entra num arranque novo** -- `--no-self-relaunch` esta' posto, e uma lane NAO poe a app
  na tela dele. O recibo diz `fixed, NOT verified` e nomeia o que falta: `UNMEASURED` ate' ele reiniciar.

Corolario: um numero de CPU/io medido numa arvore `STALE` mede o codigo velho, e um stutter "resolvido"
sem dizer qual pid, qual fio e qual linha e' um stutter nao resolvido.

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
   nenhuma entre eles. O código já implementa isto em `app/webview/youtube_captions.py`
   (`UNTRANSLATED_LANGS = ('en', 'pt', 'es')`, com o verbatim de 2026-10-30) -- e a
   regra é dela, não uma preferência: um `pick` no menu dos 3 pontos que fosse traduzir
   um destes três é **clampado**, não honrado.

   **CORRECÇÃO DE 2026-11-08, e ela substitui a metade "vai para inglês".** Verbatim:
   *"eu ja falei pra NAO traduzir entre pt br ingles e espanhol entre si. mas pra
   traduzir o resto pra linguagem que eu escolhi pro sotto. que no caso é pt br. entao
   eu to vendo um anime agora, e a legenda ta aparecendo japones."* e *"faz o botao de
   config pra eu escolher pra qual lingua traduzir."* Uma língua fora dos três vai para
   a **língua escolhida** (default `pt`), e a escolha é um valor **persistido**
   (`app/webview/caption_settings.py` -> `_main/caption-settings.json`, escrito pelo
   menu dos 3 pontos), não um literal. O original é o SEGUNDO pedido, não o primeiro:
   medido, `_target_langs('ja')` devolvia `('en', 'ja')` -- o inglês não existe para um
   vídeo japonês sem faixa inglesa, logo o anime saía em japonês. Agora devolve
   `('pt', 'ja')`. Portão: `_main/youtube-captions-oracle.py` (66 arms, `--neg-arm`
   18/18 mutantes, rc=1).
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

## DUAS ORDENS DE 2026-11-08: O TECTO DE FRAME E O `>>` DO PLAYER

1. **A ANIMACAO DA LEGENDA PODE IR ATE' 240 Hz** (verbatim: *"acho que a animacao da
   legenda pode ir ate 240hz"*). O tecto vive em `app/webview/word_fade.py`
   (`FRAME_S = 1/240`, `FRAME_HZ = 240`); **o tecto nao e' a taxa**: `caption_overlay`
   limita cada pedido ao custo MEDIDO da pintura e escreve `CAPTION_FRAME_LIMIT
   want_hz=.. paint_ms=.. rate_hz=..` quando limita. Medido no tamanho real da caixa
   (1040 x 240 px, escala 2.0): a pintura gasta **11,6 ms**, logo o tecto efectivo e'
   ~86 Hz; o laco entrega **218 quadros/s** com pintura nula e **71** com a de hoje.
   **O relogio do frame e' `time.perf_counter`, NAO `time.monotonic`**: nesta maquina o
   `monotonic` avanca de **15,000 ms** em 15,000 ms (medido, 200 000 leituras), e todo o
   prazo de quadro era aritmetica sobre ele -- 240 Hz lia-se como "0 ou 1 tique" e o
   proprio 60 Hz saia em degraus de 15/31 ms. Recibo com as duas tabelas:
   `_main/receipt-20261108-caption-clock-and-marker.md`.
2. **O MARCADOR DE FALA DO YOUTUBE NAO SE TRANSMITE** (verbatim: *"o youtube escreve >>
   em algumas legendas. nao transmita isso pro sotto"*). O `>>` (`&gt;&gt;` antes de
   descodificar, `>>` depois, `\u203a\u203a` na faixa automatica) e' do PLAYER e morre na
   ENTRADA de cada caminho -- `youtube_window.strip_speaker_markers` e' o dono unico da
   lista, e `youtube_cdp_source.parse_snapshot` o aplica a `rows`, `items` **e** `segs`
   (carregando o irmao PELO CAMINHO: um `import` por nome resolve so' com o diretorio da
   app no `sys.path`, e sem ele um fallback divergente deixa o `>>` do MEIO da linha
   passar -- medido). Portao: `youtube-cdp-source-oracle.py`, arm
   `sem-marcador-de-fala` (19/19, `--neg-arm` 15/15).

## A LEI DA STACK (decidida pelo dono)
**nemotron streaming = motor LOCAL, só com o painel aberto. Parakeet Redux = motor GERAL/de fundo**
(batch sobre o áudio acumulado, leve em RAM). *"o nvidia é pro ao vivo, o parakeet redux é pro geral."*
E a correcção do dono de 2026-11-04 vale por cima dela: **o nemotron NÃO é tempo real** (regra 2
acima) — "pro ao vivo" quer dizer *o motor que corre enquanto o painel está aberto*, não *o motor que
acompanha o áudio*.

Escolha do motor de fundo pelo **preço em RAM**, não pelo nome: o ONNX int4 do Redux mede **615 MB** de
pico contra **3,90 GB** do ternário, com transcrição byte-idêntica.

**O `parakeet-ultra` FOI RE-MEDIDO NO RUNTIME DO FABRICANTE E CONTINUA FORA — por DISCO, não pelos
motivos de 2026-11-04 (medido 2026-11-08).** A recusa antiga comparava dois runtimes (o NOSSO export
ONNX do ultra contra o redux ONNX int4) e dizia "3,5× mais lento, 2,1× de RSS e TRUNCA". No MESMO
runtime Photon/kestrel, com CUDA, a quente (p2–p3, três passagens por braço): 90 s → **0,750–0,849 s**
no ultra contra **0,699–0,731 s** no redux; 15 s → 0,162–0,172 s contra 0,165–0,201 s; 8,5 s →
0,133–0,155 s contra 0,156–0,160 s. Ou seja: **paridade**, e a VRAM também (`3 160 MB` contra
`3 206 MB`). O truncamento era do **nosso export** (a cabeça de duração não sai do checkpoint para
peça >22,5 s e devolve 3 440 tokens id 0); o modelo devolve 90 s completos, 54 palavras. O que fica
de pé é **só o disco: 1 256 514 499 B contra 179 015 759 B = 7,02×**, mais o primeiro passe (5–20 s
contra 0,97 s). Com o `I:` a 0,4 % livre e o motor de fundo escolhido pelo preço em RAM, 7× o disco
não se paga por um ganho de qualidade que **não está medido** (nos clipes curtos o texto é
carácter-a-carácter igual, e não há transcrição de referência para um WER). Recibo com as duas
tabelas: `_main/receipt-20261108-parakeet-ultra-photon.md`; re-medir com
`_main/_cache/ultra-photon-measure.py`.

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
- **A BATERIA CORRE DENTRO DE UM TECTO DE CPU, POSTO NA LARGADA (medido 2026-11-08).** O watcher
  acusou `pythonw.exe(55104)` -- cmdline desta arvore, **pai morto**, **108 % de UM nucleo**,
  `SottoNativeCaption` pintado as 17:47 e as 18:11 -- como o maior culpado de um stutter do dono, e
  era o **resto de um passo**. Prioridade `BelowNormal` (o que a bateria ja' fazia desde 2026-10-21)
  **desempata, nao limita**; o tecto e' o **Job Object** do watcher. `_main\_audit-verify-all.cmd`
  re-executa a si propria dentro de `python -m watcher run --cpu 40` antes do primeiro passo,
  `SOTTO_BATTERY_NOCAGE=1` devolve o modo sem tecto, e o sumario imprime `caged: ON|OFF` -- nenhuma
  corrida afirma "verde" sem dizer sob que tecto correu. Medido: o rc do filho atravessa o wrapper
  (`exit /b 7` -> 7) e os filhos herdam o tecto. O par `shell-orphans` +
  `red-as-expected-shell-orphans` (`_main\shell-orphans.py`) NOMEIA a shell orfa nascida na janela
  (240 min) e **nunca a mata**: a app do dono tambem nasce sem pai. Recibo:
  `_main/receipt-20261108-battery-cage-and-orphans.md`.
  **Armadilha medida no proprio bloco:** com `EnableDelayedExpansion` ligado, o `!` de `I:\!watcher`
  vira referencia de variavel, o caminho lido e' `I:\watcher`, o `if exist` falha e a corrida segue
  SEM tecto em silencio -- por isso o bloco vive **antes** do `setlocal`, e uma recusa imprime
  `CAGE declined`.
- **O CUSTO EM DISCO TAMBEM SE MEDE, EM QUALQUER VOLUME (ordem do dono via herdr, 2026-11-08).**
  Worktree, clone e store de build vivem FORA do repo, por isso "quanto este projeto ocupa" nao se
  responde com um `du` do diretorio: **`python I:\!watcher\tools\artifact-census.py --project H:/sotto
  [--budget-gib N] [--gate]`**. Atribuicao por EVIDENCIA (`git worktree list --porcelain` + todo `.git`
  ARQUIVO de qualquer volume cujo `gitdir:` aponte para o projeto + crates num store sem `.git`); nome
  parecido sai como **UNPROVEN** e nao entra no total; walk cortado diz `truncated` e `--gate` recusa
  veredito (exit 3). Rodar ANTES e DEPOIS de trabalho pesado e citar os dois numeros com o volume.
  Medido 2026-11-08, 04:1x: **7,60 GiB em 4 checkouts** (`H:/sotto` 7,41 GiB com 32 MiB de
  `node_modules`, `H:/sotto-wt/ArbV8` 78 MiB, `H:/sotto-wt/UltraRefine` 74 MiB, `H:/sotto-wt-WakeBoth`
  43 MiB orfao), e **138,68 GiB UNPROVEN** (nome igual, nao somado) -- esses NAO sao deste projeto e
  nenhum agente os apaga sem prova de dirty state.
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
- **A GUARDA É O QUE O WINDOWS RESPEITA, E O CENSO LÊ O NÓ EXACTO (medido 2026-11-08, a sétima vez
  que o dono reporta a mesma classe: *"to vendo terminal dar pop up, DE NOVO, na minha tela"*).**
  O censo desta casa existe desde 2026-11-04 e certificava `PASS` — e a janela que ele deixou passar
  foi `gh.exe(41080)`, cadeia `gh.exe <- bun.exe <- omp.exe`, `CASCADIA_HOSTING_WINDOW_CLASS`, 0,36 s
  em foreground. Três invariantes do instrumento, cada uma paga por um erro medido:
  1. **Guarda = `windowsHide: true` (JS) ou `CREATE_NO_WINDOW` + `startupinfo`
     (`STARTF_USESHOWWINDOW`/`wShowWindow=0`, Python).** `detached: true` **não** é guarda — deixa o
     filho sem consola e a próxima largada pinta outra vez (verbatim da DM). O `detached` só vale na
     arm `USER-GESTURE` (*reveal in folder*, clique do dono).
  2. **O censo julga o nó EXACTO da chamada** (`ast.get_source_segment`), nunca uma janela fixa de
     linhas: a janela de 15 linhas publicava `WEAK-FLAG` sobre uma chamada cujo `startupinfo` correcto
     estava na linha 64 de uma chamada aberta na 42 — **um portão que acusa quem está certo perde a
     autoridade**.
  3. **CLI de consola desconhecida não é `INHERITS`.** `gh`, `bun` e `deno` não estavam em
     `CONSOLE_EXES` e o censo chamava "herda a consola do pai" ao sítio que pintou a tela — falso
     quando o pai não tem consola nenhuma. A arm **C4** do `--neg-arm` carrega o par
     (`spawn('gh', {detached:true})` tem de ser `NO-FLAG`; com `windowsHide:true` tem de passar).
  **Dívida ZERADA:** `_main/console-weakflag-baseline.json` passou a `sites: []` em 2026-11-08 (os 9
  sítios congelados receberam o par). Qualquer `WEAK-FLAG` novo falha o passo. Recibo:
  `_main/receipt-20261108-terminal-paint-class.md`.
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
- **UM PIN DO `code-health` SO' DESCREVE O QUE ESTA' NO COMMIT (medido 2026-11-09).** O commit
  `5986e78` (corpo vazio, sem recibo) fixou `worker/wasapi_loopback.py` a partir do WORKING TREE --
  o ratchet passou a medir um estado que ninguem reproduz, e cinco refreshes no mesmo dia passaram
  por cima disso sem um portao dizer nada. Agora `_main/code-health-oracle.py --update` RECUSA (rc=2)
  quando alguma entrada mudaria a partir de ficheiro nao commitado e nomeia as entradas; `--skip-dirty`
  deixa-as no valor antigo (o que quase sempre se quer), `--allow-dirty` fixa e imprime cada uma para
  o recibo. O braco negativo julga as duas metades: `NEG-ARM 5 of 5` (M4 o leitor de porcelain perde
  uma forma, M5 o guarda deixa passar ficheiro sujo).
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

**PIN do `run.cmd --help` (medido 2026-11-09 09:2x, `app\webview\run.cmd --help`):** re-measured 2026-11-09 the output is 9150 B, 140 lines, 140 CRLF / 0 bare LF, rc 0, sha256
`6EEA9E1931FDD9CB1EA4DEB76148CE4E857AA954EEA01700197130E4D3BD7094`.
(606 B / 9 linhas a mais do que o pin de 8544 B / 131 CRLF: a help ganhou `--worker-threads`,
o tecto de fios do worker de ASR do par `worker-thread-limit` de 2026-11-09. O pin de 2026-11-04
estava vencido e o portao `agents-md-pins-oracle.py` acusou-o -- um pin que ninguem re-mede e'
um numero, nao um portao.)
(759 B / 8 linhas a mais do que o pin de 7985 B / 123 CRLF: a help ganhou as duas flags da shell quente,
`--no-warm-engine` e `--warm-engine-keep`, que o `run.cmd --help` imprime a partir do parser da shell.)
(Este número substitui o de 7538 B / 116 linhas, depois do bloco `THE TWO KEYS`: o `--help` passou a dizer as
DUAS teclas -- `Ctrl+Space` para a legenda ao vivo (so' display) e `Alt+C` para os paineis, com o ciclo por
indice de pressao -- que e' a ordem do dono de 2026-11-04. O pin anterior, de 7281 B / 112 linhas, era o de
2026-11-01.) O portão do pin é
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

- **PIN do ficheiro (medido 2026-11-09, 20:2x):** `_main\_audit-verify-all.cmd` = **323027 B**,
  **3793 CRLF** / 0 bare LF, sha256 `1C74B176C3266C71CF767516F3AD81297F2F14FC4126C5ECE4EB7312C4910CC4`.
  (Cinco centenas e dezassete bytes a mais do que o pin de 322510 B: o par `window-drag` +
  `red-as-expected-window-drag` -- o oraculo `_main\window-drag-oracle.py` existia com ZERO chamadores
  desde a cura do arrasto, e o `battery-wiring` acusava-o (`new-unwired 1 oraculo(s): window-drag-oracle.py`).
  E os cinquenta e oito bytes de antes: o par `caption-overlay-theme` passa a nomear
  `app\webview\overlay_paint.py`, que o oraculo IMPORTA (`_normalise_theme`, `_THEME_DEFAULT`).)
  (Mil duzentos e trinta e cinco bytes e DEZ linhas a mais do que o pin de 321217 B: o par
  `startup-ui-thread-block` + o seu `--neg-arm`, nascido do UNICO HANG do autostart do dono que
  tinha causa nomeada. `\Sotto` fechou 2026-11-08 18:57 com `LastTaskResult = 4` e o dump que a
  propria app tira (`_main\_startup-stacks.log`, 15 s, pid 9628) mostrou a THREAD DA UI presa em
  `os.makedirs <- batch_queue.py:218 <- load_shedding.py:1093 <- _start_slow_read_monitor <-
  _start_ui_watchdog <- _on_before_show <- winforms.py:775 create`: a fila do batch era construida
  DENTRO do `create` do pywebview, ou seja o `os.makedirs` do disco era chamado na unica thread que
  pode mapear a janela -- NENHUM `STAGING_SEEN`/`PRELOAD_ACTIVE`, nenhum `mark_launch_ready`,
  `UI_WATCHDOG_NOANSWER_BEFORE_FIRST` a cada 5 s. A app nao estava lenta: nao subiu. A cura move a
  abertura para o metodo `_open_load_action`, numa thread propria; o oraculo extrai as DUAS funcoes
  REAIS por `ast` e mede a chamada (**A1 0,032 s** contra o orcamento de 0,150 s, com o
  `open_action` a custar 0,400 s), o trabalho (A2), a repeticao (A3) e o interruptor (A4); o
  `--neg-arm` repoe a chamada directa (A1 cai a **0,406 s**, rc=1) e mata a thread (A2 vermelha),
  medido `NEG-ARM: PASS -- 2/2`. O autostart nao mentia: ele reportou HANG porque havia um.)
  (O pin anterior era **321217 B**,
  **3779 CRLF** / 0 bare LF, sha256 `CDE5D79400B832FE4B8BDE6D844D3E5DA7AC06DEE16E97CC8E5755919250D1C7`.
  (Mil seiscentos e cinquenta e nove bytes e DEZASSETE linhas a mais do que o pin de 319558 B: o par
  `engine-commit-cycles` + `red-as-expected-engine-commit-cycles`. Nasceu de um DM do watcher que lia
  `rss=1664 MiB` com `private=4615 MiB` no worker (2,8x) e concluia "cada carga deixa commit para
  tras". Um numero de commit sem o CICLO ao lado nao distingue tres coisas: o custo de UM modelo
  carregado, um residuo POR ciclo, e um plato que o processo segura. Medido: parakeet **+448,5 MiB**
  de commit por carga com residuo de **-1,3 MiB** por ciclo (devolve tudo); as tres sessoes ORT do
  nemotron **+467,5 MiB** (residuo 40,8 depois de soltar); as pesos do genai **+483,2 MiB** com razao
  commit/rss 0,86x. Os tres modelos juntos explicam **~1,4 GiB** dos 4,6 GiB: o resto NAO e' fuga por
  carga (a rampa e' negativa) -- e' commit segurado dentro do processo vivo, e o instrumento que o
  separa por mapeamento exige ler um pid elevado, que esta arvore nao consegue (`py-spy`: `err=5`,
  ja' medido). O `--neg-arm` aloca 200 MiB e exige o commit a subir (**200,4 MiB**, rc=1): sem ele um
  `GetProcessMemoryInfo` mal declarado imprime "0,0 MiB de fuga" -- que foi exactamente o que a
  primeira execucao desta sonda fez, com todos os numeros a zero e nenhum aviso.)
- **PIN do ficheiro (medido 2026-11-09, 14:5x):** `_main\_audit-verify-all.cmd` = **319558 B**,
  **3762 CRLF** / 0 bare LF, sha256 `A00E9B00BDE22E67F4623CB286E808ADFA8EABFA739688CA1988722A813AC5CA`.
  (Trinta e cinco bytes a mais do que o pin de 319523 B: o passo `redux-arm-weights` passa a nomear
  `app\panel\history-context-store.js` nas dependencias. O store passou a `require('./history-context-store')`
  quando o leitor de contexto foi extraido, e o passo em cache estaria a reimprimir um PASS sobre um grafo
  de `require` que ja' mudou -- a mesma classe do `panel-deps`, agora do lado do node.)
  (O pin anterior era o de 13:4x, 319523 B, o par `cost-watchdog` +
  `red-as-expected-cost-watchdog`, o CUSTO SEM TRABALHO. O watcher leu o worker do dono
  (`worker/sotto_worker.py`, pid 20676) a **270,6 %c numa janela** e a **1,2 %c** noutra, e o produto
  nao tinha serie nenhuma para julgar as duas. A CORRECAO veio depois, medida aqui: o mesmo codigo em
  12 amostras de 5 s da' **73 113 87 1 1 0 65 99 209 1 1 0 %c** -- rajadas do motor de lote com
  ociosidade entre elas, media desde o arranque **31,5 %c** -- e o `rows=0` do log era o do
  `YOUTUBE_TICK_MS`, linhas do PLAYER e nao do worker; a janela unica chamava de degradacao o que era
  trabalho. Agora o worker publica `WORKER_COST` (cpu_s, cpu_pct_avg, rows,
  rows_since_tick, rows_per_min, cpu_s_per_row, uptime_s, pid) a cada tick de stats, a shell journaliza
  uma linha por minuto (`BRIDGE_WORKER_COST`) e o vigia reinicia quando `cpu_pct_avg >= 60` **e**
  `rows_since_tick == 0` por 18 ticks (3 min) -- caso que ainda NAO FOI OBSERVADO nesta maquina, logo e'
  rede de seguranca, nao cura de um defeito medido -- com piso de 600 s e tecto de 3/hora, pelo
  `revive_worker('cost-watchdog')` que ja' existe. O passo julga as QUATRO metades (forma do worker,
  parser da shell e fiacao estatica, decisao pura, FIACAO pelo handler REAL extraido do fonte) -- 32 arms; o
  `--neg-arm` derruba 10/10 mutantes, cada um pela SUA arm. Nenhum braco abre dispositivo de audio. Recibo:
  `_main/receipt-20261109-worker-cost-and-commit.md`.)
- **PIN do ficheiro (medido 2026-11-09, 12:2x):** `_main\_audit-verify-all.cmd` = **318435 B**,
  **3752 CRLF** / 0 bare LF, sha256 `41A0577D4F3B7970B2B78432805BC43F1C051F5BD9F9A227F0CA0F6A01754C8A`.
  (Mil duzentos e vinte e um bytes e DOZE linhas a mais do que o pin de 317214 B: o par
  `cpu-tripwire` + `red-as-expected-cpu-tripwire`, o amostrador de CPU **por fio** que o watcher
  aprovou (`py-spy` nao anexa a esta arvore -- `err=5`, integridade `high` vs `medium`, medido
  2026-11-09 --, logo duas acusacoes de stutter chegaram com pid e percentagem e nenhuma linha). O
  passo julga o JUIZ: limiar **250 %c** declarado, janela **5 s**, a borda exacta dispara, e
  `None` (sem amostra) e' `UNKNOWN`, nunca "calmo" -- seis arms, `--neg-arm` 4/4. A amostragem
  viva fica on-demand porque largar sessoes ONNX num passo e' `heavy`. Primeira corrida real:
  pid 20676 = **398,8 %c** com `session-9-intra-op-0 121,8%`, `session-10-intra-op-0 80,1%`,
  `session-8-intra-op-0 64,2%` -- **tres sessoes ONNX vivas**, e o teto de 4 fios e' POR SESSAO,
  nao por processo.)
  (Mil cento e tres bytes e NOVE linhas a mais do que o pin de 316111 B: o par
  `yt-source-singleton` + `red-as-expected-yt-source-singleton`, nascido do stutter de 2026-11-09
  (o watcher mediu **81,3 %c** na shell python do dono e o log dela deu **675**
  `YOUTUBE_CDP_SOURCE state=attached` em 600 s, todas identicas). As duas linhas sao deduplicadas
  DENTRO do objeto, logo 675 copias da mesma linha sao 675 OBJETOS -- cada um a arrancar dois fios
  (`_run` + `_tid_run`) e a pagar a `/json/list`. O par executa o `_yt_cdp_ensure` REAL (extraido por
  `ast`) sobre 200 irmaos e exige UMA construcao; o `--neg-arm` roda a MESMA populacao contra o
  metodo de `HEAD` e devolve 1 ao reproduzir a multiplicacao (medido: 200 construcoes). Antes do pin
  de 316111 B, o de 315900 B nomeava as dependencias do `panel-history-clip`.)
  (Duzentos e onze bytes a mais do que o pin de 315900 B, e ZERO linhas a mais: as DUAS linhas do par
  `panel-history-clip` + `red-as-expected-panel-history-clip` passam a nomear `app\panel\panel.html`,
  `app\webview\sotto_webview.py`, `app\webview\history_context.py` e
  `_main\history-retention-fixture.py`. A arm nova da linha de 60 dias le a PAGINA e carrega o
  `history_tail`/`history_search` REAIS desses dois modulos, logo uma dependencia que os nao nomeie
  deixaria o passo em cache a descrever um painel e uma busca que ja' mudaram -- a classe do
  `panel-deps`, que ja' custou tres vezes nesta casa. O passo `panel-history-clip` nao nomeava
  `panel.html` de todo, embora carregue a pagina: era um furo anterior a esta lane.)
- **PIN do ficheiro (medido 2026-11-09, 10:1x):** `_main\_audit-verify-all.cmd` = **315505 B**,
  **3727 CRLF** / 0 bare LF, sha256 `DE84AF6E1D346CD8CED8C4FA58B7B267C069EDFE0652DA0C804E0A9A56B2AEF4`.
  (Novecentos e vinte e quatro bytes e vinte e tres linhas a mais do que o pin de 314976 B -- e este
  acrescimo NAO e' desta lane: o ficheiro cresceu depois do pin, e o portao estava RED quando esta
  sessao o correu (`AGENTS-PINS FAIL -- 2 pin(s)`, os dois de `315900 B`/`3731 CRLF`). O pin fica
  re-medido AQUI porque a regra do proprio pin exige o numero VIVO, nao o numero de quem chegou
  primeiro: medido 2026-11-09, `315900 B`, `3731 CRLF` / 0 bare LF, sha256
  `05550CB8AD717BEB89385DBF6AA113A0301E657FD7EC26D508F5564309699A1A`.)
  (Quinhentos e vinte e nove bytes e uma linha a mais do que o pin de 314976 B: as dependencias que
  faltavam a TRES passos, cada uma consumida pelo proprio oraculo e invisivel ao cache -- o par
  `worker-thread-limit` passa a nomear `_main\hidden-launch.py`, `worker\engine_policy.py` e
  `app\webview\load_shedding.py` (o A7 lanca pelo helper e o A9 importa o interruptor, que importa os
  outros dois); o par `caption-overlay-theme` passa a nomear `_main\panel-themes-oracle.mjs`,
  `app\panel\panel.html`, `app\panel\brand-bridge.js` e `app\panel\panel-unified.css` (e' de onde os 59
  payloads saem); e o par `history-context` passa a nomear `_main\hidden-launch.py` (o `_node` do
  oraculo passa por ele). A MESMA rodada fechou o furo do motor de aquecimento: o `main()` dele
  chamava `limit_threads`, que escreve o ambiente mas deixa `current_threads()` em 4 -- medido, as
  sessoes que o `attach` entrega abriam a 4 enquanto a shell pedia 2. Agora chama
  `apply_thread_budget` -> `resolve_threads`, o braco A14 EXECUTA o helper e o `--neg-arm` ganhou M8/M9
  (9 mutantes, rc=1).)
  (Mil quinhentos e sessenta e cinco bytes e dezoito linhas a mais do que o pin de 313357 B: DOIS passos,
  `history-route` e `history-route-long`, que ligam um oraculo que existia com o seu proprio controlo e
  **nenhum passo** -- a doenca do instrumento sem chamador que esta casa ja' pagou tres vezes. O oraculo
  conduz o worker REAL -> o motor REAL (`caption-formulation.js`) -> a loja REAL -> `<root>/<data>/<hora>.md`,
  e cada braco carrega o controlo da semantica PRE-CURA sobre a MESMA stream. DOIS streams porque a
  populacao muda com o fixture: medido 2026-11-09, o MESMO motor devolve `route=['final']` no curto e
  `['final','provisional-draft']` no longo, e o `want` antigo exigia as duas rotas -- reprovava um motor
  correcto. O braco passou a medir o invariante que a frase nomeia (nenhum commit viaja SEM rota, e existe
  pelo menos um), com o controlo do `before`. Os dois `always`: leem os fixtures e o motor, custam 3,3 s, e
  o `--root` fica em `_main\_cache\`, nunca no historico do dono. `battery-record-pairing` mediu 407 passos
  e 407 nomes com registo, 0 achados.)
  (Noventa e seis bytes a mais do que o pin de 313261 B, e ZERO linhas a mais: as DUAS linhas do par
  `load-shedding` + `red-as-expected-load-shedding` passam a nomear `worker\engine_switch.py` e
  `worker\engine_policy.py` nas dependencias. A ARM 26 nova EXECUTA o `ReduxHiddenSwitch` e le'
  `engine_policy.RELOAD_FLOOR_S`, logo uma dependencia que os nao nomeia deixaria o passo em cache a
  descrever um interruptor que ja' mudou -- a classe do `panel-deps`.)
  (Seiscentos e oitenta e tres bytes e quatro linhas a mais do que o pin de 312578 B: o par
  `caption-overlay-theme` + `red-as-expected-caption-overlay-theme`, o desenho da legenda NATIVA por
  tema. O oraculo existia desde as 08:44 e estava FORA da bateria -- o `battery-wiring` acusou-o com
  razao (`new-unwired caption-overlay-theme-oracle.py`). A wiring obrigou a uma correcao de
  INSTRUMENTO: o `run()` devolvia **1 quando passava** e o `--neg-arm` devolvia 0 ao apanhar, ou seja
  um controlo que nao podia falhar; agora o positivo devolve 0 e o negativo devolve **1 ao apanhar**
  (medido: `VERDICT: PASS (8/8)` rc=0 e `NEG-ARM: PASS -- 3/3 mutants caught` rc=1).
  (Setenta e tres bytes e zero linhas a mais do que o pin de 312505 B: o passo `redux-arm-weights`
  passa a nomear `worker\engine_policy.py`, `worker\redux_batch.py` e `app\panel\history-store.js`
  nas dependencias -- as arms novas do PISO DA RECARGA executam `engine_policy.ParakeetEngine` e o
  lote do `engine_switch`, e uma dependencia que os nao nomeia deixaria o passo em cache a descrever
  motores que ja mudaram.)
  (Mil trezentos e trinta e quatro bytes e doze linhas a mais do que o pin de 311171 B: o par
  `worker-thread-limit` + o seu `red-as-expected`, o orcamento de fios do WORKER de ASR. Nasceu
  do DM do watcher de 2026-11-09 (worker a 159,5 % de um nucleo, 9-10 rajadas/hora) e da
  medicao por FIO que nomeou o actor: `session-13/12/14-intra-op-0`. O `--threads N` do worker
  era INERTE -- `limit_threads` usava `setdefault` sobre o `OMP_NUM_THREADS` que o proprio
  modulo ja' tinha escrito como "4", logo as tres sessoes ORT abriam com 4 fios cada e o flag
  nao mudava um fio. Agora `--threads` ASSUME (auto mantem o ambiente, byte a byte), a shell
  passa-o por `--worker-threads` (default 2; 0 = sem flag) e o motor de FUNDO aceita o mesmo
  knob sem nunca subir acima dos 2 medidos. O oraculo mede **14/14** e o `--neg-arm` **9/9
  mutantes** (cada um derrubado pelo SEU braco: `setdefault` reposto -> A1, `--threads`
  arrancado do argv -> A6, tecto do motor `min`->`max` -> A9, a atribuicao de
  `resolve_threads` apagada -> A11, o default do motor de aquecimento a 4 -> A12,
  `StreamAsr` a ler um literal em vez de `current_threads()` -> A13, o `threads=`
  arrancado da construcao do `WarmEngine` -> A14, e as duas metades do A14 -- o
  `resolve_threads` sem o helper -> M8 e o `main()` do motor a chamar `limit_threads`
  em vez do helper -> M9). **N threads por sessao
  NAO e' N nucleos**: medido, o motor de fundo a 2 fios por sessao ainda queima 0,6-1,6 de um
  nucleo porque sao QUATRO sessoes com pool proprio.
  **MEDIDO 2026-11-09 (a mesma fixture, quatro bracos, um processo por braco, lease `heavy`
  `d95dd12a` + `d53daa7a`):** o orcamento de 2 fios corta o PICO e nao custa a legenda --
  `WORKER_THREADS threads=2 source=flag`, transcript sha IDENTICO ao de 4 fios nos dois motores
  (parakeet `1d5dfad4`, nemotron `e0c08d03`), nemotron **201,5 % -> 146,0 % de UM nucleo**
  (-27,5 %), parakeet **286,2 % -> 174,1 %** (-39,2 %), fios 63 -> 55 e 38 -> 28, RSS e privado
  inalterados. **2 fios NAO e' 1 nucleo** (146 % e' o numero, nao um "<1 core"): o knob tira
  cerca de um quarto a um terco da rajada. Custo medido: no braco de ARQUIVO o nemotron gasta
  MAIS CPU total (28,06 -> 32,34 s, +15 %) e leva mais parede (13,93 -> 22,15 s, com a carga do
  modelo dentro); no laco VIVO o custo por chunk mede, em TRES corridas do mesmo braco, **xrt 4,96 / 2,19 no
  de 2 fios e 3,26 no de 4** (p95 0,168 / 0,4885 / 0,2653 s para 560 ms de audio; o pior chunk
  quente medido foi **1,82 s** com outras lanes a correr) -- a VARIANCIA desta maquina domina a
  diferenca entre orcamentos, e o que sobrevive as tres e' que 2 fios ainda descodifica MAIS
  RAPIDO que 1x audio, logo o orcamento estreito nao cria atraso de legenda; a margem e' 2-5x,
  nao 5x, e um chunk de 1,8 s existe sob carga. Recibos: `.agent-work/receipt-omp-worker-cost.json` §measurement_ab/§measurement_pace;
  re-medir com `_main/_cache/worker-threads-ab.py` e `_main/_cache/worker-chunk-pace.py` (os dois
  exigem o lease e NAO abrem janela). E a revisao independente (2026-11-09)
  achou duas metades que o primeiro desenho NAO tinha: a resolucao vivia inline no `main()`
  (nenhum braco a alcancava -- agora e' `resolve_threads`, chamada pelo braco) e o MOTOR DE
  AQUECIMENTO construia as sessoes antes de a shell existir, com o default dele proprio (agora
  `warm_engine.py --threads`, default 2, com o A12 a exigir que os dois defaults sejam o mesmo
  numero).)
  (O par `history-context` + o seu `red-as-expected`, o portao do contexto de
  origem/visualizacao do historico -- `history_context.py` normalizado e limitado, o token
  `ctx1=` por linha, o `history_append`/leitura/busca/export do shell e o twin Node. Nasceu
  da ordem do dono de 2026-11-09: meses depois, saber de onde veio o audio e o que estava na
  tela quando foi dito. O `--neg-arm` mede 4/4 mutantes; `history-context-oracle.py` mede
  52/52 arms. O ficheiro tambem recebeu passos de outra lane depois do pin de 308834 B; o
  numero acima e' a medicao VIVA, nao uma soma da minha mudanca.)
  (Dois mil quinhentos e trinta e cinco bytes e doze linhas a mais do que o pin de 306299 B: UM
  par novo, `panel-themes` + `red-as-expected-panel-themes`, o contrato de composicao
  COMPARTILHADA do dono de 2026-11-09 ("consistencia em TODOS os temas"). O oraculo
  `_main\panel-themes-oracle.mjs` abre o `app/panel/panel.html` REAL num browser privado e
  headless e mede os **59** itens do seletor -- 45 temas CSS + 20 skins, 6 duais -- em
  geometria e pintura COMPUTADAS, uma relacao por braco: ajustes imediatamente a esquerda do
  fechar (`gap` da propria fileira), fileira ancorada em `380 - 14`, barra invisivel mas
  `overflow-y:auto` (um `scrollTop` programatico move uma caixa `hidden` -- medido, por isso o
  braco le o `overflow-y`), sem vazio embaixo, busca que revela o campo, sem circulos de demo,
  e a legenda com o FUNDO do desenho (o `--bg-slab` de cada tema quando a fileira nao tem cama
  propria; `rowBgAlpha` era 0 em 9 desenhos e `oklab(...)` ilegivel em outros tantos). Medido:
  `THEMES picker=59 css=45 skin=20 dual=6`, **11 bracos x 59 temas** (os nove de composicao
  mais `keyboard-scroll` -- PageDown/PageUp/End/Home movem a MESMA caixa que a roda resolve,
  porque esconder a barra tira a unica coisa que dizia que a caixa anda -- e `skin-mounted`,
  porque uma skin que nao montou media o tema CSS anterior e passava), 33 faces de legenda
  distintas e **58 camas de legenda distintas**; `--neg-arm` **8/8** mutantes apanhados (rc=1).
  O MESMO bloco fechou tres furos que o revisor independente provou: (1) uma folha adiada que
  falhava era anotada e nao reprovava -- o `load()` devolvia `false` e o booleano era
  descartado, logo 25 temas eram medidos contra o tema base e passavam; agora o carregamento e'
  verificado e qualquer erro de pagina que nao seja o `.jpg` de papel de parede que as 20
  maquetes nao embarcam (`SKIN-IMAGES missing`, informativo) reprova o veredito; (2) o
  `--neg-arm` do `panel-header-oracle` era o unico negativo desta casa que nao corria em lugar
  nenhum -- entrou o par `red-as-expected-panel-header-oracle`, e ele passou a devolver rc=1 ao
  apanhar (a convencao medida em 2026-11-03); (3) a arm "a borda direita da fileira e' o inset
  da janela" comparava o modelo com o proprio seed (`cursor = PANEL_WIDTH - 14`) e nao podia
  falhar -- agora o inset vem do CASCADE (`winningDecl(cluster,'right')`) e um braco separado
  exige que a folha ainda diga 14. `battery-wiring` mediu `ligados=163 sem_passo=109
  populacao=272`, PASS 7/7.)
  (Dois mil e trinta e nove bytes e vinte linhas a mais do que o pin de 304260 B: DOIS pares novos,
  os dois nascidos das cinco DMs de stutter de 2026-11-08 -- `ort-spin-idle` (o spin-wait do
  onnxruntime: tres sessoes vivas e ociosas gastavam **16,1 % de um nucleo** com o `allow_spinning`
  por omissao contra **0,0 %** sem ele, e o passivo custa 33,5 us por chamada, ~10 ms num chunk de
  560 ms; o oraculo executa o `session_options` do PROPRIO worker e as sessoes reais, 2,7 MB de
  grafos, sem abrir dispositivo) e `batch-executor-ceiling` (o passe de LOTE: `36,0 %` de um nucleo
  no fio `sotto-batch-executor`, tid 10848, pid 55104; agora o laco deriva a espera do custo medido
  -- periodo = custo/ORCAMENTO -- e o filho nasce com tecto de fios; medido 0,115 de servico contra
  0,120 de orcamento, 0,76-0,95 no mutante). Os dois `--neg-arm` medidos aqui: `NEG-ARM: PASS`.
  O `battery-wiring` conta `ligados=162 sem_passo=109 populacao=271`, PASS 7/7.)
  (O pin anterior era 304260 B / 3642 CRLF: o par `shell-orphans` + o seu `--neg-arm`, e o
  **TECTO DE CPU NA LARGADA** -- o cabecalho re-executa a corrida dentro de
  `python -m watcher run --cpu 40`, com `SOTTO_BATTERY_NOCAGE=1` como saida e a linha `caged:`
  no sumario. Nasceu da DM de stutter de 2026-11-08: `pythonw.exe(55104)`, shell largada por um
  passo e nao recolhida, orfa, 108 % de um nucleo, acusada como o maior culpado.)
  (Mil oitocentos e cinquenta e sete bytes e quatro linhas a mais do que o pin de 298679 B: o par
  `panel-history-wheel` + o seu `--neg-arm`, a RODA do historico. Nasceu da ordem do dono de
  2026-11-08 -- *"eu nao consigo usar meu scroll pra scrollar as legendas no historico"* -- e da
  causa que ele mediu: `#history-list` carrega `overflow-y:auto` **e** `overscroll-behavior:contain`
  mas e pintado `display:block`, logo a caixa tem a altura do conteudo (`clientHeight == scrollHeight`)
  e nunca rola; quem rola e `.history__body` (630/5985) e o `contain` do fantasma PARA a roda antes
  de ela chegar la. E1 (so `overscroll-behavior:auto` naquela caixa) devolve `body 0->400`; E3
  (`overflow:hidden` no corpo) devolve `body 0->0`, o controlo que prova que o probe le a caixa
  certa. O `--neg-arm` remove `wireHistoryWheel();` NUMA COPIA -- uma mutacao cirurgica do proprio
  mecanismo, nunca "o `panel.js` de HEAD", que apodrece no dia em que a cura e cometida.)
  **E UMA LICAO QUE CUSTOU UM RED FALSO (medido 2026-11-08):** o `cmd.exe` le um ficheiro de lote
  pelo OFFSET de bytes, por isso **reescrever este `.cmd` enquanto uma corrida o esta a ler executa
  lixo** -- o que apareceu foi `'S' nao e reconhecido como um comando interno`, `rc=9009` num passo
  que passa sozinho, e um sumario com 7 falhas que o mesmo comando nao reproduz. A regra e curta:
  **nenhuma edicao neste ficheiro com uma corrida em voo**; commit ou edicao primeiro, corrida
  depois, e nada mais a correr (nem probe, nem oraculo: o ratchet POR PASSO e absoluto e 5,4 s ->
  10,1 s de um `panel-header-oracle` e contenda, nao regressao).
  (Dois mil trezentos e sessenta e um bytes e TREZE linhas a mais do que o pin de 296318 B: o par
  `theme-caption-identity` + `red-as-expected-theme-caption-identity`, o portao da ordem do dono de
  2026-11-08, verbatim: *"VOCE TIROU O DESIGN DE TODAS AS LEGENDAS PRA DEIXAR ELAS IGUAIS EM TODOS OS
  TEMAS."* A cura de legibilidade do historico tinha posto `font-family: "Instrument Sans"`,
  `font-size: calc(13.5px * var(--caption-scale))` e `line-height: 1.5` como LITERAIS com `!important`
  em `app\panel\panel-unified.css` -- o ultimo ficheiro que o `panel.html` carrega --, sobre os 35
  desenhos que embarcam. Agora a linha le' os tokens do TEMA com PISO; medido no oraculo:
  theme-1 **18,5 px**, theme-2 **13,5** (piso, era 10,5), theme-3 **14,5**, theme-4 **15**, theme-5
  **14,5**, `arms 5/5`, e o `--neg-arm` 4/4 mutantes apanhados com rc=1 (com o passo declarado
  `call :step ... 1` + `call :expectred ... "NEG-ARM: PASS"`, que e' a unica forma que conta como
  controlo: o `:expectred` com o rc que o oraculo devolve ao apanhar). A MESMA linha consertou
  `red-as-expected-panel-pause-payload`, que estava declarado com rc esperado **0** e cujo oraculo
  devolvia 0 ao apanhar o mutante: um controlo que nao pode falhar. Agora o oraculo devolve 1 ao
  apanhar (medido: `NEG-ARM: PASS -- 0/5 arms ainda passam`, rc=1) e o passo declara-o.
  E o MESMO par ficou completo no RENDER: `panel-history-clip` passou a ler
  `themes/cinematic.css` e `themes/panel-designs.css` (o `lazy-assets.js` entrega-as por
  pedido, e sem elas o probe media 30 dos 45 desenhos com a face de RECURSO e chamava
  isso de identidade) e ganhou `red-as-expected-panel-history-clip`: medido, o positivo
  da' **28 faces distintas** (familia+tamanho) em 45 desenhos, e o `--neg-arm` repoe a
  regra literal de antes da cura e cai para **1 face**, rc=1.
  O pin anterior era o de 296318 B: **3576 CRLF** / 0 bare LF, sha256
  `5027CEA937F19C3480801D306A02B26A59A6AC2B793A3FE5B6731B3C46C73A81`.)
  (Oitocentos e catorze bytes e NOVE linhas a mais do que o pin de 295504 B: a cura de custo do
  `--neg-arm` da pagina de estado -- **84,5 s** na corrida, **73,26 s** sozinho, porque
  `run_mutation` copiava a arvore, renderizava e corria o check de base uma vez POR MUTACAO, oito
  vezes, com a copia a incluir o directorio de logs. `run_mutations_shared` faz a copia, a
  renderizacao e a referencia UMA vez e corre cada mutacao sobre a copia restaurada por snapshot de
  bytes: **49,45 s**, 8/8 mutacoes a nomear o check que deviam.)
  (Mil quatrocentos e sessenta e tres bytes e DEZASSETE linhas a mais do que o pin de 294041 B: o
  ratchet do RELOGIO ganhou o segundo tecto, o que era o defeito mais caro que este ficheiro tinha.
  MEDIDO: o baseline era **5 801,2 s** (de 2026-11-05) e a corrida verde media **2 102,0 s** -- o
  tecto de 6 091 s deixava passar **2,9x** de regressao em silencio, porque uma soma esconde o passo
  que engordou. Agora ha' o tecto do total (5 %) e o POR PASSO (**20 %** sobre o baseline de cada
  passo, piso de 5 s) mais seis bracos do juiz em toda invocacao; os 20 % e o piso sao a regua
  MEDIDA (o mesmo oraculo: 79,94 s sozinho contra 219,1 s na corrida = contenda 2,7x), nao um gosto.
  O baseline so' aperta por omissao e o `--neg-arm` tem DOIS mutantes -- M2 isola o ratchet por
  passo aritmeticamente (o resultado tem de continuar abaixo do prazo e o acrescimo caber no tecto do
  total), porque sem ele apagar o ratchet por passo continuava a dar `NEG-ARM: PASS` por causa da M1.)
  (Seiscentos e trinta e tres bytes e OITO linhas a mais do que o pin de 293408 B: a cura de custo
  do passo `panel-hidden-at-startup-oracle`, que era **219,1 s** dentro da corrida com 21 s de
  margem. Re-medido sozinho antes de cortar: **79,94 s** onde o comentario dizia 1,97 s. A
  populacao era um numero de CHANCES (8 repeticoes no pai, 3 em cada um dos QUATRO filhos = 234
  execucoes do harness a 0,168 s, cada uma a arrancar fios reais) e as repeticoes nunca eram
  comparadas ENTRE SI; `REPEATS_DEFAULT = 2` mais um braco de ACORDO (`REPEAT-UNSTABLE`) provam o
  mesmo com 4x menos no pai e 1,5x em cada filho. Depois: **50,7 s** sozinho, `--neg-arm` 3,59 s,
  3/3 mutantes. O determinismo foi medido ANTES de cortar: 20/20 execucoes da celula
  `startup-hidden / at-init` assentaram o mesmo valor.)
  (Setecentos e sessenta e seis bytes e NOVE linhas a mais do que o pin de 292642 B: dois numeros de
  custo RE-MEDIDOS, os dois errados por 40x e por 2,7x. O passo `panel-hidden-at-startup-oracle`
  dizia `MEDIDO: 1,97 s`; medido hoje **79,94 s** sozinho e **219,1 s** dentro da corrida -- e o
  custo cresce com as COPAS da shell que cada braco de mutacao faz (`sotto_webview.py` tem 22 780
  linhas), nao com o AST. O prazo por passo dizia "acima de todo passo legitimo (max 168 s,
  `device-silence`)"; hoje o passo mais caro que passa e o `panel-hidden` com 219,1 s, ou seja a
  margem do primeiro e **21 s** e o proximo degrau desta escada e ele. A clase e a do `pin que
  ninguem re-mede`: um numero de 2026-11-05 a justificar um tecto de hoje.)
  (Dois mil quinhentos e dezassete bytes e VINTE E SEIS linhas a mais do que o pin de 290125 B: mais
  um passo, `bend-ledger-selftest`, que corre o `--self-test` do livro de provas
  (`tools\bend_proof_ledger.py`): ele julga o CLASSIFICADOR do livro com cinco fixtures, incluindo
  "um check saltado nunca e' verde", e era um instrumento com juiz e ZERO chamadores.
  (Mil oitocentos e cinquenta e um bytes e DEZASSEIS linhas a mais do que o pin de 290125 B: o par
  `bend-mirror` + `red-as-expected-bend-mirror`, que leva as leis `Hist.*`/`Fmt.*` das DECISOES 6 e 7
  ate' as funcoes REAIS (`app\panel\history-source.js` e `app\panel\caption-formulation.js`, as duas
  executadas por `node`, nao relidas), mais as QUINZE dependencias que faltavam ao `bend-laws`
  (as 14 `bend_core\NEGATIVE_hist_*`/`NEGATIVE_fmt_*` e o `tools\bend_verify.sh`, que o portao passou
  a ler). A classe e' a do `panel-deps`: um passo em cache a descrever um ficheiro que ja' mudou. O
  portao do inventario tinha o mesmo buraco do lado do `bend_verify.sh` -- MEDIDO nesta rodada, a
  lane escreveu as 14 leis na copia do `.sh` e nao no portao, e a bateria fechou RED num passo cujo
  unico defeito era a divergencia entre duas copias do mesmo pin; agora o portao compara as duas
  listas (`deep_tool_drift()`) e recusa com `EXIT_INVENTORY`.)
  (Dois mil duzentos e vinte e um bytes e vinte e sete linhas a mais do que o pin de 287904 B: o
  par `battery-record-pairing` + o seu `--neg-arm` -- e a REPARACAO que ele obrigou a fazer no
  MESMO bloco. MEDIDO na corrida de 06:0x: o bloco do painel corria DEZ passos e tinha UM
  `call :record`, no FIM, que carimbava o `!STEP_RC!` do ULTIMO passo no nome do PRIMEIRO. O
  `:step` nao conta nada; quem conta e' `:record`/`:expectred`/`:skipped`. Logo NOVE vereditos
  daquele bloco nunca chegaram ao sumario -- e o `red-as-expected-caption-drag` estava declarado
  com `:record` (espera 0) quando o oraculo devolve 1 ao apanhar. O oraculo novo julga as tres
  metades (`R1` todo `:step` tem registo do mesmo nome, `R2` o registo vem ANTES do proximo
  `:step`, `R3` registo orfao) -- medido depois da reparacao: `380 passos, 380 nomes com
  registo, 0 achados` e `--neg-arm` 3/3 mutantes apanhados. O `battery-wiring` mediu
  `ligados=160 sem_passo=109 populacao=269`.)
  (Quinhentos e cinquenta e quatro bytes e SEIS linhas a mais do que o pin de 287350 B: o passo
  `shell-thread-budget` passa a `:skipped` -- declarado skip-capable. Medido na corrida de
  2026-11-08: `SKIP-VERDICT IN THE LOG OF A STEP THAT IS NOT DECLARED SKIP-CAPABLE:
  shell-thread-budget.log`, `1 undeclared skip verdict(s) in 404 step log(s)`. O oraculo LE a
  shell VIVA e, com a app fechada, `SHELL-THREAD-BUDGET SKIPPED reason=no-live-shell` e' o
  desfecho NORMAL -- declarado com `:record` esse skip honesto virava um RED da CORRIDA. Com
  `:skipped` ele conta em `skipped=`, e um skip nao e' um portao que passou.)
  (Mil e cinquenta e quatro bytes e DEZ linhas a mais do que o pin de 286296 B: o par `paint-cost` +
  o seu `--neg-arm`. O dono pinta uma legenda e o quadro reconstruia o TEXTO todo em cada pintura;
  a cura guarda o raster e o hit mede **0,063 ms p95** contra **6,55 ms** -- 90x, e o oraculo
  compara o pixel contra a implementacao ANTERIOR pinada em `HEAD_PIN` e **recusa** uma referencia
  que ja' traga `_PAINT_CACHE` (a primeira versao comparava a cura com ela propria e o A2 dava RED
  por desenho -- a classe "portao que nao pode falhar"). Runtime 92 s: acima do limiar do modo
  rapido, logo ele e' SKIPPED ali e nunca verde. `battery-wiring` medido: `ligados=159
  sem_passo=109 populacao=268`, PASS 7/7.)
  (Dois mil duzentos e onze bytes e VINTE E TRES linhas a mais do que o pin de 284085 B: DOIS pares
  novos, os dois nascidos do mesmo processo vivo do dono. `log-sink-dead` + o seu `--neg-arm`: o
  `log()` fazia `print(..., flush=True)` sem guarda, e um cano morto levanta -- a mesma classe que a
  casa ja' curou do lado do WORKER (`emit-pipe-dead`, 2026-11-04) e que do lado da shell nao tinha
  cura; agora o cano morto e' detectado UMA vez e o facto vai para o ficheiro. (A primeira versao
  desta linha contava um incidente que NAO ACONTECEU -- "o log morreu as 04:57 e a app ficou tres
  horas muda": a hora do log e' LOCAL (UTC-3) e eu li-a como UTC. O que esta' medido e' o custo
  (100 % de um nucleo, `sotto-caption-tick` 93,6 %/78,5 %) e a classe do `log()`; o `OSError 22`
  nesta instancia e' UNMEASURED. Ver `_main/receipt-20261108-log-sink-dead.md` §1.) `cdp-target-async` + o seu `--neg-arm`: o `/json/list` de 1,0-1,4 s
  (medido `phases={'cdp': 15.0, 'vid': 1281.0}`) saiu do laco de leitura para o fio `yt-cdp-target`.
  Recibos: `_main/receipt-20261108-log-sink-dead.md`, `_main/receipt-20261108-cdp-target-async.md`.)
  (Mil duzentos e noventa e tres bytes e treze linhas a mais do que o pin de 282792 B: o par
  `shell-thread-budget` + o seu `--neg-arm`, nascido da DM de stutter do watcher e do que ela
  obrigou a medir -- o pid da shell do dono (`42572`) acusado como maior culpado, e a atribuicao
  por FIO que nenhum passo da bateria lia: `total=103.4% de UM nucleo, tid 48064
  sotto-caption-tick = 93.6%`, reprodutivel em duas amostras. O instrumento `_main/shell-thread-cpu.py`
  existia com `--neg-arm` e ZERO chamadores -- a mesma doenca do `panel-deps` e do
  `caption-tick-thread`: um instrumento sem passo apodrece. O portao exige total <= 25 % de um
  nucleo, um fio <= 15 %, o fio mais quente COM NOME e um ratchet de +20 % sobre
  `_main/shell-thread-budget-baseline.json`; sem shell viva diz SKIPPED. `--neg-arm` mede o JUIZ
  (6/6, sem abrir janela). Recibo: `_main/receipt-20261108-stutter-caption-tick.md`.)
  (Cento e dez bytes a mais do que o pin de 282682 B: DUAS dependencias que faltavam, a mesma classe
  do `panel-deps` -- um passo em cache a descrever outro codigo. `caption-tick-thread` passou a
  nomear `app\webview\word_fade.py` (as arms A6/A9 leem `FRAME_S`/`FRAME_HZ` e o relogio de la') e
  `youtube-cdp-source` passou a nomear `app\webview\youtube_window.py` (o normalizador do marcador
  `>>` vive la' e o modulo carrega-o PELO CAMINHO; sem a dependencia o passo reimprimiria o verde
  sobre um ficheiro que ja' mudou).)
  (Mil trezentos e nove bytes e vinte e seis linhas a mais do que o pin de 280373 B: tres pares
  novos, os tres nascidos de ordens do dono de 2026-11-08. `strip-width` + o seu `--neg-arm`
  responde a *"por que a porra do painel de baixo do sotto ta gigante? restaura como era antes"*:
  a faixa abriu **1040x40 @(440,948)** as 03:30:29 (`STRIP_WIDTH from=None to=1040
  source=content`) contra o **380x40 @(770,948)** de 2026-11-07 10:22 -- 2,74x a area --, porque
  `.panel` e' `inset:0` e a "medicao de conteudo" media a propria janela e escrevia o numero de
  volta no rect salvo. `caption-drag` + o seu `--neg-arm` responde a *"segurar control, permite eu
  arrastar a legenda pra onde eu quero"*: 11 arms sobre o core puro `app\webview\caption_drag.py`
  e o `--neg-arm` a exigir P4/P7/P9 vermelhas. `paused-pace`-style wiring: `ligados=155
  sem_passo=109 populacao=264`, e o `code-health` absorve o crescimento declarado de
  `panel.js`/`hotkey_gesture.py`/`sotto_webview.py`/`caption_overlay.py`/`panel-unified.css`.)
  (O pin anterior era o de 280373 B:
  (Quinhentos e catorze bytes e cinco linhas a mais do que o pin de 279859 B: o par `hotkey-spam` +
  `red-as-expected-hotkey-spam`, o portao do Alt+C em rajada. Nasceu da ordem do dono de 2026-11-08,
  verbatim: *"apertar alt c super rapido deixa o app travando pra caralho. deixa completamente fluido.
  é pra abrir os paineis e qualquer outra coisa super rapido com o alt c sendo spammed. sem travar."*
  O `_hotkey_dispatch` deixou de enfileirar um passo por toque: ele CONTA os toques e o worker drena o
  contador no primeiro token, aplicando UMA transicao para `hotkey_gesture.advance(visible, surface, n)`
  -- N toques = 1 transicao para o estado final, com a ordem preservada quando um `live` cai no meio.
  Medido no oraculo (transicao falsa de 400 ms): rajada de 6 toques em <50 ms = **18,5 ms de despacho e
  82,1 ms de parede, 1 drain**, contra **2 461,5 ms e 6 drains** na fila FIFO antiga; 5 toques em 320 ms
  = 852 ms / 2 transicoes contra 2 051,6 ms / 5. Um toque sozinho nao ganha atraso nenhum (6,08 ms de
  despacho). `python _main/hotkey-spam-oracle.py` -> `GREEN arms=19 pass=19`; o `--neg-arm` repoe a fila
  numa COPIA e mede `pass=7 fail=12` com A1 e A5 RED. Recibo: `_main/receipt-20261108-hotkey-spam.md`.)
- O pin anterior, de 2026-11-08 03:0x: 279859 B,
  **3397 CRLF** / 0 bare LF, sha256 `210AE8D714E9DB9184A9E4B4556C062894E4CCBE6AFB0FD63D3F566B78460D23`.
  (Mil cento e sessenta e tres bytes e doze linhas a mais do que o pin de 278696 B: o par
  `caption-tick-thread` + `red-as-expected-caption-tick-thread`, nascido do DM do watcher --
  `creation=90.879 creations/s` na arvore da shell durante um stutter de 192 s. A unica criacao
  por frame da app era o `threading.Timer` do `caption_overlay._arm_tick`: **um fio POR QUADRO**,
  ~62/s com a legenda ao vivo a 16 ms, cada um `CreateThread` + `WaitForSingleObject`. Agora ha'
  um fio `daemon` unico que espera num `Event` com prazo. O oraculo conduz o
  `_arm_tick`/`_tick_loop`/`_tick` REAIS e conta `threading.Timer`: o braco antigo mede **105**
  construcoes em 1 s de frames de 5 ms contra **zero**, e o `--neg-arm` repoe a implementacao
  antiga em memoria e derruba A2 e A3. Medido hoje: `VERDICT: PASS (5/5)` e `NEG-ARM: PASS`.)
  (Mil trezentos e noventa e seis bytes e catorze linhas a mais do que o pin de 277300 B: o par
  `caption-rollup` + `red-as-expected-caption-rollup`, o ROLL-UP da legenda que o dono pediu hoje --
  *"quero a animacao de quando comeca uma linha nova e a outra linha vai pra cima"*. O motor
  (`app\webview\youtube_reveal.py`) ja' tinha a janela do player, mas o overlay NATIVO chamava
  `frame(..., capacity, 0, 0.0)`: a linha velha desaparecia num quadro. Agora `_PlayerCue.frame`
  desenha a linha a rolar, `_PlayerCue.roll()` devolve 0..1 e o bitmap desenha as linhas com
  `-roll * line_h` (a placa de fundo nao se move), com a caixa fixa em `PLAYER_ROWS` linhas. O
  passo mede PIXEL, nao texto: quatro bracos comparam o bitmap real contra as duas referencias
  paradas, e o `--neg-arm` desliga `roll_progress` e exige a arm do meio vermelha -- medido
  `VERDICT: PASS (4/4)` e `NEG-ARM: PASS` com rc=1.)
  (Dois pares novos, 1264 B e 15 linhas a mais do que o pin de 276036 B:
  `census-instrument` + `red-as-expected-census-instrument` -- o censo da shell calava abaixo de
  20 % do TOTAL e deixou de nomear a thread exactamente na faixa em que a cura a põe (10-16 %);
  agora publica com total >= 20 % **ou** uma thread >= 5 %, e `SHELL_CODE_ID ... heartbeat=true`
  volta a cada ~10 min (memo de 14 ms -> 0,0 ms), porque escrito só no arranque ele desaparece com
  a rotação do log e o portão da frescura responde `UNKNOWN` quando a instância envelhece.
  O pin anterior era 276036 B / 3356 CRLF:
  sha256 `41390E124B721FD42DF51A094DA1CCA7F321DB484DDFC64BB6BE1E12DF145669`.)
  (Mil quatrocentos e dezasseis bytes e quinze linhas a mais do que o pin de 273404 B: o par
  `worker-death-trace` + `red-as-expected-worker-death-trace`, a **morte diagnosticavel do
  worker**. Nasceu da DM do watcher de 2026-11-07 (*"acabou de acontecer stutter"*) e da medicao
  que ela obrigou: SEIS mortes do worker num dia, todas `last="Worker error at unhandled -
  OSError: [Errno 22] Invalid argument"`, cada uma comprada com uma recarga do modelo
  (`BRIDGE_LOAD_MS` 11703 / 27015 / 33860 / 37157 ms) -- e o log guardou **duas** linhas de
  stderr de cada morte, nenhuma do traceback. Duas curas medidas: o relator nunca levanta
  (`err()` do `engine_switch` e os dois `emit_fn`/`err_fn` do `contract_guard`), e a frase fica
  em `_main\webview-worker-tracebacks.log` com tecto de 256 KB. 12 arms no positivo, 3/3
  mutantes apanhados no negativo. O pin anterior era 273404 B:
  **3326 CRLF** / 0 bare LF, sha256 `FA5FFFFC51AB42327B8050A64C3357BB7EA53CBAD934D22BB84FF5AEC100B0F7`.
  (Trezentos e oitenta e seis bytes e duas linhas a mais do que o pin de 273018 B: o par
  `outside-click-timer` + `red-as-expected-outside-click-timer`, o **spin do timer do vigia de
  clique-fora** -- `SetTimer`/`KillTimer` sem `argtypes` devolvia um id que o `KillTimer` nao
  encontrava, e o re-arme a cada `WM_TIMER` degenerava o timer para **2 569-3 715 Hz** com a
  classe real a **13,1 % de um core** (contra `sotto-outside-click` **14-27 %** na instancia
  viva). Curado: id do Windows guardado, memo do intervalo, e o tick mede **9,2 Hz / 0,2 %**;
  `--neg-arm` apanhado por 3 arms (rc=1).)
  (Mil setecentos e nove bytes e dezoito linhas a mais do que o pin de 271309 B: o par
  `hotkey-panels-switch` + `red-as-expected-hotkey-panels-switch`, o interruptor do Alt+C que o
  dono pediu no MENU DO ICONE -- verbatim: *"faz um botao 'desativar atalho alt c' no click direito
  do icon do sotto"* e, um minuto depois, *"e claro, é ativar e desativar"*. UM item cujo TEXTO e'
  a accao (`Desativar atalho Alt+C` / `Ativar atalho Alt+C`), id 4, com o menu reconstruido por
  `refresh_menu` no instante em que o estado muda; a escolha vai para `_main\hotkey-settings.json`
  (`panels_enabled`) porque um interruptor que so' valesse ate' ao reinicio seria um botao que
  mente na manha seguinte. O oraculo julga as cinco propriedades da persistencia e os dois sitios
  de fiacao -- o portao do ARRANQUE (`arm_hotkey(panels=False)` nao regista a tecla e diz por que)
  e o HANDLER -- sobre um ficheiro TEMPORARIO; o `--neg-arm` muta quatro sitios, o quarto e' o
  proprio portao, medido 4/4 CAUGHT. O TEXTO do item e a fiacao do comando ficam no
  `tray-menu-oracle` (arms 15-18, 19/19, `--neg-arm` 7/7), e o clique deixou de reconstruir o
  menu: o `_build_menu()` + o `log` com `flush` corriam ANTES do `TrackPopupMenu`, entre o clique
  do dono e o menu a aparecer -- numa maquina com o disco saturado e' exactamente "aperto o botao
  direito e nao responde".)
  (Dois mil e quarenta e seis bytes e vinte e uma linhas a mais do que o pin de 269263 B: o par
  `stutter-caption` + `red-as-expected-stutter-caption`, o portao da ordem do dono de hoje --
  *"e ridiculo o fato que um stutter qualquer do meu pc, faca a legenda dessincronizar ... se a
  porra da legenda do youtube ta se movendo, mesmo com o stutter acontecendo, a NOSSA legenda que
  pegamos do youtube, TAMBEM."* Os dois tetos redondos do relogio (`min(age, 0.5)` na amostra da
  CDP e `YT_ANCHOR_MAX_S` = 3 s na extrapolacao) inventavam uma parada que o player nunca disse;
  medido com as 745 amostras REAIS do Chrome dele (`_main\fixtures\yt-paint-freeze-20261104.json`,
  deriva 4,25 ms/s = 34 ms em 8 s), custavam **2,312 s** de erro num stutter de 3 s e **4,411 s**
  num de 5 s -- 4,6x e 8,8x o orcamento de 150 ms. A tolerancia passa a ser o ESTADO PUBLICADO
  (`app\webview\youtube_clock.py`: PLAYING conta ate' 8 s, PAUSED/ENDED nao anda, sem bandeira
  serve-se a amostra) e o que NOS adiantamos e' desfeito na primeira amostra autoritativa
  (`rebase`). O oraculo fecha 14 arms e o `--neg-arm` repoe os dois tetos em COPIA, exigindo A1-A5
  vermelhas. Medido: `STUTTER-CAPTION GREEN -- arms=14 pass=14`.)
  (Cinco bytes a mais do que o pin de 269258 B: as CINCO linhas em que a bateria larga o proprio `python`
  passam a largar `pythonw`. Nasceu da queixa do dono de hoje -- *"to vendo terminal dar pop up, DE NOVO,
  na minha tela"* -- e do que o vigia de janelas mediu: o `cmd.exe` da corrida, largado por uma lane
  num processo SEM consola, da' a cada filho `python` uma consola NOVA (o Windows Terminal a aparece),
  porque `cmd` nao tem como passar `CREATE_NO_WINDOW`. `pythonw` nao tem consola nenhuma e larga os
  seus filhos por `hidden-launch.popen` (CREATE_NO_WINDOW), logo a arvore inteira fica muda. Medido
  antes de escolher: `pythonw -c "print(...)"` perde o stdout, mas o `sys.stdout` REAL escreve no
  redireccionamento (`FROM-PYW` no ficheiro) -- o log do passo continua a ser a evidencia.)
  (Mil seiscentos e quatro bytes e duas linhas a mais do que o pin de 267654 B -- o par
  `panel-deps` + `red-as-expected-panel-deps`, o portao que fecha uma mentira de CACHE medida hoje:
  os tres passos que montam o `app\panel\panel.html` real (`panel2-dom-probe`,
  `panel-header-oracle`, `panel-history-clip`) declaravam 11, 8 e 8 dependencias para uma pagina que
  carrega **25** assets, e os tres manifestos de tema (`themes\themes.js`,
  `themes\panel-designs.js`, `themes\zipc-panels.js`) nao estavam em nenhuma delas -- editar um tema
  deixava os tres passos em cache a reimprimir um PASS sobre o ficheiro antigo. As deps dos tres
  passos passam a nomear os 25 assets; o `panel-deps-oracle.py` compara a lista com o `panel.html`
  real (18 arms) e o `--neg-arm` muta UMA linha -- medido: `VERDICT: PASS -- 18/18` e
  `NEG-ARM: PASS -- o mutante foi apanhado`. O proprio neg-arm trouxe uma correcao de instrumento:
  o `replace(..., 1)` sem escopo apagava o asset de OUTRO passo e o mutante "passava".)
  (Quatrocentos e vinte e quatro bytes e duas linhas a mais do que o pin de 267230 B: o par
  `panel-pause-payload` + `red-as-expected-panel-pause-payload`, que EXECUTA o `SottoShell.stats()`
  real nas duas saidas. Nasceu de um defeito que a primeira versao da cura carregava: o `stats()`
  tem DUAS saidas e a primeira (um tick de medidor fresco) substitui a linha de WORKER_STATS
  inteira -- carimbar o pause so' na ultima deixava o botao sem noticia exactamente no caso NORMAL.
  Medido: 5/5 arms no positivo e o mutante com o carimbo arrancado cai para **0/5**.)
  (O pin de 2026-11-06, 01:2x era 267230 B,
  **3281 CRLF** / 0 bare LF, sha256 `A52B4B35060C05B1477513D9C9A89C05301DFC599320781948AE942A8A4BE286`.
  (Novecentos e noventa e cinco bytes e tres linhas a mais do que o pin de 266235 B: os tres passos
  que faltavam aos instrumentos desta rodada do dono -- `panel-header-oracle` (21 arms, incluindo o
  braco NOVO 7: o botao de pause APRENDE o estado do shell pelo canal `stats`, com um mutante de
  `panel.js` montado numa pagina propria como controlo), `panel-drag-targets` (12 arms, o arrasto dos
  paineis) e `panel-history-clip` (45 temas, as linhas do historico e o contraste do horario). Os
  tres dependem de `app\panel\panel-unified.css`, o ficheiro novo da unificacao dos temas.)
  (O pin de 2026-11-05, 23:5x: 266235 B,
  **3278 CRLF** / 0 bare LF, sha256 `64654A80628B21B58608285AD599055D00DE70BB817BAC3698DBE69045934B33`.
  (Quatrocentos e doze bytes e seis linhas a mais do que o pin de 265823 B: o build do plano passa a
  usar **caminhos absolutos** (`%ROOT%\_main\_battery-plan.py`, `--cmd %ROOT%\...`) e a **apagar o
  plano velho antes de comecar** -- medido 2026-11-05: com o `--cmd` relativo e o plano de uma
  corrida anterior no disco, um build que falhasse (o stderr ia para `nul`) deixava o `if exist`
  verdadeiro e a corrida carregava decisoes sobre OUTRO ficheiro. Um plano velho e' pior do que
  nenhum. E o passo `bend-laws` passa a ter UM texto de skip (`BEND-GATE SKIPPED`): com dois, o
  `:skipped` exige os dois e o `VERDICT: SKIPPED` que o portao nunca imprime tornava o skip um
  FAIL -- medido `failed: bend-laws=0`.)
  (Seiscentos e cinquenta e dois bytes e cinco linhas a mais do que o pin de 265171 B: o passo
  `bend-laws` passa a ser **skip-capable**. MEDIDO nesta maquina a 2026-11-05: o `wslservice`
  ficou surdo -- `wsl -d ubuntu-bend -e bash -lc true` nao voltou em **120 s**, e `wsl
  --shutdown` tambem nao voltou (rc=124 ao fim de 60 s). O portao comia entao o prazo do
  PASSO inteiro e o log dizia `STEP-DEADLINE exceeded step=bend-laws seconds=240.2` -- um RED
  que falava do relogio, nao das leis. Agora `bend-laws-gate.py` faz uma sonda de vida curta
  (`SOTTO_BEND_WSL_PROBE_S`, 25 s) e separa as duas coisas: uma lei REFUTADA continua FAIL, uma
  maquina que nao responde e' `BEND-GATE SKIPPED` (rc=0, contado em `skipped=`, nunca em
  `gate=`), e uma distro AUSENTE continua FAIL de INFRA. Dois defeitos de instrumento cairam
  com a medicao: `run_bend_version` devolvia `(texto, rc)` no ramo de excepcao e texto no
  caminho feliz, o que matava o portao num `AttributeError` em vez de dizer que a infra nao
  respondera; e o `wslpath` era pedido uma vez por lei/controlo (~16 arranques de WSL) e passa
  a ser pedido uma vez por processo.)
  (Quatro mil trezentos e noventa e dois bytes e setenta e uma linhas a mais do que o pin de
  260779 B: O PLANO DA BATERIA. A corrida perguntava ao cache UM `python` POR PASSO -- medido,
  0,124-0,150 s num passo ja' cacheado, 341 passos, **42-51 s** de interpretadores a ler o MESMO
  `_cache\battery-steps.json` e a responder `HIT` numa corrida a quente, onde nada tem de
  executar. `_main\_battery-plan.py` responde por todos **num processo** (medido: **1,84 s** para
  os 341) e `:step` le a resposta de uma variavel (`:plan_load` / `:plan_lookup`); um passo ausente
  do plano -- ou marcado DEFER porque depende do proprio ficheiro de estado que a corrida
  reescreve -- cai no caminho por passo, que continua a ser a autoridade. `SOTTO_BATTERY_PLAN=0`
  devolve o caminho por passo. Dois passos novos: `battery-plan` (`--selftest`, que compara o
  plano contra o CLI um a um nas quatro formas e nos dois modos) e o seu
  `red-as-expected-battery-plan` (`--neg-arm`, tres mutacoes plantadas numa copia: HIT inventado,
  DEFER apagado, modo rapido ignorado -- medido 3/3). Recibo:
  `_main/receipt-20261105-battery-plan.md`.)
  (Quarenta e oito bytes a mais do que o pin de 260731 B: as DUAS linhas do passo `live-queue`
  passam a nomear `worker\engine_policy.py` nas dependencias. As arms novas do varrimento de
  spools IRMAOS executam o `probe_and_spool` DESSE ficheiro e uma dependencia que o nao nomeia
  deixaria o passo em cache a descrever um arranque que ja mudou -- a mesma razao pela qual a
  linha ja nomeava `worker\live_queue.py`.
  (Quatorze linhas a mais do que o pin de 259294 B / 3182 CRLF: `live-code-freshness-control`
  (`--control`, as arms I1/I2/I3 da etiqueta) e o `red-as-expected-live-code-freshness`
  (`--neg-arm`, que repoe a lista curada numa COPIA de `code_identity.py` e exige o RED -- medido:
  `I1 cobertura: 7 de 36 .py na etiqueta`, que e' exatamente o estado de ANTES da cura. A CLASSE
  era a pior desta casa: a etiqueta dizia `FRESH` com o processo a correr outro codigo, e
  `youtube_cdp_source.py` -- o ficheiro que decide QUAL legenda vai ao ecra -- estava fora dela.)
  (Doze linhas a mais do que o pin de 257950 B / 3170 CRLF: o par `youtube-cdp-slow` + o seu
  `red-as-expected`, o prazo de uma leitura que DERRUBAVA a ligacao com o Chrome -- medido na
  instancia viva (pid 41764, 17:52) como `slow (WebSocketTimeoutException)` -> `reconnect
  (ValueError)` -> `port-closed` -> `attached` a cada ~10 s. O `break` do ramo de prazo deixava
  `payload=None`, `parse_snapshot(None)` devolvia None e o `ValueError("payload sem forma")` que
  se seguia NAO e' timeout, logo a guarda escrita em 2026-11-03 para nao fechar a ligacao nunca
  era alcancada; o mesmo ficheiro chamava `port-closed` a um `/json/list` que estourou o prazo e
  aceitava a resposta atrasada como se fosse a deste tick (id fixo em 1). Medido depois, no mesmo
  minuto: `--neg-arm` muta os tres sitios e cai 3/3 -- `NEG-ARM: PASS -- 5 arms, 3 mutants`.
  O `code-health` absorve o crescimento declarado de `app/webview/youtube_cdp_source.py`:
  bytes 56612 -> 60470, linhas 1222 -> 1292, defs 20 -> 21, `max_func` 159 -> 201 (o `_run`)
  e `except_pass` 5 -> 6 (o `close` do cano partido) -- e o de `app/webview/code_identity.py`
  (bytes 3778 -> 4453, linhas 83 -> 102, defs 1 -> 2, a funcao `code_files`) mais o
  re-export que ela custa em `app/webview/sotto_webview.py` (+314 B / +5 linhas).)
  (Quinze linhas a mais do que o pin de 256714 B: o passo `redux-arm-weights`, que faltava ao oraculo
  do interruptor do paraqueet de fundo -- sem passo ele apodreceu DUAS vezes em silencio (`FakeReader`
  sem `shed()`, `--neg-arm` morto a apontar para `worker/sotto_worker.py` quando a classe ja' vivia em
  `worker/engine_switch.py`). O oraculo agora corre a classe REAL contra o disco por nome: arma com o
  parakeet (`20/20` verde, `--neg-arm` `MUTANT VERDICT ... OK`) e recusa em UMA linha quando o
  checkpoint falta. Ligados 140 -> 141, sem_passo 111 -> 110, e a entrada de licenca com
  `REASON-MISSING preencher a mao` que o cobria foi apagada: um oraculo ligado nao precisa de licenca.)
  (Quatro linhas a mais do que o pin de 256385 B, e por isso o pin mudou: o comentario do passo
  `history-write` afirmava "o passe de batch esta' OFF por omissao", que era verdade do LADO DO
  WORKER e mentira do lado da APP -- a shell nunca passou `SOTTO_REDUX_WHEN_HIDDEN`, logo o
  interruptor nao era construido na unica instancia que o dono corre. A shell passa-o agora em
  `_child_env`, o `_main/app-target-oracle.py` pina a chave (arm e, 9/9) e o braco de producao
  foi corrido: `REDUX_SWITCH armed=true by=SOTTO_REDUX_WHEN_HIDDEN=1`, `REDUX_BATCH_ENGINE
  engine=parakeet name=onnx missing=none`, `REDUX_ENGINE_LOAD rss_mb=463.7 load_s=3.09`,
  `REDUX_SWITCH_STOP kicks=24 batch_seconds=72.56 failures=0`.)
  (Quinze linhas a mais do que o pin de 255029 B: o par `paused-pace` + o seu
  `red-as-expected`, nascido da mesma sessao VIVA e da mesma queixa de carga. Medido com o video
  PAUSADO e o painel ESCONDIDO: `YOUTUBE_LOOP_HZ hz=9.7 src_reads=755` com `YOUTUBE_TICK_MS
  avg=0` e `cdp_age_ms=16` -- o trabalho estava FORA do tick medido, numa ida e volta a CDP por
  volta, e a shell media **23,4 %** de um nucleo em REPOUSO. A escada do silencio existia mas
  `yt_mode` e' verdadeiro sempre que o ramo do YouTube corre, logo nunca descia. `poll_step`
  (funcao pura, extraida por `ast`) desce o passo com o video parado; depois da cura o laco mede
  **hz=4.0** e a shell **8,1 %**. O oraculo EXECUTA a funcao real e o `--neg-arm` devolve rc=1.)
  (Quinze linhas a mais do que o pin de 253523 B: o par `page-scan-browser` + o seu
  `red-as-expected`. MEDIDO na instancia VIVA (pid 62492, video PAUSADO):
  `EXTERNAL_CAPTIONS_READ_MS ms=1593.0 / 1547.0 / 1812.0` -- a leitura inteira dentro da
  varredura UIA da janela do Chrome, de 5 em 5 s, para concluir que uma pagina parada nao tem
  legenda. O `--neg-arm` desarma a guarda numa copia e o passo exige rc=1 + `NEG-ARM PASS`; o
  oraculo devolvia 0 ao apanhar o defeito, o que faria de um controlo um portao que nunca pode
  falhar -- corrigido no oraculo (`return 1 if ok else 0`), nao no passo.)
  (Treze linhas a mais do que o pin de 252313 B: o par `history-write` + o seu
  `red-as-expected`, nascido do relato do dono -- *"o painel da direita fica perdendo
  historico"*. MEDIDO no log vivo dele: 3830 `CAPTION_APPLIED`, **0** `HISTORY_APPEND`,
  `history/2026-11-05/` inexistente -- o choke point exigia `producer:'redux'`, o passe de
  batch esta' OFF por omissao e nenhum outro motor carimba a chave, logo o transcript tinha
  ZERO escritores e a recusa era um `return` mudo. O oraculo executa a decisao, o call
  site, a proveniencia e o `history_append` num root temporario; o `--neg-arm` repoe a porta
  antiga em COPIA e exige rc=1. Medido: 1221 commits do stream -> **130** linhas fechadas no
  disco (antes: 0), `producer=` carimbado, nenhum `provisional-draft` no ficheiro.)
  (Doze linhas a mais do que o pin de 251219 B: o `red-as-expected-worker-start-wiring`, o braco que
  faltava a um portao que era um verde SEM controlo. Nasceu de uma medicao de hoje: o arranque das
  16:19:10 escreveu `WORKER_AUTOSTART=started reason=default` **duas vezes** -- 16:19:11.098 pelo
  spawn real e 16:19:13.960 por um ramo que viu o bridge ja' armado e escreveu `started` as mesmas.
  Quem le' o log conclui que dois workers nasceram e que 1,9 GB foram lidos duas vezes; nenhum dos
  dois bracos e' verdade. Agora o ramo passa pelo `start_worker`, que recusa no MESMO shape de todas
  as outras recusas (`WORKER_AUTOSTART=declined reason=default by=start_worker
  cause=already-running`), e o `--neg-arm` muta quatro sitios e exige rc=1 -- medido 4/4.)
  (Dezanove linhas a mais do que o pin de 249653 B: o par `punct-model` + o seu `red-as-expected`,
  a pontuacao DE MODELO que ele pediu -- *"usa pontuacao de forma inteligente"* -- respondida com o
  que a casa mediu em vez de com uma opiniao: `sherpa-onnx-online-punct-en` (Apache-2.0, **int8
  7,1 MB**, CPU 1 fio) carrega em **75-91 ms** e pontua em **6,1-8,5 ms por linha** (mediana 6,8),
  contra um chunk de 560 ms. A metade que importa e' a guarda de lingua: o mesmo modelo sobre
  portugues devolve `EU Gosto Muito, disso sabe como E que E` -- caixa aleatoria com aparencia de
  pontuacao --, logo tag que nao comece por `en` e' identidade. Pontua SO a linha FECHADA; a
  parcial nao leva marca nenhuma, porque o comma a saltar de sitio a cada chunk e' o defeito de
  render que ele chamou inadmissivel. `--neg-arm` 4/4.)
  (Vinte e oito linhas a mais do que o pin de 245095 B: TRES pares novos, cada um com o seu
  `red-as-expected`, todos nascidos de defeitos que o dono viu na sessao dele hoje.
  `caption-switch-race` -- *"o botao fala que a legenda ta off, mas ta on"*: o texto aceito
  ANTES do desligar chegava ao `_drain_caption_pending` DEPOIS do `ov.show(False)` e chamava
  `ov.show(True)` (a flag era lida no ENFILEIRAR, nao na PINTURA); o oraculo executa as duas
  funcoes REAIS por AST e mede tambem o `on` que devolve a linha fresca ao ecra sem esperar a
  proxima (o 1-1,5 s que ele mediu; 2 s e o teto, abaixo da varredura de 6 s).
  `word-glue` -- *"muito rapido"* e a legenda sai `very fa st` / `fuck er`: o `▁` e posicional,
  nao lexical (18 de 19 chunks de `_main/word-split-trace.json`), e a cura cola cauda de 2
  letras com vogal a cabeca sem vogal, mais um `s` sozinho a esquerda (297 casos no log).
  `punct-prosody` -- a ordem dele de hoje: pontuacao inferida do timing/energia da voz, com
  identidade quando nao ha pausas medidas.)
  (O pin anterior, de 245095 B / 3022 CRLF, era o do PRAZO POR PASSO e do TECTO DA CORRIDA.
  O par do tecto corre no FIM da lista, imediatamente antes do sumario, porque ele le'
  `_cache\battery-steps.json` -- que a corrida escreve passo a passo. Em qualquer outro sitio
  mediria "a corrida ate' aqui", um numero menor do que o verdadeiro: a mesma classe de mentira
  que o portao existe para apanhar.
  Doze delas sao o par `battery-budget` + o seu `red-as-expected` -- o portao do RELOGIO que a
  bateria nunca teve: ratchet de +5 % sobre o baseline e nenhum passo novo acima de 240 s, com o
  TARGET de 60 s impresso a distancia (`RATCHET-OK ... TARGET NOT MET (gap 5741.2s de 60s)`)
  porque um `PASS` ao lado de 5 741 s de gap seria o verde que nao mede nada. O `--neg-arm` muta a
  LEITURA, nao o codigo: infla um passo 10x e exige o RED do mesmo `judge`.)
  (Vinte e quatro linhas antes disso, a partir do pin de 241497 B: o PRAZO POR PASSO -- o par
  `step-deadline` + `red-as-expected-step-deadline` e o bloco de comentario que diz por que.
  `:step_run` deixou de correr `!S_CMD!` sem relogio: corre-o sob `_main\step-deadline.py`
  com `SOTTO_STEP_DEADLINE_S=240`, que mata o JOB do passo e devolve **rc=124**, um codigo que
  nenhum oraculo devolve por acidente. Nasceu de dois passos presos medidos nesta arvore --
  `panel-hidden-at-startup-oracle` **3 781,6 s** e `youtube-cdp-boot-oracle` **21,6 min** -- que
  deixaram a corrida sem sumario e o sumario ANTERIOR no disco a ler-se como o de agora.
  Preco medido do wrapper: **95 ms por passo executado** (~24 s numa corrida inteira), e o filho
  escreve no stdout do wrapper, logo o log do passo continua a ser a evidencia. O `--neg-arm`
  muta o `job_terminate` numa copia e o selftest (5 arms, A5 = um processo ALHEIO sobrevive)
  tem de dar RED -- a primeira versao matava por caminhada de arvore e matou **dois `cargo.exe`
  de outra lane**; agora e' job object e o A5 e' o braco que prova que nao volta a acontecer.)
  (Vinte e oito linhas a mais do que o pin de 239421 B: os tres passos do `Ctrl+Space`
  TOMADO fora de jogo e DEVOLVIDO ao jogo -- `ctrlspace-swallow` + o seu
  `red-as-expected` + `ctrlspace-swallow-os`. Nasceu da ordem do dono de 2026-11-05:
  *"faz o control espaço nao inputar espaço pra outros apps. mas desativa isso em
  jogos"*. O oraculo corre o fio REAL (`LiveHotkeyThread`) e a tabela REAL
  (`gaming_mode.live_hotkey_plan`) contra um `user32`-gravador (14 arms, `--neg-arm`
  4/4) e o probe mede no Windows desta maquina o que nenhum fake da': a segunda
  reserva da mesma combinacao devolve **1409** e o `Unregister` devolve a tecla
  (medido: `first=1 second=0 err=1409 third=1`).)
  (Dezenove linhas a mais do que o pin de 237754 B: o par `caption-kept-on-hide` + o seu
  `red-as-expected`, que executa a `SottoShell.hide_panel` REAL por AST e prova que esconder o
  painel nao toca na legenda ao vivo (`CAPTION_WINDOW_KEPT`), com o `--neg-arm` a desarmar a
  guarda no sitio exato -- 1/1 recusado. Antes disso, vinte linhas a mais do que o pin de
  236106 B: o par `panel-prefix-row` + o seu
  `red-as-expected-panel-prefix-row` -- o MURO DE PREFIXOS que o dono viu as 06:07:33 e chamou de
  *"historico completamente patetico"*: nove `<li>` para a mesma frase, cada uma com mais palavras
  que a anterior, porque `rowIdentity` devolve `null` sem `start` e `addCaption` apendava em cada
  commit. O oraculo extrai a funcao REAL de `app\panel\panel.js` e o `--neg-arm` mutila tres sitios
  numa copia, medido 3/3 CAUGHT.)
    (Vinte e tres linhas a mais do que o pin de 234270 B: o par `panel-nav-stall` + o seu
  `red-as-expected`, a NAVEGACAO QUE NAO VOLTA NAO LEVA A APP COM ELA. Nasceu de duas largadas
  medidas nesta noite: a forma nasce (`PANEL_SHOW_GATE installed`, `UI_WATCHDOG_STARTED hwnd=..`) e
  NENHUM documento carrega -- `STARTUP_NOT_READY s=15/30/60` e mais nada, sem `PANEL_STATE_WRITER`
  (todos os instrumentos leem esse ficheiro e dizem `STALE`), sem legenda e sem uma linha a nomear
  o browser. Dois defeitos no mesmo vigia: armava-se DENTRO do handler de carregamento (o estado
  que ele existe para cobrir era o unico onde nao estava armado) e o retry chamava o `load_url`
  INLINE, que nao volta com o browser morto -- um vigia cuja recuperacao pode pendurar nunca
  dispara. Agora arma na criacao da FORMA, o retry corre em thread propria, e a linha nomeia o
  estado (`state=url='unknown' core=no`, medido). O oraculo conduz o METODO real com um `load_url`
  que nunca volta (5 arms) e o `--neg-arm` repoe o retry inline numa COPIA e exige o vermelho.)
  (Catorze linhas a mais do que o pin de 232945 B: o par `load-bg-window` + o seu `red-as-expected`,
  o prazo da JANELA DE FUNDO da carga. Nasceu do recibo de outra lane
  (`_main/receipt-20261105-extrema.md`, SottoAudit3): a janela `PROCESS_MODE_BACKGROUND_BEGIN`
  esticava 1,7 s de CPU para **33,96 s** de parede sem comprar **0,2 %** de memoria, e agora tem
  prazo de 0,75 s (`LOAD_BG_MAX_S`), com `load_bg_closed_by` a dizer qual das duas saidas fechou a
  janela. O recibo declara tres bracos que NENHUM passo executava; o oraculo
  `_main/load-bg-window-oracle.py` conduz as funcoes REAIS e mede os seis (A1-A6), incluindo um
  timer de 50 ms de verdade, e o `--neg-arm` derruba cada mutacao pela SUA arm (3/3).)
  (Catorze linhas a mais do que o pin de 231597 B: o par `parakeet-ultra` + o seu `red-as-expected`,
  a comparacao de motores de FUNDO. O candidato `parakeet-ultra` foi medido contra o `redux` no
  MESMO audio e RECUSADO: WER identico (0,1154 — os mesmos 2 subs + 1 ins), 3,5x mais lento
  (3,626 -> 12,873 s no clipe de 15 s), 2,1x de RSS (1 793 -> 3 837 MB), carga a frio 3,2x
  (7,50 -> 24,36 s) e TRUNCA: no clipe de 90 s devolve 9 palavras onde o redux devolve 62. O passo
  positivo e' `heavy` (carrega 2,4 GB); o negativo e' `always` porque NAO carrega modelo nenhum —
  prova o juiz de WER (9/9). Recibo: `_main/receipt-20261104-parakeet-ultra-refused.md`.)
  (Dezasseis linhas a mais do que o pin de 230220 B: o par `paint-row-seam` + o seu
  `red-as-expected`, a costura da perna do OLHO. O painel ja' produzia
  `CAPTION_PROVISIONAL_PAINT` e o shell nao instalava o gancho, logo a perna que mede
  `push -> pintura` so' existia para sondas de DOM e o log media o `commit` -- o FIM do que
  o olho ja' tinha visto. O portao executa os tres bracos contra o ficheiro que embarca e o
  `--neg-arm` desarma cada um numa COPIA, medido 3/3.)
  (Quatro familias de passos a mais do que o pin de 226610 B: os quatro do `panel-commit-stable`
  (o commit da linha deixa de ser um relogio -- o worker prova `stable:true`), os dois do
  `worker-park` (um veredito de dispositivo estaciona em vez de morrer e recarregar 1,9 GB: 3 278,8 s
  de recarga em 149 corridas + 2 366,8 s em 102 re-spawns `no-audio`, medidos em 593 `BRIDGE_SPAWNED`)
  e os do `caption-budget` citados abaixo. Medidos no merge: `panel-commit-stable` VERDICT PASS e
  `--neg-arm` rc=1 (`NEG-ARM: PASS`), `worker-park` GREEN 11/11 e `--neg-arm` rc=1, wiring PASS
  (ligados=125), class PASS, undefined-names GREEN.)
  (O pin anterior era 226610 B / 2807 CRLF:
  (O passo do `caption-budget` passou a nomear `app\webview\sotto_webview.py` nas dependencias: as
  arms 7-9 executam o predicado `caption_lag_aged` QUE EMBARCA, e uma dependencia que nao o nomeia
  deixaria o passo em cache a descrever um shell que ja mudou. Era 226581 B antes.)
  (Dezasseis linhas a mais do que o pin de 225203 B / 2791 CRLF: o par do governador
  `caption-budget-oracle.py`, que o proprio contrato da seccao 0 nomeava e que NAO EXISTIA (n-15 do
  audit). Medido no log do dono: `CAPTION_PAINT_LAG` e' BIMODAL -- 76,7 % das linhas com `queue_ms`
  < 100 ms e 2,9 % acima do prazo, 22,4 % a esperar o prazo inteiro com 100 % acima -- por isso o
  governador publica os dois modos com as taxas, o p95 e a percentagem acima do prazo, e recusa um
  p50 como veredicto (a fatia de 30 min da espiral deu 2 895 ms e o parse de 42 h deu 6 ms). O
  `--neg-arm` muta um corpus limpo em tres sitios e exige os tres RED, medido 3/3.)
  (O pin anterior era de 225203 B / 2791 CRLF:
  **2791 CRLF** / 0 bare LF, sha256 `EF60698A8BF57AEAB2628A291C94C3C6EB44FAFFA64EBEFDDC1C5EF8B9169C46`.
  (Catorze linhas a mais do que o pin de 224071 B / 2777 CRLF: o passo `dead-app-exit`, 11 arms com a
  prova do detector DENTRO do passo (o mutante que desarma o escalonador fica PRESO). Nasceu da ordem
  do dono de 2026-11-04 e do que o log dele mediu: `UI_WATCHDOG_EXIT code=9` as 13:01:36 e o processo
  FICOU com 36 threads, 8 de 10 janelas a nao responder e o worker filho com 3,9 GB. A hipotese do
  `os._exit` preso num read de pipe foi REFUTADA por medicao; o que sobrevive e' o `ExitProcess` a
  nunca voltar com CLR/WinForms/WebView2/GDI+ carregados. A cura e' `_hard_exit` com escalonamento de
  2,5 s, um matador externo por HANDLE (4 s, com creation stamp: um pid reciclado nunca e' morto) e
  reap limitado; o `exit_killer.py` mata os FILHOS primeiro.)
  (O pin anterior era de 224071 B:
  **2777 CRLF** / 0 bare LF, sha256 `29C76C018FF136B23287C85C4D84A035CC2D6CD9CF42B1F2C7EA1571887D19EB`.
  (Dezenove linhas a mais do que o pin de 222416 B / 2758 CRLF: o par `shell-priority` + o seu
  `--neg-arm`, 4 arms. Nascido do L10 do audit, medido: a shell viva (pid 20448) E o worker corriam
  a `BELOW_NORMAL` e o par de controlo ao lado (explorer, pwsh) a `NORMAL` -- o tecto vinha do
  largador. A cura e' `raise_visible_priority()` no inicio do `main()`, com `was`/`now` no log; o
  worker fica `BELOW_NORMAL` de proposito. O proprio braco achou um defeito meu: as constantes NAO
  sao monotonicas (BELOW_NORMAL 0x4000 > NORMAL 0x20), por isso a comparacao numerica lia "ja'
  chega" -- o oraculo plantou a despromocao e apanhou-o.)
  (Quinze linhas a mais do que o pin de 221321 B / 2743 CRLF: o passo `freeze-census`, que corre
  `_main/freeze-census.py --selftest`. Nascido da ordem do dono de 2026-11-04 -- *"o PC inteiro
  trava: herdr, os terminais dentro dele, o chrome, tudo ao mesmo tempo"*. O censo mede commit, procs,
  threads, handles e CPU da maquina em tres syscalls, ranqueia os que seguram CPU so' de 10 em 10 s,
  e publica `FREEZE`/`FREEZE_SEVERE` a partir do ATRASO do proprio tick (a maquina esfomeada atrasa
  o laco). O `--selftest` planta um `time.sleep` de 1500 ms e exige a linha com a magnitude plantada.)
  (Vinte linhas a mais do que o pin de 219712 B / 2723 CRLF: o par `tray-menu` + o seu `--neg-arm`,
  12 arms. Nasceu da ordem do dono de 2026-11-04 -- *"icone do sotto e' uma merda de mexer. botao
  direito e' travado pra abrir o menu dele ... tipo o vanguard"* -- e mede as TRES causas que faziam
  o menu parecer travado: a janela da bandeja era `HWND_MESSAGE` (nao pode ser activada, logo o
  `SetForegroundWindow` que fecha o menu ao clicar fora nao pega; o discriminador que sobreviveu ao
  mutante e' o bit `WS_POPUP` -- medido 0x4C00000 no mutante contra 0x84000000 na cura, porque o
  `GetAncestor(GA_PARENT)` NAO e' 0 numa janela message-only neste build), faltava o
  `PostMessage(hwnd, WM_NULL)` do receituario MSDN, e os DOIS botoes abriam o menu (o esquerdo
  passou a abrir o painel, como em qualquer app da bandeja). `--neg-arm` medido 3/3 CAUGHT.)
  (Dezoito linhas a mais do que o pin de 218401 B / 2705 CRLF: o par `fusion` + o seu `--neg-arm` --
  o core da fusao stream/refinado, que a ordem do dono de 2026-11-04 poe no lugar de qualquer
  deteccao de falantes. 14 arms; o `--neg-arm` muta quatro vezes e exige as quatro vermelhas.)
  (Doze linhas a mais do que o pin de 217007 B / 2693 CRLF: o par `youtube-first-at-boot` + o seu
  `--neg-arm`, 9 arms. Ele mede o gate que faltava -- enquanto o player fornece linha o texto de
  estado e' RETIDO (`CAPTION_LOADING_TEXT_WITHHELD reason=player-track`), o pipeline publica a
  ordem (`CAPTION_PIPELINE_ORDER steps=cdp,watcher,worker`), o fallback sai UMA vez por episodio
  de silencio, e a escolha de aba decide em vez de adiar: `ambiguous` tres vezes seguidas era o
  `src='?'` medido no log do dono as 12:15:15.
  Vinte e duas linhas a mais do que o pin de 215335 B / 2671 CRLF: o par `gaming-hotkey` + o seu
  `--neg-arm` (53 arms) e o par `youtube-first-at-boot` + o seu (9 arms). O primeiro nasceu de tres
  medicoes que nao se substituem: `Ctrl+Space register_ok=True` (**a tecla esta' livre**; `Alt+C` da'
  1409 porque a instancia do dono a tem), o caminho do toggle executado com um `user32` gravador
  (`SetWindowPos` flags 83 + `ShowWindow` 4/0, zero APIs de primeiro plano) e o observador a pedir
  `ABOVE_NORMAL`. O segundo mede o gate que faltava: enquanto o player fornece linha, o texto de
  estado e' RETIDO (`CAPTION_LOADING_TEXT_WITHHELD reason=player-track`), e a escolha de aba decide
  em vez de adiar (`ambiguous` tres vezes seguidas era o `src='?'` medido as 12:15 no log dele).
  Dezassete linhas a mais do que o pin de 213662 B / 2654 CRLF, do par `first-capture-fast` + o seu
  `--neg-arm`: mediu-se que **33,5 s dos 48,4 s** de arranque nao eram o modelo -- a primeira escolha
  de endpoint abria um `IAudioClient` por endpoint (3,8 s) para devolver um MORTO, a morte por
  dispositivo custava 15 s e o silencio era indistinguivel de um endpoint morto. Agora a escolha
  pergunta ao medidor VIVO (735 ms, 6 endpoints, **sem abrir cliente**), o morto declara-se em 2 s com
  rotacao IN-PROCESS (sem recarregar 1,9 GB) e a morte por dispositivo e' 250 ms. O braco negativo
  muta quatro vezes e o `--neg-arm` apanha 4/4. A medicao no arranque DO DONO continua UNMEASURED.

  Dez linhas a mais do que o pin de 212778 B / 2644 CRLF: o par do motor quente
  (`warm-engine` + `red-as-expected-warm-engine`), que roda 22 arms e exige 6/6 mutantes apanhados --
  cada mutante derrubado pela SUA arm, e o `--neg-arm` deixa zero processos e zero `warm-engine.pid`.
  O anexo ao motor mede p95 16 ms em 20 tentativas. A1/A2/A3 (o caminho de 3 s) continuam
  UNMEASURED: pede uma shell com audio, e isso e' a tela do dono.
  Vinte e oito linhas a mais do que o pin de 210085 B / 2616 CRLF, de dois pares. Quinze:
  `caption-overlay-screen` -- o oraculo que executa o `_screen_proof` REAL contra uma janela LAYERED
  oculta (arm A2 com uma RECONTA independente do predicado), exige `alpha=0` a dar RED por
  `invisible` (a classe do P0 do dono: `visible=true` e nada no ecra) e muta uma COPIA de
  `caption_overlay.py` quatro vezes -- mais o seu `--neg-arm`. Antes dele, `grep -c
  CAPTION_OVERLAY_GEOMETRY` nesta bateria dava 0: o campo que respondia a queixa do dono existia e
  nenhum portao o lia. Treze: `lag-note-cost`, que o merge do commit de perf (1c92e39) deixou SEM
  passo -- o `battery-wiring` dizia `new-unwired 1 oraculo(s) sem passo e sem licenca:
  lag-note-cost-oracle.py` -- e agora corre com o seu `--neg-arm`.
  Vinte e tres linhas a mais do que o pin de 207838 B / 2597 CRLF: os dois pares que as lanes de hoje
  escreveram e deixaram FORA da bateria -- `youtube-hidden-clock` (a pintura parada com a faixa como
  segunda testemunha) e `youtube-cdp-boot` (o arranque a pedir a porta CDP) -- mais os seus `--neg-arm`.
  O `battery-wiring` acusava-os com razao: `new-unwired 2 oraculo(s) sem passo e sem licenca`.
  Antes disso, dezoito linhas: o par `time-to-first-caption` + o seu `--neg-arm`, skip-capable, que le o log VIVO
  e mede do carimbo de arranque da shell ate' a primeira pintura -- 65 037 ms hoje, e PASS so' abaixo
  de 3000 ms. O pin anterior, de 206081 B / 2579 CRLF, era o de depois dos passos de `line-closed`
  serem apagados.)
  (Os passos de `line-closed` foram APAGADOS: o `_panel2-dom-probe.js` acusou a cura
  como regressao -- 94/94 verdes antes, 92/94 com ela, `real=[2,...] want=[1,...]` nas
  duas arms da caixa -- e o caso medido no dono (`CAPTION_IN ... final=false`, espera
  de 1503 ms) era um PARTIAL, que essa cura nunca tocava. Revertido o commit em
  `caption-formulation.js` e re-medido: 94/94 verdes outra vez. Fica o `reveal-clock`,
  que e' a latencia que o dono VE.)
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

## A LEI DO CUSTO - um laco dorme o ORCAMENTO, nunca o proprio trabalho (2026-11-08)

Nascida de uma DM de stutter do watcher (2026-11-08: `pythonw.exe(42572)`, 24 episodios em 60 min) e do que ela
obrigou a medir. O culpado ficou nomeado por instrumento externo, com o **tid** e a **linha**:

```
SHELL-THREAD-BUDGET pid=42572 total=103.4% top=93.6% tid=48064 sotto-caption-tick
```
(duas amostras, mesmo tid; `total` = % de UM nucleo). Duas metades, as duas medidas:
o processo vivo (arrancado 04:01:44) pede **60 Hz sem limite nenhum** (`git show 7ec728d^` prova:
`FRAME_S = 1/60`, zero `_limit_by_paint`) e com a pintura a **11,6 ms p95** (2026-11-08) o piso e' 69 % de um
nucleo; e a cura de 240 Hz escrita as 07:2x punha o **periodo IGUAL ao custo** (`cost * 1.02`) --
um laco que dorme exactamente o tempo que trabalha gasta **100 % de um nucleo por construcao** (aritmetica, 2026-11-08).

**AS DUAS REGRAS, e nenhuma delas e' opcional:**

1. **PERIODO = CUSTO / ORCAMENTO, nunca o custo.** O divisor e' um numero declarado (aqui
   `CAPTION_FRAME_BUDGET = 0.40`) e o log diz os tres (`CAPTION_FRAME_LIMIT paint_ms=.. budget=..
   rate_hz=..`). A taxa sobe quando o trabalho fica barato, e o nucleo nunca passa do orcamento.
   Vale para QUALQUER laco que derive o passo do proprio custo: tick de pintura, timer, poll,
   census. A classe ja' custou tres vezes nesta casa -- o `outside-click-timer` a 2 569 Hz, o censo a
   1 591 Hz e agora este a 93 % (medido 2026-11-08).
2. **UM INSTRUMENTO DE CPU SEM PASSO NA BATERIA NAO E' UM INSTRUMENTO.** `_main/shell-thread-cpu.py`
   media CPU por fio com o NOME, tinha `--neg-arm`, e tinha **zero chamadores** -- por isso a
   primeira medicao do stutter foi a queixa do dono, 149 vezes em 14 dias. O passo e' o par
   `shell-thread-budget` + `red-as-expected-shell-thread-budget` (`_main/shell-thread-budget-oracle.py`:
   total <= 25 % de um nucleo, um fio <= 15 %, o fio mais quente COM NOME, ratchet de +20 % sobre
   `_main/shell-thread-budget-baseline.json`; sem shell viva ele diz `VERDICT: SKIPPED`, e um passo
   saltado nunca e' um portao que passou).

   E o proprio portao custou QUATRO defeitos no dia em que nasceu, todos da mesma classe -- um
   instrumento que devolve `None` por defeito proprio e' indistinguivel de "nao houve nada":
   `io.open` sem `import io` (o `NameError` caia num `except Exception: return None` e o julgamento
   seguia SEM a serie), o desempacotamento de `[(nome, pct)]` ao contrario, `instance_fresh()` a ler
   `out[1]` (o stdout) em vez do rc e a importar um helper cujo nome tem HIFEN (respondia `None`
   sempre), e o `SKIPPED` mudo sem shell viva. Corrigido o quarto: sem shell ele IMPRIME a pior
   janela da serie antes de saltar -- `total=105% sotto-caption-tick=87% @ 2026-11-08 04:54:22` --,
   que e' exactamente o numero que a amostra de 5 s em repouso perdia (`19,7 %`, verde).

**O DEVER DE TRANSPORTE desta lei:** quem mexer num laco que se auto-cronometra corre
`python _main/shell-thread-budget-oracle.py` antes e depois e cola os dois numeros com o pid. Um
stutter "resolvido" sem pid, fio e linha nao e' um stutter resolvido. Recibo de referencia:
`_main/receipt-20261108-stutter-caption-tick.md`.

## UM LIMITE DE MEDICAO LARGA UM INSTRUMENTO, NAO UM PARAGRAFO (2026-11-09)

Tres fatos do mesmo dia, nesta ordem:

- o dono, 2026-11-02: *"nao mandei tu diagonisticar e parar. é pra diagnosticar e arrumar"*;
- o watcher acusou `python.exe(20676) sotto_worker.py 303,1 %c` e `pythonw.exe(50452) 81,3 %c`, e
  **nenhum** dos dois podia ser atribuido: `py-spy` devolve `err=5` nesta arvore (o processo do dono
  corre `high`, a pane `medium`);
- o instrumento que respondia "qual fio" existia com `--neg-arm` e **zero chamadores**
  (`_main/shell-thread-cpu.py`), e o banco de fios que devia responder "quanto custa cortar"
  estava **morto** -- `rc=1`, `no checkpoint in worker\models\parakeet-redux-ternary`, `0 palavras`
  nas tres caps, com tres "x realtime" impressos por um filho que morreu em 0,25 s.

**A LEI, em tres linhas:** (1) um limite de medicao nao fecha o assunto -- ele abre o instrumento
que nomeia o ator DA PROXIMA VEZ, no mesmo turno (`_main/cpu-tripwire.py`: limiar 250 %c, janela
5 s, captura por FIO e o registro dizendo `stack=unavailable` e por que); (2) um instrumento morto
imprime **nome e rc da morte** e o recibo diz "morto" -- os numeros de um filho que morreu nao se
citam, nem "para comparar"; (3) um probe que carrega modelo ou varre disco corre **caged desde a
primeira invocacao** (`python -m watcher run --cpu 40 --`, ver a lei do custo acima): medido
2026-11-09, o meu `nemotron-thread-bench` sem tecto foi o **maior produtor de pressao** do stutter
do dono (pid 56092, `io 88,5 MB/s`, tres `tick.stall` na mesma janela) -- o culpado era o
instrumento, e o recibo esta' em `_main/receipt-20261109-thread-bench-stutter.md`.

## A LEI DOS TESTES - todo teste, existente ou futuro (ordem do dono, 2026-11-05)

Verbatim: *"QUALQUER TESTE EXISTENTE OU QUE SERÁ IMPLEMENTADO, DEVE SER IMPLEMENTADO DESSE JEITO PRA
MENOR DESPERDÍCIO DE TEMPO E QUALIDADE MÁXIMA"*, e *"por que é completamente BURRO voce levar mais
que um minuto pra rodar COISAS JA GARANTIDAS EM VARIOS LUGARES DA BATERIA"*.

Medido nesta arvore antes de a regra nascer (`_cache\battery-steps.json`, 320 passos registados,
2026-11-05): **96,7 min** de tempo de passo, **86,0 % em 20 passos**, o pior **3 781,6 s** num unico
passo; os 254 passos abaixo de 5 s somam **277,8 s (4,8 %)**. O custo nao esta' nas provas baratas: esta'
numa cauda pesada **sem tecto** e numa corrida monolitica que re-executa a cauda para re-imprimir
vereditos que ja' tem.

Seis propriedades, nenhuma opcional:

1. **PRAZO POR PASSO.** `_main\step-deadline.py` (selftest de 5 arms + `--neg-arm`), piso da casa
   `SOTTO_STEP_DEADLINE_S=240`, corte mata o **JOB** do passo (nunca uma caminhada de arvore) e
   devolve **rc=124**, que nunca conta como verde. Um filho cortado escreve `STEP-DEADLINE exceeded`
   no log do proprio passo.
2. **TECTO DO RUN DEFAULT EM SEGUNDOS.** 60 s a quente e' o numero da casa; o que nao cabe e' classe
   `heavy` (opt-in), e um passo saltado e' SKIPPED, **nunca** verificado. O portao instalado hoje e'
   `_main\battery-budget-oracle.py`: ratchet de +5 % (medido 2026-11-05) sobre `battery-budget-baseline.json`, passo novo
   acima de 240 s e' RED, e o TARGET de 60 s e' impresso com a distancia
   (`RATCHET-OK ... TARGET NOT MET (gap 5741.2s de 60s)`) -- ele nunca se apresenta como "rapido".
3. **UM INVARIANTE, UM PORTAO DONO.** O segundo passo que prova o mesmo invariante e' um `crosscheck`
   declarado com custo medido, ou e' apagado: re-provar paga-se em **toda** corrida, para sempre.
4. **FAKE ANTES DO PRODUTO.** Largar a app/dispositivo e' braco `heavy`, nao teste unitario.
5. **NASCE COM O BRACO VERMELHO.** A mutacao tem de o derrubar HOJE (o braco negativo devolve o codigo
   de "apanhado", nao 0); populacao zero = `CANNOT-MEASURE`, nunca PASS; veredicto em cache leva o
   hash do proprio instrumento; duas corridas concordam.
6. **ABORTO NAO E' VEREDICTO.** O sumario escreve-se no fim, carimbado com run id + inicio, e o leitor
   recusa um sumario mais velho que a corrida que esta' a julgar.

**DEVER DE TRANSPORTE - parte do "done".** Toda mudanca que altere COMO o trabalho se faz escreve a
regra AQUI, no mesmo commit: este ficheiro e' lido por este assento e por **todo** subagente
despachado, e e' o unico lugar onde uma regra sobrevive a sessao. Forma obrigatoria: a lei datada com
o numero que protege, o mecanismo (comando + rc + o que um skip significa) e o orcamento em
segundos/contagens -- e depois re-medir qualquer pin deste ficheiro que a mudanca tenha tocado. A
fonte longa da regra (as seis propriedades, com os detectores D45-D52) vive na skill
`extreme-optimization-audit` §L12-bis/§L12-ter, e no `task-resolver` ("Test economy and the
carry-forward duty").

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
