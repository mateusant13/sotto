#!/usr/bin/env python3
"""TRAZER OS PESOS DO NEMOTRON (O MOTOR AO VIVO), E VERIFICAR QUE SAO OS MESMOS.

POR QUE ISTE SCRIPT EXISTE
--------------------------
A 2026-11-01 16:28 o `worker/models/` foi esvaziado e o motor AO VIVO parou de carregar
(`model dir not found`); a 2026-11-02 a lane repôs o ficheiro a mao, de uma revisao do Hub que
tinha de ser procurada em `onnx-community/` (a busca por `nvidia/` nao a mostra). Um artefacto
que ja' desapareceu uma vez nao se repoe por memoria: repoe-se por um comando, e o comando
prova que o que chegou e' o registado.

O QUE ESTE SCRIPT FAZ, E O QUE VERIFICA
---------------------------------------
1. Baixa `onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4` com a REVISAO FIXADA para a
   pasta que `worker/config.json` nomeia (`models/nemotron-3.5-asr-ptbr-onnx-int4`). Revisao
   fixada e nao `latest`: um "actualiza" silencioso trocaria os pesos debaixo do motor ao vivo.
2. Confere o TAMANHO de cada ficheiro grafico e o layout ORT GenAI completo.
3. Le os TRES numeros normativos do proprio `genai_config.json` e exige os que
   `docs/model-specs/README.md` fixa: `blank_id=13087`, `chunk_samples=8960`,
   `max_symbols_per_step=10`. Um export com outra janela decodifica com outro contrato, e essa
   diferenca tem de ser dita em voz alta, nao descoberta no ecra do dono.

O QUE NAO FAZ: nao instala nada, nao escreve fora de `worker/models`, e nao arranca o motor.

USO
    python _main/fetch-nemotron.py            # descarrega e verifica
    python _main/fetch-nemotron.py --verify   # so verifica o que ja esta em disco
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(HERE, 'worker', 'models')

#: The directory `worker/config.json` names (`model.dir`). It is a directory NAME, and the
#: `ptbr` in it predates the published multilingual export: renaming the runner's target is not
#: this script's business.
TARGET = os.path.join(MODELS, 'nemotron-3.5-asr-ptbr-onnx-int4')

REPO = 'onnx-community/nemotron-3.5-asr-streaming-0.6b-onnx-int4'

#: MEASURED 2026-11-02: the revision the restored copy came from. Recorded so a future run says
#: out loud when the Hub has moved on, instead of silently downloading a different quantisation.
RECORDED_REVISION = '8364d9e2dd9da23789b480bdbba9e423717e42ee'

#: bytes, measured on the restored copy 2026-11-02 (788 069 519 B in 16 files).
EXPECTED = {
    'encoder.onnx': 2677548,
    'encoder.onnx.data': 690089984,
    'decoder.onnx': 4696,
    'decoder.onnx.data': 59785216,
    'joint.onnx': 2136,
    'joint.onnx.data': 37830656,
    'silero_vad.onnx': 2243022,
}
EXPECTED_PRESENT = ('genai_config.json', 'audio_processor_config.json', 'model_config.json',
                    'tokenizer.json', 'tokenizer_config.json', 'vocab.txt')

#: `docs/model-specs/README.md` calls these normative; the decoder contract is written against
#: them and `_main/model-spec-oracle.py` compares them with `worker/config.json`.
NORMATIVE = {'blank_id': 13087, 'chunk_samples': 8960, 'max_symbols_per_step': 10}


def verify(target=None):
    target = target or TARGET
    print('VERIFICANDO %s\n' % target)
    ok = True
    for name, size in sorted(EXPECTED.items()):
        path = os.path.join(target, name)
        if not os.path.exists(path):
            print('  RED   %-24s AUSENTE' % name)
            ok = False
            continue
        got = os.path.getsize(path)
        if got != size:
            ok = False
        print('  %-5s %-24s %12d B  (esperado %d)%s'
              % ('GREEN' if got == size else 'RED', name, got, size,
                 '' if got == size else '  <-- TAMANHO'))

    for name in EXPECTED_PRESENT:
        present = os.path.exists(os.path.join(target, name))
        ok = ok and present
        print('  %-5s %-24s %s' % ('GREEN' if present else 'RED', name,
                                   'presente' if present else 'AUSENTE'))

    cfg_path = os.path.join(target, 'genai_config.json')
    if os.path.exists(cfg_path):
        model = json.load(open(cfg_path, encoding='utf-8'))['model']
        for key, want in NORMATIVE.items():
            got = model.get(key)
            same = got == want
            ok = ok and same
            print('  %-5s %-24s %s  (normativo %s)%s'
                  % ('GREEN' if same else 'RED', key, got, want,
                     '' if same else '  <-- CONTRATO DIFERENTE'))
        print('  ----  left_context             %s' % model.get('left_context'))

    print()
    print('VERDICT: %s' % ('GREEN -- o motor AO VIVO tem os pesos e o contrato normativo'
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
    if sha and sha != RECORDED_REVISION:
        print('  AVISO: a revisao registada e %s. O que chegar e verificado pelo tamanho e pelo')
        print('  contrato; se mudar, o VERDICT diz porque.')
    os.makedirs(TARGET, exist_ok=True)
    print('DESTINO %s\n' % TARGET)
    print('A DESCARREGAR (~788 MB)...')
    # The pinned revision, not the moving head: the live engine must load the weights this
    # script verified, not whatever the Hub published this morning.
    snapshot_download(repo_id=REPO, revision=RECORDED_REVISION, local_dir=TARGET)
    return 0


def neg_arm():
    """Prova o VERIFICADOR: muta um numero normativo numa COPIA e exige o RED.

    O braco negativo nunca toca no ficheiro vivo. Sem esta arm, `verify()` podia estar a
    comparar uma coisa com ela propria e publicar GREEN para sempre -- e' o defeito que ja'
    custou caro neste repo (um detector sem controle nao e' um detector).
    """
    import shutil
    import tempfile

    cfg_src = os.path.join(TARGET, 'genai_config.json')
    if not os.path.exists(cfg_src):
        print('NEG-ARM IMPOSSIVEL -- nao ha genai_config.json em %s' % TARGET)
        return 2
    base = os.environ.get('TMPDIR') or tempfile.gettempdir()
    work = tempfile.mkdtemp(prefix='nemotron-neg-', dir=base)
    try:
        for name in list(EXPECTED) + list(EXPECTED_PRESENT):
            src = os.path.join(TARGET, name)
            if os.path.exists(src):
                dst = os.path.join(work, name)
                if os.path.getsize(src) > 1 << 20:
                    # The graphs are only ever size-checked; a sparse stand-in of the same
                    # length keeps the control cheap without lying about anything it reads.
                    with open(dst, 'wb') as fh:
                        fh.truncate(os.path.getsize(src))
                else:
                    shutil.copy2(src, dst)
        cfg = json.load(open(os.path.join(work, 'genai_config.json'), encoding='utf-8'))
        cfg['model']['chunk_samples'] = cfg['model'].get('chunk_samples', 8960) + 1
        json.dump(cfg, open(os.path.join(work, 'genai_config.json'), 'w', encoding='utf-8'))
        print('NEG-ARM: chunk_samples mutado em +1 numa COPIA (%s)\n' % work)
        rc = verify(work)
        print()
        print('NEG-ARM: %s' % ('PASS -- a mutacao do contrato derruba o verificador'
                               if rc != 0 else 'FAIL -- o verificador aceitou um contrato mutado'))
        # O CONTRATO DO `:expectred` DA BATERIA: um braco negativo que ACHOU o defeito sai 1, tal
        # como os irmaos -- a bateria exige rc=1 E a frase no log. Um braco que nao achou sai 0,
        # que e' rc diferente de 1 e portanto tambem reprova.
        return 1 if rc != 0 else 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--neg-arm', action='store_true',
                    help='muta um numero normativo numa copia e exige o RED')
    args = ap.parse_args()
    if args.neg_arm:
        return neg_arm()
    if not args.verify:
        rc = download()
        if rc:
            return rc
        print()
    return verify()


if __name__ == '__main__':
    sys.exit(main())
