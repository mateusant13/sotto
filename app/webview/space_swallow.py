"""O `Ctrl+Space` SAI do resto do Windows enquanto a legenda o esta' a usar.

ORDEM DO DONO, verbatim (2026-11-06): *"control espaço pra ligar ou desligar a
legenda nao deve \"vazar\" pra outros apps. to usando control espaço pra ativar
a legenda quando vejo um video no youtube, e isso faz o espaço pausar o video."*

O QUE ESTAVA MEDIDO E ERRADO. `RegisterHotKey(MOD_CONTROL|VK_SPACE)` NAO tira a
tecla do caminho de input: o Windows entrega `WM_HOTKEY` ao processo que a
registou E continua a entregar o `WM_KEYDOWN`/`WM_CHAR` do espaco a' janela em
foco. Num browser isso e' o `space` do `<video>`: pausa. A docstring anterior do
`LiveHotkeyThread` afirmava o contrario ("nao entrega a tecla a' janela em
foco") -- era a premissa errada que produziu o sintoma que o dono descreveu.

O QUE SUBSTITUI A PREMISSA. Um hook de teclado de baixa prioridade
(`WH_KEYBOARD_LL`), instalado no fio do `LiveHotkeyThread` (o mesmo que ja' tem
fila e pump), que devolve 1 -- "engole" -- para o `VK_SPACE` quando TODAS estas
condicoes sao verdadeiras:

  * o hook esta' ARMADO (`LiveHotkeyThread` so' o arma quando
    `gaming_mode.live_hotkey_plan` diz `take`, isto e', fora de jogo e com a
    combinacao tomada);
  * o `Ctrl` esta' fisicamente em baixo (lido no instante do evento);
  * a tecla e' o espaco.

A CLASSE E' PURA (`classify_event`) e o estado e' MINIMO: o `keydown` engolido
liga `key_down_swallowed`, o `keyup` do espaco engole-se enquanto esse bit
estiver de pe' e limpa-o. Sem esse estado o app em foco receberia um `keyup`
de uma tecla cujo `keydown` nunca viu -- e um browser pode agir nesse `keyup`.
O bit tambem e' o que garante UMA alternancia por pressao: o auto-repeat do
Windows manda `keydown`s repetidos e nenhum deles alterna outra vez.

E' DE PROPOSITO QUE A DECISAO NAO ESTA' NO FIO DA SHELL. `_main/input-path-
oracle.py` (C1) exige ZERO `SetWindowsHookEx` e ZERO `WH_*_LL` no AST de
`sotto_webview.py`, e essa lei nasceu do rato que travava (docs/mouse-e-input.md
§5). A lei continua verdadeira para o caminho do rato e para a shell; esta e' a
UNICA excepcao, e ela e' medida pela ausencia do lado de la': o hook so' existe
enquanto o `Ctrl+Space` esta' tomado, e e' DESINSTALADO (`UnhookWindowsHookEx`)
antes de o jogo receber a tecla. Fora do fio `LiveHotkeyThread` nada neste
modulo e' chamado.

CUSTO: o callback corre no fio que instalou o hook, antes de o evento chegar a'
janela em foco. Ele faz UMA leitura de estado (`GetAsyncKeyState`, microssegundos)
e, quando engole, UMA chamada que o shell ja' usa para o `WM_HOTKEY`
(`hotkey_live` so' poe um pedido numa fila e volta). Nao pinta, nao abre janela,
nao mexe no audio.
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt

__all__ = [
    'KBDLLHOOKSTRUCT', 'SpaceSwallowHook', 'classify_event',
    'VK_SPACE', 'VK_CONTROL', 'WM_KEYDOWN', 'WM_KEYUP',
    'WM_SYSKEYDOWN', 'WM_SYSKEYUP', 'WH_KEYBOARD_LL',
]

WH_KEYBOARD_LL = 13
HC_ACTION = 0
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
VK_SPACE = 0x20
VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_MENU = 0x12          # Alt
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_SHIFT = 0x10
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LWIN = 0x5B
VK_RWIN = 0x5C

#: A ABI dos modificadores e' a do `RegisterHotKey` (a mesma que o
#: `parse_accelerator` do shell devolve). NAO e' uma segunda tabela de teclas:
#: sao os bits do Win32, como `MOD_NOREPEAT` na shell.
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008

#: O `LRESULT` do hook. `ctypes.c_ssize_t` e' o tamanho certo nos dois bit-ness
#: (o shell e' x64, mas a ABI nao se adivinha).
HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int,
                              wt.WPARAM, wt.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    """O que o Windows passa em `lParam` a um `WH_KEYBOARD_LL`."""

    _fields_ = [('vkCode', wt.DWORD),
                ('scanCode', wt.DWORD),
                ('flags', wt.DWORD),
                ('time', wt.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)]


#: AS PROTOTIPES SAO OBRIGATORIAS (medido 2026-11-06). Sem `restype`, o ctypes
#: trata `GetModuleHandleW` como `int` de 32 bits e TRUNCA o handle no x64; o
#: `SetWindowsHookExW` recebia um hMod invalido e devolvia **winerror=126**
#: (ERROR_MOD_NOT_FOUND). Com `hMod` correcto o hook instala (medido:
#: handle=45032163, `UnhookWindowsHookEx`=1).
_USER32 = ctypes.WinDLL('user32', use_last_error=True)
_KERNEL32 = ctypes.WinDLL('kernel32', use_last_error=True)
_KERNEL32.GetModuleHandleW.restype = ctypes.c_void_p
_KERNEL32.GetModuleHandleW.argtypes = [wt.LPCWSTR]
_USER32.SetWindowsHookExW.restype = ctypes.c_void_p
_USER32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, ctypes.c_void_p,
                                      wt.DWORD]
_USER32.UnhookWindowsHookEx.restype = ctypes.c_bool
_USER32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
_USER32.CallNextHookEx.restype = ctypes.c_ssize_t
_USER32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                   wt.WPARAM, wt.LPARAM]
_USER32.GetAsyncKeyState.restype = ctypes.c_short
_USER32.GetAsyncKeyState.argtypes = [ctypes.c_int]


def classify_event(message, vk, mods_down, armed, key_down_swallowed,
                   target_vk=VK_SPACE, required_mods=MOD_CONTROL):
    """A REGRA, pura: `(accao, next_key_down_swallowed, alternar)`.

    `mods_down`/`required_mods` usam os bits do `RegisterHotKey` (`MOD_*`): a
    tecla so' e' nossa quando TODOS os modificadores que a combinacao pede estao
    fisicamente em baixo. `accao` e' `'swallow'` (devolver 1) ou `'pass'`
    (chamar o proximo hook). `alternar` so' e' True no PRIMEIRO `keydown`
    engolido -- o auto-repeat que o Windows manda enquanto o dono segura a tecla
    nao pode alternar a legenda uma vez por repeticao. A funcao nao le' relogio
    nem global: e' a unica coisa que o oraculo tem de exercitar para provar a
    classificacao.
    """
    if not armed:
        # DESARMADO = A TECLA E' DE QUEM ESTA' EM FOCO. Em jogo o plano manda
        # desinstalar o hook; o `armed=False` e' a segunda tranca (o hook pode
        # estar instalado e ainda nao ter passado pelo pump).
        return 'pass', False, False
    if message in (WM_KEYDOWN, WM_SYSKEYDOWN):
        if (vk == target_vk
                and (mods_down & required_mods) == required_mods):
            return 'swallow', True, not key_down_swallowed
        return 'pass', key_down_swallowed, False
    if message in (WM_KEYUP, WM_SYSKEYUP):
        if vk == target_vk and key_down_swallowed:
            # O `keyup` da tecla cujo `keydown` engolimos: engole-se tambem, e
            # o estado fecha aqui (nao ha' tecla presa entre duas pressoes).
            return 'swallow', False, False
        return 'pass', key_down_swallowed, False
    return 'pass', key_down_swallowed, False


def _real_mods_down(user32):
    """Os modificadores fisicos agora, na ABI do `RegisterHotKey`."""
    mask = 0
    try:
        def down(*vks):
            return any(int(user32.GetAsyncKeyState(vk)) & 0x8000 for vk in vks)
        if down(VK_CONTROL, VK_LCONTROL, VK_RCONTROL):
            mask |= MOD_CONTROL
        if down(VK_MENU, VK_LMENU, VK_RMENU):
            mask |= MOD_ALT
        if down(VK_SHIFT, VK_LSHIFT, VK_RSHIFT):
            mask |= MOD_SHIFT
        if down(VK_LWIN, VK_RWIN):
            mask |= MOD_WIN
    except Exception:  # noqa: BLE001 -- sem leitura, o lado seguro e' NAO engolir
        return 0
    return mask


class SpaceSwallowHook(object):
    """O `WH_KEYBOARD_LL` do `Ctrl+Space`, com o ciclo de vida explicito.

    `user32`/`kernel32` sao injectaveis para o oraculo poder correr a CLASSE
    REAL contra um gravador (nenhum hook e' instalado nesse braco) e para o
    probe OS os usar reais. `armed` nunca e' inferido: quem chama diz quando a
    tecla e' nossa.
    """

    def __init__(self, on_toggle=None, log_fn=None, role='live',
                 user32=None, kernel32=None, mods_down=None,
                 target_vk=VK_SPACE, required_mods=MOD_CONTROL):
        self.on_toggle = on_toggle
        self.log_fn = log_fn or (lambda *a, **k: None)
        self.role = role
        #: A COMBINACAO VIVA. A tecla da legenda vem do ficheiro do dono
        #: (`hotkey_settings`), por isso o hook nao pode assumir ESPACO: ele
        #: recebe o VK e a mascara de modificadores que o `parse_accelerator`
        #: daquele fio produziu. O default e' a de fabrica (`Ctrl+Space`).
        self.target_vk = int(target_vk)
        self.required_mods = int(required_mods)
        #: As bibliotecas REAIS ja' tem as prototipes acima; as injectadas (o
        #: oraculo) nao precisam delas.
        self.user32 = user32 if user32 is not None else _USER32
        self.kernel32 = kernel32 if kernel32 is not None else _KERNEL32
        self.mods_down = mods_down or (lambda: _real_mods_down(self.user32))
        self.installed = False
        self.hook_handle = None
        self.armed = False
        self.swallowed = 0
        self.passed = 0
        self.toggles = 0
        self.key_down_swallowed = False
        self.last_error = None
        #: Referencia viva ao `HOOKPROC`: um callback em `ctypes` que o Python
        #: recolhe vira um ponteiro pendurado no processo do Windows.
        self._proc = None

    # -- ciclo de vida -----------------------------------------------------
    def install(self):
        """Instala o hook. Recusa-se se nao estiver armado (jogo/sem registo)."""
        if self.installed:
            return True
        if not self.armed:
            self.log_fn('SPACE_SWALLOW_SKIPPED role=%s why=not-armed'
                        % (self.role,))
            return False
        try:
            self._proc = HOOKPROC(self._on_event)
            hmod = self.kernel32.GetModuleHandleW(None)
            handle = self.user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc,
                                                   hmod, 0)
        except Exception as exc:  # noqa: BLE001 -- sem hook, o registo fica
            self.last_error = repr(exc)
            self.log_fn('SPACE_SWALLOW_INSTALL_FAILED role=%s winerror=%s '
                        'error=%r swallow=false '
                        'the_space_reaches_the_app=true'
                        % (self.role, self.last_error, exc))
            return False
        if not handle:
            self.last_error = ctypes.get_last_error()
            self.log_fn('SPACE_SWALLOW_INSTALL_FAILED role=%s winerror=%s '
                        'swallow=false the_space_reaches_the_app=true'
                        % (self.role, self.last_error))
            return False
        self.hook_handle = int(handle)
        self.installed = True
        self.key_down_swallowed = False
        self.log_fn('SPACE_SWALLOW_INSTALLED role=%s hook=%d '
                    'type=WH_KEYBOARD_LL vk=0x%02X mods=0x%02X swallow=true'
                    % (self.role, self.hook_handle, self.target_vk,
                       self.required_mods))
        return True

    def detach(self, why='stop'):
        """Retira o hook do caminho de input. Idempotente e nunca falha."""
        if not self.installed:
            return False
        handle = self.hook_handle
        try:
            ok = bool(self.user32.UnhookWindowsHookEx(handle))
            if not ok:
                self.log_fn('SPACE_SWALLOW_RELEASE_FAILED role=%s hook=%s '
                            'winerror=%s'
                            % (self.role, handle, ctypes.get_last_error()))
        except Exception as exc:  # noqa: BLE001 -- sair nao pode falhar
            self.log_fn('SPACE_SWALLOW_RELEASE_FAILED role=%s hook=%s error=%r'
                        % (self.role, handle, exc))
        self.installed = False
        self.hook_handle = None
        self.key_down_swallowed = False
        #: FORA DO CAMINHO = DESARMADO. Um callback atrasado (ou uma chamada
        #: directa do oraculo) depois do `detach` tem de PASSAR, senao a segunda
        #: tranca nao existiria: o jogo ficaria sem o espaco mesmo com o hook
        #: retirado.
        self.armed = False
        self.log_fn('SPACE_SWALLOW_RELEASED role=%s hook=%s why=%s'
                    % (self.role, handle, why))
        return True

    def set_armed(self, armed):
        """Arma/desarma SEM instalar: o `install` decide, o `detach` e' do plano."""
        self.armed = bool(armed)
        if not self.armed:
            self.key_down_swallowed = False
        return self.armed

    # -- o callback --------------------------------------------------------
    def _next(self, code, wparam, lparam):
        try:
            return self.user32.CallNextHookEx(None, code, wparam, lparam)
        except Exception:  # noqa: BLE001 -- sem cadeia, o evento passa
            return 0

    def _on_event(self, code, wparam, lparam):
        """O `HookProc` REAL. Rapido: uma leitura de estado, uma decisao, retorno."""
        if code != HC_ACTION:
            return self._next(code, wparam, lparam)
        vk = -1
        try:
            info = ctypes.cast(ctypes.c_void_p(lparam),
                               ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = int(info.vkCode)
        except Exception:  # noqa: BLE001 -- sem struct, decide-se 'pass'
            vk = -1
        try:
            mods_down = int(self.mods_down())
        except Exception:  # noqa: BLE001
            mods_down = 0
        action, self.key_down_swallowed, toggle = classify_event(
            int(wparam), vk, mods_down, bool(self.armed),
            self.key_down_swallowed, self.target_vk, self.required_mods)
        if action == 'swallow':
            self.swallowed += 1
            if toggle:
                self.toggles += 1
                self._fire_toggle()
            return 1
        self.passed += 1
        return self._next(code, wparam, lparam)

    def _fire_toggle(self):
        if self.on_toggle is None:
            return
        try:
            self.on_toggle()
        except Exception as exc:  # noqa: BLE001 -- um toggle perdido nao mata o hook
            self.log_fn('SPACE_SWALLOW_TOGGLE_FAILED role=%s error=%r'
                        % (self.role, exc))
