# REVISÃO INDEPENDENTE do `00-MAPA-CONSOLIDADO.md`

**Lane:** AuditMapReview · **Data:** 2026-10-06 · **Modo:** READ-ONLY (só este ficheiro escrito).
**Alvo revisto:** `H:/sotto/docs/audit/00-MAPA-CONSOLIDADO.md` (4412 B).
**Fontes cruzadas:** os 8 docs da mesma pasta — `audio-path.md`, `shell-bridge.md`, `doc-vs-code.md`,
`launch-entry.md`, `model-config.md`, `oracles.md`, `window-visibility.md`, `windows-landmines.md`.
**Estado vivo lido (só para a pergunta (c)):** `H:/sotto` @ HEAD `3e90f92` + working tree; lane ledger
`I:/!manager/state/progress/registro-em-voo.jsonl`+`lane-ledger.jsonl`. Nada em `H:/sotto` foi editado.

---

## Veredicto

**O mapa NÃO é fielmente completo: cobre 31 de 61 achados (51 %) e DROPA 30.** Está correto onde está
(as secções de shell-bridge e doc-vs-code estão 10/10), mas três eixos inteiros foram esvaziados —
**oracles.md (9 de 10 achados ausentes), windows-landmines.md (4 de 4) e window-visibility.md (5 de 7)**
— e a secção "Landmines" foi reproposta como "leis de medição", o que apaga os *bugs* que o doc
`windows-landmines.md` identifica (`F1`–`F4`) e ainda **deturpa** a landmine 3 (ver D-LM3).
Além disso há **6 estados errados** face ao working tree (itens 4, 7, 8, 9, 10, 29) e **3 citações
`file:line` erradas** (itens 1, 3, 29). **Nenhum achado verdadeiramente inventado (0)**, mas o item 2
é uma má-atribuição.

---

## A. Cobertura por documento (contagem verificável)

| doc fonte | achados enumerados | com casa no mapa | MISSING |
|---|---|---|---|
| `audio-path.md` | 6 (F1–F6) | 1 (item 1) (+§5 = item 4) | 5 |
| `shell-bridge.md` | 10 (F1–F10) | 10 (itens 3,5,6,11–17) | 0 |
| `doc-vs-code.md` | 10 (F1–F10) | 10 (itens 18–27) | 0 |
| `launch-entry.md` | 7 (G1–G4 + 3 notas) | 4 (item 10 agrupa G1–G4) | 3 |
| `model-config.md` | 7 (§3, §6.1, §6.3.1, §6.3.2, §6.3.3, §6.4, §6.5) | 2 (itens 8, 9) | 5 → 4 distintos |
| `oracles.md` | 10 (§3 + H1–H6 + Finding A/C/D) | 1 (item 7) | 9 |
| `window-visibility.md` | 7 (F1–F7) | 2 (itens 28, 29) | 5 |
| `windows-landmines.md` | 4 (F1–F4) + 6 leis | 0 (só 4 leis, item dif. deturpada) | 4 |
| **TOTAL** | **61** | **31** | **30** |

Nota de método: o mapa tem **29 linhas** para **31 achados** porque duas linhas são many-to-one
(item 8 = `model-config §6.3.1` **e** `§6.5`; item 10 = `launch-entry G1,G2,G3,G4`). Essa compressão
esconde 4 lacunas atrás de uma linha — por isso a contagem "achados no mapa" é ambígua por construção.

---

## B. Divergências (uma linha por divergência)

### B1 — MISSING (no doc, ausente do mapa)

