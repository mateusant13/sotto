# Recibo — duplicação das entradas de transcript (Sotto, 2026-10-06)

status: done

**Lane:** `SottoDuplicaLinhas`
**Alvo:** `H:/sotto` (a app a correr — medida, não relançada)
**Artefacto do dono:** `history/2026-10-06/06.md` e `07.md`, mais `_main/webview-run.log`

## Contrato (declarado, com fonte)

| # | item | fonte |
|---|---|---|
| 1 | ler o artefacto do dono e MOSTRAR as linhas duplicadas | o ticket |
| 2 | decidir ENTRE (a)(b)(c)(d) com evidência (comando + número) | o ticket |
| 3 | consertar só o que a evidência nomear, preservando o append | o ticket |
| 4 | cada legenda nova = UMA linha nova, NUNCA a mesma linha duas vezes | a queixa do dono, verbatim |
| 5 | `docs/audit/transcript-duplicacao.md` com linhas reais, hipótese e cura | o ticket (Acceptance) |
| 6 | um teste/check que distinga append de duplicação | o ticket (Acceptance) |
| 7 | não tocar em `worker/wasapi_loopback.py` | o ticket (Acceptance) |
| 8 | SELF-AUDIT + CACHE/PRICE no recibo | `I:/!manager/AGENTS.md` |

**Estado do entregável: LIVE** — não é "escrevi o ficheiro". O check novo foi
corrido contra três motores (o de hoje, o pré-cura e um mutante de perda) e
devolve GREEN / RED / RED com os códigos de saída 0 / 1 / 1. O motor mudado é o
mesmo ficheiro que `panel.html` carrega (`sotto_webview.py` navega para
`H:\sotto\app\electron\panel.html`); **não** foi corrido no painel a correr,
porque a ordem era medir sem relançar — ver "não verificado".

## O que mudou

| ficheiro | o quê |
|---|---|
| `app/electron/caption-formulation.js` | a cura: `emittedStart` / `emittedEnd` / `emittedWords` sobrevivem ao `commit`, e `ingest` escreve só as palavras novas de uma continuação |
| `app/electron/transcript-append-oracle.js` | o check novo (replay dos streams reais pelo motor real + casos unitários) |
| `app/electron/package.json` | script `transcript-append-oracle` (convenção do `bridge-selftest:node`) |
| `docs/audit/transcript-duplicacao.md` | o documento da Acceptance |

## A causa, em uma frase

O worker manda a LINHA (mesmo `start`, `end` a crescer — `sotto_worker.py:_event`),
o `hold deadline` do painel (1500 ms) commitava um PREFIXO dela, e `commit()`
fazia `takeBuffer()` → `lastAudioEnd = null`: a continuação deixava de ser
reconhecível como continuação e as palavras já escritas iam para o histórico
outra vez.

## A escada de evidência (os números)

```
$ node app/electron/transcript-append-oracle.js
engine under test: H:\sotto\app\electron\caption-formulation.js
#gate-live-speech (cumulative, live tap): 2 worker lines, 13 commits, 27 words, 2 line(s) checked at the weaker meta=none bar
#ACCEPT-after (delta, file mode): 16 worker lines, 16 commits, 29 words, 16 line(s) checked at the weaker meta=none bar
RESULT: GREEN — every worker line is appended once, in order, word for word      rc=0

$ node app/electron/transcript-append-oracle.js --pretend <pré-cura>
RESULT: RED — 16 violation(s)      rc=1    # 103 palavras escritas onde o worker disse 27

$ node app/electron/transcript-append-oracle.js --pretend <mutante: opening = []>
RESULT: RED — 3 violation(s)       rc=1    # "committed (2 words)" contra "expected (15 words)" = PERDA
```

O stream delta dá 16 commits / 29 palavras **antes e depois** da cura: sem
regressão no modo ficheiro.

Censo do artefacto do dono:

```
06.md: 124 entries, 3 exact-duplicate pairs, 83 word-prefix pairs   -> RED
07.md:  13 entries, 0 exact-duplicate pairs,  7 word-prefix pairs   -> RED
feed do painel == ficheiro do dono (137 == 137, mesma ordem) : True
```

