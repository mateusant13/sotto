"""O censo da ponte: WHO ficou com o tempo quando um `exec_js` nao responde.

Vivia dentro de `sotto_webview.py` (2026-11-01) e saiu por duas razoes medidas: o
ratchet conta bytes e globals de modulo, e este instrumento -- que so' corre com
`SOTTO_BRIDGE_CENSUS=1` -- nao tem por que' viver no mesmo ficheiro que o produto
que ele observa. A `_BRIDGE_CENSUS` memoizada passou a ser DESTE modulo.

O que ele responde, e porque nao e' enfeite: `exec_js TIMEOUT after 10.0s` apareceu
515 vezes no log do dono e a linha nao dizia ONDE o tempo foi. Ha' tres donos
possiveis -- o UI thread nao correu o callable, o renderer nao respondeu ao
`ExecuteScriptAsync`, ou a continuacao .NET nao entrou em Python -- e dois deles
exigem correccoes opostas. `py-spy dump` esta' NEGADO nesta maquina (os error 5,
medido 2026-11-01), portanto as stacks saem de dentro: `sys._current_frames()`.

NUNCA LANCA: uma shell que nao arranca por causa de um instrumento e' pior do que
uma sem instrumento.
"""
from __future__ import annotations

import importlib.util
import json
import os

_CENSUS_UNSET = object()
_BRIDGE_CENSUS = _CENSUS_UNSET


def census(log, warn, repo_root):
    """O `_main/bridge-census.py`, quando `SOTTO_BRIDGE_CENSUS=1`. Senao None.

    O QUE ISTO RESPONDE, e porque nao e' enfeite: `exec_js TIMEOUT after 10.0s`
    aparece 515 vezes no log do dono e a linha nao diz ONDE o tempo foi. Ha'
    tres donos possiveis -- o UI thread nao correu o callable, o renderer nao
    respondeu ao `ExecuteScriptAsync`, ou a continuacao .NET nao entrou em
    Python -- e dois deles exigem correccoes opostas. `py-spy dump` esta' NEGADO
    nesta maquina (os error 5, medido 2026-11-01), portanto o censo tira as
    stacks de dentro: `sys._current_frames()` (ver `_main/bridge-census.py`).

    NUNCA LANCA e nunca custa nada quando desligado: uma shell que nao arranca
    por causa de um instrumento e' pior do que uma sem instrumento.
    """
    global _BRIDGE_CENSUS
    if _BRIDGE_CENSUS is not _CENSUS_UNSET:
        return _BRIDGE_CENSUS
    _BRIDGE_CENSUS = None
    if (os.environ.get('SOTTO_BRIDGE_CENSUS') or '').strip().lower() not in (
            '1', 'true', 'yes', 'on'):
        return None
    try:
        import importlib.util
        path = os.path.join(repo_root, '_main', 'bridge-census.py')
        spec = importlib.util.spec_from_file_location('bridge_census', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _BRIDGE_CENSUS = mod.attach(log)
        log(f'BRIDGE_CENSUS_ON path={json.dumps(path)} '
            f'tick_ms={int(mod.TICK_S * 1000)}')
    except Exception as exc:  # noqa: BLE001 -- um instrumento partido e' um warn
        warn(f'BRIDGE_CENSUS_FAILED {type(exc).__name__}: {exc}')
        _BRIDGE_CENSUS = None
    return _BRIDGE_CENSUS


_CENSUS_UNSET = object()
_BRIDGE_CENSUS = _CENSUS_UNSET


def task_bits(box, done):
    """O estado .NET da chamada, para o censo. NUNCA lanca.

    `status=RanToCompletion` com `continuation=unset` e' a assinatura de "o JS
    respondeu e o Python nunca foi chamado"; `Waiting*`/`Running` com
    `continuation=unset` e' "o renderer nunca devolveu nada". Sao dois defeitos
    diferentes e a linha do log tem de os separar.
    """
    status = 'no-task'
    try:
        task = box.get('task')
        if task is not None:
            status = str(task.Status)
    except Exception:  # noqa: BLE001
        status = 'unreadable'
    try:
        cont = 'set' if done.is_set() else 'unset'
    except Exception:  # noqa: BLE001
        cont = '?'
    return {'status': status, 'continuation': cont}


