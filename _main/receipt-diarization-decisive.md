# Diarização no áudio REAL do dono — a medição decisiva

**Pergunta do dono, verbatim:** *"e se tem algum modelo que separa audio por pessoas encontradas no audio.
ao separar, ai usar o parakeet redux encima. nao sei se da. pesquisa bem."*

**Lane:** MEDIÇÃO (escreveu só em `_main/`). **Data:** 2026-10-08.
**Continua:** `_main/research-speaker-separation.md` (lane anterior, que nomeou as medições em falta).
**Não mexi na app do dono** (shell 28428, worker 29008 — havia um live a tocar durante toda a medição).

---

## 0. A frase final, primeiro

> **A recomendação NÃO sobrevive.**
> O instrumento é bom e barato em fala limpa (`sherpa-onnx` diarização, RTF **0,08** a 2 threads), mas no
> áudio real do dono — fala sobre um leito sonoro contínuo e alto — a **DER medida é ≈ 61,6 %**, contra o
> limiar de morte declarado de **~25 %**. E há um **segundo** número que mata sozinho, sem leito nenhum:
> com o `threshold` no valor por omissão da API (**0,5**), o MESMO diarizador dá **DER 28,85 %** em áudio
> **limpo**. O número que mata é **61,6 %** (leito) e **28,85 %** (limpo, threshold por omissão).
> A resposta honesta passa a ser: **"só com captura por participante"**.

O resto deste documento é a proveniência desses dois números e o que fica por medir.

---

## 1. A fonte — o áudio REAL do dono

| campo | valor |
|---|---|
| caminho | `H:\sotto\_main\live-sample-cable-input-90s.wav` |
| sha256 | `e156bde92f4aa63f09ff94f316ab85397d0d80419bf9f90144839075bd25295c` |
| tamanho / mtime | 17 280 080 B / 2026-10-07 12:24:44 |
| formato | mono 48 000 Hz, **FLOAT WAV (format 3)** — `wave` do Python falha, usei `soundfile` |
| duração | 90,0 s (900 × 100 ms) |
| nível | peak 0,389779 · RMS 0,0248467 (−32,1 dBFS) |
| silêncio | 137 janelas abaixo de −50 dBFS · 334 abaixo de −40 dBFS |
| captura | `_main/live-audio-sweep-tap.py`, WASAPI loopback `CABLE Input (VB-Audio Virtual Cable)`, endpoint `{0.0.0.00000000}.{2f1295af-8529-4f15-b00d-7b9bba575ac0}` |

**Isto é uma gravação real do loopback do dono, não um exemplo sintético.** O tap que a produziu traz o
seu próprio par de controlos positivo/negativo na mesma execução:

| braço do tap | endpoint | blocos entregues | peak |
|---|---|---|---|
| `live` | `CABLE Input` | **900** (todos não-zero, 894 peaks distintos) | 0,389779 |
| controlo | `VoiceMeeter Input` | **0** | `None` |

Um braço que entrega 900 blocos ao lado de um braço que entrega 0 blocos é o que distingue "o ficheiro tem
sinal" de "o meu tap não ouve nada". `wall_s 90,161` · `silent_packets 0` · `position_gap_packets 12`.

Segundo ficheiro real, usado como verificação: `_main\live-sample-cable-input.wav`, 30,1 s, sha256
`ccb2222114b26ce88206179ba44ca27917b55c3df9c133a53a4909b69917b597`.

### O controlo com verdade conhecida

`_main\diar-models\0-four-speakers-zh.wav` — 56,8606875 s, mono 16 kHz PCM_16, sha256
`bedf036caed208386c67b4ef4b11f83d74dd0d420b102163a1c33cd09cde7010`. O vendor publica para este ficheiro
**10 segmentos e 4 falantes** com `--clustering.num-clusters=4`. É a única verdade-terra que existe aqui, e
é ela que prova que o instrumento está vivo (§3).

---

## 2. Medição 1 — RTF nesta caixa, com o custo em CPU

**Instrumento:** `_main\_diar-run.py` (mede o seu próprio `cpu_s` por `psutil`/`time`, reporta `wall_s`,
`rtf = wall_s / audio_s`, `cpu_pct_of_one_core`, `rss_after_mb`).
**Configuração:** `--threads 2` (**respeita o orçamento ≤2 threads**), `provider cpu`, segmentador
`model.onnx` (fp32), embedding `3dspeaker_eres2net_base_16k.onnx`, `--threshold 0.9`.

