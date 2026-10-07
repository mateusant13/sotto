import io, re
p = r'app\panel\panel.js'
lines = io.open(p, encoding='utf-8', newline='').read().split('\n')
want = ['HUD_STATS_POLL_MS', 'hudSource', 'hudRows', 'hudFolderButton', 'hudInfo',
        'hudReady', 'hudStats', 'refreshHud', 'paintHudFacts', 'hudRow(', 'hudValue(',
        'hudStatsAge', 'hudSourceText', 'hudStatsNeeds', 'hudStatsStats',
        'wireStatsSource', 'hudRow', 'hudValue']
seen = set()
for i, l in enumerate(lines):
    if any(w in l for w in want):
        a, b = max(0, i - 3), min(len(lines), i + 4)
        key = (a // 6)
        if key in seen:
            continue
        seen.add(key)
        print('--- around %d ---' % (i + 1))
        for j in range(a, b):
            print('%4d| %s' % (j + 1, lines[j]))
