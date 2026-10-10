import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync, readdirSync, readFileSync, rmSync, existsSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { SavePath, ROUTES, defaultClipWriter } from "./save-path.js";
import { ClipWriter, MAX_ATTEMPTS } from "./clip-writer.js";

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

// Every test below builds its SavePath over a throwaway LOCALAPPDATA.
//
// MEASURED 2026-10-10T19:05Z on this host, before this change: four of these tests called
// `new SavePath()` with no argument, which resolves against the real process.env and so
// reserved real files in %LOCALAPPDATA%\Sotto\clips -- 10 zero-byte 0000.mp4..0009.mp4
// placeholders were already sitting there. SessionClock restarts at 0 every session and
// MAX_ATTEMPTS is 10, so those ten orphans consume every attempt and the suite could never
// get a free name again: measured RESULT 3 passed, 3 failed, exit code 1, the three failures
// all reading "no free sequence value after 10 attempts". A test that depends on the state
// of the user's disk is not a test. Each test now owns a directory it deletes afterwards.
const roots = [];
function tempEnv(extra = {}) {
  const root = mkdtempSync(join(tmpdir(), "shadowplay-savepath-"));
  roots.push(root);
  return { LOCALAPPDATA: root, ...extra };
}
function clipsOf(env) {
  return join(env.LOCALAPPDATA ?? env.APPDATA, "Sotto", "clips");
}
// A real encoded clip, because save() now takes CONTENT and not a length.
//
// Every call below was `s.save(route, 1024)` before 2026-10-10: a number standing in for
// bytes that did not exist. That number is the shape every production caller still passes
// (replay-ring.js:130 passes a duration in seconds, audio-track.js:61 a frame count,
// captions.js:53 a character count), so this helper is what those three call sites have to
// become. It is deliberately varied per call so no test can pass by writing one constant.
let seq = 0;
function clipOf(size = 64) {
  seq += 1;
  return Buffer.alloc(size, 0x41 + (seq % 26));
}
function cleanup() {
  for (const r of roots.splice(0)) {
    try { rmSync(r, { recursive: true, force: true }); } catch { /* best effort */ }
  }
}
process.on("exit", cleanup);

t("all four declared routes save through the one writer", () => {
  const env = tempEnv();
  const s = new SavePath({ env });
  const names = ROUTES.map((r) => s.save(r, clipOf(1024)));
  assert.deepEqual(names, ["0000.mp4", "0001.mp4", "0002.mp4", "0003.mp4"]);
  assert.equal(s.written().length, ROUTES.length);
});

t("two saves on one route still get distinct names", () => {
  const env = tempEnv();
  const s = new SavePath({ env });
  assert.notEqual(s.save("hotkey", clipOf(10)), s.save("hotkey", clipOf(11)));
});

t("an unknown route is refused", () => {
  const env = tempEnv();
  const s = new SavePath({ env });
  assert.throws(() => s.save("printer", clipOf(10)), RangeError);
});

// The count-shaped contract is GONE, and that is the decision, pinned. These used to read
// "bytes must be a non-negative integer" over -1 and 1.5, which accepted the positive
// integers and so accepted the whole defect: a length where content belonged. Now every
// number is refused, and so is the absence of an argument entirely.
t("a byte COUNT is refused, and so is no argument at all", () => {
  const env = tempEnv();
  const s = new SavePath({ env });
  assert.throws(() => s.save("hotkey", -1), TypeError);
  assert.throws(() => s.save("hotkey", 1.5), TypeError);
  assert.throws(() => s.save("hotkey", 0), TypeError,
    "zero is a length too: there is no clip in it");
  assert.throws(() => s.save("hotkey", 1024), TypeError,
    "a positive integer is the shape every production caller passes today, and it is the defect");
  assert.throws(() => s.save("hotkey"), TypeError);
  assert.throws(() => s.save("hotkey", undefined), TypeError);
  assert.throws(() => s.save("hotkey", null), TypeError);
  assert.equal(s.written().length, 0, "a refused save must not be recorded as written");
  // A refused save never reaches prepare(), so the clips directory may not even exist yet.
  // Asserting the property rather than the shape: nothing was reserved, whether that means
  // "the directory is absent" or "the directory is there and empty". An earlier version of
  // this line called readdirSync unconditionally and went red with ENOENT -- a fixture
  // assumption, not a product failure.
  const dir = clipsOf(env);
  assert.equal(existsSync(dir) ? readdirSync(dir).length : 0, 0,
    "a refused save must leave no reservation behind -- one that consumed a name would " +
    "still cost the next save one of its ten attempts");
  assert.equal(s.save("hotkey", clipOf(4)), "0000.mp4",
    "and the refused saves must not have burned a sequence value");
});

