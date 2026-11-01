# Lane TODO — sotto-lane-task-resolver-continuation

task: TC-20261025-cross-project-continuity
lane_id: sotto-lane-task-resolver-continuation
mission: Use Task Resolver v1.3 in sotto-lane and continue the project's existing accepted work with an immediately wired, falsifiable mechanical gate.
role: worker
target_access: Write-capable only for task-relevant files after inspecting the current dirty tree and existing TODO.
output_write: permitted
route_model_provider: Owner-requested OpenCode Go 1 DeepSeek V4.1 Flash; if no live response, try Go 2 through Go 6 in order, then MiniMax M3.1 through provider minimax only.
review_sequence: n/a for implementation lane; group any later review with same-subject work and use one paid reviewer per subject only after free review exhaustion.
review_inputs: [I:\!manager\state\work\TC-20261025-cross-project-continuity\owner-request.md sha256=44480fb7307c30f730c1f857bd548df00f532c6b640283bd8ed855e477638328]
withheld_inputs: [Unrelated uncommitted changes, Credentials and private user data]
target: H:\sotto task resolver invocation and current roadmap item
target_revision: HEAD=c21f8a751b188feec1594ff0f0b6745388b4b5fa; dirty path count=707; dirty path list sha256=ba593a7a080f035bf71972956bdde231c6dc55eb472e75059d90b3d8a0c1fe7c; see state\work\TC-20261025-cross-project-continuity\sotto-lane\source-manifest.json
workspace_root_id: H:\sotto
owned_paths: [., state/work/TC-20261025-cross-project-continuity/sotto-lane]
owned_branch_refs: []
deliverable_paths: [AGENTS.md, scripts/task-resolver-gate.py, scripts/test_task_resolver_gate.py, docs/roadmap.md, state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md]
todo_path: H:\sotto\state\work\TC-20261025-cross-project-continuity\sotto-lane\todo.md
not_owned: [.git and remote state, credentials and private user data, unrelated pre-existing changes, commits and pushes]
read_paths: [H:\sotto\AGENTS.md, H:\sotto\docs\roadmap.md, H:\sotto\.agents\skills\task-resolver\SKILL.md, I:\!manager\skills\task-resolver\SKILL.md, I:\!manager\skills\subagent-worklist\SKILL.md, state\work\TC-20261025-cross-project-continuity\sotto-lane\source-manifest.json]
context: [H:\sotto\AGENTS.md, H:\sotto\docs\roadmap.md, H:\sotto\.agents\skills\task-resolver\SKILL.md, I:\!manager\skills\task-resolver\SKILL.md, I:\!manager\skills\subagent-worklist\SKILL.md, state\work\TC-20261025-cross-project-continuity\sotto-lane\source-manifest.json, I:\!manager\state\work\TC-20261025-cross-project-continuity\owner-request.md]
relevant_skills: [I:\!manager\skills\task-resolver\SKILL.md v1.3.0: mandatory task workflow and immediate gate bootstrap, I:\!manager\skills\subagent-worklist\SKILL.md v1.1.4: editable TODO and delivery/closure proof]
acceptance: Use the current project TODO or roadmap; classify its chosen acceptance rows; wire a project-native deterministic gate before dependent product edits; prove positive and negative controls; deliver a real accepted-work slice and receipt.
falsifier: Any mechanical acceptance row can proceed without an executable gate and a falsifiable negative control, or the agent creates a second backlog instead of continuing existing project work.
budget: No tool-call or agent-count cap. Model first-output ceiling 300 seconds and wall ceiling 1800 seconds. Watcher lease must cover request plus cancellation and cleanup. Govern actual heavy local processes only. No commits or pushes.
receipt: H:\sotto\state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
controls: Positive: valid mechanical row and matching gate pass. Negative: remove the gate mapping or mutate the target invariant in isolation and require EXPECTED-RED at the intended assertion.
required_skill: I:\!manager\skills\subagent-worklist\SKILL.md v1.1.4
required_skill_sha256: 42f46db6dc138059ba8dd766906a8ea40c7f2bbb7086c574db1421e4f14f8203
dispatch_snapshot_ref: I:\!manager\state\work\TC-20261025-cross-project-continuity\owner-request.md@sha256:44480fb7307c30f730c1f857bd548df00f532c6b640283bd8ed855e477638328
required_ids: [C-01..C-15, W-01..W-04, T-01, T-02, T-03, T-04, T-05]

## Worklist
| order | id | title | status | receipt | parent_id | conditional | note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | C-01 | Mission field set confirmed | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-01@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | mission r0 line 5 confirmed |
| 2 | C-02 | Task read from its own artifacts | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-02@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | todo r0 + dispatch-snapshot + owner-request read |
| 3 | C-03 | Readiness basis recorded | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-03@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | route + ceilings recorded; actual route Go3 (receipt 11); no call/agent quota applied |
| 4 | C-04 | Context paths verified to exist | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-04@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | source-manifest.json absent; dirty set re-derived live |
| 5 | C-05 | Skill and TODO delivery verified | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-05@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | both skills by bytes+sha256, matched to declared digests |
| 6 | C-06 | Deliverable written at the exact declared path | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-06@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | all declared deliverable paths written |
| 7 | C-07 | Write-path discipline | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-07@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | 8 owned paths; no commit, no push, no app launch |
| 8 | C-08 | Acceptance executed | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-08@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | acceptance commands run with rcs, not prose |
| 9 | C-09 | Falsifier attempted | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-09@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | falsifier bit: battery-wired RED before wiring; own cure refuted |
| 10 | C-10 | Controls run where the claim is mechanical | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-10@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | true | controls run although conditional; 12 named arms |
| 11 | C-11 | Lane state reconciled | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-11@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | worklist statuses match the receipt evidence |
| 12 | C-12 | Change log appended for every worklist edit | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-12@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | one append-only change row per status change |
| 13 | C-13 | Done/blocked discipline | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-13@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | nothing done without a receipt; NOT RUN named |
| 14 | C-14 | Closure checked against dispatch snapshot | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-14@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | 24 rows = 15+4+5; strict replay quoted |
| 15 | C-15 | Hand-back receipt written | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-15@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | receipt ends in SELF-AUDIT |
| 16 | W-01 | Smallest change that satisfies acceptance | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-01@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | one gate, one oracle, one test, four steps, four edits |
| 17 | W-02 | Tests or checks written or updated per project rule | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-02@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | project native --neg-arm shape, no new harness |
| 18 | W-03 | Mutation or revert path exercised where the ticket requires it | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-03@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | true | 12 mutations on copies; real tree untouched |
| 19 | W-04 | No second source of truth introduced | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-04@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | skill digest pinned; baseline hash-keyed with code ceiling |
| 20 | T-01 | Read AGENTS and current TODO or roadmap then choose its next unfinished accepted item | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-01@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | P0.3 of roadmap-observability chosen; reason given |
| 21 | T-02 | Classify acceptance and wire a deterministic gate before dependent product edits | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-02@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | gate built and wired before the dependent edits |
| 22 | T-03 | Run positive and targeted negative controls and record intended gate verdicts | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-03@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | positive and named negative controls with intended verdicts |
| 23 | T-04 | Implement one highest-priority safe slice from the existing backlog and verify its real invoker | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-04@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | slice green under cmd.exe, red by design under neg-arm |
| 24 | T-05 | Write receipt and return the editable TODO with required SELF-AUDIT | done | state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-05@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354 | none | false | receipt + this TODO returned with change log |
| 25 | T-06 | P0.2 entregue: pagina de estado gerada com portao de nao-invencao | done | _main/receipt-20261025-p0-2-state-page.md#p02@sha256:b765664ea899a05a3f916311a61bebb5a9bdcc9e9032252b10abf72c99075113 | none | false | 8 checks / 8 mutantes NEG-ARM PASS; 2 passos always na bateria; pin re-medido |
| 26 | T-07 | P3.3 medido: custo do cache da bateria, com o numero do roadmap refutado | done | _main/receipt-20261025-p0-2-state-page.md#p33@sha256:b765664ea899a05a3f916311a61bebb5a9bdcc9e9032252b10abf72c99075113 | none | false | 63,3 ms/passo medidos (nao 0,33 s); resolvedor 2,6 %; corte -S nao aplicado |
| 27 | T-08 | P3.1 entregue: ratchet do wiring da bateria (oraculo novo sem passo e vermelho) | done | _main/receipt-20261025-p3-1-battery-wiring.md#p31@sha256:c4e793c03f04c60a411db4d21f46b281320e99d91a72b28b50c5bb7ef1d821bd | none | false | ratchet do wiring: 127 oraculos de enforcement, 90 sem passo; baseline pode so encolher; 7 checagens / mutantes nomeados |
| 28 | T-09 | P3.2 entregue: uma linha por reclamacao, o contraditorio do fecho declarado e cada `closed` com evidencia re-executavel | done | _main/receipt-20261025-p3-2-complaints-reconcile.md#p32@sha256:639e49ce9cb13ac9e2a88aeca1f12a5a67aac4be49742f2fee7b892f3e40e044 | none | false | 39 linhas do backlog contra 31 seccoes de fecho; 16 nao fechadas com `closure_gap` obrigatorio; o parser ingenuo perde o E1 (classe A-D) e o mutante prova-o |
| 29 | T-10 | P3.2-b: contradicoes reconciliadas contra a evidencia de hoje, veredicto da bateria lido e atribuido, e fecho por medicao com replay | done | _main/receipt-20261025-p3-2-complaints-reconcile.md#p32-reconcile@sha256:639e49ce9cb13ac9e2a88aeca1f12a5a67aac4be49742f2fee7b892f3e40e044 | none | false | escopo: bateria admitida sob lease heavy e veredicto lido (nao o rc de um passo), map v2 aplicado, C5/C6/B5/C13/C18 fechadas por medicao com closer re-executavel, as restantes contradicoes com gap redesenhado a partir da evidencia de hoje, e o vermelho da bateria atribuido ficheiro a ficheiro |
| 30 | T-11 | P3.2-b2: os seis passos pesados inventariados e o subconjunto headless recusado pelo portao de performance (NOT RUN, nao verde) | done | _main/receipt-20261025-p3-2b-heavy-inventory.md#p32-heavy@sha256:fbe505fefc48741f8665d6aa54a163d4822617c8c9ba0fa22712a68b1ba1b2e8 | none | false | 5 headless (4 strip + panel-exit3 --unit) e 1 interactivo (mute-audio, dispositivo de audio do dono); guardas medidas: lane-screen-gate PASS, Local/Global SottoShell FREE, panel-state.json de 24/10; lease heavy RECUSADO com state=amber (heavy-requires-green) e nenhum passo largado; comando pronto e snapshot da geometria guardado |
| 31 | T-12 | 1:1 do YouTube medido no payload: palavras, quebras e timing verdes em 677 amostras, a revelacao palavra-a-palavra vermelha (69 offsets no payload, 0 nos cues) e o check ligado a bateria com 7 mutantes | done | _main/receipt-20261026-live-1to1-edge.md#sampler-seek@sha256:960DA79480CF404AFD24E16C22D7F74A1EF4C72110894F0D042C71926B69EBE1 | none | false | metade viva medida 16/16 no Edge proprio (recibo live-1to1-edge) e o amostrador passou a saltar por SEEK_JS (:657) antes da leitura (:662); relay 9224 DOWN; medicao pos-fix e --selfcheck DIFERIDOS (Gaming), nao contados como portao; arranques a frio e Alt+C real NAO verificados |
| 32 | T-13 | Revelacao palavra-a-palavra do YouTube fechada: o cue carrega o tOffsetMs do payload, o prefixo revelado bate 677/677 (era 388/677) e a arm reveal-wired le o caminho vivo | done | _main/receipt-20261026-youtube-1to1-reveal.md#reveal@sha256:4FEA1B2E2AD713B79E37FC8E0716CC4D9D68451E3C8FEAD2B3EB0E907B936DE6 | none | false | 7 arms verdes, 9 mutantes each-by-named-arm; cache reconstruida com proveniencia; NAO verificado: ecra (relay 9224 DOWN), latencia do poll de 300 ms, dois arranques a frio (lease AMBER 86.0%), Alt+C real; achado nao corrigido: _tick usa lines[-1] e deita fora a segunda linha da janela |
| 33 | T-14 | Proveniencia de ROTA fechada por medicao: o recibo declara a rota que correu (providerID=opencode-go-3), nao a que a politica sonda primeiro, e um portao fica vermelho quando as duas divergem | done | _main/receipt-20261026-receipt-provenance.md#2-the-instrument-that-settles-a-route-and-the-one-that-cannot@sha256:3d2ad9b27b40a8ffe2ba290991d6a3607a6393a4d730d597becb2c0862c591de | none | false | o defeito: receipt.md:4 dizia OpenCode Go 1 e o processo que o escreveu corria em opencode-go-3; instrumento novo e re-executavel: session_v2.model por contencao do instante de criacao do recibo (1 janela de 613.3 s, as outras duas fecharam em 2.4 s e 0.9 s); portao com 4 checks e 4 bracos nomeados, vermelho primeiro nos bytes reais; battery-wiring vermelho PRE-EXISTENTE (125 vs 124); passos NAO CORRIDOS: a bateria nunca correu |

