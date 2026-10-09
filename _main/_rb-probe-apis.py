# Research lane probe: API surface of the runtimes installed here, and the graph
# inputs of the models on disk. Loads NO weights (graph headers only).
import sys, os, json, inspect

print("=" * 70)
print("SHERPA-ONNX")
print("=" * 70)
try:
    import sherpa_onnx
    print("VERSION", getattr(sherpa_onnx, "__version__", "?"))
    print("FILE", sherpa_onnx.__file__)
    on = [m for m in dir(sherpa_onnx.OnlineRecognizer) if m.startswith("from_")]
    off = [m for m in dir(sherpa_onnx.OfflineRecognizer) if m.startswith("from_")]
    print("OnlineRecognizer factories :", on)
    print("OfflineRecognizer factories:", off)
    for name in ("from_transducer", "from_nemo_transducer", "from_nemo_ctc", "from_paraformer",
                 "from_whisper", "from_sense_voice", "from_moonshine", "from_fire_red_asr",
                 "from_zipformer2_ctc", "from_wenet_ctc", "from_dolphin_ctc", "from_telespeech_ctc"):
        for cls, label in ((sherpa_onnx.OnlineRecognizer, "ONLINE"), (sherpa_onnx.OfflineRecognizer, "OFFLINE")):
            f = getattr(cls, name, None)
            if f is not None:
                try:
                    sig = str(inspect.signature(f))
                except Exception as e:
                    sig = "<no sig: %s>" % e
                print("%-7s %-22s %s" % (label, name, sig[:700]))
    print("OnlineTransducerModelConfig fields:",
          [a for a in dir(sherpa_onnx.OnlineTransducerModelConfig) if not a.startswith("_")])
    print("OfflineTransducerModelConfig fields:",
          [a for a in dir(sherpa_onnx.OfflineTransducerModelConfig) if not a.startswith("_")])
    # does the transducer config carry a model_type / prompt knob?
    for cfg in ("OnlineTransducerModelConfig", "OfflineTransducerModelConfig", "FeatureConfig"):
        c = getattr(sherpa_onnx, cfg, None)
        if c is None:
            continue
        try:
            print(cfg, "init sig:", str(inspect.signature(c.__init__))[:900])
        except Exception as e:
            print(cfg, "sig unavailable", e)
    # CUDA presence in the wheel
    import glob
    d = os.path.dirname(sherpa_onnx.__file__)
    print("WHEEL FILES (top):", sorted(os.listdir(d))[:20])
    for pat in ("*cuda*", "*.dll", "*.pyd"):
        hits = glob.glob(os.path.join(d, "**", pat), recursive=True)
        print("GLOB %-8s -> %d hit(s)" % (pat, len(hits)), [os.path.basename(h) for h in hits[:6]])
except Exception as e:
    import traceback; traceback.print_exc()

print()
print("=" * 70)
print("ONNXRUNTIME-GENAI")
print("=" * 70)
try:
    import onnxruntime_genai as og
    print("VERSION", og.__version__, "| FILE", og.__file__)
    names = [n for n in dir(og) if not n.startswith("_")]
    print("PUBLIC NAMES:", names)
    for n in ("StreamingProcessor", "AsrProcessor", "MultiModalProcessor", "Tokenizer", "Model", "Config",
              "Generator", "GeneratorParams", "Images", "Audios", "is_cuda_available", "set_logger"):
        o = getattr(og, n, None)
        print("  %-22s %s" % (n, "PRESENT" if o is not None else "ABSENT"))
    print("is_cuda_available() ->", og.is_cuda_available())
except Exception as e:
    import traceback; traceback.print_exc()

print()
print("=" * 70)
print("MODEL GRAPH HEADERS (inputs/outputs), no external data loaded")
print("=" * 70)
import onnx
MODELS = [
    r"H:\sotto\worker\models\nemotron-3.5-asr-streaming-0.6b-int8\encoder.onnx",
    r"H:\sotto\worker\models\nemotron-3.5-asr-streaming-0.6b-int8\decoder.onnx",
    r"H:\sotto\worker\models\nemotron-3.5-asr-streaming-0.6b-int8\joint.onnx",
    r"H:\VOD.RIP-models\parakeet-models\sherpa-onnx-nemo-parakeet-redux\encoder.onnx",
    r"H:\VOD.RIP-models\parakeet-models\sherpa-onnx-nemo-parakeet-redux\decoder.onnx",
    r"H:\VOD.RIP-models\parakeet-models\sherpa-onnx-nemo-parakeet-redux\joiner.onnx",
    r"H:\VOD.RIP-models\parakeet-models\sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8\encoder.int8.onnx",
    r"H:\VOD.RIP-models\parakeet-models\sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8\joiner.int8.onnx",
    r"H:\aireplay\models\parakeet-tdt-0.6b-v3-onnx\encoder-model.int8.onnx",
]
for p in MODELS:
    if not os.path.exists(p):
        print("MISSING", p); continue
    try:
        m = onnx.load(p, load_external_data=False)
        g = m.graph
        print("----", p.replace("H:\\", ""), "| ir=%s opset=%s" % (
            m.ir_version, [(o.domain or "ai.onnx", o.version) for o in m.opset_import]))
        for i in g.input:
            print("     IN ", i.name, [ (d.dim_value or d.dim_param) for d in i.type.tensor_type.shape.dim])
        for o in g.output:
            print("     OUT", o.name, [ (d.dim_value or d.dim_param) for d in o.type.tensor_type.shape.dim])
    except Exception as e:
        print("LOAD FAILED", p, type(e).__name__, str(e)[:200])
