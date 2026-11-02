# Factos medidos que nao se re-litigam

> Movido de `AGENTS.md` em 2026-10-23 (trim). Conteudo verbatim;
> a medicao e as ressalvas sao as que la estavam.


- **A legenda que o dono VÊ é a NATIVA, não o `caption.html`.** `sotto_webview.py:69` define
  `CAPTION_HTML` e há **uma** ocorrência — a definição; o único `webview.create_window` é o do
  painel; `sotto_webview.py:5885` diz *"THE FLOATING CAPTION IS A NATIVE LAYERED WINDOW, NOT A
  WEBVIEW2"*. Quem desenha é `app/webview/caption_overlay.py` + `caption_wrap.py`: **qualquer
  correcção de CSS em `app/panel/` NÃO chega ao ecrã nesta via.** O *wrap* nativo equilibra as
  duas linhas (o pior desequilíbrio do corpus passou de **0,382** — o exemplo do dono — para
  **0,118**) e **nunca parte uma palavra**: portão `_main/caption-native-wrap-oracle.py`
  (GDI+ numa bitmap de memória, 4/4, e **2 mutantes** apanhados). Recibo:
  `_main/receipt-20261021-caption-native-wrap.md`.
- **A transcrição carrega SÓ a linha que o WORKER fechou (`route=final`).** Um `provisional-draft` é a
  legenda ao vivo: a caixa pode mostrá-lo, o histórico NÃO. Guardas em `panel.js recordHistory`,
  `history-store.js append`, `sotto_webview.py history_append`. A palavra `redux` nomeia o HISTORY STORE
  (`panel.html:109` "History · Redux"), não um segundo pass de ASR.
- **O segundo pass M1-M3 (rerun) está presente e ligado na via viva**: `drain` → `finalise` → `rerun`.
- **A caixa ao vivo SUBSTITUI, não faz append**: hipótese cumulativa (`start` fixo, `end` a crescer), um
  `<li>` reescrito em sítio. Ordem mais antigo no topo; o painel SEGUE a linha nova por omissão
  (`stickToNewest`), pára quando o dono rola para cima e retoma no fundo. A regra antiga
  (`scrollHeight - scrollTop - clientHeight < 48`) nunca podia COMEÇAR.
- **Palavras partidas em fronteiras de chunk**: RESOLVIDO (`chunk_is_continuation` lê a continuação dos
  TOKENS, `join_fragments` decide o separador; `detok` intacto). Portão `_main/word-split-oracle.py`.
- **`PAGE_ERROR` é o canal que nomeia um painel partido** (o `evaluate_js` só reporta a chamada do shell).
  Regra derivada: **tudo o que o bloco de init de `panel.js` pode tocar é declarado ACIMA dele** (um `let`
  em TDZ matou o painel em todos os arranques durante um dia).
- **Alt+C é o ÚNICO controlo da app**: regista-se em thread própria com `MOD_NOREPEAT`, tem cadeia de
  fallback (`Alt+Shift+C`, `Ctrl+Alt+C`, `Ctrl+Shift+C`), falha com um diálogo, e `toggle_panel` decide por
  `IsWindowVisible` (um cache velho fazia o primeiro Alt+C ser um no-op). O Sotto regista **um** acelerador;
  o **Shift+C é do AutoClicker do dono**, não é defeito nosso.
- **Instância única**: `Local\SottoShell` (mutex). Um launch de MEDIÇÃO toma um lock **derivado**
  (`Local\SottoShell.m.<flags>`), logo o app continua single-instance e duas medições com as mesmas flags
  não coexistem. O **hotkey** é a única coisa que uma medição dispensa.
- **Um launch de medição passa `--no-hotkey`** e `CREATE_NO_WINDOW`/`pythonw.exe`; senão responde ao Alt+C
  do dono com o seu próprio painel.
- **A app arranca com o Windows** (`HKCU\...\Run\Sotto` = `pythonw.exe ... sotto_webview.py --log ...`,
  nunca `run.cmd`, que faria flash de consola). Gerir com `run.cmd --install-autostart /
  --autostart-status / --uninstall-autostart`.
