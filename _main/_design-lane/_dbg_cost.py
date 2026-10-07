import os, re, subprocess, sys, tempfile

edge = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(edge):
    edge = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'

page = r'H:/sotto/_main/_audit-render/panel-cost-on.html'
prof = tempfile.mkdtemp(prefix='sotto-cost-dbg-')
url = ('file:///' + page + '#mode=cost&theme=theme-5&arm=on&port=9&seconds=1&rate=8')
# A port of 9 is not listening, so the beacon must fail; the title is the copy.
cmd = [edge, '--headless=new', '--disable-gpu', '--no-first-run',
       '--user-data-dir=' + prof, '--virtual-time-budget=12000', '--dump-dom', url]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     encoding='utf-8', errors='replace')
out, errs = p.communicate(timeout=180)
print('dom bytes', len(out or ''), 'rc', p.returncode)
m = re.search(r'<title>(.*?)</title>', out or '', re.S)
print('TITLE:', (m.group(1)[:1200] if m else 'NO TITLE'))
print('ERR:', (errs or '')[:600])
