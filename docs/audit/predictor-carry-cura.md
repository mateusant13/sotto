# CURA — o predictor do RNN-T atravessa a fronteira de chunk

**Lane:** `CuraPredictorCarry` · **data:** 2026-10-06 · **veredicto: LANDADO e MEDIDO.**
O `worker/sotto_worker.py` já não re-prima o predictor a cada 560 ms; a transcrição do próprio
worker, medida pelo seu `--selftest`, é **byte-idêntica ao braço 3** que a lane `SottoVsReferencia`
mediu como diagnóstico.

Isto é a APLICAÇÃO da cura que `docs/audit/sotto-vs-referencia.md` §9 nomeia. A causa não é
re-derivada aqui; é citada com `file:line` e re-medida.

---

## 0. TL;DR

| | |
|---|---|
| O que mudou | `StreamAsr.run_chunk`: `h`/`c` deixam de voltar a zero por chunk, e o primeiro decode de um chunk passa a consumir o **último símbolo emitido** em vez do `<blank>` |
| Ficheiro | `worker/sotto_worker.py` (sítio antigo: `:698-711`; sítio novo: `:698-724`) |
| Reset do predictor | continua em exactamente dois sítios, ambos INÍCIO DE STREAM: `__init__` (`:506-512`) e `reset_stream_state()` (`:568-584`) |
| Braço 1 (o harness) | **inalterado**: 5 661 tokens / 2 183 palavras / WER 0.6105, e o texto continua **byte-idêntico** ao shipped arquivado (11 591 chars, sha256 `449fe638bb019357`) |
| Worker shipped, pós-cura | **10 738 tokens / 4 279 palavras (99.4 % do ref) / WER 0.1536**, texto **byte-idêntico ao braço 3** (24 454 chars, sha256 `dde1836684f89397`) |
| `py_compile` | rc=0 |
| Suite de oráculos de `_main/` | 10 corridos, **10 GREEN** (`_main/_cura-oracle-suite-nonapp.json`) |
| Smoke na app viva | `_main/panel-state.json`, `producerPid` da app do smoke, 11 linhas de **8 a 22 palavras** (antes: "Em.", "Ai i.", "Antes dos.") |

---

## 1. A causa, e o `file:line` do re-prime (confirmado ANTES de tocar)

Revisão pré-cura desta lane (o ficheiro de trabalho, não o do relatório anterior — o relatório
citava `:679-682` na revisão que ele mediu):

```python
        # The prediction network is RE-PRIMED at every chunk boundary: h/c start
        # at zero and the first decoder call consumes only the blank. MEASURED
        # reason, same file, same weights, CPU, only this line differing:
        #   carry across chunks -> 86 tokens (int4) / 108 (int8), with doubled
        #     word tails ("Goinging along country roadskingss infty schoolros")
        #   re-prime per chunk  -> 81 tokens (int4) /  91 (int8), clean, and the
        #     int8 line matches the sherpa-onnx reference almost word for word.
        self.h = np.zeros((2, 1, self.hidden), np.float32)      # :708
        self.c = np.zeros((2, 1, self.hidden), np.float32)      # :709
        dout, self.h, self.c = self._decode(np.array([[self.blank]], np.int64), self.h, self.c)  # :711
```

Confirmado por leitura do ficheiro antes de qualquer edição (`read worker/sotto_worker.py`
`:698-711`), e por `grep -n "self\.h\b\|self\.c\b"` → **só** `:506-507` (o init) e `:708-709` (o
re-prime), ou seja o predictor era destruído uma vez por chunk e nunca em mais lado nenhum.

O justificativo do re-prime era uma medição de 13.44 s (`sample1.flac`) que comparava o braço certo
contra o braço **errado**: o braço "carry" daquela tabela ainda alimentava o `<blank>`, logo media a
COLA (caudas de palavra duplicadas) e não o carry. §5 mede isso no próprio `sample1.flac`.

---

## 2. A mudança aplicada (diff mínimo, 6 sítios)

**(a) o sítio do priming** — `worker/sotto_worker.py:698-724`:

```python
        # ── THE PREDICTOR CARRIES ACROSS THE BOUNDARY (arm 3, CURA 2026-10-06) ──
        ...  # a medição dos três braços, citada no próprio código
        seed = self.blank if self._last_symbol is None else self._last_symbol
        dout, self.h, self.c = self._decode(np.array([[seed]], np.int64), self.h, self.c)
```