## Change log
changes:
- revision: r1
  item_id: C-01
  action: status
  before: '{"id": "C-01", "title": "Mission field set confirmed", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-01", "title": "Mission field set confirmed", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-01@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "mission r0 line 5 confirmed"}'
  before_order: 1
  after_order: 1
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-01'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r2
  item_id: C-02
  action: status
  before: '{"id": "C-02", "title": "Task read from its own artifacts", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-02", "title": "Task read from its own artifacts", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-02@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "todo r0 + dispatch-snapshot + owner-request read"}'
  before_order: 2
  after_order: 2
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-02'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r3
  item_id: C-03
  action: status
  before: '{"id": "C-03", "title": "Readiness basis recorded", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-03", "title": "Readiness basis recorded", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-03@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "route and ceilings recorded; no call/agent quota applied"}'
  before_order: 3
  after_order: 3
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-03'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r4
  item_id: C-04
  action: status
  before: '{"id": "C-04", "title": "Context paths verified to exist", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-04", "title": "Context paths verified to exist", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-04@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "source-manifest.json absent; dirty set re-derived live"}'
  before_order: 4
  after_order: 4
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-04'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r5
  item_id: C-05
  action: status
  before: '{"id": "C-05", "title": "Skill and TODO delivery verified", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-05", "title": "Skill and TODO delivery verified", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-05@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "both skills by bytes+sha256, matched to declared digests"}'
  before_order: 5
  after_order: 5
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-05'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r6
  item_id: C-06
  action: status
  before: '{"id": "C-06", "title": "Deliverable written at the exact declared path", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-06", "title": "Deliverable written at the exact declared path", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-06@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "all declared deliverable paths written"}'
  before_order: 6
  after_order: 6
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-06'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r7
  item_id: C-07
  action: status
  before: '{"id": "C-07", "title": "Write-path discipline", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-07", "title": "Write-path discipline", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-07@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "8 owned paths; no commit, no push, no app launch"}'
  before_order: 7
  after_order: 7
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-07'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r8
  item_id: C-08
  action: status
  before: '{"id": "C-08", "title": "Acceptance executed", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-08", "title": "Acceptance executed", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-08@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "acceptance commands run with rcs, not prose"}'
  before_order: 8
  after_order: 8
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-08'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r9
  item_id: C-09
  action: status
  before: '{"id": "C-09", "title": "Falsifier attempted", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-09", "title": "Falsifier attempted", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-09@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "falsifier bit: battery-wired RED before wiring; own cure refuted"}'
  before_order: 9
  after_order: 9
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-09'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r10
  item_id: C-10
  action: status
  before: '{"id": "C-10", "title": "Controls run where the claim is mechanical", "status": "open", "receipt": "none", "parent_id": "none", "conditional": true, "note": ""}'
  after: '{"id": "C-10", "title": "Controls run where the claim is mechanical", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-10@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": true, "note": "controls run although conditional; 12 named arms"}'
  before_order: 10
  after_order: 10
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-10'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r11
  item_id: C-11
  action: status
  before: '{"id": "C-11", "title": "Lane state reconciled", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-11", "title": "Lane state reconciled", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-11@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "worklist statuses match the receipt evidence"}'
  before_order: 11
  after_order: 11
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-11'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r12
  item_id: C-12
  action: status
  before: '{"id": "C-12", "title": "Change log appended for every worklist edit", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-12", "title": "Change log appended for every worklist edit", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-12@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "one append-only change row per status change"}'
  before_order: 12
  after_order: 12
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-12'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r13
  item_id: C-13
  action: status
  before: '{"id": "C-13", "title": "Done/blocked discipline", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-13", "title": "Done/blocked discipline", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-13@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "nothing done without a receipt; NOT RUN named"}'
  before_order: 13
  after_order: 13
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-13'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r14
  item_id: C-14
  action: status
  before: '{"id": "C-14", "title": "Closure checked against dispatch snapshot", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-14", "title": "Closure checked against dispatch snapshot", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-14@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "24 rows = 15+4+5; strict replay quoted"}'
  before_order: 14
  after_order: 14
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-14'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r15
  item_id: C-15
  action: status
  before: '{"id": "C-15", "title": "Hand-back receipt written", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "C-15", "title": "Hand-back receipt written", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-15@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "receipt ends in SELF-AUDIT"}'
  before_order: 15
  after_order: 15
  child_ids: []
  reason: 'status open -> done with the receipt anchor for C-15'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r16
  item_id: W-01
  action: status
  before: '{"id": "W-01", "title": "Smallest change that satisfies acceptance", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "W-01", "title": "Smallest change that satisfies acceptance", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-01@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "one gate, one oracle, one test, four steps, four edits"}'
  before_order: 16
  after_order: 16
  child_ids: []
  reason: 'status open -> done with the receipt anchor for W-01'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r17
  item_id: W-02
  action: status
  before: '{"id": "W-02", "title": "Tests or checks written or updated per project rule", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "W-02", "title": "Tests or checks written or updated per project rule", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-02@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "project native --neg-arm shape, no new harness"}'
  before_order: 17
  after_order: 17
  child_ids: []
  reason: 'status open -> done with the receipt anchor for W-02'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r18
  item_id: W-03
  action: status
  before: '{"id": "W-03", "title": "Mutation or revert path exercised where the ticket requires it", "status": "open", "receipt": "none", "parent_id": "none", "conditional": true, "note": ""}'
  after: '{"id": "W-03", "title": "Mutation or revert path exercised where the ticket requires it", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-03@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": true, "note": "12 mutations on copies; real tree untouched"}'
  before_order: 18
  after_order: 18
  child_ids: []
  reason: 'status open -> done with the receipt anchor for W-03'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r19
  item_id: W-04
  action: status
  before: '{"id": "W-04", "title": "No second source of truth introduced", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "W-04", "title": "No second source of truth introduced", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-04@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "skill digest pinned; baseline hash-keyed with code ceiling"}'
  before_order: 19
  after_order: 19
  child_ids: []
  reason: 'status open -> done with the receipt anchor for W-04'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r20
  item_id: T-01
  action: status
  before: '{"id": "T-01", "title": "Read AGENTS and current TODO or roadmap then choose its next unfinished accepted item", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "T-01", "title": "Read AGENTS and current TODO or roadmap then choose its next unfinished accepted item", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-01@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "P0.3 of roadmap-observability chosen; reason given"}'
  before_order: 20
  after_order: 20
  child_ids: []
  reason: 'status open -> done with the receipt anchor for T-01'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r21
  item_id: T-02
  action: status
  before: '{"id": "T-02", "title": "Classify acceptance and wire a deterministic gate before dependent product edits", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "T-02", "title": "Classify acceptance and wire a deterministic gate before dependent product edits", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-02@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "gate built and wired before the dependent edits"}'
  before_order: 21
  after_order: 21
  child_ids: []
  reason: 'status open -> done with the receipt anchor for T-02'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r22
  item_id: T-03
  action: status
  before: '{"id": "T-03", "title": "Run positive and targeted negative controls and record intended gate verdicts", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "T-03", "title": "Run positive and targeted negative controls and record intended gate verdicts", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-03@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "positive and named negative controls with intended verdicts"}'
  before_order: 22
  after_order: 22
  child_ids: []
  reason: 'status open -> done with the receipt anchor for T-03'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r23
  item_id: T-04
  action: status
  before: '{"id": "T-04", "title": "Implement one highest-priority safe slice from the existing backlog and verify its real invoker", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "T-04", "title": "Implement one highest-priority safe slice from the existing backlog and verify its real invoker", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-04@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "slice green under cmd.exe, red by design under neg-arm"}'
  before_order: 23
  after_order: 23
  child_ids: []
  reason: 'status open -> done with the receipt anchor for T-04'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r24
  item_id: T-05
  action: status
  before: '{"id": "T-05", "title": "Write receipt and return the editable TODO with required SELF-AUDIT", "status": "open", "receipt": "none", "parent_id": "none", "conditional": false, "note": ""}'
  after: '{"id": "T-05", "title": "Write receipt and return the editable TODO with required SELF-AUDIT", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-05@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "receipt + this TODO returned with change log"}'
  before_order: 24
  after_order: 24
  child_ids: []
  reason: 'status open -> done with the receipt anchor for T-05'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r25
  item_id: C-01
  action: status
  before: '{"id": "C-01", "title": "Mission field set confirmed", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-01@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "mission r0 line 5 confirmed"}'
  after: '{"id": "C-01", "title": "Mission field set confirmed", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-01@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "mission r0 line 5 confirmed"}'
  before_order: 1
  after_order: 1
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r26
  item_id: C-02
  action: status
  before: '{"id": "C-02", "title": "Task read from its own artifacts", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-02@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "todo r0 + dispatch-snapshot + owner-request read"}'
  after: '{"id": "C-02", "title": "Task read from its own artifacts", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-02@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "todo r0 + dispatch-snapshot + owner-request read"}'
  before_order: 2
  after_order: 2
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r27
  item_id: C-03
  action: status
  before: '{"id": "C-03", "title": "Readiness basis recorded", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-03@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "route and ceilings recorded; no call/agent quota applied"}'
  after: '{"id": "C-03", "title": "Readiness basis recorded", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-03@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "route + ceilings recorded; actual route Go3 (receipt 11); no call/agent quota applied"}'
  before_order: 3
  after_order: 3
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r28
  item_id: C-04
  action: status
  before: '{"id": "C-04", "title": "Context paths verified to exist", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-04@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "source-manifest.json absent; dirty set re-derived live"}'
  after: '{"id": "C-04", "title": "Context paths verified to exist", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-04@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "source-manifest.json absent; dirty set re-derived live"}'
  before_order: 4
  after_order: 4
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r29
  item_id: C-05
  action: status
  before: '{"id": "C-05", "title": "Skill and TODO delivery verified", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-05@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "both skills by bytes+sha256, matched to declared digests"}'
  after: '{"id": "C-05", "title": "Skill and TODO delivery verified", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-05@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "both skills by bytes+sha256, matched to declared digests"}'
  before_order: 5
  after_order: 5
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r30
  item_id: C-06
  action: status
  before: '{"id": "C-06", "title": "Deliverable written at the exact declared path", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-06@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "all declared deliverable paths written"}'
  after: '{"id": "C-06", "title": "Deliverable written at the exact declared path", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-06@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "all declared deliverable paths written"}'
  before_order: 6
  after_order: 6
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r31
  item_id: C-07
  action: status
  before: '{"id": "C-07", "title": "Write-path discipline", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-07@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "8 owned paths; no commit, no push, no app launch"}'
  after: '{"id": "C-07", "title": "Write-path discipline", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-07@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "8 owned paths; no commit, no push, no app launch"}'
  before_order: 7
  after_order: 7
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r32
  item_id: C-08
  action: status
  before: '{"id": "C-08", "title": "Acceptance executed", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-08@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "acceptance commands run with rcs, not prose"}'
  after: '{"id": "C-08", "title": "Acceptance executed", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-08@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "acceptance commands run with rcs, not prose"}'
  before_order: 8
  after_order: 8
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r33
  item_id: C-09
  action: status
  before: '{"id": "C-09", "title": "Falsifier attempted", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-09@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "falsifier bit: battery-wired RED before wiring; own cure refuted"}'
  after: '{"id": "C-09", "title": "Falsifier attempted", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-09@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "falsifier bit: battery-wired RED before wiring; own cure refuted"}'
  before_order: 9
  after_order: 9
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r34
  item_id: C-10
  action: status
  before: '{"id": "C-10", "title": "Controls run where the claim is mechanical", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-10@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": true, "note": "controls run although conditional; 12 named arms"}'
  after: '{"id": "C-10", "title": "Controls run where the claim is mechanical", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-10@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": true, "note": "controls run although conditional; 12 named arms"}'
  before_order: 10
  after_order: 10
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r35
  item_id: C-11
  action: status
  before: '{"id": "C-11", "title": "Lane state reconciled", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-11@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "worklist statuses match the receipt evidence"}'
  after: '{"id": "C-11", "title": "Lane state reconciled", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-11@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "worklist statuses match the receipt evidence"}'
  before_order: 11
  after_order: 11
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r36
  item_id: C-12
  action: status
  before: '{"id": "C-12", "title": "Change log appended for every worklist edit", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-12@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "one append-only change row per status change"}'
  after: '{"id": "C-12", "title": "Change log appended for every worklist edit", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-12@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "one append-only change row per status change"}'
  before_order: 12
  after_order: 12
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r37
  item_id: C-13
  action: status
  before: '{"id": "C-13", "title": "Done/blocked discipline", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-13@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "nothing done without a receipt; NOT RUN named"}'
  after: '{"id": "C-13", "title": "Done/blocked discipline", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-13@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "nothing done without a receipt; NOT RUN named"}'
  before_order: 13
  after_order: 13
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r38
  item_id: C-14
  action: status
  before: '{"id": "C-14", "title": "Closure checked against dispatch snapshot", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-14@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "24 rows = 15+4+5; strict replay quoted"}'
  after: '{"id": "C-14", "title": "Closure checked against dispatch snapshot", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-14@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "24 rows = 15+4+5; strict replay quoted"}'
  before_order: 14
  after_order: 14
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r39
  item_id: C-15
  action: status
  before: '{"id": "C-15", "title": "Hand-back receipt written", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-15@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "receipt ends in SELF-AUDIT"}'
  after: '{"id": "C-15", "title": "Hand-back receipt written", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-15@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "receipt ends in SELF-AUDIT"}'
  before_order: 15
  after_order: 15
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r40
  item_id: W-01
  action: status
  before: '{"id": "W-01", "title": "Smallest change that satisfies acceptance", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-01@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "one gate, one oracle, one test, four steps, four edits"}'
  after: '{"id": "W-01", "title": "Smallest change that satisfies acceptance", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-01@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "one gate, one oracle, one test, four steps, four edits"}'
  before_order: 16
  after_order: 16
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r41
  item_id: W-02
  action: status
  before: '{"id": "W-02", "title": "Tests or checks written or updated per project rule", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-02@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "project native --neg-arm shape, no new harness"}'
  after: '{"id": "W-02", "title": "Tests or checks written or updated per project rule", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-02@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "project native --neg-arm shape, no new harness"}'
  before_order: 17
  after_order: 17
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r42
  item_id: W-03
  action: status
  before: '{"id": "W-03", "title": "Mutation or revert path exercised where the ticket requires it", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-03@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": true, "note": "12 mutations on copies; real tree untouched"}'
  after: '{"id": "W-03", "title": "Mutation or revert path exercised where the ticket requires it", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-03@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": true, "note": "12 mutations on copies; real tree untouched"}'
  before_order: 18
  after_order: 18
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r43
  item_id: W-04
  action: status
  before: '{"id": "W-04", "title": "No second source of truth introduced", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-04@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "skill digest pinned; baseline hash-keyed with code ceiling"}'
  after: '{"id": "W-04", "title": "No second source of truth introduced", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-04@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "skill digest pinned; baseline hash-keyed with code ceiling"}'
  before_order: 19
  after_order: 19
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r44
  item_id: T-01
  action: status
  before: '{"id": "T-01", "title": "Read AGENTS and current TODO or roadmap then choose its next unfinished accepted item", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-01@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "P0.3 of roadmap-observability chosen; reason given"}'
  after: '{"id": "T-01", "title": "Read AGENTS and current TODO or roadmap then choose its next unfinished accepted item", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-01@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "P0.3 of roadmap-observability chosen; reason given"}'
  before_order: 20
  after_order: 20
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r45
  item_id: T-02
  action: status
  before: '{"id": "T-02", "title": "Classify acceptance and wire a deterministic gate before dependent product edits", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-02@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "gate built and wired before the dependent edits"}'
  after: '{"id": "T-02", "title": "Classify acceptance and wire a deterministic gate before dependent product edits", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-02@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "gate built and wired before the dependent edits"}'
  before_order: 21
  after_order: 21
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r46
  item_id: T-03
  action: status
  before: '{"id": "T-03", "title": "Run positive and targeted negative controls and record intended gate verdicts", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-03@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "positive and named negative controls with intended verdicts"}'
  after: '{"id": "T-03", "title": "Run positive and targeted negative controls and record intended gate verdicts", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-03@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "positive and named negative controls with intended verdicts"}'
  before_order: 22
  after_order: 22
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r47
  item_id: T-04
  action: status
  before: '{"id": "T-04", "title": "Implement one highest-priority safe slice from the existing backlog and verify its real invoker", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-04@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "slice green under cmd.exe, red by design under neg-arm"}'
  after: '{"id": "T-04", "title": "Implement one highest-priority safe slice from the existing backlog and verify its real invoker", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-04@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "slice green under cmd.exe, red by design under neg-arm"}'
  before_order: 23
  after_order: 23
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r48
  item_id: T-05
  action: status
  before: '{"id": "T-05", "title": "Write receipt and return the editable TODO with required SELF-AUDIT", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-05@sha256:bcfa52fec2f1b72d35b707d4a4d88db4fb0676639c5b68af239fdd1fd994ca43", "parent_id": "none", "conditional": false, "note": "receipt + this TODO returned with change log"}'
  after: '{"id": "T-05", "title": "Write receipt and return the editable TODO with required SELF-AUDIT", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-05@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "receipt + this TODO returned with change log"}'
  before_order: 24
  after_order: 24
  child_ids: []
  reason: 'rebind the receipt digest to the final receipt bytes after the Go3 provenance correction: receipt 11, 24 done rows, one pass'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r49
  item_id: T-06
  action: add
  before: none
  after: '{"id": "T-06", "title": "P0.2 entregue: pagina de estado gerada com portao de nao-invencao", "status": "done", "receipt": "_main/receipt-20261025-p0-2-state-page.md#p02@sha256:86f9dd2364cac7cff1e998222a67d4b30a41d4f8b27264c86a27131d71a53a59", "parent_id": "none", "conditional": false, "note": "8 checks / 8 mutantes NEG-ARM PASS; 2 passos always na bateria; pin re-medido"}'
  before_order: none
  after_order: 25
  child_ids: []
  reason: 'continuacao do trabalho aceite: P0.2 entregue e P3.3 medido; registo unico e a linha do roadmap, sem segundo backlog'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p0-2-state-page.md
