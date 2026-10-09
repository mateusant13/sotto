# Recibo — varredura do áudio AO VIVO do dono

**Data:** 2026-10-07, 12:56 (BRT) · **actualizado 13:4x** após a revisão do worker mudar a meio da
varredura (§1.1, §4.5) · **Lane:** MEDIÇÃO (`_main/`) · **Repo:** `H:\sotto`

**Pedido do dono, verbatim:** *"deixei uma live rolando. testa tudo que tu precise do app, pelo
som da live que ta tocando agora. ah, e tambem garanta que o removedor de ruido esteja
funcionando"*

**Regra respeitada do princípio ao fim: nenhum processo do dono foi tocado.** Medido no fim da
varredura (`Get-Process`), com os tempos de arranque **inalterados**:

| pid | nome | arrancou | cpu_s | rss_mb |
|---|---|---|---|---|
| 29008 | python (o worker) | 2026-10-07 **08:01:56** | 16,2 | 446 |
| 28428 | pythonw (o shell) | 2026-10-07 **08:01:55** | 130,2 | 98 |
| 32276 | voicemeeter | 2026-10-07 08:02:46 | 843,7 | 37 |

Nada foi morto, reiniciado, nem pedido para reiniciar. **Nada foi instalado.**

---

## 1. Como obtive o áudio ao vivo

### 1.1 A revisão em causa (nomear a revisão, regra 2 do AGENTS)

| ficheiro | bytes | linhas | mtime | sha256 |
|---|---|---|---|---|
| `worker\sotto_worker.py` (**código NO disco**, já com a correção da palavra partida e com o medidor a 10 Hz) | **242082** | 4593 | 07/10/2026 13:09:59 | `64E7EC6F6C35C33600E9D50C11AC7D8CE96FBE1FEF87C24CD628BDF03F314E61` |
| `app\webview\sotto_webview.py` (o shell, com o ramo `meter` real) | **397180** | **7930** | 07/10/2026 13:09:59 | `EA014D8F2CACD72E76668175EB46B327A6F98E74A7A9F76BE1C8D2BE94B9DB81` |

**Revisões citadas nesta varredura, e qual delas foi realmente executada — sem ambiguidade:**

- O A/B de palavras partidas foi **executado pela primeira vez** contra a revisão do worker
  **237489 B / sha256 `29E4CBFA71C1AC6DE5FA1C051C0FFFD63B1BC28E6AE214D52FC27AAE56380EA9`** e
  **re-executado** contra a revisão acima (**242082 B / `64E7EC6F…`**). Os dois veredictos são
  **idênticos** (ver §4.4). Onde este recibo citar números de linha do worker, são da revisão
  **242082 B / `64E7EC6F…`**.
- Números de linha do shell: são da revisão **397180 B / `EA014D8F…` / 7930 linhas** — **não** os
  "7 199 linhas" que o `AGENTS.md` associa a este mesmo sha256; a contagem directa
  (`(Get-Content …).Count` e a ferramenta de leitura) dá **7930**, e o `AGENTS.md` está desactualizado
  nesse ponto. Ficheiros e linhas foram movidos por outras lanes durante a varredura; cada citação
  abaixo traz o sha256 para poder ser re-conferida.

**O worker do dono (pid 29008, arrancou 08:01:56) corre uma revisão ANTERIOR a esta.** Ou seja: o
que ele produz no ecrã do dono é o comportamento **PRÉ-correção**. Isto é a base das duas cores
do ponto 4 e do ponto 5.

### 1.2 Enumeração de endpoints — sem abrir stream nenhum

**Instrumento:** `_main\live-audio-sweep-endpoints.py` (4181 B, sha256 `92E91F03…C4D74`), que usa
`IAudioMeterInformation` sobre **todos** os endpoints ACTIVE de render (flow 0) e captura (flow 1)
e devolve o `meter_peak` de cada um **sem abrir** `IAudioClient`.
**Cadência/contagem:** `meter_ms=0.5`, wall 5,117 s, 5 endpoints de render + 5 de captura.
**Saída:** `_main\live-audio-sweep-endpoints.out` (3451 B, sha256 `FF84E0F1…7D731`).

| direção | endpoint | id | formato | `meter_peak` |
|---|---|---|---|---|
| render | **CABLE Input (VB-Audio Virtual Cable)** | `{0.0.0.…}.{2f1295af-8529-4f15-b00d-7b9bba575ac0}` | 48000/2ch/32bit tag3 | **0,09956735372543335** |
| render | Speakers (NVIDIA Broadcast) | — | — | 0,0 |
| render | VoiceMeeter Input (VB-Audio VoiceMeeter VAIO) | `{…}.{55395a4e-97b2-4b96-9878-18be1ed894e0}` | — | 0,0 |
| render | AG251F1WG2 (NVIDIA High Definition Audio) | — | — | 0,0 |
| render | Alto-falantes (HyperX Quadcast) | — | — | 0,0 |
| captura | **CABLE Output (VB-Audio Virtual Cable)** | `{0.0.1.…}.{06d9db41-6dbb-4d3c-ad69-8a198ecffa0b}` | 44100/2ch/32bit | **0,12680435180664062** |
| captura | Microphone (HyperX Quadcast) | — | — | 0,000091552734375 |
| captura | Microfone (NVIDIA Broadcast) | — | — | 0,0 |
| captura | Microphone (HD Pro Webcam C920) | — | — | 0,0 |
| captura | VoiceMeeter Output (VB-Audio VoiceMeeter VAIO) | `{…}.{ebe3d739-…}` | — | 0,0 |

**Leitura:** o único caminho que carrega áudio é o par VB-Cable
**`CABLE Input` (render) → `CABLE Output` (captura)**. O VoiceMeeter está a correr mas **NÃO está
no caminho do áudio** — contradiz a nota antiga do AGENTS de que a saída predefinida é o
`VoiceMeeter Input`. E confirma o worker do dono: `panel-state.json` → `worker.device.device =
"CABLE Output (VB-Audio Virtual "`.

### 1.3 O conflito de endpoint — e como o evitei