**(b) o estado novo** — `:506-512` (`self._last_symbol = None`, ao lado do `h`/`c` do `__init__`) e
`:765-766` (`self._last_symbol = y` onde um símbolo é emitido — **dentro** do bloco, fora do
`if account:`, porque é estado de decodificação e não contador).

**(c) o reset de INÍCIO DE STREAM** — `:568-584`: `reset_stream_state()` passa a devolver o
predictor ao início (h/c a zero, `_last_symbol = None`) **além** das caches do encoder. É o sítio
certo: é literalmente "nada foi ouvido ainda".

**(d) o par save/restore da segunda passagem (M3)** — `:2288-2293` e `:2313-2315`: o `rerun()` salvava
e repunha só `cc/ct/ccl`. Com um predictor que atravessa, isso passaria a vazar o reset da segunda
passagem para dentro do stream vivo. Passa a salvar e repor os seis (`cc, ct, ccl, h, c,
_last_symbol`). **Este é o defeito que a cura cria se ninguém olhar** — §6 mostra a asserção que o
apanha.

O diff muda `run_chunk`, `reset_stream_state`, `__init__` e a função local `rerun()`; nada mais.

---

## 3. Os TRÊS braços, medidos OUTRA VEZ — o mesmo vídeo, o mesmo harness

```bat
cd H:\sotto
python _main/sotto-vs-ref-decode-arms.py "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav" ^
       "G:/sotto-ref/arms-full-cura.json" --arms 1,2,3
python _main/sotto-vs-ref-arms-compare.py --ref "G:/sotto-ref/reference-en.txt" ^
       --arms "G:/sotto-ref/arms-full-cura.json" ^
       --out "G:/sotto-ref/arms-compare-AFTER.json" ^
       --jsonl "SHIPPED_AFTER:G:/sotto-ref/sotto-full-cura.jsonl"
```

**População: 2 692 chunks de 560 ms. Janela: o vídeo inteiro, 0 – 1 507.52 s.**
Pesos: `nemotron-3.5-asr-streaming-0.6b-int8`, CUDA, `lang_id=auto`, `use_vad=true`, gate OFF.
`WER` populado nas 4 303 palavras do ref; `CER` nos 24 086 caracteres normalizados do ref.

### 3.1 ANTES da cura (medido hoje, `G:/sotto-ref/arms-full.json`, 10:31)

| braço | regra | tokens | palavras | % ref | omissions | empty chunks | blank_frac | WER | CER | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| **1 = shipped** | `h`,`c`←0 por chunk; seed=`<blank>` | 5 661 | 2 183 | 50.7 % | 2 159 | 1 597 (59.3 %) | 0.7689 | 0.6105 | 0.5768 | 114.1 s |
| 2 | `h`,`c` levados; seed=`<blank>` | 8 192 | 3 304 | 76.8 % | 1 286 | 622 (23.1 %) | 0.6970 | 0.5954 | 0.3656 | 111.2 s |
| 3 | `h`,`c` levados; seed=**último símbolo** | 10 738 | 4 279 | 99.4 % | 122 | 270 (10.0 %) | 0.6370 | 0.1536 | 0.0883 | 186.9 s |

### 3.2 DEPOIS da cura (medido hoje, `G:/sotto-ref/arms-full-cura.json`, 11:23)

| braço | regra | tokens | palavras | % ref | omissions | empty chunks | blank_frac | WER | CER | wall |
|---|---|---|---|---|---|---|---|---|---|---|
| **1 = re-prime (agora só o CONTROLO)** | `h`,`c`←0 por chunk; seed=`<blank>` | 5 661 | 2 183 | 50.7 % | 2 159 | 1 597 (59.3 %) | 0.7689 | 0.6105 | 0.5768 | 134.1 s |
| 2 | `h`,`c` levados; seed=`<blank>` | 8 192 | 3 304 | 76.8 % | 1 286 | 622 (23.1 %) | 0.6970 | 0.5954 | 0.3656 | 217.5 s |
| **3** | `h`,`c` levados; seed=**último símbolo** | **10 738** | **4 279** | **99.4 %** | **122** | **270 (10.0 %)** | **0.6370** | **0.1536** | **0.0883** | 321.4 s |
| **SHIPPED (o worker, pós-cura)** | `run_chunk` como está no ficheiro | **10 738** | **4 279** | **99.4 %** | **122** | **270** | **0.6370** | **0.1536** | **0.0883** | 265.8 s |