- revision: r50
  item_id: T-07
  action: add
  before: none
  after: '{"id": "T-07", "title": "P3.3 medido: custo do cache da bateria, com o numero do roadmap refutado", "status": "done", "receipt": "_main/receipt-20261025-p0-2-state-page.md#p33@sha256:86f9dd2364cac7cff1e998222a67d4b30a41d4f8b27264c86a27131d71a53a59", "parent_id": "none", "conditional": false, "note": "63,3 ms/passo medidos (nao 0,33 s); resolvedor 2,6 %; corte -S nao aplicado"}'
  before_order: none
  after_order: 26
  child_ids: []
  reason: 'continuacao do trabalho aceite: P0.2 entregue e P3.3 medido; registo unico e a linha do roadmap, sem segundo backlog'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p0-2-state-page.md
- revision: r51
  item_id: T-06
  action: status
  before: '{"id": "T-06", "title": "P0.2 entregue: pagina de estado gerada com portao de nao-invencao", "status": "done", "receipt": "_main/receipt-20261025-p0-2-state-page.md#p02@sha256:86f9dd2364cac7cff1e998222a67d4b30a41d4f8b27264c86a27131d71a53a59", "parent_id": "none", "conditional": false, "note": "8 checks / 8 mutantes NEG-ARM PASS; 2 passos always na bateria; pin re-medido"}'
  after: '{"id": "T-06", "title": "P0.2 entregue: pagina de estado gerada com portao de nao-invencao", "status": "done", "receipt": "_main/receipt-20261025-p0-2-state-page.md#p02@sha256:b765664ea899a05a3f916311a61bebb5a9bdcc9e9032252b10abf72c99075113", "parent_id": "none", "conditional": false, "note": "8 checks / 8 mutantes NEG-ARM PASS; 2 passos always na bateria; pin re-medido"}'
  before_order: 25
  after_order: 25
  child_ids: []
  reason: 'rebind do digest do recibo depois da passagem de refutacao (dois achados curados: cells-match-record e SELF_STEPS); o digest antigo era 86f9dd2364ca'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p0-2-state-page.md