- **Flash do painel no arranque**: a cura é `_gate_form_show` (sombra o `Show()` do pywebview enquanto
  ninguém pediu o painel). `hidden=True` **não** basta: o pywebview mostra a form transparente em cada
  navigation start. Criar a janela `offscreen` ou pôr `transparent=False` **parte o loading** — proibido.
  **Contradição declarada e NÃO reconciliada:** o censo de 25 ms mede `live` 0/20 (4/20 sem a cura),
  o bullet histórico do mesmo instrumento mede 18/20 e 88/130 amostras visíveis. Quem reabrir isto corre
  `_main/panel-startup-flash-census.py` nesta revisão antes de acreditar num dos dois.
- **O worker não pode morrer num endpoint que outro processo detém** (o detentor é normalmente o seu
  predecessor): o open é em `start()`/`_open()` e um endpoint ocupado é **esperado e tentado 2×** (1,5 s)
  antes de a escada rodar.
- **`run.cmd` já respondeu 0 a tudo**: pré-flight `--check-args` (parser do próprio shell, sem segunda
  tabela de flags) recusa com o rc do filho e regista `sotto: ARGS_REJECTED`. `--help` é byte-idêntico
  antes/depois (a afirmação é a COMPARAÇÃO, medida por `_main/run-cmd-exit-oracle.py`).
- **`CUDAExecutionProvider` funciona** (o "não carregável" era falso): um único DLL faltava
  (`cublasLt64_13.dll`), curado por `_add_cuda_dll_dirs()` em `sotto_worker.py`. E a receita do pip tem uma
  falha silenciosa: `onnxruntime-genai` instala o `onnxruntime` plain POR CIMA do gpu → reparar com
  `pip install --force-reinstall --no-deps onnxruntime-gpu==<v>`. Três perguntas distintas:
  `get_available_providers()` (pacote), `session.get_providers()` (sessão), profiler (o que EXECUTA).
- **O motor ao vivo é HÍBRIDO, não "ORT-GenAI"**: `og.Model` cobre só a janela mel cache-aware e o VAD
  Silero; encoder/decoder/joint são `InferenceSession` plain e o laço RNNT é Python. `onnxruntime-genai`
  aqui é CPU-only (`og.is_cuda_available()` → False).
- **`run.cmd` NÃO é a causa de nenhum flash de painel**, e o path `pythonw su shell` está exonerado
  (`--direct` mediu o mesmo). Um censo que re-percorre a tabela de processos NÃO vê uma app `start`-detached
  cujo cmd.exe pai já morreu: semear o conjunto pelo `pid=` do log da app.
- **O histórico canónico aceita `meta.producer === 'redux'`** (`history-source.js`), fail-closed. O worker
  estampa `REDUX_PRODUCER` em `_run_runner`. `src=worker-stamped` é OUTRO campo (client-side) — não ler um
  como o outro. Em aberto: a tag `redux` nomeia o MODELO; se o finisher mudar de modelo, ou se mantém o
  literal (a tag só é verdadeira enquanto o finisher É o Redux) ou se renomeia em todos os sítios no mesmo
  edit.
- **O feed de histórico é alimentado por linhas fechadas, e um oráculo que se auto-estampa não prova nada.**
  `_main/live-vs-history-source-oracle.js` injeta `CANONICAL_PRODUCER` no seu próprio arm "canonical path is
  open" — ler o verde como evidência é um erro.
- **`app/package.json` anuncia uma toolchain MORTA** (`electron`, `vite`, `svelte`, `tauri`). O produto não
  tem build nem npm na via viva: `run.cmd` → `sotto_webview.py` → pywebview/WebView2 serve `app/panel/*`
  tal como está. Não correr npm aqui.
- **Não há C++ neste produto**; os 28 fontes nativos estão todos em `_moved/aireplay/` (parked). O único
  statement de compilador é o desse tree: mingw-w64 g++ 15.2.0 em `H:\msys64\mingw64\bin\g++.exe` (sem
  MSVC, sem CUDA toolkit).