// the load-bearing one: a blocked save is VISIBLE, never silent
//
// This used to be `new ClipWriter({ exists: () => true })` with no directory, which
// allocated nothing at all and asserted as though it had. It now exhausts a REAL
// directory: the first MAX_ATTEMPTS names are on disk, so every reservation genuinely
// collides. Same four assertions as before, none weakened, plus the two that make the
// exhaustion real rather than simulated.
t("an exhausted directory blocks visibly instead of writing nothing", () => {
  const env = tempEnv();
  const dir = clipsOf(env);
  mkdirSync(dir, { recursive: true });
  for (let i = 0; i < MAX_ATTEMPTS; i++) {
    writeFileSync(join(dir, String(i).padStart(4, "0") + ".mp4"), "occupied");
  }
  assert.equal(readdirSync(dir).length, MAX_ATTEMPTS, "the directory must really be full");

  const s = new SavePath({ env });
  let name = null, err = null;
  try { name = s.save("hotkey", clipOf(10)); } catch (e) { err = e; s.recordFailure("hotkey", e); }
  assert.equal(name, null);
  assert.ok(err, "an exhausted directory must throw");
  assert.equal(s.blocked(), 1);
  assert.equal(s.written().length, 0);
  // the collision must have cost nothing: no file added, no file truncated
  assert.equal(readdirSync(dir).length, MAX_ATTEMPTS);
  assert.equal(readFileSync(join(dir, "0000.mp4"), "utf8"), "occupied");
});

// Item 3 of the fix, pinned end to end: a name a real directory already holds is never
// handed out again, and the bytes already there survive. This fails if the default ever
// goes permissive.
t("an existing clip is never reported as absent and is never overwritten", () => {
  const env = tempEnv();
  const dir = clipsOf(env);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "0000.mp4"), "occupied");

  const s = new SavePath({ env });
  const name = s.save("hotkey", clipOf(10));
  assert.notEqual(name, "0000.mp4", "a name already on disk must never be handed out again");
  assert.equal(readFileSync(join(dir, "0000.mp4"), "utf8"), "occupied",
    "the existing clip must be left byte-identical");
  assert.deepEqual(readdirSync(dir).sort(), ["0000.mp4", "0001.mp4"]);
});

// Item 2's decision, made executable: there is NO permissive default. A resolver given no
// predicate cannot know what is on disk, so it refuses instead of guessing. This fails the
// moment anyone reinstates `exists: () => false` as a default.
t("the resolver has no permissive default: a missing predicate is refused, not guessed", () => {
  assert.throws(() => new ClipWriter({}), TypeError,
    "ClipWriter must refuse to be built without an exists predicate");
  assert.throws(() => new ClipWriter(), TypeError);

  // ...and the default SavePath must therefore never be one of those. It is always handed
  // a predicate that reads the real directory.
  const env = tempEnv();
  const { writer } = defaultClipWriter(env);
  assert.ok(writer instanceof ClipWriter);
  assert.equal(writer.dir, clipsOf(env), "the default writer must be pointed at a real directory");
});

