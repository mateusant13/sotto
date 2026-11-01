# Owner directive — drain and stop gradually (relayed by the Droid lane, 2026-10-30)

This file is a copy of the durable bus message `f5fdf28137bc` (`droid -> sotto:*`) in
`I:\!manager\state\agent-bus\`. It is here because omp exposes no way to push a message into a live
session: `omp --help` has no message verb, `omp collab` reports no hosts, the omp IRC bus is in-process
memory, and `lane-dispatch --pi-session-fallback` refuses by design while a live process owns the
transcript ("a second writer would fork the conversation instead of delivering to it").

**What the owner asked for, in order:** read the new plans, decide yourself whether the work in flight
should land, resume the outstanding subagents, finish what is in flight, deliver, then stop gradually.

**Drain order**

1. Read the plans that landed since this lane branched — at minimum
   `docs/codeintel-completion/SUPER_ROADMAP_EXECUTION_2026-10-28.md` §"Mission mode — the only ordered
   queue" (M0–M7), `docs/CUDA_RUST_DECISION_2026-10-30.md`, and the mission lane
   `mission/one-codebase-1to10m-20261030` @ `6112b0a7` (published 2026-10-30).
2. For every outstanding subagent and in-flight edit: decide **land or discard**, with the evidence.
   Nothing stays undecided.
3. Land what you decided to land (commit + the gate you ran), or discard it and say so.
4. Deliver: write the decision list where the next session reads it.
5. Stop gradually: finish the turn, let the subagents return, then exit. Start nothing new.

**Acceptance test:** a reply listing (a) every in-flight item, (b) its land/discard verdict with the
evidence, (c) the commit or the explicit drop, (d) confirmation that no subagent is still running.

**Measured context from the neighbouring lane (so the two do not duplicate work)**

- This session (`01a185b5-…`) was live at 09:49: 23,136,345 → 23,154,022 bytes in 20 s.
- Its bun process 32356 launched `python bench_eg2.py` in
  `H:/VOD.RIP-data/embed-models-test/eg2eval/venv`, which held 73 % CPU / 2,824 MB (PID 22988) plus
  28 % / 688 MB (47568). It was stopped at 09:35 with its launcher because it saturated the host; if it
  is part of in-flight work, relaunch it bounded (thread cap or below-normal priority), not at 73 %.
- `.agents/work/*/full/` is now gitignored in the consultgpt repo: a 1225 MB `index.db` there is what
  made GitHub reject the mission push (`GH001`, 100 MB limit). Do not re-commit generated index output.

**How to acknowledge:** `python I:\!manager\tools\agent-bus.py ack --for sotto --id f5fdf28137bc`
(the reply path works — `droid` is now a registered party on the bus).
