"""As estruturas Win32 do shell, num sitio so'.

PORQUE E' QUE ISTO VIVE NUM MODULO PROPRIO. O ratchet
(`_main/code-health-oracle.py`) conta CLASSES por ficheiro, e
`app/webview/sotto_webview.py` bateu no tecto de 25 quando a leitura de pointer
lock chegou (`CURSORINFO`). O tecto nao se sobe -- extrai-se. Estas tres
declaracoes sao `ctypes.Structure` PURAS: nao tem logica, nao chamam Win32, nao
dependem de nada deste repo. Sairem do shell nao muda um byte do que o Windows
ve; o shell importa-as de volta pelos MESMOS nomes (`RECT`, `POINT`,
`CURSORINFO`), por isso nenhum chamador -- `dock_strip`, `clamp_geometry`,
`target_display`, `pointer_lock_state`, os `argtypes` de `GetClipCursor` -- muda.

O `CURSORINFO` NAO VIAJA SOZINHO: o campo `ptScreenPos` e' um `POINT`, e o
`GetClipCursor` que o `pointer_lock_state` le pede um `RECT`, por isso os tres
andam juntos -- uma struct nao se declara sem os tipos dos seus campos.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long),
                ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [('cbSize', wt.DWORD), ('flags', wt.DWORD), ('hCursor', wt.HANDLE),
                ('ptScreenPos', POINT)]
