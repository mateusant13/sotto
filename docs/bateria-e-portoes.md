# A bateria: cache, classes e portoes (ORDEM 4)

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.

### 4. Os testes são lentos e pesados: caching e incremental
> *"e teus testes demoram muito e sao pesados. implementa caching e incremental test e etc."*

**FEITO (2026-10-21, medido).** O cache de conteúdo (`_main/_stepcache.py`) guarda por passo o
**conteúdo** (não o mtime) do que julga, o rc, e o sha256 do log ⇒ um passo cujo conteúdo não mudou
**não volta a correr**. O **tempo** de cada passo é medido (o `.cmd` escreve um ficheiro-marcador
antes do passo; o `elapsed_s` vive no estado e a CLI mostra-o), e o sumário da bateria diz **quais
passos foram os lentos**. O **modo rápido** (`SOTTO_BATTERY_FAST=1`, limiar `SOTTO_BATTERY_FAST_S`,
20 s por omissão) **salta** os passos que foram lentos na corrida anterior e **diz que os saltou**
— um passo saltado **não** é um portão que passou, e sai no `skipped=` do sumário. O **modo
incremental** é o próprio cache: só os passos cujo conteúdo mudou correm.

**MEDIDO 2026-10-21 18:4x (esta máquina, bateria sozinha):** corrida com cache frio
(campainha) **399,8 s**; corrida seguinte **130,2 s** (76 de 91 passos em cache) e **VERDE**
(rc=0); corrida em **modo rápido** **27,7 s** (80 de 91 em cache, 5 passos lentos saltados) e
**VERDE** (rc=0).


### 4-a. O relógio: prazo por passo e tecto da corrida (2026-11-05)

Ordem do dono, verbatim: *"por que é completamente BURRO voce levar mais que um minuto pra rodar
COISAS JA GARANTIDAS EM VARIOS LUGARES DA BATERIA"*.

**O QUE ESTAVA MEDIDO ANTES DE A REGRA NASCER** (`_cache\battery-steps.json`, 320 passos):
**5 801,2 s (96,7 min)** de tempo de passo, **86,0 % em 20 passos**, o pior **3 781,6 s**
(`panel-hidden-at-startup-oracle`), e um segundo passo preso de **21,6 min**
(`youtube-cdp-boot-oracle`). Nenhum dos dois tinha prazo, e a corrida que os apanhou **nunca
escreveu sumário** — o `_battery-summary.txt` que ficou no disco era o da corrida ANTERIOR, lido
como se fosse o veredicto de agora. Os 254 passos abaixo de 5 s somam **277,8 s (4,8 %)**: o custo
não estava nas provas baratas.

**`_main\step-deadline.py`** — o prazo por passo. `:step_run` deixou de correr `!S_CMD!` sem
relógio: corre-o sob este wrapper com `SOTTO_STEP_DEADLINE_S=240`. No corte, o **JOB** do passo é
terminado (`TerminateJobObject`), o rc é **124** (código que nenhum oráculo devolve por acidente) e
o log do passo leva `STEP-DEADLINE exceeded step=<nome> seconds=<N> killed=<n> job=yes`. O filho
escreve no stdout do wrapper — o log continua a ser a evidência (a primeira versão usava `DEVNULL`
e apagava o veredicto: medido, o filho escrevia `ran` e o log ficava vazio).
*Preço medido:* **95 ms por passo executado** (~24 s numa corrida inteira).
*Selftest:* 5 arms; o A5 exige que um processo **alheio** sobreviva ao corte — nasceu de um defeito
real, a primeira versão matava por caminhada de árvore e matou **dois `cargo.exe` de outra lane**
(um `conhost.exe` partilhado devolve processos que o instrumento nunca largou).

