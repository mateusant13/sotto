# Dispatch End-to-End — Auditoria de Design & Features do Sotto (2026-11-25)

**Origem:** Auditoria completa de design e features do Sotto solicitada pelo dono em 2026-11-25.
**Modo de execução obrigatório (ordem do dono):**
1. Manter `todo` viva durante toda a execução (`AGENTS.md`).
2. Executar **em paralelo com até 10 subagents** (ownership estrito por arquivo/slice; sem dois subagents editando o mesmo arquivo ao mesmo tempo; quando dois slices tocarem `sotto_webview.py` ou `sotto_worker.py`, serializar ou usar worktrees isolados com merge ordenado).
3. Após a implementação de cada onda, despachar **10 reviewers independentes** (verificador ≠ autor, 1 por slice) para auditar diff, contratos, oráculos e `--neg-arm`.
4. **Regras duras da casa (`AGENTS.md`):**
   - `ASSUME THIS MACHINE IS 10x WEAKER THAN IT IS`: **1 trabalho pesado de cada vez** com lease em `I:\!manager\tools\performance-gate.py` e caged (`python -m watcher run --cpu 40 -- ...`).
   - `SOTTO_NEVER_ON_OWNER_SCREEN`: nunca abrir janela/popup na tela do dono.
   - Nunca tocar no áudio do dono (`SetMute`/`SetVolume`/default endpoint).
   - Nunca criar/focar/mover/fechar panes no Herdr.
   - Todo oráculo novo/alterado nasce com `--neg-arm` (mutante vermelho).
   - Ao final, re-medir e atualizar os pins do `AGENTS.md` (`_main/agents-md-pins-oracle.py`).

---

## Os 10 Slices de Implementação (até 10 subagents em paralelo)

### Slice 1 — `mic_tap` em todos os modos de captura (ProcessLoopback + PortAudio)
- **Problema medido:** Em `worker/sotto_worker.py:4962-4971`, `mic_tap.open_stream` só envolve `WasapiLoopbackTap` (Rung A). Ao usar `--app-target Discord.exe` (`ProcessLoopbackTap`, Rung P) ou `_PortAudioTap` (Rung B/C), o microfone do dono deixa de ser capturado.
- **Escopo:** Estender o acoplamento de `mic_tap.open_stream` (respeitando `SOTTO_MIC=0` e fallback silencioso quando não há mic) para `ProcessLoopbackTap` e `_PortAudioTap`.
- **Prova:** Adicionar braços com fakes (sem abrir dispositivo real) + `--neg-arm` no oráculo correspondente.

### Slice 2 — Ressuscitar `worker/punctuation_model.py` (remover morte por guard GPU-only)
- **Problema medido:** `worker/punctuation_model.py:74-77` fixa `_NATIVE_GPU_PLACEMENT_VERIFIED = False` porque `sherpa-onnx` não expõe API de atestação GPU-only — exatamente o mesmo bloqueio que havia matado `speaker_sidecar.py` até 2026-11-24. O modelo int8 (7,1 MB, 91 ms load, 6,8 ms/linha em CPU) fica 100% morto em runtime.
- **Escopo:** Permitir execução explícita em CPU (`provider="cpu"`) com teto de threads declarado (mesmo padrão do `speaker_sidecar.py`), mantendo a guarda estrita de língua `en`-only (nunca aplicar em `pt`) e fail-closed para identidade quando modelo ausente ou `SOTTO_PUNCT_MODEL=0`.
- **Prova:** Oráculo positivo + `--neg-arm` (mutante que remove guarda `en`-only ou quebra fail-closed).

### Slice 3 — Corrigir `worker/config.json` (`audio.device` + `use_denoise`) e destino de `qwen_summary.py`
- **Problema medido:**
  1. `worker/config.json:4` ainda tem `"device": "CABLE Input (VB-Audio Virtual Cable)"` hardcoded, contrariando o próprio `_comment` `"DELIBERATELY EMPTY"` na linha 6.
  2. `worker/config.json:2,29` anuncia `use_denoise` como ligado em `StreamAsr.run_chunk`, mas `worker/sotto_worker.py` tem **0 referências** a `denoise` (`worker/denoise.py` é 100% inerte).
  3. `worker/qwen_summary.py` (84 KB) tem **0 referências** em `sotto_worker.py` e `sotto_webview.py` (só citada em `hot_reload.py`).
- **Escopo:**
  - Limpar `audio.device` para `""` em `worker/config.json`.
  - Ligar `use_denoise` de verdade em `StreamAsr.run_chunk` quando `use_denoise: true` (mantendo `false` por padrão e byte-idêntico quando `false`) **OU** remover a chave e `worker/denoise.py` se não agregar valor real — documentando e provando a escolha.
  - Remover/arquivar `worker/qwen_summary.py` se não houver consumidor real e limpar referências órfãs em `app/webview/hot_reload.py`.
