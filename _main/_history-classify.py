"""Classify every line in the owner's history store, and the log window.

Read-only. Prints the counts the receipt cites. Not an oracle: a census.
Run: python _main/_history-classify.py
"""
import os
import re
import sys
import glob
import collections

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'history')
LINE_RE = re.compile(r'^-\s+\[(\d{2}:\d{2}:\d{2})\]\s+(.*)$')
TAIL_RE = re.compile(r'\s*<!--.*?-->\s*$')
START_RE = re.compile(r'\bstart=([-0-9.]+)')
VIA_RE = re.compile(r'\bvia=(pc|youtube|external)\b')
SRC_RE = re.compile(r'\bsrc=(\S+)')
REASON_RE = re.compile(r'\breason=([^>]*)')


def merge_key(text):
    return re.sub(r'[\s.!?\u2026,;:]+$', '', str(text or ''))


def load(path):
    rows = []
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        for raw in fh:
            m = LINE_RE.match(raw.rstrip('\n'))
            if not m:
                continue
            body = TAIL_RE.sub('', m.group(2)).strip()
            st = START_RE.search(raw)
            vi = VIA_RE.search(raw)
            rows.append({
                'time': m.group(1),
                'text': body,
                'start': float(st.group(1)) if st else None,
                'via': vi.group(1) if vi else '',
                'raw': raw.rstrip('\n'),
            })
    return rows


def main():
    files = sorted(glob.glob(os.path.join(ROOT, '2026-11-1*', '*.md')))
    counts = collections.Counter()
    per_file = []
    examples = collections.defaultdict(list)
    total = 0
    for path in files:
        rows = load(path)
        total += len(rows)
        local = collections.Counter()
        prev = None
        for i, row in enumerate(rows):
            t = row['text']
            if prev is not None:
                p = prev['text']
                if t == p:
                    local['exact_dup'] += 1
                    examples['exact_dup'].append((path, row['time'], t[:70]))
                elif merge_key(t) and merge_key(p) and merge_key(t).startswith(merge_key(p)):
                    local['prefix_ext'] += 1
                    examples['prefix_ext'].append((path, row['time'], p[-40:], t[-40:]))
                elif merge_key(t) and merge_key(p) and merge_key(p).startswith(merge_key(t)):
                    local['prefix_shrunk'] += 1
                    examples['prefix_shrunk'].append((path, row['time'], p[-50:], t[-50:]))
                elif row['start'] is not None and prev['start'] is not None \
                        and abs(row['start'] - prev['start']) < 0.05 and t != p:
                    local['same_start_diff_text'] += 1
                    examples['same_start_diff_text'].append((path, row['time'], row['start']))
                elif row['time'] < prev['time']:
                    local['time_went_backwards'] += 1
                    examples['time_went_backwards'].append((path, prev['time'], row['time']))
            # mid-word / dangling fragment: ends in a cut word (no terminal mark,
            # and the last word is a 1-3 letter stump or the line ends with a
            # coordinating word that cannot end a sentence)
            stripped = t.rstrip()
            if stripped and not re.search(r'[.!?\u2026]"?$', stripped):
                local['no_terminal_mark'] += 1
            words = stripped.split()
            if words:
                last = words[-1].lower().strip('.,!?;:"\u2026')
                if last in {'a', 'o', 'e', 'de', 'da', 'do', 'que', 'no', 'na', 'um',
                            'uma', 'pra', 'para', 'com', 'por', 'se', 'the', 'to',
                            'of', 'and', 'a', 'in', 'is', 'you', 'i', 'my'}:
                    local['ends_on_function_word'] += 1
                    examples['ends_on_function_word'].append((path, row['time'], stripped[-60:]))
            prev = row
        per_file.append((os.path.relpath(path, ROOT), len(rows), dict(local)))
        counts.update(local)

    print('FILES: %d   LINES: %d' % (len(files), total))
    print()
    print('%-26s %s' % ('CLASS', 'COUNT'))
    for k in ('exact_dup', 'prefix_ext', 'prefix_shrunk', 'same_start_diff_text',
              'time_went_backwards', 'no_terminal_mark', 'ends_on_function_word'):
        print('%-26s %d' % (k, counts[k]))
    print()
    for name, n, local in per_file:
        if n:
            print('%-24s lines=%3d %s' % (name, n, local))
    print()
    for k in ('exact_dup', 'prefix_shrunk', 'time_went_backwards', 'same_start_diff_text'):
        for ex in examples[k][:6]:
            print('%-18s %s' % (k, ex))


if __name__ == '__main__':
    main()
