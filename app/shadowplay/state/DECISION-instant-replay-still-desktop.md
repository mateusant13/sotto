# DECISION NEEDED: should instant replay refuse a still desktop?

Status: OPEN. Owner decision. Written 2026-10-11 because the case is UNSPECIFIED and the
product already behaves, so silence is not neutral -- it is an unrecorded default.

## The question

The user presses F9 and nothing is saved, because the picture did not change enough to
cover its own clock. Should that be a refusal, or should the last seconds be saved anyway?

## What the product does today

replay-ring.js:340 refuses when verdict.contentSufficientToCoverClock is not true.
frame-accounting.js:367 defines that as longestUniqueRun >= oneSecondOfClock, where
oneSecondOfClock is expectedFps, so 30 frames at 30 fps. One observed refusal read:
"holds 28 contiguous distinct frames" -- 27 changing frames, about 0.9 s of movement in an
8-second capture.

## The evidence, with population and window

- Mechanism reproduced. POPULATION 2 clips (a still one, a mixed one), WINDOW_UTC
  2026-10-11T09:31:55Z and 09:34:41Z: still gives LONGEST_UNIQUE_RUN 1 and SUFFICIENT false;
  60 still frames plus 28 changing ones gives LONGEST_UNIQUE_RUN 29 and SUFFICIENT false.
- The busy case. POPULATION 4 real desktop captures, WINDOW_UTC 2026-10-11T09:27:19Z:
  frames 213-220, longestUniqueRun EQUAL to the frame count, SUFFICIENT true.
- Magnitude of the original failure NOT reproduced from the original event. That recording
  does not exist. POPULATION 1 clip I built.

## What the specification says

Nothing. POPULATION 9 product documents in I:\!manager\runs, 142 277 B, WINDOW_UTC
2026-10-11T09:53:32Z to 09:53:41Z. Pattern static|still desktop|idle|frozen|no motion|
unchanged|identical frame|distinct|transcriber|caption matched 14 lines across 8 of the 9,
and all 14 are incidental word usage. Not one addresses a picture that stops changing.

The only reason on record is a code comment in frame-accounting.js, and its reasoning is a
transcriber's: "a transcriber does not care that some frame somewhere was new; it cares
whether the picture kept changing". That is the captions and highlights path being applied to
instant replay.

## The options

1. Keep refusing. Cost: a user pressing F9 during a quiet moment gets nothing and no file.
   Benefit: no clip is delivered that claims to be the last N seconds but shows one frame.
2. Deliver anyway. Cost: a clip whose visible duration does not match its length, which is
   what the guard was built to prevent. Benefit: the keypress always produces something.
3. Refuse, but say so. Cost: small. The message already names the count; the overlay could
   show it. Benefit: the refusal becomes legible instead of looking like a failure.
4. Relax the bound for replay only, keep it for captions. Cost: two rules instead of one.

I have no standing to pick. The guard is currently justified by another feature's reasoning
and applied to this one, which is the thing worth a decision.

## What is NOT at issue

This is not a defect claim. The guard works, is measured, and is reachable. No product
defect survived the investigation that produced this file.
