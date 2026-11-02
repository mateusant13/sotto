#!/usr/bin/env pythonw.exe
# -*- coding: utf-8 -*-
"""REVEAL-AND-PARK ORACLE -- as duas metades do mesmo defeito do dono (2026-11-02).

O DONO, verbatim, na sessao dele (`pid 18676`, 18:52):

    *"primeiro: transcricao ao vivo nao ta funcionando. segundo: legenda do
      youtube nao aparece de forma instantanea ao ligar o app. terceiro: a
      animacao da legenda que e' copiada do youtube ta errada. tu ta simplesmente
      reaplicando a animacao atual ou algo assim, quando eu quero a animacao
      classica que aparece uma palavra por vez, ate' mostrar a frase inteira,
      IGUAL acontece no youtube."*

O QUE FOI MEDIDO no log dele, e nao suposto:

  1. `BRIDGE_STOP reason=external-captions` as 18:52:13 e `spawns=1` ate' ao fim:
     o worker AO VIVO foi parqueado para a faixa do YouTube pintar, e nunca
     voltou -- 8 minutos sem uma unica legenda do microfone. O ramo do YouTube
     (`_tick(got, yt_mode=True)`) nunca chamava `_release`, por desenho: quem
     devia decidir era o `_youtube`, e o `_youtube` so' APAGAVA a janela
     (`_yt_forget` -> `CAPTION_WINDOW_BLANKED reason=no-caption-for-6.0s`).
  2. 18 `YOUTUBE_CAPTION`, todas com `why=painted-other-track`, e o relogio do
     UIA a saltar de segundo em segundo (`t=2.0, 3.0, 7.0, 12.0, 16.0, ...`):
     o ancora do relogio fino (`_yt_anchor`, que faz `yt_live_frame` recompor a
     linha a cada `RENDER_S` = 60 ms) so' era gravado no ramo `painted`, logo
     neste ramo a linha so' podia mudar quando o UIA mudava. Era isto que punha
     a frase inteira no ecra de uma vez.

O QUE ESTE ORACULO PROVA, arm por arm, sem lancar a app (importa o shell em
processo, como `external-resume-oracle.py`; nada de janela, hook ou worker):

  A1  o ramo `painted-other-track` GRAVA o ancora e a faixa
  A2  com o ancora, `yt_live_frame()` cresce PALAVRA A PALAVRA ate' a frase
      inteira, na ordem do `tOffsetMs` do fixture
  A3  `_tick(got=[], yt_mode=True)` apos `YT_RELEASE_S` de silencio DEVOLVE o
      microfone (chama `on_external_captions_released` do shell)
  A4  e NAO devolve antes do piso (`YT_RELEASE_S` = 30 s): o buraco entre duas
      cues do YouTube nao pode custar uma carga de modelo

Os bracos negativos MUTAM o ficheiro VIVO numa copia e exigem o RED pelo mesmo
codigo que publica o veredicto: um instrumento que so' sabe dizer verde nao e'
um instrumento.

    python _main\\reveal-park-oracle.py            # rc=0 verde
    python _main\\reveal-park-oracle.py --neg-arm  # rc=1 = os mutantes foram apanhados
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SHELL = os.path.join(REPO, 'app', 'webview', 'sotto_webview.py')
FIXTURE = os.path.join(HERE, 'fixtures', 'yt-WdaHAGRBB6s.en-orig.json3')
PREFIX = '_revealpark-neg-'

#: O PREFIXO REVELADO QUE O YOUTUBE DESENHA, do payload dele (tOffsetMs).
#: A primeira cue do fixture: 'Have'(0) ' you'(240) ' ever'(400) ' had'(640)
#: ' to'(800) ' kill'(920) ' a'(1160) ' man?'(1200).
REVEAL = ('Have', 'Have you', 'Have you ever', 'Have you ever had',
          'Have you ever had to', 'Have you ever had to kill',
          'Have you ever had to kill a', 'Have you ever had to kill a man?')


def _read(path):
    with open(path, encoding='utf-8', errors='replace') as fh:
        return fh.read()


def load_module(path, name):
    import importlib.util
    if os.path.dirname(path) not in sys.path:
        sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def clean_mutants():
    d = os.path.dirname(SHELL)
    for name in os.listdir(d):
        if name.startswith(PREFIX):
            try:
                os.remove(os.path.join(d, name))
            except OSError:
                pass


def build_mutant(text, name, old, new):
    if text.count(old) != 1:
        raise RuntimeError('ancora do mutante %r encontrada %d vez(es)'
                           % (name, text.count(old)))
    path = os.path.join(os.path.dirname(SHELL), PREFIX + name + '.py')
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text.replace(old, new))
    return path


# --------------------------------------------------------------------------
# A FAIXA DE TESTE: as cues REAIS do fixture, com as palavras e o relogio delas.
# --------------------------------------------------------------------------
def fixture_track():
    """As cues do payload do YouTube, no formato que `parse_json3` produz."""
    with open(FIXTURE, encoding='utf-8') as fh:
        payload = fh.read()
    import youtube_captions
    cues = youtube_captions.parse_json3(payload)
    if not cues:
        raise RuntimeError('o fixture nao produziu cues')
    return {'state': 'has-track', 'lang': 'en-US', 'cues': cues,
            'duration': 33840 / 1000.0, 'reason': 'ok'}


class FakeThread(object):
    """O leitor da faixa: devolve a faixa ja' pronta, conta os pedidos."""

    def __init__(self, track):
        self.track = track
        self.requests = 0

    def request(self, vid, painted=None, **kw):
        self.requests += 1

    def current(self, vid):
        return self.track


