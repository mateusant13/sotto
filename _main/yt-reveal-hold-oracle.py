# NO-BUG: Oracle: o tecto de 3 s do relogio da revelacao nao pode parar a linha em
#        silencio -- o episodio e' nomeado (`CAPTION_REVEAL_HELD`) e o relogio nunca
#        inventa mais video do que `PLAYER_HOLD_S` do produto.
#        Capacidade pedida pelo dono (A5, freeze-then-thaw na legenda); nao ha id de
#        `_main/bug-ledger.json` para isto, e o id nao se inventa.
"""Oracle: the reveal clock's hold -- a legitimate clamp that used to be silent.

THE DEFECT THIS NAMES. `_PlayerCue.clock()` stops the reveal at `PLAYER_HOLD_S`
(3.0 s) after the last measurement, on purpose: past that point the overlay would
be drawing words nobody measured. But it stopped **silently**, and the owner is
listening to audio that continues -- so he reads a still frame and calls it
"travou". Measured in his own logs: the producer went 8.2 s without publishing at
02:38:08 and 8.71 s at the worst point of the same session, i.e. **5.2-5.7 s of
reveal lost per episode with the old line still on screen**.

WHY A GATE AND NOT A CONSTANT CHANGE. Raising `PLAYER_HOLD_S` would trade one
lie for another (the overlay inventing video it never measured). What was missing
is the WITNESS: one line per cue, naming the gap and the seconds lost, so an
episode is a red in a log instead of an impression. The hold itself stays 3.0 s,
and the oracle proves it does not invent more than that.

ARMS (real `_PlayerCue` + real `youtube_reveal.frame`, injected clock)
  a NORMAL        -- a push every 1.0 s over 60 s: the reveal advances with the
                     cue, `held_s` stays 0, no `CAPTION_REVEAL_HELD`;
  b OWNER-STALL   -- the measured 8.2 s stall: the reveal stops at the hold,
                     `held_s == 5.2`, and EXACTLY ONE line is emitted even though
                     `frame()` is asked 60 times;
  c NO-INVENTION  -- at 2x rate the clock still stops after 3.0 s of WALL time:
                     asking at +3 s and at +30 s gives the same revealed words;
  d PAUSE         -- a cue whose `t` never moves: nothing is invented past the
                     hold, and the episode is named.

Usage:
  py -3 _main/yt-reveal-hold-oracle.py            # arms, rc 0 = all hold
  py -3 _main/yt-reveal-hold-oracle.py --neg-arm  # rc 1 = every mutant CAUGHT
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBVIEW = os.path.join(ROOT, 'app', 'webview')
OVERLAY = os.path.join(WEBVIEW, 'caption_overlay.py')
if WEBVIEW not in sys.path:
    sys.path.insert(0, WEBVIEW)


def load_from_path(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_from_source(source, name):
    """Um modulo a partir de TEXTO -- e' assim que os mutantes sao carregados."""
    folder = tempfile.mkdtemp(prefix='reveal-hold-')
    path = os.path.join(folder, name + '.py')
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(source)
    try:
        return load_from_path(path, name)
    finally:
        for leftover in (path,):
            try:
                os.unlink(leftover)
            except OSError:
                pass
        try:
            os.rmdir(folder)
        except OSError:
            pass


REVEAL = None


def cue_rows(overlay, base=100.0, count=8):
    """Um cue na forma do produto (`youtube_reveal.rows_from_cues`), com 8 palavras
    de 0,4 s cada -- a cadencia tipica de uma linha do YouTube.

    `base` move o cue no tempo do video: a linha seguinte do video comeca onde a
    anterior acabou, que e' como o player as serve."""
    global REVEAL
    if REVEAL is None:
        REVEAL = load_from_path(os.path.join(WEBVIEW, 'youtube_reveal.py'),
                                'youtube_reveal_hold_probe')
    # PALAVRAS SOBRADAS DE PROPOSITO nas arms que julgam o TECTO: com 8 palavras
    # (3,6 s de linha) a linha EXPIRA antes de o tecto de 3 s morder, e a arm
    # mediria a expiracao em vez do tecto -- um verde pela razao errada.
    words = ['w%02d' % index for index in range(count)]
    text = ' '.join(words)
    return REVEAL.rows_from_cues([{'text': text, 'start': base,
                                   'end': base + 0.4 * count,
                                   'words': [{'text': word,
                                              'start': base + 0.4 * i}
                                             for i, word in enumerate(words)]}])


def revealed(words_seen):
    """Quantas palavras o quadro mostra -- a metrica que o olho paga."""
    out = []
    for mark in words_seen or ():
        out.extend(str(mark.get('text') or '').split())
    return len(out)


def drive(overlay, rows, start_at, samples, push_every=None, rate=1.0):
    """Um cue com o relogio INJECTADO. Devolve (estado, linhas de log)."""
    lines = []
    cue = overlay._PlayerCue(rows, 100.0, at=0.0, rate=rate,
                             log=lines.append)
    seen_at = []
    for step in samples:
        if push_every and step and abs(step / push_every
                                       - round(step / push_every)) < 1e-9:
            # UM PUSH NOVO A CADA `push_every` SEGUNDOS: o relogio re-ancora e o
            # `t` avanca 1:1 com o tempo de parede (o video esta' a tocar).
            cue = overlay._PlayerCue(rows, 100.0 + step * rate, at=start_at + step,
                                     rate=rate, log=lines.append)
        seen_at.append((step, revealed(cue.frame(start_at + step))))
    return {'cue': cue, 'lines': lines, 'samples': seen_at}