- revision: r52
  item_id: T-07
  action: status
  before: '{"id": "T-07", "title": "P3.3 medido: custo do cache da bateria, com o numero do roadmap refutado", "status": "done", "receipt": "_main/receipt-20261025-p0-2-state-page.md#p33@sha256:86f9dd2364cac7cff1e998222a67d4b30a41d4f8b27264c86a27131d71a53a59", "parent_id": "none", "conditional": false, "note": "63,3 ms/passo medidos (nao 0,33 s); resolvedor 2,6 %; corte -S nao aplicado"}'
  after: '{"id": "T-07", "title": "P3.3 medido: custo do cache da bateria, com o numero do roadmap refutado", "status": "done", "receipt": "_main/receipt-20261025-p0-2-state-page.md#p33@sha256:b765664ea899a05a3f916311a61bebb5a9bdcc9e9032252b10abf72c99075113", "parent_id": "none", "conditional": false, "note": "63,3 ms/passo medidos (nao 0,33 s); resolvedor 2,6 %; corte -S nao aplicado"}'
  before_order: 26
  after_order: 26
  child_ids: []
  reason: 'rebind do digest do recibo depois da passagem de refutacao (dois achados curados: cells-match-record e SELF_STEPS); o digest antigo era 86f9dd2364ca'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p0-2-state-page.md
- revision: r53
  item_id: T-08
  action: add
  before: none
  after: '{"id": "T-08", "title": "P3.1 entregue: ratchet do wiring da bateria (oraculo novo sem passo e vermelho)", "status": "doing", "receipt": "none", "parent_id": "none", "conditional": false, "note": "ratchet do wiring: 127 oraculos de enforcement, 90 sem passo; baseline pode so encolher; 7 checagens / mutantes nomeados"}'
  before_order: none
  after_order: 27
  child_ids: []
  reason: 'P3.1: registo antes da edicao dependente e fecho com recibo proprio'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p3-1-battery-wiring.md
- revision: r54
  item_id: T-08
  action: status
  before: {"id": "T-08", "title": "P3.1 entregue: ratchet do wiring da bateria (oraculo novo sem passo e vermelho)", "status": "doing", "receipt": "none", "parent_id": "none", "conditional": false, "note": "ratchet do wiring: 127 oraculos de enforcement, 90 sem passo; baseline pode so encolher; 7 checagens / mutantes nomeados"}
  after: '{"id": "T-08", "title": "P3.1 entregue: ratchet do wiring da bateria (oraculo novo sem passo e vermelho)", "status": "done", "receipt": "_main/receipt-20261025-p3-1-battery-wiring.md#p31@sha256:c4e793c03f04c60a411db4d21f46b281320e99d91a72b28b50c5bb7ef1d821bd", "parent_id": "none", "conditional": false, "note": "ratchet do wiring: 127 oraculos de enforcement, 90 sem passo; baseline pode so encolher; 7 checagens / mutantes nomeados"}'
  before_order: 27
  after_order: 27
  child_ids: []
  reason: 'P3.1: registo antes da edicao dependente e fecho com recibo proprio'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p3-1-battery-wiring.md
- revision: r55
  item_id: T-09
  action: add
  before: none
  after: '{"id": "T-09", "title": "P3.2 entregue: uma linha por reclamacao, o contraditorio do fecho declarado e cada `closed` com evidencia re-executavel", "status": "doing", "receipt": "none", "parent_id": "none", "conditional": false, "note": "39 linhas do backlog contra 31 seccoes de fecho; 16 nao fechadas com `closure_gap` obrigatorio; o parser ingenuo perde o E1 (classe A-D) e o mutante prova-o"}'
  before_order: none
  after_order: 28
  child_ids: []
  reason: 'P3.2: registo antes das edicoes dependentes e fecho com recibo proprio'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p3-2-complaints-reconcile.md
- revision: r56
  item_id: T-09
  action: status
  before: '{"id": "T-09", "title": "P3.2 entregue: uma linha por reclamacao, o contraditorio do fecho declarado e cada `closed` com evidencia re-executavel", "status": "doing", "receipt": "none", "parent_id": "none", "conditional": false, "note": "39 linhas do backlog contra 31 seccoes de fecho; 16 nao fechadas com `closure_gap` obrigatorio; o parser ingenuo perde o E1 (classe A-D) e o mutante prova-o"}'
  after: '{"id": "T-09", "title": "P3.2 entregue: uma linha por reclamacao, o contraditorio do fecho declarado e cada `closed` com evidencia re-executavel", "status": "done", "receipt": "_main/receipt-20261025-p3-2-complaints-reconcile.md#p32@sha256:7e1995d2cee85ae77a839c580229764e233b13cd56eec479b55f50d484f69d78", "parent_id": "none", "conditional": false, "note": "39 linhas do backlog contra 31 seccoes de fecho; 16 nao fechadas com `closure_gap` obrigatorio; o parser ingenuo perde o E1 (classe A-D) e o mutante prova-o"}'
  before_order: 28
  after_order: 28
  child_ids: []
  reason: 'P3.2: registo antes das edicoes dependentes e fecho com recibo proprio'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p3-2-complaints-reconcile.md
- revision: r57
  item_id: T-10
  action: add
  before: none
  after: '{"id": "T-10", "title": "P3.2-b: contradicoes reconciliadas contra a evidencia de hoje, veredicto da bateria lido e atribuido, e fecho por medicao com replay", "status": "doing", "receipt": "none", "parent_id": "none", "conditional": false, "note": "escopo: bateria admitida sob lease heavy e veredicto lido (nao o rc de um passo), map v2 aplicado, C5/C6/B5/C13/C18 fechadas por medicao com closer re-executavel, as restantes contradicoes com gap redesenhado a partir da evidencia de hoje, e o vermelho da bateria atribuido ficheiro a ficheiro"}'
  before_order: none
  after_order: 29
  child_ids: []
  reason: 'P3.2-b: registo antes das edicoes dependentes (mapa e recibo)'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p3-2-complaints-reconcile.md
- revision: r58
  item_id: T-10
  action: status
  before: '{"id": "T-10", "title": "P3.2-b: contradicoes reconciliadas contra a evidencia de hoje, veredicto da bateria lido e atribuido, e fecho por medicao com replay", "status": "doing", "receipt": "none", "parent_id": "none", "conditional": false, "note": "escopo: bateria admitida sob lease heavy e veredicto lido (nao o rc de um passo), map v2 aplicado, C5/C6/B5/C13/C18 fechadas por medicao com closer re-executavel, as restantes contradicoes com gap redesenhado a partir da evidencia de hoje, e o vermelho da bateria atribuido ficheiro a ficheiro"}'
  after: '{"id": "T-10", "title": "P3.2-b: contradicoes reconciliadas contra a evidencia de hoje, veredicto da bateria lido e atribuido, e fecho por medicao com replay", "status": "done", "receipt": "_main/receipt-20261025-p3-2-complaints-reconcile.md#p32-reconcile@sha256:639e49ce9cb13ac9e2a88aeca1f12a5a67aac4be49742f2fee7b892f3e40e044", "parent_id": "none", "conditional": false, "note": "escopo: bateria admitida sob lease heavy e veredicto lido (nao o rc de um passo), map v2 aplicado, C5/C6/B5/C13/C18 fechadas por medicao com closer re-executavel, as restantes contradicoes com gap redesenhado a partir da evidencia de hoje, e o vermelho da bateria atribuido ficheiro a ficheiro"}'
  before_order: 29
  after_order: 29
  child_ids: []
  reason: 'P3.2-b: fecho do item com o recibo e o veredicto da bateria lido e atribuido'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p3-2-complaints-reconcile.md
- revision: r59
  item_id: T-09
  action: status
  before: '{"id": "T-09", "title": "P3.2 entregue: uma linha por reclamacao, o contraditorio do fecho declarado e cada `closed` com evidencia re-executavel", "status": "done", "receipt": "_main/receipt-20261025-p3-2-complaints-reconcile.md#p32@sha256:7e1995d2cee85ae77a839c580229764e233b13cd56eec479b55f50d484f69d78", "parent_id": "none", "conditional": false, "note": "39 linhas do backlog contra 31 seccoes de fecho; 16 nao fechadas com `closure_gap` obrigatorio; o parser ingenuo perde o E1 (classe A-D) e o mutante prova-o"}'
  after: '{"id": "T-09", "title": "P3.2 entregue: uma linha por reclamacao, o contraditorio do fecho declarado e cada `closed` com evidencia re-executavel", "status": "done", "receipt": "_main/receipt-20261025-p3-2-complaints-reconcile.md#p32@sha256:639e49ce9cb13ac9e2a88aeca1f12a5a67aac4be49742f2fee7b892f3e40e044", "parent_id": "none", "conditional": false, "note": "39 linhas do backlog contra 31 seccoes de fecho; 16 nao fechadas com `closure_gap` obrigatorio; o parser ingenuo perde o E1 (classe A-D) e o mutante prova-o"}'
  before_order: 28
  after_order: 28
  child_ids: []
  reason: 'a ligacao do recibo e do FICHEIRO, nao da seccao: a seccao P3.2-b estendeu-o e o digest mudou; re-ligado ao mesmo `#p32`'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p3-2-complaints-reconcile.md
- revision: r60
  item_id: T-11
  action: add
  before: none
  after: '{"id": "T-11", "title": "P3.2-b2: os seis passos pesados inventariados e o subconjunto headless recusado pelo portao de performance (NOT RUN, nao verde)", "status": "done", "receipt": "_main/receipt-20261025-p3-2b-heavy-inventory.md#p32-heavy@sha256:22ff3670d77aca294310cede1aaed6800164a2b2f36f90abf0115b2c04826844", "parent_id": "none", "conditional": false, "note": "5 headless (4 strip + panel-exit3 --unit) e 1 interactivo (mute-audio, dispositivo de audio do dono); guardas medidas: lane-screen-gate PASS, Local/Global SottoShell FREE, panel-state.json de 24/10; lease heavy RECUSADO com state=amber (heavy-requires-green) e nenhum passo largado; comando pronto e snapshot da geometria guardado"}'
  before_order: none
  after_order: 30
  child_ids: []
  reason: 'P3.2-b2: inventario e decisao registados; a largada foi recusada pelo portao, e recusa nao e corrida'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p3-2b-heavy-inventory.md
- revision: r61
  item_id: T-11
  action: status
  before: '{"id": "T-11", "title": "P3.2-b2: os seis passos pesados inventariados e o subconjunto headless recusado pelo portao de performance (NOT RUN, nao verde)", "status": "done", "receipt": "_main/receipt-20261025-p3-2b-heavy-inventory.md#p32-heavy@sha256:22ff3670d77aca294310cede1aaed6800164a2b2f36f90abf0115b2c04826844", "parent_id": "none", "conditional": false, "note": "5 headless (4 strip + panel-exit3 --unit) e 1 interactivo (mute-audio, dispositivo de audio do dono); guardas medidas: lane-screen-gate PASS, Local/Global SottoShell FREE, panel-state.json de 24/10; lease heavy RECUSADO com state=amber (heavy-requires-green) e nenhum passo largado; comando pronto e snapshot da geometria guardado"}'
  after: '{"id": "T-11", "title": "P3.2-b2: os seis passos pesados inventariados e o subconjunto headless recusado pelo portao de performance (NOT RUN, nao verde)", "status": "done", "receipt": "_main/receipt-20261025-p3-2b-heavy-inventory.md#p32-heavy@sha256:fbe505fefc48741f8665d6aa54a163d4822617c8c9ba0fa22712a68b1ba1b2e8", "parent_id": "none", "conditional": false, "note": "5 headless (4 strip + panel-exit3 --unit) e 1 interactivo (mute-audio, dispositivo de audio do dono); guardas medidas: lane-screen-gate PASS, Local/Global SottoShell FREE, panel-state.json de 24/10; lease heavy RECUSADO com state=amber (heavy-requires-green) e nenhum passo largado; comando pronto e snapshot da geometria guardado"}'
  before_order: 30
  after_order: 30
  child_ids: []
  reason: 'a segunda recusa trouxe a razao medida (commit-pct=86.2); o recibo cresceu e a ligacao e do ficheiro, por isso re-ligado ao mesmo `#p32-heavy`'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261025-p3-2b-heavy-inventory.md
