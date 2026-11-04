import importlib.util, json, os, subprocess, sys, tempfile
import subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location('audit_shots', os.path.join(HERE, 'audit-shots.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
wd = tempfile.mkdtemp(prefix='search-', dir=os.environ.get('TMPDIR', 'I:/cc-tmp'))
html = m.build_surface('cine-last-train', 'panel', wd, float_on=False)
job = {
    'name': 'search-last-train',
    'url': 'file:///' + html.replace(os.sep, '/') + '?search=1#panel&theme=cine-last-train',
    'w': 380, 'h': 900, 'wait': 8000,
    'eval': os.path.join(HERE, '_probe-search.js'),
    'outJson': os.path.join(wd, 'search.json'),
}
jf = os.path.join(wd, 'jobs.json')
open(jf, 'w', encoding='utf-8').write(json.dumps([job], indent=2))
r = subprocess.run(['node', os.path.join(HERE, 'cdp.mjs'), '--jobs', jf], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
print(r.stdout[-800:])
print(r.stderr[-500:])
print('rc', r.returncode)
