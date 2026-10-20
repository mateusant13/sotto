# As 23 vermelhas da 2a bateria — classificadas: VELHA ou DEFEITO REAL

**Data:** 2026-10-20
**Lane:** a 2a bateria (`_main/instruments-battery.mjs`, 145 instrumentos, `launches=0`, in-process)
**Pergunta:** cada uma das 23 vermelhas e' um **instrumento velho** (ancora / mutante / pressuposto que ficou para tras) ou um **defeito real do produto**?
**Resposta curta: 23 VELHAS, 0 defeitos reais do produto.** Duas delas escondem um defeito real **de instrumento** (ver §3), que nao e' do produto mas impede dois portoes de dizer a verdade.

---

## 1. A CONTA

| | entradas | instrumentos distintos |
|---|---|---|
| vermelhas na 2a bateria | **23** | **16** |
| ... classificadas **(a) VELHA** | **23** | 16 |
| ... classificadas **(b) DEFEITO REAL DO PRODUTO** | **0** | 0 |
| das 23 VELHAS: em instrumentos que **me pertencem** (correccao a fazer) | 22 | 15 |
| das 23 VELHAS: em instrumento **do Lead** (so reportar) | 1 | 1 (`_main/panel-hidden-at-startup-oracle.py`) |

Detalhe do que "VELHA" quer dizer aqui: **o portao esta vermelho porque mede um contrato, uma ancora ou um pressuposto que o produto ja nao tem** — nao porque o produto esteja errado. Em 4 dos 15 instrumentos que me tocam, o vermelho e' um **CRASH do proprio instrumento** (o scaffolding ficou para tras de uma mudanca do produto), que e' a forma mais barata de vermelho: nao mede nada.

---

## 2. COMO FOI MEDIDO (para se poder refazer)

* Bateria: `node _main/instruments-battery.mjs`, com `$env:TMPDIR='I:\cc-tmp'`, `$env:SOTTO_SKIP_RUN_ALL='1'`, `PYTHONIOENCODING=utf-8`.
  Log integral: `I:\cc-tmp\battery-baseline.txt`. Veredicto do runner:
  `SUMMARY: 122/145 instrument(s) OK ...; failed=23; launches=0` (rc=1, porque ha vermelhos).
  Medido no commit **9041daa**. **NAO MEDIDO:** a MESMA contagem depois dos commits do Lead
  (`0466f1b`, `a3c4cd0`), que tocaram `_main/_audit-verify-all.cmd`,
  `_main/panel-hidden-at-startup-oracle.py` e o censo — nao a lista do runner
  (`_main/instruments-battery.mjs:124` continua a listar o `panel-hidden-at-startup-oracle.py`).
* As 23 foram **reproduzidas uma a uma**, isoladas, com `$env:TMPDIR` proprio
  (`I:\cc-tmp\diag1..diag16`), para ler o que cada uma imprime.
* **Processos:** antes e depois da bateria corridos havia **exactamente** `pythonw.exe` pid 39208
  (`sotto_webview.py --log I:\cc-tmp\sotto-054348.log --show`) e `python.exe` pid 7020
  (`worker/sotto_worker.py`) — **iguais antes e depois, zero processos novos**. Nada foi
  lançado (nem shell, nem worker, nem browser), nada de áudio foi renderizado.
* **Nao houve** correccao de produto: nada em `app/webview/`, `app/panel/` ou `worker/` foi tocado.

---

## 3. A TABELA — as 23, uma por uma

Legenda da classe: **(a) VELHA** = a ancora/medida/pressuposto do instrumento ja nao bate com o
codigo de hoje; **(b) DEFEITO REAL** = o produto esta errado.

