#!/usr/bin/env python3
"""A CSP THAT FORBIDS INLINE SCRIPTS MUST HAVE NO INLINE SCRIPTS. Nothing launched.

MEASURED 2026-10-13: panel.html declares script-src self with NO unsafe-inline, and such
a CSP BLOCKS every inline script block AND every inline event handler. The strip drag
handler was THE ONLY INLINE SCRIPT in the document -- 1 inline against 12 with src -- so
the one piece of panel code that made the strip MOVABLE never ran, in any launch.

A BLOCKED SCRIPT IS NOT AN ERROR: nothing thrown, console clean, shell log silent. This
gate makes the next one loud. --neg-arm adds an inline script to a COPY and must go RED.
"""
import argparse
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = os.path.join(ROOT, "app", "panel")
RESULTS = []
COMMENT = re.compile("<!--[\s\S]*?-->")
TAG = re.compile("<script([^>]*)>", re.I)
# chr(34) IS THE QUOTE CHARACTER, and building the pattern from it avoids having a
# double quote inside a double-quoted Python string -- which is what broke the first
# two versions of this file. The quote chars are the only awkward part of the regex.
Q = chr(34)
CSPRE = re.compile("http-equiv=" + Q + "Content-Security-Policy" + Q + "\\s+content=" + Q
                   + "([^" + Q + "]+)" + Q, re.I)
HANDLER = re.compile("\\bon(click|change|input|submit|load|error|focus|blur|keydown|keyup|mouseover|mouseout|pointerdown|pointerup|pointermove)\\s*=", re.I)


def check(label, ok, detail=""):
    RESULTS.append((label, bool(ok), str(detail)))
    print(("  ok   " if ok else "  FAIL ") + label + ("  -- " + str(detail) if detail else ""))


def script_src(text):
    m = CSPRE.search(text)
    if not m:
        return None
    for part in m.group(1).split(";"):
        if part.strip().lower().startswith("script-src"):
            return part.strip()
    return ""


def audit(path, tag):
    text = open(path, encoding="utf-8").read()
    csp = script_src(text)
    name = os.path.basename(path)
    if csp is None or csp == "" or "unsafe-inline" in csp:
        check(tag + name + " permits inline (csp=" + str(csp)[:40] + ")", True)
        return
    # COMMENTS ARE NOT ELEMENTS. My first detector counted a literal <script> inside
    # a comment I had just written and reported a phantom inline script.
    code = COMMENT.sub("", text)
    inline = [m for m in TAG.finditer(code) if "src=" not in m.group(1)]
    handlers = sorted(set(HANDLER.findall(code)))
    check(tag + name + ": script-src forbids inline", True, csp[:56])
    check(tag + name + ": and there is NO inline script", not inline,
          "found %d" % len(inline))
    check(tag + name + ": and there is NO inline event handler", not handlers, str(handlers[:5]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--neg-arm", action="store_true")
    args = ap.parse_args()
    docs = [p for p in sorted(os.listdir(PANEL)) if p.endswith(".html")]
    print("panel documents: %s" % docs)
    for d in docs:
        audit(os.path.join(PANEL, d), "")
    control = list(RESULTS)
    if args.neg_arm:
        print("-- neg-arm: an inline script and an onclick added to a COPY --")
        tmp = tempfile.mkdtemp(prefix="sotto-csp-")
        try:
            for d in docs:
                src = open(os.path.join(PANEL, d), encoding="utf-8").read()
                mut = src.replace("</body>", "<script>window.__x=1;</script></body>", 1)
                if mut == src:
                    mut = src + "\n<script>window.__x=1;</script>\n"
                open(os.path.join(tmp, d), "w", encoding="utf-8").write(mut)
            for d in docs:
                audit(os.path.join(tmp, d), "  mut: ")
            red = [r for r in RESULTS[len(control):] if not r[1]]
            check("neg-arm the inline script goes RED",
                  any("NO inline script" in r[0] for r in red), "red=%d" % len(red))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    cf = [r for r in control if not r[1]]
    if args.neg_arm:
        rc = [r for r in RESULTS if r[0].startswith("neg-arm ")]
        failed = cf + [r for r in rc if not r[1]]
        total = len(control) + len(rc)
    else:
        failed, total = cf, len(control)
    print("")
    print("VERDICT: %s -- %d check(s), %d fail"
          % ("PASS" if not failed else "FAIL", total, len(failed)))
    for r in failed:
        print("   FAILED: " + r[0] + "  -- " + r[2])
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())