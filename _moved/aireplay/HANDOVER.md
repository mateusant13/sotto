# HANDOVER — o clone do Sotto, congelado e transportável

**Escrito em 2026-10-07 (relógio da máquina) por uma lane de ENTREGA.**
**Este documento é um INSTANTÂNEO, não uma constante.** A árvore que ele descreve esteve QUENTE
durante toda a medição — outra lane escrevia e cometia nela ao mesmo tempo. Cada número aqui
carrega o seu instante. Onde houver dúvida, **meça de novo** em vez de citar este ficheiro.

---

## 0. Leia isto primeiro (três minutos)

**O que é isto.** O projeto **SOTTO** — transcrição em tempo real de qualquer áudio deste PC, em
legendas sobre um overlay global **Alt+C** (a frase de aceitação do dono está em `AGENTS.md`). O
código vive em `H:\aireplay`. Esta entrega é o **clone congelado**: um repositório git com um
commit do estado, um `.gitignore` que explica cada exclusão, este documento, e um **bundle** que
se clona noutra máquina.

**O que esta entrega NÃO é.** Nada foi publicado. Não há `remote`, não houve `push`, não há
GitHub. O bundle é um ficheiro local — ver §9 para o motivo, que é concreto e não decorativo.

**O estado, em uma linha.** A transcrição, o índice e as verificações estão implementados e
medidos. **A captura de janelas está BLOQUEADA** desde as 11:20 (WGC `E_ACCESSDENIED`), e o
bloqueio **não** se levantou. Ver §3.

**Se vai MONTAR o ambiente noutra máquina, leia a §12 antes de instalar nada.** A receita ingénua
do ORT (`pip install "onnxruntime-gpu[cuda,cudnn]" onnxruntime-genai`) deixa o runtime **em CPU, em
silêncio, com `error: null`** — há uma linha de correcção e uma ordem que a evita. A §12 traz também
o DirectML como **limitação conhecida** (não é um TODO) e os números medidos de CPU vs CUDA.

**E antes de investir numa separação de falantes, leia a §13.** A diarização no loopback misturado é
**NÃO**, com número: **DER ≈ 61,6 %** (~2,5× o limiar de morte pré-registado), e é um **limite
inferior**. O caminho é **captura por participante** — mais barato, melhor áudio, e sem diarização.

**Onde as coisas estão.**

| o quê | caminho |
|---|---|
| a árvore, pelo atalho | `H:\aireplay` — **junction** (`ReparsePoint`, `LinkType: Junction`) |
| a árvore, pelo caminho REAL | `H:\sotto\_moved\aireplay` |
| o bundle (fora da árvore) | `H:\aireplay-20261007.bundle` |
| o recibo desta entrega | `receipts\receipt-handover-bundle.md` |

**Trabalhe sempre pelo caminho REAL.** O junction existe para o código que já tem `H:\aireplay`
gravado (ver §4.1) e para o dono. Um `git` corrido através do junction funciona, mas confunde
qualquer inventário que compare caminhos.

---

## 1. O que está FEITO — módulo → spec → recibo

Cada linha é um módulo que **existe em `src/`**, a spec que o manda, e os recibos que o medem.
Um recibo é o registo de uma lane: o que mediu, com que instrumento, e o que recusou.