- revision: r62
  item_id: T-12
  action: add
  before: none
  after: '{"id": "T-12", "title": "1:1 do YouTube medido no payload: palavras, quebras e timing verdes em 677 amostras, a revelacao palavra-a-palavra vermelha (69 offsets no payload, 0 nos cues) e o check ligado a bateria com 7 mutantes", "status": "done", "receipt": "_main/receipt-20261026-youtube-1to1-check.md#1to1@sha256:400EBCB182E1592949BB440C2B73D9A19EDC6302FC2293CB12F8159BFB1F5045", "parent_id": "none", "conditional": false, "note": "brief 20261026-sotto-objective; metade viva NAO medida (relay 9224 DOWN, yt-dlp com bot-check, lease heavy recusado commit 86.2%); arranques a frio e Alt+C real NAO verificados; battery-wiring 173/49/124, pins PASS, state-page 130 passos"}'
  before_order: none
  after_order: 31
  child_ids: []
  reason: 'o brief de 2026-10-26 e o registo da tarefa; a linha entra com o recibo ja escrito, ligada ao ficheiro e a seccao `#1to1`'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261026-youtube-1to1-check.md
- revision: r63
  item_id: T-13
  action: add
  before: none
  after: '{"id": "T-13", "title": "Revelacao palavra-a-palavra do YouTube fechada: o cue carrega o tOffsetMs do payload, o prefixo revelado bate 677/677 (era 388/677) e a arm reveal-wired le o caminho vivo", "status": "done", "receipt": "_main/receipt-20261026-youtube-1to1-reveal.md#reveal@sha256:4FEA1B2E2AD713B79E37FC8E0716CC4D9D68451E3C8FEAD2B3EB0E907B936DE6", "parent_id": "none", "conditional": false, "note": "7 arms verdes, 9 mutantes each-by-named-arm; cache reconstruida com proveniencia; NAO verificado: ecra (relay 9224 DOWN), latencia do poll de 300 ms, dois arranques a frio (lease AMBER 86.0%), Alt+C real; achado nao corrigido: _tick usa lines[-1] e deita fora a segunda linha da janela"}'
  before_order: none
  after_order: 32
  child_ids: []
  reason: 'o vermelho do 1:1 fechado por medicao: 388/677 -> 0/677 no prefixo revelado, com o mesmo payload e o mesmo video; o que falta (ecra, latencia, arranques, Alt+C) fica declarado no recibo, nao afirmado'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261026-youtube-1to1-reveal.md
- revision: r64
  item_id: C-01
  action: status
  before: '{"id": "C-01", "title": "Mission field set confirmed", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-01@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "mission r0 line 5 confirmed"}'
  after: '{"id": "C-01", "title": "Mission field set confirmed", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-01@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "mission r0 line 5 confirmed"}'
  before_order: 1
  after_order: 1
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r65
  item_id: C-02
  action: status
  before: '{"id": "C-02", "title": "Task read from its own artifacts", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-02@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "todo r0 + dispatch-snapshot + owner-request read"}'
  after: '{"id": "C-02", "title": "Task read from its own artifacts", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-02@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "todo r0 + dispatch-snapshot + owner-request read"}'
  before_order: 2
  after_order: 2
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r66
  item_id: C-03
  action: status
  before: '{"id": "C-03", "title": "Readiness basis recorded", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-03@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "route + ceilings recorded; actual route Go3 (receipt 11); no call/agent quota applied"}'
  after: '{"id": "C-03", "title": "Readiness basis recorded", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-03@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "route + ceilings recorded; actual route Go3 (receipt 11); no call/agent quota applied"}'
  before_order: 3
  after_order: 3
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r67
  item_id: C-04
  action: status
  before: '{"id": "C-04", "title": "Context paths verified to exist", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-04@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "source-manifest.json absent; dirty set re-derived live"}'
  after: '{"id": "C-04", "title": "Context paths verified to exist", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-04@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "source-manifest.json absent; dirty set re-derived live"}'
  before_order: 4
  after_order: 4
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r68
  item_id: C-05
  action: status
  before: '{"id": "C-05", "title": "Skill and TODO delivery verified", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-05@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "both skills by bytes+sha256, matched to declared digests"}'
  after: '{"id": "C-05", "title": "Skill and TODO delivery verified", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-05@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "both skills by bytes+sha256, matched to declared digests"}'
  before_order: 5
  after_order: 5
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r69
  item_id: C-06
  action: status
  before: '{"id": "C-06", "title": "Deliverable written at the exact declared path", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-06@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "all declared deliverable paths written"}'
  after: '{"id": "C-06", "title": "Deliverable written at the exact declared path", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-06@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "all declared deliverable paths written"}'
  before_order: 6
  after_order: 6
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r70
  item_id: C-07
  action: status
  before: '{"id": "C-07", "title": "Write-path discipline", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-07@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "8 owned paths; no commit, no push, no app launch"}'
  after: '{"id": "C-07", "title": "Write-path discipline", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-07@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "8 owned paths; no commit, no push, no app launch"}'
  before_order: 7
  after_order: 7
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r71
  item_id: C-08
  action: status
  before: '{"id": "C-08", "title": "Acceptance executed", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-08@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "acceptance commands run with rcs, not prose"}'
  after: '{"id": "C-08", "title": "Acceptance executed", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-08@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "acceptance commands run with rcs, not prose"}'
  before_order: 8
  after_order: 8
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r72
  item_id: C-09
  action: status
  before: '{"id": "C-09", "title": "Falsifier attempted", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-09@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "falsifier bit: battery-wired RED before wiring; own cure refuted"}'
  after: '{"id": "C-09", "title": "Falsifier attempted", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-09@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "falsifier bit: battery-wired RED before wiring; own cure refuted"}'
  before_order: 9
  after_order: 9
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r73
  item_id: C-10
  action: status
  before: '{"id": "C-10", "title": "Controls run where the claim is mechanical", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-10@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": true, "note": "controls run although conditional; 12 named arms"}'
  after: '{"id": "C-10", "title": "Controls run where the claim is mechanical", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-10@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": true, "note": "controls run although conditional; 12 named arms"}'
  before_order: 10
  after_order: 10
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r74
  item_id: C-11
  action: status
  before: '{"id": "C-11", "title": "Lane state reconciled", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-11@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "worklist statuses match the receipt evidence"}'
  after: '{"id": "C-11", "title": "Lane state reconciled", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-11@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "worklist statuses match the receipt evidence"}'
  before_order: 11
  after_order: 11
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r75
  item_id: C-12
  action: status
  before: '{"id": "C-12", "title": "Change log appended for every worklist edit", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-12@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "one append-only change row per status change"}'
  after: '{"id": "C-12", "title": "Change log appended for every worklist edit", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-12@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "one append-only change row per status change"}'
  before_order: 12
  after_order: 12
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r76
  item_id: C-13
  action: status
  before: '{"id": "C-13", "title": "Done/blocked discipline", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-13@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "nothing done without a receipt; NOT RUN named"}'
  after: '{"id": "C-13", "title": "Done/blocked discipline", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-13@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "nothing done without a receipt; NOT RUN named"}'
  before_order: 13
  after_order: 13
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r77
  item_id: C-14
  action: status
  before: '{"id": "C-14", "title": "Closure checked against dispatch snapshot", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-14@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "24 rows = 15+4+5; strict replay quoted"}'
  after: '{"id": "C-14", "title": "Closure checked against dispatch snapshot", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-14@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "24 rows = 15+4+5; strict replay quoted"}'
  before_order: 14
  after_order: 14
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r78
  item_id: C-15
  action: status
  before: '{"id": "C-15", "title": "Hand-back receipt written", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-15@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "receipt ends in SELF-AUDIT"}'
  after: '{"id": "C-15", "title": "Hand-back receipt written", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#c-15@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "receipt ends in SELF-AUDIT"}'
  before_order: 15
  after_order: 15
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r79
  item_id: W-01
  action: status
  before: '{"id": "W-01", "title": "Smallest change that satisfies acceptance", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-01@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "one gate, one oracle, one test, four steps, four edits"}'
  after: '{"id": "W-01", "title": "Smallest change that satisfies acceptance", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-01@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "one gate, one oracle, one test, four steps, four edits"}'
  before_order: 16
  after_order: 16
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r80
  item_id: W-02
  action: status
  before: '{"id": "W-02", "title": "Tests or checks written or updated per project rule", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-02@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "project native --neg-arm shape, no new harness"}'
  after: '{"id": "W-02", "title": "Tests or checks written or updated per project rule", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-02@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "project native --neg-arm shape, no new harness"}'
  before_order: 17
  after_order: 17
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r81
  item_id: W-03
  action: status
  before: '{"id": "W-03", "title": "Mutation or revert path exercised where the ticket requires it", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-03@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": true, "note": "12 mutations on copies; real tree untouched"}'
  after: '{"id": "W-03", "title": "Mutation or revert path exercised where the ticket requires it", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-03@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": true, "note": "12 mutations on copies; real tree untouched"}'
  before_order: 18
  after_order: 18
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r82
  item_id: W-04
  action: status
  before: '{"id": "W-04", "title": "No second source of truth introduced", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-04@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "skill digest pinned; baseline hash-keyed with code ceiling"}'
  after: '{"id": "W-04", "title": "No second source of truth introduced", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#w-04@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "skill digest pinned; baseline hash-keyed with code ceiling"}'
  before_order: 19
  after_order: 19
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r83
  item_id: T-01
  action: status
  before: '{"id": "T-01", "title": "Read AGENTS and current TODO or roadmap then choose its next unfinished accepted item", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-01@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "P0.3 of roadmap-observability chosen; reason given"}'
  after: '{"id": "T-01", "title": "Read AGENTS and current TODO or roadmap then choose its next unfinished accepted item", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-01@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "P0.3 of roadmap-observability chosen; reason given"}'
  before_order: 20
  after_order: 20
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r84
  item_id: T-02
  action: status
  before: '{"id": "T-02", "title": "Classify acceptance and wire a deterministic gate before dependent product edits", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-02@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "gate built and wired before the dependent edits"}'
  after: '{"id": "T-02", "title": "Classify acceptance and wire a deterministic gate before dependent product edits", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-02@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "gate built and wired before the dependent edits"}'
  before_order: 21
  after_order: 21
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r85
  item_id: T-03
  action: status
  before: '{"id": "T-03", "title": "Run positive and targeted negative controls and record intended gate verdicts", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-03@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "positive and named negative controls with intended verdicts"}'
  after: '{"id": "T-03", "title": "Run positive and targeted negative controls and record intended gate verdicts", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-03@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "positive and named negative controls with intended verdicts"}'
  before_order: 22
  after_order: 22
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r86
  item_id: T-04
  action: status
  before: '{"id": "T-04", "title": "Implement one highest-priority safe slice from the existing backlog and verify its real invoker", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-04@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "slice green under cmd.exe, red by design under neg-arm"}'
  after: '{"id": "T-04", "title": "Implement one highest-priority safe slice from the existing backlog and verify its real invoker", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-04@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "slice green under cmd.exe, red by design under neg-arm"}'
  before_order: 23
  after_order: 23
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r87
  item_id: T-05
  action: status
  before: '{"id": "T-05", "title": "Write receipt and return the editable TODO with required SELF-AUDIT", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-05@sha256:ca21124bd98252a81febdc0db52336de27d3a0335396d9714c022a0851e86f06", "parent_id": "none", "conditional": false, "note": "receipt + this TODO returned with change log"}'
  after: '{"id": "T-05", "title": "Write receipt and return the editable TODO with required SELF-AUDIT", "status": "done", "receipt": "state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md#t-05@sha256:fce08d3a9e647b41972a2f3b1b99d1bfb2a128dacc8461b51dac6bb298219354", "parent_id": "none", "conditional": false, "note": "receipt + this TODO returned with change log"}'
  before_order: 24
  after_order: 24
  child_ids: []
  reason: 'rebind to the receipt bytes after the 2026-10-26 provenance correction: the route is now measured (providerID=opencode-go-3, session ses_e8d811684), and the binding is of the FILE, so the same #anchor is kept'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: state/work/TC-20261025-cross-project-continuity/sotto-lane/receipt.md