| # | fonte | achado ausente (file:line do doc) | porquê importa |
|---|---|---|---|
| M1 | audio-path | **F2** `flags` lido e descartado → overflow invisível (`wasapi_loopback.py:475/477`) | é a razão de a perda ser silenciosa; sem ele o item 1 do mapa fica sem o "porquê" de ser invisível |
| M2 | audio-path | **F3** fallback de 100 ms é código morto (`wasapi_loopback.py:416,418-425`) | o buffer que o poll precisa é exactamente o inalcançável |
| M3 | audio-path | **F4** `CoInitializeEx` rejeita `S_FALSE` (`wasapi_loopback.py:187-189`) | footgun latente para 2 taps na mesma thread |
| M4 | audio-path | **F5** `tick` lido como `final` (`sotto_worker.py:1284-1301`) | regra de contabilidade; explica o "64 %" falso do brief |
| M5 | audio-path | **F6** `np.concatenate` por emit (`wasapi_loopback.py:492-496`) | menor, mas o doc nomeia-o |
| M6 | launch-entry | **`run.cmd --check-args` é flag aceite → arranca e devolve 0 sem abrir nada** (nota "Not a gap") | 2ª via de "nada aconteceu = sucesso" |
| M7 | launch-entry | **§3.4.2 blindness do `ready`**: o `ready` regex lê um stream onde o app nunca escreve (log na `--log`, não no PTY) — "measured" | o item 10 não o cobre; é medição, não hipótese |
| M8 | launch-entry | **§4 terceira causa do hang `STAGING_LOADED`, não nomeada** | o mapa atribui o hang ao `OFFSCREEN` (item 2), mas o doc diz que a causa OFFSCREEN foi removida e há uma 3ª por nomear |
| M9 | model-config | **§6.3.2** `use_vad` default do código é `False` vs ficheiro `true` vs README "on" (`sotto_worker.py:1152`→hoje `:1185`) | apagar a chave desliga VAD em silêncio |
| M10 | model-config | **§6.3.3** `PREFERRED_DEVICES = ()` vs README que o apresenta populado (`sotto_worker.py:94`) | drift doc-vs-código |
| M11 | model-config | **§6.4** AGENTS/README listam 5 chaves; o ficheiro tem 13 | o leitor não distingue chave inerte de viva |
| M12 | model-config | **§3** `lang_id` morto na vida do ficheiro (histórico) | achado com defeito documentado |
| M13 | oracles | **H1** `--selftest` não afirma qualidade do output (`sotto_worker.py:986-999`) | "verde com word-salad" 2 dias |
| M14 | oracles | **H2** `queue_drops` nunca afirmado | áudio perdido tap→ASR invisível |
| M15 | oracles | **H3** ARM A precisa de 1 caption (`panel-exit3-oracle.py:999`) | capturador a 35 % pinta LIVE |
| M16 | oracles | **H4** `model-spec-oracle` sem braço negativo | detector de drift, não oráculo |
| M17 | oracles | **H5** `_oss_oracle` sem braço negativo | verde nunca mostrado capaz de falhar |
| M18 | oracles | **H6 = Finding B** `focus_stolen=true` e rc=0 | roubo de foco é um verde |
| M19 | oracles | **Finding A** `panel-exit3-oracle.log` STALE (mtime 03:54 < fonte 04:40) | receita não descreve os braços actuais |
| M20 | oracles | **Finding C** `run-cmd-exit-oracle` está RED no conjunct do census | oráculo RED hoje, não no mapa |
| M21 | oracles | **Finding D** braço `bogus` do `runcmd-entry-driver.py` sem receita | braço existe em código, corrida sem prova |
| M22 | window-visibility | **F1** a janela aparece sozinha ≤63 ms em cada arranque (`edgechromium.py:348`) | é o *achado central* do doc e não está no mapa |
| M23 | window-visibility | **F3** o census não é panel-specific (alarme em `cmd`/`dwm`/`python`) | o item 28 cobre o predicado, não a atribuição |
| M24 | window-visibility | **F5** `_move_into_place` morto (`:1083` sem caller) + painel vivo a `x=-10000` | build a correr ≠ ficheiro auditado |
| M25 | window-visibility | **F6** `_on_navigation_start` early-return em `self.visible` (`:1549`) | "mostrado uma vez ⇒ nunca mais auto-escondido" |
| M26 | window-visibility | **F7** promessa do `run.cmd:6` "start hidden" vs flash real | wrapper promete o que o shell não cumpre |
| M27 | windows-landmines | **F1** `_main/_probe/console-census.py:106` — `CREATE_NO_WINDOW\|DETACHED` cega o canal; achado de maior confiança do doc | bug real, não lei |
| M28 | windows-landmines | **F2** `wait(timeout=)` sem handler em 3 oráculos (`device-silence-oracle.py:71`, `panel-exit3-oracle.py:160`, `panel-startup-visibility-oracle.py:386`) | órfãos em timeout |
| M29 | windows-landmines | **F3** `_main/run-live-hidden.py:71` idem + `DETACHED_PROCESS` morto (`:25`) | idem |
| M30 | windows-landmines | **F4** `_main/_run-hidden.py:24` timeout em `electron.exe` pode não ser tecto | [INFERENCE] do doc |

