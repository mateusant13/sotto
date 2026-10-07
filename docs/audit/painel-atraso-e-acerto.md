# painel: o ATRASO e o ACERTO — medidos, nao estimados

Lane `PainelAtrasoEAcerto`, 2026-10-06 (medicao 09:11–09:14 local; agora de
referencia `09:13:01-03:00`).

**Target: a app que ESTA' A CORRER.** Nada foi relancado, morto ou tocado:
`pid 42984` (pythonw, `sotto_webview.py`) e `pid 46832` (worker) estavam os dois
a correr durante toda a medicao e continuam. Fontes, todas read-only:

| fonte | o que e' |
|---|---|
| `_main/webview-run.log` | o log que a app viva escreve (`--log`); 2090 linhas. **Appenda entre instancias**, por isso carrega tambem a sessao anterior que produziu as 13 legendas |
| `history/2026-10-06/07.md` | o que o painel comitou para o dono, com relogio de parede |
| `worker/runs/*.jsonl`, `_main/_join-run.out`, `_main/sdr_arm1_live.jsonl` | a FORMA do evento do worker (o `start`/`end`), de outras corridas do MESMO fixture |
| `worker/assets/sample1.flac` | o fixture: 219040 frames @ 16 kHz = **13.690 s** |

Instrumento: `_main/_delay-accuracy-parse.py` (read-only, nao escreve nada) →
saida integral em `_main/_delay-accuracy-parse.out`.

Duas sessoes vivem no mesmo log, e e' preciso separa-las antes de qualquer
numero:

```
linha  347  shell=webview2 ... pid=18020        <- sessao A (o --probe-v2, "o fixture")
linha  374  BRIDGE_SPAWNED worker=35672
linha  501  SHELL_EXIT rc=0 reason=panel-v2-probe
linha  502  shell=webview2 ... pid=42984        <- sessao B  **A QUE O DONO TEM**
linha  529  BRIDGE_SPAWNED worker=46832
```

---

## 0. O resultado que interessa, em uma linha

> **A app que o dono tem passou 2 h 25 min a dizer "No audio to transcribe",
> com o tap a medir `peak=0.250364` — e nao escreveu uma unica legenda no disco
> entre 07:02:08 e 09:31:04.**

Isso e' medido, nao inferido, e agora com a sessao INTEIRA (a leitura anterior,
feita a meio, dizia 508 anuncios; a sessao terminou com **580**):
**580 anuncios `BRIDGE_SILENT_BENIGN ms=15000`** = **8700 s = 2 h 25 min**,
contra o buraco medido no sistema de ficheiros `07:02:08 → 09:31:04` = **8936 s
= 2 h 29 min**. As duas fontes independentes (o heartbeat do log e o mtime da
ultima linha do historico) concordam a **97.4 %**.

Nenhum dos tres numeros abaixo e' o que domina a queixa do dono. **O que domina
e' a AUSENCIA de legenda**, e ela tem numero: 0 legendas em 2 h 25 min.

> **REVISAO 10:02 local — leia a §3.5 antes de tirar conclusoes.** A app desta
> lane foi CICLADA por outro agente (a shell 42984 morreu **sem `SHELL_EXIT`**,
> e duas instancias novas passaram a escrever no mesmo log). A instancia que
> esta' a correr AGORA **produz legenda** — 294 commits — e **97.3 % do que ela
> escreveu esta' em JAPONES**. A §3.5 tem a medicao e as populacoes novas; as
> secoes 1 a 3 ficam como o registo da instancia que esta lane mediu.

---

## 1. ATRASO

### 1a. Atraso legenda-a-legenda (audio falado → texto no painel): NAO-MENSURAVEL

```
NAO-MENSURAVEL: falta um timestamp de wall-clock em BRIDGE_CAPTION_SENT e em
CAPTION_APPLIED, e falta a posicao de audio (start/end) na MESMA linha.
```

A prova nao e' a ausencia do campo no log — e' o **emissor**, que eu li:

* `app/webview/sotto_webview.py:2133`
  `log(f'BRIDGE_CAPTION_SENT delivered=true text={json.dumps(text)}')` — **dois
  campos: `delivered` e `text`. Nao ha terceiro.**
* `app/webview/sotto_webview.py:1133`
  `log(f'CAPTION_APPLIED text=... count={len(self._shell.caption_log)}')` —
  idem.
* `app/webview/sotto_webview.py:313-320` `log()` escreve `sotto: <mensagem>`
  puro — **nao ha relogio implicito em nenhuma linha do log.**
* E a posicao de audio existe, mas e' **descartada**: o worker emite
  `{"type":"caption","text":...,"start":S,"end":E}` (medido em
  `worker/runs/gate-live-speech.jsonl`), e `on_worker_caption` (:2131-2133)
  manda `meta` ao painel e **imprime so' o texto**.

Confirmacao exaustiva por varredura de todas as tags do log vivo:
**só duas carregam relogio** — `HISTORY_APPEND` (x13) e `PANEL_V2_PROBE` (x1).

Sem relogio **E** sem posicao de audio na mesma linha, "quanto tempo depois de
falado" nao tem derivacao. Um atraso adivinhado nao e' uma resposta.

### 1b. O que E' derivavel, com a populacao e a janela declaradas