- revision: r88
  item_id: T-14
  action: add
  before: none
  after: '{"id": "T-14", "title": "Proveniencia de ROTA fechada por medicao: o recibo declara a rota que correu (providerID=opencode-go-3), nao a que a politica sonda primeiro, e um portao fica vermelho quando as duas divergem", "status": "done", "receipt": "_main/receipt-20261026-receipt-provenance.md#2-the-instrument-that-settles-a-route-and-the-one-that-cannot@sha256:3d2ad9b27b40a8ffe2ba290991d6a3607a6393a4d730d597becb2c0862c591de", "parent_id": "none", "conditional": false, "note": "o defeito: receipt.md:4 dizia OpenCode Go 1 e o processo que o escreveu corria em opencode-go-3; instrumento novo e re-executavel: session_v2.model por contencao do instante de criacao do recibo (1 janela de 613.3 s, as outras duas fecharam em 2.4 s e 0.9 s); portao com 4 checks e 4 bracos nomeados, vermelho primeiro nos bytes reais; battery-wiring vermelho PRE-EXISTENTE (125 vs 124); passos NAO CORRIDOS: a bateria nunca correu"}'
  before_order: none
  after_order: 33
  child_ids: []
  reason: 'W-10 exige que o fecho seja produzido por um portao: o item entra com o recibo ja escrito e ligado ao FICHEIRO (anchor #provenance), porque a ligacao e do ficheiro e o anchor e so o sitio'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261026-receipt-provenance.md
- revision: r89
  item_id: T-12
  action: refine
  before: '{"id": "T-12", "title": "1:1 do YouTube medido no payload: palavras, quebras e timing verdes em 677 amostras, a revelacao palavra-a-palavra vermelha (69 offsets no payload, 0 nos cues) e o check ligado a bateria com 7 mutantes", "status": "done", "receipt": "_main/receipt-20261026-youtube-1to1-check.md#1to1@sha256:400EBCB182E1592949BB440C2B73D9A19EDC6302FC2293CB12F8159BFB1F5045", "parent_id": "none", "conditional": false, "note": "brief 20261026-sotto-objective; metade viva NAO medida (relay 9224 DOWN, yt-dlp com bot-check, lease heavy recusado commit 86.2%); arranques a frio e Alt+C real NAO verificados; battery-wiring 173/49/124, pins PASS, state-page 130 passos"}'
  after: '{"id": "T-12", "title": "1:1 do YouTube medido no payload: palavras, quebras e timing verdes em 677 amostras, a revelacao palavra-a-palavra vermelha (69 offsets no payload, 0 nos cues) e o check ligado a bateria com 7 mutantes", "status": "done", "receipt": "_main/receipt-20261026-live-1to1-edge.md#sampler-seek@sha256:960DA79480CF404AFD24E16C22D7F74A1EF4C72110894F0D042C71926B69EBE1", "parent_id": "none", "conditional": false, "note": "metade viva medida 16/16 no Edge proprio (recibo live-1to1-edge) e o amostrador passou a saltar por SEEK_JS (:657) antes da leitura (:662); relay 9224 DOWN; medicao pos-fix e --selfcheck DIFERIDOS (Gaming), nao contados como portao; arranques a frio e Alt+C real NAO verificados"}'
  before_order: 31
  after_order: 31
  child_ids: []
  reason: 'o amostrador de yt-1to1-live-compare.py nao cumpria o proprio cabecalho (saltar por seekTo e ler a janela de legendas depois de cada salto): a amostra passa a ser ESCOLHIDA por grelha sobre dur, e o fix fica ligado ao recibo live-1to1-edge ancorado em #sampler-seek, com CodeIntel de escopo exato e paridade de ripgrep 4/4 antes e 6/6, 1/1, 8/8 depois; a medicao depois da correcao e o --selfcheck ficam DIFERIDOS e NAO contados como portao'
  actor: sotto-lane-task-resolver-continuation
  approval_ref: none
  evidence: _main/receipt-20261026-live-1to1-edge.md

# ============================================================================
# DOGFOOD CodeIntel escopo exato — 2026-10-26 — dado JA RECOLHIDO, nao re-executado
# ============================================================================
# Alvo: app/webview/sotto_webview.py (existe, 769743 B) no checkout real H:/sotto
# (git root H:/sotto, rev c21f8a751b188feec1594ff0f0b6745388b4b5fa).
#
# COMANDOS EXATOS (CodeIntel MCP, codeintel_grep, path exato em todos, limit=100):
#  1. {pattern:"hotkey",        path:"app/webview/sotto_webview.py", limit:100}
#     -> total=30 returned=30
#     -> file:line app/webview/sotto_webview.py:31,:334,:414,:1364,:1404,:1411,:1424,
#        :1429,:1430,:1436,:1439,:1448,:1461,:1464,:1472,:1473,:1531,:1533,:2772,:2780,
#        :2905,:2918,:2986,:3015,:3476,:3479,:3480,:3482,:3487,:3488
#  2. {pattern:"panel",         path:"app/webview/sotto_webview.py", limit:100}
#     -> total=30 returned=30
#     -> file:line :5,:6,:21,:22,:23,:31,:35,:59,:62,:64,:65,:69,:71,:84,:114,:115,
#        :118,:124,:125,:126,:130,:138,:145,:149,:155,:160,:164,:176,:204,:222
#  3. {pattern:"caption_paint", path:"app/webview/sotto_webview.py", limit:100}
#     -> total=3 returned=3 -> :9494,:9495,:9497
#  4. {pattern:"set_text",      path:"app/webview/sotto_webview.py", limit:100}
#     -> total=1 returned=1 -> :9482
#  5. {pattern:"HOTKEY_PRESSED",path:"app/webview/sotto_webview.py", limit:100}
#     -> total=11 returned=11 -> :1411,:3534,:4522,:8172,:8176,:8328,:8496,:8502,
#        :8633,:8685,:9487
#  6. {pattern:"CAPTION_PAINT", path:"app/webview/sotto_webview.py", limit:100}
#     -> total=3 returned=3 -> :9494,:9495,:9497
#  7. {pattern:"zzz_absent_token_9c1f", path:"app/webview/sotto_webview.py", limit:100}
#     -> total=0 returned=0 -> (nenhuma linha)   [CONTROLO NEGATIVO]
#
# INVENTARIO rg, MESMO ficheiro, comando exato:
#  rg -n -i <term> app/webview/sotto_webview.py
#     hotkey=205  panel=941  caption_paint=3  set_text=1
#  rg -n -i "log\(.*<term>" app/webview/sotto_webview.py
#     hotkey=13  panel=88  caption_paint=1  set_text=0
#  rg -n -i "zzz_absent_token_9c1f" app/webview/sotto_webview.py  -> 0
#
# COBERTURA das linhas de log() que o rg viu, dentro do que o CodeIntel devolveu:
#  hotkey 0/13 (faltam 4500,4506,4507,4531,8489,8514,8517,8541,8551,11566,11570,11573,14556)
#  panel  1/88 (so :204)
#  caption_paint 1/1 (:9497)   set_text n/d (0 linhas de log com o termo)
#
# VEREDICTOS:
#  PASS  caption_paint: 3/3, rg 3, log-line :9497 coberta, todas as linhas no alvo.
#  PASS  set_text: 1/1 (:9482), rg 1, e o rg concorda que nao esta dentro de log(.
#  PASS  controlo negativo: token ausente -> CodeIntel 0/0 e rg 0, igual.
#  FAIL  hotkey: 30 de 205 linhas (rg), e 0/13 das linhas log(...hotkey...) alcançadas.
#  FAIL  panel: 30 de 941 linhas (rg), e 1/88 das linhas log(...panel...) alcançadas.
#  FAIL  o parametro limit=100 NAO e honrado: devolveu 30, e `total` devolve o tamanho
#        da pagina (30), nao o corpus (205/941). Sem offset/paginacao expostos.
#  FAIL  aceitacao do slice ("nenhuma linha omitida no cap declarado") para os dois
#        termos de alta frequencia.
#  UNKNOWN quantas linhas existem alem da 30a para esses termos: atingive-las exige
#        decompor por literal unico (ver abaixo), nao alargar o termo.
#  MISMATCH registado: CodeIntel != rg para hotkey e panel; igual para caption_paint,
#        set_text e para o controlo negativo.
#  SEGUINTE consulta limitada (ja provada): literal unico por ponto de emissao —
#        HOTKEY_PRESSED deu 11/11 e CAPTION_PAINT 3/3, completos e no alvo.
#
# NAO CORRIDO nesta slice: testes, --selfcheck, build, index/rebuild, install, e
# qualquer edicao de ficheiro (NOT RUN).

