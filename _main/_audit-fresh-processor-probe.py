#!/usr/bin/env python3
"""Is a SECOND streaming processor really independent? (the assumption F12 rests on)

WHY: `worker/sotto_worker.py`'s second pass (M3) now swaps the LIVE cache-aware
front end for a FRESH one (`fresh_processor()`, audit F12) so the pass cannot
advance the live mel/VAD state, and a device change installs a new one
(`reset_frontend()`). Both rest on ONE unmeasured assumption, stated by the lane
that wrote them:

    `og.Model.create_streaming_processor()` may be called repeatedly on one
    `og.Model`, and each processor owns INDEPENDENT mel/VAD state.

If the second call raises, the fix degrades to "keep the live front end" and the
pass is no better than before. If it succeeds but SHARES state, the fresh front
end is a no-op wearing the name of a cure — the exact defect class this repo keeps
finding. So it is measured here, with a decisive property rather than an
impression:

  * A processor that has consumed a FULL chunk (chunk_samples) is entitled to
    return features on the next call;
  * a FRESH processor given LESS than one chunk must NOT be able to return
    features, unless its buffer is shared with the first one.

That is the measurement: fill processor A to the brim, then hand processor B a
partial chunk and look at what comes back.

No audio device, no window, no app: `og.Model` + `process()` on zeros, exactly the
call the worker makes. Device-free by construction.

    python _main/_audit-fresh-processor-probe.py [--model DIR]

Exit 0 when independence holds, 1 when it does not, 2 on a setup error (the probe
never guesses).
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
CONFIG = os.path.join(ROOT, 'worker', 'config.json')
LOG = os.path.join(HERE, '_audit-probe', 'fresh-processor.log')

_lines: list[str] = []


def log(msg: str) -> None:
    _lines.append(msg)
    with open(LOG, 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(_lines) + '\n')
    print(msg, flush=True)


def main() -> int:
    argv = sys.argv[1:]
    model_dir = (argv[argv.index('--model') + 1] if '--model' in argv else None)
    if model_dir is None:
        try:
            with open(CONFIG, encoding='utf-8') as fh:
                cfg = json.load(fh)
        except OSError as exc:
            log(f'SETUP ERROR: cannot read {CONFIG}: {exc!r}')
            return 2
        model_dir = os.path.join(ROOT, 'worker', cfg['model']['dir'])
    if not os.path.isdir(model_dir):
        log(f'SETUP ERROR: model dir absent: {model_dir}')
        return 2

    try:
        import numpy as np
        import onnxruntime_genai as og
    except Exception as exc:  # noqa: BLE001
        log(f'SETUP ERROR: import failed: {type(exc).__name__}: {exc}')
        return 2

    with open(os.path.join(model_dir, 'genai_config.json'), encoding='utf-8') as fh:
        genai = json.load(fh)
    model_cfg = genai.get('model', {})
    chunk = int(model_cfg.get('chunk_samples') or 8960)
    log(f'model     : {model_dir}')
    log(f'chunk_samples: {chunk} (from the model dir\'s own genai_config.json)')

    try:
        model = og.Model(model_dir)
    except Exception as exc:  # noqa: BLE001
        log(f'SETUP ERROR: og.Model failed: {type(exc).__name__}: {exc}')
        return 2

    failures: list[str] = []

    # ── ARM 1: the API assumption itself — a second processor can exist ──────
    try:
        a = model.create_streaming_processor()
        b = model.create_streaming_processor()
    except Exception as exc:  # noqa: BLE001
        log(f'FAIL arm1 a second create_streaming_processor() RAISED: '
            f'{type(exc).__name__}: {exc}')
        log('VERDICT: RED — F12 degrades to "keep the live front end"')
        return 1
    log(f'PASS arm1 two processors exist, distinct objects: {a is not b}')

    # VAD OFF for the buffering question: with VAD on, `None` can mean "gated"
    # and the arm could not tell buffering from gating.
    for p in (a, b):
        try:
            p.set_option('use_vad', '0')
        except Exception as exc:  # noqa: BLE001
            log(f'SETUP ERROR: set_option failed: {exc!r}')
            return 2
    log('use_vad=0 for both (the arm must not confuse "gated" with "no buffer")')

    zeros_full = np.zeros(chunk, dtype=np.float32)
    zeros_part = np.zeros(chunk // 2, dtype=np.float32)

    # ── ARM 2: processor A takes a FULL chunk and returns features ───────────
    try:
        fa = a.process(zeros_full)
    except Exception as exc:  # noqa: BLE001
        log(f'SETUP ERROR: A.process(full) raised: {exc!r}')
        return 2
    a_had = fa is not None
    log(f'{"PASS" if a_had else "FAIL"} arm2 A returns features after a FULL chunk'
        f'  real={a_had} want=True')
    if not a_had:
        failures.append('arm2')

    # ── ARM 3: the fresh processor given HALF a chunk cannot have features ───
    # If B shared A's buffer, B would already hold a chunk's worth of context and
    # this call could return features. With independent state it cannot.
    try:
        fb = b.process(zeros_part)
    except Exception as exc:  # noqa: BLE001
        log(f'SETUP ERROR: B.process(partial) raised: {exc!r}')
        return 2
    b_had = fb is not None
    independent = not b_had
    log(f'{"PASS" if independent else "FAIL"} arm3 a FRESH processor with HALF a '
        f'chunk returns nothing  real={b_had} want=False')
    if not independent:
        failures.append('arm3')

    # ── ARM 4: and B is not simply dead — give it the other half ─────────────
    # A processor that never returns anything would make arm 3 pass vacuously.
    try:
        fb2 = b.process(zeros_part)
    except Exception as exc:  # noqa: BLE001
        log(f'SETUP ERROR: B.process(second half) raised: {exc!r}')
        return 2
    b_ready = fb2 is not None
    log(f'{"PASS" if b_ready else "FAIL"} arm4 B returns features once ITS OWN '
        f'buffer holds a full chunk  real={b_ready} want=True')
    if not b_ready:
        failures.append('arm4')

    # ── ARM 5: A is still usable after B consumed a chunk of its own ─────────
    # WAS MIS-SPECIFIED in the first draft of this probe, and the correction is
    # the point: it handed A HALF a chunk and demanded features, which the
    # front end's own contract forbids — each `process()` call is ONE chunk, so a
    # partial call right after a consumed chunk must return nothing (that is
    # exactly what arm 3 sees on a FRESH processor). The instrument was wrong,
    # not the code: a RED here would have indicted `fresh_processor()` for
    # obeying its documented chunk contract. The honest question is whether A
    # still WORKS — i.e. B's traffic did not drain or corrupt it — so A gets a
    # full chunk of its own.
    zeros_full_b = np.zeros(chunk, dtype=np.float32)
    try:
        fa2 = a.process(zeros_full_b)
    except Exception as exc:  # noqa: BLE001
        log(f'SETUP ERROR: A.process(own full chunk) raised: {exc!r}')
        return 2
    a_still = fa2 is not None
    log(f'{"PASS" if a_still else "FAIL"} arm5 A still returns features on its OWN '
        f'full chunk after B consumed one  real={a_still} want=True')
    if not a_still:
        failures.append('arm5')

    log('')
    if failures:
        log('VERDICT: RED — ' + ', '.join(failures)
            + ' (F12\'s fresh front end is not a cure as written)')
        return 1
    log('VERDICT: GREEN — two processors from one og.Model are independently '
        'buffered, so `fresh_processor()`/`reset_frontend()` really hand the pass '
        'and a new device an EMPTY front end.')
    log('SCOPE: this measures the mel/VAD buffer independence through '
        '`process()`. It does NOT measure the pass\' TEXT (the falsifier for the '
        'accuracy claim is two re-decodes of one segment, one per front end).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
