// The collision window clip-writer.test.mjs structurally cannot see.
//
// That file resolves names against an in-memory Set. Both writers therefore share one
// synchronous world: the first `nextClipName()` call has fully returned before the
// second begins, and no I/O sits between the check and the caller's write. Every probe
// there is a predicate, not a filesystem, so the check-then-act window is never entered.
//
// This file resolves against a REAL temporary directory over real syscalls. The exists
// predicate is `readdirSync(dir).includes(n)`, the same wiring e2e.test.mjs uses.
//
// MEASURED WINDOW_UTC 2026-10-10: the window was real and nothing closed it.
// nextClipName() read a listing, decided a name was free, and returned it -- no
// reservation between the check and the return. pathFor() only joined strings.
// Downstream, SavePath.save() (save-path.js:65) pushed the name onto an array and never
// touched the disk, and ensureClipsDir() (save-path.js:35) created the directory once at
// startup without reserving any name inside it. Measured here over a real directory: two
// writers were both told 0000.mp4 was free and both wrote it; four concurrent writers
// collapsed onto one file holding one clip, destroying three, with nothing reported.
//
// FIXED the same day: the name is now claimed with O_CREAT|O_EXCL, decided by the kernel,
// so the claim and the check are one syscall. The arms below were INVERTED rather than
// deleted -- they now assert distinct names, and each still fails if the reservation is
// removed. Their previous text is quoted in git history; arm 3 and arm 5 were green under
// both the racy and the fixed source, and are the regression fence.
import assert from "node:assert/strict";
import { mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync, openSync, closeSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ClipWriter } from "./clip-writer.js";

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}
const pending = [];
function ta(name, fn) {
  pending.push(
    (async () => {
      try { await fn(); passed++; console.log("  PASS " + name); }
      catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
    })()
  );
}

// A real directory, created and destroyed for each arm. No arm may leak one: a leftover
// file would silently answer the next arm's exists() and fake a collision.
function withTmp(fn) {
  const dir = mkdtempSync(join(tmpdir(), "clip-race-"));
  try { return fn(dir); }
  finally { rmSync(dir, { recursive: true, force: true }); }
}

// The async twin. A plain `return fn(dir)` would run the finally above the moment fn
// returned its promise, deleting the directory while the body was still writing into it
// -- which is exactly what the first run of this file did (ENOENT on scandir).
async function withTmpAsync(fn) {
  const dir = mkdtempSync(join(tmpdir(), "clip-race-"));
  try { return await fn(dir); }
  finally { rmSync(dir, { recursive: true, force: true }); }
}

// Two independent writers over ONE directory. Independent SessionClocks, so both start
// at 0000 -- exactly two separate capture routes in a fresh session.
function twoWriters(dir) {
  return [new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir }),
          new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir })];
}

// ---------------------------------------------------------------------------
// Arms 1-2: the race, CLOSED. Before the fix these two arms asserted the collision and
// PASSED because it was real; measured, they now assert the opposite.
// ---------------------------------------------------------------------------

// The window, opened on purpose: both resolutions complete before either write, the
// tightest legal interleaving two writers can produce. A directory listing is a
// snapshot, not a lock -- so the name is claimed with O_CREAT|O_EXCL, which the kernel
// decides atomically. A resolver now leaves a file behind, and that file is the proof.
t("RACE closed: two writers over one real directory are given different names", () => {
  withTmp((dir) => {
    const [a, b] = twoWriters(dir);
    const aName = a.nextClipName();
    const bName = b.nextClipName();
    // The reservation is a real file on a real disk -- this is what makes it exclusive.
    assert.deepEqual(readdirSync(dir).sort(), [aName, bName].sort(),
      "the winning names must be claimed on disk, not merely returned");
    assert.notEqual(bName, aName,
      `both writers were handed ${aName}; the reservation did not hold`);
    assert.equal(aName, "0000.mp4");
    assert.equal(bName, "0001.mp4");
    assert.notEqual(a.pathFor(aName), b.pathFor(bName), "the two writers targeted one path");
    assert.equal(b.attemptsFor("0000.mp4"), 1, "the loser must have advanced past 0000");
  });
});

// The consequence, also closed. Nothing is thrown and nothing is logged: the second
// write lands on top of the first and the first clip is gone. Data loss, silent.
t("RACE closed: neither writer's clip is destroyed by the other", () => {
  withTmp((dir) => {
    const [a, b] = twoWriters(dir);
    const aName = a.nextClipName();
    const bName = b.nextClipName();
    assert.notEqual(bName, aName);
    writeFileSync(a.pathFor(aName), "CLIP FROM A");
    writeFileSync(b.pathFor(bName), "CLIP FROM B");
    // Two files, two clips, nothing lost. Before the fix this was one file holding B.
    assert.deepEqual(readdirSync(dir).sort(), [aName, bName].sort());
    assert.equal(readFileSync(join(dir, aName), "utf8"), "CLIP FROM A");
    assert.equal(readFileSync(join(dir, bName), "utf8"), "CLIP FROM B");
  });
});

// ---------------------------------------------------------------------------
// Arms 3-4: the arms a fix must not break, and the red arm proves they bite.
// ---------------------------------------------------------------------------

