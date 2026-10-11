# tools/ -- measurement instruments. NOT part of the product.

`detectors.mjs` is not a module of the app. Nothing in `app/shadowplay` imports it,
and `index.js` does not re-export it. It exists so that a measurement can be checked
by something that is not the author of the measurement.

Run its self-test directly:

    node tools/detectors.mjs

It prints `RESULT_SENTINELS 16 passed, 0 failed` and exits 0 when every predicate
agrees with its own sentinel pair. Importing the predicates does NOT run the suite;
call `runSentinels()` for that.

Why it exists, with the WINDOW each defect was caught:

  - `extractResult` rejects `#getJobFromResolveResult` -- PowerShell `-match` is
    case-insensitive and that loader frame contains the word "Result". It was read as
    a test result for three consecutive runs at WINDOW_UTC 2026-10-11T03:03Z.
  - `isNonNumericToken` refuses display text such as `5\n` -- a token detector fed
    its own formatted output at WINDOW_UTC 2026-10-11T04:58Z.
  - `isEmptyHashStreamTrigger` requires rc == 0 AND zero lines -- testing only the
    second half flagged an ffmpeg ERROR exit as a trigger, same window.
  - `classifyArm` returns INVALID for a mutant that does not parse -- three arms were
    reported RED when the module had not loaded at all, WINDOW_UTC 2026-10-11T04:50Z.

RULE: if you add a predicate, add the case that must pass and the case that must fail.
A detector with one case is a detector that agrees with you.
