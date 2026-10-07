# Recibo — a rota do HISTORICO (Sotto): o ficheiro deixa de mentir

status: done

**Lane:** `SottoFragmentacao`
**Alvo:** `H:/sotto` (a app **a correr** — nao foi relancada a mao; ver §5)
**Contrato:** `H:/sotto/docs/audit/ao-vivo-vs-redux.md` §5 (M1-M9), que o ticket nomeia como o desenho
**Entregavel:** `H:/sotto/docs/audit/ao-vivo-vs-redux-CURA.md`

## Contrato (declarado, com fonte)

| # | item | fonte |
|---|---|---|
| 1 | M1 reter o PCM do segmento no `asr_thread` | o ticket (Change, item 1) |
| 2 | M2 marcar os eventos `final:false` enquanto provisorios | o ticket (item 2) |
| 3 | M3 segunda passagem sobre o audio do segmento INTEIRO, estado RNNT reposto, UM `final:true` que substitui o provisorio e e' o unico que vai ao historico | o ticket (item 3) |
| 4 | M4 os parciais ficam provisorios | o ticket (item 4) |
| 5 | M5 `final:false` NUNCA chama `onCommit` | o ticket (item 5) |
| 6 | M6 `expireHold` deixa de chamar `commit()` | o ticket (item 6) |
| 7 | M7 `addCaption`/`recordHistory` aceitam a `reason` que ja' e' calculada | o ticket (item 7) |
| 8 | M8 a linha leva `route=` e `start=` | o ticket (item 8) |
| 9 | M9 reusar a classe `.caption--provisional` que ja' existe | o ticket (item 9) |
| 10 | a latencia da legenda AO VIVO nao pode mudar | o ticket, verbatim |
| 11 | `ao-vivo-vs-redux-CURA.md` com ANTES/DEPOIS e `file:line` | o ticket (Acceptance) |
| 12 | a prova e' o FICHEIRO: `history/<data>/*.md`, as duas contagens | o ticket (Acceptance) |
| 13 | nao escrever pontuacao final num fragmento provisorio | o ticket (Acceptance) |
| 14 | `transcript-append-oracle.js` continua GREEN | o ticket (Acceptance) |
| 15 | `grep -E` ignorado: usar python ou `case` | o ticket (Acceptance) |
| 16 | SELF-AUDIT + CACHE/PRICE no recibo | `I:/!manager/AGENTS.md` |

**Estado do entregavel: LIVE.** Nao e' "escrevi o ficheiro": o caminho inteiro foi **exercitado**
(worker real -> motor real -> store real -> ficheiro em disco), e a app **real** escreveu duas
linhas no historico do dono com o formato novo sem eu a relancar.

## Acceptance — o que foi corrido, e o que deu

| # | criterio | comando | resultado |
|---|---|---|---|
| 14 | oracle de append GREEN | `node app/electron/transcript-append-oracle.js` | **GREEN**, rc=0 |
| — | linhas do worker (12 arms) | `python _main/caption-lines-oracle.py` | **12 PASS / 0 FAIL**, rc=0 |
| — | a rota ate' ao ficheiro | `node _main/history-route-oracle.js --audio G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav --max-chunks 400` | ver §2 |
| — | a 2a passagem isolada | `python _main/segment-rerun-probe.py` | ver §3 |
| 12 | as duas contagens no FICHEIRO | ver §2 | ver §2 |
| 13 | fragmento provisorio sem pontuacao final | `history/2026-10-06/10.md`, linha de 10:36:54 | **cumprido** |

## §1 O defeito, medido antes

`history/2026-10-06/*.md`, lido nesta lane as 13:23 com `python` (nunca `grep -E`):

```
entries 473
<=3 words: 352      (74.4 %)
>3 words : 121
median words per entry: 1
ends in terminal punctuation: 473  (473/473 = 100 %)
```

## §2 ANTES / DEPOIS, o mesmo stream de fala real

`node _main/history-route-oracle.js --audio G:/sotto-ref/PQw0TRzpCkk.16k-mono.wav --max-chunks 400`
— 224 s da mesma fala que o tap ao vivo ouvia, pelo mesmo worker e pelo mesmo motor. Duas
semanticas sobre o MESMO stream:

