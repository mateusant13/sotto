---
license: cc-by-nc-4.0
license_link: https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-ASR-Streaming-Multilingual-0.6b/blob/main/LICENSE
language:
- multilingual
- ru
- en
- de
- fr
- es
- zh
- ja
- ko
- ar
- hi
- pt
- it
- nl
- pl
- tr
- uk
- vi
- th
pipeline_tag: automatic-speech-recognition
tags:
- nemotron
- onnx
- int8
- onnxruntime-genai
- speech-recognition
- streaming-asr
- k-quant
- olive
- cpu
---

# Nemotron 3.5 ASR Streaming 0.6B — ONNX INT8 (CPU, 0.56s chunks)

INT8 k-quant quantized ONNX model converted from [NVIDIA Nemotron 3.5 ASR Streaming 0.6B](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-ASR-Streaming-Multilingual-0.6b) using Microsoft Olive.

Optimized for **fast CPU inference** with [ONNX Runtime GenAI](https://github.com/microsoft/onnxruntime-genai). Uses NVIDIA's recommended 0.56s chunk size for best latency/accuracy trade-off.

## Model Details

| Property | Value |
|----------|-------|
| Base model | NVIDIA Nemotron 3.5 ASR Streaming 0.6B |
| Encoder layers | 24 |
| Hidden size | 1024 |
| Quantization | INT8 k-quant (block_size=32, accuracy_level=4) |
| Chunk size | **0.56s** (8,960 samples @ 16kHz) |
| Sample rate | 16,000 Hz |
| Vocab size | 13,088 |
| Languages | 80+ (multilingual) |
| VAD | Silero VAD included |
| Total size | ~1,021 MB |

## Quick Start

### C# / .NET (onnxruntime-genai)

```csharp
using NemotronSpeech;

using var session = new ModelSession(
    modelPath: "DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu",
    executionProvider: "cpu",
    langId: "11",  // Russian
    useVad: true
);
```

### Python (onnxruntime-genai)

```python
import onnxruntime_genai as og
import numpy as np

model = og.Model("DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu")
processor = og.StreamingProcessor(model)
tokenizer = og.Tokenizer(model)
params = og.GeneratorParams(model)
generator = og.Generator(model, params)

generator.set_runtime_option("lang_id", "11")  # Russian

chunk = np.zeros(8960, dtype=np.float32)  # 0.56s @ 16kHz
inputs = processor.process(chunk)
if inputs is not None:
    generator.set_inputs(inputs)
    while not generator.is_done():
        generator.generate_next_token()
```

## Conversion Recipe

```bash
cd converter
python src/optimize.py \
  --model-name nemotron-3.5-asr-streaming-0.6b.nemo \
  --encoder-precision int8 \
  --execution-provider cpu \
  --output-dir build/onnx_models_int8_cpu
```

See [nemotron-speech-csharp](https://github.com/DimQ1/nemotron-speech-csharp) for the full C# demo app with VoiceType WPF UI.

## Files

| File | Size |
|------|------|
| `encoder.onnx` + `.data` | 922 MB |
| `decoder.onnx` + `.data` | 57 MB |
| `joint.onnx` + `.data` | 36 MB |
| `silero_vad.onnx` | 2.1 MB |
| `tokenizer.json` | 0.7 MB |

## Available Variants

| Model | Precision | Encoder | Total | Quality |
|-------|-----------|---------|-------|---------|
| [FP32](https://huggingface.co/DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-fp32-cpu) | FP32 | 2,380 MB | 2,479 MB | ⭐ Best |
| [INT8](https://huggingface.co/DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int8-cpu) | INT8 k-quant | 922 MB | **1,021 MB** | Good |
| [INT4](https://huggingface.co/DimQ1/nemotron-3.5-asr-streaming-0.6b-onnx-int4-cpu) | INT4 k-quant | 658 MB | 757 MB | ⚡ Fastest |

## License

This model inherits [cc-by-nc-4.0](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-ASR-Streaming-Multilingual-0.6b/blob/main/LICENSE) from the base NVIDIA Nemotron model.
