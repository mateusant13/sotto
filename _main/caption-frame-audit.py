"""AUDITORIA DA LEGENDA, PONTA A PONTA -- com detector de FLICKER.

ORDEM DO DONO (2026-11-02), verbatim: *"para de reagir e faz full audit. alem
disso, as legendas tao flickando. tao bugadas. ficam sumindo e aperecendo ou
trocando a atual e a antiga ao mesmo tempo"*.

O QUE ESTE INSTRUMENTO JULGA, e por que cada regra existe:

  1. VIDA       -- quantos quadros desenhados, a que cadencia, e quantos textos
                   distintos. Uma "legenda viva" tem de mudar de texto quando o
                   player muda, nao a 60 ms com o mesmo texto.
  2. REPINTURA   -- o mesmo `lines=` desenhado duas vezes seguidas. Repintar
                   texto identico e' trabalho sem mudanca (e' o que faz o texto
                   piscar quando o desenho tem animacao de entrada).
  3. OSCILACAO   -- A -> B -> A dentro de `--window` segundos. E' literalmente
                   *"trocando a atual e a antiga ao mesmo tempo"*: o desenho volta
                   ao estado anterior sem que o player tenha voltado.
  4. PULO DE LINHAS -- a MESMA ultima linha desenhada com 1 linha e depois com 2
                   (ou 2 -> 1) dentro da janela: a caixa do player encolhe por um
                   instante e o overlay segue essa contracao -- *"ficam sumindo e
                   aperecendo"*.
  5. VAZIO       -- um quadro sem linha nenhuma entre dois quadros com linha.
  6. ATRASO      -- do `YOUTUBE_CAPTION` (a leitura que reconheceu a cue) ate o
                   `EXTERNAL_CAPTION_DRAWN` que mostrou o texto dela. Medido, nunca
                   afirmado.

PROVAS DE DETECCAO: `--neg-arm` injeta sequencias CONHECIDAS (flicker de
oscilacao, pulo de linhas, vazio) e exige que o detector as apanhe, e uma
sequencia LIMPA (crescimento monotono de uma linha) que tem de passar. Um
detector sem braco negativo nao e' um detector.

USO:
    python _main/caption-frame-audit.py                      # log vivo
    python _main/caption-frame-audit.py --since 23:00        # so' de hoje, 23:00
    python _main/caption-frame-audit.py --neg-arm            # prova o detector
"""
from __future__ import annotations

import argparse
import ast
import datetime
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LOG = os.path.join(HERE, 'webview-run.log')

STAMP = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) sotto: ')
# O MESMO QUADRO, DESENHADO OU SO' DECIDIDO (2026-11-02). `EXTERNAL_CAPTION_DRAWN`
# so' existe com o overlay LIGADO; `YT_FRAME` e' o que o `_tick`decidiu, com o
# produtor ao lado (`src=`), e por isso a CADEIA pode ser auditada com a legenda
# desligada -- foi assim que a oscilacao dos dois produtores apareceu em 23:16.
DRAWN = re.compile(r'EXTERNAL_CAPTION_DRAWN rows=(\d+) lines=(\[.*\])')
DECIDED = re.compile(r'YT_FRAME src=(\S+) rows=(\d+) lines=(\[.*\])')
CAPTION = re.compile(r'YOUTUBE_CAPTION .*?text=(.*)$')


