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

## Side observation, not part of the decision

replay-ring.CURRENT.js duplicates replay-ring.js, including its import and its call site. I
have not measured which one the product loads and I am not touching either. It is recorded
here so it is not lost, because a duplicated module means an edit to one of them may not
reach the running product.
