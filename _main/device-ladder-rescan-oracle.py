#!/usr/bin/env python3
"""device-ladder-rescan-oracle -- "ordered once at startup" is true per RUN and false per SESSION.

AUDIT ROW F15: "o candidato de dispositivo e ordenado UMA vez no arranque e prefer_rendering_now nao
existe". Both halves are checkable, and they end in different places:

  HALF 1 -- the ordering. Within ONE run the candidate list IS a snapshot: it is built once
  (`candidates = device_candidates(...)`) and the rotation loop advances an INDEX into that list
  (`candidates[attempt_no + 1]`). So a device that appears DURING that run is not offered by the
  rotation. But the consequence the finding implies -- that a device appearing later is never seen --
  is FALSE, twice over:
    (a) MID-RUN: when a tap STALLS and the same-device re-opens are exhausted, the worker re-enumerates
        the live table and takes the FRESHEST first endpoint that is not the one it is on (the code
        says so in a comment: "the audio may simply have MOVED, so take the freshest enumeration");
    (b) PER RUN: every new worker run builds the list again, and the shell restarts the worker on the
        non-zero exit a flat ladder produces -- so the next run sees the new table.
  And the SUBSTANCE of the missing `prefer_rendering_now` -- prefer whatever is rendering now -- is
  implemented inside rung A, which reads each active render endpoint LIVE IAudioMeterInformation peak
  and sorts on it.

  HALF 2 -- `prefer_rendering_now` does not exist. Verified again here, by measurement: the name
  appears ZERO times in the live code tree. The finding is right about the name and the audit source is
  right that no cure was ever named; what was wrong was reading "the name is absent" as "the behaviour
  is absent".

WHAT IT DRIVES, with no audio hardware and no launch: `device_candidates` is extracted from the worker
and exec-ed in a namespace holding a FAKE `sounddevice` table (injected into sys.modules) and a fake
`wasapi_loopback` whose enumeration raises on purpose -- which is also a case the code claims to handle
("a machine with no render endpoint returns [] and the ladder skips to rung B rather than failing").

  1. ORDER/DEDUPE: the cable appears, a MICROPHONE does not, and two indices of the SAME endpoint
     collapse to ONE candidate;
  2. FRESHNESS: add a device to the fake table and call again -- it appears. The builder is a live
     snapshot, not a cache;
  3. the three byte facts behind half 1: one call site on the main path, the rotation indexing the
     frozen list, and the mid-run re-enumeration existing at all;
  4. the name `prefer_rendering_now` measured at zero in the live tree.
  --neg-arm: memoize the device table in the extracted source and arm 2 must go RED -- a freshness check
  that cannot see a cache proves nothing.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
WORKER = os.path.join(ROOT, "worker", "sotto_worker.py")

CABLE = "CABLE Output (VB-Audio Virtual Cable)"
MIC = "Microphone (USB Audio)"
PSEUDO = "Mapeador de som da Microsoft - Input"
LATE = "Line In (New Device Arrived Late)"

TABLE = [
    {"name": MIC, "max_input_channels": 2, "index": 0},
    {"name": CABLE, "max_input_channels": 2, "index": 1},
    {"name": CABLE, "max_input_channels": 2, "index": 2},
    {"name": PSEUDO, "max_input_channels": 2, "index": 3},
]


def extract(source, name):
    lines = source.split("\n")
    start = None
    for index, line in enumerate(lines):
        if line.startswith("def " + name + "("):
            start = index
            break
    if start is None:
        return None
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line and not line[0].isspace() and (line.startswith("def ") or line.startswith("class ")
                                               or line.startswith("@")):
            return "\n".join(lines[start:index])
    return "\n".join(lines[start:])


class FakeSD:
    def __init__(self, table):
        self.table = table

    def query_devices(self):
        return [dict(row) for row in self.table]


class NoRungA:
    """Rung A disabled on purpose: the fake table is the subject, and this is also the
    documented "no render endpoint" path."""

    @staticmethod
    def loopback_device_specs():
        raise RuntimeError("oracle: rung A disabled for determinism")


#: The ladder helpers read module-level tables (LOOPBACK_NAME_PATTERNS, SOUNDMAPPER_PATTERNS,
#: PREFERRED_DEVICES ...). Scraping them keeps this oracle driving the REAL scoring functions instead of
#: stubs I would have written myself -- a stub would make every arm below a test of the stub. Only
#: simple, evaluable literals are taken; anything that calls out is skipped BY NAME, so a missing
#: constant shows up as a NameError here rather than as silent agreement.
def module_constants(source):
    lines = source.split("\n")
    out = {}
    for index, line in enumerate(lines):
        match = re.match(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$", line)
        if not match:
            continue
        name, expr = match.group(1), match.group(2)
        depth = (expr.count("(") + expr.count("[") + expr.count("{")
                 - expr.count(")") - expr.count("]") - expr.count("}"))
        cursor = index
        while depth > 0 and cursor + 1 < len(lines):
            cursor += 1
            expr += "\n" + lines[cursor]
            depth = (expr.count("(") + expr.count("[") + expr.count("{")
                     - expr.count(")") - expr.count("]") - expr.count("}"))
        if expr.rstrip().endswith("\\"):
            continue
        try:
            out[name] = eval(expr.strip(), {"re": re})
        except Exception:
            continue
    return out


def build_namespace(source, table):
    names = module_constants(source)
    for helper in ("heuristic_loopback_score", "is_soundmapper_pseudo"):
        snippet = extract(source, helper)
        if not snippet:
            raise LookupError("the worker has no " + helper + " -- the ladder cannot be driven")
        exec(compile(snippet, "<" + helper + ">", "exec"), names)
    match = re.search(r"^PREFERRED_DEVICES\s*=\s*(.+)$", source, re.MULTILINE)
    names["PREFERRED_DEVICES"] = eval(match.group(1)) if match else ()
    names["err"] = lambda *a, **k: None
    return names


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--neg-arm", action="store_true")
    parsed = parser.parse_args(argv)
    say = print
    with open(WORKER, encoding="utf-8") as handle:
        source = handle.read()
    snippet = extract(source, "device_candidates")
    say("device-ladder-rescan-oracle -- F15, both halves (no device, no launch)")
    if not snippet:
        say("VERDICT: FAIL -- the worker has no device_candidates")
        return 1

    table = [dict(row) for row in TABLE]
    fake = FakeSD(table)
    saved_sd, saved_wa = sys.modules.get("sounddevice"), sys.modules.get("wasapi_loopback")
    sys.modules["sounddevice"] = fake
    sys.modules["wasapi_loopback"] = NoRungA
    wrong = []
    try:
        namespace = build_namespace(source, table)
        if parsed.neg_arm:
            mutant = snippet.replace(
                '    devs = [d for d in sd.query_devices() if d["max_input_channels"] > 0]',
                '    global _ORACLE_CACHE\n'
                '    if _ORACLE_CACHE is None:\n'
                '        _ORACLE_CACHE = [d for d in sd.query_devices()'
                ' if d["max_input_channels"] > 0]\n'
                '    devs = _ORACLE_CACHE')
            if mutant == snippet:
                say("NEG-ARM SETUP ERROR: the device-table line did not match")
                return 2
            namespace["_ORACLE_CACHE"] = None
            snippet = mutant
        exec(compile(snippet, "<device_candidates>", "exec"), namespace)
        ladder = namespace["device_candidates"]

        first = ladder({}, None)
        names1 = [c["name"] for c in first]
        say("  arm 1 candidates=%d  %s" % (len(first), [n[:34] for n in names1]))
        cable_hits = [n for n in names1 if n.startswith("CABLE Output")]
        if not cable_hits:
            wrong.append("the cable endpoint was never offered")
        if len(cable_hits) != 1:
            wrong.append("the SAME endpoint came back %d times (dedupe failed)" % len(cable_hits))
        if any(MIC == n for n in names1):
            wrong.append("a MICROPHONE was offered as a loopback candidate")

        table.append({"name": LATE, "max_input_channels": 2, "index": 4})
        second = ladder({}, None)
        names2 = [c["name"] for c in second]
        say("  arm 2 after the table gains a device: candidates=%d late_present=%s"
            % (len(second), str(LATE in names2).lower()))
        if LATE not in names2:
            wrong.append("a device that appeared AFTER the first call is INVISIBLE -- the builder is "
                         "a cache, not a live snapshot")

        main_calls = len(re.findall(r"^\s*candidates = device_candidates\(", source, re.MULTILINE))
        rescan = len(re.findall(r"for cand in device_candidates\(", source))
        rotation = len(re.findall(r"candidates\[attempt_no \+ 1\]", source))
        say("  arm 3 main-path builds=%d  mid-run re-enumerations=%d  rotation indexes the list=%d"
            % (main_calls, rescan, rotation))
        if main_calls != 1:
            wrong.append("expected exactly ONE build on the main path, saw %d" % main_calls)
        if rotation < 1:
            wrong.append("the rotation no longer indexes the frozen list -- re-read F15")
        if rescan < 1:
            wrong.append("NO mid-run re-enumeration exists, so the finding's consequence HOLDS")

        # SCOPE, fixed after the first run: the walk used to include the _main tree, and this oracle
        # names the string itself -- so the count could NEVER be zero and the arm proved nothing about
        # the product. The question is "does the PRODUCT implement it?", answered over worker/, app/
        # and scripts/. The audit documents and the oracles that name it are reported SEPARATELY,
        # because a name in a proposal is not an implementation.
        code_tree = []
        for product in ("worker", "app", "scripts"):
            for base, dirs, files in os.walk(os.path.join(ROOT, product)):
                dirs[:] = [d for d in dirs
                           if d not in {".git", "node_modules", "models", "__pycache__"}]
                for name in files:
                    if not name.endswith((".py", ".js", ".mjs", ".cmd")):
                        continue
                    path = os.path.join(base, name)
                    try:
                        with open(path, encoding="utf-8", errors="replace") as handle:
                            if "prefer_rendering_now" in handle.read():
                                code_tree.append(os.path.relpath(path, ROOT))
                    except OSError:
                        pass
        declared = []
        for extra in ("docs", "_main"):
            for base, dirs, files in os.walk(os.path.join(ROOT, extra)):
                dirs[:] = [d for d in dirs if d not in {".git", "__pycache__"}]
                for name in files:
                    if not name.endswith((".py", ".md", ".js", ".mjs")):
                        continue
                    path = os.path.join(base, name)
                    try:
                        with open(path, encoding="utf-8", errors="replace") as handle:
                            if "prefer_rendering_now" in handle.read():
                                declared.append(os.path.relpath(path, ROOT))
                    except OSError:
                        pass
        say("  arm 4 prefer_rendering_now in the PRODUCT tree: %d file(s)" % len(code_tree))
        say("        declared in docs/oracles (a PROPOSAL, not an implementation): %d file(s) %s"
            % (len(declared), [p for p in declared
                               if not p.endswith("device-ladder-rescan-oracle.py")][:4]))
        if code_tree:
            wrong.append("the product DOES name prefer_rendering_now: %s" % code_tree)
    finally:
        if saved_sd is not None:
            sys.modules["sounddevice"] = saved_sd
        else:
            sys.modules.pop("sounddevice", None)
        if saved_wa is not None:
            sys.modules["wasapi_loopback"] = saved_wa
        else:
            sys.modules.pop("wasapi_loopback", None)

    say("")
    if parsed.neg_arm:
        say("NEG-ARM " + ("PASS" if any("INVISIBLE" in w for w in wrong) else "FAIL")
            + ": memoizing the device table must make the freshness arm RED"
            + (" (it did)" if any("INVISIBLE" in w for w in wrong) else " (it did NOT)"))
        return 0 if any("INVISIBLE" in w for w in wrong) else 1
    say("VERDICT: " + ("PASS" if not wrong else "FAIL")
        + " -- per RUN the list is a snapshot and rotation indexes it, but the table is re-read on a"
        " tap stall and on every new run, and rung A already prefers what is rendering now;"
        " prefer_rendering_now is absent as a NAME, measured")
    for item in wrong:
        say("  wrong: " + item)
    return 0 if not wrong else 1


if __name__ == "__main__":
    sys.exit(main())