### B2 — Citação `file:line` errada (o achado está lá; o endereço não)

| id | mapa diz | fonte diz | evidência |
|---|---|---|---|
| C1 | item 1: `worker/wasapi_loopback.py:475` | `wasapi_loopback.py:463` (é a linha do `period`; `:475`/:477` são a linha dos `flags`, que é outra F) | mapa: "pump do WASAPI a 25 ms > anel de 22 ms" = F1 (:463); :475 é F2 |
| C2 | item 3: `sotto_webview.py:1390/1395` | `sotto_webview.py:1409-1421`, `:1415`/`:1420` | `shell-bridge.md` F1; o todo da sala também diz `:1415 e :1420`. `1390/1395` não consta de nenhum dos 8 docs |
| C3 | item 29: `sotto_webview.py:1531-1535` | idem no doc, mas o working tree mudou de conteúdo nessas linhas (ver W5) | `read` de `sotto_webview.py:1538-1557` |

### B3 — Má-atribuição (o item existe, mas diz uma coisa que a fonte não diz)

| id | mapa diz | fonte diz | evidência |
|---|---|---|---|
| X1 | item 2 = "**regressao** do `OFFSCREEN=-32000`: prende a navegacao, o worker nunca arranca" como P0 **APLICADO** | `window-visibility.md §2` diz que a cura OFFSCREEN foi *tentada e REMOVIDA* (não uma regressão do produto); `launch-entry.md §4` diz que as causas OFFSCREEN já foram removidas e **há uma 3ª causa por nomear** | `sotto_webview.py:1269-1272` e `:1549-1553` ("tried and REMOVED the same day") |

### B4 — INVENTADO

**0.** Todos os 29 itens do mapa têm origem num dos 8 docs. (Há 2 citações erradas — C1/C2 — e 1
má-atribuição — X1 —, mas nenhum achado fabricado.) As listas de lanes ("EM VOO — `SottoConfigInert`")
não vêm dos docs; verifiquei-as contra o lane ledger e estão certas (excepto a do item 8, que não tem lane).

### B5 — ESTADO ERRADO face ao working tree (mapa diz X, a árvore mostra Y)

| id | mapa diz | working tree mostra | evidência |
|---|---|---|---|
| **W1** | item 4 `blank_frac=1.0` **ABERTO** — "o unico que importa agora" | **lane `BlankFramesRootCause` despachada** (artefacto declarado `docs/audit/blank-frames-root-cause.md`) | lane ledger: `BlankFramesRootCause kind=dispatch state=dispatched`; roster: "task (sub, running)" |
| **W2** | item 8 "provider testado no DEFAULT_MODEL (int4)" **EM VOO** | **já corrigido**: `DEFAULT_MODEL = …-int8` (`sotto_worker.py:77`) e o probe usa `model_dir or DEFAULT_MODEL` (`:942`); **nenhuma lane** desenhada para este item | `read sotto_worker.py:73-77` e `:938-943`; lane ledger não tem lane para int4-probe |
| **W3** | item 9 "7 chaves do config são INERTES" **EM VOO** | **já no tree**: as 7 chaves inertes foram **apagadas** e `block_ms`/`min_chars` ficaram LIVE — o ficheiro tem agora `device, preferred_devices, block_ms, dir, lang_id, use_vad, providers, min_chars` | `read worker/config.json` (comentários "…were DELETED the same day") + `python -c` keys |
| **W4** | item 10 (G1–G4) **EM VOO** | **G4 já corrigido**: `run.cmd` já não cai para `python.exe` ("G4: NO FALLBACK to the console interpreter", refusal loud) | `read run.cmd:37-55` |
| **W5** | item 29 **ABERTO** em `:1531-1535` "a cura que FECHA" | essas linhas **já dizem** que o OFFSCREEN "was tried and REMOVED"; o comentário obsoleto que resta é o de `create_window` (`:1053-1054`, antigo `:1013-1014`) | `grep OFFSCREEN` → `:1053-1054` e `:1549-1553`; `read :1538-1557` |
| **W6** | item 7 **EM VOO** (sem noção de artefacto) | o artefacto da lane **já existe**: `_main/delivery-rate-oracle.py` (19982 B) + `_main/delivery-rate-oracle.log` (119 B, cabeçalho `threshold=0.95` sem veredicto) | `stat` em ambos os ficheiros |

Nada no mapa diz APLICADO/EM VOO sobre algo **sem** mudança (não há o inverso de (c)); os 3 "APLICADO"
(itens 1–3) **verifiquei no tree** e são reais: `wasapi_loopback.py:463` agora
`period = min(0.005, …)`; `_move_into_place`/OFFSCREEN removidos; `grep -c "self._ui(_run)"` = **1**
(a 2ª chamada de `exec_js` foi removida).

---

## C. Contagem (para a afirmação ser checável)

- **Achados enumerados nos 8 docs:** 61 (tabela A, linha a linha).
- **Linhas no mapa:** 29.
- **Achados com casa no mapa:** 31 (2 linhas many-to-one: item 8 = 2 achados, item 10 = 4).
- **MISSING:** 30 (lista B1, M1–M30).
- **INVENTED:** 0.
- **WRONG-STATE:** 6 (W1–W6).
- **Citação errada:** 3 (C1–C3).
- **Má-atribuição:** 1 (X1).
- Conferência: 31 (no mapa) + 30 (MISSING) = 61 (achados nas fontes). ✔

Os três eixos mais atingidos são `oracles.md` (9 ausentes), `window-visibility.md` (5) e
`windows-landmines.md` (4 + 1 lei deturpada). Um mapa que se anuncia "nenhum achado novo" e lê como
completo a 51 % de cobertura é precisamente o caso "pior que nenhum mapa" que a tarefa nomeia.

---

## D. Nota sobre a secção "Landmines" do mapa

O mapa escreve em "Landmines de ambiente medidas (nao sao fixes do app — sao leis de medicao)":
`taskkill pode truncar o log de um filho`.

**A fonte diz o contrário desse meandro:** `windows-landmines.md` landmine 3 →
*"Buffered-tail loss did **not** reproduce"* (3 réplicas: ficheiro, pipe-python, pipe-node). O que
realmente morde é (i) `taskkill /F` não corre shutdown graciosa (`HOTRELOAD.md:326-330`) e (ii) um caso
de codepage real e **já corrigido** (`runcmd-entry-driver.py:168-170`, `errors='replace'`). Por isso,
além de os *bugs* F1–F4 ficarem de fora, a lei que o mapa conserva (D-LM3) é a metade que o doc
**refutou**. As 6 leis viram 4 no mapa: caem a landmine 5 (paths com espaços, "no bite") e a landmine 6
(`subprocess timeout` não é tecto — **BITES em 3 oráculos**), e com a 6 cai o achado F2.

---

## SELF-AUDIT

- **protocolos em falta** — Faltei ao `dispatch-preflight` ao ir buscar as fontes por ordem de leitura
  (audio → shell → …) em vez de, primeiro, extrair mecanicamente todas as âncoras `F\d|G\d|H\d` de cada
  doc. Tivesse feito o grep de rótulos primeiro e a enumeração (§A) sairia de um `grep -o`, não de
  leitura de 200 KB. Faria diferente: `grep -nE '\*\*F[0-9]|^### F[0-9]|^G[0-9] |H[0-9] '` nos 8 docs
  como **passo 0**, antes de ler qualquer prosa.
- **verificação adicional** — O check que mais teria aumentado a confiança e **não** corri: re-sondar
  `docs/README.md:8` e `AGENTS.md:89/119/25` com um `grep` de título para provar que os itens 18–23
  continuam **stale** na árvore (fiz para 4 linhas, mas por `sed`, não por um predicado). Custo: 1
  comando; o custo real é que AGENTS.md está **untracked e editado**, logo as âncoras `:25/:89/:119/:169`
  do doc `doc-vs-code.md` podem já não resolver — não o fechei.
- **checkboxes novas** — Um passo NOVO e MECÂNICO para esta classe: **"todo `F\d`/`G\d`/`H\d` de um doc
  fonte tem de aparecer no mapa, e o `file:line` do mapa tem de ser idêntico ao do doc"**. Comando:
  `comm -23 <(grep -ohE '\b(F|G|H)[0-9]+' docs/audit/*.md | sort -u) <(grep -ohE 'item [0-9]+' 00-MAPA-CONSOLIDADO.md)`.
  Input que tem de o deixar RED: os 8 docs de hoje — a saída são os rótulos M1–M30 que este review
  encontrou à mão. Fecha o buraco "mapa gerado por leitura de títulos".
- **review por outro subagente** — **sim-com-escopo**: um segundo revisor deve re-derivar SÓ a tabela A
  (contagem de achados por doc) e a lista MISSING, a partir dos `grep` de rótulos, **sem** ler o meu
  texto — é a parte que, se eu contei mal, contamina tudo. Não para as citações C1/C2 (mecânicas) nem
  para o self-audit.
- **gate-doubt**:
  - **verde-de-verdade:** o único "verde" que produzi foi `3+4+22 = 29` a fechar a contagem **do próprio
    mapa** (auto-consistente, não vazio) e o `grep -c "self._ui(_run)" = 1`. O primeiro **não** prova
    cobertura (prova aritmética); o segundo é a conta real da correção do item 3. **Nenhum gate do repo
    correu** — não há gate que compare um mapa com as suas fontes (é o buraco).
  - **falta-no-gate:** **não existe** nenhum gate que verifique que um documento "consolidado" cobre as
    suas fontes. Um mapa futuro pode apagar 9 de 10 achados de um doc e passará **toda** a instrumentação
    da casa (self-audit-lint só checa a forma do SELF-AUDIT); nada compara conjuntos de rótulos.
  - *gate-melhor*: **o gate que esta própria sessão mandou construir** — `AuditMapGate`
    (`I:/!manager/scripts/audit-map-gate.sh`, artefacto declarado). Fecho mecânico: para cada rótulo
    `F\d|G\d|H\d` presente em qualquer doc fonte, exigir a sua presença no mapa; RED input = o mapa de
    hoje (faltam 30). Enquanto esse script não existir, o fecho é `n/a — o gate pertence à lane
    AuditMapGate, que está despachada`.
- **confiança** — **alta** na enumeração MISSING (cada linha cita um rótulo explícito do doc) e nos 6
  WRONG-STATE (cada um é um `read`/`grep` do working tree). **média** na fronteira 30/31 da contagem
  "com casa no mapa", porque o mapa agrupa (item 8, item 10) e o número exacto depende de contar linhas
  ou achados — o artefacto checável é a lista M1–M30, não a soma. O que a mudaria: o gate `audit-map-gate.sh`.
- **nao verificado** — (1) não re-corri nenhum dos oráculos citados (proibido: abririam janela);
  (2) **não confirmei** se `AGENTS.md` (untracked, editado) ainda se autocontradiz no item 20 — as
  âncoras do doc `doc-vs-code.md` podem ter deslizado; (3) não li `delivery-rate-oracle.py` linha a linha
  — só confirmei que existe e o log não tem veredicto; (4) os 3 WRONG-STATE "EM VOO" que marquei como
  já-corrigidos podem refletir trabalho **da lane em curso** a meio, não um erro do autor do mapa — dito
  como tal; (5) a contagem "61" depende da minha enumeração de achados não-rotulados (ex.: §5/§6 de
  `model-config.md`), declarada na tabela A.

---

## GATE-CHANGE REQUEST

- **gate:** `I:/!manager/scripts/audit-map-gate.sh` (artefacto declarado da lane `AuditMapGate`,
  ainda **ausente** — a lane está despachada, não entregue).
- **hole:** não existe nenhum gate que verifique que um documento "consolidado" **cobre as fontes que
  ele próprio declara**. Um mapa pode apagar 30 de 61 achados e passa toda a instrumentação da casa
  (o `self-audit-lint` só valida a forma do bloco SELF-AUDIT, nunca o conjunto de achados). Medido
  neste review: a cobertura real do `00-MAPA-CONSOLIDADO.md` é **31/61**.
- **change (merge-ready shape):** para cada doc-fonte em `H:/sotto/docs/audit/`, extrair os rótulos
  `F\d+|G\d+|H\d+|Finding [A-Z]` e os ids de landmine; exigir que cada um apareça no mapa; devolver
  não-zero a contar os ausentes. Comando-shape:
  `comm -23 <(grep -ohE '\b(F|G|H)[0-9]+' docs/audit/*.md | sort -u) <(grep -ohE 'item [0-9]+' docs/audit/00-MAPA-CONSOLIDADO.md)`
- **non-vacuity control (input que TEM de ficar RED hoje e GREEN depois):** o mapa actual
  (`00-MAPA-CONSOLIDADO.md`) — hoje devolve os 30 rótulos ausentes (M1–M30 do §B1 deste review); um
  mapa que cite todos os rótulos tem de devolver vazio. Um mapa que só reordene linhas (sem acrescentar
  achados) continua RED — é o par que discrimina "reorganizar" de "cobrir".

---

## CACHE/PRICE

`bash I:/!manager/scripts/cache-task-report.sh AuditMapReview` → rc=0, stdout VERBATIM:

```
## CACHE/PRICE
- task/agent: AuditMapReview
- source: C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditMapReview.jsonl
- cache: read=3768960 write=0 hit=95.1753% (cache-read / input+cache-read); universe: 30 usage rows from C:\Users\Administrador\.omp\agent\sessions\--I--!manager--\2026-10-06T04-22-21-088Z_01a10f72-c0a0-7284-9445-0cecfd6636ce\AuditMapReview.jsonl; instrument: scripts/cache-task-report.sh
- price: $0.00000000 USD (source: session JSONL message.usage.cost.total; provider-reported pricing; exact per-model rates: UNKNOWN — not recorded in this source); price partition by token class and model: opencode-go-1/deepseek-flash: calls=26 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000 | opencode-zen/space-bunny-free: calls=4 input=$0.00000000 output=$0.00000000 cacheRead=$0.00000000 cacheWrite=$0.00000000; partition sums to the reported total: opencode-go-1/deepseek-flash $0.00000000; opencode-zen/space-bunny-free $0.00000000 vs $0.00000000 over 30 of 30 matched usage rows
- when-failed: break_items=3; WHEN=2026-10-06T08:40:07.835000+00:00 | break_items=2; WHEN=2026-10-06T08:42:38.053000+00:00 (state=RESOLVED-BREAKS-OMP; population: 2 of 113827 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'AuditMapReview']; window: 2026-10-06T08:40:07.835000+00:00..2026-10-06T08:42:38.053000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- where-failed: session_id=01a1105e-8094-7087-bf20-6a8b4a25ba43 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791276007835 | session_id=01a1105e-8094-7087-bf20-6a8b4a25ba43 provider=deepseek-flash model=deepseek-flash item_index=110; turn_id=1791276158053 (state=RESOLVED-BREAKS-OMP; population: 2 of 113827 OMP prefix-ledger rows attributable to keys ['01a10f72-c0a0-7284-9445-0cecfd6636ce', 'AuditMapReview']; window: 2026-10-06T08:40:07.835000+00:00..2026-10-06T08:42:38.053000+00:00; key: agent_id/session_id in the OMP cache-prefix ledger)
- report generated_at: 2026-10-06T08:44:00.350673+00:00
- usage rows: 30
- model + route: opencode-go-1/deepseek-flash, opencode-zen/space-bunny-free
- input tokens: 191058
- output tokens: 38476
- cache-read tokens: 3768960
- cache-write tokens: 0
- hit ratio: 95.1753% (cache-read / input+cache-read)
- prefix breaks: 5 (state=RESOLVED-BREAKS-OMP)
- WHEN / WHERE failed:
  - break_items=3; WHEN=2026-10-06T08:40:07.835000+00:00; WHERE session_id=01a1105e-8094-7087-bf20-6a8b4a25ba43 provider=deepseek-flash model=deepseek-flash item_index=0; turn_id=1791276007835
  - break_items=2; WHEN=2026-10-06T08:42:38.053000+00:00; WHERE session_id=01a1105e-8094-7087-bf20-6a8b4a25ba43 provider=deepseek-flash model=deepseek-flash item_index=110; turn_id=1791276158053
- verdict: UNKNOWN — no task-level acceptance verdict is stored; ratio is descriptive, not a prefix-stability decision
```

Nota honesta: `$0.00000000` é o que o JSONL da sessão regista e as taxas por modelo são `UNKNOWN` nessa
fonte — reporto o valor do instrumento, não afirmo custo zero. Instrumento: `scripts/cache-task-report.sh`
(invocado do assento AuditMapReview). Falhou ao me ter mascarado o `bash` por um wrapper `timeout` (o
landmine-guard C1 bloqueou `timeout` nu) e, sem esse wrapper, resolveu à primeira.