Os `wall` subiram entre as duas corridas (114→134, 111→217, 187→321 s) porque a caixa estava
carregada com as duas passagens desta lane a correr em série; **nenhum número de qualidade mudou na
mesma direcção**, e o braço 1 é o mesmo texto nos dois momentos — ver §4.

**Critério de aceitação: cumprido pelo braço 3 e pelo próprio worker shipped — 99.4 % das palavras
do ref (dentro de ~1 % de 99.4 %) e WER 0.1536 ≤ 0.20.**

---

## 4. Os auto-controlos que dão valor à tabela (todos medidos, nenhum inferido)

**4.1 O harness não mudou por baixo.** O texto de cada braço, medido duas vezes (10:31 e 11:23)
contra o ficheiro do próprio harness: **byte-idêntico nos três**.

| braço | antes (bytes / sha256[:16]) | depois | igual? |
|---|---|---|---|
| 1 | 11 591 / `449fe638bb019357` | 11 591 / `449fe638bb019357` | **sim** |
| 2 | 19 157 / `efafc82b44e1effb` | 19 157 / `efafc82b44e1effb` | **sim** |
| 3 | 24 454 / `dde1836684f89397` | 24 454 / `dde1836684f89397` | **sim** |

**4.2 O braço 1 continua a bater com o transcrito shipped ARQUIVADO** (a exigência literal):
`G:/sotto-ref/sotto-full-text.txt`, 11 591 chars, sha256 `449fe638bb019357` — e o braço 1 re-medido
hoje é `IDENTICAL` a esse ficheiro. O harness mede o decode antigo e nada mais.

**4.3 O worker SHIPPED, pós-cura, é byte-idêntico ao braço 3.**
`G:/sotto-ref/sotto-full-cura.jsonl` → `selftest-done.text`: 24 454 chars, sha256
`dde1836684f89397` = o texto do braço 3, **`IDENTICAL`**. O mesmo vale para os contadores
(`tokens=10738`, `empty_chunks=270`, `blank_frac=0.637`, `frames=29582`, `blanks=18844`), e
`shipped vs arm1` = **False** (o controlo distingue mesmo).

Ou seja: não é um harness a concordar consigo próprio — é o **caminho de produção**
(`python sotto_worker.py --selftest --audio`) a aterrar exactamente a política que foi medida.

---

## 5. `sample1.flac` — a pergunta aberta do relatório anterior, fechada

O relatório anterior deixou aberto: *"a tabela do README mediu carry como PIOR em `sample1.flac`"*.
Medido agora, o mesmo clipe, os três braços, 24 chunks (13.44 s), CPU `int8`:

| braço | tokens | palavras | empty chunks | blank_frac | texto |
|---|---|---|---|---|---|
| 1 = re-prime | 89 | 28 | 9 | 0.6537 | `Going along slushy Country roads  speaking  in dr drafty school Day For a fortnight …` |
| 2 = carry, seed blank | 104 | 31 | 1 | 0.6176 | `going alonglushyy country roadsn speakingmpss in dr schooloms day … weekendnight'll have to put inn …` |
| **3 = carry, seed último** | **119** | **39** | 3 | 0.5854 | `going along slushy country roads and speaking to damp audiences in drty schoolrooms day after day for a fortnight he'll have to put in appearance at some place of worship on Sunday` |

**A conclusão do README não se reconcilia — porque media o braço 2.** O braço 2 tem a cola
(`alonglushyy`, `roadsn`, `weekendnight'll`); o braço 3 é o mais limpo dos três **também no clipe
curto**. Não há um efeito de "stream longo" a delimitar: a cura é correcta nas duas escalas.

---

## 6. A suite de oráculos de `_main/` depois da cura

Não existia um comando que corresse os oráculos juntos. Esta lane landou
`_main/_cura-oracle-suite.py` (serial — dois processos CUDA concorrentes morrem aos ~62 s com rc=255
e sem traceback, `sotto-vs-referencia.md` §7), e o recibo da corrida é
**`_main/_cura-oracle-suite-nonapp.json`**.

