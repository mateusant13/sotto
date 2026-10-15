"""A SEGUNDA JANELA, EM ISOLAMENTO -- SEM background_color, para testar se a caixa
opaca por tras do texto era ele."""
import os
import threading
import time

import webview

CAPTION = "H:/sotto/app/panel/caption.html"


def work_area():
    import ctypes
    from ctypes import wintypes
    rect = wintypes.RECT()
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top


wa_x, wa_y, wa_w, wa_h = work_area()
cap_w = max(360, min(900, wa_w - 80))
cap_h = 170
cap_x = wa_x + (wa_w - cap_w) // 2
cap_y = wa_y + wa_h - cap_h - 48
print("workArea=%d,%d %dx%d" % (wa_x, wa_y, wa_w, wa_h), flush=True)
print("caption window at %d,%d %dx%d" % (cap_x, cap_y, cap_w, cap_h), flush=True)

win = webview.create_window(
    "Sotto caption probe",
    url="file:///" + CAPTION.replace(os.sep, "/"),
    width=cap_w,
    height=cap_h,
    x=cap_x,
    y=cap_y,
    frameless=True,
    transparent=True,
    on_top=True,
    resizable=False,
    easy_drag=False,
    hidden=False,
)


def drive():
    # TARDE, e nao no before_show: o `DefaultBackgroundColor` so pega depois de o
    # CoreWebView2Controller existir. Testa-lo aqui diz se a caixa branca e o controlo
    # ou a form.
    time.sleep(1.2)
    try:
        form = getattr(win, "native", None)
        wv = getattr(form, "webview", None) if form is not None else None
        if wv is not None:
            from System.Drawing import Color as _C
            wv.DefaultBackgroundColor = _C.Transparent
            try:
                ctrl = getattr(wv, "CoreWebView2Controller", None)
                if ctrl is not None:
                    ctrl.DefaultBackgroundColor = _C.Transparent
                    print("CTRL_BGC set=transparent", flush=True)
                else:
                    print("CTRL_BGC sem controlador", flush=True)
            except Exception as exc:
                print("CTRL_BGC_FAILED %r" % (exc,), flush=True)
            print("LATE_WEBVIEW2_BGC set=transparent", flush=True)
        else:
            print("LATE sem controlo", flush=True)
    except Exception as exc:
        print("LATE_FAILED %r" % (exc,), flush=True)
    time.sleep(1.3)
    try:
        win.evaluate_js(
            'window.SottoCaption.set("Uma vez que voce foi.", "e a linha anterior fica aqui");'
            'window.SottoCaption.credits("TRANSCRIBING MARLOW ON-DEVICE 240 MS");'
            'window.SottoCaption.listening(true);')
        print("fixture injectada", flush=True)
    except Exception as exc:
        print("fixture falhou: %r" % (exc,), flush=True)
    time.sleep(4.5)
    print("a fechar", flush=True)
    try:
        win.destroy()
    except Exception:
        pass


def before_show():
    """A CURA DA CAIXA BRANCA. `pywebview` poe `SupportsTransparentBackColor` na form mas
    so lhe da `BackColor` no ramo NAO-transparente, portanto uma janela transparente fica
    com o `SystemColors.Control` do .NET -- medido `rgb(240,240,240)`, que e a caixa clara
    que se ve atras do texto. A form vive em `window.native`; o evento NAO passa
    argumentos (o shell assina `_on_before_show(self)` e le-a de `self._form()`)."""
    form = getattr(win, "native", None)
    if form is None:
        print("BEFORE_SHOW sem form", flush=True)
        return
    try:
        from System.Drawing import Color
        form.BackColor = Color.Transparent
        print("FORM_BACKCOLOR set=transparent", flush=True)
        # E O PROPRIO WEBVIEW2. O `DefaultBackgroundColor` do controlo e BRANCO por
        # omissao; e ele que pinta a caixa clara em todo o pixel que a pagina nao cobre,
        # e e o caminho suportado pela Microsoft (o `WS_EX_LAYERED`+`LWA_COLORKEY` NAO
        # chega ao WebView2). O shell confia que o pywebview o poe; esta janela poe-lo a
        # mao, porque a caixa persistiu com a form ja transparente.
        try:
            wv = getattr(form, "webview", None)
            if wv is not None:
                wv.DefaultBackgroundColor = Color.Transparent
                print("WEBVIEW2_BGC set=transparent", flush=True)
            else:
                print("WEBVIEW2_BGC sem controlo", flush=True)
        except Exception as exc:
            print("WEBVIEW2_BGC_FAILED %r" % (exc,), flush=True)
    except Exception as exc:
        print("FORM_BACKCOLOR_FAILED %r" % (exc,), flush=True)


win.events.before_show += before_show
threading.Thread(target=drive, daemon=True).start()
webview.start()
print("saiu", flush=True)