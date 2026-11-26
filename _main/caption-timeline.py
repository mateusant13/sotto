"""A LINHA DO TEMPO DA LEGENDA -- o instrumento que responde "como a legenda se
comporta", a partir do log que a app escreve.

Ordem do dono, 2026-11-12, verbatim:
    *"tu tem que ter uma forma de saber exatamente como a legenda da display e
    se comporta"*

O QUE ELE MEDE, e cada um nasceu de um defeito VISTO no log da sessao dele
(pid 26424, 2026-11-12 19:21-19:31, preservada em
`_main/_cache/caption-session-20261112-1921.log`):

  1. LAND-FROZEN   o `CAPTION_LAND` e' o registro que diz "esta legenda comecou
                   no segundo X e pintou-se no Y" -- e' dele que sai o
                   `lag_ms` que a casa cita. Na sessao medida ele repetiu a
                   MESMA tupla (`cue_t0=365.794 paint_t=368.740 lag_ms=2946`)
                   121 vezes em 6 minutos enquanto o texto pintado mudava. Um
                   instrumento congelado publica um drift que ninguem mediu.
  2. ROW-CLIP      a linha que o desenho DIZ ter (`EXTERNAL_CAPTION_DRAWN`) e a
                   que a pintura LEVOU (`CAPTION_PAINT_SURFACE text=`) tem de
                   ser a mesma. Medido: desenho `'to line these up'`, pintura
                   `"t"` -- a segunda linha saia cortada no primeiro caracter.
  3. DUP-PAINT     duas pinturas com o MESMO texto dentro de 20 ms sao um
                   payload entregue duas vezes, e um payload duplicado e' uma
                   das formas de uma linha ANTIGA chegar depois de uma nova.
                   Medido: `CAPTION_LAND` + `CAPTION_PAINT_SURFACE` emitidos
                   duas vezes, 6 ms de intervalo, na maioria das pinturas.
  4. LONG-HOLD     com a legenda ao vivo ligada, um texto nao pode ficar no ecra
                   mais de `HOLD_CEILING_S` sem o worker/player dizer nada. O
                   dono: *"a legenda continua mostrando as frases por muito
                   tempo"*.
  5. STALL         o maior intervalo entre pinturas enquanto o player corria.

O QUE ELE NAO FAZ
-----------------
Nao decide nada e nao pinta nada: le', julga e imprime. Nao abre janela, nao
toca em audio, nao larga a app -- e' o irmao de leitura do
`paint-live-show-oracle.py`.

USO
---
    python _main/caption-timeline.py                  # a ULTIMA sessao do log vivo
    python _main/caption-timeline.py --pid 26424
    python _main/caption-timeline.py --log _main/_cache/caption-session-*.log
    python _main/caption-timeline.py --json out.json
    python _main/caption-timeline.py --selftest       # os detectores, com fixture
    python _main/caption-timeline.py --neg-arm        # a fixture mutada

`--selftest` e `--neg-arm` nao leem o log vivo: eles julgam ESTE ficheiro, com
uma fixture sintetica, e o `--neg-arm` desliga cada detector e exige que o
detector ACUSE a ausencia. Um detector que nao pode falhar nao e' um detector.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
LOG_DEFAULT = os.path.join(ROOT, '_main', 'webview-run.log')

#: O TECTO DE PERMANENCIA. Nao e' um gosto: a legenda do YouTube mais longa que
#: o proprio player mostra sao dois cues encadeados (~10 s em fala normal), e o
#: `CAPTION_IDLE_HIDE_S = 6.0` do shell ja' apaga por silencio. Um texto que
#: sobrevive mais de 12 s esta' preso -- folga de 2x sobre o unico numero medido
#: nesta casa, para o braco nao acusar um cue longo legitimo.
HOLD_CEILING_S = 12.0
#: Duas pinturas com o mesmo texto dentro deste intervalo sao a MESMA entrega.
DUP_WINDOW_MS = 20.0
#: O desenho e a pintura de um MESMO quadro chegam a milissegundos de distancia.
PAIR_WINDOW_MS = 250.0
#: O registro do `land` e' congelado quando repete a mesma tupla `count` vezes
#: ao longo de um intervalo maior que isto. Tres repeticoes em < 1 s sao um
#: mesmo cue relatado por dois caminhos; 121 em 6 min e' um registro morto.
FROZEN_MIN_COUNT = 5
FROZEN_MIN_SPAN_S = 5.0
#: Um intervalo entre pinturas acima disto, com o player a correr, e' o laco a
#: parar -- a queixa "ela trava" medida em tempo.
STALL_S = 3.0

TS_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\.(\d{3}) ')
KV_RE = re.compile(r'(\w+)=("[^"]*"|\S+)')


def parse_log(path, pid=None):
    """Le o log e devolve (rows, starts) -- `rows` ja' filtradas pela sessao."""
    rows = []
    starts = []
    stamp = None
    day_base = None
    with io.open(path, 'r', encoding='utf-8', errors='replace') as handle:
        for line in handle:
            matched = TS_RE.match(line)
            if matched:
                day, millis = matched.group(1), matched.group(2)
                from datetime import datetime
                try:
                    stamp = datetime.strptime(day, '%Y-%m-%d %H:%M:%S').timestamp() \
                        + int(millis) / 1000.0
                except ValueError:
                    stamp = None
                day_base = day
                body = line[matched.end():]
            else:
                body = line.rstrip('\n')
            if 'SHELL_STARTUP_STAGE' in body and 'pid=' in body:
                fields = dict(KV_RE.findall(body))
                starts.append({'pid': fields.get('pid'), 't': stamp,
                               'raw': body.strip()})
                continue
            rows.append({'t': stamp, 'body': body.rstrip('\n'),
                         'day': day_base})
    if pid:
        wanted = str(pid)
        for index, start in enumerate(starts):
            if start['pid'] == wanted:
                session = [row for row in rows
                           if row['day'] is not None
                           and start['t'] is not None
                           and start['t'] <= row['t']
                           and (index + 1 >= len(starts)
                                or starts[index + 1]['t'] is None
                                or row['t'] < starts[index + 1]['t'])]
                return session, [start]
        return [], []
    if starts:
        last = starts[-1]
        session = [row for row in rows
                   if row['t'] is not None and last['t'] is not None
                   and row['t'] >= last['t']]
        return session, [last]
    return rows, []


