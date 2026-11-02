# 2026-11-02 — a morte que era um homicidio, a causa publicada, e a memoria em serie

Tres commits nesta sessao, cada um com o seu instrumento e o seu braco negativo:
`db4b4d7` (a causa da morte), `524fb9d` (o kill do proprio shell nao e' morte),
`ce324e2` (a memoria vira serie). Todos pushed em `feat/speaker-attribution-20261019`.

## 1. O que estava a acontecer (medido, nao suposto)

O dono, a jogar, com o Sotto ao vivo. O log dele (`_main/webview-run.log`, 46 MB, 46 782 282 B):

|hora|pid|rc|o que o shell dizia|o que era|
|---|---|---|---|---|
|19:22:29|41496|1|`BRIDGE_EXIT ... rc=1`|`EXTERNAL_CAPTIONS_WORKER_PARKED` -> `BRIDGE_STOP reason=external-captions`: um PARQUE deliberado (o YouTube passou a pintar). Nao publicou `BRIDGE_DEATH` -- correcto.|
|19:36:40|28396|1|`BRIDGE_DEATH rc=1 deaths=1 kind=error`|`BRIDGE_SILENT ms=30000` -> `_kill_and_restart('silent')` -> `TerminateProcess` = `rc=1`, publicado como MORTE. Painel vermelho + uma recarga inteira, num worker que tinha entregue `CAPTION_APPLIED count=200` **0,4 s antes**.|

Censo da classe: **10** `BRIDGE_SILENT` anomalas no ficheiro; **9** sao seguidas, no mesmo pid e
em menos de uma linha de log, de um `BRIDGE_EXIT rc=1`. `BRIDGE_DEATH` total = 178, dos quais 31
`kind=error`.

O motivo do silencio falso: `_note_progress` so' re-arma o cao de guarda com `WORKER_STATS` cujo
`blocks` AVANCA. Dentro de um lote longo (parakeet, `redux_mode=batch`) o laco paralisa, o `blocks`
congela, e o worker e' morto por estar a trabalhar. `infer_wall_s=18.25` no ultimo tick medido.

## 2. O que ficou

- `STDERR_TAIL_MAX = 40` (era 3) e `BRIDGE_DEATH_CAUSE <excecao>` na morte.
- O ONNX Runtime escreve WIDESTRING: a linha de stderr com NUL passa a ser re-decodificada de
  `utf-16-le` (antes ia para o log como `\u0000\u001b\u0000[\u00000\u0000;\u00009\u0000...`).
- `self.killed` marca o filho que ESTE shell terminou: `BRIDGE_EXIT ... killed=true` +
  `BRIDGE_KILLED why=the-shell-terminated-it`, sem `BRIDGE_DEATH`, sem contar a morte, sem vermelho.
- `PROGRESS_TAGS` (`REDUX_BATCH_KICK`, `REDUX_ENGINE_DONE`, `REDUX_MODE`) contam como progresso.
- `BRIDGE_RSS rss_mb=.. blocks=..` uma vez por minuto: a memoria passa a ser uma SERIE.

## 3. Os portoes, e o que cada um RECUSA

|passo|arms|braco negativo|
|---|---|---|
|`death-cause`|5 (retencao de 40, ultima linha, causa publicada, cauda limpa nao inventa causa, widestring legivel)|repo~e `STDERR_TAIL_MAX = 3` e desarma o decode -> exige as duas RED|
|`silence-kill`|5 (marca do kill, kill publicado, crash a serio continua morte, lote re-arma, stderr inerte NAO re-arma)|muta a marca (derruba ARM 1) e as `PROGRESS_TAGS` (derruba ARM 4)|
|`rss-trend`|4 (fuga=FLAG, aquecimento que assenta=ok, dente de serra=ok, serie curta=UNKNOWN)|limiar em 1e9 numa copia -> a arm da fuga TEM de cair|

`python _main/rss-trend-oracle.py --log _main/webview-run.log` -> `n=0 UNKNOWN`: o instrumento e'
novo e a serie ainda nao existe. **UNKNOWN nao e' verde** -- e' a razao de a shell passar a publicar.

## 4. O que NAO foi verificado (SELF-AUDIT)

- **Nenhuma corrida da app nesta sessao.** A shell nao pode ir ao ecra do dono (`SOTTO_NEVER_ON_OWNER_SCREEN`);
  tudo o que envolve `_pump`/`_wait`/`_kill_and_restart` foi exercitado com o codigo REAL e um `self`
  falso, e com um FILHO real nos arms de stderr. A primeira prova de campo e' o proximo uso dele:
  procurar `BRIDGE_KILLED`, `BRIDGE_DEATH_CAUSE` e `BRIDGE_RSS` no log.
- O `rc=1` das 19:00:24 (stderr em widestring, `onnxruntime_pybind_state.cc:855`) NAO foi explicado:
  a cauda de 3 linhas desse dia perdeu o contexto, e nao houve reproducao.
- `infer_wall_s=18.25` prova que um lote bloqueia o laco; NAO prova o microsegundo exacto em que o
  `blocks` congelou (o log nao guarda os ticks de stderr).
- A lane de investigacao do `rc=1` foi despachada tres vezes e NAO correu: `commandcode` 429 (limite
  semanal), `worker_zen` e `worker_cline` "No model selected", `worker_route` -> `opencode-go-6` 401.
  O trabalho foi feito nesta sessao, sem subagente.

## 5. Disco (ordem do dono: espaco desperdicado e' inadmissivel)

- **1 046 MB** de Electron MORTO removidos (provado antes: `run-all.mjs` = `SUITES 15 passed` +
  `GATE 9 passed / 0 refused`, e `transcript-append-oracle.js` GREEN sem eles).
- `git worktree prune`: 16 registos -> 6 reais. Os seis somam ~290 MB e cada um tem commits fora do
  ramo actual (1-9), por isso NAO se apagam sem decisao.
- Ficam por decidir: `_main/diar-models` 764 MB (pesos de diarizacao, gitignored, trabalho pausado),
  `.codeintel` 167 MB (indice reproduzivel), `_main/_redux-long` 232 MB (13 wav, 3600 s o maior).

## 6. O que a bateria apanhou de mim (e e' a razao de os portoes existirem)

A primeira corrida depois dos tres commits deu **RED - 6 step(s) failed**, e quatro delas eram
defeitos MEUS, nao do repo:

|passo|o que disse|o que era|
|---|---|---|
|`undefined-names`|`RED ... WEBVIEW2_BG_TRANSPARENT usado em [14881, 14888]`|a minha compressao de um bloco de comentario colou a linha do comentario ao `WEBVIEW2_BG_TRANSPARENT = '00000000'`, que ficou DENTRO do comentario: a constante deixou de existir.|
|`autostart-status`|`autostart=4` + `NameError: name 'WEBVIEW2_BG_TRANSPARENT' is not defined`|a mesma causa, apanhada a correr. Sem estes dois passos, a shell nao arrancava no proximo uso.|
|`silence-kill`|`ARM 4 ... (stats+batch=0) FAIL`|o `Fake` do oraculo nao tinha `_rss_at`, e o meu `__getattr__` permissivo devolvia uma funcao: `time.monotonic() - <funcao>` rebentava dentro do `_pump` e matava o laco antes da segunda linha.|
|`red-as-expected-*` (3)|`=0` onde o `:expectred` exige `rc=1`|os meus `--neg-arm` saiam 0 quando APANHAVAM o mutante. A convencao do repo e' a inversa: RED as designed = rc 1, e o `_cache` do passo compara os dois.|

Corrigidos os quatro, e' esta a licao que fica escrita: **o `code-health` (bytes/linhas/defs) nao ve
um nome que deixa de existir** -- quem ve e' o `undefined-names`, e a prova de que veio e' o
`autostart-status` a correr a shell. Um ratchet de tamanho nao substitui um portao de semantica.

## 7. Carga do sistema: por que hoje nao ha' uma unica linha de shed (medido)

`grep -c REDUX_SHEDDING _main/webview-run.log` = **0** no ficheiro inteiro (46 MB, desde 2026-10-13).
Nao e' um canal morto -- e' a leitura de hoje a dizer que nao ha' nada a decidir:

    python -c "import load_shedding as ls; print(ls.level_for_load(43.9, None))"   ->  leve
    commit_pct = 43.9      cpu_pct = None (primeira amostra nao e' medicao)

Os limiares, lidos do modulo e nao supostos: `HIGH_PCT = 88.0`, `VERY_HIGH_PCT = 94.0`
(commit), `CPU_HIGH_PCT = 90.0`, `CPU_VERY_HIGH_PCT = 98.0`; descer exige `commit < RESUME_PCT
(80.0)`, `cpu < CPU_RESUME_PCT (70.0)` e `CONFIRM_SAMPLES = 3` amostras (5 s cada) -- e desce UM
degrau por confirmacao (`LoadShedding.observe`). `ENGINES` e' a tabela do dono: `leve` = os dois,
`alta` = so' parakeet, `muito-alta` = nenhum, e o AUDIO NUNCA e' largado.

O ANTI-THRASH ja' existe e nao e' um piso de 180 s (premissa minha, errada): sao quatro coisas
medidas nos seus sitios, `_main/load-shedding-oracle.py` com **78 arms** verdes -- `REDUX_MIN_AUDIO_S`
(um load so' acontece quando ha' audio novo que o justifique), a histerese de 3 amostras, o
`no_audio_backoff_base=15000` a dobrar ate' `no_audio_backoff_max=300000` (5 min), e o piso
`EXTERNAL_RESUME_MIN_S = 45.0` para o regresso do worker depois das legendas do YouTube.
O ARM 10 prova o ciclo completo: `muito-alta` larga o modelo e o lote seguinte recarrega-o SOZINHO
(`loads=2`, `10 linhas de audio entraram e sairam`).
