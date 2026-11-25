# Recibo — auditoria de documentação contra o código (2026-11-25)

**Árvore:** worktree isolado `ta7ead995b/m`. **Regra:** o código é árbitro; cada número abaixo foi producedo por um comando executado NESTA árvore. Documento é alegação, não prova. Onde não há medição escreve-se `CANNOT-MEASURE`.

## Como a auditoria refutou os documentos

| documento | alegação ANTES (lida no documento) | alegação DEPOIS (lida no código + oráculo) | instrumento / evidência |
|---|---|---|---|
| `AGENTS.md` | HOLD de `Alt+C` descrito como contrato corrente; worker só retoma após piso de 45 s; hook de teclado em `worker/space_swallow.py` | HOLD não existe (`grep` zero linhas); retoma tem duas guardas e nenhum piso de 45 s; o hook é `app/webview/space_swallow.py` (o ficheiro em `worker/` não existe) | `grep -rnE 'EXTERNAL_RESUME_MIN_S\|EXTERNAL_CAPTIONS_WORKER_RESUME_DEFERRED' worker` → ZERO; `ls worker/space_swallow.py app/webview/space_swallow.py` → primeiro ausente, segundo presente; `python _main/agents-md-pins-oracle.py` → PASS |
| `AGENTS.md` (PREMISSAS PROIBIDAS) | "separar por voz" lido como nomes/DER | separar é o objectivo; nomes e DER não são métrica; slots de cor são efémeros | `_main/receipt-20261124-per-voice-default.md`; coseno mesma-voz min `+0,655` vs diferente max `+0,743` (limiar vazio); 1 voz → 3 slots em 88 s |
| `docs/hotkey-gestos.md` | `Alt+C` com HOLD e três casas por pressão | `Alt+C` é double dentro de `DOUBLE_TAP_S = 0,40 s`: 1 toque mostra faixa, 2. dentro da janela promove ao painel, fora esconde | `app/webview/hotkey_gesture.py:111,201-242`; `python _main/altc-gesture-oracle.py` → `arms=104 pass=104 fail=0`; `--neg-arm` → VERMELHO como desenhado |
| `docs/worker-lifecycle.md` | worker retoma com piso de 45 s e constante `EXTERNAL_RESUME_MIN_S` | retoma depende de `exiting`, `_external_parked` e `engine_park_reason() == 'captions'`; constante não existe em `worker/` | `app/webview/sotto_webview.py:21431-21497`; `grep` ZERO linhas; comentário único em `app/webview/sotto_webview.py:3053` |
| `docs/mouse-e-input.md` | hook global em `worker/space_swallow.py` | único hook é `app/webview/space_swallow.py`; `RegisterHotKey` regista tecla e entrega `WM_HOTKEY`, não é hook de input global | `ls` dos dois caminhos; leitura de `app/webview/sotto_webview.py` |
| `docs/audio-ladder.md` | micro só em alguns rungs; denoise inerte | micro em P/A/B/C (`sotto_worker.py:4950-5004`); `use_denoise` aplicado em `StreamAsr.run_chunk` (`:2574-2585`) | `python _main/capture-share-oracle.py` → `PASS (8/8 arms)`; `python _main/config-truth-oracle.py` → `VERDICT: PASS` (`max\|delta\|=0.079018` em 8 960 amostras) |
| `docs/shell-contract.md` | geometria sem regra de monitor | `select_display_for_point` escolhe o monitor do cursor/work area e clamp à work area | `python _main/multi-monitor-oracle.py` → `6 arm(s), 30 check(s), 0 failure(s)`, `VERDICT: PASS` |
| `docs/spec/03-CAPTURE.md` | sem secção para captura partilhada, micro em todos os rungs ou denoise ligado | secção 8 datada, com chamadores e vereditos | `python _main/capture-share-oracle.py`; `python _main/config-truth-oracle.py` |
| `docs/spec/04-ENGINES.md` | pontuação de modelo descrita como dead/GPU | `PROVIDER = "cpu"` por nome, `THREADS = 1`, guarda de língua | `python _main/punctuation-oracle.py` → `5/5 arms green`, `VERDICT: PASS` |
| `docs/spec/08-PANELS-UX.md` | três casas por pressão; menu em inglês (`Open panel`, `Quit Sotto`) | double de 0,40 s; menu PT-BR (`Abrir painel`, `Sair do Sotto`), ids `[1,4,5,3,2]` | `python _main/altc-gesture-oracle.py`; `python _main/tray-menu-oracle.py` → `CHECK arms=27 failed=0`, `VERDICT: PASS` |
| `docs/spec/13-MODULES.md` | `worker/capture_share.py`, `worker/discord_streams.py` e `worker/mic_tap.py` AUSENTES; `worker/denoise.py` dizia "ninguém no produto" | os três blocos existem; denoise tem chamador real em `sotto_worker.py:2574-2585` | `python _main/spec-coverage-oracle.py` → `ausentes=0`, `VERDICT: PASS` |
| `docs/spec/STATUS.md` | selo de 2026-11-15 ainda actual | adenda de 2026-11-25 com os vereditos e a ressalva das citações | `python _main/spec-coverage-oracle.py`; `python _main/spec-citations-oracle.py` |
| `INTENCAO.md` | INT-4 descrevia o ciclo de três pressões; nenhuma entrada para o comportamento novo | INT-4 marcado como RETIRADO; INT-10..INT-13 datadas com instrumento e veredito | ver secção "Vereditos" abaixo |

