"""O QUE O DONO ESCOLHEU PARA A LEGENDA -- persistido, nunca um literal.

O shell nasce antes do painel: uma escolha so' em memoria seria esquecida no
arranque seguinte. Vive aqui (1) `target_lang`, a lingua alvo da traducao
(ordem 2026-11-08: *"eu ja falei pra NAO traduzir entre pt br ingles e espanhol
entre si. mas pra traduzir o resto pra linguagem que eu escolhi pro sotto"*;
default `pt`, a regra das tres em `youtube_captions`) e (2) `opacity`/`plate`, o
ASPECTO da legenda nativa (dono, 2026-11-09: *"the background in the subtitles
is too wide. should be more concise and less bloaty."*): `opacity` 0.30..1.0
escala o alfa da PLACA/regua/LED e NUNCA a tinta do texto; `plate` e' `tight`
(a caixa abraca a linha medida, default) ou `normal` (o desenho de antes).
Nenhum caminho levanta -- ausente, partido ou fora do dominio cai no default --
e a escrita e' temporaria-e-renomeia, para um settings meio escrito nunca ser
lido como "sem escolha".

E (3) `capture_exclude`, o "modo stealth" da legenda -- a janela some de
OBS/Zoom/Teams/Discord e continua visivel para o dono. Ordem do dono,
2026-11-16, verbatim: *"retira o 'modo stealth' da legenda. deixa desativado por
padrao, e ativavel nas configs do sotto."* Por isso o default e'
`DEFAULT_CAPTURE_EXCLUDE = False`; quem quiser a esconder liga-a no painel. O
unico leitor da decisao e' `capture_exclusion.enabled()`, que aplica o override
`SOTTO_CAPTURE_EXCLUDE` por cima DESTE valor -- um dono, um predicado.
"""

from __future__ import annotations

import json
import os

DEFAULT_TARGET = 'pt'
DEFAULT_OPACITY = 1.0
MIN_OPACITY = 0.30
MAX_OPACITY = 1.0
PLATE_MODES = ('tight', 'normal')
DEFAULT_PLATE = 'tight'
#: O "modo stealth" desligado de fabrica (ordem do dono, 2026-11-16).
DEFAULT_CAPTURE_EXCLUDE = False

def path():
    """O ficheiro; `SOTTO_CAPTION_SETTINGS` desvia-o para os oraculos."""
    return os.environ.get('SOTTO_CAPTION_SETTINGS') or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), '_main', 'caption-settings.json')

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
    base = str(load().get('target_lang') or '').strip().lower().split('-')[0]
    return base or DEFAULT_TARGET

def visual():
    """O `{opacity, plate}` que o desenho APLICA -- o UNICO sitio do clamp."""
    data = load()
    try:
        alpha = float(data.get('opacity', DEFAULT_OPACITY))
    except (TypeError, ValueError):
        alpha = DEFAULT_OPACITY
    if alpha != alpha:                      # NaN
        alpha = DEFAULT_OPACITY
    plate = str(data.get('plate') or '').strip().lower()
    return {'opacity': max(MIN_OPACITY, min(MAX_OPACITY, alpha)),
            'plate': plate if plate in PLATE_MODES else DEFAULT_PLATE}

def save(settings):
    """Grava o dicionario. Devolve o caminho; falha de escrita nao levanta."""
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
    base = str(code or '').strip().lower().split('-')[0] or DEFAULT_TARGET
    settings = load()
    settings['target_lang'] = base
    save(settings)
    return base

def set_visual(opacity=None, plate=None):
    """Grava o aspecto e devolve o APLICADO (ja' preso ao dominio).

    `None` e' "nao mexer nesta chave": gravar so' a opacidade nao apaga a placa.
    """
    settings = load()
    if opacity is not None:
        settings['opacity'] = opacity
    if plate is not None:
        settings['plate'] = plate
    save(settings)
    return visual()


def capture_exclude():
    """O "modo stealth" guardado; ausente/partido/ilegivel = DESLIGADO.

    Nunca levanta, como `load()`. Aceita o booleano que `set_capture_exclude`
    escreve e as formas textuais que um ficheiro editado a mao pode ter -- mas
    so' o que diz SIM liga: o default tem de sobreviver a lixo no ficheiro.
    """
    raw = load().get('capture_exclude', DEFAULT_CAPTURE_EXCLUDE)
    if isinstance(raw, bool):
        return raw
    return str(raw or '').strip().lower() in ('1', 'true', 'on', 'yes')


def set_capture_exclude(want):
    """Grava a escolha e devolve o que ficou GRAVADO (bool)."""
    want = bool(want)
    settings = load()
    settings['capture_exclude'] = want
    save(settings)
    return capture_exclude()


# ── O ULTIMO DESENHO MEDIDO (2026-11-12) ────────────────────────────────────
# MEDIDO na sessao do dono (pid 46056, 19:41): a primeira linha pintou as
# 19:41:44.254 e a placa so' apareceu as 19:41:46.327 (`CAPTION_OVERLAY_THEME_
# APPLIED ... plate=yes alpha=219 why=page`), ou seja **2,07 s de texto sem
# fundo** -- verbatim: *"o background da legenda atrasou pra aparecer. entao a
# legenda ficou uns segundos sem background"*. A causa nao e' o desenho (a placa
# e' pintada no MESMO bitmap que os glifos): e' a JANELA nascer sem desenho,
# porque o payload que a pagina mede so' existe depois do DOM dela, e o
# `_brand_tokens_last` e' memoria do PROCESSO -- um arranque novo comeca vazio e
# repete os mesmos segundos.
# A CURA: o ultimo payload medido fica em DISCO e a janela nasce com ele. A
# placa passa a existir no primeiro pixel, como em qualquer arranque seguinte.
THEME_FILE = 'caption-theme.json'

def theme_path():
    """O ficheiro do ultimo desenho; `SOTTO_CAPTION_THEME` desvia-o (oraculos)."""
    return os.environ.get('SOTTO_CAPTION_THEME') or os.path.join(
        os.path.dirname(path()), THEME_FILE)

def theme():
    """O ultimo payload medido, ou `{}`. Nunca levanta.

    Um payload sem `rowBg`/`plate` nao serve para nada (o YouTube nao tem placa,
    e por isso nao e' um desenho) e nao e' devolvido: um `{}` diz "nao ha
    desenho guardado", que e' o que o chamador precisa de saber.
    """
    try:
        with open(theme_path(), 'r', encoding='utf-8') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    has_plate = bool(data.get('rowBg') or data.get('plate'))
    return data if has_plate else {}

def set_theme(tokens):
    """Grava o payload medido (temporario-e-renomeia). Devolve o caminho."""
    dest = theme_path()
    try:
        folder = os.path.dirname(dest)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = dest + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(tokens if isinstance(tokens, dict) else {}, fh,
                      indent=2, sort_keys=True)
            fh.write('\n')
        os.replace(tmp, dest)
    except OSError:
        pass
    return dest
