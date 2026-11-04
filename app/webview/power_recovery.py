"""RECUPERACAO DE ENERGIA E DE SESSAO -- o buraco que o RE mediu em 2026-11-04.

MEDIDO: `grep -n "WM_POWERBROADCAST\\|WM_WTSSESSION_CHANGE\\|
RegisterPowerSettingNotification\\|WTSRegisterSessionNotification"
app/webview/sotto_webview.py` devolvia ZERO. A app nao sabia que a maquina
tinha acordado. As tres consequencias, cada uma visivel para o dono:

  1. A posicao e a visibilidade da janela sobrevivem ao sleep, mas o
     `WS_EX_TOPMOST` pode nao sobreviver a um jogo em ecra inteiro, a um
     `Alt+Tab` para o desktop virtual ou a propria reorganizacao do Z-order do
     Windows -- e a legenda fica POR BAIXO sem um erro e sem uma linha. Isto ja'
     tem cura desde hoje (`topmost_keepalive.py`, laco de 2 s), mas o laco e' um
     *poller*: no instante em que a maquina acorda, e' o evento que sabe.
  2. O endpoint de audio pode ser invalidado enquanto dormia. O worker continua
     vivo e *surdo*: os contadores nao sobem e nada no painel o diz.
  3. Um monitor que desapareceu (dock/undock, RDP) deixa a geometria guardada
     fora de qualquer monitor: a legenda existe num sitio onde nao ha' ecra.

A decisao e PURA (`classify` + `plan`) e o transporte e' um `NativeWindow`.
Esta separacao e' a que permite provar a decisao sem tocar na maquina do dono:
nenhum oraculo deste repo consegue dormir o PC dele, mas uma mensagem
`WM_POWERBROADCAST` entregue ao WndProc REAL e' a mesma chamada que o Windows
faz -- e e' isso que o braco vivo do oraculo mede.

NAO ESCREVE. Nao muda estado de audio (`SetMute`/`SetVolume` proibidos pela
regra do dono), nao mostra painel, nao rouba foco. So' pede as accoes a quem as
sabe fazer -- e cada accao e' um metodo que ja' existe na shell.
"""
from __future__ import annotations

# -- a linguagem do Windows ------------------------------------------------
WM_POWERBROADCAST = 0x0218
WM_WTSSESSION_CHANGE = 0x02B1

PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMEAUTOMATIC = 0x0012
PBT_APMRESUMECRITICAL = 0x0006
PBT_APMSUSPEND = 0x0004
PBT_POWERSETTINGCHANGE = 0x8013

WTS_CONSOLE_CONNECT = 0x1
WTS_CONSOLE_DISCONNECT = 0x2
WTS_REMOTE_CONNECT = 0x3
WTS_REMOTE_DISCONNECT = 0x4
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8

NOTIFY_FOR_THIS_SESSION = 0

# As accoes. Nomes estaveis porque o log e' o contrato de leitura.
ACT_TOPMOST = "topmost"
ACT_WORKER = "worker"
ACT_GEOMETRY = "geometry"

_RESUME = (ACT_TOPMOST, ACT_WORKER, ACT_GEOMETRY)

# O PLANO. Cada linha e' uma razao medida, nao uma intuicao:
#
#   resume   -- os tres. O device pode ter desaparecido, o bit TOPMOST pode ter
#               sido tomado e o monitor pode ter mudado. E' o unico momento em
#               que o Windows nos diz que as tres coisas ficaram por confirmar.
#   unlock   -- topmost + geometria. O worker NAO se toca: ele atravessou o lock
#               a correr (foi medido: o processo continua e continua a escrever
#               `WORKER_STATS` com a sessao trancada), e um revive a cada unlock
#               seria um reinicio de 14-26 s a troco de nada.
#   connect  -- sessao nova (RDP/console). Geometria obrigatoria, porque o
#               conjunto de monitores mudou por definicao; topmost porque a
#               janela nasceu noutra sessao.
#   lock/suspend/logoff/desconhecido -- NADA. No lock nao ha' ecra onde pintar, e
#               agir ali so' gasta chamadas ao USER32 (e, no caso do audio,
#               faria o oposto do que o dono quer: mexer no audio dele).
_PLANS = {
    "resume": _RESUME,
    "unlock": (ACT_TOPMOST, ACT_GEOMETRY),
    "connect": (ACT_TOPMOST, ACT_GEOMETRY),
}