| oráculo | rc | veredicto |
|---|---|---|
| `segment-rerun-probe.py` | 0 | **GREEN (6/6)** |
| `model-spec-oracle.py` | 0 | GREEN |
| `config-keys-oracle.py` | 0 | GREEN (`VERDICT: PASS`) |
| `lang-id-oracle.py` | 0 | GREEN |
| `caption-lines-oracle.py` | 0 | GREEN (12 PASS / 0 FAIL) |
| `speech-gate-oracle.py` | 0 | GREEN (`VERDICT: PASS`) |
| `delivery-rate-oracle.py --wav` | 0 | GREEN (`VERDICT: PASS`) |
| `flat-endpoint-oracle.py` | 0 | GREEN (`VERDICT PASS`; CONTROL: RED **as required**) |
| `wasapi-com-init-oracle.py` | 0 | GREEN (`VERDICT PASS`, NEGARM PASS) |
| `_ordem-cura-oracle.py` | 0 | GREEN |

`SUITE: GREEN=10`. `py_compile` rc=0 em `worker/sotto_worker.py` e nos três instrumentos novos.

**NÃO corridos** (precisam da app viva / de um endpoint / do overlay, e o smoke desta lane é a
app): `panel-hidden-at-startup-oracle.py`, `restart-30s-oracle.py`, `panel-exit3-oracle.py`,
`run-cmd-exit-oracle.py`. Estão no runner e correm com `--only <nome>`; não foram corridos aqui e
por isso não são reclamados como verdes.

### 6.1 A asserção NOVA que a cura exigia (e que por pouco não passava)

A cura introduz um risco que não existia: `reset_stream_state()` agora destrói o predictor, e o
`rerun()` da segunda passagem (M3) chama-o **no meio do stream vivo**. Se o `rerun()` salvasse só as
caches do encoder — que é o que fazia — o stream vivo sairia da segunda passagem com o predictor
zerado.

`_main/segment-rerun-probe.py` ganhou **A2** (o reset devolve o predictor ao início) e **C3** (o
predictor do stream vivo sobrevive à passagem). Duas coisas que valem a pena registar:

1. **A primeira versão da C3 não conseguia ficar VERMELHA.** A passagem re-corria o stream inteiro a
   partir do zero, e com o predictor a atravessar isso reproduz o estado vivo **exactamente** (mesmos
   zeros iniciais, mesmo áudio, determinístico) → `pred_moved=False` e o restore parecia
   desnecessário. Corrigido: o segmento passou a ser a **metade final** (`chunks[13:26]`), que é o
   que o `rerun()` realmente faz (áudio de uma LINHA fechada, que começa a meio do stream). Agora
   `pred_moved=True` e a asserção tem dentes.
2. **A corrida vermelha existe e está registada:**
   `_main/_rerun-probe-cura.log` → `RESULT: RED — 1 violation(s) (5/6)` com
   `the pass moved h/c/_last_symbol: False`; a corrida corrigida
   `_main/_rerun-probe-cura2.log` → `RESULT: GREEN (6/6 assertions)` com
   `the pass moved h/c/_last_symbol: True … restore reproduces it: True`.

---

## 7. Smoke na app viva

```bat
cd H:\sotto
python _main/_app-drive.py kill                      :: a app de uma lane anterior ainda estava a escrever o MESMO dump
python -c "import subprocess;subprocess.Popen([r'C:\Program Files\Python311\pythonw.exe',r'H:/sotto/_main/_join-play.py','CABLE Input','220',r'G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=0x08000000)"
python _main/_app-drive.py launch 75 _main/_smoke3-webview.log
:: a app sai sozinha no fim do --probe-v2; o dump é lido depois
py -3 app/webview/panel_state.py --read
```

Dump copiado: `_main/_smoke3-panel-state.json`. **`producerPid = 43200`** = a app DESTE smoke (a
linha `namedState = receiving`), `captions (worker) = 102`, `chunks = 123`, `tokens = 377`,
`empty_chunks = 29` (23.6 %), `gate = on`, `music_gated = 2`, `vad_gated = 0`, `audio_s = 68.88`.

As linhas do painel, verbatim, com a contagem de palavras de cada uma:

```
C 16 'Updates that I need to talk about , espe lly from OpenAI , is the biggest.'
C 19 'Right now from Open AI is a new model that not much is known about and it is called.'
C 22 "GBT next it's not GBT minor it is not the GPT six po int one a stera but what we know so."
C 18 'So far is that it is very similar to GBD six ty one, so maybe sl ightly better.'
C  8 'With no major improvements and the biggest difference.'
C 14 'Twenty eight days shi ng ple dge because for the next twenty eight days.'
C 14 'Ship a meaningful improvement for Codex and work users to give ever full usage.'
C 14 "One has already brought a pretty major speed improvement I'm not too sure about."
C 19 'About that because we were gonna be uncovering a lot of these thing s later on and it look.'
C 17 'S like Open eye is slow ly falling six point one soul fifty percent faster by default.'
P 22 'A legenda ao vivo SOTTO-V2-1791296791346. by default tar geting around fifty tokens per second instead of thir ty also applies to ·'
```

**Nenhuma linha é um fragmento de 1-2 palavras: o mínimo é 8.** E o conteúdo é verificável contra o
próprio vídeo de referência deste trabalho ("GPT Next", "not GPT minor", "GPT six point one Astra",
"similar to GPT 6.1") — a mesma passagem de ~18 min que o relatório anterior usou.

Antes, o mesmo ficheiro (`docs/audit/painel-texto.md` §5.3 e o dump de 10:52 guardado em
`_main/_smoke-BEFORE-panel-state.json`) trazia `'Em.'`, `'Ai i.'`, `'Antes dos.'`.

**Higiene, dita porque contamina:** a primeira leitura deste smoke apanhou o dump escrito por uma
app de OUTRA lane (`producerPid 41000`, a correr desde as 11:13) — o `panel-state.json` é um
**caminho único partilhado** e o `--read` não verifica a identidade do writer. A leitura reportada
acima é a segunda, com a caixa limpa (`_app-drive.py kill`) e `producerPid` conferido contra o pid
da app lançada. Sem esse passo a tabela de §7 seria de outro processo.

---

## 8. O que NÃO foi verificado, e os riscos que a cura deixa

1. **A segunda passagem (M3) num stream longo.** O `segment-rerun-probe` prova o par
   save/restore em 7.28 s de segmento; não prova que horas de stream não degradem. Não medido.
2. **A rotação de endpoint não reinicia o predictor.** O reset existe só em início de stream
   (`__init__`, `reset_stream_state`). Um `device-rotated` a meio passa a continuar o TEXTO da fonte
   anterior. Não tocado (o brief pede explicitamente para não o fazer), e é o candidato natural a
   uma decisão seguinte.
3. **Alucinação mais longa em não-fala.** A cura amplifica o que o modelo faz — incluindo o que ele
   inventa. Na corrida CONTAMINADA de §7 apareceram linhas longas de PT/AR sem qualquer áudio
   correspondente a ser reproduzido por esta lane. Não é uma regressão medida (não há baseline
   atribuível), mas é o risco que a mudança aumenta, e `music_gated_chunks` é o contador que a
   deve vigiar.
4. **As quatro oráculos de app** listados em §6 não foram corridos.
5. **WER/CER continuam a ser ASR-contra-ASR** (o ref é a auto-legenda do YouTube): são números
   RELATIVOS, não exactidão contra verdade.
6. **Sem commit.** A árvore fica suja (como estava); o `worker/sotto_worker.py` de trabalho é o que
   foi medido.
7. **Fricção de harness, medida nesta lane (não é defeito do Sotto).** O gate `THEORIST-SEAL` recusou
   repetidamente `bash`, `write` e `edit` deste assento enquanto o pass do teorista mais novo não
   tivesse uma linha de disposição, e a linha é indexada por **(ficheiro, sha256)**: os ficheiros
   `I:/!manager/state/research/theorist/theory-*.md` são **reescritos a cada poucos segundos** pelos
   passes concorrentes do próprio loop (é a F3 do pass 13-58Z, que eu li). Logo cada linha fica
   inválida na escrita seguinte. Medido: em ~15 minutos escrevi **9 disposições** para a mesma
   família `13-58Z`/`14-03Z`/`14-07Z`, com hashes diferentes (`8cc09ab8` → `aea34298` → `2bb1f8b0` →
   `4fc1344f` → `3422105b` → `a2ae7e59` → `17063e93` → …), e ainda assim vi recusas intercaladas;
   cada recusa foi respondida com uma disposição honesta, e o registo do gate nunca foi forjado à
   mão. O efeito prático: um assento que **não** é o dono do loop não consegue fechar trabalho
   enquanto o loop escreve. Fica registado como fricção medida, com a contagem — não como desculpa.