- **`app/panel/history-store.js` NÃO está na página servida** — é lido só por oráculos. O escritor real é
  `sotto_webview.py history_append` → `_history_provenance` com a sua própria tupla `HISTORY_ROUTE_SOURCES`
  (gémea da `ROUTE_SOURCES` JS). As duas listas têm de andar juntas.
- **A LEI DO ROUTING desta caixa** (medida, não re-litigar): o loopback é **assimétrico entre APIs** — render
  no `CABLE Input` (MME) + captura no `CABLE Output` (DirectSound) entrega o tom a peak 0.4999; DirectSound→
  DirectSound **não** faz loopback. Sem nada a tocar, TODOS os loopbacks leem silêncio digital, portanto
  **uma corrida ao vivo silenciosa é normalmente comportamento CORRECTO**, e o fix é routing no
  VoiceMeeter/Windows. O worker tem de o dizer alto (exit 3), não sair 0.
- **Há um ChatGPT no terminal e o dono pediu que se use**: `gpt` = `consultgpt`
  (`C:\Program Files\Python311\Scripts\gpt.exe`, browser real, sem API key) —
  `gpt --no-code --session <nome> --prompt-file _main\<p>.txt > _main\<r>.txt 2>&1`, em background (30-60 s).
  Uso e armadilhas em `docs/tools/consultgpt.md`.
- **`_main/*fake*.py` são 5 ficheiros e nenhum é o transcritor real** (ex.: `_armE-fake-worker.py`,
  `_tap-restart-fake-worker.py`). O real mede `peak=0.44`. Citar um fake pelo nome do ficheiro.
- **O TRAVAMENTO DE ABRIR/FECHAR: as quatro causas medidas (2026-10-21, recibo
  `_main/receipt-20261021-open-close-stall.md`).** O dono pediu isto pela vigésima vez.
  (1) **O painel ficava morto 36,9 s** — o worker nascia no momento do painel e o modelo só ficava
  pronto depois (`BRIDGE_LOAD_MS ms=36968 ... worker_load_s=32.59`, log do dono). **Cura: o PRELOAD** —
  o worker nasce 20 s depois do arranque da app, em background, na prioridade BELOW_NORMAL do worker
  (`WORKER_PRELOAD scheduled delay_s=20.0` → `BRIDGE_SPAWNED` 20,0 s depois → `BRIDGE_LOAD_MS
  ms=10657` ⇒ **modelo pronto 30 s depois do arranque, sem o dono tocar em nada**). Opt-out:
  `SOTTO_NO_PRELOAD=1`; uma launch de MEDIÇÃO nunca faz preload. (2) **O Alt+C podia esperar 10 s** —
  `transparency_hack` chamava `ui(form_show)` e `_ui` tem um orçamento de **DEZ SEGUNDOS**
  (`UI_MARSHAL_TIMEOUT_S`), e quem chama é a thread do hotkey ⇒ espera agora limitada
  (`TRANSPARENCY_HACK_WAIT_S=0.25`) **com POST** como alternativa; medido: `HOTKEY_DOUBLE` → `PANEL_SHOWN`
  em **1 ms**. (3) **O fecho gelava a thread do tray 3 s** (`closer.join(3)` para um `destroy`
  cosmético) ⇒ `QUIT_DESTROY_WAIT_S=0.25`; medido: `BRIDGE_STOP` → `SHELL_EXIT` = **0,262 s**.
  (4) **Um worker ÓRFÃO sobrevivia à app** — `os._exit` não mata o filho, e o guard só existia num
  caminho de spawn ⇒ o guard é agora **central** (`start_worker` recusa se a shell está a morrer);
  medido: **zero órfãos**.