# ============================================================================
# DOGFOOD 2 — contrato REAL do codeintel_grep (regex, cap, truncation) — 2026-10-26
# ============================================================================
# Alvo unico: app/webview/sotto_webview.py. Nada mais foi tocado.
#
# CHAMADA 1: codeintel_grep({pattern:"log\\s*\\(.*(hotkey|panel|caption_paint)",
#            path:"app/webview/sotto_webview.py", limit:100})
#   returned=30  total=30  effective path=app/webview/sotto_webview.py
#   keys no envelope: results,total,_meta,_latency_ms
#   TRUNCATED FLAG: ABSENT (o campo nao existe na resposta) — nao ha como distinguir
#     "acabou" de "cortou" a nao ser comparando com outra fonte.
#   file:line devolvidos: 204,225,229,232,268,290,2980,2987,3016,3018,3442,3894,
#     3969,4489,4500,4506,4507,4531,5063,5451,5462,5520,5536,5549,5936,5939,6201,6205,
#     6588,6591
#   As linhas de log(...) desejadas ESTAO presentes — mas so as primeiras da ordem do
#     ficheiro; :4489,:4500,:4506,:4507,:4531 sao quatro `log(...hotkey...)`.
#
# CHAMADA 2: rg -n -i 'log\s*\(.*(hotkey|panel|caption_paint)' app/webview/sotto_webview.py
#   matches=102  sample 204,225,229,232,268,290,2980,2987,3016,3018
#   last sample 11566,11570,11573,14451,14556
#
# PRECISAO/RECALL medidos contra esse inventario:
#   CodeIntel linhas dentro do rg = 30/30 (precision 1.00, nada inventado)
#   linhas do CodeIntel fora do rg = 0
#   recall = 30/102 = 29,4% — faltam 72 linhas (o cap corta antes da linha 6592)
#   VEREDICTO: regex PASSA (o padrao foi honrado: `\s*`, `\(` e alternacao `|` todos
#   funcionaram); CAP PASSA como limite, FALHA como contrato de completude (sem
#   truncated, sem paginacao); cobertura do termo FALHA.
#
# CHAMADA 3 (semantica de alternacao): codeintel_grep({pattern:"HOTKEY|hotkey",
#   path:"app/webview/sotto_webview.py", limit:100}) -> returned=30 total=30,
#   MESMA lista da busca simples "hotkey": 31,334,414,1364,...,3488.
#   VEREDICTO PASS: `|` e alternacao de regex, nao literal — se fosse literal devolveria 0.
#
# ESTADO HERDADO (declarado, nao re-executado): o slice anterior deu hotkey 30/205,
# panel 30/941, caption_paint 3/3, set_text 1/1, controlo negativo 0/0; tests,
# --selfcheck, build, index/rebuild e edicao NAO foram corridos (NOT RUN).
#
# audit-sweep: JA TINHA CORRIDO nesta sessao e FALHOU por indisponibilidade —
#   `python tools/audit-sweep.py --sweep` em H:\sotto -> rc=2,
#   "C:\Program Files\Python311\python.exe: can't open file
#   'H:\\sotto\\tools\\audit-sweep.py': [Errno 2] No such file or directory",
#   Test-Path tools\audit-sweep.py = False. Nao foi re-corrido aqui.

# ============================================================================
# CORRECAO DE EVIDENCIA + sonda de regex sem alternacao — 2026-10-26 (DOGFOOD 3)
# ============================================================================
# CORRECAO de uma afirmacao MINHA na seccao DOGFOOD 2 acima: escrevi que o campo de
# truncagem estava ABSENT. Esta ERRADO — eu tinha olhado o nivel de topo
# (results,total,_meta,_latency_ms) em vez de _meta.grep. O envelope traz:
#   _meta.grep = {effective_scope:"app/webview/sotto_webview.py", result_limit:30,
#                 serialized_byte_limit:24576, duplicate_rows_collapsed:0, truncated:true}
# no call {pattern:"log\\s*\\(.*(hotkey|panel|caption_paint)", limit:100}. Note-se que
# result_limit=30 apesar de eu ter pedido 100: o limite da chamada e' cortado para 30,
# e truncated=true declara o corte em vez de o esconder. A leitura correcta fica
# registada aqui; a linha antiga NAO se apaga (append-only).
#
# SONDA: {pattern:"log\\s*\\(.*hotkey", path:"app/webview/sotto_webview.py", limit:30}
#   returned=0  total=0  lines=[]  _meta.grep={effective_scope:"app/webview/
#   sotto_webview.py", result_limit:30, truncated:false, serialized_byte_limit:24576,
#   duplicate_rows_collapsed:0}
#
# INVENTARIO rg, mesmo ficheiro:
#   rg -n -i 'log\s*\(.*hotkey' app/webview/sotto_webview.py  -> 14 matches
#     4489,4500,4506,4507,4531,8489,8514,8517,8541,8551,11566,11570,11573,14556
#     (o "13" herdado vinha do padrao anterior, sem `\s*`; com `\s*` entra tambem :4489)
#   rg -n -F 'log\s*\(.*hotkey' app/webview/sotto_webview.py  -> 0 matches (literal)
#
# VEREDICTO: a sintaxe de regex SEM alternacao NAO e' honrada. O 0 do CodeIntel e'
#   EXACTAMENTE o resultado literal (-F), o que diz que o padrao foi comparado como
#   texto e nao como regex: `\s`, `\(` e `.*` nao tiveram efeito. Na chamada anterior,
#   que trazia `|`, o mesmo motor devolveu linhas certas (incluindo :4489,:4500,:4506,
#   :4507,:4531) — logo o modo regex parece depender da presenca de `|`.
#   FAIL  CodeIntel `log\s*\(.*hotkey` -> 0 contra 14 do rg.
#   PASS  o envelope DECLARA honestamente o corte quando ha corte
#         (_meta.grep.truncated=true, result_limit=30); nesta sonda truncated=false.
#   PROXIMO passo limitado (nao corrido aqui): obter a mesma familia de linhas com um
#   padrao que contenha `|` (ex.: "log\\s*\\(.*(hotkey)"), que e' a forma que ja
#   funcionou, em vez de alargar o termo.
#
# NAO CORRIDO: testes, --selfcheck, build, index/rebuild, install, edicao de codigo,
#   e qualquer varrimento fora de app/webview/sotto_webview.py (NOT RUN).

# ============================================================================
# FECHO DE EVIDENCIA 4 — chamada unica com hash antes/depois — 2026-10-26
# ============================================================================
# ANTES da chamada:
#   git rev-parse HEAD            = c21f8a751b188feec1594ff0f0b6745388b4b5fa
#   sha256 app/webview/sotto_webview.py = 1E450C90F7F99990D35F2486F69840F5D8E951CB1D20E240925279E659946C26
#   bytes = 769743
#
# CHAMADA EXACTA:
#   codeintel_grep({pattern:"log\\s*\\(.*hotkey",
#                   path:"app/webview/sotto_webview.py", limit:30})
# RESPOSTA PARSEADA, CAMPO A CAMPO (nao resumida):
#   top-level keys            = results, total, _meta, _latency_ms
#   error                     = FIELD_ABSENT (o campo nao existe no envelope)
#   error_type                = FIELD_ABSENT
#   degraded                  = FIELD_ABSENT
#   results                   = []            <-- lista VAZIA, nao um erro
#   total                     = 0
#   _meta.keys                = grep, admission, run_id, trace_id, span_id, incident_context
#   _meta.grep.effective_scope          = app/webview/sotto_webview.py
#   _meta.grep.result_limit             = 30
#   _meta.grep.serialized_byte_limit    = 24576
#   _meta.grep.duplicate_rows_collapsed = 0
#   _meta.grep.truncated                = false
#   raw serialized bytes      = 811
#   Ou seja: a resposta NAO e' um erro e NAO foi cortada — e' zero resultados declarados
#   como zero, com o escopo certo. O desacordo e' com a verdade do ficheiro (abaixo).
#
# DEPOIS da chamada:
#   git rev-parse HEAD            = c21f8a751b188feec1594ff0f0b6745388b4b5fa  (igual)
#   sha256 app/webview/sotto_webview.py = 1E450C90F7F99990D35F2486F69840F5D8E951CB1D20E240925279E659946C26  (igual)
#   bytes = 769743 (igual)  -> a chamada NAO tocou no ficheiro.
#
# VERDADE NO MESMO FICHEIRO, comando exacto:
#   rg --no-config --no-ignore -g '!.codeintel/**' -n -i 'log\s*\(.*hotkey' app/webview/sotto_webview.py
#   count = 14
#   4489   HOTKEY_UNAVAILABLE (comentario que contem `HOTKEY_UNAVAILABLE`)
#   4500   log('HOTKEY_UNAVAILABLE alert=balloon tried=' ...)
#   4506   log(f'HOTKEY_ALERT_FAILED error={exc!r}')
#   4507   log('HOTKEY_ALERT_SHOWN shown=%s channel=%s' ...)
#   4531   log(f'HOTKEY_TRY_FAILED accelerator={accelerator} ' ...)
#   8489   log(f'HOTKEY_CAPTION_UNDONE caption_on={str(restore).lower()} ' ...)
#   8514   log('HOTKEY_DOUBLE_SWALLOWED double=discarded ' ...)
#   8517   log(f'HOTKEY_DOUBLE panel=strip after_ms={HOTKEY_GESTURE_MS}')
#   8541   log('HOTKEY_DOUBLE_SWALLOWED single=discarded ' ...)
#   8551   log(f'HOTKEY_SINGLE caption_on={str(on).lower()} ' ...)
#   11566  log('SELFTEST refused=--no-hotkey (nothing registered to prove)')
#   11570  log('SELFTEST hotkey_registered=false')
#   11573  log(f'SELFTEST hotkey_registered=' ...)
#   14556  log(f'HOTKEY_DISABLED reason={hotkey_off or "--no-hotkey"}')
#
# VEREDICTOS:
#   FAIL    CodeIntel devolveu 0 contra 14 linhas reais do MESMO ficheiro, sem erro,
#           sem truncated, sem degradacao — um zero silencioso e' pior que um erro.
#   PASS    a chamada e' read-only: sha256 do ficheiro e HEAD identicos antes/depois.
#   PASS    o envelope e' honesto quanto ao escopo (effective_scope correcto) e quanto
#           ao corte (truncated=false coerente com 0 resultados).
#   UNKNOWN se o zero vem do index estar preso a uma versao antiga do ficheiro ou de o
#           padrao sem `|` ser comparado como literal (hipotese da seccao DOGFOOD 3;
#           `rg -F` com o mesmo padrao tambem da 0, o que sustenta a hipotese literal).
#
# NAO CORRIDO: testes, --selfcheck, build, index/rebuild, install, edicao de codigo,
#   qualquer outro ficheiro (NOT RUN).

# ============================================================================
# DOGFOOD 5 — alternacao REDUNDANTE recupera as 14 linhas — 2026-10-26
# ============================================================================
# CHAMADA EXACTA:
#   codeintel_grep({pattern:"log\\\\s*\\\\(.*(hotkey|HOTKEY)",
#                   path:"app/webview/sotto_webview.py", limit:30})
#   (o `|HOTKEY` e' redundante de proposito: `-i` ja' cobria os dois casos. Entra para
#    testar a via de compatibilidade que ja' tinha funcionado antes.)
# RESPOSTA:
#   returned = 14   total = 14   raw = 7633 bytes
#   _meta.grep = {effective_scope:"app/webview/sotto_webview.py", result_limit:30,
#                 serialized_byte_limit:24576, duplicate_rows_collapsed:0,
#                 truncated:false}
#   file:line devolvidos (todos no ficheiro pedido, nenhum caminho alheio):
#     app/webview/sotto_webview.py:4489  :4500  :4506  :4507  :4531  :8489  :8514
#     app/webview/sotto_webview.py:8517  :8541  :8551  :11566 :11570 :11573 :14556
#
# COMPARACAO com o inventario anterior do MESMO ficheiro
# (rg --no-config --no-ignore -g '!.codeintel/**' -n -i 'log\\s*\\(.*hotkey', 14 linhas,
#  ficheiro sha256 1E450C90F7F99990D35F2486F69840F5D8E951CB1D20E240925279E659946C26, HEAD
#  c21f8a751b188feec1594ff0f0b6745388b4b5fa inalterado):
#   interseccao = 14/14, linhas em falta = 0, linhas a mais = 0, ordem igual.
#   VEREDICTO PASS — igualdade exacta, e`declarada como completa (truncated:false, e
#   7633 B < 24576 B, logo o corte por bytes tambem nao actua).
#
# O QUE ISTO E' E O QUE NAO E':
#   PASS  e' um WORKAROUND utilizavel: escrever a alternacao com `|` desbloqueia a busca
#         por `log(...)` neste ficheiro e devolve o conjunto completo.
#   NAO E' o fix final. O defeito por tras continua de pe': um padrao sem `|` e' passado
#         como texto literal, e o tecto de 30 linhas com `total` = tamanho da pagina
#         (medido antes: 30 devolvidas contra 205/941 reais) continua a esconder o resto.
#         A via correcta e' o CodeIntel honrar regex sempre e paginar; ate la', qualquer
#         lane que escreva `log\\s*\\(.*termo` sem `|` obtem zero silencioso.
#
# CORRECCAO QUE FECHA O UNKNOWN DA SECCAO "FECHO DE EVIDENCIA 4":
#   O UNKNOWN era "o zero vem do index estar preso a uma versao antiga do ficheiro ou de
#   o padrao sem `|` ser comparado como literal?". FICA RESOLVIDO pela evidencia na MESMA
#   revisao de codigo: mesmo HEAD (c21f8a75...), mesmo sha256 de ficheiro
#   (1E450C90...946C26), mesma sessao, e a UNICA diferenca entre o 0 e o 14 e' a presenca
#   de um `|` nao escapado no padrao. Logo o mecanismo e' o do PARSER DO PADRAO, nao o do
#   index:
#     - padrao SEM `|` -> comparado LITERALMENTE (o `0` igual ao de `rg -F`)
#     - `|` nao escapado -> activa o modo REGEX (o `14` igual ao de `rg -i`)
#   Nao foi o index a ficar velho: a mesma chamada, com `|`, le o mesmo ficheiro e ve tudo.
#
# NAO CORRIDO: testes, --selfcheck, build, index/rebuild, install, edicao de codigo ou de
#   qualquer outro ficheiro, e nenhum varrimento fora de app/webview/sotto_webview.py
#   (NOT RUN).

