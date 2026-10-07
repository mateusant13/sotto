import os, subprocess, tempfile, re

edge = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(edge):
    edge = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'

page = os.path.join(tempfile.mkdtemp(prefix='sotto-mq-'), 'p.html')
with open(page, 'w', encoding='utf-8') as fh:
    fh.write("<!doctype html><body><div id=r></div><script>"
             "document.getElementById('r').textContent = String("
             "matchMedia('(prefers-reduced-motion: reduce)').matches);</script></body>")

ARMS = [
    ('plain', []),
    ('force=0', ['--force-prefers-reduced-motion=0']),
    ('force=no-preference', ['--force-prefers-reduced-motion=no-preference']),
    ('blink-settings', ['--blink-settings=prefersReducedMotion=false']),
    ('headless=old', []),
]
for name, extra in ARMS:
    prof = tempfile.mkdtemp(prefix='sotto-mq-')
    headless = ['--headless=old'] if name == 'headless=old' else ['--headless=new']
    cmd = [edge] + headless + ['--disable-gpu', '--no-first-run', '--user-data-dir=' + prof] + extra + \
          ['--dump-dom', 'file:///' + page.replace('\\', '/')]
    try:
        p = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=90)
    except subprocess.TimeoutExpired:
        print('%-22s TIMEOUT' % name)
        continue
    m = re.search(r'id="r">([^<]*)<', p.stdout or '')
    print('%-22s reduce=%s  rc=%s' % (name, m.group(1) if m else 'NO OUTPUT', p.returncode))
