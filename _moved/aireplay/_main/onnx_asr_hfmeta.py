"""Fetch the published sha256 (LFS) / git oid for every file of the istupakov v3-onnx repo."""
import json
from huggingface_hub import HfApi

REPO = "istupakov/parakeet-tdt-0.6b-v3-onnx"
api = HfApi()
info = api.model_info(REPO, files_metadata=True)
print("repo      :", REPO)
print("revision  :", info.sha)
rows = []
for s in info.siblings:
    lfs = getattr(s, "lfs", None)
    rows.append({
        "path": s.rfilename,
        "size": s.size,
        "blob_id": getattr(s, "blob_id", None),
        "lfs_sha256": (lfs or {}).get("sha256"),
        "lfs_size": (lfs or {}).get("size"),
    })
for r in rows:
    print(json.dumps(r))