class FakeShell(object):
    """O lado do shell: o park e o resume, sem worker nenhum."""

    def __init__(self):
        self.youtube_track_thread = None
        self.external_captions_active = False
        self.external_captions_available = False
        self.parked = True
        self.resumes = 0
        self.captions = []

    def on_external_captions_released(self):
        self.resumes += 1
        self.parked = False
        return True

    def external_caption(self, line, source, final=False, instant=False, rows=None):
        self.captions.append((line, final))
        return True


def build(mod, track):
    shell = FakeShell()
    shell.youtube_track_thread = FakeThread(track)
    watcher = mod.ExternalCaptionWatcher(shell)
    watcher.yt_video_id = 'WdaHAGRBB6s'
    watcher._youtube_video_id = lambda *a, **k: 'WdaHAGRBB6s'
    watcher._youtube_painted = lambda *a, **k: ['Lean proofs.']
    return watcher, shell


# --------------------------------------------------------------------------
# AS ARMS
# --------------------------------------------------------------------------
def arm_anchor(mod, track):
    """A1: o ramo do relogio grava o ancora (a linha pode crescer entre leituras)."""
    watcher, _shell = build(mod, track)
    watcher._youtube_time = lambda *a, **k: 41.0
    watcher.yt_foreign_t = None
    lines, urgent = watcher._youtube(0, None, None)
    anchor = getattr(watcher, '_yt_anchor', None)
    ok = bool(anchor) and bool(getattr(watcher, '_yt_track', None))
    return ok, ('anchor=%r track=%s lines=%r urgent=%s'
                % (anchor, bool(getattr(watcher, '_yt_track', None)),
                   (lines[0][1] if lines else [])[:2], urgent))


def arm_reveal(mod, track):
    """A2: com o ancora, `yt_live_frame` cresce palavra a palavra.

    A prova e' o CONJUNTO ordenado de prefixos que o ecra pode mostrar: comeca
    na primeira palavra e termina na frase inteira, sem saltar a ordem do
    `tOffsetMs`. O relogio anda de verdade (o `monotonic` e' o do modulo), por
    isso a arm espera ~1,3 s -- o tempo real da cue do fixture (1 200 ms).
    """
    watcher, _shell = build(mod, track)
    base = 0.05
    watcher._yt_anchor = (base, time.monotonic())
    watcher._yt_track = track
    seen = []
    deadline = time.monotonic() + 1.45
    while time.monotonic() < deadline:
        frame = watcher.yt_live_frame()
        if frame:
            text = frame[1][-1] if frame[1] else ''
            if text and (not seen or seen[-1] != text):
                seen.append(text)
        time.sleep(mod.ExternalCaptionWatcher.RENDER_S)
    # O ultimo instante da cue: a frase inteira tem de ter aparecido.
    first = next((i for i, t in enumerate(seen) if t.startswith(REVEAL[0])), -1)
    grew = sorted(set(seen), key=len)
    ok = (first >= 0 and REVEAL[-1] in seen
          and len(set(seen)) >= 5
          and grew[-1] == REVEAL[-1])
    return ok, 'seq=%r' % (seen[:10],)


