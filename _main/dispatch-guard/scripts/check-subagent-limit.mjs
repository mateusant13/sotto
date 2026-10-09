// check-subagent-limit.mjs - the gate the 2026-10-05 fleet-sizing work needs, and
// which did not exist. NOT a hook: it is a checker you run, like the other
// law-lints in this workspace.
//
// THE GAP IT CLOSES. Owner directive, 2026-10-05, on the subagent concurrency
// ceiling: a gate that searched the logs for "limit 4" would pass with 50 applied,
// because the refusal carries no number. Worse, the number a reader is TOLD to
// quote is a decoy. The whole chain was measured on this host; each link is
// reproduced below with the artifact it came from, so nothing here is remembered,
// it is re-measured every run:
//
//   1. config.yaml:154-155          subagent.maxConcurrentPerSession: 12
//                                   (backup config.yaml.bak-50-20261005 held 50)
//   2. runtime-services-composition.ts:244-251
//        createDesktopSubagentConcurrency({
//          maxConcurrentPerSession:
//            input...configBuilder.config().subagent?.maxConcurrentPerSession, })
//                                   -> the key IS wired. The ceiling is reachable.
//   3. subagent-config.ts:16-29      parseSubagentConfig prefers the configured
//                                   value, and falls back to
//                                   SUBAGENT_CONFIG_DEFAULTS.maxConcurrentPerSession
//                                   (subagent-config.ts:7 = 4) when it is absent,
//                                   not a safe integer, or <= 0.
//   4. subagent-concurrency-admission.ts:16
//        export const DESKTOP_SUBAGENT_CONCURRENCY_LIMIT =
//          SUBAGENT_CONFIG_DEFAULTS.maxConcurrentPerSession;      // always 4
//                                   -> THE DECOY. It is the DEFAULT, not the
//                                   enforcement value. Quoting it as "the limit"
//                                   is wrong: enforcement goes through 2 -> 3.
//   5. injected-conversation-task-turn.ts:137-142
//        errorMessage: 'This parent Session has reached its configured
//        child-Agent concurrency limit. Wait for one to finish, then retry.'
//                                   -> carries NO number. CONFIRMED.
//
// THE THREE REDS. Each is a silent-failure mode, not a style preference:
//   R1 the configured value is missing or invalid -> 3 silently falls back to 4.
//      A typo in the section name (`subagents:`) is indistinguishable, from the
//      outside, from a ceiling that was never set.
//   R2 the composition stops wiring the key -> config.yaml becomes decorative and
//      every value in it is a lie.
//   R3 the refusal still carries no number -> no log-based gate can ever learn the
//      applied limit, which is the exact hole this file was written to close.
//
// WHAT IT CANNOT SEE, stated rather than implied: it reads the CONFIGURED value,
// never the RUNNING one. Whether the process that is live right now enforces 12,
// 50 or 4 is a restart-and-observe fact, and this gate makes no claim about it.
// It answers one question only: is the configured ceiling REACHABLE and NAMED.
//
// EXIT CODES - an rc carries a VERDICT, never a CAUSE.
//   0  PASS       configured ceiling reachable, wired, and the refusal names it.
//   1  RED        at least one of R1/R2/R3 holds. The cause is named per red.
//   2  NO VERDICT an input was absent or unreadable - the question was not asked.
//   3  NO VERDICT usage error.

import { existsSync, readFileSync } from "node:fs";

const USAGE =
  "usage: check-subagent-limit.mjs [--help] [--selftest]\n" +
  "  Measures the subagent concurrency ceiling end to end and refuses to pass if\n" +
  "  the configured value is unreachable, unwired, or unnamed in the refusal.\n" +
  "\n" +
  "exit codes (an rc carries a VERDICT, never a CAUSE):\n" +
  "  0  PASS        reachable + wired + refusal names the number\n" +
  "  1  RED         R1 unreachable/invalid, R2 not wired, or R3 refusal unnamed\n" +
  "  2  NO VERDICT  an input is absent or unreadable; nothing was concluded\n" +
  "  3  NO VERDICT  usage error\n" +
  "\n" +
  "environment (both default to this host):\n" +
  "  MCO_GUARD_CONFIG  path to config.yaml\n" +
  "  MCO_GUARD_ASAR    path to the runtime app.asar\n";