O unico relogio de parede do log e' `HISTORY_APPEND time=HH:MM:SS` — **resolucao
de 1 s**, relogio local, e e' exatamente o commit que o dono ve no historico do
painel e no ficheiro em disco.

* **POPULACAO:** os 13 commits da sessao A (fixture)
* **JANELA:** `07:01:02` .. `07:02:08` = **66 s** de relogio de parede
* **Cadencia entre commits** (n = 12 intervalos):
  **min 1.0 s · mediana 3.5 s · p90 8.0 s · max 22.0 s** (soma 66 s)
* **Buracos** (delta ≥ 2× mediana = 7 s):
  * `07:01:06 → 07:01:28` — **22 s sem nenhum commit**
  * `07:01:58 → 07:02:06` — 8 s sem nenhum commit

Isto e' a **cadencia de atualizacao do historico**, nao a latencia falado→visto.
Chamar-lhe "atraso" seria ler para dentro do numero o que ele nao mede.

Revisoes vs. commits na mesma sessao: **29 `BRIDGE_CAPTION_SENT` → 13
`CAPTION_APPLIED` → 13 `HISTORY_APPEND`**. Ou seja, o dono recebeu 29 revisoes
para 13 linhas, e nenhuma dessas 29 traz a hora a que chegou.

### 1c. O atraso do lado do ASR, com populacao DECLARADA

O `end-start` de cada evento de legenda = **quanto audio a legenda mostrada ja'
cobre**: `end` e' a posicao de audio no instante do emitir (o tap e'
tempo-real e `queue_drops=0`, logo acompanha o relogio) e `start` e' onde o
texto mostrado comeca. Isso faz dele a **staleness da cabeca da legenda** — a
parte do atraso que e' do ASR.

| fonte (runs do MESMO fixture, nao a sessao viva) | n | min | mediana | p90 | max |
|---|---|---|---|---|---|
| `worker/runs/gate-live-speech.jsonl` | 13 | 0.56 | 3.36 | 7.28 | 7.84 |
| `_main/_join-run.out` | 36 | 0.56 | 4.48 | 8.40 | 10.08 |
| `_main/sdr_arm1_live.jsonl` | 36 | 0.56 | 3.64 | 6.72 | 7.84 |
| **TODOS JUNTOS** | **85** | **0.56** | **3.92** | **7.84** | **10.08 s** |

**JANELA:** o fixture tem 13.69 s, e o `end-start` maximo e' 10.08 s — nenhum
valor excede o clipe, o que valida o campo como posicao dentro do fixture.

A latencia do ASR propriamente dita e' **≈ 0**: o worker emite a legenda quando
o audio chega a `end`, e o `rtf` da sessao do fixture e' **0.030**
(`infer_wall_s=4.84` / `audio_s=162.40`) — o worker NAO e' o gargalo de computo.
**O atraso nao esta' no modelo.**

**NAO-VERIFICADO:** o `start`/`end` da sessao viva (B) nunca chega ao log, por
isso esta tabela e' de OUTRAS corridas do mesmo fixture, nao da sessao do dono.
Se a sessao viva tivesse outro comportamento, este numero nao o apanharia.

### 1d. QUAL e' o atraso que o dono SENTE (o que ele ve)

Tres coisas, e so' uma delas e' "atraso":

1. **A ausencia.** Ele olha e le' `"No audio to transcribe"`. Isso nao e' um
   atraso de N segundos; e' **atraso infinito**, e dura 2 h 25 min (secao 0/3).
   E' a queixa dominante e agora tem numero.
2. **O congelamento.** Quando ha' legenda, o historico fica parado ate' **22 s**
   com audio a tocar (secao 1b) — e dentro desses 22 s o log carrega **um
   `BRIDGE_SILENT_BENIGN`** (linha 432): o tap tinha rodado para um device
   "flat". Ele nao ve "texto velho a atualizar"; ele ve **a mesma linha
   durante 22 s**.
3. **O texto que se re-escreve.** Cada linha nova **comeca com a anterior**:
   11 commits do fixture = **4 corridas**, 100 palavras mostradas para um clipe
   de 39 (secao 2C). Ele ve a mesma frase a crescer outra vez — que e' o
   "nao ta certo" dele, e nao e' medivel como atraso.

O atraso do ASR (1c) — mediana 3.9 s, max 10.1 s — e' o **menor** dos tres
fatores. Nao e' ele que faz a queixa.

---

## 2. ACERTO

**Referencia (39 palavras)** — `worker/assets/sample1.flac`, a MESMA string em
`docs/accuracy-int4-vs-fp16-20261006.md:84` (sherpa-onnx INT8) e
`docs/int8-route-20261006.md:158` ("Reference for the same audio"), byte-identica
na corrida FP32:

```
Going along slashy country roads and speaking to damp audiences in droughty
schoolrooms day after day for a fortnight, he'll have to put in an appearance
at some place of worship on Sunday morning and he can come to
```

**AVISO, porque muda a leitura:** ela e' **MAQUINA, nao transcript humano** — o
proprio repo o diz (accuracy doc, seccao *Ground-truth WER*). Duas palavras dela
sao suspeitas de erro do ASR que a produziu: `slashy` (o audio diz *slushy*) e
`droughty` (o audio diz *drafty*) — e o capturado ao vivo diz `slushy` e
`drafty`, ou seja, **acerta onde a referencia erra**.

