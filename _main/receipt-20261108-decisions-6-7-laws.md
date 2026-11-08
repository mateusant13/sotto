# RECIBO — as DECISOES 6 e 7 viram leis, e o inventario passa a ter UM dono (2026-11-08)

Tudo o que aqui esta' foi medido nesta arvore hoje; onde a linha diz `PASS`, o comando esta ao lado.

## 1. O que entrou

| artefacto | o que e' | medicao |
|---|---|---|
| `bend_core/LAWS.bend` (+411 linhas) | 14 leis novas: `Hist.*` (quem pode escrever o historico canonico) e `Fmt.*` (qual rota um commit carimba) | `bend PROOF.bend --verdict` → **ALL PROOFS CHECK**, 28 leis |
| `bend_core/PROOF.bend` (+193) | um `def Laws.<lei>` por afirmacao | idem |
| `bend_core/NEGATIVE_hist_*.bend` / `NEGATIVE_fmt_*.bend` (14 ficheiros) | um controlo por lei, uma afirmacao FALSA cada | 14/14 falham na lei que nomeiam |
| `bend_core/model.py` (+200) | a mesma amostra em Python, para host sem toolchain | `GREEN (amostra)`; `--neg-arm` viola **15** leis |
| `_main/bend_mirror.py` (novo) | liga as 14 leis as funcoes REAIS, executando-as por `node` | `MIRROR VERDICT GREEN (14 checks, 21 history rows, 10 engine cases)` |
| `tools/bend_verify.sh`, `tools/bend_proof_ledger.py` | os pins do `.sh` e o livro de provas acompanham a coorte | inventario do `.sh` = o do portao |

**As duas funcoes ligadas sao codigo VIVO**: `app/panel/panel.html:1111` carrega `history-source.js`
e `:1104` carrega `caption-formulation.js`; uma lei ligada a codigo morto nao e' evidencia.

## 2. Os cinco defeitos que a aterragem expos, e o que cada um custou

| # | defeito | medicao | cura |
|---|---|---|---|
| 1 | **duas copias do pin do inventario** divergiram no mesmo dia: a lane escreveu as 14 leis no `tools/bend_verify.sh` e nao no portao | `bend-laws rc=5`: `BEND-GATE FAIL: LAWS.bend law inventory drifted from the pin` (esperado 14, achado 28) | o portao e' o DONO do pin; o `.sh` e' um consumidor conferido por `deep_tool_drift()` -> `EXIT_INVENTORY` |
| 2 | `_main/bend_mirror.py:134` largava `node` por `subprocess.run` cru | `CONSOLE-AUDIT VERDICT FAIL -- 1 sitio(s) que abrem janela` | passa por `_main/hidden-launch.py` (`run`, `CREATE_NO_WINDOW`); auditoria `PASS -- 0 sitio(s)` |
| 3 | o `--red` do espelho devolvia **0 ao apanhar** (a inversao que a casa ja' curou no `hotkey-spam`) | `rc=0` com `RED-RUN VERDICT GREEN` | `rc=1` + `NEG-ARM PASS` quando apanha; `rc=0` quando um mutante passa |
| 4 | o `bend-laws` nao nomeava **nenhum** dos 14 controlos novos nem o `tools/bend_verify.sh` | a classe do `panel-deps`: passo em cache sobre ficheiro que ja' mudou | 15 dependencias acrescentadas |
| 5 | `tools/bend_proof_ledger.py` tinha juiz (`--self-test`, 5 fixtures) e **zero chamadores** | a lei do custo: instrumento sem passo apodrece | passo `bend-ledger-selftest` |

O braco negativo do detector NOVO (o cruzamento de pins), para ele nao ser decoracao: uma copia do
espelho com o primeiro mutante desarmado (`new == old`) devolve **0** e imprime
`RED-RUN VERDICT FAIL (1 mutant(s) not caught)` -> o `:expectred` da bateria reprova-o.

## 2-bis. Os dois bracos que a CORRIDA expos (e nao a lei)

| # | braco | medicao | cura |
|---|---|---|---|
| 6 | `panel-commit-stable` estourou o prazo do passo (`rc=124`) | corpus = o log INTEIRO: **18 744** `CAPTION_IN` em 418 754 linhas; sozinho **109,6 s**, e **>240 s** com outra lane na maquina | o CENSO continua inteiro (Python puro); o REPLAY usa a cauda de **6 000** fragmentos, declarada (`replay_sample=6000 de 18744`); passo: **17,6 s** |
| 7 | `gaming-hotkey` RED no orcamento absoluto | `tick_min=91,14 ms` contra `budget=50,0 ms`, mas `enum_min=119,13 ms` para UMA enumeracao nua (669 processos) -- racio **0,77**: o tick custou MENOS do que a enumeracao que tem de fazer | o orcamento passa a julgar a DISJUNCAO (cabe no orcamento **ou** e' o de uma enumeracao nua), e ganha o seu primeiro controlo: `MUTANTE 5` poe uma chamada de 200 ms no tick -> cost arm RED (`tick_min=259,40 ms`), `NEG-ARM PASS` **5/5** |

E um terceiro, da mesma classe do `caption-budget`: `panel-commit-stable` julgava
`audio p95 falls`, e medido sobre a cauda de 6 000 fragmentos o p95 **sobe** 3 236 -> 3 897 ms
enquanto as FATIAS melhoram (acima do orcamento **29,4 % -> 5,3 %**, saudavel **8,1 % -> 84,5 %**).
Um percentil sobre um campo BIMODAL (de 0 a 1 780 818 ms na mesma amostra) mede a populacao, nao a
cura: o braco passa a ser "nao regride" (<= 1,5x) e o numero fica publicado ao lado das fatias.

## 3. Portoes corridos

| portao | veredicto |
|---|---|
| `_main/bend-laws-gate.py` (WSL, 28 leis + 28 controlos + 2 sondas) | `BEND-GATE VERDICT: PASS` |
| `_main/bend_mirror.py` | `GREEN (14 checks)` |
| `_main/bend_mirror.py --red` | `NEG-ARM PASS -- 4/4 mutante(s)` |
| `bend_core/model.py` / `--neg-arm` | `GREEN` / `RED-BY-DESIGN` (15 leis violadas) |
| `tools/bend_proof_ledger.py --self-test` | `PASS` (5 fixtures, incluindo "um check saltado nunca e' verde") |
| `_main/console-window-audit.py` / `--neg-arm` | `PASS -- 0 sitio(s)` / `NEG-ARM PASS` |
| `_main/battery-record-pairing-oracle.py` | `passos: 385, nomes com registro: 385, achados: 0` |
| `_main/battery-wiring-oracle.py` | `PASS` (`ligados=160 sem_passo=109 populacao=269`) |
| `_main/agents-md-pins-oracle.py` | `PASS` (pin novo: 292642 B / 3533 CRLF / `8FBB1211...`) |
| docs do bundle | os cinco sha256 portados continuam a bater com a tabela do `docs/bend/README.md` |

## 4. O QUE NAO ESTA' VERIFICADO

* `verified` continua impossivel de uma lane: nada disto foi visto na tela do dono, e a lei prova
  um MODELO PURO -- nao uma corrida da app.
* O espelho e' uma checagem comportamental FINITA sobre as grades do ficheiro (21 linhas de
  historico, 10 casos de motor). Nao estabelece o teorema; o kernel e' que faz isso.
* O `bend-laws` gastou **12,5 s** numa corrida a quente; o prazo por passo da casa e' 240 s, logo
  nada a declarar, mas o numero fica aqui para o ratchet da bateria.
