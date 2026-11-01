"""AS DUAS HOTKEYS DO SOTTO -- um passo por pressao, e nenhum relogio.

ORDEM DO DONO, 2026-11-01, verbatim:

    *"modifica a legenda ao vivo hotkey. bota o padrao como control espaco. e os
    painels deixa alt c. faz os paineis alternarem mesmo se eu deixar alt
    apertado o tempo inteiro e spammando c. alterna entre show e hide."*

O QUE ISTO SUBSTITUI, e porque e' que a substituicao e' uma REMOCAO. O contrato
de 2026-10-30 media a DURACAO da segurada (`GetAsyncKeyState` em cada volta do
pump) e decidia por ela: um toque era o painel de baixo, dois o da direita, e
>= 200 ms era a legenda ao vivo. Tres relogios a discordar (`HOTKEY_HOLD_MS`,
`HOTKEY_TAP_WINDOW_MS`, `HOLD_CEILING_MS`) e uma thread a fazer polling para
medir o que o dono ja' sabia. Ele nao pediu nenhum dos dois gestos: pediu
*"alterna entre show e hide"* e uma tecla separada para a legenda. Uma pressao
e' um passo -- o resto era instrumentacao nossa, e foi toda apagada com este
ficheiro (o oraculo `_main/altc-gesture-oracle.py` guarda a ausencia).

AS DUAS TECLAS, uma so' dona cada:

    Alt+C       UMA pressao = UM passo do ciclo dos paineis, imediato
    Ctrl+Space  UMA pressao = a legenda ao vivo liga/desliga

O CICLO DOS PAINEIS. Cada pressao MUDA o que esta' no ecra -- nunca ha uma
pressao que nao faca nada, e e' isso que faz o gesto funcionar com o Alt
fisicamente em baixo e o C a ser martelado: nao ha janela de toques, nao ha
limiar, nao ha adiamento, logo nao ha nada para o Alt preso estragar.

    escondido (ultimo show: painel)  -> faixa de BAIXO   (show)
    faixa de baixo no ecra           -> esconde          (hide)
    escondido (ultimo show: faixa)   -> painel da DIREITA (show)
    painel da direita no ecra        -> esconde          (hide)

Dez pressoes: dez mudancas de visibilidade, e os shows alternam
faixa, painel, faixa, painel, faixa. `next_surface` e' a regra inteira, pura,
para poder ser medida sem teclado e sem janela.

O VOCABULARIO DAS TECLAS vive aqui e em mais lado nenhum: o shell traduz os
NOMES dos modificadores nos bits do Win32 (`RegisterHotKey`) e a tecla no `vk`
que esta tabela devolve, e `hotkey_settings` valida o ficheiro do dono com o
mesmo parser. Duas tabelas de teclas seriam duas verdades, e a segunda envelhece
sozinha.
"""
from __future__ import annotations

#: A tecla dos PAINEIS. Ordem do dono, 2026-11-01: *"os painels deixa alt c"*.
PANELS_ACCELERATOR = 'Alt+C'

#: A tecla da LEGENDA AO VIVO. Ordem do dono, 2026-11-01: *"bota o padrao como
#: control espaco"*. E' tambem o valor que `hotkey_settings` devolve quando o
#: ficheiro da escolha nao existe ou esta' ilegivel.
LIVE_ACCELERATOR = 'Ctrl+Space'

#: Nome do modificador tal como o dono escreve -> nome canonico. `MENU` e
#: `SUPER` sao aceitos porque `parse_accelerator` do shell sempre os aceitou e
#: uma tecla que ja' funcionava nao pode deixar de funcionar.
MODIFIERS = {'ALT': 'alt', 'MENU': 'alt', 'CTRL': 'ctrl', 'CONTROL': 'ctrl',
             'SHIFT': 'shift', 'WIN': 'win', 'SUPER': 'win'}

#: A ordem em que o texto normalizado escreve os modificadores. Nao e' ranking:
#: e' o que faz `Ctrl+Alt+Space` ser sempre a MESMA string.
MODIFIER_ORDER = ('ctrl', 'alt', 'shift', 'win')
MODIFIER_LABELS = {'ctrl': 'Ctrl', 'alt': 'Alt', 'shift': 'Shift', 'win': 'Win'}