**Nota de medicao que muda o instrumento:** o worker **entrou a meio** do clipe
(o clipe toca em loop e o tap comeca em fase arbitraria) — por isso o painel
comeca a mostrar o **fim** do script (`"After Day for He'll have Sunday and he
can"`). Comparar a concatenacao com a referencia como se fosse uma leitura desde
o inicio produz um WER global sem sentido. Os quatro numeros abaixo **nao
dependem da fase de entrada**.

* **POPULACAO:** as 11 linhas do fixture em `history/2026-10-06/07.md`
  (13 linhas, das quais **2 sao injectadas pelo probe**: `A legenda ao vivo
  SOTTO-V2-1791280926210.` e `Ruf.`)
* **JANELA:** `07:01:02` .. `07:01:58`

| # | metrica | valor |
|---|---|---|
| **A** | **Cobertura** (bag-of-words, sem ordem) | **21/34** palavras distintas = **61.8 %** |
| **B** | **Acerto em ORDEM** do que foi mostrado (LCS por linha / palavras da linha) | **78/100 = 78.0 %** |
| **C** | **Redundancia** (palavras mostradas / palavras do clipe) | **100/39 = 2.56×** |
| **D** | **Cortes** (token truncado na fronteira do chunk) | **3**: `coun`(de *country*), `scho`(de *schoolrooms*), `mor`(de *morning*) |

Palavras da referencia que **nao apareceram** (13 de 34 distintas): `at`,
`audiences`, `come`, `droughty`, `fortnight`, `morning`, `of`, `on`, `place`,
`put`, `slashy`, `some`, `worship`. Note-se que 5 dessas (`at`, `audiences`,
`come`, `fortnight`, `of`/`on`/`place`/`some`/`worship`) formam exatamente a
cauda do script — o tap entrou a meio e **o fim do clipe nunca foi mostrado**,
o que e' a fase de entrada, nao um erro do modelo.

**Por linha (LCS/palavras):** `5/5 · 9/9 · 3/3 · 6/6 · 9/15 · 2/2 · 6/8 · 11/13 ·
12/15 · 6/10 · 9/14`. As perdas sao sempre do mesmo tipo: o texto repete o
troco anterior (`Schoolrooms Day after` dentro de `Schoolrooms Day after He'll
an appearance and he can immediate Going a slushy coun Roads`) e corta o token
final.

**Lado do WORKER na mesma sessao** (`BRIDGE_EXIT` linha 498, `stderr_tail`):

```
audio_s=162.40  captions=18  tokens=97  frames=545  blanks=448  blank_frac=0.822
empty_chunks=46  vad_gated_chunks=86  music_gated_chunks=140  gate_kept=150
queue_drops=0   infer_wall_s=4.84
```

Dois factos que o dono sente e que isto explica:

* **`blank_frac=0.822`** — 82 % dos frames saem brancos; **97 tokens para 162 s
  de audio**, i.e. o worker decodificou ~1 passagem do clipe em ~12 que tocaram.
* **`music_gated_chunks=140` contra `gate_kept=150`** — o gate classificou como
  *musica* ~metade do que ouviu, num fixture que e' **fala pura**. O gate nao e'
  um detalhe: e' onde metade da legenda se perde.

---

## 3. CONTINUIDADE — o mapa dos buracos

### 3.1 Sessao AO VIVO (worker 46832 — a que o dono tem)

```
linhas 502..2394   revisions=0   CAPTION_APPLIED=0   'sem audio'=580
ms= distintos: [15000]     estados: {no-audio: 580}   causas: {device-rotated: 580}
peak do tap nos anuncios de 'sem audio': 0.250364 constante (n=580)
```

* **ZERO revisoes, ZERO legendas pintadas, ZERO linhas no disco** durante
  **2 h 25 min** (a sessao inteira: 580 anuncios × 15 s = 8700 s).
* Confronto com o sistema de ficheiros: `history/2026-10-06/` ficou **sem
  `08.md`**, e o `09.md` so' nasceu as `09:31:04` — nenhuma hora inteira foi
  escrita entre `07:02:08` e `09:31:04`. O buraco medido la' e'
  `07:02:08 → 09:31:04` = **8936 s = 2 h 29 min** → concordancia **97.4 %**.
* O peak **nao** e' silencio: **0.250364** contra um floor de **0.002**. E o
  proprio shell ja' sabe o que `reason=flat` significa, e escreveu-o:
  `sotto_webview.py:2907-2911` — *"the worker's word is `flat`, but it is NOT
  'below the peak floor' — measured on this box, a live idle run rotated with
  `peak=0.465216` against `floor=0.002`"*. **O tap ouve e a escada roda na
  mesma**, a cada 15 s, indefinidamente (`restarts=0`).

### 3.2 Sessao do fixture (worker 35672)

```
linhas 374..498   revisions=29   CAPTION_APPLIED=13   'sem audio'=4
ms= distintos: [15000]  causas: {device-rotated: 4}   peak=0.250702 constante
4 anuncios x 15 s = 60 s de estado 'sem audio' dentro de uma janela de 66 s
```

