# Briefing do dono — 2026-10-12 04:2x -03:00 (verbatim) + mapa de atribuições

A ordem de parada de 2026-10-11 está **LEVANTADA** por esta mensagem: *"faz o sotto abrir, agora ele ta
fechado."* O Sotto ESTÁ aberto (Lead, pid 8588 + worker filho). Ainda assim: **só o Lead lança a app/worker**;
subagentes NÃO lançam (a app é uma instância única e o dono está a usá-la).

## O pedido, verbatim

> faz o sotto abrir, agora ele ta fechado. e garante pra mim o seguinte: cada tema/template/design, de cada
> versao de painel, de cada .zip, é implementado. e eu nao quero que seja por cima do nosso painel atual, ou
> na mesma div do painel, etc. eu quero que tudo seja "traduzido" pro tamanho atual, e com os botoes atuais.
> o resto, tem que ser igual. e o painel de baixo, ta errado. ele nao deve mostrar legenda de jeito nenhum.
> ele deve ser menor ainda, mais estreito, do tamanho dos botoes. os botoes tem que ser mais claros. e ele tem
> um botao de linhar a legenda, que liga ela NA TELA, igual um overlay, EXATAMENTE IGUAL os .zip fazem. é
> mostrado na TELA. como se nao houvesse painel pra legenda, como ela tivesse solta. mas isso, é pq tem q ser
> igual aos paineis. o sotto nao deve carregar tudo de uma vez, apenas o essencial. o sotto tem que usar o
> nemotron 3.5 pra falas ao vivo, e o parakeet redux por cima de qualquer coisa ao vivo falada, por que ele
> tem melhor qualidade. quando a troca de legenda no historico acontecer por causa desses dois, faz uma
> animacao por LETRA TROCADA e inserida. pesquisa online se da pra separar os audios de cada speaker de uma
> call do discord por alguma tecnica, ou se precisamos de um modelo pra fazer isso pela gente, e se a gente ja
> tem esse modelo. se nao tiver, instala. e faz o menu dropdown de escolher temas do sotto, onde passar o
> mouse em qualquer um ja mostra o preview sem travamento e super otimizado. e acho que é o sotto que causa um
> stutter quando inicia no meu pc, acho. investiga apenas se ELE faz isso, se nao faz, ignora. despacha varias
> coisas pra subagents, que tu ta fazendo agora, e desse prompt

## Decomposição em 7 frentes (uma por subagente; escopos de escrita DISJUNTOS)

| # | entrega | escopo de escrita (só isto) |
|---|---|---|
| S1 | inventário dos .zip + folha de tradução por design | `docs/design-intake/**` (novo) |
| S2 | painel de baixo: sem legenda, mais estreito, botões claros + botão que solta a legenda NA TELA | `app/panel/panel.html`, `app/panel/panel.css`, `app/panel/panel.js`, `app/panel/caption-float.js` (novo) |
| S3 | nemotron ao vivo + parakeet redux por cima de tudo o que é falado ao vivo | `worker/sotto_worker.py`, `worker/redux_live.py`, `worker/config.json` |
| S4 | animação por LETRA trocada/inserida na troca de legenda do histórico | `app/panel/letter-swap.js` (novo), `app/panel/caption-formulation.js` |
| S5 | pesquisa: separar áudio por speaker de uma call do Discord (e instalar modelo se faltar) | `docs/research/speaker-separation.md`, `_main/_venv-diar/**` |
| S6 | dropdown de temas com preview no hover, optimizado | `app/panel/theme-switcher.js`, `app/panel/theme-tune.js`, `app/panel/themes/**` |
| S7 | carregamento só do essencial + diagnóstico do stutter no arranque | `app/webview/sotto_webview.py`, `app/panel/lazy-assets.js` (novo) |

Regras duras para todos: (1) não lançar a app/shell/worker — pedir ao Lead; (2) `$env:TMPDIR="I:\cc-tmp"`;
(3) nunca deixar janela de consola visível; (4) ficheiros do painel são CRLF ou LF — MEDIR antes de reescrever;
(5) nenhum gate verde sem braço de controlo que saiba dizer NÃO; (6) cada entrega termina com um recibo em
`_main/receipt-20261012-<frente>.md` com os números medidos e o que NÃO ficou medido; (7) não tocar em
ficheiros fora do escopo — se precisar de uma linha noutro ficheiro, escreva o pedido no recibo.
## CONTEXTO MEDIDO PELO LEAD (2026-10-12 04:35, a app ESTÁ ABERTA — ler antes de trabalhar)

* **A app está aberta e é INSTÂNCIA ÚNICA**: shell `pythonw.exe sotto_webview.py` pid **8588**, worker
  `python.exe` pid **22172**. Ninguém além do Lead lança, mata ou reinicia. Se precisares de um arranque para
  medir, escreve no teu recibo o comando exato e o que ele prova — o Lead executa e devolve os números.
