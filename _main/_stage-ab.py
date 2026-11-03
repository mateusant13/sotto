import sys, time, json, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'worker'))
import soundfile as sf
import sotto_worker as W

def run(use_vad, label, mem=None):
    if mem is not None:
        os.environ['SOTTO_CUDA_MEM_LIMIT_MB'] = str(mem)
    else:
        os.environ.pop('SOTTO_CUDA_MEM_LIMIT_MB', None)
    md = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      'worker', 'models', 'nemotron-3.5-asr-ptbr-onnx-int4')
    W._add_cuda_dll_dirs()
    provs = os.environ.get('ARM_PROVIDERS') or 'CUDAExecutionProvider,CPUExecutionProvider'
    asr = W.StreamAsr(md, providers=provs.split(','),
                      use_vad=use_vad, lang_id=None)
    pcm, sr = sf.read(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                   'worker', 'assets', 'sample1.flac'), dtype='float32')
    n = 8960
    chunks = [pcm[i:i+n] for i in range(0, len(pcm), n)]
    t0 = time.time()
    for c in chunks:
        asr.run_chunk(c)
    wall = time.time() - t0
    st = {k: round(v, 3) for k, v in asr.stage_s.items()}
    print(json.dumps({'case': label, 'chunks': len(chunks), 'wall': round(wall, 3),
                      'stage_s': st, 'providers': asr.providers}))

run(bool(int(os.environ.get('ARM_VAD', '0'))), 'probe vad=%s' % os.environ.get('ARM_VAD', '0'))
