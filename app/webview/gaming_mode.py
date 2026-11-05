"""GAMING MODE -- DETECTAR que o dono esta' num jogo, e NAO fazer mais nada.

ORDEM DO DONO, verbatim (2026-11-04):

    *"e em gaming: control espaço nao da display na legenda. nao faz nada. nem on
    nem off. fora de gaming: control espaço nao ativa o espaço em apps. detecta
    'gaming' parecido com o que meu projeto !watcher do disco i faz."*

Este ficheiro e' a terceira metade dessa ordem: **detectar**. Ele responde a
`is_gaming()` e escreve UMA linha de log em cada transicao. Nao suspende nada,
nao baixa prioridade de nada, nao mexe no worker, no modelo, no audio nem no
agendamento: quem perguntar `is_gaming()` decide. (O dono pediu para DETECTAR --
ligar isto a um auto-suspender seria uma ordem que ele nao deu, e este repo ja'
pagou por transformar "detecta X" em "faz Y".)

A VERDADE E' A DO `I:/!watcher`, PORTADA E NAO INVENTADA. Fonte lida em 2026-11-04:

  * `I:/!watcher/watcher/games.py` -- `GAME_NAMES`, `CLIENT_GAME_NAMES`,
    `CLIENT_FOREGROUND_STREAK_REQUIRED=3`, `is_game_process_detailed`,
    `detect_games`, `primary_game`. Um nome conhecido E' um jogo e E' uma partida
    (`IN_MATCH_NAMES = GAME_NAMES`); a familia do cliente (League/Riot) so' conta
    com a janela em primeiro plano por 3 ticks seguidos.
  * `I:/!watcher/watcher/models.py:433` -- `game_dwell_ticks: int = 10`;
    `watcher/config.py:254` le' `general.game_dwell_ticks`; o tick do watcher e'
    `general.tick_ms=600` (`config.py:245`), logo o dwell de fabrica do watcher e'
    ~6,0 s.
  * `I:/!watcher/watcher/engine.py:2398-2416` -- `_gaming_for_mood`: o relogio do
    dwell so' e' RE-ARMADO por uma vista real, e a entrada do mood fica presa
    durante `dwell` ticks depois da ultima vista. `engine.py:1223` --
    `gaming = hit.in_match or mode is GAMING`.

O QUE E' DIFERENTE DO WATCHER, e porque (as duas diferencas estao medidas aqui,
nao escondidas):

  1. TICK DE 2 s, NAO 600 ms. O watcher precisa de 600 ms porque governa CPU; o
     Sotto so' precisa de saber onde esta'. O custo do tick e' medido pelo braco
     (g) de `_main/gaming-hotkey-oracle.py` e tem orcamento declarado
     (`TICK_BUDGET_MS`).
  2. O DWELL E' O MESMO NUMERO DE TICKS (10) E, PORTANTO, MAIS TEMPO: 10 x 2 s =
     20 s contra os ~6,0 s do watcher. Com um tick de 2 s, um dwell de 3 ticks
     (6 s) perdia a histerese inteira que o watcher desenhou -- um jogo que
     demora 2 s a apresentar a janela faria `is_gaming()` cair entre duas
     vistas. O numero e' dele (10); o multiplicador e' o nosso tick, e ele esta'
     escrito aqui em vez de escondido.
  3. O `*-Win64-Shipping.exe` DESCONHECIDO nao conta. O watcher exige
     `cpu_pct_of_machine >= 2.0` para ele (`games.py:is_game_process_detailed`),
     e um tick de 2 s nao mede CPU por processo. Sem essa prova, um renderer
     ocioso (`EOS`, Discord, NVIDIA) seria "um jogo" -- que e' exactamente o que
     aquele limiar do watcher existe para impedir. O default dele e' 100.0 e nos
     NAO copiamos esse default: aqui, sem CPU medida, `active=False`.

CUSTO E MECANICA: UM `CreateToolhelp32Snapshot` por tick -- uma enumeracao, e
nao um `OpenProcess` por processo (medido: 29,05 ms contra 469 processos com o
caminho por handle; o braco (g) do oraculo mede o valor corrente) -- e nenhum
hook: nenhum `SetWindowsHookEx`, nenhum `RegisterHotKey`, nenhum
`GetAsyncKeyState` neste ficheiro. O unico `OpenProcess` que sobra e' o do NOME da
janela em primeiro plano, um por tick.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import threading
import time

# ---------------------------------------------------------------------------
# A VERDADE PORTADA DO WATCHER (`I:/!watcher/watcher/games.py`, 2026-11-04)
# ---------------------------------------------------------------------------

#: Nomes de jogo conhecidos (`games.py:GAME_NAMES`). Um nome aqui E' um jogo e E'
#: uma PARTIDA: `IN_MATCH_NAMES = GAME_NAMES` no watcher.
GAME_NAMES = frozenset(
    n.lower()
    for n in (
        "league of legends.exe",
        "marvel-win64-shipping.exe",
        "marvelrivals.exe",
        "marvelrivals-win64-shipping.exe",
        "valorant-win64-shipping.exe",
        "valorant.exe",
        "cs2.exe",
        "csgo.exe",
        "fortniteclient-win64-shipping.exe",
        "r5apex.exe",
        "overwatch.exe",
        "overwatch2.exe",
        "gta5.exe",
        "gtav.exe",
        "rdr2.exe",
        "rocketleague.exe",
        "destiny2.exe",
        "modernwarfare.exe",
        "cod.exe",
        "eldenring.exe",
        "witcher3.exe",
        "cyberpunk2077.exe",
        "dota2.exe",
        "deadlock.exe",
    )
)

#: A familia do CLIENTE que E' a experiencia de jogo quando esta' em primeiro
#: plano (lobby/champ select). Residente em segundo plano fica "launcher"
#: (`games.py:CLIENT_GAME_NAMES`).
CLIENT_GAME_NAMES = frozenset(
    n.lower()
    for n in (
        "leagueclient.exe",
        "leagueclientux.exe",
        "leagueclientuxrender.exe",
        "riotclient.exe",
        "riotclientservices.exe",
    )
)

#: Ticks SEGUIDOS em primeiro plano antes de o cliente reclamar `in_match`
#: (`games.py:CLIENT_FOREGROUND_STREAK_REQUIRED = 3`). Um pulso de 1 tick e' um
#: piscar de foco, nao um lobby.
CLIENT_FOREGROUND_STREAK_REQUIRED = 3

#: A CADENCIA. 2 s, uma enumeracao de processos por tick, sem hooks.
TICK_S = 2.0

#: DWELL EM TICKS, e o valor e' o do watcher: `models.py:433 game_dwell_ticks = 10`
#: (lido por `config.py:254` `general.game_dwell_ticks`). Ver a docstring do
#: modulo: o numero e' dele, o multiplicador (`TICK_S`) e' o nosso.
GAME_DWELL_TICKS = 10

#: ORCAMENTO DO TICK, declarado antes de medido. 50 ms sao 2,5 % de um tick de
#: 2 s. MEDIDO por `_main/gaming-hotkey-oracle.py` (braco g) nesta maquina:
#: **12,3 ms** tipico com 521 processos vivos, e **26,8 ms** numa corrida com a
#: maquina carregada -- o orcamento tem de ficar acima do pior observado, senao o
#: portao fica vermelho por causa da carga e nao do codigo. O caminho caro
#: (`OpenProcess` por pid, 29,05 ms) foi trocado por UM snapshot do Toolhelp.
TICK_BUDGET_MS = 50.0

#: O processo que le' nomes nao precisa dos direitos de leitura da memoria: so' do
#: caminho da imagem. `PROCESS_QUERY_LIMITED_INFORMATION` e' o direito minimo para
#: `QueryFullProcessImageNameW` e o unico que um processo `medium` consegue abrir
#: num processo `high` do dono.
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
MAX_PATH_W = 32767
TH32CS_SNAPPROCESS = 0x00000002


class PROCESSENTRY32W(ctypes.Structure):
    """A entrada do snapshot do Toolhelp -- a MESMA definicao que a shell usa."""

    _fields_ = [('dwSize', ctypes.c_ulong), ('cntUsage', ctypes.c_ulong),
                ('th32ProcessID', ctypes.c_ulong),
                ('th32DefaultHeapID', ctypes.c_size_t),
                ('th32ModuleID', ctypes.c_ulong),
                ('cntThreads', ctypes.c_ulong),
                ('th32ParentProcessID', ctypes.c_ulong),
                ('pcPriClassBase', ctypes.c_long), ('dwFlags', ctypes.c_ulong),
                ('szExeFile', ctypes.c_wchar * 260)]


# ---------------------------------------------------------------------------
# A REGRA PURA -- portada, para poder ser medida sem processo nenhum
# ---------------------------------------------------------------------------
def norm_name(name) -> str:
    """`games.py:_norm_name`: o nome compara-se em minusculas e sem espacos a volta."""
    return str(name or "").strip().lower()


def looks_like_unreal_shipping(name) -> bool:
    """`games.py:looks_like_unreal_shipping`."""
    n = norm_name(name)
    return n.endswith("-win64-shipping.exe") or n.endswith("-wingd-shipping.exe")


def is_game_name(name, extra_names=None) -> bool:
    """`games.py:is_game_name`: nome conhecido (ou extra) e' jogo."""
    n = norm_name(name)
    if n in GAME_NAMES:
        return True
    return n in {norm_name(e) for e in (extra_names or ()) if str(e or "").strip()}


