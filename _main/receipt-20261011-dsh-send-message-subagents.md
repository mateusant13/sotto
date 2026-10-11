# Receipt - DSH `send_message` could not reach subagents (2026-10-11)

Owner request, verbatim: *"fix the subagents. in the code of deepseek harness/dsh. then continue.
dont lose track"*. Scope: the DSH checkout at
`H:\env\npm-global\node_modules\@deepseek-ai\dsh\` (NOT the Sotto tree).

## 1. The defect, as measured

`send_message({target: <subagent id>})` failed with
`ToolCallError: active teammate "<id>" not found` for THREE distinct ids handed out by the
`subagent` tool in this session: `4f34e80d-e734-4ded-bd4d-53a3799e8176`,
`996b48e7-6b6a-41ee-aece-eb9ecb88ce77`, `ab6aa85e-14ba-4888-a91e-c09cf90c07d6`. The `subagent`
tool description promises the opposite: "a subagent id you can continue with `send_message`".

## 2. Root cause (located, not guessed)

TWO tools are registered under the name `send_message`, and the one this session exposes is the
Agent Team one:

| plugin | parameters | resolver |
|---|---|---|
| `dsh-experimental-tool-agent-team` | `{target, message}` | `ctx.agentTeams.sendMessage` -> roster |
| `dsh-tool-subagent-control` | `{agent_id, message}` | `ctx.subagents.sendMessage` |

The Team path resolves the target through the roster only:
`TeamService.sendMessage` (`:1824`) -> `TeamMailbox.send` (`:790`) -> `sendAdmitted` ->
`resolveActiveMember(root, state, name)` (`:350`), which throws
`TeamError("active teammate ... not found", "TEAM_MEMBER_NOT_FOUND")` when the name matches no
active Team member (`:357`). Continuable subagents live in the SEPARATE `ctx.subagents` registry,
which the Team path never consulted - even though the Agent Team service already injects
`subagents` (`static inject` at `:1732`) and already calls `this.ctx.subagents.interrupt`,
`.startContinuable` and `steerHostSubagentPrompt`. `list_agents` showed only the Lead, confirming
subagents are absent from the roster.

Predicate premise verified behaviourally (not read off the source): importing the package and
constructing `new TeamError("x", "TEAM_MEMBER_NOT_FOUND")` gives
`code === "TEAM_MEMBER_NOT_FOUND"` and `instanceof Error === true`.

## 3. The patch

`dsh-experimental-agent-team/lib/index.js`
(75141 B / sha256 3600f5e87f91bedd16295d969f5811ce5f18431a40b38922f642153389d8d68f / mtime 2026-10-11T21:37:27.136Z):

1. `TeamMailbox.send` (`:790`) wraps the roster path and, on a roster miss ONLY, delegates to a new
   `sendToContinuableSubagent`, which calls
   `ctx.subagents.sendMessage(caller, brandString(target), structuredClone(content), {signal})` -
   the service that owns residency and cold resume - and returns the SAME `{messageId, status:
   "accepted"}` shape the tool schema already declares. Any other Team failure still propagates.
2. New module-level `isRosterMiss(error)` = `error instanceof TeamError && error.code ===
   "TEAM_MEMBER_NOT_FOUND"` (`:368`), so only a roster miss takes the fallback.
3. `TeamRoster.interrupt` (`:510`, reached via `TeamService.interrupt` `:1879`) gets the same
   fallback for a subagent id - and only when `ctx.agents.get(id)` names a LIVE agent; with no live
   agent the roster miss is rethrown rather than dressed up as success.

If the target is neither a teammate nor an addressable subagent, the error names BOTH facts
(`<roster miss>; it is also not an addressable continuable subagent (<subagent error>)`) instead of
one of them.

`dsh-experimental-tool-agent-team/lib/index.js`
(19150 B / sha256 3bfc1765f0b138152fa77a1e402df7f9b554392b7933a799615df0e07f019077 / mtime 2026-10-11T21:41:21.860Z): four description fixes so the contract the model reads matches the code -
`send_message` and `interrupt_agent` now state that a continuable subagent id is accepted, the
`target` parameter says so, and `list_agents` now says it lists TEAM MEMBERS ONLY (subagents never
appear there), which is exactly the confusion this defect produced.

## 4. Verification (in-process; nothing was launched)

* REAL ESM import of both patched modules: `IMPORT OK`, exports intact
  (`TeamError, TeamId, TeamMessageId, TeamService, TeamTaskId, default`),
  `TeamService.prototype.interrupt` and `.sendMessage` still functions.
* 9 source checks GREEN: mailbox fallback call, the `ctx.subagents.sendMessage` call, the predicate,
  the roster-interrupt fallback + its `ctx.subagents.interrupt(brandString(target))` call, the two
  delegation edges (`:1824` -> mailbox, `:1879` -> roster), and the two description fixes.
* Class ownership proved by line offsets, because the first structural guess was WRONG: the patched
  `send` is `TeamMailbox` (`:790`) and the patched `interrupt` is `TeamRoster` (`:510`) - and the
  exported `TeamService` delegates to exactly those two. `TeamService` itself starts at `:1731`.
* NEG-ARM: a mutant copy with the fallback call replaced by `throw error`
  (`I:\cc-tmp\mutant-agent-team.js`, 75 077 B) turns the fallback check RED. The check can say NO.

## 5. NOT MEASURED / limits (stated, not hidden)

* **The live path is UNVERIFIED.** The harness serving this session already has the pre-patch module
  in memory, so `send_message` to a subagent id still fails IN THIS SESSION. Proof requires a
  harness restart; until then this is a code+import+neg-arm result, not a delivery result.
* The patch lives in an npm-INSTALLED package. `npm install`/upgrading `@deepseek-ai/dsh` will
  overwrite it; no patch file was left in the package tree.
* `list_agents` still does not list subagents (unchanged behaviour, now documented).
* Whether the SAME defect affects any other Team-scoped tool that resolves by name (`team_task_*`
  owners) was NOT audited - only `send_message` and `interrupt_agent` were.

Instrument: in-process `node` (import + source assertions + mutant), no shell, no app launch.
