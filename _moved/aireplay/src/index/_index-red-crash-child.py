"""Crash-writer child for _index-red-probe.py.

Separate file on purpose: the parent must `taskkill /F` exactly this process and
nothing else, so it needs a PID of its own.

It commits one batch per transaction and appends the committed row count to the
progress note, which is fsync'd so the parent cannot miss a batch it saw as done.
`--override` deliberately breaks the pragmas schema.sql pins, to prove the crash
test is capable of failing (the brief's own controls: journal_mode=OFF gave a
torn 18041 rows; cache_size=50 gave "database disk image is malformed").

SYNTHETIC DATA ONLY: content_key is the SHA-256 of a counter string.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import argparse        # noqa: E402
import hashlib         # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
import store           # noqa: E402

SCRATCH = Path(__file__).parent / "_scratch"

PATCHES = {
    # the two ways the brief says NOT to configure this database
    "journal_off": ("PRAGMA journal_mode = WAL;", "PRAGMA journal_mode = OFF;"),
    "cache_tiny": ("PRAGMA cache_size   = -16000;", "PRAGMA cache_size   = 50;"),
}


def patch_schema(override: str) -> Path:
    sql = store.SCHEMA_PATH.read_text(encoding="utf-8")
    old, new = PATCHES[override]
    if old not in sql:
        raise SystemExit(f"override {override!r}: {old!r} not found in "
                         f"{store.SCHEMA_PATH} -- schema.sql changed shape")
    out = SCRATCH / "_schema_patched_child.sql"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(sql.replace(old, new), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--progress", required=True)
    ap.add_argument("--batches", type=int, default=8)
    ap.add_argument("--rows", type=int, default=2000)
    ap.add_argument("--override", default=None)
    args = ap.parse_args()

    if args.override:
        store.SCHEMA_PATH = patch_schema(args.override)

    conn = store.connect(args.db)
    print(f"journal_mode={store.journal_mode(conn)} "
          f"override={args.override or 'none'}", flush=True)

    progress = Path(args.progress)
    done = 0
    for b in range(args.batches):
        conn.execute("BEGIN")
        for r in range(args.rows):
            i = b * args.rows + r
            ck = hashlib.sha256(f"synthetic://video/{1_000_000 + i}".encode()).hexdigest()
            conn.execute(
                "INSERT INTO video (content_key, path, size_bytes, mtime_ns, state) "
                "VALUES (?,?,?,?,?) ON CONFLICT(content_key) DO UPDATE SET "
                "path=excluded.path",
                (ck, f"synthetic_library/crash_{i}.mp4", 4096,
                 1_700_000_000_000_000_000 + i, "discovered"))
        conn.execute("COMMIT")
        done += args.rows
        with open(progress, "w") as fh:
            fh.write(str(done))
            fh.flush()
            os.fsync(fh.fileno())
        print(f"batch {b + 1} committed, total {done}", flush=True)
        # churn between batches so a kill is likely to land mid-transaction
        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())