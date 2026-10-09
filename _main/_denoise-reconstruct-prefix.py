# -*- coding: utf-8 -*-
"""Recover the PRE-CHANGE bytes of worker/sotto_worker.py, and PROVE it by hash.

WHY this exists instead of `git show HEAD:...`: HEAD is STALE here. The repo
carries uncommitted work from other lanes, so `git show HEAD:worker/sotto_worker.py`
returned 232291 B / sha256 589EB4B5..., NOT the 242082 B / 64E7EC6F... revision
that was on disk immediately before this lane's edit. Reverting to HEAD would
have thrown away other people's work.

So the pre-change file is RECONSTRUCTED by reverse-applying exactly the four
insertions this lane made, and the reconstruction is then checked against the
hash recorded BEFORE the edit:

    64E7EC6F6C35C33600E9D50C11AC7D8CE96FBE1FEF87C24CD628BDF03F314E61

If that matches, the recovered file is byte-for-byte the original -- the hash is
the proof, and it is a stronger one than a git blob would have been. If it does
NOT match, this lane's byte-identity arm is INVALID and the script says so
instead of writing a file that would silently stand in for the original.
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LIVE = os.path.join(REPO, "worker", "sotto_worker.py")
OUT = os.path.join(HERE, "denoise-prefix", "sotto_worker.py")

# The hash measured on the live file IMMEDIATELY before the first edit.
PREFIX_SHA256 = "64E7EC6F6C35C33600E9D50C11AC7D8CE96FBE1FEF87C24CD628BDF03F314E61"

# The four insertions, verbatim. Each is removed once.
BLOCKS = [
    # 1. StreamAsr.__init__: the denoiser field, after `self.gate = None`.
    """        # The noise remover (lane SottoDenoise), OFF by default and set by main()
        # from the top-level `use_denoise` key. It is a `denoise.SpectralGate` or
        # None, and None leaves this file byte-identical to its pre-denoise
        # behaviour \u2014 the key is additive and defaults to false.
        self.denoiser = None
""",
    # 2. run_chunk: the ONE call site, immediately before the mel window.
    """        # \u2500\u2500 the noise remover (lane SottoDenoise) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
        # ONE call site, and it is HERE on purpose. Everything upstream of it
        # decided on the ORIGINAL audio: the speech/music gate above ran on the
        # chunk as captured (so its dB-range/RMS features are untouched by this
        # and `music_gated_chunks` cannot move), and the caller's AGC ran on the
        # original too. Everything downstream sees the CLEANED audio: the
        # cache-aware mel window (`self.sp`, and with it the Silero VAD inside
        # it \u2014 so `vad_gated_chunks` CAN legitimately move) and the encoder.
        # Placing it at the live call site instead would have fed the gate
        # denoised audio and changed the very features the gate decides on.
        # `self.denoiser` is None unless main() read `use_denoise: true`, so
        # without that key this function is byte-identical to its pre-denoise
        # behaviour \u2014 same argument as the gate's `self.gate is None` above.
        if self.denoiser is not None:
            pcm_chunk = self.denoiser.process(pcm_chunk)

""",
    # 3. main(): the construction + the one status emit, after the gate emit.
    """    # \u2500\u2500 the noise remover (lane SottoDenoise) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
    # Additive, OFF by default, and read from the SAME config.json the rest of
    # this function reads. `denoise_from_config` never raises: a key that is
    # absent, false, or nonsense all land here as a reason string, and only the
    # literal true builds a gate. It is installed on the `asr` object rather
    # than passed to StreamAsr's constructor so the constructor's signature \u2014 and
    # every existing caller of it \u2014 is untouched, and so the FILE arm gets it
    # too: `selftest()` is handed this same `asr` further down.
    asr.denoiser, _denoise_on, _denoise_reason = _denoise_gate_from_config(cfg, TARGET_SR)
    _denoise_fields = {}
    if asr.denoiser is not None:
        _denoise_stats = asr.denoiser.stats()
        _denoise_fields = {
            "frame": _denoise_stats["frame"],
            "hop": _denoise_stats["hop"],
            "latency_ms": _denoise_stats["latency_ms"],
            "min_gain_db": _denoise_stats["min_gain_db"],
            "noise_bias": _denoise_stats["noise_bias"],
        }
    emit(
        type="status",
        state="denoise",
        denoise="on" if _denoise_on else "off",
        reason=_denoise_reason,
        config_key="use_denoise",
        **_denoise_fields,
    )

""",
]

# 4. the module-level helper, between `_lang_prompt` and `class StreamAsr`.
HELPER_HEAD = "def _denoise_gate_from_config(cfg, sr):"
HELPER_TAIL = "    return denoise.denoise_from_config(cfg, sr=sr)\n"


def main():
    src = open(LIVE, encoding="utf-8").read()
    live_sha = hashlib.sha256(src.encode("utf-8")).hexdigest()
    print("live   %s  %d B  sha256 %s" % (os.path.basename(LIVE), len(src.encode("utf-8")), live_sha))

    out = src
    for i, block in enumerate(BLOCKS, 1):
        n = out.count(block)
        print("  block %d: %d occurrence(s)" % (i, n))
        if n != 1:
            print("RECONSTRUCT-REFUSED: block %d matched %d times, not 1" % (i, n))
            return 2
        out = out.replace(block, "", 1)

    # The helper: cut from its `def` line to its final `return`, inclusive.
    if out.count(HELPER_HEAD) != 1:
        print("RECONSTRUCT-REFUSED: helper head matched %d times" % out.count(HELPER_HEAD))
        return 2
    start = out.index(HELPER_HEAD)
    # Walk back over the two blank lines that separate it from `_lang_prompt`.
    while start > 0 and out[start - 1] == "\n":
        start -= 1
    tail = out.index(HELPER_TAIL, start) + len(HELPER_TAIL)
    out = out[: start + 1] + out[tail:]

    data = out.encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()
    print("prefix %d B  sha256 %s" % (len(data), sha))
    print("expect %d B  sha256 %s" % (len(PREFIX_SHA256) and 242082, PREFIX_SHA256))
    if sha != PREFIX_SHA256:
        print("RECONSTRUCT-MISMATCH: the recovered bytes are NOT the pre-change revision.")
        print("  This lane's byte-identity arm is INVALID. Do not write the file.")
        return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "wb") as fh:
        fh.write(data)
    print("RECONSTRUCT-OK  wrote %s" % OUT)
    print("VERDICT PASS -- recovered bytes hash to the revision measured before the edit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
