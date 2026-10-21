# Sotto — contexto do repo para todo agente e subagente

Transcrição em tempo real de QUALQUER áudio deste PC, mostrada como legendas num overlay global **Alt+C**.
Aceitação do dono, verbatim: *"e eu quero que o alt c mostre as transcricoes em tempo real, de qualquer
audio do meu pc. e legendas."*

> **Este ficheiro foi reduzido ao essencial em 2026-10-21.** O registo histórico completo (1301 linhas,
> 120 232 B) está em **`docs/AGENTS-archive-20261021.md`** — é lá que se procura a proveniência de um
> número antigo, não aqui. Em conflito, vale o arquivo **mais** a re-medição; este ficheiro carrega as
> REGRAS, não a história.

## ORDENS EM VIGOR — 2026-10-21 (quatro, do dono)

### 1. O track da YouTube tem de ser a LÍNGUA ORIGINAL
> *"to vendo que o transcript atual ta sendo traduzido. nao e pra traduzir. e pra ser lingua original.
> quando ingles, e quando pt br. quando chines ou japones, ou qualquer outra, pode traduzir. ah, menos
> espanhol."*

**A REGRA EM VIGOR (revista pelo próprio dono mais tarde no MESMO dia 2026-10-21):**
*"para de traduzir pra pt br do ingles e do espanhol. o resto, traduza para ingles. qualquer
outra lingua pra ingles."* ⇒ **a legenda é INGLÊS para qualquer vídeo**, e **ESPANHOL** para um
vídeo espanhol (o espanhol **nunca** é traduzido). Implementado em
`app/webview/youtube_captions.py`: `TARGET_LANG = 'en'` (`:464`),
`NEVER_TRANSLATED_LANGS = ('es',)` (`:469`), `_target_langs(orig)` (`:472` — vídeo es → es,en;
vídeo en → en; qualquer outro → en, e a **própria língua** como último recurso, para um vídeo sem
faixa de inglês) e `_original_language(info)` (`:500`, o campo `language`, base `en-US` → `en`).
O portão tem **três** mutantes para a política (a língua original não lida, o destino em
português outra vez, o esquecimento da excepção espanhola) ⇒ **uma política que não se pode
quebrar é um comentário.**

**A REGRA ANTERIOR (substituída — fica escrita para ninguém a "arrumar" de volta):** original para
**en, pt-BR, es**; tradução **permitida** para zh/ja/qualquer outra; **espanhol NUNCA traduzido.**
O defeito vivia em `app/webview/youtube_captions.py` (`_auto_lang_keys`), que pedia
`pref` (traduzido, `tlang=`) antes de esgotar as chaves `-orig`.

**MEDIDO 2026-10-21 (a chave do defeito):** no vídeo que o dono estava a ver
(`-LODwSuymII`), `yt-dlp` diz **`language = 'en-US'`** — o vídeo é **INGLÊS** — e a
tabela tem **177 línguas**. A entrada portuguesa **não** é a original: é a
**auto-tradução** do YouTube, e o URL dela **não traz `tlang`** — por isso "a chave
que parece original" **não prova** a língua original. **O campo `language` é que
prová.** O serviço servia a **tradução** de um vídeo inglês (e o dono reclamou
exactamente disso). **A CORRECÇÃO (2026-10-21):** `_original_language(info)` (o campo `language`,
base `en-US` → `en`) + `_target_langs(orig)` (a política acima) → a faixa do **player** só conta
se for **da língua que a política pede** (o "1:1 com o vídeo" é sobre a legenda ser **do vídeo**,
não sobre seguir uma tradução que o player ligou). Portão:
`_main/youtube-captions-oracle.py` → **53/53 arms, 13/13 mutantes** (dois novos: a
língua original não lida, e a política a permitir tudo). **Re-medir antes de citar
linha.**

### 2. O gesto do Alt+C tem de funcionar à velocidade humana
> *"alt c nao ta funcionando direito pra abrir o painel e etc. um alt c: ativa ou desativa legenda ao
> vivo. dois: abre o painel de baixo. tres: abre o painel da direita."*

Contrato: **1** pressão → legenda ao vivo on/off; **2** → painel de baixo (`show_strip`); **3** → painel
da direita (`show_side`). Defeito medido (2026-10-21, `WM_HOTKEY` reais na fila da thread do hotkey, técnica
de `_main/_audit-hotkey-delivery.py`): a 120 ms os gestos 2 e 3 acertam; a **400 ms e 700 ms não fazem
nada** (ou fazem a acção errada). Causa: `HOTKEY_DOUBLE_MS = 250` (`sotto_webview.py` ~`:1403`) governa
DUAS coisas — o atraso da legenda **e** a janela do gesto — e um duplo-clique humano é 300-500 ms.
Correcção: separar `HOTKEY_CAPTION_DEFER_MS` (250) de `HOTKEY_GESTURE_MS` (700) e **DESFAZER** a legenda
quando o gesto se revela um painel (a regra do dono é *"caso double alt c, a legenda nao habilita"*).

