"""O PISO DO UIA: quanto a arvore de acessibilidade do Chrome atrasa o DOM.

Le' AS DUAS coisas ao mesmo tempo, na mesma maquina:
  * o DOM pela CDP (`_yt-cdp-probe.SILENT_PROBE`), que e' o que o player pinta;
  * a pintura pela UIA (`youtube_captions.painted_words`), que e' o que o Sotto le.
Depois responde: quando a UIA mostra X, ha' quanto tempo o DOM ja' mostrava X?
"""
import io, json, sys, threading, time, ctypes
sys.path.insert(0, 'app/webview'); sys.path.insert(0, '_main/_libs'); sys.path.insert(0, '_main')
import external_subs, youtube_captions as yc, importlib.util as u

spec = u.spec_from_file_location('p', '_main/_yt-cdp-probe.py')
probe = u.module_from_spec(spec); spec.loader.exec_module(probe)

SECONDS = 30.0
dom, uia_rows = [], []
stop = threading.Event()

def read_dom():
    ws, err = probe.open_socket(video_id=probe.sottos_video_id())
    if ws is None:
        print('ABORT', err); stop.set(); return
    counter = [0]
    extra = (('Page.setWebLifecycleState', {'state': 'active'}),
             ('Emulation.setFocusEmulationEnabled', {'enabled': True}))
    while not stop.is_set():
        reading = probe.review(ws, counter, probe.SILENT_PROBE, extra)
        dom.append((time.time(), [str(x).strip().lower() for x in (reading.get('rows') or [])]))
        time.sleep(0.05)
    ws.close()

def find_hwnd():
    found = []
    PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def cb(h, lp):
        b = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(h, b, 512)
        if 'YouTube' in b.value:
            found.append(h)
        return True
    ctypes.windll.user32.EnumWindows(PROC(cb), 0)
    return found[0] if found else None

def read_uia():
    UIA, uia = external_subs._uia()
    hwnd = find_hwnd()
    root = uia.ElementFromHandle(hwnd)
    cond = uia.CreatePropertyCondition(UIA.UIA_ClassNamePropertyId,
                                       'ytp-caption-window-container')
    win = root.FindFirst(UIA.TreeScope_Descendants, cond)
    if win is None:
        print('ABORT: sem container de legenda'); stop.set(); return
    while not stop.is_set():
        t0 = time.time()
        try:
            items = yc._painted_items(win, uia, with_rect=True)
            import youtube_window as ytw
            rows = [str(x).strip().lower() for x in ytw.rows_from_items(items)]
        except Exception as exc:
            rows = []
        uia_rows.append((t0, rows))
        time.sleep(0.05)

threading.Thread(target=read_dom, daemon=True).start()
threading.Thread(target=read_uia, daemon=True).start()
time.sleep(SECONDS)
stop.set()
time.sleep(0.3)
print('dom samples', len(dom), 'uia samples', len(uia_rows))

def age_for(rows, when):
    for t, r in reversed(dom):
        if t > when:
            continue
        if r == rows:
            return (when - t) * 1000.0
    return None

print('--- amostras lado a lado ---')
for when, rows in uia_rows[:6]:
    near = min(dom, key=lambda d: abs(d[0] - when)) if dom else None
    print('uia ', rows)
    print('dom ', near[1] if near else None)
ages, same_now = [], 0
for when, rows in uia_rows:
    if not rows:
        continue
    near = min(dom, key=lambda d: abs(d[0] - when)) if dom else None
    if near and near[1] == rows:
        same_now += 1
    age = age_for(rows, when)
    if age is not None:
        ages.append(age)
ages.sort()
print('uia rows n=%d  iguais ao DOM no instante: %d (%.0f%%)' % (len(uia_rows), same_now,
      100.0 * same_now / max(1, len([1 for r in uia_rows if r[1]]))))
if ages:
    print('ATRASO DA UIA contra o DOM: mediana %.0f ms  p90 %.0f ms  max %.0f ms  (n=%d)' % (
        ages[len(ages)//2], ages[int(len(ages)*0.9)], ages[-1], len(ages)))
