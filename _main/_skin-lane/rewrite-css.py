"""Rewrite the vendor's compiled CSS for a Shadow DOM host, and NOTHING else.

A shadow root has no `html`, no `body` and no `#root`, so the three rules that address them
have to address the skin's own root instead. Everything else in the sheet — Tailwind's
preflight, the utilities, `::selection`, the scrollbar pseudo-elements, the `@property`
registrations, every `@keyframes` — is kept BYTE FOR BYTE, because a Shadow-DOM host still
needs all of it (analysis §9.1: the whole sheet has to be adopted inside the shadow root,
and a lost `@keyframes` freezes a caption plate at `opacity:0`).

Fail-closed: every rewrite must match EXACTLY once. A silent no-match would ship a rule that
cannot apply, which is the failure this whole lane exists to prevent.

Usage:  py -3 _main/_skin-lane/rewrite-css.py
"""
import io
import os
import re
import sys

SKIN = r'H:\sotto\app\panel\skins\cinematic-2'
RAW = os.path.join(SKIN, 'app.raw.css')
OUT = os.path.join(SKIN, 'app.css')

# (label, pattern, replacement, required count)
# The prefix class is `[{};]` — `{` INCLUDED. Written first as `[};]`, the Tailwind theme
# rule (`@layer theme{:root,:host{…`) could never match, because the character in front of
# `:root` there is `{`. The fail-closed count is what turned that typo into a refusal
# instead of a dead `:root` rule shipped into a shadow root.
RULES = [
    ('tailwind preflight html,:host',
     r'(^|[{};])html,:host\{',
     r'\1:host{', 1),
    ('the height chain',
     r'html,body,#root\{height:100%\}',
     r':host,.skin-root{height:100%}', 1),
    ('body defaults',
     r'(^|[{};])body\{',
     r'\1:host{', 1),
    ('tailwind theme vars :root,:host',
     r'(^|[{};]):root,:host\{',
     r'\1:host{', 1),
]

HOST_CONTRACT = """
/* ═══ THE SHADOW-DOM HOST CONTRACT — APPENDED, NOT REORDERED ═══════════════════════════
 * Everything above this line is the vendor's compiled stylesheet, byte for byte, except
 * for the four selectors listed in _main/_skin-lane/receipt-freeze-cinematic-2.md §2.
 * This block is the minimum the vendor's `index.css` used to get for free from the
 * DOCUMENT and cannot get from a shadow root (analysis §9.1-§9.3, §9.7):
 *
 *   display:block   — a host is `display:inline` by default, so without this the app's
 *                     `h-full w-full` root has no box to be 100% OF (§9.1a, the #1
 *                     breakage: the whole skin collapses to zero height).
 *   height:100%     — `index.css`'s `html,body,#root{height:100%}` chain, re-anchored to
 *                     the host. The PARENT must give this element a definite height.
 *   font-size:16px  — every type size in the sheet is `rem`, which follows the DOCUMENT
 *                     root. A host page that sets `html{font-size:…}` would silently
 *                     rescale the whole skin (§9.7).
 *   isolation:isolate — the App root creates no stacking context of its own, so
 *                     `.grain-layer`'s `mix-blend-mode:overlay` and every
 *                     `backdrop-filter` would otherwise sample the FOREIGN page behind
 *                     (§9.3). This box is the one that makes the skin opaque to its host.
 *   background      — the vendor `body` background, so an unmounted/loading skin is the
 *                     vendor's own colour rather than the host's.
 */
:host {
  display: block;
  position: relative;
  height: 100%;
  width: 100%;
  font-size: 16px;
  isolation: isolate;
  background: var(--page, #0a0d10);
  color: var(--text, #e8eef2);
}
:host, .skin-root {
  box-sizing: border-box;
}
/* The scrollbar skin (`index.css`'s `.quiet-scroll`) is IN the sheet above and therefore
 * reaches the shadow tree — but `scrollbar-width` is not inherited and the
 * `::-webkit-scrollbar` rules are not inherited either, so a host that styles scrollbars
 * globally cannot break this. Nothing to duplicate; noted because §9.1e asks. */
/* The shadow root is a REGISTERED-PROPERTY BOUNDARY: an `@property` registration in
 * the adopted sheet does not cross into the shadow tree in Chrome, so a `var(--tw-*)`
 * that was supposed to fall back to its registered `initial-value` instead resolves to
 * nothing and any declaration consuming it dies. MEASURED on cellar (dump.js):
 * `.-translate-x-1/2{--tw-translate-x:-50%;translate:var(--tw-translate-x)
 * var(--tw-translate-y)}` — the node sets `--tw-translate-x` itself but gets
 * `--tw-translate-y` only from its registration, which did not cross — so `translate`
 * dropped and the node rendered at bare `left:50%` (x=190), 209px off the vendor
 * (x=-18.91). The map below re-declares, on the two roots the shadow tree inherits
 * from, EXACTLY the defaults the vendor's own tree computes at `#root` — measured with
 * `getComputedStyle(document.getElementById('root')).getPropertyValue(name)` for every
 * one of the 40 registered `--tw-*` names (dump.js output, cellar, vendor side):
 * non-empty there ⟺ a registration initial the tree depends on, copied byte for byte;
 * empty there ⟺ unset in both trees, so declaring nothing is the faithful choice and
 * any value invented here would be a lie. If the compiled sheet ever registers MORE
 * `@property` names, re-run the dump and extend this map with what the vendor computes. */
:host, .skin-root {
  --tw-translate-x: 0; --tw-translate-y: 0; --tw-translate-z: 0;
  --tw-border-style: solid;
  --tw-shadow: 0 0 #0000; --tw-shadow-alpha: 100%;
  --tw-inset-shadow: 0 0 #0000; --tw-inset-shadow-alpha: 100%;
  --tw-ring-shadow: 0 0 #0000;
  --tw-inset-ring-shadow: 0 0 #0000;
  --tw-ring-offset-width: 0px;
  --tw-ring-offset-color: #fff; --tw-ring-offset-shadow: 0 0 #0000;
  --tw-drop-shadow-alpha: 100%;
}
"""


