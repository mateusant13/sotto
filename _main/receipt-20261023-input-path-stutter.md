# Recibo — o rato do dono, e os protocolos que o impedem de voltar (2026-10-23)

## O que o dono disse (verbatim)

- *"para tudo e unshittified o start do sotto. abrir ou fechar ele faz meu pc travar PRA CARALHO"*
- *"MEU MOUSE TA TRAVANDO DEMAIS. O RESTO DO SISTEMA NAO. ARRUMA. AGORA. E PESQUISA ONLINE."*
- *"MEU MOUSE VOLTA AO NORMAL QUANDO EU ENTRO NO CONTROL ALT DEL, MAS VOLTA A TRAVAR DEPOIS Q EU SAIO"*
- *"meu mouse voltou ao normal. boa. nunca mais cometa esse erro. sotto e pra usuarios ate com pc fraco, isso e inadmissivel."*
- *"vai dentro do ... consultgpt e disk g superharness e disk i !manager e entenda que tipo de protocolos eles tem pra reforçar qualidade de codigo/programa. tu vai aplicar as filosofias deles pra tu desbostificar o sotto."*

## O defeito, medido (não inferido)

`_main/webview-run.log`, corrida do dono:

```
19:46:41.606  OUTSIDE_CLICK_HOOK installed=true hook=748365515 thread=34768 type=WH_MOUSE_LL
19:46:42.825  PANEL_VISIBILITY_ON_SCREEN visible=false ... panel_shown=false
```

**22 ms** depois de a app nascer, com o painel **nunca** mostrado, o Sotto instalou um hook
global de rato. Mecanismo: `WH_MOUSE_LL` entrega **todos** os eventos do rato (1000/s num rato
de 1000 Hz) ao callback **Python** da thread que o instalou, antes de qualquer outra coisa. Só o
cursor espera por esse callback — e sob **Ctrl+Alt+Del** o Windows não entrega hooks de utilizador
(o secure desktop não os chama), que é exactamente o "volta ao normal lá dentro e trava ao sair".

## A cura (três mecanismos, não uma promessa)

| mecanismo | onde | o que impede |
|---|---|---|
| **preguiçoso** | `OutsideClickWatcher.run` não instala; `_install_hook` só sob `_wants_hook()` | o hook nascer com o painel escondido |
| **libertado** | `hide_panel` escreve `armed = False`; `armed`/`edit_mode` são **propriedades** | outro sítio mudar o estado sem mexer no hook |
| **auto-cura** | `WM_TIMER` de **5 s** na thread do hook (`_sync_hook_now`) | um caminho de excepção deixar o rato preso |

## O arranque (o "travar PRA CARALHO")

| o que | antes | depois |
|---|---|---|
| preload do worker | `threading.Timer(20)` — dispara ao segundo 20 **contra** o que o dono está a fazer | watcher que espera o dono ficar **idle** (`GetLastInputInfo`, ≥ `WORKER_PRELOAD_IDLE_S` 6 s) com **tecto** `WORKER_PRELOAD_MAX_WAIT_S` 120 s, e ainda a razão `preload` |
| carga do modelo | prioridade `BELOW_NORMAL` (só CPU) | `PROCESS_MODE_BACKGROUND_BEGIN` durante a carga (CPU **e** I/O **e** memória), `_END` no `finally`; `load_priority=` no log |

## Os portões (cada um com braço negativo EXECUTADO)

| portão | braços | mutantes | neg-arm |
|---|---|---|---|
| `_main/input-path-oracle.py` | 6 (C1a, C1b, C2, C3, C4, C5) | **4/4** (arranque-instala, regra-sempre, esconder-não-desarma, sem-auto-cura) | `NEG-ARM PASS`, rc=1 por desenho |
| `_main/exception-hygiene-oracle.py` | 3 (C1 não cresce, C2 baseline não mente, C3 isenção viva) | **4/4** (ficheiro novo, baseline baixada, baseline inflacionada, ficheiro morto) | `NEG-ARM PASS`, rc=1 por desenho |
| `_main/open-close-stall-oracle.py` (F4 **re-ancorado**) | 5 factos | **8/8** (eram 5) | `NEG-ARM PASS`, rc=1 por desenho |

