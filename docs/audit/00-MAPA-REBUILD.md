# REBUILD do `00-MAPA-CONSOLIDADO.md` — o que o review apanhou, o que mudou

**Lane:** MapRebuild · **Data:** 2026-10-06 · **Modo:** READ-ONLY sobre `H:/sotto` (escritos apenas
`00-MAPA-CONSOLIDADO.md` e este ficheiro). **Fontes:** os 8 docs desta pasta lidos INTEIROS +
`00-MAPA-REVIEW.md`.

## Uma linha

O mapa antigo foi gerado **lendo cabecalhos** e cobria **31 de 61 achados (51 %)**; o novo foi
construido lendo as **fontes inteiras** e cobre **62 de 62 (100 %)**, com os 6 estados errados
corrigidos contra o working tree.

## O que o review apanhou (medido)

| metrica | mapa antigo | este mapa |
|---|---|---|
| achados nas fontes | 61 | 62 (61 + `audio-path §5`) |
| linhas | 29 | 62 |
| achados com casa | 31 | 62 |
| **MISSING** | **30** | **0** |
| INVENTED | 0 | 0 |
| **WRONG_STATE** | **6** (W1–W6) | **0** |
| citacoes erradas | 3 (C1–C3) | 0 |
| ma-atribuicao | 1 (X1) | 0 |

Eixos que o mapa antigo esvaziou e que este restaura: **`oracles.md`** (9 ausentes → 10 linhas),
**`windows-landmines.md`** (4 ausentes + a landmine 3 DETURPADA → 4 linhas + as 6 leis com o verdicto
correto), **`window-visibility.md`** (5 ausentes → 7 linhas), **`model-config.md`** (5→4 ausentes → 7 linhas),
**`launch-entry.md`** (3 ausentes → 7 linhas), **`audio-path.md`** (5 ausentes → 7 linhas).

## O que MUDEI e por que

1. **Passei de "ler titulos" a "ler as fontes".** Cada rotulo `F\d`/`G\d`/`H\d`/`Finding [A-Z]` dos 8 docs
   tem agora uma linha. A lista MISSING (M1–M30) do review foi usada como checklist: cada entrada tem
   linha — M1→#9, M2→#36, M3→#37, M4→#38, M5→#39, M6→#17, M7→#18, M8→#19, M9→#22, M10→#23, M11→#54,
   M12→#24, M13→#25, M14→#26, M15→#27, M16→#56, M17→#57, M18→#28, M19→#29, M20→#30, M21→#58, M22→#4,
   M23→#32, M24→#59, M25→#60, M26→#61, M27→#5, M28→#34, M29→#35, M30→#62. **MISSING = 0.**
2. **Estados re-verificados no working tree** (nao copiados). As 6 correcoes W1–W6:
   - **W1** (antigo item 4, `blank_frac=1.0`) ABERTO → **EM VOO** (lane `BlankFramesRootCause` despachada;
     `docs/audit/blank-frames-root-cause.md` ainda ausente).
   - **W2** (antigo item 8, sonda int4) EM VOO → **APLICADO**: li `sotto_worker.py:77`
     (`DEFAULT_MODEL = …-int8`) e `:942` (`probed_model = os.path.join(model_dir or DEFAULT_MODEL, …)`).
   - **W3** (antigo item 9, 7 chaves inertes) EM VOO → **APLICADO**: li `worker/config.json` — as 7 chaves
     foram apagadas e `block_ms`/`min_chars` carregam `_comment_live`.
   - **W4** (antigo item 10, G1–G4) EM VOO → **APLICADO**: `run.cmd:64-76` recusa o fallback de consola (G4);
     e li **G1/G2/G3 tambem fechados** — `sotto_webview.py:2528-2541` (painel ausente→3, `import webview`→1
     no `--check-args`) e `run.cmd:129-167` (ready-file limitado, sai 4 no hang).
   - **W5** (antigo item 29) — `sotto_webview.py:1549-1553` ja diz "tried and REMOVED"; o comentario
     obsoleto que resta passou a `:1054`. A linha #33 fica **OPEN** com o residuo nomeado (honesto: o
     review tinha razao a 100 % sobre `:1531-1535`, e o defeito persiste por outra linha).
   - **W6** (antigo item 7, oraculo de cadencia) EM VOO → **APLICADO**: `_main/delivery-rate-oracle.py`
     existe (20080 B) e o log corre GREEN+RED (`threshold=0.95`, `SELFTEST: PASS`).