def is_game_process_detailed(name, cpu_pct_of_machine=None, extra_names=None):
    """`(is_game, in_match)` -- a regra do watcher, com a CPU obrigatoria no Shipping.

    Diferenca declarada no topo: `cpu_pct_of_machine=None` significa "nao medido"
    e um `*-Shipping.exe` desconhecido NAO e' jogo (o watcher exige >= 2,0 % da
    maquina, `games.py:is_game_process_detailed`). O nome conhecido nao precisa de
    CPU: `True, True`.
    """
    if is_game_name(name, extra_names):
        return True, True
    if not looks_like_unreal_shipping(name):
        return False, False
    if cpu_pct_of_machine is None:
        return False, False
    active = float(cpu_pct_of_machine) >= 2.0
    return active, active


class GameHit(object):
    """`games.py:GameHit`, sem os campos que so' o governador do watcher usa."""

    __slots__ = ("name", "in_match")

    def __init__(self, name, in_match):
        self.name = str(name or "")
        self.in_match = bool(in_match)

    def __repr__(self):
        return f'GameHit(name={self.name!r}, in_match={self.in_match})'


def detect_games(names, foreground_name=None, foreground_streak=0,
                 claim_held=False, extra_names=None):
    """`games.py:detect_games` sobre uma lista de NOMES (aqui nao ha' pid nem exe).

    Ordem preservada: o primeiro hit e' o primeiro processo, e `primary_game`
    prefere o que esta' `in_match`. A familia do cliente so' entra com
    `foreground_streak >= CLIENT_FOREGROUND_STREAK_REQUIRED` (ou `claim_held`),
    que e' a mesma condicao do watcher.
    """
    hits = []
    fg = norm_name(foreground_name)
    for raw in names or ():
        name = norm_name(raw)
        is_game, in_match = is_game_process_detailed(name, None, extra_names)
        if not is_game and name in CLIENT_GAME_NAMES:
            if not (claim_held or (fg == name
                                   and int(foreground_streak)
                                   >= CLIENT_FOREGROUND_STREAK_REQUIRED)):
                continue
            is_game = True
            in_match = True
        if not is_game:
            continue
        hits.append(GameHit(raw, in_match))
    return hits