// The four files that make up the chain, matched by path suffix inside the asar.
const SRC_CONFIG = "@mavis/config/src/subagent-config.ts";
const SRC_ADMISSION = "local-runtime-v2/src/service/turn-system/execution/subagent-concurrency-admission.ts";
const SRC_COMPOSITION = "local-runtime-v2/src/application/session/runtime-services-composition.ts";
const SRC_REFUSAL = "@mavis/local-runtime/src/api/injected-conversation-task-turn.ts";

const DEFAULT_ASAR =
  "H:/Users/Administrador/AppData/Local/Programs/MiniMax Code/resources/app.asar";
const DEFAULT_CONFIG = "C:/Users/Administrador/.minimax/config.yaml";

/** Minimal asar reader. The format is a 16-byte prefix, a JSON header, then data. */
export function readAsarSources(asarPath, wanted) {
  const buf = readFileSync(asarPath);
  const jsonLen = buf.readUInt32LE(12);
  const dataStart = 8 + buf.readUInt32LE(4);
  const header = JSON.parse(buf.slice(16, 16 + jsonLen).toString("utf8"));
  const out = {};
  const want = new Set(wanted);
  (function walk(node, prefix) {
    for (const [k, v] of Object.entries(node.files || {})) {
      const q = prefix ? prefix + "/" + k : k;
      if (v.files) { walk(v, q); continue; }
      for (const w of want) {
        if (q.endsWith(w)) {
          const b = Buffer.alloc(v.size);
          b.set(buf.slice(dataStart + Number(v.offset), dataStart + Number(v.offset) + v.size));
          out[w] = b.toString("utf8");
        }
      }
    }
  })(header, "");
  return out;
}

/**
 * Read `subagent.maxConcurrentPerSession` out of the YAML WITHOUT a YAML parser.
 * Deliberately not a dependency: this must run on a host where the runtime's own
 * modules are not installed, and a wrong parse must be a named NO-VERDICT rather
 * than a plausible number.
 * Returns { value, found, reason }.
 */
