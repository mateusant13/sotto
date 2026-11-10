# NO-BUG: Portao da SEGUNDA FONTE da legenda do YouTube (`youtube_cdp_source.py`). -- trabalho de CAPACIDADE/observabilidade pedido pelo dono; nao corresponde a nenhum id de `_main/bug-ledger.json`, e declarado aqui em vez de inventar um id.
"""Portao da SEGUNDA FONTE da legenda do YouTube (`youtube_cdp_source.py`).

POR QUE ESTE FICHEIRO EXISTE

Com a aba do YouTube em segundo plano o Chrome deixa de expor a legenda na arvore
de acessibilidade (medido 2026-11-03: 3 minutos com um unico `YOUTUBE_CAPTION`, e
um cliente UIA novo noutro processo tambem vazio). A CDP le' o DOM do player e
resolve isso -- mas um caminho novo sem portao e' uma promessa. Estas arms
EXECUTAM as decisoes reais do modulo, nao procuram texto:

  A1 linhas      -- a resposta da pagina vira LINHAS do player, com a geometria de
                    cada filho; uma linha sem texto nao e' linha.
  A2 lixo        -- JSON invalido, lista, `null`: None. Nunca uma linha inventada.
  A3 identidade  -- com o id do video declarado, so' essa aba; com DUAS abas e sem
                    id, `ambiguous` (nunca se adivinha qual video esta' no ecra).
  A4 relogio     -- `t`/`paused` do `video.currentTime` chegam ao consumidor e um
                    `t` que nao e' numero vira None, nunca 0.0.
  A5 recorte     -- a expressao que corre na pagina recorta as linhas pelo
                    `overflow: hidden` do `.caption-window` (as que rolaram para
                    fora continuam no DOM e nao estao no ecra).
  A6 sem-foco    -- NINGUEM pede `Emulation.setFocusEmulationEnabled`: medido lado
                    a lado (20 leituras cada), ele leva a mediana de 2-5 ms para
                    108 ms e o p90 para 5 s -- o instrumento a criar a lentidao que
                    depois mede.
  A7 um-produtor -- a shell marca a pintura como fresca quando a leitura devolve
                    linhas, para o re-render da faixa a 60 ms nao alternar com ela
                    no mesmo ecra.

`--neg-arm` muta uma COPIA do modulo em tres sitios e exige que as arms
correspondentes caiam. Sem isso o portao seria uma lista de verdades sobre si
mesmo.
"""

from __future__ import annotations

import argparse
import ast
import bisect
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, '..', 'app', 'webview')
MODULE = os.path.join(APP, 'youtube_cdp_source.py')
SHELL = os.path.join(APP, 'sotto_webview.py')
INSTRUMENT = os.path.join(HERE, '_yt-live-latency.py')


def _load(path, name):
    import importlib.util as _iu
    spec = _iu.spec_from_file_location(name, path)
    mod = _iu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read(path):
    return io.open(path, encoding='utf-8', errors='replace').read()


def _reveal():
    """O motor de desenho REAL (`youtube_reveal`), para julgar o payload."""
    if APP not in sys.path:
        sys.path.insert(0, APP)
    import youtube_reveal
    return youtube_reveal


def _shell_methods(shell_path, names):
    """Os metodos REAIS do shell, extraidos por `ast` e compilados sozinhos.

    Importar `sotto_webview` carregaria WebView2; os metodos que interessam sao
    puros o suficiente para correr sobre um dublê (`_NS`). O que corre e' o texto
    do ficheiro que embarca -- nao uma copia escrita aqui.
    """
    src = _read(shell_path)
    tree = ast.parse(src)
    nodes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in names:
            nodes[node.name] = node
    ns = {'log': lambda *_a, **_k: None, 'time': time, 'json': json,
          'bisect': bisect}
    out = {}
    for name, node in nodes.items():
        exec(compile(ast.Module(body=[node], type_ignores=[]),
                     shell_path, 'exec'), ns)
        out[name] = ns[name]
    return out


class _NS(object):
    """Dublê do shell: os metodos extraidos leem e escrevem ESTES atributos."""

    def __init__(self, **kw):
        for key, value in kw.items():
            setattr(self, key, value)


def _fake_overlay():
    calls = {'show': [], 'set_text': [], 'hide': [], 'work_area': []}

    class _Ov(object):
        hwnd = 4242

        def show(self, on):
            calls['show'].append(bool(on))

        def hide(self):
            calls['hide'].append(True)

        def set_work_area(self, *_a, **_k):
            calls['work_area'].append(True)

        def set_text(self, *a, **k):
            calls['set_text'].append((a, k))

    return _Ov(), calls


def _probe(video_id, visible, focused, advance=0.6, paused=False, t1=100.0):
    """A forma de uma sonda real (`_probe_one`), com foco/visibilidade."""
    return {'videoId': video_id, 't0': t1 - advance, 't1': t1,
            'advance': advance, 'paused': paused, 'ended': False, 'rs': 4,
            'visible': visible, 'focused': focused,
            'tab': {'url': 'https://www.youtube.com/watch?v=' + video_id,
                    'title': video_id + ' - YouTube'}}


_ROWS = [
    {'index': 0, 'text': 'hello big world',
     'words': [{'start': 9.6, 'text': 'hello'},
               {'start': 9.9, 'text': 'big'},
               {'start': 10.4, 'text': 'world'}],
     'start': 9.5, 'end': 10.6, 'cap': None},
    {'index': 1, 'text': 'next line',
     'words': [{'start': 10.3, 'text': 'next'},
               {'start': 10.5, 'text': 'line'}],
     'start': 10.2, 'end': 11.0, 'cap': None},
]


def _texts(frames):
    return [mark['text'] for mark in frames]


def _arm_pausa_corta_a_pintura(mod, shell_path):
    """1. PAUSAR O VIDEO CORTA A PINTURA NA MESMA LEITURA (dono, 2026-11-06).

    *"se eu pauso o video, a legenda do sotto continua por mais uns 2
    segundos."* MEDIDO no log dele: 13,8 s de `paused=True` com `paint_t` a
    andar +0,95 s e a linha a crescer de 11 para 14 palavras -- o overlay revela
    contra o relogio do player e nada nesse motor sabe o que e' uma pausa.

    O payload congelado e' julgado pelo MOTOR REAL (`youtube_reveal.frame`):
    com `end=None` e sem relogio de palavras, 30 s de relogio depois tem de
    desenhar o MESMO texto. O controle ao lado: as linhas cruas CRESCEM.
    """
    yrev = _reveal()
    frozen = mod.freeze_rows(_ROWS, 10.0)
    # CONTROLE: as linhas CRUAS continuam a crescer com o relogio (10,4 s de
    # relogio mostrariam 'world'), e a congelada nao.
    grew = _texts(yrev.frame(_ROWS, 10.45))
    at10 = _texts(yrev.frame(frozen, 10.0))
    at40 = _texts(yrev.frame(frozen, 40.0))
    mod_ok = (at10 == at40 == ['hello big']
              and 'hello big world' in grew and grew != at10)

    fns = _shell_methods(shell_path, {'_yt_cue_payload'})
    cue = {'start': 9.5, 'end': 11.0, 'text': 'hello big world',
           'words': [{'start': 9.6, 'text': 'hello'},
                     {'start': 9.9, 'text': 'big'},
                     {'start': 10.4, 'text': 'world'}]}
    stub = _NS(_yt_anchor=(10.0, time.monotonic()), _yt_track={'cues': [cue]},
               yt_cdp_rate=1.0, yt_cdp_paused=True, yt_cdp_ended=False)
    payload = fns['_yt_cue_payload'](stub)
    shell_ok = bool(payload) and payload.get('paused') is True
    if shell_ok:
        p10 = _texts(yrev.frame(payload['rows'], payload['t']))
        p40 = _texts(yrev.frame(payload['rows'], payload['t'] + 30.0))
        shell_ok = (p10 == p40 == ['hello big']
                    and all(r.get('end') is None and not r.get('words')
                            for r in payload['rows']))
    stopped = (mod.player_stopped({'paused': True}) is True
               and mod.player_stopped({'ended': True}) is True
               and mod.player_stopped({'paused': False, 'ended': False}) is False
               and mod.player_stopped({}) is False)
    ok = mod_ok and shell_ok and stopped
    return ok, ('freeze=%r grew=%r shell=%r payload=%r'
                % (at10, grew, shell_ok,
                   (payload or {}).get('paused')))