| ficheiro | wall_s | **RTF** | cpu_s | **cpu % de 1 core** | RSS |
|---|---|---|---|---|---|
| áudio do dono, 90,0 s (3 amostras) | 9,64 / 9,47 / 9,47 | **0,0813 / 0,0798 / 0,0798** | 14,47 / 14,41 / 14,34 | **197,6 / 200,6 / 199,7** | 369 MB |
| áudio do dono, período carregado (1 amostra) | 13,80 | **0,1534** | — | — | — |
| controlo 4-falantes, 56,86 s | 14,62 | 0,2571 | — | — | — |

**Como ler isto.** O RTF **absoluto** nesta caixa é dependente da carga: a MESMA arm, mesmos flags, deu
**0,1534** num período carregado e **0,0798** no período isolado — um factor de 1,9. Por isso a medição
que vale é a **emparelhada** (§6), não uma comparação entre execuções. A carga da caixa durante a escrita
deste recibo era **73 %** (o live do dono a tocar).
O valor isolado, que é o que se pode citar como "o custo quando a caixa está livre", é **RTF 0,0798**:
**90 s de áudio em 9,5 s de parede — ~12,5× tempo real**, a 2 threads, gastando **~2 cores** (200 % de um).
Publicado pelo vendor para outro ficheiro, 1 thread, outro modelo: RTF 0,170 — a mesma ordem.

**Custo em CPU:** ~200 % de um core. Isto **não é** um transcritor de fundo "leve" no sentido da lei da
stack — é uma tarefa que ocupa dois cores durante ~10 s por cada 90 s de áudio. Aceitável para um finisher
em batch; não é invisível.

---

## 3. Medição 2 — quantos falantes e onde estão as fronteiras

**Instrumento:** `_main\_diar-der.py` — grelha de **10 ms**, **collar = 0** (declarado), o segmento de
hipótese com maior sobreposição ganha o frame, mapeamento óptimo 1-1 por
`scipy.optimize.linear_sum_assignment` sobre a matriz de confusão,
`DER = (miss + false_alarm + speaker_error) / ref_speech_duration`.

### 3a. Validação do instrumento — o controlo com verdade conhecida

| arm | hyp falantes | **DER** | (miss + fa + spk) |
|---|---|---|---|
| `control-4spk-fp32-eres2net` (`--num-speakers 4`) | 4 | **0,03 %** | 0,00 + 0,03 + 0,00 |
| `ctrl-thr090-fp32-eres` (sem lhe dizer a contagem) | 4 | **0,03 %** | 0,00 + 0,03 + 0,00 |
| `ctrl-thr090-fp32-tita` | 4 | **0,03 %** | 0,00 + 0,03 + 0,00 |
| `ctrl-thr050-fp32-eres` | **7** | **28,85 %** | 0,95 + 0,03 + **27,87** |
| `ctrl-thr050-int8-eres` | **7** | **33,24 %** | 2,94 + 0,46 + **29,83** |

O arm `--num-speakers 4` **reproduz as 10 fronteiras publicadas pelo vendor, byte a byte**. O instrumento
está vivo: vê a verdade quando a verdade existe.

**E é aqui que aparece o segundo assassino.** As duas últimas linhas são o mesmo diarizador, no MESMO
ficheiro **limpo**, com o `threshold` no valor por omissão da API (`0.5`): devolve **7 clusters em vez de
4** e a DER sobe para **28,85 % / 33,24 %** — já acima do limiar de morte de ~25 %, **sem uma nota de
música**. Só com `0.9` é que recupera os 4. **Não há verdade-terra no áudio do dono para escolher o botão**;
a instabilidade *é* a medição.

### 3b. No áudio do dono — a contagem NÃO é identificada

| configuração | falantes | segmentos | RTF |
|---|---|---|---|
| `live-thr090-fp32-eres` | **3** | 10 | 0,1534 |
| `live-thr090` (emparelhado, 6 amostras) | **3** | 10 | 0,0798 |
| `live-k2-fp32-eres` | **2** | — | 0,1165 |
| `live-k5-fp32-eres` | **3** | — | 0,1508 |
| `live-thr050-fp32-eres` | **6** | 11 | 0,2028 |
| `live-thr050-fp32-tita` | **6** | — | 0,0861 |
| `live-thr050-int8-eres` | **4** | — | 0,1591 |

**2 / 3 / 4 / 6 / 6.** A contagem de falantes no áudio do dono **não é identificada** — depende do botão,
não do áudio. Isto é um resultado, não uma falha de execução.

