"""O veredicto 1:1 da legenda do YouTube, medido no ecra e no player.

O QUE MEDE (e por que cada numero existe)

O dono, verbatim: *"legenda do youtube aparece na hora, com a legenda do sotto
ativa"* e *"tu vai imitar no sotto a legenda do youtube 1:1"*. Um booleano nao
mede isso. Este instrumento da' quatro numeros, todos com a mesma janela:

  * `cobertura` -- de cada INSTANTE em que o player troca de linha, em quantos o
    Sotto ja' mostrava a mesma linha ate' 500 ms depois. Um ceu de mudancas sem
    eco e' a legenda a chegar tarde.
  * `igualdade` -- de cada amostra, em quantas as duas listas de linhas sao
    IDENTICAS (texto, ordem e numero de linhas). E' o 1:1 literal.
  * `idade_max_ms` -- a maior distancia entre o que o Sotto mostra e a linha do
    player MAIS RECENTE que coincide com ela. E' o atraso do que esta' no ecra.
  * `trocas` -- quantas vezes as linhas do Sotto mudaram para algo que o player
    NUNCA mostrou (texto inventado, ou ordem trocada). Tem de ser zero.

COMO LE' (e o que NAO faz)

  * O player: CDP da aba do YouTube, so' as LINHAS VISIVEIS (o que esta' dentro
    do `overflow: hidden` do `.caption-window`) -- as que rolaram para fora
    continuam no DOM e nao estao no ecra.
  * O Sotto: as linhas que ele DESENHOU, lidas do log dele (`EXTERNAL_CAPTION_
    DRAWN` / `YT_FRAME`) -- o que ele diz ter posto no ecra, nao o que devia ter
    posto.
  * Nao ativa a aba, nao foca janela, nao envia teclas. Nao toca no audio.
  * Amostras com o video em PAUSA ou sem legenda nenhuma ficam de fora (e sao
    contadas a' parte): comparar um ecra congelado com um player parado mede o
    silencio, nao a legenda.

USO

    python _main/yt-1to1-verify.py --seconds 120
    python _main/yt-1to1-verify.py --seconds 60 --json _main/_yt-1to1.json
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'app', 'webview'))

LOG = os.path.join(HERE, 'webview-run.log')

#: Quanto tempo depois da troca no player uma linha igual ainda conta como
#: "chegou". Abaixo disso o olho nao ve' diferenca pratica; acima, ve'.
COVER_S = 0.5

_DRAWN = re.compile(r'(EXTERNAL_CAPTION_DRAWN|YT_FRAME src=\S+) rows=\d+ '
                    r'lines=(\[.*\])')


def last_drawn_rows(path=LOG, tail_bytes=262144):
    """As ultimas linhas DESENHADAS pelo Sotto: [(monotonic, rows)] ate' 2.

    Le' a cauda do log e fica com as duas ultimas, porque a comparacao precisa de
    saber o que estava no ecra ANTES e DEPOIS de uma troca do player.
    """
    out = []
    try:
        with io.open(path, encoding='utf-8', errors='replace') as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - tail_bytes))
            for line in fh:
                m = _DRAWN.search(line)
                if not m:
                    continue
                try:
                    rows = json.loads(m.group(2))
                except ValueError:
                    continue
                if not isinstance(rows, list):
                    continue
                out.append((time.monotonic(), [str(r).strip() for r in rows]))
    except OSError:
        return []
    return out[-2:]


def norm(rows):
    return [str(r).strip() for r in (rows or ()) if str(r).strip()]


def judge(samples):
    """Os quatro numeros, a partir das amostras. Puro: testavel sem Chrome."""
    counters = collections.Counter()
    ages = []
    player_changes = []          # (t, rows)
    frames = []                  # (t, rows)
    prev = None
    for s in samples:
        rows = norm(s.get('player') or ())
        if s.get('paused') or not rows:
            counters['ignoradas'] += 1
            continue
        counters['usadas'] += 1
        if rows != prev:
            player_changes.append((s['t'], rows))
            prev = rows
        if s.get('ours') is not None:
            frames.append((s['t'], norm(s['ours'])))
    # o que o player mostrou, em ordem, para detectar texto inventado
    seen = []
    for _t, rows in player_changes:
        if rows not in seen:
            seen.append(rows)
    invented = 0
    last_rows = None
    for _t, rows in frames:
        if rows and rows != last_rows:
            if rows not in seen:
                invented += 1
            last_rows = rows
    # O ATRASO, NAO SO' A IGUALDADE (2026-11-03). `igualdade_pct` conta o
    # instante exacto; uma legenda 300 ms atrasada conta como errada e uma 4 s
    # atrasada conta igual. Para o dono ("a legenda aparece na hora") o numero
    # que responde e' a IDADE do texto no ecra: para cada quadro nosso, ha quanto
    # tempo o player ja' mostrava AQUELE texto.
    lags = []
    trail = list(player_changes)
    for f_t, f_rows in frames:
        if not f_rows:
            continue
        first_seen = None
        for when, rows in trail:
            if rows == f_rows:
                first_seen = when
                break
        if first_seen is None:
            continue
        lags.append(max(0.0, f_t - first_seen))
    same = 0
    for s in samples:
        if s.get('paused'):
            continue
        rows = norm(s.get('player') or ())
        ours = norm(s.get('ours') or ())
        if rows and ours and rows == ours:
            same += 1
    covered = 0
    for when, rows in player_changes:
        hit = any(0.0 <= f_t - when <= COVER_S and f_rows == rows
                  for f_t, f_rows in frames)
        if hit:
            covered += 1
    for f_t, f_rows in frames:
        best = None
        for when, rows in player_changes:
            if rows == f_rows and when <= f_t:
                best = f_t - when
        if best is not None:
            ages.append(best * 1000.0)
    used = counters['usadas'] or 1
    return {
        'amostras': counters['usadas'],
        'ignoradas': counters['ignoradas'],
        'trocas_player': len(player_changes),
        'quadros': len(frames),
        'igualdade_pct': round(100.0 * same / used, 1),
        'cobertura_pct': round(100.0 * covered / len(player_changes), 1)
        if player_changes else None,
        'idade_max_ms': round(max(ages), 0) if ages else None,
        'idade_mediana_ms': round(sorted(ages)[len(ages) // 2], 0) if ages else None,
        'inventados': invented,
        'atraso_mediana_ms': round(1000.0 * sorted(lags)[len(lags) // 2], 0) if lags else None,
        'atraso_p90_ms': round(1000.0 * sorted(lags)[min(len(lags) - 1,
                                                int(0.9 * len(lags)))], 0) if lags else None,
    }


def run(seconds, period):
    import importlib
    probe = importlib.import_module('_yt-cdp-probe')
    ws, err = probe.open_socket(video_id=None)
    if ws is None:
        return {'erro': err}
    samples = []
    started = time.monotonic()
    # O QUE ESTA' NO ECRA' PERSISTE (2026-11-03). `last_drawn_rows` le' os
    # ultimos 256 KB do log; quando o log engorda depressa (um despejo de
    # `UI_HUNG_FRAME`, por exemplo) a cauda pode nao ter NENHUMA linha desenhada
    # e o instrumento passava a dizer `quadros=0` enquanto a legenda estava no
    # ecra -- mediu 0 quadros numa janela em que o dono viu a linha congelada.
    # A ultima linha desenhada continua a ser o que esta' na janela ate' outra
    # chegar: e' isso que este guarda.
    last_ours = None
    try:
        while time.monotonic() - started < seconds:
            try:
                reading = probe.review(ws, [0], probe.PROBE, ())
            except Exception as exc:            # noqa: BLE001
                reading = {'error': type(exc).__name__}
            drawn = last_drawn_rows()
            if drawn:
                last_ours = drawn[-1][1]
            samples.append({
                't': time.monotonic() - started,
                'paused': reading.get('paused'),
                'player': reading.get('rows') or [],
                'ours': last_ours,
                'erro': reading.get('error'),
            })
            time.sleep(period)
    finally:
        try:
            ws.close()
        except Exception:                       # noqa: BLE001
            pass
    if os.environ.get('_YT1TO1_DUMP'):
        with io.open(os.environ['_YT1TO1_DUMP'], 'w', encoding='utf-8') as fh:
            for s in samples:
                fh.write(json.dumps(s) + '\n')
    verdict = judge(samples)
    verdict['video'] = (reading.get('url') or '')[-11:] if samples else ''
    return verdict


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--seconds', type=float, default=120.0)
    ap.add_argument('--period', type=float, default=0.2)
    ap.add_argument('--json', default=None)
    ap.add_argument('--dump', default=None,
                    help='grava as amostras cruas (NDJSON), uma linha por leitura')
    args = ap.parse_args(argv)
    if args.dump:
        os.environ['_YT1TO1_DUMP'] = args.dump
    out = run(args.seconds, args.period)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    if args.json:
        io.open(args.json, 'w', encoding='utf-8').write(
            json.dumps(out, ensure_ascii=False, indent=1))
    ok = (out.get('igualdade_pct', 0) >= 80.0
          and out.get('inventados', 1) == 0
          and (out.get('idade_max_ms') or 0) <= 1500.0
           and (out.get('atraso_p90_ms') or 0) <= 1200.0)
    print('VERDICT:', '1:1' if ok else 'NOT-1:1')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
