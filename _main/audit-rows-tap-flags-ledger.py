# =============================================================================
# audit-rows-tap-flags-ledger.py -- ONE instrument for TWO open register rows
# in the WASAPI tap, driven IN-PROCESS with a scripted vtable.
#
#   #9   "flags is read and discarded -> DATA_DISCONTINUITY/SILENT are never
#         examined and the loss has no counter"  (three separate claims)
#   #39  "_pump copies the accumulator with np.concatenate on every emit"
#
# The subject is worker/wasapi_loopback.py. The instrument does NOT open a
# device and does NOT launch anything: it imports the module, builds a tap with
# __new__ (skipping __init__, which would enumerate endpoints), and replaces the
# module's _vtbl() with a scripted fake, so IAudioCaptureClient::GetNextPacketSize
# / GetBuffer / ReleaseBuffer are answered from a list of packets I choose --
# frames, flags, device position and sample values. Everything else is the REAL
# _pump: the real flag tests, the real counters, the real emit loop.
#
# EVERY arm must FLIP on a MUTANT of the module under %TEMP% (the defect fixed,
# or -- for the one claim that is REFUTED today -- the defect INTRODUCED).
# An arm that reads the same on both colours is not a detector.
#
# Usage:  py -3 _main/audit-rows-tap-flags-ledger.py [--neg-arm] [--verbose]
# =============================================================================
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
import struct
import sys
import tempfile
import threading
import time
from ctypes import wintypes

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
TAP = os.path.join(ROOT, 'worker', 'wasapi_loopback.py')

SILENT = 0x00000002           # AUDCLNT_BUFFERFLAGS_SILENT
DATA_DISCONTINUITY = 0x00000001
VERBOSE = False


def say(message):
    print(message, flush=True)


def detail(message):
    if VERBOSE:
        say('    ' + message)


def sha256_file(path):
    with open(path, 'rb') as handle:
        return hashlib.sha256(handle.read()).hexdigest().upper()


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def line_of(text, anchor):
    newline = '\r\n' if '\r\n' in text else '\n'
    index = text.find(anchor.replace('\n', newline))
    if index < 0:
        return 0
    return text.count('\n', 0, index) + 1


# ---------------------------------------------------------------------------
# mutants of the tap: one literal replacement each
# ---------------------------------------------------------------------------
MUTANTS = {
    # #9a -- the SILENT test is removed: silent packets are decoded as audio.
    'm9a-silent-test-removed': (
        'if flags.value & AUDCLNT_BUFFERFLAGS_SILENT or not data:',
        'if not data:'),
    # #9b -- THE COUNTER IS REMOVED, i.e. the pre-2026-10-11 state: the flag is read
    # and thrown away, so a discontinuity run is byte- and peak-identical to a clean
    # one and the defect is present again. (Until 2026-10-11 this mutant went the
    # other way -- it SIMULATED the fix -- because the fix did not exist yet.)
    'm9b-discontinuity-counter-removed': (
        '                if flags.value & AUDCLNT_BUFFERFLAGS_DATA_DISCONTINUITY:\n'
        '                    # Counted, not swallowed -- and NOT treated as a restart: the\n'
        '                    # position comparison above already counts the gap the flag\n'
        '                    # often accompanies. See `discontinuity_packets` above.\n'
        '                    self.discontinuity_packets += 1\n'
        '                if flags.value & AUDCLNT_BUFFERFLAGS_SILENT or not data:',
        '                if flags.value & AUDCLNT_BUFFERFLAGS_SILENT or not data:'),
    # #9c -- the device-position comparison (the loss counter) is removed.
    'm9c-position-gap-counter-removed': (
        '                if prev_pos is not None and pos.value != prev_pos + frames.value:\n'
        '                    self.position_gap_packets += 1\n'
        '                prev_pos = pos.value\n',
        '                prev_pos = pos.value\n'),
    # #39 -- the emit copies the accumulator even when ONE array is pending.
    'm39-always-concatenate': (
        'joined = np.concatenate(buf) if len(buf) > 1 else buf[0]',
        'joined = np.concatenate(buf) if True else buf[0]'),
}


def make_mutant(source, key, directory):
    old, new = MUTANTS[key]
    newline = '\r\n' if '\r\n' in source else '\n'
    old_n = old.replace('\n', newline)
    new_n = new.replace('\n', newline)
    count = source.count(old_n)
    if count != 1:
        say('SETUP ERROR: the ' + key + ' anchor appears ' + str(count)
            + ' time(s) (wanted exactly 1) -- the mutation would not be the one '
            'this instrument documents')
        raise SystemExit(2)
    path = os.path.join(directory, 'wasapi_loopback_' + key + '.py')
    with open(path, 'w', encoding='utf-8', newline='') as handle:
        handle.write(source.replace(old_n, new_n, 1))
    return path


