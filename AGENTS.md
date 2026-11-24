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
| 2 | Alt+C: o gesto é **medido**, não contado | 1 toque = painel de BAIXO · 2 toques = painel da DIREITA · **HOLD** = legenda ao vivo on/off (desligar é só DISPLAY: modelo e histórico continuam) | `docs/hotkey-gestos.md` |
| 3 | Parakeet é o segundo pass | ao vivo = nemotron só com painel aberto; fundo = Parakeet; retoma atrás de 4 guardas + piso de 45 s | `docs/worker-lifecycle.md` |
| 4 | testes lentos e pesados | cache por **conteúdo**, classe `heavy` nunca corre sem opt-in, **um passo saltado não é um portão que passou** | `docs/bateria-e-portoes.md` |
| 4-ter | o custo do Sotto | 10 processos, pico 1801 MB, worker 104 % de CPU com dois loads; parte do stutter **não** é do Sotto | `docs/custo-medido.md` |
| 5 | o rato não passa pelo Sotto | **nenhum** hook global de input existe em caminho nenhum (o `WH_MOUSE_LL` foi removido a 2026-10-30), e mede-se **pela ausência** | `docs/mouse-e-input.md` |

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
   (é a mesma lei que o HOLD do Alt+C já carrega). Nenhum caminho pode desligar
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
**O Sotto NÃO dá nomes a vozes e ninguém volta a propôr isso.** O objectivo da cadeia de falantes é
**separar o áudio para transcrever cada falante em separado**; *"quem falava quando"* não é o objectivo e
o DER **não** é métrica de aceitação. Verbatim: *"quem falava quando nao é importante, cara... sendo que é
só separar audio pra transcrever cada falante?"*

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

**PIN do `run.cmd --help` (re-measured 2026-11-24, `app\webview\run.cmd --help`):** re-measured 2026-11-24 the output is 9150 B, 140 lines, 140 CRLF / 0 bare LF, rc 0, sha256 `6EEA9E1931FDD9CB1EA4DEB76148CE4E857AA954EEA01700197130E4D3BD7094`.
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

- **PIN do ficheiro (re-medido 2026-11-24):** `_main\_audit-verify-all.cmd` = **419611 B**,
  **4798 CRLF** / 0 bare LF, sha256 `2EEEE84E66DEBFAC3932CDF76641A348E7C14D580C9BF331A3668EC687B51983`.
  O portao e' `_main/agents-md-pins-oracle.py`; se a bateria mudar, re-medir AQUI.

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

## POR MEDIR / NAO ATRIBUIdo

O que esta declarado e nao medido (e por isso nao se afirma): **`docs/por-medir.md`**.
**`verified` continua impossivel de uma lane** - sem verificador independente e sem corrida real
da app; o ledger imprime `FIXED, NOT VERIFIED`.

## COMO APROFUNDAR
`docs/AGENTS-archive-20261021.md` (a história completa, com os números verbatim) ·
`docs/shell-contract.md` · `docs/model-specs/README.md` · `docs/audit/` · `_main/receipt-*.md`
(cada correcção traz o seu recibo: instrumento, braço negativo, pin).