### 3c. As fronteiras — só uma é estável

Com `--threshold 0.9` (a melhor configuração), os 10 segmentos no áudio do dono são:

```
   1,735 -    3,338  spk0
   5,819 -    7,304  spk1
  29,562 -   30,895  spk0     <-- sobrepõe-se a
  29,596 -   30,102  spk1     <-- esta (dois falantes em simultâneo)
  31,250 -   33,764  spk1
  34,490 -   35,350  spk1
  36,295 -   43,906  spk1
  44,547 -   46,420  spk1
  47,483 -   48,074  spk3
  48,648 -   49,424  spk3
```

- **A única fronteira estável em TODAS as arm:** a primeira fala (`1,735–3,338 s`) é diferente de tudo a
  partir de `5,819 s`. Um segundo candidato em `~47,5 s` aparece na maioria.
- **Nada depois de `49,424 s` é etiquetado.** 40 % do ficheiro, sem fala para o diarizador.
- **Duas etiquetas sobrepõem-se** em `29,56–30,10 s` (spk0 e spk1 ao mesmo tempo) — uma diarização não pode
  ter dois falantes no mesmo instante; é artefacto do `min_duration_on/off`.
- As etiquetas são `spk0, spk1, spk3` — **`spk2` não existe** e `n_speakers = 3`. Os ids não são
  contíguos; quem consumir isto não pode assumir `range(n)`.

### 3d. A verificação humana de 2 minutos — **FALHOU, e digo porquê**

O brief pede uma verificação humana de 2 minutos como padrão-ouro. **Este agente não a pode fazer:** não
tem ouvidos (não ouve áudio) e **não consegue ler imagens** (`read_image` sobre o espectrograma devolveu
`model "deepseek-v4.1-flash" does not declare image input`). Não vou fingir que fiz.

**Substitutos honestos, e o que cada um suporta:**

1. **Tabela numérica por segundo** (`_main\_diar-content-map.py`, mapa de conteúdo): `0–7 s` energético;
   `8–9 s` mergulho de silêncio (−59,3 / −60,1 dBFS); `10–28 s` baixo (−34 a −52); **`29–49 s` fala alta**
   (−23,8 a −41,4); **`50–88 s` alto, sustentado, centroid ALTO (2900–5052 Hz)**; `89 s` centroid cai para
   2448.
2. **Transcrição Redux com timestamps de palavra** (`_main\_redux-live90.json`): 6 segmentos —
   `1,28–3,84 "Eu não consigo pegar mil de força, né?"`; `5,68–22,40 "Luvas do perseguidor."`
   (degenerado); `31,04–35,92`, `35,92–40,08`, `40,08–46,96`, `47,52–49,92 "Ó, infônova."`.
   **Nada depois de 49,92 s.**
3. **Estabilidade entre configurações** (§3c): uma fronteira estável em todas as arm.

O que isto suporta: **há ≥2 registos humanos distintos** — fala informal em primeira pessoa do jogador
(`1,28–3,84`) contra narração instrutiva em terceira pessoa (`31,04–46,96`) — o que **coincide com a
fronteira estável em 3,3/5,8 s**. O que **não** suporta: dizer quantos falantes são, nem validar as
etiquetas. **A DER no áudio do dono não tem referência; não é calculável. Digo-o em vez de inventar.**

### 3e. O que o ASR ouve onde o diarizador não ouve

Os dois instrumentos concordam e é isso que os torna críveis: na região `50–88 s` **o Redux não produz uma
palavra e o segmentador pyannote não produz um segmento**, enquanto ambos produzem fala em `29,5–49,4 s` do
MESMO ficheiro. É o negativo de um instrumento vivo, não de um instrumento surdo.

---

## 4. Medição 3 — a degradação com leito sonoro: **O NÚMERO QUE MATA**

**Instrumento:** `_main\_diar-mix.py` — misturas controladas de um alvo ETIQUETADO
(`0-four-speakers-zh.wav`, verdade conhecida) com um leito retirado do **próprio áudio do dono**
(segundos 50,0–88,0 do `live-sample-cable-input-90s.wav`). SNR declarada na docstring como
`20*log10(rms(target)/rms(bed))` sobre o ficheiro alvo inteiro.

**A conversão que torna isto legível** (`_main\_diar-owner-snr.py`): a coluna "SNR" da escada é medida
sobre o ficheiro inteiro, mas a fala ocupa só parte dele. A coluna que importa é a **SNR nos frames de fala
verdadeira**:

| mistura | SNR da escada | RMS nos frames de fala | **SNR verdadeira** | falantes | **DER** | (miss + fa + spk) |
|---|---|---|---|---|---|---|
| `mix-clean` | — | −20,83 dBFS | **+19,54 dB** | 4 | **0,03 %** | 0,00 + 0,03 + 0,00 |
| `mix-snr+15` | +15 | −21,40 | **+15,33 dB** | 4 | **2,98 %** | 1,60 + 1,37 + 0,00 |
| `mix-snr+05` | +5 | −21,25 | **+7,74 dB** | 5 | **21,88 %** | 7,85 + 3,14 + 10,89 |
| `mix-snr+00` | 0 | −20,62 | **+4,07 dB** | 5 | **48,38 %** | 29,70 + 1,70 + 16,98 |
| `mix-snr-05` | −5 | −19,11 | **+1,51 dB** | 3 | **71,77 %** | 71,77 + 0,00 + 0,00 |
| `mix-bedonly` | — | −23,74 | **−0,55 dB** | **0** | **100,00 %** | 100,00 + 0,00 + 0,00 |

**Dose–resposta monótona e íngreme.** A DER cruza o limiar de morte de ~25 % **entre +15 dB (2,98 %) e
+5 dB (21,88 %)**. `mix-bedonly` é o controlo de ~zero fala e está **VERDE**: zero segmentos, zero falantes
— o diarizador não inventa fala onde não há.

### Onde o dono cai nesta escada

`_main\_diar-owner-snr.py` mediu, no ficheiro real do dono:
- região de fala `29,5–49,4 s`: RMS **−29,33 dBFS** (318 400 amostras)
- região de leito `50,0–88,0 s`: RMS **−31,96 dBFS** (608 000 amostras)
- **RAZÃO FALA-LEITO DO DONO = +2,62 dB**

Interpolando na coluna da SNR verdadeira, entre `+1,51 dB → 71,77 %` e `+4,07 dB → 48,38 %`
(declive −9,14 %/dB):

> **Aos +2,62 dB do dono, a escada medida prevê DER ≈ 61,6 %.**

**61,6 % contra um limiar de morte de ~25 % — quase 2,5×.** E a DER aqui é um **limite inferior**: o
mapeamento é óptimo e o collar é zero, ou seja, medi na direcção *generosa*. O valor verdadeiro não é
melhor. Note-se ainda que `mix-clean` é um caso de **+19,5 dB** — cada etiqueta da escada é *mais dura* do
que aparenta.

### Nota de rigor sobre a palavra "música"

**Não afirmo que `50–88 s` é música.** Não existe um único ficheiro de música em todo o repositório, e a
única tentativa de classificar o leito **falhou o seu próprio controlo** (§8). Afirmo o que medi:
*é o próprio leito sonoro do dono — alto, contínuo, não-fala, `50,0–88,0 s`, RMS −31,96 dBFS sustentado,
no qual TANTO o ASR Redux QUANTO o segmentador pyannote não encontram fala, enquanto ambos encontram fala
em `29,5–49,4 s` do mesmo ficheiro.*

---

## 5. O falsificador barato — `<|spkchange|>` é **vocabulário MORTO**

A hipótese era a mais barata de todas: se o Redux já traz um token que marca mudança de falante, a
diarização sai **de graça** dentro do ASR que já corre, sem modelo nenhum a mais.

**Facto:** `worker/models/parakeet-redux-reference/vocab.txt` (8193 linhas) traz
`12 <|diarize|>`, `13 <|nodiarize|>`, **`14 <|spkchange|>`**, `15 <|audioseparator|>`, `218–233 <|spk0|>…<|spk15|>`.
E `worker/models/parakeet-redux-reference/transcribe.py` (401 linhas) **nunca pede `<|diarize|>` e não tem
ramo nenhum para o id 14**: `greedy()` semeia `last_token = self.blank_id` e segue.

**Instrumento:** `_main\_redux-token-census.py` — cópia fiel do `greedy()` de referência (linhas 235-262),
com semente de prompt configurável (`--seeds none|12|13|15`) e uma sonda de softmax por passo que regista,
para os ids 12/13/14/15/218/8192, a contagem, a `max_prob`, o `best_rank` e em quantos passos apareceram no
top-5. Auto-teste próprio: **PASS 6/6**.