# ---------------------------------------------------------------------------
# the scripted device
# ---------------------------------------------------------------------------
class FakeEp:
    name = 'FAKE endpoint (scripted, no device opened)'
    rate = 48000
    channels = 1
    bits = 32
    format_tag = 0x0003          # WAVE_FORMAT_IEEE_FLOAT
    block_align = 4


class CountingNumpy:
    """numpy, with np.concatenate counted (the #39 question)."""

    def __init__(self, numpy):
        self._np = numpy
        self.calls = 0
        self.elements = 0

    def __getattr__(self, name):
        return getattr(self._np, name)

    def concatenate(self, arrays, *args, **kwargs):
        self.calls += 1
        try:
            self.elements += sum(int(a.size) for a in arrays)
        except Exception:
            pass
        return self._np.concatenate(arrays, *args, **kwargs)


class Script:
    """The device: a list of packets, then silence and a stop."""

    def __init__(self, tap, packets):
        self.tap = tap
        self.packets = list(packets)
        self.served = 0
        self.releases = 0
        self._keep_alive = []

    def vtable(self, cap, index, *_rest):
        if index == 5:
            return self.next_size
        if index == 3:
            return self.get_buffer
        if index == 4:
            return self.release
        raise AssertionError('unexpected vtable slot ' + str(index))

    def next_size(self, cap, narg):
        if self.served < len(self.packets):
            narg._obj.value = int(self.packets[self.served]['frames'])
        else:
            narg._obj.value = 0
            self.tap._stop.set()
        return 0

    def get_buffer(self, cap, darg, farg, flagsarg, posarg, qpc):
        packet = self.packets[self.served]
        frames = int(packet['frames'])
        value = float(packet.get('value', 0.0))
        raw = struct.pack('<' + ('f' * frames), *([value] * frames))
        buffer_ = ctypes.create_string_buffer(raw, len(raw))
        self._keep_alive.append(buffer_)
        ctypes.memmove(ctypes.byref(darg._obj),
                       ctypes.byref(ctypes.c_void_p(ctypes.addressof(buffer_))),
                       ctypes.sizeof(ctypes.c_void_p))
        farg._obj.value = frames
        flagsarg._obj.value = int(packet.get('flags', 0))
        posarg._obj.value = int(packet.get('pos', 0))
        self.served += 1
        return 0

    def release(self, cap, frames):
        self.releases += 1
        return 0


def drive(mod, packets, block, frames_per_block_ms=100):
    """Run the REAL _pump over a scripted device. No device, no thread leak."""
    import numpy

    tap = mod.WasapiLoopbackTap.__new__(mod.WasapiLoopbackTap)
    proxy = CountingNumpy(numpy)
    tap.np = proxy
    tap.ep = FakeEp()
    tap.rate = FakeEp.rate
    tap.channels = FakeEp.channels
    tap.block_ms = frames_per_block_ms
    tap.block = block
    tap._stop = threading.Event()
    tap._cb_lock = threading.Lock()
    tap._capture = object()
    tap.silent_packets = 0
    tap.position_gap_packets = 0
    # SEEDED 2026-10-11: the shipped _pump now counts the discontinuity bit too,
    # and this harness builds the tap with __new__ (no __init__), so an unseeded
    # attribute is an AttributeError INSIDE the pump thread -- which kills the
    # thread and turns every arm into a crashed-pump reading, not a measurement.
    tap.discontinuity_packets = 0
    delivered = []
    tap.on_block = lambda arr: delivered.append([float(x) for x in arr])

    script = Script(tap, packets)
    mod._vtbl = script.vtable
    thread = threading.Thread(target=tap._pump, name='audit-tap-pump',
                              daemon=True)
    thread.start()
    thread.join(15)
    stuck = thread.is_alive()
    if stuck:
        tap._stop.set()
        thread.join(5)
    peaks = [max((abs(x) for x in block_), default=0.0) for block_ in delivered]
    return {
        'emits': len(delivered),
        'blocks': [len(block_) for block_ in delivered],
        'peak_per_block': [round(p, 6) for p in peaks],
        'max_peak': round(max(peaks), 6) if peaks else None,
        'silent_packets': tap.silent_packets,
        'position_gap_packets': tap.position_gap_packets,
        'discontinuity_packets': tap.discontinuity_packets,
        'packets_served': script.served,
        'releases': script.releases,
        'concatenate_calls': proxy.calls,
        'concatenate_elements': proxy.elements,
        'pump_stuck': stuck,
        'first_block_head': delivered[0][:4] if delivered else None,
    }


