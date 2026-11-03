# Recibo — as três ordens dele de 2026-11-02 (foreground, áudio, GPU)

Instrumento: esta sessão, a máquina dele. Tudo abaixo é medido nesta caixa, hoje.

## 1. "para de abrir janela de terminal em foreground" / "anota no agents.md"

**Causa medida:** era a lane. `cmd /c "_main\_audit-verify-all.cmd"` e
`powershell -NoProfile -Command …` largados de dentro da sessão alocam uma consola
por invocação; o dono viu as janelas a abrir e a desaparecer. Não há `.vbs` no repo
(grep por `wscript`/`WScript` → só `_main/start-menu-shortcut-gate.py`, que apenas
o LÊ de um atalho).

**O que ficou:**

| peça | caminho | prova |
|---|---|---|
| helper de largada | `_main/hidden-launch.py` | `--selftest`: filho python com `GetConsoleWindow()=0`; stderr chega (`rc=3`); powershell `-WindowStyle Hidden` responde |
| portão | `_main/console-window-gate.py` | `findings=12 baseline=12 new=0` → `VERDICT: GREEN`; `--neg-arm planted=1 caught=1` |
| regra | `AGENTS.md` §HARD RULES, "NADA EM FOREGROUND" | — |

**As 12 chamadas que existiam** (congeladas em `_main/console-window-baseline.json`)
foram todas corrigidas: `keepalive.py`, `agents-md-pins-oracle.py`,
`start-menu-shortcut-gate.py`, `_app-census.py`, `_app-drive.py`, `_anim-cost2.py`,
`_exit-latency-probe.py`, `_lane-profile-census.py`,
`preflight-refusal-visible-oracle.py`, `redux-live-cost-attribution.py`,
`redux-live-latency-probe.py`, `redux-live-window-census.py`.
Depois do trabalho o baseline está em **0** e o portão continua GREEN — a dívida não
cresce, e nenhuma chamada nova passa sem `CREATE_NO_WINDOW`/`startupinfo`.

## 2. "nunca mais roda nada que vai mutar meu audio ou resetar ele"

**Estado encontrado:** `muted_true=1` (`AG251F1WG2 (NVIDIA High Definition Audio)`),
`scalar0=2` — `Speakers (NVIDIA Broadcast)` e `Microfone (NVIDIA Broadcast)` a **0.0**.
O `_main/mute-audio-state.json` estava vazio: o instrumento não tinha registo do que
mudou, porque uma corrida da bateria foi morta a meio e o `finally` nunca correu.
Contrariado com a ordem: ele ouviu a máquina calada sem a ter calado.

**Reparação executada** (uma única escrita, com o valor antes/depois registado):
`Speakers (NVIDIA Broadcast)` 0.0 → 1.0, `Microfone (NVIDIA Broadcast)` 0.0 → 1.0.
Censo depois: `muted_true=['AG251F1WG2 (NVIDIA High Definition Audio)']`, `scalar0=[]`.
O mute que resta é uma **flag** de um monitor, que este instrumento não sabe pôr —
fica nomeado, não atribuído a mim.

**O que ficou:**

| peça | o que faz | prova |
|---|---|---|
| `_main/mute-audio.py` | `--mute`, `--unmute`, `--repair` **recusam** com `rc=9` + `recusa: audio do dono` sem `SOTTO_OWNER_AUDIO_OK=1`; ler (`--status`, `--status-all`, `--journal-status`) é livre | 4 invocações medidas: ler `rc=0`, escrever `rc=9` |
| journal | `audio-journal.json`: o volume ANTERIOR é escrito **antes** da escrita; `--repair` devolve-o e limpa | arm `journal-before-write` (`prior_scalar=0.42`) e `repair-restores-recorded-value` (`volume=0.42`) |
| portão | `_main/owner-audio-gate.py` | 6 arms `caught=6`; `--neg-arm` remove a guarda numa CÓPIA e exige a recusa desaparecer → `caught=1`. Nenhum arm escreve num endpoint real: o backend é um dicionário |
| oráculos de áudio | `mute-audio-oracle.py` e `device-silence-oracle.py` saem com `VERDICT: SKIPPED` sem a bandeira (medido: `rc=0` nos dois) | passos da bateria passaram a `:skipped` |
| regra | `AGENTS.md` §HARD RULES, "O ÁUDIO DO DONO NÃO SE TOCA — NUNCA" | — |

## 3. "1,7x realtime? ta certo isso? veja se tua implementacao ta errada"

**Medido no mesmo ficheiro (`worker/assets/sample1.flac`, 13,44 s) e no mesmo código:**

| onde | tempo | ×tempo real | ms/chunk (560 ms) |
|---|---|---|---|
| RTX 5080, `CUDAExecutionProvider` | 1,25 s | **10,75×** | 52 |
| idem, com a bateria a correr em paralelo | 1,71 s | 7,85× | 71 |
| `CPUExecutionProvider` | 5,92 s | 2,27× | 247 |
| o `--selftest` citado no relatório | 7,91 s | 0,59× | 330 |

