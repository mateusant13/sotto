"""O show REAL do dono: cada `PANEL_SHOWN` da instancia viva carrega `paint_ack=true`?

O censo `panel-paint-first-census.py` mede PIXEIS, mas numa instancia PRIVADA -- e a lei
`SOTTO_NEVER_ON_OWNER_SCREEN` proibe uma lane de a pôr no ecra dele para o medir. Este oraculo
fecha o buraco do outro lado: le o log da instancia que ELE carrega e julga a unica coisa que a
cura promete ali -- que o show nao e' um MAP de janela fria. O shell ja' escreve as duas
testemunhas (`PAINT_WARM ... ack=...` no arranque e `PANEL_SHOWN ... paint_ack=... wait_ms=...`
a cada show); ate' 2026-11-01 ninguem as lia.

Regras (todas medidas, nao escolhidas):

  * a sessao viva comeca na ULTIMA linha `SHELL_STARTUP_STAGE` (ou `SHELL_START`) do log;
  * `PAINT_WARM ... ack=true` tem de existir nessa sessao -- sem o aquecimento, o primeiro show
    cai no caminho frio que o censo mediu em 186-325 ms de frame vazio;
  * todo `PANEL_SHOWN` depois dele tem de trazer `paint_ack=true` e `wait_ms <= 400` (o tecto
    e' o `PAINT_ACK_TIMEOUT_MS` do shell; medido 31 ms de espera na caixa do dono).

SEM SHOW NA SESSAO NAO E' VERDE: imprime `VERDICT: SKIPPED` com a hora do arranque, e o passo
skip-capable da bateria conta o como SKIPPED -- um passo saltado nunca e' um portao que passou.
Efervescencia: `--neg-arm` muta uma copia do log em tres pontos e exige os tres vermelhos.
"""
# NO-BUG: instrumento do show REAL: le o log da instancia viva do dono e exige `paint_ack=true` e `wait_ms<=400` em cada PANEL_SHOWN; diz SKIPPED quando ainda nao houve show
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webview-run.log')
ACK_MAX_MS = 400.0

_START = ('SHELL_STARTUP_STAGE', 'SHELL_START')
_WARM = 'PAINT_WARM'
_SHOWN = 'PANEL_SHOWN'


def _lines(text):
    return [ln for ln in text.splitlines() if ln.strip()]


def _stamp(line):
    m = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})', line)
    return m.group(1) if m else ''


def _get(line, key):
    m = re.search(r'\b%s=(\S+)' % (re.escape(key),), line)
    return m.group(1) if m else None


def judge(text):
    """-> (verdict, detail). `verdict` in GREEN | RED | SKIPPED. Puro: so' o texto."""
    lines = _lines(text)
    start_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if any(tag in lines[i] for tag in _START):
            start_idx = i
            break
    if start_idx is None:
        return 'SKIPPED', {'why': 'nenhum arranque de shell no log -- nao ha sessao viva a julgar',
                           'shows': 0}
    session = lines[start_idx:]
    warm = [ln for ln in session if _WARM in ln]
    warm_ok = [ln for ln in warm if (_get(ln, 'ack') or '') == 'true']
    shown = [ln for ln in session if _SHOWN in ln]
    detail = {'started': _stamp(session[0]), 'warm': len(warm),
              'warm_ack': len(warm_ok), 'shows': len(shown), 'fails': []}
    if not warm:
        detail['fails'].append('a sessao viva nao tem PAINT_WARM: o show cai no caminho frio')
    elif not warm_ok:
        detail['fails'].append('PAINT_WARM existe mas sem ack=true (%s)'
                               % (_get(warm[-1], 'ack'),))
    bad = []
    waits = []
    for ln in shown:
        ack = _get(ln, 'paint_ack')
        ms = _get(ln, 'wait_ms')
        try:
            msf = float(ms)
        except (TypeError, ValueError):
            msf = None
        if msf is not None:
            waits.append(msf)
        if ack != 'true':
            bad.append((ln, 'paint_ack=%s' % (ack,)))
        elif msf is None:
            bad.append((ln, 'sem wait_ms'))
        elif msf > ACK_MAX_MS:
            bad.append((ln, 'wait_ms=%.1f > %.0f' % (msf, ACK_MAX_MS)))
    detail['max_wait_ms'] = max(waits) if waits else None
    for ln, why in bad:
        detail['fails'].append('show %s: %s' % (_stamp(ln) or '?', why))
    if detail['fails']:
        return 'RED', detail
    if not shown:
        return 'SKIPPED', dict(detail, why='nenhum Alt+C nesta sessao ainda (%s) -- nada a julgar'
                               % (detail['started'] or 'sem hora',))
    return 'GREEN', detail


