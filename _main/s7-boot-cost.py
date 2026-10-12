#!/usr/bin/env python3
"""S7 - where the startup cost actually goes.

Deliverable 3 of this front. The owner reports a stutter at startup, and until this
front the log could not say WHICH phase cost what, because no sotto: line carried
an hour. This instrument measures the four costs a cold boot pays, on this box, in
this run:

  weights  the three .onnx.data sidecars - the bytes the load reads off the disk
  panel    panel.html's eager asset set vs the five lazy-assets.js defers
  import   the shell module's own import cost, in a FRESH interpreter
  log      the stamp reaches the --log mirror, and the historical count of the
           defect this front fixed, scanned over the whole webview-run.log

Every number in the report is measured by this file. Nothing is copied from a
receipt, and nothing here launches the app.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
LOG = os.path.join(HERE, 'webview-run.log')
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
WORKER = os.path.join(ROOT, 'worker', 'sotto_worker.py')
PANEL_HTML = os.path.join(ROOT, 'app', 'panel', 'panel.html')
LAZY_JS = os.path.join(ROOT, 'app', 'panel', 'lazy-assets.js')
MODEL_DIR = os.path.join(ROOT, 'worker', 'models',
                         'nemotron-3.5-asr-streaming-0.6b-int8')
SIDECARS = ['encoder.onnx.data', 'decoder.onnx.data', 'joint.onnx.data']
BUF = 4 * 1024 * 1024
CREATE_NO_WINDOW = 0x08000000

STAMP_RE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) sotto: (.*)$')

#: The anchors that make a boot readable, in the order they matter. The two
#: model-loaded spellings are the ones the shell itself logs.
TIMELINE = ('SINGLE_INSTANCE', 'PRELOAD_INSTALLED', 'STAGING_SEEN', 'STAGING_LOADED',
            'RECEIVER_READY', 'PANEL_LAZY_GATE_ARMED', 'BRIDGE_START', 'BRIDGE_SPAWNED',
            'WORKER_AUTOSTART', 'STATUS_APPLIED text="model-loading"',
            'STATUS_APPLIED text="model-loaded"', 'BRIDGE_LOAD_MS',
            'BRIDGE_SILENT ms=', 'BRIDGE_SILENT_LOADING', 'BRIDGE_SILENT_LOAD_TIMEOUT',
            'BRIDGE_SILENT_BENIGN', 'BRIDGE_RESTART', 'BRIDGE_EXIT', 'BRIDGE_DEATH',
            'BRIDGE_DEATH_LIFTED', 'BRIDGE_CAPTION_SENT', 'BRIDGE_STOP')

_MODULE = None


def _load_shell_module():
    global _MODULE
    if _MODULE is None:
        sys.path.insert(0, os.path.join(ROOT, 'app', 'webview'))
        spec = importlib.util.spec_from_file_location('sotto_webview_s7cost', SHELL)
        _MODULE = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_MODULE)
    return _MODULE


# --------------------------------------------------------------------------
# weights - the bytes the load reads off the disk
# --------------------------------------------------------------------------

def arm_weights(report):
    """Read the three sidecars once, through a 4 MB buffer, and time it.

    ONE pass. The worker reads these bytes at least TWICE per load: three
    ort.InferenceSession objects (sotto_worker.py:551-553) and then og.Model over
    the same directory (:564). So the number below is a FLOOR on the disk half of
    a load, not the whole of it - the rest is CUDA session creation and the VRAM
    copy, which this instrument cannot measure without a second model in VRAM.
    """
    rows = []
    total = 0
    t_all = time.perf_counter()
    for name in SIDECARS:
        path = os.path.join(MODEL_DIR, name)
        if not os.path.exists(path):
            return [f'ARM weights: {path} is absent - the model dir moved']
        size = os.path.getsize(path)
        t0 = time.perf_counter()
        with open(path, 'rb') as f:
            while f.read(BUF):
                pass
        dt = time.perf_counter() - t0
        rows.append({'file': name, 'bytes': size, 'seconds': round(dt, 3),
                     'MiBps': round(size / 1048576 / dt, 1)})
        total += size
    wall = time.perf_counter() - t_all
    with open(WORKER, encoding='utf-8') as f:
        src = f.read()
    report['weights'] = {
        'rows': rows,
        'total_bytes': total,
        'total_MiB': round(total / 1048576, 1),
        'one_pass_seconds': round(wall, 3),
        'one_pass_MiBps': round(total / 1048576 / wall, 1),
        'buffer_bytes': BUF,
        'worker_inference_sessions': src.count('ort.InferenceSession('),
        'worker_og_model_sites': src.count('og.Model('),
        'reads_per_load': 'at least 2 (3 InferenceSession + 1 og.Model)',
    }
    return []


# --------------------------------------------------------------------------
# panel - the eager asset set vs the five defers
# --------------------------------------------------------------------------

def arm_panel(report):
    """What panel.html loads up front, and what lazy-assets.js holds back.

    The eager set is the <script src> and <link rel=stylesheet> population of the
    document itself, measured on disk. The deferred set is the assets() table of
    lazy-assets.js, also measured on disk. The ratio is the point: the deferred
    bytes are the ones that used to sit on the critical path of the first frame.
    """
    failures = []
    with open(PANEL_HTML, encoding='utf-8') as f:
        html = f.read()
    urls = re.findall(r'(?:src|href)="([^"]+)"', html)
    rows = []
    for url in urls:
        if '://' in url or url.startswith('#') or url.startswith('data:'):
            continue
        path = os.path.normpath(os.path.join(ROOT, 'app', 'panel', url))
        if not os.path.exists(path):
            failures.append(f'ARM panel: {url} is referenced by panel.html and absent')
            continue
        rows.append({'url': url, 'bytes': os.path.getsize(path)})
    eager = sum(r['bytes'] for r in rows)

    with open(LAZY_JS, encoding='utf-8') as f:
        lazy_src = f.read()
    i = lazy_src.find('assets: function')
    j = lazy_src.find('];', i)
    if i < 0 or j < 0:
        return ['ARM panel: the assets() table of lazy-assets.js was not found']
    lazy_urls = re.findall(r"'([^']+)'", lazy_src[i:j])
    lazy_rows = []
    for url in lazy_urls:
        path = os.path.normpath(os.path.join(ROOT, 'app', 'panel', url))
        if not os.path.exists(path):
            failures.append(f'ARM panel: {url} is deferred by lazy-assets.js and absent')
            continue
        lazy_rows.append({'url': url, 'bytes': os.path.getsize(path)})
    lazy = sum(r['bytes'] for r in lazy_rows)
    report['panel'] = {
        'eager_rows': rows,
        'eager_bytes': eager,
        'eager_count': len(rows),
        'lazy_rows': lazy_rows,
        'lazy_bytes': lazy,
        'lazy_count': len(lazy_rows),
        'deferred_share_of_eager': round(lazy / eager, 4) if eager else None,
    }
    return failures


# --------------------------------------------------------------------------
# import - the shell module's own import cost
# --------------------------------------------------------------------------

def arm_import(report):
    """What the shell pays before it does anything, in a FRESH interpreter.

    Measured in a subprocess on purpose: the module is cached in this process, so
    an in-process import would report ~0 and prove nothing.
    """
    shell_dir = os.path.join(ROOT, 'app', 'webview')
    code = ("import sys, time\n"
            "sys.path.insert(0, " + repr(shell_dir) + ")\n"
            "t0 = time.perf_counter()\n"
            "import sotto_webview\n"
            "dt = time.perf_counter() - t0\n"
            "print(round(dt, 3))\n")
    samples = []
    for _ in range(3):
        proc = subprocess.run([sys.executable, '-c', code],
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              cwd=HERE, creationflags=CREATE_NO_WINDOW,
                              timeout=180)
        out = proc.stdout.decode('utf-8', 'replace').strip()
        try:
            samples.append(float(out))
        except ValueError:
            return [f'ARM import: the fresh interpreter printed {out!r}']
    report['import'] = {'samples_seconds': [round(s, 3) for s in samples],
                        'best_seconds': round(min(samples), 3),
                        'n': len(samples)}
    return []


# --------------------------------------------------------------------------
# log - the stamp on the mirror, and the historical count of the defect
# --------------------------------------------------------------------------

def arm_log(report):
    failures = []
    mod = _load_shell_module()

    # 1. The stamp reaches the --log mirror. In-process: _open_log() + log(), then
    #    read the file back. Nothing is launched and no window exists.
    tmp = os.path.join(tempfile.mkdtemp(prefix='s7-log-'), 'probe.log')
    mod._open_log(tmp)
    mod.log('ARM_LOG_PROBE')
    with open(tmp, encoding='utf-8') as f:
        mirrored = f.read().strip()
    m = STAMP_RE.match(mirrored)
    if m is None:
        failures.append(f'ARM log/mirror: the --log line carries no stamp: '
                        f'{mirrored!r}')
    elif m.group(2) != 'ARM_LOG_PROBE':
        failures.append(f'ARM log/mirror: the message is {m.group(2)!r}')

    # 2. The whole-log scan. This file was written by the PRE-patch shell, so it
    #    carries no stamps at all - which is the defect deliverable 2 closes. The
    #    scan is therefore about the ORDER of events, and it SPLITS the anomalous
    #    silences two ways, because they are different facts:
    #      defect   the spawn DID eventually publish model-loaded, so the worker was
    #               LOADING and the watchdog killed it - the defect this front fixes
    #      jam      the spawn NEVER published model-loaded, so the worker was a fake
    #               or a crash loop and the watchdog was doing its job
    #    Counting both together would report 130 and mislabel 127 of them.
    with open(LOG, encoding='utf-8', errors='replace') as f:
        lines = [ln.rstrip('\n') for ln in f]
    boots = sum(1 for ln in lines if 'SINGLE_INSTANCE' in ln)
    spawns = [i for i, ln in enumerate(lines) if 'BRIDGE_SPAWNED' in ln]
    bounds = spawns + [len(lines)]
    loaded_spawns = never_loaded = clean = 0
    defect_lines = []
    jam_lines = []
    for k, s in enumerate(spawns):
        span = lines[s:bounds[k + 1]]
        sil = [s + i + 1 for i, ln in enumerate(span)
               if 'BRIDGE_SILENT ms=' in ln]
        if any('model-loaded' in ln for ln in span):
            loaded_spawns += 1
            if sil:
                defect_lines.extend(sil)
            else:
                clean += 1
        else:
            never_loaded += 1
            jam_lines.extend(sil)

    # 3. The last boot's timeline, so a future run can be compared line by line.
    starts = [i for i, ln in enumerate(lines, 1) if 'SINGLE_INSTANCE' in ln]
    timeline = []
    if starts:
        begin = starts[-1]
        for idx in range(begin - 1, len(lines)):
            ln = lines[idx]
            for anchor in TIMELINE:
                if anchor in ln:
                    timeline.append({'line': idx + 1,
                                     'anchor': anchor,
                                     'text': ln[:150]})
                    break
            if len(timeline) >= 40:
                break
    report['log'] = {
        'log_bytes': os.path.getsize(LOG),
        'log_lines': len(lines),
        'stamped_lines': sum(1 for ln in lines if STAMP_RE.match(ln)),
        'boots': boots,
        'bridge_spawns': len(spawns),
        'spawns_that_loaded': loaded_spawns,
        'spawns_that_never_loaded': never_loaded,
        'clean_loads': clean,
        'defect_instances': len(defect_lines),
        'defect_lines': defect_lines,
        'defect_is_99631': 99631 in defect_lines,
        'never_loaded_jams': len(jam_lines),
        'never_loaded_jam_lines': jam_lines[:20],
        'last_boot_timeline': timeline,
        'note': ('this log was written by the pre-patch shell: 0 stamped lines by '
                 'construction. Durations need one boot with the patched shell.'),
    }
    return failures


# --------------------------------------------------------------------------

def main() -> int:
    report = {}
    failures = []
    for fn in (arm_weights, arm_panel, arm_import, arm_log):
        try:
            failures += fn(report)
        except Exception as exc:  # noqa: BLE001 - an arm that raises is a RED
            failures.append(f'{fn.__name__} raised {exc!r}')
    report['verdict'] = 'PASS' if not failures else 'FAIL'
    report['failures'] = failures
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