// A host with no per-user data directory has no known clips location, so no name can be
// shown to be free. The old fallbacks were `exists: () => false` ("assume the disk is
// empty") and this. Failing loudly is the only answer that cannot hand out a taken name.
t("a host with no per-user data directory fails loudly instead of assuming an empty disk", () => {
  const s = new SavePath({ env: {} });
  assert.throws(() => s.save("hotkey", clipOf(10)), /cannot choose a clip name/);
  assert.equal(s.written().length, 0);
  assert.equal(s.blocked(), 0, "a refused save is not a silent one: nothing was recorded as written");
});

t("names stay chronologically sortable across routes", () => {
  const env = tempEnv();
  const s = new SavePath({ env });
  const n = ROUTES.map((r) => s.save(r, clipOf(1)));
  assert.deepEqual([...n].sort(), n);
});

// ---------------------------------------------------------------------------------------
// existsOnDisk: the predicate the suite could not see, now observed over a real directory.
//
// MEASURED 2026-10-10T19:14Z on this host, before this test existed: with a call counter
// inside existsOnDisk, the nine tests above called it ZERO times and the suite still
// reported 9 passed / 0 failed / exit 0. The cause is structural, not a missing assert.
// ClipWriter#claim (clip-writer.js:92) consults `exists` only when `dir` is null, and
// defaultClipWriter always points the writer at a real directory, so O_EXCL answered
// first; and the one test with an empty env throws out of save() at `this.#prepare?.()`
// before nextClipName() is ever reached. An unreachable function cannot fail a test, so
// `return false`, `return true` and an immediate throw all survived it.
//
// CORRECTED 2026-10-10T19:16Z: "zero times" was true of the DEFAULT writer and false as a
// general claim. Re-measured across three constructions -- default writer 0 calls, dir-less
// writer injected into SavePath 1 call, exported predicate called directly 1 call -- total 2.
// The entry is live on the degraded path and dead on the default one. The last test below
// covers the live half so the claim stays measured rather than convenient.
//
// defaultClipWriter now RETURNS the same predicate it hands the writer, so the safety
// property is observable over a real directory. These five tests are the mutants' kill.
//
// Nothing here mocks fs. Every assertion is read off the real disk through the predicate
// the production code actually uses.

// The load-bearing assertion: the same predicate, the same directory, two names -- one
// that IS on disk and one that is NOT. `exists: () => false` fails the first;
// `exists: () => true` fails the second; a throw on the first line fails both.
t("the default exists() reads the real directory: on disk is present, absent is absent", () => {
  const env = tempEnv();
  const dir = clipsOf(env);
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, "0000.mp4"), "occupied");

  const { exists } = defaultClipWriter(env);

  // precondition, so a broken fixture cannot make this pass for the wrong reason
  assert.equal(existsSync(join(dir, "0000.mp4")), true, "0000.mp4 must really be on disk");
  assert.equal(existsSync(join(dir, "0001.mp4")), false, "0001.mp4 must really be absent");

  assert.equal(exists("0000.mp4"), true,
    "a name that IS on disk must be reported PRESENT -- this is what `return false` breaks");
  assert.equal(exists("0001.mp4"), false,
    "a name that is NOT on disk must be reported ABSENT -- this is what `return true` breaks");
});

// A directory that DOES NOT exist yet is the other half of the distinction, and it is the
// case a "the disk is probably empty" shortcut gets wrong. Asserted with existsSync on the
// real path, before and after, so the transition is observed rather than assumed.
t("over a directory that does not exist yet, exists() answers absent and invents nothing", () => {
  const env = tempEnv();
  const dir = clipsOf(env);

  assert.equal(existsSync(dir), false,
    "precondition: the clips directory must really not exist before the first question");

  const { exists } = defaultClipWriter(env);
  assert.equal(exists("0000.mp4"), false,
    "nothing exists in a directory that had none -- `return true` must not survive this");

  assert.equal(existsSync(dir), true,
    "asking must have prepared the real directory, not answered from a guess");
  assert.deepEqual(readdirSync(dir), [],
    "and it must be empty: preparing a directory is not the same as finding names in it");
});

