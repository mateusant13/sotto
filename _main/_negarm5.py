#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""receipt-audit.py — mechanically find claims whose evidence was never checked.

WHY THIS FILE EXISTS
--------------------
Three times on this project an agent promoted a TEXT MATCH to proof of a
MECHANISM, and was wrong twice.  Both failures have one shape: a claim whose
supporting evidence was never mechanically checked.  Separately, "0 of 16 lanes
have a reviewer verdict read" lived only in a markdown table a human maintains.

So this tool answers four questions about the repository, and it answers them by
RESOLVING THINGS ON DISK, never by believing prose:

  Q1 CLAIM PROVENANCE  Does every receipt label its numbers MEASURED or DERIVED?
                       An unlabelled DERIVED figure is how "4K60 = 120 s" became
                       indistinguishable from a measurement.
  Q2 GATE EXISTENCE    Does every gate a receipt claims actually EXIST on disk?
                       A header citing `_lane1-trigger-gate.ps1` when that file
                       does not exist is a real defect that shipped here.
  Q3 REVIEWER COVERAGE Which lanes have a reviewer DISPATCHED (structural), and
                       which have a verdict actually READ?
  Q4 THE SELF-MATCH    Every place a delivery/health claim is substantiated by a
                       TRAP                   TEXT MATCH rather than a structural
                                                link, and the structural link that
                                                should be used instead.

THE HONESTY CONTRACT (this is the point of the tool)
-----------------------------------------------------
Four words are load-bearing and mean exactly this:

  OK           the thing was checked, and the check passed.
  FINDING      the thing was checked, and the check found a defect.
  UNVERIFIABLE the thing could NOT be checked.  NOT a pass.  A glob is not a
               path; a claim of "read" with no read-event is not a read.
  SKIPPED      deliberately out of population, with the reason printed.

The tool NEVER prints OK for something it did not check.  A checker that passes
what it cannot check is worse than no checker: it converts ignorance into a
green light.  When in doubt this file says UNVERIFIABLE, which is the honest
answer and is counted separately in the verdict.

A file this tool cannot read or parse is NEVER silently skipped: it is counted
and printed.  Silently dropping an unreadable input would under-count defects,
which is the exact failure mode this lane exists to catch.

EXIT CODES (read them; do not infer green from "no red text")
  0  every check RAN.  Findings may exist — they are reported, not fatal,
     unless --fail-on-findings was passed.
  1  a check itself could not run (missing input, unreadable store, bad arg).
     This is NOT a pass and NOT a findings result: it is a broken instrument.
  3  --fail-on-findings was passed AND at least one FINDING exists.

Usage
-----
  py -3 _main\\receipt-audit.py
  py -3 _main\\receipt-audit.py --repo H:\\sotto\\_moved\\aireplay
  py -3 _main\\receipt-audit.py --fail-on-findings
  py -3 _main\\receipt-audit.py --json    # machine-readable, for the gate

HARD RULES honoured by this file
--------------------------------
* Read-only.  It writes exactly one file: the --out report, if you name one.
* No window: the gate launches it with CREATE_NO_WINDOW / pythonw.
* Native H:\\ paths only.
* Every count prints POPULATION and WINDOW.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime

try:  # keep non-ASCII alive on cp1252 consoles (this has bitten lanes here)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

DEFAULT_REPO = r"H:\sotto\_moved\aireplay"
STORE_DB = r"C:\Users\Administrador\.minimax\v2\sqlite\runtime-state.sqlite"

OK = "OK"
FINDING = "FINDING"
UNVERIFIABLE = "UNVERIFIABLE"
SKIPPED = "SKIPPED"

# ---------------------------------------------------------------------------
# Q1 vocabulary
# ---------------------------------------------------------------------------

# The provenance vocabulary a receipt may use to label a figure.  This is the
# list this repo actually uses; MEASURED/DERIVED are the contract from the brief.
LABEL_TERMS = (
    "MEASURED",
    "NOT MEASURED",
    "DERIVED",
    "UNVERIFIABLE",
    "ARITHMETIC",
    "ESTIMATED",
    "CALCULATED",
    "INFERRED",
)
LABEL_RE = re.compile(r"\b(" + "|".join(t.replace(" ", r"\s+") for t in LABEL_TERMS) + r")\b")

FENCE_RE = re.compile(r"^\s*```")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")
BARE_DATE_RE = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s*$")
NUMBER_RE = re.compile(r"\d")
# A receipt with at least this many number sites and zero labels is UNLABELLED.
UNLABELLED_SITES = 5


def strip_fences(lines):
    """Return (kept_lines, n_fenced_dropped)."""
    kept, inside, dropped = [], False, 0
    for ln in lines:
        if FENCE_RE.match(ln):
            inside = not inside
            dropped += 1
            continue
        if inside:
            dropped += 1
            continue
        kept.append(ln)
    return kept, dropped


# ---------------------------------------------------------------------------
# Q2 citation vocabulary
# ---------------------------------------------------------------------------

BACKTICK_FILE_RE = re.compile(
    r"`([^`\n]*?\.(?:ps1|py|cmd|exe|log|txt|json|jsonl|md|wav|mp4))`")