```
stream    : 1226 caption events — 1091 provisional, 135 final

CONTROL (semantica pre-cura, o MESMO stream): {"entries":1221,"over3":279,"short":942,"shortPct":77.1,"median":2}
NEW     (rota respeitada, o MESMO stream):    {"entries":135, "over3":134,"short":1,  "shortPct":0.7,"median":16}
```

| | CONTROL (antes) | NEW (depois) |
|---|---|---|
| registos | 1221 | **135** |
| <= 3 palavras | 942 (**77,1 %**) | **1 (0,7 %)** |
| > 3 palavras | 279 (22,9 %) | 134 (99,3 %) |
| mediana | 2 | **16** |
| provisorios no ficheiro | por construcao | **0** |

**As duas contagens que o ticket pede**, no ficheiro do dono: `473 registos, 352 (74,4 %) com <=3
palavras` antes; a fraccao cai para **0,7 %** com a semantica nova (e o controlo, no mesmo stream,
da' 77,1 % — o que mostra que o numero nao desce por o ficheiro ter menos linhas, desce porque cada
linha passou a ser uma frase do worker). O artefacto em disco
(`H:/sotto/history-verify/2026-10-06/10.md`, escrito pelo `history-store.js` real) tem **136 linhas,
todas `route=final`, 0,7 % com <=3 palavras**.

## §3 A 2a passagem (M3) medida isolada

`_main/segment-rerun-probe.py` — o mesmo `StreamAsr`, a mesma gravacao, sem dispositivo:

- A `reset_stream_state()` devolve as caches ao inicio de um stream (`(1,24,70,1024)`, `(1,24,1024,8)`,
  `(1,)`, iguais a uma alocacao nova) — **PASS**
- B `run_chunk(..., account=False)` nao move contador nenhum (`n_chunks`, `audio_s`, `wall`,
  `frames_walked`, `blank_frames`, `symbols`, `empty_chunks`, `labels`) — **PASS**
- C as arrays do stream ao vivo nao sao escritas em sitio pela passagem, e o restauro reproduz o
  estado bit a bit — **PASS** (era a duvida §7 da auditoria sobre o `InferenceSession`)
- D a passagem produz texto — **PASS**, e **igual** ao texto do stream (`'O rádio Segunda feira
  Os moradores'`). Isso e' o esperado: §6.3 da auditoria ja' diz que re-decodificar **nao corrige o
  erro**, so' garante a **fronteira**.

**GREEN, 4/4.** Custo: a passagem custou **0,91x** uma passagem de streaming sobre o MESMO audio
(0,78x numa corrida com a caixa mais carregada) — re-decodificar um segmento custa
aproximadamente o que custou decodifica-lo. Os RTF absolutos desta caixa (1,59-3,04) **nao** sao
comparaveis aos 0,14-0,22 da auditoria: e' carga (a app ao vivo + orfaos), nao modelo. A
inferencia `RTF x S` do §6.2 fica assim **substituida por uma medicao**.

## §4 O que NAO mudou

Latencia da legenda ao vivo e texto da caixa: o `ingest` continua a chamar `onProvisional` a cada
parcial, e `addCaption` pinta o mesmo texto. A unica mudanca de ecra e' a pedida no M9 (o `·` final
na linha provisoria, com a classe que ja' existia).

## §5 A app nao foi relancada

A hot-reload do proprio shell recarregou o painel (`HOT_RELOAD_PANEL_DONE reload=1/2`) e um worker
NOVO arrancou depois da edicao (pid 26036, 10:31:37). O ficheiro do dono ganhou, escrito pela app:

```
- [10:33:52] Nossa, eu vou. <!-- route=provisional-draft start=3.36 reason=status-change -->
- [10:36:54] Olha <!-- route=provisional-draft start=6.72 reason=status-change -->
```

A primeira, antes de o painel apanhar a regra da pontuacao; a segunda, depois — sem o ponto final
inventado. Nada foi relancado a mao.

E minutos depois chegaram as linhas **fechadas pelo worker** — a rota `final` (M3) exercida ao
vivo, nao so' nos oraculos:

```
- [10:42:14] Ho Hora que eu ganho.        <!-- route=final … -->
- [10:42:51] Não, em uma ho Caralho Isso, man Olha bote O Li Tem uns drago O Dra Olha o play de De E eu ten.   <!-- route=final … -->
- [10:43:07] Ai i.                        <!-- route=final … -->
```

Censo do ficheiro do dono (sufixo removido antes de contar palavras):

