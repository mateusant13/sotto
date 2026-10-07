import os, re, subprocess, sys, tempfile, threading, time, urllib.request
sys.path.insert(0, r'H:\sotto\_main')
from http.server import HTTPServer
import importlib.util

spec = importlib.util.spec_from_file_location('costarm', r'H:\sotto\_main\_panel-anim-cost-arm.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

srv = HTTPServer(('127.0.0.1', 0), mod.Beacon)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
print('port', port)

page = mod.build_copy('dbg')
print('page', page)

for path in ('/arm/panel-cost-dbg.html', '/panel/panel.css', '/arm/stub.js', '/probe/_panel-anim-cost.js'):
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d%s' % (port, path), timeout=10) as r:
            body = r.read()
        print('%-40s %s %d bytes' % (path, r.status, len(body)))
    except Exception as e:
        print('%-40s FAILED %s' % (path, e))

edge = mod.find_browser('edge')
prof = tempfile.mkdtemp(prefix='sotto-cost-dbg-')
url = ('http://127.0.0.1:%d/arm/panel-cost-dbg.html#mode=cost&theme=theme-5&arm=on&port=%d&seconds=1&rate=8'
       % (port, port))
cmd = [edge, '--headless=new', '--disable-gpu', '--no-first-run',
       '--user-data-dir=' + prof, '--virtual-time-budget=12000', '--dump-dom', url]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     encoding='utf-8', errors='replace')
out, errs = p.communicate(timeout=200)
print('dom bytes', len(out or ''))
m = re.search(r'<title>(.*?)</title>', out or '', re.S)
print('TITLE:', (m.group(1)[:600] if m else 'NO TITLE'))
print('beacon payload:', (mod.Beacon.payload or {}).get('arm'))
print('ERR:', (errs or '')[:400])
srv.shutdown()