def all_pids(path):
    """TODOS os pids que arrancaram neste log, por ordem.

    `parse_log` devolve so' a sessao pedida (ou a ultima) -- e por isso nao
    serve para ESCOLHER uma sessao entre todas. Esta le' os marcadores e nao
    carrega as linhas: 27 marcadores num log de 216 mil linhas custa nada.
    """
    out = []
    with io.open(path, 'r', encoding='utf-8', errors='replace') as handle:
        for line in handle:
            if 'SHELL_STARTUP_STAGE' not in line or 'pid=' not in line:
                continue
            matched = TS_RE.match(line)
            if not matched:
                continue
            fields = dict(KV_RE.findall(line[matched.end():]))
            pid = fields.get('pid')
            if pid and pid not in out:
                out.append(pid)
    return out


def kv(body):
    out = {}
    for key, value in KV_RE.findall(body):
        if value.startswith('"') and value.endswith('"') and len(value) >= 2:
            value = value[1:-1]
        out[key] = value
    return out


def lands(rows):
    """Os registros do `CAPTION_LAND`, um por tupla (cue, paint, texto)."""
    out = []
    for row in rows:
        if ' CAPTION_LAND ' not in row['body']:
            continue
        fields = kv(row['body'])
        text = ''
        matched = re.search(r'text="(.*)"\s*$', row['body'])
        if matched:
            text = matched.group(1)
        out.append({'t': row['t'], 'cue_t0': fields.get('cue_t0'),
                    'paint_t': fields.get('paint_t'),
                    'lag_ms': fields.get('lag_ms'), 'text': text,
                    'key': (fields.get('cue_t0'), fields.get('paint_t'), text)})
    return out


def drawn(rows):
    out = []
    for row in rows:
        if ' EXTERNAL_CAPTION_DRAWN ' not in row['body']:
            continue
        matched = re.search(r'lines=(\[.*\])\s*$', row['body'])
        lines = None
        if matched:
            try:
                lines = json.loads(matched.group(1).replace("'", '"'))
            except ValueError:
                lines = None
        out.append({'t': row['t'], 'lines': lines})
    return out


#: O QUE EXPLICA UM `CAPTION_APPLIED` SEM PINTURA (2026-11-26).
#: `CAPTION_APPLIED` e' o painel a dizer que aplicou a linha; a testemunha do
#: ECRRA e' `CAPTION_PAINT_SURFACE` (`_main/boot-interaction-oracle.py`
#: `PAINT_WITNESSES`). A janela e' 2 s porque o push e o apply sao caminhos
#: diferentes do MESMO evento (medido no log do dono, 2026-11-26: o apply das
#: 02:38:11.784 caiu 1,27 s depois da ultima pintura, 10.512).
APPLIED_WITNESS_S = 2.0
#: Um `CAPTION_APPLIED` sem pintura so' se explica por uma RAZAO NOMEADA de que o
#: ecra nao ia mudar. `CAPTION_PROVISIONAL_PAINT` NAO explica: ele e' o caminho
#: da PAGINA, e um painel que aplica o que o overlay nunca recebeu e' o defeito.
APPLIED_EXCUSES = ('CAPTION_WINDOW_BLANKED', 'CAPTION_KEPT_ON_HIDE',
                   'EXTERNAL_CAPTIONS_RELEASED', 'CAPTION_IDLE_HIDE')


def applies(rows):
    out = []
    for row in rows:
        if ' CAPTION_APPLIED ' not in row['body']:
            continue
        matched = re.search(r'text="(.*?)(?:\\"|") count=', row['body'])
        out.append({'t': row['t'],
                    'text': matched.group(1) if matched else ''})
    return out


def check_applied(rows, paint_rows=None):
    """APPLIED-UNPAINTED: o painel aplicou uma linha que o ecra nunca pintou.

    MEDIDO no log do dono (2026-11-26 02:38:10.436 -> 11.784): a janela foi
    apagada pela pausa provada, o painel recebeu duas linhas
    (`CAPTION_APPLIED text="To 12 times efficiency."`) e NENHUMA
    `CAPTION_PAINT_SURFACE` saiu ate' a shell sair 12 s depois -- o dono viu a
    legenda congelar. Aquele caso era EXPLICADO (`CAPTION_WINDOW_BLANKED
    reason=youtube-paused` a 1,35 s), e e' isso que este detector aceita; o que
    ele recusa e' o apply sem pintura e sem razao nenhuma, que e' como um painel
    a funcionar sozinho se apresenta.
    """
    paint_rows = paints(rows) if paint_rows is None else paint_rows
    applied = applies(rows)
    excuses = []
    for row in rows:
        if any(token in row['body'] for token in APPLIED_EXCUSES):
            excuses.append(row['t'])
    out = []
    for item in applied:
        when = item['t']
        words = set(_words(item['text']))
        excused = False
        for paint in paint_rows:
            if paint['t'] is None or when is None:
                continue
            if abs(paint['t'] - when) > APPLIED_WITNESS_S:
                continue
            if not words or words <= set(_words(paint['text'])):
                excused = True
                break
        if not excused:
            for stamp in excuses:
                if stamp is None or when is None:
                    continue
                if abs(stamp - when) <= APPLIED_WITNESS_S:
                    excused = True
                    break
        if not excused:
            out.append(item)
    return out


def paints(rows):
    out = []
    for row in rows:
        if ' CAPTION_PAINT_SURFACE ' not in row['body']:
            continue
        matched = re.search(r'text="(.*)" ms=\d+', row['body'])
        text = matched.group(1) if matched else ''
        out.append({'t': row['t'], 'text': text,
                    'epoch': kv(row['body']).get('epoch')})
    return out


