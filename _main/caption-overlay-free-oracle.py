#!/usr/bin/env python3
"""ORACLE: THE CAPTION BUTTON OPENS NOTHING. (lane: caption, 2026-10-17)

THE OWNER, verbatim, and this file exists because the code broke it:

    "ao clicar no botao de legenda, nao deve abrir qualquer coisa. e pra ativar a
     legenda, na minha tela, sem background, sem estar conectada a qualquer
     painel. ela e livre na minha tela, an overlay"

Measured, in `_main/webview-run.log`, what one click of that button used to do:

    21:40:12.621  STRIP_HEIGHT from=40 to=220 source=css css_value=220 reason=surface-strip-float-on
    21:40:12.638  PANEL_SURFACE surface=strip reason=strip-float-on window=380x220@(770,768)
    21:40:12.643  PANEL_SURFACE surface=strip reason=float-on      window=380x220@(770,768)

+180 px of panel for a switch that was supposed to change nothing but a caption.
Three writers did it, and a check that looks at one of them is worthless, so this
oracle looks at ALL of them plus the two facts that made the switch a lie.

WHAT IS CHECKED, and why each one is a separate arm:

  A1  panel.js `applyFloat` must not call `setPanelSurface`   -- write #2
  A2  panel.js `applyFloat` must not write a floated height   -- write #1
  A3  caption-float.js `setFloat` must not call `setPanelSurface` -- write #3
  A4  panel.js must have the `shellOwnsCaptionWindow` guard   -- the branch that
      makes A1-A3 a decision instead of a deletion
  B1  caption-float.css must not blank the PAGE background on `data-float="on"`
      -- the panel's HWND is not layered (`sotto_webview.py:4969`, measured), so a
      transparent page inside it is WHITE: the slab and the corners
  C1  `push_caption_to_window` must be gated on `_caption_wanted` -- before, every
      caption line raised the window on its own with no click anywhere
  C2  `_set_live_enabled` must SET `_caption_wanted`           -- the switch
  C3  `_caption_idle_hide` must not call `show_caption_window`  -- six seconds of
      silence used to switch the owner off by writing `data-caption-window="off"`
  C4  `hide_panel` must not call `show_caption_window`          -- "not connected to
      any panel"
  D1  no live line may send the `float-on` reason              -- the second door

USAGE
    python _main/caption-overlay-free-oracle.py             # GREEN / RED on the repo
    python _main/caption-overlay-free-oracle.py --neg-arm   # every arm must go RED
    python _main/caption-overlay-free-oracle.py --selftest  # 2/2 on a scratch fixture

WHY AN ORACLE AND NOT A PROBE: the defect is a CALL THAT MUST NOT EXIST. A browser
probe cannot prove the absence of a call in a file -- it can only prove the call did
not run in the session it watched. These are static facts about the bytes, so they
are checked against the bytes, and `--neg-arm` re-introduces each defect in memory
and requires the oracle to say NO.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
import textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL_JS = os.path.join(ROOT, 'app', 'panel', 'panel.js')
FLOAT_JS = os.path.join(ROOT, 'app', 'panel', 'caption-float.js')
FLOAT_CSS = os.path.join(ROOT, 'app', 'panel', 'caption-float.css')
SHELL_PY = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')

# The height the click used to produce. Named here so the arms do not have to
# remember a number that only ever appeared in one constant and one log line.
FLOATED_HEIGHT = '220px'


# ── extractors ──────────────────────────────────────────────────────────────
def read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def js_function(src, name):
    """The body of `function name(...) { ... }`, brace-matched, or ''."""
    anchor = 'function %s(' % name
    i = src.find(anchor)
    if i < 0:
        return ''
    brace = src.find('{', i)
    if brace < 0:
        return ''
    depth = 0
    for j in range(brace, len(src)):
        ch = src[j]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                return src[brace:j + 1]
    return ''


def py_function(src, name):
    """The source of a module-level or method `def name`, via ast."""
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:  # a syntax error is a RED, not an exception here
        return None, 'sotto_webview.py does not parse: %s' % exc
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            lines = src.splitlines()
            lo = node.lineno - 1
            hi = getattr(node, 'end_lineno', node.lineno)
            return '\n'.join(lines[lo:hi]), None
    return '', None


def py_facts(block):
    """(called names, assigned attribute names, names read by an `if` test).

    Why this and not a text scan: the FIRST RUN of this oracle reported C5 RED
    against a function whose only mention of `data-caption-window` was its own
    docstring saying it does NOT write it. Three arms in a row were reading prose
    as code. These arms are about WHICH CALLS EXIST, so they are read off the tree.
    """
    tree = ast.parse(textwrap.dedent(block))
    calls, assigns, if_names = set(), set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                calls.add(func.attr)
            elif isinstance(func, ast.Name):
                calls.add(func.id)
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
            assigns.add(node.attr)
        if isinstance(node, ast.If):
            for sub in ast.walk(node.test):
                if isinstance(sub, ast.Attribute):
                    if_names.add(sub.attr)
                elif isinstance(sub, ast.Name):
                    if_names.add(sub.id)
                elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    # `if not getattr(self, '_caption_wanted', False):` tests the
                    # switch as a STRING inside getattr, not as a name. Measured:
                    # without this the arm read a real gate as no gate.
                    if_names.add(sub.value)
    return calls, assigns, if_names


def strip_css_comments(text):
    """Drop `/* ... */` comments.

    MEASURED, on this oracle's first run: without this, arm B1 read the RETIRED
    rule out of the comment that documents why it was retired and called the fix a
    failure. A scanner that reads prose as code is the exact instrument defect this
    repo has been bitten by twice (see AGENTS.md, "Keeping THIS file true").
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith('/*', i):
            j = text.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(text[i])
        i += 1
    return ''.join(out)