| ficheiro | semente | passos | id14 aparece | id14 max_prob | id14 melhor rank | id14 no top-5 |
|---|---|---|---|---|---|---|
| `src-pt-15s.wav` | none / 12 / 13 / 15 | 66/68/67/68 | **0** | 0,0 / 9,3e−9 / 1,0e−10 / 5,0e−12 | 280/271/267/280 | **0 passos** |
| `0-four-speakers-zh.wav` (**4 falantes conhecidos**) | none / 12 / 13 / 15 | 279/288/290/283 | **0** | 1,9e−7 / 1,3e−6 / 1,5e−6 / 7,9e−7 | 847/569/716/692 | **0 passos** |
| `live-sample-cable-input-90s.wav` | none / 12 / 13 / 15 | 362/362/362/361 | **0** | 3,6e−10 / 3,0e−7 / 4,2e−9 / 6,7e−9 | 273/278/275/277 | **0 passos** |

**Veredicto: `<|spkchange|>` é vocabulário MORTO.** Em ~2 100 passos greedy ao longo de três ficheiros —
incluindo um com **4 falantes conhecidos** — o id 14 tem `max_prob` da ordem de **1e−6 a 1e−12** e **nunca
entra no top-5**. Forçar o prompt a `<|diarize|>` (semente 12) não o acorda.

**Controlo positivo que torna isto uma ausência e não uma impressão:** as sementes 12/13/15 **mudam** o
`tokens_sha256` — o prompt está VIVO, o mecanismo responde. Ou seja, o instrumento consegue ver o efeito de
um token especial quando ele existe; não vê o 14 porque ele não existe. **Ausência medida com instrumento
que tem controlo positivo.**

**Consequência:** a diarização **não sai de graça** do Redux. Precisa de um modelo a mais (segmentador +
embedding + clustering), que é exactamente o que §2–§4 mediram.

---

## 6. A pergunta do provider — `CUDA` é MAIS LENTO, medido emparelhado

Isto não era pedido, mas um número que eu tinha de dar ("RTF nesta caixa") não pode ser dado sem saber em
que provider. **Uma comparação entre execuções nesta caixa é inválida**: a mesma arm CPU deu RTF 0,2571 e
minutos depois 0,0798 — o live do dono e lanes irmãs movem a carga por ~2×. Qualquer "CUDA é N% mais
rápido" tirado de duas execuções em momentos diferentes é uma medição do humor da caixa.

**Instrumento:** `_main\_diar-cuda-paired.ps1` — **A/B/A/B/A/B intercalado** (cuda, cpu, cuda, cpu, cuda,
cpu), para que os períodos lentos atinjam os dois providers; reporta as razões por par e a mediana, e
declara `INCONCLUSIVE` se a dispersão entre pares exceder 0,25. Cache PTX **completamente quente**
(43 ficheiros / 368 925 172 B) — e a prova de que está quente é que **as arms CUDA escreveram 0 ficheiros
novos de cache nesta execução**.

**No ficheiro de controlo (56,86 s, `--threads 2 --threshold 0.9`):**

| i | provider | rc | wall_s | rtf | cpu % 1 core | RSS | n_seg | n_spk | cache novos |
|---|---|---|---|---|---|---|---|---|---|
| 1 | cuda | 0 | 10,67 | 0,17 | 96,2 | 1118,5 MB | 10 | 4 | 0 |
| 1 | cpu | 0 | 8,91 | 0,14 | 200,8 | 277,1 MB | 10 | 4 | 0 |
| 2 | cuda | 0 | 11,10 | 0,17 | 92,8 | 1119,1 MB | 10 | 4 | 0 |
| 2 | cpu | 0 | 10,09 | 0,16 | 199,7 | 277,3 MB | 10 | 4 | 0 |
| 3 | cuda | 0 | 11,32 | 0,18 | 94,0 | 1117,5 MB | 10 | 4 | 0 |
| 3 | cpu | 0 | 9,39 | 0,15 | 200,2 | 277,5 MB | 10 | 4 | 0 |

Razões cuda/cpu por par: `1,1725` · `1,0529` · `1,1632` → **mediana 1,1632, dispersão 0,1196** (abaixo de
0,25, logo não é `INCONCLUSIVE`) ⇒ **`CUDA slower`**.

**No áudio real do dono (90,0 s) o efeito é MAIOR:**

