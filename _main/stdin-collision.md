# stdin implementation collision (orchestrator, not a lane decision)

WINDOW: this turn. POPULATION: the two implementations only.

| impl | lines | branch | compiled? | tested? |
|---|---|---|---|---|
| StdinCtl (v8) | 621 | main (47bb030) | NO - never built | no |
| inline (v9) | 499 | feat/stdin-v9 (fe544e4) | YES rc=0, -Wall -Wextra zero warnings | yes: ping ok, RED arm clean |

git merge feat/stdin-v9 -> CONFLICT in _moved/aireplay/src/capture/main.cpp. Merge ABORTED.
Nothing was chosen. The decision needs a compile+test verdict on main's 621-line version.
Lane bg_432637ec is producing exactly that verdict.

Known defect (found by the v9 lane's own self-review, unverified on main):
the parser matches substrings, so a strict-equality parser on '\"cmd\"' and 'ping'
is required; substring matching would accept {\"cmd\":\"pingX\"}.