O worker do dono segura **`CABLE Output`** (o lado de CAPTURA). Eu **não abri esse endpoint**.
Escolhi o **lado de RENDER da mesma cable, `CABLE Input`, em loopback WASAPI** — é o mesmo áudio
(é o par da mesma cable) e é um endpoint **diferente**, portanto não disputa nada com ele.

**`AUDCLNT_E_DEVICE_IN_USE` (`0x8889000A`) NUNCA foi encontrado nesta varredura.** Não posso
reportá-lo como medido, porque não o medi — não é uma omissão, é o resultado.

**Instrumento:** `_main\live-audio-sweep-tap.py` (7180 B, sha256 `B7C84AFF…0F0E3`). Abre um tap
`WasapiLoopbackTap` sobre o endpoint pedido, grava WAV float32 mono à taxa nativa (48 kHz),
**fecha o tap num `finally`** e volta a ler os medidores para provar a libertação. Reporta
`silent_packets` / `position_gap_packets`.

**Duas amostras gravadas, ambas com o tap fechado no fim:**

| ficheiro | bytes | sha256 | duração | utilizável? |
|---|---|---|---|---|
| `_main\live-sample-cable-input-90s.wav` (**PRIMÁRIA**) | **17280080** | **`E156BDE92F4AA63F09FF94F316AB85397D0D80419BF9F90144839075BD25295C`** | **90,0 s** | **SIM** |
| `_main\live-sample-cable-input.wav` | 5779280 | `CCB2222114B26CE88206179BA44CA27917B55C3DF9C133A53A4909B69917B597` | 30,1 s | **NÃO** — ver abaixo |

**Ficha da amostra primária:** 48000 Hz, mono, float32, 4.320.000 amostras, 900 blocos × 100 ms,
`peak` **0,389779**, `rms` **0,02484669**, `nonzero_blocks` **900/900**, `distinct_block_peaks`
**894**, `silent_packets` **0**, `position_gap_packets` **12**, wall **90,161 s**, `closed: true`.

**A amostra de 30 s é INUTILIZÁVEL e digo porquê:** as duas cores do A/B produziram a **mesma
linha única** `"fazer um Plan do T"` (`tokens: 8`, `blank_frac: 0,9608`, `vad_gated_chunks: 25`) —
o VAD Silero julgou aquela janela como não-fala, logo o teste era **vazio**. É por isso que gravei
os 90 s: o perfil da banda de voz (300–3400 Hz) por 2 s mostra fala forte em t≈30–50 s
(rácio 4,773 em t=30,0; 3,505 em t=44,0; 2,771 em t=48,0) e silêncio em t=0–28 e t=52–88
(rácio ≈0,13–0,74). O `peak` não distingue os dois regimes; a banda de voz distingue.

**Libertação do tap, medida:** `meter_after_close` de `CABLE Input` = 0,11902612447738647 — o
endpoint continua a renderizar e o meu cliente já não está lá.

**A cor de CONTROL (tap sobre `VoiceMeeter Input` em loopback) abriu mas entregou 0 blocos.** É
não-vazio mas é mais fraco do que "peak 0", e reporto-o como o que é: o Windows só alimenta um
cliente de loopback enquanto o endpoint renderiza.

### 1.4 O caminho AO VIVO dentro do worker, sem abrir device

Para exercitar o **pipeline ao vivo** (e não o `--selftest`, que é outro braço) usei
**`SOTTO_FILE_TAP=<ficheiro>`**: alimenta a amostra através do **`asr_thread` real** — com a
retenção/poda de `seg_pcm`, os cinco sítios de `drain()` e a segunda passagem — e **não abre
device nenhum**. A amostra de 90 s é reproduzida em ciclo, a wall-clock.

---

## 2. O removedor de ruído — VEREDICTO

> **NÃO EXISTE removedor de ruído no Sotto. Não há RNNoise, DeepFilterNet, WebRTC NS, Speex,
> supressão espectral, Wiener, noise gate nem `afftdn`/`anlmdn`/`arnndn` em lado nenhum do código.**
>
> **O que existe são três SELECTORES/ganho, e nenhum deles limpa o áudio que o modelo vê:**
> o **VAD Silero** (descarta blocos), o **`SpeechMusicGate`** (descarta blocos INTEIROS) e o
> **`AutoGain`** (só ganho, zero limpeza espectral).

### 2.1 O instrumento (porque a ausência precisa de instrumento, não de impressão)

**`_main\noise-remover-census.py`** (6552 B, sha256 `6D4EABFB…D58F4`) — censo read-only sobre
`worker/` + `app/`, extensões `.py .js .json .html .css`, a saltar `node_modules`, `models`,
`__pycache__`, `.git`, `_legacy-electron`.
**Contagem: 80 ficheiros / 2.196.880 bytes.** Saída: `_main\noise-remover-census.out` (5263 B,
sha256 `D02867E3…152C5`).

**Os 12 padrões de removedor — TODOS ZERO:**

`rnnoise|rn_noise` · `deepfilter|deep_filter` · `noise_suppress|noisesuppress|noise_suppression` ·
`webrtc|webrtcns|ns_level|nslevel` · `speex` · `denois|de_noise|denoiser` ·
`noise_reduc|noisereduc|noiseReduction` · `spectral_sub|spectral_subtraction` · `wiener` ·
`noise_gate|noisegate` · `afftdn|anlmdn|arnndn` · `noisered`

**Os 7 controles positivos — TODOS ACERTARAM** (logo o instrumento é sensível e o zero é
informativo): `SpeechMusicGate`, `AutoGain`, `AudioMeter`, `StreamAsr`, `resample_to_16k`,
`CUDAExecutionProvider`, `use_vad`.

**No `worker\config.json`:** chaves de `audio` = `['_comment','_comment_live','block_ms','device',
'preferred_devices']`; chaves de `model` = `['_comment_lang_id','dir','lang_id','providers',
'use_vad']`. **Chaves com forma de ruído: NENHUMA.**

### 2.2 Onde é que um removedor de ruído PERTENCERIA

