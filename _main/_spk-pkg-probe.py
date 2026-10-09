import importlib.metadata as md
names = ["sherpa-onnx","torch","torchaudio","pyannote.audio","speechbrain","nemo-toolkit","nemo_toolkit","onnxruntime","onnxruntime-gpu","faster-whisper","librosa","soundfile","silero-vad","kestrel","moondream","transformers","numpy"]
for n in names:
    try:
        print(f"PRESENT {n:20s} {md.version(n)}")
    except Exception as e:
        print(f"ABSENT  {n:20s} ({type(e).__name__})")
