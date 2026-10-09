import json

for f in ['_main/replay-nemotron-en.txt', '_main/replay-redux-en.txt',
          '_main/replay-nemotron-ptbr.txt', '_main/replay-redux-ptbr.txt']:
    print('=' * 20, f)
    n = 0
    for line in open(f, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            print(line[:200])
            continue
        if o.get('type') == 'caption' and o.get('final', True):
            n += 1
            print('FINAL [%s-%s]: %s' % (o.get('start'), o.get('end'), o.get('text')))
        if o.get('type') == 'status' and o.get('state') == 'selftest-done':
            print('SELFTEST-DONE: %s' % o.get('text'))
        if o.get('type') == 'result':
            print('RESULT: %s' % o.get('text'))
    print('finals:', n)
