"""Mechanism probe: does pywebview's `hidden=True` dance leave the form VISIBLE?

pywebview/platforms/winforms.py:777-782, the branch this shell takes because
`create_window(..., hidden=True)`:

    if window.hidden:
        browser.Opacity = 0
        browser.Show()
        browser.Hide()
        browser.Opacity = 1

A bare WinForms Form is driven through the SAME statements (no WebView2, no
model, no audio, no pywebview) and `IsWindowVisible(hwnd)` is read after every
one of them. This answers WHICH statement leaves the window visible, which is
what makes a cure correct instead of a band-aid.

SAFETY: the form is placed OFF-SCREEN (x=-10000) and is OPACITY 0 while it is
shown, so nothing can appear on the owner's desktop even if the probe is wrong.
Launched with pythonw.exe + CREATE_NO_WINDOW (AGENTS.md).

Reads back: `DANCE step=<n> stmt=<...> visible=<bool> form_visible=<bool>`
"""
import os
import sys

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   '_dance-probe.log')
lines = []


def log(msg):
    lines.append(msg)
    with open(LOG, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def main():
    import clr  # noqa: F401  (pythonnet)
    # pywebview's winforms platform is what does `clr.AddReference` on the
    # WinForms/Drawing assemblies -- the shell loads it the same way.
    import webview.platforms.winforms  # noqa: F401
    from System.Windows.Forms import (Form, FormBorderStyle, FormStartPosition,
                                      Application)
    from System.Drawing import Point, Size
    from ctypes import windll

    Application.EnableVisualStyles()

    def vis(form):
        return bool(windll.user32.IsWindowVisible(form.Handle.ToInt64()))

    form = Form()
    # `None` is a Python keyword, so the enum member needs getattr -- the same
    # spelling pywebview itself uses for frameless (winforms.py:269-271).
    form.FormBorderStyle = getattr(FormBorderStyle, 'None')
    form.ShowInTaskbar = False
    form.StartPosition = FormStartPosition.Manual
    form.Location = Point(-10000, -10000)
    form.Size = Size(364, 861)
    h = form.Handle.ToInt64()          # force handle creation, never shown
    log(f'DANCE step=0 stmt=handle-created visible={vis(form)} '
        f'form.Visible={form.Visible} hwnd={h}')

    # arm A -- the exact pywebview sequence for hidden=True
    form.Opacity = 0
    log(f'DANCE step=1 stmt=Opacity=0 visible={vis(form)} '
        f'form.Visible={form.Visible} opacity={form.Opacity}')
    form.Show()
    log(f'DANCE step=2 stmt=Show() visible={vis(form)} '
        f'form.Visible={form.Visible}')
    form.Hide()
    log(f'DANCE step=3 stmt=Hide() visible={vis(form)} '
        f'form.Visible={form.Visible}')
    form.Opacity = 1
    log(f'DANCE step=4 stmt=Opacity=1 (after Hide) visible={vis(form)} '
        f'form.Visible={form.Visible} opacity={form.Opacity}')

    # arm B -- does Opacity=1 alone re-show a HIDDEN form?
    log(f'DANCE armB_before visible={vis(form)} form.Visible={form.Visible}')
    form.Opacity = 0.5
    log(f'DANCE armB_Opacity=0.5_on_hidden visible={vis(form)} '
        f'form.Visible={form.Visible}')
    form.Opacity = 1
    log(f'DANCE armB_Opacity=1_on_hidden visible={vis(form)} '
        f'form.Visible={form.Visible}')

    # arm C -- the same final state, read again after the message queue drains
    def tick(sender, e):
        log(f'DANCE armC_after_message_loop visible={vis(form)} '
            f'form.Visible={form.Visible}')
        sender.Stop()
        form.Dispose()
        Application.Exit()

    from System.Windows.Forms import Timer
    t = Timer()
    t.Interval = 200
    t.Tick += tick
    t.Start()
    Application.Run()

    log('DANCE done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
