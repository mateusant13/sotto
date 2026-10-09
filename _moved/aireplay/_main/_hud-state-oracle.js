/* THE HEADLESS ORACLE — `_hud-state-oracle.js`.
 *
 * WHY IT IS DOM-FREE. SPEC §6 PASS-5, PASS-6 and PASS-9 are all "feed the state
 * table in, read what comes out", and none of them needs a window. Running them
 * in a real WebView2 would put a window on the owner's screen to learn something
 * a pure function can answer — and this repo's rule 1 makes every avoidable
 * window a liability. So: `hud-contract.js` is required directly, the eleven
 * states are walked, and the RESULT is printed as one `state=` line per state.
 *
 * The arms are named for the SPEC row they discharge, and every arm prints the
 * values it OBSERVED, not the values it expected.
 *
 * Usage:  node _hud-state-oracle.js [--json PATH]
 * Exit:   0 all arms green · 1 at least one red · 2 the instrument itself broke
 */

'use strict';

const path = require('path');
const fs = require('fs');
const C = require(path.join(__dirname, '..', 'src', 'ui', 'hud-contract.js'));

const SPEC = 'specs/05-overlay-hud.md';
const arms = [];
function arm(id, pass, observed) {
  arms.push({ id, pass: !!pass, observed });
  console.log(`ARM ${id} ${pass ? 'GREEN' : 'RED'} ${observed}`);
}

/* The measured fixture from SPEC §3.3, verbatim:
 *   "peak 9.2e-05 < floor 0.002 — nothing is routed into it"
 * The spec quotes it out of the sibling project's measured run
 * (`worker/runs/gate-live-silence.jsonl:11`). These are INPUTS to the render,
 * never outputs of it — a HUD that printed a peak nobody measured is worse than
 * one that says it has none. */
const SILENCE = { peak: '9.2e-05', peak_floor: '0.002' };

/* One representative context per state. Only the states that NEED facts get
 * them; IDLE with no ctx must still render a truthful line rather than crash. */
const CTX = {
  HIDDEN: {},
  ARMING: {},
  IDLE: { codec: 'H.264', bitrate_mbps: 45, ring_mb: 675 },
  RECORDING: { mode: 'gaming', resolution: '1080p60', ring_s: 119.4,
               bitrate_mbps: 45, elapsed_s: 161 },
  SAVING: { elapsed_s: 161 },
  HIDDEN_EXCLUSIVE: { reason: 'exclusive fullscreen detected' },
  ERROR_SILENT_DEVICE: SILENCE,
  ERROR_DEVICE_EXHAUSTED: { reason: 'Monitor 2 refused: WGC access denied' },
  ERROR_CORRUPT_ROW: { rejected: 1 },
  ERROR_ENCODER_REFUSED: { encoder_status: 'NVENCERR_MISSING',
                           encoder_error: 'no NVENC session available' },
  ERROR_PROTECTED: { window_class: 'DRMVideoProtectedWindow' }
};

const bindings = C.HUD_BINDINGS.map((b) => Object.assign({}, b, {
  status: b.id === 'H1' ? 'pinned' : 'registered'
}));

/* ---------------------------------------------------------------------
 * PASS-5 — every state reachable, and a DISTINCT glyph colour each.
 * The falsifier SPEC names: "a build where HIDDEN_EXCLUSIVE paints the idle
 * glyph ⇒ the distinctness assertion fails". That is what the pairwise check
 * below is: not "there are N glyphs" but "no two states share one".
 * ------------------------------------------------------------------- */
const rendered = C.tokens().map((t) => ({
  token: t,
  ctx: Object.assign({ bindings }, CTX[t]),
  plate: C.renderPlate(t, Object.assign({ bindings }, CTX[t]))
}));
arm('PASS-5-reachable', rendered.length === 11,
    `states_rendered=${rendered.length} of ${C.tokens().length} ` +
    `tokens=${C.tokens().join(',')}`);

