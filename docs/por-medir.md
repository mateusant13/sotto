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
- A contradição do flash de painel no arranque (§Factos).

- **O gesto Alt+C de 200 ms na mão do dono** (2026-10-30). A régua `HOTKEY_HOLD_MS` está provada por
  arms (199 ms = toque, 200 ms = HOLD) e por uma medição de pressões **sintéticas**; as durações reais
  dele (204 a 641 ms, recolhidas de `docs/hotkey-gestos.md`) foram medidas com o limiar antigo em vigor.
  Com 200 ms duas dessas pressões **passam a HOLD** e comutam a legenda em vez de abrir o painel. Não é
  um defeito: é a ordem dele. O que fica por medir é o que a mão dele faz agora.
- **Porque é que a criação da janela WebView2 pendurou a 2026-10-30 09:36** (`UI_HUNG_FRAME` em
  `winforms.create_window` → `thread.Join(500)`, pid 43948 morto). Onde está lido; o porquê não. Sem
  repro não há correcção, e a app ficou **sem transcrever entre 09:36 e 10:56** sem nenhum instrumento
  a dizê-lo — o `live-code-freshness-oracle` só o revelou quando foi chamado.
- **A tarefa agendada `\Sotto` não larga a app** (medido 2026-10-30 11:02:19: `-1073741510`,
  `0xC000013A` STATUS_CONTROL_C_EXIT, zero instância em 90 s). O `sotto-relaunch.py` deixou de depender
  dela (token de um processo `high` primeiro), mas a TAREFA continua partida e ninguém sabe desde
  quando — quem conta com o autostart do logon está a contar com um caminho não medido.
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
  historico otimo"*). O que esta' medido: `_main/fusion-wire-oracle.py` executa `on_worker_caption`
  REAL (extraido por `ast`) e prova que o texto fundido chega as duas superficies (o overlay e o
  payload que o painel commita, e que o `history_append` grava) -- 10 arms, `--neg-arm` rc=1; e
  `_main/fusion-audio-oracle.py` prova que o audio do ao vivo entra no lote com tecto, corte contado
  e cauda preservada por IDENTIDADE -- 11 arms, `--neg-arm` 5/5. O que **nao** esta' medido: o texto
  FUSIONADO pintado na janela nativa com uma call a correr, e a linha do historico REESCRITA pelo
  lote (o `history_merge` e' julgado no store, nao num transcript real de ponta a ponta). As duas
  coisas pedem a app aberta e audio a tocar, que a lei desta casa proibe a uma lane. Recebem
  `UNMEASURED` ate' o dono correr a app; o recibo declara o estado como DARK por isso mesmo.