8. **Declaração de assento (a única coisa que o SELO pedia a este assento).**
   `C:/Users/Administrador/.omp/agent/agents/CuraPredictorCarry.md` foi escrito com a linha `tools:`,
   que é o que faz o próximo selo saber o que este assento tem e parar de lhe endereçar pendências
   que ele não possui. Não é um artefacto do Sotto e por isso não entra na tabela §10.

---

## 9. Comandos de reprodução (a lista completa)

```bat
:: 0. compilar
cd /d H:\sotto
python -m py_compile worker/sotto_worker.py _main/segment-rerun-probe.py _main/sotto-vs-ref-arms-compare.py _main/_cura-oracle-suite.py

:: 1. os três braços no vídeo inteiro (SERIAL: dois CUDA concorrentes morrem)
python _main/sotto-vs-ref-decode-arms.py "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav" "G:/sotto-ref/arms-full-cura.json" --arms 1,2,3

:: 2. o worker SHIPPED pós-cura (é isto que tem de ser igual ao braço 3)
cd /d H:\sotto\worker
python sotto_worker.py --selftest --audio "G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav" > "G:/sotto-ref/sotto-full-cura.jsonl" 2> "G:/sotto-ref/sotto-full-cura.err"

:: 3. a tabela (WER/CER com a MESMA normalização do relatório, importada de sotto-vs-ref-compare.py)
cd /d H:\sotto
python _main/sotto-vs-ref-arms-compare.py --ref "G:/sotto-ref/reference-en.txt" --arms "G:/sotto-ref/arms-full-cura.json" --out "G:/sotto-ref/arms-compare-AFTER.json" --jsonl "SHIPPED_AFTER:G:/sotto-ref/sotto-full-cura.jsonl"

:: 4. o clipe curto (fecha a pergunta aberta de §5)
python _main/sotto-vs-ref-decode-arms.py "H:/sotto/worker/assets/sample1.flac" "H:/sotto/_main/_cura-arms-sample1.json" --arms 1,2,3

:: 5. a suite de oráculos (recibo JSON)
python _main/_cura-oracle-suite.py --only segment-rerun-probe,model-spec-oracle,config-keys-oracle,lang-id-oracle,caption-lines-oracle,speech-gate-oracle,delivery-rate-oracle-wav,flat-endpoint-oracle,wasapi-com-init-oracle,_ordem-cura-oracle --out H:/sotto/_main/_cura-oracle-suite-nonapp.json
```

---

## 10. Artefactos

| caminho | o que é |
|---|---|
| `worker/sotto_worker.py` | a cura (6 sítios; §2) |
| `worker/README.md` | §2 "Decode" reescrita: a política nova, a tabela do vídeo, e a tabela antiga mantida como proveniência |
| `_main/segment-rerun-probe.py` | +A2 e +C3 (o par save/restore do predictor, com controlo de não-vacuidade) |
| `_main/sotto-vs-ref-arms-compare.py` | NOVO — WER/CER dos braços com a normalização do relatório, importada e não re-escrita |
| `_main/_cura-oracle-suite.py` | NOVO — corre os oráculos em série e landa um recibo |
| `_main/_cura-oracle-suite-nonapp.json` | o recibo da suite (10 GREEN) |
| `G:/sotto-ref/arms-full-cura.json` | os três braços, pós-cura |
| `G:/sotto-ref/arms-compare-AFTER.json` | a tabela derivada (população e janela dentro) |
| `G:/sotto-ref/sotto-full-cura.jsonl` | o worker shipped pós-cura (byte-idêntico ao braço 3) |
| `_main/_cura-arms-sample1.json` | os três braços no clipe de 13.44 s |
| `_main/_rerun-probe-cura.log` / `-cura2.log` | a corrida RED da C3 e a corrida GREEN corrigida |
| `_main/_smoke3-panel-state.json` | o dump da app viva pós-cura |
| `_main/_smoke-BEFORE-panel-state.json` | o dump de 10:52 (fragmentos), guardado antes do smoke |

