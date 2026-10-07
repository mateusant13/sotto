SO UNDER THE SO REPLAY BUILD — CONTINUATION PASS

The owner is ABSENT. He asked (2026-10-07) for: worktrees by default, up to 30
subagents, keep researching how to build the ShadowPlay clone, move H:\aireplay
INSIDE the workspace (DONE — see BELOW), integrate everything into ONE app
called Sotto, frontend LAST, and keep working on a 3-minute heartbeat until the
app is finished.

You are ONE fire of that heartbeat. Do not restart, kill or re-launch
MiniMax Code. Never `git add -A`. Never touch the owner's sessions.

## WHERE THE WORK IS

- Everything is under `H:\sotto` (the workspace).
- The moved clone lives at `H:\sotto\_moved\aireplay` (6678 files).
- `H:\aireplay` is a JUNCTION pointing there, so every absolute path in the
  13 receipts still resolves. Do NOT delete the junction.
- Product name is SOTTO everywhere. `H:\aireplay` is only a legacy folder name.
- Lane briefs + roadmap: `H:\sotto\_moved\aireplay\ROADMAP.md` and
  `H:\sotto\_moved\aireplay\specs\`.

## THE ORDER (do not reorder it)

1. Research FIRST. Every claim is MEASURED / READ / UNKNOWN with the command
   that produced it. Never invent a number.
2. Concrete roadmap, then build.
3. FRONTEND LAST. Do not start UI work while a backend lane is unmeasured.
4. One app at the end, not two trees.

## MEASURED FACTS YOU MUST NOT RE-DERIVE (verified 2026-10-07)

- `cargo 1.97.1` WORKS on this host: `cargo generate-lockfile` -> rc=0,
  "Updating crates.io index", 7 packages locked. 1896 crates already vendored
  in H:\cargo\registry. The old claim "Tauri/Rust is abandoned here because
  cargo hangs on crates.io" is FALSE and must not be repeated.
- NVENC opens and initialises here; 10 concurrent sessions held, #11 refuses
  with status 21. See docs/research/03-nvenc-sessions.md.
- ASR: int8 ONNX Parakeet wins BOTH axes vs ternary (see AGENTS.md). ~0.9 GB.
- Embeddings: google/embeddinggemma-2, ONE 768-d vector per call -> our 5 s
  window loop is what makes granularity exist.
- The replay ring, not the AI, is the memory hog (law 7).

## THE PASS

1. Read the last receipt in `H:\sotto\_moved\aireplay\receipts\` and the
   open items. Do not re-litigate settled facts.
2. Dispatch worktrees (H:\sotto-wt-<name>) toward the roadmap. Use subagents.
3. Verify what you claim. A gate that cannot say NO is worthless — every
   instrument ships BOTH colours.
4. Write the receipt. Then EXIT so the next fire can run. Never overlap.

Report honestly: what landed, what is UNKNOWN, what you did NOT do.