Ordem real das etapas em `worker\sotto_worker.py`: `AutoGain` `:1162` → `AudioMeter` `:1344` →
`SpeechMusicGate` `:1436` → `resample_to_16k` `:1090` → `StreamAsr`/decodificação `:455` →
`join_fragments` `:1867`.

- **ANTES do VAD/portão** — o removedor mudaria exactamente as features em que o
  `SpeechMusicGate` decide (a **gama de dB** por sub-janela de 20 ms, `db_range_min` 18,0, e o
  `rms_floor` 0,004). Mudar-lhe a entrada é mudar-lhe o comportamento medido, e a decisão do
  portão deixaria de ser a que foi medida.
- **DEPOIS do portão, imediatamente antes do codificador** — é a colocação **mais segura**:
  mantém o comportamento medido do portão intacto e limpa o que o modelo vê. O contra-argumento,
  honesto, é que um sinal mais limpo também ajudaria o próprio VAD.

**Candidatos reais nesta máquina, sem instalar nada:** **RNNoise** (minúsculo, barato em CPU — o
candidato natural para um caminho ao vivo a 10 Hz), **DeepFilterNet**, **WebRTC NS**. O **Demucs
`htdemucs`** já está documentado no repo como **rejeitado pelo custo**. **Não instalei nada e não
prometo que seja "só um interruptor"**: qualquer um deles acrescenta uma etapa nova ao caminho ao
vivo, e o caminho ao vivo já não acompanha o tempo real (ver ponto 3.4).

### 2.3 O que o Sotto faz HOJE com o ruído, medido no worker VIVO do dono

Do `panel-state.json` (worker 29008, 175.792 blocos acumulados):

`gate: on` · `music_gated_chunks: 21264` · `vad_gated_chunks: 830` · `gate_kept: 10125`

Ou seja: o `SpeechMusicGate` **descartou 21.264 blocos** e deixou passar 10.125 — descarta cerca de
**dois terços**. Isto é um **portão de presença**, não um removedor: ou o bloco passa inteiro, ou
desaparece. Nada no caminho limpa o espectro do que passa.

---

## 3. O `peak` real do áudio ao vivo

### 3.1 O que o worker EMITE

**Na cor AO VIVO (com o código NO disco, `--meter-hz 10`):** objecto
`{"type":"meter","peak":X,"blocks":1}`.

- **917 eventos** de meter, **0 não-parseáveis**.
- `blocks` é **sempre exactamente 1** — confirma `blocks_per_window = max(1, round(interval/block_s)) = 1`
  a `block_ms=100` / 10 Hz.
- **Distintos: 630 de 917.** min **0,0016** · max **0,389** · média **0,064931** · mediana **0,051400**.
- Transições: **subiu 443 · desceu 467 · igual 6**. **ZERO eventos com `peak == 0,0`.**
- Histograma: `[0;0,05)` 445 · `[0,05;0,1)` 299 · `[0,1;0,2)` 130 · `[0,2;0,3)` 28 · `[0,3;0,5)` 15 · `≥0,5` 0.
- Primeiros 12: `0,0022 0,0017 0,004 0,0076 0,0045 0,005 0,0065 0,0701 0,0839 0,0629 0,0617 0,0356`
- Últimos 12: `0,0666 0,0495 0,066 0,0418 0,0746 0,0662 0,0626 0,0456 0,0311 0,0338 0,048 0,0756`

**Cadência medida: 917 eventos sobre 917 blocos entregues × 100 ms = 91,7 s = exactamente 10,0 Hz.**
E o medidor conta os blocos **ENTREGUES** pelo tap (emitidos em `on_block`, antes da fila), não os
descodificados — por isso ficou a 10 Hz mesmo com o descodificador atrasado (`audio_s=42,56`).
O `peak` run-max do próprio tap deu **0,389003** contra os **0,389779** que eu medi no WAV cru: a
diferença é o reamostrador 48k→16k.

**O `peak` do worker VIVO do dono:** `panel-state.json` → `worker.workerStats.fields.peak =
"0.853180"` — mas atenção, **esse não é o medidor de 10 Hz**: é o **máximo histórico da corrida**
(high-water mark) que vem nos `workerStats`. O `peak` instantâneo do áudio ao vivo, esse, anda em
torno de 0,05–0,09 (mediana 0,0514), com picos até ~0,39.

### 3.2 O que o painel RECEBE

**Nada com forma de medidor.**

- `_main\webview-run.log`: `BRIDGE_METER=0`, `BRIDGE_UNKNOWN=0`, `BRIDGE_MALFORMED=0` sobre o
  ficheiro TODO.
- O shell a correr **não tem** o ramo `meter` (o `else:` final em `:6911-6913` do shell EM DISCO
  faria `BRIDGE_UNKNOWN type='meter'`); o shell **no disco** tem o ramo real (`:6843 elif kind ==
  'meter':` → `_meter` `:6915`), que faria `BRIDGE_METER`. *(Números de linha da revisão do shell
  medida: 397180 B, sha256 `EA014D8F…DB81`, **7930 linhas** — ver §1.1.)*
- **A conclusão honesta: o worker do dono não emite evento `meter` nenhum** (é pré-medidor) e por
  isso o painel não recebe nenhum. O que o painel recebe é o `workerStats` (tag `tick`, cadência
  `--stats-interval` = **10,0 s**, `:2979-2983`), e é daí que lhe vem `fields.peak` (o máximo
  histórico) e `fields.blocks`.

**Consequência para o dono:** o medidor a 10 Hz **existe no código no disco** (`METER_HZ = 10.0`,
`:1340`; `METER_HZ_DEFAULT = 10.0`, `:1341`; escape `--meter-hz 0` / `SOTTO_METER_HZ=0`,
`:3551-3572`) e eu **medi-o a exactamente 10,0 Hz** — mas o worker que está a correr **não o tem**.
**O dono só o terá depois de um reinício do worker, e eu não reinicio o worker dele.**

### 3.3 O que a animação do painel precisa — e o que o `peak` faz

