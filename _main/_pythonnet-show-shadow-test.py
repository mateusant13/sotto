"""MECHANICS TEST (no window is ever shown): can a Python subclass, and can an
INSTANCE attribute, shadow System.Windows.Forms.Form.Show for a PYTHON-side
call `form.Show()`?

pywebview maps the panel with `self.form.Show()` -- a PYTHON-level attribute
lookup on a pythonnet proxy (platforms/edgechromium.py:348). If Python attribute
resolution wins over the CLR member, the shell can gate that map without
touching any subscription (which two house oracles assert as
`NavigationStarting handlers=2`). This measures which of the two spellings
works BEFORE any shell edit.

Nothing here calls Show()/ShowDialog(), so no window is created or mapped.
"""
import sys

OUT = r'H:/sotto/_main/_pythonnet-show-shadow-test.out'


def main() -> int:
    lines = []

    def p(*a):
        lines.append(' '.join(str(x) for x in a))

    try:
        import clr  # noqa: F401
        clr.AddReference('System.Windows.Forms')
        from System.Windows.Forms import Application, Form

        Application.EnableVisualStyles()

        class Sub(Form):
            def Show(self):
                return 'SUBCLASS-GATED'

        s = Sub()
        p('subclass: type(s).Show is Sub.Show ->',
          getattr(type(s), 'Show', None) is Sub.Show)
        try:
            p('subclass: s.Show resolves to ->', s.Show())
        except Exception as exc:
            p('subclass: s.Show raised ->', repr(exc))

        base = Form()
        hwnd = int(base.Handle.ToInt64())   # creates a handle, does NOT map it
        p('instance: handle created (never shown) ->', hwnd)

        def gated():
            return 'INSTANCE-GATED'

        try:
            base.Show = gated
            p('instance: setattr accepted; base.Show ->', base.Show)
            p('instance: base.Show() ->', base.Show())
        except Exception as exc:
            p('instance: setattr REFUSED ->', type(exc).__name__, exc)
        p('instance: after attempt, type(base).Show ->', getattr(type(base), 'Show', None))
    except Exception as exc:
        p('ERROR', type(exc).__name__, repr(exc))

    with open(OUT, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