# ============================================================================
# RECEIPT — 3 padroes com alternacao redundante, CodeIntel vs rg — 2026-10-26
# ============================================================================
# Alvo unico e literal: app/webview/sotto_webview.py. Sem regex=true (nao testado aqui).
# HEAD c21f8a751b188feec1594ff0f0b6745388b4b5fa; ficheiro
# sha256 1E450C90F7F99990D35F2486F69840F5D8E951CB1D20E240925279E659946C26 (769743 B).
#
# COMANDOS EXACTOS
#   CodeIntel (3 chamadas separadas, uma por padrao):
#     codeintel_grep({pattern:"log\\\\s*\\\\(.*(hotkey|HOTKEY)", path:"app/webview/sotto_webview.py", limit:30})
#     codeintel_grep({pattern:"log\\\\s*\\\\(.*(panel|PANEL)", path:"app/webview/sotto_webview.py", limit:30})
#     codeintel_grep({pattern:"log\\\\s*\\\\(.*(caption_paint|CAPTION_PAINT|set_text|SET_TEXT)", path:"app/webview/sotto_webview.py", limit:30})
#   Verdade no mesmo ficheiro:
#     rg --no-config --no-ignore -g '!.codeintel/**' -n -i --no-heading <mesmo padrao> app/webview/sotto_webview.py
#
# P1 hotkey|HOTKEY
#   CodeIntel returned=14 total=14 file:line
#     4489,4500,4506,4507,4531,8489,8514,8517,8541,8551,11566,11570,11573,14556
#   rg=14, MESMAS linhas, mesma ordem. Set equality = TRUE (0 em falta, 0 a mais).
#   _meta.grep effective_scope="app/webview/sotto_webview.py" result_limit=30 truncated=false
#     serialized_byte_limit=24576 duplicate_rows_collapsed=0 pattern_mode="regex"
#   raw response = 7606 B  (abaixo do tecto de 24576 B: nao houve corte por bytes)
#   VEREDICTO PASS — conjunto completo e igual.
#
# P2 panel|PANEL
#   CodeIntel returned=30 total=30 file:line
#     204,225,229,232,268,290,2980,2987,3016,3018,3442,3894,3969,5063,5451,5462,5520,5536,
#     5549,5936,5939,6201,6205,6588,6591,6594,6595,6596,6634,6667
#   rg=88, e as 30 devolvidas sao EXACTAMENTE o prefixo das 88 (ci_is_prefix_of_rg=TRUE).
#   Set equality = FALSE: faltam 58 linhas, a comecar em 6698,6759,6770,6827,6908,6911...
#   _meta.grep effective_scope="app/webview/sotto_webview.py" result_limit=30 truncated=TRUE
#     serialized_byte_limit=24576 duplicate_rows_collapsed=0 pattern_mode="regex"
#   raw response = 14807 B (ainda abaixo de 24576 B -> o corte e' do result_limit, nao dos bytes)
#   VEREDICTO FAIL na completude, PASS na honestidade: truncated=true declara o corte.
#
# P3 caption_paint|CAPTION_PAINT|set_text|SET_TEXT
#   CodeIntel returned=1 total=1 file:line 9497
#   rg=1, linha 9497. Set equality = TRUE.
#   _meta.grep effective_scope="app/webview/sotto_webview.py" result_limit=30 truncated=false
#     serialized_byte_limit=24576 duplicate_rows_collapsed=0 pattern_mode="regex"
#   raw response = 1332 B
#   VEREDICTO PASS.
#
# OBSERVACAO MEDIDA (campo novo): `_meta.grep.pattern_mode:"regex"` apareceu AGORA e NAO
#   existia na chamada identica do bloco DOGFOOD 5 (5 chaves: effective_scope, result_limit,
#   serialized_byte_limit, duplicate_rows_collapsed, truncated). Mesmo padrao P1, mesmo
#   ficheiro, mesma sessao — logo o processo CodeIntel em execucao MUDOU entre as duas
#   chamadas e passou a declarar o modo de padrao. Isto e' o oposto de um efeito de cache:
#   e' o servidor a expor um campo que antes nao expunha.
#
# RESUMO: 2 PASS exactos (P1, P3), 1 FAIL de completude declarado (P2, 30 de 88 com
#   truncated=true). A alternacao redundante activa o modo regex nas tres.
#   Nada foi editado no codigo; nenhum outro ficheiro foi tocado.
#
# NAO CORRIDO: testes, --selfcheck, build, index/rebuild, install, regex=true, e qualquer
#   leitura fora de app/webview/sotto_webview.py (NOT RUN).

# ============================================================================
# RECEIPT — regex=true vs regex=false, mesmo padrao, mesmo ficheiro — 2026-10-26
# ============================================================================
# Alvo unico: app/webview/sotto_webview.py. Padrao unico: log\s*\(.*hotkey. limit=30.
#
# CHAMADA A (aceite): codeintel_grep({pattern:"log\\\\s*\\\\(.*hotkey",
#   path:"app/webview/sotto_webview.py", limit:30, regex:true})
#   status=accepted  returned=14  total=14
#   file:line  4489,4500,4506,4507,4531,8489,8514,8517,8541,8551,11566,11570,11573,14556
#   _meta.grep effective_scope="app/webview/sotto_webview.py" pattern_mode="regex"
#     truncated=false  result_limit=30  serialized_byte_limit=24576
#     duplicate_rows_collapsed=0
#   resposta serializada = 7606 B
#
# CHAMADA B (aceite): mesmos args, regex:false
#   status=accepted  returned=0  total=0  file:line (nenhuma)
#   _meta.grep effective_scope="app/webview/sotto_webview.py" pattern_mode="literal"
#     truncated=false  result_limit=30  serialized_byte_limit=24576
#     duplicate_rows_collapsed=0
#   resposta serializada = 842 B
#   Nao houve erro: o servidor aceita o parametro e muda de modo. Zero nao e' falha
#   declarada, e' zero literal — e o rg -F abaixo concorda.
#
# VERDADE NO MESMO FICHEIRO
#   rg --no-config --no-ignore -g '!.codeintel/**' -n -i 'log\s*\(.*hotkey' app/webview/sotto_webview.py
#     -> 14 linhas: 4489,4500,4506,4507,4531,8489,8514,8517,8541,8551,11566,11570,11573,14556
#   rg --no-config --no-ignore -g '!.codeintel/**' -n -i -F 'log\s*\(.*hotkey' app/webview/sotto_webview.py
#     -> 0 linhas
#
# IGUALDADE VERIFICADA (comparada, nao assumida)
#   regex=true  vs rg -i : conjuntos IGUAIS, 14 = 14, mesma ordem, 0 em falta, 0 a mais.
#                            O conjunto positivo esperado (as 14 linhas de log(...hotkey...))
#                            confirma-se exactamente.
#   regex=false vs rg -F : conjuntos IGUAIS, 0 = 0.
#   VEREDICTO PASS nos dois bracos. O parametro regex e' honrado e o pattern_mode
#   declarado ("regex" / "literal") acompanha-o em vez de ficar fixo.
#
# CORRECCAO DE UM NUMERO ANTIGO DESTE MESMO TODO: os blocos anteriores registaram "0 para
#   o padrao sem `|`" e atribuiram-no a um heuristica do parser. Com o parametro explicito,
#   a explicacao medida e' mais simples e nao precisa da heuristica: por omissao o padrao
#   corre em modo LITERAL (pattern_mode="literal"), e um literal `log\s*\(.*hotkey` nao
#   existe no ficheiro; com regex:true o mesmo padrao devolve as 14. O comportamento
#   anterior (activado por `|`) fica explicado como efeito colateral dessa deteccao, nao
#   como contrato. As linhas antigas NAO se apagam (append-only).
#
# NAO CORRIDO: testes, --selfcheck, build, index/rebuild, install, e nenhuma leitura fora
#   de app/webview/sotto_webview.py (NOT RUN).

# ============================================================================
# RECEIPT — afinacao do `panel` largo com cruzamento caption/paint — 2026-10-26
# ============================================================================
# Alvo unico: app/webview/sotto_webview.py. Query de cruzamento: exige `panel` E
# (`caption` OU `paint`) na MESMA linha de log().
#
# CHAMADA (aceite): codeintel_grep({pattern:"log\\\\s*\\\\(.*(panel.*caption|caption.*panel
#   |panel.*paint|paint.*panel)", path:"app/webview/sotto_webview.py", limit:30, regex:true})
#   status=accepted  returned=1  total=1
#   file:line  9564
#   _meta.grep effective_scope="app/webview/sotto_webview.py" pattern_mode="regex"
#     truncated=false  result_limit=30  serialized_byte_limit=24576
#     duplicate_rows_collapsed=0
#   resposta serializada = 1347 B
#
# VERDADE NO MESMO FICHEIRO
#   rg --no-config --no-ignore -g '!.codeintel/**' -n -i
#      'log\s*\(.*(panel.*caption|caption.*panel|panel.*paint|paint.*panel)'
#      app/webview/sotto_webview.py
#   -> 1 linha: 9564
#
# IGUALDADE DE CONJUNTO: TRUE — 1 = 1, mesma linha, nada em falta, nada a mais.
#   VEREDICTO PASS.
#
# PARA QUE SERVIU: reduz o `panel` largo (88 linhas via rg, 30 devolvidas com
#   truncated=true) a UMA linha, dentro do cap, com truncated=false — ou seja a afinacao
#   por cruzamento de termos obtem o conjunto completo em vez de um prefixo cortado.
#   Nao resolve o tecto de 30 (um termo com mais de 30 cruzamentos voltaria a cortar);
#   resolve o caso concreto do `panel`.
#
# NAO CORRIDO: testes, --selfcheck, build, index/rebuild, install, e nenhuma leitura fora
#   de app/webview/sotto_webview.py (NOT RUN).