**`_main\battery-budget-oracle.py`** — o tecto da corrida, como **ratchet** sobre
`_main\battery-budget-baseline.json`: o total não pode crescer mais de **5 %** (medido
2026-11-05) e nenhum passo novo pode passar dos 240 s sem estar declarado como dívida. O TARGET de
**60 s** é impresso com a distância — `RATCHET-OK ... TARGET NOT MET (gap 5741.2s de 60s)` — porque
um `PASS` ao lado de 5 741 s de gap seria o verde que não mede nada. O `--neg-arm` muta a **leitura**
(infla um passo 10×) e exige o RED do mesmo `judge`. O par corre no **fim** da lista, imediatamente
antes do sumário: em qualquer outro sítio leria `_cache\battery-steps.json` a meio, isto é "a corrida
até aqui", um número menor do que o verdadeiro.

**A lei completa (as seis propriedades, e o dever de transporte para o `AGENTS.md`) vive em
`AGENTS.md` §"A LEI DOS TESTES"**; a fonte longa, com os detectores D45–D52, na skill
`extreme-optimization-audit` §L12-bis/§L12-ter.

### 4-bis. A BATERIA NÃO ABRE O MUNDO DO DONO (a garantia, 2026-10-22)

O dono reclamou, **verbatim** (sessão `ses_ea36ec6efffeE7E32m9COGhkxL`, 2026-10-21):
**01:00:18** *"e teus testes demoram muito e sao pesados. implementa caching e incremental test e
etc."* · **17:22:24** *"tu ta fazendo algo que faz meu pc travar/stutter? ou é outro processo?"* ·
**17:25:44** *"essa porra dessa bateria ai deve ta mal otimizada ou burra entao. arruma. e faz
cache/incremental test"* · **17:39:14** *"entendo por que a bateria trava e da stutter. é por que o
start do que quer que seja, da stutter no meu computador"* · e (2026-10-22) *"e tu vai garantir que
minha reclamação nunca mais aconteça"*.

**O QUE MEDIU O STUTTER (nesta máquina, 2026-10-21):** arrancar **qualquer** processo custa
**53-127 ms** de stutter (os discos estão quase sem espaço ⇒ um arranque é uma leitura de disco);
e arrancar a **app** custa muito mais — `_main/_strip-stats-log-probe.py` escreveu a medição:
**63,6 s depois, "a caixa estava saturada (VRAM 100 %, 38 `msedgewebview2.exe`)"**.

**A CORRECÇÃO AO QUE O AGENTS DIZIA (medida, 2026-10-22):** *"os passos mais lentos são os que
lançam a app"* era **exacto demais**. Lendo as **origens** dos instrumentos (`subprocess.Popen`),
só **SEIS** passos tocam o mundo do dono; dois dos "mais lentos" (`tap-open-timeout`,
`strip-surface-oracle`) **não arrancam nada** (o primeiro dorme num deadline, o segundo só lê
ficheiros). Os seis, e a leitura que os prova:

| passo | o que abre | onde está a prova |
|---|---|---|
| `strip-surface-runtime` | app + WebView2 | `_main/_strip-surface-probe.py:205` `Popen([PYW, SHELL, …])` |
| `strip-stats-log-budget` | app + WebView2 + worker | `_main/_strip-stats-log-probe.py:200` `Popen([PYW, shell, …])` |
| `strip-geometry-restore` | app + WebView2 | `_main/_strip-restore-probe.py:171` `Popen(cmd)` |
| `strip-stats-wave` | app + WebView2 | `_main/_strip-stats-probe.py:173` `Popen([PYW, SHELL, …])` |
| `control-panel-exit3-neg-arm` | app + **dispositivo de áudio** | `_main/panel-exit3-oracle.py:166` `Popen([sys.executable, SHELL])` + `--device CABLE_OUT` |
| `mute-audio` | **o dispositivo de áudio do dono** | `_main/mute-audio-oracle.py` `backend.set_volume(device_id, …)` |

