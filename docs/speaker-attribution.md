# Speaker attribution — the measured record (2026-11-24 .. 2026-11-26)

Moved verbatim out of `AGENTS.md` on 2026-11-27. `AGENTS.md` is the RULES; this file is the
evidence behind them — the numbers, the refutations and the oracle arm counts. In conflict, the
re-measurement wins; the rules themselves stay in `AGENTS.md`.

Origin sha256 of the moved block: `b4540f2c3ed536b97dcf6b5748dca91e9a8b61bf2a0f4d01812dc5999fb4d9f0`

---

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
