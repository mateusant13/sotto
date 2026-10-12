# =============================================================================
# audit-rows-byte-claims.py -- ONE instrument for THREE open register rows that
# are decided by BYTES alone: a count in a doc, a comment that contradicts the
# code around it, and a citation of a line number in another file.
#
#   #54  AGENTS/README list 5 config keys; the file has 13 (now 8)
#   #33  stale/contradictory comments in sotto_webview.py about the OFFSCREEN
#        cure (sotto_webview.py:1054 in the revision the row was written on)
#   #48  AGENTS.md cites worker-bridge.js:133 as the STATE_MAP
#
# No launch of any kind: it reads bytes, parses JSON and greps. The one thing it
# must NOT do is trust the line numbers the register carries -- both AGENTS.md
# and the shell are being edited by other lanes while this runs -- so every
# anchor is located by CONTENT and the line number is REPORTED, not assumed.
#
# EVERY arm must FLIP on a MUTANT under %TEMP%: an extra key in a config copy, a
# deleted sentence in a shell copy, a reverted citation in an AGENTS.md copy.
#
# Usage:  py -3 _main/audit-rows-byte-claims.py [--neg-arm]
# =============================================================================
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
CONFIG = os.path.join(ROOT, 'worker', 'config.json')
AGENTS = os.path.join(ROOT, 'AGENTS.md')
WORKER_README = os.path.join(ROOT, 'worker', 'README.md')
SHELL = os.path.join(ROOT, 'app', 'webview', 'sotto_webview.py')
BRIDGE_JS = os.path.join(ROOT, 'app', '_legacy-electron', 'worker-bridge.js')
REGISTER = os.path.join(ROOT, 'docs', 'audit', '00-MAPA-CONSOLIDADO.md')

BT = chr(96)                       # the backtick, kept out of this file's prose
#: The two sentences AGENTS.md carries about the startup flash, both still there
#: (row #46: they contradict each other and neither was retracted).
CLAIM_ZERO_OF_41 = 'arm P 0 of 41 samples at a 200 ms cadence'
CLAIM_VISIBLE_7S = 'THE PANEL IS VISIBLE AT STARTUP, FROM ~50 ms TO ~7 s'
STALE_OFFSCREEN = 'startup flash is handled by the OFFSCREEN creation position below.'
OFFSCREEN_REMOVED = 'The ' + BT + 'OFFSCREEN = -32000' + BT + ' cure was REMOVED'
BRIDGE_CITE = 'worker-bridge.js:**114**'
EXECUTABLE_OFFSCREEN = re.compile(r'^\s*OFFSCREEN\s*=|\.\w+\([^)]*OFFSCREEN')


def say(message):
    print(message, flush=True)


