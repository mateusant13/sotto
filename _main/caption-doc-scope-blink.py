#!/usr/bin/env python3
"""caption-doc-scope-blink -- THE REAL-ENGINE PROOF (2026-10-20).

WHAT IT MEASURES. The CASCADE, in Blink -- the engine WebView2 actually uses --
over the REAL `app/panel/panel.html` and `app/panel/caption.html`, with the REAL
stylesheets, in the REAL order that `panel.html` loads them. Not a text search,
not a re-implementation of the cascade: `getComputedStyle` on the real documents.

WHY IT EXISTS. The defect it holds was invisible to every other instrument, and
the reason is worth keeping: the jsdom harness (`_main/caption-independent-oracle.js`)
inlined `panel.css` and `caption-float.css` and NOT `zip-overlay.css` -- the sheet
that carried the three offending rules -- so the rule was not in the population.
And the static census in that gate SKIPPED any transparent `<html>/<body>` rule
whose selector mentioned `data-caption-window`, which is exactly the rule that
was wrong. Two independent holes, and both of them GREEN.

THE DEFECT, AS MEASURED (before the fix, Blink, real panel.html):

    attr=None   html_bg=rgba(11, 15, 20, 0.98)  body_bg=rgba(11, 15, 20, 0.98)
                 line_shadow=rgba(0, 0, 0, 0.88) 0px 2px 18px, ...
    attr="off"  html_bg=rgba(0, 0, 0, 0)        body_bg=rgba(0, 0, 0, 0)
                 line_shadow=none
    attr="on"   html_bg=rgba(0, 0, 0, 0)        body_bg=rgba(0, 0, 0, 0)
                 line_shadow=none

The shell writes `data-caption-window` on the PANEL document on every LIVE switch
(`sotto_webview.py:8722-8724`, with "on" and with "off"). The three rules that
carry `zip-overlay.css` were scoped to that attribute, so they ALSO matched the
panel: the panel lost its RENDER PROTECTION (`panel.css:105-127`, the
`rgba(11, 15, 20, 0.98)` under `.panel`) and the panel's inline caption lost its
shadow -- the shadow that belongs to the caption that HAS a plate under the words.

THE CONTRACT THIS GATE HOLDS:
  P1 the panel's base is OPAQUE with no attribute at all
  P2 the panel's base is OPAQUE after the shell's "off" write
  P3 the panel's base is OPAQUE after the shell's "on" write
  P4 the panel's inline caption KEEPS its shadow after the "off" write
  P5 with the "on" write, the panel's inline caption is hidden (display:none)
  C1 the caption document's base is TRANSPARENT (no plate, no box, no slab)
  C2 the caption document's line has NO shadow
  C3 the caption document's caption is VISIBLE -- it is never display:none

WHY IT IS OUT OF THE BATTERY: it LAUNCHES a browser. The repo's rule (AGENTS.md
nº 6) is that a gate that judges FILES goes in the battery and a gate that
LAUNCHES stays out -- and says so here. Its negative arm is executed and
recorded in `_main/receipt-20261020-caption-doc-scope.md`. The in-process gate
that guards the same contract on every run is
`_main/caption-independent-oracle.js` (mutants N9 and N10).

Exit codes: 0 PASS | 1 a check failed | 2 setup error (no Edge, a file missing).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, os.pardir))
PANEL = os.path.join(REPO, "app", "panel")
EDGE_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

OPAQUE = "OPAQUE"
TRANSPARENT = "TRANSPARENT"

# THE PROBE IS AN EXTERNAL FILE, not an inline block. `panel.html` declares a CSP
# with `script-src 'self'` and NO `'unsafe-inline'` (panel.html:22-25), so an
# inline <script> is BLOCKED there -- and a blocked script throws nothing and logs
# nothing, which is how it can look like a probe that "did not run".
PROBE_JS = r"""
(function () {
  var out = document.getElementById('probe-out');
  function cs(el, p) { return el ? getComputedStyle(el)[p] : null; }
  function base(v) {
    return (v === 'rgba(0, 0, 0, 0)' || v === 'transparent') ? 'TRANSPARENT' : 'OPAQUE';
  }
  function snap(attr) {
    if (attr === null) document.documentElement.removeAttribute('data-caption-window');
    else document.documentElement.setAttribute('data-caption-window', attr);
    void document.documentElement.offsetHeight;
    var line = document.getElementById('caption-float-line');
    var flt = document.getElementById('caption-float');
    var shadow = line ? cs(line, 'textShadow') : null;
    return {
      attr: attr,
      html_bg: base(cs(document.documentElement, 'backgroundColor')),
      body_bg: base(cs(document.body, 'backgroundColor')),
      shadow: (shadow && shadow !== 'none' && shadow !== 'rgba(0, 0, 0, 0)') ? 'SHADOWED' : 'NONE',
      display: flt ? cs(flt, 'display') : null
    };
  }
  function go() {
    try {
      var o = { states: [] };
      o.states.push(snap(null));
      o.states.push(snap('off'));
      o.states.push(snap('on'));
      o.states.push(snap('1'));
      out.textContent = JSON.stringify(o);
    } catch (e) { out.textContent = JSON.stringify({ error: String(e) }); }
  }
  if (document.readyState === 'complete') go();
  else window.addEventListener('load', go);
})();
"""

ROWS = []


def check(name, real, want):
    ok = real == want
    ROWS.append({"name": name, "ok": ok, "real": real, "want": want})
    return ok


def find_edge():
    for p in EDGE_CANDIDATES:
        if os.path.exists(p):
            return p
    try:
        sys.path.insert(0, os.path.join(HERE, "_design-lane"))
        import shot  # noqa: PLC0415
        if os.path.exists(shot.EDGE):
            return shot.EDGE
    except Exception:  # noqa: BLE001
        pass
    return None


def measure(edge, panel_dir):
    """One Edge launch per document; every attribute state is read in that one load.

    THE PROBE NEVER TOUCHES THE PRODUCT. It patches a COPY, in BYTES, and it
    restores what it patched in bytes too. (The first version of this gate read
    the files in TEXT mode and wrote them back in text mode: Python's universal
    newlines turned `app/panel/caption.html` -- which is LF, per
    `.gitattributes:503` -- into CRLF. A gate that rewrites the files it
    measures is a gate that corrupts the product, so it works on a copy and the
    copy is thrown away.)
    """
    out = {}
    work = os.path.join(panel_dir, "__probe.js")
    with open(work, "w", encoding="utf-8", newline="\n") as h:
        h.write(PROBE_JS)
    try:
        for page in ("panel.html", "caption.html"):
            hp = os.path.join(panel_dir, page)
            with open(hp, "rb") as h:
                original = h.read()
            patched = original.replace(
                b"</body>",
                b'<pre id="probe-out" style="display:none">PROBE-NOT-RUN</pre>'
                b'<script src="__probe.js"></script></body>')
            if patched == original:
                return None, "no </body> to patch in %s" % page
            with open(hp, "wb") as h:
                h.write(patched)
            url = "file:///" + hp.replace(os.sep, "/")
            cmd = [edge, "--headless=new", "--disable-gpu", "--no-first-run",
                   "--no-default-browser-check", "--force-device-scale-factor=1",
                   "--virtual-time-budget=8000", "--window-size=900,900",
                   "--dump-dom", url]
            try:
                p = subprocess.run(cmd, capture_output=True, timeout=180)
            except subprocess.TimeoutExpired:
                return None, "Edge timed out on %s" % page
            dom = (p.stdout or b"").decode("utf-8", "replace")
            m = re.search(r'<pre id="probe-out"[^>]*>(.*?)</pre>', dom, re.S)
            if not m:
                return None, "no probe output for %s" % page
            raw = (m.group(1).replace("&quot;", '"').replace("&amp;", "&")
                   .replace("&lt;", "<").replace("&gt;", ">"))
            try:
                out[page] = json.loads(raw)
            except ValueError:
                return None, "unreadable probe output for %s: %r" % (page, raw[:200])
            # restore the file byte-for-byte
            with open(hp, "wb") as h:
                h.write(original)
    finally:
        try:
            os.remove(work)
        except OSError:
            pass
    return out, None


def state(out, page, attr):
    for s in out[page]["states"]:
        if s["attr"] == attr:
            return s
    return None


def run_checks(panel_dir):
    """`panel_dir` is ALWAYS a disposable copy. The product is never patched."""
    ROWS.clear()
    edge = find_edge()
    if not edge:
        return None, "no Edge binary found"
    tmp = os.environ.get("TMPDIR") or tempfile.gettempdir()
    if not os.path.isdir(tmp):
        tmp = tempfile.gettempdir()
    scratch = tempfile.mkdtemp(prefix="sotto-caption-doc-", dir=tmp)
    try:
        copy_panel(panel_dir, scratch)
        out, err = measure(edge, scratch)
        if err:
            return None, err
        if "error" in out.get("panel.html", {}):
            return None, "probe failed: %s" % out["panel.html"]["error"]

        p_none = state(out, "panel.html", None)
        p_off = state(out, "panel.html", "off")
        p_on = state(out, "panel.html", "on")
        c_none = state(out, "caption.html", None)
        c_one = state(out, "caption.html", "1")

        check("P1 the panel's base is OPAQUE with no attribute at all",
              [p_none["html_bg"], p_none["body_bg"]], [OPAQUE, OPAQUE])
        check("P2 the panel's base SURVIVES the shell's \"off\" write",
              [p_off["html_bg"], p_off["body_bg"]], [OPAQUE, OPAQUE])
        check("P3 the panel's base SURVIVES the shell's \"on\" write",
              [p_on["html_bg"], p_on["body_bg"]], [OPAQUE, OPAQUE])
        check("P4 the panel's inline caption KEEPS its shadow after the \"off\" write",
              p_off["shadow"], "SHADOWED")
        check("P5 with the \"on\" write the panel's inline caption is hidden",
              p_on["display"], "none")
        check("C1 the caption document's base is TRANSPARENT (no plate, no box)",
              [c_one["html_bg"], c_one["body_bg"]], [TRANSPARENT, TRANSPARENT])
        check("C2 the caption document's line has NO shadow",
              c_one["shadow"], "NONE")
        check("C3 the caption document's caption is VISIBLE (never display:none)",
              c_one["display"] not in (None, "none"), True)
        check("C4 and the caption document's base is transparent even without the attribute",
              [c_none["html_bg"], c_none["body_bg"]], [TRANSPARENT, TRANSPARENT])
        return ROWS, None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def report(label):
    bad = 0
    print("")
    print("CAPTION DOC SCOPE -- BLINK (the real cascade) -- " + label)
    for r in ROWS:
        if not r["ok"]:
            bad += 1
            print("  [FAIL] %s\n         real=%r want=%r" % (r["name"], r["real"], r["want"]))
    print("%d check(s), %d failed" % (len(ROWS), bad))
    print("VERDICT: " + ("PASS" if bad == 0 else "FAIL"))
    return bad


def copy_panel(src, dest):
    shutil.copytree(src, dest, dirs_exist_ok=True)


def neg_arm():
    """The PRE-FIX bytes, exactly. The gate has to go RED on them."""
    tmp = os.environ.get("TMPDIR") or tempfile.gettempdir()
    if not os.path.isdir(tmp):
        tmp = tempfile.gettempdir()
    scratch = tempfile.mkdtemp(prefix="sotto-caption-doc-neg-", dir=tmp)
    try:
        copy_panel(PANEL, scratch)
        css_path = os.path.join(scratch, "zip-overlay.css")
        with open(css_path, "rb") as h:
            before = h.read()
        after = (before
                 .replace(b'html[data-caption-window="on"]:not([data-caption-doc]) #caption-float',
                          b'html[data-caption-window="on"] #caption-float')
                 .replace(b'html[data-caption-doc]', b'html[data-caption-window]'))
        if after == before:
            print("SETUP ERROR: mutant anchor absent in zip-overlay.css")
            return 2
        with open(css_path, "wb") as h:
            h.write(after)
        rows, err = run_checks(scratch)
        if err:
            print("SETUP ERROR: " + err)
            return 2
        bad = [r for r in rows if not r["ok"]]
        red = len(bad) > 0
        print("  " + ("RED  " if red else "GREEN")
              + "  M1 the caption-window rules go back to the attribute the shell"
                " writes on the PANEL -> %d failing check(s)" % len(bad))
        for r in bad:
            print("         " + r["name"])
        print("")
        print("NEG-ARM VERDICT: " + ("PASS -- the mutant went RED."
                                      if red else "FAIL -- the mutant stayed GREEN."))
        return 0 if red else 1
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main() -> int:
    neg = "--neg-arm" in sys.argv
    if neg:
        return neg_arm()
    rows, err = run_checks(PANEL)
    if err:
        print("SETUP ERROR: " + err)
        return 2
    bad = report("PRISTINE (the shipped bytes)")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
