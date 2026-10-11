# VERDICT: the keyframe chain of the Sotto capture path

Written 2026-10-11 to consolidate nine commits of investigation into one readable result.
Every claim below carries its population and its window. Claims without both are marked as
not measured rather than dropped.

## The invariant

A stored clip begins on an IDR, is remuxed from already-encoded bytes, and is never
re-encoded.

## The chain, in order of when it runs

| # | where | what it does | state |
|---|---|---|---|
| 1 | index.js:148 | encoder measures the capture's first IDR via ffprobe -skip_frame nokey | MEASURED |
| 2 | index.js:149 | refuses with ClipNotKeyframed if null or beyond tolerance | MEASURED |
| 3 | replay-ring.js:141 | contract: the ring trusts the caller, by design, with a reason | READ |
| 4 | replay-ring.js:278 | the ring re-verifies the STORED clip with NvencEncoder | MEASURED |
| 5 | replay-ring.js:330 | assessDelivery measures whether the clip covers its clock | MEASURED |

## The evidence, with population and window

**#1/#2, the capture-side condition.** POPULATION 2 clips. WINDOW_UTC 2026-10-11T09:40:41Z.
good.mp4 gives FIRST_IDR_SEC 0, refuses false. bad.mp4, cut with -copyts so its first
keyframe keeps its original timestamp, gives FIRST_IDR_SEC 1 and refuses true -- thirty times
the 0.0333 s tolerance.

**#2 on the product's own path, and why it is unreachable there.** POPULATION 4 real desktop
captures. WINDOW_UTC 2026-10-11T09:49:43Z. firstIdr was 0, 0, 0, 0 with frames 212-226. An
h264 encoder starts a fresh stream with an IDR at pts 0, so this branch does not fire through
capture() on this host. Not a defect; coverage comes from #4.

**#3 is a decision, not a gap.** replay-ring.js:141-143, verbatim: "the ring does not decide
this by arithmetic: backToNearestIdr already refused to guess, and an encoder is the only
thing that knows where its IDRs are."

**#4, the delivery-time check, driven through the real ring.** POPULATION 2 arms.
WINDOW_UTC 2026-10-11T09:46:46Z. Each arm pushes real encoded bytes with keyframe: true,
which the ring believes by contract, then lets instantReplay cut and save. The arm with its
first IDR at pts 1.0 was REFUSED with ClipNotKeyframed naming the measurement that fired, and
left 0 files, which also proves #discardRefused runs on this path. The arm with its first IDR
at pts 0 delivered.

**#5, the content gate.** POPULATION 4 clips on a curve, plus 4 real captures.
WINDOW_UTC 2026-10-11T10:13:46Z and 09:27:19Z. Two seconds of stillness followed by movement
gives LONGEST_UNIQUE_RUN 4, 13, 29, 46 at 0.1 s, 0.4 s, 0.9333 s and 1.5 s, with
contentSufficientToCoverClock false, false, false, TRUE. The threshold is oneSecondOfClock, 30
frames at 30 fps. Four real desktop captures gave longestUniqueRun equal to the frame count.

## That the running product loads the file this session edited

POPULATION 1 live module load. WINDOW_UTC 2026-10-11T10:10:46Z. import.meta.resolve, asked
of the runtime rather than read out of an import line, resolves ./replay-ring.js to
H:\sotto\app\shadowplay\replay-ring.js with sha256 e8499478c754d8f3..., identical to the file
by path and to Get-FileHash on disk. Nothing stands between this session's edits and the
running product.

## The failure this thread started from, and what it turned out to be

One gate run recorded a refusal reading "holds 28 contiguous distinct frames". I chased it
through four wrong theories of my own before landing on the right one:

- the ring draining between deliveries -- REFUTED, nothing mutates #segments on delivery
- a short capture from the encoder -- REFUTED, captures land at 212-226 in every run
- a duplicated replay-ring module -- REFUTED, replay-ring.CURRENT.js is in _fix9/, off the
  product path
- the screen being still -- CONFIRMED by the curve, and it is the product working correctly

The 28 sits one frame below the refusing point measured at 0.9333 s of movement.

## What is NOT established

The original recording does not exist. The curve predicts that a clip with under a second of
movement refuses; nobody measured the capture that failed. Everything else above is measured.

## The four corrections I made along the way, for whoever reads this next

1. Quoted a message that does not exist -- "contiguous decodable frames" where the source
   reads "contiguous distinct frames".
2. Called a working guard a defect, then a latent risk, before reading the contract at :141.
3. Reported a population of 8 documents when the directory holds 9, counting from an older
   window.
4. Reported a duplicated module after printing a filename instead of a path.