- **Prova:** Teste unitário/oráculo com `--neg-arm` cobrindo `config.json` e o caminho escolhido.

### Slice 4 — Remover trabalho DOM morto de `caption-float.js` / `letter-swap.js` no painel
- **Problema medido:** `panel.js:3762` declara que a legenda real na tela é `NativeCaptionOverlay` (`caption_overlay.py`), mas `app/panel/panel.html` ainda carrega `caption-float.css` (17 KB), `caption-float.js` (20 KB) e `letter-swap.js` (19 KB), e `panel.js:1464-1466` ainda chama `window.SottoCaptionFloat.push(...)` em toda palavra provisória.
- **Escopo:** Remover o carregamento e o push redundante de `caption-float` / `letter-swap` no fluxo principal do painel quando o overlay nativo é o dono (preservando compatibilidade com eventuais probes que testem o painel isolado, ou atualizando-os explicitamente).
- **Prova:** Oráculos de painel (`panel-row-identity-oracle.js`, etc.) verdes + confirmação de 0 chamadas redundantes em modo nativo.

### Slice 5 — Unificar idioma da interface (PT-BR consistente no Tray e no Painel)
- **Problema medido:** `TrayIcon._build_menu` (`app/webview/sotto_webview.py:10923-10951`) mistura inglês e português no mesmo menu (`Open panel`, `Desativar atalho Alt+C`, `Desligar legendas (Ctrl+Space)`, `Edit caption position`, `Quit Sotto`). `app/panel/panel.html` também mistura (`Hide`, `Open the full panel` vs `Traduzir para:`, `Fundo da legenda:`, `Esconder a legenda`).
- **Escopo:** Padronizar 100% em PT-BR (ou manter mapeamento explícito onde algum oráculo como `tray-quit-probe.py` busca texto literal, atualizando o oráculo em conjunto no mesmo commit).
- **Prova:** `tray-menu-oracle.py` + `--neg-arm` verdes.

### Slice 6 — Eliminar captura duplicada de áudio entre Worker e SpeakerSidecar
- **Problema medido:** `worker/sotto_worker.py` e `worker/speaker_sidecar.py` abrem cada um o seu próprio `WasapiLoopbackTap` + `mic_tap` independentemente (2 loopbacks + 2 mics simultâneos, risco de divergência de endpoint e 2x custo de captura/mix).
- **Escopo:** Fazer o `worker` compartilhar o stream PCM 16 kHz mono já capturado/mixado com o `speaker_sidecar` (via pipe/ring/arquivo temporário em memória/socket local com teto de buffer e drop contado), mantendo fallback standalone no sidecar apenas para execução direta em CLI/testes.
- **Prova:** `speaker-sidecar-oracle.py` + `sidecar-wiring-oracle.py` + `--neg-arm` verdes, comprovando 1 única abertura de loopback+mic em execução conjunta.

### Slice 7 — Tirar defaults reais do produto de `run.cmd` e consolidar na camada de config/shell
- **Problema medido:** `worker/config.json:32` diz `redux_live.enabled: false`, mas `app/webview/run.cmd:113,140` liga `SOTTO_REDUX_LIVE=1` e `SOTTO_REDUX_WHEN_HIDDEN=1` por contorno ao `app-target-oracle.py`. Rodar `sotto_webview.py` direto muda os defaults do produto.
- **Escopo:** Definir os defaults oficiais num único dono (config/worker/shell), manter override explícito via env (`0`/`1`), alinhar `run.cmd` para não ser uma segunda tabela secreta de defaults, e atualizar `app-target-oracle.py` se necessário mantendo a proteção contra vazamento de variáveis indevidas.
- **Prova:** `app-target-oracle.py` + `load-shedding-oracle.py` + `--neg-arm` verdes.

### Slice 8 — Suporte a multi-monitor na abertura do strip (`Alt+C`)
- **Problema medido:** `docs/shell-contract.md:145-150`: `primary_display()` usa `MonitorFromPoint(POINT(0,0))`, fazendo o strip abrir sempre no monitor primário e nunca no monitor onde o cursor está.
- **Escopo:** Criar função pura de seleção de monitor pelo ponto do cursor (`GetCursorPos` → `MonitorFromPoint(..., MONITOR_DEFAULTTONEAREST)` → fallback primário) para posicionar o strip/overlay no monitor ativo do usuário, com clamping de geometria na work area daquele monitor.
- **Prova:** Oráculo puro com geometrias multi-monitor simuladas (monitor esquerdo negativo, secundário à direita, DPI diferente) + `--neg-arm`.