* **O "painel de baixo" é a STRIP**, medida no log da shell:
  `PANEL_GEOMETRY_RESTORED surface=strip rect=1040x100@(440,920) writtenAt=2026-10-12T04:32:12-03:00 clamped=false`.
  O dono quer: sem texto de legenda nenhum, mais estreito, da ALTURA DOS BOTÕES, botões mais claros.
* **Ordem real do arranque** (de `_main/webview-run.log`, sessão a começar na linha 91910; o log NÃO tem
  timestamp por linha): `SINGLE_INSTANCE already_running=false` -> `HOT_RELOAD_WATCH panel` + `worker` (2
  watchers, debounce 250 ms) -> `PRELOAD_INSTALLED` -> `STAGING_SEEN` -> `STAGING_LOADED` -> `RECEIVER_READY`
  -> `BRIDGE_STATS_REPLY payload={"tag":"stats"}` -> `PRELOAD_ACTIVE hasSotto=true methods=14 hotkey=Alt+C`.
* **Footprint agora** (re-medido pelo Lead, janela de 19 s a cadência de 1 s, ps: TotalProcessorTime):
  worker **2479 MB** RSS (máx 2481), shell **114 MB**, 2 processos WebView2 filhos.
  **CORRIGIDO — o "96.78 s de CPU" que aqui estava era o meu bug de unidades:** `Get-Process.CPU`
  devolve um `TimeSpan` no pwsh 7 e o `-f` imprimiu-o como texto; a medida certa é
  `.TotalProcessorTime.TotalSeconds`: shell **0,63 s / 19 s** (3,3% de um core), worker **0,47 s / 19 s**
  (2,5%) com o áudio PARADO (`CAPTION_APPLIED` contado 1/s, **0** no janela; quando há áudio dá ~30/s).
  O AGENTS.md cita int8 RSS ~1192 MB: o medido já não bate, e isso é uma medição a fazer, não uma conclusão.
* **Sem janelas visíveis**: `mainWindowHandle=0` para os dois pids (nenhuma consola órfã na tela do dono).
* **Payload de stats vazio = `{"tag":"stats"}`** (não `{}`): não escrevas guardas que assumam `{}`.
* A shell expõe **14 métodos** ao painel. Precisar de um método novo no shell = fora do teu escopo nesta
  ronda: entrega a assinatura exata no recibo.

---

# ACTUALIZAÇÃO DO LEAD — 2026-10-12 05:30 -03:00 (ronda 1 de 7)

**Estado dos oráculos nesta hora — todos corridos pelo Lead, não aceito a palavra da frente:**

| frente | instrumento | resultado (corrido pelo Lead) |
|---|---|---|
| S1 | `node docs/design-intake/gap-oracle.mjs` | **não corre**: `SyntaxError: Illegal return statement` na **:272** (24 391 B / 490 linhas às 05:24). Às 05:06 estava truncado no EOF (:429). O resumo "142/0" não é auto-verificado |
| S6 | `node _main/theme-preview-oracle.js` | **VERDICT: FAIL** (25,8 KB): ARM8 "the deferral is counted" (got false), ARM8 "exactly one apply at the commit" (got 0, want 1), ARM9 "the warm path ran in an idle slice" (fonts=0 images=0 ms=0) |
| S4 | `node _main/letter-swap-oracle.js` | **VERDICT: FAIL** 76/78: `C8b text swapped got="x" want="bom dia!"` e `C12a second swap animates without a prevProducer got=0 want=1` |
| S7 | `node --check app/panel/lazy-assets.js` | **parse ok** (12,5 KB, 05:21) |

**O que mudou no chão destas frentes (medido pelo Lead):**

1. **MossFormer2 instalado** — `_main/diar-models/mossformer2/last_best_checkpoint.pt`, **670 353 271 B**,
   sha256 `00A3A48B...` == o `oid` do ponteiro LFS do servidor (verificado duas vezes: em trânsito e no
   lugar), licença **apache-2.0**. Pedido ao S5 cumprido. `torch 2.7.0+cu128` existe no Python do sistema
   mas **nunca o executei** e o código de inferência (ClearerVoice-Studio) não está instalado → **UNMEASURED**.
2. **`_main/diar-models/` é agora git-ignorado** (como `worker/models/` e `history/`) — pesos locais, nunca
   no repositório.
3. **Os 5 ficheiros `_main/_audio-*` que estavam apagados foram repostos em disco** (`git checkout --`);
   não os trates como ausentes, e nada foi perdido.
4. **Os 12 mutantes `_main/_redux-gate-mutants/*.py` re-baselados foram verificados pelo gate que os
   consome** (`VERDICT: PASS`, rc=0) e comitados (`79bd753`) — não são lixo, não os apagues nem os
   revertas.
