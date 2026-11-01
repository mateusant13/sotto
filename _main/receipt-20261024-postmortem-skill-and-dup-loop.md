# RECIBO — skill de postmortem, mecanica de debug obrigatoria e o laco do B5

**2026-10-24.** Ordem do dono: *"make real progress on Sotto, beginning with its protocols and then
applying them to code"*, sem parar na documentacao, com um instrumento pequeno de alto valor, prova
focada, e um registo unico. Modelo: DeepSeek V4.1 Flash via OpenCode Go 4 (esta lane). **Nenhum
worker foi lancado** — logo nao houve TODO para preencher nem skill para entregar a um subagente.

---

## 1. Scope

### Feito
| # | artefacto | o que e |
|---|---|---|
| 1 | `.opencode/skills/postmortem-sotto/SKILL.md` | camada **deste repo** sobre a skill canónica `I:\!manager\.agents\skills\postmortem\SKILL.md`; a versão anterior (que reescrevia a canónica) foi **retirada** — era o duplicado |
| 2 | `AGENTS.md` | §MECANICA OBRIGATORIA (7 passos, proporcional) e §POSTMORTEM (gatilho pelo **estado**, nao pela gravidade); bullet medido que **retira o numero 517**; pin da bateria re-medido |
| 3 | `_main/caption-dup-repro.py` | **o laco**: mede, minimiza, faz replay no invocador real e prova o detector por mutacao, nas **duas camadas** (store e painel) |
| 4 | `_main/_audit-verify-all.cmd` | o laco como passo `caption-dup-repro` (8 linhas) |
| 5 | `app/webview/youtube_window.py` | docstring do `collapse_growth`: o "517" sai, entram os numeros de hoje com o instrumento |

### Nao tocado
`worker/sotto_worker.py` (outra lane), `_main/code-health-baseline.json` (decisao do dono),
`_main/exception-baseline.json`, qualquer painel visivel. Nao houve largada da app, nem `--show`, nem
evento sintetico.

---

## 2. O registo da tarefa (single task record)

**Falha em estudo:** B5 — a legenda duplicada. Verbatim do dono: *"coisa duplicada"*, *"a frase era
maior, foi sumindo"*.

### Hipoteses, antes das sondas (ranqueadas, cada uma com o que a derrubaria)

| # | hipotese | sonda (uma variavel) | resultado |
|---|---|---|---|
| H1 | o duplicado e **escrito pelo store** (`history_append`) porque nada o compara com a linha anterior | ler os ficheiros reais de `history/` e contar pares consecutivos | **mantida**: 79 pares `igual` em 2077 linhas |
| H2 | o duplicado e so **render do painel**; o disco esta limpo | a mesma leitura, no disco | **derrubada**: o disco tem os pares |
| H3 | o caso "a frase era maior e foi sumindo" e o **mesmo** defeito do duplicado exacto | medir as tres relacoes em separado: igual / crescimento por prefixo / sobreposicao | **derrubada como igualdade**: 0 de crescimento por prefixo, 6 de sobreposicao. Sao relacoes diferentes -> guardas diferentes em camadas diferentes |
| H4 | o numero antigo **"517 de 2077"** e o impacto real | re-medir com a regra declarada | **derrubada**: nenhuma das tres relacoes dah 517. Numero **retirado** do AGENTS.md e do docstring |

Uma variavel por sonda: a sonda H1/H2 foi **a mesma leitura** com dois alvos (disco vs painel) e a
unica variavel foi o alvo; a sonda H3 mudou so a **relacao** de comparacao; a sonda H4 mudou so o
**numero citado**. Nenhuma sonda mudou o codigo do produto.

### Minimizar (delta-debug)

`--minimize` pega no primeiro par real do pior ficheiro, e **exige** que tirar qualquer uma das duas
linhas faca a duplicacao desaparecer. Resultado: par minimo de 2 linhas, `0 pares` com uma so ->
minimalidade provada (nao assumida).

### Replay diferencial e mutacao

| fase | o que faz | resultado de hoje |
|---|---|---|
| 3 | corre o **invocador real** `SottoShell.history_append` (duplo so substitui o caminho e a proveniencia) em 6 casos | 6/6 certos, **3 linhas escritas de 3 esperadas** |
| 4 | **mutacao focal**: `_history_last_body -> None` (a guarda desaparece) | replay **vermelho**, **4 linhas** -> `NEG-ARM PASS` |
| 5 | camada do **painel**: `collapse_growth` sobre a terna real, o caso legitimo de duas linhas vivas, e o mutante **identidade** | 3 -> 1 (fica o maior), duas vivas ficam duas, mutante **vermelho** |

O mutante escreve 4 linhas onde o codigo real escreve 3: e essa a prova de que o laco ve o defeito e
de que o detector nao e cego.

---

