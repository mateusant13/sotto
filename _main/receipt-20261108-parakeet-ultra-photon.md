# Recibo — `parakeet-ultra` vs `parakeet-redux` no MESMO runtime (Photon / kestrel), CUDA e CPU

**Data/hora:** 2026-11-08, corridas entre 01:55 e 02:22 (hora local, UTC−03:00).
**Máquina:** a do dono — RTX 5080, Intel64 Family 6 Model 183 (20 lógicos: 12 P + 8 E), Windows 10.0.26200.
**Runtime (os dois braços):** `kestrel.models.parakeet_tdt.runtime.ParakeetTdtRuntime` — o mesmo que
`worker/redux_batch.py` usa em produção. `torch 2.7.0+cu128`, `kestrel` de
`C:/Program Files/Python311/Lib/site-packages/kestrel`, `python 3.11`.
**Instrumento:** `_main/_cache/ultra-photon-measure.py` (dois defeitos do script de 2026-11-04 corrigidos —
§ "O que estava errado no instrumento"). Um processo pesado de cada vez; CPU sempre sob o ceiling da casa
(`I:/!watcher`: `python -m watcher run --cpu 40 --cwd H:/sotto -- python -u ...`).
**Ficheiros (os mesmos para os dois):** `_main/live-sample-cable-input-90s.wav` (90,000 s),
`_main/pt-br-sample.wav` (15,000 s), `_main/en-us-sample.wav` (8,543 s).

`xrt` = duração do WAV ÷ `infer_s` (o runtime reporta `source_duration_seconds` igual ao WAV em todas as
linhas: 90,000 / 15,000 / 8,543 — é a prova de que a chave lida agora é a real).
`p1` = primeira chamada no processo (inclui captura de CUDA graph no CUDA); `p2`/`p3` = chamadas seguintes.

## VEREDITO

**No mesmo runtime, ultra e redux são indistinguíveis em velocidade; o truncamento era do nosso export; o
único custo que fica é 7,02× de disco — e a rota CPU que embarca só existe para o ultra.**

- **CUDA a quente:** 90 s — ultra **0,750–0,849 s** contra redux **0,699–0,731 s** (redux 7–14 % mais
  rápido); 15 s — **0,162–0,172 s** contra **0,165–0,201 s** (ultra 2–16 % mais rápido); 8,5 s —
  **0,133–0,155 s** contra **0,156–0,160 s** (ultra 3–14 % mais rápido). **Primeiro passe** de 90 s:
  6,005 s contra 5,792 s — empate. Nenhuma destas diferenças sobrevive como "custa 3,5×".
- **VRAM (pico do allocator, CUDA):** ultra **3 160,1 MB** vs redux **3 206,2 MB** no clipe de 90 s (−1,4 %);
  nos curtas 2 657,5/2 614,8 vs 2 703,6/2 660,9 MB. Praticamente iguais.
- **CPU (ceiling 40 %):** ultra **4,8–5,1×** tempo real; redux **denso** **5,1–5,9×** (10–15 % mais rápido),
  mas o redux **como embarca não carrega** nesta máquina (sem kernel int8 — erro medido abaixo).
- **Qualidade:** nos dois clipes curtos o texto é **carácter-a-carácter igual**. No de 90 s o ultra devolve
  **54 palavras** e o redux **52**, e o redux troca "missões secundárias" por "saquudares"/"saqueudares";
  observação, não WER (não há referência).
- **Disco:** 1 256 514 499 B contra 179 015 759 B = **7,02×**.
- **O número do briefing confere:** 90 s a quente = **0,750 s / 119,98× / 3 160,1 MB** (briefing: 0,77 s /
  ~117× / 3 160 MB).

## Tabela 1 — CUDA (RTX 5080, `--device cuda --repeat 3`)