def _arm_tick_da_pausa(shell_path):
    """1b. A PAUSA NAO CONGELA O ECRA -- e o desenho NORMAL continua a sair.

    O CONTRATO MUDOU EM 2026-11-09, por ordem do dono, verbatim: *"quando eu
    deixo o video pausado, a legenda fica ao vivo, quando eu pauso, ela volta e
    fica travada em outro momento"*. A arm antiga exigia o desenho CONGELADO que
    a borda da pausa fazia no `_tick` (cura de 2026-11-06) -- e esse desenho era
    justamente a legenda a ficar travada num momento que nao e' o da pausa. Quem
    apaga agora e' o observador (`youtube-paused`/`youtube-ended`) e o piso de
    `_caption_idle_hide`; um tick de pausa NAO pinta.

    Duas metades, porque a cura podia ser "nao pintar nada nunca": um tick de
    pausa sem linha nova nao empurra NADA, e um tick com linha nova empurra.
    """
    fns = _shell_methods(shell_path, {'_tick'})
    pushes = []
    shell = _NS(push_caption_to_window=lambda *a, **k: pushes.append((a, k)),
                external_caption=lambda *a, **k: pushes.append((a, k)),
                external_captions_available=False)
    frozen_cue = {'rows': [{'index': 0, 'text': 'a frase', 'words': [],
                            'start': 0.0, 'end': None, 'cap': None}],
                  't': 10.0, 'at': 0.0, 'rate': 1.0, 'paused': True}
    watcher = _NS(shell=shell, _yt_pause_epoch=1, _yt_pause_epoch_seen=None,
                  yt_cdp_paused=True, yt_cdp_ended=False,
                  last_line='a frase', last_rows=['a frase'],
                  last_source='external:youtube:track',
                  last_change=time.monotonic(), last_seen=time.monotonic(),
                  finalized=True, _released_for_silence=False,
                  _yt_cue_payload=lambda: frozen_cue,
                  _yt_prof=lambda *_a, **_k: None,
                  STABLE_FINAL_S=1.0, RELEASE_S=6.0, YT_RELEASE_S=25.0,
                  yt_frame_key=None, _release=lambda _r: None)
    # METADE 1 -- SEM LINHA NOVA neste tick: o caso normal com o video parado.
    fns['_tick'](watcher, [], True)
    quiet = len(pushes)
    # METADE 2 -- COM LINHA NOVA: o desenho de sempre tem de sair.
    watcher._yt_pause_epoch_seen = None
    # `got` e' uma LISTA de `(fonte, linhas)` -- o formato do leitor real.
    fns['_tick'](watcher, [('external:youtube:track', ['outra frase'])], True)
    drawn = len(pushes) - quiet
    ok = quiet == 0 and drawn == 1
    detail = 'pausa_sem_linha=%d com_linha=%d' % (quiet, drawn)
    return ok, detail


def _arm_duas_abas_primeiro_plano(mod):
    """2. DUAS ABAS: MANDAM O PRIMEIRO PLANO E O QUE TOCA (dono, 2026-11-06).

    Verbatim: *"abrir outro video e ter os dois tocando ao mesmo tempo, ainda
    continua o ultimo video, inves de dar prioridade ao novo. e obviamente, se
    eu voltasse pro outro video, daria prioridade pro outro video."*

    MEDIDO no log dele antes da cura: `YOUTUBE_TARGET pick=tnBpieBy2GY
    why=declared declared=tnBpieBy2GY tabs=2` -- o id declarado nunca deixava a
    testemunha do alt-tab (visivel+focada) correr.
    """
    a_bg = _probe('AAAAAAAAAAA', 'hidden', False, advance=0.6, t1=120.0)
    b_fg = _probe('BBBBBBBBBBB', 'visible', True, advance=0.6, t1=80.0)
    both = mod.choose_target([a_bg, b_fg])
    # alt-tab DE VOLTA: A passa a ser a visivel+focada
    a_fg = _probe('AAAAAAAAAAA', 'visible', True, advance=0.6, t1=121.0)
    b_bg = _probe('BBBBBBBBBBB', 'hidden', False, advance=0.6, t1=81.0)
    back = mod.choose_target([b_bg, a_fg])
    # video NOVO numa aba nova, em primeiro plano
    c_new = _probe('CCCCCCCCCCC', 'visible', True, advance=0.6, t1=3.0)
    new = mod.choose_target([a_bg, b_bg, c_new])
    # pausar o que ele esta' a ver NAO entrega o ecra ao video de tras
    paused_fg = _probe('AAAAAAAAAAA', 'visible', True, advance=0.0,
                       paused=True, t1=130.0)
    hold = mod.choose_target([paused_fg, b_bg])
    # Chrome SEM foco (alt-tab para outra app): visivel+sem foco nao decide;
    # o titulo da janela e' a ultima aba activa, e o que TOCA decide sem ele.
    nofocus_a = _probe('AAAAAAAAAAA', 'visible', False, advance=0.0,
                       paused=True, t1=130.0)
    nofocus_b = _probe('BBBBBBBBBBB', 'visible', False, advance=0.6, t1=90.0)
    by_title = mod.choose_target([nofocus_a, nofocus_b],
                                 window_title='AAAAAAAAAAA - YouTube')
    by_play = mod.choose_target([nofocus_a, nofocus_b])
    # O ID DECLARADO NAO PASSA A' FRENTE DO TITULO (a ordem antiga)
    tabs = [{'url': 'https://www.youtube.com/watch?v=AAAAAAAAAAA',
             'title': 'AAAAAAAAAAA - YouTube'},
            {'url': 'https://www.youtube.com/watch?v=BBBBBBBBBBB',
             'title': 'BBBBBBBBBBB - YouTube'}]
    title_first, why_t = mod.pick_target(tabs, 'AAAAAAAAAAA',
                                         'BBBBBBBBBBB - YouTube')
    ok = (both == ('BBBBBBBBBBB', 'foreground')
          and back == ('AAAAAAAAAAA', 'foreground')
          and new == ('CCCCCCCCCCC', 'foreground')
          and hold == ('AAAAAAAAAAA', 'foreground')
          and by_title == ('AAAAAAAAAAA', 'window-title')
          and by_play == ('BBBBBBBBBBB', 'playing')
          and title_first is tabs[1] and why_t == 'window-title')
    return ok, ('both=%r back=%r new=%r hold=%r title=%r play=%r pt=%s'
                % (both, back, new, hold, by_title, by_play, why_t))