### Slice 9 — Limpeza segura de código morto, shells abandonadas e resíduos na raiz
- **Problema medido:** Existem 3 gerações mortas e resíduos poluindo o repo:
  - `worker/_prefix_audioflag.py` (236 KB), `worker/_sotto_worker_agcinert.py` (128 KB)
  - `worker/parakeet_ultra.py` (37 KB), `worker/ultra_export.py` (20 KB) — modelo rejeitado
  - `worker/unified_asr.py` (21 KB), `worker/unified_fixtures.py` (6 KB) — 0 referências
  - `app/panel/history-store.js`, `history-context-store.js`, `history-gallery.js` (não carregados por `panel.html`)
  - `app/_legacy-electron/` (78 arquivos), `app/src-tauri/`, `app/src/`, `app/svelte.config.js`, `app/vite.config.ts`
  - Resíduos na raiz: `--neg-arm.log`, `.jsonl`, `probe_*.py`, `probe_*_raw.json`, `test*.js`, `simple_test.js`
- **Escopo:** Antes de remover cada item, verificar `grep` de referências em `app/`, `worker/` e `_main/` (oráculos/bateria). Remover apenas o que está provadamente morto/sem consumidor (ou atualizar oráculos obsoletos) e registrar o antes/depois de disco com `artifact-census.py`.
- **Prova:** Bateria/oráculos afetados verdes + 0 imports quebrados.

### Slice 10 — Sincronizar contratos, docs e pins (`AGENTS.md`, `docs/`, `run.cmd`, `Sotto.cmd`, `INTENCAO.md`)
- **Problema medido:** 4 contratos contraditórios de `Alt+C` (`AGENTS.md`, `docs/hotkey-gestos.md`, `run.cmd`, `Sotto.cmd` vs `hotkey_gesture.py` real); `AGENTS.md` Ordem 3 ainda cita 4 guardas + piso de 45 s já removidos; `AGENTS.md` Ordem 5 afirma "nenhum hook global" omitindo a exceção `space_swallow.py`; `AGENTS.md` proíbe "quem falou quando" mas `speaker_sidecar.py` faz diarização e não separação; `INTENCAO.md` está parado em 2026-10-23.
- **Escopo:** Atualizar todas essas fontes para refletir 100% o comportamento real pós-Slices 1–9, sem perder nenhuma regra ativa do dono, e re-medir/atualizar os SHA256 pins de `AGENTS.md` (`run.cmd --help` e `_audit-verify-all.cmd`).
- **Prova:** `_main/agents-md-pins-oracle.py` verde + `gitattributes-verify` verde.

---

## Fase de Revisão Obrigatória — 10 Reviewers Independentes

Após os 10 slices concluírem, despachar **10 reviewers independentes** (verificador ≠ autor, 1 reviewer dedicado por slice, usando o roteamento de modelos de `.agents/skills/task-resolver/references/model-routing.md` — rotas gratuitas primeiro, depois fallback pago conforme regra do dono):

- **Reviewer 1 → Slice 1 (`mic_tap`)**
- **Reviewer 2 → Slice 2 (`punctuation_model`)**
- **Reviewer 3 → Slice 3 (`config.json` / `denoise` / `qwen_summary`)**
- **Reviewer 4 → Slice 4 (`caption-float` / `panel.html` / `panel.js`)**
- **Reviewer 5 → Slice 5 (UI PT-BR Tray + Panel)**
- **Reviewer 6 → Slice 6 (Captura única Worker → Sidecar)**
- **Reviewer 7 → Slice 7 (Defaults `run.cmd` vs config/bridge)**
- **Reviewer 8 → Slice 8 (Multi-monitor strip)**
- **Reviewer 9 → Slice 9 (Limpeza de código morto e shells antigas)**
- **Reviewer 10 → Slice 10 (Docs, `AGENTS.md`, pins e coerência final)**

**Critério de aceite de cada reviewer:**
1. Diff mínimo, limpo e sem regressão em arquivos fora do ownership.
2. Oráculo positivo PASS + `--neg-arm` RED-as-expected (provando que o detector pega regressão).
3. Zero violação das hard rules (`SOTTO_NEVER_ON_OWNER_SCREEN`, zero console popup, zero toque no áudio do dono, teto de threads/CPU respeitado).
4. Se algum reviewer encontrar defeito real, corrigir e re-verificar antes de declarar concluído.

---

## Registo do assento — defeitos dos reviewers, corrigidos e re-verificados (2026-11-25)

Cada linha nomeia o defeito, o sitio, a cura e a prova COLADA que a fecha. Nada aqui ficou
para a proxima lane.