def primary_game(hits):
    """`games.py:primary_game`: o primeiro `in_match`, senao o primeiro."""
    if not hits:
        return None
    for hit in hits:
        if hit.in_match:
            return hit
    return hits[0]


# ---------------------------------------------------------------------------
# A LEITURA -- um snapshot do Toolhelp por tick
# ---------------------------------------------------------------------------
_kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
_user32 = ctypes.WinDLL('user32', use_last_error=True)

_kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_kernel32.OpenProcess.restype = wt.HANDLE
_kernel32.CloseHandle.argtypes = [wt.HANDLE]
_kernel32.CloseHandle.restype = wt.BOOL
_kernel32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD,
                                                 wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
_kernel32.QueryFullProcessImageNameW.restype = wt.BOOL
_kernel32.CreateToolhelp32Snapshot.restype = wt.HANDLE
_kernel32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
_kernel32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
_kernel32.Process32NextW.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
_user32.GetForegroundWindow.restype = wt.HWND
_user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
_user32.GetWindowThreadProcessId.restype = wt.DWORD


def proc_name_from_path(path) -> str:
    """`C:\\Games\\Elden Ring\\eldenring.exe` -> `eldenring.exe`."""
    return norm_name(os.path.basename(str(path or "").replace('/', '\\')))


def _process_names(limit=4096):
    """OS NOMES (`eldenring.exe`, ...) dos processos vivos, num SO' snapshot.

    UM `CreateToolhelp32Snapshot`, e nao um `OpenProcess` por processo: o
    `EnumProcesses` + `QueryFullProcessImageNameW` custava **29,05 ms** por tick
    nesta maquina (469 processos, medido por `_main/gaming-hotkey-oracle.py`
    antes desta troca), porque cada pid pagava um handle. O snapshot devolve o
    `szExeFile` de todos de uma vez e custa uma fraccao disso.

    O snapshot nao falha por integridade: um processo `high` do dono aparece com
    o nome, sem precisar de `PROCESS_QUERY_LIMITED_INFORMATION` (o
    `OpenProcess` que ficou existe so' para o nome da janela em primeiro plano,
    um por tick). Um snapshot indisponivel devolve lista vazia: nenhum jogo
    visto, nunca um jogo inventado.
    """
    snapshot = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == wt.HANDLE(-1).value or not snapshot:
        return []
    names = []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        ok = _kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok and len(names) < int(limit):
            if int(entry.th32ProcessID) > 0:
                names.append(norm_name(entry.szExeFile))
            entry = PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
            ok = _kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        _kernel32.CloseHandle(snapshot)
    return names