def _arm_troca_limpa_o_estado(mod):
    """2b. UMA TROCA DE ABA NAO PODE SERVIR A FOTO DA ANTERIOR (2026-11-06).

    O canal de pintura nao leva `videoId` (`src=external:youtube:track`): uma
    foto publicada antes da troca e' indistinguivel de uma nova. `_adopt_tab`
    zera-a; `selected_video_id()` diz a verdade ao laco da shell.
    """
    src = mod.CdpCaptionSource(port=1, log=lambda _m: None)
    tab_a = {'webSocketDebuggerUrl': 'ws://x/AAAAAAAAAAA',
             'url': 'https://www.youtube.com/watch?v=AAAAAAAAAAA'}
    tab_b = {'webSocketDebuggerUrl': 'ws://x/BBBBBBBBBBB',
             'url': 'https://www.youtube.com/watch?v=BBBBBBBBBBB'}
    src._adopt_tab(tab_a, 'AAAAAAAAAAA')
    src._publish({'stamp': time.monotonic(), 'rows': ['linha do A'],
                  'items': [{'text': 'linha do A'}], 'videoId': 'AAAAAAAAAAA',
                  'why': 'painted'})
    before = src.snapshot(max_age=60.0)
    src._adopt_tab(tab_b, 'BBBBBBBBBBB')
    after = src.snapshot(max_age=60.0)
    ok = (before is not None and before.get('videoId') == 'AAAAAAAAAAA'
          and after is None
          and src.selected_video_id() == 'BBBBBBBBBBB')
    return ok, ('before=%r after=%r selected=%r'
                % ((before or {}).get('videoId'), after,
                   src.selected_video_id()))


def _arm_reavalia_sem_esperar(mod):
    """2c. A ESCOLHA E' RE-AVALIADA EM ABA NOVA / TROCA DE FOCO (2026-11-06).

    ERA 10 s de cache (`PLAYING_PROBE_TTL_S`) -- 10 s de legenda do video
    errado depois de um alt-tab. Agora: a ASSINATURA da lista de abas invalida a
    escolha na hora, e com duas abas o TTL e' 1 s. O relogio e' falso (`mod.time`)
    para o teste nao dormir.
    """
    calls = []
    real_pick = mod.pick_playing
    real_time = mod.time

    class _Clock(object):
        now = 1000.0

        @staticmethod
        def monotonic():
            return _Clock.now

    def fake_pick(tabs, previous='', connect=None, timeout=1.0, gap_s=0.12,
                  window_title='', declared='', budget_s=None, log=None):
        calls.append(str((tabs or [{}])[0].get('url') or ''))
        tab = (tabs or [{}])[0]
        vid = str(tab.get('url') or '').rsplit('v=', 1)[-1]
        return tab, vid, 'foreground'

    tab_a = {'webSocketDebuggerUrl': 'ws://x/A',
             'url': 'https://www.youtube.com/watch?v=AAAAAAAAAAA'}
    tab_b = {'webSocketDebuggerUrl': 'ws://x/B',
             'url': 'https://www.youtube.com/watch?v=BBBBBBBBBBB'}
    try:
        mod.pick_playing = fake_pick
        mod.time = _Clock
        src = mod.CdpCaptionSource(port=1, log=lambda _m: None)
        src._probe_connect = object()
        one = src._playing_pick_for([tab_a])
        again = src._playing_pick_for([tab_a])          # cache (1 aba, TTL 10 s)
        cached_ok = (len(calls) == 1 and one == again)
        # ABA NOVA: assinatura diferente -> sonda imediata, mesmo "no mesmo s"
        two = src._playing_pick_for([tab_b, tab_a])
        new_ok = (len(calls) == 2 and two[1] == 'BBBBBBBBBBB')
        # TROCA DE FOCO com as MESMAS abas: 1,1 s depois o TTL multi-aba expira
        # e a sonda volta a correr (o first da lista passa a ser A).
        _Clock.now += 1.1
        swapped = src._playing_pick_for([tab_a, tab_b])
        focus_ok = (len(calls) == 3 and swapped[1] == 'AAAAAAAAAAA')
        # UMA aba e 5 s: continua em cache (o TTL de 10 s vale uma sonda por aba)
        src2 = mod.CdpCaptionSource(port=1, log=lambda _m: None)
        src2._probe_connect = object()
        calls[:] = []
        src2._playing_pick_for([tab_a])
        _Clock.now += 5.0
        src2._playing_pick_for([tab_a])
        single_ok = (len(calls) == 1)
    finally:
        mod.pick_playing = real_pick
        mod.time = real_time
    ok = cached_ok and new_ok and focus_ok and single_ok
    return ok, ('cache=%s newtab=%s focus=%s single=%s calls=%d'
                % (cached_ok, new_ok, focus_ok, single_ok, len(calls)))