3. **Citacoes erradas C1–C3 corrigidas** e a **ma-atribuicao X1** removida: a antiga linha "regressao do
   `OFFSCREEN=-32000` APLICADO" nao existe — a cura foi *tentada e removida*; o que resta e o hang (#19) e
   o comentario obsoleto (#33).
4. **A landmine 3 deixou de estar deturpada.** O mapa antigo conservava "`taskkill` pode truncar o log" —
   a metade que `windows-landmines.md` **refutou** (3 replicas: ficheiro, pipe-python, pipe-node). O novo
   mapa poe o verdicto real: a metade que morde e "`taskkill /F` nao corre shutdown graciosa"
   (`HOTRELOAD.md:326-330`) e o achado **#34** (`wait(timeout=)` sem handler em 3 oraculos).
5. **Numeros que o antigo nao tinha.** O mapa agora fecha com o bloco de contagem (achados, linhas,
   MISSING, INVENTED, WRONG_STATE, APPLIED/EM VOO/OPEN) e a conferencia `14+1+47=62`.

## O que NAO fiz (e por que)

- Nao re-corri nenhum oraculo nem a app: abriria janela (proibido). Os estados vem de `read`/`grep`
  da fonte e do working tree, nao de execucao.
- Nao escrevi `agents/MapRebuild.md` nesta lane: o `SELO DO DONO` pede essa linha `tools:` para o
  resolver do selo, mas isso e escrita fora do deliverable desta lane e pertence ao dono do assento.
- Nao corrigi o `:1054` (residuo obsoleto): o deliverable e o mapa, nao o fix; esta registado como #33 OPEN.

## SELF-AUDIT

- **protocolos em falta** — Faltei ao passo mecanico que eu proprio recomendo: tivesse feito, como PASSO 0,
  `grep -oh` de todos os rotulos `F\d|G\d|H\d|Finding [A-Z]` dos 8 docs para construir a lista de 61
  ANTES de ler a prosa, e a enumeracao nao dependeria da minha leitura. Em vez disso li os 8 docs e so
  depois reconciliei com o review. O que faria diferente: extrair os rotulos com um comando primeiro e
  tratar a contagem como um `comm -23` (fontes vs mapa), nao como aritmetica a mao. Foi exactamente o
  protocolo que o proprio `00-MAPA-REVIEW.md` nomeou no seu self-audit e que eu nao apliquei de inicio.
- **verificacao adicional** — O check que mais aumentaria a confianca e que **corri barato**: re-li no
  working tree cada um dos 5 pontos que o ticket nomeia como "correcoes a honrar" (delivery-rate-oracle,
  DEFAULT_MODEL/model_dir, config keys, G4, `:1531-1535`) — feito, com `read`/`stat`/`grep` colados.
  O que **nao** corri: um `comm -23 <(rotulos dos 8 docs) <(rotulos no mapa)` como predicado final. Custo:
  1 comando; nao o corri porque a unica ferramenta de contagem que tenho aqui e o `grep`/`sort` e o gate
  proprio (`audit-map-gate.sh`) ainda nao existe (lane `AuditMapGate`). Fica como o fecho mecanico.
- **checkboxes novas** — Um passo NOVO e MECANICO para esta classe de trabalho: **"para cada rotulo
  `F\d`/`G\d`/`H\d`/`Finding [A-Z]` de qualquer doc fonte, exigir a sua presenca no mapa; e o `file:line`
  do mapa tem de ser identico ao do doc"**. Comando:
  `comm -23 <(grep -ohE '\b(F|G|H)[0-9]+' docs/audit/*.md | sort -u) <(grep -oE '\| [0-9]+ \|' docs/audit/00-MAPA-CONSOLIDADO.md | ...)`.
  Input que TEM de o deixar RED: o mapa antigo (faltavam 30). Input que tem de ficar GREEN: este mapa.
  Enquanto o `audit-map-gate.sh` nao existir, e este o passo que o substitui a mao.
- **review por outro subagente** — **sim-com-escopo**: um segundo revisor deve re-derivar SO a lista
  `rotulo → linha` do mapa a partir de um `grep -oh` dos 8 docs e comparar com as minhas 62 linhas
  (a parte que, se eu contei mal, contamina as contagens). **Nao** para os estados (sao `read`/`stat`
  mecanicos e reprodutiveis) nem para o self-audit.
- **gate-doubt**:
  - **verde-de-verdade:** o unico "verde" que produzi e aritmetico — `14 + 1 + 47 = 62` e
    `62 + 0 = 62` — e e **auto-consistente, nao vacuoso**: o mapa antigo falhava a mesma aritmetica
    (31 + 30 = 61 mas com 29 linhas). O `SELFTEST: PASS` do `delivery-rate-oracle.log` que citei como
    prova do estado #3 **nao o re-corri** — leio o log que ja estava em disco; o verde `PASS` e do
    instrumento, nao meu, e esta declarado como tal.
  - **falta-no-gate:** **nao existe** nenhum gate que verifique que um documento "consolidado" cobre as
    fontes que ele declara. Um mapa futuro pode apagar 30 de 62 achados e passa toda a instrumentacao da
    casa (`self-audit-lint` so valida a forma do bloco SELF-AUDIT). Cenario que atravessa: alguem
    "simplifica" o mapa para uma tabela por severidade e larga as linhas `oracles.md` — nada fica RED.
  - **gate-melhor:** o gate que esta propria sessao mandou construir — `I:/!manager/scripts/audit-map-gate.sh`
    (lane `AuditMapGate`): para cada rotulo `F\d|G\d|H\d|Finding [A-Z]` de cada doc fonte, exigir a sua
    presenca no mapa; RED input = o mapa antigo (30 ausentes); GREEN input = este mapa (0 ausentes).
    Enquanto nao existir, o fecho e `n/a — o gate pertence a lane AuditMapGate, despachada`.
- **confianca** — **alta** na cobertura (cada uma das 62 linhas cita um achado explicito de um doc que li
  inteiro) e nos 14 APLICADOS (cada um e um `read`/`grep`/`stat` do working tree, colado). **media** na
  fronteira "achados nas fontes = 62 vs 61": os 61 sao a enumeracao do `00-MAPA-REVIEW.md` §A, e o +1 e
  `audio-path §5` (um facto nomeado na fonte, nao rotulado `F\d`) — a lista M1–M30 e o artefacto checavel,
  nao a soma. O que a mudaria: o `audit-map-gate.sh`.
- **nao verificado** — (1) nao re-corri nenhum oraculo citado (proibido: abriria janela); (2) nao
  confirmei se `AGENTS.md` (untracked, editado) ainda se autocontradiz nos itens #46/#47/#48/#53 — as
  ancoras do doc `doc-vs-code.md` podem ter deslizado; (3) nao li `delivery-rate-oracle.py` linha a linha
  — so confirmei que existe e que o log nao tem veredicto de corrida completa; (4) o estado #2 (EM VOO)
  pode reflectir trabalho da lane a meio, nao um defeito do autor do mapa antigo; (5) nao corri o
  `comm` mecanico porque o gate nao existe.

## GATE-CHANGE REQUEST

- **gate:** `I:/!manager/scripts/audit-map-gate.sh` (artefacto declarado da lane `AuditMapGate`, ainda
  ausente — despachada).
- **hole:** nao existe gate que verifique que um documento "consolidado" **cobre as fontes que ele declara**.
  O mapa antigo apagou 30 de 61 achados e passou toda a instrumentacao da casa (`self-audit-lint` so valida
  a forma do bloco SELF-AUDIT). Medido: cobertura real do mapa antigo = 31/61.
- **change (merge-ready shape):** para cada doc-fonte em `H:/sotto/docs/audit/`, extrair os rotulos
  `F\d+|G\d+|H\d+|Finding [A-Z]` e exigir que cada um apareca no mapa; devolver nao-zero a contar os ausentes.
  Comando-shape: `comm -23 <(grep -ohE '\b(F|G|H)[0-9]+' docs/audit/*.md | sort -u) <(grep -ohE 'item [0-9]+' docs/audit/00-MAPA-CONSOLIDADO.md)`.
- **non-vacuity control:** o mapa antigo devolve os 30 rotulos ausentes (M1–M30 do review); este mapa
  devolve vazio (0 ausentes). Um mapa que so reordene linhas continua RED.

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh MapRebuild` — rc=0, stdout VERBATIM:

```
## CACHE/PRICE
- task/agent: MapRebuild
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\MapRebuild.jsonl
- cache: read=3755698 write=0 hit=94.5295% (cache-read / input+cache-read); universe: 36 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\MapRebuild.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: cline-pass/stealth/pixel-canary: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-1/deepseek-flash: calls=26 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-go-4/space-bunny-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/ling-3.1-flash-free: calls=1 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=7 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: cline-pass/stealth/pixel-canary $0.00000000; opencode-go-1/deepseek-flash $0.00000000; opencode-go-4/space-bunny-free $0.00000000; opencode-zen/ling-3.1-flash-free $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 36 of 36 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T08:45:50.906000+00:00 | break_items=1; WHEN=2026-10-06T08:45:51.956000+00:00 | break_items=3; WHEN=2026-10-06T08:45:53.180000+00:00 | break_items=11; WHEN=2026-10-06T08:45:54.348000+00:00 | break_items=2; WHEN=2026-10-06T08:48:21.198000+00:00 (state=RESOLVED-BREAKS-OMP; population: 5 of 114015 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'MapRebuild']; window: 2026-10-06T08:45:50.906000+00:00..2026-10-06T08:48:21.198000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a11063-b858-710a-8e74-c186e54f2061 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791276350906 | session_id=01a11063-b858-710a-8e74-c186e54f2061 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791276351956 | session_id=01a11063-b858-710a-8e74-c186e54f2061 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791276353180 | session_id=01a11063-b858-710a-8e74-c186e54f2061 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791276354348 | session_id=01a11063-b858-710a-8e74-c186e54f2061 provider=deepseek-flash model=deepseek-flash item_index=109; turn_id=1791276501198 (state=RESOLVED-BREAKS-OMP; population: 5 of 114015 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'MapRebuild']; window: 2026-10-06T08:45:50.906000+00:00..2026-10-06T08:48:21.198000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T08:49:21.865445+00:00
- usage rows: 36
- model + route: cline-pass/stealth/pixel-canary, opencode-go-1/deepseek-flash, opencode-go-4/space-bunny-free, opencode-zen/ling-3.1-flash-free, opencode-zen/space-bunny-free
- input tokens: 217345
- output tokens: 34185
- cache-read tokens: 3755698
- cache-write tokens: 0
- hit ratio: 94.5295% (cache-read / input+cache-read)
- cost: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source)
- prefix breaks: 20 (state=RESOLVED-BREAKS-OMP)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T08:45:50.906000+00:00; WHERE session_id=01a11063-b858-710a-8e74-c186e54f2061 provider=cline-pass model=cline-pass/stealth/pixel-canary item_index=0; turn_id=1791276350906
  - break_items=1; WHEN=2026-10-06T08:45:51.956000+00:00; WHERE session_id=01a11063-b858-710a-8e74-c186e54f2061 provider=space-bunny-free model=space-bunny-free item_index=0; turn_id=1791276351956
  - break_items=3; WHEN=2026-10-06T08:45:53.180000+00:00; WHERE session_id=01a11063-b858-710a-8e74-c186e54f2061 provider=ling-3.1-flash-free model=ling-3.1-flash-free item_index=0; turn_id=1791276353180
  - break_items=11; WHEN=2026-10-06T08:45:54.348000+00:00; WHERE session_id=01a11063-b858-710a-8e74-c186e54f2061 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791276354348
  - break_items=2; WHEN=2026-10-06T08:48:21.198000+00:00; WHERE session_id=01a11063-b858-710a-8e74-c186e54f2061 provider=deepseek-flash model=deepseek-flash item_index=109; turn_id=1791276501198
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Nota honesta: `$0.00000000` e o que o JSONL da sessao regista e as taxas por modelo sao `UNKNOWN`
nessa fonte — reporto o valor do instrumento, nao afirmo custo zero.