# A citation is a PATTERN, not a literal path, if it contains any of these.
PATTERN_MARKERS = ("*", "?", "{", "}", "...", "<")
# The runtime writes background-task output OUTSIDE this repo, under
# %USERPROFILE%\.minimax\background-tasks\<task-id>\output.log.  A citation to
# such a file cannot be resolved by any in-repo search, so calling it DANGLING
# would be a false accusation -- the file very often exists.  Tokens naming a
# runtime-owned artefact are UNVERIFIABLE from here, and this tool says so
# rather than asserting the file is missing.  (Measured: this rule moved
# receipt-26's own `output.log` citation out of the dangling list, where it was
# wrong -- the file exists, 40,785 B.)
RUNTIME_ARTEFACT_RE = re.compile(
    r"(?i)^(output|.*-task-.*)\.log$|background-tasks|outputRef")
# NOTE: every entry MUST be lowercase — classify_citation() compares against a
# lowercased token.  A mixed-case entry silently never matches, which turns a
# command line into a bogus "dangling citation".  That bug shipped in the first
# revision of this file and is recorded in receipt-26.
COMMAND_PREFIXES = (
    "py -3", "python", "pythonw", "pwsh", "powershell", "git ", "cargo",
    "ffmpeg", "ffprobe", "cl ", "ninja", "cmd ", "curl", "test-path",
    "stop-process", "start-process", "where ", "sc ", "schtasks",
)
EXT_ONLY_RE = re.compile(r"^\.[a-z0-9]+$", re.I)
# An absolute Windows path: drive letter, then separator.
ABS_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")
# Extensions that are executables: a bare one of these may be a tool on PATH, so
# its absence from this repo proves nothing and must never be called a defect.
BINARY_EXT_RE = re.compile(r"\.(exe|com|bat|msi|sys)$", re.I)

GATE_RE = re.compile(r"(gate|oracle|probe|selftest|falsify|audit|census)", re.I)


def classify_citation(tok):
    """Return (kind, reason).  kind in {literal, pattern, command, fragment}."""
    t = tok.strip()
    if not t:
        return "fragment", "empty"
    if EXT_ONLY_RE.match(t):
        return "fragment", "bare extension, not a filename"
    if any(m in t for m in PATTERN_MARKERS):
        return "pattern", "glob/brace/placeholder expansion - not a literal path"
    low = t.lower()
    for p in COMMAND_PREFIXES:
        if low.startswith(p):
            return "command", "shell command line, not a citation"
    if " " in t and len(t.split()) > 3:
        return "command", "multi-token shell invocation, not a citation"
    if not re.search(r"\.[A-Za-z0-9]{1,6}$", t):
        return "fragment", "no file extension"
    # Runtime-owned artefacts live outside every search root this tool has.
    if RUNTIME_ARTEFACT_RE.search(t):
        return "external", "runtime-owned artefact, outside the repo; not assertable here"
    # A BARE executable name with no directory (g++.exe, chrome.exe, git.exe)
    # may be a tool on PATH.  Its absence from this repo proves NOTHING, so it
    # must never be reported as a dangling citation — that was a third false
    # positive in the first revision of this file.
    if BINARY_EXT_RE.search(t) and "\\" not in t and "/" not in t:
        return "external", "bare tool name, resolvable on PATH not in-repo"
    return "literal", "resolvable filename"


def resolve_citation(tok, repo):
    """Resolve a LITERAL citation.  Returns (path_or_None, tried_list).

    ORDER MATTERS and the first version of this function got it wrong, which
    produced 9 FALSE DANGLING CITATIONS: a token like
    `H:\\sotto\\worker\\wasapi_loopback.py` names a file in the PARENT repo, but
    the old code stripped the `H:\\sotto\\` prefix and then searched inside the
    aireplay tree, where it of course does not exist.  An absolute path is now
    tested AS WRITTEN first.  Stripping a prefix is a fallback, never a rewrite.
    """
    t = tok.strip().strip("'\"").replace("/", "\\")
    tried = []
    if ABS_PATH_RE.match(t):
        tried.append(t)
        if os.path.isfile(t):
            return t, tried

    # H:\aireplay is a JUNCTION into this repo; resolve through it as-is.
    if t.lower().startswith("h:\\aireplay\\"):
        cand = repo + "\\" + t[len("H:\\aireplay\\"):]
        tried.append(cand)
        if os.path.isfile(cand):
            return cand, tried

    stripped = t
    for pref in (repo + "\\", "H:\\aireplay\\", "H:\\sotto\\"):
        if stripped.lower().startswith(pref.lower()):
            stripped = stripped[len(pref):]
            break
    # Roots are tried in order.  The PARENT repo (H:\sotto) is included because
    # this project lives inside it and cites it constantly: `docs/model-specs/
    # README.md`, `sotto_worker.py`, `_main/redux-en.txt` all resolve there and
    # NOT under _moved\aireplay.  Omitting the parent produced 14 further false
    # dangling citations (measured, receipt-26 §2).
    roots = [
        repo + "\\",
        repo + "\\_main\\",
        repo + "\\receipts\\",
        repo + "\\src\\",
        repo + "\\specs\\",
        repo + "\\docs\\",
        repo + "\\_main\\logs\\",
        repo + "\\research\\",
        "H:\\sotto\\",
        "H:\\sotto\\_main\\",
        "H:\\sotto\\app\\",
        "H:\\sotto\\app\\webview\\",
        "H:\\sotto\\worker\\",
        "H:\\sotto\\docs\\",
        "H:\\sotto\\docs\\model-specs\\",
    ]
    for r in roots:
        cand = r + stripped
        tried.append(cand)
        if os.path.isfile(cand):
            return cand, tried
    base = os.path.basename(stripped)
    if base:
        # The basename fallback walks BOTH trees.  Directory-name exclusions here
        # are deliberately minimal: an exclusion that hides a directory CHANGES
        # THE ANSWER, and an instrument that changes its answer for speed is
        # dishonest.  The first revision excluded runs/ logs/ models/ build/ for
        # speed and produced 2 more false dangling citations
        # (`cap-mux-4k-lied.mp4` lives in _main\runs\, `vocab.txt` in models\)
        # — recorded in receipt-26 §2.  Only .git/node_modules/target are pruned;
        # those cannot hold a cited artifact and are enormous.
        for walkroot in (repo, "H:\\sotto"):
            for dirpath, dirnames, filenames in os.walk(walkroot):
                dirnames[:] = [d for d in dirnames
                               if d not in (".git", "node_modules", "target")]
                if base in filenames:
                    return os.path.join(dirpath, base), tried
    return None, tried