def packets(frames_each, count, flags=0, value=0.5, step=None, start=0):
    step = frames_each if step is None else step
    return [{'frames': frames_each, 'flags': flags, 'value': value,
             'pos': start + index * step} for index in range(count)]


# ---------------------------------------------------------------------------
# arms
# ---------------------------------------------------------------------------
def arm_r9a(mod):
    """#9, claim 1: is AUDCLNT_BUFFERFLAGS_SILENT examined and counted?"""
    run = drive(mod, packets(100, 4, flags=SILENT, value=0.5), block=200)
    run['silent_flag_ignored'] = (run['silent_packets'] == 0
                                  and (run['max_peak'] or 0) > 0)
    return run


def arm_r9b(mod):
    """#9, claim 2: is DATA_DISCONTINUITY (bit 0x1) examined at all?"""
    control = drive(mod, packets(100, 4, flags=0, step=100), block=200)
    disco = drive(mod, packets(100, 4, flags=DATA_DISCONTINUITY, step=100),
                  block=200)
    same_audio = control['peak_per_block'] == disco['peak_per_block']
    same_counters = (control['silent_packets'] == disco['silent_packets']
                     and control['position_gap_packets']
                     == disco['position_gap_packets']
                     # THE COUNTER THIS CLAIM IS ABOUT (added 2026-10-11). Without it
                     # this comparison could not see the very fix it exists to measure.
                     and control['discontinuity_packets']
                     == disco['discontinuity_packets'])
    return {
        'control': control,
        'discontinuity': disco,
        'audio_identical': same_audio,
        'counters_identical': same_counters,
        'discontinuity_invisible': bool(same_audio and same_counters),
    }


def arm_r9c(mod):
    """#9, claim 3: does the loss (a position jump) have a counter?"""
    run = drive(mod, packets(100, 4, flags=0, step=400), block=200)
    run['loss_uncounted'] = run['position_gap_packets'] == 0
    return run


def arm_r39(mod):
    """#39: does every emit copy the accumulator with np.concatenate?"""
    single = drive(mod, packets(250, 4, step=250), block=250)
    multi = drive(mod, packets(100, 10, step=100), block=250)
    return {
        'one_pending_array': single,
        'several_pending_arrays': multi,
        'copies_even_with_one_pending': single['concatenate_calls'] > 0,
        'copies_per_emit_multi': (
            round(multi['concatenate_calls'] / multi['emits'], 3)
            if multi['emits'] else None),
    }


ARMS = ('r9a', 'r9b', 'r9c', 'r39')
MEASURE = {'r9a': arm_r9a, 'r9b': arm_r9b, 'r9c': arm_r9c, 'r39': arm_r39}
MUTANT_OF = {'r9a': 'm9a-silent-test-removed',
             'r9b': 'm9b-discontinuity-counter-removed',
             'r9c': 'm9c-position-gap-counter-removed',
             'r39': 'm39-always-concatenate'}
DEFECT_KEY = {'r9a': 'silent_flag_ignored', 'r9b': 'discontinuity_invisible',
              'r9c': 'loss_uncounted', 'r39': 'copies_even_with_one_pending'}
EXPECT = {
    'r9a': {'live': False, 'mutant': True},
    # r9b FLIPPED 2026-10-11, the day the counter landed in the shipped tap: the live
    # tree now REFUTES the claim and the mutant (counter removed) REPRODUCES it, so
    # the instrument keeps its power in the new state instead of pinning the old one.
    'r9b': {'live': False, 'mutant': True},
    'r9c': {'live': False, 'mutant': True},
    'r39': {'live': False, 'mutant': True},
}
ROW_OF = {
    'r9a': 'audit #9 (audio-path.md F2), claim A: SILENT is never examined',
    'r9b': 'audit #9 (audio-path.md F2), claim B: DATA_DISCONTINUITY is never '
           'examined',
    'r9c': 'audit #9 (audio-path.md F2), claim C: the loss has no counter',
    'r39': 'audit #39 (audio-path.md F6): _pump copies the accumulator with '
           'np.concatenate on every emit',
}


