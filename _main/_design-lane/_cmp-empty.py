import importlib.util, json, os, subprocess, sys, tempfile
import subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
spec = importlib.util.spec_from_file_location('audit_shots', os.path.join(HERE, 'audit-shots.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
mode = sys.argv[1] if len(sys.argv) > 1 else 'empty'
themes = sys.argv[2:] or ['cine-last-train', 'cine-blue-hour', 'cine-rainline', 'theme-1']
root = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'docs', 'design-audit-20261021', '_compare')
os.makedirs(root, exist_ok=True)
wd = tempfile.mkdtemp(prefix='cmp-', dir=os.environ.get('TMPDIR', 'I:/cc-tmp'))
html = m.build_surface('cine-last-train', 'panel', wd, float_on=False)
probe = os.path.join(HERE, '_probe-empty.js' if mode == 'empty' else '_probe-filled.js')
jobs = []
for theme in themes:
    jobs.append({
        'name': theme,
        'url': 'file:///' + html.replace(os.sep, '/') + '?cmp=' + mode + '-' + theme + '#panel&theme=' + theme,
        'w': 380, 'h': 900, 'wait': 8000,
        'eval': probe,
        'out': os.path.join(root, mode + '-' + theme + '.png'),
        'outJson': os.path.join(root, mode + '-' + theme + '.json'),
    })
jf = os.path.join(wd, 'jobs.json')
open(jf, 'w', encoding='utf-8').write(json.dumps(jobs, indent=2))
print('workdir', wd)
r = subprocess.run(['node', os.path.join(HERE, 'cdp.mjs'), '--jobs', jf], capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
print(r.stdout[-1500:])
print(r.stderr[-1000:])
print('rc', r.returncode)
