
import os, sys, json, shutil, tempfile, subprocess, re
os.environ.setdefault('TMPDIR','I:/cc-tmp')
sys.path.insert(0, "H:/sotto/_main/_design-lane")
import shot
EDGE = shot.EDGE
SRC = "H:/sotto/app/panel"
work = tempfile.mkdtemp(prefix="capm2-")
for name in os.listdir(SRC):
    s = os.path.join(SRC, name); d = os.path.join(work, name)
    if os.path.isdir(s): shutil.copytree(s, d, dirs_exist_ok=True)
    else: shutil.copyfile(s, d)
PROBE = """
<pre id="probe-out" style="display:none"></pre>
<script>
window.addEventListener('load', function () {
  var S = window.SottoCaption;
  if (S) { S.set('A segunda linha desta legenda tem de comecar na esquerda.', 'E esta e a linha anterior, por cima e mais fraca.'); S.credits('TRANSCRIBING MARLOW'); S.listening(true); }
  function cs(el,p){ return el?getComputedStyle(el)[p]:null; }
  function rect(el){ if(!el) return null; var r=el.getBoundingClientRect(); return {x:+r.x.toFixed(1),y:+r.y.toFixed(1),w:+r.width.toFixed(1),h:+r.height.toFixed(1)}; }
  var o = { vp:{w:innerWidth,h:innerHeight} };
  o.html={bg:cs(document.documentElement,'backgroundColor')};
  o.body={bg:cs(document.body,'backgroundColor')};
  var col=document.querySelector('.caption-float__col'), line=document.getElementById('caption-float-line'), prev=document.getElementById('caption-float-prev');
  o.align={col:cs(col,'textAlign'),line:cs(line,'textAlign'),prev:cs(prev,'textAlign')};
  o.alignItems={col:cs(col,'alignItems')};
  o.rects={col:rect(col),line:rect(line)};
  var painted=[];
  document.querySelectorAll('*').forEach(function(e){
    var b=getComputedStyle(e).backgroundColor, bi=getComputedStyle(e).backgroundImage;
    var hasB=b&&b!=='rgba(0, 0, 0, 0)'&&b!=='transparent';
    var hasI=bi&&bi!=='none';
    if(hasB||hasI){ painted.push({t:e.tagName,c:(e.className&&e.className.toString)?e.className.toString().slice(0,34):'',bg:b,img:hasI?bi.slice(0,40):null}); }
  });
  o.painted=painted.slice(0,10); o.paintedCount=painted.length;
  document.getElementById('probe-out').textContent=JSON.stringify(o);
});
</script>
"""
hp = os.path.join(work,"caption.html")
with open(hp,encoding="utf-8") as fh: html=fh.read()
html = html.replace("</body>", PROBE+"</body>")
with open(hp,"w",encoding="utf-8") as fh: fh.write(html)
url="file:///"+hp.replace(os.sep,"/")
cmd=[EDGE,"--headless=new","--disable-gpu","--no-first-run","--no-default-browser-check","--force-device-scale-factor=1","--virtual-time-budget=6000","--window-size=900,170","--dump-dom",url]
p=subprocess.run(cmd,capture_output=True,timeout=180)
dom=(p.stdout or b"").decode("utf-8","replace")
m=re.search(r'<pre id="probe-out"[^>]*>(.*?)</pre>',dom,re.S)
if not m:
    print("SEM SAIDA rc=%s" % p.returncode); print((p.stderr or b'').decode('utf-8','replace')[:300])
else:
    raw=m.group(1).replace('&quot;','"').replace('&amp;','&').replace('&lt;','<').replace('&gt;','>')
    print(json.dumps(json.loads(raw), indent=1)[:2500])