5. **Dois commits já no remoto:** `1f43b3b` (recibo da ronda 1 + S5 + MossFormer2) e `79bd753`
   (mutantes). `HEAD == origin/feat/build-verify-1`.

**Ainda bloqueado (o Lead não mata a app do dono):** os braços do arranque do S7 (`--no-worker` /
`SOTTO_NO_WORKER=1` vs completo) e a bateria 77/77 — a app do dono detém `SINGLE_INSTANCE`
(`Local\SottoShell`, pid do shell **8588**, worker **22172**).

## MÓDULOS ATERRADOS QUE A PÁGINA VIVA AINDA NÃO CARREGA — 05:42 (scope do S2)

Medido agora: `app/panel/panel.html` carrega **os mesmos 11 scripts** de sempre (`caption-formulation.js`
→ `panel.js`) e **mais nenhum**. Duas frentes entregaram ficheiros que ficam ÓRFÃOS até alguém os
referenciar:

| ficheiro | frente | estado do gate | quem o liga |
|---|---|---|---|
| `app/panel/letter-swap.js` | S4 | **VERDICT: PASS** 84/84; com `--neg-arm` **94/94** e 3 mutantes RED (rc=0) | ninguém — 10 matches, todos dentro do próprio ficheiro |
| `app/panel/lazy-assets.js` | S7 | parse ok (12,5 KB) | ninguém |

S2: ligar ambos é do TEU escopo (a lista `<script src>` é tua). A nota do dono é que o carregamento
tem de ser **preguiçoso** — não ponhas estes dois no caminho crítico do primeiro paint.

## AVISO AO S3 (e a quem mexe em `worker/`) — medido 05:44 pelo Lead

`app/webview/hot_reload.py` observa **`worker/`**: cada gravação em `worker/sotto_worker.py`
reinicia o worker da app **DO DONO**. Medido no `_main/webview-run.log` de hoje:

```
L97128  HOT_RELOAD_WORKER_RESTART files=1 after_idle_ms=12889 waited_ms=12889
L97140  HOT_RELOAD_WORKER_RESTART files=["sotto_worker.py"] spawns=1 started=true
L97252  BRIDGE_EXIT pid=44780 rc=3 spawns=1 captions=0 statuses=31 malformed=0
```

e a recuperação foi automática:

```
CAPTION_APPLIED text="Até o contro pra fazer os bagulho..." count=200
STATUS_APPLIED text="Receiving captions"      worker pid=28452   shell.visible=false
```

**Consequência:** o dono perde legendas em cada reinício (o bridge saiu com `captions=0` no novo
worker e voltou sozinho). O Lead não pede que pares — o ficheiro é teu — mas agrupa as gravações
e testa em cópia quando puderes, para não deixar o dono sem transcrição. **Não há permissão para
matar o worker do dono** (regra do AGENTS.md: só o Lead relança a app).

## ENTREGUE PELO LEAD — 2026-10-12 12:1x -03:00 — arranque com o Windows (pedido do dono)

**"faz o sotto sempre iniciar com windows"** — tarefa agendada **`Sotto`** registada:
`state=Ready`, trigger `MSFT_TaskLogonTrigger`, accao `H:\sotto\app\webview\run.cmd`,
working dir `H:\sotto\app\webview`, principal `Interactive / Limited`, `Hidden=true`,
`MultipleInstancesPolicy=IgnoreNew`. Ficheiros no repo: `_main/windows-autostart/`
(`sotto-task.xml` + `install.cmd` + `README.md`).

**Porque a tarefa e nao um `Start-Process` meu — MEDIDO:** um launch feito de dentro da sessao do
Lead morre com ela. O registo da shell mostrou a app a transcrever e depois:

```
sotto: SHELL_CLOSING
sotto: BRIDGE_STOP reason=closing pid=29900
sotto: HOT_RELOAD_STOPPED reason=closing watchers=0 droppedUnsettledEvents=0
sotto: BRIDGE_EXIT pid=29900 rc=1073807364 spawns=1 captions=26 statuses=30 malformed=0
```

Pela tarefa: `shell pid=33248 ppid=14640` (Task Scheduler) + `worker pid=35872 ppid=33248`,
`namedState=capture-started`, `live.count` a subir, `error` vazio.

## DEFEITO MEDIDO PARA O S7 (dono: "inicia corretamente o modelo") — escopo do S7, NAO tocar

O primeiro worker do arranque frio morreu e so o auto-restart salvou a app:

```
sotto: STATUS_APPLIED text="model-loading"
sotto: BRIDGE_SILENT ms=30000 pid=34980
sotto: STATUS_APPLIED text="model-loaded"
sotto: PLACEHOLDER_APPLIED title="Worker silent"
sotto: BRIDGE_RESTART reason=silent in_ms=1000 restart=1
sotto: BRIDGE_EXIT pid=34980 rc=1 spawns=1 captions=0 statuses=6 malformed=0
```