- **O LOAD DO MODELO: onde estão os segundos (medido, com fases).** As três sessões do ONNX custam
  **1,74-2,09 s** (encoder 1,56-1,62 s / decoder 0,10-0,31 s / joint 0,07-0,16 s) — o `load_phases_s`
  agora vai no `model-loaded`. O **disco não é o custo** (747 MB a 1,9 GB/s = 0,39 s). O load total
  varia **4,1 s a 49,2 s** conforme a máquina. ⇒ **O A/B das opções do EP CUDA é CONFUNDIDO pela
  ordem**: medido nos dois sentidos, o primeiro braço paga sempre a cache fria (defaults 49,21 s vs
  options 15,02 s; invertido: options 11,43 s vs defaults 7,89 s). Com as fases: 1,738 s (HEURISTIC)
  vs 1,824 s (EXHAUSTIVE) ⇒ **dentro do ruído**. Logo: `cudnn_conv_algo_search` fica no **default do
  ORT**; `arena_extend_strategy=kSameAsRequested` + `gpu_mem_limit` ficam como **guardas**, sem claim de
  velocidade. **A figura de 9,7 GB de VRAM do worker NÃO foi reproduzida** (medido: delta de
  **1175-1703 MiB**) — não a usar como justificação de nada.
- **A MÁQUINA DO DONO ESTÁ DEGRADADA (medido 2026-10-21 18:0x).** I: com **0,4 % livre** (13,8 GB de
  3726 GB), D: 2,1 %, E: 2,3 %, F: 7,4 %, C: 14,6 %, H: 12 %, G: 18,7 %; **722 processos** vivos; RAM
  47,7 GB com 14,4 GB livres (a pressão de memória **não** é o problema). Um arranque de `python` custa
  53-127 ms ⇒ o "o start do que quer que seja dá stutter" tem uma componente de MÁQUINA que o Sotto não
  controla. **Aviso ao dono, não acção**: ele decide o que limpar.
- **ARK-ASR-0.6B NÃO SUBSTITUI NENHUM DOS DOIS MOTORES (medido 2026-10-30 10:4x-10:5x).**
  `Edge0/ark-asr-0.6b-int8-onnx` (1,77 GB) contra os dois do repo, no mesmo wav de 16 kHz:
  **pt-BR 15,0 s** → parakeet-int4 **2,04 s / 7,36× / pico 653 MB** (texto exacto);
  nemotron-int4 (560 ms) **18,20 s / 0,82× / 1232 MB** (pt-BR reconhecível); ARK **24,51 s /
  0,61× / 2478 MB** e **texto EM INGLÊS com erros** ("interdited", "next second Friday") — a lista
  de línguas dele não tem `pt` (19: zh en de ja fr ko es pl it ro hu cs nl fi hr sk sl et lt) e ele
  **traduz** em vez de transcrever. **en-US 8,5 s** → parakeet **1,25 s / 6,83× / 598 MB**; ARK
  **31,25 s / 0,27× / 2358 MB** (texto exacto). Não faz ao vivo (janela de 30 s, autorregressivo).
  Instrumento: `_main/engine-compare.py` (parakeet/nemotron) + o `infer_ark_audio_onnx.py` do autor
  para o ARK. Recibo: `_main/receipt-20261030-ark-asr-vs-parakeet.md`. Corrida em processos
  SEPARADOS: dois clipes no mesmo processo contaminam o segundo (2,41× contra 6,83×).
- **UMA ETIQUETA DE LOG DENTRO DO `try` DESARMOU O SHEDDING POR CARGA (medido 2026-10-30
  10:56:55).** A primeira largada real da cura escreveu
  `LOAD_SHEDDING_START_FAILED error=AttributeError("'LoadSheddingMonitor' object has no attribute
  'armed'")`: a linha `LOAD_SHEDDING_STARTED` lia um atributo que a própria cura tinha RETIRADO e,
  por estar no MESMO `try` do `.start()`, o monitor nunca arrancou — o nível nunca foi publicado.
  Classe: **um diagnóstico não pode ser a causa de a funcionalidade não correr**. O log passou para
  o `else` com o seu próprio `try`, e o oráculo ganhou duas arms que o mutante do bloco anterior
  derruba (medido: rc=1, `armed` RED + log-dentro-do-guard RED).
