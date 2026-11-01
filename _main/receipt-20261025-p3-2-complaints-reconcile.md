# Recibo — P3.2: uma linha por reclamação, e a contradição deixa de ser silenciosa

item: **P3.2** de `docs/roadmap-observability.md` (2026-10-23) · data **2026-10-25** · repo `H:\sotto`
· **sem commit, sem push** · estado honesto: **ENTREGUE e ligado à bateria, NÃO VERIFICADO por
verificador independente e NÃO exercitado dentro de uma corrida da bateria** (gate `heavy` AMBER).

## P3.2

A linha do roadmap: *"Reconciliar os dois registos de reclamações (`backlog`: 10 ABERTO vs `closure`:
31/31 fechado) | uma linha por reclamação, com comando de fecho; a contradição é a mesma classe do
`BUG-20261023-03`"*.

## 1. O defeito, medido nas duas pontas

| | `runs/TC-20261022-sotto-backlog.md` | `.opencode/complaints-closure.md` |
|---|---|---|
| população | **39 linhas** (22 FECHADO, 6 PARCIAL, 10 ABERTO, 1 DECIDIDO) | **31 secções R1..R31, todas `closed`**, `81/81` reclamações cobertas |
| data | 2026-10-22 ~07:1x | secoes que citam mensagens de 2026-10-09 a 2026-10-22 |
| julga o quê | a fala do dono, linha a linha | um comando por secção (`rc=0`) |

As duas listas são do mesmo dono, sobre a mesma coisa, e **não concordam**: entre as fontes das
secções `closed` estão exactamente as mensagens que o backlog diz ABERTAS — `L100` → R16/R18 (`C5`,
`C6`, `C14`, `C18`), `L121` → R15 (`C4`), `L122` → R21 (`A1`, `B7`), `L106` → R13 (`C13`),
`L107` → R15 (`C20`), `L75` → R15 (`C21`), `L102` → R15 (`B5`, `C22`), `L145/L149` → R26 (`B6`).

Até hoje nada as juntava: cada registo era internamente consistente, e o produto da leitura era
*"10 coisas abertas"* ou *"tudo fechado"* conforme o ficheiro que se abrisse. É a classe do
`BUG-20261023-03` — *documentação afirma o contrário da medição, e a afirmação nunca é re-medida* — e
esta instância é pior: **auto-referente** (§5).

## 2. Registado antes das edições (Task Resolver)

`T-09` apendada ao TODO da lane com `status: doing` **antes** de qualquer ficheiro novo, e o replay
estrito corrido nesse estado: `RED code=REQUIRED_ID_UNSETTLED detail=T-09 status=doing` — o estado em
voo declarado, não um verde emprestado. Classificação das linhas de aceitação:

| # | linha | classe | invocador real | controlo positivo | controlo negativo |
|---|---|---|---|---|---|
| R1 | as duas populações são lidas e conferidas contra a contagem que cada uma declara | **MECHANICAL** | `python _main\complaints-reconcile-gate.py` | `backlog-parsed` 39 = 22+6+10+1; `closure-parsed` 31 secções, 81/81 | `drop-row`, `drop-fonte`, `invent-row` |
| R2 | a junção é calculada das **palavras do dono**, não escrita à mão | **MECHANICAL** | idem | `link-plausible` 21/39 ligadas, cada id verificado contra a mensagem | mutante implícito: um id que não partilhe duas palavras de 5+ letras é RED |
| R3 | uma reclamação não fechada que uma secção `closed` reivindica é **contradição**, e é calculada | **MECHANICAL** | idem | `contested-declared` 13 contradições nomeadas | `hide-gap`, `phantom-gap` |
| R4 | cada contradição traz um `gap` que **nomeia a secção** e diz o que ela não mede | **MECHANICAL** | idem | `gap` com ≥40 caracteres e o id da secção | `thin-gap` (`gap='inventado'`) |
| R5 | um `closed` só existe com evidência verificável: `command` (policy), `inspection` (`path:line`) ou `record` (a linha do backlog que contém o id) | **MECHANICAL** | idem | 23 linhas fechadas com evidência verificada | `strip-evidence`, `dead-citation` |
| R6 | um estado do mapa só diverge do backlog com `override` (razão + data + evidência) | **MECHANICAL** | idem | `map-state-agrees` 39 conferidos; `D1` fecha por override | `flip-state` |
| R7 | a secção que se fecha correndo o próprio portão do documento é **defeito declarado**, não fecho | **MECHANICAL** | idem | `self-closure-declared` acha `R28` e exige a declaração | `undeclare-self-closure` |
| R8 | **nenhuma** reclamação é declarada resolvida por este trabalho | **JUDGMENT** | este recibo | 13 contradições ficam abertas, com dono | falsificador: um `reconciled: closed` sem closer re-executável ou sem `override` datado |