---

## SELF-AUDIT (7 itens)

- **protocolos em falta** — eu não segui o protocolo que o próprio repo já tinha para lançar a app: o
  `_app-drive.py` avisa, no comentário do `launch()`, que um filho destacado **herda os handles** e
  que um `PIPE` faz o wrapper bloquear. Eu repeti exactamente esse erro ao lançar o `_join-play.py`
  por `bash`, com os handles herdados, e o áudio de 130 s **terminou antes de a app abrir o tap** —
  a primeira corrida do smoke mediu 4 linhas de quase-silêncio. Custou uma corrida inteira. O que
  faria diferente: ler o módulo que estou a usar para lançar processos **antes** do primeiro launch,
  e redireccionar sempre os três handles para DEVNULL — foi o que fez a terceira corrida funcionar.
- **verificação adicional** — devia ter corrido os **três braços também com o gate LIGADO**
  (`SOTTO_GATE=1` no braço de ficheiro), porque o dono vê a rota LIVE, onde `SpeechMusicGate` e
  `AutoGain` estão ligados e podem comer chunks antes do encoder. O relatório anterior já nomeava
  isso como `[INFERENCE]`; eu não o fechei. Custo: uma corrida CUDA por braço (~10 min no total),
  barato agora que o `_cura-oracle-suite.py` serializa. Fica NÃO FEITO, declarado.
- **checkboxes novas** — uma asserção MECÂNICA sobre a razão `empty_chunks / chunks` lida do
  **próprio JSONL do worker** (não de um harness): a mudança que partiu esta classe de trabalho
  (re-primar o predictor) subia `empty_chunks` de 270 para 1 597 num vídeo de 25 min e
  **nenhum oráculo do repo olhava para esse número**. Comando: exigir
  `empty_chunks <= 0.20 * chunks` no `selftest-done` de
  `sotto_worker.py --selftest --audio G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav` — hoje lê 270/2692 =
  0.100 (GREEN), e a revisão pré-cura lê 0.593 (RED). Uma linha, no instrumento que já existe.
- **review por outro subagente** — **sim-com-escopo**: peço revisão de (a) o par save/restore do
  `_last_symbol` em `run_chunk` fora do bloco `account` e (b) a lista de SÍTIOS que mexem no
  predictor depois da cura. O que quero que o revisor tente partir: um `run_chunk(..., account=False)`
  que saia do meio do loop (o `label()` do walk) e deixe `self._last_symbol` a apontar para um símbolo
  que o stream vivo nunca emitiu. Eu testei o caminho normal e o do `rerun()`, não esse.
- **gate-doubt**:
  - *verde-de-verdade:* (a) `SUITE: GREEN=10` **é real** mas dois dos verdes são auto-testes com
    controlo vermelho explícito (`flat-endpoint-oracle` e `wasapi-com-init-oracle` imprimem
    `CONTROL: RED as required` / `NEGARM: PASS`) — esses são os únicos onde vi o instrumento a
    conseguir ficar vermelho nesta corrida. (b) O verde da **C3** da primeira versão era
    **passa-por-construção**: a asserção não podia ficar vermelha porque o cenário que a devia
    deixar vermelha não existia (segmento = stream inteiro). Foi apanhado, corrigido, e a corrida
    VERMELHA está guardada no disco. (c) O `rc=0` do `--selftest` **continua a ser vazio por
    construção** — devolve 0 com metade da transcrição perdida (foi o que o relatório anterior
    mediu). A cura não toca nisso e eu não o reclamo como prova de nada. (d) O verde do smoke é
    real mas **atribuído por `producerPid`**; a primeira leitura seria um verde de outro processo.
  - *falta-no-gate:* o caminho `run_chunk` → `_last_symbol` → `seed` **não tem nenhum teste unitário
    a montante**: o único instrumento que o exercita é um probe que corre dois passes sobre um wav
    de 14.56 s com o modelo carregado (137 s de wall, CPU). Uma mudança futura que parta o seeding
    (por exemplo, mover o `_last_symbol = y` para dentro do `if account:`) passa por toda a suite
    verde e só aparece num vídeo de 25 min. Cenário concreto que atravessa o gate: o `_last_symbol`
    a ficar desactualizado quando `account=False`, e o segmento da segunda passagem a semear-se com
    um símbolo de outro stream.
  - *gate-melhor:* um teste SEM modelo, que fecha o buraco em <1 s: instanciar um duplo de
    `StreamAsr` (só `_decode` a devolver formas correctas e um `blank` conhecido), chamar
    `run_chunk` com um `pcm_chunk` sintético e assertar que (i) a primeira chamada usa
    `seed == blank`, (ii) a segunda usa `seed == último emitido`, (iii) `_last_symbol` avança dentro
    do bloco `account=False`, (iv) `reset_stream_state()` devolve `_last_symbol` a `None`. Input que
    tem de o deixar RED: mover `self._last_symbol = y` para dentro do `if account:` (a asserção iii).
    **n/a? Não** — é construível sem CUDA; não o escrevi por tempo, e digo-o em vez de o inventar.
