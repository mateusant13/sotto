# Owner model and reviewer routing

Apply this policy when working in the owner's projects. It selects agent/subagent models only; it does not change an application's runtime model chain.

## Workers and reviewers

1. Try the configured free worker or reviewer routes first when they are available.
2. Owner route, 2026-10-28: paid routes are also a primary lane for parallel implementation work. Use the `paid-go` agent (DeepSeek V4.1 Flash on an OpenCode Go alias) and the `paid-minimax` agent (MiniMax M3.1 Flash on provider `minimax`). The `iceman` route was removed by owner order on 2026-10-28 — do not use or recreate it.
3. When a free route fails or reaches a quota limit, keep the task moving. For paid work, probe `DeepSeek V4.1 Flash` through `opencode-go-1`, then `opencode-go-2`, `opencode-go-3`, `opencode-go-4`, `opencode-go-5`, and `opencode-go-6`. Use the first alias that passes the live marker, tool-event, and task-artifact checks. A model listing alone is not a live route. Live probe of 2026-10-28: `opencode-go-1` DEAD, `opencode-go-2` DEAD, `opencode-go-3` DEAD, **`opencode-go-4` LIVE**, `opencode-go-5` DEAD, `opencode-go-6` LIVE.
4. If none of the six Go aliases answers, use `MiniMax M3.1 Flash` through provider `minimax` only. Never route MiniMax through OpenCode Go or another provider.
5. Use no other paid model or provider unless the owner changes this policy.
6. Every paid lane obeys the owner's safety rule: delete nothing. No `rm`, `del`, `git rm`, `git clean`, `git checkout --`, `git reset --hard`, no killing processes, and no touching the owner's personal files, archives, games or volume content.

## Review batching

Before dispatch, group similar tickets and changes that share the same technical subject, acceptance boundary, and evidence into one review brief. When free review routes are exhausted, use **one paid reviewer per distinct subject per review cycle**. Do not pay for duplicate reviews of the same subject. Keep materially different subjects in separate briefs. If a later fix changes only one subject, re-review only that subject. The author never approves their own work.

## No quota-stalled lanes

Model or provider exhaustion never justifies an idle or `blocked` lane. Try the next authorized route. While a review route is being restored, continue implementation, gate/bootstrap work, verification, or other independent items. Keep the missing review evidence open and retry; never convert missing evidence into `PASS` or claim closure without a required review.

If all authorized routes are temporarily unavailable, preserve the lane as active/open, continue every safe actionable item, and retry through the next route when available. A process silence ceiling is for diagnosing a wedged request; it is not a work quota or permission to discard the task.

## Evidence and resource use

Record the provider/account alias, model, route probe, and sanitized outcome. Never record credentials. Do not cap agent count or tool calls. Use the Watcher for actual heavy local processes; model requests, reads, edits, and agent lanes are not themselves heavy processes.
