"""AS TECLAS DO DONO, num ficheiro: os paineis e a legenda ao vivo.

ORDEM DO DONO, 2026-11-01, verbatim: *"modifica a legenda ao vivo hotkey. bota o
padrao como control espaco. e os painels deixa alt c"*.

PORQUE E' QUE ISTO E' UM FICHEIRO E NAO DUAS CONSTANTES NO CODIGO. A regra
(`hotkey_gesture.py`) tem de continuar PURA e importavel sem I/O: e' ela que o
oraculo executa. As teclas mudam com o gosto do dono, e uma tecla que muda mora
num ficheiro: ele escolhe, o ficheiro guarda, o shell le' no arranque.

TRES PROPRIEDADES QUE SE PAGAM SOZINHAS:

  1. **Um ficheiro estragado nao pode deixar o Sotto sem hotkey.** Tudo o que nao
     se le' volta ao valor de fabrica (`hotkey_gesture.PANELS_ACCELERATOR` /
     `LIVE_ACCELERATOR`) e o motivo vai para o log. Uma app que recusa o gesto
     por causa de um JSON mal formado e' pior do que uma app com a tecla de
     fabrica.
  2. **A leitura e' cacheada por `mtime`**, e nao por processo: o oraculo
     reescreve o ficheiro e le'-o a seguir, no mesmo processo, e uma cache sem
     `mtime` devolver-lhe-ia o valor anterior.
  3. **A escrita e' atomica** (`panel_state.write_atomic`), para o dono nunca
     apanhar um ficheiro a meio.

O TEXTO GRAVADO E' SEMPRE O CANONICO (`normalise_accelerator`): o parser e' o
MESMO que o shell usa para registar a tecla, por isso um valor que se le' daqui e'
um valor que `RegisterHotKey` aceita -- nao ha duas tabelas de teclas.
"""
from __future__ import annotations

import json
import os

import hotkey_gesture

#: O ficheiro do estado. Ao lado dos outros estados mutaveis do repo
#: (`_main/panel-state.json`), e nao em `%APPDATA%`: os instrumentos deste repo
#: leem o estado de `_main/`, e um segundo sitio seria uma segunda verdade.
PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    '_main', 'hotkey-settings.json')

#: A chave de cada tecla no ficheiro. Uma tecla, um nome curto.
PANELS_KEY = 'panels'
LIVE_KEY = 'live'

#: A fabrica, uma vez: vive em `hotkey_gesture` e nao se repete aqui.
DEFAULTS = {PANELS_KEY: hotkey_gesture.PANELS_ACCELERATOR,
            LIVE_KEY: hotkey_gesture.LIVE_ACCELERATOR}


def _read_payload(path=None):
    path = path or PATH
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


#: `(mtime, accelerators)` ou None. Ver a propriedade 2 na docstring do modulo.
_CACHE = {'stamp': None, 'value': None}


def accelerators(path=None):
    """`{'panels': 'Alt+C', 'live': 'Ctrl+Space'}` -- o que esta' EM VIGOR.

    Uma tecla que nao esta' no ficheiro, ou que o parser recusa, cai na fabrica
    SOZINHA: um ficheiro com a tecla dos paineis estragada nao pode levar a tecla
    da legenda com ela.
    """
    path = path or PATH
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        return dict(DEFAULTS)
    if _CACHE['stamp'] == stamp and _CACHE['value'] is not None:
        return dict(_CACHE['value'])
    payload = _read_payload(path) or {}
    value = {}
    for key, default in DEFAULTS.items():
        try:
            value[key] = hotkey_gesture.normalise_accelerator(payload.get(key) or default)
        except (TypeError, ValueError):
            value[key] = hotkey_gesture.normalise_accelerator(default)
    _CACHE['stamp'] = stamp
    _CACHE['value'] = dict(value)
    return value


def write(payload, path=None):
    """Guarda as teclas e devolve `{'ok', 'panels', 'live', 'error'}`. Nunca levanta.

    A recusa e' explicita e NAO muda o ficheiro: um pedido com uma tecla que o
    parser nao aceita nao pode apagar a escolha anterior do dono. Um pedido que
    traz SO' uma das teclas mantem a outra como esta' (a que esta' em vigor).
    """
    path = path or PATH
    payload = payload or {}
    current = accelerators(path)
    result = dict(current)
    for key in DEFAULTS:
        if key not in payload:
            continue
        try:
            result[key] = hotkey_gesture.normalise_accelerator(payload.get(key))
        except (TypeError, ValueError) as exc:
            return {'ok': False, 'error': f'{key}: {exc}', 'panels': current[PANELS_KEY],
                    'live': current[LIVE_KEY]}
    try:
        import panel_state
        panel_state.write_atomic(path, dict(result))
    except Exception as exc:  # noqa: BLE001 -- uma escrita falhada e' um recado
        return {'ok': False, 'error': repr(exc), 'panels': current[PANELS_KEY],
                'live': current[LIVE_KEY]}
    _CACHE['stamp'] = None
    _CACHE['value'] = None
    return {'ok': True, 'panels': result[PANELS_KEY], 'live': result[LIVE_KEY],
            'error': None}