def parse_log(path=LOG, since=None):
    """[(quando, linhas)] dos quadros desenhados, e [(quando, texto)] das leituras."""
    frames, reads = [], []
    if not os.path.exists(path):
        return frames, reads
    with io.open(path, encoding='utf-8', errors='replace') as handle:
        for line in handle:
            match = STAMP.match(line)
            if not match:
                continue
            try:
                when = datetime.datetime.strptime(match.group(1),
                                                  '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                continue
            if since is not None and when < since:
                continue
            body = line[match.end():]
            drawn = DRAWN.search(body)
            if drawn:
                try:
                    lines = ast.literal_eval(drawn.group(2))
                except (ValueError, SyntaxError):
                    continue
                frames.append((when, [str(x) for x in lines]))
                continue
            decided = DECIDED.search(body)
            if decided:
                try:
                    lines = ast.literal_eval(decided.group(3))
                except (ValueError, SyntaxError):
                    continue
                frames.append((when, [str(x) for x in lines]))
                continue
            read = CAPTION.search(body)
            if read:
                text = read.group(1).strip().strip("'\"")
                reads.append((when, text))
    return frames, reads


def audit(frames, reads, window=1.5):
    """As seis perguntas, sobre a sequencia de quadros. Sem I/O."""
    out = {'frames': len(frames)}
    if not frames:
        out.update({'verdict': 'NO-FRAMES', 'note': 'nenhum quadro desenhado'})
        return out
    span = (frames[-1][0] - frames[0][0]).total_seconds()
    out['span_s'] = round(span, 2)
    out['per_s'] = round(len(frames) / span, 2) if span > 0 else None
    out['distinct_text'] = len({tuple(lines) for _t, lines in frames})
    empty = [f for f in frames if not any(str(x).strip() for x in f[1])]
    out['empty_frames'] = len(empty)
    # PULO DE LINHAS: mesma ultima linha, contagem diferente.
    wobble = []
    for i in range(1, len(frames)):
        prev_lines, cur_lines = frames[i - 1][1], frames[i][1]
        if not prev_lines or not cur_lines:
            continue
        gap = (frames[i][0] - frames[i - 1][0]).total_seconds()
        if gap > window:
            continue
        if prev_lines[-1] == cur_lines[-1] and len(prev_lines) != len(cur_lines):
            wobble.append((frames[i][0], prev_lines, cur_lines))
    out['row_count_wobble'] = len(wobble)
    out['wobble_examples'] = wobble[:3]
    # OSCILACAO: A -> B -> A dentro da janela.
    osc = []
    for i in range(2, len(frames)):
        a, b, c = frames[i - 2], frames[i - 1], frames[i]
        if (c[0] - a[0]).total_seconds() > window:
            continue
        if a[1] == c[1] and b[1] != a[1]:
            osc.append((a[0], a[1], b[1], c[1]))
    out['oscillations'] = len(osc)
    out['oscillation_examples'] = osc[:3]
    # REPINTURA: quadro identico ao anterior.
    repaint = sum(1 for i in range(1, len(frames)) if frames[i][1] == frames[i - 1][1])
    out['repaints'] = repaint
    # ATRASO: da leitura que reconheceu o texto ate o quadro que o mostrou.
    # O PAR TEM DE SER PROXIMO (corrigido 2026-11-02). A versao anterior emparelhava
    # a PRIMEIRA leitura que contivesse o texto, sem limite de idade: com o video em
    # pausa o `YOUTUBE_CAPTION` so' aparece na MUDANCA, e o relatorio publicou
    # `mediana=151731 ms` -- um numero que nao media atraso nenhum. Um par a mais de
    # 1,5 s de distancia nao e' um atraso medido: e' duas coisas que nao se ligam.
    LAG_MAX_S = 1.5
    lag = []
    skipped = 0
    for when, lines in frames:
        if not lines:
            continue
        needle = lines[-1]
        if not needle:
            continue
        best = None
        for r_when, r_text in reversed(reads):
            age = (when - r_when).total_seconds()
            if age < 0:
                continue
            if age > LAG_MAX_S:
                break
            if needle[:24] in r_text:
                best = age
                break
        if best is None:
            skipped += 1
        else:
            lag.append(best * 1000.0)
    if lag:
        lag_sorted = sorted(lag)
        out['lag_ms_median'] = round(lag_sorted[len(lag_sorted) // 2], 1)
        out['lag_ms_max'] = round(lag_sorted[-1], 1)
        out['lag_n'] = len(lag)
    out['lag_unpaired'] = skipped
    flicker = (out['oscillations'] > 0 or out['row_count_wobble'] > 2
               or out['empty_frames'] > 0)
    out['verdict'] = 'FLICKER' if flicker else 'CLEAN'
    return out


def report(info, stream=sys.stdout):
    print('quadros=%d  janela=%.2fs  por_segundo=%s  textos_distintos=%d'
          % (info['frames'], info.get('span_s') or 0.0, info.get('per_s'),
             info.get('distinct_text') or 0), file=stream)
    print('repinturas=%d  oscilacoes=%d  pulos_de_linha=%d  vazios=%d'
          % (info.get('repaints', 0), info.get('oscillations', 0),
             info.get('row_count_wobble', 0), info.get('empty_frames', 0)),
          file=stream)
    if info.get('lag_n'):
        print('atraso leitura->desenho: n=%d mediana=%.1f ms pior=%.1f ms (%d quadros sem par <1,5 s)'
              % (info['lag_n'], info['lag_ms_median'], info['lag_ms_max'],
                 info.get('lag_unpaired') or 0), file=stream)
    for when, prev, cur in info.get('wobble_examples') or ():
        print('  PULO   %s  %d linhas -> %d  %r' % (when.strftime('%H:%M:%S.%f')[:-3],
                                                    len(prev), len(cur), cur[-1][:48]),
              file=stream)
    for when, a, b, _c in info.get('oscillation_examples') or ():
        print('  OSCILA %s  %r -> %r -> %r' % (when.strftime('%H:%M:%S.%f')[:-3],
                                               a[-1][:28] if a else '', b[-1][:28] if b else '',
                                               a[-1][:28] if a else ''), file=stream)
    print('VERDICT: %s' % info['verdict'], file=stream)


def neg_arm():
    """Sequencias CONHECIDAS: o detector tem de apanhar as tres e passar a limpa."""
    base = datetime.datetime(2026, 11, 2, 12, 0, 0)
    def frames_of(seq, step=0.06):
        return [(base + datetime.timedelta(seconds=i * step), lines)
                for i, lines in enumerate(seq)]
    cases = [
        ('limpa (crescimento monotono)', frames_of([
            ['A'], ['A b'], ['A b c'], ['A b c d'],
        ]), 'CLEAN'),
        ('oscilacao (atual/antiga trocadas)', frames_of([
            ['antiga', 'atual 1'], ['atual 1 novo'], ['antiga', 'atual 1'],
        ]), 'FLICKER'),
        ('pulo de linhas (2 -> 1 -> 2)', frames_of([
            ['velha', 'linha'], ['linha'], ['velha', 'linha'], ['velha', 'linha x'],
        ]), 'FLICKER'),
        ('vazio entre dois quadros', frames_of([
            ['velha', 'linha'], [], ['velha', 'linha'],
        ]), 'FLICKER'),
    ]
    ok = 0
    for name, frames, want in cases:
        got = audit(frames, [])['verdict']
        good = got == want
        ok += 1 if good else 0
        print('NEG-ARM %-34s %s  esperado=%s obtido=%s'
              % (name, 'PASS' if good else 'FAIL', want, got))
    print('NEG-ARM VERDICT: %s (%d/%d)' % ('PASS' if ok == len(cases) else 'FAIL',
                                           ok, len(cases)))
    return 0 if ok == len(cases) else 1


def _stamp(text):
    """HH:MM (de hoje) ou ISO completo -> datetime, ou None."""
    if not text:
        return None
    match = re.match(r'^(\d{2}):(\d{2})(?::(\d{2}))?$', text)
    if match:
        hour, minute, second = (int(x) if x else 0 for x in match.groups())
        return datetime.datetime.combine(datetime.date.today(),
                                         datetime.time(hour, minute, second))
    return datetime.datetime.fromisoformat(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--log', default=LOG)
    ap.add_argument('--since', default=None, help='HH:MM (hoje) ou ISO completo')
    ap.add_argument('--until', default=None, help='HH:MM (hoje) ou ISO completo')
    ap.add_argument('--window', type=float, default=1.5)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    if args.neg_arm:
        return neg_arm()
    since = _stamp(args.since)
    until = _stamp(args.until)
    frames, reads = parse_log(args.log, since)
    if until is not None:
        frames = [f for f in frames if f[0] <= until]
        reads = [r for r in reads if r[0] <= until]
    info = audit(frames, reads, window=args.window)
    report(info)
    return 0 if info['verdict'] == 'CLEAN' else 1


if __name__ == '__main__':
    raise SystemExit(main())