## Vereditos — comandos corridos nesta árvore, 2026-11-25

```
$ python _main/agents-md-pins-oracle.py
AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)
VERDICT: PASS
(rc=0)

$ python _main/spec-coverage-oracle.py
SPEC-COVERAGE docs=16 ausentes=0 nome_apenas=0 classes_sem_seccao=0
SPEC-COVERAGE VERDICT: PASS
(rc=0)

$ python _main/altc-gesture-oracle.py
ALTC-GESTURE GREEN -- arms=104 pass=104 fail=0 (rc=0)
(rc=0)

$ python _main/altc-gesture-oracle.py --neg-arm
ALTC-GESTURE VERMELHO -- arms=104 pass=102 fail=2 (rc=1)
NEG-ARM double-window-ignored PASS -- RED as designed
NEG-ARM PASS -- RED as designed: as seis regressoes derrubam o oraculo
(rc=1)

$ python _main/capture-share-oracle.py
CAPTURE SHARE VERDICT: PASS (8/8 arms)
braço f: worker_taps=1 worker_mics=1 sidecar_taps=0; drops=442

$ python _main/config-truth-oracle.py
VERDICT: PASS
false arm == module-disabled arm: 35840 bytes, sha256-prefix equal
true arm changed PCM: max|delta|=0.079018 over 8960 samples

$ python _main/multi-monitor-oracle.py
MULTI-MONITOR PASS -- 6 arm(s), 30 check(s), 0 failure(s)
VERDICT: PASS

$ python _main/punctuation-oracle.py
5/5 arms green (provider-cpu, lang-pt-skip, model-absent, env-off, cuda-refused)
VERDICT: PASS

$ python _main/tray-menu-oracle.py
CHECK arms=27 failed=0
VERDICT: PASS

$ python _main/spec-citations-oracle.py
A3 GREEN  documentos indexados: 15, ausentes do disco: 0
A4 GREEN  documentos no disco: 15, fora da tabela: 0
A5 GREEN  documentos com o que-nao-se-sabe escrito: 9 de 9
A6 GREEN  citacoes a ficheiros do indice: 1726, fora do indice: 0
A7 GREEN  boletins [UNKNOWN]: 57, sem o que os fecha: 0
SPEC-CITATIONS: docs=16 citacoes=1726 sem_ficheiro=0 fora_de_alcance=0 index_ausente=0 fora_da_tabela=0 lacunas_sem_fecho=0
SPEC-CITATIONS VERDICT: PASS
(rc=0)
```