E **não** são pesados: `autostart-status` arranca o shell com `--autostart-status` (imprime e sai,
sem janela); `hotkey-delivery` corre uma PowerShell **só de leitura** ("this probe must never touch
the owner's app", words dele); os oráculos do hotkey instanciam a classe do shell com
`object.__new__` e **nunca** criam janela.

**O MECANISMO (três partes):**
1. **A CLASSE PESADA.** `call :step heavy <nome> …` no `.cmd` (e `always heavy` para os que
   também são `always`). Um passo pesado **não corre** sem `SOTTO_BATTERY_HEAVY=1`. Quando não
   corre é contado em `skipped=`, **nomeado** no sumário (`heavy:`) e **nunca** em `gate=`. Um passo
   pesado **em cache** é **grátis** (não arranca nada) e **mantém o seu gate**.
2. **A PRIORIDADE DA PRÓPRIA BATERIA = `BelowNormal`.** O `cmd.exe` da bateria põe-se abaixo do
   normal (o `.ps1` é escrito como **ficheiro**, porque a forma inline de uma query CIM devolve
   stdout vazio nesta máquina — lição medida em `_main/_audit-hotkey-delivery.py`). Os **filhos
   herdam a classe** (o `CreateProcess` herda-a): o python do cache, o instrumento, e a app que os
   passos pesados arranquem. O sumário diz o que aconteceu (`priority: …`).
3. **O PORTÃO** `_main/battery-heavy-gate.py` (na bateria desde 2026-10-22, com o braço negativo
   `red-as-expected-battery-heavy-gate`): **C1** corre as **etiquetas reais da bateria** sobre um
   passo **falso** e prova, **três vezes**, que por omissão o comando **não** corre e o passo é
   **SKIPPED**, que com `SOTTO_BATTERY_HEAVY=0` **também** não corre (o opt-in é o **VALOR** `"1"`,
   não a existência da variável) e que com o opt-in **corre** e **é** gate; **C2** as duas
   declarações concordam (cada passo pesado usa um instrumento com o marcador `BATTERY-HEAVY:` e
   cada instrumento marcado pertence a um passo pesado); **C3** o **piso** — os seis nomes da tabela
   estão lá, para a classe não poder ser esvaziada em silêncio. Neg-arm: **5/5 mutantes apanhados**
   (o **M5** existe para a leitura *existência vs valor* não voltar; a **primeira** versão da bateria
   tinha exactamente esse defeito — `if not defined` — e o censo, que põe `=0`, corria os pesados).
4. **O CENSO** `_main/_battery-start-census.py` — **LANÇA, logo fica FORA da bateria** (é dito aqui,
   como a regra 6 exige). É um traço de eventos do **kernel** (`Win32_ProcessStartTrace`), não uma
   sondagem de 250 ms (que perde um python de 100 ms), e conta **só a ÁRVORE de processos da
   bateria** — a 1.ª corrida traçou a máquina inteira e deu **10 417 arranques** (servidores MCP do
   OpenCode, apps do dono: um número desses não é um facto sobre a bateria). **MEDIDO 2026-10-22
   03:1x:** corrida **default** (pesados saltados) → **bateria rc=0**, **174 arranques na árvore**,
   **0 do mundo do dono**, **717 na máquina fora da árvore** (nunca contados). Braço negativo
   **executado**: com `--neg-arm` (que arranca `pythonw.exe -c pass`, o nome que o kernel dá ao shell
   da app) o censo **viu** `pythonw.exe x1` — **NEG-ARM PASS**. Dois defeitos que o próprio censo
   apanhou antes de valer: `Start-Process` junta o `-ArgumentList` com espaços e a regra de aspas do
   `/c` do `cmd.exe` estraga um comando com várias partes aspadas (rc=1 em 0,1 s; ora com
   `ProcessStartInfo.Arguments` cru), e a subscrição do WMI **não está viva** quando
   `Register-WmiEvent` retorna (uma corrida de 0,1 s logo a seguir deu **zero** eventos) ⇒ 1,5 s de
   espera antes de arrancar o comando.

**O QUE ESTÁ DECLARADO E NÃO ESTÁ MEDIDO:** o modo pesado (`SOTTO_BATTERY_HEAVY=1`) **não foi
corrido na máquina do dono** — seria exactamente o stutter que se quer evitar; o seu custo já está
medido no repo (62 s, 42 s, 34 s, 29 s, 26 s por passo, mais os 38 processos do WebView2).

**UM VERMELHO LATENTE QUE O MODO RÁPIDO ESCONDIA (2026-10-22):** `red-as-expected-lang-id-oracle`
estava a ser **saltado** (e um passo saltado não é um portão que passou); quando correu, deu
**rc=2**: a cópia-mutante de `worker/lang_prompt.py` é escrita para fora do repo ⇒ o `REPO` que o
módulo deriva do seu `__file__` aponta para o diretório temporário ⇒ a tabela
`REPO/docs/model-specs/original/fp16/languages.json` não está lá (o export int4 **não** traz
`languages.json`) ⇒ o mutante "não chegou a correr". Corrigido em `_main/lang-id-oracle.py` (as
raízes do mutante voltam ao repo): agora **2/2 mutantes apanhados**.

**O portão do cache** é `_main/_stepcache-oracle.py` (16 braços / 6 mutantes). Dois defeitos
encontrados por ele: a CLI's `record` **não tinha** `--t0` (o `AttributeError` matava o `record`
inteiro ⇒ o cache nunca via a CLI) e o formato da CLI mudou (`elapsed=`). O `.cmd` da bateria é
ainda FRÁGIL (ver §A bateria).