/* The states that PAINT a plate, and the subset that is an error. Both are
 * needed by the glyph arms below and by SPEC §3.4's datum arm. HIDDEN and
 * HIDDEN_EXCLUSIVE paint NO plate (SPEC §3.1: plate alpha 0 / n.a.), so they are
 * excluded from glyph distinctness — including them would be unsatisfiable. */
const painted = rendered.filter((r) => r.plate.plate_alpha > 0);
const err_painted = painted.filter((r) => C.is_error(r.token));

/* Distinctness, AT THE LEVEL THE SPEC ACTUALLY CLAIMS.
 *
 * PASS-5's text says "paints a distinct plate glyph colour" per state, but §3.1's
 * own table assigns the SAME glyph to two different things: `ARMING` and
 * `SAVING` are both "saving (amber, pulsing)", and all five `ERROR_*` are
 * "error". So the literal per-state reading is UNSATISFIABLE against §3.1 —
 * two normative sections of the same spec contradict each other.
 *
 * WHICH ONE GOVERNS, and why. §3.1 is the state table and is the thing the
 * implementation must reproduce; PASS-5's own falsifier is the tie-breaker and
 * it names only ONE requirement: "a build where `HIDDEN_EXCLUSIVE` paints the
 * idle glyph ⇒ the distinctness assertion fails". That is a statement about
 * CONFUSABILITY, not about pairwise uniqueness. §3.1 pairs `ARMING`/`SAVING`
 * because amber-transient is deliberately one visual idea, and groups the errors
 * because "a failure must never read as recording" (§1.3) is the property that
 * actually matters.
 *
 * So the assertion is EXACTLY §1.3's requirement, which is also PASS-5's named
 * falsifier: no state may share a glyph with `IDLE`, and no error may share a
 * glyph with `RECORDING`. That is satisfiable, non-vacuous, and is what the
 * owner would actually be hurt by. The contradiction is reported in
 * `receipts/receipt-25-overlay-panel.md` rather than silently resolved.
 */
const GLYPH_OF = Object.fromEntries(rendered.map((r) => [r.token, r.plate.glyph]));
const idle_glyph = GLYPH_OF.IDLE;
const rec_glyph = GLYPH_OF.RECORDING;
const looks_idle = painted.filter((r) => r.plate.glyph === idle_glyph && r.token !== 'IDLE');
const err_as_rec = err_painted.filter((r) => r.plate.glyph === rec_glyph);
arm('PASS-5-no-state-looks-idle', looks_idle.length === 0,
    `painted_states=${painted.length} ` +
    `states_sharing_IDLEs_glyph=${looks_idle.length} ` +
    `offenders=${looks_idle.map((r) => r.token).join(',') || 'none'} ` +
    `HIDDEN_EXCLUSIVE_glyph=${GLYPH_OF.HIDDEN_EXCLUSIVE} ` +
    `IDLE_glyph=${idle_glyph} (PASS-5's named falsifier)`);
arm('PASS-5-error-never-reads-as-recording', err_as_rec.length === 0,
    `error_states=${err_painted.length} sharing_RECORDINGs_glyph=` +
    `${err_as_rec.length} error_glyph=0x${(GLYPH_OF.ERROR_SILENT_DEVICE >>> 0).toString(16).toUpperCase()} ` +
    `recording_glyph=0x${(rec_glyph >>> 0).toString(16).toUpperCase()} (SPEC §1.3)`);
/* The GROUPS the spec deliberately merges, reported so the numbers are not
 * mistaken for a defect: 2 amber-transient + 5 error + 1 each of the rest. */
const groups = {};
painted.forEach((r) => { (groups[r.plate.glyph_name] =
  groups[r.plate.glyph_name] || []).push(r.token); });
arm('PASS-5-groups-match-spec-3.1',
    (groups.saving || []).length === 2 && (groups.error || []).length === 5 &&
     (groups.armed || []).length === 1 && (groups.recording || []).length === 1,
    `glyph_groups=${Object.entries(groups).map(([k, v]) => `${k}:[${v.join(',')}]`).join(' ')} ` +
    `expected_§3.1=saving:2,armed:1,recording:1,error:5`);