O campo é **`peak`** (não `level`, não `rms`) porque `wireStatsSource` do painel lê
`fields.peak`/`fields.blocks` (`app/panel/panel.js:1709` → `pushLevel`). Sobre os 917 eventos
medidos, a série **sobe 443 vezes, desce 467, fica igual 6** e tem **630 valores distintos em 917** —
ou seja, é uma série genuinamente variável a 10 Hz, com 69% de valores únicos: dá animação real e
não um degrau. **Zero valores a 0,0** — a onda nunca cai ao chão.

### 3.4 O custo do caminho ao vivo — e ele NÃO acompanha

Da cor AO VIVO (`sweep90-live-new.jsonl`): `queue_drops=234` (≈23 s de áudio perdidos),
`infer_wall_s=39,76` sobre `audio_s=42,56` → **rtf 0,93**, contra **rtf 0,161** do braço de
ficheiro. A causa está medida: **uma única `rerun` bloqueou o consumidor durante
`rerun_wall_s=44,94`**, porque a segunda passagem é **síncrona** dentro do ciclo do consumidor. No
worker vivo do dono isto acumula: `reruns: 788`, `rerun_wall_s: 224,03`. Isto é um custo real do
caminho ao vivo, e reporto-o como facto medido.

---

## 4. As duas cores do problema da palavra partida — no áudio do dono

### 4.1 O instrumento válido (e porque o primeiro foi inválido)

**Primeiro A/B (INVÁLIDO):** `sweep90-new.jsonl` vs `sweep90-before.jsonl`. As duas cores
**descodificaram diferente** (`PS.` vs `PCor`, `tokens 122` vs `118`, `frames 528` vs `524`) porque
o braço BEFORE chamava `W.selftest(...)` directamente enquanto o NEW ia por
`worker\sotto_worker.py --selftest --audio …`. **Era a via de entrada a diferir, não o `join`.**
Substituído.

**Instrumento válido: `_main\file-arm-ab.py`** (2465 B, sha256 `FFF6FA67…7FCEF`) — fixa **o mesmo
`argv` e a mesma via de entrada** (`W.main()` com `--selftest --audio … --threads 1`) para as duas
cores, e a **única** diferença é uma função:

```python
W.join_fragments = pre_fix_join      # antes:  " ".join(t for t, _c in frags if t).strip()
```

**Controlo de determinismo** (`word-split-file-ab-determinism.txt`, `fa-new-1` vs `fa-new-2`):
`final text identical? **True**`, fragmentos idênticos, `tokens 118`/`frames 524` nos dois →
**o pipeline é reprodutível ao argv fixado**, logo as duas cores são legíveis. (Replicado na revisão
actual — `word-split-file-ab-determinism2.txt`; ver §4.5.)

### 4.2 As duas cores — 8 sítios partidos no BEFORE, ZERO no NEW

`_main\word-split-file-ab-pinned.txt` (10489 B, sha256 `A3B275CE…B0CC8`). Mesmo áudio, mesmo
`argv`, mesmo decode (`tokens 118`, `frames 524`, `RECOGNISED` byte-a-byte igual).

| # | ANTES (código antigo) | AGORA (código no disco) |
|---|---|---|
| 0 | `de força luvas do PC or` | `de força luvas do **PCor**` |
| 1 | `Foca das missões se cundárias e fazer` | `…missões **secundárias** e fazer` |
| 2 | `…e fazer SDG s que são` | `…e fazer **SDGs** que são` |
| 3 | `…os pontos .  Foca na ções secundária` | `…os pontos.  Foca **nações** secundária` |
| 4 | `…que são os po ntos em interro` | `…que são os **pontos** em interro` |
| 5 | `…em interro ga ção` | `…em **interrogação**` |
| 6 | `…Elas aument am sua barra` | `…Elas **aumentam** sua barra` |
| 7 | `baixo no mapa e as .` | `baixo no mapa e **as.**` |

**A prova decisiva:** `final text identical? False`, mas
**`final text identical w/o spaces? True`** e **`all text identical w/o spaces? True`** —
**idênticos caractere por caractere depois de remover os espaços**. A correção muda **só os
separadores**; não muda uma única letra do que o modelo ouviu. Fragmentos só no BEFORE:
`['or','am']` (= `PC or`, `aument am`); só no NEW: `[]`.

**Uma ressalva honesta:** `Inf o` aparece nas **DUAS** cores. É **artefacto do modelo** (o modelo
emitiu uma marca de palavra `▁` ali), **não** o defeito do `join`.

### 4.3 A cor AO VIVO — no caminho ao vivo, e CONFUNDIDA (digo-o)

`_main\sweep90-live-new.jsonl` (51063 B, `FADF22BD…659D9`) e
`_main\sweep90-live-before.jsonl` (8979 B, `E6CC20C0…FB97`), A/B em
`_main\word-split-live-ab.txt` (9678 B, `CA200E74…22C9E`).

- NEW: a sua única linha `final:true` **não tem palavras partidas** —
  `'Eu não consigo pegar meu de força eu não consigo pegar meu de força luvas do perseguidor'`.
- BEFORE: as suas linhas `final:true` têm partições **genuínas** —
  `'nos secund es de fazer SDGs que são os pontos foca nas'` e
  `'fazer SG que são os pontos em interroga ção elas aumentam sua barra'`.
- Fragmentos NEW (8): `['não','meu','lu','ino','S','SDs','são','fo']`;
  BEFORE (12): `['não','meu','or','emi','são','es','nas','SDG','sua','SG','ção','ba']`.

**ESTE A/B NÃO É LIMPO e digo porquê, com números:** NEW teve `queue_drops=234` / `audio_s=42,56`;
BEFORE teve `queue_drops=146` / `audio_s=50,96` — as duas cores consumiram áudio **diferente e não
contíguo** (ambos os stderr mostram 3 rajadas de `audio queue full`). Rácio a nível de caractere
0,5882. **A causa é a `rerun` do NEW ter bloqueado o consumidor 44,94 s.** Por isso a prova
**autoritária** é o braço de ficheiro fixado em 4.2, e esta é evidência de apoio.

### 4.4 As strings do dono, no log DELE, produzidas pelo worker PRÉ-correção

Fonte: `_main\webview-run.log`, worker 29008 (pré-correção):