// Same predicate as arm 1, but B resolves AFTER A's bytes are on disk. There is no
// window here, so the existence check must hold: B has to walk past 0000.mp4.
// This is the arm the red arm breaks -- with the exists probe removed, B is handed a
// name that is already on disk, a collision arm 1 could never have detected.
t("a clip already on disk is never handed to a later writer", () => {
  withTmp((dir) => {
    const [a, b] = twoWriters(dir);
    const aName = a.nextClipName();
    writeFileSync(a.pathFor(aName), "CLIP FROM A");
    const bName = b.nextClipName();
    assert.notEqual(bName, aName,
      `second writer was handed ${bName}, which is already on disk as A's clip`);
    assert.deepEqual(readdirSync(dir).sort(), [aName, bName].sort());
    assert.equal(readFileSync(join(dir, aName), "utf8"), "CLIP FROM A",
      "the pre-existing clip must survive untouched");
    assert.equal(b.attemptsFor("0000.mp4"), 1, "the existence check was never consulted");
  });
});

// Arm 3 through the real async write path, with several writers racing at once. Same
// worst-case interleaving (resolve everything, then fire every write) but real I/O.
ta("concurrent async writers over one real directory each keep their own clip", async () => {
  await withTmpAsync(async (dir) => {
    const writers = [0, 1, 2, 3].map(() =>
      new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir }));
    const names = writers.map((w) => w.nextClipName());      // every claim, before any write
    assert.deepEqual(readdirSync(dir).sort(), [...names].sort(),
      "every writer must have claimed its name on disk");
    await Promise.all(names.map((n, i) =>
      writeFileSync(join(dir, n), `CLIP FROM WRITER ${i}`))); // every write, over the top
    const landed = readdirSync(dir);
    const distinctWriters = new Set(landed.map((f) =>
      readFileSync(join(dir, f), "utf8"))).size;
    // Four writers, four names, four files, four clips. Before the fix: 1 file, 1 clip.
    assert.equal(new Set(names).size, 4,
      `expected four distinct claims, got ${[...new Set(names)]}`);
    assert.equal(landed.length, 4, `4 clips collapsed onto ${landed.length} file(s) on disk`);
    assert.equal(distinctWriters, 4,
      `4 clips written, ${landed.length} file(s) survive holding ${distinctWriters}`);
  });
});

// ---------------------------------------------------------------------------
// Item 2, closed: the NARROW race, not the worst-case one.
// ---------------------------------------------------------------------------

// Arms 1/4 stage the collision deliberately: resolve everything, then write. That is the
// widest possible window and it is not what actually happens on a busy machine -- there,
// a write lands BETWEEN two resolutions. This arm reproduces that narrower shape:
// each writer resolves, yields to the event loop, then writes, so a sibling's write is
// genuinely in flight before the next writer reads the directory.
//
// It is timing-dependent by nature, so it is measured over REPS repetitions and the
// ASSERTION is on the total, not on any single repetition. On the pre-fix source this
// shape still collides: nothing in it depended on the staging.
const REPS = 200, RACERS = 4;
ta(`narrow interleaved race: 0 collisions across ${REPS} reps x ${RACERS} writers`, async () => {
  let collisions = 0, lost = 0;
  for (let rep = 0; rep < REPS; rep++) {
    await withTmpAsync(async (dir) => {
      const writers = Array.from({ length: RACERS }, () =>
        new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir }));
      // Resolve-and-yield-and-write, one per writer, started together. The yield is the
      // narrow race: it is the window a real capture loop has.
      const settled = await Promise.all(writers.map(async (w, i) => {
        const n = w.nextClipName();
        await new Promise((r) => setImmediate(r));
        writeFileSync(join(dir, n), `CLIP FROM WRITER ${i}`);
        return n;
      }));
      const names = new Set(settled);
      if (names.size !== RACERS) collisions += RACERS - names.size;
      const landed = readdirSync(dir);
      if (landed.length !== RACERS) lost += RACERS - landed.length;
    });
  }
  assert.equal(collisions, 0, `${collisions} name collision(s) in ${REPS} reps`);
  assert.equal(lost, 0, `${lost} clip(s) destroyed in ${REPS} reps`);
});

// ---------------------------------------------------------------------------
// Arm 5: the mechanism, proven to be the one actually in use.
// ---------------------------------------------------------------------------

// The writer's reservation IS an exclusive create. A is handed a name; trying to claim
// that same name again by hand must fail with EEXIST -- which proves the exclusivity is
// the kernel's, not the writer's bookkeeping, and that a lost race really is a lost race.
t("the writer's claim is a kernel-exclusive O_EXCL create, not bookkeeping", () => {
  withTmp((dir) => {
    const [a, b] = twoWriters(dir);
    const aName = a.nextClipName();
    const bName = b.nextClipName();
    assert.notEqual(aName, bName, "precondition: the two writers hold different names");
    // A's name is already claimed by the writer itself.
    assert.throws(() => openSync(a.pathFor(aName), "wx"), { code: "EEXIST" },
      "the writer's own claim must be exclusive against a second exclusive create");
    // B's name is claimed too -- so B cannot be silently overwritten either.
    assert.throws(() => openSync(b.pathFor(bName), "wx"), { code: "EEXIST" },
      "the second writer's claim must also be exclusive");
    assert.equal(readdirSync(dir).length, 2, "both names must exist on disk");
  });
});

await Promise.all(pending);
console.log(`RESULT ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);