Ou seja: **a janela de silencio do bridge (30 000 ms) e mais curta do que o carregamento do modelo**,
por isso o arranque frio declara "Worker silent" e reinicia o worker — e com o arranque automatico
do Windows agora registado, **isso acontece em TODOS os boots**. O segundo worker (pid 35872)
subiu com o cache quente, ouviu audio de imediato eLegendou (`BRIDGE_DEATH_LIFTED reason=caption
captions=1`), por isso a app recuperou sozinha — mas ~1 minuto de transcricao perde-se.

**O disco NAO e o gargalo — MEDIDO:** ler os pesos a seQuencia com buffer de 4 MB leu
`encoder.onnx.data` 967 176 192 B em **402 ms** e `decoder.onnx.data` 59 785 216 B em **28 ms**
(≈ 2,3 GB/s, total 1 026 961 408 B). O custo esta na criacao da sessao CUDA + copia para a VRAM,
nao no I/O.

**Pede-se ao S7:** (1) o `BRIDGE_SILENT` nao deve correr antes de `model-loaded` (ou a primeira
janela tem de cobrir o carregamento); (2) as linhas do registo da shell nao trazem timestamp —
sem isso o tempo de carregamento nao e mediavel, e o diagnostico do stutter no arranque fica cego.
Gate: o proprio S7 corre `py -3 _main/panel-exit3-oracle.py --unit --neg-arm` (ja existe) e
acrescenta um braco que prove a nova janela.

## FRENTE NOVA S8 — reutilizar o modelo que ja esta na VRAM (pedido do dono 12:0x)

Verbos do dono: *"ah, e se o mesmo modelo ja existe carregado na vram, reutiliza ele. se nao vai
usar duplicados, do mesmo modelo, q eu tenho de outros projetos."*

## LEAD CORRIGIU 2026-10-12 13:0x — os recibos da `run.cmd` nunca chegavam ao log (e mais uma tarefa para o S7)

**Defeito medido pelo Lead (nao e de nenhuma lane):** `cmd.exe` nao consegue fazer append a
`_main/webview-run.log` enquanto a app corre — erro 32, "o arquivo ja esta sendo usado por outro
processo" — e com o arranque automatico do Windows registado a app corre essencialmente SEMPRE:

```
cmd /c "echo X >> _main/webview-run.log"   -> erro 32, log +0 B
py  open("...","a").write("X\n")          -> log +17 B
```

Os dois recibos do wrapper (a RECUSA de flag, linha G5, e o HANG, linha G3) nunca aterravam.
Corrigido em cODIGO pelo Lead: novo `app/webview/run-cmd-log-append.py`, chamado com `%PYW%` nos dois
sitios da `run.cmd`. O helper fica AO LADO do wrapper porque os bracos de gap do
`run-cmd-exit-oracle.py` copiam uma arvore que leva `app/webview/*.py` e deixam `_main/` vazio —
um helper em `_main/` desaparece nessas copias (medido: o braco G3 perdeu o recibo).

Gates com a app do dono a correr: `preflight-refusal-visible-oracle` **PASS**
(arm1 rc=2, log +821 B; arm3 `--check-args` rc=0, log +0 B; arm4 CONTROL pre-fix cego, +0 B) e
`run-cmd-exit-oracle` **GAP-VERDICT PASS 4/4** + **CENSUS-VERDICT PASS**. Recibo:
`_main/receipt-20261012-owner-3-asks.md`.

### Tarefa nova para o S7 (dona do shell, nao e minha)

`run-cmd-exit-oracle.py` falha no braco **`help`**: o shell declara **32** flags e o `--help`
lista **27**. Faltam `--mutex-name` (:8554), `--probe-stats` (:8508), `--probe-stats-wait` (:8510),
`--probe-outside-click` (:8526) e `--probe-edit-mode` (:8528) — medidas hoje na revisao
460 312 B. Decisao tua: ou dao texto de `help=` a essas cinco (aparecem no `--help`), ou o gate
passa a comparar contra a lista REAL de flags escondidas — de qualquer forma o numero 32 tem de
continuar a ser o que o parser declara, nao o que o help imprime. **NAO alteres o output do
`--help` sem rever o pin do AGENTS.md:** a frase `re-measured 2026-10-12 the output is 4956 B, 79
lines, 79 CRLF / 0 bare LF, rc 0, sha256 91F73971...` e verificada por
`_main/agents-md-pins-oracle.py`; se o texto mudar, o pin muda COM a ancora intacta
(a frase `re-measured 2026-10-12 the output is` e o que o oraculo procura).