**FEITO E MEDIDO (2026-10-21 01:21, shell novo, pid 19624):** os dois relógios estão no
`sotto_webview.py:1441-1442`, o desfazer em `_undo_gesture_caption` (`:7923`), o gesto em `hotkey_pressed`
(`:7789`). **Depois**, no app do dono a correr: 2 pressões a **400 ms** → `HOTKEY_CAPTION_UNDONE` +
`PANEL_SHOWN mode=strip`; 3 pressões a **400 ms** → `HOTKEY_CAPTION_UNDONE` + `PANEL_SHOWN mode=side`.
**Antes** (o mesmo instrumento, o mesmo app): 400 ms → legenda on/off e **nada**; 700 ms → o mesmo.
Recibo: `_main/receipt-20261021-hotkey-gesture.md`. Portões: `hotkey-gesture-oracle.py` 14/14,
`hotkey-cycle-oracle.py` PASS, `hotkey-triple-oracle.py` 30/30 com **9/9 mutantes apanhados** — os três
tinham âncoras gastas pela renomeação da constante (e o do triplo **partia-se** com `IndentationError`),
**re-ancoradas, não afrouxadas**.

### 3. O Parakeet é o segundo pass, com lifecycle inteligente
> *"legenda ao vivo, com o modelo nemotron... qualquer legenda que ja passou (nao é mais ao vivo) tem que
> ser processada tambem pelo parakeet, ou imediatamente, ou com delay, ou quando seguro de fazer isso...
> se minha legenda ao vivo ta desativada e eu nao to usando, é só o parakeet que comanda."*

O mecanismo existe (`worker/redux_batch.py`, `worker/redux_live.py`, flag `--redux-when-hidden`,
`SOTTO_REDUX_LIVE=1` em `app/webview/run.cmd`). **Buraco medido:** `on_external_captions_released()` não
traz o worker de volta (de propósito — abrir/fechar o Sotto trava o PC do dono), logo **depois** de uma
legenda externa não há nem legenda do YouTube nem transcrição do modelo. É isso que esta ordem manda
fechar.

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
**VERDE** (rc=0). Os passos mais lentos são os que **lançam a app**:
`strip-stats-log-budget` 57-61 s, `strip-surface-runtime` 44 s, `tap-open-timeout` 34 s,
`strip-geometry-restore` 30 s, `strip-stats-wave` 26-27 s, `strip-surface-oracle` 21 s.

**O portão do cache** é `_main/_stepcache-oracle.py` (16 braços / 6 mutantes). Dois defeitos
encontrados por ele: a CLI's `record` **não tinha** `--t0` (o `AttributeError` matava o `record`
inteiro ⇒ o cache nunca via a CLI) e o formato da CLI mudou (`elapsed=`). O `.cmd` da bateria é
ainda FRÁGIL (ver §A bateria).

## A LEI DA STACK (decidida pelo dono)
**nemotron streaming = motor AO VIVO, só com o painel aberto. Parakeet Redux = motor GERAL/de fundo**
(batch sobre o áudio acumulado, leve em RAM). *"o nvidia é pro ao vivo, o parakeet redux é pro geral."*
Escolha do motor de fundo pelo **preço em RAM**, não pelo nome: o ONNX int4 do Redux mede **615 MB** de
pico contra **3,90 GB** do ternário, com transcrição byte-idêntica.

## PREMISSAS PROIBIDAS (retiradas pelo dono)
**O Sotto NÃO dá nomes a vozes e ninguém volta a propôr isso.** O objectivo da cadeia de falantes é
**separar o áudio para transcrever cada falante em separado**; *"quem falava quando"* não é o objectivo e
o DER **não** é métrica de aceitação. Verbatim: *"quem falava quando nao é importante, cara... sendo que é
só separar audio pra transcrever cada falante?"*

## HARD RULES para qualquer lane

- **Só o LEAD lança, relança ou mata a app/worker** (instância única, `Local\SottoShell`; o dono está a
  usá-la). Subagente pede o comando exacto no recibo; o Lead executa. Medições que só precisam do shell
  estático usam `--dump-dom` (não mostra janela, não arranca worker).
