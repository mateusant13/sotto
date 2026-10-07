# 07 — Engine Process (STUB — committed first so it cannot be lost)

Lane: `feat/engine-contract`. Status: **STUB**, being filled in.

## Intent

ONE engine process owning capture + ASR + index. The Engine is the PARENT and the
UI is a reconnectable CHILD: if the UI dies, recording must continue.

## Proven substrate (to be cited with file:line in the full spec)

- `worker/sotto_worker.py` ~374-377 (`emit()`) — JSON Lines over stdout.
- `worker/sotto_worker.py` ~942-1088 — device ladder.
- `worker/sotto_worker.py` ~1090 — `resample_to_16k`.
- `worker/sotto_webview.py` ~5964-5975 — consumer with watchdog.

## TODO

1. Command/event table, all JSON Lines, including `stdin -> cut`.
2. Lifecycle: attach / detach / crash / reattach.
3. Bounded queues, drop-with-counter, never block.
4. Why SQLite is the durable spine and not the bus.
5. Optional `src/engine/protocol.py` validator, both colours.