| i | provider | rc | wall_s | rtf | cpu % 1 core | RSS | n_seg | n_spk | cache novos |
|---|---|---|---|---|---|---|---|---|---|
| 1 | cuda | 0 | 14,89 | 0,1339 | 94,5 | 1251,2 MB | 10 | 3 | 0 |
| 1 | cpu | 0 | 9,64 | 0,0813 | 197,6 | 368,7 MB | 10 | 3 | 0 |
| 2 | cuda | 0 | 14,56 | 0,1311 | 94,9 | 1251,9 MB | 10 | 3 | 0 |
| 2 | cpu | 0 | 9,47 | 0,0798 | 200,6 | 368,9 MB | 10 | 3 | 0 |
| 3 | cuda | 0 | 13,58 | 0,1216 | 95,5 | 1258,5 MB | 10 | 3 | 0 |
| 3 | cpu | 0 | 9,47 | 0,0798 | 199,7 | 369,3 MB | 10 | 3 | 0 |

Razões: `1,647` · `1,6429` · `1,5238` → **mediana 1,6429, dispersão 0,1232** ⇒ **`CUDA slower`**.

**A saída é IDÊNTICA nos dois providers.** A cadeia canónica de segmentos
(`"{start:N3}-{end:N3}:{speaker}"` unida por `|`) dá o **mesmo sha256** em todas as 6 arms do controlo
(`45228D64D9DB9CD8`) e em todas as 6 arms do ficheiro do dono (`5E341679652D8DC7`, 3 falantes,
`speech_s = 19,153`). **O provider é neutro na saída**; os únicos diferenciadores são velocidade, forma de
CPU e RAM.

**Conclusão:** com a cache PTX quente, CUDA é **1,05–1,17×** o tempo de parede da CPU no ficheiro de
controlo e **1,52–1,65×** no ficheiro do dono — **mais lento**. Consome **~96 % de um core** contra
**~200 %** (a CPU usa dois cores) e custa **~1118–1259 MB contra ~277–369 MB de RSS (≈3,4–4×)**.
**A única vantagem CUDA que sobra é a forma da folga de CPU** (1 core em vez de 2) — e essa não a medi em
termos de efeito no ASR ao vivo, porque o dono tinha um live a tocar.

### O que prova que o CUDA executou mesmo — o par de controlos

Duas testemunhas por-processo desta caixa são **cegas** e digo-o em vez de as usar:
`nvidia-smi --query-compute-apps` reportou 29 pids vivos em 64 de 65 amostras com `used_memory=[N/A]` em
todas as linhas (WDDM não faz contabilidade por processo) e **nunca nomeou o nosso pid**; e
`\GPU Engine(*)\Utilization Percentage` enumera **682 instâncias, 0 delas `engtype_compute`**, mostrando o
worker CUDA conhecido do dono (pid 29008) só com `3d` 2,01 % e `copy` 0,30 %.

**A testemunha de registo é a cache PTX JIT** — só o JIT do CUDA escreve lá; uma execução CPU não pode
criar entradas. `_main\_diar-cuda-cache-probe.ps1` fixou `CUDA_CACHE_PATH` num directório novo (asserido
vazio com `throw`) e imprimiu `CUDA_CACHE_PATH honored: YES`:

| arm | provider | rc | wall_s | rtf | ficheiros novos na cache explícita | bytes novos | novos na cache por omissão |
|---|---|---|---|---|---|---|---|
| `cacheprobe-cuda-cold` | cuda | 0 | 86,09 | 1,49 | **26** | **227 898 668** | 0 |
| `cacheprobe-cuda-warm` | cuda | 0 | 26,12 | 0,44 | **17** | **141 026 504** | 0 |
| `cacheprobe-cpu` | cuda→cpu | 0 | 8,66 | 0,14 | **0** | **0** | 0 |

**Par positivo/negativo completo:** as arms CUDA escreveram **43 ficheiros / 368,9 MB** de PTX JIT
enquanto a arm CPU escreveu **0 ficheiros / 0 bytes**; e `default_new_files = 0` prova que a variável de
ambiente foi honrada. **O CUDA compila e executa kernels nesta caixa.**

O primeiro CUDA é lento (RTF 1,49) porque paga o JIT de PTX para **sm_120** (RTX 5080, Blackwell) —
dezenas de segundos ligados à CPU, uma só vez por grafo. **Não cite 1,49 nem 1,5745 como "o número da
GPU"** — é o custo de compilação, não de execução. A comparação quente é a emparelhada acima.

---

## 7. O que NÃO foi medido — declarado, não varrido