def _arm_desligar_em_pausa(shell_path):
    """3. DESLIGAR + PAUSA NAO DEIXA A LEGENDA PRESA (dono, 2026-11-06).

    Verbatim: *"ela tambem buga se eu desativo ela e o video ao mesmo tempo (ja
    que o control espaco passa pelo pause do video)"*. Duas metades, ambas as
    funcoes REAIS:

      (a) O INTERRUPTOR em pausa devolve a linha do player por velha que seja --
          MEDIDO no log dele: `CAPTION_WINDOW_REPLAY_SKIPPED age_ms=3092` com o
          video parado e o ecra VAZIO ate' o video voltar a andar. Fora da pausa
          o limite de 2 s fica (o jumpscare).
      (b) DESLIGAR e' deterministico e idempotente: o slot morre, o epoch sobe,
          o temporizador de silencio morre, e um slot com o epoch velho -- a
          corrida do `Ctrl+Space` com a pausa -- nao pinta.
    """
    fns = _shell_methods(shell_path, {'_caption_replay_allowed',
                                      '_set_live_enabled',
                                      'show_caption_window',
                                      '_drain_caption_pending'})
    allowed = fns['_caption_replay_allowed']
    rule = (allowed('linha', 30000, 2.0, True, True) is True
            and allowed('linha', 500, 2.0, False, True) is True
            and allowed('linha', 30000, 2.0, False, True) is False
            and allowed('', 0, 2.0, True, True) is False
            and allowed('linha', 30000, 2.0, True, False) is False)

    # (a) o interruptor REAL, em tres estados
    pushes = []
    stub = _NS(CAPTION_REPLAY_MAX_S=2.0, _caption_painted='linha do player',
               _caption_painted_at=time.time() - 30.0, yt_source_paused=True,
               _last_caption_was_player=True,
               _caption_wanted_store=lambda _on: None,
               show_caption_window=lambda _on: True,
               push_caption_to_window=lambda *a, **k: pushes.append((a, k)))
    fns['_set_live_enabled'](stub, {'on': True})
    replay_paused = len(pushes) == 1
    pushes[:] = []
    stub.yt_source_paused = False
    fns['_set_live_enabled'](stub, {'on': True})
    replay_playing_old = len(pushes) == 0
    stub.yt_source_paused = True
    stub._caption_painted = ''
    fns['_set_live_enabled'](stub, {'on': True})
    replay_empty = len(pushes) == 0

    # (b) OFF real, duas vezes (idempotente), com um slot armado antes
    ov, calls = _fake_overlay()
    timer = {'cancelled': False}

    class _Timer(object):
        def cancel(self):
            timer['cancelled'] = True

    off = _NS(caption_overlay=ov, _caption_window_shown=True,
              _caption_pending=(time.time() - 1.0, 'VELHA', None, 7),
              _source_epoch=7, _caption_drain_posted=True,
              _caption_idle_timer=_Timer(), _caption_wanted=False,
              _caption_painted='VELHA', _caption_painted_at=time.time(),
              _last_caption_was_player=True, _caption_coalesced=0,
              _overlay_pushes=0, _caption_pending_instant=True,
              _caption_pending_cue=None, _caption_pending_tap_ms=None,
              display={}, work_area=lambda: None,
              exec_js_post=lambda _js: True,
              _caption_lag_note=lambda *_a, **_k: None,
              _post=lambda fn: fn())
    fns['show_caption_window'](off, False)
    fns['show_caption_window'](off, False)
    off_ok = (off._caption_pending is None
              and off._caption_drain_posted is False
              and off._caption_window_shown is False
              and off._source_epoch > 7
              and timer['cancelled'] is True
              and calls['show'] == [False, False])
    # A CORRIDA: o slot foi lido ANTES do desligar (epoch velho, flag ja' OFF).
    off._caption_pending = (time.time() - 1.0, 'FANTASMA', None, 7)
    fns['_drain_caption_pending'](off)
    no_resurrect = (calls['set_text'] == [] and True not in calls['show'])
    # e o controle: com o epoch de AGORA o mesmo drain pinta (a arm nao e' cega)
    off._caption_pending = (time.time() - 1.0, 'NOVA', None, off._source_epoch)
    off._caption_wanted = True
    fns['_drain_caption_pending'](off)
    drain_alive = len(calls['set_text']) == 1 and calls['show'][-1] is True
    ok = (rule and replay_paused and replay_playing_old and replay_empty
          and off_ok and no_resurrect and drain_alive)
    return ok, ('rule=%s replay=%s/%s/%s off=%s nores=%s alive=%s'
                % (rule, replay_paused, replay_playing_old, replay_empty,
                   off_ok, no_resurrect, drain_alive))