| engine | WAV | load_s | p1 s | p2 s | p3 s | xrt (p2–p3) | VRAM pico MB (torch) | palavras |
|---|---|---|---|---|---|---|---|---|
| ultra (kestrel) | live-sample 90 s | 5,34–6,27¹ | 6,005 | 0,849 | **0,750** | **106–120×** | **3 160,1** | 54 |
| ultra (kestrel) | pt-br 15 s | 5,34–6,27¹ | 0,172 | 0,162 | **0,163** | 92× | 2 657,5 | 26 |
| ultra (kestrel) | en-us 8,543 s | 5,34–6,27¹ | 0,155 | 0,133 | **0,140** | 61–64× | 2 614,8 | 23 |
| redux (ternary) | live-sample 90 s | 4,98–6,16 | 5,792 | 0,731 | **0,699** | **123–129×** | **3 206,2** | 52 |
| redux (ternary) | pt-br 15 s | 4,98–6,16 | 0,201 | 0,165 | **0,186** | 81–91× | 2 703,6 | 26 |
| redux (ternary) | en-us 8,543 s | 4,98–6,16 | 0,160 | 0,156 | **0,158** | 54× | 2 660,9 | 23 |

Comando (executado 02:0x–02:1x): `python -u _main/_cache/ultra-photon-measure.py --device cuda --repeat 3`
(cwd `H:/sotto`), uma vez por modelo. `p1` do ultra em 90 s deu 5,2 s / 6,0 s / 19,9 s em três corridas — a
captura de graph + compilação dos fallbacks `kestrel_kernels` no primeiro passe é sensível à carga da caixa
(partilhada com outros agentes), por isso a linha mostra a corrida limpa e a variância fica declarada.
¹ o `load` do ultra nesta última corrida levou 187,95 s porque a caixa estava carregada; nas duas anteriores,
5,34 s e 6,27 s. `load_s` não serve para decidir — o `infer_s` serve.

## Tabela 2 — CPU (ceiling `--cpu 40`, `torch_threads=14`, `--device cpu --repeat 3`)

| engine | WAV | load_s | p1 s | p2 s | p3 s | xrt (p2–p3) | RSS pico MB | palavras |
|---|---|---|---|---|---|---|---|---|
| ultra (kestrel) | live-sample 90 s | 3,47 | 17,694 | 17,700 | **18,600** | 4,8–5,1× | 5 105–5 138 | 54 |
| ultra (kestrel) | pt-br 15 s | 3,47 | 3,135 | 3,293 | **2,925** | 4,6–5,1× | 4 572–4 575 | 26 |
| ultra (kestrel) | en-us 8,543 s | 3,47 | 1,779 | 1,789 | **2,081** | 4,1–4,8× | 4 522–4 523 | 23 |
| redux **denso** (nota) | live-sample 90 s | 9,06 | 16,083 | 15,303 | **16,001** | 5,6–5,9× | 4 458–4 532 | 52 |
| redux **denso** (nota) | pt-br 15 s | 9,06 | 2,675 | 2,539 | **2,620** | 5,6–5,9× | 3 848 | 26 |
| redux **denso** (nota) | en-us 8,543 s | 9,06 | 1,664 | 1,651 | **1,554** | 5,1–5,5× | 3 848 | 23 |
| redux **como embarca** | — | **não carrega** | — | — | — | — | — | — |

Comando (executado 02:1x–02:2x): `python -m watcher run --cpu 40 --cwd H:/sotto -- python -u _main/_cache/ultra-photon-measure.py --device cpu --models ultra --repeat 3`
e o mesmo com `--models redux --cpu-dense-fallback`.

- **redux como embarca, na CPU: recusa no load, medida.** `NotImplementedError: ternary weights need an int8
  matrix-multiply kernel on the CPU (avx512vnni, avxvnni or avx2 on x86; ...); the path in use here is
  'scalar'` (`kestrel_kernels/ternary.py:126`, via `kestrel/models/parakeet_tdt/weights.py:201`). A extensão
  nativa responde `gemm_isa_available("avx2") = False` nesta máquina (Raptor Lake com AVX2 fisicamente), facto
  do binário/ambiente, não do modelo. As linhas "denso" usam o fallback que o próprio vendor documenta
  (`resident_form` → `dense`, `kestrel_kernels/ternary.py:114-118`), forçado por `--cpu-dense-fallback` e
  marcado em cada linha (`dense_cpu=true`). **Não são a rota que embarca.**
- `load_s` variou entre corridas (ultra CPU: 3,47 s / 5,08 s / 100,43 s conforme a carga da caixa; redux:
  7,07 / 9,06 s). É o número menos estável do recibo; os `infer_s` de uma mesma corrida repetem dentro de
  ±10 %.

## Texto devolvido (o que a tabela pesa em palavras)

Clipe de 90 s, CUDA e CPU, texto idêntico entre rotas dentro de cada modelo:

- **ultra (54 palavras):** "Eu não consigo pegar mil de força, mano. Luvas do perseguidor. Foca nas missões
  secundárias e fazer as DGs que são os pontos. Foca nas missões secundárias e fazer as DG, que são os pontos
  em interrogação. Elas aumentam sua barra vermelha embaixo no mapa e dá a UP para sua asa. Ó, infonova."
- **redux (52 palavras):** "Eu não consigo pegar mil de força, né? Luvas do perseguidor. Foca nas saquudares
  e fazer as DGs que são os pontos. Foca nas saqueudares e fazer as DG, que são os pontos em interrogação.
  Elas aumentam sua barra vermelha embaixo no mapa e dá a UP para sua asa. Ó, infônova."

`pt-br-sample` (26 palavras) e `en-us-sample` (23 palavras): **texto carácter-a-carácter igual** entre ultra e
redux, nas duas rotas. Não há ganho de qualidade a comprar nos clipes curtos.

## A frase que corrige a recusa de 2026-11-04

> **CORRIGIDO:** a recusa de 2026-11-04 (`_main/receipt-20261104-parakeet-ultra-refused.md`) media o ultra
> pelo **nosso export ONNX** contra o redux **ONNX int4** — dois runtimes diferentes — e concluía "não ganha,
> custa 3,5× e TRUNCA áudio longo". No **mesmo** runtime (Photon/kestrel): (a) **não trunca** — 90 s → 54
> palavras e o texto completo, contra as 9 palavras do export; (b) **não custa 3,5×** — a quente fica no mesmo
> patamar (90 s: 0,750–0,849 s do ultra contra 0,699–0,731 s do redux; 15 s: 0,162–0,172 s contra
> 0,165–0,201 s; 8,5 s: 0,133–0,155 s contra 0,156–0,160 s), e a VRAM é praticamente igual (3 160,1 MB contra
> 3 206,2 MB no clipe de 90 s); (c) **o que fica de pé é o disco** — 1 256 514 499 B contra 179 015 759 B
> (7,02×) — **e a ausência de rota CPU para o redux como embarca** nesta máquina. O "não ganha em qualidade"
> continua **não testado com WER** (§ não medido); no clipe de 90 s o ultra acertou "missões secundárias" onde
> o redux escreveu "saquudares"/"saqueudares" duas vezes, o que é uma observação, não um WER.

## Custo de disco, byte exacto

Comando (executado 02:23, reproduzido agora com o mesmo resultado):

```
python -c "import os
for d in [r'I:/cc-tmp/models-src/parakeet-ultra-kestrel', r'H:/VOD.RIP-models/photon-hf/hub/models--moondream--parakeet-redux/snapshots/2bf128600aac4b16946f7ed8372e56117fe5e23b']:
    print(d, sum(os.path.getsize(os.path.realpath(os.path.join(d, n))) for n in os.listdir(d) if os.path.isfile(os.path.realpath(os.path.join(d, n)))))"
```

| checkpoint | ficheiros | bytes |
|---|---|---|
| `parakeet-ultra` (layout Photon, `I:/cc-tmp/models-src/parakeet-ultra-kestrel`) | `config.json` 1 153 + `model.safetensors` 1 255 353 386 + `tokenizer.json` 1 159 960 | **1 256 514 499** |
| `parakeet-redux` ternary (`moondream/parakeet-redux`, snapshot local do hub) | 6 ficheiros (pesos 177 774 490 + `config.json` 12 988 + `ternary.json` 57 970 + `tokenizer.json` 1 159 960 + README/.gitattributes) | **179 015 759** |

= **7,02×** em disco no total, **7,06×** só nos pesos (1 255 353 386 ÷ 177 774 490); 1 077,5 MB de diferença.
O total do redux bate ao byte com `_main/PIPELINE-WORKS.md:20` (179 015 759), o que valida a sonda.

**Nota de caminho medida:** `worker/models/parakeet-redux-ternary` **não existe** hoje nesta máquina
(`cmd /c dir H:\sotto\worker\models` → só `nemotron-3.5-asr-ptbr-onnx-int4`, `parakeet-redux-onnx-int4`,
`punct-en`; nenhuma junction). O checkpoint do Photon foi medido a partir do snapshot local do hub, que é o
destino que essa pasta deve ter. Ou seja: `worker/redux_batch.py` tal como está recusa hoje por falta do
directório — falha de instalação, não de modelo, e anterior a este recibo.

