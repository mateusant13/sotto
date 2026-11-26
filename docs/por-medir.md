# Por medir / nao atribuido

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.


- Que o mute tape *todos* os caminhos até aos ouvidos: o recibo de 2026-10-07 mediu som real na sala
  (mic 0,24–0,77) por um caminho não identificado. Medir isso exige renderizar áudio.
- Se o `emit_async` (um post pendente por canal) impede um freeze a sério: nenhum lançamento foi permitido
  na altura, e a profundidade da fila nunca foi instrumentada. A causa do freeze continua **não atribuída**.
- Que o hot reload do painel (staging bounce) funcione: o mecanismo está lido e verificado por leitura, a
  prova de máquina (`panel.url = file://…/panel.html` + `live.count >= 0`) não foi corrida desde a cura.
- O que o WebView2 real pinta de `source=proc:<pid>` ponta-a-ponta; e DUAS apps ao mesmo tempo são
  impossíveis por construção (um bridge, um worker, um valor de `--app-target`).
- ~~A contradição do flash de painel no arranque (§Factos)~~ — **FECHADO 2026-11-15**: o
  `_main/panel-flash-contradiction-oracle.py` da' `VERDICT: PASS` (rc=0) — cada número de flash nomeia
  o seu braço, a sua contagem de arranques e a sua fase, o log sobrevivente cita-se sem re-correr o
  censo, e a frase congelada desapareceu. O oráculo passou a fazer parte da bateria.

- **O gesto Alt+C de 200 ms na mão do dono** (2026-10-30). A régua `HOTKEY_HOLD_MS` está provada por
  arms (199 ms = toque, 200 ms = HOLD) e por uma medição de pressões **sintéticas**; as durações reais
  dele (204 a 641 ms, recolhidas de `docs/hotkey-gestos.md`) foram medidas com o limiar antigo em vigor.
  Com 200 ms duas dessas pressões **passam a HOLD** e comutam a legenda em vez de abrir o painel. Não é
  um defeito: é a ordem dele. O que fica por medir é o que a mão dele faz agora.
- **Porque é que a criação da janela WebView2 pendurou a 2026-10-30 09:36** (`UI_HUNG_FRAME` em
  `winforms.create_window` → `thread.Join(500)`, pid 43948 morto). Onde está lido; o porquê não. Sem
  repro não há correcção, e a app ficou **sem transcrever entre 09:36 e 10:56** sem nenhum instrumento
  a dizê-lo — o `live-code-freshness-oracle` só o revelou quando foi chamado.