def _foreground_pid():
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return 0
    pid = wt.DWORD(0)
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def _pid_to_name(pid):
    """O nome de UM pid -- a janela em primeiro plano, sem enumerar a maquina."""
    if not pid:
        return ""
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(MAX_PATH_W)
        size = wt.DWORD(MAX_PATH_W)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return proc_name_from_path(buf.value)
    finally:
        _kernel32.CloseHandle(handle)
    return ""


# ---------------------------------------------------------------------------
# O DETECTOR -- a vista, o dwell e a UNICA linha de transicao
# ---------------------------------------------------------------------------
class GamingDetector(object):
    """`is_gaming()` com o dwell do watcher; publica uma linha por TRANSICAO.

    `read_names` e `read_foreground` sao costuras (o oraculo injecta uma lista de
    nomes e um primeiro plano falsos; o processo vivo chama `_process_names` e
    `_foreground_pid`). O que se mede -- o dwell, o `in_match`, a streak do
    cliente e a transicao -- e' o do ficheiro.
    """

    def __init__(self, log=None, tick_s=TICK_S, dwell_ticks=GAME_DWELL_TICKS,
                 read_names=None, read_foreground=None, read_foreground_name=None,
                 extra_names=None, clock=None):
        self.log = log or (lambda *a, **k: None)
        self.tick_s = float(tick_s)
        self.dwell_ticks = int(dwell_ticks)
        self._read_names = read_names or _process_names
        self._read_foreground = read_foreground or _foreground_pid
        self._read_foreground_name = read_foreground_name or _pid_to_name
        self._extra_names = list(extra_names or ())
        self._clock = clock or time.monotonic
        #: O numero do tick -- o relogio do dwell. `engine.py:_gaming_for_mood`
        #: guarda o tick da ultima vista e conta a partir dele.
        self.ticks = 0
        self._seen_tick = None
        self._streak_pid_name = ""
        self._streak = 0
        self._gaming = False
        self._game_name = ""
        self._why = "start"
        self.last_names = []
        self.last_hits = []
        self.last_tick_ms = 0.0
        #: A ultima coisa que o log DISSE. A linha so' sai na transicao.
        self._published = False
        self._lock = threading.Lock()

    # -- a leitura -----------------------------------------------------------
    def tick(self):
        """UMA leitura: enumera, decide, aplica o dwell, escreve a transicao."""
        t0 = self._clock()
        names = list(self._read_names())
        self.ticks += 1
        fg_pid = int(self._read_foreground() or 0)
        fg_name = proc_name_from_path(self._read_foreground_name(fg_pid))
        # A STREAK E' POR JANELA, nao por processo: o watcher conta ticks de
        # primeiro plano CONSECUTIVOS do mesmo nome (`games.py`), e um foco que
        # muda de janela recomeca.
        if fg_name and fg_name == self._streak_pid_name:
            self._streak += 1
        else:
            self._streak_pid_name = fg_name
            self._streak = 1 if fg_name else 0
        hits = detect_games(names, foreground_name=fg_name,
                            foreground_streak=self._streak,
                            extra_names=self._extra_names)
        hit = primary_game(hits)
        raw = bool(hit is not None and hit.in_match)
        self.last_names = names
        self.last_hits = hits
        if raw:
            self._seen_tick = self.ticks
        dwell_left = 0
        if self._seen_tick is not None:
            # Ticks de histerese que AINDA restam, contando este: o tick seguinte
            # a' vista tem `dwell` restantes, e o ultimo tem 1.
            dwell_left = max(0, self.dwell_ticks - (self.ticks - self._seen_tick) + 1)
        # A REGUA E' A DO WATCHER, INCLUSIVE: `tick - seen <= dwell`
        # (`engine.py:_gaming_for_mood`). Com `dwell=10` e a vista no tick 1, o
        # tick 11 AINDA esta' em gaming e o 12 nao -- um dwell de 10 ticks tem de
        # manter 10 ticks, nao 9 (o `> 0` de uma primeira versao dava um a menos).
        gaming = bool(raw or (
            self.dwell_ticks > 0 and self._seen_tick is not None
            and (self.ticks - self._seen_tick) <= self.dwell_ticks))
        why = ("in-match" if raw else
               ("start" if self._seen_tick is None else "dwell"))
        game = hit.name if hit is not None else (
            self._game_name if gaming else "")
        with self._lock:
            self._gaming = gaming
            self._game_name = game
            self._why = why
        self.last_tick_ms = (self._clock() - t0) * 1000.0
        self._publish(gaming, game, why, raw, dwell_left)
        return gaming

    def _publish(self, gaming, game, why, raw, dwell_left):
        """UMA linha em cada TRANSICAO (nao a cada tick -- o log ja' pagou isso)."""
        prev = self._published
        self._published = bool(gaming)
        if prev == gaming:
            return
        self.log('GAMING_MODE on=%s game=%s why=%s ticks=%d raw=%s dwell_left=%d'
                 % (str(bool(gaming)).lower(), '"%s"' % (game or ""), why,
                    self.ticks, str(bool(raw)).lower(), dwell_left))

    # -- as perguntas --------------------------------------------------------
    def is_gaming(self):
        with self._lock:
            return bool(self._gaming)

    def game_name(self):
        with self._lock:
            return self._game_name

    def why(self):
        with self._lock:
            return self._why

    def snapshot(self):
        with self._lock:
            return {'gaming': self._gaming, 'game': self._game_name,
                    'why': self._why, 'ticks': self.ticks,
                    'tick_ms': round(self.last_tick_ms, 3),
                    'hits': [repr(h) for h in self.last_hits]}


