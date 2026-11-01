"""Esta' ALGUM som a sair pelos altifalantes AGORA? (leitura, nunca escrita)

O DONO, 2026-10-30: *"por que a merda do meu audio ainda some? arruam caralho"*.
Medido no registo do proprio shell (`_main/shell-relaunch.log`): **7 relancamentos
reais** em 2026-10-30, tres deles dentro da mesma hora (06:53:40, 06:56:54,
07:01:00, 07:53:43, 08:10:44, 08:12:48), cada um um `kill pid=<pid> confirmado
morto` seguido de `schtasks /run`. O vigia de auto-relancamento so' perguntava
"semaforo de legendas desligado?", e um reinicio da app reabre o dispositivo de
captura e mata o worker a meio -- o corte que ele ouve.

Este modulo e' a guarda que faltava: o vigia NAO se senta de novo enquanto houver
som a sair do PC. Le so', pela interface de medicao do Windows
(`IAudioMeterInformation` no endpoint), o pico instantaneo de cada endpoint de
renderizacao ACTIVO. Nao abre cliente de audio, nao muda volume, nao muda mute --
nao ha' aqui uma unica chamada que ESCREVA no dispositivo.

Falha de leitura = `False`: um medidor avariado nunca pode trancar o vigia para
sempre (a app deixaria de aplicar mudancas e ninguem saberia). O custo de um
falso "nao ha' som" e' um relancamento que ja' aconteceria antes deste modulo.
"""

from __future__ import annotations

import ctypes
from ctypes import POINTER, c_float, c_uint
from typing import Callable, Iterable, Sequence

#: O piso. Um valor medido no mixer de um dispositivo ocioso e' 0.000000; o
#: microfone vivo desta maquina mede 0.000092 na mesma leitura. 0.002 esta' acima
#: do ruido de um dispositivo parado e abaixo de qualquer musica falada.
PEAK_FLOOR = 0.002

_IID_METER = '{C02216F6-8C67-4B5B-9D00-D008E73E0064}'


def _meter_interface():
    """A interface COM, definida AQUI porque o `pycaw` nao a traz.

    Declarada uma vez por processo (o `comtypes` regista a interface no primeiro
    uso; repetir a classe daria um IID duplicado e um erro de registo).
    """
    global _METER
    try:
        return _METER
    except NameError:
        pass
    from comtypes import GUID, COMMETHOD, HRESULT, IUnknown

    class IAudioMeterInformation(IUnknown):
        _iid_ = GUID(_IID_METER)
        _methods_ = [
            COMMETHOD([], HRESULT, 'GetPeakValue',
                      (['out'], POINTER(c_float), 'pfPeak')),
            COMMETHOD([], HRESULT, 'GetMeteringChannelCount',
                      (['out'], POINTER(c_uint), 'pnChannelCount')),
            COMMETHOD([], HRESULT, 'QueryHardwareSupport',
                      (['out'], POINTER(c_uint), 'pdwHardwareSupportMask')),
        ]

    _METER = IAudioMeterInformation
    return _METER


def render_peaks() -> Sequence[tuple]:
    """[(nome, pico)] dos endpoints de renderizacao ACTIVOS. Pode levantar."""
    import warnings
    from comtypes import CLSCTX_ALL, CoInitialize
    from pycaw.pycaw import AudioUtilities

    with warnings.catch_warnings():
        # O `pycaw` avisa por cada propriedade que um dispositivo virtual nao
        # publica; e' ruido deste caminho, nao um erro.
        warnings.simplefilter('ignore')
        CoInitialize()
        meter = _meter_interface()
        rows = []
        for device in AudioUtilities.GetAllDevices():
            if not str(getattr(device, 'state', '')).endswith('Active'):
                continue
            try:
                raw = device._dev.Activate(meter._iid_, CLSCTX_ALL, None)
                iface = ctypes.cast(raw, POINTER(meter))
                rows.append((str(getattr(device, 'FriendlyName', '?')), iface.GetPeakValue()))
            except Exception:                          # noqa: BLE001 - ver docstring
                continue
        return rows


def playing(floor: float = PEAK_FLOOR,
            peaks: Callable[[], Iterable[tuple]] | None = None) -> bool:
    """Verdadeiro se QUALQUER endpoint de renderizacao estiver acima do piso."""
    reader = peaks or render_peaks
    try:
        return any(float(value) > floor for _, value in reader())
    except Exception:                                  # noqa: BLE001 - ver docstring
        return False


def loudest(peaks: Callable[[], Iterable[tuple]] | None = None) -> tuple:
    """(nome, pico) do endpoint mais alto -- so' para o registo do vigia."""
    reader = peaks or render_peaks
    try:
        rows = [(name, float(value)) for name, value in reader()]
    except Exception:                                  # noqa: BLE001
        return ('', 0.0)
    if not rows:
        return ('', 0.0)
    return max(rows, key=lambda row: row[1])


if __name__ == '__main__':                             # medicao avulsa
    rows = render_peaks()
    for name, value in rows:
        print('%-52s %.6f' % (name[:52], value))
    print('PLAYING=%s loudest=%r' % (playing(peaks=lambda: rows), loudest(lambda: rows)))
