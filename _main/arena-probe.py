# Where the ~2 GB really goes, now that CUDA is proven to fall back to CPU:
# (a) ORT default CPU arena vs arena-off, (b) ALL FOUR models the worker loads, as it loads them.
import os, gc, time, io
OUT = r"H:\sotto\_main\arena-probe.log"
log = io.open(OUT,"w",encoding="utf-8")
def p(*a): log.write(" ".join(str(x) for x in a)+"\n"); log.flush()
import psutil
pr = psutil.Process()
def rss(): return pr.memory_info().rss/1048576.0

import onnxruntime as ort
D = r"H:\sotto\worker\models\nemotron-3.5-asr-streaming-0.6b-int4"
enc, dec, joi, vad = (os.path.join(D,f) for f in ("encoder.onnx","decoder.onnx","joint.onnx","silero_vad.onnx"))
p("onnxruntime", ort.__version__)
p(f"RSS baseline: {rss():.1f} MB")

# (a) the arena knob, on the encoder alone
for arena in (True, False):
    gc.collect(); time.sleep(1.0); b = rss()
    so = ort.SessionOptions(); so.enable_cpu_mem_arena = arena
    t0=time.time(); s = ort.InferenceSession(enc, so, providers=["CPUExecutionProvider"]); dt=time.time()-t0
    p(f"encoder  arena={str(arena):<5} load_s={dt:5.2f}  delta={rss()-b:+8.1f} MB  rss={rss():7.1f}")
    del s; gc.collect(); time.sleep(1.0)

# (b) the whole set the worker actually creates
gc.collect(); time.sleep(1.0); b = rss()
p(f"--- all four sessions, as the worker builds them (base {b:.1f} MB) ---")
built=[]
for name, path in (("encoder",enc),("decoder",dec),("joint",joi),("silero_vad",vad)):
    if not os.path.exists(path):
        p(f"{name:<11} MISSING {path}"); continue
    sz = os.path.getsize(path)/1048576
    t0=time.time()
    try:
        s = ort.InferenceSession(path, ort.SessionOptions(), providers=["CPUExecutionProvider"])
        p(f"{name:<11} on_disk={sz:6.3f} MB  load_s={time.time()-t0:5.2f}  total_rss={rss():7.1f} MB  "
          f"in={[i.name for i in s.get_inputs()]}")
        built.append(s)
    except Exception as e:
        p(f"{name:<11} FAILED {type(e).__name__}: {str(e)[:140]}")
p(f"ALL SESSIONS BUILT: peak={rss():.1f} MB for {sum(os.path.getsize(x) for x in (enc,dec,joi,vad) if os.path.exists(x))/1048576:.2f} MB of weights")
p("DONE")
log.close()