- **Nunca deixar janela de consola visível.** Lançar python com `pythonw.exe` ou
  `creationflags 0x08000000|0x00000008`. Um censo de janelas corre a cada 60 s e loga `ALERTA-JANELA` com
  o pid. O painel também tem de ficar fora do ecrã sem Alt+C/`--show`.
- **Um filtro de kill nomeia o ARTEFACTO**, nunca uma palavra genérica: `sotto_worker\.py`,
  `sotto_webview\.py`, o caminho do exe webview/electron. Filtrar `sotto` já matou dois processos alheios.
- **Áudio de teste é MUDO.** Qualquer teste que renderize áudio usa `_main/mute-audio.py --mute/--unmute`
  (portão: `_main/mute-audio-oracle.py`, 21/21 arms, 8/8 mutantes). A recusa antiga (comparar com o
  endpoint default e sair rc=4) **continua**; o mute acrescenta-se.
- **`TMPDIR` = `I:\cc-tmp`.** `G:` enche e mata lanes com ENOSPC.
- **Caminhos nativos `H:\`.** `./node_modules/.bin/electron` não executa (rc=127). E não lançar esse
  binário como app: o Electron está MORTO.
- **Pesos e `history/` vivem só em `H:\sotto`** (`worker/models/` e `history/` são git-ignored, estão
  ausentes de qualquer worktree). Testar/medir sempre em `H:\sotto`; "ausente do worktree" nunca é prova
  de ausência.
- **Lanes editam só os seus ficheiros** (mapa de ownership no brief de dispatch).
- **Nunca fazer grep a `AGENTS.md`/ficheiros de contexto** — são auto-carregados.
- **UI em movimento (scroll, render provisório) não se toca sem instrumento:** `PANEL_STATE_PROBE`
  publica `live.scroll` porque `count` não prova posição.

## REGRAS PARA MANTER ESTE FICHEIRO VERDADEIRO (todas custaram trabalho refeito)

1. **"O grep deu ZERO" é uma afirmação com prazo de validade.** Re-correr antes de repetir, e colar os
   números de HOJE.
2. **Nomear a revisão ao citar uma linha.** As lanes editam `worker/sotto_worker.py`,
   `app/webview/sotto_webview.py` e `run.cmd` em paralelo. Dar tamanho, mtime e/ou sha256; tratar toda a
   `file:line` como HINT e re-grep antes de agir.
3. **Ausência precisa de instrumento, não de impressão.** Nomear o instrumento, a cadência e a contagem.
4. **Uma screenshot prova COR, não COORDENADAS.** O Edge headless desta máquina fixa o layout viewport em
   **492 px** em `--screenshot` E `--dump-dom`. Só `sotto_webview.py --dump-dom` (WebView2 real) responde
   "onde"; o seu key `controls` imprime `viewport_w` ao lado de cada número.
5. **O EOL do repo é REGRA, não desejo.** `.gitattributes` é **GERADO** por
   `_main/_make-gitattributes.py --write` a partir do estado medido (CRLF 712 / LF 1510 / MISTO 68 numa
   amostra de 2 296 ficheiros de texto) e verificado por `_main/_gitattributes-verify.py`. **Nunca editar
   à mão: regenerar e re-verificar.**
6. **Um portão que julga FICHEIROS entra na bateria; um portão que LANÇA fica fora e di-lo-á aqui.** Um
   portão novo nasce com o braço negativo **já executado** (`NEG-ARM PASS`, rc=1 por desenho). Um braço
   negativo que não está na bateria é um mutante a que ninguém volta a olhar.
7. **Um portão VERMELHO não é veredicto sobre o produto.** Classificar primeiro: âncora gasta (higiene) vs
   afirmação vermelha (defeito). O runner da segunda bateria separa arms negativos (rc 0/1 por desenho) de
   falhas reais (rc≥2 ou crash).
8. **Uma regra fora da população do instrumento não pode ser apanhada por ele.** O `render protection` do
   painel esteve MORTO no produto com todos os portões verdes, porque (i) o harness jsdom não carregava
   `zip-overlay.css` e (ii) o censo saltava selectores que mencionassem `data-caption-window` — a regra
   errada. A cura: o documento de legenda tem marcador próprio **`data-caption-doc="1"`**. Escrever o que
   o instrumento NÃO carrega e justificar cada selector que ele escusa.

## LAYOUT

| path | o que é |
|---|---|
| `app/webview/run.cmd` | **A APP.** Arranca escondida, **arranca o WORKER**, espera Alt+C. `--no-worker` = só shell, `--show` = painel já, `--with-worker` = alias. `%*` passa intacto; a pré-flight `--check-args` recusa flags inválidas com rc≠0 sem lançar nada. |
| `app/webview/sotto_webview.py` | o shell: WebView2 + pywebview. Auto-start do worker decidido por `_worker_autostart_reason` (5 razões; só `default` arranca). |
| `worker/sotto_worker.py` | captura → chunk → encode → RNNT greedy decode → JSONL no stdout. |
| `worker/config.json` | fonte do `model.dir`, `lang_id`, `use_vad`, providers (todas lidas). |
| `worker/models/` | pesos (git-ignored, só em `H:\sotto`). |
| `app/panel/` | **O PAINEL** (`panel.{html,css,js}` + módulos carregados pelo documento). CSS de temas é **GERADO** — nunca editar à mão. |
| `app/webview/hot_reload.py` | watcher de assets do painel/worker com debounce; recarrega o painel em sítio. |
| `app/_legacy-electron/` | **MORTO.** Não é fallback. |
| `docs/model-specs/` | docs do próprio modelo, verbatim + índice normativo. |
| `_main/` | sondas, oráculos e logs. |
| `docs/shell-contract.md` | contrato do shell (strip, SetWindowPos, hot reload, meter). |
| `docs/AGENTS-archive-20261021.md` | o histórico completo deste ficheiro. |

**PIN do `run.cmd --help` (medido 2026-10-21 01:5x):** re-measured 2026-10-21 the output is 6934 B,
107 lines, 107 CRLF / 0 bare LF, rc 0, sha256
`51B52939F76C4AA5A35D7D865ED7C6B38C01ACFAD829F36C7A6032C337E01B47`. O portão do pin é
`_main/agents-md-pins-oracle.py`: se o `--help` mudar, este número muda, e o gate obriga a re-medir **aqui**.
(O número vai **sem asteriscos**: o braço negativo do portão muta o número com um padrão que exige
`the output is ` seguido dos dígitos — com o `**` do markdown o padrão não pega e o portão perde o
seu braço negativo.)

## ANTES DE TOCAR EM `worker/`
Ler **`docs/model-specs/README.md`** — parâmetros normativos (`blank_id: 13087`,
`max_symbols_per_step: 10`, `chunk_samples: 8960`), contrato de decode, tabela de lang-ids, VAD. **Não
inventar uma convenção de decode** — esse erro já foi cometido uma vez.

## DESVIOS CONHECIDOS DO SPEC (todos corrigidos — ficam como regra)

| o que o modelo diz | o que o código faz hoje |
|---|---|
| lang id fixo | `model.lang_id` = **`"auto"`** (101). `"os"` é aceite mas perigoso (destruiu uma língua em cada direcção). Precedência `--lang-id` > `SOTTO_LANG_ID` > config; id não declarado **recusa ruidosamente (exit 2)**, nunca é clampado. |
| VAD opcional | `use_vad: true` está LIGADO e não é inerte: um chunk de silêncio faz `process()` devolver `None` (10 de 12 chunks gated). |
| int4 no config | config selecciona `...-int8` (`left_context: 70`); custo medido vs int4 = +268 MB RSS. |
| um device que abre e não ouve nada sai 0 | agora `state="silent-device"`, verdict próprio, **exit 3**; e `ran_but_silent` é testado PRIMEIRO, logo `done.verdict == "silent-device"` iff `exit == 3`. |
| `--audio` precisa de `--selftest` | **falso hoje**: `--audio X` sozinho transcreve X. |

## FACTOS MEDIDOS QUE NÃO SE RE-LITIGAM

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

## OUTPUT GRANDE — TRUNCAMENTO E O BYPASS DELIBERADO (2026-10-21)

O output de uma tool call é cortado antes de entrar no contexto. O limite vem de `tool_output` na config
activa (`G:\env-data\opencode-go-pool.json`): **`max_lines: 600`, `max_bytes: 24576`** (24 KB) — o
mecanismo é nativo (`packages/opencode/src/tool/truncate.ts`, lido por `shell`, `read`, `grep` e tools de
plugin) e não há flag por chamada.

**Três formas de não perder o que interessa:**

1. **Nativo, sempre ligado:** o output completo é escrito em disco e o texto cortado traz
   `Full output saved to: <ficheiro>`. Lê-se com `read` (`offset`/`limit`) ou `grep` sobre esse ficheiro.
   **Preferir isto** para um dump grande de que só se querem umas linhas.
2. **Bypass pedido, por chamada:** o token **`__notrunc__`** em qualquer parte dos argumentos (na prática,
   um comentário na linha de comando: `... | Select-Object -First 40  # __notrunc__`) faz o plugin
   re-expandir o output completo.