`spec-citations` estava **FAIL** no fim desta auditoria e foi **fechado no mesmo dia**: as 15 citações fora de alcance apontavam todas para `run.cmd:294-318`, linhas que existiam no `HEAD` mas que o Slice 7 encurtou quando tirou os defaults REDUX daquele ficheiro (o `run.cmd` passou de 320 para 285 linhas). Não eram "pré-existentes": nasceram **dentro** deste trabalho, e é por isso que foram corrigidas para as linhas reais em `01-ARCHITECTURE.md`, `02-BOOT.md`, `07-HISTORY-STATE.md`, `09-FAILURE-MODES.md` e `13-MODULES.md`, em vez de ficarem nomeadas à espera de outra lane.

## O braço negativo que não podia falhar (`caption-independent`, 2026-11-25)

`_main/caption-independent-oracle.js` estava **RED com 7 braços** nesta árvore e **também estava RED no `HEAD`** — o mesmo conjunto exacto (`B2 B3 C1 C3 C4 C5 C8`), provado correndo o oráculo do `HEAD` contra o `app/panel` do `HEAD` num diretório temporário (`git archive HEAD app/panel _main/caption-independent-oracle.js`), e é por isso que a lane anterior o chamou "pré-existente". A lei deste repo nomeia o problema: **um braço que não pode falhar é um verde falso, e um vermelho não é entregável**. Este oráculo está no `instruments-battery.mjs` (passo positivo e passo negativo), logo o braço negativo dele era **verde por construção**: com 7 checks sempre vermelhos, qualquer mutante "derrubava o oráculo".

As sete causas, uma por braço, todas do mesmo sítio — o documento que o oráculo julgava:

| braço | o que estava errado | cura |
|---|---|---|
| `B2` | `documentSheets()` forçava `caption-float.css` na população, e `panel.html` já não a liga; o único "ofensor" era uma regra de um ficheiro que a página não carrega | a população é o que o `panel.html` (mais o manifesto lazy) liga |
| `B2` (2ª metade) | a regra de painel `.caption-float__meter` era creditada como "coberta" por um ficheiro que não carrega | o medidor é **pintor permitido por nome** (`memberIsMeter`), como a barra esquerda; o `paintScan` passou a procurar o neutralizador em **todas** as folhas carregadas e na ordem da cascata (regra posterior de especificidade igual ganha) |
| `B2c` | provava que `caption-float.css` cobria a placa do medidor | agora prova que o varrimento não está verde por inanição (`scanned>100`) e que a folha retirada **não** está na população |
| `B3` | pedia `html` OPAQUE, e o `panel.css:105-127` põe a protecção de render no **body** (comentário que possui a regra) | `['TRANSPARENT','OPAQUE']`: `html` é o host da janela, `body` é a protecção |
| `C1` | clicava `#history-gallery .gallery__day`, markup que já não existe (o `panel.html` não liga `history-gallery.js`) | a porta que ships é o replay para `#history-list`, e o módulo retirado não pode voltar a ser ligado |
| `C3`/`C4`/`C5` | queriam `scrollTop == 1200`; `pinHistoryToBottom` (`panel.js:2006-2014`) escreve `scrollHeight - clientHeight` | comparam com a **mesma aritmética** (`feedBottom()`), não com um literal |
| `C8` | procurava `pinHistoryToBottom()` e o código chama `pinHistoryToBottom(true)` | regex `/pinHistoryToBottom\(\s*(true)?\s*\)/` |

O mutante `N3` também estava decorativo: ele injectava a regra de transparência em `caption-float.css`, folha que a página não carrega, e o selector dele (`html[data-float="on"]`) nunca casa no painel (o shell escreve `data-float` em `#caption-float`). Re-ancorado no dono vivo da base — `panel.css:105-127`, o `background` do `body` — ele derruba `B3` **e** `B3b`, que é o par que o defeito descrito exige.