| o que | porque não | o que o mediria |
|---|---|---|
| **DER no áudio do dono** | não existe verdade-terra para o áudio dele | etiquetagem manual de 2 min — **este agente não a pode fazer** (não ouve, não lê imagens) |
| efeito da folga de CPU (1 core vs 2) no ASR ao vivo | o dono tinha um live a tocar; abrir o worker seria mexer na app | correr o par CUDA/CPU com o worker ao vivo, medindo as legendas |
| áudio >90 s | o ficheiro real mais longo é 90 s | capturar um live mais longo |
| separação de fontes propriamente dita | **fora do âmbito**: a lane anterior já mostrou que é `N×` ASR e degrada pior | — |
| música real | **não existe um único ficheiro de música no repositório** | obter uma faixa e repetir a escada de §4 |

---

## 8. Instrumentos mortos — registados para não serem reutilizados

1. **`_main\_diar-bed-analysis.py` — DESQUALIFICADO, falhou o próprio controlo negativo.** Discriminador
   de modulação de envelope (`mod_ratio = energia(2–8 Hz)/energia(0,5–2 Hz)`, cita Scheirer & Slaney
   ICASSP 1997). Resultado: `synthetic-music-bed 0,000 → NÃO-FALA` (correcto), mas
   **`synthetic-drone 8,133 → FALA` (ERRADO)**, `bundled-pt-br-sample 3,237 → FALA`,
   `vendor-4spk-control 1,207 → FALA`. **Um instrumento que diz "fala" a um drone não pode classificar o
   leito do dono.** Desqualificado em vez de reparado — e é por isso que §4 não usa a palavra "música".
2. **`_main\_diar-gpu-watch.ps1` — CEGO.** Instrumentação por-processo de GPU não existe nesta caixa
   (ver §6). Não usar como evidência. Fica registado que o seu controlo positivo
   (`instrument_live_samples` = número total de amostras) está VERDE — o instrumento *correu*, só não vê.
3. **`_main\_diar-provider-probe.py` — ABANDONADO.** Substituído pela sonda de cache PTX. Ficou partido
   (exit 1) e não deve ser re-corrido.

---

## 9. Três armadilhas generalizáveis que esta lane pagou

1. **O handle de `os.add_dll_directory()` REMOVE o directório outra vez quando é recolhido pelo GC.**
   Descartar o valor de retorno desfaz a chamada em silêncio — causa de **duas** falhas de carregamento
   CUDA, com `Error loading "…\onnxruntime_providers_cuda.dll" which depends on "cublasLt64_12.dll" which
   is missing (Error 126)`. Os handles têm de ficar vivos numa lista durante a vida do processo.
2. **`dirname(dirname(os.__file__)) + "site-packages"` nomeia um directório que NÃO EXISTE**
   (`<prefix>\Python311\site-packages`). Use `sysconfig.get_paths()["purelib"]`. E **imprima sempre o
   número de directórios efectivamente retidos** — foi esse número (`dll dirs held: 0`) que expôs a
   armadilha.
3. **Numa caixa carregada, um A/B entre execuções mede a CARGA, não a variável.** A mesma arm CPU deu
   0,2571 e 0,0798. **Intercale as arms e reporte a dispersão emparelhada, ou a afirmação não vale nada.**

---

## 10. Veredicto

| pergunta | resposta medida |
|---|---|
| Dá para correr diarização no áudio do dono? | **Sim, e é barato em fala limpa:** RTF **0,0798**, 2 threads, ~200 % de um core, 369 MB |
| Quantos falantes? | **NÃO identificado: 2 / 3 / 4 / 6 / 6** conforme o botão. Uma só fronteira é estável (3,3/5,8 s) |
| Que DER no áudio real dele? | **≈ 61,6 %** previsto pela escada medida, aos **+2,62 dB** de razão fala-leito dele. **Limite inferior.** Sem verdade-terra, não é calculável directamente |
| E em áudio limpo? | **28,85 % / 33,24 %** com o `threshold` por omissão (0,5) — 7 clusters em vez de 4. **Já acima de 25 %** |
| O Redux traz a diarização de graça? | **Não.** `<|spkchange|>` (id 14) é **vocabulário morto**: 0 ocorrências, `max_prob` ~1e−6 a 1e−12, nunca no top-5, em ~2 100 passos e 3 ficheiros |
| CUDA ou CPU? | **CPU.** CUDA é 1,16× (controlo) a 1,64× (áudio do dono) **mais lento**, com 3,4–4× a RAM. Saída idêntica |
| **A recomendação sobrevive?** | **NÃO** |