Ordem crua (linhas do log): os **tres primeiros** anuncios de `sem audio`
(413/416/419) vem **antes da primeira legenda** (422). O quarto (432) cai
exatamente **dentro do buraco de 22 s** entre o commit de `07:01:06` e o de
`07:01:28`. Ou seja: **o buraco de 22 s nao e' o worker a pensar — e' o tap a
ter rodado para um device "flat" e a segurar.**

### 3.3 O mapa dos buracos, em uma linha

| de | ate' | duracao | o que o log diz que aconteceu |
|---|---|---|---|
| (inicio da captura) | `07:01:02` | ≥ 45 s (3 anuncios de 15 s) | 3× `device-rotated reason=flat` antes da 1ª legenda |
| `07:01:06` | `07:01:28` | **22 s** | 1× `BRIDGE_SILENT_BENIGN` intercalado: tap rodado |
| `07:01:58` | `07:02:06` | 8 s | sem commit (a legenda injectada pelo probe chega em 07:02:06) |
| `07:02:08` | `09:31:04` | **2 h 29 min** | 580× `device-rotated reason=flat`, 0 legendas, nenhum ficheiro de hora novo |

**Um painel que "salta" e' exatamente isto, e agora tem numero.** Os buracos nao
sao distribuidos: **todos** tem a mesma causa nomeada no log —
`device-rotated reason=flat` — e todos com o tap a medir peak ~0.25.

### 3.4 O painel esta' NA TELA agora, e esta' a dizer "No audio to transcribe"

Medido na sessao B (nao inferido): o ultimo evento de visibilidade do painel no
log e' a **linha 2177** e nenhum `PANEL_HIDDEN` o segue:

```
2161 PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
2164 PANEL_HIDDEN reason=hotkey visible=false
2165 PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
2166 PANEL_HIDDEN reason=hotkey visible=false
2170 PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
2171 PANEL_HIDDEN reason=hotkey visible=false
2172 PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false
2173 PANEL_HIDDEN reason=hotkey visible=false
2177 PANEL_SHOWN reason=hotkey visible=true show=SW_SHOWNOACTIVATE focus_stolen=false   <- FIM
```

E a ultima coisa que o painel pintou (`STATUS_APPLIED` / `PLACEHOLDER_APPLIED`)
e' exatamente esta:

```
sotto: STATUS_APPLIED      text="Audio tap silent - nothing to transcribe"
sotto: PLACEHOLDER_APPLIED title="No audio to transcribe"
```

Isto e' o que o dono ve quando carrega em Alt+C: **um painel aberto, sem uma
legenda, a dizer "No audio to transcribe"** — com `peak=0.250364` no tap.

O censo de janelas apanhou-o e **nao foi esta lane**:

```
ALERTA-JANELA ts=2026-10-06T12:16:21Z chave=42984:1845310 pid=42984 hwnd=1845310
  nome=pythonw exe=C:\Program Files\Python311\pythonw.exe inicio=2026-10-06T10:04:00Z
  cmd="...pythonw.exe" "H:\sotto\app\webview\sotto_webview.py" --with-worker --log H:/sotto/_main/webview-run.log ...
```

Que **nao e' desta lane** e' medivel, nao uma promessa: todos os processos que
esta lane arrancou foram `python.exe` (subsistema de consola), nenhum
`pythonw.exe`, e nenhum criou janela — o unico `pythonw.exe` dessas duas
contagens e' o **da app do dono, pid 42984**, que ja corria desde
`10:04:00Z` antes desta lane comecar a medir. A via e' `reason=hotkey`: quem
mostrou o painel foi o Alt+C do dono, nao este agente.

---

### 3.5 REVISAO: a app foi ciclada, a instancia NOVA produz legenda — em JAPONES

Medido as 10:01–10:03 local, **depois** de a sessao desta lane ser reiniciada.
Isto e' a populacao maior de todas (294 commits contra os 13 do fixture) e
**corrige a impressao que as secoes 0–3 podem deixar**.

**(a) A app desta lane foi ciclada.** O log carrega 20 sessoes de shell; as
quatro ultimas:

```
linha  347 shell pid= 18020  caps=29  applied=13  history=13  silent=4    SHELL_EXIT=sim   <- o fixture
linha  502 shell pid= 42984  caps=0   applied=0   history=0   silent=580  SHELL_EXIT=NAO   <- A QUE ESTA LANE MEDIU
linha 2395 shell pid= 39556  caps=46  applied=37  history=37  silent=5    SHELL_EXIT=NAO
linha 2642 shell pid= 37684  caps=427 applied=293 history=294 silent=124  SHELL_EXIT=NAO   <- A APP AGORA
```

A shell 42984 tem **ZERO `SHELL_EXIT`**: foi morta, nao despedida. **Nao foi
esta lane** — nenhum `kill`/`taskkill` foi emitido aqui, e todos os processos
que eu arranquei foram `python.exe` de consola sem janela. O evento correlacionado
e' o **reinicio de sessao do harness as 12:57:42Z** (o mesmo que reiniciou este
agente), e a instancia original da app tinha `pai=40432 paiNome=(morto)` — era
um orfao. **O mecanismo nao esta' medido**: o que esta' medido e' a ausencia de
`SHELL_EXIT` e a correlacao temporal. Ticket `a ser aberto` com esta evidencia.

