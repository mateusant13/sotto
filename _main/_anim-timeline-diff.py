#!/usr/bin/env python3
"""THE LOOK, BEFORE AND AFTER -- four invariants that hold, one difference that is
the point, and geometry that did not move.

WHAT THIS DECIDES. `_main/_anim-cost2.js` measures what the reveal COSTS; it cannot
say the panel still looks like the thing the owner asked for. `_main/_anim-visual.js`
records, for the eight frames that follow every partial, every word span of the
forming line: `opacity`, `transform`, `filter`, `display`, plus the scroll box and
the row's own geometry. This file runs that record on the panel BEFORE and the panel
AFTER (same page, same stream, same theme) and decides:

  HOLDS  A. the newest word still REVEALS: some sampled frame shows it strictly
             between the keyframe's start and 1 -- in both runs.
  HOLDS  B. it STARTS where it started: first sampled frame of every partial, same
             opacity on the newest word (within 0.03).
  HOLDS  C. the line is still FOLLOWED: after every partial the scroll box is at
             its bottom in both runs, and the row sits where it sat (within 2 px).
  HOLDS  D. it is the same LINE: the row's height and the words' `display` are
             unchanged, and no word carries a non-identity `transform`/`filter` in
             the AFTER run that it did not carry in the BEFORE one.

  THE POINT   E. in the BEFORE run the TAIL dims on EVERY partial -- the finished
             `fill: both` reveals are restarted when `paintWords` rewrites `--w-i`/
             `--w-n` -- so the line is permanently mid-fade. In the AFTER run the
             tail stays at 1 and only the new word fades. This is printed as the
             magnitude it is (tail minimum opacity, per partial), not as a pass.

The frame-by-frame diff is printed as INFORMATION: two runs of a page do not sample
the same rAF cadence, so the frame a ramp is caught on is not a property of the page.
"""
import json
import sys

TOL_PX = 2
TOL_OP = 0.03
TOL_PHASE = 50  # ms: the CONTROL says two runs of the SAME page differ by 42
START = 0.35  # `from { opacity: 0.35 }` in panel.css; some themes start lower


def load(path):
    with open(path, encoding='utf-8') as fh:
        doc = json.load(fh)
    for _key, payload in (doc.get('results') or {}).items():
        if payload and payload.get('frames'):
            return payload
    raise SystemExit('no frames in %s' % path)


def steps_of(frames):
    out = {}
    for f in frames:
        out.setdefault(f.get('step'), []).append(f)
    return {k: sorted(v, key=lambda f: f.get('t') or 0) for k, v in sorted(out.items())}


def ops(frame):
    return [float(x) for x in (frame.get('ops') or '').split(',') if x not in ('', None)]


def parts(frame, key):
    return [p for p in (frame.get(key) or '').split('|') if p != '']


def norm_tf(v):
    v = (v or 'none').strip()
    return None if v in ('none', 'matrix(1, 0, 0, 1, 0, 0)') else v


def norm_fl(v):
    v = (v or 'none').strip()
    return None if v in ('none', 'blur(0px)') else v


def at_bottom(frame):
    s = frame.get('scroll') or [0, 0, 0]
    return s[0] + s[2] >= s[1] - 1


GRID = (16, 33, 50, 66, 83, 100)  # ms after the partial; the reveal is 100 ms


def curve(frames):
    """(t, opacity of the newest word) for one partial, in time order."""
    pts = []
    for f in sorted(frames, key=lambda f: f.get('t') or 0):
        o = ops(f)
        if o:
            pts.append((float(f.get('t') or 0), o[-1]))
    return pts


def at(pts, t):
    """The curve's value at `t`, linearly interpolated. A frame cadence is not
    the page; the wall clock is."""
    if not pts:
        return None
    if t <= pts[0][0]:
        return pts[0][1]
    for (t0, o0), (t1, o1) in zip(pts, pts[1:]):
        if t0 <= t <= t1:
            if t1 == t0:
                return o0
            return o0 + (o1 - o0) * (t - t0) / (t1 - t0)
    return pts[-1][1]


