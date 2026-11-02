# 2026-11-02 — o fade fora, o corte duro do ganho, e a repetição no seam do chunk

Três ordens do dono nesta conversa, nesta ordem: *"e tira a animacao de fade in"*, e
antes dela o par que ficou aberto — *"a transcrição ao vivo não funciona direito e é
lerdo pra caralho"* + *"parece que só usa meu microfone e não qualquer audio"*. E a
ordem que enquadra tudo: *"nao mandei tu diagnosticar e parar. é pra diagnosticar e
arrumar"*.

Cada número abaixo foi medido **no caminho vivo**, não numa reimplementação dele.

---

## 1. O fade de entrada — fora

| onde | o que era | o que é |
|---|---|---|
| `app/panel/panel.css` `.caption` | `animation: caption-in 220ms` (opacity 0→1 + translateY 5px) | `animation: none` |
| `app/panel/panel.css` `.caption__word[data-typing]` | `animation: sotto-word-in 140ms` | `animation: none !important` |
| `app/panel/themes/cinematic.css` | `cine-fade 450ms` / `cine-rise 500ms` no MESMO seletor (2 temas) | removidos |
| `@keyframes caption-in`, `@keyframes sotto-word-in` | — | apagados (código morto) |

O `!important` não é decoração: `cinematic.css` declara no **mesmo** seletor e carrega
**depois** de `panel.css`; sem ele, escolher um tema da zip voltava a pôr a legenda a
esbater-se. Prova no banco de ensaio (`_main/sim/panel-sim.py`, Chromium real, emissão
de uma legenda `external:youtube:track` a crescer palavra a palavra):

```
rowAnim=none  typingAnim=none  rowAnims=0   (4 emissões, cada uma medida)
com a regra do tema injectada AO VIVO:
typingAnim=none  rowAnim=none  animations=0   ← o guarda `!important` ganha
```

## 2. O ganho que cortava a onda — `peak_out = 1.000000` em todos os ticks

Instrumento: 30 s do loopback `VoiceMeeter Input` capturados com
`worker/wasapi_loopback.py` (`I:/cc-tmp/cap.wav`), alimentados ao caminho vivo por
`SOTTO_FILE_TAP` — o mesmo `asr_thread`, o mesmo gate, o mesmo AGC, sem abrir
dispositivo.

A captura, medida: pico bruto **1,0045**, RMS **-23,7 dBFS**, mediana por chunk
**-51,1 dBFS**, 21,8 % de silêncio digital.

Antes (`WORKER_STATS`, caminho vivo):

```
peak_out=1.000000  gain_max_db=+23.5  gain_would_max_db=+24.0   em TODOS os ticks
```

O `AutoGain._process_sub` multiplicava pelo ganho e **depois** fazia
`np.clip(out, -1, 1)` — um corte duro. O alvo de RMS (-20 dBFS) não vê o pico, por isso
pedia +24 dB numa onda que já tocava no teto.

Cura: **teto de pico** (`AGC_CEILING = 0.98`), aplicado **antes** de multiplicar; o
ganho aplicado desce até o pico caber, e o `self.gain_db` suavizado (ataque/libertação)
não se move com isso. Contadores novos em `WORKER_STATS`: `limited_blocks`,
`limit_db_min`.

Depois, no mesmo áudio, mesma sonda: **`peak_out=0.980000`, `limited_blocks=3`**.

Portão: `_main/agc_order_probe.py` arm **D** — pico de entrada 0,9928 com o alvo a pedir
+24 dB; exige `peak_out <= AGC_CEILING` e `limited_blocks > 0`, e reproduz o defeito
em ficheiro (`old_peak=1.0000`) como controlo. `--neg-arm` desarma
`if g > g_ceiling` num TOKEN numa cópia do worker e exige RED:
`NEG-ARM mutant rc=1 caught=True`, `peak_out=1.0000 limited_blocks=0`.

## 3. A repetição no seam do chunk — `tem umas tem umas`