## O defeito do meu export ONNX

1. **Medido:** no export `I:/cc-tmp/models-src/parakeet-ultra-onnx`, o passo **[22,52–50,04] s** do clipe de
   90 s devolveu **3 440 tokens, todos id 0 e duração 0** (`10 × 344` frames), **texto vazio** — registado em
   `worker/parakeet_ultra.py:86-96`; reprodução: `python _main/parakeet-ultra-oracle.py --engine ultra-onnx`
   (corrida de 2026-11-04 23:43–23:47, 90 s → 62,521 s e 9 palavras no recibo dessa data).
2. **Causa:** o laço do export faz `frame += 0` e nunca avança; só o BLANK é resgatado com passo de 1 — o
   orçamento fica **por frame em vez de por sequência** (`_greedy_onnx`,
   `worker/parakeet_ultra.py:100-133`), e o `[22,52–50,04]` esgota os 344 frames a emitir zeros.
3. **O caminho do fabricante não tem o defeito:** no mesmo clipe de 90 s o kestrel devolveu **54 palavras e o
   texto completo** (tabela 1). O truncamento era do export caseiro; o modelo não trunca. Esta linha corrige
   o fundamento 3 da recusa de 2026-11-04.

Não re-medido hoje por instrução explícita ("não re-meca o que já está medido"); os números acima são os da
medição que produziu o comentário do código e o recibo de 2026-11-04.

## O que NÃO foi medido

- **WER num corpus.** Não há transcrição de referência para os três WAVs; a comparação é de texto entre
  motores, e nos clipes curtos os textos são iguais (WER igual, mas contra nada). O "não ganha qualidade" da
  recusa continua **não demonstrado** por WER — só não contradito.
- **Rota viva de 30 s** (a janela que o produto usa ao vivo): medidos 8,5 s e 15 s, não a janela exacta.
- **VRAM por processo do driver:** `nvidia-smi --query-compute-apps=pid,used_memory` devolve `[N/A]` neste
  WDDM; `vram_peak_mb` é o allocator do torch (exacto para o que o runtime aloca, cego a alocações nativas
  fora do torch).
- **Sensibilidade a threads na CPU** (14 threads por omissão; uma corrida anterior com `torch.set_num_threads(2)`
  deu 16,96 s contra 21,34 s no clipe de 90 s do ultra — sinal de que a rota CPU é sensível ao escalonador,
  não varrido).
- **Estabilidade térmica / 10+ minutos de carga** e **throughput de disco** na carga (a variância
  3,47→187,95 s do `load_s` não foi isolada).
- **Qualidade do ultra noutros idiomas/domínios**: só pt-BR e en-US, um clipe cada.

## Como re-medir

```
python -u _main/_cache/ultra-photon-measure.py --device cuda --repeat 3
python -m watcher run --cpu 40 --cwd H:/sotto -- python -u _main/_cache/ultra-photon-measure.py --device cpu --models ultra --repeat 3
python -m watcher run --cpu 40 --cwd H:/sotto -- python -u _main/_cache/ultra-photon-measure.py --device cpu --models redux --cpu-dense-fallback --repeat 3
```

## O que estava errado no instrumento (corrigido no mesmo ficheiro)

1. `result.get("duration")` → o dict não tem essa chave; `_finalize` publica `duration_seconds` e
   `source_duration_seconds` (`kestrel/models/parakeet_tdt/runtime.py:823-835`,
   `kestrel/models/asr/contract.py:60-95`). O `audio_s` saía `0.0` e todo o `xrt` saía `0`. Agora o `xrt` usa
   a duração do WAV (`soundfile.info`) e a duração reportada fica ao lado como contraprova.
2. Braço redux apontava para `worker/models/parakeet-redux-onnx-int4` (ONNX sem `model.safetensors`/
   `tokenizer.json`/`ternary.json`): o loader recusava. Agora aponta ao snapshot Photon do hub, com
   `--redux-dir` para override.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: UltraReceipt