- Duas: **`_main\_audit-verify-all.cmd`** (principal) e **`instruments-battery.mjs`** (segunda; o header
  diz `Launches NOTHING`).
- **PIN do ficheiro (medido 2026-10-23 21:5x):** `_main\_audit-verify-all.cmd` = **108675 B**,
  **1464 CRLF** / 0 bare LF, sha256 `9A3925DF8FC1D5EF385BEEFC20263ED10AC43525943EBC8E1F8948AA102A2E08`.
  (Era 106254 B / 1435 CRLF antes dos portões `external-resume` e `code-health` e dos seus braços
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
- **O exit code É o veredicto.** Três tipos de passo: `:record` (o portão), `:control` (só passa se o
  instrumento ficou RED na cópia partida e imprimiu o seu veredicto de controlo), `:expectred` (rc tem de
  ser exactamente 1 com o texto da violação). Instrumento em falta = FALHA. Ler **`BATTERY-VERDICT` + exit
  code**, nunca o `rc` de um passo nem a última linha, e confirmar que só há UM `steps=`.
- **CRLF é obrigatório e não chega.** O `cmd.exe` procura os labels por **offset de byte**: um ficheiro LF
  faz a lista correr DUAS VEZES, e uma edição do próprio `.cmd` a meio da corrida faz o mesmo com CRLF (uma
  corrida cujo sha256 muda a meio é SUJA: dizer e repetir). **O `write` emite LF** — nunca escrever este
  ficheiro com ele; usar `edit` (preserva CRLF) ou converter.
- Estado medido **2026-10-21 18:4x**: `steps 91, gate=65, control=9, skipped=1, expect-red=16, missing=0,
  cached=76` — **VERDE, rc=0** (o `hotkey-delivery` SKIPPED: o app do dono detém o Alt+C, e o
  instrumento di-lo alto, como deve). A corrida com cache frio foi **399,8 s**; a seguinte
  **130,2 s**; a de **modo rápido** (`SOTTO_BATTERY_FAST=1`) **27,7 s** com `steps 91, gate=60,
  control=9, skipped=6, cached=80` (5 saltos **contados como skipped**, não como gates).
  **Um passo saltado não é um gate que passou** — o `skipped=` do sumário é a prova.
  **Estado medido 2026-10-22 03:1x (corrida default, com a CLASSE PESADA ligada):** `steps 95,
  gate=64, control=9, skipped=4, expect-red=18, missing=0, cached=84` — **VERDE, rc=0**, com
  `heavy: mute-audio strip-stats-log-budget strip-surface-runtime strip-stats-wave` (os outros
  dois passos pesados estavam **em cache**, e um passo pesado em cache é grátis e mantém o gate) e
  `priority: BATTERY-PRIORITY BelowNormal pid=4236`. 84 dos 95 passos vieram do cache.
  (As âncoras gastas desta vez: `panel2-dom-probe` contava as linhas no **documento inteiro** e
  a **sonda do brand** (`panel.html:1288`) traz uma linha `caption--provisional` — re-ancorado ao
  **listo do strip**; e `stepcache-oracle` apanhou que a CLI's `record` não tinha `--t0`.)
- **Estado medido 2026-10-23 22:0x (corrida default, com os portões novos):**
  `steps 115, gate=73, control=8, skipped=6, expect-red=28, missing=0, cached=96` — **VERDE,
  rc=0**, `failed: -none-`; `heavy:` = os seis da tabela do §4-bis (saltados, **não** contados como
  gates). Os seis passos novos de 2026-10-23: `input-path`, `exception-hygiene`, `seam-coverage`
  (**9/9 invocadores**), `bug-ledger` (**9/9 mutantes**), `tooling-intent` (165 ferramentas, baseline
  160) e `external-resume` (**8 braços / 8 mutantes**, ORDEM 3); mais o `code-health` (`always`, 43
  ficheiros de produto, 3/3 mutantes) que é um **ratchet**: só pode descer. O `open-close-stall` teve a
  **F4 re-ancorada** ao preload idle-gated (8 mutantes apanhados).
  O que a corrida **não** verificou está escrito no próprio veredicto: os 6 pesados, e os dois irmãos
  `unproven` do `bug-ledger`.
- **Os três portões do hotkey ESTÃO na bateria desde 2026-10-21** — `hotkey-cycle`,
  `hotkey-gesture`, `hotkey-triple` (eram os que **não** estavam, e é assim que um portão apodrece em
  silêncio). Entraram com a ORDEM n.º 2 fechada. Entrou também o do **wrap nativo**
  (`caption-native-wrap`), que julga a legenda que o dono VÊ (a nativa, não o `caption.html`).
- **O portão do OPEN/CLOSE entrou em 2026-10-21** — `open-close-stall` + o braço
  `red-as-expected-open-close-stall` (5 mutantes, rc=1 por desenho). Julga **FICHEIROS** (5 factos
  estruturais, por AST ⇒ nada de launches ⇒ entra na bateria). **Os DOIS PROBES que lançam processos
  ficam FORA da bateria** (`_main/_cuda-vram-footprint-probe.py` e `_main/_exit-latency-probe.py`) e é
  dito aqui: medem a VRAM/o load e a latência da saída.
- **E `_main/_border-radius-probe.py` também fica FORA** (medido 2026-10-22): ele LANÇA um
  Chromium (headless Edge por CDP) para medir o raio e o canto de cada um dos 45 designs — a
  metade **renderizada** das bordas. A metade de **FICHEIROS** é o portão `border-radius-gate`
  (3 claims + 3 mutantes), que julga só `app/panel/panel.css`, **não lança nada** e **está na
  bateria** (`border-radius-gate` + o braço negativo `red-as-expected-border-radius-gate`).
- **E `_main/yt-1to1-live-compare.py` também fica FORA** (medido 2026-10-23): ele LANÇA um Edge
  próprio (`--user-data-dir I:\cc-tmp\edge-1to1`, `--mute-audio`, CDP 9333), liga o CC **a tocar**
  (com o player pausado o YouTube não pinta nada: 44 amostras seguidas vazias), toca o vídeo desde o
  início e lê a janela do player a cada instante — e mata só a árvore do PID que abriu. É o
  instrumento que mediu `LIVE_1TO1 iguais=46/46 ... veredicto=MATCH` contra a faixa que o player
  pinta. A metade de **FICHEIROS** é `youtube-foreign-paint` (4 braços + 3 mutantes + braço negativo
  `red-as-expected-youtube-foreign-paint`) e os braços da pontuação dentro de `youtube-captions`
  (66 arms / 17 mutantes) — esses **não lançam nada** e **estão na bateria**.