Os textos dos chunks, verbatim do run `SOTTO_FILE_TAP`:

```
14,00-14,56 'caramba'   16,24-16,80 'tem'   16,80-17,36 'umas'
17,36-17,92 'tem umas'  17,92-18,48 'youtuber que' ...
```

Linha publicada: `caramba tem umas tem umas youtuber que elas só são sapadas mesmo não é`.

**Uma hipótese, e o que a refutaria:** o carry do predictor entre chunks. Refutação
medida: com o carry desarmado (símbolo + `h`/`c` zerados por chunk) no MESMO áudio, o
run inteiro colapsa para **`Caram Tem`** — o carry é obrigatório. Logo a cura não pode
ser no decode.

Cura: `dedup_seam_repeat()` em `worker/sotto_worker.py`, chamado no **único** lugar que
decide texto (`join_fragments`) e nas duas outras montagens de texto do ficheiro
(`state=done.text`, `--selftest`). **Uma** palavra repetida é fala (`nao nao`, `é é`) e
sobrevive; **duas ou mais**, contíguas, são o artefacto. O limite superior (6) impede
engolir uma frase repetida de propósito.

Depois, mesmo áudio, mesma sonda:

```
last caption: caramba tem umas youtuber que elas só são sapadas mesmo não é
done.text   : caramba tem umas youtuber que elas só são sapadas mesmo não é
```

Portão: `_main/caption-seam-dedup-oracle.py`, sete arms (A colapso medido, B uma
palavra sobrevive, C o rabo mais longo ganha, D não-adjacente intocado, E integração
pelos fragmentos MEDIDOS, F idempotência, G as três montagens de texto) e `--neg-arm`
com `SEAM_REPEAT_MIN_WORDS = 1` a derrubar a arm B: `caught=True`.

## 4. O que NÃO era defeito — medido, para não voltar a caçar fantasmas

| hipótese | medição | veredicto |
|---|---|---|
| "só usa meu microfone" | varredura de 11 endpoints a 400 ms: só `VoiceMeeter Input` tem sinal (peak 0,394); todos os outros 0,000. O endpoint em uso é o **loopback dele** (áudio do sistema). | **não é o microfone** |
| "o nível baixo impede o modelo" | 30 s normalizados a -3 dBFS de pico: **mesmos 27 tokens, mesmo texto** | nível não é o limite |
| "mais ganho recuperava a fala" | mutante com `AGC_MAX_GAIN_DB = 40` / alvo -18: **mesmo texto, mesmos 27 tokens**, `blank_frac` 0,912 | ganho não é o limite |
| "o motor é lento" | `rtf = 0,25` (`infer_wall_s=7,0` para `audio_s=28,56`) — **4× mais rápido que o tempo real**; cadência dos eventos: **0,56 s de áudio / ~0,55 s de parede** por chunk | o motor não é o "lerdo" |
| "o gate come a fala" | `music_gated_chunks=7` de 51; `gate_kept` alto; a transcrição sai coerente | não é o gate |

O que sobra e é do **áudio dele**: a mediana por chunk é **-51 dBFS**, com 75 % dos
chunks abaixo de -30 dBFS — trechos longos de música/pausa. Nesses, o modelo emite
*pouco* (blank_frac ~0,91), e "pouco" lido no ecrã parece "lerdo". Nenhum ganho muda
isso: foi medido duas vezes.

## 5. O caminho da legenda: os números que sobraram

`BRIDGE_CAPTION_SENT` → `CAPTION_APPLIED` na sessão dele (`pid 36532`, 125 pares):
p50 **1,515 s**. **Este número NÃO é latência de pintura** e não se apresenta como tal:
`CAPTION_APPLIED` é emitido no caminho do *commit* (`panel.js` `commitCaption`), isto é,
quando a linha **fecha** — e a linha fecha 1,5-8 s depois de nascer. A latência da
pintura provisória não tem instrumento hoje; fica declarada em
`docs/por-medir.md`-classe, não afirmada.