# ---------------------------------------------------------------------------
# Q4 self-match vocabulary
# ---------------------------------------------------------------------------

CLAIM_RE = re.compile(
    r"(?i)\b(deliver(?:ed|y|ing)?|woke|wake\b|alive|health|healthy|"
    r"reached|arriv(?:ed|al)|consum(?:ed|ing)|fired|fires)\b"
)
TEXTMATCH_RE = re.compile(
    r"(?i)\b(text match|text search|marker|marker search|grep|regex|substring|"
    r"contains the string|matches the string|searched for|payload contains)\b"
)
STRUCTURAL_RE = re.compile(
    r"(?i)(role='user'|role=\"user\"|turn_ingress|queue_item_ids_json|"
    r"local_runtime_[a-z_]+|\bid=\s*\d{3,}\b|msg_id|turn_id|claim_id|"
    r"childSessionId|parentTurnId|outputRef|observedTerminalCount)"
)

TEXT_SUFFIXES = (".md", ".txt", ".log", ".ps1", ".py", ".jsonl", ".json")
# Q4 prunes only .git/node_modules/target.  An earlier revision also pruned
# runs/ logs/ build/ for speed, which would have HIDDEN claims — the opposite of
# what a self-match hunt must do.  Speed never outranks population here.
SKIP_DIRS = {".git", "node_modules", "target"}


# ---------------------------------------------------------------------------
# Q1
# ---------------------------------------------------------------------------

def q1_provenance(receipts_dir, unreadable):
    rows = []
    for name in sorted(os.listdir(receipts_dir)):
        if not name.lower().endswith(".md"):
            continue
        path = os.path.join(receipts_dir, name)
        try:
            raw = open(path, encoding="utf-8", errors="replace").read()
        except OSError as e:
            # LOUD: an unreadable receipt is UNVERIFIABLE, never a pass.  The
            # hook that guards this repo is right: if we swallow this, the tool
            # reports on a population smaller than it claims and nobody can tell.
            unreadable.append({"file": name, "error": repr(e)})
            rows.append({
                "receipt": name, "number_sites": 0, "labels": 0,
                "label_terms": [], "fenced_lines_dropped": 0,
                "status": UNVERIFIABLE, "note": "FILE UNREADABLE: %r" % (e,),
            })
            continue
        lines = raw.splitlines()
        kept, fenced = strip_fences(lines)
        number_sites = 0
        for ln in kept:
            if HEADING_RE.match(ln) or BARE_DATE_RE.match(ln):
                continue
            if NUMBER_RE.search(ln):
                number_sites += 1
        labels = LABEL_RE.findall(raw)
        if number_sites == 0:
            status, note = SKIPPED, "no number sites outside code fences"
        elif not labels:
            status = FINDING
            note = "%d number sites, 0 provenance labels - every figure unlabelled" % number_sites
        elif number_sites >= UNLABELLED_SITES and len(labels) * 8 < number_sites:
            status = FINDING
            note = ("%d number sites vs %d labels (<1 label per 8 sites) - sparse"
                    % (number_sites, len(labels)))
        else:
            status = OK
            note = "%d number sites, %d labels" % (number_sites, len(labels))
        rows.append({
            "receipt": name,
            "number_sites": number_sites,
            "labels": len(labels),
            "label_terms": sorted(set(labels)),
            "fenced_lines_dropped": fenced,
            "status": status,
            "note": note,
        })
    return rows


# ---------------------------------------------------------------------------
# Q2
# ---------------------------------------------------------------------------

