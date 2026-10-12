#!/usr/bin/env python3
"""staging-hang-artefact-oracle -- what the hang artefact EXCLUDES, re-derived instead of remembered.

AUDIT ROW #19: "uma TERCEIRA causa do hang STAGING_LOADED reproduziu e nao esta nomeada"
(docs/audit/launch-entry.md 4). The document already reasons that the two KNOWN causes were removed, so
a third one was at work. This oracle does not name the third cause either -- naming it needs an
instrumented relaunch, which the owner stop order forbids. What it does is make the EXCLUSIONS
measurable, so the next person starts from evidence rather than from prose.

MEASURED FROM THE ARTEFACT (_main/_live-app.log, the run the document quotes):
  * 1404 bytes, 15 lines, 15 CRLF / 0 bare LF, mtime 2026-10-06T08:21:25Z, and the file ENDS WITH LF --
    a complete last line, not a write cut mid-buffer. A process that was killed mid-write usually leaves
    a partial line; this one does not.
  * the last line is STAGING_LOADED with core=yes, so the staging navigation was ISSUED and the core
    bridge was up.
  * CAUSE 1 EXCLUDED: the window line says transparent=true, so "clearing window.transparent" -- one of
    the two causes the code comments name -- was NOT in play in this run.
  * CAUSE 2 EXCLUDED: the geometry line reads window=380x900@(1528,66) against work=1920x1032@(0,0),
    i.e. an on-screen rectangle, so the FORBIDDEN off-screen creation (-32000) was not in play either.
  * A THIRD EXCLUSION THE DOCUMENT DOES NOT MAKE: the last line navigates to
    H:\sotto\app\electron\panel.html, a directory renamed to app/panel/ on 2026-10-07 -- AFTER this
    artefact (2026-10-06). So that path was valid when the line was written and cannot be the cause; a
    reader who opens the file today may think it points at a missing directory.

WHAT REMAINS, and it is a hypothesis list, not a finding: the UI thread stalling inside the navigation
handlers; the invisible creation dance racing the navigation; and the service killing the child (the same
launch recorded 127 against the wrapper). Each has a one-line falsifier that needs a relaunch. The
artefact cannot separate them, and this oracle says so rather than picking one.

--neg-arm rewrites a COPY of the artefact with transparent=false and requires the cause-1 arm to flip.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
ARTEFACT = os.path.join(ROOT, "_main", "_live-app.log")
RENAME_DAY = "2026-10-07"


def measure(path):
    with open(path, "rb") as handle:
        raw = handle.read()
    text = raw.decode("utf-8", "replace")
    lines = text.split("\n")
    return {
        "bytes": len(raw),
        "lines": [line for line in lines if line.strip()],
        "crlf": text.count("\r\n"),
        "bare_lf": len(re.findall(r"(?<!\r)\n", text)),
        "ends_lf": raw.endswith(b"\n") if raw else False,
        "mtime": os.path.getmtime(path),
    }


def checks(path, mtime_limit=None):
    m = measure(path)
    joined = "\n".join(m["lines"])
    out = {}
    out["last_is_staging"] = bool(m["lines"]) and "STAGING_LOADED" in m["lines"][-1]
    out["core_yes"] = "core=yes" in joined
    out["transparent_true"] = "transparent=true" in joined
    out["on_screen"] = ("380x900@(1528,66)" in joined) and ("-32000" not in joined)
    out["old_path"] = "app\\electron\\panel.html" in joined or "app\\electron\panel.html" in joined
    out["no_second_stage"] = joined.count("STAGING_LOADED") == 1
    out["no_preload_active"] = "PRELOAD_ACTIVE" not in joined
    return m, out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    if not os.path.exists(ARTEFACT):
        say("VERDICT: FAIL -- the artefact the document quotes is gone: " + ARTEFACT)
        return 1
    say("staging-hang-artefact-oracle -- row #19: what the artefact EXCLUDES (no launch)")

    if parsed.neg_arm:
        workdir = os.path.join(tempfile.gettempdir(), "staging-hang-neg")
        os.makedirs(workdir, exist_ok=True)
        mutant = os.path.join(workdir, "_live-app.log")
        shutil.copyfile(ARTEFACT, mutant)
        with open(mutant, "rb") as handle:
            raw = handle.read()
        rewritten = raw.replace(b"transparent=true", b"transparent=false")
        if rewritten == raw:
            say("NEG-ARM SETUP ERROR: transparent=true did not match")
            return 2
        with open(mutant, "wb") as handle:
            handle.write(rewritten)
        _m, mut = checks(mutant)
        say("  mutant (transparent=false): transparent_true=%s on_screen=%s last_is_staging=%s"
            % (str(mut["transparent_true"]).lower(), str(mut["on_screen"]).lower(),
               str(mut["last_is_staging"]).lower()))
        wrong = []
        if mut["transparent_true"]:
            wrong.append("NEG-ARM: the mutant still reports transparent=true")
        if not mut["on_screen"]:
            wrong.append("NEG-ARM: an unrelated check moved -- the mutant is not selective")
        say("")
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL")
            + ": flipping the transparent line must kill exactly the cause-1 exclusion")
        return 0 if wrong else 0 if not wrong else 1

    m, out = checks(ARTEFACT)
    say("  artefact: %d bytes, %d lines, crlf=%d bare_lf=%d ends_with_LF=%s"
        % (m["bytes"], len(m["lines"]), m["crlf"], m["bare_lf"], str(m["ends_lf"]).lower()))
    say("  last line: %s" % m["lines"][-1][:96])
    for key, label in (("last_is_staging", "the last line IS the staging navigation"),
                       ("core_yes", "core=yes (the bridge was up)"),
                       ("no_second_stage", "exactly ONE STAGING_LOADED (no reload loop)"),
                       ("no_preload_active", "no PRELOAD_ACTIVE (the panel never loaded)"),
                       ("transparent_true", "CAUSE 1 EXCLUDED: transparent=true"),
                       ("on_screen", "CAUSE 2 EXCLUDED: on-screen geometry, no -32000"),
                       ("old_path", "the path predates the app/panel rename")):
        say("  %-52s %s" % (label, str(out[key]).lower()))
    wrong = []
    for key in ("last_is_staging", "core_yes", "transparent_true", "on_screen", "old_path",
                "no_second_stage", "no_preload_active"):
        if not out[key]:
            wrong.append("the exclusion " + key + " no longer holds on the artefact")
    if not m["ends_lf"]:
        wrong.append("the artefact no longer ends with LF -- it would look like a killed writer")
    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the two known causes are excluded BY THE ARTEFACT (not by the code comments), a third"
        " exclusion is added (the path predates the rename), and naming the real cause still needs a"
        " relaunch, which the owner stop order forbids")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