- `:7139/:7143` → `"bot lan e"` … `CAPTION_APPLIED "Bot lan e." count=99/100`
- `:30286-30290` → `"…it's a good plan 's winnable when you have floating"` →
  `"…'s winnable when you have floati." count=200` (aqui `winnable` está certo, mas `me le` e
  `floati` estão partidos)
- `:31716-31727` → `CAPTION_APPLIED "The other lan e and because the e gi ant Evo is so broken now I 'm telling you it is."`
- `:33691-33697` → `"M in front, so I'm gonna go the lan e and meet rage the game."`
- `:33703-33711` (**primeira passagem, CORRECTA**) → `"no no tornado of dreams and then I fucking joked I fucking I fucking choked I fucking"`
- `:33713/:33714` (**MESMO áudio, passagem posterior**) → `"Tor nado of Dreams and then I fucking jo I fucking ed I fucking choked I fucking"` → `CAPTION_APPLIED "Tor nado of Dreams and then I fucking jo I fucking ed I fucking choked I fucking."`
- `:33716-33720` → `"Choked that was so winn able I had both his tow s down."`
- `:33752/:33753` (**mesmo áudio, depois de `HOT_RELOAD_APPLIED reload=34`**) → `"That was so winnable.  I had both his towers down."` (o **espaço duplo** é a junção da segunda passagem)

**Mecanismo provado por estas linhas:** o defeito **depende do alinhamento dos blocos** — o MESMO
áudio é descodificado certo numa passagem (`tornado`, `joked`) e partido noutra (`tor nado`,
`jo`+`ed`). A correção torna o separador **independente do alinhamento**.

### 4.5 REPLICAÇÃO na revisão ACTUAL do worker (`64E7EC6F…`) — o veredicto não mudou

O A/B de 4.2 foi **executado** contra a revisão `29E4CBFA…` (237489 B). Como o `worker\sotto_worker.py`
mudou durante a varredura, **voltei a correr o MESMO instrumento válido** (`file-arm-ab.py`, mesmo
`argv`, mesmo áudio `live-sample-cable-input-90s.wav`, `--threads 1`, **sequencialmente**) contra a
revisão actual **242082 B / sha256 `64E7EC6F…`**. Os três braços, todos rc=0:

| braço | ficheiro | bytes | sha256 | wall |
|---|---|---|---|---|
| NEW | `_main\fa2-new.jsonl` | 7178 | `1A0841F94830748A6849DD026582D8CCD43F313A1F0E6B33ADEB23D57058BB15` | 12,0 s |
| BEFORE | `_main\fa2-before.jsonl` | 7226 | `2849F934DA87793DDFD380707A13B700C0E89D337013B0AF924B624E371D1F77` | 16,6 s |
| NEW (2ª vez) | `_main\fa2-new2.jsonl` | 7180 | `CE9E729A91518EC34E24C9559C59ABE6FBDFC826A817AEBE0DDB6DE23CE966A3` | 16,6 s |

(`.err` correspondentes: `fa2-new.err` 805 B `A3499F3A…ED548`; `fa2-before.err` 812 B
`B0FF2D63…FE910`; `fa2-new2.err` 806 B `8CE24FA8…A2A4B`.)

**Os três braços têm contadores de decode IDÊNTICOS** — `audio_s 89,600`, `tokens 118`, `frames 524`,
`empty_chunks 32`, `vad_gated_chunks 102`, `music_gated_chunks 0`, `gate=off`. (O `infer_wall_s`
difere — 5,373 / 7,714 / 6,489 s — por ordem de execução/contensão; **não** é uma comparação de custo.)

**Controlo de determinismo** (`_main\word-split-file-ab-determinism2.txt`, 10382 B, sha256
`C0AE340F0961E15E26CC626A4D7E9878707A22DF68CAE6FD01E65E5424C41E1A`): `fa2-new` vs `fa2-new2` →
`final text identical? **True**`, fragmentos idênticos, só-no-um `[]` nos dois sentidos.

**As duas cores** (`_main\word-split-file-ab2.txt`, 10489 B, sha256
`6F49316CB6496B398BCEFFBAC7D106C77B4FC5EB5525F1D20D27C873AA68FECB`): `fa2-new` vs `fa2-before` →
`final text identical? False`, **`final text identical w/o spaces? True`**,
**`all text identical w/o spaces? True`**, fragmentos só no BEFORE `['or','am']`, só no NEW `[]`.
As 5 linhas fechadas do NEW, verbatim: `'de força luvas do PCor'`,
`'Foca das missões secundárias e fazer SDGs que são os pontos.  Foca nações secundária'`,
`'s em fazer SD que são os pontos em interrogação.  Elas aumentam sua barra vermelha em'`,
`'baixo no mapa e as.'`, `'Info nova'`. As do BEFORE trazem `PC or`, `se cundárias`, `SDG s`,
`pontos .  Foca na ções`, `po ntos`, `interro ga ção`, `aument am`, `e as .` — **os 8 sítios de 4.2,
reproduzidos um a um na revisão actual.** `Inf o` continua a aparecer nas **duas** cores.

**Uma nota de instrumento:** o `RECOGNISED` (o `done.text`, o detok da corrida inteira) é
**byte-idêntico** nos três braços — o defeito **nunca esteve** no `detok`/`done.text`, e é por isso
que o sinal do A/B vive no **JSONL por-caption**, não nessa linha. Ler os `RECOGNISED` iguais como
"a correção não fez nada" é um erro de instrumento.

### 4.6 O que NÃO consegui corrigir

O worker do dono (pid 29008) corre **código pré-correção** e arrancou às **08:01:56**. **Não posso
corrigi-lo sem o reiniciar, e não o reinicio.** O que fiz em vez disso: gravei a amostra do áudio
ao vivo e passei a **mesma amostra** pelo **código no disco** no meu próprio processo. **Sim, as
strings dele desaparecem no código novo** — os 8 sítios da tabela 4.2, com o texto sem espaços
idêntico.

---

## 5. O que li do `panel-state.json` — o painel NO ESTADO AO VIVO