**(b) A instancia nova PRODUZ legenda, e DEPOIS cai no mesmo silencio.**
294 commits, `history/2026-10-06/09.md`:

* **POPULACAO: 294 commits · JANELA `09:35:41`..`09:59:34` = 1433 s (23.9 min)**
* **Cadencia commit-a-commit (n=293): min 0 s · mediana 2 s · p90 6 s · max 499 s**
* Buracos ≥ 5× mediana (10 s): **14**, e **917 s de 1433 s = 64.0 % da janela
  esta' DENTRO de um buraco**. Os maiores: `09:51:00 → 09:59:19` = **499 s
  (8.3 min) sem legenda**, `09:41:36 → 09:43:20` = 104 s, `09:48:45 → 09:50:00` = 75 s.
* `BRIDGE_SILENT_BENIGN` nesta instancia: **124**, `peak` do tap **0.0** e
  **0.142383**, `restarts` = **1 e 3**. O ultimo `BRIDGE_CAPTION_SENT` esta' no
  indice 1726 de 1781 e o primeiro "sem audio" depois dele no 1731.
* O que o painel pinta no fim do log: `"Audio tap silent - nothing to transcribe"`
  / `"No audio to transcribe"` — **identico ao estado das secoes 0–3**.

**A mediana de 2 s e' a outra face do mesmo problema**: quando a legenda sai, sai
em estouro (min 0 s = varios commits no mesmo segundo, p90 6 s); e quando nao
sai, nao sai por 8 minutos. **O painel nao tem cadencia — tem rajadas e buracos.**

**(c) O ACHADO QUE MANDA: 97.3 % do que a app escreveu esta' em JAPONES.**

```
POPULACAO: 330 linhas em history/2026-10-06/09.md
JANELA:    09:31:04 .. 09:59:34
  com kana/kanji (japones): 321  = 97.3 %
  so' ASCII (latim):          9  =  2.7 %
  ultima linha japonesa: 09:51:00     primeira linha latina: 09:59:19
```

a fronteira, verbatim:

```
09:50:49  お前に.
09:50:52  お前.
09:50:53  納得する.
09:51:00  未だ村は.      <-- ultima em japones
09:59:19  And by September Partner reportedly.   <-- volta a latino depois do buraco de 499 s
09:59:19  Mail and Partner reportedly ga.
09:59:23  Two point five.
09:59:24  Then.
09:59:25  Then on.
```

amostra do inicio: `あとございます.` `電話取ら.` `大.` `緊急の.` `実.` `彼女の誕.`
`一周年の.` `お前も帰.` `まだ仕.` `俺一人.` `一人にす.` `ありがと.`

**Isto e' `"e ainda ta uma merda"` com data e com percentagem.** Nao e' um
atraso nem um vazio: e' **texto fluente no idioma ERRADO**, 20 minutos seguidos.
O `lang_id` do worker e' `"auto"` (`worker/config.json`), que resolve para o
auto-slot 101 do modelo — e o **proprio repo ja' mediu o modo de falha irmao**
deste campo (`AGENTS.md`, tabela de desvios: `"os"` → `pt-BR` (12) colapsava 94
tokens para 10; o literal `0` fazia o mesmo dano ao portugues). Aqui o
`auto` **escolheu japones**.

**ACERTO desta sessao: NAO-MENSURAVEL** — e a prova de que nao e' um numero que
me falta, e' o audio que eu nao tenho: das 34 palavras distintas da referencia
do fixture, **apenas 2 aparecem** nos 330 commits (5.9 %), e **0 linhas** das
330 partilham 2 ou mais palavras com ela. Ou seja: **o que estava a tocar nesta
sessao nao era o fixture**, e sem o script do que tocava nao existe
denominador. Reportar "5.9 % de cobertura" como nota do modelo seria um
instrumento avariado — a comparacao seria entre duas coisas diferentes.

**A verificacao que isto acrescenta a`§2`**: a instancia nova **reproduz** o
estado `no-audio` (124 anuncios, peak 0.142383), como a instancia antiga
reproduzia (580 anuncios, peak 0.250364) — **duas instancias independentes, o
mesmo desfecho**. E acrescenta um defeito que a instancia antiga nao tinha como
mostrar, porque nao produziu uma unica legenda: **quando ela consegue ouvir,
transcreve noutro idioma**.

---

## 4. NAO-VERIFICADO (explicito)

* **O atraso legenda-a-legenda da sessao viva.** Nao medido, e nao por falta de
  vontade: falta o campo (1a). Medir isto exige **1 linha de log a mais** —
  ver §5.
* **O atraso real de uma legenda que aparece.** A secao 1b mede a cadencia de
  commit; a 1c mede a staleness da cabeca num fixture, de outras corridas. O
  numero "falado → visto" **desta** sessao nao existe.
* **O `start`/`end` da sessao viva** (B). Idem.
* **O WORKER_STATS da sessao viva.** Ainda nao houve `BRIDGE_EXIT` em B, logo
  nao ha' `blank_frac` / `music_gated_chunks` / `rtf` para ela — a secao 2 usa
  os da sessao A.
* **A causa do `reason=flat` com peak=0.25.** Medido o SINTOMA (o peak e' real,
  a escada roda), nao a regra que decide "flat" no worker. Ler
  `sotto_worker.py:2200-2310` inteiro e' outra lane; aqui ficou o que o log
  prova.