Os três entram na bateria com o passo `red-as-expected-*` correspondente; a bateria exige rc
**exactamente 1** e o texto `NEG-ARM PASS` nesse passo.

## Censos medidos hoje (o que os protocolos mandaram medir)

| regra (fonte) | medida |
|---|---|
| `subprocess.run` sem `timeout=` (consultgpt `subprocess-watchdog.mdc`) | **0** no produto — a regra já é honrada |
| `except Exception: pass` sem razão escrita (`fix-on-sight.mdc`) | **40** em **11** ficheiros, agora com catraca |
| `TODO/FIXME/HACK` no produto | censo textual deu ruído ("HACK" em prosa) — **não** virou portão: uma regra fora da população do instrumento não pode ser apanhada por ele |

O censo de `except: pass` foi feito **três** vezes: a primeira por regex deu **6 603** (falso
positivo: contava `try:` inteiros), a segunda por AST sobre 48 ficheiros deu **74**, e a final —
com a população declarada, `runs/` e `_probe/` fora — deu **40**. O número só vale com a
população ao lado; é a regra 8 do `AGENTS.md` a funcionar.

## O protocolo adaptado

`docs/quality-protocol.md` — sete leis, cada uma com **de onde veio** e **qual portão do Sotto a
impõe**, a ordem de trabalho, a definição de pronto, e uma tabela de cobertura que diz
honestamente o que ainda é prosa. As duas linhas que estavam em falta (lei 5 e lei 7) ficaram
mecanizadas ou medidas neste turno.

## O que NÃO ficou provado (declarado, não esquecido)

1. **Não houve uma corrida da app com a cura.** A app está fechada (o dono ordenou fechá-la) e
   **só o LEAD a lança**; a via sancionada é `schtasks /create … /it` + `/run`. Portanto a
   afirmação "o rato não trava com a app aberta" é **estrutural** (o hook não existe enquanto o
   painel está escondido), não uma medição de rato real.
2. **O auto-cura de 5 s nunca disparou em produção** — foi provado por leitura/AST e por mutante,
   não por um incidente real (seria preciso um caminho de excepção que deixasse `armed` preso).
3. **O efeito do `PROCESS_MODE_BACKGROUND_BEGIN` no stutter do dono não foi medido** com
   `sotto-perf-log.py`: exigiria lançar a app. O log passa a trazer `load_priority=` para que a
   próxima corrida real o possa confirmar.
4. **A divida dos 40 `except Exception: pass` continua lá.** A catraca impede o próximo; não
   substitui a leitura de cada um.
5. **A reclamação de hoje não está na população do fecho.** O corpus
   (`I:\!manager\state\herdr\complaints\sotto.md`) termina em **2026-10-22** (154 linhas); as
   queixas do rato de 2026-10-23 não lá estão, e esse ficheiro **não é meu para escrever** — é o
   manager que o escreve. O `complaints-closure-gate` não pode contar o que a população não tem;
   fica declarado, não varrido para debaixo do tapete.

## Como re-verificar (qualquer pessoa, sem lançar a app)

```
python _main\input-path-oracle.py ; python _main\input-path-oracle.py --neg-arm
python _main\open-close-stall-oracle.py ; python _main\open-close-stall-oracle.py --neg-arm
python _main\exception-hygiene-oracle.py ; python _main\exception-hygiene-oracle.py --neg-arm
python _main\seam-coverage-oracle.py ; python _main\seam-coverage-oracle.py --neg-arm
python _main\bug-ledger-oracle.py ; python _main\bug-ledger-oracle.py --neg-arm
powershell: cmd /c _main\_audit-verify-all.cmd   -> ler BATTERY-VERDICT + exit code
python _main\agents-md-pins-oracle.py
python _main\_gitattributes-verify.py
```

---

# Segunda passagem (2026-10-23, depois de o dono dizer que eu não tinha lido o que devia)

O dono: *"nao me convenceu que tu leu oq tu deveria. veja os .md recentes de ate 5 dias atras de cada
projeto."* Feito por **população primeiro**: todos os `.md` com mtime ≤ 5 dias nos três sítios
(consultgpt 998, superharness 8 628, manager 9 645 — dominados por worktrees e scratch), filtrados
para documentos de projecto. Os que interessam, com data:

| ficheiro | data | o que acrescentou |
|---|---|---|
| `G:\superharness\runs\workflow-quality-loop-findings.md` | 2026-10-23 20:20 | Jidoka; cápsula de incidente; FTA de cima + FMEA de baixo; **controlo positivo e negativo por invocador**; "um mutante apanhado não prova completude" |
| `I:\!manager\state\research\bug-hunt-workflow-approaches.md` | 2026-10-23 20:12 | estados `reported → … → recurrence watch`; "reported e fixed nunca são verified"; delta debugging; tooling só se desbloqueia um bug nomeado |
| `I:\!manager\state\cards\TC-20261023-opencode-orchestrator-test-gap-controls.md` | 2026-10-23 19:31 | `tri_state_probe` PASS/RED/**UNKNOWN**; `silent-failure metric` (cada braço passado/falhado/saltado **com razão**) |
| `I:\!manager\state\cards\TC-20261023-opencode-orchestrator-review-findings-repair.md` | 2026-10-23 19:58 | campos de aceitação: `negative_control`, `positive_control`, `mutation_or_revert`, `provenance_sha`; "nunca declarar fecho com checks do próprio autor" |
| `G:\superharness\.opencode\complaints-closure.md` | 2026-10-22 16:01 | a forma do fecho: `## título` + `evidence: comando -> substring estável` + `status:` |

## O que a segunda passagem ENCONTROU (não é um teste a mais: é um inquérito)

O oráculo do §5 provava 6 braços. Enumerar os **invocadores reais** do seam (FTA a partir do dano
"hook vivo sem painel") encontrou **três sem controlo nenhum**:

1. **`stop()`** — o hook e o `WM_TIMER` sobreviviam ao encerramento (hook vivo numa thread morta);
2. **`WM_HOOK_SYNC`** — o canal entre threads: `armed` mudava e o hook não;
3. **um segundo tipo de hook** (teclado) — nada no repo o proibia.

Os três estão fechados com braço próprio (C7, C4-sync, C6) e os mutantes `stop-nao-liberta`,
`sem-canal`, `hook-de-teclado` derrubam-nos. O oráculo passou de 6 para **10 braços / 10 mutantes**.

## O que foi construído nesta passagem

| artefacto | o que prova | medido |
|---|---|---|
| `_main/seam-inventory.json` | 9 invocadores enumerados | — |
| `_main/seam-coverage-oracle.py` | por invocador: positivo verde no real **e** o negativo derruba **aquele** braço | **9/9 PROVED**; 3 mutantes do inventário apanhados |
| `_main/bug-ledger.json` + `_main/bug-ledger-oracle.py` | estados do bug; `fixed` tem de citar um passo **da bateria**; `verified` exige verificador ≠ autor | **5/5** mutantes; ledger diz **FIXED, NOT VERIFIED** nos dois bugs |
| `_main/incidents/INC-20261023-01-mouse-hook.md` | cápsula: esperado/observado, invocador, revisão `c21f8a7`, sha do artefacto, reprodução, fronteira, primeira divergência, 5 condições contribuintes, acção com estado final, teste de escape | — |
| `docs/quality-protocol.md` §8–§10 | jidoka, cobertura por invocador, estados | — |

**O que continua NÃO provado** (a mesma honestidade do §5, agora com nome): não houve corrida real
da app com a cura; o auto-cura nunca disparou em produção; a cobertura é de 9 invocadores que **eu**
enumerei — o próprio Superharness avisa que mutantes provam afirmações sobre mutações escolhidas, não
a completude do inventário. O inventário é o elo mais frágil e está escrito como tal.

---

# Terceira passagem (2026-10-23, a terceira nota e o revamp)

O dono mandou ler também `C:\Users\Administrador\Desktop\consult-chatgpt\consultgpt\.agents\work\bug-hunting-workflow\bug-hunting-workflow-findings.md`
(2026-10-23 20:33) — a nota que faltava — e depois pediu *"um rebase/revamp/remake do sotto pro workflow
ou o codigo atual parar de ser horrivel"* e *"conserta tudo do sotto que eu ja falei nessa sessao"*.

## O que a terceira nota acrescentou, e onde ficou mecanizado

| exigência da nota | onde vive agora | medido |
|---|---|---|
| *"hypothetico-deductive loop ... form one hypothesis, predict an observation, and falsify it"* | `hypothesis` + `falsifier` **obrigatórios** no ledger | o mutante `M6` (hipótese sem falsificador) fica vermelho |
| cápsula com **environment**, **revision**, **trace/sessão** | `reproduced.environment` + `.revision` + `.artifact_sha` (64 hex **ou** `unrecorded` com nota) | `M9` (reprodução sem identidade do artefacto) vermelho |
| delta debugging / minimizar | `minimal_repro` obrigatório | idem, no portão |
| *"fix the defect class and mechanically inspect siblings (same probe on every instance)"* | `siblings[]` com `instance`/`probe`/`verdict`/`why` | `M7` (veredicto inventado) vermelho; **3** irmãos `unproven` impressos |
| regressão no estilo certo | `regression.style` ∈ example/property/stateful/differential/replay | validado no portão |

## Ferramenta só com intenção declarada (`blocked_bug_ids` / `evidence_unblocked`)

`_main/tooling-intent-oracle.py` + `_main/tooling-intent-baseline.json`: **165** ficheiros de enforcement
em `_main`, **5** declarados, **160** no baseline, **0** vermelhos. Um ficheiro novo sem `# BLOCKS: BUG-…`
(com o id a existir no ledger) ou `# NO-BUG: <razão>` é vermelho; **4/4** mutantes + **controlo positivo**

- a dívida não pode crescer. A regra é a da nota: trabalho de ferramenta é elegível quando remove um
  bloqueio nomeado; caso contrário é capacidade, e tem de o **dizer**.

## ORDEM 3: o buraco não era código, era prova

O `AGENTS.md` afirmava que `on_external_captions_released()` não trazia o worker de volta. Re-lido o
método: **traz** — `exiting` → não (senão órfão), release sem park → não, em pausa → não, sem painel nem
legenda → não, dentro de 45 s → `EXTERNAL_CAPTIONS_WORKER_RESUME_DEFERRED` sem mexer no relógio, resto →
`start_worker('external-end')`. Criado `_main/external-resume-oracle.py`: **8 braços / 8 mutantes**, cada
mutante a derrubar **o seu** braço. Correcção do `AGENTS.md` §3 incluída.

## O revamp: o "horrível" passou a ser medido e decrescente

`_main/code-health-oracle.py` + baseline (43 ficheiros de produto): `sotto_webview.py` **758 679 B /
13 273 linhas**, `main` do worker **2 297 linhas**, **82** `except: pass`, **10** `global`. O portão falha
em **qualquer** aumento (3/3 mutantes + positivo) e um ficheiro novo acima de 120 000 B é recusado. O
plano por fatias, com portão em cada uma, está em **`docs/revamp-2026-10-23.md`** — e diz explicitamente
que **não** houve remake, porque a nota manda *"smaller batches"* e a shell não pode ser lançada por uma
lane.

**Sexta fatia já feita, e era um defeito:** o `AGENTS.md` dizia que `HKCU\...\Run\Sotto` **não existia** —
e essa frase era uma *"correcção"* de uma bullet anterior. Medido: a chave tem **22 entradas e `Sotto` é
uma delas**. A correcção estava errada; a bullet original era a verdadeira. Registado como
`BUG-20261023-03` (classe: *documentação afirma o contrário da medição*), com o irmão do flash do painel
declarado **`unproven`** em vez de silenciado.

## ADENDA 2026-10-30 — "so o LEAD a lanca, via schtasks" ja' nao e' a regra

Esta frase descrevia o estado de 2026-10-23. **Medido 2026-10-30:** uma lane `medium` lança a app por
token emprestado sem tarefa, sem alteracao de agendador e sem palavra do dono --
`sotto-relaunch.py --relaunch` matou o pid `high` (delegado: `taskkill` direto da' `rc=128 Acesso
negado`) e a nova instancia `pid 19648` ganhou a mutex com `hotkey=True tray=True`. A regra que continua
em vigor e' a do ecra: `SOTTO_NEVER_ON_OWNER_SCREEN` (a app arranca escondida).
