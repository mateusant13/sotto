#!/usr/bin/env python3
"""A MEMORIA TEM DE SER UMA SERIE, NAO UMA FOTO -- o detector de fuga de RSS.

PORQUE ISTO EXISTE. O worker publica `rss_mb` em cada `WORKER_STATS`, mas a shell
so' o guardava na CAUDA DA MORTE -- ou seja, o numero existia exactamente quando
ja' nao havia o que medir. Sem serie nao se prova nem se refuta "leak", e o dono
proibe as duas coisas: fuga E a afirmacao sem medida. Desde 2026-11-02 a shell
escreve `BRIDGE_RSS rss_mb=... blocks=...` uma vez por minuto.

O JULGAMENTO, e o que ele RECUSA:
  * uma serie curta (`n < MIN_SAMPLES`) => `UNKNOWN`. Nunca `ok`: um skip nao e'
    um portao que passou.
  * fuga: inclinacao >= `SLOPE_FLAG_MB_PER_MIN` **e** crescimento total
    >= `GROWTH_FLAG_MB` -- as duas, para que um arranque que aquece 30 MB e
    assenta nao seja chamado de fuga.
  * dente de serra (sobe e desce, inclinacao ~0) NAO e' fuga: e' cache a encher
    e a esvaziar, e dizer o contrario seria ruido.

ARMS (series sinteticas com forma CONHECIDA, e o controlo ao lado de cada uma):
  1  fuga linear (+30 MB/min, 30 amostras) -> FLAG
  2  aquecimento e planalto (sobe 40 MB e fica) -> sem flag
  3  dente de serra (oscila 200 MB, inclinacao 0) -> sem flag
  4  serie curta (5 amostras de uma fuga) -> UNKNOWN, nunca verde

BRACO NEGATIVO (`--neg-arm`): uma copia deste ficheiro com o limiar em 1e9 -- a
arm 1 TEM de ficar RED nela, senao o detector so' prova a sua aritmetica.
"""
import argparse
import re
import subprocess
import sys
import tempfile

#: Quanto de RSS por minuto ja' e' fuga. Um run longo e' um PLANALTO: o modelo
#: carrega uma vez (1-2,5 GB) e o RSS anda com o buffer de audio (decenas de MB),
#: nao 2 MB por minuto para sempre.
SLOPE_FLAG_MB_PER_MIN = 2.0
GROWTH_FLAG_MB = 30.0
MIN_SAMPLES = 10


def _slope(points):
    """Inclinacao por minuto por minimos quadrados: `points` e' [(min, mb)]."""
    n = len(points)
    if n < 2:
        return 0.0
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    num = sum((p[0] - mx) * (p[1] - my) for p in points)
    den = sum((p[0] - mx) ** 2 for p in points)
    if den == 0:
        return 0.0
    return num / den


def judge(values, slope_flag=SLOPE_FLAG_MB_PER_MIN, growth_flag=GROWTH_FLAG_MB,
          min_samples=MIN_SAMPLES):
    """-> `(verdict, slope, growth, note)`, com `verdict` em FLAG/ok/UNKNOWN."""
    n = len(values)
    if n < min_samples:
        return ('UNKNOWN', 0.0, 0.0,
                'so\' %d amostra(s): o minimo e\' %d -- curto demais para julgar'
                % (n, min_samples))
    # O AQUECIMENTO NAO E' FUGA. A inclinacao e' medida na CAUDA (75 % final da
    # serie) e o crescimento a partir do maximo do PRIMEIRO quarto -- assim uma
    # serie que sobe 40 MB e assenta da' inclinacao ~0 e crescimento ~0, que e' a
    # verdade, enquanto uma fuga linear continua a subir na cauda.
    head = max(1, n // 4)
    tail_from = max(head, n - max(head, (3 * n) // 4))
    points = [(float(i), float(v)) for i, v in enumerate(values)][tail_from:]
    slope = _slope(points)
    growth = values[-1] - max(values[:head])
    if slope >= slope_flag and growth >= growth_flag:
        return ('FLAG', slope, growth,
                'cresce %+.1f MB/min na cauda e %+.1f MB depois do aquecimento: e\' fuga'
                % (slope, growth))
    return ('ok', slope, growth,
            'inclinacao %+.1f MB/min na cauda, %+.1f MB depois do aquecimento'
            % (slope, growth))


def read_log(path):
    pat = re.compile(r'BRIDGE_RSS rss_mb=([\d.]+)')
    out = []
    with open(path, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            m = pat.search(line)
            if m:
                out.append(float(m.group(1)))
    return out


def arms():
    res = {}
    leak = [1200.0 + 30.0 * i for i in range(30)]
    v = judge(leak)
    res['1'] = v[0] == 'FLAG'
    print('ARM 1  fuga linear      -> %-7s slope=%+.1f growth=%+.1f  %s'
          % (v[0], v[1], v[2], 'PASS' if res['1'] else 'FAIL'))

    warm = [1000.0 + 40.0 * min(i, 4) for i in range(30)]
    v = judge(warm)
    res['2'] = v[0] == 'ok'
    print('ARM 2  aquece e assenta  -> %-7s slope=%+.1f growth=%+.1f  %s'
          % (v[0], v[1], v[2], 'PASS' if res['2'] else 'FAIL'))

    saw = [1500.0 + (200.0 if i % 2 else 0.0) for i in range(30)]
    v = judge(saw)
    res['3'] = v[0] == 'ok'
    print('ARM 3  dente de serra    -> %-7s slope=%+.1f growth=%+.1f  %s'
          % (v[0], v[1], v[2], 'PASS' if res['3'] else 'FAIL'))

    v = judge(leak[:5])
    res['4'] = v[0] == 'UNKNOWN'
    print('ARM 4  serie curta       -> %-7s  %s' % (v[0], 'PASS' if res['4'] else 'FAIL'))
    return res


def neg_arm():
    src = open(__file__, encoding='utf-8', newline='').read()
    needle = 'SLOPE_FLAG_MB_PER_MIN = 2.0'
    # A LINHA da constante, e nao a string dentro deste proprio `neg_arm`.
    at = src.find(chr(10) + needle + chr(10))
    if at < 0:
        print('NEG-ARM FAIL: limiar nao encontrado')
        return 1
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False,
                                     encoding='utf-8', newline='\n') as fh:
        fh.write(src[:at + 1] + 'SLOPE_FLAG_MB_PER_MIN = 1e9' + src[at + 1 + len(needle):])
        path = fh.name
    try:
        proc = subprocess.run([sys.executable, path], capture_output=True, text=True)
    finally:
        import os
        try:
            os.remove(path)
        except OSError:
            pass
    out = proc.stdout or ''
    red = proc.returncode != 0 and any(
        ln.startswith('ARM 1 ') and ln.rstrip().endswith('FAIL') for ln in out.splitlines())
    print('NEG-ARM limiar=1e9 rc=%d arm1_red=%s  %s'
          % (proc.returncode, red, 'PASS' if red else 'FAIL'))
    print('NEG-ARM PASS' if red else 'NEG-ARM FAIL')
    return 0 if red else 1


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--log', default=None, help='le um log real e publica a serie')
    a = ap.parse_args()
    if a.neg_arm:
        raise SystemExit(neg_arm())
    ok = all(arms().values())
    if a.log:
        vals = read_log(a.log)
        v, s, g, note = judge(vals)
        print('SERIE REAL %s: n=%d verdict=%s %s' % (a.log, len(vals), v, note))
    print('VERDICT:', 'GREEN' if ok else 'RED')
    raise SystemExit(0 if ok else 1)
