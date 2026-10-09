"""Quantify how wrong the regressed search is, with brute-force ground truth.

Runs the SAME code path the gate measures, then checks the top fused hit
against a brute-force cosine ranking. Reports recall@1 and recall@10.
"""
import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS"):
    os.environ[_v] = "2"

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
PROBE = REPO / "_moved" / "aireplay" / "_main" / "slice_scale_probe.py"
sys.path.insert(0, str(REPO / "_moved" / "aireplay" / "src" / "index"))

_spec = importlib.util.spec_from_file_location("slice_scale_probe", PROBE)
probe = importlib.util.module_from_spec(_spec)
sys.modules["slice_scale_probe"] = probe
_spec.loader.exec_module(probe)

import numpy as np  # noqa: E402
import store  # noqa: E402
import tempfile  # noqa: E402
import search  # noqa: E402

store.set_thread_budget(2)

N = 5000
NQ = 100
DIM = probe.DIM
CHANNEL = "visual"

rng = np.random.default_rng(probe.SEED)
tmp = tempfile.mkdtemp(prefix="recall-")
conn = store.connect(pathlib.Path(tmp) / "scratch.sqlite")
vid = store.upsert_video(
    conn, content_key=rng.bytes(32).hex(), path="/synthetic/x.mp4",
    size_bytes=1, mtime_ns=1_760_000_000_000_000_000, duration_ms=60000,
    codec="synthetic", w=1920, h=1080, fps=25.0)
conn.execute("BEGIN")
seg_ids = []
for i in range(N):
    seg_ids.append(store.upsert_segment(conn, video_id=vid, start_ms=i * 5000,
                                        end_ms=(i + 1) * 5000, n_visual=1))
conn.execute("COMMIT")
CH = 4096
for s in range(0, N, CH):
    m = min(CH, N - s)
    vecs = rng.standard_normal((m, DIM)).astype(np.float32)
    store.upsert_embeddings(
        conn, [(seg_ids[s + j], CHANNEL, vecs[j]) for j in range(m)],
        model=probe.MODEL, dtype="fp32", dim=DIM)

idx = search.SearchIndex(conn)
qrng = np.random.default_rng(probe.SEED + 1)

# the query vector IS a stored vector, so its true nearest neighbour by cosine
# is itself (cosine 1.0) -- exact ground truth, no labels needed.
hit1 = hit10 = 0
for _ in range(NQ):
    qi = int(qrng.integers(0, idx.n))
    q = idx.vecs[qi]
    hits = idx.search(q, k=10)
    got = [int(h["seg_id"]) for h in hits]
    truth = int(idx.seg_ids[qi])
    if got[:1] == [truth]:
        hit1 += 1
    if truth in got:
        hit10 += 1

print(f"QUERIES         : {NQ}")
print(f"recall@1        : {hit1}/{NQ} = {hit1 / NQ * 100:.1f}%")
print(f"recall@10       : {hit10}/{NQ} = {hit10 / NQ * 100:.1f}%")
conn.close()
sys.exit(0 if hit10 == NQ else 1)