**Instrumento:** `_main\live-panel-read.py` (5194 B, sha256 `67FA6E83…2A84BA`) → saída
`_main\panel-live-read.txt` (3016 B, sha256 `716BC173…1E2E9`). Lição já aprendida neste repo: o
console do PowerShell transforma `ã` em U+FFFD, por isso o ficheiro é a evidência, não o pipe.
**Ficheiro lido:** 36637 B, mtime 12:55:59, sha256
`B61671725991BD5CB73299CEFCDC5A3EF9F196E2EB85ACF2A24BB40DF4137C2F`, `sequence: 8764`.

### 5.1 O que o dono pediu para eu reportar

| pergunta | resposta medida |
|---|---|
| `live.scroll.client` (altura da caixa) | **717 px** |
| `live.count` | **169** linhas |
| há prosa de programador pintada? | **NÃO** — `panel.live.hint: ""` |
| o índice de linha desapareceu? | **SIM** — chaves da linha = `['latest','provisional','text']`, **nenhum campo de índice** |

**Auto-scroll está a seguir, e é medido:** `scroll = {top: 15102, height: 15819, client: 717,
atBottom: true, overflowing: true}` — e `top` = `height − client` = `15819 − 717 = 15102`
**exactamente**. A caixa está colada à linha nova. `latest: true` em **exactamente 1** linha
(índice 168), `provisional: 0`.

### 5.2 A contradição que encontrei, e o mecanismo dela

`namedState: "no-audio"` **ao mesmo tempo que** `count: 169` e `worker.captions: 6859`.
Três elos, todos medidos:

1. **`panel.status = {"kind": "live", "text": ""}`** — o painel reporta `kind: live` mas com texto
   **VAZIO**, por isso `named_state()` (`sotto_webview.py:4120`) **nunca** casa
   `'Receiving captions'` e cai para as regras seguintes.
2. **`worker.noAudio: true` está LATCHED.** É limpo **apenas** em `_spawn()` (`:6666`, e `:6512` no
   `__init__`) — **nunca** por uma caption. `_consume` levanta `pending_error` numa caption
   (`:6841`) mas **não toca em `no_audio`**.
3. **`named_state()` testa `noAudio` DEPOIS dos estados de erro** (`:4130-4131` → `NO_AUDIO_STATE`
   = `'no-audio'`, `:255`).

O elo que fecha: **`_no_audio_evidence` (`:7041-7080`)** trata `device-rotated` com `reason=flat`
como **evidência de que não há áudio** — e o **comentário do próprio código** (`:7048-7058`) diz
que esse rótulo **NÃO** significa "abaixo do piso de peak":

> *"The worker's word is `flat`, but it is NOT 'below the peak floor' — measured on this box, a live
> idle run rotated with `peak=0.465216` against `floor=0.002` … the tap heard something and the
> model found nothing to transcribe in the window"*

**`reason=flat` é um rótulo SOBRECARREGADO.** É emitido quando a janela do ladder
(`TAP_WINDOW_S = 6.0`, `:218`) expira **sem caption** — não porque o sinal era plano. O payload
carrega `peak`/`peak_floor` exactamente para os dois casos se distinguirem. **Prova nas duas
cores:** a evidência do dono é `reason=flat peak=0.0 floor=0.002` (**mesmo morto**); a minha é
`reason=flat peak=0.389003` (**bem alto, 0 captions em 6 s**).

**A evidência do worker VIVO é `device-rotated reason=flat peak=0.0 floor=0.002`** — ou seja, ao
arrancar ele rodou fora de um candidato genuinamente morto (`peak=0,0`), latchou `noAudio`, e
**6.859 captions depois continua com `noAudio: true`**.

### 5.3 A frase FALSA que este latch já pintou no ecrã do dono

`_on_silence` (`:7082-7127`): quando o stdout fica quieto e `self.no_audio` é verdadeiro, o shell
**pinta**:

- `STATUS_APPLIED text="Audio tap silent - nothing to transcribe"`
- `PLACEHOLDER_APPLIED title="No audio to transcribe"` com o corpo
  *"The worker measured every tap it opened below the peak floor: this endpoint is carrying digital
  silence…"*

**Contagens sobre o `webview-run.log` inteiro (39893 linhas):**

| linha | contagem |
|---|---|
| `BRIDGE_SILENT_BENIGN` | **1503** |
| `STATUS_APPLIED text="Audio tap silent - nothing to transcribe"` | **869** |
| `PLACEHOLDER_APPLIED title="No audio to transcribe"` | **873** |

**E os `peak` que vêm DENTRO da própria evidência** — valores distintos no log inteiro:
**`0` · `0,142383` · `0,250364` · `0,250702` · `0,407688` · `0,462641`**.

**Cinco dos seis são ALTOS** (0,14 a 0,46, contra um piso de 0,002). Ou seja: o painel disse ao
dono *"este endpoint está a carregar silêncio digital / o worker mediu todos os taps abaixo do piso
de peak"* **enquanto o áudio estava a 0,46 de peak** — e a própria frase de evidência, na linha ao
lado, traz o número que a desmente. Há 1503 disparos do watchdog e 869 pinturas (a diferença são os
casos em que havia um erro real no ecrã, que tem prioridade).

**Ressalva importante, para não exagerar:** no worker ACTUAL (pid 29008) **não há nenhum
`BRIDGE_SILENT_BENIGN`** — o último foi `:26943` (pid 37032) e o 29008 nasceu em `:26978`. No
worker actual o latch está **no estado**, não no ecrã: o watchdog só dispara após `ms=15000` de
stdout quieto, e o worker actual emite captions e stats a cada 10 s, por isso não dispara. O que
ele pinta é `STATUS_APPLIED text="device-rotated (flat)"` (`:26996`+), logo a seguir ao arranque.

---

## 6. Custo próprio, e o que NÃO consegui fazer

### 6.1 O meu custo

- **Tecto de threads: `--threads 1`** em todas as corridas de A/B; nunca passei de 2.
- Braço de ficheiro: `infer_wall_s` **5,42–5,69 s** para 89,6 s de áudio → **rtf 0,161**;
  `peak_rss_mb` **2400,9**.
