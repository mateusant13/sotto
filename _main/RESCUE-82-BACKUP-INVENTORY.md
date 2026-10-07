# RESCUE-82 BACKUP INVENTORY

Source: H:\sotto @ HEAD 24df100
Census: 2026-10-07 21:29:11 UTC (brief said 818 / 736 untracked / 0 staged)
Fresh: 82 tracked modified, 0 staged, 737 untracked collapsed / 17270 untracked files (-uall)
Population changed vs brief: untracked 736 -> 737 (+1). Tracked modified unchanged at 82.

All 82 copied BOTH ways into _backup/H-sotto/:
- working/    (on-disk working-tree version = what a checkout would destroy)
- committed/  (git show HEAD:<path> = the version a checkout would restore)

NOTE: committed/ was written via git show piped through PowerShell, so CRLF/LF
may be normalised. Treat committed/ as reference; working/ is byte-exact.

| AGENTS.md | 60765 | 55186 |
| README.md | 14180 | 2934 |
| _main/_armE-fake-worker.py | 3275 | 2866 |
| _main/_audit-render/make-harness.py | 3921 | 3954 |
| _main/_audit-render/panel-chrome-frame.html | 1948 | 1954 |
| _main/_audit-render/panel-chrome-real.html | 38443 | 35375 |
| _main/_audit-render/panel-cost-on.html | 38784 | 35264 |
| _main/_audit-render/panel-cost-reduced.html | 38784 | 35264 |
| _main/_audit-render/panel-cost-relayout.html | 38784 | 35264 |
| _main/_audit-render/panel-harness.html | 39983 | 37335 |
| _main/_audit-verify-all.cmd | 32203 | 26692 |
| _main/_audit-verify/_battery-summary.txt | 1617 | 1266 |
| _main/_audit-verify/js/BOOTSTRAP_JS.js | 13370 | 10441 |
| _main/_audit-verify/js/BRIDGE_PROBE.js | 2910 | 2696 |
| _main/_design-lane/gen_themes.py | 73152 | 72799 |
| _main/_panel-anim-cost-arm.py | 24613 | 16730 |
| _main/_panel-anim-cost.js | 18954 | 11397 |
| _main/_panel-anim-cost.json | 8587 | 5161 |
| _main/_panel-chrome-arm.py | 40078 | 37091 |
| _main/_panel-chrome-probe.js | 36662 | 33349 |
| _main/_panel-clear-lifted-mutant.py | 389073 | 245185 |
| _main/_panel-verdict-benign-mutant.py | 389263 | 245378 |
| _main/_panel2-dom-probe.js | 53862 | 31954 |
| _main/_redux-gate-mutants/env-optin.py | 242082 | 233211 |
| _main/_redux-gate-mutants/fail-safe.py | 242083 | 233212 |
| _main/_redux-gate-mutants/flag-exists.py | 242081 | 233210 |
| _main/_redux-gate-mutants/flag-guarded.py | 242075 | 233204 |
| _main/_redux-gate-mutants/hard-rule.py | 242042 | 233171 |
| _main/_redux-gate-mutants/memory-gate.py | 242083 | 233212 |
| _main/_redux-gate-mutants/payload-guarded.py | 242068 | 233197 |
| _main/_redux-gate-mutants/shell-loop.py | 397149 | 245335 |
| _main/_redux-gate-mutants/shell-measured.py | 397140 | 245326 |
| _main/_redux-gate-mutants/stamp.py | 242081 | 233210 |
| _main/_redux-gate-mutants/switch-wired.py | 242078 | 233207 |
| _main/_redux-gate-mutants/verdict-counts-batch.py | 242046 | 233175 |
| _main/no-python-icon-after.json | 4862 | 4875 |
| _main/panel-exit3-oracle.py | 53743 | 50892 |
| _main/panel-visibility.json | 423 | 421 |
| _main/receipt-word-split-fix.md | 15048 | 10476 |
| _main/word-split-trace.json | 5399 | 5466 |
| _moved/aireplay/AGENTS.md | 39851 | 33646 |
| _moved/aireplay/_main/font-lag-probe.ps1 | 3944 | 3623 |
| _moved/aireplay/_main/font-shots.ps1 | 3101 | 2772 |
| _moved/aireplay/_main/heartbeat.ps1 | 28107 | 3372 |
| _moved/aireplay/_main/panel-tema-1-teleprompter-1920x1080.png | 104796 | 265952 |
| _moved/aireplay/_main/panel-tema-1-teleprompter.png | 248749 | 515700 |
| _moved/aireplay/_main/panel-tema-2-broadcast-1920x1080.png | 63947 | 193731 |
| _moved/aireplay/_main/panel-tema-2-broadcast.png | 151982 | 223431 |
| _moved/aireplay/_main/panel-tema-3-manuscrito-1920x1080.png | 90496 | 290071 |
| _moved/aireplay/_main/panel-tema-3-manuscrito.png | 186110 | 343222 |
| _moved/aireplay/_main/panel-tema-4-cinema-card-1920x1080.png | 102174 | 323802 |
| _moved/aireplay/_main/panel-tema-4-cinema-card.png | 226979 | 508992 |
| _moved/aireplay/_main/panel-tema-5-instrumento-1920x1080.png | 82430 | 282600 |
| _moved/aireplay/_main/panel-tema-5-instrumento.png | 175958 | 281202 |
| _moved/aireplay/_main/panel-temas-comparacao.png | 439811 | 905304 |
| _moved/aireplay/_main/panel-temas-manifest.json | 163340 | 168628 |
| _moved/aireplay/_main/panel-temas-tabela.md | 13862 | 14071 |
| _moved/aireplay/_main/wgc-probe.cpp | 16667 | 6163 |
| _moved/aireplay/_main/wgc-probe.exe | 307103 | 343149 |
| _moved/aireplay/control/optchat/view.txt | 540 | 534 |
| _moved/aireplay/receipts/receipt-14-ring-cap-vram-vs-ram.md | 5581 | 4865 |
| _moved/aireplay/specs/03-capture-encode.md | 22863 | 21297 |
| _moved/aireplay/src/asr/engine.py | 14918 | 7621 |
| _moved/aireplay/src/asr/runner.py | 12225 | 11998 |
| _moved/aireplay/src/asr/transcribe.py | 6729 | 6050 |
| _moved/aireplay/src/capture/replay.cpp | 27495 | 23253 |
| _moved/aireplay/src/capture/replay.h | 7453 | 6548 |
| _moved/aireplay/src/capture/ring_buffer.cpp | 11148 | 5304 |
| _moved/aireplay/src/capture/ring_buffer.h | 7512 | 3535 |
| _moved/aireplay/src/capture/run_battery.ps1 | 28290 | 4125 |
| _moved/aireplay/src/capture/test_window.cpp | 24136 | 13397 |
| _moved/aireplay/src/capture/test_window.h | 7637 | 2371 |
| app/panel/panel.css | 57825 | 47030 |
| app/panel/panel.html | 39300 | 35075 |
| app/panel/panel.js | 104463 | 85658 |
| app/panel/themes/theme-1.css | 23531 | 24955 |
| app/panel/themes/theme-2.css | 23897 | 25453 |
| app/panel/themes/theme-3.css | 23034 | 24231 |
| app/panel/themes/theme-4.css | 22993 | 24417 |
| app/panel/themes/theme-5.css | 24608 | 25809 |
| app/webview/sotto_webview.py | 397180 | 277922 |
| worker/config.json | 5882 | 4730 |