NEG_CASES = (
    # (rotulo, o que muda, o que se espera)
    ('show-sem-ack', lambda t: t.replace('paint_ack=true', 'paint_ack=false', 1), 'RED'),
    # A cauda sintetica e' a ULTIMA ocorrencia: mutar a primeira apanhava uma sessao velha
    # e o braco passava verde (medido).
    ('show-lento', lambda t: re.sub(r'wait_ms=[\d.]+(?=[^\d.]*$)', 'wait_ms=951.0', t), 'RED'),
    ('sessao-sem-aquecimento', lambda t: '\n'.join(
        ln for ln in t.splitlines() if _WARM not in ln), 'RED'),
)


def neg_arm(text):
    cases = list(NEG_CASES)
    bad = 0
    for label, mutate, expect in cases:
        got, detail = judge(mutate(text))
        ok = got == expect
        bad += 0 if ok else 1
        print('  %-28s -> %-8s %s  %s'
              % (label, got, 'RED-as-required' if ok else 'NOT-CAUGHT',
                 (detail.get('fails') or ['-'])[0][:90]))
    if not text.strip():
        print('NEG-ARM: a amostra esta vazia -- as mutacoes nao provam nada')
        return 1
    print('NEG-ARM cases=%d caught=%d' % (len(cases), len(cases) - bad))
    if bad:
        print('NEG-ARM FAIL')
        return 1
    print('NEG-ARM PASS')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--log', default=LOG)
    ap.add_argument('--neg-arm', action='store_true')
    args = ap.parse_args(argv)
    if not os.path.exists(args.log):
        print('PAINT-LIVE VERDICT: SKIPPED (sem log em %s)' % (args.log,))
        return 0
    text = open(args.log, encoding='utf-8', errors='replace').read()
    if args.neg_arm:
        # A amostra das mutacoes e' o log REAL; se ele nao tem um show ainda, fabrica-se um
        # a partir do arranque, porque um braco negativo sobre texto vazio e' um braco a rir.
        # SEMPRE uma cauda sintetica LIMPA: as mutacoes tem de morder alguma coisa, e o
        # texto vivo pode nao ter show nenhum (foi o caso medido hoje). O braco positivo
        # deste oraculo continua a ser o log REAL (`--log`), nunca esta cauda.
        sample = (text + '\n2099-01-01 00:00:00.000 sotto: PAINT_WARM reason=startup ack=true'
                         ' ack_wait_ms=31.0\n'
                         '2099-01-01 00:00:01.000 sotto: PANEL_SHOWN reason=hotkey-tap'
                         ' visible=true paint_ack=true wait_ms=32.0\n')
        return neg_arm(sample)
    verdict, detail = judge(text)
    print('PAINT-LIVE arranque=%s warm=%d ack=%d shows=%d max_wait_ms=%s'
          % (detail.get('started') or '-', detail.get('warm', 0),
             detail.get('warm_ack', 0), detail.get('shows', 0),
             detail.get('max_wait_ms')))
    for why in detail.get('fails') or []:
        print('  RED: %s' % (why,))
    if verdict == 'SKIPPED':
        print('PAINT-LIVE VERDICT: SKIPPED (%s)'
              % (detail.get('why') or 'nada a julgar',))
        return 0
    print('PAINT-LIVE VERDICT: %s' % (verdict,))
    return 0 if verdict == 'GREEN' else 1


if __name__ == '__main__':
    raise SystemExit(main())
