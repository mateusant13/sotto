# Parakeet como segundo pass e lifecycle do worker (ORDEM 3)

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.

### 3. O Parakeet é o segundo pass, com lifecycle inteligente
> *"legenda ao vivo, com o modelo nemotron... qualquer legenda que ja passou (nao é mais ao vivo) tem que
> ser processada tambem pelo parakeet, ou imediatamente, ou com delay, ou quando seguro de fazer isso...
> se minha legenda ao vivo ta desativada e eu nao to usando, é só o parakeet que comanda."*

O mecanismo existe (`worker/redux_batch.py`, `worker/redux_live.py`, flag `--redux-when-hidden`,
`SOTTO_REDUX_LIVE=1` em `app/webview/run.cmd`). **BURACO DECLARADO, RE-MEDIDO E FECHADO EM 2026-10-23.**
O texto anterior dizia que `on_external_captions_released()` **não** trazia o worker de volta. Re-lido o
método nesta revisão: **traz** — atrás de **quatro guardas** e de um **piso de 45 s**
(`EXTERNAL_RESUME_MIN_S`): shell a morrer (`exiting` → não arranca, senão fica um órfão que carrega 1,2 GB
depois de a app fechar, medido 2026-10-20), release sem park, em pausa, e sem painel **nem legenda**
visíveis; dentro dos 45 s loga `EXTERNAL_CAPTIONS_WORKER_RESUME_DEFERRED` e **não** mexe no relógio. O
que faltava não era código: era **prova**. Isso é `_main/external-resume-oracle.py` — **8 braços / 8
mutantes** (`sem-guarda-exiting`, `sem-guarda-park`, `sem-guarda-pausa`, `sem-guarda-visivel`,
`legenda-nao-conta`, `sem-piso-45s`, `relogio-antes-do-piso`, `relogio-nao-anda`), na bateria com o braço
negativo `red-as-expected-external-resume`. **A lição:** um `AGENTS.md` que descreve um buraco já fechado
manda trabalho para o sítio errado; re-medir antes de repetir (regra 1).

### 3b. Carga: os motores carregam e largam sozinhos, e o áudio espera (2026-11-01)

Ordem do dono, verbatim:

> *"modelos carregados dependendo da carga do sistema ou nao. quando carga liberar, carrega sozinho
> (NUNCA TRAVAR O PC DO USUARIO OU STUTTER OU QUALQUER COISA DESSA NATUREZA) e processa qualquer audio
> nao processado, com o parakeet."*

O QUE MUDOU, e onde vive:

* **A decisão lê a carga MEDIDA.** `app/webview/load_shedding.py:LoadProbe` mede commit % (uma vez por
  `SAMPLE_INTERVAL_S` = 5 s, `GlobalMemoryStatusEx`) e CPU % (`psutil.cpu_percent(interval=None)`, nunca
  bloqueia); `LoadShedding` aplica os limiares com histerese. `ReduxHiddenSwitch.tick` obedece ao **pior**
  entre o nível publicado pela shell e o medido, e a linha `REDUX_SHEDDING` leva `commit_pct=`, `cpu_pct=`
  e `why=` — o número que disparou a decisão está escrito, não inferido.
* **Quem corre o lote é o parakeet** (`worker/sotto_worker.py:ParakeetEngine`, ONNX int4, ~615 MB
  medidos), carregado na thread `redux-batch` — nunca na thread do áudio. `RunnerEngine` (o
  `worker/redux_batch.py` ternário, ~3,9 GB) continua como alternativa quando é ele que está no disco.
* **`muito-alta` LARGA o modelo** (`REDUX_ENGINE_RELEASE` com o motivo) e **a descida recarrega sozinho**
  no lote seguinte — é a ordem, ao pé da letra.
* **O áudio nunca é o que se larga.** Todo bloco capturado com nada carregado entra em
  `worker/live_queue.py:PendingAudio`: RAM até `max_audio_s` e, ao passar disso, **spool em disco** (ordem
  de chegada, `float32` cru, um ficheiro por ciclo). Não existe caminho de código que deite um bloco fora:
  `dropped` só pode ser 0, e o `done` do worker publica `reduxAudioIn` / `reduxAudioOut` /
  `reduxAudioSpilled` / `reduxAudioDropped`. O acumulador antigo (`REDUX_BUFFER_TRIMMED`, que apagava o
  bloco mais velho aos 120 s) **já não existe**.

OS TECTOS, ditos por inteiro:

| tecto | valor | onde |
| --- | --- | --- |
| RAM do áudio à espera | `--redux-max-audio` (120 s = 7,7 MB) — acima disto vai para disco, não para o lixo | `PendingAudio(ram_s=…)` |
| disco do spool | sem tecto próprio; avisa (`AUDIO_PENDING_LOW_DISK`) abaixo de 1 GiB livres | `SPOOL_LOW_DISK_BYTES` |
| memória livre para um lote parakeet | 800 MB (`REDUX_ENGINE_MIN_FREE_MB`, pico 615 MB + margem); o ternário mantém 4600 MB | `flush_pending` |
| janela decodificada por passagem | 3 s (`REDUX_ENGINE_WINDOW_S`) | `_run_engine` |
| intervalo entre lotes | `--redux-batch-interval` (15 s) | `maybe_kick` |
| recuo depois de um lote falhado | 2^n s até 60 s (`_park`) — um motor partido não é tentado 1×/s | `_park` |
| fila do áudio vivo | 2 s, sai o mais VELHO (`live_queue.enqueue_live`) | `LIVE_QUEUE_MAX_S` |

PROVA: `_main/load-shedding-oracle.py` (74 braços; executa `LoadProbe`, `LoadShedding` e o
`ReduxHiddenSwitch` reais: 96 % medido → `shed` com o número no log; 25 blocos com nada carregado → 25 na
espera, 0 perdidos, 15 no disco; carga a libertar → o motor carrega sozinho e a espera **drena para
zero**, N entra == N sai; `muito-alta` larga o modelo e o lote seguinte recarrega-o) e
`_main/live-queue-oracle.py` (32 braços do `PendingAudio`: ordem através da RAM e do disco, entrega total,
devolução à frente, `dropped=0`). Braços negativos: **tabela trocada**, **canal trocado**, **um bloco
deitado fora**, **fila fechada cedo** — os quatro ficam RED, medidos.
