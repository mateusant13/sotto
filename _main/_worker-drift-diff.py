"""Name the byte-level drift between two revisions of one file.

Written because `worker/sotto_worker.py` (236 802 B, 16:55:47) is SMALLER than the
pristine copy the denoise lane froze at `_main/denoise-frozen/off/sotto_worker.py`
(242 082 B, 15:28:57), and 82 lines is enough to contain a whole feature. A size
difference is not a diagnosis: this prints the actual hunks.

Usage:  py -3 _main/_worker-drift-diff.py A B [outfile]
Exit:   0 always (the DIFF is the report, not a verdict).
"""
import difflib
import hashlib
import sys


def load(p):
    with open(p, "rb") as fh:
        raw = fh.read()
    return raw, raw.decode("utf-8", "replace").splitlines(keepends=True)


def main(argv):
    if len(argv) < 3:
        print("usage: _worker-drift-diff.py A B [outfile]")
        return 0
    pa, pb = argv[1], argv[2]
    raw_a, a = load(pa)
    raw_b, b = load(pb)
    for tag, p, lines in (("A", pa, a), ("B", pb, b)):
        h = hashlib.sha256(open(p, "rb").read()).hexdigest().upper()
        print(f"{tag} {p}\n  bytes={len(lines and open(p,'rb').read())} lines={len(lines)} sha256={h}")
    print()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    added = removed = 0
    hunks = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        removed += i2 - i1
        added += j2 - j1
        hunks.append((tag, i1, i2, j1, j2))
    print(f"opcodes: {len(hunks)}  lines removed={removed}  lines added={added}")
    print(f"net lines: {len(b) - len(a):+d}   net bytes: {len(raw_b) - len(raw_a):+d}")
    print()
    diff = list(
        difflib.unified_diff(a, b, fromfile=pa, tofile=pb, n=3, lineterm="\n")
    )
    out = argv[3] if len(argv) > 3 else None
    if out:
        with open(out, "w", encoding="utf-8", newline="") as fh:
            fh.writelines(diff)
        print(f"unified diff ({len(diff)} lines) -> {out}")
    else:
        sys.stdout.writelines(diff[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
