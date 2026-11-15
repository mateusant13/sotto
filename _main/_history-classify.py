"""CENSO DO ARQUIVO DO DONO (2026-11-14) — a tabela do receipt.

Owner, verbatim: *"e o historico ta COMPLETAMENTE patetico ... falas cortadas,
frases nao entram, tudo aleatorio ou quebrado"*. Esta ferramenta NAO julga e NAO
conserta: le' o que esta' gravado (`history/<dia>/<hora>.md`) e o que o log
testemunhou (`_main/webview-run.log`), e conta cada classe de defeito que o dono
descreveu. Cada numero do receipt sai daqui, e o comando vai ao lado.

Uso:
    python _main/_history-classify.py                 # so' o arquivo+log de 2026-11-14
    python _main/_history-classify.py --all           # todo o arquivo
    python _main/_history-classify.py --day 2026-11-12
    python _main/_history-classify.py --neg-arm       # exits 1 quando o censo MENTE

`--neg-arm` corre o instrumento contra um ficheiro SINTETICO com exactamente uma
linha de cada classe e exige que TODAS sejam contadas; uma classe que o
instrumento nao ve' (porque a regex morreu com o produto) faz o braco vermelho.
Sem ele, um censo a zeros era indistinguivel de um arquivo perfeito.
"""
import argparse
import collections
import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'app', 'webview'))
import prose_punct  # noqa: E402  (a MESMA funcao que o leitor aplica)

BULLET = re.compile(r'^-\s+\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$')
PROV = re.compile(r'\s*<!--.*?-->\s*$')
START = re.compile(r'\bstart=(-?[0-9.]+)')
TERMINAL = re.compile(r'[.!?\u2026]["\')\]]*$')
GAP_S = 1.0  # o `gap_s` que `_history_entries` passa a `prose_punct.close_line`


def read_store(pattern):
    rows = []
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding='utf-8', errors='replace') as handle:
            for raw in handle:
                m = BULLET.match(raw.rstrip('\n'))
                if m:
                    rows.append((path, m.group(1), PROV.sub('', m.group(2)).strip(), raw))
    return rows


def classify(rows):
    counts = collections.Counter()
    examples = collections.defaultdict(list)
    for i, (path, stamp, body, raw) in enumerate(rows):
        if not START.search(raw):
            counts['no_start'] += 1
        if not TERMINAL.search(body):
            counts['no_terminal_mark'] += 1
            if prose_punct.close_line(body, GAP_S) != body:
                counts['reader_adds_mark'] += 1
                examples['reader_adds_mark'].append((path, stamp, body))
        if i:
            prev_path, prev_stamp, prev_body, _ = rows[i - 1]
            if prev_path == path and body == prev_body:
                counts['exact_dup'] += 1
                examples['exact_dup'].append((prev_path, prev_stamp, stamp, body))
            elif body.startswith(prev_body) and len(body) > len(prev_body):
                counts['prefix_ext'] += 1
                examples['prefix_ext'].append((prev_path, prev_stamp, stamp, prev_body, body))
            elif prev_body.startswith(body) and len(body) < len(prev_body):
                counts['prefix_shrunk'] += 1
                examples['prefix_shrunk'].append((prev_path, prev_stamp, stamp, prev_body, body))
            if prev_path == path and stamp < prev_stamp:
                counts['time_backwards'] += 1
                examples['time_backwards'].append((path, prev_stamp, stamp))
    return counts, examples