def arms(module_path=MODULE, shell_path=SHELL, instrument_path=INSTRUMENT):
    # `module_path=None` = o modulo REAL, so' o SHELL mutado (A11 vive na shell).
    module_path = module_path or MODULE
    mod = _load(module_path, 'yt_cdp_under_test')
    shell = _read(shell_path)
    out = []

    # A1 -- linhas
    payload = ('{"videoId":"abc","title":"t","why":"painted","rows":['
               '{"text":"  ola   mundo ","items":['
               '{"text":"ola","left":"10.6","top":5,"right":20,"bottom":15},'
               '{"text":"mundo","left":25,"top":5.4,"right":40,"bottom":15}]},'
               '{"text":"   ","items":[{"text":"x","left":1,"top":1,"right":2,"bottom":3}]}]}')
    snap = mod.parse_snapshot(payload)
    a1 = (snap is not None and snap["rows"] == ["ola mundo"]
          and [i["text"] for i in snap["items"]] == ["ola", "mundo"]
          and snap["items"][0]["left"] == 10)
    out.append(("linhas-do-player", a1, "rows=%r" % (snap or {}).get("rows")))

    # A1-bis -- O MARCADOR DE FALA DO PLAYER NAO PASSA (dono, 2026-11-08,
    # verbatim: *"youtube escreve >> em algumas legendas. nao transmita iss pro
    # sotto"*). O `>>` chega em tres formas (a entidade `&gt;&gt;` antes de o DOM
    # descodificar, o `>>` ja' descodificado, e o `\u203a\u203a` da faixa
    # automatica) e em DUAS posicoes: a abrir a linha e no MEIO dela, quando o
    # painel junta dois segmentos. As tres linhas e os tres segmentos saem limpos.
    marker_payload = ('{"videoId":"abc","why":"painted","rows":['
                      '{"text":"&gt;&gt; Nossa.","items":['
                      '{"text":"&gt;&gt;","left":0,"top":0,"right":9,"bottom":9},'
                      '{"text":"Nossa.","left":10,"top":0,"right":60,"bottom":9}]},'
                      '{"text":"da wave. >> Nossa.","items":['
                      '{"text":"da wave.","left":0,"top":20,"right":70,"bottom":29},'
                      '{"text":">>","left":71,"top":20,"right":80,"bottom":29},'
                      '{"text":"Nossa.","left":81,"top":20,"right":130,"bottom":29}]},'
                      '{"text":"\u203a\u203a ok","items":['
                      '{"text":"ok","left":0,"top":40,"right":20,"bottom":49}]}],'
                      '"segs":["&gt;&gt; Nossa.","da wave.","Nossa."]}')
    msnap = mod.parse_snapshot(marker_payload)
    a1b = (msnap is not None
           and msnap["rows"] == ["Nossa.", "da wave. Nossa.", "ok"]
           and [i["text"] for i in msnap["items"]]
           == ["Nossa.", "da wave.", "Nossa.", "ok"]
           and msnap["segs"] == ["Nossa.", "da wave.", "Nossa."])
    out.append(("sem-marcador-de-fala", a1b,
                "rows=%r segs=%r items=%r" % (
                    (msnap or {}).get("rows"), (msnap or {}).get("segs"),
                    [i["text"] for i in (msnap or {}).get("items") or []])))

    # A2 -- lixo
    a2 = (mod.parse_snapshot("nao e json") is None
          and mod.parse_snapshot("[]") is None
          and mod.parse_snapshot("null") is None)
    out.append(("sem-linha-inventada", a2, "lixo=None"))

    # A3 -- identidade
    tabs = [{"url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
             "webSocketDebuggerUrl": "ws1"},
            {"url": "https://www.youtube.com/watch?v=BBBBBBBBBBB",
             "webSocketDebuggerUrl": "ws2"}]
    pick_named, why_named = mod.pick_target(tabs, "BBBBBBBBBBB")
    pick_amb, why_amb = mod.pick_target(tabs, "")
    pick_absent, why_absent = mod.pick_target(tabs, "CCCCCCCCCCC")
    a3 = (pick_named is tabs[1] and why_named == "named"
          and pick_amb is None and why_amb == "ambiguous"
          and pick_absent is None and why_absent == "video-not-open")
    out.append(("identidade-do-video", a3,
                "%s/%s/%s" % (why_named, why_amb, why_absent)))

    # A4 -- relogio
    snap2 = mod.parse_snapshot('{"t": 34.571, "paused": true, "rows": []}')
    snap3 = mod.parse_snapshot('{"t": "abc", "paused": null, "rows": []}')
    a4 = (snap2["t"] == 34.571 and snap2["paused"] is True
          and snap3["t"] is None and snap3["paused"] is None)
    out.append(("relogio-do-player", a4, "t=%r/%r" % (snap2["t"], snap3["t"])))

    # A5 -- recorte do clip
    js = mod.EXTRACT_JS
    a5 = ("overflowY" in js and "0.5 * h" in js and "getBoundingClientRect" in js)
    out.append(("recorte-do-clip", a5, "half-line=%s" % ("0.5 * h" in js)))

    # A6 -- sem focus emulation em sitio nenhum do produto
    # So' CODIGO conta: o comentario do instrumento e' a medicao que justifica a
    # regra (mediana 2-5 ms sem ele, 108 ms com ele) e tem de sobreviver a ela.
    offenders = []
    for path in (shell, instrument_path, MODULE):
        if not os.path.exists(path):
            continue
        text = _read(path)
        for match in re.finditer(r"\(\s*['\"]Emulation\.setFocusEmulationEnabled['\"]"
                                 r"|\.setFocusEmulationEnabled\s*\(", text):
            # So' a TUPLA ou a CHAMADA contam. A prosa (docstring, comentario) que
            # cita o nome para explicar a medicao nao e' um pedido a ninguem.
            line = text[:match.start()].rsplit(nl, 1)[-1]
            if line.lstrip().startswith(('#', '*', '"""', "'''")):
                continue
            offenders.append(os.path.basename(path))
            break
    a6 = not offenders
    out.append(("sem-focus-emulation", a6, "offenders=%s" % (offenders or "-")))

    # A7 -- um produtor por vez
    a7 = bool(re.search(r"if lines:\s*\n\s*self\.yt_live_paint_at = "
                        r"time\.monotonic\(\)", shell))
    out.append(("um-produtor-por-vez", a7, "marca-fresca=%s" % a7))

    # A8 -- A ABA E' IDENTIDADE SEM JANELA (2026-11-04). Medido no arranque do
    # dono: 65 s com `src='?' why=''` e o Chrome aberto num video, porque o laco
    # perguntava a janela em primeiro plano PRIMEIRO e desistia ali. A decisao
    # executada e' a real (`foreground_source`), nos tres casos.
    fg = getattr(mod, "foreground_source", None)
    a8 = bool(fg) and (
        fg(0, "vid123") == "external:youtube"
        and fg(0, "") == ""
        and fg(4242, "") == "external:youtube:foreground")
    out.append(("janela-nao-e-obrigatoria", a8,
                "fg(0,tid)=%r fg(0,'')=%r fg(hwnd)='foreground'"
                % (fg(0, "vid123") if fg else None, fg(0, "") if fg else None)))

    # A9 -- A SHELL USA-A, e o `why=` deixa de ser vazio quando nao ha' jogador:
    #      um `return [], False` mudo e' o que fez os 65 s nao terem endereco.
    a9 = bool(re.search(r"foreground_source\(hwnd, _tabvid\)", shell)) \
        and bool(re.search(r"why': 'no-player-window'", shell))
    out.append(("shell-usa-a-decisao", a9, "wired=%s" % a9))

    # A10 -- O ID DECLARADO FILTRA A ESCOLHA, NAO A LEITURA (2026-11-04). MEDIDO
    # no log do dono: 10:16:17 `wrong-video (vDmjw-c_R2k)` -> `state=ambiguous`
    # e **13 minutos sem uma linha** (`YOUTUBE_TICK_MS src='?' rows=0
    # cdp_age_ms=789250`) com a faixa do player a pintar. A funcao executada e' a
    # REAL (`adopt_decision`), nos quatro casos, e a shell obedece-lhe.
    ad = getattr(mod, "adopt_decision", None)
    a10 = bool(ad) and (
        ad("MOZIBMBHK-8", "vDmjw-c_R2k", False) == ("adopt", "declared-closed")
        and ad("MOZIBMBHK-8", "vDmjw-c_R2k", True) == ("refuse", "wrong-video")
        and ad("MOZIBMBHK-8", "MOZIBMBHK-8", True) == ("same", "same-video")
        and ad("", "vDmjw-c_R2k", True) == ("same", "no-declared"))
    # A CHAMADA VIVE NO LEITOR (`_run`), nao na shell: um controle no ficheiro
    # errado diria `wired=False` para sempre.
    _mod_src = _read(module_path)
    _wired = "adopt_decision(" in _mod_src and "_declared_closed(" in _mod_src
    out.append(("adota-a-aba-que-navegou", a10 and _wired,
                "adopt=%s wired=%s" % (a10, _wired)))

    # A11 -- A PORTA ABRE COM O PIPELINE E NAO COM O PRIMEIRO TICK (2026-11-04).
    # MEDIDO no arranque do dono: `pre-lock` 10:06:36.407, primeira leitura
    # 38.272, `attached` 40.798, primeira linha do player 40.889 -- 4,5 s para
    # uma legenda que a pagina ja' tinha. A chamada tem de estar DENTRO de
    # `start_caption_pipeline` e ANTES do `start_external_caption_watcher`.
    _pipe = shell.find("CAPTION_PIPELINE_START")
    _pre = shell.find("self._yt_cdp_boot_attach", _pipe if _pipe > 0 else 0)
    _watch = shell.find("'watcher', lambda: self.start_external_caption_watcher()",
                        _pipe if _pipe > 0 else 0)
    a11 = _pipe > 0 and _pre > _pipe and _watch > _pre
    out.append(("porta-cdp-abre-no-arranque", a11,
                "pipeline=%d preopen=%d watcher=%d" % (_pipe, _pre, _watch)))
    # A12 -- AS ABAS SAO SONADAS AO MESMO TEMPO (2026-11-05). MEDIDO no log do
    # dono: `EXTERNAL_CAPTIONS_READ_MS ms=8609.0 phases={'source': 8609.0}` --
    # oito segundos e meio dentro de UMA leitura, uma ligacao por aba somada.
    # O instrumento e' uma rede FALSA que atrasa 0,3 s por ligacao: com quatro
    # abas, a soma tem de passar de 1,2 s e o paralelo tem de ficar abaixo de
    # 0,8 s. E as duas formas tem de devolver os MESMOS numeros, na mesma ordem.
    class _Conn(object):
        def __init__(self):
            self._id = 1

        def settimeout(self, _t):
            pass

        def send(self, payload):
            # a resposta tem de ter o `id` PEDIDO: o `_ws_eval` ignora eventos
            # num laco e um `id` errado seria um laco infinito (medido: este
            # braco ficou preso quando devolvia sempre 1).
            try:
                self._id = int(json.loads(payload).get("id") or 1)
            except (TypeError, ValueError):
                self._id = 1

        def recv(self):
            value = json.dumps({"videoId": "v", "t": 3.0, "paused": False})
            return json.dumps({"id": self._id,
                               "result": {"result": {"value": value}}})

        def close(self):
            pass

    def _slow_connect(_url, timeout=None):
        time.sleep(0.3)
        return _Conn()

    tabs4 = [{"url": "https://www.youtube.com/watch?v=AAAAAAAAAAA" + str(i),
              "webSocketDebuggerUrl": "ws%d" % i} for i in range(4)]
    t0 = time.time()
    seq_probes = mod.probe_tabs(tabs4, connect=_slow_connect, timeout=1.0,
                                gap_s=0.0, parallel=False)
    seq_s = time.time() - t0
    t0 = time.time()
    par_probes = mod.probe_tabs(tabs4, connect=_slow_connect, timeout=1.0,
                                gap_s=0.0, parallel=True)
    par_s = time.time() - t0
    same = ([(p["t1"], p["videoId"]) for p in seq_probes]
            == [(p["t1"], p["videoId"]) for p in par_probes]
            and len(par_probes) == 4)
    a12 = same and par_s < 0.8 and seq_s > 1.2
    out.append(("abas-em-paralelo", a12,
                "seq=%.2fs par=%.2fs mesmos=%s" % (seq_s, par_s, same)))

    # A13..A17 -- os tres defeitos que o dono reportou a 2026-11-06
    for name, fn in (("pausa-corta-a-pintura",
                      lambda: _arm_pausa_corta_a_pintura(mod, shell_path)),
                     ("pausa-nao-congela",
                      lambda: _arm_tick_da_pausa(shell_path)),
                     ("duas-abas-primeiro-plano",
                      lambda: _arm_duas_abas_primeiro_plano(mod)),
                     ("troca-limpa-o-estado",
                      lambda: _arm_troca_limpa_o_estado(mod)),
                     ("reavalia-sem-esperar",
                      lambda: _arm_reavalia_sem_esperar(mod)),
                     ("desligar-em-pausa",
                      lambda: _arm_desligar_em_pausa(shell_path))):
        try:
            ok, detail = fn()
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, 'EXCECAO %r' % (exc,)
        out.append((name, ok, detail))

    # A18..A21 -- O CUSTO QUE NAO DORME (DM do watcher, stutter 50452, 2026-11-09):
    # `YOUTUBE_TARGET ... why=declared` e `YOUTUBE_CDP_SOURCE state=attached` saiam
    # a cada volta do laco (6 513 + 6 511 linhas nos ultimos 2 MB do log do dono, o
    # par a ~1,4x/s cada). O estado passa a sair na MUDANCA e no batimento; estas
    # arms medem as QUATRO metades -- nao repete, muda sai, batimento sai, e o
    # oraculo continua a ver a primeira escolha.
    def _state_arms():
        # A SONDA E' UM DUPLO INSTANTANEO, e a razao e' CUSTO MEDIDO (2026-11-09):
        # estas arms medem o LIMIAR DA ESCRITA (`YOUTUBE_TARGET`/`YOUTUBE_CDP_SOURCE`
        # na mudanca e no batimento), nao a sonda. Com o transporte REAL,
        # `ws://x/AAA` (host que nao existe) custa **2,70 s por `_choose`** -- o laco
        # abaixo faz 22 delas e cada `arms()` pagava ~59 s, o que levava o
        # `red-as-expected` (as copias de entao, 15) a **>900 s** e o prazo da
        # bateria a mata-lo (o baseline do passo e' 122,4 s; medido aqui: 400 s
        # sem terminar, e o `--neg-arm` nunca chegava a imprimir um veredicto).
        # O duplo responde `rs=0`/`t=0`, que e' a MESMA recusa de hoje
        # (`probe=no-player`) e o MESMO caminho de queda -- so' sem a espera --
        # logo as contagens que estas arms julgam nao mudam.
        class _NoPlayer(object):
            def __init__(self):
                self._id = 1

            def settimeout(self, _t):
                pass

            def send(self, payload):
                # O id PEDIDO, sempre: o `_ws_eval` ignora o que nao casa e um id
                # fixo prenderia a SEGUNDA leitura num laco infinito.
                try:
                    self._id = int(json.loads(payload).get("id") or 1)
                except (TypeError, ValueError):
                    self._id = 1

            def recv(self):
                value = json.dumps({"videoId": "AAAAAAAAAAA", "t": 0.0,
                                    "rs": 0, "paused": False})
                return json.dumps({"id": self._id,
                                   "result": {"result": {"value": value}}})

            def close(self):
                pass

        def _fake_connect(_url, timeout=None):
            return _NoPlayer()

        logs = []
        obj = mod.CdpCaptionSource(port=0, log=logs.append)
        obj._probe_connect = _fake_connect
        tabs = [{"webSocketDebuggerUrl": "ws://x/AAA",
                 "url": "https://www.youtube.com/watch?v=AAAAAAAAAAA",
                 "title": "video - YouTube"}]
        obj._video_id = "AAAAAAAAAAA"
        frame = {"stamp": time.monotonic(), "rows": ["a"],
                 "items": [{"text": "a"}], "videoId": "AAAAAAAAAAA"}
        for _ in range(20):
            obj._choose(tabs)
            obj._publish(frame, "attached")
        targets = [l for l in logs if l.startswith("YOUTUBE_TARGET")]
        states = [l for l in logs if l.startswith("YOUTUBE_CDP_SOURCE")]
        yield ("estado-nao-repete", len(states) == 1 and len(targets) == 1,
               "20 voltas -> target=%d estado=%d (era 40; o resto sao mudancas)"
               % (len(targets), len(states)))
        # A MUDANCA SAI NA HORA: a fonte que cai para `slow` e volta tem de deixar
        # as duas linhas, senao a cura apagava a evidencia que os oraculos leem.
        obj._publish(frame, "slow (WebSocketTimeoutException)")
        obj._publish(frame, "attached")
        seen = [l.split("state=", 1)[1] for l in logs
                if l.startswith("YOUTUBE_CDP_SOURCE")]
        yield ("estado-na-mudanca", seen[-2:] == ["slow (WebSocketTimeoutException)",
                                                 "attached"],
               "sequencia=%r" % (seen[-2:],))
        # O BATIMENTO: 61 s depois, o MESMO estado sai outra vez (uma vez por minuto,
        # nao 8 vezes por segundo) -- e' o que deixa o oraculo provar que respira.
        before = len([l for l in logs if l.startswith("YOUTUBE_CDP_SOURCE")])
        obj._note_log_t -= mod._STATE_HEARTBEAT_S + 1.0
        obj._publish(frame, "attached")
        after = len([l for l in logs if l.startswith("YOUTUBE_CDP_SOURCE")])
        yield ("estado-batimento", after == before + 1,
               "linhas antes=%d depois=%d (batimento de %.0fs)"
               % (before, after, mod._STATE_HEARTBEAT_S))
        # O CONTROLE: uma escolha DIFERENTE tem de escrever outra linha `YOUTUBE_TARGET`,
        # senao a cura trocava a repeticao por um silencio que esconde a troca de aba.
        other = [dict(tabs[0], url="https://www.youtube.com/watch?v=BBBBBBBBBBB",
                      title="outro - YouTube")]
        obj2 = mod.CdpCaptionSource(port=0, log=logs.append)
        obj2._probe_connect = _fake_connect
        obj2._video_id = "AAAAAAAAAAA"
        obj2._choose(tabs)
        n1 = len([l for l in logs if l.startswith("YOUTUBE_TARGET")])
        obj2._choose(other)
        n2 = len([l for l in logs if l.startswith("YOUTUBE_TARGET")])
        yield ("escolha-diferente-escreve", n2 == n1 + 1,
               "linhas %d -> %d ao trocar de aba" % (n1, n2))

    for name, ok, detail in _state_arms():
        out.append((name, ok, detail))
    return out


