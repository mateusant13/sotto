# NO-BUG: modulo NOVO (alvo por NOME de processo para o tap por processo); nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
# -*- coding: utf-8 -*-
"""ALVO DO TAP POR PROCESSO, escolhido por NOME -- e re-escolhido quando morre.

POR QUE ISTO EXISTE (ordem do dono, 2026-11-09, verbatim): *"to em call no
discord agora. identifica corretamente o audio saindo do discord. faz o tempo
real funcionar"*. O `--target-pid` ja' existia e funciona (medido nesta maquina:
`PLP_START hr=0`, 39 blocos em 4 s com o `Discord.exe` pid 24484, 0 pacotes
silenciosos) -- mas um pid e' um numero que muda quando o dono reinicia o
Discord, e nesse instante o tap fica sem alvo. O que o dono nomeia e' o
PROGRAMA, nao o pid.

DUAS DECISOES QUE O CODIGO CARREGA, as duas medidas:

1. **O ALVO E' A RAIZ DA ARVORE, nao o processo mais gordo.** O
   `AUDIOCLIENT_ACTIVATION_PARAMS` em modo `INCLUDE_TARGET_PROCESS_TREE` captura
   a arvore do pid dado, logo um pid do MEIO da arvore deixa de fora os irmaos
   que renderizam audio. Nesta maquina o `Discord.exe` tem seis processos e um
   deles e' o dono da sessao de audio; a raiz e' o unico cujo pai NAO e' tambem
   `Discord.exe`.

2. **PID MORTO NAO E' ALVO.** `resolve` devolve o pid vivo agora; quando ele
   morre, `resolve_again` escolhe outro processo do mesmo nome em vez de deixar
   a escada sem rung. Um alvo que morreu no meio nao pode ser confundido com um
   programa que nunca esteve la'.

Puro o suficiente para ser julgado sem abrir dispositivo: `match` e `pick_root`
operam sobre linhas de uma tabela de processos injectada, e o oraculo
`_main/process-target-oracle.py` e' quem as julga.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", wt.DWORD),
                ("cntUsage", wt.DWORD),
                ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_wchar * 260)]


def normalise(name) -> str:
    """`Discord` / `discord.exe` / ` C:\\x\\Discord.exe ` -> `discord.exe`."""
    got = os.path.basename(str(name or "").strip().strip('"')).strip().lower()
    if not got:
        return ""
    return got if got.endswith(".exe") else got + ".exe"


def match(rows, name) -> list:
    """[(pid, ppid, image)] dos processos que sao EXACTAMENTE esse programa.

    `rows` e' `[(pid, ppid, image)]` -- a forma que `snapshot()` devolve. Nome
    comparado por igualdade do basename, nunca por substring: `Discord.exe` nao
    pode casar com `DiscordCanary.exe`, e uma substring casaria.
    """
    want = normalise(name)
    if not want:
        return []
    out = []
    for row in rows:
        try:
            pid, ppid, image = int(row[0]), int(row[1]), str(row[2])
        except (TypeError, ValueError, IndexError):
            continue
        if normalise(image) == want:
            out.append((pid, ppid, image))
    return out


def pick_root(rows, name):
    """O pid da RAIZ da arvore desse programa, ou None.

    Raiz = o processo do nome cujo PAI nao tem o mesmo nome (o "main" do
    programa). Empate (mais de uma raiz, ex.: duas instancias): o maior pid, que
    e' o mais recente no Windows, porque um Discord que reiniciou deixa a raiz
    velha a morrer. O criterio e' declarado aqui em vez de ficar implicito na
    ordem em que a tabela veio.
    """
    hits = match(rows, name)
    if not hits:
        return None
    same = {pid for pid, _ppid, _img in hits}
    roots = [pid for pid, ppid, _img in hits if ppid not in same]
    pool = roots or [pid for pid, _ppid, _img in hits]
    return max(pool)


def snapshot() -> list:
    """[(pid, ppid, image)] da maquina, lido agora. `[]` quando nao da' para ler.

    `[]` NAO e' "o programa nao existe": quem chama decide, e o worker trata os
    dois casos com a mesma recusa -- mas a frase que ele escreve diz qual dos
    dois foi (ver `describe`).
    """
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
    k32.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32)]
    k32.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32)]
    k32.CloseHandle.argtypes = [ctypes.c_void_p]
    snap = k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == INVALID_HANDLE_VALUE:
        return []
    rows = []
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    try:
        ok = k32.Process32FirstW(ctypes.c_void_p(snap), ctypes.byref(entry))
        while ok:
            rows.append((int(entry.th32ProcessID), int(entry.th32ParentProcessID),
                         str(entry.szExeFile)))
            ok = k32.Process32NextW(ctypes.c_void_p(snap), ctypes.byref(entry))
    finally:
        k32.CloseHandle(ctypes.c_void_p(snap))
    return rows


def alive(pid) -> bool:
    """True quando `pid` existe AGORA (OpenProcess com QUERY_LIMITED, sem tocá-lo)."""
    try:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.OpenProcess.restype = ctypes.c_void_p
        k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        k32.CloseHandle.argtypes = [ctypes.c_void_p]
        h = k32.OpenProcess(0x1000, False, int(pid))
        if not h:
            return False
        k32.CloseHandle(ctypes.c_void_p(h))
        return True
    except Exception:                        # noqa: BLE001 - nunca levanta por um alvo
        return False


def resolve(name, rows=None):
    """O pid da raiz de `name` AGORA, ou None."""
    return pick_root(snapshot() if rows is None else rows, name)


def resolve_again(name, current=None, rows=None):
    """O pid a usar na proxima rotacao: o actual se ainda vive, senao um novo.

    Isto e' o que faz um tap por nome sobreviver ao reinicio do programa. Quando
    nao ha' nenhum processo do nome, devolve None -- e o chamador tem de DIZER
    isso em vez de abrir o mix do endpoint em silencio (a substituicao calada e'
    a classe que a escada desta casa existe para remover).
    """
    if current and alive(current):
        return int(current)
    return resolve(name, rows=rows)