**Invoker da bateria:** `call :step always complaints-reconcile 0 … python _main\complaints-reconcile-gate.py`
e `call :step always red-as-expected-complaints-reconcile 1 … --neg-arm` com o token `NEG-ARM PASS`.

## 3. O desenho: três artefactos, e a junção não é opinião

1. **A população** — os dois documentos, lidos como estão. O parser do backlog usa `[A-Z]\d+`; um
   `[A-D]\d+` perde a linha `E1` e dá **38 em vez de 39** (medido; é o braço negativo `drop-row`).
   A população do corpus é `complaints_canon.complaints()` = **81**, não `load()` = 148: as outras 67
   são directivas, dispatches, ruído e probes, e contá-las faria o documento de fecho parecer
   incompleto por 67 linhas que não são reclamações. **O próprio portão apanhou este erro na sua
   primeira execução** (§6).
2. **A junção** — por citação exacta das palavras do dono (recall medido **12/39**) e, onde a citação
   é paráfrase, por ligações declaradas cujo id é verificado contra a mensagem (duas palavras de 5+
   letras em comum, ou a citação inteira contida). Resultado: **21/39** linhas ligadas ao corpus. Um
   id que a citação exacta encontre **tem** de estar declarado — o portão exige-o.
3. **A contradição** — calculada: `reconciled != closed and corpus_ids ∩ fontes(section) ≠ ∅`. Sai
   **13**: `A1→R21`, `B5→R15`, `B6→R26`, `B7→R21`, `C4→R15`, `C5→R16/R18`, `C6→R16/R18`,
   `C13→R13`, `C14→R16/R18`, `C18→R16/R18`, `C20→R15`, `C21→R15`, `C22→R15`. Cada uma leva `gap`
   que nomeia a secção e diz o que a evidência dela **não** mede. Nenhuma é declarada resolvida.

## 4. Duas coisas que a junção fez aparecer (e que valem mais que o mecanismo)

**(a) `R28` fecha-se correndo o portão do próprio documento.** A secção *"finaliza o Sotto: tudo que
reclamei tem de estar feito"* (`L119`, 2026-10-22 06:11 — a frase mais exigente do corpus) tem como
evidência:

```
evidence: `python _main/complaints-closure-gate.py --self` -> CLOSURE
    CLOSURE documento=complaints-closure.md sections=31 closed=30 covered=81/81 missing=0
```

O documento absolve-se a si mesmo. E o literal citado diz `closed=30` enquanto hoje o documento tem
**31** fechadas (`L942`): **a evidência citada já não descreve o documento que a contém, e nada a
re-mede**. Fica declarado no mapa (`known_defects`), com dono, e o portão exige essa declaração —
tirá-la é `RED` (`undeclare-self-closure`).

**(b) A evidência de `R16` não é auditável, e o backlog dá `file:line`.** `R16` (a caixa de procura e
as barras on/off) fecha com `python _main/complaints-assert.py onoff-bars-absent -> PASS`: uma
asserção sem ficheiro nem linha. O backlog responde com `panel.html:601-614`, onde o formulário
`<form class="search" id="search-form">` está. Duas afirmações opostas, uma auditável e a outra não —
e é o formato da evidência, não a boa-fé de ninguém, que decide qual se pode verificar.