def neg_arm():
    """Tres mutacoes numa COPIA do modulo; cada uma derruba a SUA arm."""
    tmp = tempfile.mkdtemp(prefix="yt-cdp-neg-")
    try:
        src = _read(MODULE)
        shell_src = _read(SHELL)
        # A COPIA CARREGA OS IRMAOS DO DIRETORIO REAL. `youtube_cdp_source`
        # carrega `youtube_window` pelo caminho (o marcador de fala `>>` vive la'),
        # portanto ao lado do mutante tem de estar o irmao -- senao o mutante nao
        # importa e a mutacao nao prova nada (medido: FileNotFoundError aqui).
        shutil.copy2(os.path.join(APP, "youtube_window.py"),
                     os.path.join(tmp, "youtube_window.py"))
        results = []

        mut = os.path.join(tmp, "sem_id.py")
        io.open(mut, "w", encoding="utf-8").write(
            src.replace('    if video_id:\n        named = [t for t in tabs if video_id in str(t.get("url") or "")]',
                        '    if False:\n        named = [t for t in tabs if video_id in str(t.get("url") or "")]', 1))
        got = dict((n, ok) for n, ok, _ in arms(module_path=mut))
        results.append(("identidade-cega", not got.get("identidade-do-video", False)))

        mut2 = os.path.join(tmp, "sem_clip.py")
        io.open(mut2, "w", encoding="utf-8").write(
            src.replace("    return ov >= 0.5 * h;", "    return true;", 1))
        got2 = dict((n, ok) for n, ok, _ in arms(module_path=mut2))
        results.append(("clip-removido", not got2.get("recorte-do-clip", False)))

        mut3 = os.path.join(tmp, "linha_sem_texto.py")
        io.open(mut3, "w", encoding="utf-8").write(
            # A LINHA CRUA (sem colapso de espacos e sem o marcador de fala): a
            # ancora e' a linha de HOJE, que passou a chamar o normalizador.
            src.replace('        text = strip_speaker_markers(line.get("text"))',
                        '        text = str(line.get("text") or "")', 1))
        got3 = dict((n, ok) for n, ok, _ in arms(module_path=mut3))
        results.append(("linhas-sem-filtro", not got3.get("linhas-do-player", False)))

        # O `>>` VOLTA (dono, 2026-11-08): a copia entrega o texto do player cru,
        # sem passar pelo `strip_speaker_markers` -- e a arm do marcador tem de
        # cair, senao ela nao guarda nada.
        mut_marker = os.path.join(tmp, "com_marcador.py")
        io.open(mut_marker, "w", encoding="utf-8").write(
            src.replace('        text = strip_speaker_markers(line.get("text"))',
                        '        text = " ".join(str(line.get("text") or "").split())', 1))
        got_marker = dict((n, ok) for n, ok, _ in arms(module_path=mut_marker))
        results.append(("marcador-volta",
                        not got_marker.get("sem-marcador-de-fala", False)))

        # A ABA NAO PROVA NADA: e' o comportamento de antes de 2026-11-04 -- sem
        # jogador em primeiro plano o laco desistia e a fonte do player nunca
        # chegava ao ecra.
        mut4 = os.path.join(tmp, "aba_nao_prova.py")
        io.open(mut4, "w", encoding="utf-8").write(
            src.replace("    return 'external:youtube' if str(tab_video_id or '').strip() else ''",
                        "    return ''", 1))
        got4 = dict((n, ok) for n, ok, _ in arms(module_path=mut4))
        results.append(("aba-nao-prova", not got4.get("janela-nao-e-obrigatoria", False)))

        # SEM ADOCAO: a foto de outro video volta a ser recusa incondicional, que
        # e' o laco preso por 13 min medido no log do dono.
        mut5 = os.path.join(tmp, "sem_adocao.py")
        io.open(mut5, "w", encoding="utf-8").write(
            src.replace("    if not declared_open:\n        return 'adopt', 'declared-closed'",
                        "    if False:\n        return 'adopt', 'declared-closed'", 1))
        got5 = dict((n, ok) for n, ok, _ in arms(module_path=mut5))
        results.append(("sem-adocao", not got5.get("adota-a-aba-que-navegou", False)))

        # SEM PRE-ABERTURA: a chamada sai do arranque e volta a esperar o tick.
        mut6 = os.path.join(tmp, "sem_preabertura.py")
        io.open(mut6, "w", encoding="utf-8").write(
            shell_src.replace("target=self._yt_cdp_boot_attach,",
                              "target=lambda: None,", 1))
        got6 = dict((n, ok) for n, ok, _ in arms(module_path=None, shell_path=mut6))
        results.append(("sem-preabertura", not got6.get("porta-cdp-abre-no-arranque", False)))

        # SEM PARALELO: as abas voltam a ser somadas uma atras da outra -- o
        # `EXTERNAL_CAPTIONS_READ_MS ms=8609` medido no log do dono.
        mut7 = os.path.join(tmp, "sem_paralelo.py")
        io.open(mut7, "w", encoding="utf-8").write(
            src.replace("    if not parallel or len(items) == 1:",
                        "    if True:", 1))
        got7 = dict((n, ok) for n, ok, _ in arms(module_path=mut7))
        results.append(("sem-paralelo", not got7.get("abas-em-paralelo", False)))

        # -- 2026-11-06: os tres defeitos do dono -----------------------------
        # (1) O CONGELAMENTO some: o payload volta a ser a linha crua, que
        # cresce com o relogio do player -- o `paint_t` a andar +0,95 s medido.
        mut8 = os.path.join(tmp, "pausa_sem_congelar.py")
        io.open(mut8, "w", encoding="utf-8").write(
            src.replace('        out.append({"index": row.get("index"), "text": text, "words": [],\n'
                        '                    "start": (start if start is not None else 0.0),\n'
                        '                    "end": None, "cap": None})',
                        '        out.append(dict(row))', 1))
        got8 = dict((n, ok) for n, ok, _ in arms(module_path=mut8))
        results.append(("pausa-sem-congelar",
                        not got8.get("pausa-corta-a-pintura", False)))

        # (2) O PRIMEIRO PLANO deixa de contar: a escolha volta ao "ja' adotado
        # que ainda toca", que com duas abas a tocar fica no video errado.
        mut9 = os.path.join(tmp, "sem_primeiro_plano.py")
        io.open(mut9, "w", encoding="utf-8").write(
            src.replace("    front = [p for p in usable if tab_is_foreground(p)]",
                        "    front = []", 1))
        got9 = dict((n, ok) for n, ok, _ in arms(module_path=mut9))
        results.append(("sem-primeiro-plano",
                        not got9.get("duas-abas-primeiro-plano", False)))

        # (2b) A FOTO DA ABA ANTERIOR sobrevive a' troca -- legenda de um video
        # no ecra do outro, o erro que este canal nao leva `videoId` para
        # distinguir.
        mut10 = os.path.join(tmp, "troca_nao_limpa.py")
        io.open(mut10, "w", encoding="utf-8").write(
            src.replace("        if key != old:\n            with self._lock:\n                self._snap = None",
                        "        if False:\n            with self._lock:\n                self._snap = None", 1))
        got10 = dict((n, ok) for n, ok, _ in arms(module_path=mut10))
        results.append(("troca-nao-limpa",
                        not got10.get("troca-limpa-o-estado", False)))

        # (2c) A ASSINATURA da lista de abas sai da chave da cache: uma aba nova
        # espera o TTL de 10 s (a legenda do video anterior).
        mut11 = os.path.join(tmp, "sem_assinatura.py")
        io.open(mut11, "w", encoding="utf-8").write(
            src.replace("if cached and len(cached) >= 4 and cached[3] == sig:",
                        "if cached and len(cached) >= 4 and True:", 1))
        got11 = dict((n, ok) for n, ok, _ in arms(module_path=mut11))
        results.append(("sem-assinatura",
                        not got11.get("reavalia-sem-esperar", False)))

        # (2d) O TTL VOLTA A 10 s COM DUAS ABAS: um alt-tab fica ate' 10 s no
        # video anterior -- a cache so' a tempo, sem a chave de foco.
        mut12 = os.path.join(tmp, "ttl_dez.py")
        io.open(mut12, "w", encoding="utf-8").write(
            src.replace("        ttl = (PLAYING_PROBE_TTL_S if len(sig) <= 1\n"
                        "               else PLAYING_PROBE_TTL_MULTI_S)",
                        "        ttl = PLAYING_PROBE_TTL_S", 1))
        got12 = dict((n, ok) for n, ok, _ in arms(module_path=mut12))
        results.append(("ttl-dez",
                        not got12.get("reavalia-sem-esperar", False)))

        # (3) A PAUSA NAO ENVELHECE A LINHA do player: o interruptor volta a
        # recusar a linha que o video parado continua a mostrar.
        mut13 = os.path.join(tmp, "replay_sem_pausa.py")
        io.open(mut13, "w", encoding="utf-8").write(
            shell_src.replace("    if bool(paused) and bool(from_player):\n        return True",
                              "    if False:\n        return True", 1))
        got13 = dict((n, ok) for n, ok, _ in arms(module_path=None, shell_path=mut13))
        results.append(("replay-sem-pausa",
                        not got13.get("desligar-em-pausa", False)))

        # (1b) A PAUSA VOLTA A CONGELAR O ECRA: o desenho que a cura de
        # 2026-11-06 fazia (e que o dono reprovou em 2026-11-09) e' reintroduzido
        # no `_tick` -- um tick de pausa sem linha nova volta a empurrar a linha
        # velha, e a arm 1b tem de cair.
        #
        # A ANCORA E' ESCOLHIDA DENTRO DO `_tick` (2026-11-09). O mesmo carimbo
        # aparece DUAS vezes na shell -- o reset por troca de video e o `_tick` --
        # e o `replace(..., 1)` mutava a PRIMEIRA: o "mutante" saia com o `_tick`
        # intacto e `sem-borda-de-pausa` respondia NOT-CAUGHT sem que a cura
        # alguma vez fosse derrubada. Medido nesta arvore: 5067 (reset) e 5978
        # (`_tick`). Uma ancora que nao existe mais tem de GRITAR, nao de passar.
        _tick_at = shell_src.find("    def _tick(self, got, yt_mode=False):")
        _stamp = ("        self._yt_pause_epoch_seen = int("
                  "getattr(self, '_yt_pause_epoch', 0) or 0)")
        _stamp_at = shell_src.find(_stamp, _tick_at + 1 if _tick_at >= 0 else 0)
        if _tick_at < 0 or _stamp_at < 0:
            raise RuntimeError(
                "ancora do `_tick` desapareceu da shell (tick=%d stamp=%d): "
                "o mutante `sem-borda-de-pausa` nao tem onde aterrar e um "
                "mutante que nao muta nada e' um controlo que nao pode falhar"
                % (_tick_at, _stamp_at))
        mut14 = os.path.join(tmp, "pausa_congela.py")
        io.open(mut14, "w", encoding="utf-8").write(
            shell_src[:_stamp_at] + _stamp + "\n"
            "        if (getattr(self, 'yt_cdp_paused', False)\n"
            "                and getattr(self, 'last_line', '')):\n"
            "            self.shell.push_caption_to_window(\n"
            "                self.last_line, instant=True)"
            + shell_src[_stamp_at + len(_stamp):])
        got14 = dict((n, ok) for n, ok, _ in arms(module_path=None, shell_path=mut14))
        results.append(("sem-borda-de-pausa",
                        not got14.get("pausa-nao-congela", False)))

        # (4) O LIMIAR DO ESTADO VOLTA A NAO EXISTIR: a guarda de `_publish` sai e
        # a fonte escreve `YOUTUBE_CDP_SOURCE` a cada volta -- as 6 511 linhas
        # medidas no log do dono. A arm `estado-nao-repete` tem de cair, senao as
        # quatro arms de 2026-11-09 sao um verde que nao pode falhar.
        mut_dedup = os.path.join(tmp, "sem_dedup_estado.py")
        io.open(mut_dedup, "w", encoding="utf-8").write(
            src.replace("            if unchanged and not due:\n",
                        "            if False:\n", 1))
        got_dedup = dict((n, ok) for n, ok, _ in arms(module_path=mut_dedup))
        results.append(("sem-dedup-estado",
                        not got_dedup.get("estado-nao-repete", False)))
        return results
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args(argv)
    if args.neg_arm:
        results = neg_arm()
        bad = 0
        for name, caught in results:
            print("NEG-ARM %-20s %s" % (name, "CAUGHT" if caught else "NOT-CAUGHT"))
            bad += 0 if caught else 1
        print("NEG-ARM VERDICT: %s (%d/%d)"
              % ("PASS" if not bad else "FAIL", len(results) - bad, len(results)))
        # A CONVENCAO DA BATERIA (2026-11-03): um `red-as-expected` declara rc=1.
        # "Apanhei todos os mutantes" E' o resultado VERMELHO que o `:expectred`
        # exige, senao o passo passa como se fosse um oraculo normal e o mutante
        # nunca e' recusado. rc=0 quando um mutante escapa (o passo fica vermelho
        # de verdade, e com a frase FAIL no log).
        return 1 if not bad else 0
    bad = 0
    # UMA EXECUCAO, nao tres: `len(arms())` no format era chamado DUAS vezes
    # depois do laco, ou seja as 23 arms corriam tres vezes por corrida para
    # imprimir um numero de duas letras (medido 2026-11-09: 191,8 s de parede
    # para ~40 s de trabalho). O custo e' o de UM `arms()`.
    ran = arms()
    for name, ok, note in ran:
        print("%-22s %s  %s" % (name, "PASS" if ok else "FAIL", note))
        bad += 0 if ok else 1
    print("VERDICT: %s (%d/%d)" % ("PASS" if not bad else "FAIL",
                                   len(ran) - bad, len(ran)))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
