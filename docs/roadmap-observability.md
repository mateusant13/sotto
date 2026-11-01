# Roadmap — observabilidade, memória e dívida medida (2026-10-23)

Deriva de `docs/protocolos-observabilidade.md` §15. Cada linha tem **ficheiro**, **portão** e
**dependência**. A coluna *paralelo* diz o que pode correr ao mesmo tempo, e a razão é sempre a mesma:
**ficheiro novo pode; ficheiro de produto não** (a árvore é uma só, o `AGENTS.md` e o `.cmd` têm um único
escritor, e a app é instância única).

---

## P0 — "menos idas à memória humana" (paralelo, só ficheiros novos)

| id | o que | ficheiro | portão | dependência | paralelo |
|---|---|---|---|---|---|
| **P0.1** | `sotto facts`: imprime cada facto medido **com o instrumento ao lado** (`load_s=22.8 (worker: model-loaded)`); `--verify` re-corre o instrumento e compara | `_main/sotto-facts.py` + `_main/facts.json` | `--selftest` com instrumento falso: tem de **falhar** quando o valor muda | nenhuma | **sim** |
| **P0.2** | Página de estado **gerada** a partir das saídas dos oráculos, nunca escrita à mão; recusa renderizar um passo que não correu | `_main/sotto-state-page.py` → `docs/state-generated.md` | recusa-se a inventar: um passo ausente é `NOT RUN`, nunca um verde | nenhuma | **sim** |
| **P0.3** | Portão da **data**: uma afirmação numérica no `AGENTS.md` sem data/medição ao lado é vermelha; baseline ratchet | `_main/claims-date-oracle.py` + `_main/claims-date-baseline.json` | `--neg-arm` 3 mutantes (número sem data, data sem instrumento, baseline a crescer) | nenhuma | **sim** |
| **P0.4** | Ligar P0.1–P0.3 à bateria + braços negativos | `_main/_audit-verify-all.cmd` (CRLF, `edit`, nunca `write`) | bateria verde | P0.1–P0.3 | **não** (escritor único: eu) |

**Estado da P0 (medido 2026-10-25 10:3x).** **P0.3 ENTREGUE e ligada.** `_main/claims-date-oracle.py`
faz 4 checks (`new-undated-claim`, `baseline-schema`, `baseline-ceiling`, `baseline-orphans`) com
**6** mutantes — os 3 que esta linha pedia (número sem data, data sem instrumento, baseline a crescer)
e mais dois que o portão mostrou serem precisos: a entrada **órfã** (a licença tem de encolher quando a
linha é curada) e o **fail-safe** de baseline ausente (só pode ser vermelho). O tecto do baseline está
pinado **no código** (4), não no JSON, para o regenerador não poder levantar o seu próprio limite. A
unidade da afirmação é o **bloco**, não a linha: a leitura linha-a-linha acusava 23 sítios e quase todos
eram a continuação de uma frase cuja cabeça carrega a data. O baseline nasceu com **7** afirmações e
ficou em **4** — as três curadas incluem um número **velho** (`119 linhas de medições`; medido **120**),
que é a primeira coisa que este portão encontrou. Os passos `claims-date` e
`red-as-expected-claims-date` estão na bateria. **P0.1 continua por fazer**; P0.4 fica a faltar
só para ela.

**P0.2 ENTREGUE e ligado (medido 2026-10-25 10:3x).** `_main/sotto-state-page.py` gera
`docs/state-generated.md` a partir de **três** artefactos e de mais nada: a declaração dos passos
(`_main/_audit-verify-all.cmd`), o registo do que correu (`_cache/battery-steps.json`, escrito pelo
`_main/_stepcache.py`) e as saídas (`_main/_audit-verify/*.log`). Seis estados — `PASS`,
`EXPECTED-RED`, `FAIL`, `STALE`, `NO-VERDICT`, `NOT RUN` — e **nenhum verde sem sustentação**: `PASS`
exige rc igual ao esperado, log com o sha256 registado e deps com o fingerprint de hoje; `EXPECTED-RED`
exige ainda o token declarado em `:expectred` dentro do log; um passo sem registo **e** sem log é
`NOT RUN` e nunca outra coisa. Oito verificações (`step-declared`, `no-invented-green`,
`absent-is-not-run`, `expected-red-token`, `verdict-vocabulary`, `cells-match-record`,
`summary-counts`, e `page-in-sync` com `--require-fresh`) e **oito mutantes**, todos `NEG-ARM PASS` com
rc=1 por desenho. Os passos
`state-page` e `red-as-expected-state-page` estão na bateria como `always` (custo 3,49 s). Primeira
medição da página: 124 passos — `PASS=49`, `EXPECTED-RED=17`, **`FAIL=7`**, `STALE=37`,
`NO-VERDICT=7`, `NOT RUN=7`. Os `FAIL` são estado real medido em 2026-10-24 (`code-health`,
`exception-hygiene`, `panel-flash-contradiction`, `strip-*`) e os `STALE` são os verdes cujas deps
mudaram depois — o preço honesto de 713 caminhos sujos. Recibo:
`_main/receipt-20261025-p0-2-state-page.md`.

## P1 — "menos idas à memória do processo" (serial, ficheiro de produto)

O achado que manda nisto: `og.Model(model_dir)` **e** três `InferenceSession` carregam os mesmos pesos;
`peak_rss 785 MB` para 747 MB de modelo; e o estado benigno já foi medido com `private 3070 MB` e
`rss 21 MB` (páginas *trimmed*, memória comprometida, modelo não libertado).