| # | label da bateria | ficheiro | classe | a prova (ficheiro:linha + texto) | o que a correccao exige |
|---|---|---|---|---|---|
| 1 | `canonical-producer 47/47` | `_main/canonical-producer-oracle.py` | **(a) VELHA** | `:468` `weights = [p for p in (REDUX_MODEL_DIR, REDUX_MODEL_DIR_INT4) if p.is_dir()]` / `:471` condicao `checkpoint_present is False` — mas `:75` `REDUX_MODEL_DIR_INT4 = .../parakeet-redux-onnx-int4` **existe em disco**, logo `checkpoint_present` e' True e o check vai vermelho. O proprio detalhe do check (`:472`) imprime `default=...parakeet-redux-ternary exists=False` — ou seja, **o gap que o rotulo descreve continua real**; o que envelheceu foi a condicao, que mede a **uniao** de dois directorios. | Medir so o checkpoint **que o runner usa por omissao**: `worker/redux_batch.py:39` `DEFAULT_MODEL_DIR = HERE/"models"/"parakeet-redux-ternary"` (que **nao existe**). O `onnx-int4` e' o engine *live* (`worker/sotto_worker.py:3635` `REDUX_LIVE_ONNX_RELPATH`), nao o default do runner. |
| 2 | `neg-arm-falsifiability` | `_main/audit-rows-negative-arm-falsifiability.py` | **(a) VELHA** — e ver §4 (defeito de instrumento) | `:146` `cannot_say_no = not (neg['rc'] == 0 and blind['rc'] != 0)` — codifica a convencao **antes** de 2026-10-11. O proprio `_main/model-spec-oracle.py:22-24` documenta a convencao actual: `--neg-arm 1 = PASS BY DESIGN ... 0 = a mutant was NOT caught`. Medido hoje: `neg_arm_rc=1` (apanhou a deriva) **e** `blinded_neg_arm_rc=1` (nao apanhou) — **iguais**, porque `_main/model-spec-oracle.py:150` devolve `EXIT_FAIL` (=1, `:41`) tambem no caso "nao apanhou". | (i) `_main/model-spec-oracle.py:150` passar a devolver **0** quando um mutante nao e' apanhado (cumprir o contrato que ele proprio escreve nas linhas 20-24); (ii) a linha `:146` do falsifiability passa a ler a convencao actual (apanhou=1, nao apanhou=0). |
| 3 | `visibility-guard (rows #60/#61)` | `_main/panel-visibility-guard-oracle.py` | **(a) VELHA** (CRASH) | `AttributeError: 'Probe' object has no attribute '_blank_caption_window'`. A classe `Probe` (`:76-118`) tem `show_caption_window` (`:110`) mas **nao** `_blank_caption_window`. O produto trocou: `app/webview/sotto_webview.py:7726` `self._blank_caption_window('panel-hidden')` (dentro de `hide_panel`), def em `:8597`. | Acrescentar o stub `_blank_caption_window` ao `Probe` (o registo e' o mesmo que o do `show_caption_window`: "o efeito e' do shell, nao daqui"). |
| 4 | `visibility-guard neg` | o mesmo | **(a) VELHA** (CRASH) | idem #3 | idem #3 — o neg-arm nao chega a correr porque o braço morre primeiro. |
| 5 | `ladder-rescan (row F15)` | `_main/device-ladder-rescan-oracle.py` | **(a) VELHA** (CRASH) | `NameError: name 'is_bluetooth_audio_device' is not defined`. `build_namespace` (`:130-140`) so extrai dois helpers: `:132` `for helper in ("heuristic_loopback_score", "is_soundmapper_pseudo")`. O worker chama um terceiro: `worker/sotto_worker.py:1284` `if is_bluetooth_audio_device(d["name"]):` (def `:192`). | Acrescentar `is_bluetooth_audio_device` (e `is_bluetooth_audio_device_in`, `:243`, se a ladder o usar) a tupla de extracao de `:132`. |
| 6 | `ladder-rescan neg` | o mesmo | **(a) VELHA** (CRASH) | idem #5 | idem #5. |
| 7 | `verify-all starts nothing (precondition for running it)` | `_main/verify-all-launch-audit.py` | **(a) VELHA** (falso positivo) | Medido hoje: `VERDICT: FAIL -- 84 step(s) read; 1 carry a launcher signature outside the safe-uses list.` / `launches: agents-md-pins (line 402)`. A linha=`_main/_audit-verify-all.cmd:402` e' `call :step agents-md-pins 0 "_main\agents-md-pins-oracle.py;app\webview\run.cmd;..." "%OUT%\agents-md-pins.log" python _main\agents-md-pins-oracle.py` — o `run.cmd` esta no **terceiro argumento (as DEPS)**, e o **comando** (5o em diante) e' `python _main\agents-md-pins-oracle.py`, que so le o ficheiro e responde `--help`. A auditoria classifica a **linha inteira** (`:64-69`), logo acusa uma dependencia como se fosse um comando. | Na **auditoria** (o `.cmd` e' do Lead e nao se toca): separar o comando das DEPS antes de procurar a assinatura de launcher. Nao ha nada a corrigir no `.cmd` — nenhum passo arranca o shell. |
| 8 | `handler-map (the 2.5 h outage)` | `_main/bridge-handler-map-oracle.py` | **(a) VELHA** | `FAIL and the shipped table holds the page vocabulary (25 kind(s)) -- missing=[] extra=['beginWindowDrag','pause','setLiveEnabled','sotto:beginWindowDrag','sotto:pause','sotto:setLiveEnabled']`. O pin `EXPECTED_KINDS` (`:52-59`) tem 25 entradas e nao conhece os 3 handlers novos. O produto tem-nos: `app/webview/sotto_webview.py:5307` `'beginWindowDrag': ('shell','_begin_window_drag')`, `:5312` `'setLiveEnabled'`, `:5315` `'pause'` (+ as variantes `sotto:`), e o preload posta-os em `:4561`/`:4571`/`:4581`. `missing=[]` — **o produto nao perdeu nenhum kind**; o pin e' que esta para tras. | Acrescentar as 6 entradas a `EXPECTED_KINDS` (o proprio check continua a poder dizer NAO: e' a lista que o `--neg-arm` M1 M2 M3 manipulam). |
| 9 | `handler-map neg` | o mesmo | **(a) VELHA** | `VERDICT: FAIL -- 9 check(s), 1 fail` — o control falha logo no primeiro check, pela mesma razao. | idem #8. |
| 10 | `hotkey cycle strip->side->hide` | `_main/hotkey-cycle-oracle.py` | **(a) VELHA** (contrato **retirado**) | Medido hoje: `arm_cycle` falha 6 checks (`panel_mode after 6 presses = ['strip','strip','side','side','side','side'], expected ['strip','side','side','strip','side','side']`), `arm_no_clock` falha 3 (`hotkey_pressed() reads a clock (monotonic) at line 7806`; `reads self._last_hotkey_press at line 7815` / `7844`), `arm_toggle` falha 1. O oraculo mede um ciclo de **3 estados, sem relogio**; o produto tem hoje o **gesto 1/2/3** com janela de duplo toque: `app/webview/sotto_webview.py:7772-7850` (docstring: *"THIS REPLACES the three-state cycle (2026-10-13)"*), `:7806` `now = time.monotonic()`, `:7807`/`:7815`/`:7844` `_last_hotkey_press`, `:1403` `HOTKEY_DOUBLE_MS = 250`. As tres linhas `call :cycle` do runner sao o mesmo ficheiro (rotulo `hotkey cycle ...` e `Alt+C cycle ...`). | **Re-ancorar** (nao apagar): os braços/mutantes passam a medir o contrato **actual** (gesto 1/2/3 + a janela de 250 ms). O contrato actual ja tem dois portoes **VERDES**: `_main/hotkey-triple-oracle.py` (23/23) e `_main/hotkey-gesture-oracle.py` (11/11) — sao a referencia. **Restricao:** `_main/aceitacao-dono.md:15` (A1) e `:49` (D4) citam `hotkey-cycle-oracle`, e `_main/aceitacao-gate.py` exige que o instrumento citado **exista e esteja na bateria** → o instrumento **tem de continuar na lista**, logo a correccao e' re-ancorar, nunca remover. |
| 11 | `panel hide gate at startup (headless, 4 mutants)` | `_main/panel-hidden-at-startup-oracle.py` | **(a) VELHA** (CRASH) — **FICHEIRO DO LEAD** | `AttributeError: 'SottoShell' object has no attribute 'external_captions_active'`. O **produto tem o atributo**: `app/webview/sotto_webview.py:5710` `self.external_captions_active = False`. O crash e' do **instrumento** (a casca que ele monta nao o declara) — logo **nao e' defeito de produto**. | **Nao tocar** (ownership do Lead; o Lead ja o registou na bateria principal em `0466f1b`). Reportado aqui so. |
| 12 | `cinematic designs fidelity` | `_main/cinematic-designs-oracle.py` | **(a) VELHA** | O pin ainda nao conhece o `--caption-scale`: `:451` `'cinematic-1': {'--size-closed': 'max(13px, calc(var(--size-caption) * 0.66))'` vs o valor **enviado** em `app/panel/themes/cinematic.css` — `max(13px * var(--caption-scale), calc(var(--size-caption) * 0.66 * var(--caption-scale)))` (16 ocorrencias com a variante, 10 com `--size-closed: 13px`), e `app/panel/themes/zipc-panels.css:73` `--size-closed: 13px` + `:114` `font-size: calc(var(--size-closed) * var(--caption-scale))`. | Re-pinar na forma **com** `--caption-scale` (o dial de fonte do dono). |
| 13 | `Alt+C cycle strip->side->hide` | `_main/hotkey-cycle-oracle.py` | **(a) VELHA** | **duplicado** da #10 no runner (`_main/instruments-battery.mjs:114` e `:148` sao o mesmo ficheiro com rotulos diferentes). | idem #10; e o runner deixa de listar o mesmo ficheiro duas vezes (a lista e' minha). |
| 14 | `Alt+C cycle neg (3 mutants)` | `_main/hotkey-cycle-oracle.py --neg-arm` | **(a) VELHA** | Os 3 mutantes estao ancorados no contrato antigo: `:81` `"        self.panel_mode = 'strip'"`, `:89` `"        self.set_panel_surface('panel', reason)"`, `:93` `"        if self.panel_mode == 'side':\r\n"`. Os tres mutantes nao mudam mais o comportamento medido. | Re-ancorar os 3 mutantes no gesto actual (e verificar que continuam a mudar o comportamento medido — mutante decorativo nao entra). |
| 15 | `panel chrome neg (3 mutants)` | `_main/panel-chrome-gate.py` | **(a) VELHA** | `NEG-ARM M1 tele labels back: CONTROL IS DEAD (anchor count=0)`. A ancora M1 (`:351-352`) e' `'        <span class="chrome chrome--mano" data-chrome="foot" data-slot="start">'` — **count=0** no HTML de hoje. O que existe e' `app/panel/panel.html:245` `       <div class="chrome chrome--mano" data-chrome="head">` (o `mano` **sobeu** para `head`; o que perdeu o rodape foi o `tele`, `:216` `chrome--tele` com `data-chrome="head"`). | Re-ancorar M1 no no real (`chrome--mano` com `data-chrome="head"`), com contagem verificada = 1, mantendo a mutacao a **por de volta** os dois spans `tele` de rodape (que e' o que o gate tem de apanhar). |
| 16 | `cine themes neg (8 mutants)` | `_main/cine-themes-oracle.py` | **(a) VELHA** | `NEG-ARM VERDICT: FAIL -- 8 mutant(s), 0 wrong, 1 inert, control GREEN` — M1 substitue `var(--size-closed, calc(var(--size-caption) * 0.72))`, que tem **count=0** em todos os `theme-*.css` (o valor enviado traz `--caption-scale`, ex. `app/panel/themes/cinematic.css:251`). Mutante **inerte** = portao cego nesse ponto. | Re-ancorar M1 no valor **enviado** (o mesmo com `--caption-scale`) e voltar a exigir que ele leve o arm a RED. |
| 17 | `cinematic designs neg (6)` | `_main/cinematic-designs-oracle.py --neg-arm` | **(a) VELHA** | `mutant anchor not found: 'font-size: var(--size-closed, calc(var(--size-caption) * 0.7'` — a ancora M1 nao existe no CSS actual (mesma causa de #12). | idem #12, na ancora do mutante. |
| 18 | `caption independent of panel` | `_main/caption-independent-oracle.js` | **(a) VELHA** | `49 check(s), 10 failed` — A13b/A13c/A13d/A14/A15/A19/A20 com `real=["false",null,"none"] want=["true","on","block"]` (o gate espera o overlay **criado no browser**) e B2/B3/B3b (o gate espera que a pagina **nao** pinte `html`/`body` opacos). O produto passou a ter **janela de legenda nativa**: `app/panel/panel.js:2718-2721` `shellOwnsCaptionWindow()`, `:2728-2729` `applyFloat` sai logo, e a base opaca do painel e' **protecção de render** deliberada (`app/panel/panel.js:2709` cita `panel.css:105-127`). | Re-ancorar o bloco do overlay no contrato **nativo** (o gate passa a medir que a pagina NAO cria overlay quando o shell tem `setLiveEnabled`, e que a base opaca e' intencional). |
| 19 | `three overlays` | `_main/three-overlays-oracle.js` | **(a) VELHA** (2 checks) | Medido hoje: `33 check(s), 2 failed` → **A5** `the LIVE button is bound and raises the window height ... setStripHeight(FLOAT_HEIGHT)` — `FLOAT_HEIGHT` foi **eliminado de proposito**: `app/panel/panel.js:62-84` (*"Until this morning there were TWO constants here, STRIP_HEIGHT='40px' and FLOAT_HEIGHT='220px' ... The second one is GONE, and it is gone because of what the log measured ... the constant that produced it is deleted instead of being re-tuned"*), `:85` `const STRIP_HEIGHT = '40px';`. E **D6** (`:252-254`) testa o **HTML cru** por `id="strip-theme-button"` — a cadeia so sobrevive **nos comentarios** que documentam a remocao (`app/panel/panel.html:301-303`, `:725-728`, `:807-818`); no markup real o botao nao existe (e `app/panel/panel.css:1633` tem a regra do picker, portanto a metade do CSS do D6 passa). | A5: re-ancorar na **altura unica** (`STRIP_HEIGHT`). D6: testar o HTML **sem comentarios** (o gate tem de medir markup, nao prosa). |
| 20 | `strip float oracle` | `_main/strip-float-oracle.js` | **(a) VELHA** | `50 check(s), 4 failed`: S20b (ordem da row da strip), W8 (`the raised height is FLOAT_HEIGHT`), W10 (`applyFloat calls setPanelSurface ONLY while...`), Z5 (`each design declares its own caption size`). Mesmo produto, mesma data: `FLOAT_HEIGHT` eliminado (`app/panel/panel.js:62-85`), `applyFloat` ja nao pergunta nada ao shell (`app/panel/panel.js:2692-2698` descreve as **tres escritas que foram removidas**; `:2728-2736` e' o corpo actual, que so chama `setStripHeight(STRIP_HEIGHT)` em `:2734`). | Re-ancorar os 4 checks no que o produto faz hoje. |
| 21 | `botoes lane gesture` | `_main/botoes-lane-gesture-oracle.js` | **(a) VELHA** | `11 check(s), 4 failed` — o gate espera o offset do drag **publicado como string** em `sotto:strip-offset` (`real="object" want="string"`, `[null,null,null]` vs `[60,30,1]`, pintado `["0px","0px"]`, bridge chamada com `false`). O drag passou a ser **nativo do SO**: `app/panel/strip-drag.js:31` `var native = !!(bridge && typeof bridge.beginWindowDrag === "function")`, `:67` `bridge.beginWindowDrag(surface)`; o caminho JS ficou **so como fallback** (`:92` `var KEY = "sotto:strip-offset"`, `:117-119` `bridge.setStripOffset(...)`). O shell responde: `app/webview/sotto_webview.py:5307` + `:4561`. | Re-ancorar no drag nativo (o gate passa a medir que o SO move a janela e que o fallback JS existe para os harnesses sem `beginWindowDrag`). |
| 22 | `surface loop: page half (echo asks nothing)` | `_main/surface-loop-panel-oracle.js` | **(a) VELHA** | `VERDICT: FAIL (shipped 5/6 green)` — RED em `A GENUINE-SWITCH a real surface switch still repaints -- pageAsks=0 surface=strip`. O braco A conta **`bridge.setPanelSurface` asks**, e `applyFloat` ja nao pergunta nada ao shell (mesma prova de #20: `app/panel/panel.js:2692-2698`, `:2728-2736`). | Re-ancorar o braco A no que a pagina pede **hoje** (ou medir o efeito, nao o `ask` que ja nao existe). |
| 23 | `surface loop page neg: both guards RED` | `_main/surface-loop-panel-oracle.js --neg-arm` | **(a) VELHA** | O mesmo check A vermelho → os 2 mutantes (M1 `value !== previous` em `surface.js`, M2 `after !== before` em `panel.js`) continuam load-bearing, mas o braco que os exercita morreu. | idem #22. |

---

## 4. (b) DEFEITOS REAIS

### 4.1 Do PRODUTO (shell / worker / painel): **ZERO** — nenhum confirmado

Nenhum dos 23 vermelhos se resolve em "o produto esta errado". Em todos os casos o **produto
mudou de proposito** e o **portao ficou atras**. As mudancas do produto que explicam os vermelhos
estao todas documentadas no proprio codigo (com data e motivo), e nenhuma delas e' um
acidente:

| mudanca do produto (deliberada) | quem a fez | o que os portos ainda medem |
|---|---|---|
| gesto Alt+C de 1/2/3 com janela de 250 ms, em vez do ciclo de 3 estados sem relogio | dono, 2026-10-13 / 2026-10-18 (`app/webview/sotto_webview.py:7772-7850`) | #10, #13, #14 |
| janela de legenda **nativa** no SO (`NativeCaptionOverlay`), overlay do browser so como fallback | 2026-10-17 (`app/panel/panel.js:2702-2721`) | #18 |
| `FLOAT_HEIGHT` eliminado (uma unica altura, 40 px) | 2026-10-17 (`app/panel/panel.js:62-85`) | #19, #20, #22, #23 |
| drag da strip **nativo** do SO, com o caminho JS como fallback | (`app/panel/strip-drag.js:31-87`) | #21 |
| dial de fonte com `--caption-scale` | (`app/panel/themes/cinematic.css`, `zipc-panels.css:114`) | #12, #16, #17 |
| botao de tema da strip **cortado** pelo dono (o picker e' do painel) | (`app/panel/panel.html:301-303`, `:725-728`, `:807-818`) | #19 |
| chrome `mano` **subiu** para `head`; o `tele` perdeu o rodape | (`app/panel/panel.html:216`, `:245`) | #15 |
| checkpoint Redux: o default do runner e' o `ternary` (ausente); o `onnx-int4` e' o engine live | (`worker/redux_batch.py:39`, `worker/sotto_worker.py:3635`) | #1 |

**Uma limitacao declarada (nao e' defeito, e' o gap que o proprio portao existe para fixar):** o
**braço Redux batch esta inerte nesta maquina** — `worker/models/parakeet-redux-ternary` nao existe,
`worker/redux_batch.py:113-119` aborta sem `model.safetensors`/`ternary.json`, e o switch do worker
**recusa-se a armar** (`_main/canonical-producer-oracle.py:484-490`, GREEN). O gate descreve isso
com as proprias palavras (`:681-685`): *"THE ONE REMAINING GAP: the Redux checkpoint is not on disk,
so the batch arm cannot produce the line."* O que esta mal **no portao** e' so a condicao do check
(ver #1).

### 4.2 De um INSTRUMENTO (nao do produto) — 1 achado, com prova

**`_main/model-spec-oracle.py` nao consegue distinguir "apanhou a deriva" de "nao apanhou".**

O instrumento escreve o contrato nos proprios comentarios:

```
#   --neg-arm    1 = PASS BY DESIGN (the negative arm is SUPPOSED to find the drift; the
#                     battery's :expectred recorder asks for exactly that), 0 = a mutant
#                     was NOT caught, 2 = setup error (a decorative mutant).
```
(`_main/model-spec-oracle.py:22-24`)

Mas o codigo devolve **1 nos dois casos**:

```python
        if not ok:
            return EXIT_FAIL      # :150  -- e' 1 (EXIT_FAIL = 1, :41)
        ...
        return 1                 # :153  -- "rc=1 BY DESIGN"
```

Medido hoje (`$env:TMPDIR='I:\cc-tmp\diag13'`, `python _main/model-spec-oracle.py --neg-arm`):
* na arvore viva → `NEG-ARM PASS -- mutants 2/2 caught, 0 decorative`, **rc=1**;
* na copia **cega** (a comparacao forçada a `return True`, que e' a mutacao da linha r56) →
  `NEG-ARM FAIL -- mutants 0/2 caught, 0 decorative`, **rc=1** tambem.

Consequencia: `audit-rows-negative-arm-falsifiability.py:146`
(`cannot_say_no = not (neg['rc'] == 0 and blind['rc'] != 0)`) **nao consegue dizer** se o oraculo
diz NAO ou nao — porque os dois rc's sao o mesmo numero. E' por isso que a linha r56 aparece como
`defect=True expected=False WRONG COLOUR`.

**Correccao proposta (2 linhas, ambas em instrumentos):**
1. `_main/model-spec-oracle.py:150` → devolver **0** quando um mutante nao e' apanhado
   (cumprir o contrato das linhas 20-24). **Verificar primeiro** que a bateria principal
   (`_main/_audit-verify-all.cmd`, do Lead) nao depende do rc=1 nesse caminho: o caminho vivo
   continua a dar 1 (mutantes apanhados), e o `:expectred` pede exactamente 1.
2. `_main/audit-rows-negative-arm-falsifiability.py:146` → ler a convencao actual
   (apanhou=1, nao apanhou=0) em vez da de antes de 2026-10-11.

---

## 5. O QUE NAO FICOU FECHADO (e porquê)

| # | o que | porquê |
|---|---|---|
| 1 | **As 22 correccoes (a) NAO foram aplicadas.** A classificacao esta pronta e a correccao de cada uma esta escrita na tabela (§3, coluna "o que a correccao exige"), mas **nenhum ficheiro de instrumento foi editado** — o Lead pediu a classificacao primeiro, com prazo curto, e nada foi tocado para nao colidir com escritas alheias. | ordem do Lead |
| 2 | **A contagem final da bateria (depois das correccoes) e' NAO MEDIDO.** | as correccoes nao existem ainda |
| 3 | **A contagem da 2a bateria depois dos commits do Lead (`0466f1b`, `a3c4cd0`) e' NAO MEDIDO.** O baseline e' de `9041daa`; esses commits tocaram o `.cmd`, o `panel-hidden-at-startup-oracle.py` e o censo — **nao** a lista do runner. | nao voltei a correr a bateria (o Lead pediu a classificacao, nao uma re-medicao) |
| 4 | **`_main/panel-hidden-at-startup-oracle.py` (vermelho #11): reportado, nao corrigido.** | o ficheiro e' **do Lead** (`0466f1b` acabou de o mexer) |
| 5 | **`_main/_audit-verify-all.cmd`: nao tocado.** A correccao do #7 e' na auditoria (`_main/verify-all-launch-audit.py`), que e' minha. | o `.cmd` e' do Lead |
| 6 | **`hotkey-cycle-oracle.py`: a forma exacta da re-ancoragem (3 mutantes) fica para a fase de correccao**, mas o ficheiro **tem de continuar na lista da bateria** — `_main/aceitacao-dono.md:15` (A1) e `:49` (D4) citam-no e `_main/aceitacao-gate.py` exige que o instrumento citado exista e esteja listado. Logo: re-ancorar, **nunca remover**. | restricao do `aceitacao-gate` |
| 7 | **Nenhum produto foi corrigido** (`app/webview/`, `app/panel/`, `worker/` intactos). | (b) nao ha defeito de produto; e nao se mexe no produto sem o Lead |

### 5.1 ACTUALIZACAO DO LEAD (2026-10-20, depois desta classificacao)

O Lead **re-mediu** a 2a bateria (a que dava 122/145 failed=23) e aplicou TRES das correccoes.
O numero actual da 2a bateria e' **123/145, failed=22** — porque o `panel-hidden-at-startup-oracle.py`
(#11) ja esta VERDE desde `fe3ef4b`, e nao porque as outras 21 tenham sido corrigidas.

| vermelho | o que o Lead fez | medido depois |
|---|---|---|
| **#2** `neg-arm-falsifiability` | **O INSTRUMENTO PEDIA CONFIRMACAO AO LEAD. A CONFIRMACAO FOI DADA E A CORRECCAO FOI APLICADA.** `_main/model-spec-oracle.py` passou a devolver **0** quando um mutante nao e' apanhado (cumprindo o contrato que ele proprio escreve nas linhas 20-24 e a convencao do AGENTS.md: rc=1 por desenho, rc=0 = mutante sobreviveu); e `_main/audit-rows-negative-arm-falsifiability.py:146` passou a ler a convencao actual. | **VIVO** rc=1 (`NEG-ARM PASS -- mutants 2/2 caught`); **CEGO** (a comparacao forcada a `return True`) rc=0 (`NEG-ARM FAIL -- mutants 0/2 caught`, `THE ORACLE CANNOT SAY NO`) — **os dois rc's sao DIFERENTES**, que e' o que o arm queria provar. O falsificador inteiro: `VERDICT: PASS`, rc=0. Antes: `VERDICT: FAIL (1/3 labels matched)`. |
| **#8/#9** `handler-map` (+neg) | O pin `EXPECTED_KINDS` foi re-ancorado nas 6 entradas novas. | normal: `VERDICT: PASS -- 7 check(s), 0 fail` (`the shipped table holds the page vocabulary (31 kind(s)) -- exact`); neg-arm: `VERDICT: PASS -- 9 check(s), 0 fail` — **os 3 mutantes continuam a ir a RED**. |
| **#11** `panel hide gate at startup` | Ja nao e' vermelho: `fe3ef4b` semeou as flags no fake. | `VERDICT: PASS` (medido na corrida de 08:23). |

**As outras 21 correccoes (a) continuam NAO aplicadas** — a tabela do §3 tem o plano exacto de cada
uma. E a bateria PRINCIPAL continua a ser a prova de referencia: **84 passos, gate=59, control=9,
skipped=1, expect-red=15, missing=0, failed=0 -> GREEN WITH 1 SKIPPED**, rc=0.


---

## 6. REGISTO DAS MEDICOES

* Bateria completa: `I:\cc-tmp\battery-baseline.txt` (SUMMARY: 122/145, failed=23, launches=0).
* Corridas isoladas: `I:\cc-tmp\diag1..diag16\` (uma pasta por instrumento, `TMPDIR` proprio).
* Citas re-medidas hoje (numeros de linha actuais): `I:\cc-tmp\citations.txt` (script `I:\cc-tmp\citations.py`).
* Nenhum ficheiro deste recibo depende de `I:\` para ser lido — os logs sao o registo, a prova
  esta no `ficheiro:linha` do repositorio.