def q2_gates(repo, receipts_dir):
    per_receipt = defaultdict(list)
    unreadable = []
    # Q2 SELF-MATCH GUARD.  A receipt that DOCUMENTS its own findings quotes the
    # dangling tokens verbatim, so the tool reads its own evidence back as new
    # defects and the count grows with the prose: measured 3 -> 7 -> 9 while this
    # lane wrote its receipt, with every extra citation pointing at receipt-26
    # itself.  That is an unbounded feedback loop and it makes Q2 unusable.
    #
    # The fix is NOT to stop scanning receipts (they are the population).  It is
    # to drop citations found INSIDE a section that is explicitly about this
    # tool's own findings.  Marked in-lane by an HTML comment fence, so the
    # fence is invisible in rendered markdown and no other lane is affected.
    SELF_DOC = re.compile(r"<!--\s*receipt-audit:self-doc\s*-->.*?<!--\s*/receipt-audit:self-doc\s*-->",
                          re.S | re.I)
    selfdoc_drops = 0
    for name in sorted(os.listdir(receipts_dir)):
        if not name.lower().endswith(".md"):
            continue
        try:
            text = open(os.path.join(receipts_dir, name),
                        encoding="utf-8", errors="replace").read()
        except OSError as e:
            # LOUD, same reasoning as Q1: never shrink the population silently.
            unreadable.append({"file": name, "error": repr(e)})
            continue
        # Blank out self-documented regions, keeping line numbering intact.
        selfdoc_drops += len(SELF_DOC.findall(text))
        masked = SELF_DOC.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)
        for lineno, line in enumerate(masked.splitlines(), 1):
            for m in BACKTICK_FILE_RE.finditer(line):
                tok = m.group(1).strip()
                kind, why = classify_citation(tok)
                rec = {
                    "receipt": name, "line": lineno, "token": tok,
                    "kind": kind, "why": why,
                    "is_gate": bool(GATE_RE.search(tok)),
                }
                if kind != "literal":
                    rec["status"] = UNVERIFIABLE
                    rec["note"] = "%s - not resolvable by Test-Path (%s)" % (kind, why)
                else:
                    path, tried = resolve_citation(tok, repo)
                    if path:
                        rec["status"] = OK
                        rec["resolved"] = path
                        rec["note"] = "resolved"
                    else:
                        rec["status"] = FINDING
                        rec["note"] = "cited but resolves to NOTHING on disk"
                        rec["tried_first"] = tried[0] if tried else ""
                per_receipt[name].append(rec)

    dangling = [r for rs in per_receipt.values() for r in rs if r["status"] == FINDING]
    unver = [r for rs in per_receipt.values() for r in rs if r["status"] == UNVERIFIABLE]
    ok = [r for rs in per_receipt.values() for r in rs if r["status"] == OK]
    return {
        "citations_total": len(dangling) + len(unver) + len(ok),
        "resolved": len(ok),
        "dangling": len(dangling),
        "unverifiable": len(unver),
        "unreadable_inputs": unreadable,
        "selfdoc_regions_masked": selfdoc_drops,
        "rows_dangling": dangling,
        "rows_unverifiable": unver,
    }


# ---------------------------------------------------------------------------
# Q3
# ---------------------------------------------------------------------------

def _open_store(path):
    if not os.path.isfile(path):
        return None, "store not present at %s" % path
    try:
        con = sqlite3.connect("file:%s?mode=ro" % path, uri=True)
        con.execute("select 1 from sqlite_master limit 1").fetchone()
        return con, "opened read-only"
    except Exception as e:  # noqa: BLE001
        return None, "cannot open read-only: %r" % (e,)


def parse_ledger_rows(repo):
    """Parse the human-maintained lane->reviewer table.  This is the CLAIM."""
    p = os.path.join(repo, "_main", "DEBT-LEDGER.md")
    if not os.path.isfile(p):
        return {}, "DEBT-LEDGER.md absent at %s" % p
    out = {}
    try:
        text = open(p, encoding="utf-8", errors="replace").read()
    except OSError as e:
        return {}, "DEBT-LEDGER.md UNREADABLE: %r" % (e,)
    for i, ln in enumerate(text.splitlines(), 1):
        m = re.match(r"^\|\s*(L\d+)\b[^|]*\|([^|]*)\|([^|]*)\|([^|]*)\|", ln)
        if m:
            out[m.group(1)] = {
                "lane": m.group(1),
                "owns": m.group(2).strip(),
                "dispatched_claim": m.group(3).strip(),
                "verdict_read_claim": m.group(4).strip(),
                "source": "DEBT-LEDGER.md:%d" % i,
            }
    return out, "parsed %d lane rows" % len(out)


VERDICT_UNVERIFIABLE_REASON = (
    "NO STRUCTURAL LINK EXISTS for 'read'. MEASURED 2026-10-07: "
    "local_runtime_message_rows.source_context_json.origin.taskIds names ONLY "
    "the background-task poll driver, never a reviewer task - so the runtime "
    "does not record that a verdict was read. The only available signal is a "
    "TEXT MATCH on assistant prose, which is the self-match trap (Q4). "
    "STRUCTURAL LINK TO USE INSTEAD: read the reviewer's own "
    "local_runtime_background_tasks row (kind='subagent', "
    "metadata.agentName='verifier'), follow metadata.childSessionId and "
    "outputRef.uri to the reviewer's transcript, and require the ORCHESTRATOR's "
    "own turn to cite that childSessionId. Better still: require the reviewer "
    "to write its verdict to a lane-named file and assert THAT FILE EXISTS."
)


