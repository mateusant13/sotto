#!/usr/bin/env python3
"""intake-shots.py -- THE PRINTS.

WHAT IT MAKES
--------------
1. EVERY DEMO of the .zip originals, as the owner shipped it:
     zip1  sotto-app-design-directions.zip        5 designs  (tele..inst)
     zip2  sotto-transcription-panel-designs.zip  5 panels   (teleprompter..instrument)
     zip5  cinematic-transcription-app-designs (2).zip 20 themes (rainline..quiet-marina)
   each demo gets TWO prints:
     <set>-<nn>-<name>.png         the demo as the owner sees it, whole app
     <set>-<nn>-<name>-panel.png   the demo's OWN PANEL, clipped out of it
   The clip is the one the comparison needs: the product's panel is 380x900, so
   the demo's panel is what the product has to look like.

2. THE CURRENT PRODUCT'S PANEL, one print per theme the owner can pick, at the
   real 380x900, with the zip's own script lines in the rail.

THE INSTRUMENT
--------------
`cdp.mjs`, not Edge's own --screenshot: the layout viewport of a headless Edge
screenshot is clamped to 492 px on this box (measured 2026-10-20: 380 -> 492,
520 -> 496, 1000 -> 976), so a screenshot of the panel is a 492 px layout
cropped to 380. cdp.mjs sets the LAYOUT viewport over the DevTools protocol
and the panel is measured and photographed at the owner's 380 px.

THE BUNDLES
------------
The prints are made against the OWNER'S OWN prebuilt bundles -- the single-file
Vite dists that ship with the zips -- and NOT against a rebuild:
     H:\\aireplay\\docs\\design\\sotto-app-design-directions\\dist\\index.html
     H:\\aireplay\\docs\\design\\sotto-transcription-panel-designs\\dist\\index.html
     H:\\sotto\\_main\\_design-lane\\zips\\cinematic-2\\dist\\index.html
so a print is the demo the owner actually has.

THE DELTA (owner, 2026-10-20, verbatim: *"faz cache e teste incremental/delta
e etc pra tu parar de re rodar tudo do zero TODA HORA"*)
----------------------------------------------------------------------
This lane used to re-render EVERY job on EVERY invocation -- 100 demo prints
+ 44 theme prints, ~13 minutes of headless Edge, to produce the SAME PNGs.
Now only the jobs whose INPUTS changed are rendered; the rest are skipped and
the result they had is carried over to `jobs-result.json`, which still
describes EVERY job.

The rules live in `shots-delta.py` (pure: no browser, no network, no write
but the state file) and the state lives in `H:\\sotto\\_cache\\shots-steps.json`.
`--no-delta` is the escape hatch: it re-renders everything.

THE PLAN IS STILL COMPLETE
--------------------------
`data/jobs.json` keeps the WHOLE plan -- it is the record of what exists --
and the jobs that actually run are written to a throwaway file inside the
scratch workdir, which is what `cdp.mjs` is given.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import shot  # noqa: E402

# `shots-delta.py` has a DASH in its name, so it cannot be `import`ed by
# name: it is loaded by path, the way `panel-measure.py` is.
_spec = importlib.util.spec_from_file_location(
    'shots_delta', os.path.join(HERE, 'shots-delta.py'))
shots_delta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shots_delta)

_spec = importlib.util.spec_from_file_location(
    'panel_measure', os.path.join(HERE, 'panel-measure.py'))
panel_measure = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(panel_measure)

CDP = os.path.join(HERE, 'cdp.mjs')
PROBE_DEMO = os.path.join(HERE, 'probe-demo.js')
PROBE_PANEL = os.path.join(HERE, 'probe-panel.js')

# THE DEMO BUNDLES -- the owner's own prebuilt single-file dists, committed in
# the repo at `_main/zip-mockups/` (receipt-20261013-all-five-zips-build.md).
# MEASURED 2026-10-20: zip-A, zip-D and zip-E are BYTE-IDENTICAL to the other
# copies on this box (sha256 9D1AF1F5.. / 12793DAC.. / FD4601AE..), so the five
# files in that folder are ONE set and are used for all five prints.
BUNDLE_A = 'file:///H:/sotto/_main/zip-mockups/zip-A-directions.html'
BUNDLE_B = 'file:///H:/sotto/_main/zip-mockups/zip-E-panels.html'
BUNDLE_C = 'file:///H:/sotto/_main/zip-mockups/zip-B-themes.html'
BUNDLE_C1 = 'file:///H:/sotto/_main/zip-mockups/zip-C-panels.html'
BUNDLE_C2 = 'file:///H:/sotto/_main/zip-mockups/zip-D-themes.html'

# THE DEMOS, in the zips' own order.
A_DEMOS = [('01', 'teleprompter'), ('02', 'broadcast'), ('03', 'manuscrito'),
           ('04', 'cartao-de-cinema'), ('05', 'instrumento')]
B_DEMOS = [('01', 'teleprompter'), ('02', 'broadcast'), ('03', 'manuscrito'),
           ('04', 'cartao-de-cinema'), ('05', 'instrumento')]
# zip3 = cinematic (c0): ten themes, ArrowRight cycles, opens on index 0.
C_DEMOS = [('01', 'midnight-rain'), ('02', 'warm-hour'), ('03', 'velvet-dusk'),
           ('04', 'study-light'), ('05', 'tideline'), ('06', 'motel-glow'),
           ('07', 'paper-moon'), ('08', 'quiet-streets'), ('09', 'last-reel'),
           ('10', 'north-fog')]
# zip4 = cinematic (1) (c1): ten panels, ArrowRight cycles, opens on index 0.
C1_DEMOS = [('01', 'glass-cards'), ('02', 'hairline'), ('03', 'paper'), ('04', 'quotes'),
            ('05', 'ledger'), ('06', 'feed'), ('07', 'bubbles'), ('08', 'timeline'),
            ('09', 'chips'), ('10', 'gutter')]
C2_DEMOS = [('01', 'rainline'), ('02', 'blue-plate'), ('03', 'cellar'), ('04', 'linen'),
            ('05', 'side-b'), ('06', 'north-window'), ('07', 'adobe'), ('08', 'glasshouse'),
            ('09', 'film-club'), ('10', 'nightswim'), ('11', 'reading-hour'), ('12', 'snowline'),
            ('13', 'last-train'), ('14', 'dusk-highway'), ('15', 'harbor'), ('16', 'fireside'),
            ('17', 'blue-hour'), ('18', 'paper-rain'), ('19', 'terrace'), ('20', 'quiet-marina')]

# THE PRODUCT'S OWN THEME IDS (themes.js + panel-designs.js + zipc-panels.js).
PRODUCT_THEMES = (
    ['theme-1', 'theme-2', 'theme-3', 'theme-4', 'theme-5']
    + ['cine-midnight-rain', 'cine-warm-hour', 'cine-velvet-dusk', 'cine-study-light',
       'cine-tideline-body', 'cine-north-fog', 'cine-motel-glow', 'cine-paper-moon',
       'cine-quiet-streets', 'cine-last-reel', 'cine-cafe', 'cine-tideline',
       'cine-rainglass', 'cine-fieldnotes', 'cine-dustlight', 'cine-rooftop',
       'cine-analog', 'cine-shelves', 'cine-ember', 'cine-rainline', 'cine-blue-hour',
       'cine-cellar', 'cine-linen', 'cine-reading-hour', 'cine-last-train']
    + ['pd-tele', 'pd-bcast', 'pd-mano', 'pd-cine', 'pd-instr']
    + ['GlassCards', 'Hairline', 'Paper', 'Quotes', 'Ledger',
       'Feed', 'Bubbles', 'Timeline', 'Chips', 'Gutter']
)


def demo_jobs(outdir, jobs, sets, CLIPS=False):
    """Every demo of every zip that has a prebuilt bundle on disk."""
    for (num, name), key in (zip(A_DEMOS, '12345') if 'zipA' in sets else []):
        base = 'zip1-directions-%s-%s' % (num, name)
        if not CLIPS:
            jobs.append({'name': base, 'set': 'zipA', 'url': BUNDLE_A, 'w': 1600, 'h': 1000, 'wait': 2600,
                         'keys': [key], 'out': os.path.join(outdir, base + '.png'),
                         'eval': PROBE_DEMO, 'outJson': os.path.join(outdir, base + '.json')})
        jobs.append({'name': base + '-panel', 'set': 'zipA', 'url': BUNDLE_A, 'w': 1600, 'h': 1000, 'wait': 2600,
                     'keys': [key], 'clip': '.sotto-panel',
                     'out': os.path.join(outdir, base + '-panel.png')})

    for (num, name), key in (zip(B_DEMOS, '12345') if 'zipB' in sets else []):
        base = 'zip2-panels-%s-%s' % (num, name)
        jobs.append({'name': base, 'set': 'zipB', 'url': BUNDLE_B, 'w': 1600, 'h': 1800, 'wait': 2600,
                     'keys': [key], 'out': os.path.join(outdir, base + '.png'),
                     'eval': PROBE_DEMO, 'outJson': os.path.join(outdir, base + '.json')})
        jobs.append({'name': base + '-panel', 'set': 'zipB', 'url': BUNDLE_B, 'w': 1600, 'h': 1800, 'wait': 2600,
                     'keys': [key], 'clip': '.panel-in',
                     'out': os.path.join(outdir, base + '-panel.png')})

    # The c2 app opens on THEMES[2] ('cellar') and ArrowRight cycles forward.
    for i, (num, name) in (enumerate(C2_DEMOS) if 'zipC2' in sets else []):
        presses = (i - 2) % len(C2_DEMOS)
        keys = ['ArrowRight'] * presses
        base = 'zip5-cinematic-2-%s-%s' % (num, name)
        jobs.append({'name': base, 'set': 'zipC2', 'url': BUNDLE_C2, 'w': 1600, 'h': 1000, 'wait': 3000,
                     'keys': keys, 'after': 900,
                     'out': os.path.join(outdir, base + '.png'),
                     'eval': PROBE_DEMO, 'outJson': os.path.join(outdir, base + '.json')})
        jobs.append({'name': base + '-panel', 'set': 'zipC2', 'url': BUNDLE_C2, 'w': 1600, 'h': 1000, 'wait': 3000,
                     'keys': keys, 'after': 900, 'clip': 'aside',
                     'out': os.path.join(outdir, base + '-panel.png')})

    # zip3 = cinematic (c0): ten themes, ArrowRight cycles, opens on index 0.
    for i, (num, name) in (enumerate(C_DEMOS) if 'zipC' in sets else []):
        keys = ['ArrowRight'] * i
        base = 'zip3-cinematic-%s-%s' % (num, name)
        jobs.append({'name': base, 'set': 'zipC', 'url': BUNDLE_C, 'w': 1600, 'h': 1000, 'wait': 3000,
                     'keys': keys, 'after': 900,
                     'out': os.path.join(outdir, base + '.png'),
                     'eval': PROBE_DEMO, 'outJson': os.path.join(outdir, base + '.json')})
        jobs.append({'name': base + '-panel', 'set': 'zipC', 'url': BUNDLE_C, 'w': 1600, 'h': 1000, 'wait': 3000,
                     'keys': keys, 'after': 900, 'clip': 'aside',
                     'out': os.path.join(outdir, base + '-panel.png')})

    # zip4 = cinematic (1) (c1): ten panels, ArrowRight cycles, opens on index 0.
    for i, (num, name) in (enumerate(C1_DEMOS) if 'zipC1' in sets else []):
        keys = ['ArrowRight'] * i
        base = 'zip4-cinematic-1-%s-%s' % (num, name)
        jobs.append({'name': base, 'set': 'zipC1', 'url': BUNDLE_C1, 'w': 1600, 'h': 1000, 'wait': 3000,
                     'keys': keys, 'after': 900,
                     'out': os.path.join(outdir, base + '.png'),
                     'eval': PROBE_DEMO, 'outJson': os.path.join(outdir, base + '.json')})
        jobs.append({'name': base + '-panel', 'set': 'zipC1', 'url': BUNDLE_C1, 'w': 1600, 'h': 1000, 'wait': 3000,
                     'keys': keys, 'after': 900, 'clip': 'aside',
                     'out': os.path.join(outdir, base + '-panel.png')})


def panel_jobs(workroot, outdir, themes, jobs):
    """The product's panel, at 380x900, one workdir per theme.

    `srcRoot` and `theme` are the DELTA's inputs: the built document lives in
    a `tempfile.mkdtemp()` that is deleted at the end of the run, so the
    fingerprint is taken over the workdir's CONTENTS -- the document itself
    and the sheets and scripts it reads -- and not over a path that
    disappears. `theme` is what tells the delta which theme sheet is this
    render's own (see `shots-delta.py`).
    """
    for theme in themes:
        wd = os.path.join(workroot, theme.replace('/', '_'))
        os.makedirs(wd, exist_ok=True)
        html = panel_measure.build(theme, 'panel', wd)
        base = 'current-%s' % theme
        jobs.append({'name': base, 'set': 'current', 'url': 'file:///' + html.replace(os.sep, '/'),
                     'w': 380, 'h': 900, 'wait': 7000,
                     'srcRoot': wd, 'theme': theme,
                     'out': os.path.join(outdir, base + '.png'),
                     'eval': PROBE_PANEL, 'outJson': os.path.join(outdir, base + '.json')})


def split_jobs(jobs, state, no_delta=False, fingerprints=None):
    """(hits, misses). PURE: no browser, no network, no write.

    The delta's whole point: a job whose inputs did not change is SKIPPED, a
    job whose inputs changed is NOT skipped, and a job with no input at all is
    never a hit. The honesty rule is `shots-delta.decide()` and lives there.
    """
    if no_delta:
        return [], list(jobs)
    hits, misses = [], []
    for job in jobs:
        name = job.get('name')
        fp = (fingerprints or {}).get(name)
        if fp is None:
            fp = shots_delta.fingerprint(job)
        entry = (state.get('jobs') or {}).get(name)
        hit, _reason = shots_delta.decide(job, entry, state, fp)
        if hit:
            hits.append(job)
        else:
            misses.append(job)
    return hits, misses


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.join(REPO, 'docs', 'design-intake'))
    ap.add_argument('--only', default='all', choices=('all', 'demos', 'current'))
    ap.add_argument('--sets', default='', help='comma list of zip sets: zipA,zipB,zipC,zipC1,zipC2')
    ap.add_argument('--clips', action='store_true', help='only the clipped panel prints')
    ap.add_argument('--themes', default='')
    ap.add_argument('--no-delta', action='store_true',
                    help='the escape hatch: re-render EVERY job, whatever the cache says')
    ap.add_argument('--state', default=shots_delta.DEFAULT_STATE,
                    help='the delta state file (default: %s)' % shots_delta.DEFAULT_STATE)
    args = ap.parse_args()

    demo_dir = os.path.join(args.root, 'demos')
    cur_dir = os.path.join(args.root, 'current')
    data_dir = os.path.join(args.root, 'data')
    for d in (demo_dir, cur_dir, data_dir):
        os.makedirs(d, exist_ok=True)

    jobs = []
    workroot = tempfile.mkdtemp(prefix='sotto-intake-', dir=os.environ.get('TMPDIR', 'I:/cc-tmp'))
    try:
        if args.only in ('all', 'demos'):
            demo_jobs(demo_dir, jobs, set((args.sets or 'zipA,zipB,zipC,zipC1,zipC2').split(',')), args.clips)
        if args.only in ('all', 'current'):
            themes = [t.strip() for t in args.themes.split(',') if t.strip()] or PRODUCT_THEMES
            panel_jobs(workroot, cur_dir, themes, jobs)

        # THE COMPLETE PLAN, always: it is the record of what exists.
        jf = os.path.join(data_dir, 'jobs.json')
        with open(jf, 'w', encoding='utf-8', newline='\n') as fh:
            json.dump(jobs, fh, indent=1)

        # THE DELTA: only the jobs whose inputs changed are rendered.
        state, err = shots_delta.load_state(args.state)
        if err:
            print('state: %s -- every job runs again' % err)
        fingerprints = {}
        if not args.no_delta:
            for job in jobs:
                fingerprints[job.get('name')] = shots_delta.fingerprint(job)
        hits, misses = split_jobs(jobs, state, no_delta=args.no_delta,
                                  fingerprints=fingerprints)
        print('jobs: %d  hits: %d  misses: %d' % (len(jobs), len(hits), len(misses)))

        new_results = {}
        if misses:
            # the jobs that RUN go to a throwaway file; `jobs.json` stays the
            # complete plan.
            runf = os.path.join(workroot, 'jobs-run.json')
            with open(runf, 'w', encoding='utf-8', newline='\n') as fh:
                json.dump(misses, fh, indent=1)
            outf = os.path.join(workroot, 'jobs-run-result.json')
            proc = subprocess.run(['node', CDP, '--jobs', runf, '--json', outf],
                                   capture_output=True, timeout=3600)
            sys.stdout.write(proc.stdout.decode('utf-8', 'replace')[-4000:])
            if proc.returncode != 0:
                sys.stderr.write(proc.stderr.decode('utf-8', 'replace')[-2000:])
            if os.path.isfile(outf):
                with open(outf, encoding='utf-8') as fh:
                    data = json.load(fh)
                for r in (data.get('jobs') or []):
                    new_results[r.get('name')] = r

        # THE FINAL RESULT describes EVERY job: the hits with the result they
        # had, the misses with the result they just got.
        results = []
        for job in jobs:
            r = new_results.get(job.get('name'))
            if r is None:
                entry = (state.get('jobs') or {}).get(job.get('name')) or {}
                r = dict(entry.get('result') or {})
                r['name'] = job.get('name')
                r['url'] = job.get('url')
                r['viewport'] = [job.get('w'), job.get('h')]
                r['dsf'] = job.get('dsf', 1)
                r['shot'] = job.get('out')
                if job.get('outJson'):
                    r['json'] = job.get('outJson')
            results.append(r)
        with open(os.path.join(data_dir, 'jobs-result.json'), 'w', encoding='utf-8', newline='\n') as fh:
            json.dump({'jobs': results}, fh, indent=2)

        # WHAT RAN IS WHAT IS RECORDED. A job that FAILED is not recorded:
        # a failure is never reused as if it were a pass.
        recorded = 0
        for job in misses:
            r = new_results.get(job.get('name'))
            if not r or r.get('error'):
                continue
            entry, _reason = shots_delta.record(job, r, state, fingerprints.get(job.get('name')))
            if entry:
                recorded += 1
        shots_delta.save_state(state, args.state)
        print('recorded: %d of %d misses' % (recorded, len(misses)))
    finally:
        shutil.rmtree(workroot, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
