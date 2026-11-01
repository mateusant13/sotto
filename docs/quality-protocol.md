# Protocolo de qualidade do Sotto — adaptado de três casas

Escrito 2026-10-23. Não é uma cópia: cada lei diz **de onde veio** e **qual é o portão do Sotto que a
impõe**. Uma lei sem portão é a próxima coisa a apodrecer.

Fontes lidas (por ordem de utilidade para este repo):

| casa | o que tem | o que levámos |
|---|---|---|
| `I:\!manager` | `playbooks/error-proof.md`, `AGENTS.md` (§ regras), `hooks/pre-block-owner-app-kill.ts` | constraints extraídas **antes** da acção, checker com rc 0/1/2, "ausência de evidência nunca é evidência de conformidade" |
| `C:\Users\Administrador\Desktop\consult-chatgpt\consultgpt` | `.cursor/rules/fix-on-sight.mdc`, `subprocess-watchdog.mdc`, `testing-timeout.mdc`, `default-development-protocol.mdc` | padrões proibidos que falham sozinhos, disciplina de subprocesso, 20 s na primeira corrida |
| `G:\superharness` | `engineering-protocol.md` §1–§9, `harness.json`, `weaknesses-register.md` | três naturezas de trabalho, "smallest mechanism", instrumentado por omissão, definição de pronto, gate de release |

---

## As sete leis

### 1. A evidência vence a afirmação — e o `rc` carrega um veredicto, nunca uma causa
*(manager: "an `rc` carries a VERDICT, never a CAUSE"; "a truncated tool line is NOT evidence")*

