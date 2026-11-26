# Sotto — contexto do repo para todo agente e subagente

Este ficheiro carrega as **REGRAS**, não a história. A história completa (números verbatim, proveniência e narrativas de incidente) vive em `docs/AGENTS-archive-20261021.md`, em `docs/*.md` e em `_main/receipt-*.md`. Em conflito, vale a re-medição. Dever de transporte: uma mudança que altera COMO o trabalho se faz escreve a regra AQUI, no mesmo commit.

## ASSUME THIS MACHINE IS 10x WEAKER THAN IT IS — AND WRITE THE CODE THAT WAY (owner order, 2026-11-11)
Verbatim: *"UPDATE YOUR LOCAL AGENTS.md SO YOU STOP CAUSING PERFORMANCE DROPS ON THIS COMPUTER.
ASSUME THIS MACHINE IS 10x WEAKER THAN IT IS AND WRITE THE CODE THAT WAY: one heavy job at a time, a
declared ceiling in threads/MB/s/GiB measured BEFORE the job starts (not after it hurts), cache and
resume so nothing is redone, and no unbounded loop, fan-out or in-memory accumulation. THROTTLING IS
THE WORST OF THE APPROACHES: every preferable approach is a genuine optimization -- do less work, do
it once, batch it, reuse it, make it incremental, drop the duplicate -- and a cap only comes after the
work itself got cheaper. A limit you did not measure is not a limit."*

Cinco obrigacoes, e a ordem entre elas e' a propria ordem dele:

1. **UM trabalho pesado de cada vez**, e so' com o lease do gate central
   (`I:\!manager\tools\performance-gate.py`). `unknown` nao e' `green`, um skip nao e' aprovacao, e
   dois agentes a varrer disco em paralelo sao o stutter que ele reporta. Heavy = um carregamento de
   modelo, uma corrida de bateria, uma varredura de censo, um codec, um sweep de corpus inteiro; e
   ela corre atras do cager do proprio projeto desde a PRIMEIRA invocacao
   (`python -m watcher run --cpu 40 -- …` aqui).
2. **O tecto e' DECLARADO ANTES do trabalho**, em escola de threads (por sessao, nao por processo),
   em MB/GiB de RSS/commit, em MB/s de IO e em numero de ficheiros por varredura. Depois mede-se e
   colam-se os dois numeros. Um numero escrito DEPOIS da maquina doer nao e' um tecto, e' uma desculpa
   com digitos.
3. **Cache e resume por CONTEUDO** (hash dos bytes de entrada + parametros), incremental (so' as
   combinacoes novas) e delta (`MISS <key>` / `CACHE HIT <key>`). A mesma pergunta re-executada com
   uma flag diferente e' zero informacao nova (ver
   `_packs/performance/extreme-optimization-audit` §"Reuse before re-running").
