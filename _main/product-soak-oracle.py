# NO-BUG: Oracle: a whole PRODUCT session, read from its own artifacts, must show the
#        caption clock, the painted surface AND the history writer all advancing.
#        Capacidade pedida pelo dono (A3, soak de estado estavel); nao ha id de
#        `_main/bug-ledger.json` para isto, e o id nao se inventa.
"""Oracle: the product-level steady-state soak, judged from the product's own output.

THE HOLE THIS CLOSES (harness angle A3): nothing ran the whole product and asked,
afterwards, whether the three counters a caption needs had all advanced -- the
CLOCK (the cue time the overlay reveals against), the PAINT (the surface that
changed), and the HISTORY (the transcript the owner keeps). Unit oracles cover each
in isolation; the owner's reported failure ("froze after 2 seconds") is exactly the
state where one of them stops while the others keep going.

The same problem had two different faces in two sessions, both measured:

  * 2026-11-26 02:38 -- paints stopped for 13 s while `EXTERNAL_CAPTION_DRAWN`
    kept arriving and history kept being written (two rows at 02:38:11);
  * 2026-11-12 19:21 -- `CAPTION_LAND` froze its tuple for 6 minutes while the
    painted text changed (`caption-timeline` LAND-FROZEN).

WHY IT READS ARTIFACTS AND NOT A MOCK. The three counters live in three
subsystems (tick / overlay / store). A fake host that drives all three would
prove the fake. The log and the history store ARE the product's output, so this
instrument judges them, and the answer is falsifiable by the same file the owner
already has.

ARMS (each one pure over a parsed session, so a mutant can flip it)
  a SOAK-DURATION -- the session lasted at least `--minutes` of wall time; a
                     shorter one is CANNOT-MEASURE (never PASS, never FAIL);
  b PAINT-CADENCE -- while cues were ARRIVING, no stretch longer than
                     `MAX_PAINT_GAP_S` passed without a `CAPTION_PAINT_SURFACE`.
                     A real pause excuses it only when no cue arrived inside it --
                     a blank with lines arriving is the freeze;
  c CLOCK-ADVANCE -- the cue time never goes backwards without a seek/video-change
                     witness, and it moved at all;
  d HISTORY-ADVANCE -- every `final=true` line sent is in the transcript, or a
                     `HISTORY_REFUSED` names why not.

Usage:
  py -3 _main/product-soak-oracle.py                     # the last session, bar = 5 min
  py -3 _main/product-soak-oracle.py --minutes 0         # judge whatever session exists
  py -3 _main/product-soak-oracle.py --neg-arm           # rc 1 = every mutant CAUGHT
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
LOG_DEFAULT = os.path.join(HERE, 'webview-run.log')
HISTORY_DEFAULT = os.path.join(ROOT, 'history')

#: O TECTO DA CADENCIA. 3 s e' o mesmo limite que `caption-timeline` ja' usa para
#: STALL (`STALL_S`), e nenhuma sessao do dono o respeitou: 8,71 s em 2026-11-26.
MAX_PAINT_GAP_S = 3.0

TS_RE = re.compile(r'^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\.(\d{3}) ')
CLOCK_RE = re.compile(r'\bt=([0-9.]+)')
HISTORY_ROW_RE = re.compile(r'^- \[(\d{2}):(\d{2}):(\d{2})\]')
HISTORY_START_RE = re.compile(r'\bstart=([0-9.]+)')


def _epoch(day, clock, millis='000'):
    import datetime
    try:
        base = datetime.datetime.strptime('%s %s' % (day, clock),
                                          '%Y-%m-%d %H:%M:%S').timestamp()
    except ValueError:
        return None
    return base + int(millis) / 1000.0


def parse_log(text):
    """(session rows, wall seconds). A sessao e' a ULTIMA -- desde o ultimo
    `SHELL_STARTUP_STAGE ... stage=pre-lock`."""
    rows = []
    for line in text.splitlines():
        matched = TS_RE.match(line)
        if not matched:
            continue
        stamp = _epoch(*matched.groups())
        if stamp is None:
            continue
        rows.append({'t': stamp, 'body': line[matched.end():]})
    start = 0
    for index, row in enumerate(rows):
        if 'SHELL_STARTUP_STAGE' in row['body'] and 'stage=pre-lock' in row['body']:
            start = index
    session = rows[start:]
    if not session:
        return [], 0.0
    return session, session[-1]['t'] - session[0]['t']


def parse_history(root, day):
    """As linhas de historico do dia: (hora do dia em segundos, start=, texto)."""
    out = []
    folder = os.path.join(root, day) if day else root
    if not os.path.isdir(folder):
        return out
    for name in sorted(os.listdir(folder)):
        if not name.endswith('.md'):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    row = HISTORY_ROW_RE.match(line)
                    if not row:
                        continue
                    start = HISTORY_START_RE.search(line)
                    out.append({'hms': (int(row.group(1)) * 3600
                                        + int(row.group(2)) * 60
                                        + int(row.group(3))),
                                'start': float(start.group(1)) if start else None,
                                'text': line[:80]})
        except OSError:
            continue
    return out


def analyse(session, duration, history_rows, day=None, minutes=5.0):
    """O veredicto inteiro, puro -- e' isto que os mutantes atingem."""
    results = {}
    if not session:
        return {'a': (False, 'sem sessao no log'), 'verdict': 'CANNOT-MEASURE',
                'why': 'no-session'}

    # DISPLAY DESLIGADO NAO E' DEFEITO DE CADENCIA (2026-11-26). Uma sessao em
    # modo lane diz `CAPTION_WANTED_START on=false`: nesse modo nao existe cue
    # nem pintura POR CONFIGURACAO, e julgar `why=b` seria chamar defeito ao que
    # o interruptor desligou. Refusa pelo nome, antes da barra de duracao.
    if any(' CAPTION_WANTED_START on=false' in row['body'] for row in session):
        results['a'] = (False, 'CAPTION_WANTED_START on=false')
        return {'a': results['a'], 'verdict': 'CANNOT-MEASURE',
                'why': 'display-off', 'duration': duration}

    # a DURACAO -- um soak de 35 s nao pode passar por um de 5 min.
    if duration < minutes * 60.0:
        results['a'] = (False, 'duration=%.0fs bar=%.0fs'
                        % (duration, minutes * 60.0))
        return {'a': results['a'], 'verdict': 'CANNOT-MEASURE',
                'why': 'short-session', 'duration': duration}
    results['a'] = (True, 'duration=%.0fs bar=%.0fs'
                    % (duration, minutes * 60.0))

    paints = [row['t'] for row in session if ' CAPTION_PAINT_SURFACE ' in row['body']]
    cues = [row['t'] for row in session
            if ' EXTERNAL_CAPTION_DRAWN ' in row['body']
            or (' YOUTUBE_TICK_MS ' in row['body'] and ' rows=0 ' not in row['body'])]
    blanks = [row['t'] for row in session
              if ' CAPTION_WINDOW_BLANKED ' in row['body']
              or ' EXTERNAL_CAPTIONS_RELEASED ' in row['body']]

    # ZERO CUES NAO E' UMA SESSAO SEM DEFEITO -- E' UMA SESSAO SEM PRODUTO
    # (2026-11-26, encontrado ao auditar este juiz). Nenhum braco exigia uma
    # legenda: uma janela de 5 min com pinturas e ZERO textos entregues passava
    # em a/b/c/d e imprimia PASS, porque "nenhuma cue por dentro do buraco" e'
    # verdade quando nao ha cue nenhuma. Um veredicto sobre "as legendas
    # funcionam" precisa de pelo menos uma legenda para julgar; sem ela o
    # honesto e' CANNOT-MEASURE, nunca verde.
    if not cues:
        results['b'] = (False, 'nenhuma cue entregue na sessao')
        return {'a': results['a'], 'b': results['b'],
                'verdict': 'CANNOT-MEASURE', 'why': 'no-cues',
                'duration': duration}

    # b CADENCIA -- o buraco medido e' entre pinturas, e so' conta se uma cue
    # chegou por dentro dele: com o video parado nao ha o que pintar.
    worst_gap, worst_at, stalled = 0.0, None, False
    if not paints:
        results['b'] = (False, 'nenhuma CAPTION_PAINT_SURFACE na sessao')
    else:
        marks = sorted(paints)
        if cues:
            marks = sorted(set(paints + [cues[0], cues[-1]]))
        for before, after in zip(marks, marks[1:]):
            gap = after - before
            if gap <= worst_gap:
                continue
            inside = [c for c in cues if before < c < after]
            if not inside:
                continue
            excused = any(before <= b <= after for b in blanks) and len(inside) == 0
            worst_gap, worst_at = gap, after
            stalled = not excused
            if excused:
                worst_gap, worst_at = 0.0, None
        # O TECTO DA REVELACAO, AO LADO DA CADENCIA (2026-11-26): um
        # `CAPTION_REVEAL_HELD` diz que o relogio do overlay parou no tecto de
        # `PLAYER_HOLD_S` porque nenhuma leitura nova chegou. Ele nao muda o
        # veredicto (o tecto existe para nao inventar video), mas sem o numero no
        # relatorio um episodio de "congelou" continua a citar so' o buraco de
        # pintura e nao a causa.
        held = [row for row in session if ' CAPTION_REVEAL_HELD ' in row['body']]
        lost = 0.0
        for row in held:
            found = re.search(r'lost_s=([0-9.]+)', row['body'])
            if found:
                lost = max(lost, float(found.group(1)))
        results['b'] = (not stalled,
                        'worst_gap=%.2fs at=%s paints=%d cues=%d '
                        'reveal_held=%d max_lost_s=%.2f'
                        % (worst_gap, worst_at, len(paints), len(cues),
                           len(held), lost))

    # c RELOGIO -- o `t=` das linhas de pausa/seek nao pode recuar sem um
    # testemunho de seek/troca de video, e tem de avancar.
    clock = []
    for index, row in enumerate(session):
        if not any(token in row['body'] for token in
                   ('YOUTUBE_PAUSE_PROVEN', 'YOUTUBE_PAUSE_RESUMED',
                    'YOUTUBE_PAUSE_DISAGREED')):
            continue
        found = CLOCK_RE.search(row['body'])
        if found:
            clock.append((index, float(found.group(1))))
    recoil = []
    for (i0, t0), (i1, t1) in zip(clock, clock[1:]):
        if t1 >= t0 - 0.05:
            continue
        excused = any('YOUTUBE_SEEK_RESYNC' in session[j]['body']
                      or 'YOUTUBE_VIDEO_CHANGED' in session[j]['body']
                      for j in range(i0, i1 + 1))
        if not excused:
            recoil.append((t0, t1))
    moved = (clock[-1][1] - clock[0][1]) if len(clock) >= 2 else 0.0
    results['c'] = (bool(clock) and not recoil and moved > 0.0,
                    'samples=%d moved=%.2fs recoils=%d'
                    % (len(clock), moved, len(recoil)))

    # d HISTORICO -- cada linha `final=true` enviada esta' no transcrito, ou uma
    # recusa nomeada diz porque nao esta'.
    finals = [row for row in session
              if ' EXTERNAL_CAPTION_SENT ' in row['body'] and ' final=true' in row['body']]
    refused = [row for row in session if ' HISTORY_REFUSED ' in row['body']]
    day_rows = [r for r in history_rows if r['start'] is not None]
    missing = max(0, len(finals) - len(refused) - len(day_rows))
    results['d'] = (missing == 0,
                    'finals=%d history_rows=%d refused=%d missing=%d'
                    % (len(finals), len(day_rows), len(refused), missing))

    bad = [key for key in ('a', 'b', 'c', 'd') if not results[key][0]]
    return dict(results, verdict='FAIL' if bad else 'PASS', why=','.join(bad),
                duration=duration)


