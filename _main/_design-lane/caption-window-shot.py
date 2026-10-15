"""Renderiza caption.html com texto de teste -- para VER o que ele pinta."""
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, "H:/sotto/_main/_design-lane")
import shot

SRC = "H:/sotto/app/panel"
OUT = "I:/cc-tmp/cap"
os.makedirs(OUT, exist_ok=True)

FIXTURE = """
<script>
window.addEventListener("load", function () {
  var S = window.SottoCaption;
  if (!S) { document.title = "NO-API"; return; }
  S.set("Uma vez que voce foi.", "e a linha anterior fica aqui em cima, mais fraca");
  S.credits("TRANSCRIBING MARLOW \u00b7 ON-DEVICE \u00b7 240 MS");
  S.listening(true);
});
</script>
"""

work = tempfile.mkdtemp(prefix="capwin-")
for name in os.listdir(SRC):
    s = os.path.join(SRC, name)
    d = os.path.join(work, name)
    if os.path.isdir(s):
        shutil.copytree(s, d, dirs_exist_ok=True)
    else:
        shutil.copyfile(s, d)

hp = os.path.join(work, "caption.html")
with open(hp, encoding="utf-8") as fh:
    html = fh.read()
html = html.replace("</body>", FIXTURE + "</body>")
with open(hp, "w", encoding="utf-8") as fh:
    fh.write(html)

png = os.path.join(OUT, "caption-window.png")
if os.path.isfile(png):
    os.remove(png)
ok, rc, err = shot.shoot(hp, png, 900, 170, "strip")
print("ok=%s rc=%s bytes=%s" % (ok, rc, os.path.getsize(png) if os.path.isfile(png) else -1))
if err:
    print("stderr: " + err[:200])