def check_frozen(land_rows):
    """LAND-FROZEN: a mesma tupla repetida ao longo de um intervalo longo."""
    buckets = {}
    for row in land_rows:
        buckets.setdefault(row['key'], []).append(row)
    frozen = []
    for key, items in buckets.items():
        span = (items[-1]['t'] or 0) - (items[0]['t'] or 0)
        if len(items) >= FROZEN_MIN_COUNT and span >= FROZEN_MIN_SPAN_S:
            frozen.append({'key': list(key), 'count': len(items),
                           'span_s': round(span, 1), 'text': key[2][:80]})
    frozen.sort(key=lambda item: -item['count'])
    return frozen


def _words(text):
    return [word for word in text.replace('\\n', ' ').split(' ') if word]


def _acceptable(drawn_line, painted_line):
    """A pintura pode estar ATRASADA na revelacao, nunca errada.

    Palavra por palavra e' o que o dono pede ("`nao a frase inteira`"), logo a
    pintura e' legitimamente um PREFIXO de palavras do desenho. O que nao pode
    acontecer -- e aconteceu na sessao dele -- e' a pintura ser um prefixo de
    CARACTERES de uma palavra (`to line these up` -> `t`): a palavra partida no
    ecra e' o defeito, e e' isso que este braco mede.
    """
    drawn_words = _words(drawn_line)
    painted_words = _words(painted_line)
    if not painted_words:
        return True
    if len(painted_words) > len(drawn_words):
        return False
    if painted_words != drawn_words[:len(painted_words)]:
        return False
    last = painted_words[-1]
    return drawn_words[len(painted_words) - 1].startswith(last)


def _missing_words(drawn_line, painted_line):
    drawn_words = _words(drawn_line)
    painted_words = _words(painted_line)
    if painted_words and drawn_words[:len(painted_words)] == painted_words:
        tail = drawn_words[len(painted_words):]
        return ' '.join(tail)[:60]
    return ''


def _compare_rows(drawn_lines, painted, previous_drawn=None):
    """O desenho e a pintura da MESMA linha -- com a rolagem no meio.

    Tres casos legitimos, um defeito:

    * `ok` a pintura e' palavra-a-palavra um prefixo do desenho (a revelacao
      pode estar ATRASADA; atrasar nao e' cortar a palavra ao meio);
    * `ok` a pintura traz UMA linha a mais no topo, e essa linha e' a ULTIMA
      linha do desenho ANTERIOR -- e' o roll-up que o dono pediu (a linha velha
      sobe enquanto a nova entra), e ela tem de ser a de antes, nao uma de tres
      cues atras;
    * `ok` a pintura e' MAIOR que o desenho por uma linha vazia no fim (o
      respirador da caixa), que ja' foi descartado aqui.

    Defeito: qualquer outra linha extra, ou uma linha que nao e' prefixo por
    PALAVRA (`to line these up` pintado como `t` -- a palavra partida no ecra
    que o dono viu).
    """
    if not painted:
        return 'ok', None
    offset = 0
    if len(painted) > len(drawn_lines):
        offset = len(painted) - len(drawn_lines)
        if offset != 1:
            return 'rows', ' '.join(painted[:offset])
        head = painted[0]
        lagging = (_words(drawn_lines[0])[:1] if drawn_lines else [])
        if previous_drawn:
            tail = _words(previous_drawn[-1])
            if not (head.strip() and (not tail or head in (' '.join(tail),)
                                      or ' '.join(tail).startswith(head))):
                return 'stale-row-in-front', head
        elif lagging and not head.strip():
            return 'rows', head
    aligned = painted[offset:]
    for index, line in enumerate(aligned):
        if index >= len(drawn_lines):
            return 'rows', line
        if not _acceptable(drawn_lines[index], line):
            return 'clip', line
    return 'ok', None


def check_rows(rows):
    """ROW-CLIP: a linha desenhada tem de estar na pintura seguinte."""
    mismatches = []
    drawn_rows = drawn(rows)
    paint_rows = paints(rows)
    previous_cue = None
    cursor = 0
    for item in drawn_rows:
        while cursor < len(paint_rows) and paint_rows[cursor]['t'] is not None \
                and item['t'] is not None and paint_rows[cursor]['t'] < item['t']:
            cursor += 1
        # Um `ms=0` carrega o texto ANTERIOR: o overlay nao repintou porque o
        # alvo nao mudou (medido 2026-11-12 19:32: `DRAW ['annoying.','That']`
        # seguido de uma pintura identica a de antes, e o texto novo so' na
        # pintura seguinte). Quem julga e' a primeira pintura que MUDA, senao o
        # braco acusa o desenho de nao estar no ecra quando ele ainda nao podia
        # estar -- um vermelho do instrumento, nao do produto.
        felt = cursor
        while felt < len(paint_rows):
            before = paint_rows[felt - 1]['text'] if felt > 0 else None
            if paint_rows[felt]['text'] != before:
                break
            felt += 1
        if cursor >= len(paint_rows) or felt >= len(paint_rows):
            break
        nxt = paint_rows[felt]
        if item['t'] is None or nxt['t'] is None:
            continue
        if (nxt['t'] - item['t']) * 1000.0 > PAIR_WINDOW_MS:
            continue
        if not item['lines']:
            continue
        # O log ESCAPA a quebra de linha (`text="...\\nt"`, com a barra invertida
        # literal no ficheiro) -- medido na sessao do dono: a linha que chega ao
        # parser e' `hello\nt` e um `split('\n')` devolve UM elemento so', o que
        # fazia o braco A7 medir o escape em vez da pintura.
        painted = [line for line in
                   nxt['text'].replace('\\n', '\n').split('\n')]
        while painted and not painted[-1].strip():
            painted.pop()
        drawn_lines = [str(x) for x in item['lines']]
        verdict, extra = _compare_rows(drawn_lines, painted, previous_cue)
        if verdict != 'ok':
            mismatches.append({'drawn': drawn_lines,
                               'painted': painted,
                               'why': verdict,
                               'extra_line': extra,
                               'lagging_words': [
                                   _missing_words(drawn_lines[i], painted[i])
                                   for i in range(min(len(painted), len(drawn_lines)))],
                               'ms': round((nxt['t'] - item['t']) * 1000.0, 1)})
        previous_cue = drawn_lines
    return mismatches