`worker/wasapi_loopback.py`: **não tocado** (aparece `M` no `git status` por
outra lane; este lane não o abriu para escrita).

## SELF-AUDIT

- **protocolos em falta** — a regra do `dispatch-preflight` ("verificar os paths
  citados antes de os citar") apanhei-a a meio: citei `worker/runs/gate-live-speech.jsonl`
  pela documentação de um audit anterior e só depois fui confirmar a forma das
  captions. Faria diferente: abrir o produtor da linha (o `_event` do worker)
  ANTES de raciocinar sobre o que a linha mede — foi exactamente o que o audit
  `painel-atraso-e-acerto.md` já dizia e eu repeti o atalho.
- **verificação adicional** — um replay do stream reconstruído a partir de
  `webview-run.log` (só texto; sem `start`/`end`) pelo motor real, que fecharia a
  inferência do §6 do audit. Custo: o log não guarda posição de áudio, logo a
  reconstrução exige inventar a janela — mediria o meu palpite, não o ficheiro do
  dono. Não correu, e por isso está marcado `[INFERENCE]` no audit em vez de
  contado como prova.
- **checkboxes novas** — a mecânica que faltava a esta classe: *quando uma linha
  é escrita por um produtor e o consumidor mantém estado entre commits, o
  invariante é `concat(escrito) == dito`, uma vez cada*, e o check que o trava
  corre o stream real pelo módulo real com o pior caso temporal
  (`node app/electron/transcript-append-oracle.js`). UM comando, RED no motor
  pré-cura, RED no mutante de perda, GREEN no de hoje.
- **review por outro subagente** — sim-com-escopo: revisão do `ingest` novo em
  `caption-formulation.js:355-393` (a porta `start === emittedStart`, a ordem
  `emittedWords`/`opening` e a interacção com o `chars`-cap em `sotto_webview.py`
  que re-entra com a mesma `meta`). Um par que corra o oracle contra um stream
  dele é a revisão mais útil; o resto do trabalho é medição já citada.
- **gate-doubt**:
  - `verde-de-verdade:` o GREEN do `transcript-append-oracle` é de verdade e não
    vacuo, e a prova é o par armado em volta dele: o MESMO comando, o MESMO
    stream e a MESMA asserção dão `rc=1 / RED — 16 violation(s)` contra
    `git show HEAD:app/electron/caption-formulation.js` e `rc=1 / RED — 3` contra
    o mutante `opening = []`. Não é passa-por-construção (o oracle falha quando
    falha), não é flag suprida à mão (não há `--skip`), não é artefacto stale (o
    stream é lido em cada corrida) nem instrumento partilhado (é um `node` novo
    por corrida, sem estado em disco). O `--history` DO ficheiro do dono é RED —
    se o oracle tratasse tudo como verde, este braço não podia ser vermelho.
  - `falta-no-gate:` o oracle só compara stream contra motor. **Não** verifica a
    fidelidade do que o motor RECEBE: se o bridge passar a entregar as captions já
    fundidas (texto acumulado pelo shell em vez do worker), o oracle continua
    verde porque é ele que fornece o stream. Cenário que uma mudança futura
    atravessa: alguém põe `on_worker_caption` a receber a linha e imprime no log
    a linha inteira em vez do fragmento → o oracle não vê, e o `BRIDGE_CAPTION_SENT`
    deixa de casar com o que o motor come.
  - `gate-melhor:` um braço que compara o stream do oracle com o log da app —
    `node app/electron/transcript-append-oracle.js --from-log _main/webview-run.log`
    extraindo a sequência de `BRIDGE_CAPTION_SENT` e exigindo que a concatenação
    dos commits seja um prefixo exacto dessa sequência. Input que o deixa RED: um
    log onde um fragmento aparece duas vezes seguidas (o que o `§3(b)/(c)` já
    mediu ser zero) — hoje esse braço não existe, e é o buraco acima.
- **confianca** — alta na causa e na cura (a causa é reproduzida pelo motor
  pré-cura e a cura é medida pelo mesmo replay), média na cobertura da app em
  execução: o ficheiro do dono não foi regenerado. Subiria a alta com uma captura
  nova depois da cura (exige relançar a app) ou com o braço `--from-log`.
- **nao verificado** —
  1. o painel a correr com o motor novo (nada foi relançado);
  2. a app Electron (`app/electron/main.js`) com o motor novo — partilha o mesmo
     `caption-formulation.js`, mas não foi exercitado;
  3. o comportamento visual novo (linha seguinte só com as palavras novas) num
     écran real;
  4. `worker/wasapi_loopback.py` (de outra lane — deliberadamente não medido aqui);
  5. se um stream acumulativo chega com `start` arredondado de forma diferente
     entre parciais da MESMA linha (a guarda usa `===`); no stream real todas as
     parciais da linha 1 trazem `0.56` e as da linha 2 `8.96`, mas não esgotei
     streams.

## CACHE/PRICE

```
## CACHE/PRICE
- task/agent: SottoDuplicaLinhas
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoDuplicaLinhas.jsonl
- cache: read=8584448 write=0 hit=97.4596% (cache-read / input+cache-read); universe: 60 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T09-25-44-752Z_01a11088-84b0-75a9-9c9f-193b70f51d26\SottoDuplicaLinhas.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=52 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=5 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; open…[CORTADO pelo instrumento de leitura em 768 chars por linha]
- when-failed: break_items=2; WHEN=2026-10-06T12:18:14.405000+00:00 | break_items=1; WHEN=2026-10-06T12:18:15.121000+00:00 | break_items=2; WHEN=2026-10-06T12:18:15.781000+00:00 | break_items=8; WHEN=2026-10-06T12:18:16.628000+00:00 | break_items=2; WHEN=2026-10-06T12:20:23.335000+00:00 | break_items=3; WHEN=2026-10-06T12:25:05.168000+00:00 (state=RESOLVED-BREAKS-OMP; population: 6 of 117460 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoDuplicaLinhas']; window: 2026-10-06T12:18:14.405000+00:00..2026-10-06T12:25:05.168000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791289094405 | session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791289095121 | session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791289095781 | session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791289096628 | session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=deepseek-flash model=deepseek-flash item_index=90; turn_id=1791289223335 | session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=deepseek-fla…[CORTADO pelo instrumento de leitura em 768 chars por linha]
- report generated_at: 2026-10-06T12:26:19.689199+00:00
- usage rows: 60
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 223762
- output tokens: 74609
- cache-read tokens: 8584448
- cache-write tokens: 0
- hit ratio: 97.4596% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 18 (state=RESOLVED-BREAKS-OMP; population: 6 of 117460 OMP prefix-ledger rows attributable to keys ['01a11088-84b0-75a9-9c9f-193b70f51d26', 'SottoDuplicaLinhas']; window: 2026-10-06T12:18:14.405000+00:00..2026-10-06T12:25:05.168000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- WHEN / WHERE failed:
  - break_items=2; WHEN=2026-10-06T12:18:14.405000+00:00; WHERE session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791289094405
  - break_items=1; WHEN=2026-10-06T12:18:15.121000+00:00; WHERE session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791289095121
  - break_items=2; WHEN=2026-10-06T12:18:15.781000+00:00; WHERE session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791289095781
  - break_items=8; WHEN=2026-10-06T12:18:16.628000+00:00; WHERE session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791289096628
  - break_items=2; WHEN=2026-10-06T12:20:23.335000+00:00; WHERE session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=deepseek-flash model=deepseek-flash item_index=90; turn_id=1791289223335
  - break_items=3; WHEN=2026-10-06T12:25:05.168000+00:00; WHERE session_id=01a11126-2036-701c-a8d2-1a57a239f388 provider=deepseek-flash model=deepseek-flash item_index=192; turn_id=1791289505168
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Nota de fidelidade: as duas marcas `[CORTADO pelo instrumento de leitura em 768
chars por linha]` substituem o `…` que o instrumento de leitura aplicou às duas
linhas mais longas do relatório (o `cache-task-report.sh` escreveu-as inteiras no
artefacto). Nenhum número foi editado; onde o instrumento cortou, está dito.
