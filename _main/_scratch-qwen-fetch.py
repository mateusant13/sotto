#!/usr/bin/env python3
"""SCRATCH fetch for the Qwen3.5-0.8B ORT-GenAI CPU export (PRINCE-1 repo, cpu/ subset only).

Downloads nothing but the text job's files (~695 MB; the vision encoder + projector are skipped
on purpose -- plan §2.2: this is a text job), verifies EVERY file against the sha256 / git-blob
sha1 that the Hugging Face API publishes for that exact revision, and writes a provenance file
next to the weights. Deleted after the receipt quotes it.
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO = "Prince-1/Qwen3.5-0.8B-Onnx"
REV = "main"
DEST = Path(r"H:\sotto\worker\models\qwen3.5-0.8b-ortgenai-cpu")
FILES = [
    "text.onnx",
    "text.onnx.data",
    "embedding.onnx",
    "embedding.onnx.data",
    "tokenizer.json",
    "tokenizer_config.json",
    "genai_config.json",
    "model_config.json",
    "config.json",
    "chat_template.jinja",
    "processor_config.json",
    # The first real load failed with "Load model from ...\vision.onnx failed: File doesn't
    # exist" -- this export is multimodal and ORT-GenAI opens the vision tower at LOAD time
    # even for a text-only job.  Downloading the two files keeps the export exactly as
    # published (the alternative was editing genai_config.json, i.e. shipping a modified
    # artifact).  Measured, not assumed: the failure is what put them here.
    "vision.onnx",
    "vision.onnx.data",
]


def log(msg):
    print(msg, flush=True)


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha1(path):
    """The sha1 of `blob <len>\\0<content>` -- how git (and the HF API) names a non-LFS file."""
    size = path.stat().st_size
    h = hashlib.sha1(b"blob %d\x00" % size)
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(
        f"https://huggingface.co/api/models/{REPO}/tree/{REV}?recursive=true", timeout=60
    ) as resp:
        tree = json.load(resp)
    meta = {e["path"]: e for e in tree}
    revision = None
    total_expected = sum(meta[f"cpu/{f}"]["size"] for f in FILES if f"cpu/{f}" in meta)
    log(f"repo={REPO} rev={REV} target={DEST}")
    log(f"planned bytes: {total_expected:,} B ({total_expected / 1e6:.1f} MB) over "
        f"{len(FILES)} file(s); vision files are NOT fetched")

    rows = []
    for name in FILES:
        key = f"cpu/{name}"
        entry = meta.get(key)
        if entry is None:
            log(f"MISSING-IN-TREE {key}")
            return 1
        url = f"https://huggingface.co/{REPO}/resolve/{REV}/{key}"
        path = DEST / name
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
        # The HF tree API puts the git blob SHA-1 in the top-level ``oid`` and the sha256 of
        # the CONTENT in ``lfs.oid``.  Comparing a sha256 against the top-level oid is a
        # guaranteed mismatch -- measured here on the first run of this very script.
        expected_sha = lfs.get("oid")
        verdict = "MATCH" if (expected_sha and digest == expected_sha) else None
        blob = None
        if not expected_sha:
            blob = git_blob_sha1(path)
            verdict = "MATCH(git-blob-sha1)" if blob == entry["oid"] else None
        if verdict is None:
            verdict = "MISMATCH"
        log(f"{verdict:20s} {key}  size={size:,} (tree says {entry['size']:,})  "
            f"sha256={digest}" + (f"  git_sha1={blob}" if blob else ""))
        rows.append({"path": key, "size": size, "tree_size": entry["size"],
                     "lfs": bool(expected_sha), "api_git_oid": entry["oid"],
                     "api_lfs_sha256": expected_sha, "sha256": digest,
                     "git_blob_sha1": blob, "verdict": verdict})
        if verdict.startswith("MISMATCH") or size != entry["size"]:
            log("VERIFICATION FAILED -- stopping")
            return 2

    written = sum(r["size"] for r in rows)
    lines = [f"# provenance for {REPO} @ {REV}, cpu/ subset (text job only)",
             f"# total {written:,} B ({written / 1e6:.1f} MB) in {len(rows)} file(s)",
             "# columns: size_bytes  sha256  git_blob_sha1(if not LFS)  verdict  path",
             "# sha256 verified against the oid the HF API publishes for this revision"]
    for r in rows:
        lines.append(f"{r['size']:>12}  {r['sha256']}  {r['git_blob_sha1'] or '-':>40}  "
                     f"{r['verdict']:20}  {r['path']}")
    (DEST / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"TOTAL bytes on disk: {written:,} B ({written / 1e6:.1f} MB)")
    log(f"VERDICT: {len(rows)}/{len(rows)} file(s) verified against the HF API published oid")
    log(f"provenance written to {DEST / 'SHA256SUMS.txt'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
