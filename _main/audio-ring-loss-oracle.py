"""audio-ring-loss-oracle - a perda de audio do ring tem de ficar REGISTADA.

O DEFEITO QUE ESTE PORTAO JULGA (medido 2026-11-17 no corpus de 2026-11-16,
`_main/bench/discord-call-20261116/manifest.json`): o ring cobriu 71,6 % do
tempo de parede do dia, e os buracos maiores estavam DENTRO de um segmento --
2 325,2 s em `173532.24k.opus`, 1 133,0 s em `170639.24k.opus`. Investigacao
(este portao nasceu dela):

  * o escritor NAO parou: cada segmento tem exactamente 9 600 000 amostras e o
    `ffprobe` de cada ficheiro e' `samples/rate`, ou seja o indice DESCREVE o
    audio guardado;
  * a perda veio de FORA: `block_samples` do tap / 48 000 = 12 037,3 s em
    17 129 s de parede (70,3 %), e o ring guardou 11 600 s disso;
  * e NADA dizia isso em lado nenhum: `index.jsonl` declarava 600 s continuos,
    `dropped_s` existia so' em memoria, e o buraco tinha de ser ADIVINHADO
    comparando o `mtime` do ficheiro com o nome.

As seis emendas julgadas aqui, todas no comportamento (nao no fonte):

  A1 um intervalo de parede sem NENHUM bloco vira linha em `gaps.jsonl`;
  A2 o segmento que o atravessou diz `wall_s`, `gap_s` e `dropped_s`;
  A3 `status()` conta os buracos e as amostras que a fila recusou;
  A4 o instrumento de cobertura (`_main/audio-ring-coverage.py`) le esses campos
     como REGISTADOS (`provenance=recorded`), nao como `mtime` derivado;
  A5 um segmento com audio e depois SILENCIO fecha pela parede (2 s de segmento,
     3 s calado) -- a rotacao ociosa comparava `time.monotonic()` com um
     `time.time()` e NUNCA disparava (o bug que deixou 2 525 s num ficheiro);
  A6 o buraco e a perda de fila tambem vao para o LOG (uma linha por buraco,
     uma linha por janela de perda, com o numero).

`--neg-arm` muta uma COPIA de `worker/audio_ring.py` em quatro sitios, um por
classe de emenda, e exige as quatro vermelhas. Um portao que so' passa com o
codigo de hoje nao prova nada; o mutante e' a metade que falta.

Usage:
  python _main/audio-ring-loss-oracle.py [--ring worker/audio_ring.py]
  python _main/audio-ring-loss-oracle.py --neg-arm
"""
from __future__ import annotations

import argparse
import importlib.util
import io
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RING = os.path.join(ROOT, 'worker', 'audio_ring.py')
COVERAGE = os.path.join(HERE, 'audio-ring-coverage.py')

#: 0,1 s de audio a 16 kHz (a forma do bloco do tap), e um "burst" de 1,0 s que
#: a fila de 0,5 s NAO aceita -- e' a perda exacta que o portao cobra.
BLOCK = 1600
BURST = 16000
GAP_MIN_S = 0.3
GAP_INJECTED_S = 0.45
SEGMENT_S = 2.0