/* ---------------------------------------------------------------------
 * PASS-6 — ERROR_SILENT_DEVICE's second line carries the peak AND the floor.
 * ------------------------------------------------------------------- */
const sd = rendered.find((r) => r.token === 'ERROR_SILENT_DEVICE').plate;
const has_peak = sd.line2.indexOf(SILENCE.peak) >= 0;
const has_floor = sd.line2.indexOf(SILENCE.peak_floor) >= 0;
arm('PASS-6-silent-device-facts', has_peak && has_floor,
    `line2=${JSON.stringify(sd.line2)} has_peak=${has_peak} ` +
    `has_floor=${has_floor}`);

/* And the honesty inverse: with NO measurement, the line must SAY it has none
 * rather than print a zero that looks measured. This is the arm a careless
 * implementation fails. */
const sdNone = C.error_line_2('ERROR_SILENT_DEVICE', {});
const honest = sdNone.indexOf('not measured') >= 0 &&
               sdNone.indexOf('0.000') < 0;
arm('PASS-6-unmeasured-says-so', honest,
    `line2=${JSON.stringify(sdNone)} says_not_measured=` +
    `${sdNone.indexOf('not measured') >= 0} prints_a_fake_zero=` +
    `${sdNone.indexOf('0.000') >= 0}`);

/* ---------------------------------------------------------------------
 * PASS-9 — `hud_state=` in the log string-equals the enum name.
 * The defect this reproduces is the sibling project's
 * `exit3-armB-worker.jsonl`: a `done` verdict that disagreed with the emitted
 * state inside ONE run. Here it is a render whose line 1 is a friendly phrase.
 * ------------------------------------------------------------------- */
const friendly = rendered.filter((r) => r.plate.line1 !== r.token);
arm('PASS-9-line1-is-enum-name', friendly.length === 0,
    `mismatched=${friendly.length} ` +
    `observed=${friendly.map((r) => `${r.token}->${r.plate.line1}`).join(',') || 'none'}`);

/* ---------------------------------------------------------------------
 * §1.1's CEILING — three lines, never four. A long reason is clamped, not
 * wrapped, so this cannot be defeated by a long string.
 * ------------------------------------------------------------------- */
const over = rendered.filter((r) => r.plate.line_count > 3);
const longest = rendered.reduce((m, r) => Math.max(m, r.plate.line_count), 0);
arm('SPEC-1.1-three-line-ceiling', over.length === 0,
    `max_lines=${longest} states_over=${over.length} ` +
    `over=${over.map((r) => `${r.token}:${r.plate.line_count}`).join(',') || 'none'}`);

/* A deliberately enormous reason — the adversarial input for the ceiling. */
const huge = C.renderPlate('ERROR_DEVICE_EXHAUSTED',
    { reason: 'x'.repeat(4000) });
arm('SPEC-1.1-ceiling-holds-at-4000-chars', huge.line_count <= 3,
    `chars_in=4000 line_count=${huge.line_count} ` +
    `line2_len=${huge.line2.length} (clamped by the binder's ellipsis, not here)`);

/* ---------------------------------------------------------------------
 * §3.4 rule 1 — errors are STICKY, and §4.3 — a taken key says it is taken.
 * ------------------------------------------------------------------- */
const err = rendered.filter((r) => C.is_error(r.token));
const non_empty = err.filter((r) => r.plate.line2.length > 0);
arm('SPEC-3.4-error-carries-a-datum', err.length === 5 && non_empty.length === 5,
    `error_states=${err.length} with_line2=${non_empty.length} ` +
    `tokens=${err.map((r) => r.token).join(',')}`);

const bl = C.binding_line(bindings);
arm('SPEC-4.3-binding-line-not-silent',
    bl.indexOf('Alt+F9 taken by another app') >= 0,
    `line3=${JSON.stringify(bl)}`);