# ---------------------------------------------------------------------------
# O FIO -- 2 s, um tick, e ele NAO AGE
# ---------------------------------------------------------------------------
class GamingWatcher(threading.Thread):
    """O fio do detector. LE' e LOG'A; nao altera nada.

    `is_gaming()`/`snapshot()` sao o que este fio entrega. Ele NAO para o worker,
    NAO baixa prioridade, NAO muda `poll_s` de ninguem: e' `daemon` e morre com o
    processo. O dono pediu para DETECTAR; agir sobre a deteccao e' decisao dele.
    """

    def __init__(self, log=None, tick_s=TICK_S, detector=None, **kwargs):
        super().__init__(name='sotto-gaming-mode', daemon=True)
        self.log = log or (lambda *a, **k: None)
        self.detector = detector or GamingDetector(log=self.log, tick_s=tick_s,
                                                   **kwargs)
        self._stop_requested = threading.Event()

    def run(self):
        self.log('GAMING_WATCH tick_s=%.1f dwell_ticks=%d source=watcher'
                 % (self.detector.tick_s, self.detector.dwell_ticks))
        while not self._stop_requested.is_set():
            try:
                self.detector.tick()
            except Exception as exc:  # noqa: BLE001 -- um tick perdido nao mata o fio
                self.log('GAMING_TICK_FAILED error=%r' % (exc,))
            self._stop_requested.wait(self.detector.tick_s)

    def stop(self):
        self._stop_requested.set()

    def is_gaming(self):
        return self.detector.is_gaming()


