import io, re, html, json, os, subprocess, sys, tempfile

edge = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(edge):
    edge = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'

page = r'H:/sotto/_main/_audit-render/panel-chrome-real.html'
prof = tempfile.mkdtemp(prefix='sotto-dbg-')
cmd = [edge, '--headless=new', '--disable-gpu', '--no-first-run',
       '--user-data-dir=' + prof, '--virtual-time-budget=30000',
       '--dump-dom', 'file:///' + page + '#mode=chrome']
p = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='replace', timeout=240)
t = p.stdout or ''
print('dom bytes', len(t), 'rc', p.returncode)
m = re.search(r'id="caption-list"[^>]*>(.*?)</ol>', t, re.S)
print('CAPTION LIST:')
print((m.group(1)[:3000] if m else 'NONE'))
for mm in re.finditer(r'data-chrome-probe-(\d+)="([^"]*)"', t):
    d = json.loads(html.unescape(mm.group(2)))
    print(d['theme'], 'index', d['indexShown'], d['indexText'], 'committed', d['committedIndex'],
          'forming', d['formingIndex'], 'wordCount', d['wordCount'])