## 3. Invocadores exactos e resultados (colados, nao resumidos)

```
python H:\sotto\_main\caption-dup-repro.py
  ficheiros=10  linhas=2077  iguais=79  crescimento=0  sobreposicao=6
  par minimo (sobreposicao): 2 linhas; tirar qualquer uma -> 0 pares (minimo provado)
  fase 3: 6/6 ok, linhas escritas=3 esperadas=3, PASS
  fase 4: com o mutante: replay FICOU VERMELHO; linhas escritas com o mutante=4; NEG-ARM PASS
  fase 5: crescimento 3 -> ['O radio Segunda Os']; duas vivas ficam duas; mutante -> VERMELHO
  CAPTION-DUP-VERDICT PASS  fases=5  falharam=0  saltadas=0
  rc=0
```

```
python _main\agents-md-pins-oracle.py
  sotto: 111454 B    true
  sotto: 1499 CRLF   true
  AGENTS-PINS PASS -- 2 pin(s) checked live, 0 failure(s)   rc=0
python _main\panel-flash-contradiction-oracle.py            rc=0
python _main\youtube-window-oracle.py                       rc=0
AST OK em _main\caption-dup-repro.py e app\webview\youtube_window.py
```

Pin novo da bateria: **111454 B, 1499 CRLF, 0 bare LF**, sha256
`204A93EE3D8B1DACD5EF93483721CA8458545941978D7D89D97C3F4464BB76E5` (era 110748 B / 1491 CRLF).

### Controlos

- **Positivo:** o laco inteiro em `rc=0`, com o veredicto `CAPTION-DUP-VERDICT PASS`.
- **Negativo:** fase 4 (mutante) tem de ficar vermelha, e o passo da bateria fica vermelho se ela
  ficar verde — o detector e auto-verificavel, nao ha um `red-as-expected-*` separado por isso.

---

## 4. Decisoes que valem registo

1. **A skill vive no repo, nao no perfil do utilizador.** O runtime carrega skills de
   `C:\Users\Administrador\.config\opencode\skills` — **fora** da fronteira de escrita de uma lane. A
   camada do repo vive em `.opencode/skills/postmortem-sotto/SKILL.md` e o runtime **descobriu-a**
   (apareceu na lista de skills no momento da escrita). *(A primeira versao chamava-se `postmortem` e
   reescrevia a canonica; foi retirada na ronda de frota — ver §8.)*
2. **O gatilho do postmortem e o estado, nao a gravidade.** Contido/resolvido ou quase-acidente: sim.
   Bug aberto: nao — e bug-hunt. Escrito no AGENTS.md com essa frase.
3. **A mecanica de debug e obrigatoria mas proporcional.** Sete passos para o defeito que doi; para um
   typo, nenhum. A proporcionalidade esta na primeira linha da seccao, nao numa nota de rodape.
4. **O "517" saiu.** Era um numero sem relacao declarada. Ficam os tres numeros de hoje, cada um com a
   sua relacao e o instrumento que os mediu. O repo diz: *"o grep deu ZERO e uma afirmacao com prazo de
   validade"* — o mesmo vale para um numero herdado.
5. **O instrumento nao escreve no artefacto que mede.** A primeira versao deixava
   `HISTORY_APPEND path="I:\\cc-tmp\\..."` no `_main/webview-run.log` a cada corrida; passou a silenciar
   o `log` do shell durante o replay (`_silent_log`).

---

## 5. Rollback

**Nao usar `git checkout -- <ficheiro>`**: esta arvore tem 700 caminhos sujos de outras lanes, e o
`checkout` apagaria trabalho que nao e meu. O rollback e cirurgico:

| artefacto | como reverter |
|---|---|
| `.opencode/skills/postmortem-sotto/` | apagar a pasta (nova) |
| `_main/caption-dup-repro.py` | apagar o ficheiro (novo) |
| `_main/_audit-verify-all.cmd` | apagar as 8 linhas a seguir ao bloco `lane-screen-gate` (linhas 302-309) |
| `AGENTS.md` | apagar §MECANICA, §POSTMORTEM e o bullet da duplicacao; repor o pin antigo (110748 B / 1491 CRLF / `71B6A09...`), que o portao do pin exige |
| `app/webview/youtube_window.py` | so o docstring do `collapse_growth`; o comportamento nao mudou |

---

## 6. Nao verificado / por medir

- **O passo novo nao correu dentro de uma bateria completa.** Esta provado que corre (rc=0) e que o pin
  bate certo, mas o `BATTERY-VERDICT` continua a ser o ultimo medido (`RED - 6`, anterior a estas
  mudancas). **`wired, not yet exercised inside a full run`** — e isso nao e `verified`.
- **As 79 linhas antigas ficam no ficheiro.** A guarda e para a frente; o instrumento agora di-lo em
  voz alta para ninguem ler o numero como "a cura falhou".