- Toda a afirmação de estado é `evidence: <comando> -> <substring estável>`, nunca uma frase.
- Um número derivado publica-se **com população e janela** ("76 de 91 passos em cache, corrida de
  130,2 s em 2026-10-21"), não sozinho.
- **Sotto:** `BATTERY-VERDICT` + exit code é o veredicto da bateria; um passo saltado não é um portão
  que passou (`skipped=` é a prova). `_main/receipt-*.md` guarda o instrumento, o braço negativo e o pin.

### 2. Um portão que não pode ficar VERMELHO não é um portão
*(manager: "a test that cannot go RED is not evidence"; consultgpt: `tdd-red-green.mdc`)*

- Todo o portão novo nasce com **braço negativo já executado** (`NEG-ARM PASS`, rc=1 por desenho) e
  **mutantes** que ele apanha. Sem isso é um comentário com sintaxe.
- **Sotto:** `--neg-arm` em `youtube-foreign-paint-oracle.py`, `border-radius-gate.py`,
  `battery-heavy-gate.py`, `input-path-oracle.py` (4 mutantes); a bateria tem o passo
  `red-as-expected-*` correspondente, com `:expectred` a exigir rc **exactamente 1** e o texto.

### 3. O menor mecanismo, e instrumentado por omissão
*(superharness §2b: "SMALLEST-MECHANISM", "INSTRUMENTED-BY-DEFAULT"; "a guard without telemetry is a
guard that doesn't exist")*

- Preferir **mecanismo** (gate, lock, fila, schema, temporizador) a **prosa** ("lembra-te de").
- Todo o guarda publica o que fez: contador, evento, ou uma linha de log com nome próprio.
- **Sotto:** o hook de rato tem três mecanismos (preguiçoso, libertado por propriedade, auto-cura de
  5 s) e cada transição escreve `OUTSIDE_CLICK_HOOK installed=…` / `uninstalled reason=…`.
  A classe pesada da bateria publica `heavy:` e `priority:` no sumário.

### 4. Extrair as restrições ANTES de agir; o checker corre antes do efeito
*(manager: `error-proof.md` — 5 passos; "absence of evidence is never treated as evidence of compliance")*

- Um pedido do dono transforma-se em **cartão** com as restrições como estruturas verificáveis, não numa
  lista de afazeres. `≤ 3 meses`, `grátis`, `não matar a app do dono`, `áudio mudo` são **gates**.
- O checker corre **antes** do efeito secundário: rc 0 passa, 1 viola, 2 é falha de processo (não é
  licença para avançar).
- **Sotto:** as HARD RULES do `AGENTS.md` são este cartão (áudio mudo por `mute-audio.py`, filtro de
  kill nomeia o artefacto, `TMPDIR=I:\cc-tmp`, só o LEAD lança a app). O que falta é o checker único —
  ver §Dívida.

### 5. Fix on sight — zero tolerância, e os padrões proibidos falham sozinhos
*(consultgpt: `fix-on-sight.mdc`)*

Proibido no produto: `TODO/FIXME/HACK` no caminho vivo; `except Exception: pass` sem razão escrita;
fallback silencioso com semântica diferente; um teste que só passa porque faz mock do que devia testar;
flag aceite e ignorada; docstring que mente.

**Sotto:** o `_record` do outside-click foi curado assim em 2026-10-17 (log flood de 640 B/s); hoje o
`except` do hook leva a razão no comentário ou não existe.

### 6. A superfície do dono é sagrada: nada entra no caminho de input/composição sem precisar
*(owner, 2026-10-23; ver `AGENTS.md` §5)*

- Hook global, overlay layered, janela transparente, capture, timer de pintura: **medidos pela
  ausência**. Com o produto parado, não existem.
- Um sintoma "só o rato" com o resto bom aponta para o caminho de input, não para carga do sistema.
- **Sotto:** `_main/input-path-oracle.py` (6 braços / 4 mutantes) + `red-as-expected-input-path`.

### 7. Disciplina de subprocesso — esperar primeiro, matar por opt-in, 20 s na primeira corrida
*(consultgpt: `subprocess-watchdog.mdc`, `testing-timeout.mdc`)*

- Nada de `subprocess.run(...)` sem `timeout=`; `Popen` sem monitor é um processo que sobrevive ao turno.
- **Esperar por capacidade** em vez de matar; matar só por opt-in explícito; o filtro **nomeia o
  artefacto** (`sotto_worker\.py`), nunca uma palavra genérica.
- Primeira corrida de verificação: **20 s**. Só se sobe o tecto depois de a corrida curta não ter erros.
- **Sotto:** `_main/mute-audio.py` (portão 21/21), o `CREATE_NO_WINDOW` do shell, e o `battery-heavy-gate`
  (pesados só com `SOTTO_BATTERY_HEAVY=1` lido pelo **valor**).

---

## A ordem de trabalho (adaptada de `engineering-protocol.md` §2)

1. **Natureza** — é *conserto* (há um defeito medido), *contrato* (interface/observável) ou *novo
   mecanismo*? A natureza escolhe o método. Conserto: primeiro o instrumento que o reproduz.
2. **Plano com todos os itens nomeados** pelo dono; silêncio sobre um item é falha.
3. **Leitura com evidência** — `file:line` re-lido hoje; toda a citação é HINT até ser re-grepada.
4. **Teste primeiro** — o braço que fica vermelho com o defeito e verde com a cura.
5. **Implementar até verde**, com o mecanismo mais pequeno que aguenta.
6. **Braço negativo + mutantes**, executados, não prometidos.
7. **Registar** — recibo com instrumento, números, e o que **não** ficou provado.

## Definição de pronto (adaptada de §6/§8)

- [ ] o defeito tem uma medição **antes** e uma **depois**, com o mesmo instrumento;
- [ ] o portão está na bateria **e** o seu `red-as-expected-*` também;
- [ ] o braço negativo correu (`NEG-ARM PASS`, rc=1 por desenho);
- [ ] os mutantes do portão são apanhados (`N/M`);
- [ ] `AGENTS-PINS` verde, `_gitattributes-verify` verde (`DIVERGENTES 0`);
- [ ] `BATTERY-VERDICT` verde com `missing=0`, e o `skipped=` lido (não escondido);
- [ ] recibo em `_main/receipt-*.md` com o que ficou por provar;
- [ ] se tocou no caminho de input/composição: prova de ausência com o produto parado.

---

## As três leis que vieram depois (2026-10-23, segunda passagem)

Fontes frescas, lidas por data e não por nome: `G:\superharness\runs\workflow-quality-loop-findings.md`
(2026-10-23 20:20), `I:\!manager\state\research\bug-hunt-workflow-approaches.md` (2026-10-23 20:12), e
os cartões de trabalho do manager (`state/cards/TC-20261023-…`) que mostram o formato real de
aceitação: `production_entrypoint`, `negative_control`, `positive_control`, `mutation_or_revert`,
`provenance_ref`, `provenance_sha`, **`tri_state_probe`** (PASS / RED / **UNKNOWN**) e a
**`silent-failure metric`** ("todos os braços reportados, passado, falhado ou saltado **com a razão**").

### 8. Jidoka — parar a linha quando o check está vermelho, velho, ausente ou incapaz de provar o seu resultado
*(superharness §1; manager `bug-hunt-workflow-approaches.md`)*

Um estado **desconhecido** nunca é verde. No Sotto: `BATTERY-VERDICT` distingue `GREEN` de
`GREEN WITH n SKIPPED`, `missing=0` é impresso, `_main/_skip-verdict-guard.py` recusa um log que
tenha o veredicto de salto sem o registo do salto, e o `skipped=` é lido em voz alta. Um passo pesado
saltado **não** conta como gate.

### 9. A cobertura conta-se por INVOCADOR, com positivo **e** negativo no invocador real
*(superharness §"The missing control")*

`invocadores provados / invocadores enumerados`; um invocador sem os dois bloqueia a entrega. Um
mutante apanhado não diz qual invocador ficou desprotegido — foi assim que três ficaram sem controlo
no seam do input (`stop`, `WM_HOOK_SYNC`, hook de teclado). Sotto: `_main/seam-inventory.json` (9
invocadores) + `_main/seam-coverage-oracle.py` (**9/9 PROVED**, o negativo tem de derrubar **aquele**
braço) + `_main/input-path-oracle.py` (10 braços / 10 mutantes).

### 10. Estados do bug, e "fixed" nunca é "verified"
*(manager `bug-hunt-workflow-approaches.md` §"Suggested states")*

`reported → reproduced → cause-isolated → fixed → verified → recurrence-watch`. Cada estado tem a sua
prova: `reproduced` = um ficheiro-fonte que contenha a evidência; `cause-isolated` = cápsula de
incidente no disco; `fixed` = um passo **da bateria** e o seu braço negativo; `verified` = instrumento
+ data + **verificador que não é o autor**; `recurrence-watch` = instrumento **e** janela.
Sotto: `_main/bug-ledger.json` + `_main/bug-ledger-oracle.py` (9/9 mutantes) e a cápsula
`_main/incidents/INC-20261023-01-mouse-hook.md`. Hoje o ledger imprime **FIXED, NOT VERIFIED** nos
dois bugs — e isso é o estado honesto, não uma falha do portão.

### 11. Nenhuma ferramenta de enforcement sem intenção declarada
*(manager §"Manager changes to consider": `blocked_bug_ids` + `evidence_unblocked`; consultgpt §"Concrete loop" 6–7)*

Trabalho de ferramenta só é elegível se remover um bloqueio **nomeado** de um bug; caso contrário é
trabalho de capacidade e **tem de o dizer**. Mecanicamente, cada `*oracle*.py`/`*-gate.py`/`*-guard.py`
de `_main` carrega no cabeçalho `# BLOCKS: BUG-…` (ids que existem no ledger) ou `# NO-BUG: <razão>`,
e a dívida antiga é um **ratchet** que não pode crescer. Medido em 2026-10-23: **165** ferramentas,
**5** declaradas, **160** no baseline, 0 vermelhas — e a nota de que a cobertura de mutantes não prova
completude fica escrita ao lado.

O laço completo (11 passos), os campos obrigatórios e os quatro portões estão no `AGENTS.md`,
secção **MODO BUG-HUNT — OBRIGATÓRIO**.

---

## Cobertura hoje (o que está mecanizado, e o que não está)

| lei | portão que a impõe |
|---|---|
| 1 evidência | `agents-md-pins-oracle.py`, o sumário `BATTERY-VERDICT`, `receipt-*.md` |
| 2 pode ficar vermelho | `--neg-arm` em 5+ oráculos; `red-as-expected-*` (23 passos) |
| 3 menor mecanismo | `battery-heavy-gate.py` (5/5 mutantes), `_stepcache-oracle.py` |
| 4 restrições antes | **parcial** — as HARD RULES são prosa; não há checker único |
| 5 fix on sight | `exception-hygiene-oracle.py` — **catraca** (4/4 mutantes): 40 sem razão em 11 ficheiros não podem crescer |
| 6 superfície do dono | `input-path-oracle.py` (6 braços, 4/4 mutantes) + `red-as-expected-input-path` |
| 7 subprocesso | **medido, ainda sem portão**: `subprocess.run` sem `timeout=` = **0** no produto (censo AST de 24 ficheiros); o que já está mecanizado: `mute-audio-oracle.py` e `battery-heavy-gate.py` |
| 8 jidoka | `_skip-verdict-guard.py`, o veredicto tri-estado da bateria (`GREEN` vs `GREEN WITH n SKIPPED`) |
| 9 cobertura por invocador | `seam-coverage-oracle.py` (9/9) sobre `seam-inventory.json` + `input-path-oracle.py` (10/10 mutantes) |
| 10 estados do bug | `bug-ledger-oracle.py` (9/9 mutantes) + a cápsula de incidente |
| 11 intenção da ferramenta | `tooling-intent-oracle.py` (4/4 mutantes + controlo positivo) sobre 165 ferramentas, baseline de 160 |

A linha 4 e a segunda metade da 7 são dívida declarada, não silêncio: um censo sem portão é um
relatório, e um relatório não impede o próximo erro.