* **A fase exata em que o tap entrou no clipe.** Constatada pelo texto (comeca
  no fim do script), nao cronometrada.
* **Qualquer juizo estetico.** Nao ha' nenhum neste relatorio, por desenho: mede-se
  e o dono julga.

Acrescentados pela §3.5 (a instancia que corre agora):

* **O mecanismo da morte da shell 42984.** Medido: `SHELL_EXIT` ausente, e a
  correlacao com o reinicio de sessao das 12:57:42Z. NAO medido: se a morte veio
  do job object do harness, de outro agente, ou de outra coisa. A afirmacao que
  eu sustento e' so' esta: **nao foi este assento** (nenhum kill emitido aqui) e
  a shell nao se despediu.
* **Que audio estava a tocar na sessao das 09:3x.** Nao sei, e o proprio
  resultado prova que nao era o fixture (2 de 34 palavras-cobertura). Sem o
  script desse audio, o ACERTO dessa sessao e' `NAO-MENSURAVEL`.
* **Porque o `lang_id: "auto"` escolheu japones.** Medido o sintoma (97.3 % de
  kana/kanji, fronteira as 09:51:00). A decisao do auto-slot do modelo nao foi
  instrumentada nesta lane.
* **O `reconhecimento`/`tokens`/`lang` do WORKER_STATS da sessao nova.** Ainda
  nao houve `BRIDGE_EXIT` para ela.

---

## 5. O detalhe que faz o proximo relatorio ser diferente

Uma linha em `on_worker_caption` (sotto_webview.py:2131-2133) resolve a maior
parte do que ficou NAO-VERIFICADO acima — e nao custa instrumento novo, porque
os dados **ja' passam por ali**. Provado, nao assumido: o parque de linhas do
worker em `sotto_webview.py:2790-2799` faz

```python
meta = {k: v for k, v in message.items() if k not in ('type', 'text')}
...
self.on_caption(str(text), meta)          # :2801
```

e o `message` do worker e' `{"type":"caption","text":...,"model":...,`
`"start":S,"end":E}` (medido em `worker/runs/gate-live-speech.jsonl`). Logo
`meta.start` e `meta.end` **estao na mao** de `on_worker_caption` e sao
descartados pela linha de log:

```python
def on_worker_caption(self, text, meta):
    self.emit('caption', {'text': text, 'meta': meta})
    log(f'BRIDGE_CAPTION_SENT delivered=true text={json.dumps(text)}')
    # + o que falta, e ja' esta' em `meta`:
    #   t=<monotonic> start=<meta.start> end=<meta.end>
```

Com `meta.start`/`meta.end` na linha, o atraso falado→visto vira aritmetica.
Nao foi feito aqui **de proposito**: isso edita o ficheiro da app que estao a
correr, e o brief desta lane proibe tocar.

---

## 6. Artefactos desta lane

| ficheiro | o que e' |
|---|---|
| `docs/audit/painel-atraso-e-acerto.md` | este relatorio |
| `_main/_delay-accuracy-parse.py` | o instrumento (read-only; nao escreve nada) |
| `_main/_delay-accuracy-parse.out` | a saida integral, de onde saem todos os numeros acima |
| `_main/_delay-accuracy-parse-now.py` | o instrumento da **segunda populacao** (a instancia que corre AGORA, §3.5) |
| `_main/_delay-accuracy-parse-now.out` | a saida dessa segunda medicao |

Nenhum ficheiro sob `worker/` ou `app/` foi tocado. Nenhum processo foi
relancado, morto ou sinalizado. O dono nao viu janela nenhuma aparecer: nao foi
aberta nenhuma.

---

## SELF-AUDIT

* **protocolos em falta** — Faltou-me `read-before-concluding` no primeiro
  numero que produzi: ia escrever "o painel tem atraso de X" a partir de
  `HISTORY_APPEND time=`, tratando a cadencia de commit como se fosse latencia.
  So' depois de ler `sotto_webview.py:2133` e ver que a linha **nao tem terceiro
  campo** e' que virou `NAO-MENSURAVEL` + cadencia rotulada. O que faria
  diferente: **abrir o emissor da linha ANTES de calcular o que a linha mede** —
  uma leitura de 20 linhas teria poupado uma secao inteira reescrita.
* **verificacao adicional** — Barata e nao corre: rodar `--probe-v2` **agora**,
  na build atual, e ver se a sessao AO VIVO tambem produz as 13 legendas — isso
  provaria que o `PANEL_V2_GATE=GREEN` do log e' da build que o dono tem e nao de
  uma anterior. **Custo: exige relancar a app.** Nao o fiz porque o brief proibe
  tocar, e a proibicao vale mais que a duvida. Registada, nao resolvida.
* **checkboxes novas** — Um passo NOVO e MECANICO para esta classe (medir
  latencia de painel a partir de log):
  `python -c "import re,sys; L=[l for l in open(sys.argv[1],encoding='utf-8') if 'CAPTION_SENT' in l or 'CAPTION_APPLIED' in l]; bad=[l for l in L if not re.search(r'\bt=\d',l)]; sys.exit(1 if bad else 0)" _main/webview-run.log`
  — **RED hoje** (42 de 42 linhas de legenda em `webview-run.log` sem relogio;
  29 `BRIDGE_CAPTION_SENT` + 13 `CAPTION_APPLIED`). **Corrido agora, nao
  afirmado:** `python -c "..." _main/webview-run.log` → `total 42 sem relogio 42`,
  `exit=1`. O input que tem de o deixar RED e' precisamente este log; ele so'
  fica verde quando o §5 for feito.