- Braço ao vivo: `infer_wall_s` **39,76 s** para `audio_s` 42,56 → **rtf 0,93**;
  `peak_rss_mb` **2453,0**.
- As cores correram **sequencialmente** (corridas concorrentes toldam os tempos: o mesmo braço de
  ficheiro mediu `rtf 0,161` sozinho e `rtf 0,687` com contenção). **Não cito os tempos do braço de
  ficheiro como comparação de custo NEW-vs-BEFORE** — o `infer_wall_s 210,453` de uma corrida
  anterior era contenção de outras lanes, não custo. A replicação na revisão actual (§4.5) mediu
  **wall 12,0 s / 16,6 s / 16,6 s** para os três braços de 89,6 s de áudio, com
  `infer_wall_s` 5,373 / 7,714 / 6,489 — também **não** comparável entre braços (ordem e contenção).
- **Nenhum processo meu ficou a correr** no fim.

### 6.2 O que NÃO consegui fazer, e porquê

1. **Não corri o ladder de device do próprio worker.** Fazê-lo abriria o **endpoint de captura do
   dono** (`CABLE Output`), que o worker dele segura. Em vez disso exercitei o **caminho de device
   de verdade** com um tap WASAPI em loopback sobre `CABLE Input` (30 s e 90 s), que abriu,
   entregou **900/900 blocos não-zero** e **fechou** as duas vezes (confirmado por releitura dos
   medidores). E o worker do dono já prova o ladder ponta-a-ponta melhor do que eu provaria:
   **6.859 captions** com `device.device = "CABLE Output (VB-Audio Virtual "`.
2. **Não corrigi o worker a correr.** É pré-correção e arrancou às 08:01:56; corrigi-lo exigiria
   reiniciá-lo. **Não reiniciei.**
3. **Não corri o shell.** Lock de instância única + a app do dono está viva. Logo **não verifiquei
   o DOM do painel directamente** — só o `panel-state.json`. Tudo o que digo do painel vem daí.
4. **Não posso reportar `AUDCLNT_E_DEVICE_IN_USE` como medido** — nunca o encontrei. Não é uma
   omissão; é o resultado.
5. **O A/B do caminho ao vivo está confundido** pelos `queue_drops` (NEW 234 vs BEFORE 146), e
   digo-o em vez de o apresentar como limpo. O A/B autoritário é o braço de ficheiro fixado.
6. **A cor de control do tap (`VoiceMeeter Input`) entregou 0 blocos** — é não-vazio mas é mais
   fraco do que "peak 0", e reporto-o como tal.
7. **Testei áudio de 90 s** (a amostra `live-sample-cable-input-90s.wav`, 900 blocos), mas **não
   testei o caminho Redux** — fora do âmbito desta lane.
8. **Não instalei nenhum removedor de ruído** e **não prometo que seja "só um interruptor"**.

### 6.3 Inventário — 41 ficheiros criados por mim, todos em `H:\sotto\_main\`

