# Research lane probe: which runtimes are installed in THIS interpreter.
# Read-only. Writes nothing. Prints one line per interesting distribution.
import sys, importlib.metadata as md

INTEREST = [
    "onnxruntime", "onnxruntime-genai", "onnxruntime-genai-cuda", "onnxruntime-directml",
    "onnxruntime-gpu", "onnxruntime-openvino", "onnxruntime-qnn", "onnxruntime-vitisai",
    "torch", "torchvision", "torchaudio", "torch-directml",
    "openvino", "openvino-genai", "openvino-tokenizers", "optimum",
    "tensorrt", "tensorrt-llm", "nvidia-tensorrt", "polygraphy", "trtexec",
    "ctranslate2", "faster-whisper", "openai-whisper", "whispercpp", "pywhispercpp",
    "sherpa-onnx", "k2", "funasr", "nemo-toolkit", "nemo_toolkit", "nemo",
    "moondream", "kestrel", "kestrel-kernels", "kestrel-native", "photon",
    "transformers", "optimum-onnx", "onnx", "onnxconverter-common", "onnxscript",
    "numpy", "scipy", "soundfile", "sounddevice", "pyaudio", "pywin32", "pywebview",
    "huggingface-hub", "hf-transfer", "huggingface_hub", "tokenizers", "sentencepiece",
    "mlx", "llama-cpp-python", "llama_cpp_python", "vllm", "exllamav2", "gguf",
    "windows-ai", "winml", "directml", "torch-directml", "ai-edge-litert",
    "mediapipe", "vosk", "speechbrain", "pyannote.audio", "silero-vad", "webrtcvad",
    "onnx2torch", "neural-compressor", "nncf", "accelerate", "datasets", "librosa",
]

found = {}
for d in md.distributions():
    try:
        name = d.metadata["Name"]
    except Exception:
        continue
    if not name:
        continue
    key = name.lower().replace("_", "-")
    found[key] = d.version

print("PYTHON", sys.version.replace("\n", " "), "|", sys.executable)
print("PREFIX", sys.prefix)
print("--- INTEREST (present) ---")
for want in sorted(set(x.lower().replace("_", "-") for x in INTEREST)):
    if want in found:
        print("PRESENT %-28s %s" % (want, found[want]))
print("--- INTEREST (ABSENT) ---")
absent = [w for w in sorted(set(x.lower().replace("_", "-") for x in INTEREST)) if w not in found]
print("ABSENT " + ", ".join(absent))
print("--- TOTAL DISTRIBUTIONS:", len(found))