def check_dups(paint_rows):
    """DUP-PAINT: o mesmo texto pintado duas vezes dentro da janela."""
    dups = []
    for previous, current in zip(paint_rows, paint_rows[1:]):
        if previous['t'] is None or current['t'] is None:
            continue
        gap_ms = (current['t'] - previous['t']) * 1000.0
        if previous['text'] == current['text'] and gap_ms <= DUP_WINDOW_MS:
            dups.append({'text': previous['text'][:80],
                         'ms': round(gap_ms, 1)})
    return dups


def check_hold(paint_rows, ceiling_s=HOLD_CEILING_S):
    """LONG-HOLD: um texto que fica no ecra alem do tecto."""
    holds = []
    for previous, current in zip(paint_rows, paint_rows[1:]):
        if previous['t'] is None or current['t'] is None:
            continue
        if previous['text'] == current['text']:
            continue
        held = current['t'] - previous['t']
        if held > ceiling_s:
            holds.append({'text': previous['text'][:80],
                          'held_s': round(held, 2)})
    return holds


def check_stall(paint_rows, limit_s=STALL_S):
    """STALL: o maior intervalo entre pinturas, e os que passam do limite."""
    worst = 0.0
    stalls = []
    for previous, current in zip(paint_rows, paint_rows[1:]):
        if previous['t'] is None or current['t'] is None:
            continue
        gap = current['t'] - previous['t']
        worst = max(worst, gap)
        if gap > limit_s:
            stalls.append({'gap_s': round(gap, 2),
                           'after': previous['text'][:60]})
    return {'worst_s': round(worst, 2), 'stalls': stalls,
            'count': len(paint_rows)}


def plate_applies(rows):
    """As linhas em que o DESENHO com placa chegou a' janela."""
    out = []
    for row in rows:
        if ' CAPTION_OVERLAY_THEME_APPLIED ' not in row['body']:
            continue
        fields = kv(row['body'])
        if str(fields.get('plate') or '').lower() != 'yes':
            continue
        out.append({'t': row['t'], 'theme': fields.get('theme'),
                    'why': fields.get('why')})
    return out


def plate_rows(rows):
    """As linhas `CAPTION_PLATE` -- o facto por QUADRO, nao por tema aplicado.

    Medido na sessao do dono (pid 18160, 2026-11-12): `CAPTION_PLATE plate=off
    ... text=1 paint_n=1` as 19:56:17.465 e `plate=yes` so' as 19:56:31.592 --
    14,1 s de texto sem fundo. Esta linha e' a testemunha DIRETA; o
    `CAPTION_OVERLAY_THEME_APPLIED` e' o proxy (o desenho chegou), e os dois
    concordam quando o desenho ja' existia na criacao.
    """
    out = []
    for row in rows:
        if ' CAPTION_PLATE ' not in row['body']:
            continue
        fields = kv(row['body'])
        out.append({'t': row['t'], 'plate': fields.get('plate'),
                    'text_n': fields.get('text_n'),
                    'lag_frames': fields.get('lag_frames'),
                    'lag_ms': fields.get('lag_ms')})
    return out


def check_plate_late(rows, rows_paint=None):
    """PLATE-LATE: texto no ecra antes de a placa do desenho existir.

    MEDIDO na sessao do dono (pid 46056): a primeira linha pintou as
    19:41:44.254 e o `CAPTION_OVERLAY_THEME_APPLIED ... plate=yes` chegou as
    19:41:46.327 -- **2,07 s de legenda sem fundo**, verbatim: *"o background da
    legenda atrasou pra aparecer. entao a legenda ficou uns segundos sem
    background"*. A placa e' pintada no MESMO bitmap que os glifos, logo o
    defeito nao e' de pintura: e' a janela nascer sem desenho.

    O braco mede a ORDEM, nao a existencia: um `theme-1` legitimo que nunca teve
    placa nao acusa nada (o desenho do YouTube nao tem fundo por ordem), e um
    arranque que ja' nasce vestido nao acusa nada. O vermelho e' so' a janela em
    que houve pixel de texto e o desenho com placa ainda nao tinha chegado.
    """
    paints = rows_paint if rows_paint is not None else paints(rows)
    # O FACTO POR QUADRO MANDA QUANDO EXISTE: `CAPTION_PLATE ... lag_frames=N`
    # e' a distancia entre o primeiro pixel de texto e o pixel da placa, medida
    # no proprio overlay. O tema aplicado fica como proxy para uma sessao que
    # ainda nao emite esta linha.
    for row in plate_rows(rows):
        if str(row['plate'] or '').lower() != 'on':
            continue
        try:
            lag_frames = int(row['lag_frames'] or 0)
            lag_ms = float(row['lag_ms'] or 0.0)
        except (TypeError, ValueError):
            continue
        if lag_frames > 0:
            first = paints[0]['text'][:60] if paints else ''
            return [{'late_ms': round(lag_ms, 1), 'theme': '-',
                     'why': 'frames', 'first_paint': first,
                     'lag_frames': lag_frames}]
        return []
    applies = plate_applies(rows)
    if not paints:
        # Sem `CAPTION_PAINT_SURFACE` (uma janela que nasceu vestida e ainda nao
        # pintou texto) nao ha' o que julgar: um `why=overlay-created` com placa
        # e' a CURA, nao um defeito.
        return []
    if not applies:
        return []
    first_paint = paints[0]['t']
    first_apply = applies[0]['t']
    if first_paint is None or first_apply is None or first_apply <= first_paint:
        return []
    return [{'late_ms': round((first_apply - first_paint) * 1000.0, 1),
             'theme': applies[0]['theme'], 'why': applies[0]['why'],
             'first_paint': paints[0]['text'][:60]}]