def classify(msg: int, wparam: int):
    """A mensagem vira um evento com nome, ou `None` para o que nao se acao."""
    try:
        msg = int(msg)
        wparam = int(wparam)
    except (TypeError, ValueError):
        return None
    if msg == WM_POWERBROADCAST:
        if wparam in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND,
                      PBT_APMRESUMECRITICAL):
            return "resume"
        return None
    if msg == WM_WTSSESSION_CHANGE:
        if wparam == WTS_SESSION_UNLOCK:
            return "unlock"
        if wparam in (WTS_CONSOLE_CONNECT, WTS_REMOTE_CONNECT):
            return "connect"
        return None
    return None


def plan(event):
    """As accoes para o evento, em ordem, sem duplicados."""
    if not event:
        return ()
    acts = _PLANS.get(event, ())
    seen = []
    for a in acts:
        if a not in seen:
            seen.append(a)
    return tuple(seen)


class PowerRecovery:
    """Entrega `plan(classify(...))` aos handlers, a partir de um WndProc REAL.

    PORQUE UMA JANELA PROPRIA, e nao a do painel (medido 2026-11-04 08:0x):
    `NativeWindow.AssignHandle` na form do painel devolveu
    `POWER_RECOVERY_ATTACHED` e `PostMessageW` aceitou a mensagem, mas nenhuma
    linha `POWER_RESUME` apareceu -- o handle do WinForms e' recriado quando o
    WebView2 termina de subir, e a subclasse morre com o handle antigo. Uma
    janela top-level POPUP de tamanho zero, criada e nunca mostrada, e' do nosso
    dono do principio ao fim, nao pinta nada, e recebe os BROADCAST do Windows
    (a janela da bandeja nao recebe: e' `HWND_MESSAGE`).

    O contrato de leitura e' o log: `POWER_RESUME event=.. actions=..` e uma
    linha por accao. Uma accao que levanta nao impede as outras.
    """

    CLASS_NAME = "SottoPowerRecoveryWindow"

    def __init__(self, handlers, log=None, hwnd=None):
        self.handlers = dict(handlers or {})
        self.log = log or (lambda _m: None)
        self.hwnd = int(hwnd) if hwnd else None
        self._own = hwnd is None
        self._hwnd = None
        self._proc = None
        self._registered = False
        self.fired = []

    # -- o transporte ------------------------------------------------------
    def attach(self):
        """Cria a janela numa THREAD com bomba de mensagens, e pede as notificacoes.

        PORQUE UMA THREAD PROPRIA (medido 2026-11-04 08:1x): a janela era criada
        na thread que chamou `_on_before_show`, e `PostMessageW` era ACEITE sem
        que o `WndProc` corresse uma vez -- uma mensagem postada so' e' despachada
        por uma thread que esteja a BOMBEAR, e essa thread nao bombeia: quem
        bombeia e' a `Application.Run` do WinForms, noutra thread. A bandeja deste
        shell ja' e' assim (thread propria + `GetMessage`), e este objecto segue o
        mesmo desenho em vez de inventar outro.
        """
        import threading

        self._stop = threading.Event()
        self._ready = threading.Event()
        self._tid = None
        self._thread = threading.Thread(target=self._run_window,
                                        name='sotto-power-window', daemon=True)
        self._thread.start()
        self._ready.wait(5.0)
        return self._registered

    def _run_window(self):
        import ctypes
        from ctypes import wintypes as wt

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        # AS ASSINATURAS SAO OBRIGATORIAS AQUI (medido no `--neg-arm` do oraculo):
        # sem `argtypes`, o `lparam` de 64 bits chega ao `DefWindowProcW` como um
        # int Python e o ctypes levanta `OverflowError: int too long to convert`
        # dentro do callback -- o Windows engole a excepcao, o proc devolve lixo e
        # o defeito so' aparece quando um mutante deixa passar uma mensagem com
        # ponteiro no `lparam`.
        user32.DefWindowProcW.argtypes = [wt.HWND, ctypes.c_uint, ctypes.c_size_t,
                                          ctypes.c_ssize_t]
        user32.DefWindowProcW.restype = ctypes.c_ssize_t
        user32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND,
                                       ctypes.c_uint, ctypes.c_uint]
        user32.GetMessageW.restype = ctypes.c_int
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wt.MSG)]
        user32.DispatchMessageW.restype = ctypes.c_ssize_t
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wt.MSG)]
        user32.TranslateMessage.restype = wt.BOOL
        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wt.HWND, ctypes.c_uint,
                                     ctypes.c_size_t, ctypes.c_ssize_t)

        def _wndproc(hwnd, msg, wparam, lparam):
            try:
                self.on_message(int(msg), int(wparam))
            except Exception as exc:  # noqa: BLE001 -- o proc nunca levanta
                self.log("POWER_RECOVERY_WNDPROC_FAILED msg=0x%04x error=%r"
                         % (int(msg), exc))
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._proc = WNDPROC(_wndproc)
        hinst = kernel32.GetModuleHandleW(None)

        class WNDCLASSEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_uint), ("style", ctypes.c_uint),
                ("lpfnWndProc", ctypes.c_void_p), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE),
                ("hIcon", wt.HICON), ("hCursor", ctypes.c_void_p),
                ("hbrBackground", ctypes.c_void_p), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON),
            ]

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = ctypes.cast(self._proc, ctypes.c_void_p)
        wc.hInstance = hinst
        wc.lpszClassName = self.CLASS_NAME
        user32.RegisterClassExW.argtypes = [ctypes.POINTER(WNDCLASSEXW)]
        if not user32.RegisterClassExW(ctypes.byref(wc)):
            err = ctypes.get_last_error()
            if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS (a restart)
                self.log("POWER_RECOVERY_CLASS_FAILED winerror=%d" % err)
                self._ready.set()
                return

        user32.CreateWindowExW.restype = wt.HWND
        # Parent = 0 (top-level) e TAMANHO ZERO: um broadcast chega-lhe, e nao ha'
        # pixel nenhum para ele mostrar.
        hwnd = user32.CreateWindowExW(0, self.CLASS_NAME, "", 0x80000000,
                                      0, 0, 0, 0, None, None, hinst, None)
        if not hwnd:
            self.log("POWER_RECOVERY_WINDOW_FAILED winerror=%d"
                     % ctypes.get_last_error())
            self._ready.set()
            return
        self.hwnd = int(hwnd)
        self._hwnd = self.hwnd
        self._tid = kernel32.GetCurrentThreadId()

        try:
            wtsapi = ctypes.WinDLL("wtsapi32.dll")
            wtsapi.WTSRegisterSessionNotification.argtypes = [wt.HWND, wt.DWORD]
            wtsapi.WTSRegisterSessionNotification.restype = wt.BOOL
            self._registered = bool(wtsapi.WTSRegisterSessionNotification(
                self.hwnd, NOTIFY_FOR_THIS_SESSION))
        except Exception as exc:  # noqa: BLE001
            self.log("POWER_RECOVERY_REGISTER_FAILED error=%r" % (exc,))
        self.log("POWER_RECOVERY_ATTACHED hwnd=%s own_window=%s session_notify=%s"
                 % (self.hwnd, str(self._own).lower(), str(self._registered).lower()))
        self._ready.set()

        msg = wt.MSG()
        while not self._stop.is_set():
            got = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if got in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def detach(self):
        try:
            if self._registered:
                import ctypes
                from ctypes import wintypes as wt
                w = ctypes.WinDLL("wtsapi32.dll")
                w.WTSUnRegisterSessionNotification.argtypes = [wt.HWND]
                w.WTSUnRegisterSessionNotification.restype = wt.BOOL
                w.WTSUnRegisterSessionNotification(self.hwnd)
        except Exception:  # noqa: BLE001
            pass
        self._registered = False
        self._stop.set()
        try:
            import ctypes
            from ctypes import wintypes as wt
            u = ctypes.WinDLL("user32", use_last_error=True)
            u.PostThreadMessageW.argtypes = [wt.DWORD, wt.UINT, wt.WPARAM, wt.LPARAM]
            if self._tid:
                u.PostThreadMessageW(self._tid, 0x0012, 0, 0)  # WM_QUIT
            if self._that_hwnd():
                u.DestroyWindow(self._hwnd)
        except Exception:  # noqa: BLE001
            pass
        self.log("POWER_RECOVERY_DETACHED hwnd=%s" % (self.hwnd,))

    def _that_hwnd(self):
        return bool(self._hwnd)

    # -- a decisao ---------------------------------------------------------
    def on_message(self, msg, wparam):
        event = classify(msg, wparam)
        if not event:
            return None
        acts = plan(event)
        self.fired.append({"event": event, "actions": list(acts)})
        self.log("POWER_RESUME event=%s msg=0x%04x wparam=0x%04x actions=%s"
                 % (event, msg, wparam, ",".join(acts) or "-"))
        for act in acts:
            fn = self.handlers.get(act)
            if fn is None:
                continue
            try:
                fn(event, act)
            except Exception as exc:  # noqa: BLE001 -- uma accao nao mata as outras
                self.log("POWER_RESUME_ACTION_FAILED event=%s action=%s error=%r"
                         % (event, act, exc))
        return acts