// The refusal stays a refusal. existsOnDisk must reach prepare() and inherit ITS named
// error; a throw placed before that call replaces the diagnosis with a generic one, which
// is how this mutant gets caught by message rather than by accident.
t("exists() refuses by prepare()'s named error when no data root exists", () => {
  const { exists } = defaultClipWriter({});
  assert.throws(() => exists("0000.mp4"), /cannot choose a clip name/,
    "the refusal must come from prepare(), with its diagnosis intact");
});

// The predicate and the writer must be the SAME function, not two look-alikes. If they
// could drift, the property tested above would not be the one production uses.
t("the returned predicate is the very predicate the writer was constructed with", () => {
  const env = tempEnv();
  const { writer, exists } = defaultClipWriter(env);
  mkdirSync(clipsOf(env), { recursive: true });
  writeFileSync(join(clipsOf(env), "0000.mp4"), "occupied");

  // observed effect, not object identity: the writer must skip the name its predicate
  // reports as taken. If the two were different functions, the writer would hand out
  // 0000.mp4 and this would fail.
  assert.equal(exists("0000.mp4"), true);
  assert.equal(writer.nextClipName(), "0001.mp4",
    "the writer must not hand out a name its own predicate reported as present");
});

// The live half of the measurement above. On the DEFAULT writer the predicate is never
// called, so nothing else in this suite can reach it.
//
// MEASURED WINDOW_UTC 2026-10-10T19:27Z, after save() was switched to writeClip: this test
// WENT RED, and the reason is structural rather than cosmetic. The old save() called
// nextClipName(), whose #claim asks `exists` only when the writer has no directory, so a
// dir-less writer was the one construction that reached existsOnDisk for real. writeClip()
// goes through openClip(), which refuses a dir-less writer by name -- "cannot open a clip:
// this ClipWriter has no directory" -- BEFORE any name is claimed and therefore before
// exists is consulted. So the predicate is no longer reachable through save() on ANY
// construction. That is the honest consequence of the fix, not a test that got weaker: the
// refusal still happens, still writes nothing, and is still loud. Only its message moved,
// and it moved to the earlier, more specific refusal. Making exists reachable again would
// mean editing clip-writer.js:92, which this lane does not own.
t("a dir-less writer refuses by name instead of guessing", () => {
  const { writer } = defaultClipWriter({});
  assert.equal(writer.dir, null, "precondition: this writer must really have no directory");

  const s = new SavePath({ writer });
  assert.throws(() => s.save("hotkey", clipOf(10)), /cannot open a clip/,
    "the refusal must survive the detour through the writer, and must be the writer's own");
  assert.equal(s.written().length, 0);
  assert.equal(s.blocked(), 0, "a refused save is not a silent one");
});

// The replacement for the kill this test used to provide, pointed at the mutant that
// actually matters on this path. A dir-less writer handed the PERMISSIVE predicate --
// `exists: () => false`, "assume the disk is empty", the predicate this file was changed to
// remove -- used to be told every name was free and would hand out 0000.mp4 with nothing
// behind it. It must refuse now. If save() ever regresses to name-reservation without
// content, this goes red with the permissive answer intact.
t("a dir-less writer is not made permissive by a permissive predicate", () => {
  const writer = new ClipWriter({ exists: () => false });
  assert.equal(writer.dir, null, "precondition: this writer must really have no directory");

  const s = new SavePath({ writer });
  assert.throws(() => s.save("hotkey", clipOf(10)), /cannot open a clip/,
    "`exists: () => false` must not buy a dir-less writer a free name to write nothing into");
  assert.equal(s.written().length, 0);
});

