import assert from "node:assert/strict";
import { mix, sumPower, toDbFS, fromDbFS, safeGain, HEADROOM_DB } from "./audio-mix.js";

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

// The two cases must NOT give the same answer. If they do, the code has lost
// the distinction the whole module exists to express.
t("uncorrelated and correlated sums differ", () => {
  const u = mix([0.5, 0.5], { correlated: false });
  const c = mix([0.5, 0.5], { correlated: true });
  assert.ok(Math.abs(c.linear - u.linear) > 0.2,
    "the two cases collapsed to the same value");
});

t("uncorrelated is a power sum: sqrt(0.25+0.25) = 0.7071", () => {
  assert.ok(Math.abs(sumPower([0.5, 0.5]) - Math.SQRT1_2) < 1e-12);
});

t("correlated is a linear sum: 0.5+0.5 = 1.0, which clips", () => {
  const c = mix([0.5, 0.5], { correlated: true });
  assert.equal(c.linear, 1);
  assert.ok(c.dbfs >= 0, "a linear sum at unity must be at or over 0 dBFS");
});

t("the two equal signals differ by exactly the 3.01 dB headroom", () => {
  const u = mix([0.5, 0.5], { correlated: false });
  const c = mix([0.5, 0.5], { correlated: true });
  const gapDb = c.dbfs - u.dbfs;
  assert.ok(gapDb > HEADROOM_DB - 0.05 && gapDb < HEADROOM_DB + 0.05,
    `gap ${gapDb.toFixed(3)} dB is not the documented ${HEADROOM_DB}`);
});

t("uncorrelated stays under 0 dBFS where correlated does not", () => {
  const u = mix([0.5, 0.5], { correlated: false });
  assert.ok(u.dbfs < 0);
});

t("dBFS round-trips", () => {
  assert.ok(Math.abs(toDbFS(fromDbFS(-6.02)) - (-6.02)) < 1e-9);
});

t("silence is -Infinity, not NaN and not 0", () => {
  assert.equal(toDbFS(0), -Infinity);
});

t("the correlated gain keeps the worst case under 0 dBFS", () => {
  const c = mix([0.5, 0.5], { correlated: true });
  const g = safeGain(true);
  assert.ok(c.linear * g < 1, "headroom did not actually buy headroom");
});

t("an empty mix is refused", () => {
  assert.throws(() => mix([]), RangeError);
});

console.log(`RESULT ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);