def main():
    with io.open(RAW, encoding='utf-8') as fh:
        css = fh.read()
    print('raw sheet: %d chars' % len(css))

    out = css
    report = []
    for label, pat, repl, want in RULES:
        hits = re.findall(pat, out)
        if len(hits) != want:
            sys.stderr.write('FAIL-CLOSED: rule "%s" matched %d time(s), expected %d\n'
                             % (label, len(hits), want))
            return 1
        m = re.search(pat, out)
        before = out[max(0, m.start() - 20):m.end() + 60]
        out = re.sub(pat, repl, out, count=want)
        after = out[max(0, m.start() - 20):m.end() + 60]
        report.append((label, before, after))
        print('  rewrote %-34s x%d' % (label, want))

    # The appended contract must not smuggle in a rule that changes the vendor's painting:
    # it carries only the five host-level facts listed above.
    out = out + HOST_CONTRACT

    with io.open(OUT, 'w', encoding='utf-8', newline='') as fh:
        fh.write(out)
    print('wrote %s  %d chars (%+d vs raw)' % (OUT, len(out), len(out) - len(css)))

    print('')
    print('=== every selector rewritten, before -> after ===')
    for label, before, after in report:
        print('--- %s' % label)
        print('  before: %s' % before.replace('\n', ' '))
        print('  after : %s' % after.replace('\n', ' '))

    # What a shadow root cannot use, re-checked on the OUTPUT: any surviving bare `html`
    # or `body` selector would be dead code in the skin, and a surviving remote URL would
    # be blocked by the panel's CSP. COMMENTS ARE STRIPPED FIRST: the appended host
    # contract quotes the vendor's own `html,body,#root{height:100%}` to explain what it
    # replaces, and a scan that counted that would report a dead rule that does not exist
    # (a false alarm in a gate is how the next reader learns to ignore the word).
    scan = re.sub(r'/\*.*?\*/', '', out, flags=re.S)
    for pat, what in ((r'(^|[{};])html\{', 'bare html rule'),
                      (r'(^|[{};])body\{', 'bare body rule'),
                      (r'(^|[{};])#root\{', 'bare #root rule'),
                      (r'url\(\s*[\'"]?https?:', 'remote url'),
                      (r'@font-face', '@font-face')):
        n = len(re.findall(pat, scan))
        print('  %-18s in the output: %d%s' % (what, n, '   OK' if n == 0 else '   <-- DEAD/BLOCKED'))
    for pat, what in ((r'@keyframes', '@keyframes'), (r'::selection', '::selection'),
                      (r'::-webkit-scrollbar', 'scrollbar pseudo'),
                      (r'@property', '@property')):
        n = len(re.findall(pat, scan))
        print('  %-18s in the output: %d%s' % (what, n, '   SURVIVED' if n else '   <-- LOST'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
