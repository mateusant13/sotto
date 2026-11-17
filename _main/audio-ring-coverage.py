"""audio-ring-coverage - quanto do tempo de PAREDE o ring gravou, e ONDE se perdeu.

O INSTRUMENTO DA MEDIDA DE 2026-11-17. Ele responde a pergunta que o corpus de
2026-11-16 deixou aberta (`_main/bench/discord-call-20261116/manifest.json`:
`content_s` 13 516,7 contra `wall_span_s` 18 866,3 em 69 segmentos = 71,6 %):

    quanto do tempo de parede o ring cobriu, e a diferenca e' PERDA DO RING
    (fila) ou AUDIO QUE NUNCA CHEGOU (tap sem stream)?

AS DUAS FONTES, e a ordem em que sao preferidas -- conteudo antes de metadados:

  1. `index.jsonl` de HOJE: `wall_s`, `gap_s`, `dropped_s` que o proprio ring
     mediu na entrada (a partir de 2026-11-17). `provenance=recorded`.
  2. `index.jsonl` ANTIGO (sem esses campos): `wall_s` = `mtime - hora do nome`
     e `unaccounted_s` = `wall_s - (t1-t0)`. `provenance=mtime,+derived` --
     funciona, mas `mtime` e' metadado: um `copy`/`touch` mente e o numero deixa
     de ser uma medida do audio.

Por que `t1-t0` NAO e' a cobertura: ele e' `samples/rate` do que foi escrito, e
o ring so' escreve o que recebe. Um segmento perfeitamente continuo para o
indice pode ter atravessado 42 minutos de parede com 200 s de som dentro --
medido em `173532.24k.opus` (2 525,2 s de parede, 600,0 s declarados, 200,0 s de
audio real a 48 kHz).

Usage (leve: so' JSONL + `stat`, nenhum decode):
  python _main/audio-ring-coverage.py [--root H:/sotto] [--day 2026-11-16] [--json]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _index(root):
    p = os.path.join(root, 'history', 'audio', 'index.jsonl')
    out = []
    try:
        with open(p, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        return []
    return out


def _gaps(root):
    p = os.path.join(root, 'history', 'audio', 'gaps.jsonl')
    out = []
    try:
        with open(p, encoding='utf-8') as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except ValueError:
                        continue
    except OSError:
        return []
    return out


def _open_epoch(rec):
    """A hora de PAREDE em que o ficheiro abriu, do NOME dele.

    `history/audio/<AAAA-MM-DD>/<HHMMSS>.<kbps>k.opus` -- o nome e' o unico
    carimbo que o ring escreve no momento em que abre (o `t0` do indice e'
    relogio de AUDIO). Devolve None quando o nome nao obedece ao formato.
    """
    try:
        day = os.path.basename(os.path.dirname(rec['file']))
        name = os.path.basename(rec['file']).split('.')[0]
        y, m, d = [int(x) for x in day.split('-')]
        return _dt.datetime(y, m, d, int(name[0:2]), int(name[2:4]),
                            int(name[4:6])).timestamp()
    except (KeyError, ValueError, IndexError):
        return None


#: As taxas de mistura que o Windows entrega. A razao `samples/wall` de um
#: segmento SAUDAVEL da' o rate do tap com o erro do nome do ficheiro (o
#: `HHMMSS` trunca a hora de abertura a 1 s, logo a razao erra ~0,5 %), e um
#: segmento que drena um atraso da' mais do que o rate real. Por isso a
#: inferencia e' a MEDIANA e o resultado e' encaixado na taxa padrao mais perto
#: -- uma taxa de mistura e' um valor de uma lista, nao um numero livre.
_STD_RATES = (8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000, 88200, 96000)


def _snap_rate(hz):
    if not hz:
        return None
    return min(_STD_RATES, key=lambda r: abs(r - float(hz)))


def measure(root, day=None, tap_rate=None):
    """As medidas da cobertura do ring inteiro (ou de um dia). JSON-avel.

    `tap_rate` e' o rate REAL do tap em Hz. O ring DECLARA 16000 e recebe
    blocos a 48000 (`worker/sotto_worker.py:4440`), logo `samples/rate` do
    indice e' 3x a duracao real do audio -- medir cobertura com ele da' 214 %.
    Sem `--tap-rate`, o proprio audio responde: num segmento sem perda,
    `samples/wall_s` E' o rate do tap, logo a medida e' o percentil 90 dessa
    razao (perda so' empurra a razao para baixo).
    """
    rows = _index(root)
    if day:
        rows = [r for r in rows if ('/%s/' % day) in str(r.get('file', ''))]
    prepared = []
    for rec in rows:
        rate = float(rec.get('rate') or 16000)
        declared_s = round(int(rec.get('samples') or 0) / rate, 3)
        wall_s = rec.get('wall_s')
        wall_src = 'recorded' if isinstance(wall_s, (int, float)) else None
        if wall_s is None:
            opened = _open_epoch(rec)
            if opened is not None:
                try:
                    wall_s = os.path.getmtime(os.path.join(root, rec['file'])) - opened
                    wall_src = 'mtime'
                except OSError:
                    wall_s = None
        prepared.append({'rec': rec, 'rate': rate, 'declared_s': declared_s,
                         'wall_s': wall_s, 'wall_src': wall_src})
    # O RATE REAL, medido no audio (ou dado). `p90` e nao `max`: um segmento
    # cujo `mtime` foi tocado depois tem uma razao absurda, e um so' bastaria
    # para envenenar a inferencia inteira.
    rate_src = 'flag'
    raw_rate = None
    if tap_rate:
        tap_rate = float(tap_rate)
    else:
        ratios = []
        for p in prepared:
            w = p['wall_s']
            n = int(p['rec'].get('samples') or 0)
            if isinstance(w, (int, float)) and w >= 1.0 and n > 0:
                ratios.append(n / float(w))
        if ratios:
            ratios.sort()
            raw_rate = ratios[len(ratios) // 2]
            tap_rate = _snap_rate(raw_rate)
            rate_src = 'inferred'
        else:
            tap_rate = None
            rate_src = 'index'
    out_rows = []
    for p in prepared:
        rec, rate, declared_s, wall_s, wall_src = (p['rec'], p['rate'],
                                                  p['declared_s'], p['wall_s'],
                                                  p['wall_src'])
        content_s = (round(int(rec.get('samples') or 0) / tap_rate, 3)
                     if tap_rate else declared_s)
        gap_s = rec.get('gap_s')
        gap_src = 'recorded' if isinstance(gap_s, (int, float)) else None
        dropped_s = rec.get('dropped_s')
        # O QUE NAO TEM EXPLICACAO no registo: parede que o segmento atravessou
        # sem amostras dentro. Num segmento antigo (sem `gap_s`) este numero
        # junta tap parado + fila; num novo, `gap_s` e `dropped_s` o desdobram.
        unaccounted = None
        if isinstance(wall_s, (int, float)):
            unaccounted = round(float(wall_s) - content_s, 3)
        if gap_s is None:
            gap_s = unaccounted
            gap_src = 'derived' if unaccounted is not None else None
        out_rows.append({
            'file': os.path.basename(str(rec.get('file', ''))),
            'day': os.path.basename(os.path.dirname(str(rec.get('file', '')))),
            'content_s': content_s,
            'declared_s': declared_s,
            'wall_s': round(float(wall_s), 3) if isinstance(wall_s, (int, float)) else None,
            'gap_s': round(float(gap_s), 3) if isinstance(gap_s, (int, float)) else None,
            'queue_drop_s': round(float(dropped_s), 3) if isinstance(dropped_s, (int, float)) else None,
            'unaccounted_s': unaccounted,
            'wall_src': wall_src,
            'gap_src': gap_src,
        })
    content = round(sum(r['content_s'] for r in out_rows), 1)
    wall = round(sum(r['wall_s'] for r in out_rows if r['wall_s'] is not None), 1)
    gaps = [r for r in out_rows if r['gap_s'] is not None]
    gap_s = round(sum(r['gap_s'] for r in gaps), 1)
    drops = round(sum(r['queue_drop_s'] for r in out_rows
                      if r['queue_drop_s'] is not None), 1)
    explained = round(sum(r['unaccounted_s'] for r in out_rows
                          if r['unaccounted_s'] is not None), 1)
    markers = _gaps(root)
    if day:
        markers = [m for m in markers
                   if ('/%s/' % day) in str(m.get('file') or '')]
    worst = sorted((r for r in out_rows if r['unaccounted_s'] is not None),
                   key=lambda r: -r['unaccounted_s'])[:5]
    return {
        'root': root,
        'day': day or 'all',
        'segments': len(out_rows),
        'content_s': content,
        'wall_s': wall,
        'covered': round(content / wall, 4) if wall else None,
        'unaccounted_s': explained,
        'tap_gap_s': gap_s,
        'queue_drop_s': drops,
        'gap_markers': len(markers),
        'gap_markers_s': round(sum(float(m.get('gap_s') or 0) for m in markers), 1),
        'tap_rate': round(tap_rate, 0) if tap_rate else None,
        'tap_rate_raw': round(raw_rate, 0) if raw_rate else None,
        'tap_rate_src': rate_src,
        'provenance': {
            'wall': sorted({r['wall_src'] for r in out_rows if r['wall_src']}),
            'gap': sorted({r['gap_src'] for r in out_rows if r['gap_src']}),
        },
        'worst': worst,
        'rows': out_rows,
    }


def render(m):
    prov = m['provenance']
    print('AUDIO-RING COVERAGE root=%s day=%s' % (m['root'], m['day']))
    print('  segments=%d content_s=%.1f wall_s=%.1f covered=%s'
          % (m['segments'], m['content_s'], m['wall_s'],
             ('%.4f' % m['covered']) if m['covered'] is not None else 'n/a'))
    print('  unaccounted_s=%.1f tap_gap_s=%.1f queue_drop_s=%.1f '
          'gap_markers=%d gap_markers_s=%.1f'
          % (m['unaccounted_s'], m['tap_gap_s'], m['queue_drop_s'],
             m['gap_markers'], m['gap_markers_s']))
    print('  tap_rate=%s src=%s  provenance wall=%s gap=%s'
          % (m['tap_rate'], m['tap_rate_src'],
             ','.join(prov['wall']) or '-', ','.join(prov['gap']) or '-'))
    for r in m['worst']:
        print('  worst %s content_s=%.1f wall_s=%.1f gap_s=%.1f unaccounted_s=%.1f '
              'wall_src=%s gap_src=%s'
              % (r['file'], r['content_s'], r['wall_s'] or 0.0, r['gap_s'] or 0.0,
                 r['unaccounted_s'] or 0.0, r['wall_src'] or '-', r['gap_src'] or '-'))
    print('COVERAGE segments=%d content_s=%.1f wall_s=%.1f covered=%s '
          'unaccounted_s=%.1f tap_gap_s=%.1f queue_drop_s=%.1f gap_markers=%d '
          'tap_rate=%s wall_src=%s gap_src=%s'
          % (m['segments'], m['content_s'], m['wall_s'],
             ('%.4f' % m['covered']) if m['covered'] is not None else 'n/a',
             m['unaccounted_s'], m['tap_gap_s'], m['queue_drop_s'],
             m['gap_markers'], m['tap_rate'],
             ','.join(prov['wall']) or '-', ','.join(prov['gap']) or '-'))
    return 0 if m['segments'] else 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--root', default=ROOT)
    ap.add_argument('--day', default=None, help='AAAA-MM-DD (default: todos)')
    ap.add_argument('--tap-rate', type=float, default=None,
                    help='rate REAL do tap em Hz (default: inferido do audio)')
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    m = measure(os.path.abspath(args.root), args.day, tap_rate=args.tap_rate)
    if args.json:
        print(json.dumps({k: v for k, v in m.items() if k != 'rows'},
                         indent=1, ensure_ascii=False))
        return 0 if m['segments'] else 2
    return render(m)


if __name__ == '__main__':
    sys.exit(main())