/* ---------------------------------------------------------------------
 * SPEC §5 — the DPI rule and the 25 % cap.
 * ------------------------------------------------------------------- */
const dpi_cases = [[96, 1920], [96, 2560], [96, 3840], [144, 3840], [192, 3840]];
const widths = dpi_cases.map(([dpi, dw]) => ({
  dpi, dw, w: C.plate_width_px(dpi, dw),
  font: C.scale_px('font_px_primary', dpi),
  share: C.plate_width_px(dpi, dw) / dw
}));
const cap_ok = widths.every((w) => w.share <= 0.25 + 1e-9);
const clamp_ok = widths.every((w) => w.font >= 12 && w.font <= 22);
arm('SPEC-5-dpi-and-25pct-cap', cap_ok && clamp_ok,
    widths.map((w) => `dpi${w.dpi}@${w.dw}:w=${w.w} font=${w.font} ` +
                      `share=${(w.share * 100).toFixed(1)}%`).join(' | ') +
    ` cap_ok=${cap_ok} font_clamped_12_22=${clamp_ok}`);

/* Every parameter the panel reads must EXIST. An unused key is a deleted key in
 * this repo, and a missing one is a crash at load. */
const dangling = C.used_params().filter((k) => !C.PARAMS[k]);
arm('SPEC-7-no-inert-param', dangling.length === 0,
    `params_declared=${C.used_params().length} ` +
    `dangling=${dangling.join(',') || 'none'} ` +
    `names=${C.used_params().join(',')}`);

/* ---------------------------------------------------------------------
 * THE DISJOINTNESS ASSERTION — DEAL §6.3, and the SECOND reported
 * contradiction. `hud-contract.js`'s `HUD_BINDINGS` header says the reasoning;
 * this is where it is measured.
 *
 * DEAL §6.3: "Duplicate bindings must be refused at arm time … §2.1 and §2.4
 * are disjoint today". §2.1 (the replay ladder) and §2.4 (the overlay chain)
 * are indeed disjoint — that is the claim this arm enforces as a HARD ZERO,
 * and it is the one that protects Alt+C from the replay keys.
 *
 * But SPEC §4.2's HUD table deliberately re-uses five of §2.1's rungs (H1, H3,
 * H4, H5, H6 each cite a `trigger.cpp` line as the rung they match). Read
 * literally, §6.3 would refuse 5 of SPEC's own rows. The invariant that is
 * actually load-bearing — and non-vacuous — is:
 *   (a) overlay x replay-ladder == 0   (DEAL §2.4's claim, enforced as zero)
 *   (b) overlay x hud-table   == 0   (Alt+C can never collide with a HUD key)
 *   (c) hud x replay overlaps are ALL DECLARED via `dup_of` — an UNDECLARED
 *       overlap is the defect §6.3 is really about, and it fails here.
 * ------------------------------------------------------------------- */
const c_overlay_replay = C.collisions(C.OVERLAY_BINDINGS, C.REPLAY_LADDER);
const c_overlay_hud = C.collisions(C.OVERLAY_BINDINGS, C.HUD_BINDINGS);

const declared = new Set(C.HUD_BINDINGS.filter((b) => b.dup_of).map((b) => b.name));
const replayNames = new Set(C.REPLAY_LADDER.map((r) => r.name));
const overlaps = C.HUD_BINDINGS.filter((b) => replayNames.has(b.name));
const undeclared = overlaps.filter((b) => !b.dup_of);

arm('DEAL-6.3-overlay-vs-replay-disjoint', c_overlay_replay.length === 0,
    `pairs=${c_overlay_replay.length} ` +
    `overlays=[${C.OVERLAY_BINDINGS.map((b) => b.name)}] ` +
    `ladder=[${C.REPLAY_LADDER.map((r) => r.name)}]`);
arm('DEAL-6.3-overlay-vs-hud-disjoint', c_overlay_hud.length === 0,
    `pairs=${c_overlay_hud.length} ` +
    `overlaps=${c_overlay_hud.join(',') || 'none'}`);
