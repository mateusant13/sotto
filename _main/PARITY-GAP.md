# ShadowPlay Parity Gap — verified against source

WINDOW: this lane (`lane/parity`). Every claim below is checked against code in
`app/panel/*`, `worker/sotto_worker.py`, `app/webview/*`. The pre-existing
`SHADOWPLAY-PARITY.md` is treated as an untrusted starting point, not evidence.

Status is exactly one of IMPLEMENTED (code exists AND was seen running),
SOURCE-ONLY (code exists, never observed running), ABSENT (named paths searched,
listed), UNSEARCHED (not searched — never counted as ABSENT).

Table and counts: filled in below as the search completes.