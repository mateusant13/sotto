import assert from "node:assert/strict";
import { CaptionTrack, MAX_CAPTION_MS } from "./captions.js";
import { SavePath, ClipWriter } from "./index.js";
import { mkdtempSync, writeFileSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

let passed = 0, failed = 0;
function t(name, fn) {
  try { fn(); passed++; console.log("  PASS " + name); }
  catch (e) { failed++; console.log("  FAIL " + name + " :: " + e.message); }
}

const clip = () => new CaptionTrack({ clip: "0000.mp4" });

t("captions are stored in insertion order and read back sorted", () => {
  const c = clip();
  c.add("third", 300);
  c.add("first", 100);
  c.add("second", 200);
  assert.deepEqual(c.ordered().map((r) => r.text), ["first", "second", "third"]);
  assert.equal(c.count, 3);
});

t("a clip with no captions is valid and writes no sidecar", () => {
  const c = clip();
  assert.equal(c.count, 0);
  assert.equal(c.sidecar(), null);
});

t("the sidecar goes through the one writer", () => {
  // WHAT THIS ARM WAS, AND WHY IT WAS THE DEFECT.
  //
  // It built `new ClipWriter({ exists: () => false })` with no directory. A writer with
  // no directory can reserve a name but has nowhere to put bytes, so the only file it
  // could ever produce was an empty one -- which is exactly the 0-byte artifact this
  // change ends. It then called sidecar(), which passed `text.length`, a CHARACTER
  // COUNT. There is no caption file behind the number 7.
  //
  // sidecar() now hands over the text itself, and the writer is given a real directory
  // so the arm can check what landed. The assertion that matters is the last one: the
  // sidecar must contain the caption, because a name called 0000.mp4 with nothing in it
  // passes every comparison this arm used to make.
  const dir = mkdtempSync(join(tmpdir(), "shadowplay-cap-"));
  try {
    const w = new ClipWriter({ exists: (n) => readdirSync(dir).includes(n), dir });
    const p = new SavePath({ writer: w });
    const c = new CaptionTrack({ clip: "0000.mp4", savePath: p });
    c.add("hello", 0);
    c.add("world", 1500);
    assert.equal(c.sidecar(), "0000.mp4");

    assert.ok(readdirSync(dir).includes("0000.mp4"), "the sidecar is not on disk");
    const written = readFileSync(join(dir, "0000.mp4"), "utf8");
    assert.equal(written, "0\thello\n1500\tworld",
      "the sidecar must carry the timestamped caption text itself");
    assert.equal(statSync(join(dir, "0000.mp4")).size, Buffer.byteLength(written, "utf8"),
      "every byte handed in must be on disk");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

t("an empty or whitespace caption is refused", () => {
  const c = clip();
  assert.throws(() => c.add("", 0), TypeError);
  assert.throws(() => c.add("   ", 0), TypeError);
  assert.throws(() => c.add(42, 0), TypeError);
});

t("a negative or non-numeric timestamp is refused", () => {
  const c = clip();
  assert.throws(() => c.add("x", -1), RangeError);
  assert.throws(() => c.add("x", NaN), RangeError);
});

t("a caption beyond the cap is refused", () => {
  const c = clip();
  assert.throws(() => c.add("late", MAX_CAPTION_MS + 1), RangeError);
  assert.doesNotThrow(() => c.add("exactly at the cap", MAX_CAPTION_MS));
});

t("a caption track needs a clip name", () => {
  assert.throws(() => new CaptionTrack({ clip: "" }), TypeError);
});

t("captions never block the clip they belong to", () => {
  // adding captions must not touch the clip path, only its own rows
  const c = clip();
  c.add("a", 10);
  assert.equal(c.clip, "0000.mp4");
  assert.equal(c.count, 1);
});

// PERMANENT ARM, sibling of the one in audio-track.test.mjs. Same reason, same three
// branches: the inheritance probe (23370cc) measured once in a scratch file, which is not
// coverage. Branch 2 (the CONTROL) is what makes branch 1 falsifiable -- files_left===0 is
// also satisfied by a call that never wrote anything at all.
t("INHERITANCE: captions hands save() real text, not a length", () => {
  const dir = mkdtempSync(join(tmpdir(), "sp-inherit-"));
  try {
    const failing = {
      writeClip(data) {
        writeFileSync(join(dir, "0000.mp4"), Buffer.from(data));
        return "0000.mp4";
      },
    };
    // clip MUST be a string: captions.js:15 refuses an object. That refusal is what made
    // the original probe report forced=0 while everything looked green.
    const c = new CaptionTrack({ clip: "0000.mp4", savePath: new SavePath({ writer: failing }) });
    c.add("kill", 1200);
    c.sidecar();
    assert.equal(readdirSync(dir).length, 1, "REFUSAL branch: a successful save leaves exactly one file");

    let seen = null;
    const good = {
      writeClip(data) { seen = data; writeFileSync(join(dir, "0000.mp4"), Buffer.from(data)); return "0000.mp4"; },
    };
    const d = new CaptionTrack({ clip: "0001.mp4", savePath: new SavePath({ writer: good }) });
    d.add("hello", 0);
    d.sidecar();
    assert.equal(readdirSync(dir).length, 1, "control: a successful save must leave a file");
    assert.equal(typeof seen, "string",
      "control: save() must receive the text, not text.length -- received " + typeof seen);
    assert.ok(seen.length > 0, "control: the payload must be non-empty");

    let redFired = false;
    try {
      assert.equal(typeof seen, "number",
        "RED ARM: deliberately asserts the OLD broken contract (text.length) and must FAIL");
    } catch { redFired = true; }
    assert.equal(redFired, true,
      "the RED arm did not go red, so this gate cannot say NO and proves nothing");
  } finally { rmSync(dir, { recursive: true, force: true }); }
});

console.log(`RESULT ${passed} passed, ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);