| id | o que | ficheiro | portão | dependência | paralelo |
|---|---|---|---|---|---|
| **P1.1** | A/B `SOTTO_LOAD_AB=bytes` / `basic` sobre `load_phases_s` | `worker/sotto_worker.py` (já tem o travão) | 3 corridas de ~30 s, mesmo áudio, mesmo texto reconhecido | — | em curso |
| **P1.2** | Medir se o `og.Model` precisa dos pesos todos ou só do front-end mel/VAD (RSS depois de cada passo, não no fim) | `_main/mem-split-probe.py` (novo) | a soma das fases tem de bater com o `peak_rss` | P1.1 | **sim** (ficheiro novo) |
| **P1.3** | Orçamento de memória impresso no log em **cada** transição de estado (`rss`, `private`, `working set`) | `worker/sotto_worker.py` | `code-health` não cresce; uma linha por transição, medida | P1.1 | não |
| **P1.4** | *Unload* explícito no silêncio benigno (`private 3070 MB`) e medir de novo | `worker/sotto_worker.py` | antes/depois com o mesmo instrumento; texto transcrito inalterado | P1.2 | não |
| **P1.5** | `awareness`: se o `og.Model` duplica o encoder, a cura é estrutural (uma carga, duas vistas), não um travão de ORT | decisão + recibo | `load_phases_s` + `peak_rss` antes/depois | P1.2 | não |

## P2 — bloqueado no dono

| id | o que | porque bloqueia |
|---|---|---|
| **P2.1** | Arranque **sob** o profiler (`py-spy record -- pythonw sotto_webview.py`) | exige fechar e reabrir a app; só tu o podes fazer (a app é instância única e esta pane é elevada) |
| **P2.2** | Perfil do lado **JS** do painel | precisa de `--remote-debugging-port` no WebView2; hoje só há sondas de DOM |

## P3 — dívida já medida, ainda não mechanizada

| id | o que | números |
|---|---|---|
| **P3.1** | Ratchet do *wiring* da bateria — **ENTREGUE 2026-10-25**: medido **171** oráculos de enforcement, **47** ligados, **124** sem passo (os números antigos, 127/37/90, ficam retirados). Tecto **124** pinado no código, baseline com 124 entradas nomeadas com razão e data | `_main/battery-wiring-oracle.py` + `_main/battery-wiring-baseline.json`; 6 checks e 6 mutantes (`NEG-ARM PASS`, rc=1 por desenho); passos `battery-wiring` e `red-as-expected-battery-wiring` na bateria. **Falta o verde dentro de uma corrida** (gate `heavy` AMBER) |
| **P3.2** | Reconciliar os dois registos de reclamacoes - **ENTREGUE 2026-10-25**: **39 linhas** do backlog (22 fechadas, 6 parciais, 10 abertas, 1 decidida) contra **31 seccoes fechadas** do documento de fecho, e a juncao e calculada pelas PALAVRAS DO DONO (21/39 ligadas). Daí saem **13 contradicoes** (a seccao de fecho reivindica a reclamacao que o backlog diz aberta), cada uma obrigada a um `gap` que nomeia a seccao e diz o que a sua evidencia NAO mede. **D1 fecha-se por medicao** (`_main/external-resume-oracle.py`, 8/8, re-executado). Achado principal: **R28 fecha-se correndo o proprio portao do documento** (`--self`) e o literal que cita diz `closed=30` quando hoje sao 31 - auto-fecho declarado como defeito conhecido | `_main/complaints-reconcile-gate.py` + `_main/complaints-reconcile.json`; **8 checks** e **10 mutantes** (`NEG-ARM PASS`, rc=1 por desenho); passos `complaints-reconcile` e `red-as-expected-complaints-reconcile`, os dois `always`. **Falta o verde dentro de uma corrida** (gate `heavy` AMBER) |
| **P3.3** | Custo do cache da bateria: **medido 2026-10-25** com `_main/stepcache-cost-probe.py` — **63,3 ms** por passo em cache (a frase antiga dizia 0,33 s e é **retirada**, não corrigida), dos quais **42,6 ms** são arranque de processo e **1,6 ms** (2,6 %) o resolvedor; 100 passos ≈ **6,3 s**. O corte é no arranque: `python -S` mede **54,0 ms** (−17 %) com o mesmo veredicto — **ainda não aplicado** | `_main/stepcache-cost-probe.py` (novo); `--neg-arm` 3 braços (estado ausente/corrompido/vazio → `NO-VERDICT`, nunca um número). Falta o antes/depois **dentro** de uma corrida da bateria |

---

## Ordem de execução

```
hoje, em paralelo:   P0.1 ─┐
                     P0.2 ─┼─> P0.4 (eu, serial)  ─> bateria verde
                     P0.3 ─┘
                     P1.2 (sonda nova, sem tocar em produto)
serial, a seguir:    P1.1 -> P1.3 -> P1.4 -> P1.5
quando o dono puder: P2.1 -> P2.2
dívida:              P3.1 -> P3.2 -> P3.3
```

**Regra de aceitação de cada item:** só entra quando o portão está na bateria, o braço negativo foi
**executado** (`NEG-ARM PASS`, rc=1 por desenho) e o número *antes*/*depois* está escrito no recibo. Sem
isso é capacidade nova, e a lei do `tooling-intent` manda-a declarar `# NO-BUG:` — ou não entra.