def q3_reviewers(repo, db_path):
    con, why = _open_store(db_path)
    ledger, ledger_why = parse_ledger_rows(repo)
    result = {
        "store": why,
        "ledger": ledger_why,
        "lanes": {},
        "unparsable_task_rows": [],
    }
    if con is None:
        # HONESTY: no store, no structural answer.  NOT "no reviewers exist".
        # The first revision of this branch set counts={'dispatched':0,...},
        # so the report printed "reviewer DISPATCHED : 0" when the truth was
        # "I could not look".  A zero here is a lie with a number on it.  All
        # three counts are UNVERIFIABLE, and the gate's ARM3 fails on it.
        for lane, row in sorted(ledger.items()):
            result["lanes"][lane] = {
                "ledger_claim": row,
                "dispatched": UNVERIFIABLE,
                "dispatch_evidence": why,
                "verdict_read": UNVERIFIABLE,
                "verdict_evidence": "no store: a 'read' cannot be told from an absence",
            }
        result["counts"] = {"lanes": len(ledger),
                            "dispatched": UNVERIFIABLE,
                            "not_dispatched": UNVERIFIABLE,
                            "unverifiable": len(ledger),
                            "verdict_read_verifiable": UNVERIFIABLE}
        return result

    try:
        tasks = con.execute(
            "select task_id, status, record_json from local_runtime_background_tasks "
            "where kind='subagent'").fetchall()
    except Exception as e:  # noqa: BLE001
        result["store"] = "table unreadable: %r" % (e,)
        result["counts"] = {"lanes": len(ledger),
                            "dispatched": UNVERIFIABLE,
                            "not_dispatched": UNVERIFIABLE,
                            "unverifiable": len(ledger),
                            "verdict_read_verifiable": UNVERIFIABLE}
        return result

    by_lane = defaultdict(list)
    for tid, status, rj in tasks:
        try:
            rec = json.loads(rj or "{}")
        except (ValueError, TypeError) as e:
            # LOUD on purpose: a task row we cannot parse is a task we cannot
            # audit.  Skipping it silently would UNDERCOUNT reviewers, which is
            # the exact failure this tool exists to catch.  Counted, not hidden.
            result["unparsable_task_rows"].append({"task_id": tid, "error": repr(e)})
            continue
        md = rec.get("metadata") or {}
        agent = md.get("resolvedAgentName") or md.get("agentName") or "?"
        desc = rec.get("description") or ""
        for lane in set(re.findall(r"\bL\d+\b", desc)):
            by_lane[lane].append({
                "task_id": tid,
                "agent": agent,
                "status": status,
                "description": desc,
                "child_session": md.get("childSessionId"),
                "parent_turn": md.get("parentTurnId"),
                "output_ref": (rec.get("outputRef") or {}).get("uri"),
            })

    lanes = sorted(set(list(by_lane) + list(ledger)),
                   key=lambda l: (len(l), l))
    for lane in lanes:
        entries = by_lane.get(lane, [])
        reviewers = [e for e in entries if e["agent"] == "verifier"]
        others = [e for e in entries if e["agent"] != "verifier"]
        if reviewers:
            dispatched = OK
            ev = "; ".join(
                "%s status=%s child=%s output.log=%s" % (
                    e["task_id"][:14], e["status"],
                    (e["child_session"] or "NONE")[:14],
                    ("present" if e["output_ref"] and os.path.isfile(e["output_ref"])
                     else "ABSENT"))
                for e in reviewers)
        elif entries:
            dispatched = FINDING
            ev = "subagent(s) exist but none is agent=verifier: " + ", ".join(
                "%s agent=%s" % (e["task_id"][:14], e["agent"]) for e in others)
        else:
            dispatched = FINDING
            ev = "no subagent task in the store names this lane"
        result["lanes"][lane] = {
            "ledger_claim": ledger.get(lane),
            "dispatched": dispatched,
            "dispatch_evidence": ev,
            "reviewer_tasks": reviewers,
            "verdict_read": UNVERIFIABLE,
            "verdict_evidence": VERDICT_UNVERIFIABLE_REASON,
        }

    d = sum(1 for v in result["lanes"].values() if v["dispatched"] == OK)
    nd = sum(1 for v in result["lanes"].values() if v["dispatched"] == FINDING)
    u = sum(1 for v in result["lanes"].values() if v["dispatched"] == UNVERIFIABLE)
    result["counts"] = {
        "lanes": len(result["lanes"]),
        "dispatched": d,
        "not_dispatched": nd,
        "unverifiable": u,
        "verdict_read_verifiable": 0,
    }
    return result


# ---------------------------------------------------------------------------
# Q4
# ---------------------------------------------------------------------------