export function readConfiguredLimit(text) {
  const lines = String(text).split(/\r?\n/);
  let inSubagent = false;
  let subagentIndent = -1;
  for (const raw of lines) {
    const line = raw.replace(/#.*$/, "").replace(/\s+$/, "");
    if (line === "") continue;
    const indent = line.length - line.trimStart().length;
    if (/^subagent\s*:\s*$/.test(line.trim())) { inSubagent = true; subagentIndent = indent; continue; }
    if (!inSubagent) continue;
    if (indent <= subagentIndent && line.trim() !== "") { break; } // left the section
    const m = /^(maxConcurrentPerSession\s*:\s*)(.+?)\s*$/.exec(line.trim());
    if (!m) continue;
    const raw2 = m[2].replace(/^["']|["']$/g, "");
    if (!/^\d+$/.test(raw2)) {
      return { value: null, found: true, reason: "not_an_integer:" + raw2 };
    }
    const n = Number(raw2);
    if (!Number.isSafeInteger(n) || n <= 0) {
      return { value: null, found: true, reason: "out_of_range:" + raw2 };
    }
    return { value: n, found: true, reason: null };
  }
  return { value: null, found: false, reason: "key_absent" };
}

/** The runtime's own default, read from the bundle rather than remembered. */
export function readRuntimeDefault(srcConfig) {
  const m = /maxConcurrentPerSession\s*:\s*(\d+)/.exec(srcConfig || "");
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isSafeInteger(n) && n > 0 ? n : null;
}

/** Is the config key actually handed to the admission policy? */
export function isWired(srcComposition) {
  if (!srcComposition) return false;
  const at = srcComposition.indexOf("createDesktopSubagentConcurrency({");
  if (at < 0) return false;
  const call = srcComposition.slice(at, at + 400);
  return /subagent/.test(call) && /maxConcurrentPerSession/.test(call);
}

/** Does the refusal the user actually sees carry the number? */
export function refusalCarriesNumber(srcRefusal) {
  if (!srcRefusal) return null;
  const at = srcRefusal.indexOf("concurrency limit");
  if (at < 0) return null;
  const window = srcRefusal.slice(Math.max(0, at - 400), at + 200);
  return /\d/.test(window.replace(/^.*concurrency limit$/, ""));
}

/**
 * The pure half: measured facts in, one verdict out. Exported so the self-test
 * can drive every RED without a file system.
 *   facts = { keyFound, configured, configReason, runtimeDefault, wired, refusalNames }
 *
 * `keyFound` means THE KEY WAS FOUND, and it is deliberately NOT the same field
 * as "the config file exists". Conflating the two was a real defect this file
 * shipped with: a renamed section (`subagents:`) then reported itself as an
 * "invalid value" instead of an absent key, and the pure function and the real
 * collect() path disagreed about what the field meant. The end-to-end arm E4 is
 * what caught it.
 * Returns "PASS" | "RED".
 */
export function assess(facts) {
  if (!facts || facts.keyFound !== true) return "RED";        // R1a absent
  if (facts.configured === null) return "RED";                // R1b invalid
  if (facts.wired !== true) return "RED";                     // R2
  if (facts.refusalNames !== true) return "RED";              // R3
  return "PASS";
}

function collect(configPath, asarPath) {
  const facts = {
    configured: null, configReason: null, keyFound: false, configPresent: false,
    runtimeDefault: null, wired: null, refusalNames: null,
    where: { config: configPath, asar: asarPath },
  };
  if (!existsSync(configPath)) { facts.configReason = "config_absent"; return facts; }
  facts.configPresent = true;
  const cfg = readConfiguredLimit(readFileSync(configPath, "utf8"));
  facts.keyFound = cfg.found;
  facts.configured = cfg.value;
  facts.configReason = cfg.reason;
  if (!existsSync(asarPath)) { facts.configReason = facts.configReason || "asar_absent"; return facts; }
  let src;
  try {
    src = readAsarSources(asarPath, [SRC_CONFIG, SRC_ADMISSION, SRC_COMPOSITION, SRC_REFUSAL]);
  } catch (err) {
    facts.configReason = "asar_unreadable:" + (err && err.message ? String(err.message).slice(0, 80) : "?");
    return facts;
  }
  const missing = [SRC_CONFIG, SRC_COMPOSITION, SRC_REFUSAL].filter((k) => !src[k]);
  if (missing.length > 0) { facts.configReason = "asar_missing_sources:" + missing.length; return facts; }
  facts.runtimeDefault = readRuntimeDefault(src[SRC_CONFIG]);
  facts.wired = isWired(src[SRC_COMPOSITION]);
  facts.refusalNames = refusalCarriesNumber(src[SRC_REFUSAL]);
  return facts;
}

function report(facts) {
  const reds = [];
  if (facts.keyFound !== true) reds.push("R1 config key absent -> the runtime falls back to its default, and a typo is indistinguishable from a ceiling that was never set");
  else if (facts.configured === null) reds.push("R1 configured value invalid (" + facts.configReason + ") -> silent fallback to the default");
  if (facts.wired === false) reds.push("R2 the composition does not pass subagent.maxConcurrentPerSession to the admission policy -> config.yaml is decorative");
  if (facts.refusalNames === false) reds.push("R3 the refusal carries no number -> no log-based gate can learn the applied limit; a search for \"limit 4\" would pass with 50 applied");
  process.stdout.write("configured_ceiling = " + (facts.configured ?? "UNREACHABLE") + "\n");
  process.stdout.write("runtime_default   = " + (facts.runtimeDefault ?? "UNKNOWN") + "  (the decoy DESKTOP_SUBAGENT_CONCURRENCY_LIMIT)\n");
  process.stdout.write("wired_to_policy  = " + facts.wired + "\n");
  process.stdout.write("refusal_names_it = " + facts.refusalNames + "\n");
  if (facts.configured !== null && facts.runtimeDefault !== null && facts.configured === facts.runtimeDefault) {
    process.stdout.write(
      "NOTE: the configured value EQUALS the runtime default, so this run cannot distinguish " +
        "\"set to the default\" from \"never wired\". A ceiling equal to the default is not evidence of a working ceiling.\n",
    );
  }
  process.stdout.write("verdict: " + (reds.length === 0 ? "PASS" : "RED") + "\n");
  for (const r of reds) process.stdout.write("  - " + r + "\n");
  return reds.length;
}

function main() {
  const argv = process.argv.slice(2);
  if (argv.includes("--help") || argv.includes("-h")) { process.stdout.write(USAGE + "\n"); process.exit(0); }
  if (argv.includes("--selftest")) { process.exit(selftest()); }
  for (const a of argv) {
    process.stderr.write("check-subagent-limit: USAGE ERROR: unknown option '" + a + "'\n" + USAGE + "\n");
    process.exit(3);
  }
  const configPath = process.env.MCO_GUARD_CONFIG || DEFAULT_CONFIG;
  const asarPath = process.env.MCO_GUARD_ASAR || DEFAULT_ASAR;
  let facts;
  try {
    facts = collect(configPath, asarPath);
  } catch (err) {
    process.stdout.write("verdict: NO VERDICT (" + (err && err.message ? String(err.message).slice(0, 100) : "unknown") + ")\n");
    process.exit(2);
  }
  if (!existsSync(configPath) || !existsSync(asarPath)) {
    process.stdout.write("verdict: NO VERDICT (an input is absent; nothing was concluded)\n");
    process.exit(2);
  }
  const reds = report(facts);
  process.exit(reds === 0 ? 0 : 1);
}

// ---- the self-test ---------------------------------------------------------
// Fixture-driven, and it builds a REAL asar so the reader is exercised rather
// than assumed. Every RED is produced from a fixture that differs from the green
// one in exactly the fact under test.
function selftest() {
  let pass = 0, fail = 0;
  const check = (name, ok, detail) => {
    ok ? (pass += 1) : (fail += 1);
    process.stdout.write(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? "\n         " + detail : ""}\n`);
  };

  const CFG_OK = "# c\nsubagent:\n  maxConcurrentPerSession: 12\ndefaultModelContextWindow: 512000\n";
  const CFG_MISSING = "# c\ndefaultModelContextWindow: 512000\n";
  const CFG_INVALID = "subagent:\n  maxConcurrentPerSession: many\n";
  const SRC_CFG = "export const SUBAGENT_CONFIG_DEFAULTS: SubagentConfig = {\n  maxConcurrentPerSession: 4,\n};\n" +
    "export function parseSubagentConfig(raw) {\n  const maxConcurrentPerSession = config.maxConcurrentPerSession;\n" +
    "  return { maxConcurrentPerSession: typeof x === 'number' && Number.isSafeInteger(x) && x > 0 ? x : 4 };\n}\n";
  const SRC_COMP_OK = "  ? createDesktopSubagentConcurrency({\n      db: input.options.db,\n" +
    "      maxConcurrentPerSession:\n        input.options.compatibility.agentHost.preparation.configBuilder.config().subagent\n" +
    "          ?.maxConcurrentPerSession,\n    })\n";
  const SRC_COMP_DEAD = "  ? createDesktopSubagentConcurrency({\n      db: input.options.db,\n    })\n";
  const SRC_REF_NO_NUM = "    errorMessage:\n      'This parent Session has reached its configured child-Agent concurrency limit. " +
    "Wait for one to finish, then retry.',\n    errorCode: SUBAGENT_CONCURRENCY_LIMIT_ERROR_CODE,\n";
  const SRC_REF_NUM = "    errorMessage:\n      'This parent Session has reached its child-Agent concurrency limit of 12. " +
    "Wait for one to finish, then retry.',\n    errorCode: SUBAGENT_CONCURRENCY_LIMIT_ERROR_CODE,\n";

  /** Build a byte-faithful minimal asar from {path: text}, nested like the real one. */
  function makeAsar(dir, name, files) {
    const parts = [];
    const root = { files: {} };
    let off = 0;
    for (const [k, t] of Object.entries(files)) {
      const bytes = Buffer.from(t, "utf8");
      const segs = k.split("/");
      let node = root;
      for (const s of segs.slice(0, -1)) {
        if (!node.files[s]) node.files[s] = { files: {} };
        node = node.files[s];
      }
      node.files[segs[segs.length - 1]] = { size: bytes.length, offset: String(off) };
      parts.push(bytes);
      off += bytes.length;
    }
    const json = Buffer.from(JSON.stringify(root), "utf8");
    const pre = Buffer.alloc(16);
    pre.writeUInt32LE(4, 0);
    pre.writeUInt32LE(8 + json.length, 4);
    pre.writeUInt32LE(json.length, 8);
    pre.writeUInt32LE(json.length, 12);
    const p = dir + "/" + name;
    writeFileSync(p, Buffer.concat([pre, json, ...parts]));
    return p;
  }

  process.stdout.write("SELFTEST check-subagent-limit\n\n");
  const dir = mkdtempSync(join(tmpdir(), "subagent-limit-"));
  const srcFiles = { [SRC_CONFIG]: SRC_CFG, [SRC_COMPOSITION]: SRC_COMP_OK, [SRC_REFUSAL]: SRC_REF_NO_NUM };
  const asar = makeAsar(dir, "app.asar", srcFiles);

  // 1. the reader really reads: our own asar round-trips.
  const back = readAsarSources(asar, [SRC_CONFIG]);
  check("asar round-trip: the reader recovers a file it wrote", back[SRC_CONFIG] === SRC_CFG);

  // 2. configured value parses, and the wrong shapes are refused by name.
  const ok = readConfiguredLimit(CFG_OK);
  check("config: 12 parsed from subagent.maxConcurrentPerSession", ok.found === true && ok.value === 12);
  const miss = readConfiguredLimit(CFG_MISSING);
  check("R1 config key absent -> named, not guessed", miss.found === false && miss.reason === "key_absent");
  const bad = readConfiguredLimit(CFG_INVALID);
  check("R1 non-integer -> named", bad.found === true && bad.value === null && /^not_an_integer/.test(bad.reason));

  // 3. the three REDs, each from a fixture differing in exactly one fact.
  const green = { keyFound: true, configured: 12, configReason: null, runtimeDefault: 4, wired: true, refusalNames: true };
  check("baseline fixture is PASS", assess(green) === "PASS");
  const r1 = assess({ ...green, configured: null, keyFound: true, configReason: "not_an_integer:many" });
  check("R1b unreachable value -> RED", r1 === "RED");
  const r1b = assess({ ...green, keyFound: false });
  check("R1a section renamed -> RED (indistinguishable from R1b by the outside)", r1b === "RED");
  const r2 = assess({ ...green, wired: false });
  check("R2 key no longer wired -> RED", r2 === "RED");
  const r3 = assess({ ...green, refusalNames: false });
  check("R3 refusal carries no number -> RED", r3 === "RED");
  const three = [r1, r1b, r2, r3].filter((v) => v === "RED").length;
  check("three DISTINCT reds reachable from one green", three === 4, "red count=" + three);

  // 4. the refusals as the bundle actually carries them, measured earlier.
  check("the real refusal string carries no number (R3 is RED on this host)", refusalCarriesNumber(SRC_REF_NO_NUM) === false);
  check("a refusal that names the number passes R3", refusalCarriesNumber(SRC_REF_NUM) === true);
  check("the real composition source IS wired (so R2 is not the live defect)", isWired(SRC_COMP_OK) === true);
  check("a composition that drops the key is not wired", isWired(SRC_COMP_DEAD) === false);

  // 5. END TO END, through the REAL binary. Arms 1-4 above exercise the pure
  //    function, which is not the same claim: they would stay green even if
  //    collect()/report() were broken, and a gate whose file-reading half is
  //    broken reds on everything - including a healthy host - for the wrong
  //    reason. So the real process is spawned against fixtures, and its rc AND
  //    its printed verdict are both asserted.
  //
  //    E1 is the GREEN CONTROL and it is the load-bearing one: without a fixture
  //    that PASSES, "every fixture is red" is indistinguishable from a gate that
  //    simply never passes anything.
  const SELF = process.argv[1];
  const asarGreen = makeAsar(dir, "green.asar", {
    [SRC_CONFIG]: SRC_CFG, [SRC_COMPOSITION]: SRC_COMP_OK, [SRC_REFUSAL]: SRC_REF_NUM,
  });
  const asarR3 = makeAsar(dir, "r3.asar", {
    [SRC_CONFIG]: SRC_CFG, [SRC_COMPOSITION]: SRC_COMP_OK, [SRC_REFUSAL]: SRC_REF_NO_NUM,
  });
  const asarR2 = makeAsar(dir, "r2.asar", {
    [SRC_CONFIG]: SRC_CFG, [SRC_COMPOSITION]: SRC_COMP_DEAD, [SRC_REFUSAL]: SRC_REF_NUM,
  });
  const cfgOk = dir + "/ok.yaml"; writeFileSync(cfgOk, CFG_OK, "utf8");
  const cfgRenamed = dir + "/renamed.yaml";
  writeFileSync(cfgRenamed, CFG_OK.replace("subagent:", "subagents:"), "utf8");
  const cfgBad = dir + "/bad.yaml"; writeFileSync(cfgBad, CFG_INVALID, "utf8");

  function e2e(label, cfgPath, asarPath, wantRc, wantText) {
    const r = spawnSync(process.execPath, [SELF], {
      encoding: "utf8",
      env: { ...process.env, MCO_GUARD_CONFIG: cfgPath, MCO_GUARD_ASAR: asarPath },
    });
    const out = String(r.stdout || "");
    const ok = r.status === wantRc && out.includes(wantText);
    check(
      label,
      ok,
      ok ? "" : `want rc=${wantRc} + ${JSON.stringify(wantText)}; got rc=${r.status} + ` +
        JSON.stringify(out.split("\n").filter((l) => l.includes("verdict") || l.includes("R1") || l.includes("R2") || l.includes("R3"))[0] || "(no verdict line)"),
    );
  }
  process.stdout.write("\n  -- end to end, real binary, fixture inputs --\n");
  e2e("E1 GREEN CONTROL: reachable + wired + numbered refusal -> rc=0 PASS", cfgOk, asarGreen, 0, "verdict: PASS");
  e2e("E2 R3 end to end: refusal carries no number -> rc=1, R3 named", cfgOk, asarR3, 1, "R3 the refusal carries no number");
  e2e("E3 R2 end to end: composition drops the key -> rc=1, R2 named", cfgOk, asarR2, 1, "R2 the composition does not pass");
  e2e("E4 R1 end to end: section renamed -> rc=1, R1 named", cfgRenamed, asarGreen, 1, "R1 config key absent");
  e2e("E5 R1 end to end: value not an integer -> rc=1, reason named", cfgBad, asarGreen, 1, "not_an_integer");
  e2e("E6 NO-VERDICT: config absent -> rc=2, never 1 and never 0", dir + "/does-not-exist.yaml", asarGreen, 2, "NO VERDICT");

  process.stdout.write(`\narms_pass=${pass} arms_fail=${fail}\n`);
  process.stdout.write(`SELFTEST_VERDICT=${fail === 0 ? "PASS" : "FAIL"}\n`);
  try { rmSync(dir, { recursive: true, force: true }); } catch { /* scratch */ }
  return fail === 0 ? 0 : 1;
}

import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

main();
