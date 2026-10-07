"""Remove the HUD from panel.js, and the dead paths that only it used.

Every cut is anchored on text that must occur EXACTLY once, so a silent miss is
impossible: the script prints a MISS line instead of removing the wrong region.
"""
import io

P = r'app\panel\panel.js'
src = io.open(P, encoding='utf-8', newline='').read()
orig_len = len(src)
log = []


def cut(start, end, label):
    """Delete from the line holding `start` through the line holding `end`."""
    global src
    i = src.find(start)
    if i < 0 or src.count(start) != 1:
        log.append('MISS %-34s start count=%d' % (label, src.count(start)))
        return
    j = src.find(end, i)
    if j < 0:
        log.append('MISS %-34s end not found' % label)
        return
    j += len(end)
    # swallow the trailing newline so no blank line is left behind
    while j < len(src) and src[j] in '\r\n':
        j += 1
    src = src[:i] + src[j:]
    log.append('cut  %-34s %d bytes' % (label, j - i))


def sub(old, new, label, expect=1):
    global src
    n = src.count(old)
    if n != expect:
        log.append('MISS %-34s count=%d (want %d)' % (label, n, expect))
        return
    src = src.replace(old, new)
    log.append('sub  %-34s %d site(s)' % (label, n))


# ── 1. the poll constant ────────────────────────────────────────────────────
cut('/**\n * How often the HUD pulls', 'const HUD_STATS_POLL_MS = 4000;', 'poll constant')

# ── 2. the dom cache entries ────────────────────────────────────────────────
cut("  // the panel surface's HUD", "hudFolderButton: document.getElementById('hud-folder-button'),",
    'dom cache')

# ── 3. the module state ─────────────────────────────────────────────────────
cut('let hudInfo = {', 'let hudReady = false;', 'hudInfo/hudReady')
sub("/** The history root the shell reported, or null. The HUD's folder tooltip. */",
    '/** The history root the shell reported, or null. */', 'historyRootPath comment')
cut('// The shell-side stats payload, once the shell has one.', 
    'const hudStats = { stats: null, receivedAt: null };', 'hudStats state')

# ── 4. the init-path calls ──────────────────────────────────────────────────
cut('  // The HUD reads state that has not arrived yet', '  refreshHud();', 'init path')
cut('  // The HUD\'s "Live lines" is a count', '  refreshHud();', 'refreshLines')
cut("        // The HUD's Transcript tooltip names the folder the same button opens.\n"
    "        historyRootPath = root;\n"
    "        if (dom.hudFolderButton) dom.hudFolderButton.title = `Open ${root} in the OS file manager`;",
    "historyRootPath = root;", 'historyRootPath assignment')
cut('  // The HUD reports WHICH canonical writer', '  refreshHud();', 'history paint')
sub('  applyLiveEnabled(liveEnabled, { silent: true });\n  refreshHud();\n',
    '  applyLiveEnabled(liveEnabled, { silent: true });\n', 'applySurface')
cut('  updateStripState();\n  refreshHud();\n}\n\n/** The strip\'s status',
    '/** The strip\'s status', 'updateStripState tail')
sub('  updateStripState();\n  refreshHud();\n', '  updateStripState();\n', 'strip tail', expect=2)
sub('    updateStripState();\n    refreshHud();\n', '    updateStripState();\n', 'wireStatus', expect=1)
sub('    // ONE place records what the shell said, so the strip\'s single word and the\n'
    '    // HUD\'s State row are painted from the same fact (see `updateStripState`).',
    '    // ONE place records what the shell said, so the strip\'s single word is\n'
    '    // painted from that one fact (see `updateStripState`).', 'wireStatus comment')
sub('  // The panel\'s OWN statuses land in the same snapshot the shell\'s do: the strip\n'
    '  // and the HUD would otherwise keep showing a stale shell sentence after Clear.',
    '  // The panel\'s OWN statuses land in the same snapshot the shell\'s do: the strip\n'
    '  // would otherwise keep showing a stale shell sentence after Clear.', 'setStatus comment')
sub('  // The paused state is reported by the HUD\'s `State` row and by the strip\'s one\n'
    '  // word; there is no separate Pause row any more (the HUD is a performance\n'
    '  // readout \u2014 see the note above `refreshHud`). `setStatus` below carries it into\n'
    '  // the snapshot both of those read, so a single repaint is enough.',
    '  // The paused state is reported by the strip\'s one word. `setStatus` below\n'
    '  // carries it into the snapshot that word reads, so one repaint is enough.',
    'applyPause comment')

# ── 5. the whole HUD block (row builders, refreshHud, wireStatsSource, paintHudFacts) ──
cut('// ---------------------------------------------------------------------------\n'
    '// THE HUD \u2014 a SMALL PERFORMANCE READOUT',
    '/** Ask the OS file manager to open the entry\'s file, or the root when null. */',
    'HUD JS block (kept revealPath)')
sub('/** Ask the OS file manager to open the entry\'s file, or the root when null. */',
    '/** Ask the OS file manager to open the entry\'s file, or the root when null. */',
    'revealPath survives')

io.open(P, 'w', encoding='utf-8', newline='').write(src)
for line in log:
    print(line)
print('panel.js: %d -> %d bytes' % (orig_len, len(src)))
left = [i + 1 for i, l in enumerate(src.split('\n')) if 'hud' in l.lower() or 'HUD' in l]
print('remaining hud mentions on lines: %r' % left)