- **`code-health` continua vermelho** (bytes/linhas do `sotto_webview.py`, decisao do dono sobre o
  `--update`) e **`exception-hygiene`** continua vermelho pelo `worker/sotto_worker.py` de outra lane.
- **O `collapse_growth` nao cura a sobreposicao** (as 6 da janela deslizante). E uma quarta relacao, com
  guarda propria por fazer: **declarada, nao corrigida**.
- O exemplo de minimizacao de hoje caiu num par japones (`何だお前.` / `お前.`) porque e o primeiro do
  pior ficheiro — o instrumento nao escolhe idioma, e isso e o correcto.

---

## 7. SELF-AUDIT (onde eu posso estar errado)

1. **Qual das tres relacoes o dono viu nao esta provado.** Ele disse *"coisa duplicada"* (igualdade: 79
   no disco, curada pela fase 3) e *"a frase era maior, foi sumindo"* (crescimento: curado no painel,
   exercitado na fase 5 com o seu proprio mutante). O que **nao** esta curado sao as **6 sobreposicoes**
   — a janela deslizante em que uma linha comeca onde a outra acabou. E possivel que ele tenha visto uma
   dessas, e nesse caso nenhuma das duas guardas a apanha. **Declarado com o numero: 6 de 2077.**
2. **O pior ficheiro (`2026-10-06\09.md`, 60 pares) e japones.** A cura foi validada com texto ingles;
   nada garante que a comparacao se comporte igual com CJK sem espacos — a igualdade byte-a-byte sim, a
   sobreposicao por prefixo nao foi exercitada em CJK.
3. **`_silent_log` esconde o log durante o replay.** Se o `history_append` real falhasse de uma forma que
   so aparece no log, o instrumento nao o mostraria — mostra-o pelo `entrou/esperado` e pela contagem no
   ficheiro, mas e uma perda de sinal deliberada.
4. **A skill e um documento; nao ha portao que obrigue a usa-la.** O AGENTS.md diz *quando* e que nao;
   nada mede se uma lane escreveu postmortem quando devia. Um portao para isso exigiria um registo de
   incidentes que o repo nao tem — **declarado, nao construido** (seria cerimonia sem dados).
5. **O passo na bateria depende de `python` no PATH e de importar o shell** (~2-4 s). Numa maquina sem
   as dependencias do shell, o passo falha por infraestrutura e nao por defeito — e isso parecer-se-ia
   com um vermelho verdadeiro.

---

## 8. Ronda de coordenacao de frota (2026-10-24, steer do manager)

### O que o steer mudou

A skill canonica passou a ser `I:\!manager\.agents\skills\postmortem\SKILL.md`. A minha versao anterior
reescrevia-a — exactamente o **duplicado** que o steer proibe. Foi **retirada** (o runtime confirmou:
`postmortem` deixou de estar disponivel) e substituida por `postmortem-sotto`, que carrega so as decisoes
deste repo: o tracker existente, o fecho mecanico e as recusas.

### Gate central, medido com o proprio instrumento

```
python I:\!manager\tools\performance-gate.py status
performance-gate: RED
  reasons: commit-pct=92.6 >= red 90.0
  policy:  heavy_allowed=False  amber_light_allowed=False  amber_light_ttl_max=300.0s
  leases:  heavy=0/1  light=0/3                                  rc=1
```

Lido isto, **nao** larguei build, bateria, indexacao, benchmark nem campanha de mutacao. O trabalho
desta ronda foi codigo, docs e diff estatico.

### Instrumento novo: `_main/closure-evidence-replay.py`

O que se mediu **antes** de o construir: o tracker tem **31 seccoes e 63 evidencias**, todas
`status: closed`, e o portao dele (`_main/complaints-closure-gate.py`) **nao executa nada** — nao tem
`subprocess` nem `--run`. Portanto `closed` e uma afirmacao de ontem, não uma medicao de hoje.

Antes ainda, uma hipotese foi falsificada: **0 de 63** evidencias citam ficheiro inexistente, logo o
problema não era "fechado sobre um cadáver" — era a ausência de re-execução.

O instrumento reusa as **mesmas expressoes** do portao (nada de esquema novo) e re-executa uma seccao,
comparando `rc` e marcador com o que a seccao afirma.

| comando | hoje |
|---|---|
| `python _main\closure-evidence-replay.py` (lista) | 31 seccoes, 63 evidencias, **4 recusadas por politica**, 59 re-executaveis, `rc=0` |
| `python _main\closure-evidence-replay.py --self` | **6/6**, `SELF PASS`, `rc=0` |
| `--run --section R<n>` / `--neg-arm` | **NAO exercitado** — executam evidencia de outro dono, e o gate esta RED |

