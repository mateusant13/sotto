#!/usr/bin/env python3
"""webview-shell-field-count-oracle -- the "14 fields" IS reproducible; it is a GRANULARITY, not a mystery.

AUDIT ROW F9 (shell): "14 campos, 0 divergencias do webview-shell nao e reproduzivel"
(docs/audit/doc-vs-code.md section 9, inherited from row #52). The audit reproduced the SUBSTANTIVE claim
(the two shells render identically) but reported "fields compared: 64 MISMATCHES: 0" for the method the
source document names, and concluded that the "14" the document quotes "does not fall out of the method"
and is unexplained.

IT FALLS OUT OF THE METHOD, AND THIS ORACLE SHOWS THE ARITHMETIC FROM THE TWO LOGS THEMSELVES, which are
still on disk (_main/electron-dump-fresh.log, _main/webview-dump.stdout.txt, one DOMDUMP JSON line each):

    4 page-level fields (body, sheets, viewport, zoom)
  + 10 elements, each with 6 display properties (color, display, opacity, position, rect, visibility)

  COARSE (one field per ELEMENT) = 4 + 10   = 14   <- exactly what the document quotes
  FINE   (one field per PROPERTY) = 4 + 10*6 = 64   <- exactly what the audit measured

Both numbers are right and both are measured; they differ only in whether an element counts as one field
or as its six properties. The row premise ("not reproducible") is therefore REFUTED, and the row is closed
with the count RE-DERIVED rather than remembered.

ARMS: the two shells parse to the same four page-level fields and the same ten element keys; 0 mismatches
across all 64 fine-grained comparisons (that is the substantive claim, re-measured here); the coarse count
equals the number in the source document; the fine count equals the number in the audit; and both quote
sites still carry their number, so an edit to either goes RED.

--neg-arm rewrites a COPY of the electron dump with one element opacity changed and requires the mismatch
arm to flip while the counts stay put (a selective mutant). The real dumps are never modified.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
ELECTRON = os.path.join(ROOT, "_main", "electron-dump-fresh.log")
WEBVIEW = os.path.join(ROOT, "_main", "webview-dump.stdout.txt")
SOURCE_DOC = os.path.join(ROOT, "docs", "webview-shell-20261006.md")
AUDIT_DOC = os.path.join(ROOT, "docs", "audit", "doc-vs-code.md")
AGENTS = os.path.join(ROOT, "AGENTS.md")


def load(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if "DOMDUMP" in line:
                return json.loads(line.split("DOMDUMP", 1)[1].strip())
    raise SystemExit("no DOMDUMP line in " + path)


def compare(electron, webview):
    out = {"mismatches": 0, "pairs": 0}
    e_els = electron.get("els") or {}
    w_els = webview.get("els") or {}
    page = [k for k in electron if k != "els"]
    out["page_fields"] = sorted(page)
    out["els"] = len(e_els)
    out["same_element_keys"] = sorted(e_els) == sorted(w_els)
    props = sorted(e_els[sorted(e_els)[0]].keys()) if e_els else []
    out["props"] = props
    for key in page:
        out["pairs"] += 1
        if electron.get(key) != webview.get(key):
            out["mismatches"] += 1
    for key in sorted(set(e_els) | set(w_els)):
        left = e_els.get(key) or {}
        right = w_els.get(key) or {}
        out["pairs"] += 1
        if left != right:
            out["mismatches"] += 1
    out["coarse"] = len(page) + len(e_els)
    out["fine"] = len(page) + len(e_els) * len(props)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    wrong = []
    electron_path = ELECTRON
    mutant = None
    if parsed.neg_arm:
        workdir = os.path.join(tempfile.gettempdir(), "f9-neg")
        os.makedirs(workdir, exist_ok=True)
        mutant = os.path.join(workdir, "electron-dump-fresh.log")
        shutil.copyfile(ELECTRON, mutant)
        with open(mutant, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        changed = re.sub(r'("opacity":"[0-9.]+")', '"opacity":"0.424242"', text, count=1)
        if changed == text:
            say("NEG-ARM SETUP ERROR: no opacity field matched")
            return 2
        with open(mutant, "w", encoding="utf-8", newline="") as handle:
            handle.write(changed)
        electron_path = mutant
    electron = load(electron_path)
    webview = load(WEBVIEW)
    info = compare(electron, webview)
    say("webview-shell-field-count-oracle -- row F9 (shell): the granularity behind the number")
    say("  page-level fields : %d %s" % (len(info["page_fields"]), info["page_fields"]))
    say("  elements          : %d  same keys in both shells: %s"
        % (info["els"], str(info["same_element_keys"]).lower()))
    say("  per-element props : %d %s" % (len(info["props"]), info["props"]))
    say("  compared pairs    : %d   mismatches: %d" % (info["pairs"], info["mismatches"]))
    say("  COARSE 4 + els        = %d   (the source document quotes 14)" % info["coarse"])
    say("  FINE   4 + els*props  = %d   (the audit measured 64)" % info["fine"])
    if parsed.neg_arm:
        say("")
        say("  mutant: one element opacity changed -> mismatches=%d, counts unchanged: %s"
            % (info["mismatches"], str((info["coarse"], info["fine"]) == (14, 64)).lower()))
        if info["mismatches"] == 0:
            wrong.append("NEG-ARM: a changed element was NOT counted as a mismatch -- the comparison arm"
                         " measures nothing")
        if (info["coarse"], info["fine"]) != (14, 64):
            wrong.append("NEG-ARM: the mutant moved the COUNTS too -- it is not selective")
        say("")
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL")
            + ": a single changed field must show as a mismatch and must not move the field counts")
        return 0 if not wrong else 1

    with open(SOURCE_DOC, encoding="utf-8") as handle:
        source_doc = handle.read()
    with open(AUDIT_DOC, encoding="utf-8") as handle:
        audit_doc = handle.read()
    with open(AGENTS, encoding="utf-8", errors="replace") as handle:
        agents = handle.read()
    quotes_14 = re.search(r"14 fields, 0 mismatches", source_doc) is not None
    quote_line = re.search(r"fields compared: 14 \| MISMATCHES: 0", source_doc) is not None
    audit_64 = re.search(r"fields compared: 64 MISMATCHES: 0", audit_doc) is not None
    # AGENTS.md WRAPS this line ("...compared,\n0 mismatches)"), so the pattern must tolerate the wrap
    agents_14 = re.search(r"14 DOM fields compared,\s*0 mismatches", agents) is not None
    say("  quote sites: doc \"14 fields, 0 mismatches\"=%s, doc tool line \"14\"=%s, audit \"64\"=%s,"
        " AGENTS.md phrase=%s"
        % (str(quotes_14).lower(), str(quote_line).lower(), str(audit_64).lower(),
           str(agents_14).lower()))
    if info["mismatches"] != 0:
        wrong.append("the two shells now DIFFER in %d field(s) -- the substantive claim would be dead"
                     % info["mismatches"])
    if not info["same_element_keys"]:
        wrong.append("the two shells no longer carry the same element keys")
    if info["coarse"] != 14:
        wrong.append("the coarse count is %d, not the 14 the document quotes" % info["coarse"])
    if info["fine"] != 64:
        wrong.append("the fine count is %d, not the 64 the audit measured" % info["fine"])
    if not (quotes_14 and quote_line and audit_64):
        wrong.append("one of the quote sites no longer carries its number")
    say("")
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- the 14 is REPRODUCIBLE: it counts one field per ELEMENT (4 page-level + 10 elements) while"
        " the audit counted each element six display properties (4 + 60 = 64). Same logs, same method,"
        " two granularities, 0 mismatches either way; the row premise \"not reproducible\" is REFUTED")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())