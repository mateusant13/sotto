# ORACLE for docs/oss-approaches-20261006.md -- "is what that document recommends still
# what the code does?". Four claims, each read out of the LIVE tree.
#
# NEGATIVE ARM (2026-10-11 -- closes audit row #57, "\`_oss_oracle\` nao tem braco negativo").
# The default run is unchanged (same four checks, same GREEN/RED wording, same exit 0/3).
# \`--neg-arm\` builds a MUTANT TREE in TMPDIR -- the four inputs copied and exactly ONE
# changed per arm -- and requires the FAILING SET to be exactly the check that arm targets.
# A mutant that also breaks an unrelated check is reported, not hidden.
import json, os, re, shutil, sys, tempfile
from pathlib import Path

REPO = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def checks(root, emit=print):
    """Returns {name: bool}. \`emit\` receives the PASS/FAIL lines (default: stdout)."""
    c = json.loads((root / 'worker/config.json').read_text(encoding='utf-8'))
    w = (root / 'worker/sotto_worker.py').read_text(encoding='utf-8')
    model_dir = root / 'worker' / c['model']['dir'] / 'genai_config.json'
    g = json.loads(model_dir.read_text(encoding='utf-8'))
    f = root / 'app/panel/caption-formulation.js'
    cf = f.read_text(encoding='utf-8') if f.exists() else ''
    out = {}

    def chk(n, cond):
        emit(('PASS ' if cond else 'FAIL ') + n)
        return bool(cond)

    out['C1'] = chk('C1 VAD is ON and the gated chunk (process() -> None) is handled (worker/config.json + run_chunk)',
                    c['model']['use_vad'] is True and 'vad_gated_chunks' in w)
    # C2 RE-BASELINED 2026-10-11, and the reason matters more than the new pattern. The claim
    # is SUBSTANTIVE (no agreement buffer in the worker; the renderer owns it) and the two
    # NEGATIVE guards below still carry it: re-measured, `HypothesisBuffer` and `commited` are
    # both ABSENT from worker/ (0 matches) and `agreedPrefix|LocalAgreement` is absent from the
    # whole of worker/ (0 matches). What had aged was the POSITIVE spelling: the old pattern
    # pinned `emit(type="caption", text=text`, a one-line call the worker no longer has -- it
    # now puts a caption DICT (sotto_worker.py:3620 `self._captions.put({"type": "caption",
    # "text": text, ...})`, and :2928 the other channel). A pattern that pins a call's spelling
    # is a drift detector for the spelling, not an oracle for the claim; this one now matches
    # the dict form, and the negative arm's M2 (a copy with `HypothesisBuffer` added) proves it
    # can still say NO.
    out['C2'] = chk('C2 worker caption is still a raw run_chunk passthrough, no agreement buffer',
                    bool(re.search(r'text,\s*n\s*=\s*asr\.run_chunk', w))
                    and bool(re.search(r'"type":\s*"caption"', w))
                    and bool(re.search(r'"text":\s*text', w))
                    and 'HypothesisBuffer' not in w and 'commited' not in w)
    out['C3'] = chk('C3 renderer formulation extracted to caption-formulation.js with LocalAgreement-2 + audio-gap boundary',
                    'agreedPrefixLength' in cf and 'SENTENCE_GAP_S' in cf)
    out['C4'] = chk('C4 model geometry is 560 ms (chunk_samples 8960 @16k) with a bundled silero VAD',
                    g['model']['chunk_samples'] == 8960 and 'vad' in g['model'])
    return out


def _tree(tmp, cfg=None, worker=None, genai=None, js=None):
    """A mutant tree: the four live inputs copied, then the caller's edit applied."""
    live_cfg = json.loads((REPO / 'worker/config.json').read_text(encoding='utf-8'))
    model_rel = 'worker/' + live_cfg['model']['dir'] + '/genai_config.json'
    src = {'worker/config.json': None, 'worker/sotto_worker.py': None,
           model_rel: None, 'app/panel/caption-formulation.js': None}
    edits = {'worker/config.json': cfg, 'worker/sotto_worker.py': worker, model_rel: genai,
             'app/panel/caption-formulation.js': js}
    for rel in src:
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = (REPO / rel).read_text(encoding='utf-8')
        if edits[rel] is not None:
            text = edits[rel](text)
        dst.write_text(text, encoding='utf-8')
    return tmp


def neg_arm():
    base = Path(tempfile.mkdtemp(prefix='sotto-oss-neg-', dir=os.environ.get('TMPDIR') or None))
    try:
        arms = [
            ('M1 config use_vad=false', {'C1'}, dict(cfg=lambda t: t.replace('"use_vad": true', '"use_vad": false'))),
            ('M2 worker gains HypothesisBuffer', {'C2'}, dict(worker=lambda t: t + '\n# HypothesisBuffer\n')),
            ('M3 js loses agreedPrefixLength', {'C3'}, dict(js=lambda t: t.replace('agreedPrefixLength', 'xPrefixLength'))),
            ('M4 model chunk_samples=1', {'C4'}, dict(genai=lambda t: json.dumps(
                {**json.loads(t), 'model': {**json.loads(t)['model'], 'chunk_samples': 1}}))),
        ]
        # THE CONTROL IS A MEASUREMENT, NOT A LABEL (repaired 2026-10-11 after the audit-row
        # sweep proved the first version of this arm printed "the live tree is GREEN" from
        # `all(results)` -- the MUTANT comparisons -- and never probed the live tree at all.
        # That is the same failure mode as live-vs-history-source-oracle.js: a gate that supplies
        # the thing it then finds. `checks(REPO)` is now called for real, its four verdicts are
        # printed, and the arm FAILS if the live tree is not green.
        live = checks(REPO)
        live_green = all(live.values())
        results = []
        for name, expected, kwargs in arms:
            sub = base / name.split()[0]
            sub.mkdir(parents=True, exist_ok=True)
            tree = _tree(sub, **kwargs)
            got = {k for k, v in checks(tree, lambda *a: None).items() if not v}
            ok = got == expected
            results.append(ok)
            print(('PASS ' if ok else 'FAIL ') + f'NEG {name}: failing set {sorted(got) or "[]"}'
                  + f' (expected {sorted(expected)})')
        print(('PASS ' if live_green else 'FAIL ')
              + 'NEG control: the LIVE tree probed in this same process -> '
              + ('GREEN' if live_green else 'RED')
              + f'  {dict(sorted(live.items()))}')
        ok = all(results) and live_green
        print('NEG-ARM', 'PASS' if ok else 'FAIL')
        return 0 if ok else 1
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == '__main__':
    if '--neg-arm' in sys.argv:
        raise SystemExit(neg_arm())
    res = checks(REPO)
    good = all(res.values())
    print('ORACLE', 'GREEN (doc still true)' if good else 'RED (doc is now stale - rewrite it)')
    raise SystemExit(0 if good else 3)