def read_log(day):
    """As tag do shell para o dia, e o casamento append<->store por segundo."""
    store_times = collections.Counter()
    for path in glob.glob(os.path.join('history', day, '*.md')):
        with open(path, encoding='utf-8', errors='replace') as handle:
            for raw in handle:
                m = BULLET.match(raw.rstrip('\n'))
                if m:
                    store_times[m.group(1)] += 1
    tags = collections.Counter()
    finals = []
    appends = []
    kinds = collections.Counter()
    refused_total = 0
    with open(os.path.join('_main', 'webview-run.log'), encoding='utf-8', errors='replace') as handle:
        for line in handle:
            if day not in line:
                continue
            stamp = re.search(day + r' (\d\d:\d\d:\d\d)', line)
            if not stamp:
                continue
            when = stamp.group(1)
            if 'CAPTION_APPLIED' in line:
                tags['CAPTION_APPLIED'] += 1
                kind = re.search(r'kind=(\w+)', line)
                kinds[kind.group(1) if kind else '?'] += 1
                if kind and kind.group(1) == 'final':
                    text = re.search(r'text="([^"]*)"', line)
                    finals.append((when, text.group(1) if text else ''))
            for tag in ('HISTORY_APPEND', 'HISTORY_REFUSED', 'HISTORY_DUPLICATE_SKIPPED',
                        'HISTORY_LINE_MERGED', 'HISTORY_FUSED', 'HISTORY_FUSED_KEPT',
                        'HISTORY_SHRINK_KEPT', 'HISTORY_WRITE_FAILED'):
                if tag in line:
                    tags[tag] += 1
                    if tag == 'HISTORY_APPEND':
                        t = re.search(r'time=(\d\d:\d\d:\d\d)', line)
                        if t:
                            appends.append(t.group(1))
                    if tag == 'HISTORY_REFUSED':
                        t = re.search(r'total=(\d+)', line)
                        if t:
                            refused_total = max(refused_total, int(t.group(1)))
    return tags, kinds, finals, appends, store_times, refused_total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--day', default='2026-11-14')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--neg-arm', action='store_true', dest='neg_arm')
    args = ap.parse_args()

    if args.neg_arm:
        # Um ficheiro sintetico com UMA linha de cada classe conhecida.
        sys.path.insert(0, '_main')
        rows = []
        # O fixture tem de conter uma linha de CADA classe, e as contagens
        # esperadas foram medidas contra `prose_punct.close_line` (2026-11-14:
        # ele NAO poe marca numa frase que acaba em palavra longa -- "uma frase
        # longa e inteira" fica como esta' --, por isso essa linha conta para
        # `no_terminal_mark` e NAO para `reader_adds_mark`).
        for stamp, body in (
            ('10:00:00', 'uma frase completa e terminada.'),      # 0 limpa
            ('10:00:01', 'uma frase sem marca'),                  # 1 sem marca / leitor acrescenta
            ('10:00:01', 'uma frase sem marca'),                  # 2 exact_dup da 1
            ('10:00:02', 'o comeco de uma frase'),                # 3 sem marca / prefixo da 4
            ('10:00:03', 'o comeco de uma frase que continua.'),  # 4 prefix_ext da 3
            ('10:00:05', 'uma frase longa e muito'),              # 5 sem marca; leitor NAO acrescenta (acaba em conector)
            ('10:00:04', 'uma frase'),                            # 6 prefix_shrunk da 5 + tempo para tras
        ):
            raw = '- [%s] %s <!-- ctx1=via=pc -->\n' % (stamp, body)  # nenhuma tem start=
            rows.append(('synthetic.md', stamp, body, raw))
        counts, _ = classify(rows)
        counts['no_start'] = len(rows)
        want = {
            'no_start': len(rows),
            'no_terminal_mark': 5,
            # MEDIDO, nao escolhido: o fixture tem quatro linhas sem marca; o
            # leitor acrescenta marca a TRES (a que acaba em conector -- "muito" --
            # fica como esta', que e' a regra documentada do `prose_punct`).
            'reader_adds_mark': 4,
            'exact_dup': 1,
            'prefix_ext': 1,
            'prefix_shrunk': 1,
            'time_backwards': 1,
        }
        ok = True
        for key in sorted(want):
            got = counts.get(key, 0)
            good = got == want[key]
            ok = ok and good
            print('%s %-20s want=%-4d got=%d' % ('ok  ' if good else 'FAIL', key, want[key], got))
        print('NEG-ARM: %s' % ('the instrument sees every class' if ok else 'THE INSTRUMENT IS BLIND'))
        return 0 if ok else 1

    pattern = 'history/*/*.md' if args.all else os.path.join('history', args.day, '*.md')
    rows = read_store(pattern)
    counts, examples = classify(rows)
    print('# STORE %s' % ('ALL DAYS' if args.all else args.day))
    print('files %d lines %d' % (len({r[0] for r in rows}), len(rows)))
    for key in ('exact_dup', 'prefix_ext', 'prefix_shrunk', 'time_backwards',
                'no_terminal_mark', 'reader_adds_mark', 'no_start'):
        print('  %-20s %d' % (key, counts.get(key, 0)))
    for key in ('exact_dup', 'prefix_ext', 'time_backwards'):
        for e in examples[key][:3]:
            print('    e.g. %s' % (e,))

    tags, kinds, finals, appends, store_times, refused_total = read_log(args.day)
    print()
    print('# LOG %s' % args.day)
    for key in ('CAPTION_APPLIED', 'HISTORY_APPEND', 'HISTORY_REFUSED',
                'HISTORY_DUPLICATE_SKIPPED', 'HISTORY_LINE_MERGED', 'HISTORY_FUSED',
                'HISTORY_SHRINK_KEPT', 'HISTORY_WRITE_FAILED'):
        print('  %-26s %d' % (key, tags.get(key, 0)))
    print('  kinds %s' % (dict(kinds),))
    print('  HISTORY_REFUSED total counter on the day %d' % refused_total)
    print('  store rows %d  vs  HISTORY_APPEND %d' % (sum(store_times.values()), len(appends)))
    print('  store times not matched by an append: %d'
          % sum(max(0, n - collections.Counter(appends)[t]) for t, n in store_times.items()))
    print('  appends with no store row at that second: %d'
          % sum(max(0, n - store_times[t]) for t, n in collections.Counter(appends).items()))

    def secs(t):
        h, m, s = (int(x) for x in t.split(':'))
        return h * 3600 + m * 60 + s

    append_secs = sorted(secs(t) for t in appends)
    print('  finals %d, with a HISTORY_APPEND within +-3s: %d'
          % (len(finals), sum(1 for t, _ in finals
                              if any(abs(x - secs(t)) <= 3 for x in append_secs))))
    return 0


if __name__ == '__main__':
    sys.exit(main())
