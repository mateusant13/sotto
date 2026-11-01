#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Print the summary line of an arm file produced by driver.py."""
import io
import json
import sys


def load(path):
    raw = io.open(path, encoding='utf-8', errors='replace').read()
    i = raw.find('RESULT_JSON ')
    if i < 0:
        return None
    j = raw.find('\n', i)
    line = raw[i + len('RESULT_JSON '):] if j < 0 else raw[i + len('RESULT_JSON '):j]
    return json.loads(line.strip())


if __name__ == '__main__':
    for path in sys.argv[1:]:
        d = load(path)
        if d is None:
            print('%-24s NO RESULT' % path)
            continue
        lc = d.get('log_channel', {})
        print('%-24s verdict=%-5s flips=%2d/%2d posted=%2d delivered=%2d '
              'log(S/H)=%2d/%2d agree=%-5s gas=%-3d prop=%s' % (
                  d.get('label', path), d['verdict'], d['flips'],
                  d['expected_flips'], d['presses_posted'],
                  d['presses_delivered_by_pump'], lc.get('PANEL_SHOWN', -1),
                  lc.get('PANEL_HIDDEN', -1), lc.get('channels_agree'),
                  d.get('getasynckeystate_reads_during_run', -1),
                  d.get('property_present')))