O número que eu reportei era **de máquina ocupada**, não do modelo. O modelo é o
`nemotron-3.5-asr-ptbr-onnx-int4` (encoder 690 MB), não o parakeet; o parakeet int4
já estava medido em 6,83× (`docs/factos-medidos.md`).

**O defeito real que a pergunta expôs:** `onnxruntime 1.30` precisa de
`cublasLt64_13.dll` (CUDA 13) + cuDNN 9, que existem **dentro** dos wheels
(`site-packages/nvidia/cu13/bin/x86_64/`, `site-packages/nvidia/cudnn/bin/`) e não
no PATH. Sem `_add_cuda_dll_dirs()` antes da primeira `InferenceSession`, a sessão
cai para CPU com um aviso que **não é fatal** e que o log do worker vivo mostra:

```
[W:onnxruntime ...] No registered plugin EP device found for 'CUDAExecutionProvider' with device_id=0
```

Com as pastas registadas: `asr.providers=['CUDAExecutionProvider','CPUExecutionProvider']`
e 10,75×. A função já existe (`sotto_worker.py:477`, chamada em `:4979`, antes de
`choose_providers`), portanto a escolha do caminho está certa — o que faltava era
**visibilidade**: a shell guardava só `STATUS_APPLIED text="model-loaded"` e o
payload com `providers_selected` era descartado.

**O que ficou:** a shell passou a escrever
`WORKER_PROVIDERS selected=… available=… note=… cuda_probe=…`
(`app/webview/sotto_webview.py`, ramo `stage=providers`), e
`_main/worker-providers-oracle.py` julga essa linha: um provider de GPU
**disponível e não escolhido** é `RED` (é o fallback silencioso de hoje); linha
ausente é `SKIPPED`, nunca verde; caixa sem GPU é `PASS` honesto.
`--neg-arm` corre os três casos pela **mesma** `judge()` que publica o veredicto:
`cases=3 caught=3`.

## A bateria

`_main/_audit-verify-all.cmd` = **170272 B**, **2167 CRLF** / 0 bare LF, sha256
`9DFEF8F658F35B0B655507973893EB819693FAD4F6195819FEBE32542BE8F4FA`; o portão do pin
(`_main/agents-md-pins-oracle.py`) confirma os dois pins com leitura ao vivo.

Passos novos: `console-window-gate` + `red-as-expected-console-window-gate`,
`owner-audio-gate` + `red-as-expected-owner-audio-gate`, `worker-providers` +
`red-as-expected-worker-providers`; `mute-audio`, `device-silence` e o seu negativo
passaram a `:skipped`.

## 4. Onde o tempo do worker vai (perfil, não palpite)

O `worker/sotto_worker.py` passou a medir **três estágios** por chunk —
`stage_s = {pre, enc, dec}` — publicados no payload do `--selftest` e somados sem
sobreposição (`pre` = front end + Silero VAD, `enc` = sessão do encoder, `dec` =
walk guloso). Medido, `sample1.flac` (13,44 s), RTX 5080, três corridas:

| estágio | tempo | fatia |
|---|---|---|
| `enc` (encoder) | 2,04–2,62 s | **~87 %** |
| `dec` (decoder + joint) | 0,23–0,25 s | ~10 % |
| `pre` (front end + VAD) | 0,04–0,06 s | ~2 % |
| total | 2,3–2,9 s | 4,6–5,8× tempo real |

O primeiro número que eu publiquei (1,25 s / 10,75×) **não é reprodutível**: as
corridas repetidas na mesma máquina dão 2,3–2,9 s. O que fica como afirmação é a
faixa reprodutível, não o melhor caso isolado — 330 ms medidos antes eram de
máquina ocupada e 1,25 s foi de uma corrida que não voltou a repetir.

**Teto do arena CUDA custava 18 %** (tudo o resto fixo):

| `SOTTO_CUDA_MEM_LIMIT_MB` | `enc` | total |
|---|---|---|
| 4096 (era o default) | 3,256 s | 3,719 s |
| 8192 | 2,927 s | 3,343 s |
| 0 (sem teto, **agora o default**) | 2,662 s | 3,161 s |

`kSameAsRequested` já cresce pelo que é pedido, e o modelo int4 pede ~1 GB: o teto
não protegia nada e custava 18 % num estágio que é 87 % do tempo. O ambiente
continua a poder repô-lo.

**TensorRT foi tentado e não está disponível:** `onnxruntime` responde
`Please install TensorRT libraries` e cai para CUDA. Fica nomeado como o lever
seguinte (o encoder é conv-pesado), com o custo do download por decidir pelo dono.
Aviso do próprio ORT, medido no perfil: `2 Memcpy nodes are added ... might have
negative impact on performance (including unable to run CUDA graph)` — o próximo
passo técnico é IOBinding + CUDA graph, não mais um provider.
