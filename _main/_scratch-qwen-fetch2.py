#!/usr/bin/env python3
"""SCRATCH fetch #2 -- parameterised by argv, for the ARM 2 candidate.

  py -3 _main/_scratch-qwen-fetch2.py <repo> <subdir-or-.> <dest-dir> <file> [file ...]

Same shape as the first fetcher: stream each file, verify its sha256 (LFS) or git-blob sha1
(non-LFS) against what the Hugging Face API publishes for that revision, write SHA256SUMS.txt.
Deleted after the receipt quotes it.
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path


def log(msg):
    print(msg, flush=True)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha1(path):
    h = hashlib.sha1(b"blob %d\x00" % path.stat().st_size)
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def main():
    repo, subdir, dest_arg = sys.argv[1], sys.argv[2], sys.argv[3]
    files = sys.argv[4:]
    prefix = "" if subdir in (".", "") else subdir.rstrip("/") + "/"
    dest = Path(dest_arg)
    dest.mkdir(parents=True, exist_ok=True)

    with urllib.request.urlopen(
        f"https://huggingface.co/api/models/{repo}/tree/main?recursive=true", timeout=60
    ) as resp:
        tree = json.load(resp)
    meta = {e["path"]: e for e in tree}
    with urllib.request.urlopen(f"https://huggingface.co/api/models/{repo}", timeout=60) as resp:
        revision = json.load(resp).get("sha")
    planned = sum(meta[prefix + f]["size"] for f in files if prefix + f in meta)
    log(f"repo={repo} revision={revision}")
    log(f"planned bytes: {planned:,} B ({planned / 1e6:.1f} MB) over {len(files)} file(s)")

    rows = []
    for name in files:
        key = prefix + name
        entry = meta.get(key)
        if entry is None:
            log(f"MISSING-IN-TREE {key}")
            return 1
        url = f"https://huggingface.co/{repo}/resolve/main/{key}"
        path = dest / name
        if not path.exists() or path.stat().st_size != entry["size"]:
            log(f"GET {key} ({entry['size']:,} B) ...")
            tmp = path.with_suffix(path.suffix + ".part")
            with urllib.request.urlopen(url, timeout=300) as resp, open(tmp, "wb") as out:
                done = 0
                while True:
                    block = resp.read(1 << 22)
                    if not block:
                        break
                    out.write(block)
                    done += len(block)
                    if done % (64 << 20) < (1 << 22):
                        log(f"    {done:,}/{entry['size']:,} B")
            tmp.replace(path)
        else:
            log(f"HAVE {key} ({entry['size']:,} B)")
        size = path.stat().st_size
        digest = sha256_of(path)
        lfs = entry.get("lfs") or {}
        expected = lfs.get("oid")
        verdict = "MATCH" if (expected and digest == expected) else None
        blob = None
        if not expected:
            blob = git_blob_sha1(path)
            verdict = "MATCH(git-blob-sha1)" if blob == entry["oid"] else None
        verdict = verdict or "MISMATCH"
        log(f"{verdict:20s} {key}  size={size:,} (tree says {entry['size']:,})  sha256={digest}")
        if verdict.startswith("MISMATCH") or size != entry["size"]:
            log("VERIFICATION FAILED -- stopping")
            return 2
        rows.append((key, size, digest, blob, verdict))

    total = sum(r[1] for r in rows)
    lines = [f"# provenance for {repo} @ {revision}",
             f"# total {total:,} B ({total / 1e6:.1f} MB) in {len(rows)} file(s)",
             "# columns: size_bytes  sha256  git_blob_sha1(if not LFS)  verdict  path"]
    lines += [f"{r[1]:>12}  {r[2]}  {r[3] or '-':>40}  {r[4]:20}  {r[0]}" for r in rows]
    (dest / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"TOTAL bytes on disk: {total:,} B ({total / 1e6:.1f} MB)")
    log(f"VERDICT: {len(rows)}/{len(rows)} file(s) verified against the HF API published oid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
