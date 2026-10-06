"""PROBE: is WinForms `VisibleChanged` raised SYNCHRONOUSLY inside `Show()`?

The intermittent startup flash is pywebview calling `self.form.Show()` in its
own `on_navigation_start` (edgechromium.py:347). The shell's counter-measure is
a handler on a DIFFERENT event (`CoreWebView2.NavigationStarting`), and the
measured gap between the Show and the shell's Hide is up to ~58 ms — i.e. the
two run at different points of the message pump.

If `VisibleChanged` is raised INSIDE `Show()`, a handler on it can re-hide the
form in the SAME call, before a frame is composed, and no ordering race exists
at all. This probe answers that with one form, off-screen, no console.

    pythonw.exe _main/_visiblechanged-probe.py
"""

from __future__ import annotations

import os
import sys

def main() -> int:
    try:
        import clr  # pythonnet; loads with the runtime
        clr.AddReference('System.Windows.Forms')
        clr.AddReference('System.Drawing')
    except Exception as exc:
        print(f'NO_CLR {exc}')
        return 3
    from System.Windows.Forms import Application, Form, FormStartPosition
    from System.Drawing import Point, Size

    Application.EnableVisualStyles()
    events: list[str] = []
    form = Form()
    form.Text = 'vc-probe'
    form.StartPosition = FormStartPosition.Manual
    form.Location = Point(-10000, -10000)
    form.Size = Size(200, 100)

    def on_visible_changed(sender, args):
        events.append(f'VisibleChanged Visible={form.Visible}')

    form.VisibleChanged += on_visible_changed

    events.append('calling Show()')
    form.Show()
    events.append('after Show()')
    events.append('calling Hide()')
    form.Hide()
    events.append('after Hide()')

    print('EVENTS:')
    for e in events:
        print('  ' + e)
    idx_show = events.index('calling Show()')
    idx_after = events.index('after Show()')
    sync = any('VisibleChanged' in e for e in events[idx_show:idx_after])
    print(f'VISIBLECHANGED_SYNCHRONOUS={"true" if sync else "false"}')
    form.Close()
    return 0 if sync else 3


if __name__ == '__main__':
    sys.exit(main())