- ~~**A tarefa agendada `\Sotto` não larga a app**~~ — **MEDIDO 2026-11-15, e o item estava VENCIDO.**
  `schtasks /query /tn Sotto /v /fo LIST` devolve `Modo de Logon: Interativo apenas`, `Estado:
  Habilitado`, `Último resultado: 0`, `Tarefa a ser executada: H:\sotto\app\webview\run.cmd`, e o log
  vivo confirma a largada: `SHELL_STARTUP_STAGE pid=19996 stage=pre-lock` as **2026-11-14 13:01:22.817**
  (a hora do `Hora da última execução: 14/11/2026 13:01:13` mais 9 s de arranque), `TRAY_ICON_ADD
  ok=true`, e a MESMA sessão a viver ate' as **22:35:35** — **9 h 34 m** de app a funcionar, com
  `CAPTION_WANTED_START on=true`, `HOTKEY_REGISTERED register=true`, `SPACE_SWALLOW_INSTALLED`, tres
  `BRIDGE_LOAD_MS`. O `-1073741510` de 2026-10-30 media outro estado da tarefa e outro `run.cmd`;
  o caminho do autostart do logon **esta' medido e funciona**. `UNMEASURED` continua so' uma coisa:
  a largada **no logon** em si (o `Tipo de Agendamento: No logon` so' se prova no proximo logon dele),
  porque a linha acima e' o resultado de uma execucao da tarefa, nao de um boot.
- **A qualidade do ARK-ASR no português além de um clipe de 15 s** (2026-10-30): mediu-se que ele
  emite **inglês** onde devia transcrever, e a lista de línguas não tem `pt`. Um WER sobre corpus não
  existe, e não é preciso para a decisão tomada (`_main/receipt-20261030-ark-asr-vs-parakeet.md`).
- **41 `except … : pass` em `app/webview/sotto_webview.py`** (medido hoje com `ast`: um handler cujo
  corpo e' so' `pass`, zero `bare except`; `youtube_captions.py` 9, `worker/sotto_worker.py` 13).
  Dos 41, o `exception-hygiene-oracle` conta 7 — os dois numeros medem coisas diferentes (o portao
  conta `except Exception` sem comentario, a AST conta todo o handler mudo) e **nenhum dos dois diz
  quantos desses 41 escondem uma falha que o dono sentiria**. O `code-health` estava no limiar
  (21 -> 41) e a linha de base foi atualizada HOJE com esta linha escrita, nao em silencio.
  Auditar e' trabalho por fazer: cada handler ou ganha `log(...)` com um codigo nomeado, ou uma razao
  escrita ao lado. Nao se "corrige" apagando o `pass`.
- **A VOZ DE UMA CALL REAL NO TAP POR PROCESSO** (2026-11-09, ordem do dono *"identifica corretamente o
  audio saindo do discord"*). O caminho esta' medido ate' onde uma lane pode ir: `PLP_START hr=0`, a
  RAIZ da arvore do `Discord.exe` (pid 22992, e **nao** o maior pid 24484) abre e entrega **39 blocos
  em 4 s** com `pump_exited=False hr=0`, e o alvo por NOME resolve/re-resolve (`PROCESS-TARGET PASS
  14/14`, `--neg-arm` 3/3). O que **nao** esta' medido e' a voz: na janela da medicao o Discord
  renderizava SILENCIO (`peak=0.0 rms=0.0 silent_packets=0`) -- um tap aberto e mudo e' indistinguivel
  de um tap que nao ouve. Prova-la exige uma call activa, e a separacao contra o mix exigiria TOCAR
  audio numa lane, que a lei do audio do dono proibe. Recibo:
  `_main/receipt-20261109-discord-per-app-tap.md` §5.

- **A FUSAO PELO SEAM VIVO DA APP** (2026-11-09, ordem do dono *"legenda AO VIVO otima E
  historico otimo"*). Estado atual: `SOTTO_FUSION` continua desligado por padrao. Com a flag ligada,
  `_fusion_caption` publica apenas texto sem divergencia entre as duas hipoteses (sinal de acordo,
  nao prova acustica); sem evidencia acustica para uma divergencia, preserva a hipotese original do
  stream e marca revisao. `_main/fusion-wire-oracle.py`
  executa o seam real extraido por `ast` (10 arms; controles negativos apanham call-site removido e
  guard permissivo), e `_main/panel-row-identity-oracle.js` percorre o `caption-formulation.js`, o
  `panel.js` e o CSS reais: 11 checks positivos; M8 apanha a remocao do marcador da linha e M9 apanha
  a perda do meta no produtor. A linha textual permanece original; o painel ganha o marcador visual
  `?` e o titulo de revisao. `_main/fusion-audio-oracle.py` continua a provar o lote limitado, corte
  contado e cauda preservada por identidade (11 arms, `--neg-arm` 5/5). **UNMEASURED:** pintura real
  no WebView2/overlay durante uma sessao viva, WER/CER ou taxa de correcao com referencia humana, e
  qualquer confirmacao acustica de palavras divergentes. Esses limites mantem a fusao desligada por
  padrao e impedem afirmar ganho de precisao.

- **O SPLIT DO ARRANQUE NA MAQUINA DELE, POR FASE** (2026-11-10) — **MEDIDO 2026-11-15, e o split com
  o disco degradado EXISTE no log dele.** O item dizia que so' o perfil de uma maquina desta arvore
  (`_main/_cache/acc-target-name.log`, `total=8.572s`) estava medido e que o caso dos 44,3 s ficava em
  aberto. Os **tres** `WORKER_BOOT_PROF` da sessao de 2026-11-14 13:01-22:35 (a que a tarefa `\Sotto`
  largou, pid 9612/38848/28360) trazem o split completo, cada um com a sua parede:

  | arranque | `BRIDGE_LOAD_MS` | `sess_encoder` (=`load_phases.encoder`) | `decoder` | `joint` | `sessions_total` |
  |---|---|---|---|---|---|
  | 13:01:43 | 20 500 ms | 19,614 s (18,529) | 0,671 s | 0,034 s | 19,234 s |
  | 18:34:57 | 29 735 ms | 29,352 s (28,711) | 0,092 s | 0,041 s | 28,844 s |
  | 19:59:19 | 51 062 ms | 50,472 s (50,130) | 0,253 s | 0,088 s | 50,470 s |

  O `sess_encoder` e' **96-99 %** do `sessions_total` nos tres: o custo do arranque na maquina dele
  **e' UM so' — a sessao do encoder**, e `decoder`+`joint` juntos ficam abaixo de 0,7 s em todos.
  Ou seja a hipotese que este item levantava ("o arranque paga DUAS cargas") **esta' refutada para o
  caso degradado**: o `og_model` nem aparece nos tres perfis (o `og_import` fica em 0,34-1,07 s), e a
  variacao de 20,5 s para 51,1 s e' **a mesma sessao a demorar 2,5x** conforme o disco, nao uma carga
  a mais. O `boot-profile-oracle` le exactamente estes campos e da' `PASS -- 4 arms` no perfil real
  (medido agora: `SPLIT total=18.473s ... sess_encoder=+16.570 ... og_model=+1.257`), com
  `--neg-arm 3/3`. O que **continua por medir** e' a CURA: adiar a construcao do `og.Model` deixa de
  ter alvo (ele nao e' o custo), e o alvo real — a sessao do ORT do encoder — so' encurta com o disco
  menos degradado ou com um checkpoint menor, e nenhum dos dois e' uma mudanca de codigo desta lane.
  Por isso nenhuma cura se escreve aqui: o numero diz que nao ha o que adiar. O caminho que faltava ja'
  esta' montado e agora corre: a tag `WORKER_BOOT_PROF` atravessa a allowlist (commit `1583cb2`) e o
  passo `boot-profile` le' o ultimo perfil do log dele com o split impresso.

- **O `ack_ms` da PRIMEIRA pintura depois das flags de desbackground (2026-11-24).** O relogio do
  dono media `PANEL_SHOW_COST reason=hotkey-cycle-strip mode=strip ... ack_ms=328.0 total_ms=359.0
  budget_ms=400` (pid 27448, 07:59:58.083) e `ack_ms=0.0 total_ms=109.0` no segundo show do mesmo
  minuto: a janela nasce escondida e o renderer e' despriorizado, logo o primeiro quadro custa 328 ms
  e os seguintes nao. As duas flags que atacam essa causa embarcam em `app/webview/webview2_args.py`
  (`--disable-renderer-backgrounding`, `--disable-backgrounding-occluded-windows`) e o
  `_main/webview2-args-scope-oracle.py` prova que ELAS CHEGAM ao ambiente (12/12 arms, `--neg-arm`
  3/3) -- mas isso e' a metade do INSTRUMENTO. **A leitura que falta e' `PANEL_SHOW_COST ack_ms` de um
  processo novo DEPOIS das flags**, e esta pane nao a produz: tentado duas vezes em 2026-11-24
  (`pythonw app/webview/sotto_webview.py --no-warm-engine --probe-v2 25 --exit-after 200 --log
  _main/_cache/_probe-firstshow.log`) e o WebView2 morreu antes da janela nas duas --
  `WEBVIEW2_INIT_FAILED 0x80010108 RPC_E_DISCONNECTED` as 12:34:53 e `0x80080005 CO_E_SERVER_EXEC_FAILURE`
  as 12:35:05, com `PANEL_V2_GATE=RED` e nenhum `PANEL_SHOW_COST`. E' a limitacao de pane ja' registada
  em `AGENTS.md`; a medicao exige o Alt+C do dono num arranque dele. CANNOT-MEASURE aqui, NOT a pass.

- **O tecto do diarizador depois do `42b7420f` (2026-11-26) — `fixed, NOT verified`.** A janela
  `DEFAULT_WINDOW_S` desceu de 20,0 s para 10,0 s porque `S.tick` mediu, sobre 11,9 s de áudio real
  (`_main/_cache/...-12s-16k.wav`, `provider=cpu`, 2 fios), **RTF 0,037 com janela 10 s** contra
  **RTF 0,768 com janela 20 s** (0,38 s de CPU por tique contra 15,36 s) — o penhasco medido é 40×.
  O que NÃO está medido: a CPU do processo `python.exe` do sidecar **depois de ele arrancar com o
  código novo**. O processo vivo é o `python.exe(73436)`, criado 11:45:10, anterior ao commit; uma
  lane não reinicia a app dele. A medição é `_main/shell-thread-cpu.py <pid> --seconds 8` na árvore
  dele depois do próximo arranque. Antes: **40,9 % de um núcleo**. Esperado: **~7,6 %**.

- **A cadência de pintura e do relógio de revelação com o painel ABERTO (2026-11-26).** Com
  `SOTTO_LANE_LAUNCH=1` a shell publica `CAPTION_WANTED_START on=false reason=lane` e
  `_caption_wanted=false`: não há cues nem `CAPTION_PAINT_SURFACE`, logo a cadência de pintura e o
  relógio de revelação não podem ser julgados de uma lane. A metade que corre (attach, snapshot,
  pausa, seek, leitura, histórico) está coberta por `yt-pause-disagreement`, `youtube-monotonic`,
  `yt-diag-truth`, `product-soak`. A outra metade exige a faixa na tela dele — buraco nomeado, não
  decisão de lane.

- **O YouTube a tocar de um perfil de lane (medido 2026-11-26, três perfis).** Um `--user-data-dir`
  limpo abre a página, o DOM fica completo e
  `movie_player.getPlayerResponse().playabilityStatus.status == LOGIN_REQUIRED` com
  `streamingData.adaptiveFormats` vazio: `readyState` fica 0 e nenhum segmento de legenda aparece.
  Os cookies de consentimento não levantam isso, e nem `--headless=new` nem janela fora do ecrã mudam
  nada — é política de sessão do YouTube. `CANNOT-MEASURE reason=youtube-login-required`; a via
  livre de dono é um login descartável dentro do perfil da lane, e o perfil dele nunca é a resposta.

## Captura e replay do player — o que a medicao de 2026-11-26 deixou em aberto

- **CUE TEXT sem sessao: `UNMEASURED` por impossibilidade medida.** 3 videos, 26 faixas, todas
  `200` com 0 bytes num perfil de lane sem login. Uma lane com cookie jar (`--cookies`, Netscape ou
  JSON) fecha; sem ele o braco (g) do `yt-capture-replay-oracle.py` responde
  `CANNOT-MEASURE why=no-caption-segment`.
- **Frescura da foto no replay: HOLE declarado** (o `stamp` nasce na leitura, logo uma linha do
  tempo nao distingue foto velha de leitura nova). Dono: `_main/yt-pause-disagreement-oracle.py`.
- **A pausa/seek na instalacao do dono**: `fixed, NOT verified` — os pids 53752/73436 correm codigo
  anterior aos commits de 2026-11-26.

## A CAMADA DE PROVA DO BEND NAO ESTA A SER VERIFICADA NESTA MAQUINA (medido 2026-11-26)

`wsl -l -q` nesta maquina lista **`bluetest`** e mais nada (lido dos bytes UTF-16-LE:
`b\0l\0u\0e\0t\0e\0s\0t\0`). A distro `ubuntu-bend`, onde o portao do Bend corre
(`bend PROOF.bend --verdict`, nunca `--check-only`, pela regra do Bend 2 neste `AGENTS.md`), **nao
existe aqui**. O `_main/bend-laws-gate.py` classificava isso como `BEND-GATE FAIL ... not usable` e a
bateria publicava RED de INFRA; antes disso, `_wsl_alive` expirava e o passo era SKIPPED *pelo
relogio*, nao pela ausencia — duas maneiras de nao dizer a verdade.

- A sonda agora pergunta a LISTA (`_distro_installed`), nao a mensagem de erro: o `wsl.exe` imprime o
  erro de distro ausente para o **stdout** de um processo sem consola (`stderr` vazio, medido) e a
  lista em UTF-16-LE. Uma distro AUSENTE sai `BEND-GATE SKIPPED: ... NOT INSTALLED` (rc 0, casado
  pelo `:skipped` da bateria); uma distro PRESENTE que nao responde continua `EXIT_INFRA`.
- **O que isto NAO faz:** as leis do Bend continuam **NAO VERIFICADAS** neste estado. `LAWS.bend` /
  `PROOF.bend` e os `NEGATIVE_*.bend` nao foram executados nesta corrida, e nenhum arm desta sessao
  os substitui. O log do passo diz isso com todas as letras, e a linha da bateria e' `skipped`.
- Para fechar: instalar/repor a distro `ubuntu-bend` (acao de sistema, do dono) e correr
  `python _main/bend-laws-gate.py` -> `BEND-GATE VERDICT: PASS`. Ate' la', a afirmacao
  "as leis provam o modelo" tem de ser lida como `UNMEASURED` nesta maquina.

## DOIS PORTÕES PROMETIAM UM FICHEIRO QUE NÃO EXISTE (medido 2026-11-26)

`AGENTS.md` apresentava dois checques como armados sobre um baseline em disco. O `git ls-files` de
2026-11-26 diz que **nenhum dos dois ficheiros existe**, e cada portão tinha o seu próprio jeito de
não dizer nada:

|portão|o que a prosa prometia|o que o código fazia|o que faz agora|
|---|---|---|---|
|`_main/shell-thread-budget-oracle.py`|ratchet de +20 % sobre `_main/shell-thread-budget-baseline.json`|`if baseline:` com `baseline={}` → **o ratchet desaparecia em silêncio**|imprime `RATCHET absent reason=no-baseline file=...` e mantém os tectos absolutos (total 25 %, fio 15 %, fio mais quente COM NOME)|
|`_main/owner-screen-gate.py`|dívida congelada em `_main/owner-screen-baseline.json`|`except: return {'ceiling': 0, ...}` — mais duro, mas mudo|imprime `OWNER-SCREEN baseline=absent file=... ceiling=0`|

- **Prova do primeiro (sem shell viva):** `main()` conduzido com uma leitura injectada
  (`total=5,0 %`, dois fios com nome) e um baseline inexistente → `rc 0`, a linha
  `RATCHET absent reason=no-baseline ...` impressa e `VERDICT: PASS` decidido pelos tectos.
- **Prova do segundo:** `python _main/owner-screen-gate.py` → `baseline=absent`, 1330 ficheiros de
  produto, `achados=0`, `VERDICT PASS`.
- **O que continua NÃO MEDIDO:** o **valor** do ratchet. Ele só existe depois de um arranque fresco
  da shell medir `python _main/shell-thread-budget-oracle.py --update`; a instância do dono
  (pid 53752, criada 11:45:10) é anterior ao código desta sessão, e uma lane não a põe na tela dele.
  Até lá o ratchet está **desarmado**, dito pelo próprio oráculo, não escondido.
