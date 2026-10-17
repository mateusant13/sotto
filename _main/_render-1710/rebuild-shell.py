"""Rebuild app/webview/sotto_webview.py from HEAD's blob bytes + the ONE intended
change, so the file's mixed line endings (HEAD: 11198 CRLF + 139 bare LF) survive
byte for byte.  `core.autocrlf=true` makes any tool that rewrites the file turn those
139 bare LF into CRLF, and `git diff` then reports the whole file as changed.
"""
import subprocess

REPO = r'H:\sotto'
PATH = 'app/webview/sotto_webview.py'

head = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:' + PATH],
                      capture_output=True, check=True).stdout

OLD = b"    y = work['y'] + round((h - panel_height) / 2)\r\n"
NEW = (
    b"    # TOP-DOCKED, NOT VERTICALLY CENTRED (owner, 2026-10-17: *\"o painel de baixo\r\n"
    b"    # esta muito embaixo, tem que ser mais pra cima\"*). The old line was\r\n"
    b"    #     y = work['y'] + round((h - panel_height) / 2)\r\n"
    b"    # which, with `panel_height = min(900, h - 2*m)`, left the panel's top edge\r\n"
    b"    # half a screen below the top of the work area -- which is what the owner\r\n"
    b"    # means by \"too low\".\r\n"
    b"    #\r\n"
    b"    # THE NEW FORMULA, exactly:  y = work['y'] + m\r\n"
    b"    # -- the SAME `m` the right edge already uses (`max(0, min(margin, w/8, h/8))`,\r\n"
    b"    # :1008), so the panel hangs PANEL_MARGIN (12) from the top and from the right\r\n"
    b"    # and nothing else about the width changes. Containment is arithmetic, not a\r\n"
    b"    # hope: `panel_height` is clamped to `h - 2*m` (:1011), so\r\n"
    b"    # `work['y'] + m + panel_height <= work['y'] + h - m`, and both clamps below\r\n"
    b"    # (`max(work['y'], ...)`, then `min(..., work['y'] + h - height)`) still run, so\r\n"
    b"    # a short or offset monitor can never push the panel out of its work area.\r\n"
    b"    y = work['y'] + m\r\n"
)

assert head.count(OLD) == 1, head.count(OLD)
out = head.replace(OLD, NEW, 1)

with open(REPO + '\\' + PATH.replace('/', '\\'), 'wb') as fh:
    fh.write(out)

crlf = out.count(b'\r\n')
print('rebuilt: bytes=%d CRLF=%d BARE_LF=%d (HEAD was %d/%d)'
      % (len(out), crlf, out.count(b'\n') - crlf,
         head.count(b'\r\n'), head.count(b'\n') - head.count(b'\r\n')))