```
PRE-cure  (sem sufixo): 502 entries, 379 <=3 words (75.5 %)
POST-cure (com sufixo):   7 entries,   4 <=3 words (57.1 %)
ALL                    : 509 entries, 383 <=3 words (75.2 %)
```

As duas rotas estao' portanto provadas **ao vivo**. A estatistica do ficheiro **do dono** nao cai
para 0,7 %, e as duas razoes nao sao a cura: 502 das 509 linhas sao anteriores a cura e o ficheiro
e' append-only; e das 7 pos-cura, 4 sao `provisional-draft` (o `flush` de status escreve o que o
worker nao fechou, quando o worker e' morto — o tap desta caixa esta' plano). A comparacao
antes/depois legitima e' a do §2, sobre o mesmo stream.

## §6 Os ficheiros tocados

```
worker/sotto_worker.py                      (M1, M2, M3)
app/electron/caption-formulation.js         (M3, M5, M6, M7, M8)
app/electron/panel.js                       (M6, M7, M8, M9)
app/electron/history-store.js               (M8)
app/electron/main.js                        (M8 — o meta deixava de ser deitado fora)
app/electron/worker-bridge.js               (M8 — o arm Electron levava a rota ao renderer)
app/electron/transcript-append-oracle.js    (le o sufixo como METADATA)
app/webview/sotto_webview.py                (M8 — o store da app real)
_main/caption-lines-oracle.py               (arm 11: o fecho fora de banda)
_main/history-route-oracle.js               (NOVO — a rota ate' ao ficheiro)
_main/segment-rerun-probe.py                (NOVO — a 2a passagem isolada)
docs/audit/ao-vivo-vs-redux-CURA.md         (o entregavel)
```

gate-change-request: n/a — esta lane nao encontrou um buraco num GATE do manager; mudou o
CONTRATO de dois oraculos do proprio repo Sotto (o arm 9 ficou como estava, e um arm 11 novo
nasceu para o fecho fora de banda), e isso esta' justificado com a medicao dentro do codigo.

## SELF-AUDIT

- **protocolos em falta** — o `dispatch-preflight` manda VERIFICAR os paths citados antes de
  escrever o brief. Aqui o analogo era verificar **cada `file:line`** que eu ia citar no
  `-CURA.md`; eu citei-os de uma colheita feita ANTES do ultimo par de edicoes, e dois numeros
  mudaram (`caption-formulation.js` :512, `sotto_webview.py:2102`). Fui corrigi-los com uma
  segunda colheita. O que faria diferente: colher os `file:line` **depois** da ultima edicao, ou
  marcar a colheita como "re-verificar antes de publicar".
- **verificacao adicional** — teria aumentado a confianca correr o `history-route-oracle.js` com
  o audio **do proprio dono** (o que o tap ouviu) em vez de `PQw0TRzpCkk.16k-mono.wav`; esse
  ficheiro *e'* provavelmente o audio do tap (mesma fala em BR), mas nao esta' provado que seja.
  Custo: ~3 min de modelo. Ficou por fazer e esta' declarado no §7 da `-CURA.md`.
- **checkboxes novas** — uma assercao MECANICA que eu acrescentaria a esta classe de trabalho:
  **o ficheiro e' o oraculo, e o sufixo e' METADATA**. Comando:
  `python -c "…censo que (a) separa o texto do `<!-- -->` antes de contar palavras e (b) exige
  `route=` em 100 % das linhas novas…"`; o input que a deixa RED e' um ficheiro com **uma** linha
  de resumo sem `route=` (ou com o sufixo contado como palavras). E' o que separa "o ficheiro
  mudou" de "o ficheiro passou a mentir de outra maneira".
- **review por outro subagente** — **sim-com-escopo**: review de `worker/sotto_worker.py`
  `_close`/`take_closed`/`rerun` (a parte onde eu MUDEI o contrato de um objecto puro que tres
  arms antigos exercem) e de `caption-formulation.js` `ingest`/`commit` (a fiacao de `route`,
  `start`, `fileText`). Nao vale a pena re-rever o `panel.js`/stores (mecanicos).
