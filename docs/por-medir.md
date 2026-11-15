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
  historico otimo"*). O que esta' medido: `_main/fusion-wire-oracle.py` executa `on_worker_caption`
  REAL (extraido por `ast`) e prova que o texto fundido chega as duas superficies (o overlay e o
  payload que o painel commita, e que o `history_append` grava) -- 10 arms, `--neg-arm` rc=1; e
  `_main/fusion-audio-oracle.py` prova que o audio do ao vivo entra no lote com tecto, corte contado
  e cauda preservada por IDENTIDADE -- 11 arms, `--neg-arm` 5/5. O que **nao** esta' medido: o texto
  FUSIONADO pintado na janela nativa com uma call a correr, e a linha do historico REESCRITA pelo
  lote (o `history_merge` e' julgado no store, nao num transcript real de ponta a ponta). As duas
  coisas pedem a app aberta e audio a tocar, que a lei desta casa proibe a uma lane. Recebem
  `UNMEASURED` ate' o dono correr a app; o recibo declara o estado como DARK por isso mesmo.

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
