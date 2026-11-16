"""A JANELA QUE NAO E' AUDIO NAO MERECE UMA DECODIFICACAO.

THE MEASURED DEFECT (2026-11-16, the owner's live worker, pid 20584, `--threads 2`):

    python _main/shell-thread-cpu.py 20584 --burst --seconds 40 --above 20
    BURST t=+1.0s fios=309.4% session-16-intra-op-3:73.4% ...-1:71.9% ...-0:71.9%
    BURST-END segundos_acima_de_20%=5 pico_fios=309.4% processo_total=31.9%

and, in the same window, the batch log (`_main/webview-run.log`):

    REDUX_BATCH_KICK reason=interval engine=parakeet audio_s=30.0 ... asrs=0
    STATUS_APPLIED text="redux-batch-empty"

`audio_s=30.0` on EVERY kick is the `REDUX_BATCH_PASS_MAX_S` cap: the pass never
drained, because each one decoded ten 3 s windows that contained NOTHING. The
tap, in the same minute, said `sample={"peak":0.0,"blocks":2.0}` and
`tap-silent-desktop window_s=4.0 endpoints=6 peak=1.0`. Two to three cores
producing zero captions, with a backlog that grew instead of draining.

WHY THIS IS A MODULE OF ITS OWN: the structural ratchet
(`_main/code-health-oracle.py`) forbids growing a file already in its baseline,
and a new file is the sanctioned place for extracted code -- the same reason
`worker/caption_noise.py` exists. The predicate, its floor and the measurement
that justifies the floor travel together, and `engine_policy.run_engine_pass`
imports it.

THE FLOOR IS NOT A NEW NUMBER. `worker/audio_recorder.py` already declares the
measured digital-silence pair of this class of machine:

    DIGITAL_SILENCE_PEAK = 1e-3      # measured 2026-10-06: peak 0.000122 on
    DIGITAL_SILENCE_RMS  = 1e-4      # every loopback with nothing playing

and uses it to drop a silent recording instead of writing a file full of zeros.
It is the SAME measurement for the SAME purpose, so this module IMPORTS it: a
second declaration of one number is the second truth this repo keeps paying for.

THE SHAPE IS THE CONSERVATIVE ONE -- BOTH floors must be crossed (`and`, never
`or`). A window is skipped only when its peak AND its RMS are under the floors:

  * digital silence (zeros, or the 0.000122 dead-tap): peak 0, rms 0 -> skipped;
  * room tone / dither (peak under the floor, rms over it): DECODED, because the
    RMS branch refuses to call it silence;
  * real speech: clears the peak floor by more than an order of magnitude. The
    oracle's `A2 quiet-but-real-decodes` arm decodes a -35 dBFS window (peak
    0.0178 = 17x the floor) on purpose, and `A4` decodes a window that is 99 %
    zeros with a 40 ms speech burst in it.

What is skipped is audio no engine can turn into words. The audio that is
skipped is still CONSUMED from the pending queue exactly as before (the pass
walks the same windows), and `run_engine_pass` publishes `silent_windows=N
silent_s=X` ONCE per pass, so "nothing was transcribed" never becomes
indistinguishable from "nothing was handed over".

MEASURED COST, both arms in one caged process on this box (2026-11-16, the real
parakeet export, `--threads 2`, `python -m watcher run --cpu 40 --io very-low`):

    UNGATED (pre-fix): 10 windows of digital silence -> wall 17.89 s,
            cpu 30.45 s (170 % of one core), and the three texts the engine
            produced were all `Mmm` -- i.e. the filler `admit_batch_caption`
            then drops, so the 30 CPU-seconds bought ZERO captions.
    GATED  (shipped): the same 30 s -> wall 0.0066 s, cpu ~0, `transcribe`
            calls 0, `load` calls 0, and `REDUX_ENGINE_DONE ... windows=10
            silent_windows=10 silent_s=30.0`.

The judge itself is 0.009-0.038 ms per 3 s window (`batch-silence-gate-oracle`
arm A11, ceiling 1,0 ms declared there), ~0.04 % of one window's decode.

ORACLE: `python _main/batch-silence-gate-oracle.py` (11 arms, both colours;
`--neg-arm` disables the call site and zeroes the floors, and requires the gate
arms to go RED: rc=1/0/2 as the house convention).
"""
from __future__ import annotations

from audio_recorder import DIGITAL_SILENCE_PEAK, DIGITAL_SILENCE_RMS


def window_is_digital_silence(chunk, peak_floor=None, rms_floor=None):
    """True only when a window is DIGITAL SILENCE under the imported floors.

    PURE and cheap: two reductions of the window, no copy, no allocation beyond
    the RMS reduction, no device and no model. MEASURED on 3 s of 16 kHz PCM
    (`_main/batch-silence-gate-oracle.py` arm A11): 0.0198 ms per window, i.e.
    ~0.2 ms for the ten windows of the `REDUX_BATCH_PASS_MAX_S` cap -- against a
    measured 2.40 s of wall per decoded window.

    The peak is computed as `max(max(x), -min(x))` on purpose: `np.abs(x).max()`
    would allocate a second copy of the window on every call, and this runs for
    every window of every pass.
    """
    import numpy as np

    peak_floor = (DIGITAL_SILENCE_PEAK if peak_floor is None
                  else float(peak_floor))
    rms_floor = (DIGITAL_SILENCE_RMS if rms_floor is None else float(rms_floor))
    if chunk is None or int(getattr(chunk, "size", 0)) == 0:
        # An empty window carries nothing to skip: the decision belongs to the
        # engine, which returns "" for it -- this is not the silence path.
        return False
    hi = float(np.max(chunk))
    lo = float(np.min(chunk))
    peak = hi if hi >= -lo else -lo
    if peak >= peak_floor:
        # The cheap test already proved this window is not digital silence.
        return False
    rms = float(np.sqrt(np.mean(np.square(chunk, dtype=np.float64))))
    return rms < rms_floor
