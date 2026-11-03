"""O ATRASO DO SOTTO CONTRA O PLAYER, medido de 4 em 4 decimos de segundo.

Este e' o instrumento da aceitacao: *"provar que a legenda tem tudo 1:1"*, com o
video A TOCAR. Ele nao julga texto por impressao -- mede tres coisas:

  1. **ATRASO**: para cada MUDANCA nas linhas que o player mostra, quanto tempo o
     Sotto leva a desenhar aquelas linhas (`t_desenho - t_apareceu`).
  2. **ADIANTAMENTO**: quantos quadros do Sotto mostram texto que o player ainda
     NAO mostra (o *"fora de sync"* dos dois sentidos).
  3. **ATRASO-VELHO**: quantos quadros do Sotto mostram texto que o player JA'
     deixou para tras.

O player e' lido por CDP (`_yt-cdp-probe.probe`), sem focar a aba e so' em pagina
do YouTube. O Sotto e' lido do proprio log (`YT_FRAME` / `EXTERNAL_CAPTION_DRAWN`),
que e' o que o `_tick` DECIDE desenhar. Nada de captura de ecra.

USO:
    python _main/_yt-live-latency.py --seconds 120
    python _main/_yt-live-latency.py --seconds 120 --json out.json
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

LOG = os.path.join(HERE, 'webview-run.log')
SAMPLES = os.path.join(HERE, '_yt-latency.jsonl')

# A DATA FAZ PARTE DO CARIMBO (corrigido 2026-11-03). O padrao antigo capturava
# so' a HORA e recombinava com o dia de HOJE: as linhas de 2026-11-02 22:10
# viravam "hoje as 22:10", ou seja 22 h no FUTURO, e entraram 2081 quadros
# velhos na janela de 7 s que o instrumento devia julgar.
STAMP = re.compile(r'^(?:(\d{4}-\d{2}-\d{2}) )?(\d{2}:\d{2}:\d{2}\.\d{3}) '
                   r'.*?(?:YT_FRAME src=\S+ rows=\d+|EXTERNAL_CAPTION_DRAWN '
                   r'rows=\d+) lines=(\[.*\])')


def norm(text):
    text = re.sub(r'\s+', ' ', str(text or '')).strip().lower()
    return text.strip('.,!?;:')


def norm_rows(rows):
    out = []
    for row in rows or ():
        text = norm(row)
        if text and (not out or out[-1] != text):
            out.append(text)
    return out


def stamp_to_epoch(stamp, day=None):
    """'YYYY-MM-DD HH:MM:SS.mmm' ou 'HH:MM:SS.mmm' (dia de hoje) -> epoch local."""
    date_part, _, time_part = stamp.partition(' ')
    if time_part:
        moment_date = datetime.date.fromisoformat(date_part)
        stamp = time_part
    else:
        moment_date = day or datetime.date.today()
    hour, minute, rest = stamp.split(':')
    second, _, millis = rest.partition('.')
    return datetime.datetime.combine(
        moment_date, datetime.time(int(hour), int(minute), int(second),
                                   int(millis.ljust(3, '0')[:3]) * 1000)
    ).timestamp()

def read_frames(since_epoch):
    frames = []
    if not os.path.exists(LOG):
        return frames
    with io.open(LOG, encoding='utf-8', errors='replace') as handle:
        for line in handle:
            match = STAMP.search(line)
            if not match:
                continue
            when = stamp_to_epoch((match.group(1) + ' ' if match.group(1) else '')
                                  + match.group(2))
            if when < since_epoch - 2:
                continue
            try:
                lines = json.loads(match.group(3).replace("'", '"'))
            except Exception:
                continue
            frames.append((when, [str(x) for x in lines]))
    return frames


def sample(seconds, period, play=True):
    """Amostra o player por CDP, mantendo o SILENCIO em cada avaliacao.

    Tres invariantes dentro do laco, cada um nascido de um defeito medido:
      * `muted=true` + `volume=0` re-afirmados -- o dono ouviu o video depois
        de um mute isolado;
      * `Page.setWebLifecycleState(active)` + `Emulation.setFocusEmulationEnabled`
        -- com a aba em segundo plano o player deixa de pintar a legenda e o
        leitor mede um ecra congelado;
      * o filtro de geometria do `SILENT_PROBE` -- o DOM guarda 3 segmentos
        enquanto 2 estao dentro da caixa.
    """
    import importlib
    probe_mod = importlib.import_module('_yt-cdp-probe')
    importlib.reload(probe_mod)
    video_id = probe_mod.sottos_video_id()
    ws, error = probe_mod.open_socket(video_id=video_id)
    if ws is None:
        print('ABORT: %s' % error)
        return time.time(), []
    js = probe_mod.SILENT_PROBE if play else probe_mod.PROBE
    # NENHUM 'EMULATION' NO INSTRUMENTO (2026-11-03, MEDIDO). Estes dois pedidos
    # existiam para 'acordar' a aba escondida. Medidos lado a lado, no mesmo
    # minuto, com 20 leituras cada:
    #
    #   nada               mediana 2-5 ms    p90 64-88 ms
    #   focus emulation    mediana   108 ms   p90 5009 ms    (PIOR)
    #   lifecycle=active   mediana   3-4 ms   p90 61-74 ms
    #   os dois            mediana   246 ms   p90 6889 ms    (PESSIMO)
    #
    # O `setFocusEmulationEnabled` faz a pagina acreditar que esta' focada e
    # custa ate' 9 s por leitura: o instrumento estava a criar a lentidao que
    # depois media.
    extra = ()
    started = time.time()
    samples = []
    counter = [0]
    with io.open(SAMPLES, 'w', encoding='utf-8') as sink:
        try:
            while time.time() - started < seconds:
                try:
                    reading = probe_mod.review(ws, counter, js, extra)
                except Exception as exc:  # noqa: BLE001
                    # A aba escondida pode adiar uma leitura por segundos; uma
                    # amostra perdida nao e' o fim da medicao.
                    reading = {'error': type(exc).__name__, 'rows': []}
                entry = {'w': round(time.time(), 3),
                         't': reading.get('t'),
                         'paused': reading.get('paused'),
                         'muted': reading.get('muted'),
                         'vol': reading.get('vol'),
                         'rows': reading.get('rows') or [],
                         'error': reading.get('error')}
                sink.write(json.dumps(entry, ensure_ascii=False) + '\n')
                sink.flush()
                samples.append(entry)
                time.sleep(period)
        finally:
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass
    return started, samples

def analyse(started, samples, video_id=None):
    frames = read_frames(started)
    played = [s for s in samples if not s['paused'] and s['rows']]
    out = {'samples': len(samples), 'playing_samples': len(played),
           'frames': len(frames)}

    # Mudancas nas linhas do player, com o instante em que foram VISTAS.
    changes = []
    last = None
    for item in samples:
        rows = norm_rows(item['rows'])
        if rows != last:
            changes.append((item['w'], rows))
            last = rows
    out['player_changes'] = len(changes)

    latencies = []
    missed = []
    for when, rows in changes:
        if not rows:
            continue
        hit = None
        for f_when, f_rows in frames:
            if f_when < when - 0.5:
                continue
            if f_when > when + 3.0:
                break
            if norm_rows(f_rows) == rows:
                hit = f_when - when
                break
        if hit is None:
            missed.append([round(when - started, 2), rows])
        else:
            latencies.append(max(0.0, hit * 1000.0))
    latencies.sort()
    out['latency_n'] = len(latencies)
    out['latency_missed'] = len(missed)
    if latencies:
        out['latency_ms_median'] = round(latencies[len(latencies) // 2], 1)
        out['latency_ms_p90'] = round(latencies[int(len(latencies) * 0.9)], 1)
        out['latency_ms_max'] = round(latencies[-1], 1)
    out['missed_examples'] = missed[:5]

    # Cada quadro do Sotto contra o estado do player no instante dele.
    ahead, stale, same, unknown = 0, 0, 0, 0
    examples = {'ahead': [], 'stale': []}
    for f_when, f_rows in frames:
        mine = norm_rows(f_rows)
        before = None
        after = None
        for item in samples:
            if item['w'] <= f_when:
                before = item
            elif after is None:
                after = item
                break
        if before is None:
            unknown += 1
            continue
        now_rows = norm_rows(before['rows'])
        mine_text = ' '.join(mine)
        now_text = ' '.join(now_rows)
        next_text = ' '.join(norm_rows(after['rows'])) if after else ''
        if not mine_text:
            unknown += 1
        elif mine == now_rows or mine_text in now_text:
            same += 1
        elif mine_text.startswith(now_text) or (next_text and next_text.startswith(mine_text)):
            ahead += 1
            if len(examples['ahead']) < 5:
                examples['ahead'].append([round(f_when - started, 2), mine, now_rows])
        else:
            stale += 1
            if len(examples['stale']) < 5:
                examples['stale'].append([round(f_when - started, 2), mine, now_rows])
    # A IDADE DO QUE O ECRA MOSTRA (2026-11-03). A metrica que um humano sente
    # nao e' "quantos quadros casaram" -- e' HÁ QUANTO TEMPO o texto no ecra
    # ja' nao e' o do player. Para cada amostra, achar o instante mais RECENTE
    # em que o player mostrou exactamente aquelas linhas: a diferenca e' a idade.
    ages = []
    agree = 0
    for item in samples:
        mine = norm_rows(item['rows'])
        when = item['w']
        shown = None
        for f_when, f_rows in frames:
            if f_when <= when:
                shown = (f_when, norm_rows(f_rows))
            else:
                break
        if shown is None:
            continue
        if shown[1] == mine:
            agree += 1
            ages.append(0.0)
            continue
        age = None
        for prev in reversed(samples):
            if prev['w'] > when:
                continue
            if norm_rows(prev['rows']) == shown[1]:
                age = (when - prev['w']) * 1000.0
                break
        if age is not None:
            ages.append(age)
    ages.sort()
    out['agree'] = agree
    out['agree_pct'] = round(100.0 * agree / max(1, len(samples)), 1)
    out['display_age_n'] = len(ages)
    if ages:
        out['display_age_ms_median'] = round(ages[len(ages) // 2], 1)
        out['display_age_ms_p90'] = round(ages[int(len(ages) * 0.9)], 1)
        out['display_age_ms_max'] = round(ages[-1], 1)
    # OSCILACAO: A -> B -> A dentro de 500 ms. E' o *"ficando sumindo e
    # aparecendo"* do dono, contado em vez de descrito.
    osc = 0
    dedup = []
    for f_when, f_rows in frames:
        key = norm_rows(f_rows)
        if not dedup or dedup[-1][1] != key:
            dedup.append((f_when, key))
    for i in range(len(dedup) - 2):
        a, b, c = dedup[i], dedup[i + 1], dedup[i + 2]
        if a[1] == c[1] and a[1] != b[1] and (c[0] - a[0]) <= 0.5:
            osc += 1
    out['oscillations'] = osc
    out.update({'frames_same': same, 'frames_ahead': ahead,
                'frames_stale': stale, 'frames_unknown': unknown,
                'examples': examples})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--seconds', type=float, default=120.0)
    ap.add_argument('--period', type=float, default=0.4)
    ap.add_argument('--json', default=None)
    ap.add_argument('--no-play', action='store_true')
    args = ap.parse_args(argv)
    started, samples = sample(args.seconds, args.period,
                              play=not args.no_play)
    report = analyse(started, samples)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.json:
        io.open(args.json, 'w', encoding='utf-8').write(
            json.dumps(report, ensure_ascii=False, indent=2))
    ok = (report['latency_missed'] == 0 and report['frames_ahead'] == 0
          and report['frames_stale'] == 0 and report['latency_n'] >= 5)
    print('VERDICT: %s' % ('1:1' if ok else 'NOT-1:1'))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