* **review por outro subagente** — **sim-com-escopo**: aceito, com escopo
  *"o numerador e o denominador de cada metrica da secao 2"* (a conta
  LCS-por-linha e a lista de truncamentos sao as duas que mais facilmente
  passariam um erro de instrumento, e a minha confianca nelas e' a mais baixa
  de todo o relatorio).
* **gate-doubt**:
  * **verde-de-verdade:** o unico "verde" que este trabalho consome e' o
    `PANEL_V2_GATE=GREEN` da linha 496 — e ele **e' de OUTRA sessao** (shell
    18020, worker 35672), nao da que o dono tem. Nao o tratei como prova da app
    viva por isso. O que EU corri (`_main/_delay-accuracy-parse.py`) nao e' um
    gate: e' um parser, e a sua saida foi conferida a mao contra as linhas cruas
    do log (linha do tempo da §3.2) — o numero de `BRIDGE_SILENT_BENIGN` (580,
    lido a meio da sessao como 508) bate com a contagem independente do buraco
    no historico a 97.4 %.
  * **falta-no-gate:** o `PANEL_V2_GATE` **nao verifica que a app que responde
    ao dono esta' a produzir legenda** — so' verifica que o painel pinta o que
    lhe injectam. Um cenario futuro que atravessa esse buraco: uma lane faz
    `--probe-v2`, tira `GREEN`, e a app que fica a correr ao lado esta' em
    `no-audio` ha' 2 h. **Foi exatamente o que aconteceu aqui.**
  * **gate-melhor:** um check MECANICO que fecha o buraco — exigir que a ultima
    linha do historico em disco tenha menos de N minutos:
    `python -c "import os,glob,sys; f=sorted(glob.glob('history/*/*.md')); age=__import__('time').time()-os.stat(f[-1]).st_mtime; print(f[-1],round(age)); sys.exit(0 if age<300 else 1)"`
    Input que o tem de deixar RED: o estado de AGORA (`history/.../07.md`,
    ~7853 s). Um `PANEL_V2_GATE=GREEN` com isto RED significa "o painel pinta e
    nao esta' a ouvir", que e' a frase que faltava ao gate.
* **confianca** — **alta** nos numeros da §3 (duas fontes independentes, 97.8 %
  de concordancia) e na §1b (relogio unico, populacao e janela explicitas);
  **media** na §2 (a referencia e' MAQUINA e tem ela propria dois erros
  conhecidos; a metrica B depende do meu LCS por linha) e na §1c (populacao e'
  de outras corridas, nao da sessao viva). O que subiria a confianca: a §5
  aplicada, ou um transcript humano de `sample1.flac` — nenhum dos dois existe
  no repo.
* **nao verificado** — ver a secao 4 deste relatorio, integralmente. Os itens
  que a §3.5 acrescentou e que pesam mais: o **mecanismo** da morte da shell
  42984 (medido so' que nao houve `SHELL_EXIT` e que nao foi por acao deste
  assento), o **audio de origem** da sessao em que saiu japones (logo, o ACERTO
  dessa sessao e' `NAO-MENSURAVEL`), e a **razao** pela qual `lang_id: "auto"`
  escolheu japones.

---

## 7. ESTADO DEPOIS DESTA LANE (medido as 17:42Z, com a distincao dado-vs-codigo)

Esta seccao existe porque **os dois defeitos que esta lane abriu continuam
abertos**, e o mais perigoso seria confundir "a linha mudou" com "o defeito
acabou". Medido eu mesmo, nao lido do painel:

### 7.1 `theorist-delta-guard` e `theorist-always-on` passaram a EM DIA — pelo DADO, nao pelo CODIGO

| | antes (o que eu medi) | agora (o que eu medi) |
|---|---|---|
| `theorist-delta-guard` artefacto | **ausente** | existe, 4244 B, 37 linhas, mtime `14:39:02`, ultima linha `06/10/2026 14:39:01 RAN … rc=0` |
| `theorist-delta-guard` registo | `tolerancia: 8640`, `estado_declarado: "DESLIGADO"`, `medido_em 2026-09-30T03:50` | `tolerancia: 6`, `estado_declarado` **removido**, `medido_em 2026-10-06T13:47` |
| `theorist-always-on` produto | glob `theory-*.md` mais recente com 45.87 h | 1048 ficheiros, mais recente com **0.00 h** |
| **o CODIGO que causava o defeito** | `hooks/live/governadores-externos.ts` | **INALTERADO** — mtime `2026-10-03 11:13:08`, e a ordem continua `if (mtime === null)` na **linha 1897** antes de `if (g.estado_declarado === "DESLIGADO")` na **linha 2001** |

**Leitura, com o vocabulario que a casa exige:** o SINTOMA foi removido; a
**razao** nao. O ramo continua ordenado de forma que um governador que o registo
declare `DESLIGADO` **cai em `VERMELHO-SEM-SINAL` sempre que o artefacto
declarado faltar** — so' nao cai hoje porque alguem fez o artefacto existir e
tirou o `estado_declarado` do registo. **O proximo governador DESLIGADO sem
ficheiro de log reproduz o defeito.** Ticket `df9f26d05833f4fc184e04a9`
**continua ABERTO** por isso, e nao o fecho: fechar aqui seria exactamente o
modo-de-passar que o dono reprovou.

### 7.2 A legenda em japones: a JANELA fechou, a CAUSA nao

```
09.md   330 linhas   321 japonesas (97.3%)   09:31:04..09:59:34
10.md    54 linhas     0 japonesas ( 0.0%)   10:02:12..10:59:26
11.md    49 linhas     0 japonesas ( 0.0%)   11:00:02..11:26:35
```

e o campo que decide o idioma **nao mudou**:

```
worker/config.json -> model.lang_id = "auto"     (o mesmo valor da janela japonesa)
```

Nenhum commit no repo desde `09:30` (`git log --oneline --since='2026-10-06
09:30'` → vazio), e o `_comment_lang_id` ainda descreve o `'auto'` como "the
only one of the three that is good on BOTH". **Nao houve cura: houve outro
audio.** O painel volta a mostrar japones no dia em que o auto-slot do modelo
escolher japones outra vez. Ticket `913a5e991c50bc78d9a8007a` **continua
ABERTO**.

**O que isto custou e o que fica:** as duas pendencias que o selo me entregou
passaram a EM DIA com sinais que antes nao existiam (as linhas `RAN … rc=0` do
delta-guard e as `theory-*.md` novas do always-on), e isso satisfaz o
`FECHO EXIGIDO` — mas **medido por mim, nao aceito da linha do painel**. E os
dois defeitos que esta lane abriu ficam abertos com a prova de que o codigo e o
`lang_id` nao se mexeram.

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh PainelAtrasoEAcerto` → rc=0, saida
verbatim (o texto abre com o proprio cabecalho `## CACHE/PRICE` e e' por isso
colado como veio):

