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
    time.sleep(0.3)
    # TESTE DECISIVO: pinta o body de VERMELHO. Se a caixa ficar vermelha, quem a pinta e
    # a PAGINA (e o problema esta no CSS). Se ficar clara, quem a pinta e a JANELA (e o
    # problema esta na criacao). Uma linha, e acaba com a duvida.
    time.sleep(1.0)
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
        # TESTE DECISIVO 2: VERMELHO na form. Se a caixa ficar vermelha, quem a pinta e a
        # FORM; se ficar clara, e o WebView2 por cima dela.
        # A CURA: `TransparencyKey`. Uma form de TOPO com `BackColor = Color.Transparent`
        # NAO fica transparente -- o .NET nao tem para onde compor sem um pai, e cai no
        # `SystemColors.Control` (a caixa clara, medido). O caminho do WinForms para uma
        # form de topo e uma COR-CHAVE: tudo o que for exactamente essa cor sai da janela.
        # MAGENTA e nao branco: a legenda e `#f5f8fc` e o branco puro podia cair na chave.
        # O shell parece transparente sem isto porque a PAGINA dele cobre a form inteira; a
        # pagina da legenda e transparente de proposito, e entao a form aparece.
        MAGENTA = Color.FromArgb(0xFF, 0xFF, 0x00, 0xFF)
        form.BackColor = MAGENTA
        form.TransparencyKey = MAGENTA
        # E O WEBVIEW2, NA THREAD DA UI, DEPOIS DE O CONTROLADOR EXISTIR. Medido: o
        # `DefaultBackgroundColor` posto no `before_show` nao chega, e posto de um thread
        # qualquer falha com "can only be accessed from the UI thread". `form.Invoke`
        # marshala para a thread da UI. O controlo e `form.webview`.
        from System import Action
        def _kill_wv_bg():
            try:
                wv = getattr(form, "webview", None)
                if wv is None:
                    print("INVOKE sem controlo", flush=True)
                    return
                wv.DefaultBackgroundColor = Color.Transparent
                print("INVOKE_WEBVIEW2_BGC set=transparent", flush=True)
            except Exception as exc:
                print("INVOKE_WEBVIEW2_BGC_FAILED %r" % (exc,), flush=True)
        form.Invoke(Action(_kill_wv_bg))
        print("FORM_TRANSPARENCYKEY set=magenta", flush=True)
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