#: QUANTO TEMPO UM VIDEO A ANDAR PODE FICAR COM O ECRA APAGADO POR CAUSA DE UMA
#: PAUSA (2026-11-12). Nao e' um gosto: e' o `CLOCK_STATIC_PAUSE_S` do shell
#: (2,0 s) mais o passo de leitura lento da pausa (0,5 s) e folga. Acima disto,
#: com quadros novos a chegar, a bandeira esta' a mentir.
PAUSE_FREEZE_S = 3.0


def check_pause_freeze(rows, limit_s=PAUSE_FREEZE_S):
    """PAUSE-FREEZE: o ecra apagado por `youtube-paused` com o video a andar.

    O DONO, verbatim (2026-11-12): *"por que agora mesmo, ao apertar ctrl space
    algumas vezes, ela travou"* e *"as vezes ta no sync, as vezes so' para e nao
    continua dando display palavra por palavra"*. MEDIDO nesta sessao (pid
    46056), e e' o defeito inteiro:

        19:41:49.489  YOUTUBE_CDP_PACED paused=True poll_s=0.50
        19:41:49.537  CAPTION_WINDOW_BLANKED reason=youtube-paused epoch=3
        ...           38 `YT_FRAME` com o texto a MUDAR durante 12 minutos ...
        19:53:48.635  YOUTUBE_POLL_PACED paused=False
        e ZERO `CAPTION_PAINT_SURFACE` nesses 12 minutos.

    A bandeira `video.paused` leu True e nao voltou a ler False; o portao do
    `external_caption` recusa pixels enquanto `yt_source_paused` for verdadeiro.
    O ecra fica vazio com o video a tocar, e nenhuma tecla o traz de volta.

    A medida: desde um `CAPTION_WINDOW_BLANKED reason=youtube-paused` ate' ao
    primeiro `CAPTION_PAINT_SURFACE` seguinte, OU ate' ao fim da sessao. Se
    nesse intervalo chegaram >= 2 `YT_FRAME` com texto DIFERENTE (o player a
    desenhar linhas novas) e o intervalo passou de `limit_s`, e' PAUSE-FREEZE.
    Um video realmente pausado nao produz quadros novos -- e' isso que separa
    a pausa verdadeira desta.
    """
    out = []
    blank_at = None
    frames = []
    for row in rows:
        body = row['body']
        if ' CAPTION_WINDOW_BLANKED ' in body and 'reason=youtube-paused' in body:
            blank_at = row['t']
            frames = []
            continue
        if blank_at is None:
            continue
        if ' CAPTION_PAINT_SURFACE ' in body or ' CAPTION_PAINT ' in body:
            blank_at = None
            frames = []
            continue
        if ' YT_FRAME ' in body:
            text = body.split('lines=', 1)[-1]
            if not frames or frames[-1] != text:
                frames.append(text)
            if (row['t'] is not None and len(frames) >= 2
                    and row['t'] - blank_at > limit_s):
                out.append({'t': blank_at, 'held_s': round(row['t'] - blank_at, 1),
                            'new_frames': len(frames)})
                blank_at = None
    # A sessao acabou com o ecra apagado e o player a desenhar.
    if blank_at is not None and len(frames) >= 2:
        last = rows[-1]['t'] if rows and rows[-1]['t'] is not None else blank_at
        held = last - blank_at
        if held > limit_s:
            out.append({'t': blank_at, 'held_s': round(held, 1),
                        'new_frames': len(frames)})
    return out


def judge(rows, ceiling_s=HOLD_CEILING_S):
    """O veredicto inteiro, a partir das linhas ja' filtradas."""
    land_rows = lands(rows)
    paint_rows = paints(rows)
    frozen = check_frozen(land_rows)
    mism = check_rows(rows)
    dups = check_dups(paint_rows)
    holds = check_hold(paint_rows, ceiling_s)
    stall = check_stall(paint_rows)
    late_plate = check_plate_late(rows, paint_rows)
    pause_freeze = check_pause_freeze(rows)
    blind = check_applied(rows, paint_rows)
    failures = []
    if frozen:
        failures.append('LAND-FROZEN')
    if mism:
        failures.append('ROW-CLIP')
    if dups:
        failures.append('DUP-PAINT')
    if holds:
        failures.append('LONG-HOLD')
    if late_plate:
        failures.append('PLATE-LATE')
    if pause_freeze:
        failures.append('PAUSE-FREEZE')
    if blind:
        failures.append('APPLIED-UNPAINTED')
    return {
        'land_records': len(land_rows),
        'land_distinct': len({row['key'] for row in land_rows}),
        'lands': land_rows,
        'frozen': frozen,
        'paints': len(paint_rows),
        'mismatches': mism,
        'dups': dups,
        'late_plate': late_plate,
        'pause_freeze': pause_freeze,
        'applied_blind': blind,
        'holds': holds,
        'stall': stall,
        'failures': failures,
        'verdict': 'FAIL' if failures else ('PASS' if paint_rows else 'SKIPPED'),
    }