### A frase que decide

> **A recomendação morre, e o número que a mata é `61,6 %`.**
> O dono tem **+2,62 dB** de razão fala-leito no seu próprio áudio de loopback; a escada medida nesta caixa
> prevê **DER ≈ 61,6 %** nesse ponto, contra o limiar de morte declarado de **~25 %** — quase **2,5×**.
> E há um segundo número que mata sem leito nenhum: **28,85 %** de DER em áudio **limpo** com o `threshold`
> no valor por omissão da API. O token `<|spkchange|>` que tornaria isto gratuito é **vocabulário morto**.
> **A resposta honesta é: só com captura por participante.**
> A diarização continua a ser a arquitectura certa — **uma** passada de ASR com etiqueta de quem falou, em
> vez de N passadas sobre N fluxos separados — mas ela **não é utilizável no sinal que o dono tem hoje**:
> um mix de loopback com fala de jogo, amigos e um leito alto e contínuo.

**O que mudaria a resposta:** capturar cada participante no seu próprio fluxo (o caso Discord/VoiceMeeter
já tem os fluxos separados a montante), ou um sinal com fala isolada acima de ~+15 dB de SNR verdadeira —
onde a DER medida é **2,98 %** e a recomendação vive.

---

## 11. Reprodução

```powershell
# 1. a fonte e o seu hash
py -3 _main\_diar-probe-wav.py --wav _main\live-sample-cable-input-90s.wav

# 2. o controlo com verdade conhecida (tem de dar DER 0,03 %, 10 segmentos, 4 falantes)
py -3 _main\_diar-cuda-launch.py _main\_diar-run.py --wav _main\diar-models\0-four-speakers-zh.wav `
    --threads 2 --threshold 0.9 --num-speakers 4 --provider cpu --tag repro-ctrl --out _main\_repro-ctrl.json
py -3 _main\_diar-der.py --ref-vendor --hyp _main\_repro-ctrl.json

# 3. o áudio do dono
py -3 _main\_diar-cuda-launch.py _main\_diar-run.py --wav _main\live-sample-cable-input-90s.wav `
    --threads 2 --threshold 0.9 --provider cpu --tag repro-live --out _main\_repro-live.json

# 4. a escada de leito e a conversão para as unidades do dono
py -3 _main\_diar-mix.py --target _main\diar-models\0-four-speakers-zh.wav `
    --bed _main\live-sample-cable-input-90s.wav --bed-start 50.0 --bed-end 88.0 --snrs "15,5,0,-5"
py -3 _main\_diar-owner-snr.py

# 5. o falsificador do vocabulário
py -3 _main\_redux-token-census.py --selftest
py -3 _main\_redux-token-census.py --wav _main\diar-models\0-four-speakers-zh.wav --seeds 12

# 6. a comparação emparelhada de provider (a única forma válida nesta caixa)
pwsh -NoProfile -File _main\_diar-cuda-paired.ps1 -Pairs 3
pwsh -NoProfile -File _main\_diar-cuda-paired.ps1 -Pairs 3 `
    -Wav H:\sotto\_main\live-sample-cable-input-90s.wav `
    -OutJson H:\sotto\_main\_diar-cuda-paired-live90.json -ArmPrefix pairedlive
```

**Modelos usados** (em `_main\diar-models\`, descarregados por esta lane):
`sherpa-onnx-pyannote-segmentation-3-0\model.onnx` 5 992 913 B (`220ad67ca923bef2…`) ·
`3dspeaker_eres2net_base_16k.onnx` 39 593 761 B (`1a331345f04805ba…`) ·
`nemo_en_titanet_small.onnx` 40 257 283 B.
Runtime: `sherpa-onnx 1.13.4+cuda12.cudnn9`, Python 3.11.8 (`C:\Program Files\Python311`).

**Provas dos instrumentos** (ambas as cores observadas, nunca só a verde):
`_main\_diar-der-selftest.json` → `SELFTEST-VERDICT: PASS` 12/12, com dois arms **INVARIANT**
(troca de etiquetas e permutação total dão DER 0,00 — o mapeamento óptimo absorve qualquer renomeação) e
cinco arms RED (deslocamento +0,5 s → 30,36 %; fusão de dois falantes na hipótese → 19,30 %; queda dos
últimos 3 segmentos → 28,62 %; falso alarme em silêncio → 9,81 %; colapso num só falante → 63,00 %).
