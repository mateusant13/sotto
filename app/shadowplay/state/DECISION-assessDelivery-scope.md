# DECISION NEEDED: should the delivery-content gate apply to instant replay at all?

Status: OPEN. Owner decision. Written 2026-10-11 alongside the still-desktop decision, and
closely related to it: that one asks what happens on a still screen, this one asks whether
the mechanism enforcing it belongs on this path.

## Blast radius, measured

POPULATION = every .js file under app/shadowplay, comments excluded, WINDOW_UTC
2026-10-11T10:01:29Z.

- Defined once: frame-accounting.js:322
  `export async function assessDelivery(path, expectedFps, expectedSeconds)`
- Called twice, in files that are copies of each other:
    replay-ring.js:330            verdict = await assessDelivery(source, this.#fps, seconds);
    replay-ring.CURRENT.js:275    verdict = await assessDelivery(source, this.#fps, seconds);
- Imported by the same two: replay-ring.js:9, replay-ring.CURRENT.js:9

So there is exactly ONE product call site, and the second "site" is a duplicated module.
Nothing in captions or highlights calls it, even though the reasoning inside
frame-accounting.js is a transcriber's. The gate was written for one consumer and reached
exactly one consumer, which is not the consumer the comment argues for.

## The question

assessDelivery refuses a clip that cannot stand in for its own clock. That is right for
captions and highlights, where a frozen picture produces no transcript. Is it right for
instant replay, where the user pressed a key asking for the last seconds of their screen?

Three coherent positions:

1. Same gate everywhere. One rule, no special cases. Cost: a quiet moment yields nothing.
2. Replay exempt, captions strict. Two rules. Cost: two things to keep consistent.
3. Same gate, replay reports it. One rule, and the refusal is legible to the user.

## What I cannot decide

Whether a saved replay should show a still picture for its whole length is a product
question about what a user expects from "instant replay". I have measurements on the
mechanism and no specification on the intent.

## CORRECTION, WINDOW_UTC 2026-10-11T10:06:13Z: the duplicate-module alarm was unfounded

This file originally carried a side observation saying replay-ring.CURRENT.js duplicated
replay-ring.js, and that an edit to one might not reach the running product. That was
wrong in the part that mattered, and the correction is here rather than only in a report.

I had found the second call site with a recursive Select-String and printed the file NAME
without its directory. A file inside _fix9/ printed identically to a sibling in the product
directory, and I read the name as a location.

Measured, POPULATION = every .js under app/shadowplay, WINDOW_UTC 2026-10-11T10:06:13Z:
    replay-ring.js                19 458 B  sha E8499478C754D8F3  mtime 2026-10-11T01:20:32Z
    _fix9/replay-ring.CURRENT.js  16 145 B  sha F8FBF11319942417  mtime 2026-10-10T19:34:43Z
    *.CURRENT.js in the whole tree: 1 -- the one in _fix9, which holds 6 files
    index.js:58  export { ReplayRing, ... } from "./replay-ring.js";
    index.js:76  import { ReplayRing, ... } from "./replay-ring.js";
    index.js does not mention _fix anywhere

So the product loads replay-ring.js, the file this session edited. The _fix9 copy is a stale
snapshot roughly a day old and 3 313 B smaller, sitting in a fix folder that is not on the
product path. Nothing I did today to the ring failed to reach the product.