O `--neg-arm` foi re-corrido: 13 mutantes, cada um derruba o seu braço (`N3` → `B3\|B3b`, `N13` → `A18\|A21c\|A23c`, `N1` → `C3\|C4\|C5\|C6\|C9`), `NEG-ARM VERDICT: PASS`, rc=0 — agora um verde que **pode** falhar.

## A bateria da casa contra estas dez fatias (2026-11-25)

A bateria principal (`_main\_audit-verify-all.cmd`) correu contra esta árvore e devolveu **quatro vermelhos que não eram do documento**: `panel-themes`, `nemotron-preload`, `code-health`, `claims-date`, mais dois que o censo levantou (`battery-wiring`, `spec-citations`). Cinco foram defeito real; um (`claims-date`) era uma afirmação sem data que este trabalho escreveu.

| passo | o que estava vermelho | leitura | cura |
|---|---|---|---|
| `panel-themes` | `FAIL caption-plate pass=0 fail=59` | o braço media `#caption-float .caption-float__col`, um `div` cujo ÚNICO pintor era `caption-float.css`, folha que a S4 deixou de ligar (a legenda no ecrã é o overlay NATIVO) | o braço e o piso de placas distintas passam a medir `--brand-plate`, o token que o overlay recebe. Provado que o pipeline está intacto: sonda directa nas duas árvores → `plateVar=rgba(7, 8, 8, 0.860)`, `SottoBrand.last().rowBgAlpha=0.86` no `HEAD` **e** hoje; só o `colBg` mudou (`rgba(7,8,8,0.86)` → `rgba(0,0,0,0)`). Agora `CAPTION-PLATES distinct=true (58 computed beds)`, `VERDICT: PASS`, e o `--neg-arm` continua `13/13 mutants caught` |
| `nemotron-preload` | `MISSING: production WorkerBridge does not opt into hidden Redux` | o controle só aceitava `env['SOTTO_REDUX_WHEN_HIDDEN'] = '1'` (atribuição); a S7 trocou por `env.setdefault(...)` para que um `0` explícito do dono sobrevivesse | o predicado `_opts_into_hidden` aceita as **duas** grafias e o mutante novo `shell-opt-in` (troca o `setdefault` por `= '0'`) tem de ser apanhado — `NEG-ARM: PASS -- 17/17 focused lifecycle mutations caught` (eram 16) |
| `battery-wiring` | `new-unwired: 1 oraculo(s) sem passo: discord-streams-oracle.py` | um oráculo novo sem passo é um instrumento que ninguém corre | par `discord-streams` + `red-as-expected-discord-streams` na bateria (9 s o positivo, 8 s o negativo, árvore FALSA em `I:\cc-tmp`, sem dispositivo nem modelo) → `ligados=229 sem_passo=102`, `PASS checks=7 fail=0` |
| `code-health` | 27 métricas pioraram (`sotto_worker.py` 536 430→540 428 B, `speaker_sidecar.py` 83 148→95 500 B, `mic_tap`/`capture_share`/`punctuation_model`/`denoise` novos) | crescimento real das fatias S1/S2/S6 | rebaseline explícito `--update --allow-dirty`, que **imprime** cada entrada fixada (10 ficheiros) → `CODE-HEALTH VERDICT PASS`, `NEG-ARM PASS -- 5 of 5` |
| `claims-date` | `new-undated-claim` | `- **UI 100% PT-BR.**` sem data | datada `2026-11-25`, com o oráculo que a prova (`panel-language`) nomeado na própria frase → `BATTERY-VERDICT claims-date PASS checks=4 fail=0` |
| `spec-citations` | `A1 RED 13-MODULES.md:970 cita app/panel/history-gallery.js` | a secção do módulo apagado ficou no doc | secção reescrita como `REMOVIDO (2026-11-25)` com a razão e o que ficou no lugar → `citacoes=1726 sem_ficheiro=0`, `PASS` |