> **ESTA SECÇÃO MUDOU DEPOIS DE SER ESCRITA — leia o aviso antes de confiar numa linha.**
> O inventário abaixo foi medido entre as **12:24 e as 12:55**. Re-medido às **14:4x**, a mesma
> árvore já não é a mesma: **3 ficheiros de `src/index/` foram APAGADOS do disco**
> (`__init__.py`, `schema.py`, `selftest.py`), **`specs/07-highlights.md` foi APAGADO do disco**,
> e **apareceram 3 specs novas e 3 módulos novos que ninguém rastreou** — `specs\05-clip-to-asr.md`
> (824 B), `specs\06-broadcast-and-capture-card.md` (60 096 B), `specs\07-engine-process.md` (936 B),
> `src\pipeline\` (3 ficheiros, 80 963 B), `src\storage\` (3 ficheiros, 87 991 B),
> `src\ui\` (5 ficheiros, 70 436 B). **Nenhum deles está rastreado** (`git ls-files` = 0) ⇒
> **nenhum viaja no bundle.**
> O que isto faz ao bundle está explicado em §5.2: um bundle leva o estado **COMMITADO**, não o
> disco, portanto o bundle final **leva ficheiros já substituídos** (`src\index\schema.py`,
> `specs\07-highlights.md`) **e não leva os que os substituíram**. Não é um defeito do bundle —
> é o que um bundle é, e é a razão de o §5.2 existir.
> As entradas marcadas **`[SUPERADO]`** abaixo ficam com o texto original e a correcção ao lado,
> porque uma afirmação apagada esconde que alguém precisou dela.

### 1.1 ASR — `src\asr\` (10 ficheiros, ~90 KB de código)

Manda: **`specs\02-asr.md`** (25 457 B).
Recibos: `receipt-02-asr-impl.md`, `receipt-04-asr.md`, `receipt-05-onnx-asr.md`,
`receipt-12-audio-level-contract.md`, `receipt-17-asr-parity.md`, `receipt-10-redux-2-threads.md`,
`receipt-11-onnx-threads.md`.
Investigação: `docs\research\04-asr.md`, `05-onnx-asr.md`, `10-redux-2-threads.md`,
`11-onnx-threads.md`, `12-audio-level-contract.md`.

| ficheiro | B | o que é |
|---|---|---|
| `constants.py` | 14 318 | modelo, caminhos, **e a proveniência** de cada constante |
| `engine.py` | 13 157 | o motor ONNX |
| `runner.py` | 11 917 | o laço |
| `parity.py` | 11 791 | paridade contra o oráculo de OUTRO motor |
| `gate.py` | 21 732 | o gate |
| `transcribe.py` | 6 588 | a entrada `python -m asr.transcribe` |
| `level.py` | 5 602 | o emissor de nível a 10 Hz |
| `segment.py` | 4 553 | o segmentador por silêncio |
| `audio.py` | 3 087 | I/O de áudio |
| `__init__.py` | 938 | |

O contrato medido: `intra_op=4 / inter_op=1` (o joelho medido), `segment_mode == "silence"`, o
texto de 814 caracteres **byte-idêntico** ao registado, o nível a **10 eventos por segundo de
áudio**, e `rss_peak_wset` na banda 700–1200 MB (a banda medida é 920–929 MB).

### 1.2 Índice e busca — `src\index\`

Manda: **`specs\04-index-search.md`** (60 347 B).
Recibos: `receipt-06-embeddings.md`, `receipt-07-index-search.md`, `receipt-08-import-library.md`.
Investigação: `docs\research\06-embeddings.md`, `07-index-search.md`, `08-import-library.md`.

| ficheiro | B | o que é |
|---|---|---|
| `selftest.py` | 42 745 | os braços de verificação, incluindo os mutantes |
| `store.py` | 17 145 | o escritor |
| `schema.py` | 15 748 | o esquema + a migração |
| `search.py` | 10 039 | a busca |
| `__init__.py` | 2 612 | |

O `selftest.py` tem braços que **devem ficar VERMELHOS** e um `--expect red` que inverte o veredicto
— é assim que o braço C prova que o gate **sabe dizer não**. Um `--verify-fixture` re-lê
`_main/runs/threads11/silence-t4-p1.json` e falha se o texto embutido diferir.

### 1.3 Captura e codificação — `src\capture\` (C++)

Mandam: **`specs\01-capture-modes-and-scheduling.md`** (8 591 B) e
**`specs\03-capture-encode.md`** (22 552 B).
Recibos: `receipt-01-capture-encode.md`, `receipt-03-capture-impl.md`,
`receipt-03-nvenc-sessions.md`, `receipt-14-ring-cap-vram-vs-ram.md`,
`receipt-15-offline-cut-pass1147.md`, **`receipt-18-capture-capability-battery.md`**.
Investigação: `docs\research\01-capture-encode.md`, `03-nvenc-sessions.md`.

Os maiores: `wasapi_audio.cpp` 43 734, `replay.cpp` 25 917, `test_window.cpp` 23 603,
`main.cpp` 19 700, `trigger.cpp` 19 797, `nvenc_encoder.cpp` 17 515, `wgc_capture.cpp` 14 150,
`mp4_writer.cpp` 13 732, `ring_buffer.cpp` 8 238, `nv12_convert.cpp` 7 612,
`trigger_selftest.cpp` 14 356, `third_party\nvEncodeApi.h` 313 554.
Mais `build.cmd` 1 061, os `.h` de cada um, `d3d11_ctx.cpp`, `selftest.cpp`, `common.cpp`.
**`run_battery.ps1` 26 015 B é a bateria de capacidade do próprio clone** — §7 diz como correr.

### 1.4 Overlay / HUD — a spec RENOMEADA e um módulo que APARECEU (e não está rastreado)

**`[SUPERADO]`** Mandam: **`specs\05-overlay-hud.md`** (47 588 B) e **`docs\overlay-hotkey-contract.md`**
(21 002 B) — **o `05-overlay-hud.md` já não existe em disco**; `specs\05` é agora
**`specs\05-clip-to-asr.md` (824 B, NÃO RASTREADO)**. O `docs\overlay-hotkey-contract.md` continua lá
(21 002 B, rastreado).
Recibos: `receipt-preview-designs.md` (9 336 B), `receipt-render-panel-temas.md` (18 803 B) — ambos
presentes e rastreados.

**`[SUPERADO]` "`src\ui\` está VAZIA."** Era verdade às ~12:55 e é FALSO agora. Medido às **14:4x**,
`src\ui\` tem **5 ficheiros reais, 70 436 B, e 0 rastreados** (`git ls-files -- src/ui` = vazio):
`hud-shell.py` 29 621, `hud-contract.js` 22 056, `hud-panel.js` 7 683, `hud-panel.css` 7 603,
`hud-panel.html` 3 473 — mais um `__pycache__\hud-shell.cpython-311.pyc` (35 788 B). **É o painel do
clone a começar a existir.** Nada disto viaja no bundle (não rastreado, §5.2).

O que continua verdade e é o que importa para quem migra: **o painel PROVADO e vivo ainda não foi
copiado para aqui** — vive em `H:\sotto\app\panel\` e é a Fusão B a funcionar, ver §1.8 e §8.

> Nota de honestidade, e é a terceira revisão desta única secção: uma versão anterior dizia
> "`src\ui\` não existe"; a seguir, "existe mas está vazia"; agora, "existe com 5 ficheiros, nenhum
> rastreado". **Todas foram verdade no seu instante.** É a lei da casa aplicada a mim: **uma
> ausência medida tem prazo de validade** — e uma PRESENÇA medida também. Re-meça antes de citar.

### 1.5 Integração

`receipt-13-refute-integration-audit.md` (3 495 B) + `docs\integration-sotto-app.md` (32 130 B).

### 1.6 Highlights — a spec foi APAGADA do disco e SUBSTITUÍDA; o oráculo ficou

**`[SUPERADO]`** "`specs\07-highlights.md` (28 600 B) existe." **Já não existe em disco** — está
**apagado mas ainda RASTREADO** (`git status` = ` D specs/07-highlights.md`), portanto **o bundle
final ainda o leva**. `specs\07` é agora **`specs\07-engine-process.md` (936 B, NÃO RASTREADO)**.
E **`specs\06-broadcast-and-capture-card.md` (60 096 B, NÃO RASTREADO) EXISTE** — a frase antiga
"não há spec 06" (§8 item 7) morreu. Ver §5.2 para o que isto faz ao bundle.

O que **continua** verdade: **não há módulo de highlights em `src/` e não há recibo.** Mas **o oráculo
existe e PASSA**: `_main\oracle-07-highlights.py` (12 147 B) com o log
`_main\oracle-07-highlights.log` (698 B), `VERDICT PASS` — 0 highlights de 180 s de tom e 180 s de
uma caminhada, e o braço de controlo dispara sem a conjunção. Estado exato: **o oráculo está
escrito e verde; a implementação em `src/` não existe.**


### 1.7 Não é trabalho de produto

`receipts\receipt-22-single-cron-delivers.md` (5 117 B) é da **outra lane** (a da orquestração).
Está no bundle porque o bundle é local e leva a história toda; não é uma funcionalidade do Sotto.

### 1.8 O QUE AINDA NÃO FOI COPIADO PARA ESTE CLONE — leia antes de procurar o painel

**Este clone não tem aplicação executável.** Tem specs, código de captura/ASR/índice, oráculos e
recibos. Não tem o painel, não tem os runners provados, não tem a bateria da árvore de fora.

Medido em 2026-10-07 ~12:55: **`app\` NÃO EXISTE** e **`worker\` NÃO EXISTE** neste clone (0 itens
cada, `Test-Path` = falso). Na árvore de fora existem todos:

| o que falta aqui | onde está (árvore de fora) | estado |
|---|---|---|
| **O PAINEL** — `panel.{html,css,js}` + temas, `caption-formulation.js`, `history-source.js`, `history-store.js`, `surface.js`, `theme-switcher.js` | `H:\sotto\app\panel\` | EXISTE |
| **O SHELL** — WebView2 + pywebview, Alt+C, tray, lock de instância única, hot reload | `H:\sotto\app\webview\sotto_webview.py` | EXISTE |
| **Runner Redux batch** (o ORÁCULO de paridade) | `H:\sotto\worker\redux_batch.py` | EXISTE |
| **ASR ao vivo** (nemotron int8, ONNX GenAI, WASAPI loopback) | `H:\sotto\worker\sotto_worker.py` | EXISTE |
| **WASAPI loopback + escada de dispositivos** | `H:\sotto\worker\wasapi_loopback.py` | EXISTE |
| **Pesos Redux ternário** (177 774 490 B, CC-BY-4.0) | `H:\sotto\worker\models\parakeet-redux-ternary\` | EXISTE |
| **A bateria de verificação da árvore de fora** | `H:\sotto\_main\_audit-verify-all.cmd` (28 947 B) | EXISTE |

**Porque é que isto é uma decisão e não um esquecimento.** É a **Fusão B** do `AGENTS.md` do clone,
decidida pelo dono: **construir ao lado, e só migrar quando a árvore de fora estiver calma.** A
árvore de fora está a fechar bugs seus neste momento — lanes a editar o `_main/`, a bateria, o painel
e o `AGENTS.md` dela. Copiar agora significaria (i) mover ficheiros que uma lane tem meio-editados e
(ii) herdar código inacabado, que continuaria a ser corrigido num sítio enquanto a cópia divergia em
silêncio. **A regra da casa é explícita: nunca deixar o mesmo trabalho duplicado em duas árvores sem
dizer.** Este clone desenvolve o que a árvore de fora NÃO tem (captura, encoder, ring buffer, índice
multimodal, busca, importação de biblioteca) e **não leva cópias nenhumas enquanto a de fora estiver
quente.**

**O gatilho de migração são TRÊS condições, não "quando parecer pronto":**
1. `_main\_audit-verify-all.cmd` reporta `skipped=0` e `failed : -none-` **com a app fechada**;
2. nenhuma lane tem um ficheiro aberto em `H:\sotto`;
3. cada módulo copiado é registado **com o seu sha256 no momento da cópia**, para que qualquer
   divergência futura seja detectável em vez de descoberta.

**Consequência prática para quem abrir este bundle noutra máquina:** não procure `run.cmd`. Não há.
O que se reproduz a partir daqui são as **verificações** (§7), não a aplicação. Para ter a aplicação
é preciso copiar os módulos acima — e só depois do gatilho.

---

## 2. Os gates e os oráculos que EXISTEM no clone (`_main\`)

**`_main\all-gates.ps1` (23 919 B) é o gate agregado DESTE projeto.** Três leis, por construção:
(1) **a descoberta é um glob, nunca uma lista** — resolve `_lane*-gate.ps1` fresco a cada corrida e
imprime POPULATION e WINDOW; (2) **uma verificação em falta é um FAIL, não um skip** — zero gates
descobertos ⇒ FAIL, um gate nomeado em `-Expect` que não existe ⇒ FAIL, um include inexistente ⇒
FAIL; (3) **o código de saída real é lido do objeto Process**, nunca de `$LASTEXITCODE`, nunca de um
pipe. Uma pendura é um FAIL e nomeia o gate.

Inventário real em `_main\`: `all-gates.ps1` 23 919; `durability-gate.ps1` 45 739;
`_lane16-wake-gate.ps1` 30 116; `_lane3-ringcap-gate.ps1` 20 673; `_lane7-window-gate.ps1` 16 931;
`_lane23-trigger-defects-gate.ps1` 13 082; `_lane1-trigger-gate.ps1` 11 956;
`_lane4-index-gate.ps1` 9 060; `_lane9-asr-gate.ps1` 4 141; `_lane02-durability-oracle.ps1` 4 585;
`_hb-lock-selftest.ps1` 4 721; `_all-gates-window-census.py` 7 057; `oracle-02-asr.py` 15 474;
`oracle-07-highlights.py` 12 147; `asr02-selftest.py` 8 056.

**Atenção — dois nomes parecidos, dois ficheiros diferentes:**

- `_main\all-gates.ps1` — **existe no clone**. É o agregado deste projeto.
- `_main\_audit-verify-all.cmd` — **NÃO existe no clone.** A única cópia é a da árvore de FORA:
  `H:\sotto\_main\_audit-verify-all.cmd` (28 947 B). Não cite um caminho do clone que não existe.

---

## 3. O que está BLOQUEADO — a captura de janelas (WGC), desde as 11:20

**O facto.** `Windows.Graphics.Capture` recusa **todas** as tentativas de criar um item de captura
para uma janela. O código devolve `E_ACCESSDENIED` = `0x80070005`. Isto **não** é um erro de
programação nosso: no **mesmo processo, na mesma corrida**, a sessão diz que é suportada e o item
recusa.

**Os dois valores na MESMA corrida — as duas cores juntas, que é a regra da casa:**

```
IsSupported -> 0x00000000 supported=1
CreateForWindow(own window)        -> 0x80070005 E_ACCESSDENIED
CreateForWindow(foreground window) -> 0x80070005 E_ACCESSDENIED
CreateForWindow(desktop window)    -> 0x80070005 E_ACCESSDENIED
CreateForWindow(shell taskbar)     -> 0x80070005 E_ACCESSDENIED
CreateForMonitor(primary monitor)  -> 0x80070005 E_ACCESSDENIED
```

**O instrumento, nomeado.** `_main\wgc-probe.exe`, **307 103 B, mtime 2026-10-07 12:05:07,
sha256 `9B0F884A6933B0C5E918FB728A2E044A530A37C4BF25677449BCFCF1601621FC`**. Fonte:
`_main\wgc-probe.cpp` (16 323 B). **Exatamente 5 pontos de chamada**: a própria janela, a janela em
primeiro plano, a janela do ambiente de trabalho, a barra de tarefas, e o monitor primário.
O binário está **guardado por hash antes e depois** de cada corrida e **não mudou** em nenhuma.

**Quatro instantes independentes, todos a negar:**

| instante | log | resultado |
|---|---|---|
| 11:55:11 | `_main\logs\wgc-denial-probe-3.txt` | 5/5 `0x80070005` |
| 12:10:27 | `_main\logs\handover-wgc-verify.txt` | 5/5 `0x80070005` |
| 12:28:11 | `_main\logs\cap-battery-20261007-122811.txt` | 5/5 `0x80070005` (lido como 5 de 6 — ver abaixo) |
| ~12:39 | `_main\logs\handover-wgc-verify-2.txt` | **5 pontos de chamada, 5 negados, 0 sucessos**, contados à mão |

Cadência de cada um: **UMA corrida, 5 braços**. Nenhum passou `--find-access-iid`, para não
interferir com a experiência da outra lane.

### 3.1 O artefacto `PARTIAL: 5 of 6` — NÃO é um sucesso parcial

**Dois logs de bateria imprimem `probe rc=0  items_tried=6  E_ACCESSDENIED=5` e
`-> PARTIAL: 5 of 6 items refused with E_ACCESSDENIED`.** Um leitor do log cru concluiria, errado,
que o bloqueio está a ceder.

**É um erro do INSTRUMENTO, não da WGC.** A regex dos itens não exigia um `(` e por isso **também
apanhava a linha de banner** `=== WGC CreateForWindow probe ===` e contava-a como um sexto item de
captura. A regex das recusas era estrita, e daí 5 de 6.

O próprio `src\capture\run_battery.ps1` documenta o bug e a cura (linhas ~170–179): as duas regex
passam a exigir o `(` e são contadas **sobre o mesmo predicado**, para que o numerador e o
denominador nunca possam discordar. A minha re-execução (`handover-wgc-verify-2.txt`) contou
**5 pontos de chamada e 5 negados, à mão**.

**Portanto: WGC continua TOTALMENTE bloqueada — 0 de 5.** O `5 of 6` é um número errado produzido
pela medição.

### 3.2 O que o bloqueio NÃO é

A política de consentimento **não** explica a recusa. Lido no registo:

- `HKLM` e `HKCU\...\ConsentStore\graphicsCaptureProgrammatic` = **`Allow`**
- `HKCU\...\graphicsCaptureProgrammatic\NonPackaged` = **`Allow`**
- `HKLM` e `HKCU\...\graphicsCaptureWithoutBorder` = **`Allow`**
- Existem chaves por executável, em `HKCU\...\graphicsCaptureWithoutBorder\NonPackaged\`:
  `H:#aireplay#_main#build#aireplay-capture.exe` e
  `H:#sotto#_moved#aireplay#_main#build#aireplay-capture.exe`

Ou seja: **a política diz `Allow` e a API diz `E_ACCESSDENIED`.** A negação não está no valor da
política. Isto é o que sobra para investigar.

**Tempos do consent store** (FILETIME convertido):
`H:#aireplay#…aireplay-capture.exe` → `LastUsedTimeStart = 2026-10-07 11:20:06.998`,
`LastUsedTimeStop = 11:20:47.031` (40,03 s).
`H:#sotto#_moved#aireplay#…aireplay-capture.exe` → Start `11:24:31.621`, Stop `11:24:37.628`.

**Discrepância a registar honestamente:** o `receipt-03-capture-impl.md` §7 regista
`LastUsedTimeStop = 11:20:09` («o SO revogou o acesso 3 segundos depois do início»); relendo o
**mesmo** valor do registo obtém-se `11:20:47.031` — **38 segundos de diferença**, não
arredondamento. As duas leituras ficam registadas. O facto central — a negação começou naquela
bateria e persiste — não é afetado.

### 3.3 Uma experiência ABERTA, que NÃO está concluída

`_main\logs\wgc-request-access.txt` (12:04:13, 528 B) é de outra lane:
`MATCH after 89 candidate(s): {743ED370-06EC-5040-A58A-901F0F757095}`,
`RequestAccessAsync(Programmatic) -> 0x00000000`, `async status = 1 (Completed) errorCode=0x00000000`,
e depois `calling slot 6 ...` — **o ficheiro acaba aí.** `RequestAccessAsync` **não** é a cura
provada nem está provado que falhou. Não escreva nenhuma das duas coisas.

### 3.4 Divulgação honesta sobre a sonda

A sonda cria a **sua própria** janela 200×200 `WS_POPUP|WS_VISIBLE` com
`WS_EX_TOOLWINDOW|WS_EX_NOACTIVATE` em (0,0), imprime `own window: <hwnd> (IsWindowVisible=1)` e
destrói-a antes de sair. **Não é uma janela do dono e não fica.** As três corridas usaram o binário
**original**, no caminho original, com o hash conferido antes e depois.

---

## 4. O INVENTÁRIO DE EXCLUSÕES — o que o git NÃO leva

**EXCLUIR DO GIT NÃO É APAGAR DO DISCO.** Todos os pesos, binários, clipes, bases de dados e
`node_modules` continuam em disco. O `.gitignore` só diz ao git para não os versionar. **Nada foi
apagado por esta lane.**

O `.gitignore` do clone: **11 453 B, sha256
`D82FCD27406CC0D5BED78F62DAF414087CA8E047FF6DADDFCF29F34B29B6471A`**.
Cada padrão tem um comentário com o motivo e os números.

### 4.1 O que isto significa ao clonar noutra máquina — LEIA ANTES DE ABRIR O BUNDLE

**O bundle é o código e a documentação. Não é o sistema a correr.** Estas são as dependências que
**NÃO viajam** e que tem de re-obter para reproduzir o que foi medido:

| o que falta | tamanho | onde estava | como re-obter |
|---|---|---|---|
| pesos ASR ONNX | 670 619 803 B | `models\parakeet-tdt-0.6b-v3-onnx\` | HuggingFace `istupakov/parakeet-tdt-0.6b-v3-onnx`, revisão `8f23f0c0…` — 5/5 sha256 verificados |
| fixtures de vídeo do muxer | 146 606 044 + 149 720 741 B | `_main\src\cap-1080p60.h264`, `cap-2160p60.h264` | **geradas pela bateria** — ver §7; sem elas as linhas de muxer da bateria não correm |
| áudio longo do ASR | **115 200 044 B** | **`H:\sotto\_main\_redux-long\plain-3600s.wav` — FORA do clone** | não está em lado nenhum do clone; é fixture da árvore de fora |
| áudio curto de paridade | 273 422 + 480 044 B | `H:\sotto\_main\_redux-long\src-en-8s.wav`, `src-pt-15s.wav` — **FORA** | idem |
| oráculo de paridade | 263 + 293 B | `H:\sotto\_main\redux-en.txt`, `redux-ptbr.txt` — **FORA** | idem |
| executáveis já compilados | 15–20 ficheiros / 8,6–10,1 MB | `_main\build\`, `_main\*.exe` | recompilar: `src\capture\build.cmd` |
| `node_modules` dos dois projetos de design | 5 898 ficheiros / 179 084 294 B | `docs\design\*\` | `npm ci` |
| clips, bases de dados, faiss | ~7,2 GB | `_main\runs\`, `_main\_index-store*\` | **são resultados, não entradas** — regeram-se a correr |

**A descoberta importante desta entrega:** `src\asr\constants.py:58` tem
`SOTTO_ROOT = Path(r"H:\sotto")` **gravado no código**. As fixtures de áudio e os oráculos de
paridade do ASR são lidos da **árvore de fora**, não do clone. Noutra máquina, `H:\sotto` não
existe e esses braços **não correm** até esta linha ser mudada. As restantes constantes de caminho
(`REPO_ROOT`, `MODEL_DIR`, `REGISTERED_REFERENCE_DIR`) são **relativas ao clone** e são portáveis.

O C++ também grava caminhos absolutos: `src\capture\main.cpp:256,257,399` escrevem em
`H:\aireplay\_main\runs\` e `src\capture\trigger_selftest.cpp:355` usa `H:\aireplay\_main\build`.
Funcionam **porque o junction existe** — noutra máquina, a pasta tem de se chamar `H:\aireplay`.

### 4.2 Os baldes, com tamanhos (instantâneo 2026-10-07 12:24:26, árvore QUENTE)

Classificação **primeiro-que-casa-vence**, com `node_modules/` atribuído PRIMEIRO (é dependência
vendida, reinstalável com `npm ci`, não é binário nosso).

| padrão | ficheiros | bytes | porque está excluído |
|---|---|---|---|
| `*.mp4` | 52 | 3 623 054 661 | clipes gravados — resultado, não entrada |
| `*.db` | 16 | 3 034 505 216 | índices SQLite — regeneráveis a partir dos clipes |
| `*.onnx` | 3 | 670 525 767 | pesos — re-baixáveis, e foi isto que rebentou o limite de 2 GB |
| `*.h264` | 4 | 437 499 144 | fixtures de vídeo do muxer |
| `node_modules/` | 5 898 | 179 084 294 | dependência vendida; `npm ci` |
| `*.faiss` | 1 | 141 371 558 | índice vetorial — regenerável |
| `*.whl` | 1 | 27 275 208 | pacote Python descarregado |
| `_main/ocr-frames/` | 9 | 22 946 173 | frames extraídos para OCR — derivados |
| `ort_*.json` | 9 | 20 465 893 | perfis do onnxruntime — diagnósticos |
| `*.wav` | 4 | 20 162 156 | áudio de trabalho |
| `_main/_fontes-antes-instrumento/` | 6 | 10 162 382 | render ANTES — histórico |
| `_main/_fontes-antes/` | 6 | 10 033 865 | render ANTES — histórico |
| `*.exe` | 15 | 8 655 485 | binários compilados |
| `_main/_fontes-ruido/` | 1 | 1 858 760 | render de ruído |
| `__pycache__/` + `*.pyc` | 28 | 391 432 | cache de bytecode |
| `models/` | 15 | 210 947 | o resto da pasta de modelos |
| `*.obj` | 1 | 117 935 | objeto intermédio |
| `*.db-shm` | 1 | 32 768 | sidecar SQLite |
| `*.pid` | 1 | 7 | pid de um processo morto |
| `*.db-wal` | 1 | 0 | sidecar SQLite |
| `*.lock` | 1 | 0 | lock |
| **TOTAL** | **6 073** | **8 208 353 651** | reconcilia **exatamente** com o total medido |

**Fronteira deliberada que fica registada:** os renders de fonte **"antes"** são excluídos
(22 055 007 B em 13 PNG) mas os renders **"depois"** (`_main\preview-fontes-*.png`,
`_main\font-fraunces-specimen-depois*.png`), **todos** os diagnósticos de texto
(`_main\font-diag-*.txt`, `font-dom-*.html`) e os `_crop-*-diff.png` são **mantidos** — para que a
comparação antes/depois continue legível.

### 4.3 Regras que hoje casam ZERO ficheiros, e ficam de propósito

`*.onnx.data` · `*.safetensors` · `*.kstlc` · `*.pdb` · `*.lib` · `*.node` (fora de
`node_modules`) · `.pytest_cache/` · `*.bundle` · `*.gguf` · `*.bin`.

**Uma regra que só existe depois do acidente não serve.** A lição que as pôs lá: no projeto Sotto,
`git add` varreu **2,8 GB** de pesos porque **`*.onnx` NÃO casa `*.onnx.data`** — o `.onnx` é o
cabeçalho do grafo e o `.onnx.data` são os pesos, ~150× maiores. O `push` foi recusado pelo limite
de 2 GB do GitHub. Por isso são **duas linhas separadas**, e por isso as regras ficam mesmo quando
hoje não casam nada: a próxima máquina vai exportar `.onnx.data` outra vez.

**Nota de sintaxe, verificada empiricamente:** um DIRETÓRIO totalmente excluído (`build/`) **não
pode** ser re-incluído ficheiro a ficheiro — o git nunca desce lá dentro, e `!build/*.cpp` é texto
morto. `build/*` mantém o diretório visitável e torna as negações eficazes. Foi exatamente esse o
bug que engoliu `_main/build/guid-probe.cpp` (335 B) e `hdr-probe.cpp` (290 B) — **código-fonte
dentro de um diretório de build**. Corrigido e verificado: 0 ficheiros que não sejam `.exe`/`.obj`
sob `_main/build/` estão ignorados.

---

## 5. OS NÚMEROS DO CONGELAMENTO

**Cada número tem o seu instante. A árvore cresceu entre eles.**

| instante | o que foi medido |
|---|---|
| 2026-10-07 **12:24:26** | árvore **7 029 ficheiros / 8 235 595 803 B**; ignorados **6 073 / 8 208 353 651 B**; preparados **963 / 30 455 175 B** |
| 2026-10-07 **12:26:55** | commit `51f84cc` — **1 069 ficheiros / 31 992 375 B** preparados |
| 2026-10-07 **12:39:06** | **1 070 rastreados**; ponta `9cb9eb2`; árvore de trabalho **suja com 283 linhas** |
| 2026-10-07 **~12:55** | **1 073 rastreados**; ponta **`aa06894`**; **13 commits**; suja com **368 linhas**; **não-rastreados-e-não-ignorados = 515** |

**O instrumento de exclusão, e porque é o autoritativo:** `git ls-files --others --ignored
--exclude-standard` dá os ignorados, e `git ls-files --others --exclude-standard` dá os **não
rastreados e não ignorados** — que tem de ser **0**. É imune à corrida entre o que está em disco e
o que está no índice. Medido às 12:24:26: **0**. Padrões ignorados sem correspondência: **0**.

> **Esse "0" tem prazo de validade, e venceu — medido às ~12:55: são 515.** Não é uma regressão do
> `.gitignore`: é a **outra lane a produzir trabalho entre commits**. Os 515 são, na esmagadora
> maioria, `_main\_all-gates-logs\<carimbo>\*.log` — dezenas de corridas do `all-gates.ps1` entre
> as 12:27 e as 12:50 — mais `_main\_adv-*.txt`, os dois `research\*.md` (§8) e o **próprio
> `HANDOVER.md` deste documento, que ainda não estava commitado quando a contagem correu**.
> A lição é a da casa, aplicada a mim: **um "grep devolveu ZERO" é uma afirmação com prazo de
> validade — volte a correr antes de a citar.** Por isso o número fica aqui com o instante em que
> deixou de ser verdade, em vez de ser apagado.
>
> **Re-medido às 15:25:17: são 1 366** (1 133 rastreados, 27 commits, ponta `87efeaf`). Ou seja: em
> duas horas e meia o passivo não-rastreado **quase triplicou**. Isto não é uma falha do `.gitignore`
> — é a lane vizinha a escrever e a commitar em paralelo, e o congelamento a ser um **instantâneo**.


**Integridade — `[SUPERADO]`: era "0 ficheiros rastreados em falta no disco" às 12:24:26 e é FALSO
desde então.** Medido às **15:25:17: 21 ficheiros rastreados já não existem em disco** (§5.2), com
**1 133 rastreados, 27 commits, ponta `87efeaf`, 602 linhas de estado, 1 366 não-rastreados e não
ignorados**. **Binários rastreados: 0** — uma regex
sobre `git ls-files` para `.exe|.obj|.node|.pdb|.lib|.onnx|.onnx.data|.safetensors|.kstlc|.db|.mp4|.h264|.wav|.whl|.faiss|.pyc|.bundle|.lock|.pid` devolveu **0 ficheiros**.
**Segredos:** 0 suspeitos.

**Rastreados por pasta:** `_main` 839, `docs` 51, `src` 47, `receipts` 18, `specs` 4, resto 3.
**Rastreados por extensão (topo):** 275 `.txt`, 137 `.py`, 114 `.json`, 87 `.log`, 45 `.md`,
37 `.png`, 37 `.html`, 34 `.ps1`, 27 `.cpp`, 26 `.out`, 25 `.err`, 18 `.h`.

**O repositório resultante tem ~32 MB.** É altamente transportável — e é por isso que o `.gitignore`
importa: sem ele, o mesmo `git add` levava 8,2 GB.

### 5.1 Fidelidade de bytes — a história CORRIGIDA (a primeira versão desta secção estava errada)

**O que eu tinha escrito, e porque era falso:** *"`core.autocrlf` global está vazio/não definido"*.
Medido, com o instrumento ao lado de cada linha:

| âmbito | comando | valor medido |
|---|---|---|
| sistema | `git config --system core.autocrlf` | **`true`** |
| global | `git config --global core.autocrlf` | **(vazio)** |
| local do clone | `git config core.autocrlf` | **`false`** |
| local do clone | `git config core.eol` | **`native`** |

**O `true` está no âmbito SISTEMA — e é ele que manda num clone novo.** O clone que eu fiz está
protegido pelo `false` local (fixado **antes** do primeiro `git add`, de propósito, para os blobs
reproduzirem os bytes em disco), mas **um `git clone` do bundle numa máquina com o mesmo `--system`
NÃO herda esse `false`** — a configuração do repositório **não viaja num bundle**. Um bundle leva
objetos e referências, não `config`.

**O que isso faz aos bytes, medido em vez de suposto** (clone de ensaio do bundle, comparado ficheiro
a ficheiro com o original):

| ficheiro | no original | no clone por omissão | o que aconteceu |
|---|---|---|---|
| `src\capture\build.cmd` (blob CRLF, 1 061 B, 14 CRLF) | 1 061 B | **1 061 B** | **byte-idêntico** — já era CRLF |
| `.gitignore` (blob **LF**, 11 453 B, 204 LF) | 11 453 B | **11 657 B / 204 CRLF / 0 LF** | cresceu **exatamente o número de linhas** |

**Duas conclusões que só a medição dá:**

1. **Não é uma substituição cega de bytes.** O git é *CRLF-aware*: um blob que já tem CRLF **não** é
   tocado, um blob LF ganha um CR por linha. E, medido: **a contagem de CRCRLF é ZERO em todo o lado**
   — a hipótese de que "um blob CRLF vira CRCRLF" (que eu tinha escrito antes) está **REFUTADA**.
2. **Todo ficheiro LF muda de tamanho E de sha256 num clone por omissão.** Regra prática:
   **tamanho no clone = tamanho em disco + número de linhas**, para ficheiros LF; **igual**, para
   ficheiros CRLF.

**Este próprio documento é LF-only** (1 048 LF, 0 CRLF, 0 CRCRLF, 63 753 B às 15:25:17, sha256
`D96DFA7A9F072FF3462920F3716D9E1C270648AA53A7E399C262A43B5023E718`) — logo, num clone por omissão,
**cresce ~1 048 B e o sha256 acima NÃO se reproduz**. Isto é esperado, não é corrupção.

**Para reproduzir byte a byte, o comando é este — e tem de ser este:**

```
git clone -c core.autocrlf=false "H:\aireplay-20261007.bundle" <destino>
```

Sem o `-c core.autocrlf=false`, o clone é **legível e correto**, mas **não é byte-idêntico** ao que eu
congelei: os `.cmd` continuam válidos (já eram CRLF) e os ficheiros LF ficam maiores. **Nada fica
partido** — mas nenhum sha256 que eu registe a partir do disco bate certo no clone por omissão.

### 5.2 O que o bundle leva é o COMMITTED, não o disco — a divergência, medida

**Um bundle é um instantâneo do estado COMMITADO, não da árvore de trabalho.** Medido às
**15:25:17** (`git ls-files` contra `Test-Path`, ficheiro a ficheiro — não uma impressão):

- **1 133 rastreados**, ponta **`87efeaf`**, **27 commits**, **602 linhas** em `git status --porcelain`.
- **21 ficheiros rastreados NÃO existem em disco** (`git status` = ` D`) ⇒ **viajam no bundle com o
  conteúdo ANTIGO**, como se ainda estivessem lá:
  `_main\_lane25-stage-durability.ps1`, `_main\_lane25-stage-probe.log`,
  `_main\_lane25-stage-probe.ps1`, `_main\_lane25-stage.log`, `_main\_lane4-run\armC-v.log`,
  os 6 de `_main\_lane4-run\work\mutant-escape\`, os 6 de `_main\_lane4-run\work\mutant-unit\`,
  **`specs\07-highlights.md`**, **`src\index\__init__.py`**, **`src\index\schema.py`**,
  **`src\index\selftest.py`**.
- **1 366 não-rastreados e não ignorados** ⇒ **NÃO viajam de todo**, por construção. Entre eles, o
  trabalho mais recente: as specs `05-clip-to-asr.md` (824 B), `06-broadcast-and-capture-card.md`
  (60 096 B) e `07-engine-process.md` (936 B); os módulos `src\ui\` (5 ficheiros / 70 436 B),
  `src\pipeline\` (3 / 80 963 B) e `src\storage\` (3 / 87 991 B); os dois `research\*.md` (39 340 B);
  `_main\logs\handover-wgc-verify-2.txt` (1 654 B); e, até ao commit #2, **o próprio `HANDOVER.md`**.

**As três frases que o leitor do bundle tem de ter na cabeça:**

1. **Rastreado-e-apagado-do-disco VIAJA** (o git guarda o blob; a ausência em disco é local).
2. **Não-rastreado NÃO VIAJA** (não há blob nenhum).
3. **A árvore de trabalho suja VIAJA na sua última revisão COMMITADA**, não na revisão que está em
   disco. Concretamente, e é o caso mais caro: **`src\capture\run_battery.ps1` está sujo** — disco
   **28 290 B** (mtime 13:09:59, sha256 `0E3FAB7AB5FC3C9C7F27566EF3EB8A96C976459A262D836D15F1E082AAE204F9`),
   blob na ponta **23 377 B** — e **a correção do WGC está no DISCO, não no blob** (§3.1). O mesmo
   para **`_main\all-gates.ps1`**: disco **29 247 B** vs blob **22 165 B**. **O commit #2 existe
   precisamente para fechar isto.**

**Não há aqui erro de ninguém: é a lane vizinha a trabalhar na mesma árvore, e eu a congelar um
instantâneo.** A leitura correta do bundle é *"o que estava commitado às 12:26:55, mais a história
que entretanto avançou"* — nunca *"o que estava em disco às 15:25"*.

---

## 6. A HISTÓRIA GIT — e a lane que partilha o repositório

**8 commits, `--all`, do mais novo para o mais antigo (medido às 12:39:06):**
| sha | hora | assunto | de quem |
|---|---|---|---|
| `9cb9eb2` | 12:38:46 | index: bound the search page in SQL instead of slicing the whole corpus in python | outra lane |
| `d96a5a1` | 12:36:10 | driver: classify by MESSAGE, not by exit code | outra lane |
| `a5fd446` | 12:35:39 | index: the searchable clip index (schema, writer, search, migration) + LANE4 gate | outra lane |
| `22c3e42` | 12:30:32 | state: the scheduled fires, as logged | outra lane |
| **`51f84cc`** | **12:26:55** | **freeze: estado do clone Sotto em 2026-10-07 12:2x (entrega transportavel)** | **ESTA lane** |
| `47c020f` | 12:25:47 | PROVEN: a single cron delivers a message like the owner types | outra lane |
| `066005d` | 12:23:02 | wake v4: mcode exec --session is the door; the SQLite queue only validates | outra lane |
| `bae4e1e` | 12:15:43 | wake v3: repaired-row injector, self-waking loop, orchestrator mandate (inicial, 825 ficheiros) | outra lane |

**Cinco commits mais, medidos ~12:55, todos da outra lane — a ponta é `aa06894` e a história tem
13 commits:** `f6d9fe3` (driver: one session, TWO transports; and read the whole error body),
`de068ba` (PROVEN: the cron woke THIS session — CHK-W1 PASS), `4ce26c7` (close the deferred restart
promise as a procedure, not a debt), `d13d423` (**RETRACT receipt-23's headline: the 12:40:54 turn
was hand-pushed** — uma lane a retratar-se por escrito), `aa06894` (cron: retarget the idle session;
prompt over stdin, never argv). **12 dos 13 commits NÃO são meus.** Rastreados: **1 073**.

**Re-medido às 15:25:17 — a história tem 27 commits e a ponta é `87efeaf`** (`lane25: census 18
locale-grouped format sites; 1 defective memory site fixed`). **25 dos 27 commits NÃO são meus** — só
`51f84cc` (o congelamento) e o commit #2 desta entrega o são. A ponta avançou **14 vezes** desde o
congelamento. Isto não é um defeito da entrega: é o preço de congelar um instantâneo de uma árvore
que outra lane está a usar, e é a razão por que §5.2 existe.


**O commit de congelamento é o `51f84cc`:**
`tree_sha = 4f42605b5f4078a34f6adde59bd56f951881b324`, cometido em `2026-10-07T12:26:55-03:00`,
autor `mateusant13 <102630293+mateusant13@users.noreply.github.com>`, **135 ficheiros alterados**.
**Não é um commit raiz** — tem 1 pai. **7 dos 8 commits NÃO são meus.**

**Uma segunda lane partilha este repositório.** Escreve e comete nele ao mesmo tempo (os assuntos
`wake v3/v4`, `single cron`, `index/LANE4` são dela). Consequências, todas registadas:
(a) a ponta **avançou para lá do meu congelamento** quatro vezes depois dele; (b) **não reescrevi
história nenhuma** — o meu commit foi posto por cima; (c) a árvore de trabalho está **suja com 283
entradas** de trabalho dela em curso — **não as varri para o meu commit**.

### 6.1 A "colisão" do `.gitignore` — explicada, e inofensiva

O `.gitignore` foi **criado** por esta lane, **modificado** pela lane irmã às 12:23 (commit
`066005d`) e **reescrito** por esta lane ~12:26 e cometido em `51f84cc`.

`git show 066005d -- .gitignore` mostra a edição `build/` → `build/*` com o comentário da negação.
**Essa era a MINHA própria edição não cometida na árvore de trabalho**, varrida para o commit dela
pelo `git add -A` dela. **Nenhuma regra dela se perdeu**, e a minha reescrita preservou exatamente
esse raciocínio. Está aqui porque um leitor do histórico veria uma lane a editar o ficheiro de
outra e concluiria conflito.

### 6.2 Porque são DOIS commits

Um commit **não pode citar o próprio sha**. O commit #1 (`51f84cc`) é o congelamento do estado.
O commit #2 traz este `HANDOVER.md`, o recibo, e `_main\logs\handover-wgc-verify-2.txt` — ficheiros
que **citam o sha do #1**. É por isso que a história tem os dois, e não um.

**O commit #2 leva também, e isto é o que fecha a divergência de §5.2:**
`src\capture\run_battery.ps1` (o instrumento com a **correção do WGC** que hoje só existe em disco —
blob 23 377 B vs disco 28 290 B) e `_main\all-gates.ps1` (blob 22 165 B vs disco 29 247 B). **Sem
isso, o bundle entrega uma bateria PRÉ-correção**, e quem o clonar mede a coisa errada. **Caminhos
explícitos apenas — nunca `git add -A`** —, e **`AGENTS.md` NÃO entra** (é da lane vizinha e está
sujo; §5.2).

---

## 7. COMO REPRODUZIR — os comandos exatos

Corra tudo a partir da raiz do clone. **Sem janelas visíveis** (a regra da casa) e com **caminhos
`H:\` nativos**.

### 7.1 A bateria de capacidade da captura — o instrumento principal

```powershell
pwsh -File src\capture\run_battery.ps1                 # corrida completa (compila primeiro)
pwsh -File src\capture\run_battery.ps1 -SkipBuild      # reusa o exe já compilado
pwsh -File src\capture\run_battery.ps1 -Reps 5 -Census # estatística apertada + censo de janelas
pwsh -File src\capture\run_battery.ps1 -Root H:\aireplay   # sobrescrever a raiz da árvore
```

Parâmetros: `[string]$Root = 'H:\sotto\_moved\aireplay'`, `[switch]$SkipBuild`.

**O código de saída tem um significado próprio:**
**`0` = a bateria CORREU** (as recusas individuais são resultados, não falhas);
**`2` = não correu de todo** (falta a toolchain). Um `0` **não** quer dizer que todas as linhas
passaram — o rodapé do próprio log diz isso.

**Proveniência:** cada linha é marcada `MEASURED`, `DERIVED` ou `NOT MEASURED`, e **uma linha sem
proveniência é um defeito**. Regras duras mantidas: janelas-filhas escondidas, **nenhum comando
nativo por pipe** (`& exe args > file 2>&1` e depois `$LASTEXITCODE`).

### 7.2 Os oráculos do ASR

```powershell
# o verificador SEM MODELO (não precisa de pesos, não abre dispositivo de áudio)
pythonw.exe _main\asr02-selftest.py

# o oráculo completo do ASR — OS DOIS BRAÇOS DE CONTROLO NUMA SÓ ORDEM
pythonw.exe _main\oracle-02-asr.py
```

O `oracle-02-asr.py` corre o produto **e duas cópias deliberadamente partidas**: o braço B reverte
`DEFAULT_SEGMENT_MODE` para `"fixed"` (o texto tem de COLAPSAR, rácio ≤ 0,50 — a armadilha medida é
0,229) e o braço C reverte `INTRA_OP_NUM_THREADS` para 1 (o contrato de threads tem de FALHAR).
**O veredicto exige os braços do produto VERDES e os controlos VERMELHOS.**

> **ATENÇÃO — não é portável como está.** Precisa de
> `H:\sotto\_main\_redux-long\plain-3600s.wav` (115 200 044 B) e dos oráculos
> `H:\sotto\_main\redux-{en,ptbr}.txt`, que estão **fora do clone**. Ver §4.1.
> O `asr02-selftest.py` **é** portável: é sem modelo e usa as fronteiras gravadas em
> `_main\runs\threads11\silence-t4-p1.json`, que **está** no clone (3 474 B, rastreado).

### 7.3 O índice e a busca

```powershell
python -m index.selftest --arm A --db FICHEIRO
```

Braços registados: `--arm A` (por omissão), o `OLD-SHAPE v0 db migrated ADDITIVELY`, e braços
mutantes que **têm de ficar VERMELHOS**. O `--expect red` inverte o veredicto →
`RED-as-expected`, e é assim que o braço C prova que o gate sabe dizer não.

### 7.4 O gate agregado do clone

```powershell
pwsh -File _main\all-gates.ps1                          # o agregado real
pwsh -File _main\all-gates.ps1 -TimeoutSec 600          # corrida paciente
pwsh -File _main\all-gates.ps1 -Expect _lane01-x-gate   # EXIGE que um gate exista
pwsh -File _main\all-gates.ps1 -SelfTest                # prova que ele sabe ficar VERMELHO
```

### 7.5 O gate agregado da árvore de FORA

```powershell
H:\sotto\_main\_audit-verify-all.cmd
```

**Este ficheiro NÃO existe no clone** — é da árvore de fora, e está aqui porque é o agregado do
projeto Sotto inteiro.

> **TEM DE FICAR CRLF.** O `cmd.exe` procura um ficheiro batch por **DESLOCAMENTO DE BYTES**: com
> terminações só-LF os deslocamentos guardados derivam e a lista de passos corre **DUAS VEZES** —
> medido: a passagem 1 deu `steps : 16 gate=10` VERDE, e depois o cmd retomou e voltou a correr a
> cauda, imprimindo um SEGUNDO resumo `steps : 40 gate=28` — 40 marcas para **29 passos distintos**,
> cada controlo duas vezes, **duas cargas do modelo int8**. O ficheiro hoje é CRLF (337 CRLF /
> 0 LF isolado, sha256 `9DA38ECFCD33C53889458F17087FAF35012AE3BD4B3CCC914384E6B6B3D45BB`).
> **Qualquer ferramenta que o reescreva com `\n` volta a quebrá-lo em silêncio.**

**O código de saída É o veredicto.** Três tipos de passo: `:record` (o gate), `:control` (só passa
se o controlo do instrumento ficou VERMELHO na cópia partida), `:expectred` (rc exatamente 1 com o
texto da violação). **Um instrumento EM FALTA é uma FALHA.** Medido: corrida limpa
`steps : 29 gate=23 control=5 expect-red=1 missing=0 / BATTERY-VERDICT: GREEN / exit-code: 0`;
prova negativa `INJECTED-FAILING-STEP rc=3 … BATTERY-VERDICT: RED … NEGPROOF-EXITCODE=1`.
**Leia o par `BATTERY-VERDICT`/exit-code — nunca o `rc` de um passo isolado, nunca a última linha,
e nunca um `steps :` sem confirmar que só há UM.**

### 7.6 Os highlights

```powershell
pythonw.exe _main\oracle-07-highlights.py
```

Verde: `_main\oracle-07-highlights.log`. Mede 15,00 highlights / 10 min no braço real, 0 de 180 s
de tom e 0 de 180 s de caminhada, com o controlo a disparar sem a conjunção.

### 7.7 Recompilar a captura

```powershell
src\capture\build.cmd
```

---

## 8. O QUE NÃO FOI FEITO, E O QUE NÃO ESTÁ VERIFICADO

Escrito aqui de propósito, para que ninguém leia o resto como mais do que é.

1. **A captura de janelas continua bloqueada.** Nada nesta entrega a desbloqueou. §3.
2. **`RequestAccessAsync(Programmatic)` está por concluir.** Não se sabe se serve. §3.3.
3. **`specs\07-highlights.md` foi APAGADA do disco e não tem módulo em `src/` nem recibo.**
   **`[SUPERADO]`** "não tem módulo nem recibo" continua verdade; a spec é que já não está em disco
   (está apagada mas ainda RASTREADA ⇒ **viaja no bundle**), e `specs\07` é agora
   `07-engine-process.md` (936 B, não rastreado). O oráculo existe e passa. §1.6.
4. **`[SUPERADO]` `src\ui\` está VAZIA.** Era verdade às ~12:55. **Re-medido às 14:4x: 5 ficheiros
   reais, 70 436 B, 0 rastreados** (`hud-shell.py` 29 621, `hud-contract.js` 22 056,
   `hud-panel.js` 7 683, `hud-panel.css` 7 603, `hud-panel.html` 3 473). Continua verdade o que
   importa: **nenhuma linha disto viaja no bundle** (não rastreado) e **o painel PROVADO continua a
   viver só em `H:\sotto\app\panel\`**. §1.4.
5. **A aplicação não está aqui.** `app\` e `worker\` **não existem** neste clone: sem painel, sem
   shell WebView2, sem `run.cmd`, sem os runners de ASR provados, sem os pesos do Redux ternário. É
   a Fusão B a funcionar (§1.8) — não é um esquecimento, e o gatilho de migração tem três condições.
   **O que se reproduz a partir do bundle são as VERIFICAÇÕES (§7), não a aplicação.**
6. **`research\` na raiz do clone (2 ficheiros, 39 340 B) NÃO está rastreado** — apareceu depois do
   meu congelamento (`research\open-source-alternatives.md` 14 648 B, `research\shadowplay-parity.md`
   24 692 B). É trabalho da outra lane, por commitá-la. **O que não está rastreado não viaja no
   bundle**, por construção: o bundle leva história git, não disco. Mesma regra para os **1 365**
   não-rastreados de §5 (eram 515 ao 12:55 — o número cresceu com a árvore).
7. **`[SUPERADO]` Não há spec 06.** Era verdade quando escrito. **Re-medido às 14:4x:
   `specs\06-broadcast-and-capture-card.md` EXISTE, 60 096 B, e não está rastreado.** `specs\` tem
   hoje 01, 02, 03, 04, 05 (`05-clip-to-asr.md`, 824 B, não rastreado), 06 (60 096 B, não rastreado)
   e 07 (`07-engine-process.md`, 936 B, não rastreado). **Dos 7, apenas 01–04 viajam no bundle.**
8. **O ASR não é portável como está** — `constants.py:58` grava `H:\sotto`. §4.1.
9. **As fixtures do muxer não viajam** — as linhas de muxer da bateria precisam de as regerar. §4.1.
10. **A medição é um instantâneo.** A árvore estava QUENTE. Qualquer número aqui pode ter mudado.
11. **`receipt-03-capture-impl.md` §7 regista `LastUsedTimeStop = 11:20:09`** e a releitura dá
    `11:20:47.031`. As duas ficam; a diferença não está explicada. §3.2.
12. **`receipt-22-single-cron-delivers.md` é da outra lane**, não é funcionalidade do produto.
13. **Duas medições do mesmo facto discordaram** porque a árvore crescia entre elas — por isso cada
    número aqui carrega o seu instante.


### 8.1 Uma discrepância de datas, registada e não resolvida

O relógio do sistema lê **2026-10-07**. O `AGENTS.md` do clone e vários documentos estão datados
**2026-10-08**. **O nome do bundle segue o relógio** (`H:\aireplay-20261007.bundle`). A discrepância
fica nomeada — não foi resolvida em silêncio, e não deve ser.

---

## 9. PORQUE O BUNDLE FICA LOCAL — o motivo concreto

**Não há `remote`. Não houve `push`. Não há GitHub. Nada foi publicado.**

O motivo não é decorativo: **`docs\brief-pesquisarsobre.txt` (210 127 B, sha256
`B2A3E4D63E64ADD6196ABE6EB0E59D0BE98F88B51475097A858C86DCBD265337`, blob git
`c9410f1b9942996abd401f693508207012e12313`) é a conversa de investigação PRIVADA do dono, e está
RASTREADA** — ou seja, **viaja dentro do bundle**. Foi verificado: `git ls-files` lista-o.

O `AGENTS.md` do clone manda lê-lo primeiro mas **verificar, nunca herdar**. É material de trabalho
do dono, não documentação para publicar. Enquanto ele estiver versionado, **este repositório não
pode ser empurrado para lado nenhum.**

Antes de publicar alguma vez: decidir o destino do brief, e rever os 51 ficheiros rastreados de
`docs/` com essa decisão em mãos.

---

## 10. PRÓXIMO — por ordem de valor

1. **Desbloquear a captura.** É o único bloqueio duro. O que sobra para investigar: a política diz
   `Allow` e a API diz `E_ACCESSDENIED` (§3.2) — logo o problema **não** está no valor da política.
   Concluir (ou abandonar) a experiência do `RequestAccessAsync` da outra lane, e olhar para o lado
   do processo que **pede** (integridade, token, sessão) em vez do lado da política.
2. **Implementar `src/highlights/`** contra o oráculo que já passa (§1.6) — é o trabalho com o
   melhor rácio esforço/prova: a prova já existe, falta o código.
3. **Tornar o ASR portável:** tirar `H:\sotto` de `src\asr\constants.py:58`, e decidir onde vivem
   as fixtures de áudio (no clone? num caminho configurável?).
4. **O gancho de visibilidade do painel e o agendador horário** — a lei da stack do dono (o motor
   ao vivo só quando o painel está aberto; o Redux quando está fechado) depende destes dois. O
   `AGENTS.md` do clone diz explicitamente: **até isso existir, não corte a captura ao esconder o
   painel.**
5. **`[SUPERADO]` Escrever a spec 06.** A spec 06 **já existe** (`specs\06-broadcast-and-capture-card.md`,
   60 096 B) — o que falta é **rastreá-la**, como às outras duas specs novas (`05-clip-to-asr.md`
   824 B, `07-engine-process.md` 936 B) e aos três módulos novos (`src\ui\` 5 ficheiros / 70 436 B,
   `src\pipeline\` 3 / 80 963 B, `src\storage\` 3 / 87 991 B): **nenhum deles viaja no bundle
   enquanto não estiver commitado.** §5.2.
6. **Reconciliar o índice com o disco antes do próximo bundle.** Há **21 ficheiros rastreados que já
   não existem em disco** (§5.2) — viajam como conteúdo antigo — e **1 365 não-rastreados que não
   viajam de todo**. Um `git add` explícito dos novos e um `git rm` dos apagados resolvem os dois
   lados; **nunca `git add -A`** (a lane vizinha escreve na mesma árvore).

---

## 11. Regras da casa que valem para quem continuar

- **Nunca deixe uma janela de consola visível no ecrã do dono.** Ele já reclamou duas vezes. Use
  `pythonw.exe` ou `CREATE_NO_WINDOW`. **Um censo de 60 s não prova a ausência de uma janela
  curta** — amostre à sua própria cadência quando a afirmação for "não apareceu janela".
- **Um filtro de kill nomeia o ARTEFATO, nunca uma palavra genérica.** Um filtro pela palavra solta
  `sotto` já matou dois processos alheios.
- **Ambas as cores para cada gate.** Um instrumento que não sabe dizer NÃO não vale nada.
- **SKIP não é um passe.** Uma verificação em falta é uma FALHA.
- **A ausência exige um instrumento, não uma impressão** — e nomeie o instrumento, a cadência e a
  contagem.
- **Um "o grep devolveu ZERO" tem prazo de validade.** Volte a correr o grep antes de o citar.
- **Caminhos `H:\` nativos.** `./node_modules/.bin/electron` não executa nesta caixa (rc=127).
- **Nomeie a revisão sempre que citar uma linha** — estas lanes editam os mesmos ficheiros em
  paralelo.
- **EXCLUIR DO GIT NÃO É APAGAR DO DISCO.**

---

## 12. GPU / Execution Providers — a receita que se leva para a outra máquina

**Porque é que esta secção existe, e porque é que ela está ESCRITA AQUI.** O recibo original,
`H:\sotto\_main\receipt-execution-providers.md`, **NÃO está no clone** — verifiquei com
`git ls-files -- _main/receipt-execution-providers.md` (vazio) e um glob sobre `H:\sotto` encontra
exactamente **uma** cópia, na árvore de fora. Como o clone viaja para outra máquina e o recibo não
viaja com ele, a receita accionável fica transcrita aqui. Isto não é uma cópia do recibo: é o que
interessa a quem monta o ambiente do outro lado.

**Nota de revisão, porque há dois números em circulação.** O recibo que li tem **36 099 B** e sha256
`319FD417E934C0A1B4ED22EE5DFB7237537055AD09F999A58306557FA515B484`, mtime **2026-10-07 13:44:50**.
Uma medição anterior, citada a montante, registou **35 167 B** / sha256
`4B0EDCCCA34E9ACEBC9A9DD81E6A35B6F1A29FBEAF061D49C522F4385B99201B` — ou seja **o ficheiro cresceu
932 B depois dessa medição**. Ambos os pares são verdadeiros, em instantes diferentes; o que eu li é o
de 36 099 B. E **o par `rtf 0.0926` / `0.8037` que me foi citado NÃO aparece neste recibo**: um grep
por `rtf 0\.0926`, `0\.8037` e `8 threads` devolveu **ZERO** ocorrências. Os números de velocidade
abaixo são os do recibo que li, não os citados.

### 12.1 Três perguntas, três instrumentos, nunca intermutáveis

Esta é a regra que o recibo isola como a mais importante, e vale a pena levá-la literalmente:

| # | pergunta | instrumento | resposta verbatim |
|---|---|---|---|
| 1 | o **pacote** oferece CUDA? | `ort.get_available_providers()` | `['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']` |
| 2 | a **sessão** usa CUDA? | `InferenceSession.get_providers()` | `["CUDAExecutionProvider", "CPUExecutionProvider"]` |
| 3 | a CUDA **executa** nós, ou só está anexada? | profiler do ORT (`enable_profiling=True`), contagem de eventos `cat=="Node"` por `args.provider` | encoder: **1792 de 1793 nós na CUDA (99,94 %)**, 100,0 % do tempo |

O nível 3 é o único que responde à pergunta que interessa. **Uma sessão pode reportar
`['CUDAExecutionProvider','CPUExecutionProvider']` e correr TODOS os nós na CPU** — foi exactamente o
que o DirectML fez (§12.4). O único nó de CPU no encoder é `Tile`, 94 µs: ruído de fronteira, não
trabalho. `encoder.onnx` pedido em CPU é o **controlo positivo** (1800 nós, 100 % CPU).

### 12.2 A ARMADILHA da instalação — a receita ingénua deixa o ORT em CPU, EM SILÊNCIO

**Este é o achado mais accionável de todo o material, e contradiz a receita que qualquer pessoa
escreveria.** As duas cores foram medidas no mesmo venv (`gpu2`).

**COR VERMELHA — a receita ingénua:**
```powershell
& 'C:\Program Files\Python311\python.exe' -m venv <venv>
& <venv>\Scripts\python.exe -m pip install --no-cache-dir --progress-bar off "onnxruntime-gpu[cuda,cudnn]" onnxruntime-genai
```
O pip instala o `onnxruntime` **simples DEPOIS** do build GPU — porque é dependência dura do
`onnxruntime-genai`. Resultado medido:
- `available: ["AzureExecutionProvider","CPUExecutionProvider"]`
- sessão CUDA real sobre `encoder.onnx` → `REAL_get_providers: ["CPUExecutionProvider"]`,
  **`error: null`**, `load_s: 1.802`
- `UserWarning: Specified provider 'CUDAExecutionProvider' is not in available provider names…`

**O `error` é `null` e a carga "sucede": o ORT fica CPU-only sem dizer nada.** É a pior classe de
falha — não há excepção, não há aviso, só um `null` onde devia estar a dizer que não.

**Prova de propriedade, por RECORD do wheel:**
| dist-info | entradas `onnxruntime/capi/` | entradas `providers_cuda` |
|---|---|---|
| `onnxruntime-1.30.0.dist-info` | 21 | **0** |
| `onnxruntime_gpu-1.30.0.dist-info` | 23 | **1** |

O wheel simples **sobrescreve 21 ficheiros partilhados e deita fora o `providers_cuda`**. Os três
pacotes instalam-se no **mesmo namespace `onnxruntime`** e quem ganha é **a ORDEM do pip** — último
escritor ganha, ficheiro a ficheiro.

**COR VERDE — a correcção, uma linha, no MESMO venv:**
```powershell
& <venv>\Scripts\python.exe -m pip install --no-cache-dir --progress-bar off --force-reinstall --no-deps onnxruntime-gpu==1.30.0
```
→ `available: ["TensorrtExecutionProvider","CUDAExecutionProvider","CPUExecutionProvider"]` e sessão
`["CUDAExecutionProvider","CPUExecutionProvider"]`, `error: null`, `load_s: 2.254`, stderr
`CUDA_DLL_DIRS: applied`. **A única variável era a ordem de instalação.** Os extras `[cuda,cudnn]`
fizeram o seu trabalho: `nvidia-cublas 13.8.0.4`, `nvidia-cudnn-cu13 9.27.0.42`, `nvidia-cufft
12.4.0.43`, `nvidia-curand 10.4.4.72`, `nvidia-cuda-nvrtc 13.4.92`, `nvidia-cuda-runtime 13.4.92`,
`nvidia-nvjitlink 13.4.92`, com `…\nvidia\cu13\bin\x86_64\cublasLt64_13.dll` a **493 474 416 B**.

**Detalhe que engana:** o METADATA do `onnxruntime-gpu 1.30.0` declara o runtime CUDA como **extras
OPCIONAIS** — daí a armadilha ser invisível numa revisão de `pip install` a olho.

### 12.3 As DUAS falhas distintas — não as confundir

1. **A do pip (acima):** o provider **não está listado de todo**, e o erro é **`null`**.
2. **A do DLL:** o provider **está listado** mas falha a inicializar — `cublasLt64_13.dll`,
   **WinError 126**, numa shell limpa. Cura: pôr `site-packages\nvidia\cu13\bin\x86_64` no DLL search
   path. **O `torch\lib` é CUDA 12 e NÃO serve este DLL.** O worker de produção já faz isto:
   `worker/sotto_worker.py:277` (`_add_cuda_dll_dirs()`), chamado de `:3251` antes da carga do modelo.

### 12.4 DirectML: uma LIMITAÇÃO CONHECIDA, não um TODO

**O DirectML não pode embarcar hoje, e a parede não é nossa.** O `encoder.onnx` tem **220
ocorrências do domínio `com.microsoft`** — `MatMulNBits`, `CausalConv1D`, `ConformerConvolution`,
`ConvSubsampling`, `MaskedConvSequential`, `RelPositionMultiHeadAttention`, … O DML carrega o *joint*
e o `silero_vad`, mas **não compila o encoder**: devolve **`E_INVALIDARG` (0x80070057)** no autor de
operadores do DML. A cadeia mede-o e desiste em silêncio:
`EP_CHAIN chosen=CPUExecutionProvider available=DmlExecutionProvider,CPUExecutionProvider` /
`trace=DmlExecutionProvider:silently-dropped (session fell back to ['CPUExecutionProvider'])`.

**Escreva-se como limitação conhecida.** Não é um caminho mais lento: é um caminho que **não existe**
enquanto o encoder usar `MatMulNBits` e os restantes ops `com.microsoft`. O que desbloquearia o DML
está identificado no recibo: suporte do DML a `MatMulNBits` e aos restantes ops do encoder.

### 12.5 O que se GANHA com CUDA — os números do recibo, não os citados

Medidos nesta caixa (RTX 5080):
- **CPU 4 threads:** 6,68–8,11 **core·s por audio·s**; headroom live **1,19–1,35×** — marginal.
- **CPU 8 threads** (o default automático do worker, `min(8, 20//2)` = 8): **671,79 ms** de chunk
  mediano contra **560 ms** de chunk de áudio = **0,83× — NÃO acompanha o tempo real.**
- **CUDA 4 threads:** 0,51–0,60 **core·s por audio·s**; headroom live **8–10×**.
- **RAM de host:** a CUDA usa **~423 MB MENOS de RSS** (1665,6 vs 2089,2) — o custo é **disco**, não
  RAM — e carrega **4× mais rápido**.

**Núcleos devolvidos à máquina: ~6 a ~14**, conforme o braço de CPU contra o qual se compara. Isto é a
cura do congelamento que o dono reportou, e a razão pela qual **com GPU funcional a reserva de ~5–8
núcleos do ASR pode ser levantada.** A joelheira `intra_op_num_threads=4` foi medida **na CPU**; com
GPU a joelheira muda de sítio.

**A cadeia de fallback — as quatro cores, medidas.** Existe uma cadeia de 4 braços, e o braço forçado
(`--force-fail 0`) foi testado: a cadeia **desce e ainda transcreve**. **O que a cadeia NUNCA pode
fazer:** usar `get_available_providers()` para decidir o que foi usado.

### 12.6 Onde isto vive no código de produção

`worker/sotto_worker.py`: `choose_providers(requested, model_dir=None)` em **`:1734`** →
`(providers, available, note, probed_model)`, com a sonda de vivacidade CUDA em **`:1788-1800`**;
chamado de **`:3253`**, depois de `_add_cuda_dll_dirs()` em `:3251`; `providers_selected=providers` em
`:3262`. As três notas de diagnóstico: `:1795 "cuda-registered-but-not-loadable"`,
`:1800 f"cuda-unavailable: {type(exc).__name__}: {str(exc)[:160]}"`, `:1802 "cuda-not-registered"`.
`StreamAsr.__init__` em `:458`; **`self.providers = self.enc.get_providers()` em `:505` — o real, não
o disponível.** `state="model-loaded"` com `providers=asr.providers` em `:3290-3297`.
**`worker/config.json` linha 14:** `"providers": ["CUDAExecutionProvider", "CPUExecutionProvider"]`.

> **Nomeie a revisão.** Estas linhas são do `sotto_worker.py` no instante em que o recibo foi escrito.
> O ficheiro move-se de hora a hora (§11) — **re-corra o grep** antes de agir sobre um número de linha.

### 12.7 O que fazer na máquina nova — a ordem que evita a armadilha

```powershell
# 1) instalar (a ordem do pip é a armadilha; a correcção vem logo a seguir)
pip install "onnxruntime-gpu[cuda,cudnn]" onnxruntime-genai
# 2) A GUARDA — sem esta linha o passo 1 pode ter deixado o ORT em CPU, com error: null
pip install --force-reinstall --no-deps onnxruntime-gpu==1.30.0
# 3) o VEREDICTO é este, não o passo 1
python -c "import onnxruntime as ort; print(ort.get_available_providers())"
#    esperado: ['TensorrtExecutionProvider','CUDAExecutionProvider','CPUExecutionProvider']
```

**Não instalei nada nesta caixa** para escrever esta secção — o worker aqui **já corre com CUDA**
(`providers_selected:["CUDAExecutionProvider","CPUExecutionProvider"]`). Isto é uma **receita para o
clone**, transcrita do recibo, não uma alteração feita aqui.

### 12.8 O que NÃO está verificado nesta secção

- **Não reproduzi as medições** — leio-as do recibo (§12.0, nota de revisão). O que fiz foi ler o
  ficheiro e transcrever, com os números e os caminhos como lá estão.
- **O par `rtf 0.0926` / `0.8037` que me foi citado não existe neste recibo** (grep = ZERO). Se ele
  vier de outra medição, **essa medição não é este ficheiro** — e um "grep devolveu ZERO" tem prazo de
  validade (§11): re-corra-o antes de o citar.
- **O recibo NÃO viaja no bundle.** Quem continuar na máquina nova tem esta secção; quem quiser o
  recibo inteiro tem de o copiar de `H:\sotto\_main\` **com o sha256 registado no momento da cópia**.

---

## 13. Diarização — veredicto FECHADO: **NÃO** no loopback misturado

**Isto é uma decisão de produto com um número por baixo, não uma opinião.** A pergunta do dono foi se
existe um modelo que separe o áudio por pessoas e, ao separar, corra o Parakeet Redux por cima. A
resposta medida é **não** — no loopback misturado. A §13.4 diz qual é o caminho, e ele é mais barato.

**Fontes, e o estado delas em relação a ESTE clone.** As duas vivem **só na árvore de fora**
(`H:\sotto\_main\`), **não** no clone — verificado com `Test-Path` nos dois caminhos e
`git ls-files` no clone (vazio):

| artefacto | onde existe | tamanho | sha256 (verificado por mim) |
|---|---|---|---|
| `_main\receipt-diarization-decisive.md` | **só `H:\sotto\`** (359 linhas, mtime 2026-10-07 14:11:26) | 28 470 B | `CD754B40C6D2D780ECFE5D69DC4129D8C341403D1BFDCE99D764A26C97FDBFF3` |
| `_main\live-sample-cable-input-90s.wav` | **só `H:\sotto\`** (mtime 2026-10-07 12:24:44) | 17 280 080 B | `E156BDE92F4AA63F09FF94F316AB85397D0D80419BF9F90144839075BD25295C` |

**Os dois hashes conferem com os que me foram citados.** O `.wav` é 90 s de **48 kHz, 2 canais,
16 bits** (90 × 48 000 × 2 × 2 = 17 280 000 B + 80 B de cabeçalho) — aritmética que fecha com o
tamanho em disco, e que confirma ser o loopback do `CABLE Input` à taxa nativa. **Nem o recibo nem o
áudio viajam no bundle** (o `.wav` seria ignorado de qualquer forma: `.gitignore:159` = `*.wav`).
Quem continuar na máquina nova tem esta secção; para reabrir a medição tem de copiar os dois
artefactos **com o sha256 registado no momento da cópia**.

### 13.1 A medição que fecha a porta — DER ≈ **61,6 %** no áudio do dono

O ficheiro do dono tem uma razão **fala-leito de +2,62 dB**. A curva abaixo foi medida com o **leito do
próprio áudio do dono** como alvo, com **SNR verdadeira nos frames de fala**:

| SNR verdadeira | DER medido |
|---|---|
| +19,54 dB | 0,03 % |
| +15,33 dB | 2,98 % |
| +7,74 dB | 21,88 % |
| +4,07 dB | 48,38 % |
| +1,51 dB | 71,77 % |
| **+2,62 dB (o áudio do dono)** | **≈ 61,6 % (interpolado)** |

**61,6 % é ~2,5× o limiar de morte de ~25 % que foi declarado ANTES da medição** — o limiar foi
pré-registado, não escolhido depois de ver o resultado, e é isso que faz disto uma refutação e não um
número escolhido a dedo.

**E é um LIMITE INFERIOR.** Collar zero, mapeamento óptimo de falantes: as duas escolhas que *ajudam*
o diarizador. Com as convenções normais da métrica o número é **pior**, nunca melhor. Se uma leitura
fácil quiser salvar a diarização, tem de o fazer contra um limite inferior de 61,6 %.

**Uma cautela que NÃO se pode saltar:** não escreva que o leito é **"música"**. Não existe música no
repo, e **o classificador de leito falhou o próprio controlo negativo** — ou seja, o instrumento que
distingue "música" de outra coisa não provou que sabe fazê-lo. O que está medido é mais estreito e
suficiente: **um leito contínuo, não-fala e alto, onde TANTO o Redux QUANTO o pyannote não acham
fala, enquanto ambos acham fala em 29,5–49,4 s do mesmo ficheiro.** Dois diarizadores independentes
a concordar que ali não há fala — isso é o achado.

### 13.2 O segundo assassino — a instabilidade do botão (independente do leito)

**Mesmo com áudio LIMPO, o diarizador não é utilizável com o botão por omissão.** Com o threshold por
omissão da API (0,5), no mesmo áudio limpo:

| precisão | DER | clusters encontrados |
|---|---|---|
| fp32 | **28,85 %** | 7 (em vez de 4) |
| int8 | **33,24 %** | 7 (em vez de 4) |

Só com **0.9** é que os **4** clusters voltam. **Não há verdade-terra no áudio do dono para escolher o
botão** — e sem verdade-terra para calibrar, **a INSTABILIDADE é a medição.** Não é "escolha-se o
threshold certo": é que o threshold certo é um parâmetro que não temos como fixar neste áudio, e um
diarizador cuja contagem de falantes oscila entre 4 e 7 conforme um botão não é uma base para correr
um transcritor por cima.

### 13.3 O vocabulário é MORTO — `<|spkchange|>` não dispara

O Redux **tem** o token no vocabulário. Os pesos não o usam:

- `<|spkchange|>` **id 14** → **0 ocorrências em ~2 100 passos greedy**, em **3 ficheiros**, incluindo
  **um com 4 falantes conhecidos**.
- `max_prob` **1,9e−7 a 1e−12**; melhor **rank 267–847**; **0 passos no top-5**.

**O controlo positivo que faz disto AUSÊNCIA e não impressão:** forçar o prompt a `<|diarize|>`
(semente 12) **não acorda** o id 14 — mas as sementes **12/13/15 MUDAM o `tokens_sha256`**, o que
prova que **o prompt está vivo** e que a ausência não é um instrumento morto a olhar para o lado.
Sem esse controlo, "0 ocorrências" seria só um grep.

**Conclusão:** a diarização **não sai de graça do Redux**. **Capacidade no vocabulário ≠ capacidade
nos pesos** — e é por isso que "o token existe" nunca foi argumento.

### 13.4 A resposta de produto: **captura por participante**

No loopback misturado, **não**. O caminho é **captura por participante** — e a razão é que nos
clientes reais (**Discord, Teams, Zoom, Meet**) **cada cliente já envia o seu próprio microfone**:
os fluxos estão separados **a montante**. Consequência, e é a parte boa: **é de graça, é melhor
áudio, e não precisa de separação nem de diarização.** O trabalho de diarização desaparece por não
ser necessário, não por ser difícil.

**Defeito de instrumento a registar, para quem reutilizar o sherpa:** as etiquetas que ele emite são
**`spk0, spk1, spk3` com `n_speakers=3`** — **`spk2` NÃO existe.** Qualquer consumidor que assuma
`range(n)` sobre estas etiquetas vai indexar um falante que não está lá. Trate as etiquetas como
**identificadores opacos**, nunca como índices.

### 13.5 GPU **não** é lei — e as duas medições ficam lado a lado

**Para o sherpa, a CUDA é MAIS LENTA que a CPU.** Comparação **emparelhada A/B/A/B intercalada** (não
duas execuções separadas), no áudio do dono: mediana **1,6429× mais lento** na GPU, RSS **1251 MB vs
369 MB (3,4×)**, CPU **~95 % de 1 core vs ~200 % (2 cores)**, com saída **byte-idêntica**
(sha256 canónico `5E341679652D8DC7` nas **6 arms**).

**Isto NÃO contradiz os 7,29–8,74× do nemotron no ORT** (§1.1: int8 a 4 threads, 7,29× fixo / 8,74×
alinhado a silêncio). As duas afirmações são verdadeiras ao mesmo tempo, e é isso que se leva:

> **"GPU é mais rápida" não é uma lei — é uma medição por runtime e por grafo.**

Quem generalizar de um destes números para o outro vai errar. Escreva os dois lado a lado.

**A armadilha de método que expôs isto, e que vale mais que o número:** numa caixa **carregada**, um
A/B entre execuções mede a **CARGA**, não a variável — **a mesma arm deu RTF 0,1534 e 0,0798, um
factor de 1,9**. A cura é **intercalar (A/B/A/B) e reportar a dispersão emparelhada**; sem isso a
afirmação não vale nada, por muito limpo que o número pareça.

### 13.6 Duas armadilhas de Python que se generalizam

**(a) `os.add_dll_directory()` REMOVE o directório outra vez quando o handle é recolhido pelo GC.**
Descartar o valor de retorno **desfaz a chamada EM SILÊNCIO** — o código parece certo, corre sem erro,
e o DLL não está lá. **Manter os handles vivos numa lista.** (É o mesmo tipo de silêncio do §12.2: a
falha não levanta nada.)

**(b) `dirname(dirname(os.__file__)) + "site-packages"` nomeia um directório que NÃO EXISTE.** Usar
**`sysconfig.get_paths()["purelib"]`** — e **imprimir sempre o número de directórios retidos**, para
que "apliquei os caminhos" seja um número e não uma intenção.

### 13.7 O que mudaria a resposta, o que está morto, e o que não foi medido

**Mudaria a resposta:** SNR verdadeira **acima de ~+15 dB** (onde a DER medida é **2,98 %**), ou
**captura por participante** (§13.4).

**Instrumentos mortos — NÃO reutilizar:**

| instrumento | estado |
|---|---|
| `_diar-bed-analysis.py` | **desqualificado** — falhou o próprio controlo negativo |
| `_diar-gpu-watch.ps1` | **cego** |
| `_diar-provider-probe.py` | **abandonado**, exit 1 |

**Não medido, declarado como não medido:** a **DER no áudio do dono** (não há verdade-terra — o 61,6 %
é interpolação da curva, §13.1), **áudio acima de 90 s**, e **música real**.

---

*Fim. Se este documento contradiz a máquina, a máquina tem razão — meça de novo.*