def arms(overlay):
    rows = cue_rows(overlay)
    results = []

    # a NORMAL -- 60 publicacoes a 1,0 s, cada uma com o SEU cue (o video anda
    # 1:1 e o player serve uma linha nova a cada ~3,6 s). Para CADA publicacao a
    # revelacao tem de sair da primeira palavra e chegar mais longe 2,4 s depois:
    # um cue que nao revela e' a linha congelada que o dono descreveu.
    lines = []
    stalled_pushes = 0
    worst = None
    for second in range(60):
        base = 100.0 + second * 1.0
        cue = overlay._PlayerCue(cue_rows(overlay, base), base, at=float(second),
                                 log=lines.append)
        first = revealed(cue.frame(float(second)))
        later = revealed(cue.frame(float(second) + 2.4))
        if first < 1 or later <= first:
            stalled_pushes += 1
            if worst is None:
                worst = (second, first, later)
    quiet = not lines
    results.append(('a NORMAL', bool(stalled_pushes == 0 and quiet),
                    'pushes=60 stalled=%d worst=%s held_lines=%d'
                    % (stalled_pushes, worst, len(lines))))

    # b OWNER-STALL -- um unico cue, sem push, 8.2 s: o buraco medido.
    long_rows = cue_rows(overlay, 100.0, count=60)
    stall = drive(overlay, long_rows, 0.0, [0.0, 1.0, 3.0, 3.5, 5.0, 8.2])
    frozen_tail = stall['samples'][2][1] == stall['samples'][-1][1]
    held_ok = abs(stall['cue'].held_s - 5.2) < 0.01
    one_line = len(stall['lines']) == 1 and 'CAPTION_REVEAL_HELD' in stall['lines'][0]
    results.append(('b OWNER-STALL', bool(frozen_tail and held_ok and one_line),
                    'frozen_tail=%s held=%.2f lines=%d'
                    % (frozen_tail, stall['cue'].held_s, len(stall['lines']))))

    # c NO-INVENTION -- 2x: o tecto e' de tempo de PAREDE, nao de video.
    fast = drive(overlay, long_rows, 0.0, [1.0, 3.0, 30.0], rate=2.0)
    early, ceiling, later = (fast['samples'][0][1], fast['samples'][1][1],
                             fast['samples'][2][1])
    same = ceiling == later
    advanced = early < ceiling
    results.append(('c NO-INVENTION', bool(same and advanced),
                    'words@+1s=%d @+3s=%d @+30s=%d held=%.2f'
                    % (early, ceiling, later, fast['cue'].held_s)))

    # d PAUSE -- o `t` nunca anda: nao se inventa nada, e o episodio tem nome.
    paused = overlay._PlayerCue(long_rows, 100.0, at=0.0, rate=1.0,
                               log=lambda _m: None)
    before = revealed(paused.frame(1.0))
    ceiling = revealed(paused.frame(3.0))
    after = revealed(paused.frame(60.0))
    results.append(('d PAUSE', bool(before < ceiling and ceiling == after),
                    'words@+1s=%d @+3s=%d @+60s=%d held=%.2f'
                    % (before, ceiling, after, paused.held_s)))
    return results


MUTATIONS = (
    # (label, old, new, arm that must fall)
    ('no-witness', "                self.log('CAPTION_REVEAL_HELD gap_s=%.2f "
                   "hold_s=%.2f lost_s=%.2f '\n"
                   "                         't=%.3f rows=%d'\n"
                   "                         % (gap, PLAYER_HOLD_S, gap - PLAYER_HOLD_S,\n"
                   "                            self.t, len(self.rows)))",
     "                pass", 'b OWNER-STALL'),
    ('hold-30s', 'PLAYER_HOLD_S = 3.0', 'PLAYER_HOLD_S = 30.0', 'c NO-INVENTION'),
    ('hold-removed', 'elapsed = min(gap, PLAYER_HOLD_S)', 'elapsed = gap', 'd PAUSE'),
)


def neg_arm():
    with open(OVERLAY, encoding='utf-8') as fh:
        source = fh.read()
    caught = weak = 0
    for label, old, new, owner in MUTATIONS:
        if source.count(old) != 1:
            print('  RED   mutant %-14s ancora nao encontrada (%d) -- mutante decorativo'
                  % (label, source.count(old)))
            weak += 1
            continue
        module = load_from_source(source.replace(old, new, 1),
                                  'caption_overlay_mut_' + label.replace('-', '_'))
        got = {name: ok for name, ok, _detail in arms(module)}
        if not got.get(owner):
            print('  GREEN mutant %-14s caught by: %s' % (label, owner))
            caught += 1
        else:
            print('  RED   mutant %-14s SURVIVED on arm %s -- gate blind'
                  % (label, owner))
    total = len(MUTATIONS)
    ok = caught == total and weak == 0
    print('NEG-ARM VERDICT: %s (%d/%d mutants caught, %d decorative)'
          % ('PASS' if ok else 'FAIL', caught, total, weak))
    return 1 if ok else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args()
    if args.neg_arm:
        return neg_arm()

    overlay = load_from_path(OVERLAY, 'caption_overlay_hold_probe')
    failed = 0
    for name, ok, detail in arms(overlay):
        print('  %-16s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
        failed += 0 if ok else 1
    print('REVEAL-HOLD VERDICT: %s (%d failure(s))'
          % ('PASS' if not failed else 'FAIL', failed))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