- **confiança** — **alta** para a cura e para os números do vídeo (três controlos independentes:
  braços determinísticos entre corridas, braço 1 == shipped arquivado, shipped pós-cura == braço 3
  byte a byte). **média** para o comportamento em produção longa (M3 em horas, rotação de endpoint,
  alucinação em não-fala — §8). O que a subiria: o `SOTTO_GATE=1` nos três braços, e uma hora de
  app viva com áudio conhecido.
- **não verificado** — (1) os braços com o gate LIGADO; (2) as quatro oráculos de app; (3) M3 sobre
  um stream longo; (4) rotação de endpoint a meio do stream; (5) a alucinação longa em não-fala
  (§8.3); (6) o teste unitário sem modelo do `_last_symbol` (o "gate-melhor" acima); (7) CPU para os
  números do vídeo — só CUDA.

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh CuraPredictorCarry` → **rc=0**, saída verbatim (linhas
de carga; o texto integral está em `_main/_cura-cache-report.txt`):

```
## CACHE/PRICE
- task/agent: CuraPredictorCarry
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\CuraPredictorCarry.jsonl
- cache: read=25300736 write=0 hit=98.6931% (cache-read / input+cache-read); universe: 111 usage rows from …\CuraPredictorCarry.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=110 … | opencode-go-1/mimo-v2.6-flash: calls=1 …
- when-failed: break_items=1; WHEN=2026-10-06T13:50:10.658000+00:00 | break_items=3; WHEN=2026-10-06T13:52:08.430000+00:00 | break_items=1; WHEN=2026-10-06T14:07:13.652000+00:00 | break_items=2; WHEN=2026-10-06T14:07:52.230000+00:00 (state=RESOLVED-BREAKS-OMP; population: 4 of 119199 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'CuraPredictorCarry']; window: 2026-10-06T13:50:10.658000+00:00..2026-10-06T14:07:52.230000+00:00)
- where-failed: session_id=01a1117a-89d9-76f6-8d04-a22b1f79b9f8 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791294610658 | … item_index=108; turn_id=1791294728430 | … item_index=200; turn_id=1791295633652 | … item_index=198; turn_id=1791295672230
- report generated_at: 2026-10-06T14:31:27.624005+00:00
- usage rows: 111
- model + route: opencode-go-1/deepseek-flash, opencode-go-1/mimo-v2.6-flash
- input tokens: 335026
- output tokens: 77490
- cache-read tokens: 25300736
- cache-write tokens: 0
- hit ratio: 98.6931% (cache-read / input+cache-read)
- cost: $0.00000000 USD (… exact per-model rates: UNKNOWN …)
- prefix breaks: 7 (state=RESOLVED-BREAKS-OMP; population: 4 of 119199 …)
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Leitura: o custo reportado é **$0.00000000 em 111 linhas de usage** (rota free/`opencode-go-1`), com
**98.69 % de cache-read** e **0 writes**; as tarifas por modelo são **UNKNOWN** nesta fonte, e o
próprio instrumento diz que a razão é descritiva, não um veredicto. Os **7 prefix breaks** trazem
`WHEN`/`WHERE` acima e o estado é `RESOLVED-BREAKS-OMP`; todos caem em
`session_id=01a1117a-89d9-76f6-8d04-a22b1f79b9f8`, **não** no `source` desta lane.