def report(path, pid=None, ceiling_s=HOLD_CEILING_S, limit=6):
    rows, starts = parse_log(path, pid)
    result = judge(rows, ceiling_s)
    session = starts[-1] if starts else None
    print(f'caption-timeline  log={path}')
    if session:
        print(f'  sessao   pid={session["pid"]}')
    print(f'  linhas   {len(rows)}  (CAPTION_LAND={result["land_records"]} '
          f'distintos={result["land_distinct"]}  pinturas={result["paints"]})')
    if result['frozen']:
        for item in result['frozen'][:limit]:
            print(f'  LAND-FROZEN  n={item["count"]} span={item["span_s"]}s '
                  f'cue_t0={item["key"][0]} paint_t={item["key"][1]} '
                  f'text={item["text"]!r}')
    if result['mismatches']:
        for item in result['mismatches'][:limit]:
            print(f'  ROW-CLIP     drawn={item["drawn"]!r} '
                  f'painted={item["painted"]!r} ms={item["ms"]}')
    if result['dups']:
        print(f'  DUP-PAINT    n={len(result["dups"])} '
              f'worst_ms={max(d["ms"] for d in result["dups"])}')
    if result['holds']:
        for item in result['holds'][:limit]:
            print(f'  LONG-HOLD    {item["held_s"]}s text={item["text"]!r}')
    if result['pause_freeze']:
        item = result['pause_freeze'][0]
        print(f'  PAUSE-FREEZE ecra={item["held_s"]}s com o video a andar '
              f'frames={item["new_frames"]}')
    if result['applied_blind']:
        for item in result['applied_blind'][:limit]:
            print(f'  APPLIED-UNPAINTED text={item["text"]!r} '
                  f'(nenhuma pintura nem razao em {APPLIED_WITNESS_S:g}s)')
    if result['late_plate']:
        item = result['late_plate'][0]
        print(f'  PLATE-LATE   {item["late_ms"]}ms theme={item["theme"]} '
              f'why={item["why"]} text={item["first_paint"]!r}')
    stall = result['stall']
    print(f'  STALL        worst={stall["worst_s"]}s '
          f'over_{STALL_S:g}s={len(stall["stalls"])} paints={stall["count"]}')
    print(f'VERDICT: {result["verdict"]}'
          + ('' if not result['failures']
             else '  falhas=' + ','.join(result['failures'])))
    return result


# ---------------------------------------------------------------- fixture ----
#: A fixture e' LITERALMENTE a forma da sessao do dono, encolhida: um `land`
#: congelado, um desenho cuja segunda linha a pintura corta, a mesma pintura
#: entregue duas vezes e um texto seguro por 20 s. Cada detector tem de a ver.
FIXTURE = '''\
2026-11-12 19:21:04.738 sotto: SHELL_STARTUP_STAGE pid=999 stage=pre-lock
2026-11-12 19:21:05.100 sotto: CAPTION_PAINT_SURFACE src=player rows=2 text="hello\\n" ms=0 epoch=1
2026-11-12 19:21:07.100 sotto: CAPTION_OVERLAY_THEME_APPLIED theme=theme-1 font=Arial live=38.0 brand=theme-1 plate=yes alpha=219 radius=7.4 fade=no why=page
2026-11-12 19:21:05.112 sotto: CAPTION_PAINT_SURFACE src=player rows=2 text="hello\\n" ms=0 epoch=1
2026-11-12 19:21:05.200 sotto: EXTERNAL_CAPTION_DRAWN rows=2 lines=["hello", "to line these"]
2026-11-12 19:21:05.210 sotto: CAPTION_PAINT_SURFACE src=player rows=2 text="hello\\nt" ms=6 epoch=1
2026-11-12 19:21:05.500 sotto: CAPTION_LAND cue_t0=365.794 paint_t=368.740 lag_ms=2946 rows=2 text="a"
2026-11-12 19:21:07.500 sotto: CAPTION_LAND cue_t0=365.794 paint_t=368.740 lag_ms=2946 rows=2 text="a"
2026-11-12 19:21:09.500 sotto: CAPTION_LAND cue_t0=365.794 paint_t=368.740 lag_ms=2946 rows=2 text="a"
2026-11-12 19:21:11.500 sotto: CAPTION_LAND cue_t0=365.794 paint_t=368.740 lag_ms=2946 rows=2 text="a"
2026-11-12 19:21:13.500 sotto: CAPTION_LAND cue_t0=365.794 paint_t=368.740 lag_ms=2946 rows=2 text="a"
2026-11-12 19:21:33.600 sotto: CAPTION_PAINT_SURFACE src=player rows=2 text="later\\nline" ms=0 epoch=1
2026-11-12 19:21:34.000 sotto: YOUTUBE_CDP_PACED paused=True poll_s=0.50
2026-11-12 19:21:34.040 sotto: CAPTION_WINDOW_BLANKED reason=youtube-paused epoch=4 wanted=true
2026-11-12 19:21:35.000 sotto: YT_FRAME src=external:youtube:track rows=2 lines=['annoying.', 'That']
2026-11-12 19:21:36.500 sotto: YT_FRAME src=external:youtube:track rows=2 lines=['That', "really wasn't"]
2026-11-12 19:21:39.000 sotto: CAPTION_APPLIED text="That really wasn't." count=9 kind=partial
'''


