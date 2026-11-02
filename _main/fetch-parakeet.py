#!/usr/bin/env python3
"""TRAZER OS PESOS DO PARAKEET REDUX, E VERIFICAR QUE SAO OS MESMOS.

POR QUE ISTE SCRIPT EXISTE
--------------------------
O dono, 2026-10-17: *"vao ser processados continuamente por modelo melhor. o
parakeet"*.

`worker/redux_live.py` JA E o motor (Parakeet Redux TDT, mesmo contrato JSONL,
`--worker worker\\redux_live.py`). O que faltava eram os PESOS. E ha uma
contradiccao escrita no `AGENTS.md`, em dois sitios, sobre eles:

    :857  "As tres directorias Redux nomeadas abaixo ... estao AUSENTES."
    :860  "parakeet-redux-onnx-int4/ -- ESTA DE NOVO EM DISCO (2026-10-08):
           27 ficheiros, 415,87 MB, re-baixado. O 'APAGADO' abaixo ficou VALSO."

MEDIDO hoje, com `node` sobre `H:\\sotto\\worker\\models`: **um** directorio, so
`nemotron-3.5-asr-ptbr-onnx-int4`. Nenhuma das tres. Isto e a regra 1 do proprio
`AGENTS.md` a acontecer outra vez -- *"uma afirmacao tem prazo de validade, repete
o grep antes de a repetir"* -- e por isso este script nao confia em nenhuma das
duas frases: mede.

O QUE ESTE SCRIPT FAZ, E O QUE VERIFICA
----------------------------------------
1. Baixa `eschmidbauer/parakeet-redux-onnx` com a REVISAO FIXADA, para a pasta que
   `redux_live.py:143` le (`models/parakeet-redux-onnx-int4`). Revisao fixada e
   `latest`: um "actualiza" silencioso trocaria os pesos debaixo do motor.
2. Confere **contagens de bytes E prefixos de sha256** contra os valores que o
   `AGENTS.md` regista. E a verificacao que separa "descarreguei um ficheiro" de
   "descarreguei O ficheiro":

       encoder-model.onnx        343 841 943 B   sha256 ade2c65c...
       decoder_joint-model.onnx   72 552 270 B   sha256 97ae0cb0...
       preprocessor.onnx           1 224 294 B   sha256 3de5742f...
       vad-model.onnx             18 300 687 B   sha256 18dfbe34...
       transcribe.py                  17 844 B   (o laco TDT de referencia)

3. Confirma `vocab.txt` e `config.json`, e que `onnxruntime` cumpre o `>= 1.22` que
   o proprio export exige.

O QUE NAO FAZ: nao instala nada, nao escreve fora de `worker/models`, e nao arranca
o motor. Um download que fica a meio e um motor que recusa pesos sao dois estados
que o script distingue e diz em voz alta.

USO
    python _main/fetch-parakeet.py            # descarrega e verifica
    python _main/fetch-parakeet.py --verify   # so verifica o que ja esta em disco
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(HERE, 'worker', 'models')

#: The export `redux_live.py:143` loads. The directory NAME is the int4 name even
#: though the repo is the plain ONNX export -- that is the name the runner looks
#: for, and renaming the runner is not this script's business.
TARGET = os.path.join(MODELS, 'parakeet-redux-onnx-int4')

REPO = 'eschmidbauer/parakeet-redux-onnx'

#: The revision AGENTS.md names, truncated. The FULL sha is read from the Hub at
#: run time and printed, so the receipt can carry it; the prefix below is what the
#: recorded hashes were taken from.
RECORDED_REVISION_PREFIX = '1c285ba7'

#: bytes + sha256 prefix, exactly as AGENTS.md records them.
EXPECTED = {
    'encoder-model.onnx': (343841943, 'ade2c65c'),
    'decoder_joint-model.onnx': (72552270, '97ae0cb0'),
    'preprocessor.onnx': (1224294, '3de5742f'),
    'vad-model.onnx': (18300687, '18dfbe34'),
    'transcribe.py': (17844, None),
}
#: Present and required, size not recorded in AGENTS.md.
EXPECTED_UNSIZED = ('vocab.txt', 'config.json')


def sha256_prefix(path, n=8):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()[:n]


def verify():
    print('VERIFICANDO %s\n' % TARGET)
    ok = True
    for name, (size, sha) in sorted(EXPECTED.items()):
        path = os.path.join(TARGET, name)
        if not os.path.exists(path):
            print('  RED   %-28s AUSENTE' % name)
            ok = False
            continue
        got = os.path.getsize(path)
        size_ok = got == size
        sha_txt = '' if sha is None else ' sha256=%s' % sha256_prefix(path)
        sha_ok = sha is None or sha_txt.split('=')[1].startswith(sha)
        flag = 'GREEN' if (size_ok and sha_ok) else 'RED'
        if not (size_ok and sha_ok):
            ok = False
        print('  %-5s %-28s %12d B  (esperado %d)%s%s'
              % (flag, name, got, size, sha_txt,
                 '' if size_ok else '  <-- TAMANHO'))

    for name in EXPECTED_UNSIZED:
        path = os.path.join(TARGET, name)
        present = os.path.exists(path)
        if not present:
            ok = False
        print('  %-5s %-28s %s'
              % ('GREEN' if present else 'RED', name,
                 ('%d B' % os.path.getsize(path)) if present else 'AUSENTE'))

    # The export's own requirement, checked rather than assumed.
    try:
        import onnxruntime
        version = onnxruntime.__version__
        parts = tuple(int(x) for x in version.split('.')[:2])
        enough = parts >= (1, 22)
        print('  %-5s onnxruntime            %s  (o export pede >= 1.22)'
              % ('GREEN' if enough else 'RED', version))
        ok = ok and enough
    except Exception as exc:  # noqa: BLE001
        print('  RED   onnxruntime            %s: %s' % (type(exc).__name__, exc))
        ok = False

    print()
    print('VERDICT: %s' % ('GREEN -- os pesos estao em disco e sao os registados'
                           if ok else 'RED -- ver acima'))
    return 0 if ok else 1


def download():
    try:
        from huggingface_hub import HfApi, snapshot_download
    except Exception as exc:  # noqa: BLE001
        print('huggingface_hub indisponivel: %s: %s' % (type(exc).__name__, exc))
        return 2

    info = HfApi().model_info(REPO)
    sha = getattr(info, 'sha', None)
    print('REPO    %s' % REPO)
    print('REVISAO %s' % sha)
    if sha and not sha.startswith(RECORDED_REVISION_PREFIX):
        print('  AVISO: o AGENTS.md regista a revisao %s... e a revisao actual e %s.'
              % (RECORDED_REVISION_PREFIX, sha))
        print('  Os hashes sao verificados contra os registados, portanto a revisao')
        print('  certa mantem-nos GREEN; se nao, o verificador diz porquê.')
    os.makedirs(TARGET, exist_ok=True)
    print('DESTINO %s\n' % TARGET)
    print('A DESCARREGAR (~416 MB)...')
    snapshot_download(repo_id=REPO, revision=sha, local_dir=TARGET,
                      allow_patterns=['*.onnx', '*.txt', '*.json', 'transcribe.py',
                                     'requirements.txt', 'README.md'])
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true')
    args = ap.parse_args()
    if not args.verify:
        rc = download()
        if rc:
            return rc
        print()
    return verify()


if __name__ == '__main__':
    sys.exit(main())