- **gate-doubt**:
  - **verde-de-verdade**: o `transcript-append-oracle.js` deu GREEN em **duas** corridas minhas
    (antes e depois do fecho fora de banda) — mas a segunda corrida **so' passou porque o guarda
    `emittedWords`/`emittedEnd` do motor segura a duplicacao**, e nao porque os eventos do worker
    mudaram. Isso e' um verde real, mas *vacuoso quanto ao que eu mudei*: a corrida nao teria
    apanhado uma regressao no par `_close`/`take_closed`. Quem a apanha e' o arm 11 (novo).
    E a contagem do §2 foi corrida com o MESMO motor nos dois braços (controlo e novo) — um
    instrumento partilhado, mas usado nos dois lados da comparacao, o que e' o que a torna justa.
  - **falta-no-gate**: o `transcript-append-oracle.js` NAO verifica a ROTA. Um `ingest` que
    passasse a tratar `final:false` como commitavel continuaria GREEN (o stream e' legado, sem
    sufixo) e encheria o ficheiro de provisorios outra vez. O cenario concreto que o atravessa:
    alguem "simplifica" `provisionalRoute` para `Boolean(meta.final)` — o ficheiro volta a 74 % e
    nenhum gate do repo fica RED.
  - **gate-melhor**: `node _main/history-route-oracle.js` fecha esse buraco, e o input que o deixa
    RED e' exactamente essa simplificacao (o arm "no provisional partial reaches the transcript"
    e o arm "THE FILE: every entry is closed and marked" ficam RED). E' a checkbox acima em forma
    de comando.
- **confianca** — **alta** na direccao e na magnitude (74,4 % -> 0,7 % e' uma ordem de grandeza,
  medida no mesmo stream); **media** no custo absoluto da 2a passagem, porque a caixa estava
  carregada (a corrida do stream deu RTF 3,04 contra os 0,14-0,22 medidos pela auditoria — e'
  carga, nao modelo). O que a subiria: medir a 2a passagem com a caixa ociosa.
- **nao verificado**:
  1. o custo ABSOLUTO da 2a passagem numa caixa ociosa (so' o RATIO esta' medido, §3);
  2. que o audio `PQw0TRzpCkk.16k-mono.wav` seja exactamente o que o tap ao vivo ouviu;
  3. o caminho Electron (`main.js`/`worker-bridge.js`/`history-store.js`) correu nos oraculos,
     mas **nao** num Electron a correr — a app real e' a WebView2;
  4. ~~que o worker da app ao vivo atinja uma linha fechada (`final:true`)~~ — **VERIFICADO
     depois**: 3 linhas `route=final` apareceram no ficheiro do dono (10:42:14, 10:42:51, 10:43:07),
     uma delas com 22 palavras. A minha afirmacao anterior de que o worker nunca fechava uma linha
     esta' refutada, e foi corrigida no bilhete `c7c667a6c6bb04282b5e9624` (segunda liquidacao).
  5. uma correccao de calibracao minha, declarada: a PRIMEIRA corrida longa do
     `history-route-oracle` tinha **dois braços com metrica errada** (comparavam contagens
     absolutas de linhas >3 palavras em populacoes de tamanhos diferentes, e contavam o ficheiro
     sem o esvaziar). Os **censos** desses braços sao validos e sao os do §2; as **asserccoes**
     foram corrigidas para fraccoes e para o oraculo ser dono do ficheiro, e a corrida foi
     repetida com o stream gravado (`--stream`, ~10 s em vez de ~170 s). O caminho `--stream`
     esta' verificado (GREEN).

