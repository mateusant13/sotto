# Receipt — harness title/summary practice survey

Deliverable: `docs/harness-title-practice.md`.
Task: read `G:\superharness\repos\` and report how harnesses generate the title of a
conversation/prompt/session, then recommend a title+summary design for Sotto's hourly Qwen pass.

**Hard rule obeyed:** `G:\` was never written to. All output is under `H:\sotto`.
`worker/**`, `app/**`, `docs/qwen-hourly-plan.md` and `docs/qwen-model-choice.md` were **read only
where noted** and **not edited**. No model was downloaded or loaded. No window was created —
every command was a pwsh/rg/read invocation, no GUI launched.

---

## 1. What I actually did

| # | Action | Instrument | Result |
|---|---|---|---|
| 1 | Listed `G:\superharness\repos\` | `Get-ChildItem` | **57 directories**, not the brief's list — see §2 |
| 2 | Whole-tree pattern sweep A (title phrases) | `rg` background job `pwsh-835` → `_main/arch-title-grep-A.txt` | exit 0, **222 392 B**, 1 280 hits, 32 repos |
| 3 | Whole-tree pattern sweep B (title identifiers) | `rg` background job `pwsh-836` → `_main/arch-title-grep-B.txt` | exit 0, **243 540 B**, 1 651 hits, 23 repos |
| 4 | Union + filter to high-signal lines | pwsh → `_main/arch-title-selected.txt` | 2 916 unique lines → **843 selected** |
| 5 | Per-repo ABSENT classification | `rg` background job `pwsh-901` → `_main/arch-title-absent-scan.txt` | 41 repos classified with hit counts |
| 6 | Direct reads of the hit files | `read` / `rg -n` | 17 harnesses' title logic read in source |
| 7 | ORT-GenAI parameter verification | `py -3 -c`, `rg` over `site-packages` | §6 — a real finding |

**Why not the `grep` tool:** it timed out twice at its 30 s cap on this tree. All searching was done
with `C:\Program Files\Python311\Scripts\rg.exe` directly, as background jobs where the tree was big.

**Why no subagents:** attempted 4 parallel `subagent` calls for cluster sweeps; all four were
rejected with `subagent depth 2 exceeds maxDepth 1` (I am already a delegated child). The sweep was
therefore done serially by me. This is disclosed because it affects coverage confidence: a single
agent reading 57 repos in one context is thinner than four agents' worth of per-repo reading.

---

## 2. The directory listing (corrected)

The brief's list was explicitly "not exhaustive". The complete 57: `agency-agents`, `Agent-Reach`,
`AI-Scientist`, `aider`, `alethe-agents`, `anthropics-skills`, `Bend1`, `Bend2`, `broot`, `buzz`,
`claude-squad`, `cline`, `codebase-memory-mcp`, `Codewhale`, `deepseek-harness`,
`dsh-anchored-standard`, `dsh-router-standard`, `dsh-routing-suite`, `dsh-super-injector`,
`freebuff`, `Fusion`, `fx`, `gastown`, `gentle-pi`, `graft`, `grok`,
`grok-bot-0.18-reconstructed`, `gstack`, `herdr`, `hermes-agent`, `jcode`, `langgraph`, `Maestro`,
`minimax-code`, `obra-superpowers`, `oh-my-pi`, `openai-agents-python`, `openclaw-audit`,
`opencode`, `OpenHands`, `OpenMontage`, `optimus-prime`, `orca`, `pi`, `prime-agent`,
`pydantic-ai`, `qwen-code`, `skim`, `SWE-agent`, `t3code`, `tau`, `terminal-src`, `unreal-agent`,
`walgit`, `warp`, `wt-comp-guard-verify`, `ZCode` (+ `imageharnessestierlist.jpg`).

**Entries the brief `opencode`-family wording hid:** there is one `opencode` (a monorepo, not
several), and the brief also named `AI-Scientist` twice. The `opencode` checkout carries the
**most complete title instrumentation of the whole set** — a `/packages/core/src/plugin/agent.ts`
copy of the prompt, a `/packages/opencode/src/agent/prompt/` copy, and a
`/packages/opencode/test/lib/llm-server.ts:609` assertion
(`JSON.stringify(body).includes("Generate a title for this conversation")`).

---

## 3. Paths read, in full or in relevant part

### 3.1 Title generation — read and quoted

| Path (`G:\superharness\repos\` prefix) | Lines read |
|---|---|
| `hermes-agent\agent\title_generator.py` | **whole file, 762 lines** |
| `opencode\packages\opencode\src\agent\prompt\title.txt` | whole file, 44 lines |
| `opencode\packages\opencode\src\session\prompt.ts` | 180–269 |
| `opencode\packages\opencode\src\agent\agent.ts` | 225–304 |
| `opencode\packages\opencode\src\provider\provider.ts` | 1905–1944 |
| `opencode\packages\core\src\plugin\agent.ts` | 25–114 |
| `deepseek-harness\packages\session\session-title-llm\src\index.ts` | **whole file, 303 lines** |
| `deepseek-harness\packages\session\session-title\src\normalize.ts` | **whole file, 74 lines** |
| `deepseek-harness\packages\session\session-title-first-prompt-llm\src\index.ts` | whole file, 40 lines |
| `deepseek-harness\packages\session\session-title\src\index.ts` | 1–120 (of 835) |
| `deepseek-harness\packages\session\session-title\README.md` | whole file, 149 lines |
| `deepseek-harness\packages\bundle\base\cordis.patch.yml` | 45–84 |
| `deepseek-harness\packages\compaction\compaction-basic\src\summarizer.ts` | **whole file, 221 lines** |
| `deepseek-harness\packages\compaction\compaction-basic\src\config.ts` | grep only |
| `oh-my-pi\packages\coding-agent\src\utils\title-generator.ts` | 1–220 (of ~400) |
| `oh-my-pi\packages\coding-agent\src\prompts\system\title-system.md` | whole file, 3 lines |
| `oh-my-pi\packages\coding-agent\src\prompts\system\title-marker-instruction.md` | whole file, 1 line |
| `oh-my-pi\packages\coding-agent\src\tiny\text.ts` | 1–300 (grep with line numbers) |
| `oh-my-pi\packages\coding-agent\src\tiny\message-preproc.ts` | 127–155 |
| `qwen-code\packages\core\src\services\sessionTitle.ts` | 1–250 (of 346) |
| `minimax-code\...\assets\agents\desktop-task\session-title\system.md` | whole file, 41 lines |
| `minimax-code\...\sessions\title\session-title-service.ts` | grep with line numbers |
| `ZCode\...\runtime\methods\title-generation-sidecar.ts` | 20–59 + grep |
| `fx\src\core\session\session_title_generation.zig` | 1–100 (of 659) |
| `Fusion\packages\core\src\ai\ai-summarize.ts` | 20–99, 933–990, + grep |
| `grok\crates\codegen\xai-grok-shell\src\session\helpers\session_summary.rs` | 1–80, 190–269 |
| `grok\...\session\acp_session_impl\title_refresh.rs` | 1–60 |
| `t3code\apps\server\src\textGeneration\TextGenerationPrompts.ts` | 205–274 (of 318) |
| `freebuff\common\src\util\thread-title.ts` | **whole file, 46 lines** |
| `openclaw-audit\src\gateway\dashboard-session-title.ts` | grep with line numbers |
| `OpenHands\src\utils\title-llm-profile.ts` | whole file, 36 lines |
| `warp\app\src\ai\conversation_rename.rs` | grep with line numbers |
| `Codewhale\crates\tui\src\session_manager.rs` | grep with line numbers |
| `cline\sdk\packages\core\src\services\session-data.ts` | 205–249 |

### 3.2 Summarisation / compaction — read and quoted

| Path | Lines read |
|---|---|
| `opencode\packages\opencode\src\agent\prompt\summary.txt` | whole file, 11 lines |
| `opencode\packages\opencode\src\agent\prompt\compaction.txt` | whole file, 5 lines |
| `opencode\packages\core\src\session\compaction.ts` | 1–30, 100–219 |
| `deepseek-harness\...\compaction-basic\src\summarizer.ts` | whole file (§3.1) |
| `hermes-agent\agent\context_compressor.py` | 4490–4559, 4625–4669, + grep over 7 858 lines |

### 3.3 Sotto's own docs — read, not edited

- `H:\sotto\docs\qwen-hourly-plan.md` — grepped for `prompt|max_new_tokens|temperature|titulo|summary|resumo|think|loop|enable_thinking`; read 684–733 and 824–883. **Not edited.** Three divergences are recorded in the deliverable's §5.7.
- `H:\sotto\docs\qwen-model-choice.md` — **not read.** It was not needed: the model class was fixed by the brief (0.6 B / 0.8 B int4 ORT-GenAI), and reading it would not have changed the recommendation. Disclosed so the omission is not mistaken for coverage.
- `H:\sotto\AGENTS.md` — auto-loaded, not grepped (the house rule forbids grepping for it).

---

## 4. What I could NOT find — stated as findings

1. **`aider` has no session-title logic.** Its only pattern hit is front matter in
   `aider\website\docs\usage\caching.md:2`. Searched `aider\aider\` with both pattern sets.
2. **`SWE-agent`, `langgraph`, `AI-Scientist`, `Agent-Reach`, `codebase-memory-mcp`,
   `claude-squad`, `gentle-pi`, `graft`, `herdr`, `skim`, `walgit`, `wt-comp-guard-verify`,
   `terminal-src`, `broot`, `Bend1`, `Bend2`, `obra-superpowers`, `dsh-router-standard`,
   `dsh-routing-suite`, `dsh-super-injector` — 0 matches** on either pattern set.
3. **`cline` has no model-based titling.** `deriveTitleFromPrompt`
   (`sdk\packages\core\src\services\session-data.ts:239-249`) is a pure heuristic: first line, cap
   120. Note that this *contradicts* the common belief that Cline titles with the model — the
   models in this checkout only *display* a title.
4. **No harness found that generates title and summary in ONE call.** This is the single most
   consequential absence, because `docs\qwen-hourly-plan.md:697-701` proposes exactly that. Every
   title implementation titles from the first message; every summary implementation is a separate
   call over the whole input.
5. **No harness in this set uses `stop` sequences for titles.** Every one relies on a token cap, a
   marker/JSON contract, a deadline, or a sanitiser — never on a stop string. Worth knowing before
   Sotto reaches for one.
6. **`qwen-code`'s `session-title-design.md`** (`qwen-code\docs\design\session-title\session-title-design.md`)
   was located by the sweep but **not read**; the implementation file carried the prompt, the
   parameters and the rationale inline. Disclosed as unread.
7. **`oh-my-pi\.omp\skills\system-prompts\small-models.md`** was located as a title-adjacent hit and
   **not read**. Given oh-my-pi's `TITLE_MAX_TOKENS = 1024` comment is the most Sotto-relevant line
   found, this file is the best candidate for a follow-up read.
8. **`minimax-code`'s `session-title-model-adapter.ts`** was located; the *model* it selects was not
   read out. The `maxTokens`/`timeoutMs`/retry constants and the prompt were, and those are what the
   recommendation uses.
9. **`grok`'s `storage\summary_write.rs`** and `session\persistence.rs` were hit by the sweep and
   not read — they are persistence paths, not prompt paths.

---

## 5. Read vs inferred

### 5.1 READ (quoted, with file:line in the deliverable)

- Every fenced prompt block in `docs/harness-title-practice.md` §3, verbatim from the file.
- Every parameter value attributed to a named harness: `hermes` `max_tokens=64` / `temperature=0.3`;
  `DSH` `maxOutputTokens=64` / `timeoutMs=60000` / `targetWords=5`; `qwen-code` `temperature=0.2` /
  `maxOutputTokens=100` / `maxAttempts=1`; `opencode` `temperature=0.5` / `retries=2`;
  `minimax` `TITLE_MAX_TOKENS=1000` / `TITLE_TIMEOUT_MS=10000` / `[500,2000]`;
  `ZCode` `timeout 60000` / `MAX_TITLE_INPUT_CHARS=1200` / `MAX_TITLE_CHARS=100`;
  `fx` `128` / `15000` / `2048 B` / `60 B`; `Fusion` `4000` / `60`;
  `grok` `with_max_output_tokens(100)` / `with_temperature(1.0)` / `TITLE_SOURCE_MAX_BYTES=8000` /
  `TITLE_MAX_BYTES=80` / `45 s`; `openclaw` `60` / `1000` / `30000`;
  `oh-my-pi` `TITLE_MAX_TOKENS=1024` / `MAX_TITLE_CHARS=80` / `MAX_TITLE_WORDS=12`;
  `t3code` `3-8 words, fewer than 40 characters`; `freebuff` `2000` / `60`;
  `Codewhale` `MAX_SESSION_TITLE_CHARS=100`; `cline` `MAX_TITLE_LENGTH=120`;
  `warp` `CONVERSATION_TITLE_MAX_CHARS=500`.
- The mechanism claims (two-stage at hermes; refresh-at-3-and-6-then-freeze at grok;
  provider-supersession at DSH; gate predicate at fx) — all read in source.
- **ORT-GenAI facts (§6)** — read from `site-packages`.
- All four "named failure modes" in §4.6, each with its implementing line.

### 5.2 INFERRED (labelled as such in the deliverable)

- **That `max_length` in ORT-GenAI 0.17.1 is a TOTAL-sequence bound, prompt included.** Inferred
  from three facts I *did* read: `runtime_config.search` has no `max_new_tokens` key
  (`builder_config.py:717-740`); `max_length` is validated against the exported `context_length`
  (`:789-795`); `min_length` and `max_length` are compared to each other (`:797`). The `.pyd`
  contains `max_length` and not `max_new_tokens`. **I did not run generation**, so the deliverable
  marks this a must-verify with a one-line probe rather than a fact.
- **That the schema constraint does not stop a thinking loop.** Reasoning: the harnesses' schemas
  constrain the *visible* output channel, and oh-my-pi's own comment says a local Qwen3's template
  can force thinking regardless of a `reasoning: false` flag. Labelled as inference.
- **That DSH's default title route is the main model.** Inferred from `cordis.patch.yml:62-69`
  setting no `provider`/`model` while `session-title-llm/src/index.ts:185-191` falls back to
  `request.route` (the logged main request). Labelled as inference.
- **That "3-7 words / sentence case / no quotes" is the industry consensus.** Counted across the
  prompts I read (13 of 17), which is evidence, not proof — the sample is one checkout directory.
- **The recommendation itself** (§5 of the deliverable) is my synthesis, not a quotation from any
  harness. Every constant in `§5.3` carries a harness provenance inline; the *combination* is mine.

### 5.3 NOT established

- Whether any *frontier* harness has a title mechanism the patterns missed because it lives behind a
  vendor SDK (e.g. `grok-bot-0.18-reconstructed`, `buzz`'s ACP adapter, `ZCode`'s `internal-methods`).
- Token-level cost or latency of any of these designs. Every latency figure in
  `docs/qwen-hourly-plan.md` §3.3/§4.3 is estimated, and nothing here changes that.
- Whether Sotto's 0.6 B/0.8 B int4 build will load at all. Out of scope for a reading task; still the
  first thing to verify (the plan says so at `:866-873`).

---

## 6. Two findings that are not about harnesses but that the task needed

Both are **checkable on this box** and both are in the deliverable.

### 6.1 The installed ORT-GenAI has no `max_new_tokens`

`C:\Program Files\Python311\Lib\site-packages\onnxruntime_genai-0.17.1.dist-info` — the version
`docs/qwen-hourly-plan.md:827` names. In `models\builder_config.py:717-740` the accepted
`runtime_config.search` keys are `batch_size, blank_penalty, chunk_size, diversity_penalty,
do_sample, early_stopping, length_penalty, max_length, min_length, no_repeat_ngram_size, num_beams,
num_return_sequences, past_present_share_buffer, random_seed, repetition_penalty, temperature,
top_k, top_p` — **no `max_new_tokens`**. A string scan of
`onnxruntime_genai.cp311-win_amd64.pyd` finds `max_length:1, min_length:1, do_sample:2,
repetition_penalty:2, max_new_tokens:0`. And `max_length` is bounded by the exported
`context_length` (`:789-795`): *"runtime_config.search.max_length exceeds the exported model
context_length"*.

Consequence: `docs/qwen-hourly-plan.md:833` (`set_search_options(max_length=max_tokens, …)` where
§4 defines `max_tokens` as **output** tokens) is very likely under-setting the bound — with a
~6 634-token prompt, `max_length≈185` sits *below* the prompt. The fix is one line
(`prompt_tokens + max_new`) plus an assert. **Not run; marked must-verify.**

### 6.2 The installed ORT-GenAI Qwen builder has no thinking switch

`rg -i 'think'` over
`C:\Program Files\Python311\Lib\site-packages\onnxruntime_genai\models\builders\qwen.py` (76 333 B)
returns **0 matches**. There is no `enable_thinking`, no `no_think`, no reasoning handling at the
builder level. So Sotto cannot disable thinking via the runtime — only via the chat template and the
prompt, which is exactly the situation `oh-my-pi`'s `TITLE_MAX_TOKENS = 1024` comment describes.
This is *why* the recommendation does not lean on `/no_think` and instead puts a wall-clock check
between token steps.

---

## 7. Things I would do next, in order

1. **Run the `max_length` probe** (§6.1). One line, decides whether the cap is real.
2. **A/B `do_sample=False` vs `repetition_penalty=1.1`** on one real hour, measuring
   `finish_reason == "deadline"` rate. The recommendation defaults to greedy; the penalty is the
   documented second-line loop-break and should be measured, not assumed.
3. **Read `oh-my-pi\.omp\skills\system-prompts\small-models.md`** — the single best unread lead
   (§4.7).
4. **Measure prefill**, not generation, for a 6 634-token prompt on CPU. The plan's `0.05 s/token`
   is an assumption and it decides whether the title call should use 1 200 chars (my recommendation)
   or the whole hour.