A prova de hoje e a da **comparacao** (muta-se a afirmacao, nao o sistema), nao a de ponta a ponta — e o
instrumento di-lo na propria saida, para ninguem ler `SELF PASS` como "o tracker esta correcto".

### Politica de seguranca do instrumento

`SKIPPED (policy)` para comandos que possam largar a app, agendar tarefa ou injectar input sintetico
(`--show`, `run.cmd`, `schtasks`, `keybd_event`, `keepalive`, `SOTTO_LANE_LAUNCH`), e para
interpretadores que nao conhece (`git` caiu aqui: 4 evidencias). Um skip **nao** conta como aprovado.

### TODO aberto, com o log de mudancas

`{"evidence":0,"event":"todo-add:fleet-coordination+postmortem-canonical","at":"2026-10-24T09:53:52Z"}`
em `.opencode/goal-log.jsonl` (append-only, o formato que ja existia — nao inventei um segundo).

1. **Ligar `closure-evidence-replay --self` a bateria** quando o gate estiver verde. Nao o fiz agora de
   proposito: acrescentar um passo que nao posso validar numa corrida completa seria um portao nao
   exercitado, que e a coisa que a bateria existe para nao ter.
2. **Correr `--run` por seccao** (uma de cada vez, com o lease) para medir drift real do tracker.
3. **As 6 sobreposicoes** continuam sem cura (herdado da ronda anterior).

### Regra de frota

`AGENTS.md`, HARD RULES: antes de build/bateria completa/indexacao/benchmark/mutacao, consultar
`performance-gate.py` e obter o lease `heavy` **exclusivo**; com **RED**, so codigo/docs/diff estatico;
os governadores locais sao sinal **extra** e nunca autorizam trabalho pesado concorrente por fora do
gate central; `unknown` nao e `green`.

---

## 9. Compactar o prompt auto-carregado (2026-10-24, steer do manager)

O `AGENTS.md` e carregado em todas as sessoes, logo o detalhe nao pertence la. Medi antes/depois e
**movi, nao apaguei**:

| bloco | antes | depois | onde passou a viver o detalhe |
|---|---|---|---|
| §MECANICA (7 passos) | 25 linhas | **8** | skill `postmortem-sotto` §Mecânica de debug |
| §POSTMORTEM (gatilho + tracker + fecho) | 18 linhas | **7** | skill `postmortem-sotto` |
| `AGENTS.md` inteiro | 20125 B / 292 linhas | **18205 B / 263 linhas** | — |

O que ficou no prompt e um **ponteiro obrigatorio**: quando invocar a skill, e que com o bug **ACTIVO**
se fica no MODO BUG-HUNT. A regra "sem culpa: culpa o portao que faltava" nao desapareceu — mudou-se para
a skill, com o verbatim do dono (*"faz gates ou agents.md"*).

### Dois defeitos meus, apanhados ao correr os instrumentos

1. **`--explain` contava "sem caminho" como problema** (4 evidencias: `git`, `nvidia-smi`). Falso
   positivo: uma evidencia que nao cita ficheiro nao esta errada. Passaram a ser duas contagens
   separadas, e o veredicto so depende de `ficheiro ausente`.
2. **`lane-screen-gate` ficou VERMELHO por minha causa**: os literais da *lista de recusas* do
   instrumento parecem-lhe um **uso** de input sintetico. A saida errada seria meter o ficheiro no
   `lane-screen-baseline.json` — isso e declarar divida que nao tenho, e a baseline **nao pode crescer**.
   A certa foi a politica passar a **dados** (`_main/closure-evidence-policy.json`, 589 B), para o
   detector manter a distincao entre *proibir* e *usar*.

### Fail-closed, medido (e o ficheiro foi reposto)

Com a politica ausente: `evidencias=63  recusadas-por-politica=63  re-executaveis=0` — sem politica o
instrumento **nao corre nada**, e diz porquê. Reposto: 4 recusas (`nvidia-smi`, `git` x3), 59
re-executaveis.

### Estado verificado desta ronda

| comando | resultado |
|---|---|
| `python _main\closure-evidence-replay.py` | 63 evidencias, 4 recusadas, 59 re-executaveis, `rc=0` |
| `... --explain` | `EXPLAIN-VERDICT OK`, 0 ausentes, 4 sem caminho, `rc=0` |
| `... --self` | 6/6, `SELF PASS`, `rc=0` |
| `python _main\lane-screen-gate.py` | `VERDICT: PASS`, `rc=0` |
| `python _main\agents-md-pins-oracle.py` | `rc=0` |
| `python _main\panel-flash-contradiction-oracle.py` | `rc=0` |
| `I:\!manager\tools\performance-gate.py status` | **RED**, `commit-pct=92.8 >= 90`, `rc=1` |

Continua **nao exercitado**: `--run --section` e `--neg-arm` — executam evidencia de outro dono, e o gate
central esta RED.