- **O `run.cmd`/shell ARRANCA COM `LOAD_SHEDDING_STARTED` E SEM `HOTKEY_..._FAILED` (medido
  2026-10-30 10:58:59, pid 43304):** `gesture=taps-1|taps-2|hold hold_ms=200 tap_window_ms=400`.
- **AS TRES DIRECTORIAS DE MODELO DO `worker/models/` ESTAVAM VAZIAS A 2026-11-02 01:26, E SO' UMA SE
  REPOE SOZINHA (medido 2026-11-02):** o directorio estava vazio (mtime 2026-11-01 16:28; o log tem
  `model-loaded` as 16:25:45 e `model dir not found` as 16:28:30). O parakeet ONNX int4 voltou por
  `python _main/fetch-parakeet.py` — `VERDICT GREEN`, encoder 343 841 943 B `ade2c65c`, decoder_joint
  72 552 270 B `97ae0cb0`, preprocessor 1 224 294 B `3de5742f`, vad 18 300 687 B `18dfbe34`,
  `transcribe.py` 17 844 B — e transcreve de verdade: um segmento na fila deu
  "The radio announced that the bridge over the river will be closed next Monday. Residents need an
  alter." O **nemotron ao vivo TAMBEM se repoe** (medido 2026-11-02, correccao da mesma nota):
  `onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4` na revisao `8364d9e2` publica o layout
  ORT GenAI completo — 788 069 519 B em 16 ficheiros, `blank_id=13087`, `chunk_samples=8960`,
  `max_symbols_per_step=10`, `left_context=56`, `decoder.hidden_size=640` — e o motor ao vivo
  transcreve com ele: `rtf 0.479` com CUDA+CPU (pico 809 MB) e `rtf 3.078` so' a CPU (pico 422 MB)
  no clipe de 8,4 s, texto identico nos dois. Reposto por `python _main/fetch-nemotron.py`.
- **O REDUX ONNX AO VIVO FICA EM 0,97x DO TEMPO REAL NESTA MAQUINA (medido 2026-11-02,
  `worker/redux_live.py --wav _main/en-us-sample.wav`, 172 passes):** `mean_compute_s=5.16`
  `max_compute_s=7.29` para `step_s=2.0`/`window_s=5.00`, `overruns=172/172`, `backlog_s` estavel em
  34-38 s, `peak=0.689819`, com 54 % de CPU e 24,4 GB de RAM livres. Nao e' defeito do motor: e' a
  razao medida de a lei da stack pôr o nemotron no AO VIVO e o parakeet no fundo.
- **A EDICAO DA FAIXA ESCONDIA A PROPRIA FAIXA (medido 2026-11-02 12:55:09, corrigido 13:03:33):**
  `PANEL_SHOWN ... 09.307` (`paint_ack wait_ms=156.0`) e `OUTSIDE_CLICK decision=outside closed=true`
  no mesmo instante, `PANEL_HIDDEN` as `09.311`, e `PANEL_EDIT_MODE on=true` as `09.311` — 4 ms tarde
  demais. O guarda do outside-click era armado DEPOIS de `show_panel()`, e o show custa o paint ack.
  Armado ANTES, `_strip-surface-probe` deu GREEN 26/26 e o braço D registou
  `OUTSIDE_CLICK source=probe-edit-outside decision=edit-mode closed=false`.
- **`--max-seconds` E TEMPO DE PAREDE DESDE O ARRANQUE, PORTANTO INCLUI O CARREGAMENTO DO MODELO
  (medido 2026-11-02):** `load_s=38,96` (frio) e 23,09 (quente) contra uma janela de 20 s no ARM3 do
  `device-silence` deu `captions=0` com `blocks=56 peak=0,275 speech_blocks=6` — captou fala e não
  transcreveu nada porque a janela fechou antes do primeiro decode. O oráculo passou a derivar a janela
  do `load_s` da PRÓPRIA corrida (`load_s + max(secs,20) + 10`, uma única repetição).