4. **Nada de laco, fan-out ou acumulacao sem tecto**: nem thread por evento, nem re-arma de timer por
   tick, nem `list`/`dict`/buffer que cresce com o tempo de vida do processo (tecto declarado + corte
   CONTADO + linha que o diz, como o `REDUX_FUSE_TRIMMED`). Uma fila tem tecto e CONTA o que largou
   (`LOG_STDOUT_SUPPLIED dropped=N` e' a forma), e um laco que deriva o proprio periodo divide o
   custo por um orcamento declarado em vez de dormir o custo.
5. **O throttle vem DEPOIS da optimizacao, nunca antes.** Primeiro faz-se menos trabalho, uma vez,
   em lote, reutilizado, incremental, sem duplicacao; so' o que sobrar desse exercicio pode levar um
   tecto -- e o tecto nao e' a cura: o `--cpu 40` do watcher limita CPU e NAO limita IO, logo um
   trabalho que le' disco precisa do seu proprio duty cycle na origem, com o custo do lote medido e o
   descanso derivado dele (`ratio = 4.0`), nunca um `sleep` fixo por lote.

O instrumento do disco e' `python I:\!watcher\tools\artifact-census.py --project H:/sotto [--budget-gib N
--gate]` antes e depois, com os dois numeros e o volume; o do processo e' o pid + o fio COM NOME
(`_main/shell-thread-cpu.py`) e a arvore (`_main/tree-cost-oracle.py`). **Uma medicao nao e' trabalho;
uma sonda que mede queimando a maquina e' o defeito** -- toda sonda tem o seu proprio tecto de fios e
de IO, a sua propria cache e o seu proprio prazo. E a frase que resume a lei:
**um limite que nao foi medido nao e' um limite.**

### A `--threads N` FLAG IS NOT A PROCESS BUDGET WHEN TWO LIBRARIES RUN IN ONE PROCESS (measured 2026-11-17)

Medido 2026-11-17: um peer lane sampleou tres trabalhos pesados "from H:/sotto" ao mesmo tempo,
somando **1276 % de um nucleo**; o `2` foi aplicado **duas vezes no mesmo processo** (`torch.set_num_threads(2)`
para o separador e `intra_op_num_threads=2` para a sessao ASR), logo o total do processo era 4 fios.

- **The budget is the SUM over every pool alive in the process, and it is declared as a process
  total.** `worker/engine_serialization.py` is the shipped example of the arithmetic (`total`, `live`,
  `small`, `batch`); a second library beside the first spends the same budget, it does not double it.
- **The process PRINTS what the libraries actually hold**: `THREADS process_budget=<n>
  torch=<torch.get_num_threads()> ort_intra=<session value> env OMP=.. MKL=.. OPENBLAS=..`. A ceiling
  the process never states is a claim, and this repo's rule is that an unmeasured limit is not a limit.
- **The environment carries it too**, set from the parsed `--threads` **before** the first numpy/torch
  import (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `NUMEXPR_NUM_THREADS`).
- **Two engines in one process halve, never sum**: while the score runs beside the separator, torch
  gets `max(1, budget-1)` and the ASR gets `max(1, budget-1)` -- or the score moves to a child process
  after the separator is freed.
- **A heavy script launches with `--single`**: `python -m watcher run --cpu 10 --single --io very-low
  -- <cmd>` refuses a duplicate (exit 75), and the `--cpu` number is the same process total the script prints.

## Owner rule — ship work without paperwork drag (2026-10-31T02:59:01-03:00)
Keep useful behavior and its minimum proof/docs moving in the same fast delivery. Skip optional process artifacts when they cost more than the change. Before agent fan-out or disk-heavy builds/tests, use `fast-land-shared-artifacts`: measure total disk growth, share the sanctioned target/cache across lanes, and serialize instead of duplicating heavy artifacts when sharing is unsafe. This owner direction supersedes older process checklists that add optional work without protecting a concrete risk; keep only minimum proof for correctness, security, data integrity, or destructive work.

## Bend 2 — MANDATORY reference bundle, read before any load-bearing claim (owner, 2026-10-29)
`docs/bend/README.md` is the entry point (ported from consultgpt 2026-10-29, byte-identical copies,
sha256 in that file). Read it, then `docs/bend/BEND_PROOFS_REFERENCE.md`, then
`docs/bend/BEND_LAW_GUIDE.md`. The contract in one line: claims in `LAWS.bend`, proofs in
`PROOF.bend`, gate `bend PROOF.bend --verdict` in WSL `ubuntu-bend` (never `--check-only`), every
law with a negative control that must fail, every law mirrored to the real production function.
A **latency/sync budget is never a law** -- it needs a measured falsifier; a law proves only the
ordering underneath it. Goal: YouTube subtitles on screen, synced ≈1:1 -- `drift_ms` measured, never a boolean.

## Browser: agent-browser default.
Owner browser: authorized for task-needed authentication; follow this project's access scope.

### USAR O NAVEGADOR E O YOUTUBE SEM APARECER NA TELA DELE (medido 2026-11-04)

Ordem dele, verbatim: *"tu pode usar meu youtube e meu navegador. só que dessa vez, no background. nao
me atrapalhando. quando descobrir como fazer no background, anota no agents.md"*.

`agent-browser` e' **headless por omissao**, e no Windows um Chrome headless largado pelo CLI **corre
num desktop privado** (`skills get core --full`). Nao ha janela: nao ha o que esconder, e nao ha
`--headed` em caminho nenhum desta casa. A sessao nao pode ser o `chrome` dele: nomes de sessao
separados, um por tarefa.

```bash
S=$(agent-browser session id --scope worktree --prefix yt-evidence)
agent-browser open "https://www.youtube.com/watch?v=<id>" --session "$S"
agent-browser eval "document.title" --session "$S"
agent-browser eval "(()=>{const c=document.querySelectorAll('.ytp-caption-segment');return c.length?c[c.length-1].textContent.slice(0,90):'no-captions'})()" --session "$S"
agent-browser close --session "$S"
```

Tres avisos que custaram medicao:
- **`no-captions` antes de o video tocar** nao e' ausencia de legenda: sem play nao ha cue.
- **O perfil dele NAO se copia.** Para uma pagina que exige login, a via e' `--auto-connect --pin-tab`
  sobre o Chrome que ja' esta' aberto (confirmar `title`+URL do tab exacto antes de agir), nunca uma copia.
- **Nao navegar num tab dele.** `--auto-connect` sem `--pin-tab` no tab certo mexe na sessao que ele
  esta' a usar. Se o tab necessario nao estiver la', o caminho e' a sessao headless propria.

## Herdr: cross-project coordination only, never the default
Default is to stay in the current harness (this session, this worktree). Use Herdr only when coordination genuinely spans canonical projects -- a decision or artifact another project's lane must receive. Ordinary project work must not create/focus/move/close a pane, and must not rewrite this file's routing/instructions; a routing edit needs an explicit owner request or a real cross-project need. When Herdr is genuinely needed: cap one visible pane per canonical project across workspaces/worktrees; create via `python I:/!manager/tools/herdr-visible-pane-budget.py workspace --cwd <root> --label <id>` only; unknown/already-present projects refuse; reuse the main pane; extra workers headless; no raw create/focus/move/close.

## A TODO LIST VIVE, SEMPRE (ordem do dono, 2026-11-15)

Verbatim: *"keep todo list, always. manage it. and put it in agents.md to do this."*

Toda lane mantém a `todo` viva do primeiro turno ao último: `init` antes da primeira ação com 3+ passos,
`done` no instante em que o passo passa (nunca "no fim"), `append` a cada item novo que aparece no meio do
trabalho. Uma fala do dono vira ficha no MESMO turno em que é lida (a regra do `H:\pi-agent\AGENTS.md`
inteira vale aqui). Um passo que não vai ser feito por bloqueio é nomeado como tal, não apagado em
silêncio. Nenhum turno termina com trabalho acionável fora da lista.

## Mandatory task-resolver and model routing
Use `.agents/skills/task-resolver/SKILL.md` for every non-trivial software task. At invocation, classify acceptance rows as mechanical or judgment-based and immediately implement/wire any missing task-relevant deterministic gate before dependent product edits. Follow `.agents/skills/task-resolver/references/model-routing.md`; model quota never idles or blocks a lane.

### Owner amendments — worker model routing and paid time budgets (2026-10-25)

Agent/reviewer fallback (mandatory): free routes first; then DeepSeek V4.1 Flash through OpenCode Go 1–6 in order, then MiniMax M3.1 through provider `minimax` only. Group similar review tickets; after free reviewers exhaust, use one paid reviewer per distinct subject. Model quota never leaves a lane idle or blocked; reroute and keep other work moving. Full rules: `.agents/skills/task-resolver/references/model-routing.md`.

Paid DeepSeek and MiniMax lanes use task-sized ceilings, not work quotas: allow at least 300 seconds to first output and 1,800 seconds wall time by default, longer for broader tasks. The live performance lease must outlast the wall ceiling plus cancellation/cleanup margin. If a heavy-process lease cannot cover a task, split the heavy work and continue non-heavy/independent items; never idle or mark the lane blocked for model/lease exhaustion. A timeout triggers route/liveness diagnosis and retry; it does not erase work or prove provider failure.

Transcrição em tempo real de QUALQUER áudio deste PC, mostrada como legendas num overlay global **Alt+C**.
Aceitação do dono, verbatim: *"e eu quero que o alt c mostre as transcricoes em tempo real, de qualquer
audio do meu pc. e legendas."*

> **Este ficheiro foi reduzido ao essencial.** O registo histórico completo está em
> **`docs/AGENTS-archive-20261021.md`** — é lá que se procura a proveniência de um número antigo, não
> aqui. Em conflito, vale a re-medição; este ficheiro carrega as REGRAS, não a história.

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
| 1 | track do YouTube na língua original | **en, pt-BR e espanhol: a LÍNGUA ORIGINAL, sem tradução em direcção nenhuma**; **qualquer outra → a língua ESCOLHIDA, default pt-BR**, persistida em `_main/caption-settings.json` | `docs/politica-youtube.md` |
| 2 | Alt+C: o gesto é **medido**, não contado | **sem HOLD**: 1 toque = faixa de BAIXO; 2. toque dentro de `DOUBLE_TAP_S = 0,40 s` desde o show da faixa = painel da DIREITA; fora da janela = esconde. `Ctrl+Space` comuta a legenda ao vivo (só DISPLAY). Portão: `_main/altc-gesture-oracle.py` (104/104) | `docs/hotkey-gestos.md` |
| 3 | Parakeet é o segundo pass | ao vivo = nemotron só com painel aberto; fundo = Parakeet; a retoma só corre se a shell NÃO estiver a sair (`exiting`), se houver latch `_external_parked` e se `engine_park_reason() == 'captions'`. Pausa e visibilidade desligam **só o DISPLAY**, nunca o pedido de parque. **Sem piso de 45 s**: `EXTERNAL_RESUME_MIN_S` e `EXTERNAL_CAPTIONS_WORKER_RESUME_DEFERRED` não existem no código vivo. Portão: `_main/external-resume-latch-oracle.py` | `docs/worker-lifecycle.md` |
| 4 | testes lentos e pesados | cache por **conteúdo**, classe `heavy` nunca corre sem opt-in, **um passo saltado não é um portão que passou** | `docs/bateria-e-portoes.md` |
| 4-ter | o custo do Sotto | 10 processos, pico 1801 MB, worker 104 % de CPU com dois loads; parte do stutter **não** é do Sotto | `docs/custo-medido.md` |
| 5 | o rato não passa pelo Sotto | **zero hooks globais de rato** (`WH_MOUSE_LL`/`SetWindowsHookEx` removidos a 2026-10-30). A ÚNICA excepção é `app/webview/space_swallow.py` (não `worker/`): um `WH_KEYBOARD_LL` armado só quando `gaming_mode.live_hotkey_plan` diz `take`, retirado antes do jogo receber a tecla. `RegisterHotKey` entrega `WM_HOTKEY` e **não é** um hook global de input. Mede-se pela ausência: `_main/input-path-oracle.py` | `docs/mouse-e-input.md` |

## MODO BUG-HUNT - OBRIGATORIO PARA QUALQUER DEFEITO REPORTADO (2026-10-23)

Quando o dono reporta um defeito, o trabalho **e** bug-hunt. Protocolo completo (11 passos, contados em
2026-10-25) em **`docs/bug-hunt.md`**, cada um com o portao que o recusa. O resumo que basta para nao errar:

1. nomear o cluster e o impacto; 2. observado vs esperado, palavras dele verbatim; 3. reproduzir e
guardar a evidencia em FICHEIRO; 4. **uma hipotese + o que a refutaria**; 5. minimizar; 6. corrigir a
CLASSE e varrer os irmaos com a mesma sonda; 7. regressao no estilo certo; 8. provar o detector
(negativo derruba AQUELE braco); 9. cobertura por invocador; 10. replay + verificador != autor;
11. capsula de incidente + `recurrence-watch` com instrumento e janela.

**PASSO 0 — O PROCESSO E' O DA ARVORE?** Antes de julgar qualquer comportamento que ele relata:
`python _main/live-code-freshness-oracle.py --strict`. `STALE` = a app que ele carrega e' anterior ao
codigo; a primeira accao e' **reiniciar**, nao corrigir. `UNKNOWN` nao e' `FRESH`. Nascido de um erro
medido a 2026-10-30: ele carregava uma instancia antiga enquanto oraculos verdes julgavam FICHEIROS --
ver `docs/bug-hunt.md`.

**`reported` e `fixed` nunca se apresentam como `verified`.**

**A CURA JA' ESTA' NO FICHEIRO NAO E' A CURA JA' ESTA' NO PROCESSO.** O WORKER nao precisa da mao dele:
e' um processo separado lido do disco em cada arranque; mata-se pelo ARTEFACTO (`cmdline` contem
`sotto_worker.py`, verificado ANTES do kill -- um filtro de kill nomeia o artefacto, nunca a palavra) e
a shell respawna sozinha. A prova e' `_main/shell-thread-cpu.py <pid> --seconds 8 --top 8` antes e
depois, com pid e tid. A SHELL so' entra num arranque novo (`--no-self-relaunch` esta' posto, e uma
lane NAO poe a app na tela dele): o recibo diz `fixed, NOT verified` e nomeia o que falta --
`UNMEASURED` ate' ele reiniciar. Corolario: um numero de CPU/io medido numa arvore `STALE` mede o
codigo velho, e um stutter "resolvido" sem dizer qual pid, qual fio e qual linha e' um stutter nao resolvido.

### MECANICA OBRIGATORIA PARA DEFEITO NAO-TRIVIAL (2026-10-24)

Para defeito **nao-trivial** (o sintoma nao aponta para a linha, ou a correccao pode esconder outra):
carregar a skill **`bug-hunt-sotto`** (`.opencode/skills/bug-hunt-sotto/SKILL.md`), que roteia ao
protocolo de **11 passos** (`docs/bug-hunt.md`, contados em 2026-10-25) e ao exemplo a copiar,
`_main/caption-dup-repro.py`; a mecanica de verificacao -- **sete passos** (a mesma origem): repro
no invocador real, 3 a 5 hipoteses falsificaveis
antes das sondas, uma variavel por sonda, minimizar, replay diferencial, mutacao focal, um registo
unico -- vive em `.opencode/skills/postmortem-sotto/SKILL.md` §Mecanica, com o que recusa cada um.
Proporcional: para um typo, um numero ou uma linha, nada disto.

## DEPOIS DO INCIDENTE: POSTMORTEM — 2026-10-24

**Invocar `.opencode/skills/postmortem-sotto` (camada deste repo; metodo na canonica
`I:\!manager\.agents\skills\postmortem\SKILL.md`) quando o incidente estiver contido/resolvido, ou
depois de um quase-acidente apanhado.** Com o bug **ACTIVO** nao ha postmortem: fica-se no MODO
BUG-HUNT acima. Os passos, o tracker, o fecho mecanico e as recusas estao na skill -- nao se repetem aqui.

## TRES REGRAS DO DONO, ESCRITAS COMO LEI (2026-11-04)

1. **NAO SE TRADUZ ENTRE INGLES, PT-BR E ESPANHOL.** Verbatim: *"nao e pra traduzir
   entre ingles pt br e espanhol. nesses 3, é lingua original que da display."* Um
   vídeo em qualquer um dos três sai **naquela língua**; não há tradução em direcção
   nenhuma entre eles. O código já implementa isto em `app/webview/youtube_captions.py`
   (`UNTRANSLATED_LANGS = ('en', 'pt', 'es')`) -- e a
   regra é dela, não uma preferência: um `pick` no menu dos 3 pontos que fosse traduzir
   um destes três é **clampado**, não honrado.

   **CORRECÇÃO DE 2026-11-08, e ela substitui a metade "vai para inglês".** Verbatim:
   *"eu ja falei pra NAO traduzir entre pt br ingles e espanhol entre si. mas pra
   traduzir o resto pra linguagem que eu escolhi pro sotto. que no caso é pt br. entao
   eu to vendo um anime agora, e a legenda ta aparecendo japones."* e *"faz o botao de
   config pra eu escolher pra qual lingua traduzir."* Uma língua fora dos três vai para
   a **língua escolhida** (default `pt`), e a escolha é um valor **persistido**
   (`app/webview/caption_settings.py` -> `_main/caption-settings.json`, escrito pelo
   menu dos 3 pontos), não um literal. O original é o SEGUNDO pedido, não o primeiro.
   Portão: `_main/youtube-captions-oracle.py` (66 arms, `--neg-arm` 18/18 mutantes, rc=1).
2. **O NVIDIA NEMOTRON NÃO É TEMPO REAL.** Ele é o motor de transcrição local e o
   atraso dele é medido, não hipotético: não se promete "ao vivo" a partir dele e
   não se desenha caminho que dependa de ele acompanhar o áudio. A legenda que chega
   ao ecrã em tempo real é a do **YouTube** (fonte externa) e, sem ela, a do motor
   local com o atraso que ele tiver -- dito assim, sem eufemismo.
3. **LEGENDA AO VIVO DESLIGADA NÃO É MODELO DESLIGADO.** Verbatim: *"se a legenda
   ao vivo ta desativada, nao signiifca q o modelo ta desativado. é o DISPLAY que ta
   desativado."* O `LIVE_ENABLED on=false` corta **o display**; o modelo continua
   carregado, a transcrição continua a correr e o histórico continua a ser escrito
   (o interruptor e' o `Ctrl+Space`, uma pressao; nao existe HOLD no Alt+C). Nenhum caminho pode desligar
   worker, modelo ou histórico a pretexto de "legenda ao vivo desligada".

## DUAS ORDENS DE 2026-11-08: O TECTO DE FRAME E O `>>` DO PLAYER

1. **A ANIMACAO DA LEGENDA PODE IR ATE' 240 Hz** (verbatim: *"acho que a animacao da
   legenda pode ir ate 240hz"*). O tecto vive em `app/webview/word_fade.py`
   (`FRAME_S = 1/240`, `FRAME_HZ = 240`); **o tecto nao e' a taxa**: `caption_overlay`
   limita cada pedido ao custo MEDIDO da pintura e escreve `CAPTION_FRAME_LIMIT
   want_hz=.. paint_ms=.. rate_hz=..` quando limita. **O relogio do frame e'
   `time.perf_counter`, NAO `time.monotonic`** (nesta maquina o `monotonic` avanca de
   15,000 ms em 15,000 ms). Recibo: `_main/receipt-20261108-caption-clock-and-marker.md`.
2. **O MARCADOR DE FALA DO YOUTUBE NAO SE TRANSMITE** (verbatim: *"o youtube escreve >>
   em algumas legendas. nao transmita isso pro sotto"*). O `>>` (`&gt;&gt;` antes de
   descodificar, `>>` depois, `\u203a\u203a` na faixa automatica) e' do PLAYER e morre na
   ENTRADA de cada caminho -- `youtube_window.strip_speaker_markers` e' o dono unico da
   lista, e `youtube_cdp_source.parse_snapshot` o aplica a `rows`, `items` **e** `segs`
   (carregando o irmao PELO CAMINHO: um `import` por nome resolve so' com o diretorio da
   app no `sys.path`). Portao: `youtube-cdp-source-oracle.py`, arm
   `sem-marcador-de-fala` (19/19, `--neg-arm` 15/15).

## A AUTORIDADE DO RELOGIO DO YOUTUBE E' UMA TESTEMUNHA DUPLA (medido 2026-11-06)

Tres ordens do dono na mesma sessao apontavam para o mesmo sitio: *"skippar o video ou
voltar o video, buga a legenda. sai de sync, atrasda, faz varias coisas horriveis"*, *"NAO É para o
sotto depender de ativar a legenda DO YOUTUBE para a legenda do youtube funcionar no sotto"* e
*"aconteceu só mais de varios segundos depois"*. O elo comum: o caminho do YouTube decidia PAUSA e
SEEK por testemunhas que nao existem com o CC do player desligado. Detalhe e serie medida:
`docs/factos-medidos.md`, `_main/_cache/sess-today.log`.

A lei, e ela vale para qualquer fonte que publique posicao:

- **Um seek prova-se pelo PAR (posicao exata, carimbo de parede)**, nunca pelo relogio nem pela
  pintura: recuo maior que `SEEK_BACK_S` e' seek (o player nao anda para tras), avanco maior do que
  a taxa maxima do player no intervalo tambem. Duas leituras do MESMO carimbo nao sao uma segunda
  medida (o cache CDP de ≤1,2 s declina com `same-snapshot`), e a mudanca de video zera a serie.
  O relogio sozinho **continua proibido de recuar**.
- **O chao desce junto com a ancora e com o alinhamento**, no MESMO tique: deixar o `yt_hit` velho
  faz o `_yt_clock_agrees` recusar o instante novo como `clock-stale-last-cue` e o ecra continua a
  servir a linha de +10 s -- o seek nao envenenava so' o relogio, envenenava o SERVICO.
- **A pausa so' apaga com testemunha que concorda**: `CAPTION_WINDOW_BLANKED reason=youtube-paused`
  exige posicao medida imovel por `CLOCK_STATIC_PAUSE_S` em carimbos DISTINTOS
  (`YOUTUBE_PAUSE_PROVEN witness=flag+clock-static`); a bandeira sozinha congela a interpolacao e
  diz o nome (`YOUTUBE_PAUSE_UNWITNESSED`), e o primeiro tique em que o relogio anda repinta.
- **Um snapshot em cache nao e' uma medicao**, e tambem nao e' ausencia: ele devolve o ULTIMO
  veredicto medido.

Portao: `_main/youtube-monotonic-oracle.py` (30 arms), mais `stutter-caption`, `yt-clock-static` e
`live-route`.

## A LEI DA STACK (decidida pelo dono)
**nemotron streaming = motor LOCAL, só com o painel aberto. Parakeet Redux = motor GERAL/de fundo**
(batch sobre o áudio acumulado, leve em RAM). *"o nvidia é pro ao vivo, o parakeet redux é pro geral."*
E a correcção do dono de 2026-11-04 vale por cima dela: **o nemotron NÃO é tempo real** (regra 2
acima) -- "pro ao vivo" quer dizer *o motor que corre enquanto o painel está aberto*, não *o motor que
acompanha o áudio*.

Escolha do motor de fundo pelo **preço em RAM**, não pelo nome: o ONNX int4 do Redux mede **615 MB** de
pico contra **3,90 GB** do ternário, com transcrição byte-idêntica.

- **`parakeet-ultra` FICA FORA -- por DISCO (re-medido no runtime do fabricante, 2026-11-08).** No MESMO
  runtime Photon/kestrel com CUDA há paridade de tempo e de VRAM; o que fica de pé é **só o disco:
  1 256 514 499 B contra 179 015 759 B = 7,02×**, mais o primeiro passe. Recibo:
  `_main/receipt-20261108-parakeet-ultra-photon.md`; re-medir com `_main/_cache/ultra-photon-measure.py`.
- **`ARK-ASR-0.6B` FOI MEDIDO E RECUSADO (2026-10-30).** Não tem `pt` e **traduz** em vez de transcrever;
  não faz ao vivo. Não integrar de novo sem um checkpoint com português e sem tradução --
  `_main/receipt-20261030-ark-asr-vs-parakeet.md`, `_main/engine-compare.py` para re-medir.

## A JANELA DO DIARIZADOR TEM UM PENHASCO, E ELE FOI PAGO NA MAQUINA DO DONO (2026-11-26)

O dono reportou stutter outra vez e o watcher nomeou o maior consumidor: **`python.exe(73436)` =
`worker/speaker_sidecar.py`, 8,6 % de um núcleo no tique do episódio** — filho da shell DELE (2026-11-26)
(`pythonw.exe(53752)`), ou seja código de produto, não instrumento de lane. Re-medido por mim:
**40,9 % de um núcleo** com o processo vivo. (2026-11-26)

- **A medição que faltava**: `S.tick()` sobre 11,9 s de áudio real da call, com o mesmo diarizador
  (`provider=cpu`, 2 fios). MEDIDO: **janela 10 s = 0,38 s de CPU por tique (RTF 0,037)**;
  **janela 20 s = 15,36 s de CPU por tique (RTF 0,768)** — 40x, e o dobro do tempo real.
- **A lei**: um default `--window-s` acima de `SAFE_WINDOW_S` (10 s) paga o penhasco e gira o
  processo em permanência. `DEFAULT_WINDOW_S` passou a **10.0** e `DEFAULT_EVERY_S` a **5.0**
  (sobreposição de 50 %, que é a que dá contexto ao diarizador): custo esperado **7,6 % de um (2026-11-26)
  núcleo** em vez de 154 % teóricos / 40,9 % medidos. (2026-11-26)
- **Nada disto é throttle**: é a MESMA janela a um RTF 40x menor, porque o modelo cai do penhasco
  acima de 10 s (o próprio `main` já avisava, com a tabela 0,042@10 s / 0,668@11 s / 1,69@14 s).
- **`fixed, NOT verified`** até ele reiniciar: a instância dele carrega o código anterior.
  O número do processo em execução mede-se com `python _main/shell-thread-cpu.py <pid>` e o
  veredicto da atribuição com `stall-attr`.
- **Portão**: `_main/speaker-sidecar-oracle.py` (142/142 arms, 21/21 mutantes) — e dois arms dele
  eram VERMELHOS por isolamento, não por produto: o braço da ordem dos guardas lia o registo VIVO
  do `capture_share` e, com o worker do dono a publicar, nunca construía o tap (`calls=['load']`).
  Agora ele substitui `capture_share` por um stub com `connect_client -> None`. Um braço que
  depende do estado ambiente da máquina mede o ambiente, não o contrato.

## POR VOZ E' O DEFAULT: O SIDECAR NOMEIA, O WORKER CARIMBA (2026-11-24)

Ordem do dono, verbatim: *"sotto é pra conseguir distinguir cada voz/camada de audio e saber
transcrever corretamente cada uma em paralelo. faz isso de algum jeito usando o que o discord
proporciona ou entao com modelo que separa vozes."* e, quando recebeu um pedido de token de bot,
*"tu nao precisa de nada disso ai. faz direito"*.

- **A VIA E' A QUE JA' ESTAVA NA CASA, E ESTAVA MORTA.** `worker/speaker_sidecar.py` (diarizador)
  escreve `_main/diar-live.json`; `worker/speaker_bridge.py` (dentro do worker) le' e carimba
  `source=voice:speaker-N` por linha; o painel ja' pinta uma linha e um tom por voz. Nada disso
  precisava de bot, de convite ou de token.
- **`--speakers` PASSOU A SER O DEFAULT** (`--no-speakers` desliga). O dono abre a app por
  duplo-clique; uma capacidade que exige uma flag que ele nunca escreve nao existe. O sidecar arranca
  com o WORKER (nunca antes de ele arrancar) e morre com a shell.
- **O DIARIZADOR CORRE EM CPU, PEDIDA POR NOME (`DIARIZER_PROVIDER`).** O guard GPU-only recusava
  TODA a startup (`installed sherpa-onnx has no strict diarization adapter`) porque o sherpa 1.13.4
  nao expoe atestacao para `OfflineSpeakerDiarization` -- a feature estava morta, nao lenta. Um pedido
  `cuda` continua recusado; um pedido `cpu` nao tem acelerador de onde cair e e' o caminho MEDIDO:
  **DER 0,03 %** (`_main/_diar-run.py`) e **RTF 0,416 / 277 MB / 0,9 s de load a 2 fios**. O silencio
  nao paga inferencia: `tick` mede `speech_fraction` e, abaixo de 30 %, **RECORTA a janela para o
  trecho com fala** (`speech_span` + `SPARSE_PAD_S=0,5 s`, piso `MIN_TRIMMED_S=1,2 s`) e soma o
  deslocamento de volta em `to_absolute`; so' sem fala nenhuma (ou com menos que o piso) declina, e
  declina SEM chamar o modelo. A barra nao desce -- o que muda e' o que o modelo ve'.
  **MEDIDO 2026-11-24**: no JOIN ao vivo a fala do dono ocupava 2-8 % de 20 s, a janela inteira era
  recusada em quase todos os tiques e 7 legendas reais saiam sem voz.
- **A IDENTIDADE DE SLOT EM FALA ESPARSA NAO ESTA RESOLVIDA, e agora esta' MEDIDA a razao.**
  `StableSpeakerSlots` casa por TEMPO FALADO PARTILHADO; quando duas janelas nao partilham fala
  nenhuma (12 s de silencio entre falas do dono), a mesma pessoa ganha outro slot -- medido: **UMA
  voz -> 3 slots** num fixture esparso de 88 s. A via "obvia" (embedding por segmento +
  limiar de cosseno) foi **CONSTRUIDA E REFUTADA** no mesmo dia:
  `_main/_slot-cosine-distribution.py` em 120 s da call multi-voz do dono mede
  **mesma voz min +0,655** contra **vozes diferentes max +0,743** -- o intervalo de limiar e'
  **VAZIO**, logo nao existe cosseno que separe estas populacoes com este modelo neste audio. O custo
  fica declarado: durante fala esparsa o painel pode pintar **uma cor a mais** para a mesma pessoa;
  um nome errado nao e' aceitavel, e por isso nao ha limiar no codigo.
- **Um payload `"fake": true` e' RECUSADO pelo nome**, nao pela idade: o oraculo escreve fixtures
  frescas, e uma fixture fresca a nomear vozes reais e' o cracha a mentir que o `speaker_bridge`
  existe para impedir.
- **As provas, e elas correm:** `_main/speaker-sidecar-oracle.py` (98/98, 10/10 mutantes; inclui o
  recorte esparso, o deslocamento absoluto, o declinio sem inferencia e sete arms do
  `_open_endpoint`),
  `_main/sidecar-wiring-oracle.py` (26/26, mutante do BELOW_NORMAL apanhado; inclui `--speakers`
  default ON lido do AST),
  `_main/_sidecar-replay-real.py` em 60 s da call Discord REAL de 2026-11-16 (2 slots, 6 janelas,
  0 vazias, 97,8 s de CPU), e `_main/speakers-live-join.py` -- o JOIN que nunca tinha corrido: arranca
  sidecar + worker com `CREATE_NO_WINDOW`, vida limitada, e exige payload real/fresco e linhas
  carimbadas; silencio responde `CANNOT-MEASURE reason=silence`, nunca verde. **O veredicto le a
  SAIDA DO PRODUTO (o JSONL do worker), nunca a reconstroi**: um replay com epoch sintetico
  (`tap_ms - start`) disse "0 de 49" num log onde o worker tinha carimbado **84** linhas -- o
  `tap_ms` acontece DEPOIS de a linha fechar (0,15-1,4 s), e esse deslocamento tira a linha do
  segmento (medido 2026-11-25).
- **AS DUAS METADES TEM DE ABRIR O MESMO ENDPOINT, E O WORKER E' QUEM DECIDE QUAL (medido
  2026-11-25).** O segundo join vivo publicou payload sao a cada 10 s, o worker imprimiu **91
  legendas reais**, e `attributed_captions` foi **0** -- sem erro nenhum dos dois lados. O sidecar
  dizia `capturing 'WASAPI loopback: VoiceMeeter Input (VB-Audio VoiceMeeter VAIO)'` e o worker
  escrevia `device:WASAPI loopback: Fones de ouvido (soundcore Space Q45)`. Causa: o Windows tem UM
  default por function (`E_CONSOLE` vs `E_MULTIMEDIA`) e as duas metades perguntavam coisas
  diferentes -- o worker segue o **pico do `IAudioMeterInformation` ao vivo** (`live_endpoint_order()`,
  rung A do `sotto_worker.py`), o sidecar seguia o `is_default`/`GetDefaultAudioEndpoint` estatico.
  Lei: `_open_endpoint` pergunta o que o worker pergunta -- nome pedido -> **endpoint que esta' a
  RENDERIZAR AGORA** -> default do SO -> ranking -- e abre um endpoint vivo mesmo que ele falte da
  lista de specs. Nenhum instrumento do picker le o dispositivo REAL: os arms injetam
  `wasapi_loopback` (um arm que le o dispositivo desta maquina "passa" sem testar nada, medido).
- **O MICROFONE ENTRA NO MESMO STREAM QUE O LOOPBACK (ordem do dono, 2026-11-25, verbatim: *"its
  capture my mic and transcript it aswell, in real time. and its any mic not just mine cause this
  will be a product"*).** O loopback carrega o que o PC TOCA (o outro lado da chamada); a fala do
  dono nao esta' nele, logo sem isto o produto transcreve todos menos ele. **`mic_tap.open_stream` envolve TODOS os rungs que abrem dispositivo** — A (`WasapiLoopbackTap`), P (`ProcessLoopbackTap`) e B/C (`_PortAudioTap`); cada um imprime `MIC_CAPTURE`. O rung `file` nao abre dispositivo. `worker/mic_tap.py` abre o
  dispositivo de captura que o **proprio Windows** aponta (`query_devices(kind="input")`), filtra
  **so'** o que nao e' um microfone (cabo virtual VB-Audio/CABLE, Sound Mapper, "driver de captura de
  som primario", Stereo Mix -- que e' um loopback e poria o audio do PC na conversa duas vezes) e
  mistura 16 kHz mono por cima do bloco do loopback. Um microfone de headset Bluetooth E' oferecido
  (recusar e' decisao do dono, nao nossa), e nenhum default de dispositivo, volume ou endpoint e'
  tocado. Regras medidas: o ganho do loopback e' **constante** em todos os blocos (0,75/0,75 -- um
  ganho que so' entra quando ha' fala do micro faz o nivel saltar e o AGC bombear; medido = 0,45 com
  micro e 0,4 sem), o audio do micro que o bloco do loopback nao consumiu e' **carregado** para o
  seguinte (2400 amostras medidas), e o buffer do loopback **nunca** e' escrito pela mistura. Sem
  microfone o tap de loopback volta **intacto** (0,5 entra, 0,5 sai). Portao: `_main/
  speaker-sidecar-oracle.py`, bateria `mic_battery` (15 arms, todos com `sounddevice` e taps falsos --
  nenhum abre um dispositivo nem grava a sala de ninguem) + 4 mutantes (`mix-gain-only-on-mic-blocks`,
  `leftover-mic-audio-dropped`, `a-virtual-cable-becomes-the-microphone`,
  `explicit-microphone-name-ignored`, `the-mix-hides-the-tap-surface`,
  `a-silent-microphone-is-not-reported`) -> `arms 114/114  mutants 16/16`. Um micro que so' entrega
  zeros imprime `MIC_SILENT device=... reason=digital-silence` UMA vez (medido nesta maquina: o USB
  dele deu pico 0,00003 em MME e DirectSound e recusou abrir em WASAPI -- mutado, nivel 0 ou
  permissao de micro negada; nao se toca no audio dele para "resolver" isso). Desligar: `--no-mic` no
  sidecar, `SOTTO_MIC=0` para o worker.
- **Modelo de separacao continua REFUTADO para esta via**: MossFormer2_SS_16K sobre 60 s da mesma call
  gastou **1335,107 s (RTF 22,25)** e pos 210 palavras no stream 0 e 2 no stream 1 contra 211 no mix
  (`_main/bench/logs/moss-after.log`).
- **O bot (`discord/`) e' a divisao EXATA por participante** (um stream Opus por user, SSRC -> user id
  pelo opcode SPEAKING) e `worker/discord_streams.py` transcreve essa arvore por falante, mas exige
  token/convite: e' alternativa quando o dono a pedir, NUNCA a rota que ele tem de configurar.
- **O CACHE `.ort` DO REDUX NAO SE SERVE QUANDO A SESSAO TEM DE ATESTAR COLOCACAO (medido
  2026-11-24).** A inicializacao ORT-format do ORT 1.30 salta o callback de atribuicao de EP, logo
  uma sessao carregada de `<graph>.ort` devolve **ZERO** linhas de
  `get_provider_graph_assignment_info()`. O log do dono morreu nisto (`2026-11-24 07:55:08
  REDUX_BATCH_FAILED ... 'graph/node assignment readback is empty or unbounded'`). `_cache_identity`
  recusa o cache sempre que `_placement_attestation_required(sess_options)`; o portao e'
  `_main/redux-gpu-unavailable-oracle.py` (arm `cache-bypass`, nas duas direcoes, mais o braco do
  fake que reproduz as ZERO linhas). Nao repor o cache sem uma prova de que ele atesta.

## REGRAS DATADAS DE 2026-11-25 (o detalhe vive em docs/)

- **UMA CAPTURA, UM LEITOR.** O worker publica o bloco já misturado (loopback + micro, 16 kHz mono) para o sidecar por `worker/capture_share.py`: um cliente só (`BUSY`), fila `QUEUE_BLOCKS` com queda CONTADA em `CAPTURE_SHARE_DROP dropped=N`, publicação inerte sem leitor, e `SOTTO_CAPTURE_SHARE=0` desliga o cliente (fallback nomeado). Nenhum segundo loopback/micro em execução conjunta. Detalhe: `docs/worker-lifecycle.md`; prova: `_main/capture-share-oracle.py` (8/8 arms, controlo 8/8 mutantes).
- **PONTUAÇÃO DE MODELO EM CPU POR NOME.** `worker/punctuation_model.py` pede `PROVIDER = "cpu"` e recusa `cuda` por nome; guarda de língua `en`-only, `SOTTO_PUNCT_MODEL=0` desliga, e falta de modelo/pacote devolve a string intacta. Nunca rodar sobre `pt`. Detalhe: `docs/spec/04-ENGINES.md`; prova: `_main/punctuation-oracle.py` (5/5).
- **UM CHAMADOR PARA O DENOISE.** `use_denoise` é chave TOP-LEVEL, `false` por omissão (caminho byte-idêntico); quando `true`, o ÚNICO ponto de acção é `StreamAsr.run_chunk`, depois do gate fala/música e antes da janela mel/VAD. Detalhe: `docs/audio-ladder.md`; prova: `_main/config-truth-oracle.py` (PASS nas três afirmações).
- **UMA TABELA DE DEFAULTS `SOTTO_REDUX_*`.** `WorkerBridge._child_env` é o dono único: `setdefault('SOTTO_REDUX_WHEN_HIDDEN','1')` e `setdefault('SOTTO_REDUX_LIVE','1')`, explícito `0` ganha, `run.cmd` não mantém segunda tabela; o worker resolve `flag > env > config` em `redux_live_settings`. Detalhe: `docs/worker-lifecycle.md`; provas: `_main/config-truth-oracle.py`, `_main/app-target-oracle.py`, `_main/load-shedding-oracle.py`.
- **A FAIXA ABRE NO MONITOR DO CURSOR.** `select_display_for_point` escolhe por contenção física, depois `MONITOR_DEFAULTTONEAREST`, depois primário; o rect é clampado à WORK AREA daquele monitor (DPI por monitor, escalado uma vez). `primary_display()` não é o caminho do strip. Detalhe: `docs/shell-contract.md`; prova: `_main/multi-monitor-oracle.py` (6 braços).
- **UI 100% PT-BR (2026-11-25).** Bandeja: `Abrir painel`, `Desativar/Ativar atalho Alt+C`, `Desligar/Ligar legendas (Ctrl+Space)`, `Editar posicao da legenda`, `Sair do Sotto`; painel e faixa com rótulos PT-BR, incluindo as cadeias escritas em RUNTIME pelo `panel.js` (medido: `_main/panel-language-oracle.js` → `VERDICT: PASS`, braço negativo derruba). Detalhe: `docs/spec/08-PANELS-UX.md`; provas: `_main/tray-menu-oracle.py` (27 arms) e `_main/tray-quit-probe.py`.

## LIVE PIPELINE VERIFICATION — THE END-TO-END WORKFLOW, WITH NO OWNER IN IT (2026-11-26)

Owner order, verbatim: *"anota no teu agents.md todo o workflow end to end que tu tem que fazer pra
tu nao depender de mim nem uma unica vez"*. Every step below is a lane's own job. None of it needs
his hands, his browser, his profile or his word. What it must never do is touch his environment.

**MEASURED 2026-11-26, and the reason this section exists:** a lane asked the owner to restart the
app, play a video and run a command; he answered *"i will not do this. YOU will do this"*. The lane
then drove HIS Chrome tab on port 9222 — unpausing the video he had left paused — and he answered
*"é tu que ta despausando a merda do video que eu deixei pausado inves de tu fazer na porra do TEU
AMBIENTE?"*. Both mistakes are closed by the recipe below.

### 0. The browser is YOURS, always

- **Never his Chrome, never port 9222, never his profile, never his tab.** Port 9222 with
  `--user-data-dir=C:\ChromeDebugProfile` is HIS session; opening, playing, muting, seeking or
  closing anything there is the defect the order above names.
- Your instance, exactly this shape (hidden, silent, throwaway profile):
  `chrome.exe --headless=new --user-data-dir=I:\cc-tmp\sotto-lane-chrome --remote-debugging-port=9340
  --remote-debugging-address=127.0.0.1 --mute-audio --autoplay-policy=no-user-gesture-required
  --no-first-run --no-default-browser-check --disable-background-timer-throttling
  --disable-renderer-backgrounding --disable-backgrounding-occluded-windows --window-size=1280,720`
  launched with `CREATE_NO_WINDOW` + `STARTF_USESHOWWINDOW`/`wShowWindow=0` (no console, no window).
  `--mute-audio` is the browser-level mute: the room hears nothing without touching his device.
- **A signed-out profile cannot play YouTube — MEASURED 2026-11-26, three profiles.** A clean
  `--user-data-dir` opens the watch page, the DOM is complete, and
  `movie_player.getPlayerResponse().playabilityStatus.status` is `LOGIN_REQUIRED` with
  `streamingData.adaptiveFormats` empty: `video.readyState` stays 0, `currentTime` stays 0, and no
  caption segment ever appears. The consent cookies (`SOCS=CAI`, `CONSENT=YES+1`) do not lift it, and
  neither `--headless=new` nor an off-screen window changes it — it is YouTube's session policy, not a
  browser setting. The shell says the same thing from its side: attach succeeds
  (`YOUTUBE_CDP_ATTACH_OK pick=<vid>`) and every later snapshot is `rs=0`, so the source publishes
  `state=dead-tab`. Consequences, in order: (1) a lane's own environment covers attach, snapshot
  parsing, the pause/seek/clock rules and the read envelope, and it reports the playback half as
  `CANNOT-MEASURE reason=youtube-login-required` when no session exists; (2) a burner login inside the
  lane profile is the owner-free way to close that half; (3) the owner's own profile is never the
  answer, even though it is what makes playback work.
- **Free the port before relaunching — MEASURED 2026-11-26.** A Chrome that was just killed holds
  `9340` for a couple of seconds; the next launch exits with `ConnectionRefused` and a lane that only
  retries the *new* process waits forever. The recipe polls `/json/version` until it fails, then
  launches, then polls until it answers — and captures the child's stderr to a file so a dead browser
  names its own reason instead of a bare refusal.
- Pick the video from a public URL; `/json/new?url=` may open `about:blank`, so navigate with
  `Page.navigate` and poll `document.title` (bounded 30 s) before believing the page loaded.
- If you touched his tab by accident, restore it in the same turn — `mp.seekTo(<his timestamp>)`,
  `mp.pauseVideo()`, `mp.unMute()`, delete any `muted`/`volume` pin you installed — then say so.

### 1. Launch the shell hidden, aimed at YOUR port

```
python -c "..."            # kill ONLY your previous instance: pid read from the log's
                           # SHELL_STARTUP_STAGE line, then psutil cmdline must contain
                           # 'sotto_webview.py' BEFORE the kill (a foreign cmdline is empty)