#: As teclas que NAO sao uma letra. `vk` e' o codigo virtual do Windows da
#: tecla (`VK_SPACE` == 0x20); uma letra e' `ord('C')`, que e' o mesmo numero
#: que o Windows usa para ela. O rotulo e' o que o ficheiro e o log escrevem.
KEY_TABLE = (
    ('Space', 0x20), ('Tab', 0x09), ('Enter', 0x0D), ('Esc', 0x1B),
    ('Backspace', 0x08), ('Insert', 0x2D), ('Delete', 0x2E),
    ('Home', 0x24), ('End', 0x23), ('PageUp', 0x21), ('PageDown', 0x22),
    ('Up', 0x26), ('Down', 0x28), ('Left', 0x25), ('Right', 0x27),
    ('F1', 0x70), ('F2', 0x71), ('F3', 0x72), ('F4', 0x73), ('F5', 0x74),
    ('F6', 0x75), ('F7', 0x76), ('F8', 0x77), ('F9', 0x78), ('F10', 0x79),
    ('F11', 0x7A), ('F12', 0x7B),
)
_KEYS = {label.upper(): vk for label, vk in KEY_TABLE}
_LABELS = {vk: label for label, vk in KEY_TABLE}


def parse_accelerator(text):
    """`'Alt+C'` -> `(('alt',), 0x43)`; `'Ctrl+Space'` -> `(('ctrl',), 0x20)`.

    Levanta `ValueError` para o que NAO e' uma tecla: um accelerador que o shell
    nao consegue traduzir em `RegisterHotKey` tem de ser recusado aqui, e nao
    numa falha de registo que deixa a app com uma tecla morta e um log obscuro.

    EXIGE PELO MENOS UM MODIFICADOR. Uma tecla global sem modificador escreve-se
    na app que o dono estiver a usar; nao ha gesto que justifique isso, e as duas
    teclas deste contrato tem as duas um.
    """
    mods: list[str] = []
    key = None
    for part in str(text or '').split('+'):
        token = part.strip()
        if not token:
            continue
        upper = token.upper()
        if upper in MODIFIERS:
            name = MODIFIERS[upper]
            if name in mods:
                raise ValueError(f'duplicate modifier {token!r} in {text!r}')
            mods.append(name)
        elif key is not None:
            raise ValueError(f'two keys ({key!r}, {token!r}) in {text!r}')
        elif len(upper) == 1:
            key = upper
        elif upper in _KEYS:
            key = upper
        else:
            raise ValueError(f'unsupported accelerator key {token!r}')
    if key is None:
        raise ValueError(f'no key in accelerator {text!r}')
    if not mods:
        raise ValueError(f'no modifier in accelerator {text!r} (a global key '
                         'without one would type into the owner\'s app)')
    return (tuple(name for name in MODIFIER_ORDER if name in mods),
            ord(key) if len(key) == 1 else _KEYS[key])


def normalise_accelerator(text):
    """O texto canonico (`'Ctrl+Space'`, `'Alt+C'`). Levanta como `parse_accelerator`."""
    mods, vk = parse_accelerator(text)
    key = _LABELS.get(vk) or chr(vk)
    return '+'.join([MODIFIER_LABELS[name] for name in mods] + [key])


def next_surface(visible, surface):
    """UM Alt+C -> UM passo. Devolve o que MOSTRAR, ou `None` para esconder.

    `visible` e' o que a JANELA mede (`IsWindowVisible`), nunca uma intencao: um
    `show` que falhou deixou o painel escondido e o ciclo tem de continuar de
    onde o dono esta' a ver.

    `surface` e' a ultima superficie APLICADA (`surface_applied`), e ela
    sobrevive ao `hide` de proposito -- e' essa memoria que faz o show seguinte
    alternar. Por isso o `hide_panel` do shell NAO limpa `surface_applied`
    (o oraculo prende as duas coisas juntas).
    """
    if visible:
        return None
    return 'panel' if str(surface or '') == 'strip' else 'strip'