def py_string_constants_outside_docstrings(src):
    """Every string literal that is NOT a docstring.

    Arm D1 needs this and not a line scan: the retired `float-on` reason is quoted
    in docstrings (the measured log excerpt inside `_blank_caption_window`), so a
    line scan reports the COMMENT as the DEFECT. Measured on this oracle's first
    run — D1 was RED against a file whose only `float-on` occurrences are prose.
    """
    tree = ast.parse(src)
    docstring_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, 'body', None)
            if isinstance(body, list) and body:
                first = body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                        and isinstance(first.value.value, str):
                    docstring_ids.add(id(first.value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstring_ids:
            out.append(node.value)
    return out


# ── the arms ────────────────────────────────────────────────────────────────
def check(files):
    """files: {logical name: source text}. Returns [(arm, ok, detail)]."""
    panel_js = files['panel.js']
    float_js = files['caption-float.js']
    float_css = files['caption-float.css']
    shell_py = files['sotto_webview.py']

    apply_float = js_function(panel_js, 'applyFloat')
    guard = js_function(panel_js, 'shellOwnsCaptionWindow')
    set_float = js_function(float_js, 'setFloat')

    push, err = py_function(shell_py, 'push_caption_to_window')
    live, err2 = py_function(shell_py, '_set_live_enabled')
    idle, err3 = py_function(shell_py, '_caption_idle_hide')
    hide, err4 = py_function(shell_py, 'hide_panel')
    blank, err5 = py_function(shell_py, '_blank_caption_window')

    syntax_errors = [e for e in (err, err2, err3, err4, err5) if e]
    results = []
    if syntax_errors:
        return [('A0-python-parses', False, syntax_errors[0])]

    # A1 / A2 — the panel's own window must not be touched by the caption switch.
    results.append((
        'A1 applyFloat never calls setPanelSurface',
        bool(apply_float) and 'setPanelSurface' not in apply_float,
        'applyFloat body: %s' % (apply_float[:70].replace('\n', ' ') or 'NOT FOUND'),
    ))
    results.append((
        'A2 applyFloat never writes a floated height',
        bool(apply_float) and FLOATED_HEIGHT not in apply_float,
        'no %s in applyFloat' % FLOATED_HEIGHT,
    ))

    # A3 — the second writer, which grew the window even when A1 was skipped.
    results.append((
        'A3 caption-float setFloat never calls setPanelSurface',
        bool(set_float) and 'setPanelSurface' not in set_float,
        'setFloat body: %s' % (set_float[:70].replace('\n', ' ') or 'NOT FOUND'),
    ))

    # A4 — the guard that turns A1..A3 into a decision rather than a deletion.
    results.append((
        'A4 applyFloat keeps the shellOwnsCaptionWindow guard',
        bool(guard) and 'setLiveEnabled' in guard and 'shellOwnsCaptionWindow' in apply_float,
        'guard present=%s used=%s' % (bool(guard),
                                      'shellOwnsCaptionWindow' in apply_float),
    ))

    # B1 — the page must keep its opaque base: an unlayered window + a transparent
    # page is WHITE, measured, not asserted.
    css_code = strip_css_comments(float_css)
    blanks_page = False
    for selector in ('html[data-float="on"]', 'body[data-float="on"]'):
        i = css_code.find(selector)
        if i >= 0:
            brace = css_code.find('{', i)
            depth = 0
            for j in range(brace, len(css_code)):
                if css_code[j] == '{':
                    depth += 1
                elif css_code[j] == '}':
                    depth -= 1
                    if depth == 0:
                        if 'transparent' in css_code[brace:j]:
                            blanks_page = True
                        break
    results.append((
        'B1 caption-float.css never blanks the page background',
        not blanks_page,
        'html/body[data-float=on] background:transparent present=%s' % blanks_page,
    ))

    # C1..C5 — the switch must mean something, and silence must not own it.
    push_calls, _, push_if = py_facts(push)
    live_calls, live_assigns, _ = py_facts(live)
    idle_calls, _, _ = py_facts(idle)
    hide_calls, _, _ = py_facts(hide)
    blank_calls, blank_assigns, _ = py_facts(blank)

    results.append((
        'C1 push_caption_to_window is gated on _caption_wanted',
        '_caption_wanted' in push_if,
        'an `if` tests the switch=%s' % ('_caption_wanted' in push_if),
    ))
    results.append((
        'C2 _set_live_enabled sets _caption_wanted',
        '_caption_wanted' in live_assigns and 'show_caption_window' in live_calls,
        'assigns the flag=%s calls the window=%s'
        % ('_caption_wanted' in live_assigns, 'show_caption_window' in live_calls),
    ))
    results.append((
        'C3 six seconds of silence does not switch the owner off',
        'show_caption_window' not in idle_calls and '_blank_caption_window' in idle_calls,
        'idle hide blanks pixels=%s' % ('_blank_caption_window' in idle_calls),
    ))
    results.append((
        'C4 hiding the panel does not switch the caption off',
        'show_caption_window' not in hide_calls and '_blank_caption_window' in hide_calls,
        'hide_panel blanks pixels=%s' % ('_blank_caption_window' in hide_calls),
    ))
    results.append((
        'C5 _blank_caption_window only clears pixels',
        'show_caption_window' not in blank_calls
        and 'evaluate_js' not in blank_calls
        and '_caption_window_shown' in blank_assigns,
        'calls=%s assigns_shown=%s'
        % (sorted(blank_calls), '_caption_window_shown' in blank_assigns),
    ))

    # D1 — the second door. Comments and docstrings may quote the retired reason;
    # a string literal in live code may not.
    try:
        live_strings = py_string_constants_outside_docstrings(shell_py)
    except SyntaxError as exc:
        return results + [('D1 no live line sends the float-on reason', False,
                           'sotto_webview.py does not parse: %s' % exc)]
    offenders = [s for s in live_strings if 'float-on' in s or 'float-off' in s]
    results.append((
        'D1 no live line sends the float-on reason',
        not offenders,
        'string literals naming it: %s' % (offenders[:2] or 'none'),
    ))

    return results


# ── mutations: each one must make EXACTLY its arm go red ────────────────────
def mutations(files):
    """[(label, files, arm index that must turn RED)]"""
    out = []

    f = dict(files)
    f['panel.js'] = files['panel.js'].replace(
        'function applyFloat(on) {',
        'function applyFloat(on) {\n'
        "  if (currentSurface() === 'strip') bridge.setPanelSurface('strip', 'x');",
        1)
    out.append(('panel.applyFloat asks the shell to re-surface', f, 'A1'))

    f = dict(files)
    f['panel.js'] = files['panel.js'].replace(
        'function applyFloat(on) {',
        "function applyFloat(on) {\n  setStripHeight('%s');" % FLOATED_HEIGHT,
        1)
    out.append(('panel.applyFloat writes %s' % FLOATED_HEIGHT, f, 'A2'))

    f = dict(files)
    f['caption-float.js'] = files['caption-float.js'].replace(
        '  function setFloat(next) {',
        '  function setFloat(next) {\n'
        "    window.sotto.setPanelSurface('strip', 'float-on');",
        1)
    out.append(('caption-float.setFloat asks the shell to re-surface', f, 'A3'))

    f = dict(files)
    f['panel.js'] = files['panel.js'].replace(
        '  if (shellOwnsCaptionWindow()) return;', '  // guard removed', 1)
    out.append(('the shellOwnsCaptionWindow guard is removed', f, 'A4'))

    f = dict(files)
    f['caption-float.css'] = files['caption-float.css'].replace(
        '/* DELETED 2026-10-17, AND THIS WAS THE OWNER\'S "BACKGROUND".',
        'html[data-float="on"],\nbody[data-float="on"] {\n'
        '  background: transparent;\n}\n\n/* DELETED 2026-10-17, AND THIS WAS THE OWNER\'S "BACKGROUND".',
        1)
    out.append(('the page goes transparent on data-float=on', f, 'B1'))

    f = dict(files)
    f['sotto_webview.py'] = files['sotto_webview.py'].replace(
        "        if not getattr(self, '_caption_wanted', False):\n            return False\n",
        '', 1)
    out.append(('push_caption_to_window drops the switch', f, 'C1'))

    f = dict(files)
    f['sotto_webview.py'] = files['sotto_webview.py'].replace(
        '            self._caption_wanted = on\n', '', 1)
    out.append(('_set_live_enabled forgets to set the flag', f, 'C2'))

    f = dict(files)
    f['sotto_webview.py'] = files['sotto_webview.py'].replace(
        "            self._blank_caption_window('no-caption-for-%ss' % (self.CAPTION_IDLE_HIDE_S,))",
        '            self.show_caption_window(False)', 1)
    out.append(('six seconds of silence switches the owner off', f, 'C3'))

    f = dict(files)
    f['sotto_webview.py'] = files['sotto_webview.py'].replace(
        "        self._blank_caption_window('panel-hidden')",
        '        self.show_caption_window(False)', 1)
    out.append(('hiding the panel switches the caption off', f, 'C4'))

    f = dict(files)
    f['sotto_webview.py'] = files['sotto_webview.py'].replace(
        '        self._caption_window_shown = False\n'
        '        try:\n'
        '            self._post(lambda: ov.show(False))\n'
        '        except Exception:  # noqa: BLE001\n'
        '            pass\n',
        '        self.show_caption_window(False)\n', 1)
    out.append(('_blank_caption_window rewrites the attribute', f, 'C5'))

    f = dict(files)
    f['sotto_webview.py'] = files['sotto_webview.py'].replace(
        '        payload = payload or {}\n        reason = payload.get(\'reason\') or \'page\'',
        '        payload = payload or {}\n        reason = payload.get(\'reason\') or \'page\'\n'
        "        if reason in ('float-on', 'float-off'):\n"
        "            self._shell.show_caption_window(reason == 'float-on')",
        1)
    out.append(('a surface reason opens the caption again', f, 'D1'))

    return out


def load_repo():
    return {
        'panel.js': read(PANEL_JS),
        'caption-float.js': read(FLOAT_JS),
        'caption-float.css': read(FLOAT_CSS),
        'sotto_webview.py': read(SHELL_PY),
    }


def arm_prefix(label):
    return label.split(' ', 1)[0]


def run_neg_arm(files):
    print('NEG-ARM: each defect re-introduced in memory must turn its arm RED\n')
    ok = True
    for label, mutated, arm in mutations(files):
        results = check(mutated)
        verdicts = {arm_prefix(a): good for a, good, _ in results}
        red = verdicts.get(arm) is False
        print('  %-4s %-52s -> %s (want %s RED)'
              % (arm, label, 'RED' if red else 'GREEN', arm))
        if not red:
            ok = False
    print()
    print('NEG-ARM: %s' % ('PASS -- the oracle can say NO' if ok else 'FAIL'))
    return 0 if ok else 1


def run_selftest(files):
    results = check(files)
    green = all(good for _, good, _ in results)
    print('SELFTEST control (the repo as it stands): %s'
          % ('GREEN' if green else 'RED'))
    failed = run_neg_arm(files)
    ok = green and failed == 0
    print()
    print('SELFTEST: %s' % ('GREEN (2/2)' if ok else 'RED'))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--neg-arm', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()

    files = load_repo()
    if args.selftest:
        return run_selftest(files)
    if args.neg_arm:
        return run_neg_arm(files)

    results = check(files)
    print('THE CAPTION BUTTON OPENS NOTHING -- %d arms\n' % len(results))
    width = max(len(a) for a, _, _ in results)
    bad = 0
    for arm, good, detail in results:
        label = arm[len(arm_prefix(arm)):].strip()
        print('  %-5s %-*s  %s' % ('GREEN' if good else 'RED', width, label, detail))
        if not good:
            bad += 1
    print()
    if bad:
        print('VERDICT: RED -- %d arm(s) failed' % bad)
        return 1
    print('VERDICT: GREEN -- the panel opens nothing on a caption click, the page')
    print('         keeps its own base, and the caption is the native overlay.')
    return 0


if __name__ == '__main__':
    sys.exit(main())