```
## CACHE/PRICE
- task/agent: PainelAtrasoEAcerto
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\PainelAtrasoEAcerto.jsonl
- cache: read=14364416 write=0 hit=98.2271% (cache-read / input+cache-read); universe: 79 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\PainelAtrasoEAcerto.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=72 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000
- when-failed: break_items=1; WHEN=2026-10-06T12:07:06.722000+00:00 | break_items=1; WHEN=2026-10-06T12:07:07.253000+00:00 | break_items=1; WHEN=2026-10-06T12:07:07.801000+00:00 | break_items=3; WHEN=2026-10-06T12:07:08.422000+00:00 | break_items=3; WHEN=2026-10-06T12:09:00.188000+00:00 | break_items=3; WHEN=2026-10-06T12:14:06.146000+00:00 (state=RESOLVED-BREAKS-OMP; population: 6 of 117292 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'PainelAtrasoEAcerto']; window: 2026-10-06T12:07:06.722000+00:00..2026-10-06T12:14:06.146000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791288426722 | session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791288427253 | session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791288427801 | session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791288428422 | session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=deepseek-flash model=deepseek-flash item_index=89; turn_id=1791288540188 | session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=deepseek-flash model=deepseek-flash item_index=199; turn_id=1791288846146
- report generated_at: 2026-10-06T12:17:25.566138+00:00
- usage rows: 79
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 259267
- output tokens: 85221
- cache-read tokens: 14364416
- cache-write tokens: 0
- hit ratio: 98.2271% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 12 (state=RESOLVED-BREAKS-OMP; population: 6 of 117292 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'PainelAtrasoEAcerto']; window: 2026-10-06T12:07:06.722000+00:00..2026-10-06T12:14:06.146000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=1; WHEN=2026-10-06T12:07:06.722000+00:00; WHERE session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791288426722
  - break_items=1; WHEN=2026-10-06T12:07:07.253000+00:00; WHERE session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791288427253
  - break_items=1; WHEN=2026-10-06T12:07:07.801000+00:00; WHERE session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791288427801
  - break_items=3; WHEN=2026-10-06T12:07:08.422000+00:00; WHERE session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791288428422
  - break_items=3; WHEN=2026-10-06T12:09:00.188000+00:00; WHERE session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=deepseek-flash model=deepseek-flash item_index=89; turn_id=1791288540188
  - break_items=3; WHEN=2026-10-06T12:14:06.146000+00:00; WHERE session_id=01a1111c-1ea6-72d7-b821-461e6fb45b96 provider=deepseek-flash model=deepseek-flash item_index=199; turn_id=1791288846146
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Nota de leitura: **seis prefix breaks, todos com `item_index` 0, 89 e 199** —
`item_index=0` e' a PROPRIA mensagem de sistema (o prefixo mais estavel que
existe), e ela parte quando o provedor troca
(`cline-pass` → `space-bunny-free` → `ling-3.1-flash-free` → `deepseek-flash`),
ou seja o break e' de ROTA, nao de conteudo. Os `break_items` de `deepseek-flash`
a `item_index=89/199` sao o mesmo modelo com o prefixo a crescer. Fonte integral
guardada em `I:/Temp/_cache-pa.txt`.
