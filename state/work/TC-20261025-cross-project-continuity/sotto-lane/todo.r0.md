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
| 1 | C-01 | Mission field set confirmed | open | none | none | false |  |
| 2 | C-02 | Task read from its own artifacts | open | none | none | false |  |
| 3 | C-03 | Readiness basis recorded | open | none | none | false |  |
| 4 | C-04 | Context paths verified to exist | open | none | none | false |  |
| 5 | C-05 | Skill and TODO delivery verified | open | none | none | false |  |
| 6 | C-06 | Deliverable written at the exact declared path | open | none | none | false |  |
| 7 | C-07 | Write-path discipline | open | none | none | false |  |
| 8 | C-08 | Acceptance executed | open | none | none | false |  |
| 9 | C-09 | Falsifier attempted | open | none | none | false |  |
| 10 | C-10 | Controls run where the claim is mechanical | open | none | none | true |  |
| 11 | C-11 | Lane state reconciled | open | none | none | false |  |
| 12 | C-12 | Change log appended for every worklist edit | open | none | none | false |  |
| 13 | C-13 | Done/blocked discipline | open | none | none | false |  |
| 14 | C-14 | Closure checked against dispatch snapshot | open | none | none | false |  |
| 15 | C-15 | Hand-back receipt written | open | none | none | false |  |
| 16 | W-01 | Smallest change that satisfies acceptance | open | none | none | false |  |
| 17 | W-02 | Tests or checks written or updated per project rule | open | none | none | false |  |
| 18 | W-03 | Mutation or revert path exercised where the ticket requires it | open | none | none | true |  |
| 19 | W-04 | No second source of truth introduced | open | none | none | false |  |
| 20 | T-01 | Read AGENTS and current TODO or roadmap then choose its next unfinished accepted item | open | none | none | false |  |
| 21 | T-02 | Classify acceptance and wire a deterministic gate before dependent product edits | open | none | none | false |  |
| 22 | T-03 | Run positive and targeted negative controls and record intended gate verdicts | open | none | none | false |  |
| 23 | T-04 | Implement one highest-priority safe slice from the existing backlog and verify its real invoker | open | none | none | false |  |
| 24 | T-05 | Write receipt and return the editable TODO with required SELF-AUDIT | open | none | none | false |  |

## Change log
changes: []
