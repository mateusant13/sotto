import assert from "node:assert/strict";
import { Broadcast, TRANSPORTS } from "./broadcast.js";

let passed = 0, failed = 0;
function t(name, fn) {
  return Promise.resolve()
    .then(fn)
    .then(() => { passed++; console.log("  PASS " + name); })
    .catch((e) => { failed++; console.log("  FAIL " + name + " :: " + e.message); });
}

const ok = async () => true;

const run = async () => {
  await t("three transports are declared", () => {
    assert.equal(TRANSPORTS.length, 3);
    assert.deepEqual([...TRANSPORTS].sort(), ["rtmp", "srt", "whip"]);
  });

  await t("each declared transport can be constructed", () => {
    for (const tr of TRANSPORTS) {
      const b = new Broadcast({ transport: tr, target: "rtmp://x/y" });
      assert.equal(b.transport, tr);
      assert.equal(b.live, false);
    }
  });

  await t("an unsupported transport is refused", () => {
    assert.throws(() => new Broadcast({ transport: "carrier-pigeon", target: "x" }), RangeError);
  });

  await t("an empty target is refused", () => {
    assert.throws(() => new Broadcast({ transport: "rtmp", target: "" }), TypeError);
  });

  await t("going live without a probe is refused", async () => {
    const b = new Broadcast({ transport: "rtmp", target: "rtmp://x/y" });
    await assert.rejects(() => b.start(async () => { throw new Error("probe must run first"); }), /probe must run first/);
    assert.equal(b.live, false);
  });

  await t("a failed probe stops the stream and says why", async () => {
    const b = new Broadcast({ transport: "srt", target: "srt://x/y" });
    await assert.rejects(() => b.probe(async () => false), /probe failed for srt/);
    assert.equal(b.live, false);
  });

  await t("start probes once and then goes live", async () => {
    let probes = 0;
    const b = new Broadcast({ transport: "whip", target: "https://x/y" });
    const r = await b.start(async () => { probes++; return true; });
    assert.equal(r.live, true);
    await b.start(async () => { probes++; return true; });   // already probed
    assert.equal(probes, 1, "the probe must not repeat");
  });

  await t("the probe receives the transport and target it must test", async () => {
    let seen = null;
    const b = new Broadcast({ transport: "srt", target: "srt://host:9000" });
    await b.probe(async (tr, tgt) => { seen = [tr, tgt]; return true; });
    assert.deepEqual(seen, ["srt", "srt://host:9000"]);
  });

  await t("stop ends the stream", async () => {
    const b = new Broadcast({ transport: "rtmp", target: "rtmp://x/y" });
    await b.start(ok);
    assert.equal(b.stop(), false);
  });

  console.log(`RESULT ${passed} passed, ${failed} failed`);
  process.exit(failed === 0 ? 0 : 1);
};

run();