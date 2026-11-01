#!/usr/bin/env python
"""O SOTTO NAO MEXE NA FAIXA DE AUDIO -- a metade da "auto dublagem" que e' dele.

O DONO, 2026-10-22 09:35 e 09:52: *"tira a auto dublagem"* (fonte `L146` do corpus).

A medicao completa daquela queixa vive no relay do contrato
(`_main/yt-audio-track.py`, `127.0.0.1:9224`), que le a ABA do proprio video e
pergunta ao player quais faixas existem, qual e' a de omissao e o que
`setAudioTrack` responde. Esse instrumento depende do Chrome dele com a extensao
viva; quando o relay nao esta' la', ele diz `AUDIO_TRACK relay indisponivel` e sai
1 -- uma medicao ausente nao e' uma medicao.

Este ficheiro mede a OUTRA metade, que corre sempre: **o Sotto nao toca na faixa de
audio**. Nao pede, nao escolhe, nao muda e nao desfaz nada de audio -- so' le'
legendas. Se alguem acrescentar `setAudioTrack`/`audioTracks` a' arvore, a dublagem
passa a ser responsabilidade dela e este instrumento fica VERMELHO, que e' o que
obriga a decisao a ser tomada em vez de acontecer por acrescento.

    python _main/yt-no-dub-oracle.py            -> PASS/VERMELHO, rc 0/1
    python _main/yt-no-dub-oracle.py --neg-arm   -> injecta a chamada numa copia e
                                                   exige o VERMELHO (rc 1)

# NO-BUG: instrumento da queixa de 2026-10-22; nao corrige o produto, le' o que ele
# faz com a faixa de audio e prova que nao faz nada.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

#: A populacao do produto que pode chegar ao player. Declarada, nao adivinhada: sao os
#: ficheiros que falam com o YouTube (a legenda) e os que montam a pagina do painel.
POPULATION = (
    'app/webview/youtube_captions.py',
    'app/webview/youtube_reveal.py',
    'app/webview/youtube_window.py',
    'app/webview/sotto_webview.py',
)

#: As API do player que mexem na FAIXA DE AUDIO. Se uma delas aparecer, a dublagem
#: passou a ser responsabilidade desta arvore.
FORBIDDEN = (
    'setAudioTrack',
    'getAudioTrack',
    'audioTracks',
    'audioTrackId',
    'defaultAudioTrackIndex',
    'playerCaptionsTracklistRenderer',
)

rows = []


def add(ok, label, detail=''):
    rows.append((bool(ok), label, str(detail)))


def read(path):
    with io.open(path, encoding='utf-8') as fh:
        return fh.read()


def scan(text):
    hits = []
    for name in FORBIDDEN:
        if name in text:
            for m in re.finditer(re.escape(name), text):
                line = text.count('\n', 0, m.start()) + 1
                hits.append((name, line))
    return hits


def run(population=POPULATION, root=REPO):
    for rel in population:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            add(False, '%s existe' % rel, 'ausente -- a populacao declarada mentiu')
            continue
        hits = scan(read(path))
        add(not hits, '%s nao nomeia a faixa de audio do player' % rel,
            'hits=%r' % (hits[:4],))

    # A SEGUNDA METADE: o pedido de legenda pede a lingua ORIGINAL e nunca uma traducao
    # do audio. `tlang` na URL de legendas e' traducao de LEGENDA (e a politica proibe-a
    # entre en/pt/es -- ver `youtube-captions-oracle.py`); aqui interessa que nao exista
    # nenhum parametro de audio.
    caps = read(os.path.join(root, 'app/webview/youtube_captions.py'))
    add('audioTrack' not in caps and 'dub' not in caps.lower(),
        'o pedido de legenda nao carrega parametro de audio nem de dublagem', 'youtube_captions')

    failed = [r for r in rows if not r[0]]
    for ok, label, detail in rows:
        print('%s %s%s' % ('PASS' if ok else 'FALHA', label,
                           '' if ok else '  <- %s' % detail))
    print('\nYT-NO-DUB %s -- arms=%d pass=%d fail=%d (rc=%d)'
          % ('PASS' if not failed else 'VERMELHO', len(rows),
             len(rows) - len(failed), len(failed), 0 if not failed else 1))
    return 0 if not failed else 1


def neg_arm():
    """Injeta `setAudioTrack` numa COPIA da populacao e exige o VERMELHO."""
    tmp = tempfile.mkdtemp(prefix='ytnodub-neg-')
    try:
        for rel in POPULATION:
            src = os.path.join(REPO, rel)
            dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
        target = os.path.join(tmp, 'app/webview/youtube_captions.py')
        text = io.open(target, encoding='utf-8').read()
        io.open(target, 'w', encoding='utf-8', newline='').write(
            text + "\n\ndef _dublagem(player):\n    return player.setAudioTrack({'id': 'x'})\n")
        global rows
        rows = []
        rc = run(root=tmp)
        if rc != 0:
            print('\nNEG-ARM PASS -- RED as designed: a chamada injectada derruba o oraculo')
            return 1
        print('\nNEG-ARM FALHOU: o oraculo ficou verde com `setAudioTrack` injectado')
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv):
    if '--neg-arm' in argv:
        return neg_arm()
    return run()


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