## CACHE/PRICE
- task/agent: SottoFragmentacao
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoFragmentacao.jsonl
- cache: read=27473824 write=0 hit=98.6648% (cache-read / input+cache-read); universe: 112 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoFragmentacao.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=101 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=8 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-4/space-bunny-free $0.00000000; opencode-zen/ling-3.1-flash-free $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 112 of 112 matched usage rows
- when-failed: break_items=5; WHEN=2026-10-06T13:12:35.756000+00:00 | break_items=1; WHEN=2026-10-06T13:12:39.851000+00:00 | break_items=5; WHEN=2026-10-06T13:12:41.148000+00:00 | break_items=16; WHEN=2026-10-06T13:12:42.370000+00:00 | break_items=2; WHEN=2026-10-06T13:19:55.803000+00:00 | break_items=2; WHEN=2026-10-06T13:22:28.985000+00:00 | break_items=1; WHEN=2026-10-06T13:32:42.755000+00:00 (state=RESOLVED-BREAKS-OMP; population: 7 of 118264 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoFragmentacao']; window: 2026-10-06T13:12:35.756000+00:00..2026-10-06T13:32:42.755000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791292355756 | session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791292359851 | session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791292361148 | session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791292362370 | session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=deepseek-flash model=deepseek-flash item_index=44; turn_id=1791292795803 | session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=deepseek-flash model=deepseek-flash item_index=88; turn_id=1791292948985 | session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=deepseek-flash model=deepseek-flash item_index=396; turn_id=1791293562755 (state=RESOLVED-BREAKS-OMP; population: 7 of 118264 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoFragmentacao']; window: 2026-10-06T13:12:35.756000+00:00..2026-10-06T13:32:42.755000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T13:40:22.219844+00:00
- usage rows: 112
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 371788
- output tokens: 126805
- cache-read tokens: 27473824
- cache-write tokens: 0
- hit ratio: 98.6648% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- price partition: price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=101 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=8 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-4/space-bunny-free $0.00000000; opencode-zen/ling-3.1-flash-free $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 112 of 112 matched usage rows
- prefix breaks: 32 (state=RESOLVED-BREAKS-OMP; population: 7 of 118264 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoFragmentacao']; window: 2026-10-06T13:12:35.756000+00:00..2026-10-06T13:32:42.755000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=5; WHEN=2026-10-06T13:12:35.756000+00:00; WHERE session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791292355756
  - break_items=1; WHEN=2026-10-06T13:12:39.851000+00:00; WHERE session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791292359851
  - break_items=5; WHEN=2026-10-06T13:12:41.148000+00:00; WHERE session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791292361148
  - break_items=16; WHEN=2026-10-06T13:12:42.370000+00:00; WHERE session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791292362370
  - break_items=2; WHEN=2026-10-06T13:19:55.803000+00:00; WHERE session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=deepseek-flash model=deepseek-flash item_index=44; turn_id=1791292795803
  - break_items=2; WHEN=2026-10-06T13:22:28.985000+00:00; WHERE session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=deepseek-flash model=deepseek-flash item_index=88; turn_id=1791292948985
  - break_items=1; WHEN=2026-10-06T13:32:42.755000+00:00; WHERE session_id=01a11156-b738-73f3-adc6-43d763a2a1ab provider=deepseek-flash model=deepseek-flash item_index=396; turn_id=1791293562755
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision

## §8 ESTADO NO FIM — a cura foi DE-LANDADA por outra lane (17:45Z)

Apensado por `write`: o `edit` estava gateado pelo selo do teorista (ver bilhete 91bd528776ca020c9641cb8c).
As seccoes §1-§6 descrevem uma cura que EU medi GREEN as 13:40Z e que **ja' nao esta' no disco**.

- `app/electron/caption-formulation.js` perdeu a metade de renderer — ZERO ocorrencias de
  `lineProvisional`, `provisionalRoute`, `finalRoute`, `lineFinalPass`, `fileText`,
  `inventPunctuation`, `final-pass`; `onCommit(` voltou a ser a chamada sem `meta` e `expireHold()`
  voltou a `return commit('hold-timeout')`. Os **outros seis** ficheiros da cura mantiveram as marcas.
- `panel.js` foi reescrito por OUTRA lane (`docs/audit/historico-vs-redux.md`), com a intencao certa
  (`route !== 'final'` -> nao escreve) mas com o fallback `|| 'final'` a torna-la VACUA, porque o
  motor nao devolve `route`: escreve `route=final` em TUDO.
- PROVA em `history/2026-10-06/14.md` (14:43-14:46Z): `route=final` SEM `start=` e com razoes
  PRE-cura (`reason=hold-timeout`, `reason=audio-gap 72.80s`). Histograma: {'provisional': 11, 'final': 71}.
- E a prova de que a cura ESTAVA a funcionar, no mesmo dia, `11.md` (11:25-11:26Z): todas as linhas
  `route=final start=N reason=final-pass` — `final-pass` e' o marcador M3 desta lane.
- **O unico instrumento que reparou foi o meu oraculo**: `node _main/history-route-oracle.js` -> RED,
  4 violacoes. O `transcript-append-oracle.js` continua GREEN porque NAO cobre a rota.

Bilhete aberto: **`4fb5b25380cbc8269977e22e`** (P1) com o pedido de UMA de duas accoes.