def _load(path, name):
    """Importa `path` como modulo novo (uma copia mutada aterra aqui)."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _load_coverage():
    return _load(COVERAGE, 'audio_ring_coverage_probe')


def _block(np, value=0.05):
    """UM bloco de BLOCK amostras float32 (nao silencio: o nivel nao importa)."""
    return (np.sin(np.arange(BLOCK) * 0.05) * value).astype('float32')


def _wait(cond, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return bool(cond())


def probe_loss(mod, np, tmp):
    """A1-A3, A6: um buraco de chegada e uma recusa de fila, num segmento real."""
    logs = []
    ring = mod.AudioRing(tmp, hours=1.0, kbps=24, segment_s=SEGMENT_S,
                         queue_s=0.5, cap_mb=20.0, gap_min_s=GAP_MIN_S,
                         log=logs.append)
    if not ring.enabled:
        return {'error': 'ring did not start (no ffmpeg?)', 'logs': logs}
    out = {'logs': logs}
    try:
        blk = _block(np)
        for _ in range(8):                       # 0,8 s de audio, a 1x
            ring.push(blk)
            time.sleep(0.1)
        # A RECUSA: 1,0 s de audio contra uma fila de 0,5 s. `n > _q_max` e'
        # recusado mesmo com a fila vazia -- a recusa e' deterministica.
        ring.push((np.zeros(BURST, dtype='float32')))
        time.sleep(GAP_INJECTED_S)               # > gap_min_s: o tap cala-se
        for _ in range(12):                      # + 1,2 s fecha o segmento (2,0 s)
            ring.push(blk)
            time.sleep(0.1)
        _wait(lambda: bool(mod.read_index(tmp)), 6.0)
    finally:
        ring.close()
    out['gaps'] = mod.read_gaps(tmp)
    out['rows'] = mod.read_index(tmp)
    out['status'] = ring.status()
    return out


def probe_idle(mod, np, tmp):
    """A5: audio e depois silencio -- o segmento TEM de fechar pela parede."""
    logs = []
    ring = mod.AudioRing(tmp, hours=1.0, kbps=24, segment_s=SEGMENT_S,
                         cap_mb=20.0, gap_min_s=60.0, log=logs.append)
    out = {'logs': logs}
    if not ring.enabled:
        out['error'] = 'ring did not start (no ffmpeg?)'
        return out
    try:
        blk = _block(np)
        for _ in range(10):                      # 1,0 s de audio, metade do segmento
            ring.push(blk)
            time.sleep(0.1)
        # O ESCRITOR OCIOSO: `get(timeout=1.0)` volta vazio e o ramo de ocioso
        # decide. Com o relogio errado a comparacao e' negativa para sempre e
        # nenhuma linha de indice aparece.
        out['closed_by_wall'] = _wait(lambda: bool(mod.read_index(tmp)), 8.0)
    finally:
        ring.close()
    out['rows'] = mod.read_index(tmp)
    return out


def judge(mod, np):
    """Os seis arms. Devolve [(nome, ok, detalhe)]."""
    arms = []
    tmp = tempfile.mkdtemp(prefix='ring-loss-')
    tmp2 = tempfile.mkdtemp(prefix='ring-idle-')
    try:
        got = probe_loss(mod, np, tmp)
        if got.get('error'):
            return [('A1-marcador-de-buraco', False, got['error'])]
        gaps = got['gaps']
        rows = got['rows']
        st = got['status']
        logs = got['logs'] or []
        one = [g for g in gaps if GAP_MIN_S <= float(g.get('gap_s') or 0) <= 2.0]
        arms.append(('A1-marcador-de-buraco', bool(one),
                     'rows=%d gaps=%d gap_s=%s'
                     % (len(gaps), len(gaps),
                        ','.join('%.2f' % float(g.get('gap_s') or 0) for g in gaps[:3]))))
        seg = rows[0] if rows else {}
        ok_a2 = (isinstance(seg.get('wall_s'), (int, float))
                 and float(seg['wall_s']) >= float(seg.get('t1', 0)) - float(seg.get('t0', 0)) + 0.2
                 and float(seg.get('gap_s') or 0) >= GAP_INJECTED_S * 0.8
                 and float(seg.get('dropped_s') or 0) >= 0.5)
        arms.append(('A2-segmento-diz-a-perda', ok_a2,
                     'wall_s=%s gap_s=%s dropped_s=%s samples=%s'
                     % (seg.get('wall_s'), seg.get('gap_s'), seg.get('dropped_s'),
                        seg.get('samples'))))
        ok_a3 = (int(st.get('gaps') or 0) >= 1 and float(st.get('dropped_s') or 0) >= 0.5
                 and len(gaps) >= 1)
        arms.append(('A3-contadores-de-perda', ok_a3,
                     'gaps=%s gap_s=%s dropped_s=%s'
                     % (st.get('gaps'), st.get('gap_s'), st.get('dropped_s'))))
        cov = _load_coverage()
        m = cov.measure(tmp, tap_rate=16000)
        ok_a4 = (m['gap_markers'] >= 1
                 and 'recorded' in (m['provenance']['wall'] or [])
                 and 'recorded' in (m['provenance']['gap'] or [])
                 and m['tap_gap_s'] >= GAP_INJECTED_S * 0.8)
        arms.append(('A4-instrumento-le-o-registo', ok_a4,
                     'covered=%s tap_gap_s=%.2f markers=%d wall_src=%s gap_src=%s'
                     % (m['covered'], m['tap_gap_s'], m['gap_markers'],
                        ','.join(m['provenance']['wall']),
                        ','.join(m['provenance']['gap']))))
        idle = probe_idle(mod, np, tmp2)
        first = (idle.get('rows') or [{}])[0]
        ok_a5 = (bool(idle.get('closed_by_wall'))
                 and 0 < int(first.get('samples') or 0) < int(SEGMENT_S * 16000))
        arms.append(('A5-rotacao-por-parede', ok_a5,
                     'closed_by_wall=%s samples=%s rows=%d'
                     % (idle.get('closed_by_wall'), first.get('samples'),
                        len(idle.get('rows') or []))))
        joined = '\n'.join(str(x) for x in logs)
        ok_a6 = ('gap ' in joined and 'dropped ' in joined)
        arms.append(('A6-log-da-perda', ok_a6,
                     'gap_line=%s drop_line=%s'
                     % ('gap ' in joined, 'dropped ' in joined)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(tmp2, ignore_errors=True)
    return arms


#: As quatro mutacoes, uma por classe de emenda. Cada uma e' uma string EXACTA do
#: fonte de hoje; se ela deixar de existir o portao diz "ANCORA NAO ENCONTRADA"
#: em vez de fingir que testou.
MUTATIONS = [
    ('M1-buraco-nao-detectado',
     '                if gap >= self._gap_min_s:',
     '                if False:  # M1'),
    ('M2-segmento-sem-perda',
     "               'wall_s': wall_s,\n"
     "               'gap_s': round(seg_gap_s, 3),\n"
     "               'dropped_s': round(seg_dropped / float(self.rate), 3)}",
     '               }'),
    ('M3-fila-nao-contada',
     '                self.dropped_s += n / float(self.rate)\n'
     '                self._dropped_samples += n\n'
     '                self._seg_dropped += n',
     '                pass  # M3'),
    ('M4-rotacao-com-o-relogio-errado',
     'time.monotonic() - self._seg_started_mono >= self.segment_s',
     'time.monotonic() - self._seg_started >= self.segment_s'),
]


def neg_arm():
    src = io.open(RING, encoding='utf-8', newline='').read()
    import numpy as np
    caught = 0
    tmp = tempfile.mkdtemp(prefix='ring-mut-')
    try:
        for name, old, new in MUTATIONS:
            if old not in src:
                print('%s ANCORA NAO ENCONTRADA -- mutacao impossivel' % name)
                continue
            p = os.path.join(tmp, 'audio_ring_mut.py')
            io.open(p, 'w', encoding='utf-8', newline='').write(src.replace(old, new, 1))
            try:
                mod = _load(p, 'audio_ring_mut')
                arms = judge(mod, np)
                broken = [a[0] for a in arms if not a[1]]
            except Exception as exc:                # noqa: BLE001 -- mutante quebrado conta
                broken = ['EXC:%r' % (exc,)]
            if broken:
                caught += 1
                print('%s CAUGHT by %s' % (name, ','.join(broken)))
            else:
                print('%s NOT-CAUGHT' % name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('NEG-ARM: %s -- %d/%d'
          % ('PASS' if caught == len(MUTATIONS) else 'FAIL', caught, len(MUTATIONS)))
    return 0 if caught == len(MUTATIONS) else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--ring', default=RING)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)

    if not os.path.exists(args.ring):
        print('AUDIO-RING-LOSS VERDICT: FAIL -- %s ausente' % args.ring)
        return 1
    import numpy as np
    mod = _load(os.path.abspath(args.ring), 'audio_ring_under_test')
    arms = judge(mod, np)
    for name, ok, detail in arms:
        print('%s %s %s' % ('PASS' if ok else 'FAIL', name, detail))
    bad = [a for a in arms if not a[1]]
    print('AUDIO-RING-LOSS VERDICT: %s -- %d/%d'
          % ('PASS' if not bad else 'FAIL', len(arms) - len(bad), len(arms)))
    if args.neg_arm:
        return neg_arm()
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