- source: G:\env-data\superharness\usage_telemetry\model-usage.jsonl
- cache: read=UNKNOWN — cache-read field absent or invalid on one or more matched usage rows write=UNKNOWN — cache-write field absent or invalid on one or more matched usage rows hit=UNKNOWN — input/cache-read denominator incomplete or zero; universe: 0 usage rows from G:\env-data\superharness\usage_telemetry\model-usage.jsonl; instrument: scripts/cache-task-report.sh
- price: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available; UNKNOWN — no usage rows matched, so there is no price to partition
- when-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['UltraReceipt']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- where-failed: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['UltraReceipt']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- report generated_at: 2026-11-08T05:17:13.146466+00:00
- usage rows: 0
- model + route: UNKNOWN — no provider usage rows matched
- input tokens: UNKNOWN — input field absent or invalid on one or more matched usage rows
- output tokens: UNKNOWN — output field absent or invalid on one or more matched usage rows
- cache-read tokens: UNKNOWN — cache-read field absent or invalid on one or more matched usage rows
- cache-write tokens: UNKNOWN — cache-write field absent or invalid on one or more matched usage rows
- hit ratio: UNKNOWN — input/cache-read denominator incomplete or zero
- cost: UNKNOWN — cost field absent or invalid on one or more matched usage rows; no complete total or rate card available
- price partition: UNKNOWN — no usage rows matched, so there is no price to partition
- prefix breaks: UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['UltraReceipt']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- WHEN / WHERE failed:
UNKNOWN — no ledger break row attributable to this task: 1831 provider-request (kind=call) prefix-break rows exist, 0 attributable to keys ['UltraReceipt']; this task's identity matches no ledger row; agent_id is present on 26538 of 105775 ledger rows and on every row written since 2026-09-21T20:45:15.452000+00:00 (state=KEY-ABSENT; population: 0 of 105775 ledger rows carry this identity; window: UNKNOWN — ts_unix_ms absent on the rows in scope; key: agent_id/session_id in the SH ledger)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

## SELF-AUDIT

- **protocolos em falta** — não guardei um log com timestamp por corrida (o shell não estampa cada comando):
  a "hora" deste recibo é a janela da sessão, não o relógio de cada linha. O protocolo que faltou foi
  `tee` de cada corrida para `_main/_cache/ultra-photon-<epoch>.log`; com ele, cada número teria hora própria.
- **verificacao adicional** — corrida tripla por braço, feita. Foi ela que apanhou o `load` de 187,95 s e o
  `p2 = 1,245 s` contaminado pela carga da caixa: com um `p2` único eu teria publicado um número ~60 % acima
  do real.
- **checkboxes novas** — por braço, 3 passes e um assert mecânico: `max(p2,p3)/min(p2,p3) <= 1.5` (senão a
  linha é `STABLE=no` e não entra na decisão) e `load_s` explicitamente fora da tabela de decisão.
- **review por outro subagente** — `sim-com-escopo` — a tabela, o veredito e a frase de correção; o ponto mais
  frágil para atacar é a escolha de `p2–p3` como "a quente" e a ausência de WER.
- **gate-doubt**:
  - `verde-de-verdade:` os três verdes que sustentam o recibo são (i) `source_duration_seconds == wav_s` em
    todas as 36 linhas medidas — o leitor antigo devolvia 0,0, logo a igualdade não passa por construção;
    (ii) VRAM de 3 160,1 MB contra os 3 160 MB do briefing, instrumento independente, mesmo número ao décimo;
    (iii) 90 s a quente 0,750 s contra os 0,77 s do briefing. Cada um falharia com a chave errada, o modelo
    errado ou o leitor errado.
  - `falta-no-gate:` nada no instrumento impede publicar números de uma caixa carregada como se fossem limpos
    — foi exactamente o que produziu o `p2 = 1,245 s` e o `load = 187,95 s`. Um run futuro com outro agente a
    saturar a CPU reproduz o erro sem aviso nenhum.
  - `gate-melhor:` `assert max(p2,p3)/min(p2,p3) <= 1.5` e `assert p1 <= 20*min(p2,p3)` por linha, mais
    repetir o `load` quando ele exceder 4× o menor `load` do mesmo modelo; o input que TEM de ficar RED é a
    corrida registada aqui com `load=187,95 s` e `p1=19,927 s`.
- **confianca** — `alta` para o CUDA (3 passes, VRAM reproduzida ao décimo, dois modelos no mesmo processo de
  medição); `media` para a CPU (3 passes, mas caixa partilhada e `load_s` instável).
- **nao verificado** — WER contra transcrição de referência; janela viva de 30 s; VRAM nativa fora do torch;
  rota CPU do redux como embarca (não existe nesta máquina); sensibilidade a threads na CPU.
