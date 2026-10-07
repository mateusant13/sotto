import os, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer

HITS = []


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        HITS.append(self.path[:120])
        self.send_response(204)
        self.end_headers()

    def log_message(self, *a):
        pass


srv = HTTPServer(('127.0.0.1', 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()

page = os.path.join(tempfile.mkdtemp(prefix='beacon-'), 'p.html')
with open(page, 'w', encoding='utf-8') as fh:
    fh.write("""<!doctype html><html><head>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self' 'unsafe-inline'; img-src 'self' data:;">
<title>t</title></head><body><div id=r>start</div><script>
var img = new Image();
img.src = 'http://127.0.0.1:PORT/report?payload=' + encodeURIComponent(JSON.stringify({hello:'world'}));
img.onload = function(){ document.getElementById('r').textContent = 'IMG-OK'; };
img.onerror = function(){ document.getElementById('r').textContent = 'IMG-ERR'; };
fetch('http://127.0.0.1:PORT/report2?payload=x').then(function(){document.getElementById('r').textContent += ' FETCH-OK';})
  .catch(function(e){document.getElementById('r').textContent += ' FETCH-ERR:'+e.message;});
</script></body></html>""".replace('PORT', str(port)))

# Serve the page from the same origin, so 'self' covers the beacon.
with open(page, encoding='utf-8') as fh:
    HTML = fh.read()

edge = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(edge):
    edge = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'

prof = tempfile.mkdtemp(prefix='beacon-prof-')
url = 'file:///' + page.replace('\\', '/')
cmd = [edge, '--headless=new', '--disable-gpu', '--no-first-run',
       '--user-data-dir=' + prof, '--virtual-time-budget=6000', '--dump-dom', url]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     encoding='utf-8', errors='replace')
out, errs = p.communicate(timeout=120)
print('HITS from file:// page:', HITS)
import re
m = re.search(r'id="r">([^<]*)<', out or '')
print('page said:', m.group(1) if m else 'NO OUTPUT')
HITS.clear()

# now serve over http
class P(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/report'):
            HITS.append(self.path[:120])
            self.send_response(204); self.end_headers(); return
        body = HTML.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


srv2 = HTTPServer(('127.0.0.1', 0), P)
port2 = srv2.server_address[1]
threading.Thread(target=srv2.serve_forever, daemon=True).start()
HTML = HTML.replace(str(port), str(port2))
prof = tempfile.mkdtemp(prefix='beacon-prof-')
cmd = [edge, '--headless=new', '--disable-gpu', '--no-first-run',
       '--user-data-dir=' + prof, '--virtual-time-budget=6000', '--dump-dom',
       'http://127.0.0.1:%d/p.html' % port2]
p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     encoding='utf-8', errors='replace')
out, errs = p.communicate(timeout=120)
print('HITS from http page:', HITS)
m = re.search(r'id="r">([^<]*)<', out or '')
print('page said:', m.group(1) if m else 'NO OUTPUT')
