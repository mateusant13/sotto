"""O LIMIAR DO HOLD DO ALT+C, configuravel pelo painel direito.

ORDEM DO DONO, 2026-10-30: o `HOLD` do Alt+C liga/desliga a legenda ao vivo, e o
tempo a partir do qual um Alt+C e' um HOLD tem de poder ser escolhido **no painel
da direita** -- nao fixo no codigo, a espera de um rebuild.

PORQUE E' QUE ISTO E' UM FICHEIRO E NAO UMA CONSTANTE. A regra (`hotkey_gesture.py`)
tem de continuar PURA e importavel sem I/O: e' ela que o oraculo executa. O que
muda com o gosto do dono e' so' o NUMERO que se lhe passa, e um numero que muda
mora num ficheiro. O dono escolhe, o ficheiro guarda, a thread le'.

TRES PROPRIEDADES QUE SE PAGAM SOZINHAS:

  1. **Um ficheiro estragado nao pode deixar o Alt+C surdo.** Tudo o que nao se
     le' volta ao valor de fabrica (`hotkey_gesture.HOTKEY_HOLD_MS`) e o motivo
     vai para o log. Uma app que recusa o gesto por causa de um JSON mal
     formado e' pior do que uma app com o limiar antigo.
  2. **A leitura e' cacheada por `mtime`**, e nao por processo: o oraculo e a
     bateria reescrevem o ficheiro e leem-no a seguir, no mesmo processo, e uma
     cache sem `mtime` devolver-lhes-ia o valor anterior -- o defeito classico de
     uma cache que mente sobre o disco.
  3. **A escrita e' atomica** (`panel_state.write_atomic`), para o dono nunca
     apanhar um ficheiro a meio.

O NUMERO E' SEMPRE UM DOS `HOTKEY_HOLD_MS_CHOICES`: a lista existe para o painel
oferecer opcoes legiveis em vez de aceitar um numero livre que ninguem sabe se e'
milissegundos, segundos, ou um erro de escrita.
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

#: O que o painel oferece, em ms. A ORDEM NAO E' RANKING -- e' so' a ordem do
#: dropdown, e o elemento que a fabrica usa vem PRIMEIRO (era 500, depois 900,
#: agora 200 -- a fabrica vive em `hotkey_gesture.HOTKEY_HOLD_MS`, uma vez).
#:
#: **200 ENTROU EM 2026-10-30 POR ORDEM DIRETA DO DONO**, verbatim: *"a porra do
#: alt c, bota 200ms"*. A lista so' aceita os valores que estao nela (o
#: `clamp_hold_ms` aproxima ao mais proximo), por isso sem esta entrada um pedido
#: de 200 ms caia' em 300 e a ordem ficaria cumprida so' no comentario.
#: 300/400/500/700/900/1200 ficam para ele poder voltar atras num clique: com
#: 200 ms um toque acima de ~200 ms ja' comuta a legenda (ver `hotkey_gesture`).
HOTKEY_HOLD_MS_CHOICES = (200, 300, 400, 500, 700, 900, 1200)


def clamp_hold_ms(value):
    """O milissegundo mais proximo de `value` que a regra aceita, ou None.

    `None` quando `value` nao e' um numero: nao se inventa uma escolha a partir
    de lixo -- quem chama usa o valor de fabrica e diz porque.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    choices = HOTKEY_HOLD_MS_CHOICES
    return int(min(choices, key=lambda c: (abs(c - number), c)))


def _read_payload(path=None):
    path = path or PATH
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


#: `(mtime, hold_ms)` ou None. Ver a propriedade 2 na docstring do modulo.
_CACHE = {'stamp': None, 'hold_ms': None}


def hold_ms(path=None):
    """O limiar EM VIGOR, em ms, com o valor de fabrica como retorno."""
    path = path or PATH
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        return float(hotkey_gesture.HOTKEY_HOLD_MS)
    if _CACHE['stamp'] == stamp and _CACHE['hold_ms'] is not None:
        return _CACHE['hold_ms']
    payload = _read_payload(path)
    choice = clamp_hold_ms((payload or {}).get('holdMs'))
    value = float(choice if choice else hotkey_gesture.HOTKEY_HOLD_MS)
    _CACHE['stamp'] = stamp
    _CACHE['hold_ms'] = value
    return value


def write(payload, path=None):
    """Guarda a escolha e devolve `{'ok', 'holdMs', 'error'}`. Nunca levanta.

    A recusa e' explicita e NAO muda o ficheiro: um pedido sem `holdMs` nao pode
    apagar a escolha anterior do dono.
    """
    path = path or PATH
    raw = (payload or {}).get('holdMs')
    choice = clamp_hold_ms(raw)
    if choice is None:
        return {'ok': False, 'error': 'holdMs not a number', 'holdMs': None}
    try:
        import panel_state
        panel_state.write_atomic(path, {'holdMs': choice})
    except Exception as exc:  # noqa: BLE001 -- uma escrita falhada e' um recado
        return {'ok': False, 'error': repr(exc), 'holdMs': None}
    _CACHE['stamp'] = None
    _CACHE['hold_ms'] = None
    return {'ok': True, 'holdMs': choice, 'error': None}
