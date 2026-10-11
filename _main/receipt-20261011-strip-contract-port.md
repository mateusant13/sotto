# Receipt - the strip contract port (2026-10-11)

Lane: the same session that cured the frozen tap. Owner's instruction in force: close everything, leave no gaps,
per-app audio must be separated. This receipt covers ONE increment: the surgical port of the strip contract into
the live WebView2 shell, and the live verification of Alt+C on the result.

## 1. What was ported, and from where

- Reference: `I:/cc-tmp/ref-55c422b-shell.py` = 8,218 lines / 406,194 B / sha256
  `71B3539CA23A33A38BB1B77CF58F86F1AEAF9BE1091AEFDFBC4AB2EFD41050D9` (branch `rescue/dangling-55c422b`).
  Wholesale adoption was REJECTED earlier: the reference predates live-only work (place_panel, BRIDGE_UNKNOWN,
  the P1-P9 reload ceiling, silent-device, --exit-after) and `git diff --no-index --numstat` is 2599/1164.
- Port sources: `I:/cc-tmp/port-geometry.py` (5 blocks) and `I:/cc-tmp/port-meter-stats.py` (17 blocks),
  with the placement map in `I:/cc-tmp/port-meter-stats-manifest.md` (517 lines).
- Applier: `I:/cc-tmp/apply-port.py` - parses the `### BLOCK n` markers, asserts each live anchor is non-blank and
  each block body is not already present, asserts the block's first-line indentation equals the anchor's, splices
  bottom-up (so no index is computed by hand), asserts the base file's sha256 before touching it, and writes with
  encode-BEFORE-open.

## 2. Measured result of the port

| revision | size | sha256 (first 16) | CRLF | bare LF | lines | py_compile |
|---|---|---|---|---|---|---|
| before | 337,049 B | `056FAC42DBE74190` | 6,783 | 0 | 6,783 | rc=0 |
| after 22 blocks | 358,688 B | `F2C7D3884FAB08EC` | 7,189 | 0 | 7,189 | rc=0 |
| after the wiring fix | 359,010 B | `5E3B8BE81695298B` | 7,193 | 0 | 7,194 | rc=0 |

21 of the 22 block bodies are present EXACTLY ONCE, verbatim. Static proof of the port's surface: the shell imports
and `SottoShell` carries `strip_height_from_css`, `refresh_strip_height`, `stats`, `reply_stats`,
`on_worker_stats`, `on_worker_meter`, `_stats_log_maybe`, `emit_async`; `WorkerBridge.__init__` now takes
`on_stats`/`on_meter`; `'surface': 'strip'` survives in the geometry dict.

## 3. THREE DEVIATIONS from the port sources, all found by measurement

1. **meter BLOCK 8 is not verbatim.** It carried the reference's OWN `'code': self._reload_policy.state(),`
   context line at the reference's deeper nesting (16 spaces) while the live anchor has that same line at 12.
   Inserted verbatim it would have duplicated the key AND broken indentation. Applied as its two NEW keys
   (`meterPushes`, `statsPushes`) re-indented to the live anchor's indentation. The block's own note said it
   carried "the code key above, the closing brace below"; the extracted body has 3 lines and no closing brace.
2. **The geometry call site - the manifest's suggested edit was WRONG.** `port-meter-stats-manifest.md` section 8.1
   proposed `dock_strip(work, self.strip_height)`. Live `dock_strip` is
   `def dock_strip(work, width=STRIP_WIDTH, height=STRIP_HEIGHT, margin=PANEL_MARGIN)` - WIDTH is the second
   positional parameter, so that edit passes the HEIGHT as the WIDTH. MEASURED on the running shell:
   `PANEL_PLACED mode=strip docked=bottom-strip work=1920x1032@(0,0) window=148x150@(886,870) margin=12`
   (148 wide!). The manifest itself flagged this edit as "NOT RUN by this lane - stated as the edit the code shape
   implies, not as a measured result". Corrected to the keyword form `dock_strip(work, height=self.strip_height)`,
   measured after the fix: `window=1040x100@(440,920)`.
3. **The CSS height read is guarded on the renderer.** The reference calls `refresh_strip_height` from its surface
   application with no guard; live can place the panel from `--show` before the bridge has answered, and the call
   goes through `exec_js`. Live now calls it as
   `if self.renderer_ready.is_set(): self.refresh_strip_height('place-' + str(mode))`.
   The fallback stays the honest answer when the page cannot answer (`STRIP_HEIGHT source=fallback ... why=css-unavailable`).
4. Housekeeping in the same edit: the port had introduced a SECOND `STRIP_HEIGHT_FALLBACK = 148` (the block carries
   the constant; live already had it at line 640) - the duplicate was removed, and one bare LF introduced by the
   fix was repaired (0 bare LF today).