def _selftest():
    import tempfile
    cases = []

    path = os.path.join(tempfile.mkdtemp(prefix='caption-timeline-'), 'fixture.log')
    with io.open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(FIXTURE)
    rows, _starts = parse_log(path)
    result = judge(rows)

    cases.append(('A1 LAND-FROZEN visto', bool(result['frozen']),
                  f'n={len(result["frozen"])}'))
    cases.append(('A2 ROW-CLIP visto', bool(result['mismatches']),
                  f'n={len(result["mismatches"])}'))
    cases.append(('A3 DUP-PAINT visto', bool(result['dups']),
                  f'n={len(result["dups"])}'))
    cases.append(('A4 LONG-HOLD visto', bool(result['holds']),
                  f'n={len(result["holds"])}'))
    cases.append(('A5 veredicto FAIL na fixture',
                  result['verdict'] == 'FAIL', result['verdict']))
    # A9: o painel aplicou 5 s depois da ultima pintura e da ultima razao
    # nomeada -- nada explica aquela linha no ecra.
    cases.append(('A9 APPLIED-UNPAINTED visto', bool(result['applied_blind']),
                  f'n={len(result["applied_blind"])}'))

    # A6: a fixture sem o congelamento -- o land muda de tupla a cada linha. O
    # detector TEM de calar, senao ele acusa qualquer sessao longa.
    clean = FIXTURE.replace('cue_t0=365.794 paint_t=368.740 lag_ms=2946',
                            'cue_t0=366.000 paint_t=366.050 lag_ms=50')
    clean = clean.replace('text="a"', 'text="a"')
    clean_lines = []
    for index, line in enumerate(clean.splitlines()):
        clean_lines.append(line.replace('cue_t0=366.000', f'cue_t0={366.0 + index}'))
    clean_path = os.path.join(os.path.dirname(path), 'clean.log')
    with io.open(clean_path, 'w', encoding='utf-8', newline='') as handle:
        handle.write('\n'.join(clean_lines) + '\n')
    clean_rows, _ = parse_log(clean_path)
    clean_result = judge(clean_rows)
    # A10: o MESMO apply, 0,4 s depois de uma razao NOMEADA (`CAPTION_WINDOW_
    # BLANKED`), tem de ficar em silencio -- a janela nao ia mudar e a razao esta'
    # escrita. Sem esta arm o detector acusaria toda pausa do dono, que e' o
    # `HOLD` legitimo.
    excused = FIXTURE.replace(
        '2026-11-12 19:21:39.000 sotto: CAPTION_APPLIED',
        '2026-11-12 19:21:34.500 sotto: CAPTION_APPLIED')
    excused_path = os.path.join(os.path.dirname(path), 'excused.log')
    with io.open(excused_path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(excused)
    excused_rows, _ = parse_log(excused_path)
    excused_result = judge(excused_rows)
    cases.append(('A10 apply explicado por razao nomeada cala',
                  not excused_result['applied_blind'],
                  f'n={len(excused_result["applied_blind"])}'))

    cases.append(('A6 sem congelamento o detector cala',
                  not clean_result['frozen'],
                  f'n={len(clean_result["frozen"])}'))

    # A7: a fixture com o desenho IGUAL a pintura. O `ROW-CLIP` tem de calar.
    aligned = FIXTURE.replace('lines=["hello", "to line these"]',
                              'lines=["hello", "t"]')
    aligned_path = os.path.join(os.path.dirname(path), 'aligned.log')
    with io.open(aligned_path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(aligned)
    aligned_rows, _ = parse_log(aligned_path)
    cases.append(('A7 desenho == pintura silencia o ROW-CLIP',
                  not judge(aligned_rows)['mismatches'],
                  f'n={len(judge(aligned_rows)["mismatches"])}'))

    # A8: sem `CAPTION_PAINT_SURFACE` nenhum o veredicto e' SKIPPED -- ausencia
    # de medida nunca e' PASS (a lei desta casa).
    empty_path = os.path.join(os.path.dirname(path), 'empty.log')
    with io.open(empty_path, 'w', encoding='utf-8', newline='') as handle:
        handle.write('2026-11-12 19:21:04.738 sotto: SHELL_STARTUP_STAGE pid=1 stage=x\n')
    empty_rows, _ = parse_log(empty_path)
    cases.append(('A8 sem pintura -> SKIPPED',
                  judge(empty_rows)['verdict'] == 'SKIPPED',
                  judge(empty_rows)['verdict']))

    # A9: o filtro por `--pid` escolhe a sessao certa. Duas sessoes na fixture,
    # e a antiga tem o congelamento: pedir a NOVA nao pode devolver a velha.
    two = (FIXTURE
           + '2026-11-12 20:00:00.000 sotto: SHELL_STARTUP_STAGE pid=1000 stage=pre-lock\n'
           + '2026-11-12 20:00:01.000 sotto: CAPTION_PAINT_SURFACE src=player rows=1 '
             'text="only" ms=0 epoch=2\n'
           + '2026-11-12 20:00:01.500 sotto: CAPTION_PAINT_SURFACE src=player rows=1 '
             'text="next" ms=0 epoch=2\n')
    two_path = os.path.join(os.path.dirname(path), 'two.log')
    with io.open(two_path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(two)
    newest_rows, newest_starts = parse_log(two_path)
    cases.append(('A9 --pid escolhe a sessao pedida',
                  bool(newest_starts) and newest_starts[-1]['pid'] == '1000'
                  and not judge(newest_rows)['frozen'],
                  f'pids={[s["pid"] for s in newest_starts]} '
                  f'paints={len(paints(newest_rows))}'))

    # A10: o TEXTO ANTES DA PLACA (2026-11-12). A fixture tem uma pintura as
    # .100 e o desenho com placa a chegar 2,0 s depois -- a forma MEDIDA na
    # sessao do dono (`PLATE-LATE 2073.0ms`). O detector tem de a ver, e a
    # sessao que ja' nasce vestida tem de calar.
    late = judge(rows)['late_plate']
    cases.append(('A10 PLATE-LATE visto', bool(late),
                  f'ms={late[0]["late_ms"] if late else 0}'))
    early = FIXTURE.replace(
        '2026-11-12 19:21:05.100 sotto: CAPTION_PAINT_SURFACE',
        '2026-11-12 19:21:04.900 sotto: CAPTION_OVERLAY_THEME_APPLIED '
        'theme=theme-1 font=Arial live=38.0 brand=theme-1 plate=yes alpha=219 '
        'radius=7.4 fade=no why=overlay-created\n'
        '2026-11-12 19:21:05.100 sotto: CAPTION_PAINT_SURFACE', 1)
    early_path = os.path.join(os.path.dirname(path), 'early.log')
    with io.open(early_path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(early)
    early_rows, _ = parse_log(early_path)
    cases.append(('A11 janela ja vestida cala o PLATE-LATE',
                  not judge(early_rows)['late_plate'],
                  f'n={len(judge(early_rows)["late_plate"])}'))

    # A12: o ecra apagado por `youtube-paused` com o player a desenhar linhas
    # NOVAS (2026-11-12). A fixture tem exactamente a forma medida na sessao do
    # dono: blank as 19:21:34.040 e dois `YT_FRAME` distintos sem uma pintura
    # entre eles; o detector tem de ver, e uma pausa VERDADEIRA (quadros
    # repetidos, sem texto novo) tem de calar.
    freeze = judge(rows)['pause_freeze']
    cases.append(('A12 PAUSE-FREEZE visto', bool(freeze),
                  f'held_s={freeze[0]["held_s"] if freeze else 0}'))
    real_pause = FIXTURE.replace(
        "lines=['annoying.', 'That']", "lines=['annoying.', 'That']").replace(
        "lines=['That', \"really wasn't\"]", "lines=['annoying.', 'That']")
    rp_path = os.path.join(os.path.dirname(path), 'real-pause.log')
    with io.open(rp_path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(real_pause)
    rp_rows, _ = parse_log(rp_path)
    cases.append(('A13 pausa de verdade cala o PAUSE-FREEZE',
                  not judge(rp_rows)['pause_freeze'],
                  f'n={len(judge(rp_rows)["pause_freeze"])}'))

    ok = all(good for _name, good, _ev in cases)
    for name, good, evidence in cases:
        print(('PASS ' if good else 'FAIL ') + name + ' -- ' + str(evidence))
    print(f'{{\"ok\": {str(ok).lower()}, \"cases\": {len(cases)}, '
          f'\"caught\": {sum(1 for _n, g, _e in cases if g)}}}')
    print('NEG-ARM: PASS' if ok else 'NEG-ARM: FAIL')
    return 0 if ok else 1


def _neg_arm():
    """Cada detector DESLIGADO tem de fazer a fixture deixar de ser acusada.

    A mutacao e' no DETECTOR, nao na fixture: desligar o detector e exigir que a
    ausencia de acusacao apareca prova que foi ele que acusou. Uma mutacao na
    fixture provaria so' que a fixture mudou.
    """
    global check_frozen, check_rows, check_dups, check_hold, check_plate_late
    global check_pause_freeze, check_applied
    import tempfile
    path = os.path.join(tempfile.mkdtemp(prefix='caption-timeline-neg-'), 'fixture.log')
    with io.open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(FIXTURE)
    rows, _ = parse_log(path)
    baseline = judge(rows)
    caught = []

    saved = (check_frozen, check_rows, check_dups, check_hold, check_plate_late,
             check_pause_freeze, check_applied)
    for label, target_name in (('M1 land-frozen', 'check_frozen'),
                               ('M2 row-clip', 'check_rows'),
                               ('M3 dup-paint', 'check_dups'),
                               ('M4 long-hold', 'check_hold'),
                               ('M5 plate-late', 'check_plate_late'),
                               ('M6 pause-freeze', 'check_pause_freeze'),
                               ('M7 applied-unpainted', 'check_applied')):
        (check_frozen, check_rows, check_dups, check_hold, check_plate_late,
         check_pause_freeze, check_applied) = saved
        globals()[target_name] = lambda *a, **k: []
        muted = judge(rows)
        wanted = {'M1 land-frozen': 'LAND-FROZEN', 'M2 row-clip': 'ROW-CLIP',
                  'M3 dup-paint': 'DUP-PAINT', 'M4 long-hold': 'LONG-HOLD',
                  'M5 plate-late': 'PLATE-LATE',
                  'M6 pause-freeze': 'PAUSE-FREEZE',
                  'M7 applied-unpainted': 'APPLIED-UNPAINTED'}[label]
        good = wanted in baseline['failures'] and wanted not in muted['failures']
        caught.append(good)
        print(('CAUGHT ' if good else 'MISSED ') + label
              + f'  antes={wanted in baseline["failures"]} '
                f'depois={wanted in muted["failures"]}')
    (check_frozen, check_rows, check_dups, check_hold, check_plate_late,
     check_pause_freeze, check_applied) = saved
    ok = all(caught)
    print(f'NEG-ARM: {"PASS" if ok else "FAIL"} -- {sum(caught)}/{len(caught)}')
    return 1 if ok else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='A linha do tempo da legenda: como ela se comporta, com '
                    'numeros do log que a app escreve.')
    parser.add_argument('--log', default=LOG_DEFAULT)
    parser.add_argument('--pid', default=None)
    parser.add_argument('--ceiling', type=float, default=HOLD_CEILING_S)
    parser.add_argument('--json', default=None)
    parser.add_argument('--pid-latest', action='store_true',
                        help='a sessao que TERMINOU (o ultimo pid que pintou), '
                             'para julgar uma sessao ja\' fechada')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--neg-arm', action='store_true')
    parsed = parser.parse_args(argv)
    if parsed.pid_latest:
        # A SESSAO QUE JA' ACABOU (2026-11-12). O defeito que o dono descreve
        # ("ela travou") termina com um `HANG`/`SHELL_EXIT`, e a sessao NOVA
        # (a que o log sempre devolve) tem zero pinturas -- julgar so' a ultima
        # deixaria o defeito sem numeros. Este modo escolhe o pid com mais
        # pinturas no ficheiro inteiro, que e' a sessao que produziu o defeito.
        best_pid, best_n = None, -1
        for candidate in all_pids(parsed.log):
            session, _ = parse_log(parsed.log, candidate)
            n = len(paints(session))
            if n > best_n:
                best_pid, best_n = candidate, n
        if best_pid:
            parsed.pid = best_pid
    if parsed.selftest:
        return _selftest()
    if parsed.neg_arm:
        return _neg_arm()
    if not os.path.exists(parsed.log):
        print(f'caption-timeline: NO LOG at {parsed.log}')
        return 0
    result = report(parsed.log, parsed.pid, parsed.ceiling)
    if parsed.json:
        payload = {key: value for key, value in result.items() if key != 'lands'}
        with io.open(parsed.json, 'w', encoding='utf-8', newline='') as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=False))
    return 1 if result['verdict'] == 'FAIL' else 0


if __name__ == '__main__':
    sys.exit(main())