| reviewer | defeito (BLOCKER) | sitio | cura | prova |
|---|---|---|---|---|
| R1 | a mixagem congelava `primary.rate` no `attach()`; o `ProcessLoopbackTap` declara 48 kHz PROVISORIO e o braco de 44,1 kHz realmente existe -> 4 410 amostras saiam como 1 470 (erro de 8 % no rung que este slice acabou de ligar) | `worker/mic_tap.py` `_src_rate()` | taxa lida NO CALLBACK, de `self.primary.rate` | `speaker-sidecar-oracle` `arms 142/142 mutants 21/21`; braco novo "a primary that settles 44.1 kHz in start() is resampled at THAT rate"; mutante `a-48k-primary-is-treated-as-16k` GREEN |
| R1 | `SOTTO_MIC=00` caia para LIGADO (interruptor de privacidade adivinhava) | `worker/mic_tap.py` `open_stream` | lista de LIGAR explicita (`1|on|true|yes|en`, vazio) | braco "every off-looking value (including `00`) keeps the microphone CLOSED" + mutante `sotto-mic-zero-ignored` |
| R1 | microfone aberto antes do primary; um primary que rebenta deixava um stream vivo por rung | `worker/mic_tap.py` `open_stream` | `try/except BaseException` fecha o mic e re-levanta | braco "a primary that fails to open closes the microphone it already opened" + mutante `a-failed-primary-leaks-the-microphone` |
| R6 | um estranho que liga e fica calado EXPULSAVA o sidecar da slot (qualquer processo local forçava o segundo par de dispositivos) | `worker/capture_share.py` `_accept_loop` | so o portador do slot o liberta; o estranho leva `BUSY` e e' fechado | braco `g a stranger cannot eject the slot holder` + mutante `stranger-ejects-slot` |
| R6 (achado do assento, medido 4/8 corridas) | um `stop()` ordenado chegava ao leitor como EOF e era anunciado `publisher-closed`, e o sidecar abria um SEGUNDO tap local ao desligar | `worker/capture_share.py` `Client._read_loop` | EOF so' e' falha quando `_stop` nao foi pedido | braco `h an orderly stop is not a failure` + mutante `orderly-stop-looks-like-crash`; `capture-share-oracle` `PASS (8/8 arms)` / `NEG ARM VERDICT: PASS (8/8 mutants caught, 0 decorative)` |
| R8 | DIP com extensao 0 (1 px fisico a 400 %), `primary_index` ignorado, `shcore` recarregado por chamada no caminho da legenda | `app/webview/sotto_webview.py` | `max(1, round(...))` na extensao; `primary_index` honrado quando nao ha ponto; `_shcore()` carregada uma vez | `multi-monitor-oracle` `PASS -- 6 arm(s), 30 check(s)` / `CONTROL PASS -- all 11 mutants reddened their own arm` (inclui mutantes do clamp de altura e da conversao DIP) |
| R4 | `caption-independent-oracle` A18 ainda exigia o produtor `SottoCaptionFloat.push` que este trabalho apagou; B3 era verde falso sobre um rotulo que o JS repinta em ingles | `_main/caption-independent-oracle.js`, `app/panel/panel.js` | A18 rebaselinado para o que embarca; o rotulo passa a PT-BR e o gate julga o valor RUNTIME | entregue a `S5bPanelRuntime` com as linhas dos gates |
| R5 | ~40 textos user-visible escritos em ingles pelo `panel.js` por cima do `panel.html` PT-BR (metade do ecra traduzida) | `app/panel/panel.js`, `app/panel/theme-switcher.js` | traducao no sitio da escrita + oraculo de runtime jsdom | entregue a `S5bPanelRuntime` |
| R7 | braco `j` cobria so o caminho LIVE; `fake_root` sem uso | `_main/app-target-oracle.py`, `_main/load-shedding-oracle.py` | M4 + sonda em processo filho; caminho falso apagado | `app-target-oracle` `PASS live=GREEN(10/10) M1..M3 RED M4 RED-as-expected`; `load-shedding-oracle` `arms=257 pass=257 fail=0` |

**Bateria:** os quatro oraculos novos entram como par `step` + `red-as-expected`
(`config-truth`, `capture-share`, `punctuation`, `multi-monitor`), e tres deles passaram a sair com
`rc=1` quando o controlo apanha todos os mutantes (convencao `:expectred`; medido `multi=1 punct=1
capture=1`, e `0` no sentido positivo). O pin de `_main/_audit-verify-all.cmd` em `AGENTS.md` foi
re-medido: **424056 B, 4847 CRLF, 0 bare LF**, sha256
`84F93C5F3D18DC531655825347574BE18578E4732C5D47AB919D5E437740B018` (`agents-md-pins-oracle` PASS).
