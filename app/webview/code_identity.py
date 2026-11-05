"""O que ESTE processo carregou -- a etiqueta que o portao da frescura compara.

Nasceu de um erro medido, nao de estetica: o dono carregou Alt+C numa instancia de 01:12:39 e
reclamou que a legenda ligava e desligava; o gesto novo ja' estava no disco. O log da instancia
provava-o -- escrevia `HOTKEY_SINGLE`, uma etiqueta que o fonte ja' nao sabe escrever -- mas so'
quem compara etiquetas a mao o via. Quatro oraculos verdes julgavam FICHEIROS; ele carregava num
PROCESSO.

Saiu de `sotto_webview.py` em 2026-11-01 quando a etiqueta passou a contar tambem os ficheiros da
PAGINA: o shell estava no tecto de bytes do ratchet e um diagnostico nao tem por que' viver dentro
do produto que ele mede. A `_CODE_ID_FILES` e a `_CODE_ID_GLOBS` sao lidas pelo
`_main/live-code-freshness-oracle.py` a partir do modulo do shell, que as re-exporta.

Nunca lanca: uma shell que nao arranca por causa de um numero de diagnostico e' pior do que uma
sem numero.
"""
from __future__ import annotations

import glob as _glob
import hashlib
import os

_CODE_ID_FILES = (
    'sotto_webview.py',
    'hotkey_gesture.py',
    'caption_overlay.py',
    'caption_wrap.py',
    'youtube_captions.py',
    'youtube_reveal.py',
    'youtube_window.py',
)
#: A PAGINA tambem e' codigo, e ate' 2026-11-01 nao entrava na etiqueta. Medido: a cura do
#: custo de animacao mudou `app/panel/panel.css` e `panel.js` (push 3,83 -> 0,72 ms, LoAF
#: 186,7 -> 0) e a `SHELL_CODE_ID` do processo continuou `A21E04974C7F` -- ou seja o dono
#: podia estar a olhar para a UI antiga com o portao da frescura a dizer `FRESH`. As imagens
#: ficam de fora: elas nao decidem comportamento, e somam dezenas de MB.
_CODE_ID_GLOBS = ('../panel/*.js', '../panel/*.css', '../panel/*.html',
                  '../panel/themes/*.css')

#: O WORKER: o outro processo que decide o que o dono ve'. `runs/` fica de fora
#: (sao copias de harness) e `models/` tambem (sao pesos, dezenas de MB).
_CODE_ID_WORKER_GLOBS = ('../../worker/*.py',)


def code_files(here=None, missing=None):
    """A LISTA dos ficheiros que entram na etiqueta. UMA definicao, dois leitores.

    O `code_identity()` (que o PROCESSO escreve ao arrancar) e o
    `_main/live-code-freshness-oracle.py` (que recalcula o DISCO para comparar)
    leem daqui. Enquanto eram duas listas, o portao media outro conjunto -- e um
    portao que mede outro conjunto diz `FRESH` sobre um processo que carregou
    codigo diferente (o caso medido de 2026-11-05: `youtube_cdp_source.py` fora
    das duas).
    """
    here = here or os.path.dirname(os.path.abspath(__file__))
    if missing is None:
        missing = []
    names = list(_CODE_ID_FILES)
    try:
        for _p in sorted(_glob.glob(os.path.join(here, '*.py'))):
            _rel = os.path.basename(_p)
            if _rel not in names:
                names.append(_rel)
    except Exception:  # noqa: BLE001 -- um diagnostico nunca derruba o arranque
        missing.append('*.py')
    page = set()
    for pattern in _CODE_ID_GLOBS:
        try:
            for pth in _glob.glob(os.path.join(here, pattern), recursive=True):
                page.add(os.path.relpath(pth, here))
        except Exception:  # noqa: BLE001
            missing.append(pattern)
    names.extend(sorted(page))
    names.extend(_worker_files(here, missing))
    return names


def _worker_files(here, missing):
    """O WORKER TAMBEM E' CODIGO DA APP, e ate' 2026-11-05 nao entrava na etiqueta.

    Medido: a cura do spool (`worker/live_queue.py` + `worker/engine_policy.py`)
    entrou no disco, a shell correu `--strict` e o portao disse `FRESH` com o
    worker VIVO a correr o codigo anterior -- o PASSO 0 do bug-hunt a mentir sobre
    metade da app. O glob e' o do directorio de producao: `worker/runs/` e
    `worker/runs/*/` sao copias de harness, e as dezenas de MB de `worker/models/`
    nao sao codigo.
    """
    out = []
    for pattern in _CODE_ID_WORKER_GLOBS:
        try:
            for pth in sorted(_glob.glob(os.path.join(here, pattern))):
                out.append(os.path.relpath(pth, here))
        except Exception:  # noqa: BLE001
            missing.append(pattern)
    return out


def code_identity(here=None):
    """`sha256=<12 hex> files=<n> ...` -- o codigo que ESTE processo carregou.

    Nasceu de um erro medido, nao de estetica. O dono carregou Alt+C numa
    instancia de 01:12:39 e reclamou que a legenda ligava e desligava; o gesto
    novo (1 toque = painel de baixo, 2 = direita, HOLD = legenda) ja' estava no
    disco. O log da instancia provava-o -- escrevia `HOTKEY_SINGLE`, uma
    etiqueta que o fonte ja' nao sabe escrever -- mas so' quem compara etiquetas
    a mao o via. Quatro oraculos verdes julgavam FICHEIROS; ele carregava num
    PROCESSO.

    Um unico fio fecha a classe: o processo diz, ao arrancar, o sha256 do que
    carregou, e `_main/live-code-freshness-oracle.py` compara-o com o do disco.

    Nunca lanca: uma shell que nao arranca por causa de um numero de diagnostico
    e' pior do que uma shell sem numero.
    """
    here = here or os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    missing = []
    names = code_files(here, missing)
    for name in names:
        try:
            with open(os.path.join(here, name), 'rb') as fh:
                h.update(fh.read())
        except OSError:
            missing.append(name)
    return 'sha256=%s files=%d%s' % (
        h.hexdigest()[:12].upper(), len(names) - len(missing),
        (' missing=' + ','.join(missing)) if missing else '')