**Uma reclamação fecha-se de facto, por medição.** `D1` ("parakeet no segundo pass com lifecycle
inteligente") estava ABERTA com a evidência *"buraco em `on_external_captions_released`
(`sotto_webview.py:9194`)"*. O `BUG-20261023-03` já tinha medido que o método repõe o worker com as
guardas, e hoje `python _main/external-resume-oracle.py` dá `EXTERNAL-RESUME VERDICT PASS` com 8
braços verdes. `D1` passa a `closed` **por `override` datado**, com o comando no mapa, e
`--replay` re-executa-o: `REPLAY PASS D1 rc=0 esperado=0 literal=achado`. É o único fecho novo desta
lane, e é medido.

## 5. O que mudou (caminhos exactos)

| caminho | tipo | bytes | sha256 |
|---|---|---|---|
| `_main/complaints-reconcile-gate.py` | **novo** (LF) | 31780 | `1d78708d1ee65c7b6cf0e7614ad7530dfc8867192300fcc72569e18b585470b2` |
| `_main/complaints-reconcile.json` | **novo**, 39 linhas | 16406 | `f0236b320f74d51069730f7d75dd2e21671fc60f4b23cb6397e3f6dfb5faefa1` |
| `_main/_audit-verify-all.cmd` | 2 passos novos (7 linhas de comentário + 6 de passo), ambos `always` | 118761 (1574 CRLF / 0 bare LF) | `f73f330e27f3066ea8eaab640d83489ad61c0e523cd10efd05708e634dbf408a` |
| `AGENTS.md` | pin re-medido + a linha de história | 21856 | `c74ae88e7cd59b112b22f7026ca4749b7fdf9e6a50627736d40084601be823af` |
| `docs/state-generated.md` | regenerada (128 passos) | 17242 | `9262ea12210a2345194df56200792da30cb1088b71b6ecd71e27282e1803b581` |
| `docs/roadmap-observability.md` | linha P3.2 com os números medidos | 9245 | `e43d32de6c309bf9c6b0721e6e91514afd789772c4a0569cabfd9ace8807d6c3` |

**Aviso sobre o roadmap:** às 08:05:31 de hoje esse ficheiro foi reescrito por **outra lane** (8099 →
8434 B, travessões tipográficos convertidos em hífens ASCII) e a linha P3.1 desta lane sobreviveu.
Esta lane editou **só** a linha P3.2; o sha acima descreve o ficheiro no momento do recibo, não uma
versão estável — a linha é a unidade citável, não o digest.

Ficheiros de produto de outras lanes: **não tocados** (`app/webview/sotto_webview.py`,
`app/webview/youtube_window.py`, `worker/sotto_worker.py`; mtimes 2026-10-23/24).

## 6. Evidência executada

``` 
python _main\complaints-reconcile-gate.py
CHECK backlog-parsed         PASS  linhas=39 closed=22 decided=1 open=10 partial=6 declarados=ABERTO:10,DECIDIDO:1,FECHADO:22,PARCIAL:6
CHECK closure-parsed         PASS  seccoes=31 closed=31 com_fonte=31 cobertura=81/81
CHECK map-covers-population  PASS  linhas=39 mapa=39
CHECK map-state-agrees       PASS  39 estado(s) conferido(s)
CHECK closed-has-evidence    PASS  23 linha(s) fechada(s) com evidencia verificada
CHECK contested-declared     PASS  contradicoes=13 A1->R21,B5->R15,B6->R26,B7->R21,C13->R13,C14->R16/R18,C18->R16/R18,C20->R15,C21->R15,C22->R15,C4->R15,C5->R16/R18,...
CHECK self-closure-declared  PASS  auto-fecho=R28 declarados=1
CHECK link-plausible         PASS  linhas_ligadas=21/39
SUMMARY lines=39 closed=23 decided=1 open=9 partial=6 contradicoes=13
COMPLAINTS-RECONCILE PASS checks=8 fail=0                                        rc=0

python _main\complaints-reconcile-gate.py --neg-arm
MUTATION drop-row                NEG-ARM PASS [esperado: map-covers-population]  recusou por: map-covers-population
MUTATION invent-row              NEG-ARM PASS [esperado: map-covers-population]  recusou por: map-covers-population
MUTATION flip-state              NEG-ARM PASS [esperado: map-state-agrees]       recusou por: map-state-agrees, closed-has-evidence
MUTATION strip-evidence          NEG-ARM PASS [esperado: closed-has-evidence]    recusou por: closed-has-evidence
MUTATION dead-citation           NEG-ARM PASS [esperado: closed-has-evidence]    recusou por: closed-has-evidence
MUTATION hide-gap                NEG-ARM PASS [esperado: contested-declared]     recusou por: contested-declared
MUTATION phantom-gap             NEG-ARM PASS [esperado: contested-declared]     recusou por: contested-declared
MUTATION thin-gap                NEG-ARM PASS [esperado: contested-declared]     recusou por: contested-declared
MUTATION undeclare-self-closure  NEG-ARM PASS [esperado: self-closure-declared]  recusou por: self-closure-declared
MUTATION drop-fonte              NEG-ARM PASS [esperado: closure-parsed]         recusou por: closure-parsed
NEG-ARM PASS mutations=10 named-arm-fail=0                                       rc=1 (por desenho)

python _main\complaints-reconcile-gate.py --replay
REPLAY PASS D1 rc=0 esperado=0 literal=achado
REPLAY-VERDICT PASS ran=1 failed=0 skipped=0                                     rc=0
```

Portões que policiam a mudança:

``` 
python _main\agents-md-pins-oracle.py   -> AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)  rc=0
python _main\sotto-state-page.py --require-fresh
   SUMMARY passos=128 PASS=49 EXPECTED-RED=17 FAIL=7 STALE=37 NO-VERDICT=7 NOT RUN=11
   BATTERY-VERDICT state-page PASS checks=8 fail=0                                                rc=0
python _main\claims-date-oracle.py      -> BATTERY-VERDICT claims-date PASS checks=4 fail=0       rc=0
python _main\tooling-intent-oracle.py   -> TOOLING-INTENT VERDICT PASS                            rc=0
python _main\battery-wiring-oracle.py   -> populacao=172 ligados=48 sem_passo=124 ; PASS checks=6  rc=0
python _main\code-health-oracle.py      -> FAIL rc=2, as MESMAS 8 metricas de 3 ficheiros de outra lane
```

**O ratchet do P3.1 morde outra vez, no mesmo dia:** o oráculo novo é um `*-gate.py`, logo entra na
população do wiring. Ligado no mesmo gesto, `sem_passo` fica em **124** e o tecto não se move; se
tivesse ficado por ligar, `new-unwired` seria vermelho. É a prova de que o P3.1 não é decoração.

## 7. Passagem de refutação (sequencial)

**(a) A população do corpus estava errada na primeira execução — apanhada pelo próprio portão.**
`load()` dá 148 mensagens; `complaints()` dá 81. A asserção de cobertura correu contra 148 e acusou 67
"reclamações sem secção" — um falso vermelho que teria feito o portão nascer partido. Corrigido para
`complaints()` (`cobertura=81/81`) e declarado no código, no ponto onde se decide a população.

**(b) Um `gap` de nove letras passava.** A primeira versão exigia só que `gap` fosse não vazio: um
`gap: "inventado"` satisfazia a existência e não dizia nada — exactamente a doença que o portão
combate. Agora exige ≥40 caracteres **e** o id da secção que contradiz; o mutante `thin-gap` prova os
dois braços. Ao apertar, apanhou logo um erro meu: o `gap` da `C14` nomeava `R15` quando as secções
que a reivindicam são `R16/R18` (chega por `L100`) — texto corrigido, não o check.

**(c) O que a passagem NÃO derrubou, e fica como limite declarado.**
(i) O portão verifica que um `closer` **corre e imprime o literal**, não que o comando seja *relevante*
para a reclamação: `python -c "print('X')"` passa a policy. Quem fecha por `override` fica registado
com data e comando; a relevância é julgamento humano.
(ii) `gap` é prosa: o portão exige que nomeie a secção e tenha corpo, não que seja verdade.
(iii) A junção por vocabulário aceita duas palavras comuns (`sotto`, `painel`); 21/39 é o recall
medido, e 18 linhas não têm ligação nenhuma — o `SUMMARY` diz o número em vez de o esconder.
(iv) Uma edição **coordenada** do backlog e do mapa (baixar a contagem declarada) escapa a um portão
local; ficaria a precisar de história.

## 8. Fronteira do Watcher

`I:\!manager\tools\performance-gate.py status` → **AMBER**, `heavy_allowed=False`, com um lease
`light` de outro dono activo. Logo **nenhuma corrida completa da bateria** nesta lane. Os dois passos
novos foram exercitados com o **argv exacto** que a `.cmd` lhes dá e os rc que ela espera (0 e 1),
mas o verde *dentro de uma corrida* fica `NOT RUN` — `docs/state-generated.md` mostra 11 `NOT RUN`, e
é assim que deve estar.

## 9. Reverter

Apagar `_main/complaints-reconcile-gate.py` e `_main/complaints-reconcile.json`; retirar os dois
blocos `complaints-reconcile` / `red-as-expected-complaints-reconcile` da `.cmd` e reverter o pin no
`AGENTS.md` para **116990 B / 1558 CRLF / `A81E170B…B4739285F`**; regenerar `docs/state-generated.md`
e a linha P3.2 do roadmap. Nada mais importa estes ficheiros.

## 10. Abertos, com dono

1. **Corrida da bateria** (fecha o verde dos dois passos): precisa do lease `heavy`.
2. **13 contradições** — cada uma com `gap`; fechá-las exige o ecrã do dono (as que pedem o DOM
   renderizado) ou a ligação em ficheiros de outra lane (`B5`/`B6` em `sotto_webview.py`).
3. **`R28` auto-fecho** e o literal `closed=30` vs 31 — dono do documento de fecho, fora desta lane.
4. **`code-health` FAIL rc=2** — as mesmas 8 métricas em 3 ficheiros de outra lane, inalteradas.
## P3.2-reconcile

Reconciliacao das contradicoes abertas contra a evidencia de hoje, e o veredicto da bateria que estava
na fila desde o P0.2.

### 1. A bateria: admitida sob lease, e o veredicto lido do FICHEIRO

Lease `heavy id=291494fe2c4c450699945f8f7504027f owner=sotto-lane-p32 ttl=3600`, concedido com o
portao GREEN (`heavy_allowed=True`, 0 leases), libertado no fim. Comando: `set SOTTO_BATTERY_HEAVY=1 &&
_main\_audit-verify-all.cmd`, log `G:\Temp\opencode\battery-p32.log` (166 linhas).

```
steps    : 128   gate=80  control=8  skipped=6  expect-red=34  missing=0  cached=64
failed:  exception-hygiene=2 code-health=2 red-as-expected-code-health=2 state-page=1 red-as-expected-state-page=2
BATTERY-VERDICT: RED - 5 step(s) failed
```

Um so `steps=`. O exit code foi 1 e o veredicto diz RED: os dois concordam, e foi o veredicto que se
leu, nao o `rc` de um passo.

**6 passos NAO CORRERAM** -- `skipped:` e `heavy:` sao exactamente a mesma lista (`mute-audio`,
`strip-stats-log-budget`, `strip-surface-runtime`, `strip-geometry-restore`, `strip-stats-wave`,
`control-panel-exit3-neg-arm`), e um passo saltado **nao** e um portao que passou.

A causa foi medida, nao suposta: `cmd /c "set FOO=1 && set FOO"` imprime `FOO=1 ` (com espaco a
direita), e `cmd /c "set BAR=1&& set BAR"` imprime `BAR=1`. O `set VAR=1 && ...` entrega o valor
`"1 "`, e o opt-in da `.cmd` le o VALOR (`if not "%SOTTO_BATTERY_HEAVY%"=="1"`), logo recusou os
pesados. Forma correcta, na proxima: `set "SOTTO_BATTERY_HEAVY=1" && ...` ou `set
SOTTO_BATTERY_HEAVY=1&& ...`. O instrumento esta certo; a invocacao estava errada.

### 2. As 5 falhas, uma por uma, com o que esta lane pode e nao pode fazer

| passo | rc | causa medida | de quem e |
|---|---|---|---|
| `exception-hygiene` | 2 | `got={'worker/sotto_worker.py': {'now': 8, 'baseline': 7}}`; `measured 41` vs `baseline 40` | ficheiro de outra lane (`git diff --stat`: +139/-2, duas linhas `except` novas) |
| `code-health` | 2 | as 8 metricas pioradas estao TODAS em `app/webview/sotto_webview.py`, `app/webview/youtube_window.py`, `worker/sotto_worker.py` | os tres ficheiros sujos de outras lanes, preservados por ordem |
| `red-as-expected-code-health` | 2 | CONTROL FAILED porque o passo real ja sai 2: o braco nao distingue o defeito injectado do que ja la esta | consequencia da linha acima |
| `state-page` | 1 | pagina velha (o passo lia um resumo que ja nao descrevia o registo) | **desta lane: corrigido** |
| `red-as-expected-state-page` | 2 | o mesmo motivo, do lado do braco | **desta lane: corrigido** |

`code-health` e `exception-hygiene` sao o MESMO facto visto por dois instrumentos independentes:
`except_pass piorou de 13 para 14` em `worker/sotto_worker.py` e `now: 8 / baseline: 7` no mesmo
ficheiro. Uma causa, um ficheiro, e nenhum dos dois e desta lane. Nao se fecha nem com uma edicao
(proibida) nem a subir a linha de base (esconderia a regressao). Fica **RED, atribuido**, com dono.

Depois desta lane, com o registo vivo:

```
python _main\sotto-state-page.py --write     -> passos=128 PASS=84 EXPECTED-RED=31 FAIL=6 STALE=2 NO-VERDICT=5 NOT RUN=0
python _main\sotto-state-page.py --check     -> BATTERY-VERDICT state-page PASS checks=7 fail=0   (rc=0)
python _main\sotto-state-page.py --require-fresh -> BATTERY-VERDICT state-page PASS checks=8 fail=0 (rc=0)
```

Ou seja: das 5 falhas, **2 passaram a verdes** com o trabalho desta lane; as outras 3 sao um ficheiro
alheio e o braco que o segue. O verde da bateria inteira continua **impossivel daqui**, e agora esta
dito com numeros em vez de "por correr".

### 3. As contradicoes: 13 -> 8, e nenhuma fechada por opiniao

O mapa aplicado (`_main/complaints-reconcile.json`) e o `v2`; o portao mede o resto:

```
CHECK contested-declared PASS contradicoes=8 A1->R21,B6->R26,B7->R21,C14->R16/R18,C20->R15,C21->R15,C22->R15,C4->R15
SUMMARY lines=39 closed=28 decided=1 open=5 partial=5 contradicoes=8
COMPLAINTS-RECONCILE PASS checks=8 fail=0
```

As cinco que fecharam, com o comando que `--replay` re-executa e o literal que ele tem de achar:

| id | o que decidiu | literal |
|---|---|---|
| `C5` | `panel.html:599-607` hoje e o COMENTARIO que registra a ordem do dono (2026-10-21 21:24 verbatim) -- o backlog de 2026-10-22 citava ali o formulario | `RESULT search-box-absent PASS` (nodes 0, wiring 0) |
| `C6` | a assercao de R16 le `panel.css` e `panel.html` com comentarios removidos: 0 regras por `[aria-pressed]`, 0 palavra em `::after`, 2 bolas, 1 regra `data-live="on"` | `RESULT onoff-bars-absent PASS` |
| `B5` | `youtube_window.collapse_growth` existe, foi medida contra o historico do dono (79/0/6) e esta LIGADA em `sotto_webview.py:2408-2416` | `BATTERY-VERDICT youtube-window-oracle PASS checks=12 fail=0` |
| `C13` | `three-overlays-oracle` A3: o overlay da legenda e gated em `data-float` (`display:none` por omissao, `block` so em strip+float); C3: nenhum no historico/transcricao no markup do strip | `33 check(s), 0 failed / VERDICT: PASS` |
| `C18` | a marca medida no documento VIVO (o `panel.html` entregue, em Edge sem janela), 4 larguras, por tema | `TOTAL: 36 brand measurement(s) across 4 widths; 0 with the text wider than its box` |

Os dois probes de render correram sob um lease proprio (`heavy id=f52984739e8e4f3488c5e53d801fb09e`,
`validate` -> `valid heavy lease ... state=green`, libertado no fim), sequenciais, com a saida completa
guardada (`G:\Temp\opencode\c13-three-overlays.log` 4079 B, `c18-brand-truncation.log` 5699 B). Nenhum
deles pede janela: `select-string 'headless:\s*false|--window-position|show:\s*true'` sobre `_main\*.mjs`
e `_main\*.js` devolve **vazio**, e o `chromium.launch({channel:'msedge'})` do Playwright e headless por
omissao.

Cada `closed` leva a prova do que **nao** prova:

* `C13` e prova de REGRA (nenhuma regra pinta a legenda na superficie do painel), **nao** um censo de
  pixeis do painel direito pintado -- nenhuma sonda desta bateria faz esse censo;
* `C18` mede **4** larguras, nao todas as larguras de janela que o dono usa;
* `B5` fecha o caminho VIVO; o escritor do armazem (`history_append`) continua **sem guarda propria** --
  falta defesa em profundidade, nao ha caminho aberto.

As 8 que ficam, cada uma com o que lhe falta e nao e desta lane: `A1`/`B7` (o slip de VRAM sob
inferencia; a qualidade do texto contra audio conhecido), `B6` (a metade PINTADA: a janela de duas
linhas ja chega ao caminho vivo, a re-embrulhar pela largura nao), `C14`/`C20`/`C21`/`C22` (o DOM
pintado, ou uma decisao do dono), `C4` (o tema broadcast renderizado). Nenhuma foi fechada por
"parece feito".

### 4. O defeito que este passo encontrou no instrumento do P0.2

Ao regenerar a pagina, o braco negativo do P0.2 passou a `NEG-ARM FAIL mutations=8 named-arm-fail=1`:
o mutante `forget-step` era recusado por quatro checagens mas **nao** pela que declara
(`absent-is-not-run`). Cluster: instrumento afirma um braco que nao dispara. Hipotese unica: a mutacao
apaga o log pelo nome do PASSO, e o log real nao se chama assim.

`mut_flip_green_to_notrun` apagava `pycompile-sotto_webview.log`; o ficheiro do passo e
`pycompile-webview.log` (a coluna `log` da propria pagina). O registo saia, o log ficava, e a condicao
nomeada -- "sem registo **E** sem log" -- nao podia ser verdadeira. O erro so era *visivel* agora: com a
pagina velha, o mutante era recusado por divergencia e o braco parecia provado.

Correccao (a classe, nao o sintoma): ler o nome do log do PROPRIO registo antes de o apagar. Prova,
com a expectativa declarada **inalterada**:

```
antes:  MUTATION forget-step  NEG-ARM FAIL  [esperado: absent-is-not-run] ... recusaram: no-invented-green, cells-match-record, page-in-sync, summary-counts
        NEG-ARM FAIL mutations=8 named-arm-fail=1
depois: MUTATION forget-step  NEG-ARM PASS  [esperado: absent-is-not-run] recusou por: no-invented-green, absent-is-not-run, cells-match-record, page-in-sync, summary-counts
        NEG-ARM PASS mutations=8 named-arm-fail=0
```

Se o mutante fosse "recusado por outra coisa qualquer", nao valia; ele passou a ser recusado **pelo
braco que o nomeia**, e foi o unico a mudar. Nao ha braco novo nem expectativa afrouxada.

### 5. Outros controles, hoje

```
python _main\complaints-reconcile-gate.py --neg-arm  -> NEG-ARM PASS mutations=10 named-arm-fail=0 (rc=1 POR DESENHO)
python _main\complaints-reconcile-gate.py --replay   -> REPLAY PASS B5,C5,C6,C13,C18,D1 ; REPLAY-VERDICT PASS ran=6 failed=0 skipped=0 (rc=0)
```

### 6. Limites deste passo (o que NAO prova)

1. `--replay` prova que o closer **corre e imprime o literal**; nao prova que ele e **relevante** --
   `python -c "print('X')"` passaria a politica. A relevancia e do gap, e o gap e prosa.
2. A classe pesada da bateria **nunca correu**: 6 passos NOT RUN.
3. O verde da bateria inteira continua fora do alcance desta lane: 2 passos vermelhos por um ficheiro
   que ela nao pode tocar.
4. `C18` mede 4 larguras; `C13` e prova de regra. Nenhum dos dois e um censo do ecra do dono.

### 7. Reverter

`git checkout -- _main/sotto-state-page.py` devolve a mutacao ao estado anterior (e o braco nomeado
volta a nao disparar); `git checkout -- _main/complaints-reconcile.json` devolve o mapa de 13
contradicoes; `python _main/sotto-state-page.py --write` regenera a pagina a partir do registo vivo.