def half_ramp(pts):
    """The first `t` at which the newest word has crossed half of its ramp."""
    if not pts:
        return None
    lo, hi = pts[0][1], max(o for _t, o in pts)
    if hi - lo <= 0.01:
        return None
    target = (lo + hi) / 2.0
    for (t0, o0), (t1, o1) in zip(pts, pts[1:]):
        if o0 < target <= o1:
            if o1 == o0:
                return t1
            return t0 + (t1 - t0) * (target - o0) / (o1 - o0)
    return targets_end(pts, target)


def targets_end(pts, target):
    # the ramp crossed half only after the last sample: report the last time
    return pts[-1][0] if pts[-1][1] >= target else None


def split_anim(value):
    """`sotto-5-snap@pending+0` -> ('sotto-5-snap', 'pending')."""
    if not value:
        return ('', '')
    name, _, rest = value.partition('@')
    return (name, rest.split('+')[0])


def tail_min(frame):
    o = ops(frame)
    return min(o[:-1]) if len(o) > 1 else 1.0


def main(argv):
    if len(argv) != 3:
        raise SystemExit('usage: %s before.json after.json' % argv[0])
    before, after = load(argv[1]), load(argv[2])
    sb, sa = steps_of(before['frames']), steps_of(after['frames'])
    fails = []

    print('BEFORE %s  theme=%s  frames=%d  steps=%d'
          % (argv[1], before.get('theme'), len(before['frames']), len(sb)))
    print('AFTER  %s  theme=%s  frames=%d  steps=%d'
          % (argv[2], after.get('theme'), len(after['frames']), len(sa)))
    if sorted(sb) != sorted(sa):
        fails.append('E0 different partials: %s vs %s' % (sorted(sb), sorted(sa)))

    def ramp(frames):
        n = 0
        for lst in frames.values():
            for f in lst:
                o = ops(f)
                if o and START - 0.34 < o[-1] < 0.99:
                    n += 1
        return n

    print('\nA. the reveal still happens (frames that caught the newest word fading)')
    print('   before=%d  after=%d' % (ramp(sb), ramp(sa)))
    if not ramp(sb) or not ramp(sa):
        fails.append('A a run has no fade on the newest word at all')

    print('\nB. WHERE THE FADE IS, as a TIME, not as a frame index: the moment the')
    print('   newest word crosses half of its ramp (`t50`). A frame cadence is not')
    print('   the page, so a half-ramp time is the only phase-free comparison.')
    print('   partial  before t50   after t50   delta')
    for step in sorted(set(sb) & set(sa)):
        cb, ca = curve(sb[step]), curve(sa[step])
        if not cb or not ca:
            continue
        b50, a50 = half_ramp(cb), half_ramp(ca)
        if b50 is None or a50 is None:
            print('   %-8s %-12s %-11s (the ramp never crosses half inside the window)'
                  % (step, '%.0f' % b50 if b50 is not None else 'none',
                     '%.0f' % a50 if a50 is not None else 'none'))
            continue
        print('   %-8s %-12.0f %-11.0f %+.0f ms' % (step, b50, a50, a50 - b50))
        if abs(a50 - b50) > TOL_PHASE:
            fails.append('B partial %s: the fade crosses half %.0f ms later'
                         % (step, a50 - b50))

    print('\nB2. the animation itself, read from the DOM on the first frame after')
    print('    every partial: same name, same start, same duration?')
    for step in sorted(set(sb) & set(sa)):
        nb = (sb[step][0] or {}).get('anims')
        na = (sa[step][0] or {}).get('anims')
        if not nb or not na:
            print('    %-4s not recorded on one side (a record made before the '
                  '`anims` field existed) -- skipped' % step)
            continue
        print('    %-4s before %-28s after %s' % (step, nb, na))
        if split_anim(nb)[0] != split_anim(na)[0]:
            fails.append('B2 partial %s: a different animation (%s vs %s)'
                         % (step, split_anim(nb)[0], split_anim(na)[0]))
        # `startTime - pushAt`: a NUMBER once the animation has started, the string
        # 'pending' when it has not. Both are compared as the same thing -- it is
        # the same animation, started off the same frame -- within TOL_PHASE.
        sb2, sa2 = split_anim(nb)[1], split_anim(na)[1]
        if sb2 != sa2:
            try:
                if abs(float(sb2) - float(sa2)) > TOL_PHASE:
                    fails.append('B2 partial %s: it starts %.0f ms apart'
                                 % (step, float(sa2) - float(sb2)))
            except ValueError:
                fails.append('B2 partial %s: it starts at a different moment (%s vs %s)'
                             % (step, sb2, sa2))

    print('\nE. the tail on every partial -- the difference this lane is FOR')
    print('   partial   before: tail min opacity   after: tail min opacity')
    for step in sorted(set(sb) & set(sa)):
        mb = min((tail_min(f) for f in sb[step]), default=1.0)
        ma = min((tail_min(f) for f in sa[step]), default=1.0)
        print('   %-8s %.2f                      %.2f' % (step, mb, ma))
        if ma < 0.99:
            fails.append('E partial %s: the AFTER tail is still dimmed (%.2f)' % (step, ma))

    print('\nC. followed, and where the row sits (last frame of each partial)')
    for step in sorted(set(sb) & set(sa)):
        lb, la = sb[step][-1], sa[step][-1]
        db = (lb.get('rowH') or 0) - (la.get('rowH') or 0)
        dt = (lb.get('rowTop') or 0) - (la.get('rowTop') or 0)
        print('   %-4s follow %-5s/%-5s  rowH %s/%s  rowTop %s/%s  d=%+d/%+d'
              % (step, at_bottom(lb), at_bottom(la), lb.get('rowH'), la.get('rowH'),
                 lb.get('rowTop'), la.get('rowTop'), db, dt))
        if not at_bottom(la):
            fails.append('C partial %s: the AFTER run left the box off the bottom (%s)'
                         % (step, la.get('scroll')))
        if abs(db) > TOL_PX or abs(dt) > TOL_PX:
            fails.append('C partial %s: geometry moved by %+d/%+d px' % (step, db, dt))

    print('\nD. the box model and the base state of every word')
    for step in sorted(set(sb) & set(sa)):
        lb, la = sb[step][-1], sa[step][-1]
        disb, disa = parts(lb, 'disp'), parts(la, 'disp')
        tfb = [norm_tf(x) for x in parts(lb, 'tf')]
        tfa = [norm_tf(x) for x in parts(la, 'tf')]
        flb = [norm_fl(x) for x in parts(lb, 'fl')]
        fla = [norm_fl(x) for x in parts(la, 'fl')]
        print('   %-4s display %-8s/%-8s  transform %-18s/%-18s  filter %s/%s'
              % (step, ''.join(disb), ''.join(disa),
                 str([x for x in tfb if x])[:18], str([x for x in tfa if x])[:18],
                 [x for x in flb if x], [x for x in fla if x]))
        if disb != disa:
            fails.append('D partial %s: word display changed %s -> %s'
                         % (step, ''.join(disb), ''.join(disa)))
        # a word the AFTER run animates must be the last one only
        extra = [i for i, v in enumerate(tfa) if v and not (i == len(tfa) - 1)]
        if extra:
            fails.append('D partial %s: the AFTER run transforms tail words %s'
                         % (step, extra))

    print('\nframe-by-frame of the newest word (information)')
    n = 0
    total = 0
    for step in sorted(set(sb) & set(sa)):
        for i, (fb, fa) in enumerate(zip(sb[step], sa[step])):
            total += 1
            ob, oa = ops(fb), ops(fa)
            if ob and oa and abs(ob[-1] - oa[-1]) > 0.15:
                n += 1
                if n <= 5:
                    print('   partial %s frame %d: newest %.2f vs %.2f (t=%s/%s)'
                          % (step, i, ob[-1], oa[-1], fb.get('t'), fa.get('t')))
    print('   frames whose newest word differs by more than 0.15: %d of %d' % (n, total))

    print('\nVERDICT: %s' % ('RED -- the after run is not the same look' if fails
                             else 'THE LOOK IS THE SAME, AND THE TAIL NO LONGER RE-FADES'))
    for f in fails:
        print('   ' + f)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