def arm_anchor_has_cue(mod, track):
    """A5: o outro ramo do relogio (`has-cue`) TAMBEM grava o ancora.

    MEDIDO no log do dono (`pid 18676`, 18:53:01): `YOUTUBE_TRACK_STATE
    reason=no-cue` e `reason=has-cue` aparecem entre as cues do player. Um
    mutante que apague so' o ancora DESTE ramo passava verde sem esta arm -- e um
    mutante que nao move o artefacto do veredicto nao prova nada.
    """
    watcher, _shell = build(mod, track)
    watcher._youtube_painted = lambda *a, **k: []
    # Uma cue VIVA: a 2.a do fixture e' [2.64, 6.80). A 41 s nao ha' cue nenhuma
    # e a arm mediria o buraco, nao o ramo.
    watcher._youtube_time = lambda *a, **k: 3.0
    watcher.yt_hit = None
    lines, urgent = watcher._youtube(0, None, None)
    ok = bool(getattr(watcher, '_yt_anchor', None)) and bool(lines)
    return ok, 'anchor=%r lines=%r urgent=%s' % (
        getattr(watcher, '_yt_anchor', None),
        (lines[0][1] if lines else []), urgent)


def arm_park_release(mod, track):
    """A3: sem linha durante `YT_RELEASE_S`, o microfone volta."""
    watcher, shell = build(mod, track)
    watcher.last_line = ''
    watcher.last_seen = time.monotonic() - (mod.ExternalCaptionWatcher.YT_RELEASE_S + 1.0)
    watcher._tick([], True)
    return shell.resumes >= 1, 'resumes=%d parked=%s' % (shell.resumes, shell.parked)


def arm_park_floor(mod, track):
    """A4: um buraco entre cues NAO devolve o microfone (piso de 30 s)."""
    watcher, shell = build(mod, track)
    watcher.last_line = ''
    watcher.last_seen = time.monotonic() - 5.0
    watcher._tick([], True)
    return shell.resumes == 0, 'resumes=%d (esperado 0 a 5 s)' % shell.resumes


ARMS = (
    ('A1-ancora-no-ramo-do-relogio', arm_anchor),
    ('A2-revelacao-palavra-a-palavra', arm_reveal),
    ('A5-ancora-no-ramo-has-cue', arm_anchor_has_cue),
    ('A3-microfone-volta-apos-30s', arm_park_release),
    ('A4-piso-de-30s-no-buraco-entre-cues', arm_park_floor),
)

#: O mutante devolve o ficheiro ao estado MEDIDO antes da cura.
MUTANTS = (
    ('sem-ancora-no-ramo-foreign',
     """                self._yt_anchor = (float(now_t), time.monotonic())
                self._yt_track = track
""", ''),
    ('sem-ancora-no-ramo-has-cue',
     """        self._yt_anchor = (float(t), time.monotonic())
        self._yt_track = track
""", ''),
    ('sem-release-do-youtube',
     """            if (now - self.last_seen) >= self.YT_RELEASE_S:
                self._release('yt-no-line')""", """            if False:
                self._release('yt-no-line')"""),
)


def run_arms(mod, track):
    rows = []
    bad = 0
    for label, fn in ARMS:
        try:
            ok, detail = fn(mod, track)
        except Exception as exc:  # noqa: BLE001
            ok, detail = False, 'EXC %r' % (exc,)
        bad += 0 if ok else 1
        rows.append((label, ok, detail))
    return rows, bad


def neg_arm(text):
    cases = 0
    caught = 0
    for name, old, new in MUTANTS:
        path = build_mutant(text, name, old, new)
        try:
            mod = load_module(path, PREFIX.replace('-', '_') + name.replace('-', '_'))
            track = fixture_track()
            rows, bad = run_arms(mod, track)
            got = 'RED' if bad else 'GREEN'
            caught += 1 if bad else 0
            cases += 1
            print('  %-34s -> %-6s %s' % (name, got,
                                          [r[0] for r in rows if not r[1]]))
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
    print('NEG-ARM cases=%d caught=%d' % (cases, caught))
    if caught != cases:
        print('NEG-ARM FAIL')
        return 2
    print('NEG-ARM PASS')
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--neg-arm', action='store_true',
                    help='muta a copia viva e exige o RED das arms')
    args = ap.parse_args(argv)
    text = _read(SHELL)
    if args.neg_arm:
        try:
            return neg_arm(text)
        finally:
            clean_mutants()
    mod = load_module(SHELL, 'sotto_shell_reveal_park')
    track = fixture_track()
    rows, bad = run_arms(mod, track)
    for label, ok, detail in rows:
        print('  %-38s %-4s %s' % (label, 'PASS' if ok else 'FAIL', detail[:150]))
    print('VERDICT: %s (%d/%d arms)' % ('GREEN' if not bad else 'RED',
                                        len(rows) - bad, len(rows)))
    return 0 if not bad else 2


if __name__ == '__main__':
    sys.exit(main())