def sha256_file(path):
    with open(path, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest().upper()


def read(path):
    with open(path, encoding='utf-8', newline='') as handle:
        return handle.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(text)


def line_of(text, anchor):
    index = text.find(anchor)
    if index < 0:
        return 0
    return text.count('\n', 0, index) + 1


def leaf_paths(obj, prefix=''):
    out = []
    for key, value in obj.items():
        path = prefix + '.' + key if prefix else key
        if isinstance(value, dict):
            out.extend(leaf_paths(value, path))
        else:
            out.append(path)
    return out


MUTANTS = {}


def build_mutants(work):
    config = json.loads(read(CONFIG))
    inflated = dict(config)
    # PAD TO THE NUMBER THE DOCUMENT CLAIMS, NOT BY A FIXED COUNT OF EXTRAS.
    # This builder used to add exactly 8 extras, which produced 13 keys only
    # while the live config held 5. It now holds 6 (redux_live arrived with the
    # S3 lane), so 5+8=13 had become 14 and the r54 reading no longer flipped:
    # the mutant stopped being a control and reported nothing. Padding to the
    # claimed number keeps the mutant meaning -- a config with exactly 13
    # top-level keys, which is what the doc sentence says the file has.
    claimed = 13
    missing = claimed - len(inflated)
    if missing < 0:
        say('SETUP ERROR: the live config already carries %d top-level keys, '
            'more than the %d the row claims; the r54 row must be re-measured '
            'before this mutant means anything' % (len(inflated), claimed))
        raise SystemExit(2)
    for index in range(missing):
        inflated['extra_key_%d' % index] = index
    MUTANTS['config_13_keys'] = os.path.join(work, 'config-13-keys.json')
    write(MUTANTS['config_13_keys'], json.dumps(inflated, indent=2) + '\n')
    shell = read(SHELL)
    # RE-ANCHORED 2026-10-11: the live shell no longer CONTAINS the stale sentence (row #33
    # was closed in the product code), so the mutant now RESTORES it instead of deleting it,
    # and the anchor is the corrected comment line it gets appended after. A gate that needs
    # the defect present to build its own control is a gate that pins the defect.
    RESTORE_AFTER = '        # it sent readers looking for code that is not there.'
    if shell.count(RESTORE_AFTER) != 1:
        say('SETUP ERROR: the r33 restore anchor appears '
            + str(shell.count(RESTORE_AFTER)) + ' time(s)')
        raise SystemExit(2)
    _nl = '\r\n' if '\r\n' in shell else '\n'
    MUTANTS['shell_stale_comment_restored'] = os.path.join(
        work, 'sotto_webview_stale_comment_restored.py')
    write(MUTANTS['shell_stale_comment_restored'],
          shell.replace(RESTORE_AFTER,
                        RESTORE_AFTER + _nl + '        # The ' + STALE_OFFSCREEN, 1))
    agents = read(AGENTS)
    MUTANTS['agents_old_citation'] = os.path.join(
        work, 'AGENTS-with-old-citation.md')
    write(MUTANTS['agents_old_citation'],
          agents.replace(BRIDGE_CITE, 'worker-bridge.js:**133**'))
    if agents.count(CLAIM_ZERO_OF_41) != 1:
        say('SETUP ERROR: the r46 anchor appears '
            + str(agents.count(CLAIM_ZERO_OF_41)) + ' time(s)')
        raise SystemExit(2)
    MUTANTS['agents_one_claim_removed'] = os.path.join(
        work, 'AGENTS-one-flash-claim-removed.md')
    write(MUTANTS['agents_one_claim_removed'],
          agents.replace(CLAIM_ZERO_OF_41, 'arm P was sampled'))
    return agents.count(BRIDGE_CITE)


# ---------------------------------------------------------------------------
# arms
# ---------------------------------------------------------------------------
def arm_r54(ctx):
    config = json.loads(read(ctx['config']))
    register = read(REGISTER)
    row_line, row = 0, ''
    for index, line in enumerate(register.split('\n')):
        if line.startswith('| 54 |'):
            row_line, row = index + 1, line
            break
    leaves = leaf_paths(config)
    semantic = [leaf for leaf in leaves if '_comment' not in leaf]
    readme = read(WORKER_README).split('\n')
    return {
        'config': ctx['config'],
        'top_level_keys': sorted(config.keys()),
        'top_level_count': len(config),
        'leaf_count_all': len(leaves),
        'leaf_count_non_comment': len(semantic),
        'non_comment_leaves': sorted(semantic),
        'register_row_line': row_line,
        'register_row': row[:130],
        'readme_lines_184_185': readme[183:185],
        'numbers_stale': not (len(config) in (13, 8)),
    }


def arm_r33(ctx):
    shell = read(ctx['shell'])
    lines = shell.split('\n')
    occurrences = []
    executable = []
    for index, line in enumerate(lines):
        if 'OFFSCREEN' not in line:
            continue
        occurrences.append(index + 1)
        if EXECUTABLE_OFFSCREEN.search(line):
            executable.append(index + 1)
    stale_line = line_of(shell, STALE_OFFSCREEN)
    return {
        'shell': ctx['shell'],
        'offscreen_lines': occurrences,
        'stale_comment_line': stale_line,
        'stale_comment_text': STALE_OFFSCREEN,
        'removal_note_line': line_of(shell, OFFSCREEN_REMOVED),
        'executable_offscreen_uses': executable,
        'stale_comment_present': bool(stale_line and not executable),
    }


def arm_r48(ctx):
    agents = read(ctx['agents'])
    bridge_lines = read(BRIDGE_JS).split('\n')
    declared = [index + 1 for index, line in enumerate(bridge_lines)
                if 'STATE_MAP = {' in line]
    lookup = [index + 1 for index, line in enumerate(bridge_lines)
              if 'STATE_MAP[' in line]
    cite_line = line_of(agents, BRIDGE_CITE)
    return {
        'bridge_js': BRIDGE_JS,
        'state_map_declared_line': declared,
        'state_map_lookup_line': lookup,
        'agents_cite_line': cite_line,
        'agents_sentence': (agents.split('\n')[cite_line - 1][:200]
                            if cite_line else ''),
        # The row's DEFECT is a WRONG citation, so the key is the negation: a
        # correct AGENTS.md reads False here, and the mutant that restores the
        # old :133 citation reads True.
        'citation_wrong': not bool(cite_line and declared and declared[0] == 114),
    }


def arm_r46(ctx):
    """#46: the two contradictory flash claims in AGENTS.md, located by content."""
    agents = read(ctx['agents'])
    zero = line_of(agents, CLAIM_ZERO_OF_41)
    visible = line_of(agents, CLAIM_VISIBLE_7S)
    return {
        'agents': ctx['agents'],
        'claim_zero_of_41_line': zero,
        'claim_visible_7s_line': visible,
        'contradiction_present': bool(zero and visible),
        'flash_itself_measured': False,
        'flash_gap': ('both numbers come from instruments that LAUNCH the shell '
                      '(panel-startup-visibility-oracle, '
                      'panel-startup-flash-census); the owner order of '
                      '2026-10-11 forbids that launch, so which number is true '
                      'is NOT MEASURED here -- only that both sentences are '
                      'still in the file'),
    }


ARMS = ('r54', 'r33', 'r48', 'r46')
MEASURE = {'r54': arm_r54, 'r33': arm_r33, 'r48': arm_r48, 'r46': arm_r46}
DEFECT_KEY = {'r54': 'numbers_stale', 'r33': 'stale_comment_present',
              'r48': 'citation_wrong', 'r46': 'contradiction_present'}
ROW_OF = {
    'r54': 'audit #54: AGENTS/README listam 5 chaves do config; o ficheiro tem '
           '13 (hoje 8)',
    'r33': 'audit #33: comentarios obsoletos/contraditorios no sotto_webview.py '
           'sobre a cura OFFSCREEN',
    'r48': 'audit #48: AGENTS.md cita worker-bridge.js:133 como STATE_MAP '
           '(declarado em :114)',
    'r46': 'audit #46: AGENTS.md contradiz-se sobre o painel no arranque '
           '("0 de 41" vs "visivel 50 ms-7 s")',
}
# r33 flipped to False on 2026-10-11: the stale sentence was deleted from the live shell
# (`sotto_webview.py:3552`), which is what this arm exists to notice. The mutant now restores
# it, so the pair still shows both colours.
EXPECT_LIVE = {'r54': True, 'r33': False, 'r48': False, 'r46': True}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Three open register rows decided by bytes: a doc count, a '
                    'stale comment, a cross-file citation. Launches nothing.')
    parser.add_argument('--neg-arm', action='store_true')
    parsed = parser.parse_args(argv)

    work = tempfile.mkdtemp(prefix='sotto-audit-bytes-')
    say('audit-rows-byte-claims -- three open rows, one instrument')
    say('work       : ' + work)
    for path in (CONFIG, AGENTS, WORKER_README, SHELL, BRIDGE_JS, REGISTER):
        say('  ' + path.ljust(52) + ' ' + str(os.path.getsize(path)).ljust(8)
            + ' B sha256 ' + sha256_file(path)[:16])
    say('launches   : NOTHING (bytes, JSON.parse, greps)')

    cites = build_mutants(work)
    say('')
    say('mutants    :')
    for key, path in MUTANTS.items():
        say('  ' + key.ljust(24) + ' ' + os.path.basename(path).ljust(36) + ' '
            + str(os.path.getsize(path)).ljust(8) + ' B sha256 '
            + sha256_file(path)[:16])
    say('note       : the AGENTS.md citation ' + BRIDGE_CITE + ' occurs '
        + str(cites) + ' time(s) in the live file; the mutant reverts it')

    def context(config, shell, agents):
        return {'config': config, 'shell': shell, 'agents': agents}

    def measure(ctx):
        results = {}
        for name in ARMS:
            try:
                results[name] = MEASURE[name](ctx)
            except Exception as exc:  # noqa: BLE001
                results[name] = {'ERROR': type(exc).__name__ + ': ' + str(exc)}
        return results

    def report(label, results, expected):
        say('')
        say('== ' + label)
        matched = True
        for name in ARMS:
            got = results[name]
            defect = got.get(DEFECT_KEY[name])
            ok = (defect is expected[name])
            matched = matched and ok
            say('  ARM ' + name + '  ' + ROW_OF[name])
            say('      defect=' + str(defect) + ' expected=' + str(expected[name])
                + '  ' + ('OK' if ok else 'WRONG COLOUR'))
            say('      measured: ' + json.dumps(got, default=str))
        return matched

    verdicts = []
    live_present = []
    live_measured = False
    if not parsed.neg_arm:
        results = measure(context(CONFIG, SHELL, AGENTS))
        live_measured = True
        # RECORDED, not asserted: the closing line used to claim "three rows" as a fixed
        # string; it now names the rows that are still defective on the live bytes.
        live_present = [name for name in ARMS
                        if results[name].get(DEFECT_KEY[name]) is True]
        ok = report('LIVE -- what the bytes say today', results, EXPECT_LIVE)
        verdicts.append(('live', ok))

    results = measure(context(MUTANTS['config_13_keys'], SHELL, AGENTS))
    ok = report('MUTANT config with 13 top-level keys -- the r54 reading must '
                'FLIP', results,
                # r33 carries the LIVE value in every block that does not mutate the shell.
                {'r54': False, 'r33': False, 'r48': False, 'r46': True})
    verdicts.append(('m-config-13', ok))

    results = measure(context(CONFIG, MUTANTS['shell_stale_comment_restored'], AGENTS))
    ok = report('MUTANT shell with the stale sentence RESTORED -- the r33 '
                'reading must FLIP to the DEFECT', results,
                {'r54': True, 'r33': True, 'r48': False, 'r46': True})
    verdicts.append(('m-no-stale-comment', ok))

    results = measure(context(CONFIG, SHELL, MUTANTS['agents_old_citation']))
    ok = report('MUTANT AGENTS.md with the old citation restored -- the r48 '
                'reading must FLIP to the DEFECT', results,
                {'r54': True, 'r33': False, 'r48': True, 'r46': True})
    verdicts.append(('m-old-citation', ok))

    results = measure(context(CONFIG, SHELL,
                              MUTANTS['agents_one_claim_removed']))
    ok = report('MUTANT AGENTS.md with one flash claim removed -- the r46 '
                'reading must FLIP', results,
                {'r54': True, 'r33': False, 'r48': False, 'r46': False})
    verdicts.append(('m-one-claim-removed', ok))

    say('')
    failed = [label for label, ok in verdicts if not ok]
    if failed:
        say('VERDICT: FAIL  (' + str(len(verdicts) - len(failed)) + '/'
            + str(len(verdicts)) + ' labels matched; wrong: ' + str(failed) + ')')
        return 1
    if not live_measured:
        live_text = 'live NOT probed in this mode'
    elif live_present:
        live_text = (str(len(live_present)) + ' of ' + str(len(ARMS))
                     + ' rows still defective on the live bytes ('
                     + ', '.join(live_present) + ')')
    else:
        live_text = ('0 of ' + str(len(ARMS)) + ' rows defective on the live bytes -- every'
                     ' one refuted by the bytes today')
    say('VERDICT: PASS  live: ' + live_text + '; ' + str(len(verdicts) - 1) + '/'
        + str(len(verdicts) - 1) + ' mutants flipped the reading they are aimed at')
    return 0


if __name__ == '__main__':
    sys.exit(main())