**Peso morto apagado no mesmo commit.** `app/panel/history-gallery.js` e `_main/history-gallery-oracle.js` não tinham chamador em `app/panel` (`_main/_panel2-dom-probe.js` ARM G asserta que o `#history-gallery` está ausente do documento) — sobravam o próprio ficheiro, o oráculo e os dois passos que julgavam o par. Saíram os dois ficheiros, os dois passos (`history-gallery-oracle`, `control-history-gallery-neg-arm`) e a entrada em `_main/_audit-render/make-harness.py` ASSETS, com a secção do `13-MODULES.md` reescrita.

**Uma fatia, um portão.** `_main/panel-language-oracle.js` tinha sido ligado em `instruments-battery.mjs` **e** agora entra na bateria da casa em par com `red-as-expected-panel-language` (que impõe o `rc` esperado); a listagem dupla foi removida de `instruments-battery.mjs`, porque o segundo passo que prova o mesmo invariante paga-se em toda a corrida.

**PIN da bateria re-medido** depois destas mudanças: `424751 B`, `4854 CRLF` / 0 bare LF, sha256 `317B4D3C87694C971EFF3F2D35A6E872FF5C3151C7C6AD5163EACDA911CB625E` — `_main/agents-md-pins-oracle.py` confirma `2 pin(s) checked live, 0 failure(s)`.

**Uma nota de processo, contra nós próprios.** A primeira corrida desta bateria foi **invalidada** porque este assento editou `_main\_audit-verify-all.cmd` enquanto ela corria: `cmd.exe` relê o ficheiro por deslocamento de bytes e passou a executar linhas partidas (`'wallow-probe.py' não é reconhecido…`). A árvore foi parada (`taskkill /T /F` sobre o `cmd.exe` que largou o watcher) e a corrida recomeçou do zero com a árvore final. Um resultado lido de uma bateria cujo ficheiro mudou debaixo dela não é um veredito.

## A segunda passagem da bateria (2026-11-25, mesma sessão)

A primeira corrida completa fechou com `BATTERY-VERDICT: RED - 3 step(s) failed` e `564 steps` (299 em cache). Os três não eram do produto, eram do INSTRUMENTO — e cada um tinha parado de ver o seu sujeito sem que ninguém notasse:

| passo | o que dizia | leitura | cura |
|---|---|---|---|
| `strip-surface-oracle` (rc=3) | `REAL-FAIL the tray menu has no 'Edit caption position'` | a bandeja é PT-BR desde a ordem de 100% PT-BR (`'Editar posição da legenda'`, `sotto_webview.py:11175`); o oráculo ainda pedia a cadeia inglesa | o check continua a pinar a PORTA (`ID_TRAY_EDIT`) e passa a pinar o rótulo que ships; `STRIP-ORACLE CONTROL PASS broken-copies-red=5 arms=119`, rc=0 |
| `red-as-expected-punct-model` (rc=0 onde se pedia 1) | `NEG-ARM: PASS -- as oito regressoes derrubam o oraculo` | o braço negativo devolvia `EXIT_PASS` depois de apanhar tudo: um controle que não pode passar pela convenção `:expectred` | devolve `EXIT_FAIL` (a convenção da casa é **sair 1 quando apanha**) — medido `neg_rc=1`, `pos_rc=0` |
| `red-as-expected-tap-delivery-stall` (rc=1, marcador não casava) | log: `NEG-ARM: PASS -- 4/4` | o oráculo ganhou o mutante M4 e a bateria exigia o texto `-- 3/3`; o comentário do próprio oráculo ainda dizia `3/3` | marcador da bateria passa a `"NEG-ARM: PASS --"` (o `rc=1` já é o discriminador; o texto só prova de que linha veio), e o doc do oráculo diz `4/4 (M1..M4)` |

**`canonical-producer` estava CRASHED, e o crash escondia dois braços vermelhos.** O `instruments-battery.mjs` anunciava `canonical-producer 47/47`; o oráculo morria em `AttributeError: 'NoneType' object has no attribute 'ParakeetEngine'` no `--red-arm` e, no positivo, em `assert worker stamp line not unique` — porque o worker passou a ser DOIS ficheiros (`2cc4e58`: a entrada `worker/sotto_worker.py` e o núcleo `worker/engine_switch.py`) e o oráculo só lia a entrada. Quatro curas, todas medidas:

- `anchor_any(...)` resolve cada HOP nos **dois** ficheiros vivos e imprime o `<ficheiro>:<linha>` do que de facto casou (11 âncoras do worker: 5 no núcleo, 6 na entrada) — sem imprimir o número de um ficheiro no outro.
- o corte do mutante é feito no ficheiro que **possui** a linha (`engine_switch.py:1654`), e a unicidade é exigida sobre a população inteira (`count=1`).
- o `--red-arm` deixou de escrever a cópia em `%TEMP%` e passa a **compilar o texto mutado com o caminho vivo** (`load_python_module(..., source_text=...)`): a cópia em `G:\Temp` perdia `import engine_policy` (`_policy=None`) e um `HERE` errado — um mutante que não importa não é um mutante.
- dois braços que estavam vermelhos por política retirada: `isCanonical(meta)` saiu do `panel.js` em **2026-11-05** (a admissão vive em `sourceApi.transcriptRoute(meta)`), e o meta reconstruído ganhou `fileText` legitimamente (`caption-formulation.js:869-873`, só quando a marca final foi INVENTADA). O primeiro foi re-aimado para a chamada real; o segundo passou a exigir os quatro saltos `route/start/routeSource/producer` presentes com uma allow-list declarada (`fileText`, `source`) e nada do evento do worker a viajar junto.

Medido: `SUMMARY: 48/48 checks green` (`VERDICT: PASS`) e `--red-arm` com `10 of 40 checks FAILED against the mutant subject (this is the expected colour)`, rc=1. O rótulo do `instruments-battery.mjs` foi corrigido para `canonical-producer 48/48`.

**O que a primeira corrida já tinha provado verde** (e continua verde depois destas curas): `panel-themes` 59 temas / 19 braços, `nemotron-preload` 17/17 mutações, `discord-streams` positivo e negativo, `panel-language` positivo e negativo, `code-health`, `claims-date`, `battery-wiring`, `tooling-intent`, `spec-citations`, `agents-md-pins`.

## O que não foi medido

- `CANNOT-MEASURE` — processo vivo do dono: nenhuma janela/popup foi aberta e nenhum dispositivo de áudio foi tocado nesta lane. Nenhuma frase aqui afirma que a app dele está a correr este código.
- `CANNOT-MEASURE` — nomes de falantes e DER em chamada real: sem call ao vivo, sem token do Discord e sem permissão para carregar pesos de separation; a refutação disponível é a de 2026-11-24, citada acima.
- `CANNOT-MEASURE` — comportamento em dois monitores físicos: a máquina tem um monitor; o oráculo usa árvores sintéticas.
- `UNMEASURED` — o `run.cmd --help` novo **no ecrã de um terminal real**: medido por pipe (9 618 B, 147 linhas, 147 CRLF, rc 0), que é a mesma via do pin; nenhuma lane abre consola na tela do dono para o ler a olho.

## Ficheiros tocados pelo slice de documentos

(Este bloco descreve a fatia `S10DocTruth`; o que a bateria obrigou a mexer em código e em instrumentos está na secção acima.)

`AGENTS.md`, `INTENCAO.md`, `docs/hotkey-gestos.md`, `docs/worker-lifecycle.md`, `docs/mouse-e-input.md`, `docs/audio-ladder.md`, `docs/shell-contract.md`, `docs/spec/03-CAPTURE.md`, `docs/spec/04-ENGINES.md`, `docs/spec/08-PANELS-UX.md`, `docs/spec/13-MODULES.md`, `docs/spec/STATUS.md`, `_main/receipt-20261125-design-audit.md`. Nenhum ficheiro de código, `worker/config.json` ou ficheiro pré-existente não-doc foi alterado.