SOTTO_LANE_LAUNCH=1 SOTTO_YT_CDP_PORT=9340 python _main/keepalive.py   # backgrounded, no deadline
```
`SOTTO_LANE_LAUNCH=1` gives the hidden launch and the job-object keepalive;
`SOTTO_YT_CDP_PORT=9340` is what stops the shell from adopting his tab (`resolve_port`,
`youtube_cdp_source.py:81-95`). Readiness is a bounded grep of `_main/webview-run.log`, 120 s, and
each stage is named when it is missing:

| stage | line that proves it |
|---|---|
| shell alive | `SHELL_STARTUP_STAGE pid=<p> stage=pre-lock` |
| tab adopted | `YOUTUBE_CDP_ATTACH_OK ... pick=<vid>` |
| frames flowing | `YOUTUBE_CDP_SOURCE state=attached` |
| captions read | `YOUTUBE_TICK_MS ... rows=N` and `YT_FRAME src=external:youtube:track` |

`CAPTION_WANTED_START on=false reason=lane(SOTTO_LANE_LAUNCH=1)` is EXPECTED and is not a defect:
lane mode never paints on his screen. Consequence, and it must be stated in every receipt — with
`_caption_wanted=false` there are no cues and no `CAPTION_PAINT_SURFACE`, so paint cadence and the
reveal clock cannot be judged live; the pause/clock/seek half can. Painting requires the strip on
his screen: that needs his word in that session, never a lane's own decision.

### 2. Drive the real player, demand the receipts

`py -3 _main/yt-live-freeze-drive.py --port 9340` (also `--plan pause-only`, `--fast`,
`--selftest`). It calls the player's own API (`mp.pauseVideo`/`playVideo`/`seekTo`) and then
requires that the shell witnessed each action in its own log. Three refusals by name: no `/watch`
tab, a player not playing at start, and a receipt that is not BORN AFTER its step — a line from
before the action proves nothing.

### 3. Judge, with the exit code that belongs to each instrument

```
py -3 _main/yt-pause-disagreement-oracle.py --log _main/webview-run.log   # 0 CLEAN | 1 CONTRADICTED | 3 CANNOT-MEASURE
py -3 _main/product-soak-oracle.py --minutes 0                            # 0 PASS | 1 FAIL | 3 CANNOT-MEASURE
py -3 _main/yt-diag-truth-oracle.py                                       # 0 GREEN | 1 RED
py -3 _main/yt-live-freeze-drive.py --port 9340                           # 0 PASS | 1 FAIL | 3 CANNOT-MEASURE
```
`--minutes 0` judges whatever session exists; a real >=5 min session uses the default bar. Zero
captions in the window is `CANNOT-MEASURE why=no-cues`, never PASS (2026-11-26).

### 4. Teardown, and leave nothing behind

Kill YOUR chrome by the pid you launched (its profile is `I:\cc-tmp\sotto-lane-chrome`, delete only
that exact path), kill the shell by the pid the log named, and let `keepalive.py` exit on its own
(it watches for the app to die). Never kill a process by a generic name filter.

### 5. What the first complete run measured (2026-11-26, video TGOe1w8m5OU)

- Pause, resume and two seeks reached the player; the shell answered `YOUTUBE_PAUSE_DISAGREED
  clock_rate=0.45`, `YOUTUBE_PAUSE_PROVEN held_s=17.4`, `YOUTUBE_SEEK_RESYNC was=761.87
  now=759.43`; `yt-pause-disagreement-oracle --log` returned `episodes=2 contradicted=0 CLEAN` rc 0.
- **The seek receipt arrived 11 s after the seek, and one caption read blocked 16437 ms** (2026-11-26)
  (`EXTERNAL_CAPTIONS_READ_MS ... phases={'painted': 15906, 'track': 16422}`); the loop fell to
  `YOUTUBE_LOOP_HZ hz=0.1..1.5` (median 0.5 against a 4 Hz intent) and the shell wrote nothing at
  all for 112 s while the box sat at 91.5 % CPU / 72 % commit. A slow read in the 4 Hz loop is the
  measured mechanism of "the subtitles worked two seconds and then froze", and the per-stage budget
  for that read is the open slice.

### 6. EVERY test class, and the recipe that runs it with no owner in it

Owner's clarification, verbatim: *"eu to falando QUALQUER tipo de teste, nao só esse"*. The rule is
the same for all of them: a test either runs inside the lane's own environment or it is a HOLE named
`CANNOT-MEASURE`, never a request to him. Nothing below needs his screen, his browser, his audio
device, his word or his clock.

| class | the command | what it proves | boundary it must never cross |
|---|---|---|---|
| caption pipeline, offline | `py -3 _main/caption-timeline.py --selftest`, `_main/yt-producer-soak-oracle.py`, `_main/yt-reveal-hold-oracle.py` | the clock, the cue handoff and the reveal hold, on fixtures in the product's own log shape | none — pure code, no window |
| overlay pixels | `py -3 _main/overlay-ink-oracle.py` | the real GDI+ bitmap from `overlay_paint._layout` off-screen: ink exists, follows the text, caches per line | never `--show`, never a visible overlay |
| history store | `py -3 _main/history-replay-oracle.py` | 200 captions through the real `history_merge` into a temp store in the store's own format; idempotent on `start=` | writes only a unique temp dir |
| pause / seek / clock | `py -3 _main/yt-pause-disagreement-oracle.py`, `_main/youtube-monotonic-oracle.py`, `_main/yt-diag-truth-oracle.py` | the pause witness, the seek resync and the `why=` label, on source arms and on a real log with `--log` | reads only |
| live YouTube pipeline | §1–§3 above, port 9340 + your own Chrome | attach, frames, pause proof, seek witness, receipts born after each action | never port 9222 |
| Gemini/panel UI surface | `python app/webview/panel_state.py --read`, `_main/panel-language-oracle.js`, `_main/tray-menu-oracle.py`, `_main/multi-monitor-oracle.py` | what the panel published, the PT-BR strings written at RUNTIME, the tray menu, the strip's monitor rect | read/state only, panel hidden |
| hotkeys and gestures | `py -3 _main/altc-gesture-oracle.py`, `_main/altc-soak-oracle.py` | single tap never opens the right panel, double tap does, 200 taps leave no growth | never synthetic input (`keybd_event`/`SendInput`) — it measures Windows, not Sotto |
| audio capture, mic, sidecar | `py -3 _main/speaker-sidecar-oracle.py`, `_main/capture-share-oracle.py`, `_main/audio-ring-journal-oracle.py` | mixer gain, leftover mic audio, BUSY refusal, the captured block shared by one reader, the ring's retention | never open or mute a real device; fakes only; `owner-audio-gate.py` refuses a write |
| ASR engines / worker | fixture audio through the worker, `_main/redux-gpu-unavailable-oracle.py`, `_main/config-truth-oracle.py` | the placement attestation, the decode contract, the config defaults table | never the owner's audio; a model load only in a caged run |
| shell cost | `py -3 _main/shell-thread-budget-oracle.py`, `_main/console-window-audit.py` | CPU per named thread under the ratchet, no console window opened anywhere | no `--show`; the ratchet is not raised to pass |
| stall attribution | `py -3 _main/stall-heartbeat-oracle.py`, `_main/stall-attr.py --selftest`, `_main/stall-attr.py --log _main/webview-run.log` | a silent window classified HOST / SHELL-ONLY / HOST-IDLE from two processes' independent clocks; no heartbeat is `CANNOT-MEASURE`, never clean | reads and one 1 Hz child of its own; never the owner's app |
| wiring / dead code | `py -3 _main/dead-unwired-oracle.py`, `_main/battery-wiring-oracle.py` | every module has a caller or is documented dead; every instrument is in the battery | reads only |
| the whole battery | `_main\_audit-verify-all.cmd` (caged, per-step deadline) | every gate, its red arm, and the exit code that IS the verdict | one heavy job at a time; `SOTTO_BATTERY_NOCAGE=1` only with a stated reason |
| the angle matrix | `python <skills>/_packs/task/project-harness/scripts/harness_run.py --project H:/sotto` | each feature × angle cell answers with a command and a red arm, or is a HOLE | a HOLE is reported, never papered over |

Two standing consequences. First, when a test genuinely needs his screen, his audio device or his
account, that is a HOLE with a named reason (`CANNOT-MEASURE`), listed in the receipt — and it is
never converted into "the owner should run this". Second, a new instrument ships with its red arm
and with its row in the battery in the SAME change; an instrument nobody runs is not an instrument.

A LIVE row carries its environment in a `pre` column, and the harness asks it before the command.
`pre` exits 0 only when the victim exists (a `/watch` tab with `readyState>0` and a player that is
playing); every other rc is printed as `CANNOT-MEASURE precondition refused (rc=3): <the command>`,
so a missing app or tab is a named refusal instead of a green on nothing or a red for the weather.
Measured 2026-11-26 in both directions: a precondition that holds gives `PASS` with its red arm
refused (neg rc=1), a precondition that fails gives `CANNOT-MEASURE` and the runner exits 2.

## UMA PAUSA QUE A MEDIDA DESMENTIU NAO APAGA O ECRA (ordem do dono, 2026-11-26)

Verbatim: *"i just opened sotto, went to youtube, subtitles from youtube worked for like 2 seconds and
then froze, when i unpaused it still did not worked"*. O log dele (pid 57008) mostra as duas
testemunhas a discordar no MESMO tick: `YOUTUBE_PAUSE_DISAGREED clock_rate=0.58` as .508 e
`YOUTUBE_PAUSE_PROVEN held_s=0.25` as .756, e o `CAPTION_WINDOW_BLANKED` a seguir.

- **Uma so' regra, um so' dono:** `youtube_clock.pause_proven(clock_static, clock_moving,
  photo_fresh)`. O movimento MEDIDO ganha sempre que as duas testemunhas discordam; `_now_paused` e a
  testemunha da borda derivam dela, e nao existe segunda copia inline (o oraculo recusa uma). A
  tabela de verdade sao 8 combinacoes, e o oraculo conduz as 8.
- **FOTO VELHA NAO PROVA PAUSA (o resto do mesmo episodio).** `_yt_clock_static` compara com a ultima
  posicao DIFERENTE, logo "parado" e' o que uma foto de 5,9 s sempre diz: `YOUTUBE_SNAPSHOT_STALE
  age_ms=5891` (02:38:08.713) e o apagar decidido as 02:38:10.436 (`held_s=0.6`) deixaram 13 s sem
  UMA pintura -- *"when i unpaused it still did not worked"*. A frescura vem do `stamp` da propria
  foto (`_yt_snap_fresh`, `DOM_FRESH_S = 1.2`), nunca de um proxy; sem foto do tick a pausa e'
  DESCONHECIDA e o desconhecido nao apaga nada (`YOUTUBE_PAUSE_STALE_PHOTO held_s=.. age_ms=..`, uma
  linha por episodio). Uma pausa DE VERDADE continua a apagar: a CDP publica a 80 ms, a foto e' fresca, (2026-11-26)
  `arm19-static-pause-still-blanks` e `arm20-cached-snapshot-is-not-a-second-measure` seguem verdes.
- **O espelho `yt_source_paused` e' o portao que recusa cada linha seguinte** (`external_caption`).
  Arma-lo com uma pausa desmentida e' o congelamento: o ecra nao volta ao despausar. Nenhum caminho
  pode arma-lo sem `pause_proven`.
- **Um diagnostico nao sobrevive a' foto que o produziu:** `_yt_diag_now` le as linhas no limite dos
  leitores (1,2 s, era 8 s) e imprime `why='painted-stale'` quando o rotulo preso e a contagem fresca
  nao podem ser do mesmo instante. Portoes: `_main/yt-pause-disagreement-oracle.py` e
  `_main/yt-diag-truth-oracle.py`, os dois na bateria com o seu `red-as-expected`.
- **A prova depois do reinicio dele e' um comando:**
  `python _main/yt-pause-disagreement-oracle.py --log _main/webview-run.log` -> `CLEAN`. A janela
  DEFAULT e' a ultima sessao (`SHELL_STARTUP_STAGE`); `--since 'YYYY-MM-DD HH:MM'` escolhe outra.
  Medido no log historico: 18 episodios contraditos antes do fix, e 1 na sessao dele.

## UM SILENCIO NO LOG TEM DOIS DONOS, E O PRODUTO TEM DE DIZER QUAL (medido 2026-11-26)

Verbatim do dono: *"i just opened sotto, went to youtube, subtitles from youtube worked for like 2
seconds and then froze, when i unpaused it still did not worked"*. Duas classes de defeito estavam
empilhadas na mesma queixa, e a segunda nao era da shell:

1. **A shell** — leitura de 16,4 s, lapide no `_yt_cdp_ensure`, laco de 4 Hz a 0,5 Hz. Corrigido em
   `02793b2` (`yt_read_budget`) e `1d2649dde2` (`yt_cdp_retry`).
2. **A maquina** — dois silencios de **112,2 s** (05:42:22.751->05:44:14.916) e **67,1 s**
   (05:44:51.524->05:45:58) a 91,5 % de CPU e 72,3 % de commit. **MEDIDO, e o veredicto e' HOST**: o (2026-11-26)
   worker tem relogio proprio e ficheiro proprio, e escreveu `WORKER_COST wall_s=112.9` e os registos
   `history/audio/gaps.jsonl:258` **111,241 s** e `:261` **100,824 s** dentro dessas MESMAS janelas.
   Dois processos, dois relogios, uma janela — nao e' o GIL da shell, e uma lane que so' olhasse para
   o log da shell teria "corrigido" o sitio errado.

**A LEI, e ela vale para qualquer investigacao de congelamento:**

- **Um silencio no log nao e' um veredicto: e' uma pergunta.** Respondem-na **duas** testemunhas de
  processos diferentes; uma testemunha so' (o log da shell, ou um fio de vigilancia dentro dela) nao
  distingue "a maquina parou de agendar" de "o GIL deste processo foi tomado".
- **A terceira testemunha vive fora da shell e morre com ela**: `app/webview/stall_heartbeat.py`,
  largado pelo passo `heartbeat` (o PRIMEIRO de `CAPTION_PIPELINE_ORDER`) com o stdin como dono —
  quando a shell morre o pipe fecha, o filho ve' EOF e sai sozinho, sem kill por nome e sem orfao.
  Escreve 1 Hz em `_main/_cache/stall-heartbeat.log`.
- **O leitor e' um comando**: `python _main/stall-attr.py --log _main/webview-run.log` responde
  `HOST` (buraco nos dois), `SHELL-ONLY` (buraco so' na shell — este e' o nosso bug) ou `HOST-IDLE`
  (a maquina parou, nada estava a ser escrito); sem ficheiro de relogio responde
  `CANNOT-MEASURE why=no-heartbeat`, **nunca** verde.
- **Portoes:** `stall-heartbeat` + `red-as-expected-stall-heartbeat` (8 arms, 7 mutantes) e
  `stall-attr` + `red-as-expected-stall-attr` (4 fixtures de veredicto, 1 mutante que cega a
  classificacao).
- **A consequencia que fica escrita:** enquanto o silencio for `HOST`, a cura do lado do produto nao
  e' "ir mais rapido" — e' **nao depender de cadencia exacta** (a foto velha nao apaga o ecra, o
  `PLAYER_HOLD_S` segura a linha, o orcamento serve a ultima leitura), que e' o que as regras de
  2026-11-26 acima ja' fazem.

## UM FILHO DE TESTE TAMBEM TEM TECTO, E O DONO NAO ESPERA ATRAS DELE (medido 2026-11-26)

O watcher mandou o stutter com nome e pid: `python.exe(56424)` =
`_main/panel-hidden-at-startup-oracle.py --mutant-only ... --deadline 90.0`, **153,5 % de um nucleo** (2026-11-26)
no episodio, com o relogio do proprio governor 2,2 s atrasado. A arvore era a minha (bateria caged
`--cpu 40`), o filho era meu, e a atribuicao estava certa.

- **Reproduzido, e e' a CLASSE:** UM mutante daquele oraculo chega a **300,2 %** de um nucleo durante (2026-11-26)
  **7,1 s** -- ele faz `load_shell` (o `sotto_webview.py` inteiro) **e** `arm_hidden`, que sobe um
  WebView2 real. Nenhum tecto: nem fios, nem prioridade.
- **A cura, e ela e' do codigo, nao do governor:** `OMP/MKL/OPENBLAS/NUMEXPR/VECLIB=1` no ambiente do
  filho e `CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS` na largada. Medido depois: pico **272,5 %**,
  prioridade **16384** (BELOW_NORMAL), rc 0, **7,3 s** -- o trabalho continua a COMPLETAR.
- **O custo residual e' NOMEADO, nao escondido:** subir um WebView2 custa ~2,7 nucleos por ~7 s, e
  isso e' intrinseco ao gate (o produto faz o mesmo quando arranca). O que a prioridade garante e' que
  o dono nunca espera atras dele; a bateria continua a ser **um trabalho pesado de cada vez**.
- **A REGRA PARA QUALQUER INSTRUMENTO NOVO:** um passo que larga um filho pesado declara (1) o numero
  de fios do filho, (2) a prioridade, (3) o prazo, (4) que corre sozinho. Um filho de teste com a
  prioridade do dono e sem tecto de fios e' o stutter que ele reporta, vestido de gate.

## O RUNTIME DE WEBVIEW2: a MAIOR instalada, e nenhum pin (ordem do dono, 2026-11-11)

Verbatim: *"WEBVIEW2 RUNTIME ORDER FROM THE OWNER (2026-11-11): use the GREATER version. This is a
measured inventory, not a preference - act on it in your tree."* Duas regras, e a segunda é a que
ninguém vê violar:

1. **NUNCA fixar** uma versão nem um caminho (`...\Application\<versão>\msedgewebview2.exe`) em
   código, config, docs ou fixture. Se um dia for preciso apontar, calcula-se a **maior pasta
   instalada**, ou não se aponta nada e o loader escolhe.
2. **Que versão estou a correr é pergunta do PROCESSO, não do registo** -- um host que arrancou antes
   da actualização mantém o binário antigo mapeado até reiniciar.

A shell do Sotto não passa pasta nenhuma: `apply_webview2_environment` mexe em três knobs e nenhum é o
runtime, o código não contém `BrowserExecutableFolder` nem a variável
`WEBVIEW2_BROWSER_EXECUTABLE_FOLDER`, e a knob do pywebview está vazia
(`webview.settings['WEBVIEW2_RUNTIME_PATH'] = None`). `UNMEASURED`: o processo do Sotto a correr
**depois** de reiniciar (uma lane não a põe na tela dele).

**PORTÃO (o invariante não fica em prosa): par `webview2-runtime` + `red-as-expected-webview2-runtime`
na bateria**, com `_main/webview2-runtime-oracle.py`: 6 arms no positivo e `--neg-arm` com **7/7**
controlos apanhados. O número da versão **não** é portado: o oráculo compara com a maior lida do disco
na hora, porque um literal ali seria o próprio pin que ele proíbe.

## PREMISSAS PROIBIDAS (retiradas pelo dono)
**O Sotto NÃO dá NOMES a vozes e ninguém volta a propôr isso.** A ordem de 2026-11-24 é *separar as camadas de áudio e transcrever CADA falante em paralelo* — a **separação → transcrição por voz é o objectivo**, e `worker/speaker_sidecar.py` + `worker/speaker_bridge.py` carimbam `voice:speaker-N` por defecto. O que está PROIBIDO é (1) atribuir NOMES de pessoas e perseguir "quem falava quando" como meta e (2) usar o DER como métrica de aceitação do produto. Cores e rótulos são **slots efémeros** da sessão, não identidades: quando o slot não é resolvível, a interface pinta **uma cor nova** em vez de inventar um nome errado. Verbatim do dono: *"quem falava quando nao é importante, cara... sendo que é só separar audio pra transcrever cada falante?"*

**A IDENTIDADE DE SLOT FOI REFUTADA, NÃO ADIADA** (medido 2026-11-24, `_main/receipt-20261124-per-voice-default.md`): `_main/_slot-cosine-distribution.py` em 120 s da call mede mesma voz **min +0,655** contra vozes diferentes **max +0,743** — intervalo de limiar VAZIO. Não há cosseno que separe as populações com este modelo; por isso não há limiar no código e uma voz esparsa pode ganhar um slot extra (1 voz → 3 slots num fixture de 88 s). O custo é uma cor a mais, nunca um nome mentiroso. Prova viva: `_main/speaker-sidecar-oracle.py`.

## HARD RULES para qualquer lane

- **A TELA DO DONO NAO E O MEU BANCO DE ENSAIO (2026-10-23; ordem verbatim, dada DUAS vezes).**
  `SOTTO_NEVER_ON_OWNER_SCREEN`. Ele disse: *"para de abrir essa merda na minha tela. tu vai
  resolver no teu ambiente ai sem encher o meu saco"*, e quando lhe mostrei que a app tem seams
  proprios, *"entao nunca mais faz isso. faz gates ou agents.md"*. Lei: **nenhuma lane lança a app
  de modo a que ela apareça no ecra dele** -- nem com `--show`, nem por um harness que a passe por
  ele. Um painel visível é dele: espera pela palavra dele **naquela** sessão. E **nenhum evento
  sintético é evidência sobre a app**: `keybd_event`/`SendInput` medem o Windows. O caminho de uma
  lane é o da app: `SOTTO_LANE_LAUNCH=1` + `_main/keepalive.py` (arranca **escondida**) e a leitura por
  `app/webview/panel_state.py --read` + `_main/webview-run.log`. Portão:
  `_main/lane-screen-gate.py` na bateria (+ braço negativo); a dívida anterior à regra está
  **congelada** em `_main/lane-screen-baseline.json` e **não pode crescer**.
- **Uma lane não deixa uma instância partida a deter `Local\SottoShell`**: uma instância velha faz as
  largadas seguintes morrerem em silêncio entre `SHELL_STARTUP_STAGE stage=pre-lock` e
  `SINGLE_INSTANCE` (pids 53136 e 63392, zero linhas, porque `pythonw` não tem stderr). O dono abre a
  app (duplo-clique) ou o autostart abre-a no logon; um filtro de kill nomeia o **ARTEFACTO** -- o
  `CommandLine` de um processo alheio vem **vazio**, logo a identidade prova-se pelo `pid=` do log +
  a hora de arranque, nunca pelo `CommandLine`. A medição completa das quatro vias de largada está em
  `docs/shell-contract.md`.
- **O TRABALHO PESADO PEDE LICENCA A FROTA (2026-10-24).** Antes de um build, de uma bateria
  completa, de indexacao, de benchmark ou de campanha de mutacao: consultar o estado do gate central
  **`I:\!manager\tools\performance-gate.py`** e obter o **lease `heavy` exclusivo** dele. Com o gate
  **RED** esses comandos **nao se largam** -- continua-se por inspeccao de codigo, edicao de docs e
  diff estatico. Os governadores locais (Watcher, bateria) sao sinal **extra** e **nunca** autorizam
  trabalho pesado concorrente por fora do gate central. `unknown` tambem nao e `green`, e um skip nao e
  aprovacao.
- **A BATERIA CORRE DENTRO DE UM TECTO DE CPU, POSTO NA LARGADA (medido 2026-11-08).** Prioridade
  `BelowNormal` **desempata, nao limita**; o tecto e' o **Job Object** do watcher.
  `_main\_audit-verify-all.cmd` re-executa a si propria dentro de `python -m watcher run --cpu 40`
  antes do primeiro passo, `SOTTO_BATTERY_NOCAGE=1` devolve o modo sem tecto, e o sumario imprime
  `caged: ON|OFF` -- nenhuma corrida afirma "verde" sem dizer sob que tecto correu. O par
  `shell-orphans` + `red-as-expected-shell-orphans` (`_main\shell-orphans.py`) NOMEIA a shell orfa
  nascida na janela e **nunca a mata**: a app do dono tambem nasce sem pai. Recibo:
  `_main/receipt-20261108-battery-cage-and-orphans.md`.
  **Armadilha:** com `EnableDelayedExpansion` ligado, o `!` de `I:\!watcher` vira referencia de
  variavel, o caminho lido e' `I:\watcher` e a corrida segue SEM tecto em silencio -- por isso o bloco
  vive **antes** do `setlocal`.
- **O CUSTO EM DISCO TAMBEM SE MEDE, EM QUALQUER VOLUME (ordem do dono via herdr, 2026-11-08).**
  Worktree, clone e store de build vivem FORA do repo, por isso "quanto este projeto ocupa" nao se
  responde com um `du` do diretorio: **`python I:\!watcher\tools\artifact-census.py --project H:/sotto
  [--budget-gib N] [--gate]`**. Atribuicao por EVIDENCIA (`git worktree list --porcelain` + todo `.git`
  ARQUIVO de qualquer volume cujo `gitdir:` aponte para o projeto + crates num store sem `.git`); nome
  parecido sai como **UNPROVEN** e nao entra no total; walk cortado diz `truncated` e `--gate` recusa
  veredito (exit 3). Rodar ANTES e DEPOIS de trabalho pesado e citar os dois numeros com o volume.
  Nenhum agente apaga volume `UNPROVEN` sem prova de dirty state.
- **Nunca deixar janela de consola visível.** Lançar python com `pythonw.exe` ou
  `creationflags 0x08000000|0x00000008`. Um censo de janelas corre a cada 60 s e loga `ALERTA-JANELA` com
  o pid. O painel também tem de ficar fora do ecrã sem Alt+C/`--show`.
- **NADA EM FOREGROUND -- NEM O AGENTE, NEM UM SCRIPT DELE (ordem do dono, 2026-11-02).** *"para de
  abrir janela de terminal em foreground. é tu? ou um .vbs?"* e *"anota no agents.md pra
  tu nunca mais fazer nada em foreground ou ter scripts q façam isso"*. **A LEI:** nenhum agente desta casa
  larga `cmd /c`, `powershell`, `.bat`, `.cmd` ou `start` sem esconder a janela -- `cmd /c` vai por
  `_main/hidden-launch.py` (`run(argv)`, que põe `CREATE_NO_WINDOW` + `SW_HIDE`), `powershell` leva
  `-WindowStyle Hidden -NonInteractive`, e `python` leva `pythonw.exe` ou o `creationflags`. Os
  `Popen` do repo que largam `cmd`/`powershell`/`run.cmd` passam todos pelo mesmo helper; os portões
  são `_main/console-window-audit.py` (censo **AST** de cada sítio que larga um processo) e
  `_main/console-window-watch.py` (o vigia vivo), com a dívida anterior à regra **congelada** num
  baseline que não pode crescer. Um `subprocess` sem `CREATE_NO_WINDOW` herda a consola do pai e
  **não** abre janela -- por isso um agente que corre de um terminal nunca vê o defeito e o dono, que
  corre a app em `pythonw`, vê-o todos os dias. Duas provas, porque uma só mente (código e ecrã).

### O PORTÃO DAS JANELAS: DUAS PROVAS, CÓDIGO E ECRÃ (2026-11-04)

- **CÓDIGO -- `_main/console-window-audit.py`.** Censo AST que resolve o
  `creationflags`/`startupinfo` **no escopo**. O `--neg-arm` larga um `os.system` num ficheiro
  temporário e **tem** de dar rc=1.
- **ECRÃ -- `_main/console-window-watch.py`.** Larga o alvo com `CREATE_NO_WINDOW` e observa
  `EnumWindows` a **40 ms** mais `SetWinEventHook`, porque no Windows 11 a consola pode ser
  `ConsoleWindowClass`, `CASCADIA_HOSTING_WINDOW_CLASS` ou `PseudoConsoleWindow`; um censo de uma só
  classe mente. A medição no ecrã faz-se **UMA vez**, com o resultado colado no recibo/commentário,
  e não se repete: um instrumento cujo positivo só sabe falar por uma janela real tem uma
  fotografia, não um controlo.
- **NENHUM SCRIPT ABRE NADA NA TELA DELE -- NEM POP-UP, NEM DIÁLOGO, NEM NAVEGADOR (ordem do dono,
  2026-11-04, verbatim: *"nao faz nenhum script existente ou novo abrir coisa na minha tela tipo pop
  up"*).** Fica proibido, em todo o código deste repo (produto, instrumento, oráculo, braço negativo,
  harness) e para toda a frota: `webbrowser.open*`, `os.startfile`, `tkinter`/`Tk()`/`Toplevel()`,
  `MessageBoxW/A`, `ShellExecute*`, `pywebview.create_confirmation_dialog`/`create_file_dialog`,
  `subprocess` a largar `start`/`explorer`/`mshta`/`rundll32`/`control`/`ms-settings:`/um URL, e no JS
  `window.open(`/`alert(`/`confirm(`/`prompt(`/`shell.openExternal(`. O que **pode** abrir: a janela
  do **próprio Sotto** (painel, overlay, `stage`). **O que fazer em vez disso:** escrever o resultado
  num ficheiro (`out://`, `runs/`, `_main/*.log`) e dizer o caminho; um instrumento que precisa de
  resposta pergunta por ficheiro e volta a ler o ficheiro, nunca por caixa de diálogo.
  **Portão:** `_main/owner-screen-gate.py` (com o seu `red-as-expected-owner-screen`); a dívida
  anterior à regra vive congelada em `_main/owner-screen-baseline.json` e **não pode crescer**.
- **A GUARDA É O QUE O WINDOWS RESPEITA.** `windowsHide: true` (JS) ou `CREATE_NO_WINDOW` +
  `startupinfo` (`STARTF_USESHOWWINDOW`/`wShowWindow=0`, Python). `detached: true` **não** é guarda --
  deixa o filho sem consola e a próxima largada pinta outra vez. O censo julga o **nó EXACTO** da
  chamada (`ast.get_source_segment`), nunca uma janela fixa de linhas: **um portão que acusa quem está
  certo perde a autoridade**. CLI de consola desconhecida não é `INHERITS` (`gh`, `bun`, `deno`);
  a arm **C4** do `--neg-arm` cobre isso. Dívida zerada em `_main/console-weakflag-baseline.json`
  (`sites: []`); qualquer `WEAK-FLAG` novo falha o passo. Recibo:
  `_main/receipt-20261108-terminal-paint-class.md`.
- **Uma janela que aparece e desaparece em 100 ms continua a ser uma janela na tela dele**: o
  detector de campo e' o censo `ALERTA-JANELA` de 60 s, e um pop-up nao se justifica com "foi rapido".
  O `console-window-gate.py` que uma versao antiga citava **nunca existiu nesta arvore** -- um portao
  que so' existe na prosa nao e' portao.
- **Um filtro de kill nomeia o ARTEFACTO**, nunca uma palavra genérica: `sotto_worker\.py`,
  `sotto_webview\.py`, o caminho do exe webview/electron. Filtrar `sotto` já matou dois processos alheios.
- **UM PIN DO `code-health` SO' DESCREVE O QUE ESTA' NO COMMIT.** `_main/code-health-oracle.py --update`
  RECUSA (rc=2) quando alguma entrada mudaria a partir de ficheiro nao commitado; `--skip-dirty`
  deixa-as no valor antigo, `--allow-dirty` fixa e imprime cada uma para o recibo. O braco negativo
  julga as duas metades: `NEG-ARM 5 of 5`.
- **Áudio de teste é MUDO.** Qualquer teste que renderize áudio usa `_main/mute-audio.py --mute/--unmute`
  (portão: `_main/mute-audio-oracle.py`). A recusa antiga (comparar com o endpoint default e sair rc=4)
  **continua**; o mute acrescenta-se. **Mudar a default nao basta**: o `feed_cable` do `device-silence`
  renderiza para `CABLE Input (VB-Audio Virtual Cable)` e o VoiceMeeter encaminha para uma saída de
  HARDWARE que **não** é a default. Censo read-only: `python _main/mute-audio.py --status-all`.
  **Um instrumento que RENDERIZA áudio (ARM3 do `device-silence`, `feed_cable`, o oráculo do mute)
  não corre numa lane desta máquina**; só correm os que LÊEM.
- **O ÁUDIO DO DONO NÃO SE TOCA -- NUNCA (ordem verbatim, 2026-11-02: *"nunca mais roda nada que vai
  mutar meu audio ou resetar ele e fazer mutar. acabou de mutar. arruma"*).** Nenhum agente pode:
  **mutar, desmutar, zerar volume, mudar a default, reiniciar o endpoint ou "repor" o estado de áudio
  dele**. É `MUST NOT` para toda a frota, inclusive para um passo de bateria que a lane larga.
  **A MECÂNICA:** todo instrumento que ESCREVE num endpoint (`mute-audio.py` sem argumentos de leitura,
  `--mute`, `--unmute`, `executar`/`repor`/`reset` do `device-silence`, qualquer `SetMute`/`SetVolume`)
  passa a exigir `SOTTO_OWNER_AUDIO_OK=1` no ambiente, com recusa `rc=9` e a frase
  `recusa: audio do dono` quando a flag falta; o portão é `_main/owner-audio-gate.py` e o braço
  negativo larga o instrumento **sem** a flag e exige a recusa. Ler é sempre livre (`--status-all`),
  escrever é dele. Uma lane que precise de áudio mudo: pede ao dono, não muda o dele.
- **Um tap é aberto, lido e libertado pelo MESMO fio dono.** Um fio que ABRE e outro que LE' e' a classe
  do defeito, mesmo quando os blocos chegam por sorte enquanto o primeiro vive. Portão:
  `_main/process-target-oracle.py` (22 arms, `--neg-arm` 7/7).
- **`TMPDIR` = `I:\cc-tmp`.** `G:` enche e mata lanes com ENOSPC. A raiz da sonda escolhe-se por um
  write de 64 KiB medido; o perfil efemero do browser vai para o temp do sistema e e' apagado no fim.
- **Caminhos nativos `H:\`.** `./node_modules/.bin/electron` não executa (rc=127). E não lançar esse
  binário como app: o Electron está MORTO.
- **Pesos e `history/` vivem só em `H:\sotto`** (`worker/models/` e `history/` são git-ignored, estão
  ausentes de qualquer worktree). Testar/medir sempre em `H:\sotto`; "ausente do worktree" nunca é prova
  de ausência.
- **Lanes editam só os seus ficheiros** (mapa de ownership no brief de dispatch).
- **Nunca fazer grep a `AGENTS.md`/ficheiros de contexto** -- são auto-carregados.
- **UI em movimento (scroll, render provisório) não se toca sem instrumento:** `PANEL_STATE_PROBE`
  publica `live.scroll` porque `count` não prova posição.

## REGRAS PARA MANTER O ARQUIVO VERDADEIRO

As oito regras (cada uma custou trabalho refeito) estao em **`docs/regras-do-arquivo.md`**.
A primeira e a que mais se esquece: **"o grep deu ZERO" e uma afirmacao com prazo de
validade - re-correr antes de repetir, e colar os numeros de HOJE.**

## LAYOUT

A tabela de ficheiros e o que cada um e: **`docs/layout.md`**.

**PIN do `run.cmd --help` (re-measured 2026-11-25, `app\webview\run.cmd --help`):** re-measured 2026-11-25 the output is 9618 B, 147 lines, 147 CRLF / 0 bare LF, rc 0, sha256 `E59D5E040028E7432361B2634D43EBC27CCABF1F55A2C6F6C7480232EC0C473E`.
(O `--help` deixou de ensinar o ciclo de quatro passos do Alt+C, que o codigo ja' nao tem: a ordem do
dono de 2026-11-24 -- *"abrir o da direita apenas em double alt c"* -- e' o que `hotkey_gesture.next_action`
faz, e o texto do help diz isso mesmo. O portao e' `_main/altc-gesture-oracle.py`; o pin e' este numero.)
O numero vai **sem asteriscos**: o braco negativo do portao muta o numero com um padrao que exige
`the output is ` seguido dos digitos. O portao e' `_main/agents-md-pins-oracle.py`: se o `--help` mudar,
este numero muda, e o gate obriga a re-medir **aqui**.

## ANTES DE TOCAR EM `worker/`
Ler **`docs/model-specs/README.md`** -- parâmetros normativos (`blank_id: 13087`,
`max_symbols_per_step: 10`, `chunk_samples: 8960`), contrato de decode, tabela de lang-ids, VAD. **Não
inventar uma convenção de decode** -- esse erro já foi cometido uma vez.

## DESVIOS CONHECIDOS DO SPEC

Todos corrigidos; ficam como regra. Tabela completa em **`docs/modelo-e-decode.md`**.

## FACTOS MEDIDOS - ANTES DE AFIRMAR UM NUMERO, LE `docs/factos-medidos.md`

O que mais custa quando esquecido (o detalhe e a serie medida estao no doc):

- **O numero do painel no arranque TEM POPULACAO** (medido 2026-11-12; a ordem do dono proibe
  re-correr o censo). Leitor puro: `python _main/panel-startup-flash-census.py --read
  _main/fixtures/panel-startup-flash-census-20261011.log` -> `ARM-SUMMARY-READ arm=live
  launches=19/20 launches_with_mech=3/19 launches_at_startup=0/19 longest_mech_ms=663`. Os outros
  numeros sao OUTRAS populacoes: `18/20` e' o braco `nogate-nonet` (cura E rede arrancadas), e `0/20`
  e o `11 de 20` do `run.cmd` **nao tem log em disco** -- valem `UNMEASURED`, nao se re-medem. O
  `log()` do censo abria o ficheiro com `'w'` a cada linha, logo cada invocacao `apagava o log` da
  anterior (medido: um `--read` deixou 42 B de um log de 4 073 B). Corrigido: append com uma rotacao,
  e o `--read` imprime sem escrever. Portao: `_main/panel-flash-contradiction-oracle.py`.
- **A legenda que o dono VE e a NATIVA** (`caption_overlay.py`), nao o `caption.html`: corrigir CSS
  em `app/panel/` **nao chega ao ecra** nessa via.
- **A transicao carrega so a linha que o worker FECHOU** (`route=final`); `provisional-draft` e a
  legenda ao vivo e NAO entra no historico.
- **`app/panel/history-store.js` nao esta na pagina servida**; o escritor real e
  `sotto_webview.py history_append` com a sua propria tupla de rotas.
- **A maquina do dono esta degradada** (I: 0,4 % livre, 722 processos): um arranque custa 53-127 ms.
  Parte do stutter nao e do Sotto.
- **A duplicacao no historico dele, medida 2026-10-24** com `_main/caption-dup-repro.py`: o numero
  antigo "517 de 2077" **nao se reproduz** e fica retirado. Re-mede-se com um comando, nao com uma citacao.
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
Um passo que descreve a corrida corre DEPOIS dela; as linhas de estado vivem no fim fisico da bateria.

- **PIN do ficheiro (re-medido 2026-11-26):** `_main\_audit-verify-all.cmd` = **445321 B**,
  **5077 CRLF** / 0 bare LF, sha256 `D14F9057EB5A54F2F6247DC298240E3AB9EFCEE6B528C11982ABD4F6DF2C2DDA`.
  O portao e' `_main/agents-md-pins-oracle.py`; se a bateria mudar, re-medir AQUI.
  (Os quatro passos novos sao os da auditoria de 2026-11-25 -- `config-truth`, `capture-share`,
  `punctuation`, `multi-monitor`, cada um com o seu `red-as-expected`; `discord-streams` e
  `panel-language` entraram depois, tambem em par com o seu `red-as-expected`, e os dois passos
  do `history-gallery` saíram com o modulo que eles julgavam. 2026-11-25 (mais tarde): entraram
  `panel-chrome` + `panel-chrome-neg` e `base-themes` + `base-themes-neg` -- os dois instrumentos
  existiam e nenhum estava ligado a esta bateria. 2026-11-26: entraram dois pares novos do
  congelamento da legenda do YouTube -- `yt-pause-disagreement` (uma pausa que a MEDIDA desmentiu
  nao apaga o ecra) e `yt-diag-truth` (o rotulo `why='painted'` nao sobrevive a' foto que o
  produziu). 2026-11-26: entraram `audio-ring-journal` (o journal do anel de audio crescia para
  sempre) e `dead-unwired` (os dois modulos sem fio e a contagem de scripts da pagina), cada um em
  par com o seu `red-as-expected`; o censo `battery-wiring` recusou os dois como `new-unwired`
  antes de o par existir. Tambem em 2026-11-26: `yt-producer-soak` (5 minutos simulados de leitura
  com um produtor que publica no proprio relogio) e `yt-producer-soak-neg`. E, a fechar o angulo A3,
  `product-soak` + `red-as-expected-product-soak`: o soak lido dos artefactos do PROPRIO produto
  (log da shell + `history/`), exigindo que relogio, superficie pintada e historico avancem na
  mesma sessao; sessao abaixo da barra responde `CANNOT-MEASURE` (nunca verde).
  E `yt-reveal-hold` + `red-as-expected-yt-reveal-hold`: o tecto de 3 s do relogio da
  revelacao (`_PlayerCue.clock`) parava a linha em SILENCIO -- agora nomeia o episodio
  (`CAPTION_REVEAL_HELD gap_s=.. lost_s=..`) e o oraculo prova que ele nunca inventa mais
  de `PLAYER_HOLD_S` de video, com o buraco de 8,2 s medido no log dele como arm.
  E `overlay-ink` + `red-as-expected-overlay-ink`: a metade dos PIXEIS, lida do bitmap GDI+
  FORA DO ECRA (tema sem placa, logo cada pixel com alfa e' glifo): tinta para a linha dele,
  largura de tinta a seguir o texto, rasters diferentes por texto, zero tinta para legenda
  vazia, e A->B->A de volta ao raster de A -- o cache de pintura nao serve outra linha.
  E `history-replay` + `red-as-expected-history-replay`: 200 legendas pela regra real de
  fusao dao 200 linhas distintas num ficheiro na forma do store, cada linha entregue duas
  vezes nao duplica nada (a forma do defeito "517 de 2077"), crescer reescreve, repetir
  noutro `start` entra e encolher nao apaga o rabo -- o que fecha tambem a idempotencia no
  transcrito. E `yt-cdp-retry` + `red-as-expected-yt-cdp-retry`: a fonte CDP tinha um SENTINELA como
  lapide -- uma excecao transitoria de `start()` desligava o caminho barato para o resto da
  sessao -- e agora arma um cooldown nomeado (5 s a duplicar ate' 60 s,
  `YOUTUBE_CDP_SOURCE_RETRY tries=.. next_s=..`), provado por um arm que conduz duas falhas
  e uma boa largada em 300 s de ticks a 4 Hz contra o controle da lapide. E `yt-read-budget` + `red-as-expected-yt-read-budget`: o ramo UIA da leitura da
  legenda ganhou ORCAMENTO com recusa nomeada (`YOUTUBE_UIA_SLOW_BUDGET ms=.. hold_s=..`)
  -- a cadencia simulada com os numeros DELE vai de 0,067 Hz (a leitura de 15906 ms a
  bloquear o laco de 4 Hz) para 2,95 Hz. E `altc-soak` + `red-as-expected-altc-soak`: 200 toques de Alt+C a 3 s no
  modulo puro, provando que toque unico nunca abre o painel da direita e que nenhum
  contentor do modulo cresce em 200 chamadas.)

## `git rm --cached` SO' CONTA QUANDO `git ls-tree HEAD` CONCORDA (medido 2026-11-26)

**Duas vezes nesta sessao um `git rm --cached` devolveu rc=0 e o commit seguinte NAO levou a remocao**
(`.opencode/goal.json`: `93a63b0` mudou so' o `.gitignore` e o ficheiro continuou versionado; antes, os
tres registos de gate deram `commit rc=1 -- no changes added to commit`). O rc do `rm` mede o indice,
o rc do `commit` mede que ALGO entrou -- nenhum dos dois mede o que ficou em `HEAD`. A regra:

- Depois de destrackear, a prova e' **lida da arvore publicada**, nao do rc: `git ls-tree HEAD <dir>`
  **sem** o caminho, `git ls-files --error-unmatch <path>` a falhar, e `git show --stat --oneline HEAD`
  a mostrar a DELECAO (`| N ------`). Um caminho cujo `git check-ignore` imprime uma regra e' estado,
  nao fonte (`.opencode/.closure-gate*.json`, `.opencode/goal*.json`, `.steady-watcher.json`).
- Commit por caminho (`git commit -m ... -- <path>`) ja' engoliu uma remocao encenada; commit de
  indice (sem `-- <path>`, so' com o que esta' encenado) levou-a. Preferir o segundo e verificar a
  arvore depois.
- Um commit de indice puro nao corre a bateria: `SOTTO_SKIP_RUN_ALL=1`, e a mensagem diz que o fez.

## O EOL DO REPO E' UMA REGRA (medido 2026-11-15)

**Um comando que se chama `--verify` ou verifica, ou nao existe.** `_main/_make-gitattributes.py
--verify` delegava em `_main/_gitattributes-verify.py` e devolve o rc dele; a saida viaja por **PIPE**
e e' reimpressa (herdar o stdout do filho apagava a prova com um rc certo). O juiz `julgar()` e' uma
funcao PURA e `--selftest` alimenta essa funcao REAL com fotografias, incluindo o MISTO servido fora
do terminador dominante: `SELFTEST: PASS -- 12/12` (com o juiz mutado, rc=1). Passos na bateria:
`gitattributes-verify` (portao real), `gitattributes-verify-arm` e o selftest.

**A metade que Importa: o blob de um ficheiro `text` guarda LF, sempre.** `eol=crlf` e' do CHECKOUT,
nunca do indice. Quem responde isso e' **`git ls-files --eol`** (`i/lf w/crlf attr/text eol=crlf`):
o portao le essa fonte (`parse_ls_eol` + `julgar_blob`, as duas puras) e falha com
`VERDICT: FAIL -- o INDICE guarda bytes que o .gitattributes proibe`, nomeando a cura
(`git add --renormalize -- <ficheiro>`). Comparar checkout com worktree nao basta: com `eol=crlf` as
duas pontas sao CRLF e um blob gravado com CRLF dava `DIVERGENTES: 0` e verde enquanto o diff ficava
sujo para sempre. O adaptador separa os campos da ESQUERDA por **espacos** e so' o caminho vem depois de
um **TAB**; um blob binario publica `i/-text` e nao conta como divergente.

## A LEI DO CUSTO - um laco dorme o ORCAMENTO, nunca o proprio trabalho (2026-11-08)

**AS DUAS REGRAS, e nenhuma delas e' opcional:**

1. **PERIODO = CUSTO / ORCAMENTO, nunca o custo.** O divisor e' um numero declarado (aqui
   `CAPTION_FRAME_BUDGET = 0.40`) e o log diz os tres (`CAPTION_FRAME_LIMIT paint_ms=.. budget=..
   rate_hz=..`). A taxa sobe quando o trabalho fica barato, e o nucleo nunca passa do orcamento.
   Vale para QUALQUER laco que derive o passo do proprio custo: tick de pintura, timer, poll,
   census. Um laco que dorme exactamente o tempo que trabalha gasta 100 % de um nucleo por construcao
   (aritmetica, 2026-11-08).
2. **UM INSTRUMENTO DE CPU SEM PASSO NA BATERIA NAO E' UM INSTRUMENTO.** `_main/shell-thread-cpu.py`
   media CPU por fio com o NOME e tinha **zero chamadores**. O passo e' o par
   `shell-thread-budget` + `red-as-expected-shell-thread-budget` (`_main/shell-thread-budget-oracle.py`,
   medido 2026-11-08:
   total <= 25 % de um nucleo, um fio <= 15 %, o fio mais quente COM NOME, ratchet de +20 % sobre
   `_main/shell-thread-budget-baseline.json`; sem shell viva ele diz `VERDICT: SKIPPED`, e um passo
   saltado nunca e' um portao que passou). Um instrumento que devolve `None` por defeito proprio e'
   indistinguivel de "nao houve nada".

**O DEVER DE TRANSPORTE desta lei:** quem mexer num laco que se auto-cronometra corre
`python _main/shell-thread-budget-oracle.py` antes e depois e cola os dois numeros com o pid. Um
stutter "resolvido" sem pid, fio e linha nao e' um stutter resolvido. Recibo de referencia:
`_main/receipt-20261108-stutter-caption-tick.md`.

## UM LIMITE DE MEDICAO LARGA UM INSTRUMENTO, NAO UM PARAGRAFO (2026-11-09)

**A LEI, em tres linhas:** (1) um limite de medicao nao fecha o assunto -- ele abre o instrumento
que nomeia o ator DA PROXIMA VEZ, no mesmo turno (`_main/cpu-tripwire.py`: limiar 250 %c, janela
5 s, captura por FIO e o registro dizendo `stack=unavailable` e por que); (2) um instrumento morto
imprime **nome e rc da morte** e o recibo diz "morto" -- os numeros de um filho que morreu nao se
citam, nem "para comparar"; (3) um probe que carrega modelo ou varre disco corre **caged desde a
primeira invocacao** (`python -m watcher run --cpu 40 --`, ver a lei do custo acima). Recibo:
`_main/receipt-20261109-thread-bench-stutter.md`.

## O ORCAMENTO E' DA ESPERA, NAO DE UMA PERGUNTA -- E UM VEREDITO DE PROCESSO STALE NAO E' VEREDITO (2026-11-10)

- **Cada pergunta gasta no maximo `CONTENT_GATE_ATTEMPT_FRACTION` (0,5) do orcamento**, para que uma
  pagina ocupada receba duas perguntas sem passar o total de espera.
- **A SOMA E' O QUE O OLHO PAGA:** julgar `content_wait_ms + wait_ms` contra o MESMO orcamento e
  publicar a cauda (`total_p50_ms`/`total_p95_ms`/`total_max_ms`), nao cada metade.
- **STALE NAO E' VEREDITO.** Com o processo `STALE`/`UNKNOWN`, o RED vira `SKIPPED` com cada falha
  reimpressa como `STALE-EVIDENCE`. A demissao e' uma funcao PURA (`demote_stale`) e o `--neg-arm`
  julga a MATRIZ inteira: `RED+STALE -> SKIPPED`, `RED+FRESH -> RED`, `RED+UNKNOWN -> SKIPPED`,
  `GREEN`/`SKIPPED` nunca mudam.
- **A RAIZ TEMPORARIA ESCOLHE-SE PELO CUSTO MEDIDO, E O PERFIL DO NAVEGADOR NAO VIVE NELA.** Um write
  de 64 KiB medido em cada candidata decide a raiz; uma raiz lenta e' recusada POR NOME, nao vira um
  timeout mudo.

## A TROCA DE DONO SE ESCREVE, E A RECONEXAO E' TRANSPORTE (medido 2026-11-11)

- **Uma transicao de dono que nao se escreve e' o defeito.** O unico sitio que baixa
  `external_captions_active` e' `ExternalCaptionWatcher._release`, e a linha
  `EXTERNAL_CAPTIONS_RELEASED` tem de viver DENTRO de `if self.last_line:`. Uma transicao muda nao se
  pode datar, julgar nem curar: escreve-se UMA vez por transicao, com o motivo e com `had_line`.
- **Reconexao e' transporte, nunca evidencia de troca de video.** `pick` nunca adota aba que nao seja
  o video declarado, e nunca prefere uma `paused-loaded` a uma a tocar.
  Recibo: `_main/receipt-20261111-live-start-latency.md`.

## A LEI DOS TESTES - todo teste, existente ou futuro (ordem do dono, 2026-11-05)

Verbatim: *"QUALQUER TESTE EXISTENTE OU QUE SERÁ IMPLEMENTADO, DEVE SER IMPLEMENTADO DESSE JEITO PRA
MENOR DESPERDÍCIO DE TEMPO E QUALIDADE MÁXIMA"*, e *"por que é completamente BURRO voce levar mais
que um minuto pra rodar COISAS JA GARANTIDAS EM VARIOS LUGARES DA BATERIA"*.

Seis propriedades, nenhuma opcional:

1. **PRAZO POR PASSO.** `_main\step-deadline.py` (selftest de 5 arms + `--neg-arm`), piso da casa
   `SOTTO_STEP_DEADLINE_S=240`, corte mata o **JOB** do passo (nunca uma caminhada de arvore) e
   devolve **rc=124**, que nunca conta como verde. Um filho cortado escreve `STEP-DEADLINE exceeded`
   no log do proprio passo.
2. **TECTO DO RUN DEFAULT EM SEGUNDOS.** 60 s a quente e' o numero da casa; o que nao cabe e' classe
   `heavy` (opt-in), e um passo saltado e' SKIPPED, **nunca** verificado. O portao e'
   `_main\battery-budget-oracle.py` (medido 2026-11-05): ratchet de +5 % sobre
   `battery-budget-baseline.json`, passo novo
   acima de 240 s e' RED, e o TARGET de 60 s e' impresso com a distancia -- ele nunca se apresenta
   como "rapido".
3. **UM INVARIANTE, UM PORTAO DONO.** O segundo passo que prova o mesmo invariante e' um `crosscheck`
   declarado com custo medido, ou e' apagado: re-provar paga-se em **toda** corrida, para sempre.
4. **FAKE ANTES DO PRODUTO.** Largar a app/dispositivo e' braco `heavy`, nao teste unitario.
5. **NASCE COM O BRACO VERMELHO.** A mutacao tem de o derrubar HOJE (o braco negativo devolve o codigo
   de "apanhado", nao 0); populacao zero = `CANNOT-MEASURE`, nunca PASS; veredicto em cache leva o
   hash do proprio instrumento; duas corridas concordam.
6. **ABORTO NAO E' VEREDICTO.** O sumario escreve-se no fim, carimbado com run id + inicio, e o leitor
   recusa um sumario mais velho que a corrida que esta' a julgar.

**UM CORTE NO PRAZO NAO E' UMA DURACAO (medido 2026-11-11).** `smooth` descarta amostra **historica**
que caia a menos de 1 s do prazo e **imprime** cada uma como `KILL-SAMPLE dropped step=..`, e as
amostras desta corrida NUNCA sao descartadas. O rebaseline julga com a **mesma** regua do portao
(`PER_STEP_FLOOR_S`, `PER_STEP_PCT`, `PER_STEP_SLACK_S`). Um artefato de corrida escreve-se com prefixo
`_` dentro de `_main\_audit-verify\`, senao o `skip-verdict-guard` o le' como log de passo.

**DEVER DE TRANSPORTE - parte do "done".** Toda mudanca que altere COMO o trabalho se faz escreve a
regra AQUI, no mesmo commit: este ficheiro e' lido por este assento e por **todo** subagente
despachado, e e' o unico lugar onde uma regra sobrevive a sessao. Forma obrigatoria: a lei datada com
o numero que protege, o mecanismo (comando + rc + o que um skip significa) e o orcamento em
segundos/contagens -- e depois re-medir qualquer pin deste ficheiro que a mudanca tenha tocado. A
fonte longa da regra vive na skill `extreme-optimization-audit` §L12-bis/§L12-ter e no `task-resolver`
("Test economy and the carry-forward duty").

## UM BRACO QUE LE UMA LISTA ENTRE DOIS PASSOS DO PRODUTOR NAO E' UM BRACO (medido 2026-11-26)

Medido nesta maquina: `nemotron-preload` deu **10/12** dentro da jaula da bateria e **12/12** sozinho
minutos depois, na MESMA arvore. Os dois bracos culpados eram `if status_events:` -- um teste de
VAZIO feito no instante entre o produtor publicar o estado e o produtor decidir o que fazer com ele
(`app/webview/sotto_webview.py:25962` publica, `:26163-26166` descarta, `:26168` entrega). O braco
nao media a supressao: media o escalonador.

A lei, e vale para qualquer oraculo que observe um fio produtor:

- **Um braco de vazio so' existe se o vazio for o produto de um BARREIRA**, nunca de uma corrida.
  Se a lista pode receber um evento depois de o braco olhar, o braco e' um sorteio -- e um sorteio
  custa uma corrida inteira da bateria (medido: 821 s + 1 080 s).
- **A forma deterministica e' uma de tres**, e o comentario no codigo diz qual e por que: (a)
  dreno limitado com tecto declarado e depois juizo sobre o que ficou; (b) juizo por **NOME**
  contra o conjunto que o produtor pode legitimamente publicar, feito **depois** da ultima linha
  dele; (c) **projecao PURA** sobre um dicionario local (aqui `caption_status_for`), que nenhum fio
  pode mudar.
- **Um braco pode ser APAGADO quando e' estritamente subsumido**, e so' entao: o check de sequencia
  final conta eventos, logo um vazamento aparece como evento a mais -- e o produto tem UM leitor
  (`_pump`), o que garante que a linha ja' foi consumida na barreira.
- **A forma nova prova que sabe ficar vermelha:** mutar a EXPECTATIVA (nao o produto) tem de dar
  `MISSING` + rc=1. Medido: `10/12` com `['capture-started']` e `11/12` com a projecao invertida,
  revertidos para `12/12 PASS`; `--neg-arm` `17/17`.

## POR MEDIR / NAO ATRIBUIdo

O que esta declarado e nao medido (e por isso nao se afirma): **`docs/por-medir.md`**.
**`verified` continua impossivel de uma lane** - sem verificador independente e sem corrida real
da app; o ledger imprime `FIXED, NOT VERIFIED`.

## COMO APROFUNDAR
`docs/AGENTS-archive-20261021.md` (a história completa, com os números verbatim) ·
`docs/shell-contract.md` · `docs/model-specs/README.md` · `docs/audit/` · `_main/receipt-*.md`
(cada correcção traz o seu recibo: instrumento, braço negativo, pin).
