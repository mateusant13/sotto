# LANE 01 - extract the inputs that specs/04-index-search.md must cover.
#
# WHY: AGENTS.md forbids product code before the spec that covers it, and the index
# has NO spec (specs/ holds 01,02,03 only) while docs/research/07-index-search.md is
# the measured design. So the next product step is a SPEC, and this lane hands the
# spec author the raw material instead of making it re-read the lane.
#
# HOUSE RULES HONOURED HERE:
#  - BOTH COLOURS. ARM-0 = the real doc, must be GREEN. ARM-A = a deliberately
#    corrupted COPY in _main\ (the original is never touched) that must go RED.
#    An instrument that cannot say NO is worthless.
#  - A SKIP is not a pass: arm_status is printed per arm, never merged.
#  - Law 8: single-threaded, no drive walk, no artefact above ~200 KB. This script
#    reads ONE 16 KB markdown file and writes ONE small JSON.
#
# Usage:  python _main\_lane01-index-spec-inputs.py
# Exit:   0 = both arms behaved (0 green + 1 red). Non-zero = the ORACLE is broken.

import hashlib
import json
import os
import re
import sys

ROOT = r"H:\sotto\_moved\aireplay"
SRC = os.path.join(ROOT, "docs", "research", "07-index-search.md")
CORRUPT_COPY = os.path.join(ROOT, "_main", "lane01-armA-corrupt.md")
OUT = os.path.join(ROOT, "_main", "lane01-index-spec-inputs.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(path):
    """Pull the things a spec must carry out of a research lane."""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()

    headings = re.findall(r"^(#{1,4})\s+(.*)$", text, flags=re.M)

    # The SQLite schema lives in a ```sql fence, but NOT as `CREATE TABLE` - the
    # lane writes it as a compact grammar: `video(id PK, path, ...)`. MEASURED
    # 2026-10-07 by this oracle's own RED arm: my first version looked for
    # `CREATE TABLE`, found none, and called a lane that HAS a schema schemaless.
    # An instrument that cries wolf on the real input is as broken as one that
    # never says NO.
    fenced = re.findall(r"```sql(.*?)```", text, flags=re.S | re.I)
    schema_block = "\n".join(fenced)
    schema_tables = re.findall(r"(?m)^\s*(\w+)\s*\((?=[^)]*\bPK\b)", schema_block)
    if not schema_tables:
        schema_tables = re.findall(r"(?m)^\s*(\w+)\s*\(", schema_block)
    schema_tables = [t for t in schema_tables if t.lower() not in ("select", "insert", "create")]

    # Every "table-ish" markdown row (| a | b |) that names a column-ish token.
    schema_rows = re.findall(r"^\|\s*`?(\w+)`?\s*\|", text, flags=re.M)

    # Numbers with units are the claims the spec must not silently inherit.
    numbers = re.findall(r"\b\d[\d\s.,]*\s?(?:ms|s\b|MB|MiB|GB|GiB|MiB/s|d|dims?|×|x\b|%|fps)", text)

    unknowns = re.findall(r"(?i)\b(UNKNOWN|UNVERIFIED|not measured|não medid[oa]|TODO|TBD)\b", text)

    # The three provenance channels are a constitutional requirement, not a choice.
    channels = {
        "speech": bool(re.search(r"(?i)\b(speech|transcript|asr)\b", text)),
        "ocr": bool(re.search(r"(?i)\bocr\b", text)),
        "visual": bool(re.search(r"(?i)\b(visual|vision|frame)\b", text)),
    }

    measured_marks = len(re.findall(r"(?i)\b(MEASURED|READ|UNKNOWN)\b", text))
    cited_paths = sorted(set(re.findall(r"`([\w./\\-]+\.(?:md|py|cpp|rs|ps1|cmd))`", text)))

    return {
        "bytes": len(text.encode("utf-8")),
        "heading_count": len(headings),
        "headings": [h[1].strip() for h in headings][:40],
        "create_table_statements": schema_tables,
        "schema_row_tokens": len(set(schema_rows)),
        "numeric_claims": len(numbers),
        "unknown_marks": len(unknowns),
        "provenance_labels_present": measured_marks,
        "cited_paths": cited_paths[:25],
        "channels": channels,
    }


def judge(d):
    """GREEN only if the spec can actually be written from this input."""
    problems = []
    if len(d["create_table_statements"]) < 1:
        problems.append("no SQL schema fence with a table(...) grammar -> the schema is not in this lane")
    if d["unknown_marks"] < 1:
        problems.append("no UNKNOWN/UNVERIFIED marker -> cannot tell claim from measurement")
    if not all(d["channels"].values()):
        missing = [k for k, v in d["channels"].items() if not v]
        problems.append("missing provenance channel(s): " + ",".join(missing))
    if d["numeric_claims"] < 3:
        problems.append("too few numeric claims -> probably not the measured design")
    return ("RED" if problems else "GREEN"), problems


def main():
    if not os.path.isfile(SRC):
        print("FAIL: source lane missing: " + SRC)
        return 2

    src_sha = sha256(SRC)
    with open(SRC, "r", encoding="utf-8", errors="replace") as fh:
        original = fh.read()

    # ---------- ARM-0: the real lane. Must be GREEN. ----------
    arm0 = extract(SRC)
    arm0_status, arm0_problems = judge(arm0)

    # ---------- ARM-A: a CORRUPT COPY. Must be RED. ----------
    # Two independent breaks so the RED cannot be an accident of one bad regex:
    #   1. strip the whole ```sql fence -> the schema is gone;
    #   2. rename the OCR channel -> the three-channel constitution is broken.
    corrupt = re.sub(r"```sql.*?```", "(schema fence removed by ARM-A)", original, flags=re.S)
    corrupt = re.sub(r"(?i)\bocr\b", "ONSCREEN-TEXT-CHANNEL-REMOVED", corrupt)
    with open(CORRUPT_COPY, "w", encoding="utf-8") as fh:
        fh.write(corrupt)
    armA = extract(CORRUPT_COPY)
    armA_status, armA_problems = judge(armA)

    # The original must be byte-identical after the run: we proved we did not
    # mutate the lane we are reading.
    unchanged = sha256(SRC) == src_sha

    report = {
        "lane": "01-index-spec-inputs",
        "source": SRC,
        "source_sha256": src_sha,
        "source_unchanged_by_lane": unchanged,
        "arms": {
            "ARM-0-real": {"status": arm0_status, "problems": arm0_problems, "facts": arm0},
            "ARM-A-corrupt": {"status": armA_status, "problems": armA_problems},
        },
        "oracle_selfcheck": "GREEN only if ARM-0 is GREEN AND ARM-A is RED AND the source is unchanged",
    }
    oracle_ok = (arm0_status == "GREEN" and armA_status == "RED" and unchanged)
    report["oracle_verdict"] = "GREEN" if oracle_ok else "RED"

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    # SKIP is never merged into pass: printed as its own column.
    print("lane=01-index-spec-inputs  source_sha256=" + src_sha[:16])
    print("  ARM-0-real     : " + arm0_status + ("  <- " + "; ".join(arm0_problems) if arm0_problems else ""))
    print("  ARM-A-corrupt  : " + armA_status + ("  <- " + "; ".join(armA_problems) if armA_problems else ""))
    print("  source_unchanged: " + str(unchanged))
    print("  tables_found=" + str(arm0["create_table_statements"]) +
          "  unknown_marks=" + str(arm0["unknown_marks"]) +
          "  numeric_claims=" + str(arm0["numeric_claims"]) +
          "  channels=" + ",".join(k for k, v in arm0["channels"].items() if v))
    print("  ORACLE: " + report["oracle_verdict"] + "  -> " + OUT)

    if not oracle_ok:
        print("ORACLE BROKEN: the arms did not separate. Fix the instrument before trusting it.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())