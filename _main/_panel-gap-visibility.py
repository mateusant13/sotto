"""Throwaway oracle: is the per-row "Show in folder" button and the search
`<mark>` LAYOUT AND VISIBLE in the real panel, or merely present in the DOM?

The v2 acceptance probe counts DOM nodes (`#history-list .hist__folder`), which
a `display:none` node would also satisfy. This wraps `request_exit` so that,
the instant the probe is about to exit (the list then holds the SEARCH RESULT),
one extra `exec_js` measures the bounding rect + computed style of the first
`.hist__folder` and the first `mark`, with the row itself as a CONTROL: if the
control is zero-sized the instrument is measuring a window that never laid out,
and the run says so instead of reporting "invisible".

Nothing is opened. No window is shown (`--no-hotkey`, no `--show`).
"""
import importlib.util
import json
import os
import sys

SHELL = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '..', 'app', 'webview', 'sotto_webview.py')
sys.path.insert(0, os.path.dirname(os.path.abspath(SHELL)))
spec = importlib.util.spec_from_file_location('sotto_webview', SHELL)
mod = importlib.util.module_from_spec(spec)
sys.modules['sotto_webview'] = mod
spec.loader.exec_module(mod)

VIS_JS = r"""
(() => {
  const qa = (s) => Array.from(document.querySelectorAll(s));
  const info = (el) => {
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return { w: Math.round(r.width), h: Math.round(r.height),
             x: Math.round(r.x), y: Math.round(r.y),
             display: cs.display, visibility: cs.visibility, opacity: cs.opacity,
             text: (el.textContent || '').slice(0, 24) };
  };
  const list = document.getElementById('history-list');
  const rows = qa('#history-list .hist');
  const folders = qa('#history-list .hist__folder');
  const marks = qa('#history-list mark');
  return {
    hint: 'list was left in SEARCH-RESULT state by the probe',
    rows: rows.length, folders: folders.length, marks: marks.length,
    controlRow: info(rows[0]),
    folder: info(folders[0]),
    mark: info(marks[0]),
    listClientH: list ? list.clientHeight : null,
    listScrollTop: list ? list.scrollTop : null,
  };
})()
"""

orig_request_exit = mod.SottoShell.request_exit


def patched_request_exit(self, rc, **kw):
    try:
        vis = self.exec_js(VIS_JS)
        mod.log('PANEL_GAP_VISIBILITY ' + json.dumps(vis, separators=(',', ':')))
    except Exception as exc:  # noqa: BLE001 -- report, never hide the failure
        mod.log('PANEL_GAP_VISIBILITY_FAILED ' + repr(exc))
    return orig_request_exit(self, rc, **kw)


mod.SottoShell.request_exit = patched_request_exit

if __name__ == '__main__':
    # The probe flags are REQUIRED for this measurement; anything the caller
    # passes additionally (e.g. --log <path>) is appended.
    argv = ['--no-hotkey', '--probe-v2', '3'] + sys.argv[1:]
    sys.exit(mod.main(argv))
