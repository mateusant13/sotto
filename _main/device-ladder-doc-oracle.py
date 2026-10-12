#!/usr/bin/env python3
"""device-ladder-doc-oracle -- does the worker README still describe the ladder the code has?

WHY THIS EXISTS. Audit row #23 was filed as "PREFERRED_DEVICES = () while the worker README
presents it populated". Measured, the claim as written is FALSE: the README never lists an entry,
it names a RUNG of the device_candidates() order. What IS true is subtler and worth a gate -- the
README documents an ORDER, and an order is a contract that drifts in silence. A lane that moves a
rung, or that populates the built-in tuple, leaves the doc describing a ladder that no longer
exists, and every later reader reasons from the doc.

WHAT IT CHECKS, from the bytes of both files:
  1. the README names the rungs of device_candidates() IN THE CODE ORDER;
  2. the README statement about emptiness AGREES with the tuple as the code has it today -- if
     PREFERRED_DEVICES = () becomes non-empty, a README that says EMPTY must go RED, and a README
     that stays silent while the tuple is empty is RED too.

BOTH COLOURS. --neg-arm writes two mutant READMEs into a scratch dir: one with two rungs swapped
(the ORDER check must break) and one with the emptiness sentence deleted (the EMPTINESS check must
break); the pristine copy must stay GREEN.

NO LAUNCH: plain string operations over two text files plus a copy of one of them.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
CODE = os.path.join(ROOT, "worker", "sotto_worker.py")
README = os.path.join(ROOT, "worker", "README.md")

SQ = chr(39)
DQ = chr(34)

#: (label, [substrings whose POSITION offers this rung]) in the order device_candidates offers them.
#: Written with chr() for the quotes so this file itself carries no quoting hazard.
CODE_RUNGS = (
    ("wanted", ["if wanted:"]),
    ("device", ["cfg_audio.get(" + SQ + "device" + SQ + ")",
                "cfg_audio.get(" + DQ + "device" + DQ + ")"]),
    ("preferred_devices", ["cfg_audio.get(" + SQ + "preferred_devices" + SQ + ")",
                           "cfg_audio.get(" + DQ + "preferred_devices" + DQ + ")"]),
    ("builtin", ["names.extend(PREFERRED_DEVICES)"]),
    ("tail", ["offer(d, " + SQ + "tail" + SQ, "offer(d, " + DQ + "tail" + DQ]),
)

#: README token -> rung. Two tokens map to "wanted" on purpose: the README splits the explicit
#: override into its two sources (the flag and the env var), which the code collapses into one.
README_TOKENS = (
    ("--device", "wanted"),
    ("SOTTO_AUDIO_DEVICE", "wanted"),
    ("audio.device", "device"),
    ("audio.preferred_devices", "preferred_devices"),
    ("PREFERRED_DEVICES", "builtin"),
    ("remaining non-microphone inputs", "tail"),
)

#: The sentence this oracle requires while the tuple has no entries, and forbids once it has one:
#: a doc that says EMPTY about a populated list is the same defect, mirrored.
EMPTY_CLAIMS = ("built-in tuple is **EMPTY**", "built-in tuple is **EMPTY",
                "built-in tuple is EMPTY")


def read(path):
    with open(path, encoding="utf-8", errors="replace") as handle:
        return handle.read()


def first_pos(text, keys):
    hits = [text.find(key) for key in keys]
    hits = [hit for hit in hits if hit >= 0]
    return min(hits) if hits else None


def code_rungs(text):
    out = []
    for label, keys in CODE_RUNGS:
        pos = first_pos(text, keys)
        if pos is not None:
            out.append((pos, label))
    out.sort()
    return [label for _pos, label in out]


def readme_rungs(text):
    hits = []
    for token, rung in README_TOKENS:
        pos = text.find(token)
        if pos >= 0:
            hits.append((pos, rung, token))
    hits.sort()
    order = []
    for _pos, rung, _token in hits:
        if not order or order[-1] != rung:
            order.append(rung)
    return order, [token for _pos, _rung, token in hits]


def builtin_tuple(text):
    marker = "PREFERRED_DEVICES = ("
    start = text.find(marker)
    if start < 0:
        return None, None
    end = text.find(")", start)
    body = text[start + len(marker):end].strip()
    entries = [part.strip() for part in body.split(",") if part.strip()]
    return len(entries), entries[:4]


def says_empty(text):
    low = text.lower()
    return any(claim.lower() in low for claim in EMPTY_CLAIMS)


def measure(code_path, readme_path, verbose=False):
    code_text, readme_text = read(code_path), read(readme_path)
    order = code_rungs(code_text)
    doc_order, tokens = readme_rungs(readme_text)
    count, sample = builtin_tuple(code_text)
    result = {
        "code_order": order,
        "readme_order": doc_order,
        "readme_tokens_seen": tokens,
        "builtin_entries": count,
        "builtin_entries_sample": sample,
        "readme_says_empty": says_empty(readme_text),
    }
    result["order_matches"] = order == doc_order
    result["emptiness_agrees"] = bool(result["readme_says_empty"]) == (count == 0)
    result["ladder_doc_drifted"] = not (result["order_matches"] and result["emptiness_agrees"])
    if verbose:
        result["readme_len"] = len(readme_text)
        result["code_len"] = len(code_text)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--code", default=CODE)
    parser.add_argument("--readme", default=README)
    parser.add_argument("--neg-arm", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    say("device-ladder-doc-oracle -- README order vs code order (no launch)")

    if parsed.neg_arm:
        scratch = tempfile.mkdtemp(prefix="sotto-ladder-neg-")
        control = measure(parsed.code, parsed.readme)
        say("  control (pristine)   order_matches=" + str(control["order_matches"])
            + " emptiness_agrees=" + str(control["emptiness_agrees"]))
        text = read(parsed.readme)
        mutants = {
            "m1-rungs-swapped": text.replace(
                "`audio.device`, then `audio.preferred_devices`",
                "`audio.preferred_devices`, then `audio.device`", 1),
            "m2-empty-sentence-removed": text.replace("built-in tuple is **EMPTY", "NOT", 1),
        }
        wrong = []
        if control["ladder_doc_drifted"]:
            wrong.append("control")
        for label, mutant in mutants.items():
            path = os.path.join(scratch, label + ".md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(mutant)
            got = measure(parsed.code, path)
            say("  " + label.ljust(26) + "order_matches=" + str(got["order_matches"])
                + " emptiness_agrees=" + str(got["emptiness_agrees"]))
            if label.startswith("m1") and got["order_matches"]:
                wrong.append(label + " (order not broken)")
            if label.startswith("m2") and got["emptiness_agrees"]:
                wrong.append(label + " (emptiness not broken)")
        say("")
        say("NEG-ARM: a mutated README must break its OWN check; wrong: " + str(wrong))
        say("NEG-ARM " + ("PASS" if not wrong else "FAIL"))
        return 0 if not wrong else 1

    result = measure(parsed.code, parsed.readme, parsed.verbose)
    for key in ("code_order", "readme_order", "builtin_entries", "readme_says_empty",
                "order_matches", "emptiness_agrees"):
        say("  " + key.ljust(20) + str(result[key]))
    say("")
    if result["ladder_doc_drifted"]:
        say("VERDICT: DRIFTED -- code rungs=" + str(len(result["code_order"]))
            + " documented=" + str(len(result["readme_order"]))
            + "; tuple entries=" + str(result["builtin_entries"])
            + "; readme_says_empty=" + str(result["readme_says_empty"]))
        return 1
    say("VERDICT: IN SYNC -- the README describes the ladder the code has today"
        + " (order matches, and the emptiness sentence agrees with the tuple)")
    return 0


if __name__ == "__main__":
    sys.exit(main())