import json, difflib, re

def redux_text(f):
    for line in open(f, encoding='utf-8'):
        o = json.loads(line)
        if o.get('type') == 'result':
            return o['text']

def nemo_text(f):
    for line in open(f, encoding='utf-8'):
        o = json.loads(line)
        if o.get('type') == 'status' and o.get('state') == 'selftest-done':
            return o['text']

def norm(s):
    s = s.lower()
    s = re.sub(r'[^\w\s]', '', s)
    return s.split()

for name, rf, nf in [('pt-BR', '_main/replay-redux-ptbr.txt', '_main/replay-nemotron-ptbr.txt'),
                     ('EN', '_main/replay-redux-en.txt', '_main/replay-nemotron-en.txt')]:
    r = redux_text(rf); n = nemo_text(nf)
    print('=' * 30, name)
    print('REDUX   :', r)
    print('NEMOTRON:', n)
    rw, nw = norm(r), norm(n)
    sm = difflib.SequenceMatcher(None, rw, nw)
    sub = ins = dele = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'replace':
            sub += max(i2 - i1, j2 - j1)
            print('  SUBST redux[%s] -> nemo[%s]' % (' '.join(rw[i1:i2]), ' '.join(nw[j1:j2])))
        elif tag == 'delete':
            dele += i2 - i1
            print('  DELETED from nemo (redux-only): %s' % ' '.join(rw[i1:i2]))
        elif tag == 'insert':
            ins += j2 - j1
            print('  INSERTED by nemo (redux lacks): %s' % ' '.join(nw[j1:j2]))
    wer = (sub + ins + dele) / max(len(rw), 1)
    print('  ref_words=%d hyp_words=%d edits(S=%d I=%d D=%d) WER-vs-redux=%.1f%%'
          % (len(rw), len(nw), sub, ins, dele, 100 * wer))