## 4. Live verification of Alt+C on the ported revision

Real `WM_HOTKEY` posts to the shell's own hotkey thread (`PostThreadMessageW(thread, 0x0312, 0xB0F0, 0)`),
shell pid 12220 launched exactly as the Run value does (`pythonw.exe sotto_webview.py --log ...`):

    HOTKEY_REGISTERED accelerator=Alt+C register=true isRegistered=true mod_norepeat=true thread=2576
    RECEIVER_READY captions=0 hasBridge=True placeholder="Waiting for audio ..."
    WORKER_AUTOSTART=started reason=default
    CODE_STATE reason=worker-started-default worker_disk=503f095df893f358 worker_stale=False
               shell_disk=d0609e55b6030c39 shell_loaded=d0609e55b6030c39 shell_stale=False
    STRIP_HEIGHT from=148 to=100 source=css css_value=100 extra=0 reason=place-strip
    PANEL_PLACED mode=strip docked=bottom-strip work=1920x1032@(0,0) window=1040x100@(440,920) margin=12
    PANEL_SHOWN reason=hotkey mode=strip visible=true show=SW_SHOW+FOREGROUND focus_stolen=intentional(hotkey)
    PANEL_HIDDEN reason=hotkey visible=false

So: the hotkey registers and delivers, the strip surface applies at 1040 wide, the height comes FROM THE STYLESHEET
(the live CSS says 100, not the 150 the older lane measured), the worker autostarts by default, and the running
code is the code on disk. After the last edit the panel was confirmed OFF SCREEN
(`_main/panel-state.json` -> `shell.visible=false`).

## 5. What the port did NOT close - measured, per instrument

| battery step | before | after the port | why it is still red |
|---|---|---|---|
| `strip-stats-log-budget` | rc=1 | **rc=0, "STRIP-LOG CONTROL PASS"** | closed |
| `strip-hot-reload` | rc=3 | **rc=0** | closed (its survey still prints a vacuous ABSENT row for `stats`, which now exists) |
| `strip-surface-oracle` | rc=3 | rc=3, verdict **CRASH** | it raises `AttributeError: module 'sotto_real' has no attribute 'clamp_geometry'` at its line 107 - the clamp/restore/surface subsystem is NOT in the 22 blocks |
| `strip-geometry-restore` | rc=3 | rc=3, 3 of 6 checks red | the shell never READS `_main/panel-visibility.json` back: live has zero occurrences of `clamp_geometry`, `restore_saved_geometry`, `geometry_snapshot`, `work_area` |
| `strip-stats-wave` | rc=3 | rc=3, 8 of 15 checks red | the probe's own arm summaries are EMPTY objects and it wrote no per-arm log for its newest stamp - under diagnosis |
| `strip-surface-runtime` | rc=3 | rc=3, 14 of 21 checks red | arms A/C/D demand the surface/edit/tray subsystem (tray item "Edit caption position", edit mode, bridge member count) |

The oracle's own member census names exactly what is missing: `SottoShell.{set_panel_surface, set_edit_mode,
edit_drag_to, set_strip_height, geometry_for, geometry_snapshot, restore_saved_geometry, work_area,
_apply_window_geometry}`, a `surface` parameter on `show_panel`, `clamp_geometry` + `normalise_surface_name` +
`SURFACE_NAMES` at module level, `ID_TRAY_EDIT` + the tray menu item, and seven needles in `BOOTSTRAP_JS`.
That extraction is IN FLIGHT; this receipt records the state before it lands.

## 6. A self-inflicted loss, and the rules that came out of it

While writing the port the applier did `open(LIVE, 'wb').write(new.encode('latin1'))` and the file was UTF-8:
Python evaluates `open(...)` FIRST (truncating the target to 0 bytes) and then the argument raised
`UnicodeEncodeError` - so the live shell was destroyed by a failed write. The pre-write copy had itself been
overwritten by the NEXT run of the same script (which copied the now-empty file). Recovery: the shell was restored
byte-exactly from `git show HEAD:app/webview/sotto_webview.py` (CRLF re-normalised) and verified -
`size=337049 sha256=056FAC42DBE74190...`, `py_compile rc=0`. Rules adopted, all in the applier:
encode BEFORE opening for write; assert the base sha256 before touching a file; never overwrite a backup with a
copy of the current state without checking its size first.

## 7. NOT PROVEN

- The four red steps above are not closed; the surface/edit/tray subsystem is not ported yet.
- The strip height of 100 comes from the live stylesheet at this instant; no claim is made about what the owner
  will see after a theme change (the read is once per real change, and the log names the reason).
- The `_strip-reload-probe.py` survey defect (10 hardcoded ABSENT rows) is not fixed.
- Per-app audio separation: untouched by this receipt.