| ficheiro | bytes | sha256 |
|---|---|---|
| `live-audio-sweep-endpoints.py` | 4181 | `92E91F0319ADF559F559A6DB6FC4DDAB9E6756F4622CD87552E50A3ECE3C4D74` |
| `live-audio-sweep-endpoints.out` | 3451 | `FF84E0F11BF97127C7A47A44A67A6405FDF3665948727B0D8E9F02536EE7D731` |
| `live-audio-sweep-tap.py` | 7180 | `B7C84AFFEF52B2830D5499A537600D48837112A5E3DDF80B40C231A16C80F0E3` |
| **`live-sample-cable-input-90s.wav`** | **17280080** | **`E156BDE92F4AA63F09FF94F316AB85397D0D80419BF9F90144839075BD25295C`** |
| `live-sample-cable-input.wav` | 5779280 | `CCB2222114B26CE88206179BA44CA27917B55C3DF9C133A53A4909B69917B597` |
| `word-split-before-run.py` | 3000 | `2A527868C972BEC352FC8FDBB57B973C1292BF273490FEA5D90E09763879C990` |
| `file-arm-ab.py` | 2465 | `FFF6FA67F21B16D8CD4029459F1681555AE5FE048CC25C4F2FD3A57A3F77FCEF` |
| `word-split-before-live.py` | 3031 | `83E3FB16652B033426F4F8FACA875EB93DCF3B5DEF2426EB7F335059D8681828` |
| `noise-remover-census.py` | 6552 | `6D4EABFB4447E71C705F1B54DE362790A451BD41C508B90DA64A10DFB6DD58F4` |
| `noise-remover-census.out` | 5263 | `D02867E3258661B52A7B52393BCF462A18220DCEFD253076741F7C61E96152C5` |
| `live-arm-analyze.py` | 7214 | `9A25509E87880CC34C2E7914427BC9A36C8B9F322FE14F7636B672D869954E3E` |
| `word-split-live-ab.py` | 5789 | `F311C493D5B3A4EBEC9C521353AE8EBEE375C7A55B5E62CE05454478561FCF18` |
| `sweep90-new.jsonl` | 7211 | `FCA2E0743D80BEA21982D6CC20326DB4AA54CACC2177DEDAB70CA6077159B62F` |
| `sweep90-new.err` | 725 | `F4DDB87606A56C14F8F7C193B12B347A10A48C3ACE3AAC1655143D8A6A23F9E4` |
| `sweep90-before.jsonl` *(INVÁLIDO)* | 5942 | `826EC71FDC07F975174A35F219CD1644131EDDAE865A1A4F577242DE380E4AFB` |
| `sweep90-before.err` | 700 | `DBB14E3AA2BA3A731E96846F8B5B6870EE798111A3D10838E24FEE8F2871DF40` |
| `fa-new-1.jsonl` | 7179 | `EFFECE5D5E7163F3D5428D0E707B4454FB918B77E7C96BF82AE7A89012A900CD` |
| `fa-new-1.err` | 806 | `E02E524DE2F0EE8CF4BAF99797F17C2FF607F781E92046E5E09AEF0595665E6D` |
| `fa-new-2.jsonl` | 7180 | `3AC823C93FF3E01966CA89EAACD44C37F88333F4E4B5E05C49785E25B7BDB7A2` |
| `fa-new-2.err` | 806 | `047E9B3A7AF775D76E10FBFB3FE31BEFC1371B445CD18A20A1F26CE24E5C1536` |
| `fa-before.jsonl` | 7226 | `ACB4A661D1099B859C029A25ED436A3AFCDD270813CABF600FCE1DF72A83A658` |
| `fa-before.err` | 811 | `B860AF969555C9B7F553DF6D4BE04F274EA4B25D7A50394A961BC85A7C0F90B1` |
| `word-split-file-ab.txt` *(INVÁLIDO)* | 10635 | `8B45380C159AD584946AAE2DFFDB43E37461591B7EC07F579D165DF90A9DE789` |
| **`word-split-file-ab-pinned.txt`** | **10489** | **`A3B275CE2E0B1DA6D97211884314836AA44587E727D651D5C4C86EE9AA9B0CC8`** |
| **`word-split-file-ab-determinism.txt`** | **10383** | **`187EEAB218FFB126389445E55E7C485B3BB56B55C2629A2FE30C6FC073C65538`** |
| `word-split-live-ab.txt` | 9678 | `CA200E7486AB34AB1DB26AF85EE6F3915009D017071ACE0C0BB76D9D56722C9E` |
| `sweep90-live-new.jsonl` | 51063 | `FADF22BDD8544199D7F0300A3ED2F8F33B2FBBF36ACD895D7F4B5059FD3659D9` |
| `sweep90-live-new.err` | 5330 | `18DB849CFEE8E4E6C176DDB45DEA5C80372DC0E91A1DB42118E9B0184A81E01F` |
| `sweep90-live-before.jsonl` | 8979 | `E6CC20C09A4D232A5FF24911913B6724A9D231EFB1CC50BA12D901DCDB39FB97` |
| `sweep90-live-before.err` | 5948 | `BE541B4443F9CBE779BFBA2D90876C23C30E1BB0968A2F620DBC01D1614FBBE5` |
| `live-panel-read.py` | 5194 | `67FA6E8395E15D2A62F7D57029B6E70699B5AA1D1E7B0F984175F3780A2A84BA` |
| `panel-live-read.txt` | 3016 | `716BC173AE71472F528098B1DA12E272D2FF260C6D42E6EA388C892B3E61E2E9` |
| **`fa2-new.jsonl`** (revisão actual) | **7178** | **`1A0841F94830748A6849DD026582D8CCD43F313A1F0E6B33ADEB23D57058BB15`** |
| `fa2-new.err` | 805 | `A3499F3AB8C3783268B15D1B3E5664B24E81E807CDAF831AC2FF5810FF4ED548` |
| **`fa2-before.jsonl`** (revisão actual) | **7226** | **`2849F934DA87793DDFD380707A13B700C0E89D337013B0AF924B624E371D1F77`** |
| `fa2-before.err` | 812 | `B0FF2D63C418873FF51CB4E93BEA98BE51B5A054183EE6224CF4DE87A60FE910` |
| **`fa2-new2.jsonl`** (revisão actual, 2ª vez) | **7180** | **`CE9E729A91518EC34E24C9559C59ABE6FBDFC826A817AEBE0DDB6DE23CE966A3`** |
| `fa2-new2.err` | 806 | `8CE24FA8150D648B2FECC0179D6D008784B78B75F2DFB2B41F38BBC0BCBA2A4B` |
| **`word-split-file-ab2.txt`** (2 cores, revisão actual) | **10489** | **`6F49316CB6496B398BCEFFBAC7D106C77B4FC5EB5525F1D20D27C873AA68FECB`** |
| **`word-split-file-ab-determinism2.txt`** (controlo, revisão actual) | **10382** | **`C0AE340F0961E15E26CC626A4D7E9878707A22DF68CAE6FD01E65E5424C41E1A`** |

**Escrita confinada a `H:\sotto\_main\`.** Não toquei em `worker/`, `app/` nem `AGENTS.md`.

---

## 7. Resumo de uma linha por ponto

1. **Áudio ao vivo obtido** por loopback WASAPI de **`CABLE Input`** (lado de render da mesma
   cable; o worker do dono segura o lado de captura, que **não abri**). Amostra guardada:
   `_main\live-sample-cable-input-90s.wav`, 90,0 s, sha256 `E156BDE9…5295C`. **Nunca vi
   `AUDCLNT_E_DEVICE_IN_USE`.**
2. **O removedor de ruído NÃO EXISTE** (12 padrões a zero, 7 controles positivos a acertar,
   80 ficheiros / 2,2 MB). O que existe são três selectores/ganho que não limpam nada.
3. **`peak` real:** medidor a **exactamente 10,0 Hz**, 917 eventos, 630 distintos, mediana
   **0,0514**, máximo **0,389**, zero zeros, sobe 443 / desce 467. **O painel não recebe medidor
   nenhum** — o worker do dono é pré-medidor. `peak` do worker vivo = 0,853180 (máximo histórico).
4. **8 sítios partidos no código antigo, ZERO no código no disco**, texto sem espaços **idêntico
   caractere por caractere** — e o veredicto **replicou** na revisão actual do worker
   (`64E7EC6F…`, §4.5). As strings do dono (`lan e`, `Tor nado`, `winn able`, `tow s`,
   `jo`+`ed`) estão no log DELE, produzidas pelo worker pré-correção — e **desaparecem no código
   novo**.
5. **Painel:** `client` **717 px**, `count` **169**, `hint` **vazio** (sem prosa de programador),
   **sem índice de linha** (chaves `latest`/`provisional`/`text`), auto-scroll a seguir
   (`top = height − client` exacto). E `namedState: "no-audio"` com 6.859 captions — latch que só
   é limpo num respawn, alimentado por um `reason=flat` que o próprio código documenta como
   **não** significando "abaixo do piso"; já pintou a frase falsa **869 vezes** com peaks de até
   **0,462641** na linha de evidência.
6. **Recibo:** este ficheiro.
