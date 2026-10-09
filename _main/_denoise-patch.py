# -*- coding: utf-8 -*-
"""Split this lane's change out of worker/sotto_worker.py, reversibly, on BYTES.

WHAT THIS PROVES. The claim to defend is "with `use_denoise: false` the worker
behaves exactly as it does today". The control for that is a worker WITHOUT this
lane's code, so this script produces one by removing exactly the four insertions
this lane made and then proves the removal is EXACT by round-tripping at the
byte level:

    crlf(insert_blocks(strip_blocks(raw)))  ==  raw

If that identity holds, the two files differ by this lane's change and NOTHING
else -- the measurement is an isolation, not a guess.

TWO TRAPS THIS SCRIPT EXISTS TO DODGE, both hit once while writing it:

 1. LINE ENDINGS. The worker is CRLF (measured: 246517 B, 4673 CRLF, 0 bare LF,
    0 lone CR). `open(path, encoding="utf-8").read()` in TEXT mode applies
    universal newlines and strips all 4673 `\\r`, so the same unchanged file read 241844 B from Python and
    246517 B from PowerShell -- and that stripped text was then compared against
    the recorded pre-edit hash, which made it look exactly like a sibling lane
    was rewriting the file under this lane, oscillating between two revisions a
    minute apart. It was not: 246517 - 4673 = 241844 is the whole discrepancy.
    This script reads and writes BYTES and converts explicitly, so the round trip
    is checked on the real thing.

 2. DECORATIVE LINES. The inserted comments end in long runs of box-drawing
    characters, and the 4-space header of block 3 is a SUBSTRING of the 8-space
    header of block 2. Retyping a run one character short, or anchoring on an
    indented line that occurs twice, makes an exact-text match fail for a reason
    that has nothing to do with the code -- and the failure reads as "the file is
    not what you think". The blocks are therefore SLICED between short anchors
    (block 3 positionally, from the unique line it follows), never retyped.

WHY NOT `git show HEAD:...`. HEAD is STALE here: 232291 B / sha256 589EB4B5...,
while the file on disk is 246517 B -- other lanes have uncommitted work in the
same file, so reverting to HEAD would discard their work. The control is derived
from the CURRENT bytes, and it reproduces the pre-edit revision EXACTLY:
242082 B / sha256 64E7EC6F... , which is the strongest form this isolation can
take. Both hashes travel in the receipt.

USAGE
    py -3 _main/_denoise-patch.py --verify
    py -3 _main/_denoise-patch.py --off-out _main/denoise-frozen/off/sotto_worker.py
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
LIVE = os.path.join(REPO, "worker", "sotto_worker.py")

PRE_EDIT_SHA256 = "64E7EC6F6C35C33600E9D50C11AC7D8CE96FBE1FEF87C24CD628BDF03F314E61"
PRE_EDIT_BYTES = 242082

# Short anchors. Each must occur exactly ONCE in the LF-normalised text.
A1_START = "        # The noise remover (lane SottoDenoise), OFF by default"
A1_END = "        self.denoiser = None\n"

A2_START = "        # \u2500\u2500 the noise remover (lane SottoDenoise) \u2500\u2500"
A2_END = "            pcm_chunk = self.denoiser.process(pcm_chunk)\n\n"
A2_AFTER = "        feats = self.sp.process(pcm_chunk)\n"  # block 2 sits right before this

A3_START = "    # \u2500\u2500 the noise remover (lane SottoDenoise) \u2500\u2500"
A3_END = "        **_denoise_fields,\n    )\n\n"
A3_AFTER = "        hold_chunks=GATE_HOLD_CHUNKS,\n    )\n\n"  # block 3 sits right after this

HELPER_HEAD = "def _denoise_gate_from_config(cfg, sr):"
HELPER_NEXT = "class StreamAsr:"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def slice_block(text, start_anchor, end_anchor, label):
    """Return (block, problems). Block runs from start_anchor to the end of end_anchor."""
    if text.count(start_anchor) != 1:
        return None, ["%s: start anchor matched %d times, expected 1"
                      % (label, text.count(start_anchor))]
    if text.count(end_anchor) != 1:
        return None, ["%s: end anchor matched %d times, expected 1"
                      % (label, text.count(end_anchor))]
    s = text.index(start_anchor)
    e = text.index(end_anchor, s) + len(end_anchor)
    return text[s:e], []


def extract(raw_lf):
    """(blocks, helper, problems). Blocks in file order: 1 field, 2 call site, 3 emit."""
    problems = []
    b1, p = slice_block(raw_lf, A1_START, A1_END, "block1(field)")
    problems += p
    b2, p = slice_block(raw_lf, A2_START, A2_END, "block2(call site)")
    problems += p
    # Block 3 is located POSITIONALLY, right after A3_AFTER: its own header line is
    # indented 4 spaces, and the 8-space header of block 2 contains that substring,
    # so an indented anchor matches twice and would refuse for the wrong reason.
    if raw_lf.count(A3_AFTER) != 1:
        problems.append("block3: A3_AFTER matched %d times" % raw_lf.count(A3_AFTER))
        b3 = None
    elif raw_lf.count(A3_END) != 1:
        problems.append("block3: end anchor matched %d times" % raw_lf.count(A3_END))
        b3 = None
    else:
        s3 = raw_lf.index(A3_AFTER) + len(A3_AFTER)
        e3 = raw_lf.index(A3_END, s3) + len(A3_END)
        b3 = raw_lf[s3:e3]
        if not b3.startswith(A3_START):
            problems.append("block3: does not start with its own header")
        if A3_START not in b3:
            problems.append("block3: header missing")
    if raw_lf.count(HELPER_HEAD) != 1:
        problems.append("helper: head matched %d times" % raw_lf.count(HELPER_HEAD))
    if raw_lf.count(HELPER_NEXT) != 1:
        problems.append("helper: %r matched %d times" % (HELPER_NEXT, raw_lf.count(HELPER_NEXT)))
    if problems:
        return None, None, problems
    hs = raw_lf.index(HELPER_HEAD)
    he = raw_lf.index(HELPER_NEXT, hs)
    return (b1, b2, b3), raw_lf[hs:he], []


def strip_blocks(raw_lf, blocks, helper):
    b1, b2, b3 = blocks
    out = raw_lf.replace(b1, "", 1)
    out = out.replace(b2, "", 1)
    out = out.replace(b3, "", 1)
    out = out.replace(helper, "", 1)
    return out


def insert_blocks(off_lf, blocks, helper):
    b1, b2, b3 = blocks
    out = off_lf
    at = out.index(HELPER_NEXT)
    out = out[:at] + helper + out[at:]
    out = out.replace(A3_AFTER, A3_AFTER + b3, 1)
    out = out.replace(A2_AFTER, b2 + A2_AFTER, 1)
    out = out.replace("        self.gate = None\n        self.music_gated_chunks = 0\n",
                      "        self.gate = None\n        self.music_gated_chunks = 0\n" + b1, 1)
    return out


def main(argv):
    mode = argv[1] if len(argv) > 1 else "--verify"
    raw = open(LIVE, "rb").read()
    crlf = raw.count(b"\r\n")
    bare_lf = raw.count(b"\n") - crlf
    lone_cr = raw.count(b"\r") - crlf
    print("live     %d B  %d CRLF  %d bare-LF  %d lone-CR  sha256 %s"
          % (len(raw), crlf, bare_lf, lone_cr, sha(raw)))
    if bare_lf or lone_cr:
        print("PATCH-REFUSED: mixed line endings; the byte round trip would not be exact")
        return 1

    raw_lf = raw.replace(b"\r\n", b"\n")
    print("live(LF) %d B  sha256 %s" % (len(raw_lf), sha(raw_lf)))
    print("pre-edit (recorded before this lane's edit): %d B  sha256 %s"
          % (PRE_EDIT_BYTES, PRE_EDIT_SHA256))

    blocks, helper, problems = extract(raw_lf.decode("utf-8"))
    if problems:
        print("PATCH-REFUSED: this file is not 'OFF + this lane's four insertions':")
        for p in problems:
            print("  - %s" % p)
        print("VERDICT FAIL -- re-apply this lane's edit before measuring")
        return 1
    for name, b in zip(("block1(field)", "block2(call site)", "block3(emit)"), blocks):
        print("  %-18s %d B" % (name, len(b.encode("utf-8"))))
    print("  %-18s %d B" % ("helper", len(helper.encode("utf-8"))))

    off_lf = strip_blocks(raw_lf.decode("utf-8"), blocks, helper)

    # ── the gate: byte-level round trip ─────────────────────────────────────
    back_lf = insert_blocks(off_lf, blocks, helper)
    back = back_lf.encode("utf-8").replace(b"\n", b"\r\n")
    rt = back == raw
    print("round-trip  crlf(off + four blocks) == live : %s  (sha %s)" % (rt, sha(back)))
    if not rt:
        print("VERDICT FAIL -- the OFF file is not the live file minus this lane's change")
        return 1

    leftovers = sorted({w for w in ("denoise", "denoiser", "_denoise", "SpectralGate")
                        if w in off_lf})
    print("off mentions this lane at all : %s" % (leftovers or "no"))
    if leftovers:
        print("VERDICT FAIL -- the OFF file still carries this lane's names")
        return 1
    for word in ("class StreamAsr", "def main", "def run_chunk", "def selftest", "def rerun"):
        if word not in off_lf:
            print("VERDICT FAIL -- OFF file lost %r" % word)
            return 1
    if "use_denoise" in off_lf:
        print("VERDICT FAIL -- OFF file mentions the config key")
        return 1

    off_bytes = off_lf.encode("utf-8").replace(b"\n", b"\r\n")
    print("off      %d B  %d CRLF  sha256 %s" % (len(off_bytes), off_bytes.count(b"\r\n"), sha(off_bytes)))
    # Diagnostic, not the gate: the gate is the round trip above. This says the
    # reconstruction landed on the exact revision recorded before the edit, i.e.
    # nothing else in the file has moved since -- worth printing either way.
    print("off == revision recorded immediately before this lane's edit : %s"
          % (len(off_bytes) == PRE_EDIT_BYTES and sha(off_bytes).upper() == PRE_EDIT_SHA256))

    if mode == "--verify":
        print("VERDICT PASS -- live == OFF + exactly this lane's four insertions, byte for byte")
        return 0
    if mode != "--off-out" or len(argv) < 3:
        print("unknown mode %r (use --verify or --off-out PATH)" % mode)
        return 2
    out_path = argv[2]
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(off_bytes)
    print("wrote    %s" % out_path)
    print("VERDICT PASS -- OFF arm is the live revision minus this lane's four insertions")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