// ---------------------------------------------------------------------------------------
// The bytes. Everything above pins WHICH NAME is issued; this pins what is inside the file,
// which is the half that shipped empty.
//
// MEASURED WINDOW_UTC 2026-10-10T19:26:18Z by the operator on the writer: writeClip landed
// an exact 12288-byte payload as 12288 bytes on disk and refused a zero-byte payload with a
// TypeError. That proves the writer. It does NOT prove the product used it, and it did not:
// save() called nextClipName(), which leaves a zero-byte placeholder by design. A writer
// that works and a save path that bypasses it produce the same POP=10 empty clips.

// THE assertion that can actually fail, over a real directory and a real payload. The size
// 12288 is the operator's measured figure so the number is not invented to fit.
t("a saved clip lands its bytes: what goes in is byte-for-byte what is on disk", () => {
  const env = tempEnv();
  const s = new SavePath({ env });
  const payload = Buffer.alloc(12288);
  for (let i = 0; i < payload.length; i++) payload[i] = i % 251;

  const name = s.save("instant-replay", payload);
  const path = s.pathOf(name);

  assert.equal(statSync(path).size, payload.byteLength,
    "the file must be exactly as long as the payload -- not zero, not short");
  assert.deepEqual(readFileSync(path), payload,
    "and the bytes must be the payload's, not merely a file of the right length");
  assert.equal(s.written().length, 1, "a real save is recorded as written");
});

// The regression pin for the shipped defect, stated over the whole directory rather than
// one file: after saving through every route, NOTHING here is empty. Under the old contract
// all four files were 0 bytes and this assertion fails on the first one.
t("no clip this path writes is ever empty", () => {
  const env = tempEnv();
  const s = new SavePath({ env });
  ROUTES.forEach((r) => s.save(r, clipOf(48 + r.length)));

  const dir = clipsOf(env);
  const files = readdirSync(dir).sort();
  assert.equal(files.length, ROUTES.length, "precondition: every route really did save");
  for (const f of files) {
    assert.ok(statSync(join(dir, f)).size > 0,
      `${f} is 0 bytes: that is the artifact this whole change exists to stop`);
  }
});

// The refusal has to cost NOTHING. An empty payload is refused by the writer BEFORE it
// claims a name, so the next save still gets 0000.mp4; if the refusal came after the claim,
// the name would be burned and this test would see 0001.mp4 -- which is the exhaustion trap
// the suite header already documents, and it would arrive one save early and look healthy.
t("an empty payload is refused and reserves nothing", () => {
  const env = tempEnv();
  const s = new SavePath({ env });
  assert.throws(() => s.save("hotkey", Buffer.alloc(0)), TypeError);
  assert.throws(() => s.save("hotkey", ""), TypeError);

  const dir = clipsOf(env);
  assert.deepEqual(readdirSync(dir), [], "a refused empty payload must leave no file at all");

  const name = s.save("hotkey", clipOf(8));
  assert.equal(name, "0000.mp4",
    "the refused saves must not have consumed a sequence value");
  assert.equal(readdirSync(dir).length, 1);
});

// The properties that were already true and must still be true now that a payload is
// mandatory: the name FORMAT is unchanged, and names stay chronologically sortable. Both
// are measured on disk through the real names, not on the strings save() returned alone.
t("real content does not disturb the name format or its chronological order", () => {
  const env = tempEnv();
  const s = new SavePath({ env });
  const names = ROUTES.map((r) => s.save(r, clipOf(2048)));
  for (const n of names) assert.match(n, /^\d{4}\.mp4$/, `name format changed: ${n}`);
  assert.deepEqual([...names].sort(), names, "names must still sort chronologically");

  // ...and the sort must describe the disk, not just the array: these are the same clips
  // in the same order when the directory is read back the way a player would read it.
  assert.deepEqual(readdirSync(clipsOf(env)).sort(), [...names].sort());
});

console.log(`RESULT ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);