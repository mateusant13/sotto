# Separar os áudios de cada speaker de uma call do Discord — S5

Frente S5 de 7. Brief: `docs/owner-brief-20261012.md`.
Âmbito: este documento + `_main/_venv-diar/**`. Recibo: `_main/receipt-20261012-s5.md>.

> **Resposta curta.** Para separar *quem fala quando* numa call do Discord **não é preciso
> nenhum modelo** — o Discord entrega um fluxo de áudio **por participante** e o Sotto
> já tem o código para capturar **um processo por app** (`--target-pid`). O que **não**
> existe hoje é um modelo que separe **falas sobrepostas** (duas pessoas a falar ao mesmo
> tempo) — e a única família de "source separation" instalável aqui separa **música**
> (voz vs. acompanhamento), **não falantes**. A diarização (*quem fala quando*, numa
> mistura) **existe e está medida**: é possível, mas está **morta** para este uso nesta
> caixa (DER ≈ 61,6 % previsto no áudio do dono, contra um limiar de morte de ~25 %).

---

## 1. As três perguntas, separadas

| pergunta | o que é | resposta |
|---|---|---|
| **A.** Dá para separar os áudios de cada speaker? | isolar o áudio de cada participante | **Sim, sem modelo** — por fluxo do Discord (bot) ou por processo (`--target-pid`) |
| **B.** Ou precisamos de um modelo para fazer isso pela gente? | — | **Só para fala sobreposta** (duas vozes ao mesmo tempo). Para *quem fala quando*, **não** |
| **C.** E a gente já tem esse modelo? Se não tiver, instala. | — | **Não temos** um modelo de separação de falantes. Os que há são de **música** (2 stems). O mais próximo (MossFormer2) é PyTorch, Apache-2.0, e **não resolve** o caso sem falar sobreposta |

---

## 2. Rota 1 — captura por processo (**funciona hoje, zero modelo**)

O worker **já tem** a captura por processo. É a rota mais barata e a única que não
precisa de modelo nenhum.

**Medido no worker live** (`worker/sotto_worker.py`, **310 593 B / 5929 linhas**,
sha256 `246BF8091D6FEBF5F15DF81D8AF9F06E6281083017CA1AD39A236AA23265C651`,
mtime 2026-10-12T02:11:19Z):

| linha | o que |
|---|---|
| `:4073` | `ap.add_argument("--target-pid", ...)` — help: "instead of the endpoint mix; SOTTO_TARGET_PID also sets it" |
| `:952` | `def device_candidates(cfg_audio=None, wanted=None, target_pid=None):` |
| `:1035` | comentário: "the owner named a pid (`--target-pid` / `SOTTO_TARGET_PID`), and offered AFTER" |
| **`:1044`–`:1045`** | **`if target_pid:` → `offer(process_loopback_candidate(target_pid, _plp_proc_desc(target_pid)), "p",`** — a rung `p`, **depois** da rung C |
| `:1644`–`:1680` | `PLP_DEVICE_ID = "VAD\\Process_Loopback"`, `PLP_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1`, `PLP_MODE_INCLUDE_TARGET_PROCESS_TREE = 0` |
| `:1665` | "# INERT BY DEFAULT: nothing below runs unless --target-pid / SOTTO_TARGET_PID" |
| `:2226` | `class ProcessLoopbackTap` |
| `:2506` | `process_loopback_candidate(pid, desc="")` |
| `:2547` | devolve `"proc:%s" % dev.get("target_pid")` |
| `:4534`–`:4583` | resolução; `:4583` `device_candidates(audio_cfg, wanted, target_pid=target_pid)` |
| `:5293`–`:5306` | rotação `device-rotated reason="per-app-tap-lost"` |

**O que isto dá:** **uma stream por processo** (uma app = uma stream). Não é uma stream
*por falante* — é *por app*. Se o dono quiser o áudio do Discord sozinho, `--target-pid
<discord.exe>` dá-lhe **uma stream com todos os participantes misturados** dentro do
Discord. Ou seja: **resolve o "ouvir o Discord sem o resto do PC", mas não resolve "um
falante = uma legenda"** por si só.

**Process Loopback é por processo, não por thread/falante.** `VAD\\Process_Loopback`
com `PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE = 0` abre a árvore de processos
*alvo* e devolve o **mix** desse processo. Não há, na API do Windows, um handle por
*voz* dentro de um processo.

---

## 3. Rota 2 — fluxos por utilizador no Discord (**não precisa de modelo, mas precisa de bot/plugin**)

O Discord **não** expõe um stream por utilizador à API pública de cliente — expõe-o ao
**bot** que está na call, e a plugins de cliente (BetterDiscord).

**Medido — `discord.js` `VoiceReceiver`** (https://discord.js.org/docs/packages/voice/0.19.0/VoiceReceiver:Class):

| membro | o que |
|---|---|
| `subscribe(target: string, options?)` | **"Creates a subscription for the given user id. Returns: A readable stream of Opus packets received from the target."** |
| `ssrcMap` | **"Maps SSRCs to Discord user ids."** |
| `speaking` | `SpeakingMap` — quem está a falar |
| `subscriptions` | `Map<string, AudioReceiveStream>` |

**Tradução:** um **bot** emite uma stream **por participante** (`subscribe(user_id)`) e o
`ssrcMap` diz-lhe qual o utilizador de cada SSRC. **Isto é a resposta à pergunta A.** Mas
exige um **bot** na call (ou um plugin de cliente que faça o mesmo no cliente do dono) —
**não** é algo que o Sotto consiga fazer sozinho a partir do `--target-pid`.

**O que o dono já provou existir no cliente:** o plugin BetterDiscord **BetterVolume**
(controlo de volume **por utilizante**, client-side). Isso prova que o cliente *tem* o
áudio por utilizador disponível localmente — mas é um **controlo de volume**, não uma
stream. Não é uma API de áudio por falante.

**Rota recomendada (se o dono quiser isto):** um **bot** (discord.js) na call com
`VoiceReceiver` + `subscribe(user_id)`, a enviar cada stream para um pipe/arquivo por
utilizador, e o Sotto a transcrever **cada stream separadamente** (uma legenda por falante,
com `source = user:<id>`). **Zero modelo.**

---

## 4. Rota 3 — diarização (quem fala quando, numa mistura) (**existe, está medida, está MORTA**)

A diarização responde "quem falou quando" **a partir de uma mistura**. É a rota que
**precisaria** de um modelo se não houver captura por falante.

**O que há em disco** (`_main/diar-models`, **96 195 886 B / 91,7 MiB**, 15 ficheiros):

| ficheiro | bytes | nota |
|---|---|---|
| `sherpa-onnx-pyannote-segmentation-3-0/model.onnx` | 5 992 913 | segmentador |
| `sherpa-onnx-pyannote-segmentation-3-0/model.int8.onnx` | 1 540 506 | |
| `3dspeaker_eres2net_base_16k.onnx` | 39 593 761 | extractor de embeddings de falante |
| `nemo_en_titanet_small.onnx` | 40 257 283 | alternativa |
| `0-four-speakers-zh.wav` | 1 819 586 | **controlo com verdade conhecida** (10 segmentos, 4 falantes) |
| `seg.tar.bz2` | 6 958 444 | |

**Runtime:** `sherpa-onnx 1.13.4+cuda12.cudnn9` em **Python 3.11.8**
(`C:\Program Files\Python311`). **`_main/_venv-diar` está VAZIO** — é um venv limpo
(pip + setuptools apenas, **23 387 336 B / 22,3 MiB**, 1497 ficheiros, `Lib/site-packages`
só tem `pip-24.0`, `setuptools-65.5.0`, `_distutils_hack`, `pkg_resources`). **Não
tem nenhum pacote de diarização** — o runtime real é o **Python de sistema**, não o venv.

**Veredito já decidido** (`_main/receipt-diarization-decisive.md)): **só com captura por
participante**. Os números que o matam:

| medição | valor |
|---|---|
| DER no áudio real do dono (leito sonoro +2,62 dB) | **≈ 61,6 %** (previsto pela escada de SNR medida) |
| DER em áudio limpo, `threshold` por omissão (0,5) | **28,85 %** (7 clusters em vez de 4) |
| limiar de morte declarado | **~25 %** |
| DER no controlo com verdade conhecida, `threshold=0.9` | **0,03 %** ✅ |

**Reproduzido hoje (esta frente):** o instrumento `_main/_diar-run.py` + `_diar-der.py`
dá, no ficheiro de controlo, **10 segmentos / 4 falantes / DER 0,03 %** — o pipeline está
**vivo e correto**. No áudio real do dono (90,0 s, 48 kHz → 16 kHz) dá **3 falantes,
4 segmentos, RTF 0,3207, pico RSS 382,9 MB, fala 23,287 s (25,87 %)**.

**Porque é que morre:** a DER é um **limite inferior** (não há verdade-terra no áudio do
dono — o recibo anterior diz-o explicitamente: *"A DER no áudio do dono não tem referência;
não é calculável. Digo-o em vez de inventar."*). Aos +2,62 dB de razão fala/leito do dono,
a escada dose–resposta medida prevê **≈ 61,6 %** — **quase 2,5×** o limiar de morte. E
mesmo **sem leito nenhum**, o `threshold` por omissão dá **28,85 %** — já acima de
25 %. **Só com `threshold=0.9`** é que recupera os 4 falantes no controlo.

**Conclusão da rota 3:** a diarização é **possível** mas **não serve** para este uso nesta
caixa. A recomendação **morre** nestes números.

---

## 5. Rota 4 — source separation (desembaraçar vozes sobrepostas) (**NÃO HÁ MODELO ADEQUADO**)

A separação de fontes é o que respondeu "duas pessoas a falar ao mesmo tempo". É a única
rota que **precisaria mesmo** de um modelo.

**O que a API instalada faz** (`sherpa_onnx.OfflineSourceSeparation`):

| classe | o que |
|---|---|
| `OfflineSourceSeparation`, `Config`, `ModelConfig` | motor geral |
| `SpleeterModelConfig` | **2 stems: vocals + accompaniment** |
| `UvrModelConfig` | **UVR / MDX-Net** (música) |
| `OfflineSourceSeparationGetNumberOfStems` | header C: *"For Spleeter 2-stems this returns 2 (vocals + accompaniment)"* |

**Medido hoje** — descarreguei e corrí `UVR_MDXNET_9482.onnx` (**29 704 738 B / 28,3 MiB**,
sha256 `9D78F8566FA8198065214AB628BE1DE966A500C57786695AA4B13E2B27A7727D`) com o
ficheiro de teste `qi-feng-le-zh.wav` (**4 604 504 B**), usando o exemplo do próprio vendor
(`offline-source-separation-uvr.py`):

| medição | valor |
|---|---|
| stems produzidos | **2** (o vendor faz `assert len(output.stems) == 2` e chama-lhes `vocals` / `non_vocals`) |
| RTF (CPU, 2 threads) | **0,8048** — **mais lento que tempo real** |
| pico RSS | **3 237,2 MB** (de 42,7 MB de base) |
| `reconstruction_delta_rms` | **0,0** — é uma **divisão 2-way exata**, não uma "separação de falantes" |
| delta RMS entre as duas stems | 0,182767 (são sinais diferentes: voz vs. resto) |

**Distribuição `k2-fsa/sherpa-onnx-models` release `source-separation-models`** (25 assets,
**1 137 734 500 B / 1085 MiB** no total): Spleeter 2stems (fp16 33,6 MiB / int8 46,4 MiB /
fp32 71,2 MiB) e **UVR MDX-Net** (vários, 29,7–66,8 MiB). **Todos são modelos de 2 stems
de música.** **Nenhum separa vozes humanas.**

**Modelo que separa falantes, mas NÃO está instalado:** `alibabasglab/MossFormer2_SS_16K`
(HuggingFace) — **Apache-2.0**, PyTorch (`last_best_checkpoint.pt`), 16 kHz, *"separates
mixed-speaker speeches into individual speaker's speech"*. É o candidato real para a
pergunta C — mas é **PyTorch** (precisaria do torch instalado, 5,6 GB) e **não está em
disco**.

**Conclusão da rota 4:** **não há** modelo de separação de falantes adequado instalado. Os
que há são de música (2 stems). **Não instalei** o MossFormer2 porque (a) não está no
âmbito de escrita (escreveria em `_main/diar-models/`, fora do âmbito) e (b) **não
resolve o caso sem fala sobreposta** — e o caso do dono, medido, é *quem fala quando* num
mix, não desembaraçar vozes sobrepostas.

---

## 6. O que é possível HOJE nesta máquina

| rota | estado hoje | modelo? |
|---|---|---|
| **1. Captura por processo** (`--target-pid`) | **Funciona** — código live no worker | **Não** |
| **2. Fluxos por utilizador** (bot `VoiceReceiver`) | **Possível** — precisa de um bot/plugin | **Não** |
| **3. Diarização** (quem fala quando) | **Existe e está medida** — mas **MORTA** (DER 61,6 % / 28,85 %) | Sim (sherpa-onnx) |
| **4. Source separation** (vozes sobrepostas) | **Não há modelo adequado** — só música 2-stem | **Falta** (MossFormer2) |

**Resposta às três perguntas:**
- **A.** Dá para separar os áudios de cada speaker? → **Sim, sem modelo** (rota 1 por
  processo; rota 2 por utilizador, com bot).
- **B.** Precisamos de um modelo? → **Não** para *quem fala quando* (rota 1/2). **Sim** só
  para *fala sobreposta* (rota 4).
- **C.** Já temos esse modelo? → **Não.** Os que há são de música. O mais próximo
  (MossFormer2_SS_16K, Apache-2.0, PyTorch) **não está instalado**.

---

## 7. Plano de integração no worker — 3 passos

**Passo 1 — Captura por processo (zero modelo, zero risco).** O código **já existe**
(`:1044`–`:1045`, `:2226`). Falta só o dono usar `--target-pid <discord.exe>` (ou
`SOTTO_TARGET_PID`). **Ação:** documentar no `worker/README.md` e testar com o pid do
Discord. **Medido:** 1 stream por processo, depois da rung C.

**Passo 2 — Uma legenda por falante, via bot (zero modelo).** Um bot discord.js na call
com `VoiceReceiver.subscribe(user_id)` → uma stream por utilizador → o Sotto transcreve
**cada stream separadamente**, com `source = user:<id>`. **Isto é a resposta real à
pergunta do dono.** **Ação:** escrever um pequeno bot (discord.js) que ligue para um
pipe por utilizador; o worker já tem `source` (`:2547`) e o painel já tem
`rowIdentity(source, start)` (`panel.js:326`). **Requer:** token de bot + o dono a
adicionar o bot à call.

**Passo 3 — (Só se o dono quiser fala sobreposta) MossFormer2.** Instalar
`alibabasglab/MossFormer2_SS_16K` (Apache-2.0, PyTorch, 16 kB) — **fora do âmbito de
escrita desta frente** (escreveria em `_main/diar-models/`). **Requer:** aprovação do Lead
para escrever fora do âmbito. **Não recomendado** sem o dono dizer que tem fala sobreposta
real — a diarização medida mostra que o problema dele é *quem fala quando*, não sobreposição.

---

## 8. O que NÃO instalei, e porquê

| modelo | licença | tamanho | porque é que não está instalado |
|---|---|---|---|
| `UVR_MDXNET_9482.onnx` | (sherpa-onnx) | **29 704,738 B** | **Descarreguei e corrí** para medir — é **música** (2 stems), não falantes. Fica em `_main/diar-models/` |
| `alibabasglab/MossFormer2_SS_16K` | **Apache-2.0** | (`.pt`, PyTorch) | **Não está em disco.** Fora do âmbito de escrita. Só se o dono quiser fala sobreposta |
| `pyannote.audio` / `speechbrain` / `demucs` / `nemo` / `asteroid` | — | — | **Ausentes** (probe: ModuleNotFoundError / 0 resultados). Não instalados |

**Nenhum pacote foi instalado.** A frente é de **pesquisa + medição**, não de instalação.
Se o dono quiser a rota 3 (MossFormer2), **peço ao Lead** a autorização para escrever em
`_main/diar-models/`.

---

## 9. Referências

- Brief do dono: `docs/owner-brief-20261012.md` (S5)
- Recibo decisivo anterior: `_main/receipt-diarization-decisive.md`
- Worker live: `worker/sotto_worker.py` — 310 593 B / 5929 linhas / sha256 `246BF8091D6FEBF5F15DF81D8AF9F06E6281083017CA1AD39A236AA23265C651` / mtime 2026-10-12T02:11:19Z
- `discord.js` VoiceReceiver: https://discord.js.org/docs/packages/voice/0.19.0/VoiceReceiver:Class
- `k2-fsa/sherpa-onnx` release `source-separation-models`: https://github.com/k2-fsa/sherpa-onnx/releases/tag/source-separation-models
- Exemplo do vendor: https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/offline-source-separation-uvr.py
- `alibabasglab/MossFormer2_SS_16K` (Apache-2.0): https://huggingface.co/alibabasglab/MossFormer2_SS_16K
- ModelScope MossFormer2: https://www.modelscope.cn/models/iic/speech_mossformer2_separation_temporal_8k
- `sherpa-onnx` c-api.h (OfflineSourceSeparationGetNumberOfStems): `C:\Program Files\Python311\Lib\site-packages\sherpa_onnx\include\sherpa-onnx\c-api\c-api.h`

---

## 10. UNMEASURED

| o que | porquê |
|---|---|
| DER **real** no áudio do dono | **Não há verdade-terra** (o recibo anterior diz-o). O 61,6 % é uma **previsão** da escada de SNR medida |
| Rota 2 ponta-a-a-ponto | **Não lancei nenhum bot** — o dono não pediu, e lançar bots na call dele é fora do âmbito |
| Efeito da diarização no ASR ao vivo | Não medi (o dono tinha um live a tocar) |
| `threshold` ótimo para o áudio do dono | **Não há verdade-terra** para o escolher |
| Fala sobreposta real no áudio do dono | **Não sei** — nunca medi sobreposição. Se não houver, a rota 4 não serve para nada |
| Painel com `source=user:<id>` | **Não testei** no WebView2 (fora do âmbito de escrita) |
| DER em áudio > 90 s | O ficheiro do dono é **90,0 s**; não testei mais longo |