def run_all(mod):
    results = {}
    for name in ARMS:
        try:
            results[name] = MEASURE[name](mod)
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
        defect = defect if isinstance(defect, bool) else None
        ok = (defect is expected[name])
        matched = matched and ok
        wanted = 'DEFECT-PRESENT' if expected[name] else 'DEFECT-REFUTED'
        seen = 'DEFECT-PRESENT' if defect else 'DEFECT-REFUTED'
        say('  ARM ' + name + '  ' + seen.ljust(15) + ' want=' + wanted.ljust(15)
            + ('OK' if ok else 'WRONG COLOUR') + '  ' + ROW_OF[name])
        say('      measured: ' + json.dumps(got, default=str))
    return matched


def main(argv=None):
    global VERBOSE
    parser = argparse.ArgumentParser(
        description='Two open audit rows in the WASAPI tap, driven in-process '
                    'with a scripted vtable (opens no device, launches nothing).')
    parser.add_argument('--tap', default=TAP)
    parser.add_argument('--neg-arm', action='store_true')
    parser.add_argument('--verbose', action='store_true')
    parsed = parser.parse_args(argv)
    VERBOSE = parsed.verbose
    tap_path = os.path.abspath(parsed.tap)

    say('audit-rows-tap-flags-ledger -- two open rows, one instrument')
    say('tap        : ' + tap_path)
    say('bytes      : ' + str(os.path.getsize(tap_path)))
    say('sha256     : ' + sha256_file(tap_path))
    say('launches   : NOTHING (no shell, no worker, no device; the ' 
        'IAudioCaptureClient vtable is scripted)')

    with open(tap_path, encoding='utf-8', newline='') as handle:
        source = handle.read()
    say('')
    say('anchors (1-based line of the FIRST occurrence, live bytes):')
    for key in ARMS:
        anchor = MUTANTS[MUTANT_OF[key]][0]
        say('  ' + key + ': ' + MUTANT_OF[key].ljust(34) + ' anchor line '
            + str(line_of(source, anchor)) + '  '
            + repr(anchor.split('\n')[0].strip()[:58]))

    directory = tempfile.mkdtemp(prefix='sotto-audit-tap-')
    say('')
    say('mutants    : ' + directory)
    mutant_paths = {}
    for key in ARMS:
        path = make_mutant(source, MUTANT_OF[key], directory)
        mutant_paths[key] = path
        say('  ' + os.path.basename(path).ljust(50) + ' '
            + str(os.path.getsize(path)) + ' B  sha256 '
            + sha256_file(path)[:16])

    verdicts = []
    live_present = []
    live_measured = False
    if not parsed.neg_arm:
        live = load_module(tap_path, 'audit_tap_live')
        results = run_all(live)
        # The live present-set is RECORDED, not hard-coded: the closing VERDICT used to
        # assert "1 of 4 ... (the discontinuity bit)" as a fixed sentence, and that
        # sentence went stale the day the bit started being examined (2026-10-11).
        live_measured = True
        live_present = [name for name in ARMS
                        if results[name].get(DEFECT_KEY[name]) is True]
        expected = {name: EXPECT[name]['live'] for name in ARMS}
        ok = report('LIVE tap -- every arm must read what the ARM declares',
                    results, expected)
        verdicts.append(('live', ok))

    for key in ARMS:
        module = load_module(mutant_paths[key], 'audit_tap_' + key)
        results = run_all(module)
        expected = {name: (EXPECT[name]['mutant'] if name == key
                           else EXPECT[name]['live']) for name in ARMS}
        ok = report('MUTANT ' + MUTANT_OF[key] + ' -- arm ' + key
                    + ' alone must FLIP', results, expected)
        verdicts.append((key, ok))

    say('')
    failed = [label for label, ok in verdicts if not ok]
    if failed:
        say('VERDICT: FAIL  (' + str(len(verdicts) - len(failed)) + '/'
            + str(len(verdicts)) + ' labels matched; wrong: ' + str(failed) + ')')
        return 1
    if not live_measured:
        # A verdict may not claim a reading this mode never took: with --neg-arm the
        # live block above is skipped, so it says so instead of printing a set.
        live_text = ('live NOT probed in this mode (--neg-arm: mutants only), so no live '
                     'set is claimed')
    elif live_present:
        live_text = (str(len(live_present)) + ' of ' + str(len(ARMS))
                     + ' defect claims present (' + ', '.join(live_present) + ')')
    else:
        live_text = ('0 of ' + str(len(ARMS)) + ' defect claims present -- every one '
                     'refuted on the live bytes')
    say('VERDICT: PASS  live: ' + live_text
        + '; ' + str(len(ARMS)) + '/' + str(len(ARMS))
        + ' mutants flipped exactly their own arm')
    return 0


if __name__ == '__main__':
    sys.exit(main())