def live_hotkey_plan(gaming, registered, register_failed=False):
    """O `Ctrl+Space` TOMADO ou DEVOLVIDO? -- a tabela, pura e testavel.

    ORDEM DO DONO, verbatim (2026-11-05): *"faz o control espaço nao inputar
    espaço pra outros apps. mas desativa isso em jogos. entao control espaço em
    um jogo pode sim apertar espaço. só que nao vai ter display de legenda, pra
    ter, tenho que dar alt c e ativar manualmente"*.

    AS DUAS METADES, E PORQUE CADA UMA E' UMA SO':

      * FORA DE JOGO a combinacao e' TOMADA (`RegisterHotKey`): o Windows entrega
        `WM_HOTKEY` a' shell e NAO entrega a tecla a' janela em foco -- e' o que
        impede o `Ctrl+Space` de escrever um ESPACO no editor, no browser, no
        chat. A legenda e' o que a tecla faz.
      * EM JOGO a combinacao e' DEVOLVIDA (`UnregisterHotKey`): o jogo recebe o
        `Ctrl+Space` NATIVO (nao ha' `SendInput` nenhum, logo nao ha' o problema
        dos jogos que leem input por raw input), e a shell nao alterna nada --
        *"nao da display na legenda. nao faz nada. nem on nem off"*. Ligar a
        legenda dentro do jogo e' o Alt+C, que e' registado sempre.

    A DEVOLUCAO E' A PRIMEIRA ACAO EM TODA ENTRADA EM JOGO, inclusive quando o
    registo nunca existiu: `give-back` e' idempotente no chamador.

    `register_failed` existe para o caso medido (`winerror=1409`, outro programa
    tem a combinacao): sem tomar a tecla nao ha' como nao vazar o espaco, e o
    unico caminho honesto e' o observador -- que alterna a legenda e deixa a
    tecla passar. Quem chama diz isso no log, nao finge que tomou.
    """
    if gaming:
        return 'give-back' if registered else 'stay-free'
    if register_failed:
        return 'stay-free'
    return 'stay-free' if registered else 'take'


if __name__ == '__main__':
    det = GamingDetector(log=lambda m: print(m, flush=True))
    print(det.tick(), det.snapshot())
