"""A LINGUA PARA QUE O SOTTO TRADUZ -- um valor PERSISTIDO, escolhido pelo dono.

As duas ordens, verbatim (2026-11-08):

    *"eu ja falei pra NAO traduzir entre pt br ingles e espanhol entre si. mas
    pra traduzir o resto pra linguagem que eu escolhi pro sotto. que no caso é
    pt br. entao eu to vendo um anime agora, e a legenda ta aparecendo japones."*
    *"e faz o botao de config pra eu escolher pra qual lingua traduzir."*

O que este ficheiro governa e' UMA coisa: o alvo da traducao para uma faixa cuja
lingua ORIGINAL esta' fora de `en`/`pt`/`es` (a regra das tres vive em
`youtube_captions.UNTRANSLATED_LANGS` e nao se toca aqui). O default e' `pt`
porque e' a lingua dele -- o anime japones que ele estava vendo saia em japones
porque o modulo servia `TARGET_LANG = 'en'`, e o clamp antigo devolvia o original
como ultimo recurso sem nunca pedir a traducao que ele quer.

POR QUE UM FICHEIRO E NAO UM LITERAL: a escolha dele tem de sobreviver ao
reinicio da shell. O `localStorage` do painel ja' guarda o que o seletor mostra,
mas o shell nasce antes do painel e o modulo e' importado por ele -- sem um valor
em disco, o primeiro video de cada arranque sairia na lingua do dia anterior.

O DEFAULT E' DE CLASSE E NAO DE CONVENIENCIA: `DEFAULT_TARGET = 'pt'` e' o valor
que responde quando nao ha ficheiro, quando o ficheiro esta' corrompido ou quando
a lingua gravada nao e' um codigo que o YouTube aceite. Nenhum caminho devolve
`''` -- um alvo vazio faria a traducao desaparecer em silencio.
"""

from __future__ import annotations

import json
import os

#: A lingua escolhida quando nao ha escolha registada. E' a lingua do dono.
DEFAULT_TARGET = 'pt'

#: Onde vive a escolha. `SOTTO_CAPTION_SETTINGS` desvia-o para um ficheiro
#: temporario -- e' assim que os oraculos provam a persistencia sem tocar na
#: escolha real dele (a mesma forma do `hotkey-settings.json`).
def _default_path():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(os.path.dirname(here))
    return os.path.join(root, '_main', 'caption-settings.json')


def path():
    return os.environ.get('SOTTO_CAPTION_SETTINGS') or _default_path()


def base_lang(code):
    """O BASE de um codigo ('pt-BR' -> 'pt'); vazio continua vazio."""
    return str(code or '').strip().lower().split('-')[0]


def load():
    """O dicionario em disco, ou `{}`. Nunca levanta."""
    try:
        with open(path(), 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def target_lang():
    """A lingua-alvo, ja' normalizada. NUNCA vazia (ver `DEFAULT_TARGET`)."""
    base = base_lang(load().get('target_lang'))
    return base or DEFAULT_TARGET


def save(settings):
    """Grava o dicionario. Devolve o caminho; falha de escrita nao levanta.

    A escrita e' TEMPORARIA-E-RENOMEIA: um ficheiro de settings meio escrito
    seria lido pelo proximo arranque como "sem escolha", e o dono veria a lingua
    dele trocada sem ter tocado em nada.
    """
    dest = path()
    try:
        folder = os.path.dirname(dest)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = dest + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(settings, fh, indent=2, sort_keys=True)
            fh.write('\n')
        os.replace(tmp, dest)
    except OSError:
        pass
    return dest


def set_target_lang(code):
    """Grava a escolha e devolve o base aplicado (`''` volta ao default)."""
    base = base_lang(code) or DEFAULT_TARGET
    settings = load()
    settings['target_lang'] = base
    save(settings)
    return base