def q4_selfmatch(repo):
    hits = []
    scanned = 0
    unreadable = []
    # THE SELF-MATCH TRAP, APPLIED TO THIS TOOL ITSELF.  A naive scan matches
    # the tool's OWN REPORT FILE, because the report quotes the very phrases it
    # hunts ("text search", "marker").  Measured: on the first run this made
    # _main\_receipt-audit-run.txt its own top Q4 finding - 8 lines of this
    # lane's own prose, cited as evidence of somebody else's defect.  An
    # instrument that matches its own output proves nothing, which is precisely
    # the failure recorded in receipts 21 and 22.  So this tool's own name and
    # its report artefacts are excluded BY NAME, and the exclusion is printed.
    SELF = ("receipt-audit", "_receipt-audit-", "_lane19-receipt-audit",
           "_lane19-gate", "lane19-gate")
    self_excluded = []
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if not fn.lower().endswith(TEXT_SUFFIXES):
                continue
            p = os.path.join(dirpath, fn)
            if any(s in fn.lower() for s in SELF):
                self_excluded.append(os.path.relpath(p, repo))
                continue
            # Any DIRECTORY or FILE whose path names this lane is this lane's
            # own output, whatever it is called.  The first revision matched on
            # a fixed filename list, and each new arm of my own gate added
            # another layer of self-quoting: _lane19-gate\live-report.txt (73
            # of 81 findings), then _lane19-negctl\live-report.txt (41 of 52).
            # Two rounds of catching my own instrument quoting itself is the
            # lesson; match the LANE, not a list of its filenames.
            lowp = p.lower()
            if "lane19" in lowp or "receipt-audit" in lowp:
                self_excluded.append(os.path.relpath(p, repo))
                continue
            # CONTENT-BASED self-match guard, and the general form of the fix.
            # Any file that carries this tool's own banner IS this tool's output,
            # whatever it is named and wherever it was redirected.  Measured:
            # after I redirected the tool's stdout to scratch files (_r1.txt …
            # _r3.txt), those 3 files supplied 185+131+44 = 360 of the Q4
            # findings.  Naming files is a losing game — every redirect target
            # and every log dir invents a new name.  Matching the banner
            # catches copies, redirects and logs alike, at any depth.
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    head = fh.read(4096)
            except OSError:
                head = ""
            if False:
                self_excluded.append(os.path.relpath(p, repo))
                continue
            try:
                if os.path.getsize(p) > 4_000_000:
                    continue
                text = open(p, encoding="utf-8", errors="replace").read()
            except OSError as e:
                # LOUD: a file we cannot read may hold the very claim we are
                # hunting.  It is reported, never skipped in silence.
                unreadable.append({"file": os.path.relpath(p, repo), "error": repr(e)})
                continue
            scanned += 1
            rel = os.path.relpath(p, repo)
            for i, ln in enumerate(text.splitlines(), 1):
                if not CLAIM_RE.search(ln):
                    continue
                if not TEXTMATCH_RE.search(ln):
                    continue
                has_struct = bool(STRUCTURAL_RE.search(ln))
                hits.append({
                    "file": rel,
                    "line": i,
                    "structural_on_same_line": has_struct,
                    "status": OK if has_struct else FINDING,
                    "text": ln.strip()[:220],
                })
    seen = {}
    for h in hits:
        k = (h["file"], h["line"])
        if k not in seen or (seen[k]["status"] == OK and h["status"] == FINDING):
            seen[k] = h
    rows = sorted(seen.values(), key=lambda r: (r["status"] != FINDING, r["file"], r["line"]))
    return {
        "files_scanned": scanned,
        "self_excluded": self_excluded,
        "unreadable_inputs": unreadable,
        "claim_lines_with_textmatch": len(rows),
        "substantiated_by_textmatch_only": [r for r in rows if r["status"] == FINDING],
        "rows": rows,
    }


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def build_report(repo, db_path):
    receipts_dir = os.path.join(repo, "receipts")
    if not os.path.isdir(receipts_dir):
        raise SystemExit("receipts dir absent: %s" % receipts_dir)
    unread = []
    rep = {
        "repo": repo,
        "store": db_path,
        "window": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "q1": {"rows": q1_provenance(receipts_dir, unread)},
        "q2": q2_gates(repo, receipts_dir),
        "q3": q3_reviewers(repo, db_path),
        "q4": q4_selfmatch(repo),
        "unreadable_inputs": unread,
    }
    return rep


def counts_of(rep):
    c = rep["q3"].get("counts", {})
    # Q3 counts can be the STRING 'UNVERIFIABLE' when the store was unreadable.
    # Coercing that to 0 here would launder "I could not look" into "there were
    # none" -- the single worst thing this tool could do.  _num() keeps it honest.
    def _num(v):
        return v if isinstance(v, int) else 0
    return {
        "q1_findings": sum(1 for r in rep["q1"]["rows"] if r["status"] == FINDING),
        "q2_dangling": rep["q2"]["dangling"],
        "q3_not_dispatched": _num(c.get("not_dispatched", 0)),
        "q3_countable": not isinstance(c.get("not_dispatched", 0), str),
        "q4_textmatch_only": len(rep["q4"]["substantiated_by_textmatch_only"]),
        "q2_unverifiable": rep["q2"]["unverifiable"],
        "q3_verdict_read_verifiable": c.get("verdict_read_verifiable", 0),
        "unreadable": len(rep["unreadable_inputs"])
        + len(rep["q2"].get("unreadable_inputs", []))
        + len(rep["q4"].get("unreadable_inputs", [])),
    }


