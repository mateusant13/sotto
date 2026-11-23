# NO-BUG: a perda do ring medida em 2026-11-17 (71,6 % de parede coberta, 2 325,2 s de buraco DENTRO de um segmento) -- trabalho de CAPACIDADE/observabilidade sobre um defeito medido e datado, para o qual `_main/bug-ledger.json` nao tem id
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

As sete emendas julgadas aqui, todas no comportamento (nao no fonte):

  A1 um intervalo de parede sem NENHUM bloco vira linha em `gaps.jsonl`;
  A2 o segmento que o atravessou diz `wall_s`, `gap_s` e `dropped_s`;
  A3 `status()` conta os buracos e as amostras que a fila recusou;
  A4 o instrumento de cobertura (`_main/audio-ring-coverage.py`) le esses campos
     como REGISTADOS (`provenance=recorded`), nao como `mtime` derivado;
  A5 um segmento com audio e depois SILENCIO fecha pela parede (2 s de segmento,
     3 s calado) -- a rotacao ociosa comparava `time.monotonic()` com um
     `time.time()` e NUNCA disparava (o bug que deixou 2 525 s num ficheiro);
  A6 o buraco e a perda de fila tambem vao para o LOG (uma linha por buraco,
     uma linha por janela de perda, com o numero);
  A7 a pausa do tap MAIOR que um segmento: o buraco atravessa a rotacao e tem
     de ficar no segmento cujo `[wall_t0, wall_t1]` o CONTEM -- o seguinte, cujo
     intervalo comeca onde o audio anterior acabou --, e nao num ficheiro cujo
     `wall_s` ele excede. As tres identidades publicadas tem de fechar em cada
     linha do indice: `wall_t1-wall_t0 == wall_s`, `wall_s == stream_s+gap_s`
     e `wall_s-(t1-t0) == gap_s` (esta' ultima com a folga de UM bloco do tap,
     que e' o audio do ultimo bloco, medido depois da chegada dele).

`--neg-arm` muta uma COPIA de `worker/audio_ring.py`, um sitio por classe de
emenda, e corre o portao INTEIRO contra cada copia (subprocesso, o mesmo
caminho de entrada que o dono usa): o mutante tem de sair rc=1 com linha FAIL.
Um portao que so' passa com o codigo de hoje nao prova nada; o mutante e' a
metade que falta. A convencao da casa (`_main/_battery-plan.py:neg_arm`) vale
aqui: `--neg-arm` sai 1 quando APANHA tudo, 0 quando um mutante sobrevive.

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
import subprocess
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
#: A pausa de A7: maior que o segmento inteiro, para o escritor ocioso fechar o
#: ficheiro aberto ANTES de o tap voltar -- e' o que faz o buraco atravessar a
#: rotacao em vez de ficar dentro de um ficheiro.
GAP_ROTATE_S = 2.6
#: A folga aceitavel em `wall_s-(t1-t0)-gap_s`: UM bloco do tap. O audio do
#: ultimo bloco chega ao ficheiro mas e' medido depois da chegada dele, logo o
#: intervalo de parede fica um bloco curto; o `sleep` do teste acrescenta o
#: jitter de escalonamento (~ms por bloco).
TOL_BLOCK_S = 0.35


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
        # A ROTACAO E' PEDIDA, NAO CONTADA EM BLOCOS. Medido 2026-11-23: 20 blocos
        # de 0,1 s fecham 2,0 s exactos, mas a fila de 0,5 s RECUSA alguns sob
        # contenda e o segmento fica abaixo do limiar -- a corrida devolvia
        # `rows=0` e A2/A4 caiam sobre um escritor correto (2 corridas seguidas
        # deram 7/7). Empurrar ate' o indice responder mede o mesmo invariante e
        # nao depende de nenhum bloco ser aceito: o tecto e' 4 s de parede.
        for _ in range(40):
            if mod.read_index(tmp):
                break
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


def probe_rotation_gap(mod, np, tmp):
    """A7: pausa do tap MAIOR que o segmento -- o buraco atravessa a rotacao.

    O escritor ocioso fecha o segmento 1 pela parede com o tap calado; o bloco
    seguinte abre o 2. O buraco medido entre os dois `push` tem de aparecer no
    `gaps.jsonl` carimbado no segmento cujo intervalo de parede o CONTEM.
    """
    logs = []
    ring = mod.AudioRing(tmp, hours=1.0, kbps=24, segment_s=SEGMENT_S,
                         cap_mb=20.0, gap_min_s=GAP_MIN_S, log=logs.append)
    out = {'logs': logs}
    if not ring.enabled:
        out['error'] = 'ring did not start (no ffmpeg?)'
        return out
    blk = _block(np)
    try:
        for _ in range(10):                     # 1,0 s: nasce o segmento 1
            ring.push(blk)
            time.sleep(0.1)
        # SEM NENHUM BLOCO por mais que o segmento: o escritor ocioso fecha o 1.
        out['closed_by_wall'] = _wait(lambda: bool(mod.read_index(tmp)), 8.0)
        time.sleep(GAP_ROTATE_S)
        for _ in range(12):                     # + 1,2 s: nasce o segmento 2
            ring.push(blk)
            time.sleep(0.1)
    finally:
        ring.close()
    out['rows'] = mod.read_index(tmp)
    out['gaps'] = mod.read_gaps(tmp)
    return out


def judge_rotation(rows, marks, cov):
    """As identidades e a atribuicao de A7. Devolve (ok, detalhe).

    O intervalo de cada segmento vem de `cov._span`: os campos gravados quando
    existem (`wall_t0`/`wall_t1`) e, no codigo de hoje, o NOME do ficheiro mais
    o `wall_s` -- que e' exactamente o intervalo que o defeito publicava (do
    primeiro bloco ao ultimo, sem o buraco que atravessou a rotacao). O arm
    julga COMPORTAMENTO: o mutante tem de cair pela particao do tempo, pela
    identidade ou pela contencao, nao por o campo nao existir.
    """
    problems = []
    if len(rows) < 2:
        return False, 'rows=%d (a rotacao por parede nao fechou o segmento 1)' % len(rows)

    def span(r):
        t0, t1, src = cov._span(r)
        return t0, t1, (1.5 if src == 'name' else 0.005), src

    # 1. A PARTICao DO TEMPO: o fim de um segmento e' o inicio do seguinte. Sem
    #    isto a pausa que atravessa a rotacao cai NUM VAZIO entre os dois.
    for a, b in zip(rows, rows[1:]):
        _a0, a1, _asl, _src = span(a)
        b0, _b1, _bsl, _src2 = span(b)
        if a1 is None or b0 is None:
            problems.append('%s/%s: sem intervalo de parede' %
                            (os.path.basename(str(a.get('file'))),
                             os.path.basename(str(b.get('file')))))
            continue
        lost = b0 - a1
        if lost > 0.002:
            problems.append('tempo de chegada SEM DONO entre %s e %s: %.2f s'
                            % (os.path.basename(str(a.get('file'))),
                               os.path.basename(str(b.get('file'))), lost))
        elif lost < -0.01:
            problems.append('intervalos de dois segmentos SOBREPOSTOS: %.2f s' % (-lost))
    # 2. A IDENTIDADE do segmento: `wall_s == stream_s + gap_s` (exacta) e
    #    `wall_s - (t1-t0) == gap_s` (folga de um bloco do tap).
    for r in rows:
        name = os.path.basename(str(r.get('file')))
        if r.get('wall_s') is None:
            problems.append('%s: sem wall_s' % name)
            continue
        ws = float(r['wall_s'])
        gap = float(r.get('gap_s') or 0.0)
        if r.get('stream_s') is None:
            problems.append('%s: sem stream_s (a identidade nao se verifica)' % name)
        elif abs(ws - float(r['stream_s']) - gap) > 0.002:
            problems.append('%s: wall_s=%.3f != stream_s+gap_s=%.3f' 
                            % (name, ws, float(r['stream_s']) + gap))
        residual = ws - (float(r['t1']) - float(r['t0'])) - gap
        if abs(residual) > TOL_BLOCK_S:
            problems.append('%s: wall_s-(t1-t0)-gap_s=%.2f (folga %.2f)'
                            % (name, residual, TOL_BLOCK_S))
        if gap > ws + 0.002:
            problems.append('%s: gap_s=%.2f > wall_s=%.2f' % (name, gap, ws))
        if r.get('wall_t0') is not None and r.get('wall_t1') is not None:
            if abs((float(r['wall_t1']) - float(r['wall_t0'])) - ws) > 0.002:
                problems.append('%s: wall_t1-wall_t0 != wall_s' % name)
    # 3. CADA MARCADOR NOMEIA UM SEGMENTO QUE O CONTEM, e o indice conta o mesmo.
    byfile = {r.get('file'): r for r in rows}
    charged = {}
    for g in marks:
        f = g.get('file')
        if not f:
            continue
        r = byfile.get(f)
        s0, s1, slack, _ = span(r) if r else (None, None, 0.0, None)
        if s0 is None:
            problems.append('marcador para ficheiro sem intervalo: %s'
                            % os.path.basename(str(f)))
            continue
        if not (s0 - slack <= float(g['t0']) and float(g['t1']) <= s1 + slack):
            problems.append('marcador [%.1f,%.1f] FORA do intervalo de %s (%.1f..%.1f)'
                            % (float(g['t0']), float(g['t1']), os.path.basename(str(f)), s0, s1))
        charged[f] = charged.get(f, 0.0) + float(g.get('gap_s') or 0.0)
    for r in rows:
        idx = float(r.get('gap_s') or 0.0)
        led = charged.get(r.get('file'), 0.0)
        if abs(idx - led) > 0.002:
            problems.append('%s: gap_s=%.3f mas o ledger soma %.3f'
                            % (os.path.basename(str(r.get('file'))), idx, led))
    # 4. O BURACO DA ROTACAO existe e tem dono.
    big = [g for g in marks if float(g.get('gap_s') or 0.0) >= GAP_ROTATE_S - 0.8]
    if not big:
        problems.append('o buraco da rotacao (>=%.1f s) nao esta no ledger'
                        % (GAP_ROTATE_S - 0.8))
    for g in big:
        if not g.get('file'):
            problems.append('buraco de %.2f s sem segmento que o contenha'
                            % float(g['gap_s']))
    worst = max((abs(float(r['wall_s']) - (float(r['t1']) - float(r['t0']))
                    - float(r.get('gap_s') or 0.0))
                 for r in rows if r.get('wall_s') is not None), default=0.0)
    detail = ('rows=%d marks=%d between=%d rotation_gap_s=%s worst_residual=%.3f%s'
              % (len(rows), len(marks), sum(1 for g in marks if not g.get('file')),
                 ','.join('%.2f' % float(g['gap_s']) for g in big) or '-', worst,
                 '' if not problems else ' :: ' + ' | '.join(problems[:3])))
    return not problems, detail


def judge(mod, np):
    """Os sete arms. Devolve [(nome, ok, detalhe)]."""
    arms = []
    tmp = tempfile.mkdtemp(prefix='ring-loss-')
    tmp2 = tempfile.mkdtemp(prefix='ring-idle-')
    tmp3 = tempfile.mkdtemp(prefix='ring-rotate-')
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
                     'covered_span=%s tap_gap_s=%.2f markers=%d wall_src=%s gap_src=%s'
                     % (m['covered_span'], m['tap_gap_s'], m['gap_markers'],
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
        rot = probe_rotation_gap(mod, np, tmp3)
        if rot.get('error'):
            arms.append(('A7-buraco-atravessa-rotacao', False, rot['error']))
        else:
            ok_a7, detail = judge_rotation(rot['rows'], rot['gaps'], cov)
            arms.append(('A7-buraco-atravessa-rotacao', ok_a7, detail))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(tmp2, ignore_errors=True)
        shutil.rmtree(tmp3, ignore_errors=True)
    return arms


#: As cinco mutacoes, uma por classe de emenda. Cada uma e' uma string EXACTA do
#: fonte de hoje; se ela deixar de existir o portao diz "ANCORA NAO ENCONTRADA"
#: em vez de fingir que testou.
MUTATIONS = [
    ('M1-buraco-nao-detectado',
     '                if gap >= self._gap_min_s:',
     '                if False:  # M1'),
    ('M2-segmento-sem-perda',
     "               'wall_s': wall_s,\n"
     "               'stream_s': stream_s,\n"
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
    # O DEFEITO DE 2026-11-17, restaurado: o intervalo de parede do segmento
    # volta a comecar no PRIMEIRO bloco dele em vez de onde o audio anterior
    # acabou, logo o buraco que atravessa a rotacao deixa de caber em segmento
    # nenhum -- e vai parar ao ficheiro que ABRE quando ele acaba.
    ('M5-span-comeca-no-primeiro-bloco',
     '        self._seg_span_start = self._last_closed_wall',
     '        self._seg_span_start = None  # M5'),
]


def neg_arm():
    """Corre o portao INTEIRO contra cada mutante, num subprocesso.

    O caminho de entrada e' o do dono (`--ring <copia>`), nao um `judge()` em
    processo: um mutante que mata o import ou o probe tem de aparecer como
    vermelho, e nao como excepcao apanhada por engano. Devolve 1 quando apanha
    todos (convencao da casa: `--neg-arm` sai 1 ao apanhar).
    """
    src = io.open(RING, encoding='utf-8', newline='').read()
    caught = 0
    tmp = tempfile.mkdtemp(prefix='ring-mut-')
    try:
        for name, old, new in MUTATIONS:
            if old not in src:
                print('%s ANCORA NAO ENCONTRADA -- mutacao impossivel' % name)
                continue
            p = os.path.join(tmp, 'audio_ring_mut.py')
            io.open(p, 'w', encoding='utf-8', newline='').write(src.replace(old, new, 1))
            proc = subprocess.run([sys.executable, os.path.abspath(__file__),
                                   '--ring', p],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out = proc.stdout.decode('utf-8', 'replace')
            fails = [ln for ln in out.splitlines() if ln.startswith('FAIL ')]
            if proc.returncode == 1 and fails:
                caught += 1
                print('%s CAUGHT gate_rc=1 by %s'
                      % (name, fails[0][5:].split(' ')[0]))
            elif proc.returncode == 0:
                print('%s NOT-CAUGHT gate_rc=0 -- o mutante passou' % name)
            else:
                print('%s NOT-CAUGHT gate_rc=%d sem linha FAIL (traceback=%s)'
                      % (name, proc.returncode, 'Traceback' in out))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = caught == len(MUTATIONS)
    print('NEG-ARM: %s -- %d/%d'
          % ('PASS' if ok else 'FAIL', caught, len(MUTATIONS)))
    return 1 if ok else 0


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
