# Decisive measurement: does int4 cost MORE RAM than int8 because ORT expands the
# 4-bit weights to fp32? One dir per PROCESS (clean base), session build + one real
# inference step. Launched with pythonw -> no console window.
import os, gc, sys, json, time, io

LOG = r"H:\sotto\_main\precision-ram-probe.log"
MODE = os.environ.get("PREC", "")
LOG = LOG if not MODE else LOG.replace(".log", "-%s.log" % MODE)
log = io.open(LOG, "w", encoding="utf-8")
def p(*a):
    log.write(" ".join(str(x) for x in a) + "\n"); log.flush()

import psutil
pr = psutil.Process()
def rss(): return pr.memory_info().rss / 1048576.0

D = r"H:\sotto\worker\models\nemotron-3.5-asr-streaming-0.6b-%s" % (MODE or "int4")

# on-disk truth, headers AND external-data sidecars, separately
tot_hdr = tot_data = 0
for f in sorted(os.listdir(D)):
    fp = os.path.join(D, f); s = os.path.getsize(fp)
    tag = "DATA" if f.endswith(".data") else "hdr "
    if f.endswith(".data"): tot_data += s
    elif f.endswith(".onnx"): tot_hdr += s
    if s > 1000: p("   %-28s %10.3f MB  %s" % (f, s/1048576, tag))
p("PRECISION=%s  headers=%.2f MB  WEIGHTS(.onnx.data)=%.2f MB  total=%.2f MB"
  % (MODE or "int4", tot_hdr/1048576, tot_data/1048576, (tot_hdr+tot_data)/1048576))

import onnxruntime as ort
p("baseline RSS=%.1f MB" % rss())
sessions = {}
for name, fn in (("encoder", "encoder.onnx"), ("decoder", "decoder.onnx"), ("joint", "joint.onnx")):
    fp = os.path.join(D, fn)
    if not os.path.exists(fp): p("%s MISSING" % name); continue
    t0 = time.time()
    try:
        s = ort.InferenceSession(fp, ort.SessionOptions(), providers=["CPUExecutionProvider"])
        sessions[name] = s
        gc.collect(); time.sleep(0.4)
        p("  build %-8s %.2fs  -> RSS %.1f MB" % (name, time.time()-t0, rss()))
    except Exception as e:
        p("  build %-8s FAILED %s: %s" % (name, type(e).__name__, str(e)[:130]))

# one REAL inference on the encoder: audio_signal [+ zeros] and the streaming caches.
enc = sessions.get("encoder")
if enc:
    p("encoder inputs:")
    import numpy as np
    feed = {}
    try:
        for i in enc.get_inputs():
            shp = [d if isinstance(d, int) else 1 for d in i.shape]
            p("   %-24s %s" % (i.name, i.shape))
            if i.type == "tensor(float)":
                feed[i.name] = np.zeros(shp, dtype=np.float32)
            elif i.type == "tensor(int64)":
                feed[i.name] = np.zeros(shp, dtype=np.int64)
        t0 = time.time()
        enc.run(None, feed)
        gc.collect(); time.sleep(0.5)
        p("  INFERENCE ok in %.2fs -> RSS %.1f MB  (PEAK %.1f MB)"
          % (time.time()-t0, rss(), pr.memory_info().peak_wset/1048576))
    except Exception as e:
        p("  INFERENCE FAILED %s: %s" % (type(e).__name__, str(e)[:200]))

p("FINAL RSS=%.1f MB  PEAK=%.1f MB for %.2f MB of on-disk weights"
  % (rss(), pr.memory_info().peak_wset/1048576, (tot_hdr+tot_data)/1048576))
p("DONE")
log.close()