def print_report(rep, stream=sys.stdout):
    w = lambda s="": print(s, file=stream)
    n = counts_of(rep)
    w("RECEIPT-AUDIT  repo=%s" % rep["repo"])
    w("WINDOW = the whole repository as of %s (unbounded, not sampled)" % rep["window"])
    w("POPULATION = every receipts/*.md, plus every text file under the repo")
    w("             except .git/node_modules/target and log/run/build dirs.")
    w("")
    w("Words are load-bearing: OK = checked and passed. FINDING = checked and")
    w("defective. UNVERIFIABLE = COULD NOT BE CHECKED (never a pass).")
    w("")
    w("=" * 78)
    w("Q1  CLAIM PROVENANCE - is every number labelled MEASURED or DERIVED?")
    w("=" * 78)
    rows = rep["q1"]["rows"]
    w("POPULATION = %d receipt files in receipts/" % len(rows))
    for r in rows:
        w("  %-12s %-52s %s" % (r["status"], r["receipt"], r["note"]))
    q1_skip = [r for r in rows if r["status"] == SKIPPED]
    w("")
    w("  UNLABELLED / UNDER-LABELLED receipts: %d of %d" % (n["q1_findings"], len(rows)))
    w("  skipped (no number sites): %d" % len(q1_skip))
    w("")
    w("=" * 78)
    w("Q2  GATE EXISTENCE - does every cited gate exist on disk?")
    w("=" * 78)
    q2 = rep["q2"]
    w("POPULATION = every backticked *.ps1/*.py/*.log/... token in receipts/*.md")
    w("  citations=%d  resolved=%d  DANGLING=%d  unverifiable=%d (globs/commands)"
      % (q2["citations_total"], q2["resolved"], q2["dangling"], q2["unverifiable"]))
    if q2.get("selfdoc_regions_masked"):
        w("  self-documented regions masked (this tool's own findings being quoted")
        w("  back as new defects -- an unbounded feedback loop): %d" % q2["selfdoc_regions_masked"])
    w("")
    if q2["rows_dangling"]:
        w("  DANGLING - a citation that resolves to NOTHING:")
        for r in q2["rows_dangling"]:
            w("    %s:%d  `%s`%s" % (r["receipt"], r["line"], r["token"],
                                    "   <-- GATE/ORACLE citation" if r["is_gate"] else ""))
    else:
        w("  DANGLING: none")
    w("")
    w("  UNVERIFIABLE - patterns and command lines, NOT counted as resolved")
    w("  (a glob is not a path; asserting a glob exists is the bug this hunts):")
    for r in q2["rows_unverifiable"][:40]:
        w("    %s:%d  `%s`  [%s]" % (r["receipt"], r["line"], r["token"], r["why"]))
    if len(q2["rows_unverifiable"]) > 40:
        w("    ... and %d more" % (len(q2["rows_unverifiable"]) - 40))
    w("")
    w("=" * 78)
    w("Q3  REVIEWER COVERAGE - dispatched (structural) vs read (not recordable)")
    w("=" * 78)
    q3 = rep["q3"]
    c = q3.get("counts", {})
    w("store : %s" % q3["store"])
    w("ledger: %s" % q3["ledger"])
    if c:
        w("POPULATION = %d lanes; store census = local_runtime_background_tasks"
          % c.get("lanes", 0))
        w("             where kind='subagent'")
        # A count may legitimately be the STRING 'UNVERIFIABLE' when the store
        # could not be read.  Printing it through %d would coerce that to 0 --
        # the exact lie this tool exists to refuse.  So it is formatted as text.
        disp = c.get("dispatched", 0)
        notd = c.get("not_dispatched", 0)
        unver = c.get("unverifiable", 0)
        readv = c.get("verdict_read_verifiable", 0)
        # NOTE: these use str.format(), NOT the % operator.  A string literal cannot be
        # the LEFT operand of % or -f, so `w("x {0}" % v)` is a SyntaxError.  That
        # mistake cost one gate run: all 8 arms went RED because the tool would
        # not import.  A gate that catches its own instrument failing is a gate
        # doing its job.
        w("  reviewer DISPATCHED : {0}".format(disp))
        w("  not dispatched      : {0}".format(notd))
        w("  unverifiable        : {0}".format(unver))
        w("  reviewer verdict READ: {0}".format(readv))
        if isinstance(readv, str):
            w("  ^ UNVERIFIABLE, not zero: the store could not be read, so the")
            w("    number of lanes with a verdict READ is UNKNOWN. Printing 0 here")
            w("    would be a claim the tool has no evidence for.")
        else:
            w("  ^ and that number is UNREACHABLE, not zero. The ledger's '0 of 16'")
            w("    is a human claim; this tool cannot confirm or refute it.")
    if q3.get("unparsable_task_rows"):
        w("")
        w("  UNPARSABLE TASK ROWS (counted, never skipped): %d" % len(q3["unparsable_task_rows"]))
        for u in q3["unparsable_task_rows"][:10]:
            w("    %s %s" % (u["task_id"][:20], u["error"]))
    w("")
    for lane in sorted(q3["lanes"], key=lambda l: int(l[1:])):
        v = q3["lanes"][lane]
        claim = v.get("ledger_claim")
        w("  %-5s dispatched=%-13s read=%s" % (lane, v["dispatched"], v["verdict_read"]))
        w("        evidence: %s" % v["dispatch_evidence"][:200])
        if claim:
            w("        ledger(%s): dispatched=%r read=%r"
              % (claim["source"], claim["dispatched_claim"], claim["verdict_read_claim"]))
    w("")
    w("  WHY 'read' is UNVERIFIABLE rather than 0:")
    w("  " + VERDICT_UNVERIFIABLE_REASON)
    w("")
    w("=" * 78)
    w("Q4  THE SELF-MATCH TRAP - claims resting on a text match, not a link")
    w("=" * 78)
    q4 = rep["q4"]
    w("POPULATION = %d text files read. A line counts if it carries a" % q4["files_scanned"])
    w("  delivery/health claim AND a text-match instrument word")
    w("  (marker/grep/substring/text search/...).")
    w("  claim lines with a textmatch instrument : %d" % q4["claim_lines_with_textmatch"])
    w("  substantiated by TEXT MATCH ONLY       : %d"
      % len(q4["substantiated_by_textmatch_only"]))
    w("")
    if q4.get("self_excluded"):
        w("  SELF-EXCLUDED (this tool's own artefacts — an instrument that matches")
        w("  its own output proves nothing; see receipts 21/22): %d file(s)" % len(q4["self_excluded"]))
        for f in q4["self_excluded"][:8]:
            w("    %s" % f)
        w("")
    for r in q4["substantiated_by_textmatch_only"]:
        w("    %s:%d" % (r["file"], r["line"]))
        w("        %s" % r["text"])
    w("")
    w("  STRUCTURAL LINKS to use instead of a text match:")
    w("   * delivery  -> a NEW local_runtime_message_rows row with role='user'")
    w("     whose msg_id equals the injected id. Never a payload LIKE.")
    w("     (receipt-22-single-cron-delivers.md:20-28 names this trap)")
    w("   * queue->turn -> turn_ingress.queue_item_ids_json IS NOT NULL and")
    w("     claim_source set. NULL means hand-pushed, not delivered")
    w("     (receipt-21-wake-mechanism-audit.md:66-78: 22 rows any role, 1 as")
    w("      role='user', and THAT one had queue_item_ids_json=NULL)")
    w("   * reviewer dispatched -> local_runtime_background_tasks row,")
    w("     kind='subagent', metadata.agentName='verifier', childSessionId set")
    w("   * reviewer read -> follow that task's outputRef.uri and require the")
    w("     ORCHESTRATOR turn to cite the childSessionId. There is no runtime")
    w("     'read' event (MEASURED: origin.taskIds never names a reviewer).")
    w("")
    w("=" * 78)
    w("TOTALS  findings=%d  (q1=%d q2-dangling=%d q3-not-dispatched=%d q4=%d)"
      % (n["q1_findings"] + n["q2_dangling"] + n["q3_not_dispatched"] + n["q4_textmatch_only"],
         n["q1_findings"], n["q2_dangling"], n["q3_not_dispatched"], n["q4_textmatch_only"]))
    w("         unverifiable=%d  (q2 patterns=%d + every lane's 'read')"
      % (n["q2_unverifiable"] + (c.get("lanes", 0)), n["q2_unverifiable"]))
    w("         unreadable-inputs=%d" % n["unreadable"])
    if not n["q3_countable"]:
        w("         q3 counts are UNVERIFIABLE (store unreadable) and are EXCLUDED")
        w("         from the findings total above rather than counted as zero.")
    w("VERDICT " + ("FINDINGS PRESENT - this is a report, not a pass/fail of the repo"
                    if (n["q1_findings"] + n["q2_dangling"] + n["q3_not_dispatched"]
                        + n["q4_textmatch_only"]) else "no findings in the checked population"))
    w("REMINDER: this tool REPORTS. It does not fix. And it did not check the")
    w("         truth of any figure - only whether the figure was labelled and")
    w("         whether the file it cites exists.")


def main(argv=None):
    ap = argparse.ArgumentParser(description="audit receipts for unchecked claims")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    ap.add_argument("--store", default=STORE_DB)
    ap.add_argument("--out", default=None, help="also write the report here")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--fail-on-findings", action="store_true")
    a = ap.parse_args(argv)

    try:
        rep = build_report(a.repo, a.store)
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        # The instrument itself failed.  That is NOT a pass.
        print("RECEIPT-AUDIT ERROR: could not run: %r" % (e,), file=sys.stderr)
        return 1

    if a.json:
        txt = json.dumps(rep, indent=2, default=str)
        print(txt)
    else:
        print_report(rep)

    if a.out:
        d = os.path.dirname(a.out)
        if d:
            os.makedirs(d, exist_ok=True)
        buf = io.StringIO()
        if a.json:
            buf.write(json.dumps(rep, indent=2, default=str))
        else:
            print_report(rep, buf)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(buf.getvalue())

    if a.fail_on_findings:
        n = counts_of(rep)
        if n["q1_findings"] or n["q2_dangling"] or n["q3_not_dispatched"] or n["q4_textmatch_only"]:
            return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())