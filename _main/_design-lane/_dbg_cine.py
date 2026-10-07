import io, re, json, html, os, subprocess, sys, tempfile
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

edge = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(edge):
    edge = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
page = r'H:/sotto/_main/_audit-render/panel-chrome-real.html'
prof = tempfile.mkdtemp(prefix='sotto-dbg4-')
cmd = [edge, '--headless=new', '--disable-gpu', '--no-first-run',
       '--user-data-dir=' + prof, '--virtual-time-budget=30000',
       '--dump-dom', 'file:///' + page + '#mode=chrome']
p = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=240)
t = p.stdout or ''
for mm in re.finditer(r'data-chrome-probe-(\d+)="([^"]*)"', t):
    d = json.loads(html.unescape(mm.group(2)))
    if d['theme'] != 'theme-4':
        continue
    for k in ('headShown', 'headRect', 'headText', 'headDisplay', 'shownHeads',
              'headCount', 'wordmarkShown', 'liveTimeColor', 'pastTimeColor',
              'alphaPanel', 'alphaCaptions', 'alphaBody', 'alphaCaption',
              'headerAppRegion', 'buttonsOffRow', 'levelAttr', 'meterAnimation'):
        print('%-18s %r' % (k, d.get(k)))
    print('buttons:', [(b['id'], b['top'], b['inHeader']) for b in d.get('buttons', [])])
