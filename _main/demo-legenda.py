"""A DEMO que o dono nunca viu: a legenda ao VIVA, com o pipeline inteiro.

O que este script prova, e o que nunca foi provado nesta maquina:
  1. um ficheiro de audio REAL (o sample pt-BR) entra pelo cabo virtual;
  2. o worker TAPA esse cabo, em modo vivo (a escada de dispositivos, a
     mesma que a app usa);
  3. o worker TRANSCRREVE e escreve a legenda em JSONL no stdout;
  4. a legenda chega ao shell -- que e' o que a mostra no overlay.

A rota e' a MEDIDA (AGENTS.md): render para "CABLE Input", captura no
"CABLE Output"/loopback do CABLE Input. NUNCA para o default output do
sistema -- esse e' a altifalante do dono, e o proprio probe tem uma
REFUSAL para isso (SOTTO_ALLOW_AUDIBLE=1). Aqui a recusa e' a mesma,
inalteravel, e compara o endpoint de RENDER ESCOLHIDO com o default do
sistema -- como o inject-all-probe faz -- e nao o default com o nome do
render (o que recusaria uma renderizacao inofensiva).

O worker e' launched por mim (o Lead) e morto por pid, no fim.
"""
import json
import os
import subprocess
import sys
import threading
import time

import numpy as np
import sounddevice as sd
import soundfile as sf

REPO = r'H:\sotto'
SRC = os.path.join(REPO, '_main', 'pt-br-sample.wav')
RENDER_NAME = 'CABLE Input'          # a entrada do cabo: o audio sai em CABLE Output
SECONDS = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0
OUT = r'I:\cc-tmp\demo-legenda.json'
PY = r'C:\Program Files\Python311\python.exe'


def default_output_index():
    """O indice do endpoint de saida DEFAULT do sistema.

    `sd.query_devices(kind='output')` devolve um DICT (indice -> device), nao
    uma lista -- a iteracao directa dá strings e rebenta. O default
    canonico e' `sd.default.device[1]`.
    """
    try:
        idx = sd.default.device[1]
    except Exception:
        return None
    if idx is None:
        return None
    try:
        d = sd.query_devices(int(idx))
    except Exception:
        return None
    if d.get('max_output_channels', 0) <= 0:
        return None
    return int(idx)


def find_render():
    for d in sd.query_devices():
        if d['max_output_channels'] > 0 and RENDER_NAME.lower() in d['name'].lower():
            return d
    return None


def main():
    dev = find_render()
    if dev is None:
        print(json.dumps({'error': 'no render endpoint named %r' % RENDER_NAME}), flush=True)
        return 2

    # HARD REFUSAL, a mesma do inject-all-probe: se o endpoint que vamos
    # renderizar for o DEFAULT do sistema, o som sai nos altifalantes do dono.
    dflt = default_output_index()
    if dflt is not None and dev['index'] == dflt and os.environ.get('SOTTO_ALLOW_AUDIBLE') != '1':
        print(json.dumps({'refused': 'AUDIBLE-DEVICE', 'device': dev['name'],
                          'why': 'o endpoint de render e o default do sistema = a saida do dono'}),
              flush=True)
        return 4

    stop = threading.Event()
    pcm, rate = sf.read(SRC, dtype='float32', always_2d=True)
    target = int(dev['default_samplerate'])
    if rate != target:
        n = int(len(pcm) * target / rate)
        idx = np.linspace(0, len(pcm) - 1, n)
        pcm = np.stack([np.interp(idx, np.arange(len(pcm)), pcm[:, c])
                        for c in range(pcm.shape[1])], axis=1)
    ch = min(int(dev['max_output_channels']) or 2, pcm.shape[1])
    pcm = np.ascontiguousarray(pcm[:, :ch], dtype='float32')

    def render_thread():
        print('render: %s -> %r  %d Hz  %d ch  (loop)' % (os.path.basename(SRC),
                                                         dev['name'], target, ch), flush=True)
        with sd.OutputStream(device=dev['index'], samplerate=target, channels=ch,
                             dtype='float32') as out:
            while not stop.is_set():
                out.write(pcm)

    th = threading.Thread(target=render_thread, daemon=True)
    th.start()
    time.sleep(1.0)

    cmd = [PY, os.path.join(REPO, 'worker', 'sotto_worker.py')]
    print('worker:', ' '.join(cmd), flush=True)
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=REPO, env=env, text=True, encoding='utf-8',
                            errors='replace', creationflags=0x08000000)
    captions = []
    statuses = []

    def pump(stream, sink, tag):
        for line in stream:
            line = line.rstrip()
            if not line:
                continue
            if tag == 'out':
                try:
                    obj = json.loads(line)
                except ValueError:
                    continue
                if obj.get('type') == 'caption':
                    sink.append(obj)
                    print('>>> LEGENDA: %r' % obj.get('text'), flush=True)
                else:
                    statuses.append(obj)
                    print('    [%s] %s' % (obj.get('type', '?'),
                                          json.dumps(obj, ensure_ascii=False)[:220]),
                          flush=True)
            else:
                print('    err| %s' % line[:220], flush=True)

    t_out = threading.Thread(target=pump, args=(proc.stdout, captions, 'out'), daemon=True)
    t_err = threading.Thread(target=pump, args=(proc.stderr, statuses, 'err'), daemon=True)
    t_out.start()
    t_err.start()

    t0 = time.time()
    while time.time() - t0 < SECONDS and proc.poll() is None:
        time.sleep(0.5)
    stop.set()
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(10)
        except subprocess.TimeoutExpired:
            proc.kill()
    time.sleep(0.5)

    receipt = {
        'demo': 'legenda ao viva, pipeline real',
        'source': SRC,
        'render': dev['name'],
        'render_api': sd.query_hostapis(dev['hostapi'])['name'],
        'render_is_system_default': (dflt is not None and dev['index'] == dflt),
        'seconds': round(time.time() - t0, 1),
        'worker_rc': proc.returncode,
        'n_captions': len(captions),
        'captions': captions,
        'statuses': statuses[-14:],
    }
    with open(OUT, 'w', encoding='utf-8') as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=2)
    print('\n=== RESUMO: %d legenda(s) em %.1fs  (rc=%s) -> %s'
          % (len(captions), receipt['seconds'], proc.returncode, OUT), flush=True)
    for c in captions:
        print('   %r' % c.get('text'))
    return 0 if captions else 1


if __name__ == '__main__':
    sys.exit(main())
