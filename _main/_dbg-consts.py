import importlib.util, json, os, sys
WEBVIEW = r'H:\sotto\app\webview'
SHELL = os.path.join(WEBVIEW, 'sotto_webview.py')
sys.path.insert(0, WEBVIEW)
spec = importlib.util.spec_from_file_location('dbg_shell', SHELL)
m = importlib.util.module_from_spec(spec)
sys.modules['dbg_shell'] = m
spec.loader.exec_module(m)
consts = m.SottoHost.dispatch.__code__.co_consts
out = {
    'consts': [c for c in consts if isinstance(c, str)],
    'has_panel_surface': 'panel-surface' in consts,
    'has_stats': 'stats' in consts,
    'nconsts': len(consts),
}
open(r'H:\sotto\_main\_dbg-consts.json', 'w', encoding='utf-8').write(json.dumps(out, indent=2))