arm('DEAL-6.3-hud-overlaps-all-declared', undeclared.length === 0,
    `hud_rows_mirroring_a_rung=${overlaps.length} ` +
    `declared_via_dup_of=${overlaps.length - undeclared.length} ` +
    `undeclared=${undeclared.map((b) => b.id + '/' + b.name).join(',') || 'none'} ` +
    `declared=${overlaps.map((b) => `${b.id}:${b.name}<-${b.dup_of}`).join(' ')}`);

/* F12 must be LAST in the ladder — DEAL §2.2, which contradicts
 * `trigger.cpp:65` on purpose (MS Learn reserves F12 for the debugger). */
const last = C.REPLAY_LADDER[C.REPLAY_LADDER.length - 1];
arm('DEAL-2.2-F12-last', last.name === 'F12',
    `ladder_tail=${C.REPLAY_LADDER.map((r) => r.name).join(' > ')} ` +
    `last=${last.name}`);

/* ---------------------------------------------------------------------
 * THE CONTROL ARM, IN ONE PROCESS. `collisions` is handed an identical pair and
 * MUST report it. A control that stays green is a failing control, so this lives
 * next to the assertion it validates: if `collisions` ever returned [] for a
 * real duplicate, every DISJOINT arm above would be vacuous.
 *
 * NOTE THE ARITHMETIC, because it is the bug this arm was written to catch in
 * ITSELF: `collisions(a, b)` is |a| x |b| pairs, so a 2-row list against a
 * 1-row slice yields TWO hits (X<->X and Y<->X), not one. The first run of this
 * arm asserted `=== 1` and went RED for exactly that reason — the oracle's
 * arithmetic, not the detector. The assertion below checks the DETECTED PAIRS,
 * which is what the arm is actually for.
 * ------------------------------------------------------------------- */
const fake = [{ name: 'X', vk: 0x78, mods: 1 }, { name: 'Y', vk: 0x78, mods: 1 }];
const found = C.collisions(fake, fake.slice(0, 1));
arm('CONTROL-collisions-detects-real-duplicate',
    found.length === 2 && found.includes('X <-> X') && found.includes('Y <-> X'),
    `input=X(vk=0x78,mods=1),Y(same) vs [X] detected=${found.length} ` +
    `found=${found.join(' | ')} expected=2 (|a|x|b|)`);

/* The negative control for the SAME function: two DIFFERENT pairs must produce
 * zero, or a detector that always returns non-empty would pass the arm above. */
const none = C.collisions([{ name: 'X', vk: 0x78, mods: 1 }],
                          [{ name: 'Z', vk: 0x78, mods: 2 }]);
arm('CONTROL-collisions-clean-on-distinct', none.length === 0,
    `input=X(vk=0x78,mods=1) vs Z(vk=0x78,mods=2) detected=${none.length} ` +
    `found=${none.join('|') || 'none'} (same vk, different mods => not a pair)`);

/* ---------------------------------------------------------------------
 * SUMMARY
 * ------------------------------------------------------------------- */
const red = arms.filter((a) => !a.pass);
console.log('');
console.log(`POPULATION arms=${arms.length} ` +
            `states_rendered=${rendered.length} ` +
            `bindings_declared=${C.HUD_BINDINGS.length} ` +
            `dpi_cases=${dpi_cases.length}`);
console.log(`WINDOW none — headless, no window was created, no audio, no display ` +
            `required (see the file header for why)`);
console.log(`VERDICT ${red.length === 0 ? 'PASS' : 'FAIL'} ` +
            `green=${arms.length - red.length} red=${red.length}` +
            (red.length ? ` failed=[${red.map((a) => a.id).join(',')}]` : ''));

const jidx = process.argv.indexOf('--json');
if (jidx > 0 && process.argv[jidx + 1]) {
  fs.writeFileSync(process.argv[jidx + 1],
    JSON.stringify({ arms, rendered, widths }, null, 2), 'utf8');
}
process.exit(red.length === 0 ? 0 : 1);