3. **Bypass global:** `OPENCODE_NO_TRUNCATE=1` no ambiente do servidor vale para todas as chamadas.

O tecto da re-expansão é **512 KB** (`OPENCODE_NO_TRUNCATE_MAX`), e acima disso o corte fica com uma nota a
dizer onde está o ficheiro: um bypass que anula o limite por completo é a mesma avaria que o limite existe
para evitar. O plugin é `~/.config/opencode/plugins/no-truncate.ts`, composto com o ECC em `index.ts`
(um entrypoint por plugin ⇒ o `default` encadeia os dois hooks `tool.execute.after`). Verificado por seis
braços em `I:\cc-tmp\no-truncate-check.ts`: sem marcador nada muda, com marcador e com env re-expande,
output não truncado é intocado, tecto excedido mantém o corte e nomeia o ficheiro, ficheiro ilegível não
rebenta. **Muda a config/plugin ⇒ reiniciar o serviço** (o `Config` é cacheado com `Duration.infinity`).

## A BATERIA

- Duas: **`_main\_audit-verify-all.cmd`** (principal) e **`instruments-battery.mjs`** (segunda; o header
  diz `Launches NOTHING`).
- **PIN do ficheiro (medido 2026-10-21 18:4x):** `_main\_audit-verify-all.cmd` = **84979 B**,
  **1165 CRLF** / 0 bare LF, sha256 `713F1BE8D066B2DC9FF188ABA0AE96B174D58B1C96E2E4C7377B63F65F1B48F4`.
  (Era 84305 B / 1156 CRLF; cresceu com o **portão do open/close**, com o
  **modo rápido/incremental** e com o **`fast-skip` nos passos skip-capable**.) O portão do pin é
  `_main/agents-md-pins-oracle.py` — se o `.cmd` mudar, o número muda, e o gate
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
  (As âncoras gastas desta vez: `panel2-dom-probe` contava as linhas no **documento inteiro** e
  a **sonda do brand** (`panel.html:1288`) traz uma linha `caption--provisional` — re-ancorado ao
  **listo do strip**; e `stepcache-oracle` apanhou que a CLI's `record` não tinha `--t0`.)
- **Os três portões do hotkey ESTÃO na bateria desde 2026-10-21** — `hotkey-cycle`,
  `hotkey-gesture`, `hotkey-triple` (eram os que **não** estavam, e é assim que um portão apodrece em
  silêncio). Entraram com a ORDEM n.º 2 fechada. Entrou também o do **wrap nativo**
  (`caption-native-wrap`), que julga a legenda que o dono VÊ (a nativa, não o `caption.html`).
- **O portão do OPEN/CLOSE entrou em 2026-10-21** — `open-close-stall` + o braço
  `red-as-expected-open-close-stall` (5 mutantes, rc=1 por desenho). Julga **FICHEIROS** (5 factos
  estruturais, por AST ⇒ nada de launches ⇒ entra na bateria). **Os DOIS PROBES que lançam processos
  ficam FORA da bateria** (`_main/_cuda-vram-footprint-probe.py` e `_main/_exit-latency-probe.py`) e é
  dito aqui: medem a VRAM/o load e a latência da saída.

## POR MEDIR / NÃO ATRIBUÍDO (declarado, não esquecido)

- Que o mute tape *todos* os caminhos até aos ouvidos: o recibo de 2026-10-07 mediu som real na sala
  (mic 0,24–0,77) por um caminho não identificado. Medir isso exige renderizar áudio.
- Se o `emit_async` (um post pendente por canal) impede um freeze a sério: nenhum lançamento foi permitido
  na altura, e a profundidade da fila nunca foi instrumentada. A causa do freeze continua **não atribuída**.
- Que o hot reload do painel (staging bounce) funcione: o mecanismo está lido e verificado por leitura, a
  prova de máquina (`panel.url = file://…/panel.html` + `live.count >= 0`) não foi corrida desde a cura.
- O que o WebView2 real pinta de `source=proc:<pid>` ponta-a-ponta; e DUAS apps ao mesmo tempo são
  impossíveis por construção (um bridge, um worker, um valor de `--app-target`).
- A contradição do flash de painel no arranque (§Factos).

## COMO APROFUNDAR
`docs/AGENTS-archive-20261021.md` (a história completa, com os números verbatim) ·
`docs/shell-contract.md` · `docs/model-specs/README.md` · `docs/audit/` · `_main/receipt-*.md`
(cada correcção traz o seu recibo: instrumento, braço negativo, pin).