ARMS = (('a', 'SOAK-DURATION'), ('b', 'PAINT-CADENCE'),
        ('c', 'CLOCK-ADVANCE'), ('d', 'HISTORY-ADVANCE'))


# --------------------------------------------------------------- fixtures ---
def _stamp(offset):
    """`2026-11-26 HH:MM:SS.mmm` a partir de segundos desde 03:00:00."""
    total = 3 * 3600 + offset
    return '2026-11-26 %02d:%02d:%06.3f' % (int(total // 3600),
                                            int(total % 3600 // 60),
                                            total % 60.0)


def _fixture(minutes=6, paint_gap=0.5, finals=8, history=True, agree=True,
             cues=True, display_off=False):
    """Uma sessao sintetica na FORMA da do dono, com os numeros sob controlo."""
    lines = [_stamp(0) + ' sotto: SHELL_STARTUP_STAGE pid=1 stage=pre-lock']
    if display_off:
        lines.append(_stamp(0) + ' sotto: CAPTION_WANTED_START on=false '
                     'reason=lane(SOTTO_LANE_LAUNCH=1) stored=false')
    span = minutes * 60.0
    step = 0.0
    index = 0
    while step < span:
        clock = 100.0 + step
        if cues:
            lines.append(_stamp(step) + ' sotto: EXTERNAL_CAPTION_DRAWN '
                         'rows=2 lines=["a", "b"]')
        if step % 10.0 < 1e-9 and step > 0:
            lines.append(_stamp(step) + ' sotto: YOUTUBE_PAUSE_DISAGREED '
                         'paused_flag=True clock_rate=0.50 t=%.2f vid=X' % clock)
        if index % max(1, int(paint_gap / 0.5)) == 0 or paint_gap == 0:
            lines.append(_stamp(step) + ' sotto: CAPTION_PAINT_SURFACE '
                         'src=player rows=2 text="a" ms=1 epoch=1')
        index += 1
        step += 0.5
    if paint_gap > MAX_PAINT_GAP_S:
        # MUTANTE: um buraco de `paint_gap` segundos no meio, com cues a chegar.
        hole_start, hole_end = span / 2.0, span / 2.0 + paint_gap
        keep = []
        for line in lines:
            matched = TS_RE.match(line)
            if matched and 'CAPTION_PAINT_SURFACE' in line:
                stamp = _epoch(*matched.groups())
                base = _epoch('2026-11-26', '03:00:00', '000')
                if base is not None and hole_start < stamp - base < hole_end:
                    continue
            keep.append(line)
        lines = keep
    if agree:
        lines.append(_stamp(span) + ' sotto: YOUTUBE_PAUSE_DISAGREED '
                     'paused_flag=True clock_rate=0.50 t=%.2f vid=X' % (100.0 + span))
    for i in range(finals):
        lines.append(_stamp(span - 0.3 * i) + ' sotto: EXTERNAL_CAPTION_SENT '
                     'count=%d source=external:youtube:track final=true text="x"'
                     % (i + 1))
    text = '\n'.join(lines) + '\n'
    rows = []
    if history:
        for i in range(finals):
            rows.append({'hms': 0, 'start': 100.0 + i, 'text': 'x'})
    return text, rows


def judge_fixture(text, history_rows, minutes=5.0):
    session, duration = parse_log(text)
    return analyse(session, duration, history_rows, minutes=minutes)


def neg_arm():
    """Cada mutante tem de fazer a SUA arm cair -- o juiz e' o que ele atinge."""
    caught = weak = 0
    # O CONTROLO: a fixture BOA tem de passar. Se ela falhasse, os mutantes a
    # caírem nao provavam nada -- um portao que recusa tudo tambem e' cego.
    good_text, good_rows = _fixture()
    good = judge_fixture(good_text, good_rows)
    if good['verdict'] != 'PASS':
        print('  RED   fixture-boa nao passa (%s) -- os mutantes abaixo nao provam nada'
              % good.get('why'))
        weak += 1
    else:
        print('  PASS  a fixture boa passa (a/b/c/d verdes)')
    specs = (
        # (label, fixture kwargs, arm that must break, expected refusal)
        ('paint-stall-12s', dict(paint_gap=12.0), 'b', None),
        ('no-paints-at-all', dict(paint_gap=1e9), 'b', None),
        ('no-cues-at-all', dict(cues=False), 'b', 'no-cues'),
        ('history-silent', dict(history=False), 'd', None),
        ('short-session', dict(minutes=2), 'a', None),
        ('display-off-session', dict(display_off=True, cues=False), 'a', 'display-off'),
    )
    for label, kwargs, owner, refusal in specs:
        text, rows = _fixture(**kwargs)
        got = judge_fixture(text, rows)
        if refusal:
            # Uma sessao sem legendas tem de ser RECUSADA, nao aprovada: ate'
            # 2026-11-26 este juiz imprimia PASS nela.
            if got.get('verdict') == 'CANNOT-MEASURE' and got.get('why') == refusal:
                print('  GREEN mutant %-18s refused by name: %s'
                      % (label, got.get('why')))
                caught += 1
            else:
                print('  RED   mutant %-18s NOT refused (%s/%s) -- gate blind'
                      % (label, got.get('verdict'), got.get('why')))
            continue
        if got.get('verdict') == 'CANNOT-MEASURE' and owner != 'a':
            print('  RED   mutant %-18s fixture nem chegou a medir (%s)'
                  % (label, got.get('why')))
            weak += 1
            continue
        ok = got[owner][0]
        if not ok:
            print('  GREEN mutant %-18s caught by: %s (%s)'
                  % (label, owner, got[owner][1]))
            caught += 1
        else:
            print('  RED   mutant %-18s SURVIVED on arm %s -- gate blind'
                  % (label, owner))
    # A MUTACAO MAIS IMPORTANTE: um relogio que recua sem testemunho.
    text, rows = _fixture()
    # O ULTIMO `t=` da sessao recua para 10 s: nenhum `YOUTUBE_SEEK_RESYNC` nem
    # `YOUTUBE_VIDEO_CHANGED` o explica, entao e' o recuo que a arm c recusa.
    marks = list(re.finditer(r't=([0-9.]+) vid=X', text))
    if marks:
        last = marks[-1]
        text = text[:last.start(1)] + '10.00' + text[last.end(1):]
    got = judge_fixture(text, rows)
    if not got['c'][0]:
        print('  GREEN mutant %-18s caught by: c (%s)' % ('clock-recoil', got['c'][1]))
        caught += 1
    else:
        print('  RED   mutant %-18s SURVIVED on arm c' % 'clock-recoil')
    total = len(specs) + 1
    ok = caught == total and weak == 0
    print('NEG-ARM VERDICT: %s (%d/%d mutants caught, %d decorative)'
          % ('PASS' if ok else 'FAIL', caught, total, weak))
    return 1 if ok else 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--log', default=LOG_DEFAULT)
    ap.add_argument('--history', default=HISTORY_DEFAULT)
    ap.add_argument('--minutes', type=float, default=5.0)
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--fixture', action='store_true',
                    help='julga a fixture sintetica (nao depende do log do dono)')
    args = ap.parse_args()

    if args.neg_arm:
        return neg_arm()
    if args.fixture:
        text, rows = _fixture()
        got = judge_fixture(text, rows, minutes=args.minutes if args.minutes else 5.0)
        for key, name in ARMS:
            ok, detail = got[key]
            print('  %-16s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
        print('FIXTURE VERDICT: %s' % got['verdict'])
        return 0 if got['verdict'] == 'PASS' else 1

    try:
        with open(args.log, encoding='utf-8', errors='replace') as fh:
            text = fh.read()
    except OSError as exc:
        print('PRODUCT-SOAK CANNOT-MEASURE reason=%r' % (exc,))
        return 3
    session, duration = parse_log(text)
    day = None
    if session:
        stamp = session[0]['t']
        import datetime
        day = datetime.datetime.fromtimestamp(stamp).strftime('%Y-%m-%d')
    rows = parse_history(args.history, day)
    got = analyse(session, duration, rows, day=day, minutes=args.minutes)

    print('product-soak  log=%s  day=%s  duration=%.0fs  bar=%.0fs'
          % (args.log, day, got.get('duration', 0.0), args.minutes * 60.0))
    for key, name in ARMS:
        if key not in got:
            print('  %-16s SKIPPED (sessao nao medida)' % name)
            continue
        ok, detail = got[key]
        print('  %-16s %s  %s' % (name, 'PASS' if ok else 'FAIL', detail))
    print('VERDICT: %s%s' % (got['verdict'],
                             '' if got['verdict'] == 'PASS'
                             else '  why=' + str(got.get('why'))))
    if got['verdict'] == 'CANNOT-MEASURE':
        return 3
    return 0 if got['verdict'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
