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
**LEITURA HISTÓRICA, NÃO A REGRA DE HOJE.** O parágrafo acima descreve o estado em 2026-10-23; a correção de 2026-11-10 logo abaixo é a que vale. Re-medido em 2026-11-25 nesta árvore: `grep -rnE 'EXTERNAL_RESUME_MIN_S|EXTERNAL_CAPTIONS_WORKER_RESUME_DEFERRED' worker` → **ZERO LINHAS** (só um comentário em `app/webview/sotto_webview.py:3053` e cópias congeladas em `_main/`). A retoma viva tem duas guardas (`exiting`, `engine_park_reason() == 'captions'`) mais o latch `_external_parked`, em `app/webview/sotto_webview.py:21472-21497`; não há piso de 45 s.

**CORRECÇÃO DE 2026-11-10 — DUAS das quatro guardas saíram, e a razão é que elas GUSTAVAM o release.**
Medido no estado em disco da sessão do dono (2026-11-09 21:36:12): `"park": "captions"` com
`"visible": false`, reimpresso a cada 3 s, `staleAfterSeconds=9.0` a nunca expirar; **1**
`EXTERNAL_CAPTIONS_ENGINE_RESUMED` contra **16** `ENGINE_PARK reason=` em 187 339 linhas de log. O latch
`_external_parked` era consumido **antes** das guardas de `_paused` e de visibilidade, e como o release é
de **borda** (o watcher avisa uma vez) um `return False` queimava a única oportunidade — o
`set_engine_park(None)` nunca corria e a chamada seguinte morria no latch já consumido. As palavras dele
foram *"a legenda congela e nunca volta"* e *"o audio volta e nada acontece"*.
- **O piso de 45 s já não existe** (`EXTERNAL_RESUME_MIN_S` e `EXTERNAL_CAPTIONS_WORKER_RESUME_DEFERRED`
  foram removidos com o processo em 2026-11-03): limpar um **pedido** num ficheiro não custa nada, e o
  piso mantinha o motor largado até 45 s depois de o player parar.
- **A pausa e a visibilidade deixaram de guardar o PEDIDO.** Elas desligam o **DISPLAY** (regra 3:
  legenda ao vivo desligada não é modelo desligado), nunca o parque, que é do MOTOR. Só o motivo
  `captions` sai daqui; o parque por **VRAM** tem outro dono e continua de pé.
- Portão: `_main/external-resume-latch-oracle.py` (7 braços sobre a função REAL extraída por `ast`, e o
  `--neg-arm` repõe as duas guardas **na função extraída** e cai em 3 braços, rc=1), na bateria como
  `external-resume-latch` + `red-as-expected-external-resume-latch`.
- **A CURA RECUSADA, e por que:** o forense propôs que o ramo do parque do worker perguntasse ao medidor
  vivo (`_live_render_peaks`) se algum endpoint voltou a tocar e terminasse o *hold* — o contrato do
  `silent_desktop_hold` diz mesmo "qualquer endpoint acima do piso → `None`". **Mas aquele contrato é da
  máquina CALADA, não do parque:** com o player a fornecer legenda o áudio **está** a tocar, portanto o
  hold terminaria em todas as janelas e a escada voltaria a abrir um cliente WASAPI por janela — o defeito
  de 46 rotações em 11 minutos que o hold existe para curar. Não foi aplicado.

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

## 2026-11-25 — uma captura para o worker e o sidecar; uma tabela de defaults `SOTTO_REDUX_*`

**UMA CAPTURA, UM LEITOR.** O worker já abre o único par loopback + micro (`mic_tap.open_stream`) e entrega 16 kHz mono float32 à ASR; o sidecar abria outro par para a mesma chamada. `worker/capture_share.py` publica agora o bloco **já misturado** no limite do ASR (`worker/sotto_worker.py:8609-8610`) e o sidecar liga-se antes de enumerar qualquer dispositivo (`worker/speaker_sidecar.py:1811-1844`). Contrato medido: um cliente só (`BUSY`), fila `QUEUE_BLOCKS` com queda contada em `CAPTURE_SHARE_DROP dropped=N`, publicação inerte sem leitor, timeout de ligação de `TIMEOUT_S = 2.0` com `CAPTURE_SHARE fallback reason=<...>`, e `SOTTO_CAPTURE_SHARE=0` desliga o cliente por nome. O sidecar standalone mantém o tap local como fallback; **com `BUSY` NÃO ha' fallback** —
o worker ja' abriu o par e um segundo par nos mesmos endpoints e' o defeito que a regra
proibe, logo o sidecar degrada por nome (`sidecar: no diarization -- capture slot busy;
no second device opened`, rc=2, zero taps). `_main/capture-share-oracle.py` arm `i` (9/9
arms, mutante `busy-fallback-opens-second-pair` apanhado) `[MEASURED]` 2026-11-26: com a
slot ocupada o codigo anterior abria o par (`taps=1`, `MIC_CAPTURE mic=fake`). `[MEASURED]` 2026-11-25: `python _main/capture-share-oracle.py` → `CAPTURE SHARE VERDICT: PASS (8/8 arms)`, incluindo o braço `f` com `worker_taps=1 worker_mics=1 sidecar_taps=0`, o `g` (um estranho calado não despe o leitor) e o `h` (um stop ordenado não é falha).

**OS DEFAULTS TÊM UM DONO SÓ.** `WorkerBridge._child_env` usa `setdefault` para `SOTTO_REDUX_WHEN_HIDDEN` e `SOTTO_REDUX_LIVE` (`app/webview/sotto_webview.py:25243,25254`): o valor explícito `0` do operador ganha, e `run.cmd` deixou de ser a segunda tabela de defaults (só comenta a escada). Quem resolve é o worker, em `redux_live_settings` (`worker/sotto_worker.py:6375-6413`): flag → ambiente (`1` liga, `0` desliga) → `redux_live.enabled` do config → desligado, com o motivo impresso em `opt_in=`. Assim duplo-clique, autostart e `run.cmd` arrancam o mesmo binário com o mesmo comportamento. `[MEASURED]` 2026-11-25: `python _main/config-truth-oracle.py` → `VERDICT: PASS` nas três afirmações; os portões de transporte são `_main/app-target-oracle.py` e `_main/load-shedding-oracle.py`.
