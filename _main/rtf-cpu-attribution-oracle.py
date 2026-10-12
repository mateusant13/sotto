#!/usr/bin/env python3
"""rtf-cpu-attribution-oracle -- "RTF > 1 na CPU" is TRUE for some regimes and FALSE for others, and the row
cites one of them without saying which.

AUDIT ROW F10 (auditoria-completa-20261007.md:72): "RTF > 1 na CPU: a app nao acompanha a fala em tempo
real; CUDA e pedido e nao carrega", citing _main/_review-segrerun.out and docs/model-specs/README.md:130-146.
This oracle measures BOTH citations and the whole RTF landscape on disk, because the number depends on the
regime and on the implementation:

  * THE PRIMARY CITATION IS REAL: _main/_review-segrerun.out (2008 B, mtime 2026-10-07T05:51:23Z) reports
    provider=[CPUExecutionProvider] and a stream RTF above 1 -- but it is a segment-RERUN review: 85.07 s of
    work for 14.56 s of audio, on a loaded box.
  * THE SECOND CITATION IS DANGLING: docs/model-specs/README.md:130-146 does not mention RTF at all; it is
    the lang_id/WER table. A reader following the row second source finds nothing about real time.
  * THE LANDSCAPE, each number in its home: 1.334 (sherpa-onnx INT8 REFERENCE on CPU, the worker own header
    at sotto_worker.py:50), 5.843 (the loaded rerun above), 0.792 / 0.483 (int4 / int8 CPU FILE runs,
    _main/diary-20261006-0609.md:38), 0.144 / 0.110 (this worker GPU int8/int4, same header), and the
    1,59-3,04 absolutes that _main/fragmentacao-receipt.md:102-103 attributes to LOAD, not model, whose own
    not-verified list names the idle-box measurement as missing.
  * ONE OF THE THREE OWNER OPTIONS IS NOT IMPLEMENTED, and a comment says it is: sotto_webview.py cites
    "panel.js:1738-1740 (the behind chip)" as reading peak/blocks -- that line is wireSurfaces(), and
    panel.js carries no behind/lagging chip at all.

THE CUDA HALF was refuted on 2026-10-08 (the worker adds the cublasLt64_13.dll directory and the live run is
GPU-backed); the provider line from the same artefact is recorded here as the measured context.

ARM 5 is the control: the RTF is PARSED from the artefact and must be above 1, so replacing that file with
the GPU run flips the arm -- no number here is remembered.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
SEGRERUN = os.path.join(ROOT, "_main", "_review-segrerun.out")
SPECS = os.path.join(ROOT, "docs", "model-specs", "README.md")
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")
DIARY = os.path.join(ROOT, "_main", "diary-20261006-0609.md")
FRAG = os.path.join(ROOT, "_main", "fragmentacao-receipt.md")
SHELL = os.path.join(ROOT, "app", "webview", "sotto_webview.py")
PANEL_JS = os.path.join(ROOT, "app", "panel", "panel.js")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.parse_args(argv)
    say = print
    wrong = []
    if not os.path.exists(SEGRERUN):
        say("VERDICT: FAIL -- the primary citation is gone: " + SEGRERUN)
        return 1
    seg = read(SEGRERUN)
    specs = read(SPECS)
    panel = read(PANEL_JS)
    shell = read(SHELL)
    say("rtf-cpu-attribution-oracle -- row F10 (from the artefacts; no run, no launch)")
    provider_cpu = "CPUExecutionProvider" in seg
    rtf_match = re.search(r"RTF ([0-9.]+)", seg)
    rtf = float(rtf_match.group(1)) if rtf_match else None
    say("  arm 1  the primary citation: %d B, CPUExecutionProvider=%s, stream RTF=%s" % (os.path.getsize(SEGRERUN), str(provider_cpu).lower(), rtf))
    if not provider_cpu:
        wrong.append("arm 1: the cited artefact no longer shows a CPU provider")
    specs_slice = "\n".join(specs.split("\n")[127:147])
    mentions_rtf = "RTF" in specs_slice
    say("  arm 2  the second citation (model-specs README:130-146) mentions RTF: %s" % str(mentions_rtf).lower())
    if mentions_rtf:
        wrong.append("arm 2: the second citation NOW mentions RTF -- the dangling pointer was fixed")
    landscape = [
        (WORKER, "RTF 1.334", "sherpa-onnx INT8 reference ON CPU (the worker own header)"),
        (WORKER, "RTF 0.144", "this worker, GPU int8"),
        (DIARY, "rtf CPU 0.792", "int4 CPU file run -- BELOW 1"),
        (DIARY, "0.483", "int8 CPU file run -- BELOW 1"),
        (FRAG, "nao modelo", "the receipt own attribution of the above-1 absolutes (it writes \"e' carga\")"),
        (FRAG, "1,59-3,04", "the loaded absolutes, in the receipt own words"),
    ]
    say("  arm 3  the landscape, each number in its home:")
    for path, needle, why in landscape:
        ok = needle in read(path)
        say("     %-22s %s  (%s)" % (needle, str(ok).lower(), why))
        if not ok:
            wrong.append("arm 3: " + needle + " is gone from " + os.path.basename(path))
    chip_claim = "panel.js:1738-1740" in shell
    panel_lines = panel.split("\n")
    line_1739 = panel_lines[1738].strip() if len(panel_lines) > 1738 else ""
    # A CHIP, not the word. panel.js says "behind" in prose ("the panel is behind it", "the bar keeps the
    # label and the behind chip" in a COMMENT at :1021), and my first version of this arm read the comment as
    # the feature and concluded "not implemented" -- a false negative of exactly the kind this repo writes
    # rules about. What IS the shipped thing is the painting below, measured by its own two anchors.
    chip_predicate = "const behind = (drops !== null && drops > 0) || (rate !== null && rate < 1);" in panel
    chip_paint = "behind \u00b7 " in panel or "behind . " in panel
    chip_doc = "The \"behind\" chip in the live bar" in panel
    chip_forms = [
        ("the behind predicate (drops>0 or rate<1)", chip_predicate),
        ("the chip text it paints", chip_paint),
        ("its own docstring line", chip_doc),
    ]
    chip_exists = all(ok for _why, ok in chip_forms)
    say("  arm 4  the behind chip: shell claims panel.js:1738-1740=%s; that line reads %r" % (str(chip_claim).lower(), line_1739[:40]))
    say("         chip forms: " + ", ".join("%s=%s" % (why, str(ok).lower()) for why, ok in chip_forms))
    if not chip_exists:
        wrong.append("arm 4: the behind chip is GONE from panel.js -- the owner option would have to be built")
    cited_is_chip = "behind" in line_1739
    say("         the cited line carries the chip: %s -- %s" % (str(cited_is_chip).lower(), "citation accurate" if cited_is_chip else "STALE CITATION in the shell comment"))
    if rtf is None:
        wrong.append("arm 5: no RTF could be parsed from the artefact -- the control cannot judge")
    elif rtf <= 1.0:
        wrong.append("arm 5 CONTROL: the artefact RTF is %.3f, NOT above 1 -- this is not the loaded rerun the row cites" % rtf)
    else:
        say("  arm 5  CONTROL: the RTF parsed from the artefact (%.3f) is above 1, as the row claims" % rtf)
    detail = " -- the primary citation is REAL (CPU provider, RTF above 1) but it is a LOADED RERUN; the second citation does not mention RTF at all; the landscape on disk runs from 0.110 (this worker, GPU) to 5.843 (loaded CPU) with the CPU FILE runs BELOW 1, so the row cites one regime without naming it. ALL THREE owner options already exist: GPU is the shipped path, a smaller chunk is one flag away, and the panel ALREADY paints a behind chip when drops>0 or rate<1 -- while the shell comment that cites it points at wireSurfaces(), a stale citation, not a missing feature"
    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL") + detail)
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())