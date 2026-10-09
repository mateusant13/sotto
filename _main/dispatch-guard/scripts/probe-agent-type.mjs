// probe-agent-type.mjs - SubagentStart hook. ADVISORY, NEVER BLOCKS.
//
// WHY THIS EXISTS. The contract says `SubagentStart` matches on `agent_type`
// (references/local-plugin-hooks.md:74) and the owner-facing analysis held this to
// be the only surface that could make a seat such as `falsifier` mandatory rather
// than merely reachable.
//
// THAT CLAIM IS UNPROVEN, AND THIS FILE IS THE INSTRUMENT THAT SETTLES IT.
//
// Measured 2026-10-03 on this host, before writing this Plugin:
//   population  : 8 files matching runtime-*.log under
//                 C:\Users\Administrador\.minimax\v2\observability\logs
//   window      : 2026-10-02T19:59:58 -> 2026-10-03T02:36:34 local
//   instrument  : full-file literal search for SubagentStart, SubagentStop,
//                 agent_type, hookEventName, hookSpecificOutput, PLUGIN_ROOT
//   result      : 0 runtime-emitted hook events. Every textual hit was an agent's
//                 own tool-call payload (a sibling lane's grep, or this lane's own
//                 reads) echoed into the log - NOT an event emission.
//
// So `agent_type` is UNPROVEN, not absent: the channel has never carried a message
// because its producer does not exist yet (installed Plugin population = 0).
// Shipping a DENY keyed on an unmeasured field would mean shipping a hook whose
// behaviour is unknown, which is the silent-failure class this Plugin exists to
// kill.
//
// Therefore this hook does the only thing that is safe while unproven: it records
// the field verbatim, adds one line of context, and blocks nothing. The first real
// dispatch with the Plugin installed turns the unproven field into a measured one,
// at zero enforcement cost and zero false-block risk. The liveness gate then reports
// what was observed.
//
// If `agent_type` turns out to be populated, the deny that belongs here is a
// one-line change, and the observed values are in the ledger to justify it.

import { fingerprint, parsePayload, readStdin, record } from "./ledger.mjs";

const CONTEXT =
  "Dispatch seat constraint (mcode-dispatch-guard): before starting, confirm the seat " +
  "can produce the artifact you are about to ask for. A read-only role (scout, explore, " +
  "verifier, review) must not be handed a file to write; either change the seat or drop " +
  "the file from the brief. When you close, your final line must answer explicitly: " +
  "'Does your implementation meet the spec? YES - <sentence>' or 'NO - <which part and why>'.";

async function main() {
  const raw = await readStdin();
  const payload = parsePayload(raw);

  const agentType = typeof payload.agent_type === "string" ? payload.agent_type : null;
  const agentId = typeof payload.agent_id === "string" ? payload.agent_id : null;

  // The measurement. `populated: false` is recorded explicitly so a later reader can
  // tell "field absent" from "field never observed" - they are different states and
  // collapsing them is how an absence gets published as a fact.
  record({
    event: payload.hook_event_name || "SubagentStart",
    verdict: "OBSERVED",
    action: "context_only",
    agent_type_present: agentType !== null,
    agent_type: agentType,
    agent_id_sha: fingerprint(agentId || ""),
    session: payload.session_id || "unknown",
  });

  // Advisory only. No `decision` key is ever emitted here, so this hook cannot
  // block a turn no matter what the field contains.
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "SubagentStart",
        additionalContext: CONTEXT,
      },
    }) + "\n",
  );
  process.exit(0);
}

main();
